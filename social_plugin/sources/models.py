"""Source document data models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SourceDocument:
    """A reference document read from Google Docs, PDF, or local file."""

    source_type: str  # 'google_doc', 'pdf', 'local_file'
    source_path: str  # URL or local path
    title: str = ""
    content: str = ""
    content_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA256 hash of content."""
        self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()
        return self.content_hash

    def to_db_dict(self) -> dict:
        if not self.content_hash and self.content:
            self.compute_hash()
        return {
            "source_type": self.source_type,
            "source_path": self.source_path,
            "title": self.title or None,
            "content": self.content or None,
            "content_hash": self.content_hash or None,
        }

    @classmethod
    def from_db_row(cls, row) -> SourceDocument:
        data = dict(row)
        return cls(
            source_type=data["source_type"],
            source_path=data["source_path"],
            title=data.get("title") or "",
            content=data.get("content") or "",
            content_hash=data.get("content_hash") or "",
        )
