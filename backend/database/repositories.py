from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from datetime import datetime
import json
from backend.database.models import CrawlRun, Product, ProductSnapshot, Favorite, ProductDeal, ProductPricePoint


def list_products(db: Session, category: str | None, limit: int, offset: int):
    query = select(Product).where(Product.is_active.is_(True))
    if category:
        query = query.where(Product.category == category)
    return list(db.scalars(query.order_by(desc(Product.last_seen_at)).limit(limit).offset(offset)))


def get_product(db: Session, cluster_id: str):
    return db.scalar(select(Product).where(Product.cluster_id == cluster_id))

def get_product_by_id(db: Session, product_id: int):
    return db.get(Product, product_id)


def list_product_history(db: Session, product_id: int, limit: int):
    query = select(ProductSnapshot).where(ProductSnapshot.product_id == product_id)
    return list(db.scalars(query.order_by(desc(ProductSnapshot.captured_at)).limit(limit)))


def list_crawl_runs(db: Session, limit: int, offset: int):
    query = select(CrawlRun).order_by(desc(CrawlRun.started_at)).limit(limit).offset(offset)
    return list(db.scalars(query))

def list_json_rows(db: Session, model, product_id: int, limit: int):
    rows = db.scalars(select(model).where(model.product_id == product_id).order_by(desc(model.captured_at), desc(model.id)).limit(limit))
    field = "deal_json" if model is ProductDeal else "point_json"
    return [json.loads(getattr(row, field)) for row in rows]

def get_latest_detail(db: Session, product_id: int):
    from backend.database.models import ProductDetail
    return db.scalar(select(ProductDetail).where(ProductDetail.product_id == product_id).order_by(desc(ProductDetail.captured_at), desc(ProductDetail.id)))

def list_product_deals(db: Session, product_id: int, limit: int):
    return list_json_rows(db, ProductDeal, product_id, limit)

def list_product_price_points(db: Session, product_id: int, limit: int):
    return list_json_rows(db, ProductPricePoint, product_id, limit)

def list_favorites(db: Session, user_id: str):
    return list(db.scalars(select(Favorite).where(Favorite.user_id == user_id).order_by(desc(Favorite.created_at))))

def add_favorite(db: Session, product_id: int, user_id: str):
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.product_id == product_id))
    if favorite:
        return favorite
    favorite = Favorite(user_id=user_id, product_id=product_id, created_at=datetime.now().isoformat(timespec="microseconds"))
    db.add(favorite); db.flush(); return favorite

def remove_favorite(db: Session, product_id: int, user_id: str):
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.product_id == product_id))
    if favorite: db.delete(favorite); return True
    return False
