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

## Validation (Nov 16, fresh 56-run matrix: 7 tasks x 2 agents x 4 reps)
- Provider billing state verified live in the Cloudflare dashboard before the
  run: plan "Workers Free" (Active), "No payment method on file" - the account
  cannot be billed; usage metered 0/10k neurons at run start.
- Rolled the bench API token (old secret invalidated); same Account.Workers AI
  scope. Token lives in the vault, referenced as env.CF_WORKERS_AI_KEY in the
  local Bifrost app dir - never in this repo.
- Results reproduced the Nov 7/8 findings on a fresh date: clean tasks PASS
  except concise on three_hop (answers from excerpts, FAIL 4/4); flaky
  injector: skeptic recovers via retries (3/4 PASS) while concise does not
  (2/4); misleading injector: skeptic FAIL 4/4 (believes the stale doc),
  concise 2/4; outage injector: both FAIL mid-investigation with the trace
  showing exactly where the provider "went down".
- Token meter: 100,199 tokens across 56 runs (~3,133 neurons conservative
  estimate including smoke runs, 31% of the 10k/day free allocation).
- Guardrail fix: the daily neuron cap previously reset per invocation, which
  chunked runs (--skip/--limit) defeated. The cap now persists in a dated
  state file (BENCH_CAP_STATE) and fails closed across invocations; it also
  prints prior daily spend at startup.
- Gateway change: BENCH_WIRE_MODEL_PREFIX prefixes the model name on the wire
  for Bifrost provider routing (e.g. "cf-workers-ai/"); benchmark records keep
  the canonical @cf/... model name.
