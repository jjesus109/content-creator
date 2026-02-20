import logging
from openai import OpenAI
from app.settings import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims — matches content_history.embedding vector(1536)
# Embedding cost: $0.02/MTok for text-embedding-3-small — negligible per call but counted by circuit breaker
COST_PER_MTOK = 0.02


class EmbeddingService:
    """
    Wraps OpenAI embeddings API.
    Uses synchronous client — safe in APScheduler ThreadPoolExecutor.
    Do NOT use AsyncOpenAI here — thread pool jobs have no event loop.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, text: str) -> tuple[list[float], float]:
        """
        Generate a 1536-dimension embedding for the given text.

        Returns:
            (embedding, cost_usd) where embedding is list[float] of length 1536.

        Use for:
            - Topic summaries before similarity check (short text, ~10-20 words)
            - Script text when saving to content_history (full script)

        The embedding model tokenizes Spanish text correctly.
        Cost is returned so the caller can report to CircuitBreakerService.
        """
        response = self._client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        embedding = response.data[0].embedding  # list[float], 1536 elements
        tokens_used = response.usage.total_tokens
        cost_usd = (tokens_used / 1_000_000) * COST_PER_MTOK
        logger.debug("Embedding generated: %d tokens, $%.6f", tokens_used, cost_usd)
        return embedding, cost_usd
