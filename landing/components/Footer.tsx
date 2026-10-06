"use client"

import { motion } from "framer-motion"
import { Logo, SOKOSUMI_URL } from "./Navbar"

const sections = [
  {
    title: "Product",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "The team", href: "#team" },
      { label: "Verification", href: "#verification" },
      { label: "Pricing", href: "#pricing" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Built on",
    links: [
      { label: "Sokosumi", href: "https://www.sokosumi.com" },
      { label: "Masumi Network", href: "https://www.masumi.network" },
      { label: "Chainlink CRE", href: "https://docs.chain.link/cre" },
      { label: "Kodosumi", href: "https://docs.kodosumi.io" },
      { label: "Cardano", href: "https://cardano.org" },
    ],
  },
]

export const Footer = () => {
  return (
    <footer className="w-full bg-[#fafafa] border-t border-[#e5e5e5]">
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 mb-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="lg:col-span-6"
          >
            <div className="text-2xl text-[#202020] mb-4">
              <Logo />
            </div>
            <p className="text-[15px] leading-6 text-[#666666] max-w-md mb-6">
              A verified multi-agent growth and ads team for e-commerce merchants. Every deliverable checked by
              Chainlink, every hire paid through Masumi escrow on Cardano.
            </p>
            <a
              href={SOKOSUMI_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-[#156d95] text-white px-[18px] py-[15px] rounded-full text-base leading-4 hover:rounded-2xl transition-all"
            >
              Hire Nora on Sokosumi
            </a>
          </motion.div>

          <div className="lg:col-span-6 grid grid-cols-2 gap-8">
            {sections.map((section, i) => (
              <motion.div
                key={section.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: 0.1 * (i + 1) }}
              >
                <h4 className="text-sm font-medium text-[#202020] mb-4 uppercase tracking-wide">{section.title}</h4>
                <ul className="space-y-3">
                  {section.links.map((link) => (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        {...(link.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                        className="text-sm text-[#666666] hover:text-[#202020] transition-colors"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="pt-8 border-t border-[#e5e5e5] flex flex-col md:flex-row justify-between items-center gap-3">
          <p className="text-sm text-[#666666]">© 2026 Uplift. Built at TOKEN2049 Origins, Singapore.</p>
          <p className="text-sm text-[#999]" style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}>
            Cardano Agentic Commerce · Chainlink CRE
          </p>
        </div>
      </div>
    </footer>
  )
}
