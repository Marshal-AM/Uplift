import {
  ConfidentialHTTPClient,
  consensusIdenticalAggregation,
  consensusMedianAggregation,
  HTTPClient,
  httpRequest,
  type NodeRuntime,
  type Runtime,
  text,
} from "@chainlink/cre-sdk"
import { sha256 } from "@noble/hashes/sha2.js"
import { bytesToHex } from "@noble/hashes/utils.js"
import canonicalize from "canonicalize"

export type Config = {
  sokosumiApiUrl: string
  gatewayUrl: string
  bedrockRegion: string
  bedrockModel: string
  secretsOwner: string
  authorizedKeys: string[]
}

export type Json = Record<string, any>

export const sha256Hex = (s: string): string => bytesToHex(sha256(new TextEncoder().encode(s)))
export const canonical = (v: unknown): string => canonicalize(v) as string

// --- Confidential HTTP (DON mode): anything that carries a Vault DON secret, plus large bodies ----------

type CallOpts = { method?: string; headers?: Record<string, string>; body?: unknown; secrets?: string[] }

export function call(runtime: Runtime<Config>, url: string, opts: CallOpts = {}): { status: number; body: string } {
  const body = opts.body === undefined ? undefined
    : new TextEncoder().encode(typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body))
  const resp = new ConfidentialHTTPClient()
    .sendRequest(runtime, {
      request: httpRequest({
        url,
        method: opts.method ?? (body ? "POST" : "GET"),
        headers: { "Content-Type": "application/json", Accept: "application/json", ...opts.headers },
        ...(body ? { body } : {}), // bytes: never parsed as a template, so payload text cannot collide with {{.x}}
        timeout: "60s",
      }),
      vaultDonSecrets: [...(opts.secrets ?? [])].sort()
        .map((key) => (runtime.config.secretsOwner ? { key, owner: runtime.config.secretsOwner } : { key })),
    })
    .result()
  return { status: resp.statusCode, body: text(resp) }
}

export function callJson(runtime: Runtime<Config>, url: string, opts: CallOpts = {}): any {
  const r = call(runtime, url, opts)
  if (r.status >= 400) throw new Error(`${opts.method ?? "GET"} ${url.split("?")[0]} → ${r.status}: ${r.body.slice(0, 200)}`)
  return JSON.parse(r.body)
}

// --- Regular HTTP in node mode: public fetches, reduced to a small value every node agrees on ----------

export function nodeFetch(nodeRuntime: NodeRuntime<Config>, url: string): { status: number; body: string } {
  const resp = new HTTPClient()
    .sendRequest(nodeRuntime, { url, method: "GET", headers: { "User-Agent": "Mozilla/5.0 (Uplift verifier)" } })
    .result()
  return { status: resp.statusCode, body: text(resp) }
}

/** Run `fn` on every node and agree on its (deterministic) JSON-able result. Keep results < 25 KB. */
export function onNodes<T>(runtime: Runtime<Config>, fn: (n: NodeRuntime<Config>) => T): T {
  const out = runtime.runInNodeMode((n: NodeRuntime<Config>) => JSON.stringify(fn(n)),
    consensusIdenticalAggregation<string>())().result()
  return JSON.parse(out) as T
}

/** Run `fn` on every node and take the median of a number (for live web pages that differ slightly). */
export function medianOnNodes(runtime: Runtime<Config>, fn: (n: NodeRuntime<Config>) => number): number {
  return runtime.runInNodeMode(fn, consensusMedianAggregation<number>())().result()
}

/** Fetch a content-addressed document and check it hashes to what the caller claims. */
export function fetchVerified(n: NodeRuntime<Config>, url: string, expected: string): string {
  const r = nodeFetch(n, url)
  if (r.status !== 200) throw new Error(`fetch ${expected.slice(0, 12)} → ${r.status}`)
  if (sha256Hex(r.body) !== expected) throw new Error(`hash mismatch for ${expected.slice(0, 12)}`)
  return r.body
}

// --- Judge: Claude Sonnet 5.5 on Bedrock, max 5 points, neutral 2.5 when unavailable ------------------

export function judge(runtime: Runtime<Config>, question: string, material: string): { points: number; note: string } {
  const c = runtime.config
  try {
    const out = callJson(runtime,
      `https://bedrock-runtime.${c.bedrockRegion}.amazonaws.com/model/${c.bedrockModel}/converse`, {
        headers: { Authorization: "Bearer {{.bedrockApiKey}}" },
        secrets: ["bedrockApiKey"],
        body: {
          messages: [{ role: "user", content: [{ text: `${question}\n\nMaterial:\n${material.slice(0, 12000)}` }] }],
          inferenceConfig: { maxTokens: 400, temperature: 0 },
          toolConfig: {
            tools: [{ toolSpec: { name: "verdict", description: "Score the material.", inputSchema: { json: {
              type: "object",
              properties: { score: { type: "number", minimum: 0, maximum: 5 }, reason: { type: "string" } },
              required: ["score", "reason"],
            } } } }],
            toolChoice: { tool: { name: "verdict" } },
          },
        },
      })
    const use = out.output.message.content.find((b: Json) => b.toolUse)?.toolUse.input
    return { points: Math.max(0, Math.min(5, Number(use.score))), note: String(use.reason ?? "").slice(0, 300) }
  } catch (e) {
    runtime.log(`judge unavailable: ${String(e).slice(0, 200)}`)
    return { points: 2.5, note: "judge unavailable" }
  }
}

// --- Sokosumi and the Uplift gateway ---------------------------------------------------------------

export function soko(runtime: Runtime<Config>, role: string, path: string,
  opts: { method?: string; body?: unknown; as?: [string, string] } = {}): any {
  const headers: Record<string, string> = { Authorization: `Bearer {{.soko_${role}}}` }
  if (opts.as) {
    headers["X-Context-User-Id"] = opts.as[0]
    if (opts.as[1]) headers["X-Context-Organization-Id"] = opts.as[1]
  }
  return callJson(runtime, `${runtime.config.sokosumiApiUrl}${path}`,
    { method: opts.method, body: opts.body, headers, secrets: [`soko_${role}`] }).data
}

export function taskEvents(runtime: Runtime<Config>, role: string, taskId: string): Json[] {
  return soko(runtime, role, `/v1/tasks/${taskId}/events`) // oldest first; no limit = full list
}

export function gateway(runtime: Runtime<Config>, path: string, body: Json, write = false): { status: number; body: string } {
  const key = write ? "gatewayWriteKey" : "gatewayReadKey"
  return call(runtime, `${runtime.config.gatewayUrl}${path}`,
    { body, headers: { Authorization: `Bearer {{.${key}}}` }, secrets: [key] })
}

export function dataforseo(runtime: Runtime<Config>, path: string, tasks: Json[]): Json[] {
  const r = callJson(runtime, `https://api.dataforseo.com/v3/${path}`,
    { body: tasks, headers: { Authorization: "Basic {{.dataforseoAuth}}" }, secrets: ["dataforseoAuth"] })
  return (r.tasks ?? []).flatMap((t: Json) => t.result ?? [])
}

export function callback(runtime: Runtime<Config>, url: string, result: Json): void {
  const r = call(runtime, url, { body: result, headers: { Authorization: "Bearer {{.workerHookKey}}" },
    secrets: ["workerHookKey"] })
  if (r.status >= 400) runtime.log(`callback → ${r.status}`)
}
