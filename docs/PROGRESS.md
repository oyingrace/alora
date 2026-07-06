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

- [x] Snippet: catalog reader, event capture, consent banner, and now a full
      floating panel — chat tab, "For you" recs tab, Memory Inspector tab
      (view/correct-ready/delete + audit log). Still zero runtime deps, 3.84KB
      gzipped (well under the 50KB budget)
- [x] `identity.ts`: single source of truth for session/shopper id + consent —
      `shopper_id` is only ever persistent (localStorage) once opted in,
      otherwise it's the ephemeral session id, so nothing outlives the session
- [x] Next.js storefront: 8 seeded products (mirroring the backend seed),
      listing page + detail pages with schema.org JSON-LD and a
      `data-memora-add-to-cart` button for the snippet's event capture; the
      snippet script tag is wired into the root layout
- [x] Product catalog schema + sync endpoint (`app/models/product.py`,
      `POST /catalog`) — 8-product seed script (`scripts/seed_catalog.py`), real
      qwen-vl-max tagging over real images still pending (needs QWEN_API_KEY)
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
- [x] Verified end-to-end in a real browser (Playwright): consent banner →
      launcher → panel → Inspector shows a seeded belief → delete → status
      flips to `deprecated`, audit row appears, delete button disappears. Found
      and fixed two real bugs this way: missing CORS middleware (every
      cross-origin widget request was failing preflight) and the snippet never
      sending `shopper_id` to `/events` at all

## Phase 4 — Autonomy + benchmark

- [x] Reorder flow: cadence detection (`detect_reorder_candidates`) → propose →
      approvals/rejections tracked per shopper → promotes ask-first to
      auto+notify after 3 approvals → one-click revoke back to recommend-only
      (`app/services/autonomy.py`, `/autonomy` endpoints)
- [x] `create_reorder_proposal` /chat tool: declines for anonymous shoppers,
      asks for approval at ask-first, auto-reorders (writing a real
      `KIND_REORDER` episode) at auto+notify
- [x] Autonomy status + one-click "turn off" revoke button in the snippet's
      Memory Inspector
- [x] Benchmark harness (`bench/`): 3 scripted personas (Budget Shopper, Style
      Shifter, Gift Buyer) × 20 sessions each, run through both a baseline arm
      (no episodes written at all — true "similarity-only, no memory") and a
      Memora arm (one persistent shopper_id, consolidation runs every
      session). Metrics: qwen-max-judged rec relevance, tokens/session
      (`qwen.get_token_usage()`), and sessions-to-recover after Style
      Shifter's scripted preference correction. Drives apps/api's services
      in-process — no HTTP, no separate server
- [x] `bench/fake_qwen.py`: deterministic offline stand-in for Qwen calls
      (same seam apps/api's own tests mock), so the harness runs and is
      verifiable without a QWEN_API_KEY; `run_benchmark.py` only uses it when
      no real key is configured or `--fake` is passed
- [x] `bench/report.py` writes `bench/out/report.md` + `bench/out/chart.png`
      (matplotlib, one subplot per persona)

## Phase 5 — Ship

- [ ] Final ECS deploy + proof recording
- [ ] Architecture diagram image (`docs/architecture.png`)
- [ ] 3-minute demo video
- [ ] Devpost submission
- [ ] Optional blog post
