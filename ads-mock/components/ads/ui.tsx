"use client"
import { CalendarDays, ChevronDown, CircleAlert, CirclePause, FastForward, Info, Play, RotateCcw } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { MockBadge } from "@/components/brand"
import { count, decimal, money, pct, range } from "@/lib/format"
import { DAYS, avgCpc, costPerConv, ctr, dayDates, roas, type Metrics } from "@/lib/sim"
import { actions, useHydrated, useMock, type Status } from "@/lib/store"

export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  const hydrated = useHydrated()
  const dates = dayDates()
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h1 className="font-roboto text-[22px] text-[#202124]">{title}</h1>
      <div className="flex items-center gap-3">
        {children}
        <button className="flex items-center gap-2 rounded border border-[#dadce0] bg-white px-3 py-1.5 text-[13px] text-[#3c4043] hover:bg-[#f8f9fa]">
          <CalendarDays className="h-4 w-4 text-[#5f6368]" />
          <span className="font-medium">Last 30 days</span>
          <span className="text-[#5f6368]">{hydrated ? range(dates[0], dates[DAYS - 1]) : ""}</span>
          <ChevronDown className="h-4 w-4 text-[#5f6368]" />
        </button>
      </div>
    </div>
  )
}

export function Card({ title, action, children, className = "" }: { title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-[#dadce0] bg-white ${className}`}>
      {title && (
        <div className="flex items-center justify-between px-5 pb-2 pt-4">
          <h2 className="text-[16px] font-medium text-[#202124]">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export type Col = { label: string; right?: boolean; width?: string }

export function Table({ cols, rows, totals = [], empty }: { cols: Col[]; rows: React.ReactNode[][]; totals?: React.ReactNode[][]; empty?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-roboto text-[14px] text-[#202124]">
        <thead>
          <tr className="border-b border-[#dadce0]">
            {cols.map((c, i) => (
              <th
                key={i}
                style={{ width: c.width }}
                className={`whitespace-nowrap px-3 py-3 text-[12px] font-medium text-[#5f6368] ${c.right ? "text-right" : "text-left"}`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && empty && (
            <tr>
              <td colSpan={cols.length} className="px-3 py-8 text-center text-[#5f6368]">
                {empty}
              </td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-[#e8eaed] hover:bg-[#f8f9fa]">
              {r.map((cell, j) => (
                <td key={j} className={`whitespace-nowrap px-3 py-3 ${cols[j]?.right ? "text-right tabular-nums" : ""}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
          {totals.map((r, i) => (
            <tr key={`t${i}`} className="border-b border-[#e8eaed] bg-[#f8f9fa] text-[#3c4043]">
              {r.map((cell, j) => (
                <td key={j} className={`whitespace-nowrap px-3 py-2.5 font-medium ${cols[j]?.right ? "text-right tabular-nums" : ""}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** A campaign name that may be long: the start truncates, the type at the end (" · Search") always shows. */
export function CampaignName({ name, max = 300, className = "" }: { name: string; max?: number; className?: string }) {
  const parts = name.split(" · ")
  const tail = parts.length > 1 ? parts.pop() : null
  return (
    <span title={name} className={`flex min-w-0 items-baseline ${className}`} style={{ maxWidth: max }}>
      <span className="truncate">{parts.join(" · ")}</span>
      {tail && <span className="shrink-0 whitespace-pre"> · {tail}</span>}
    </span>
  )
}

/** The standard Google Ads metric columns, with "—" where a ratio has no data yet. */
export const METRIC_COLS: Col[] = [
  { label: "Impr.", right: true },
  { label: "Clicks", right: true },
  { label: "CTR", right: true },
  { label: "Avg. CPC", right: true },
  { label: "Cost", right: true },
  { label: "Conversions", right: true },
  { label: "Cost / conv.", right: true },
  { label: "Conv. value / cost", right: true },
]

export const metricCells = (m: Metrics): React.ReactNode[] => [
  count(m.impressions),
  count(m.clicks),
  m.impressions ? pct(ctr(m)) : "—",
  m.clicks ? money(avgCpc(m)) : "—",
  money(m.cost),
  decimal(m.conversions),
  m.conversions ? money(costPerConv(m)) : "—",
  m.cost ? decimal(roas(m)) : "—",
]

export function StatusDot({ status, onChange }: { status: Status; onChange?: (s: Status) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener("mousedown", close)
    return () => document.removeEventListener("mousedown", close)
  }, [])
  return (
    <div ref={ref} className="relative inline-block">
      <button
        aria-label={`Status: ${status}`}
        onClick={() => onChange && setOpen(!open)}
        className="flex items-center gap-0.5 rounded p-1 hover:bg-[#f1f3f4]"
      >
        {status === "Enabled" ? (
          <span className="block h-3 w-3 rounded-full bg-[#1e8e3e]" />
        ) : (
          <CirclePause className="h-4 w-4 text-[#5f6368]" />
        )}
        {onChange && <ChevronDown className="h-3 w-3 text-[#5f6368]" />}
      </button>
      {open && onChange && (
        <div className="absolute left-0 top-8 z-30 w-40 rounded-md bg-white py-1.5 shadow-[0_2px_6px_2px_rgba(60,64,67,0.15),0_1px_2px_rgba(60,64,67,0.3)]">
          {(["Enabled", "Paused"] as Status[]).map((s) => (
            <button
              key={s}
              onClick={() => {
                onChange(s)
                setOpen(false)
              }}
              className="flex w-full items-center gap-3 px-4 py-2 text-left text-[14px] text-[#202124] hover:bg-[#f1f3f4]"
            >
              {s === "Enabled" ? <span className="block h-3 w-3 rounded-full bg-[#1e8e3e]" /> : <CirclePause className="h-4 w-4 text-[#5f6368]" />}
              {s === "Enabled" ? "Enable" : "Pause"}
            </button>
          ))}
          <div className="mx-4 my-1 border-t border-[#e8eaed]" />
          <span className="block px-4 py-2 text-[14px] text-[#9aa0a6]">Remove</span>
        </div>
      )}
    </div>
  )
}

export function StatusText({ status, learning, limited }: { status: Status; learning?: boolean; limited?: boolean }) {
  if (status === "Paused") return <span className="text-[#5f6368]">Paused</span>
  if (limited)
    return (
      <span className="inline-flex items-center gap-1 text-[#202124]">
        Limited by budget <Info className="h-3.5 w-3.5 text-[#5f6368]" />
      </span>
    )
  return <span className="text-[#202124]">{learning ? "Eligible (Learning)" : "Eligible"}</span>
}

/** The mock's time-lapse control. Not part of real Google Ads, so it is styled and labelled as the mock. */
export function SimBar() {
  const s = useMock()
  const enabled = Object.values(s.status).some((v) => v === "Enabled")
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-[#f9d97c] bg-[#fef7e0] px-4 py-2.5 font-roboto text-[13px] text-[#3c4043]">
      <MockBadge />
      {!enabled ? (
        <>
          <span className="flex items-center gap-1.5">
            <CircleAlert className="h-4 w-4 text-[#e37400]" />
            Your campaigns were created paused by Uplift. Enable them to simulate 30 days of mock traffic.
          </span>
          <button
            onClick={actions.enableAll}
            className="ml-auto rounded-full bg-[#1a73e8] px-4 py-1.5 font-medium text-white hover:bg-[#1765cc]"
          >
            Enable all campaigns
          </button>
        </>
      ) : (
        <>
          <span className="font-medium">
            {s.running ? `Simulating day ${s.day} of ${DAYS}` : s.day >= DAYS ? `Simulated ${DAYS} days of traffic` : `Paused at day ${s.day} of ${DAYS}`}
          </span>
          <div className="h-1.5 min-w-[120px] flex-1 overflow-hidden rounded-full bg-[#f6e3a6]">
            <div className="h-full rounded-full bg-[#e37400] transition-[width]" style={{ width: `${(s.day / DAYS) * 100}%` }} />
          </div>
          <span className="flex items-center gap-1">
            {s.running ? (
              <SimButton icon={<CirclePause className="h-4 w-4" />} label="Pause" onClick={actions.pause} />
            ) : s.day < DAYS ? (
              <SimButton icon={<Play className="h-4 w-4" />} label="Resume" onClick={actions.resume} />
            ) : null}
            {s.day < DAYS && <SimButton icon={<FastForward className="h-4 w-4" />} label="Skip to day 30" onClick={actions.skip} />}
            <SimButton icon={<RotateCcw className="h-4 w-4" />} label="Replay" onClick={actions.replay} />
          </span>
        </>
      )}
    </div>
  )
}

function SimButton({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1 rounded px-2 py-1 font-medium text-[#1a73e8] hover:bg-[#fdefc3]">
      {icon}
      {label}
    </button>
  )
}

export function Toolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-[#dadce0] px-4 py-2.5">
      <button
        aria-label="New (mock)"
        className="flex h-10 w-10 items-center justify-center rounded-full bg-[#1a73e8] text-[24px] font-light leading-none text-white shadow hover:bg-[#1765cc]"
      >
        +
      </button>
      <span className="rounded border border-[#dadce0] px-2.5 py-1 text-[13px] text-[#3c4043]">Status: All but removed</span>
      <span className="text-[13px] font-medium text-[#1a73e8]">Add filter</span>
      <span className="ml-auto flex items-center gap-2">{children}</span>
    </div>
  )
}
