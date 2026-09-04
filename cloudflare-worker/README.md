# FloorPlanner OpenAI proxy

FloorPlanner is a static site with no backend, and OpenAI's API doesn't
support direct browser calls (no CORS headers) the way Anthropic's does.
This Worker is a thin passthrough that just adds the missing CORS header
and forwards the request to `api.openai.com` unchanged -- your OpenAI key
still only ever lives in your browser's localStorage and in this Worker's
memory for the duration of a single request; it's never stored anywhere.

## Deploy (one-time, ~5 minutes)

1. Install Wrangler if you don't have it: `npm install -g wrangler`
2. From this folder, log in: `wrangler login` (opens a browser to authorize
   against your Cloudflare account -- free tier is plenty for this).
3. Deploy: `wrangler deploy`
4. Wrangler prints a URL like `https://floorplanner-openai-proxy.<your-subdomain>.workers.dev`.
   Copy it.
5. In FloorPlanner, open "Generate floor plan" > switch provider to OpenAI,
   and paste that URL into the "Proxy URL" field, plus your OpenAI API key
   (from platform.openai.com/api-keys) into the key field.

## Optional: lock the proxy to your own site

By default `ALLOWED_ORIGIN` in `openai-proxy.js` is `'*'`, meaning any site
could technically route a request through your Worker (they'd still need
their own OpenAI key to get a real response, but it's cleaner to lock it
down). Once FloorPlanner is deployed to its GitHub Pages URL, edit
`ALLOWED_ORIGIN` to that exact URL and redeploy with `wrangler deploy`.
