import numpy as np
import pytest

from statgate.core.sequential import MixtureSPRT


class TestMixtureSPRT:
    def test_type_one_error_is_controlled_under_optional_stopping(self):
        rng = np.random.default_rng(31)
        rejections = 0
        simulations = 150
        for _ in range(simulations):
            sprt = MixtureSPRT(theta0=0.0, alpha=0.05, min_samples=10)
            for _ in range(8):
                decision = sprt.update(rng.normal(0.0, 0.2, size=25))
                if decision.decided:
                    rejections += 1
                    break
        assert rejections / simulations <= 0.10

    def test_detects_true_effect_and_stops_early(self):
        rng = np.random.default_rng(32)
        stopped_at = []
        for _ in range(50):
            sprt = MixtureSPRT(theta0=0.0, alpha=0.05, min_samples=10)
            decided_n = None
            for _ in range(16):
                decision = sprt.update(rng.normal(0.3, 0.2, size=25))
                if decision.decided:
                    decided_n = decision.n
                    assert decision.direction == 1
                    break
            assert decided_n is not None
            stopped_at.append(decided_n)
        assert float(np.mean(stopped_at)) < 200.0

    def test_detects_negative_effect_with_direction(self):
        rng = np.random.default_rng(33)
        sprt = MixtureSPRT(theta0=0.0, alpha=0.05, min_samples=10)
        decision = sprt.update(rng.normal(-0.5, 0.1, size=100))
        assert decision.decided
        assert decision.direction == -1

    def test_no_decision_before_min_samples(self):
        sprt = MixtureSPRT(theta0=0.0, alpha=0.05, min_samples=20)
        decision = sprt.update(np.full(10, 5.0))
        assert not decision.decided

    def test_pvalue_is_monotone_nonincreasing(self):
        rng = np.random.default_rng(34)
        sprt = MixtureSPRT(theta0=0.0, alpha=0.01, min_samples=5)
        previous = 1.0
        for _ in range(10):
            decision = sprt.update(rng.normal(0.05, 0.3, size=10))
            assert decision.p_value <= previous + 1e-12
            previous = decision.p_value

    def test_zero_variance_matching_null_never_rejects(self):
        sprt = MixtureSPRT(theta0=0.5, alpha=0.05, min_samples=5)
        decision = sprt.update(np.full(50, 0.5))
        assert not decision.decided
        assert decision.p_value == 1.0

    def test_constant_batch_carries_no_evidence_even_far_from_null(self):
        sprt = MixtureSPRT(theta0=0.0, alpha=0.05, min_samples=5, tau=0.1)
        decision = sprt.update(np.full(20, 1.0))
        assert not decision.decided
        assert decision.p_value == 1.0

    def test_identical_early_diffs_do_not_ship_instantly(self):
        sprt = MixtureSPRT(theta0=-0.02, alpha=0.05, min_samples=10)
        decision = sprt.update(np.zeros(10))
        assert not decision.decided
        assert decision.p_value == 1.0

    def test_recovers_full_power_after_degenerate_first_window(self):
        rng = np.random.default_rng(35)
        sprt = MixtureSPRT(theta0=0.0, alpha=0.05, min_samples=10)
        first = sprt.update(np.zeros(10))
        assert not first.decided
        decision = sprt.update(rng.normal(0.5, 0.2, size=100))
        assert decision.decided
        assert decision.direction == 1

    def test_empty_batch_is_a_noop(self):
        sprt = MixtureSPRT()
        decision = sprt.update([])
        assert decision.n == 0
        assert not decision.decided

    def test_rejects_invalid_parameters(self):
        with pytest.raises(ValueError):
            MixtureSPRT(alpha=0.0)
        with pytest.raises(ValueError):
            MixtureSPRT(tau=-1.0)
        with pytest.raises(ValueError):
            MixtureSPRT(min_samples=1)
        with pytest.raises(ValueError):
            MixtureSPRT().update([1.0, float("inf")])
