"""Tests for config module."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from social_plugin.config import Config


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
