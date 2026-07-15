from statgate.__about__ import __version__
from statgate.report.errorbar import render_error_bar
from statgate.verdict import GateReport, SideSummary, Verdict

MARKER = "<!-- statgate-report -->"

_HEADLINES = {
    Verdict.SHIP: ":white_check_mark: **SHIP**",
    Verdict.BLOCK: ":no_entry: **BLOCK**",
    Verdict.INCONCLUSIVE: ":warning: **INCONCLUSIVE**",
}

_EXPLANATIONS = {
    Verdict.SHIP: (
        "The candidate is statistically non-inferior to the baseline: the entire "
        "confidence interval sits above the margin."
    ),
    Verdict.BLOCK: (
        "The regression is real: the entire confidence interval sits below the margin. "
        "This is not eval noise."
    ),
    Verdict.INCONCLUSIVE: (
        "The suite is too small to tell whether this difference is a real regression "
        "or sampling noise."
    ),
}


def _side_row(side: SideSummary) -> str:
    pass_cell = "n/a"
    if side.pass_rate is not None and side.pass_interval is not None:
        pass_cell = (
            f"{side.pass_rate:.1%} "
            f"[{side.pass_interval.low:.1%}, {side.pass_interval.high:.1%}]"
        )
    return (
        f"| {side.label} | {side.n_cases} | {side.n_records} "
        f"| {side.mean:.4f} | {pass_cell} |"
    )


def render_markdown(report: GateReport) -> str:
    """Render the gate report as GitHub flavored markdown."""
    lines = [
        MARKER,
        f"## {_HEADLINES[report.verdict]}",
        "",
        _EXPLANATIONS[report.verdict],
        "",
        "| | |",
        "|---|---|",
        f"| Metric | {report.metric} ({report.analysis}) |",
        f"| Mean difference | {report.mean_diff:+.4f} |",
        (
            f"| {report.interval.confidence:.0%} confidence interval "
            f"| [{report.interval.low:+.4f}, {report.interval.high:+.4f}] |"
        ),
        f"| Non-inferiority margin | {-report.margin:+.4f} |",
        f"| Permutation p-value | {report.p_value:.4f} |",
        f"| Paired cases | {report.n_pairs} |",
    ]
    if report.required_pairs is not None:
        lines.append(f"| Pairs needed to decide | ~{report.required_pairs} |")
    lines += [
        "",
        "```",
        render_error_bar(report.interval, report.mean_diff, report.margin),
        "```",
        "",
        "<details>",
        "<summary>Details</summary>",
        "",
        "| Side | Cases | Records | Mean | Pass rate |",
        "|---|---|---|---|---|",
        _side_row(report.baseline),
        _side_row(report.candidate),
        "",
    ]
    if report.notes:
        lines += [f"- {note}" for note in report.notes]
        lines.append("")
    lines += [
        "</details>",
        "",
        f"<sub>statgate v{__version__}</sub>",
        "",
    ]
    return "\n".join(lines)
