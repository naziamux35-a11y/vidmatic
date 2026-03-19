from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from auth import get_current_user
from models import User, Channel
import os
import uuid
from datetime import datetime, timezone
from composio import Composio
import logging

logger = logging.getLogger(__name__)

youtube_router = APIRouter()

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize Composio client
COMPOSIO_API_KEY = os.environ.get('COMPOSIO_API_KEY', 'ak_Ppdy7XYc5YA9AXLUBK6E')
composio_client = Composio(api_key=COMPOSIO_API_KEY)

# Frontend URL for redirects
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://vidmatic-preview.preview.emergentagent.com')

# YouTube Integration ID (created once and reused)
YOUTUBE_INTEGRATION_ID = None

async def get_or_create_youtube_integration():
    """Get or create YouTube integration in Composio"""
    global YOUTUBE_INTEGRATION_ID
    
    if YOUTUBE_INTEGRATION_ID:
        return YOUTUBE_INTEGRATION_ID
    
    try:
        # Check existing integrations
        integrations = composio_client.integrations.get()
        for integ in integrations:
            if hasattr(integ, 'appName') and integ.appName == 'youtube':
                YOUTUBE_INTEGRATION_ID = integ.id
                logger.info(f"Found existing YouTube integration: {YOUTUBE_INTEGRATION_ID}")
                return YOUTUBE_INTEGRATION_ID
        
        # Get YouTube app ID
        apps = composio_client.apps.get()
        youtube_app = None
        for app in apps:
            if getattr(app, 'key', '').lower() == 'youtube':
                youtube_app = app
                break
        
        if not youtube_app:
            raise Exception("YouTube app not found in Composio")
        
        # Create new integration
        integration = composio_client.integrations.create(
            app_id=youtube_app.appId,
            name='vidmatic_youtube',
            use_composio_auth=True
        )
        
        YOUTUBE_INTEGRATION_ID = integration.id
        logger.info(f"Created new YouTube integration: {YOUTUBE_INTEGRATION_ID}")
        return YOUTUBE_INTEGRATION_ID
        
    except Exception as e:
        logger.error(f"Failed to get/create YouTube integration: {str(e)}")
        raise

class OAuthStartRequest(BaseModel):
    redirect_uri: Optional[str] = None

class UploadVideoRequest(BaseModel):
    channel_id: str
    video_file_path: str
    title: str
    description: str
    tags: List[str]
    thumbnail_path: Optional[str] = None
    scheduled_at: Optional[str] = None

@youtube_router.post("/oauth/start")
async def start_oauth(req: OAuthStartRequest, user: User = Depends(get_current_user)):
    """Start YouTube OAuth flow using Composio"""
    try:
        # Get or create YouTube integration
        integration_id = await get_or_create_youtube_integration()
        
        # Construct callback URL
        callback_url = f"{FRONTEND_URL}/api/youtube/oauth/callback"
        
        # Initiate connection with Composio
        connection = composio_client.connected_accounts.initiate(
            integration_id=integration_id,
            entity_id=user.user_id,  # Use our internal user ID
            redirect_url=callback_url
        )
        
        logger.info(f"Composio connection initiated for user {user.user_id}, connected_account_id: {connection.connectedAccountId}")
        
        # Store the pending connection in database for later verification
        await db.pending_connections.update_one(
            {"user_id": user.user_id, "connected_account_id": connection.connectedAccountId},
            {
                "$set": {
                    "user_id": user.user_id,
                    "connected_account_id": connection.connectedAccountId,
                    "status": connection.connectionStatus,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        return {
            "authorization_url": connection.redirectUrl,
            "connection_id": connection.connectedAccountId,
            "state": connection.connectedAccountId
        }
    except Exception as e:
        logger.error(f"Failed to initiate Composio connection: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start YouTube connection: {str(e)}")

@youtube_router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    connectionId: str = Query(None, description="Composio connection ID (old format)"),
    connectedAccountId: str = Query(None, description="Composio connected account ID"),
    status: str = Query(None, description="Connection status"),
    appName: str = Query(None, description="App name"),
    error: str = Query(None)
):
    """Handle YouTube OAuth callback from Composio"""
    # Composio sends connectedAccountId, not connectionId
    connection_id = connectedAccountId or connectionId
    
    logger.info(f"OAuth callback received. connectedAccountId: {connectedAccountId}, connectionId: {connectionId}, status: {status}")
    logger.info(f"Full query params: {dict(request.query_params)}")
    
    # Handle errors
    if error:
        logger.error(f"OAuth error: {error}")
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error={error}")
    
    if not connection_id:
        logger.error("No connection ID received in callback")
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error=no_connection_id")
    
    try:
        # Get the connection details from Composio
        connection = composio_client.connected_accounts.get(connection_id=connection_id)
        
        if not connection:
            logger.error(f"Connection not found: {connection_id}")
            return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error=connection_not_found")
        
        logger.info(f"Connection retrieved: {connection}")
        
        # Get connection details
        connection_dict = connection.__dict__ if hasattr(connection, '__dict__') else {}
        # Composio stores user_id in clientUniqueUserId field
        entity_id = connection_dict.get('clientUniqueUserId') or connection_dict.get('entityId') or connection_dict.get('entity_id')
        conn_status = connection_dict.get('status', 'unknown')
        
        logger.info(f"Connection entity_id: {entity_id}, conn_status: {conn_status}")
        
        if not entity_id:
            # Try to find the user from pending connections
            pending = await db.pending_connections.find_one({"connected_account_id": connection_id})
            if pending:
                entity_id = pending.get("user_id")
                logger.info(f"Found entity_id from pending connections: {entity_id}")
        
        if not entity_id:
            logger.error("No entity_id found")
            return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error=no_user_found")
        
        # Get channel info - use connection data
        channel_name = "YouTube Channel"
        channel_avatar = None
        subscriber_count = 0
        youtube_channel_id = connection_id
        
        # Try to get info from connection
        if hasattr(connection, 'connectionParams') and connection.connectionParams:
            params = connection.connectionParams
            if hasattr(params, 'scope'):
                logger.info(f"Connection scope: {params.scope}")
        
        # Check if there's account info in connected_account_id's metadata
        # For now, we'll use a default name that user can update later
        # We could also try to fetch channel details using the connection
        
        # Create or update channel record in database
        channel_id = f"ch_{uuid.uuid4().hex[:12]}"
        channel_doc = {
            "channel_id": channel_id,
            "user_id": entity_id,
            "youtube_channel_id": youtube_channel_id,
            "channel_name": f"Connected YouTube Channel",  # User can rename later
            "channel_avatar": "https://www.youtube.com/img/desktop/yt_1200.png",  # Default YT avatar
            "subscriber_count": subscriber_count,
            "composio_connection_id": connection_id,
            "connection_status": conn_status,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }
        
        # Check if channel already exists for this user with this connection
        existing_channel = await db.channels.find_one({
            "user_id": entity_id,
            "composio_connection_id": connection_id
        })
        
        if existing_channel:
            await db.channels.update_one(
                {"_id": existing_channel["_id"]},
                {"$set": {
                    "channel_name": channel_name,
                    "channel_avatar": channel_avatar,
                    "subscriber_count": subscriber_count,
                    "is_active": True,
                    "connected_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            channel_id = existing_channel["channel_id"]
            logger.info(f"Updated existing channel: {channel_id}")
        else:
            await db.channels.insert_one(channel_doc)
            logger.info(f"Created new channel: {channel_id}")
        
        # Clean up pending connection
        await db.pending_connections.delete_one({"connected_account_id": connection_id})
        
        # Redirect back to dashboard with success
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_connected=true&channel_id={channel_id}")
        
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        import traceback
        traceback.print_exc()
        error_msg = str(e).replace(' ', '_')[:100]
        return RedirectResponse(url=f"{FRONTEND_URL}/dashboard?youtube_error={error_msg}")

@youtube_router.get("/connection/status/{connection_id}")
async def check_connection_status(connection_id: str, user: User = Depends(get_current_user)):
    """Check the status of a Composio connection"""
    try:
        connection = composio_client.connected_accounts.get(connection_id=connection_id)
        connection_dict = connection.__dict__ if hasattr(connection, '__dict__') else {}
        
        return {
            "connection_id": connection_id,
            "status": connection_dict.get('status', 'unknown'),
            "entity_id": connection_dict.get('entityId'),
            "details": connection_dict
        }
    except Exception as e:
        logger.error(f"Failed to check connection status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check connection: {str(e)}")

@youtube_router.get("/channels")
async def get_channels(user: User = Depends(get_current_user)):
    """Get user's connected YouTube channels"""
    channels = await db.channels.find({"user_id": user.user_id, "is_active": True}, {"_id": 0}).to_list(100)
    return channels

@youtube_router.delete("/channels/{channel_id}")
async def disconnect_channel(channel_id: str, user: User = Depends(get_current_user)):
    """Disconnect a YouTube channel"""
    channel = await db.channels.find_one({"channel_id": channel_id, "user_id": user.user_id})
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Deactivate in our database
    result = await db.channels.update_one(
        {"channel_id": channel_id, "user_id": user.user_id},
        {"$set": {"is_active": False}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"message": "Channel disconnected"}

@youtube_router.get("/channels/{channel_id}/stats")
async def get_channel_stats(channel_id: str, user: User = Depends(get_current_user)):
    """Get channel statistics using Composio"""
    channel = await db.channels.find_one({
        "channel_id": channel_id, 
        "user_id": user.user_id,
        "is_active": True
    })
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    composio_connection_id = channel.get("composio_connection_id")
    
    if not composio_connection_id:
        raise HTTPException(status_code=400, detail="No Composio connection found for this channel")
    
    try:
        # Get entity for this connection
        entity = composio_client.get_entity(id=channel.get("user_id"))
        
        # Execute get channel statistics action
        result = entity.execute(
            action="YOUTUBE_GET_CHANNEL_STATISTICS",
            params={},
            connected_account_id=composio_connection_id
        )
        
        if result:
            return result
        
        return {
            "channel_id": channel_id,
            "subscriber_count": channel.get("subscriber_count", 0),
            "message": "Using cached data"
        }
        
    except Exception as e:
        logger.error(f"Failed to get channel stats: {str(e)}")
        return {
            "channel_id": channel_id,
            "subscriber_count": channel.get("subscriber_count", 0),
            "error": str(e)
        }

@youtube_router.post("/upload")
async def upload_video(req: UploadVideoRequest, user: User = Depends(get_current_user)):
    """Upload video to YouTube using Composio"""
    channel = await db.channels.find_one({
        "channel_id": req.channel_id, 
        "user_id": user.user_id,
        "is_active": True
    })
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    composio_connection_id = channel.get("composio_connection_id")
    
    if not composio_connection_id:
        raise HTTPException(status_code=400, detail="No Composio connection found for this channel")
    
    try:
        # Get entity for this connection
        entity = composio_client.get_entity(id=user.user_id)
        
        # Execute upload video action
        result = entity.execute(
            action="YOUTUBE_UPLOAD_VIDEO",
            params={
                "file_path": req.video_file_path,
                "title": req.title,
                "description": req.description,
                "tags": req.tags
            },
            connected_account_id=composio_connection_id
        )
        
        return {
            "message": "Video upload initiated",
            "status": "processing",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Failed to upload video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")

@youtube_router.get("/channels/{channel_id}/videos")
async def list_channel_videos(channel_id: str, user: User = Depends(get_current_user)):
    """List videos from a channel using Composio"""
    channel = await db.channels.find_one({
        "channel_id": channel_id, 
        "user_id": user.user_id,
        "is_active": True
    })
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    composio_connection_id = channel.get("composio_connection_id")
    
    if not composio_connection_id:
        raise HTTPException(status_code=400, detail="No Composio connection found for this channel")
    
    try:
        # Get entity for this connection
        entity = composio_client.get_entity(id=user.user_id)
        
        # Execute list videos action
        result = entity.execute(
            action="YOUTUBE_LIST_CHANNEL_VIDEOS",
            params={},
            connected_account_id=composio_connection_id
        )
        
        return {
            "videos": result if result else []
        }
        
    except Exception as e:
        logger.error(f"Failed to list videos: {str(e)}")
        return {"videos": [], "error": str(e)}
