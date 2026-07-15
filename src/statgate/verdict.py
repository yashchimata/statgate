from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import numpy as np

from statgate.config import GateSettings
from statgate.core.bootstrap import bca_mean_interval, unpaired_mean_diff_interval
from statgate.core.intervals import Interval, wilson_proportion_interval
from statgate.core.pairing import aggregate_by_case, build_paired
from statgate.core.permutation import sign_flip_pvalue, two_sample_pvalue
from statgate.core.power import required_sample_size
from statgate.errors import AnalysisError
from statgate.records import EvalRecord, Metric

_EPS = 1e-12


class Verdict(StrEnum):
    SHIP = "SHIP"
    BLOCK = "BLOCK"
    INCONCLUSIVE = "INCONCLUSIVE"


EXIT_CODES: dict[Verdict, int] = {
    Verdict.SHIP: 0,
    Verdict.BLOCK: 1,
    Verdict.INCONCLUSIVE: 2,
}


@dataclass(frozen=True)
class SideSummary:
    """Descriptive statistics for one side of the comparison."""

    label: str
    n_cases: int
    n_records: int
    mean: float
    pass_rate: float | None
    pass_interval: Interval | None


@dataclass(frozen=True)
class GateReport:
    """Everything the renderers need to explain a gate decision."""

    verdict: Verdict
    metric: Metric
    analysis: Literal["paired", "unpaired"]
    mean_diff: float
    interval: Interval
    p_value: float
    alpha: float
    margin: float
    n_pairs: int
    sd_diff: float
    baseline: SideSummary
    candidate: SideSummary
    baseline_only: int
    candidate_only: int
    required_pairs: int | None
    notes: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]


def _summarize_side(
    label: str, records: Sequence[EvalRecord], metric: Metric, confidence: float
) -> SideSummary:
    values = [record.value(metric) for record in records]
    cases = {record.case_id for record in records}
    flags_by_case: dict[str, list[bool]] = {}
    for record in records:
        if record.passed is not None:
            flags_by_case.setdefault(record.case_id, []).append(record.passed)
    pass_rate: float | None = None
    pass_interval: Interval | None = None
    if flags_by_case:
        per_case = [sum(flags) / len(flags) for flags in flags_by_case.values()]
        pass_rate = float(np.mean(per_case))
        pass_interval = wilson_proportion_interval(pass_rate, len(per_case), confidence)
    return SideSummary(
        label=label,
        n_cases=len(cases),
        n_records=len(records),
        mean=float(np.mean(values)),
        pass_rate=pass_rate,
        pass_interval=pass_interval,
    )


def _decide(interval: Interval, margin: float) -> Verdict:
    if interval.low > -margin:
        return Verdict.SHIP
    if interval.high < -margin:
        return Verdict.BLOCK
    return Verdict.INCONCLUSIVE


def _required_pairs(
    mean_diff: float, sd_diff: float, n_pairs: int, settings: GateSettings
) -> tuple[int | None, str | None]:
    distance = abs(mean_diff + settings.margin)
    if distance < _EPS:
        return None, (
            "the observed difference sits exactly on the margin, "
            "so no suite size can resolve this comparison"
        )
    if sd_diff < _EPS:
        return None, None
    needed = required_sample_size(sd_diff, distance, settings.alpha, settings.power)
    if needed <= n_pairs:
        return needed, (
            "the observed difference is close to the margin; "
            "more cases may sharpen the estimate only slightly"
        )
    return needed, None


def evaluate_gate(
    baseline_records: Sequence[EvalRecord],
    candidate_records: Sequence[EvalRecord],
    settings: GateSettings,
) -> GateReport:
    """Compare candidate against baseline and produce a gate decision.

    The decision uses a non-inferiority rule on the confidence interval
    of the mean difference (candidate minus baseline):

    - SHIP when the interval lies entirely above ``-margin``
    - BLOCK when the interval lies entirely below ``-margin``
    - INCONCLUSIVE otherwise, with the suite size needed to decide
    """
    if not baseline_records:
        raise AnalysisError("baseline has no records")
    if not candidate_records:
        raise AnalysisError("candidate has no records")

    metric = settings.metric
    confidence = settings.confidence
    paired = build_paired(baseline_records, candidate_records, metric)
    notes: list[str] = []

    use_paired = (
        paired.n_pairs >= settings.min_pairs
        and paired.pair_fraction >= settings.min_pair_fraction
    )

    if use_paired:
        analysis: Literal["paired", "unpaired"] = "paired"
        diffs = paired.diffs
        mean_diff = float(diffs.mean())
        interval = bca_mean_interval(
            diffs, confidence=confidence, resamples=settings.resamples, seed=settings.seed
        )
        p_value = sign_flip_pvalue(
            diffs, permutations=settings.permutations, seed=settings.seed
        )
        sd_diff = float(diffs.std(ddof=1)) if paired.n_pairs > 1 else 0.0
        n_pairs = paired.n_pairs
        if paired.baseline_only or paired.candidate_only:
            notes.append(
                f"{paired.baseline_only} baseline-only and {paired.candidate_only} "
                "candidate-only cases were excluded from the paired analysis"
            )
    else:
        analysis = "unpaired"
        base_values = np.asarray(
            list(aggregate_by_case(baseline_records, metric).values()), dtype=np.float64
        )
        cand_values = np.asarray(
            list(aggregate_by_case(candidate_records, metric).values()), dtype=np.float64
        )
        if base_values.size < settings.min_pairs or cand_values.size < settings.min_pairs:
            raise AnalysisError(
                f"not enough data: {paired.n_pairs} shared cases, "
                f"{base_values.size} baseline cases, {cand_values.size} candidate cases; "
                f"the gate needs at least {settings.min_pairs} on each side"
            )
        mean_diff = float(cand_values.mean() - base_values.mean())
        interval = unpaired_mean_diff_interval(
            base_values,
            cand_values,
            confidence=confidence,
            resamples=settings.resamples,
            seed=settings.seed,
        )
        p_value = two_sample_pvalue(
            base_values, cand_values, permutations=settings.permutations, seed=settings.seed
        )
        sd_diff = float(
            np.sqrt(base_values.var(ddof=1) + cand_values.var(ddof=1))
            if base_values.size > 1 and cand_values.size > 1
            else 0.0
        )
        n_pairs = paired.n_pairs
        notes.append(
            f"only {paired.n_pairs} cases matched by case_id "
            f"({paired.pair_fraction:.0%} of the union), so the analysis fell back to "
            "an unpaired comparison; unpaired analysis needs far more cases to reach "
            "the same certainty"
        )

    verdict = _decide(interval, settings.margin)
    required_pairs: int | None = None
    if verdict is Verdict.INCONCLUSIVE:
        required_pairs, note = _required_pairs(mean_diff, sd_diff, n_pairs, settings)
        if note:
            notes.append(note)

    if sd_diff < _EPS and use_paired:
        notes.append("every case moved by the same amount, so the interval has zero width")

    return GateReport(
        verdict=verdict,
        metric=metric,
        analysis=analysis,
        mean_diff=mean_diff,
        interval=interval,
        p_value=p_value,
        alpha=settings.alpha,
        margin=settings.margin,
        n_pairs=n_pairs,
        sd_diff=sd_diff,
        baseline=_summarize_side("baseline", baseline_records, metric, confidence),
        candidate=_summarize_side("candidate", candidate_records, metric, confidence),
        baseline_only=paired.baseline_only,
        candidate_only=paired.candidate_only,
        required_pairs=required_pairs,
        notes=tuple(notes),
    )
