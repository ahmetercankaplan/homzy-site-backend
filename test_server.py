from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime, timezone

app = FastAPI()

# Mock data
mock_properties = [
    {
        "id": str(uuid.uuid4()),
        "title": "Modern Apartment in Central London",
        "description": "Beautiful 2-bedroom apartment in the heart of London with stunning city views.",
        "price": 2500,
        "currency": "GBP",
        "location": "London, UK",
        "address": "123 Oxford Street, London W1D 2HG",
        "coordinates": {"lat": 51.5074, "lng": -0.1278},
        "size_m2": 85,
        "bedrooms": 2,
        "bathrooms": 1,
        "property_type": "flat",
        "furnished": True,
        "pets_allowed": False,
        "parking": False,
        "balcony_garden": True,
        "energy_rating": "B",
        "availability_date": "2025-05-01",
        "photos": [
            "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800",
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800"
        ],
        "features": ["Central Heating", "Double Glazing", "Elevator"],
        "country": "GB",
        "city": "London",
        "featured": True,
        "agent_info": {
            "id": "agent1",
            "name": "Sarah Johnson",
            "email": "sarah@homzy.com",
            "picture": "https://randomuser.me/api/portraits/women/1.jpg"
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Charming Studio in Paris Marais",
        "description": "Cozy studio apartment in the historic Marais district.",
        "price": 1200,
        "currency": "EUR",
        "location": "Paris, France",
        "address": "15 Rue des Rosiers, 75004 Paris",
        "coordinates": {"lat": 48.8566, "lng": 2.3522},
        "size_m2": 35,
        "bedrooms": 1,
        "bathrooms": 1,
        "property_type": "studio",
        "furnished": True,
        "pets_allowed": True,
        "parking": False,
        "balcony_garden": False,
        "energy_rating": "C",
        "availability_date": "2025-04-15",
        "photos": [
            "https://images.unsplash.com/photo-1536376072261-38c75010e6c9?w=800"
        ],
        "features": ["Fully Equipped Kitchen", "High-Speed WiFi"],
        "country": "FR",
        "city": "Paris",
        "featured": True,
        "agent_info": {
            "id": "agent2",
            "name": "Pierre Dubois",
            "email": "pierre@homzy.com",
            "picture": "https://randomuser.me/api/portraits/men/2.jpg"
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }
]

# Models
class Property(BaseModel):
    id: str
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
    featured: bool
    agent_info: dict
    created_at: str

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Homzy API is running!"}

@app.get("/api/properties", response_model=List[Property])
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
    featured: Optional[bool] = None,
    limit: int = 50
):
    properties = mock_properties.copy()
    
    # Apply filters
    if location:
        properties = [p for p in properties if location.lower() in p["location"].lower()]
    if min_price is not None:
        properties = [p for p in properties if p["price"] >= min_price]
    if max_price is not None:
        properties = [p for p in properties if p["price"] <= max_price]
    if bedrooms is not None:
        properties = [p for p in properties if p["bedrooms"] == bedrooms]
    if bathrooms is not None:
        properties = [p for p in properties if p["bathrooms"] == bathrooms]
    if property_type:
        properties = [p for p in properties if p["property_type"] == property_type]
    if furnished is not None:
        properties = [p for p in properties if p["furnished"] == furnished]
    if pets_allowed is not None:
        properties = [p for p in properties if p["pets_allowed"] == pets_allowed]
    if parking is not None:
        properties = [p for p in properties if p["parking"] == parking]
    if balcony_garden is not None:
        properties = [p for p in properties if p["balcony_garden"] == balcony_garden]
    if country:
        properties = [p for p in properties if p["country"] == country]
    if featured is not None:
        properties = [p for p in properties if p["featured"] == featured]
    
    return properties[:limit]

@app.get("/api/properties/{property_id}", response_model=Property)
async def get_property(property_id: str):
    for prop in mock_properties:
        if prop["id"] == property_id:
            return prop
    raise HTTPException(status_code=404, detail="Property not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

