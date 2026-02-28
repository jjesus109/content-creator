import logging
from datetime import datetime, timedelta, timezone

from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.settings import get_settings

logger = logging.getLogger(__name__)

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[int]) -> str:
    """Convert a list of up to 4 integers to an 8-level Unicode sparkline string."""
    if not values or max(values) == 0:
        return "▁" * len(values)
    mn, mx = min(values), max(values)
    if mn == mx:
        return "▄" * len(values)
    return "".join(
        SPARK_CHARS[int((v - mn) / (mx - mn) * 7)]
        for v in values
    )


def format_virality_alert(platform: str, video_date: str, current_views: int) -> str:
    """
    Minimal virality alert format — video date and view count only.
    No baseline average, no percentage above threshold.
    """
    return (
        f"ALERTA DE VIRALIDAD\n\n"
        f"Plataforma: {platform.upper()}\n"
        f"Video del: {video_date}\n"
        f"Vistas actuales: {current_views:,}"
    )


def format_weekly_report(top_videos: list[dict], top_performer_summary: str = "") -> str:
    """
    Format the weekly report message for Telegram.
    Shows per-platform breakdown (YT/IG/TK/FB).
    Renders None pct_change as 'N/A'.
    top_performer ranked by retention_rate (highest in the week).
    """
    from datetime import date
    lines = [f"REPORTE SEMANAL — {date.today().strftime('%d %b %Y')}\n"]
    if not top_videos:
        lines.append("Sin datos de metricas esta semana.")
        return "\n".join(lines)
    for i, v in enumerate(top_videos[:5], 1):
        spark = sparkline(v.get("last_4_weeks_views", []))
        pct = v.get("pct_change")
        if pct is None:
            pct_str = "N/A"
        elif pct >= 0:
            pct_str = f"+{pct:.0f}%"
        else:
            pct_str = f"{pct:.0f}%"
        # Per-platform breakdown
        breakdown = v.get("platform_breakdown", {})
        yt = breakdown.get("youtube")
        ig = breakdown.get("instagram")
        tk = breakdown.get("tiktok")
        fb = breakdown.get("facebook")

        def fmt(n):
            return f"{n:,}" if n is not None else "—"

        platform_line = f"YT: {fmt(yt)} | IG: {fmt(ig)} | TK: {fmt(tk)} | FB: {fmt(fb)}"
        lines.append(
            f"{i}. {v['topic_summary'][:40]}\n"
            f"   {spark} {v['total_views']:,} views ({pct_str})\n"
            f"   {platform_line}"
        )
    if top_performer_summary:
        lines.append(f"\nMejor retencion: {top_performer_summary[:60]}")
    return "\n".join(lines)


class AnalyticsService:
    """
    Analytics computation layer: rolling average, virality detection, sparkline, weekly report.
    Reads from platform_metrics table via Supabase.
    Synchronous — runs in APScheduler ThreadPoolExecutor (no event loop).
    """

    def __init__(self, supabase=None) -> None:
        """Accept optional supabase client for testability (same pattern as SimilarityService)."""
        self._supabase = supabase or get_supabase()
        self._settings = get_settings()

    def compute_rolling_average(
        self, content_history_id: str, platform: str
    ) -> float:
        """
        Return the average view count over the past 28 days for a given
        content_history_id + platform combination.
        Returns 0.0 when there are no rows or no non-null view values.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=28)).isoformat()
        result = (
            self._supabase.table("platform_metrics")
            .select("views")
            .eq("content_history_id", content_history_id)
            .eq("platform", platform)
            .gte("harvested_at", cutoff)
            .execute()
        )
        rows = result.data or []
        views_list = [r["views"] for r in rows if r.get("views") is not None]
        return sum(views_list) / len(views_list) if views_list else 0.0

    def check_and_alert_virality(
        self,
        content_history_id: str,
        platform: str,
        current_views: int,
        topic_summary: str,
        video_date: str,
    ) -> bool:
        """
        Check if a video is going viral and fire a Telegram alert every 48h harvest cycle
        while it remains above the virality threshold.

        De-duplication uses a 48h time window, NOT IS NULL — this means the alert fires
        again on the next harvest cycle if views remain above threshold.

        Steps:
        1. Check 48h de-duplication window.
        2. Require baseline: at least 2 videos with metrics on this platform.
        3. Compute rolling average; require 5x threshold.
        4. Fire alert, update virality_alerted_at, mark video as Eternal.
        Returns True if alert fired, False otherwise.
        """
        # Step 1: 48h de-duplication check
        cutoff_48h = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        latest_result = (
            self._supabase.table("platform_metrics")
            .select("virality_alerted_at, harvested_at")
            .eq("content_history_id", content_history_id)
            .eq("platform", platform)
            .order("harvested_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_rows = latest_result.data or []
        if latest_rows:
            alerted_at = latest_rows[0].get("virality_alerted_at")
            if alerted_at and alerted_at > cutoff_48h:
                # Already alerted within this harvest cycle — skip
                return False

        # Step 2: Require at least 2 published videos with metrics on this platform
        baseline_result = (
            self._supabase.table("platform_metrics")
            .select("content_history_id", count="exact")
            .eq("platform", platform)
            .execute()
        )
        # Count distinct content_history_ids
        all_rows = baseline_result.data or []
        distinct_ids = {r["content_history_id"] for r in all_rows}
        if len(distinct_ids) < 2:
            return False

        # Step 3: Rolling average + virality threshold (5x)
        rolling_avg = self.compute_rolling_average(content_history_id, platform)
        if rolling_avg == 0 or current_views < rolling_avg * 5.0:
            return False

        # Step 4a: Fire alert
        alert_text = format_virality_alert(platform, video_date, current_views)
        send_alert_sync(alert_text)

        # Step 4b: Update virality_alerted_at on the latest platform_metrics row
        now_iso = datetime.now(timezone.utc).isoformat()
        if latest_rows:
            latest_harvested_at = latest_rows[0].get("harvested_at")
            if latest_harvested_at:
                (
                    self._supabase.table("platform_metrics")
                    .update({"virality_alerted_at": now_iso})
                    .eq("content_history_id", content_history_id)
                    .eq("platform", platform)
                    .eq("harvested_at", latest_harvested_at)
                    .execute()
                )

        # Step 4c: Mark video as Eternal in content_history
        (
            self._supabase.table("content_history")
            .update({"is_eternal": True, "storage_status": "exempt"})
            .eq("id", content_history_id)
            .execute()
        )

        logger.info(
            "Virality alert fired for content_history_id=%s platform=%s views=%d",
            content_history_id, platform, current_views,
        )
        return True

    def build_weekly_report(self) -> str:
        """
        Build the weekly performance report for the Sunday scheduled message.
        Queries platform_metrics for the last 7 days and previous 7 days.
        Ranks top 5 videos by total views; top performer by retention_rate.
        Returns formatted report string.
        """
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=7)).isoformat()
        prev_week_start = (now - timedelta(days=14)).isoformat()

        # Fetch all metrics for the current week
        current_result = (
            self._supabase.table("platform_metrics")
            .select(
                "content_history_id, platform, views, retention_rate, harvested_at"
            )
            .gte("harvested_at", week_start)
            .execute()
        )
        current_rows = current_result.data or []

        if not current_rows:
            return format_weekly_report([], "")

        # Fetch all metrics for the previous week
        prev_result = (
            self._supabase.table("platform_metrics")
            .select("content_history_id, views")
            .gte("harvested_at", prev_week_start)
            .lt("harvested_at", week_start)
            .execute()
        )
        prev_rows = prev_result.data or []

        # Build lookup: content_history_id -> sum of previous week views
        prev_views_by_id: dict[str, int] = {}
        for r in prev_rows:
            cid = r["content_history_id"]
            prev_views_by_id[cid] = prev_views_by_id.get(cid, 0) + (r.get("views") or 0)

        # Aggregate current week by content_history_id
        totals: dict[str, dict] = {}
        for r in current_rows:
            cid = r["content_history_id"]
            platform = r["platform"]
            views = r.get("views") or 0
            retention = r.get("retention_rate")
            if cid not in totals:
                totals[cid] = {
                    "content_history_id": cid,
                    "total_views":        0,
                    "platform_breakdown": {"youtube": None, "instagram": None, "tiktok": None, "facebook": None},
                    "max_retention":      None,
                }
            totals[cid]["total_views"] += views
            # Update platform breakdown (keep highest views if multiple rows per platform)
            existing = totals[cid]["platform_breakdown"].get(platform)
            totals[cid]["platform_breakdown"][platform] = (
                max(existing, views) if existing is not None else views
            )
            # Track max retention_rate for top-performer ranking
            if retention is not None:
                if totals[cid]["max_retention"] is None or retention > totals[cid]["max_retention"]:
                    totals[cid]["max_retention"] = retention

        # Fetch topic_summary for each content_history_id
        all_ids = list(totals.keys())
        ch_result = (
            self._supabase.table("content_history")
            .select("id, topic_summary, created_at")
            .in_("id", all_ids)
            .execute()
        )
        ch_map = {r["id"]: r for r in (ch_result.data or [])}

        # Sort by total_views descending — take top 5
        sorted_videos = sorted(
            totals.values(), key=lambda x: x["total_views"], reverse=True
        )[:5]

        # Build report items
        top_videos = []
        for v in sorted_videos:
            cid = v["content_history_id"]
            ch = ch_map.get(cid, {})
            topic_summary = ch.get("topic_summary", cid[:20])

            prev_week_views = prev_views_by_id.get(cid, 0)
            pct_change: float | None = None
            if prev_week_views > 0:
                pct_change = (v["total_views"] - prev_week_views) / prev_week_views * 100

            # Compute last-4-weeks sparkline (4 weekly buckets incl. current)
            last_4_weeks_views = self._get_4_week_totals(cid, now)

            top_videos.append({
                "content_history_id": cid,
                "topic_summary":      topic_summary,
                "total_views":        v["total_views"],
                "pct_change":         pct_change,
                "platform_breakdown": v["platform_breakdown"],
                "last_4_weeks_views": last_4_weeks_views,
            })

        # Find top performer by retention_rate
        top_performer_summary = ""
        top_performer = max(
            (v for v in totals.values() if v.get("max_retention") is not None),
            key=lambda x: x["max_retention"],
            default=None,
        )
        if top_performer:
            cid = top_performer["content_history_id"]
            ch = ch_map.get(cid, {})
            top_performer_summary = ch.get("topic_summary", cid[:20])

        return format_weekly_report(top_videos, top_performer_summary)

    def _get_4_week_totals(self, content_history_id: str, now: datetime) -> list[int]:
        """
        Return a list of 4 weekly view totals for the past 4 weeks (oldest to newest).
        Used for sparkline generation in the weekly report.
        """
        weekly_totals = []
        for week_offset in range(3, -1, -1):  # weeks 4,3,2,1 (oldest first)
            week_end = (now - timedelta(days=7 * week_offset)).isoformat()
            week_start = (now - timedelta(days=7 * (week_offset + 1))).isoformat()
            result = (
                self._supabase.table("platform_metrics")
                .select("views")
                .eq("content_history_id", content_history_id)
                .gte("harvested_at", week_start)
                .lt("harvested_at", week_end)
                .execute()
            )
            rows = result.data or []
            total = sum(r.get("views") or 0 for r in rows)
            weekly_totals.append(total)
        return weekly_totals
