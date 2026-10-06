"use client"

import { motion } from "framer-motion"
import type { LucideIcon } from "lucide-react"
import {
  Workflow,
  Search,
  Radar,
  MessagesSquare,
  BadgePercent,
  PenLine,
  Camera,
  LayoutGrid,
  Languages,
  Newspaper,
  Megaphone,
  Scale,
  Gauge,
} from "lucide-react"

type Member = { name: string; role: string; deliverable: string; price: string; icon: LucideIcon }

const NORA: Member = {
  name: "Nora",
  role: "Uplift Lead · E-commerce Growth Manager",
  deliverable:
    "Reads your request, picks all 12 specialists or just the ones it needs, quotes the price, runs the work in order, merges the launch pack and hands the approved changes to Chainlink to publish.",
  price: "1.50 task fee + hired specialists",
  icon: Workflow,
}

const TEAM: Member[] = [
  { name: "Kai", role: "Search Demand Analyst", deliverable: "Keyword map, intent clusters, seasonality and peak windows", price: "1.25", icon: Search },
  { name: "Rafael", role: "Competitor & Market Analyst", deliverable: "Who ranks, their prices, claims, offers and gaps", price: "1.25", icon: Radar },
  { name: "Priya", role: "Competitor Review & Sentiment Analyst", deliverable: "What competitors' customers love, hate and still need", price: "1.50", icon: MessagesSquare },
  { name: "Marcus", role: "Pricing & Promotions Strategist", deliverable: "Price positioning, promo calendar, margin-safe discount codes", price: "1.25", icon: BadgePercent },
  { name: "Clara", role: "Product Page Copywriter", deliverable: "Title, description, SEO title and meta, handle, tags", price: "2.00", icon: PenLine },
  { name: "Iris", role: "Product Visual Designer", deliverable: "Image audit, cleanup, lifestyle scenes, crops, alt text", price: "2.50", icon: Camera },
  { name: "Oskar", role: "Catalog, Collections & Feed Specialist", deliverable: "Category, attributes, collections, Google Shopping feed health", price: "1.50", icon: LayoutGrid },
  { name: "Yuki", role: "Localization & Transcreation", deliverable: "Localized listings with local keywords", price: "1.00 / locale", icon: Languages },
  { name: "Leo", role: "Content & Email Marketer", deliverable: "FAQ, comparison table, blog article, email and social copy", price: "2.00", icon: Newspaper },
  { name: "Sasha", role: "Paid Ads Strategist", deliverable: "Google Ads plan with break-even bids, created paused", price: "1.50", icon: Megaphone },
  { name: "Ruth", role: "Claims & Compliance Reviewer", deliverable: "Claim, trademark and policy findings with safe rewrites", price: "0.25", icon: Scale },
  { name: "Quinn", role: "Store Auditor & Performance Analyst", deliverable: "0–100 listing score, conversion audit, before/after report", price: "0.50", icon: Gauge },
]

function Avatar({ icon: Icon, size = 44, inverted = false }: { icon: LucideIcon; size?: number; inverted?: boolean }) {
  return (
    <span
      className={`shrink-0 rounded-2xl flex items-center justify-center ${
        inverted ? "bg-white text-[#156d95]" : "bg-[#156d95] text-white"
      }`}
      style={{ width: size, height: size }}
    >
      <Icon style={{ width: size * 0.45, height: size * 0.45 }} strokeWidth={1.8} />
    </span>
  )
}

export const TeamSection = () => {
  return (
    <section id="team" className="w-full px-4 sm:px-8 py-24 bg-white">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-12 gap-6 mb-12">
          <div className="col-span-12 lg:col-span-7">
            <p
              className="text-xs uppercase tracking-tight text-[#146e96] mb-4"
              style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
            >
              The team
            </p>
            <h2 className="text-[34px] sm:text-[44px] leading-tight tracking-tight text-[#202020] font-medium">
              One lead, twelve specialists. Hire the whole team or just one.
            </h2>
          </div>
          <p className="col-span-12 lg:col-span-5 text-lg text-[#555] lg:pt-10">
            Every member is a Sokosumi coworker with its own inputs, deliverables and fixed price, and every one works
            toward the same goal: better rankings that turn into sales.
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.7 }}
          className="rounded-[32px] p-7 sm:p-9 mb-3 text-white flex flex-col md:flex-row gap-6 md:items-center"
          style={{ background: "linear-gradient(120deg, #0c2638 0%, #156d95 100%)" }}
        >
          <Avatar icon={NORA.icon} size={64} inverted />
          <div className="flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <h3 className="text-2xl font-semibold">{NORA.name}</h3>
              <span className="text-white/70 text-sm">{NORA.role}</span>
            </div>
            <p className="mt-2 text-white/85 text-[15px] leading-6 max-w-3xl">{NORA.deliverable}</p>
          </div>
          <span
            className="w-fit text-xs px-3 py-1.5 rounded-full bg-white/10 border border-white/20"
            style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
          >
            {NORA.price}
          </span>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {TEAM.map((m, i) => (
            <motion.div
              key={m.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.5, delay: (i % 4) * 0.06 }}
              className="group rounded-[28px] p-6 bg-[#f4f8fb] hover:bg-white hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] border border-transparent hover:border-black/5 transition-all flex flex-col gap-4"
            >
              <div className="flex items-center gap-3">
                <Avatar icon={m.icon} />
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold text-[#202020] leading-tight">{m.name}</h3>
                  <p className="text-[13px] text-[#6b6b6b] leading-snug">{m.role}</p>
                </div>
              </div>
              <p className="text-[15px] leading-6 text-[#404040]">{m.deliverable}</p>
              <div
                className="mt-auto flex items-center justify-between text-[12px] text-[#8a8a8a]"
                style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
              >
                <span>fixed price</span>
                <span className="text-[#146e96]">{m.price} credits</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
