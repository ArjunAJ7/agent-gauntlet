"""Static HTML report + trace viewer from a JSONL run file.

Single self-contained file (no JS deps) so it can be attached to a submission
or served anywhere. Comparison table aggregates per agent x task; clicking a
row reveals the full step trace for that run.
"""
from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict

from .pricing import estimate_run, load_pricing, total as cost_total


def load(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def aggregate(recs: list[dict]) -> dict:
    agg = defaultdict(list)
    for r in recs:
        agg[(r["agent"], r["task_id"])].append(r)
    pricing = load_pricing()
    rows = []
    for (agent, task), rs in sorted(agg.items()):
        n = len(rs)
        rows.append({
            "agent": agent, "task": task, "n": n,
            "success_rate": sum(r["success"] for r in rs) / n,
            "avg_steps": sum(r["steps"] for r in rs) / n,
            "avg_tools": sum(r["tool_calls"] for r in rs) / n,
            "avg_tokens": sum(r["usage"]["total_tokens"] for r in rs) / n,
            "avg_wall_s": sum(r["wall_s"] for r in rs) / n,
            "tool_errors": sum(r["tool_errors"] for r in rs),
            "est_cost": cost_total(rs, pricing),
        })
    return rows


def render(rows: list[dict], recs: list[dict]) -> str:
    trs = []
    for row in rows:
        trs.append(
            f"<tr><td>{html.escape(row['agent'])}</td><td>{html.escape(row['task'])}</td>"
            f"<td>{row['n']}</td><td>{row['success_rate']:.0%}</td>"
            f"<td>{row['avg_steps']:.1f}</td><td>{row['avg_tools']:.1f}</td>"
            f"<td>{row['avg_tokens']:.0f}</td><td>{row['avg_wall_s']:.1f}s</td>"
            f"<td>{row['tool_errors']}</td>"
            f"<td>{('$' + format(row['est_cost'][0], '.4f')) if row['est_cost'] else 'unavailable'}</td></tr>")
    blocks = []
    for i, r in enumerate(recs):
        steps = "".join(
            f"<li><b>{html.escape(s['kind'])}</b> "
            f"{html.escape(json.dumps({k: v for k, v in s.items() if k not in ('kind', 'step')}))}</li>"
            for s in r["trace"])
        verdict = "PASS" if r["success"] else "FAIL"
        blocks.append(
            f"<details><summary>#{i} {html.escape(r['task_id'])} x "
            f"{html.escape(r['agent'])} rep{r['rep']} - {verdict}</summary>"
            f"<p><b>Answer:</b> {html.escape(r['answer'])}</p><ol>{steps}</ol></details>")
    grand = cost_total(recs)
    grand_txt = f"${grand[0]:.4f} across {grand[1]} runs" if grand else "unavailable (some runs unpriced)"
    pricing = load_pricing()
    cost_note = (f"Estimated cost is computed from published list prices "
                 f"({html.escape(pricing['source'])}, accessed {html.escape(pricing['accessed'])}) "
                 f"applied to recorded token usage. It is an estimate, NOT an actual bill; "
                 f"reference runs paid $0 on the free tier. Rows with unknown models or missing "
                 f"usage show unavailable, never zero. Grand total: {grand_txt}.")
    return f"""<!doctype html><meta charset=utf-8><title>Agent Gauntlet report</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.4rem}}
details{{margin:.6rem 0}}summary{{cursor:pointer}}</style>
<h1>Agent Gauntlet - benchmark report</h1>
<p>{len(recs)} runs. Deterministic grading; resilience rows are synthetic failure-injection variants.</p>
<table><tr><th>Agent</th><th>Task</th><th>Runs</th><th>Success</th><th>Steps</th>
<th>Tool calls</th><th>Tokens</th><th>Wall</th><th>Tool errors</th><th>Est. cost (USD)</th></tr>
{''.join(trs)}</table>
<p><small>{cost_note}</small></p>
<h2>Run traces</h2>{''.join(blocks)}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    recs = load(a.jsonl)
    with open(a.out, "w") as f:
        f.write(render(aggregate(recs), recs))
    print(f"wrote {a.out} from {len(recs)} runs")


if __name__ == "__main__":
    main()
