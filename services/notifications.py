from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from auth import validate_jwt
from db import get_db
from models import Notification

router = APIRouter()


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


@router.post("/mark-read/{notification_id}")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """
    Mark a notification as read.
    """
    try:
        user_id = user["user_id"]
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.users.any(user_id))
            .first()
        )
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        notification.sent_status = True
        db.commit()
        
        return {"message": "Notification marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")


def create_notification(db: Session, users: List[int], event: str, message: str):
    """
    Create a notification for specified users.
    This function can be called from other services.
    """
    try:
        notification = Notification(
            users=users,
            event=event,
            message=message,
            sent_status=False,
        )
        db.add(notification)
        db.commit()
        return notification
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}")
        db.rollback()
        return None
