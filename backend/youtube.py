from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from auth import get_current_user
from models import User
import os
import uuid
import asyncio
from datetime import datetime, timezone
from composio import Composio
import logging

logger = logging.getLogger(__name__)

youtube_router = APIRouter()

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

COMPOSIO_API_KEY = os.environ['COMPOSIO_API_KEY']
FRONTEND_URL = os.environ['FRONTEND_URL']
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), "media")

composio_client = Composio(
    api_key=COMPOSIO_API_KEY,
    dangerously_allow_auto_upload_download_files=True,
    file_upload_dirs=[MEDIA_ROOT],
)

_youtube_auth_config_id: Optional[str] = None


def _get_youtube_auth_config_id() -> str:
    """Find (or create) the YouTube auth config in Composio."""
    global _youtube_auth_config_id
    if _youtube_auth_config_id:
        return _youtube_auth_config_id
    configs = composio_client.auth_configs.list(toolkit_slug="youtube")
    for cfg in getattr(configs, "items", []):
        if not (getattr(cfg, "disabled", False) or getattr(cfg, "is_disabled", False)):
            _youtube_auth_config_id = cfg.id
            return _youtube_auth_config_id
    created = composio_client.auth_configs.create(
        toolkit={"slug": "youtube"},
        options={"type": "use_composio_managed_auth", "name": "vidmatic_youtube"},
    )
    _youtube_auth_config_id = created.id
    return _youtube_auth_config_id


def _execute_tool(slug: str, user_id: str, connected_account_id: str, arguments: Dict[str, Any]) -> Dict:
    """Execute a Composio tool (sync SDK) and return its data payload."""
    result = composio_client.tools.execute(
        slug,
        arguments=arguments,
        user_id=user_id,
        connected_account_id=connected_account_id,
    )
    if isinstance(result, dict):
        if not result.get("successful", True):
            raise RuntimeError(result.get("error") or f"{slug} failed")
        return result.get("data") or {}
    return result


async def execute_tool(slug: str, user_id: str, connected_account_id: str, arguments: Dict[str, Any]) -> Dict:
    return await asyncio.to_thread(_execute_tool, slug, user_id, connected_account_id, arguments)


async def fetch_youtube_channel_details(user_id: str, connected_account_id: str) -> Optional[Dict]:
    """Fetch the connected user's YouTube channel name, avatar and statistics."""
    try:
        playlists = await execute_tool(
            "YOUTUBE_LIST_USER_PLAYLISTS", user_id, connected_account_id,
            {"part": "snippet", "maxResults": 5},
        )
        items = playlists.get("items", []) if playlists else []
        youtube_channel_id = None
        channel_title = "YouTube Channel"
        if items:
            snippet = items[0].get("snippet", {})
            youtube_channel_id = snippet.get("channelId")
            channel_title = snippet.get("channelTitle", channel_title)

        if not youtube_channel_id:
            logger.warning("Could not determine channel ID from playlists")
            return None

        stats = await execute_tool(
            "YOUTUBE_GET_CHANNEL_STATISTICS", user_id, connected_account_id,
            {"id": youtube_channel_id, "part": "snippet,statistics"},
        )
        channels = stats.get("channels") or stats.get("items") or []
        if not channels:
            return {
                "youtube_channel_id": youtube_channel_id,
                "channel_name": channel_title,
                "channel_avatar": None,
                "subscriber_count": 0, "video_count": 0, "view_count": 0,
                "custom_url": None, "description": None,
            }
        ch = channels[0]
        snippet = ch.get("snippet", {})
        statistics = ch.get("statistics", {})
        thumbs = snippet.get("thumbnails", {})
        return {
            "youtube_channel_id": youtube_channel_id,
            "channel_name": snippet.get("title", channel_title),
            "channel_avatar": (thumbs.get("medium") or thumbs.get("default") or {}).get("url"),
            "subscriber_count": int(statistics.get("subscriberCount", 0)),
            "video_count": int(statistics.get("videoCount", 0)),
            "view_count": int(statistics.get("viewCount", 0)),
            "custom_url": snippet.get("customUrl"),
            "description": (snippet.get("description") or "")[:200] or None,
        }
    except Exception as e:
        logger.error(f"Error fetching YouTube channel details: {e}")
        return None


async def upload_video_to_youtube(
    user_id: str, connected_account_id: str, file_path: str,
    title: str, description: str, tags: list, privacy_status: str = "public",
    category_id: str = "22",
) -> Dict:
    """Upload a local MP4 to YouTube via Composio. Returns response_data with video id."""
    data = await execute_tool(
        "YOUTUBE_UPLOAD_VIDEO", user_id, connected_account_id,
        {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:30],
            "categoryId": category_id,
            "privacyStatus": privacy_status,
            "videoFilePath": file_path,
        },
    )
    return data.get("response_data") or data


async def update_youtube_video(
    user_id: str, connected_account_id: str, youtube_video_id: str, privacy_status: str,
) -> Dict:
    return await execute_tool(
        "YOUTUBE_UPDATE_VIDEO", user_id, connected_account_id,
        {"videoId": youtube_video_id, "privacyStatus": privacy_status},
    )


async def set_youtube_thumbnail(
    user_id: str, connected_account_id: str, youtube_video_id: str, thumbnail_url: str,
) -> Dict:
    return await execute_tool(
        "YOUTUBE_UPDATE_THUMBNAIL", user_id, connected_account_id,
        {"videoId": youtube_video_id, "thumbnailUrl": thumbnail_url},
    )


class OAuthStartRequest(BaseModel):
    redirect_uri: Optional[str] = None


@youtube_router.post("/oauth/start")
async def start_oauth(req: OAuthStartRequest, user: User = Depends(get_current_user)):
    """Start YouTube OAuth flow using Composio v3"""
    try:
        auth_config_id = await asyncio.to_thread(_get_youtube_auth_config_id)
        callback_url = f"{FRONTEND_URL}/api/youtube/oauth/callback"

        connection = await asyncio.to_thread(
            composio_client.connected_accounts.initiate,
            user_id=user.user_id,
            auth_config_id=auth_config_id,
            callback_url=callback_url,
            allow_multiple=True,
        )

        conn_id = getattr(connection, "id", None)
        redirect_url = getattr(connection, "redirect_url", None) or getattr(connection, "redirectUrl", None)
        logger.info(f"Composio connection initiated for user {user.user_id}: {conn_id}")

        await db.pending_connections.update_one(
            {"connected_account_id": conn_id},
            {"$set": {
                "user_id": user.user_id,
                "connected_account_id": conn_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"authorization_url": redirect_url, "connection_id": conn_id}
    except Exception as e:
        logger.error(f"Failed to initiate Composio connection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start YouTube connection: {str(e)}")


@youtube_router.get("/oauth/callback")
async def oauth_callback(request: Request):
    """Handle YouTube OAuth callback from Composio"""
    params = dict(request.query_params)
    logger.info(f"OAuth callback params: {params}")

    error = params.get("error")
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error={error}")

    connection_id = (
        params.get("connected_account_id") or params.get("connectedAccountId")
        or params.get("connectionId") or params.get("nanoid")
    )

    try:
        if not connection_id:
            status = params.get("status", "")
            if status.upper() in ("SUCCESS", "ACTIVE", ""):
                pending = await db.pending_connections.find().sort("created_at", -1).to_list(1)
                if pending:
                    connection_id = pending[0]["connected_account_id"]
        if not connection_id:
            return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error=no_connection_id")

        account = await asyncio.to_thread(composio_client.connected_accounts.get, connection_id)
        conn_status = getattr(account, "status", "unknown")
        entity_id = getattr(account, "user_id", None)

        if not entity_id:
            pending = await db.pending_connections.find_one({"connected_account_id": connection_id})
            if pending:
                entity_id = pending.get("user_id")
        if not entity_id:
            return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error=no_user_found")

        details = await fetch_youtube_channel_details(entity_id, connection_id)
        if details:
            channel_fields = {
                "youtube_channel_id": details["youtube_channel_id"],
                "channel_name": details["channel_name"],
                "channel_avatar": details["channel_avatar"],
                "subscriber_count": details["subscriber_count"],
                "video_count": details["video_count"],
                "view_count": details["view_count"],
                "custom_url": details["custom_url"],
                "description": details["description"],
            }
        else:
            channel_fields = {
                "youtube_channel_id": connection_id,
                "channel_name": "YouTube Channel",
                "channel_avatar": None,
                "subscriber_count": 0, "video_count": 0, "view_count": 0,
                "custom_url": None, "description": None,
            }

        existing = await db.channels.find_one({
            "user_id": entity_id,
            "youtube_channel_id": channel_fields["youtube_channel_id"],
        })
        if existing:
            channel_id = existing["channel_id"]
            await db.channels.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    **channel_fields,
                    "composio_connection_id": connection_id,
                    "connection_status": str(conn_status),
                    "is_active": True,
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        else:
            channel_id = f"ch_{uuid.uuid4().hex[:12]}"
            await db.channels.insert_one({
                "channel_id": channel_id,
                "user_id": entity_id,
                **channel_fields,
                "composio_connection_id": connection_id,
                "connection_status": str(conn_status),
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            })

        await db.pending_connections.delete_one({"connected_account_id": connection_id})
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_connected=true&channel_id={channel_id}")
    except Exception as e:
        logger.error(f"Error processing callback: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error={str(e).replace(' ', '_')[:100]}")


@youtube_router.get("/channels")
async def get_channels(user: User = Depends(get_current_user)):
    channels = await db.channels.find({"user_id": user.user_id, "is_active": True}, {"_id": 0}).to_list(100)
    return channels


@youtube_router.post("/channels/{channel_id}/sync")
async def sync_channel_details(channel_id: str, user: User = Depends(get_current_user)):
    channel = await db.channels.find_one({"channel_id": channel_id, "user_id": user.user_id, "is_active": True})
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    conn_id = channel.get("composio_connection_id")
    if not conn_id:
        raise HTTPException(status_code=400, detail="No Composio connection found for this channel")

    details = await fetch_youtube_channel_details(user.user_id, conn_id)
    if not details:
        raise HTTPException(status_code=500, detail="Could not fetch channel details from YouTube")

    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {**details, "last_synced_at": datetime.now(timezone.utc).isoformat()}},
    )
    updated = await db.channels.find_one({"channel_id": channel_id}, {"_id": 0})
    return updated


@youtube_router.delete("/channels/{channel_id}")
async def disconnect_channel(channel_id: str, user: User = Depends(get_current_user)):
    result = await db.channels.update_one(
        {"channel_id": channel_id, "user_id": user.user_id},
        {"$set": {"is_active": False}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel disconnected"}
