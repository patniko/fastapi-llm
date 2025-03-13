import enum
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import ARRAY, Boolean, Column, Date, DateTime, Enum, ForeignKey
from sqlalchemy import Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base

###
# Users
###


# Alchemy models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    email = Column(String, unique=True, index=True, nullable=True)
    email_verified = Column(Boolean, default=False)
    phone = Column(String, unique=True, index=True, nullable=True)
    phone_verified = Column(Boolean, default=False)
    picture = Column(String, unique=False, nullable=True)
    password_hash = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_logged_in = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String, nullable=False, default="UTC")
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete timestamp
    is_deleted = Column(Boolean, default=False)  # Flag to mark user as deleted


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String, nullable=False, unique=True, index=True)
    device_type = Column(String, nullable=False)  # "ios" or "android"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token = Column(String, nullable=False, unique=True, index=True)
    device_info = Column(String, nullable=True)  # Store device fingerprint info
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


###
# Notifications
###


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    users = Column(ARRAY(Integer), nullable=False)
    event = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_status = Column(Boolean, default=False)


###
# OAuth2 Credentials
###


class OAuth2Provider(str, enum.Enum):
    GOOGLE = "google"
    GITHUB = "github"
    FACEBOOK = "facebook"


class OAuth2Credentials(Base):
    __tablename__ = "oauth2_credentials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider = Column(Enum(OAuth2Provider), nullable=False)
    email = Column(String, nullable=False, index=True)
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


###
# Generic Item (Example Model)
###


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


###
# Pydantic Models for API
###


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: int
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    email_verified: bool
    phone: str
    phone_verified: bool
    picture: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    password: str


class UserUpdate(BaseModel):
    first_name: str = None
    last_name: str = None
    email: str = None
    phone: str = None
    picture: str = None


class ItemCreate(BaseModel):
    title: str
    description: str = None
    data: dict = None


class ItemResponse(BaseModel):
    id: int
    title: str
    description: str = None
    data: dict = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ItemUpdate(BaseModel):
    title: str = None
    description: str = None
    data: dict = None
    is_active: bool = None
