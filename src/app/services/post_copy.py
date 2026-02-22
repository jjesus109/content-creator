"""
Social media copy generation and thumbnail extraction utilities.

PostCopyService runs in APScheduler thread context — uses the synchronous
Anthropic client only. Do NOT switch to AsyncAnthropic; there is no event loop
in APScheduler's ThreadPoolExecutor.

extract_thumbnail() must also be called from a thread pool context — it performs
blocking I/O (HTTP download + ffmpeg subprocess). Do NOT call it from async
handlers directly; use asyncio.get_event_loop().run_in_executor() or equivalent.
"""
import logging
import subprocess
from io import BytesIO

import requests
from anthropic import Anthropic

from app.settings import get_settings

logger = logging.getLogger(__name__)


class PostCopyService:
    """
    Generates Spanish social media post copy for a daily philosophical video.

    The generated copy accompanies the approved video at publish time:
      - Hook: 1 impactful opening line
      - Body: 2-3 reflective lines
      - Hashtags: 5-8 thematic hashtags

    Uses the synchronous Anthropic client (same model as ScriptGenerationService).
    Runs in APScheduler ThreadPoolExecutor — no event loop.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_generation_model  # default: claude-haiku-3-5-20241022

    def generate(self, script_text: str, topic_summary: str) -> str:
        """
        Generate Spanish social media post copy for a video.

        Produces a Hook + body + hashtags string in neutral Spanish.
        The copy reflects the philosophical tone of the script without
        asking viewers to follow or subscribe.

        Args:
            script_text:    The full script used in the video. Provides the
                            philosophical depth and specific language for copy.
            topic_summary:  Short 10-20 word phrase summarising the script topic.
                            Used to focus hashtag and hook generation.

        Returns:
            A ready-to-publish post copy string (max ~200 words) containing:
              - Hook (1 impactful line)
              - Body (2-3 reflective lines)
              - Hashtags (5-8 thematic tags)

        Raises:
            anthropic.APIError: On Claude API failures.
        """
        system = (
            "Eres un redactor de redes sociales especializado en contenido filosófico en español neutro. "
            "Tu tarea es crear el copy de publicación para un video filosófico.\n\n"
            "ESTRUCTURA OBLIGATORIA:\n"
            "1. HOOK (1 línea impactante): Una frase que detiene el scroll — pregunta, paradoja o verdad incómoda.\n"
            "2. CUERPO (2-3 líneas): Desarrolla la idea con tono reflexivo. Sin exageraciones, sin clickbait.\n"
            "3. HASHTAGS (5-8 etiquetas): Temáticos y de nicho — filosofía, reflexión, crecimiento personal.\n\n"
            "REGLAS:\n"
            "- Español neutro, tono reflexivo, sin urgencia artificial\n"
            "- NO incluyas llamadas a seguir, comentar ni compartir\n"
            "- Máximo 200 palabras en total\n"
            "- Devuelve ÚNICAMENTE el copy, sin etiquetas de sección ni explicaciones"
        )

        user = (
            f"Tema del video: {topic_summary}\n\n"
            f"Guion completo:\n{script_text}\n\n"
            "Genera el copy de publicación."
        )

        message = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.7,
        )
        text = message.content[0].text.strip()
        logger.debug(
            "PostCopyService.generate: %d in / %d out tokens",
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        return text


def extract_thumbnail(video_url: str) -> BytesIO:
    """
    Extract a thumbnail JPEG from a video URL at the 1-second mark.

    Downloads the video bytes synchronously, pipes them into ffmpeg, and returns
    the resulting JPEG image wrapped in a BytesIO object.

    The returned BytesIO has a `.name` attribute set to "thumbnail.jpg" because
    python-telegram-bot requires a file-like object with a name when sending photos.

    DO NOT call from async handlers — blocking I/O (HTTP download + ffmpeg subprocess),
    must run in thread pool context (APScheduler thread or run_in_executor).

    Args:
        video_url: Public URL of the video to extract the thumbnail from.
                   Must be accessible without authentication (e.g. Supabase public URL).

    Returns:
        BytesIO object containing JPEG image bytes, seeked to position 0,
        with `.name = "thumbnail.jpg"` set for PTB compatibility.

    Raises:
        requests.HTTPError:         If the video download fails (non-2xx status).
        RuntimeError:               If ffmpeg exits with a non-zero return code.
        subprocess.TimeoutExpired:  If ffmpeg takes longer than 30 seconds.
    """
    logger.info("Downloading video for thumbnail extraction: %s", video_url)
    resp = requests.get(video_url, timeout=60)
    resp.raise_for_status()
    video_bytes = resp.content
    logger.info("Video downloaded for thumbnail: %d bytes", len(video_bytes))

    # Extract one JPEG frame at t=1s.
    # -ss before -i: fast seek to 1 second before reading input.
    # scale=320:-1: resize to 320px wide, preserve aspect ratio.
    # pipe:0 / pipe:1: read from stdin, write to stdout — no temp files.
    cmd = [
        "ffmpeg",
        "-ss", "00:00:01",
        "-i", "pipe:0",
        "-frames:v", "1",
        "-f", "image2",
        "-c:v", "mjpeg",
        "-vf", "scale=320:-1",
        "pipe:1",
    ]

    result = subprocess.run(
        cmd,
        input=video_bytes,
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0:
        stderr_text = result.stderr.decode(errors="replace")
        logger.error(
            "ffmpeg thumbnail extraction failed (exit %d): %s",
            result.returncode,
            stderr_text,
        )
        raise RuntimeError(
            f"ffmpeg exited with code {result.returncode}: {stderr_text}"
        )

    buf = BytesIO(result.stdout)
    buf.name = "thumbnail.jpg"  # Required by python-telegram-bot when sending photos
    buf.seek(0)
    logger.info("Thumbnail extracted: %d bytes", len(result.stdout))
    return buf
