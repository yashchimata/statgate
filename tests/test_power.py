import pytest

from statgate.core.power import (
    minimum_detectable_effect,
    power_table,
    required_sample_size,
)


class TestPower:
    def test_known_value(self):
        mde = minimum_detectable_effect(sd=0.2, n=100, alpha=0.05, power=0.8)
        assert mde == pytest.approx(0.2 * (1.959964 + 0.841621) / 10.0, rel=1e-4)

    def test_mde_shrinks_with_larger_suites(self):
        values = [minimum_detectable_effect(0.2, n) for n in (25, 100, 400)]
        assert values[0] > values[1] > values[2]

    def test_round_trip_with_required_sample_size(self):
        sd = 0.25
        for n in (30, 120, 500):
            effect = minimum_detectable_effect(sd, n)
            assert abs(required_sample_size(sd, effect) - n) <= 1

    def test_required_size_grows_for_smaller_effects(self):
        assert required_sample_size(0.2, 0.01) > required_sample_size(0.2, 0.1)

    def test_zero_sd_needs_minimum_suite(self):
        assert required_sample_size(0.0, 0.05) == 2

    def test_table_matches_pointwise_values(self):
        rows = power_table(0.3, sizes=(50, 100))
        assert rows[0].n == 50
        assert rows[0].mde == pytest.approx(minimum_detectable_effect(0.3, 50))
        assert rows[1].mde == pytest.approx(minimum_detectable_effect(0.3, 100))

    def test_rejects_invalid_input(self):
        with pytest.raises(ValueError):
            minimum_detectable_effect(-0.1, 100)
        with pytest.raises(ValueError):
            minimum_detectable_effect(0.2, 1)
        with pytest.raises(ValueError):
            required_sample_size(0.2, 0.0)
        with pytest.raises(ValueError):
            required_sample_size(0.2, 0.05, alpha=1.5)
        with pytest.raises(ValueError):
            power_table(0.2, sizes=())
