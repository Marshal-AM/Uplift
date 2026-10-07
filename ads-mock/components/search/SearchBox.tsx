"use client"
import { Camera, Mic, Search, X } from "lucide-react"
import { useRouter } from "next/navigation"
import { useMemo, useRef, useState } from "react"
import { useDataset } from "@/lib/dataset"

export function SearchBox({
  initial = "",
  tab,
  variant,
}: {
  initial?: string
  tab?: string
  variant: "home" | "serp"
}) {
  const router = useRouter()
  const { ds } = useDataset()
  const { SUGGESTED_QUERIES } = ds
  const pool = useMemo(
    () => [...new Set([...ds.SUGGESTED_QUERIES, ...ds.KEYWORDS.map((k) => k.text), ...ds.RELATED_SEARCHES])],
    [ds],
  )
  const [q, setQ] = useState(initial)
  const [open, setOpen] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const suggestions = useMemo(() => {
    const t = q.trim().toLowerCase()
    return (t ? pool.filter((s) => s.includes(t) && s !== t) : SUGGESTED_QUERIES).slice(0, 8)
  }, [q, pool, SUGGESTED_QUERIES])

  const go = (query: string) => {
    const v = query.trim()
    if (!v) return
    setOpen(false)
    input.current?.blur()
    router.push(`/search/?q=${encodeURIComponent(v)}${tab ? `&tbm=${tab}` : ""}`)
  }

  const showList = open && suggestions.length > 0
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        go(q)
      }}
      className={`relative w-full ${variant === "home" ? "max-w-[584px]" : "max-w-[692px]"}`}
    >
      <div
        className={`relative z-20 flex h-[46px] items-center border border-[#dfe1e5] bg-white pl-4 pr-3 font-serp hover:shadow-[0_1px_6px_rgba(32,33,36,0.28)] ${
          showList ? "rounded-t-[24px] border-transparent shadow-[0_1px_6px_rgba(32,33,36,0.28)]" : "rounded-[24px]"
        } ${variant === "serp" ? "shadow-[0_2px_5px_1px_rgba(64,60,67,0.16)]" : ""}`}
      >
        {variant === "home" && <Search className="mr-3 h-5 w-5 text-[#9aa0a6]" />}
        <input
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          aria-label="Search (mock)"
          autoComplete="off"
          className="h-full flex-1 bg-transparent text-[16px] text-[#202124] outline-none"
        />
        {q && (
          <button type="button" aria-label="Clear" onClick={() => { setQ(""); input.current?.focus() }} className="px-2 text-[#70757a]">
            <X className="h-6 w-6" strokeWidth={1.5} />
          </button>
        )}
        {variant === "serp" && q && <span className="mx-1 h-[65%] w-px bg-[#dfe1e5]" />}
        <Mic className="mx-2 h-6 w-6 text-[#4285f4]" strokeWidth={1.75} aria-hidden />
        <Camera className="mx-2 h-6 w-6 text-[#4285f4]" strokeWidth={1.75} aria-hidden />
        {variant === "serp" && (
          <button type="submit" aria-label="Search" className="ml-1 pl-2 text-[#4285f4]">
            <Search className="h-6 w-6" strokeWidth={2} />
          </button>
        )}
      </div>
      {showList && (
        <ul className="absolute left-0 right-0 top-[46px] z-10 rounded-b-[24px] bg-white pb-4 pt-1 font-serp shadow-[0_4px_6px_rgba(32,33,36,0.28)]">
          <li className="mx-4 mb-1 border-t border-[#e8eaed]" />
          {suggestions.map((s) => (
            <li key={s}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { setQ(s); go(s) }}
                className="flex w-full items-center gap-3 px-4 py-1.5 text-left text-[16px] text-[#202124] hover:bg-[#f1f3f4]"
              >
                <Search className="h-4 w-4 shrink-0 text-[#9aa0a6]" />
                <span>
                  {s.toLowerCase().startsWith(q.trim().toLowerCase()) && q.trim() ? (
                    <>
                      {s.slice(0, q.trim().length)}
                      <b>{s.slice(q.trim().length)}</b>
                    </>
                  ) : (
                    s
                  )}
                </span>
              </button>
            </li>
          ))}
          <li className="px-4 pt-2 text-right text-[12px] text-[#70757a]">{ds.source === "demo" ? "Suggestions are mock data" : "Suggestions from the run's keyword research"}</li>
        </ul>
      )}
    </form>
  )
}
