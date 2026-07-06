#!/usr/bin/env python3
"""Persona benchmark harness: baseline (similarity-only, no memory) vs Memora.

3 scripted personas x 20 sessions each, run through both arms (BUILD_PLAN.md §7
Phase 4). Metrics: rec relevance (LLM-judged), recovery-after-preference-shift
(Style Shifter persona only), tokens per session. Writes bench/out/report.md and
bench/out/chart.png.

Usage:
    python run_benchmark.py                  # real Qwen Cloud calls (needs QWEN_API_KEY)
    python run_benchmark.py --fake            # deterministic offline stand-in (see fake_qwen.py)
    python run_benchmark.py --max-sessions 3  # smoke test, fewer sessions per persona
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).parent
API_DIR = BENCH_DIR.parent / "apps" / "api"
OUT_DIR = BENCH_DIR / "out"

sys.path.insert(0, str(BENCH_DIR.parent))  # so `import bench.xyz` resolves
sys.path.insert(0, str(API_DIR))  # so `import app.xyz` resolves, matching scripts/seed_catalog.py

STORE_ID = "demo"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", action="store_true", help="force the offline fake-Qwen shim")
    parser.add_argument(
        "--max-sessions", type=int, default=None, help="truncate each persona's session count"
    )
    return parser.parse_args()


async def _amain(args: argparse.Namespace) -> None:
    from app.core.config import get_settings
    from app.services.memory_client import memory_client

    settings = get_settings()
    use_fake = args.fake or not settings.qwen_api_key
    if use_fake:
        from bench import fake_qwen

        fake_qwen.install()
        print("QWEN_API_KEY not set (or --fake passed) — using the offline fake-Qwen shim.")
    else:
        print("Using real Qwen Cloud calls.")

    from bench.harness import run_persona_arm, sessions_to_recover
    from bench.personas import all_personas
    from bench.report import render_chart, render_report
    from scripts.seed_catalog import seed as seed_catalog

    await memory_client.connect()
    try:
        await seed_catalog()

        personas = all_personas()
        if args.max_sessions:
            for persona in personas:
                persona.sessions = persona.sessions[: args.max_sessions]

        results = []
        for persona in personas:
            print(f"running persona: {persona.name} ({len(persona.sessions)} sessions/arm)")
            baseline = await run_persona_arm(STORE_ID, persona, persistent=False)
            memora = await run_persona_arm(STORE_ID, persona, persistent=True)
            recovery = None
            if persona.name == "Style Shifter":
                shift_index = len(persona.sessions) - 9 - 1  # the correction-event session
                recovery = {
                    "baseline": sessions_to_recover(baseline.sessions, shift_index),
                    "memora": sessions_to_recover(memora.sessions, shift_index),
                }
            results.append(
                {
                    "persona": persona,
                    "baseline": baseline,
                    "memora": memora,
                    "recovery": recovery,
                }
            )

        OUT_DIR.mkdir(exist_ok=True)
        render_report(results, OUT_DIR / "report.md", fake=use_fake)
        render_chart(results, OUT_DIR / "chart.png")
        print(f"wrote {OUT_DIR / 'report.md'} and {OUT_DIR / 'chart.png'}")
    finally:
        await memory_client.close()


def main() -> None:
    asyncio.run(_amain(_parse_args()))


if __name__ == "__main__":
    main()
