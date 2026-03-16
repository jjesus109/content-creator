import sys, logging
sys.path.insert(0, "src")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from unittest.mock import patch
from app.services.embeddings import EmbeddingService
from app.services.database import get_supabase

supabase = get_supabase()
embed_svc = EmbeddingService()

# Seed the same topic that the mock will return on attempt 0 and 1
seed_topic = "La libertad segun Sartre y la angustia de elegir sin red de seguridad"
embedding, _ = embed_svc.generate(seed_topic)
supabase.table("content_history").insert({
    "script_text": "[TEST SEED] Eliminar despues.",
    "topic_summary": seed_topic,
    "embedding": embedding,
}).execute()
print(f"Seeded: {seed_topic!r}\n")

# Mock: attempts 0 and 1 return the seeded topic (forces retry),
#       attempt 2 returns a genuinely different topic (should pass)
attempt_topics = {
    0: (seed_topic, 0.0),
    1: ("Sartre y la nausea existencial como fuente de libertad autentica", 0.0),
    2: ("El concepto Zen de Mushin y la accion sin esfuerzo consciente", 0.0),
}

def mock_topic(mood, attempt, rejection_constraints):
    topic, cost = attempt_topics[attempt]
    print(f"  [mock] generate_topic_summary(attempt={attempt}) → {topic!r}")
    return topic, cost

def mock_script(topic_summary, mood, target_words, rejection_constraints):
    return f"[TEST SCRIPT] Topic: {topic_summary}", 0.0

def mock_summarize(script, target_words):
    return script, 0.0

with patch("app.scheduler.jobs.daily_pipeline.ScriptGenerationService.generate_topic_summary", mock_topic), \
    patch("app.scheduler.jobs.daily_pipeline.ScriptGenerationService.generate_script", mock_script), \
    patch("app.scheduler.jobs.daily_pipeline.ScriptGenerationService.summarize_if_needed", mock_summarize):
    from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
    daily_pipeline_job()

print("\nDone. Check content_history for the saved test script.")