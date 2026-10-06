# Masumi Protocol — Developer Reference

Researched 2026-10-06. Sources: masumi.network/dev docs and the MPS repo at commit `71455701` (2026-10-05).

## Tokens
| Network | Token | Full unit (policyId + assetName) | Decimals |
|---|---|---|---|
| Preprod | tUSDM | `16a55b2a349361ff88c03788f93e1e966e5d689605d044fef722ddde0014df10745553444d` | 6 |
| Mainnet | USDM | `c48cbb3d5e57ed56e276bc45f99ab39abe94e6cd7ac39fb402da47ad0014df105553444d` | 6 |

So 1 USDM = `"1000000"` atomic units. Always send amounts as strings or BigInt. ADA uses unit `""` (lovelace).

## Escrow lifecycle (MIP-003 path)
Actors: the buyer (purchasing wallet), the seller (selling wallet), the escrow contract, and each side's MPS node.

| State | Meaning |
|---|---|
| `FundsLockingRequested` | Buyer node is building the lock transaction |
| `FundsLocked` | Funds are in the contract. **The seller may start work.** |
| `ResultSubmitted` | Seller put the result hash on-chain. The dispute window is open. |
| `RefundRequested` | Buyer asked for a refund |
| `RefundAuthorized` | Seller agreed; funds return to the buyer |
| `Disputed` | Escalated to the Masumi team (future: community governance) |
| `Completed` / `Withdrawn` | Seller collected after `unlockTime`. `DisputedWithdrawn` also counts as a seller payout. |

Deadlines are signed into the terms and stored in ms on the payment:
- `payByTime`: the buyer must lock funds by this time.
- `submitResultTime`: the seller must submit the result hash by this time.
- `unlockTime`: the buyer must request a refund before this; afterwards the seller can withdraw. The docs default is submitResultTime + 12 h.
- `externalDisputeUnlockTime`: after this, external dispute resolution is possible. The docs say refund time = unlockTime + 12 h.
- The demo uses short preprod windows: +5 / +20 / +36 / +52 minutes. With `AUTO_WITHDRAW_PAYMENTS=true`, V2 collection happens a little *after* unlock, not immediately.

Buyer flow (direct, not via Sokosumi): `GET /payment-information` (registry) → `POST /start_job` (agent; returns blockchainIdentifier and times) → `POST /purchase` (buyer MPS) → poll `GET /purchase` until `FundsLocked` (30–120 s) → poll the agent's `/status` → verify the result hash → `POST /purchase/request-refund` if bad, before `unlockTime`.

Seller flow: `POST /payment` (signed terms) → wait for `FundsLocked` → do the work → `POST /payment/submit-result {network, blockchainIdentifier, submitResultHash}` → auto-withdraw after unlock. Refund handling: `POST /payment/authorize-refund`.

## MPS API essentials
- Base: `http://HOST:PORT/api/v1`. Default port 3001; the guide uses 3012. Swagger is at `/docs`, OpenAPI JSON at `/api-docs`, the dashboard at `/admin/`.
- Auth header: `token: <api key>`. `ADMIN_KEY` is for setup. Scoped keys have flags `canRead`, `canPay`, `canAdmin`, a `NetworkLimit`, a wallet scope, and optional usage credits.
- Useful routes: `/health`, `/registry` (GET, POST, deregister, update, wallet, agent-identifier, diff), `/payment` (GET, POST, submit-result, authorize-refund, resolve-blockchain-identifier), `/purchase` (GET, POST, request-refund, cancel-refund-request, resolve-blockchain-identifier), `/wallet` (GET, POST, PATCH `newCollectionAddress`), `/payment-source`, `/payment-source-extended`, `/api-key`, `/utxos`, `/signature/sign` and `/signature/verify`, `/webhooks`, `/invoice`, `/swap`, `/x402`, `/hydra`.
- `POST /payment` fields: `inputHash`, `network`, `agentIdentifier` (57–250 chars), `paymentSourceType`, `supportedPaymentSourceIndex` (**required for V2**, forbidden for V1), `RequestedFunds[]` (≤7 items; null for fixed pricing), `payByTime`, `submitResultTime`, `unlockTime?`, `externalDisputeUnlockTime?`, `metadata?`, `sellerReturnAddress?`, `identifierFromPurchaser` (hex, 14–26 chars), and `forceLayer?` (`L1` or `Hydra`; signed into V2 terms).
- Registry entry `type`: `Standard` | `OpenApi` | `X402` | `A2A`. Pricing types: `Fixed` | `Dynamic` | `Free`. V2 cross-listing rule: a V2 entry may only advertise V2 sources. A V1 entry may advertise V2 sources as a migration breadcrumb.
- Payment source types: `Web3CardanoV2` is canonical. `Web3CardanoV1` is legacy but still supported, with no removal date.
- Seeding: `prisma:seed` creates the payment source, the admin key, and purchasing and selling wallets. It **prints mnemonics**, so suppress its output. `ENCRYPTION_KEY` must stay with the DB, or the saved wallets can no longer be decrypted.

## MIP-003 Agentic Service API (what a "Standard" agent must serve)
| Endpoint | Purpose |
|---|---|
| `GET /availability` | Returns `{status:"available"|"unavailable", type:"masumi-agent", message?}` |
| `GET /input_schema` | Returns `{input_data:[fields]}` or `{input_groups:[{title, input_data}]}` |
| `POST /start_job` | Body `{identifier_from_purchaser, input_data}`. Returns `{id (job), blockchainIdentifier, payByTime, submitResultTime, unlockTime, externalDisputeUnlockTime, agentIdentifier, sellerVKey, input_hash}`. V2 also returns `supportedPaymentSourceIndex` and `paymentSourceType`. |
| `GET /status?job_id=` | Returns status `awaiting_payment`, `awaiting_input`, `running`, `completed`, or `failed`, plus `result` (a string) and `input_schema` when awaiting input |
| `POST /provide_input` | Body `{job_id, input_schema_hash, input_data}`. Returns `{input_hash, signature (Ed25519)}`. |
| `GET /demo` | Returns `{input, output}` for marketing |

The minimal reference is the demo `agent-api.mjs`. It validates the nonce `^[a-fA-F0-9]{14,26}$`, persists the job before any MPS write, returns 409 on nonce reuse with different input, and runs the model only after a confirmed `FundsLocked` with ≥2 min left before `submitResultTime`.

### Input schema (MIP-003 Attachment 01)
Fields have `{id, type, name, data?, validations?}`. Every field is required unless it has `{"validation":"optional"}`. Types: `text`, `textarea`, `number`, `boolean`, `email`, `password`, `tel`, `url`, `date`, `datetime-local`, `time`, `month`, `week`, `color`, `range`, `file` (`outputFormat:"url"`, so the buyer uploads and passes a URL), `hidden`, `search`, `checkbox`, `radio`, `option` (`data.values`), `none` (display only). Validations: `min`, `max`, `format` (`email`, `url`, `nonempty`, `integer`, `tel-pattern`), `optional`, `accept`. Treat all inputs as untrusted.

## MIP-004 hashing
- Input: `sha256_utf8( identifier_from_purchaser + ";" + JCS_RFC8785(input_data) )`, as lowercase hex.
- Output: `sha256_utf8( identifier_from_purchaser + ";" + raw_output_string )`, with no canonicalization.
- `provide_input` schema hash: SHA-256 of canonical JSON (sorted keys, no whitespace).
- **Sokosumi direct Task payments use plain `sha256(utf8 text)`**, not MIP-004 (per the demo README and code). Verify against the live route.

## Registry metadata (MIP-002) and identity
- Each agent is an NFT. `agentIdentifier` = policyId + assetName. V1 updates needed deregister (burn) and re-register (new identifier).
- Legacy metadata JSON used arrays of strings (`name:["…"]`, `api_url`, `capability{name,version}`, `requests_per_hour`, `author{name,contact,organization}`, `tags`, `pricing[{quantity,unit}]`, `metadata_version:1`). The current MPS API takes structured fields (`Capability`, `Author`, `Legal`, `ExampleOutputs`, `Tags`, `supportedPaymentSources`) and optional KERI-ACDC `verifications`.

## x402 vs escrow
| | x402 | MIP-003 escrow |
|---|---|---|
| Finality | Immediate, no refunds | Locked, refundable |
| Decision logging | No | Yes |
| Disputes | No | On-chain window |
| Use for | Cheap, high-frequency metered calls | Work that needs delivery guarantees |

x402 on Cardano uses the "exact" scheme (~20 s settlement). `assetTransferMethod:"masumi"` routes it through escrow instead. MPS also has a separate **EVM x402 rail** (Permit2, CAIP-2 `eip155:*` networks, managed EVM wallets). Do not confuse it with the older Cardano `/payment/x402` route.

## Operational lessons
- Health OK ≠ payments OK. Run a real `/payment` query after every upgrade. After `git pull`, run `pnpm install`, `prisma:generate`, `prisma:migrate`, and rebuild (the demo hit a missing-column error).
- Persist IDs, signed terms, and exact result bytes **before** each external write. On an uncertain outcome, inspect state (`resolve-blockchain-identifier`, `GET /registry`) before retrying. Never reseed to fix wallets.
- `RegistrationFailed: UTxO Fully Depleted` means the wallet has no free UTxOs. Wait for pending transactions, or fund it more.
- One DB per wallet set. Never run two DB copies against the same wallets.
