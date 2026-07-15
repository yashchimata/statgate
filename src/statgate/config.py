import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from statgate.errors import ConfigError

DEFAULT_CONFIG_NAME = "statgate.toml"


class GateSettings(BaseModel):
    """Decision policy for the compare gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: Literal["score", "pass_rate"] = "score"
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    margin: float = Field(default=0.02, ge=0.0)
    power: float = Field(default=0.8, gt=0.0, lt=1.0)
    resamples: int = Field(default=10_000, ge=100)
    permutations: int = Field(default=10_000, ge=100)
    seed: int | None = None
    min_pairs: int = Field(default=5, ge=2)
    min_pair_fraction: float = Field(default=0.5, ge=0.0, le=1.0)

    @property
    def confidence(self) -> float:
        return 1.0 - self.alpha


class SequentialSettings(BaseModel):
    """Batching policy for sequential mode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_size: int = Field(default=25, ge=1)
    max_cases: int = Field(default=400, ge=2)
    tau: float | None = Field(default=None, gt=0.0)
    min_samples: int = Field(default=10, ge=2)

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if self.min_samples > self.max_cases:
            raise ValueError("min_samples cannot exceed max_cases")
        return self


class Config(BaseModel):
    """Top level statgate configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: GateSettings = Field(default_factory=GateSettings)
    sequential: SequentialSettings = Field(default_factory=SequentialSettings)


def _format_validation_error(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
    )


def apply_overrides(
    config: Config,
    gate: dict[str, object] | None = None,
    sequential: dict[str, object] | None = None,
) -> Config:
    """Return a new config with overrides applied and re-validated.

    Building fresh models instead of copying keeps field and cross-field
    validators in force for CLI flags, so both configuration surfaces
    enforce the same rules.
    """
    updates: dict[str, object] = {}
    try:
        if gate:
            updates["gate"] = GateSettings(**{**config.gate.model_dump(), **gate})
        if sequential:
            updates["sequential"] = SequentialSettings(
                **{**config.sequential.model_dump(), **sequential}
            )
    except ValidationError as exc:
        raise ConfigError(f"invalid option value: {_format_validation_error(exc)}") from exc
    return config.model_copy(update=updates) if updates else config


def load_config(path: Path | None = None) -> Config:
    """Load configuration from a TOML file.

    When ``path`` is None, ``statgate.toml`` in the working directory is
    used if present, otherwise defaults apply.
    """
    if path is None:
        default = Path(DEFAULT_CONFIG_NAME)
        if not default.is_file():
            return Config()
        path = default
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"could not read config file {path}: {exc}") from exc
    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid config in {path}: {_format_validation_error(exc)}") from exc
