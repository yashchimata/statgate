"""Adapter: DeepEval results files -> normalized summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_deepeval_results(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("test_results") or data.get("results") or data.get("items") or []
        if not rows and "metrics" in data:
            rows = [data]
    else:
        rows = list(data)

    metrics: list[dict[str, Any]] = []
    passed = failed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        success = row.get("success")
        if success is None:
            success = row.get("passed")
        if success is True:
            passed += 1
        elif success is False:
            failed += 1
        metrics.append(
            {
                "name": row.get("name") or row.get("metric") or row.get("test_name"),
                "success": success,
                "score": row.get("score") or row.get("threshold_score"),
            }
        )
    return {
        "format": "deepeval",
        "totals": {"passed": passed, "failed": failed, "count": len(metrics)},
        "metrics": metrics,
    }
