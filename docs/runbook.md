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

爬虫是长耗时任务，建议在独立终端运行；后端启动后不会自动执行爬取。

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
