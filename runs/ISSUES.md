# Issues found and fixed during the final end-to-end test (2026-10-07)

Each entry: what happened, the evidence, the fix and where it landed. Times are UTC.

## 1. Nora's Dynamic payment never purchased (claim stuck PENDING)
- **Seen:** Nora Task `01a1143b…` (02:54): Sokosumi debited 6.0 credits and created the claim, but its buyer never
  purchased; `GET /v1/tasks/{id}/receipt` → `claimStatus: PENDING`; the escrow never locked.
- **Cause:** Nora was registered on Masumi as an `OpenApi` agent (no `api_base_url`). Sokosumi's buying payment node
  resolves the agent's on-chain metadata before purchasing and does not handle the OpenApi entry type (its generated
  MPS client has no OpenApi registry type). The 12 Standard specialists purchased normally.
- **Fix:** Nora re-registered as a **Standard** agent with Dynamic pricing; her agent API is `/agents/nora` on the
  Worker (MIP-003 shape, `/availability` for the registry health check). Verified: the next Nora Task's claim went
  `PENDING → PURCHASED → FundsLocked → ResultSubmitted`. Commits `aaca758`, registration confirmed 03:13.
- **Also:** a Task whose escrow is not locked by its pay-by deadline now fails cleanly ("nothing was published or
  delivered") instead of waiting forever.

## 2. Bedrock API key expired mid-test
- **Seen:** 03:13 — every model call returned `401 Bearer Token has expired`; Nora could not plan.
- **Fix:** new key set on Railway (`kodosumi`, `worker`, CRE secret) and in local `.env` files; services restarted.
  The key is short-lived (expires ~15:20 UTC).

## 3. Chainlink crashed on Leo's comparison table (FAIL 0/100 in Nora runs)
- **Seen:** Nora Task `01a11467…` — Leo FAIL 0/100 twice; local CRE simulation: `TypeError: not a function`.
- **Cause:** Leo cites comparison evidence as a `{domain: url}` map; the profile called `.some()` on it as an array.
  Standalone Leo runs (FAQ, email, social) never include a comparison, so only Nora's runs hit it.
- **Fix:** the check reads `Object.values(evidence)`. Commit `b411bc5`. Leo was not billed in that run.

## 4. Kai's brand gate flagged the material "borosilicate"
- **Seen:** Kai FAIL in Nora Task `01a1143b…`; the brand "Borosil" matched inside "borosilicate".
- **Fix:** brand terms and forbidden words match whole words. Commit `56bb090` (with the pass-mark calibration).

## 5. Kodosumi accepted a launch whose run never started
- **Seen:** Leo standalone Task `01a11429…` stuck after payment; the run id was unknown to Kodosumi and status calls
  hung (later 502).
- **Fix:** status calls time out after 15 s; a run still unknown 90 s after launch is relaunched (standalone up to
  twice; Nora's nodes through their retry). Verified: Leo relaunched, passed 90/100 and published.

## 6. Nora asked to approve "0 changes"; Ruth skipped on review-only requests
- **Fix:** Ruth always runs when planned (live listing when nothing changes); no empty approval step; delivery waits
  for the escrow lock. Commit `cc1c342`.

## 7. Coworker listings: long names, no avatars
- **Seen:** names repeated the role already shown as the caption; Core rejected `company` and `image` on
  `PATCH /v1/coworkers/{id}` ("Unrecognized keys"), although the CLI offers both flags.
- **Fix:** names are first names (`registry_name` keeps the on-chain Masumi name); avatars uploaded as files to
  `POST /v1/coworkers/{id}/image` with the signed-in CLI session (`infra/sokosumi/upload_avatars.mjs`). Commits
  `5837505`, `b226850`.

## 8. Marcus reused a discount code that already exists in the store
- **Seen:** Marcus Task `01a11475…` proposed `SINGLES11`, already used by the bamboo bottle's promotion (Shopify codes
  are unique per store, so publishing would fail). Declined as the merchant.
- **Fix:** Marcus reads the store's existing codes, tells the model to avoid them and makes any remaining collision
  unique (`SINGLES11` → `SINGLES112`).

## 9. Oskar put the tumbler into the "Bamboo Bottles" collection; the approval showed only an id
- **Seen:** Oskar Task `01a1147d-df75…` proposed "collections: add to 333623328929" (= "Bamboo Bottles"): the tumbler
  shares a bamboo lid, not a product type. Declined as the merchant.
- **Fix:** Oskar only picks collections of the same kind of product and may return none; approval messages name
  collections (and categories) instead of showing their ids.

## 10. Observation (not changed): generated scenes can show third-party marks
- Iris's car cup-holder scene for the tumbler shows a car maker's emblem on the steering wheel. The product itself is
  faithful (fidelity 1.0). Worth a prompt note ("no logos or brand marks in the scene") in a later pass.
