from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from auth import validate_jwt
from db import get_db
from models import Item, ItemCreate, ItemResponse, ItemUpdate

router = APIRouter()


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


@router.get("/", response_model=List[ItemResponse])
async def get_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """
    Get all items for the authenticated user.
    """
    try:
        items = (
            db.query(Item)
            .filter(Item.user_id == user["user_id"])
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items
    except Exception as e:
        logger.error(f"Error retrieving items: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve items")


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int, db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    """
    Get a specific item by ID.
    """
    try:
        item = (
            db.query(Item)
            .filter(Item.id == item_id, Item.user_id == user["user_id"])
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving item: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve item")


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    item_update: ItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(validate_jwt),
):
    """
    Update an existing item.
    """
    try:
        db_item = (
            db.query(Item)
            .filter(Item.id == item_id, Item.user_id == user["user_id"])
            .first()
        )
        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Update fields if provided
        if item_update.title is not None:
            db_item.title = item_update.title
        if item_update.description is not None:
            db_item.description = item_update.description
        if item_update.data is not None:
            db_item.data = item_update.data
        if item_update.is_active is not None:
            db_item.is_active = item_update.is_active

        db.commit()
        db.refresh(db_item)
        return db_item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating item: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update item")


@router.delete("/{item_id}")
async def delete_item(
    item_id: int, db: Session = Depends(get_db), user: dict = Depends(validate_jwt)
):
    """
    Delete an item.
    """
    try:
        db_item = (
            db.query(Item)
            .filter(Item.id == item_id, Item.user_id == user["user_id"])
            .first()
        )
        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        db.delete(db_item)
        db.commit()
        return {"message": "Item deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete item")
