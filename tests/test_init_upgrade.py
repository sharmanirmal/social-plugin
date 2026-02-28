"""Tests for social-plugin init --upgrade config migration."""

from pathlib import Path

import yaml

from social_plugin.config import CONFIG_VERSION, _DEFAULT_CONFIG
from social_plugin.init_wizard import run_upgrade


def _write_config(path: Path, data: dict) -> Path:
    """Helper to write a YAML config to a file."""
    config_path = path / "config.yaml"
    config_path.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))
    return config_path


def _read_config(path: Path) -> dict:
    """Helper to read a YAML config from a file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def test_upgrade_adds_missing_sections(tmp_path):
    """Old config without rules/style_examples gets them after upgrade."""
    old = {
        "topics": {"primary": "Drones"},
        "generation": {"provider": "openai", "model": "gpt-4o"},
    }
    config_path = _write_config(tmp_path, old)

    result = run_upgrade(config_path)

    assert result == config_path
    upgraded = _read_config(config_path)
    assert "rules" in upgraded
    assert "do" in upgraded["rules"]
    assert "dont" in upgraded["rules"]
    assert "style_examples" in upgraded
    assert "safety" in upgraded


def test_upgrade_preserves_user_values(tmp_path):
    """User's provider, model, topics remain unchanged after upgrade."""
    old = {
        "topics": {"primary": "My Custom Topic", "keywords": ["custom"]},
        "generation": {"provider": "openai", "model": "gpt-4o", "temperature": 0.9},
    }
    config_path = _write_config(tmp_path, old)

    run_upgrade(config_path)

    upgraded = _read_config(config_path)
    assert upgraded["topics"]["primary"] == "My Custom Topic"
    assert upgraded["topics"]["keywords"] == ["custom"]
    assert upgraded["generation"]["provider"] == "openai"
    assert upgraded["generation"]["model"] == "gpt-4o"
    assert upgraded["generation"]["temperature"] == 0.9


def test_upgrade_preserves_user_hashtags(tmp_path):
    """Custom hashtags are not replaced by defaults."""
    old = {
        "topics": {
            "primary": "Drones",
            "hashtags": {"twitter": ["#Drones", "#UAV"], "linkedin": ["#Drones"]},
        },
    }
    config_path = _write_config(tmp_path, old)

    run_upgrade(config_path)

    upgraded = _read_config(config_path)
    assert upgraded["topics"]["hashtags"]["twitter"] == ["#Drones", "#UAV"]
    assert upgraded["topics"]["hashtags"]["linkedin"] == ["#Drones"]


def test_upgrade_creates_backup(tmp_path):
    """A .bak file is created during upgrade."""
    old = {"topics": {"primary": "Drones"}}
    config_path = _write_config(tmp_path, old)

    run_upgrade(config_path)

    backup_path = config_path.with_suffix(".yaml.bak")
    assert backup_path.exists()
    # Backup should contain original content
    backup_data = _read_config(backup_path)
    assert backup_data["topics"]["primary"] == "Drones"
    assert "rules" not in backup_data


def test_upgrade_adds_config_version(tmp_path):
    """config_version field is present and set to current version after upgrade."""
    old = {"topics": {"primary": "Drones"}}
    config_path = _write_config(tmp_path, old)

    run_upgrade(config_path)

    upgraded = _read_config(config_path)
    assert upgraded["config_version"] == CONFIG_VERSION


def test_upgrade_idempotent(tmp_path):
    """Running upgrade twice produces the same result with no data loss."""
    old = {
        "topics": {"primary": "Drones", "keywords": ["drones", "UAV"]},
        "generation": {"provider": "openai", "model": "gpt-4o"},
    }
    config_path = _write_config(tmp_path, old)

    run_upgrade(config_path)
    first_result = _read_config(config_path)

    run_upgrade(config_path)
    second_result = _read_config(config_path)

    assert first_result == second_result
    assert second_result["topics"]["primary"] == "Drones"
    assert second_result["generation"]["provider"] == "openai"


def test_upgrade_no_config_errors(tmp_path):
    """Nonexistent config path returns None without crashing."""
    nonexistent = tmp_path / "does_not_exist" / "config.yaml"
    result = run_upgrade(nonexistent)
    assert result is None


def test_upgrade_preserves_unknown_user_keys(tmp_path):
    """User keys not in defaults are kept after upgrade."""
    old = {
        "topics": {"primary": "Drones"},
        "my_custom_section": {"key": "value"},
        "another_key": 42,
    }
    config_path = _write_config(tmp_path, old)

    run_upgrade(config_path)

    upgraded = _read_config(config_path)
    assert upgraded["my_custom_section"] == {"key": "value"}
    assert upgraded["another_key"] == 42
