# Agent Gauntlet

A benchmarking platform for AI **agents**, not just models.

Model benchmarks (MMLU, HumanEval, ...) score a single prompt in isolation. Real agents
fail differently: they compound small errors across steps, misuse tools, burn tokens on
loops, and break when a tool is flaky, a provider dies mid-run, or a tool returns
plausible-but-wrong output. Agent Gauntlet measures *that*.

Built for the Geek Room Global AI Hackathon (Bifrost track), on top of the open-source
[Bifrost](https://github.com/maximhq/bifrost) gateway: every model call in a run goes
through one local gateway, which gives the platform uniform per-call metering
(tokens, latency, cost) across any provider Bifrost supports.

## What it measures

Per agent x task x repetition:

- **Success rate** - deterministic graders, no LLM judging
- **Steps and tool calls** to completion (and where runs loop or stall)
- **Tokens and cost** per successful outcome, via Bifrost metering
- **Wall-clock latency**
- **Resilience** under synthetic failure injection: flaky tools, mid-run provider
  outage, and misleading tool output. Injection runs only inside the platform's own
  synthetic tool environments - never against real people, accounts, or services.

## Layout

- `bench/gateway.py` - OpenAI-compatible client for the local Bifrost gateway
- `bench/envs/` - synthetic tool environments (docs store, ticket tracker) + failure injectors
- `bench/agents.py` - the test agents under benchmark (ReAct variants)
- `bench/tasks.py` - task suite with deterministic graders
- `bench/runner.py` - run matrix executor with hard budget caps, JSONL traces
- `bench/report.py` - static HTML report + per-run trace viewer
- `docs/` - architecture and infra notes

## Quickstart

1. Run a local Bifrost gateway with at least one provider configured (see `docs/infra.md`).
2. `export BIFROST_URL=http://127.0.0.1:18777 BIFROST_VK=<virtual-key>`
3. `python -m bench.runner --suite core --reps 3 --out traces/run.jsonl`
4. `python -m bench.report traces/run.jsonl --out report.html`

The runner refuses to exceed a daily usage budget (`BENCH_DAILY_NEURON_CAP`, default
conservative) and a per-run step cap, so benchmarking a free-tier upstream stays free.

## For judges: evaluate in 5 minutes

No API keys are needed to inspect the evidence: `docs/infra.md` has the full setup,
provider constraints found, and validation notes. To re-run the benchmark yourself:

1. Start any Bifrost gateway with one chat provider (a free-tier key is enough; the
   reference runs used Cloudflare Workers AI free tier).
2. `python -m bench.runner --suite core --reps 2 --out /tmp/run.jsonl` — 28 runs,
   about a minute on the reference setup.
3. `python -m bench.report /tmp/run.jsonl --out report.html` and open it: per-task
   pass rates, token/step/latency distributions, and a trace viewer showing every
   model turn and tool call, including injected faults.

Grader behavior is checkable without any provider: every task ships negative
controls (deliberately wrong answers the grader must reject) in the test notes in
`bench/tasks.py`.

## Reference results (validated)

56-run matrix: 7 tasks x 2 agents x 4 reps, Cloudflare Workers AI free tier via local
Bifrost, 2026-11-08. Agents: `react-concise` (minimal prompt) and `react-skeptic`
(instructed to verify tool output and retry failed calls).

| Task | concise | skeptic | What it shows |
| --- | --- | --- | --- |
| docs.single_hop.refund_window | 4/4 | 4/4 | baseline retrieval |
| tickets.priority.open_critical | 4/4 | 4/4 | second env, list+read chain |
| docs.multi_hop.cron_tz | 4/4 | 4/4 | two-document join |
| docs.three_hop.lag_threshold | 3/4 | 4/4 | concise answers from excerpts without reading; skeptic reads the chain |
| docs.multi_hop.cron_tz.flaky | 2/4 | 3/4 | transient tool errors; retries recover most but not all |
| docs.multi_hop.cron_tz.misleading | 0/4 | 0/4 | a stale-but-plausible document fools both agents every time |
| docs.three_hop.lag_threshold.outage | 0/4 | 0/4 | simulated gateway termination mid-run; trace shows exactly where each run stood |

Token cost: skeptic used ~45% more tokens than concise for the same clean-task
outcomes. Findings that only an agent-level benchmark surfaces: small agents trust
tool output even when flagged stale, and retry behavior — not reasoning — is what
separates agents under flaky tools. Injection is synthetic and labeled: injectors
run inside the platform's own environments, proven to activate (fault counts in
each trace), and graders reject deliberate bad answers (negative controls).

## Disclosure

This project was built with AI assistance (code generation), disclosed per hackathon rules.
