import sqlite3
import json
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime
from app.config import settings

logger = logging.getLogger("feels.database")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initializes tables for tokens, caching, rate limits, and recommendations."""
    conn = get_db_connection()
    try:
        with conn:
            # Enable WAL mode for concurrency
            conn.execute("PRAGMA journal_mode=WAL;")

            # 1. User sessions & tokens
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    spotify_user_id TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expires_at REAL,
                    created_at REAL,
                    updated_at REAL
                );
            """)

            # 2. Spotify history cache (Enforces 1 fetch per user per calendar day)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spotify_history_cache (
                    session_id TEXT,
                    date_str TEXT,
                    tracks_json TEXT,
                    created_at REAL,
                    PRIMARY KEY (session_id, date_str)
                );
            """)

            # 3. AI Mood Analysis cache (Hash of 10 tracks -> structured mood profile)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_mood_cache (
                    tracks_hash TEXT PRIMARY KEY,
                    mood_json TEXT,
                    created_at REAL
                );
            """)

            # 4. User refresh limits (Max 15 per calendar day)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_refresh_limits (
                    session_id TEXT,
                    date_str TEXT,
                    refresh_count INTEGER DEFAULT 0,
                    updated_at REAL,
                    PRIMARY KEY (session_id, date_str)
                );
            """)

            # 5. SerpAPI external request budget limits
            conn.execute("""
                CREATE TABLE IF NOT EXISTS serpapi_budget_limits (
                    date_str TEXT PRIMARY KEY,
                    request_count INTEGER DEFAULT 0,
                    updated_at REAL
                );
            """)

            # 6. SerpAPI search query cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS serpapi_cache (
                    query_key TEXT,
                    date_str TEXT,
                    results_json TEXT,
                    created_at REAL,
                    PRIMARY KEY (query_key, date_str)
                );
            """)

            # 7. Served recommendations history (for smart rotation/deduplication)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS served_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    place_id TEXT,
                    served_at REAL
                );
            """)
        logger.info("Database initialized successfully at %s", settings.DATABASE_PATH)
    finally:
        conn.close()

# Session Management
def save_session(session_id: str, access_token: str, refresh_token: str, expires_in: int, spotify_user_id: Optional[str] = None) -> None:
    now = datetime.now().timestamp()
    expires_at = now + expires_in
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO user_sessions (session_id, spotify_user_id, access_token, refresh_token, token_expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    access_token=excluded.access_token,
                    refresh_token=COALESCE(excluded.refresh_token, user_sessions.refresh_token),
                    token_expires_at=excluded.token_expires_at,
                    spotify_user_id=COALESCE(excluded.spotify_user_id, user_sessions.spotify_user_id),
                    updated_at=excluded.updated_at;
            """, (session_id, spotify_user_id, access_token, refresh_token, expires_at, now, now))
    finally:
        conn.close()

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM user_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def delete_session_data(session_id: str) -> None:
    """Wipes all user data: tokens, cached history, served recommendations, and refresh counters."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM spotify_history_cache WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM user_refresh_limits WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM served_recommendations WHERE session_id = ?", (session_id,))
    finally:
        conn.close()

# Spotify Listening History Cache
def get_cached_spotify_history(session_id: str, date_str: str) -> Optional[List[Dict[str, Any]]]:
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT tracks_json FROM spotify_history_cache WHERE session_id = ? AND date_str = ?",
            (session_id, date_str)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["tracks_json"])
        return None
    finally:
        conn.close()

def save_cached_spotify_history(session_id: str, date_str: str, tracks: List[Dict[str, Any]]) -> None:
    now = datetime.now().timestamp()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO spotify_history_cache (session_id, date_str, tracks_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, date_str) DO UPDATE SET
                    tracks_json=excluded.tracks_json,
                    created_at=excluded.created_at;
            """, (session_id, date_str, json.dumps(tracks), now))
    finally:
        conn.close()

# AI Mood Cache
def get_cached_ai_mood(tracks_hash: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT mood_json FROM ai_mood_cache WHERE tracks_hash = ?", (tracks_hash,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["mood_json"])
        return None
    finally:
        conn.close()

def save_cached_ai_mood(tracks_hash: str, mood_data: Dict[str, Any]) -> None:
    now = datetime.now().timestamp()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO ai_mood_cache (tracks_hash, mood_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(tracks_hash) DO UPDATE SET
                    mood_json=excluded.mood_json,
                    created_at=excluded.created_at;
            """, (tracks_hash, json.dumps(mood_data), now))
    finally:
        conn.close()

# SerpAPI Cache
def get_cached_serpapi_search(query_key: str, date_str: str) -> Optional[List[Dict[str, Any]]]:
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT results_json FROM serpapi_cache WHERE query_key = ? AND date_str = ?",
            (query_key, date_str)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["results_json"])
        return None
    finally:
        conn.close()

def save_cached_serpapi_search(query_key: str, date_str: str, results: List[Dict[str, Any]]) -> None:
    now = datetime.now().timestamp()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO serpapi_cache (query_key, date_str, results_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(query_key, date_str) DO UPDATE SET
                    results_json=excluded.results_json,
                    created_at=excluded.created_at;
            """, (query_key, date_str, json.dumps(results), now))
    finally:
        conn.close()

# Recommendation Deduplication Tracking
def record_served_recommendations(session_id: str, place_ids: List[str]) -> None:
    now = datetime.now().timestamp()
    conn = get_db_connection()
    try:
        with conn:
            for pid in place_ids:
                conn.execute(
                    "INSERT INTO served_recommendations (session_id, place_id, served_at) VALUES (?, ?, ?)",
                    (session_id, pid, now)
                )
    finally:
        conn.close()

def get_recently_served_place_ids(session_id: str, limit: int = 20) -> List[str]:
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT place_id FROM served_recommendations
            WHERE session_id = ?
            ORDER BY served_at DESC LIMIT ?
        """, (session_id, limit))
        return [row["place_id"] for row in cursor.fetchall()]
    finally:
        conn.close()
