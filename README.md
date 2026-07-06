# Memora

**The memory layer for e-commerce.** A drop-in shopping agent, installable on any store
with one script tag, that remembers shoppers transparently — and forgets on purpose.

Built for the Global AI Hackathon Series with Qwen Cloud — Track 1: MemoryAgent.

## The problem

Recommenders have two failures: they can't forget (buy one baby-shower gift, see
strollers for six months) and they're a black box (you can't see or correct what they
believe about you). Memora builds *stated, inspectable beliefs* about each shopper,
asks before memorizing anomalies, decays stale preferences, revises beliefs when
behavior contradicts them, and earns graduated autonomy for actions like reorders —
all visible and editable in a Memory Inspector.

## Architecture

```
┌─────────────── Merchant site (demo storefront) ───────────────┐
│  <script src=".../agent.js" data-store-id="demo">             │
│   ├─ catalog reader (schema.org JSON-LD parse on page load)   │
│   ├─ event capture (search, view, dwell, add-to-cart, buy)    │
│   └─ widget UI (chat panel, recs rail, Memory Inspector)      │
└───────────────────────────┬───────────────────────────────────┘
                            │ HTTPS (first-party events API)
┌───────────────────────────▼───────────────────────────────────┐
│  FastAPI backend (Alibaba Cloud ECS, Docker Compose)          │
│  /events /chat /memory /recs /catalog                          │
│  MCP server — recall / write_episode / revise_belief / forget  │
│  Workers — consolidation, decay tick, contradiction detector    │
│  Postgres+pgvector ── Redis                                    │
└──────────────────────────────────────────────────────────────┘
```

Full design: [`BUILD_PLAN.md`](./BUILD_PLAN.md), [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md),
[`docs/MEMORY_DESIGN.md`](./docs/MEMORY_DESIGN.md).

**Non-negotiable rule:** the agent runtime never queries the database for memory
directly — only through the MCP tools in [`packages/mcp-memory`](./packages/mcp-memory).
That's what makes the memory layer a reusable, open-sourceable component and enforces
the context budget at the tool boundary.

## Repo layout

```
apps/api/           FastAPI backend (Python 3.12, SQLAlchemy async, alembic)
apps/web/            Next.js 14 — demo storefront + Memory Inspector + merchant stub
packages/snippet/    Vanilla TS widget, Vite build → dist/agent.js (<50KB gzipped)
packages/mcp-memory/ MCP server exposing memory tools (recall/write/revise/forget)
bench/               Persona simulation + baseline-vs-memora benchmark
docs/                ARCHITECTURE.md, MEMORY_DESIGN.md, diagrams
deploy/              docker-compose.yml, Caddyfile, ECS setup notes
```

## Quickstart

```bash
cp .env.example .env   # fill in QWEN_API_KEY
make dev               # postgres+redis via compose, api + web locally
```

- API: http://localhost:8000 (docs at `/docs`)
- Web: http://localhost:3000

## Qwen Cloud usage

OpenAI-compatible endpoint, model IDs from env only (`MODEL_REASONING`, `MODEL_FAST`,
`MODEL_VISION`, `MODEL_EMBED`). Every call to Qwen goes through the single choke point
[`apps/api/app/services/qwen.py`](./apps/api/app/services/qwen.py) — retries, timeouts,
per-call token logging.

## Deployment

Deployed on Alibaba Cloud ECS via Docker Compose + Caddy (TLS). See
[`deploy/README.md`](./deploy/README.md).

## Status

Tracking against [`BUILD_PLAN.md`](./BUILD_PLAN.md) §7. Live checklist:
[`docs/PROGRESS.md`](./docs/PROGRESS.md).

## License

MIT — see [`LICENSE`](./LICENSE).
