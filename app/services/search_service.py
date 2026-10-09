import urllib.parse
import hashlib
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.config import settings
from app.database import (
    get_cached_serpapi_search,
    save_cached_serpapi_search,
    record_served_recommendations,
    get_recently_served_place_ids
)
from app.services.rate_limiter import rate_limiter
from app.models.schemas import PlaceRecommendation, MoodProfile

logger = logging.getLogger("feels.search")

# Curated, verified outdoor Pune destinations for graceful offline fallback
# and seed discovery. All locations are real places in Pune, Maharashtra.
PUNE_VERIFIED_OUTDOOR_PLACES: List[Dict[str, Any]] = [
    {
        "id": "pune-vetal-tekdi",
        "title": "Vetal Tekdi & ARAI Hills",
        "neighborhood": "Kothrud / Senapati Bapat Road",
        "category": "High-Elevation Trail & Ridge",
        "address": "Paud Road, Kelewadi, Kothrud, Pune, Maharashtra 411038",
        "rating": 4.6,
        "reviews_count": 5200,
        "photo_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "High wind, dirt tracks, panoramic skyline views, ideal for trail running and clearing your head.",
        "best_for_energy": ["High", "Medium"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Vetal+Tekdi+Pune"
    },
    {
        "id": "pune-taljai-hills",
        "title": "Taljai Hills Forest Reserve",
        "neighborhood": "Sahakar Nagar / Dhankawadi",
        "category": "Woodland Trail & Biodiversity Park",
        "address": "Taljai Hills, Sahakar Nagar, Pune, Maharashtra 411009",
        "rating": 4.5,
        "reviews_count": 3800,
        "photo_url": "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Dense green canopies, peafowl calls, gentle dirt paths, and quiet shaded groves.",
        "best_for_energy": ["Medium", "Low"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Taljai+Hills+Pune"
    },
    {
        "id": "pune-pashan-lake",
        "title": "Pashan Lake Sanctuary",
        "neighborhood": "Pashan / Baner",
        "category": "Waterfront Wetland & Bird Walk",
        "address": "Pashan, Pune, Maharashtra 411021",
        "rating": 4.3,
        "reviews_count": 2100,
        "photo_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Water reflections, migratory bird watching, gentle evening breeze, suited to reflective contemplation.",
        "best_for_energy": ["Low", "Medium"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Pashan+Lake+Pune"
    },
    {
        "id": "pune-empress-garden",
        "title": "Empress Botanical Garden",
        "neighborhood": "Pune Camp / Ghorpadi",
        "category": "Heritage Arboretum & Shaded Lawns",
        "address": "Near Race Course, Ghorpadi, Pune, Maharashtra 411001",
        "rating": 4.4,
        "reviews_count": 4900,
        "photo_url": "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Century-old banyan trees, quiet shaded glades, soft grass to sit on, calm acoustic environment.",
        "best_for_energy": ["Low"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Empress+Garden+Pune"
    },
    {
        "id": "pune-okayama-garden",
        "title": "Pune Okayama Friendship Garden (Pu La Deshpande)",
        "neighborhood": "Sinhagad Road / Dattawadi",
        "category": "Japanese Stroll Garden",
        "address": "Sinhagad Road, Dattawadi, Pune, Maharashtra 411030",
        "rating": 4.5,
        "reviews_count": 7600,
        "photo_url": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Meandering canals, wooden footbridges, natural stonework, highly structured tranquil walking.",
        "best_for_energy": ["Low", "Medium"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Pune+Okayama+Friendship+Garden+Pune"
    },
    {
        "id": "pune-sinhagad-fort",
        "title": "Sinhagad Fort Ridge",
        "neighborhood": "Sinhagad Ghat / Haveli",
        "category": "Mountain Fortress & Dramatic Ascent",
        "address": "Sinhagad Ghat Road, Thoptewadi, Pune, Maharashtra 411025",
        "rating": 4.6,
        "reviews_count": 14200,
        "photo_url": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Steep clifftops, swirling mountain clouds, intense leg workout, raw historic grandeur.",
        "best_for_energy": ["High"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Sinhagad+Fort+Pune"
    },
    {
        "id": "pune-khadakwasla-dam",
        "title": "Khadakwasla Dam Shoreline",
        "neighborhood": "Khadakwasla",
        "category": "Open Reservoir Waterfront",
        "address": "Khadakwasla, Pune, Maharashtra 411024",
        "rating": 4.4,
        "reviews_count": 9100,
        "photo_url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Expansive horizon, lapping water, fresh air, wide sunset skies over the Sahyadri ranges.",
        "best_for_energy": ["Medium", "High"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Khadakwasla+Dam+Pune"
    },
    {
        "id": "pune-osho-park",
        "title": "Osho Teerth Park & Nala Garden",
        "neighborhood": "Koregaon Park",
        "category": "Zen Ecological Sanctuary",
        "address": "19, Sanaswadi, Koregaon Park, Pune, Maharashtra 411001",
        "rating": 4.5,
        "reviews_count": 2800,
        "photo_url": "https://images.unsplash.com/photo-1518495973542-4542c06a5843?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Bamboo groves, running stream, peaceful wooden walkways, secluded urban nature sanctuary.",
        "best_for_energy": ["Low"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Osho+Teerth+Park+Pune"
    },
    {
        "id": "pune-baner-hill",
        "title": "Baner Hill & Tukai Devi Trail",
        "neighborhood": "Baner",
        "category": "Sunset Vista & Urban Hill Trail",
        "address": "Baner Hill, Baner, Pune, Maharashtra 411045",
        "rating": 4.5,
        "reviews_count": 3200,
        "photo_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Breezy ridge line, quick steep climb from city level, golden hour sunset views across Western Pune.",
        "best_for_energy": ["High", "Medium"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Baner+Hill+Pune"
    },
    {
        "id": "pune-bund-garden",
        "title": "Bund Garden (Mahatma Gandhi Udyan)",
        "neighborhood": "Sangamvadi / Yerawada",
        "category": "Riverside Promenade",
        "address": "Bund Garden Rd, Sangamvadi, Pune, Maharashtra 411001",
        "rating": 4.2,
        "reviews_count": 4300,
        "photo_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=800&q=80",
        "vibe_descriptor": "Mula-Mutha riverfront trees, historic stone bridge views, breezy evening strolling.",
        "best_for_energy": ["Low", "Medium"],
        "directions_url": "https://www.google.com/maps/search/?api=1&query=Bund+Garden+Pune"
    }
]

class SearchService:
    @staticmethod
    def normalize_query_key(query: str) -> str:
        clean = query.strip().lower()
        return hashlib.md5(clean.encode("utf-8")).hexdigest()

    @classmethod
    async def search_places_in_pune(
        cls,
        search_query: str,
        mood: MoodProfile
    ) -> List[Dict[str, Any]]:
        """
        Executes a localized SerpAPI Google Maps search for outdoor spots in Pune.
        Adheres strictly to the SerpAPI daily budget and checks cache first.
        """
        query_key = cls.normalize_query_key(search_query)
        today_str = settings.get_current_date_str()

        # 1. Check database cache for this query today
        cached_results = get_cached_serpapi_search(query_key, today_str)
        if cached_results:
            logger.info("Using cached SerpAPI results for query: '%s'", search_query)
            return cached_results

        # 2. Check SerpAPI API key
        if not settings.SERPAPI_API_KEY or settings.SERPAPI_API_KEY.startswith("your_"):
            logger.info("SerpAPI key not configured. Using verified Pune outdoor dataset.")
            return []

        # 3. Check and increment daily SerpAPI budget
        allowed, used_count, remaining_budget = rate_limiter.attempt_serpapi_request()
        if not allowed:
            logger.warning("SerpAPI daily budget exhausted (%d/%d used). Falling back to cached results.",
                           used_count, settings.SERPAPI_DAILY_BUDGET)
            return []

        # 4. Make external request to SerpAPI
        full_query = f"{search_query} Pune Maharashtra"
        params = {
            "engine": "google_maps",
            "q": full_query,
            "hl": "en",
            "gl": "in",
            "api_key": settings.SERPAPI_API_KEY
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("https://serpapi.com/search.json", params=params)
                if resp.status_code != 200:
                    logger.error("SerpAPI error (%d): %s", resp.status_code, resp.text)
                    return []

                data = resp.json()
                local_results = data.get("local_results", [])
                normalized_items: List[Dict[str, Any]] = []

                for item in local_results:
                    title = item.get("title")
                    if not title:
                        continue

                    place_id = f"serp-{hashlib.md5(title.encode('utf-8')).hexdigest()[:8]}"
                    address = item.get("address", "Pune, Maharashtra")
                    rating = item.get("rating")
                    reviews = item.get("reviews")
                    category = item.get("type", "Outdoor Destination")
                    photo = item.get("thumbnail") or "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"
                    maps_link = item.get("link") or f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(title + ' Pune')}"

                    normalized_items.append({
                        "id": place_id,
                        "title": title,
                        "neighborhood": address.split(",")[-2].strip() if "," in address else "Pune",
                        "category": category,
                        "address": address,
                        "rating": float(rating) if rating else None,
                        "reviews_count": int(reviews) if reviews else None,
                        "photo_url": photo,
                        "vibe_descriptor": f"Real-world open space identified via SerpAPI matching '{search_query}'.",
                        "directions_url": maps_link,
                        "source": "serpapi"
                    })

                # Save in cache
                if normalized_items:
                    save_cached_serpapi_search(query_key, today_str, normalized_items)
                return normalized_items

        except Exception as e:
            logger.error("SerpAPI request failed: %s", e)
            return []

    @classmethod
    async def discover_recommendations(
        cls,
        session_id: str,
        mood: MoodProfile,
        limit: int = 3
    ) -> List[PlaceRecommendation]:
        """
        Discovers and curates suitable places in Pune matching the listening mood.
        Deduplicates against recently served places and prioritizes high-relevance matches.
        """
        recently_served = get_recently_served_place_ids(session_id, limit=15)
        candidates: List[Dict[str, Any]] = []

        # Step A: Attempt SerpAPI search using Qwen's targeted search queries
        for query in mood.search_intents[:1]:  # Bounded to 1 targeted search to conserve budget
            serp_results = await cls.search_places_in_pune(query, mood)
            for item in serp_results:
                candidates.append(item)

        # Step B: If candidates < 5, blend with curated Pune outdoor destinations suited to this energy level
        suitable_verified = [
            p for p in PUNE_VERIFIED_OUTDOOR_PLACES
            if mood.energy_level in p.get("best_for_energy", ["Medium"])
        ]
        if not suitable_verified:
            suitable_verified = PUNE_VERIFIED_OUTDOOR_PLACES

        candidates.extend(suitable_verified)

        # Step C: Deduplicate candidates by title / ID
        seen_ids = set()
        unique_candidates: List[Dict[str, Any]] = []
        for c in candidates:
            cid = c.get("id") or c.get("title")
            if cid not in seen_ids:
                seen_ids.add(cid)
                unique_candidates.append(c)

        # Step D: Prioritize candidates that haven't been served recently in this session
        unseen = [c for c in unique_candidates if c["id"] not in recently_served]
        if len(unseen) >= limit:
            selected_candidates = unseen[:limit]
        else:
            # Take all available unseen candidates first, then backfill from previously served
            seen_backfill = [c for c in unique_candidates if c["id"] in recently_served]
            selected_candidates = (unseen + seen_backfill)[:limit]

        # Step E: Generate grounded explanations using local Qwen for selected places
        from app.services.ai_service import ai_service

        recommendations: List[PlaceRecommendation] = []
        served_ids: List[str] = []

        for item in selected_candidates:
            # Generate grounded reason
            why_fits = await ai_service.generate_grounded_explanation(
                place_title=item["title"],
                place_category=item.get("category", "Outdoor Area"),
                place_neighborhood=item.get("neighborhood", "Pune"),
                mood=mood
            )

            rec = PlaceRecommendation(
                id=item["id"],
                title=item["title"],
                neighborhood=item.get("neighborhood", "Pune"),
                category=item.get("category", "Outdoor Spot"),
                address=item.get("address"),
                rating=item.get("rating"),
                reviews_count=item.get("reviews_count"),
                photo_url=item.get("photo_url"),
                why_it_fits=why_fits,
                vibe_descriptor=item.get("vibe_descriptor"),
                directions_url=item.get("directions_url", f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(item['title'] + ' Pune')}"),
                source=item.get("source", "cached")
            )
            recommendations.append(rec)
            served_ids.append(rec.id)

        # Record served places for rotation
        record_served_recommendations(session_id, served_ids)

        return recommendations

search_service = SearchService()
