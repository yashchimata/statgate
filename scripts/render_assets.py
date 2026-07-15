"""Regenerate the SVG terminal screenshots embedded in the README.

Run from the repository root with the project installed:

    python scripts/render_assets.py

Every image is produced from real statgate output on the data in
examples/, so the assets never drift from actual behavior.
"""

from pathlib import Path

import numpy as np
from rich.console import Console

from statgate.adapters import load_records
from statgate.config import GateSettings, SequentialSettings
from statgate.core.pairing import build_paired
from statgate.core.power import (
    minimum_detectable_effect,
    power_table,
    required_sample_size,
)
from statgate.report.power_report import PowerReport, render_power_terminal
from statgate.report.sequential_report import render_sequential_terminal
from statgate.report.terminal import render_terminal
from statgate.sequential_runner import run_replay
from statgate.verdict import evaluate_gate

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SETTINGS = GateSettings(seed=42)


def fresh_console() -> Console:
    return Console(record=True, width=90, force_terminal=True, color_system="truecolor")


def save(console: Console, name: str) -> None:
    console.save_svg(str(ASSETS / name), title="statgate")
    print(f"wrote assets/{name}")


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    baseline = load_records(ROOT / "examples" / "baseline.jsonl")
    candidate = load_records(ROOT / "examples" / "candidate.jsonl")
    regression = load_records(ROOT / "examples" / "regression.jsonl")

    console = fresh_console()
    console.print(
        "[bold green]$[/] statgate compare baseline.jsonl candidate.jsonl", highlight=False
    )
    render_terminal(evaluate_gate(baseline, candidate, SETTINGS), console)
    save(console, "compare-ship.svg")

    console = fresh_console()
    console.print(
        "[bold green]$[/] statgate compare baseline.jsonl regression.jsonl", highlight=False
    )
    render_terminal(evaluate_gate(baseline, regression, SETTINGS), console)
    save(console, "compare-block.svg")

    console = fresh_console()
    console.print(
        "[bold green]$[/] statgate power --baseline baseline.jsonl --candidate candidate.jsonl",
        highlight=False,
    )
    paired = build_paired(baseline, candidate, "score")
    sd = float(np.std(paired.diffs, ddof=1))
    report = PowerReport(
        sd=sd,
        alpha=SETTINGS.alpha,
        power=SETTINGS.power,
        n_current=paired.n_pairs,
        mde_current=minimum_detectable_effect(sd, paired.n_pairs),
        effect=SETTINGS.margin,
        required_n=required_sample_size(sd, SETTINGS.margin),
        rows=tuple(power_table(sd)),
    )
    render_power_terminal(report, console)
    save(console, "power.svg")

    console = fresh_console()
    console.print(
        "[bold green]$[/] statgate sequential baseline.jsonl regression.jsonl --batch-size 20",
        highlight=False,
    )
    outcome = run_replay(
        baseline, regression, SETTINGS, SequentialSettings(batch_size=20, max_cases=400)
    )
    render_sequential_terminal(outcome, console)
    save(console, "sequential.svg")


if __name__ == "__main__":
    main()
