import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from statgate.sequential_runner import SequentialOutcome
from statgate.verdict import Verdict

_STYLES = {
    Verdict.SHIP: "green",
    Verdict.BLOCK: "red",
    Verdict.INCONCLUSIVE: "yellow",
}


def sequential_to_dict(outcome: SequentialOutcome) -> dict[str, Any]:
    return {
        "verdict": outcome.verdict.value,
        "exit_code": outcome.exit_code,
        "pairs_used": outcome.pairs_used,
        "pairs_available": outcome.pairs_available,
        "max_cases": outcome.max_cases,
        "saved_fraction": outcome.saved_fraction,
        "theta0": outcome.theta0,
        "batches": [
            {
                "batch": snap.batch,
                "n_pairs": snap.n_pairs,
                "mean_diff": snap.mean_diff,
                "p_value": snap.p_value,
                "decided": snap.decided,
            }
            for snap in outcome.snapshots
        ],
        "notes": list(outcome.notes),
    }


def render_sequential_json(outcome: SequentialOutcome) -> str:
    return json.dumps(sequential_to_dict(outcome), indent=2)


def render_sequential_markdown(outcome: SequentialOutcome) -> str:
    lines = [
        f"## Sequential verdict: **{outcome.verdict.value}**",
        "",
        f"Decided after **{outcome.pairs_used}** of up to "
        f"**{min(outcome.pairs_available, outcome.max_cases)}** pairs "
        f"({outcome.saved_fraction:.0%} of the budget saved).",
        "",
        "| Batch | Pairs | Mean diff | Always-valid p |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {snap.batch} | {snap.n_pairs} | {snap.mean_diff:+.4f} | {snap.p_value:.4f} |"
        for snap in outcome.snapshots
    ]
    if outcome.notes:
        lines.append("")
        lines += [f"- {note}" for note in outcome.notes]
    lines.append("")
    return "\n".join(lines)


def render_sequential_terminal(
    outcome: SequentialOutcome, console: Console | None = None
) -> None:
    console = console or Console()
    table = Table(box=None, pad_edge=False)
    table.add_column("batch", justify="right")
    table.add_column("pairs", justify="right")
    table.add_column("mean diff", justify="right")
    table.add_column("always-valid p", justify="right")
    for snap in outcome.snapshots:
        style = "bold" if snap.decided else ""
        table.add_row(
            str(snap.batch),
            str(snap.n_pairs),
            f"{snap.mean_diff:+.4f}",
            f"{snap.p_value:.4f}",
            style=style,
        )

    summary = (
        f"stopped after {outcome.pairs_used} pairs "
        f"(budget {min(outcome.pairs_available, outcome.max_cases)}, "
        f"saved {outcome.saved_fraction:.0%})"
    )
    body_lines = [summary]
    body_lines += [f"note: {note}" for note in outcome.notes]
    console.print(
        Panel.fit(
            "\n".join(body_lines),
            title=f"[bold {_STYLES[outcome.verdict]}]{outcome.verdict.value}[/]",
            border_style=_STYLES[outcome.verdict],
        )
    )
    console.print(table)
