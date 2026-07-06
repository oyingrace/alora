# Progress

Tracked against `BUILD_PLAN.md` §7. Update at the end of each phase.

## Phase 0 — Scaffold + deploy pipeline first

- [x] Monorepo scaffold (`apps/api`, `apps/web`, `packages/snippet`,
      `packages/mcp-memory`, `bench`, `docs`, `deploy`)
- [x] Docker Compose (api, postgres+pgvector, redis, web, caddy)
- [x] `.env` plumbing (`.env.example`)
- [x] Qwen choke point written (`apps/api/app/services/qwen.py`) — hello-world call
      still needs a real `QWEN_API_KEY` to exercise against the live endpoint
- [x] MIT license, public repo assumed (verify repo visibility + About section)
- [ ] ECS instance provisioned + `docker compose up` verified running on it

## Phase 1 — Memory core

- [x] Schema + initial migration (episodes, beliefs, autonomy, memory_audit)
- [x] Event ingest endpoint (`POST /events`) — annotate (qwen-turbo) → embed (cached)
      → `write_episode` via MCP client; gift-clarification flag on anomalous purchases
- [x] Embedding service wired to `qwen.py` (Redis, content-hash keyed cache)
- [x] Episode summaries + intent classification (qwen-turbo, validated, retry-once,
      graceful fallback)
- [x] Consolidation worker (`app/workers/consolidation.py`) — triggers every
      `CONSOLIDATION_EVERY_N_EVENTS`, qwen-max proposes create/reinforce/revise/
      deprecate mutations, applied via MCP tools
- [x] Decay tick (`app/workers/decay.py`) — hourly asyncio loop, per-category
      half-life math, audited as `action="decay"`
- [x] Unit tests: consolidation JSON contract, decay math, ranking, MCP server tools,
      event ingest, embedding cache (48 tests total across both packages)

## Phase 2 — MCP server + agent runtime

- [x] MCP server: `recall` / `write_episode` / `revise_belief` / `forget` with hard
      `budget_tokens` enforcement
- [x] Semantic ranking in `recall` (cosine similarity × confidence × recency, falls
      back to confidence/recency when no query embedding is given)
- [x] MCP client wired into apps/api (persistent stdio session via FastAPI lifespan)
      — the sole path apps/api uses to touch memory
- [x] `/chat` agent runtime (`app/services/chat_agent.py`): qwen-max tool loop
      (`recall`, `catalog_search`), bounded iterations, honest "memory offline"
      degradation, records the exchange as a `chat` episode on success
- [x] `catalog_search` tool + backing `products` table (migration 0002), embedded
      and cosine-ranked; `POST /catalog` sync endpoint with qwen-vl-max visual
      tagging hook (best-effort, cached by image URL)
- [ ] `create_reorder_proposal` tool — deferred to Phase 4, depends on the
      `autonomy` cadence-detection logic that belongs there
- [x] Graceful degradation: Qwen outages caught at every call site (annotation,
      embedding, consolidation, chat, recs) and fall back rather than 500 —
      `/chat` returns an honest "memory offline" message, `/recs` serves the
      similarity-only ordering and reports `degraded: true`

## Phase 3 — Storefront + snippet + Inspector

- [x] Snippet scaffold: catalog reader, event capture, widget shell + consent banner
      (1.37KB gzipped, zero runtime deps)
- [x] Next.js app router skeleton
- [x] Product catalog schema + sync endpoint (`app/models/product.py`,
      `POST /catalog`) — 8-product seed script (`scripts/seed_catalog.py`), real
      storefront JSON-LD wiring and qwen-vl-max tagging over real images still
      pending (needs a live storefront + QWEN_API_KEY)
- [x] `/memory` endpoint (Inspector backend): GET lists every belief (including
      decaying/deprecated) + full audit trail; PATCH corrects a belief; DELETE
      removes one, audited distinctly as `user_delete` vs system `deprecate`
- [x] `/recs` endpoint: `recall`-informed embedding search over the catalog,
      reranked by qwen-turbo, hard `max_price`/`category` filters — deleting a
      belief in the Inspector changes what the next `/recs` call returns
- [x] Anonymous vs persistent consent handling (architecture rule 5): `/events`
      and `/chat` take a `persist` flag from the consent banner; declining skips
      Postgres and qwen entirely, landing in a TTL'd Redis session log instead
      (`app/services/session_store.py`)
- [ ] Chat panel + recs rail + Memory Inspector UI (frontend still pending —
      backend endpoints above are ready for it)

## Phase 4 — Autonomy + benchmark

- [ ] Reorder flow: cadence detection → propose → approvals → auto+notify promotion
- [ ] `create_reorder_proposal` /chat tool (see Phase 2 note above)
- [ ] Benchmark harness: 3 personas × 20 sessions, baseline vs Memora
- [ ] Benchmark chart PNG

## Phase 5 — Ship

- [ ] Final ECS deploy + proof recording
- [ ] Architecture diagram image (`docs/architecture.png`)
- [ ] 3-minute demo video
- [ ] Devpost submission
- [ ] Optional blog post
