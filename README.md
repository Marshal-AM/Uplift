# Uplift

A verified multi-agent e-commerce growth and ads team, listed on Sokosumi. The product is specified in [`../docs/uplift/`](../docs/uplift/).

## Build decisions

| Concern | Choice | Why |
|---|---|---|
| Python services and agents | Python 3.12, `uv` workspace | Kodosumi is Python-first and tested on 3.12 / Ray 2.48 |
| CRE workflow | TypeScript, `@chainlink/cre-sdk` 1.23, Bun | Official SDK path |
| HTTP services | FastAPI + uvicorn | Kodosumi's `ServeAPI` is FastAPI; same stack everywhere |
| Database access | `psycopg` 3 + plain SQL migrations | Small schemas; no ORM needed |
| Token encryption | AWS KMS `GenerateDataKey` + AES-GCM (`cryptography`) | Envelope encryption as specified |
| LLM | Amazon Bedrock Converse, `global.anthropic.claude-sonnet-5-5` | Single model (CRE judge uses a Bedrock API key) |
| Canonical JSON | RFC 8785 JCS: `rfc8785` (Python), `canonicalize` (TS) | Same `resultHash` / `change_hash` on both sides (`e2e/cre_parity.py`) |
| Shopify | Admin GraphQL `2026-10`; app config via Shopify CLI (`shopify.app.toml`) | Official tooling |
| Hosting | Railway: Postgres, gateway, worker, Kodosumi (Ray in one container, `/data` volume), MPS | Railway CLI per requirement |

## Repo layout

```
uplift/
  packages/core/        uplift_core: JCS hashing, changeset ownership, Listing Score, rules engine, Bedrock client
  services/gateway/     Connection Gateway: Shopify OAuth, KMS-encrypted token store, read API, CRE-only write API
  services/worker/      Worker: one executor per coworker, specialist Task runner, Nora orchestration,
                        Responses-API chat, CRE trigger + result callback, Masumi paid-Task flow
  agents/               Kodosumi ServeAPI: 12 specialist flows (one module each) + shared tools/runtime
  cre/uplift-clearing/  CRE workflow `uplift-clearing`: verify (role profiles + Bedrock judge, refunds) and publish
                        (approval check, op provenance/ownership, gateway write, after-score); src/core.ts mirrors
                        packages/core
  rules/                uplift-rules.json, shared by Ruth/Quinn (Python) and CRE (TS)
  infra/kodosumi/       Kodosumi container (Ray head + panel + boot of the `uplift` Expose)
  infra/sokosumi/       Coworker listings and idempotent registration (keys → infra/.secrets, Railway, cre/.env)
  infra/mps/            Pinned masumi-payment-service deploy (patched to migrate + seed on start)
  infra/masumi/         Masumi registry: 12 flows via the Kodosumi panel, Nora via the MPS (Fixed tUSDM)
  infra/shopify-app/    shopify.app.toml (Shopify CLI)
  e2e/                  End-to-end checks run against real services
```

## Runbook

```sh
uv sync --all-packages && (cd cre/uplift-clearing && bun install)

# Gateway (deployed): connect a store, then exercise read/write/idempotency/revert
railway run --service gateway -- uv run python e2e/gateway_e2e.py connect   # open the printed link
railway run --service gateway -- uv run python e2e/gateway_e2e.py verify

# CRE ↔ Python lockstep (hashes, rule hits, Listing Score)
uv run python e2e/cre_parity.py

# Kodosumi locally (Ray on 6380 to keep 6379 free)
uv run ray start --head --port 6380 && KODO_RAY_SERVER=localhost:6380 uv run koco start &
uv run python infra/kodosumi/boot.py
# …or the production container
docker build -f infra/kodosumi/Dockerfile -t uplift-kodosumi . && docker run -p 3370:3370 uplift-kodosumi

# Coworkers (after `sokosumi --preprod auth login`)
uv run python infra/sokosumi/register.py --worker-url https://<worker> --push

# Payment node and Masumi registration (selling wallet must hold test ADA)
sh infra/mps/deploy.sh
uv run python infra/masumi/register.py --publish

# CRE workflow (after `cre login`); the Worker runs this itself when CRE_TRIGGER_URL is unset
cd cre && cre workflow simulate uplift-clearing --non-interactive --trigger-index 0 \
  --http-payload '<json>' --target local-simulation
```

Secrets never live in the repo: services read Railway variables, the CRE simulator reads `cre/.env`
(deployed workflows read the Vault DON), coworker keys are captured once into `infra/.secrets/` (0600).
