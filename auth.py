from datetime import datetime
from datetime import timedelta
import secrets
import uuid

import bcrypt
import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy.orm import Session

from env import get_settings
from memcache import get_redis, get_cached_data, set_cached_data
from models import User, RefreshToken

SECRET_KEY = get_settings().auth_secret_key
ALGORITHM = get_settings().auth_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = get_settings().auth_access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = 90  # 90 days for refresh token

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def validate_jwt(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get("sub")
        payload["token"] = token
        if id is None:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"Error validating jwt: {str(e)}")
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


def get_user(db, phone: str):
    return db.query(User).filter(User.phone == phone).first()


def get_user_by_id(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def generate_refresh_token() -> str:
    """Generate a secure random refresh token"""
    return f"{uuid.uuid4()}-{secrets.token_hex(32)}"


def create_refresh_token(db: Session, user_id: int, device_info: str = None) -> str:
    """
    Create a new refresh token for a user and store it in the database and Redis

    Args:
        db: Database session
        user_id: User ID
        device_info: Optional device information

    Returns:
        The refresh token string
    """
    # Generate a secure token
    token = generate_refresh_token()

    # Calculate expiration date (90 days from now)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Create database record
    refresh_token = RefreshToken(
        user_id=user_id,
        token=token,
        device_info=device_info,
        expires_at=expires_at,
        is_revoked=False,
    )

    try:
        db.add(refresh_token)
        db.commit()

        # Also store in Redis for faster lookups with TTL
        redis = get_redis()
        if redis:
            # Store token in Redis with expiration
            token_key = f"refresh_token:{token}"
            token_data = {
                "user_id": user_id,
                "is_revoked": False,
                "created_at": datetime.utcnow().isoformat(),
            }
            # Convert timedelta to seconds for Redis TTL
            ttl_seconds = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            set_cached_data(token_key, token_data, ttl_seconds)

            # Also maintain a set of user's active tokens
            user_tokens_key = f"user_refresh_tokens:{user_id}"
            try:
                # Get existing tokens or create empty list
                user_tokens = get_cached_data(user_tokens_key) or []
                user_tokens.append(token)
                set_cached_data(user_tokens_key, user_tokens, ttl_seconds)
            except Exception as e:
                logger.error(f"Redis error storing user tokens: {str(e)}")

        return token
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating refresh token: {str(e)}")
        raise


def validate_refresh_token(db: Session, token: str) -> dict:
    """
    Validate a refresh token and return the associated user data

    Args:
        db: Database session
        token: Refresh token to validate

    Returns:
        Dict with user_id if valid

    Raises:
        HTTPException: If token is invalid, expired or revoked
    """
    # First check Redis for faster validation
    redis = get_redis()
    if redis:
        token_key = f"refresh_token:{token}"
        token_data = get_cached_data(token_key)

        if token_data:
            # Check if token is revoked in Redis
            if token_data.get("is_revoked", False):
                logger.warning(f"Attempt to use revoked token: {token[:10]}...")
                raise HTTPException(status_code=401, detail="Token has been revoked")

            # If valid in Redis, update last_used in database
            try:
                refresh_token = (
                    db.query(RefreshToken).filter(RefreshToken.token == token).first()
                )

                if refresh_token:
                    refresh_token.last_used_at = datetime.utcnow()
                    db.commit()

                    return {"user_id": token_data["user_id"]}
            except Exception as e:
                logger.error(f"Database error updating token usage: {str(e)}")
                # Continue with validation even if update fails

    # If not in Redis or Redis unavailable, check database
    try:
        refresh_token = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == token,
                RefreshToken.is_revoked == False,  # noqa
                RefreshToken.expires_at > datetime.utcnow(),
            )
            .first()
        )

        if not refresh_token:
            logger.warning(f"Invalid or expired refresh token: {token[:10]}...")
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Update last used timestamp
        refresh_token.last_used_at = datetime.utcnow()
        db.commit()

        # If Redis is available, update cache
        if redis:
            token_key = f"refresh_token:{token}"
            token_data = {
                "user_id": refresh_token.user_id,
                "is_revoked": False,
                "created_at": refresh_token.created_at.isoformat(),
            }
            # Calculate remaining TTL
            remaining_seconds = (
                refresh_token.expires_at - datetime.utcnow()
            ).total_seconds()
            if remaining_seconds > 0:
                set_cached_data(token_key, token_data, int(remaining_seconds))

        return {"user_id": refresh_token.user_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating refresh token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")


def revoke_refresh_token(db: Session, token: str) -> bool:
    """
    Revoke a refresh token

    Args:
        db: Database session
        token: Refresh token to revoke

    Returns:
        True if successful, False otherwise
    """
    try:
        refresh_token = (
            db.query(RefreshToken).filter(RefreshToken.token == token).first()
        )

        if not refresh_token:
            return False

        # Mark as revoked in database
        refresh_token.is_revoked = True
        db.commit()

        # Also update Redis if available
        redis = get_redis()
        if redis:
            token_key = f"refresh_token:{token}"
            token_data = get_cached_data(token_key)

            if token_data:
                token_data["is_revoked"] = True
                # Keep the same TTL
                remaining_seconds = (
                    refresh_token.expires_at - datetime.utcnow()
                ).total_seconds()
                if remaining_seconds > 0:
                    set_cached_data(token_key, token_data, int(remaining_seconds))

            # Also add to blacklist for extra security
            blacklist_key = f"token_blacklist:{token}"
            set_cached_data(
                blacklist_key,
                {"revoked_at": datetime.utcnow().isoformat()},
                int(remaining_seconds),
            )

        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error revoking refresh token: {str(e)}")
        return False


def revoke_all_user_tokens(db: Session, user_id: int) -> bool:
    """
    Revoke all refresh tokens for a user

    Args:
        db: Database session
        user_id: User ID

    Returns:
        True if successful, False otherwise
    """
    try:
        # Mark all tokens as revoked in database
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa
        ).update({"is_revoked": True})

        db.commit()

        # Also update Redis if available
        redis = get_redis()
        if redis:
            # Get user's tokens from Redis
            user_tokens_key = f"user_refresh_tokens:{user_id}"
            user_tokens = get_cached_data(user_tokens_key) or []

            # Revoke each token in Redis
            for token in user_tokens:
                token_key = f"refresh_token:{token}"
                token_data = get_cached_data(token_key)

                if token_data:
                    token_data["is_revoked"] = True
                    # Keep same TTL
                    set_cached_data(token_key, token_data, 3600 * 24)  # 24 hours

                # Add to blacklist
                blacklist_key = f"token_blacklist:{token}"
                set_cached_data(
                    blacklist_key,
                    {"revoked_at": datetime.utcnow().isoformat()},
                    3600 * 24 * 7,
                )  # 7 days

            # Clear the user's token list
            set_cached_data(user_tokens_key, [], 1)  # Short TTL to clear

        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error revoking all user tokens: {str(e)}")
        return False
