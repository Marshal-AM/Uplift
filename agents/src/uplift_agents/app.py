"""Kodosumi app: one Ray Serve ingress exposing the 12 Uplift specialists.

Each endpoint becomes a Kodosumi flow (`x-kodosumi`) and, through Sumi, a MIP-003 agent at
`/sumi/uplift/<name>` — that URL is the apiBaseUrl registered on Masumi.
"""

import json
import re

import fastapi
from kodosumi.core import Launch, ServeAPI
from kodosumi.core import forms as F
from kodosumi.error import KodosumiError
from ray import serve
from uplift_core import trace

from .flows import clara, iris, kai, leo, marcus, oskar, priya, quinn, rafael, ruth, sasha, yuki

AUTHOR = "Uplift"
VERSION = "5.0.0"

SPECIALISTS = [
    ("kai", kai, "Kai · Search Demand Analyst",
     "Clustered keyword map from real Google autocomplete, related searches and questions, with demand and intent.",
     ["keyword research", "seo", "search intent"]),
    ("rafael", rafael, "Rafael · Competitor & Market Analyst",
     "Who ranks on Google and Google Shopping, what they charge and promise, and where the gaps are.",
     ["competitor analysis", "google shopping", "pricing"]),
    ("priya", priya, "Priya · Competitor Review & Sentiment Analyst",
     "What competitors' customers love, hate and still want — with verbatim, linked quotes.",
     ["competitor reviews", "sentiment", "voice of customer"]),
    ("marcus", marcus, "Marcus · Pricing & Promotions Strategist",
     "Price positioning, promotion calendar and scheduled discount codes that never break your margin floor.",
     ["pricing", "promotions", "discount codes"]),
    ("clara", clara, "Clara · Product Page Copywriter",
     "Title, description, SEO title and meta, handle and tags — real search terms, facts only.",
     ["copywriting", "product description", "seo"]),
    ("iris", iris, "Iris · Product Visual Designer",
     "Image audit, cleanup, lifestyle scenes around your real product, channel versions and alt text.",
     ["product images", "background removal", "alt text"]),
    ("oskar", oskar, "Oskar · Catalog, Collections & Shopping Feed Specialist",
     "Product category, tags, collections, related products and Google Shopping feed readiness.",
     ["catalog", "google shopping", "collections"]),
    ("yuki", yuki, "Yuki · Localization & Transcreation Specialist",
     "Your listing adapted to a new market with local search terms, published into store translations.",
     ["translation", "localization", "multilingual seo"]),
    ("leo", leo, "Leo · Content & Email Marketer",
     "FAQ, comparison table, SEO blog article, launch emails, flow blueprints and a social pack.",
     ["content", "faq", "email"]),
    ("sasha", sasha, "Sasha · Paid Ads Strategist",
     "Break-even Google Ads campaigns with keywords, negatives, copy and a paused import file.",
     ["google ads", "ppc", "roas"]),
    ("ruth", ruth, "Ruth · Claims & Compliance Reviewer",
     "Claim, trademark and ad-policy findings with safe rewrites.",
     ["compliance", "claims", "ad policy"]),
    ("quinn", quinn, "Quinn · Store Auditor & Performance Analyst",
     "0–100 listing score, ranking snapshot, fix plan and before/after reports.",
     ["audit", "seo audit", "product ranking"]),
]

app = ServeAPI()


class _Narrated:
    """The flow's tracer, also sending each of the agent's own step notes to the live trace as a heading."""

    def __init__(self, tracer, role: str):
        self._tracer, self._role = tracer, role

    def markdown_sync(self, text: str):
        step = re.sub(r"\*\*\w+\*\* · ", "", text).replace("**", "").strip()
        trace.emit("Agent", step[:1].upper() + step[1:], status="stage", kind="stage")
        return self._tracer.markdown_sync(text)

    def __getattr__(self, name: str):
        return getattr(self._tracer, name)


def _run_id(inputs: dict) -> str | None:
    try:
        return json.loads(inputs.get("context") or "{}").get("job_or_task_id")
    except ValueError:
        return None


def _guarded(fn):
    """Kodosumi only surfaces KodosumiError; wrap so every failure reaches the caller with its message. Each run is
    attributed to its Sokosumi Task in the live trace."""
    role = fn.__module__.rsplit(".", 1)[-1]

    def run(inputs: dict, tracer):
        run_id = _run_id(inputs) or ""
        node = run_id.split(":", 1)[1] if ":" in run_id else role  # Nora's plan node: quinn_after, yuki:de
        trace.bind(run_id or None, node, process_wide=True)
        try:
            return fn(inputs, _Narrated(tracer, role))
        except KodosumiError as exc:
            trace.emit("Agent", "Stopped", str(exc), status="error", kind="agent.error")
            raise
        except Exception as exc:
            trace.emit("Agent", "Stopped with an error", f"{type(exc).__name__}: {exc}", status="error",
                       kind="agent.error")
            raise KodosumiError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            trace.flush()

    run.__name__ = f"{fn.__module__.rsplit('.', 1)[-1]}_run"
    return run


def _register(name: str, module, summary: str, description: str, tags: list[str]) -> None:
    model = F.Model(
        F.Markdown(f"## {summary}\n{description}"),
        *module.FIELDS,
        F.InputArea(label="Context (set automatically by Uplift; leave empty)", name="context"),
        F.Submit("Run"),
        F.Cancel("Cancel"),
    )

    async def enter(request: fastapi.Request, inputs: dict):
        return Launch(request, _guarded(module.run), inputs=inputs)

    app.enter(path=f"/{name}", model=model, summary=summary, description=description, tags=["Uplift", *tags],
              version=VERSION, author=AUTHOR, organization=AUTHOR)(enter)


for spec in SPECIALISTS:
    _register(*spec)


@serve.deployment
@serve.ingress(app)
class Uplift:
    pass


fast_app = Uplift.bind()
