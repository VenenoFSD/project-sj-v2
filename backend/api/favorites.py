from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.database import repositories
from backend.services import product_service

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.get("")
def get_favorites(user_id: str = Query("default"), db: Session = Depends(get_db)):
    items = []
    for fav in repositories.list_favorites(db, user_id):
        product = repositories.get_product_by_id(db, fav.product_id)
        if product:
            items.append({"id": fav.id, "user_id": user_id, "created_at": fav.created_at, "product": {"cluster_id": product.cluster_id, "title": product.title, "img": product.img, "url": product.url}})
    return {"items": items}

@router.post("/{cluster_id}")
def add_product_favorite(cluster_id: str, user_id: str = Query("default"), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    repositories.add_favorite(db, product.id, user_id)
    return {"cluster_id": cluster_id, "user_id": user_id, "favorited": True}

@router.delete("/{cluster_id}")
def delete_product_favorite(cluster_id: str, user_id: str = Query("default"), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    repositories.remove_favorite(db, product.id, user_id)
    return {"cluster_id": cluster_id, "user_id": user_id, "favorited": False}
