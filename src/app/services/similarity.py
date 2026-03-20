import logging
from supabase import Client
from app.services.database import get_supabase

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85   # 85% cosine similarity — reject if any history entry exceeds this
LOOKBACK_DAYS = 90             # Only compare against last 90 days of content history

SCENE_SIMILARITY_THRESHOLD = 0.78   # 75-80% cosine similarity — recalibrated for visual scenes
                                      # Empirically validated via dry-run script before enforcement
SCENE_LOOKBACK_DAYS = 7             # 7-day window (visual scenes need shorter memory than scripts)


class SimilarityService:
    """
    Wraps the check_script_similarity Postgres function via Supabase RPC.

    CRITICAL: PostgREST (supabase-py) does not support pgvector operators (<=>)
    in .table().select() queries. MUST use .rpc() to call the SQL function.

    The check_script_similarity function returns rows where cosine SIMILARITY
    exceeds the threshold. Similarity = 1 - cosine distance. The SQL function
    already handles the inversion — Python code just checks if any rows returned.
    """

    def __init__(self, supabase: Client | None = None) -> None:
        self._supabase = supabase or get_supabase()

    def is_too_similar(
        self,
        embedding: list[float],
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> bool:
        """
        Returns True if any script in content_history exceeds the similarity threshold.
        Returns False when content_history is empty (first run — no false positive).

        Args:
            embedding: 1536-dimension vector from EmbeddingService.generate()
            threshold: cosine similarity threshold (default 0.85)

        Returns True → caller should retry with a different topic.
        Returns False → topic is sufficiently unique, proceed to script generation.
        """
        try:
            result = self._supabase.rpc(
                "check_script_similarity",
                {
                    "query_embedding": embedding,
                    "similarity_threshold": threshold,
                    "lookback_days": LOOKBACK_DAYS,
                },
            ).execute()
            is_similar = len(result.data) > 0
            if is_similar:
                logger.info(
                    "Similarity check: REJECT — %d matching script(s) above %.0f%% threshold",
                    len(result.data),
                    threshold * 100,
                )
            else:
                logger.debug("Similarity check: PASS — topic is sufficiently unique")
            return is_similar
        except Exception as e:
            # If similarity check fails (e.g., DB connection issue), log and fail OPEN
            # (allow generation to proceed) — content repetition is preferable to a silent outage
            logger.error("Similarity check failed: %s — defaulting to PASS", e)
            return False

    def is_too_similar_scene(
        self,
        embedding: list[float],
        threshold: float = SCENE_SIMILARITY_THRESHOLD,
    ) -> bool:
        """
        Returns True if any scene in content_history exceeds the similarity threshold.
        Uses check_scene_similarity SQL function (7-day lookback, scene_embedding column).
        Mirrors is_too_similar() but for scene embeddings (separate table function, different defaults).

        Returns False when content_history is empty or on DB error (fail open — same as is_too_similar()).

        NOTE: Caller is responsible for respecting the scene_anti_repetition_enabled feature flag.
        This method always executes the check; the pipeline decides whether to enforce it.
        """
        try:
            result = self._supabase.rpc(
                "check_scene_similarity",
                {
                    "query_embedding": embedding,
                    "similarity_threshold": threshold,
                    "lookback_days": SCENE_LOOKBACK_DAYS,
                },
            ).execute()
            is_similar = len(result.data) > 0
            if is_similar:
                logger.info(
                    "Scene similarity check: REJECT — %d matching scene(s) above %.0f%% threshold",
                    len(result.data),
                    threshold * 100,
                )
            else:
                logger.debug("Scene similarity check: PASS — scene is sufficiently unique")
            return is_similar
        except Exception as e:
            logger.error("Scene similarity check failed: %s — defaulting to PASS", e)
            return False

    def get_similar_scripts(
        self,
        embedding: list[float],
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> list[dict]:
        """
        Returns list of matching scripts (id, topic_summary, similarity).
        Used for logging/debugging — daily pipeline uses is_too_similar() instead.
        """
        result = self._supabase.rpc(
            "check_script_similarity",
            {
                "query_embedding": embedding,
                "similarity_threshold": threshold,
                "lookback_days": LOOKBACK_DAYS,
            },
        ).execute()
        return result.data
