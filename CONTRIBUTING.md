# Contributing

Thanks for your interest in improving statgate.

## Setup

```bash
git clone https://github.com/yashchimata/statgate
cd statgate
python -m venv .venv
. .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
pytest
ruff check src tests
mypy src
```

All three must pass. CI runs the test suite on Linux across Python 3.11 to
3.13 and on Windows with Python 3.12, plus ruff and mypy on Linux.

## What makes a good contribution here

- **New adapters** are the most valuable additions: a parser for another
  eval runner's output format, with fixture files and tests, makes statgate
  useful to a whole new group. Keep adapters thin; they translate into
  `EvalRecord` and nothing else.
- **Statistical changes** need evidence. If you touch anything in
  `statgate/core/`, include or extend a calibration test that demonstrates
  coverage or error rates on synthetic data with known ground truth. A
  method that cannot be validated that way does not belong in the core.
- **Report improvements** should keep all three renderers (terminal,
  markdown, JSON) consistent with each other.

## Design rules the project holds to

- No LLM calls, no network calls, no telemetry. The gate must be auditable
  and runnable anywhere.
- Runtime dependencies stay minimal (numpy, click, rich, pydantic).
- Every public function is typed; `mypy` runs in strict mode.
- Exit codes are a contract: 0 SHIP, 1 BLOCK, 2 INCONCLUSIVE, 3 error.
  Nothing may repurpose them.

## How changes land

The `main` branch is protected. Every change, including from the
maintainer, is expected to arrive as a pull request that:

1. passes all required CI checks (lint, the full test matrix, and the
   action smoke test),
2. is approved by a code owner (currently @yashchimata), and
3. lands as a squash merge, keeping history linear.

Force pushes and branch deletion on `main` are disabled. Release tags
(`v*`) cannot be deleted or moved. Workflows run with read-only tokens
unless a job explicitly requests more, and publishing to PyPI requires a
manual approval on the `pypi` environment on top of CI.

First-time contributors will see "workflow awaiting approval" on their
pull request; a maintainer approves the run after a quick look at the
diff. This is a standard defense for public repositories, not a judgment
of your change.

## Reporting bugs

Include the statgate version (`statgate --version`), the command you ran,
and if possible a minimal results file that reproduces the issue. If the
data is sensitive, `statgate validate` output plus the record count is
usually enough to start.
