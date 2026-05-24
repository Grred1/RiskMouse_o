"""
东方财富股吧数据接口统一封装层

集中管理所有股吧爬虫逻辑，消除 sentiment.py / mouse_agent.py / macro.py 之间的重复代码。
"""
from __future__ import annotations

import re
import time
import logging
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://guba.eastmoney.com/",
}


def scrape_stock_posts(symbol: str, max_pages: int = 3,
                       max_posts: int = 60) -> list[dict]:
    """
    爬取个股的股吧帖子列表。

    参数：
        symbol:      股票代码（纯数字，如 '002081'）
        max_pages:   爬取页数（默认 3）
        max_posts:   返回上限条数（默认 60）
    返回：
        [{title, url}, ...]
    """
    all_posts = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        try:
            url = f"https://guba.eastmoney.com/list,{symbol}_{page}.html"
            r = requests.get(url, headers=_HEADERS, timeout=10)
            if r.status_code != 200:
                break
            r.encoding = 'utf-8'
            titles = re.findall(r'"post_title"\s*:\s*"([^"]+)"', r.text)
            ids = re.findall(r'"post_id"\s*:\s*(\d+)', r.text)
            for t, pid in zip(titles, ids):
                t = t.strip()
                if len(t) > 4 and pid not in seen_ids \
                   and not any(kw in t for kw in ["反诈", "网警", "举报"]):
                    seen_ids.add(pid)
                    all_posts.append({
                        "title": t,
                        "url": f"https://guba.eastmoney.com/news,{symbol},{pid}.html",
                    })
        except Exception as e:
            logger.warning("scrape_stock_posts(%s) 第 %d 页失败: %s", symbol, page, e)
            break
    return all_posts[:max_posts]


def fetch_market_posts(days: int = 30) -> list[dict]:
    """
    获取全市场热门股吧帖子（大盘首页）。

    参数：
        days: 只返回最近 N 天的帖子
    返回：
        [{title, url, date, source: "guba"}, ...]
    """
    all_posts = []
    seen = set()
    cutoff = datetime.now() - timedelta(days=days)

    for page in range(1, 6):
        try:
            url = f"https://guba.eastmoney.com/list,zssh000001_{page}.html"
            r = requests.get(url, headers=_HEADERS, timeout=10)
            if r.status_code != 200:
                break
            r.encoding = 'utf-8'
            titles = re.findall(r'"post_title"\s*:\s*"([^"]+)"', r.text)
            post_ids = re.findall(r'"post_id"\s*:\s*"?(\d+)"?', r.text)
            pub_times = re.findall(r'"post_publish_time"\s*:\s*"([^"]+)"', r.text)

            for i, t in enumerate(titles):
                t = t.strip()
                if len(t) < 5 or t in seen:
                    continue
                if any(kw in t for kw in ["反诈", "网警", "举报", "广告"]):
                    continue
                pid = post_ids[i] if i < len(post_ids) else ""
                pt = pub_times[i] if i < len(pub_times) else ""
                date_str = _parse_date(pt)
                try:
                    if datetime.strptime(date_str, "%Y-%m-%d") < cutoff:
                        continue
                except Exception:
                    pass
                seen.add(t)
                all_posts.append({
                    "title": t,
                    "url": f"https://guba.eastmoney.com/news,zssh000001,{pid}.html" if pid else "",
                    "date": date_str,
                    "source": "guba",
                })
            time.sleep(0.5)
        except Exception as e:
            logger.warning("fetch_market_posts 第 %d 页失败: %s", page, e)
            break
    return all_posts


def fetch_stock_logic(pure_code: str, symbol: str) -> str:
    """
    获取股吧多维度数据，组装成市场上涨逻辑文本（供 sentiment.py 使用）。
    包含：热门关键词、帖子标题、人气排名。

    参数：
        pure_code: 纯数字代码
        symbol:    带前缀代码（如 SZ002081）
    返回：
        格式化的文本字符串
    """
    from .akshare import get_hot_keywords, get_hot_rank_latest

    parts = []

    # 1. 热门关键词
    try:
        df_kw = get_hot_keywords(symbol=symbol)
        if df_kw is not None and not df_kw.empty:
            kws = []
            for _, row in df_kw.iterrows():
                kws.append(f"{row.get('概念名称','')}(热度{row.get('热度',0)})")
            if kws:
                parts.append("股吧热门概念: " + ", ".join(kws[:8]))
    except Exception:
        pass

    # 2. 爬取股吧帖子标题
    try:
        titles = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://guba.eastmoney.com/",
        }
        for page in range(1, 3):
            url = f"https://guba.eastmoney.com/list,{pure_code}_{page}.html"
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200:
                break
            r.encoding = 'utf-8'
            found = re.findall(r'"post_title"\s*:\s*"([^"]+)"', r.text)
            for t in found:
                t = t.strip()
                if len(t) > 4:
                    titles.append(t)
            if len(titles) >= 20:
                break
        if titles:
            parts.append("股吧热帖标题: " + " | ".join(titles[:15]))
    except Exception:
        pass

    # 3. 人气排名
    try:
        df_latest = get_hot_rank_latest(symbol=symbol)
        if df_latest is not None and not df_latest.empty:
            rank_data = {}
            for _, row in df_latest.iterrows():
                val = row["value"]
                if isinstance(val, float) and (val != val or abs(val) == float('inf')):
                    continue
                rank_data[str(row["item"])] = str(val)
            if rank_data:
                parts.append(
                    f"人气排名第{rank_data.get('rank','?')}名"
                    f"（共{rank_data.get('marketAllCount','?')}只股票）"
                )
    except Exception:
        pass

    return "\n".join(parts) if parts else "暂未获取到股吧数据"


def _parse_date(raw) -> str:
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
