from functools import lru_cache
from supabase import create_client, Client
from app.settings import get_settings


@lru_cache
def get_supabase() -> Client:
    """
    Supabase client singleton.
    Uses service_role key (not anon key) for unrestricted server-side access.
    Called by: CircuitBreakerService, health endpoint, future pipeline services.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)
