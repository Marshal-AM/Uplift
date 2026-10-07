"use client"
import Link from "next/link"
import { useDataset } from "@/lib/dataset"

/** "Try …" links under the home search box: the run's (or demo's) top keywords. */
export function Suggestions() {
  const { SUGGESTED_QUERIES } = useDataset().ds
  return (
    <p className="mt-7 text-center text-[13px] text-[#4d5156]">
      Mock demo · try{" "}
      {SUGGESTED_QUERIES.map((q, i) => (
        <span key={q}>
          <Link href={`/search/?q=${encodeURIComponent(q)}`} className="text-[#1a0dab] hover:underline">
            {q}
          </Link>
          {i < SUGGESTED_QUERIES.length - 1 ? " · " : ""}
        </span>
      ))}
    </p>
  )
}

/** The home page's "Google Search" button searches the top keyword. */
export function FirstQueryLink({ className, children }: { className: string; children: React.ReactNode }) {
  const { SUGGESTED_QUERIES } = useDataset().ds
  return (
    <Link href={`/search/?q=${encodeURIComponent(SUGGESTED_QUERIES[0] ?? "")}`} className={className}>
      {children}
    </Link>
  )
}
