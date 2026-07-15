import hashlib
import json
from pathlib import Path
from typing import Any

from statgate.errors import AdapterError
from statgate.records import EvalRecord


def _result_rows(data: Any, path: Path) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise AdapterError(f"{path}: expected a promptfoo JSON object")
    results = data.get("results")
    if isinstance(results, dict):
        inner = results.get("results")
        if isinstance(inner, list):
            return [row for row in inner if isinstance(row, dict)]
    if isinstance(results, list):
        return [row for row in results if isinstance(row, dict)]
    raise AdapterError(
        f"{path}: no results found; expected output of 'promptfoo eval -o results.json'"
    )


def _case_id(row: dict[str, Any], index: int) -> str:
    test_idx = row.get("testIdx")
    prompt_idx = row.get("promptIdx")
    if test_idx is not None:
        case = f"test-{test_idx}"
        if prompt_idx is not None:
            case += f"-prompt-{prompt_idx}"
        return case
    variables = row.get("vars")
    if isinstance(variables, dict) and variables:
        digest = hashlib.sha256(
            json.dumps(variables, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        case = f"vars-{digest}"
        if prompt_idx is not None:
            case += f"-prompt-{prompt_idx}"
        return case
    return f"row-{index}"


def _provider_id(row: dict[str, Any]) -> str | None:
    provider = row.get("provider")
    if isinstance(provider, dict):
        value = provider.get("id") or provider.get("label")
        return str(value) if value is not None else None
    if isinstance(provider, str):
        return provider
    return None


def parse_promptfoo(path: Path) -> list[EvalRecord]:
    """Parse the JSON file written by ``promptfoo eval -o results.json``.

    Case ids are derived from promptfoo test and prompt indices, so two
    exports of the same suite pair cleanly. Provider id and named scores
    are preserved in metadata.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AdapterError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AdapterError(f"{path}: invalid JSON: {exc.msg}") from exc

    rows = _result_rows(data, path)
    if not rows:
        raise AdapterError(f"{path}: promptfoo results are empty")

    records: list[EvalRecord] = []
    for index, row in enumerate(rows):
        success = row.get("success")
        score = row.get("score")
        if success is None and score is None:
            continue
        metadata: dict[str, Any] = {}
        provider = _provider_id(row)
        if provider is not None:
            metadata["provider"] = provider
        named_scores = row.get("namedScores")
        if isinstance(named_scores, dict) and named_scores:
            metadata["named_scores"] = named_scores
        try:
            records.append(
                EvalRecord(
                    case_id=_case_id(row, index),
                    score=float(score) if score is not None else None,
                    passed=bool(success) if success is not None else None,
                    metadata=metadata,
                )
            )
        except (TypeError, ValueError) as exc:
            raise AdapterError(f"{path}: result {index}: {exc}") from exc
    if not records:
        raise AdapterError(f"{path}: no scored results found in promptfoo output")
    return records
