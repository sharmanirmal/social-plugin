# Social Plugin — CLAUDE.md

AI-powered CLI tool for social media content generation and publishing, focused on Physical AI & Robotics.

## Project Overview

Discovers trending topics via RSS feeds, reads reference content from local files/Google Docs/PDFs, uses AI (Claude, GPT, or Gemini) to generate tweet and LinkedIn post drafts, and posts approved content. SQLite for all state management. Config-driven via YAML.

## Tech Stack

- **Language**: Python 3.11+
- **CLI**: Click + Rich (formatted tables/panels)
- **AI**: Multi-provider via `llm_client.py` — Anthropic Claude, OpenAI GPT, Google Gemini
- **Database**: SQLite (data/social_plugin.db) — single file state manager
- **Twitter/X**: tweepy (pay-per-use API model)
- **LinkedIn**: Manual posting (clipboard copy — macOS/Linux/Windows) — auto-post deferred
- **Config**: YAML (config/config.yaml) + .env for secrets
- **Safety**: better-profanity + custom blocked words + compliance checks
- **Packaging**: PyPI-ready (setuptools), install scripts for macOS/Linux/Windows

## Project Structure

```
social-plugin/
├── config/
│   ├── config.yaml              # Main YAML config (user-customized)
│   └── config.example.yaml      # Documented example
├── credentials/                 # Gitignored — Google service account JSON
├── social_plugin/
│   ├── cli.py                   # Click CLI — 19 commands (incl init, config, list, delete)
│   ├── config.py                # YAML loader with app-dir resolution + validation
│   ├── init_wizard.py           # Interactive 6-step setup wizard
│   ├── db.py                    # SQLite schema (6 tables), CRUD helpers
│   ├── auth/                    # twitter_auth, linkedin_auth, google_auth
│   ├── trends/                  # RSS-based trend discovery (Google News + industry feeds)
│   ├── sources/                 # Content readers: local files, Google Docs, PDFs
│   ├── generator/
│   │   ├── llm_client.py        # Multi-provider LLM abstraction (Claude, GPT, Gemini)
│   │   ├── claude_client.py     # Legacy Claude-only client (backward compat)
│   │   ├── content_generator.py # Orchestrator: trends + docs → LLM → drafts
│   │   ├── prompts.py           # System/user prompt builders
│   │   └── safety.py            # Profanity filter + blocked words
│   ├── drafts/                  # Draft model, status lifecycle, CRUD manager
│   ├── publisher/               # Twitter posting, LinkedIn clipboard, media upload
│   ├── notifications/           # Slack webhook notifications
│   ├── analytics/               # Engagement tracking, daily summaries, stats
│   ├── templates/               # Bundled templates (legacy config template)
│   └── utils/                   # Logger (rotating file), retry (tenacity)
├── scripts/
│   ├── install.sh               # macOS/Linux one-liner installer
│   └── install.ps1              # Windows PowerShell installer
├── data/
│   ├── social_plugin.db         # SQLite database (gitignored)
│   ├── cache/                   # Downloaded docs/images
│   └── logs/                    # Rotating log files
├── tests/                       # 33 tests (config, db, drafts, safety, prompts)
├── .github/workflows/           # CI: test.yml + publish.yml (TestPyPI → PyPI)
├── pyproject.toml               # PyPI metadata, deps, entry points
├── LICENSE                      # MIT
├── MANIFEST.in
├── README.md
├── .env                         # Gitignored — API keys
└── .env.example
```

## Key Commands

```bash
social-plugin init                   # Interactive setup wizard
social-plugin config --show          # Show config paths and active provider
social-plugin fetch-trends           # Fetch trending topics from RSS feeds
social-plugin fetch-sources          # Read configured Google Docs, PDFs, local files
social-plugin generate               # Generate 1 tweet + 1 LinkedIn draft via LLM
social-plugin generate --dry-run     # Preview without saving
social-plugin list --last 10         # List last N drafts by date
social-plugin drafts                 # List pending drafts (rich table)
social-plugin drafts --status all    # List all drafts
social-plugin show <id>              # Full draft details
social-plugin approve <id>           # Approve for posting (also accepts failed drafts)
social-plugin reject <id> -n "why"   # Reject with notes
social-plugin delete <id>            # Delete a draft permanently
social-plugin edit <id>              # Open in $EDITOR
social-plugin regen <id> -t "casual" # Regenerate with new tone via LLM
social-plugin post --id <id>         # Post specific draft
social-plugin post --all-approved    # Post all approved drafts
social-plugin post --dry-run         # Simulate posting
social-plugin run-all                # Full pipeline: trends → sources → generate
social-plugin stats                  # Analytics dashboard
social-plugin history --days 30      # Content history
social-plugin expire                 # Expire old pending drafts (>7 days)
social-plugin auth-check             # Verify all API credentials
```

## Draft Lifecycle

```
PENDING → approve → APPROVED → post → POSTED
  ↓         ↑                    ↓
reject   regen(tone)           FAILED
  ↓
REJECTED
  ↓
expire (7 days) → EXPIRED
```

## Database Schema (SQLite)

6 tables in `data/social_plugin.db`:
- **trends** — RSS-fetched trending topics, partitioned by date
- **source_documents** — Content from Google Docs/PDFs/local files, with content hash
- **drafts** — Full lifecycle: id, platform, content, hashtags, tone, status, generation metadata
- **post_analytics** — Engagement tracking: likes, retweets, comments, impressions
- **run_log** — Pipeline audit trail: type, status, timing, summary
- **config_snapshots** — Config YAML snapshots for audit

## Configuration

### Config Resolution Order

1. Explicit `--config` flag
2. CWD `./config/config.yaml` (development mode)
3. App dir `config.yaml` (installed mode — `~/Library/Application Support/social-plugin/` on macOS)

Main config: `config/config.yaml` — see `config/config.example.yaml` for full docs.

Key sections: topics, accounts, sources, generation, safety, notifications, trends, database, logging.

### Multi-LLM Provider

```yaml
generation:
  provider: "anthropic"           # "anthropic", "openai", or "google" (auto-detected if omitted)
  model: "claude-sonnet-4-5-20250929"  # or "gpt-4o", "gemini-2.0-flash"
```

Provider is auto-detected from model name: `claude-*` → anthropic, `gpt-*/o1-*/o3-*` → openai, `gemini-*` → google.

The factory function `create_llm_client()` in `llm_client.py` returns the appropriate client. All clients implement the `LLMClient` protocol with a `generate(system_prompt, user_prompt) -> GenerationResult` method.

### Content Sources (unified local reader)

`local_files` supports individual files AND folders. When given a folder path, it auto-discovers all supported files inside:
- `.txt`, `.md`, `.csv`, `.rst` — plain text
- `.pdf` — extracted via pdfplumber
- `.doc`, `.docx` — extracted via python-docx

Config accepts bare strings or dicts: `["/path/to/folder"]` or `[{path: "/path/to/file.pdf", name: "My Doc"}]`

Remote PDFs use the `pdfs` config section with `url:` key.

## Environment Variables (.env)

```
# LLM Provider (set one based on your provider)
ANTHROPIC_API_KEY          # For Claude models
OPENAI_API_KEY             # For GPT/o1/o3 models
GOOGLE_API_KEY             # For Gemini models

# Twitter/X
TWITTER_API_KEY            # Required for posting
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_TOKEN_SECRET
TWITTER_BEARER_TOKEN

# Optional
SLACK_WEBHOOK_URL          # Slack notifications
GOOGLE_SERVICE_ACCOUNT_PATH # Google Docs access
```

## API Details

- **Twitter/X**: Pay-per-use model (as of 2025). Credentials from developer.x.com. App type: "Automated App or Bot". Requires Read+Write permissions.
- **LinkedIn**: Manual posting mode — drafts copied to clipboard (macOS/Linux/Windows). Auto-post deferred until LinkedIn Developer app is set up.
- **Anthropic**: claude-sonnet-4-5-20250929, claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5-20251001
- **OpenAI**: gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o1-mini, o3-mini
- **Google**: gemini-2.0-flash, gemini-2.5-pro, gemini-2.5-flash, gemini-1.5-pro
- **Trends**: Google News RSS (free, no API key needed). No Twitter search API used.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v          # Run tests
social-plugin --help                # Verify CLI
```

### Building & Publishing

```bash
pip install build twine
python -m build
twine check dist/*
```

CI publishes automatically on tag push (`v*`) via GitHub Actions:
1. **build** — builds wheel + sdist, uploads as artifact
2. **testpypi** — publishes to TestPyPI (test.pypi.org)
3. **pypi** — publishes to PyPI (pypi.org) after TestPyPI succeeds

Both registries use OIDC trusted publishing (no API tokens). To release:
```bash
git tag v0.1.0
git push --tags
```

## Architecture Decisions

- **Multi-LLM via Protocol** — `LLMClient` protocol in `llm_client.py`, factory pattern, provider auto-detected from model name
- **SQLite as state manager** — single file DB, zero config, queryable history
- **RSS for trend discovery** — free, no API keys, works with Twitter pay-per-use model
- **Cross-platform config paths** — `click.get_app_dir()` for installed mode, CWD for development
- **Init wizard** — interactive 6-step setup for non-technical users, includes mandatory local docs folder, tests API key on the spot
- **Files and folders** — local_files supports individual paths or folder paths (auto-discovers supported files)
- **Tone configurable per draft** — `regen` command re-generates with LLM using new tone
- **Profanity filter** — better-profanity scans before saving drafts
- **Hashtag deduplication** — display_content skips hashtags already present in generated text

## Usage Model

All operations are **manually triggered** by the user — no cron or scheduled automation. Typical workflow:

```bash
social-plugin init               # First time only
social-plugin fetch-trends       # 1. Get latest trends
social-plugin fetch-sources      # 2. Read local docs/PDFs
social-plugin generate           # 3. Generate drafts
social-plugin drafts             # 4. Review
social-plugin approve <id>       # 5. Approve
social-plugin post --id <id>     # 6. Post
```

Or use `social-plugin run-all` to run steps 1-3 in one command.

## Future Enhancements

- Image/video summarization via Claude vision API
- MCP server for Claude marketplace integration
- LinkedIn auto-posting when Developer app is ready
- Content calendar / A/B testing
