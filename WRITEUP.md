# Uplift: a verified AI growth team for Shopify, settled on Cardano

## The problem

A small merchant who lists a product on Shopify needs keyword research, competitor pricing, product copy, photos,
catalog data, an FAQ, compliant claims and a Google Ads setup before the listing can be found and advertised well.
Agencies charge a monthly retainer for this, which most small merchants can't afford. AI tools are cheap, but they
can invent product claims, overwrite working copy, and charge whether the result is good or not. The merchant has no
record of what was changed and no way to pay only for work that turned out to be correct.

## The solution

Uplift is a team of 13 AI agents listed as coworkers on Sokosumi. A merchant hires one specialist for a single job, or
hires **Nora**, the lead agent, who plans the job, hires the specialists it needs, and charges once for the work that
passed verification.

**Nora (lead).** Turns a request such as "fully optimize my listing" into a priced plan, runs the specialists in the
right order, merges their changes and bills only for the specialists whose work passed.

**The twelve specialists:**

| Coworker | What it does | Price |
|---|---|---|
| **Quinn**, Store Auditor | Scores the listing out of 100, checks where it ranks, and maps every gap to the specialist who can fix it | 0.5 tUSDM |
| **Kai**, Search Demand Analyst | Finds the phrases shoppers actually search for on Google, with demand and intent | 1.25 tUSDM |
| **Rafael**, Competitor & Market Analyst | Identifies the real competitors, their prices and claims, and where the product can win | 1.25 tUSDM |
| **Priya**, Review & Sentiment Analyst | Reads competitors' reviews and Reddit threads to find what buyers complain about | 1.5 tUSDM |
| **Marcus**, Pricing & Promotions | Positions the price and schedules discount codes that never go below the margin floor | 1.25 tUSDM |
| **Clara**, Product Page Copywriter | Rewrites the title, description and SEO fields using only facts the merchant gave | 2.0 tUSDM |
| **Iris**, Product Visual Designer | Turns one phone photo into a studio shot and lifestyle scenes that still match the real product | 2.5 tUSDM |
| **Oskar**, Catalog & Shopping Feed | Sets the product category, tags and collections, and checks Google Shopping feed readiness | 1.5 tUSDM |
| **Leo**, Content & Email Marketer | Writes the FAQ, a comparison table, a blog article, launch emails and social posts | 2.0 tUSDM |
| **Sasha**, Paid Ads Strategist | Builds Google Ads campaigns from break-even economics, delivered paused | 1.5 tUSDM |
| **Yuki**, Localization | Translates and adapts the listing for another language, with local keywords | 1.0 tUSDM / locale |
| **Ruth**, Claims & Compliance | Flags claims that could get the store fined or delisted and proposes safe rewrites | 0.25 tUSDM |

Prices are in tUSDM, the test USD stablecoin used by the Masumi escrow. Sokosumi charges 100 workspace credits per
tUSDM, so a full Nora run of 16 tUSDM uses 1,600 credits.

**Each specialist is useful on its own.** A merchant can hire Kai only for keyword research, Ruth only for a compliance
check before running ads, or Quinn only for an audit. Each one has its own inputs, deliverables, price and
verification rules, so it does not depend on Nora to be worth hiring.

**Why Masumi.** Every paid Task is a Masumi escrow on Cardano:
- the merchant's payment is locked in a smart contract before the work is delivered;
- the agent writes the hash of its verified deliverable on-chain when it finishes;
- if no result is submitted before the deadline (for example, the merchant declined the changes), the escrow returns
  the money to the buyer on-chain;
- the buyer can dispute a result during a fixed window before the funds are released to the agent;
- every agent has an on-chain identity (a Masumi registry NFT), so the buyer knows exactly which agent it is paying.

**Why Kodosumi.** The twelve specialists run as Kodosumi flows on Ray. Kodosumi gives each agent a standard API that
Masumi can register (MIP-003), runs many agent executions in parallel across Ray workers, tracks the status of every
execution, and lets a stuck run be stopped and restarted. Adding capacity means adding Ray workers, not rewriting the
agents.

## Proof: a real Shopify listing, optimized end to end by Nora

In the Uplift Shopify development store, we created a new listing, "Dripper D-02" (one phone photo, a one-line
description), next to 25 competing coffee listings. Nora ran the full team on it from a Sokosumi Task.

- **Store search rank:** before the run the product appeared for **0 of 6** tracked phrases. After the run it was
  **#1 for 5 of 6**. Measured with the Shopify Admin API product search, sorted by relevance, at the start and end of
  the run.
- **Listing score:** 20.1 → 77.3 out of 100 (Quinn).
- **Verification:** 12 of 12 specialist results passed Chainlink CRE; 14 changes were published to the store.
- **Cost and time:** 16 tUSDM (1,600 credits), about 16 minutes.

| Proof | Link |
|---|---|
| Full run record: brief, every event, receipt, verdicts and deliverables | [runs/17-nora-dripper-full-team](https://github.com/SamFelix03/Uplift/blob/main/runs/17-nora-dripper-full-team/README.md) |
| Rank before and after, with the Shopify endpoint used | [RANKS.md](https://github.com/SamFelix03/Uplift/blob/main/runs/17-nora-dripper-full-team/RANKS.md) |
| Every step of the run (661 events: agent, service, timing) | [trace.json](https://github.com/SamFelix03/Uplift/blob/main/runs/17-nora-dripper-full-team/trace.json) |
| Escrow locked on Cardano (16 tUSDM, FundsLocked) | [`a3c1b746…`](https://preprod.cexplorer.io/tx/a3c1b746a4b66af13a9431026d04609b53a2a2606b9c0a1c8ec5d87dd9a309f5) |
| Verified result hash written on-chain (ResultSubmitted) | [`01dfd76d…`](https://preprod.cexplorer.io/tx/01dfd76d3c13780e3d402d54e17c27204d02978b7e9344fa8be2968a07ed2ab1) |
| This run's payout to Uplift | Unlocks at 00:55 UTC on 2026-10-08 (12 h after the payment request), then collected automatically |
| Payouts already made to Uplift: 36 escrows, 47 tUSDM, in 20 Cardano transactions | [Payout list](https://github.com/SamFelix03/Uplift/blob/main/README.md#3-payouts-to-uplifts-selling-wallet) · example [`e829b5c3…`](https://preprod.cexplorer.io/tx/e829b5c321e754ef4eb1fc4f51d61c682bb36181e0180d88cc4d52088cfa8865) (4 escrows, 7 tUSDM) |
| Uplift's selling wallet (receives the payouts) | [`addr_test1qrsepqrq…6hgrv`](https://preprod.cexplorer.io/address/addr_test1qrsepqrqv32h56cr2tva5aa6ehy0nz55r908zq7t0ag9s08lg89063dkz5ujz9gjf3d4ghtfxrh0hkwxm4dcds6f3vzqw6hgrv) |
| Masumi escrow contract | [`addr_test1wzs4e6wc…ftgn37w4g`](https://preprod.cexplorer.io/address/addr_test1wzs4e6wc95hkwezlccjw9mdvq0r0rsgx6zk34avptga3ftgn37w4g) |
| The run's Google Ads campaigns, previewed | [Google Ads mock](https://ads-mock-production.up.railway.app/ads/?task=01a11663-e114-73e8-bb4f-db0e5967eee9&t=958178c83aec89ed88744edfc700c991) |

## Technical approach

### How the system fits together

- **Sokosumi** is where the merchant hires a coworker, writes the brief, approves plans and changes, and pays with
  workspace credits.
- The **Uplift Worker** (Python, FastAPI) receives each Task, runs Nora's plan or a single specialist, handles
  payment, and journals every step in Postgres so a restart resumes where it left off.
- The **agents** run on **Kodosumi**. Each one writes its deliverables to S3 under the SHA-256 of their content, and
  returns a manifest whose hash identifies the whole deliverable.
- **Chainlink CRE** (workflow `uplift-clearing`) re-downloads each deliverable, checks its hash, and scores it against
  a role-specific set of checks. It is also the only component allowed to write to the store, and only after the
  merchant approves the exact change set.
- **Masumi** on Cardano holds the payment in escrow and records the verified result hash.
- A **Connection Gateway** holds the store's Shopify OAuth tokens (encrypted with AWS KMS). Agents get read-only
  access; only the CRE workflow has the write key.

### What each coworker uses, and why

Shared by every coworker:
- **Kodosumi (on Ray)**: runs the agent as a flow and exposes it as a Masumi-registrable API.
- **Grok 4.7 on Amazon Bedrock**: reasoning, writing and structured output (JSON that matches a schema).
- **Amazon S3**: stores every deliverable under the SHA-256 of its content, so its hash can be checked later.
- **Chainlink CRE**: re-checks the deliverable's hash and scores it before it can be billed or published.

**Quinn**, Store Auditor
- **Shopify Admin API** (through the Uplift gateway): reads the listing to compute the listing score and checks where
  the product ranks in the store's product search.
- **Serper (Google search)**: finds where the store's page ranks on Google for the main phrases.
- **Google PageSpeed**: measures the mobile speed of the live product page.
- **Grok**: rates how persuasive the copy is and writes the fix plan.

**Kai**, Search Demand Analyst
- **Serper (Google autocomplete, related searches, "People also ask")**: collects the phrases real shoppers type, which
  are the raw material for the keyword map and its demand scores.
- **Grok**: proposes seed terms, detects brand and competitor names (moved to negatives) and clusters keywords by intent.
- **Firecrawl** (when the merchant gives a product URL): reads the current product page for seed terms.

**Rafael**, Competitor & Market Analyst
- **Serper (Google search and Google Shopping)**: finds who ranks and who sells the same kind of product, with prices.
- **Firecrawl**: reads each competitor's product page into structured data (price, claims, features). A second API key
  takes over when the first hits its rate limit.
- **Grok**: removes results that are not real competitors and writes the positioning and gaps.

**Priya**, Review & Sentiment Analyst
- **Serper (Google search)** (when no competitors are given): finds competing product pages, including Amazon
  listings, to collect reviews from.
- **Bright Data**: collects Amazon reviews of competing products.
- **Firecrawl**: reads reviews on competitors' own stores and on Trustpilot.
- **Tavily**: finds and reads Reddit threads about the product category; a quote is kept only if it appears word for
  word on the page.
- **Grok**: codes every review by aspect and sentiment, and builds personas and the win plan.

**Marcus**, Pricing & Promotions
- **Shopify Admin API**: reads the product's price, unit cost and the store's existing discount codes, so new codes
  never collide with old ones.
- **Serper (Google Shopping)** (only when Rafael's price bands are not available): checks current market prices.
- **Nager.Date**: lists public holidays in the market, used to schedule promotions.
- **Grok**: proposes price scenarios and discount codes; any code below the 35% margin floor is dropped.

**Clara**, Product Page Copywriter
- **Grok**: builds the facts ledger, writes three copy variants, scores them with a rubric and checks grammar.
- **Serper (Google autocomplete)** (only when Kai has not run): a quick keyword pass so the copy targets real searches.
- **Firecrawl** (when the merchant gives a product URL instead of a connected store): reads the current page.

**Iris**, Product Visual Designer
- **Gemini Nano Banana 2.1**: renders a white-background studio shot and lifestyle scenes from the merchant's own photo.
- **Grok vision**: audits the existing images and checks that each render still looks like the real product; a render
  that does not match is thrown away.
- **Web download** (Shopify CDN): fetches the merchant's original product photos.

**Oskar**, Catalog & Shopping Feed
- **Shopify Admin API**: reads the Shopify product taxonomy, the store's collections and related products.
- **Grok**: picks the category, cleans tags and chooses which collections the product belongs in.

**Leo**, Content & Email Marketer
- **Serper ("People also ask")**: collects the questions shoppers actually ask, which become the FAQ.
- **Shopify Admin API**: reads store data such as the blog the article is saved to (unpublished).
- **Grok**: writes the FAQ, comparison table, blog article, emails and social posts from verified facts.

**Sasha**, Paid Ads Strategist
- **Grok**: writes the ad headlines and descriptions from Clara's facts and Priya's win plan.
- **Serper (Google autocomplete)** (only when no keywords are given): finds generic phrases to bid on.
- Bids, budgets and break-even cost are computed in code from the store's price and margin, not by the model.

**Yuki**, Localization
- **Grok**: translates, adapts and back-translates the copy to catch meaning drift.
- **Serper (Google autocomplete, local market)**: finds the phrases shoppers use in that language.
- **Shopify Admin API**: reads which languages the store has enabled and the content to translate.

**Ruth**, Claims & Compliance
- **Grok**: decides whether each flagged claim is backed by the facts and writes a safe rewrite; Grok vision reads
  text inside images.
- **Firecrawl and web download** (when the merchant gives URLs): read the pages and images to review.
- The 13 compliance rules run in code (the same rules file Chainlink uses), so the checks are repeatable.

**Nora**, Lead
- **Sokosumi**: receives the Task, posts the plan, the bill and the change approval, and delivers the results.
- **Grok**: maps the request to the specialists it needs.
- **Kodosumi**: launches each specialist's run and tracks its status.
- **Shopify Admin API**: reads the product snapshot the specialists work from.
- **Masumi and Cardano**: creates the payment request and waits for the escrow lock before publishing.
- **Chainlink CRE**: verifies every specialist's result and publishes the approved changes to the store.

### Nora: an example workflow

For "Launch my ceramic coffee dripper" (the run above):

1. **Plan.** Grok maps the request to the specialists it needs and Nora quotes a ceiling (at most 16 tUSDM). The plan
   is hashed and sent to the merchant for approval.
2. **Run.** Specialists start in waves as their inputs become available: Quinn and Kai first; then Rafael and Oskar;
   Priya and Marcus; Clara and Iris; then Leo and Sasha. Each one reads only upstream results that already passed
   Chainlink.
3. **Verify.** Each result is checked by Chainlink CRE as soon as it arrives. A failed result is retried once and is
   never billed.
4. **Merge.** Nora merges the passed change sets, and Ruth removes anything with an unresolved high-severity claim.
5. **Bill.** Nora requests one Masumi payment for the sum of the specialists that passed (Dynamic pricing). Sokosumi
   charges the credits and the tUSDM is locked in escrow.
6. **Publish.** The merchant approves the merged change set (14 changes here). After the escrow lock is confirmed,
   Chainlink CRE writes the changes to Shopify, and Quinn scores the listing again.
7. **Settle.** Nora writes the result hash to the escrow on Cardano and delivers a launch pack and a link to preview
   the Google Ads campaigns.

### Masumi

- **Registry:** each of the 13 agents is an NFT on the Masumi registry (Cardano preprod); its identifier is attached to
  every payment.
- **Own payment node:** Uplift runs its own Masumi Payment Service, which creates the seller terms, watches the escrow,
  submits results and withdraws payouts automatically.
- **Seller terms:** each payment commits to the SHA-256 of the merchant's brief and sets the deadlines: pay by, submit
  result by, unlock, and the end of the dispute window.
- **Pricing:** specialists use fixed prices; Nora uses dynamic pricing, so the escrow holds exactly the sum of the
  specialists that passed.
- **Gating:** nothing is published or delivered until the escrow lock is confirmed on-chain.
- **Refunds and disputes:** declined or failed work gets no result, so the contract refunds the buyer after the
  deadline. A submitted result can be disputed until the dispute window closes.

### Sokosumi

- All 13 agents are listed as Sokosumi coworkers with a description, avatar and price.
- Merchants pay with workspace credits; Sokosumi's buyer node converts them to tUSDM and locks them in the Masumi
  escrow, so the merchant never needs a Cardano wallet.
- Plans and change sets are approved inside the Sokosumi Task, and Chainlink CRE checks that the approval came from the
  Task owner before publishing.

### Kodosumi

- Each specialist is a Kodosumi flow with an input form, exposed as a MIP-003 endpoint that is registered on Masumi.
- Executions run on Ray, so many specialists (and many merchants' Tasks) run in parallel.
- The Worker launches flows through Kodosumi's API, polls their status, and stops and relaunches a run that stalls.

## Deployment, scaling and go-to-market

**Deployment.** Today everything runs on Railway (Worker, Kodosumi, Masumi payment node, gateway, Postgres) against
Sokosumi preprod and Cardano preprod. Going to production means three changes that the code already supports: publish
the Shopify app so any merchant can connect a store, settle in mainnet USDM, and run the CRE workflow on a Chainlink
DON instead of the simulator.

**Scaling.**
- More agent capacity means more Ray workers in the Kodosumi cluster; the agents themselves do not change.
- The Worker keeps its state in Postgres and only one instance runs Tasks at a time, so it can be redeployed safely
  while Tasks are running.
- The Masumi node batches escrow transactions (43 escrows were locked in 16 transactions in our test), which keeps
  on-chain fees low as volume grows.
- The main running cost is the model and data API calls per run, which scale with the number of Tasks.

**Go-to-market.**
- **Start where the buyers are:** the agents are already listed on Sokosumi, and the same Uplift app can be listed on
  the Shopify App Store.
- **Use the audit as the entry point:** a Quinn audit costs 0.5 tUSDM and ends with a fix plan that names which
  specialist to hire for each gap.
- **Price per job, not per month:** a full launch costs about 16 tUSDM, compared with an agency retainer.
- **Work with agencies and freelancers:** they can use Uplift to deliver more listings per client and keep the
  on-chain record as proof of work.

## Conclusion

Sokosumi aims to give businesses marketing agents and services that they can hire and pay for without managing
contracts or wallets. Uplift fits that directly: a set of marketing and e-commerce specialists that can be hired one
at a time or as a team, whose work is verified before it reaches the store, and whose payments are held in Masumi
escrow on Cardano and released only for verified results. It is a working example of the kind of service the
Sokosumi marketplace and the wider Cardano ecosystem are built to support.
