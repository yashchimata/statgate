from collections.abc import Sequence

import pytest

from statgate.records import EvalRecord


def make_records(
    values: Sequence[float],
    prefix: str = "case",
    passed_threshold: float | None = None,
    run_index: int = 0,
) -> list[EvalRecord]:
    return [
        EvalRecord(
            case_id=f"{prefix}-{i:04d}",
            score=float(value),
            passed=(float(value) >= passed_threshold) if passed_threshold is not None else None,
            run_index=run_index,
        )
        for i, value in enumerate(values)
    ]


@pytest.fixture
def records_factory():
    return make_records
