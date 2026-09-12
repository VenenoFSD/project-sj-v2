import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
import logging
from collections.abc import Callable
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRAWLER_PATH = PROJECT_ROOT / "backend" / "crawler" / "crawler.py"
LOGGER = logging.getLogger("product_tracker.crawl_service")
_lock = threading.Lock()
_tasks: dict[str, dict] = {}
_processes: dict[str, subprocess.Popen] = {}


class CrawlAlreadyRunningError(RuntimeError):
    pass


def _watch(task_id: str, process: subprocess.Popen, on_complete: Callable[[str, int], None] | None = None):
    try:
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                with _lock:
                    task = _tasks.get(task_id)
                    if task is not None:
                        task["output"] = f'{task["output"]}{line}'[-20000:]
    finally:
        if process.stdout:
            process.stdout.close()
        return_code = process.wait()
        with _lock:
            task = _tasks.get(task_id)
            if task is not None:
                task["return_code"] = return_code
                task["status"] = "success" if return_code == 0 else "failed"
            _processes.pop(task_id, None)
        LOGGER.info("crawl process finished task_id=%s return_code=%s status=%s", task_id, return_code, "success" if return_code == 0 else "failed")
        if on_complete is not None:
            try:
                on_complete(task_id, return_code)
            except Exception:
                LOGGER.exception("crawl completion callback failed task_id=%s", task_id)


def start_crawl(*, pages: int, category: str | None, ip: str | None, sort: str, detail: bool, no_alert: bool, no_overview: bool = False, on_complete: Callable[[str, int], None] | None = None) -> str:
    with _lock:
        if any(task["status"] == "running" for task in _tasks.values()):
            raise CrawlAlreadyRunningError("A crawl task is already running")
        task_id = uuid.uuid4().hex
        args = [sys.executable, "-u", str(CRAWLER_PATH), "--pages", str(pages), "--sort", sort]
        if category:
            args += ["--category", category]
        else:
            args += ["--category", "all"]
        if ip:
            args += ["--ip", ip]
        if detail:
            args.append("--detail")
        if no_alert:
            args.append("--no-alert")
        if no_overview:
            args.append("--no-overview")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        display_args = ["python", "-u", CRAWLER_PATH.relative_to(PROJECT_ROOT).as_posix(), *args[3:]]
        initial_output = f"$ {shlex.join(display_args)}\n\n"
        LOGGER.info("starting crawl process task_id=%s pages=%s category=%s ip=%s sort=%s detail=%s no_alert=%s no_overview=%s", task_id, pages, category, ip, sort, detail, no_alert, no_overview)
        try:
            process = subprocess.Popen(
                args,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            LOGGER.exception("failed to start crawl process task_id=%s", task_id)
            raise
        _tasks[task_id] = {"task_id": task_id, "status": "running", "pid": process.pid, "output": initial_output, "return_code": None}
        _processes[task_id] = process
        threading.Thread(target=_watch, args=(task_id, process, on_complete), daemon=True).start()
        LOGGER.info("crawl process started task_id=%s pid=%s", task_id, process.pid)
        return task_id


def get_task(task_id: str):
    with _lock:
        return dict(_tasks.get(task_id)) if task_id in _tasks else None


def stop_all_crawls(timeout: float = 10.0):
    with _lock:
        processes = list(_processes.items())
    if not processes:
        return
    LOGGER.info("stopping active crawl processes count=%s", len(processes))
    for task_id, process in processes:
        if process.poll() is None:
            LOGGER.info("terminating crawl process task_id=%s pid=%s", task_id, process.pid)
            try:
                process.terminate()
            except OSError:
                LOGGER.exception("failed to terminate crawl process task_id=%s pid=%s", task_id, process.pid)
    deadline = time.monotonic() + timeout
    for task_id, process in processes:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            LOGGER.warning("killing crawl process after timeout task_id=%s pid=%s", task_id, process.pid)
            try:
                process.kill()
            except OSError:
                LOGGER.exception("failed to kill crawl process task_id=%s pid=%s", task_id, process.pid)
    LOGGER.info("active crawl processes stopped")
