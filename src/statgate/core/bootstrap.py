import numpy as np
import numpy.typing as npt

from statgate.core.intervals import Interval, normal_cdf, z_quantile

FloatArray = npt.NDArray[np.float64]

_EPS = 1e-12


def _as_float_array(values: npt.ArrayLike, name: str) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one dimensional")
    if arr.size < 2:
        raise ValueError(f"{name} needs at least two values, got {arr.size}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    return arr


def _bca_quantiles(
    boot: FloatArray, values: FloatArray, observed: float, confidence: float
) -> tuple[float, float]:
    resamples = boot.size
    below = float(np.count_nonzero(boot < observed))
    ties = float(np.count_nonzero(boot == observed))
    p0 = (below + 0.5 * ties) / resamples
    p0 = min(max(p0, 1.0 / (resamples + 1.0)), resamples / (resamples + 1.0))
    z0 = z_quantile(p0)

    n = values.size
    jack = (values.sum() - values) / (n - 1)
    centered = jack.mean() - jack
    denom = 6.0 * float(np.sum(centered**2)) ** 1.5
    accel = float(np.sum(centered**3)) / denom if denom > _EPS else 0.0

    alpha = 1.0 - confidence
    quantiles = []
    for z_alpha in (z_quantile(alpha / 2.0), z_quantile(1.0 - alpha / 2.0)):
        correction = 1.0 - accel * (z0 + z_alpha)
        if correction <= _EPS:
            quantiles.append(normal_cdf(z_alpha))
        else:
            quantiles.append(normal_cdf(z0 + (z0 + z_alpha) / correction))
    return quantiles[0], quantiles[1]


def bca_mean_interval(
    values: npt.ArrayLike,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int | None = None,
) -> Interval:
    """Bias-corrected and accelerated bootstrap interval for the mean.

    Used on per-case paired differences. BCa corrects both the median bias
    of the bootstrap distribution and its skew, which matters for the
    small, non-normal samples typical of eval suites.
    """
    arr = _as_float_array(values, "values")
    if resamples < 100:
        raise ValueError(f"resamples must be at least 100, got {resamples}")
    observed = float(arr.mean())
    if float(arr.max() - arr.min()) < _EPS:
        return Interval(observed, observed, confidence)

    rng = np.random.default_rng(seed)
    n = arr.size
    boot = np.empty(resamples, dtype=np.float64)
    chunk = max(1, min(resamples, 20_000_000 // max(n, 1)))
    start = 0
    while start < resamples:
        stop = min(start + chunk, resamples)
        idx = rng.integers(0, n, size=(stop - start, n))
        boot[start:stop] = arr[idx].mean(axis=1)
        start = stop

    q_low, q_high = _bca_quantiles(boot, arr, observed, confidence)
    low = float(np.quantile(boot, q_low))
    high = float(np.quantile(boot, q_high))
    if low > high:
        low, high = high, low
    return Interval(low, high, confidence)


def unpaired_mean_diff_interval(
    baseline: npt.ArrayLike,
    candidate: npt.ArrayLike,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int | None = None,
) -> Interval:
    """Percentile bootstrap interval for the difference of independent means.

    Fallback for the case where baseline and candidate share too few
    case ids to support a paired analysis.
    """
    base = _as_float_array(baseline, "baseline")
    cand = _as_float_array(candidate, "candidate")
    if resamples < 100:
        raise ValueError(f"resamples must be at least 100, got {resamples}")
    observed = float(cand.mean() - base.mean())
    spread = float(base.max() - base.min()) + float(cand.max() - cand.min())
    if spread < _EPS:
        return Interval(observed, observed, confidence)

    rng = np.random.default_rng(seed)
    boot = np.empty(resamples, dtype=np.float64)
    chunk = max(1, min(resamples, 20_000_000 // max(base.size + cand.size, 1)))
    start = 0
    while start < resamples:
        stop = min(start + chunk, resamples)
        rows = stop - start
        base_idx = rng.integers(0, base.size, size=(rows, base.size))
        cand_idx = rng.integers(0, cand.size, size=(rows, cand.size))
        boot[start:stop] = cand[cand_idx].mean(axis=1) - base[base_idx].mean(axis=1)
        start = stop

    alpha = 1.0 - confidence
    low = float(np.quantile(boot, alpha / 2.0))
    high = float(np.quantile(boot, 1.0 - alpha / 2.0))
    return Interval(low, high, confidence)
