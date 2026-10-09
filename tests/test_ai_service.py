import pytest
from app.services.ai_service import AIService
from app.models.schemas import SpotifyTrack, MoodProfile

def test_tracks_fingerprint_deterministic():
    tracks1 = [
        SpotifyTrack(id="t1", name="Track A", artists=["Artist 1"], album="Album X"),
        SpotifyTrack(id="t2", name="Track B", artists=["Artist 2"], album="Album Y")
    ]
    tracks2 = [
        SpotifyTrack(id="t1", name="Track A", artists=["Artist 1"], album="Album X"),
        SpotifyTrack(id="t2", name="Track B", artists=["Artist 2"], album="Album Y")
    ]
    # Changed track
    tracks3 = [
        SpotifyTrack(id="t1", name="Track A", artists=["Artist 1"], album="Album X"),
        SpotifyTrack(id="t3", name="Track C", artists=["Artist 3"], album="Album Z")
    ]

    hash1 = AIService.compute_tracks_fingerprint(tracks1)
    hash2 = AIService.compute_tracks_fingerprint(tracks2)
    hash3 = AIService.compute_tracks_fingerprint(tracks3)

    assert hash1 == hash2
    assert hash1 != hash3

def test_extract_and_validate_json_clean_payload():
    raw = '''{
        "mood_title": "Kinetic High-Ridge Focus",
        "mood_summary": "High BPM and driving percussion seeking an uphill climb.",
        "dominant_qualities": ["Fast Pace", "Focused Drive", "Aerobic Rhythm"],
        "energy_level": "High",
        "suitable_outdoor_activities": ["Hill Sprint", "Ridge Run"],
        "search_intents": ["steep hill trail Pune", "panoramic nature Tekdi Pune"],
        "reasoning": "The rapid cadence and heavy bassline require physical engagement outdoors."
    }'''
    parsed = AIService._extract_and_validate_json(raw)
    profile = MoodProfile(**parsed)

    assert profile.mood_title == "Kinetic High-Ridge Focus"
    assert profile.energy_level == "High"
    assert len(profile.dominant_qualities) == 3
    assert len(profile.search_intents) == 2

def test_extract_and_validate_json_with_markdown_fences():
    raw = '''```json
    {
        "mood_title": "Zen Canopy Walk",
        "mood_summary": "Soft acoustic guitars and gentle reverbs.",
        "dominant_qualities": ["Acoustic", "Contemplative", "Gentle"],
        "energy_level": "Low",
        "suitable_outdoor_activities": ["Shaded Walk", "Bench Reading"],
        "search_intents": ["botanical garden shaded walk Pune"],
        "reasoning": "Subtle textures and soft tones pair naturally with serene botanical spaces."
    }
    ```'''
    parsed = AIService._extract_and_validate_json(raw)
    profile = MoodProfile(**parsed)

    assert profile.mood_title == "Zen Canopy Walk"
    assert profile.energy_level == "Low"

def test_extract_and_validate_json_malformed_fallback():
    raw = "I could not generate valid JSON. The music was very good."
    parsed = AIService._extract_and_validate_json(raw)
    profile = MoodProfile(**parsed)

    # Must safely fall back to valid MoodProfile without throwing
    assert profile.mood_title != ""
    assert profile.energy_level in ["Low", "Medium", "High"]
    assert len(profile.search_intents) <= 2
