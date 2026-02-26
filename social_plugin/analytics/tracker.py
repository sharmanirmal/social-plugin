"""Analytics tracking — engagement metrics, post performance, daily summaries."""

from __future__ import annotations

from datetime import date, timedelta

from social_plugin.db import Database
from social_plugin.utils.logger import get_logger

logger = get_logger()


class AnalyticsTracker:
    """Track and query engagement analytics from SQLite."""

    def __init__(self, db: Database):
        self.db = db

    def get_post_performance(self, draft_id: str) -> dict | None:
        """Get performance metrics for a specific post."""
        row = self.db.get_analytics(draft_id)
        if row is None:
            return None
        return dict(row)

    def get_daily_summary(self, target_date: str | None = None) -> dict:
        """Get a summary of activity for a specific date."""
        target = target_date or date.today().isoformat()

        # Drafts created
        drafts_created = self.db.execute(
            "SELECT COUNT(*) as cnt FROM drafts WHERE date(created_at) = ?", (target,)
        )
        # Drafts posted
        drafts_posted = self.db.execute(
            "SELECT COUNT(*) as cnt FROM drafts WHERE date(posted_at) = ? AND status = 'posted'", (target,)
        )
        # Total engagement
        engagement = self.db.execute_one(
            """SELECT
                COALESCE(SUM(likes), 0) as total_likes,
                COALESCE(SUM(retweets), 0) as total_shares,
                COALESCE(SUM(comments), 0) as total_comments,
                COALESCE(SUM(impressions), 0) as total_impressions
            FROM post_analytics WHERE date(posted_at) = ?""",
            (target,),
        )
        # Trends fetched
        trends_count = self.db.execute(
            "SELECT COUNT(*) as cnt FROM trends WHERE date = ?", (target,)
        )

        return {
            "date": target,
            "drafts_created": drafts_created[0]["cnt"] if drafts_created else 0,
            "drafts_posted": drafts_posted[0]["cnt"] if drafts_posted else 0,
            "trends_fetched": trends_count[0]["cnt"] if trends_count else 0,
            "total_likes": engagement["total_likes"] if engagement else 0,
            "total_shares": engagement["total_shares"] if engagement else 0,
            "total_comments": engagement["total_comments"] if engagement else 0,
            "total_impressions": engagement["total_impressions"] if engagement else 0,
        }

    def get_overall_stats(self) -> dict:
        """Get overall cumulative statistics."""
        status_counts = self.db.get_draft_counts_by_status()

        total_engagement = self.db.execute_one(
            """SELECT
                COUNT(*) as total_posts,
                COALESCE(SUM(likes), 0) as total_likes,
                COALESCE(SUM(retweets), 0) as total_shares,
                COALESCE(SUM(comments), 0) as total_comments,
                COALESCE(SUM(impressions), 0) as total_impressions
            FROM post_analytics"""
        )

        # Generation costs
        cost_data = self.db.execute_one(
            """SELECT
                COALESCE(SUM(generation_tokens), 0) as total_tokens,
                COALESCE(SUM(generation_cost), 0) as total_cost
            FROM drafts"""
        )

        # Recent runs
        recent_runs = self.db.get_recent_runs(limit=5)

        return {
            "draft_counts": status_counts,
            "total_posts": total_engagement["total_posts"] if total_engagement else 0,
            "total_likes": total_engagement["total_likes"] if total_engagement else 0,
            "total_shares": total_engagement["total_shares"] if total_engagement else 0,
            "total_comments": total_engagement["total_comments"] if total_engagement else 0,
            "total_impressions": total_engagement["total_impressions"] if total_engagement else 0,
            "total_tokens": cost_data["total_tokens"] if cost_data else 0,
            "total_cost": cost_data["total_cost"] if cost_data else 0,
            "recent_runs": [dict(r) for r in recent_runs],
        }

    def get_content_history(self, days: int = 30) -> list[dict]:
        """Get content history for the past N days."""
        rows = self.db.execute(
            """SELECT d.*, pa.likes, pa.retweets, pa.comments, pa.impressions, pa.post_url as analytics_url
            FROM drafts d
            LEFT JOIN post_analytics pa ON d.id = pa.draft_id
            WHERE d.created_at > datetime('now', ?)
            ORDER BY d.created_at DESC""",
            (f"-{days} days",),
        )
        return [dict(r) for r in rows]

    def get_top_performing(self, limit: int = 5, metric: str = "likes") -> list[dict]:
        """Get top performing posts by a metric."""
        valid_metrics = {"likes", "retweets", "comments", "impressions"}
        if metric not in valid_metrics:
            metric = "likes"

        rows = self.db.execute(
            f"""SELECT d.id, d.platform, d.content, d.posted_at,
                pa.likes, pa.retweets, pa.comments, pa.impressions, pa.post_url
            FROM drafts d
            JOIN post_analytics pa ON d.id = pa.draft_id
            WHERE d.status = 'posted'
            ORDER BY pa.{metric} DESC
            LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in rows]
