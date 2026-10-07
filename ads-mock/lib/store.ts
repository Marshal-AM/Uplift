"use client"
// The mock account's state: campaign status, budgets, the simulation clock and applied recommendations. Kept in
// localStorage so it survives page changes and reloads; every read and write tolerates storage being unavailable.
import { useSyncExternalStore } from "react"
import { CAMPAIGNS, type CampaignId } from "./data"
import { DAYS, type SimInput } from "./sim"

export type Status = "Enabled" | "Paused"

export type MockState = {
  status: Record<CampaignId, Status>
  budgets: Record<CampaignId, number>
  day: number // simulated days elapsed (0–30)
  running: boolean
  applied: string[]
}

const KEY = "uplift-ads-mock-v1"
const TICK_MS = 170

export const DEFAULT_STATE: MockState = {
  status: { search: "Paused", pmax: "Paused" },
  budgets: Object.fromEntries(CAMPAIGNS.map((c) => [c.id, c.budget])) as Record<CampaignId, number>,
  day: 0,
  running: false,
  applied: [],
}

let state: MockState = DEFAULT_STATE
let loaded = false
let timer: ReturnType<typeof setInterval> | null = null
const listeners = new Set<() => void>()

function load() {
  if (loaded || typeof window === "undefined") return
  loaded = true
  try {
    const raw = window.localStorage.getItem(KEY)
    if (raw) state = { ...DEFAULT_STATE, ...JSON.parse(raw) }
  } catch {
    state = DEFAULT_STATE
  }
  sync()
}

function save() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state))
  } catch {
    // private mode or blocked storage: the mock still works for this page view
  }
}

function set(next: Partial<MockState>) {
  state = { ...state, ...next }
  save()
  sync()
  listeners.forEach((l) => l())
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
    const status = { ...state.status, [id]: value }
    set({ status, day: 0, running: anyEnabled(status) })
  },
  enableAll() {
    const status = { search: "Enabled", pmax: "Enabled" } as Record<CampaignId, Status>
    set({ status, day: 0, running: true })
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
    set({ ...DEFAULT_STATE })
  },
}

function subscribe(cb: () => void) {
  load()
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
