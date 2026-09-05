# 爬虫脚本说明

脚本入口：`backend/crawler/crawler.py`

脚本从 Bilibili 会员购转售接口获取首页、筛选维度、商品列表和可选的商品详情，并将商品及价格历史写入 `data/products.db`。

## 运行前提

在项目根目录激活虚拟环境并安装依赖：

```powershell
cd D:\code\project-sj-v2
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`requests` 和 `tqdm` 为可选增强依赖。未安装 `requests` 时脚本会回退到标准库 `urllib`；未安装 `tqdm` 时不会显示进度条。

## 基本命令

查看参数：

```powershell
python backend/crawler/crawler.py --help
```

默认抓取：

```powershell
python backend/crawler/crawler.py
```

默认分类为 `898`，默认排序为 `hot`，默认抓取全部页面（最多 500 页，并根据新增率动态停止）。

## 参数说明

### 抓取参数

#### `--pages PAGES`

指定抓取页数。

- 类型：整数
- 默认：`0`
- `0`：全量模式，最多抓取 500 页，并启用动态停止
- 大于 `0`：只抓取指定页数

示例：

```powershell
python backend/crawler/crawler.py --pages 20
```

#### `--all`

全量抓取，等同于 `--pages 0`。

```powershell
python backend/crawler/crawler.py --all
```

#### `--sort SORT`

商品排序方式。可选值：

- `hot`：热门
- `mostListings`：在售数量较多
- `priceFirst`：价格优先

默认值：`hot`。

```powershell
python backend/crawler/crawler.py --sort priceFirst
```

在全量模式下，脚本会依次抓取当前排序方式及另外两种排序方式，并按商品 ID 去重；指定 `--pages` 时只抓取一种排序方式。

#### `--category CATEGORY`

商品分类 ID。

- 默认：`898`（脚本注释中的 3C 数码分类）
- 传入 `all` 或空字符串：不限定分类

```powershell
python backend/crawler/crawler.py --category 142
python backend/crawler/crawler.py --category all
```

分类 ID 可通过 `--list-filters` 获取。

#### `--ip IP`

IP 分区 ID。

- 默认：不限制 IP
- 传入 `all` 或空字符串：不限定 IP

```powershell
python backend/crawler/crawler.py --ip 123
```

IP 分区 ID 可通过 `--list-filters` 获取。

#### `--detail`

获取商品详情。列表抓取和商品入库完成后，额外请求商品详情接口。

详情包括：

- 商品图片列表
- 价格标签
- 最低价
- 最近成交价
- 商品属性
- 价格走势点
- 成交记录

当前实现会获取本次商品列表中每个商品的详情，并将详情保存到数据库；指定 `--json` 时也会写入 JSON 的 `details` 字段。

```powershell
python backend/crawler/crawler.py --pages 5 --detail
```

该参数会增加请求数量和运行时间。

### 存储与导出参数

#### `--db DB`

指定 SQLite 数据库路径。

- 默认：项目根目录 `data/products.db`
- 父目录不存在时会自动创建

```powershell
python backend/crawler/crawler.py --db data/products.db
python backend/crawler/crawler.py --db data/test-products.db --pages 1
```

#### `--csv CSV`

将本次抓取的商品追加导出到 CSV。

字段包括：抓取时间、分类、商品 ID、标题、价格、参考价、折扣、人气、图片和 URL。

```powershell
python backend/crawler/crawler.py --pages 20 --csv data/products.csv
```

#### `--json JSON`

将本次抓取结果导出为 JSON。文件包含 `meta` 和 `products`；使用 `--detail` 时还会追加 `details`。

```powershell
python backend/crawler/crawler.py --pages 5 --json data/products.json
python backend/crawler/crawler.py --pages 5 --detail --json data/products-detail.json
```

### 分析与筛选参数

#### `--trend`

只读取数据库并分析最近两次抓取的价格趋势，不执行网络抓取。

输出价格上涨、下降、不变、新增和消失商品。

```powershell
python backend/crawler/crawler.py --trend
python backend/crawler/crawler.py --trend --category 898
```

#### `--list-filters`

只请求首页接口并列出可用筛选维度，不抓取商品列表。

输出：

- 排序方式及名称
- 商品分类 ID 及名称
- IP 分区 ID 及名称

```powershell
python backend/crawler/crawler.py --list-filters
```

筛选维度会保存到数据库的 `catalog_filters` 表，同时保存一条首页快照到 `home_snapshots`；该模式不会抓取商品列表。

#### `--no-alert`

关闭本次抓取结束后的价格异动检测。

```powershell
python backend/crawler/crawler.py --no-alert
```

#### `--alert-prev N`

价格异动检测时，对比当前抓取之前的 N 次抓取。

- 类型：整数
- 默认：`3`

```powershell
python backend/crawler/crawler.py --alert-prev 5
```

#### `--alert-abs AMOUNT`

价格下降的绝对金额阈值，单位为元。

- 类型：浮点数
- 默认：`10.0`

只要降价绝对值超过该值，且满足异动条件，就会触发提醒。

```powershell
python backend/crawler/crawler.py --alert-abs 20
```

#### `--alert-pct RATE`

价格下降的相对比例阈值。

- 类型：浮点数
- 默认：`0.10`，即 10%

```powershell
python backend/crawler/crawler.py --alert-pct 0.15
```

#### `--alert-csv CSV`

将检测到的价格异动商品导出为 CSV。

```powershell
python backend/crawler/crawler.py --alert-csv data/alerts.csv
```

### 输出控制参数

#### `--no-overview`

不打印首页概览，但仍会请求首页接口。

```powershell
python backend/crawler/crawler.py --no-overview
```

#### `--quiet`

安静模式，减少商品列表抓取过程中的终端输出，并关闭进度条显示；不改变抓取和入库逻辑。

```powershell
python backend/crawler/crawler.py --quiet
```

## 常用组合

小规模验证抓取并写入测试库：

```powershell
python backend/crawler/crawler.py --pages 1 --db data/test-products.db --quiet
```

抓取指定分类并保存详情 JSON：

```powershell
python backend/crawler/crawler.py --category 142 --pages 10 --detail --json data/category-142.json
```

全量抓取并导出 CSV，同时保留异动结果：

```powershell
python backend/crawler/crawler.py --all --csv data/products.csv --alert-csv data/alerts.csv
```

仅查看筛选项：

```powershell
python backend/crawler/crawler.py --list-filters --db data/products.db
```

## 数据写入说明

正常抓取流程如下：

1. 请求首页，读取概览和筛选维度。
2. 创建一条 `crawl_runs` 抓取记录。
3. 按页请求商品流并根据商品 ID 去重。
4. 写入或更新 `products`，并写入本次 `product_snapshots`。
5. 如果使用 `--detail`，保存本次抓取全部商品的详情、成交记录和价格走势点。
6. 执行价格异动检测（除非使用 `--no-alert`）。

主要数据库表：

- `products`：商品基础信息
- `product_snapshots`：价格和标签历史
- `crawl_runs`：抓取批次及状态
- `catalog_filters`：分类、IP 和排序维度
- `home_snapshots`：首页概览快照
- `product_details`：商品详情摘要
- `product_deals`：成交记录
- `product_price_points`：价格走势图数据

## 注意事项

- 建议从项目根目录运行命令。
- 全量抓取可能耗时较长，并可能触发站点限流。
- `--detail` 会为本次抓取的每个商品产生额外请求，商品数量较多时运行时间会明显增加。
- `--trend` 不访问网络，只读取本地数据库。
- 删除 `data/products.db` 会清空商品、历史和抓取记录；下次运行会自动重建数据库结构。
- 每次执行都会在 `logs/` 下新建独立日志文件，例如 `crawler_20260906_021530_123456.log`。详情请求会记录请求结果、响应字段、解析结果和入库跳过原因；日志文件不会提交到 Git。
