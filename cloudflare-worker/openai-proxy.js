// Minimal CORS-enabling passthrough to OpenAI's Chat Completions API.
//
// Why this exists: api.openai.com sends no Access-Control-Allow-Origin
// header, so a static site (FloorPlanner, GitHub Pages, no backend) can't
// call it directly from the browser -- every request gets blocked by CORS
// before it even reaches OpenAI. Anthropic's API has a header
// (anthropic-dangerous-direct-browser-access) specifically to allow direct
// browser calls; OpenAI has no equivalent, so this Worker exists purely to
// add that missing CORS header and forward the request unchanged.
//
// This does NOT hold or see your OpenAI key persistently -- it reads the
// key you send per-request (from FloorPlanner's own localStorage, entered
// by you in the app) and forwards it straight to OpenAI. Cloudflare Workers
// don't log request bodies by default. If you want a hard guarantee no
// other site can use this proxy with your key, set ALLOWED_ORIGIN below to
// your FloorPlanner GitHub Pages URL instead of "*".

const ALLOWED_ORIGIN = 'https://slwmoninja.github.io'; // FloorPlanner's actual GitHub Pages origin

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'content-type, authorization',
};

export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }
    if (request.method !== 'POST') {
      return new Response('Only POST is supported.', { status: 405, headers: CORS_HEADERS });
    }

    const authHeader = request.headers.get('authorization');
    if (!authHeader) {
      return new Response('Missing Authorization header.', { status: 401, headers: CORS_HEADERS });
    }

    const body = await request.text();

    const upstream = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'authorization': authHeader,
      },
      body,
    });

    const responseBody = await upstream.text();
    return new Response(responseBody, {
      status: upstream.status,
      headers: { ...CORS_HEADERS, 'content-type': 'application/json' },
    });
  },
};
