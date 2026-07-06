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
- [ ] Event ingest endpoint (`/events`)
- [ ] Embedding service wired to `qwen.py`
- [ ] Episode summaries + intent classification (qwen-turbo)
- [ ] Consolidation worker
- [ ] Decay tick
- [ ] Unit tests: consolidation JSON contract, decay math

## Phase 2 — MCP server + agent runtime

- [x] MCP server scaffold: `recall` / `write_episode` / `revise_belief` / `forget`
      with hard `budget_tokens` enforcement (naive recency/confidence ranking)
- [ ] Semantic ranking in `recall` (cosine similarity × confidence × recency)
- [ ] `/chat` agent runtime: qwen-max tool loop via MCP client
- [ ] `catalog_search` and `create_reorder_proposal` tools
- [ ] Graceful degradation path (Qwen API down → cached recs, honest chat error)

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
