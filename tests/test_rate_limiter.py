import pytest
import sqlite3
import os
import concurrent.futures
from unittest.mock import patch

from app.config import settings
from app.database import init_db, get_db_connection
from app.services.rate_limiter import RateLimiter

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Sets up an isolated SQLite test database for rate limit tests."""
    test_db_path = str(tmp_path / "test_rate_limits.db")
    with patch.object(settings, "DATABASE_PATH", test_db_path):
        with patch.object(settings, "USER_DAILY_REFRESH_LIMIT", 15):
            with patch.object(settings, "SERPAPI_DAILY_BUDGET", 15):
                init_db()
                yield test_db_path

def test_user_refresh_limit_under_threshold():
    session_id = "test_user_session_1"
    
    # Refresh 1
    allowed, used, remaining = RateLimiter.attempt_user_refresh(session_id)
    assert allowed is True
    assert used == 1
    assert remaining == 14

    # Refresh 2
    allowed, used, remaining = RateLimiter.attempt_user_refresh(session_id)
    assert allowed is True
    assert used == 2
    assert remaining == 13

def test_user_refresh_limit_exhaustion():
    session_id = "test_user_session_exhaust"
    
    # Exhaust 15 refreshes
    for i in range(1, 16):
        allowed, used, remaining = RateLimiter.attempt_user_refresh(session_id)
        assert allowed is True
        assert used == i
        assert remaining == (15 - i)
        
    # 16th refresh should be rejected
    allowed, used, remaining = RateLimiter.attempt_user_refresh(session_id)
    assert allowed is False
    assert used == 15
    assert remaining == 0

def test_serpapi_budget_tracking():
    # Attempt 1
    allowed, used, remaining = RateLimiter.attempt_serpapi_request()
    assert allowed is True
    assert used == 1
    assert remaining == 14

    status = RateLimiter.get_serpapi_budget_status()
    assert status["used_count"] == 1
    assert status["remaining_budget"] == 14
    assert status["can_make_request"] is True

def test_serpapi_budget_exhaustion():
    # Exhaust all 15 SerpAPI requests
    for i in range(1, 16):
        allowed, used, remaining = RateLimiter.attempt_serpapi_request()
        assert allowed is True
        assert used == i

    # 16th request must be rejected
    allowed, used, remaining = RateLimiter.attempt_serpapi_request()
    assert allowed is False
    assert used == 15
    assert remaining == 0
    
    status = RateLimiter.get_serpapi_budget_status()
    assert status["can_make_request"] is False

def test_concurrent_user_refreshes_prevent_overshoot():
    session_id = "test_concurrent_user"
    
    def try_refresh():
        return RateLimiter.attempt_user_refresh(session_id)

    # Launch 25 concurrent threads attempting to refresh
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_refresh) for _ in range(25)]
        results = [f.result() for f in futures]

    # Exactly 15 should have succeeded (allowed=True), 10 should have been rejected (allowed=False)
    allowed_count = sum(1 for r in results if r[0] is True)
    rejected_count = sum(1 for r in results if r[0] is False)

    assert allowed_count == 15
    assert rejected_count == 10
