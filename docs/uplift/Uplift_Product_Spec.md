# Uplift — Product Specification (v5)

*A verified multi-agent e-commerce growth and ads optimization team for merchants, listed on Sokosumi. v1 supports Shopify stores and Google's shopping and ads channels.*

| Platform | Role |
|---|---|
| Sokosumi | Distribution, Tasks, credits, approvals |
| Masumi | Identity, escrow, payment |
| Kodosumi | Agent runtime |
| Chainlink CRE | Independent verification and gated publishing |
| Amazon Bedrock | All LLM inference |

*TOKEN2049 Origins Hackathon — Cardano Agentic Commerce track and Chainlink CRE track. Spec date 2026-10-06. Deadline 2026-10-07 23:59.*

The companion document **[Uplift_Agent_Spec_Sheet.md](Uplift_Agent_Spec_Sheet.md)** defines every coworker's inputs, workflow steps, external services, outputs and verification checks.

---

## 1. Product

### 1.1 One-line pitch
Uplift is an AI e-commerce growth and ads optimization team for merchants. **Its goal is to improve the product's ranking** — in organic search, in shopping results and in the store's own search — and to turn that visibility into sales. In one engagement it:
- researches the market;
- rebuilds the product listing and launch assets;
- prepares the ad campaigns;
- publishes everything the merchant approves.

Chainlink scores and checks every piece of work before the merchant pays for it. Nothing in the store or ad account changes until the merchant approves it inside Sokosumi.

### 1.2 Who it is for
- **Primary:** merchants with about 10–2,000 products and teams of 1–20 people who cannot afford an e-commerce or performance-marketing agency retainer (typically €2–10k per month).
- **Secondary:** agencies and freelancers who run many stores and ad accounts and want verified, repeatable deliverables.

### 1.3 Platform support
Uplift's specialists work on the merchant's **product catalog**, **storefront content** and **ad campaigns**. Each platform connects through an adapter in the Uplift Connection Gateway.

| Area | v1 (this release) | Designed for |
|---|---|---|
| Commerce platform | **Shopify**: product, translation, discount, collection and content writes | Additional commerce platforms through new gateway adapters. The agents' inputs and outputs are platform-neutral. |
| Shopping feeds | **Google Merchant Center**, via Shopify's Google & YouTube channel, with required-field checks and a supplemental feed | Merchant API diagnostics, further shopping channels |
| Ads | **Google Ads**: full campaign plan, break-even bidding and a Google Ads Editor import file with every campaign paused | Direct paused pushes and full Google Ads management, then further ad networks |
| Analytics | Shopify sales reports (ShopifyQL) | GA4 and further analytics sources |

All merchant-facing wording, coworker listings and deliverables are platform-neutral. Platform names appear only where a v1 integration is specified.

### 1.4 What the merchant can ask for
| Request | What happens |
|---|---|
| "Launch my new bamboo bottle" | Full launch with all 12 specialists: research, listing, visuals, catalog and shopping feed, translations, content and email copy, ad campaigns, compliance, publishing, before/after report |
| "Rewrite these 3 product pages" | Keywords, competitor reviews, copy, compliance, audit |
| "Why isn't this product selling?" | Audit and analytics diagnosis, competitor intel, competitor reviews, then a prioritized fix plan |
| "Plan our Black Friday promotion" | Demand seasonality, competitor prices, promotion plan with discount codes, email copy, ads plan |
| "Sell this in Germany and Japan" | Localized listings, local keywords, compliance |
| "Get my products into Google Shopping without errors" | Catalog and feed fixes, plus a Merchant Center issue report |
| "Make my product photos convert better" | Image audit, cleanup, lifestyle scenes, channel crops, alt text |
| Hire any single specialist | Each specialist works standalone as a Sokosumi Coworker, with its own inputs and deliverables |

### 1.5 The merchant's journey (everything happens inside Sokosumi)
1. **Ask.** The merchant does one of three things:
   - @mentions **Nora (Uplift Lead)** in Sokosumi chat;
   - assigns Nora a Task;
   - assigns a Task directly to one specialist.
2. **Connect the store (once).** If the work needs store data, the Task moves to *Authentication required* with a link. The merchant signs in to their store platform (Shopify in v1) and approves Uplift's scopes. The ads and analytics connection (Google in v1) is optional and only requested when the work needs it.
3. **Approve the plan and price.** Nora posts the plan as a Task comment: which specialists, in what order, what each delivers and what each costs. The Task moves to *Approval required*. The merchant approves by moving the Task to **Ready** with the status picker, or by replying "approve". Any other reply is a change request.
4. **The work runs.** Specialists deliver in dependency order. Chainlink checks and scores each deliverable. Work that fails the check is refunded automatically and redone once, with the reasons attached.
5. **Review the changes.** Nora posts the final change set as a Task comment: a plain-language before/after summary plus an attached diff file. The Task moves to *Approval required* again, and the merchant approves the same way.
6. **Publish.** Chainlink confirms the approval and the scores, then publishes the approved changes to the store, and creates the ad campaigns in a paused state. It re-reads the store to confirm.
7. **Report.** The merchant gets:
   - a before/after listing score;
   - what each specialist changed;
   - what each step cost;
   - Chainlink's verification result for each step.

   The Task is then completed.

### 1.6 What makes it different
| Property | How |
|---|---|
| **Ranking-first** | Every specialist works toward discoverability: real search demand, competitor gaps, keyword-placed copy, a clean category and feed, localized keywords, search-ready visuals and alt text, and supporting content. The listing score weights discoverability highest. |
| **Verified work** | Chainlink CRE independently re-checks and scores every deliverable. It re-fetches cited sources, recomputes the maths and scores, and runs the compliance rules. Only work that passes gets paid. |
| **Gated execution** | No store change happens without the merchant's approval in Sokosumi and a passing Chainlink result. Agents never hold store credentials. |
| **Modular** | All 12 specialists are full standalone coworkers. Nora combines any subset. |
| **No double charge** | Each Job has one escrow at one fixed price. The approved quote caps spend, and Chainlink refunds any hire outside the quote. |

### 1.7 Scope boundaries (by design)
- **One engagement, one result.** Each request ends with a published change set and a before/after report.
- **Never changes** price, compare-at price, inventory, variants, product status or theme files, and never touches orders or customers. Pricing changes are delivered as recommendations plus discount codes.
- **Ad campaigns** are created **paused**; the merchant switches them on. In v1 the ads channel is Google Ads.
- **Email and social** content is delivered as ready-to-use copy and HTML files.
- No marketplace channels (Amazon, eBay), influencer outreach or review solicitation.

---

## 2. The team

1 lead and 12 specialists. All 13 are Sokosumi **Coworkers**. The 12 specialists, plus Nora's fee terms, are also **Masumi Agents**, so Nora can hire them as escrowed Jobs. Full details are in the [spec sheet](Uplift_Agent_Spec_Sheet.md).

| # | Name | Sokosumi caption (role) | Core deliverable | Unit · fixed price (tUSDM = credits) |
|---|---|---|---|---|
| 0 | **Nora** | Uplift Lead · E-commerce Growth Manager | Plan and quote, orchestration, merged launch pack, publishing | Task fee 1.50, plus hired specialists |
| 1 | **Kai** | Search Demand Analyst | Keyword map, intent clusters, seasonality, peak windows | Per product or topic · 1.25 |
| 2 | **Rafael** | Competitor & Market Analyst | Competitor matrix: who ranks, prices, claims, offers, gaps | Per product or category · 1.25 |
| 3 | **Priya** | Competitor Review & Sentiment Analyst | Competitor customer sentiment: loves, complaints, unmet needs, quotes | Per competitor set (up to 5 products) · 1.50 |
| 4 | **Marcus** | Pricing & Promotions Strategist | Price positioning, promotion calendar, margin-safe discount codes | Per product or campaign · 1.25 |
| 5 | **Clara** | Product Page Copywriter | Title, description, SEO title and meta, handle, tags | Per product · 2.00 |
| 6 | **Iris** | Product Visual Designer | Image audit, cleanup, lifestyle scenes, channel crops, alt text, ordering | Per product (up to 8 images) · 2.50 |
| 7 | **Oskar** | Catalog, Collections & Shopping Feed Specialist | Category and attributes, collections, related products, feed health | Per product · 1.50 |
| 8 | **Yuki** | Localization & Transcreation Specialist | Localized listing and local keywords | Per product per locale · 1.00 |
| 9 | **Leo** | Content & Email Marketer | FAQ, comparison table, blog article, email campaign copy, social pack | Per product or campaign · 2.00 |
| 10 | **Sasha** | Paid Ads Strategist | Campaign plan with break-even bids, ad copy, import file, paused campaigns (Google Ads in v1) | Per product or campaign · 1.50 |
| 11 | **Ruth** | Claims & Compliance Reviewer | Claim, trademark and policy findings with safe rewrites | Per product or asset bundle · 0.25 |
| 12 | **Quinn** | Store Auditor & Performance Analyst | 0–100 listing score, conversion audit, analytics diagnosis, before/after report | Per product per report · 0.50 |

- Catalog data, collections, product linking and feed health live with **Oskar**.
- Handle, SEO title and meta live with **Clara**.
- **Priya analyses competitors' customers only.** She does not read the merchant's own reviews.
- The names do not clash with Sokosumi's featured coworkers (Elena, Hannah, Alex, Maya, Jamal).

---

## 3. Platform mapping (all real primitives)

### 3.1 Sokosumi
Verified against `masumi-network/sokosumi` commit `5d6d6cf` (2026-10-06).

| Need | Sokosumi primitive | Notes |
|---|---|---|
| Listing each team member | **Coworker** record: `name`, `caption` (≤255), `description`, `url`, `baseURL`, `metadata`, `capabilities: [tasks, chat]`. Owned by the **Uplift Vendor**. | Register with `sokosumi --preprod coworkers register --vendor-id … --capability tasks --capability chat --base-url https://chat.uplift.example/v1`. Coworkers start private (`isWhitelisted:false`). Per-workspace access via `coworkers connect`, approved by the workspace owner. Public gallery listing needs whitelisting by a Sokosumi platform admin. |
| Standalone use | **Task** assigned to the coworker | Created with the New Task wizard or `POST /v1/tasks`. The coworker worker polls `GET /v1/coworkers/me/events`. |
| Chat | Coworker `baseURL` implementing the **OpenAI Responses API**: `POST /conversations`, streaming `POST /responses`, `GET /responses/{id}` | Core sends `X-Sokosumi-User-Id`, `X-Sokosumi-Organization-Id` and `X-Coworker-Slug`, with **no bearer token**. The Worker's chat endpoint serves all 13 coworkers by routing on `X-Coworker-Slug`. Chat collects the brief and creates a **DRAFT** Task assigned to itself, which the merchant moves to Ready. Chat never touches the store or money. |
| Asking the merchant something | Task event `status: INPUT_REQUIRED` with a comment | The merchant answers with a comment, and the coworker moves the Task on |
| **Plan approval** and **change approval** | Task event `status: APPROVAL_REQUIRED` with the quote or change set as a comment (plus an attached diff file) | Only a coworker can set this status. The merchant approves by moving the Task to **Ready** (or **Running**) in the status picker — a person may set either status on an `APPROVAL_REQUIRED` Task — or by replying "approve". Either action is recorded as a user-authored Task event. |
| Store connection | Task event `status: AUTHENTICATION_REQUIRED` with `authenticationUrl` (https) | For store-platform and ads/analytics connections (v1: Shopify, Google) |
| Nora hiring specialists | `POST /v1/tasks/{taskId}/jobs {agentId, inputData, maxCredits, name}` | Coworker or Soko Bot authentication only, as the assigned collaborator. **Billed to the Task owner's credits.** Sokosumi's buyer wallet funds the Masumi escrow. Web "Hire" is off for users (ADR-0006/0024); this API is the supported route. |
| Agent pricing for Jobs | Core starts Jobs only for **FREE / FIXED** pricing | Every Uplift Masumi registration uses **Fixed** tUSDM pricing |
| Reading a Job's result | `GET /v1/jobs/{id}` | Returns status, `result`, `resultHash` and `inputHash` |
| Refunding a failed Job | `POST /v1/jobs/{id}/refund` | Any collaborator on the Job may call it (Nora's coworker key with `X-Context-*` headers) |
| Charging a standalone Task | Task event with `masumiPayment` (signed seller terms) | Coworker-only. The balance is checked first; insufficient credits set `OUT_OF_CREDITS`. |
| Delivering files | `POST /v1/tasks/{id}/files` | Coworkers may upload. Max 100 MB per file; no SVG. |
| Acting on the merchant's behalf | `X-Context-User-Id` / `X-Context-Organization-Id` on the coworker key | Core enforces workspace grants |
| Seller receipt | `GET /v1/tasks/{id}/receipt` (`sokosumi runtime receipt`) | `settled:true` and `txHash` once the Masumi escrow is withdrawn to the seller |
| Ratings | `POST /v1/agents/{id}/ratings` | After a finished Job. Nora posts a rating consistent with the Chainlink result. |
| Soko Bot discovery | Soko Bot fit-rates Agents (minimum 0.4) | Keyword-rich captions, descriptions and tags. `SOKO_BOT_ENABLED` defaults to false, so Uplift does not rely on it. |

### 3.2 Masumi
- **Registry V2:** 13 registrations (12 specialists plus Nora). Each is a `Web3CardanoV2` source with `pricing: {pricingType: "Fixed"}` in tUSDM:
  - unit `16a55b2a349361ff88c03788f93e1e966e5d689605d044fef722ddde0014df10745553444d`;
  - 6 decimals.
- **Wallets:** one selling wallet per coworker, for clean per-coworker accounting.
  - Each keeps a collateral UTxO of at least 5 ADA.
  - All are seeded on one Uplift MPS node.
  - Collection address is **null**.
- **Escrow:** Masumi's escrow (lock → result hash → refund window → withdraw), used as provided.
- **One payment node** (MPS) for all Uplift selling wallets, with auto-withdraw and refund authorization for failed Jobs.

### 3.3 Kodosumi (specialist runtime, Kodosumi 1.2.0 on Ray Serve)
- **One Ray cluster.** Each specialist is one **Expose** item with a bootstrap YAML (pinned `py_modules` commit zip, pip dependencies, `num_cpus`), booted from Control > Expose.
- **Sumi endpoints** (`/sumi/{expose}/…`) give each specialist a MIP-003 API:
  - `availability`, `input_schema`, `start_job`, `status/{job_id}` and `provide_input`.
  - These URLs are the `apiBaseUrl` registered on Masumi, so **Jobs hired by Nora run through Sumi**.
  - Payment config: `KODO_MASUMI0="Preprod https://mps.uplift.example/api/v1 <scoped token> 1200 3600 1.0"`, plus `KODO_SUMI_ADDRESS`.
- **The panel API** (`POST /-/<host>/<port>/-/<expose>/…`, then `GET /outputs/status/{fid}`) runs the same flow without Sumi payment. Standalone Tasks use it, and the coworker worker runs the paid-Task flow itself.
- **Locks become questions.** `tracer.lock()` becomes MIP-003 `awaiting_input` in Job mode and Task `INPUT_REQUIRED` in Task mode. Nora's Job inputs are complete, so locks only fire standalone.
- **Files.** Inputs go in `/in`, deliverables in `/out`. Deliverables are mirrored to the artifact store and attached to the Task.
- **Result-hash rule.** Every flow returns `final` as one string: the **RFC 8785 canonical JSON of the Deliverable Manifest** (§6.3). Kodosumi's `create_result_hash` gives `sha256_utf8(final_string)`, which becomes the Job's `resultHash`.

### 3.4 Models (LLM on Amazon Bedrock; image work on remove.bg and Gemini)
- **LLM:** **Grok 4.7** via the bedrock-runtime **Chat Completions API** (OpenAI-compatible), inference profile `us.xai.grok-4.7` in `us-east-1` (one model, one region). It is used for:
  - all text generation, coding/classification and synthesis;
  - vision (`image_url` content parts);
  - structured JSON output (via a forced function call).
- **Image work (Iris only):**
  - **remove.bg API** (`POST /v1.0/removebg`): product cut-outs (`type=product`, `crop=true`, `size=auto`), with an AI drop shadow (`shadow_type=drop`) for compositing. Iris places these exact pixels on white for studio shots and into generated backgrounds for lifestyle scenes.
  - **Gemini Nano Banana 2.1** (`gemini-nano-banana-2.1`, Gemini Interactions API): generates the empty background sets for lifestyle scenes. It never draws the product.
- Translation, grammar checks, image OCR and keyword clustering all run on Grok 4.7; no separate translation, grammar, OCR or embedding services.
- **Who calls Bedrock:** agents, the Worker (Nora and chat) and Chainlink.
- **Auth:**
  - Kodosumi and the Worker call Bedrock over HTTPS with a **Bedrock API key** (`Authorization: Bearer …`, env `BEDROCK_LLM_API_KEY`).
  - Chainlink CRE uses the same key from the Vault DON (`{{.bedrockApiKey}}`).
  - remove.bg (`X-API-Key`, `REMOVEBG_API_KEY`) and Gemini (`x-goog-api-key`, `GEMINI_API_KEY`) keys live only in the Kodosumi service environment.
- **Retries:** throttling and transient errors (429/5xx) back off exponentially; there are no alternative models or regions.

### 3.5 Chainlink CRE
See §5.

---

## 4. System architecture

```
                          ┌────────────────────────── Sokosumi (preprod) ──────────────────────────┐
 Merchant ──chat/Task──►  │ Core: Tasks · approvals · Jobs · credits · files · receipts · ratings  │
                          └──────▲──────────────────────────────▲───────────────────────▲──────────┘
                                 │coworker keys (13)            │Jobs → Sumi start_job  │Responses API
                     ┌───────────┴───────────┐        ┌─────────┴──────────┐   ┌────────┴─────────┐
                     │ Uplift Worker         │◄──────►│ Kodosumi cluster    │   │ Uplift Worker    │
                     │ (Task executors, Nora │ panel  │ 12 specialist flows │   │ chat (Responses  │
                     │ orchestrator, journal)│  API   │ Sumi MIP-003        │   │ API)             │
                     └──┬─────────────▲──────┘        └───┬──────────┬──────┘
                        │ HTTP trigger│ result callback   │ payments │ LLM
                        ▼             │               ┌───▼──────┐   ▼
                   Chainlink CRE `uplift-clearing`    │Uplift MPS│  Amazon Bedrock
                   (verify · publish)                 └───┬──────┘  (Chat Completions)
                        │ Confidential HTTP (Vault keys)  │ Masumi escrow (Cardano Preprod)
                        ▼
                  Uplift Connection Gateway ◄── writes only with CRE's key
                  (platform adapters — v1: Shopify; KMS envelope-encrypted)
                        │
                        ▼
                  Shopify Admin GraphQL
```

| Component | Tech | Responsibility | Holds secrets? |
|---|---|---|---|
| **Uplift Worker** | Python (asyncio) + PostgreSQL | One executor per coworker key. Polls events, runs standalone Tasks (paid-Task flow) and Nora's orchestration. Keeps a per-Task journal, writing each step **before** its side effect. Receives CRE result callbacks. | 13 coworker runtime keys, scoped MPS `ReadAndPay` token, CRE trigger key (Railway service variables) |
| **Kodosumi cluster** | Ray 2.48 + Kodosumi 1.2 | Runs the 12 specialist flows, Sumi endpoints and Job payments | Data-API, remove.bg, Gemini and Bedrock API keys as service env vars |
| **Worker chat** | FastAPI (in the Worker) | Responses API for all coworkers; creates DRAFT Tasks | Coworker keys |
| **Uplift MPS** | masumi-payment-service + PostgreSQL | 13 selling wallets, auto-withdraw, refund authorization | Encrypted wallet mnemonics, admin key |
| **Uplift Connection Gateway** | Python (FastAPI) + PostgreSQL + AWS KMS | Platform adapters (v1: Shopify) for OAuth connect and reconnect, encrypted token storage and rotation; a **read API** for agents and CRE; a **write API only CRE can call** | All merchant tokens, envelope-encrypted |
| **Artifact store** | Amazon S3, content-addressed | Deliverable files (`sha256` keys) | IAM role |

---

## 5. Chainlink CRE — verifier and gate

### 5.1 Why Chainlink
Masumi records **what** was delivered (input and result hashes), and Sokosumi records **who** was paid. Neither has a **verifier**, and neither gives an AI a credible way to act on a merchant's store only after independent checks. CRE provides two things a single company server cannot credibly provide:

1. **Independent verifier and scorer.**
   - A decentralized oracle network (DON) re-checks each deliverable against public sources and deterministic rules.
   - It reaches consensus on a **score (0–100) and verdict (PASS/FAIL)**.
   - That result decides whether the specialist gets paid and whether its changes may go live.
2. **Gatekeeper for store writes.**
   - The key that unlocks the Connection Gateway's write API lives only in the CRE **Vault DON**.
   - It is injected into requests **inside an enclave** through **Confidential HTTP** templates (`{{.gatewayWriteKey}}`).
   - No Uplift server, agent or operator can trigger a store write on its own.
   - CRE publishes only after confirming the merchant's approval in Sokosumi and the passing scores.

### 5.2 The workflow: `uplift-clearing`
- **Code:** TypeScript, `@chainlink/cre-sdk` ≥1.8, compiled to WASM.
- **Run:** simulated with `cre workflow simulate uplift-clearing` for the demo; deployed with `cre workflow deploy`.
- **Trigger:** one HTTP trigger. Callers sign requests with the Uplift Worker's authorized EVM key (JWT). The handler routes by `action`.
- **Result:** the workflow returns its result to the Worker by HTTP callback (Confidential HTTP, `{{.workerCallbackKey}}`). The Worker posts it as a Task comment, e.g. "Chainlink verification: PASS · 82/100".

| Action | Called by | Reads | Does |
|---|---|---|---|
| `verify` | Nora, after each Job completes; a specialist's worker before submitting a standalone Task result | **Approved plan:** the quote comment plus the merchant's approval event on the Sokosumi Task (Confidential HTTP, Nora's key). **Job:** `GET /v1/jobs/{id}` for status, `resultHash`, agent and credits. **Verification bundle:** HTTP. **Store snapshot:** gateway read API. | 1. Checks `sha256(JCS(manifest))` equals the Job's `resultHash` (standalone: equals the manifest hash the worker will submit). 2. Checks the Job's agent and credits are in the approved plan. 3. Runs the role's **verifier profile** (sheet §V), including the **Bedrock judge**. 4. Returns score and PASS/FAIL. 5. On **FAIL for a Job** — or a Job outside the approved plan — files the refund in the same run (`POST /v1/jobs/{id}/refund`, Confidential HTTP with `{{.noraCoworkerKey}}`). |
| `publish` | Nora (or a standalone specialist's worker), after the change approval | **Approval:** the Sokosumi Task's change-set comment (with `change_hash`) and a later user-authored approval event — status moved from `APPROVAL_REQUIRED` to Ready/Running, or an "approve" comment by the Task owner or a workspace member. **Verify results:** for every change in the set, from the Worker's journal, re-confirmed against the Jobs. | 1. Confirms the approval and that every change in the set comes from a PASS deliverable owned by the right role. 2. Calls the gateway **write API** via Confidential HTTP, injecting `{{.gatewayWriteKey}}`, with the change set and `change_hash`. 3. Re-reads the store through the gateway read API. 4. Recomputes the listing score and returns `published`, the after-snapshot hash and the after-score. |

How each read is done:
- **Public facts:** regular HTTP; every node fetches, and they reach consensus on the extracted field.
- **Paid APIs, the Bedrock judge and secret-bearing calls:** Confidential HTTP; one call from the enclave, with consensus on the request.
- **Deterministic maths and rules:** run in workflow code.

### 5.3 The Bedrock judge
- **Model:** Claude Grok 4.7 on Amazon Bedrock.
- **Call:** Chat Completions through Confidential HTTP, with `Authorization: Bearer {{.bedrockApiKey}}`.
- **Prompts:** strict JSON output; each prompt is versioned with its role's verifier profile.
- **Weight:** the judge contributes at most **5 of 100 points** in any profile. Everything else is deterministic or source-checked.
- **Errors:** if the judge call errors, those points are scored at the neutral midpoint.

### 5.4 Verdict rule
- A deliverable **passes** when both hold:
  - all of its role's **hard gates** hold (safety rules only: margin floor, spend cap, bid ceiling, field ownership, product-pixel fidelity, competitor-only sources);
  - its weighted score reaches the role's pass threshold, which is between 60 and 70 (sheet §V).
- Numeric re-checks use generous tolerance bands (±30% for market metrics), because third-party data shifts between fetches.
- The score is reported with every result and shown to the merchant.

### 5.5 Vault DON secrets
| Secret | Used for | Injected via |
|---|---|---|
| `gatewayWriteKey` | `publish` | Confidential HTTP header template |
| `gatewayReadKey` | Snapshot reads | `runtime.getSecret` |
| `noraCoworkerKey` | Sokosumi Task and Job reads; refunds | Confidential HTTP header template |
| `bedrockApiKey` | Bedrock judge | Confidential HTTP header template |
| `workerCallbackKey` | Result callback to the Worker | Confidential HTTP header template |
| `dataforseoBasic` | Market re-checks | Confidential HTTP |
| `firecrawlKey` | Page re-fetch fallback | Confidential HTTP |

Merchant store and ad-account tokens stay in the Connection Gateway, encrypted. The gateway executes writes only when they are presented with CRE's `gatewayWriteKey` (§9).

---

## 6. Data contracts

### 6.1 Job input envelope (Nora → specialist)
Every Job's `inputData` follows the specialist's MIP-003 schema and always includes:
- `brief`;
- `store_snapshot`: canonical product JSON from the gateway read API;
- `upstream`: verified upstream manifests (URL plus `resultHash`);
- `constraints`: brand voice, locked terms, locales, margin floor, forbidden claims;
- `plan_ref`.

Because the snapshot is part of `inputData`, the Job's `inputHash` commits to exactly what the agent saw.

### 6.2 Standalone Task input
The Task description and attached files are parsed into the same schema. Missing required fields become `INPUT_REQUIRED` questions, as listed per agent in the sheet.

### 6.3 Deliverable Manifest (every agent's `final`)
```json
{
  "uplift": "5",
  "role": "copywriter",
  "agent": "clara",
  "job_or_task_id": "…",
  "input_hash": "…",
  "summary_md": "human-readable summary",
  "changeset": [ {"target":"shopify.product","id":"gid://shopify/Product/…","field":"title","before":"…","after":"…"} ],
  "artifacts": [ {"name":"copy_variants.json","sha256":"…","url":"https://…/…","mime":"application/json"} ],
  "evidence": [ {"claim":"…","source_url":"…","fetched_at":"…","excerpt":"…"} ],
  "verification_bundle": {"url":"…","sha256":"…"},
  "self_checks": {"…":"…"},
  "profile": "copywriter@5.0.0"
}
```
- `resultHash = sha256_utf8(JCS(manifest))`.
- The `changeset` contains only fields the role owns (sheet §0.6).

### 6.4 Change approval comment
The merged change set Nora posts for approval contains:
- the plain-language summary;
- the list of changes, by owner;
- the before/after excerpts;
- an attached `changes.html`;
- `change_hash = sha256(JCS(merged changeset))`.

CRE's `publish` reads this comment and requires the approval event to come after it.

---

## 7. Listing Score

Quinn computes the score, and CRE recomputes it.

| Section | Points |
|---|---|
| Discoverability: SEO title and meta, handle, keyword coverage | 22 |
| Persuasion and copy quality | 20 |
| Visuals: count, quality, hero image, alt text | 15 |
| Trust content: shipping and returns information, FAQ, comparison table, review signals | 18 |
| Catalog and feed data: category, attributes, GTIN, Merchant Center status | 15 |
| Compliance | 10 |
| **Total** | **100** |

- The judge contributes at most 5 points.
- The **before** score comes from Quinn's verified baseline audit.
- The **after** score is recomputed by CRE at `publish`.
- Both scores appear in the final report.

---

## 8. Payments

### 8.1 Rails
| Rail | Payer | Flow |
|---|---|---|
| **Specialist Job** (Nora mode) | Merchant's workspace credits | 1. `POST /v1/tasks/{taskId}/jobs` (maxCredits = list price). 2. Core buys at the fixed price from Sokosumi's wallet, opening a Masumi escrow toward the specialist's seller wallet. 3. Kodosumi runs and submits `resultHash`. 4. CRE `verify`: **PASS** → auto-withdraw after unlock; **FAIL** → CRE files the refund in the same run, and Nora re-hires once. |
| **Nora's fee** | Merchant's workspace credits | Paid-Task `masumiPayment` on Nora's Task (seller terms from `POST /payment` on Nora's registration). The result is submitted after the final report. |
| **Standalone specialist Task** | Merchant's workspace credits | 1. The worker gets seller terms (`POST /payment`, Fixed). 2. Task event `masumiPayment` → `FundsLocked`. 3. Kodosumi runs (panel API). 4. CRE `verify` **before submission**. **PASS:** `submit-result`, Task `COMPLETED`. **FAIL:** retry once with the reasons; if it fails again, no result is submitted, the Task is set `FAILED` with reasons, and the escrow returns to the buyer after `submitResultTime`. |

### 8.2 Cost controls
- Nora's plan total is approved explicitly by the merchant.
- Every Job carries `maxCredits` equal to its list price.
- CRE refunds any Job outside the approved plan.
- `OUT_OF_CREDITS` pauses the Task.
- Masumi per-key caps apply to the MPS runtime token.

### 8.3 Proof for the judges
- Masumi escrow lock and withdraw transactions on Cardanoscan.
- `runtime receipt` showing `settled:true`, plus an independent Blockfrost check of the seller's net receipt.
- CRE workflow simulation logs and the per-Job verification comments on the Sokosumi Task (score, verdict, refund).

---

## 9. Store connection and credential custody (v1 adapters)

### 9.1 Commerce platform adapter (v1: Shopify app)
- **Type:** a Dev Dashboard app with **custom distribution**, installed by each merchant through the OAuth **authorization-code grant**.
- **Token:** the install returns an **offline access token**. Custom-distribution apps are exempt from Shopify's expiring-token requirement for public apps, so the token stays valid until the merchant uninstalls the app or Uplift replaces it.
- **Hackathon:** the same app, installed on a development store.
- **Scopes:**

  | Scope | Used by |
  |---|---|
  | `read_products`, `write_products` | Clara, Oskar, Iris, Leo |
  | `write_translations`, `read_locales` | Yuki |
  | `read_discounts`, `write_discounts` | Marcus |
  | `write_content` | Leo (blog articles, unpublished) |
  | `write_files` | Iris |
  | `read_inventory` | Marcus (`InventoryItem.unitCost`) |
  | `read_reports` | Quinn's diagnosis (ShopifyQL); requires Level 2 protected customer data in production |

- **Mandatory webhooks:** `app/uninstalled` (deletes the token), plus the compliance webhooks `customers/data_request`, `customers/redact` and `shop/redact`.

### 9.2 Connect and reconnect
There is one store link per Sokosumi user or organization, shared by all Uplift coworkers.

1. **Connect.** A coworker that needs store data and finds no valid link posts a Task event `AUTHENTICATION_REQUIRED` with `authenticationUrl=https://connect.uplift.example/shopify/start?state=<JWS{taskId,userId,orgId,coworker,nonce,exp}>`. Sokosumi shows this as an **Authenticate** button on the Task.
2. **Authorize.** The merchant clicks the button and enters the shop domain. The gateway redirects to `https://{shop}/admin/oauth/authorize?client_id=…&scope=…&redirect_uri=…&state=…`.
3. **Store.** On callback, the gateway:
   - verifies the HMAC and `state`;
   - exchanges the code for the offline access token;
   - stores it with **envelope encryption** (a per-shop data key wrapped by AWS KMS, ciphertext in PostgreSQL).
4. **Resume.** The gateway notifies the Worker, and the coworker resumes the Task (`RUNNING`).
5. **Reconnect and rotate.** Whenever a Shopify call returns `401` (token revoked, app reinstalled or token invalid), the gateway marks the link **invalid**, and the coworker repeats step 1 on the current Task.
   - Work pauses at `AUTHENTICATION_REQUIRED`, so nothing runs with a dead token.
   - The new token from the merchant's reconnect **replaces** the old one, and the old ciphertext is deleted.
   - Before each Job starts, the Worker runs a cheap `shop { id }` read to detect a dead token early.
6. **Ads and analytics adapter** (designed for: Google — GA4 `analytics.readonly`, Merchant API `content`, Google Ads `adwords`): the same connect, reconnect and replace pattern, only when the work needs it.

### 9.3 Who can do what
| Caller | Read | Write |
|---|---|---|
| Agents (Kodosumi) | `store_snapshot` in `inputData` from Nora; standalone, a short-lived **job-scoped read capability** (JWT naming the shop, resources and fields) | **Never** |
| Nora (Worker) | Snapshot reads for planning and the baseline | **Never** |
| CRE `uplift-clearing` | Yes (read key) | **Only** through the write API, with `{{.gatewayWriteKey}}` from the Vault via Confidential HTTP, after confirming the merchant's approval and the passing results, and with a matching `change_hash` |
| Merchant | Connects and reconnects with the Task's **Authenticate** button. Disconnects by uninstalling the Uplift app, which deletes the token. | — |

---

## 10. Orchestration (Nora)
Routing details are in the spec sheet, §0.

1. **Intake.** Bedrock (Grok 4.7) maps the request to capability tags.
   - Keyword scoring runs against each specialist's name, caption, description and tags.
   - Fit check (≥ 0.4), using Soko Bot's wording: *"Can this agent do what the request asks? A related topic is not enough."*
2. **Dependency closure** in code (sheet §0.4).
3. **Full flow or subset.**
   - "launch", "overhaul", a new product, or "full optimization" → all 12 specialists.
   - Anything else → the minimal closed subset.
4. **Quote.** Nora sets `APPROVAL_REQUIRED` with a comment listing each agent, deliverable, order and credits, plus the total. The merchant approves (Ready, or "approve").
5. **Execute** the DAG. Job inputs include verified upstream manifests, and parallel nodes run together.
6. **Gate.** CRE `verify` scores each Job.
   - A FAIL is refunded and re-hired once.
   - A second FAIL marks the node *blocked*; it is left out of the change set and named in the change-approval comment.
7. **Change approval and publish** (sheet §0, steps 11–12).
8. **Report and close.**
   - Upload Quinn's before/after report and the **Uplift Launch Pack** (ZIP).
   - Nora posts ratings, collects her fee, and sets `COMPLETED`.

---

## 11. Demo script (preprod)
1. **Standalone hire.** The merchant assigns **Quinn** "Audit my bamboo bottle". Quinn returns a score of 42 with the top fixes. CRE `verify` passes (comment: "Chainlink verification: PASS · 88/100"), the result is submitted, and the receipt is settled.
2. **Full launch.**
   - "@Nora launch my bamboo bottle" → store connection (`AUTHENTICATION_REQUIRED`).
   - Quote of 19.50 credits for 1 product and 2 locales (`APPROVAL_REQUIRED`).
   - The merchant moves the Task to Ready.
3. **Execution.** Each Job gets a verification comment with its score.
   - Research runs in parallel: Kai and Rafael, then Priya.
   - Marcus runs next.
   - The builders run: Clara, Iris, Oskar, then Leo.
   - Sasha, Yuki and Ruth run last.
4. **Failure.** Kai's keyword map contains a competitor trademark.
   - FAIL, and the refund is filed in the same run.
   - The credits return to the merchant.
   - Kai is re-hired and passes.
5. **Change approval.**
   - Nora posts "11 changes ready" with the before/after summary and `changes.html`.
   - The merchant moves the Task to Ready.
   - CRE confirms the approval and publishes to Shopify, then creates paused Google Ads campaigns.
   - The listing score rises to 86.
6. **Report.** Quinn writes the after-report, and Nora completes the Task and collects her fee. `runtime receipt` shows `settled:true`.
7. **Subset.** "Translate this listing into German" runs only Yuki, Ruth and Quinn (before/after).

---

## 12. Build plan
| Tier | Scope | By |
|---|---|---|
| **T1** | Register the coworkers, plus the paid-Task proof (Nora). Kodosumi cluster with Quinn, Kai, Rafael, Priya, Clara and Ruth. Connection Gateway (Shopify). `uplift-clearing` (`verify`, `publish`). Bedrock wiring. | Hour 12 |
| **T2** | Iris, Oskar, Marcus, Yuki, Leo and Sasha. Change-approval comment and diff file. | Hour 18 |
| **T3** | Demo polish and the proof page. | Hour 22 |

**First-hour spikes**
1. A Kodosumi Sumi `start_job` hired by a coworker through `POST /tasks/{id}/jobs` on preprod (Fixed pricing).
2. Install the v1 Shopify app on a dev store via the Task's Authenticate button, confirm the offline token type, and run `productUpdate` through the gateway.
3. Confidential HTTP with `{{.bedrockApiKey}}` calling Bedrock Chat Completions, in simulation.
4. CRE reading a Task's approval event through the Sokosumi API with the coworker key.
5. `POST /v1/jobs/{id}/refund` on a test Job.

---

## 13. Open items
- **ShopifyQL product-level sessions and conversion datasets** for Quinn's diagnosis; v1 diagnoses from sales, rankings and the score.
- **Task-claim refunds:** whether Core refunds Task-claim credits when `submitResultTime` lapses without a result (the standalone FAIL path).
- **Amazon reviews:** DataForSEO's Amazon reviews endpoint is "temporarily unavailable", so Bright Data is the primary source.
- **Google Ads API developer token** (Basic access) is needed for direct paused pushes, beyond v1's Editor import file.
