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

后台启动一次爬虫任务。请求体字段：`pages`（0-500，默认 0）、`category`、`ip`、`sort`（`hot`、`mostListings`、`priceFirst`）、`detail`、`no_alert`。

接口返回 `task_id` 后，可轮询任务状态：

```text
GET /api/crawl-runs/tasks/{task_id}
```

同一后端进程同时只允许一个抓取任务运行。

接口实际响应结构以 Swagger/OpenAPI 为准；新增或修改接口时同步更新本文档。

### `GET /api/catalog/{filter_type}`

查询已抓取的筛选维度。`filter_type` 支持 `category`、`ip`、`sort`。

### `GET /api/home/latest`

查询最近一次抓取保存的首页概览信息。

### Favorites

- `GET /api/favorites?user_id=default`：查询收藏
- `POST /api/favorites/{cluster_id}?user_id=default`：收藏商品
- `DELETE /api/favorites/{cluster_id}?user_id=default`：取消收藏
