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
