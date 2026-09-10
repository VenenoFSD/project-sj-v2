from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.repositories import list_crawl_runs
from backend.database.session import get_db
from backend.services import crawl_service
from backend.api.schemas import CrawlParams

router = APIRouter(prefix="/crawl-runs", tags=["crawl-runs"])


class CrawlRequest(CrawlParams):
    pass


@router.post("")
def start_crawl(request: CrawlRequest):
    try:
        task_id = crawl_service.start_crawl(**request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "running"}


@router.get("/tasks/{task_id}")
def get_crawl_task(task_id: str):
    task = crawl_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Crawl task not found")
    return task


@router.get("")
def get_crawl_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    runs = list_crawl_runs(db, limit, offset)
    return {"items": [
        {
            "id": run.id,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "category": run.category,
            "ip_id": run.ip_id,
            "sort_type": run.sort_type,
            "requested_pages": run.requested_pages,
            "actual_pages": run.actual_pages,
            "product_count": run.product_count,
            "status": run.status,
        } for run in runs
    ], "limit": limit, "offset": offset}
