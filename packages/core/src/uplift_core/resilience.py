"""Timeouts and retries for every outside call (model APIs, search, scraping, image generation).

One policy per call site:

    POLICY = Policy("Serper", attempt_timeout=30, attempts=4, budget=90)
    resp = request("POST", url, POLICY, json=body, headers=headers)

- Every attempt has a hard deadline (connect 10 s; read/write/pool `attempt_timeout`), so a hung connection fails
  in bounded time instead of hanging.
- Only transient failures are retried: timeouts, connection errors and 408/409/425/429/500/502/503/504.
  4xx answers that a retry cannot fix come back to the caller at once.
- Backoff is exponential with full jitter (AWS architecture guidance), and a server's Retry-After wins.
- `budget` caps the whole call, attempts and waits together; no attempt starts that the budget cannot finish.
- Each retry is visible in the live trace.

The result is the last response (the caller decides with raise_for_status) or the last exception.
"""

import random
import time
from dataclasses import dataclass, replace
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from . import trace

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
CONNECT_S = 10.0


@dataclass(frozen=True)
class Policy:
    service: str  # as the live trace names it
    attempt_timeout: float  # seconds one attempt may take (no byte for this long = timeout)
    attempts: int = 3
    budget: float | None = None  # seconds for the whole call; default attempts × attempt_timeout + waits
    base_delay: float = 1.0
    max_delay: float = 20.0
    retry_status: frozenset[int] = frozenset(RETRY_STATUS)  # answers worth another attempt on the same key

    def with_timeout(self, attempt_timeout: float, budget: float | None = None) -> "Policy":
        return replace(self, attempt_timeout=attempt_timeout, budget=budget)

    def without(self, *statuses: int) -> "Policy":
        """The same policy, handing these answers straight back (e.g. a 429 a fallback key can serve)."""
        return replace(self, retry_status=self.retry_status - set(statuses))


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError):
            return None


def _backoff(policy: Policy, attempt: int) -> float:
    return random.uniform(0, min(policy.max_delay, policy.base_delay * 2 ** attempt))  # full jitter


def request(method: str, url: str, policy: Policy, **kwargs: Any) -> httpx.Response:
    budget = policy.budget or policy.attempts * policy.attempt_timeout + policy.attempts * policy.max_delay
    started = time.monotonic()
    last: httpx.Response | Exception | None = None
    for attempt in range(policy.attempts):
        left = budget - (time.monotonic() - started)
        timeout = min(policy.attempt_timeout, left)
        if timeout < 2:
            break
        try:
            resp = httpx.request(method, url, timeout=httpx.Timeout(timeout, connect=min(CONNECT_S, timeout)),
                                 **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last, why, wait = exc, ("timed out" if isinstance(exc, httpx.TimeoutException)
                                    else f"connection failed ({type(exc).__name__})"), None
        else:
            if resp.status_code not in policy.retry_status:
                return resp
            last, why, wait = resp, f"answered {resp.status_code}", _retry_after(resp)
        if attempt == policy.attempts - 1:
            break
        delay = min(wait if wait is not None else _backoff(policy, attempt), policy.max_delay * 3)
        if budget - (time.monotonic() - started) - delay < 2:
            break
        trace.emit(policy.service, f"{policy.service} {why} — retrying ({attempt + 2} of {policy.attempts})",
                   f"after {delay:.1f} s · attempt limit {timeout:.0f} s", status="wait", kind="retry")
        time.sleep(delay)
    if isinstance(last, httpx.Response):
        return last
    if last is not None:
        raise last
    raise httpx.TimeoutException(f"{policy.service}: no time left in the {budget:.0f} s budget")
