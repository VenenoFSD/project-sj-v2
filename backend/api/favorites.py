from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.services import favorite_service, product_service

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.get("")
def get_favorites(user_id: str = Query("default"), db: Session = Depends(get_db)):
    # 收藏列表要渲染商品卡片，所以商品字段与 `/api/products` 保持一致（含最新价格快照）。
    items = []
    for favorite in favorite_service.list_favorites(db, user_id):
        product = product_service.get_product_by_id(db, favorite.product_id)
        if product:
            items.append({
                "id": favorite.id,
                "user_id": user_id,
                "created_at": favorite.created_at,
                "product": product_service.product_payload(product, product_service.get_latest_snapshot(db, product.id)),
            })
    return {"items": items}

@router.post("/{cluster_id}")
def add_product_favorite(cluster_id: str, user_id: str = Query("default"), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    favorite_service.add_favorite(db, product.id, user_id)
    return {"cluster_id": cluster_id, "user_id": user_id, "favorited": True}

@router.delete("/{cluster_id}")
def delete_product_favorite(cluster_id: str, user_id: str = Query("default"), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    favorite_service.remove_favorite(db, product.id, user_id)
    return {"cluster_id": cluster_id, "user_id": user_id, "favorited": False}
