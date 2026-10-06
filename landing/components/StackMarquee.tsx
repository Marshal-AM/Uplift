"use client"

const STACK = [
  { name: "Sokosumi", role: "Tasks, credits, approvals" },
  { name: "Masumi", role: "Identity, escrow, payment" },
  { name: "Cardano", role: "Escrow settlement" },
  { name: "Chainlink CRE", role: "Verification and gated publishing" },
  { name: "Kodosumi", role: "Agent runtime" },
  { name: "Amazon Bedrock", role: "LLM inference" },
  { name: "Shopify", role: "Store adapter (v1)" },
  { name: "Google Merchant Center", role: "Shopping feed" },
  { name: "Google Ads", role: "Paused campaigns" },
]

function Row({ reverse = false }: { reverse?: boolean }) {
  const items = [...STACK, ...STACK]
  return (
    <div className="relative overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_10%,black_90%,transparent)]">
      <div className={`flex gap-3 w-max ${reverse ? "animate-[uplift-marquee_48s_linear_infinite_reverse]" : "animate-[uplift-marquee_40s_linear_infinite]"}`}>
        {items.map((s, i) => (
          <div key={`${s.name}-${i}`} className="shrink-0 rounded-full border border-black/10 bg-white px-5 py-3 flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-[#156d95]" />
            <span className="text-[15px] font-medium text-[#202020] whitespace-nowrap">{s.name}</span>
            <span
              className="text-[12px] text-[#8a8a8a] whitespace-nowrap"
              style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
            >
              {s.role}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export const StackMarquee = () => {
  return (
    <section className="w-full py-20 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-8 mb-10 text-center">
        <p
          className="text-xs uppercase tracking-tight text-[#146e96] mb-3"
          style={{ fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
        >
          Built on
        </p>
        <h2 className="text-[30px] sm:text-[38px] leading-tight tracking-tight text-[#202020] font-medium">
          Real primitives, end to end.
        </h2>
      </div>
      <div className="space-y-3">
        <Row />
        <Row reverse />
      </div>
    </section>
  )
}
