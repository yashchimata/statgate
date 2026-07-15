import json
from pathlib import Path

from statgate.adapters._shared import record_from_mapping
from statgate.errors import AdapterError
from statgate.records import EvalRecord


def parse_jsonl(path: Path) -> list[EvalRecord]:
    """Parse a JSON Lines results file, one record object per line."""
    records: list[EvalRecord] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AdapterError(f"could not read {path}: {exc}") from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        records.append(record_from_mapping(item, f"{path}:{line_number}"))
    if not records:
        raise AdapterError(f"{path}: no records found")
    return records


def parse_json_array(path: Path) -> list[EvalRecord]:
    """Parse a JSON file containing an array of record objects."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AdapterError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AdapterError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(data, list):
        raise AdapterError(f"{path}: expected a JSON array of records")
    if not data:
        raise AdapterError(f"{path}: no records found")
    return [
        record_from_mapping(item, f"{path}[{index}]") for index, item in enumerate(data)
    ]
