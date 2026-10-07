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

## 11. Nora planned the whole team for a content-and-compliance request
- **Seen:** Nora Task (final run, glass bottle) asked for "an FAQ, a comparison, a blog article, plus a compliance
  check"; Nora planned all 11 specialists (ceiling 16.0 credits) instead of Leo and Ruth (plus Quinn). The plan was
  approved before review, so the run went ahead as a complete all-specialist Nora flow.
- **Cause:** the planner switches to the full flow when the request names many capabilities.
- **Fix:** the planner chooses only the capabilities whose deliverables were asked for; `full_flow` only for launch /
  overhaul / full optimization requests (the "6+ capabilities means everyone" shortcut is removed).

## 12. Observation (not changed): Clara's title in the final Nora run
- Clara's proposed title "Reusable Glass Water Bottles 550 Ml Borosilicate Glass" leads with a plural keyword and
  Title Case turned "ml" into "Ml". It passed Chainlink (76.5) and was approved so the full flow could complete;
  worth a follow-up so units keep their case and the title names the single product.

## 13. Operator error: a duplicate wave B was launched (declined, nothing published)
- **Seen:** a chained test command kept going after a failed `git pull --rebase` and, once its deploy wait timed
  out, created a second set of wave B Tasks (Clara, Iris, Oskar, Leo, Marcus — `01a11492-…`, 9.25 credits).
- **Handled:** all five were declined at their approval step, so no duplicate changes reached the store; no result
  was submitted for them, so their escrow returns to the buyer after the deadline. Recorded under
  `tumbler/duplicates/`.
- **Lesson:** test chains stop on the first failed step (`set -e`), and Task launches check for an open Task with the
  same brief first.
