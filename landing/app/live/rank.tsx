"use client"

import { useEffect, useState } from "react"
import { ShoppingBag, X } from "lucide-react"

/* The Task product's store-search rank at the start of the run and after it ends, checked by the Uplift Worker
   against Shopify's Admin API (products search, sorted by relevance) with the store's own access token. */

export type RankRow = { phrase: string; rank: number | null; results: number; ahead: string[] }
export type RankCheck = {
  checked_at: number
  product: Record<string, any>
  phrases: string[]
  ranks: RankRow[]
  endpoint: string
  query: string
  shop: string
}
export type Ranks = { start: RankCheck | null; end: RankCheck | null }

const TOP = 50
const fmt = (r: number | null | undefined) => (r ? `#${r}` : `not in top ${TOP}`)
const time = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })

export function useRanks(api: string, task: string | null, key: string, refreshKey: number) {
  const [ranks, setRanks] = useState<Ranks | null>(null)
  useEffect(() => {
    setRanks(null)
    if (!task || !key) return
    let alive = true
    const load = async () => {
      try {
        const r = await fetch(`${api}/trace/ranks?task=${encodeURIComponent(task)}&key=${encodeURIComponent(key)}`)
        if (r.ok && alive) setRanks(await r.json())
      } catch {}
    }
    load()
    const t = setInterval(load, 6000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [api, task, key, refreshKey])
  return ranks
}

function summary(c: RankCheck) {
  const found = c.ranks.filter((r) => r.rank).length
  const top = c.ranks.filter((r) => r.rank === 1).length
  return { found, top, total: c.ranks.length }
}

function Move({ from, to }: { from: number | null | undefined; to: number | null | undefined }) {
  const a = from ?? TOP + 1
  const b = to ?? TOP + 1
  if (b < a) return <span className="lv-up">▲</span>
  if (b > a) return <span className="lv-down">▼</span>
  return null
}

/** What the trace says about a check that has no stored result yet. */
export type CheckState = "none" | "running" | "failed"

const Spin = () => <span className="lv-spin" style={{ display: "inline-block", width: 12, height: 12, marginRight: 6 }} />

export function RankCard({ ranks, startState, endState, finished, onOpen }: { ranks: Ranks | null; startState: CheckState; endState: CheckState; finished: boolean; onOpen: () => void }) {
  const start = ranks?.start
  const end = ranks?.end
  if (!start && !end && startState === "none" && endState === "none") return null
  const product = (end ?? start)?.product
  const s = start ? summary(start) : null
  const e = end ? summary(end) : null
  const endRank = (phrase: string) => end?.ranks.find((r) => r.phrase.toLowerCase() === phrase.toLowerCase())?.rank
  const src = end ?? start
  return (
    <div
      className="lv-card lv-rank"
      role="button"
      tabIndex={0}
      aria-label="Open the store-search rank details"
      onClick={() => (start || end) && onOpen()}
      onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && (start || end) && (ev.preventDefault(), onOpen())}
    >
      <h3 className="lv-rank-head">
        <ShoppingBag size={14} /> Store-search rank
        {(start || end) && <span className="open">Details →</span>}
      </h3>
      {product && <div className="lv-rank-product">{product.title}</div>}
      <div className="lv-rank-cols">
        <div className={`lv-rank-col ${s ? "" : "pending"}`}>
          <div className="k">At the start</div>
          {s ? (
            <>
              <div className="big lv-mono">{s.found}<small>/{s.total} found</small></div>
              <div className="sub">#1 for {s.top}</div>
            </>
          ) : (
            <div className="big">{startState === "running" ? <><Spin />checking…</> : "not recorded"}</div>
          )}
        </div>
        <div className={`lv-rank-col ${e ? "" : "pending"}`}>
          <div className="k">After the run</div>
          {e ? (
            <>
              <div className="big lv-mono">{e.found}<small>/{e.total} found</small> {s && <Move from={s.total - s.found} to={e.total - e.found} />}</div>
              <div className="sub">#1 for {e.top}</div>
            </>
          ) : (
            <div className="big">
              {endState === "running" || (finished && endState === "none") ? <><Spin />checking…</> : endState === "failed" ? "not recorded" : "when it ends"}
            </div>
          )}
        </div>
      </div>
      {start && (
        <div className="lv-rank-list">
          {start.ranks.slice(0, 6).map((r) => (
            <div className="lv-rank-li" key={r.phrase}>
              <span className="p">{r.phrase}</span>
              <span className="r lv-mono">
                {fmt(r.rank).replace(`not in top ${TOP}`, "—")}
                {end && <> → {fmt(endRank(r.phrase)).replace(`not in top ${TOP}`, "—")} <Move from={r.rank} to={endRank(r.phrase)} /></>}
              </span>
            </div>
          ))}
        </div>
      )}
      {src && (
        <div className="lv-src">
          Live from the <b>Shopify Admin API</b> · <span className="lv-mono">{src.endpoint}</span>
        </div>
      )}
    </div>
  )
}

function money(v: any, cur = "") {
  return v === null || v === undefined || v === "" ? "—" : `${Number(v).toFixed(2)} ${cur}`.trim()
}

function detailRows(p: Record<string, any>): [string, string][] {
  const price = p.priceRangeV2
  const lo = price?.minVariantPrice?.amount
  const hi = price?.maxVariantPrice?.amount
  const cur = price?.minVariantPrice?.currencyCode ?? ""
  const variants: any[] = p.variants?.nodes ?? []
  const cost = variants.map((v) => v?.inventoryItem?.unitCost?.amount).find((x) => x != null)
  const margin = cost && lo && Number(lo) ? ` · margin ${Math.round(100 * (1 - Number(cost) / Number(lo)))}%` : ""
  return [
    ["Title", p.title ?? "—"],
    ["Handle", p.handle ?? "—"],
    ["Product ID", `${p.legacyResourceId ?? "—"} (${String(p.status ?? "").toLowerCase()})`],
    ["SKU", variants.map((v) => v?.sku).filter(Boolean).join(", ") || "—"],
    ["Price", price ? (lo === hi ? money(lo, cur) : `${money(lo)}–${money(hi, cur)}`) + (cost ? ` · cost ${money(cost, cur)}${margin}` : "") : "—"],
    ["Vendor / type", `${p.vendor || "—"} / ${p.productType || "—"}`],
    ["Category", p.category?.fullName ?? "—"],
    ["Collections", (p.collections?.nodes ?? []).map((c: any) => c.title).join(", ") || "—"],
    ["Tags", (p.tags ?? []).join(", ") || "—"],
    ["Images", p.media ? String(p.media.nodes.length) : "—"],
    ["SEO title", p.seo?.title || "— (uses the product title)"],
    ["SEO description", p.seo?.description || "—"],
    ["Store URL", p.onlineStoreUrl || "— (not on the Online Store)"],
  ]
}

export function RankModal({ ranks, onClose }: { ranks: Ranks; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])
  const { start, end } = ranks
  const latest = (end ?? start)!
  const before = start && end ? Object.fromEntries(detailRows(start.product)) : null
  const phrases = (start ?? end)!.ranks.map((r) => r.phrase)
  const at = (c: RankCheck | null, phrase: string) => c?.ranks.find((r) => r.phrase.toLowerCase() === phrase.toLowerCase())
  const s = start ? summary(start) : null
  const e = end ? summary(end) : null
  return (
    <div className="lv-backdrop" onClick={onClose} role="presentation">
      <div className="lv-modal" role="dialog" aria-modal="true" aria-label="Store-search rank" onClick={(ev) => ev.stopPropagation()}>
        <div className="lv-modal-top">
          <div style={{ minWidth: 0 }}>
            <div className="s">Store-search rank</div>
            <h2 className="lv-h">{latest.product.title}</h2>
            <div className="s lv-mono">{latest.product.handle} · {latest.shop}</div>
          </div>
          <button className="lv-modal-close" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>

        <h3>Where it ranks in the store's own search</h3>
        <table className="lv-table">
          <thead>
            <tr>
              <th>Search phrase</th>
              <th style={{ textAlign: "center" }}>At the start</th>
              <th style={{ textAlign: "center" }}>After the run</th>
              <th style={{ textAlign: "center" }} className="hide-sm">Results</th>
              <th className="hide-sm">Ranked above it</th>
            </tr>
          </thead>
          <tbody>
            {phrases.map((ph) => {
              const a = at(start, ph)
              const b = at(end, ph)
              const cur = b ?? a
              return (
                <tr key={ph}>
                  <td>{ph}</td>
                  <td className="c lv-mono">{a ? fmt(a.rank) : "—"}</td>
                  <td className="c lv-mono">{b ? <>{fmt(b.rank)} <Move from={a?.rank} to={b.rank} /></> : "—"}</td>
                  <td className="c lv-mono hide-sm">{cur?.results ?? "—"}</td>
                  <td className="dim hide-sm">{cur?.ahead?.join(", ") || ""}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="lv-summary">
          {s && <>At the start: <b>{s.found}/{s.total}</b> phrases find it, #1 for {s.top}. </>}
          {e ? <>After the run: <b>{e.found}/{e.total}</b> find it, #1 for {e.top}.</> : "The second check runs once the Task has ended."}
        </div>

        <h3>The listing {end ? "after the run" : "at the start"}</h3>
        <dl className="lv-kv wide">
          {detailRows(latest.product).map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <dt>{k}</dt>
              <dd>
                {v}
                {before && before[k] !== undefined && before[k] !== v && <span className="lv-was">{before[k]}</span>}
              </dd>
            </div>
          ))}
        </dl>

        <div className="lv-source">
          Fetched by the Uplift Worker from the real Shopify Admin API with this store&apos;s own access token (read-only, through the
          Uplift gateway): <code>{latest.endpoint}</code> · <code>products(first: {TOP}, query: $q, sortKey: RELEVANCE)</code>, one request
          per phrase.
          {start && <> Start checked {time(start.checked_at)}.</>}
          {end && <> End checked {time(end.checked_at)}.</>}
        </div>
      </div>
    </div>
  )
}
