from dataclasses import dataclass
from math import sqrt
from statistics import NormalDist

_NORMAL = NormalDist()


@dataclass(frozen=True)
class Interval:
    """A two-sided confidence interval."""

    low: float
    high: float
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence < 1.0:
            raise ValueError(f"confidence must be in (0, 1), got {self.confidence}")
        if self.low > self.high:
            raise ValueError(f"interval low {self.low} exceeds high {self.high}")

    @property
    def width(self) -> float:
        return self.high - self.low

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high


def z_quantile(p: float) -> float:
    """Standard normal quantile."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"quantile probability must be in (0, 1), got {p}")
    return _NORMAL.inv_cdf(p)


def normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return _NORMAL.cdf(x)


def wilson_proportion_interval(p_hat: float, total: int, confidence: float = 0.95) -> Interval:
    """Wilson score interval for an observed proportion over ``total`` units.

    Unlike the normal approximation, the Wilson interval behaves well for
    small samples and for proportions near 0 or 1, which is the common
    regime for eval pass rates. ``total`` must be the number of
    independent units; for clustered data pass the cluster count.
    """
    if total <= 0:
        raise ValueError("total must be a positive integer")
    if not 0.0 <= p_hat <= 1.0:
        raise ValueError(f"p_hat must be in [0, 1], got {p_hat}")
    z = z_quantile(0.5 + confidence / 2.0)
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p_hat + z2 / (2.0 * total)) / denom
    half = z * sqrt(p_hat * (1.0 - p_hat) / total + z2 / (4.0 * total * total)) / denom
    low = min(max(0.0, center - half), p_hat)
    high = max(min(1.0, center + half), p_hat)
    return Interval(low, high, confidence)


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> Interval:
    """Wilson score interval for a binomial success count."""
    if total <= 0:
        raise ValueError("total must be a positive integer")
    if not 0 <= successes <= total:
        raise ValueError(f"successes must be in [0, {total}], got {successes}")
    return wilson_proportion_interval(successes / total, total, confidence)
