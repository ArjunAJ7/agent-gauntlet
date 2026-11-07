"""OpenAI-compatible client for the local Bifrost gateway.

Every model call in a benchmark run flows through here so metering is
uniform: Bifrost returns usage (tokens) per call and logs latency/cost
server-side. No provider SDKs, no direct provider calls from agents.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field


@dataclass
class CallRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    ok: bool
    error: str | None = None


@dataclass
class Gateway:
    base_url: str | None = None
    virtual_key: str | None = None
    timeout_s: int = 120
    records: list[CallRecord] = field(default_factory=list)

    def __post_init__(self):
        self.base_url = (self.base_url or os.environ.get("BIFROST_URL", "http://127.0.0.1:18777")).rstrip("/")
        self.virtual_key = self.virtual_key or os.environ.get("BIFROST_VK", "")

    def chat(self, model: str, messages: list[dict], max_tokens: int = 1024,
             temperature: float = 0.0, tools: list[dict] | None = None) -> dict:
        """One chat completion through Bifrost. Returns the raw response dict.

        Raises GatewayError on transport/API failure so the runner can record
        the call as failed (a failed call is benchmark data, not a crash).
        """
        body = {"model": model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "x-bf-vk": self.virtual_key},
            method="POST")
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                payload = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            self.records.append(CallRecord(model, 0, 0, time.monotonic() - t0, False, f"http {e.code}: {detail}"))
            raise GatewayError(f"http {e.code}: {detail}") from e
        except Exception as e:  # timeouts, connection resets == provider-outage data
            self.records.append(CallRecord(model, 0, 0, time.monotonic() - t0, False, str(e)))
            raise GatewayError(str(e)) from e
        latency = time.monotonic() - t0
        usage = payload.get("usage") or {}
        self.records.append(CallRecord(
            model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
            latency, True))
        return payload

    def totals(self) -> dict:
        ok = [r for r in self.records if r.ok]
        return {
            "calls": len(self.records),
            "failed_calls": len(self.records) - len(ok),
            "prompt_tokens": sum(r.prompt_tokens for r in ok),
            "completion_tokens": sum(r.completion_tokens for r in ok),
            "latency_s": round(sum(r.latency_s for r in ok), 3),
        }


class GatewayError(Exception):
    pass


class OutageGateway:
    """Simulated mid-run provider outage: delegates to a real Gateway for the
    first `after` model calls, then every call fails with GatewayError, as a
    provider outage would surface. Synthetic and local; nothing external is
    touched. Records pass through to the inner gateway for metering.
    """

    def __init__(self, inner: "Gateway", after: int):
        self.inner = inner
        self.after = after
        self.calls = 0

    @property
    def records(self):
        return self.inner.records

    def chat(self, model, messages, max_tokens=1024, temperature=0.0, tools=None):
        self.calls += 1
        if self.calls > self.after:
            raise GatewayError("simulated provider outage: gateway unreachable")
        return self.inner.chat(model, messages, max_tokens=max_tokens,
                               temperature=temperature, tools=tools)
