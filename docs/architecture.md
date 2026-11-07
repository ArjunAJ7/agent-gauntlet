# Architecture

```
test agents (bench/agents.py)
      |  OpenAI-compatible chat, all providers through one URL
      v
local Bifrost gateway  ---- per-call metering: tokens, latency, cost
      |
      v
upstream provider (any Bifrost-supported; dev uses a free-tier account)
```

Benchmark-side, agents also call **synthetic tool environments**
(`bench/envs/`): in-process tools with known ground truth. Deterministic
graders (`bench/tasks.py`) check the final answer against that ground truth -
no LLM judging, so results are reproducible and cannot be sweet-talked.

**Failure injection** (`bench/envs/inject.py`) wraps those same synthetic
tools: flaky transient errors, stale/misleading content, and (runner-level)
mid-run provider outage. Injection never leaves the synthetic world: it does
not target real people, accounts, or services, and simulated behavior is
labeled as simulation in every trace and report.

**Runner** (`bench/runner.py`) executes the agent x task x repetition matrix,
enforces a hard daily usage budget and per-task step caps, and appends one
JSONL trace record per run. **Report** (`bench/report.py`) renders a
self-contained HTML comparison table plus per-run trace viewer.
