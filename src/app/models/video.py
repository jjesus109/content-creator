from enum import Enum
from typing import Optional
from pydantic import BaseModel


class VideoStatus(str, Enum):
    """
    Lifecycle states for content_history.video_status.
    Stored as plain text in Postgres — the CHECK constraint in migration 0003 enforces valid values.
    Migration 0007 adds 'approval_timeout'. Migration 0008 adds 'kling_pending', 'kling_pending_retry', 'published'.
    """
    PENDING_RENDER = "pending_render"   # script saved, HeyGen job submitted, poller registered
    PENDING_RENDER_RETRY = "pending_render_retry"  # first timeout fired; resubmitted to HeyGen; new poller registered
    RENDERING = "rendering"             # HeyGen is processing (intermediate status from poll response)
    PROCESSING = "processing"           # render complete, ffmpeg + upload in progress
    READY = "ready"                     # video_url is stable and ready for Phase 4 delivery
    FAILED = "failed"                   # render or processing failed; creator alerted
    APPROVAL_TIMEOUT = "approval_timeout"  # 24h elapsed without creator response — new generation will proceed
    KLING_PENDING = "kling_pending"         # script saved, Kling job submitted via fal.ai, poller registered
    KLING_PENDING_RETRY = "kling_pending_retry"  # first 20-min timeout; resubmitted to Kling; new poller registered
    PUBLISHED = "published"                 # video published to at least one platform


class HeyGenWebhookEventData(BaseModel):
    video_id: str
    url: Optional[str] = None           # present on avatar_video.success
    msg: Optional[str] = None           # present on avatar_video.fail
    callback_id: Optional[str] = None


class HeyGenWebhookPayload(BaseModel):
    event_type: str                     # "avatar_video.success" | "avatar_video.fail"
    event_data: HeyGenWebhookEventData
