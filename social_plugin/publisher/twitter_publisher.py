"""Post tweets via tweepy (pay-per-use X API)."""

from __future__ import annotations

from pathlib import Path

from social_plugin.auth.twitter_auth import get_twitter_api_v1, get_twitter_client
from social_plugin.config import Config
from social_plugin.db import Database
from social_plugin.drafts.draft_manager import DraftManager
from social_plugin.drafts.models import Draft
from social_plugin.generator.llm_client import LLMClient
from social_plugin.publisher.media_uploader import validate_image
from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()


class TwitterPublisher:
    """Publish tweets using Twitter API v2 (free tier)."""

    def __init__(self, config: Config, db: Database, draft_manager: DraftManager, llm: LLMClient | None = None):
        self.config = config
        self.db = db
        self.draft_manager = draft_manager
        self.llm = llm
        self._client = None
        self._api_v1 = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_twitter_client()
        return self._client

    @property
    def api_v1(self):
        if self._api_v1 is None:
            self._api_v1 = get_twitter_api_v1()
        return self._api_v1

    def _check_daily_limit(self) -> bool:
        """Check if we've hit the daily posting limit."""
        max_per_day = self.config.accounts.get("twitter", {}).get("max_posts_per_day", 1)
        posted_today = self.db.get_posts_count_today("twitter")
        if posted_today >= max_per_day:
            logger.warning("Daily tweet limit reached (%d/%d)", posted_today, max_per_day)
            return False
        return True

    def _upload_media(self, image_path: str) -> int | None:
        """Upload media via v1.1 API and return media_id."""
        if not validate_image(image_path, "twitter"):
            return None
        try:
            media = self.api_v1.media_upload(image_path)
            logger.info("Uploaded media: %s -> id=%s", image_path, media.media_id)
            return media.media_id
        except Exception as e:
            logger.error("Media upload failed: %s", e)
            return None

    @with_retry(max_attempts=2, retry_on=(Exception,))
    def _post_tweet(self, text: str, media_ids: list[int] | None = None) -> dict:
        """Post a tweet and return response data."""
        kwargs = {"text": text}
        if media_ids:
            kwargs["media_ids"] = media_ids

        response = self.client.create_tweet(**kwargs)
        tweet_id = response.data["id"]
        return {"tweet_id": tweet_id, "url": f"https://x.com/i/status/{tweet_id}"}

    def _regenerate_to_fit(self, draft: Draft, char_limit: int) -> str | None:
        """Use LLM to regenerate tweet content to fit within char_limit."""
        from social_plugin.generator.prompts import build_tweet_system_prompt, build_regen_prompt

        topic = self.config.topics.get("primary", "Physical AI and Robotics")
        rules = self.config.rules

        system_prompt = build_tweet_system_prompt(
            max_length=char_limit,
            tone=draft.tone or "concise",
            hashtags=draft.hashtags,
            compliance_note=self.config.safety.get("compliance_note", ""),
            topic=topic,
            rules=rules,
        )
        system_prompt += f"\n\nCRITICAL: Your response MUST be under {char_limit} characters including hashtags."
        user_prompt = build_regen_prompt(draft.content, "concise", "tweet")
        result = self.llm.generate(system_prompt, user_prompt)
        text = result.text.strip()
        if len(text) <= char_limit:
            return text
        return None

    def post(self, draft: Draft, dry_run: bool = False) -> dict | None:
        """Post a tweet from an approved draft."""
        if not self._check_daily_limit():
            return None

        text = draft.display_content
        x_premium = self.config.accounts.get("twitter", {}).get("x_premium", False)
        char_limit = 25000 if x_premium else 280

        # Fallback: drop appended hashtags if over limit
        if len(text) > char_limit and len(draft.content) <= char_limit:
            text = draft.content
            logger.info("Dropped appended hashtags to fit %d-char limit", char_limit)

        if len(text) > char_limit:
            if self.llm:
                regenerated = self._regenerate_to_fit(draft, char_limit)
                if regenerated:
                    text = regenerated
                    self.draft_manager.update_content(draft.id, text, draft.hashtags)
                    logger.info("Auto-regenerated tweet to fit %d-char limit", char_limit)
                else:
                    logger.error(
                        "Auto-regenerated tweet still exceeds %d-char limit. "
                        "Use 'social-plugin regen %s -t concise'.",
                        char_limit, draft.id,
                    )
                    return None
            else:
                logger.error(
                    "Tweet (%d chars) exceeds %d-char limit. "
                    "Use 'social-plugin regen %s -t concise' to regenerate within the limit.",
                    len(text), char_limit, draft.id,
                )
                return None

        if dry_run:
            logger.info("[DRY RUN] Would post tweet: %s", text[:100])
            return {"dry_run": True, "text": text}

        # Handle media
        media_ids = None
        if draft.image_path and Path(draft.image_path).exists():
            media_id = self._upload_media(draft.image_path)
            if media_id:
                media_ids = [media_id]

        try:
            result = self._post_tweet(text, media_ids)
            post_url = result["url"]
            self.draft_manager.mark_posted(draft.id, post_url)

            # Record analytics
            self.db.insert_analytics({
                "draft_id": draft.id,
                "platform": "twitter",
                "post_url": post_url,
                "posted_at": draft.posted_at or "now",
            })

            logger.info("Posted tweet: %s -> %s", draft.id, post_url)
            return result
        except Exception as e:
            error_msg = str(e)
            logger.error("Tweet posting failed for %s: %s", draft.id, error_msg)
            return None

    def post_all_approved(self, dry_run: bool = False) -> list[dict]:
        """Post all approved Twitter drafts."""
        approved = self.draft_manager.list_approved()
        twitter_drafts = [d for d in approved if d.platform.value == "twitter"]
        results = []

        for draft in twitter_drafts:
            result = self.post(draft, dry_run=dry_run)
            if result:
                results.append(result)
            if not dry_run and not self._check_daily_limit():
                break

        return results
