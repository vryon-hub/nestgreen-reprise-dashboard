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
    const upstream = 'https://vryon-hub.github.io/nestgreen-reprise-dashboard' + url.pathname + url.search;
    const resp = await fetch(upstream, { cf: { cacheTtl: 0 } });
    const newResp = new Response(resp.body, resp);
    newResp.headers.set('Cache-Control', 'no-store');
    return newResp;
  },
};
