"use client"

import { motion } from "framer-motion"
import { MessageSquare, PlugZap, ClipboardCheck, Cpu, FileDiff, Rocket, BarChart3 } from "lucide-react"

const steps = [
  {
    icon: MessageSquare,
    title: "Ask",
    body: "@mention Nora in Sokosumi chat, assign her a Task, or give a Task straight to one specialist.",
    tag: "Sokosumi",
  },
  {
    icon: PlugZap,
    title: "Connect your store once",
    body: "The Task shows an Authenticate button. You approve Uplift's scopes in Shopify. Agents never see the token.",
    tag: "Shopify OAuth",
  },
  {
    icon: ClipboardCheck,
    title: "Approve the plan and price",
    body: "Nora picks only the specialists your request needs and posts the quote: who, in what order, what each costs.",
    tag: "Approval required",
  },
  {
    icon: Cpu,
    title: "The work runs, and gets checked",
    body: "Each hire is paid into Masumi escrow on Cardano. Chainlink scores every deliverable. Failures are refunded and redone once.",
    tag: "Masumi · Chainlink",
  },
  {
    icon: FileDiff,
    title: "Review the changes",
    body: "Nora posts one change set: a plain-language before/after summary plus a diff file. You approve in Sokosumi.",
    tag: "Approval required",
  },
  {
    icon: Rocket,
    title: "Chainlink publishes",
    body: "CRE confirms your approval and the passing scores, then writes to your store and creates ad campaigns paused.",
    tag: "Chainlink CRE",
  },
  {
    icon: BarChart3,
    title: "Get the report",
    body: "Before/after listing score, what each specialist changed, what each step cost and its verification result.",
    tag: "Report",
  },
]

export const HowItWorks = () => {
  return (
    <section id="how-it-works" className="w-full px-4 sm:px-8 py-24 bg-[#fafafa]">
      <div className="max-w-7xl mx-auto">
        <div className="max-w-3xl mb-14">
          <p
            className="text-xs uppercase tracking-tight text-[#146e96] mb-4"
            style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
          >
            How it works
          </p>
          <h2 className="text-[34px] sm:text-[44px] leading-tight tracking-tight text-[#202020] font-medium">
            One request. Everything happens inside Sokosumi.
          </h2>
          <p className="mt-4 text-lg text-[#555]">
            Nothing in your store or ad account changes until you approve it, and no specialist is paid until Chainlink
            passes its work.
          </p>
        </div>

        <ol className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {steps.map((s, i) => (
            <motion.li
              key={s.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: [0.645, 0.045, 0.355, 1] }}
              className={`relative rounded-[28px] p-7 bg-white border border-black/5 flex flex-col gap-4 ${
                i === steps.length - 1 ? "lg:col-span-1 sm:col-span-2" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="w-11 h-11 rounded-2xl bg-[#156d95]/10 text-[#156d95] flex items-center justify-center">
                  <s.icon className="w-5 h-5" />
                </span>
                <span
                  className="text-[11px] text-[#9a9a9a]"
                  style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
                >
                  0{i + 1}
                </span>
              </div>
              <h3 className="text-xl font-semibold text-[#202020] leading-snug">{s.title}</h3>
              <p className="text-[15px] leading-6 text-[#5a5a5a]">{s.body}</p>
              <span
                className="mt-auto w-fit text-[11px] px-2.5 py-1 rounded-full bg-[#f1f5f8] text-[#146e96]"
                style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
              >
                {s.tag}
              </span>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  )
}
