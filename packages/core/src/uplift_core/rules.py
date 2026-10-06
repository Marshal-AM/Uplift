"""uplift-rules engine: deterministic claim scanning shared by Ruth, Quinn and (ported) CRE."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any


@dataclass
class Hit:
    rule_id: str
    pack: str
    severity: str
    location: str
    excerpt: str
    message: str


@lru_cache
def load() -> dict[str, Any]:
    return json.loads(files("uplift_core").joinpath("uplift-rules.json").read_text())


def scan(segments: list[dict[str, str]], brand_terms: list[str] | None = None,
         substantiated: set[str] | None = None) -> list[Hit]:
    """segments: [{"location": "title", "text": "...", "kind": "copy"|"ad"|"shopping_image"}]"""
    rules = load()["rules"]
    hits: list[Hit] = []
    for seg in segments:
        text, kind = seg["text"] or "", seg.get("kind", "copy")
        for rule in rules:
            if rule.get("applies_to") and rule["applies_to"] != kind:
                continue
            flags = 0 if rule.get("case_sensitive") else re.IGNORECASE
            for m in re.finditer(rule["pattern"], text, flags):
                if substantiated and rule["id"] in substantiated and rule.get("substantiable"):
                    continue
                hits.append(Hit(rule["id"], rule["pack"], rule["severity"], seg["location"],
                                text[max(0, m.start() - 30): m.end() + 30], rule["message"]))
        for term in brand_terms or []:
            if term and re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                hits.append(Hit("TM-001", "trademarks", "high", seg["location"], term,
                                f"Uses competitor mark '{term}'."))
    return hits
