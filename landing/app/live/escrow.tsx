"use client"

import { useEffect, useState } from "react"
import { ArrowUpRight, Link2 } from "lucide-react"

/* The Task's Masumi escrow on Cardano: what was locked, every on-chain transaction (with explorer links) and the
   escrow's deadlines, read live by the Uplift Worker from its payment node. */

export type EscrowTx = {
  state: string
  label: string
  status: string
  tx: string
  block: number | null
  at: number | null
  confirmations: number | null
  fee_lovelace: string | null
}
export type Escrow = {
  amount: number
  unit: string
  state: string | null
  state_label: string
  network: string
  blockchain_id: string
  contract: string | null
  explorer: string
  created: number | null
  pay_by: number | null
  result_by: number | null
  unlock: number | null
  dispute_until: number | null
  transactions: EscrowTx[]
}

export function useEscrow(api: string, task: string | null, key: string, refreshKey: number) {
  const [escrow, setEscrow] = useState<Escrow | null>(null)
  useEffect(() => {
    setEscrow(null)
    if (!task || !key) return
    let alive = true
    const load = async () => {
      try {
        const r = await fetch(`${api}/trace/escrow?task=${encodeURIComponent(task)}&key=${encodeURIComponent(key)}`)
        if (r.ok && alive) setEscrow((await r.json()).escrow ?? null)
      } catch {}
    }
    load()
    const t = setInterval(load, 10000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [api, task, key, refreshKey])
  return escrow
}

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
const short = (h: string) => `${h.slice(0, 8)}…${h.slice(-6)}`

function until(ms: number, now: number) {
  const m = Math.round((ms - now) / 60000)
  if (m <= 0) return "passed"
  return m < 60 ? `in ${m} min` : `in ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`
}

const PAID = new Set(["Withdrawn", "RefundWithdrawn", "DisputedWithdrawn"])

export function EscrowCard({ escrow, now }: { escrow: Escrow | null; now: number }) {
  if (!escrow) return null
  const tone = PAID.has(escrow.state ?? "") ? "var(--ok)" : escrow.state ? "var(--run)" : "var(--wait)"
  const locked = escrow.transactions.some((t) => t.state === "FundsLocked")
  const paidOut = escrow.transactions.some((t) => PAID.has(t.state))
  return (
    <section className="lv-card lv-esc">
      <h3>
        <Link2 size={14} /> Escrow on Cardano
        <span className="lv-esc-pill" style={{ ["--c" as any]: tone }}>{escrow.state_label}</span>
      </h3>
      <div className="lv-esc-amount">
        <span className="lv-mono">{escrow.amount}</span> {escrow.unit}
        <small> · {escrow.amount} Sokosumi credits, locked by the buyer</small>
      </div>
      <ol className="lv-esc-steps">
        <li className="done">
          <div className="t">Payment requested</div>
          <div className="s">
            {escrow.created ? clock(escrow.created) : ""}
            {escrow.pay_by && !locked ? ` · must be locked by ${clock(escrow.pay_by)}` : ""}
          </div>
        </li>
        {escrow.transactions.map((t) => (
          <li key={t.tx} className={t.status === "Confirmed" ? "done" : "active"}>
            <div className="t">{t.label}</div>
            <div className="s">
              {t.at ? clock(t.at) : ""}
              {t.block ? ` · block ${t.block.toLocaleString()}` : t.status !== "Confirmed" ? " · confirming…" : ""}
            </div>
            <a className="lv-esc-tx lv-mono" href={`${escrow.explorer}/tx/${t.tx}`} target="_blank" rel="noreferrer">
              tx {short(t.tx)} <ArrowUpRight size={12} />
            </a>
          </li>
        ))}
        {!locked && (
          <li className="active">
            <div className="t">Waiting for the lock on-chain</div>
            <div className="s">the buyer&apos;s wallet sends the funds to the escrow contract</div>
          </li>
        )}
        {locked && !paidOut && escrow.unlock && (
          <li className="pending">
            <div className="t">Unlocks for payout</div>
            <div className="s">
              {clock(escrow.unlock)} · {until(escrow.unlock, now)}
              {escrow.state !== "ResultSubmitted" && escrow.result_by ? ` · result due by ${clock(escrow.result_by)}` : ""}
            </div>
          </li>
        )}
      </ol>
      {escrow.contract && (
        <div className="lv-src">
          Masumi escrow contract on {escrow.network} ·{" "}
          <a className="lv-mono" href={`${escrow.explorer}/address/${escrow.contract}`} target="_blank" rel="noreferrer">
            {short(escrow.contract)}
          </a>{" "}
          · payment <span className="lv-mono">{escrow.blockchain_id}</span>
        </div>
      )}
    </section>
  )
}
