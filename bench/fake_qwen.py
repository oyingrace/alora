"""Deterministic stand-in for Qwen Cloud calls, used only when QWEN_API_KEY is unset.

Patches `app.services.qwen.chat` / `.embed` directly — the same seam every test in
apps/api/tests mocks through — so the rest of the pipeline (intent annotation,
consolidation, recs reranking, the LLM judge) runs unmodified. This keeps the harness
runnable for free during development; run_benchmark.py skips this shim entirely and
hits the real API whenever QWEN_API_KEY is set, which is what judges will do.

Nothing here is a claim about real Qwen behavior — it's a keyword-overlap heuristic
standing in for it, just detailed enough to make the memory-vs-baseline gap visible.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from types import SimpleNamespace

from app.services import qwen
from app.services.intent import _SYSTEM_PROMPT as _INTENT_PROMPT
from app.services.recs import _RERANK_SYSTEM_PROMPT
from app.workers.consolidation import _SYSTEM_PROMPT as _CONSOLIDATION_PROMPT
from bench.llm_judge import _JUDGE_SYSTEM_PROMPT

_KEYWORDS = [
    "ornate", "minimalist", "budget", "affordable", "premium", "carved", "clean",
    "scandinavian", "canvas", "leather", "stroller", "sneaker", "shoe", "chair",
    "table", "tote", "weekender", "travel", "jog", "gift",
]


def _has_keyword(text: str, kw: str) -> bool:
    """Word-boundary match — plain substring containment would let "ornate" match
    inside "ornamentation", which is the opposite of what it's meant to detect.
    """
    return re.search(rf"\b{re.escape(kw)}\b", text) is not None


def _fake_usage(text: str) -> SimpleNamespace:
    prompt_tokens = max(1, len(text) // 4)
    completion_tokens = max(1, len(text) // 8)
    return SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def _fake_vector(text: str, dim: int = 1024) -> list[float]:
    text_l = text.lower()
    vec = [0.0] * dim
    for i, kw in enumerate(_KEYWORDS):
        if _has_keyword(text_l, kw):
            vec[i % dim] = 1.0
    digest = int(hashlib.sha256(text_l.encode()).hexdigest(), 16)
    noise_idx = len(_KEYWORDS) + (digest % (dim - len(_KEYWORDS)))
    vec[noise_idx] = 0.3
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def fake_embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    vectors = [_fake_vector(t) for t in texts]
    qwen._log_usage("embed", model or "fake-embed", _fake_usage(" ".join(texts)), 0.0)
    return vectors


def _fake_intent_reply(user_content: str) -> str:
    payload = json.loads(user_content)
    note = (payload.get("payload") or {}).get("note", "")
    intent = "gift" if "gift" in note.lower() else "self"
    summary = note or f"{payload.get('kind', 'event')} event"
    return json.dumps({"summary": summary[:80], "intent": intent})


def _fake_rerank_reply(user_content: str) -> str:
    payload = json.loads(user_content)
    candidates = payload.get("candidates", [])
    ranked = sorted(candidates, key=lambda c: c.get("similarity", 0.0), reverse=True)
    rankings = [
        {"name": c["name"], "score": min(1.0, max(0.0, c.get("similarity", 0.0)))} for c in ranked
    ]
    return json.dumps({"rankings": rankings})


def _fake_consolidation_reply(user_content: str) -> str:
    payload = json.loads(user_content)
    episodes = payload.get("recent_episodes", [])
    beliefs = payload.get("existing_beliefs", [])

    # Never let an anomalous gift purchase skew the shopper's own-preference belief.
    own_episodes = [e for e in episodes if e.get("intent") != "gift"]
    if not own_episodes:
        return json.dumps({"mutations": []})

    # `episodes` arrives most-recent-first (see _load_context). Only look at the
    # last couple of episodes to decide the *current* preference — recent behavior
    # should be able to override older behavior within a session or two, the same
    # way a real consolidation call would weigh a fresh, explicit correction over
    # stale evidence sitting deeper in the window.
    recent_episodes = own_episodes[:2]
    keyword_counts: dict[str, int] = {}
    for e in recent_episodes:
        summary_l = (e.get("summary") or "").lower()
        for kw in _KEYWORDS:
            if _has_keyword(summary_l, kw):
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    if not keyword_counts:
        return json.dumps({"mutations": []})

    # Mention every keyword seen (not just the single most frequent one) so the
    # belief statement's own fake embedding overlaps with whichever product the
    # shopper actually viewed, the same way a real consolidation LLM's free-text
    # statement would naturally echo several of the shopper's own words.
    matched_keywords = sorted(keyword_counts, key=lambda k: -keyword_counts[k])
    dominant_kw = matched_keywords[0]
    statement = f"prefers {' '.join(matched_keywords)} products"
    evidence_ids = [e["id"] for e in recent_episodes]

    existing_style_belief = next(
        (b for b in beliefs if b.get("category") in ("style", "budget")), None
    )
    if existing_style_belief is None:
        mutation = {
            "action": "create",
            "statement": statement,
            "category": "budget" if dominant_kw in ("budget", "affordable") else "style",
            "confidence": 0.75,
            "evidence_episode_ids": evidence_ids,
            "reason": (
                f"repeated behavior across {len(recent_episodes)} episodes points to {dominant_kw}"
            ),
        }
    elif statement != existing_style_belief["statement"]:
        mutation = {
            "action": "revise",
            "belief_id": existing_style_belief["id"],
            "statement": statement,
            "confidence": 0.75,
            "evidence_episode_ids": evidence_ids,
            "reason": (
                f"browsing shifted away from '{existing_style_belief['statement']}' "
                f"toward {dominant_kw}"
            ),
        }
    else:
        mutation = {
            "action": "reinforce",
            "belief_id": existing_style_belief["id"],
            "confidence": min(0.95, existing_style_belief.get("confidence", 0.5) + 0.05),
            "evidence_episode_ids": evidence_ids,
            "reason": f"further evidence reinforcing {dominant_kw}",
        }
    return json.dumps({"mutations": [mutation]})


_GENERIC_WORDS = {
    "for", "an", "a", "the", "and", "or", "style", "bag", "bags", "shoe", "shoes",
    "furniture", "adult",
}


def _fake_judge_reply(user_content: str) -> str:
    payload = json.loads(user_content)
    words = {w.strip(".,") for w in payload.get("ideal_description", "").lower().split()}
    ideal_keywords = {w for w in words if w not in _GENERIC_WORDS and len(w) > 3}
    recs = payload.get("recs", [])
    if not recs or not ideal_keywords:
        return json.dumps({"score": 0.0})
    hits = 0
    for r in recs:
        text = f"{r.get('name', '')} {r.get('category', '')} {r.get('description', '')}".lower()
        if any(_has_keyword(text, kw) for kw in ideal_keywords):
            hits += 1
    return json.dumps({"score": round(hits / len(recs), 3)})


async def fake_chat(
    messages: list[dict],
    *,
    model: str | None = None,
    reasoning: bool = False,
    **kwargs,
) -> str:
    system = messages[0]["content"]
    user = messages[-1]["content"]

    if system == _INTENT_PROMPT:
        reply = _fake_intent_reply(user)
    elif system == _RERANK_SYSTEM_PROMPT:
        reply = _fake_rerank_reply(user)
    elif system == _CONSOLIDATION_PROMPT:
        reply = _fake_consolidation_reply(user)
    elif system == _JUDGE_SYSTEM_PROMPT:
        reply = _fake_judge_reply(user)
    else:
        reply = "{}"

    qwen._log_usage("chat", model or "fake-chat", _fake_usage(reply), 0.0)
    return reply


def install() -> None:
    """Monkeypatch the qwen choke point in place. Call once, before anything else."""
    qwen.chat = fake_chat
    qwen.embed = fake_embed
