"""Config loading — YAML files with ``${ENV_VAR}`` / ``${ENV_VAR:default}`` interpolation.

Config over code (standards §3): no hard-coded paths, tables, or credentials.
Values resolve from the YAML file, with environment variables filling in secrets
and environment-specific bits at load time.

    settings = load_config("config/sources/sap_erp.yaml")
    host = settings["connection"]["host"]
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from scb_common.errors import ConfigError

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def _interpolate(value: Any) -> Any:
    """Recursively replace ``${VAR}`` / ``${VAR:default}`` in strings."""
    if isinstance(value, str):
        def sub(m: re.Match[str]) -> str:
            name, default = m.group(1), m.group(2)
            env = os.environ.get(name)
            if env is not None:
                return env
            if default is not None:
                return default
            raise ConfigError(f"Environment variable '{name}' is not set and has no default")
        return _VAR.sub(sub, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_config(path: str | Path) -> dict[str, Any]:
    """Load and env-interpolate a YAML config file into a dict."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"Config file not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough
        raise ConfigError(f"Invalid YAML in {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(raw).__name__}: {p}")
    return _interpolate(raw)


def require(cfg: dict[str, Any], *keys: str) -> Any:
    """Fetch a nested key path, raising ConfigError with a clear trail if absent.

        require(cfg, "connection", "host")
    """
    node: Any = cfg
    trail: list[str] = []
    for key in keys:
        trail.append(key)
        if not isinstance(node, dict) or key not in node:
            raise ConfigError(f"Missing required config key: {'.'.join(trail)}")
        node = node[key]
    return node
