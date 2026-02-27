"""Interactive setup wizard for social-plugin init."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

import click
import yaml
from rich.console import Console
from rich.panel import Panel

from social_plugin.config import get_app_dir

console = Console()

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
}

# Env var per provider
PROVIDER_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def _strip_quotes(s: str) -> str:
    """Strip surrounding quotes from user input."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    return s


def run_init_wizard() -> Path:
    """Run the interactive init wizard. Returns the path to the created config."""
    console.print(Panel(
        "[bold]Social Plugin — Setup Wizard[/bold]\n\n"
        "This will create your configuration and get you ready to generate content.",
        border_style="cyan",
    ))
    console.print()

    app_dir = get_app_dir()

    # -------------------------------------------------------------------------
    # Step 1: Config directory
    # -------------------------------------------------------------------------
    console.print("[bold cyan]Step 1/6:[/bold cyan] Config directory")
    console.print(f"  Config will be saved to: [green]{app_dir}[/green]")

    if app_dir.exists() and (app_dir / "config.yaml").exists():
        overwrite = click.confirm("  Config already exists. Overwrite?", default=False)
        if not overwrite:
            console.print("[yellow]Setup cancelled. Existing config preserved.[/yellow]")
            return app_dir / "config.yaml"

    app_dir.mkdir(parents=True, exist_ok=True)
    console.print()

    # -------------------------------------------------------------------------
    # Step 2: AI Provider
    # -------------------------------------------------------------------------
    console.print("[bold cyan]Step 2/6:[/bold cyan] AI Provider")
    console.print("  Which AI provider do you want to use?")
    console.print("    [green]1[/green] Anthropic Claude (claude-sonnet-4-5-20250929)")
    console.print("    [green]2[/green] OpenAI GPT (gpt-4o)")
    console.print("    [green]3[/green] Google Gemini (gemini-2.0-flash)")
    console.print()

    provider_choice = click.prompt("  Choice", type=click.IntRange(1, 3), default=1)
    provider_map = {1: "anthropic", 2: "openai", 3: "google"}
    provider = provider_map[provider_choice]
    model = DEFAULT_MODELS[provider]

    custom_model = click.prompt(f"  Model name", default=model)
    if custom_model:
        model = custom_model

    env_key = PROVIDER_ENV_KEYS[provider]
    api_key = os.environ.get(env_key, "")
    if not api_key:
        api_key = click.prompt(f"  {env_key}", hide_input=True, default="")

    console.print()

    # -------------------------------------------------------------------------
    # Step 3: Twitter/X API (optional)
    # -------------------------------------------------------------------------
    console.print("[bold cyan]Step 3/6:[/bold cyan] Twitter/X API (optional)")
    twitter_enabled = click.confirm("  Do you have Twitter/X API keys?", default=False)

    twitter_keys: dict[str, str] = {}
    if twitter_enabled:
        twitter_keys["TWITTER_API_KEY"] = click.prompt("  TWITTER_API_KEY", default="")
        twitter_keys["TWITTER_API_SECRET"] = click.prompt("  TWITTER_API_SECRET", default="")
        twitter_keys["TWITTER_ACCESS_TOKEN"] = click.prompt("  TWITTER_ACCESS_TOKEN", default="")
        twitter_keys["TWITTER_ACCESS_TOKEN_SECRET"] = click.prompt("  TWITTER_ACCESS_TOKEN_SECRET", default="")
        twitter_keys["TWITTER_BEARER_TOKEN"] = click.prompt("  TWITTER_BEARER_TOKEN", default="")

    console.print()

    # -------------------------------------------------------------------------
    # Step 4: Local Documents Folder
    # -------------------------------------------------------------------------
    console.print("[bold cyan]Step 4/6:[/bold cyan] Local Documents Folder")
    console.print("  Path to a folder with your reference docs (txt, md, pdf, docx, csv).")

    while True:
        local_folder = click.prompt("  Folder path")
        local_folder = local_folder.strip().strip("'\"")
        local_path = Path(local_folder).expanduser().resolve()
        if local_path.is_dir():
            local_folder = str(local_path)
            break
        console.print(f"  [red]Directory not found: {local_path}[/red]")

    console.print(f"  [green]Using: {local_folder}[/green]")
    console.print()

    # -------------------------------------------------------------------------
    # Step 5: Content Topics
    # -------------------------------------------------------------------------
    console.print("[bold cyan]Step 5/6:[/bold cyan] Content Topics")
    primary_topic = click.prompt("  Primary topic", default="Physical AI and Robotics")

    kw_input = click.prompt(
        "  Keywords (comma-separated)",
        default="physical AI, robotics, embodied AI",
    )
    keywords = [_strip_quotes(k) for k in kw_input.split(",") if k.strip()]

    ht_input = click.prompt(
        "  Hashtags (comma-separated)",
        default="#PhysicalAI, #Robotics, #AI",
    )
    hashtags = [_strip_quotes(h) if _strip_quotes(h).startswith("#") else f"#{_strip_quotes(h)}" for h in ht_input.split(",") if h.strip()]

    console.print()

    # -------------------------------------------------------------------------
    # Step 6: Verify & Initialize
    # -------------------------------------------------------------------------
    console.print("[bold cyan]Step 6/6:[/bold cyan] Verify & Initialize")

    # Test API key if provided
    if api_key:
        console.print(f"  Testing {provider} API key...", end=" ")
        try:
            _test_api_key(provider, api_key, model)
            console.print("[green]OK[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")
            console.print("  [dim]You can fix the key later in .env[/dim]")
    else:
        console.print(f"  [yellow]No {env_key} provided — set it in .env before generating[/yellow]")

    # Write .env
    env_path = app_dir / ".env"
    env_lines = []
    if api_key:
        env_lines.append(f"{env_key}={api_key}")
    for k, v in twitter_keys.items():
        if v:
            env_lines.append(f"{k}={v}")
    if env_lines:
        env_path.write_text("\n".join(env_lines) + "\n")
        console.print(f"  [green]Created {env_path}[/green]")

    # Write config
    data_dir = app_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    rss_query = quote_plus(primary_topic.lower())

    config_dict = {
        "topics": {
            "primary": primary_topic,
            "keywords": keywords,
            "hashtags": {
                "twitter": hashtags,
                "linkedin": hashtags,
            },
        },
        "accounts": {
            "twitter": {
                "enabled": twitter_enabled,
                "api_tier": "pay-per-use",
                "max_posts_per_day": 2,
            },
            "linkedin": {
                "enabled": True,
                "auto_post": False,
                "max_posts_per_day": 1,
            },
        },
        "sources": {
            "google_docs": [],
            "pdfs": [],
            "local_files": [local_folder],
            "media": [],
            "cache_ttl_hours": 24,
        },
        "generation": {
            "provider": provider,
            "model": model,
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
        "safety": {
            "profanity_filter": True,
            "blocked_words": [],
            "compliance_note": "",
        },
        "notifications": {
            "slack": {
                "enabled": False,
                "webhook_url_env": "SLACK_WEBHOOK_URL",
                "channel": "#social-content",
            },
            "cli": True,
        },
        "trends": {
            "rss_feeds": [
                f"https://news.google.com/rss/search?q={rss_query}",
                f"https://news.google.com/rss/search?q={rss_query}+site:x.com",
                f"https://news.google.com/rss/search?q={rss_query}+site:linkedin.com",
            ],
            "max_results": 20,
        },
        "database": {
            "path": "data/social_plugin.db",
        },
        "logging": {
            "level": "INFO",
            "file": "data/logs/social_plugin.log",
            "max_size_mb": 10,
            "backup_count": 5,
        },
    }

    config_text = "# Social Plugin Configuration\n# Generated by: social-plugin init\n\n"
    config_text += yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)

    config_path = app_dir / "config.yaml"
    config_path.write_text(config_text)
    console.print(f"  [green]Created {config_path}[/green]")

    # Initialize database
    try:
        from social_plugin.config import Config
        from social_plugin.db import Database

        cfg = Config.load(str(config_path))
        db = Database(cfg.db_path)
        console.print(f"  [green]Database initialized at {cfg.db_path}[/green]")
    except Exception as e:
        console.print(f"  [yellow]Database init warning: {e}[/yellow]")

    console.print()
    console.print(Panel(
        "[bold green]Setup complete![/bold green]\n\n"
        "Next steps:\n"
        "  [cyan]social-plugin fetch-trends[/cyan]    — fetch trending topics\n"
        "  [cyan]social-plugin generate[/cyan]        — generate draft content\n"
        "  [cyan]social-plugin drafts[/cyan]          — review your drafts\n"
        "  [cyan]social-plugin config --show[/cyan]   — view config paths",
        border_style="green",
    ))

    return config_path


def _test_api_key(provider: str, api_key: str, model: str) -> None:
    """Quick test of the API key by making a minimal request."""
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}],
        )
    elif provider == "openai":
        import openai

        client = openai.OpenAI(api_key=api_key)
        client.chat.completions.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}],
        )
    elif provider == "google":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model)
        m.generate_content("Say hi")
