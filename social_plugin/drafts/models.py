"""Draft-related data models."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    TWITTER = "twitter"
    LINKEDIN = "linkedin"


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    POSTED = "posted"
    FAILED = "failed"
    EXPIRED = "expired"


def short_uuid() -> str:
    """Generate an 8-character short UUID."""
    return uuid.uuid4().hex[:8]


@dataclass
class Draft:
    """Represents a social media draft."""

    id: str = field(default_factory=short_uuid)
    platform: Platform = Platform.TWITTER
    content: str = ""
    hashtags: list[str] = field(default_factory=list)
    tone: str = ""
    source_reference: str = ""
    image_path: str | None = None
    status: DraftStatus = DraftStatus.PENDING
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    posted_at: datetime | None = None
    post_url: str | None = None
    reviewer_notes: str | None = None
    error_message: str | None = None
    generation_model: str | None = None
    generation_tokens: int | None = None
    generation_cost: float | None = None

    def to_db_dict(self) -> dict:
        """Convert to a dict suitable for SQLite insertion."""
        return {
            "id": self.id,
            "platform": self.platform.value if isinstance(self.platform, Platform) else self.platform,
            "content": self.content,
            "hashtags": json.dumps(self.hashtags) if self.hashtags else None,
            "tone": self.tone or None,
            "source_reference": self.source_reference or None,
            "image_path": self.image_path,
            "status": self.status.value if isinstance(self.status, DraftStatus) else self.status,
            "generation_model": self.generation_model,
            "generation_tokens": self.generation_tokens,
            "generation_cost": self.generation_cost,
        }

    @classmethod
    def from_db_row(cls, row) -> Draft:
        """Create a Draft from a SQLite row."""
        data = dict(row)
        hashtags = json.loads(data["hashtags"]) if data.get("hashtags") else []
        return cls(
            id=data["id"],
            platform=Platform(data["platform"]),
            content=data["content"],
            hashtags=hashtags,
            tone=data.get("tone") or "",
            source_reference=data.get("source_reference") or "",
            image_path=data.get("image_path"),
            status=DraftStatus(data["status"]),
            created_at=data.get("created_at"),
            reviewed_at=data.get("reviewed_at"),
            posted_at=data.get("posted_at"),
            post_url=data.get("post_url"),
            reviewer_notes=data.get("reviewer_notes"),
            error_message=data.get("error_message"),
            generation_model=data.get("generation_model"),
            generation_tokens=data.get("generation_tokens"),
            generation_cost=data.get("generation_cost"),
        )

    @property
    def display_content(self) -> str:
        """Content with hashtags appended for display (avoids duplicates)."""
        if self.hashtags:
            # Check if hashtags are already present in the content
            content_lower = self.content.lower()
            missing_tags = [t for t in self.hashtags if t.lower() not in content_lower]
            if missing_tags:
                tags = " ".join(missing_tags)
                return f"{self.content} {tags}"
        return self.content
