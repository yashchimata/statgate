from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from statgate.report.errorbar import render_error_bar
from statgate.verdict import GateReport, SideSummary, Verdict

_STYLES = {
    Verdict.SHIP: "bold green",
    Verdict.BLOCK: "bold red",
    Verdict.INCONCLUSIVE: "bold yellow",
}

_SUBTITLES = {
    Verdict.SHIP: "candidate is statistically non-inferior to baseline",
    Verdict.BLOCK: "the regression is real, not eval noise",
    Verdict.INCONCLUSIVE: "the suite is too small to tell signal from noise",
}


def _stats_table(report: GateReport) -> Table:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="dim")
    table.add_column()
    table.add_row("metric", f"{report.metric} ({report.analysis})")
    table.add_row("mean difference", f"{report.mean_diff:+.4f}")
    table.add_row(
        f"{report.interval.confidence:.0%} confidence interval",
        f"[{report.interval.low:+.4f}, {report.interval.high:+.4f}]",
    )
    table.add_row("non-inferiority margin", f"{-report.margin:+.4f}")
    table.add_row("permutation p-value", f"{report.p_value:.4f}")
    table.add_row("paired cases", str(report.n_pairs))
    if report.required_pairs is not None:
        table.add_row("pairs needed to decide", f"~{report.required_pairs}")
    return table


def _sides_table(report: GateReport) -> Table:
    table = Table(box=None, pad_edge=False)
    table.add_column("side", style="dim")
    table.add_column("cases", justify="right")
    table.add_column("records", justify="right")
    table.add_column("mean", justify="right")
    table.add_column("pass rate", justify="right")

    def row(side: SideSummary) -> tuple[str, str, str, str, str]:
        pass_cell = "n/a"
        if side.pass_rate is not None and side.pass_interval is not None:
            pass_cell = (
                f"{side.pass_rate:.1%} "
                f"[{side.pass_interval.low:.1%}, {side.pass_interval.high:.1%}]"
            )
        return (
            side.label,
            str(side.n_cases),
            str(side.n_records),
            f"{side.mean:.4f}",
            pass_cell,
        )

    table.add_row(*row(report.baseline))
    table.add_row(*row(report.candidate))
    return table


def render_terminal(report: GateReport, console: Console | None = None) -> None:
    """Print the gate report to the terminal."""
    console = console or Console()
    style = _STYLES[report.verdict]
    body: list[RenderableType] = [
        _stats_table(report),
        Text(""),
        Text(render_error_bar(report.interval, report.mean_diff, report.margin)),
        Text(""),
        _sides_table(report),
    ]
    if report.notes:
        body.append(Text(""))
        for note in report.notes:
            body.append(Text(f"note: {note}", style="dim"))
    console.print(
        Panel(
            Group(*body),
            title=f"[{_STYLES[report.verdict]}]{report.verdict.value}[/]",
            subtitle=_SUBTITLES[report.verdict],
            border_style=style.replace("bold ", ""),
        )
    )
