"""Estimated-cost helper: published list prices x recorded token usage.

Estimates only - never actual bills. Unknown models or missing input/output
usage produce None (rendered "unavailable"), never zero.
"""
from __future__ import annotations

import json
import os

_PRICING_PATH = os.path.join(os.path.dirname(__file__), "pricing.json")


def load_pricing(path: str = _PRICING_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def estimate_cost_usd(model: str, prompt_tokens, completion_tokens,
                      pricing: dict | None = None) -> float | None:
    """List-price estimate for one run, or None when it cannot be computed."""
    if pricing is None:
        pricing = load_pricing()
    rates = pricing.get("models", {}).get(model)
    if rates is None:
        return None
    if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
        return None
    return (prompt_tokens * rates["input_usd_per_mtok"]
            + completion_tokens * rates["output_usd_per_mtok"]) / 1_000_000


def estimate_run(run: dict, pricing: dict | None = None) -> float | None:
    usage = run.get("usage") or {}
    return estimate_cost_usd(run.get("model"), usage.get("prompt_tokens"),
                             usage.get("completion_tokens"), pricing)


def total(runs: list[dict], pricing: dict | None = None) -> tuple[float, int] | None:
    """(total_usd, n_runs) when every run is estimable, else None."""
    vals = [estimate_run(r, pricing) for r in runs]
    if any(v is None for v in vals):
        return None
    return sum(vals), len(vals)


def _selftest() -> None:
    p = load_pricing()
    # formula: 1M input + 1M output on the reference model = 0.051 + 0.335
    v = estimate_cost_usd("@cf/meta/llama-3.2-3b-instruct", 1_000_000, 1_000_000, p)
    assert v is not None and abs(v - 0.386) < 1e-9, v
    # unknown model -> unavailable
    assert estimate_cost_usd("unknown-model", 100, 100, p) is None
    # missing usage -> unavailable (run-level)
    assert estimate_run({"model": "@cf/meta/llama-3.2-3b-instruct", "usage": {}}, p) is None
    assert estimate_run({"model": "@cf/meta/llama-3.2-3b-instruct"}, p) is None
    # partial usage -> unavailable
    assert estimate_run({"model": "@cf/meta/llama-3.2-3b-instruct",
                         "usage": {"prompt_tokens": 10}}, p) is None
    # totals: all-estimable sums; any unavailable -> None
    runs = [{"model": "@cf/meta/llama-3.2-3b-instruct",
             "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}}] * 2
    t = total(runs, p)
    assert t is not None and abs(t[0] - 0.772) < 1e-9 and t[1] == 2, t
    assert total(runs + [{"model": "unknown-model",
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1}}], p) is None
    # report alignment: header count == cell count on every row; values and
    # unavailable both visible in the emitted HTML
    import re
    from . import report as _report
    sample = [
        {"agent": "a", "task_id": "t1", "rep": 0, "success": True, "answer": "x",
         "trace": [], "steps": 1, "tool_calls": 1, "tool_errors": 0, "wall_s": 1.0,
         "model": "@cf/meta/llama-3.2-3b-instruct",
         "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
                   "total_tokens": 2_000_000}},
        {"agent": "a", "task_id": "t2", "rep": 0, "success": False, "answer": "x",
         "trace": [], "steps": 1, "tool_calls": 0, "tool_errors": 0, "wall_s": 1.0,
         "model": "unknown-model",
         "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}},
    ]
    doc = _report.render(_report.aggregate(sample), sample)
    n_headers = doc.count("<th>")
    body_rows = re.findall(r"<tr>(.*?)</tr>", doc, re.S)[1:]
    assert body_rows, "no body rows rendered"
    for row_html in body_rows:
        assert row_html.count("<td>") == n_headers, (n_headers, row_html.count("<td>"))
    assert "$0.3860" in doc, "known 2M-token estimate missing from HTML"
    assert "unavailable" in doc, "unknown-model row must show unavailable"
    print("pricing self-tests: 11/11 pass")


if __name__ == "__main__":
    _selftest()
