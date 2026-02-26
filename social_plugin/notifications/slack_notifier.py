"""Slack webhook notifications."""

from __future__ import annotations

import json
import os

import httpx

from social_plugin.config import Config
from social_plugin.drafts.models import Draft
from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()


class SlackNotifier:
    """Send notifications via Slack incoming webhooks."""

    def __init__(self, config: Config):
        self.config = config
        self.enabled = config.notifications.get("slack", {}).get("enabled", False)
        webhook_env = config.notifications.get("slack", {}).get("webhook_url_env", "SLACK_WEBHOOK_URL")
        self.webhook_url = os.environ.get(webhook_env) if self.enabled else None
        self.channel = config.notifications.get("slack", {}).get("channel", "#social-content")

    @with_retry(max_attempts=2, retry_on=(httpx.HTTPError, ConnectionError))
    def _send(self, payload: dict) -> bool:
        """Send a payload to Slack webhook."""
        if not self.webhook_url:
            logger.debug("Slack not configured, skipping notification")
            return False

        response = httpx.post(self.webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Slack notification sent")
        return True

    def notify_drafts_ready(self, drafts: list[Draft]) -> bool:
        """Notify that new drafts are ready for review."""
        if not drafts:
            return False

        lines = ["*New drafts ready for review:*\n"]
        for draft in drafts:
            preview = draft.content[:60].replace("\n", " ")
            lines.append(f"• [{draft.platform.value}] \"{preview}...\" (ID: `{draft.id}`)")

        lines.append(f"\nRun `social-plugin drafts` to review.")

        return self._send({"text": "\n".join(lines)})

    def notify_posted(self, draft: Draft, post_url: str = "") -> bool:
        """Notify that a post went live."""
        text = f"*Posted [{draft.platform.value}]:* {draft.content[:80]}..."
        if post_url and not post_url.startswith("manual://"):
            text += f"\n<{post_url}|View post>"
        return self._send({"text": text})

    def notify_error(self, error_message: str, context: str = "") -> bool:
        """Notify about an error."""
        text = f"*Error in social-plugin:*\n```{error_message}```"
        if context:
            text += f"\nContext: {context}"
        return self._send({"text": text})

    def notify_pipeline_complete(self, summary: dict) -> bool:
        """Notify that a pipeline run completed."""
        lines = ["*Pipeline run complete:*"]
        for key, value in summary.items():
            lines.append(f"• {key}: {value}")
        return self._send({"text": "\n".join(lines)})
