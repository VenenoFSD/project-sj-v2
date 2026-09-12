from sqlalchemy import desc, func, or_, select, true
from sqlalchemy.orm import Session, aliased

from datetime import datetime
import json
from backend.database.models import CrawlRun, Product, ProductDetail, ProductSnapshot, Favorite, ProductDeal, ProductPricePoint, ScheduledCrawl

# IP 分区不是 `products` 的列：爬虫只把它作为请求筛选条件发出去，归属信息落在详情接口返回的
# 属性数组里，所以按 IP 筛选要读 `product_details.attributes`。没有详情记录的商品 IP 未知，
# 任何具体 IP 都匹配不到 —— 这与详情、成交、价格点接口的数据覆盖限制一致。
IP_ATTRIBUTE_NAME = "IP"

# 一个关键词最多展开成多少个全角/半角写法，超过就退回原词，避免长英文词把 LIKE 条件撑爆。
SEARCH_VARIANT_LIMIT = 8
# 半角可打印 ASCII(0x21-0x7E) 与全角 U+FF01-U+FF5E 逐位对应，偏移量固定。
FULL_WIDTH_OFFSET = 0xFEE0


def ip_attribute_rows():
    """`product_details.attributes` 上的 `json_each` 表值别名。"""
    return func.json_each(ProductDetail.attributes).table_valued("value")


def ip_attribute_product_ids(ip: str):
    """详情属性中 `IP` 等于给定值的商品 id 子查询。"""
    attribute = ip_attribute_rows()
    return (
        select(ProductDetail.product_id)
        .join(attribute, true())
        .where(
            func.json_extract(attribute.c.value, "$.attrName") == IP_ATTRIBUTE_NAME,
            func.json_extract(attribute.c.value, "$.attrValue") == ip,
        )
    )


def like_pattern(term: str):
    """把关键词转成 LIKE 模式，`\\`、`%`、`_` 按字面量处理，不让用户输入变成通配符。"""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def width_equivalents(char: str):
    """一个字符的全角/半角等价写法，只对符号做转换，字母和数字原样保留。

    字母数字排除在外是刻意的：`100%` 这样的词里两个数字就会吃掉展开预算，导致真正需要容忍的
    符号反而退化成精确匹配；而用户手输全角字母数字的可能性极低。
    """
    if char.isalnum():
        return (char,)
    code = ord(char)
    if 0x21 <= code <= 0x7E:
        return (char, chr(code + FULL_WIDTH_OFFSET))
    if 0xFF01 <= code <= 0xFF5E:
        return (char, chr(code - FULL_WIDTH_OFFSET))
    return (char,)


def width_variants(term: str):
    """一个关键词的全角/半角等价写法（按字符做笛卡尔积）。

    标题里的符号可能是全角也可能是半角：中文标题常见全角「！」「（）」，而加号、百分号这类多为
    半角。SQLite 的 LIKE 没有字符类（`[+＋]` 只有 GLOB 支持，而 GLOB 区分大小写），一个模式
    匹配不了两种写法，所以展开成若干等价关键词再用 OR 组合。

    组合数超过 `SEARCH_VARIANT_LIMIT` 时（一个词里有 4 个以上符号）退回原词，避免 LIKE 条件
    爆炸。空白字符不会走到这里 —— 全角空格和半角空格在 `search_conditions` 里都已经当分隔符
    切掉了，两种写法靠词与词之间的 AND 互通。
    """
    variants = [""]
    for char in term:
        variants = [prefix + item for prefix in variants for item in width_equivalents(char)]
        if len(variants) > SEARCH_VARIANT_LIMIT:
            return [term]
    return variants


def search_conditions(search: str):
    """空格分隔的多个关键词按 AND 组合：标题要同时命中每一个词，词越多结果越窄。

    `str.split()` 不带参数按空白切分（半角空格、全角空格、连续空格都算），所以只有空格时返回
    空条件列表，等价于没有搜索。每个词内部再按全角/半角等价写法做 OR。
    """
    conditions = []
    for term in search.split():
        patterns = [like_pattern(variant) for variant in width_variants(term)]
        conditions.append(or_(*[Product.title.ilike(pattern, escape="\\") for pattern in patterns]))
    return conditions


def list_products(db: Session, category: str | None, ip: str | None, search: str | None, sort: str | None, limit: int, offset: int):
    query = select(Product).where(Product.is_active.is_(True))
    if category:
        query = query.where(Product.category == category)
    if ip:
        query = query.where(Product.id.in_(ip_attribute_product_ids(ip)))
    if search:
        query = query.where(*search_conditions(search))
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

def count_products(db: Session, category: str | None, ip: str | None, search: str | None):
    query = select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    if category:
        query = query.where(Product.category == category)
    if ip:
        query = query.where(Product.id.in_(ip_attribute_product_ids(ip)))
    if search:
        query = query.where(*search_conditions(search))
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

def list_running_scheduled_crawls(db: Session):
    return list(db.scalars(select(ScheduledCrawl).where(ScheduledCrawl.last_status == "running").order_by(ScheduledCrawl.id.asc())))

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
