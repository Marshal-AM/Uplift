"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus } from "lucide-react"
type FAQItem = {
  question: string
  answer: string
}
type FAQSectionProps = {
  title?: string
  faqs?: FAQItem[]
}
const defaultFAQs: FAQItem[] = [
  {
    question: "What is Uplift?",
    answer:
      "Uplift is an AI e-commerce growth and ads team for merchants, listed on Sokosumi. A lead coworker, Nora, plus 12 specialists research your market, rebuild your product listing and launch assets, prepare ad campaigns and publish what you approve. The goal is better rankings in organic search, shopping results and your store's own search, turned into sales.",
  },
  {
    question: "Do the AI agents get access to my Shopify store?",
    answer:
      "No. You connect your store once through Shopify's own install screen, and the access token is stored encrypted in Uplift's Connection Gateway. Agents only receive read-only snapshots. The key that can write to your store lives in Chainlink's Vault and is used inside an enclave, only after you approve the changes in Sokosumi.",
  },
  {
    question: "What does Chainlink actually check?",
    answer:
      "Every deliverable is re-checked by a Chainlink CRE workflow: it re-fetches cited sources, recomputes the maths and the listing score, and runs the compliance rules. The decentralized network agrees on a 0–100 score and a PASS or FAIL. An AI judge contributes at most 5 of the 100 points; everything else is deterministic or source-checked.",
  },
  {
    question: "What happens if a specialist's work fails?",
    answer:
      "Chainlink files the refund in the same run, so the credits return to your workspace, and Nora re-hires that specialist once with the failure reasons attached. If it fails again, that part is left out of the change set and named in Nora's summary. Failed work is never published.",
  },
  {
    question: "How do I pay, and can it overspend?",
    answer:
      "You pay with Sokosumi workspace credits. Each hire is a Masumi escrow on Cardano at one fixed price. Nora's quote lists every specialist and its cost, you approve the total, every hire is capped at its list price, and Chainlink refunds any hire outside the approved plan. Running out of credits pauses the Task.",
  },
  {
    question: "Will Uplift change my prices or turn on my ads?",
    answer:
      "No. Uplift never changes price, compare-at price, inventory, variants, product status or theme files, and never touches orders or customers. Pricing advice comes as recommendations plus scheduled discount codes. Google Ads campaigns are created paused, so you decide when they go live.",
  },
  {
    question: "Which platforms are supported?",
    answer:
      "Version 1 supports Shopify stores, Google Merchant Center (via Shopify's Google & YouTube channel) and Google Ads. The agents' inputs and outputs are platform-neutral, so more commerce platforms and ad networks can be added through new gateway adapters.",
  },
  {
    question: "Can I hire just one specialist?",
    answer:
      "Yes. Every specialist is a standalone Sokosumi coworker with its own inputs, deliverables and fixed price. Assign a Task to Quinn for an audit, Clara for copy or Yuki for translations, and the same Chainlink verification applies.",
  },
]
export const FAQSection = ({ title = "Frequently asked questions", faqs = defaultFAQs }: FAQSectionProps) => {
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const toggleFAQ = (index: number) => {
    setOpenIndex(openIndex === index ? null : index)
  }
  return (
    <section id="faq" className="w-full py-24 px-4 sm:px-8 bg-white">
      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-12 gap-16">
          {/* Left Column - Title */}
          <div className="lg:col-span-4">
            <h2
              className="text-[40px] leading-tight font-normal text-[#202020] tracking-tight sticky top-24"
              style={{
                fontFamily: "var(--font-figtree), Figtree",
                fontWeight: "400",
                fontSize: "40px",
              }}
            >
              {title}
            </h2>
          </div>

          {/* Right Column - FAQ Items */}
          <div className="lg:col-span-8">
            <div className="space-y-0">
              {faqs.map((faq, index) => (
                <div key={index} className="border-b border-[#e5e5e5] last:border-b-0">
                  <button
                    onClick={() => toggleFAQ(index)}
                    className="w-full flex items-center justify-between py-6 text-left group hover:opacity-70 transition-opacity duration-150"
                    aria-expanded={openIndex === index}
                  >
                    <span
                      className="text-lg leading-7 text-[#202020] pr-8"
                      style={{
                        fontFamily: "var(--font-figtree), Figtree",
                        fontWeight: "400",
                      }}
                    >
                      {faq.question}
                    </span>
                    <motion.div
                      animate={{
                        rotate: openIndex === index ? 45 : 0,
                      }}
                      transition={{
                        duration: 0.2,
                        ease: [0.4, 0, 0.2, 1],
                      }}
                      className="flex-shrink-0"
                    >
                      <Plus className="w-6 h-6 text-[#202020]" strokeWidth={1.5} />
                    </motion.div>
                  </button>

                  <AnimatePresence initial={false}>
                    {openIndex === index && (
                      <motion.div
                        initial={{
                          height: 0,
                          opacity: 0,
                        }}
                        animate={{
                          height: "auto",
                          opacity: 1,
                        }}
                        exit={{
                          height: 0,
                          opacity: 0,
                        }}
                        transition={{
                          duration: 0.3,
                          ease: [0.4, 0, 0.2, 1],
                        }}
                        className="overflow-hidden"
                      >
                        <div className="pb-6 pr-12">
                          <p
                            className="text-lg leading-6 text-[#666666]"
                            style={{
                              fontFamily: "var(--font-figtree), Figtree",
                            }}
                          >
                            {faq.answer}
                          </p>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
