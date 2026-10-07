# Uplift — Agent Spec Sheet (v5)

Companion to **[Uplift_Product_Spec.md](Uplift_Product_Spec.md)**. For every coworker, this sheet covers:
- its Sokosumi listing;
- its standalone inputs, workflow, external services and outputs;
- how it behaves when Nora runs it as part of an Uplift plan;
- its Kodosumi implementation;
- the Chainlink CRE verifier profile that scores it and decides whether it is paid.

**Section legend used for every agent:**

| Code | Section |
|---|---|
| **L** | Listing (Sokosumi Coworker profile and Masumi registration) |
| **S** | Standalone inputs (what the merchant must provide) |
| **W** | Workflow (steps, each naming its service) |
| **O** | Output (deliverables, plus the store fields and scopes it owns) |
| **U** | In the Uplift flow (what Nora passes in, and who consumes the output) |
| **K** | Kodosumi implementation |
| **X** | External services |
| **V** | CRE verifier profile (run by `uplift-clearing` action `verify`) |
| **F** | Failure handling |

**Conventions**
- **Prices** are Fixed tUSDM on Masumi Registry V2 (`Web3CardanoV2`), equal to Sokosumi credits.
  - One standalone Task, or one run in Nora's plan, is **one unit**.
  - Larger orders are split into several Tasks or runs.
  - Standalone, the merchant pays the specialist's fixed price through Masumi escrow. In Nora's plan, the same price counts toward her one payment, and only if the run passed Chainlink.
- **Store reads** come from the **Uplift Connection Gateway**:
  - in Nora's runs, as a snapshot inside the run input;
  - in standalone mode, as a run-scoped read capability.
- **Store writes** are only ever a `changeset` in the Deliverable Manifest. CRE `publish` executes them after the merchant approves the change set in Sokosumi.
- **Questions to the merchant** use Task `INPUT_REQUIRED`, raised via Kodosumi `tracer.lock`, in standalone mode only.
  - In Nora's runs, inputs are complete. A missing input makes the run fail fast with reason `INPUT_MISSING`, and Nora asks the merchant instead.
- **All LLM inference** uses **Grok 4.7 on Amazon Bedrock**:
  - bedrock-runtime Chat Completions API (OpenAI-compatible), inference profile `us.xai.grok-4.7` in `us-east-1`, called over HTTPS with a Bedrock API key.
  - JSON output via a forced function call, and vision via `image_url` content parts.
  - Translation, grammar, image OCR and keyword clustering are Grok 4.7 calls.
- **Image work** is Iris's alone: **Gemini Nano Banana 2.1** renders studio shots and lifestyle scenes from the merchant's photo, and Grok 4.7 vision checks each render's fidelity against that photo.
- **CRE judge**
  - One judge: Claude Grok 4.7 on Bedrock, called via Confidential HTTP with `Authorization: Bearer {{.bedrockApiKey}}`.
  - It contributes at most 5 points in any profile.
  - If the judge call errors, those points are scored at the neutral midpoint.
- **Every verify result** (score and PASS/FAIL) is posted as a comment on the Sokosumi Task.
- **Deliverables**
  - Every deliverable is written to Kodosumi `/out` and mirrored to the S3 artifact store (content-addressed).
  - In standalone mode, deliverables are also attached to the Task (`POST /v1/tasks/{id}/files`).
  - The `final` result is the canonical Deliverable Manifest string.

---

## 0. Nora — Uplift Lead

### L — Listing
| Field | Value |
|---|---|
| `name` | Nora |
| `caption` | Uplift Lead · E-commerce Growth Manager |
| `description` | "Your AI e-commerce growth and ads team lead, focused on getting your products ranked higher. Tell Nora what you want: launch a product, fix a listing that isn't selling, plan a promotion, go international. She builds a plan with the right specialists (keyword research, competitor and review analysis, pricing, copy, product photos, catalog and shopping feeds, translation, content and email copy, paid ads, compliance, auditing) and tells you up front the most it can cost. You pay only for the specialists whose work passes. She runs the work, has every deliverable scored and verified by Chainlink, publishes only what you approve, and hands you a before/after report. Works with Shopify stores and Google Ads today." |
| `capabilities` | `tasks`, `chat` |
| `metadata.tags` | ecommerce, shopify, product launch, listing optimization, conversion rate optimization, CRO, SEO, google shopping, google ads, marketing team, growth |
| Masumi registration | `uplift-lead`, **Dynamic** pricing (`supportedPaymentSources[].pricing = {"pricingType":"Dynamic"}`). No fee of her own: each Task's price is the specialists whose work passed, plus Quinn's after-report. |

### S — Inputs
| Input | Required | How obtained |
|---|---|---|
| Request in plain language | ✅ | Chat or Task description |
| Store connection (Shopify in v1) | ✅ if the listing is touched | `AUTHENTICATION_REQUIRED` → Gateway OAuth |
| Target product(s) | ✅ | Product URL or handle, or picked from a list Nora posts as `INPUT_REQUIRED` |
| Budget cap (credits) | optional | Caps the plan's ceiling |
| Markets and locales | optional | Default: the store's primary market |
| Brand voice samples, locked terms | optional | Files or text |
| Ads and analytics connection (Google in v1) | only if the plan needs it | Requested per plan |

### W — Workflow
**Phases:** start → intake → [auth_wait | input_wait] → plan → quote_wait → execute → merge → pay → propose → approval_wait → publish → report → deliver → done.

1. **Intake.** Bedrock (Grok 4.7) extracts the goal, products, markets, constraints and capability tags.
2. **Connection check.** Nora asks the Gateway whether a link exists for this user or organization. If not, she posts `AUTHENTICATION_REQUIRED` with the connect URL and waits for the Gateway callback.
3. **Baseline.** Nora takes a store snapshot (Gateway read). Whenever a listing will change or a diagnosis is requested, she runs **Quinn** in audit mode alongside the first wave of specialists.
4. **Routing.** §0.3 picks the specialists, and dependencies are closed in code (§0.4).
5. **Quote.** Nora posts a markdown plan and sets `APPROVAL_REQUIRED`.
   - The plan covers agents, deliverables, order, credits, and what will still need the merchant.
   - The total is a ceiling: "at most X credits". The merchant pays only for the specialists whose work passes.
   - It includes a fenced JSON block with the plan (roles and credits), which CRE reads.
6. **Plan approval.** Nora watches the Task events.
   - A user-authored move to **Ready** or **Running**, or an "approve" comment, approves the plan.
   - Any other comment is a change request: Nora re-plans and re-quotes.
7. **Execution.** Nora walks the DAG (§0.5). For each node:
   - build the input (envelope in product spec §6.1);
   - run the specialist's agent directly: the same Kodosumi deployment registered on Masumi as that specialist (no Sokosumi Job, no per-agent escrow);
   - journal the run ID;
   - when the run finishes, call CRE `uplift-clearing` action `verify`, mode `task` (HTTP trigger, JWT signed with the Worker's authorized key).

   Nodes with no unmet dependencies run in parallel.
8. **Gate.** The CRE result is posted as a Task comment. CRE also checks that the role is in the plan the merchant approved.
   - **PASS:** the manifest is released downstream.
   - **FAIL:** Nora retries once, with `failure_reasons` in the input. A failed run is never billed.
   - **Second FAIL:** the node is left out of the change set, and the change-approval comment names it.
9. **Merge.** Nora collects every changeset and resolves field ownership (§0.6) into change groups: store product, translations, discounts, collections, content, ad campaigns.
10. **Compliance and projection.**
    - **Ruth's** run covers all public-facing text and images. Any op at a location where a high-severity finding has no passing rewrite is dropped from the change set.
    - Nora projects the after-score by applying the merged changeset to the baseline snapshot and running the deterministic Listing Score sections.
11. **Pay.** Nora reveals the price: the specialists whose work passed Chainlink, plus Quinn's after-report (it runs once the changes are live).
    - She requests one Masumi payment for that amount: `POST /payment` with `RequestedFunds` in tUSDM (1 credit = 1 tUSDM), then Task event `masumiPayment`.
    - Sokosumi Core debits the merchant's credits when it accepts the payment. Out of credits, the Task ends `OUT_OF_CREDITS`, and nothing is published or delivered.
12. **Change approval.** Nora posts the change set as a Task comment and sets `APPROVAL_REQUIRED`. The comment contains:
    - a plain-language summary;
    - changes by owner;
    - before/after excerpts;
    - `change_hash`;
    - an attached `changes.html` diff.
13. **Publish.** When the merchant approves (Ready/Running, or "approve") and the escrow shows `FundsLocked`, Nora calls `uplift-clearing` action `publish`.
    - CRE confirms the approval, publishes through the gateway, re-reads the store, and returns the after-score.
    - If no write was attempted, Nora retries `publish` once on error.
14. **After-report.** Nora runs Quinn (before/after mode).
15. **Deliver.** Nora uploads the **Launch Pack** (a ZIP with every deliverable's summary and manifest) to the Task, submits the result hash to the MPS, and sets `COMPLETED`.

### §0.3 Routing
- **Capability tags:** `keywords`, `competitors`, `reviews`, `pricing`, `copy`, `visuals`, `catalog`, `localization`, `content`, `email`, `ads`, `compliance`, `audit`, `analytics`.
- **Keyword score:** matches against each specialist's name and caption (counted ×2), description and tags.
- **LLM fit check:** "Can this agent do what the request asks? A related topic is not enough." A specialist needs fit ≥ 0.4.
- **Full flow:** selected for "launch", "overhaul", "full optimization", a new product, or requests matching ≥ 6 tags.

### §0.4 Dependency closure (code)
| If the plan contains | Add |
|---|---|
| Clara, Leo, Sasha, or Yuki needing local keywords | **Kai**, unless the merchant supplied a keyword list |
| Clara, Leo, Iris, or Sasha | **Priya**, when competitors are known or discoverable (≥1 competitor product with ≥20 public reviews). Otherwise Priya is skipped, with a note in the quote. |
| Priya | **Rafael**, unless the merchant named the competitors |
| Marcus | **Rafael** (price bands) |
| Sasha | **Marcus** (margin), plus **Iris** if Performance Max is in scope (image assets) |
| Leo together with Clara | Leo runs **after** Clara, to reuse her facts and voice |
| Yuki | Runs after Kai (local seeds) and Clara, and translates Clara's new copy rather than the copy it replaces |
| Any changeset to the store or ad account | **Ruth** |
| Any listing change or diagnosis | **Quinn** (baseline and after) |

### §0.5 Full-flow DAG
1. **Phase 0:** Quinn baseline. It runs alongside Phase 1 rather than ahead of it: only the after-report reads it, and the store does not change before publish.
2. **Phase 1:** Kai, then Rafael (he searches Google with Kai's real keywords), then Priya.
3. **Phase 2:** Marcus.
4. **Phase 3:** Clara, Iris and Oskar in parallel, then Leo, then Sasha.
5. **Phase 4:** Yuki, as soon as Clara has passed (alongside Leo and Sasha).
6. **Phase 5:** Ruth.
7. **Phase 6:** Quinn projection, then payment, change approval and publish.
8. **Phase 7:** Quinn after-report, then close.

**Example plan (1 product, 2 locales):** at most 18.00 credits. The final price counts only the runs that passed Chainlink, plus Quinn's after-report.

| Agent | Credits |
|---|---|
| Kai | 1.25 |
| Rafael | 1.25 |
| Priya | 1.50 |
| Marcus | 1.25 |
| Clara | 2.00 |
| Iris | 2.50 |
| Oskar | 1.50 |
| Yuki × 2 | 2.00 |
| Leo | 2.00 |
| Sasha | 1.50 |
| Ruth | 0.25 |
| Quinn × 2 | 1.00 |

### §0.6 Field ownership (CRE publishes a change only to its owner's fields)
| Target | Owner |
|---|---|
| `title`, `descriptionHtml`, `handle` (+ redirect), `seo.title`, `seo.description`, `tags` (copy tags) | Clara |
| `category`, category metafields (attributes), `productType`, `vendor`, `tags` (taxonomy tags), collections, related/complementary metafields | Oskar |
| Media (add, reorder), image alt text | Iris |
| Translations | Yuki |
| Discount codes | Marcus |
| `custom.faq`, `custom.comparison` metafields, blog articles | Leo |
| Ad campaigns (paused; Google Ads in v1) | Sasha |

**Never touched:** price, compare-at price, inventory, variants, product status, orders, customers, theme files.

### O — Output
- Plan comment with the price ceiling.
- Per-run verification comments.
- Price comment and one Masumi payment.
- Launch Pack (ZIP).
- Change-approval comment with the diff file.
- Final before/after report.

### K — Kodosumi
- Nora has no Kodosumi flow. Intake, planning, merging and her state machine run in the Uplift Worker (Bedrock via the Worker's API key), because they need Sokosumi coworker credentials and long waits.

### X — Services
| Service | Use |
|---|---|
| Amazon Bedrock (Grok 4.7) | Intake, planning, merging, report writing |
| Sokosumi Core API | Task events and approvals, `masumiPayment`, files, receipt |
| Kodosumi | Runs each specialist's deployment directly |
| Uplift Connection Gateway | Snapshots, connection status |
| Chainlink CRE HTTP trigger | `verify`, `publish` (JWT signed with the Worker's authorized key) |
| Uplift MPS | Nora's payment (`POST /payment` with `RequestedFunds`), `FundsLocked` status, result submission |

### V — Verifier (Nora)
- Every specialist run is checked against the approved plan JSON. Out-of-plan runs FAIL and are not billed.
- Publishing happens only after the merchant approves the change set.

---

## 1. Kai — Search Demand Analyst

### L
| Field | Value |
|---|---|
| `caption` | Search Demand Analyst |
| `description` | "Finds what your customers actually search for. Give Kai your product and market and get a clustered keyword map built from real Google autocomplete suggestions, related searches and shopper questions, with a demand signal for each keyword, buyer intent, and where to use each cluster: product title, description, blog or ads." |
| `tags` | keyword research, SEO, google autocomplete, search intent, keyword clusters, ecommerce SEO, PPC keywords |
| Unit · price | per product or topic, per market · **1.25** |

### S
| id | MIP-003 type | Req. | Notes |
|---|---|---|---|
| `product` | textarea | ✅ | Product name and short description, **or** `product_url` |
| `product_url` | url | — | Read via Firecrawl, or via the Gateway if connected |
| `market_country` | option | ✅ | e.g. US, DE, JP; maps to Serper `gl` |
| `language` | option | ✅ | Serper `hl` |
| `seed_keywords` | textarea | — | One per line |
| `competitor_domains` | textarea | — | Competitor brands to filter |
| `exclude_terms` | textarea | — | Brand terms to avoid |
| `own_brand_terms` | textarea | — | Allowed brand terms |

**Questions it may ask:** the market, if it cannot be inferred.

### W
1. **Normalize the product.** Firecrawl `/scrape` on `product_url`, or the Gateway snapshot. Bedrock (Grok 4.7) extracts attributes and use cases, plus 10–20 seed keywords (merged with `seed_keywords`).
2. **Expand.** For up to 12 seeds, in the target market and language:
   - Serper `/autocomplete`: Google autocomplete suggestions, with their position.
   - Serper `/search`: related searches and People Also Ask questions.
   - Each keyword keeps its source evidence (type, seed query, autocomplete position).
3. **Demand signal** (deterministic, 0–100). Points per source: autocomplete = max(1, 10 − position), related search = 4, People Also Ask = 2, seed = 3. Summed per keyword and normalized to the top keyword.
4. **Brand and trademark filter.**
   - Build a brand-term set from `exclude_terms`, competitor domains, and brand names Bedrock (Grok 4.7) detects in the keyword list, minus `own_brand_terms`.
   - Keywords containing other companies' marks move to negatives.
5. **Cluster.** Bedrock (Grok 4.7) groups the keywords into clusters of the same shopper need, every keyword in exactly one cluster, and gives each cluster:
   - a name;
   - an on-page role: `title`, `description`, `seo_meta`, `blog`, `ads_exact`, `ads_phrase` or `negative`;
   - a search intent: `informational`, `commercial`, `transactional` or `navigational`.
6. **Write the deliverables.** Primary keyword (best `title` keyword) and up to 12 secondary keywords.

### O
- `keyword_map.json` / `.csv` (keyword, demand, intent, cluster, role)
- `negatives.txt`
- `summary.md`
- **Store writes:** none

### U
- **Input:** snapshot and market from Nora; competitor domains from Rafael when he ran first.
- **Consumers:**
  - Clara
  - Leo
  - Sasha (ad groups, negatives)
  - Yuki (local seeds)
  - Oskar (tags, collection names)
  - Quinn (keyword placement, ranking snapshot)

### K
- Expose `kai`, entrypoint `run(inputs, tracer)`.
- Step 2 fans out over the seeds, 4 concurrent Serper calls.
- Lock: `market` (standalone only).
- Dependencies: `httpx`, `boto3` (in the Kodosumi image).

### X
| Step | Service | API |
|---|---|---|
| 1 | Firecrawl | `POST /v2/scrape` |
| 1, 4, 5 | Amazon Bedrock | Chat Completions (Grok 4.7) |
| 2 | Serper.dev | `POST /autocomplete` (`suggestions`), `POST /search` (`relatedSearches`, `peopleAlsoAsk`) |

### V — `kai@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| No foreign trademarks | Deterministic match against the brand-term set in the bundle | 20 |
| Demand recomputed | Demand scores recomputed from the bundle's sources match | 20 |
| Cluster integrity | Each keyword in exactly one cluster; valid roles | 15 |
| Intent labels | Every keyword has a valid intent label | 10 |
| Keywords are real | Confidential HTTP Serper autocomplete re-run for up to 5 sampled autocomplete-sourced keywords; ≥60% reappear | 30 |
| Judge | Relevance of top clusters to the product | 5 |

### F
- **No keywords found:** the run fails with a clear message.
- **Serper errors:** retries with backoff on rate limits and server errors, then `SOURCE_UNAVAILABLE`.

---

## 2. Rafael — Competitor & Market Analyst

### L
| Field | Value |
|---|---|
| `caption` | Competitor & Market Analyst |
| `description` | "Shows you who you're really up against. Rafael looks at who ranks on Google and Google Shopping for your product, what they charge, what they promise, how they present the offer (shipping, bundles, guarantees) and where the gaps are. Every finding links to its source." |
| `tags` | competitor analysis, market research, google shopping, SERP analysis, price benchmarking, positioning, ecommerce competitors |
| Unit · price | per product or category, per market · **1.25** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| `product` / `product_url` | textarea / url | ✅ | |
| `market_country`, `language` | option | ✅ | |
| `known_competitors` | textarea | — | Domains or product URLs |
| `price_point` | number | — | Merchant's price, for positioning |
| `max_competitors` | number | — | Default 8, max 15 |

### W
1. **Query set.** Up to 5 head queries: Kai's map if present, otherwise Bedrock (Grok 4.7).
2. **Google results.**
   - Serper `/search` (top 20) per query: SERP rows (position, domain, link) and People Also Ask.
   - Serper `/shopping` for the first query: Shopping offers (title, seller, price, rating, rating count, product ID).
3. **Competitor set.**
   - Rank domains by visibility (sum of 1/position across the SERP rows), excluding the merchant's own domain.
   - Add `known_competitors` and keep the top N.
4. **Product pages.**
   - Firecrawl `/scrape` (rendered) with a JSON extraction schema covering: title, price, compare-at price, currency, claims, guarantees, shipping/returns text, bundles, image count, video, review count and rating, and JSON-LD `Product`/`Offer`/`AggregateRating`.
   - For Shopify stores, also read the public `/products/{handle}.js` when exposed.
5. **Analysis.**
   - Price bands (min, p25, median, p75, max), computed deterministically from competitor page prices and parsed Shopping offer prices.
   - Claim frequency, offer patterns and content gaps.
   - A positioning map via Bedrock (Grok 4.7).
6. **Write the deliverables.**

### O
- `competitor_matrix.csv` / `.json` (evidence URL per cell)
- `price_bands.json`
- `positioning.md`
- `gaps.md`
- `competitor_set.json` (competitor product URLs; Google Shopping offers with title, product ID, seller, price, rating and rating count; competitor brands; feeds Priya and Sasha)
- **Store writes:** none

### U
- **Consumers:**
  - Priya
  - Marcus (price bands)
  - Clara and Leo (claims to beat, comparison facts)
  - Sasha (competitor angles, brand negatives)
  - Iris (visual benchmarks)

### K
- Expose `rafael`.
- Ray fan-out over competitor URLs, with ≤8 concurrent Firecrawl calls.
- Lock: competitor confirmation (standalone, optional).

### X
| Service | Endpoints |
|---|---|
| Serper.dev | `POST /search` (`organic`, `peopleAlsoAsk`), `POST /shopping` |
| Firecrawl | `/v1/scrape` with JSON extraction |
| Shopify public storefront | `/products/{handle}.js` |
| Amazon Bedrock | Grok 4.7 |

### V — `rafael@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Cited pages support the facts | Re-fetch 3 sampled evidence URLs (regular HTTP, consensus on the extracted field; one Confidential fetch for volatile pages); ≥2 of 3 contain the claimed title or a price within ±10% | 35 |
| Band maths | Recomputed | 20 |
| Ranking sanity | One Serper search: ≥3 of the claimed top-5 domains appear in the top 10 | 20 |
| Coverage | ≥4 competitors with ≥5 filled attributes | 15 |
| Judge | Positioning consistent with the matrix | 5 |
| Evidence URLs | https | 5 |

### F
- **Blocked pages:** marked `unavailable` and excluded from coverage; Shopping offer prices still feed the price bands.

---

## 3. Priya — Competitor Review & Sentiment Analyst

> Priya analyzes **what competitors' customers say**, never the merchant's own reviews. She tells the merchant what buyers in the category love, hate and still wish for, so the listing, offer and ads can win on exactly those points.

### L
| Field | Value |
|---|---|
| `caption` | Competitor Review & Sentiment Analyst |
| `description` | "Reads thousands of your competitors' customer reviews so you don't have to. Give Priya the competing products (or just your category) and get what customers love, their top complaints, unmet wishes, deal-breakers and the exact words they use. Each point comes with verbatim quotes and links, ready to turn into copy, FAQs, ads and product improvements." |
| `tags` | competitor reviews, customer sentiment, voice of customer, review analysis, amazon reviews, trustpilot, market insights, customer pain points |
| Unit · price | per competitor set (up to 5 products), per market · **1.50** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| `competitor_products` | textarea | ✅ unless `category` | Product URLs or Amazon ASINs/URLs (1–5) |
| `category` | text | ✅ unless products | Priya discovers the top 5 competitors |
| `competitor_domains` | textarea | — | For Trustpilot brand reviews |
| `market_country`, `language` | option | ✅ | |
| `my_product` | textarea / url | — | **Context only.** Its reviews are not analyzed. |
| `focus_aspects` | textarea | — | e.g. "leaks, taste, cleaning" |
| `include_social` | boolean | — | Reddit discussions (default true) |

**Questions it may ask:** confirmation of auto-discovered competitors.

### W
1. **Resolve the competitor set.**
   - From URLs: detect the platform.
   - From Rafael's `competitor_set.json` when present.
   - From a category: Serper `/search` for `<category> site:amazon.com` (Amazon listings) and `best <category>` (brand product pages); up to 5 products.
   - The merchant's own shop domain is excluded.
2. **Collect reviews.**
   - **Amazon:** Bright Data **Amazon Reviews** scraper (by ASIN), ≤300 per product, mixed stars.
   - **Trustpilot:** `https://www.trustpilot.com/review/<domain>` pages read with Firecrawl `/scrape`.
   - **Competitor storefronts:** Firecrawl `/scrape`, parsing JSON-LD `Review` and rendered review-widget text.
   - **Social (optional):** Reddit threads found and excerpted with the **Tavily** Search API (`include_domains: reddit.com`).
3. **Clean.**
   - Dedupe with MinHash.
   - Drop reviews under 5 words.
   - Reviews in any language are coded directly by Grok 4.7; quotes stay in their original language.
4. **Aspect-based sentiment.** Bedrock (Grok 4.7) codes batches of 50 reviews against a JSON schema:
   - aspects;
   - polarity −2..+2;
   - flags `is_wish`, `is_dealbreaker`, `switch_reason`;
   - `use_case`, `buyer_type`.
5. **Aggregate** (deterministic).
   - Aspect frequency and net sentiment per competitor and overall.
   - Recency weighting: the last 18 months count ×2.
   - Rank Loves, Complaints, Wishes and Deal-breakers.
6. **Quotes.** 3–5 verbatim quotes per finding, each with source URL, stars and date.
7. **Buyer personas.** 2–4 personas, built only from coded reviews. Each attribute cites ≥3 review IDs.
8. **"How to win" synthesis** (Grok 4.7). One action per finding:
   - a listing claim (only if `my_product` supports it);
   - an FAQ;
   - a proof image;
   - an offer or guarantee;
   - an ad angle;
   - a product-improvement idea.

### O
- `competitor_sentiment_report.md`
- `findings.json`
- `coded_reviews.parquet`
- `personas.json`
- `win_plan.json`
- **Store writes:** none

### U
- **Input:** Rafael's `competitor_set.json`, plus the merchant's snapshot as context.
- **Consumers:**
  - Clara (objections, customer language)
  - Leo (FAQ, comparison rows)
  - Iris (proof shots)
  - Marcus (value perception)
  - Sasha (ad angles)

### K
- Expose `priya`.
- Ray fan-out per source. Bright Data runs as an async collect with polling; coding runs in parallel batches.
- Lock: competitor confirmation (standalone only).

### X
| Step | Service | API |
|---|---|---|
| 2 | Bright Data | Amazon Reviews Web Scraper API |
| 1 | Serper.dev | `POST /search` (competitor discovery) |
| 2 | Firecrawl | `/v1/scrape` (storefronts, Trustpilot) |
| 2 | Tavily | Search API (Reddit discussions) |
| 4, 7, 8 | Amazon Bedrock | Grok 4.7 |

### V — `priya@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Quotes are verbatim | Re-fetch the source pages of 5 sampled quotes; fuzzy substring match ≥0.9 similarity; ≥3 of 5 match | 30 |
| Counts recomputed | From the bundle's coded-review table | 25 |
| Competitor-only | No source matches the merchant's shop or primary domain | 15 |
| Persona evidence | Attributes cite existing review IDs | 10 |
| Coverage | ≥100 reviews and ≥2 sources | 10 |
| Judge | Re-codes 10 reviews; checks agreement | 5 |
| Win-plan grounding | Actions reference finding IDs | 5 |

### F
- **<50 reviews:** result is delivered with a `thin_evidence` note.
- **A source fails:** Priya continues with the other sources and notes the gap.

---

## 4. Marcus — Pricing & Promotions Strategist

### L
| Field | Value |
|---|---|
| `caption` | Pricing & Promotions Strategist |
| `description` | "Prices and promotions that sell without killing your margin. Marcus benchmarks your price against the market, models discount scenarios against your real unit costs, plans a promotion calendar around holidays and retail events, and creates scheduled discount codes in your store that never go below your margin floor." |
| `tags` | pricing strategy, promotions, discount codes, black friday, margin, price benchmarking, promo calendar, store discounts |
| Unit · price | per product or campaign · **1.25** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| `product` / connected product | url | ✅ | |
| `goal` | option | ✅ | launch, clearance, seasonal (e.g. BFCM), AOV growth |
| `promo_window` | date range | — | Default: next holiday or retail event |
| `margin_floor_pct` | number | ✅ | e.g. 35 |
| `unit_cost` | number | ✅ unless in Shopify | From `InventoryItem.unitCost` when connected |
| `shipping_cost` | number | — | |
| `discount_limits` | textarea | — | Max %, combinability, once per customer |
| `market_country` | option | ✅ | |

### W
1. **Costs and prices.**
   - Gateway read of variants' `price` and `compareAtPrice`, plus `inventoryItem.unitCost`.
   - A missing cost becomes an `INPUT_REQUIRED` question.
2. **Market prices.** Rafael's `price_bands.json`, or price bands from Serper `/shopping` offers for the product.
3. **Demand calendar.**
   - Public holidays from **Nager.Date** (`/api/v3/PublicHolidays/{year}/{country}`).
   - A maintained retail-event table (Prime Day, BFCM, Singles' Day).
4. **Scenarios** (deterministic).
   - Post-discount margin per mechanic: percent, fixed, threshold, bundle, free shipping.
   - Break-even lift: `ΔQ = d / (m − d)`.
   - Position vs the price bands.
5. **Strategy.** Bedrock (Grok 4.7) chooses:
   - the positioning;
   - list-price guidance (advisory);
   - a calendar of 1–4 promotions.
6. **Discount codes.** `discountCodeBasicCreate` inputs:
   - `title`, `code`;
   - scheduled `startsAt` / `endsAt`;
   - percentage or amount;
   - `items`, `appliesOncePerCustomer`, `usageLimit`, `combinesWith`, `minimumRequirement`.

### O
- `pricing_strategy.md`
- `scenarios.csv`
- `promo_calendar.json` / `.ics`
- `discount_codes.json`
- **changeset:** discount codes (scheduled)
- **Scopes:** `read_products`, `read_inventory`, `read_discounts`, `write_discounts`
- Never writes prices or variants.

### U
- **Input:** Rafael's bands, snapshot.
- **Consumers:**
  - Leo (email offer)
  - Sasha (margin)
  - Clara (offer line)

### K
- Expose `marcus`.
- Single flow; numpy for the scenarios.
- Lock: `unit_cost` (standalone only).

### X
| Service | Use |
|---|---|
| Uplift Gateway (Shopify Admin GraphQL) | Products, variants, `inventoryItem.unitCost`, existing discounts |
| Serper.dev | `POST /shopping` (light market scan) |
| Nager.Date API | Public holidays |
| Amazon Bedrock | Grok 4.7 |

### V — `marcus@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Margin safety | For every code: `(price − discount − unit_cost − shipping) / (price − discount) ≥ floor`, from the gateway snapshot | 35 |
| Dates | `startsAt` in the future, `endsAt` after `startsAt` | 20 |
| Code hygiene | Unique, well-formed codes | 15 |
| Scenario maths | Recomputed | 15 |
| Band references | Position matches the bands | 10 |
| Judge | Rationale | 5 |

---

## 5. Clara — Product Page Copywriter

### L
| Field | Value |
|---|---|
| `caption` | Product Page Copywriter |
| `description` | "Product pages that rank and convert. Clara writes your title, description, SEO title and meta description, URL handle and tags. She uses real search terms, answers the objections buyers raise about competitors, and states only facts about your product. You get three variants scored against a 45-point rubric, with the best one selected." |
| `tags` | product description, copywriting, product title, ecommerce SEO, meta description, ecommerce copy, conversion copywriting |
| Unit · price | per product · **2.00** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| connected product **or** `current_copy` | url / textarea | ✅ | |
| `product_facts` | textarea / file | ✅ if not in store | Specs, materials, dimensions, certifications, care, warranty |
| `target_keywords` | textarea | — | Otherwise Clara runs a mini keyword pass |
| `audience` | text | — | |
| `brand_voice` | textarea / file | — | |
| `forbidden_words` | textarea | — | |
| `locale` | option | ✅ | |

**Questions it may ask:** missing key facts.

### W
1. **Facts ledger.** Build `facts.json` from the snapshot (or the product page) and `product_facts`. Every claim must cite a fact ID.
2. **Keywords.** Kai's map, or `target_keywords`, or Google autocomplete via Serper `/autocomplete` in the locale's market and language (top 15, split into primary and secondary).
3. **Objections and language.** From Priya's findings, when present.
4. **Generate three variants** (Bedrock Grok 4.7, structured output). Each variant contains:
   - `title` (≤70 characters);
   - `descriptionHtml` (sanitized), structured as hook → benefits → specs → use cases → objection answers → care and guarantee;
   - `seo.title` (≤60), `seo.description` (≤155);
   - `handle`;
   - copy `tags`.
5. **Self-score** each variant on the 45-point rubric and pick the best.
   - Grammar and spelling check by Grok 4.7.
   - Readability via Flesch (textstat).
6. **Redirect.** If the handle changes, the changeset includes a redirect from the old path.

### O
- `copy_variants.json`
- `selected_copy.html`
- `facts.json`
- `rubric_scores.json`
- **changeset:** `title`, `descriptionHtml`, `handle` (+ redirect), `seo.title`, `seo.description`, copy `tags`
- **Scope:** `write_products`

### U
- **Input:**
  - Kai's map
  - Priya's findings
  - Rafael's claims
  - Marcus's offer line
  - brand constraints
- **Consumers:** Yuki, Leo, Sasha, Ruth, Quinn.

### K
- Expose `clara`.
- The 3 variants run in parallel on Ray.
- Lock: missing facts (standalone only).

### X
| Service | Use |
|---|---|
| Amazon Bedrock | Grok 4.7: facts, generation, self-scoring |
| Serper.dev | `POST /autocomplete` (mini keyword pass) |
| Firecrawl | `current_copy` from URL |
| Uplift Gateway | Snapshot |

### V — `clara@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Format | Length limits (+10% on body sections), sanitized HTML, handle format, no forbidden words | 25 |
| Keyword placement | Primary keyword (or close variant) in title or SEO title, and in the description | 15 |
| Fact grounding | ≥85% of claim sentences map to an existing fact ID | 25 |
| Keyword coverage | ≥ half of the secondary terms used | 10 |
| Objection coverage | ≥2 of Priya's top complaints answered (when Priya ran) | 10 |
| Readability and grammar | Flesch in band; few grammar errors | 10 |
| Judge | Persuasiveness and voice | 5 |
| Ownership | Changeset ⊆ Clara's fields | **hard gate** |

---

## 6. Iris — Product Visual Designer

### L
| Field | Value |
|---|---|
| `caption` | Product Visual Designer |
| `description` | "Product photos that sell on every channel. Upload your product images (or connect your store) and Iris audits them, re-shoots your product as a clean white studio photo, places it in realistic lifestyle scenes, and exports ready-to-use versions for your store, Google Shopping, Google Ads and Amazon. Every new image is checked against your original photo so the product stays true to life. She also writes the alt text and recommends the image order." |
| `tags` | product photography, product images, white background, lifestyle images, image editing, google shopping images, amazon main image, ecommerce visuals, alt text |
| Unit · price | per product (up to 8 source images and 4 lifestyle scenes) · **2.50** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| `images` (file, multiple) **or** connected product | file / url | ✅ | JPEG/PNG/WebP, ≥800 px |
| `product_name`, `category` | text | ✅ | |
| `channels` | option (multi) | ✅ | Store product page, Google Shopping, Google Ads (PMax), Amazon main, social |
| `brand_style` | textarea / file | — | Palette, mood, references |
| `scene_briefs` | textarea | — | Iris proposes scenes if empty |
| `lifestyle_count` | number | — | 0–4, default 3 |
| `must_show` | textarea | — | e.g. "leak-proof lid" |

**Questions it may ask:** scene-concept approval before generation (standalone only; can be skipped).

### W
1. **Ingest.** From Shopify media (snapshot URLs) or `/in`. Read dimensions and color profile with libvips/pyvips and convert to sRGB.
2. **Audit.** Bedrock (Grok 4.7) vision, per image:
   - type;
   - background, lighting, sharpness;
   - product fill;
   - overlays and watermarks;
   - duplicates (**imagehash**).
3. **Gap analysis.** Against the category's best-practice set: hero on white, 3+ angles, scale/in-hand, detail, lifestyle, `must_show` proof, packaging. Uses Priya's proof points and Rafael's benchmarks.
4. **Studio shot.** **Gemini Nano Banana 2.1** re-shoots the hero photo as an e-commerce studio image: the product alone on pure white (#FFFFFF) with a soft contact shadow, 2K square. The prompt requires the product to stay unchanged (shape, colours, material, logos, markings).
5. **Lifestyle scenes.** **Gemini Nano Banana 2.1** places the product from the hero photo into each scene brief (photorealistic, realistic scale, matching light and shadows; no people, no added text or logos).
6. **Fidelity check.** **Grok 4.7 vision** compares every render with the original photo and scores product fidelity 0–1 with a list of differences. Renders below 0.90 are dropped. White-background channel exports are cropped from a studio shot that passed.
7. **Channel variants** (Pillow):

   | Channel | Spec |
   |---|---|
   | Store product page | 2048×2048 |
   | Google Shopping | White or neutral background, no promotional overlays, ≥1500 px |
   | Google Ads / PMax | 1200×1200 square and 1200×628 landscape |
   | Amazon main | Pure white background, ≥85% fill, ≥1600 px |
   | Social | 1080×1080 |
8. **Export stats.** Border brightness and product fill are measured on every export for the channel checks.
9. **Alt text.** Bedrock (Grok 4.7) vision, ≤125 characters, includes the product name.
10. **Order and variant mapping.** Hero first, then the image answering the top objection, then angles, lifestyle, detail. Images are mapped to color variants.

### O
- `image_pack.zip` (by channel)
- `visual_audit.json`
- `alt_text.json`
- `order.json`
- `fidelity.json`
- **changeset:**
  - media add: `stagedUploadsCreate` → upload → `fileCreate` → `productUpdate` media
  - reorder: `productReorderMedia`
  - alt text: `fileUpdate`
- **Scopes:** `write_products`, `write_files`
- Google Ads image assets feed Sasha.

### U
- **Input:**
  - snapshot media
  - Priya's proof points
  - Rafael's benchmarks
  - Clara's facts
  - brand style
- **Consumers:** Sasha, Leo, Yuki (alt-text translation), Quinn.
- **Standalone compatibility:** a PASS Iris manifest for the same product snapshot hash, recorded in the Worker's journal, can be reused by Nora instead of re-hiring Iris.

### K
- Expose `iris`.
- Ray fan-out per image.
- Lock: scene approval (standalone only).
- `runtime_env.pip`: `pyvips`, `imagehash`, `scikit-image`, `playwright`, `boto3`, `httpx`.

### X
| Step | Service |
|---|---|
| 2, 9 | Amazon Bedrock (Grok 4.7 vision) |
| 4, 5 | Gemini API: Nano Banana 2.1 (Interactions API) |
| 6 | Amazon Bedrock: Grok 4.7 vision (fidelity) |
| 7, 8 | Pillow (local) |
| Publish | Shopify `stagedUploadsCreate`, `fileCreate`, `productUpdate`, `productReorderMedia`, `fileUpdate` |

### V — `iris@5` · pass ≥ 40
The bundle carries each kept render's fidelity score (Grok vision against the original photo), plus every export's size, border brightness and fill.

| Check | Method | Points |
|---|---|---|
| Product fidelity | At least one render kept, and every kept render's fidelity ≥0.90 | 25 |
| Channel rules | Google Shopping variant: light border (≥240), no overlay flag. Amazon main: white background, ≥80% fill. Sizes meet minimums. | 25 |
| Alt text | Non-empty, ≤140 characters, names the product | 15 |
| Hero | ≥1000 px, light/neutral background | 15 |
| Gap closure | ≥ half of the missing shot types added | 10 |
| Judge | Realism and brand fit | 5 |
| Ownership | Media and alt text only | 5 |

---

## 7. Oskar — Catalog, Collections & Shopping Feed Specialist

### L
| Field | Value |
|---|---|
| `caption` | Catalog, Collections & Shopping Feed Specialist |
| `description` | "Makes your products easy to find, in your store and in shopping feeds like Google Shopping. Oskar sets the right product category and attributes, cleans up product type and tags, places products in the right collections (and writes the collection page SEO), links related and complementary products, and fixes Google Merchant Center issues so your products don't get disapproved. Works with Shopify stores today." |
| `tags` | product catalog, google shopping, merchant center, product feed, product taxonomy, collections, ecommerce SEO, related products |
| Unit · price | per product · **1.50** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| connected product(s) | — | ✅ | Requires the store connection |
| Google Merchant Center connection | — | — | Optional; enables issue diagnosis |
| `attributes` | textarea | — | Material, color, size, age group, gender, GTIN/MPN/brand |
| `collection_strategy` | option | — | "use existing only" or "create where useful" |

### W
1. **Category.**
   - Map to the **Shopify Standard Product Taxonomy**: Admin API taxonomy search, ranked by Bedrock (Grok 4.7).
   - Recommend category attribute values (in `catalog_changes.json`) for the merchant to set.
   - Normalize `productType` and `vendor`.
2. **Tags.** Taxonomy and merchandising tags from Kai's clusters and the store's existing tag vocabulary.
3. **Identifiers.**
   - Validate GTINs (GS1 check digit), MPN and brand.
   - Barcode fixes are delivered as a Shopify bulk-import CSV, because variants are not written.
4. **Collections.**
   - Score existing collections for fit. Add the product with `collectionAddProducts`, or confirm a smart rule already includes it.
   - Where useful, create a category collection (`collectionCreate`: title, `descriptionHtml`, SEO title and description, rule set) targeting a Kai cluster.
5. **Related and complementary products.**
   - Chosen by attribute similarity, complementarity (Grok 4.7) and stock status.
   - Written to the Search & Discovery **related** and **complementary** product metafields.
6. **Feed health.** Check Google's required feed fields (ID, title, Google product category, brand, GTIN or MPN, condition) on the product's data; Shopify's Google & YouTube channel syncs the fixes.
7. **Export.** A Google supplemental feed CSV.

### O
- `catalog_changes.json`
- `collections_plan.md`
- `feed_report.json`
- `google_supplemental.csv`
- `barcode_fixes.csv`
- **changeset:**
  - `category`
  - `productType`, `vendor`
  - taxonomy `tags`
  - collection membership, new collection
  - related/complementary metafields
- **Scopes:** `read_products`, `write_products`

### U
- **Input:** Kai's clusters and the snapshot.
- **Consumers:**
  - Quinn (catalog score)
  - Sasha (Shopping/PMax structure)
  - Leo (collection links)

### K
- Expose `oskar`, single flow.
- Lock: Merchant Center connection (optional; can be skipped).

### X
| Service | Use |
|---|---|
| Shopify Admin GraphQL (Gateway) | Taxonomy, product, collections, metafields |
| Google Merchant API | Product statuses and issues (OAuth `content`) |
| Amazon Bedrock | Grok 4.7 |
| GS1 check digit | Local |

### V — `oskar@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Category validity | The chosen category is one of the taxonomy search results | 30 |
| Collections | New collection's SEO fields fit limits; target collection exists | 20 |
| Related links | Every referenced ID is a store product ID | 15 |
| Tag hygiene | No duplicate tag variants; ≤20 tags | 15 |
| Export schema | Google required fields present | 15 |
| Judge | Category and collection fit | 5 |
| Ownership | Oskar's fields only | **hard gate** |

---

## 8. Yuki — Localization & Transcreation Specialist

### L
| Field | Value |
|---|---|
| `caption` | Localization & Transcreation Specialist |
| `description` | "Sell in new countries with listings that read as if they were written there. Yuki adapts your title, description, SEO fields, alt text and FAQs to each market. She uses the local search terms people actually type, keeps your brand terms intact, converts units, and publishes straight into your store's translations." |
| `tags` | translation, localization, transcreation, store translation, multilingual SEO, international ecommerce, german, japanese, french, spanish |
| Unit · price | per product per locale · **1.00** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| connected product **or** `source_copy` | — / textarea | ✅ | |
| `target_locales` | option (multi) | ✅ | Each locale = one unit |
| `locked_terms` | textarea | — | Kept verbatim |
| `local_keywords` | textarea | — | Otherwise Yuki runs a local keyword pass |
| `market_notes` | textarea | — | Tone, formality, regulations |

**Questions it may ask:** enabling a target locale that isn't enabled in the store.

### W
1. **Source content.**
   - Gateway `translatableResource`: `title`, `body_html`, `meta_title`, `meta_description` and `handle`, with their `translatableContentDigest`.
   - When Clara is in the plan, her verified new copy replaces those fields: Yuki translates what will be published.
   - Media alt text and the FAQ metafield are included.
2. **Locales.** Enabled shop locales (`read_locales`).
3. **Local keywords.** `local_keywords` when given; otherwise Google autocomplete via Serper `/autocomplete` in the target market and language (`gl`/`hl`), seeded with source terms translated by Grok 4.7.
4. **Locked terms.** Brand and product terms that must stay verbatim.
5. **Transcreation.** Bedrock (Grok 4.7), straight from the source:
   - native fluency;
   - local keywords in the title, meta and opening;
   - units and date formats;
   - HTML preserved.
6. **Back-translation.** Grok 4.7 translates back to the source language and flags drift.
7. **Changeset.** `translationsRegister` entries (`locale`, `key`, `value`, `translatableContentDigest`; optional `marketId`).
   An entry made from Clara's copy carries `source` (that copy) instead of a digest: Shopify only digests the copy once it is live, so the Gateway reads the digest at publish, after Clara's update, and only if the live text is that source. Nora leaves the translation out if Clara's update is not published.

### O
- `translations_<locale>.json`
- `local_keywords_<locale>.csv`
- `qa_report.md`
- **changeset:** translations
- **Scopes:** `write_translations`, `read_locales`

### U
- **Input:** final copy, FAQ and alt text from Clara, Leo and Iris; Kai's source keywords.
- **Consumers:** Ruth, Quinn.

### K
- Expose `yuki`.
- One run per locale, in parallel.

### X
| Service | Use |
|---|---|
| Shopify Admin GraphQL | `translatableResource`, `shopLocales`, `translationsRegister` |
| Serper.dev | `POST /autocomplete` (local keywords) |
| Amazon Bedrock | Grok 4.7 |

### V — `yuki@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Digest freshness | Digests match the current source (a stale key is accepted if the source text is unchanged) | 20 |
| Locked terms | ≥90% of occurrences preserved | 20 |
| Lengths | Title ≤75, meta title ≤65, meta description ≤165 (CJK-aware) | 15 |
| Local keyword | Primary local keyword (or variant) in title, meta or first paragraph | 15 |
| Completeness | ≥95% of segments in the target language; HTML balanced | 15 |
| Local keywords are real | Each of the top 3 local keywords comes back from Serper autocomplete in that market; ≥2 of 3 | 10 |
| Judge | Meaning preserved | 5 |

---

## 9. Leo — Content & Email Marketer

### L
| Field | Value |
|---|---|
| `caption` | Content & Email Marketer |
| `description` | "Content that answers buyers' questions and brings them back. Leo writes a product FAQ that tackles real objections, a comparison table against competitors, an SEO blog article, a launch email sequence (ready-to-import HTML and plain-text versions), automation flow blueprints, and a social post pack with tracked links." |
| `tags` | content marketing, FAQ, blog writing, email marketing, product launch email, social media posts, comparison table, SEO content |
| Unit · price | per product or campaign · **2.00** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| connected product **or** `product_facts` | — | ✅ | |
| `deliverables` | option (multi) | ✅ | faq, comparison, blog, email, social |
| `audience`, `brand_voice` | textarea | — | |
| `launch_date` | date | — | |
| `offer` | textarea | — | From Marcus in the flow |
| `competitors` | textarea | — | From Rafael in the flow |
| `email_platform` | option | — | Generic, Shopify Email, Mailchimp (formats the HTML merge tags) |
| `blog_id` | option | only for blog publishing | Leo lists the shop's blogs |
| `social_platforms` | option (multi) | — | Instagram, TikTok, X, LinkedIn, Facebook |

### W
1. **Research.**
   - Serper `/search` for the head term: People Also Ask questions and the top result titles.
   - Kai's clusters; Priya's complaints and wishes.
2. **FAQ.**
   - 6–10 fact-grounded Q&As in the product metafield `custom.faq` (JSON).
   - Questions target real search queries: People Also Ask and Kai's question keywords.
3. **Comparison table.** Merchant vs 2–4 competitors, on attributes from Rafael's matrix only. Stored in the metafield `custom.comparison`.
4. **Blog article.**
   - 1,200–1,800 words, H2/H3 informed by the top result titles and People Also Ask.
   - Internal links to the product and its collection, an Iris image, and UTM links.
   - Created **unpublished** (`articleCreate`, `isPublished: false`).
5. **Email.**
   - A launch sequence (announcement, plus a reminder or offer), as responsive HTML and plain text, with merge tags for the chosen platform.
   - Flow blueprints (welcome, browse abandonment, cart abandonment) as step-by-step specs with copy.
   - SMS copy.
6. **Social pack.** 5–10 posts per platform: copy, hashtags, Iris image references and UTM links, as CSV.
7. **UTM builder** (deterministic): `utm_source`, `utm_medium`, `utm_campaign=uplift-<task>`, `utm_content`.

### O
- `faq.json`
- `comparison.json`
- `blog_article.html`
- `emails/` (HTML and text)
- `flow_blueprints.md`
- `social_pack.csv`
- **changeset:** `custom.faq`, `custom.comparison` (`metafieldsSet`); blog article (unpublished)
- **Scopes:** `write_products`, `write_content`

### U
- **Input:**
  - Clara's copy and facts
  - Priya's findings
  - Rafael's matrix
  - Kai's clusters
  - Marcus's offer
  - Iris's images
- **Consumers:** Yuki, Ruth, Quinn.

### K
- Expose `leo`.
- Each deliverable is a parallel Ray task.
- Lock: `blog_id` (standalone only).

### X
| Service | Use |
|---|---|
| Serper.dev | `POST /search` (People Also Ask, result titles) |
| Amazon Bedrock | Grok 4.7 |
| Shopify Admin GraphQL | `metafieldsSet`, `articleCreate`, blogs |

### V — `leo@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| FAQ grounding | ≥80% of answers cite a fact ID | 20 |
| Search-query coverage | ≥3 FAQ questions match People Also Ask or Kai's question keywords | 10 |
| Comparison sourcing | Competitor cells carry evidence URLs from Rafael's matrix | 15 |
| Article | Word count within ±20% of target; internal links on the shop domain; unpublished | 20 |
| Email | Subject ≤70 chars; unsubscribe placeholder present; plain-text version present | 15 |
| UTM consistency | ≥90% of links carry the campaign UTMs | 10 |
| Judge | Tone and voice | 5 |
| Ownership | Leo's fields only | 5 |

---

## 10. Sasha — Paid Ads Strategist

### L
| Field | Value |
|---|---|
| `caption` | Paid Ads Strategist |
| `description` | "Ad campaigns that can't lose money by design. Sasha builds search and shopping campaigns around your break-even numbers: bids and budgets capped by your margin, keyword and negative lists, ad copy and image assets, and tracking. You get a ready-to-import Google Ads Editor file with every campaign paused, ready for you to review and switch on. Supports Google Ads (Search and Shopping/Performance Max) today." |
| `tags` | google ads, performance max, shopping ads, search ads, PPC, ROAS, ad copy, campaign planning, ecommerce advertising |
| Unit · price | per product or campaign · **1.50** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| connected product **or** `product_facts` + `price` | — | ✅ | |
| `campaign_types` | option (multi) | ✅ | Search, Shopping / Performance Max |
| `budget_cap` | number + period | ✅ | |
| `goal` | option | ✅ | Target ROAS or target CPA |
| `margin_pct` or `unit_cost` | number | ✅ | From Marcus in the flow |
| `conversion_rate` | number | — | Otherwise a flagged category default |
| `markets` | option (multi) | ✅ | |

### W
1. **Unit economics** (deterministic).
   - Break-even CPA = price × margin.
   - Break-even ROAS = 1 / margin.
   - Max CPC = target CPA × CVR.
   - CVR comes from the input, or a flagged category default.
2. **Keywords.**
   - Kai's map (`ads_exact`, `ads_phrase`, `title` and `description` roles), or Google autocomplete via Serper `/autocomplete` for the product.
   - Every keyword is bid at the max CPC from the unit economics, which is capped by break-even.
3. **Negatives.** Kai's negatives, competitor brand terms (unless conquesting) and irrelevant intents.
4. **Structure.**
   - Search ad groups per cluster.
   - A Shopping / Performance Max asset group filtered to the product.
   - Budgets split by expected return, with the total ≤ cap.
5. **Ad copy** (Bedrock Grok 4.7).
   - RSA headlines ≤30 characters (×15) and descriptions ≤90 (×4).
   - PMax long headline ≤90.
   - Angles come from Priya; claims only from verified facts.
6. **Assets.** Iris's Google Ads images (1200×1200, 1200×628).
7. **Tracking.** UTMs and a conversion-tracking checklist.
8. **Deliver.**
   - A Google Ads Editor CSV with every campaign **Paused**, for the merchant to import, review and enable.

### O
- `ads_plan.md`
- `unit_economics.json`
- `google_ads_editor.csv`
- `ad_copy.json`
- `tracking_checklist.md`
- **changeset (optional):** paused Google Ads campaigns
- **Scope:** Google `adwords`. Live pushes need a Google Ads developer token (Basic access).

### U
- **Input:** Marcus, Kai, Clara, Iris, Priya, Rafael.
- **Consumers:** Ruth, Quinn.

### K
- Expose `sasha`, single flow.
- Lock: budget confirmation (standalone, with a connected account).

### X
| Service | Use |
|---|---|
| Serper.dev | `POST /autocomplete` (keywords when Kai did not run) |
| Amazon Bedrock | Grok 4.7 |

### V — `sasha@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Spend cap | Total budgets over the period ≤ cap | 25 |
| Bid safety | Every max CPC / tCPA ≤ break-even (recomputed) | 25 |
| Negatives sanity | No negative blocks a positive keyword (match-type logic) | 15 |
| Limits | Character limits | 10 |
| Final URLs | On the shop domain, with UTMs | 10 |
| Paused state | Every campaign in the import file is Paused | 10 |
| Judge | Copy relevance | 5 |

---

## 11. Ruth — Claims & Compliance Reviewer

### L
| Field | Value |
|---|---|
| `caption` | Claims & Compliance Reviewer |
| `description` | "Catches risky claims before your customers, competitors or ad platforms do. Ruth checks product copy, images, emails and ads against consumer-protection rules (US FTC, EU), green-claims rules, health and cosmetic claim limits, competitor trademarks, and ad-platform and shopping-feed policies (Google Ads and Merchant Center today). Every finding comes with its rule, severity, location and a safe rewrite." |
| `tags` | compliance, advertising claims, FTC, green claims, trademark, ad policy, merchant center policy, product claims review, legal review |
| Unit · price | per product or asset bundle · **0.25** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| `assets` | textarea / file / url | ✅ | Copy, HTML, images (OCR), email HTML, ad CSVs, or a product URL |
| `markets` | option (multi) | ✅ | US, EU, UK… (selects rule packs) |
| `category` | option | ✅ | General, supplements, cosmetics, food contact, kids, electronics… |
| `own_trademarks`, `competitor_brands` | textarea | — | |
| `substantiation` | file | — | Certificates and test reports that unlock claims |

### W
1. **Extract text.** From copy, HTML, email and ads; image text read by Grok 4.7 vision.
2. **Rule engine.** `uplift-rules`: deterministic, versioned, open source, with its hash recorded in the verifier profile. Rule packs:
   - superlatives and comparatives;
   - environmental claims (FTC Green Guides; EU rules on generic environmental claims);
   - health and medical;
   - cosmetics;
   - pricing (reference prices, fake urgency);
   - children's products;
   - trademarks (competitor marks beyond nominative use; ®/™ misuse);
   - platform policies (Google Ads; Merchant Center, including no promotional overlays on Shopping images).
3. **Substantiation matching.** A claim backed by a supplied certificate is downgraded to "substantiated".
4. **Rewrites.** Bedrock (Grok 4.7) proposes compliant alternatives. The engine re-checks each one.
5. **Verdict.** pass / pass-with-fixes / blocked (any unresolved high-severity finding).

### O
- `compliance_report.md` / `.json` (rule ID, pack version, severity, location, excerpt, rewrite)
- `blocked: bool`
- **changeset:** none.
  - In the flow, Nora returns the rewrites to the owning agents.
  - Standalone, the rewrites are delivered as a suggested diff.

### U
- **Input:** every public-facing artifact in the merged changeset, plus the brand lists from Priya and Rafael.
- **If blocked:** Nora sends targeted rewrites back to the owner. If that would exceed the approved ceiling, she asks the merchant first.

### K
- Expose `ruth`, single flow.
- The rule engine is vendored and pinned.

### X
| Service | Use |
|---|---|
| Amazon Bedrock | Grok 4.7, rewrites only (never verdicts) |
| `uplift-rules` | Local deterministic engine |

### V — `ruth@5` · pass ≥ 40
CRE runs the **same rule engine** (a JS port generated from the same rule YAML) on the bundle's extracted text.

| Check | Method | Points |
|---|---|---|
| High-severity coverage | Every high-severity hit CRE finds is in Ruth's report | 40 |
| Overall agreement | ≥80% overlap between hit sets (rule ID and location) | 30 |
| Rewrites | ≥90% of rewrites pass the engine | 25 |
| Judge | Rewrite quality | 5 |

---

## 12. Quinn — Store Auditor & Performance Analyst

### L
| Field | Value |
|---|---|
| `caption` | Store Auditor & Performance Analyst |
| `description` | "Finds out why a product isn't ranking or selling. Quinn checks where your product ranks today, on Google and in your store's own search, and audits its page for search, copy, images, trust content, catalog and feed data and compliance, giving a 0–100 score with prioritized fixes. Connect your store and she uses your sales data to diagnose whether you have a traffic, conversion or basket-size problem. After changes go live, she produces the before/after report." |
| `tags` | ecommerce audit, product page audit, SEO audit, product ranking, search visibility, ecommerce analytics, listing score |
| Unit · price | per product per report · **0.50** |

### S
| id | type | Req. | Notes |
|---|---|---|---|
| `product_url` **or** connected product | url | ✅ | Public URL audits work without any connection |
| `mode` | option | ✅ | `audit`, `diagnose` (uses store sales), `before_after` |
| Shopify connection | — | recommended | ShopifyQL sales (`read_reports`), data checks |
| `date_range` | date range | `diagnose` | Default: last 28 days |
| `competitor_urls` | textarea | — | Benchmarks |
| `store_queries` | textarea | — | Store search phrases to track; default: the keyword list |

### W
1. **Page capture.** Firecrawl `/scrape` (rendered HTML, markdown), plus Gateway product data when connected.
2. **Ranking snapshot.** Serper `/search` (top 20) for the product's top 5 keywords (Kai's map if present, otherwise generated with Grok 4.7). Records the store domain's current Google position and who outranks it.
3. **Store search rank.** The product's position in the store's own relevance-ranked product search (Shopify Admin `products(query:, sortKey: RELEVANCE)` through the Gateway read API) for the tracked phrases: `store_queries`, or the keyword list.
4. **Content and visuals.**
   - Title/meta and keyword placement (Kai's map if present).
   - Copy depth.
   - Image count, size and alt text.
   - Video.
5. **Trust content.**
   - Shipping and returns information present.
   - FAQ and comparison table present.
   - Review signals present.
   - Specs complete; guarantee stated.
6. **Catalog and feed.** Category, attributes, GTIN.
7. **Compliance quick scan.** `uplift-rules` superlative and trademark packs.
8. **Score.** Listing Score 0–100, with the weights in product spec §7.
9. **Page speed** (informational, not scored). **PageSpeed Insights API v5** (mobile): LCP, CLS, INP and top opportunities, listed in the report.
10. **Analytics** (`diagnose`).
   - ShopifyQL: `FROM sales SHOW total_sales, orders GROUP BY product_title SINCE -28d`.
   - Funnel diagnosis (Bedrock, from sales, rankings and the score sections):

     | Weak metric | Problem | Specialists |
     |---|---|---|
     | Low sessions | Traffic | Kai, Sasha, Oskar |
     | Low add-to-cart rate | Page | Clara, Iris, Leo |
     | Low checkout rate | Offer or shipping | Marcus |
     | Low AOV | Bundles / related products | Marcus, Oskar |
11. **Fix plan.** Prioritized by impact × effort. Each fix names the Uplift specialist and their price, ready for Nora's quote.
12. **Before/after** (`before_after`). Compares the baseline snapshot and score with the published state, section by section, including Google positions and store search ranks before vs after, listing every change and its owner.

### O
- `audit_report.md` / `.json` (score breakdown, ranking snapshot, store search ranks, findings, diagnosis, page-speed notes, before/after in that mode)
- `fix_plan.json`
- **Store writes:** none

### U
- **Baseline** (Phase 0), **projection** on the merged changeset, and the **after-report** (Phase 7).
- The fix plan feeds Nora's routing for "why isn't this selling?" requests.

### K
- Expose `quinn`.
- Capture, page speed and analytics run as parallel Ray tasks.
- No locks: a missing connection is reported as `not_measured`.

### X
| Service | Use |
|---|---|
| Firecrawl | Page render |
| Google PageSpeed Insights API v5 | Speed notes (informational) |
| Shopify Admin GraphQL | `shopifyqlQuery` (`read_reports`), product data, `products(query:, sortKey: RELEVANCE)` (store search rank) |
| Serper.dev | `POST /search` (ranking snapshot) |
| Amazon Bedrock | Grok 4.7 (keyword generation, report writing) |
| `uplift-rules` | Compliance quick scan |

### V — `quinn@5` · pass ≥ 40
| Check | Method | Points |
|---|---|---|
| Score agreement | CRE recomputes the deterministic sections from the bundle plus a fresh gateway snapshot; Quinn's total within ±3 points | 50 |
| Sales numbers | A ShopifyQL result is present whenever the sales query ran | 20 |
| Findings reproduced | Google position re-checked for one keyword via Serper search (within ±5 positions); checklist findings from a page re-fetch, ≥80% agree | 20 |
| Fix-plan mapping | Each fix names a valid specialist and price | 5 |
| Judge | Diagnosis consistent with the numbers | 5 |

---

## Appendix A — External service matrix

| Service | Agents | Purpose | Auth / secret holder |
|---|---|---|---|
| **Amazon Bedrock**: Grok 4.7 | All agents, Worker (Nora, chat), CRE judge | All LLM inference, vision, translation, OCR, keyword clustering | Bedrock API key: Kodosumi and Worker env, CRE Vault (judge) |
| **Gemini API** (Nano Banana 2.1) | Iris | Studio shots and lifestyle scenes | Kodosumi env |
| **Serper.dev** (search, shopping, autocomplete) | Kai, Rafael, Priya, Marcus, Clara, Yuki, Leo, Sasha, Quinn | Google results, Shopping offers, autocomplete | API key (`X-API-KEY`): `SERPER_API_KEY` in Kodosumi env, `serperApiKey` in CRE Vault |
| **Bright Data** (Amazon scrapers) | Priya | Amazon reviews | Kodosumi env |
| **Firecrawl** | Kai, Rafael, Priya, Clara, Quinn | Rendering, scraping, extraction (incl. Trustpilot pages) | Kodosumi env |
| **Tavily Search API** | Priya | Reddit discussions | Kodosumi env |
| **Nager.Date** | Marcus | Public holidays | None |
| **Google PageSpeed Insights API** | Quinn | Speed notes | Kodosumi env |
| **Shopify Admin GraphQL** | All (reads); Clara, Iris, Oskar, Yuki, Leo, Marcus (writes via CRE) | Store data | Merchant tokens: **Connection Gateway only** |
| **Sokosumi Core API** | Worker, Nora, CRE | Tasks, approvals, payments, files, receipts | 13 coworker keys (Worker and CRE Vault) |
| **Masumi Payment Service** | Kodosumi, Worker | Payments (uses Blockfrost internally) | Scoped `ReadAndPay` token |
| **Chainlink CRE** | — | `uplift-clearing` (`verify`, `publish`) | CRE account; HTTP-trigger authorized key (Worker) |
| **Amazon S3** | All | Artifact store | IAM role |
| **AWS KMS** | Gateway | Token envelope encryption | IAM credentials |
| **PostgreSQL** | Worker, Gateway, MPS | Journals, encrypted tokens, payments | — |

## Appendix B — Standalone vs Uplift-mode behavior

| Agent | Standalone needs store connection? | Can ask the merchant | Writes in standalone mode | In Uplift mode, skips |
|---|---|---|---|---|
| Kai | No | Market | None | — |
| Rafael | No | Competitor confirmation | None | Own query generation (uses Kai) |
| Priya | No | Competitor confirmation | None | Discovery (uses Rafael) |
| Marcus | Recommended (costs) | Unit cost | Discount codes, after approval | Light market scan |
| Clara | Optional (paste copy) | Missing facts | Copy fields, after approval | Mini keyword pass |
| Iris | Optional (upload images) | Scene approval | Media and alt text, after approval | Scene approval |
| Oskar | **Yes** | Merchant Center connection | Catalog fields, after approval | — |
| Yuki | Optional (paste copy) | Enable locale | Translations, after approval | Local keyword pass if Kai covered the locale |
| Leo | Optional | Blog choice | Metafields and article, after approval | — |
| Sasha | Optional | Budget confirmation | Paused Google Ads campaigns, after approval | — |
| Ruth | No | — | None (suggested diff) | — |
| Quinn | No for `audit`; yes for `diagnose` | — | None | — |

**Standalone writes** follow the same path as a Nora flow:
1. The coworker posts the change set (summary, `change_hash`, attached `changes.html`) and sets `APPROVAL_REQUIRED`.
2. The merchant moves the Task to Ready, or replies "approve".
3. The coworker's worker calls CRE `publish`.

**Field-level open items.** Confirm against the live Admin API before Oskar and Clara publish:
- the Search & Discovery related/complementary metafield namespace and keys;
- the handle-redirect option on `productUpdate`.
