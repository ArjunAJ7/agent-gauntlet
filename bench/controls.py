"""Reproducible grader controls.

Every task grader must ACCEPT its positive controls (correct answers) and
REJECT its negative controls (deliberately wrong or look-alike answers).
A pass in the benchmark means the answer, not the grader.

Run:  python -m bench.controls      (exit code 1 if any control fails)
"""
from __future__ import annotations

import sys

from .tasks import TASKS

CONTROLS: dict[str, dict[str, list[str]]] = {
    "tickets.priority.open_critical": {
        "accept": [
            "T-104, assigned to meera",
            "The open critical ticket is T-104 (meera).",
        ],
        "reject": [
            "",
            "T-101 meera",            # wrong ticket id
            "T-104 tomas",            # wrong assignee
            "T-103",                  # closed ticket, no assignee
            "T-1045 meera",           # look-alike id; word boundary must not match
            "T-101 is unrelated; the answer is T-104, meera",  # contradicting id named
        ],
    },
    "docs.single_hop.refund_window": {
        "accept": [
            "30 days",
            "The automatic refund limit is 30 days from purchase.",
        ],
        "reject": [
            "",
            "300 days",               # word boundary: \b30\b must not match 300
            "31 days",                # wrong limit
            "30",                     # number without unit
            "within a month",         # paraphrase, not the exact figure
            "manager review",           # wrong path
            "not 30 days, it is 60 days",  # contradiction: wrong alternative named
        ],
    },
    "docs.three_hop.lag_threshold": {
        "accept": [
            "250 messages",
            "Alerts fire when lag exceeds 250.",
        ],
        "reject": [
            "",
            "2500",                   # word boundary: \b250\b must not match 2500
            "2500 messages",
            "25",
            "251",
            "lag exceeds 1250",         # wrong figure
            "I don't know",
            "not 250 but 2500 messages",   # contradiction: wrong alternative named
        ],
    },
    "docs.multi_hop.cron_tz": {
        "accept": [
            "SCHEDULER_TZ, defaulting to UTC",
            "SCHEDULER_TZ; when unset, cron runs in UTC.",
            "Not CRON_TZ - SCHEDULER_TZ, default UTC.",  # explicit negation is honest
        ],
        "reject": [
            "",
            "CRON_TZ, Asia/Kolkata",                    # the misleading document's answer
            "SCHEDULER_TZ defaulting to Asia/Kolkata",  # right variable, wrong default
            "SCHEDULER_TZ",                             # missing the default
            "UTC",                                      # missing the variable
            "CRON_TZ or SCHEDULER_TZ, UTC",             # contradiction: both named, no negation
        ],
    },
}


def gateway_fault_controls() -> tuple[int, int]:
    """Unit controls for the synthetic gateway fault wrappers: a 429 must
    deny the first call and any call inside the retry-after window, and let
    a caller that actually waited through; metering must pass through."""
    import time as _time

    from .gateway import RateLimitGateway, GatewayError

    class FakeInner:
        def __init__(self):
            self.records = []
            self.calls = 0

        def chat(self, model, messages, max_tokens=1024, temperature=0.0, tools=None):
            self.calls += 1
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    gw = RateLimitGateway(FakeInner(), retry_after_s=0.05)
    total = failed = 0

    def check(label, fn, expect_429):
        nonlocal total, failed
        total += 1
        try:
            fn()
            got_429 = False
        except GatewayError as e:
            got_429 = "429" in str(e)
        ok = got_429 == expect_429
        failed += not ok
        print(f"{'ok ' if ok else 'FAIL'}  gateway.ratelimit{'':27s} {label} -> 429={got_429}")

    check("first call denied", lambda: gw.chat("m", []), True)
    check("immediate retry denied", lambda: gw.chat("m", []), True)
    _time.sleep(0.06)
    check("call after window passes", lambda: gw.chat("m", []), False)
    check("later call still passes", lambda: gw.chat("m", []), False)
    total += 1
    if gw.inner.calls != 2 or gw.denials != 2:
        failed += 1
        print(f"FAIL  gateway.ratelimit{'':27s} metering -> inner={gw.inner.calls} denials={gw.denials}")
    else:
        print(f"ok   gateway.ratelimit{'':27s} metering -> inner=2 denials=2")
    return total, failed


def main() -> int:
    by_id = {t.task_id: t for t in TASKS}
    total = failed = 0
    for task_id, groups in CONTROLS.items():
        task = by_id[task_id]
        for kind, answers in groups.items():
            expect = kind == "accept"
            for ans in answers:
                got = task.grade(ans)
                ok = got == expect
                total += 1
                failed += not ok
                mark = "ok " if ok else "FAIL"
                shown = ans if ans else "<empty>"
                print(f"{mark}  {task_id:38s} {kind:6s} {shown!r} -> {got}")
    g_total, g_failed = gateway_fault_controls()
    total += g_total
    failed += g_failed
    print(f"\n{total - failed}/{total} controls behave")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
