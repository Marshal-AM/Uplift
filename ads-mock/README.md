# Uplift Google Ads mock

A standalone, static frontend that mocks **Google Search** and **Google Ads** for the Uplift demo. It shows how the
campaigns Uplift builds would appear to shoppers and how they would perform in the advertiser's account, without
Google Ads credentials.

It shows one of two things, named in the strip at the top of every page:

- **A finished Uplift run.** The campaigns, ad groups, keywords, negatives, ad copy, bids and budgets come from the
  run's verified Google Ads deliverable (Sasha's Google Ads Editor file and economics). Keyword demand and search
  terms come from Kai, Google Shopping competitors and ranking pages from Rafael, "People also ask" from Leo's FAQ,
  the product copy from Clara, and the product image from Iris.
- **The demo store** (`lib/data.ts`): a fictional store, used when no run is connected.

Either way the traffic numbers are simulated, nothing talks to Google, and every page carries a **MOCK** strip.

## What's in it

| Route | What it mocks |
| --- | --- |
| `/` | Google home page |
| `/search/?q=…` | Search results: the store's responsive search ad with sitelinks, a competitor ad, Sponsored products carousel, organic results, People also ask, related searches, and an **Ad preview and diagnosis** panel that explains why the ad does or doesn't show (keyword match, negative keyword, paused campaign) |
| `/search/?q=…&tbm=shop` | Shopping tab with filters and product grid |
| `/store/` | The fictional storefront an ad click lands on |
| `/ads/` | Google Ads Overview: metric tiles, performance chart, campaigns, search terms, keywords, Performance Max networks |
| `/ads/campaigns/` · `ad-groups/` · `ads/` · `keywords/` · `search-terms/` · `negative-keywords/` · `products/` · `recommendations/` | The matching Google Ads pages |

**The simulation.** Campaigns start **Paused**, as Uplift creates them. Enabling them (status dot, the Enable
button, or the recommendation) plays a 30-day time-lapse. Daily traffic comes from each keyword's demand, quality
score and expected CTR, capped by the daily budget, so "Limited by budget" and the budget recommendation behave
for real. The numbers are deterministic. State lives in the browser (localStorage); **Reset mock** in the top strip
clears it.

## Showing a run

The data comes from the Worker's `/ads` API (`services/worker/src/uplift_worker/ads_api.py`):

| Link | Shows |
| --- | --- |
| `/?key=<view key>` | The newest run with a passed Google Ads deliverable. The key is the `/live` page's `TRACE_VIEW_KEY`; it is remembered and removed from the address bar. The strip then offers a run picker, **Latest run** and **Use demo data**. |
| `/ads/?task=<task id>&t=<token>` | One run, from the "Preview your Google Ads campaigns (mock)" link Nora posts when a Task finishes. The token opens that run only. |
| `/` with neither | The demo store, with **Connect to Uplift runs** in the strip. |

Configuration:

- **Mock:** `NEXT_PUBLIC_UPLIFT_API`, the Worker's URL (defaults to the production Worker).
- **Worker:** add the mock's URL to `TRACE_ORIGINS` (CORS) and set `ADS_MOCK_URL` to it so Nora's final comment links
  each run. `http://localhost:3100` is allowed by default.

Nothing is invented for a run: what no agent produces (competitor text ads, sitelinks, star ratings) is not shown.

## Run locally

```sh
npm install
npm run dev        # http://localhost:3100
```

## Build and deploy

```sh
npm run build      # static site in out/
npm run preview    # serve out/ on http://localhost:3100
```

`out/` is a plain static site, so it can be hosted anywhere:

- **Railway (live):** service `ads-mock`, Root Directory `/ads-mock`, deployed on every push that touches
  `ads-mock/` (`railway.json` serves `out/` on `$PORT`), at https://ads-mock-production.up.railway.app.
  `NEXT_PUBLIC_UPLIFT_API` is set on the service; the Worker has the URL in `TRACE_ORIGINS` and `ADS_MOCK_URL`.
- **Vercel:** import the repo, set **Root Directory** to `ads-mock`. The defaults (`npm run build`, Next.js) work.
- **Netlify / Cloudflare Pages / S3:** build command `npm run build`, publish directory `ads-mock/out`.

`scripts/fix-export.mjs` runs after `next build`. Next 16 writes link-prefetch files in nested folders, but the
browser requests flat names. The script copies them to those names, so static hosts don't answer every prefetch
with a 404.

## Editing the mock

The demo store is in `lib/data.ts` (its `Dataset` type is the shape the Worker returns for a run), loading and
switching runs in `lib/dataset.ts`, and the traffic model in `lib/sim.ts`. Keep demo brands and domains fictional
(`.example` domains) and keep the **Mock** labels.
