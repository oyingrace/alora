# Architecture

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
│                                                                │
│  /events    → ingest, embed (text-embedding-v3), store        │
│  /chat      → agent runtime (qwen-max + tool loop)            │
│  /memory    → inspector CRUD (list/correct/delete beliefs)    │
│  /recs      → retrieval: beliefs + episodes + catalog rerank  │
│  /catalog   → sync endpoint; qwen-vl-max tags product images  │
│                                                                │
│  MCP server (stdio/SSE) — memory.recall, memory.write,        │
│    memory.revise, memory.forget — the agent runtime consumes  │
│    memory ONLY through these MCP tools                        │
│                                                                │
│  Workers: consolidation (episodes→beliefs), decay tick,       │
│    contradiction detector                                     │
│                                                                │
│  Postgres+pgvector ── Redis (anon sessions, queues)           │
└────────────────────────────────────────────────────────────────┘
```

## Components

| Package | Role |
|---|---|
| `apps/api` | FastAPI backend: ingest, chat agent runtime, recs, catalog sync, workers |
| `apps/web` | Next.js demo storefront, Memory Inspector UI, merchant config stub |
| `packages/snippet` | Zero-dependency vanilla TS widget: catalog reader, event capture, widget UI |
| `packages/mcp-memory` | MCP server — the only path to memory (see rule below) |
| `bench` | Persona simulation + baseline-vs-Memora benchmark |
| `deploy` | Docker Compose stack + Caddy TLS termination, ECS provisioning notes |

## The MCP boundary (non-negotiable)

The agent runtime never queries the database for memory directly. All memory access —
read and write — goes through four MCP tools: `recall(query, budget_tokens)`,
`write_episode(event)`, `revise_belief(id, evidence)`, `forget(id, reason)`. This:

1. Enforces the context budget (`budget_tokens`) at the tool boundary, not by
   convention inside the agent loop.
2. Makes the memory layer a standalone, mountable component any agent runtime can
   consume — not just Memora's `/chat` endpoint.
3. Is a first-class MCP integration, not an internal abstraction dressed up as one.

## Multi-model orchestration

Each Qwen Cloud model is scoped to the job it's cheapest and fastest at:

- `MODEL_REASONING` (qwen-max class) — `/chat` tool loop, consolidation worker
- `MODEL_FAST` (qwen-turbo class) — episode summaries, intent classification, recs rerank
- `MODEL_VISION` (qwen-vl-max) — catalog image tagging at sync time, cached by content hash
- `MODEL_EMBED` (text-embedding-v3) — episode/belief/product embeddings, cached by content hash

All calls funnel through the single choke point `apps/api/app/services/qwen.py`
(retries, timeouts, per-call token logging) — see `.env.example` for the model IDs
each env var controls.

## Data flow: a shopping session

1. Snippet posts events to `/events` as the shopper browses.
2. `/events` embeds + stores an episode, and `qwen-turbo` writes a one-line summary +
   intent classification.
3. Every 15 events (or session end), the consolidation worker clusters episodes and
   calls `qwen-max` to propose belief create/reinforce/revise/deprecate — each
   mutation logged to `memory_audit`.
4. `/chat` and `/recs` call `memory.recall` through the MCP client to get a
   budget-capped context, then respond.
5. Hourly decay tick ages confidence down per belief category's half-life.
6. The Memory Inspector (in `apps/web`) reads `/memory`, renders beliefs + audit trail,
   and lets the shopper correct or delete — which re-runs `/recs` live.

See `docs/MEMORY_DESIGN.md` for the memory lifecycle in detail.
