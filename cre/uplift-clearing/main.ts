// uplift-clearing — one HTTP-triggered workflow with two actions:
//   verify:  hash-check a deliverable, score it with its role profile (+ one Bedrock judge), refund a failed Job
//   publish: confirm the merchant approved this exact change set, check every op's provenance and ownership,
//            execute it through the gateway's write API (whose key only this workflow holds), re-score the listing
// Results go back to the Uplift Worker callback.
import { decodeJson, handler, HTTPCapability, type HTTPPayload, Runner, type Runtime } from "@chainlink/cre-sdk"
import { ownersOf, score } from "./src/core"
import {
  call, callback, canonical, type Config, fetchVerified, gateway, type Json, judge, onNodes, sha256Hex, soko, taskEvents,
} from "./src/lib"
import { type Check, type Local, PROFILES } from "./src/profiles"

const APPROVE = /^\s*(approve|approved|yes|go|ship it|lgtm)\b/i

// --- verify ---------------------------------------------------------------------------------------

function planRoles(events: Json[], approvalEventId: string): string[] | null {
  const idx = events.findIndex((e) => e.id === approvalEventId)
  if (idx < 0 || events[idx].actor?.type !== "user") return null
  const quote = events.slice(0, idx).reverse().find((e) => e.status === "APPROVAL_REQUIRED" && /```json/.test(e.comment ?? ""))
  const m = quote?.comment.match(/```json\s*([\s\S]*?)```/)
  return m ? JSON.parse(m[1]).agents.map((a: Json) => a.role) : null
}

function verify(runtime: Runtime<Config>, req: Json): Json {
  const profile = PROFILES[req.role]
  if (!profile) throw new Error(`no profile for ${req.role}`)
  const now = runtime.now().getTime()

  const local = onNodes(runtime, (n): Local & { error?: string } => {
    try {
      const manifest = JSON.parse(fetchVerified(n, req.manifest_url, req.result_hash))
      if (manifest.role !== req.role) return { checks: [], probes: {}, judge: { question: "", material: "" }, error: "manifest role mismatch" }
      const bundle = JSON.parse(fetchVerified(n, manifest.verification_bundle.url, manifest.verification_bundle.sha256))
      const out = profile.local(manifest, bundle, now)
      const unowned = (manifest.changeset ?? []).some((op: Json) => ownersOf(op).has("?"))
      return unowned ? { ...out, error: "changeset touches unsupported fields" } : out
    } catch (e) {
      return { checks: [], probes: {}, judge: { question: "", material: "" }, error: String(e).slice(0, 200) }
    }
  })
  if (local.error) return { outcome: "FAIL", score: 0, reasons: [local.error], checks: [] }

  if (req.mode === "job") {
    const job = soko(runtime, "nora", `/v1/jobs/${req.job_id}`)
    if (job.taskId !== req.task_id || !job.result || sha256Hex(job.result) !== req.result_hash)
      return { outcome: "FAIL", score: 0, reasons: ["Job result does not match the delivered manifest"], checks: [] }
  }
  if (req.plan_approval_event_id) {  // work done for Nora must be part of the plan the merchant approved
    const roles = planRoles(taskEvents(runtime, "nora", req.task_id), req.plan_approval_event_id)
    if (!roles?.includes(req.role)) {
      const outside = { outcome: "FAIL", score: 0, reasons: ["Work is outside the approved plan"], checks: [] }
      return req.mode === "job" ? refundAnd(runtime, req, outside) : outside
    }
  }

  const checks: Check[] = [...local.checks, ...(profile.remote?.(runtime, local.probes) ?? [])]
  const verdict = judge(runtime, local.judge.question, local.judge.material)
  checks.push({ name: "Judge", points: verdict.points, max: 5 })
  const total = Math.round(checks.reduce((a, c) => a + c.points, 0) * 10) / 10
  const gates = checks.filter((c) => c.gate).map((c) => `${c.name} (required)`)
  const outcome = gates.length === 0 && total >= profile.pass ? "PASS" : "FAIL"
  const reasons = [...gates, ...checks.filter((c) => c.max && c.points < c.max * 0.5).map((c) => `${c.name}: ${c.points}/${c.max}`)]
  const result = { outcome, score: total, pass_mark: profile.pass, reasons, checks, judge_note: verdict.note }
  return outcome === "FAIL" && req.mode === "job" ? refundAnd(runtime, req, result) : result
}

function refundAnd(runtime: Runtime<Config>, req: Json, result: Json): Json {
  try {
    soko(runtime, "nora", `/v1/jobs/${req.job_id}/refund`, { method: "POST", body: {}, as: [req.user_id, req.org_id] })
    return { ...result, refunded: true }
  } catch (e) {
    runtime.log(`refund failed: ${String(e).slice(0, 200)}`)
    return { ...result, refunded: false }
  }
}

// --- publish --------------------------------------------------------------------------------------

function approvalProblem(events: Json[], req: Json): string | null {
  const idx = events.findIndex((e) => e.id === req.approval_event_id)
  if (idx < 0) return "approval event not found"
  const e = events[idx]
  if (e.actor?.type !== "user" || e.actor.id !== req.user_id) return "approval was not given by the task owner"
  if (!(["READY", "RUNNING"].includes(e.status) || APPROVE.test(e.comment ?? ""))) return "event is not an approval"
  const ask = events.slice(0, idx).reverse().find((x) => x.status === "APPROVAL_REQUIRED")
  if (!ask?.comment?.includes(req.change_hash.slice(0, 16))) return "approval does not refer to this change set"
  return null
}

function publish(runtime: Runtime<Config>, req: Json): Json {
  const problem = approvalProblem(taskEvents(runtime, req.coworker, req.task_id), req)
  if (problem) return { published: false, reason: problem }

  const raw = call(runtime, req.changeset_url)
  if (raw.status !== 200 || sha256Hex(raw.body) !== req.change_hash) return { published: false, reason: "change set does not match its hash" }
  const changeset: Json[] = JSON.parse(raw.body)
  if (canonical(changeset) !== raw.body) return { published: false, reason: "change set is not canonical" }

  // provenance: every op must come verbatim from a verified deliverable of the role that owns it
  const sources = onNodes(runtime, (n) => (req.manifests as Json[]).map((ref) => {
    const m = JSON.parse(fetchVerified(n, ref.url, ref.hash))
    return { role: m.role as string, ops: (m.changeset ?? []).map((op: Json) => sha256Hex(canonical(op))) as string[] }
  }))
  for (const op of changeset) {
    const h = sha256Hex(canonical(op))
    const owners = [...ownersOf(op)]
    const ok = sources.some((s) => s.ops.includes(h) && owners.every((o) => o === s.role))
    if (!ok) return { published: false, reason: `op ${op.op} has no owning deliverable` }
  }

  const applied = gateway(runtime, "/v1/write/apply",
    { user_id: req.user_id, org_id: req.org_id, change_hash: req.change_hash, changeset }, true)
  if (applied.status === 409) return { published: false, reason: "store_reauth_required" }
  if (applied.status >= 400) return { published: false, reason: `store write failed (${applied.status}): ${applied.body.slice(0, 200)}` }

  const productId = changeset.map((op) => op.product_id ?? op.owner_id ?? op.resource_id)
    .find((id) => typeof id === "string" && id.includes("/Product/"))
  let afterScore: number | null = null
  if (productId) {
    const snap = gateway(runtime, "/v1/read/snapshot", { user_id: req.user_id, org_id: req.org_id, product_id: productId })
    if (snap.status === 200) afterScore = score(JSON.parse(snap.body).product).deterministic
  }
  return { published: true, applied: JSON.parse(applied.body).applied?.length ?? changeset.length, after_score: afterScore }
}

// --- trigger --------------------------------------------------------------------------------------

const onTrigger = (runtime: Runtime<Config>, payload: HTTPPayload): string => {
  const req = decodeJson(payload.input) as Json
  let result: Json
  try {
    result = req.action === "verify" ? verify(runtime, req) : req.action === "publish" ? publish(runtime, req)
      : { error: `unknown action ${req.action}` }
  } catch (e) {
    const reason = String(e).slice(0, 300)
    runtime.log(`${req.action} failed: ${reason}`)
    result = req.action === "publish" ? { published: false, reason } : { outcome: "FAIL", score: 0, reasons: [reason], checks: [] }
  }
  const out = { request_id: req.request_id, action: req.action, ...result }
  callback(runtime, req.callback_url, out)
  return JSON.stringify({ request_id: req.request_id, outcome: result.outcome ?? result.published })
}

const initWorkflow = (config: Config) => [
  handler(new HTTPCapability().trigger({
    authorizedKeys: config.authorizedKeys.map((publicKey) => ({ type: "KEY_TYPE_ECDSA_EVM", publicKey })),
  }), onTrigger),
]

export async function main() {
  const runner = await Runner.newRunner<Config>()
  await runner.run(initWorkflow)
}
