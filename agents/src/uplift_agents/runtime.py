"""Shared agent runtime: the run context passed in by Nora or the Worker, and the deliverable builder.

Every flow:
    ctx = Context.from_inputs(inputs)        # human fields + optional `context` JSON envelope
    out = Deliverable(role, ctx)             # collects artifacts, evidence, changeset
    ...
    return out.finalize(summary_md)          # canonical manifest string -> resultHash
"""

import hashlib
import json
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any

import boto3
import httpx
from uplift_core import trace
from uplift_core.hashing import canonical, sha256_hex

from . import tools

BUCKET = os.environ.get("ARTIFACT_BUCKET", "uplift-artifacts-517207998460")
URL_TTL = 7 * 24 * 3600  # max presign lifetime for IAM-user credentials


@dataclass
class Context:
    """Inputs for one run. `envelope` is set when Nora (or the Worker for standalone Tasks) calls the agent."""

    fields: dict[str, Any]
    envelope: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inputs(cls, inputs: dict[str, Any]) -> "Context":
        raw = (inputs.get("context") or "").strip()
        envelope = json.loads(raw) if raw else {}
        fields = {k: v for k, v in inputs.items() if k != "context"}
        # Nora puts the human-facing values in the envelope too; explicit form fields win
        for k, v in envelope.get("fields", {}).items():
            if fields.get(k) in (None, ""):
                fields[k] = v
        return cls(fields, envelope)

    def get(self, name: str, default: Any = None) -> Any:
        value = self.fields.get(name)
        return default if value in (None, "", []) else value

    def lines(self, name: str) -> list[str]:
        return [x.strip() for x in str(self.get(name, "")).splitlines() if x.strip()]

    @property
    def run_id(self) -> str:
        return self.envelope.get("job_or_task_id") or os.environ.get("KODOSUMI_FID", "local")

    @property
    def read_token(self) -> str | None:
        return self.envelope.get("read_token")

    @property
    def snapshot(self) -> dict[str, Any] | None:
        return self.envelope.get("store_snapshot")

    @property
    def product(self) -> dict[str, Any] | None:
        return (self.snapshot or {}).get("product")

    def upstream(self, role: str) -> dict[str, Any] | None:
        """Verified upstream manifest from another specialist. Nora passes only its resultHash;
        manifests are stored content-addressed, so the hash is also the storage key."""
        result_hash = self.envelope.get("upstream", {}).get(role)
        if not result_hash:
            return None
        body = _s3().get_object(Bucket=BUCKET, Key=f"artifacts/{result_hash}/manifest.json")["Body"].read()
        if hashlib.sha256(body).hexdigest() != result_hash:
            raise RuntimeError(f"upstream {role} manifest does not match its resultHash")
        return json.loads(body)

    def upstream_artifact(self, role: str, name: str) -> Any:
        manifest = self.upstream(role)
        if not manifest:
            return None
        art = next((a for a in manifest["artifacts"] if a["name"] == name), None)
        if not art:
            return None
        raw = httpx.get(art["url"], timeout=60).content
        return json.loads(raw) if art["mime"] == "application/json" else raw


def _s3():
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def store_bytes(name: str, data: bytes, mime: str) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    key = f"artifacts/{digest}/{name}"
    s3 = _s3()
    with trace.span("Amazon S3", f"Saved {name}", f"{len(data) / 1024:,.1f} KB · content-addressed {digest[:12]}…",
                    kind="s3.put", meta={"sha256": digest, "type": mime}):
        s3.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=mime)
    url = s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=URL_TTL)
    return digest, url


class Deliverable:
    def __init__(self, role: str, agent: str, ctx: Context, profile_version: str = "5.0.0"):
        self.role, self.agent, self.ctx = role, agent, ctx
        self.profile = f"{role}@{profile_version}"
        self.changeset: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []
        self.self_checks: dict[str, Any] = {}
        self.bundle: dict[str, Any] = {}  # compact data CRE re-checks (< 200 KB)

    def artifact(self, name: str, content: Any, mime: str | None = None) -> str:
        if isinstance(content, (dict, list)):
            data, mime = json.dumps(content, ensure_ascii=False, indent=2).encode(), "application/json"
        elif isinstance(content, str):
            data = content.encode()
            mime = mime or mimetypes.guess_type(name)[0] or "text/plain"
        else:
            data, mime = content, mime or mimetypes.guess_type(name)[0] or "application/octet-stream"
        digest, url = store_bytes(name, data, mime)
        self.artifacts.append({"name": name, "sha256": digest, "url": url, "mime": mime})
        return url

    def cite(self, claim: str, source_url: str, excerpt: str = "") -> None:
        self.evidence.append({"claim": claim, "source_url": source_url, "excerpt": excerpt[:500]})

    def finalize(self, summary_md: str) -> str:
        bundle_bytes = canonical(self.bundle).encode()
        digest, url = store_bytes("verification_bundle.json", bundle_bytes, "application/json")
        manifest = {
            "uplift": "5",
            "role": self.role,
            "agent": self.agent,
            "job_or_task_id": self.ctx.run_id,
            "input_hash": sha256_hex(canonical(self.ctx.fields)),
            "summary_md": summary_md,
            "changeset": self.changeset,
            "artifacts": self.artifacts,
            "evidence": self.evidence,
            "verification_bundle": {"url": url, "sha256": digest},
            "self_checks": self.self_checks,
            "profile": self.profile,
        }
        text = canonical(manifest)
        # the manifest itself is published so Nora and CRE can fetch it by resultHash
        store_bytes("manifest.json", text.encode(), "application/json")
        return text


def need_store(ctx: Context) -> str:
    if not ctx.read_token:
        raise RuntimeError("STORE_CONNECTION_REQUIRED")
    return ctx.read_token


__all__ = ["Context", "Deliverable", "need_store", "tools"]
