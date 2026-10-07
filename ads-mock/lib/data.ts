// All data in this app is hardcoded mock data for the Uplift demo. Every store, brand, site and number is
// fictional; nothing here comes from or goes to Google.

export const ACCOUNT = {
  name: "Evergreen Bottle Co. (mock)",
  customerId: "123-456-7890",
  currency: "USD",
  email: "owner@evergreenbottle.example",
}

export const STORE = {
  name: "Evergreen Bottle Co.",
  domain: "evergreenbottle.example",
  url: "https://www.evergreenbottle.example",
}

export const PRODUCT = {
  id: "bamboo-insulated-bottle",
  title: "Bamboo Insulated Bottle – 750 ml",
  shortTitle: "Bamboo Insulated Bottle 750 ml",
  price: 34,
  rating: 4.8,
  reviews: 212,
  color: "#3f7d5a",
  bullets: [
    "Double-wall stainless steel: cold for 24 hours, hot for 12",
    "Real bamboo lid with a leak-proof silicone seal",
    "BPA-free, plastic-free, fits most cup holders",
    "Free US shipping over $40 and 30-day returns",
  ],
}

// Uplift's ads specialist (Sasha) sizes bids from the product's economics: max CPC = target CPA × conversion rate.
export const ECONOMICS = {
  price: 34,
  margin: 0.62,
  breakevenCpa: 21.08,
  targetCpa: 14.76,
  conversionRate: 0.025,
  maxCpc: 0.37,
  monthlyBudget: 1000,
}

export type CampaignId = "search" | "pmax"

export const CAMPAIGNS: {
  id: CampaignId
  name: string
  type: "Search" | "Performance Max"
  budget: number
  bidStrategy: string
  target?: string
}[] = [
  {
    id: "search",
    name: "Uplift · Bamboo Bottle · Search",
    type: "Search",
    budget: 19.74,
    bidStrategy: "Maximize clicks",
    target: "Max CPC $0.37",
  },
  {
    id: "pmax",
    name: "Uplift · Bamboo Bottle · Performance Max",
    type: "Performance Max",
    budget: 13.16,
    bidStrategy: "Maximize conversion value",
    target: "Target ROAS 230%",
  },
]

export type MatchType = "Exact match" | "Phrase match"

export type Keyword = {
  text: string
  match: MatchType
  adGroup: string
  demand: number // 0–100 search demand signal from the keyword specialist (Kai)
  qualityScore: number
  ctr: number // expected click-through rate at the top position
}

export const AD_GROUPS = ["Bamboo bottle", "Insulated bottle", "Eco gifts"] as const

export const KEYWORDS: Keyword[] = [
  { text: "bamboo water bottle", match: "Exact match", adGroup: "Bamboo bottle", demand: 100, qualityScore: 8, ctr: 0.062 },
  { text: "insulated bamboo water bottle", match: "Phrase match", adGroup: "Bamboo bottle", demand: 82, qualityScore: 9, ctr: 0.071 },
  { text: "bamboo lid water bottle", match: "Phrase match", adGroup: "Bamboo bottle", demand: 64, qualityScore: 8, ctr: 0.058 },
  { text: "insulated water bottle 750ml", match: "Phrase match", adGroup: "Insulated bottle", demand: 58, qualityScore: 7, ctr: 0.044 },
  { text: "stainless steel water bottle bamboo lid", match: "Exact match", adGroup: "Insulated bottle", demand: 40, qualityScore: 8, ctr: 0.066 },
  { text: "leak proof insulated bottle", match: "Phrase match", adGroup: "Insulated bottle", demand: 47, qualityScore: 6, ctr: 0.036 },
  { text: "eco friendly water bottle", match: "Phrase match", adGroup: "Eco gifts", demand: 71, qualityScore: 6, ctr: 0.031 },
  { text: "plastic free water bottle", match: "Phrase match", adGroup: "Eco gifts", demand: 55, qualityScore: 7, ctr: 0.039 },
  { text: "sustainable gift bottle", match: "Exact match", adGroup: "Eco gifts", demand: 22, qualityScore: 5, ctr: 0.027 },
]

// Phrase negatives. Like Uplift's ads specialist, none of them blocks one of the campaign's own keywords.
export const NEGATIVES = ["wholesale", "bulk", "diy", "near me", "glass", "kids", "northpeak", "cheap"]

export const HEADLINES: { text: string; label: "Best" | "Good" | "Low" | "Learning" }[] = [
  { text: "Bamboo Insulated Bottle", label: "Best" },
  { text: "Cold for 24 Hours", label: "Best" },
  { text: "Plastic-Free Bamboo Lid", label: "Good" },
  { text: "Leak-Proof 750 ml Bottle", label: "Good" },
  { text: "Free US Shipping Over $40", label: "Good" },
  { text: "Double-Wall Steel Bottle", label: "Good" },
  { text: "Hot 12h, Cold 24h", label: "Learning" },
  { text: "Evergreen Bottle Co.", label: "Good" },
  { text: "Shop the Bamboo Bottle", label: "Low" },
  { text: "BPA-Free Stainless Steel", label: "Good" },
  { text: "30-Day Free Returns", label: "Learning" },
  { text: "Fits Most Cup Holders", label: "Low" },
]

export const DESCRIPTIONS: { text: string; label: "Best" | "Good" | "Low" | "Learning" }[] = [
  { text: "Double-wall steel keeps drinks cold 24 hours and hot 12. Real bamboo lid, no plastic.", label: "Best" },
  { text: "Leak-proof and BPA-free. Free US shipping over $40 and 30-day returns.", label: "Good" },
  { text: "750 ml that fits most cup holders. Rated 4.8 by 212 customers. Order yours today.", label: "Good" },
  { text: "Made to last, built to be refilled. Shop the Bamboo Insulated Bottle at Evergreen.", label: "Learning" },
]

export const DISPLAY_PATH = ["bottles", "bamboo"]

export const SITELINKS = [
  { title: "Shop All Bottles", line: "Insulated bottles in 6 colors" },
  { title: "Gift Sets", line: "Bottle, sleeve and brush bundle" },
  { title: "Bottle Care", line: "How to clean a bamboo lid" },
  { title: "Our Story", line: "Plastic-free since 2019" },
]

export const CALLOUTS = ["30-Day Returns", "Plastic-Free Packaging", "Ships in 1-2 Days"]

export type TextAd = {
  advertiser: string
  domain: string
  path: string
  title: string
  description: string
  sitelinks?: string[]
  color: string
}

export const COMPETITOR_ADS: TextAd[] = [
  {
    advertiser: "Northpeak Outdoors",
    domain: "northpeak.example",
    path: "insulated-bottles",
    title: "Northpeak® Insulated Bottles | Built for the Trail",
    description: "Ice cold for 24 hrs. Shop 20+ colors and sizes. Free shipping on orders $50+.",
    color: "#1f3a5f",
  },
  {
    advertiser: "Terra Hydrate",
    domain: "terrahydrate.example",
    path: "eco",
    title: "Eco Water Bottles - Plastic-Free Designs",
    description: "Reusable bottles made from recycled steel. Join 40,000 happy refillers. Shop now.",
    color: "#7a5c2e",
  },
]

export type Offer = {
  id: string
  title: string
  seller: string
  price: number
  was?: number
  rating: number | null
  reviews: number
  image?: string | null
  shipping: string
  color: string
  lid: string
  ours?: boolean
}

export const OFFERS: Offer[] = [
  { id: "ours", title: "Bamboo Insulated Bottle – 750 ml", seller: STORE.name, price: 34, rating: 4.8, reviews: 212, shipping: "Free shipping over $40", color: "#3f7d5a", lid: "#c8a46e", ours: true },
  { id: "np", title: "Northpeak 24 oz Trail Bottle", seller: "Northpeak Outdoors", price: 39.95, rating: 4.7, reviews: 1240, shipping: "Free shipping", color: "#1f3a5f", lid: "#222831" },
  { id: "th", title: "Terra Bamboo Flask 500 ml", seller: "Terra Hydrate", price: 27.99, was: 32, rating: 4.5, reviews: 341, shipping: "$4.99 shipping", color: "#d9cfc1", lid: "#b8935a" },
  { id: "kh", title: "Kinfolk Steel Bottle 750 ml", seller: "Kinfolk Home", price: 31.5, rating: 4.6, reviews: 88, shipping: "Free shipping", color: "#9aa5ad", lid: "#59636b" },
  { id: "ag", title: "AquaGrove Eco Bottle 600 ml", seller: "AquaGrove", price: 24, rating: 4.3, reviews: 156, shipping: "Free 5-day shipping", color: "#6aa6c9", lid: "#e8e2d6" },
  { id: "ss", title: "Summit Bamboo Tumbler 20 oz", seller: "Summit Supply", price: 29, rating: 4.4, reviews: 402, shipping: "Free shipping", color: "#c45c3c", lid: "#a8814f" },
  { id: "lw", title: "Lowtide Insulated Bottle 1 L", seller: "Lowtide Goods", price: 42, rating: 4.6, reviews: 517, shipping: "Free shipping", color: "#2b2b2b", lid: "#bfa173" },
  { id: "fn", title: "Fernway Kids Bamboo Bottle", seller: "Fernway", price: 19.99, rating: 4.2, reviews: 63, shipping: "$3.99 shipping", color: "#e0b84a", lid: "#c9a36a" },
]

export type Organic = { site: string; domain: string; crumbs: string[]; title: string; snippet: string; date?: string; color: string }

export const ORGANIC: Organic[] = [
  {
    site: "Trailguide",
    domain: "trailguide.example",
    crumbs: ["gear", "best-insulated-water-bottles"],
    title: "The 9 Best Insulated Water Bottles of 2026, Tested and Reviewed",
    snippet:
      "We filled 31 bottles with ice water and left them in a hot car for 24 hours. Our top picks for keeping drinks cold, including two with bamboo lids.",
    date: "Aug 14, 2026",
    color: "#e2711d",
  },
  {
    site: STORE.name,
    domain: STORE.domain,
    crumbs: ["products", "bamboo-insulated-bottle"],
    title: "Bamboo Insulated Bottle – 750 ml – Evergreen Bottle Co.",
    snippet:
      "Double-wall stainless steel keeps drinks cold for 24 hours and hot for 12. Real bamboo lid with a leak-proof seal. Free US shipping over $40.",
    color: "#3f7d5a",
  },
  {
    site: "Green Living Forum",
    domain: "greenlivingforum.example",
    crumbs: ["threads", "are-bamboo-bottles-worth-it"],
    title: "Are bamboo lid water bottles actually worth it?",
    snippet:
      "I switched to a bamboo lid bottle last spring. The lid needs to dry fully between washes, but it hasn't cracked or smelled. Insulation is as good as my old one…",
    date: "Mar 2, 2026",
    color: "#5a8f29",
  },
  {
    site: "EcoHome Guide",
    domain: "ecohomeguide.example",
    crumbs: ["kitchen", "plastic-free-water-bottles"],
    title: "Plastic-Free Water Bottles: A Buyer's Guide",
    snippet:
      "Stainless steel, glass or bamboo? We compare durability, insulation and how plastic-free each design really is, with prices from $19 to $45.",
    date: "Jan 21, 2026",
    color: "#2a7f83",
  },
  {
    site: "Northpeak Outdoors",
    domain: "northpeak.example",
    crumbs: ["collections", "bottles"],
    title: "Insulated Water Bottles | Northpeak Outdoors",
    snippet: "Shop insulated bottles built for the trail. Lifetime warranty. Available in 20+ colors and sizes from 12 oz to 64 oz.",
    color: "#1f3a5f",
  },
]

export const PEOPLE_ALSO_ASK = [
  {
    q: "Are bamboo water bottles insulated?",
    a: "Most bamboo water bottles use a double-wall stainless steel body with a bamboo lid or sleeve. The steel body provides the insulation; the bamboo is the cap.",
  },
  {
    q: "Do bamboo lids get moldy?",
    a: "Bamboo can absorb moisture. Hand-wash the lid, let it dry fully upside down, and oil it occasionally with food-safe oil to keep it sealed.",
  },
  {
    q: "How long do insulated bottles keep water cold?",
    a: "A good double-wall vacuum bottle keeps drinks cold for about 24 hours and hot for about 12, depending on the lid and how full it is.",
  },
  {
    q: "What is the most eco-friendly water bottle?",
    a: "A durable stainless steel bottle you reuse for years usually has the lowest footprint per use. Plastic-free lids reduce microplastics further.",
  },
]

// Search terms people actually typed, attributed to the keyword that matched them (share = part of that
// keyword's traffic). Excluded terms were added as negatives by the Uplift plan.
export const SEARCH_TERMS: { term: string; keyword: string; share: number; added?: boolean; excluded?: boolean }[] = [
  { term: "bamboo water bottle", keyword: "bamboo water bottle", share: 1, added: true },
  { term: "insulated bamboo water bottle", keyword: "insulated bamboo water bottle", share: 0.46, added: true },
  { term: "best insulated bamboo water bottle", keyword: "insulated bamboo water bottle", share: 0.31 },
  { term: "insulated bamboo water bottle 750ml", keyword: "insulated bamboo water bottle", share: 0.23 },
  { term: "bamboo lid water bottle", keyword: "bamboo lid water bottle", share: 0.58, added: true },
  { term: "stainless water bottle with bamboo lid", keyword: "bamboo lid water bottle", share: 0.42 },
  { term: "insulated water bottle 750ml", keyword: "insulated water bottle 750ml", share: 0.67, added: true },
  { term: "750ml insulated water bottle cold 24 hours", keyword: "insulated water bottle 750ml", share: 0.33 },
  { term: "stainless steel water bottle bamboo lid", keyword: "stainless steel water bottle bamboo lid", share: 1, added: true },
  { term: "leak proof insulated bottle", keyword: "leak proof insulated bottle", share: 0.7, added: true },
  { term: "leak proof insulated bottle for backpack", keyword: "leak proof insulated bottle", share: 0.3 },
  { term: "eco friendly water bottle", keyword: "eco friendly water bottle", share: 0.52, added: true },
  { term: "eco friendly water bottle gift", keyword: "eco friendly water bottle", share: 0.48 },
  { term: "plastic free water bottle", keyword: "plastic free water bottle", share: 0.74, added: true },
  { term: "plastic free insulated water bottle", keyword: "plastic free water bottle", share: 0.26 },
  { term: "sustainable gift bottle", keyword: "sustainable gift bottle", share: 1, added: true },
  { term: "eco friendly water bottle wholesale", keyword: "eco friendly water bottle", share: 0, excluded: true },
  { term: "plastic free water bottle kids", keyword: "plastic free water bottle", share: 0, excluded: true },
]

export const RELATED_SEARCHES = [
  "bamboo water bottle insulated",
  "best eco friendly water bottle",
  "bamboo lid water bottle mold",
  "insulated water bottle 750ml",
  "plastic free water bottle uk",
  "bamboo tumbler with lid",
  "stainless steel bottle bamboo lid",
  "sustainable water bottle brands",
]

export const SUGGESTED_QUERIES = [
  "bamboo water bottle",
  "insulated bamboo water bottle",
  "eco friendly water bottle",
  "plastic free water bottle",
]

export type Label = "Best" | "Good" | "Low" | "Learning"

/** Everything the mock shows. DEMO is the hardcoded store above; a finished Uplift run supplies the same shape. */
export type Dataset = {
  id: string
  source: "demo" | "run"
  run?: { task: string; title: string; coworker?: string | null; phase?: string | null; updated?: number }
  ACCOUNT: { name: string; customerId: string; currency: string }
  STORE: { name: string; domain: string; url: string }
  PRODUCT: {
    id: string; title: string; shortTitle: string; price: number; rating: number | null; reviews: number; color: string
    bullets: string[]; image?: string | null
  }
  ECONOMICS: typeof ECONOMICS
  CAMPAIGNS: typeof CAMPAIGNS
  KEYWORDS: Keyword[]
  AD_GROUPS: readonly string[]
  NEGATIVES: string[]
  HEADLINES: { text: string; label: Label }[]
  DESCRIPTIONS: { text: string; label: Label }[]
  DISPLAY_PATH: string[]
  SITELINKS: { title: string; line: string }[]
  CALLOUTS: string[]
  COMPETITOR_ADS: TextAd[]
  OFFERS: Offer[]
  ORGANIC: Organic[]
  PEOPLE_ALSO_ASK: { q: string; a: string }[]
  SEARCH_TERMS: typeof SEARCH_TERMS
  RELATED_SEARCHES: string[]
  SUGGESTED_QUERIES: string[]
  SHOPPING_TERMS: string[]
  editorCsvUrl?: string | null
}

export const DEMO: Dataset = {
  id: "demo",
  source: "demo",
  ACCOUNT, STORE, PRODUCT: { ...PRODUCT, image: null }, ECONOMICS, CAMPAIGNS, KEYWORDS, AD_GROUPS, NEGATIVES, HEADLINES,
  DESCRIPTIONS, DISPLAY_PATH, SITELINKS, CALLOUTS, COMPETITOR_ADS, OFFERS, ORGANIC, PEOPLE_ALSO_ASK, SEARCH_TERMS,
  RELATED_SEARCHES, SUGGESTED_QUERIES,
  SHOPPING_TERMS: ["bottle", "flask", "tumbler"],
}
