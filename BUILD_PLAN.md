# Memora — Build Plan

**The memory layer for e-commerce.** A drop-in shopping agent, installable on any store
with one script tag, that remembers shoppers transparently — and forgets on purpose.

- **Hackathon:** Global AI Hackathon Series with Qwen Cloud (Devpost)
- **Tracks:** Track 1 (MemoryAgent) — primary. Track 4 (Autopilot Agent) — secondary framing.
- **Deadline:** July 8, 2026. This plan is scoped as a 48-hour sprint.
- **License:** MIT (required: repo must be public + open source with visible license)

---

## 1. One-paragraph pitch

Every recommender system has two famous failures: it can't forget (buy one baby-shower
gift, see strollers for six months) and it's a black box (users can't see or correct what
it believes). Memora is a conversational shopping agent embedded in any storefront via a
one-line snippet. It builds *stated, inspectable beliefs* about each shopper from their
behavior, asks clarifying questions before memorizing anomalies ("was that a gift?"),
decays stale preferences over time, revises beliefs when behavior contradicts them, and
earns graduated autonomy for actions like reorders — all with a user-facing Memory
Inspector where any belief can be corrected or deleted, instantly changing
recommendations.

## 2. Hard submission requirements (checklist)

- [ ] Public GitHub repo, MIT LICENSE file visible in About section
- [ ] Backend deployed on Alibaba Cloud (ECS) — separate short screen recording proving it
- [ ] Link to a code file in the repo that calls Alibaba Cloud / Qwen Cloud APIs
      (point to `apps/api/app/services/qwen.py`)
- [ ] Architecture diagram (in README + `docs/architecture.png`)
- [ ] ~3 minute public demo video (YouTube)
- [ ] Text description identifying the track (Track 1: MemoryAgent)
- [ ] Optional: blog post about the build (extra $500 prize — write it from CLAUDE.md notes)

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| LLM API | Qwen Cloud, OpenAI-compatible endpoint `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Required; use the `openai` Python SDK with a custom base_url |
| Reasoning model | `qwen-max` (or the strongest Qwen 3.x available in Model Studio) | Agent chat, belief consolidation, conflict resolution |
| Fast model | `qwen-turbo` / `qwen-flash` | Event summarization, intent classification, query rewriting — cheap + low latency |
| Vision model | `qwen-vl-max` | Ingest product images at catalog sync → visual attribute tags ("minimalist", "leather", "warm tones"). Multimodal = judging points |
| Embeddings | `text-embedding-v3` (Qwen Cloud) | Product + episode embeddings |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2 | Fast to build, Claude Code writes it well |
| DB | PostgreSQL 16 + pgvector (single Docker container) | One store for relational + vector; no extra infra |
| Cache/session | Redis 7 | Anonymous session memory (TTL = consent-friendly ephemerality) |
| Background jobs | `arq` (Redis-based) or a simple asyncio scheduler | Consolidation ("sleep cycle"), decay ticks |
| Snippet | Vanilla TypeScript, bundled with Vite to a single `agent.js` (<50KB) | Zero dependencies, drops into any site |
| Storefront + dashboard | Next.js 14 (app router), Tailwind | Demo store, Memory Inspector, merchant config page |
| MCP server | Python `mcp` SDK, exposes memory as tools | Judges explicitly score "MCP integrations" |
| Deployment | Alibaba Cloud ECS (1 instance) + Docker Compose; Caddy for TLS | Cheapest path to "deployed on Alibaba Cloud" proof |

**Model note:** verify exact model IDs in the Qwen Cloud console on day 1 — the hackathon
build session referenced "Qwen 3.7"; use whatever the console lists as the flagship
reasoning model and update `MODEL_REASONING` in `.env`.

## 4. Architecture

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

**The MCP decision (call this out in docs + demo):** the agent runtime does not touch the
database directly. All memory operations go through an MCP server exposing four tools:
`recall(query, budget_tokens)`, `write_episode(event)`, `revise_belief(id, evidence)`,
`forget(id, reason)`. This (a) directly hits the "MCP integrations" judging line, (b)
makes the memory layer a reusable open-source component any agent can mount — your
"scalability / community adoption" story, and (c) enforces the context budget at the
tool boundary.

## 5. Memory system design (Track 1 core)

### 5.1 Data model

```sql
-- Raw behavioral events (episodic memory)
episodes(
  id uuid pk, store_id, shopper_id, session_id,
  kind text,            -- search | view | dwell | add_to_cart | purchase | chat | correction
  payload jsonb,        -- query, product_id, dwell_ms, price, etc.
  summary text,         -- one-line summary written by qwen-turbo
  embedding vector(1024),
  intent text,          -- self | gift | research | unknown  (classified, or asked)
  created_at timestamptz
)

-- Consolidated beliefs (semantic memory)
beliefs(
  id uuid pk, store_id, shopper_id,
  statement text,       -- "Prefers leather over synthetic"
  category text,        -- style | budget | size | brand | cadence | constraint
  confidence float,     -- 0..1
  evidence uuid[],      -- episode ids (provenance)
  status text,          -- active | decaying | deprecated
  last_reinforced_at timestamptz,
  decay_half_life_days int,   -- per-category: budget=30, style=90, size=365
  embedding vector(1024)
)

-- Graduated autonomy per action class
autonomy(
  shopper_id, action_class text,   -- reorder | price_watch | cart_build
  level int,            -- 0 recommend-only, 1 ask-first, 2 auto+notify
  track_record jsonb,   -- approvals, rejections, outcomes
  updated_at timestamptz
)
```

### 5.2 Memory lifecycle

1. **Capture:** snippet posts events → backend embeds + stores episode; `qwen-turbo`
   writes a one-line summary and classifies intent. Low-confidence intent on anomalous
   purchases (embedding distance from shopper centroid > threshold) → queue a
   clarifying question for the widget: "Was this a gift, or should I learn from it?"
2. **Consolidate (sleep cycle):** every N events (N=15) or on session end, worker
   clusters recent episodes and calls `qwen-max` with existing beliefs + new episodes →
   returns belief updates as JSON: create / reinforce (bump confidence, reset decay
   clock) / revise / deprecate, each with cited evidence episode ids. Idempotent;
   log every mutation to a `memory_audit` table (shown in Inspector).
3. **Decay:** hourly tick multiplies confidence by half-life curve; below 0.3 →
   status=decaying (excluded from recall, shown grayed in Inspector); below 0.15 →
   deprecated.
4. **Contradiction:** consolidation prompt explicitly checks new evidence against active
   beliefs; a contradiction triggers revision with a human-readable reason stored in
   audit ("3 recent purchases exceed remembered budget — raising budget belief").
5. **Constrained recall:** `memory.recall` takes a hard `budget_tokens` (default 1,500).
   Ranker: cosine similarity × confidence × recency → greedy-pack top beliefs + top-3
   episode summaries into budget. The budget and what made the cut are displayed live
   in the demo UI (judges see the constraint being enforced).

### 5.3 Recommendations

Hybrid: candidate products by embedding similarity to (query ∪ active beliefs), filtered
by hard constraints (size, budget belief ± tolerance), reranked by a `qwen-turbo` scoring
call. Deleting a belief in the Inspector re-runs recs live — the money demo moment.

## 6. What's IN and OUT (48-hour scope)

**IN:** demo storefront (~24 seeded products with images), snippet with event capture +
schema.org catalog reader, chat agent, recs rail, Memory Inspector (view/correct/delete +
audit log), intent clarification question, consolidation + decay + contradiction, MCP
memory server, one autonomy class (reorder: level 0→1→2), benchmark script with 3
synthetic personas, Alibaba Cloud deployment.

**OUT (roadmap slide only):** Shopify/WooCommerce marketplace apps, merchant dashboard
beyond a config stub, multi-store admin, portable cross-store profiles, payments,
real checkout.

## 7. Build phases (48 hours, in Claude Code)

**Phase 0 — Scaffold + deploy pipeline first (hours 0–3).**
Monorepo scaffold, Docker Compose (api, postgres+pgvector, redis, web, caddy), `.env`
plumbing, Qwen hello-world call through the OpenAI SDK, GitHub repo public with MIT
license, provision ECS instance NOW and get compose stack running on it (deploying at
hour 3 instead of hour 45 removes the biggest risk). Record nothing yet; just make
`docker compose up` work on ECS.

**Phase 1 — Memory core (hours 3–12).**
Schema + migrations (alembic), event ingest endpoint, embedding service, episode
summaries + intent classification, consolidation worker, decay tick, `memory_audit`.
Unit tests for consolidation JSON contract and decay math (judges read code — tests on
the novel logic score "engineering excellence").

**Phase 2 — MCP server + agent runtime (hours 12–20).**
MCP server exposing recall/write/revise/forget with the token budget. Agent runtime:
FastAPI `/chat` → qwen-max tool loop (tools: memory via MCP client, catalog_search,
create_reorder_proposal). Structured outputs everywhere; retries with backoff;
graceful degradation if Qwen API fails (serve cached recs, honest error in chat).

**Phase 3 — Storefront + snippet + Inspector (hours 20–32).**
Next.js storefront with schema.org JSON-LD on product pages; seed catalog (run
`qwen-vl-max` once over images → visual tags, cached). Vite snippet: catalog reader,
event capture, floating widget (chat, recs rail, Inspector tab, consent banner: "Want me
to remember you? / Stay anonymous this session"). Anonymous = Redis session memory with
TTL, explicit opt-in to persist — the ethical answer to device-ID tracking; say so in
the demo.

**Phase 4 — Autonomy + benchmark (hours 32–40).**
Reorder flow: detect consumable repurchase cadence from episodes → propose → approvals
tracked in `autonomy` → after 3 approvals agent proposes promotion to auto+notify →
one-click revoke. Benchmark harness: 3 scripted personas × 20 sessions, baseline
(similarity-only recs, no memory) vs Memora; metrics: rec relevance (LLM-judged),
recovery-after-preference-shift (sessions until relevant again), tokens per session.
Output a chart PNG for README + video.

**Phase 5 — Ship (hours 40–48).**
Final ECS deploy, proof recording (SSH in, `docker ps`, hit the live URL, show ECS
console), architecture diagram, README + `docs/ARCHITECTURE.md` + `docs/MEMORY_DESIGN.md`,
record 3-min video (script in §9), Devpost submission, optional blog post.

## 8. Judging criteria mapping (rehearse these answers)

- **Technical depth 30%:** MCP memory server; multi-model orchestration (max/turbo/VL/
  embeddings each doing the right job); hard context-budget enforcement at the tool
  boundary; hybrid retrieval with confidence×recency ranking; contradiction detection.
- **Innovation & architecture 30%:** decay + provenance + audit (the "forgetting"
  nobody builds); consent-based anonymous memory; graduated autonomy; clean module
  boundaries (snippet / api / memory / mcp / web are separable packages); error
  handling + degradation paths; tests on core logic.
- **Problem value 25%:** universally felt pain (the stroller problem); one-line install
  = real adoption path; the MCP memory layer is independently open-sourceable —
  community story.
- **Presentation 15%:** Memory Inspector IS the visualization of the key logic; live
  budget meter; benchmark chart; architecture docs written as you go.

## 9. Demo video script (3:00)

- 0:00–0:20 — The stroller problem, one sentence. "Recommenders can't forget and can't
  be corrected. Memora is memory done right — installable in one line."
- 0:20–0:45 — Paste the script tag into a bare storefront, refresh, agent comes alive
  and reads the catalog. (The production-ready moment.)
- 0:45–1:30 — Shopper journey: browse, search; agent recalls beliefs in chat; buy an
  anomalous gift → agent ASKS "gift or preference?" → mark gift → recs unaffected.
- 1:30–2:10 — Memory Inspector: beliefs with confidence + evidence; delete one →
  recs change live; show audit log of an automatic revision; show token-budget meter.
- 2:10–2:40 — Autonomy: reorder proposal → approvals → agent earns auto-reorder →
  revoke with one click. Flash the benchmark chart (recovery-after-shift).
- 2:40–3:00 — Architecture slide (MCP memory layer, Qwen models, Alibaba Cloud),
  roadmap (Shopify app, portable profiles), close.

## 10. Risks

- **$40 credit budget:** use qwen-turbo for everything high-frequency; qwen-max only in
  chat + consolidation; cache VL tags and embeddings. Log token spend per call from
  hour 1.
- **Model IDs/availability differ from this plan:** verify in console day 1; keep model
  names in env vars only.
- **ECS friction:** that's why deployment is Phase 0.
- **Scope creep:** anything not in §6 IN-list is cut without discussion.