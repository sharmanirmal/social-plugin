"""Tests for config module."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from social_plugin.config import Config, _deep_merge, _DEFAULT_CONFIG


def test_load_defaults():
    """Config loads with defaults when no YAML file exists."""
    config = Config.load("/nonexistent/config.yaml")
    assert config.get("topics.primary") == "Physical AI and Robotics"
    assert config.get("database.path") == "data/social_plugin.db"
    assert config.get("logging.level") == "INFO"


def test_load_from_yaml():
    """Config merges YAML with defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"topics": {"primary": "Custom Topic"}, "logging": {"level": "DEBUG"}}, f)
        tmp_path = f.name

    try:
        config = Config.load(tmp_path)
        assert config.get("topics.primary") == "Custom Topic"
        assert config.get("logging.level") == "DEBUG"
        # Defaults still present
        assert config.get("database.path") == "data/social_plugin.db"
    finally:
        os.unlink(tmp_path)


def test_get_nested():
    """Config supports dot-separated and varargs access."""
    config = Config.load("/nonexistent/config.yaml")
    assert config.get("topics", "primary") == "Physical AI and Robotics"
    assert config.get("topics.primary") == "Physical AI and Robotics"
    assert config.get("nonexistent.key", default="fallback") == "fallback"


def test_validate_warnings(monkeypatch):
    """Config validation returns warnings for missing env vars."""
    config = Config.load("/nonexistent/config.yaml")
    # Clear env after load (load_dotenv may set them from .env)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("TWITTER_API_KEY", raising=False)
    warnings = config.validate()
    # Default provider is anthropic, so should warn about ANTHROPIC_API_KEY
    assert any("ANTHROPIC_API_KEY" in w for w in warnings)


def test_properties():
    """Config properties return expected structures."""
    config = Config.load("/nonexistent/config.yaml")
    assert isinstance(config.topics, dict)
    assert isinstance(config.generation, dict)
    assert isinstance(config.accounts, dict)
    assert isinstance(config.sources, dict)
    assert isinstance(config.safety, dict)


def test_rules_property_defaults():
    """Config returns default rules with DO and DON'T lists."""
    config = Config.load("/nonexistent/config.yaml")
    rules = config.rules
    assert isinstance(rules, dict)
    assert "do" in rules
    assert "dont" in rules
    assert len(rules["do"]) >= 1
    assert len(rules["dont"]) >= 1
    # Check that defaults are sensible
    assert any("data points" in r.lower() for r in rules["do"])
    assert any("clickbait" in r.lower() for r in rules["dont"])


def test_style_examples_property_defaults():
    """Config returns empty style_examples by default."""
    config = Config.load("/nonexistent/config.yaml")
    examples = config.style_examples
    assert isinstance(examples, list)
    assert len(examples) == 0


# =============================================================================
# Backward compatibility tests — old configs without new sections
# =============================================================================


def test_old_config_without_rules_gets_defaults():
    """Old config missing 'rules' key gets default DO/DON'T lists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"topics": {"primary": "Robots"}}, f)
        tmp = f.name
    try:
        config = Config.load(tmp)
        rules = config.rules
        assert "do" in rules and len(rules["do"]) >= 1
        assert "dont" in rules and len(rules["dont"]) >= 1
    finally:
        os.unlink(tmp)


def test_old_config_without_style_examples_gets_defaults():
    """Old config missing 'style_examples' gets empty list."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"topics": {"primary": "Robots"}}, f)
        tmp = f.name
    try:
        config = Config.load(tmp)
        assert config.style_examples == []
    finally:
        os.unlink(tmp)


def test_old_config_without_config_version():
    """Old config without config_version loads without error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"topics": {"primary": "Robots"}, "generation": {"model": "gpt-4o"}}, f)
        tmp = f.name
    try:
        config = Config.load(tmp)
        assert config.get("topics.primary") == "Robots"
        assert config.generation["model"] == "gpt-4o"
        assert config.rules is not None
        assert config.style_examples is not None
    finally:
        os.unlink(tmp)


def test_user_values_survive_deep_merge():
    """User's custom values are preserved when merging with defaults."""
    user = {"topics": {"primary": "Custom Topic"}, "generation": {"model": "gpt-4o"}}
    merged = _deep_merge(_DEFAULT_CONFIG, user)
    assert merged["topics"]["primary"] == "Custom Topic"
    assert merged["generation"]["model"] == "gpt-4o"
    # Defaults still present for untouched keys
    assert merged["safety"]["profanity_filter"] is True


def test_deep_merge_preserves_user_lists():
    """User's list values are not mixed with defaults — user list wins."""
    user = {"topics": {"hashtags": {"twitter": ["#MyTag"]}}}
    merged = _deep_merge(_DEFAULT_CONFIG, user)
    assert merged["topics"]["hashtags"]["twitter"] == ["#MyTag"]


def test_deep_merge_adds_missing_nested_keys():
    """If user has 'rules.do' but not 'rules.dont', dont gets default."""
    user = {"rules": {"do": ["My custom rule"]}}
    merged = _deep_merge(_DEFAULT_CONFIG, user)
    assert merged["rules"]["do"] == ["My custom rule"]
    assert len(merged["rules"]["dont"]) >= 1  # default dont rules


def test_old_config_all_properties_work():
    """Realistic old config (no rules/style_examples/config_version) — all properties work."""
    old_config = {
        "topics": {"primary": "Drones", "keywords": ["drones"], "hashtags": {"twitter": ["#Drones"]}},
        "accounts": {"twitter": {"enabled": False}},
        "generation": {"provider": "openai", "model": "gpt-4o"},
        "safety": {"profanity_filter": True},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(old_config, f)
        tmp = f.name
    try:
        config = Config.load(tmp)
        # All properties callable without error
        assert config.topics["primary"] == "Drones"
        assert config.generation["model"] == "gpt-4o"
        assert config.accounts["twitter"]["enabled"] is False
        assert config.safety["profanity_filter"] is True
        assert isinstance(config.rules, dict)
        assert isinstance(config.style_examples, list)
        assert isinstance(config.sources, dict)
        assert isinstance(config.notifications, dict)
        assert config.trends_config is not None
    finally:
        os.unlink(tmp)


def test_empty_config_gets_all_defaults():
    """Empty YAML file gets all defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        tmp = f.name
    try:
        config = Config.load(tmp)
        assert config.get("topics.primary") == "Physical AI and Robotics"
        assert config.get("database.path") == "data/social_plugin.db"
        assert isinstance(config.rules, dict)
        assert isinstance(config.style_examples, list)
    finally:
        os.unlink(tmp)
