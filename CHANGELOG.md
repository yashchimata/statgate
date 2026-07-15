# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-14

### Added

- `statgate compare`: paired BCa bootstrap gate with SHIP, BLOCK, and
  INCONCLUSIVE verdicts, non-inferiority margins, permutation cross-check,
  and unpaired fallback when case ids do not align.
- `statgate power`: minimum detectable effect and required suite size
  analysis, from data or from a known standard deviation.
- `statgate sequential`: always-valid mixture SPRT boundaries with replay
  mode and live batch-driving mode for early stopping.
- `statgate validate`: pre-flight check for results files.
- Adapters: JSON Lines, JSON array, CSV, and promptfoo results files, with
  automatic format detection.
- Renderers: terminal (rich), GitHub-flavored markdown with ASCII error
  bars, and JSON.
- Composite GitHub Action with sticky pull request comments, job summary
  output, and verdict-based check enforcement.
- Configuration via `statgate.toml` with full CLI overrides.
- Exit code contract: 0 SHIP, 1 BLOCK, 2 INCONCLUSIVE, 3 operational error.
