from sqlalchemy.orm import Session

from backend.database import repositories


def product_payload(product, current_snapshot=None):
    """商品的接口返回结构。商品列表和收藏列表共用，避免两个接口的商品字段各长一套。"""
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


def list_products(db: Session, category: str | None, ip: str | None, search: str | None, sort: str | None, limit: int, offset: int):
    return repositories.list_products(db, category, ip, search, sort, limit, offset)

def count_products(db: Session, category: str | None, ip: str | None, search: str | None):
    return repositories.count_products(db, category, ip, search)


def get_product(db: Session, cluster_id: str):
    return repositories.get_product(db, cluster_id)

def get_product_by_id(db: Session, product_id: int):
    return repositories.get_product_by_id(db, product_id)


def list_product_history(db: Session, product_id: int, limit: int):
    return repositories.list_product_history(db, product_id, limit)

def get_latest_snapshot(db: Session, product_id: int):
    return repositories.get_latest_snapshot(db, product_id)

def get_latest_detail(db: Session, product_id: int):
    return repositories.get_latest_detail(db, product_id)

def list_product_deals(db: Session, product_id: int, limit: int):
    return repositories.list_product_deals(db, product_id, limit)

def list_product_price_points(db: Session, product_id: int, limit: int):
    return repositories.list_product_price_points(db, product_id, limit)
