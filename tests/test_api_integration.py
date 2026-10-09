import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import init_db
from app.models.schemas import MoodProfile

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path):
    test_db = str(tmp_path / "test_api.db")
    with patch.object(settings, "DATABASE_PATH", test_db):
        init_db()
        yield

def test_root_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Feels" in response.text
    assert "Pune" in response.text

def test_app_serves_html():
    response = client.get("/app")
    assert response.status_code == 200
    assert "Feels" in response.text
    assert "Translating Music into Movement" in response.text



def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "ollama_model" in data
    assert "timezone" in data
    assert data["timezone"] == "Asia/Kolkata"

def test_auth_status_unauthenticated():
    response = client.get("/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["quota"]["daily_limit"] == 15
    assert data["quota"]["remaining_count"] == 15

def test_auth_disconnect():
    response = client.post("/auth/disconnect")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "disconnected"

def test_recommendations_unauthenticated_returns_401():
    response = client.get("/api/recommendations")
    assert response.status_code == 401
    assert "Spotify" in response.json()["detail"]

def test_preview_demo_endpoint_runs_pipeline():
    mock_mood = MoodProfile(
        mood_title="Kinetic Sahyadri Focus",
        mood_summary="Driving rhythms and adrenaline seeking steep ascents.",
        dominant_qualities=["Drive", "Tempo", "Open Air"],
        energy_level="High",
        suitable_outdoor_activities=["Trail Running", "Hill Climb"],
        search_intents=["Vetal Tekdi Pune hills"],
        reasoning="Music demands cardiovascular engagement on Pune's hills."
    )

    with patch("app.services.ai_service.ai_service.analyze_listening_mood", AsyncMock(return_value=mock_mood)):
        with patch("app.services.ai_service.ai_service.generate_grounded_explanation", AsyncMock(return_value="Trail suits your fast BPM music.")):
            response = client.post("/api/preview-demo")
            assert response.status_code == 200
            data = response.json()
            assert len(data["tracks"]) == 10
            assert data["mood_profile"]["mood_title"] == "Kinetic Sahyadri Focus"
            assert len(data["places"]) == 3
            assert data["is_cached_listening"] is True
            assert data["quota"]["remaining_count"] == 15

def test_refresh_rate_limit_enforcement():
    mock_mood = MoodProfile(
        mood_title="Zen Water Reflection",
        mood_summary="Acoustic textures seeking calm waters.",
        dominant_qualities=["Calm", "Reflective"],
        energy_level="Low",
        suitable_outdoor_activities=["Lake Walk"],
        search_intents=["Pashan Lake bird watching Pune"],
        reasoning="Calm acoustic dynamics pair with lake waters."
    )

    # Simulate 15 successful refreshes
    with patch("app.services.spotify_service.spotify_service.get_recently_played_tracks", AsyncMock(return_value=([], True))):
        with patch("app.services.ai_service.ai_service.analyze_listening_mood", AsyncMock(return_value=mock_mood)):
            with patch("app.services.search_service.search_service.discover_recommendations", AsyncMock(return_value=[])):
                # Run 15 refreshes
                for i in range(15):
                    resp = client.post("/api/refresh")
                    assert resp.status_code == 200

                # The 16th refresh must return HTTP 429
                resp = client.post("/api/refresh")
                assert resp.status_code == 429
                assert "Daily refresh limit reached" in resp.json()["detail"]
