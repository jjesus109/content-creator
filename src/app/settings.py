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
    claude_generation_model: str = "claude-haiku-3-5-20241022"  # configurable — upgrade to sonnet without redeploy


@lru_cache
def get_settings() -> Settings:
    return Settings()
