from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, aliased

from datetime import datetime
import json
from backend.database.models import CrawlRun, Product, ProductSnapshot, Favorite, ProductDeal, ProductPricePoint, ScheduledCrawl


def list_products(db: Session, category: str | None, search: str | None, sort: str | None, limit: int, offset: int):
    query = select(Product).where(Product.is_active.is_(True))
    if category:
        query = query.where(Product.category == category)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    if sort:
        latest_snapshot = aliased(ProductSnapshot)
        latest_snapshot_id = (
            select(ProductSnapshot.id)
            .where(ProductSnapshot.product_id == Product.id)
            .order_by(desc(ProductSnapshot.captured_at), desc(ProductSnapshot.id))
            .limit(1)
            .scalar_subquery()
        )
        query = query.outerjoin(latest_snapshot, latest_snapshot.id == latest_snapshot_id)
        if sort == "price":
            sort_value = latest_snapshot.price
        else:
            sort_value = latest_snapshot.price / func.nullif(latest_snapshot.reference_price, 0)
        query = query.order_by(
            sort_value.is_(None),
            sort_value.asc(),
            desc(Product.last_seen_at),
            Product.id.asc(),
        )
    else:
        query = query.order_by(desc(Product.last_seen_at), Product.id.asc())
    return list(db.scalars(query.limit(limit).offset(offset)))

def count_products(db: Session, category: str | None, search: str | None):
    query = select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    if category:
        query = query.where(Product.category == category)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    return db.scalar(query) or 0


def get_product(db: Session, cluster_id: str):
    return db.scalar(select(Product).where(Product.cluster_id == cluster_id))

def get_product_by_id(db: Session, product_id: int):
    return db.get(Product, product_id)


def list_product_history(db: Session, product_id: int, limit: int):
    query = select(ProductSnapshot).where(ProductSnapshot.product_id == product_id)
    return list(db.scalars(query.order_by(desc(ProductSnapshot.captured_at)).limit(limit)))

def get_latest_snapshot(db: Session, product_id: int):
    query = select(ProductSnapshot).where(ProductSnapshot.product_id == product_id).order_by(desc(ProductSnapshot.captured_at), desc(ProductSnapshot.id)).limit(1)
    return db.scalar(query)


def list_crawl_runs(db: Session, limit: int, offset: int):
    query = select(CrawlRun).order_by(desc(CrawlRun.started_at)).limit(limit).offset(offset)
    return list(db.scalars(query))

def create_scheduled_crawl(db: Session, *, name: str | None, interval_seconds: int, crawl_params: str, created_at: str):
    schedule = ScheduledCrawl(
        name=name,
        enabled=True,
        interval_seconds=interval_seconds,
        crawl_params=crawl_params,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(schedule)
    db.flush()
    return schedule

def get_scheduled_crawl(db: Session, schedule_id: int):
    return db.get(ScheduledCrawl, schedule_id)

def list_scheduled_crawls(db: Session):
    return list(db.scalars(select(ScheduledCrawl).order_by(ScheduledCrawl.id.asc())))

def list_enabled_scheduled_crawls(db: Session):
    return list(db.scalars(select(ScheduledCrawl).where(ScheduledCrawl.enabled.is_(True)).order_by(ScheduledCrawl.id.asc())))

def update_scheduled_crawl(db: Session, schedule_id: int, *, updated_at: str, **fields):
    schedule = get_scheduled_crawl(db, schedule_id)
    if schedule is None:
        return None
    for field, value in fields.items():
        setattr(schedule, field, value)
    schedule.updated_at = updated_at
    db.flush()
    return schedule

def delete_scheduled_crawl(db: Session, schedule_id: int):
    schedule = get_scheduled_crawl(db, schedule_id)
    if schedule is None:
        return False
    db.delete(schedule)
    db.flush()
    return True

_UNSET = object()

def update_scheduled_crawl_run(db: Session, schedule_id: int, *, expected_task_id=_UNSET, last_run_at=_UNSET, last_task_id=_UNSET, last_status=_UNSET, last_error=_UNSET, last_finished_at=_UNSET, next_run_at=_UNSET):
    schedule = get_scheduled_crawl(db, schedule_id)
    if schedule is None:
        return None
    if expected_task_id is not _UNSET and schedule.last_task_id != expected_task_id:
        return None
    fields = {
        "last_run_at": last_run_at,
        "last_task_id": last_task_id,
        "last_status": last_status,
        "last_error": last_error,
        "last_finished_at": last_finished_at,
        "next_run_at": next_run_at,
    }
    for field, value in fields.items():
        if value is not _UNSET:
            setattr(schedule, field, value)
    db.flush()
    return schedule

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
