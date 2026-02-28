import logging
from datetime import datetime, timezone

import requests
import tenacity
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from app.services.database import get_supabase
from app.services.publishing import PublishingService
from app.settings import get_settings

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Platform API callers for YouTube, Instagram, TikTok, and Facebook.
    Each platform fetcher returns a dict of metrics (fail-soft — never raises).
    fetch_and_store() is the main entry point called by harvest_metrics_job.
    Synchronous — runs in APScheduler ThreadPoolExecutor (no event loop).
    """

    def __init__(self, supabase=None) -> None:
        """Accept optional supabase client for testability (same pattern as SimilarityService)."""
        self._supabase = supabase or get_supabase()
        self._settings = get_settings()

    def fetch_and_store(
        self,
        content_history_id: str,
        platform: str,
        external_post_id: str,
    ) -> dict | None:
        """
        Main entry point called by harvest_metrics_job.
        Routes to the correct platform fetcher and persists the row in platform_metrics.

        Returns:
            dict of metrics on success, None on failure (fail-soft — never raises).
        """
        platform_map = {
            "youtube":   self._fetch_youtube,
            "instagram": self._fetch_instagram,
            "tiktok":    self._fetch_tiktok,
            "facebook":  self._fetch_facebook,
        }
        fetcher = platform_map.get(platform)
        if not fetcher:
            logger.warning("Unknown platform: %s", platform)
            return None

        try:
            metrics = fetcher(external_post_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch metrics for platform=%s post_id=%s: %s",
                platform, external_post_id, exc,
            )
            return None

        row = {
            "content_history_id": content_history_id,
            "platform":           platform,
            "external_post_id":   external_post_id,
            "harvested_at":       datetime.now(timezone.utc).isoformat(),
            **metrics,
        }

        try:
            self._supabase.table("platform_metrics").insert(row).execute()
        except Exception as exc:
            logger.error(
                "Failed to insert platform_metrics row for platform=%s: %s",
                platform, exc,
            )
            return None

        return metrics

    @tenacity.retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _fetch_youtube(self, video_id: str) -> dict:
        """
        Fetch YouTube metrics via Data API v3 + YouTube Analytics API.
        Returns dict with: views, likes, comments, retention_rate.
        retention_rate comes from averageViewPercentage (Analytics API — optional, partial harvest on failure).
        """
        access_token = PublishingService()._refresh_youtube_token()

        # --- Data API v3: statistics ---
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part":         "statistics,contentDetails",
                "id":           video_id,
                "access_token": access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        items = response.json().get("items", [])

        if not items:
            logger.warning("YouTube: no items for video_id=%s", video_id)
            return {"views": 0, "likes": 0, "comments": 0, "retention_rate": None}

        stats = items[0].get("statistics", {})
        views    = int(stats.get("viewCount",    0))
        likes    = int(stats.get("likeCount",    0))
        comments = int(stats.get("commentCount", 0))
        # NOTE: dislikeCount is always 0 since December 2021 — not read

        # --- YouTube Analytics API: averageViewPercentage (optional) ---
        retention_rate = None
        try:
            analytics_response = requests.get(
                "https://youtubeanalytics.googleapis.com/v2/reports",
                params={
                    "ids":          "channel==MINE",
                    "metrics":      "averageViewPercentage",
                    "dimensions":   "video",
                    "filters":      f"video=={video_id}",
                    "access_token": access_token,
                },
                timeout=15,
            )
            analytics_response.raise_for_status()
            rows = analytics_response.json().get("rows", [])
            if rows:
                retention_rate = float(rows[0][1])
        except Exception as exc:
            logger.warning(
                "YouTube Analytics partial harvest for video_id=%s: %s", video_id, exc
            )

        return {
            "views":          views,
            "likes":          likes,
            "comments":       comments,
            "retention_rate": retention_rate,
        }

    @tenacity.retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _fetch_instagram(self, media_id: str) -> dict:
        """
        Fetch Instagram metrics via Meta Graph API v18 (Insights endpoint).
        Uses 'views' metric — NOT 'video_views' (deprecated in Graph API v21, Jan 2025).
        retention_rate is not exposed by Instagram — set to None, log partial harvest warning.
        Returns dict with: views, reach, saves, shares, retention_rate.
        """
        s = self._settings
        response = requests.get(
            f"https://graph.instagram.com/v18.0/{media_id}/insights",
            params={
                "metric":       "views,reach,saved,shares",
                "access_token": s.instagram_access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            logger.warning(
                "Instagram: empty insights data for media_id=%s "
                "(account may be under 1,000 followers or API unavailable)",
                media_id,
            )
            return {
                "views":          None,
                "reach":          None,
                "saves":          None,
                "shares":         None,
                "retention_rate": None,
            }

        parsed = {item["name"]: item["values"][0]["value"] for item in data}

        logger.warning(
            "Instagram: retention_rate not available via Graph API for media_id=%s — partial harvest",
            media_id,
        )
        return {
            "views":          parsed.get("views"),
            "reach":          parsed.get("reach"),
            "saves":          parsed.get("saved"),
            "shares":         parsed.get("shares"),
            "retention_rate": None,
        }

    @tenacity.retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _fetch_tiktok(self, video_id: str) -> dict:
        """
        Fetch TikTok metrics via Display API v2.
        Skips gracefully with WARNING if tiktok_access_token is not configured.
        retention_rate: TikTok does not return video_duration in query endpoint — set to None.
        Returns dict with: views, likes, shares, retention_rate.
        """
        s = self._settings
        if not s.tiktok_access_token:
            logger.warning("TikTok access token not configured — skipping harvest")
            return {"views": None, "likes": None, "shares": None, "retention_rate": None}

        response = requests.post(
            "https://open.tiktokapis.com/v2/video/query/",
            headers={"Authorization": f"Bearer {s.tiktok_access_token}"},
            json={
                "filters": {"video_ids": [video_id]},
                "fields":  [
                    "view_count",
                    "like_count",
                    "share_count",
                    "average_time_watched",
                    "total_time_watched",
                ],
            },
            timeout=15,
        )
        response.raise_for_status()
        data_list = response.json().get("data", {}).get("videos", [])
        if not data_list:
            logger.warning("TikTok: no video data returned for video_id=%s", video_id)
            return {"views": None, "likes": None, "shares": None, "retention_rate": None}

        video_data = data_list[0]
        # retention_rate: video_duration not returned here — partial harvest
        logger.warning(
            "TikTok: retention_rate not computable (video_duration absent in query response) "
            "for video_id=%s — partial harvest",
            video_id,
        )
        return {
            "views":          video_data.get("view_count"),
            "likes":          video_data.get("like_count"),
            "shares":         video_data.get("share_count"),
            "retention_rate": None,
        }

    @tenacity.retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _fetch_facebook(self, media_id: str) -> dict:
        """
        Fetch Facebook metrics via Meta Graph API v18 (Insights + shares endpoints).
        Skips gracefully if facebook_access_token is not configured.
        retention_rate computed from post_video_avg_time_watched / post_video_length * 100 when available.
        Returns dict with: views, shares, retention_rate.
        """
        s = self._settings
        if not s.facebook_access_token:
            logger.warning("Facebook access token not configured — skipping harvest")
            return {"views": None, "shares": None, "retention_rate": None}

        # --- Insights: views and retention components ---
        insights_response = requests.get(
            f"https://graph.facebook.com/v18.0/{media_id}/insights",
            params={
                "metric":       "post_impressions,post_video_views,post_video_avg_time_watched,post_video_length",
                "access_token": s.facebook_access_token,
            },
            timeout=15,
        )
        insights_response.raise_for_status()
        insights_data = insights_response.json().get("data", [])
        insights = {item["name"]: item["values"][0]["value"] for item in insights_data if "values" in item and item["values"]}

        views = insights.get("post_video_views")

        # Compute retention_rate if both time metrics are available and non-zero
        avg_time  = insights.get("post_video_avg_time_watched")
        video_len = insights.get("post_video_length")
        if avg_time and video_len and float(video_len) > 0:
            retention_rate = float(avg_time) / float(video_len) * 100
        else:
            retention_rate = None
            logger.warning(
                "Facebook: retention_rate not computable for media_id=%s — partial harvest",
                media_id,
            )

        # --- Shares: separate endpoint ---
        shares = None
        try:
            shares_response = requests.get(
                f"https://graph.facebook.com/v18.0/{media_id}",
                params={
                    "fields":       "shares",
                    "access_token": s.facebook_access_token,
                },
                timeout=15,
            )
            shares_response.raise_for_status()
            shares_data = shares_response.json().get("shares", {})
            shares = shares_data.get("count")
        except Exception as exc:
            logger.warning(
                "Facebook: shares fetch failed for media_id=%s — partial harvest: %s",
                media_id, exc,
            )

        return {
            "views":          views,
            "shares":         shares,
            "retention_rate": retention_rate,
        }
