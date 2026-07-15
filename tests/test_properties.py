from hypothesis import given, settings
from hypothesis import strategies as st

from statgate.adapters._shared import record_from_mapping
from statgate.core.bootstrap import bca_mean_interval
from statgate.core.intervals import wilson_interval
from statgate.core.permutation import sign_flip_pvalue
from statgate.core.power import minimum_detectable_effect, required_sample_size

scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

RESERVED_KEYS = {"case_id", "score", "passed", "run_index", "metadata", "id", "test_id", "case"}


class TestWilsonProperties:
    @given(
        total=st.integers(min_value=1, max_value=10_000),
        data=st.data(),
        confidence=st.floats(min_value=0.5, max_value=0.999),
    )
    @settings(max_examples=200)
    def test_bounds_bracket_the_estimate(self, total, data, confidence):
        successes = data.draw(st.integers(min_value=0, max_value=total))
        interval = wilson_interval(successes, total, confidence)
        p_hat = successes / total
        assert 0.0 <= interval.low <= p_hat <= interval.high <= 1.0


class TestPowerProperties:
    @given(
        sd=st.floats(min_value=0.01, max_value=10.0),
        n=st.integers(min_value=2, max_value=100_000),
        alpha=st.floats(min_value=0.001, max_value=0.2),
        power=st.floats(min_value=0.5, max_value=0.99),
    )
    @settings(max_examples=200)
    def test_round_trip_is_consistent(self, sd, n, alpha, power):
        effect = minimum_detectable_effect(sd, n, alpha, power)
        assert effect > 0
        recovered = required_sample_size(sd, effect, alpha, power)
        assert abs(recovered - n) <= max(2, n * 0.01)

    @given(sd=st.floats(min_value=0.01, max_value=5.0))
    @settings(max_examples=50)
    def test_mde_is_monotone_in_n(self, sd):
        values = [minimum_detectable_effect(sd, n) for n in (10, 100, 1000)]
        assert values[0] > values[1] > values[2]


class TestBootstrapProperties:
    @given(values=st.lists(scores, min_size=5, max_size=40))
    @settings(max_examples=25, deadline=None)
    def test_interval_is_ordered_and_finite(self, values):
        interval = bca_mean_interval(values, confidence=0.9, resamples=300, seed=1)
        assert interval.low <= interval.high
        assert -1.0 <= interval.low <= 2.0
        assert -1.0 <= interval.high <= 2.0


class TestPermutationProperties:
    @given(values=st.lists(st.floats(min_value=-1, max_value=1), min_size=3, max_size=40))
    @settings(max_examples=25, deadline=None)
    def test_pvalue_is_a_probability(self, values):
        p = sign_flip_pvalue(values, permutations=200, seed=1)
        assert 0.0 < p <= 1.0


class TestRecordProperties:
    @given(
        case_id=st.text(min_size=1, max_size=30),
        score=scores,
        extras=st.dictionaries(
            st.text(min_size=1, max_size=10).filter(lambda k: k not in RESERVED_KEYS),
            st.one_of(st.integers(), st.text(max_size=10), st.booleans()),
            max_size=3,
        ),
    )
    @settings(max_examples=100)
    def test_extras_survive_into_metadata(self, case_id, score, extras):
        record = record_from_mapping({"case_id": case_id, "score": score, **extras}, "ctx")
        assert record.case_id == case_id
        assert record.score == score
        assert record.metadata == extras
