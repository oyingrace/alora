"""Renders the benchmark harness's results into report.md + chart.png
(BUILD_PLAN.md §7: "Output a chart PNG for README + video.")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_report(results: list[dict[str, Any]], path: Path, *, fake: bool) -> None:
    lines = ["# Benchmark report", ""]
    if fake:
        lines.append(
            "> Generated with the offline fake-Qwen shim (`bench/fake_qwen.py`) — no "
            "QWEN_API_KEY was available. Numbers below demonstrate the harness's "
            "mechanics; re-run without `--fake` and a real key for the numbers that "
            "go in the README/video."
        )
        lines.append("")

    lines.append("| Persona | Arm | Avg relevance | Avg tokens/session | Recovery (sessions) |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        persona = r["persona"]
        recovery = r["recovery"]
        for arm_key in ("baseline", "memora"):
            arm = r[arm_key]
            recovery_str = "n/a"
            if recovery is not None:
                val = recovery[arm_key]
                recovery_str = str(val) if val is not None else "did not recover"
            lines.append(
                f"| {persona.name} | {arm.arm} | {arm.avg_relevance:.2f} | "
                f"{arm.avg_tokens:.0f} | {recovery_str} |"
            )

    lines.append("")
    lines.append("## Notes")
    lines.append(
        "- **Rec relevance**: qwen-max-judged 0..1 score of the returned recs against "
        "the persona's current ideal preference, averaged across sessions."
    )
    lines.append(
        "- **Recovery (sessions)**: for Style Shifter only — how many sessions after "
        "the explicit preference correction it took relevance to cross "
        f"{0.5:.1f} again."
    )
    lines.append(
        "- **Baseline**: a fresh shopper_id every session, so nothing persists "
        "between sessions — the closest fair comparison to a similarity-only "
        "recommender with no memory."
    )

    path.write_text("\n".join(lines) + "\n")


def render_chart(results: list[dict[str, Any]], path: Path) -> None:
    fig, axes = plt.subplots(1, len(results), figsize=(6 * len(results), 4.5), squeeze=False)
    axes = axes[0]

    for ax, r in zip(axes, results, strict=True):
        persona = r["persona"]
        baseline_scores = [s.relevance for s in r["baseline"].sessions]
        memora_scores = [s.relevance for s in r["memora"].sessions]
        sessions = list(range(1, len(baseline_scores) + 1))

        ax.plot(sessions, baseline_scores, label="baseline", marker="o", markersize=3)
        ax.plot(sessions, memora_scores, label="memora", marker="o", markersize=3)
        ax.set_title(persona.name)
        ax.set_xlabel("session")
        ax.set_ylabel("rec relevance")
        ax.set_ylim(-0.05, 1.05)
        ax.legend()

    fig.suptitle("Memora vs baseline: recommendation relevance per session")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
