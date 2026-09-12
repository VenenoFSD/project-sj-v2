# Product Tracker API

开发环境启动：

```powershell
python -m uvicorn backend.main:app --reload
```

Swagger UI：`http://127.0.0.1:8000/docs`

## 接口

### `GET /api/health`

返回服务状态：

```json
{"status":"ok"}
```

### `GET /api/products`

列表接口支持可选排序参数 `sort`：`price` 按最新价格从低到高排序，`discount` 按最新 `price / reference_price` 从低到高排序。未传入 `sort` 时保持按最近抓取时间倒序；缺少可排序数据的商品排在有效排序值之后。

查询当前有效商品。

查询参数：`category`（可选）、`search`（商品标题关键词，可选）、`sort`（`price` 或 `discount`，可选）、`limit`（1-100，默认 20）、`offset`（默认 0）。响应包含 `items`、`total`、`limit` 和 `offset`。

### `GET /api/products/{cluster_id}/history`

查询商品价格历史。参数 `limit` 范围 1-200，默认 30。

### `GET /api/products/{cluster_id}/details`

查询最近一次保存的商品详情，包括图片、属性、价格标签、最低价和最近成交价。

### `GET /api/products/{cluster_id}/deals`

查询商品成交记录，`limit` 默认 50，最大 500。返回 `user_avatar`、`user_name`、`deal_price`、`deal_time`。

### `GET /api/products/{cluster_id}/price-points`

查询商品价格走势点，`limit` 默认 200，最大 1000。返回 `date_label`、`avg_price`、`volume`。

### `GET /api/crawl-runs`

查询抓取批次记录。参数：`limit`（1-100，默认 20）、`offset`（默认 0）。

### `POST /api/crawl-runs`

后台启动一次爬虫任务。请求体字段：`pages`（0-500，默认 0）、`category`、`ip`、`sort`（`hot`、`mostListings`、`priceFirst`）、`detail`、`no_alert`、`no_overview`（不打印首页概览，默认 `false`）。

接口返回 `task_id` 后，可轮询任务状态：

```text
GET /api/crawl-runs/tasks/{task_id}
```

同一后端进程同时只允许一个抓取任务运行。

接口实际响应结构以 Swagger/OpenAPI 为准；新增或修改接口时同步更新本文档。

### `POST /api/schedules`

创建 interval 定时爬取任务。`interval_seconds` 范围为 60-2592000 秒，`crawl_params` 复用爬虫参数：`pages`、`category`、`ip`、`sort`、`detail`、`no_alert` 和 `no_overview`。创建后任务默认启用。

### `GET /api/schedules`

查询全部定时任务，返回 `items`。每项包含配置、`enabled`、`last_status`、`last_error`、`last_run_at`、`last_finished_at` 和 `next_run_at`。

### `GET /api/schedules/{schedule_id}`

查询单个定时任务详情。不存在时返回 `404`。

### `PATCH /api/schedules/{schedule_id}`

更新任务名称、间隔、爬虫参数或 `enabled` 状态。未传入的字段保持不变；不存在时返回 `404`。

### `POST /api/schedules/{schedule_id}/run`

立即触发一次任务，不改变原有定时周期。任务已禁用或当前已有其他爬取任务运行时返回 `409`。

### `DELETE /api/schedules/{schedule_id}`

删除定时任务并移除对应调度 job。成功返回 `204`。

定时任务状态取值包括：`running`（已启动）、`success`（执行成功）、`failed`（爬虫进程失败）、`skipped`（已有任务运行而跳过）和 `error`（启动或配置错误）。

### `GET /api/catalog/{filter_type}`

查询已抓取的筛选维度。`filter_type` 支持 `category`、`ip`、`sort`。

### `GET /api/home/latest`

查询最近一次抓取保存的首页概览信息。

### Favorites

- `GET /api/favorites?user_id=default`：查询收藏
- `POST /api/favorites/{cluster_id}?user_id=default`：收藏商品
- `DELETE /api/favorites/{cluster_id}?user_id=default`：取消收藏
