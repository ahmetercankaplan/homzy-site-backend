import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


COUNTRY_LABELS = {
    "GB": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
}

CITY_DATA = [
    {"city": "London", "country": "GB", "lat": 51.5074, "lng": -0.1278, "currency": "GBP"},
    {"city": "Manchester", "country": "GB", "lat": 53.4808, "lng": -2.2426, "currency": "GBP"},
    {"city": "Birmingham", "country": "GB", "lat": 52.4862, "lng": -1.8904, "currency": "GBP"},
    {"city": "Paris", "country": "FR", "lat": 48.8566, "lng": 2.3522, "currency": "EUR"},
    {"city": "Lyon", "country": "FR", "lat": 45.764, "lng": 4.8357, "currency": "EUR"},
    {"city": "Berlin", "country": "DE", "lat": 52.52, "lng": 13.405, "currency": "EUR"},
    {"city": "Munich", "country": "DE", "lat": 48.1351, "lng": 11.582, "currency": "EUR"},
]

AGENTS = [
    {"id": "agent-sarah", "name": "Sarah Johnson", "email": "sarah@homzy.com", "picture": "https://randomuser.me/api/portraits/women/1.jpg"},
    {"id": "agent-james", "name": "James Carter", "email": "james@homzy.com", "picture": "https://randomuser.me/api/portraits/men/2.jpg"},
    {"id": "agent-amelie", "name": "Amelie Laurent", "email": "amelie@homzy.com", "picture": "https://randomuser.me/api/portraits/women/3.jpg"},
    {"id": "agent-hans", "name": "Hans Mueller", "email": "hans@homzy.com", "picture": "https://randomuser.me/api/portraits/men/4.jpg"},
    {"id": "agent-ayse", "name": "Ayse Demir", "email": "ayse@homzy.com", "picture": "https://randomuser.me/api/portraits/women/5.jpg"},
]

PHOTOS = [
    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1200",
    "https://images.unsplash.com/photo-1470246973918-29a93221c455?w=1200",
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200",
    "https://images.unsplash.com/photo-1507089947368-19c1da9775ae?w=1200",
    "https://images.unsplash.com/photo-1501045661006-fcebe0257c3f?w=1200",
]

PLAN_SEEDS = [
    {
        "id": "plan-free",
        "name": "Free",
        "slug": "free",
        "monthly_price_cents": 0,
        "currency": "GBP",
        "max_active_listings": 1,
        "type": "individual",
        "features": ["1 active listing", "15 day listing life", "3 photos", "Basic visibility"],
    },
    {
        "id": "plan-standard",
        "name": "Standard",
        "slug": "standard",
        "monthly_price_cents": 999,
        "currency": "GBP",
        "max_active_listings": 3,
        "type": "individual",
        "features": ["3 active listings", "60 day listing life", "15 photos", "Better ranking"],
    },
    {
        "id": "plan-agent-starter",
        "name": "Agent Starter",
        "slug": "agent-starter",
        "monthly_price_cents": 2900,
        "currency": "GBP",
        "max_active_listings": 10,
        "type": "agent",
        "features": ["Basic stats", "Agent profile badge"],
    },
    {
        "id": "plan-agent-pro",
        "name": "Agent Pro",
        "slug": "agent-pro",
        "monthly_price_cents": 5900,
        "currency": "GBP",
        "max_active_listings": 30,
        "type": "agent",
        "features": ["Higher visibility", "Pro Agent badge"],
    },
    {
        "id": "plan-agency-unlimited",
        "name": "Agency Unlimited",
        "slug": "agency-unlimited",
        "monthly_price_cents": 9900,
        "currency": "GBP",
        "max_active_listings": 0,
        "type": "agent",
        "features": ["Unlimited listings", "Team access", "Featured Agency badge"],
    },
]


def _base_features(prop_type: str) -> List[str]:
    shared = ["High-Speed WiFi", "Smart Thermostat", "Double Glazing"]
    if prop_type == "flat":
        return shared + ["Elevator Access", "Concierge"]
    if prop_type == "house":
        return shared + ["Private Garden", "Driveway"]
    return shared + ["Compact Layout", "Co-working Desk"]


def generate_seed_properties(count: int = 50) -> List[Dict[str, Any]]:
    """Create deterministic but varied seed data."""
    properties: List[Dict[str, Any]] = []
    prop_types = ["flat", "house", "studio"]
    energy_ratings = ["A", "B", "C", None]

    for idx in range(count):
        city_meta = CITY_DATA[idx % len(CITY_DATA)]
        prop_type = prop_types[idx % len(prop_types)]
        agent = AGENTS[idx % len(AGENTS)]
        energy = energy_ratings[idx % len(energy_ratings)]

        bedrooms = 1 + (idx % 4)
        bathrooms = 1 + (idx % 2)
        size_m2 = 45 + (idx * 3)
        price_base = 750 + (idx * 45)
        price = price_base if city_meta["currency"] == "EUR" else price_base * 0.78

        availability_date = (datetime.now(timezone.utc) + timedelta(days=14 + idx)).date().isoformat()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=90)

        photos = PHOTOS[:3 + (idx % 2)]

        properties.append(
            {
                "id": str(uuid.uuid4()),
                "title": f"{city_meta['city']} {prop_type.title()} #{idx + 1}",
                "description": f"Light-filled {prop_type} in {city_meta['city']} with modern finishes, close to transport and amenities.",
                "price": round(price, 2),
                "currency": city_meta["currency"],
                "location": f"{city_meta['city']}, {COUNTRY_LABELS[city_meta['country']]}",
                "address": f"{10 + idx} Main Street, {city_meta['city']}",
                "coordinates": {"lat": city_meta["lat"], "lng": city_meta["lng"]},
                "size_m2": size_m2,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "property_type": prop_type,
                "furnished": idx % 2 == 0,
                "pets_allowed": idx % 3 == 0,
                "parking": idx % 4 != 1,
                "balcony_garden": idx % 2 == 0,
                "energy_rating": energy,
                "student_friendly": idx % 3 == 0,
                "availability_date": availability_date,
                "photos": photos,
                "photos_count": len(photos),
                "agent_info": agent,
                "features": _base_features(prop_type),
                "country": city_meta["country"],
                "city": city_meta["city"],
                "featured": idx < 8,
                "created_at": now.isoformat(),
                "status": "active",
                "expires_at": expires_at.isoformat(),
                "boost_expires_at": None,
                "spotlight_expires_at": None,
            }
        )

    return properties


PROPERTIES_DATA = generate_seed_properties()
