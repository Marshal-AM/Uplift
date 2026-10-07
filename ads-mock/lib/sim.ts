// Deterministic mock performance: the same 30 days every time. Raw (uncapped) traffic is generated once from
// each keyword's demand, quality score and CTR; budgets are applied when totals are read, so raising a budget
// in the mock genuinely lifts clicks on budget-limited days.
import { ECONOMICS, KEYWORDS, OFFERS, PRODUCT, SEARCH_TERMS, type CampaignId } from "./data"

export const DAYS = 30

export type Metrics = { impressions: number; clicks: number; cost: number; conversions: number; value: number }
export const ZERO: Metrics = { impressions: 0, clicks: 0, cost: 0, conversions: 0, value: 0 }

function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const rand = mulberry32(20261007)
const jitter = (lo: number, hi: number) => lo + (hi - lo) * rand()

/** Dates for the 30 simulated days, ending yesterday. */
export function dayDates(now = new Date()): Date[] {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
  return Array.from({ length: DAYS }, (_, i) => new Date(end.getFullYear(), end.getMonth(), end.getDate() - (DAYS - 1 - i)))
}

const WEEKDAY = [1.12, 0.94, 0.97, 1, 0.98, 1.03, 1.15] // Sun..Sat
const dates = dayDates()

type Raw = Metrics
const searchRaw: Record<string, Raw>[] = []
const pmaxRaw: Raw[] = []

for (let d = 0; d < DAYS; d++) {
  const learning = Math.min(1, 0.55 + d * 0.09)
  const dow = WEEKDAY[dates[d].getDay()]
  const row: Record<string, Raw> = {}
  for (const k of KEYWORDS) {
    const impressions = k.demand * 3.4 * learning * dow * jitter(0.85, 1.15)
    const clicks = impressions * k.ctr * jitter(0.85, 1.15)
    const cpc = ECONOMICS.maxCpc * (0.95 - k.qualityScore * 0.035) * jitter(0.9, 1.1)
    const conversions = clicks * ECONOMICS.conversionRate * jitter(0.55, 1.45)
    row[k.text] = { impressions, clicks, cost: clicks * cpc, conversions, value: conversions * PRODUCT.price }
  }
  searchRaw.push(row)
  const impressions = 2600 * learning * dow * jitter(0.85, 1.15)
  const clicks = impressions * 0.012 * jitter(0.85, 1.15)
  const conversions = clicks * 0.022 * jitter(0.6, 1.4)
  pmaxRaw.push({ impressions, clicks, cost: clicks * 0.33 * jitter(0.9, 1.1), conversions, value: conversions * PRODUCT.price })
}

const scale = (m: Metrics, f: number): Metrics => ({
  impressions: m.impressions * f, clicks: m.clicks * f, cost: m.cost * f, conversions: m.conversions * f, value: m.value * f,
})
export const add = (a: Metrics, b: Metrics): Metrics => ({
  impressions: a.impressions + b.impressions, clicks: a.clicks + b.clicks, cost: a.cost + b.cost,
  conversions: a.conversions + b.conversions, value: a.value + b.value,
})
const sum = (ms: Metrics[]) => ms.reduce(add, ZERO)

export type SimInput = { day: number; enabled: Record<CampaignId, boolean>; budgets: Record<CampaignId, number> }

/** One simulated day of the Search campaign, per keyword, with the daily budget applied. */
function searchDay(d: number, budget: number) {
  const row = searchRaw[d]
  const cost = Object.values(row).reduce((a, m) => a + m.cost, 0)
  const f = cost > budget ? budget / cost : 1
  const out: Record<string, Metrics> = {}
  for (const [k, m] of Object.entries(row)) out[k] = scale(m, f)
  return { keywords: out, limited: f < 1, lostShare: 1 - f }
}

function pmaxDay(d: number, budget: number) {
  const m = pmaxRaw[d]
  const f = m.cost > budget ? budget / m.cost : 1
  return { total: scale(m, f), limited: f < 1 }
}

const live = (s: SimInput, id: CampaignId, d: number) => s.enabled[id] && d < s.day

export function keywordTotals(s: SimInput): Record<string, Metrics> {
  const out: Record<string, Metrics> = Object.fromEntries(KEYWORDS.map((k) => [k.text, ZERO]))
  for (let d = 0; d < DAYS; d++) {
    if (!live(s, "search", d)) continue
    const day = searchDay(d, s.budgets.search)
    for (const k of KEYWORDS) out[k.text] = add(out[k.text], day.keywords[k.text])
  }
  return out
}

export function campaignTotals(s: SimInput): Record<CampaignId, Metrics> {
  let pmax = ZERO
  for (let d = 0; d < DAYS; d++) if (live(s, "pmax", d)) pmax = add(pmax, pmaxDay(d, s.budgets.pmax).total)
  return { search: sum(Object.values(keywordTotals(s))), pmax }
}

/** Share of recent simulated days on which a campaign hit its budget (drives "Limited by budget"). */
export function limitedShare(s: SimInput, id: CampaignId): number {
  const days = Array.from({ length: DAYS }, (_, d) => d).filter((d) => live(s, id, d)).slice(-7)
  if (!days.length) return 0
  const hit = days.filter((d) => (id === "search" ? searchDay(d, s.budgets.search).limited : pmaxDay(d, s.budgets.pmax).limited))
  return hit.length / days.length
}

export function searchLostToBudget(s: SimInput): number {
  const days = Array.from({ length: DAYS }, (_, d) => d).filter((d) => live(s, "search", d))
  if (!days.length) return 0
  return days.reduce((a, d) => a + searchDay(d, s.budgets.search).lostShare, 0) / days.length
}

/** Account totals per day for the chart; days not yet simulated are null so the line grows as time passes. */
export function dailySeries(s: SimInput) {
  return dates.map((date, d) => {
    if (d >= s.day || (!s.enabled.search && !s.enabled.pmax)) return { date, m: null as Metrics | null }
    let m = ZERO
    if (s.enabled.search) m = add(m, sum(Object.values(searchDay(d, s.budgets.search).keywords)))
    if (s.enabled.pmax) m = add(m, pmaxDay(d, s.budgets.pmax).total)
    return { date, m }
  })
}

export function searchTermRows(s: SimInput) {
  const kw = keywordTotals(s)
  return SEARCH_TERMS.map((t) => ({ ...t, m: scale(kw[t.keyword], t.share) }))
}

export function adGroupTotals(s: SimInput): Record<string, Metrics> {
  const kw = keywordTotals(s)
  const out: Record<string, Metrics> = {}
  for (const k of KEYWORDS) out[k.adGroup] = add(out[k.adGroup] ?? ZERO, kw[k.text])
  return out
}

/** Performance Max traffic by network, for the Products and Overview pages. */
export const PMAX_CHANNELS = [
  { name: "Shopping ads", share: 0.62 },
  { name: "Search", share: 0.21 },
  { name: "Display", share: 0.09 },
  { name: "YouTube", share: 0.05 },
  { name: "Gmail & Discover", share: 0.03 },
]
export const pmaxChannel = (m: Metrics, share: number) => scale(m, share)

export const ourOffer = OFFERS.find((o) => o.ours)!

// Derived ratios, safe on zero.
export const ctr = (m: Metrics) => (m.impressions ? m.clicks / m.impressions : 0)
export const avgCpc = (m: Metrics) => (m.clicks ? m.cost / m.clicks : 0)
export const costPerConv = (m: Metrics) => (m.conversions ? m.cost / m.conversions : 0)
export const convRate = (m: Metrics) => (m.clicks ? m.conversions / m.clicks : 0)
export const roas = (m: Metrics) => (m.cost ? m.value / m.cost : 0)
