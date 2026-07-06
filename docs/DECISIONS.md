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
