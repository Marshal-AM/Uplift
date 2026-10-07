"use client"
import {
  Bell, ChevronDown, CircleHelp, CreditCard, Megaphone, Menu, Plus, RefreshCw, Search, Settings, Trophy, Wrench,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { AdsLogo } from "@/components/brand"
import { MockStrip } from "@/components/MockStrip"
import { ACCOUNT } from "@/lib/data"

type NavItem = { label: string; href?: string }
const MENU: { group?: string; items: NavItem[] }[] = [
  { items: [{ label: "Overview", href: "/ads/" }, { label: "Recommendations", href: "/ads/recommendations/" }, { label: "Insights and reports" }] },
  {
    group: "Campaigns",
    items: [
      { label: "Campaigns", href: "/ads/campaigns/" },
      { label: "Ad groups", href: "/ads/ad-groups/" },
      { label: "Ads", href: "/ads/ads/" },
      { label: "Assets" },
      { label: "Products", href: "/ads/products/" },
    ],
  },
  {
    group: "Audiences, keywords, and content",
    items: [
      { label: "Search keywords", href: "/ads/keywords/" },
      { label: "Search terms", href: "/ads/search-terms/" },
      { label: "Negative search keywords", href: "/ads/negative-keywords/" },
      { label: "Audiences" },
    ],
  },
  { items: [{ label: "Change history" }] },
]

const RAIL = [
  { label: "Create", icon: Plus, create: true },
  { label: "Campaigns", icon: Megaphone, active: true },
  { label: "Goals", icon: Trophy },
  { label: "Tools", icon: Wrench },
  { label: "Billing", icon: CreditCard },
  { label: "Admin", icon: Settings },
]

export function AdsShell({ children }: { children: React.ReactNode }) {
  const path = usePathname()
  const norm = (p: string) => (p.endsWith("/") ? p : p + "/")
  return (
    <div className="flex min-h-screen flex-col bg-[#f8f9fa] font-roboto text-[#202124]">
      <MockStrip />
      <header className="flex h-16 items-center gap-4 border-b border-[#dadce0] bg-white px-4">
        <Menu className="h-6 w-6 text-[#5f6368]" aria-hidden />
        <Link href="/ads/">
          <AdsLogo />
        </Link>
        <span className="mx-1 hidden h-8 w-px bg-[#dadce0] md:block" />
        <button className="hidden items-center gap-2 rounded px-2 py-1 text-left hover:bg-[#f1f3f4] md:flex">
          <span className="leading-tight">
            <span className="block text-[14px] font-medium">{ACCOUNT.name}</span>
            <span className="block text-[12px] text-[#5f6368]">{ACCOUNT.customerId}</span>
          </span>
          <ChevronDown className="h-4 w-4 text-[#5f6368]" />
        </button>
        <div className="mx-auto hidden h-11 max-w-[460px] flex-1 items-center gap-3 rounded-lg bg-[#f1f3f4] px-4 text-[15px] text-[#5f6368] lg:flex">
          <Search className="h-5 w-5" />
          Search for a page or campaign
        </div>
        <div className="ml-auto flex items-center gap-1 text-[#5f6368] lg:ml-0">
          {[RefreshCw, CircleHelp, Bell].map((Icon, i) => (
            <span key={i} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-[#f1f3f4]">
              <Icon className="h-5 w-5" />
            </span>
          ))}
          <span className="ml-2 flex h-8 w-8 items-center justify-center rounded-full bg-[#3f7d5a] text-[14px] font-medium text-white">
            E
          </span>
        </div>
      </header>

      <div className="flex flex-1">
        <nav className="hidden w-[80px] shrink-0 flex-col items-center gap-3 border-r border-[#dadce0] bg-white pt-4 md:flex">
          {RAIL.map(({ label, icon: Icon, create, active }) => (
            <div key={label} className="flex flex-col items-center gap-1 text-[12px] text-[#3c4043]">
              <span
                className={`flex items-center justify-center ${
                  create
                    ? "h-10 w-10 rounded-xl bg-white shadow-[0_1px_3px_rgba(60,64,67,0.3),0_4px_8px_3px_rgba(60,64,67,0.15)]"
                    : `h-8 w-14 rounded-full ${active ? "bg-[#e8f0fe]" : ""}`
                }`}
              >
                <Icon className={`h-5 w-5 ${create ? "text-[#1a73e8]" : active ? "text-[#1967d2]" : "text-[#5f6368]"}`} strokeWidth={create ? 2.5 : 2} />
              </span>
              <span className={active ? "font-medium text-[#1967d2]" : ""}>{label}</span>
            </div>
          ))}
        </nav>

        <aside className="hidden w-[248px] shrink-0 border-r border-[#dadce0] bg-white py-2 lg:block">
          {MENU.map((section, i) => (
            <div key={i} className={i > 0 ? "border-t border-[#e8eaed] py-1" : "py-1"}>
              {section.group && (
                <div className="flex items-center justify-between px-6 py-2 text-[14px] font-medium text-[#202124]">
                  {section.group}
                  <ChevronDown className="h-4 w-4 rotate-180 text-[#5f6368]" />
                </div>
              )}
              {section.items.map((item) => {
                const active = item.href && norm(path) === item.href
                const cls = `mr-3 block rounded-r-full py-2 text-[14px] ${section.group ? "pl-10" : "pl-6"} ${
                  active ? "bg-[#e8f0fe] font-medium text-[#1967d2]" : item.href ? "text-[#3c4043] hover:bg-[#f1f3f4]" : "cursor-default text-[#9aa0a6]"
                }`
                return item.href ? (
                  <Link key={item.label} href={item.href} className={cls}>
                    {item.label}
                  </Link>
                ) : (
                  <span key={item.label} className={cls} title="Not part of the mock">
                    {item.label}
                  </span>
                )
              })}
            </div>
          ))}
        </aside>

        <main className="min-w-0 flex-1 px-4 py-5 md:px-7">
          <MobileMenu path={norm(path)} />
          {children}
        </main>
      </div>
    </div>
  )
}

function MobileMenu({ path }: { path: string }) {
  const items = MENU.flatMap((s) => s.items).filter((i) => i.href)
  return (
    <div className="no-scrollbar mb-4 flex gap-2 overflow-x-auto lg:hidden">
      {items.map((i) => (
        <Link
          key={i.label}
          href={i.href!}
          className={`whitespace-nowrap rounded-full border px-3 py-1 text-[13px] ${
            path === i.href ? "border-[#1a73e8] bg-[#e8f0fe] text-[#1967d2]" : "border-[#dadce0] bg-white text-[#3c4043]"
          }`}
        >
          {i.label}
        </Link>
      ))}
    </div>
  )
}
