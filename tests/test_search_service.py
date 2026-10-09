import pytest
from unittest.mock import patch
from app.config import settings
from app.database import init_db, save_cached_serpapi_search, get_cached_serpapi_search
from app.services.search_service import SearchService, PUNE_VERIFIED_OUTDOOR_PLACES
from app.models.schemas import MoodProfile

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    test_db_path = str(tmp_path / "test_search.db")
    with patch.object(settings, "DATABASE_PATH", test_db_path):
        init_db()
        yield test_db_path

def test_query_normalization():
    q1 = "   Outdoor Trails PUNE  "
    q2 = "outdoor trails pune"
    assert SearchService.normalize_query_key(q1) == SearchService.normalize_query_key(q2)

def test_serpapi_cache_save_and_retrieve():
    key = SearchService.normalize_query_key("vetal tekdi hill walk")
    date_str = settings.get_current_date_str()
    dummy_results = [{"id": "p1", "title": "Vetal Tekdi", "category": "Ridge"}]

    save_cached_serpapi_search(key, date_str, dummy_results)
    cached = get_cached_serpapi_search(key, date_str)

    assert cached is not None
    assert len(cached) == 1
    assert cached[0]["title"] == "Vetal Tekdi"

def test_pune_verified_places_have_essential_fields():
    assert len(PUNE_VERIFIED_OUTDOOR_PLACES) >= 8
    for place in PUNE_VERIFIED_OUTDOOR_PLACES:
        assert "id" in place
        assert "title" in place
        assert "neighborhood" in place
        assert "category" in place
        assert "directions_url" in place
        assert "Pune" in place["directions_url"]

def test_discover_recommendations_deduplication():
    import asyncio
    
    mood = MoodProfile(
        mood_title="High Energy Ascent",
        mood_summary="High tempo music",
        dominant_qualities=["Fast"],
        energy_level="High",
        suitable_outdoor_activities=["Trail Run"],
        search_intents=["running hills Pune"],
        reasoning="Connecting music with high hills."
    )

    session_id = "test_dedup_session"
    
    async def _run():
        with patch("app.services.ai_service.ai_service.generate_grounded_explanation", return_value="High energy terrain matches your music."):
            # First discovery batch
            batch_1 = await SearchService.discover_recommendations(session_id, mood, limit=3)
            assert len(batch_1) == 3
            ids_1 = {p.id for p in batch_1}

            # Second discovery batch (refresh)
            batch_2 = await SearchService.discover_recommendations(session_id, mood, limit=3)
            assert len(batch_2) == 3
            ids_2 = {p.id for p in batch_2}

            # Smart rotation should favor new places if available
            assert len(ids_1.union(ids_2)) > 3

    asyncio.run(_run())

