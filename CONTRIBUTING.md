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

## Reporting bugs

Include the statgate version (`statgate --version`), the command you ran,
and if possible a minimal results file that reproduces the issue. If the
data is sensitive, `statgate validate` output plus the record count is
usually enough to start.
