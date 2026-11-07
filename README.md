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

## Disclosure

This project was built with AI assistance (code generation), disclosed per hackathon rules.
