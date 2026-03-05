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
    heygen_webhook_secret: str = ""             # HMAC-SHA256 signing secret from HeyGen webhook config (empty = skip validation, e.g. free plan)
    heygen_dark_backgrounds: str                # Comma-separated Supabase Storage public URLs for dark cinematic images (min 2)
                                                # Note: HeyGen API v2 has NO built-in scene_id system — custom image URLs required
    heygen_ambient_music_urls: str              # Comma-separated Supabase Storage public URLs for ambient music tracks (2-4 tracks)
    heygen_gesture_prompt: str  # Avatar gesture instruction sent as character.prompt in v2 API

    # Publishing — Direct platform APIs (PUBL-01, PUBL-02)

    # Instagram (Meta Graph API v18 — long-lived user access token, 60-day expiry)
    instagram_access_token: str                 # Meta long-lived token — refresh every 60 days
    instagram_business_account_id: str          # Instagram Business Account numeric ID

    # Facebook (Meta Graph API — permanent long-lived Page access token)
    facebook_access_token: str                  # Meta Page access token (long-lived, permanent)
    facebook_page_id: str                       # Facebook Page ID

    # YouTube (Data API v3 — OAuth2 refresh token, never expires with offline access)
    youtube_client_id: str                      # OAuth2 client ID from Google Cloud Console
    youtube_client_secret: str                  # OAuth2 client secret
    youtube_refresh_token: str                  # OAuth2 refresh token (offline access, permanent)

    # TikTok: manual posting — no API credentials needed
    # (copy shown in approval message; video URL sent in confirmation message)

    # TikTok Display API OAuth 2.0 tokens (ANLX-01)
    # Creator must authorize once via /auth/tiktok FastAPI route
    # access_token and refresh_token stored here after first authorization
    tiktok_access_token: str = ""       # Display API user access token (expires in 24h, refresh via refresh_token)
    tiktok_refresh_token: str = ""      # Refresh token (valid for 365 days)

    # Audience timezone for peak hour scheduling (PUBL-02)
    # Must be a valid pytz timezone string (e.g. "US/Eastern", "America/Mexico_City")
    audience_timezone: str = "US/Eastern"

    # Per-platform peak hour (start of window, 24h format, audience_timezone)
    # Defaults: TikTok 7-9pm, Instagram 11am-1pm, Facebook 1-3pm, YouTube 12-3pm
    peak_hour_tiktok: int = 19      # 7 PM
    peak_hour_instagram: int = 11   # 11 AM
    peak_hour_facebook: int = 13    # 1 PM
    peak_hour_youtube: int = 12     # 12 PM


@lru_cache
def get_settings() -> Settings:
    return Settings()
