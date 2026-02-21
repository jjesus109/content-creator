from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All configuration read from environment variables.
    Never read os.environ directly — always use get_settings().
    Railway injects these as encrypted env vars (SCRTY-01).
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Supabase (INFRA-02)
    supabase_url: str
    supabase_key: str  # service_role key — never anon key
    database_url: str  # postgresql+psycopg2:// via session pooler port 5432 (INFRA-03)

    # Telegram (SCRTY-02)
    telegram_bot_token: str
    telegram_creator_id: int  # only user ID the bot responds to

    # Circuit breaker limits — configurable via Railway env vars (INFRA-04)
    daily_cost_limit: float = 2.0    # USD per day; hard halt above this
    max_daily_attempts: int = 10     # API call count per day; hard halt above this

    # Pipeline schedule (INFRA-03)
    pipeline_hour: int = 7           # 7 AM America/Mexico_City

    # AI generation (SCRP-01, SCRP-02, SCRP-03)
    anthropic_api_key: str
    openai_api_key: str
    claude_generation_model: str = "claude-sonnet-4-5-20250929"  # configurable — upgrade to sonnet without redeploy

    # HeyGen video production (VIDP-01, VIDP-02)
    heygen_api_key: str                         # API key — HeyGen dashboard → Settings → API
    heygen_avatar_id: str                       # Portrait-trained avatar ID (pre-flight: verify in HeyGen dashboard)
    heygen_voice_id: str                        # Fixed voice ID — consistent brand voice, no rotation
    heygen_webhook_url: str                     # Public URL of /webhooks/heygen route on Railway (e.g. https://yourapp.railway.app/webhooks/heygen)
    heygen_webhook_secret: str                  # HMAC-SHA256 signing secret from HeyGen webhook config
    heygen_dark_backgrounds: str                # Comma-separated Supabase Storage public URLs for dark cinematic images (min 2)
                                                # Note: HeyGen API v2 has NO built-in scene_id system — custom image URLs required
    heygen_ambient_music_urls: str              # Comma-separated Supabase Storage public URLs for ambient music tracks (2-4 tracks)


@lru_cache
def get_settings() -> Settings:
    return Settings()
