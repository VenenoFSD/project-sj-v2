from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.schemas import CrawlParams
from backend.database import repositories
from backend.database.session import get_db
from backend.services import crawl_service
from backend.services import scheduler_service


router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    name: str | None = Field(None, max_length=100)
    interval_seconds: int = Field(..., ge=60, le=2592000)
    crawl_params: CrawlParams


class ScheduleUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    interval_seconds: int | None = Field(None, ge=60, le=2592000)
    crawl_params: CrawlParams | None = None
    enabled: bool | None = None


class ScheduleResponse(BaseModel):
    id: int
    name: str | None
    enabled: bool
    interval_seconds: int
    crawl_params: CrawlParams
    created_at: str
    updated_at: str
    last_run_at: str | None
    last_task_id: str | None
    last_status: str | None
    last_error: str | None
    last_finished_at: str | None
    next_run_at: str | None


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]


def _payload(schedule):
    try:
        params = scheduler_service.decode_crawl_params(schedule.crawl_params)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Stored schedule parameters are invalid") from exc
    return {
        "id": schedule.id,
        "name": schedule.name,
        "enabled": schedule.enabled,
        "interval_seconds": schedule.interval_seconds,
        "crawl_params": params,
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
        "last_run_at": schedule.last_run_at,
        "last_task_id": schedule.last_task_id,
        "last_status": schedule.last_status,
        "last_error": schedule.last_error,
        "last_finished_at": schedule.last_finished_at,
        "next_run_at": schedule.next_run_at,
    }


def _not_found(exc):
    raise HTTPException(status_code=404, detail="Scheduled crawl not found") from exc


@router.post("", response_model=ScheduleResponse, status_code=201)
def create_schedule(request: ScheduleCreate, db: Session = Depends(get_db)):
    try:
        schedule = scheduler_service.create_schedule(
            db,
            name=request.name,
            interval_seconds=request.interval_seconds,
            crawl_params=request.crawl_params.model_dump(),
        )
    except scheduler_service.SchedulerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _payload(schedule)


@router.get("", response_model=ScheduleListResponse)
def list_schedules(db: Session = Depends(get_db)):
    return {"items": [_payload(schedule) for schedule in repositories.list_scheduled_crawls(db)]}


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = repositories.get_scheduled_crawl(db, schedule_id)
    if schedule is None:
        _not_found(None)
    return _payload(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: int, request: ScheduleUpdate, db: Session = Depends(get_db)):
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="At least one field is required")
    if updates.get("interval_seconds") is None and "interval_seconds" in updates:
        raise HTTPException(status_code=422, detail="interval_seconds cannot be null")
    if updates.get("crawl_params") is None and "crawl_params" in updates:
        raise HTTPException(status_code=422, detail="crawl_params cannot be null")
    if updates.get("enabled") is None and "enabled" in updates:
        raise HTTPException(status_code=422, detail="enabled cannot be null")
    try:
        schedule = scheduler_service.update_schedule(db, schedule_id, updates)
    except scheduler_service.ScheduleNotFoundError as exc:
        _not_found(exc)
    except scheduler_service.SchedulerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _payload(schedule)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    try:
        scheduler_service.delete_schedule(db, schedule_id)
    except scheduler_service.ScheduleNotFoundError as exc:
        _not_found(exc)
    return Response(status_code=204)


@router.post("/{schedule_id}/run")
def run_schedule(schedule_id: int):
    try:
        task_id = scheduler_service.trigger_schedule(schedule_id, source="manual")
    except scheduler_service.ScheduleNotFoundError as exc:
        _not_found(exc)
    except scheduler_service.ScheduleDisabledError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except scheduler_service.SchedulerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except crawl_service.CrawlAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "running"}
