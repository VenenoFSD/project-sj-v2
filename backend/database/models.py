from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String)
    img: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[str] = mapped_column(String, nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    snapshots: Mapped[list["ProductSnapshot"]] = relationship(back_populates="product")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    ip_id: Mapped[str | None] = mapped_column(String)
    sort_type: Mapped[str | None] = mapped_column(String)
    requested_pages: Mapped[int | None] = mapped_column(Integer)
    actual_pages: Mapped[int | None] = mapped_column(Integer)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False)


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    crawl_run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"), nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    reference_price: Mapped[float | None] = mapped_column(Float)
    discount: Mapped[str | None] = mapped_column(Text)
    popularity: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[str] = mapped_column(String, nullable=False)

    product: Mapped[Product] = relationship(back_populates="snapshots")


class ProductDetail(Base):
    __tablename__ = "product_details"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), unique=True)
    lowest_price: Mapped[str | None] = mapped_column(String)
    latest_deal_price: Mapped[str | None] = mapped_column(String)
    price_tag: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[str | None] = mapped_column(Text)
    images: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[str] = mapped_column(String, nullable=False)


class ProductDeal(Base):
    __tablename__ = "product_deals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    deal_json: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[str] = mapped_column(String, nullable=False)


class ProductPricePoint(Base):
    __tablename__ = "product_price_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    point_json: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[str] = mapped_column(String, nullable=False)


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default="default", nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)
