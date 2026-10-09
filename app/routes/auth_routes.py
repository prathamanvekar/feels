import secrets
import logging
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from app.config import settings
from app.services.spotify_service import spotify_service
from app.services.rate_limiter import rate_limiter
from app.database import (
    save_session,
    get_session,
    delete_session_data,
    get_cached_spotify_history
)
from app.models.schemas import AuthStatus, RefreshQuotaStatus

logger = logging.getLogger("feels.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory dictionary for transient OAuth state validation
_oauth_states = {}

def get_or_create_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get("feels_session_id") or request.cookies.get("tg_session_id")
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        response.set_cookie(
            key="feels_session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=settings.COOKIE_SECURE,
            max_age=86400 * 30  # 30 days
        )
    return session_id

@router.get("/login")
async def login(request: Request, response: Response):
    """Initiates the Spotify Authorization Code OAuth flow."""
    if not settings.SPOTIFY_CLIENT_ID:
        raise HTTPException(
            status_code=400,
            detail="Spotify Client ID is not configured. Please set SPOTIFY_CLIENT_ID in your .env file."
        )

    session_id = request.cookies.get("feels_session_id") or request.cookies.get("tg_session_id")
    if not session_id:
        session_id = secrets.token_urlsafe(32)

    state = secrets.token_urlsafe(24)
    _oauth_states[state] = session_id

    auth_url = spotify_service.generate_auth_url(state)
    redirect = RedirectResponse(url=auth_url, status_code=307)
    redirect.set_cookie(
        key="tg_session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=86400 * 30
    )
    return redirect

@router.get("/callback")
async def callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handles the redirect back from Spotify after user authorization."""
    if error:
        logger.warning("Spotify authorization denied or failed with: %s", error)
        return RedirectResponse(url=f"/?auth_error={error}", status_code=303)

    if not code or not state:
        return RedirectResponse(url="/?auth_error=missing_code_or_state", status_code=303)

    expected_session_id = _oauth_states.pop(state, None)
    cookie_session_id = request.cookies.get("tg_session_id")

    session_id = expected_session_id or cookie_session_id
    if not session_id:
        return RedirectResponse(url="/?auth_error=invalid_oauth_state", status_code=303)

    try:
        token_data = await spotify_service.exchange_code_for_tokens(code)
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 3600)

        # Store tokens safely in SQLite
        save_session(session_id, access_token, refresh_token, expires_in)
        logger.info("Spotify credentials safely stored for session %s", session_id[:8])

        response = RedirectResponse(url="/app?connected=true", status_code=303)
        response.set_cookie(
            key="feels_session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=settings.COOKIE_SECURE,
            max_age=86400 * 30
        )
        return response

    except Exception as e:
        logger.error("OAuth callback error: %s", e)
        return RedirectResponse(url=f"/?auth_error={str(e)}", status_code=303)

@router.get("/status", response_model=AuthStatus)
async def auth_status(request: Request, response: Response):
    """Returns the current Spotify authentication and daily refresh quota status."""
    session_id = get_or_create_session_id(request, response)
    session = get_session(session_id)
    today_str = settings.get_current_date_str()

    quota_data = rate_limiter.get_user_refresh_status(session_id)
    quota = RefreshQuotaStatus(**quota_data)

    is_authenticated = bool(session and session.get("access_token"))
    cached_tracks = bool(get_cached_spotify_history(session_id, today_str))

    return AuthStatus(
        authenticated=is_authenticated,
        spotify_user_id=session.get("spotify_user_id") if session else None,
        has_cached_tracks=cached_tracks,
        quota=quota
    )

@router.post("/disconnect")
async def disconnect(request: Request, response: Response):
    """
    Disconnects the Spotify account and clears stored tokens, cached listening history,
    and recommendation history.
    """
    session_id = request.cookies.get("feels_session_id") or request.cookies.get("tg_session_id")
    if session_id:
        delete_session_data(session_id)
        logger.info("Cleared all local data and session for %s", session_id[:8])

    response.delete_cookie("feels_session_id")
    response.delete_cookie("tg_session_id")
    return {
        "status": "disconnected",
        "message": "Spotify account disconnected. All local tokens, cached listening history, and session limits have been wiped."
    }
