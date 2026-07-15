import pytest

from statgate.core.pairing import aggregate_by_case, build_paired
from statgate.errors import AnalysisError
from statgate.records import EvalRecord


def record(case_id: str, score: float | None = None, passed: bool | None = None, run: int = 0):
    return EvalRecord(case_id=case_id, score=score, passed=passed, run_index=run)


class TestAggregateByCase:
    def test_averages_repeated_runs(self):
        records = [record("a", 0.2, run=0), record("a", 0.6, run=1), record("b", 1.0)]
        values = aggregate_by_case(records, "score")
        assert values == {"a": pytest.approx(0.4), "b": 1.0}

    def test_pass_rate_metric_uses_passed_flag(self):
        records = [record("a", passed=True), record("a", passed=False, run=1)]
        values = aggregate_by_case(records, "pass_rate")
        assert values == {"a": pytest.approx(0.5)}

    def test_pass_rate_metric_requires_passed_flag(self):
        with pytest.raises(AnalysisError, match="pass_rate"):
            aggregate_by_case([record("a", score=0.5)], "pass_rate")

    def test_score_metric_falls_back_to_passed(self):
        values = aggregate_by_case([record("a", passed=True)], "score")
        assert values == {"a": 1.0}

    def test_empty_records_raise(self):
        with pytest.raises(AnalysisError):
            aggregate_by_case([], "score")


class TestBuildPaired:
    def test_pairs_shared_cases_sorted(self):
        baseline = [record("b", 0.5), record("a", 0.2), record("c", 0.9)]
        candidate = [record("c", 1.0), record("a", 0.4), record("d", 0.1)]
        paired = build_paired(baseline, candidate, "score")
        assert paired.case_ids == ("a", "c")
        assert paired.baseline.tolist() == [0.2, 0.9]
        assert paired.candidate.tolist() == [0.4, 1.0]
        assert paired.baseline_only == 1
        assert paired.candidate_only == 1
        assert paired.diffs.tolist() == pytest.approx([0.2, 0.1])

    def test_stream_order_follows_candidate_appearance(self):
        baseline = [record("a", 0.1), record("b", 0.2), record("c", 0.3)]
        candidate = [record("c", 0.3), record("a", 0.1), record("b", 0.2)]
        paired = build_paired(baseline, candidate, "score", order="stream")
        assert paired.case_ids == ("c", "a", "b")

    def test_pair_fraction(self):
        baseline = [record("a", 0.1), record("b", 0.2)]
        candidate = [record("a", 0.1), record("c", 0.2), record("d", 0.3)]
        paired = build_paired(baseline, candidate, "score")
        assert paired.n_pairs == 1
        assert paired.pair_fraction == pytest.approx(0.25)

    def test_no_shared_cases(self):
        paired = build_paired([record("a", 0.1)], [record("b", 0.2)], "score")
        assert paired.n_pairs == 0
        assert paired.pair_fraction == 0.0
