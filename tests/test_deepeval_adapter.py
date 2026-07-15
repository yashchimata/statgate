from pathlib import Path
from adapters.deepeval_results import parse_deepeval_results

def test_parse():
    p = Path(__file__).parent / "fixtures" / "deepeval-sample.json"
    data = parse_deepeval_results(p)
    assert data["format"] == "deepeval"
    assert data["totals"]["count"] == 2
    assert data["totals"]["passed"] == 1
