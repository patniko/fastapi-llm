# Authentication Documentation

This document provides an overview of the authentication system used in the FastAPI Template.

## Authentication Flow

The application uses JWT (JSON Web Tokens) for authentication with refresh tokens for maintaining long-lived sessions. The authentication flow is as follows:

1. User logs in with credentials (email/phone and password)
2. Server validates credentials and generates an access token and refresh token
3. Client stores both tokens
4. Client includes the access token in the Authorization header for API requests
5. When the access token expires, client uses the refresh token to get a new access token
6. If the refresh token expires or is revoked, user must log in again

## Authentication Components

### JWT Tokens

JWT tokens are used for authentication. The tokens are signed using a secret key and contain the user's ID and other claims.

### Refresh Tokens

Refresh tokens are used to obtain new access tokens when they expire. Refresh tokens are stored in the database and can be revoked.

### Password Hashing

Passwords are hashed using bcrypt before being stored in the database.

## Implementation

The authentication system is implemented in `auth.py`. Here's an overview of the key functions:

### Password Hashing

```python
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
```

### JWT Token Generation

```python
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
```

### JWT Token Validation

```python
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
```

### Refresh Token Management

```python
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
```

```python
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
```

## API Endpoints

The authentication API endpoints are implemented in `services/users.py`. Here's an overview of the key endpoints:

### Login with Password

```python
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
```

### Refresh Token

```python
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
```

### Revoke Token

```python
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
```

## Using Authentication in API Endpoints

To protect an API endpoint with authentication, use the `validate_jwt` dependency:

```python
@router.get("/me", response_model=UserResponse)
async def read_users_me(
    db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    try:
        user = get_user(db, phone=user["phone"])
        if not user:
            logger.warning(f"User not found for phone: {user['phone']}")
            raise HTTPException(status_code=404, detail="No user found")

        # ... rest of the function
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in read_users_me: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

The `validate_jwt` function will extract the user information from the JWT token and make it available in the `user` parameter.
