import json

import numpy as np
from rich.console import Console

from statgate.config import GateSettings
from statgate.core.intervals import Interval
from statgate.report import (
    MARKER,
    render_error_bar,
    render_json,
    render_markdown,
    render_terminal,
)
from statgate.report.jsonout import report_to_dict
from statgate.verdict import evaluate_gate
from tests.conftest import make_records

SETTINGS = GateSettings(resamples=1000, permutations=1000, seed=5)


def sample_report(shift: float = 0.05):
    rng = np.random.default_rng(1)
    base = rng.uniform(0.3, 0.9, size=50)
    cand = np.clip(base + shift + rng.normal(0, 0.05, size=50), 0, 1)
    return evaluate_gate(
        make_records(base, passed_threshold=0.6),
        make_records(cand, passed_threshold=0.6),
        SETTINGS,
    )


class TestErrorBar:
    def test_contains_interval_and_point_markers(self):
        art = render_error_bar(Interval(-0.05, 0.1, 0.95), 0.02, 0.02)
        lines = art.splitlines()
        assert "[" in lines[0]
        assert "]" in lines[0]
        assert "o" in lines[0]
        assert "|" in lines[1]
        assert "-margin" in lines[2]
        assert "95% CI [" in lines[3]

    def test_point_between_brackets(self):
        art = render_error_bar(Interval(-0.2, 0.4, 0.95), 0.1, 0.02)
        bar = art.splitlines()[0]
        assert bar.index("[") < bar.index("o") < bar.index("]")

    def test_degenerate_interval_renders(self):
        art = render_error_bar(Interval(0.1, 0.1, 0.95), 0.1, 0.02)
        assert "o" in art.splitlines()[0]

    def test_ascii_only(self):
        art = render_error_bar(Interval(-1.0, 1.0, 0.99), 0.0, 0.05)
        assert art == art.encode("ascii", errors="replace").decode("ascii")


class TestMarkdown:
    def test_contains_marker_verdict_and_tables(self):
        report = sample_report()
        text = render_markdown(report)
        assert text.startswith(MARKER)
        assert report.verdict.value in text
        assert "| Mean difference |" in text
        assert "| baseline |" in text
        assert "| candidate |" in text
        assert "```" in text

    def test_inconclusive_lists_required_pairs(self):
        rng = np.random.default_rng(8)
        base = rng.uniform(0.2, 1.0, size=10)
        cand = base + rng.normal(-0.05, 0.35, size=10)
        report = evaluate_gate(make_records(base), make_records(cand), SETTINGS)
        assert report.verdict.value == "INCONCLUSIVE"
        assert report.required_pairs is not None
        assert "Pairs needed to decide" in render_markdown(report)


class TestJson:
    def test_round_trips_through_json(self):
        report = sample_report()
        payload = json.loads(render_json(report))
        assert payload["verdict"] == report.verdict.value
        assert payload["exit_code"] == report.exit_code
        assert payload["interval"]["low"] == report.interval.low
        assert payload["baseline"]["pass_rate"] is not None
        assert payload["n_pairs"] == 50

    def test_dict_has_stable_keys(self):
        payload = report_to_dict(sample_report())
        for key in (
            "statgate_version",
            "verdict",
            "metric",
            "analysis",
            "mean_diff",
            "interval",
            "p_value",
            "notes",
        ):
            assert key in payload


class TestTerminal:
    def test_renders_without_crashing_and_shows_verdict(self):
        report = sample_report()
        console = Console(record=True, width=100, no_color=True)
        render_terminal(report, console)
        text = console.export_text()
        assert report.verdict.value in text
        assert "mean difference" in text
