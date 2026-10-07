"use client"
// The mock account's state: campaign status, budgets, the simulation clock and applied recommendations. Kept in
// localStorage per dataset (the demo store, or one Uplift run), so it survives page changes and reloads and a run
// never inherits another's state; every read and write tolerates storage being unavailable.
import { useSyncExternalStore } from "react"
import { DEMO, type CampaignId, type Dataset } from "./data"
import { DAYS, type SimInput } from "./sim"

export type Status = "Enabled" | "Paused"

export type MockState = {
  status: Record<CampaignId, Status>
  budgets: Record<CampaignId, number>
  day: number // simulated days elapsed (0–30)
  running: boolean
  applied: string[]
}

const KEY = "uplift-ads-mock-v2"
const TICK_MS = 170

/** Campaigns arrive paused, as Uplift creates them, at the daily budgets its ads specialist set. */
function defaults(ds: Dataset): MockState {
  const budgets = { search: 0, pmax: 0 } as Record<CampaignId, number>
  for (const c of ds.CAMPAIGNS) budgets[c.id] = c.budget
  return { status: { search: "Paused", pmax: "Paused" }, budgets, day: 0, running: false, applied: [] }
}

export const DEFAULT_STATE = defaults(DEMO)

let dsId = DEMO.id
let present = new Set<CampaignId>(DEMO.CAMPAIGNS.map((c) => c.id))
let fresh = DEFAULT_STATE
let state: MockState = DEFAULT_STATE
let loaded = false
let timer: ReturnType<typeof setInterval> | null = null
const listeners = new Set<() => void>()

function load() {
  if (typeof window === "undefined") return
  loaded = true
  try {
    const raw = window.localStorage.getItem(`${KEY}:${dsId}`)
    state = raw ? { ...fresh, ...JSON.parse(raw) } : fresh
  } catch {
    state = fresh
  }
  sync()
}

function save() {
  try {
    window.localStorage.setItem(`${KEY}:${dsId}`, JSON.stringify(state))
  } catch {
    // private mode or blocked storage: the mock still works for this page view
  }
}

function notify() {
  listeners.forEach((l) => l())
}

function set(next: Partial<MockState>) {
  state = { ...state, ...next }
  save()
  sync()
  notify()
}

/** Called when the dataset changes: switch to that dataset's saved state (or a fresh, paused account). */
export function bindDataset(ds: Dataset) {
  if (ds.id === dsId) return
  dsId = ds.id
  present = new Set(ds.CAMPAIGNS.map((c) => c.id))
  fresh = defaults(ds)
  state = { ...fresh, running: false }
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (loaded) load()
  notify()
}

/** Start or stop the time-lapse ticker to match `state.running`. */
function sync() {
  if (state.running && !timer) {
    timer = setInterval(() => {
      const day = Math.min(DAYS, state.day + 1)
      set({ day, running: day < DAYS })
    }, TICK_MS)
  } else if (!state.running && timer) {
    clearInterval(timer)
    timer = null
  }
}

const anyEnabled = (s: Record<CampaignId, Status>) => Object.values(s).some((v) => v === "Enabled")

export const actions = {
  /** Any status change restarts the 30-day simulation for the campaigns now enabled. */
  setStatus(id: CampaignId, value: Status) {
    if (!present.has(id)) return
    const status = { ...state.status, [id]: value }
    set({ status, day: 0, running: anyEnabled(status) })
  },
  enableAll() {
    const status = { search: present.has("search") ? "Enabled" : "Paused", pmax: present.has("pmax") ? "Enabled" : "Paused" } as Record<CampaignId, Status>
    set({ status, day: 0, running: anyEnabled(status) })
  },
  setBudget(id: CampaignId, value: number) {
    set({ budgets: { ...state.budgets, [id]: value }, day: anyEnabled(state.status) ? 0 : state.day, running: anyEnabled(state.status) })
  },
  replay() {
    if (anyEnabled(state.status)) set({ day: 0, running: true })
  },
  skip() {
    if (anyEnabled(state.status)) set({ day: DAYS, running: false })
  },
  pause() {
    set({ running: false })
  },
  resume() {
    if (anyEnabled(state.status) && state.day < DAYS) set({ running: true })
  },
  apply(id: string) {
    if (!state.applied.includes(id)) set({ applied: [...state.applied, id] })
  },
  reset() {
    set({ ...fresh })
  },
}

function subscribe(cb: () => void) {
  if (!loaded) load()
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function useMock(): MockState {
  return useSyncExternalStore(subscribe, () => state, () => DEFAULT_STATE)
}

export function simInput(s: MockState): SimInput {
  return {
    day: s.day,
    enabled: { search: s.status.search === "Enabled", pmax: s.status.pmax === "Enabled" },
    budgets: s.budgets,
  }
}

/** True after the first client render; used for anything that depends on the viewer's clock. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  )
}
