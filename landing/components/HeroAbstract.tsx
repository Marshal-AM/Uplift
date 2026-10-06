"use client"

import { motion, useReducedMotion } from "framer-motion"

const BLOBS = [
  { size: "70%", left: "-10%", top: "-12%", color: "rgba(82,174,227,0.55)", x: [0, 60, -20, 0], y: [0, 40, 80, 0], d: 18 },
  { size: "60%", left: "45%", top: "35%", color: "rgba(21,109,149,0.75)", x: [0, -70, -30, 0], y: [0, -50, 30, 0], d: 22 },
  { size: "45%", left: "10%", top: "55%", color: "rgba(158,210,252,0.35)", x: [0, 50, 90, 0], y: [0, -30, -70, 0], d: 26 },
]

const RINGS = [
  { r: 70, dash: "0", opacity: 0.22, dur: 0 },
  { r: 120, dash: "2 10", opacity: 0.2, dur: 60 },
  { r: 175, dash: "70 20", opacity: 0.12, dur: 90 },
  { r: 230, dash: "1 14", opacity: 0.16, dur: 120 },
  { r: 290, dash: "0", opacity: 0.06, dur: 0 },
]

export function HeroAbstract() {
  const reduce = useReducedMotion()

  return (
    <div className="relative w-full h-full overflow-hidden" style={{ background: "linear-gradient(160deg,#0a1f30 0%,#0c2a40 55%,#0f3550 100%)" }}>
      {/* drifting light */}
      {BLOBS.map((b, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: b.size,
            height: b.size,
            left: b.left,
            top: b.top,
            background: `radial-gradient(circle at center, ${b.color} 0%, transparent 65%)`,
            filter: "blur(30px)",
          }}
          animate={reduce ? undefined : { x: b.x, y: b.y, scale: [1, 1.08, 0.96, 1] }}
          transition={{ duration: b.d, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        />
      ))}

      {/* fine dot grid */}
      <div
        className="absolute inset-0 opacity-[0.18]"
        style={{
          backgroundImage: "radial-gradient(rgba(255,255,255,0.6) 1px, transparent 1px)",
          backgroundSize: "26px 26px",
          maskImage: "radial-gradient(circle at 50% 50%, black 30%, transparent 75%)",
          WebkitMaskImage: "radial-gradient(circle at 50% 50%, black 30%, transparent 75%)",
        }}
      />

      {/* concentric rings */}
      <svg viewBox="0 0 600 600" className="absolute inset-0 w-full h-full">
        {RINGS.map((ring, i) => (
          <motion.circle
            key={i}
            cx={300}
            cy={300}
            r={ring.r}
            fill="none"
            stroke="#ffffff"
            strokeOpacity={ring.opacity}
            strokeWidth={1}
            strokeDasharray={ring.dash}
            style={{ originX: "300px", originY: "300px", transformBox: "view-box" }}
            animate={reduce || !ring.dur ? undefined : { rotate: i % 2 ? -360 : 360 }}
            transition={{ duration: ring.dur, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
          />
        ))}

        {/* orbiting points */}
        {[120, 175, 230].map((r, i) => (
          <motion.g
            key={r}
            style={{ originX: "300px", originY: "300px", transformBox: "view-box" }}
            animate={reduce ? undefined : { rotate: i % 2 ? -360 : 360 }}
            transition={{ duration: 24 + i * 12, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
          >
            <circle cx={300 + r} cy={300} r={3.5} fill="#ffffff" opacity={0.9} />
            <circle cx={300 + r} cy={300} r={10} fill="#9ed2fc" opacity={0.15} />
          </motion.g>
        ))}
      </svg>

      {/* soft core */}
      <motion.div
        className="absolute left-1/2 top-1/2 rounded-full"
        style={{
          width: "22%",
          height: "22%",
          x: "-50%",
          y: "-50%",
          background: "radial-gradient(circle, rgba(255,255,255,0.95) 0%, rgba(158,210,252,0.55) 35%, rgba(82,174,227,0) 70%)",
          filter: "blur(2px)",
        }}
        animate={reduce ? undefined : { scale: [1, 1.12, 1], opacity: [0.85, 1, 0.85] }}
        transition={{ duration: 6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
      />

      {/* vignette */}
      <div className="absolute inset-0 pointer-events-none" style={{ boxShadow: "inset 0 0 120px rgba(4,14,22,0.65)" }} />
    </div>
  )
}
