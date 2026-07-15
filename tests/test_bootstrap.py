import numpy as np
import pytest

from statgate.core.bootstrap import bca_mean_interval, unpaired_mean_diff_interval


class TestBcaMeanInterval:
    def test_contains_true_mean_at_nominal_rate(self):
        rng = np.random.default_rng(42)
        true_mean = 0.1
        covered = 0
        simulations = 200
        for _ in range(simulations):
            sample = rng.normal(true_mean, 0.2, size=40)
            interval = bca_mean_interval(sample, confidence=0.95, resamples=1500, seed=1)
            if interval.contains(true_mean):
                covered += 1
        assert 0.88 <= covered / simulations <= 0.99

    def test_skewed_data_coverage(self):
        rng = np.random.default_rng(7)
        true_mean = 1.0
        covered = 0
        simulations = 150
        for _ in range(simulations):
            sample = rng.exponential(true_mean, size=60)
            interval = bca_mean_interval(sample, confidence=0.95, resamples=1500, seed=1)
            if interval.contains(true_mean):
                covered += 1
        assert 0.85 <= covered / simulations <= 1.0

    def test_constant_input_gives_degenerate_interval(self):
        interval = bca_mean_interval(np.full(30, 0.5), seed=1)
        assert interval.low == interval.high == 0.5

    def test_deterministic_with_seed(self):
        values = np.random.default_rng(3).normal(0, 1, 50)
        a = bca_mean_interval(values, resamples=500, seed=11)
        b = bca_mean_interval(values, resamples=500, seed=11)
        assert a == b

    def test_narrows_with_more_data(self):
        rng = np.random.default_rng(5)
        small = bca_mean_interval(rng.normal(0, 1, 20), resamples=1000, seed=1)
        large = bca_mean_interval(rng.normal(0, 1, 2000), resamples=1000, seed=1)
        assert large.width < small.width

    def test_rejects_tiny_or_bad_input(self):
        with pytest.raises(ValueError):
            bca_mean_interval([1.0])
        with pytest.raises(ValueError):
            bca_mean_interval([1.0, float("nan"), 2.0])
        with pytest.raises(ValueError):
            bca_mean_interval([[1.0, 2.0]])
        with pytest.raises(ValueError):
            bca_mean_interval([1.0, 2.0, 3.0], resamples=10)


class TestUnpairedInterval:
    def test_covers_true_difference(self):
        rng = np.random.default_rng(9)
        covered = 0
        simulations = 150
        for _ in range(simulations):
            base = rng.normal(0.6, 0.15, size=50)
            cand = rng.normal(0.65, 0.15, size=50)
            interval = unpaired_mean_diff_interval(
                base, cand, confidence=0.95, resamples=1200, seed=1
            )
            if interval.contains(0.05):
                covered += 1
        assert 0.88 <= covered / simulations <= 0.99

    def test_constant_inputs(self):
        interval = unpaired_mean_diff_interval(np.full(10, 0.5), np.full(10, 0.7), seed=1)
        assert interval.low == interval.high == pytest.approx(0.2)
