"use client"
import Link from "next/link"
import { useState } from "react"
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Card, PageHeader, SimBar, Table } from "@/components/ads/ui"
import { optimizationScore, useAccount } from "@/components/ads/useAccount"
import { CAMPAIGNS } from "@/lib/data"
import { count, decimal, money, pct, shortDate } from "@/lib/format"
import { PMAX_CHANNELS, avgCpc, ctr, type Metrics } from "@/lib/sim"
import { useHydrated } from "@/lib/store"

const METRICS: { key: string; label: string; get: (m: Metrics) => number; fmt: (n: number) => string }[] = [
  { key: "clicks", label: "Clicks", get: (m) => m.clicks, fmt: count },
  { key: "impressions", label: "Impressions", get: (m) => m.impressions, fmt: count },
  { key: "cpc", label: "Avg. CPC", get: avgCpc, fmt: money },
  { key: "cost", label: "Cost", get: (m) => m.cost, fmt: money },
  { key: "conversions", label: "Conversions", get: (m) => m.conversions, fmt: decimal },
  { key: "value", label: "Conv. value", get: (m) => m.value, fmt: money },
]
const COLORS = ["#1a73e8", "#d93025", "#f9ab00", "#188038"]

export function Overview() {
  const a = useAccount()
  const hydrated = useHydrated()
  const [selected, setSelected] = useState(["clicks", "impressions"])
  const colorOf = (k: string) => COLORS[selected.indexOf(k)] ?? "transparent"
  const data = a.series.map((d) => ({
    date: hydrated ? shortDate(d.date) : "",
    ...Object.fromEntries(METRICS.map((m) => [m.key, d.m ? Number(m.get(d.m).toFixed(2)) : null])),
  }))
  const toggle = (k: string) =>
    setSelected((cur) => (cur.includes(k) ? (cur.length > 1 ? cur.filter((x) => x !== k) : cur) : [...cur, k].slice(-4)))
  const score = optimizationScore(a.s.applied, Object.values(a.s.status).includes("Enabled"))
  const topTerms = [...a.terms].filter((t) => !t.excluded).sort((x, y) => y.m.clicks - x.m.clicks).slice(0, 5)
  const topKeywords = Object.entries(a.keywords).sort((x, y) => y[1].clicks - x[1].clicks).slice(0, 5)

  return (
    <>
      <PageHeader title="Overview" />
      <SimBar />
      <Card className="mb-5 overflow-hidden">
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6">
          {METRICS.map((m) => {
            const on = selected.includes(m.key)
            return (
              <button
                key={m.key}
                onClick={() => toggle(m.key)}
                className="border-b border-r border-[#e8eaed] px-5 py-3 text-left"
                style={{ borderTop: `4px solid ${on ? colorOf(m.key) : "transparent"}`, background: on ? "#fff" : "#f8f9fa" }}
              >
                <div className="text-[12px] font-medium text-[#5f6368]">{m.label}</div>
                <div className="mt-1 text-[24px] text-[#202124]">{m.fmt(m.get(a.account))}</div>
              </button>
            )
          })}
        </div>
        <div className="h-[260px] px-2 pb-2 pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ left: 8, right: 8, top: 4, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#e8eaed" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#5f6368" }} tickLine={false} axisLine={{ stroke: "#dadce0" }} interval={4} />
              {selected.map((k, i) => (
                <YAxis
                  key={k}
                  yAxisId={k}
                  orientation={i % 2 ? "right" : "left"}
                  hide={i > 1}
                  tick={{ fontSize: 11, fill: "#5f6368" }}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                />
              ))}
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 4,
                  border: "none",
                  boxShadow: "0 1px 3px rgba(60,64,67,.3),0 4px 8px 3px rgba(60,64,67,.15)",
                }}
                formatter={(v: number, name: string) => {
                  const m = METRICS.find((x) => x.key === name)!
                  return [m.fmt(v), m.label]
                }}
              />
              {selected.map((k) => (
                <Line key={k} yAxisId={k} dataKey={k} stroke={colorOf(k)} strokeWidth={2} dot={false} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Campaigns" action={<ViewAll href="/ads/campaigns/" />}>
          <Table
            cols={[{ label: "Campaign" }, { label: "Cost", right: true }, { label: "Clicks", right: true }, { label: "CTR", right: true }]}
            rows={CAMPAIGNS.map((c) => {
              const m = a.campaigns[c.id]
              return [
                <span key="n" className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${a.s.status[c.id] === "Enabled" ? "bg-[#1e8e3e]" : "bg-[#9aa0a6]"}`} />
                  <Link href="/ads/campaigns/" className="max-w-[260px] truncate text-[#1a73e8] hover:underline">
                    {c.name}
                  </Link>
                </span>,
                money(m.cost),
                count(m.clicks),
                m.impressions ? pct(ctr(m)) : "—",
              ]
            })}
          />
        </Card>
        <Card title="Optimization score" action={<ViewAll href="/ads/recommendations/" label="View recommendations" />}>
          <div className="flex items-center gap-6 px-5 pb-5 pt-2">
            <ScoreRing value={score} />
            <p className="text-[14px] leading-[20px] text-[#5f6368]">
              Your account can perform better. Apply recommendations to raise your optimization score; each shows its
              estimated impact. <span className="text-[#9aa0a6]">(mock)</span>
            </p>
          </div>
        </Card>
        <Card title="Search terms" action={<ViewAll href="/ads/search-terms/" />}>
          <Table
            cols={[{ label: "Search term" }, { label: "Clicks", right: true }, { label: "Impr.", right: true }]}
            rows={topTerms.map((t) => [t.term, count(t.m.clicks), count(t.m.impressions)])}
          />
        </Card>
        <Card title="Search keywords" action={<ViewAll href="/ads/keywords/" />}>
          <Table
            cols={[{ label: "Keyword" }, { label: "Clicks", right: true }, { label: "Cost", right: true }]}
            rows={topKeywords.map(([k, m]) => [k, count(m.clicks), money(m.cost)])}
          />
        </Card>
        <Card title="Performance Max: where your ads showed" className="xl:col-span-2">
          <div className="space-y-3 px-5 pb-5 pt-2">
            {PMAX_CHANNELS.map((c) => (
              <div key={c.name} className="flex items-center gap-4 text-[14px]">
                <span className="w-36 shrink-0 text-[#3c4043]">{c.name}</span>
                <div className="h-2.5 flex-1 rounded-full bg-[#e8eaed]">
                  <div className="h-full rounded-full bg-[#1a73e8]" style={{ width: `${c.share * 100}%` }} />
                </div>
                <span className="w-28 text-right tabular-nums text-[#5f6368]">{count(a.campaigns.pmax.impressions * c.share)} impr.</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}

function ViewAll({ href, label = "View all" }: { href: string; label?: string }) {
  return (
    <Link href={href} className="text-[14px] font-medium text-[#1a73e8] hover:underline">
      {label}
    </Link>
  )
}

export function ScoreRing({ value, size = 96 }: { value: number; size?: number }) {
  const r = 40
  const c = 2 * Math.PI * r
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className="shrink-0" role="img" aria-label={`Optimization score ${value.toFixed(1)}%`}>
      <circle cx="50" cy="50" r={r} fill="none" stroke="#e8eaed" strokeWidth="8" />
      <circle
        cx="50"
        cy="50"
        r={r}
        fill="none"
        stroke="#1a73e8"
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={`${(value / 100) * c} ${c}`}
        transform="rotate(-90 50 50)"
      />
      <text x="50" y="56" textAnchor="middle" fontSize="18" fill="#202124" fontFamily="Roboto, Arial">
        {value.toFixed(1)}%
      </text>
    </svg>
  )
}
