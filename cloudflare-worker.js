const REPO = 'vryon-hub/nestgreen-reprise-dashboard';
const WORKFLOW = 'refresh.yml';
// Au-delà de ce délai sans run récent (actif ou terminé), on considère
// que le cron GitHub Actions a raté un cycle et on force un nouveau run.
const STALE_THRESHOLD_MINUTES = 20;

function githubHeaders(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_PAT}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'nestgreen-dashboard-worker',
    'Content-Type': 'application/json',
  };
}

async function triggerRefresh(env) {
  return fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: 'POST',
      headers: githubHeaders(env),
      body: JSON.stringify({ ref: 'main' }),
    }
  );
}

async function getLastRun(env) {
  const resp = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1`,
    { headers: githubHeaders(env) }
  );
  if (!resp.ok) return null;
  const data = await resp.json();
  return (data.workflow_runs && data.workflow_runs[0]) || null;
}

// ---------- sondage direct du vrai seuil BackBox (sans passer par GitHub Actions,
// pour répondre en 1-2s au lieu d'attendre le démarrage d'un runner) ----------
const BM_HOST = 'www.backmarket.fr';
const PROBE_DROP_PCT = 0.20;

function bmHeaders(env) {
  return {
    Authorization: `Basic ${env.BM_API_KEY}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
    // Cloudflare bloque le fetch() natif des Workers avec Error 1010 /
    // browser_signature_banned sur www.backmarket.fr sans ce header (même piège
    // que urllib côté Python, cf memoire buyback_backmarket_project.md).
    'User-Agent': 'curl/8.7.1',
  };
}

async function getCompetitor(listingId, market, env) {
  const resp = await fetch(`https://${BM_HOST}/ws/buyback/v1/competitors/${listingId}`, {
    headers: bmHeaders(env),
  });
  if (!resp.ok) throw new Error(`competitors HTTP ${resp.status}`);
  const data = await resp.json();
  const entry = data.find(e => e.market === market);
  if (!entry) throw new Error(`marché ${market} absent de la réponse`);
  return {
    price: parseFloat(entry.price.amount),
    priceToWin: parseFloat(entry.price_to_win.amount),
    isWinning: entry.is_winning,
  };
}

async function setPrice(listingId, market, amount, env) {
  const resp = await fetch(`https://${BM_HOST}/ws/buyback/v1/listings/${listingId}`, {
    method: 'PUT',
    headers: bmHeaders(env),
    body: JSON.stringify({ prices: { [market]: { amount: amount.toFixed(2), currency: 'EUR' } } }),
  });
  if (!resp.ok) throw new Error(`PUT prix HTTP ${resp.status}`);
}

const round2 = n => Math.round(n * 100) / 100;

// Simulation brute : pousse le prix à -20% et renvoie tel quel ce que BackMarket
// répond (price_to_win, is_winning) -> aucune décision automatique (ni retour en
// arrière, ni optimisation) : le prix reste au niveau simulé, à l'utilisateur de
// décider ensuite quoi en faire (le garder, le baisser encore, le remonter).
async function probePriceLive(listingId, market, env) {
  const before = await getCompetitor(listingId, market, env);
  if (!before.isWinning) {
    return { status: 'not_winning_already_reliable', original_price: before.price, price_to_win: before.priceToWin };
  }

  const probePrice = round2(before.price * (1 - PROBE_DROP_PCT));
  await setPrice(listingId, market, probePrice, env);
  const after = await getCompetitor(listingId, market, env);

  return {
    status: 'simulated',
    original_price: before.price,
    new_price: probePrice,
    price_to_win: after.priceToWin,
    is_winning: after.isWinning,
  };
}

// Surveillance périodique (Cloudflare Cron Trigger) : compense le cron
// GitHub Actions qui saute parfois plusieurs cycles sans raison identifiable.
// Si le dernier run date de plus de STALE_THRESHOLD_MINUTES et qu'aucun run
// n'est en cours, on force un nouveau déclenchement.
async function watchdog(env) {
  const last = await getLastRun(env);
  if (!last) {
    console.log('watchdog: aucun run trouvé via l\'API GitHub');
    return;
  }

  const isActive = last.status === 'in_progress' || last.status === 'queued';
  const ageMinutes = (Date.now() - new Date(last.created_at).getTime()) / 60000;
  console.log(`watchdog: dernier run ${last.created_at} (status=${last.status}, age=${ageMinutes.toFixed(1)}min)`);

  if (isActive) return;

  if (ageMinutes > STALE_THRESHOLD_MINUTES) {
    console.log('watchdog: run manqué détecté, déclenchement forcé');
    const resp = await triggerRefresh(env);
    console.log(`watchdog: dispatch -> status ${resp.status}`);
  }
}

export default {
  async fetch(request, env) {
    const expected = 'Basic ' + btoa(`${env.BASIC_AUTH_USER}:${env.BASIC_AUTH_PASS}`);
    const auth = request.headers.get('Authorization');

    if (auth !== expected) {
      return new Response('Authentification requise', {
        status: 401,
        headers: { 'WWW-Authenticate': 'Basic realm="Nestgreen Reprise"' },
      });
    }

    const url = new URL(request.url);

    // Déclenche le workflow GitHub Actions de rafraîchissement depuis le bouton
    // "Forcer la mise à jour" du dashboard -> compense le cron GitHub Actions
    // qui ne se déclenche pas de façon fiable tout seul. Le token GitHub reste
    // uniquement ici (secret Worker), jamais exposé côté navigateur.
    if (url.pathname === '/force-refresh' && request.method === 'POST') {
      const ghResp = await triggerRefresh(env);
      if (ghResp.status === 204) {
        return new Response(JSON.stringify({ ok: true }), {
          headers: { 'Content-Type': 'application/json' },
        });
      }
      const errText = await ghResp.text();
      return new Response(JSON.stringify({ ok: false, status: ghResp.status, error: errText }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Sonde/optimise le vrai seuil BackBox sur UN listing×marché précis, en direct
    // (pas de passage par GitHub Actions -> réponse en 1-2s au lieu de ~1 min).
    // Toujours déclenché manuellement depuis le bouton "Sonder ce prix", jamais en masse.
    if (url.pathname === '/probe-price' && request.method === 'POST') {
      let payload;
      try {
        payload = await request.json();
      } catch {
        return new Response(JSON.stringify({ ok: false, error: 'JSON invalide' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      const { listing_id, market } = payload || {};
      if (!listing_id || !market) {
        return new Response(JSON.stringify({ ok: false, error: 'listing_id et market requis' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      try {
        const result = await probePriceLive(listing_id, market, env);
        return new Response(JSON.stringify({ ok: true, ...result }), {
          headers: { 'Content-Type': 'application/json' },
        });
      } catch (err) {
        return new Response(JSON.stringify({ ok: false, error: String(err && err.message || err) }), {
          status: 502,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    const upstream = 'https://vryon-hub.github.io/nestgreen-reprise-dashboard' + url.pathname + url.search;
    const resp = await fetch(upstream, { cf: { cacheTtl: 0 } });
    const newResp = new Response(resp.body, resp);
    newResp.headers.set('Cache-Control', 'no-store');
    return newResp;
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(watchdog(env));
  },
};
