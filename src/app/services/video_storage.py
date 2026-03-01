"""
Supabase Storage upload service for processed video files.

Uploads the final MP4 bytes to the 'videos' bucket and returns the stable public URL.

Pre-flight note: The 'videos' bucket MUST be set to PUBLIC in the Supabase dashboard
before any public URL returned by this service will be accessible to callers.

Naming convention: videos/YYYY-MM-DD.mp4 (locked — do not change without migrating existing URLs)
"""
import logging
from datetime import date

from app.services.database import get_supabase

logger = logging.getLogger(__name__)

VIDEO_BUCKET = "videos"


class VideoStorageService:
    """
    Wraps Supabase Storage for video uploads.

    Accepts an optional supabase client for testability (mirrors SimilarityService pattern).
    In production the client is obtained lazily via get_supabase().
    """

    def __init__(self, supabase=None) -> None:
        """
        Args:
            supabase: Optional pre-created Supabase Client (for unit tests).
                      If None, get_supabase() is called on first use.
        """
        self.supabase = supabase if supabase is not None else get_supabase()

    def upload(self, video_bytes: bytes, target_date: date | None = None) -> str:
        """
        Upload processed MP4 bytes to Supabase Storage and return the stable public URL.

        The file is stored at `videos/YYYY-MM-DD.mp4` inside the `videos` bucket.
        Upsert is enabled so same-day re-runs overwrite without error.

        Args:
            video_bytes:  The raw MP4 bytes to upload. Must be a finalized video
                          (audio-mixed, encoded) — NOT the HeyGen signed URL.
            target_date:  The content date (defaults to today). Used to derive the
                          stable file path.

        Returns:
            The stable public URL for the uploaded file (e.g.
            https://<project>.supabase.co/storage/v1/object/public/videos/2026-01-15.mp4).
            This URL — not any HeyGen signed URL — is what callers should persist.

        Raises:
            Exception: Propagates any Supabase Storage client errors to the caller.
        """
        if target_date is None:
            target_date = date.today()

        file_path = f"videos/{target_date.isoformat()}.mp4"

        self.supabase.storage.from_(VIDEO_BUCKET).upload(
            path=file_path,
            file=video_bytes,
            file_options={
                "content-type": "video/mp4",
                "upsert": "true",           # string, not bool — Supabase Python client requirement
                "cache-control": "31536000",  # 1 year — content is permanent once approved
            },
        )

        public_url: str = self.supabase.storage.from_(VIDEO_BUCKET).get_public_url(file_path)
        logger.info("Uploaded video to Supabase Storage: %s", public_url,
                    extra={"pipeline_step": "video_upload", "content_history_id": ""})
        return public_url
