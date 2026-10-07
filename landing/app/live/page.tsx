"use client"

import "./live.css"

import { EscrowCard, useEscrow } from "./escrow"
import { RankCard, RankModal, useRanks } from "./rank"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { LucideIcon } from "lucide-react"
import {
  ArrowDown,
  Bot,
  CalendarDays,
  Check,
  ChevronDown,
  Clock,
  Cpu,
  Database,
  Download,
  Flame,
  Gauge,
  Globe,
  ImagePlus,
  Link2,
  MessagesSquare,
  Moon,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Star,
  Sun,
  Wallet,
  Workflow,
  X,
} from "lucide-react"

/* ------------------------------------------------------------------ data */

const API = (process.env.NEXT_PUBLIC_TRACE_API || "https://worker-production-47e0.up.railway.app").replace(/\/$/, "")

type Ev = {
  id: number
  at: number
  start: number
  agent: string | null
  service: string
  step: string
  detail: string
  status: string
  ms: number | null
  span: string | null
  kind: string | null
  meta: Record<string, any> | null
}

type Task = {
  task: string
  title: string
  brief: string
  coworker: string | null
  phase: string | null
  phase_label: string
  started: number
  last: number
  steps: number
  agents: string[]
  credits: number | null
}

const PEOPLE: Record<string, string> = {
  nora: "Uplift Lead",
  kai: "Search Demand Analyst",
  rafael: "Competitor & Market Analyst",
  priya: "Review & Sentiment Analyst",
  marcus: "Pricing & Promotions Strategist",
  clara: "Product Page Copywriter",
  iris: "Product Visual Designer",
  oskar: "Catalog & Feed Specialist",
  yuki: "Localization Specialist",
  leo: "Content & Email Marketer",
  sasha: "Paid Ads Strategist",
  ruth: "Claims & Compliance Reviewer",
  quinn: "Store Auditor",
}
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
/** Nora's plan nodes as people read them: quinn_after → Quinn (after-report), yuki:de → Yuki (de) */
const baseOf = (agent: string) => agent.split(/[_:]/)[0]
const nameOf = (agent: string) => {
  const [base, ...rest] = agent.replace("_after", ":after-report").split(":")
  return cap(base) + (rest.length ? ` (${rest.join(":")})` : "")
}

type Svc = { match: string; label: string; color: string; icon: LucideIcon; what: string }
const SERVICES: Svc[] = [
  { match: "Sokosumi", label: "Sokosumi", color: "#a78bfa", icon: MessagesSquare, what: "Task, updates, files, approvals" },
  { match: "Masumi", label: "Masumi", color: "#f5b942", icon: Wallet, what: "Payment requests and results" },
  { match: "Cardano", label: "Cardano", color: "#22d3ee", icon: Link2, what: "Escrow smart contract" },
  { match: "Chainlink", label: "Chainlink CRE", color: "#6b9bff", icon: ShieldCheck, what: "Verification and publishing" },
  { match: "Kodosumi", label: "Kodosumi", color: "#fb923c", icon: Cpu, what: "Runs the agents" },
  { match: "Amazon Bedrock", label: "Grok 4.7 · Bedrock", color: "#f472b6", icon: Sparkles, what: "Reasoning and writing" },
  { match: "Google Gemini", label: "Gemini Nano Banana", color: "#2dd4bf", icon: ImagePlus, what: "Image generation" },
  { match: "Serper", label: "Google · Serper", color: "#a3e635", icon: Search, what: "Google results, Shopping, autocomplete" },
  { match: "Shopify", label: "Shopify", color: "#5fd38a", icon: ShoppingBag, what: "Store data (read-only)" },
  { match: "Firecrawl", label: "Firecrawl", color: "#ff8a65", icon: Flame, what: "Reads web pages" },
  { match: "Bright Data", label: "Bright Data", color: "#94a3b8", icon: Star, what: "Amazon reviews" },
  { match: "Tavily", label: "Tavily", color: "#fde047", icon: Globe, what: "Reddit discussions" },
  { match: "Amazon S3", label: "Amazon S3", color: "#cbd5e1", icon: Database, what: "Content-addressed deliverables" },
  { match: "Uplift Worker", label: "Uplift Worker", color: "#7cc8f2", icon: Workflow, what: "Orchestration and journal" },
  { match: "Nager", label: "Nager.Date", color: "#94a3b8", icon: CalendarDays, what: "Public holidays" },
  { match: "Google PageSpeed", label: "PageSpeed", color: "#94a3b8", icon: Gauge, what: "Page speed" },
  { match: "Web", label: "Web", color: "#94a3b8", icon: Download, what: "Downloads" },
  { match: "Agent", label: "Agent", color: "#7cc8f2", icon: Bot, what: "The agent's own steps" },
]
const svcOf = (service: string): Svc =>
  SERVICES.find((s) => service.startsWith(s.match)) ?? { match: service, label: service, color: "#94a3b8", icon: Globe, what: "" }

const WAITING = new Set(["auth_wait", "input_wait", "quote_wait", "approval_wait"])

/* ------------------------------------------------------------------ format */

function dur(ms: number | null | undefined): string {
  if (ms == null) return ""
  if (ms < 1000) return `${Math.max(1, Math.round(ms))} ms`
  const s = ms / 1000
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`
  const m = Math.floor(s / 60)
  const r = Math.round(s % 60)
  return m < 60 ? `${m} m ${String(r).padStart(2, "0")} s` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} m`
}
function offset(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(s / 60)
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}` : `${m}:${String(s % 60).padStart(2, "0")}`
}
function ago(ms: number, now: number): string {
  const s = Math.max(0, (now - ms) / 1000)
  if (s < 60) return "just now"
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(ms).toLocaleDateString()
}
const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })

/* ------------------------------------------------------------------ stream */

function mergeEvent(list: Ev[], index: Map<string, number>, raw: Omit<Ev, "start">): void {
  const ev: Ev = { ...raw, start: raw.at }
  if (ev.span && index.has(ev.span)) {
    const i = index.get(ev.span)!
    const prev = list[i]
    list[i] = { ...prev, ...ev, start: prev.start, meta: { ...(prev.meta || {}), ...(ev.meta || {}) }, detail: ev.detail || prev.detail }
    return
  }
  if (ev.span) index.set(ev.span, list.length)
  list.push(ev)
}

function useTrace(task: string | null, key: string) {
  const [events, setEvents] = useState<Ev[]>([])
  const [conn, setConn] = useState<"idle" | "live" | "retry">("idle")
  const store = useRef<{ list: Ev[]; index: Map<string, number>; queued: boolean; fresh: Set<number> }>({
    list: [],
    index: new Map(),
    queued: false,
    fresh: new Set(),
  })

  useEffect(() => {
    store.current = { list: [], index: new Map(), queued: false, fresh: new Set() }
    setEvents([])
    if (!task || !key) return
    setConn("retry")
    const es = new EventSource(`${API}/trace/stream?task=${encodeURIComponent(task)}&key=${encodeURIComponent(key)}`)
    es.onopen = () => setConn("live")
    es.onerror = () => setConn("retry")
    es.onmessage = (m) => {
      try {
        const raw = JSON.parse(m.data)
        mergeEvent(store.current.list, store.current.index, raw)
        store.current.fresh.add(raw.id)
      } catch {
        return
      }
      if (!store.current.queued) {
        store.current.queued = true
        requestAnimationFrame(() => {
          store.current.queued = false
          setEvents([...store.current.list])
        })
      }
    }
    return () => es.close()
  }, [task, key])

  return { events, conn }
}

/* ------------------------------------------------------------------ pipeline */

type StageState = "done" | "active" | "waiting" | "pending" | "skipped" | "failed"
type Stage = { label: string; icon: LucideIcon; state: StageState; sub: string }

const ORDER_SPECIALIST = ["start", "intake", "auth_wait", "input_wait", "pay", "execute", "verify", "funds_wait", "approval", "approval_wait", "publish", "deliver", "done"]
const ORDER_NORA = ["start", "intake", "auth_wait", "input_wait", "plan", "quote_wait", "execute", "merge", "pay", "propose", "approval_wait", "publish", "report", "deliver", "done"]

function pipeline(events: Ev[], task: Task | undefined): Stage[] {
  const isNora = task?.coworker === "nora"
  const order = isNora ? ORDER_NORA : ORDER_SPECIALIST
  const phases = events.filter((e) => e.kind === "phase").map((e) => e.meta?.phase as string)
  const phase = task?.phase ?? phases[phases.length - 1] ?? "start"
  const failed = phase === "failed" || phase === "closed"
  const pos = order.indexOf(phase === "closed" || phase === "failed" ? phases.filter((p) => order.includes(p)).slice(-1)[0] ?? "start" : phase)
  const seen = new Set(phases)
  const past = (p: string) => pos > order.indexOf(p)
  const of = (kind: string) => events.filter((e) => e.kind === kind)
  const last = (kind: string) => of(kind).slice(-1)[0]
  const st = (done: boolean, active: boolean, waiting = false): StageState =>
    done ? "done" : waiting ? "waiting" : active ? (failed ? "failed" : "active") : "pending"

  const charged = of("payment.charged").some((e) => e.status === "ok")
  const escrow = last("cardano.escrow")
  const runs = of("kodosumi.run")
  const running = runs.filter((e) => e.status === "running").length
  const verifies = of("cre.verify")
  const passes = verifies.filter((e) => e.status === "ok").length
  const publish = last("cre.publish")
  const done = phase === "done"
  const approvalSeen = seen.has("approval_wait")
  const noApproval = !approvalSeen && (phase === "deliver" || phase === "report" || done)

  const received: Stage = { label: "Task received", icon: MessagesSquare, state: events.length ? "done" : "pending", sub: "Sokosumi" }
  const payment: Stage = {
    label: isNora ? "Bill & payment" : "Payment",
    icon: Wallet,
    state: st(charged, phase === "pay"),
    sub: charged ? `${task?.credits ?? ""} credits · Masumi`.trim() : isNora ? "after the work" : "Masumi",
  }
  const lock: Stage = {
    label: "Escrow locked",
    icon: Link2,
    state: escrow?.status === "ok" ? "done" : escrow?.status === "running" ? "active" : "pending",
    sub: escrow?.status === "ok" ? (escrow.ms != null ? `Cardano · ${dur(escrow.ms)}` : "Cardano · locked") : escrow ? "settling on Cardano" : "Cardano",
  }
  const approval: Stage = {
    label: "Your approval",
    icon: Check,
    state: noApproval ? "skipped" : st(approvalSeen && past("approval_wait"), false, phase === "approval_wait"),
    sub: noApproval ? "no store changes" : phase === "approval_wait" ? "waiting for you" : "in Sokosumi",
  }
  const published: Stage = {
    label: "Published",
    icon: ShoppingBag,
    state: noApproval ? "skipped" : publish?.status === "ok" ? "done" : publish?.status === "fail" ? "failed" : st(false, phase === "publish"),
    sub: publish?.meta?.after_score != null ? `listing score ${publish.meta.after_score}/95` : "Chainlink → Shopify",
  }
  const delivered: Stage = { label: "Delivered", icon: Download, state: st(done, phase === "deliver" || phase === "report"), sub: done ? "Task completed" : "files + summary" }

  if (!isNora) {
    const run = runs.slice(-1)[0]
    const verdict = verifies.slice(-1)[0]
    return [
      received,
      payment,
      { label: "Agent at work", icon: Cpu, state: run?.status === "ok" ? "done" : run?.status === "error" && failed ? "failed" : run ? "active" : "pending", sub: run?.status === "ok" ? `Kodosumi · ${dur(run.ms)}` : "Kodosumi" },
      { label: "Chainlink check", icon: ShieldCheck, state: verdict?.status === "ok" ? "done" : verdict?.status === "fail" ? (failed ? "failed" : "active") : verdict ? "active" : "pending", sub: verdict?.meta?.score != null ? `${verdict.meta.outcome} · ${verdict.meta.score}/100` : "CRE" },
      lock,
      approval,
      published,
      delivered,
    ]
  }
  const agents = new Set(runs.map((e) => e.agent))
  return [
    received,
    { label: "Plan & quote", icon: Workflow, state: st(past("quote_wait"), phase === "intake" || phase === "plan", phase === "quote_wait"), sub: phase === "quote_wait" ? "waiting for you" : "Nora" },
    { label: "Team at work", icon: Bot, state: st(past("execute"), phase === "execute"), sub: agents.size ? `${agents.size} specialists · ${running} running` : "Kodosumi" },
    { label: "Chainlink checks", icon: ShieldCheck, state: st(past("execute") && verifies.length > 0, verifies.length > 0), sub: verifies.length ? `${passes}/${verifies.length} passed` : "CRE" },
    payment,
    lock,
    approval,
    published,
    delivered,
  ]
}

/* ------------------------------------------------------------------ timeline grouping */

type Item =
  | { type: "stage"; ev: Ev }
  | { type: "row"; ev: Ev }
  | { type: "group"; key: string; evs: Ev[] }

const GROUPABLE = /^(serper\.|shopify\.read|s3\.put|firecrawl|download|tavily\.)/

function build(events: Ev[]): Item[] {
  const out: Item[] = []
  for (const ev of events) {
    if (ev.status === "stage") {
      out.push({ type: "stage", ev })
      continue
    }
    const prev = out[out.length - 1]
    const groupable = ev.kind && GROUPABLE.test(ev.kind)
    if (groupable && prev && prev.type === "group" && prev.evs[0].kind === ev.kind && prev.evs[0].agent === ev.agent) {
      prev.evs.push(ev)
      continue
    }
    if (groupable && prev && prev.type === "row" && prev.ev.kind === ev.kind && prev.ev.agent === ev.agent) {
      out[out.length - 1] = { type: "group", key: `g-${prev.ev.id}`, evs: [prev.ev, ev] }
      continue
    }
    out.push({ type: "row", ev })
  }
  // two in a row read better as rows
  return out.flatMap((it) => (it.type === "group" && it.evs.length < 3 ? it.evs.map((ev) => ({ type: "row" as const, ev })) : [it]))
}

/* ------------------------------------------------------------------ small parts */

function Avatar({ role: agent, size = 28 }: { role?: string | null; size?: number }) {
  const role = agent ? baseOf(agent) : agent
  if (!role || !PEOPLE[role]) return <span className="lv-av" style={{ width: size, height: size, display: "inline-grid", placeItems: "center" }}><Workflow size={size * 0.5} /></span>
  return <img className="lv-av" src={`/avatars/${role}.png`} alt={nameOf(agent!)} width={size} height={size} style={{ width: size, height: size }} />
}

function Chip({ service }: { service: string }) {
  const s = svcOf(service)
  const Icon = s.icon
  return (
    <span className="lv-chip" style={{ ["--c" as any]: s.color }}>
      <Icon strokeWidth={2.2} />
      {s.label}
    </span>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === "running") return <span className="lv-spin" aria-label="running" />
  if (status === "wait") return <Clock size={17} color="var(--wait)" strokeWidth={2.4} aria-label="retrying" />
  if (status === "error") return <X size={18} color="var(--bad)" strokeWidth={2.6} aria-label="error" />
  if (status === "fail") return <X size={18} color="var(--wait)" strokeWidth={2.6} aria-label="did not pass" />
  return <Check size={18} color="var(--ok)" strokeWidth={2.6} aria-label="done" />
}

function Checks({ checks }: { checks: any[] }) {
  return (
    <div className="lv-checks">
      {checks.map((c, i) => {
        const pct = c.max ? Math.max(0, Math.min(100, (c.points / c.max) * 100)) : 0
        return (
          <div className="lv-check" key={i}>
            <span className="nm" title={c.name}>{c.name}{c.gate ? " · required" : ""}</span>
            <span className="pt lv-mono">{c.points}/{c.max}</span>
            <span className="lv-bar"><i className={pct >= 70 ? "" : pct >= 40 ? "mid" : "low"} style={{ width: `${pct}%` }} /></span>
          </div>
        )
      })}
    </div>
  )
}

function Details({ ev }: { ev: Ev }) {
  const meta = { ...(ev.meta || {}) }
  const prompt = meta.prompt
  const checks = Array.isArray(meta.checks) ? meta.checks : null
  const message = meta.message
  const instruction = meta.instruction
  for (const k of ["prompt", "checks", "message", "instruction", "phase"]) delete meta[k]
  const rows = Object.entries(meta).filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length))
  return (
    <div className="lv-more" onClick={(e) => e.stopPropagation()}>
      <dl className="lv-kv">
        <dt>Service</dt>
        <dd>{ev.service}{svcOf(ev.service).what ? ` — ${svcOf(ev.service).what}` : ""}</dd>
        <dt>Started</dt>
        <dd className="lv-mono">{clock(ev.start)}{ev.ms != null ? ` · took ${dur(ev.ms)}` : ""}</dd>
        {ev.agent && (<><dt>Agent</dt><dd>{nameOf(ev.agent)} · {PEOPLE[baseOf(ev.agent)] ?? ""}</dd></>)}
        {rows.map(([k, v]) => (
          <FragmentKV key={k} k={k} v={v} />
        ))}
      </dl>
      {checks && checks.length > 0 && (<><div className="lv-sub">Chainlink checks</div><Checks checks={checks} /></>)}
      {message && (<><div className="lv-sub">Message posted to the Task</div><pre className="lv-pre">{message}</pre></>)}
      {instruction && (<><div className="lv-sub">Image instruction</div><pre className="lv-pre">{instruction}</pre></>)}
      {prompt && (<><div className="lv-sub">Prompt (start)</div><pre className="lv-pre">{prompt}</pre></>)}
    </div>
  )
}

function FragmentKV({ k, v }: { k: string; v: any }) {
  const label = cap(k.replace(/_/g, " "))
  const value = Array.isArray(v) ? v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(" · ") : typeof v === "object" ? JSON.stringify(v) : String(v)
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  )
}

function Row({ ev, t0, now, multi, open, onToggle, fresh }: { ev: Ev; t0: number; now: number; multi: boolean; open: boolean; onToggle: () => void; fresh: boolean }) {
  const running = ev.status === "running"
  return (
    <div className={`lv-row ${open ? "open" : ""} ${ev.status === "error" ? "error" : ""} ${ev.status === "fail" || ev.status === "wait" ? "fail" : ""} ${fresh ? "fresh" : ""}`} onClick={onToggle} role="button" aria-expanded={open}>
      <span className="lv-time lv-mono" title={clock(ev.start)}>{offset(ev.start - t0)}</span>
      <span className="lv-ico"><StatusIcon status={ev.status} /></span>
      <div style={{ minWidth: 0 }}>
        <div className="lv-line1">
          {multi && ev.agent && (
            <span className="lv-who-mini"><Avatar role={ev.agent} size={22} />{nameOf(ev.agent)}</span>
          )}
          <Chip service={ev.service} />
          <span className="lv-step">{ev.step}</span>
        </div>
        {ev.detail && <div className="lv-detail">{ev.detail}</div>}
      </div>
      <span className={`lv-dur lv-mono ${running ? "live" : ""}`}>{running ? dur(now - ev.start) : dur(ev.ms)}</span>
      {open && <Details ev={ev} />}
    </div>
  )
}

function Group({ evs, t0, now, multi, open, onToggle, openRow, toggleRow }: { evs: Ev[]; t0: number; now: number; multi: boolean; open: boolean; onToggle: () => void; openRow: number | null; toggleRow: (id: number) => void }) {
  const first = evs[0]
  const running = evs.filter((e) => e.status === "running").length
  const errors = evs.filter((e) => e.status === "error").length
  const total = evs.reduce((a, e) => a + (e.ms ?? 0), 0)
  const label = first.step.split(":")[0]
  const end = Math.max(...evs.map((e) => e.start + (e.ms ?? now - e.start)))
  return (
    <div>
      <div className={`lv-row ${open ? "open" : ""}`} onClick={onToggle} role="button" aria-expanded={open}>
        <span className="lv-time lv-mono">{offset(first.start - t0)}</span>
        <span className="lv-ico"><StatusIcon status={running ? "running" : errors ? "error" : "ok"} /></span>
        <div style={{ minWidth: 0 }}>
          <div className="lv-line1">
            {multi && first.agent && (<span className="lv-who-mini"><Avatar role={first.agent} size={22} />{nameOf(first.agent)}</span>)}
            <Chip service={first.service} />
            <span className="lv-step">{evs.length} × {label}</span>
          </div>
          <div className="lv-detail">
            {evs.slice(0, 3).map((e) => e.step.includes(":") ? e.step.split(":").slice(1).join(":").trim() : e.detail).filter(Boolean).join(" · ")}
            {evs.length > 3 ? ` · and ${evs.length - 3} more` : ""}
            {running ? ` — ${running} in progress` : ""}{errors ? ` — ${errors} failed` : ""}
          </div>
          {!open && <div className="lv-group-more">Show all {evs.length}</div>}
        </div>
        <span className={`lv-dur lv-mono ${running ? "live" : ""}`} title={`${dur(total)} of calls in total`}>{dur(end - first.start)}</span>
      </div>
      {open && (
        <div style={{ paddingLeft: 40, borderLeft: "2px solid var(--line)", marginLeft: 88 }}>
          {evs.map((e) => (
            <Row key={e.id} ev={e} t0={t0} now={now} multi={false} open={openRow === e.id} onToggle={() => toggleRow(e.id)} fresh={false} />
          ))}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ page */

export default function LivePage() {
  const [theme, setTheme] = useState<"dark" | "light">("dark")
  const [key, setKey] = useState("")
  const [keyDraft, setKeyDraft] = useState("")
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [taskErr, setTaskErr] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [follow, setFollow] = useState(true)
  const [menu, setMenu] = useState(false)
  const [agentFilter, setAgentFilter] = useState<string | null>(null)
  const [openRow, setOpenRow] = useState<number | null>(null)
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set())
  const [briefOpen, setBriefOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [atBottom, setAtBottom] = useState(true)
  const [rankOpen, setRankOpen] = useState(false)
  const scroller = useRef<HTMLDivElement | null>(null)
  const seenIds = useRef<Set<number>>(new Set())

  // key and preferences: URL first, then this browser
  useEffect(() => {
    const url = new URL(window.location.href)
    let k = url.searchParams.get("key") || ""
    try {
      if (k) localStorage.setItem("uplift-live-key", k)
      else k = localStorage.getItem("uplift-live-key") || ""
      const t = localStorage.getItem("uplift-live-theme")
      if (t === "light" || t === "dark") setTheme(t)
    } catch {}
    setKey(k)
    const t = url.searchParams.get("task")
    if (t) {
      setSelected(t)
      setFollow(false)
    }
    if (url.searchParams.has("key")) {
      url.searchParams.delete("key")
      window.history.replaceState(null, "", url.toString())
    }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem("uplift-live-theme", theme)
    } catch {}
  }, [theme])

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  // recent Tasks
  useEffect(() => {
    if (!key) return
    let alive = true
    const load = async () => {
      try {
        const r = await fetch(`${API}/trace/tasks?key=${encodeURIComponent(key)}`)
        if (r.status === 401) {
          setTaskErr("That key was not accepted.")
          return
        }
        const body = await r.json()
        if (alive) {
          setTasks(body.tasks)
          setTaskErr("")
        }
      } catch {
        if (alive) setTaskErr("Can't reach the Uplift Worker right now — retrying.")
      }
    }
    load()
    const t = setInterval(load, 3000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [key])

  // follow the newest Task
  useEffect(() => {
    if (!tasks?.length) return
    const newest = [...tasks].sort((a, b) => b.started - a.started)[0]
    if (!selected || (follow && newest.task !== selected)) {
      setSelected(newest.task)
      setAgentFilter(null)
      setOpenRow(null)
    }
  }, [tasks, follow, selected])

  const { events, conn } = useTrace(selected, key)
  const task = tasks?.find((t) => t.task === selected)

  const t0 = events[0]?.start ?? task?.started ?? now
  const finished = task?.phase === "done" || task?.phase === "closed" || task?.phase === "failed"
  const lastAt = events.length ? Math.max(...events.map((e) => e.start + (e.ms ?? 0))) : now
  const elapsed = (finished ? lastAt : now) - t0

  // What the page shows: no error steps, and no step still "running" from an agent run that has already ended (a
  // run that was lost or stopped never closes its open steps). The pipeline keeps reading every event.
  const shown = useMemo(() => {
    const ended = new Map<string, number>()
    for (const e of events)
      if (e.kind === "kodosumi.run" && e.status !== "running" && e.agent) ended.set(e.agent, Math.max(ended.get(e.agent) ?? 0, e.at))
    return events.filter((e) => {
      if (e.status === "error") return false
      if (e.status !== "running") return true
      if (finished) return false
      const end = e.agent ? ended.get(e.agent) : undefined
      return !(end && end > e.start && e.kind !== "kodosumi.run")
    })
  }, [events, finished])

  const agents = useMemo(() => {
    const by = new Map<string, number>()
    for (const e of shown) if (e.agent) by.set(e.agent, (by.get(e.agent) ?? 0) + 1)
    return [...by.entries()]
  }, [shown])
  const multi = agents.length > 1

  const visible = useMemo(() => (agentFilter ? shown.filter((e) => e.agent === agentFilter) : shown), [shown, agentFilter])
  const items = useMemo(() => build(visible), [visible])
  const stages = useMemo(() => pipeline(events, task), [events, task])
  const running = useMemo(() => shown.filter((e) => e.status === "running").sort((a, b) => b.start - a.start), [shown])

  const services = useMemo(() => {
    const by = new Map<string, { label: string; svc: Svc; calls: number; ms: number; active: boolean; first: number }>()
    for (const e of shown) {
      if (e.status === "stage") continue
      const s = svcOf(e.service)
      const cur = by.get(s.label) ?? { label: s.label, svc: s, calls: 0, ms: 0, active: false, first: e.start }
      cur.calls += 1
      cur.ms += e.ms ?? 0
      cur.active = cur.active || e.status === "running"
      by.set(s.label, cur)
    }
    return [...by.values()].sort((a, b) => a.first - b.first)
  }, [shown])

  // re-read the rank checks as soon as the trace shows one finishing
  const rankDone = events.filter((e) => e.kind?.startsWith("rank.") && e.status !== "running").length
  const ranks = useRanks(API, selected, key, rankDone)
  useEffect(() => setRankOpen(false), [selected])
  // re-read the escrow when the trace shows a payment step finishing
  const payDone = events.filter((e) => (e.kind === "cardano.escrow" || e.kind?.startsWith("masumi.") || e.kind === "payment.charged") && e.status !== "running").length
  const escrow = useEscrow(API, selected, key, payDone)
  const checkState = (kind: string): "none" | "running" | "failed" => {
    const last = events.filter((e) => e.kind === kind).slice(-1)[0]
    return !last ? "none" : last.status === "running" ? "running" : last.status === "error" ? "failed" : "none"
  }

  const verdicts = useMemo(() => shown.filter((e) => e.kind === "cre.verify" && e.status !== "running"), [shown])
  const lastVerdict = verdicts[verdicts.length - 1]

  const nowEv = running[0] ?? shown[shown.length - 1]

  // fresh-row highlight: ids not seen before this render
  const fresh = useMemo(() => {
    const f = new Set<number>()
    for (const e of events) if (!seenIds.current.has(e.id)) f.add(e.id)
    return f
  }, [events])
  useEffect(() => {
    for (const e of events) seenIds.current.add(e.id)
  }, [events])
  useEffect(() => {
    seenIds.current = new Set()
  }, [selected])

  // keep the newest step in view while following
  useEffect(() => {
    if (!atBottom) return
    const el = scroller.current
    if (el && el.scrollHeight > el.clientHeight) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
    else window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })
  }, [items.length, atBottom])

  const onScroll = useCallback(() => {
    const el = scroller.current
    if (!el) return
    const scrollable = el.scrollHeight > el.clientHeight
    const dist = scrollable ? el.scrollHeight - el.scrollTop - el.clientHeight : document.body.scrollHeight - window.scrollY - window.innerHeight
    setAtBottom(dist < 160)
  }, [])
  useEffect(() => {
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [onScroll])

  const jump = () => {
    setAtBottom(true)
    const el = scroller.current
    if (el && el.scrollHeight > el.clientHeight) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
    else window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })
  }

  const statusTone = !task ? "var(--text-3)" : task.phase === "done" ? "var(--ok)" : task.phase === "failed" || task.phase === "closed" ? "var(--bad)" : WAITING.has(task.phase ?? "") ? "var(--wait)" : "var(--run)"

  /* ---------- key gate ---------- */
  if (!key) {
    return (
      <div className="lv" data-theme={theme}>
        <div className="lv-center">
          <div>
            <Logo />
            <h2 className="lv-h">Uplift Live</h2>
            <p>Every step behind a Sokosumi Task, as it happens — the agent, the service it is using, and the result. Enter the viewing key to continue.</p>
            <form
              style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 22, flexWrap: "wrap" }}
              onSubmit={(e) => {
                e.preventDefault()
                const k = keyDraft.trim()
                if (!k) return
                try {
                  localStorage.setItem("uplift-live-key", k)
                } catch {}
                setKey(k)
              }}
            >
              <input className="lv-input lv-mono" placeholder="Viewing key" value={keyDraft} onChange={(e) => setKeyDraft(e.target.value)} aria-label="Viewing key" />
              <button className="lv-primary" type="submit">Open</button>
            </form>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="lv" data-theme={theme}>
      <div className="lv-app">
        {/* top bar */}
        <header className="lv-top">
          <span className="lv-logo lv-h"><Logo /> Uplift <small>Live</small></span>
          <div className="lv-picker">
            <button className="lv-picker-btn" onClick={() => setMenu((m) => !m)} aria-expanded={menu}>
              <Avatar role={task?.coworker} size={32} />
              <span className="t">{task ? task.title : tasks ? "Choose a Task" : "Loading…"}</span>
              <ChevronDown size={18} style={{ flex: "none", color: "var(--text-3)" }} />
            </button>
            {menu && tasks && (
              <div className="lv-menu" onMouseLeave={() => setMenu(false)}>
                {tasks.map((t) => (
                  <button
                    key={t.task}
                    className="lv-menu-item"
                    aria-current={t.task === selected}
                    onClick={() => {
                      setSelected(t.task)
                      setFollow(false)
                      setMenu(false)
                      setAgentFilter(null)
                      setOpenRow(null)
                    }}
                  >
                    <Avatar role={t.coworker} size={36} />
                    <span style={{ minWidth: 0 }}>
                      <div className="t">{t.title}</div>
                      <div className="s">
                        {t.coworker ? cap(t.coworker) : "—"} · {t.phase_label || "—"} · {ago(t.last, now)}
                      </div>
                    </span>
                  </button>
                ))}
                {!tasks.length && <div className="lv-menu-item s">No Tasks yet.</div>}
              </div>
            )}
          </div>
          <span className="lv-spacer" />
          <button className="lv-pill-btn" aria-pressed={follow} onClick={() => setFollow((f) => !f)} title="Switch to each new Task automatically">
            Follow new Tasks
          </button>
          <span className="lv-conn">
            <span className={`lv-dot ${conn === "live" ? "on" : conn === "retry" ? "warn" : ""}`} />
            {conn === "live" ? "Live" : conn === "retry" ? "Connecting…" : "Idle"}
          </span>
          <button className="lv-pill-btn" onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))} aria-label="Switch theme">
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </header>

        {taskErr && <div style={{ padding: "10px 24px", color: "var(--wait)", fontSize: 14 }}>{taskErr}</div>}

        {!task && tasks && !tasks.length && (
          <div className="lv-center">
            <div>
              <span className="lv-spin" style={{ width: 28, height: 28, display: "inline-block" }} />
              <h2 className="lv-h">Waiting for the first Task</h2>
              <p>Assign a Task to any Uplift coworker on Sokosumi. It appears here the moment the coworker picks it up.</p>
            </div>
          </div>
        )}

        {task && (
          <>
            {/* hero */}
            <section className="lv-hero">
              <div className="lv-hero-main">
                <Avatar role={task.coworker} size={64} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="lv-who">
                    <b>{task.coworker ? cap(task.coworker) : "Uplift"}</b>
                    <span>{task.coworker ? PEOPLE[task.coworker] : ""}</span>
                    <span style={{ color: "var(--text-3)" }}>·</span>
                    <span className="lv-mono" style={{ color: "var(--text-3)", fontSize: 13 }} title={task.task}>Task …{task.task.slice(-8)}</span>
                  </div>
                  <h1 className="lv-h">{task.title}</h1>
                  {task.brief && (
                    <div>
                      <div className={`lv-brief ${briefOpen ? "" : "clamp"}`}>{task.brief}</div>
                      {task.brief.length > 180 && (
                        <button className="lv-link" onClick={() => setBriefOpen((b) => !b)}>{briefOpen ? "Show less" : "Show the full brief"}</button>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div className="lv-stats">
                <div className="lv-stat">
                  <div className="k">Status</div>
                  <div className="v lv-status" style={{ color: statusTone }}>
                    <span className="lv-dot" style={{ background: statusTone }} />
                    {task.phase_label || "Starting"}
                  </div>
                </div>
                <div className="lv-stat"><div className="k">Elapsed</div><div className="v lv-mono">{offset(elapsed)}</div></div>
                <div className="lv-stat"><div className="k">Credits</div><div className="v lv-mono">{task.credits ?? "—"}</div></div>
                <div className="lv-stat"><div className="k">Steps</div><div className="v lv-mono">{shown.filter((e) => e.status !== "stage").length}</div></div>
                <div className="lv-stat"><div className="k">Services</div><div className="v lv-mono">{services.length}</div></div>
                {multi && <div className="lv-stat"><div className="k">Agents</div><div className="v lv-mono">{agents.length}</div></div>}
              </div>
              <div className="lv-pipe" aria-label="Progress">
                {stages.map((s, i) => {
                  const Icon = s.icon
                  return (
                    <div key={i} className={`lv-stage ${s.state}`}>
                      <div className="lv-stage-dot">{s.state === "done" ? <Check size={18} strokeWidth={3} /> : s.state === "failed" ? <X size={18} strokeWidth={3} /> : <Icon size={17} strokeWidth={2.2} />}</div>
                      <div className="lv-stage-label">{s.label}</div>
                      <div className="lv-stage-sub">{s.sub}</div>
                    </div>
                  )
                })}
              </div>
            </section>

            <div className="lv-body">
              {/* timeline */}
              <main className="lv-scroll" ref={scroller} onScroll={onScroll}>
                {nowEv && (
                  <div className="lv-now">
                    <div className="lv-now-inner">
                      <span className="lbl">{nowEv.status === "running" ? "Now" : finished ? "Last step" : "Latest"}</span>
                      {multi && nowEv.agent && <Avatar role={nowEv.agent} size={26} />}
                      <Chip service={nowEv.service} />
                      <span className="txt">{nowEv.step}</span>
                      <span className="tm lv-mono">{nowEv.status === "running" ? dur(now - nowEv.start) : ago(nowEv.start + (nowEv.ms ?? 0), now)}</span>
                    </div>
                  </div>
                )}
                {multi && (
                  <div className="lv-filters">
                    <button className="lv-fchip all" aria-pressed={!agentFilter} onClick={() => setAgentFilter(null)}>
                      Everyone <span className="n">{shown.length}</span>
                    </button>
                    {agents.map(([a, n]) => (
                      <button key={a} className="lv-fchip" aria-pressed={agentFilter === a} onClick={() => setAgentFilter(agentFilter === a ? null : a)}>
                        <Avatar role={a} size={26} /> {nameOf(a)} <span className="n">{n}</span>
                      </button>
                    ))}
                  </div>
                )}
                <div className="lv-tl">
                  {!events.length && (
                    <div className="lv-center" style={{ minHeight: 240 }}>
                      <div><span className="lv-spin" style={{ width: 24, height: 24, display: "inline-block" }} /><p style={{ marginTop: 12 }}>Waiting for the first step…</p></div>
                    </div>
                  )}
                  {items.map((it) => {
                    if (it.type === "stage") {
                      return (
                        <div className="lv-stagehead" key={it.ev.id}>
                          <Avatar role={it.ev.agent} size={30} />
                          <span>
                            <div className="a">{it.ev.agent ? nameOf(it.ev.agent) : "Agent"}</div>
                            <div className="t lv-h">{it.ev.step}</div>
                          </span>
                          <span className="when lv-mono">{offset(it.ev.start - t0)}</span>
                        </div>
                      )
                    }
                    if (it.type === "group") {
                      const open = openGroups.has(it.key)
                      return (
                        <Group
                          key={it.key}
                          evs={it.evs}
                          t0={t0}
                          now={now}
                          multi={multi && !agentFilter}
                          open={open}
                          onToggle={() =>
                            setOpenGroups((g) => {
                              const n = new Set(g)
                              n.has(it.key) ? n.delete(it.key) : n.add(it.key)
                              return n
                            })
                          }
                          openRow={openRow}
                          toggleRow={(id) => setOpenRow(openRow === id ? null : id)}
                        />
                      )
                    }
                    return (
                      <Row
                        key={it.ev.id}
                        ev={it.ev}
                        t0={t0}
                        now={now}
                        multi={multi && !agentFilter}
                        open={openRow === it.ev.id}
                        onToggle={() => setOpenRow(openRow === it.ev.id ? null : it.ev.id)}
                        fresh={fresh.has(it.ev.id) && events.length > 1}
                      />
                    )
                  })}
                </div>
              </main>

              {/* side */}
              <aside className="lv-side lv-scroll">
                <RankCard ranks={ranks} startState={checkState("rank.start")} endState={checkState("rank.end")} finished={task.phase === "done"} onOpen={() => setRankOpen(true)} />
                <EscrowCard escrow={escrow} now={now} />
                <section className="lv-card">
                  <h3>{running.length ? <span className="lv-spin" style={{ width: 12, height: 12 }} /> : null} In progress</h3>
                  {running.length ? (
                    <div className="lv-running">
                      {running.slice(0, 6).map((e) => {
                        const s = svcOf(e.service)
                        const Icon = s.icon
                        return (
                          <div className="lv-running-row" key={e.id}>
                            <Icon size={18} color={s.color} style={{ marginTop: 2 }} />
                            <div style={{ minWidth: 0 }}>
                              <div className="st">{e.step}</div>
                              <div className="sv">{s.label}{e.agent ? ` · ${nameOf(e.agent)}` : ""}</div>
                            </div>
                            <span className="tm lv-mono">{dur(now - e.start)}</span>
                          </div>
                        )
                      })}
                      {running.length > 6 && <div className="lv-empty-side">and {running.length - 6} more</div>}
                    </div>
                  ) : (
                    <div className="lv-empty-side">{finished ? "Nothing — this Task has finished." : "Nothing running this second."}</div>
                  )}
                </section>

                {lastVerdict && (
                  <section className="lv-card">
                    <h3><ShieldCheck size={14} /> Chainlink verdict{verdicts.length > 1 ? `s · ${verdicts.filter((v) => v.status === "ok").length}/${verdicts.length} passed` : ""}</h3>
                    {multi && verdicts.length > 1 && (
                      <div style={{ display: "grid", gap: 6, marginBottom: 14 }}>
                        {verdicts.map((v) => (
                          <div key={v.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14 }}>
                            <Avatar role={v.agent} size={22} />
                            <span style={{ flex: 1 }}>{v.agent ? nameOf(v.agent) : ""}</span>
                            <span className="lv-mono" style={{ color: v.status === "ok" ? "var(--ok)" : "var(--wait)", fontWeight: 700 }}>
                              {v.meta?.outcome} {v.meta?.score}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="lv-verdict">
                      <span className="o" style={{ color: lastVerdict.status === "ok" ? "var(--ok)" : "var(--wait)" }}>{lastVerdict.meta?.outcome}</span>
                      <span className="s lv-mono">{lastVerdict.meta?.score}/100{multi && lastVerdict.agent ? ` · ${nameOf(lastVerdict.agent)}` : ""}</span>
                    </div>
                    {Array.isArray(lastVerdict.meta?.checks) && <Checks checks={lastVerdict.meta!.checks} />}
                    {lastVerdict.meta?.judge && <p style={{ fontSize: 13.5, color: "var(--text-2)", margin: "12px 0 0" }}>“{lastVerdict.meta.judge}”</p>}
                  </section>
                )}

                <section className="lv-card">
                  <h3>Services used</h3>
                  {services.length ? (
                    <div className="lv-svc">
                      {services.map((s) => (
                        <div key={s.label} className={`lv-svc-row ${s.active ? "active" : ""}`}>
                          <span style={{ minWidth: 0 }}>
                            <Chip service={s.svc.match} />
                            <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 4 }}>{s.svc.what}</div>
                          </span>
                          <span className="m lv-mono">
                            {s.active ? <span style={{ color: "var(--run)", fontWeight: 600 }}>in use · </span> : null}
                            {s.calls}×{s.ms ? ` · ${dur(s.ms)}` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="lv-empty-side">None yet.</div>
                  )}
                </section>
              </aside>
            </div>
          </>
        )}
      </div>
      {rankOpen && ranks && (ranks.start || ranks.end) && <RankModal ranks={ranks} onClose={() => setRankOpen(false)} />}
      {task && !atBottom && (
        <button className="lv-jump" onClick={jump}>
          <ArrowDown size={16} /> Latest step
        </button>
      )}
    </div>
  )
}

function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="10" fill="#156d95" />
      <path d="M9 19.5 L16 12 L23 19.5" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="16" cy="23" r="2" fill="#7cc8f2" />
    </svg>
  )
}
