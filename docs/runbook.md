# 项目运行手册

本文档说明爬取脚本和 FastAPI 后端的本地运行方式。

## 1. 环境准备

在项目根目录执行：

```powershell
cd D:\code\project-sj-v2
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

以后每次开发前先激活虚拟环境：

```powershell
cd D:\code\project-sj-v2
.venv\Scripts\Activate.ps1
```

退出虚拟环境：

```powershell
deactivate
```

## 2. 数据库位置

默认 SQLite 数据库为 `data/products.db`。爬虫和后端默认使用同一个数据库；爬虫支持通过 `--db` 显式指定其他路径。

## 3. 运行爬取脚本

脚本入口为 `backend/crawler/crawler.py`。

完整参数说明见：[crawler.md](crawler.md)

```powershell
python backend/crawler/crawler.py --help
python backend/crawler/crawler.py
python backend/crawler/crawler.py --pages 20
python backend/crawler/crawler.py --category 898 --sort hot
python backend/crawler/crawler.py --category 898 --detail
python backend/crawler/crawler.py --list-filters
python backend/crawler/crawler.py --trend
python backend/crawler/crawler.py --pages 20 --json data/products.json
python backend/crawler/crawler.py --pages 20 --csv data/products.csv
python backend/crawler/crawler.py --db data/products.db --trend
```

## 4. 运行后端

在项目根目录、虚拟环境已激活的终端中执行：

```powershell
python -m uvicorn backend.main:app --reload
```

默认地址为 `http://127.0.0.1:8000`。

- Swagger UI：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc
- 接口说明：[api.md](api.md)

指定监听地址和端口：

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## 5. 基础验证

```powershell
python -m compileall backend
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod "http://127.0.0.1:8000/api/products?limit=20"
Invoke-RestMethod "http://127.0.0.1:8000/api/crawl-runs?limit=20"
```

## 6. 运行顺序

1. 激活 `.venv` 并安装 `requirements.txt`。
2. 执行爬虫写入或更新 `data/products.db`。
3. 启动 FastAPI 后端。
4. 通过 `/docs` 或前端调用查询接口。

爬虫是长耗时任务，建议在独立终端运行；后端只有存在启用的定时任务时才会自动执行爬取。

每次爬虫执行都会在 `logs/` 下生成独立日志文件，查看最近一次日志：

```powershell
$latestLog = Get-ChildItem logs -Filter "crawler_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $latestLog.FullName -Tail 100
```

也可以通过 API 手动触发后台抓取：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/crawl-runs `
  -ContentType "application/json" `
  -Body '{"pages":1,"category":"898","sort":"hot","detail":false}'
```

返回 `task_id` 后查询状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/crawl-runs/tasks/{task_id}
```

## 定时爬取任务

定时任务由 FastAPI 进程内的 APScheduler 管理。当前部署应使用单个 worker，避免多个进程重复注册并执行同一个任务：

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

创建一个每 10 分钟执行一次的任务：

```powershell
$body = @{
  name = "默认商品巡检"
  interval_seconds = 600
  crawl_params = @{
    pages = 1
    category = "898"
    ip = $null
    sort = "hot"
    detail = $false
    no_alert = $false
  }
} | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8000/api/schedules" -Method Post -ContentType "application/json" -Body $body
```

使用 `GET /api/schedules` 或 `GET /api/schedules/{schedule_id}` 查看 `enabled`、`last_status`、`last_error`、`last_run_at`、`last_finished_at` 和 `next_run_at`。前端可使用 `POST /api/schedules/{schedule_id}/run` 立即触发一次，使用 `PATCH` 修改或启停任务，使用 `DELETE` 删除任务。

后端关闭时会停止调度器并终止仍在运行的爬虫子进程；关键调度、启动、跳过、完成、异常和生命周期事件写入后端日志。

## 前端开发（Windows 注意事项）

```powershell
cd frontend
npm run dev          # http://localhost:5173
npm run build        # 产出 frontend/dist
```

Windows 下文件监听器存在一个已知问题：编辑器或自动化工具保存文件时采用**原子写入**（先在目标同目录建 `<文件名>.<pid>.<uuid>.tmpdir/`，写完 rename 覆盖，再删除临时目录）。临时目录出现在监听范围内、又在监听器完成注册前被删除时，`fs.watch` 会返回 `EBUSY`，该 `error` 事件未被兜住，会把整个 `npm run dev` 进程带崩（报错路径形如 `src/styles/.theme.css.<pid>.<uuid>.tmpdir/theme.css.tmp`）。

`frontend/vite.config.js` 已经在 `server.watch.ignored` 中排除了这类临时目录、`dist/` 与 VCS 元数据，因此正常情况下不会再触发。若仍然遇到：

1. 重新执行 `npm run dev` 即可，源码本身没有损坏；
2. 确认 `npm run dev` 与 `npm run build` **没有同时运行**——两者都会大量读写 `frontend/` 下的文件；
3. 必要时清理残留：`Get-ChildItem frontend -Recurse -Force -Filter "*.tmpdir" | Remove-Item -Recurse -Force`。

