from dataclasses import dataclass
from math import ceil, sqrt

from statgate.core.intervals import z_quantile

DEFAULT_SIZES = (25, 50, 100, 200, 400, 800)


@dataclass(frozen=True)
class PowerRow:
    """Minimum detectable effect for one suite size."""

    n: int
    mde: float


def _z_total(alpha: float, power: float) -> float:
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if not 0.0 < power < 1.0:
        raise ValueError(f"power must be in (0, 1), got {power}")
    return z_quantile(1.0 - alpha / 2.0) + z_quantile(power)


def minimum_detectable_effect(
    sd: float, n: int, alpha: float = 0.05, power: float = 0.8
) -> float:
    """Smallest mean difference detectable with the given suite size.

    Uses the standard normal approximation for a paired two-sided test:
    the per-case differences have standard deviation ``sd`` and the suite
    has ``n`` paired cases.
    """
    if sd < 0.0:
        raise ValueError(f"sd must be non-negative, got {sd}")
    if n < 2:
        raise ValueError(f"n must be at least 2, got {n}")
    return _z_total(alpha, power) * sd / sqrt(n)


def required_sample_size(
    sd: float, effect: float, alpha: float = 0.05, power: float = 0.8
) -> int:
    """Paired cases needed to detect ``effect`` with the given power."""
    if sd < 0.0:
        raise ValueError(f"sd must be non-negative, got {sd}")
    if effect <= 0.0:
        raise ValueError(f"effect must be positive, got {effect}")
    z = _z_total(alpha, power)
    return max(2, ceil((z * sd / effect) ** 2))


def power_table(
    sd: float,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    alpha: float = 0.05,
    power: float = 0.8,
) -> list[PowerRow]:
    """Minimum detectable effect across a range of suite sizes."""
    if not sizes:
        raise ValueError("sizes must not be empty")
    return [PowerRow(n=n, mde=minimum_detectable_effect(sd, n, alpha, power)) for n in sizes]
