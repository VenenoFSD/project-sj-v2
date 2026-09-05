import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


def product_payload(product, current_snapshot=None):
    payload = {
        "cluster_id": product.cluster_id,
        "title": product.title,
        "category": product.category,
        "img": product.img,
        "url": product.url,
        "first_seen_at": product.first_seen_at,
        "last_seen_at": product.last_seen_at,
        "is_active": product.is_active,
    }
    if current_snapshot is not None:
        payload.update({
            "price": current_snapshot.price,
            "reference_price": current_snapshot.reference_price,
            "discount": current_snapshot.discount,
            "popularity": current_snapshot.popularity,
            "captured_at": current_snapshot.captured_at,
        })
    return payload


@router.get("")
def get_products(
    category: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    products = product_service.list_products(db, category, limit, offset)
    return {"items": [product_payload(product) for product in products], "limit": limit, "offset": offset}


@router.get("/{cluster_id}")
def get_product(cluster_id: str, db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    history = product_service.list_product_history(db, product.id, 1)
    return product_payload(product, history[0] if history else None)


@router.get("/{cluster_id}/history")
def get_product_history(
    cluster_id: str,
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    history = product_service.list_product_history(db, product.id, limit)
    return {"cluster_id": cluster_id, "items": [
        {
            "price": item.price,
            "reference_price": item.reference_price,
            "discount": item.discount,
            "popularity": item.popularity,
            "captured_at": item.captured_at,
        } for item in history
    ]}


@router.get("/{cluster_id}/details")
def get_product_details(cluster_id: str, db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    row = product_service.get_latest_detail(db, product.id)
    if row is None:
        return {"cluster_id": cluster_id, "detail": None}
    return {
        "cluster_id": cluster_id,
        "lowest_price": row.lowest_price,
        "latest_deal_price": row.latest_deal_price,
        "price_tag": json.loads(row.price_tag or "{}"),
        "attributes": json.loads(row.attributes or "[]"),
        "images": json.loads(row.images or "[]"),
        "captured_at": row.captured_at,
    }

@router.get("/{cluster_id}/deals")
def get_product_deals(cluster_id: str, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"cluster_id": cluster_id, "items": product_service.list_product_deals(db, product.id, limit)}

@router.get("/{cluster_id}/price-points")
def get_product_price_points(cluster_id: str, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"cluster_id": cluster_id, "items": product_service.list_product_price_points(db, product.id, limit)}
