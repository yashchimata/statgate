from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from statgate.errors import AnalysisError

Metric = Literal["score", "pass_rate"]


class EvalRecord(BaseModel):
    """One graded eval case from a single run.

    Either ``score`` or ``passed`` must be present. ``run_index``
    distinguishes repeated runs of the same case.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(min_length=1)
    score: float | None = Field(default=None, allow_inf_nan=False)
    passed: bool | None = None
    run_index: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_measurement(self) -> Self:
        if self.score is None and self.passed is None:
            raise ValueError("record must contain a score, a passed flag, or both")
        return self

    def value(self, metric: Metric) -> float:
        """Return the numeric value of this record under the given metric."""
        if metric == "score":
            if self.score is not None:
                return self.score
            return 1.0 if self.passed else 0.0
        if self.passed is None:
            raise AnalysisError(
                f"case {self.case_id!r} has no passed flag; "
                "the pass_rate metric requires a boolean passed field on every record"
            )
        return 1.0 if self.passed else 0.0
