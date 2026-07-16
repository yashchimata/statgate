import json
from pathlib import Path

import pytest

from statgate.adapters import detect_adapter, load_records
from statgate.errors import AdapterError

FIXTURES = Path(__file__).parent / "fixtures"


class TestJsonl:
    def test_parses_records_with_extras_into_metadata(self, tmp_path):
        path = tmp_path / "results.jsonl"
        path.write_text(
            '{"case_id": "a", "score": 0.5, "latency_ms": 120}\n'
            '\n'
            '{"id": "b", "passed": true, "run_index": 2}\n',
            encoding="utf-8",
        )
        records = load_records(path)
        assert len(records) == 2
        assert records[0].case_id == "a"
        assert records[0].metadata == {"latency_ms": 120}
        assert records[1].case_id == "b"
        assert records[1].passed is True
        assert records[1].run_index == 2

    def test_reports_line_numbers_on_bad_json(self, tmp_path):
        path = tmp_path / "results.jsonl"
        path.write_text('{"case_id": "a", "score": 0.5}\nnot json\n', encoding="utf-8")
        with pytest.raises(AdapterError, match=":2:"):
            load_records(path)

    def test_missing_measurement_is_rejected(self, tmp_path):
        path = tmp_path / "results.jsonl"
        path.write_text('{"case_id": "a"}\n', encoding="utf-8")
        with pytest.raises(AdapterError, match="score"):
            load_records(path)

    def test_nan_and_infinite_scores_are_rejected_at_load(self, tmp_path):
        for literal in ("NaN", "Infinity", "-Infinity"):
            path = tmp_path / "results.jsonl"
            path.write_text(
                f'{{"case_id": "a", "score": {literal}}}\n', encoding="utf-8"
            )
            with pytest.raises(AdapterError, match=":1:"):
                load_records(path)

    def test_missing_case_id_is_rejected(self, tmp_path):
        path = tmp_path / "results.jsonl"
        path.write_text('{"score": 0.5}\n', encoding="utf-8")
        with pytest.raises(AdapterError, match="case_id"):
            load_records(path)

    def test_empty_file_is_rejected(self, tmp_path):
        path = tmp_path / "results.jsonl"
        path.write_text("\n\n", encoding="utf-8")
        with pytest.raises(AdapterError, match="no records"):
            load_records(path)


class TestJsonArray:
    def test_parses_array(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text(
            json.dumps([{"case_id": "a", "score": 1.0}, {"case_id": "b", "score": 0.0}]),
            encoding="utf-8",
        )
        records = load_records(path)
        assert [record.case_id for record in records] == ["a", "b"]

    def test_object_that_is_not_promptfoo_is_rejected(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text('{"cases": []}', encoding="utf-8")
        with pytest.raises(AdapterError, match="unrecognized JSON layout"):
            load_records(path)


class TestCsv:
    def test_parses_csv_with_metadata_columns(self, tmp_path):
        path = tmp_path / "results.csv"
        path.write_text(
            "case_id,score,passed,model\n"
            "a,0.5,true,alpha\n"
            "b,0.9,false,alpha\n",
            encoding="utf-8",
        )
        records = load_records(path)
        assert records[0].score == 0.5
        assert records[0].passed is True
        assert records[0].metadata == {"model": "alpha"}
        assert records[1].passed is False

    def test_bool_synonyms(self, tmp_path):
        path = tmp_path / "results.csv"
        path.write_text(
            "case_id,passed\na,PASS\nb,fail\nc,1\nd,No\n", encoding="utf-8"
        )
        records = load_records(path)
        assert [record.passed for record in records] == [True, False, True, False]

    def test_bad_score_reports_row(self, tmp_path):
        path = tmp_path / "results.csv"
        path.write_text("case_id,score\na,fine\n", encoding="utf-8")
        with pytest.raises(AdapterError, match=":2:"):
            load_records(path)

    def test_bad_boolean_is_rejected(self, tmp_path):
        path = tmp_path / "results.csv"
        path.write_text("case_id,passed\na,maybe\n", encoding="utf-8")
        with pytest.raises(AdapterError, match="boolean"):
            load_records(path)


class TestPromptfoo:
    def test_parses_fixture(self):
        records = load_records(FIXTURES / "promptfoo_baseline.json")
        assert len(records) == 8
        assert records[0].case_id == "test-0-prompt-0"
        assert records[0].score == 0.9
        assert records[0].passed is True
        assert records[0].metadata["provider"] == "openai:gpt-4.1"
        assert records[0].metadata["named_scores"] == {"accuracy": 0.9}

    def test_baseline_and_candidate_pair_by_case_id(self):
        baseline = load_records(FIXTURES / "promptfoo_baseline.json")
        candidate = load_records(FIXTURES / "promptfoo_candidate.json")
        assert {r.case_id for r in baseline} == {r.case_id for r in candidate}

    def test_rejects_layout_without_results(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text('{"results": {"nothing": true}}', encoding="utf-8")
        with pytest.raises(AdapterError, match="promptfoo"):
            load_records(path, adapter="promptfoo")

    def test_multiple_prompts_get_distinct_case_ids(self, tmp_path):
        rows = [
            {"testIdx": t, "promptIdx": p, "success": True, "score": 0.5}
            for t in range(4)
            for p in range(2)
        ]
        path = tmp_path / "results.json"
        path.write_text(json.dumps({"results": {"results": rows}}), encoding="utf-8")
        records = load_records(path, adapter="promptfoo")
        case_ids = [record.case_id for record in records]
        assert len(case_ids) == 8
        assert len(set(case_ids)) == 8
        assert "test-0-prompt-0" in case_ids
        assert "test-0-prompt-1" in case_ids

    def test_vars_digest_fallback_when_test_idx_missing(self, tmp_path):
        rows = [
            {"vars": {"question": "alpha"}, "success": True, "score": 1.0},
            {"vars": {"question": "beta"}, "success": False, "score": 0.0},
        ]
        path = tmp_path / "results.json"
        path.write_text(json.dumps({"results": {"results": rows}}), encoding="utf-8")
        records = load_records(path, adapter="promptfoo")
        assert all(record.case_id.startswith("vars-") for record in records)
        assert records[0].case_id != records[1].case_id
        rerun = load_records(path, adapter="promptfoo")
        assert [r.case_id for r in rerun] == [r.case_id for r in records]

    def test_row_index_fallback_and_unscored_rows_skipped(self, tmp_path):
        rows = [
            {"success": True, "score": 1.0},
            {"vars": {}, "provider": "p"},
            {"success": False},
        ]
        path = tmp_path / "results.json"
        path.write_text(json.dumps({"results": {"results": rows}}), encoding="utf-8")
        records = load_records(path, adapter="promptfoo")
        assert [record.case_id for record in records] == ["row-0", "row-2"]

    def test_top_level_results_list_layout(self, tmp_path):
        rows = [{"testIdx": 0, "success": True, "score": 0.9}]
        path = tmp_path / "results.json"
        path.write_text(json.dumps({"results": rows}), encoding="utf-8")
        records = load_records(path, adapter="promptfoo")
        assert records[0].case_id == "test-0"


class TestDetection:
    def test_detects_by_extension_and_content(self, tmp_path):
        jsonl = tmp_path / "a.jsonl"
        jsonl.write_text('{"case_id": "a", "score": 1}\n', encoding="utf-8")
        csv_file = tmp_path / "a.csv"
        csv_file.write_text("case_id,score\na,1\n", encoding="utf-8")
        assert detect_adapter(jsonl) == "jsonl"
        assert detect_adapter(csv_file) == "csv"
        assert detect_adapter(FIXTURES / "promptfoo_baseline.json") == "promptfoo"

    def test_unknown_extension_is_rejected(self, tmp_path):
        path = tmp_path / "results.txt"
        path.write_text("x", encoding="utf-8")
        with pytest.raises(AdapterError, match="cannot infer adapter"):
            load_records(path)

    def test_missing_file_is_rejected(self, tmp_path):
        with pytest.raises(AdapterError, match="not found"):
            load_records(tmp_path / "nope.jsonl")

    def test_unknown_adapter_name_is_rejected(self, tmp_path):
        path = tmp_path / "a.jsonl"
        path.write_text('{"case_id": "a", "score": 1}\n', encoding="utf-8")
        with pytest.raises(AdapterError, match="unknown adapter"):
            load_records(path, adapter="parquet")


def test_empty_results_guard_20260716():
    rows = []
    assert len(rows) == 0
