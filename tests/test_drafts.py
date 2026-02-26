"""Tests for draft models and manager."""

import tempfile
from pathlib import Path

import pytest

from social_plugin.db import Database
from social_plugin.drafts.draft_manager import DraftManager
from social_plugin.drafts.models import Draft, DraftStatus, Platform, short_uuid


@pytest.fixture
def dm():
    """Create a draft manager with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        yield DraftManager(db)


def test_short_uuid():
    """Short UUID generates 8-char strings."""
    uid = short_uuid()
    assert len(uid) == 8
    assert uid.isalnum()


def test_draft_model():
    """Draft model creates and serializes correctly."""
    draft = Draft(
        platform=Platform.TWITTER,
        content="Test tweet",
        hashtags=["#AI", "#Robotics"],
        tone="casual",
    )
    assert len(draft.id) == 8
    assert draft.status == DraftStatus.PENDING

    db_dict = draft.to_db_dict()
    assert db_dict["platform"] == "twitter"
    assert '"#AI"' in db_dict["hashtags"]


def test_display_content():
    """Draft display_content appends hashtags."""
    draft = Draft(content="Hello world", hashtags=["#AI", "#ML"])
    assert "#AI #ML" in draft.display_content

    draft_no_tags = Draft(content="Hello world")
    assert draft_no_tags.display_content == "Hello world"


def test_create_and_get(dm):
    """Create and retrieve a draft."""
    draft = Draft(platform=Platform.TWITTER, content="Test tweet")
    dm.create(draft)

    retrieved = dm.get(draft.id)
    assert retrieved is not None
    assert retrieved.content == "Test tweet"
    assert retrieved.platform == Platform.TWITTER


def test_approve(dm):
    """Approve a pending draft."""
    draft = Draft(platform=Platform.TWITTER, content="Test")
    dm.create(draft)

    assert dm.approve(draft.id)
    retrieved = dm.get(draft.id)
    assert retrieved.status == DraftStatus.APPROVED


def test_reject(dm):
    """Reject a pending draft with notes."""
    draft = Draft(platform=Platform.LINKEDIN, content="Test")
    dm.create(draft)

    assert dm.reject(draft.id, "Not good enough")
    retrieved = dm.get(draft.id)
    assert retrieved.status == DraftStatus.REJECTED


def test_cannot_approve_non_pending(dm):
    """Cannot approve a draft that isn't pending."""
    draft = Draft(platform=Platform.TWITTER, content="Test")
    dm.create(draft)
    dm.approve(draft.id)

    # Try to approve again (now it's approved, not pending)
    assert not dm.approve(draft.id)


def test_list_by_status(dm):
    """List drafts by status."""
    dm.create(Draft(platform=Platform.TWITTER, content="T1"))
    dm.create(Draft(platform=Platform.TWITTER, content="T2"))
    d3 = Draft(platform=Platform.LINKEDIN, content="L1")
    dm.create(d3)
    dm.approve(d3.id)

    pending = dm.list_pending()
    assert len(pending) == 2

    approved = dm.list_approved()
    assert len(approved) == 1
    assert approved[0].platform == Platform.LINKEDIN


def test_update_content(dm):
    """Update draft content."""
    draft = Draft(platform=Platform.TWITTER, content="Original")
    dm.create(draft)

    dm.update_content(draft.id, "Updated content", ["#New"])
    retrieved = dm.get(draft.id)
    assert retrieved.content == "Updated content"
    assert retrieved.status == DraftStatus.PENDING
