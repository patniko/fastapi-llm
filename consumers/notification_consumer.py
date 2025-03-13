import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from db import SessionLocal
from models import Notification


async def process_notifications():
    """
    Process pending notifications.
    This is a generic implementation that can be customized based on your needs.
    """
    try:
        db = SessionLocal()
        try:
            # Get unsent notifications
            notifications = (
                db.query(Notification)
                .filter(Notification.sent_status == False)  # noqa
                .order_by(Notification.created_at.asc())
                .limit(100)
                .all()
            )

            if not notifications:
                logger.debug("No pending notifications to process")
                return

            logger.info(f"Processing {len(notifications)} pending notifications")

            # Process each notification
            for notification in notifications:
                try:
                    # Here you would implement your notification delivery logic
                    # For example, sending push notifications, emails, etc.
                    
                    # This is a placeholder for actual notification delivery
                    logger.info(
                        f"Sending notification {notification.id} to users {notification.users}: "
                        f"{notification.event} - {notification.message}"
                    )
                    
                    # Simulate successful delivery
                    notification.sent_status = True
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing notification {notification.id}: {str(e)}")
                    db.rollback()
                    continue

            logger.info("Notification processing completed")

        except Exception as e:
            logger.error(f"Error in notification processing: {str(e)}")
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Critical error in notification processing: {str(e)}")


async def send_notification_to_user(user_id: int, event: str, message: str):
    """
    Helper function to send a notification to a specific user.
    This can be called from other services.
    """
    try:
        db = SessionLocal()
        try:
            notification = Notification(
                users=[user_id],
                event=event,
                message=message,
                created_at=datetime.utcnow(),
                sent_status=False,
            )
            db.add(notification)
            db.commit()
            logger.debug(f"Created notification for user {user_id}: {event} - {message}")
            return notification
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            db.rollback()
            return None
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Critical error creating notification: {str(e)}")
        return None


if __name__ == "__main__":
    # For testing
    asyncio.run(process_notifications())
