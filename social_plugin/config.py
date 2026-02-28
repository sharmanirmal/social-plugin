"""YAML config loader with validation and defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import click
import yaml
from dotenv import load_dotenv


def get_app_dir() -> Path:
    """Get the platform-specific application config directory.

    - macOS: ~/Library/Application Support/social-plugin/
    - Windows: C:\\Users\\<user>\\AppData\\Roaming\\social-plugin\\
    - Linux: ~/.config/social-plugin/
    """
    return Path(click.get_app_dir("social-plugin"))


CONFIG_VERSION = 2  # Bump when new config sections are added

_DEFAULT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "topics": {
        "primary": "Physical AI and Robotics",
        "keywords": ["physical AI", "robotics", "embodied AI"],
        "hashtags": {
            "twitter": ["#PhysicalAI", "#Robotics"],
            "linkedin": ["#PhysicalAI", "#Robotics", "#AI"],
        },
    },
    "accounts": {
        "twitter": {"enabled": True, "api_tier": "pay-per-use", "max_posts_per_day": 1},
        "linkedin": {"enabled": True, "auto_post": False, "max_posts_per_day": 1},
    },
    "sources": {"google_docs": [], "pdfs": [], "local_files": [], "media": [], "cache_ttl_hours": 24},
    "generation": {
        "provider": None,  # Auto-detected from model name if not set
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 4096,
        "temperature": 0.7,
        "default_tone": "informative, thought-provoking, professional",
        "tweet": {
            "max_length": 280,
            "count_per_run": 1,
            "style": "concise insight with relevant hashtag",
        },
        "linkedin_post": {
            "max_length": 3000,
            "count_per_run": 1,
            "style": "thought-leadership, conversational, uses line breaks, ends with a question",
        },
    },
    "safety": {"profanity_filter": True, "blocked_words": [], "compliance_note": ""},
    "rules": {
        "do": [
            "Include specific data points or statistics when available",
            "Reference the source or study when citing facts",
            "Write with a clear, authentic voice — not generic marketing speak",
        ],
        "dont": [
            "Never use clickbait or sensationalist language",
            "Avoid generic hype phrases like 'revolutionize', 'game-changer', or 'disrupt'",
            "Don't start posts with 'Exciting news!' or similar clichés",
        ],
    },
    "style_examples": [],
    "notifications": {"slack": {"enabled": False, "webhook_url_env": "SLACK_WEBHOOK_URL", "channel": "#social-content"}, "cli": True},
    "trends": {
        "rss_feeds": ["https://news.google.com/rss/search?q=physical+AI+robotics"],
        "max_results": 20,
    },
    "database": {"path": "data/social_plugin.db"},
    "logging": {"level": "INFO", "file": "data/logs/social_plugin.log", "max_size_mb": 10, "backup_count": 5},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Application configuration loaded from YAML with env var support."""

    def __init__(self, data: dict[str, Any], project_root: Path):
        self._data = data
        self.project_root = project_root

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """Load config from YAML file, merging with defaults.

        Resolution order:
        1. Explicit config_path argument (--config flag)
        2. CWD ./config/config.yaml (development mode)
        3. APP_DIR/config.yaml (installed mode)
        """
        if config_path is not None:
            # Explicit path provided
            config_path = Path(config_path)
            project_root = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent
        else:
            # Try CWD first (development mode)
            cwd_config = Path.cwd() / "config" / "config.yaml"
            app_dir_config = get_app_dir() / "config.yaml"

            if cwd_config.exists():
                config_path = cwd_config
                project_root = Path.cwd()
            elif app_dir_config.exists():
                config_path = app_dir_config
                project_root = get_app_dir()
            else:
                # No config found — use CWD as project root (defaults only)
                config_path = cwd_config
                project_root = Path.cwd()

        # Load .env from same root as config
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        user_config: dict = {}
        if config_path.exists():
            with open(config_path) as f:
                user_config = yaml.safe_load(f) or {}

        data = _deep_merge(_DEFAULT_CONFIG, user_config)
        return cls(data, project_root)

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value using dot-separated keys or varargs."""
        if len(keys) == 1 and "." in keys[0]:
            keys = tuple(keys[0].split("."))

        current = self._data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    @property
    def db_path(self) -> Path:
        return self.project_root / self.get("database.path", default="data/social_plugin.db")

    @property
    def log_file(self) -> Path | None:
        log = self.get("logging.file")
        return self.project_root / log if log else None

    @property
    def topics(self) -> dict:
        return self._data.get("topics", {})

    @property
    def generation(self) -> dict:
        return self._data.get("generation", {})

    @property
    def accounts(self) -> dict:
        return self._data.get("accounts", {})

    @property
    def sources(self) -> dict:
        return self._data.get("sources", {})

    @property
    def safety(self) -> dict:
        return self._data.get("safety", {})

    @property
    def notifications(self) -> dict:
        return self._data.get("notifications", {})

    @property
    def rules(self) -> dict:
        return self._data.get("rules", {"do": [], "dont": []})

    @property
    def style_examples(self) -> list[str]:
        return self._data.get("style_examples", [])

    @property
    def trends_config(self) -> dict:
        return self._data.get("trends", {})

    @property
    def raw(self) -> dict:
        return self._data

    def env(self, key: str, default: str | None = None) -> str | None:
        """Get an environment variable."""
        return os.environ.get(key, default)

    @property
    def llm_provider(self) -> str:
        """Get the effective LLM provider (explicit or auto-detected from model)."""
        provider = self.get("generation.provider")
        if provider:
            return provider
        model = self.get("generation.model", default="claude-sonnet-4-5-20250929")
        if model.startswith("claude-"):
            return "anthropic"
        elif model.startswith(("gpt-", "o1", "o3")):
            return "openai"
        elif model.startswith("gemini-"):
            return "google"
        return "anthropic"

    def validate(self) -> list[str]:
        """Return a list of validation warnings."""
        warnings = []

        # Check API key for the configured LLM provider
        provider = self.llm_provider
        provider_env_keys = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_key = provider_env_keys.get(provider, "ANTHROPIC_API_KEY")
        if not self.env(env_key):
            warnings.append(f"{env_key} not set (required for {provider} provider)")

        if self.accounts.get("twitter", {}).get("enabled") and not self.env("TWITTER_API_KEY"):
            warnings.append("Twitter enabled but TWITTER_API_KEY not set")
        if self.notifications.get("slack", {}).get("enabled"):
            webhook_env = self.notifications["slack"].get("webhook_url_env", "SLACK_WEBHOOK_URL")
            if not self.env(webhook_env):
                warnings.append(f"Slack enabled but {webhook_env} not set")
        return warnings
