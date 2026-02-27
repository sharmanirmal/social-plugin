"""Tests for database module."""

import tempfile
from pathlib import Path

import pytest

from social_plugin.db import Database


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


def test_schema_creation(db):
    """Database creates all tables on init."""
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = {row["name"] for row in tables}
    expected = {"trends", "source_documents", "drafts", "post_analytics", "run_log", "config_snapshots", "schema_version"}
    assert expected.issubset(table_names)


def test_insert_and_get_trend(db):
    """Insert and retrieve a trend."""
    trend = {
        "source": "twitter_rss",
        "title": "Test Trend",
        "summary": "Summary",
        "url": "https://example.com",
        "relevance_score": 0.8,
        "date": "2025-01-01",
    }
    db.insert_trend(trend)
    trends = db.get_trends("2025-01-01")
    assert len(trends) == 1
    assert trends[0]["title"] == "Test Trend"


def test_insert_and_get_draft(db):
    """Insert and retrieve a draft."""
    draft = {
        "id": "test1234",
        "platform": "twitter",
        "content": "Test tweet content",
        "status": "pending",
    }
    db.insert_draft(draft)
    row = db.get_draft("test1234")
    assert row is not None
    assert row["content"] == "Test tweet content"


def test_update_draft_status(db):
    """Update draft status."""
    db.insert_draft({
        "id": "abc12345",
        "platform": "twitter",
        "content": "Test",
        "status": "pending",
    })
    db.update_draft_status("abc12345", "approved")
    row = db.get_draft("abc12345")
    assert row["status"] == "approved"


def test_expire_old_drafts(db):
    """Expire old pending drafts."""
    # Insert a draft with old timestamp
    db.execute(
        "INSERT INTO drafts (id, platform, content, status, created_at) VALUES (?, ?, ?, ?, datetime('now', '-30 days'))",
        ("old12345", "twitter", "Old tweet", "pending"),
    )
    count = db.expire_old_drafts(7)
    assert count == 1
    row = db.get_draft("old12345")
    assert row["status"] == "expired"


def test_run_log(db):
    """Start and complete a run log entry."""
    run_id = db.start_run("test_run")
    assert run_id > 0
    db.complete_run(run_id, "success", {"test": "data"})
    runs = db.get_recent_runs(1)
    assert len(runs) == 1
    assert runs[0]["status"] == "success"


def test_draft_counts_by_status(db):
    """Get draft counts grouped by status."""
    db.insert_draft({"id": "d1", "platform": "twitter", "content": "T1", "status": "pending"})
    db.insert_draft({"id": "d2", "platform": "twitter", "content": "T2", "status": "pending"})
    db.insert_draft({"id": "d3", "platform": "twitter", "content": "T3", "status": "approved"})
    counts = db.get_draft_counts_by_status()
    assert counts["pending"] == 2
    assert counts["approved"] == 1


# =============================================================================
# Rejection / Approval feedback notes
# =============================================================================


def test_get_recent_rejection_notes(db):
    """Get rejection notes from recently rejected drafts."""
    db.insert_draft({"id": "rej1", "platform": "twitter", "content": "T1", "status": "pending"})
    db.update_draft_status(
        "rej1", "rejected",
        reviewed_at="2025-12-01T00:00:00",
        reviewer_notes="too generic",
    )
    notes = db.get_recent_rejection_notes(days=3650)
    assert "too generic" in notes


def test_get_recent_rejection_notes_excludes_null(db):
    """Rejection notes excludes drafts with null/empty notes."""
    db.insert_draft({"id": "rej2", "platform": "twitter", "content": "T2", "status": "pending"})
    db.update_draft_status("rej2", "rejected", reviewed_at="2025-12-01T00:00:00")
    db.insert_draft({"id": "rej3", "platform": "twitter", "content": "T3", "status": "pending"})
    db.update_draft_status(
        "rej3", "rejected",
        reviewed_at="2025-12-01T00:00:00",
        reviewer_notes="",
    )
    notes = db.get_recent_rejection_notes(days=3650)
    assert len(notes) == 0


def test_get_recent_rejection_notes_platform_filter(db):
    """Rejection notes can be filtered by platform."""
    db.insert_draft({"id": "rejT", "platform": "twitter", "content": "T", "status": "pending"})
    db.update_draft_status(
        "rejT", "rejected",
        reviewed_at="2025-12-01T00:00:00",
        reviewer_notes="twitter issue",
    )
    db.insert_draft({"id": "rejL", "platform": "linkedin", "content": "L", "status": "pending"})
    db.update_draft_status(
        "rejL", "rejected",
        reviewed_at="2025-12-01T00:00:00",
        reviewer_notes="linkedin issue",
    )
    twitter_notes = db.get_recent_rejection_notes(days=3650, platform="twitter")
    assert "twitter issue" in twitter_notes
    assert "linkedin issue" not in twitter_notes


def test_get_recent_approval_notes(db):
    """Get approval notes from recently approved drafts."""
    db.insert_draft({"id": "app1", "platform": "twitter", "content": "T1", "status": "pending"})
    db.update_draft_status(
        "app1", "approved",
        reviewed_at="2025-12-01T00:00:00",
        reviewer_notes="loved the data points",
    )
    notes = db.get_recent_approval_notes(days=3650)
    assert "loved the data points" in notes


def test_get_recent_approval_notes_excludes_non_approved(db):
    """Approval notes only includes approved/posted drafts."""
    db.insert_draft({"id": "pend1", "platform": "twitter", "content": "T1", "status": "pending"})
    db.update_draft_status(
        "pend1", "pending",
        reviewed_at="2025-12-01T00:00:00",
        reviewer_notes="some note",
    )
    notes = db.get_recent_approval_notes(days=3650)
    assert len(notes) == 0
