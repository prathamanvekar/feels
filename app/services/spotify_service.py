import urllib.parse
import secrets
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import httpx

from app.config import settings
from app.database import (
    save_session,
    get_session,
    get_cached_spotify_history,
    save_cached_spotify_history
)
from app.models.schemas import SpotifyTrack

logger = logging.getLogger("feels.spotify")

class SpotifyService:
    @staticmethod
    def generate_auth_url(state: str) -> str:
        """Constructs the Spotify OAuth authorization URL."""
        params = {
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
            "scope": settings.SPOTIFY_SCOPES,
            "state": state,
            "show_dialog": "true"
        }
        return f"{settings.SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    @staticmethod
    async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
        """Exchanges authorization code for access and refresh tokens."""
        if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
            raise ValueError("Spotify credentials not configured in environment variables.")

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "client_secret": settings.SPOTIFY_CLIENT_SECRET
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                settings.SPOTIFY_TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code != 200:
                logger.error("Spotify token exchange failed with status %d: %s", resp.status_code, resp.text)
                raise ValueError(f"Spotify authentication failed: {resp.json().get('error_description', 'Unknown error')}")
            return resp.json()

    @staticmethod
    async def refresh_access_token(session_id: str, refresh_token: str) -> str:
        """Refreshes an expired access token using the refresh token."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "client_secret": settings.SPOTIFY_CLIENT_SECRET
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                settings.SPOTIFY_TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code != 200:
                logger.error("Spotify token refresh failed with status %d", resp.status_code)
                raise ValueError("Spotify session expired or revoked. Please re-authenticate.")

            data = resp.json()
            new_access_token = data.get("access_token")
            new_refresh = data.get("refresh_token", refresh_token)
            expires_in = data.get("expires_in", 3600)

            session = get_session(session_id)
            user_id = session.get("spotify_user_id") if session else None
            save_session(session_id, new_access_token, new_refresh, expires_in, user_id)
            return new_access_token

    @classmethod
    async def get_valid_access_token(cls, session_id: str) -> str:
        """Retrieves a valid access token for the session, refreshing if necessary."""
        session = get_session(session_id)
        if not session or not session.get("access_token"):
            raise ValueError("No active Spotify session found. Please connect your Spotify account.")

        expires_at = session.get("token_expires_at", 0)
        now = datetime.now().timestamp()

        # If expired or expiring within 60 seconds, refresh
        if now >= (expires_at - 60):
            refresh_token = session.get("refresh_token")
            if not refresh_token:
                raise ValueError("Session token expired and no refresh token available.")
            return await cls.refresh_access_token(session_id, refresh_token)

        return session["access_token"]

    @classmethod
    async def get_recently_played_tracks(cls, session_id: str) -> Tuple[List[SpotifyTrack], bool]:
        """
        Retrieves the 10 most recently played tracks for the session.
        Enforces rule: fetched at most once per user per calendar day (APP_TIMEZONE).
        Returns: (tracks: List[SpotifyTrack], is_cached: bool)
        """
        today_str = settings.get_current_date_str()

        # Check database cache for today
        cached_data = get_cached_spotify_history(session_id, today_str)
        if cached_data:
            logger.info("Reusing cached Spotify listening history for date %s", today_str)
            tracks = [SpotifyTrack(**item) for item in cached_data]
            return tracks, True

        # Fetch from Spotify API
        access_token = await cls.get_valid_access_token(session_id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"limit": 10}
            resp = await client.get(settings.SPOTIFY_RECENTLY_PLAYED_URL, headers=headers, params=params)

            if resp.status_code == 401:
                # Retry once after refreshing token
                session = get_session(session_id)
                if session and session.get("refresh_token"):
                    access_token = await cls.refresh_access_token(session_id, session["refresh_token"])
                    headers = {"Authorization": f"Bearer {access_token}"}
                    resp = await client.get(settings.SPOTIFY_RECENTLY_PLAYED_URL, headers=headers, params=params)

            if resp.status_code != 200:
                logger.error("Failed to fetch recently played tracks from Spotify (%d): %s", resp.status_code, resp.text)
                raise ValueError(f"Spotify API error ({resp.status_code}): Could not retrieve listening history.")

            data = resp.json()
            items = data.get("items", [])

            if not items:
                raise ValueError("No recently played tracks found in your Spotify account. Listen to a few songs first!")

            parsed_tracks: List[SpotifyTrack] = []
            for item in items:
                track = item.get("track", {})
                album = track.get("album", {})
                images = album.get("images", [])
                image_url = images[0]["url"] if images else None
                artist_names = [a.get("name", "Unknown Artist") for a in track.get("artists", [])]
                played_at = item.get("played_at")
                spotify_url = track.get("external_urls", {}).get("spotify")

                parsed_tracks.append(SpotifyTrack(
                    id=track.get("id", str(secrets.token_hex(6))),
                    name=track.get("name", "Unknown Track"),
                    artists=artist_names,
                    album=album.get("name", "Unknown Album"),
                    album_art_url=image_url,
                    played_at=played_at,
                    spotify_url=spotify_url
                ))

            # Cache the 10 tracks for today in SQLite
            save_cached_spotify_history(session_id, today_str, [t.model_dump() for t in parsed_tracks])
            logger.info("Fetched and cached %d recently played tracks from Spotify for %s", len(parsed_tracks), today_str)

            return parsed_tracks, False

spotify_service = SpotifyService()
