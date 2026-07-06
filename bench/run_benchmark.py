#!/usr/bin/env python3
"""Persona benchmark harness: baseline (similarity-only) vs Memora.

Stub for Phase 0 — personas, session scripting, and the LLM-judge scoring loop are
Phase 4 work (BUILD_PLAN.md §7). Running this now just confirms the output paths exist.
"""

from pathlib import Path

OUT_DIR = Path(__file__).parent / "out"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    report_path = OUT_DIR / "report.md"
    report_path.write_text(
        "# Benchmark report\n\nNot yet implemented — see bench/README.md.\n"
    )
    print(f"wrote stub report to {report_path}")


if __name__ == "__main__":
    main()
