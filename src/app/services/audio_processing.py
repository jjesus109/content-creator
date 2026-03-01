import subprocess
import logging
import os
import tempfile
import random
import requests

from app.settings import get_settings

logger = logging.getLogger(__name__)


class AudioProcessingService:
    """
    Mixes ambient background music into a HeyGen-rendered video using ffmpeg.

    Pipeline:
      1. Download the HeyGen signed video URL to bytes.
      2. Pick a random ambient music track from the configured pool.
      3. Download the music track to a temp file (ffmpeg cannot read two stdin
         pipes simultaneously).
      4. Run ffmpeg with a filter_complex that applies a low-shelf EQ to the
         voice channel and mixes the music at the configured volume.
      5. Return processed MP4 bytes ready for Supabase Storage upload.

    Temp file cleanup is guaranteed via try/finally even if ffmpeg raises.

    ffmpeg EQ parameters (from audio research):
      f=180  — 180 Hz warmth zone for voice; adds body below 200 Hz without muddiness
      g=3    — +3 dB subtle warmth, not boomy
      t=1    — filter type 1 = lowshelf (not peaking)
      w=0.7  — Q of 0.7 = broad shelving curve appropriate for warmth

    movflags=frag_keyframe+empty_moov is REQUIRED when writing MP4 to pipe:1 —
    without it ffmpeg cannot seek backwards to write the moov atom and the output
    is corrupt.
    """

    def __init__(self) -> None:
        # Settings read internally so callers pass no credentials.
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def pick_music_track(self) -> str:
        """Return a random URL from the comma-separated ambient music pool.

        Raises:
            ValueError: if HEYGEN_AMBIENT_MUSIC_URLS is empty or unset.
        """
        raw = self._settings.heygen_ambient_music_urls.strip()
        if not raw:
            raise ValueError(
                "HEYGEN_AMBIENT_MUSIC_URLS is empty — configure at least one "
                "ambient music track URL in settings."
            )
        urls = [u.strip() for u in raw.split(",") if u.strip()]
        if not urls:
            raise ValueError(
                "HEYGEN_AMBIENT_MUSIC_URLS contains no valid URLs after parsing."
            )
        return random.choice(urls)

    def process_video_audio(
        self,
        video_url: str,
        music_volume: float = 0.25,
    ) -> bytes:
        """Download video + music, run ffmpeg EQ + mix, return processed MP4 bytes.

        Args:
            video_url:     Signed HeyGen video URL (expires; call promptly).
            music_volume:  Relative volume for ambient music track (0.0–1.0).
                           Default 0.25 = 25% — audible but subservient to voice.

        Returns:
            Raw MP4 bytes with processed audio, ready for Supabase Storage upload.

        Raises:
            requests.HTTPError: if video or music download fails.
            RuntimeError:       if ffmpeg exits with non-zero return code.
            subprocess.TimeoutExpired: if ffmpeg takes longer than 120 seconds.
        """
        # Step 1 — Download HeyGen video bytes (blocking; correct in APScheduler
        # thread pool because there is no running event loop to contend with).
        logger.info("Downloading HeyGen video from signed URL...",
                    extra={"pipeline_step": "audio_process", "content_history_id": ""})
        video_resp = requests.get(video_url, timeout=120)  # 2-min timeout for large files (200-500 MB)
        video_resp.raise_for_status()
        video_bytes = video_resp.content
        logger.info("HeyGen video downloaded: %d bytes", len(video_bytes))

        # Step 2 — Pick music track URL and download music bytes.
        music_url = self.pick_music_track()
        logger.info("Downloading ambient music track: %s", music_url)
        music_resp = requests.get(music_url, timeout=30)
        music_resp.raise_for_status()
        music_bytes = music_resp.content
        logger.info("Ambient music downloaded: %d bytes", len(music_bytes))

        # Step 3 — Write music to a temp file (ffmpeg cannot read two stdin
        # pipes simultaneously; one input must come from disk).
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(music_bytes)
            tmp_path = tmp.name

        # Step 4 — Run ffmpeg; always clean up the temp file.
        try:
            filter_complex = (
                # Voice low-shelf EQ: 180Hz, +3dB, Q=0.7 — adds warmth without muddiness
                "[0:a]equalizer=f=180:g=3:t=1:w=0.7[eq_voice];"
                # Reduce music to configured volume (default 25% — audible but subservient to voice)
                f"[1:a]volume={music_volume}[music];"
                # Mix: duration=first uses video audio length; dropout_transition=2 fades music gracefully
                "[eq_voice][music]amix=inputs=2:duration=first:dropout_transition=2[mixed]"
            )
            cmd = [
                "ffmpeg",
                "-i", "pipe:0",         # Input 0: video bytes from stdin
                "-i", tmp_path,          # Input 1: music from temp file
                "-filter_complex", filter_complex,
                "-map", "0:v",           # Copy video stream unchanged
                "-map", "[mixed]",       # Use processed audio stream
                "-c:v", "copy",          # No re-encode of video (preserves quality, fast)
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "frag_keyframe+empty_moov",  # REQUIRED: pipe:1 output needs fragmented MP4
                "-f", "mp4",
                "pipe:1",                # Output processed MP4 to stdout
            ]
            logger.info("Starting ffmpeg audio processing...",
                        extra={"pipeline_step": "audio_process", "content_history_id": ""})
            result = subprocess.run(
                cmd,
                input=video_bytes,
                capture_output=True,
                timeout=120,             # 2-min timeout for processing
            )
            if result.returncode != 0:
                stderr_text = result.stderr.decode(errors="replace")
                logger.error(
                    "ffmpeg failed (exit %d): %s",
                    result.returncode,
                    stderr_text,
                    extra={"pipeline_step": "audio_process", "content_history_id": ""},
                )
                raise RuntimeError(
                    f"ffmpeg exited with code {result.returncode}"
                )
            logger.info(
                "ffmpeg processing complete. Output size: %d bytes",
                len(result.stdout),
                extra={"pipeline_step": "audio_process", "content_history_id": ""},
            )
            return result.stdout
        finally:
            os.unlink(tmp_path)
