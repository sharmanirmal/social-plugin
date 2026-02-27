"""LinkedIn-related trend discovery via Google News RSS + industry feeds."""

from __future__ import annotations

from datetime import date

import feedparser
import httpx

from social_plugin.config import Config
from social_plugin.db import Database
from social_plugin.trends.models import Trend
from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()


class LinkedInTrendFetcher:
    """Fetch trending topics relevant to LinkedIn from RSS feeds."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.keywords = config.topics.get("keywords", [])
        self.max_results = config.trends_config.get("max_results", 20)

    def _get_feeds(self) -> list[str]:
        """Get RSS feeds for LinkedIn trends + industry feeds."""
        feeds = self.config.trends_config.get("rss_feeds", [])
        # Include LinkedIn-specific and general industry feeds (exclude Twitter/X-specific)
        result = [
            f for f in feeds
            if "site:twitter.com" not in f.lower() and "site:x.com" not in f.lower()
        ]
        if not result:
            primary = self.config.topics.get("primary", "Physical AI and Robotics")
            result = [
                f"https://news.google.com/rss/search?q={primary.replace(' ', '+')}",
            ]
        return result

    def _score_relevance(self, title: str, summary: str) -> float:
        """Score how relevant a trend is to our keywords."""
        text = f"{title} {summary}".lower()
        score = 0.0
        for kw in self.keywords:
            if kw.lower() in text:
                score += 1.0
        max_score = max(len(self.keywords), 1)
        return min(score / max_score, 1.0)

    @with_retry(max_attempts=3, retry_on=(httpx.HTTPError, ConnectionError))
    def _fetch_feed(self, url: str) -> list[dict]:
        """Fetch and parse a single RSS feed."""
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        return feed.entries

    def fetch(self) -> list[Trend]:
        """Fetch LinkedIn-related trends from all configured RSS feeds."""
        today = date.today().isoformat()
        trends: list[Trend] = []
        feeds = self._get_feeds()

        for feed_url in feeds:
            try:
                entries = self._fetch_feed(feed_url)
                logger.info("Fetched %d entries from %s", len(entries), feed_url[:80])

                for entry in entries[: self.max_results]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    url = entry.get("link", "")
                    author = entry.get("author", "")

                    score = self._score_relevance(title, summary)
                    trend = Trend(
                        source="linkedin_rss",
                        title=title,
                        summary=summary,
                        url=url,
                        author=author,
                        relevance_score=score,
                        date=today,
                    )
                    trends.append(trend)
            except Exception as e:
                logger.warning("Failed to fetch feed %s: %s", feed_url[:80], e)

        trends.sort(key=lambda t: t.relevance_score, reverse=True)
        trends = trends[: self.max_results]

        for trend in trends:
            self.db.insert_trend(trend.to_db_dict())

        logger.info("Stored %d LinkedIn trends for %s", len(trends), today)
        return trends
