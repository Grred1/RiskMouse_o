"""
新闻数据接口统一封装层

集中管理所有新闻源爬虫（财新 / 财联社 / 新华社），
取代 macro.py 中散落的 _fetch_*_news 私有函数。
"""
from __future__ import annotations

import re
import time
import logging
from datetime import datetime, timedelta

import requests

from . import guba as data_guba

logger = logging.getLogger(__name__)


# ── 日期解析工具 ────────────────────────────────────────────────

def parse_date(raw) -> str:
    """通用日期字符串解析 → YYYY-MM-DD"""
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")
    if isinstance(raw, int):
        ts = raw
        if ts > 1e12:
            ts //= 1000
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")
    raw_str = str(raw).strip()
    if raw_str.isdigit():
        try:
            ts = int(raw_str)
            if ts > 1e12:
                ts //= 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw_str[:len(fmt)], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", raw_str)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return datetime.now().strftime("%Y-%m-%d")


# ── 财新 ────────────────────────────────────────────────────────

def fetch_caixin_news(pages: int = 3) -> list[dict]:
    """获取财新网最新财经新闻"""
    all_news = []
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "referer": "https://cxdata.caixin.com/index/newsTab?tab=latest",
    }
    for page in range(1, pages + 1):
        try:
            url = "https://cxdata.caixin.com/api/dataplus/sjtPc/news"
            params = {"pageNum": str(page), "pageSize": "100", "showLabels": "true"}
            r = requests.get(url, params=params, headers=headers, timeout=12)
            if r.status_code != 200:
                break
            items = r.json().get("data", {}).get("data", [])
            if not items:
                break
            for item in items:
                raw_time = item.get("time") or item.get("publishTime") or item.get("createTime") or ""
                title = item.get("title") or ""
                if not title or len(title) < 5:
                    continue
                all_news.append({
                    "title": title.strip(),
                    "summary": str(item.get("summary", "") or "").strip(),
                    "url": str(item.get("url", "") or "").strip(),
                    "date": parse_date(raw_time),
                    "source": "caixin",
                })
            time.sleep(0.3)
        except Exception as e:
            logger.warning("fetch_caixin_news 第 %d 页失败: %s", page, e)
            break
    return all_news


# ── 财联社 ──────────────────────────────────────────────────────

def fetch_cls_news(days: int = 30) -> list[dict]:
    """获取财联社电报（最新API）"""
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cls.cn/"}
    all_news = []
    cutoff = datetime.now() - timedelta(days=days)
    try:
        url = "https://www.cls.cn/nodeapi/telegraphList"
        params = {
            "app": "CailianpressWeb", "os": "web",
            "refresh_type": 1, "order": 1,
            "rn": 50, "sv": "8.4.6",
            "sign": "8bc6630fbf8b4a195cd99b4da66ed07b",
        }
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            items = r.json().get("data", {}).get("roll_data", [])
            for item in items:
                title = item.get("title", "").strip()
                if not title or len(title) < 5:
                    continue
                date_str = parse_date(item.get("ctime", ""))
                try:
                    if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                        continue
                except Exception:
                    pass
                all_news.append({
                    "title": title,
                    "summary": item.get("brief", item.get("content", ""))[:200],
                    "url": item.get("shareurl", item.get("share_url", "")),
                    "date": date_str,
                    "source": "cls",
                })
    except Exception as e:
        logger.warning("fetch_cls_news 失败: %s", e)
    return all_news


# ── 新华社 ──────────────────────────────────────────────────────

def fetch_xinhua_news(days: int = 30) -> list[dict]:
    """获取新华社财经 RSS"""
    headers = {"User-Agent": "Mozilla/5.0"}
    all_news = []
    cutoff = datetime.now() - timedelta(days=days)
    urls = [
        "https://www.news.cn/fortune/rss.xml",
        "http://www.xinhuanet.com/english/rss/businessrss.xml",
    ]
    fetched = False
    for url in urls:
        if fetched:
            break
        try:
            import xml.etree.ElementTree as ET
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            for item in root.iter('item'):
                title = item.findtext('title', '').strip()
                if not title or len(title) < 5:
                    continue
                date_str = parse_date(item.findtext('pubDate', ''))
                try:
                    if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                        continue
                except Exception:
                    pass
                all_news.append({
                    "title": title,
                    "summary": item.findtext('description', '')[:200],
                    "url": item.findtext('link', ''),
                    "date": date_str,
                    "source": "xinhua",
                })
            fetched = True
        except Exception as e:
            logger.warning("fetch_xinhua_news(%s) 失败: %s", url, e)
    return all_news


# ── 聚合 ──────────────────────────────────────────────────────────

def fetch_all_news(days: int = 30) -> tuple[list[dict], list[dict]]:
    """
    聚合所有新闻源 + 股吧帖子。

    返回：
        (official_news, social_posts)
        official: caixin + cls + xinhua
        social:   guba market posts
    """
    official = []
    official.extend(fetch_caixin_news(pages=3))
    official.extend(fetch_cls_news(days=days))
    official.extend(fetch_xinhua_news(days=days))
    social = data_guba.fetch_market_posts(days=days)
    return official, social
