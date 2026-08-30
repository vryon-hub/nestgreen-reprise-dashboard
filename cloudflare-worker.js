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

// Surveillance périodique (Cloudflare Cron Trigger) : compense le cron
// GitHub Actions qui saute parfois plusieurs cycles sans raison identifiable.
// Si le dernier run date de plus de STALE_THRESHOLD_MINUTES et qu'aucun run
// n'est en cours, on force un nouveau déclenchement.
async function watchdog(env) {
  const last = await getLastRun(env);
  if (!last) return;

  const isActive = last.status === 'in_progress' || last.status === 'queued';
  if (isActive) return;

  const ageMinutes = (Date.now() - new Date(last.created_at).getTime()) / 60000;
  if (ageMinutes > STALE_THRESHOLD_MINUTES) {
    await triggerRefresh(env);
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
