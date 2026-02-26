"""Trend data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trend:
    """A trending topic discovered from RSS feeds."""

    source: str  # 'twitter_rss', 'linkedin_rss', 'industry_rss'
    title: str
    summary: str = ""
    url: str = ""
    author: str = ""
    relevance_score: float = 0.0
    fetched_at: datetime | None = None
    date: str = ""  # YYYY-MM-DD

    def to_db_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "summary": self.summary or None,
            "url": self.url or None,
            "author": self.author or None,
            "relevance_score": self.relevance_score,
            "date": self.date,
        }

    @classmethod
    def from_db_row(cls, row) -> Trend:
        data = dict(row)
        return cls(
            source=data["source"],
            title=data["title"],
            summary=data.get("summary") or "",
            url=data.get("url") or "",
            author=data.get("author") or "",
            relevance_score=data.get("relevance_score") or 0.0,
            fetched_at=data.get("fetched_at"),
            date=data.get("date") or "",
        )
