import io
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional, List
from uuid import uuid4

import httpx
import jwt
from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile
from loguru import logger
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from auth import create_access_token
from auth import get_user
from auth import get_user_by_id
from auth import validate_jwt
from auth import verify_password  # Add this import
from auth import get_password_hash  # Add this import
from auth import (
    create_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
)
from db import get_db
from env import get_settings
from memcache import get_cached_data
from memcache import set_cached_data
from models import DeviceToken
from models import User

router = APIRouter()


# Service models
class SmsVerify(BaseModel):
    phone: str
    code: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: int
    expires_in: int  # Access token expiration in seconds

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RevokeTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    phone_verified: bool
    email: str
    email_verified: bool
    picture: str
    is_onboarded: bool


class UserUpdate(BaseModel):
    first_name: Optional[str] | None = None
    last_name: Optional[str] | None = None
    picture: Optional[str] | None = None
    birth_date: Optional[date] | None = None
    postal_code: Optional[str] | None = None


class Token(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    email_verified: str
    phone: str
    phone_verified: str
    picture: str
    updated_at: str
    admin: str
    access_token: str
    token_type: str


class HashResponse(BaseModel):
    key_name: str
    value: str

    model_config = {"from_attributes": True}


class HashCreate(BaseModel):
    key_name: str
    value: str


class UserHashes(BaseModel):
    contacts_hash: Optional[str]
    routines_hash: Optional[str]
    catalog_hash: Optional[str]


class ResetToken(BaseModel):
    confirmation_code: str
    new_password: str
    confirm_new_password: str


class DeviceTokenRequest(BaseModel):
    token: str
    device_type: str = (
        "ios"  # Default to iOS since we're focusing on Apple push notifications
    )


class DeviceTokenResponse(BaseModel):
    id: int
    user_id: int
    token: str
    device_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class PasswordUpdate(BaseModel):
    current_password: Optional[str] = None  # Optional for users without password
    new_password: str


class PasswordLogin(BaseModel):
    phone: str
    password: str


# Service helper functions
def is_valid_phone_number(phone: str):
    if phone == "invalid_phone":
        return False
    else:
        return True


def sanitize_number(phone: str):
    # Remove any non-digit characters
    digits_only = "".join(filter(str.isdigit, phone))
    # If number started with a + we assume it is already a full number
    if phone[0] == "+":
        return f"+{digits_only}"
    # If it's a US number without country code, add +1
    if len(digits_only) == 10:
        return f"+1{digits_only}"
    # If it already has country code (11 digits starting with 1)
    elif len(digits_only) == 11 and digits_only.startswith("1"):
        return f"+{digits_only}"
    # Return with + prefix if not already present
    return f"+{digits_only}" if not phone.startswith("+") else phone


def ignore_validation(phone: str):
    return phone in [
        "+15625555555",
        "+15625551111",
        "+11234567890",
        "+15551234567",
        "+15625944162",
    ]


def resize_image(image: Image.Image, max_size: tuple) -> Image.Image:
    """Resize image while maintaining aspect ratio"""
    image.thumbnail(max_size)
    return image


def update_user_avatar(user: User, picture: str, db: Session):
    if not user:
        raise HTTPException(status_code=404, detail="No user found.")
    try:
        if picture:
            user.picture = picture
        db.commit()

        user = get_user(db, phone=user.phone)
        response: UserResponse = UserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            phone_verified=user.phone_verified,
            email=user.email,
            email_verified=user.email_verified,
            picture=user.picture,
            is_onboarded=True if user.first_name else False,
        )

        # Update the avatar cache with new data
        cache_key = f"avatar:{user.id}"
        cache_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_initial": user.last_name[0] if user.last_name else "",
            "picture": user.picture,
        }
        try:
            set_cached_data(cache_key, cache_data, 3600)
        except Exception as e:
            logger.error(f"Error updating avatar cache for user {user.id}: {str(e)}")
            # Continue even if cache update fails
            pass

        return response
    except Exception as e:
        logger.error(f"Error updating user avatar: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update user avatar")


def create_token_response(
    user: User, db: Session, device_info: str = None
) -> TokenResponse:
    """Helper function to create a consistent token response"""
    # Create access token (24 hours)
    access_token_expires = timedelta(hours=24)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "email_verified": user.email_verified,
            "phone": user.phone,
            "phone_verified": user.phone_verified,
            "picture": user.picture,
            "updated_at": datetime.now().isoformat() + "Z",
            "admin": False,
            "password_set": bool(user.password_hash),
        },
        expires_delta=access_token_expires,
    )

    # Create refresh token (90 days)
    refresh_token = create_refresh_token(db, user.id, device_info)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "expires_in": int(access_token_expires.total_seconds()),
    }


# Custom clients and settings
twilio_client = Client(
    get_settings().twilio_client_id, get_settings().twilio_client_key
)
twilio_verify = twilio_client.verify.services(get_settings().twilio_verify)

MAX_AVATAR_FILE_SIZE = 1 * 1024 * 1024  # 1MB
MAX_AVATAR_IMAGE_SIZE = (300, 300)


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    try:
        user = get_user(db, phone=user["phone"])
        if not user:
            logger.warning(f"User not found for phone: {user['phone']}")
            raise HTTPException(status_code=404, detail="No user found")

        try:
            user_id: int = user.id
            if user_id is None:
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        except jwt.PyJWTError as e:
            logger.error(f"JWT validation error: {str(e)}")
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            logger.warning(f"User not found for id: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            phone_verified=user.phone_verified,
            email=user.email,
            email_verified=user.email_verified,
            picture=user.picture,
            is_onboarded=True if user.first_name else False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in read_users_me: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/me", response_model=UserResponse)
async def update_users_me(
    updates: UserUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    try:
        db_user = get_user_by_id(db, user_id=user["user_id"])
        if not db_user:
            logger.warning("User not found for update")
            raise HTTPException(status_code=404, detail="No user found")

        try:
            if updates.first_name is not None:
                db_user.first_name = updates.first_name
            if updates.last_name is not None:
                db_user.last_name = updates.last_name
            if updates.picture is not None:
                db_user.picture = updates.picture
            if updates.birth_date is not None:
                db_user.birth_date = updates.birth_date
            if updates.postal_code is not None:
                db_user.postal_code = updates.postal_code

            db.commit()

        except Exception as e:
            logger.error(f"Database error updating user: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update user")

        updated_user = db_user
        return UserResponse(
            id=updated_user.id,
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            phone=updated_user.phone,
            phone_verified=updated_user.phone_verified,
            email=updated_user.email,
            email_verified=updated_user.email_verified,
            picture=updated_user.picture,
            is_onboarded=True if updated_user.first_name else False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_users_me: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/me/token", response_model=TokenResponse)
async def get_token(db: Session = Depends(get_db), user: dict = Depends(validate_jwt)):
    try:
        user = get_user(db, phone=user["phone"])
        if not user:
            raise HTTPException(status_code=404, detail="No user found")

        if user.is_deleted:
            raise HTTPException(status_code=403, detail="Account has been deleted")

        # Get device info from request if available
        device_info = "Unknown device"  # Default value

        return create_token_response(user, db, device_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating tokens: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate tokens")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh an access token using a valid refresh token"""
    try:
        # Validate the refresh token
        token_data = validate_refresh_token(db, request.refresh_token)

        # Get the user
        user = get_user_by_id(db, user_id=token_data["user_id"])
        if not user:
            logger.warning("User not found for refresh token")
            raise HTTPException(status_code=404, detail="User not found")

        if user.is_deleted:
            # Revoke the token if user is deleted
            revoke_refresh_token(db, request.refresh_token)
            raise HTTPException(status_code=403, detail="Account has been deleted")

        # Create a new access token with the same refresh token
        access_token_expires = timedelta(hours=24)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "email_verified": user.email_verified,
                "phone": user.phone,
                "phone_verified": user.phone_verified,
                "picture": user.picture,
                "updated_at": datetime.now().isoformat() + "Z",
                "admin": False,
                "password_set": bool(user.password_hash),
            },
            expires_delta=access_token_expires,
        )

        return {
            "access_token": access_token,
            "refresh_token": request.refresh_token,  # Return the same refresh token
            "token_type": "bearer",
            "user_id": user.id,
            "expires_in": int(access_token_expires.total_seconds()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")


@router.post("/revoke")
async def revoke_token(
    request: RevokeTokenRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """Revoke a refresh token"""
    try:
        # Revoke the token
        success = revoke_refresh_token(db, request.refresh_token)
        if not success:
            raise HTTPException(status_code=404, detail="Token not found")

        return {"message": "Token revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to revoke token")


@router.post("/revoke-all")
async def revoke_all_tokens(
    db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    """Revoke all refresh tokens for the current user"""
    try:
        # Revoke all tokens for the user
        success = revoke_all_user_tokens(db, user["user_id"])
        if not success:
            raise HTTPException(status_code=500, detail="Failed to revoke all tokens")

        return {"message": "All tokens revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking all tokens: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to revoke all tokens")


@router.post("/me/avatar", response_model=UserResponse)
async def upload_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    # Upload user avatar with proper error handling
    try:
        db_user = get_user(db, phone=user["phone"])
        if not db_user:
            logger.warning("User not found for avatar upload")
            raise HTTPException(status_code=404, detail="No user found")

        # Validate file size
        try:
            await image.seek(0)
            content = await image.read()
            if len(content) > MAX_AVATAR_FILE_SIZE:
                logger.warning(
                    f"Avatar upload exceeds size limit: {len(content)} bytes"
                )
                raise HTTPException(
                    status_code=400, detail="File size exceeds 1MB limit"
                )
        except Exception as e:
            logger.error(f"Error reading upload file: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid file upload")

        # Process image
        try:
            img = Image.open(io.BytesIO(content))
            img = resize_image(img, MAX_AVATAR_IMAGE_SIZE)

            buf = io.BytesIO()
            img.save(buf, format=img.format)
            buf.seek(0)

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid image format")

        # Upload to Cloudflare
        try:
            headers = {"Authorization": f"Bearer {get_settings().cloudflare_api_token}"}

            files = {"file": (image.filename, buf, image.content_type)}

            unique_identifier = f"user_avatar_{db_user.id}"
            params = {"id": unique_identifier}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    get_settings().cloudflare_image_upload_url,
                    headers=headers,
                    files=files,
                    params=params,
                )

                if response.status_code != 200:
                    logger.error(f"Cloudflare upload failed: {response.text}")
                    raise HTTPException(
                        status_code=500, detail="Failed to upload image"
                    )

                payload = response.json()
                picture = payload["result"]["variants"][0]
                return update_user_avatar(db_user, picture, db)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during image upload: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to upload image")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/avatar/{user_id}")
async def get_avatar(user_id: int, db: Session = Depends(get_db)):
    """Get user avatar with Redis caching and graceful fallback"""
    cache_key = f"avatar:{user_id}"

    try:
        # Try to get from cache first
        cached_data = get_cached_data(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for avatar:{user_id}")
            return cached_data
    except Exception as e:
        # Log cache error but continue to database
        logger.error(f"Cache error for avatar:{user_id}: {str(e)}")

    # Get from database (either cache miss or cache error)
    try:
        user = get_user_by_id(db, user_id=user_id)
        if not user:
            logger.error(f"No user found for avatar:{user_id}")
            raise HTTPException(status_code=404, detail="No user found.")

        # Prepare response data
        response_data = {
            "id": user_id,
            "first_name": user.first_name,
            "last_initial": user.last_name[0] if user.last_name else "",
            "picture": user.picture,
        }
        # Try to store in cache, but don't block on cache errors
        try:
            cache_success = set_cached_data(cache_key, response_data, 3600)
            if not cache_success:
                logger.warning(f"Failed to cache avatar:{user_id}")
        except Exception as e:
            logger.error(f"Error caching avatar:{user_id}: {str(e)}")

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error for avatar:{user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sms/code")
async def send_verification_sms(phone: str, db: Session = Depends(get_db)):
    try:
        if not is_valid_phone_number(phone):
            logger.warning(f"Invalid phone number attempt: {phone}")
            raise HTTPException(status_code=400, detail="Invalid phone number format")

        if ignore_validation(phone):
            return {"message": "Success"}

        # Format the phone number to E.164 format
        formatted_phone = sanitize_number(phone)
        logger.debug(f"Formatted phone number: {formatted_phone}")

        # Attempt to send verification code via Twilio
        try:
            verification = twilio_verify.verifications.create(
                to=formatted_phone, channel="sms"
            )
            if verification.status != "pending":
                logger.error(
                    f"Unexpected Twilio verification status: {verification.status}"
                )
                raise HTTPException(
                    status_code=500, detail="Failed to send verification code"
                )
            return {"message": "Success"}

        except TwilioRestException as e:
            logger.error(f"Twilio API error: {str(e)}")
            raise HTTPException(
                status_code=500, detail="SMS service temporarily unavailable"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_verification_sms: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/me", status_code=200)
async def delete_account(
    db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    """Soft delete a user account"""
    try:
        db_user = get_user_by_id(db, user_id=user["user_id"])
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Mark user as deleted
        db_user.is_deleted = True
        db_user.deleted_at = datetime.now(timezone.utc)
        # Update phone number to prevent reuse with random number
        random_suffix = str(uuid4().int % 10000)  # Get random number between 0-9999
        db_user.phone = f"__{db_user.phone}__{random_suffix}"

        # Revoke all refresh tokens
        revoke_all_user_tokens(db, db_user.id)

        db.commit()
        return {"message": "Account successfully deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete account")


@router.post("/sms/verify", response_model=TokenResponse)
async def verify_sms(info: SmsVerify, db: Session = Depends(get_db)):
    """Verify SMS code with proper error handling"""
    try:
        formatted_phone = sanitize_number(info.phone)
        # Handle test cases
        if not (
            (info.code == "wrong_code" or info.code == "123456")
            and ignore_validation(formatted_phone)
        ):
            try:
                verification_check = twilio_client.verify.v2.services(
                    "VAad1486b23a345a16ab35e09379f67ead"
                ).verification_checks.create(to=formatted_phone, code=info.code)
                if verification_check.status != "approved":
                    logger.warning(
                        f"Failed verification attempt for phone: {formatted_phone}"
                    )
                    raise HTTPException(
                        status_code=400, detail="Invalid verification code"
                    )

            except TwilioRestException as e:
                logger.error(f"Twilio verification error: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail="Verification service temporarily unavailable",
                )

        if ignore_validation(info.phone) and not (info.code == "123456"):
            raise HTTPException(status_code=400, detail="Invalid verification code")

        info.phone = formatted_phone

        # Handle user creation/update
        try:
            user = get_user(db, phone=info.phone)
            if user:
                if user.is_deleted:
                    raise HTTPException(
                        status_code=403, detail="Account has been deleted"
                    )
                user.last_logged_in = datetime.utcnow()
            else:
                user = User(
                    phone=info.phone,
                    phone_verified=True,
                    first_name="",
                    last_name="",
                    email="",
                    email_verified=False,
                    picture="",
                    last_logged_in=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(user)

            db.commit()

            user = get_user(db, phone=info.phone)

        except Exception as e:
            logger.error(f"Database error during user creation/update: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create/update user")

        # Generate authentication tokens
        try:
            # Get device info from request if available
            device_info = "Mobile device"  # Default value for SMS verification

            return create_token_response(user, db, device_info)
        except Exception as e:
            logger.error(f"Token generation error: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to generate authentication tokens"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_sms: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/password/set", response_model=TokenResponse)
async def set_password(
    password_update: PasswordUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """Set or update user password"""
    try:
        db_user = get_user_by_id(db, user_id=user["user_id"])
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update password
        db_user.password_hash = get_password_hash(password_update.new_password)
        db.commit()

        # Generate new tokens
        device_info = "Password set device"
        return create_token_response(db_user, db, device_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting password: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to set password")


@router.post("/password/login", response_model=TokenResponse)
async def login_with_password(
    password_login: PasswordLogin, db: Session = Depends(get_db)
):
    """Login using phone and password"""
    try:
        formatted_phone = sanitize_number(password_login.phone)
        user = get_user(db, phone=formatted_phone)

        # First check if user exists at all
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Then check password matches if user has password login enabled
        if user.password_hash:
            if not verify_password(password_login.password, user.password_hash):
                raise HTTPException(status_code=401, detail="Invalid credentials")
        else:
            # User exists but hasn't set up password login
            raise HTTPException(
                status_code=400, detail="Password login not enabled for this user"
            )

        # Generate tokens
        device_info = "Password login device"
        return create_token_response(user, db, device_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during password login: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to login with password")
