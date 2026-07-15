from pathlib import Path
from adapters.junit_xml import parse_junit_xml

def test_parse_sample():
    p = Path(__file__).parent / "fixtures" / "sample-junit.xml"
    data = parse_junit_xml(p)
    assert data["format"] == "junit-xml"
    assert data["totals"]["tests"] == 2
    assert data["totals"]["failures"] == 1
    assert any(c["status"] == "failed" for c in data["cases"])
