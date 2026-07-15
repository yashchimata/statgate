import numpy as np
import pytest

from statgate.config import GateSettings
from statgate.errors import AnalysisError
from statgate.records import EvalRecord
from statgate.verdict import Verdict, evaluate_gate
from tests.conftest import make_records

SETTINGS = GateSettings(resamples=1500, permutations=1500, seed=7)


def shifted_records(n: int, shift: float, noise: float, seed: int = 1):
    rng = np.random.default_rng(seed)
    ability = rng.uniform(0.3, 0.9, size=n)
    base = np.clip(ability + rng.normal(0, noise, size=n), 0, 1)
    cand = np.clip(base + shift + rng.normal(0, noise / 2, size=n), 0, 1)
    return make_records(base), make_records(cand)


class TestVerdicts:
    def test_clear_improvement_ships(self):
        baseline, candidate = shifted_records(80, shift=0.08, noise=0.05)
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.verdict is Verdict.SHIP
        assert report.exit_code == 0
        assert report.analysis == "paired"
        assert report.mean_diff > 0
        assert report.interval.low > -SETTINGS.margin

    def test_flat_change_ships_within_margin(self):
        baseline, candidate = shifted_records(200, shift=0.0, noise=0.02)
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.verdict is Verdict.SHIP

    def test_clear_regression_blocks(self):
        baseline, candidate = shifted_records(80, shift=-0.15, noise=0.05)
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.verdict is Verdict.BLOCK
        assert report.exit_code == 1
        assert report.interval.high < -SETTINGS.margin

    def test_small_noisy_suite_is_inconclusive_with_required_pairs(self):
        rng = np.random.default_rng(5)
        base = rng.uniform(0.2, 1.0, size=12)
        cand = base + rng.normal(-0.05, 0.35, size=12)
        report = evaluate_gate(make_records(base), make_records(cand), SETTINGS)
        assert report.verdict is Verdict.INCONCLUSIVE
        assert report.exit_code == 2
        assert report.required_pairs is not None
        assert report.required_pairs > 12

    def test_verdict_is_deterministic_with_seed(self):
        baseline, candidate = shifted_records(40, shift=0.02, noise=0.1)
        first = evaluate_gate(baseline, candidate, SETTINGS)
        second = evaluate_gate(baseline, candidate, SETTINGS)
        assert first.verdict == second.verdict
        assert first.interval == second.interval


class TestUnpairedFallback:
    def test_disjoint_case_ids_fall_back_to_unpaired(self):
        rng = np.random.default_rng(11)
        baseline = make_records(rng.uniform(0.5, 0.9, size=60), prefix="old")
        candidate = make_records(rng.uniform(0.5, 0.9, size=60), prefix="new")
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.analysis == "unpaired"
        assert any("unpaired" in note for note in report.notes)

    def test_too_little_data_raises(self):
        with pytest.raises(AnalysisError, match="not enough data"):
            evaluate_gate(
                make_records([0.5, 0.6], prefix="old"),
                make_records([0.5, 0.6], prefix="new"),
                SETTINGS,
            )

    def test_repeated_runs_count_as_cases_not_records(self):
        baseline = [
            EvalRecord(case_id=f"old-{c}", score=0.5 + 0.01 * r, run_index=r)
            for c in range(3)
            for r in range(5)
        ]
        candidate = [
            EvalRecord(case_id=f"new-{c}", score=0.5 + 0.01 * r, run_index=r)
            for c in range(3)
            for r in range(5)
        ]
        with pytest.raises(AnalysisError, match="3 baseline cases"):
            evaluate_gate(baseline, candidate, SETTINGS)

    def test_unpaired_analysis_aggregates_repeated_runs(self):
        rng = np.random.default_rng(17)
        baseline = [
            EvalRecord(case_id=f"old-{c}", score=float(rng.normal(0.6, 0.05)), run_index=r)
            for c in range(20)
            for r in range(5)
        ]
        candidate = [
            EvalRecord(case_id=f"new-{c}", score=float(rng.normal(0.6, 0.05)), run_index=r)
            for c in range(20)
            for r in range(5)
        ]
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.analysis == "unpaired"
        base_case_means = {}
        for record in baseline:
            base_case_means.setdefault(record.case_id, []).append(record.score)
        case_sd = float(np.std([np.mean(v) for v in base_case_means.values()], ddof=1))
        assert report.interval.width > 2.0 * case_sd / np.sqrt(20)

    def test_empty_sides_raise(self):
        with pytest.raises(AnalysisError):
            evaluate_gate([], make_records([0.5] * 10), SETTINGS)
        with pytest.raises(AnalysisError):
            evaluate_gate(make_records([0.5] * 10), [], SETTINGS)


class TestReportContents:
    def test_pass_rate_summaries_present_when_flags_exist(self):
        baseline = make_records([0.4, 0.9, 0.7, 0.8, 0.2, 0.9], passed_threshold=0.6)
        candidate = make_records([0.5, 0.9, 0.8, 0.8, 0.3, 0.9], passed_threshold=0.6)
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.baseline.pass_rate is not None
        assert report.candidate.pass_interval is not None
        assert 0.0 <= report.baseline.pass_rate <= 1.0

    def test_pass_interval_uses_cases_not_repeated_runs(self):
        baseline = [
            EvalRecord(case_id=f"case-{c}", passed=c < 3, run_index=r)
            for c in range(6)
            for r in range(25)
        ]
        candidate = [
            EvalRecord(case_id=f"case-{c}", passed=c < 3, run_index=r)
            for c in range(6)
            for r in range(25)
        ]
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.baseline.pass_rate == pytest.approx(0.5)
        assert report.baseline.pass_interval is not None
        assert report.baseline.pass_interval.width > 0.5

    def test_pass_rate_metric_end_to_end(self):
        settings = GateSettings(
            metric="pass_rate", resamples=1500, permutations=1500, seed=7
        )
        rng = np.random.default_rng(6)
        base_flags = rng.uniform(size=60) < 0.7
        cand_flags = base_flags | (rng.uniform(size=60) < 0.3)
        baseline = [
            EvalRecord(case_id=f"case-{i}", passed=bool(f)) for i, f in enumerate(base_flags)
        ]
        candidate = [
            EvalRecord(case_id=f"case-{i}", passed=bool(f)) for i, f in enumerate(cand_flags)
        ]
        report = evaluate_gate(baseline, candidate, settings)
        assert report.metric == "pass_rate"
        assert report.verdict is Verdict.SHIP
        assert report.mean_diff > 0

    def test_partial_overlap_notes_excluded_cases(self):
        baseline = make_records([0.5] * 30 + [0.9] * 5, prefix="case")
        candidate = make_records([0.55] * 30, prefix="case")
        rng = np.random.default_rng(3)
        baseline = [
            EvalRecord(case_id=r.case_id, score=float(rng.uniform(0.4, 0.8)))
            for r in baseline
        ]
        report = evaluate_gate(baseline, candidate, SETTINGS)
        assert report.baseline_only == 5
        assert any("excluded" in note for note in report.notes)

    def test_zero_margin_requires_strict_superiority(self):
        settings = GateSettings(margin=0.0, resamples=1500, permutations=1500, seed=7)
        baseline, candidate = shifted_records(100, shift=0.1, noise=0.05)
        report = evaluate_gate(baseline, candidate, settings)
        assert report.verdict is Verdict.SHIP
        baseline, candidate = shifted_records(100, shift=-0.1, noise=0.05)
        report = evaluate_gate(baseline, candidate, settings)
        assert report.verdict is Verdict.BLOCK
