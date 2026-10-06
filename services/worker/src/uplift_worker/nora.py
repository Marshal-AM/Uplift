"""Nora — Uplift Lead. Plans, quotes, hires specialists as escrowed Jobs, gates them through CRE, merges,
asks for one approval and publishes.

Phases: start → intake → [auth_wait | input_wait] → plan → quote_wait → pay → funds_wait → execute →
merge → approval_wait → publish → report → deliver → done | failed
"""

import contextlib
import io
import json
import time
import zipfile
from copy import deepcopy
from typing import Any

from uplift_core import llm
from uplift_core.hashing import change_hash, result_hash, sha256_hex
from uplift_core.score import score

from . import cre, db, payments, runs
from .clients import Sokosumi
from .config import settings
from .runs import manifest_from_store

CAPABILITIES = {
    "keywords": "kai", "competitors": "rafael", "reviews": "priya", "pricing": "marcus", "copy": "clara",
    "visuals": "iris", "catalog": "oskar", "localization": "yuki", "content": "leo", "email": "leo", "ads": "sasha",
    "compliance": "ruth", "audit": "quinn", "analytics": "quinn",
}
ORDER = ["quinn", "kai", "rafael", "priya", "marcus", "clara", "iris", "oskar", "leo", "sasha", "yuki"]
DEPENDS = {"priya": ["rafael"], "marcus": ["rafael"], "clara": ["kai", "priya"], "iris": ["priya"],
           "oskar": ["kai"], "leo": ["clara", "priya", "rafael", "kai", "marcus"], "sasha": ["marcus", "kai", "iris", "clara"],
           "yuki": ["clara", "leo", "iris"]}
FULL_FLOW = ["kai", "rafael", "priya", "marcus", "clara", "iris", "oskar", "leo", "sasha", "yuki"]


def close(roles: set[str], has_keywords: bool, competitors_known: bool) -> set[str]:
    """Dependency closure in code (spec §0.4)."""
    roles = set(roles)
    if roles & {"clara", "leo", "sasha", "yuki"} and not has_keywords:
        roles.add("kai")
    if roles & {"clara", "leo", "iris", "sasha"}:
        roles.add("priya")
    if "priya" in roles and not competitors_known:
        roles.add("rafael")
    if "marcus" in roles:
        roles.add("rafael")
    if "sasha" in roles:
        roles |= {"marcus", "iris"}
    return roles


def plan(task: dict, answers: list[str]) -> dict[str, Any]:
    brief = f"{task.get('name')}\n{task.get('description')}\nFollow-ups: {answers}"
    intent = llm.structured(
        f"A merchant asked their e-commerce growth team:\n{brief}\n"
        f"Which capabilities are needed? Options: {sorted(set(CAPABILITIES))}. full_flow means launch/overhaul/"
        "new product/full optimization. Extract product hint, target market (country code), locales for "
        "translation, keywords and competitors if the merchant gave them, a credit budget if stated, and a "
        "one-paragraph goal.",
        {"type": "object", "properties": {
            "capabilities": {"type": "array", "items": {"type": "string"}}, "full_flow": {"type": "boolean"},
            "product_hint": {"type": "string"}, "market_country": {"type": "string"},
            "locales": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "competitors": {"type": "array", "items": {"type": "string"}},
            "budget_credits": {"type": "number"}, "goal": {"type": "string"},
            "fit": {"type": "object", "additionalProperties": {"type": "number"},
                    "description": "for each capability you chose: 0–1, can that specialist do what is asked? "
                                   "A related topic is not enough."}},
         "required": ["capabilities", "full_flow", "goal"]})
    chosen = {CAPABILITIES[c] for c in intent["capabilities"] if c in CAPABILITIES
              and (intent.get("fit") or {}).get(c, 1) >= 0.4}
    roles = set(FULL_FLOW) if intent["full_flow"] or len(intent["capabilities"]) >= 6 else chosen
    roles = close(roles, bool(intent.get("keywords")), bool(intent.get("competitors")))
    roles.add("ruth")
    roles.add("quinn")  # baseline + after-report for any listing change
    if "yuki" in roles and not intent.get("locales"):
        roles.discard("yuki")
    return {"intent": intent, "roles": sorted(roles, key=lambda r: (ORDER + ["ruth"]).index(r))}


def quote(roles: list[str], locales: list[str]) -> tuple[list[dict], float]:
    prices = settings().prices
    lines = [{"role": "nora", "units": 1, "credits": prices["nora"]}]
    for r in roles:
        units = len(locales) if r == "yuki" else 2 if r == "quinn" else 1
        lines.append({"role": r, "units": units, "credits": round(prices[r] * units, 2)})
    return lines, round(sum(line["credits"] for line in lines), 2)


def fields_for(role: str, intent: dict, product: dict, locale: str | None = None) -> dict[str, Any]:
    market = (intent.get("market_country") or "US").upper()
    base = {"market_country": market, "language": "en"}
    title = product.get("title", "")
    return {
        "kai": {**base, "product": title, "seed_keywords": "\n".join(intent.get("keywords", [])),
                "competitor_domains": "\n".join(intent.get("competitors", []))},
        "rafael": {**base, "product": title, "known_competitors": "\n".join(intent.get("competitors", []))},
        "priya": {**base, "category": product.get("productType") or title, "my_product": title,
                  "competitor_products": "\n".join(intent.get("competitors", []))},
        "marcus": {"market_country": market, "goal": "launch", "margin_floor_pct": "35", "product": title},
        "clara": {"locale": "en-US"},
        "iris": {"product_name": title, "category": product.get("productType") or "product",
                 "channels": "store,google_shopping,google_ads", "lifestyle_count": "3"},
        "oskar": {"collection_strategy": "existing"},
        "yuki": {"target_locale": locale or "", "target_market": (locale or "").upper()},
        "leo": {"deliverables": "faq,comparison,blog,email,social"},
        "sasha": {"campaign_types": "search,shopping", "budget_cap": "1000", "market_country": market,
                  "margin_pct": ""},
        "ruth": {"markets": "US,EU", "category": "general"},
        "quinn": {"mode": "audit", "market_country": market, "store_queries": "\n".join(intent.get("keywords", []))},
    }[role]


def advance(task_id: str) -> None:  # noqa: C901 — one explicit state machine reads best in one place
    client = Sokosumi("nora")
    task = client.task(task_id)
    run = db.get_run(task_id) or {"phase": "start", "state": {}}
    phase, st = run["phase"], run["state"]
    s = settings()

    def save(next_phase: str) -> None:
        db.save_run(task_id, "nora", next_phase, st)

    while True:
        if phase == "start":
            client.event(task_id, status="RUNNING", comment="Hi, I'm Nora. Reading your request…")
            phase = "intake"
            save(phase)

        elif phase == "intake":
            if not runs.store_connected(task):
                runs.request_connection(client, task, "I'll work on your listing directly.")
                phase = "auth_wait"
                save(phase)
                return
            st["plan"] = plan(task, st.get("answers", []))
            hint = st["plan"]["intent"].get("product_hint", "")
            products = runs.find_products(task, hint) if hint else []
            if not products:
                listing = "\n".join(f"- {p['title']} (`{p['handle']}`)" for p in runs.find_products(task))
                st["wait_event_id"] = client.event(task_id, status="INPUT_REQUIRED",
                                                   comment=f"Which product is this for?\n{listing}")["id"]
                phase = "input_wait"
                save(phase)
                return
            st["product_id"] = products[0]["id"]
            st["baseline_snapshot"] = runs.snapshot(task, st["product_id"])
            phase = "plan"
            save(phase)

        elif phase in ("auth_wait", "input_wait"):
            if phase == "auth_wait":
                if not runs.store_connected(task):
                    return
            else:
                answer = runs.latest_comment(runs.user_replies(client, task_id, st.get("wait_event_id")))
                if not answer:
                    return
                st.setdefault("answers", []).append(answer)
            client.event(task_id, status="RUNNING", comment="Thanks — continuing.")
            phase = "intake"
            save(phase)

        elif phase == "plan":
            intent, roles = st["plan"]["intent"], st["plan"]["roles"]
            lines, total = quote(roles, intent.get("locales", []))
            if intent.get("budget_credits") and total > intent["budget_credits"]:
                optional = [r for r in reversed(ORDER) if r in roles and r not in ("quinn", "clara")]
                while optional and total > intent["budget_credits"]:
                    roles.remove(optional.pop(0))
                    lines, total = quote(roles, intent.get("locales", []))
            st["plan"] |= {"roles": roles, "lines": lines, "total": total}
            st["plan_hash"] = sha256_hex(json.dumps(lines, sort_keys=True))
            table = "\n".join(f"| {line['role'].title()} | {line['units']} | {line['credits']} |" for line in lines)
            plan_json = json.dumps({"agents": [{"role": line["role"], "credits": line["credits"]} for line in lines],
                                    "total": total, "plan_hash": st["plan_hash"]})
            st["wait_event_id"] = client.event(task_id, status="APPROVAL_REQUIRED", comment=(
                f"**Plan for {st['baseline_snapshot']['product']['title']}**\n\n{intent['goal']}\n\n"
                f"| Specialist | Units | Credits |\n|---|---|---|\n{table}\n| **Total** | | **{total}** |\n\n"
                "Every deliverable is scored and checked by Chainlink before it's paid; failed work is refunded. "
                "Nothing changes in your store until you approve the final changes.\n\n"
                "Move this Task to **Ready** (or reply **approve**) to start, or reply with changes.\n\n"
                f"```json\n{plan_json}\n```"))["id"]
            phase = "quote_wait"
            save(phase)
            return

        elif phase == "quote_wait":
            replies = runs.user_replies(client, task_id, st["wait_event_id"])
            decision = runs.approval_event(replies)
            if decision is None:
                return
            if decision is False:
                st.setdefault("answers", []).append(runs.latest_comment(replies))
                client.event(task_id, status="RUNNING", comment="Updating the plan…")
                phase = "intake"
                save(phase)
                continue
            st["plan_approval_event_id"] = decision["id"]
            client.event(task_id, status="RUNNING", comment="Approved — starting the work.")
            phase = "pay" if s.payments_enabled else "execute"
            save(phase)

        elif phase == "pay":
            st["terms"] = payments.request_terms("nora", task.get("description") or task.get("name"), task_id)
            payments.charge(client, task_id, st["terms"], s.prices["nora"])
            phase = "funds_wait"
            save(phase)

        elif phase == "funds_wait":
            if not payments.funds_locked(st["terms"]):
                return
            phase = "execute"
            save(phase)

        elif phase == "execute":
            if not step_dag(client, task, st):
                save(phase)
                return
            phase = "merge"
            save(phase)

        elif phase == "merge":
            merge(client, task, st)
            phase = "approval_wait"
            save(phase)
            return

        elif phase == "approval_wait":
            replies = runs.user_replies(client, task_id, st["wait_event_id"])
            decision = runs.approval_event(replies)
            if decision is None:
                return
            if decision is False:
                st["wait_event_id"] = client.event(task_id, comment="Noted. Reply **approve** to publish these "
                                                                    "changes, or cancel the Task.")["id"]
                save(phase)
                return
            st["approval_event_id"] = decision["id"]
            client.event(task_id, status="RUNNING", comment="Approved — Chainlink is publishing your changes.")
            phase = "publish"
            save(phase)

        elif phase == "publish":
            user_id, org_id = runs.owner(task)
            st["publish"] = cre.trigger("publish", {
                "task_id": task_id, "coworker": "nora", "user_id": user_id, "org_id": org_id,
                "change_hash": st["change_hash"], "approval_event_id": st["approval_event_id"],
                "changeset_url": runs.changeset_url(st["changeset"]),
                "manifests": [runs.manifest_ref(n["result_hash"]) for n in st["nodes"].values()
                              if n.get("verdict") == "PASS" and n["role"] not in ("quinn", "ruth")]})
            if not st["publish"].get("published"):
                st["error"] = f"Publishing was refused: {st['publish'].get('reason', 'unknown')}"
                phase = "failed"
            else:
                phase = "report"
            save(phase)

        elif phase == "report":
            if "after" not in st:
                st["after"] = {"status": "pending"}
                after_inputs = fields_for("quinn", st["plan"]["intent"], {}) | {"mode": "before_after"}
                hire(client, task, st, "quinn_after", "quinn", after_inputs)
                save(phase)
            if not poll_node(client, task, st, "quinn_after"):
                save(phase)
                return
            phase = "deliver"
            save(phase)

        elif phase == "deliver":
            deliver(client, task, st)
            if s.payments_enabled:
                payments.submit_result(st["terms"], result_hash(json.dumps(st["publish"], sort_keys=True)))
            phase = "done"
            save(phase)
            return

        elif phase == "failed":
            client.event(task_id, status="FAILED", comment=st.get("error", "Something went wrong."))
            phase = "closed"
            save(phase)
            return
        else:
            return


# --- execution -------------------------------------------------------------------------------------

def hire(client: Sokosumi, task: dict, st: dict, node: str, role: str, fields: dict, extra: dict | None = None) -> None:
    nodes = st.setdefault("nodes", {})
    n = nodes.setdefault(node, {"role": role, "attempts": 0})
    upstream = {r: v["result_hash"] for r, v in nodes.items() if v.get("result_hash") and v.get("verdict") == "PASS"}
    envelope = {"job_or_task_id": f"{task['id']}:{node}", "fields": fields, "read_token": runs.read_token(task),
                "store_snapshot": runs.snapshot(task, st["product_id"]), "upstream": upstream,
                "failure_reasons": n.get("failure_reasons", []), **(extra or {})}
    job = client.hire(task["id"], settings().agent_ids[role], {**fields, "context": json.dumps(envelope)},
                      settings().prices[role], f"{role.title()} · {node}")
    n |= {"job_id": job["id"], "status": "hired", "attempts": n["attempts"] + 1}


def poll_node(client: Sokosumi, task: dict, st: dict, node: str) -> bool:
    """True once the node is finished (PASS or given up)."""
    n = st["nodes"][node]
    if n["status"] in ("done", "blocked"):
        return True
    job = client.job(n["job_id"])
    if job["status"] in ("failed", "payment_failed"):
        n["failure_reasons"] = [job.get("result") or job["status"]]
        n["status"] = "blocked" if n["attempts"] >= 2 else "retry"
        return n["status"] == "blocked"
    if job["status"] != "completed" or not job.get("result"):
        return False
    n["result_hash"] = result_hash(job["result"])
    user_id, org_id = runs.owner(task)
    verdict = cre.trigger("verify", {"mode": "job", "role": n["role"], "task_id": task["id"], "job_id": n["job_id"],
                                     "result_hash": n["result_hash"], "manifest_url": runs.manifest_ref(n["result_hash"])["url"],
                                     "user_id": user_id, "org_id": org_id,
                                     "plan_approval_event_id": st.get("plan_approval_event_id")})
    n["verdict"] = verdict["outcome"]
    n["score"] = verdict["score"]
    client.event(task["id"], comment=f"{n['role'].title()} delivered · Chainlink: **{verdict['outcome']}** "
                                     f"{verdict['score']}/100" + ("" if verdict["outcome"] == "PASS" else
                                                                  " · refunded, retrying once"))
    if verdict["outcome"] == "PASS":
        n["status"] = "done"
        return True
    n["failure_reasons"] = verdict.get("reasons", [])
    n["status"] = "blocked" if n["attempts"] >= 2 else "retry"
    return n["status"] == "blocked"


def step_dag(client: Sokosumi, task: dict, st: dict) -> bool:
    """Advance every node that can move. True when all nodes are finished."""
    intent, roles = st["plan"]["intent"], st["plan"]["roles"]
    product = st["baseline_snapshot"]["product"]
    nodes = st.setdefault("nodes", {})
    wanted = [r for r in ORDER if r in roles]
    targets = []
    for r in wanted:
        if r == "yuki":
            targets += [(f"yuki:{loc}", "yuki", loc) for loc in intent.get("locales", [])]
        else:
            targets.append((r, r, None))
    finished = True
    for node, role, locale in targets:
        n = nodes.get(node)
        deps = [d for d in DEPENDS.get(role, []) if d in roles] + ([] if role == "quinn" else ["quinn"])
        if not n or n.get("status") == "retry":
            if all(nodes.get(d, {}).get("status") in ("done", "blocked") for d in deps):
                hire(client, task, st, node, role, fields_for(role, intent, product, locale))
            finished = False
            continue
        if not poll_node(client, task, st, node):
            finished = False
    return finished


def merge(client: Sokosumi, task: dict, st: dict) -> None:
    """Collect changesets from passing deliverables, run Ruth over them, project the score, ask for approval."""
    changeset: list[dict] = []
    for n in st["nodes"].values():
        if n.get("verdict") == "PASS" and n["role"] not in ("quinn", "ruth"):
            changeset += manifest_from_store(n["result_hash"])["changeset"]
    if changeset and "ruth" in st["plan"]["roles"] and "ruth" not in st["nodes"]:
        hire(client, task, st, "ruth", "ruth", fields_for("ruth", st["plan"]["intent"], {}),
             extra={"review_changeset": changeset})
        while not poll_node(client, task, st, "ruth"):
            time.sleep(10)
        ruth = st["nodes"]["ruth"]
        if ruth.get("verdict") == "PASS":
            report = manifest_from_store(ruth["result_hash"])
            blocked_locations = {h["location"] for h in report.get("self_checks", {}).get("unresolved", [])}
            changeset = [op for op in changeset if not _touches(op, blocked_locations)]
    st["changeset"] = changeset
    st["change_hash"] = change_hash(changeset)
    projected = deepcopy(st["baseline_snapshot"]["product"])
    for op in changeset:
        if op["op"] == "product.update":
            projected |= op["fields"]
    before = score(st["baseline_snapshot"]["product"])["deterministic"]
    after = score(projected)["deterministic"]
    client.upload(task["id"], "changes.html", runs.changes_html(changeset), "text/html")
    blocked = [n["role"] for n in st["nodes"].values() if n["status"] == "blocked"]
    st["wait_event_id"] = client.event(task["id"], status="APPROVAL_REQUIRED", comment=(
        f"**{len(changeset)} changes ready** (projected core listing score {before:.0f} → {after:.0f} of 95):\n\n"
        + runs.describe_changes(changeset, st["baseline_snapshot"]["product"])
        + (f"\n\nNot included (did not pass verification): {', '.join(blocked)}." if blocked else "")
        + f"\n\nFull diff attached (`changes.html`, change hash `{st['change_hash'][:16]}`). "
        "Ads stay paused and the blog article stays unpublished.\n\n"
        "Move this Task to **Ready** (or reply **approve**) to publish."))["id"]


def _touches(op: dict, locations: set[str]) -> bool:
    name = op["op"]
    if name == "product.update":
        return any(loc.startswith("product.") for loc in locations)
    if name == "metafields.set":
        return any(f"metafield.{m['key']}" in locations for m in op["metafields"])
    if name == "translations.register":
        return any(loc.startswith("translation.") for loc in locations)
    if name == "article.create":
        return "article" in locations
    return False


def deliver(client: Sokosumi, task: dict, st: dict) -> None:
    pack = io.BytesIO()
    with zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED) as z:
        for node, n in st["nodes"].items():
            if n.get("result_hash"):
                m = manifest_from_store(n["result_hash"])
                z.writestr(f"{node}/summary.md", m["summary_md"])
                z.writestr(f"{node}/manifest.json", json.dumps(m, indent=2))
    client.upload(task["id"], "uplift-launch-pack.zip", pack.getvalue(), "application/zip")
    after = st["nodes"]["quinn_after"]
    report = manifest_from_store(after["result_hash"])["summary_md"] if after.get("result_hash") else ""
    user_id, org_id = runs.owner(task)
    for n in st["nodes"].values():
        if n.get("verdict") and n["status"] == "done":
            with contextlib.suppress(Exception):  # ratings are best-effort
                client.rate(settings().agent_ids[n["role"]], 5 if n["verdict"] == "PASS" else 2, (user_id, org_id))
    client.event(task["id"], status="COMPLETED", comment=(
        f"**Done.** Published {len(st['changeset'])} changes. Core listing score now "
        f"{st['publish'].get('after_score', '?')}/95.\n\n{report}\n\nEverything is in `uplift-launch-pack.zip`."))
