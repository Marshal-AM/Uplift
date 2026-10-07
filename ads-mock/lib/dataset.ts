"use client"
// Which data the mock shows: the hardcoded DEMO store, or a finished Uplift run fetched from the Worker's /ads API.
//
//   /?key=<view key>              newest run with Google Ads output (the key is remembered, then removed from the URL)
//   /ads/?task=<id>&key=<key>     a specific run
//   /ads/?task=<id>&t=<token>     a run shared by Nora's "Preview your Google Ads" link (opens that run only)
//
// Without a key or link the mock shows the demo store. Every storage access tolerates blocked storage.
import { useSyncExternalStore } from "react"
import { DEMO, type Dataset } from "./data"
import { bindDataset } from "./store"

export const API = (process.env.NEXT_PUBLIC_UPLIFT_API || "https://worker-production-47e0.up.railway.app").replace(/\/$/, "")
const KEY_STORE = "uplift-ads-view-key"
const RUN_STORE = "uplift-ads-run"

export type RunMeta = NonNullable<Dataset["run"]>
export type DataState = {
  ds: Dataset
  status: "demo" | "loading" | "live" | "error"
  error?: string
  runs: RunMeta[] // other runs the viewer can switch to (view key only)
}

const INITIAL: DataState = { ds: DEMO, status: "demo", runs: [] }
let state: DataState = INITIAL
let started = false
const listeners = new Set<() => void>()

function set(next: Partial<DataState>) {
  state = { ...state, ...next }
  bindDataset(state.ds)
  listeners.forEach((l) => l())
}

const read = (k: string) => {
  try {
    return window.localStorage.getItem(k) || ""
  } catch {
    return ""
  }
}
const write = (k: string, v: string | null) => {
  try {
    if (v) window.localStorage.setItem(k, v)
    else window.localStorage.removeItem(k)
  } catch {
    // storage blocked: the choice lasts for this page view
  }
}

function valid(d: unknown): d is Dataset {
  const x = d as Dataset
  return !!x && Array.isArray(x.KEYWORDS) && Array.isArray(x.CAMPAIGNS) && Array.isArray(x.HEADLINES) && !!x.PRODUCT
}

async function fetchRun(task: string | null, key: string, token: string) {
  const q = new URLSearchParams()
  if (task) q.set("task", task)
  if (key) q.set("key", key)
  if (token) q.set("t", token)
  set({ status: "loading", error: undefined })
  try {
    const r = await fetch(`${API}/ads/run?${q}`)
    if (!r.ok) throw new Error(r.status === 401 ? "This link or key is not valid." : r.status === 404 ? "No finished run with Google Ads output yet." : `Worker answered ${r.status}.`)
    const d = await r.json()
    if (!valid(d)) throw new Error("The run's data is incomplete.")
    write(RUN_STORE, JSON.stringify({ task: d.id, token }))
    set({ ds: d, status: "live" })
  } catch (e) {
    set({ ds: DEMO, status: "error", error: e instanceof Error ? e.message : "Could not load the run." })
  }
}

async function fetchRuns(key: string) {
  try {
    const r = await fetch(`${API}/ads/runs?key=${encodeURIComponent(key)}`)
    if (r.ok) set({ runs: (await r.json()).runs ?? [] })
  } catch {
    // the run list is a convenience; the current run still shows
  }
}

function start() {
  if (started || typeof window === "undefined") return
  started = true
  const url = new URL(window.location.href)
  const urlKey = url.searchParams.get("key")
  if (urlKey) {
    write(KEY_STORE, urlKey)
    url.searchParams.delete("key")
    window.history.replaceState(null, "", url.toString())
  }
  const key = urlKey || read(KEY_STORE)
  let task = url.searchParams.get("task")
  let token = url.searchParams.get("t") || ""
  if (!task && !key) {
    try {
      const saved = JSON.parse(read(RUN_STORE) || "null")
      if (saved?.task && saved?.token) ({ task, token } = saved)
    } catch {
      // ignore a malformed saved run
    }
  }
  if (!key && !(task && token)) return
  void fetchRun(task, key, token)
  if (key) void fetchRuns(key)
}

export const dataActions = {
  selectRun(task: string) {
    const key = read(KEY_STORE)
    const url = new URL(window.location.href)
    url.searchParams.set("task", task)
    url.searchParams.delete("t")
    window.history.replaceState(null, "", url.toString())
    void fetchRun(task, key, "")
  },
  latest() {
    const key = read(KEY_STORE)
    if (key) void fetchRun(null, key, "")
  },
  useKey(key: string) {
    write(KEY_STORE, key.trim())
    if (key.trim()) {
      void fetchRun(null, key.trim(), "")
      void fetchRuns(key.trim())
    }
  },
  showDemo() {
    write(RUN_STORE, null)
    write(KEY_STORE, null)
    const url = new URL(window.location.href)
    url.searchParams.delete("task")
    url.searchParams.delete("t")
    window.history.replaceState(null, "", url.toString())
    set({ ds: DEMO, status: "demo", error: undefined, runs: [] })
  },
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  start()
  return () => listeners.delete(cb)
}

export function useDataset(): DataState {
  return useSyncExternalStore(subscribe, () => state, () => INITIAL)
}
