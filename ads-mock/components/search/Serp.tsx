"use client"
import { ChevronDown, Grip, Settings, SlidersHorizontal } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useState } from "react"
import { GoogleLogo, MockBadge } from "@/components/brand"
import { MockStrip } from "@/components/MockStrip"
import { SearchBox } from "@/components/search/SearchBox"
import {
  CompetitorAd, DiagnosisPanel, OfferCard, OrganicResult, OurAd, PeopleAlsoAsk, RelatedSearches, ShoppingCarousel,
  SponsoredHeader,
} from "@/components/search/results"
import type { Offer } from "@/lib/data"
import { useDataset } from "@/lib/dataset"
import { diagnose, shoppingEligible } from "@/lib/match"

const TABS = ["All", "Shopping", "Images", "Videos", "News", "Maps"]

export function Serp() {
  const params = useSearchParams()
  const query = (params.get("q") ?? "").trim()
  const tab = params.get("tbm") === "shop" ? "Shopping" : "All"
  const [hideAds, setHideAds] = useState(false)
  const { ds } = useDataset()
  const { COMPETITOR_ADS, OFFERS, ORGANIC, RELATED_SEARCHES } = ds
  const search = diagnose(ds, query)
  const shopping = shoppingEligible(ds, query)
  const productQuery = search.showing || shopping
  const offers = OFFERS.filter((o) => (o.ours ? shopping : true) && !(o.id === "fn" && !query.includes("kid")))

  return (
    <div className="min-h-screen font-serp">
      <MockStrip />
      <header className="flex flex-col items-center gap-3 px-4 pt-4 sm:flex-row sm:gap-6 sm:px-7 sm:pt-5">
        <Link href="/" className="shrink-0 sm:w-[124px]">
          <GoogleLogo size={30} />
        </Link>
        <div className="flex-1">
          <SearchBox key={query + tab} variant="serp" initial={query} tab={tab === "Shopping" ? "shop" : undefined} />
        </div>
        <div className="hidden items-center gap-4 md:flex">
          <Settings className="h-6 w-6 text-[#5f6368]" aria-hidden />
          <Grip className="h-6 w-6 text-[#5f6368]" aria-hidden />
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#3f7d5a] text-[14px] font-medium text-white">
            E
          </span>
        </div>
      </header>

      <nav className="mt-3 flex items-center gap-1 overflow-x-auto px-4 sm:pl-[180px] no-scrollbar">
        {TABS.map((t) => {
          const active = t === tab
          const href = t === "All" ? `/search/?q=${encodeURIComponent(query)}` : t === "Shopping" ? `/search/?q=${encodeURIComponent(query)}&tbm=shop` : null
          const cls = `relative whitespace-nowrap px-3 pb-3 pt-2 text-[14px] ${active ? "font-medium text-[#1a73e8]" : "text-[#5f6368]"}`
          return href ? (
            <Link key={t} href={href} className={cls}>
              {t}
              {active && <span className="absolute bottom-0 left-2 right-2 h-[3px] rounded-t bg-[#1a73e8]" />}
            </Link>
          ) : (
            <span key={t} className={`${cls} cursor-default`} title="Not part of the mock">
              {t}
            </span>
          )
        })}
        <span className="flex items-center gap-1 px-3 pb-3 pt-2 text-[14px] text-[#5f6368]">
          More <ChevronDown className="h-4 w-4" />
        </span>
        <span className="ml-auto flex items-center gap-1 px-3 pb-3 pt-2 text-[14px] text-[#5f6368]">
          Tools <SlidersHorizontal className="h-4 w-4" />
        </span>
      </nav>
      <div className="border-b border-[#ebebeb]" />

      {!query ? (
        <p className="px-4 py-10 text-[14px] text-[#4d5156] sm:pl-[180px]">Type a search to see mock results.</p>
      ) : tab === "Shopping" ? (
        <ShoppingTab query={query} offers={offers} demo={ds.source === "demo"} />
      ) : (
        <div className="flex flex-col gap-10 px-4 pt-5 sm:pl-[180px] xl:flex-row">
          <main className="w-full max-w-[652px]">
            <div className="mb-6 xl:hidden">
              <DiagnosisPanel query={query} search={search} shopping={shopping} />
            </div>
            {productQuery && (
              <section className="mb-2">
                <SponsoredHeader hidden={hideAds} onToggle={() => setHideAds(!hideAds)} />
                {!hideAds && (
                  <>
                    {search.showing && <OurAd query={query} top />}
                    {COMPETITOR_ADS.slice(0, search.showing ? 1 : 2).map((ad) => (
                      <CompetitorAd key={ad.domain} ad={ad} query={query} />
                    ))}
                  </>
                )}
              </section>
            )}
            {shopping && !hideAds && <ShoppingCarousel offers={offers.slice(0, 6)} query={query} />}
            {ORGANIC.slice(0, 2).map((r, i) => (
              <OrganicResult key={`${r.domain}-${i}`} r={r} query={query} />
            ))}
            <PeopleAlsoAsk />
            {ORGANIC.slice(2).map((r, i) => (
              <OrganicResult key={`${r.domain}-${i + 2}`} r={r} query={query} />
            ))}
            {productQuery && !hideAds && search.showing && COMPETITOR_ADS[1] && (
              <section className="mb-8">
                <div className="mb-3 text-[14px] font-bold text-[#202124]">Sponsored</div>
                <CompetitorAd ad={COMPETITOR_ADS[1]} query={query} />
              </section>
            )}
            <RelatedSearches items={RELATED_SEARCHES.filter((s) => s !== query).slice(0, 8)} query={query} />
            <Pagination />
          </main>
          <div className="hidden w-[360px] shrink-0 xl:block">
            <div className="sticky top-5">
              <DiagnosisPanel query={query} search={search} shopping={shopping} />
            </div>
          </div>
        </div>
      )}
      <SerpFooter live={ds.source === "run"} />
    </div>
  )
}

function ShoppingTab({ query, offers, demo }: { query: string; offers: Offer[]; demo: boolean }) {
  const prices = offers.map((o) => o.price).sort((a, b) => a - b)
  const mid = prices.length ? Math.round(prices[Math.floor(prices.length / 2)]) : 30
  const low = prices.length ? Math.round(prices[Math.floor(prices.length / 4)]) : 25
  const sellers = [...new Set(offers.map((o) => o.seller).filter(Boolean))].slice(0, 4)
  const chips = demo
    ? ["Under $30", "Free shipping", "Bamboo lid", "On sale", "750 ml", "Stainless steel", "4★ & up"]
    : [`Under $${mid}`, "On sale", "Free shipping", "4★ & up", "Nearby"]
  const filters: [string, string[]][] = demo
    ? [
        ["Price", ["Up to $25", "$25 – $35", "Over $35"]],
        ["Material", ["Stainless steel", "Bamboo", "Glass"]],
        ["Capacity", ["500 ml", "750 ml", "1 L"]],
        ["Seller", sellers],
      ]
    : [
        ["Price", [`Up to $${low}`, `$${low} – $${mid}`, `Over $${mid}`]],
        ["Seller", sellers],
      ]
  return (
    <div className="px-4 pt-4 sm:pl-[180px] sm:pr-8">
      <div className="no-scrollbar mb-5 flex gap-2 overflow-x-auto">
        {chips.map((c) => (
          <span key={c} className="whitespace-nowrap rounded-lg border border-[#dadce0] px-3 py-1.5 text-[14px] text-[#3c4043]">
            {c}
          </span>
        ))}
      </div>
      <div className="flex gap-8">
        <aside className="hidden w-[180px] shrink-0 text-[14px] text-[#202124] lg:block">
          {filters.map(([title, items]) => (
            <div key={title} className="mb-5 border-b border-[#ebebeb] pb-4">
              <div className="mb-2 font-medium">{title}</div>
              {items.map((i) => (
                <label key={i} className="mb-1.5 flex items-center gap-2 text-[#3c4043]">
                  <input type="checkbox" className="h-4 w-4 accent-[#1a73e8]" /> {i}
                </label>
              ))}
            </div>
          ))}
        </aside>
        <main className="flex-1">
          <div className="mb-3 flex items-center gap-2 text-[14px] font-bold text-[#202124]">
            Sponsored <span className="font-normal text-[#70757a]">· Results for “{query}”</span>
          </div>
          <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
            {offers.map((o) => (
              <OfferCard key={o.id} o={o} query={query} wide />
            ))}
          </div>
          <p className="mt-8 text-[12px] text-[#70757a]">
            {demo ? "Prices, sellers and products are mock data." : "Competitor offers from the run's Google Shopping research; layout is a mock."}{" "}
            <MockBadge />
          </p>
        </main>
      </div>
    </div>
  )
}

function Pagination() {
  return (
    <div className="mb-12 flex items-center justify-center gap-6 text-[14px]">
      <span className="text-[#202124]">1</span>
      {[2, 3, 4, 5, 6].map((n) => (
        <span key={n} className="cursor-pointer text-[#1a0dab] hover:underline">
          {n}
        </span>
      ))}
      <span className="cursor-pointer font-medium text-[#1a0dab] hover:underline">Next</span>
    </div>
  )
}

function SerpFooter({ live }: { live: boolean }) {
  return (
    <footer className="mt-6 bg-[#f2f2f2] text-[14px] text-[#70757a]">
      <div className="border-b border-[#dadce0] px-4 py-3 sm:pl-[180px]">United States · {live ? "Results from the run's research; layout is a mock" : "Results are mock data"}</div>
      <div className="flex gap-7 px-4 py-3 sm:pl-[180px]">
        <span>Help</span>
        <span>Send feedback</span>
        <span>Privacy</span>
        <span>Terms</span>
      </div>
    </footer>
  )
}
