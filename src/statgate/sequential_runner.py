import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from statgate.adapters import load_records
from statgate.config import GateSettings, SequentialSettings
from statgate.core.pairing import build_paired
from statgate.core.sequential import MixtureSPRT
from statgate.errors import AnalysisError
from statgate.records import EvalRecord
from statgate.verdict import EXIT_CODES, Verdict


@dataclass(frozen=True)
class BatchSnapshot:
    """State of the sequential test after one batch."""

    batch: int
    n_pairs: int
    mean_diff: float
    p_value: float
    decided: bool


@dataclass(frozen=True)
class SequentialOutcome:
    """Final result of a sequential comparison."""

    verdict: Verdict
    snapshots: tuple[BatchSnapshot, ...]
    pairs_used: int
    pairs_available: int
    max_cases: int
    theta0: float
    notes: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]

    @property
    def saved_fraction(self) -> float:
        ceiling = min(self.pairs_available, self.max_cases)
        if ceiling <= 0:
            return 0.0
        return max(0.0, 1.0 - self.pairs_used / ceiling)


def _verdict_from_direction(decided: bool, direction: int) -> Verdict:
    if not decided:
        return Verdict.INCONCLUSIVE
    return Verdict.SHIP if direction > 0 else Verdict.BLOCK


def run_replay(
    baseline_records: Sequence[EvalRecord],
    candidate_records: Sequence[EvalRecord],
    gate: GateSettings,
    sequential: SequentialSettings,
) -> SequentialOutcome:
    """Replay already collected results through the sequential boundaries.

    Shows where the comparison would have stopped had it been run
    sequentially, and how many cases that would have saved. The test is
    anchored at ``theta0 = -margin``: stopping above it ships, stopping
    below it blocks.
    """
    paired = build_paired(baseline_records, candidate_records, gate.metric, order="sorted")
    if paired.n_pairs < sequential.min_samples:
        raise AnalysisError(
            f"sequential mode needs at least {sequential.min_samples} paired cases, "
            f"found {paired.n_pairs}"
        )
    theta0 = -gate.margin
    sprt = MixtureSPRT(
        theta0=theta0,
        alpha=gate.alpha,
        tau=sequential.tau,
        min_samples=sequential.min_samples,
    )
    diffs = paired.diffs
    limit = min(paired.n_pairs, sequential.max_cases)
    snapshots: list[BatchSnapshot] = []
    consumed = 0
    batch_number = 0
    decided = False
    direction = 0
    while consumed < limit and not decided:
        batch_number += 1
        stop = min(consumed + sequential.batch_size, limit)
        decision = sprt.update(diffs[consumed:stop])
        consumed = stop
        decided = decision.decided
        direction = decision.direction
        snapshots.append(
            BatchSnapshot(
                batch=batch_number,
                n_pairs=decision.n,
                mean_diff=decision.mean,
                p_value=decision.p_value,
                decided=decision.decided,
            )
        )

    notes: list[str] = []
    if paired.n_pairs > sequential.max_cases:
        notes.append(
            f"only the first {sequential.max_cases} of {paired.n_pairs} pairs were "
            "considered because of the max_cases limit"
        )
    return SequentialOutcome(
        verdict=_verdict_from_direction(decided, direction),
        snapshots=tuple(snapshots),
        pairs_used=consumed,
        pairs_available=paired.n_pairs,
        max_cases=sequential.max_cases,
        theta0=theta0,
        notes=tuple(notes),
    )


def run_live(
    command_template: str,
    baseline_path: Path,
    candidate_path: Path,
    adapter: str,
    gate: GateSettings,
    sequential: SequentialSettings,
) -> SequentialOutcome:
    """Drive an external eval command batch by batch until a decision.

    The command template may reference ``{start}`` and ``{count}``. After
    every invocation both results files are re-read and any newly
    appeared paired cases are folded into the sequential test. The run
    stops on a decision, at ``max_cases``, or when two consecutive
    batches add no new pairs.
    """
    theta0 = -gate.margin
    sprt = MixtureSPRT(
        theta0=theta0,
        alpha=gate.alpha,
        tau=sequential.tau,
        min_samples=sequential.min_samples,
    )
    snapshots: list[BatchSnapshot] = []
    notes: list[str] = []
    consumed_ids: set[str] = set()
    batch_number = 0
    stalled = 0
    decided = False
    direction = 0
    pairs_available = 0

    while len(consumed_ids) < sequential.max_cases and not decided and stalled < 2:
        batch_number += 1
        command = command_template.replace("{start}", str(len(consumed_ids))).replace(
            "{count}", str(sequential.batch_size)
        )
        completed = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise AnalysisError(
                f"batch command failed with exit code {completed.returncode}"
                + (f": {stderr}" if stderr else "")
            )

        baseline_records = load_records(baseline_path, adapter)
        candidate_records = load_records(candidate_path, adapter)
        paired = build_paired(
            baseline_records, candidate_records, gate.metric, order="stream"
        )
        pairs_available = paired.n_pairs
        capacity = sequential.max_cases - len(consumed_ids)
        fresh: list[float] = []
        for case_id, diff in zip(paired.case_ids, paired.diffs, strict=True):
            if capacity <= 0:
                break
            if case_id in consumed_ids:
                continue
            consumed_ids.add(case_id)
            fresh.append(float(diff))
            capacity -= 1
        if not fresh:
            stalled += 1
            continue
        stalled = 0
        decision = sprt.update(fresh)
        decided = decision.decided
        direction = decision.direction
        snapshots.append(
            BatchSnapshot(
                batch=batch_number,
                n_pairs=decision.n,
                mean_diff=decision.mean,
                p_value=decision.p_value,
                decided=decision.decided,
            )
        )
    consumed = len(consumed_ids)

    if stalled >= 2:
        notes.append(
            "stopped because two consecutive batches produced no new paired cases; "
            "check that the batch command appends to the results files"
        )
    return SequentialOutcome(
        verdict=_verdict_from_direction(decided, direction),
        snapshots=tuple(snapshots),
        pairs_used=consumed,
        pairs_available=max(pairs_available, consumed),
        max_cases=sequential.max_cases,
        theta0=theta0,
        notes=tuple(notes),
    )
