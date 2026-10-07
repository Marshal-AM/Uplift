import { Grip } from "lucide-react"
import Link from "next/link"
import { GoogleLogo } from "@/components/brand"
import { MockStrip } from "@/components/MockStrip"
import { SearchBox } from "@/components/search/SearchBox"
import { FirstQueryLink, Suggestions } from "@/components/search/Suggestions"

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col font-serp">
      <MockStrip />
      <header className="flex h-[60px] items-center justify-end gap-4 px-4 text-[13px] text-[#202124]">
        <Link href="/ads/" className="hover:underline">
          Google Ads (mock)
        </Link>
        <span className="cursor-default hover:underline">Images</span>
        <Grip className="h-6 w-6 text-[#5f6368]" aria-hidden />
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#3f7d5a] text-[14px] font-medium text-white">
          E
        </span>
      </header>

      <main className="flex flex-1 flex-col items-center px-4 pt-[min(18vh,170px)]">
        <GoogleLogo size={84} />
        <div className="mt-7 w-full max-w-[584px]">
          <SearchBox variant="home" />
        </div>
        <div className="mt-7 flex gap-3">
          <FirstQueryLink className="rounded border border-[#f8f9fa] bg-[#f8f9fa] px-4 py-2 text-[14px] text-[#3c4043] hover:border-[#dadce0] hover:shadow-sm">
            Google Search
          </FirstQueryLink>
          <Link
            href="/store/"
            className="rounded border border-[#f8f9fa] bg-[#f8f9fa] px-4 py-2 text-[14px] text-[#3c4043] hover:border-[#dadce0] hover:shadow-sm"
          >
            I&apos;m Feeling Lucky
          </Link>
        </div>
        <Suggestions />
      </main>

      <footer className="bg-[#f2f2f2] text-[14px] text-[#70757a]">
        <div className="border-b border-[#dadce0] px-8 py-3">United States · Mock</div>
        <div className="flex flex-wrap justify-between gap-2 px-8 py-3">
          <span className="flex gap-7">
            <span>About</span>
            <Link href="/ads/" className="hover:underline">
              Advertising
            </Link>
            <span>Business</span>
            <span>How Search works</span>
          </span>
          <span className="flex gap-7">
            <span>Privacy</span>
            <span>Terms</span>
            <span>Settings</span>
          </span>
        </div>
      </footer>
    </div>
  )
}
