# Kodosumi — Runtime Guide and Agent-Workflow Patterns

Researched 2026-10-06. Sources: docs.kodosumi.io (`llms.txt` full dump, generated 2026-10-06) and the repo `masumi-network/kodosumi` at commit `c4f2032` (v1.2.0, 2026-09-15). The repo's `docs/*.mdx` files are **newer** than the public guides: they cover Expose, Boot, Sumi, and the Masumi registry.

## What it is
A Python-first runtime for "agentic services" on **Ray + Ray Serve**, with a Litestar admin **Panel** (port 3370), a **Spooler** that persists event streams (SQLite per job), and detached **Runner** actors. You write a Flow; Kodosumi handles launching, monitoring, scaling, HITL, files, and (in v1.2) MIP-003 exposure and Masumi payments.

It is not required for the TOKEN2049 Coworker path. It is the natural choice when you want a **Python, multi-step, parallel, or HITL** agent that is also sold as a Masumi/Sokosumi agent.

## Core concepts
| Term | Meaning |
|---|---|
| **Flow** | The automated process (Kodosumi's preferred word for "agent") |
| **Agentic Service** | A deployable unit = endpoints + entrypoints + flows |
| **Endpoint** | An HTTP route declared with `@app.enter(...)`. Adds the OpenAPI extension `x-kodosumi`. |
| **Entrypoint** | The Python callable launched by `Launch(request, "pkg.mod:fn", inputs=...)`. Signature: `async def fn(inputs: dict, tracer: Tracer)`. |
| **ServeAPI** | Kodosumi's FastAPI wrapper (`from kodosumi.core import ServeAPI`) |
| **Forms** | `kodosumi.core.forms as F`: `Model`, `InputText`, `InputArea`, `InputNumber`, `InputDate`, `InputTime`, `InputDateTime`, `InputPassword`, `Checkbox`, `Select`/`InputOption`, `InputFiles`, `Markdown`, `HTML`, `Break`, `Submit`, `Cancel`, `Action` |
| **InputsError** | Raised in the endpoint for field-level validation: `error.add(field="msg")` |
| **Tracer** | Emits events: `debug`, `result`, `action`, `markdown`, `html`, `text` (each with a `_sync` twin), `lock(...)`, `fs()` / `fs_sync()` |
| **Runner / Spooler / Event stream** | Execution actor / persistence daemon / events `meta`, `inputs`, `agent`, `status`, `stdout`, `stderr`, `debug`, `action`, `result`, `final`, `error`, `upload`, `lock`, `lease`, `eof` |
| **Lifecycle** | `starting → running → (awaiting ⇄ running) → finished | error` |
| **Lock / Lease** | HITL: `await tracer.lock("id", data=…, timeout=…)` pauses (default timeout 3 h). `@app.lock("id")` returns the form shown to the human. `@app.lease("id")` validates input and returns the value to the flow. |
| **Files** | `/in` holds user uploads and `/out` holds deliverables. Use `AsyncFileSystem` in async code and `SyncFileSystem` inside `@ray.remote` functions. |

## Minimal service skeleton
```python
import fastapi, ray
from ray import serve
from kodosumi.core import ServeAPI, Launch, Tracer, InputsError, forms as F

app = ServeAPI()
model = F.Model(F.Markdown("# Brief"), F.InputArea(label="Brief", name="brief"),
                F.Submit("Run"), F.Cancel("Cancel"))

@app.enter(path="/", model=model, summary="My Flow", description="…",
           tags=["demo"], version="1.0.0", author="me@example.com")
async def enter(request: fastapi.Request, inputs: dict):
    if not inputs.get("brief", "").strip():
        raise InputsError(brief="Required")
    return Launch(request, "my_pkg.flow:run", inputs=inputs)

async def run(inputs: dict, tracer: Tracer):
    await tracer.markdown("Working…")
    return {"answer": "..."}            # becomes the `final` event

@serve.deployment
@serve.ingress(app)
class Svc: pass
fast_app = Svc.bind()
```
Run options:
- Debug: `uvicorn my_pkg.flow:app --port 8011`, then `koco start --register http://localhost:8011/openapi.json`.
- Ray: `serve run my_pkg.flow:fast_app` (routes at `:8000/-/routes`).
- Production: Expose/Boot, or `koco deploy -f ./data/config/config.yaml --run`.

Installation is tested with `ray==2.48.0` and Python 3.12.6. Install with `pip install kodosumi`, or start from `kodosumi-examples` (hymn, prime, throughput, form).

## Deployment
- **koco CLI**:
  - `koco start` runs the spooler and the panel together. `koco spool [--status|--stop|--block]` and `koco serve [--register URL] [--reload]` run them separately.
  - `koco deploy -f config.yaml [--dry-run|--run|--status|--stop]`.
- **Ray Serve YAML split**: a base `./data/config/config.yaml` (proxy, http port, logging) plus one app YAML per service (`name`, `route_prefix`, `import_path`, `runtime_env{pip, py_modules (pinned GitHub commit zip), env_vars}`, `deployments[{name, num_replicas, ray_actor_options{num_cpus}}]`).
- **Expose / Boot / Exchange (v1.2, preferred)**: in the panel, go to Control > Expose. Each expose item has `name`, `display`, `network` (`Preprod`/`Mainnet`), `enabled`, a `bootstrap` YAML, and an auto-filled `meta`. **Boot** runs: deploy → health check (polls every 2 s, up to 30 min) → register flows that have `x-kodosumi` → HEAD-check endpoints → update meta. States: `DRAFT`, `DEAD`, `DEPLOYING`, `RUNNING`, `UNHEALTHY`, `DEPLOY_FAILED`. Exchange exports and imports JSON backups. API: `/expose`, `/boot`, `/exchange/*`.
- Config uses `KODO_*` environment variables: `EXEC_DIR`, `RAY_SERVER` (localhost:6379), `APP_SERVER` (:3370), `ADMIN_DATABASE` (sqlite), `ADMIN_EMAIL`, `ADMIN_PASSWORD` (default *admin*; **change it**), `SECRET_KEY`, `CORS_ORIGINS`, `WAIT_FOR_JOB` (600), `PROXY_TIMEOUT` (30), and spooler tuning.
- Panel API: `POST /login` or `/api/login` (returns `KODOSUMI_API_KEY` and cookies), `GET /flow`, launch with `POST /-/host/port/-/path`, stream with `GET /outputs/stream/{fid}`, status with `GET /outputs/status/{fid}`, and locks with `GET`/`POST /lock/{fid}/{lid}`.

## Masumi / Sokosumi integration built into Kodosumi 1.2
- **Sumi API** (MIP-002/MIP-003): every exposed flow gets `/sumi/{expose}[/{meta}]/availability`, `/input_schema`, `/start_job`, `/status/{job_id}`, and `/provide_input`, plus discovery at `GET /sumi`. Kodosumi forms are translated into MIP-003 input fields. **HITL locks surface as `awaiting_input`**, and `provide_input` releases them. The result is always a string.
- **Payment config**: `KODO_MASUMI0="Preprod <MPS base url> <api key> [pay_by_s=1200] [submit_by_s=3600] [poll_s=1.0]"`, with up to `MASUMI9` for multiple networks. Set the expose `network` to match. Set `KODO_SUMI_ADDRESS` to the public URL.
- In the per-endpoint meta YAML, adding `agentIdentifier` turns on payment: the Runner creates the Masumi payment after `start_job`, waits for funds, and then runs. Without it, the flow runs free.
- **Registry from the panel**: `POST /expose/{name}/registry` with `{flow_url, wallet_vkey, pricing_type, amount, currency:"USDM"}`, then `/registry/poll` and `/registry/deregister`, and `GET /expose/{name}/wallets`. The dropdown labels wallets `[V1]`/`[V2]`. A V2 registration writes `agentIdentifier`, `registrationId`, `paymentSourceType: Web3CardanoV2`, and `supportedPaymentSourceIndex: 0` into the meta YAML.
- **V1→V2 migration**: the "Migrate to V2" button mints a new identifier. V1 keeps serving until the mint confirms. **Leave the V2 selling wallet's collection address empty.**
- Payment dashboard: revenue and failure analysis.

## How to build *proper* agent workflows with Kodosumi (guidelines)
1. **Endpoint vs entrypoint discipline.** The endpoint only parses, validates (`InputsError`), and `Launch`es, and it must return fast. All slow work belongs in the entrypoint, which runs as a detached Runner.
2. **Fan out with Ray.** Decorate units of work with `@ray.remote`. Gather results with `ray.wait(..., num_returns=1, timeout=1)` so you can stream partial results through `tracer.markdown/result` while the rest is in flight. Inside a remote function, use the `_sync` tracer methods and `fs_sync`.
3. **Stream intermediate results.** Use `result`/`markdown` for progress, `action` for tool outputs, and `debug` for logs. Return a single structured `final`. The Sokosumi/Masumi-facing result is the stringified final, so make it deliverable-quality.
4. **Human-in-the-loop by design.** Put approvals and clarifications behind `tracer.lock()` with explicit timeouts. Validate in `@app.lease` and raise `InputsError` to keep the lock open. This maps to MIP-003 `awaiting_input`/`provide_input` and to Sokosumi Job `inputRequest`.
5. **Files over blobs.** Accept uploads via `InputFiles` (`/in`). Write deliverables (PDF, CSV, decks) to `/out`. This matches Sokosumi's "files, not chat logs".
6. **Reproducible deploys.** Pin `py_modules` to commit zips and pin pip dependencies in `runtime_env`. Keep secrets in `env_vars` injected at deploy time, never in the repo. Size `num_cpus` and replicas, and cap concurrency to avoid out-of-memory failures (Ray "limit running tasks" pattern).
7. **Metadata is your listing.** `summary`, `description`, `tags`, `version` (semver), `author`, and `organization` on `@app.enter` feed the panel, MIP-002 metadata, and the Sokosumi gallery.
8. **Paid flows**: set `KODO_MASUMI*`, register a V2 USDM price from the panel, and confirm `RegistrationConfirmed` before advertising. Test `start_job → awaiting_payment → running → completed` end-to-end on Preprod.
9. **Ops**: change the admin password and `SECRET_KEY`, restrict `CORS_ORIGINS`, back up with Exchange export, and use expose health checks (`app_running`, `endpoint_alive`, `fields_match`).

## Coworker vs Kodosumi: when to use which [inferred]
- **Sokosumi Coworker + worker** (any runtime): fastest path into Sokosumi task boards and the TOKEN2049 flow. No public URL needed.
- **Kodosumi flow as a Masumi Agent**: you get public MIP-003 endpoints, Ray scale, HITL, files, and built-in payments. This is good for heavier Python pipelines (CrewAI/LangGraph) and agent-to-agent sales.
- **Combined**: a Coworker worker can call a Kodosumi flow, either via the panel API or via its `/sumi` endpoints, as its "agent".

## masumi-skills
Install with `npx skills add https://github.com/masumi-network/masumi-skills --skill masumi`. It is a progressive-disclosure skill with references for kodosumi-runtime, agentic-services (MIP-003), masumi-payments, registry-identity, sokosumi-marketplace, smart-contracts, cardano-blockchain, and API debug recipes. Its last commit is 2026-07-13, so it is older than the CLI 1.0.4 flow.
