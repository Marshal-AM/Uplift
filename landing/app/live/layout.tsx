import type { Metadata } from "next"
import type React from "react"

export const metadata: Metadata = {
  title: "Uplift Live",
  description: "Every step behind an Uplift Task as it happens: the agent, the service it is using and the result.",
  robots: { index: false, follow: false },
}

export default function LiveLayout({ children }: { children: React.ReactNode }) {
  return children
}
