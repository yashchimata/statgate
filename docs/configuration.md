# Configuration

statgate reads configuration from a TOML file. Resolution order:

1. `--config path/to/file.toml` if given (missing file is an error)
2. `statgate.toml` in the working directory if present
3. Built-in defaults

CLI flags always override file values for that invocation.

## Full reference

```toml
[gate]
metric = "score"
alpha = 0.05
margin = 0.02
power = 0.8
resamples = 10000
permutations = 10000
seed = 42
min_pairs = 5
min_pair_fraction = 0.5

[sequential]
batch_size = 25
max_cases = 400
tau = 0.1
min_samples = 10
```

Unknown keys are rejected with an error naming the key, so typos fail loudly
instead of silently using defaults.

## [gate]

| Key | Default | Meaning |
|---|---|---|
| `metric` | `"score"` | What to gate on. `"score"` uses each record's score (falling back to the pass flag when absent). `"pass_rate"` uses the boolean pass flag and requires it on every record. |
| `alpha` | `0.05` | Significance level. The confidence interval covers `1 - alpha`. Lower alpha means fewer false blocks and more INCONCLUSIVE verdicts. |
| `margin` | `0.02` | The largest regression treated as tolerable, in metric units. The decision rule compares the confidence interval against `-margin`. Zero demands strict superiority. |
| `power` | `0.8` | Target power used for suite size recommendations in INCONCLUSIVE verdicts and in `statgate power`. |
| `resamples` | `10000` | Bootstrap resamples. 10,000 is enough for stable 95% intervals; increase for very small alpha. |
| `permutations` | `10000` | Iterations of the permutation cross-check. |
| `seed` | unset | Seed for all resampling. Set it in CI for reproducible reports. |
| `min_pairs` | `5` | Minimum matched cases for a paired analysis. Below this, statgate tries the unpaired fallback. |
| `min_pair_fraction` | `0.5` | Minimum fraction of the case universe that must match by id before the paired analysis is trusted. |

## [sequential]

| Key | Default | Meaning |
|---|---|---|
| `batch_size` | `25` | Cases evaluated between sequential looks. Batches below about 20 weaken the variance estimate. |
| `max_cases` | `400` | Hard budget. If the boundary is never crossed the verdict is INCONCLUSIVE. |
| `tau` | auto | Mixture scale of the sequential test. By default it is matched to the observed standard deviation once `min_samples` observations exist. Pin it for strict comparability across runs. |
| `min_samples` | `10` | No decision is made before this many pairs, protecting the variance estimate. |

## Choosing a margin

The margin encodes a product judgment: how much regression on this metric is
acceptable in exchange for shipping? Useful anchors:

- Set it to the score movement you would not notice in production. If a 1
  point drop on your grader has never mattered, `margin = 0.01` is honest.
- Run `statgate power` first. If your suite cannot detect effects smaller
  than 0.05, a margin of 0.01 will produce INCONCLUSIVE forever. Either
  grow the suite or widen the margin to what the suite can support.
- Ratchet over time. Teams often start with `margin = 0.05`, grow their
  suites, and tighten toward 0.01.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | SHIP |
| 1 | BLOCK |
| 2 | INCONCLUSIVE |
| 3 | Operational error (bad file, bad flags, unusable data) |

`compare` and `sequential` use the full table. `power` and `validate` use 0
for success and 3 for errors.
