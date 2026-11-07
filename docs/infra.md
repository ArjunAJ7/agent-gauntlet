# Infra notes (sanitized)

- Gateway: open-source Bifrost, self-hosted locally (`npx -y @maximhq/bifrost`,
  flags: `-app-dir <dir> -port <port> -host 127.0.0.1`).
- Providers are configured with environment-variable key references
  (`env.MY_PROVIDER_KEY`) so no credential ever lands in this repo.
- A Bifrost **virtual key** (governance plugin) scopes benchmark traffic and
  gives per-key budgets/rate limits for free; the runner passes it via the
  `x-bf-vk` header from `BIFROST_VK`.
- Development upstream: Cloudflare Workers AI free tier (10,000 neurons/day);
  the runner's `BENCH_DAILY_NEURON_CAP` hard-stops well below that. Account
  billing state is verified before any scaled run; free-tier provider docs
  alone are treated as leads, not evidence.
- Bifrost's own `logs.db` records every call server-side; the report's
  token/latency numbers reconcile against it.

## Provider constraints discovered (Workers AI via Bifrost, Nov 7)
- Assistant tool-call turns must carry content as a string (null is rejected); the agent loop sends "".
- Only single tool-call turns are accepted; parallel calls are trimmed to the first, noted in the trace.
- Snippets are 60-char excerpts by design: full answers require docs_read, which is what makes the
  misleading injector reachable.

## Validation (Nov 7, 24-run matrix: 6 tasks x 2 agents x 2 reps)
- Graders pass negative controls (word-boundary matching; 8+ deliberate bad answers rejected).
- Flaky injector fires real transient errors (1-4/run, seeds vary per rep): skeptic recovers via
  retries (PASS), concise does not (FAIL).
- Misleading injector's stale document was read and believed in 4/4 runs: both agents FAIL.
  Finding: small ReAct agents trust plausible tool output; cross-check prompts do not save them
  when the excerpt no longer carries the answer.
- Outage injector (gateway dies after 2 calls): both agents FAIL mid-investigation with 1 model
  error - the trace shows exactly where each run stood when the provider "went down".
- Clean three-hop: skeptic (reads the doc chain) PASS 2/2; concise (answers from search excerpts)
  FAIL 2/2.
