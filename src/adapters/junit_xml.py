"""Adapter: parse JUnit XML results into a normalized summary."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_junit_xml(path: str | Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    # root may be testsuites or testsuite
    suites = []
    if root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    elif root.tag == "testsuite":
        suites = [root]
    else:
        suites = root.findall(".//testsuite")

    total = failures = errors = skipped = 0
    cases: list[dict[str, Any]] = []
    for suite in suites:
        total += int(suite.attrib.get("tests") or 0)
        failures += int(suite.attrib.get("failures") or 0)
        errors += int(suite.attrib.get("errors") or 0)
        skipped += int(suite.attrib.get("skipped") or 0)
        for case in suite.findall("testcase"):
            status = "passed"
            if case.find("failure") is not None:
                status = "failed"
            elif case.find("error") is not None:
                status = "error"
            elif case.find("skipped") is not None:
                status = "skipped"
            cases.append(
                {
                    "name": case.attrib.get("name"),
                    "classname": case.attrib.get("classname"),
                    "time": float(case.attrib.get("time") or 0),
                    "status": status,
                }
            )
    return {
        "format": "junit-xml",
        "totals": {
            "tests": total or len(cases),
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "passed": max((total or len(cases)) - failures - errors - skipped, 0),
        },
        "cases": cases,
    }
