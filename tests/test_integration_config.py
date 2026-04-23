from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ["OPENEVO_DATA_DIR"] = ""


def test_config_json_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("OPENEVO_DATA_DIR", str(data))
    from openevo.config.settings import clear_settings_cache, get_settings, reload_settings

    clear_settings_cache()
    data.mkdir(parents=True, exist_ok=True)
    (data / "config.json").write_text(json.dumps({"port": 9999}), encoding="utf-8")
    cfg = get_settings()
    assert cfg.port == 9999

    (data / "config.json").write_text(json.dumps({"port": 10001}), encoding="utf-8")
    reload_settings()
    assert get_settings().port == 10001


def test_config_nested_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "d2"
    monkeypatch.setenv("OPENEVO_DATA_DIR", str(data))
    from openevo.config.settings import clear_settings_cache, get_settings

    clear_settings_cache()
    data.mkdir(parents=True, exist_ok=True)
    (data / "config.json").write_text(
        json.dumps({"memory": {"memory_char_limit": 500}}),
        encoding="utf-8",
    )
    cfg = get_settings()
    assert cfg.memory.memory_char_limit == 500
    assert cfg.memory.user_char_limit == 1375
