"""Three scripted shopper personas, each a sequence of sessions (BUILD_PLAN.md §7
Phase 4). Every session is a handful of behavioral events plus one /recs call judged
against `ideal_description` — what a good recommendation list looks like *at that
point in the story*, deliberately worded without the differentiating style/budget
keyword so a plain keyword-matching baseline can't cheat off the query text alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionScript:
    events: list[tuple[str, dict]]
    recs_query: str
    ideal_description: str
    category: str | None = None


@dataclass
class Persona:
    name: str
    sessions: list[SessionScript] = field(default_factory=list)


def _view(note: str) -> tuple[str, dict]:
    return ("view", {"note": note})


def _dwell(note: str) -> tuple[str, dict]:
    return ("dwell", {"note": note})


def budget_shopper() -> Persona:
    """Consistently wants the cheapest option, never states a budget explicitly —
    tests whether memory holds a stable price-sensitivity belief across sessions.
    """
    sessions = []
    for _ in range(20):
        sessions.append(
            SessionScript(
                events=[
                    _view("Looked at the canvas weekender bag, budget-friendly and affordable"),
                    _dwell("Spent a while comparing prices, wants the cheap affordable option"),
                ],
                recs_query="bag",
                ideal_description="an affordable, budget-friendly, cheap bag",
                category="bags",
            )
        )
    return Persona(name="Budget Shopper", sessions=sessions)


def style_shifter() -> Persona:
    """Ornate furniture for 10 sessions, then an explicit correction toward
    minimalist for the remaining 10 — tests recovery-after-preference-shift.
    """
    sessions = []
    for _ in range(10):
        sessions.append(
            SessionScript(
                events=[
                    _view("Browsed the carved walnut accent chair, loves ornate bold detailing"),
                    _dwell("Lingered on the ornate carved chair for a while"),
                ],
                recs_query="furniture",
                ideal_description="ornate, carved, bold-style furniture",
                category="furniture",
            )
        )
    sessions.append(
        SessionScript(
            events=[
                (
                    "correction",
                    {"note": "Actually I want something more minimalist now, not ornate anymore"},
                ),
                _view("Looked at the minimalist oak side table, likes the clean lines"),
            ],
            recs_query="furniture",
            ideal_description="minimalist, clean-lined, Scandinavian style furniture",
            category="furniture",
        )
    )
    for _ in range(9):
        sessions.append(
            SessionScript(
                events=[
                    _view("Browsed the minimalist oak side table again, clean simple lines"),
                    _dwell("Lingered on the minimalist table"),
                ],
                recs_query="furniture",
                ideal_description="minimalist, clean-lined, Scandinavian style furniture",
                category="furniture",
            )
        )
    return Persona(name="Style Shifter", sessions=sessions)


def gift_buyer() -> Persona:
    """Shops for athletic shoes for themself throughout, with one anomalous stroller
    purchase mid-way explicitly noted as a gift — the "stroller problem": a single
    gift purchase must never corrupt the shopper's own-preference belief.
    """
    sessions = []
    for _ in range(9):
        sessions.append(
            SessionScript(
                events=[
                    _view("Looked at minimalist leather sneakers, likes the clean premium look"),
                    _dwell("Compared a couple of minimalist premium sneaker options"),
                ],
                recs_query="shoes",
                ideal_description="minimalist, clean, premium sneakers",
                category="shoes",
            )
        )
    sessions.append(
        SessionScript(
            events=[
                (
                    "purchase",
                    {
                        "product_id": "baby-001",
                        "note": "Buying this stroller as a gift for my sister's new baby",
                    },
                )
            ],
            recs_query="shoes",
            ideal_description="minimalist, clean, premium sneakers",
            category="shoes",
        )
    )
    for _ in range(10):
        sessions.append(
            SessionScript(
                events=[
                    _view("Looked at minimalist leather sneakers again, clean premium finish"),
                    _dwell("Compared minimalist premium sneaker options"),
                ],
                recs_query="shoes",
                ideal_description="minimalist, clean, premium sneakers",
                category="shoes",
            )
        )
    return Persona(name="Gift Buyer", sessions=sessions)


def all_personas() -> list[Persona]:
    return [budget_shopper(), style_shifter(), gift_buyer()]
