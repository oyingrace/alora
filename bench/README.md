# Benchmark

Persona simulation + baseline-vs-Memora comparison (BUILD_PLAN.md §7 Phase 4).

Three scripted personas, 20 sessions each, run through both arms:

- **baseline** — no episodes are ever written; every session calls `/recs`
  cold. The closest fair comparison to a similarity-only recommender with no
  memory.
- **memora** — one persistent shopper_id for the whole persona; episodes
  accumulate and consolidation ("sleep cycle") runs at the end of every
  session.

Personas (`personas.py`):

- **Budget Shopper** — consistently wants the cheapest bag, never states a
  budget explicitly. Tests whether memory holds a stable price-sensitivity
  belief.
- **Style Shifter** — browses ornate furniture for 10 sessions, then issues
  an explicit correction toward minimalist for the remaining 10. Tests
  recovery-after-preference-shift.
- **Gift Buyer** — shops for sneakers for themself throughout, with one
  anomalous stroller purchase mid-way explicitly noted as a gift. Tests that
  a single gift purchase never corrupts the shopper's own-preference belief
  (the "stroller problem" from the pitch).

Metrics, per session:

- rec relevance (qwen-max-judged 0..1 score against the persona's current
  ideal preference — see `llm_judge.py`)
- tokens spent (`app.services.qwen.get_token_usage()`)
- sessions-to-recover after the Style Shifter's scripted correction

Output: `bench/out/report.md` + `bench/out/chart.png`, embedded in the README
and demo video.

## Running

Needs apps/api's dependencies on the path (its venv, or `pip install -r
../apps/api/requirements.txt`), plus Postgres + Redis up and migrated
(`make migrate`).

```bash
cd bench
python run_benchmark.py                  # real Qwen Cloud calls — needs QWEN_API_KEY
python run_benchmark.py --fake           # offline, deterministic stand-in (see fake_qwen.py)
python run_benchmark.py --max-sessions 3 # smoke test, fewer sessions per persona
```

## Status

Done. `--fake` mode (no QWEN_API_KEY needed) is verified to run end-to-end
and produce a real baseline/memora gap; the real-API numbers for the
README/video still need a run with a live `QWEN_API_KEY`.
