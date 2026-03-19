from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

class SubscriptionPlan(str, Enum):
    FREE_TRIAL = "free_trial"
    PRO_MONTHLY = "pro_monthly"
    PRO_YEARLY = "pro_yearly"

class VideoStatus(str, Enum):
    PENDING = "pending"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_VOICEOVER = "generating_voiceover"
    GENERATING_VIDEO = "generating_video"
    GENERATING_THUMBNAIL = "generating_thumbnail"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    role: UserRole = UserRole.USER
    subscription_plan: SubscriptionPlan = SubscriptionPlan.FREE_TRIAL
    video_credits: int = 2
    free_video_credits: int = 0
    referral_code: str
    referred_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime

class Channel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    channel_id: str
    user_id: str
    youtube_channel_id: str
    channel_name: str
    channel_avatar: Optional[str] = None
    subscriber_count: Optional[int] = 0
    composio_connection_id: Optional[str] = None  # Composio connection ID for OAuth
    connected_at: datetime
    is_active: bool = True

class Video(BaseModel):
    model_config = ConfigDict(extra="ignore")
    video_id: str
    user_id: str
    channel_id: Optional[str] = None
    prompt: str
    video_length: str
    voice_style: str
    visual_style: str
    language: str = "en"
    status: VideoStatus
    script: Optional[str] = None
    voiceover_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_urls: Optional[List[str]] = []
    selected_thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    seo_score: Optional[int] = 0
    youtube_video_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str
    user_id: Optional[str] = None
    session_id: str
    amount: float
    currency: str
    plan: Optional[SubscriptionPlan] = None
    payment_status: PaymentStatus
    metadata: Optional[Dict[str, Any]] = {}
    created_at: datetime
    updated_at: datetime

class Referral(BaseModel):
    model_config = ConfigDict(extra="ignore")
    referral_id: str
    referrer_id: str
    referred_user_id: Optional[str] = None
    referred_email: Optional[str] = None
    status: str
    reward_granted: bool = False
    created_at: datetime
    updated_at: datetime