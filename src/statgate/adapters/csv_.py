import csv
from pathlib import Path
from typing import Any

from statgate.adapters._shared import record_from_mapping
from statgate.errors import AdapterError
from statgate.records import EvalRecord

_TRUE_VALUES = {"true", "1", "yes", "y", "pass", "passed"}
_FALSE_VALUES = {"false", "0", "no", "n", "fail", "failed"}


def _parse_bool(raw: str, context: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise AdapterError(f"{context}: cannot interpret {raw!r} as a boolean")


def _convert_cell(key: str, value: str, context: str) -> Any:
    if key == "score":
        try:
            return float(value)
        except ValueError as exc:
            raise AdapterError(f"{context}: cannot interpret {value!r} as a score") from exc
    if key == "passed":
        return _parse_bool(value, context)
    if key == "run_index":
        try:
            return int(value)
        except ValueError as exc:
            raise AdapterError(f"{context}: cannot interpret {value!r} as a run index") from exc
    return value


def _row_to_item(row: dict[str, str], context: str) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for key, raw in row.items():
        if key is None or raw is None or raw.strip() == "":
            continue
        item[key] = _convert_cell(key, raw.strip(), context)
    return item


def parse_csv(path: Path) -> list[EvalRecord]:
    """Parse a CSV results file with a header row.

    Recognized columns: case_id (or id), score, passed, run_index.
    Additional columns are preserved as metadata.
    """
    records: list[EvalRecord] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise AdapterError(f"{path}: empty CSV file")
            for row_number, row in enumerate(reader, start=2):
                context = f"{path}:{row_number}"
                item = _row_to_item(row, context)
                if item:
                    records.append(record_from_mapping(item, context))
    except OSError as exc:
        raise AdapterError(f"could not read {path}: {exc}") from exc
    if not records:
        raise AdapterError(f"{path}: no records found")
    return records
