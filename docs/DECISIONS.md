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
- The widget stays vanilla TS / zero-dependency for the chat/recs/Inspector panel
  too, not just the event-capture shell — the "one script tag, works on any
  storefront" pitch breaks if the panel secretly needs React. `identity.ts`
  centralizes session/shopper id + consent so `events.ts` and `widget.ts` can't
  drift into two different notions of who the shopper is.
- Built `apps/web`'s product pages against the same 8 products as
  `scripts/seed_catalog.py` (duplicated, not fetched from the API) — the
  snippet's catalog reader is supposed to parse schema.org JSON-LD that the
  storefront itself rendered, so the storefront needs to own product data, not
  proxy it from the backend.
- `packages/snippet`'s build output (`dist/agent.js`) is committed to
  `apps/web/public/agent.js` rather than built as part of apps/web's Docker
  image — apps/web's Dockerfile builds from its own directory, and teaching it
  about a sibling package (like apps/api's Dockerfile now does for mcp-memory)
  felt like more complexity than a 4KB checked-in file justifies. `make snippet`
  rebuilds and copies it.
- Found two real bugs only by testing the widget in an actual browser rather
  than trusting unit tests alone: apps/api had no CORS middleware at all (every
  cross-origin request — which is every real embed, by design — failed
  preflight), and `events.ts` never sent `shopper_id` in its POST body despite
  the backend requiring it. Neither surfaced in Python or TypeScript unit
  tests, which only ever called same-origin or mocked the network.
- Graduated autonomy (`app/services/autonomy.py`) reads purchase/reorder
  episodes directly with plain SQL rather than through the MCP `recall` tool —
  architecture rule 1 governs the memory *table* (beliefs/episodes as shopper
  memory), and the `autonomy` table is a normal apps/api table like the
  product catalog, not memory. The reorder episode it writes on approval,
  though, is real episodic memory and does go through `write_episode`.
- The benchmark harness (`bench/`) drives apps/api's actual service functions
  in-process (no HTTP, no separate server process) so it has direct access to
  `qwen.get_token_usage()` for the tokens-per-session metric, and calls
  `consolidate_shopper` once at the end of every scripted session instead of
  relying on `/events`' event-count cadence — deterministic and easier to
  reason about for a benchmark than a fire-and-forget background task. The
  "baseline" arm skips writing episodes entirely rather than just using a
  fresh shopper_id per session: a fresh id with real memory turned on would
  still get one session's worth of belief-informed reranking, which isn't
  "similarity-only, no memory."
- `bench/fake_qwen.py` patches `app.services.qwen.chat`/`.embed` (the same
  seam every apps/api test mocks) with a deterministic keyword-overlap shim so
  the harness is runnable and its mechanics verifiable without a real
  QWEN_API_KEY or spending the token budget on every dev iteration.
  `run_benchmark.py` only reaches for it when no key is configured (or
  `--fake` is passed); real submission numbers come from a real run.
