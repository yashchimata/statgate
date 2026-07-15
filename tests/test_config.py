import pytest

from statgate.config import Config, load_config
from statgate.errors import ConfigError


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = load_config(None)
        assert config == Config()
        assert config.gate.alpha == 0.05
        assert config.gate.margin == 0.02
        assert config.sequential.batch_size == 25

    def test_reads_default_file_from_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "statgate.toml").write_text(
            "[gate]\nalpha = 0.01\nmargin = 0.05\n", encoding="utf-8"
        )
        config = load_config(None)
        assert config.gate.alpha == 0.01
        assert config.gate.margin == 0.05
        assert config.gate.metric == "score"

    def test_explicit_path(self, tmp_path):
        path = tmp_path / "custom.toml"
        path.write_text("[sequential]\nbatch_size = 10\nmax_cases = 50\n", encoding="utf-8")
        config = load_config(path)
        assert config.sequential.batch_size == 10
        assert config.sequential.max_cases == 50

    def test_missing_explicit_path_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nope.toml")

    def test_invalid_toml_raises(self, tmp_path):
        path = tmp_path / "bad.toml"
        path.write_text("gate = [broken", encoding="utf-8")
        with pytest.raises(ConfigError, match="could not read"):
            load_config(path)

    def test_unknown_keys_are_rejected_with_location(self, tmp_path):
        path = tmp_path / "bad.toml"
        path.write_text("[gate]\nalpa = 0.05\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="alpa"):
            load_config(path)

    def test_out_of_range_values_are_rejected(self, tmp_path):
        path = tmp_path / "bad.toml"
        path.write_text("[gate]\nalpha = 2.0\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="alpha"):
            load_config(path)

    def test_min_samples_cannot_exceed_max_cases(self, tmp_path):
        path = tmp_path / "bad.toml"
        path.write_text("[sequential]\nmin_samples = 100\nmax_cases = 50\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="min_samples"):
            load_config(path)
