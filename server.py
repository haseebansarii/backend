from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import feedparser
import httpx


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# ============= MODELS =============

class AppConfig(BaseModel):
    id: str = Field(default="main_config")
    restaurant_name: str = Field(default="Number ONE")
    city: str = Field(default="ROMA")
    logo_base64: Optional[str] = None
    theme_primary_color: str = Field(default="#FF0000")
    theme_secondary_color: str = Field(default="#2C3E50")
    theme_text_color: str = Field(default="#FFFFFF")
    rss_feed_url: str = Field(default="https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it")
    weather_api_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class AppConfigUpdate(BaseModel):
    restaurant_name: Optional[str] = None
    city: Optional[str] = None
    logo_base64: Optional[str] = None
    theme_primary_color: Optional[str] = None
    theme_secondary_color: Optional[str] = None
    theme_text_color: Optional[str] = None
    rss_feed_url: Optional[str] = None
    weather_api_key: Optional[str] = None

class SlideImage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_base64: str
    order: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SlideImageCreate(BaseModel):
    image_base64: str
    order: Optional[int] = 0

class SlideSettings(BaseModel):
    id: str = Field(default="slide_settings")
    interval_seconds: int = Field(default=10)
    transition_effect: str = Field(default="fade")  # fade, slide, zoom
    auto_play: bool = Field(default=True)

class SlideSettingsUpdate(BaseModel):
    interval_seconds: Optional[int] = None
    transition_effect: Optional[str] = None
    auto_play: Optional[bool] = None

class CurrentNumber(BaseModel):
    id: str = Field(default="current_number")
    number: int = Field(default=1)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NumberUpdate(BaseModel):
    number: int

class BluetoothRemote(BaseModel):
    id: str = Field(default="bluetooth_remote")
    device_name: Optional[str] = None
    device_id: Optional[str] = None
    button_a_action: str = Field(default="increment")  # increment, decrement, reset
    button_b_action: str = Field(default="decrement")
    button_c_action: str = Field(default="reset")
    button_d_action: str = Field(default="none")
    is_paired: bool = Field(default=False)

class BluetoothRemoteUpdate(BaseModel):
    device_name: Optional[str] = None
    device_id: Optional[str] = None
    button_a_action: Optional[str] = None
    button_b_action: Optional[str] = None
    button_c_action: Optional[str] = None
    button_d_action: Optional[str] = None
    is_paired: Optional[bool] = None

class VoiceSettings(BaseModel):
    id: str = Field(default="voice_settings")
    enabled: bool = Field(default=True)
    voice_type: str = Field(default="female")  # male, female
    pitch: float = Field(default=1.0)  # 0.5 to 2.0
    rate: float = Field(default=1.0)  # 0.5 to 2.0
    phrase_template: str = Field(default="Numero {number}")
    language: str = Field(default="it-IT")

class VoiceSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    voice_type: Optional[str] = None
    pitch: Optional[float] = None
    rate: Optional[float] = None
    phrase_template: Optional[str] = None
    language: Optional[str] = None


# ============= CONFIG ENDPOINTS =============

@api_router.get("/config", response_model=AppConfig)
async def get_config():
    """Get app configuration"""
    config = await db.app_config.find_one({"id": "main_config"})
    if not config:
        # Create default config
        default_config = AppConfig()
        await db.app_config.insert_one(default_config.dict())
        return default_config
    return AppConfig(**config)

@api_router.put("/config", response_model=AppConfig)
async def update_config(config_update: AppConfigUpdate):
    """Update app configuration"""
    update_data = {k: v for k, v in config_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.app_config.update_one(
        {"id": "main_config"},
        {"$set": update_data},
        upsert=True
    )
    
    config = await db.app_config.find_one({"id": "main_config"})
    return AppConfig(**config)


# ============= SLIDE IMAGES ENDPOINTS =============

@api_router.get("/slides", response_model=List[SlideImage])
async def get_slides():
    """Get all slide images"""
    slides = await db.slide_images.find().sort("order", 1).to_list(100)
    return [SlideImage(**slide) for slide in slides]

@api_router.post("/slides", response_model=SlideImage)
async def create_slide(slide: SlideImageCreate):
    """Create new slide image"""
    slide_obj = SlideImage(**slide.dict())
    await db.slide_images.insert_one(slide_obj.dict())
    return slide_obj

@api_router.delete("/slides/{slide_id}")
async def delete_slide(slide_id: str):
    """Delete slide image"""
    result = await db.slide_images.delete_one({"id": slide_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Slide not found")
    return {"message": "Slide deleted successfully"}

@api_router.put("/slides/reorder")
async def reorder_slides(slide_orders: List[dict]):
    """Reorder slides"""
    for item in slide_orders:
        await db.slide_images.update_one(
            {"id": item["id"]},
            {"$set": {"order": item["order"]}}
        )
    return {"message": "Slides reordered successfully"}


# ============= SLIDE SETTINGS ENDPOINTS =============

@api_router.get("/slides/settings", response_model=SlideSettings)
async def get_slide_settings():
    """Get slide settings"""
    settings = await db.slide_settings.find_one({"id": "slide_settings"})
    if not settings:
        default_settings = SlideSettings()
        await db.slide_settings.insert_one(default_settings.dict())
        return default_settings
    return SlideSettings(**settings)

@api_router.put("/slides/settings", response_model=SlideSettings)
async def update_slide_settings(settings_update: SlideSettingsUpdate):
    """Update slide settings"""
    update_data = {k: v for k, v in settings_update.dict().items() if v is not None}
    
    result = await db.slide_settings.update_one(
        {"id": "slide_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    settings = await db.slide_settings.find_one({"id": "slide_settings"})
    return SlideSettings(**settings)


# ============= CURRENT NUMBER ENDPOINTS =============

@api_router.get("/number", response_model=CurrentNumber)
async def get_current_number():
    """Get current serving number"""
    number = await db.current_number.find_one({"id": "current_number"})
    if not number:
        default_number = CurrentNumber()
        await db.current_number.insert_one(default_number.dict())
        return default_number
    return CurrentNumber(**number)

@api_router.put("/number", response_model=CurrentNumber)
async def update_number(number_update: NumberUpdate):
    """Update current number"""
    update_data = {
        "number": number_update.number,
        "updated_at": datetime.utcnow()
    }
    
    await db.current_number.update_one(
        {"id": "current_number"},
        {"$set": update_data},
        upsert=True
    )
    
    number = await db.current_number.find_one({"id": "current_number"})
    return CurrentNumber(**number)

@api_router.post("/number/increment", response_model=CurrentNumber)
async def increment_number():
    """Increment current number by 1"""
    current = await db.current_number.find_one({"id": "current_number"})
    if not current:
        current = CurrentNumber().dict()
        await db.current_number.insert_one(current)
    
    new_number = current.get("number", 1) + 1
    update_data = {
        "number": new_number,
        "updated_at": datetime.utcnow()
    }
    
    await db.current_number.update_one(
        {"id": "current_number"},
        {"$set": update_data}
    )
    
    number = await db.current_number.find_one({"id": "current_number"})
    return CurrentNumber(**number)

@api_router.post("/number/decrement", response_model=CurrentNumber)
async def decrement_number():
    """Decrement current number by 1"""
    current = await db.current_number.find_one({"id": "current_number"})
    if not current:
        current = CurrentNumber().dict()
        await db.current_number.insert_one(current)
    
    new_number = max(1, current.get("number", 1) - 1)  # Don't go below 1
    update_data = {
        "number": new_number,
        "updated_at": datetime.utcnow()
    }
    
    await db.current_number.update_one(
        {"id": "current_number"},
        {"$set": update_data}
    )
    
    number = await db.current_number.find_one({"id": "current_number"})
    return CurrentNumber(**number)

@api_router.post("/number/reset", response_model=CurrentNumber)
async def reset_number():
    """Reset number to 1"""
    update_data = {
        "number": 1,
        "updated_at": datetime.utcnow()
    }
    
    await db.current_number.update_one(
        {"id": "current_number"},
        {"$set": update_data},
        upsert=True
    )
    
    number = await db.current_number.find_one({"id": "current_number"})
    return CurrentNumber(**number)


# ============= NEWS FEED ENDPOINT =============

@api_router.get("/news")
async def get_news_feed():
    """Get news from RSS feed"""
    try:
        config = await db.app_config.find_one({"id": "main_config"})
        rss_url = config.get("rss_feed_url", "https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it") if config else "https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it"
        
        # Parse RSS feed
        feed = feedparser.parse(rss_url)
        
        news_items = []
        for entry in feed.entries[:20]:  # Get top 20 news
            news_items.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", "")
            })
        
        return {"news": news_items}
    except Exception as e:
        logger.error(f"Error fetching news: {str(e)}")
        return {"news": [], "error": str(e)}


# ============= WEATHER ENDPOINT (MOCKED FOR NOW) =============

@api_router.get("/weather")
async def get_weather():
    """Get weather data (mocked for now, will use API later)"""
    config = await db.app_config.find_one({"id": "main_config"})
    city = config.get("city", "ROMA") if config else "ROMA"
    
    # Mock weather data
    mock_weather = {
        "city": city,
        "current": {
            "temp": 32,
            "condition": "sunny",
            "icon": "☀️"
        },
        "forecast": [
            {"day": "GIO", "temp": 35, "condition": "sunny"},
            {"day": "VEN", "temp": 36, "condition": "sunny"},
            {"day": "SAB", "temp": 35, "condition": "sunny"},
            {"day": "DOM", "temp": 35, "condition": "partly_cloudy"},
            {"day": "LUN", "temp": 35, "condition": "sunny"},
            {"day": "MAR", "temp": 34, "condition": "sunny"}
        ]
    }
    
    return mock_weather


# ============= BLUETOOTH REMOTE ENDPOINTS =============

@api_router.get("/bluetooth", response_model=BluetoothRemote)
async def get_bluetooth_settings():
    """Get bluetooth remote settings"""
    settings = await db.bluetooth_remote.find_one({"id": "bluetooth_remote"})
    if not settings:
        default_settings = BluetoothRemote()
        await db.bluetooth_remote.insert_one(default_settings.dict())
        return default_settings
    return BluetoothRemote(**settings)

@api_router.put("/bluetooth", response_model=BluetoothRemote)
async def update_bluetooth_settings(settings_update: BluetoothRemoteUpdate):
    """Update bluetooth remote settings"""
    update_data = {k: v for k, v in settings_update.dict().items() if v is not None}
    
    await db.bluetooth_remote.update_one(
        {"id": "bluetooth_remote"},
        {"$set": update_data},
        upsert=True
    )
    
    settings = await db.bluetooth_remote.find_one({"id": "bluetooth_remote"})
    return BluetoothRemote(**settings)


# ============= VOICE SETTINGS ENDPOINTS =============

@api_router.get("/voice", response_model=VoiceSettings)
async def get_voice_settings():
    """Get voice/TTS settings"""
    settings = await db.voice_settings.find_one({"id": "voice_settings"})
    if not settings:
        default_settings = VoiceSettings()
        await db.voice_settings.insert_one(default_settings.dict())
        return default_settings
    return VoiceSettings(**settings)

@api_router.put("/voice", response_model=VoiceSettings)
async def update_voice_settings(settings_update: VoiceSettingsUpdate):
    """Update voice/TTS settings"""
    update_data = {k: v for k, v in settings_update.dict().items() if v is not None}
    
    await db.voice_settings.update_one(
        {"id": "voice_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    settings = await db.voice_settings.find_one({"id": "voice_settings"})
    return VoiceSettings(**settings)


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Nothing special to do
    yield
    # Shutdown: Close the MongoDB client
    client.close()
