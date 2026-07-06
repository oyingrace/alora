# Design decisions

One line per notable decision, newest last. Fuel for the blog-post writeup.

- Monorepo with five separable packages (`apps/api`, `apps/web`, `packages/snippet`,
  `packages/mcp-memory`, `bench`) so the memory layer can be lifted out and
  open-sourced independently of the demo storefront.
- `packages/mcp-memory` gets its own SQLAlchemy models mirroring `apps/api`'s schema
  rather than importing from `apps/api`, keeping it a standalone, mountable component
  against the same Postgres database.
- All Qwen Cloud calls funnel through `apps/api/app/services/qwen.py` as a single
  choke point (retries, timeouts, token logging) — never call the `openai` SDK
  directly from routers or workers.
- `recall`'s ranking starts as a naive confidence/recency sort in Phase 0; cosine
  similarity against the query embedding is deferred to Phase 1 once embeddings are
  wired up, so the budget-enforcement contract can be built and tested first.
- Belief decay half-life is per-category (budget=30d, style/brand=90d, cadence=60d,
  constraint=180d, size=365d) rather than a single global constant, reflecting how
  fast each kind of preference actually goes stale.
- `revise_belief` takes an explicit `action` (create/reinforce/revise/decay) instead
  of inferring it from which arguments were passed — a decay-driven confidence drop
  and a reinforcement bump both just "set confidence", so inference would have
  mislabeled decay as reinforcement in the memory_audit trail.
- The consolidation worker and decay tick read episodes/beliefs via direct DB access
  (apps/api's own SQLAlchemy models) rather than through `recall`, since they're
  system-internal batch jobs (cluster-a-shopper's-recent-episodes,
  sweep-every-belief) and not "the agent answering one query" that rule 1 is
  guarding against — `recall`'s shopper-scoped, budget-capped shape doesn't fit a
  bulk sweep. Every *mutation* from both workers, though, still goes through
  `revise_belief`/`forget`, so memory_audit stays the one complete, audited record
  of what changed, regardless of which code path decided to change it.
- The Qwen choke point (`apps/api/app/services/qwen.py`) is the only place allowed
  to hold Qwen credentials/model IDs, so the consolidation JSON contract
  (`packages/mcp-memory/mcp_memory/consolidation_contract.py`) is pure Pydantic with
  no LLM client of its own — apps/api imports it to validate qwen-max's response
  rather than duplicating the contract in both packages.
- apps/api's MCP client spawns `python -m mcp_memory.server` as a subprocess over
  stdio, so its Docker build context moved from `apps/api/` to the repo root (the
  image needs `packages/mcp-memory` installed alongside its own dependencies).
