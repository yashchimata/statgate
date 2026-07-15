import json
from collections.abc import Callable
from pathlib import Path

from statgate.adapters.csv_ import parse_csv
from statgate.adapters.jsonl import parse_json_array, parse_jsonl
from statgate.adapters.promptfoo import parse_promptfoo
from statgate.errors import AdapterError
from statgate.records import EvalRecord

_PARSERS: dict[str, Callable[[Path], list[EvalRecord]]] = {
    "jsonl": parse_jsonl,
    "json": parse_json_array,
    "csv": parse_csv,
    "promptfoo": parse_promptfoo,
}

ADAPTER_NAMES: tuple[str, ...] = ("auto", *sorted(_PARSERS))


def detect_adapter(path: Path) -> str:
    """Choose an adapter from the file extension and content."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise AdapterError(f"could not read {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{path}: invalid JSON: {exc.msg}") from exc
        if isinstance(data, dict) and "results" in data:
            return "promptfoo"
        if isinstance(data, list):
            return "json"
        raise AdapterError(
            f"{path}: unrecognized JSON layout; pass --adapter to select one explicitly"
        )
    raise AdapterError(
        f"{path}: cannot infer adapter from extension {suffix!r}; "
        "expected .jsonl, .json, or .csv, or pass --adapter"
    )


def load_records(path: Path, adapter: str = "auto") -> list[EvalRecord]:
    """Load eval records from a results file using the named adapter."""
    if not path.is_file():
        raise AdapterError(f"results file not found: {path}")
    name = detect_adapter(path) if adapter == "auto" else adapter
    parser = _PARSERS.get(name)
    if parser is None:
        raise AdapterError(
            f"unknown adapter {name!r}; available adapters: {', '.join(ADAPTER_NAMES)}"
        )
    return parser(path)
