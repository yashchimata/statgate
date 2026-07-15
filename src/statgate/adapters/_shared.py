from typing import Any

from pydantic import ValidationError

from statgate.errors import AdapterError
from statgate.records import EvalRecord

_KNOWN_KEYS = {"case_id", "score", "passed", "run_index", "metadata"}
_CASE_ID_ALIASES = ("case_id", "id", "test_id", "case")


def record_from_mapping(item: Any, context: str) -> EvalRecord:
    """Build an EvalRecord from one parsed mapping.

    Unknown keys are preserved in metadata rather than rejected, so
    records exported with extra bookkeeping fields still load.
    """
    if not isinstance(item, dict):
        raise AdapterError(f"{context}: expected an object, got {type(item).__name__}")

    case_id: Any = None
    consumed: set[str] = set()
    for alias in _CASE_ID_ALIASES:
        if alias in item and item[alias] is not None:
            case_id = item[alias]
            consumed.add(alias)
            break
    if case_id is None:
        raise AdapterError(f"{context}: missing case_id")

    metadata_field = item.get("metadata")
    metadata: dict[str, Any] = dict(metadata_field) if isinstance(metadata_field, dict) else {}
    extras = {
        key: value
        for key, value in item.items()
        if key not in _KNOWN_KEYS and key not in consumed
    }
    metadata.update(extras)

    try:
        return EvalRecord(
            case_id=str(case_id),
            score=item.get("score"),
            passed=item.get("passed"),
            run_index=item.get("run_index", 0),
            metadata=metadata,
        )
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "record"
        raise AdapterError(f"{context}: {location}: {first['msg']}") from exc
