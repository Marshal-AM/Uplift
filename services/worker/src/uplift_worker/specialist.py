"""Standalone Task runner for one specialist coworker (Kai … Quinn).

Phases (journaled before each side effect):
start → intake → [auth_wait | input_wait] → pay → execute → verify → funds_wait → [approval → approval_wait →
publish] → deliver → done | failed
(the work runs while the escrow lock settles on-chain; nothing is delivered or published before it is locked)
"""

import json
from typing import Any

from uplift_core import llm
from uplift_core.hashing import change_hash, result_hash

from . import cre, db, payments, runs
from .clients import FlowError, Kodosumi, ReauthRequired, Sokosumi
from .config import settings

NEEDS_STORE = {"oskar"}  # every other specialist also works from pasted copy, URLs or images


def _required(schema: list[dict]) -> list[str]:
    return [f["id"] for f in schema if f["type"] != "none" and f["id"] != "context"
            and not any(v["validation"] == "optional" for v in f.get("validations") or [])]


def form_values(schema: list[dict], values: dict[str, str]) -> dict[str, str]:
    """Non-empty answers as Kodosumi form values, over the form's own defaults (so the merchant is not asked for a
    market or language the form already defaults to); a checkbox counts as checked only with the value "on"."""
    boolean = {f["id"] for f in schema if f["type"] == "boolean"}
    out = {f["id"]: str(d) for f in schema if f["id"] not in boolean and (d := (f.get("data") or {}).get("default"))}
    out |= {k: v for k, v in values.items() if v and k not in boolean}
    out |= {k: "on" for k in boolean if str(values.get(k, "")).strip().lower() in ("true", "yes", "on", "1")}
    return out


def intake(task: dict, schema: list[dict], answers: list[str]) -> dict[str, Any]:
    fields = [{"id": f["id"], "label": f["name"], "type": f["type"], "options": (f.get("data") or {}).get("values")}
              for f in schema if f["type"] != "none" and f["id"] != "context"]
    return llm.structured(
        f"A merchant assigned this Task:\nTitle: {task.get('name')}\nBrief: {task.get('description')}\n"
        f"Follow-up answers: {answers}\nFill the form fields from the brief. Copy any content the merchant pasted "
        "(product copy, HTML, ad text, URLs, image links) verbatim and in full into the matching field. Leave unknown "
        "fields empty. "
        "Set uses_connected_store to true only if the merchant wants you to work on a product in their store and has "
        "NOT given you the copy, URLs or images the work needs; pasted content means false. Set product_hint to the "
        "product's name/handle/URL if mentioned.\nFields: " + json.dumps(fields),
        {"type": "object", "properties": {
            "values": {"type": "object", "additionalProperties": {"type": "string"}},
            "uses_connected_store": {"type": "boolean"}, "product_hint": {"type": "string"},
            "missing_question": {"type": "string",
                                 "description": "one short question for anything essential that is missing"}},
         "required": ["values", "uses_connected_store"]})


def advance(role: str, task_id: str) -> None:
    client = Sokosumi(role)
    task = client.task(task_id)
    run = db.get_run(task_id) or {"phase": "start", "state": {}}
    phase, st = run["phase"], run["state"]

    def save(next_phase: str) -> None:
        db.save_run(task_id, role, next_phase, st)

    while True:
        if phase == "start":
            client.event(task_id, status="RUNNING", comment="On it.")
            phase = "intake"
            save(phase)

        elif phase == "intake":
            schema = Kodosumi().input_schema(role)
            parsed = intake(task, schema, st.get("answers", []))
            st["fields"] = form_values(schema, parsed["values"])
            # naming a product in a connected store means "work on that product" (so changes can be published)
            uses_store = role in NEEDS_STORE or parsed["uses_connected_store"] or (
                bool(parsed.get("product_hint")) and runs.store_connected(task))
            if uses_store and not runs.store_connected(task):
                runs.request_connection(client, task, "This needs your store data.")
                phase = "auth_wait"
                save(phase)
                return
            if uses_store and not st.get("product_id"):
                products = runs.find_products(task, parsed.get("product_hint", ""))
                if len(products) == 1 or (products and parsed.get("product_hint")):
                    st["product_id"] = products[0]["id"]
                else:
                    listing = "\n".join(f"- {p['title']} (`{p['handle']}`)" for p in runs.find_products(task))
                    st["wait_event_id"] = client.event(task_id, status="INPUT_REQUIRED",
                                                       comment=f"Which product should I work on?\n{listing}")["id"]
                    phase = "input_wait"
                    save(phase)
                    return
            missing = [f for f in _required(schema) if f not in st["fields"]]
            if missing and not (uses_store and set(missing) <= {"product", "product_name", "current_copy"}):
                question = parsed.get("missing_question") or f"Please add: {', '.join(missing)}."
                st["wait_event_id"] = client.event(task_id, status="INPUT_REQUIRED", comment=question)["id"]
                phase = "input_wait"
                save(phase)
                return
            # a question asked mid-run (INPUT_MISSING) comes back through intake: never charge twice
            phase = "pay" if settings().payments_enabled and not st.get("terms") else "execute"
            save(phase)

        elif phase == "auth_wait":
            if not runs.store_connected(task):
                return
            client.event(task_id, status="RUNNING", comment="Store connected — continuing.")
            phase = "intake"
            save(phase)

        elif phase == "input_wait":
            replies = runs.user_replies(client, task_id, st.get("wait_event_id"))
            answer = runs.latest_comment(replies)
            if not answer:
                return
            st.setdefault("answers", []).append(answer)
            hits = [p for p in runs.find_products(task, answer)] if runs.store_connected(task) else []
            if hits and not st.get("product_id"):
                st["product_id"] = hits[0]["id"]
            client.event(task_id, status="RUNNING", comment="Thanks — continuing.")
            phase = "intake"
            save(phase)

        elif phase == "pay":
            paid = payments.pay(client, task_id, st, role, task.get("description") or task.get("name"),
                                settings().prices[role], lambda: save("pay"))
            # Core debits the credits when it accepts the payment, so the work starts now; the escrow lock settles
            # on-chain meanwhile and is required before anything is delivered or published (funds_wait)
            phase = "execute" if paid else "closed"  # out of credits: Sokosumi already shows OUT_OF_CREDITS
            save(phase)

        elif phase == "funds_wait":
            if st.get("terms") and not payments.funds_locked(st["terms"]):
                return
            phase = st.pop("after_funds", "execute")
            save(phase)

        elif phase == "execute":
            envelope = {"job_or_task_id": task_id, "fields": st["fields"],
                        "failure_reasons": st.get("failure_reasons", [])}
            if st.get("product_id"):
                envelope |= {"read_token": runs.read_token(task), "store_snapshot": runs.snapshot(task, st["product_id"])}
            kodo = Kodosumi()
            try:
                if not st.get("fid"):  # journal the run id first so a restart resumes instead of relaunching
                    st["fid"] = kodo.launch(role, {**st["fields"], "context": json.dumps(envelope)})
                    save(phase)
                manifest_text = kodo.wait(st["fid"])
            except ReauthRequired:
                st.pop("fid", None)
                runs.request_connection(client, task, "Your store connection expired.")
                phase = "auth_wait"
                save(phase)
                return
            except FlowError as exc:
                st.pop("fid", None)
                message = str(exc)
                if "INPUT_MISSING" in message:
                    st["wait_event_id"] = client.event(task_id, status="INPUT_REQUIRED",
                                                       comment=message.split("INPUT_MISSING:")[-1].strip())["id"]
                    phase = "input_wait"
                elif "STORE_REAUTH_REQUIRED" in message or "STORE_CONNECTION_REQUIRED" in message:
                    runs.request_connection(client, task, "I need access to your store.")
                    phase = "auth_wait"
                else:
                    st["error"] = message[:500]
                    phase = "failed"
                save(phase)
                continue
            st.pop("fid", None)
            st["result_hash"] = result_hash(manifest_text)
            st["manifest"] = json.loads(manifest_text)
            phase = "verify"
            save(phase)

        elif phase == "verify":
            user_id, org_id = runs.owner(task)
            verdict = cre.trigger("verify", {"mode": "task", "role": role, "task_id": task_id,
                                             "result_hash": st["result_hash"],
                                             "manifest_url": runs.manifest_ref(st["result_hash"])["url"],
                                             "user_id": user_id, "org_id": org_id})
            st.setdefault("verdicts", []).append(verdict)
            client.event(task_id, comment=f"Chainlink verification: **{verdict['outcome']}** · {verdict['score']}/100")
            if verdict["outcome"] == "PASS":
                st["after_funds"] = "approval" if st["manifest"]["changeset"] else "deliver"
                phase = "funds_wait"
            elif len(st["verdicts"]) < 2:
                st["failure_reasons"] = verdict.get("reasons", [])
                phase = "execute"
            else:
                st["error"] = "Work did not pass verification twice; no charge was submitted."
                phase = "failed"
            save(phase)

        elif phase == "approval":
            changeset = st["manifest"]["changeset"]
            st["change_hash"] = change_hash(changeset)
            product = (runs.snapshot(task, st["product_id"]) or {}).get("product") if st.get("product_id") else None
            client.upload(task_id, "changes.md", runs.changes_md(changeset), "text/markdown")
            st["wait_event_id"] = client.event(task_id, status="APPROVAL_REQUIRED", comment=(
                "Ready to publish these changes:\n\n" + runs.describe_changes(changeset, product, runs.category_names(task, changeset))
                + f"\n\nFull diff attached (`changes.md`, change hash `{st['change_hash'][:16]}`).\n"
                "Move this Task to **Ready** (or reply **approve**) to publish."))["id"]
            phase = "approval_wait"
            save(phase)
            return

        elif phase == "approval_wait":
            replies = runs.user_replies(client, task_id, st["wait_event_id"])
            decision = runs.approval_event(replies)
            if decision is None:
                return
            if decision is False:
                st["wait_event_id"] = client.event(task_id, comment="Noted. Reply **approve** to publish, or cancel "
                                                                    "the Task to keep your store unchanged.")["id"]
                save(phase)
                return
            st["approval_event_id"] = decision["id"]
            client.event(task_id, status="RUNNING", comment="Approved — publishing.")
            phase = "publish"
            save(phase)

        elif phase == "publish":
            user_id, org_id = runs.owner(task)
            result = cre.trigger("publish", {"task_id": task_id, "coworker": role, "user_id": user_id, "org_id": org_id,
                                             "change_hash": st["change_hash"],
                                             "approval_event_id": st["approval_event_id"],
                                             "changeset_url": runs.changeset_url(st["manifest"]["changeset"]),
                                             "manifests": [runs.manifest_ref(st["result_hash"])]})
            st["publish"] = result
            if not result.get("published"):
                st["error"] = f"Publishing was refused: {result.get('reason', 'unknown')}"
                phase = "failed"
            else:
                phase = "deliver"
            save(phase)

        elif phase == "deliver":
            runs.deliver_files(client, task_id, st["manifest"], st.setdefault("delivered", []), lambda: save("deliver"))
            if settings().payments_enabled:
                payments.submit_result(st["terms"], st["result_hash"])
            after = (st.get("publish") or {}).get("after_score")
            note = "\n\nPublished to your store." + (f" Core listing score now {after}/95." if after is not None else "") \
                if st.get("publish") else ""
            client.event(task_id, status="COMPLETED", comment=st["manifest"]["summary_md"] + note)
            phase = "done"
            save(phase)
            return

        elif phase == "failed":
            client.event(task_id, status="FAILED", comment=st.get("error", "Something went wrong."))
            phase = "closed"
            save(phase)
            return

        else:  # done / closed
            return
