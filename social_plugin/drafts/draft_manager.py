"""Draft CRUD operations via SQLite with status transitions."""

from __future__ import annotations

from datetime import datetime

from social_plugin.db import Database
from social_plugin.drafts.models import Draft, DraftStatus, Platform
from social_plugin.utils.logger import get_logger

logger = get_logger()


class DraftManager:
    """Manages draft lifecycle via SQLite."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, draft: Draft) -> Draft:
        """Save a new draft to the database."""
        self.db.insert_draft(draft.to_db_dict())
        logger.info("Created draft %s [%s] on %s", draft.id, draft.status.value, draft.platform.value)
        return draft

    def get(self, draft_id: str) -> Draft | None:
        """Retrieve a draft by ID."""
        row = self.db.get_draft(draft_id)
        if row is None:
            return None
        return Draft.from_db_row(row)

    def list_by_status(self, status: DraftStatus, platform: Platform | None = None) -> list[Draft]:
        """List drafts with a given status."""
        rows = self.db.get_drafts_by_status(
            status.value,
            platform.value if platform else None,
        )
        return [Draft.from_db_row(r) for r in rows]

    def list_pending(self) -> list[Draft]:
        return self.list_by_status(DraftStatus.PENDING)

    def list_approved(self) -> list[Draft]:
        return self.list_by_status(DraftStatus.APPROVED)

    def approve(self, draft_id: str, notes: str | None = None) -> bool:
        """Approve a pending or failed draft with optional positive notes."""
        draft = self.get(draft_id)
        if draft is None:
            logger.error("Draft %s not found", draft_id)
            return False
        if draft.status not in (DraftStatus.PENDING, DraftStatus.FAILED):
            logger.warning("Draft %s is %s, cannot approve", draft_id, draft.status.value)
            return False
        kwargs: dict = {"reviewed_at": datetime.utcnow().isoformat()}
        if notes:
            kwargs["reviewer_notes"] = notes
        self.db.update_draft_status(draft_id, DraftStatus.APPROVED.value, **kwargs)
        logger.info("Approved draft %s", draft_id)
        return True

    def reject(self, draft_id: str, notes: str = "") -> bool:
        """Reject a pending draft with optional notes."""
        draft = self.get(draft_id)
        if draft is None:
            logger.error("Draft %s not found", draft_id)
            return False
        if draft.status != DraftStatus.PENDING:
            logger.warning("Draft %s is %s, not pending", draft_id, draft.status.value)
            return False
        self.db.update_draft_status(
            draft_id,
            DraftStatus.REJECTED.value,
            reviewed_at=datetime.utcnow().isoformat(),
            reviewer_notes=notes or None,
        )
        logger.info("Rejected draft %s", draft_id)
        return True

    def mark_posted(self, draft_id: str, post_url: str = "") -> bool:
        """Mark an approved draft as posted."""
        draft = self.get(draft_id)
        if draft is None or draft.status != DraftStatus.APPROVED:
            return False
        self.db.update_draft_status(
            draft_id,
            DraftStatus.POSTED.value,
            posted_at=datetime.utcnow().isoformat(),
            post_url=post_url or None,
        )
        logger.info("Posted draft %s -> %s", draft_id, post_url or "(no URL)")
        return True

    def mark_failed(self, draft_id: str, error: str) -> bool:
        """Mark a draft as failed with error message."""
        self.db.update_draft_status(draft_id, DraftStatus.FAILED.value, error_message=error)
        logger.error("Draft %s failed: %s", draft_id, error)
        return True

    def delete(self, draft_id: str) -> bool:
        """Delete a draft permanently."""
        draft = self.get(draft_id)
        if draft is None:
            logger.error("Draft %s not found", draft_id)
            return False
        deleted = self.db.delete_draft(draft_id)
        if deleted:
            logger.info("Deleted draft %s", draft_id)
        return deleted

    def update_content(self, draft_id: str, content: str, hashtags: list[str] | None = None) -> bool:
        """Update draft content (e.g., after manual edit or regeneration)."""
        import json

        data: dict = {"content": content, "status": DraftStatus.PENDING.value}
        if hashtags is not None:
            data["hashtags"] = json.dumps(hashtags)
        self.db.update("drafts", data, "id = ?", (draft_id,))
        logger.info("Updated content for draft %s", draft_id)
        return True

    def get_recent(self, days: int = 7, platform: Platform | None = None) -> list[Draft]:
        """Get recent drafts."""
        rows = self.db.get_recent_drafts(days, platform.value if platform else None)
        return [Draft.from_db_row(r) for r in rows]

    def expire_old(self, days: int = 7) -> int:
        """Expire drafts older than N days that are still pending."""
        count = self.db.expire_old_drafts(days)
        if count:
            logger.info("Expired %d old drafts", count)
        return count
