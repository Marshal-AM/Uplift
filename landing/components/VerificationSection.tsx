"use client"

import { motion } from "framer-motion"
import { ShieldCheck, KeyRound, Coins, RotateCcw } from "lucide-react"

const scoreSections = [
  { label: "Discoverability", detail: "SEO title and meta, handle, keyword coverage", points: 22 },
  { label: "Persuasion & copy", detail: "Clear benefits, answers objections", points: 20 },
  { label: "Trust content", detail: "Shipping, returns, FAQ, comparison, reviews", points: 18 },
  { label: "Visuals", detail: "Count, quality, hero image, alt text", points: 15 },
  { label: "Catalog & feed", detail: "Category, attributes, GTIN, Merchant Center", points: 15 },
  { label: "Compliance", detail: "Claims, trademarks, platform policy", points: 10 },
]

const pillars = [
  {
    icon: ShieldCheck,
    title: "Independent verifier",
    body: "Chainlink's decentralized oracle network re-fetches cited sources, recomputes the maths and runs the compliance rules. Consensus decides PASS or FAIL and a 0–100 score.",
  },
  {
    icon: KeyRound,
    title: "Gatekeeper for store writes",
    body: "The only key that can write to your store lives in Chainlink's Vault, used inside an enclave. No Uplift server, agent or operator can publish on its own.",
  },
  {
    icon: Coins,
    title: "Escrow on Cardano",
    body: "Every hire is a Masumi escrow at one fixed price, paid from your Sokosumi credits. The approved quote caps spend.",
  },
  {
    icon: RotateCcw,
    title: "Automatic refunds",
    body: "Work that fails is refunded in the same Chainlink run and redone once with the reasons attached. Hires outside the quote are refunded too.",
  },
]

export const VerificationSection = () => {
  return (
    <section id="verification" className="w-full px-4 sm:px-8 py-24 bg-[#fafafa]">
      <div className="max-w-7xl mx-auto grid grid-cols-12 gap-3">
        <div className="col-span-12 lg:col-span-7 rounded-[40px] bg-white border border-black/5 p-8 sm:p-12">
          <p
            className="text-xs uppercase tracking-tight text-[#146e96] mb-4"
            style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
          >
            Verification · Chainlink CRE
          </p>
          <h2 className="text-[32px] sm:text-[40px] leading-tight tracking-tight text-[#202020] font-medium mb-8">
            Trust the work without trusting the AI.
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {pillars.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="flex flex-col gap-2"
              >
                <span className="w-10 h-10 rounded-2xl bg-[#156d95]/10 text-[#156d95] flex items-center justify-center">
                  <p.icon className="w-5 h-5" />
                </span>
                <h3 className="text-lg font-semibold text-[#202020]">{p.title}</h3>
                <p className="text-[15px] leading-6 text-[#5a5a5a]">{p.body}</p>
              </motion.div>
            ))}
          </div>

          <div
            className="mt-10 rounded-3xl bg-[#0c2638] text-[#cfe3f0] p-5 text-[12.5px] leading-6 overflow-x-auto"
            style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
          >
            <div className="text-[#5f88a3]">{"// Sokosumi Task comment, posted after each Chainlink run"}</div>
            <div>
              <span className="text-[#6ee7b7]">Chainlink verification: PASS · 82/100</span>{" "}
              <span className="text-[#7fa6bf]">clara · product copy</span>
            </div>
            <div>
              <span className="text-[#fca5a5]">Chainlink verification: FAIL · 41/100</span>{" "}
              <span className="text-[#7fa6bf]">kai · competitor trademark → refunded, re-hired</span>
            </div>
            <div>
              <span className="text-[#93c5fd]">published · 11 changes · after-score 86</span>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5 rounded-[40px] p-8 sm:p-12 text-white" style={{ background: "linear-gradient(160deg,#0c2638,#123a55)" }}>
          <p
            className="text-xs uppercase tracking-tight text-[#7cc8f2] mb-4"
            style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
          >
            Listing score
          </p>
          <h3 className="text-[28px] leading-tight font-medium mb-2">Ranking-first, out of 100.</h3>
          <p className="text-white/70 text-[15px] leading-6 mb-8">
            Quinn computes it; Chainlink recomputes it before and after publishing. The AI judge contributes at most 5
            points. Everything else is rules and source checks.
          </p>
          <ul className="space-y-4">
            {scoreSections.map((s, i) => (
              <li key={s.label}>
                <div className="flex items-baseline justify-between text-[15px]">
                  <span className="font-medium">{s.label}</span>
                  <span className="text-[#7cc8f2] tabular-nums" style={{ fontFamily: "var(--font-geist-mono), monospace" }}>
                    {s.points}
                  </span>
                </div>
                <div className="text-[12.5px] text-white/50 mb-1.5">{s.detail}</div>
                <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${(s.points / 22) * 100}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.1, delay: 0.1 + i * 0.08, ease: [0.645, 0.045, 0.355, 1] }}
                    className="h-full rounded-full"
                    style={{ background: "linear-gradient(90deg,#52aee3,#34d399)" }}
                  />
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-10 flex items-center gap-4">
            <div className="text-center">
              <div className="text-[34px] font-semibold text-white/60 tabular-nums">42</div>
              <div className="text-[11px] text-white/50" style={{ fontFamily: "var(--font-geist-mono), monospace" }}>
                before
              </div>
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-white/20 to-[#34d399]" />
            <div className="text-center">
              <div className="text-[34px] font-semibold text-[#34d399] tabular-nums">86</div>
              <div className="text-[11px] text-white/50" style={{ fontFamily: "var(--font-geist-mono), monospace" }}>
                after (demo)
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
