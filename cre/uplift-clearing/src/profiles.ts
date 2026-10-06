// Verifier profiles (`<role>@5`). `local` runs on every node over the hash-checked manifest and bundle and must
// be deterministic; `remote` runs in DON mode for re-checks that need a secret (DataForSEO) or the live web.
import type { NodeRuntime, Runtime } from "@chainlink/cre-sdk"
import { ownsAll, scan, score } from "./core"
import { type Config, dataforseo, type Json, medianOnNodes, nodeFetch } from "./lib"

export type Check = { name: string; points: number; max: number; gate?: boolean }
export type Local = { checks: Check[]; probes: Json; judge: { question: string; material: string } }
type Profile = {
  pass: number
  local: (m: Json, b: Json, now: number) => Local
  remote?: (runtime: Runtime<Config>, probes: Json) => Check[]
}

const check = (name: string, ok: boolean | number, max: number, gate = false): Check => {
  const share = typeof ok === "number" ? Math.max(0, Math.min(1, ok)) : ok ? 1 : 0
  return { name, points: Math.round(share * max * 10) / 10, max, ...(gate && share < 1 ? { gate: true } : {}) }
}
const ratio = (hit: number, total: number) => (total ? hit / total : 1)
/** Full points at `target` share and above, proportional below. */
const atLeast = (share: number, target: number) => Math.min(1, share / target)
const within = (a: number, b: number, tol: number) => b === 0 ? a === 0 : Math.abs(a - b) / b <= tol
const plain = (html: string) => (html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
const isHttps = (u: string) => /^https:\/\//.test(u || "")
const norm = (s: string) => (s || "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim()
const sigWords = (s: string) => norm(s).split(" ").filter((w) => w.length > 3)
const overlaps = (a: string, b: string) => {
  const bw = new Set(sigWords(b))
  return sigWords(a).filter((w) => bw.has(w)).length >= 2
}
const pick = <T>(xs: T[], n: number): T[] => {
  if (xs.length <= n) return xs
  const step = xs.length / n
  return Array.from({ length: n }, (_, i) => xs[Math.floor(i * step)])
}
const htmlBalanced = (html: string) => {
  const stack: string[] = []
  for (const m of (html || "").matchAll(/<\/?([a-z0-9]+)[^>]*?(\/?)>/gi)) {
    const tag = m[1].toLowerCase()
    if (m[2] === "/" || ["br", "img", "hr", "meta", "input", "source"].includes(tag)) continue
    if (m[0].startsWith("</")) { if (stack.pop() !== tag) return false } else stack.push(tag)
  }
  return stack.length === 0
}
const syllables = (w: string) => Math.max(1, (w.toLowerCase().replace(/e$/, "").match(/[aeiouy]+/g) ?? []).length)
const flesch = (text: string) => {
  const sentences = Math.max(1, (text.match(/[.!?]+/g) ?? []).length)
  const ws = text.split(/\s+/).filter(Boolean)
  if (!ws.length) return 0
  const syl = ws.reduce((a, w) => a + syllables(w), 0)
  return 206.835 - 1.015 * (ws.length / sentences) - 84.6 * (syl / ws.length)
}

/** Re-fetch public pages on every node; median of the share that still contain the expected text. */
function pagesContain(runtime: Runtime<Config>, items: { url: string; needles: string[] }[]): number {
  if (!items.length) return 1
  return medianOnNodes(runtime, (n: NodeRuntime<Config>) => {
    let reachable = 0
    let found = 0
    for (const it of items) {
      try {
        const r = nodeFetch(n, it.url)
        if (r.status !== 200) continue
        reachable++
        const page = norm(r.body)
        if (it.needles.some((x) => x && page.includes(norm(x)))) found++
      } catch { /* unreachable pages are not evidence either way */ }
    }
    return reachable < 2 ? 0.5 : found / reachable
  })
}

// --- profiles -------------------------------------------------------------------------------------

const kai: Profile = {
  pass: 60,
  local: (m, b) => {
    const kws: Json[] = b.keywords ?? []
    const live = kws.filter((k) => k.role !== "negative")
    const brandHits = live.filter((k) => (b.brand_terms ?? []).some((t: string) => t && norm(k.keyword).includes(norm(t))))
    const totals = Array(12).fill(0)
    for (const k of live.filter((k) => k.monthly?.length).slice(0, 50)) {
      const s = k.monthly.slice(-12)
      s.forEach((v: number, i: number) => { totals[i] += v || 0 })
    }
    const months: number[] = b.months ?? []
    const peaks = totals.map((v, i) => [months[i], v]).sort((x, y) => y[1] - x[1]).slice(0, 3).map((x) => x[0])
    const agree = (b.peak_months ?? []).filter((p: number) => peaks.includes(p)).length
    const roles = ["title", "description", "seo_meta", "blog", "ads_exact", "ads_phrase", "negative"]
    const seen = new Map<string, number>()
    kws.forEach((k) => seen.set(norm(k.keyword), (seen.get(norm(k.keyword)) ?? 0) + 1))
    const clean = kws.filter((k) => k.cluster != null && roles.includes(k.role) && seen.get(norm(k.keyword)) === 1)
    const sample = pick([...live].sort((x, y) => (y.volume ?? 0) - (x.volume ?? 0)), 10)
    return {
      checks: [
        check("No foreign trademarks", brandHits.length === 0, 20, true),
        check("Seasonality recomputed", agree >= 2 || !b.peak_months?.length, 20),
        check("Cluster integrity", atLeast(ratio(clean.length, kws.length), 0.95), 15),
      ],
      probes: { loc: b.location_code, lang: b.language_code,
        sample: sample.map((k) => ({ keyword: k.keyword, volume: k.volume, intent: k.intent })) },
      judge: { question: "Do these keyword clusters fit the product a shopper would search for? 5 = all relevant.",
        material: `${m.summary_md}\n${JSON.stringify(sample.map((k) => [k.keyword, k.cluster, k.role]))}` },
    }
  },
  remote: (runtime, p) => {
    const kws = p.sample.map((k: Json) => k.keyword)
    if (!kws.length) return [check("Volumes are real", false, 30), check("Intent labels", false, 10)]
    const vol = dataforseo(runtime, "keywords_data/google_ads/search_volume/live",
      [{ keywords: kws, location_code: p.loc, language_code: p.lang }])
    const live = new Map(vol.map((r: Json) => [norm(r.keyword), r.search_volume ?? 0]))
    const volOk = p.sample.filter((k: Json) => live.has(norm(k.keyword))
      && within(k.volume ?? 0, live.get(norm(k.keyword)) as number, 0.3)).length
    const intent = dataforseo(runtime, "dataforseo_labs/google/search_intent/live",
      [{ keywords: kws, language_code: p.lang }])[0]?.items ?? []
    const labels = new Map(intent.map((r: Json) => [norm(r.keyword), r.keyword_intent?.label]))
    const intentOk = p.sample.filter((k: Json) => labels.get(norm(k.keyword)) === k.intent).length
    return [check("Volumes are real", atLeast(ratio(volOk, kws.length), 0.7), 30),
      check("Intent labels", atLeast(ratio(intentOk, kws.length), 0.6), 10)]
  },
}

const rafael: Profile = {
  pass: 60,
  local: (m, b) => {
    const prices: number[] = [...(b.prices ?? [])].sort((x, y) => x - y)
    const median = prices.length ? (prices.length % 2 ? prices[(prices.length - 1) / 2]
      : (prices[prices.length / 2 - 1] + prices[prices.length / 2]) / 2) : null
    const bands = b.bands ?? {}
    const bandsOk = !prices.length || (within(bands.min, prices[0], 0.01) && within(bands.max, prices.at(-1)!, 0.01)
      && (median == null || within(bands.median, median, 0.02)))
    const evidence: Json[] = b.evidence ?? []
    const covered = (b.coverage ?? []).filter((c: Json) => c.filled >= 5).length
    return {
      checks: [
        check("Band maths", bandsOk, 20),
        check("Coverage", atLeast(covered / 4, 1), 15),
        check("Evidence URLs", atLeast(ratio(evidence.filter((e) => isHttps(e.url)).length, evidence.length), 0.9), 5),
      ],
      probes: { loc: b.location_code, lang: b.language_code, query: b.queries?.[0], top: b.top_domains ?? [],
        pages: pick(evidence.filter((e) => isHttps(e.url)), 3)
          .map((e) => ({ url: e.url, needles: [e.title?.slice(0, 60), e.price != null ? String(e.price) : ""] })) },
      judge: { question: "Is the positioning consistent with the competitor matrix and price bands? 5 = fully.",
        material: m.summary_md },
    }
  },
  remote: (runtime, p) => {
    const cited = pagesContain(runtime, p.pages)
    let ranking = 1
    if (p.query && p.top.length) {
      const items = dataforseo(runtime, "serp/google/organic/live/advanced",
        [{ keyword: p.query, location_code: p.loc, language_code: p.lang, depth: 10 }])[0]?.items ?? []
      const top10 = items.filter((i: Json) => i.type === "organic").map((i: Json) => i.domain)
      ranking = atLeast(p.top.filter((d: string) => top10.includes(d)).length / Math.min(5, p.top.length), 0.6)
    }
    return [check("Cited pages support the facts", atLeast(cited, 0.67), 35), check("Ranking sanity", ranking, 20)]
  },
}

const priya: Profile = {
  pass: 60,
  local: (m, b) => {
    const own = norm(b.own_domain ?? "")
    const sources: string[] = b.sources ?? []
    const ownHit = own && sources.some((s) => norm(s).includes(own))
    const coded: Json[] = b.coded ?? []
    const ids = new Set(coded.map((c) => c.id))
    const counts = new Map<string, number>()
    const bump = (k: string, by: number) => counts.set(k, (counts.get(k) ?? 0) + by)
    for (const c of coded) {
      for (const a of c.aspects ?? []) {
        const name = String(a.aspect ?? "").toLowerCase().trim()
        if (a.polarity > 0) bump(`love:${name}`, c.weight ?? 1)
        else if (a.polarity < 0) {
          bump(`complaint:${name}`, c.weight ?? 1)
          if (c.is_dealbreaker) bump(`dealbreaker:${name}`, 1)
        }
        if (c.is_wish) bump(`wish:${name}`, 1)
      }
    }
    const findings: Json[] = b.findings ?? []
    const recount = findings.filter((f) => Math.abs((counts.get(f.id) ?? 0) - f.weighted_count) <= 0.5).length
    const personaRefs: string[] = (b.personas ?? []).flatMap((p: Json) => (p.attributes ?? []).flatMap((a: Json) => a.review_ids ?? []))
    const findingIds = new Set(findings.map((f) => f.id))
    const winRefs = (b.win_plan ?? []).filter((w: Json) => findingIds.has(w.finding_id)).length
    const quotes: Json[] = b.quotes ?? []
    return {
      checks: [
        check("Competitor-only", !ownHit, 15, true),
        check("Counts recomputed", atLeast(ratio(recount, findings.length), 0.9), 25),
        check("Persona evidence", atLeast(ratio(personaRefs.filter((i) => ids.has(i)).length, personaRefs.length), 0.9), 10),
        check("Coverage", atLeast((b.review_count ?? 0) / 100, 1) * (new Set(quotes.map((q) => q.source)).size >= 2 ? 1 : 0.5), 10),
        check("Win-plan grounding", atLeast(ratio(winRefs, (b.win_plan ?? []).length), 0.8), 5),
      ],
      probes: { pages: pick(quotes.filter((q) => isHttps(q.source_url)), 5)
        .map((q) => ({ url: q.source_url, needles: [q.text.slice(0, 80)] })) },
      judge: { question: "Are these competitor review findings coded correctly from the quotes? 5 = all correct.",
        material: `${m.summary_md}\n${JSON.stringify(quotes.slice(0, 10))}` },
    }
  },
  remote: (runtime, p) => [check("Quotes are verbatim", atLeast(pagesContain(runtime, p.pages), 0.6), 30)],
}

const marcus: Profile = {
  pass: 65,
  local: (m, b, now) => {
    const margin = (price: number, d: number) => (price - d > 0 ? (price - d - b.unit_cost - b.shipping) / (price - d) : -1)
    const codes: Json[] = b.codes ?? []
    const safe = codes.every((c) => margin(b.price, (b.price * c.percentage) / 100) >= b.floor)
    const dates = codes.every((c) => Date.parse(c.starts) > now - 864e5 && Date.parse(c.ends) > Date.parse(c.starts))
    const unique = new Set(codes.map((c) => c.code.toUpperCase())).size === codes.length
      && codes.every((c) => /^[A-Z0-9_-]{4,32}$/i.test(c.code))
    const scen = (b.scenarios ?? []).every((s: Json) =>
      Math.abs(margin(b.price, (b.price * s.discount_pct) / 100) - s.margin) < 0.002)
    const bands = b.bands ?? {}
    const bandRef = !bands.median || /premium|value|parity|match|below|above|mid/i.test(b.positioning ?? "")
    return {
      checks: [check("Margin safety", safe, 35, true), check("Dates", dates, 20), check("Code hygiene", unique, 15),
        check("Scenario maths", scen, 15), check("Band references", bandRef, 10)],
      probes: {},
      judge: { question: "Is this pricing rationale sound for the margin and market bands? 5 = sound.",
        material: `${m.summary_md}\nbands ${JSON.stringify(bands)} floor ${b.floor}` },
    }
  },
}

const clara: Profile = {
  pass: 65,
  local: (m, b) => {
    const blocks: Json[] = b.blocks ?? []
    const body = blocks.map((x) => x.text).join(" ")
    const forbidden: string[] = b.forbidden ?? []
    const fmt = [
      (b.title ?? "").length <= 77, (b.seo?.title ?? "").length <= 66, (b.seo?.description ?? "").length <= 176,
      /^[a-z0-9]+(-[a-z0-9]+)*$/.test(b.handle ?? "") && b.handle.length <= 66,
      !blocks.some((x) => /<script|on\w+=/i.test(x.text)),
      !forbidden.some((w) => w && norm(`${b.title} ${body}`).includes(norm(w))),
    ]
    const primary = norm(b.primary ?? "")
    const primaryWords = primary.split(" ").filter(Boolean)
    const near = (t: string) => !primary || norm(t).includes(primary)
      || primaryWords.filter((w) => norm(t).includes(w)).length >= Math.ceil(primaryWords.length * 0.75)
    const facts = new Set(Object.keys(b.facts ?? {}).length ? Object.keys(b.facts) : (b.facts ?? []).map((f: Json) => f.id))
    const claims = blocks.filter((x) => x.type === "p" || x.type === "li")
    const grounded = claims.filter((x) => x.fact_ids?.length && x.fact_ids.every((f: string) => facts.has(f))).length
    const secondary: string[] = b.secondary ?? []
    const objections: string[] = (b.objections ?? []).map((o: Json) => (typeof o === "string" ? o : o.aspect ?? o.text ?? ""))
    const answered = objections.filter((o) => overlaps(o, body) || norm(body).includes(norm(o))).length
    const fl = flesch(plain(body))
    return {
      checks: [
        check("Format", fmt.filter(Boolean).length / fmt.length, 25),
        check("Keyword placement", (near(b.title) || near(b.seo?.title ?? "")) && near(body), 15),
        check("Fact grounding", atLeast(ratio(grounded, claims.length), 0.85), 25),
        check("Keyword coverage", atLeast(ratio(secondary.filter((s) => norm(body).includes(norm(s))).length,
          secondary.length), 0.5), 10),
        check("Objection coverage", objections.length ? atLeast(answered / 2, 1) : 1, 10),
        check("Readability and grammar", (fl >= 30 && fl <= 80 ? 0.5 : 0.25) + ((b.grammar_issue_count ?? 0) <= 5 ? 0.5 : 0.25), 10),
        check("Ownership", ownsAll(m.changeset, "clara"), 0, true),
      ],
      probes: {},
      judge: { question: "How persuasive, clear and on-voice is this product copy for shoppers? 5 = excellent.",
        material: `Title: ${b.title}\n${body}` },
    }
  },
}

const iris: Profile = {
  pass: 60,
  local: (m, b) => {
    const scenes: Json[] = b.scenes ?? []
    const exports: Json[] = b.exports ?? []
    const minSize = (e: Json) => Math.min(e.width, e.height) >= (e.channel === "amazon" ? 1000 : 800)
    const rules = exports.map((e) => minSize(e) && (e.kind !== "white" || (e.border_mean >= 240
      && (e.channel !== "amazon" || e.fill_ratio >= 0.5))))
    const alts: Json[] = b.alts ?? []
    const name = sigWords(b.product_name ?? "")
    const altOk = alts.filter((a) => {
      const t = typeof a === "string" ? a : a.alt ?? ""
      return t.trim() && t.length <= 140 && (!name.length || name.some((w) => norm(t).includes(w)))
    }).length
    const missing: string[] = b.missing_before ?? []
    return {
      checks: [
        check("Product fidelity", scenes.every((s) => s.ssim >= 0.9), 25, true),
        check("Channel rules", ratio(rules.filter(Boolean).length, rules.length) * (b.overlay_flags?.google_shopping ? 0 : 1), 25),
        check("Alt text", atLeast(ratio(altOk, alts.length), 0.9), 15),
        check("Hero", (b.hero_width ?? 0) >= 1000, 15),
        check("Gap closure", missing.length ? atLeast((b.added_types ?? []).length / missing.length, 0.5) : 1, 10),
        check("Ownership", ownsAll(m.changeset, "iris"), 5),
      ],
      probes: {},
      judge: { question: "Do these image deliverables look realistic and fit the brand? 5 = yes.", material: m.summary_md },
    }
  },
}

const oskar: Profile = {
  pass: 65,
  local: (m, b) => {
    const tags: string[] = [...(b.existing_tags ?? []), ...(b.tags ?? [])]
    const dupes = tags.length - new Set(tags.map(norm)).size
    const nc = b.new_collection
    const feed = b.feed ?? {}
    const required = ["id", "title", "google_product_category", "brand", "condition"]
    return {
      checks: [
        check("Category validity", !b.category_id || (b.category_candidates ?? []).includes(b.category_id), 30),
        check("Collections", !nc || ((nc.title ?? "").length <= 255 && (nc.seo?.title ?? nc.title ?? "").length <= 70
          && (nc.seo?.description ?? "").length <= 320), 20),
        check("Related links", [...(b.related ?? []), ...(b.complementary ?? [])].every((id: string) => /^gid:\/\/shopify\/Product\/\d+$/.test(id)), 15),
        check("Tag hygiene", dupes === 0 && tags.length <= 25, 15),
        check("Export schema", ratio(required.filter((f) => feed[f]).length, required.length), 15),
        check("Ownership", ownsAll(m.changeset, "oskar"), 0, true),
      ],
      probes: {},
      judge: { question: "Do the chosen category and collections fit this product? 5 = clearly right.", material: m.summary_md },
    }
  },
}

const yuki: Profile = {
  pass: 65,
  local: (m, b) => {
    const tr: Json = b.translated ?? {}
    const src: Json = b.source ?? {}
    const keys = Object.keys(tr)
    const cjk = /^(ja|zh|ko)/i.test(b.locale ?? "")
    const len = (s: string) => (cjk ? [...(s ?? "")].length * 2 : (s ?? "").length)
    const locked: string[] = b.locked_terms ?? []
    const all = keys.map((k) => tr[k]).join(" ")
    const srcAll = keys.map((k) => src[k]?.value ?? "").join(" ")
    const lockedExpected = locked.filter((t) => srcAll.includes(t))
    const local = norm(b.primary_local ?? "")
    const lengths = [len(tr.title) <= 75 * (cjk ? 2 : 1), len(tr.meta_title ?? "") <= 65 * (cjk ? 2 : 1),
      len(tr.meta_description ?? "") <= 165 * (cjk ? 2 : 1)]
    const changed = keys.filter((k) => tr[k] && tr[k] !== src[k]?.value).length
    const opsFresh = (m.changeset ?? []).flatMap((o: Json) => o.translations ?? [])
      .every((t: Json) => !t.translatableContentDigest || t.translatableContentDigest === src[t.key]?.digest)
    return {
      checks: [
        check("Digest freshness", opsFresh, 20),
        check("Locked terms", lockedExpected.length ? atLeast(ratio(lockedExpected.filter((t) => all.includes(t)).length,
          lockedExpected.length), 0.9) : 1, 20),
        check("Lengths", lengths.filter(Boolean).length / lengths.length, 15),
        check("Local keyword", !local || [tr.title, tr.meta_title, plain(tr.body_html ?? "").slice(0, 400)]
          .some((t) => norm(t ?? "").includes(local)), 15),
        check("Completeness", atLeast(ratio(changed, keys.length), 0.95) * (htmlBalanced(tr.body_html ?? "") ? 1 : 0.5), 15),
      ],
      probes: { loc: b.location_code, lang: (b.locale ?? "").split("-")[0], keywords: (b.local_keywords ?? []).slice(0, 3) },
      judge: { question: `Does the ${b.locale} text preserve the meaning of the source? 5 = fully.`,
        material: `SOURCE: ${plain(srcAll).slice(0, 4000)}\n\nTRANSLATION: ${plain(all).slice(0, 4000)}` },
    }
  },
  remote: (runtime, p) => {
    const kws = (p.keywords as Json[]).map((k) => (typeof k === "string" ? k : k.keyword)).filter(Boolean)
    if (!kws.length) return [check("Volumes", 0.5, 10)]
    const res = dataforseo(runtime, "keywords_data/google_ads/search_volume/live",
      [{ keywords: kws, location_code: p.loc, language_code: p.lang }])
    const real = res.filter((r: Json) => (r.search_volume ?? 0) > 0).length
    return [check("Volumes", atLeast(real / kws.length, 0.67), 10)]
  },
}

const leo: Profile = {
  pass: 60,
  local: (m, b) => {
    const facts = new Set(Object.keys(b.facts ?? {}).length ? Object.keys(b.facts) : (b.facts ?? []).map((f: Json) => f.id))
    const faq: Json[] = b.faq ?? []
    const questions = [...(b.paa ?? []), ...(b.question_keywords ?? [])].map((q: Json) => (typeof q === "string" ? q : q.question ?? q.keyword ?? ""))
    const covered = faq.filter((f) => questions.some((q) => overlaps(f.question, q))).length
    const comp = b.comparison
    const article = b.article
    const emails: Json[] = b.emails ?? []
    const links: string[] = article?.links ?? []
    const shop = norm(b.shop_url ?? "")
    const articleOp = (m.changeset ?? []).find((o: Json) => o.op === "article.create")
    const target = 900
    return {
      checks: [
        check("FAQ grounding", faq.length ? atLeast(ratio(faq.filter((f) => (f.fact_ids ?? []).some((i: string) => facts.has(i))).length, faq.length), 0.8) : 1, 20),
        check("Search-query coverage", faq.length ? atLeast(covered / 3, 1) : 1, 10),
        check("Comparison sourcing", !comp || (comp.evidence ?? []).some((u: string) => isHttps(u)), 15),
        check("Article", !article || ((Math.abs(article.word_count - target) / target <= 0.4)
          && links.filter((l) => !l.startsWith("http") || !shop || norm(l).includes(shop)).length === links.length
          && (!articleOp || articleOp.input.isPublished === false)), 20),
        check("Email", emails.length ? ratio(emails.filter((e) => (e.subject ?? "").length <= 70 && e.has_unsubscribe
          && e.has_text).length, emails.length) : 1, 15),
        check("UTM consistency", links.length ? atLeast(ratio(links.filter((l) => l.includes(`utm_campaign=${b.campaign}`)
          || l === "#").length, links.length), 0.9) : 1, 10),
        check("Ownership", ownsAll(m.changeset, "leo"), 5),
      ],
      probes: {},
      judge: { question: "Is the tone helpful, credible and on-brand for shoppers? 5 = yes.",
        material: `${JSON.stringify(faq.slice(0, 5))}\n${article?.first_100 ?? ""}` },
    }
  },
}

const sasha: Profile = {
  pass: 65,
  local: (m, b) => {
    const e = b.economics ?? {}
    const campaigns: Json[] = b.campaigns ?? []
    const monthly = campaigns.reduce((a, c) => a + (c.daily_budget ?? 0), 0) * 30.4
    const breakeven = e.price * e.margin
    const maxCpc = breakeven * e.conversion_rate
    const bids = campaigns.every((c) => c.max_cpc == null || c.max_cpc <= maxCpc + 0.01) && e.max_cpc <= maxCpc + 0.01
    const positives: Json[] = b.keywords ?? []
    const negs: string[] = (b.negatives ?? []).map((n: Json) => (typeof n === "string" ? n : n.keyword))
    const blocks = positives.filter((k) => negs.some((n) => {
      const nw = norm(n).split(" ")
      const kw = norm(k.keyword).split(" ")
      return nw.every((w) => kw.includes(w)) // a phrase/broad negative blocks any query containing all its words
    })).length
    const heads: string[] = b.headlines ?? []
    const descs: string[] = b.descriptions ?? []
    const shop = norm(b.shop_url ?? "")
    return {
      checks: [
        check("Spend cap", monthly <= e.monthly_budget * 1.01, 25, true),
        check("Bid safety", bids, 25, true),
        check("Negatives sanity", blocks === 0, 15),
        check("Limits", heads.every((h) => h.length <= 30) && descs.every((d) => d.length <= 90), 10),
        check("Final URLs", isHttps(b.final_url) && (!shop || norm(b.final_url).includes(shop)) && /utm_campaign=/.test(b.final_url), 10),
        check("Paused state", campaigns.every((c) => (c.status ?? "Paused").toLowerCase() === "paused"), 10),
      ],
      probes: {},
      judge: { question: "Are these ad headlines and descriptions relevant to the keywords and product? 5 = yes.",
        material: `${heads.join(" | ")}\n${descs.join(" | ")}\n${positives.slice(0, 20).map((k) => k.keyword).join(", ")}` },
    }
  },
}

const ruth: Profile = {
  pass: 65,
  local: (m, b) => {
    const mine = scan(b.segments ?? [], b.brand_terms ?? [], b.substantiated ?? [])
    const key = (h: Json) => `${h.rule_id}@${h.location}`
    const theirs = new Set((b.hits ?? []).map(key))
    const ours = new Set(mine.map(key))
    const highMissed = mine.filter((h) => h.severity === "high" && !theirs.has(key(h))).length
    const union = new Set([...theirs, ...ours])
    const inter = [...ours].filter((k) => theirs.has(k)).length
    const rewrites: Json[] = b.rewrites ?? []
    const clean = rewrites.filter((r) => scan([{ location: "rewrite", text: r.rewrite ?? r.text ?? "",
      kind: r.kind }], b.brand_terms ?? [], b.substantiated ?? []).length === 0).length
    return {
      checks: [
        check("High-severity coverage", highMissed === 0, 40),
        check("Overall agreement", union.size ? atLeast(inter / union.size, 0.8) : 1, 30),
        check("Rewrites", rewrites.length ? atLeast(clean / rewrites.length, 0.9) : 1, 25),
      ],
      probes: {},
      judge: { question: "Are these compliant rewrites accurate and still persuasive? 5 = yes.",
        material: JSON.stringify(rewrites.slice(0, 8)) },
    }
  },
}

const SPECIALISTS = ["kai", "rafael", "priya", "marcus", "clara", "iris", "oskar", "yuki", "leo", "sasha", "ruth"]

const quinn: Profile = {
  pass: 65,
  local: (m, b) => {
    const recomputed = score(b.product ?? {}, b.keywords)
    const fixes: Json[] = b.fixes ?? []
    const rank = (b.rankings ?? []).find((r: Json) => r.keyword)
    return {
      checks: [
        check("Score agreement", Math.abs(recomputed.deterministic - (b.deterministic ?? -99)) <= 3, 50),
        check("Analytics numbers", !b.sales_query || !!b.sales, 20),
        check("Fix-plan mapping", fixes.every((f) => SPECIALISTS.includes(f.specialist) && f.price > 0), 5),
      ],
      probes: { loc: b.location_code, rank, domain: norm(new URL(b.product?.onlineStoreUrl || "https://x").hostname.replace(/^www\./, "")) },
      judge: { question: "Is the diagnosis consistent with the score sections, rankings and sales numbers? 5 = yes.",
        material: `${m.summary_md}\n${JSON.stringify({ sections: b.sections, rankings: b.rankings, sales: b.sales }).slice(0, 6000)}` },
    }
  },
  remote: (runtime, p) => {
    if (!p.rank || !p.domain || p.domain === "x") return [check("Findings reproduced", 0.75, 20)]
    const items = dataforseo(runtime, "serp/google/organic/live/advanced",
      [{ keyword: p.rank.keyword, location_code: p.loc, language_code: "en", depth: 50 }])[0]?.items ?? []
    const hit = items.find((i: Json) => i.type === "organic" && norm(i.domain).includes(p.domain))
    const pos = hit ? hit.rank_absolute : null
    const claimed = p.rank.organic_position
    return [check("Findings reproduced", (pos == null && claimed == null) || (pos != null && claimed != null
      && Math.abs(pos - claimed) <= 5), 20)]
  },
}

export const PROFILES: Record<string, Profile> = { kai, rafael, priya, marcus, clara, iris, oskar, yuki, leo, sasha, ruth, quinn }
