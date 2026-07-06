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
- [ ] `/chat` agent runtime: qwen-max tool loop via MCP client
- [ ] `catalog_search` and `create_reorder_proposal` tools
- [x] Graceful degradation: Qwen outages caught at every call site (annotation,
      embedding, consolidation) and fall back rather than 500; `/recs`/`/chat`
      honest-error paths still pending (no such endpoints yet)

## Phase 3 — Storefront + snippet + Inspector

- [x] Snippet scaffold: catalog reader, event capture, widget shell + consent banner
      (1.37KB gzipped, zero runtime deps)
- [x] Next.js app router skeleton
- [ ] Seeded catalog (~24 products, schema.org JSON-LD, qwen-vl-max visual tags)
- [ ] Chat panel + recs rail + Memory Inspector UI
- [ ] Anonymous session memory in Redis with TTL; opt-in persistence

## Phase 4 — Autonomy + benchmark

- [ ] Reorder flow: cadence detection → propose → approvals → auto+notify promotion
- [ ] Benchmark harness: 3 personas × 20 sessions, baseline vs Memora
- [ ] Benchmark chart PNG

## Phase 5 — Ship

- [ ] Final ECS deploy + proof recording
- [ ] Architecture diagram image (`docs/architecture.png`)
- [ ] 3-minute demo video
- [ ] Devpost submission
- [ ] Optional blog post
