"use client"

import { motion } from "framer-motion"
import { Check } from "lucide-react"
import { SOKOSUMI_URL } from "./Navbar"

const plans = [
  {
    name: "One specialist",
    price: "from 0.25",
    unit: "tUSDM per job · 25 credits",
    example: "“Audit my bamboo bottle” → Quinn, 0.50 tUSDM",
    features: [
      "Assign a Task to any of the 12 specialists",
      "Fixed price, paid into escrow",
      "Chainlink-verified before you pay",
      "Refund if the work fails twice",
    ],
    cta: "Browse the team",
    href: "#team",
    highlight: false,
  },
  {
    name: "Focused fix",
    price: "≈ 6.00",
    unit: "tUSDM · 600 credits · 1 product page",
    example: "“Rewrite my product page” → Kai, Priya, Clara, Ruth, Quinn (before + after)",
    features: [
      "Nora picks only the specialists you need",
      "Price ceiling up front, approved by you",
      "One change set to review",
      "Before/after listing score",
    ],
    cta: "Ask Nora",
    href: SOKOSUMI_URL,
    highlight: false,
  },
  {
    name: "Full launch",
    price: "≈ 18.00",
    unit: "tUSDM · 1,800 credits · 1 product, 2 locales",
    example: "“Launch my bamboo bottle” → all 12 specialists",
    features: [
      "Research, listing, visuals, catalog and feed",
      "Translations, content and email copy",
      "Google Ads plan, created paused",
      "Published by Chainlink after your approval",
    ],
    cta: "Hire Nora on Sokosumi",
    href: SOKOSUMI_URL,
    highlight: true,
  },
]

export const PricingSection = () => {
  return (
    <section id="pricing" className="w-full px-4 sm:px-8 py-24 bg-[#fafafa]">
      <div className="max-w-7xl mx-auto">
        <div className="max-w-3xl mb-12">
          <p
            className="text-xs uppercase tracking-tight text-[#146e96] mb-4"
            style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
          >
            Pricing
          </p>
          <h2 className="text-[34px] sm:text-[44px] leading-tight tracking-tight text-[#202020] font-medium">
            Pay per job, not per month.
          </h2>
          <p className="mt-4 text-lg text-[#555]">
            No retainer. You pay with your Sokosumi workspace credits (100 credits per tUSDM), once, after the work: Nora charges the sum of
            the specialists she used, never more than the ceiling you approved. Work that fails verification is free.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {plans.map((p, i) => (
            <motion.div
              key={p.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.08 }}
              className={`rounded-[32px] p-8 flex flex-col ${
                p.highlight ? "text-white" : "bg-white border border-black/5 text-[#202020]"
              }`}
              style={p.highlight ? { background: "linear-gradient(150deg,#0c2638,#156d95)" } : undefined}
            >
              <h3 className="text-lg font-semibold">{p.name}</h3>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-[40px] font-semibold tracking-tight">{p.price}</span>
              </div>
              <span
                className={`text-[12px] ${p.highlight ? "text-white/70" : "text-[#8a8a8a]"}`}
                style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
              >
                {p.unit}
              </span>
              <p className={`mt-5 text-[14px] leading-6 ${p.highlight ? "text-white/80" : "text-[#5a5a5a]"}`}>{p.example}</p>
              <ul className="mt-6 space-y-3 mb-8">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2.5 text-[15px] leading-6">
                    <Check className={`w-4 h-4 mt-1 shrink-0 ${p.highlight ? "text-[#34d399]" : "text-[#156d95]"}`} />
                    <span className={p.highlight ? "text-white/90" : "text-[#404040]"}>{f}</span>
                  </li>
                ))}
              </ul>
              <a
                href={p.href}
                {...(p.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                className={`mt-auto block text-center rounded-full px-[18px] py-[15px] text-base leading-4 transition-all duration-150 hover:rounded-2xl ${
                  p.highlight ? "bg-white text-[#0c2638]" : "border border-[#202020] text-[#202020]"
                }`}
              >
                {p.cta}
              </a>
            </motion.div>
          ))}
        </div>
        <p
          className="mt-6 text-[12px] text-[#8a8a8a]"
          style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
        >
          Prices are in tUSDM, the test USD stablecoin the Masumi escrow holds on Cardano preprod. Sokosumi charges 100
          workspace credits per 1 tUSDM (a 6.00 tUSDM job uses 600 credits). Each specialist has a fixed price; example
          totals depend on the plan Nora proposes.
        </p>
      </div>
    </section>
  )
}
