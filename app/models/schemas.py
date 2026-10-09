from typing import List, Optional
from pydantic import BaseModel, Field

class SpotifyTrack(BaseModel):
    id: str
    name: str
    artists: List[str]
    album: str
    album_art_url: Optional[str] = None
    played_at: Optional[str] = None
    spotify_url: Optional[str] = None

class MoodProfile(BaseModel):
    mood_title: str = Field(description="A poetic, evocative title for the listening mood (2-5 words)")
    mood_summary: str = Field(description="A concise synthesis of the emotional atmosphere and sonic texture")
    dominant_qualities: List[str] = Field(description="3-4 distinct musical and emotional qualities")
    energy_level: str = Field(description="Energy rating: Low, Medium, or High")
    suitable_outdoor_activities: List[str] = Field(description="Specific real-world outdoor activities suited to this mood")
    search_intents: List[str] = Field(description="1-2 targeted search queries for outdoor spots in Pune")
    reasoning: str = Field(description="Thoughtful explanation connecting the tracks to real-world spaces")

class PlaceRecommendation(BaseModel):
    id: str
    title: str
    neighborhood: str
    category: str
    address: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    photo_url: Optional[str] = None
    why_it_fits: str
    vibe_descriptor: Optional[str] = None
    directions_url: str
    source: str = "serpapi"

class RefreshQuotaStatus(BaseModel):
    daily_limit: int = 15
    used_count: int
    remaining_count: int
    date: str
    resets_at: str
    timezone: str = "Asia/Kolkata"
    can_refresh: bool

class RecommendationResponse(BaseModel):
    tracks: List[SpotifyTrack]
    mood_profile: MoodProfile
    places: List[PlaceRecommendation]
    quota: RefreshQuotaStatus
    is_cached_listening: bool
    is_refreshed: bool = False
    serpapi_budget_remaining: int
    message: Optional[str] = None

class AuthStatus(BaseModel):
    authenticated: bool
    spotify_user_id: Optional[str] = None
    has_cached_tracks: bool = False
    quota: RefreshQuotaStatus

class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    ollama_model: str
    database_ok: bool
    serpapi_configured: bool
    timezone: str
    current_date: str
