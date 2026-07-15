import json
from typing import Any

from statgate.__about__ import __version__
from statgate.core.intervals import Interval
from statgate.verdict import GateReport, SideSummary


def _interval_to_dict(interval: Interval | None) -> dict[str, float] | None:
    if interval is None:
        return None
    return {
        "low": interval.low,
        "high": interval.high,
        "confidence": interval.confidence,
    }


def _side_to_dict(side: SideSummary) -> dict[str, Any]:
    return {
        "label": side.label,
        "n_cases": side.n_cases,
        "n_records": side.n_records,
        "mean": side.mean,
        "pass_rate": side.pass_rate,
        "pass_interval": _interval_to_dict(side.pass_interval),
    }


def report_to_dict(report: GateReport) -> dict[str, Any]:
    """Convert a gate report to a JSON serializable dictionary."""
    return {
        "statgate_version": __version__,
        "verdict": report.verdict.value,
        "exit_code": report.exit_code,
        "metric": report.metric,
        "analysis": report.analysis,
        "mean_diff": report.mean_diff,
        "interval": _interval_to_dict(report.interval),
        "p_value": report.p_value,
        "alpha": report.alpha,
        "margin": report.margin,
        "n_pairs": report.n_pairs,
        "sd_diff": report.sd_diff,
        "baseline": _side_to_dict(report.baseline),
        "candidate": _side_to_dict(report.candidate),
        "baseline_only": report.baseline_only,
        "candidate_only": report.candidate_only,
        "required_pairs": report.required_pairs,
        "notes": list(report.notes),
    }


def render_json(report: GateReport) -> str:
    """Render the gate report as pretty printed JSON."""
    return json.dumps(report_to_dict(report), indent=2)
