# Social Plugin — CLAUDE.md

AI-powered CLI tool for social media content generation and publishing, focused on Physical AI & Robotics.

## Project Overview

Discovers trending topics via RSS feeds, reads reference content from local files/Google Docs/PDFs, uses Claude AI to generate tweet and LinkedIn post drafts, and posts approved content. SQLite for all state management. Config-driven via YAML.

## Tech Stack

- **Language**: Python 3.11+
- **CLI**: Click + Rich (formatted tables/panels)
- **AI**: Anthropic Claude API (claude-sonnet-4-5-20250929)
- **Database**: SQLite (data/social_plugin.db) — single file state manager
- **Twitter/X**: tweepy (pay-per-use API model)
- **LinkedIn**: Manual posting (clipboard copy) — auto-post deferred
- **Config**: YAML (config/config.yaml) + .env for secrets
- **Safety**: better-profanity + custom blocked words + compliance checks

## Project Structure

```
social-plugin/
├── config/
│   ├── config.yaml              # Main YAML config (user-customized)
│   └── config.example.yaml      # Documented example
├── credentials/                 # Gitignored — Google service account JSON
├── social_plugin/
│   ├── cli.py                   # Click CLI — 15 commands
│   ├── config.py                # YAML loader with defaults + validation
│   ├── db.py                    # SQLite schema (6 tables), CRUD helpers
│   ├── auth/                    # twitter_auth, linkedin_auth, google_auth
│   ├── trends/                  # RSS-based trend discovery (Google News + industry feeds)
│   ├── sources/                 # Content readers: local files, Google Docs, PDFs
│   ├── generator/               # Claude client, prompts, content generator, safety
│   ├── drafts/                  # Draft model, status lifecycle, CRUD manager
│   ├── publisher/               # Twitter posting, LinkedIn clipboard, media upload
│   ├── notifications/           # Slack webhook notifications
│   ├── analytics/               # Engagement tracking, daily summaries, stats
│   └── utils/                   # Logger (rotating file), retry (tenacity)
├── data/
│   ├── social_plugin.db         # SQLite database (gitignored)
│   ├── cache/                   # Downloaded docs/images
│   └── logs/                    # Rotating log files
├── tests/                       # 33 tests (config, db, drafts, safety, prompts)
├── pyproject.toml
├── .env                         # Gitignored — API keys
└── .env.example
```

## Key Commands

```bash
social-plugin fetch-trends           # Fetch trending topics from RSS feeds
social-plugin fetch-sources          # Read configured Google Docs, PDFs, local files
social-plugin generate               # Generate 1 tweet + 1 LinkedIn draft via Claude
social-plugin generate --dry-run     # Preview without saving
social-plugin drafts                 # List pending drafts (rich table)
social-plugin drafts --status all    # List all drafts
social-plugin show <id>              # Full draft details
social-plugin approve <id>           # Approve for posting
social-plugin reject <id> -n "why"   # Reject with notes
social-plugin edit <id>              # Open in $EDITOR
social-plugin regen <id> -t "casual" # Regenerate with new tone via Claude
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

Main config: `config/config.yaml` — see `config/config.example.yaml` for full docs.

Key sections: topics, accounts, sources, generation, safety, notifications, trends, database, logging.

### Content Sources (unified local reader)

`local_files` supports individual files AND folders. When given a folder path, it auto-discovers all supported files inside:
- `.txt`, `.md`, `.csv`, `.rst` — plain text
- `.pdf` — extracted via pdfplumber
- `.doc`, `.docx` — extracted via python-docx

Config accepts bare strings or dicts: `["/path/to/folder"]` or `[{path: "/path/to/file.pdf", name: "My Doc"}]`

Remote PDFs use the `pdfs` config section with `url:` key.

## Environment Variables (.env)

```
ANTHROPIC_API_KEY          # Required — Claude API
TWITTER_API_KEY            # Required for posting
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_TOKEN_SECRET
TWITTER_BEARER_TOKEN
SLACK_WEBHOOK_URL          # Optional — Slack notifications
GOOGLE_SERVICE_ACCOUNT_PATH # Optional — Google Docs access
```

## API Details

- **Twitter/X**: Pay-per-use model (as of 2025). Credentials from developer.x.com. App type: "Automated App or Bot". Requires Read+Write permissions.
- **LinkedIn**: Manual posting mode — drafts copied to clipboard. Auto-post deferred until LinkedIn Developer app is set up.
- **Anthropic**: Account has access to claude-sonnet-4-5-20250929, claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5-20251001. Currently using Sonnet 4.5.
- **Trends**: Google News RSS (free, no API key needed). No Twitter search API used.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v          # Run 33 tests
social-plugin --help                # Verify CLI
```

## Architecture Decisions

- **SQLite as state manager** — single file DB, zero config, queryable history
- **RSS for trend discovery** — free, no API keys, works with Twitter pay-per-use model
- **Files and folders** — local_files supports individual paths or folder paths (auto-discovers supported files)
- **Tone configurable per draft** — `regen` command re-generates with Claude using new tone
- **Profanity filter** — better-profanity scans before saving drafts
- **Hashtag deduplication** — display_content skips hashtags already present in generated text

## Usage Model

All operations are **manually triggered** by the user — no cron or scheduled automation. Typical workflow:

```bash
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
- PyPI publishing
