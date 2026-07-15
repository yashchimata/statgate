import sys
from pathlib import Path
from typing import Any

import click
import numpy as np
from rich.console import Console

from statgate.__about__ import __version__
from statgate.adapters import ADAPTER_NAMES, load_records
from statgate.config import Config, apply_overrides, load_config
from statgate.core.pairing import build_paired
from statgate.core.power import (
    DEFAULT_SIZES,
    minimum_detectable_effect,
    power_table,
    required_sample_size,
)
from statgate.errors import StatgateError
from statgate.report import render_json, render_markdown, render_terminal
from statgate.report.power_report import (
    PowerReport,
    render_power_json,
    render_power_markdown,
    render_power_terminal,
)
from statgate.report.sequential_report import (
    render_sequential_json,
    render_sequential_markdown,
    render_sequential_terminal,
)
from statgate.sequential_runner import run_live, run_replay
from statgate.verdict import GateReport, evaluate_gate

ERROR_EXIT_CODE = 3

_adapter_option = click.option(
    "--adapter",
    type=click.Choice(ADAPTER_NAMES),
    default="auto",
    show_default=True,
    help="Results file format.",
)
_config_option = click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to statgate.toml. Defaults to ./statgate.toml when present.",
)
_format_option = click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "markdown", "json"]),
    default="terminal",
    show_default=True,
    help="Output format.",
)
_metric_option = click.option(
    "--metric",
    type=click.Choice(["score", "pass_rate"]),
    default=None,
    help="Metric to gate on, overriding the config file.",
)
_alpha_option = click.option(
    "--alpha",
    type=click.FloatRange(0.0, 1.0, min_open=True, max_open=True),
    default=None,
    help="Significance level, overriding the config file.",
)
_margin_option = click.option(
    "--margin",
    type=click.FloatRange(min=0.0),
    default=None,
    help="Non-inferiority margin, overriding the config file.",
)


def _gate_overrides(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _load_gate_settings(config_path: Path | None, **overrides: Any) -> Config:
    return apply_overrides(load_config(config_path), gate=_gate_overrides(**overrides))


def _emit(content: str, output: Path | None) -> None:
    if output is None:
        click.echo(content)
    else:
        try:
            output.write_text(content, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise StatgateError(f"could not write report to {output}: {exc}") from exc


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="statgate")
def cli() -> None:
    """Statistically calibrated ship or block CI gates for LLM evals.

    Exit codes for compare and sequential: 0 SHIP, 1 BLOCK,
    2 INCONCLUSIVE, 3 operational error.
    """


@cli.command()
@click.argument("baseline", type=click.Path(path_type=Path))
@click.argument("candidate", type=click.Path(path_type=Path))
@_adapter_option
@_config_option
@_format_option
@_metric_option
@_alpha_option
@_margin_option
@click.option(
    "--seed",
    type=click.IntRange(min=0),
    default=None,
    help="Seed for reproducible resampling.",
)
@click.option("--resamples", type=click.IntRange(min=100), default=None)
@click.option("--permutations", type=click.IntRange(min=100), default=None)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the report to a file instead of stdout.",
)
def compare(
    baseline: Path,
    candidate: Path,
    adapter: str,
    config_path: Path | None,
    output_format: str,
    metric: str | None,
    alpha: float | None,
    margin: float | None,
    seed: int | None,
    resamples: int | None,
    permutations: int | None,
    output: Path | None,
) -> None:
    """Compare two eval runs and decide SHIP, BLOCK, or INCONCLUSIVE."""
    config = _load_gate_settings(
        config_path,
        metric=metric,
        alpha=alpha,
        margin=margin,
        seed=seed,
        resamples=resamples,
        permutations=permutations,
    )
    baseline_records = load_records(baseline, adapter)
    candidate_records = load_records(candidate, adapter)
    report = evaluate_gate(baseline_records, candidate_records, config.gate)
    _render_gate_report(report, output_format, output)
    sys.exit(report.exit_code)


def _render_gate_report(report: GateReport, output_format: str, output: Path | None) -> None:
    if output_format == "terminal":
        if output is None:
            render_terminal(report)
        else:
            try:
                with output.open("w", encoding="utf-8") as handle:
                    render_terminal(report, Console(file=handle, no_color=True, width=100))
            except OSError as exc:
                raise StatgateError(f"could not write report to {output}: {exc}") from exc
    elif output_format == "markdown":
        _emit(render_markdown(report), output)
    else:
        _emit(render_json(report), output)
    if output is not None:
        click.echo(
            f"verdict: {report.verdict.value} "
            f"(mean diff {report.mean_diff:+.4f}, "
            f"CI [{report.interval.low:+.4f}, {report.interval.high:+.4f}]); "
            f"report written to {output}"
        )


@cli.command()
@click.option(
    "--baseline",
    type=click.Path(path_type=Path),
    default=None,
    help="Baseline results file, paired with --candidate to estimate sd.",
)
@click.option(
    "--candidate",
    type=click.Path(path_type=Path),
    default=None,
    help="Candidate results file, paired with --baseline to estimate sd.",
)
@click.option(
    "--sd",
    type=click.FloatRange(min=0.0),
    default=None,
    help="Known sd of per-case differences.",
)
@click.option(
    "--n",
    "n_current",
    type=click.IntRange(min=2),
    default=None,
    help="Current suite size in paired cases.",
)
@click.option(
    "--effect",
    type=click.FloatRange(min=0.0, min_open=True),
    default=None,
    help="Target effect size to detect.",
)
@click.option("--sizes", default=None, help="Comma separated suite sizes for the table.")
@_adapter_option
@_config_option
@_format_option
@_metric_option
@_alpha_option
@click.option(
    "--power",
    "power_target",
    type=click.FloatRange(0.0, 1.0, min_open=True, max_open=True),
    default=None,
    help="Target statistical power, overriding the config file.",
)
def power(
    baseline: Path | None,
    candidate: Path | None,
    sd: float | None,
    n_current: int | None,
    effect: float | None,
    sizes: str | None,
    adapter: str,
    config_path: Path | None,
    output_format: str,
    metric: str | None,
    alpha: float | None,
    power_target: float | None,
) -> None:
    """Report what regressions the eval suite can actually detect."""
    config = _load_gate_settings(
        config_path, metric=metric, alpha=alpha, power=power_target
    )
    gate = config.gate

    if (baseline is None) != (candidate is None):
        raise click.UsageError("--baseline and --candidate must be provided together")
    if baseline is not None and candidate is not None:
        baseline_records = load_records(baseline, adapter)
        candidate_records = load_records(candidate, adapter)
        paired = build_paired(baseline_records, candidate_records, gate.metric)
        if paired.n_pairs < 2:
            raise click.UsageError(
                f"only {paired.n_pairs} paired cases; power analysis needs at least 2"
            )
        sd = float(np.std(paired.diffs, ddof=1))
        if n_current is None:
            n_current = paired.n_pairs
    if sd is None:
        raise click.UsageError("provide either --sd or both --baseline and --candidate")

    parsed_sizes: tuple[int, ...] = DEFAULT_SIZES
    if sizes is not None:
        try:
            parsed_sizes = tuple(sorted({int(part) for part in sizes.split(",") if part.strip()}))
        except ValueError as exc:
            raise click.UsageError(f"cannot parse --sizes {sizes!r}: {exc}") from exc
        if not parsed_sizes or any(n < 2 for n in parsed_sizes):
            raise click.UsageError("--sizes must contain integers of at least 2")

    target_effect = effect if effect is not None else (gate.margin if gate.margin > 0 else None)
    report = PowerReport(
        sd=sd,
        alpha=gate.alpha,
        power=gate.power,
        n_current=n_current,
        mde_current=(
            minimum_detectable_effect(sd, n_current, gate.alpha, gate.power)
            if n_current is not None
            else None
        ),
        effect=target_effect,
        required_n=(
            required_sample_size(sd, target_effect, gate.alpha, gate.power)
            if target_effect is not None and sd > 0
            else None
        ),
        rows=tuple(power_table(sd, parsed_sizes, gate.alpha, gate.power)),
    )
    if output_format == "terminal":
        render_power_terminal(report)
    elif output_format == "markdown":
        click.echo(render_power_markdown(report))
    else:
        click.echo(render_power_json(report))


@cli.command()
@click.argument("baseline", type=click.Path(path_type=Path))
@click.argument("candidate", type=click.Path(path_type=Path))
@click.option(
    "--run",
    "run_template",
    default=None,
    help=(
        "Shell command that produces the next batch of results. "
        "May reference {start} and {count}. Without --run, existing "
        "results are replayed through the sequential boundaries."
    ),
)
@_adapter_option
@_config_option
@_format_option
@_metric_option
@_alpha_option
@_margin_option
@click.option("--tau", type=click.FloatRange(min=0.0, min_open=True), default=None)
@click.option("--batch-size", type=click.IntRange(min=1), default=None)
@click.option("--max-cases", type=click.IntRange(min=2), default=None)
def sequential(
    baseline: Path,
    candidate: Path,
    run_template: str | None,
    adapter: str,
    config_path: Path | None,
    output_format: str,
    metric: str | None,
    alpha: float | None,
    margin: float | None,
    tau: float | None,
    batch_size: int | None,
    max_cases: int | None,
) -> None:
    """Stop the eval run early once the verdict is statistically clear."""
    config = _load_gate_settings(config_path, metric=metric, alpha=alpha, margin=margin)
    config = apply_overrides(
        config,
        sequential=_gate_overrides(tau=tau, batch_size=batch_size, max_cases=max_cases),
    )

    if run_template is None:
        baseline_records = load_records(baseline, adapter)
        candidate_records = load_records(candidate, adapter)
        outcome = run_replay(
            baseline_records, candidate_records, config.gate, config.sequential
        )
    else:
        outcome = run_live(
            run_template, baseline, candidate, adapter, config.gate, config.sequential
        )

    if output_format == "terminal":
        render_sequential_terminal(outcome)
    elif output_format == "markdown":
        click.echo(render_sequential_markdown(outcome))
    else:
        click.echo(render_sequential_json(outcome))
    sys.exit(outcome.exit_code)


@cli.command()
@click.argument("results", type=click.Path(path_type=Path))
@_adapter_option
def validate(results: Path, adapter: str) -> None:
    """Check that a results file parses and summarize its contents."""
    records = load_records(results, adapter)
    cases = {record.case_id for record in records}
    runs_per_case: dict[str, int] = {}
    for record in records:
        runs_per_case[record.case_id] = runs_per_case.get(record.case_id, 0) + 1
    with_score = sum(1 for record in records if record.score is not None)
    with_passed = sum(1 for record in records if record.passed is not None)
    max_runs = max(runs_per_case.values())

    click.echo(f"{results}: OK")
    click.echo(f"  records: {len(records)}")
    click.echo(f"  distinct cases: {len(cases)}")
    click.echo(f"  records per case: {min(runs_per_case.values())} to {max_runs}")
    click.echo(f"  with score: {with_score}")
    click.echo(f"  with passed flag: {with_passed}")
    if max_runs > 1:
        click.echo(
            "  note: repeated records per case are averaged into one value per case"
        )


def main() -> None:
    """Console entry point with distinct exit codes for errors."""
    try:
        result = cli.main(standalone_mode=False)
    except SystemExit:
        raise
    except click.ClickException as exc:
        exc.show()
        sys.exit(ERROR_EXIT_CODE)
    except click.exceptions.Abort:
        click.echo("aborted", err=True)
        sys.exit(ERROR_EXIT_CODE)
    except StatgateError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(ERROR_EXIT_CODE)
    except Exception as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(ERROR_EXIT_CODE)
    sys.exit(result if isinstance(result, int) else 0)
