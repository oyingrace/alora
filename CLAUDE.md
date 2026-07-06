# CLAUDE.md — Memora

Drop-in memory layer + shopping agent for e-commerce. Hackathon sprint (Qwen Cloud
Global AI Hackathon, Track 1: MemoryAgent). Deadline-driven: prefer working and simple
over clever. Read `BUILD_PLAN.md` for full architecture and phase plan before large tasks.

## Repo layout

```
apps/api/        FastAPI backend (Python 3.12, SQLAlchemy async, alembic)
apps/web/        Next.js 14 — demo storefront + Memory Inspector + merchant stub
packages/snippet/  Vanilla TS widget, Vite build → dist/agent.js (keep <50KB gzipped)
packages/mcp-memory/  MCP server exposing memory tools (recall/write/revise/forget)
bench/           Persona simulation + baseline-vs-memora benchmark
docs/            ARCHITECTURE.md, MEMORY_DESIGN.md, diagrams
deploy/          docker-compose.yml, Caddyfile, ECS setup notes
```

## Commands

- `make dev` — compose up postgres+redis, run api (uvicorn --reload) and web (next dev)
- `make test` — pytest apps/api (focus: consolidation contract, decay math, recall budget)
- `make snippet` — build packages/snippet to dist/agent.js
- `make bench` — run persona benchmark, writes bench/out/report.md + chart.png
- `make deploy` — rsync + compose up on ECS (see deploy/README)

## Qwen Cloud usage (required by hackathon)

- OpenAI SDK with `base_url=https://dashscope-intl.aliyuncs.com/compatible-mode/v1`,
  key in `QWEN_API_KEY`. All model IDs come from env: `MODEL_REASONING` (qwen-max class),
  `MODEL_FAST` (qwen-turbo class), `MODEL_VISION` (qwen-vl-max), `MODEL_EMBED`
  (text-embedding-v3). Never hardcode model names.
- All Qwen calls go through `apps/api/app/services/qwen.py` — single choke point with
  retries (3, exponential backoff), timeouts, and per-call token logging to stdout.
  This file is our "proof of Alibaba Cloud API usage" link for judges: keep it clean.
- Budget is $40 total. Default to MODEL_FAST; MODEL_REASONING only in /chat and the
  consolidation worker. Cache embeddings and VL tags (content-hash keyed).

## Architecture rules (non-negotiable)

1. The agent runtime NEVER queries the database for memory directly. Memory access only
   through the MCP tools in packages/mcp-memory: `recall`, `write_episode`,
   `revise_belief`, `forget`. Enforce the `budget_tokens` limit inside `recall`.
2. Every belief mutation (create/reinforce/revise/deprecate/user-delete) writes a row to
   `memory_audit` with a human-readable reason. The Inspector renders this verbatim.
3. All LLM structured outputs are validated with Pydantic models; on validation failure,
   retry once with the error appended, then fall back gracefully (log + skip, never 500).
4. Graceful degradation: if Qwen API is down, /recs serves cached/similarity-only
   results and /chat returns an honest "memory offline" message. No silent failures.
5. Anonymous shoppers: session memory in Redis with TTL only. Persistence requires the
   explicit opt-in flag from the consent banner. No device fingerprinting anywhere.

## Style

- Python: ruff + type hints everywhere; small modules; no ORM logic in route handlers
  (services layer). TS: strict mode; snippet has zero runtime dependencies.
- Write/update tests when touching: consolidation prompt contract, decay curve,
  recall ranking/packing, autonomy promotion rules. Skip UI tests.
- Conventional commits (feat:, fix:, docs:). Keep PR-sized commits so the repo history
  reads well to judges.
- When adding any notable design decision, append one line to docs/DECISIONS.md
  (fuel for the blog-post prize).

## Current phase

Track progress against BUILD_PLAN.md §7. Update the checkbox list in
docs/PROGRESS.md at the end of each phase.