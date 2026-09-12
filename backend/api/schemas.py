from pydantic import BaseModel, Field


class CrawlParams(BaseModel):
    pages: int = Field(0, ge=0, le=500)
    category: str | None = "898"
    ip: str | None = None
    sort: str = Field("hot", pattern="^(hot|mostListings|priceFirst)$")
    detail: bool = False
    no_alert: bool = False
    no_overview: bool = False
