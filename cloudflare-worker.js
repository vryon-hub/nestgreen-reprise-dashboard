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
      const ghResp = await fetch(
        'https://api.github.com/repos/vryon-hub/nestgreen-reprise-dashboard/actions/workflows/refresh.yml/dispatches',
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${env.GITHUB_PAT}`,
            Accept: 'application/vnd.github+json',
            'User-Agent': 'nestgreen-dashboard-worker',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ ref: 'main' }),
        }
      );
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
};
