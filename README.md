# statgate

Statistically calibrated ship or block CI gates for LLM evals.

[![CI](https://github.com/yashchimata/statgate/actions/workflows/ci.yml/badge.svg)](https://github.com/yashchimata/statgate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

Your eval gate is lying to you. A 2 point score drop on a 50 case suite is
almost always sampling noise, but a threshold gate treats it as a regression.
So teams either block merges on coin flips or learn to ignore the red X,
which is worse. LLM outputs are nondeterministic, eval suites are small, and
a raw pass rate comparison cannot tell signal from noise.

statgate is the statistics layer between your eval runner and your merge
button. Feed it two eval runs and it pairs cases, runs a paired bootstrap
analysis, and returns one of three verdicts:

| Verdict | Exit code | Meaning |
|---|---|---|
| `SHIP` | 0 | The candidate is statistically non-inferior to the baseline. |
| `BLOCK` | 1 | The regression is real. This is not noise. |
| `INCONCLUSIVE` | 2 | The suite is too small to tell, and statgate reports how many cases you would need. |

Operational failures (bad files, bad flags) exit with code 3, so your
pipeline can always distinguish "the gate decided" from "the gate broke".

statgate makes no LLM calls, sends no network requests, and depends only on
numpy, click, rich, and pydantic. It works with any eval runner that can
produce a results file.

## Install

```bash
pip install git+https://github.com/yashchimata/statgate
```

Or from a clone:

```bash
git clone https://github.com/yashchimata/statgate
cd statgate
pip install .
```

## Quickstart

```bash
statgate compare examples/baseline.jsonl examples/candidate.jsonl --seed 42
```

```text
+----------------------------------- SHIP ------------------------------------+
| metric                   score (paired)                                     |
| mean difference          +0.0361                                            |
| 95% confidence interval  [+0.0103, +0.0615]                                 |
| non-inferiority margin   -0.0200                                            |
| permutation p-value      0.0085                                             |
| paired cases             80                                                 |
|                                                                             |
|                         [--------------o--------------]                     |
| ......|...........|..........................................               |
| -margin (-0.02)   0                                                         |
| diff +0.0361   95% CI [+0.0103, +0.0615]                                    |
|                                                                             |
| side       cases  records    mean             pass rate                     |
| baseline      80       80  0.6676  71.2% [60.5%, 80.0%]                     |
| candidate     80       80  0.7036  78.8% [68.6%, 86.3%]                     |
+------------ candidate is statistically non-inferior to baseline ------------+
```

The repository ships example data, so you can try every command right away:

```bash
statgate compare examples/baseline.jsonl examples/regression.jsonl
statgate power --baseline examples/baseline.jsonl --candidate examples/candidate.jsonl
statgate sequential examples/baseline.jsonl examples/regression.jsonl
```

## Input formats

statgate ingests results files, not eval frameworks, so any runner works.
The format is detected from the file, or forced with `--adapter`.

**JSON Lines** (one record per line):

```json
{"case_id": "q-001", "score": 0.83, "passed": true}
{"case_id": "q-002", "score": 0.41, "passed": false, "run_index": 0}
```

`case_id` identifies the test case and must match between baseline and
candidate for the paired analysis. Either `score` or `passed` is required.
Repeated runs of the same case (via `run_index`) are averaged per case.
Unknown fields are kept as metadata. A JSON array of the same objects and a
CSV with the same columns both work too.

**promptfoo**: point statgate at the file written by
`promptfoo eval -o results.json`. Case ids are derived from test and prompt
indices, so two exports of the same suite pair cleanly.

## Commands

### `statgate compare baseline candidate`

The gate. Pairs cases by `case_id`, computes a bias-corrected and
accelerated (BCa) bootstrap confidence interval on the mean per-case
difference, cross-checks it with a paired permutation test, and applies a
non-inferiority decision rule against the configured margin. Output formats:
`terminal` (default), `markdown`, `json`. Use `--output report.md` to write
the report to a file.

When baseline and candidate share too few case ids, statgate falls back to
an unpaired comparison and says so in the report. Pairing is worth
preserving: a paired analysis typically needs 3 to 10 times fewer cases for
the same certainty.

### `statgate power`

Tells you what your suite can actually detect, before you trust it.

```bash
statgate power --baseline examples/baseline.jsonl --candidate examples/candidate.jsonl
```

```text
+-------------- power analysis ---------------+
| sd of per-case differences: 0.1180          |
| alpha: 0.05   power: 0.8                    |
| current suite (80 pairs) can detect: 0.0370 |
| detecting 0.0200 requires about 274 pairs   |
+---------------------------------------------+
suite size  minimum detectable effect
        25                     0.0661
        50                     0.0468
       100                     0.0331
       200                     0.0234
       400                     0.0165
       800                     0.0117
```

If an INCONCLUSIVE verdict keeps recurring, this command turns suite sizing
from folklore into arithmetic. It also works without data via `--sd`.

### `statgate sequential baseline candidate`

Runs the comparison through always-valid sequential boundaries (a mixture
sequential probability ratio test) so the run can stop the moment the
verdict is statistically clear, instead of paying for the full suite every
time. Two modes:

Replay mode analyzes existing files batch by batch and shows where the run
could have stopped:

```bash
statgate sequential baseline.jsonl candidate.jsonl --batch-size 25
```

Live mode drives your eval command one batch at a time and stops early. The
template may reference `{start}` and `{count}`:

```bash
statgate sequential baseline.jsonl candidate.jsonl \
  --run "python run_eval.py --offset {start} --limit {count} --out candidate.jsonl"
```

On clearly better or clearly worse candidates this typically saves half or
more of the eval budget, which is real money when every case is an LLM call.

### `statgate validate results-file`

Parses a results file, reports what it found, and exits non-zero if the file
is unusable. Useful as a cheap pre-flight check in CI.

## GitHub Action

```yaml
jobs:
  eval-gate:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - name: Run evals
        run: ./run_evals.sh   # produces baseline.jsonl and candidate.jsonl
      - uses: yashchimata/statgate@main
        with:
          baseline: baseline.jsonl
          candidate: candidate.jsonl
```

The action posts a sticky comment on the pull request with the verdict and
error bars, updates it in place on every push, writes the report to the job
summary, and fails the check only on BLOCK (or on INCONCLUSIVE if you set
`fail-on-inconclusive: true`). See [docs/github-action.md](docs/github-action.md)
for all inputs.

## Configuration

statgate reads `statgate.toml` from the working directory, or from
`--config path`. The most common values can also be overridden with CLI
flags such as `--margin`, `--alpha`, `--metric`, and `--seed`.

```toml
[gate]
metric = "score"        # or "pass_rate"
alpha = 0.05            # significance level; confidence is 1 - alpha
margin = 0.02           # regression size you are willing to tolerate
power = 0.8             # target power for suite size recommendations
resamples = 10000       # bootstrap resamples
permutations = 10000    # permutation test iterations
seed = 42               # set for fully reproducible reports

[sequential]
batch_size = 25
max_cases = 400
```

The margin is the heart of the policy. `margin = 0.02` means "block only
when we are confident the candidate is more than 2 points worse". A margin
of zero demands proof of strict improvement, which small suites can rarely
provide. Details in [docs/configuration.md](docs/configuration.md).

## How the statistics work

Short version: per-case paired differences, a BCa bootstrap confidence
interval on their mean, a sign-flip permutation test as a cross-check, a
non-inferiority decision rule, normal-approximation power analysis, and a
mixture SPRT for always-valid sequential stopping. Cases are the resampling
unit, so repeated runs of the same case are never mistaken for independent
evidence.

The long version, with the reasoning behind each choice and the known
limitations, is in [docs/methodology.md](docs/methodology.md). The test
suite includes calibration checks that verify interval coverage and false
positive rates against synthetic data with known ground truth.

## Development

```bash
git clone https://github.com/yashchimata/statgate
cd statgate
python -m venv .venv && . .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src
```

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
