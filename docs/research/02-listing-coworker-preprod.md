# Listing an AI Coworker on Sokosumi Preprod — Runbook

Researched 2026-10-06, against CLI `@masumi_network/sokosumi@1.0.4`, MPS commit `71455701`, and demo-agent-token2049 branch `live-demo-name-finder`.
The authoritative project guide is [../agent-guide.md](../agent-guide.md) (the TOKEN2049 guide). This file explains it, cross-checks it against source, and adds the legacy "Agent" path.

---

## 0. Pick a path

| Goal | Path |
|---|---|
| Get a coworker that a workspace can assign Tasks to, private first (**the hackathon requirement**) | **Path A: Coworker**, steps A1–A7 |
| Expose a public MIP-003 HTTP agent that buyers "hire" as Jobs | **Path B: Masumi Agent** |
| Get paid on-chain for Coworker Tasks | Path A, plus the Masumi registration from Path B (Dynamic pricing, V2). The worker does the payment steps. |

**Public discovery** of a Coworker means it is globally whitelisted (`isWhitelisted:true`). Only a platform admin can set that; it is not self-service. On preprod, a Vendor admin can only create **private** coworkers. On mainnet, coworker creation still needs a platform admin. **[source: CLI README, Core refs]**

---

## Path A — Coworker (current flow)

### Prerequisites
- Node.js **24**. The CLI `engines` field pins `24.x`. *This machine currently has Node v22.23.0. Upgrade before installing.*
- A Sokosumi preprod account: https://preprod.sokosumi.com/signup
- Membership in at least one **organization** workspace. Core refuses to create a Vendor without one, with the error "Creating a vendor requires an organization workspace…". Create a demo organization using the Workspace switcher in the web UI.

### A1. Install the CLI and sign in
```sh
unset SOKOSUMI_API_KEY SOKOSUMI_AUTH_TOKEN      # these override saved OAuth
npm i -g @masumi_network/sokosumi               # NOT `sokosumi` (old docs are stale)
sokosumi --version
sokosumi --preprod auth login                   # browser OAuth; preprod client lqhckIfBGmFhBMyCkbhvUkXHiatZVXwR
sokosumi --preprod auth whoami --json           # verify the intended account and platformRole
sokosumi skills path                            # bundled SKILL.md files: sokosumi, coworker, tasks, jobs, agents, watch
```
Credentials are stored in the OS vault (macOS Keychain). Precedence: flags > env > `~/.sokosumi/config.json` > local `.env` > defaults. `SOKOSUMI_API_KEY` beats `SOKOSUMI_AUTH_TOKEN`.

### A2. Discover before creating
```sh
sokosumi --preprod workspaces list --json             # organization memberships
sokosumi --preprod workspaces list --personal --json  # read-only; does NOT create the personal WS
sokosumi --preprod vendors me --json                  # Vendor memberships and roles
sokosumi --preprod coworkers list --scope owned --json
```

### A3. Vendor, then Coworker
```sh
# Only if you have no Vendor. There is one self-service Vendor per account; on a limit conflict, reuse `vendors me`.
sokosumi --preprod vendors create --name "VENDOR NAME" --slug vendor-slug --json

# Creates a PRIVATE coworker (isWhitelisted:false). --personal also creates the personal workspace and requests access.
sokosumi --preprod coworkers register --vendor-id VENDOR_ID --name "COWORKER NAME" --capability tasks --personal --json
# On resume, never re-register. Use: coworkers connect COWORKER_ID --vendor-id VENDOR_ID --personal --json
```
- You need Vendor role `admin`; `developer` is not enough. Organization owner/admin does **not** grant Vendor authority.
- `coworkers provision` is an alternative that only creates the record and does not request workspace access.
- Capabilities are `tasks` (a worker polls) and `chat` (requires `--base-url`, an OpenAI-compatible endpoint). You can enable both.
- In the web UI, switch to **Personal Workspace** to see the coworker.

Checkpoint: save the Vendor ID, Coworker ID, personal workspace ID, and access ID. Access must be `GRANTED`.

### A4. Runtime key
- `sokosumi --preprod coworkers api-key COWORKER_ID --json` returns a `coworker_…` token **once**; later lists show only a prefix.
- Import it into the vault with `sokosumi --preprod runtime key-import --coworker-id ID --api-key-stdin`. The import checks the coworker's identity and its `tasks` capability.
- The guide's Node one-liner (in agent-guide.md §2) does both steps. It writes `SOKOSUMI_COWORKER_API_KEY` to a git-ignored `.env.local` with mode 0600, then imports. Never print the key.
- Runtime commands use **only** this key and are fixed to preprod. They never use your OAuth login.

### A5. Build the agent and worker
- Agent: any runtime works. The default is **Vercel eve** (`npx eve@latest init my-agent`). Put the job in `agent/instructions.md` and the model in `agent/agent.ts`. The demo uses Z.ai GLM through `@ai-sdk/openai-compatible`.
- Worker: a loop that finds READY Tasks for your coworker, runs `runtime start`, sends the description to the agent, saves the exact UTF-8 result (max 1 MiB), then runs `runtime complete`. The reference implementation is `worker.mjs` in demo-agent-token2049 (`live-demo-name-finder`):
  - Per-Task journal in `.local/<taskId>.json` with phases `starting → started → model-pending → result-saved → complete-pending → completed`. Write each phase **before** the side effect.
  - A single-instance lock (`worker-lock.mjs`). Run **one executor per coworker**.
  - Poll interval 5 s using `sokosumi --preprod tasks list --coworker-id ID --json`.
  - Follow-up comments: read task events, filter `actor.type==='user'` comments, continue the same eve session, and post a reply with `createTaskEvent`. The worker imports `runtime-credentials.js`, `http-client.js`, and `task-service.js` from the installed CLI's `dist/src`, which it locates via `sokosumi skills path`.
- A polling worker needs **no public URL**.

### A6. Execution-only rehearsal (unpaid)
1. Add Stripe **test** credits to the Personal Workspace at https://preprod.sokosumi.com/billing?tab=credits, using card `4242 4242 4242 4242` with any future expiry and any CVC.
2. Pause the auto worker, then run:
```sh
sokosumi --preprod tasks create --personal --coworker-id CID --name "Tiny agent demo" \
  --description "Write a two-sentence welcome for the hackathon." --status READY --json
sokosumi --preprod runtime start TASK_ID --coworker-id CID --personal --json      # → RUNNING
# run the agent, write result.txt
sokosumi --preprod runtime complete TASK_ID --coworker-id CID --personal --result-file ./result.txt --json
```
- A first `runtime start` can return **403 `grant_required`** ("Vendor workspace access is required"). The workspace owner approves the Vendor request in Personal Workspace notifications; then retry **the same Task**. For `grant_denied` or `grant_revoked`, the workspace owner must resolve it.
- Coworker access (who can assign work) and the Vendor runtime grant (who can execute) are **separate** approvals.

### A7. Share it with an organization or event workspace
```sh
sokosumi --preprod coworkers connect CID --vendor-id VID --workspace-id ORG_ID --json   # PENDING = request submitted
sokosumi --preprod workspaces check ORG_ID --json                                      # taskSeatEligible etc.
```
- Org task commands use `--organization-slug SLUG`. Org runtime commands use `--organization-id ORG_ID`. Never combine these with `--personal`.
- On approval, you get an in-app notification and an email titled "COWORKER_NAME approved for WORKSPACE_NAME". Check its `runtimeAccessStatus` (`GRANTED`, `PENDING`, `NOT_REQUESTED`, `DENIED`, or `REVOKED`) separately.
- TOKEN2049 event: join link `https://preprod.sokosumi.com/join/9Ycw8wzmzXB2WEKa-umzUJX6_GEFiVdu`, organization ID `01a109d1-32a9-71a3-a0e3-658b2a7987cd`, slug `token2049-origins-hackathon-2026-nws2r7`.

---

## Path A+ — Paid Coworker Tasks (Masumi escrow)

### Payment node (MPS)
```sh
git clone https://github.com/masumi-network/masumi-payment-service.git && cd masumi-payment-service
git rev-parse HEAD
(umask 077; cp .env.example .env)      # DATABASE_URL, ENCRYPTION_KEY(>=32), ADMIN_KEY(>=32), BLOCKFROST_API_KEY_PREPROD,
                                       # PORT=3012, SEED_ONLY_IF_EMPTY=true, AUTO_WITHDRAW_PAYMENTS=true
                                       # REMOVE COLLECTION_WALLET_V2_PREPROD_ADDRESS (unset ≠ empty string)
pnpm install --frozen-lockfile && pnpm run prisma:generate && pnpm run prisma:migrate
pnpm run prisma:seed >/dev/null 2>&1   # prints mnemonics, so suppress output; seeds a Web3CardanoV2 Preprod source + wallets
pnpm -C frontend run build && pnpm run dev
curl --fail http://127.0.0.1:3012/api/v1/health
```
- Database: PostgreSQL ≥13, a dedicated DB. Docker example: `postgres:16` on `127.0.0.1:5433`.
- MPS is **not** a Cardano node; it reaches the chain through Blockfrost.
- The selling wallet's `collectionAddress` must be `null`. If a V2 selling wallet has a collection address, it is signed into the terms, and buyers on another node fail signature checks. Kodosumi's docs give the same warning. **[source]**
- Fund the **selling wallet** with test ADA for registration, collateral (≥5 ADA reserve UTxO, per MPS CONTEXT), and fees. Faucet: https://dispenser.masumi.network (uses the verification code from your registration email). The seller needs **no** USDM to receive payment, because Core's buyer funds escrow.

### Register on Masumi (seller side)
`POST {MPS}/api/v1/registry`, with headers `token: <ADMIN_KEY>` and `content-type: application/json`. Shape taken from the demo `payment-registration.mjs`:
```json
{
  "network": "Preprod",
  "type": "Standard",
  "sellingWalletVkey": "<selling wallet vkey>",
  "supportedPaymentSources": [{
    "chain": "Cardano", "network": "Preprod", "paymentSourceType": "Web3CardanoV2",
    "address": "<seeded V2 smartContractAddress>",
    "pricing": { "pricingType": "Dynamic" }
  }],
  "name": "…", "description": "…",
  "Capability": { "name": "<model>", "version": "1" },
  "Author": { "name": "…" },
  "Tags": ["…"], "ExampleOutputs": [],
  "apiBaseUrl": "http://127.0.0.1:21950"
}
```
- Access `type` values: `Standard` needs `apiBaseUrl`, `OpenApi` needs `openApiSpecUrl`, `X402` needs `x402ResourcesUrl`, and `A2A` (V2 only) needs `apiBaseUrl`, `a2aAgentCardUrl`, and `a2aProtocolVersions`. **[source: MPS registry/schemas.ts]**
- With V2, pricing lives **per supported payment source**. Do not use the top-level `AgentPricing`. The guide requires exactly `{"pricingType":"Dynamic"}`.
- Poll `GET /registry?network=Preprod&filterPaymentSourceType=Web3CardanoV2` until the state is `RegistrationConfirmed` (`Requested → Initiated → Confirmed`, or `Failed`). Then save `agentIdentifier`, the source index, policyId, contract address, seller vkey, and seller address.
- The Standard `apiBaseUrl` must be a **real** MIP-003 API you implement. The demo's `agent-api.mjs` is a minimal one. Never point it at the MPS URL.
- To update metadata: V1 required deregister (burn) and re-mint. MPS now has `registry/update` routes, but verify them before relying on them.

### Scoped runtime key for the worker
`POST /api/v1/api-key` with the admin token:
```json
{"usageLimited":"false","UsageCredits":[],"NetworkLimit":["Preprod"],"ChainIdLimit":[],
 "canRead":true,"canPay":true,"canAdmin":false,
 "walletScopeEnabled":true,"WalletScopeHotWalletIds":["<selling wallet id>"],
 "x402WalletScopeEnabled":true,"X402WalletScopeEvmWalletIds":[]}
```
The token is revealed **once**; a masked `*****` value means it is lost. Store it in a 0600 file.

### Per-Task paid sequence (from `paid-task.mjs`)
1. **Seller terms**: `POST /api/v1/payment` with:
   ```json
   {"network":"Preprod","agentIdentifier":"…","paymentSourceType":"Web3CardanoV2","supportedPaymentSourceIndex":0,
    "inputHash":"<sha256(raw task description UTF-8)>","identifierFromPurchaser":"<20 hex chars>",
    "RequestedFunds":[{"amount":"1000000","unit":"16a55b2a…745553444d"}],
    "payByTime":"+5m","submitResultTime":"+20m","unlockTime":"+36m","externalDisputeUnlockTime":"+52m",
    "metadata":"{\"taskId\":\"…\"}"}
   ```
   The time fields take ISO timestamps (relative offsets shown for brevity). The response carries a signed `blockchainIdentifier`. Do **not** edit signed fields.
2. **Ask Core to buy**: `POST {Core}/v1/tasks/{taskId}/events` with the coworker key and body `{comment, masumiPayment:{blockchainIdentifier, agentIdentifier, sellerVkey, submitResultTime, payByTime, unlockTime, externalDisputeUnlockTime, inputHash, identifierFromPurchaser, paymentSourceType:"Web3CardanoV2", supportedPaymentSourceIndex, Amounts:[{amount,unit}], PaymentSource:{network:"Preprod", smartContractAddress, policyId}}}`. Core charges credits and locks escrow. Core cannot carry non-null `sellerReturnAddress` or `forceLayer`.
3. Poll `POST /api/v1/payment/resolve-blockchain-identifier` (`includeHistory:'true'`) until `onChainState==='FundsLocked'` **and** a Confirmed transaction exists.
4. Recheck `submitResultTime`, run the model, and save the result.
5. `POST /api/v1/payment/submit-result` with `{network, blockchainIdentifier, submitResultHash}`. Wait for a confirmed `ResultSubmitted` whose hash matches.
6. Complete the Task with event `{status:"COMPLETED", comment: result}`.
7. After `unlockTime`, MPS auto-withdraws (`Withdrawn`). Verify with `GET {Core}/v1/tasks/{id}/receipt` (or `sokosumi runtime receipt TASK_ID --coworker-id CID --json`): it must show `settled:true` and a `txHash`. Then check independently: the Blockfrost `txs/{hash}/utxos` net tUSDM at the seller address must be > 0.

> **Hashing gotcha.** Direct Task payments hash the **raw UTF-8 string** (`sha256(text)`). The Standard MIP-003 API route uses **MIP-004**: `sha256(nonce + ";" + JCS(input))` for input and `sha256(nonce + ";" + output)` for output. The demo README states this explicitly. Test both forms with newlines, quotes, and backslashes. **[source]**

> `runtime complete` does **not** submit `masumiPayment`, the result hash, or collection. Your worker must do those. Task `COMPLETED`, a credit debit, or `PURCHASED` is **not** proof of seller payment.

---

## Path B — Legacy "Agent" listing (Masumi registry → Sokosumi gallery)

From the Masumi docs "Register agent" and "List agent on Sokosumi" pages:
1. Run an MPS node and fund the selling wallet with test ADA.
2. Build a **MIP-003** API: `/availability` (`{status:"available", type:"masumi-agent"}`), `/input_schema`, `/start_job`, `/status`, `/provide_input`, and `/demo`. See [03-masumi-payments-reference.md](03-masumi-payments-reference.md).
3. Register with **USDM pricing**. The preprod tUSDM unit is `16a55b2a349361ff88c03788f93e1e966e5d689605d044fef722ddde0014df10745553444d` (6 decimals). Set `PAYMENT_UNIT` to the same unit.
4. Preprod: "Your agent will automatically appear in the Sokosumi preprod gallery: https://preprod.sokosumi.com/agents". **[source: docs; not live-verified, and the current UI is Coworker-centric]**
5. Mainnet: whitelisting via the Tally form https://tally.so/r/nPLBaV. The team reviews submissions (name, description, public HTTPS MIP-003 URL, pricing, tags, example outputs, ToS/Privacy URLs).
6. Buyers use `sokosumi agents list` / `agents hire AGENT_ID --input-json … --max-credits N`, then `jobs get` and `jobs input` for HITL.

Kodosumi automates Path B: Expose a flow, register it from the panel, and get the `/sumi/...` MIP-003 endpoints. See [04-kodosumi-guide.md](04-kodosumi-guide.md).

---

## Discrepancies found (docs vs current code)

| Topic | Older docs say | Current reality |
|---|---|---|
| CLI package | `npm install -g sokosumi`, Node 18+ | `@masumi_network/sokosumi` 1.0.4, Node **24** |
| Coworker creation | admin `POST /coworkers` + whitelist | On preprod, a Vendor admin can self-create private coworkers via the CLI. Whitelisting is still admin-only. |
| MPS port | 3001 | 3001 is the default; the guide sets `PORT=3012`. The demo used 38127. |
| MPS auth header | `x-api-key` | `token` header |
| Registry pricing | top-level `pricing`/`AgentPricing`, Fixed | V2: `supportedPaymentSources[].pricing`; the guide uses `Dynamic` |
| Registration time | 5–15 min | Kodosumi docs: 1–3 min on preprod |
| Payment source | V1 | `Web3CardanoV2` is canonical; V1 is "legacy" (still supported). V1→V2 gives a **new** agentIdentifier. |
| Install guide | `masumi-services-dev-quickstart` docker compose (registry 3000, payment 3001) | Still valid for a quick node; the guide uses a direct MPS clone with pnpm 10.30.2 |
| Sokosumi Simple/Advanced `payment_mode` YAML (masumi-skills) | appears in the skill | Not found in any CLI/Core source I read. Treat as **unverified**. |

## Status of the CLI's own claims (as of the 1.0.4 package)
The CLI README marks "Live runtime execution remains unverified" and says "payment submission and global publication remain separate work". The demo repo's status log (2026-10-06) shows: a VERIFIED real Task `COMPLETED`; a VERIFIED `RegistrationConfirmed` with Dynamic V2 pricing (tx `4391dc1b…`); and a failed paid API run caused by an MPS **schema/binary mismatch** (`PaymentRequest.cardanoFeeAccountingVersion` missing). Lesson: after `git pull` on MPS, rebuild and re-run migrations together. A health check is not proof that payments work.
