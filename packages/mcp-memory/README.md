# memora-mcp-memory

MCP server exposing Memora's memory layer as four tools:

- `recall(store_id, shopper_id, query, budget_tokens=1500)` — hybrid-ranked beliefs +
  recent episode summaries, greedy-packed into a hard token budget.
- `write_episode(store_id, shopper_id, session_id, kind, payload)` — records a raw
  behavioral event (episodic memory).
- `revise_belief(belief_id, evidence_episode_ids, new_statement=None, new_confidence=None, reason)`
  — mutates a belief and writes a `memory_audit` row with a human-readable reason.
- `forget(belief_id, reason)` — marks a belief deprecated (soft delete) and audits it.

**Why this is its own package:** the agent runtime (`apps/api`) never queries the
database for memory directly — see CLAUDE.md architecture rule 1. Every memory read or
write goes through these four tools, which is also what enforces the `budget_tokens`
limit at the tool boundary instead of leaving it to whichever caller remembers to. That
same boundary is what makes this package mountable by any agent, not just Memora's —
the "reusable memory layer" story for judges and for open-source adoption.

## Running

```bash
pip install -e .
python -m mcp_memory.server        # stdio transport, for local agent-loop dev
```

## Status

Phase 0 scaffold: tool signatures, input/output Pydantic contracts, and DB wiring are
in place; ranking/packing logic, consolidation, and decay land in Phase 1–2 per
`BUILD_PLAN.md` §7.
