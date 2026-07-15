from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from statgate.errors import AnalysisError
from statgate.records import EvalRecord, Metric

FloatArray = npt.NDArray[np.float64]

PairOrder = Literal["sorted", "stream"]


@dataclass(frozen=True)
class PairedData:
    """Per-case values aligned between a baseline run and a candidate run.

    Values are aggregated to one number per case by averaging over
    repeated runs, so downstream resampling operates on cases. Cases are
    the natural cluster unit for eval suites: repeated runs of the same
    case are correlated and must not be treated as independent samples.
    """

    case_ids: tuple[str, ...]
    baseline: FloatArray
    candidate: FloatArray
    baseline_only: int
    candidate_only: int

    @property
    def n_pairs(self) -> int:
        return len(self.case_ids)

    @property
    def diffs(self) -> FloatArray:
        return self.candidate - self.baseline

    @property
    def pair_fraction(self) -> float:
        universe = self.n_pairs + self.baseline_only + self.candidate_only
        return self.n_pairs / universe if universe else 0.0


def aggregate_by_case(records: Sequence[EvalRecord], metric: Metric) -> dict[str, float]:
    """Average each case's records into a single per-case value."""
    if not records:
        raise AnalysisError("no records to analyze")
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for record in records:
        value = record.value(metric)
        sums[record.case_id] = sums.get(record.case_id, 0.0) + value
        counts[record.case_id] = counts.get(record.case_id, 0) + 1
    return {case_id: sums[case_id] / counts[case_id] for case_id in sums}


def build_paired(
    baseline_records: Sequence[EvalRecord],
    candidate_records: Sequence[EvalRecord],
    metric: Metric,
    order: PairOrder = "sorted",
) -> PairedData:
    """Pair baseline and candidate values by case id.

    With ``order="sorted"`` pairs are sorted by case id for deterministic
    output. With ``order="stream"`` pairs keep the order in which cases
    first appear in the candidate records, which sequential mode relies
    on to consume new cases as they arrive.
    """
    base_values = aggregate_by_case(baseline_records, metric)
    cand_values = aggregate_by_case(candidate_records, metric)

    shared = [case for case in cand_values if case in base_values]
    if order == "sorted":
        shared.sort()
    else:
        seen: set[str] = set()
        ordered: list[str] = []
        for record in candidate_records:
            case = record.case_id
            if case in base_values and case not in seen:
                seen.add(case)
                ordered.append(case)
        shared = ordered

    baseline = np.asarray([base_values[c] for c in shared], dtype=np.float64)
    candidate = np.asarray([cand_values[c] for c in shared], dtype=np.float64)
    return PairedData(
        case_ids=tuple(shared),
        baseline=baseline,
        candidate=candidate,
        baseline_only=len(base_values) - len(shared),
        candidate_only=len(cand_values) - len(shared),
    )
