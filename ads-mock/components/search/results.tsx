"use client"
import { CheckCircle2, ChevronDown, ChevronRight, CircleAlert, EllipsisVertical, Search, Star, XCircle } from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import { BottleArt, Favicon, MockBadge } from "@/components/brand"
import {
  CALLOUTS, DESCRIPTIONS, DISPLAY_PATH, HEADLINES, PEOPLE_ALSO_ASK, PRODUCT, SITELINKS, STORE,
  type Offer, type Organic, type TextAd,
} from "@/lib/data"
import type { Diagnosis } from "@/lib/match"
import { useMock } from "@/lib/store"

const hash = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7)

// Responsive search ads show up to three headlines joined by " | " and up to two descriptions.
const COMBOS = [[0, 1, 2], [0, 4, 3], [9, 1, 5], [0, 2, 10], [3, 1, 7], [5, 1, 4]]

const singular = (w: string) => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w)

/** Bold whole words of the query inside a snippet (plurals included), as Google does. */
export function Highlight({ text, query }: { text: string; query: string }) {
  const terms = new Set(query.toLowerCase().split(/\s+/).filter((t) => t.length > 2).map(singular))
  if (!terms.size) return <>{text}</>
  return (
    <>
      {text.split(/([A-Za-z0-9]+)/).map((part, i) =>
        terms.has(singular(part.toLowerCase())) ? (
          <b key={i} className="font-bold text-[#5f6368]">
            {part}
          </b>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  )
}

function SiteLine({ name, domain, path, color }: { name: string; domain: string; path: string[]; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <Favicon name={name} color={color} />
      <div className="min-w-0 leading-tight">
        <div className="truncate text-[14px] text-[#202124]">{name}</div>
        <div className="truncate text-[12px] text-[#4d5156]">
          https://www.{domain}
          {path.length > 0 && <span> › {path.join(" › ")}</span>}
        </div>
      </div>
      <EllipsisVertical className="h-[18px] w-[18px] shrink-0 text-[#5f6368]" aria-hidden />
    </div>
  )
}

function Stars({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center align-[-2px]">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className="h-[13px] w-[13px]"
          fill={i < Math.round(value) ? "#fbbc04" : "#dadce0"}
          stroke="none"
        />
      ))}
    </span>
  )
}

export function SponsoredHeader({ hidden, onToggle }: { hidden: boolean; onToggle: () => void }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <span className="text-[14px] font-bold text-[#202124]">Sponsored</span>
      <button className="text-[12px] text-[#4d5156] hover:underline" onClick={onToggle}>
        {hidden ? "Show sponsored results" : "Hide sponsored results"}
      </button>
    </div>
  )
}

/** The merchant's own responsive search ad, built from the Uplift ad assets. */
export function OurAd({ query, top }: { query: string; top: boolean }) {
  const combo = COMBOS[hash(query) % COMBOS.length]
  const title = combo.map((i) => HEADLINES[i].text).join(" | ")
  const desc = DESCRIPTIONS[hash(query + "d") % 2].text
  const href = "/store/?from=search-ad&q=" + encodeURIComponent(query)
  return (
    <div className="mb-7">
      <SiteLine name={STORE.name} domain={STORE.domain} path={DISPLAY_PATH} color={PRODUCT.color} />
      <Link href={href} className="mt-1.5 block text-[20px] leading-[26px] text-[#1a0dab] hover:underline">
        {title}
      </Link>
      <div className="mt-1 text-[14px] leading-[22px] text-[#4d5156]">
        <Highlight text={desc} query={query} /> <span>{CALLOUTS.slice(0, 2).join(" · ")}</span>
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[14px] text-[#4d5156]">
        <span>{PRODUCT.rating}</span>
        <Stars value={PRODUCT.rating} />
        <span>({PRODUCT.reviews})</span>
        <span className="mx-1">·</span>
        <span>Free shipping over $40</span>
      </div>
      {top ? (
        <div className="mt-3 grid grid-cols-1 gap-x-8 gap-y-3 pl-[38px] sm:grid-cols-2">
          {SITELINKS.map((s) => (
            <div key={s.title}>
              <Link href={href} className="text-[16px] text-[#1a0dab] hover:underline">
                {s.title}
              </Link>
              <div className="text-[14px] text-[#4d5156]">{s.line}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-1 text-[14px]">
          {SITELINKS.map((s, i) => (
            <span key={s.title}>
              <Link href={href} className="text-[#1a0dab] hover:underline">
                {s.title}
              </Link>
              {i < SITELINKS.length - 1 && <span className="text-[#4d5156]"> · </span>}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export function CompetitorAd({ ad, query }: { ad: TextAd; query: string }) {
  return (
    <div className="mb-7">
      <SiteLine name={ad.advertiser} domain={ad.domain} path={[ad.path]} color={ad.color} />
      <span className="mt-1.5 block cursor-pointer text-[20px] leading-[26px] text-[#1a0dab] hover:underline">{ad.title}</span>
      <div className="mt-1 text-[14px] leading-[22px] text-[#4d5156]">
        <Highlight text={ad.description} query={query} />
      </div>
    </div>
  )
}

export function OrganicResult({ r, query }: { r: Organic; query: string }) {
  const ours = r.domain === STORE.domain
  const title = ours ? (
    <Link href="/store/?from=organic" className="text-[20px] leading-[26px] text-[#1a0dab] hover:underline">
      {r.title}
    </Link>
  ) : (
    <span className="cursor-pointer text-[20px] leading-[26px] text-[#1a0dab] hover:underline">{r.title}</span>
  )
  return (
    <div className="mb-8">
      <SiteLine name={r.site} domain={r.domain} path={r.crumbs} color={r.color} />
      <h3 className="mt-1.5">{title}</h3>
      <div className="mt-1 text-[14px] leading-[22px] text-[#4d5156]">
        {r.date && <span className="text-[#70757a]">{r.date} — </span>}
        <Highlight text={r.snippet} query={query} />
      </div>
      {ours && (
        <div className="mt-1 flex items-center gap-1 text-[14px] text-[#70757a]">
          <Stars value={PRODUCT.rating} /> Rating: {PRODUCT.rating} · {PRODUCT.reviews} reviews · ${PRODUCT.price.toFixed(2)} ·
          In stock
        </div>
      )}
    </div>
  )
}

export function OfferCard({ o, query, wide }: { o: Offer; query: string; wide?: boolean }) {
  const card = (
    <div className={`group ${wide ? "w-full" : "w-[160px] shrink-0"}`}>
      <div className="overflow-hidden rounded-lg">
        <BottleArt color={o.color} lid={o.lid} size={wide ? 220 : 160} bg="#f1f3f4" />
      </div>
      <div className="mt-2 line-clamp-2 text-[14px] leading-[20px] text-[#202124] group-hover:underline">{o.title}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-[16px] font-bold text-[#202124]">${o.price.toFixed(2)}</span>
        {o.was && <span className="text-[12px] text-[#70757a] line-through">${o.was.toFixed(2)}</span>}
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[12px] text-[#4d5156]">
        <Favicon name={o.seller} color={o.color} size={16} />
        <span className="truncate">{o.seller}</span>
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[12px] text-[#4d5156]">
        <span>{o.rating}</span>
        <Star className="h-3 w-3" fill="#fbbc04" stroke="none" />
        <span>({o.reviews >= 1000 ? `${(o.reviews / 1000).toFixed(1)}K` : o.reviews})</span>
      </div>
      <div className="mt-0.5 text-[12px] text-[#4d5156]">{o.shipping}</div>
    </div>
  )
  return o.ours ? (
    <Link href={`/store/?from=shopping-ad&q=${encodeURIComponent(query)}`}>{card}</Link>
  ) : (
    <div className="cursor-pointer">{card}</div>
  )
}

export function ShoppingCarousel({ offers, query }: { offers: Offer[]; query: string }) {
  return (
    <section className="mb-8">
      <div className="mb-1 text-[14px] font-bold text-[#202124]">Sponsored</div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[20px] text-[#202124]">Shop {query}</h2>
        <EllipsisVertical className="h-5 w-5 text-[#5f6368]" aria-hidden />
      </div>
      <div className="relative">
        <div className="no-scrollbar flex gap-4 overflow-x-auto pb-1">
          {offers.map((o) => (
            <OfferCard key={o.id} o={o} query={query} />
          ))}
        </div>
        <span className="pointer-events-none absolute right-[-18px] top-[62px] flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-[0_1px_3px_rgba(60,64,67,0.3),0_4px_8px_3px_rgba(60,64,67,0.15)]">
          <ChevronRight className="h-5 w-5 text-[#5f6368]" />
        </span>
      </div>
      <div className="mt-4 border-t border-[#ebebeb]" />
    </section>
  )
}

export function PeopleAlsoAsk() {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <section className="mb-8">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[20px] text-[#202124]">People also ask</h2>
        <EllipsisVertical className="h-5 w-5 text-[#5f6368]" aria-hidden />
      </div>
      {PEOPLE_ALSO_ASK.map((p, i) => (
        <div key={p.q} className="border-b border-[#dadce0]">
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between py-3.5 text-left text-[16px] text-[#202124]"
          >
            {p.q}
            <ChevronDown className={`h-5 w-5 text-[#5f6368] transition ${open === i ? "rotate-180" : ""}`} />
          </button>
          {open === i && <p className="pb-4 text-[14px] leading-[22px] text-[#4d5156]">{p.a}</p>}
        </div>
      ))}
      <div className="mt-1 text-right text-[12px] text-[#70757a]">Feedback</div>
    </section>
  )
}

export function RelatedSearches({ items, query }: { items: string[]; query: string }) {
  const q = query.toLowerCase().split(/\s+/)
  return (
    <section className="mb-10">
      <h2 className="mb-4 text-[20px] text-[#202124]">People also search for</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {items.map((s) => (
          <Link
            key={s}
            href={`/search/?q=${encodeURIComponent(s)}`}
            className="flex items-center gap-4 rounded-full bg-[#f1f3f4] px-4 py-3 text-[14px] text-[#202124] hover:bg-[#e8eaed]"
          >
            <Search className="h-4 w-4 shrink-0 text-[#5f6368]" />
            <span>
              {s.split(" ").map((w, i) => (
                <span key={i}>{q.includes(w) ? w : <b>{w}</b>} </span>
              ))}
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}

/** Like Google Ads' Ad preview and diagnosis tool: why the merchant's ads do or don't show for this search. */
export function DiagnosisPanel({ query, search, shopping }: { query: string; search: Diagnosis; shopping: boolean }) {
  const s = useMock()
  const row = (ok: boolean, title: string, detail: React.ReactNode) => (
    <div className="flex gap-2.5 py-2.5">
      {ok ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-[#188038]" /> : <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#d93025]" />}
      <div>
        <div className="text-[14px] font-medium text-[#202124]">{title}</div>
        <div className="text-[13px] leading-[19px] text-[#5f6368]">{detail}</div>
      </div>
    </div>
  )
  const paused = (id: "search" | "pmax") => s.status[id] !== "Enabled"
  return (
    <aside className="rounded-lg border border-[#dadce0] p-4 font-roboto">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[16px] font-medium text-[#202124]">Ad preview and diagnosis</span>
        <MockBadge />
      </div>
      <div className="mb-2 text-[12px] text-[#5f6368]">
        “{query}” · United States · English · Desktop
      </div>
      <div className="divide-y divide-[#e8eaed]">
        {search.showing
          ? row(true, "Your Search ad is showing", <>Keyword <b>{search.keyword.text}</b> · {search.keyword.match} · Ad group “{search.keyword.adGroup}”</>)
          : search.reason === "negative"
            ? row(false, "Your Search ad isn't showing", <>The search matches your negative keyword <b>{search.negative}</b>.</>)
            : row(false, "Your Search ad isn't showing", <>None of your keywords match this search.</>)}
        {shopping
          ? row(true, "Your Shopping ad is showing", <>Performance Max · {PRODUCT.shortTitle}</>)
          : row(false, "Your Shopping ad isn't showing", <>This search isn't relevant to products in your feed.</>)}
      </div>
      {(paused("search") || paused("pmax")) && (search.showing || shopping) && (
        <div className="mt-2 flex gap-2 rounded-md bg-[#fef7e0] p-2.5 text-[12px] leading-[17px] text-[#3c4043]">
          <CircleAlert className="h-4 w-4 shrink-0 text-[#e37400]" />
          <span>
            {paused("search") && paused("pmax") ? "Both campaigns are" : paused("search") ? "The Search campaign is" : "Performance Max is"}{" "}
            paused, so real shoppers wouldn&apos;t see this yet. This is a preview of how the ad will appear once enabled.
          </span>
        </div>
      )}
      <Link
        href="/ads/campaigns/"
        className="mt-3 inline-flex h-9 items-center rounded-full bg-[#1a73e8] px-5 text-[14px] font-medium text-white hover:bg-[#1765cc] hover:shadow"
      >
        Open Google Ads (mock)
      </Link>
    </aside>
  )
}
