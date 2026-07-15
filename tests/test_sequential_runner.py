import json
import sys

import numpy as np
import pytest

from statgate.config import GateSettings, SequentialSettings
from statgate.errors import AnalysisError
from statgate.sequential_runner import run_live, run_replay
from statgate.verdict import Verdict
from tests.conftest import make_records

GATE = GateSettings(seed=3)
SEQ = SequentialSettings(batch_size=25, max_cases=400)


def shifted(n: int, shift: float, noise: float, seed: int = 1):
    rng = np.random.default_rng(seed)
    base = rng.uniform(0.3, 0.9, size=n)
    cand = base + shift + rng.normal(0, noise, size=n)
    return make_records(base), make_records(cand)


class TestReplay:
    def test_clear_regression_stops_early_and_blocks(self):
        baseline, candidate = shifted(400, shift=-0.2, noise=0.05)
        outcome = run_replay(baseline, candidate, GATE, SEQ)
        assert outcome.verdict is Verdict.BLOCK
        assert outcome.pairs_used < 400
        assert outcome.saved_fraction > 0.5
        assert outcome.snapshots[-1].decided

    def test_clear_improvement_stops_early_and_ships(self):
        baseline, candidate = shifted(400, shift=0.15, noise=0.05)
        outcome = run_replay(baseline, candidate, GATE, SEQ)
        assert outcome.verdict is Verdict.SHIP
        assert outcome.pairs_used < 400

    def test_borderline_data_exhausts_budget_inconclusively(self):
        baseline, candidate = shifted(100, shift=-GATE.margin, noise=0.4, seed=9)
        outcome = run_replay(baseline, candidate, GATE, SEQ)
        assert outcome.verdict is Verdict.INCONCLUSIVE
        assert outcome.pairs_used == 100

    def test_max_cases_limit_is_respected_and_noted(self):
        baseline, candidate = shifted(300, shift=0.0, noise=0.3, seed=11)
        seq = SequentialSettings(batch_size=25, max_cases=100)
        outcome = run_replay(baseline, candidate, GATE, seq)
        assert outcome.pairs_used <= 100
        if outcome.verdict is Verdict.INCONCLUSIVE:
            assert any("max_cases" in note for note in outcome.notes)

    def test_too_few_pairs_raise(self):
        baseline, candidate = shifted(5, shift=0.0, noise=0.1)
        with pytest.raises(AnalysisError, match="at least"):
            run_replay(baseline, candidate, GATE, SEQ)


class TestLive:
    def test_drives_batch_command_until_decision(self, tmp_path):
        baseline_path = tmp_path / "baseline.jsonl"
        candidate_path = tmp_path / "candidate.jsonl"
        rng = np.random.default_rng(2)
        base_values = rng.uniform(0.3, 0.7, size=300)
        with baseline_path.open("w", encoding="utf-8") as handle:
            for i, value in enumerate(base_values):
                handle.write(
                    json.dumps({"case_id": f"case-{i:04d}", "score": float(value)}) + "\n"
                )
        candidate_path.write_text("", encoding="utf-8")

        script = tmp_path / "run_batch.py"
        script.write_text(
            "import json, sys\n"
            "start, count = int(sys.argv[1]), int(sys.argv[2])\n"
            f"base = json.load(open(r'{tmp_path / 'base_values.json'}'))\n"
            f"out = open(r'{candidate_path}', 'a', encoding='utf-8')\n"
            "for i in range(start, min(start + count, len(base))):\n"
            "    row = {'case_id': f'case-{i:04d}', 'score': base[i] - 0.3 + (i % 7) * 0.01}\n"
            "    out.write(json.dumps(row) + '\\n')\n"
            "out.close()\n",
            encoding="utf-8",
        )
        (tmp_path / "base_values.json").write_text(
            json.dumps([float(v) for v in base_values]), encoding="utf-8"
        )

        template = f'"{sys.executable}" "{script}" {{start}} {{count}}'
        outcome = run_live(
            template, baseline_path, candidate_path, "jsonl", GATE, SEQ
        )
        assert outcome.verdict is Verdict.BLOCK
        assert outcome.pairs_used < 300
        assert len(outcome.snapshots) >= 1

    def test_late_arriving_baseline_pair_is_consumed_exactly_once(self, tmp_path):
        baseline_path = tmp_path / "baseline.jsonl"
        candidate_path = tmp_path / "candidate.jsonl"
        with baseline_path.open("w", encoding="utf-8") as handle:
            for i in range(20):
                handle.write(
                    json.dumps({"case_id": f"c{i:02d}", "score": 0.5 + (i % 3) * 0.001})
                    + "\n"
                )
        candidate_path.write_text(
            json.dumps({"case_id": "zz", "score": 0.5}) + "\n", encoding="utf-8"
        )

        script = tmp_path / "run_batch.py"
        script.write_text(
            "import json, sys\n"
            "start = int(sys.argv[1])\n"
            f"cand = open(r'{candidate_path}', 'a', encoding='utf-8')\n"
            f"base = open(r'{baseline_path}', 'a', encoding='utf-8')\n"
            "if start == 0:\n"
            "    for i in range(10):\n"
            "        row = {'case_id': f'c{i:02d}', 'score': 0.5 + (i % 3) * 0.001}\n"
            "        cand.write(json.dumps(row) + '\\n')\n"
            "elif start == 10:\n"
            "    base.write(json.dumps({'case_id': 'zz', 'score': 10.5}) + '\\n')\n"
            "    for i in range(10, 16):\n"
            "        row = {'case_id': f'c{i:02d}', 'score': 0.5 + (i % 3) * 0.001}\n"
            "        cand.write(json.dumps(row) + '\\n')\n"
            "cand.close()\n"
            "base.close()\n",
            encoding="utf-8",
        )
        template = f'"{sys.executable}" "{script}" {{start}} {{count}}'
        seq = SequentialSettings(batch_size=10, max_cases=400)
        outcome = run_live(template, baseline_path, candidate_path, "jsonl", GATE, seq)
        assert outcome.pairs_used == 17
        assert outcome.snapshots[-1].n_pairs == 17
        assert outcome.snapshots[-1].mean_diff < -0.3

    def test_failing_command_raises_with_stderr(self, tmp_path):
        baseline_path = tmp_path / "baseline.jsonl"
        baseline_path.write_text('{"case_id": "a", "score": 1}\n', encoding="utf-8")
        candidate_path = tmp_path / "candidate.jsonl"
        candidate_path.write_text('{"case_id": "a", "score": 1}\n', encoding="utf-8")
        template = f'"{sys.executable}" -c "import sys; sys.exit(9)"'
        with pytest.raises(AnalysisError, match="exit code 9"):
            run_live(template, baseline_path, candidate_path, "jsonl", GATE, SEQ)

    def test_stalls_when_command_produces_nothing(self, tmp_path):
        baseline_path = tmp_path / "baseline.jsonl"
        candidate_path = tmp_path / "candidate.jsonl"
        with baseline_path.open("w", encoding="utf-8") as handle:
            for i in range(30):
                handle.write(json.dumps({"case_id": f"c{i}", "score": 0.5}) + "\n")
        with candidate_path.open("w", encoding="utf-8") as handle:
            for i in range(5):
                handle.write(json.dumps({"case_id": f"c{i}", "score": 0.5}) + "\n")
        template = f'"{sys.executable}" -c "pass"'
        outcome = run_live(template, baseline_path, candidate_path, "jsonl", GATE, SEQ)
        assert outcome.verdict is Verdict.INCONCLUSIVE
        assert any("no new paired cases" in note for note in outcome.notes)
