# Uplift Google Ads mock

A standalone, static frontend that mocks **Google Search** and **Google Ads** for the Uplift demo. It shows how the
campaigns Uplift builds would appear to shoppers and how they would perform in the advertiser's account, without
Google Ads credentials.

Everything is hardcoded mock data (`lib/data.ts`): the store, product, ads, keywords, competitors and results are
fictional. Every page carries a **MOCK** strip, and nothing talks to Google or to the Uplift backend.

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

- **Vercel:** import the repo, set **Root Directory** to `ads-mock`. The defaults (`npm run build`, Next.js) work.
- **Netlify / Cloudflare Pages / S3:** build command `npm run build`, publish directory `ads-mock/out`.

`scripts/fix-export.mjs` runs after `next build`. Next 16 writes link-prefetch files in nested folders, but the
browser requests flat names. The script copies them to those names, so static hosts don't answer every prefetch
with a 404.

## Editing the mock

All content is in `lib/data.ts` (store, product, ad assets, keywords, negatives, competitors, results) and the
traffic model in `lib/sim.ts`. Keep brands and domains fictional (`.example` domains) and keep the **Mock** labels.
