"""Content generation orchestrator: trends + docs → Claude → drafts."""

from __future__ import annotations

from datetime import date

from social_plugin.config import Config
from social_plugin.db import Database
from social_plugin.drafts.draft_manager import DraftManager
from social_plugin.drafts.models import Draft, Platform
from social_plugin.generator.llm_client import create_llm_client
from social_plugin.generator.prompts import (
    build_linkedin_system_prompt,
    build_regen_prompt,
    build_tweet_system_prompt,
    build_user_prompt,
    build_add_context_prompt,
)
from social_plugin.generator.safety import ContentSafety
from social_plugin.utils.logger import get_logger

logger = get_logger()


class ContentGenerator:
    """Orchestrates content generation from trends and sources using an LLM."""

    def __init__(self, config: Config, db: Database, draft_manager: DraftManager):
        self.config = config
        self.db = db
        self.draft_manager = draft_manager

        gen_cfg = config.generation
        self.llm = create_llm_client(
            model=gen_cfg.get("model", "claude-sonnet-4-5-20250929"),
            max_tokens=gen_cfg.get("max_tokens", 4096),
            temperature=gen_cfg.get("temperature", 0.7),
            provider=gen_cfg.get("provider"),
        )

        safety_cfg = config.safety
        self.safety = ContentSafety(
            blocked_words=safety_cfg.get("blocked_words", []),
            compliance_note=safety_cfg.get("compliance_note", ""),
        )

    def _get_recent_trends(self) -> list[dict]:
        """Get today's trends from the database."""
        today = date.today().isoformat()
        rows = self.db.get_trends(today)
        return [dict(r) for r in rows]

    def _get_recent_sources(self) -> list[dict]:
        """Get recently fetched source documents."""
        cache_ttl = self.config.sources.get("cache_ttl_hours", 24)
        rows = self.db.get_recent_source_documents(hours=cache_ttl)
        return [dict(r) for r in rows]

    def generate_tweet(self, tone: str | None = None, dry_run: bool = False) -> Draft | None:
        """Generate a tweet draft."""
        gen_cfg = self.config.generation
        tweet_cfg = gen_cfg.get("tweet", {})
        topics_cfg = self.config.topics

        tone = tone or gen_cfg.get("default_tone", "informative, thought-provoking, professional")
        hashtags = topics_cfg.get("hashtags", {}).get("twitter", ["#PhysicalAI", "#Robotics"])

        x_premium = self.config.accounts.get("twitter", {}).get("x_premium", False)
        max_length = tweet_cfg.get("max_length", 25000 if x_premium else 280)

        system_prompt = build_tweet_system_prompt(
            max_length=max_length,
            tone=tone,
            hashtags=hashtags,
            compliance_note=self.config.safety.get("compliance_note", ""),
        )

        trends = self._get_recent_trends()
        sources = self._get_recent_sources()

        if not sources:
            logger.warning("No source documents available — generated content will be based on trends and general knowledge only")

        # Fetch recent drafts for freshness context (last 15 drafts / 10 days)
        recent_rows = self.db.get_recent_drafts(days=10, platform="twitter")[:15]
        previous_content = [dict(r)["content"] for r in recent_rows] if recent_rows else None

        user_prompt = build_user_prompt(
            platform="Twitter",
            trends=trends,
            sources=sources,
            previous_drafts=previous_content,
        )

        result = self.llm.generate(system_prompt, user_prompt)

        # Safety check
        safety_result = self.safety.check(result.text)
        if not safety_result.is_safe:
            logger.warning("Tweet draft failed safety: %s", safety_result.summary)
            if self.config.safety.get("profanity_filter", True):
                result = self.llm.generate(
                    system_prompt + "\n\nIMPORTANT: Avoid any profanity, vulgarity, or inappropriate language.",
                    user_prompt,
                )

        content = result.text.strip()
        if len(content) > max_length:
            logger.warning("Tweet (%d chars) over %d-char limit — retrying with stricter constraint", len(content), max_length)
            result = self.llm.generate(
                system_prompt + f"\n\nCRITICAL: Your response MUST be under {max_length} characters including hashtags.",
                user_prompt,
            )
            content = result.text.strip()

        if dry_run:
            logger.info("[DRY RUN] Tweet: %s", content[:100])
            return Draft(platform=Platform.TWITTER, content=content, hashtags=hashtags, tone=tone)

        draft = Draft(
            platform=Platform.TWITTER,
            content=content,
            hashtags=hashtags,
            tone=tone,
            source_reference=f"trends:{len(trends)},sources:{len(sources)}",
            generation_model=result.model,
            generation_tokens=result.total_tokens,
            generation_cost=result.estimated_cost,
        )
        self.draft_manager.create(draft)
        return draft

    def generate_linkedin_post(self, tone: str | None = None, dry_run: bool = False) -> Draft | None:
        """Generate a LinkedIn post draft."""
        gen_cfg = self.config.generation
        li_cfg = gen_cfg.get("linkedin_post", {})
        topics_cfg = self.config.topics

        tone = tone or gen_cfg.get("default_tone", "thought-leadership, conversational")
        hashtags = topics_cfg.get("hashtags", {}).get("linkedin", ["#PhysicalAI", "#Robotics", "#AI"])

        system_prompt = build_linkedin_system_prompt(
            max_length=li_cfg.get("max_length", 3000),
            tone=tone,
            hashtags=hashtags,
            compliance_note=self.config.safety.get("compliance_note", ""),
        )

        trends = self._get_recent_trends()
        sources = self._get_recent_sources()

        if not sources:
            logger.warning("No source documents available — generated content will be based on trends and general knowledge only")

        # Fetch recent drafts for freshness context (last 15 drafts / 10 days)
        recent_rows = self.db.get_recent_drafts(days=10, platform="linkedin")[:15]
        previous_content = [dict(r)["content"] for r in recent_rows] if recent_rows else None

        user_prompt = build_user_prompt(
            platform="LinkedIn",
            trends=trends,
            sources=sources,
            previous_drafts=previous_content,
        )

        result = self.llm.generate(system_prompt, user_prompt)

        # Safety check
        safety_result = self.safety.check(result.text)
        if not safety_result.is_safe:
            logger.warning("LinkedIn draft failed safety: %s", safety_result.summary)
            if self.config.safety.get("profanity_filter", True):
                result = self.llm.generate(
                    system_prompt + "\n\nIMPORTANT: Avoid any profanity, vulgarity, or inappropriate language.",
                    user_prompt,
                )

        content = result.text.strip()

        if dry_run:
            logger.info("[DRY RUN] LinkedIn: %s", content[:100])
            return Draft(platform=Platform.LINKEDIN, content=content, hashtags=hashtags, tone=tone)

        draft = Draft(
            platform=Platform.LINKEDIN,
            content=content,
            hashtags=hashtags,
            tone=tone,
            source_reference=f"trends:{len(trends)},sources:{len(sources)}",
            generation_model=result.model,
            generation_tokens=result.total_tokens,
            generation_cost=result.estimated_cost,
        )
        self.draft_manager.create(draft)
        return draft

    def generate_all(self, tone: str | None = None, dry_run: bool = False) -> list[Draft]:
        """Generate all configured content (1 tweet + 1 LinkedIn post by default)."""
        drafts: list[Draft] = []

        tweet_cfg = self.config.generation.get("tweet", {})
        li_cfg = self.config.generation.get("linkedin_post", {})

        for _ in range(tweet_cfg.get("count_per_run", 1)):
            if self.config.accounts.get("twitter", {}).get("enabled", True):
                draft = self.generate_tweet(tone=tone, dry_run=dry_run)
                if draft:
                    drafts.append(draft)

        for _ in range(li_cfg.get("count_per_run", 1)):
            if self.config.accounts.get("linkedin", {}).get("enabled", True):
                draft = self.generate_linkedin_post(tone=tone, dry_run=dry_run)
                if draft:
                    drafts.append(draft)

        return drafts

    def regenerate(self, draft_id: str, new_tone: str) -> Draft | None:
        """Regenerate a draft with a new tone."""
        draft = self.draft_manager.get(draft_id)
        if draft is None:
            logger.error("Draft %s not found", draft_id)
            return None

        platform_name = "tweet" if draft.platform == Platform.TWITTER else "LinkedIn post"

        if draft.platform == Platform.TWITTER:
            system_prompt = build_tweet_system_prompt(tone=new_tone, is_rewrite=True)
        else:
            system_prompt = build_linkedin_system_prompt(tone=new_tone)

        user_prompt = build_regen_prompt(draft.content, new_tone, platform_name)
        result = self.llm.generate(system_prompt, user_prompt)

        # Safety check
        safety_result = self.safety.check(result.text)
        if not safety_result.is_safe:
            logger.warning("Regenerated draft failed safety: %s", safety_result.summary)

        content = result.text.strip()
        self.draft_manager.update_content(draft_id, content, draft.hashtags)
        logger.info("Regenerated draft %s with tone '%s'", draft_id, new_tone)

        return self.draft_manager.get(draft_id)
