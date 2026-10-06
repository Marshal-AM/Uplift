// Prints the CRE-side hashes, rule hits and scores for e2e/cre_parity.py to compare with the Python core.
import { scan, score } from "./src/core"
import { canonical, sha256Hex } from "./src/lib"

const cases = JSON.parse(await Bun.stdin.text())
console.log(JSON.stringify(cases.map((c: any) => ({
  canonical_hash: sha256Hex(canonical(c.changeset)),
  score: score(c.product, c.keywords),
  hits: scan(c.segments, c.brand_terms).map((h) => `${h.rule_id}@${h.location}`),
}))))
