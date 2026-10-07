"use client"
import { ArrowLeft, Check, Search, ShoppingBag, Star, Truck, User } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useState } from "react"
import { BottleArt, MockBadge } from "@/components/brand"
import { MockStrip } from "@/components/MockStrip"
import { PRODUCT, STORE } from "@/lib/data"

const SOURCES: Record<string, string> = {
  "search-ad": "a Google Search ad",
  "shopping-ad": "a Google Shopping ad",
  organic: "an organic Google result",
}

const SHOTS = [
  { color: PRODUCT.color, lid: "#c8a46e", bg: "#f4f1ea" },
  { color: PRODUCT.color, lid: "#c8a46e", bg: "#e7efe9" },
  { color: "#2f5d46", lid: "#b8935a", bg: "#f4f1ea" },
  { color: "#d9cfc1", lid: "#c8a46e", bg: "#f4f1ea" },
]

export function Storefront() {
  const params = useSearchParams()
  const from = params.get("from") ?? ""
  const q = params.get("q") ?? ""
  const [shot, setShot] = useState(0)
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)

  return (
    <div className="min-h-screen bg-white font-roboto text-[#1f2421]">
      <MockStrip />
      {SOURCES[from] && (
        <div className="flex flex-wrap items-center justify-between gap-2 bg-[#e8f0fe] px-4 py-2 text-[13px] text-[#174ea6]">
          <span>
            <MockBadge className="mr-2" />
            You arrived from {SOURCES[from]}
            {q && <> for “{q}”</>}. In real Google Ads this visit is a paid click, tagged with utm_source=google and
            utm_medium=cpc.
          </span>
          {q && (
            <Link href={`/search/?q=${encodeURIComponent(q)}`} className="inline-flex items-center gap-1 font-medium hover:underline">
              <ArrowLeft className="h-4 w-4" /> Back to results
            </Link>
          )}
        </div>
      )}
      <div className="bg-[#2f5d46] py-2 text-center text-[13px] text-white">Free US shipping on orders over $40</div>
      <header className="flex items-center justify-between border-b border-[#e5e7eb] px-6 py-5">
        <nav className="hidden gap-6 text-[14px] md:flex">
          <span>Bottles</span>
          <span>Gift sets</span>
          <span>Bottle care</span>
          <span>Our story</span>
        </nav>
        <span className="font-serif text-[22px] tracking-wide">{STORE.name}</span>
        <span className="flex gap-4">
          <Search className="h-5 w-5" />
          <User className="h-5 w-5" />
          <ShoppingBag className="h-5 w-5" />
        </span>
      </header>

      <main className="mx-auto grid max-w-6xl gap-10 px-6 py-10 md:grid-cols-2">
        <div>
          <div className="overflow-hidden rounded-lg">
            <BottleArt {...SHOTS[shot]} size={560} />
          </div>
          <div className="mt-3 grid grid-cols-4 gap-3">
            {SHOTS.map((s, i) => (
              <button
                key={i}
                onClick={() => setShot(i)}
                className={`overflow-hidden rounded-md border-2 ${i === shot ? "border-[#1f2421]" : "border-transparent"}`}
              >
                <BottleArt {...s} size={130} />
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[12px] uppercase tracking-[0.15em] text-[#6b7280]">{STORE.name}</p>
          <h1 className="mt-2 font-serif text-[34px] leading-tight">{PRODUCT.title}</h1>
          <div className="mt-3 flex items-center gap-2 text-[14px]">
            <span className="flex">
              {Array.from({ length: 5 }, (_, i) => (
                <Star key={i} className="h-4 w-4" fill="#1f2421" stroke="none" />
              ))}
            </span>
            {PRODUCT.rating} · {PRODUCT.reviews} reviews
          </div>
          <p className="mt-5 text-[24px]">${PRODUCT.price.toFixed(2)} USD</p>
          <p className="mt-1 text-[13px] text-[#6b7280]">Taxes included. Shipping calculated at checkout.</p>
          <ul className="mt-6 space-y-2 text-[15px]">
            {PRODUCT.bullets.map((b) => (
              <li key={b} className="flex gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#2f5d46]" /> {b}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex items-center gap-4">
            <div className="flex items-center border border-[#d1d5db]">
              <button className="px-4 py-3" onClick={() => setQty(Math.max(1, qty - 1))}>
                −
              </button>
              <span className="w-8 text-center">{qty}</span>
              <button className="px-4 py-3" onClick={() => setQty(qty + 1)}>
                +
              </button>
            </div>
            <button
              onClick={() => setAdded(true)}
              className="flex-1 bg-[#1f2421] py-3.5 text-[15px] tracking-wide text-white hover:bg-[#2f5d46]"
            >
              Add to cart
            </button>
          </div>
          {added && (
            <p className="mt-3 rounded bg-[#fef7e0] px-3 py-2 text-[13px] text-[#3c4043]">
              <MockBadge className="mr-2" /> Mock store: nothing was added and no order is placed. In a real store this
              would be the conversion Google Ads reports.
            </p>
          )}
          <div className="mt-8 flex items-center gap-2 border-t border-[#e5e7eb] pt-6 text-[14px] text-[#4b5563]">
            <Truck className="h-5 w-5" /> Ships in 1–2 business days · 30-day returns
          </div>
          <p className="mt-6 text-[12px] text-[#9ca3af]">
            Mock storefront for the Uplift demo. {STORE.name} is a fictional store.
          </p>
        </div>
      </main>
    </div>
  )
}
