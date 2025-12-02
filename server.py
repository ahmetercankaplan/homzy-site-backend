from fastapi import FastAPI, APIRouter, HTTPException, Depends, Response, Cookie, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import stripe

from in_memory_db import InMemoryDB
from mock_data import PROPERTIES_DATA, PLAN_SEEDS

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.getenv('MONGO_URL')
DB_NAME = os.getenv('DB_NAME', 'homzy')
USE_IN_MEMORY_DB = os.getenv('USE_IN_MEMORY_DB', 'true').lower() == 'true'
ENABLE_DEV_AUTH = os.getenv('ENABLE_DEV_AUTH', 'true').lower() == 'true'
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
PADDLE_VENDOR_ID = os.getenv('PADDLE_VENDOR_ID')
PADDLE_API_KEY = os.getenv('PADDLE_API_KEY')
PADDLE_PUBLIC_KEY = os.getenv('PADDLE_PUBLIC_KEY')

client = None
if not USE_IN_MEMORY_DB and MONGO_URL:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    DATA_SOURCE = "mongodb"
else:
    db = InMemoryDB(PROPERTIES_DATA, PLAN_SEEDS)
    DATA_SOURCE = "in-memory"
    USE_IN_MEMORY_DB = True

# UK + EU Country Whitelist (ISO 3166-1 alpha-2)
ALLOWED_COUNTRIES = {
    'GB',  # United Kingdom
    # EU Members
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 
    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 
    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
}

app = FastAPI()
api_router = APIRouter(prefix="/api")

stripe.api_key = STRIPE_SECRET_KEY or ""

# Models
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "individual"
    plan_id: str = "plan-free"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Session(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Property(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    price: float
    currency: str
    location: str
    address: str
    coordinates: dict
    size_m2: float
    bedrooms: int
    bathrooms: int
    property_type: str
    furnished: bool
    pets_allowed: bool
    parking: bool
    balcony_garden: bool
    energy_rating: Optional[str] = None
    availability_date: str
    photos: List[str]
    agent_info: dict
    features: List[str]
    country: str
    city: str
    featured: bool = False
    status: str = "active"
    photos_count: int = 0
    expires_at: Optional[datetime] = None
    boost_expires_at: Optional[datetime] = None
    spotlight_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Favorite(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    property_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ViewingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    user_id: str
    name: str
    email: str
    phone: str
    message: Optional[str] = None
    preferred_date: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Input Models
class PropertyCreate(BaseModel):
    title: str
    description: str
    price: float
    currency: str
    location: str
    address: str
    coordinates: dict
    size_m2: float
    bedrooms: int
    bathrooms: int
    property_type: str
    furnished: bool
    pets_allowed: bool
    parking: bool
    balcony_garden: bool
    energy_rating: Optional[str] = None
    availability_date: str
    photos: List[str]
    features: List[str]
    country: str
    city: str
    postcode: Optional[str] = None
    floorplan: Optional[str] = None
    status: Optional[str] = "active"

class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    coordinates: Optional[dict] = None
    size_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_type: Optional[str] = None
    furnished: Optional[bool] = None
    pets_allowed: Optional[bool] = None
    parking: Optional[bool] = None
    balcony_garden: Optional[bool] = None
    energy_rating: Optional[str] = None
    availability_date: Optional[str] = None
    photos: Optional[List[str]] = None
    features: Optional[List[str]] = None
    country: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    floorplan: Optional[str] = None
    status: Optional[str] = None

class ViewingRequestCreate(BaseModel):
    property_id: str
    name: str
    email: str
    phone: str
    message: Optional[str] = None
    preferred_date: Optional[str] = None

class DevLogin(BaseModel):
    email: str
    name: str
    picture: Optional[str] = None

class Plan(BaseModel):
    id: str
    name: str
    slug: str
    monthly_price_cents: int
    currency: str
    max_active_listings: int
    type: str
    features: list

# Auth helpers
async def get_current_user(session_token: Optional[str] = Cookie(None), authorization: Optional[str] = None):
    token = session_token
    if not token and authorization:
        token = authorization.replace("Bearer ", "")
    
    if not token:
        return None
    
    session = await db.sessions.find_one({"session_token": token})
    if not session or datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
        return None
    
    user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
    return User(**user) if user else None

async def get_plan_by_id(plan_id: str) -> Plan:
    plan = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        plan = await db.plans.find_one({"slug": "free"}, {"_id": 0})
    return Plan(**plan)

async def get_plan_by_slug(slug: str) -> Optional[Plan]:
    plan = await db.plans.find_one({"slug": slug}, {"_id": 0})
    return Plan(**plan) if plan else None

async def count_active_listings(user: User) -> int:
    listings = await db.properties.find({"agent_info.id": user.id, "status": "active"}, {"_id": 0}).to_list(10000)
    return len(listings)

async def enforce_plan_limits(user: User, photos: List[str]) -> dict:
    plan = await get_plan_by_id(user.plan_id)
    limits = {
        "free": {"max_listings": 1, "max_photos": 3, "days": 15},
        "standard": {"max_listings": 3, "max_photos": 15, "days": 60},
        "agent-starter": {"max_listings": 10, "max_photos": 30, "days": 90},
        "agent-pro": {"max_listings": 30, "max_photos": 40, "days": 120},
        "agency-unlimited": {"max_listings": 0, "max_photos": 60, "days": 180},
    }
    rule = limits.get(plan.slug, limits["free"])
    active_count = await count_active_listings(user)
    if rule["max_listings"] and active_count >= rule["max_listings"]:
        raise HTTPException(status_code=400, detail="You have reached the maximum number of active listings for your plan. Please upgrade your plan.")
    if len(photos) > rule["max_photos"]:
        raise HTTPException(status_code=400, detail=f"Your plan allows max {rule['max_photos']} photos.")
    return {"plan": plan, "rule": rule}

def compute_expiry(rule_days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=rule_days)

def is_active(until: Optional[str]) -> bool:
    if not until:
        return False
    dt = until if isinstance(until, datetime) else datetime.fromisoformat(until)
    return dt > datetime.now(timezone.utc)

# Auth endpoints
@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        data = resp.json()
    
    existing_user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    if not existing_user:
        user = User(
            email=data["email"],
            name=data["name"],
            picture=data.get("picture")
        )
        user_dict = user.model_dump()
        user_dict["created_at"] = user_dict["created_at"].isoformat()
        await db.users.insert_one(user_dict)
    else:
        user = User(**existing_user)
    
    session_token = data["session_token"]
    session = Session(
        user_id=user.id,
        session_token=session_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    session_dict = session.model_dump()
    session_dict["created_at"] = session_dict["created_at"].isoformat()
    session_dict["expires_at"] = session_dict["expires_at"].isoformat()
    await db.sessions.insert_one(session_dict)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=604800,
        path="/"
    )
    
    return {"user": user.model_dump()}

@api_router.post("/auth/dev-login")
async def dev_login(payload: DevLogin, response: Response):
    if not ENABLE_DEV_AUTH:
        raise HTTPException(status_code=403, detail="Developer login disabled")

    existing_user = await db.users.find_one({"email": payload.email}, {"_id": 0})
    if not existing_user:
        user = User(
            email=payload.email,
            name=payload.name,
            picture=payload.picture
        )
        user_dict = user.model_dump()
        user_dict["created_at"] = user_dict["created_at"].isoformat()
        await db.users.insert_one(user_dict)
    else:
        user = User(**existing_user)

    session_token = str(uuid.uuid4())
    session = Session(
        user_id=user.id,
        session_token=session_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    session_dict = session.model_dump()
    session_dict["created_at"] = session_dict["created_at"].isoformat()
    session_dict["expires_at"] = session_dict["expires_at"].isoformat()
    await db.sessions.insert_one(session_dict)

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=604800,
        path="/"
    )

    return {"user": user.model_dump(), "session_token": session_token, "source": DATA_SOURCE}

@api_router.get("/plans", response_model=List[Plan])
async def list_plans():
    plans = await db.plans.find({}, {"_id": 0}).to_list(50)
    return [Plan(**p) for p in plans]

@api_router.post("/plans/subscribe")
async def subscribe_plan(plan_slug: str, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    plan = await get_plan_by_slug(plan_slug)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.users.update_one({"id": user.id}, {"$set": {"plan_id": plan.id, "role": "agent" if plan.type == "agent" else "individual"}})
    updated = await db.users.find_one({"id": user.id}, {"_id": 0})
    return {"message": "Plan updated", "user": updated, "plan": plan.model_dump()}

@api_router.get("/me/usage")
async def get_usage(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    plan = await get_plan_by_id(user.plan_id)
    active = await count_active_listings(user)
    return {
        "plan": plan.model_dump(),
        "active_listings": active,
        "max_active_listings": plan.max_active_listings
    }

@api_router.get("/auth/me")
async def get_me(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user": user.model_dump()}

@api_router.post("/auth/logout")
async def logout(response: Response, user: Optional[User] = Depends(get_current_user), session_token: Optional[str] = Cookie(None)):
    if session_token:
        await db.sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    return {"message": "Logged out"}

# Property endpoints
@api_router.get("/properties", response_model=List[Property])
async def get_properties(
    location: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    property_type: Optional[str] = None,
    furnished: Optional[bool] = None,
    pets_allowed: Optional[bool] = None,
    parking: Optional[bool] = None,
    balcony_garden: Optional[bool] = None,
    country: Optional[str] = None,
    energy_rating: Optional[str] = None,
    featured: Optional[bool] = None,
    limit: int = 50
):
    # Force filter to only allowed countries
    query = {"country": {"$in": list(ALLOWED_COUNTRIES)}}
    await expire_outdated_listings()
    
    if location:
        query["$or"] = [
            {"location": {"$regex": location, "$options": "i"}},
            {"address": {"$regex": location, "$options": "i"}},
            {"city": {"$regex": location, "$options": "i"}}
        ]
    if min_price is not None:
        query["price"] = {"$gte": min_price}
    if max_price is not None:
        query.setdefault("price", {})["$lte"] = max_price
    if bedrooms is not None:
        query["bedrooms"] = bedrooms
    if bathrooms is not None:
        query["bathrooms"] = bathrooms
    if property_type:
        query["property_type"] = property_type
    if furnished is not None:
        query["furnished"] = furnished
    if pets_allowed is not None:
        query["pets_allowed"] = pets_allowed
    if parking is not None:
        query["parking"] = parking
    if balcony_garden is not None:
        query["balcony_garden"] = balcony_garden
    if country and country in ALLOWED_COUNTRIES:
        query["country"] = country
    if energy_rating:
        query["energy_rating"] = energy_rating
    if featured is not None:
        query["featured"] = featured
    # Only active listings
    query["status"] = "active"

    properties = await db.properties.find(query, {"_id": 0}).to_list(10000)
    # ranking: spotlight > boost > featured > created_at desc
    def sort_key(prop):
        return (
            0 if is_active(prop.get("spotlight_expires_at")) else 1,
            0 if is_active(prop.get("boost_expires_at")) else 1,
            0 if prop.get("featured") else 1,
            -(prop.get("created_at").timestamp() if isinstance(prop.get("created_at"), datetime) else datetime.fromisoformat(str(prop.get("created_at"))).timestamp())
        )
    properties = sorted(properties, key=sort_key)[:limit]
    for prop in properties:
        if isinstance(prop.get("created_at"), str):
            prop["created_at"] = datetime.fromisoformat(prop["created_at"])
    return properties

@api_router.get("/properties/{property_id}", response_model=Property)
async def get_property(property_id: str):
    prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if isinstance(prop.get("created_at"), str):
        prop["created_at"] = datetime.fromisoformat(prop["created_at"])
    return Property(**prop)

@api_router.post("/properties", response_model=Property)
async def create_property(prop_data: PropertyCreate, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    enforcement = await enforce_plan_limits(user, prop_data.photos)
    rule = enforcement["rule"]
    plan = enforcement["plan"]

    # Validate country is in whitelist
    if prop_data.country not in ALLOWED_COUNTRIES:
        raise HTTPException(
            status_code=400, 
            detail=f"Properties can only be created in UK and EU countries. {prop_data.country} is not allowed."
        )
    
    # Validate currency matches region (default EUR for EU + TR, GBP for UK)
    allowed_currencies = {
        "GB": {"GBP", "EUR"},
    }
    region_allowed = allowed_currencies.get(prop_data.country, {"EUR"})
    if prop_data.currency not in region_allowed:
        raise HTTPException(status_code=400, detail=f"Currency {prop_data.currency} is not valid for {prop_data.country}")
    
    prop = Property(
        **prop_data.model_dump(),
        agent_info={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "picture": user.picture
        },
        featured=False,
        status="active",
        photos_count=len(prop_data.photos),
        expires_at=compute_expiry(rule["days"])
    )
    prop_dict = prop.model_dump()
    prop_dict["created_at"] = prop_dict["created_at"].isoformat()
    if prop_dict.get("expires_at"):
        prop_dict["expires_at"] = prop_dict["expires_at"].isoformat()
    await db.properties.insert_one(prop_dict)
    return prop

@api_router.get("/me/listings", response_model=List[Property])
async def get_my_listings(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    properties = await db.properties.find({"agent_info.id": user.id}, {"_id": 0}).to_list(1000)
    for prop in properties:
        if isinstance(prop.get("created_at"), str):
            prop["created_at"] = datetime.fromisoformat(prop["created_at"])
    return properties

@api_router.put("/listings/{listing_id}", response_model=Property)
async def update_listing(listing_id: str, prop_data: PropertyUpdate, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check ownership
    existing = await db.properties.find_one({"id": listing_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if existing["agent_info"]["id"] != user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listings")
    
    # Validate country if being updated
    if prop_data.country and prop_data.country not in ALLOWED_COUNTRIES:
        raise HTTPException(
            status_code=400, 
            detail=f"Properties can only be in UK and EU countries. {prop_data.country} is not allowed."
        )
    
    # Build update dict
    update_dict = {k: v for k, v in prop_data.model_dump(exclude_unset=True).items() if v is not None}
    if "photos" in update_dict:
        update_dict["photos_count"] = len(update_dict["photos"])
    if update_dict:
        await db.properties.update_one({"id": listing_id}, {"$set": update_dict})
    
    updated = await db.properties.find_one({"id": listing_id}, {"_id": 0})
    if isinstance(updated.get("created_at"), str):
        updated["created_at"] = datetime.fromisoformat(updated["created_at"])
    return Property(**updated)

@api_router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check ownership
    existing = await db.properties.find_one({"id": listing_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if existing["agent_info"]["id"] != user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own listings")
    
    await db.properties.delete_one({"id": listing_id})
    await db.favorites.delete_many({"property_id": listing_id})
    return {"message": "Listing deleted successfully"}

# Boost / Spotlight
@api_router.post("/listings/{listing_id}/boost")
async def boost_listing(listing_id: str, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    listing = await db.properties.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["agent_info"]["id"] != user.id:
        raise HTTPException(status_code=403, detail="You can only boost your own listings")
    boost_until = datetime.now(timezone.utc) + timedelta(days=7)
    await db.properties.update_one({"id": listing_id}, {"$set": {"boost_expires_at": boost_until.isoformat()}})
    return {"message": "Listing boosted", "boost_expires_at": boost_until.isoformat()}

@api_router.post("/listings/{listing_id}/spotlight")
async def spotlight_listing(listing_id: str, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    listing = await db.properties.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["agent_info"]["id"] != user.id:
        raise HTTPException(status_code=403, detail="You can only spotlight your own listings")
    until = datetime.now(timezone.utc) + timedelta(days=7)
    await db.properties.update_one({"id": listing_id}, {"$set": {"spotlight_expires_at": until.isoformat(), "featured": True}})
    return {"message": "Listing spotlighted", "spotlight_expires_at": until.isoformat()}

# Favorites
@api_router.get("/favorites", response_model=List[Property])
async def get_favorites(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    favorites = await db.favorites.find({"user_id": user.id}, {"_id": 0}).to_list(1000)
    property_ids = [f["property_id"] for f in favorites]
    
    properties = await db.properties.find({"id": {"$in": property_ids}}, {"_id": 0}).to_list(1000)
    for prop in properties:
        if isinstance(prop.get("created_at"), str):
            prop["created_at"] = datetime.fromisoformat(prop["created_at"])
    return properties

@api_router.post("/favorites/{property_id}")
async def add_favorite(property_id: str, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    existing = await db.favorites.find_one({"user_id": user.id, "property_id": property_id})
    if existing:
        return {"message": "Already in favorites"}
    
    favorite = Favorite(user_id=user.id, property_id=property_id)
    fav_dict = favorite.model_dump()
    fav_dict["created_at"] = fav_dict["created_at"].isoformat()
    await db.favorites.insert_one(fav_dict)
    return {"message": "Added to favorites"}

@api_router.delete("/favorites/{property_id}")
async def remove_favorite(property_id: str, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    await db.favorites.delete_one({"user_id": user.id, "property_id": property_id})
    return {"message": "Removed from favorites"}

# Viewing requests
@api_router.post("/viewing-requests")
async def create_viewing_request(data: ViewingRequestCreate, user: Optional[User] = Depends(get_current_user)):
    viewing = ViewingRequest(
        **data.model_dump(),
        user_id=user.id if user else "guest"
    )
    viewing_dict = viewing.model_dump()
    viewing_dict["created_at"] = viewing_dict["created_at"].isoformat()
    await db.viewing_requests.insert_one(viewing_dict)
    return {"message": "Viewing request submitted"}

# Stripe checkout mock/real
@api_router.post("/stripe/checkout-session")
async def create_checkout_session(payload: dict, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    purpose = payload.get("purpose")
    plan_slug = payload.get("plan_slug")
    listing_id = payload.get("listing_id")
    addon = payload.get("addon")  # boost | spotlight

    price_map = {
        "standard": {"gbp": 999},
        "agent-starter": {"gbp": 2900},
        "agent-pro": {"gbp": 5900},
        "agency-unlimited": {"gbp": 9900},
        "boost": {"gbp": 499},
        "spotlight": {"gbp": 1499},
    }
    # If Stripe key missing, simulate success for local dev
    if not STRIPE_SECRET_KEY:
        if purpose == "plan" and plan_slug:
            await subscribe_plan(plan_slug, user)
        if purpose == "addon" and listing_id and addon:
            if addon == "boost":
                await boost_listing(listing_id, user)
            if addon == "spotlight":
                await spotlight_listing(listing_id, user)
        return {"session_id": f"dev_session_{uuid.uuid4()}", "mode": purpose, "url": None}

    try:
        line_items = []
        if purpose == "plan":
            line_items.append({
                "price_data": {
                    "currency": "gbp",
                    "unit_amount": price_map.get(plan_slug, {"gbp": 0})["gbp"],
                    "product_data": {"name": f"Plan {plan_slug}"},
                    "recurring": {"interval": "month"}
                },
                "quantity": 1
            })
        elif purpose == "addon" and addon:
            line_items.append({
                "price_data": {
                    "currency": "gbp",
                    "unit_amount": price_map.get(addon, {"gbp": 0})["gbp"],
                    "product_data": {"name": f"Addon {addon.title()}"},
                },
                "quantity": 1
            })
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="subscription" if purpose == "plan" else "payment",
            success_url=payload.get("success_url") or "http://localhost:3000?success=true",
            cancel_url=payload.get("cancel_url") or "http://localhost:3000?cancel=true",
            client_reference_id=user.id,
            metadata={
                "purpose": purpose,
                "plan_slug": plan_slug or "",
                "listing_id": listing_id or "",
                "addon": addon or ""
            }
        )
        return {"session_id": session.id, "url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    event = None
    try:
        if endpoint_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        else:
            event = stripe.Event.construct_from({"type": "manual", "data": {"object": {}}}, stripe.api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = event["data"]["object"] if "data" in event and "object" in event["data"] else {}
    metadata = data.get("metadata", {})
    user_id = data.get("client_reference_id") or metadata.get("user_id")
    if not user_id:
        return {"status": "ignored"}

    if metadata.get("purpose") == "plan" and metadata.get("plan_slug"):
        await db.users.update_one({"id": user_id}, {"$set": {"plan_id": f"plan-{metadata['plan_slug']}"}})
    if metadata.get("purpose") == "addon" and metadata.get("listing_id"):
        if metadata.get("addon") == "boost":
            await db.properties.update_one({"id": metadata["listing_id"]}, {"$set": {"boost_expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()}})
        if metadata.get("addon") == "spotlight":
            await db.properties.update_one({"id": metadata["listing_id"]}, {"$set": {"spotlight_expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(), "featured": True}})
    return {"status": "ok"}

# Maintenance
@api_router.post("/tasks/expire-listings")
async def run_expiry():
    await expire_outdated_listings()
    return {"message": "Expiry task completed"}

# Paddle checkout (mock/real)
@api_router.post("/paddle/checkout-session")
async def paddle_checkout_session(payload: dict, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    purpose = payload.get("purpose")
    plan_slug = payload.get("plan_slug")
    listing_id = payload.get("listing_id")
    addon = payload.get("addon")

    price_map = {
        "standard": 999,
        "agent-starter": 2900,
        "agent-pro": 5900,
        "agency-unlimited": 9900,
        "boost": 499,
        "spotlight": 1499,
    }

    # Mocked path if keys missing
    if not PADDLE_API_KEY:
        if purpose == "plan" and plan_slug:
            await subscribe_plan(plan_slug, user)
        if purpose == "addon" and listing_id and addon:
            if addon == "boost":
                await boost_listing(listing_id, user)
            if addon == "spotlight":
                await spotlight_listing(listing_id, user)
        return {"checkout_url": None, "session_id": f"paddle_mock_{uuid.uuid4()}"}

    # Minimal Paddle Classic-style payload (requires server-side integration in production)
    try:
        amount = price_map.get(plan_slug or addon, 0) / 100
        product_name = f"{purpose}-{plan_slug or addon}"
        checkout_url = f"https://sandbox-checkout.paddle.com/checkout?price={amount}&product={product_name}"
        return {"checkout_url": checkout_url, "session_id": f"paddle_{uuid.uuid4()}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("API data source: %s", DATA_SOURCE)

async def expire_outdated_listings():
    now = datetime.now(timezone.utc)
    listings = await db.properties.find({}, {"_id": 0}).to_list(10000)
    for lst in listings:
        expires = lst.get("expires_at")
        if expires and isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if expires and expires < now and lst.get("status") != "expired":
            await db.properties.update_one({"id": lst["id"]}, {"$set": {"status": "expired"}})

@app.on_event("shutdown")
async def shutdown_db_client():
    if client:
        client.close()
