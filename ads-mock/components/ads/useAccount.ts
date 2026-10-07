"use client"
import { useMemo } from "react"
import { CAMPAIGNS } from "@/lib/data"
import {
  DAYS, adGroupTotals, add, campaignTotals, dailySeries, keywordTotals, limitedShare, searchLostToBudget, searchTermRows,
} from "@/lib/sim"
import { simInput, useMock } from "@/lib/store"

/** Everything an Ads page needs, recomputed only when the mock state changes. */
export function useAccount() {
  const s = useMock()
  return useMemo(() => {
    const input = simInput(s)
    const campaigns = campaignTotals(input)
    return {
      s,
      input,
      campaigns,
      account: add(campaigns.search, campaigns.pmax),
      keywords: keywordTotals(input),
      adGroups: adGroupTotals(input),
      terms: searchTermRows(input),
      series: dailySeries(input),
      limited: Object.fromEntries(CAMPAIGNS.map((c) => [c.id, limitedShare(input, c.id) >= 0.4])) as Record<"search" | "pmax", boolean>,
      lostToBudget: searchLostToBudget(input),
      learning: s.day > 0 && s.day < 7,
      done: s.day >= DAYS,
    }
  }, [s])
}

/** Optimization score: starts at 71.4% and rises with each applied recommendation, as in Google Ads. */
export const RECOMMENDATIONS = [
  { id: "enable", points: 9.2 },
  { id: "budget", points: 8.1 },
  { id: "headlines", points: 4.6 },
  { id: "troas", points: 3.9 },
  { id: "negatives", points: 2.8 },
] as const

export function optimizationScore(applied: string[], enabled: boolean) {
  const base = 71.4
  const gained = RECOMMENDATIONS.filter((r) => applied.includes(r.id) || (r.id === "enable" && enabled)).reduce(
    (a, r) => a + r.points,
    0,
  )
  return Math.min(100, base + gained)
}
