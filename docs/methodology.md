# Methodology

This document explains the statistical machinery behind each statgate
command, why each method was chosen, and where the guarantees have limits.

## The problem statgate solves

An eval score is a sample statistic. Run the same suite twice against the
same model and the pass rate moves, because LLM outputs are stochastic and
graders are imperfect. A CI gate that compares two raw numbers ("baseline
scored 0.84, candidate scored 0.82, fail") is testing the noise as much as
the model. With a 50 case suite, the standard error of a pass rate near 80%
is about 5.7 percentage points. Score movements smaller than that are
routine even when nothing changed.

The result in practice is a flaky gate, and flaky gates train teams to click
"re-run" or to ignore the check entirely. statgate replaces the raw
comparison with an explicit statistical decision.

## Pairing

`compare` aligns baseline and candidate records by `case_id` and computes
one difference per case. Pairing removes the between-case variance from the
comparison: hard cases are hard in both runs, so their difficulty cancels,
and only the change between runs remains. For typical eval suites this cuts
the sample size needed for a decision by a factor of 3 to 10 compared with
treating the two runs as independent samples.

Repeated runs of the same case (`run_index`) are averaged into one value per
case before any analysis. Cases, not runs, are the independent unit: two
runs of the same case share the case's difficulty and are correlated, and
treating them as independent evidence would make every interval too narrow.
This is a clustered analysis with cases as clusters.

When fewer than `min_pairs` cases match, or the matched fraction falls below
`min_pair_fraction`, statgate falls back to an unpaired comparison of
independent means, states this in the report, and uses methods suited to
that design. Unpaired analysis needs far more data for the same certainty,
which the report also says.

## The confidence interval

The interval on the mean per-case difference comes from a bias-corrected
and accelerated (BCa) bootstrap with 10,000 resamples by default. Reasons
for this choice:

- Per-case differences are usually not normal. They are bounded, often
  multimodal (many zeros, a few large swings), and skewed. The bootstrap
  does not assume a shape.
- Plain percentile bootstrap intervals are biased when the statistic's
  distribution is skewed. BCa corrects both the median bias (the z0
  correction, estimated from the fraction of resamples below the observed
  mean) and the skew (the acceleration term, estimated by jackknife).
- At eval suite sizes (tens to a few hundred cases) these corrections
  matter. The test suite verifies empirical coverage against synthetic
  normal and heavily skewed data.

Degenerate inputs (all differences identical) produce a zero-width interval
rather than a crash, with a note in the report.

## The decision rule

statgate frames the gate as a non-inferiority test, not a superiority test.
The configured `margin` is the largest regression you are willing to
tolerate; the default 0.02 means "up to 2 points worse is acceptable noise
tolerance, anything beyond that must be blocked".

With the confidence interval `[low, high]` on the mean difference
(candidate minus baseline):

- `low > -margin`: the whole interval sits in acceptable territory. SHIP.
- `high < -margin`: the whole interval sits in regression territory. BLOCK.
- otherwise: INCONCLUSIVE.

Superiority gating (`margin = 0`) is supported but rarely what CI wants:
requiring statistical proof that every merge strictly improves the metric
blocks nearly all neutral changes on realistic suite sizes.

The three-state verdict is deliberate. Collapsing INCONCLUSIVE into either
pass or fail is how gates become either useless or hated. statgate instead
reports the suite size that would have been needed, so the team can make an
informed call and fix the suite.

## The permutation cross-check

Alongside the interval, `compare` reports a two-sided paired permutation
test (sign-flip test). Under the null hypothesis that nothing changed, each
per-case difference is symmetric around zero, so flipping its sign is as
likely as not. The p-value is the fraction of random sign assignments whose
mean is at least as extreme as the observed one, computed with the standard
add-one correction so it is never exactly zero.

The permutation test is exact under weaker assumptions than the bootstrap
and serves as an independent check: a tiny p-value with an interval that
straddles the margin usually means the effect is real but smaller than the
margin, which is exactly the nuance a raw threshold cannot express.

## Power analysis

`power` uses the standard normal approximation for a paired two-sided test.
The minimum detectable effect at suite size n is

```
MDE(n) = (z(1 - alpha/2) + z(power)) * sd / sqrt(n)
```

where `sd` is the standard deviation of per-case differences, estimated
from data when two files are given. The required sample size inverts the
same formula. This is an approximation (it ignores the estimation error in
sd itself), but at the suite sizes where the answer matters the
approximation error is small compared to the effect being studied, and the
formula has the virtue of being auditable by anyone.

The practical value is the framing: "your 40 cases can only detect a 15
point regression at 80% power" converts an argument about feelings into an
argument about arithmetic.

## Sequential testing

`sequential` implements a mixture sequential probability ratio test
(mixture SPRT) on the running mean of paired differences, anchored at
`theta0 = -margin`:

```
Lambda_n = sqrt(sigma^2 / (sigma^2 + n * tau^2))
           * exp(n^2 * tau^2 * (mean - theta0)^2 / (2 * sigma^2 * (sigma^2 + n * tau^2)))
```

The running p-value is the minimum of `1 / Lambda_n` across looks. The
mixture construction is what allows peeking after every batch without the
false positive inflation that repeated fixed-n tests suffer. When the
p-value drops below alpha, the test stops: mean above `theta0` ships,
below it blocks.

Three honest caveats:

- With `tau` fixed in advance and the variance known, this construction is
  exactly anytime-valid. statgate estimates the variance from the data at
  every look and, unless `--tau` is given, chooses `tau` from the early
  data too, so the guarantee is approximate rather than exact. The test
  suite checks the realized false positive rate under optional stopping
  and it sits at or below alpha in simulation.
- The mixture scale `tau` trades early sensitivity against asymptotic
  sharpness. Pin it with `--tau` for strict comparability across runs.
- Batches with no spread carry no evidence. If every difference observed
  so far is identical, the test waits for informative data instead of
  concluding anything from a variance of zero; a run whose differences
  never vary at all ends INCONCLUSIVE rather than deciding on faith.

The payoff is direct: on clearly better or clearly worse candidates the run
stops after a fraction of the suite, and every case not run is tokens not
bought.

## Pass rates

Side summaries report each run's pass rate with a Wilson score interval.
Unlike the textbook normal interval, Wilson behaves correctly for small
samples and rates near 0 or 1, which is the common regime for eval pass
rates. The gate itself operates on the chosen metric (`score` by default,
`pass_rate` to gate on the pass flag), always through the paired machinery
above.

## Reproducibility

Set `seed` in the config or `--seed` on the command line and every
resampling procedure becomes deterministic: identical inputs produce
identical reports. CI configurations should set it.

## Known limitations

- The unpaired fallback is a blunt instrument. If your runner cannot emit
  stable case ids, fixing that is worth more than any statistics.
- Bootstrap and permutation methods assume cases are exchangeable. If your
  suite mixes strata with very different behavior (say, easy smoke tests
  and a hard adversarial set), a per-stratum gate is more informative than
  one pooled verdict.
- The sequential test's approximation degrades if batch sizes are tiny and
  the score distribution is extremely heavy-tailed; prefer batches of 20 or
  more cases.
- statgate quantifies sampling noise. It cannot detect that your grader is
  systematically wrong, that your suite stopped covering what users do, or
  that the metric is saturated. Statistics after judgment, not instead of it.
