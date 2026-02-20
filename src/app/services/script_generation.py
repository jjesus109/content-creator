import logging
from anthropic import Anthropic
from supabase import Client
from app.settings import get_settings
from app.services.database import get_supabase

logger = logging.getLogger(__name__)

# Cost rates for claude-haiku-3-5-20241022 (configurable via CLAUDE_GENERATION_MODEL)
# Haiku 3.5: $0.80/MTok input, $4.00/MTok output — cheapest capable model for short creative text
COST_INPUT_PER_MTOK = 0.80
COST_OUTPUT_PER_MTOK = 4.00


def _word_count(text: str) -> int:
    """Word count for Spanish text. Uses split() — NOT len(text) (that's character count)."""
    return len(text.split())


class ScriptGenerationService:
    """
    Generates Spanish philosophical scripts using the 6-pillar framework via Claude.

    All Claude API calls use the SYNCHRONOUS Anthropic client.
    This service runs inside APScheduler's ThreadPoolExecutor — no event loop.
    Do NOT switch to AsyncAnthropic.

    Cost is returned from every method so the caller (daily pipeline job)
    can call cb.record_attempt(cost) after each call.
    """

    def __init__(self, supabase: Client | None = None) -> None:
        self._supabase = supabase or get_supabase()
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_generation_model  # default: claude-haiku-3-5-20241022

    def _call_claude(self, system: str, user: str, max_tokens: int = 400) -> tuple[str, float]:
        """
        Internal: single Claude API call. Returns (text, cost_usd).
        temperature=0.9 for creative variation in philosophical scripts.
        """
        message = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.9,
        )
        text = message.content[0].text.strip()
        cost = (
            message.usage.input_tokens * COST_INPUT_PER_MTOK
            + message.usage.output_tokens * COST_OUTPUT_PER_MTOK
        ) / 1_000_000
        logger.debug("Claude call: %d in / %d out tokens, $%.6f", message.usage.input_tokens, message.usage.output_tokens, cost)
        return text, cost

    def load_active_rejection_constraints(self) -> list[dict]:
        """
        Reads rejection_constraints WHERE expires_at > now().
        Returns list of {reason_text, pattern_type}.
        Empty list when no active constraints (Phase 2 state — Phase 4 writes to this table).
        """
        try:
            result = self._supabase.table("rejection_constraints").select(
                "reason_text, pattern_type"
            ).gt("expires_at", "now()").execute()
            return result.data or []
        except Exception as e:
            logger.error("Failed to load rejection constraints: %s — proceeding without", e)
            return []

    def generate_topic_summary(
        self,
        mood: dict,
        attempt: int = 0,
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, float]:
        """
        Generate a short topic summary (~10-20 words) for similarity checking.
        The topic summary is embedded and compared against content_history BEFORE generating the full script.
        This avoids paying for full script generation on topics that will be rejected.

        attempt=0: Normal topic from the pool
        attempt=1: Same philosophical root, different angle (retry on similarity detection)
        attempt=2: Completely different topic from the same pool (second retry)

        Returns (topic_summary, cost_usd).
        """
        pool_name = mood.get("pool", "existential")
        tone = mood.get("tone", "contemplative")

        retry_instruction = ""
        if attempt == 1:
            retry_instruction = (
                "IMPORTANTE: Este es un segundo intento. Usa la misma raiz filosofica "
                "pero desde un angulo completamente diferente — otro pensador, otra paradoja, otra tension."
            )
        elif attempt >= 2:
            retry_instruction = (
                "IMPORTANTE: Este es el tercer intento. Elige un tema COMPLETAMENTE diferente "
                "dentro del mismo pool tematico — otra escuela, otro concepto, otra pregunta."
            )

        constraint_text = self._format_constraints(rejection_constraints or [])

        system = (
            "Eres un asistente que genera resúmenes de temas para guiones filosoficos en espanol neutro. "
            "Devuelve UNICAMENTE una frase corta (10-20 palabras) que capture el tema central del guion. "
            "Sin explicaciones, sin puntos, solo la frase del tema."
        )

        user = (
            f"Pool tematico: {pool_name}\n"
            f"Tono emocional: {tone}\n"
            f"{retry_instruction}\n"
            f"{constraint_text}\n"
            "Genera un resumen del tema para esta semana."
        )

        return self._call_claude(system, user, max_tokens=60)

    def generate_script(
        self,
        topic_summary: str,
        mood: dict,
        target_words: int,
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, float]:
        """
        Generate the full philosophical script in Spanish using the 6-pillar framework.

        The 6 pillars (ALL must be felt in every script — CONTEXT.md locked decision):
        1. Philosophical Root — real school, thinker, or concept (Stoicism, Nietzsche, Zen...)
        2. Universal Tension — opens with a contradiction the viewer recognizes in their own life
        3. Insight Flip — development reframes common understanding (not a summary, a shift)
        4. Emotional Anchor — connects insight to a specific feeling (peace, ambition, grief, clarity)
        5. Reflective CTA — asks the viewer to sit with one question or try one thing (NO "follow for more")
        6. Creator Archetype — "The Seeker": actively questions, admits uncertainty, invites thinking together

        Returns (script_text, cost_usd). Script may exceed target_words — caller must call summarize_if_needed().
        """
        tone = mood.get("tone", "contemplative")
        pool_name = mood.get("pool", "existential")
        constraint_text = self._format_constraints(rejection_constraints or [])

        system = (
            "Eres 'El Buscador' — un creador de contenido filosofico en espanol neutro que activamente "
            "cuestiona, explora con honestidad, admite incertidumbre e invita al espectador a pensar junto contigo. "
            "NO eres un maestro ni una autoridad. Eres un companero de reflexion.\n\n"
            "ESTRUCTURA OBLIGATORIA (los 6 pilares deben sentirse en cada guion):\n"
            "1. RAIZ FILOSOFICA: Ancla en una escuela real, pensador o concepto (Estoicismo, Nietzsche, Zen, Camus...)\n"
            "2. TENSION UNIVERSAL: Abre con una contradiccion o paradoja que el espectador reconoce en su propia vida\n"
            "3. GIRO DE PERSPECTIVA: El desarrollo reencuadra la comprension comun — no resume, desplaza el punto de vista\n"
            "4. ANCLA EMOCIONAL: Conecta el insight a un sentimiento especifico (paz, ambicion, duelo, claridad)\n"
            "5. CTA REFLEXIVO: Pide al espectador que se siente con una pregunta o pruebe una cosa — NUNCA 'sigueme para mas'\n"
            "6. ARQUETIPO DEL CREADOR: Tono de buscador — pregunta activamente, no dicta verdades absolutas\n\n"
            "REGLAS DE FORMATO:\n"
            f"- Escribe exactamente en espanol neutro, masculino, frases cortas optimizadas para voz AI\n"
            f"- Tono emocional de la semana: {tone}\n"
            f"- Objetivo de palabras: ~{target_words} palabras (puedes ir hasta {int(target_words * 1.15)} — se resumira si excedes)\n"
            "- Devuelve UNICAMENTE el guion, sin titulos, sin etiquetas de seccion, sin explicaciones"
        )

        user = (
            f"Tema: {topic_summary}\n"
            f"Pool tematico: {pool_name}\n"
            f"{constraint_text}\n"
            "Genera el guion."
        )

        # max_tokens: target_words * 4 gives room for Spanish word variance + pillar development
        return self._call_claude(system, user, max_tokens=target_words * 4)

    def summarize_if_needed(
        self,
        script: str,
        target_words: int,
    ) -> tuple[str, float]:
        """
        Check word count; if over target, make a second Claude call to compress.
        Preserves the 6-pillar structure during compression — development section absorbs cuts.

        Returns (final_script, cost_usd) where cost_usd is 0.0 if no summarization needed.
        The returned script is guaranteed to be within target_words.

        SCRP-03: Creator never sees an over-length script.
        """
        if _word_count(script) <= target_words:
            logger.debug("Word count OK: %d words (target: %d)", _word_count(script), target_words)
            return script, 0.0

        logger.info("Script over limit: %d words (target: %d) — summarizing", _word_count(script), target_words)

        system = (
            "Eres un editor de guiones filosoficos en espanol neutro. "
            "Tu unica tarea es reducir el guion al numero de palabras indicado, "
            "preservando obligatoriamente:\n"
            "- La raiz filosofica (pensador o escuela mencionado)\n"
            "- El ancla emocional (el sentimiento especifico)\n"
            "- El CTA reflexivo al final (la pregunta o accion para el espectador)\n"
            "Si necesitas recortar, comprime el desarrollo (el giro de perspectiva). "
            "Devuelve UNICAMENTE el guion resumido, sin explicaciones."
        )

        user = (
            f"Resume este guion a aproximadamente {target_words} palabras (maximo {int(target_words * 1.05)}):\n\n"
            f"{script}"
        )

        summarized, cost = self._call_claude(system, user, max_tokens=target_words * 3)

        # Verify the summary is actually shorter; truncate at sentence boundary if overshot
        final_count = _word_count(summarized)
        if final_count > target_words:
            # Truncate to last sentence boundary within target_words
            words = summarized.split()
            truncated = " ".join(words[:target_words])
            # Walk back to last sentence-ending punctuation to avoid mid-sentence cut
            for end_char in (".", "!", "?"):
                last_end = truncated.rfind(end_char)
                if last_end > len(truncated) * 0.7:  # only if sentence is reasonably long
                    truncated = truncated[:last_end + 1]
                    break
            logger.warning(
                "Summarization overshot: %d words (target: %d) — truncated to sentence boundary",
                final_count, target_words
            )
            summarized = truncated

        return summarized, cost

    def _format_constraints(self, constraints: list[dict]) -> str:
        """Format active rejection constraints into a prompt injection string."""
        if not constraints:
            return ""
        lines = ["RESTRICCIONES ACTIVAS (evitar estos patrones esta semana):"]
        for c in constraints:
            lines.append(f"- [{c.get('pattern_type', 'topic')}] {c.get('reason_text', '')}")
        return "\n".join(lines) + "\n"
