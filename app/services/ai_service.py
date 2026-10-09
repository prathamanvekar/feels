import json
import hashlib
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.database import get_cached_ai_mood, save_cached_ai_mood
from app.models.schemas import SpotifyTrack, MoodProfile

logger = logging.getLogger("feels.ai")

class AIService:
    @staticmethod
    def compute_tracks_fingerprint(tracks: List[SpotifyTrack]) -> str:
        """Generates a stable SHA-256 hash representing this exact list of tracks."""
        fingerprint_data = "".join(f"{t.id}:{t.name}:{','.join(t.artists)}" for t in tracks)
        return hashlib.sha256(fingerprint_data.encode("utf-8")).hexdigest()

    @classmethod
    async def analyze_listening_mood(cls, tracks: List[SpotifyTrack]) -> MoodProfile:
        """
        Runs local inference with qwen2.5-coder:7b via Ollama to produce a structured mood profile.
        Caches result by track fingerprint to avoid redundant GPU/CPU inference.
        """
        tracks_hash = cls.compute_tracks_fingerprint(tracks)

        # Check database cache first
        cached = get_cached_ai_mood(tracks_hash)
        if cached:
            try:
                logger.info("Found cached AI mood analysis for tracks hash %s", tracks_hash[:8])
                return MoodProfile(**cached)
            except Exception as e:
                logger.warning("Error parsing cached AI mood: %s. Re-running inference.", e)

        # Prepare prompt for Qwen
        tracklist_text = "\n".join([
            f"- \"{t.name}\" by {', '.join(t.artists)} (Album: {t.album})"
            for t in tracks
        ])

        system_prompt = (
            "You are an expert musicologist, environmental psychologist, and outdoor curator. "
            "Analyze the user's recent music listening session as a cohesive emotional atmosphere. "
            "Do not merely look at song titles literally; synthesize the overall sonic texture, tempo, "
            "energy level (Low, Medium, or High), and emotional resonance. "
            "Determine what kind of outdoor environments and activities in Pune, India would best match "
            "this soundtrack to get the person away from their screen and into the real world.\n\n"
            "You MUST reply with ONLY a single valid JSON object strictly matching this schema:\n"
            "{\n"
            '  "mood_title": "Short evocative title (2-4 words, e.g. Kinetic High-Ridge Focus)",\n'
            '  "mood_summary": "1-2 thoughtful sentences summarizing the emotional essence of the session",\n'
            '  "dominant_qualities": ["Quality 1", "Quality 2", "Quality 3"],\n'
            '  "energy_level": "Low | Medium | High",\n'
            '  "suitable_outdoor_activities": ["Activity 1", "Activity 2", "Activity 3"],\n'
            '  "search_intents": ["outdoor nature trail Pune", "panoramic sunset hill Pune"],\n'
            '  "reasoning": "2-3 sentences explaining why this music connects with these outdoor settings."\n'
            "}\n"
            "Do NOT include markdown formatting or extra text outside the JSON object."
        )

        user_content = f"Recent listening session (10 tracks):\n{tracklist_text}\n\nProduce the structured JSON mood profile:"

        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\n{user_content}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.4,
                "top_p": 0.9,
                "num_predict": 700
            }
        }

        async with httpx.AsyncClient(timeout=float(settings.OLLAMA_TIMEOUT_SECONDS)) as client:
            try:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json=payload
                )
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Could not connect to Ollama at {settings.OLLAMA_BASE_URL}. "
                    f"Please ensure Ollama is running locally with '{settings.OLLAMA_MODEL}'."
                )

            if resp.status_code != 200:
                raise RuntimeError(f"Ollama inference error ({resp.status_code}): {resp.text}")

            result = resp.json()
            raw_response = result.get("response", "").strip()

            # Parse and validate JSON
            parsed_json = cls._extract_and_validate_json(raw_response)
            mood_profile = MoodProfile(**parsed_json)

            # Cache the validated result
            save_cached_ai_mood(tracks_hash, mood_profile.model_dump())
            logger.info("Generated and cached new AI mood profile: '%s'", mood_profile.mood_title)
            return mood_profile

    @classmethod
    async def generate_grounded_explanation(
        cls,
        place_title: str,
        place_category: str,
        place_neighborhood: str,
        mood: MoodProfile
    ) -> str:
        """
        Uses local Qwen to generate a single grounded sentence explaining why a specific Pune spot
        suits the user's listening mood, without hallucinating fake amenities.
        """
        prompt = (
            f"Write exactly ONE concise, grounded sentence explaining why '{place_title}' "
            f"({place_category} in {place_neighborhood}, Pune) is the ideal place to visit right now "
            f"given a listening mood of '{mood.mood_title}' ({mood.energy_level} energy: {mood.mood_summary}). "
            f"Do not invent false commercial features; focus on open air, atmosphere, and terrain. "
            f"Respond with only that single sentence."
        )

        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 120
            }
        }

        cache_key = f"{place_title}:{mood.mood_title}:{mood.energy_level}"
        if not hasattr(cls, "_explanation_cache"):
            cls._explanation_cache = {}
        if cache_key in cls._explanation_cache:
            return cls._explanation_cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json=payload)
                if resp.status_code == 200:
                    text = resp.json().get("response", "").strip()
                    # Clean up quotes if present
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]
                    cls._explanation_cache[cache_key] = text
                    return text
        except Exception as e:
            logger.warning("Local explanation generation fallback for %s: %s", place_title, e)

        # Fallback explanation if model is busy
        fallback = f"The open atmosphere and topography of {place_title} provide the exact spatial counterpart to your {mood.energy_level.lower()}-energy soundtrack."
        cls._explanation_cache[cache_key] = fallback
        return fallback


    @staticmethod
    def _extract_and_validate_json(raw: str) -> Dict[str, Any]:
        """Safely parses JSON from raw response, stripping any wrapping artifacts."""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.error("JSON decode error in Qwen output: %s\nRaw output: %s", err, raw)
            # Fallback recovery
            return {
                "mood_title": "Atmospheric Outdoor Resonance",
                "mood_summary": "A rich blend of sonic textures seeking physical space and fresh perspectives.",
                "dominant_qualities": ["Dynamic Cadence", "Spacious Horizon", "Outdoor Momentum"],
                "energy_level": "Medium",
                "suitable_outdoor_activities": ["Hill Walk", "Park Stride", "Quiet Overlook"],
                "search_intents": ["nature hills walking trails Pune", "open scenic gardens Pune"],
                "reasoning": "The emotional cadence of this listening session invites a transition from indoor focus to Pune's undulating hills and open parks."
            }

        # Normalize required keys
        required_keys = ["mood_title", "mood_summary", "dominant_qualities", "energy_level", "suitable_outdoor_activities", "search_intents", "reasoning"]
        for key in required_keys:
            if key not in data:
                data[key] = "Atmospheric" if "title" in key else ["Outdoor walk"]

        if not isinstance(data.get("dominant_qualities"), list):
            data["dominant_qualities"] = [str(data.get("dominant_qualities", "Atmospheric"))]
        if not isinstance(data.get("suitable_outdoor_activities"), list):
            data["suitable_outdoor_activities"] = ["Scenic walk in Pune"]
        if not isinstance(data.get("search_intents"), list) or len(data["search_intents"]) == 0:
            data["search_intents"] = ["outdoor nature trails Pune", "scenic viewpoints Pune"]

        # Bound search intents to max 2 queries
        data["search_intents"] = data["search_intents"][:2]

        return data

ai_service = AIService()
