"""Follow a Task's live trace in the terminal — the same steps as the /live page.

    uv run python e2e/trace.py                    # the newest Task, live
    uv run python e2e/trace.py TASK_ID            # a given Task
    uv run python e2e/trace.py TASK_ID --until-wait   # stop when it waits for the merchant or finishes
    uv run python e2e/trace.py --tasks            # recent Tasks

Reads the viewing key from infra/.secrets/trace.json (or TRACE_VIEW_KEY).
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from rich.console import Console
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("TRACE_API", "https://worker-production-47e0.up.railway.app")
COLORS = {"Sokosumi": "medium_purple1", "Masumi": "gold1", "Cardano": "cyan", "Chainlink": "dodger_blue1",
          "Kodosumi": "dark_orange", "Amazon Bedrock": "hot_pink", "Google Gemini": "aquamarine1", "Serper": "chartreuse2",
          "Shopify": "spring_green2", "Firecrawl": "salmon1", "Tavily": "yellow1", "Amazon S3": "grey70",
          "Uplift Worker": "sky_blue1", "Agent": "sky_blue1"}
MARK = {"ok": ("✓", "green"), "running": ("…", "dodger_blue1"), "error": ("✗", "red"), "fail": ("✗", "yellow"),
        "stage": ("▸", "bold white")}
WAITING = {"auth_wait", "input_wait", "quote_wait", "approval_wait"}
DONE = {"done", "closed", "failed"}


def key() -> str:
    if os.environ.get("TRACE_VIEW_KEY"):
        return os.environ["TRACE_VIEW_KEY"]
    return json.loads((ROOT / "infra" / ".secrets" / "trace.json").read_text())["view_key"]


def get(path: str, **params) -> dict:
    return httpx.get(f"{API}{path}", params={"key": key(), **params}, timeout=30).raise_for_status().json()


def color(service: str) -> str:
    return next((c for k, c in COLORS.items() if service.startswith(k)), "grey62")


def dur(ms) -> str:
    if ms is None:
        return ""
    return f"{ms:.0f} ms" if ms < 1000 else f"{ms / 1000:.1f} s" if ms < 60_000 else f"{ms // 60_000:.0f} m {ms % 60_000 / 1000:02.0f} s"


def name(agent: str) -> str:
    base, _, rest = agent.replace("_after", ":after-report").partition(":")
    return base.title() + (f" ({rest})" if rest else "")


def line(e: dict, t0: float) -> Text:
    off = (e["at"] - t0) / 1000
    t = Text(f"{int(off // 60):>3}:{int(off % 60):02d}  ", style="grey50")
    mark, style = MARK.get(e["status"], ("·", "white"))
    if e["status"] == "stage":
        return t + Text(f"{mark} {name(e['agent'] or '')} · {e['step']}", style="bold")
    t += Text(f"{mark} ", style=style)
    if e["agent"]:
        t += Text(f"{name(e['agent']):<7} ", style="grey70")
    t += Text(f"[{e['service']}] ", style=color(e["service"]))
    t += Text(e["step"], style="bold" if e["status"] != "running" else "")
    if e["detail"]:
        t += Text(f" — {e['detail']}", style="grey62")
    if e["ms"] is not None and e["status"] != "running":
        t += Text(f"  {dur(e['ms'])}", style="grey50")
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?")
    ap.add_argument("--tasks", action="store_true", help="list recent Tasks")
    ap.add_argument("--until-wait", action="store_true", help="stop when the merchant must act or the Task ends")
    a = ap.parse_args()
    out = Console(highlight=False)
    tasks = get("/trace/tasks")["tasks"]
    if a.tasks:
        for t in tasks:
            when = datetime.fromtimestamp(t["started"] / 1000).strftime("%H:%M")
            out.print(f"{t['task']}  {when}  {(t['coworker'] or '').title():<7} {t['phase_label']:<34} {t['title']}")
        return
    task = a.task or (tasks[0]["task"] if tasks else None)
    if not task:
        raise SystemExit("No traced Tasks yet.")
    info = next((t for t in tasks if t["task"] == task), {})
    out.print(Text(f"{(info.get('coworker') or '').title()} · {info.get('title', task)}", style="bold"))
    after, t0, settled, last_pass = 0, None, set(), False
    while True:
        events = get("/trace/events", task=task, after=after)["events"]
        for e in events:
            after = e["id"]
            t0 = t0 or e["at"]
            if e["status"] == "running" and e["span"]:
                continue  # printed once, when it finishes (Ctrl-C shows nothing half-done)
            if e["span"]:
                settled.add(e["span"])
            out.print(line(e, t0))
        if last_pass:  # one more read after the end, for the steps written alongside it
            out.print(Text(f"— {phase}", style="bold yellow" if phase in WAITING else "bold green"))
            return
        phase = next((t["phase"] for t in get("/trace/tasks")["tasks"] if t["task"] == task), None)
        last_pass = phase in DONE or (a.until_wait and phase in WAITING)
        time.sleep(1 if last_pass else 2)


if __name__ == "__main__":
    main()
