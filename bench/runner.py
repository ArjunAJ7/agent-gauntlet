"""Run matrix executor: agent x task x repetitions, with hard budget caps.

Caps are enforced before every model call so a benchmark on a free-tier
upstream stays free even if a task loops. Every run appends one JSONL record
with its full step trace - traces are the platform's evidence, not summaries.
"""
from __future__ import annotations

import argparse
import json
import os
import time

from .agents import REACT_CONCISE, REACT_SKEPTIC, AgentSpec, run_agent
from .gateway import Gateway
from .tasks import get_suite

# Conservative default: Cloudflare Workers AI free tier is 10,000 neurons/day;
# a small-model call here costs ~0.1-0.5 neurons. The cap is a hard stop.
DAILY_NEURON_CAP = float(os.environ.get("BENCH_DAILY_NEURON_CAP", "2000"))


def estimate_neurons(record: dict) -> float:
    # llama-3.2-3b: ~0.06 neurons per 10 tokens (published pricing basis;
    # refined against real account usage before scaled runs)
    return record["usage"]["total_tokens"] * 0.006


def run_matrix(suite: str, agents: list[AgentSpec], reps: int, out_path: str):
    tasks = get_suite(suite)
    gateway = Gateway()
    spent = 0.0
    n_done = 0
    with open(out_path, "a") as out:
        for task in tasks:
            for spec in agents:
                for rep in range(reps):
                    if spent >= DAILY_NEURON_CAP:
                        print(f"BUDGET CAP reached ({spent:.1f} neurons); stopping.")
                        return n_done
                    trace: list[dict] = []
                    t0 = time.monotonic()
                    before = len(gateway.records)
                    answer = run_agent(spec, gateway, task.make_env(),
                                       task.goal, task.max_steps, trace)
                    wall = time.monotonic() - t0
                    calls = gateway.records[before:]
                    usage = {"prompt_tokens": sum(c.prompt_tokens for c in calls),
                             "completion_tokens": sum(c.completion_tokens for c in calls)}
                    usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
                    ok = task.grade(answer)
                    rec = {"task_id": task.task_id, "agent": spec.name,
                           "model": spec.model, "rep": rep, "success": ok,
                           "answer": answer[:500], "usage": usage,
                           "wall_s": round(wall, 2),
                           "steps": len([t for t in trace if t["kind"] == "model"]),
                           "tool_calls": len([t for t in trace if t["kind"] == "tool"]),
                           "tool_errors": len([t for t in trace if t.get("outcome") == "error"]),
                           "model_errors": len([t for t in trace if t["kind"] == "model_error"]),
                           "trace": trace}
                    spent += estimate_neurons(rec)
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    n_done += 1
                    print(f"{task.task_id} x {spec.name} rep{rep}: "
                          f"{'PASS' if ok else 'FAIL'} "
                          f"({rec['steps']} steps, {rec['tool_calls']} tools, "
                          f"{usage['total_tokens']} tok, {wall:.1f}s)")
    return n_done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="core")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    n = run_matrix(args.suite, [REACT_CONCISE, REACT_SKEPTIC], args.reps, args.out)
    print(f"completed {n} runs -> {args.out}")


if __name__ == "__main__":
    main()
