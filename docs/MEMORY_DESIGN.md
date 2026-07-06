# Memory design

## Data model

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

-- Every belief mutation, human-readable, rendered verbatim in the Inspector
memory_audit(
  id uuid pk, belief_id, store_id, shopper_id,
  action text,          -- create | reinforce | revise | deprecate | user_delete
  reason text,
  created_at timestamptz
)
```

Implemented in `apps/api/app/models/` and mirrored (read/write scoped) in
`packages/mcp-memory/mcp_memory/models.py`, migrated by
`apps/api/alembic/versions/0001_initial_schema.py`.

## Lifecycle

1. **Capture.** Snippet posts events → `/events` embeds + stores an episode;
   `qwen-turbo` writes a one-line summary and classifies intent. Anomalous purchases
   (embedding distance from the shopper's centroid above a threshold) with low-confidence
   intent queue a clarifying question in the widget: "Was that a gift, or should I learn
   from it?"
2. **Consolidate (sleep cycle).** Every `CONSOLIDATION_EVERY_N_EVENTS` events (default
   15) or on session end, a worker clusters recent episodes and calls `qwen-max` with
   existing beliefs + new episodes. Response is validated against a Pydantic contract:
   create / reinforce (bump confidence, reset decay clock) / revise / deprecate, each
   citing evidence episode ids. Idempotent; every mutation writes a `memory_audit` row.
3. **Decay.** Hourly tick multiplies confidence by a half-life curve keyed on
   `decay_half_life_days` (budget=30, style=90, brand=90, cadence=60, constraint=180,
   size=365). Below 0.3 → `status=decaying` (excluded from recall, shown grayed in the
   Inspector); below 0.15 → `deprecated`.
4. **Contradiction.** The consolidation prompt explicitly checks new evidence against
   active beliefs. A contradiction triggers a revision with a human-readable reason in
   `memory_audit` (e.g. "3 recent purchases exceed remembered budget — raising budget
   belief").
5. **Constrained recall.** `memory.recall(query, budget_tokens)` (default 1,500) ranks
   by cosine similarity × confidence × recency and greedy-packs top beliefs + top-3
   episode summaries into the budget. What made the cut, and the budget used, is shown
   live in the demo UI.

## Recommendations

Hybrid retrieval: candidate products by embedding similarity to (query ∪ active
beliefs), filtered by hard constraints (size, budget belief ± tolerance), reranked by a
`qwen-turbo` scoring call. Deleting a belief in the Inspector re-runs `/recs` live —
the money demo moment.

## Autonomy (reorder, one action class in scope)

Detect consumable repurchase cadence from episodes → propose reorder → approvals
tracked in `autonomy.track_record`. After `PROMOTION_APPROVALS_REQUIRED` (3) approvals,
the agent proposes promotion from level 1 (ask-first) to level 2 (auto+notify).
One-click revoke back to level 0 at any time.

## Status

Phase 0 scaffold: schema + migration + MCP tool contracts are in place with a naive
recency/confidence sort in `recall`. Semantic ranking, consolidation worker, decay
tick, and contradiction detection are Phase 1–2 work — see `BUILD_PLAN.md` §7 and
`docs/PROGRESS.md`.
