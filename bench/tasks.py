"""Task suite: each task has a synthetic environment, a goal, and a
deterministic grader. No LLM judging - success is checkable ground truth.
"""
from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Callable

from .envs.docs import DocsStore


@dataclass
class Task:
    task_id: str
    suite: str
    goal: str                       # what the agent is asked to do
    make_env: Callable[[int], object]  # fresh synthetic env per run, takes rep index
    grade: Callable[[str], bool]    # deterministic check on the final answer
    max_steps: int = 12
    outage_after: int | None = None  # if set, the model gateway "goes down" after this many calls


def _docs_single_hop(rep: int = 0) -> DocsStore:
    return DocsStore(docs={
        "refund-policy": "Refunds: requests within 30 days are approved automatically. "
                         "After 30 days a manager review is required.",
        "shipping": "Standard shipping takes 5-7 business days. Express takes 2.",
        "onboarding": "New hires get a laptop on day one and VPN access on day two.",
    })


def _docs_three_hop(rep: int = 0) -> DocsStore:
    return DocsStore(docs={
        "incident-4821": "Incident 4821: elevated 5xx from the checkout API. "
                         "Root cause traced to the payments worker. See runbook-payments-worker.",
        "runbook-payments-worker": "Payments worker runbook: for 5xx spikes, first check "
                                   "the queue consumer lag. Lag config lives in queue-config.",
        "queue-config": "Queue consumer lag is tracked per partition. An alert "
                        "fires when a partition's lag exceeds 250 messages. The "
                        "threshold is set by LAG_ALERT_THRESHOLD.",
        "glossary": "5xx: server-side HTTP errors.",
    })


def _docs_multi_hop(rep: int = 0) -> DocsStore:
    return DocsStore(docs={
        "release-notes-4.2": "Release 4.2 moved cron scheduling from the worker "
                             "service to the scheduler service. See scheduler-config.",
        "scheduler-config": "The scheduler service reads its timezone from "
                            "SCHEDULER_TZ. When SCHEDULER_TZ is unset, cron jobs "
                            "run in UTC.",
        "worker-config": "The worker service reads WORKER_CONCURRENCY, default 4.",
        "changelog-old": "Release 4.1 added the worker service.",
    })


TASKS: list[Task] = [
    Task(
        task_id="docs.single_hop.refund_window",
        suite="core",
        goal="A customer asks: can they still get an automatic refund 20 days after "
             "purchase? Answer with the exact day limit from the document store.",
        make_env=_docs_single_hop,
        grade=lambda ans: bool(re.search(r"\b30\b", ans)) and "day" in ans.lower(),
    ),
    Task(
        task_id="docs.three_hop.lag_threshold",
        suite="core",
        goal="During incident 4821, above how many messages do queue consumer lag "
             "alerts fire? Follow the documents from the incident to the config and "
             "answer with the exact number.",
        make_env=_docs_three_hop,
        grade=lambda ans: bool(re.search(r"\b250\b", ans)),
    ),
    Task(
        task_id="docs.multi_hop.cron_tz",
        suite="core",
        goal="After release 4.2, which environment variable controls the timezone used "
             "for cron scheduling, and what is its default? Use the document store.",
        make_env=_docs_multi_hop,
        grade=lambda ans: "SCHEDULER_TZ" in ans and "UTC" in ans,
    ),
]

# Failure-injection variants wrap the same ground-truth envs; the grader is unchanged,
# so resilience is measured as success-rate delta under stress.
def with_injection(task: Task, mode: str, **kw) -> Task:
    from .envs.inject import FlakyWrapper, MisleadingWrapper
    if mode == "flaky":
        return Task(task.task_id + ".flaky", "resilience", task.goal,
                    lambda rep=0: FlakyWrapper(task.make_env(rep), **{**kw, "seed": kw.get("seed", 0) + rep}), task.grade,
                    task.max_steps + 6)
    if mode == "outage":
        return Task(task.task_id + ".outage", "resilience", task.goal,
                    task.make_env, task.grade, task.max_steps,
                    outage_after=kw.get("after", 2))
    if mode == "misleading":
        stale = {  # known-wrong but plausible content per task
            "docs.multi_hop.cron_tz": "The scheduler service reads its timezone from "
                                      "CRON_TZ. When CRON_TZ is unset, cron jobs run "
                                      "in Asia/Kolkata.",
        }
        doc = {"docs.multi_hop.cron_tz": "scheduler-config"}[task.task_id]
        return Task(task.task_id + ".misleading", "resilience", task.goal,
                    lambda rep=0: MisleadingWrapper(task.make_env(rep), doc, stale[task.task_id]),
                    task.grade, task.max_steps)
    raise ValueError(mode)


def get_suite(name: str) -> list[Task]:
    out = [t for t in TASKS if t.suite == name]
    if name == "core":  # core suite also runs resilience variants of its tasks
        out += [with_injection(TASKS[2], "flaky", fail_rate=0.3, seed=7),
                with_injection(TASKS[2], "misleading"),
                with_injection(TASKS[1], "outage", after=2)]
    return out
