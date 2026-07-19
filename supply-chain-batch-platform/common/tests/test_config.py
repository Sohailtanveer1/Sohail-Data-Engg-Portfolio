import pytest

from scb_common.config import load_config, require
from scb_common.errors import ConfigError


def _write(tmp_path, text):
    p = tmp_path / "cfg.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_env_interpolation_with_default(tmp_path, monkeypatch):
    monkeypatch.delenv("SCB_HOST", raising=False)
    p = _write(tmp_path, "connection:\n  host: ${SCB_HOST:localhost}\n  port: 5432\n")
    cfg = load_config(p)
    assert cfg["connection"]["host"] == "localhost"
    assert cfg["connection"]["port"] == 5432


def test_env_interpolation_reads_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SCB_HOST", "db.internal")
    p = _write(tmp_path, "connection:\n  host: ${SCB_HOST:localhost}\n")
    assert load_config(p)["connection"]["host"] == "db.internal"


def test_missing_var_without_default_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("SCB_SECRET", raising=False)
    p = _write(tmp_path, "token: ${SCB_SECRET}\n")
    with pytest.raises(ConfigError):
        load_config(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_require_reports_missing_key_trail(tmp_path):
    p = _write(tmp_path, "connection:\n  host: h\n")
    cfg = load_config(p)
    assert require(cfg, "connection", "host") == "h"
    with pytest.raises(ConfigError, match="connection.port"):
        require(cfg, "connection", "port")
