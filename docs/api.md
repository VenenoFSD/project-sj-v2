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

查询当前有效商品。

查询参数：`category`（可选）、`limit`（1-100，默认 20）、`offset`（默认 0）。

### `GET /api/products/{cluster_id}`

查询商品详情及最新价格快照。商品不存在返回 `404`。

### `GET /api/products/{cluster_id}/history`

查询商品价格历史。参数 `limit` 范围 1-200，默认 30。

### `GET /api/products/{cluster_id}/details`

查询最近一次保存的商品详情，包括图片、属性、价格标签、最低价和最近成交价。

### `GET /api/products/{cluster_id}/deals`

查询商品成交记录，`limit` 默认 50，最大 500。

### `GET /api/products/{cluster_id}/price-points`

查询商品价格走势点，`limit` 默认 200，最大 1000。

### `GET /api/crawl-runs`

查询抓取批次记录。参数：`limit`（1-100，默认 20）、`offset`（默认 0）。

接口实际响应结构以 Swagger/OpenAPI 为准；新增或修改接口时同步更新本文档。

### `GET /api/catalog/{filter_type}`

查询已抓取的筛选维度。`filter_type` 支持 `category`、`ip`、`sort`。

### `GET /api/home/latest`

查询最近一次抓取保存的首页概览信息。

### Favorites

- `GET /api/favorites?user_id=default`：查询收藏
- `POST /api/favorites/{cluster_id}?user_id=default`：收藏商品
- `DELETE /api/favorites/{cluster_id}?user_id=default`：取消收藏
