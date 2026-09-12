import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler

from backend.api.schemas import CrawlParams
from backend.database import repositories
from backend.database.session import SessionLocal
from backend.services import crawl_service


LOGGER = logging.getLogger("product_tracker.scheduler")
JOB_PREFIX = "scheduled_crawl_"
SCHEDULER_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
# Surfaced verbatim by the backend page, so it is written for the operator rather than the log.
INTERRUPTED_RUN_ERROR = "服务重启，上次运行已中断"
_scheduler: BackgroundScheduler | None = None
_scheduler_lock = threading.RLock()


class SchedulerUnavailableError(RuntimeError):
    pass


class ScheduleNotFoundError(LookupError):
    pass


class ScheduleDisabledError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(SCHEDULER_TIMEZONE).isoformat(timespec="seconds")


def _job_id(schedule_id: int) -> str:
    return f"{JOB_PREFIX}{schedule_id}"


def _serialize_params(params: dict) -> str:
    return json.dumps(CrawlParams.model_validate(params).model_dump(), ensure_ascii=False, separators=(",", ":"))


def decode_crawl_params(value: str) -> dict:
    try:
        return CrawlParams.model_validate(json.loads(value)).model_dump()
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Invalid scheduled crawl parameters") from exc


def _job_next_run_at(job) -> str | None:
    """Reads a job's next fire time, or None when there is none.

    Job declares next_run_time as a __slots__ member and only assigns it once the job reaches a
    running scheduler: add_job() onto a stopped scheduler merely queues the job in _pending_jobs
    and leaves the attribute unset, so reading it eagerly raises AttributeError.
    """
    next_run_time = getattr(job, "next_run_time", None)
    return next_run_time.isoformat(timespec="seconds") if next_run_time else None


def _next_run_at(schedule_id: int) -> str | None:
    with _scheduler_lock:
        if _scheduler is None:
            return None
        return _job_next_run_at(_scheduler.get_job(_job_id(schedule_id)))


def _write_run_state(schedule_id: int, **fields):
    db = SessionLocal()
    try:
        schedule = repositories.update_scheduled_crawl_run(db, schedule_id, **fields)
        if schedule is None:
            LOGGER.warning("schedule state update skipped schedule_id=%s reason=not_found", schedule_id)
        else:
            db.commit()
    except Exception:
        db.rollback()
        LOGGER.exception("schedule state update failed schedule_id=%s fields=%s", schedule_id, sorted(fields))
    finally:
        db.close()


def _reconcile_interrupted_runs(db) -> int:
    """Closes out schedules left in "running" by an interrupted shutdown.

    Startup is the one moment where no crawl of this process can be running yet, so any stored
    "running" state is necessarily stale — the subprocess was killed on shutdown and its watcher
    thread, being a daemon, may not have written the failure before the interpreter exited. Left
    alone the row would keep showing a ghost run and disable every row's actions in the UI.
    """
    schedules = repositories.list_running_scheduled_crawls(db)
    for schedule in schedules:
        schedule.last_status = "failed"
        schedule.last_error = INTERRUPTED_RUN_ERROR
        schedule.last_task_id = None
        LOGGER.warning("stale run reconciled schedule_id=%s", schedule.id)
    if schedules:
        db.flush()
    return len(schedules)


def _add_job(scheduler: BackgroundScheduler, schedule_id: int, interval_seconds: int):
    return scheduler.add_job(
        _run_crawl,
        trigger="interval",
        seconds=interval_seconds,
        args=[schedule_id],
        id=_job_id(schedule_id),
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
        max_instances=1,
    )


def init_scheduler():
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            LOGGER.info("scheduler initialization skipped reason=already_running")
            return
        LOGGER.info("scheduler initialization started")
        scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "misfire_grace_time": 60,
                "coalesce": True,
                "max_instances": 1,
            },
        )
        db = SessionLocal()
        try:
            reconciled_count = _reconcile_interrupted_runs(db)
            # Start before registering: jobs added to a stopped scheduler are only queued in
            # _pending_jobs, and their next_run_time stays unset until the scheduler starts.
            scheduler.start()
            schedules = repositories.list_enabled_scheduled_crawls(db)
            for schedule in schedules:
                try:
                    job = _add_job(scheduler, schedule.id, schedule.interval_seconds)
                    schedule.next_run_at = _job_next_run_at(job)
                    LOGGER.info("schedule job registered schedule_id=%s interval_seconds=%s next_run_at=%s reason=startup", schedule.id, schedule.interval_seconds, schedule.next_run_at)
                except Exception:
                    LOGGER.exception("schedule job registration failed schedule_id=%s reason=startup", schedule.id)
            _scheduler = scheduler
            db.commit()
            LOGGER.info("scheduler initialized enabled_schedule_count=%s reconciled_run_count=%s", len(schedules), reconciled_count)
        except Exception:
            db.rollback()
            if scheduler.running:
                scheduler.shutdown(wait=False)
            LOGGER.exception("scheduler initialization failed")
            raise
        finally:
            db.close()


def shutdown_scheduler():
    global _scheduler
    with _scheduler_lock:
        scheduler = _scheduler
        _scheduler = None
    if scheduler is None:
        LOGGER.info("scheduler shutdown skipped reason=not_running")
        return
    LOGGER.info("scheduler shutdown started")
    scheduler.shutdown(wait=True)
    LOGGER.info("scheduler shutdown completed")


def register_job(schedule_id: int, interval_seconds: int) -> str | None:
    with _scheduler_lock:
        if _scheduler is None or not _scheduler.running:
            raise SchedulerUnavailableError("Scheduler is not running")
        job = _add_job(_scheduler, schedule_id, interval_seconds)
    next_run_at = _job_next_run_at(job)
    LOGGER.info("schedule job registered schedule_id=%s interval_seconds=%s next_run_at=%s", schedule_id, interval_seconds, next_run_at)
    return next_run_at


def unregister_job(schedule_id: int):
    with _scheduler_lock:
        if _scheduler is None:
            LOGGER.info("schedule job unregister skipped schedule_id=%s reason=scheduler_not_running", schedule_id)
            return
        try:
            _scheduler.remove_job(_job_id(schedule_id))
            LOGGER.info("schedule job unregistered schedule_id=%s", schedule_id)
        except JobLookupError:
            LOGGER.info("schedule job unregister skipped schedule_id=%s reason=job_not_found", schedule_id)


def reschedule_job(schedule_id: int, interval_seconds: int) -> str | None:
    with _scheduler_lock:
        if _scheduler is None or not _scheduler.running:
            raise SchedulerUnavailableError("Scheduler is not running")
        try:
            job = _scheduler.reschedule_job(_job_id(schedule_id), trigger="interval", seconds=interval_seconds)
        except JobLookupError:
            LOGGER.warning("schedule job missing during reschedule schedule_id=%s action=register", schedule_id)
            job = _add_job(_scheduler, schedule_id, interval_seconds)
    next_run_at = _job_next_run_at(job)
    LOGGER.info("schedule job rescheduled schedule_id=%s interval_seconds=%s next_run_at=%s", schedule_id, interval_seconds, next_run_at)
    return next_run_at


def _on_crawl_complete(schedule_id: int, ready: threading.Event):
    def callback(task_id: str, return_code: int):
        if not ready.wait(timeout=30):
            LOGGER.warning("schedule completion state delayed schedule_id=%s task_id=%s", schedule_id, task_id)
        finished_at = _now()
        status = "success" if return_code == 0 else "failed"
        _write_run_state(
            schedule_id,
            expected_task_id=task_id,
            last_status=status,
            last_error=None if return_code == 0 else f"Crawler exited with return code {return_code}",
            last_finished_at=finished_at,
        )
        LOGGER.info("scheduled crawl completed schedule_id=%s task_id=%s status=%s return_code=%s", schedule_id, task_id, status, return_code)
    return callback


def _start_crawl(schedule_id: int, params: dict, source: str):
    ready = threading.Event()
    callback = _on_crawl_complete(schedule_id, ready)
    try:
        task_id = crawl_service.start_crawl(**params, on_complete=callback)
    except crawl_service.CrawlAlreadyRunningError as exc:
        _write_run_state(
            schedule_id,
            last_run_at=_now(),
            last_task_id=None,
            last_status="skipped",
            last_error=str(exc),
            last_finished_at=_now(),
        )
        LOGGER.warning("scheduled crawl skipped schedule_id=%s source=%s reason=crawl_already_running", schedule_id, source)
        if source == "manual":
            raise
        return None
    except Exception as exc:
        _write_run_state(
            schedule_id,
            last_run_at=_now(),
            last_task_id=None,
            last_status="error",
            last_error=str(exc),
            last_finished_at=_now(),
        )
        LOGGER.exception("scheduled crawl start failed schedule_id=%s source=%s", schedule_id, source)
        if source == "manual":
            raise
        return None

    try:
        state = {
            "last_run_at": _now(),
            "last_task_id": task_id,
            "last_status": "running",
            "last_error": None,
            "last_finished_at": None,
        }
        if source == "scheduled":
            state["next_run_at"] = _next_run_at(schedule_id)
        _write_run_state(
            schedule_id,
            **state,
        )
    finally:
        ready.set()
    LOGGER.info("scheduled crawl started schedule_id=%s source=%s task_id=%s", schedule_id, source, task_id)
    return task_id


def trigger_schedule(schedule_id: int, source: str = "scheduled"):
    db = SessionLocal()
    try:
        schedule = repositories.get_scheduled_crawl(db, schedule_id)
        if schedule is None:
            if source == "scheduled":
                LOGGER.warning("scheduled crawl trigger skipped schedule_id=%s reason=schedule_not_found", schedule_id)
                return None
            raise ScheduleNotFoundError(schedule_id)
        if not schedule.enabled:
            if source == "scheduled":
                LOGGER.info("scheduled crawl trigger skipped schedule_id=%s reason=disabled", schedule_id)
                return None
            raise ScheduleDisabledError("Schedule is disabled")
        params = decode_crawl_params(schedule.crawl_params)
    except ValueError as exc:
        LOGGER.exception("scheduled crawl parameters invalid schedule_id=%s", schedule_id)
        if source == "scheduled":
            _write_run_state(schedule_id, last_run_at=_now(), last_status="error", last_error=str(exc), last_finished_at=_now())
            return None
        raise
    finally:
        db.close()
    LOGGER.info("scheduled crawl trigger received schedule_id=%s source=%s", schedule_id, source)
    return _start_crawl(schedule_id, params, source)


def _sync_job(schedule_id: int):
    db = SessionLocal()
    try:
        schedule = repositories.get_scheduled_crawl(db, schedule_id)
        if schedule is None or not schedule.enabled:
            unregister_job(schedule_id)
            return
        next_run_at = register_job(schedule.id, schedule.interval_seconds)
        schedule.next_run_at = next_run_at
        db.commit()
    except Exception:
        db.rollback()
        LOGGER.exception("schedule job synchronization failed schedule_id=%s", schedule_id)
    finally:
        db.close()


def create_schedule(db, *, name: str | None, interval_seconds: int, crawl_params: dict):
    schedule = repositories.create_scheduled_crawl(
        db,
        name=name,
        interval_seconds=interval_seconds,
        crawl_params=_serialize_params(crawl_params),
        created_at=_now(),
    )
    try:
        schedule.next_run_at = register_job(schedule.id, interval_seconds)
        db.commit()
        db.refresh(schedule)
    except Exception:
        db.rollback()
        unregister_job(schedule.id)
        LOGGER.exception("schedule creation failed schedule_id=%s", schedule.id)
        raise
    LOGGER.info("schedule created schedule_id=%s name=%s interval_seconds=%s", schedule.id, schedule.name, interval_seconds)
    return schedule


def update_schedule(db, schedule_id: int, updates: dict):
    schedule = repositories.get_scheduled_crawl(db, schedule_id)
    if schedule is None:
        raise ScheduleNotFoundError(schedule_id)
    old_enabled = schedule.enabled
    old_interval = schedule.interval_seconds
    for field, value in updates.items():
        if field == "crawl_params":
            value = _serialize_params(value)
        setattr(schedule, field, value)
    schedule.updated_at = _now()
    db.flush()
    try:
        if not schedule.enabled:
            unregister_job(schedule_id)
            schedule.next_run_at = None
        elif not old_enabled:
            schedule.next_run_at = register_job(schedule_id, schedule.interval_seconds)
        elif schedule.interval_seconds != old_interval:
            schedule.next_run_at = reschedule_job(schedule_id, schedule.interval_seconds)
        db.commit()
        db.refresh(schedule)
    except Exception:
        db.rollback()
        _sync_job(schedule_id)
        LOGGER.exception("schedule update failed schedule_id=%s fields=%s", schedule_id, sorted(updates))
        raise
    LOGGER.info("schedule updated schedule_id=%s fields=%s enabled=%s interval_seconds=%s", schedule_id, sorted(updates), schedule.enabled, schedule.interval_seconds)
    return schedule


def delete_schedule(db, schedule_id: int):
    schedule = repositories.get_scheduled_crawl(db, schedule_id)
    if schedule is None:
        raise ScheduleNotFoundError(schedule_id)
    try:
        unregister_job(schedule_id)
        repositories.delete_scheduled_crawl(db, schedule_id)
        db.commit()
    except Exception:
        db.rollback()
        _sync_job(schedule_id)
        LOGGER.exception("schedule deletion failed schedule_id=%s", schedule_id)
        raise
    LOGGER.info("schedule deleted schedule_id=%s", schedule_id)


def _run_crawl(schedule_id: int):
    try:
        trigger_schedule(schedule_id)
    except Exception:
        LOGGER.exception("scheduled crawl job failed schedule_id=%s", schedule_id)
