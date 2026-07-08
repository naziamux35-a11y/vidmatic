from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from auth import get_current_user
from models import User
from stock import validate_pexels_key, validate_pixabay_key
import os
from datetime import datetime, timezone

settings_router = APIRouter()

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


class StockKeysRequest(BaseModel):
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None


def _mask(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return key[:4] + "•" * 8 + key[-4:] if len(key) > 8 else "•" * 8


@settings_router.get("/stock-keys")
async def get_stock_keys(user: User = Depends(get_current_user)):
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "stock_api_keys": 1})
    keys = (doc or {}).get("stock_api_keys") or {}
    return {
        "pexels": _mask(keys.get("pexels")),
        "pixabay": _mask(keys.get("pixabay")),
        "has_pexels": bool(keys.get("pexels")),
        "has_pixabay": bool(keys.get("pixabay")),
    }


@settings_router.put("/stock-keys")
async def update_stock_keys(req: StockKeysRequest, user: User = Depends(get_current_user)):
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "stock_api_keys": 1})
    keys = (doc or {}).get("stock_api_keys") or {}

    if req.pexels_api_key is not None:
        key = req.pexels_api_key.strip()
        if key:
            if not await validate_pexels_key(key):
                raise HTTPException(status_code=400, detail="Invalid Pexels API key. Please check it and try again.")
            keys["pexels"] = key
        else:
            keys.pop("pexels", None)

    if req.pixabay_api_key is not None:
        key = req.pixabay_api_key.strip()
        if key:
            if not await validate_pixabay_key(key):
                raise HTTPException(status_code=400, detail="Invalid Pixabay API key. Please check it and try again.")
            keys["pixabay"] = key
        else:
            keys.pop("pixabay", None)

    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"stock_api_keys": keys, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {
        "message": "Stock API keys updated",
        "has_pexels": bool(keys.get("pexels")),
        "has_pixabay": bool(keys.get("pixabay")),
    }
