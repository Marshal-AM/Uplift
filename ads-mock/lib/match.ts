import type { Dataset, Keyword } from "./data"

export type Diagnosis =
  | { showing: true; keyword: Keyword }
  | { showing: false; reason: "negative"; negative: string }
  | { showing: false; reason: "no-keyword" }

const words = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").split(/\s+/).filter(Boolean)

// Plural/singular folding, as close variants do for Google's exact and phrase match.
const stem = (w: string) => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w)

const contains = (query: string[], phrase: string[]) =>
  phrase.length > 0 && query.some((_, i) => phrase.every((p, j) => query[i + j] === p))

/** Which keyword (if any) would trigger the ad for this query, following exact/phrase match and phrase negatives. */
export function diagnose(ds: Dataset, query: string): Diagnosis {
  const q = words(query).map(stem)
  for (const n of ds.NEGATIVES) {
    if (contains(q, words(n).map(stem))) return { showing: false, reason: "negative", negative: n }
  }
  const exact = ds.KEYWORDS.find((k) => k.match === "Exact match" && words(k.text).map(stem).join(" ") === q.join(" "))
  if (exact) return { showing: true, keyword: exact }
  const phrase = ds.KEYWORDS.filter((k) => k.match === "Phrase match" && contains(q, words(k.text).map(stem)))
    .sort((a, b) => b.text.length - a.text.length)[0]
  if (phrase) return { showing: true, keyword: phrase }
  return { showing: false, reason: "no-keyword" }
}

/** Product searches also trigger the Shopping (Performance Max) listing, even without a matching keyword. */
export function shoppingEligible(ds: Dataset, query: string): boolean {
  const q = words(query).map(stem)
  if (ds.NEGATIVES.some((n) => contains(q, words(n).map(stem)))) return false
  return ds.SHOPPING_TERMS.map(stem).some((w) => q.includes(w))
}
