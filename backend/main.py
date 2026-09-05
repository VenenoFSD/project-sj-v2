from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.crawl_runs import router as crawl_runs_router
from backend.api.products import router as products_router
from backend.api.catalog import router as catalog_router
from backend.api.home import router as home_router
from backend.api.favorites import router as favorites_router

app = FastAPI(
    title="Product Tracker API",
    version="0.1.0",
    description="商品与价格历史查询接口",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


app.include_router(products_router, prefix="/api")
app.include_router(crawl_runs_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(home_router, prefix="/api")
app.include_router(favorites_router, prefix="/api")
