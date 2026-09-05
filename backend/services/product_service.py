from sqlalchemy.orm import Session

from backend.database import repositories


def list_products(db: Session, category: str | None, limit: int, offset: int):
    return repositories.list_products(db, category, limit, offset)


def get_product(db: Session, cluster_id: str):
    return repositories.get_product(db, cluster_id)


def list_product_history(db: Session, product_id: int, limit: int):
    return repositories.list_product_history(db, product_id, limit)

def get_latest_detail(db: Session, product_id: int):
    return repositories.get_latest_detail(db, product_id)

def list_product_deals(db: Session, product_id: int, limit: int):
    return repositories.list_product_deals(db, product_id, limit)

def list_product_price_points(db: Session, product_id: int, limit: int):
    return repositories.list_product_price_points(db, product_id, limit)
