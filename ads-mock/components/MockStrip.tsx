"use client"
import Link from "next/link"
import { dataActions, useDataset } from "@/lib/dataset"
import { longDate } from "@/lib/format"
import { actions } from "@/lib/store"

/** Present on every page: this is a mock, nothing is real, and where its data comes from. */
export function MockStrip() {
  return (
    <div className="font-roboto text-[12px]">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 bg-[#202124] px-4 py-1.5 text-[#e8eaed]">
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
      <SourceBar />
    </div>
  )
}

function SourceBar() {
  const { ds, status, error, runs } = useDataset()
  const connect = () => {
    const key = window.prompt("Uplift view key (the same key as the /live page):")
    if (key) dataActions.useKey(key)
  }
  const btn = "text-[#8ab4f8] hover:underline"
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[#3c4043] bg-[#2d2e31] px-4 py-1.5 text-[#bdc1c6]">
      {status === "live" && ds.run ? (
        <>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#81c995]" />
            <b className="font-medium text-[#e8eaed]">Live data from an Uplift run:</b> {ds.run.title}
            {ds.run.updated ? <span className="text-[#9aa0a6]">· {longDate(new Date(ds.run.updated))}</span> : null}
          </span>
          {runs.length > 1 && (
            <select
              value={ds.id}
              onChange={(e) => dataActions.selectRun(e.target.value)}
              aria-label="Choose a run"
              className="max-w-[260px] rounded bg-[#3c4043] px-2 py-0.5 text-[#e8eaed] outline-none"
            >
              {runs.map((r) => (
                <option key={r.task} value={r.task}>
                  {r.title} · {r.updated ? longDate(new Date(r.updated)) : r.task.slice(0, 8)}
                </option>
              ))}
            </select>
          )}
          <span className="text-[#9aa0a6]">Ads, keywords and products come from the agents; traffic is simulated.</span>
          <span className="ml-auto flex gap-4">
            {runs.length > 0 && (
              <button onClick={dataActions.latest} className={btn}>
                Latest run
              </button>
            )}
            <button onClick={dataActions.showDemo} className={btn}>
              Use demo data
            </button>
          </span>
        </>
      ) : status === "loading" ? (
        <span>Loading the Uplift run…</span>
      ) : (
        <>
          <span>
            {status === "error" ? (
              <>
                <b className="font-medium text-[#f28b82]">Couldn&apos;t load the run:</b> {error} Showing the demo store.
              </>
            ) : (
              <>Showing the demo store (fictional). Connect to see a finished Uplift run&apos;s campaigns here.</>
            )}
          </span>
          <button onClick={connect} className={`ml-auto ${btn}`}>
            Connect to Uplift runs
          </button>
        </>
      )}
    </div>
  )
}
