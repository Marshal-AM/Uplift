# Sokosumi · Masumi · Kodosumi — Ecosystem Overview

Researched 2026-10-06. Sources: [05-references.md](05-references.md). Facts marked **[source]** were read from code or docs. Facts marked **[inferred]** are my synthesis.

## TL;DR

| Layer | Product | One line | Who runs it |
|---|---|---|---|
| Marketplace / work surface | **Sokosumi** | Where businesses hire "AI coworkers" and brief them like colleagues. Credits, tasks, deliverables. | Serviceplan Group + NMKR (Munich). Hosted SaaS. |
| Protocol (payments + identity) | **Masumi** | Cardano protocol for agent identity (NFT registry), escrowed payments (USDM), and decision logging (hashes on-chain). | Open source. You run your own **Masumi Payment Service (MPS)** node. |
| Runtime | **Kodosumi** | Ray-based Python runtime for running agent workflows at scale, with an admin panel, event streams, HITL locks, and built-in MIP-003 + Masumi payments. | Open source. You self-host it, or use a hosted panel. |

Canonical pipeline from the masumi-skills docs: `Build agent (any framework) → Deploy on Kodosumi → Register on Masumi → List on Sokosumi → Get paid via Masumi`. **[source]**

The **current preprod developer path is Coworker-centric**. The CLI (`@masumi_network/sokosumi` 1.0.4) and the TOKEN2049 guide do not require Kodosumi. They use any agent runtime (Vercel eve by default), plus a polling worker, plus optional MPS for payments. **[source]**

---

## 1. Sokosumi

### What it is
- Marketing site: "a marketplace where you hire AI coworkers for marketing work. A coworker has a name, a role, and a vendor." Users brief coworkers like colleagues and get **files, not a chat log**: PDFs, decks, dashboards. **[source]**
- Developer docs: "the marketplace for AI agents. It is where agents are discovered, accessed and matched to users and other agents." It integrates Masumi (payments and identity) and Kodosumi (execution). It is framework-agnostic: CrewAI, AutoGen, PhiData, LangGraph, and others. **[source]**
- Built in Munich by Serviceplan Group "with NMKR". Enterprise logos on the site include Telekom, Allianz, Lufthansa, ARD, and Samsung. **[source]**

### Why it exists [inferred, from positioning]
- Agencies and enterprises want outsourced specialist work without hiring. Chatbots do not produce deliverables, and they do not fit task boards and review loops.
- Agent builders lack distribution, billing, identity, and trust. Sokosumi supplies the buyers and the credits. Masumi supplies trustless settlement, so a third-party vendor can be paid per task with an audit trail.
- "Coworkers don't replace your people." Humans still brief and review the work.

### Buyer-side features
- **Named AI coworkers** with public profiles from vendors. Featured coworkers include Elena (strategy), Hannah (research), Alex (coding/dashboards), Maya (creative), and Jamal (experience).
- **Task board**: "who has it and where it stands". One brief can be split across several coworkers working in parallel.
- **Template tasks** covering research, social, planning, writing, engineering, and prototyping. Each template shows sample outputs before you spend credits.
- Workspaces: a **Personal Workspace** plus **Organization Workspaces** with a shared credit pool and seats. Also Projects, a History feed, Chat rooms, Drive/Exports, an Image Studio, and Hermes (beta).
- **Billing**: Free plan has 250 credits per seat. Paid plans start at €25/month for 1,500 credits per seat. Enterprise is custom. Credits come in two types: *subscription* credits renew each cycle; *extra* credits never expire. **[source]**
- Use cases by industry: agencies (pitch research, competitive analysis); SaaS (SEO audits, launch content, AI visibility); e-commerce (social listening, competitor monitoring); finance (market intel briefings); media (content operations).

### Two "sellable unit" models (important)
| | **Agent** (older, Masumi-first) | **Coworker** (current focus) |
|---|---|---|
| Identity | On-chain Masumi registry NFT (`agentIdentifier`) | Sokosumi Core record (`coworkerId`) owned by a **Vendor** |
| Interface | Your hosted **MIP-003 HTTP API** (`/start_job`, `/status`, …) | **Tasks**: a worker polls Core for assigned Tasks. **Chat**: an OpenAI-compatible `baseURL`. |
| Buyer action | `agents hire AGENT_ID` creates a **Job** | Create a **Task** on the task board, assigned to the coworker |
| Payment | Masumi escrow per job | Workspace **credits**. Optionally, the worker attaches a `masumiPayment` and Core's buyer funds Masumi escrow. |
| Listing | Preprod: auto-appears in the gallery after Masumi registration with USDM pricing (per docs). Mainnet: Tally whitelisting form. | Private by default (`isWhitelisted:false`). Workspace access is via grants. Global listing requires platform whitelisting. |

### Interaction surfaces
- **Web**: `sokosumi.com` / `app.sokosumi.com`. Preprod is at `preprod.sokosumi.com`, with email/Google/Microsoft/Passkey login.
- **REST API**: mainnet `https://api.sokosumi.com/v1`, preprod `https://api.preprod.sokosumi.com/v1`. Uses a Bearer token. Responses use the envelope `{data, meta:{pagination:{cursor,nextCursor}}}`. Pagination is cursor-based. The old `X-API-Key` header is no longer accepted. **[source: masumi-skills]**
- **CLI**: `@masumi_network/sokosumi` (Node 24). See [02-listing-coworker-preprod.md](02-listing-coworker-preprod.md).
- **MCP**: `@sokosumi/mcp-server` exposes listAgents, getAgentDetails, createJob, getJobStatus, and waitForJob. **[source: masumi-skills; not independently verified]**
- **Python SDK**: "pysokosumi" (docs page `/dev/sokosumi/documentation/pysokosumi`).
- **Agent Skills**: bundled with the CLI. Run `sokosumi skills path`, or install with `npx skills add https://github.com/masumi-network/sokosumi --full-depth --skill sokosumi`. The skills are `sokosumi`, `coworker`, `tasks`, `jobs`, `agents`, and `watch`.

### What Sokosumi gives *agent developers* specifically
1. **Distribution**: a buyer base, a gallery, template tasks, and organization workspaces that can grant access to your coworker.
2. **Identity and vendor model**: a Vendor owns Coworkers. Vendor roles are `admin` and `developer`; only `admin` can connect a coworker.
3. **Two capabilities**: `chat` (you supply an OpenAI-compatible endpoint) and `tasks` (you run a worker that polls events).
4. **Runtime credentials** scoped to one coworker (`coworker_…` keys), kept separate from human OAuth.
5. **Task lifecycle API**: events with `RUNNING`, `INPUT_REQUIRED`, `COMPLETED`, `FAILED`. Comments allow follow-ups. Usage reporting goes to `/coworkers/me/usage`, using idempotency keys of the form `usage:{taskId}:{eventId}:{action}`.
6. **Payment bridge**: a Task event can carry `masumiPayment`. Core debits the buyer's workspace credits and funds Masumi escrow toward your seller wallet. `runtime receipt` proves on-chain settlement.
7. **Delegation headers** for chat coworkers: `X-Delegation-User-Id` and `X-Delegation-Organization-Id`.

---

## 2. Masumi

### What it is
"Decentralized protocol for AI agents payments and identity." It runs on Cardano and is framework-agnostic. **[source]** It has three pillars:
1. **Identity and trust**: each agent is registered as an NFT in an on-chain registry (MIP-002 metadata), giving it an `agentIdentifier` (policyId + asset name). Optional KERI/ACDC verifications are supported.
2. **Decision logging**: SHA-256 hashes of input and output (MIP-004) are put on-chain, giving tamper-evident proof of what was asked and what was delivered.
3. **Agent payments**: an escrow smart contract (Aiken, audited by TxPipe in April 2025) handles agent↔agent and human↔agent payments in **USDM** (stablecoin), with refunds and disputes.

### Components
- **Masumi Payment Service (MPS)**: the node you run (Node/TS, PostgreSQL, Blockfrost). It manages hot wallets (purchasing and selling), registry minting, escrow transactions, auto-withdraw, webhooks, invoices, swaps, an x402 rail, and Hydra L2 (experimental). It has an admin dashboard at `/admin/`.
- **Registry Service**: read-only queries of on-chain registrations (`/payment-information`, registry-entry search).
- **Standards (MIPs)**: MIP-001 (process), MIP-002 (on-chain metadata), MIP-003 (Agentic Service API) with Attachment-01 (input schema format), MIP-004 (hashing).
- **x402**: an HTTP-402 pay-per-call rail. It is immediate and non-refundable. Use it for cheap, high-frequency calls; use MIP-003 escrow for work that needs delivery guarantees.
- **Integrations**: n8n node, Masumi MCP server, masumi-skills (an AI coding assistant skill), Agent Explorer (`masumi.network/agent-explorer`), and an Agent Messenger ("inbox registry").

### Why it exists [inferred]
Autonomous agents need to transact with strangers. Masumi provides escrow, so the seller only gets paid after submitting a result hash, and the buyer can dispute within a window. Verifiable identity and auditability make this suitable for regulated or enterprise buyers.

Details: [03-masumi-payments-reference.md](03-masumi-payments-reference.md).

---

## 3. Kodosumi

- "The runtime environment to manage and execute agentic services at scale." It is built on **Ray / Ray Serve**, plus Litestar and FastAPI. It is Python-first. Current version is 1.2.0 (repo commit `c4f2032`, 2026-09-15).
- Building blocks: your Flow, Kodosumi itself (panel, spooler, runner, event stream), and the Ray cluster.
- Features: admin panel (port 3370), timeline and analytics dashboard, forms, file I/O, HITL locks and leases, **Expose/Boot/Exchange** declarative deployments, **Sumi endpoints that are MIP-003 compliant**, and a built-in **Masumi registry and payment dashboard**.

Details and workflow guidance: [04-kodosumi-guide.md](04-kodosumi-guide.md).

---

## 4. How the pieces fit (paid Coworker on preprod)

```
Buyer (Sokosumi Web/CLI) ──create Task──► Sokosumi Core ◄──poll/start/complete── Your Worker ──prompt──► Your Agent (eve / Kodosumi flow / anything)
                                              │                                      │
                                   charges workspace credits                 POST /payment (signed terms)
                                   funds escrow (Core = buyer)               POST /payment/submit-result
                                              ▼                                      ▼
                                     Cardano Preprod escrow contract ◄──────── Your MPS node (selling wallet)
                                              │
                                   after unlockTime → auto-withdraw → seller wallet (tUSDM)
```

Key separations to keep straight:
- Workspace **credits** ≠ test **USDM** in escrow ≠ **model-provider** costs. Each is billed separately.
- **Coworker ID**, **Vendor ID**, and Masumi **agentIdentifier** are three different identifiers.
- **Account OAuth** creates Tasks. The **Coworker runtime key** executes them. The **MPS `token`** (scoped `canPay`) handles payments. The **MPS ADMIN_KEY** is for setup only.
