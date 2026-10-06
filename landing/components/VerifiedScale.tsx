"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"

type StatItem = { value: string; description: string; delay: number }
type DataPoint = { id: number; left: number; top: number; height: number; direction: "up" | "down"; delay: number; fail: boolean }

const stats: StatItem[] = [
  { value: "13", description: "AI coworkers, each\nhireable on its own", delay: 0 },
  { value: "100%", description: "of deliverables re-checked\nby Chainlink CRE", delay: 0.2 },
  { value: "0", description: "store writes without\nyour approval", delay: 0.4 },
  { value: "1", description: "fixed price per job.\nNo double charge.", delay: 0.6 },
]

// Each bar is one deliverable; a few fail the check and are refunded (red tips).
const generateDataPoints = (): DataPoint[] =>
  Array.from({ length: 50 }, (_, i) => {
    const direction = i % 2 === 0 ? "down" : "up"
    const height = 88 + ((i * 53) % 120)
    const top = direction === "down" ? 250 + ((i * 37) % 150) : -80 + ((i * 29) % 100)
    return { id: i, left: 1 + i * 32, top, height, direction, delay: i * 0.035, fail: i % 11 === 7 }
  })

export const VerifiedScale = () => {
  const [isVisible, setIsVisible] = useState(false)
  const [dataPoints] = useState<DataPoint[]>(generateDataPoints)
  const [typingComplete, setTypingComplete] = useState(false)

  useEffect(() => {
    setIsVisible(true)
    const timer = setTimeout(() => setTypingComplete(true), 1000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="w-full overflow-hidden bg-white">
      <div className="mx-auto max-w-7xl px-8 py-24 pt-16">
        <div className="grid grid-cols-12 gap-5 gap-y-16">
          <div className="col-span-12 md:col-span-6 relative z-10">
            <div
              className="relative h-6 inline-flex items-center uppercase text-xs mb-12 px-2"
              style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
            >
              <div className="flex items-center gap-0.5 overflow-hidden">
                <motion.span
                  initial={{ width: 0 }}
                  animate={{ width: "auto" }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className="block whitespace-nowrap overflow-hidden"
                  style={{ color: "#146e96" }}
                >
                  Ranking-first, verified by default
                </motion.span>
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: typingComplete ? [1, 0, 1, 0] : 0 }}
                  transition={{ duration: 1, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
                  className="block w-1.5 h-3 ml-0.5 rounded-sm"
                  style={{ background: "#146e96" }}
                />
              </div>
            </div>

            <h2 className="text-[34px] sm:text-[40px] font-normal leading-tight tracking-tight text-[#111A4A] mb-6">
              Every piece of work is scored before it's paid.{" "}
              <span className="opacity-40">Only what passes reaches your store.</span>
            </h2>

            <p className="text-lg leading-6 text-[#111A4A] opacity-60 mt-0 mb-6">
              Agencies charge for effort. Uplift's specialists are paid through escrow on Cardano, and Chainlink's
              decentralized oracle network re-checks each deliverable against live sources and fixed rules. Work that
              fails is refunded automatically and redone once.
            </p>

            <a
              href="#verification"
              className="relative inline-flex justify-center items-center leading-4 font-medium h-9 text-[#232730] bg-white/50 backdrop-blur-sm shadow-[0_0_0_1px_rgba(87,90,100,0.12)] transition-all duration-200 rounded-lg px-4 mt-5 text-sm group hover:shadow-[0_1px_2px_0_rgba(0,0,0,0.05),0_0_0_1px_rgba(87,90,100,0.18)]"
            >
              <span className="relative z-10 flex items-center gap-1">
                How verification works
                <ArrowRight className="w-4 h-4 -mr-1 transition-transform duration-150 group-hover:translate-x-1" />
              </span>
            </a>
          </div>

          <div className="col-span-12 md:col-span-6 hidden md:block">
            <div className="relative w-full h-[416px] -ml-[200px]">
              <div className="absolute top-0 left-[302px] w-[680px] h-[416px] pointer-events-none">
                <div className="relative w-full h-full">
                  {dataPoints.map((point) => {
                    const tint = point.fail ? "248, 113, 113" : "176, 200, 196"
                    return (
                      <motion.div
                        key={point.id}
                        initial={{ opacity: 0, height: 0 }}
                        animate={isVisible ? { opacity: [0, 1, 1], height: [0, point.height, point.height] } : {}}
                        transition={{ duration: 2, delay: point.delay, ease: [0.5, 0, 0.01, 1] }}
                        className="absolute w-1.5 rounded-[3px]"
                        style={{
                          left: `${point.left}px`,
                          top: `${point.top}px`,
                          background:
                            point.direction === "down"
                              ? `linear-gradient(rgb(${tint}) 0%, rgb(${tint}) 10%, rgba(156, 217, 93, 0.1) 40%, rgba(113, 210, 240, 0) 75%)`
                              : `linear-gradient(to top, rgb(${tint}) 0%, rgb(${tint}) 10%, rgba(156, 217, 93, 0.1) 40%, rgba(113, 210, 240, 0) 75%)`,
                        }}
                      >
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={isVisible ? { opacity: [0, 1] } : {}}
                          transition={{ duration: 0.3, delay: point.delay + 1.7 }}
                          className="absolute -left-[1px] w-2 h-2 rounded-full"
                          style={{
                            top: point.direction === "down" ? "0px" : `${point.height - 8}px`,
                            background: point.fail ? "#ef4444" : "#167E6C",
                          }}
                        />
                      </motion.div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12">
            <div className="grid grid-cols-12 gap-5 relative z-10">
              {stats.map((stat, index) => (
                <div key={index} className="col-span-6 md:col-span-3">
                  <motion.div
                    initial={{ opacity: 0, y: 20, filter: "blur(4px)" }}
                    animate={isVisible ? { opacity: 1, y: 0, filter: "blur(0px)" } : {}}
                    transition={{ duration: 1.5, delay: stat.delay, ease: [0.1, 0, 0.1, 1] }}
                    className="flex flex-col gap-2"
                  >
                    <span className="text-2xl font-medium leading-[26.4px] tracking-tight" style={{ color: "#146e96" }}>
                      {stat.value}
                    </span>
                    <p className="text-xs leading-[13.2px] text-[#7C7F88] m-0 whitespace-pre-line">{stat.description}</p>
                  </motion.div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
