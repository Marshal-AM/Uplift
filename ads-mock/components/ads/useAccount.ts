"use client"
import { useMemo } from "react"
import { useDataset } from "@/lib/dataset"
import {
  DAYS, adGroupTotals, add, campaignTotals, dailySeries, keywordTotals, limitedShare, searchLostToBudget, searchTermRows,
} from "@/lib/sim"
import { simInput, useMock } from "@/lib/store"

/** Everything an Ads page needs, recomputed only when the dataset or the mock state changes. */
export function useAccount() {
  const s = useMock()
  const { ds } = useDataset()
  return useMemo(() => {
    const input = simInput(s)
    const campaigns = campaignTotals(ds, input)
    return {
      ds,
      s,
      input,
      campaigns,
      account: add(campaigns.search, campaigns.pmax),
      keywords: keywordTotals(ds, input),
      adGroups: adGroupTotals(ds, input),
      terms: searchTermRows(ds, input),
      series: dailySeries(ds, input),
      limited: { search: limitedShare(ds, input, "search") >= 0.4, pmax: limitedShare(ds, input, "pmax") >= 0.4 },
      lostToBudget: searchLostToBudget(ds, input),
      learning: s.day > 0 && s.day < 7,
      done: s.day >= DAYS,
    }
  }, [s, ds])
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
