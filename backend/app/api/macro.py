"""
宏观风险日历 API
多数据源采集 → 新闻聚类（相似新闻合并为同一事件） → LLM 并行过滤 → 时间分析
"""
from __future__ import annotations

import re
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Query

from ..core import read_cache, write_cache
from ..core.config import CACHE_DIR
from ..core.data import news as data_news
from ..core.data import guba as data_guba
from ..core.cache.news_cluster import NewsClusterEngine
from ..core.cache.similarity import normalize_title as _normalize_title
from ..core.cache.similarity import calculate_similarity
from ..agents import run_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["宏观风险"])

# 聚类引擎单例
_cluster_engine = NewsClusterEngine()

# ══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(raw) -> str:
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")
    if isinstance(raw, int):
        ts = raw
        if ts > 1e12: ts //= 1000
        try: return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except: return datetime.now().strftime("%Y-%m-%d")
    raw_str = str(raw).strip()
    if raw_str.isdigit():
        try:
            ts = int(raw_str)
            if ts > 1e12: ts //= 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except: pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try: return datetime.strptime(raw_str[:len(fmt)], fmt).strftime("%Y-%m-%d")
        except: pass
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", raw_str)
    if m: return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return datetime.now().strftime("%Y-%m-%d")

def _parse_llm_json(text: str) -> list | dict:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    try: return json.loads(text)
    except:
        m = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
    return None

def _gen_event_key(title: str, date: str) -> str:
    content = f"{title}_{date}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

# ══════════════════════════════════════════════════════════════════════════════
# 数据采集（统一委托给 data.news）
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_all_sources(days: int = 30) -> tuple[list[dict], list[dict]]:
    return data_news.fetch_all_news(days=days)

# ══════════════════════════════════════════════════════════════════════════════
# 新闻聚类
# ══════════════════════════════════════════════════════════════════════════════

def _cluster_news(official: list[dict], social: list[dict]) -> list[dict]:
    """
    将原始新闻摄入聚类引擎，返回去重后的独立事件列表。
    """
    all_items = official + social
    if not all_items:
        return []

    engine = NewsClusterEngine(auto_save=False)
    for item in all_items:
        engine.ingest(
            title=item.get("title", ""),
            summary=item.get("summary", ""),
            url=item.get("url", ""),
            source=item.get("source", "unknown"),
            date=item.get("date", datetime.now().strftime("%Y-%m-%d")),
        )
    engine.save()  # 批量写入一次

    return engine.to_llm_items()

# ══════════════════════════════════════════════════════════════════════════════
# LLM 处理（并行）
# ══════════════════════════════════════════════════════════════════════════════

def _run_llm_batch(agent_name: str, batch: list[dict],
                   format_fn, parse_fn) -> list[dict]:
    """单批 LLM 调用"""
    batch_text = format_fn(batch)
    try:
        result = run_agent(agent_name, batch_text)
        if result and isinstance(result, list):
            return parse_fn(result, batch)
    except Exception as e:
        logger.error("%s 批次失败: %s", agent_name, e)
    return []


def _format_filter_batch(batch: list[dict]) -> dict:
    """格式化过滤 Agent 的输入"""
    lines = []
    for item in batch:
        lines.append(
            f"[{item['date']}] [{item['source']}] {item['title']}\n"
            f"摘要: {item.get('summary', '')[:100]}\n"
            f"链接: {item.get('url', '')}"
        )
    return {"news_data": "\n\n".join(lines)}


def _parse_filter_result(results: list[dict], batch: list[dict]) -> list[dict]:
    """解析过滤 Agent 的输出"""
    kept = []
    for item in results:
        if item.get("keep", False):
            kept.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "date": item.get("date", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "category": item.get("category", "其他"),
                "risk_level": item.get("risk_level", "中"),
            })
    return kept


def _filter_risk_events(clusters: list[dict]) -> list[dict]:
    """并行过滤风险事件"""
    if not clusters:
        return []

    batch_size = 20
    batches = [clusters[i:i+batch_size] for i in range(0, len(clusters), batch_size)]
    all_filtered: list[dict] = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                _run_llm_batch, "filter_risk_events", batch,
                _format_filter_batch, _parse_filter_result
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            result = future.result()
            all_filtered.extend(result)

    return all_filtered


def _format_time_batch(batch: list[dict]) -> dict:
    """格式化时间分析 Agent 的输入"""
    current_date = datetime.now().strftime("%Y-%m-%d")
    lines = []
    for item in batch:
        lines.append(
            f"- 报道日期: {item['date']}\n"
            f"  标题: {item['title']}\n"
            f"  摘要: {item.get('summary', '')[:100]}\n"
            f"  分类: {item.get('category', '其他')}"
        )
    return {"current_date": current_date, "events_data": "\n".join(lines)}


def _parse_time_result(results: list[dict], batch: list[dict]) -> list[dict]:
    """解析时间分析 Agent 的输出"""
    analyzed = []
    for j, item in enumerate(results):
        if j < len(batch):
            batch[j]["first_occurrence"] = item.get("first_occurrence", batch[j]["date"])
            batch[j]["duration"] = item.get("duration", "中期影响")
            batch[j]["duration_days"] = item.get("duration_days", 30)
            batch[j]["time_status"] = item.get("time_status", "进行中")
            batch[j]["time_reasoning"] = item.get("reasoning", "")
            analyzed.append(batch[j])
    # 补全未返回的
    for j in range(len(results), len(batch)):
        batch[j]["first_occurrence"] = batch[j]["date"]
        batch[j]["duration"] = "中期影响"
        batch[j]["duration_days"] = 30
        batch[j]["time_status"] = "进行中"
        batch[j]["time_reasoning"] = "默认设置"
        analyzed.append(batch[j])
    return analyzed


def _analyze_event_times(events: list[dict]) -> list[dict]:
    """并行分析事件时间特征"""
    if not events:
        return []

    batch_size = 10
    batches = [events[i:i+batch_size] for i in range(0, len(events), batch_size)]
    all_analyzed: list[dict] = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                _run_llm_batch, "analyze_event_timing", batch,
                _format_time_batch, _parse_time_result
            ): batch
            for batch in batches
        }
        for future in as_completed(futures):
            result = future.result()
            all_analyzed.extend(result)

    return all_analyzed

# ══════════════════════════════════════════════════════════════════════════════
# 语义去重（轻量字符级，已由聚类引擎处理，此步为二次保护）
# ══════════════════════════════════════════════════════════════════════════════

def _merge_sources(sources: list[str]) -> list[str]:
    seen = set()
    result = []
    for s in sources:
        if s not in seen: seen.add(s); result.append(s)
    return result

def _semantic_dedup(events: list[dict], threshold: float = 0.6) -> list[dict]:
    if not events: return []
    result = []
    for ev in events:
        merged = False
        ev_sources = ev.get("sources", [ev.get("source", "未知")])
        for existing in result:
            if calculate_similarity(ev.get("title", ""), existing.get("title", "")) >= threshold:
                existing_sources = existing.get("sources", [])
                existing["sources"] = _merge_sources(existing_sources + ev_sources)
                if ev.get("url"): existing["url"] = ev.get("url")
                merged = True
                break
        if not merged:
            ev["sources"] = ev.get("sources", [ev.get("source", "未知")])
            result.append(ev)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# 缓存管理
# ══════════════════════════════════════════════════════════════════════════════

def _load_persistent_events() -> dict:
    try:
        data = read_cache("macro_risk_timeline_persistent", module="macro")
        return data or {"events": [], "last_updated": ""}
    except: return {"events": [], "last_updated": ""}

def _save_persistent_events(data: dict) -> None:
    try:
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_cache("macro_risk_timeline_persistent", data, module="macro")
    except Exception as e:
        logger.error(f"保存缓存失败: {e}")

def _merge_events(existing: list[dict], new: list[dict]) -> list[dict]:
    seen_titles = set()
    deduped_existing = []
    for ev in existing:
        title = ev.get("title", "").strip()
        if title not in seen_titles:
            seen_titles.add(title)
            deduped_existing.append(ev)
    merged = list(deduped_existing)
    for ev in new:
        title = ev.get("title", "").strip()
        if title not in seen_titles:
            seen_titles.add(title)
            merged.append(ev)
    merged = _semantic_dedup(merged, threshold=0.6)
    merged.sort(key=lambda x: x.get("first_occurrence", ""), reverse=True)
    return merged

def _classify_timeline_events(events: list[dict]) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    past, current, future = [], [], []
    for ev in events:
        fo = ev.get("first_occurrence", "")
        status = ev.get("time_status", "进行中")
        duration_days = ev.get("duration_days", 30)
        try:
            start = datetime.strptime(fo, "%Y-%m-%d") if fo else datetime.now()
            end_date = start + timedelta(days=duration_days)
            ev["estimated_end"] = end_date.strftime("%Y-%m-%d")
        except:
            ev["estimated_end"] = ""
        try:
            end_dt = datetime.strptime(ev.get("estimated_end", "2099-12-31"), "%Y-%m-%d")
            is_ended = end_dt < datetime.now()
        except: is_ended = False
        if status == "预期发生" and fo > today:
            future.append(ev)
        elif status == "进行中" or not is_ended:
            current.append(ev)
        else:
            past.append(ev)
    def calc_risk_stats(evts):
        return {
            "total": len(evts),
            "high": sum(1 for e in evts if e.get("risk_level") == "高"),
            "medium": sum(1 for e in evts if e.get("risk_level") == "中"),
            "low": sum(1 for e in evts if e.get("risk_level") == "低"),
        }
    return {
        "past": {"events": past, "stats": calc_risk_stats(past)},
        "current": {"events": current, "stats": calc_risk_stats(current)},
        "future": {"events": future, "stats": calc_risk_stats(future)},
        "by_risk_level": {
            "high": [e for e in events if e.get("risk_level") == "高"],
            "medium": [e for e in events if e.get("risk_level") == "中"],
            "low": [e for e in events if e.get("risk_level") == "低"],
        },
    }

# ══════════════════════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/macro/risk-timeline")
def get_macro_risk_timeline(
    refresh: bool = Query(False, description="是否强制刷新"),
    background: bool = Query(False, description="后台静默更新"),
    days: int = Query(30, description="采集最近N天数据"),
):
    CACHE_KEY = f"macro_risk_timeline_{days}d"
    if not refresh:
        cached = read_cache(CACHE_KEY, module="macro")
        if cached:
            cached["from_cache"] = True
            cached["cache_status"] = "warm"
            return cached
        return {
            "timeline": {"past": {"events": [], "stats": {}}, "current": {"events": [], "stats": {}}, "future": {"events": [], "stats": {}}},
            "stats": {"total": 0, "raw_count": 0},
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
            "cache_status": "no_cache",
            "message": "暂无缓存数据，请点击刷新获取最新数据"
        }
    if background:
        cached = read_cache(CACHE_KEY, module="macro")
        if cached: cached["from_cache"] = True; cached["cache_status"] = "background_updating"
        import threading
        def background_update():
            try:
                existing = _load_persistent_events().get("events", [])
                official, social = _fetch_all_sources(days=days)
                clusters = _cluster_news(official, social)
                filtered = _filter_risk_events(clusters)
                analyzed = _analyze_event_times(filtered)
                merged = _merge_events(existing, analyzed)
                _save_persistent_events({"events": merged})
                timeline = _classify_timeline_events(merged)
                all_stats = {"total": len(merged), "raw_count": len(official) + len(social)}
                data = {"timeline": timeline, "stats": all_stats, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                write_cache(CACHE_KEY, data, module="macro")
            except Exception as e:
                logger.error(f"后台更新失败: {e}")
        thread = threading.Thread(target=background_update, daemon=True)
        thread.start()
        if cached: return cached
        return {"from_cache": False, "cache_status": "background_started"}
    try:
        existing = _load_persistent_events().get("events", [])
        existing_fingerprints = set()
        for ev in existing:
            title_words = "".join(filter(str.isalnum, ev.get("title", "")[:20])).lower()
            date = ev.get("date", "")[:10]
            existing_fingerprints.add(f"{title_words}_{date}")
        official, social = _fetch_all_sources(days=days)
        if not official and not social:
            return {
                "timeline": {"past": {"events": [], "stats": {}}, "current": {"events": [], "stats": {}}, "future": {"events": [], "stats": {}}},
                "stats": {"total": 0, "raw_count": 0},
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_cache": False
            }
        clusters = _cluster_news(official, social)
        logger.info("聚类后: 原始%s+%s条 → %s个独立事件", len(official), len(social), len(clusters))
        filtered = _filter_risk_events(clusters)
        analyzed = _analyze_event_times(filtered)
        merged = _merge_events(existing, analyzed)
        _save_persistent_events({"events": merged})
        timeline = _classify_timeline_events(merged)
        all_stats = {"total": len(merged), "raw_count": len(official) + len(social)}
        data = {"timeline": timeline, "stats": all_stats, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        write_cache(CACHE_KEY, data, module="macro")
        data["from_cache"] = False
        data["cache_status"] = "fresh"
        return data
    except Exception as e:
        logger.error(f"宏观风险时间轴生成失败: {e}")
        return {
            "timeline": {"past": {"events": [], "stats": {}}, "current": {"events": [], "stats": {}}, "future": {"events": [], "stats": {}}},
            "stats": {"total": 0, "raw_count": 0},
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False, "error": str(e),
        }
