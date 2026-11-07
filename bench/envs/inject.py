"""Failure injectors: wrap a synthetic environment to stress agent resilience.

Three modes, all deterministic under a seed, all confined to synthetic tools:
- flaky: tool calls randomly fail with transient errors
- misleading: one tool returns plausible-but-wrong content (the doc exists but
  its answer was overwritten with a stale value)
- outage: the model gateway itself is cut after N calls (simulated provider
  failure mid-run) - implemented by the runner swapping the gateway, not here.
"""
from __future__ import annotations

import random


class FlakyWrapper:
    """Randomly fail tool calls with a transient-looking error."""

    def __init__(self, env, fail_rate: float = 0.3, seed: int = 0):
        self.env = env
        self.fail_rate = fail_rate
        self.rng = random.Random(seed)
        self.failures = 0

    def tools_schema(self):
        return self.env.tools_schema()

    def dispatch(self, name, args):
        if self.rng.random() < self.fail_rate:
            self.failures += 1
            raise TransientToolError("temporary error, please retry")
        return self.env.dispatch(name, args)


class MisleadingWrapper:
    """One named document's content is replaced with a stale, wrong answer."""

    def __init__(self, env, doc_id: str, stale_text: str):
        self.env = env
        self.doc_id = doc_id
        self.stale_text = stale_text

    def tools_schema(self):
        return self.env.tools_schema()

    def dispatch(self, name, args):
        if name == "docs_read" and args.get("doc_id") == self.doc_id:
            return self.stale_text
        return self.env.dispatch(name, args)


class TransientToolError(Exception):
    pass
