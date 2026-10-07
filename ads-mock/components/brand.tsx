import { Poppins } from "next/font/google"

const wordmark = Poppins({ subsets: ["latin"], weight: ["500"] })

const LETTERS: [string, string][] = [
  ["G", "#4285F4"], ["o", "#EA4335"], ["o", "#FBBC05"], ["g", "#4285F4"], ["l", "#34A853"], ["e", "#EA4335"],
]

/** Google-style wordmark, always paired with a "Mock" badge. */
export function GoogleLogo({ size = 30, badge = true }: { size?: number; badge?: boolean }) {
  return (
    <span className="inline-flex items-start gap-1 select-none" aria-label="Google (mock)">
      <span className={wordmark.className} style={{ fontSize: size, lineHeight: 1, letterSpacing: -size * 0.04 }}>
        {LETTERS.map(([l, c], i) => (
          <span key={i} style={{ color: c }}>
            {l}
          </span>
        ))}
      </span>
      {badge && <MockBadge />}
    </span>
  )
}

export function MockBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`rounded-sm bg-[#fce8b2] px-1 py-px font-roboto text-[10px] font-bold uppercase leading-none tracking-wide text-[#7a4f01] ${className}`}
    >
      Mock
    </span>
  )
}

/** Google Ads-style mark: a yellow and a blue bar and a green dot, plus the product name. */
export function AdsLogo() {
  return (
    <span className="inline-flex items-center gap-2 select-none" aria-label="Google Ads (mock)">
      <svg width="28" height="26" viewBox="0 0 192 176" aria-hidden>
        <rect x="70" y="-6" width="52" height="150" rx="26" transform="rotate(30 96 69)" fill="#FBBC04" />
        <rect x="118" y="20" width="52" height="150" rx="26" transform="rotate(-30 144 95)" fill="#4285F4" />
        <circle cx="40" cy="145" r="27" fill="#34A853" />
      </svg>
      <span className="font-roboto text-[22px] text-[#5f6368]">
        <span className={wordmark.className}>Google</span> Ads
      </span>
      <MockBadge />
    </span>
  )
}

/** Round site icon with an initial, the way Google shows favicons next to results. */
export function Favicon({ name, color, size = 26 }: { name: string; color: string; size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full border border-[#dadce0] bg-[#f1f3f4]"
      style={{ width: size, height: size }}
    >
      <span
        className="flex items-center justify-center rounded-full font-serp font-bold text-white"
        style={{ width: size * 0.66, height: size * 0.66, background: color, fontSize: size * 0.38 }}
      >
        {name[0]}
      </span>
    </span>
  )
}

/** A simple bottle product shot in SVG, so the mock needs no image files. */
export function BottleArt({ color, lid, size = 120, bg = "#f8f9fa" }: { color: string; lid: string; size?: number; bg?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" role="img" aria-label="Product image (mock)">
      <rect width="120" height="120" fill={bg} />
      <ellipse cx="60" cy="108" rx="22" ry="4" fill="#000" opacity="0.08" />
      <rect x="44" y="12" width="32" height="16" rx="4" fill={lid} />
      <rect x="47" y="14" width="26" height="2" rx="1" fill="#fff" opacity="0.25" />
      <path d="M46 28h28v6c0 4 8 8 8 16v52a6 6 0 0 1-6 6H44a6 6 0 0 1-6-6V50c0-8 8-12 8-16z" fill={color} />
      <rect x="44" y="52" width="5" height="44" rx="2.5" fill="#fff" opacity="0.18" />
    </svg>
  )
}
