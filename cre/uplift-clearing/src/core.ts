// TypeScript port of packages/core (rules.py, changeset.py, score.py). Keep in lockstep with the Python.
import rulesFile from "../../../rules/uplift-rules.json"
import type { Json } from "./lib"

// --- rules ----------------------------------------------------------------------------------------

export type Hit = { rule_id: string; severity: string; location: string }
type Segment = { location: string; text: string; kind?: string }

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

export function scan(segments: Segment[], brandTerms: string[] = [], substantiated: string[] = []): Hit[] {
  const hits: Hit[] = []
  for (const seg of segments) {
    const text = seg.text || ""
    const kind = seg.kind ?? "copy"
    for (const rule of rulesFile.rules as Json[]) {
      if (rule.applies_to && rule.applies_to !== kind) continue
      if (rule.substantiable && substantiated.includes(rule.id)) continue
      const re = new RegExp(rule.pattern, rule.case_sensitive ? "g" : "gi")
      for (const _ of text.matchAll(re)) hits.push({ rule_id: rule.id, severity: rule.severity, location: seg.location })
    }
    for (const term of brandTerms) {
      if (term && new RegExp(`\\b${escapeRe(term)}\\b`, "i").test(text))
        hits.push({ rule_id: "TM-001", severity: "high", location: seg.location })
    }
  }
  return hits
}

// --- changeset ownership --------------------------------------------------------------------------

const PRODUCT_FIELD_OWNERS: Record<string, string> = {
  title: "clara", descriptionHtml: "clara", handle: "clara", seo: "clara",
  productType: "oskar", vendor: "oskar", category: "oskar",
}
const OP_OWNERS: Record<string, string> = {
  "product.tags_add": "clara", "product.taxonomy_tags_add": "oskar", "metafields.set": "*",
  "collection.add_products": "oskar", "collection.create": "oskar",
  "media.add": "iris", "media.reorder": "iris", "media.update_alt": "iris",
  "translations.register": "yuki", "discount.create": "marcus", "article.create": "leo",
}
const METAFIELD_OWNERS: Record<string, string> = {
  "custom.faq": "leo", "custom.comparison": "leo",
  "shopify--discovery--product_recommendation.related_products": "oskar",
  "shopify--discovery--product_recommendation.complementary_products": "oskar",
}

export function ownersOf(op: Json): Set<string> {
  if (op.op === "product.update") return new Set(Object.keys(op.fields ?? {}).map((f) => PRODUCT_FIELD_OWNERS[f] ?? "?"))
  if (op.op === "metafields.set") {
    return new Set((op.metafields ?? []).map((m: Json) =>
      METAFIELD_OWNERS[`${m.namespace}.${m.key}`] ?? (m.namespace === "shopify" ? "oskar" : "?")))
  }
  return new Set([OP_OWNERS[op.op] ?? "?"])
}

/** True when every op in the changeset is owned by `role`. */
export const ownsAll = (changeset: Json[], role: string) =>
  changeset.every((op) => [...ownersOf(op)].every((o) => o === role))

// --- listing score (deterministic 95) -------------------------------------------------------------

const words = (html: string) => (html || "").replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean)
const has = (text: string, phrase: string) => (text || "").toLowerCase().includes(phrase.toLowerCase())

function metafield(product: Json, namespace: string, key: string): any {
  const mf = (product.metafields?.nodes ?? []).find((m: Json) => m.namespace === namespace && m.key === key)
  if (!mf) return null
  try { return JSON.parse(mf.value) } catch { return mf.value }
}

const round2 = (x: number) => Math.round(x * 100) / 100

export function score(product: Json, keywords?: { primary?: string; secondary?: string[] } | null) {
  const primary = (keywords?.primary ?? "").toLowerCase()
  const secondary = (keywords?.secondary ?? []).map((s) => s.toLowerCase())
  const title = product.title ?? ""
  const body = product.descriptionHtml ?? ""
  const bodyText = words(body).join(" ")
  const seoTitle = product.seo?.title ?? ""
  const seoDesc = product.seo?.description ?? ""
  const media = (product.media?.nodes ?? []).filter((m: Json) => m.mediaContentType === "IMAGE")
  const faq = metafield(product, "custom", "faq") ?? []
  const comparison = metafield(product, "custom", "comparison")
  const sections: Record<string, number> = {}

  let d = 0
  d += seoTitle.length >= 30 && seoTitle.length <= 60 ? 4 : 0
  d += seoDesc.length >= 70 && seoDesc.length <= 160 ? 4 : 0
  const handle = product.handle ?? ""
  d += /^[a-z0-9]+(-[a-z0-9]+)*$/.test(handle) && handle.length <= 60 ? 2 : 0
  if (primary) {
    d += has(title, primary) ? 4 : 0
    d += has(seoTitle, primary) || has(seoDesc.slice(0, 160), primary) ? 3 : 0
    d += secondary.filter((s) => has(bodyText, s)).length >= Math.min(3, secondary.length || 3) ? 3 : 0
  } else {
    d += title.length >= 20 && title.length <= 70 ? 4 : 0
    d += seoTitle && seoDesc ? 3 : 0
    d += bodyText.split(" ").filter(Boolean).length >= 150 ? 3 : 0
  }
  d += (product.tags ?? []).length >= 3 ? 2 : 0
  sections.discoverability = d

  const n = bodyText.split(" ").filter(Boolean).length
  let p = n >= 150 ? 5 : (5 * n) / 150
  p += n >= 300 ? 2 : 0
  p += (body.toLowerCase().match(/<li/g) ?? []).length >= 3 ? 3 : 0
  p += /<h[23]/i.test(body) ? 2 : 0
  p += title.length >= 20 && title.length <= 70 ? 3 : 0
  sections.persuasion = round2(p)

  let v = Math.min(media.length, 5)
  v += media.length ? (5 * media.filter((m: Json) => (m.alt ?? "").trim()).length) / media.length : 0
  const widths = media.map((m: Json) => m.image?.width ?? 0)
  v += widths.length && widths[0] >= 1000 ? 3 : 0
  v += widths.some((w: number) => w >= 1500) ? 2 : 0
  sections.visuals = round2(v)

  const faqText = JSON.stringify(faq).toLowerCase()
  let t = Array.isArray(faq) && faq.length >= 3 ? 5 : 0
  t += comparison ? 4 : 0
  t += ["shipping", "returns", "return policy", "delivery"].some((w) => has(bodyText + faqText, w)) ? 4 : 0
  const ratingCount = metafield(product, "reviews", "rating_count")
  t += ratingCount && Number(ratingCount) > 0 ? 3 : 0
  t += ["warranty", "guarantee"].some((w) => has(bodyText + faqText, w)) ? 2 : 0
  sections.trust = t

  let c = product.category ? 5 : 0
  c += product.productType ? 2 : 0
  c += product.vendor ? 1 : 0
  c += Math.min(3, (product.metafields?.nodes ?? []).filter((m: Json) => m.namespace === "shopify").length)
  const variants = product.variants?.nodes ?? []
  c += variants.length && variants.every((x: Json) => x.barcode) ? 2 : 0
  c += (product.collections?.nodes ?? []).length ? 2 : 0
  sections.catalog = c

  const hits = scan([{ location: "title", text: title }, { location: "description", text: bodyText },
    { location: "seo", text: `${seoTitle} ${seoDesc}` }])
  const high = hits.filter((h) => h.severity === "high").length
  const medium = hits.filter((h) => h.severity === "medium").length
  sections.compliance = Math.max(0, 10 - 3 * high - medium)

  const deterministic = round2(Object.values(sections).reduce((a, b) => a + b, 0))
  return { sections, deterministic }
}
