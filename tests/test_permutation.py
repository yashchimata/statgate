import numpy as np
import pytest

from statgate.core.permutation import sign_flip_pvalue, two_sample_pvalue


class TestSignFlip:
    def test_null_false_positive_rate_is_controlled(self):
        rng = np.random.default_rng(21)
        rejections = 0
        simulations = 200
        for _ in range(simulations):
            diffs = rng.normal(0.0, 0.2, size=40)
            if sign_flip_pvalue(diffs, permutations=800, seed=1) < 0.05:
                rejections += 1
        assert rejections / simulations <= 0.10

    def test_detects_clear_effect(self):
        rng = np.random.default_rng(22)
        diffs = rng.normal(0.3, 0.1, size=50)
        assert sign_flip_pvalue(diffs, permutations=2000, seed=1) < 0.01

    def test_all_zero_diffs_give_pvalue_one(self):
        assert sign_flip_pvalue(np.zeros(30)) == 1.0

    def test_pvalue_never_zero(self):
        diffs = np.full(50, 5.0)
        p = sign_flip_pvalue(diffs, permutations=500, seed=1)
        assert p > 0.0

    def test_rejects_bad_input(self):
        with pytest.raises(ValueError):
            sign_flip_pvalue([])
        with pytest.raises(ValueError):
            sign_flip_pvalue([1.0, 2.0], permutations=10)


class TestTwoSample:
    def test_null_false_positive_rate_is_controlled(self):
        rng = np.random.default_rng(23)
        rejections = 0
        simulations = 100
        for _ in range(simulations):
            base = rng.normal(0.5, 0.2, size=30)
            cand = rng.normal(0.5, 0.2, size=30)
            if two_sample_pvalue(base, cand, permutations=500, seed=1) < 0.05:
                rejections += 1
        assert rejections / simulations <= 0.12

    def test_detects_clear_effect(self):
        rng = np.random.default_rng(24)
        base = rng.normal(0.5, 0.1, size=60)
        cand = rng.normal(0.8, 0.1, size=60)
        assert two_sample_pvalue(base, cand, permutations=1000, seed=1) < 0.01

    def test_identical_constant_samples(self):
        assert two_sample_pvalue(np.full(10, 0.5), np.full(10, 0.5)) == 1.0
