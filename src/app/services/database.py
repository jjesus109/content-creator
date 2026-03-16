import base64
import json
import logging
from functools import lru_cache

from supabase import create_client, Client

from app.settings import get_settings

logger = logging.getLogger(__name__)


def validate_supabase_key(key: str) -> None:
    """
    Decode the JWT payload section (middle segment) and assert role == 'service_role'.
    No signature verification — we only read the claim.
    Raises RuntimeError with a clear, actionable message if validation fails.
    Called from lifespan before run_migrations() so misconfiguration fails fast.
    """
    try:
        parts = key.split(".")
        if len(parts) != 3:
            raise ValueError("not a three-part JWT")
        payload_b64 = parts[1]
        # JWT base64url uses no padding; add == to satisfy stdlib decoder
        padding = "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes)
        role = payload["role"]
    except Exception as exc:
        raise RuntimeError(
            f"Could not decode SUPABASE_KEY as a JWT — is it set correctly in Railway? "
            f"Error: {exc}"
        ) from exc

    if role != "service_role":
        raise RuntimeError(
            f"SUPABASE_KEY appears to be the anon key (role='{role}'). "
            "Set it to the service_role key in Railway — "
            "the anon key cannot bypass RLS and will cause 403s on every Storage upload."
        )

    logger.info("SUPABASE_KEY validated: service_role JWT confirmed")


@lru_cache
def get_supabase() -> Client:
    """
    Supabase client singleton.
    Uses service_role key (not anon key) for unrestricted server-side access.
    Called by: CircuitBreakerService, health endpoint, future pipeline services.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)
