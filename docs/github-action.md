# GitHub Action

The repository doubles as a composite GitHub Action that runs the gate and
posts the report to the pull request.

## Minimal setup

```yaml
name: Eval gate
on: pull_request

jobs:
  eval-gate:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Produce eval results
        run: |
          ./run_evals.sh main > baseline.jsonl
          ./run_evals.sh HEAD > candidate.jsonl

      - uses: yashchimata/statgate@main
        with:
          baseline: baseline.jsonl
          candidate: candidate.jsonl
```

The action:

1. Installs statgate into the runner's Python.
2. Runs `statgate compare` with markdown output.
3. Appends the report to the job summary.
4. Posts the report as a comment on the pull request, updating the same
   comment on subsequent pushes instead of stacking new ones.
5. Fails the check only when the verdict is BLOCK, or when the verdict is
   INCONCLUSIVE and `fail-on-inconclusive` is set.

`permissions: pull-requests: write` is required for the comment. Without
it, set `comment: "false"` and rely on the job summary.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `baseline` | required | Path to the baseline results file. |
| `candidate` | required | Path to the candidate results file. |
| `config` | none | Path to a `statgate.toml`. |
| `adapter` | `auto` | Force a results format: `jsonl`, `json`, `csv`, `promptfoo`. |
| `margin` | from config | Non-inferiority margin override. |
| `alpha` | from config | Significance level override. |
| `comment` | `true` | Post the sticky pull request comment. |
| `fail-on-inconclusive` | `false` | Treat INCONCLUSIVE as a failure. |
| `github-token` | `github.token` | Token used for the comment. |
| `python-version` | `3.12` | Python used to run statgate. |

## Outputs

| Output | Meaning |
|---|---|
| `verdict` | `SHIP`, `BLOCK`, `INCONCLUSIVE`, or `ERROR`. |
| `exit-code` | The raw statgate exit code. |

Use the outputs to build richer policies, for example allowing INCONCLUSIVE
on draft pull requests but not on release branches:

```yaml
      - uses: yashchimata/statgate@main
        id: gate
        with:
          baseline: baseline.jsonl
          candidate: candidate.jsonl
          fail-on-inconclusive: ${{ github.base_ref == 'release' }}

      - if: steps.gate.outputs.verdict == 'INCONCLUSIVE'
        run: echo "Consider growing the eval suite; see the PR comment for the required size."
```

## Where the baseline comes from

Common patterns, in increasing order of rigor:

- **Re-run on main**: check out the base branch, run the suite, then run it
  on the head branch. Costs two eval runs but is always current.
- **Cached baseline artifact**: a scheduled workflow on main runs the suite
  and uploads `baseline.jsonl` as an artifact; pull request workflows
  download it. One eval run per PR.
- **Committed baseline**: the baseline file lives in the repository and is
  refreshed deliberately. Cheapest, and the refresh commit is itself gated.

Whichever you choose, keep `case_id` values stable across runs; the paired
analysis depends on them.
