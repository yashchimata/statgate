from pathlib import Path
import tempfile
from adapters.junit_xml import parse_junit_xml

def test_empty_suite():
    xml = """<?xml version='1.0'?><testsuite tests='0' failures='0' errors='0' skipped='0'></testsuite>"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "e.xml"
        p.write_text(xml, encoding="utf-8")
        data = parse_junit_xml(p)
        assert data["totals"]["tests"] == 0
