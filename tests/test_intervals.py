import pytest

from statgate.core.intervals import Interval, normal_cdf, wilson_interval, z_quantile


class TestInterval:
    def test_width_and_contains(self):
        interval = Interval(-0.1, 0.3, 0.95)
        assert interval.width == pytest.approx(0.4)
        assert interval.contains(0.0)
        assert interval.contains(-0.1)
        assert not interval.contains(0.31)

    def test_rejects_inverted_bounds(self):
        with pytest.raises(ValueError):
            Interval(0.5, 0.1, 0.95)

    def test_rejects_bad_confidence(self):
        with pytest.raises(ValueError):
            Interval(0.0, 1.0, 1.0)


class TestZQuantile:
    def test_known_values(self):
        assert z_quantile(0.975) == pytest.approx(1.959964, abs=1e-5)
        assert z_quantile(0.8) == pytest.approx(0.841621, abs=1e-5)
        assert z_quantile(0.5) == pytest.approx(0.0, abs=1e-12)

    def test_symmetry(self):
        assert z_quantile(0.3) == pytest.approx(-z_quantile(0.7))

    def test_rejects_boundaries(self):
        with pytest.raises(ValueError):
            z_quantile(0.0)
        with pytest.raises(ValueError):
            z_quantile(1.0)

    def test_cdf_inverts_quantile(self):
        for p in (0.05, 0.25, 0.5, 0.9, 0.999):
            assert normal_cdf(z_quantile(p)) == pytest.approx(p, abs=1e-9)


class TestWilsonInterval:
    def test_known_value(self):
        interval = wilson_interval(45, 50, 0.95)
        assert interval.low == pytest.approx(0.7864, abs=2e-3)
        assert interval.high == pytest.approx(0.9565, abs=2e-3)

    def test_extreme_proportions_stay_in_unit_interval(self):
        zero = wilson_interval(0, 20)
        full = wilson_interval(20, 20)
        assert zero.low == 0.0
        assert zero.high > 0.0
        assert full.high == 1.0
        assert full.low < 1.0

    def test_narrows_with_more_data(self):
        small = wilson_interval(8, 10)
        large = wilson_interval(800, 1000)
        assert large.width < small.width

    def test_rejects_invalid_counts(self):
        with pytest.raises(ValueError):
            wilson_interval(5, 0)
        with pytest.raises(ValueError):
            wilson_interval(11, 10)
        with pytest.raises(ValueError):
            wilson_interval(-1, 10)
