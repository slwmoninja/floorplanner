# FloorPlanner OpenAI proxy

FloorPlanner is a static site with no backend, and OpenAI's API doesn't
support direct browser calls (no CORS headers) the way Anthropic's does.
This Worker is a thin passthrough that just adds the missing CORS header
and forwards the request to `api.openai.com` unchanged -- your OpenAI key
still only ever lives in your browser's localStorage and in this Worker's
memory for the duration of a single request; it's never stored anywhere.

## Status: deployed 2026-09-04

Live at `https://floorplanner-openai-proxy.rfwrites2.workers.dev`, locked
to `https://slwmoninja.github.io` (see below) -- the app already has this
URL as its default, so you shouldn't need to touch this unless it needs
redeploying (e.g. after editing `openai-proxy.js`) or you want your own
separate copy.

## Redeploy / deploy your own (~5 minutes)

1. Install Wrangler if you don't have it: `npm install -g wrangler`
2. From this folder, log in: `wrangler login` (opens a browser to authorize
   against your Cloudflare account -- free tier is plenty for this).
3. Deploy: `wrangler deploy`
4. Wrangler prints a URL like `https://floorplanner-openai-proxy.<your-subdomain>.workers.dev`.
   Copy it.
5. In FloorPlanner, open "Generate floor plan" > switch provider to OpenAI,
   and paste that URL into the "Proxy URL" field (replacing the default),
   plus your OpenAI API key (from platform.openai.com/api-keys) into the
   key field.

## Locked to FloorPlanner's own site

`ALLOWED_ORIGIN` in `openai-proxy.js` is set to `https://slwmoninja.github.io`
(not `'*'`), so only requests from FloorPlanner's real deployed origin will
complete in a browser -- others get the CORS header back but it won't match
their origin, so the browser blocks it client-side. This does mean local
testing (e.g. `python -m http.server` on localhost) won't be able to reach
this Worker from OpenAI's provider path; temporarily set `ALLOWED_ORIGIN`
back to `'*'` and redeploy if you need to test that locally, then restore it.
