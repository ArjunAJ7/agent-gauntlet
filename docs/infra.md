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

## Validation (Nov 17, offline)
- Added RateLimitGateway (429 + retry-after window; denied calls record no
  tokens, as with a real provider), Task.ratelimit_after_s, and a
  docs.single_hop.refund_window.ratelimit resilience variant (after_s=2.0).
- Agent specs now carry model_retries / honor_retry_after; react-skeptic
  retries a failed model call once immediately, new react-backoff parses the
  retry-after window and sleeps (capped at 5s). Previously every agent loop
  broke on the first model error.
- Offline scripted-gateway validation: concise FAIL (1 denial, gives up),
  skeptic FAIL (2 denials, immediate retry inside window), backoff PASS
  (1 denial, waits, completes search->read->answer). Outage parity: all
  three still FAIL; skeptic/backoff traces now show the retry attempts.
- Controls extended to 41: five RateLimitGateway unit controls (first call
  denied, in-window retry denied, post-window pass, metering pass-through).

## Local Bifrost recipe (rediscovered Nov 17; survives this note, not the sandbox)
- `npx -y @maximhq/bifrost -app-dir ~/bifrost-app -port 18777 -host 127.0.0.1`
  (v1.6.3; the binary dies when the launching shell exits, so start it in the
  same shell invocation that runs the benchmark).
- ~/bifrost-app/config.json (source_of_truth: config.json): native
  `cloudflare` provider (custom providers may NOT use cloudflare as a base
  type; and the openai base fails key selection because Cloudflare has no
  GET /models, which list_models_failed gates on). Key: value
  env.CF_WORKERS_AI_KEY, models ["*"], cloudflare_key_config.account_id set.
- Governance is mandatory: create a virtual key via
  POST /api/governance/virtual-keys with header X-Bifrost-Setup-Token
  (BIFROST_SETUP_TOKEN env at startup). The VK must have
  allow_all_providers=true and NO provider_configs - a provider_config with
  no key grant restricts the key pool to zero ("no keys found for provider").
- Runner env: BIFROST_URL=http://127.0.0.1:18777, BIFROST_VK=<vk>,
  BENCH_WIRE_MODEL_PREFIX="cloudflare/".

## Validation (Nov 17, real-model smoke, 6 runs)
- Local Bifrost config was wiped overnight; instead of rebuilding it, the
  gateway gained BENCH_AUTH_HEADER (direct-provider mode) and the smoke ran
  against the Cloudflare OpenAI-compatible endpoint directly (usage +
  neurons fields confirmed present; rolled bench token, same scope).
- Ratelimit variant, 1 rep x 3 agents (evidence/smoke-ratelimit-outage-20261117.jsonl):
  concise FAIL (first 429, gives up), skeptic FAIL (immediate retry inside
  the 2s window, second 429), backoff PASS (429 -> waited out the window ->
  docs_search -> docs_read -> correct answer "30 days", 868 tokens, 3.5s
  wall). Matches the offline scripted-gateway predictions exactly.
- Outage variant, 1 rep x 3 agents: concise and skeptic hit the injected
  outage and failed mid-investigation (1-2 model errors) as designed.
  Backoff's run ended at step 1 via the known excerpt-answering failure
  mode (answered from the search snippet without docs_read, wrong value),
  so its outage behavior was not exercised in this smoke; offline scripted
  validation covers outage parity for all three designs.
- Smoke spend: ~3.7k tokens (~120 neurons conservative) against the 10k/day
  free allocation; cap state file recorded the spend as usual.
- Gateway-mediated repeat (same 6 runs, rebuilt local Bifrost per the recipe
  above, evidence/smoke-ratelimit-outage-mediated-20261117.jsonl): identical
  outcomes - ratelimit concise FAIL / skeptic FAIL / backoff PASS (868
  tokens, 2.7s wall through the gateway); outage as before. The Bifrost
  stack remains the default and documented path; BENCH_AUTH_HEADER direct
  mode is a labeled fallback for when the local gateway is unavailable.
