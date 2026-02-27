# Social Plugin

AI-powered CLI tool for social media content generation and publishing, focused on Physical AI & Robotics.

Discovers trending topics via RSS feeds, reads reference content from local files/Google Docs/PDFs, uses AI to generate tweet and LinkedIn post drafts, and posts approved content.

## Quick Start

**macOS / Linux:**
```bash
pipx install social-plugin
social-plugin init
```

**Windows (PowerShell):**
```powershell
pipx install social-plugin
social-plugin init
```

The `init` wizard walks you through choosing an AI provider, entering API keys, setting your local docs folder, and configuring your topics.

## Prerequisites

You need an API key from at least one provider:

| Provider | Get API Key | Models |
|----------|-------------|--------|
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/) | `claude-sonnet-4-5-20250929`, `claude-opus-4-6` |
| **OpenAI** | [platform.openai.com](https://platform.openai.com/) | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini` |
| **Google** | [aistudio.google.com](https://aistudio.google.com/) | `gemini-2.0-flash`, `gemini-2.5-pro` |

For posting to Twitter/X, you also need API keys from [developer.x.com](https://developer.x.com/).

## Manual Install (from source)

```bash
git clone https://github.com/nirmalsharma/social-plugin.git
cd social-plugin
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config/config.example.yaml config/config.yaml
cp .env.example .env
# Edit .env with your API keys
social-plugin --help
```

## Configuration

After running `social-plugin init`, config is stored in:

- **macOS:** `~/Library/Application Support/social-plugin/config.yaml`
- **Linux:** `~/.config/social-plugin/config.yaml`
- **Windows:** `%APPDATA%\social-plugin\config.yaml`

If running from the repo directory, `./config/config.yaml` takes priority (development mode).

### Multi-Provider Config

```yaml
generation:
  provider: "anthropic"           # "anthropic", "openai", or "google"
  model: "claude-sonnet-4-5-20250929"  # or "gpt-4o", "gemini-2.0-flash"
  max_tokens: 4096
  temperature: 0.7
```

Provider is auto-detected from the model name if not set. Set the matching env var:

- `ANTHROPIC_API_KEY` for Claude models
- `OPENAI_API_KEY` for GPT/o1/o3 models
- `GOOGLE_API_KEY` for Gemini models

## Usage

### Typical Workflow

```bash
social-plugin fetch-trends       # 1. Get latest trending topics
social-plugin fetch-sources      # 2. Read local docs/PDFs
social-plugin generate           # 3. Generate AI drafts
social-plugin drafts             # 4. Review pending drafts
social-plugin approve <id>       # 5. Approve a draft
social-plugin post --id <id>     # 6. Post to Twitter/LinkedIn
```

Or run steps 1-3 in one command:

```bash
social-plugin run-all
```

### All Commands

| Command | Description |
|---------|-------------|
| `init` | Interactive setup wizard |
| `config --show` | Show config paths and active provider |
| `fetch-trends` | Fetch trending topics from RSS feeds |
| `fetch-sources` | Read configured Google Docs, PDFs, local files |
| `generate` | Generate 1 tweet + 1 LinkedIn draft |
| `generate --dry-run` | Preview without saving |
| `list --last 10` | List last N drafts ordered by date |
| `drafts` | List pending drafts |
| `drafts --status all` | List all drafts |
| `show <id>` | Full draft details |
| `review <id>` | Interactive review (approve/edit/regen/reject) |
| `approve <id>` | Approve for posting (also accepts failed drafts) |
| `reject <id> -n "reason"` | Reject with notes |
| `delete <id>` | Delete a draft permanently |
| `edit <id>` | Open in $EDITOR |
| `regen <id> -t "casual"` | Regenerate with new tone |
| `post --id <id>` | Post specific draft |
| `post --all-approved` | Post all approved drafts |
| `run-all` | Full pipeline: trends + sources + generate |
| `stats` | Analytics dashboard |
| `history --days 30` | Content history |
| `expire` | Expire old pending drafts |
| `auth-check` | Verify API credentials |

### Content Generation Quality

Generated content benefits from several quality features:

- **Long-form X/Twitter posts** — tweets can be up to 4000 characters when the content warrants depth (not limited to 280)
- **Source URL references** — when referencing articles or research, generated posts include clickable source URLs
- **Freshness-aware** — multiple `generate` runs in the same day produce different content (previous drafts passed as context)
- **Meaningful rewrites** — `review` choice 3 (add context) and `regen` produce genuinely different posts, not minor rewordings
- **Source warnings** — warns when no reference documents are available, suggests adding docs for richer content
- **X.com + Twitter feed support** — trend discovery works with both x.com and twitter.com RSS feeds

### Draft Lifecycle

```
PENDING → approve → APPROVED → post → POSTED
  ↓         ↑                    ↓
reject   regen(tone)           FAILED
  ↓
REJECTED
  ↓
expire (7 days) → EXPIRED
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

### Install from TestPyPI

To test a pre-release build before it goes to PyPI:

```bash
pipx install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ social-plugin
```

### Publishing

CI publishes automatically on tag push via GitHub Actions:

```bash
git tag v0.1.0
git push --tags
```

This triggers: **build** → **TestPyPI** → **PyPI** (sequential, OIDC trusted publishing).

## License

MIT
