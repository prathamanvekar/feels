# Feels 🌿

> **A soundtrack for getting out of your head and into the world.**  
> Built for the **Hacktoberfest 2026 Open-Source AI Challenge: Week 1 ("Touch Grass" Theme)**  
> Tag: `#hf26challenge` • Partner Category: **Best Use of SerpApi**

---

## 1. Executive Summary

**Feels** is a local, privacy-first web application that bridges personal music listening patterns with physical outdoor exploration in **Pune, Maharashtra, India**. 

Instead of generic chatbot chats or superficial algorithmic genre tags, Feels connects to your Spotify listening history (fetching your 10 most recent tracks at most once per calendar day) and hands the session directly to a **locally running open-weight large language model (`qwen2.5-coder:7b` via Ollama)**.

The local AI synthesizes the emotional cadence, tempo, and acoustic atmosphere of your session into a structured outdoor mood profile, which is then grounded in real-world spaces via **SerpAPI** and verified Pune topography (ridge trails like Vetal Tekdi, forest reserves like Taljai, lake sanctuaries like Pashan, or heritage arboretums like Empress Garden). 

**The goal is intentional:** the screen exists solely to help you pick a trail or park, provide directions, and get you outside.

---

## 2. Why Open Innovation & Local AI Matters

In closed commercial AI architectures:
1. **Intimate personal taste leaves your device:** A user's music history reveals emotional states, daily routines, vulnerabilities, and focus habits. Routing raw listening history to third-party proprietary LLM providers exposes private behavioral data. Feels runs **100% of listening interpretation on your laptop via Ollama**. Only anonymized spatial search terms (e.g. `ridge trail nature viewpoint Pune`) are sent to external search providers.

2. **Deterministic, zero-marginal-cost inference:** By running open-weight `qwen2.5-coder:7b` locally, inference costs $0.00 in cloud tokens.
3. **Offline Cognition:** If you're on a trail with spotty cellular reception or working offline, the mood profiling and verified regional cache work completely without internet access.
4. **Reproducibility & Weight Sovereignty:** No sudden deprecation of commercial model versions or unpredictable prompt drift.

---

## 3. System Architecture & Data Flow

```mermaid
flowchart TD
    subgraph Browser ["Frontend (Editorial Neobrutalism UI)"]
        UI["Web App (Vanilla CSS + HTML5)"]
        QuotaDisplay["Live Refresh Quota (15/Day)"]
    end

    subgraph Backend ["FastAPI Local Backend (:8000)"]
        AuthRoute["/auth/login & /auth/callback"]
        RecRoute["/api/recommendations & /api/refresh"]
        RateLimit["Rate Limiter (SQLite Atomic Locks)"]
        DB[(Local SQLite Store)]
    end

    subgraph PrivateAI ["Private Local On-Device AI"]
        Ollama["Ollama Engine (:11434)"]
        Qwen["qwen2.5-coder:7b (Open-Weight)"]
    end

    subgraph ExternalServices ["External Web Services"]
        Spotify["Spotify Web API (user-read-recently-played)"]
        SerpAPI["SerpAPI (Google Maps Pune Search)"]
    end

    UI -->|1. OAuth Login| AuthRoute
    AuthRoute -->|Exchange Auth Code| Spotify
    Spotify -->|2. Fetch 10 Tracks (Max 1/Day)| RecRoute
    RecRoute -->|Cache Tracks in DB| DB

    RecRoute -->|3. Send Track Metadata Only| Ollama
    Ollama -->|Run Inference| Qwen
    Qwen -->|4. Structured JSON Mood Profile| RecRoute

    RecRoute -->|5. Rate-Limited Search (Max 15/Day)| SerpAPI
    SerpAPI -->|Real Coordinates & Reviews| RecRoute
    RecRoute -->|Cache Queries & Deduplicate| DB

    RecRoute -->|6. Render Curated Cards & Directions| UI
    RateLimit -->|Persist Usage Counters| DB
```

---

## 4. Design Philosophy & Visual Aesthetics

Inspired by contemporary botanical neobrutalism and editorial festival typography (reference: Green Roots / Zurich):
- **Editorial Typography:** Google Fonts `Fraunces` (warm, high-contrast serif headlines), `Space Grotesk` (technical mono labels and stats), and `Plus Jakarta Sans` (legible body copy).
- **Color Palette:** Warm oatmeal paper background (`#F4F6EE`), deep forest ink (`#142F20`), acid lime highlights (`#B8F03E`), and terracotta accents (`#F15A24`).
- **Neobrutalist Precision:** 2px solid borders, deliberate 4px offset hard shadows, circular stamp emblems, arched photo masks, and tactile interactive feedback.
- **No Clutter:** Avoids generic purple SaaS gradients, floating blobs, and emoji soup.

---

## 5. Daily Request Budgets & Rate Limits

Feels enforces two independent, persistent rate limits evaluated against the **Asia/Kolkata** calendar day (`YYYY-MM-DD`):


| Scope | Daily Limit | Persistence | Behavior on Exhaustion |
| :--- | :---: | :---: | :--- |
| **User Refresh Limit** | **15 refreshes / day** | SQLite `user_refresh_limits` | Rejects with `HTTP 429`. UI displays remaining countdown until midnight reset. |
| **SerpAPI Request Budget** | **15 searches / day** | SQLite `serpapi_budget_limits` | Searches fall back to cached results & verified Pune outdoor index without breaking. |
| **Spotify History Fetch** | **1 fetch / day** | SQLite `spotify_history_cache` | Cached for the calendar day; recommendation refreshes never hit Spotify repeatedly. |

---

## 6. Prerequisites

1. **Python 3.10+** (Tested on Python 3.14.3)
2. **Ollama** installed on your laptop ([ollama.com](https://ollama.com))
3. The open-weight model:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
4. **Spotify Developer Account** ([developer.spotify.com](https://developer.spotify.com/dashboard))
5. *(Optional for live web search)* **SerpAPI API Key** ([serpapi.com](https://serpapi.com)) — Free tier includes 100 searches/month.

---

## 7. Setup & Local Installation

### Step 1: Clone and Navigate
```bash
cd "c:\Users\prath\Desktop\LOCKIN\dev\hacktober\second week"
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Spotify Developer Dashboard
SPOTIFY_CLIENT_ID="your_spotify_client_id"
SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
SPOTIFY_REDIRECT_URI="http://127.0.0.1:8000/auth/callback"

# SerpAPI
SERPAPI_API_KEY="your_serpapi_api_key"
SERPAPI_DAILY_BUDGET=15
USER_DAILY_REFRESH_LIMIT=15

# Timezone & Local AI
APP_TIMEZONE="Asia/Kolkata"
OLLAMA_BASE_URL="http://127.0.0.1:11434"
OLLAMA_MODEL="qwen2.5-coder:7b"
```

### Step 3: Spotify Developer Dashboard Configuration
1. Open [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create an App (or select your existing app).
3. In **Settings**, add the exact Redirect URI:
   ```
   http://127.0.0.1:8000/auth/callback
   ```
4. Save changes.

### Step 4: Ensure Ollama is Running
Start the local Ollama server if it is not already running:
```bash
ollama serve
```
Verify the model is ready:
```bash
ollama list
```

### Step 5: Start Feels
Run the FastAPI application via Uvicorn:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Landing Page:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Main App:** [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)

*(Connecting Spotify will automatically redirect you to `/app`, where you'll see the 4-stage processing progress before the curated recommendations are rendered).*


---

## 8. Running Automated Tests

All tests are implemented using `pytest` with isolated in-memory SQLite fixtures and thread-safety tests:
```bash
python -m pytest tests -v
```

Test coverage includes:
- `test_rate_limiter.py`: 15-refresh cap, atomic thread-safe locking, SerpAPI request budget, and overshoot protection under 25 concurrent threads.
- `test_ai_service.py`: JSON schema validation, markdown block stripping, track fingerprinting, and malformed model fallback recovery.
- `test_search_service.py`: Query normalization, query caching, verified Pune dataset integrity, and deduplication across consecutive refreshes.
- `test_api_integration.py`: OAuth status routes, HTTP 429 rate limit responses, preview demo test fixtures, and HTML delivery.

---

## 9. Troubleshooting

### 1. Spotify OAuth "INVALID_CLIENT: Invalid redirect URI"
- **Cause:** The redirect URI registered in Spotify Dashboard does not match `http://127.0.0.1:8000/auth/callback`.
- **Fix:** In Spotify Developer Dashboard > App Settings > Redirect URIs, ensure `http://127.0.0.1:8000/auth/callback` is saved with exact trailing slashes and port.

### 2. Ollama Connection Error (`503 Service Unavailable`)
- **Cause:** Ollama service is not running or port `11434` is blocked.
- **Fix:** Open a terminal and run `ollama serve`. Verify with `curl http://127.0.0.1:11434/api/tags`.

### 3. "No recently played tracks found"
- **Cause:** Your Spotify account hasn't listened to tracks recently or is a fresh account.
- **Fix:** Play 2-3 tracks in Spotify, or use the **"⚡ Try Sample Session (Instant Demo)"** button on the landing page to test the local Qwen model and SerpAPI pipeline with representative test fixtures.

### 4. SerpAPI Daily Budget Exhaustion
- **Cause:** All 15 external searches for the calendar day have been consumed.
- **Fix:** Feels automatically falls back to cached queries and the verified Pune outdoor index. The budget resets automatically at midnight in `Asia/Kolkata`.

### 5. Disconnecting Account & Data Purge
- Click the **"Disconnect"** button in the header or floating bottom bar. This immediately invokes `POST /auth/disconnect`, deleting your session cookies, SQLite OAuth tokens, and cached listening history.

