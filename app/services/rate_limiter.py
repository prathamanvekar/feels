import threading
from datetime import datetime
from typing import Tuple, Dict, Any
from app.config import settings
from app.database import get_db_connection

# Thread lock to serialize limit checks and atomic increments
_lock = threading.Lock()

class RateLimiter:
    @staticmethod
    def get_user_refresh_status(session_id: str) -> Dict[str, Any]:
        """Returns the current refresh status for the user for today."""
        date_str = settings.get_current_date_str()
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "SELECT refresh_count FROM user_refresh_limits WHERE session_id = ? AND date_str = ?",
                (session_id, date_str)
            )
            row = cursor.fetchone()
            used = row["refresh_count"] if row else 0
            limit = settings.USER_DAILY_REFRESH_LIMIT
            remaining = max(0, limit - used)

            return {
                "daily_limit": limit,
                "used_count": used,
                "remaining_count": remaining,
                "date": date_str,
                "resets_at": f"{date_str} 23:59:59 {settings.APP_TIMEZONE}",
                "timezone": settings.APP_TIMEZONE,
                "can_refresh": remaining > 0
            }
        finally:
            conn.close()

    @staticmethod
    def attempt_user_refresh(session_id: str) -> Tuple[bool, int, int]:
        """
        Atomically checks and increments the user-triggered refresh count.
        Returns: (allowed: bool, current_used_count: int, remaining_count: int)
        """
        date_str = settings.get_current_date_str()
        limit = settings.USER_DAILY_REFRESH_LIMIT
        now = datetime.now().timestamp()

        with _lock:
            conn = get_db_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        "SELECT refresh_count FROM user_refresh_limits WHERE session_id = ? AND date_str = ?",
                        (session_id, date_str)
                    )
                    row = cursor.fetchone()
                    current = row["refresh_count"] if row else 0

                    if current >= limit:
                        return False, current, 0

                    new_count = current + 1
                    conn.execute("""
                        INSERT INTO user_refresh_limits (session_id, date_str, refresh_count, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(session_id, date_str) DO UPDATE SET
                            refresh_count = excluded.refresh_count,
                            updated_at = excluded.updated_at;
                    """, (session_id, date_str, new_count, now))

                    remaining = max(0, limit - new_count)
                    return True, new_count, remaining
            finally:
                conn.close()

    @staticmethod
    def get_serpapi_budget_status() -> Dict[str, Any]:
        """Returns the current SerpAPI request budget status for today."""
        date_str = settings.get_current_date_str()
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "SELECT request_count FROM serpapi_budget_limits WHERE date_str = ?",
                (date_str,)
            )
            row = cursor.fetchone()
            used = row["request_count"] if row else 0
            budget = settings.SERPAPI_DAILY_BUDGET
            remaining = max(0, budget - used)

            return {
                "daily_budget": budget,
                "used_count": used,
                "remaining_budget": remaining,
                "date": date_str,
                "can_make_request": remaining > 0
            }
        finally:
            conn.close()

    @staticmethod
    def attempt_serpapi_request() -> Tuple[bool, int, int]:
        """
        Atomically checks and increments the SerpAPI request budget count.
        Returns: (allowed: bool, current_used_count: int, remaining_budget: int)
        """
        date_str = settings.get_current_date_str()
        budget = settings.SERPAPI_DAILY_BUDGET
        now = datetime.now().timestamp()

        with _lock:
            conn = get_db_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        "SELECT request_count FROM serpapi_budget_limits WHERE date_str = ?",
                        (date_str,)
                    )
                    row = cursor.fetchone()
                    current = row["request_count"] if row else 0

                    if current >= budget:
                        return False, current, 0

                    new_count = current + 1
                    conn.execute("""
                        INSERT INTO serpapi_budget_limits (date_str, request_count, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(date_str) DO UPDATE SET
                            request_count = excluded.request_count,
                            updated_at = excluded.updated_at;
                    """, (date_str, new_count, now))

                    remaining = max(0, budget - new_count)
                    return True, new_count, remaining
            finally:
                conn.close()

rate_limiter = RateLimiter()
