"""LinkedIn publisher — generates formatted drafts for manual posting.

Auto-posting will be enabled when LinkedIn Developer app is set up.
For now: formats draft + copies to clipboard.
"""

from __future__ import annotations

import subprocess
import sys

from social_plugin.config import Config
from social_plugin.db import Database
from social_plugin.drafts.draft_manager import DraftManager
from social_plugin.drafts.models import Draft
from social_plugin.utils.logger import get_logger

logger = get_logger()


class LinkedInPublisher:
    """Placeholder publisher for LinkedIn — manual posting mode."""

    def __init__(self, config: Config, db: Database, draft_manager: DraftManager):
        self.config = config
        self.db = db
        self.draft_manager = draft_manager
        self.auto_post = config.accounts.get("linkedin", {}).get("auto_post", False)

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to system clipboard."""
        try:
            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=text.encode(), check=True)
            elif sys.platform == "win32":
                subprocess.run(["clip.exe"], input=text.encode("utf-16le"), check=True)
            elif sys.platform == "linux":
                subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
            else:
                logger.warning("Clipboard not supported on %s", sys.platform)
                return False
            logger.info("Copied to clipboard")
            return True
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.warning("Could not copy to clipboard: %s", e)
            return False

    def format_post(self, draft: Draft) -> str:
        """Format a LinkedIn draft for posting."""
        text = draft.content
        if draft.hashtags:
            tags = " ".join(draft.hashtags)
            if tags not in text:
                text = f"{text}\n\n{tags}"
        return text

    def post(self, draft: Draft, dry_run: bool = False) -> dict | None:
        """Prepare a LinkedIn post for manual publishing."""
        text = self.format_post(draft)

        if dry_run:
            logger.info("[DRY RUN] LinkedIn post: %s", text[:100])
            return {"dry_run": True, "text": text}

        if self.auto_post:
            # Future: actual LinkedIn API posting
            logger.warning("LinkedIn auto-posting not yet implemented")

        # Copy to clipboard for manual posting
        copied = self._copy_to_clipboard(text)

        # Mark as posted (manual workflow)
        self.draft_manager.mark_posted(draft.id, "manual://linkedin")

        self.db.insert_analytics({
            "draft_id": draft.id,
            "platform": "linkedin",
            "post_url": "manual://linkedin",
            "posted_at": "now",
        })

        return {
            "mode": "manual",
            "copied_to_clipboard": copied,
            "text": text,
            "instructions": "Post copied to clipboard. Paste it on LinkedIn.",
        }

    def post_all_approved(self, dry_run: bool = False) -> list[dict]:
        """Prepare all approved LinkedIn drafts for posting."""
        approved = self.draft_manager.list_approved()
        linkedin_drafts = [d for d in approved if d.platform.value == "linkedin"]
        results = []

        max_per_day = self.config.accounts.get("linkedin", {}).get("max_posts_per_day", 1)
        for draft in linkedin_drafts[:max_per_day]:
            result = self.post(draft, dry_run=dry_run)
            if result:
                results.append(result)

        return results
