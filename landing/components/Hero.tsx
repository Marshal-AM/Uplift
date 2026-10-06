"use client"

import { motion } from "framer-motion"
import { ShieldCheck } from "lucide-react"
import { HeroAbstract } from "./HeroAbstract"
import { SOKOSUMI_URL } from "./Navbar"

const EASE = [0.645, 0.045, 0.355, 1] as const

export const Hero = () => {
  return (
    <section id="home" className="w-full px-4 sm:px-8 pt-28 sm:pt-32 pb-16">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-12 gap-2">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, ease: EASE }}
            className="col-span-12 lg:col-span-6 bg-[#e9e9e9] rounded-[40px] p-8 sm:p-12 lg:p-16 flex flex-col justify-end lg:aspect-square overflow-hidden"
          >
            <motion.span
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ duration: 0.4, ease: EASE, delay: 0.5 }}
              className="inline-flex w-fit items-center gap-1.5 text-xs sm:text-sm uppercase tracking-tight text-[#5c6b74] mb-6"
              style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
            >
              <ShieldCheck className="w-4 h-4 text-[#156d95]" />
              Verified by Chainlink · Paid on Cardano
            </motion.span>

            <h1
              className="text-[40px] leading-[44px] sm:text-[56px] sm:leading-[60px] tracking-tight text-[#202020] max-w-[540px] mb-6"
              style={{ fontWeight: 500, fontFamily: "var(--font-figtree), Figtree" }}
            >
              Your AI growth team that only gets paid for verified work.
            </h1>

            <p className="text-lg leading-7 text-[#404040] max-w-[540px]">
              Uplift is a team of 13 AI specialists on Sokosumi that pushes your products up the rankings in search,
              shopping and your own store. Chainlink checks every deliverable before you pay, and nothing in your store
              changes until you approve it.
            </p>

            <ul className="flex gap-1.5 flex-wrap mt-10">
              <li>
                <a
                  href={SOKOSUMI_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-white rounded-full px-[18px] py-[15px] text-base leading-4 whitespace-nowrap transition-all duration-150 hover:rounded-2xl"
                  style={{ background: "#156d95" }}
                >
                  Hire Nora on Sokosumi
                </a>
              </li>
              <li>
                <a
                  href="#how-it-works"
                  className="block text-[#202020] border border-[#202020] rounded-full px-[18px] py-[15px] text-base leading-4 whitespace-nowrap transition-all duration-150 hover:rounded-2xl"
                >
                  See how it works
                </a>
              </li>
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.2 }}
            className="col-span-12 lg:col-span-6 rounded-[40px] aspect-square overflow-hidden bg-[#081a27]"
          >
            <HeroAbstract />
          </motion.div>
        </div>
      </div>
    </section>
  )
}
