import json
import subprocess
import sys

import numpy as np
import pytest
from click.testing import CliRunner

from statgate.cli import cli, main
from statgate.report import MARKER


def write_jsonl(path, values, prefix="case"):
    with path.open("w", encoding="utf-8") as handle:
        for i, raw in enumerate(values):
            score = float(raw)
            row = {"case_id": f"{prefix}-{i:04d}", "score": score, "passed": score >= 0.6}
            handle.write(json.dumps(row) + "\n")


@pytest.fixture
def data_dir(tmp_path):
    rng = np.random.default_rng(4)
    base = rng.uniform(0.4, 0.9, size=60)
    write_jsonl(tmp_path / "baseline.jsonl", base)
    write_jsonl(
        tmp_path / "improved.jsonl", np.clip(base + 0.1 + rng.normal(0, 0.02, 60), 0, 1)
    )
    write_jsonl(
        tmp_path / "regressed.jsonl", np.clip(base - 0.15 + rng.normal(0, 0.02, 60), 0, 1)
    )
    write_jsonl(tmp_path / "noisy.jsonl", np.clip(base + rng.normal(-0.03, 0.35, 60), 0, 1))
    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


class TestCompare:
    def test_ship_exits_zero(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "1"],
        )
        assert result.exit_code == 0
        assert "SHIP" in result.output

    def test_block_exits_one(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "regressed.jsonl"),
             "--seed", "1"],
        )
        assert result.exit_code == 1
        assert "BLOCK" in result.output

    def test_inconclusive_exits_two(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "noisy.jsonl"),
             "--seed", "1", "--resamples", "1000"],
        )
        assert result.exit_code == 2
        assert "INCONCLUSIVE" in result.output

    def test_markdown_format(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "1", "--format", "markdown"],
        )
        assert MARKER in result.output

    def test_json_format_parses(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "1", "--format", "json"],
        )
        payload = json.loads(result.output)
        assert payload["verdict"] == "SHIP"
        assert payload["n_pairs"] == 60

    @pytest.mark.parametrize("output_format", ["terminal", "markdown", "json"])
    def test_output_file(self, runner, data_dir, tmp_path, output_format):
        out = tmp_path / "report.txt"
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "1", "--format", output_format, "--output", str(out)],
        )
        assert result.exit_code == 0
        assert "report written to" in result.output
        content = out.read_text(encoding="utf-8")
        if output_format == "markdown":
            assert content.startswith(MARKER)
        elif output_format == "json":
            assert json.loads(content)["verdict"] == "SHIP"
        else:
            assert "SHIP" in content
            assert "\x1b" not in content

    def test_margin_override_changes_verdict(self, runner, data_dir):
        strict = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "regressed.jsonl"),
             "--seed", "1", "--margin", "0.5"],
        )
        assert strict.exit_code == 0

    def test_config_file_is_used(self, runner, data_dir, tmp_path):
        config = tmp_path / "statgate.toml"
        config.write_text("[gate]\nmargin = 0.5\n", encoding="utf-8")
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "regressed.jsonl"),
             "--seed", "1", "--config", str(config)],
        )
        assert result.exit_code == 0

    def test_cli_flag_overrides_config_file_even_when_falsy(self, runner, data_dir, tmp_path):
        config = tmp_path / "statgate.toml"
        config.write_text("[gate]\nmargin = 0.5\n", encoding="utf-8")
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "regressed.jsonl"),
             "--seed", "0", "--config", str(config), "--margin", "0.0", "--format", "json"],
        )
        payload = json.loads(result.output)
        assert payload["margin"] == 0.0
        assert payload["verdict"] == "BLOCK"
        assert result.exit_code == 1

    def test_pass_rate_metric_end_to_end(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "1", "--metric", "pass_rate", "--format", "json"],
        )
        payload = json.loads(result.output)
        assert payload["metric"] == "pass_rate"
        assert payload["baseline"]["pass_rate"] is not None
        assert result.exit_code == payload["exit_code"]

    def test_permutations_flag_is_accepted(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "1", "--permutations", "500", "--format", "json"],
        )
        assert result.exit_code == 0

    def test_negative_seed_is_rejected(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["compare", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl"),
             "--seed", "-1"],
        )
        assert result.exit_code != 0
        assert "seed" in result.output.lower()


class TestPower:
    def test_with_sd(self, runner):
        result = runner.invoke(cli, ["power", "--sd", "0.2", "--n", "100"])
        assert result.exit_code == 0
        assert "minimum detectable effect" in result.output

    def test_with_files_json(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["power", "--baseline", str(data_dir / "baseline.jsonl"),
             "--candidate", str(data_dir / "noisy.jsonl"), "--format", "json"],
        )
        payload = json.loads(result.output)
        assert payload["n_current"] == 60
        assert payload["required_n"] > 0
        assert len(payload["table"]) > 0

    def test_requires_sd_or_files(self, runner):
        result = runner.invoke(cli, ["power"])
        assert result.exit_code != 0
        assert "provide either --sd" in result.output

    def test_rejects_half_of_file_pair(self, runner, data_dir):
        result = runner.invoke(cli, ["power", "--baseline", str(data_dir / "baseline.jsonl")])
        assert result.exit_code != 0
        assert "together" in result.output

    def test_custom_sizes(self, runner):
        result = runner.invoke(
            cli, ["power", "--sd", "0.2", "--sizes", "10,20", "--format", "json"]
        )
        payload = json.loads(result.output)
        assert [row["n"] for row in payload["table"]] == [10, 20]

    def test_bad_sizes_rejected(self, runner):
        result = runner.invoke(cli, ["power", "--sd", "0.2", "--sizes", "ten"])
        assert result.exit_code != 0


class TestSequential:
    def test_replay_json(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["sequential", str(data_dir / "baseline.jsonl"), str(data_dir / "regressed.jsonl"),
             "--format", "json", "--batch-size", "15"],
        )
        payload = json.loads(result.output)
        assert payload["verdict"] == "BLOCK"
        assert result.exit_code == 1
        assert payload["pairs_used"] <= 60

    def test_replay_terminal(self, runner, data_dir):
        result = runner.invoke(
            cli,
            ["sequential", str(data_dir / "baseline.jsonl"), str(data_dir / "improved.jsonl")],
        )
        assert result.exit_code == 0
        assert "SHIP" in result.output


class TestValidate:
    def test_valid_file(self, runner, data_dir):
        result = runner.invoke(cli, ["validate", str(data_dir / "baseline.jsonl")])
        assert result.exit_code == 0
        assert "OK" in result.output
        assert "records: 60" in result.output

    def test_invalid_file_via_main_exits_three(self, monkeypatch, tmp_path, capsys):
        bad = tmp_path / "bad.jsonl"
        bad.write_text("not json\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["statgate", "validate", str(bad)])
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 3
        assert "error" in capsys.readouterr().err


class TestMainEntry:
    def test_version(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["statgate", "--version"])
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        assert "statgate" in capsys.readouterr().out

    def test_missing_results_file_exits_three(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(
            sys,
            "argv",
            ["statgate", "compare", str(tmp_path / "a.jsonl"), str(tmp_path / "b.jsonl")],
        )
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 3

    def test_usage_error_exits_three(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["statgate", "compare"])
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 3

    def test_nan_score_exits_three_with_location(self, monkeypatch, capsys, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text(
            '{"case_id": "a", "score": 0.5}\n{"case_id": "b", "score": NaN}\n',
            encoding="utf-8",
        )
        good = tmp_path / "good.jsonl"
        good.write_text('{"case_id": "a", "score": 0.5}\n', encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["statgate", "compare", str(good), str(bad)])
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 3
        assert ":2:" in capsys.readouterr().err

    def test_invalid_cross_field_override_exits_three(self, monkeypatch, capsys, tmp_path):
        data = tmp_path / "data.jsonl"
        with data.open("w", encoding="utf-8") as handle:
            for i in range(30):
                handle.write(json.dumps({"case_id": f"c{i}", "score": 0.5 + i * 0.01}) + "\n")
        monkeypatch.setattr(
            sys,
            "argv",
            ["statgate", "sequential", str(data), str(data), "--max-cases", "2"],
        )
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 3
        assert "min_samples" in capsys.readouterr().err

    def test_module_execution_works(self):
        result = subprocess.run(
            [sys.executable, "-m", "statgate", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "statgate" in result.stdout
