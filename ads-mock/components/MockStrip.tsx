"use client"
import Link from "next/link"
import { actions } from "@/lib/store"

/** Present on every page: this is a mock, nothing is real. */
export function MockStrip() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 bg-[#202124] px-4 py-1.5 font-roboto text-[12px] text-[#e8eaed]">
      <span>
        <b className="mr-1.5 rounded-sm bg-[#fdd663] px-1 text-[#202124]">MOCK</b>
        Simulated Google Search and Google Ads for the Uplift demo. Not affiliated with Google. No real searches,
        ads or spend.
      </span>
      <span className="flex items-center gap-4">
        <Link href="/" className="hover:underline">
          Search (mock)
        </Link>
        <Link href="/ads/" className="hover:underline">
          Google Ads (mock)
        </Link>
        <button
          onClick={() => {
            if (confirm("Reset the mock account? Campaigns go back to Paused and the simulation clears.")) actions.reset()
          }}
          className="text-[#8ab4f8] hover:underline"
        >
          Reset mock
        </button>
      </span>
    </div>
  )
}
