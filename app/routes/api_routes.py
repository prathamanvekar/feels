import logging
from fastapi import APIRouter, Request, Response, HTTPException, status
import httpx

from app.config import settings
from app.services.spotify_service import spotify_service
from app.services.ai_service import ai_service
from app.services.search_service import search_service
from app.services.rate_limiter import rate_limiter
from app.routes.auth_routes import get_or_create_session_id
from app.models.schemas import (
    RecommendationResponse,
    RefreshQuotaStatus,
    HealthResponse
)

logger = logging.getLogger("feels.api")
router = APIRouter(prefix="/api", tags=["Recommendations & Diagnostics"])

@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(request: Request, response: Response):
    """
    Retrieves the current soundtrack mood profile and curated Pune outdoor spots.
    Reuses cached tracks if already fetched today.
    """
    session_id = get_or_create_session_id(request, response)

    try:
        # 1. Fetch recently played tracks (cached daily per user)
        tracks, is_cached_listening = await spotify_service.get_recently_played_tracks(session_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving tracks: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Spotify service error: {str(e)}")

    try:
        # 2. Local Ollama inference with qwen2.5-coder:7b
        mood_profile = await ai_service.analyze_listening_mood(tracks)
    except Exception as e:
        logger.error("Local AI inference error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Local AI model unavailable: {str(e)}. Make sure Ollama is running with qwen2.5-coder:7b."
        )

    try:
        # 3. Discover curated Pune locations matching mood
        places = await search_service.discover_recommendations(session_id, mood_profile, limit=3)
    except Exception as e:
        logger.error("Location discovery error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Location discovery error: {str(e)}")

    # 4. Quota and SerpAPI status
    quota_info = rate_limiter.get_user_refresh_status(session_id)
    budget_info = rate_limiter.get_serpapi_budget_status()

    return RecommendationResponse(
        tracks=tracks,
        mood_profile=mood_profile,
        places=places,
        quota=RefreshQuotaStatus(**quota_info),
        is_cached_listening=is_cached_listening,
        is_refreshed=False,
        serpapi_budget_remaining=budget_info["remaining_budget"],
        message="Recommendations ready based on your recent soundtrack."
    )

@router.post("/refresh", response_model=RecommendationResponse)
async def refresh_recommendations(request: Request, response: Response):
    """
    User-triggered refresh for new Pune recommendations.
    Strictly enforces max 15 refreshes per day. Reuses cached Spotify tracks.
    """
    session_id = get_or_create_session_id(request, response)

    # 1. Enforce user-triggered daily refresh limit (15 max)
    allowed, used_count, remaining_count = rate_limiter.attempt_user_refresh(session_id)
    quota_info = rate_limiter.get_user_refresh_status(session_id)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily refresh limit reached ({settings.USER_DAILY_REFRESH_LIMIT}/{settings.USER_DAILY_REFRESH_LIMIT}). "
                f"Your quota resets at midnight ({quota_info['resets_at']}). "
                f"Time to close the screen and head outside!"
            )
        )

    # 2. Get tracks (reusing today's cached tracks, never re-hitting Spotify API needlessly)
    try:
        tracks, is_cached_listening = await spotify_service.get_recently_played_tracks(session_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # 3. AI mood profile (from cache if same tracks)
    mood_profile = await ai_service.analyze_listening_mood(tracks)

    # 4. Fresh discovery / rotated places in Pune
    places = await search_service.discover_recommendations(session_id, mood_profile, limit=3)
    budget_info = rate_limiter.get_serpapi_budget_status()

    return RecommendationResponse(
        tracks=tracks,
        mood_profile=mood_profile,
        places=places,
        quota=RefreshQuotaStatus(**quota_info),
        is_cached_listening=is_cached_listening,
        is_refreshed=True,
        serpapi_budget_remaining=budget_info["remaining_budget"],
        message=f"Refreshed recommendations. You have {remaining_count} refreshes remaining today."
    )

@router.get("/quota", response_model=RefreshQuotaStatus)
async def get_quota_status(request: Request, response: Response):
    """Returns the user's remaining refresh quota for today."""
    session_id = get_or_create_session_id(request, response)
    quota_info = rate_limiter.get_user_refresh_status(session_id)
    return RefreshQuotaStatus(**quota_info)

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check testing Ollama connectivity, model status, and DB."""
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                tags_data = resp.json()
                models = [m.get("name") for m in tags_data.get("models", [])]
                ollama_ok = any(settings.OLLAMA_MODEL in m for m in models)
    except Exception as e:
        logger.warning("Ollama health check check failed: %s", e)

    return HealthResponse(
        status="healthy" if ollama_ok else "degraded",
        ollama_connected=ollama_ok,
        ollama_model=settings.OLLAMA_MODEL,
        database_ok=True,
        serpapi_configured=bool(settings.SERPAPI_API_KEY and not settings.SERPAPI_API_KEY.startswith("your_")),
        timezone=settings.APP_TIMEZONE,
        current_date=settings.get_current_date_str()
    )

@router.post("/preview-demo", response_model=RecommendationResponse)
async def preview_sample_recommendations(request: Request, response: Response):
    """
    Test fixture endpoint allowing live evaluation of the local Qwen model and SerpAPI
    pipeline using a sample 10-track listening session from the project brief.
    Clearly marks is_cached_listening=True.
    """
    session_id = get_or_create_session_id(request, response)
    
    sample_tracks = [
        {"id": "s1", "name": "'Till I Collapse", "artists": ["Eminem", "Nate Dogg"], "album": "The Eminem Show", "album_art_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=300&q=80"},
        {"id": "s2", "name": "Robbers", "artists": ["The 1975"], "album": "The 1975", "album_art_url": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=300&q=80"},
        {"id": "s3", "name": "Run Boy Run", "artists": ["Woodkid"], "album": "The Golden Age", "album_art_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=300&q=80"},
        {"id": "s4", "name": "Midnight City", "artists": ["M83"], "album": "Hurry Up, We're Dreaming", "album_art_url": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=300&q=80"},
        {"id": "s5", "name": "Intro", "artists": ["The xx"], "album": "xx", "album_art_url": "https://images.unsplash.com/photo-1445985543469-221e57446c70?auto=format&fit=crop&w=300&q=80"},
        {"id": "s6", "name": "Breathe", "artists": ["The Prodigy"], "album": "The Fat of the Land", "album_art_url": "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?auto=format&fit=crop&w=300&q=80"},
        {"id": "s7", "name": "Weightless", "artists": ["Marconi Union"], "album": "Weightless (Ambient Transmissions Vol. 2)", "album_art_url": "https://images.unsplash.com/photo-1518495973542-4542c06a5843?auto=format&fit=crop&w=300&q=80"},
        {"id": "s8", "name": "Holocene", "artists": ["Bon Iver"], "album": "Bon Iver", "album_art_url": "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=300&q=80"},
        {"id": "s9", "name": "Sail", "artists": ["AWOLNATION"], "album": "Megalithic Symphony", "album_art_url": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=300&q=80"},
        {"id": "s10", "name": "Teardrop", "artists": ["Massive Attack"], "album": "Mezzanine", "album_art_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=300&q=80"}
    ]
    
    from app.models.schemas import SpotifyTrack
    tracks = [SpotifyTrack(**t) for t in sample_tracks]
    
    # Run the real local Qwen AI model
    mood_profile = await ai_service.analyze_listening_mood(tracks)
    places = await search_service.discover_recommendations(session_id, mood_profile, limit=3)
    quota_info = rate_limiter.get_user_refresh_status(session_id)
    budget_info = rate_limiter.get_serpapi_budget_status()

    return RecommendationResponse(
        tracks=tracks,
        mood_profile=mood_profile,
        places=places,
        quota=RefreshQuotaStatus(**quota_info),
        is_cached_listening=True,
        is_refreshed=False,
        serpapi_budget_remaining=budget_info["remaining_budget"],
        message="Running with sample listening session test fixture. Local Qwen 2.5 Coder 7B inference active."
    )

