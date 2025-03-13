# Services Documentation

This document provides an overview of the services used in the FastAPI Template.

## Overview

The services directory contains modules that implement the business logic of the application. Each service is responsible for a specific domain of functionality and is implemented as a FastAPI router.

## Service Structure

Each service follows a similar structure:

1. Define a FastAPI router
2. Define API endpoints as router methods
3. Implement business logic
4. Handle errors and return appropriate responses

## Core Services

### User Service

The user service (`services/users.py`) handles user authentication, profile management, and related operations. It includes endpoints for:

- User registration
- User authentication
- User profile management
- Password management
- Device token management

Example endpoint:

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
```

### Item Service

The item service (`services/items.py`) is a generic example service that demonstrates CRUD operations for a simple item model. It includes endpoints for:

- Creating items
- Reading items
- Updating items
- Deleting items

Example endpoint:

```python
@router.post("/", response_model=ItemResponse)
async def create_item(
    item: ItemCreate, db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    """
    Create a new item for the authenticated user.
    """
    try:
        db_item = Item(
            user_id=user["user_id"],
            title=item.title,
            description=item.description,
            data=item.data,
            is_active=True,
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    except Exception as e:
        logger.error(f"Error creating item: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create item")
```

### Notification Service

The notification service (`services/notifications.py`) handles notification management. It includes endpoints for:

- Getting notifications
- Marking notifications as read

Example endpoint:

```python
@router.get("/")
async def get_notifications(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """
    Get notifications for the authenticated user.
    """
    try:
        user_id = user["user_id"]
        notifications = (
            db.query(Notification)
            .filter(Notification.users.any(user_id))
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": notification.id,
                "event": notification.event,
                "message": notification.message,
                "created_at": notification.created_at,
                "sent_status": notification.sent_status,
            }
            for notification in notifications
        ]
    except Exception as e:
        logger.error(f"Error retrieving notifications: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve notifications")
```

### Webhook Service

The webhook service (`services/webhooks.py`) handles webhook integration for receiving and processing external events. It includes endpoints for:

- Receiving webhooks
- Registering webhooks

Example endpoint:

```python
@router.post("/incoming")
async def receive_webhook(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Receive and process incoming webhooks from external services.
    This is a generic implementation that can be customized based on your needs.
    
    The x-webhook-signature header can be used to verify the authenticity of the webhook.
    """
    try:
        # Get the raw request body
        body = await request.body()
        
        # Parse the JSON payload
        payload = await request.json()
        
        # Log the webhook
        logger.info(f"Received webhook: {payload}")
        
        # Here you would implement webhook signature verification if needed
        if x_webhook_signature:
            # Verify the webhook signature
            # This is a placeholder for actual signature verification
            logger.debug(f"Webhook signature: {x_webhook_signature}")
            
            # Example verification (replace with your actual verification logic)
            # if not verify_signature(body, x_webhook_signature):
            #     raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Process the webhook based on its type
        webhook_type = payload.get("type")
        if not webhook_type:
            raise HTTPException(status_code=400, detail="Missing webhook type")
        
        # Handle different webhook types
        if webhook_type == "example_event":
            # Process example event
            return process_example_event(payload, db)
        else:
            # Unknown webhook type
            logger.warning(f"Unknown webhook type: {webhook_type}")
            return {"status": "ignored", "reason": "Unknown webhook type"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")
```

## Adding a New Service

To add a new service:

1. Create a new file in the `services/` directory
2. Define a FastAPI router
3. Implement your service endpoints
4. Add the router to `server.py`

Example:

```python
# services/my_service.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from auth import validate_jwt
from db import get_db
from models import MyModel, MyModelCreate, MyModelResponse

router = APIRouter()


@router.post("/", response_model=MyModelResponse)
async def create_my_model(
    model: MyModelCreate, db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    """
    Create a new model for the authenticated user.
    """
    try:
        db_model = MyModel(
            user_id=user["user_id"],
            # Set other fields from model
        )
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model
    except Exception as e:
        logger.error(f"Error creating model: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create model")


@router.get("/", response_model=List[MyModelResponse])
async def get_my_models(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """
    Get all models for the authenticated user.
    """
    try:
        models = (
            db.query(MyModel)
            .filter(MyModel.user_id == user["user_id"])
            .offset(skip)
            .limit(limit)
            .all()
        )
        return models
    except Exception as e:
        logger.error(f"Error retrieving models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve models")
```

Then add the router to `server.py`:

```python
from services.my_service import router as my_service_router

# ...

app.include_router(my_service_router, prefix="/my-models", tags=["my-models"])
```

## Best Practices

When implementing services, follow these best practices:

1. **Separation of Concerns**: Each service should focus on a specific domain of functionality.
2. **Error Handling**: Use try-except blocks to catch and handle errors appropriately.
3. **Logging**: Use the logger to log important events and errors.
4. **Authentication**: Use the `validate_jwt` dependency to protect endpoints that require authentication.
5. **Database Access**: Use the `get_db` dependency to get a database session.
6. **Response Models**: Define Pydantic models for API responses to ensure consistent and validated responses.
7. **Documentation**: Add docstrings to endpoints to document their purpose and usage.
