---
title: "Feels: Translating Your Spotify Soundtrack into Real Outdoor Places with Local AI and SerpApi"
published: false
tags: ["hf26challenge", "opensource", "devchallenge"]
canonical_url: false
cover_image: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1200&q=80"
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

## What I Built
Like many developers, I spend hours locked in a sensory bubble at my desk with noise-canceling headphones on, cycling through music while deep in code. Over time, I noticed something undeniable about my daily Spotify queue: my listening history serves as an unfiltered mirror of my mental state and fatigue. When hunting subtle bugs or sprinting against deadlines, my queue naturally shifts to driving, high-tempo electronica. When unwinding after a long refactoring session or mapping system architecture, it settles into minimalist acoustic or atmospheric ambient soundscapes:

```text
Session Window (Last 10 Tracks):
- M83: Midnight City -> 105 BPM, expansive synth wave, high kinetic momentum
- Justice: Genesis -> 117 BPM, distorted analog bass, aggressive forward drive
- The xx: Intro -> 100 BPM, minimalist reverberation, steady contemplative pace
- The Prodigy: Breathe -> 130 BPM, breakbeat rhythm, peak adrenaline burst
- Woodkid: Run Boy Run -> 132 BPM, marching orchestral drums, surging forward drive
```

Streaming algorithms take this behavioral data and use it to feed more screen addiction, building autoplay queues engineered to keep you in your chair. The moment you push your commits, you close your editor only to open social feeds or video streams instead of getting fresh air.

I built **Feels** to turn that dynamic around: using your soundtrack as a natural bridge to step away from your desk and reconnect with the outdoors.

**Feels** is a web application that takes your recent Spotify listening session and interprets its acoustic cadence, energy density, and emotional texture using an open-weight model running locally on your hardware. Rather than trapping you in a conversational chatbot loop, it acts as an environmental scout. It maps your sonic state to geographic search intents, then uses **SerpApi's Google Maps engine** to find three verified real-world outdoor destinations - such as elevated ridgeline trails, shaded forest loops, or tranquil lakeside parks. Each spot includes verified user ratings, review counts, photos, a grounded explanation of why it fits your current soundtrack, and one-click Google Maps directions.

To ensure the screen stays the shortest part of the experience, the application enforces a strict cap of 15 refreshes per day. You check your curated spots, pick a trail, shut the laptop, and head outside.

## Demo

Here is a walkthrough of Feels in action, showing the Spotify authorization, the live four-stage processing indicator, and the resulting outdoor trail cards:

![Feels Project Demo](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/2r1880ndjno3ilb7esdt.gif)

## Code
{% github prathamanvekar/feels %}

## How I Built It
The system is designed as an end-to-end pipeline connecting audio streaming telemetry, private on-device reasoning, and grounded spatial exploration. When users open the app, a real-time four-stage status pipeline visualizes the progress as tracks are fetched, analyzed on-device, queried spatially, and curated:

![Feels Architecture Diagram](https://raw.githubusercontent.com/prathamanvekar/feels/main/architecture.png)

Data ingestion begins with the **Spotify Web API**, authenticating users via OAuth 2.0 with the `user-read-recently-played` scope. Rather than polling continuously, Feels retrieves your ten most recently played tracks at most once per calendar day. The backend extracts essential track attributes, artist metadata, and timestamps to evaluate pacing and acoustic density while keeping external requests to a minimum. These tracks are hashed and stored in an embedded SQLite database (`feels.db`), ensuring that subsequent refreshes throughout the day never spam Spotify servers.

To translate raw music tracks into an outdoor setting, Feels runs **Qwen 2.5 Coder 7B** locally through **Ollama** on localhost port 11434. Instead of open-ended conversational completions, the model is constrained to output a strict JSON schema containing acoustic energy levels, dominant emotional descriptors, and targeted spatial search queries:

```python
# Querying local Ollama with JSON schema enforcement and defensive extraction
payload = {
    "model": "qwen2.5-coder:7b",
    "prompt": f"{ENVIRONMENTAL_PSYCHOLOGY_PROMPT}\n\nRecent listening session:\n{tracklist_text}",
    "stream": False,
    "format": "json",
    "options": {"temperature": 0.35, "top_p": 0.9, "num_predict": 700},
}
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post("http://127.0.0.1:11434/api/generate", json=payload)
    analysis = extract_and_validate_json(response.json().get("response", ""))
```

Those environmental queries feed directly into **SerpApi's Google Maps engine** to retrieve genuine physical places with verified ratings, reviews, and geographic coordinates. The SQLite cache deduplicates visited spots so each refresh rotates to fresh outdoor locations. For cloud hosting and continuous deployment, Feels includes a native `render.yaml` blueprint, allowing it to deploy seamlessly to **Render** as a Python web service with automatic dependency installation, persistent environment variables, and live health monitoring via `/api/health`.

## Why Does Open Innovation Matter?
Listening history is personal behavioral telemetry. What someone plays during late-night debugging or high-pressure sprints reflects their emotional state, stress levels, and daily habits. Routing raw listening history to third-party commercial AI providers exposes private behavioral patterns to corporate tracking pipelines. Running an open-weight model locally ensures that private listening data never leaves the developer's laptop, transmitting only generalized, non-identifying outdoor search terms to map services.

Open innovation also eliminates recurring token anxiety. When small personal utilities depend on metered cloud APIs, every casual refresh incurs a monetary penalty. Running open-weight models on consumer hardware provides predictable, deterministic inference at zero marginal cost, enabling sustainable tools that cost nothing to operate.

Finally, outdoor exploration often takes place near hill ridgelines, nature sanctuaries, and forest paths where mobile reception is weak or unavailable. Because Feels combines local Ollama inference with persistent SQLite caching, the core mood profiling and trail guidance continue to function smoothly even when disconnected from the network.

## My Agent Session
{% agent_session 679 %}

## Prize Categories
Best Use of Render
