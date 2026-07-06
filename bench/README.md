# Benchmark

Persona simulation + baseline-vs-Memora comparison (BUILD_PLAN.md §7 Phase 4).

3 scripted personas × 20 sessions each, run twice: once against a similarity-only
baseline (no memory), once against Memora. Metrics:

- rec relevance (LLM-judged, qwen-max as judge)
- recovery-after-preference-shift (sessions until relevant again after a stated shift)
- tokens per session (cost line for the $40 budget)

Output: `bench/out/report.md` + `bench/out/chart.png`, embedded in the README and demo
video.

## Running

```bash
python run_benchmark.py
```

## Status

Stub — personas and harness land in Phase 4.
