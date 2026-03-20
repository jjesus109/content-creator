"""
Phase 10 shared test fixtures.

Provides: mock_scene_library, mock_music_pool, mock_supabase, mock_openai_client.
Used by: test_music_pool.py, test_scene_engine.py, test_seasonal_calendar.py,
         test_anti_repetition.py, test_music_matcher.py, test_caption_generator.py,
         test_pipeline_wiring.py
"""
import json
import pytest
from unittest.mock import MagicMock

SAMPLE_SCENE_LIBRARY = [
    {"location": "cocina", "activity": "inspeccionar olla", "mood": "curious", "weight": 1.0},
    {"location": "terraza", "activity": "vigilar pájaros", "mood": "playful", "weight": 0.8},
    {"location": "sofá", "activity": "dormir estirado", "mood": "sleepy", "weight": 1.0},
    {"location": "jardín", "activity": "perseguir mariposa", "mood": "playful", "weight": 0.9},
    {"location": "ventana", "activity": "observar lluvia", "mood": "curious", "weight": 0.7},
]

SAMPLE_MUSIC_POOL = [
    {"id": "uuid-1", "title": "Siesta Suave", "artist": "Lo-Fi Mexico", "file_url": "https://example.com/1.mp3", "mood": "sleepy", "bpm": 75, "platform_tiktok": True, "platform_youtube": True, "platform_instagram": True, "platform_facebook": True, "license_expires_at": None},
    {"id": "uuid-2", "title": "Gatito Juguetón", "artist": "Tropical Beats", "file_url": "https://example.com/2.mp3", "mood": "playful", "bpm": 118, "platform_tiktok": True, "platform_youtube": True, "platform_instagram": False, "platform_facebook": True, "license_expires_at": None},
    {"id": "uuid-3", "title": "Curiosidad Felina", "artist": "Ambient MX", "file_url": "https://example.com/3.mp3", "mood": "curious", "bpm": 95, "platform_tiktok": False, "platform_youtube": True, "platform_instagram": True, "platform_facebook": True, "license_expires_at": None},
]

SAMPLE_EXPIRED_TRACK = {
    "id": "uuid-expired",
    "title": "Expired Song",
    "artist": "Old Artist",
    "file_url": "https://example.com/expired.mp3",
    "mood": "playful",
    "bpm": 115,
    "platform_tiktok": True,
    "platform_youtube": True,
    "platform_instagram": True,
    "platform_facebook": True,
    "license_expires_at": "2026-01-01T00:00:00Z",
}


@pytest.fixture
def expired_track():
    return SAMPLE_EXPIRED_TRACK


@pytest.fixture
def mock_scene_library():
    return SAMPLE_SCENE_LIBRARY


@pytest.fixture
def mock_music_pool():
    return SAMPLE_MUSIC_POOL


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for Phase 10 tests."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client returning structured scene+caption JSON."""
    client = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = json.dumps({
        "scene_prompt": "Mochi, el gato naranja tabby, inspecciona con curiosidad una olla humeante en la cocina mexicana. Sus orejas están erguidas mientras olfatea el aroma. La luz cálida del atardecer entra por la ventana.",
        "caption": "Mochi descubre los secretos de la cocina"
    })
    response.usage.prompt_tokens = 150
    response.usage.completion_tokens = 80
    client.chat.completions.create.return_value = response
    return client
