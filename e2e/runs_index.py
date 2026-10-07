"""Write runs/README.md: one row per recorded Task (from each run folder's README.md header)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "runs"


def field(text: str, name: str) -> str:
    m = re.search(rf"^- \*\*{re.escape(name)}:\*\* (.+)$", text, re.M)
    return m.group(1).strip() if m else "—"


def rows(folder: Path) -> list[str]:
    out = []
    for run in sorted(p for p in folder.iterdir() if (p / "README.md").exists()):
        text = (run / "README.md").read_text()
        title = text.splitlines()[0].lstrip("# ")
        verdicts = re.findall(r"\*\*(PASS|FAIL)\*\*[^\n]*?([\d.]+)/100", text.split("## Timeline")[0])
        verdict = ", ".join(f"{v} {s}" for v, s in verdicts) or "—"
        out.append(f"| [{run.name}]({run.relative_to(ROOT)}/README.md) | {title} | {field(text, 'Final status')} | "
                   f"{field(text, 'Credits charged')} | {field(text, 'Payment claim')} | "
                   f"{field(text, 'Elapsed (created → last event)')} | {verdict} |")
    return out


HEAD = "| Run | Task | Status | Credits | Payment | Elapsed | Chainlink |\n|---|---|---|---|---|---|---|"
nora = [p for p in sorted(ROOT.iterdir()) if p.is_dir() and p.name.startswith(("00-", "14-"))]
body = ["# Uplift — final end-to-end test (2026-10-07)", "",
        "Every Task below was created from the merchant's Sokosumi account (preprod, personal workspace), paid in "
        "Sokosumi credits through Masumi escrow on Cardano preprod, run by the Uplift coworker, checked by the "
        "Chainlink CRE workflow `uplift-clearing`, and — where it changes the store — approved in Sokosumi and "
        "published by Chainlink. Each folder holds the exact brief, every Task event with timestamps, the payment "
        "receipt, the cost, the Chainlink verdicts and the full deliverables (manifest, artifacts, verification "
        "bundle). Problems found during the test and how they were fixed: [ISSUES.md](ISSUES.md).", "",
        "## Nora (lead) — orchestrated runs on the glass bottle (`glass-cork-bottle`)", "",
        "Nora plans with a price ceiling, runs the specialists directly (each specialist's agent, verified by "
        "Chainlink), then charges once for the specialists whose work passed.", "", HEAD]
body += [r for f in nora for r in rows(ROOT) if f"[{f.name}]" in r]
body += ["", "## The 12 specialists — individual Tasks on the travel tumbler (`travel-tumbler`)", "",
         "A new merchant listing (title \"Travel Tumbler TT-400\", one photo, one-line description). Each specialist "
         "got one relevant Task, as a merchant would assign it. Declined attempts are kept as evidence; their "
         "re-runs follow them. A declined Task was charged when it started, but no result was submitted for it, so its "
         "escrow returns to the buyer after the deadline (Masumi refund path). Store-search ranks before and after: "
         "[tumbler/RANKS.md](tumbler/RANKS.md).", "",
         HEAD, *rows(ROOT / "tumbler")]
(ROOT / "README.md").write_text("\n".join(body) + "\n")
print((ROOT / "README.md").read_text())
