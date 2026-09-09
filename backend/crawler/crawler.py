#!/usr/bin/env python3

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
from pathlib import Path
import random
import re
import sys
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager
import threading


# 项目根目录及默认数据库路径，避免依赖脚本运行时的当前工作目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "products.db"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("product_tracker.crawler")


def configure_run_logger() -> Path:
    """为本次脚本执行创建独立日志文件。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = LOG_DIR / f"crawler_{timestamp}.log"
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.info("crawler run started log_file=%s", log_path)
    return log_path

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# 解决 Windows 控制台编码问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ==================== User-Agent 池 ====================
USER_AGENTS = [
    # 只使用桌面 Chrome 指纹，避免 UA / sec-ch-ua / platform 互相矛盾。
    # UA 在一个 Session 生命周期内保持稳定；刷新 Session 时才重新选择。
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
]

DETAIL_WORKERS = 5


# ==================== 配置类 ====================
@dataclass
class CrawlerConfig:
    """爬虫配置"""
    base_url: str = "https://mall.bilibili.com/mall-c-search"
    referer: str = "https://mall.bilibili.com/neul-next/resell/home.html?noTitleBar=1"
    timeout: int = 12
    max_retries: int = 6
    max_pages: int = 500
    default_pages: int = 0
    rate_limit_wait_base: float = 2.5
    request_interval: Tuple[float, float] = (0.7, 1.1)
    page_retries: int = 2
    page_retry_wait: float = 2.0
    
    # 动态终止策略参数
    window_size: int = 5  # 滑动窗口大小
    min_new_threshold: float = 0.05  # 新增占比低于 5% 视为低新增
    low_new_streak_limit: int = 3  # 连续低新增页数上限
    
    # 价格异动检测
    alert_prev_n: int = 3
    alert_abs_threshold: float = 10.0
    alert_pct_threshold: float = 0.10

# ==================== 商品模型 ====================
@dataclass
class Product:
    """商品数据模型"""
    cluster_id: str
    title: str
    price: str
    reference_price: str = ""
    discount: str = ""
    popularity: str = ""
    img: str = ""
    url: str = ""
    crawl_time: str = ""
    category: str = ""
    
    @classmethod
    def from_api_item(cls, item: Dict[str, Any], category: str = "", crawl_time: str = "") -> 'Product':
        """从 API 响应创建 Product 对象"""
        price_tags = "、".join(t.get("text", "") for t in item.get("priceTags", []) if t.get("text"))
        popularity = "、".join(t.get("text", "") for t in item.get("popularityTags", []) if t.get("text"))
        symbol = item.get("currencySymbol", "¥")
        
        img = item.get("img", "")
        if img and img.startswith("//"):
            img = "https:" + img
            
        return cls(
            cluster_id=str(item.get("id", "")),
            title=item.get("title", "") or "（未命名/限时大漏）",
            price=f"{symbol}{item.get('price', '')}",
            reference_price=f"{symbol}{item['referencePrice']}" if item.get("referencePrice") else "",
            discount=price_tags,
            popularity=popularity,
            img=img,
            url=item.get("url", ""),
            category=category,
            crawl_time=crawl_time
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "title": self.title,
            "price": self.price,
            "reference_price": self.reference_price,
            "discount": self.discount,
            "popularity": self.popularity,
            "img": self.img,
            "url": self.url,
            "category": self.category,
            "crawl_time": self.crawl_time
        }
    
    @staticmethod
    def _price_to_float(value: str) -> Optional[float]:
        """将展示用价格字符串转换为数据库数值。"""
        if value is None:
            return None
        text = str(value).strip().replace("¥", "").replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    def to_db_tuple(self, product_id: Optional[int] = None, crawl_run_id: Optional[int] = None) -> tuple:
        """转换为数据库快照元组，价格以 REAL 存储。"""
        return (
            product_id,
            crawl_run_id,
            self._price_to_float(self.price),
            self._price_to_float(self.reference_price),
            self.discount,
            self.popularity,
            self.crawl_time
        )

# ==================== 爬虫类（无全局状态） ====================
class BiliResellCrawler:
    """B站会员购转售爬虫 - 每个实例独立 Session"""
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()
        self.session = None
        self._lock = threading.Lock()  # 单实例内并发安全
        self._init_session()
    
    def _get_user_agent(self) -> str:
        """获取当前 Session 的固定 UA。"""
        if not hasattr(self, "user_agent") or not self.user_agent:
            self.user_agent = random.choice(USER_AGENTS)
        return self.user_agent
    
    def _build_headers(self) -> Dict[str, str]:
        """构建与当前 UA / 平台一致的浏览器请求头。"""
        ua = self._get_user_agent()
        chrome_match = re.search(r"Chrome/(\d+)", ua)
        chrome_version = chrome_match.group(1) if chrome_match else "140"
        return {
            "Content-Type": "application/json",
            "User-Agent": ua,
            "Referer": self.config.referer,
            "Origin": "https://mall.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "sec-ch-ua": f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
    
    def _init_session(self):
        """初始化独立 Session"""
        if _HAS_REQUESTS:
            self.session = requests.Session()
            self._refresh_session()
    
    def _refresh_session(self):
        """刷新设备指纹 Cookie"""
        with self._lock:
            # 整个 Session 使用同一 UA；只有刷新 Session 指纹时才重新选择。
            self.user_agent = random.choice(USER_AGENTS)
            b3 = f"{uuid.uuid4()}{random.randint(10000, 99999)}infoc"
            b4 = str(uuid.uuid4())
            now_ts = int(time.time())
            uuid_str = f"{uuid.uuid4().hex}{now_ts % 100000}infoc"
            
            cookies = {
                "buvid3": b3,
                "buvid4": b4,
                "_uuid": uuid_str,
                "b_nut": str(now_ts),
                "buvid_fp": str(uuid.uuid4()).replace("-", ""),
                "fingerprint": str(uuid.uuid4()).replace("-", "")[:16],
            }
            
            if self.session:
                self.session.cookies.clear()
                for key, value in cookies.items():
                    self.session.cookies.set(key, value, domain=".bilibili.com")
                # 更新与新 UA 匹配的完整 headers
                headers = self._build_headers()
                self.session.headers.update(headers)
    
    def _api_post(self, path: str, body: Dict[str, Any], retries: Optional[int] = None) -> Dict[str, Any]:
        """调用 API，支持智能重试"""
        retries = retries or self.config.max_retries
        url = self.config.base_url + path
        
        if _HAS_REQUESTS and self.session:
            return self._api_post_requests(url, body, retries)
        else:
            return self._api_post_urllib(url, body, retries)
    
    def _api_post_requests(self, url: str, body: Dict[str, Any], retries: int) -> Dict[str, Any]:
        """使用 requests.Session 发送请求"""
        last_error = None
        rate_limit_streak = 0
        
        for attempt in range(1, retries + 1):
            try:
                # Session 内保持 UA 稳定，避免同一会话频繁跨设备/浏览器指纹跳变。
                resp = self.session.post(url, json=body, timeout=self.config.timeout)
                
                # 检查是否触发 429 或反爬
                is_rate_limited = (
                    resp.status_code == 429 or 
                    ('<html' in resp.text[:50].lower() if resp.text else False)
                )
                
                if is_rate_limited:
                    rate_limit_streak += 1
                    wait = self._calculate_wait_time(attempt)
                    refresh = rate_limit_streak >= 3
                    self._log_warning(
                        f"触发频控，等待 {wait:.1f}s 后重试 "
                        f"(第 {attempt}/{retries} 次，连续 {rate_limit_streak} 次)"
                    )
                    LOGGER.warning(
                        "api retry url=%s attempt=%d/%d reason=rate_limited "
                        "rate_limit_streak=%d wait=%.1fs refresh_session=%s",
                        url, attempt, retries, rate_limit_streak, wait, refresh
                    )
                    time.sleep(wait)
                    if refresh:
                        self._refresh_session()
                        rate_limit_streak = 0
                        LOGGER.warning(
                            "api session refreshed url=%s attempt=%d/%d reason=consecutive_rate_limits",
                            url, attempt, retries
                        )
                    continue
                
                if resp.status_code == 200:
                    rate_limit_streak = 0
                    payload = resp.json()
                    if not payload.get("success", True):
                        error_msg = payload.get('message', '未知错误')
                        raise RuntimeError(f"接口返回失败: {error_msg}")
                    return payload.get("data", {})
                else:
                    rate_limit_streak = 0
                    raise requests.exceptions.HTTPError(f"HTTP {resp.status_code}")
                    
            except json.JSONDecodeError as e:
                wait = self._calculate_wait_time(attempt) * 2
                self._log_warning(f"JSON 解析失败 (可能反爬)，等待 {wait:.1f}s 后重试")
                LOGGER.warning(
                    "api retry url=%s attempt=%d/%d reason=json_decode_error wait=%.1fs",
                    url, attempt, retries, wait
                )
                self._refresh_session()
                time.sleep(wait)
                last_error = e
                
            except requests.exceptions.Timeout as e:
                rate_limit_streak = 0
                wait = attempt * 1.5
                self._log_warning(f"请求超时，等待 {wait:.1f}s 后重试")
                LOGGER.warning(
                    "api retry url=%s attempt=%d/%d reason=timeout wait=%.1fs error=%s",
                    url, attempt, retries, wait, e
                )
                time.sleep(wait)
                last_error = e
                
            except requests.exceptions.RequestException as e:
                rate_limit_streak = 0
                wait = attempt * 2.0
                self._log_warning(f"请求异常: {e}，等待 {wait:.1f}s 后重试")
                LOGGER.warning(
                    "api retry url=%s attempt=%d/%d reason=request_exception wait=%.1fs error=%s",
                    url, attempt, retries, wait, e
                )
                time.sleep(wait)
                last_error = e
                
            except Exception as e:
                rate_limit_streak = 0
                if attempt >= retries:
                    raise RuntimeError(f"请求失败 ({url}): {e}")
                LOGGER.warning(
                    "api retry url=%s attempt=%d/%d reason=exception wait=1.5s error=%s",
                    url, attempt, retries, e
                )
                time.sleep(1.5)
                last_error = e
        
        LOGGER.error("api retries exhausted url=%s attempts=%d last_error=%s", url, retries, last_error)
        raise RuntimeError(f"接口重试 {retries} 次仍失败: {last_error}")
    
    def _api_post_urllib(self, url: str, body: Dict[str, Any], retries: int) -> Dict[str, Any]:
        """使用 urllib 发送请求（回退方案）"""
        data = json.dumps(body).encode("utf-8")
        last_error = None
        rate_limit_streak = 0
        
        for attempt in range(1, retries + 1):
            headers = self._build_headers()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                if not payload.get("success", True):
                    raise RuntimeError(f"接口返回失败: {payload.get('message', '未知错误')}")
                return payload.get("data", {})
                
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    rate_limit_streak += 1
                    wait = self._calculate_wait_time(attempt)
                    refresh = rate_limit_streak >= 3
                    self._log_warning(
                        f"触发频控，等待 {wait:.1f}s 后重试 "
                        f"(第 {attempt}/{retries} 次，连续 {rate_limit_streak} 次)"
                    )
                    LOGGER.warning(
                        "api retry url=%s attempt=%d/%d reason=rate_limited "
                        "rate_limit_streak=%d wait=%.1fs refresh_session=%s",
                        url, attempt, retries, rate_limit_streak, wait, refresh
                    )
                    time.sleep(wait)
                    if refresh:
                        self._refresh_session()
                        LOGGER.warning(
                            "api session refreshed url=%s attempt=%d/%d reason=consecutive_rate_limits",
                            url, attempt, retries
                        )
                        rate_limit_streak = 0
                    last_error = RuntimeError(f"HTTP 429: {url}")
                else:
                    rate_limit_streak = 0
                    last_error = RuntimeError(f"HTTP {e.code}: {e.reason}")
                    if attempt < retries:
                        LOGGER.warning(
                            "api retry url=%s attempt=%d/%d reason=http_%d wait=1.5s",
                            url, attempt, retries, e.code
                        )
                        time.sleep(1.5)
                        
            except urllib.error.URLError as e:
                rate_limit_streak = 0
                last_error = RuntimeError(f"网络错误: {e.reason}")
                if attempt < retries:
                    LOGGER.warning(
                        "api retry url=%s attempt=%d/%d reason=url_error wait=2.0s error=%s",
                        url, attempt, retries, e.reason
                    )
                    time.sleep(2.0)
                    
            except json.JSONDecodeError as e:
                rate_limit_streak = 0
                wait = self._calculate_wait_time(attempt) * 2
                self._log_warning(f"JSON 解析失败，等待 {wait:.1f}s 后重试")
                LOGGER.warning(
                    "api retry url=%s attempt=%d/%d reason=json_decode_error wait=%.1fs",
                    url, attempt, retries, wait
                )
                time.sleep(wait)
                last_error = e
                
            except Exception as e:
                rate_limit_streak = 0
                last_error = RuntimeError(f"请求异常: {e}")
                if attempt < retries:
                    LOGGER.warning(
                        "api retry url=%s attempt=%d/%d reason=exception wait=1.5s error=%s",
                        url, attempt, retries, e
                    )
                    time.sleep(1.5)
        
        final_error = last_error or RuntimeError("未知错误")
        LOGGER.error("api retries exhausted url=%s attempts=%d last_error=%s", url, retries, final_error)
        raise final_error
    
    def _calculate_wait_time(self, attempt: int) -> float:
        """计算退避等待时间（带随机抖动）"""
        base = self.config.rate_limit_wait_base
        wait = attempt * base
        jitter = random.uniform(0.9, 1.2)
        return wait * jitter
    
    def _log_warning(self, msg: str):
        print(f"\n  [⚠] {msg}", file=sys.stderr, flush=True)
    
    def get_home(self) -> Dict[str, Any]:
        """获取首页信息"""
        return self._api_post("/resell/home", {})
    
    def get_feed(self, page_num: int = 1, page_size: int = 20, 
                 sort_type: str = "hot", category_id: Optional[str] = None, 
                 ip_id: Optional[str] = None) -> Dict[str, Any]:
        """获取商品流"""
        filters = {}
        if category_id:
            filters["productCategory"] = category_id
        if ip_id:
            filters["ipId"] = ip_id
            
        body = {
            "pageNum": page_num,
            "pageSize": page_size,
            "sortType": sort_type,
            "filters": filters,
        }
        return self._api_post("/resell/feed", body)
    
    def get_cluster_info(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """获取商品详情与成交信息"""
        url = "https://mall.bilibili.com/mall-search-items/items_detail/cluster_info"
        LOGGER.info("detail request cluster_id=%s", cluster_id)
        
        if _HAS_REQUESTS and self.session:
            for attempt in range(1, 4):
                try:
                    resp = self.session.post(url, json={"clusterId": str(cluster_id)}, 
                                            timeout=self.config.timeout)
                    if resp.status_code == 200:
                        payload = resp.json()
                        if payload.get("code") == 0:
                            parsed = self._parse_cluster_detail(payload.get("data", {}))
                            LOGGER.info("detail success cluster_id=%s parsed_cluster_id=%s deals=%d chart_points=%d fields=%s", cluster_id, parsed.get("cluster_id"), len(parsed.get("deals", [])), len(parsed.get("chart_points", [])), list((payload.get("data") or {}).keys()))
                            return parsed
                        LOGGER.warning("detail rejected cluster_id=%s status=%s code=%s message=%s", cluster_id, resp.status_code, payload.get("code"), payload.get("message"))
                    else:
                        LOGGER.warning("detail http failure cluster_id=%s status=%s", cluster_id, resp.status_code)
                except Exception as e:
                    LOGGER.warning("detail request error cluster_id=%s attempt=%d error=%s", cluster_id, attempt, e)
                    if attempt >= 3:
                        self._log_warning(f"获取商品详情失败 ({cluster_id}): {e}")
                    time.sleep(1.0)
            return None
        
        # urllib 回退
        data = json.dumps({"clusterId": str(cluster_id)}).encode("utf-8")
        headers = self._build_headers()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("code") == 0:
                    parsed = self._parse_cluster_detail(payload.get("data", {}))
                    LOGGER.info("detail success cluster_id=%s parsed_cluster_id=%s deals=%d chart_points=%d fields=%s", cluster_id, parsed.get("cluster_id"), len(parsed.get("deals", [])), len(parsed.get("chart_points", [])), list((payload.get("data") or {}).keys()))
                    return parsed
                LOGGER.warning("detail rejected cluster_id=%s code=%s message=%s", cluster_id, payload.get("code"), payload.get("message"))
        except Exception as e:
            LOGGER.warning("detail request error cluster_id=%s error=%s", cluster_id, e)
            self._log_warning(f"获取商品详情失败 ({cluster_id}): {e}")
        return None
    
    def _parse_cluster_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析商品详情数据"""
        basic = data.get("clusterBasicInfoFloorVO") or {}
        price_floor = data.get("clusterPriceFloorVO") or {}
        recent_buy = data.get("clusterRecentBuyFloorVO") or {}
        attr_floor = data.get("clusterAttrFloorVO") or {}
        header_floor = data.get("clusterHeaderFloorVO") or {}
        btn_floor = data.get("clusterPurchaseButton") or {}
        
        chart_points = []
        if recent_buy.get("chartData"):
            chart_points = recent_buy["chartData"].get("chartPoints", [])
        deals = recent_buy.get("recentDeals") or []
        cluster_id = data.get("clusterId") or basic.get("clusterId") or ""
        deal_field = "deals" if recent_buy.get("deals") else ("recentDeals" if recent_buy.get("recentDeals") else "none")
        LOGGER.info("detail payload cluster_id=%s basic_fields=%s recent_buy_fields=%s deal_field=%s deals=%d chart_points=%d", cluster_id, list(basic.keys()), list(recent_buy.keys()), deal_field, len(deals), len(chart_points))
        
        latest_deal_price = None
        if deals and len(deals) > 0 and deals[0].get("dealPrice"):
            latest_deal_price = str(deals[0].get("dealPrice"))
        elif chart_points and len(chart_points) > 0:
            last_pt = chart_points[-1]
            p_val = last_pt.get("avgPrice") or last_pt.get("price")
            if p_val:
                p_val_str = str(p_val).strip()
                latest_deal_price = p_val_str if p_val_str.startswith("¥") else f"¥{p_val_str}"
        
        return {
            "cluster_id": str(cluster_id),
            "title": basic.get("clusterName", ""),
            "images": header_floor.get("clusterImgList", []),
            "price_tag": price_floor.get("priceTag", {}),
            "lowest_price": btn_floor.get("buttonSubText", ""),
            "latest_deal_price": latest_deal_price,
            "attributes": attr_floor.get("attrList", []),
            "chart_points": chart_points,
            "deals": deals,
        }


_detail_worker_local = threading.local()


def fetch_detail_with_worker(config: CrawlerConfig, cluster_id: str) -> Optional[Dict[str, Any]]:
    crawler = getattr(_detail_worker_local, "crawler", None)
    if crawler is None:
        crawler = BiliResellCrawler(config)
        _detail_worker_local.crawler = crawler
    try:
        detail = crawler.get_cluster_info(cluster_id)
    except Exception as exc:
        LOGGER.warning("detail worker error cluster_id=%s error=%s", cluster_id, exc)
        detail = None
    time.sleep(random.uniform(0.5, 1.0))
    return detail


DETAIL_FAILURE_ID_OUTPUT_LIMIT = 20


def report_crawl_summary(list_stats: Dict[str, Any], detail_success: Optional[int] = None, detail_failures: Optional[List[str]] = None):
    detail_failures = detail_failures or []
    console_lines = [
        "",
        "【抓取统计】",
        f"  列表请求：成功 {list_stats['succeeded']} 页，失败 {list_stats['failed']} 页",
    ]
    log_lines = list(console_lines)

    for failure in list_stats["failures"]:
        line = f"  列表失败：sort={failure['sort']} page={failure['page']} error={failure['error']}"
        console_lines.append(line)
        log_lines.append(line)

    if detail_success is None:
        console_lines.append("  详情请求：未启用")
        log_lines.append("  详情请求：未启用")
    else:
        console_lines.append(f"  详情请求：成功 {detail_success} 条，失败 {len(detail_failures)} 条")
        log_lines.append(f"  详情请求：成功 {detail_success} 条，失败 {len(detail_failures)} 条")
        if detail_failures:
            failure_ids_line = f"  详情失败商品 ID：{', '.join(detail_failures)}"
            log_lines.append(failure_ids_line)
            if len(detail_failures) <= DETAIL_FAILURE_ID_OUTPUT_LIMIT:
                console_lines.append(failure_ids_line)
            else:
                console_lines.append(f"  详情失败商品 ID 过多（{len(detail_failures)} 个），终端不展开；完整 ID 已写入日志。")

    for line in console_lines:
        print(line)
    for line in log_lines:
        LOGGER.info(line)

# ==================== SQLite 数据管理类 ====================
class SQLiteDataManager:
    """SQLite 数据管理。

    数据模型：
      products          商品主表，只保存商品当前/静态信息
      crawl_runs        每次抓取的批次信息
      product_snapshots 每次抓取的价格/标签历史快照

    这样可以避免每次抓取重复保存 title/img/url，同时保留完整价格历史。
    """

    def __init__(self, db_path: str = str(DEFAULT_DB_PATH)):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    category TEXT,
                    img TEXT,
                    url TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    category TEXT,
                    ip_id TEXT,
                    sort_type TEXT,
                    requested_pages INTEGER,
                    actual_pages INTEGER,
                    product_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'running'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    crawl_run_id INTEGER NOT NULL,
                    price REAL,
                    reference_price REAL,
                    discount TEXT,
                    popularity TEXT,
                    captured_at TEXT NOT NULL,
                    FOREIGN KEY(product_id) REFERENCES products(id),
                    FOREIGN KEY(crawl_run_id) REFERENCES crawl_runs(id),
                    UNIQUE(product_id, crawl_run_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_product_time ON product_snapshots(product_id, captured_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_run ON product_snapshots(crawl_run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_category_time ON crawl_runs(category, started_at)")
            conn.execute("CREATE TABLE IF NOT EXISTS catalog_filters (id INTEGER PRIMARY KEY AUTOINCREMENT, filter_type TEXT NOT NULL, item_id TEXT NOT NULL, name TEXT, captured_at TEXT NOT NULL, UNIQUE(filter_type, item_id))")
            conn.execute("CREATE TABLE IF NOT EXISTS home_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, crawl_run_id INTEGER, title_img TEXT, entry_text TEXT, entry_url TEXT, discount_title TEXT, discount_subtitle TEXT, captured_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS product_details (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL UNIQUE, lowest_price TEXT, latest_deal_price TEXT, price_tag TEXT, attributes TEXT, images TEXT, captured_at TEXT NOT NULL, FOREIGN KEY(product_id) REFERENCES products(id))")
            conn.execute("CREATE TABLE IF NOT EXISTS product_deals (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, deal_json TEXT NOT NULL, captured_at TEXT NOT NULL, FOREIGN KEY(product_id) REFERENCES products(id))")
            conn.execute("CREATE TABLE IF NOT EXISTS product_price_points (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, point_json TEXT NOT NULL, captured_at TEXT NOT NULL, FOREIGN KEY(product_id) REFERENCES products(id))")
            conn.execute("CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL DEFAULT 'default', product_id INTEGER NOT NULL, created_at TEXT NOT NULL, UNIQUE(user_id, product_id), FOREIGN KEY(product_id) REFERENCES products(id))")

    def save_home(self, home: Dict[str, Any], captured_at: str, crawl_run_id: Optional[int] = None):
        fb = home.get("filterBar", {})
        floor = home.get("discountFloor", {})
        header = home.get("header", {})
        right = header.get("rightEntry", {})
        with self.get_connection() as conn:
            for key, values in (("sort", fb.get("sortTypes", [])), ("category", fb.get("quickCategories", [])), ("ip", fb.get("quickIp", []))):
                for item in values:
                    item_id = item.get("type") or item.get("id")
                    if item_id is not None:
                        conn.execute("INSERT OR REPLACE INTO catalog_filters(filter_type,item_id,name,captured_at) VALUES (?,?,?,?)", (key, str(item_id), item.get("name"), captured_at))
            conn.execute("INSERT INTO home_snapshots(crawl_run_id,title_img,entry_text,entry_url,discount_title,discount_subtitle,captured_at) VALUES (?,?,?,?,?,?,?)", (crawl_run_id, header.get("titleImg"), right.get("text"), right.get("jumpUrl"), floor.get("title"), floor.get("subTitle"), captured_at))

    def save_detail(self, detail: Dict[str, Any], crawl_run_id: int):
        cluster_id = str(detail.get("cluster_id", ""))
        if not cluster_id:
            LOGGER.warning("detail skipped reason=missing_cluster_id crawl_run_id=%s", crawl_run_id)
            return
        captured_at = self.get_run_time(crawl_run_id)
        with self.get_connection() as conn:
            row = conn.execute("SELECT id FROM products WHERE cluster_id=?", (cluster_id,)).fetchone()
            if not row:
                LOGGER.warning("detail skipped cluster_id=%s reason=product_not_found crawl_run_id=%s", cluster_id, crawl_run_id)
                return
            product_id = row[0]
            conn.execute("INSERT OR REPLACE INTO product_details(product_id,lowest_price,latest_deal_price,price_tag,attributes,images,captured_at) VALUES (?,?,?,?,?,?,?)", (product_id, detail.get("lowest_price"), detail.get("latest_deal_price"), json.dumps(detail.get("price_tag"), ensure_ascii=False), json.dumps(detail.get("attributes", []), ensure_ascii=False), json.dumps(detail.get("images", []), ensure_ascii=False), captured_at))
            conn.execute("DELETE FROM product_deals WHERE product_id=?", (product_id,))
            for deal in detail.get("deals", []):
                conn.execute("INSERT INTO product_deals(product_id,deal_json,captured_at) VALUES (?,?,?)", (product_id, json.dumps(deal, ensure_ascii=False), captured_at))
            for point in detail.get("chart_points", []):
                conn.execute("INSERT INTO product_price_points(product_id,point_json,captured_at) VALUES (?,?,?)", (product_id, json.dumps(point, ensure_ascii=False), captured_at))
            LOGGER.info("detail saved cluster_id=%s product_id=%s deals=%d chart_points=%d", cluster_id, product_id, len(detail.get("deals", [])), len(detail.get("chart_points", [])))

    def _migrate_legacy_products(self, conn):
        """迁移旧版 products(cluster_id, ..., crawl_time) 单表结构。"""
        legacy = "products_legacy_v1"
        conn.execute(f"ALTER TABLE products RENAME TO {legacy}")
        conn.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT,
                img TEXT,
                url TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE crawl_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                category TEXT,
                ip_id TEXT,
                sort_type TEXT,
                requested_pages INTEGER,
                actual_pages INTEGER,
                product_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'success'
            )
        """)
        conn.execute("""
            CREATE TABLE product_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                crawl_run_id INTEGER NOT NULL,
                price REAL,
                reference_price REAL,
                discount TEXT,
                popularity TEXT,
                captured_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(crawl_run_id) REFERENCES crawl_runs(id),
                UNIQUE(product_id, crawl_run_id)
            )
        """)

        rows = conn.execute(f"SELECT * FROM {legacy} ORDER BY crawl_time, id").fetchall()
        if not rows:
            return

        run_ids = {}
        for row in rows:
            key = (row["crawl_time"], row["category"])
            if key not in run_ids:
                cur = conn.execute(
                    "INSERT INTO crawl_runs(started_at, finished_at, category, product_count, status) VALUES (?, ?, ?, 0, 'success')",
                    (row["crawl_time"], row["crawl_time"], row["category"])
                )
                run_ids[key] = cur.lastrowid

            product = conn.execute("SELECT id FROM products WHERE cluster_id = ?", (row["cluster_id"],)).fetchone()
            if product:
                product_id = product[0]
                conn.execute("""
                    UPDATE products
                    SET title=?, category=?, img=?, url=?, last_seen_at=?, is_active=1
                    WHERE id=?
                """, (row["title"], row["category"], row["img"], row["url"], row["crawl_time"], product_id))
            else:
                cur = conn.execute("""
                    INSERT INTO products(cluster_id, title, category, img, url, first_seen_at, last_seen_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (row["cluster_id"], row["title"], row["category"], row["img"], row["url"], row["crawl_time"], row["crawl_time"]))
                product_id = cur.lastrowid

            def to_float(value):
                if value is None:
                    return None
                text = str(value).replace("¥", "").replace(",", "").strip()
                try:
                    return float(text) if text else None
                except ValueError:
                    return None

            conn.execute("""
                INSERT OR IGNORE INTO product_snapshots
                (product_id, crawl_run_id, price, reference_price, discount, popularity, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_id, run_ids[key], to_float(row["price"]), to_float(row["reference_price"]),
                  row["discount"], row["popularity"], row["crawl_time"]))

        for run_id in run_ids.values():
            count = conn.execute("SELECT COUNT(*) FROM product_snapshots WHERE crawl_run_id=?", (run_id,)).fetchone()[0]
            conn.execute("UPDATE crawl_runs SET product_count=? WHERE id=?", (count, run_id))

    def start_crawl(self, category: Optional[str], ip_id: Optional[str], sort_type: str, requested_pages: int) -> int:
        started_at = datetime.now().isoformat(timespec="microseconds")
        with self.get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO crawl_runs(
                    started_at, category, ip_id, sort_type, requested_pages,
                    actual_pages, product_count, status
                )
                VALUES (?, ?, ?, ?, ?, 0, 0, 'running')
            """, (started_at, category, ip_id, sort_type, requested_pages))
            return cur.lastrowid

    def get_run_time(self, crawl_run_id: int) -> str:
        """获取本次抓取的唯一时间戳。"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT started_at FROM crawl_runs WHERE id=?", (crawl_run_id,)).fetchone()
            if not row:
                raise ValueError(f"不存在的 crawl_run_id: {crawl_run_id}")
            return row[0]

    def finish_crawl(self, crawl_run_id: int, product_count: int, status: str = "success", actual_pages: Optional[int] = None):
        finished_at = datetime.now().isoformat(timespec="microseconds")
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE crawl_runs
                SET finished_at=?, product_count=?, status=?, actual_pages=COALESCE(?, actual_pages)
                WHERE id=?
            """, (finished_at, product_count, status, actual_pages, crawl_run_id))

    def save_products(self, products: List[Product], crawl_run_id: int):
        if not products:
            return
        with self.get_connection() as conn:
            run = conn.execute("SELECT started_at FROM crawl_runs WHERE id=?", (crawl_run_id,)).fetchone()
            if not run:
                raise ValueError(f"不存在的 crawl_run_id: {crawl_run_id}")
            captured_at = run["started_at"]

            for p in products:
                # 商品主表：只维护当前元数据。
                conn.execute("""
                    INSERT INTO products(cluster_id, title, category, img, url, first_seen_at, last_seen_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(cluster_id) DO UPDATE SET
                        title=excluded.title,
                        category=excluded.category,
                        img=excluded.img,
                        url=excluded.url,
                        last_seen_at=excluded.last_seen_at,
                        is_active=1
                """, (p.cluster_id, p.title, p.category, p.img, p.url, captured_at, captured_at))

                product_id = conn.execute("SELECT id FROM products WHERE cluster_id=?", (p.cluster_id,)).fetchone()[0]
                conn.execute("""
                    INSERT OR REPLACE INTO product_snapshots
                    (product_id, crawl_run_id, price, reference_price, discount, popularity, captured_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id, crawl_run_id,
                    Product._price_to_float(p.price),
                    Product._price_to_float(p.reference_price),
                    p.discount, p.popularity, captured_at
                ))

    def get_history_rows(self, category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = """
            SELECT s.id, s.captured_at AS crawl_time,
                   p.cluster_id, p.title, s.price, s.reference_price,
                   s.discount, s.popularity, p.img, p.url, p.category
            FROM product_snapshots s
            JOIN products p ON p.id = s.product_id
        """
        params = []
        if category:
            sql += " WHERE p.category = ?"
            params.append(category)
        sql += " ORDER BY s.captured_at DESC, s.id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.get_connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_times(self, category: Optional[str] = None) -> List[str]:
        sql = """
            SELECT DISTINCT r.started_at
            FROM crawl_runs r
            JOIN product_snapshots s ON s.crawl_run_id = r.id
        """
        params = []
        if category:
            sql += " WHERE r.category = ?"
            params.append(category)
        sql += " ORDER BY r.started_at"
        with self.get_connection() as conn:
            return [row[0] for row in conn.execute(sql, params).fetchall()]

    def get_price_history(self, cluster_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT s.captured_at AS crawl_time, s.price
                FROM product_snapshots s
                JOIN products p ON p.id = s.product_id
                WHERE p.cluster_id = ?
                ORDER BY s.captured_at DESC
                LIMIT ?
            """, (cluster_id, limit)).fetchall()
            return [dict(row) for row in rows]

    def detect_alerts_sql(self, category: Optional[str] = None,
                          current_time: Optional[str] = None,
                          prev_n: int = 3,
                          abs_th: float = 10.0,
                          pct_th: float = 0.10) -> Optional[Dict[str, Any]]:
        times = self.get_times(category)
        if not times:
            return None
        if current_time and current_time in times:
            idx = times.index(current_time)
        else:
            idx = len(times) - 1
            current_time = times[idx]
        if idx < 1:
            return {"alerts": [], "current_time": current_time, "prev_times": [], "baseline_count": 0}

        prev_times = times[max(0, idx - prev_n):idx]
        placeholders = ",".join("?" for _ in prev_times)
        with self.get_connection() as conn:
            sql = f"""
                WITH current_prices AS (
                    SELECT p.cluster_id, p.title, p.url, s.price AS current_price
                    FROM product_snapshots s
                    JOIN products p ON p.id=s.product_id
                    JOIN crawl_runs r ON r.id=s.crawl_run_id
                    WHERE r.started_at = ? {"AND r.category = ?" if category else ""}
                ),
                history_prices AS (
                    SELECT p.cluster_id, MAX(s.price) AS max_price
                    FROM product_snapshots s
                    JOIN products p ON p.id=s.product_id
                    JOIN crawl_runs r ON r.id=s.crawl_run_id
                    WHERE r.started_at IN ({placeholders}) {"AND r.category = ?" if category else ""}
                    GROUP BY p.cluster_id
                )
                SELECT c.cluster_id, c.title, c.url,
                       c.current_price, h.max_price AS high_price,
                       (h.max_price-c.current_price) AS drop_abs,
                       ((h.max_price-c.current_price)/h.max_price) AS drop_pct
                FROM current_prices c
                JOIN history_prices h ON c.cluster_id=h.cluster_id
                WHERE c.current_price > 0 AND h.max_price > c.current_price
                  AND ((h.max_price-c.current_price) > ?
                       OR ((h.max_price-c.current_price)/h.max_price) > ?)
                ORDER BY drop_pct DESC, drop_abs DESC
            """
            params = [current_time]
            if category:
                params.append(category)
            params.extend(prev_times)
            if category:
                params.append(category)
            params.extend([abs_th, pct_th])
            alerts = [dict(row) for row in conn.execute(sql, params).fetchall()]

            count_sql = """
                SELECT COUNT(DISTINCT s.product_id)
                FROM product_snapshots s
                JOIN crawl_runs r ON r.id=s.crawl_run_id
                WHERE r.started_at = ?
            """
            count_params = [current_time]
            if category:
                count_sql += " AND r.category = ?"
                count_params.append(category)
            total = conn.execute(count_sql, count_params).fetchone()[0]
            return {"alerts": alerts, "current_time": current_time,
                    "prev_times": prev_times, "baseline_count": total}

    def analyze_trend_sql(self, category: Optional[str] = None):
        times = self.get_times(category)
        if len(times) < 2:
            print(f"需要至少 2 次抓取记录才能分析 (当前 {len(times)} 次)")
            return
        cur_t, prev_t = times[-1], times[-2]

        with self.get_connection() as conn:
            sql = """
                WITH current_prices AS (
                    SELECT p.cluster_id, p.title, s.price AS price_num
                    FROM product_snapshots s
                    JOIN products p ON p.id=s.product_id
                    JOIN crawl_runs r ON r.id=s.crawl_run_id
                    WHERE r.started_at = ?
                ),
                prev_prices AS (
                    SELECT p.cluster_id, s.price AS price_num
                    FROM product_snapshots s
                    JOIN products p ON p.id=s.product_id
                    JOIN crawl_runs r ON r.id=s.crawl_run_id
                    WHERE r.started_at = ?
                )
                SELECT c.cluster_id, c.title, p.price_num AS prev_price,
                       c.price_num AS cur_price, (c.price_num-p.price_num) AS diff
                FROM current_prices c
                LEFT JOIN prev_prices p ON c.cluster_id=p.cluster_id
                WHERE c.price_num > 0
            """
            params = [cur_t, prev_t]
            if category:
                sql = sql.replace("WHERE r.started_at = ?\n                ),", "WHERE r.started_at = ? AND r.category = ?\n                ),", 1)
                sql = sql.replace("WHERE r.started_at = ?\n                )\n                SELECT", "WHERE r.started_at = ? AND r.category = ?\n                )\n                SELECT", 1)
                params = [cur_t, category, prev_t, category]
            rows = conn.execute(sql, params).fetchall()

            up, down, same = [], [], 0
            for row in rows:
                if row['prev_price'] is None:
                    continue
                diff = row['diff']
                if diff > 0.01:
                    up.append((row['title'], row['prev_price'], row['cur_price'], diff))
                elif diff < -0.01:
                    down.append((row['title'], row['prev_price'], row['cur_price'], diff))
                else:
                    same += 1

            new_sql = """
                SELECT p.cluster_id, p.title, s.price
                FROM product_snapshots s
                JOIN products p ON p.id=s.product_id
                JOIN crawl_runs r ON r.id=s.crawl_run_id
                WHERE r.started_at = ?
                  AND p.cluster_id NOT IN (
                    SELECT p2.cluster_id
                    FROM product_snapshots s2
                    JOIN products p2 ON p2.id=s2.product_id
                    JOIN crawl_runs r2 ON r2.id=s2.crawl_run_id
                    WHERE r2.started_at = ?
                  )
            """
            gone_sql = new_sql.replace("r.started_at = ?", "r.started_at = ?", 1).replace(
                "WHERE r2.started_at = ?", "WHERE r2.started_at = ?", 1)
            new_params = [cur_t, prev_t]
            gone_params = [prev_t, cur_t]
            if category:
                new_sql = new_sql.replace("WHERE r.started_at = ?", "WHERE r.started_at = ? AND r.category = ?", 1)
                new_sql = new_sql.replace("WHERE r2.started_at = ?", "WHERE r2.started_at = ? AND r2.category = ?", 1)
                new_params = [cur_t, category, prev_t, category]
                gone_sql = new_sql
                gone_params = [prev_t, category, cur_t, category]
            new_products = conn.execute(new_sql, new_params).fetchall()
            gone_products = conn.execute(gone_sql, gone_params).fetchall()

            cat_label = category if category else "all"
            print("\n" + "=" * 60)
            print(f"【价格走势对比】 分类={cat_label}")
            print(f"  本次: {cur_t}")
            print(f"  上次: {prev_t}")
            print(f"\n  价格上升 ▲: {len(up)} 个")
            for title, prev, cur, diff in sorted(up, key=lambda x: -x[3])[:15]:
                print(f"    ▲ {title}  ¥{prev:.2f} → ¥{cur:.2f}  (+{diff:.2f})")
            print(f"\n  价格下降 ▼: {len(down)} 个")
            for title, prev, cur, diff in sorted(down, key=lambda x: x[3])[:15]:
                print(f"    ▼ {title}  ¥{prev:.2f} → ¥{cur:.2f}  ({diff:.2f})")
            print(f"\n  价格不变: {same} 个")
            print(f"  本次新增上架 ＋: {len(new_products)} 个")
            for p in new_products[:15]:
                print(f"    ＋ {p['title']}  ¥{p['price']:.2f}" if p['price'] is not None else f"    ＋ {p['title']}  -")
            print(f"  本次下架/消失 －: {len(gone_products)} 个")
            for p in gone_products[:15]:
                print(f"    － {p['title']}  ¥{p['price']:.2f}" if p['price'] is not None else f"    － {p['title']}  -")

# ==================== 兼容 CSV 数据管理（保留） ====================
class CSVDataManager:
    """CSV 数据管理（向后兼容）"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
    
    def append_history(self, products: List[Product]):
        """追加到 CSV"""
        if not products:
            return
        
        exists = os.path.exists(self.csv_path)
        cols = ["crawl_time", "category", "cluster_id", "title", "price",
                "reference_price", "discount", "popularity", "img", "url"]
        
        with open(self.csv_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            if not exists:
                writer.writeheader()
            for p in products:
                writer.writerow(p.to_dict())

# ==================== 主程序 ====================
def main():
    log_path = configure_run_logger()
    parser = argparse.ArgumentParser(
        description="B站会员购转售商品爬虫 - 生产级优化版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python crawler.py                              # 默认全量抓取 3C 分类
  python crawler.py --pages 20                   # 抓取指定 20 页
  python crawler.py --category 142 --detail      # 抓取手办分类并获取详情
  python crawler.py --db products.db --trend     # 使用 SQLite 查看趋势
        """
    )
    
    # 抓取参数
    parser.add_argument("--pages", type=int, default=0,
                       help="抓取页数，设为 0 表示全量（默认: 全量）")
    parser.add_argument("--all", action="store_true",
                       help="全量抓取（等同于 --pages 0）")
    parser.add_argument("--sort", default="hot",
                       choices=["hot", "mostListings", "priceFirst"],
                       help="排序方式")
    parser.add_argument("--category", default="898",
                       help="商品分类 ID（默认: 898 = 3C 数码）")
    parser.add_argument("--ip", default=None,
                       help="IP 分区 ID")
    parser.add_argument("--detail", action="store_true",
                       help="获取商品详情（注意额外请求）")
    
    # 存储参数
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH),
                       help=f"SQLite 数据库路径（默认: {DEFAULT_DB_PATH}）")
    parser.add_argument("--csv", default=None,
                       help="CSV 导出路径（可选，向后兼容）")
    parser.add_argument("--json", default=None,
                       help="JSON 导出路径")
    
    # 分析参数
    parser.add_argument("--trend", action="store_true",
                       help="仅查看价格趋势（不抓取）")
    parser.add_argument("--list-filters", action="store_true",
                       help="仅列出筛选维度")
    parser.add_argument("--no-alert", action="store_true",
                       help="关闭价格异动检测")
    parser.add_argument("--alert-prev", type=int, default=3,
                       help="异动检测对比次数（默认: 3）")
    parser.add_argument("--alert-abs", type=float, default=10.0,
                       help="异动绝对阈值（元，默认: 10）")
    parser.add_argument("--alert-pct", type=float, default=0.10,
                       help="异动相对阈值（默认: 0.10 = 10%%）")
    parser.add_argument("--alert-csv", default=None,
                       help="导出异动到 CSV")
    
    # 其他
    parser.add_argument("--no-overview", action="store_true",
                       help="不打印首页概览")
    parser.add_argument("--quiet", action="store_true",
                       help="安静模式")
    
    args = parser.parse_args()
    
    if args.all:
        args.pages = 0
    
    # 初始化
    config = CrawlerConfig(default_pages=args.pages)
    crawler = BiliResellCrawler(config)
    db_mgr = SQLiteDataManager(args.db)
    
    category = None if args.category in ("", "all") else args.category
    ip_id = None if args.ip in ("", "all") else args.ip
    
    # 仅查看趋势
    if args.trend:
        db_mgr.analyze_trend_sql(category)
        return
    
    # 获取首页
    try:
        home = crawler.get_home()
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 创建抓取批次并保存首页/筛选数据；筛选模式也需要持久化这些信息。
    crawl_run_id = db_mgr.start_crawl(category, ip_id, args.sort, args.pages)
    crawl_time = db_mgr.get_run_time(crawl_run_id)
    db_mgr.save_home(home, crawl_time, crawl_run_id)

    if args.list_filters:
        list_filters(home)
        db_mgr.finish_crawl(crawl_run_id, 0, status="success", actual_pages=0)
        return
    
    if not args.no_overview:
        print_overview(home)
    
    try:
        products, list_stats = crawl_products(crawler, args, category, ip_id, args.quiet)
    except Exception:
        db_mgr.finish_crawl(crawl_run_id, 0, status="failed", actual_pages=getattr(crawler, "actual_pages", 0))
        raise

    if not products:
        report_crawl_summary(list_stats)
        db_mgr.finish_crawl(crawl_run_id, 0, status="empty", actual_pages=getattr(crawler, "actual_pages", 0))
        print("\n未获取到任何商品")
        return

    # 保存到 SQLite：商品主表 + 本次抓取快照
    for p in products:
        p.crawl_time = crawl_time
        p.category = category or "all"

    db_mgr.save_products(products, crawl_run_id)
    db_mgr.finish_crawl(crawl_run_id, len(products), status="success", actual_pages=getattr(crawler, "actual_pages", 0))
    print(f"已保存 {len(products)} 条商品快照到数据库 -> {args.db} (crawl_run={crawl_run_id})")
    
    # CSV 导出（可选）
    if args.csv:
        csv_mgr = CSVDataManager(args.csv)
        csv_mgr.append_history(products)
        print(f"已追加到 CSV -> {args.csv}")
    
    # JSON 导出
    if args.json:
        export_json(products, args.json, category, ip_id, args.sort)
        print(f"已导出 JSON -> {args.json}")
    
    # 获取详情
    if args.detail:
        print("\n【获取商品详情】")
        detail_results: List[Optional[Dict[str, Any]]] = [None] * len(products)
        detail_success = 0
        detail_failures = []
        with ThreadPoolExecutor(max_workers=min(DETAIL_WORKERS, len(products))) as executor:
            future_indices = {
                executor.submit(fetch_detail_with_worker, crawler.config, product.cluster_id): index
                for index, product in enumerate(products)
            }
            for completed, future in enumerate(as_completed(future_indices), 1):
                index = future_indices[future]
                product = products[index]
                try:
                    detail = future.result()
                except Exception as exc:
                    LOGGER.warning("detail future error cluster_id=%s error=%s", product.cluster_id, exc)
                    detail = None
                if detail:
                    detail_results[index] = detail
                    db_mgr.save_detail(detail, crawl_run_id)
                    detail_success += 1
                else:
                    detail_failures.append(str(product.cluster_id))
                    LOGGER.warning("detail failed cluster_id=%s", product.cluster_id)
                print(f"  [{completed}/{len(products)}] 获取 {product.title[:30]}...")
        details = [detail for detail in detail_results if detail is not None]
        
        if args.json:
            with open(args.json, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["details"] = details
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        detail_success = None
        detail_failures = None
    
    # 价格异动检测
    if not args.no_alert:
        alert_result = db_mgr.detect_alerts_sql(
            category, crawl_time,
            prev_n=args.alert_prev,
            abs_th=args.alert_abs,
            pct_th=args.alert_pct
        )
        
        if alert_result and alert_result["alerts"]:
            print_alerts(alert_result, args.alert_abs, args.alert_pct)
            if args.alert_csv:
                export_alerts_csv(alert_result["alerts"], args.alert_csv)
                print(f"已导出异动 -> {args.alert_csv}")

    report_crawl_summary(list_stats, detail_success, detail_failures)
    
    print("\n" + "=" * 60)
    print(f"完成！共获取 {len(products)} 条商品")

def crawl_products(crawler: BiliResellCrawler, args, 
                   category: Optional[str], ip_id: Optional[str],
                   quiet: bool = False) -> Tuple[List[Product], Dict[str, Any]]:
    """抓取商品 - 使用动态终止策略"""
    
    crawler.actual_pages = 0
    if args.pages == 0:
        max_pages = crawler.config.max_pages
        mode = "全量"
    else:
        max_pages = args.pages
        mode = f"前 {args.pages} 页"
    
    cat_label = f"分类={category}" if category else "全部分类"
    ip_label = f"IP={ip_id}" if ip_id else ""
    print(f"\n【商品流】 模式={mode} {cat_label} {ip_label}")
    
    all_sorts = ["hot", "mostListings", "priceFirst"]
    sort_type = args.sort if args.sort in all_sorts else "hot"
    sort_modes = [sort_type]
    per_sort_limit = max_pages
    
    seen_ids: Set[str] = set()
    products: List[Product] = []
    list_stats = {"attempted": 0, "succeeded": 0, "failed": 0, "failures": []}
    
    for sort_idx, sort_type in enumerate(sort_modes, 1):
        if len(sort_modes) > 1:
            print(f"\n>>> [{sort_idx}/{len(sort_modes)}] 抓取排序「{sort_type}」")
        
        # 动态终止策略：记录最近 N 页的新增率
        recent_rates = deque(maxlen=crawler.config.window_size)
        low_new_streak = 0
        
        actual_limit = per_sort_limit if args.pages == 0 else max_pages
        
        for page in range(1, actual_limit + 1):
            crawler.actual_pages += 1
            feed = None
            last_error = None
            total_page_attempts = crawler.config.page_retries + 1
            for page_attempt in range(1, total_page_attempts + 1):
                list_stats["attempted"] += 1
                try:
                    feed = crawler.get_feed(
                        page_num=page,
                        sort_type=sort_type,
                        category_id=category,
                        ip_id=ip_id
                    )
                    list_stats["succeeded"] += 1
                    break
                except Exception as e:
                    last_error = e
                    LOGGER.warning(
                        "page retry sort=%s page=%d attempt=%d/%d wait=%.1fs error=%s",
                        sort_type, page, page_attempt, total_page_attempts,
                        crawler.config.page_retry_wait if page_attempt < total_page_attempts else 0.0,
                        e
                    )
                    if page_attempt < total_page_attempts:
                        if not quiet:
                            print(f"  第{page}页抓取失败，等待 {crawler.config.page_retry_wait:.1f}s 后重试 ({page_attempt}/{crawler.config.page_retries})")
                        time.sleep(crawler.config.page_retry_wait)

            if feed is None:
                e = last_error or RuntimeError("unknown page fetch error")
                list_stats["failed"] += 1
                failure = {"sort": sort_type, "page": page, "error": str(e)}
                list_stats["failures"].append(failure)
                LOGGER.warning("list fetch failed sort=%s page=%s error=%s", sort_type, page, e)
                if not quiet:
                    print(f"  第{page}页抓取失败: {e}")
                continue
            
            items = feed.get("items", [])
            if not items:
                if not quiet:
                    print(f"  第{page}页返回空列表，该维度已抓完")
                break
            
            # 去重
            added = []
            for item in items:
                pid = str(item.get("id", ""))
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    product = Product.from_api_item(item, category or "all")
                    products.append(product)
                    added.append(product)
            
            # 计算新增率
            new_rate = len(added) / len(items) if items else 0
            recent_rates.append(new_rate)
            
            if not quiet:
                print(f"  第{page:02d}页 | 新增 {len(added):02d}/{len(items)} 条 | 新增率 {new_rate:.1%} | 累计 {len(products)} 条")
            
            # 动态终止判断：基于新增率
            if len(recent_rates) == crawler.config.window_size:
                avg_rate = sum(recent_rates) / len(recent_rates)
                if avg_rate < crawler.config.min_new_threshold:
                    low_new_streak += 1
                else:
                    low_new_streak = 0
                
                if low_new_streak >= crawler.config.low_new_streak_limit:
                    if not quiet:
                        print(f"  连续 {low_new_streak} 页新增率 < {crawler.config.min_new_threshold:.1%}，停止抓取")
                    break
            
            time.sleep(random.uniform(*crawler.config.request_interval))
            
    
    return products, list_stats

def print_overview(home: Dict[str, Any]):
    """打印首页概览"""
    header = home.get("header", {})
    right = header.get("rightEntry", {})
    print("=" * 60)
    print("【页面概览】")
    if header.get("titleImg"):
        print(f"  标题图: {header.get('titleImg')}")
    if right.get("text"):
        print(f"  入口: {right.get('text')} -> {right.get('jumpUrl')}")
    
    floor = home.get("discountFloor", {})
    items = floor.get("items", [])
    if items:
        print(f"\n【{floor.get('title', '限时大漏')}】{floor.get('subTitle', '')}")
        for it in items[:5]:
            product = Product.from_api_item(it)
            line = f"  - {product.title}  {product.price}"
            if product.reference_price:
                line += f" (原价 {product.reference_price})"
            if product.discount:
                line += f"  [{product.discount}]"
            print(line)
        if len(items) > 5:
            print(f"  ... 还有 {len(items)-5} 个")

def list_filters(home: Dict[str, Any]):
    """列出可用的筛选维度"""
    fb = home.get("filterBar", {})
    print("【排序 sort_type】")
    for s in fb.get("sortTypes", []):
        mark = " *" if s.get("selected") else ""
        print(f"  {s.get('type')}: {s.get('name')}{mark}")
    print("\n【商品分类 category_id】")
    for c in fb.get("quickCategories", []):
        print(f"  {c.get('id')}: {c.get('name')}")
    print("\n【IP 分区 ip_id】")
    for c in fb.get("quickIp", []):
        print(f"  {c.get('id')}: {c.get('name')}")

def export_json(products: List[Product], path: str, category: Optional[str], 
                ip_id: Optional[str], sort_type: str):
    """导出 JSON"""
    data = {
        "meta": {
            "category": category,
            "ip": ip_id,
            "sort": sort_type,
            "total": len(products),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "products": [p.to_dict() for p in products]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def print_alerts(alert_result: Dict[str, Any], abs_th: float, pct_th: float):
    """打印价格异动提醒"""
    alerts = alert_result["alerts"]
    
    print("\n" + "=" * 60)
    print(f"【价格异动提醒】")
    print(f"  本次抓取: {alert_result['current_time']}")
    print(f"  对比基准: 前 {len(alert_result['prev_times'])} 次抓取的最高价")
    print(f"  触发条件: 降价 > {abs_th:.0f} 元 或 > {pct_th * 100:.0f}%")
    
    if not alerts:
        print("  ✓ 未检测到符合阈值的价格异动")
        return
    
    print(f"  ⚠️ 发现 {len(alerts)} 个降价异动商品：")
    for a in alerts[:30]:
        print(f"    🔻 {a['title'][:40]}")
        print(f"       高位 ¥{a['high_price']:.2f} → 现 ¥{a['current_price']:.2f}  "
              f"(降 {a['drop_abs']:.2f}元 / {a['drop_pct'] * 100:.1f}%)")
    if len(alerts) > 30:
        print(f"    ... 其余 {len(alerts) - 30} 个见 --alert-csv 导出文件")

def export_alerts_csv(alerts: List[Dict], path: str):
    """导出异动到 CSV"""
    cols = ["cluster_id", "title", "high_price", "current_price", 
            "drop_abs", "drop_pct", "url"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for a in alerts:
            writer.writerow({
                "cluster_id": a["cluster_id"],
                "title": a["title"],
                "high_price": f"{a['high_price']:.2f}",
                "current_price": f"{a['current_price']:.2f}",
                "drop_abs": f"{a['drop_abs']:.2f}",
                "drop_pct": f"{a['drop_pct'] * 100:.2f}",
                "url": a["url"],
            })

if __name__ == "__main__":
    main()
