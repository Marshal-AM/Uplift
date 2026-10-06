# Uplift: master spec (v4)

**One payment flow, Sokosumi-native routing, and only contracts that Masumi and Sokosumi don't already provide.**

*TOKEN2049 Origins hackathon: Cardano Agentic Commerce track and Chainlink CRE track. Updated 6 Oct 2026. Deadline 7 Oct 23:59. Source of truth.*

**Research behind this version** (with quotes, file paths and line numbers), in `seller_agents_research/`:
- `sokosumi_capabilities_and_routing.md`
- `masumi_capabilities_and_contract_overlap.md`

> **Changes in v4:**
> - **One payment flow:** the customer's Sokosumi credits pay **every** agent, both the Lead and each agent it hires, through Masumi escrow. **Specialists no longer hire each other.**
> - **Routing:** the Lead routes each request to **all 13 agents or only the subset it needs**, using Sokosumi's catalog API and the same method Sokosumi's own router uses.
> - **Contracts:** `uplift_vault` is **dropped** (Sokosumi pays from its own wallet, and Masumi already caps spending). `uplift_suite` shrinks to `uplift_config`. `uplift_cert` is replaced by `uplift_attest`, which is tied to the live Masumi escrow. `uplift_permit` is new (the merchant's on-chain consent before anything is published). `uplift_success_fee` is an optional add-on.

---

## 1. What Sokosumi and Masumi already do (so we don't rebuild it)

| Need | Already provided | So Uplift… |
|---|---|---|
| **Paying agents** | When a Coworker hires an Agent (`POST /v1/tasks/{taskId}/jobs`), the Job is **billed to the Task owner's credits**. **Sokosumi's own wallet funds the Masumi escrow**; the Coworker's wallet is never used | Uses this for **every** hire. One payment flow |
| **Escrow, refunds, disputes** | Masumi `vested_pay` V2: lock, then result hash, then time-based release. Full refunds on request; admin multisig for disputes | Uses it unchanged. Doesn't build escrow |
| **Spending limits** | Workspace credits, seats, **per-Job `maxCredits`**, an `OUT_OF_CREDITS` pause; Masumi per-API-key caps. An on-chain co-signed smart wallet is in development (Masumi PR #952, draft) | **No vault.** Sets `maxCredits` on every hire. (Missing: a per-Task budget cap. "Quote approval" is only *Planned* in Sokosumi, so Uplift adds an approved quote, see §4) |
| **Identity, listing, price** | Masumi Registry V2 (identity, metadata, on-chain price); the Sokosumi catalog | Lists all 14 agents there. **No second registry** |
| **Per-job on-chain record** | The escrow holds the input hash and result hash (MIP-004) while it's live | Binds Chainlink's verdict to it (§6) |
| **Routing** | **Soko Bot**, Sokosumi's personal assistant for *users*: keyword scoring plus an LLM fit check (fit ≥ 0.4), then **one agent per action**. Coworkers can't call it, and it may be switched off (`SOKO_BOT_ENABLED` defaults to false) | (1) Writes keyword-rich listings so Soko Bot sends users to the Lead or to a single Uplift agent. (2) Inside the Lead, does **multi-agent subset routing**, which Sokosumi doesn't offer, using the catalog API and the same method |
| **Reputation** | Off-chain 1–5 star ratings (almost unused: 1 rated agent each on Preprod and Mainnet), plus `jobCount` | Adds on-chain **verification attestations**. Also posts a Sokosumi rating after each Job, so both signals agree |
| **Verifier** | **None.** No verifier or oracle role exists anywhere in Masumi or Sokosumi | **Chainlink CRE is Uplift's verifier.** This is the core gap Uplift fills |
| **Agent acting on a merchant's store** | Nothing | CRE holds the store keys, and the merchant consents on-chain (§6) |

**Judges look for** (from Masumi's TOKEN2049 pages):
- quality
- usefulness ("which steps still need a person")
- reliable execution with no double charge
- **verified payment**

The paid-Task collection proof comes first.

---

## 2. The one payment flow

```
CUSTOMER (Sokosumi workspace credits)
   │  pays ──► Uplift Lead's fee               ─┐
   │  pays ──► each agent the Lead hires        ├─ all through Sokosumi's wallet → Masumi escrow (Cardano)
   │  pays ──► or one agent hired directly     ─┘
   ▼
Each agent submits its result hash → Chainlink CRE verifies → PASS: escrow releases to the agent
                                                            → FAIL: CRE files the refund → credits back to the customer
```

- **The same rail for everyone.** Whether the customer hires one agent directly or the Lead hires 13, every agent is paid from the customer's credits into its own Masumi escrow.
- **The Lead never holds or forwards money.** It is paid its orchestration fee for the Task (paid-Task flow: `masumiPayment`), and it commissions agents billed to the customer.
- **Cost control:**
  - every hire carries `maxCredits` = the agent's list price
  - the customer approves a **quote** before work starts
  - CRE flags any hire outside the approved quote and files a refund for it
- **Failed work:** CRE files the refund (`POST /v1/jobs/{id}/refund`) before the escrow unlocks. Credits return to the customer once the on-chain refund is withdrawn. The Lead re-hires that agent once, with the failure reasons attached.

---

## 3. The 14 agents (1 head + 13 specialists)

Every agent:
- is listed on **Sokosumi** (Masumi Registry V2, FIXED tUSDM price) and **can be hired on its own**
- uses MIP-003 endpoints and Masumi escrow, with its result hash on-chain
- has a **verifier profile** that CRE runs; its hash is in `uplift_config`
- gets an **`uplift_attest`** attestation for every Job that passes

Prices are placeholders, in credits shown as tUSDM.

| # | Agent | What it does | Price | Owns (CRE publishes) | CRE checks (highlights) |
|---|---|---|---|---|---|
| 1 | **Uplift Lead** (head; Sokosumi Coworker) | Reads the request, **routes to all 13 agents or a subset**, quotes, runs the work, merges the results, reports | 1.5 + the hired agents | — | The quote is honoured; final score ≥ target (when the listing changes) |
| 2 | **Keyword & Demand Scout** | Clustered keyword map, intents, seasonality, peak windows | 1.25 | — | Metrics re-fetched (≥ 80% within tolerance); 0 trademarks; seasonality recomputed |
| 3 | **SERP & Competitor Intel** | Who ranks, prices, claims, JSON-LD, gaps | 1.0 | — | Cited pages re-fetched; prices and titles found in them; band maths recomputed |
| 4 | **Customer Insight Miner** | Review themes, objections, verbatim quotes, evidence-linked personas | 1.25 | — | Quotes verbatim; counts recomputed; persona evidence exists |
| 5 | **Pricing & Promotions Strategist** | Price scenarios, promo calendar, scheduled discount codes | 1.25 | Discount codes | Margins ≥ floor after discount; dates in peak windows; codes read back |
| 6 | **Listing Copywriter** | Title, body, SEO title and meta (3 variants, best one chosen) | 2.0 | `title`, `descriptionHtml`, `seo.*` | 45-point rubric section; hard gates; dual-LLM fact check (5 points) |
| 7 | **Visual Merchandiser** | Image audit, ordering, alt text, optional lifestyle images | 1.0 | Media | Alt rules; hero image ≥ 1000 px; ordering |
| 8 | **Catalog Data Engineer** | Taxonomy, attributes, handle, tags, Product JSON-LD, channel exports | 1.25 | Taxonomy, handle, tags, attributes | Category exists; handle and tag rules; JSON-LD; exports pass schemas |
| 9 | **Collection & Linking Architect** | Category collection page plus related-product links | 1.0 | Collections, `custom.related` | SEO lengths; product in the collection; links resolve |
| 10 | **Localization Studio** | Transcreation into 2 locales with local keywords | 1.5 | Translations | Lengths; locked terms; local keyword; back-translation (low weight) |
| 11 | **Content Studio** | FAQ and comparison table, SEO blog article, launch email and social posts | 2.0 | `custom.faq`, `custom.comparison`, blog | JSON-LD; FAQ maps to objections; article and link checks; UTM |
| 12 | **Ads Strategist** | Campaign plan with break-even bid maths, plus exports | 1.5 | — | Spend ≤ cap; bids ≤ break-even; no negative blocks a positive |
| 13 | **Compliance Guardian** | Claim, trademark and policy violations, with fixes | 0.25 | — | Same rule engine in CRE; hits must match |
| 14 | **Listing Auditor & Reporter** | **Audit:** 0–100 score plus fixes. **Report:** before/after, what each agent changed, what was paid | 0.3 | — | Score must **equal** CRE's recomputed score; report numbers recomputed |

**Nobody can change price, inventory or product status.** CRE rejects any change outside an agent's owned fields.

---

## 4. Routing in the Uplift Lead: all 13, or just a subset

**How a request reaches the Lead:**
- Directly: a user mentions **@Uplift Lead** in Sokosumi chat.
- Through Soko Bot: Sokosumi's user assistant routes the user to the Lead, or to one Uplift agent, because the listings are keyword-rich.

Core calls the Lead's responses endpoint. The Lead then creates the Task (`POST /v1/tasks`).

**The routing algorithm** mirrors Soko Bot's method, but picks a **set** of agents and runs them together:

1. **Load the candidates.** `GET /v1/agents/{id}` for the 13 Uplift agent IDs on the Lead's own allow-list, giving summary, tags, input schema, credits, rating and job count. **Sokosumi has no allow-list feature, so the Lead keeps its own.**
2. **Extract what the request needs.** An LLM maps the request onto 13 capability tags (keywords, competitors, insights, pricing, copy, images, catalog data, collections, localization, content, ads, compliance, audit).
3. **Score each agent:**
   - **keyword score:** hits in the request against the agent's name and capability, which count double, plus its summary and tags
   - **LLM fit check**, in the same wording as Soko Bot: *"Can this agent do what the request asks? A related topic is not enough."* Keep agents with fit ≥ 0.4.
4. **Close the dependencies, in code** (a fixed dependency graph, not the LLM):
   - Copywriter, Content Studio or Ads → add the Keyword & Demand Scout, unless the user supplied keywords.
   - Copywriter or Content Studio → add the Customer Insight Miner, if reviews exist.
   - Pricing & Promotions → add SERP & Competitor Intel.
   - Localization → runs after the Copywriter, if new copy is in the plan.
   - **Any agent that writes to the store → add the Compliance Guardian.**
   - **Any change to the listing → add the Listing Auditor & Reporter**, for the baseline and final report.
5. **Decide full flow or subset.**
   - "Launch", "overhaul", "full optimisation" or a new product → **all 13**.
   - Otherwise, **the minimal closed subset**.
6. **Quote, then approve.**
   - The Lead posts the plan (agents, order, credits each, total) and sets the Task to **`APPROVAL_REQUIRED`**.
   - The customer approves.
   - CRE commits the **plan hash** (§7).
   - This adds the per-Task budget cap Sokosumi lacks.
7. **Execute.** Hire each agent with `POST /v1/tasks/{taskId}/jobs {agentId, inputData, maxCredits}`, in dependency order. Agents run in parallel where they can, and verified outputs are passed into later jobs.
8. **Gate.** CRE checks each Job. A failed Job is refunded and re-hired once. Work that writes to the store waits for the merchant's permit, then CRE publishes it.
9. **Complete.** Merge the results, have the Auditor & Reporter write the report, then `POST /v1/tasks/{id}/events {status: COMPLETED}`.

**Routing examples:**

| Customer writes | Agents chosen | Count |
|---|---|---|
| "Launch my new bamboo bottle on my store" | All 13 | 13 |
| "Rewrite the titles and descriptions of these 3 products" | Keyword & Demand Scout, Customer Insight Miner, Listing Copywriter, Compliance Guardian, Listing Auditor & Reporter | 5 |
| "Translate my bottle listing into German and Japanese" | Localization Studio, Compliance Guardian, Listing Auditor & Reporter | 3 |
| "Plan a Black Friday promotion" | Keyword & Demand Scout (seasonality), SERP & Competitor Intel, Pricing & Promotions Strategist, Compliance Guardian | 4 |
| "Why isn't this listing converting?" | Listing Auditor & Reporter, SERP & Competitor Intel, Customer Insight Miner | 3 |

**Full-flow order** when all 13 are chosen:
1. Audit (baseline).
2. Research: Keyword & Demand Scout, SERP & Competitor Intel, Customer Insight Miner.
3. Strategy: Pricing & Promotions Strategist.
4. Build: Copywriter, Visual Merchandiser, Catalog Data Engineer, Collection & Linking Architect, Content Studio, then Localization Studio.
5. Compliance review.
6. **Merchant permit, then CRE publishes.**
7. Launch: Ads Strategist.
8. Report.

---

## 5. Cardano integrations

| Integration | Use | Notes |
|---|---|---|
| **Sokosumi Coworker** | The Uplift Lead takes chat requests and Tasks | CLI: `npm i -g @masumi_network/sokosumi`, then `sokosumi --preprod auth login`, then create an organization and vendor, then `coworkers register --capability tasks`. Worker polls `GET /v1/coworkers/me/events`. The chat endpoint is OpenAI-Responses-compatible. Paid-Task proof follows the demo's `paid-task.mjs` |
| **Sokosumi Jobs API** | Every hire | `POST /v1/tasks/{taskId}/jobs` (billed to the Task owner's credits, with `maxCredits`); `GET /v1/tasks/{id}/jobs`; `POST /v1/jobs/{id}/refund`; ratings through `POST /v1/agents/{id}/ratings` |
| **Event workspace** | Visibility to judges | `https://preprod.sokosumi.com/join/9Ycw8wzmzXB2WEKa-umzUJX6_GEFiVdu`, organization `01a109d1-32a9-71a3-a0e3-658b2a7987cd` |
| **Masumi Registry V2** | 13 Agents listed (the Lead is a Coworker) | Fixed tUSDM pricing (asset `16a55b2a…745553444d`). Automatic Preprod listing in about 5–15 minutes. **Keyword-rich descriptions and tags**, so Soko Bot can find them. Each registry update changes the `agentIdentifier` (the version is part of the asset name), so set the URL and metadata before registering |
| **Masumi Payment Service** (self-hosted) | Agents get paid | `Web3CardanoV2` plus `supportedPaymentSourceIndex`. **Don't use pip-masumi 1.2.0**; copy the Node `agent-api.mjs` from `demo-agent-token2049`. Webhooks drive agent-side refund authorisation |
| **Masumi `vested_pay` V2** | Escrow for every Job | Each deadline ≥ 15 minutes after the previous one; a 7-minute cooldown. Refunds are full and time-boxed |
| **Our contracts** | `uplift_config`, `uplift_attest`, `uplift_permit`, optional `uplift_success_fee` | §6 |
| **Chain reads** | CRE, Lead, Console | NOWNodes (Blockfrost-compatible) if it serves Preprod; otherwise Blockfrost or Koios |
| **Submission proof** | Masumi's requirement | Preprod payment-node transaction, collection transaction, seller's net receipt, slides with the video |

---

## 6. Smart contracts (Cardano, Aiken, Plutus V3)

### 6.1 How they were chosen

| Planned in v3 | Verdict | Reason |
|---|---|---|
| `uplift_vault` | **Dropped** | Sokosumi pays every Job from its own wallet, so a vault held by the Lead is **outside the money flow**. Masumi's V2 escrow requires a key-address buyer, so a script buyer would lock the funds permanently. Spending caps exist already, and an on-chain co-signed wallet is in development (PR #952) |
| `uplift_suite` | **Reduced to `uplift_config`** | Agent IDs and prices already live in Masumi's registry. A copy would drift, and IDs change on every registry update. **Only the Chainlink key and the verifier-rule hashes are new** |
| `uplift_cert` | **Replaced by `uplift_attest`** | Masumi records "what was delivered" (the result hash) but **never "who checked it, and did it pass?"** The attestation adds the missing independent verifier, bound to Masumi's escrow |
| — | **New: `uplift_permit`** | Nothing in Masumi or Sokosumi records a merchant's **consent** before an AI acts with the merchant's credentials. It also answers the judges' "which steps still need a person" |
| — | **Optional: `uplift_success_fee`** | Masumi escrow can't release on a third-party condition. Use it for a success fee paid only if CRE confirms the listing hit its target |

**Not built** (Masumi or Sokosumi already does it): registry, escrow, disputes, identity/KYC, spending vault, L2.

### 6.2 How Cardano trusts Chainlink

- **Primary:** CRE holds an **Ed25519 key as a workflow secret**, used inside the TEE in production. It signs short, domain-tagged messages, and Aiken checks them with **`verify_ed25519_signature`** against the key in `uplift_config`. CRE never builds Cardano transactions; the Lead's backend submits them.
- **Stretch:** check the DON's secp256k1 report signatures on-chain.
- **Base Sepolia** (always): Chainlink's forwarder checks DON signatures natively.
- **Replay protection:** each signed message includes a **domain tag** and an **output reference the transaction must spend**.

**First-hour spike:** Ed25519 signing (`@noble/ed25519` with `@noble/hashes`) inside CRE's QuickJS runtime. **Fallback:** a disclosed relayer key.

### 6.3 `uplift_config`: verifier configuration (a reference UTxO plus a one-shot NFT)

**`ConfigDatum`:**

| Field | Type | Purpose |
|---|---|---|
| `cre_vk` | ByteArray (32) | Chainlink's Ed25519 public key |
| `rules` | `List<(role: ByteArray, verifier_profile_hash: ByteArray)>` | Which version of each agent's checks CRE applies, public and fixed |
| `seller_vkhs` | `List<VerificationKeyHash>` | Our agents' selling wallets. They're stable, unlike registry IDs, so they identify Uplift work |
| `admins`, `threshold` | `List<VerificationKeyHash>`, Int | Team multisig |
| `version` | Int | Increments on each update |

- **Redeemer `Update`:** needs the admin threshold; the NFT stays put; `version + 1`.
- **Read by** `uplift_attest`, `uplift_permit` and CRE as a reference input.
- **Why it matters:** the key Cardano trusts and the rules Chainlink applies are **on-chain and versioned**. Rotating the key or changing a rule is a visible, signed event.

### 6.4 `uplift_attest`: verification attestations bound to the live Masumi escrow (minting policy)

**What it proves:** *Chainlink checked exactly the work this agent committed in Masumi's escrow, and here is the verdict.*

**Mint rules.** All of the following must hold in the minting transaction:
1. **The live Masumi `vested_pay` V2 escrow UTxO for the Job is a reference input.** Its datum is in the result-submitted state, and its **input hash, result hash and seller** match the attestation. Aiken decodes Masumi's V2 datum, using the type in the cloned `payment-v2` source.
2. The seller's key hash is in `uplift_config.seller_vkhs`, so the attestation is for Uplift work.
3. There is a **CRE Ed25519 signature** over `("ATTEST", escrow_out_ref, input_hash, result_hash, role, verifier_profile_hash, verdict, score, artifact_hash, spent_out_ref)`.
4. `verifier_profile_hash` equals `uplift_config.rules[role]`.
5. **The asset name = `blake2b_224(escrow_out_ref)`, and the token goes to an always-fail "attestation store" address** with an inline datum `{job_ref, agent_seller_vkh, role, input_hash, result_hash, verifier_profile_hash, verdict, score, artifact_hash, evm_verdict_ref, issued_at}`.

**Constraints and uses:**
- **Timing:** the attestation must be minted while the escrow is still live, after the result is submitted and before the seller collects. The earliest unlock is 15 minutes after submit, and the default is 6 hours.
- **Cost:** about 1.5–2 ADA locked per attestation, which is fine on Preprod. Mints can be batched per phase.
- **What uses it:**
  - `uplift_permit`: only PASS-attested work can be approved and published
  - the Reporter: each agent's on-chain verified track record
  - the Console's agent profiles
- **Why it isn't duplication:** Masumi's escrow says *what* was delivered; nothing says *whether it was right*. This also cross-links to the Base Sepolia `NodeVerdict` through `evm_verdict_ref`.

### 6.5 `uplift_permit`: the merchant's on-chain consent to publish (spend validator plus a permit token)

A **state machine** for each store change-set:

| State | How it gets there | Who signs |
|---|---|---|
| **Verified** | Created when a PASS `uplift_attest` exists for the change-set; holds `{campaign_ref, product_ref, change_hash, attest_refs[], merchant_vkh, expires}` | Lead backend, plus the CRE `"PERMIT"` signature |
| **Approved** | The merchant approves the exact `change_hash` | **The merchant** (CIP-30 wallet, for example Lace on Preprod) |
| **Published** | CRE published to Shopify and recorded the Shopify product ID and `published_hash` | CRE `"PUBLISHED"` signature |
| **Revoked / Expired** | The merchant revokes before publishing, or `expires` passes | Merchant / anyone |

**Enforcement:**
- **CRE's `audit_publish` reads the permit on Cardano and publishes only when it is `Approved` and unused.** It then moves the permit to `Published`, so it can't be reused.
- A store write therefore needs **both** Chainlink's verdict **and** the merchant's on-chain approval.
- The merchant can approve each phase in one transaction (several change-sets per permit).
- **For newcomers:** the Console shows "Approve 6 changes" with a plain-language diff, then a single wallet signature.

### 6.6 `uplift_success_fee`: optional outcome-based fee (spend validator)

- **Datum:** `{merchant_vkh, lead_vkh, amount, product_ref, baseline_score, target_score, deadline, campaign_ref}`.
- **The merchant locks a success fee in tUSDM** on top of the normal Sokosumi credits.
- **`Release`:** a CRE `"OUTCOME"` signature confirms the final score ≥ `target_score` for `product_ref` before `deadline`. The fee pays the Lead's address.
- **`Reclaim`:** after `deadline` with no qualifying signature, the merchant takes it back.
- **Why it's optional:** it sits outside Sokosumi's credit flow and doesn't count toward Masumi's "verified payment" criterion. Pitch it as the "pay for results" add-on.

### 6.7 Masumi contracts (used, not modified)

| Contract | Use |
|---|---|
| **`vested_pay` V2** | Every Job's escrow. Read as a **reference input** by `uplift_attest` |
| **Registry V2** | Agent identity, metadata and price |

### 6.8 Base Sepolia: `UpliftLedger.sol` (Chainlink's native write)

**Why Base Sepolia:**
- CRE can't write natively to Cardano.
- The forwarder checks DON signatures on-chain.
- Log events drive `settle`.
- It's fast and cheap; Ethereum Sepolia had an upgrade on 6 Oct.

**Events:**
- `PlanCommitted(taskRef, planHash, agents, quoteCredits)`
- `BaselineCommitted(taskRef, productGid, score, snapshotHash)`
- `NodeVerdict(taskRef, jobRef, agentRole, resultHash, verifierProfileHash, outcome, score)`
- `Published(taskRef, productGid, changeHash, permitRef, afterScore)`
- `FinalScore(taskRef, score)`

It accepts writes only from the forwarder and our workflow, and holds no funds.

**Alternative:** a Solana devnet program, which would also qualify for the Solana side track.

---

## 7. Chainlink integrations

**Workflow:** `uplift-clearing`, written in TypeScript with the CRE SDK.
- **Simulate:** `cre workflow simulate uplift-clearing --broadcast`.
- **Install the skills:** `npx skills add smartcontractkit/chainlink-agent-skills`.
- **One HTTP trigger** routes by `action`.

| Action / handler | Trigger | Reads | Does | Writes / signs |
|---|---|---|---|---|
| **`connect_store`** | HTTP, inside the TEE | Shopify OAuth callback data, forwarded by our backend | Checks the HMAC, exchanges the install code for the store token, encrypts it, stores only the ciphertext (§8.1) | — |
| **`plan_commit`** | HTTP, inside the TEE | Sokosumi Task (Confidential HTTP); Shopify (Confidential HTTP); `uplift_config` (Cardano) | Checks the approved plan uses only Uplift agents at catalog prices; baseline score | `PlanCommitted`, `BaselineCommitted` |
| **`verify_node`** | HTTP, inside the TEE when keys are needed | **Masumi escrow on Cardano** (result hash, state); DataForSEO and LLMs; cited pages; Sokosumi Job (agent, credits) | Runs the agent's verifier profile. Checks the Job's agent and credits match the plan, and that the deliverable's hash equals the on-chain result hash | `NodeVerdict`; signs `ATTEST` |
| **`permit_open`** | HTTP | `uplift_attest` tokens (Cardano) | Every change-set in a publishing group has a PASS attestation | Signs `PERMIT` |
| **`audit_publish`** | HTTP, **`handlerInTee`** | **`uplift_permit` on Cardano (must be `Approved`)**; Shopify | Re-checks ownership and hashes, **publishes to Shopify**, re-reads and re-scores | `Published`; signs `PUBLISHED` |
| **`settle`** | **EVM Log** (`NodeVerdict` with outcome FAIL) | Masumi escrow state | Files **that Job's** refund (`POST /v1/jobs/{id}/refund`, Confidential HTTP) before unlock, and notifies the Lead to re-hire | — |
| **`close`** | HTTP, inside the TEE | Shopify; the Task | Final score; signs `OUTCOME` for the optional success fee | `FinalScore` |
| **`sweeper`** | **Cron** (every 5 min) | Masumi escrows; permits | Refunds before unlock; expired permits; retries | — |

**What CRE reads from Cardano:**
- **each Job's live Masumi escrow:** state, input and result hashes, seller, unlock time
- **`uplift_config`:** its own key and the rule hashes
- **`uplift_attest` tokens:** for permits and reports
- **`uplift_permit` state:** **it never publishes without `Approved`**
- **`uplift_success_fee` state** (optional)

All through NOWNodes or Blockfrost.

**Secrets in the enclave:** the exact list is in **§8.4**. Agents never hold store credentials.

**Agents never hold store credentials.**

**Limits:**
- ≤ 15 HTTP calls per run, ≤ 10 s each, ≤ 5 min per run: one `verify_node` run per Job, and `audit_publish` per publishing group.
- The production HTTP trigger fires at most once per 30 s.

**Dual-LLM judge:** two models, strict JSON, a deterministic merge. Disagreement or confidence below 0.7 means ESCALATE. LLM judgement is capped at 5 of 100 points.

---

## 8. Connecting a Shopify store, and exactly what CRE holds

### 8.1 What the merchant does

The merchant never pastes a password or API key anywhere: not into Sokosumi chat, not to the Lead, not to any agent.

1. **Ask.** The merchant writes in Sokosumi: "@Uplift Lead optimise my bamboo bottle on `my-store.myshopify.com`".
2. **The Lead asks to connect the store, using Sokosumi's built-in button.** If the store isn't connected yet, the Lead posts:
   `POST /v1/tasks/{id}/events {status: "AUTHENTICATION_REQUIRED", authenticationUrl: "https://uplift.app/connect/shopify?task={id}&shop={shop}"}`
   Sokosumi shows an **"Authenticate"** button on the Task and notifies the merchant (verified in Sokosumi's code: `apps/core/src/routes/v1/tasks/[id]/events/schema.ts:309-330`, `apps/web/.../task-activity.tsx:766-773`).
   - The URL must be https.
   - The button label is fixed by Sokosumi.
3. **Shopify's standard install screen.** The button opens Uplift's connect page, which redirects to Shopify's OAuth install screen (`https://{shop}/admin/oauth/authorize?client_id=…&scope=…&redirect_uri=…&state=…`).
   - Shopify lists exactly what Uplift may do (scopes in §8.3).
   - **Price, inventory and orders are not requested.**
   - The merchant clicks **Install**.
4. **The token goes straight to Chainlink.**
   - Shopify redirects to our callback with a one-time `code`.
   - The callback **does not exchange the code itself**. It forwards `{shop, code, hmac, state}` to the CRE workflow (HTTP trigger, action `connect_store`).
   - Inside the TEE, CRE:
     1. checks Shopify's HMAC with the app's client secret;
     2. exchanges the code for the store's offline access token (`POST https://{shop}/admin/oauth/access_token`);
     3. **encrypts the token with a key only CRE holds**;
     4. sends just the ciphertext to the Uplift token store.
   - **Neither our backend nor any agent ever sees the plain token.**
5. **Optional: bind the store to the merchant's wallet.**
   - The merchant signs a one-time CIP-8 message `("UPLIFT-STORE", shop, merchant_vkh)` with Lace.
   - CRE checks it and records the binding.
   - From then on, only that wallet can approve `uplift_permit`s for that store.
6. **Continue.** Our backend notifies the Lead that the store is connected. The Lead sets the Task to `RUNNING` and continues: routing, then quote (`APPROVAL_REQUIRED`), then work.
7. **Revoke at any time.** Uninstalling the Uplift app in Shopify kills the token. Shopify's `app/uninstalled` webhook makes the backend delete the ciphertext. Nothing is ever published without the merchant's `uplift_permit` approval anyway.

**At publish time:** CRE `audit_publish`:
1. fetches the store's ciphertext;
2. **decrypts it inside the TEE**;
3. calls the Shopify Admin GraphQL API;
4. throws the plain token away when the run ends.

Agents only ever deliver *proposed* change-sets.

### 8.2 Hackathon demo vs production

| | **Hackathon demo** (our own store) | **Production** (any merchant) |
|---|---|---|
| Store | Our Shopify **dev store** (Partner account, then Dev Dashboard, then `shopify store create dev --demo-data`) | The merchant's own store |
| Shopify app | **Dev Dashboard app**, installed on our dev store. Dev Dashboard apps only work on stores in our own organisation | **Public (unlisted) Shopify app** using the OAuth authorization-code grant, so any merchant can install it |
| Connect step | Already connected. We still **show** the `AUTHENTICATION_REQUIRED` button flow in the video | The §8.1 flow |
| How CRE gets a token | **Client-credentials grant**: CRE uses the app's client ID and secret to get a fresh **24-hour token** inside the TEE on each run (`POST https://{shop}.myshopify.com/admin/oauth/access_token`) | CRE decrypts the merchant's stored **offline token** inside the TEE |
| Storefront | Always password-protected, so scoring reads the Admin API | Public |
| Backup | WooCommerce with Yoast on TasteWP (application password as the secret) | — |

### 8.3 Shopify permissions (scopes) Uplift requests

| Scope | Used by |
|---|---|
| `read_products`, `write_products` | Listing text, SEO fields, tags, handle, taxonomy, metafields, collections (Copywriter, Catalog Data Engineer, Collection & Linking Architect, Content Studio's FAQ fields) |
| `write_files` | Image alt text, media (Visual Merchandiser) |
| `read_publications`, `write_publications` | Making new collections and content visible |
| `read_locales`, `write_locales`, `write_translations` | Localization Studio |
| `read_content`, `write_content` | Blog articles (Content Studio) |
| `read_discounts`, `write_discounts` | Scheduled, inactive discount codes (Pricing & Promotions Strategist) |
| **Not requested** | Orders, customers, inventory, payments, themes. Price changes are blocked by CRE's hard gate anyway |

### 8.4 Exactly what credentials live inside the CRE workflow

They're stored as CRE workflow secrets: `secrets.yaml` in simulation, Chainlink's secrets store when deployed. They're used **only inside the TEE handler** (Confidential HTTP), except where noted.

| Secret name | What it is | Used for | Demo / Prod | In TEE? |
|---|---|---|---|---|
| `SHOPIFY_CLIENT_ID` | Uplift Shopify app's client ID | OAuth exchange; client-credentials token | Both | Yes |
| `SHOPIFY_CLIENT_SECRET` | Uplift Shopify app's client secret | **Demo:** gets the 24-hour token for our dev store. **Prod:** checks the OAuth callback HMAC and exchanges the install `code` for the merchant's token | Both | **Yes** (high value) |
| `SHOPIFY_DEMO_SHOP` | `uplift-demo.myshopify.com` (config, not secret) | Demo store domain | Demo | — |
| `UPLIFT_TOKEN_KEY` | X25519 private key (its public half encrypts merchant tokens) | Decrypts each merchant's stored Shopify token at publish time | Prod | **Yes** (high value) |
| `TOKEN_STORE_API_KEY` | Read/write key for the encrypted token store | Fetch and store ciphertext | Prod | Yes |
| `LLM_API_KEY_A`, `LLM_API_KEY_B` | Two different LLM providers (spending-limited keys) | Dual-LLM judge | Both | **Yes** |
| `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | DataForSEO API account | Re-fetch keyword metrics and search results to check the Scout and SERP Intel | Both | Yes |
| `SOKOSUMI_API_KEY` | The Lead's Coworker runtime key (`coworker_…`) | Read Tasks and Jobs; **file refunds** (`POST /v1/jobs/{id}/refund`) for failed Jobs | Both | **Yes** |
| `CRE_CARDANO_ED25519_SEED` | 32-byte Ed25519 seed; its public key is in `uplift_config.cre_vk` | Signs `ATTEST`, `PERMIT`, `PUBLISHED` and `OUTCOME` messages that Cardano contracts check | Both | **Yes** (high value) |
| `CARDANO_READ_API_KEY` | NOWNodes (or Blockfrost Preprod) project key | Read Masumi escrows, `uplift_config`, attestations and permits | Both | No (read-only, low value) |

**Never inside CRE:**
- agents' Cardano wallet keys and Masumi payment-service admin keys (each agent's own server)
- the merchant's wallet keys
- the merchant's Shopify password
- any EVM private key: **writes to Base Sepolia are signed by Chainlink's nodes and delivered through the forwarder, so CRE needs no EVM key of its own**

**Agents and the Lead never receive** any Shopify credential, the decryption key or the Cardano signing key.

**Rotation:**
- Rotating `CRE_CARDANO_ED25519_SEED` means an `uplift_config` `Update` signed by the team multisig, with the new public key.
- Rotating Shopify credentials means a new client secret in the Partner Dashboard, then updating the CRE secret.
- Rotating `UPLIFT_TOKEN_KEY` means re-encrypting the stored tokens inside a CRE maintenance run.

*Unverified: the exact way to store and decrypt per-merchant tokens inside a deployed Confidential Workflow (secrets are documented; per-merchant ciphertext handling is our design); and Shopify's public-app review for production. The demo relies only on the documented client-credentials flow with a workflow secret.*

---

## 9. End-to-end demo

1. **Standalone hire:** a user hires just the **Listing Auditor & Reporter** on Sokosumi (0.3 credits).
   - It reports a score of 42, and CRE confirms the score matches.
   - **`uplift_attest` is minted against the live escrow.**
   - The escrow later releases the payment to the agent.
2. **Full request:**
   - The seller writes "@Uplift Lead launch my bamboo bottle".
   - The Lead routes to **all 13** and posts a quote of 15.75 credits (`APPROVAL_REQUIRED`), and the seller approves.
   - CRE writes `PlanCommitted` and the baseline (42).
3. **Execution:**
   - The Lead hires each agent through the Jobs API, billed to the seller's credits, each with `maxCredits`.
   - Each Job is a Masumi escrow. CRE runs `verify_node`, writes `NodeVerdict`, and mints an attestation.
4. **Failure:**
   - The Keyword & Demand Scout's output contains a trademark, so the verdict is FAIL.
   - `settle` files that Job's refund, and the credits return to the seller.
   - The Lead re-hires the Scout, which passes.
5. **Build and permit:**
   - The builders deliver and the Compliance Guardian reviews.
   - CRE opens a **permit** for the 6 verified change-sets, and the merchant clicks **Approve** in Lace.
   - CRE `audit_publish` publishes, and the score rises to **86**.
6. **Launch, report, done:**
   - The Ads Strategist runs, then the Auditor & Reporter writes the report.
   - The Lead completes the Task, and its fee collection proves verified payment.
   - Optional: `close` releases the success fee.
7. **Subset demo:** "Translate this listing into German" routes to only 3 agents.
8. **Proof:**
   - Cardanoscan: escrows, attestations, permits
   - Basescan: verdicts
   - CRE simulation logs
   - the Console

---

## 10. Build plan

| Tier | Contents | By |
|---|---|---|
| **T1** | Lead with routing, quote and execution; Keyword & Demand Scout, SERP & Competitor Intel, Customer Insight Miner, Listing Copywriter, Visual Merchandiser, Catalog Data Engineer, Compliance Guardian, Listing Auditor & Reporter. **Contracts:** `uplift_config`, `uplift_attest`. **CRE:** `plan_commit`, `verify_node`, `audit_publish`, `settle`. **EVM:** `UpliftLedger`. **The paid-Task collection proof** | Hour 12 |
| **T2** | Pricing & Promotions Strategist, Collection & Linking Architect, Content Studio, Localization Studio, Ads Strategist. **`uplift_permit`** plus CRE `permit_open`; `close`; `sweeper`; the Console | Hour 18 |
| **T3** | `uplift_success_fee`; DON-signature checks in Aiken; the x402 lane | Hour 22 |

**First-hour checks:**
1. The Lead as a Coworker plus one Agent, live and paid on Preprod (verified payment proof).
2. CRE simulation reading Shopify, writing to Base Sepolia, and **signing with Ed25519**.
3. **An Aiken test that decodes a real Masumi V2 escrow datum** and checks a CRE signature.
4. A Masumi refund through `POST /v1/jobs/{id}/refund`.
5. One payment node serving 13 agents.
6. Shopify scopes.
7. Verifiers running under QuickJS.
8. NOWNodes on Preprod.

---

## 11. Open items (unverified)

- Ed25519 signing inside CRE's runtime (otherwise, a disclosed relayer key).
- Masumi V2 escrow datum layout for the reference-input check. Take it from `payment-v2` source in the local clone.
- Whether Soko Bot is enabled on Preprod.
- Event-workspace approval time; NOWNodes Preprod.
- Shopify dev-store scopes for translations, blog, discounts and collections.
