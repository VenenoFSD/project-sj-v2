import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRAWLER_PATH = PROJECT_ROOT / "backend" / "crawler" / "crawler.py"
_lock = threading.Lock()
_tasks: dict[str, dict] = {}


def _watch(task_id: str, process: subprocess.Popen):
    stdout, _ = process.communicate()
    with _lock:
        task = _tasks[task_id]
        task["return_code"] = process.returncode
        task["output"] = stdout[-20000:] if stdout else ""
        task["status"] = "success" if process.returncode == 0 else "failed"


def start_crawl(*, pages: int, category: str | None, ip: str | None, sort: str, detail: bool, no_alert: bool) -> str:
    with _lock:
        if any(task["status"] == "running" for task in _tasks.values()):
            raise RuntimeError("A crawl task is already running")
        task_id = uuid.uuid4().hex
        args = [sys.executable, str(CRAWLER_PATH), "--pages", str(pages), "--sort", sort]
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
        env = os.environ.copy()
        process = subprocess.Popen(
            args,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        _tasks[task_id] = {"task_id": task_id, "status": "running", "pid": process.pid, "output": "", "return_code": None}
        threading.Thread(target=_watch, args=(task_id, process), daemon=True).start()
        return task_id


def get_task(task_id: str):
    with _lock:
        return dict(_tasks.get(task_id)) if task_id in _tasks else None
