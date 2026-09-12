import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


def parse_json(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


@router.get("")
def get_products(
    category: str | None = None,
    ip: str | None = Query(None, max_length=100),
    search: str | None = Query(None, max_length=100),
    sort: str | None = Query(None, pattern="^(price|discount)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    products = product_service.list_products(db, category, ip, search, sort, limit, offset)
    return {"items": [product_service.product_payload(product, product_service.get_latest_snapshot(db, product.id)) for product in products], "total": product_service.count_products(db, category, ip, search), "limit": limit, "offset": offset}


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
        "price_tag": parse_json(row.price_tag, {}),
        "attributes": [{"name": item.get("attrName", ""), "value": item.get("attrValue", "")} for item in parse_json(row.attributes, [])],
        "images": parse_json(row.images, []),
        "captured_at": row.captured_at,
    }

@router.get("/{cluster_id}/deals")
def get_product_deals(cluster_id: str, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    items = product_service.list_product_deals(db, product.id, limit)
    return {"cluster_id": cluster_id, "items": [{"user_avatar": item.get("userAvatar"), "user_name": item.get("userName"), "deal_price": item.get("dealPrice"), "deal_time": item.get("dealTime")} for item in items]}

@router.get("/{cluster_id}/price-points")
def get_product_price_points(cluster_id: str, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    product = product_service.get_product(db, cluster_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    items = product_service.list_product_price_points(db, product.id, limit)
    return {"cluster_id": cluster_id, "items": [{"date_label": item.get("dateLabel"), "avg_price": item.get("avgPrice"), "volume": item.get("volume")} for item in items]}
