"""
Combines the exclusion bookkeeping from both exports into one auditable
report: per export type, total traces considered, count excluded per
reason, and a sample of excluded trace_ids per reason. Callable as a
script (writes /data/exports/exclusion_report.md) and via
GET /export/exclusions (returns the same data as JSON).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from export_preference import build_preference_export
from export_sft import build_sft_export

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPORTS_DIR = DATA_DIR / "exports"
OUT_PATH = EXPORTS_DIR / "exclusion_report.md"

SAMPLE_SIZE = 5


def _reasons_with_samples(excluded_by_reason: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    return {
        reason: {"count": len(ids), "sample_trace_ids": ids[:SAMPLE_SIZE]}
        for reason, ids in excluded_by_reason.items()
    }


def build_exclusion_report() -> dict[str, Any]:
    sft = build_sft_export()
    preference = build_preference_export()

    sft_excluded = _reasons_with_samples(sft["excluded_by_reason"])
    preference_excluded = _reasons_with_samples(preference["excluded_by_reason"])

    total_sft_excluded = sum(v["count"] for v in sft_excluded.values())
    assert total_sft_excluded + sft["kept_count"] == sft["total_traces_considered"], (
        "sft exclusion counts must sum to total traces considered"
    )

    return {
        "sft": {
            "total_traces_considered": sft["total_traces_considered"],
            "total_sessions": sft["total_sessions"],
            "kept_count": sft["kept_count"],
            "excluded": sft_excluded,
        },
        "preference": {
            "total_traces_considered": preference["total_traces_considered"],
            "pair_count": preference["pair_count"],
            "pairs_by_source": preference["pairs_by_source"],
            "excluded": preference_excluded,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Exclusion Report", ""]
    lines.append(
        "Generated from the current SQLite corpus. All trace_ids below are "
        "auditable via `GET /traces/{trace_id}`."
    )
    lines.append("")

    sft = report["sft"]
    lines.append("## SFT export")
    lines.append("")
    lines.append(f"- Total traces considered: **{sft['total_traces_considered']}** "
                  f"across **{sft['total_sessions']}** sessions")
    lines.append(f"- Kept (written to sft.jsonl): **{sft['kept_count']}**")
    lines.append("")
    if sft["excluded"]:
        lines.append("| Reason | Count | Sample trace_ids |")
        lines.append("|---|---|---|")
        for reason, data in sft["excluded"].items():
            sample = ", ".join(f"`{t}`" for t in data["sample_trace_ids"])
            lines.append(f"| {reason} | {data['count']} | {sample} |")
    lines.append("")

    pref = report["preference"]
    lines.append("## Preference pair export")
    lines.append("")
    lines.append(f"- Total traces considered: **{pref['total_traces_considered']}**")
    lines.append(f"- Pairs written to preference.jsonl: **{pref['pair_count']}**")
    for source, count in pref["pairs_by_source"].items():
        lines.append(f"  - {source}: {count}")
    lines.append("")
    if pref["excluded"]:
        lines.append("| Reason | Count | Sample trace_ids |")
        lines.append("|---|---|---|")
        for reason, data in pref["excluded"].items():
            sample = ", ".join(f"`{t}`" for t in data["sample_trace_ids"])
            lines.append(f"| {reason} | {data['count']} | {sample} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    report = build_exclusion_report()
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_markdown(report))
    print(f"Wrote exclusion report to {OUT_PATH}")


if __name__ == "__main__":
    main()
