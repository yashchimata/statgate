import numpy as np
import numpy.typing as npt

_EPS = 1e-12


def sign_flip_pvalue(
    diffs: npt.ArrayLike,
    permutations: int = 10_000,
    seed: int | None = None,
) -> float:
    """Two-sided paired permutation test on per-case differences.

    Under the null hypothesis of no systematic difference, each per-case
    difference is symmetric around zero, so its sign is exchangeable.
    """
    arr = np.asarray(diffs, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 1:
        raise ValueError("diffs must be a non-empty one dimensional array")
    if permutations < 100:
        raise ValueError(f"permutations must be at least 100, got {permutations}")
    observed = abs(float(arr.mean()))
    if float(np.max(np.abs(arr))) < _EPS:
        return 1.0

    rng = np.random.default_rng(seed)
    n = arr.size
    extreme = 0
    chunk = max(1, min(permutations, 20_000_000 // max(n, 1)))
    start = 0
    while start < permutations:
        stop = min(start + chunk, permutations)
        signs = rng.choice(np.array([-1.0, 1.0]), size=(stop - start, n))
        perm_means = np.abs((signs * arr).mean(axis=1))
        extreme += int(np.count_nonzero(perm_means >= observed - _EPS))
        start = stop
    return (extreme + 1.0) / (permutations + 1.0)


def two_sample_pvalue(
    baseline: npt.ArrayLike,
    candidate: npt.ArrayLike,
    permutations: int = 10_000,
    seed: int | None = None,
) -> float:
    """Two-sided permutation test for a difference of independent means."""
    base = np.asarray(baseline, dtype=np.float64)
    cand = np.asarray(candidate, dtype=np.float64)
    if base.ndim != 1 or cand.ndim != 1 or base.size < 1 or cand.size < 1:
        raise ValueError("baseline and candidate must be non-empty one dimensional arrays")
    if permutations < 100:
        raise ValueError(f"permutations must be at least 100, got {permutations}")
    observed = abs(float(cand.mean() - base.mean()))
    pooled = np.concatenate([base, cand])
    if float(np.max(pooled) - np.min(pooled)) < _EPS:
        return 1.0

    rng = np.random.default_rng(seed)
    n_cand = cand.size
    n_total = pooled.size
    total = float(pooled.sum())
    extreme = 0
    chunk = max(1, min(permutations, 20_000_000 // max(n_total, 1)))
    start = 0
    while start < permutations:
        stop = min(start + chunk, permutations)
        order = np.argsort(rng.random((stop - start, n_total)), axis=1)
        shuffled = pooled[order]
        cand_sums = shuffled[:, :n_cand].sum(axis=1)
        cand_means = cand_sums / n_cand
        base_means = (total - cand_sums) / base.size
        extreme += int(np.count_nonzero(np.abs(cand_means - base_means) >= observed - _EPS))
        start = stop
    return (extreme + 1.0) / (permutations + 1.0)
