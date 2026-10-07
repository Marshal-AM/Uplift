"use client"
import { Check, CircleCheck, Monitor, Pencil, Smartphone, Sparkles, TrendingUp, Wallet, Wrench } from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import { BottleArt, MockBadge } from "@/components/brand"
import { ScoreRing } from "@/components/ads/Overview"
import {
  Card, METRIC_COLS, PageHeader, SimBar, StatusDot, StatusText, Table, Toolbar, metricCells, type Col,
} from "@/components/ads/ui"
import { RECOMMENDATIONS, optimizationScore, useAccount } from "@/components/ads/useAccount"
import {
  AD_GROUPS, CALLOUTS, CAMPAIGNS, DESCRIPTIONS, DISPLAY_PATH, ECONOMICS, HEADLINES, KEYWORDS, NEGATIVES, PRODUCT,
  SITELINKS, STORE, type Keyword,
} from "@/lib/data"
import { count, decimal, money, pct } from "@/lib/format"
import { PMAX_CHANNELS, ZERO, add, costPerConv, ctr, pmaxChannel, roas } from "@/lib/sim"
import { actions } from "@/lib/store"

const searchName = CAMPAIGNS[0].name
const fmtKeyword = (k: Pick<Keyword, "text" | "match">) => (k.match === "Exact match" ? `[${k.text}]` : `"${k.text}"`)
const Box = () => <input type="checkbox" aria-label="Select row" className="h-4 w-4 accent-[#1a73e8]" />

// --- Campaigns --------------------------------------------------------------------------------------

export function CampaignsPage() {
  const a = useAccount()
  const score = optimizationScore(a.s.applied, Object.values(a.s.status).includes("Enabled"))
  const cols: Col[] = [
    { label: "", width: "32px" }, { label: "", width: "48px" }, { label: "Campaign" }, { label: "Budget" }, { label: "Status" },
    { label: "Optimization score", right: true }, { label: "Campaign type" }, ...METRIC_COLS,
  ]
  return (
    <>
      <PageHeader title="Campaigns" />
      <SimBar />
      <Card>
        <Toolbar />
        <Table
          cols={cols}
          rows={CAMPAIGNS.map((c) => [
            <Box key="b" />,
            <StatusDot key="s" status={a.s.status[c.id]} onChange={(v) => actions.setStatus(c.id, v)} />,
            <span key="n" title={`${c.name} · ${c.bidStrategy}`} className="block max-w-[300px] truncate font-medium text-[#1a73e8]">{c.name}</span>,
            <BudgetCell key="g" id={c.id} value={a.s.budgets[c.id]} limited={a.s.status[c.id] === "Enabled" && a.limited[c.id]} />,
            <StatusText key="t" status={a.s.status[c.id]} learning={a.learning} limited={a.limited[c.id]} />,
            <span key="o" className="text-[#1a73e8]">{(score - (c.id === "pmax" ? 2.3 : 0)).toFixed(1)}%</span>,
            c.type,
            ...metricCells(a.campaigns[c.id]),
          ])}
          totals={[
            ["", "", "Total: All but removed campaigns", money(a.s.budgets.search + a.s.budgets.pmax) + "/day", "", "", "", ...metricCells(a.account)],
            ["", "", "Total: Account", "", "", "", "", ...metricCells(a.account)],
          ]}
        />
      </Card>
    </>
  )
}

function BudgetCell({ id, value, limited }: { id: "search" | "pmax"; value: number; limited: boolean }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value.toFixed(2))
  if (editing)
    return (
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const v = Number(draft)
          if (v > 0) actions.setBudget(id, Math.round(v * 100) / 100)
          setEditing(false)
        }}
      >
        <span className="text-[#5f6368]">$</span>
        <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} className="w-20 rounded border border-[#1a73e8] px-2 py-1 text-[14px] outline-none" />
        <button className="text-[13px] font-medium text-[#1a73e8]">Save</button>
      </form>
    )
  return (
    <button onClick={() => { setDraft(value.toFixed(2)); setEditing(true) }} className="group flex items-center gap-1.5 text-left">
      <span className={limited ? "text-[#b06000]" : ""}>{money(value)}/day</span>
      <Pencil className="h-3.5 w-3.5 text-[#5f6368] opacity-0 group-hover:opacity-100" />
    </button>
  )
}

// --- Ad groups --------------------------------------------------------------------------------------

export function AdGroupsPage() {
  const a = useAccount()
  const status = a.s.status.search
  return (
    <>
      <PageHeader title="Ad groups" />
      <SimBar />
      <Card>
        <Toolbar />
        <Table
          cols={[{ label: "", width: "32px" }, { label: "", width: "40px" }, { label: "Ad group" }, { label: "Campaign" }, { label: "Status" }, { label: "Default max. CPC", right: true }, ...METRIC_COLS]}
          rows={AD_GROUPS.map((g) => [
            <Box key="b" />,
            <StatusDot key="s" status="Enabled" />,
            <span key="n" className="font-medium text-[#1a73e8]">{g}</span>,
            <span key="c" className="text-[#1a73e8]">{searchName}</span>,
            status === "Enabled" ? "Eligible" : <span key="p" className="text-[#5f6368]">Campaign paused</span>,
            money(ECONOMICS.maxCpc),
            ...metricCells(a.adGroups[g] ?? ZERO),
          ])}
          totals={[["", "", "Total: All but removed ad groups", "", "", "", ...metricCells(a.campaigns.search)]]}
        />
      </Card>
    </>
  )
}

// --- Ads & assets -----------------------------------------------------------------------------------

const LABEL_STYLE: Record<string, string> = {
  Best: "bg-[#e6f4ea] text-[#137333]",
  Good: "bg-[#e8f0fe] text-[#1967d2]",
  Low: "bg-[#fce8e6] text-[#c5221f]",
  Learning: "bg-[#f1f3f4] text-[#5f6368]",
  Pending: "bg-[#f1f3f4] text-[#5f6368]",
}

export function AdsPage() {
  const a = useAccount()
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop")
  const excellent = a.s.applied.includes("headlines")
  const hasData = a.s.day >= 7 && a.s.status.search === "Enabled"
  const label = (l: string) => (hasData ? l : a.s.status.search === "Enabled" ? "Learning" : "Pending")
  const m = a.campaigns.search
  return (
    <>
      <PageHeader title="Ads" />
      <SimBar />
      <Card className="mb-5">
        <Toolbar />
        <Table
          cols={[{ label: "", width: "32px" }, { label: "", width: "40px" }, { label: "Ad" }, { label: "Ad group" }, { label: "Status" }, { label: "Ad type" }, { label: "Ad strength" }, ...METRIC_COLS]}
          rows={[[
            <Box key="b" />,
            <StatusDot key="s" status="Enabled" />,
            <div key="ad" className="max-w-[300px] whitespace-normal py-1 font-serp">
              <div className="text-[12px] text-[#202124]">Sponsored · {STORE.domain}/{DISPLAY_PATH.join("/")}</div>
              <div className="text-[14px] leading-[18px] text-[#1a0dab]">{HEADLINES[0].text} | {HEADLINES[1].text} | {HEADLINES[2].text}</div>
              <div className="text-[12px] leading-[16px] text-[#4d5156]">{DESCRIPTIONS[0].text}</div>
            </div>,
            "All ad groups (3)",
            a.s.status.search === "Enabled" ? "Eligible" : <span key="p" className="text-[#5f6368]">Campaign paused</span>,
            "Responsive search ad",
            <AdStrength key="st" excellent={excellent} />,
            ...metricCells(m),
          ]]}
        />
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card
          title="Ad preview"
          action={
            <span className="flex rounded-full border border-[#dadce0] p-0.5">
              {(["desktop", "mobile"] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setDevice(d)}
                  className={`flex items-center gap-1 rounded-full px-3 py-1 text-[13px] ${device === d ? "bg-[#e8f0fe] text-[#1967d2]" : "text-[#5f6368]"}`}
                >
                  {d === "desktop" ? <Monitor className="h-4 w-4" /> : <Smartphone className="h-4 w-4" />}
                  {d === "desktop" ? "Desktop" : "Mobile"}
                </button>
              ))}
            </span>
          }
        >
          <div className="flex justify-center bg-[#f1f3f4] px-5 py-6">
            <div className={`rounded-lg bg-white p-4 font-serp shadow ${device === "mobile" ? "w-[340px]" : "w-full max-w-[600px]"}`}>
              <div className="mb-2 text-[14px] font-bold text-[#202124]">Sponsored</div>
              <div className="text-[14px] text-[#202124]">{STORE.name}</div>
              <div className="text-[12px] text-[#4d5156]">https://www.{STORE.domain} › {DISPLAY_PATH.join(" › ")}</div>
              <div className={`mt-1 text-[#1a0dab] ${device === "mobile" ? "text-[18px] leading-[24px]" : "text-[20px] leading-[26px]"}`}>
                {HEADLINES[0].text} | {HEADLINES[1].text}
                {device === "desktop" && ` | ${HEADLINES[2].text}`}
              </div>
              <div className="mt-1 text-[14px] leading-[22px] text-[#4d5156]">
                {DESCRIPTIONS[0].text} {device === "desktop" && DESCRIPTIONS[1].text} {CALLOUTS[0]}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[14px] text-[#1a0dab]">
                {SITELINKS.map((s) => <span key={s.title}>{s.title}</span>)}
              </div>
            </div>
          </div>
          <p className="px-5 py-3 text-[12px] text-[#5f6368]">
            Ads may show in different combinations. Preview is a mock. <MockBadge />
          </p>
        </Card>

        <Card title="Asset performance">
          <Table
            cols={[{ label: "Asset" }, { label: "Asset type" }, { label: "Performance" }, { label: "Impr.", right: true }]}
            rows={[
              ...HEADLINES.map((h, i) => [h.text, "Headline", <Label key="l" text={label(h.label)} />, count(m.impressions * (0.32 - i * 0.022))]),
              ...DESCRIPTIONS.map((d, i) => [<span key="d" className="block max-w-[320px] truncate">{d.text}</span>, "Description", <Label key="l" text={label(d.label)} />, count(m.impressions * (0.55 - i * 0.12))]),
            ]}
          />
        </Card>
      </div>
    </>
  )
}

function Label({ text }: { text: string }) {
  return <span className={`rounded px-2 py-0.5 text-[12px] font-medium ${LABEL_STYLE[text]}`}>{text}</span>
}

function AdStrength({ excellent }: { excellent: boolean }) {
  const filled = excellent ? 4 : 3
  const color = excellent ? "#1e8e3e" : "#1a73e8"
  return (
    <span className="flex items-center gap-2">
      <span className="flex gap-0.5">
        {Array.from({ length: 4 }, (_, i) => (
          <span key={i} className="h-1.5 w-4 rounded-full" style={{ background: i < filled ? color : "#e8eaed" }} />
        ))}
      </span>
      <span style={{ color }} className="font-medium">{excellent ? "Excellent" : "Good"}</span>
    </span>
  )
}

// --- Keywords ---------------------------------------------------------------------------------------

const component = (qs: number, offset: number) => {
  const v = qs + offset
  return v >= 8 ? "Above average" : v >= 6 ? "Average" : "Below average"
}

export function KeywordsPage() {
  const a = useAccount()
  return (
    <>
      <PageHeader title="Search keywords" />
      <SimBar />
      <div className="mb-4 flex gap-3 rounded-lg border border-[#dadce0] bg-white p-4 text-[14px] leading-[20px] text-[#3c4043]">
        <Wallet className="h-5 w-5 shrink-0 text-[#1a73e8]" />
        <span>
          Bids set by Uplift from your break-even economics: price {money(ECONOMICS.price)} × margin {pct(ECONOMICS.margin)} ={" "}
          break-even cost per sale <b>{money(ECONOMICS.breakevenCpa)}</b>. Target {money(ECONOMICS.targetCpa)} × conversion rate{" "}
          {pct(ECONOMICS.conversionRate)} = max CPC <b>{money(ECONOMICS.maxCpc)}</b>. Cost / conv. above break-even shows in red.{" "}
          <MockBadge />
        </span>
      </div>
      <Card>
        <Toolbar />
        <Table
          cols={[
            { label: "", width: "32px" }, { label: "", width: "40px" }, { label: "Keyword" }, { label: "Ad group" }, { label: "Status" },
            { label: "Max. CPC", right: true }, { label: "Quality Score", right: true }, { label: "Exp. CTR" }, { label: "Ad relevance" },
            { label: "Landing page exp." }, ...METRIC_COLS,
          ]}
          rows={KEYWORDS.map((k) => {
            const m = a.keywords[k.text]
            const cells = metricCells(m)
            const cpa = m.conversions ? costPerConv(m) : 0
            cells[6] = m.conversions ? <span key="cpa" className={cpa > ECONOMICS.breakevenCpa ? "font-medium text-[#d93025]" : ""}>{money(cpa)}</span> : "—"
            return [
              <Box key="b" />,
              <StatusDot key="s" status="Enabled" />,
              <span key="k" className="text-[#1a73e8]">{fmtKeyword(k)}</span>,
              k.adGroup,
              a.s.status.search === "Enabled" ? (k.demand < 30 ? "Low search volume" : "Eligible") : <span key="p" className="text-[#5f6368]">Campaign paused</span>,
              money(ECONOMICS.maxCpc),
              `${k.qualityScore}/10`,
              component(k.qualityScore, 0),
              component(k.qualityScore, 1),
              component(k.qualityScore, -1),
              ...cells,
            ]
          })}
          totals={[["", "", "Total: All but removed keywords", "", "", "", "", "", "", "", ...metricCells(a.campaigns.search)]]}
        />
      </Card>
    </>
  )
}

// --- Search terms -----------------------------------------------------------------------------------

export function SearchTermsPage() {
  const a = useAccount()
  const [picked, setPicked] = useState<string[]>([])
  const [note, setNote] = useState("")
  const toggle = (t: string) => setPicked((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]))
  const kwFor = (text: string) => KEYWORDS.find((k) => k.text === text)!
  return (
    <>
      <PageHeader title="Search terms" />
      <SimBar />
      <Card>
        {picked.length > 0 ? (
          <div className="flex items-center gap-4 border-b border-[#dadce0] bg-[#e8f0fe] px-4 py-2.5 text-[14px]">
            <span className="font-medium text-[#1967d2]">{picked.length} selected</span>
            {["Add as keyword", "Add as negative keyword"].map((l) => (
              <button
                key={l}
                className="font-medium text-[#1a73e8] hover:underline"
                onClick={() => { setNote(`Mock: "${l}" for ${picked.length} term(s). Nothing changes in a real Google Ads account.`); setPicked([]) }}
              >
                {l}
              </button>
            ))}
          </div>
        ) : (
          <Toolbar />
        )}
        {note && <div className="border-b border-[#dadce0] bg-[#fef7e0] px-4 py-2 text-[13px] text-[#3c4043]">{note}</div>}
        <Table
          cols={[{ label: "", width: "32px" }, { label: "Search term" }, { label: "Match type" }, { label: "Added / Excluded" }, { label: "Ad group" }, { label: "Keyword" }, ...METRIC_COLS]}
          rows={a.terms
            .filter((t) => t.excluded || t.m.impressions > 0 || a.s.day === 0)
            .map((t) => {
              const k = kwFor(t.keyword)
              const exactish = t.term === k.text
              return [
                <input key="c" type="checkbox" checked={picked.includes(t.term)} onChange={() => toggle(t.term)} className="h-4 w-4 accent-[#1a73e8]" />,
                t.term,
                k.match === "Exact match" ? "Exact match" : exactish ? "Exact match (close variant)" : "Phrase match",
                t.excluded ? <span key="e" className="text-[#d93025]">Excluded</span> : t.added ? "Added" : "None",
                k.adGroup,
                fmtKeyword(k),
                ...metricCells(t.m),
              ]
            })}
          totals={[["", "Total: Search terms", "", "", "", "", ...metricCells(a.campaigns.search)]]}
        />
      </Card>
    </>
  )
}

// --- Negative keywords ------------------------------------------------------------------------------

export function NegativeKeywordsPage() {
  return (
    <>
      <PageHeader title="Negative search keywords" />
      <Card>
        <Toolbar />
        <Table
          cols={[{ label: "", width: "32px" }, { label: "Negative keyword" }, { label: "Match type" }, { label: "Added to" }, { label: "Level" }]}
          rows={NEGATIVES.map((n) => [<Box key="b" />, `"${n}"`, "Phrase match", <span key="c" className="text-[#1a73e8]">{searchName}</span>, "Campaign"])}
        />
        <p className="px-4 py-3 text-[12px] text-[#5f6368]">
          Added by Uplift from off-target and competitor-brand searches, and checked so none blocks one of your own keywords. <MockBadge />
        </p>
      </Card>
    </>
  )
}

// --- Products (Performance Max) ---------------------------------------------------------------------

export function ProductsPage() {
  const a = useAccount()
  const m = a.campaigns.pmax
  const on = a.s.status.pmax === "Enabled"
  return (
    <>
      <PageHeader title="Products" />
      <SimBar />
      <Card className="mb-5">
        <Toolbar />
        <Table
          cols={[
            { label: "Product" }, { label: "Item ID" }, { label: "Price", right: true }, { label: "Status" }, { label: "Impr.", right: true },
            { label: "Clicks", right: true }, { label: "CTR", right: true }, { label: "Cost", right: true }, { label: "Conversions", right: true },
            { label: "Conv. value", right: true }, { label: "Conv. value / cost", right: true },
          ]}
          rows={[[
            <span key="p" className="flex items-center gap-3">
              <span className="overflow-hidden rounded"><BottleArt color={PRODUCT.color} lid="#c8a46e" size={40} /></span>
              <span className="font-medium text-[#1a73e8]">{PRODUCT.title}</span>
            </span>,
            PRODUCT.id,
            money(PRODUCT.price),
            on ? "Eligible" : <span key="s" className="text-[#5f6368]">Campaign paused</span>,
            count(m.impressions), count(m.clicks), m.impressions ? pct(ctr(m)) : "—", money(m.cost), decimal(m.conversions),
            money(m.value), m.cost ? decimal(roas(m)) : "—",
          ]]}
        />
      </Card>
      <Card title="Performance Max by network">
        <Table
          cols={[{ label: "Network" }, ...METRIC_COLS]}
          rows={PMAX_CHANNELS.map((c) => [c.name, ...metricCells(pmaxChannel(m, c.share))])}
          totals={[["Total", ...metricCells(PMAX_CHANNELS.reduce((acc, c) => add(acc, pmaxChannel(m, c.share)), ZERO))]]}
        />
      </Card>
    </>
  )
}

// --- Recommendations --------------------------------------------------------------------------------

export function RecommendationsPage() {
  const a = useAccount()
  const enabled = Object.values(a.s.status).includes("Enabled")
  const score = optimizationScore(a.s.applied, enabled)
  const points = Object.fromEntries(RECOMMENDATIONS.map((r) => [r.id, r.points]))
  const weeklyGain = Math.round(a.campaigns.search.clicks * (a.lostToBudget / Math.max(0.01, 1 - a.lostToBudget)) * (7 / Math.max(1, a.s.day)))
  const cards = [
    {
      id: "enable", show: !enabled, icon: Wrench, category: "Repairs", title: "Enable your campaigns",
      body: "Both campaigns are paused, so your ads aren't showing. Turn them on to start getting traffic.",
      impact: "Ads start showing", apply: actions.enableAll, view: "/ads/campaigns/",
    },
    {
      id: "budget", show: true, icon: Wallet, category: "Bidding & budgets", title: "Raise your budget",
      body: a.limited.search
        ? `Your Search campaign is limited by budget. Raising it from ${money(a.s.budgets.search)} to $26.00/day could get about ${count(Math.max(weeklyGain, 0))} more clicks a week.`
        : "Your Search campaign may become limited by budget at busier times. A budget of $26.00/day keeps it showing all day.",
      impact: "+ clicks", apply: () => { actions.setBudget("search", 26); actions.apply("budget") }, view: "/ads/campaigns/",
    },
    {
      id: "headlines", show: true, icon: Sparkles, category: "Ads & assets", title: "Improve your responsive search ad",
      body: "Add 3 more unique headlines that include your popular keywords to raise ad strength from Good to Excellent.",
      impact: "Ad strength: Excellent", apply: () => actions.apply("headlines"), view: "/ads/ads/",
    },
    {
      id: "troas", show: true, icon: TrendingUp, category: "Bidding & budgets", title: "Bid more efficiently with Target ROAS",
      body: "Performance Max has enough conversions to bid toward a 230% target return on ad spend.",
      impact: "+ conv. value", apply: () => actions.apply("troas"), view: "/ads/products/",
    },
    {
      id: "negatives", show: true, icon: Check, category: "Keywords & targeting", title: "Add negative keywords",
      body: "2 search terms (“wholesale”, “kids”) don't match your product. Keep blocking them across new campaigns.",
      impact: "− wasted spend", apply: () => actions.apply("negatives"), view: "/ads/negative-keywords/",
    },
  ].filter((c) => c.show)

  return (
    <>
      <PageHeader title="Recommendations" />
      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-6 p-5">
          <ScoreRing value={score} size={120} />
          <div>
            <div className="text-[16px] font-medium">Optimization score</div>
            <p className="mt-1 max-w-[520px] text-[14px] leading-[20px] text-[#5f6368]">
              An estimate of how well your account is set to perform. Applying a recommendation raises your score by the
              amount shown. Recommendations here are mock. <MockBadge />
            </p>
          </div>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        {cards.map((c) => {
          const done = a.s.applied.includes(c.id)
          const Icon = c.icon
          return (
            <Card key={c.id} className={done ? "opacity-70" : ""}>
              <div className="p-5">
                <div className="mb-3 flex items-center justify-between text-[12px] font-medium uppercase tracking-wide text-[#5f6368]">
                  <span className="flex items-center gap-2"><Icon className="h-4 w-4 text-[#1a73e8]" /> {c.category}</span>
                  <span className="rounded-full bg-[#e8f0fe] px-2 py-0.5 normal-case tracking-normal text-[#1967d2]">+{points[c.id].toFixed(1)}%</span>
                </div>
                <div className="text-[16px] font-medium text-[#202124]">{c.title}</div>
                <p className="mt-1.5 text-[14px] leading-[20px] text-[#5f6368]">{c.body}</p>
                <div className="mt-2 text-[13px] text-[#188038]">{c.impact}</div>
                <div className="mt-4 flex justify-end gap-2">
                  {done ? (
                    <span className="flex items-center gap-1.5 text-[14px] font-medium text-[#188038]"><CircleCheck className="h-4 w-4" /> Applied</span>
                  ) : (
                    <>
                      <Link href={c.view} className="rounded px-4 py-2 text-[14px] font-medium text-[#1a73e8] hover:bg-[#f1f8ff]">View</Link>
                      <button onClick={c.apply} className="rounded border border-[#dadce0] px-4 py-2 text-[14px] font-medium text-[#1a73e8] hover:bg-[#f1f8ff]">Apply</button>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </>
  )
}
