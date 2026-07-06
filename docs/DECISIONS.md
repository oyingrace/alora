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
- The product catalog (`app/models/product.py`) is a normal apps/api table with
  direct DB access, not routed through the MCP tools — architecture rule 1 is about
  the memory tables (episodes/beliefs), and products aren't memory.
- `/chat`'s tool loop only exposes `recall` and `catalog_search`; `create_reorder_proposal`
  is deliberately left out until Phase 4, since a real implementation needs the
  cadence-detection logic that belongs to the autonomy feature, not a stub that
  would just be replaced later.
- `qwen.py` gained `chat_message()` alongside `chat()` — same retry/logging wrapper,
  but returns the raw response message (content + tool_calls) instead of just text,
  so the chat tool loop can drive multi-turn tool calls without a second Qwen client
  or a breaking change to `chat()`'s existing callers (intent, consolidation).
- `MemoryClient` splits `MemoryToolError` (the MCP round-trip succeeded but the tool
  rejected the call, e.g. "belief not found") from `MemoryUnavailableError`
  (transport failure) — building `/memory`'s PATCH/DELETE surfaced that collapsing
  both into one exception meant a 404 case would report as a 503.
- `/memory`'s GET is a direct DB read (all belief statuses + full audit trail) for
  the same reason consolidation/decay are: it's a "show me everything" shape that
  doesn't fit `recall`'s budget-capped, active-only contract. Every write from the
  endpoint (PATCH/DELETE) still goes through `revise_belief`/`forget`.
- `forget`'s `action` param distinguishes `user_delete` (shopper deletes it in the
  Inspector) from `deprecate` (system-driven, e.g. a contradiction found during
  consolidation) — same status transition, different audit story.
- `/recs` builds its search text from `query ∪ recalled belief statements` rather
  than parsing a numeric budget out of belief text — beliefs are free-form natural
  language (e.g. "budget conscious"), not structured fields, so a regex-based
  "extract the dollar amount" would be fragile. Callers pass `max_price`/`category`
  as explicit hard constraints instead; extracting them automatically from budget
  beliefs is a stretch goal, not implemented.
- Anonymous shoppers (consent banner declined) get a completely separate storage
  path (`app/services/session_store.py`, Redis list + TTL) rather than writing to
  Postgres and deleting later — CLAUDE.md rule 5 requires persistence to be
  opt-in, not opt-out-after-the-fact, and skipping Qwen entirely for these events
  also avoids paying for summarization of data that expires with the session.
