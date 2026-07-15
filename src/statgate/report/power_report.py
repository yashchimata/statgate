import json
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from statgate.core.power import PowerRow


@dataclass(frozen=True)
class PowerReport:
    """What the current suite can detect and what a decision would take."""

    sd: float
    alpha: float
    power: float
    n_current: int | None
    mde_current: float | None
    effect: float | None
    required_n: int | None
    rows: tuple[PowerRow, ...]


def power_report_to_dict(report: PowerReport) -> dict[str, Any]:
    return {
        "sd": report.sd,
        "alpha": report.alpha,
        "power": report.power,
        "n_current": report.n_current,
        "mde_current": report.mde_current,
        "effect": report.effect,
        "required_n": report.required_n,
        "table": [{"n": row.n, "mde": row.mde} for row in report.rows],
    }


def render_power_json(report: PowerReport) -> str:
    return json.dumps(power_report_to_dict(report), indent=2)


def render_power_markdown(report: PowerReport) -> str:
    lines = [
        "## Power analysis",
        "",
        f"Standard deviation of per-case differences: `{report.sd:.4f}` "
        f"(alpha `{report.alpha}`, power `{report.power}`)",
        "",
    ]
    if report.n_current is not None and report.mde_current is not None:
        lines += [
            f"With the current **{report.n_current}** paired cases, the smallest "
            f"regression this suite can reliably detect is **{report.mde_current:.4f}**.",
            "",
        ]
    if report.effect is not None and report.required_n is not None:
        lines += [
            f"Detecting a difference of **{report.effect:.4f}** requires about "
            f"**{report.required_n}** paired cases.",
            "",
        ]
    lines += [
        "| Suite size | Minimum detectable effect |",
        "|---|---|",
    ]
    lines += [f"| {row.n} | {row.mde:.4f} |" for row in report.rows]
    lines.append("")
    return "\n".join(lines)


def render_power_terminal(report: PowerReport, console: Console | None = None) -> None:
    console = console or Console()
    table = Table(box=None, pad_edge=False)
    table.add_column("suite size", justify="right")
    table.add_column("minimum detectable effect", justify="right")
    for row in report.rows:
        table.add_row(str(row.n), f"{row.mde:.4f}")

    lines = [
        f"sd of per-case differences: {report.sd:.4f}",
        f"alpha: {report.alpha}   power: {report.power}",
    ]
    if report.n_current is not None and report.mde_current is not None:
        lines.append(
            f"current suite ({report.n_current} pairs) can detect: {report.mde_current:.4f}"
        )
    if report.effect is not None and report.required_n is not None:
        lines.append(
            f"detecting {report.effect:.4f} requires about {report.required_n} pairs"
        )
    console.print(Panel.fit("\n".join(lines), title="power analysis"))
    console.print(table)
