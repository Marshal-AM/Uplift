# References (checked 2026-10-06)

## Sokosumi
- Product: https://www.sokosumi.com/ · App: https://app.sokosumi.com · **Preprod**: https://preprod.sokosumi.com (signup `/signup`, billing `/billing?tab=credits`, legacy gallery `/agents`)
- API: mainnet `https://api.sokosumi.com/v1` · preprod `https://api.preprod.sokosumi.com/v1` · public OpenAPI `GET /v1/openapi`
- Dev docs hub: https://www.masumi.network/dev/sokosumi/documentation
  - Coworkers: https://www.masumi.network/dev/sokosumi/documentation/coworkers
  - CLI docs (stale on package name): https://www.masumi.network/dev/sokosumi/cli_docs
  - API reference: https://www.masumi.network/dev/sokosumi/api-reference
  - MCP: https://www.masumi.network/dev/sokosumi/mcp
  - Other pages: `/projects`, `/history`, `/organization`, `/pysokosumi`, `/hermes`, `/image-generation`
- CLI on npm: `@masumi_network/sokosumi` (v1.0.4, modified 2026-10-05). Source: https://github.com/masumi-network/sokosumi/tree/main/apps/cli
- Skills: `npx skills add https://github.com/masumi-network/sokosumi --full-depth --skill sokosumi` (also `coworker`, `tasks`, `jobs`, `agents`, `watch`)
- Mainnet listing form (legacy agents): https://tally.so/r/nPLBaV

## Masumi
- Docs: https://www.masumi.network/dev/masumi/documentation
  - Install node: `/dev/masumi/documentation/get-started/install-masumi-node`
  - Register agent: `/dev/masumi/documentation/get-started/register-agent`
  - List on Sokosumi: `/dev/masumi/documentation/how-to-guides/list-agent-on-sokosumi`
  - Other how-tos: `/how-to-guides/top-up-your-wallets`, `/hosting-guide`, `/human-in-the-loop`, `/how-to-enable-agent-collaboration`
  - Agentic Service API: `/technical-documentation/agentic-service-api`
  - Technical docs: `/technical-documentation/registry-metadata-standard`, `/agent-identity-nft`, `/environment-variables`
- Core concepts: https://www.masumi.network/dev/masumi/core-concepts (payments, refunds-and-disputes, registry, x402, wallets, tokens, smart-contracts, decision-logging, …)
- MIPs: https://www.masumi.network/dev/masumi/mips (`_mip-002`, `_mip-003`, `_mip-003-attachment-01`, `_mip-004`)
- Skill entry: https://www.masumi.network/skill.md · Agent explorer: https://www.masumi.network/agent-explorer
- Faucet (test ADA/tUSDM): https://dispenser.masumi.network
- Cardano x402: https://developers.cardano.org/x402/
- Blockfrost (Preprod project key): https://blockfrost.io/

## Repos (commit read)
| Repo | Commit / date | Notes |
|---|---|---|
| https://github.com/masumi-network/masumi-payment-service | `71455701` · 2026-10-05 | `README.md`, `CONTEXT.md` (glossary), `docs/configuration.md`, `docs/deployment.md`, `docs/x402.md`, `docs/adr/*`, `src/routes/api/{registry,payments,purchases}` |
| https://github.com/masumi-network/demo-agent-token2049 | branch `live-demo-name-finder` · 2026-10-06 | Reference eve agent, worker, paid adapter, MIP-003 API, registration script. Branch `feat/token2049-event-guide` is the earlier reference. |
| https://github.com/masumi-network/kodosumi | `c4f2032` · v1.2.0 · 2026-09-15 | `docs/expose.mdx`, `docs/sumi-api.mdx`, `docs/masumi-registry.mdx` are newer than the public guides |
| https://github.com/masumi-network/kodosumi-examples | — | hymn, prime, throughput, form |
| https://github.com/masumi-network/masumi-skills | `3eabe4a` · 2026-07-13 | `skill/references/*.md` (somewhat stale) |
| https://github.com/masumi-network/masumi-services-dev-quickstart | — | docker compose: registry :3000, payment :3001, postgres :5432 |

## Kodosumi
- Guides: https://docs.kodosumi.io/guides. Any page is available as markdown by appending `.md`. Full dump: https://docs.kodosumi.io/llms.txt
- Key pages: `/guides/concepts`, `/installation`, `/develop`, `/deploy`, `/config`, `/forms`, `/lifecycle`, `/locks`, `/files`, `/files-api`, `/timeline`, `/meta`, `/panel`, `/masumi-skills`, `/cli` (koco)

## Agent runtime (TOKEN2049 default)
- Vercel eve: https://github.com/vercel/eve (getting-started, client overview, deployment/vercel)
- Z.ai GLM-5.3-Flash: https://docs.z.ai/guides/vlm/glm-5.3-flash · pricing: https://docs.z.ai/guides/overview/pricing
- Railway (worker/MPS/Postgres hosting): https://docs.railway.com/services

## TOKEN2049 event
- Join: https://preprod.sokosumi.com/join/9Ycw8wzmzXB2WEKa-umzUJX6_GEFiVdu · org ID `01a109d1-32a9-71a3-a0e3-658b2a7987cd` · slug `token2049-origins-hackathon-2026-nws2r7`
- Submission checklist: https://www.masumi.network/token2049/submission · BuilderBase: https://builderbase.com/event/token2049-origins-hackathon

## Local scratch copies
Read-only clones and the `npm pack` of the CLI were placed in the session scratchpad, which is ephemeral and not kept. Re-fetch with `git clone --depth 1 …` / `npm pack @masumi_network/sokosumi` when needed.
