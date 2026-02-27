"""Click CLI entry point for social-plugin."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from social_plugin.config import Config
from social_plugin.db import Database
from social_plugin.drafts.draft_manager import DraftManager
from social_plugin.drafts.models import DraftStatus, Platform
from social_plugin.utils.logger import setup_logger, get_logger

console = Console()


def _init(config_path: str | None = None) -> tuple[Config, Database, DraftManager]:
    """Initialize config, database, and draft manager."""
    config = Config.load(config_path)
    logger = setup_logger(
        level=config.get("logging.level", default="INFO"),
        log_file=str(config.log_file) if config.log_file else None,
        max_size_mb=config.get("logging.max_size_mb", default=10),
        backup_count=config.get("logging.backup_count", default=5),
    )
    db = Database(config.db_path)
    dm = DraftManager(db)
    return config, db, dm


@click.group()
@click.option("--config", "config_path", default=None, help="Path to config YAML file")
@click.pass_context
def cli(ctx, config_path: str | None):
    """Social Plugin — AI-powered social media content generation."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path

    # First-run detection: if no config found and not running init/config/help
    invoked = ctx.invoked_subcommand
    if invoked not in ("init", "config", None):
        from social_plugin.config import get_app_dir
        from pathlib import Path

        has_config = (
            config_path is not None
            or (Path.cwd() / "config" / "config.yaml").exists()
            or (get_app_dir() / "config.yaml").exists()
        )
        if not has_config:
            console.print("[yellow]No configuration found.[/yellow]")
            console.print("Run [cyan]social-plugin init[/cyan] to set up your configuration.")
            raise click.Abort()


# =============================================================================
# init
# =============================================================================

@cli.command("init")
def init_cmd():
    """Interactive setup wizard — creates config, .env, and database."""
    from social_plugin.init_wizard import run_init_wizard
    run_init_wizard()


# =============================================================================
# config
# =============================================================================

@cli.command("config")
@click.option("--show", is_flag=True, help="Show config file paths and active provider")
@click.pass_context
def config_cmd(ctx, show: bool):
    """Show configuration paths and settings."""
    from social_plugin.config import get_app_dir
    from pathlib import Path

    config_path = ctx.obj.get("config_path")

    app_dir = get_app_dir()
    cwd_config = Path.cwd() / "config" / "config.yaml"
    app_config = app_dir / "config.yaml"

    console.print(Panel("[bold]Configuration Paths[/bold]", border_style="cyan"))
    console.print(f"  App directory:     [cyan]{app_dir}[/cyan]")
    console.print(f"  CWD config:        {'[green]exists' if cwd_config.exists() else '[dim]not found'}[/] {cwd_config}")
    console.print(f"  App dir config:    {'[green]exists' if app_config.exists() else '[dim]not found'}[/] {app_config}")

    # Show which config is active
    if config_path:
        console.print(f"  [bold]Active config:[/bold] [green]{config_path}[/green] (--config flag)")
    elif cwd_config.exists():
        console.print(f"  [bold]Active config:[/bold] [green]{cwd_config}[/green] (CWD)")
    elif app_config.exists():
        console.print(f"  [bold]Active config:[/bold] [green]{app_config}[/green] (app dir)")
    else:
        console.print("  [bold]Active config:[/bold] [yellow]none — run social-plugin init[/yellow]")

    if show:
        try:
            config, _, _ = _init(config_path)
            console.print(f"\n  [bold]Provider:[/bold] {config.llm_provider}")
            console.print(f"  [bold]Model:[/bold] {config.get('generation.model')}")
            console.print(f"  [bold]Database:[/bold] {config.db_path}")
        except Exception:
            pass


# =============================================================================
# fetch-trends
# =============================================================================

@cli.command("fetch-trends")
@click.pass_context
def fetch_trends(ctx):
    """Fetch trending topics from RSS feeds."""
    config, db, _ = _init(ctx.obj.get("config_path"))

    run_id = db.start_run("fetch_trends")
    try:
        from social_plugin.trends.twitter_trends import TwitterTrendFetcher
        from social_plugin.trends.linkedin_trends import LinkedInTrendFetcher

        twitter_fetcher = TwitterTrendFetcher(config, db)
        linkedin_fetcher = LinkedInTrendFetcher(config, db)

        twitter_trends = twitter_fetcher.fetch()
        linkedin_trends = linkedin_fetcher.fetch()

        total = len(twitter_trends) + len(linkedin_trends)

        # Display results
        table = Table(title=f"Trends Fetched ({date.today().isoformat()})")
        table.add_column("Source", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Score", style="green", justify="right")

        for t in (twitter_trends + linkedin_trends)[:15]:
            table.add_row(t.source, t.title[:80], f"{t.relevance_score:.2f}")

        console.print(table)
        console.print(f"\n[green]Total: {total} trends stored[/green]")

        db.complete_run(run_id, "success", {"twitter": len(twitter_trends), "linkedin": len(linkedin_trends)})
    except Exception as e:
        db.complete_run(run_id, "failed", error=str(e))
        console.print(f"[red]Error fetching trends: {e}[/red]")
        raise click.Abort()


# =============================================================================
# fetch-sources
# =============================================================================

@cli.command("fetch-sources")
@click.pass_context
def fetch_sources(ctx):
    """Fetch content from configured sources (Google Docs, PDFs, local files)."""
    config, db, _ = _init(ctx.obj.get("config_path"))

    run_id = db.start_run("fetch_sources")
    counts = {"google_docs": 0, "remote_pdfs": 0, "local_files": 0}

    try:
        sources_cfg = config.sources

        # Google Docs (require API auth)
        gdocs = sources_cfg.get("google_docs", [])
        if gdocs:
            from social_plugin.sources.gdocs_reader import GoogleDocsReader
            reader = GoogleDocsReader(db)
            docs = reader.read_all(gdocs)
            counts["google_docs"] = len(docs)
            console.print(f"[cyan]Google Docs:[/cyan] {len(docs)} read")

        # Remote PDFs (URLs only — local PDFs go through local_files)
        pdfs = sources_cfg.get("pdfs", [])
        remote_pdfs = [p for p in pdfs if p.get("url")]
        if remote_pdfs:
            from social_plugin.sources.pdf_reader import PDFReader
            reader = PDFReader(db)
            docs = reader.read_all(remote_pdfs)
            counts["remote_pdfs"] = len(docs)
            console.print(f"[cyan]Remote PDFs:[/cyan] {len(docs)} read")

        # Local files — unified reader for txt, md, csv, pdf, doc, docx
        local = sources_cfg.get("local_files", [])
        # Also include local PDF paths from the pdfs config section
        local_pdfs = [{"path": p.get("path"), "name": p.get("name", "")} for p in pdfs if p.get("path")]
        all_local = local + local_pdfs
        if all_local:
            from social_plugin.sources.local_reader import LocalReader
            reader = LocalReader(db)
            docs = reader.read_all(all_local)
            counts["local_files"] = len(docs)
            console.print(f"[cyan]Local files:[/cyan] {len(docs)} read")

        total = sum(counts.values())
        console.print(f"\n[green]Total: {total} sources fetched[/green]")
        db.complete_run(run_id, "success", counts)
    except Exception as e:
        db.complete_run(run_id, "failed", error=str(e))
        console.print(f"[red]Error fetching sources: {e}[/red]")
        raise click.Abort()


# =============================================================================
# generate
# =============================================================================

@cli.command("generate")
@click.option("--tone", default=None, help="Override default tone for generation")
@click.option("--dry-run", is_flag=True, help="Print drafts without saving")
@click.pass_context
def generate(ctx, tone: str | None, dry_run: bool):
    """Generate social media drafts using Claude."""
    config, db, dm = _init(ctx.obj.get("config_path"))

    run_id = db.start_run("generate")
    try:
        from social_plugin.generator.content_generator import ContentGenerator
        from social_plugin.notifications.slack_notifier import SlackNotifier

        generator = ContentGenerator(config, db, dm)
        drafts = generator.generate_all(tone=tone, dry_run=dry_run)

        if dry_run:
            console.print(Panel("[yellow]DRY RUN — drafts not saved[/yellow]"))

        for draft in drafts:
            console.print(Panel(
                draft.display_content,
                title=f"[{draft.platform.value}] {draft.id}",
                subtitle=f"tone: {draft.tone}" if draft.tone else None,
                border_style="cyan" if draft.platform == Platform.TWITTER else "blue",
            ))

        if not dry_run and drafts:
            # Send Slack notification
            notifier = SlackNotifier(config)
            notifier.notify_drafts_ready(drafts)

            # Save config snapshot
            config_yaml = yaml.dump(config.raw)
            config_hash = hashlib.sha256(config_yaml.encode()).hexdigest()[:16]
            db.save_config_snapshot(config_hash, config_yaml)

        console.print(f"\n[green]Generated {len(drafts)} draft(s)[/green]")
        db.complete_run(run_id, "success", {"drafts": len(drafts)})
    except Exception as e:
        db.complete_run(run_id, "failed", error=str(e))
        console.print(f"[red]Error generating content: {e}[/red]")
        raise click.Abort()


# =============================================================================
# drafts
# =============================================================================

@cli.command("drafts")
@click.option("--status", default="pending", type=click.Choice(["pending", "approved", "rejected", "posted", "failed", "expired", "all"]))
@click.pass_context
def list_drafts(ctx, status: str):
    """List drafts by status."""
    _, db, dm = _init(ctx.obj.get("config_path"))

    if status == "all":
        drafts = []
        for s in DraftStatus:
            drafts.extend(dm.list_by_status(s))
    else:
        drafts = dm.list_by_status(DraftStatus(status))

    if not drafts:
        console.print(f"[dim]No {status} drafts found[/dim]")
        return

    table = Table(title=f"Drafts ({status})")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Platform", style="magenta")
    table.add_column("Content", style="white", max_width=60)
    table.add_column("Status", style="green")
    table.add_column("Created", style="dim")

    for draft in drafts:
        preview = draft.content[:55].replace("\n", " ")
        table.add_row(
            draft.id,
            draft.platform.value,
            preview + "..." if len(draft.content) > 55 else preview,
            draft.status.value,
            str(draft.created_at)[:16] if draft.created_at else "",
        )

    console.print(table)


# =============================================================================
# show
# =============================================================================

@cli.command("show")
@click.argument("draft_id")
@click.pass_context
def show_draft(ctx, draft_id: str):
    """Show full details of a draft."""
    _, _, dm = _init(ctx.obj.get("config_path"))

    draft = dm.get(draft_id)
    if draft is None:
        console.print(f"[red]Draft {draft_id} not found[/red]")
        raise click.Abort()

    # Build detail panel
    details = []
    details.append(f"[bold]ID:[/bold] {draft.id}")
    details.append(f"[bold]Platform:[/bold] {draft.platform.value}")
    details.append(f"[bold]Status:[/bold] {draft.status.value}")
    details.append(f"[bold]Tone:[/bold] {draft.tone or 'default'}")
    details.append(f"[bold]Created:[/bold] {draft.created_at}")
    if draft.reviewed_at:
        details.append(f"[bold]Reviewed:[/bold] {draft.reviewed_at}")
    if draft.posted_at:
        details.append(f"[bold]Posted:[/bold] {draft.posted_at}")
    if draft.post_url:
        details.append(f"[bold]URL:[/bold] {draft.post_url}")
    if draft.reviewer_notes:
        details.append(f"[bold]Notes:[/bold] {draft.reviewer_notes}")
    if draft.error_message:
        details.append(f"[bold]Error:[/bold] {draft.error_message}")
    if draft.generation_model:
        details.append(f"[bold]Model:[/bold] {draft.generation_model}")
    if draft.generation_tokens:
        details.append(f"[bold]Tokens:[/bold] {draft.generation_tokens}")
    if draft.generation_cost:
        details.append(f"[bold]Cost:[/bold] ${draft.generation_cost:.4f}")
    if draft.image_path:
        details.append(f"[bold]Image:[/bold] {draft.image_path}")

    console.print(Panel(
        "\n".join(details),
        title=f"Draft {draft.id}",
        border_style="cyan",
    ))
    console.print()
    console.print(Panel(draft.display_content, title="Content", border_style="green"))


# =============================================================================
# review (interactive)
# =============================================================================

def _display_draft(draft):
    """Display draft content in a panel."""
    border = "cyan" if draft.platform.value == "twitter" else "blue"
    console.print()
    console.print(Panel(
        draft.display_content,
        title=f"[{draft.platform.value}] {draft.id}",
        subtitle=f"tone: {draft.tone or 'default'} | {len(draft.content)} chars",
        border_style=border,
    ))
    console.print()


@cli.command("review")
@click.argument("draft_id")
@click.pass_context
def review_draft(ctx, draft_id: str):
    """Interactively review and customize a draft before approving."""
    config, db, dm = _init(ctx.obj.get("config_path"))

    draft = dm.get(draft_id)
    if draft is None:
        console.print(f"[red]Draft {draft_id} not found[/red]")
        raise click.Abort()

    if draft.status.value not in ("pending", "rejected"):
        console.print(f"[yellow]Draft {draft_id} is already {draft.status.value}[/yellow]")
        return

    _display_draft(draft)

    while True:
        console.print("[bold]What would you like to do?[/bold]")
        console.print("  [green]1[/green] Approve as-is")
        console.print("  [cyan]2[/cyan] Change tone (regenerate with new tone)")
        console.print("  [cyan]3[/cyan] Add context (regenerate with additional info)")
        console.print("  [cyan]4[/cyan] Edit text manually")
        console.print("  [cyan]5[/cyan] Add/remove hashtags")
        console.print("  [red]6[/red] Reject")
        console.print("  [dim]7[/dim] Skip (leave as pending)")
        console.print()

        choice = click.prompt("Choice", type=click.IntRange(1, 7))

        # --- Approve ---
        if choice == 1:
            dm.approve(draft_id)
            console.print(f"\n[green]Draft {draft_id} approved![/green]")
            console.print(f"[dim]Run: social-plugin post --id {draft_id}[/dim]")
            break

        # --- Change tone ---
        elif choice == 2:
            current_tone = draft.tone or config.generation.get("default_tone", "")
            console.print(f"[dim]Current tone: {current_tone}[/dim]")
            new_tone = click.prompt("New tone (e.g. casual, bold, humorous, technical)")

            from social_plugin.generator.content_generator import ContentGenerator
            generator = ContentGenerator(config, db, dm)

            console.print("[dim]Regenerating...[/dim]")
            draft = generator.regenerate(draft_id, new_tone)
            if draft:
                _display_draft(draft)
            else:
                console.print("[red]Regeneration failed[/red]")
                break

        # --- Add context ---
        elif choice == 3:
            console.print("[dim]Provide additional information or context to incorporate:[/dim]")
            extra_info = click.prompt("Additional info")

            from social_plugin.generator.llm_client import create_llm_client
            from social_plugin.generator.prompts import build_tweet_system_prompt, build_linkedin_system_prompt
            from social_plugin.drafts.models import Platform

            gen_cfg = config.generation
            llm = create_llm_client(
                model=gen_cfg.get("model", "claude-sonnet-4-5-20250929"),
                max_tokens=gen_cfg.get("max_tokens", 4096),
                temperature=gen_cfg.get("temperature", 0.7),
                provider=gen_cfg.get("provider"),
            )

            tone = draft.tone or gen_cfg.get("default_tone", "")
            if draft.platform == Platform.TWITTER:
                system_prompt = build_tweet_system_prompt(tone=tone)
            else:
                system_prompt = build_linkedin_system_prompt(tone=tone)

            user_prompt = (
                f"Here is an existing {draft.platform.value} post:\n\n"
                f"{draft.content}\n\n"
                f"Rewrite it incorporating this additional information: {extra_info}\n\n"
                f"Keep the same general style and tone. Output ONLY the rewritten text."
            )

            console.print("[dim]Regenerating with added context...[/dim]")
            result = llm.generate(system_prompt, user_prompt)
            content = result.text.strip()
            dm.update_content(draft_id, content, draft.hashtags)
            draft = dm.get(draft_id)
            _display_draft(draft)

        # --- Manual edit ---
        elif choice == 4:
            editor = os.environ.get("EDITOR", "vim")
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(draft.display_content)
                tmp_path = f.name

            try:
                subprocess.run([editor, tmp_path], check=True)
                with open(tmp_path) as f:
                    new_content = f.read().strip()

                if new_content != draft.display_content:
                    dm.update_content(draft_id, new_content)
                    draft = dm.get(draft_id)
                    console.print("[green]Content updated[/green]")
                    _display_draft(draft)
                else:
                    console.print("[dim]No changes made[/dim]")
            finally:
                os.unlink(tmp_path)

        # --- Hashtags ---
        elif choice == 5:
            import json
            current_tags = draft.hashtags or []
            console.print(f"[dim]Current hashtags: {', '.join(current_tags) if current_tags else 'none'}[/dim]")
            action = click.prompt("Add or remove?", type=click.Choice(["add", "remove", "replace"]))

            if action == "add":
                new_tags = click.prompt("Hashtags to add (comma-separated, e.g. #NewTag, #Other)")
                tags_to_add = [t.strip() for t in new_tags.split(",") if t.strip()]
                updated_tags = current_tags + [t if t.startswith("#") else f"#{t}" for t in tags_to_add]
            elif action == "remove":
                tag_to_remove = click.prompt("Hashtag to remove")
                tag_to_remove = tag_to_remove.strip()
                updated_tags = [t for t in current_tags if t.lower() != tag_to_remove.lower()]
            else:  # replace
                new_tags = click.prompt("New hashtags (comma-separated)")
                updated_tags = [t.strip() if t.strip().startswith("#") else f"#{t.strip()}" for t in new_tags.split(",") if t.strip()]

            dm.update_content(draft_id, draft.content, updated_tags)
            draft = dm.get(draft_id)
            console.print(f"[green]Hashtags updated: {', '.join(draft.hashtags)}[/green]")
            _display_draft(draft)

        # --- Reject ---
        elif choice == 6:
            notes = click.prompt("Rejection reason (optional)", default="", show_default=False)
            dm.reject(draft_id, notes)
            console.print(f"[yellow]Draft {draft_id} rejected[/yellow]")
            break

        # --- Skip ---
        elif choice == 7:
            console.print(f"[dim]Draft {draft_id} left as pending[/dim]")
            break


# =============================================================================
# approve
# =============================================================================

@cli.command("approve")
@click.argument("draft_id")
@click.pass_context
def approve_draft(ctx, draft_id: str):
    """Approve a pending draft for posting."""
    _, _, dm = _init(ctx.obj.get("config_path"))

    if dm.approve(draft_id):
        console.print(f"[green]Draft {draft_id} approved[/green]")
    else:
        console.print(f"[red]Could not approve draft {draft_id} (not found or not pending)[/red]")


# =============================================================================
# reject
# =============================================================================

@cli.command("reject")
@click.argument("draft_id")
@click.option("--notes", "-n", default="", help="Rejection reason")
@click.pass_context
def reject_draft(ctx, draft_id: str, notes: str):
    """Reject a pending draft."""
    _, _, dm = _init(ctx.obj.get("config_path"))

    if dm.reject(draft_id, notes):
        console.print(f"[yellow]Draft {draft_id} rejected[/yellow]")
    else:
        console.print(f"[red]Could not reject draft {draft_id}[/red]")


# =============================================================================
# delete
# =============================================================================

@cli.command("delete")
@click.argument("draft_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete_draft(ctx, draft_id: str, yes: bool):
    """Delete a draft permanently."""
    _, _, dm = _init(ctx.obj.get("config_path"))

    draft = dm.get(draft_id)
    if draft is None:
        console.print(f"[red]Draft {draft_id} not found[/red]")
        raise click.Abort()

    if not yes:
        console.print(f"  [bold]ID:[/bold] {draft.id}")
        console.print(f"  [bold]Platform:[/bold] {draft.platform.value}")
        console.print(f"  [bold]Status:[/bold] {draft.status.value}")
        console.print(f"  [bold]Content:[/bold] {draft.content[:80]}...")
        if not click.confirm(f"\nDelete this draft?", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    if dm.delete(draft_id):
        console.print(f"[green]Draft {draft_id} deleted[/green]")
    else:
        console.print(f"[red]Could not delete draft {draft_id}[/red]")


# =============================================================================
# list
# =============================================================================

@cli.command("list")
@click.option("--last", "limit", default=10, help="Number of recent drafts to show")
@click.pass_context
def list_recent(ctx, limit: int):
    """List recent drafts ordered by date."""
    _, db, _ = _init(ctx.obj.get("config_path"))

    from social_plugin.drafts.models import Draft

    rows = db.get_latest_drafts(limit)
    if not rows:
        console.print("[dim]No drafts found[/dim]")
        return

    drafts = [Draft.from_db_row(r) for r in rows]

    table = Table(title=f"Recent Drafts (last {limit})")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Platform", style="magenta")
    table.add_column("Content", style="white", max_width=55)
    table.add_column("Status", style="green")
    table.add_column("Created", style="dim")

    for draft in drafts:
        preview = draft.content[:50].replace("\n", " ")
        table.add_row(
            draft.id,
            draft.platform.value,
            preview + "..." if len(draft.content) > 50 else preview,
            draft.status.value,
            str(draft.created_at)[:16] if draft.created_at else "",
        )

    console.print(table)


# =============================================================================
# edit
# =============================================================================

@cli.command("edit")
@click.argument("draft_id")
@click.pass_context
def edit_draft(ctx, draft_id: str):
    """Open a draft in $EDITOR for manual editing."""
    _, _, dm = _init(ctx.obj.get("config_path"))

    draft = dm.get(draft_id)
    if draft is None:
        console.print(f"[red]Draft {draft_id} not found[/red]")
        raise click.Abort()

    editor = os.environ.get("EDITOR", "vim")
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(draft.display_content)
        tmp_path = f.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            new_content = f.read().strip()

        if new_content != draft.display_content:
            dm.update_content(draft_id, new_content)
            console.print(f"[green]Draft {draft_id} updated[/green]")
        else:
            console.print(f"[dim]No changes made[/dim]")
    finally:
        os.unlink(tmp_path)


# =============================================================================
# regen
# =============================================================================

@cli.command("regen")
@click.argument("draft_id")
@click.option("--tone", "-t", required=True, help="New tone for regeneration")
@click.pass_context
def regen_draft(ctx, draft_id: str, tone: str):
    """Regenerate a draft with a new tone via Claude."""
    config, db, dm = _init(ctx.obj.get("config_path"))

    from social_plugin.generator.content_generator import ContentGenerator

    generator = ContentGenerator(config, db, dm)
    draft = generator.regenerate(draft_id, tone)

    if draft:
        console.print(Panel(
            draft.display_content,
            title=f"Regenerated [{draft.platform.value}] {draft.id}",
            subtitle=f"tone: {tone}",
            border_style="cyan",
        ))
    else:
        console.print(f"[red]Could not regenerate draft {draft_id}[/red]")


# =============================================================================
# post
# =============================================================================

@cli.command("post")
@click.option("--all-approved", is_flag=True, help="Post all approved drafts")
@click.option("--id", "draft_id", default=None, help="Post a specific draft by ID")
@click.option("--dry-run", is_flag=True, help="Simulate posting without actually posting")
@click.pass_context
def post_content(ctx, all_approved: bool, draft_id: str | None, dry_run: bool):
    """Post approved drafts to social media."""
    config, db, dm = _init(ctx.obj.get("config_path"))

    from social_plugin.publisher.twitter_publisher import TwitterPublisher
    from social_plugin.publisher.linkedin_publisher import LinkedInPublisher
    from social_plugin.notifications.slack_notifier import SlackNotifier

    run_id = db.start_run("post")
    twitter_pub = TwitterPublisher(config, db, dm)
    linkedin_pub = LinkedInPublisher(config, db, dm)
    notifier = SlackNotifier(config)
    results: list[dict] = []

    try:
        if draft_id:
            draft = dm.get(draft_id)
            if draft is None:
                console.print(f"[red]Draft {draft_id} not found[/red]")
                raise click.Abort()
            if draft.status != DraftStatus.APPROVED:
                console.print(f"[yellow]Draft {draft_id} is {draft.status.value}, not approved[/yellow]")
                raise click.Abort()

            if draft.platform == Platform.TWITTER:
                result = twitter_pub.post(draft, dry_run=dry_run)
            else:
                result = linkedin_pub.post(draft, dry_run=dry_run)

            if result:
                results.append(result)
                if not dry_run:
                    notifier.notify_posted(draft, result.get("url", ""))

        elif all_approved:
            twitter_results = twitter_pub.post_all_approved(dry_run=dry_run)
            linkedin_results = linkedin_pub.post_all_approved(dry_run=dry_run)
            results = twitter_results + linkedin_results

            if not dry_run:
                for r in results:
                    if "draft_id" in r:
                        d = dm.get(r["draft_id"])
                        if d:
                            notifier.notify_posted(d, r.get("url", ""))
        else:
            console.print("[yellow]Specify --all-approved or --id <draft_id>[/yellow]")
            raise click.Abort()

        if dry_run:
            console.print(Panel("[yellow]DRY RUN — nothing was posted[/yellow]"))

        for r in results:
            if r.get("dry_run"):
                console.print(f"[dim]Would post: {r.get('text', '')[:80]}...[/dim]")
            elif r.get("mode") == "manual":
                console.print(f"[blue]LinkedIn post copied to clipboard[/blue]")
                if r.get("instructions"):
                    console.print(f"[dim]{r['instructions']}[/dim]")
            else:
                url = r.get("url", "")
                console.print(f"[green]Posted: {url}[/green]")

        console.print(f"\n[green]{len(results)} post(s) processed[/green]")
        db.complete_run(run_id, "success", {"posted": len(results)})
    except click.Abort:
        db.complete_run(run_id, "failed")
        raise
    except Exception as e:
        db.complete_run(run_id, "failed", error=str(e))
        notifier.notify_error(str(e), "post command")
        console.print(f"[red]Error posting: {e}[/red]")
        raise click.Abort()


# =============================================================================
# run-all
# =============================================================================

@cli.command("run-all")
@click.option("--dry-run", is_flag=True, help="Run pipeline without saving/posting")
@click.pass_context
def run_all(ctx, dry_run: bool):
    """Run full pipeline: fetch trends -> fetch sources -> generate drafts."""
    config, db, dm = _init(ctx.obj.get("config_path"))

    run_id = db.start_run("full_pipeline")
    summary = {}

    try:
        # 1. Fetch trends
        console.print("[bold]Step 1/3: Fetching trends...[/bold]")
        from social_plugin.trends.twitter_trends import TwitterTrendFetcher
        from social_plugin.trends.linkedin_trends import LinkedInTrendFetcher

        tt = TwitterTrendFetcher(config, db)
        lt = LinkedInTrendFetcher(config, db)
        twitter_trends = tt.fetch()
        linkedin_trends = lt.fetch()
        summary["trends"] = len(twitter_trends) + len(linkedin_trends)
        console.print(f"  [green]{summary['trends']} trends fetched[/green]")

        # 2. Fetch sources
        console.print("[bold]Step 2/3: Fetching sources...[/bold]")
        source_count = 0
        sources_cfg = config.sources

        gdocs = sources_cfg.get("google_docs", [])
        if gdocs:
            from social_plugin.sources.gdocs_reader import GoogleDocsReader
            reader = GoogleDocsReader(db)
            docs = reader.read_all(gdocs)
            source_count += len(docs)

        pdfs = sources_cfg.get("pdfs", [])
        remote_pdfs = [p for p in pdfs if p.get("url")]
        if remote_pdfs:
            from social_plugin.sources.pdf_reader import PDFReader
            reader = PDFReader(db)
            docs = reader.read_all(remote_pdfs)
            source_count += len(docs)

        local = sources_cfg.get("local_files", [])
        local_pdfs = [{"path": p.get("path"), "name": p.get("name", "")} for p in pdfs if p.get("path")]
        all_local = local + local_pdfs
        if all_local:
            from social_plugin.sources.local_reader import LocalReader
            reader = LocalReader(db)
            docs = reader.read_all(all_local)
            source_count += len(docs)

        summary["sources"] = source_count
        console.print(f"  [green]{source_count} sources read[/green]")

        # 3. Generate drafts
        console.print("[bold]Step 3/3: Generating drafts...[/bold]")
        from social_plugin.generator.content_generator import ContentGenerator
        from social_plugin.notifications.slack_notifier import SlackNotifier

        generator = ContentGenerator(config, db, dm)
        drafts = generator.generate_all(dry_run=dry_run)
        summary["drafts"] = len(drafts)

        for draft in drafts:
            console.print(Panel(
                draft.display_content,
                title=f"[{draft.platform.value}] {draft.id}",
                border_style="cyan" if draft.platform == Platform.TWITTER else "blue",
            ))

        if not dry_run and drafts:
            notifier = SlackNotifier(config)
            notifier.notify_drafts_ready(drafts)
            notifier.notify_pipeline_complete(summary)

        # Save config snapshot
        if not dry_run:
            config_yaml = yaml.dump(config.raw)
            config_hash = hashlib.sha256(config_yaml.encode()).hexdigest()[:16]
            db.save_config_snapshot(config_hash, config_yaml)

        console.print(f"\n[green]Pipeline complete: {summary}[/green]")
        db.complete_run(run_id, "success", summary)
    except Exception as e:
        db.complete_run(run_id, "failed", summary, error=str(e))
        console.print(f"[red]Pipeline error: {e}[/red]")
        raise click.Abort()


# =============================================================================
# stats
# =============================================================================

@cli.command("stats")
@click.pass_context
def show_stats(ctx):
    """Show analytics dashboard."""
    config, db, _ = _init(ctx.obj.get("config_path"))

    from social_plugin.analytics.tracker import AnalyticsTracker
    tracker = AnalyticsTracker(db)

    stats = tracker.get_overall_stats()
    today_summary = tracker.get_daily_summary()

    # Overall stats
    console.print(Panel("[bold]Overall Statistics[/bold]", border_style="green"))

    draft_table = Table(title="Draft Counts by Status")
    draft_table.add_column("Status", style="cyan")
    draft_table.add_column("Count", style="white", justify="right")
    for status, count in stats.get("draft_counts", {}).items():
        draft_table.add_row(status, str(count))
    console.print(draft_table)

    console.print(f"\n[bold]Engagement:[/bold]")
    console.print(f"  Total posts: {stats['total_posts']}")
    console.print(f"  Likes: {stats['total_likes']}")
    console.print(f"  Shares/Retweets: {stats['total_shares']}")
    console.print(f"  Comments: {stats['total_comments']}")
    console.print(f"  Impressions: {stats['total_impressions']}")

    console.print(f"\n[bold]Generation Costs:[/bold]")
    console.print(f"  Total tokens: {stats['total_tokens']:,}")
    console.print(f"  Estimated cost: ${stats['total_cost']:.4f}")

    # Today's summary
    console.print(Panel(f"[bold]Today ({today_summary['date']})[/bold]", border_style="blue"))
    console.print(f"  Trends fetched: {today_summary['trends_fetched']}")
    console.print(f"  Drafts created: {today_summary['drafts_created']}")
    console.print(f"  Drafts posted: {today_summary['drafts_posted']}")

    # Recent runs
    if stats.get("recent_runs"):
        run_table = Table(title="Recent Pipeline Runs")
        run_table.add_column("Type", style="cyan")
        run_table.add_column("Status", style="green")
        run_table.add_column("Started", style="dim")
        for run in stats["recent_runs"]:
            run_table.add_row(
                run.get("run_type", ""),
                run.get("status", ""),
                str(run.get("started_at", ""))[:16],
            )
        console.print(run_table)


# =============================================================================
# history
# =============================================================================

@cli.command("history")
@click.option("--days", default=30, help="Number of days to look back")
@click.pass_context
def show_history(ctx, days: int):
    """Show content history."""
    config, db, _ = _init(ctx.obj.get("config_path"))

    from social_plugin.analytics.tracker import AnalyticsTracker
    tracker = AnalyticsTracker(db)

    history = tracker.get_content_history(days=days)

    if not history:
        console.print(f"[dim]No content in the last {days} days[/dim]")
        return

    table = Table(title=f"Content History (last {days} days)")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Platform", style="magenta")
    table.add_column("Content", style="white", max_width=50)
    table.add_column("Status", style="green")
    table.add_column("Likes", justify="right")
    table.add_column("Created", style="dim")

    for item in history:
        content_preview = (item.get("content") or "")[:45].replace("\n", " ")
        table.add_row(
            item.get("id", ""),
            item.get("platform", ""),
            content_preview + "..." if len(item.get("content", "")) > 45 else content_preview,
            item.get("status", ""),
            str(item.get("likes") or 0),
            str(item.get("created_at", ""))[:16],
        )

    console.print(table)


# =============================================================================
# expire
# =============================================================================

@cli.command("expire")
@click.option("--days", default=7, help="Expire drafts older than N days")
@click.pass_context
def expire_drafts(ctx, days: int):
    """Expire old pending drafts."""
    _, _, dm = _init(ctx.obj.get("config_path"))

    count = dm.expire_old(days)
    if count:
        console.print(f"[yellow]Expired {count} draft(s) older than {days} days[/yellow]")
    else:
        console.print("[dim]No drafts to expire[/dim]")


# =============================================================================
# auth-check
# =============================================================================

@cli.command("auth-check")
@click.option("--platform", type=click.Choice(["twitter", "linkedin", "google", "all"]), default="all")
@click.pass_context
def auth_check(ctx, platform: str):
    """Verify API credentials for a platform."""
    config, _, _ = _init(ctx.obj.get("config_path"))

    checks = []
    if platform in ("twitter", "all"):
        checks.append(("Twitter", _check_twitter))
    if platform in ("linkedin", "all"):
        checks.append(("LinkedIn", _check_linkedin))
    if platform in ("google", "all"):
        checks.append(("Google", _check_google))

    # Check LLM provider API key
    if platform == "all":
        config, _, _ = _init(ctx.obj.get("config_path"))
        provider = config.llm_provider
        provider_env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}
        env_key = provider_env.get(provider, "ANTHROPIC_API_KEY")
        api_key = os.environ.get(env_key)
        if api_key:
            console.print(f"[green]{provider.title()} API key ({env_key}): configured[/green]")
        else:
            console.print(f"[red]{provider.title()} API key ({env_key}): not set[/red]")

    for name, check_fn in checks:
        try:
            result = check_fn()
            console.print(f"[green]{name}: {result}[/green]")
        except Exception as e:
            console.print(f"[red]{name}: {e}[/red]")


def _check_twitter() -> str:
    from social_plugin.auth.twitter_auth import verify_twitter_credentials
    info = verify_twitter_credentials()
    return f"Authenticated as @{info['username']}"


def _check_linkedin() -> str:
    from social_plugin.auth.linkedin_auth import verify_linkedin_credentials
    result = verify_linkedin_credentials()
    if result is None:
        return "Not configured (manual posting mode)"
    return f"Token present (auto_post={result.get('auto_post', False)})"


def _check_google() -> str:
    from social_plugin.auth.google_auth import get_google_credentials
    creds = get_google_credentials()
    return f"Service account loaded: {creds.service_account_email}"


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    cli()
