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
import threading
import calendar as calendar_lib
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

# ── 刷新进度追踪 ──────────────────────────────────────────────

_update_progress: dict[str, dict] = {}
_update_locks: dict[str, threading.Lock] = {}
_update_locks_lock = threading.Lock()

_PROGRESS_MAP = {
    "idle":         ("等待中", 0),
    "fetching":     ("正在采集新闻数据...", 5),
    "clustering":   ("正在聚类相似新闻...", 20),
    "llm_filtering":("AI 正在过滤风险事件...", 30),
    "llm_timing":   ("AI 正在分析时间特征...", 60),
    "merging":      ("正在合并历史事件...", 85),
    "caching":      ("正在写入缓存...", 95),
    "done":         ("更新完成", 100),
}

def _set_progress(cache_key: str, stage: str, detail: str = ""):
    """更新刷新进度"""
    label, percent = _PROGRESS_MAP.get(stage, ("", 0))
    _update_progress[cache_key] = {
        "stage": stage,
        "detail": detail or label,
        "percent": percent,
        "updated_at": datetime.now().strftime("%H:%M:%S"),
    }

def _clear_progress(cache_key: str):
    _update_progress.pop(cache_key, None)



# ══════════════════════════════════════════════════════════════════════════════
# 数据采集（统一委托给 data.news）
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_all_sources(days: int = 30) -> tuple[list[dict], list[dict]]:
    return data_news.fetch_all_news(days=days)


# ══════════════════════════════════════════════════════════════════════════════
# 结构化经济日历（未来风险先验）
# ══════════════════════════════════════════════════════════════════════════════

def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> datetime:
    """返回某月第 occurrence 个 weekday（周一为 0）。"""
    first_weekday = datetime(year, month, 1).weekday()
    day = 1 + ((weekday - first_weekday) % 7) + (occurrence - 1) * 7
    return datetime(year, month, day)


def _upcoming_macro_calendar(now: datetime | None = None, horizon_days: int = 120) -> list[dict]:
    """生成未来重要经济数据发布窗口。

    这是一个无 Key 的结构化补充源：用于给新闻风险监控提供“未来事件”先验。
    规则类日期可能受节假日调整，因此在 UI 中明确标记为发布窗口，正式投资决策仍
    应以对应机构的官方日历为准。
    """
    now = now or datetime.now()
    end = now + timedelta(days=horizon_days)
    events: list[dict] = []

    def add_event(date: datetime, title: str, summary: str, risk_level: str, source: str, url: str, category: str = "宏观数据"):
        if now.date() < date.date() <= end.date():
            events.append({
                "title": title,
                "summary": summary,
                "date": date.strftime("%Y-%m-%d"),
                "first_occurrence": date.strftime("%Y-%m-%d"),
                "duration": "数据发布窗口",
                "duration_days": 1,
                "time_status": "预期发生",
                "time_reasoning": "结构化经济日历规则生成，最终日期以官方日历为准",
                "risk_level": risk_level,
                "category": category,
                "source": source,
                "url": url,
                "is_calendar_event": True,
            })

    # 覆盖当前月和后四个月，避免跨年时遗漏。
    for offset in range(5):
        month_index = now.month - 1 + offset
        year = now.year + month_index // 12
        month = month_index % 12 + 1
        last_day = calendar_lib.monthrange(year, month)[1]

        # 中国 LPR 通常在每月 20 日报价；非工作日可能顺延。
        add_event(
            datetime(year, month, min(20, last_day)), "中国 LPR 报价窗口",
            "关注贷款市场报价利率调整对银行、地产与市场流动性的影响。",
            "中", "中国人民银行（规则日历）", "https://www.pbc.gov.cn/",
            "货币政策",
        )
        # PMI 通常在月末发布，节假日附近可能调整。
        add_event(
            datetime(year, month, last_day), "中国 PMI 数据发布窗口",
            "关注制造业与非制造业景气变化及其对周期行业的影响。",
            "中", "国家统计局（规则日历）", "https://www.stats.gov.cn/",
            "宏观数据",
        )
        # 美国非农通常在每月第一个周五发布；CPI 以第二个周三附近窗口展示。
        add_event(
            _nth_weekday(year, month, 4, 1), "美国非农就业数据发布窗口",
            "就业数据会影响美元、美债收益率及全球风险偏好。",
            "高", "美国劳工统计局（规则日历）", "https://www.bls.gov/schedule/news_release/empsit.htm",
            "海外宏观",
        )
        add_event(
            _nth_weekday(year, month, 2, 2), "美国 CPI 数据发布窗口",
            "通胀数据可能改变市场对美联储政策路径的预期。",
            "高", "美国劳工统计局（规则日历）", "https://www.bls.gov/schedule/news_release/cpi.htm",
            "海外宏观",
        )

    # FOMC 的日期为官方 2026 年会议安排，后续年份交由官方日历更新。
    fomc_dates = ("2026-09-15", "2026-10-27", "2026-12-08")
    for value in fomc_dates:
        meeting = datetime.strptime(value, "%Y-%m-%d")
        add_event(
            meeting, "美联储 FOMC 议息会议窗口",
            "利率决议与点阵图可能显著影响全球流动性、汇率及成长股估值。",
            "高", "美联储（官方日历）", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            "货币政策",
        )

    return events


def _attach_upcoming_calendar(data: dict) -> dict:
    """将经济日历叠加到新闻时间线；不写入新闻持久化缓存，避免重复积累。"""
    timeline = data.get("timeline", {})
    news_events = [
        *(timeline.get("past", {}).get("events", []) or []),
        *(timeline.get("current", {}).get("events", []) or []),
        *(timeline.get("future", {}).get("events", []) or []),
    ]
    calendar_events = _upcoming_macro_calendar()
    known = {(event.get("title"), event.get("first_occurrence") or event.get("date")) for event in news_events}
    merged = news_events + [
        event for event in calendar_events
        if (event.get("title"), event.get("first_occurrence") or event.get("date")) not in known
    ]
    data["timeline"] = _classify_timeline_events(merged)
    stats = data.setdefault("stats", {})
    stats["total"] = len(merged)
    stats["calendar_count"] = len(calendar_events)
    return data

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

def _start_background_update(cache_key: str, days: int) -> dict:
    """启动后台更新，同一 cache_key 同时只允许一个后台任务"""
    # 检查是否已有后台任务在运行
    with _update_locks_lock:
        if cache_key in _update_locks and _update_locks[cache_key].locked():
            logger.info("后台更新已在进行中，跳过重复请求: %s", cache_key)
            cached = read_cache(cache_key, module="macro")
            if cached:
                cached["from_cache"] = True
                cached["cache_status"] = "background_updating"
                return cached
            return {"from_cache": False, "cache_status": "background_started"}
        lock = _update_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _update_locks[cache_key] = lock
        lock.acquire()

    cached = read_cache(cache_key, module="macro")
    if cached:
        cached["from_cache"] = True
        cached["cache_status"] = "background_updating"

    _set_progress(cache_key, "fetching")

    def _background_update():
        try:
            existing = _load_persistent_events().get("events", [])
            _set_progress(cache_key, "fetching")
            official, social = _fetch_all_sources(days=days)
            _set_progress(cache_key, "clustering", f"已采集 {len(official)+len(social)} 条新闻")
            clusters = _cluster_news(official, social)
            _set_progress(cache_key, "llm_filtering", f"聚类完成，共 {len(clusters)} 个独立事件")
            filtered = _filter_risk_events(clusters)
            _set_progress(cache_key, "llm_timing", f"风险过滤完成，保留 {len(filtered)} 条事件")
            analyzed = _analyze_event_times(filtered)
            _set_progress(cache_key, "merging", f"时间分析完成，共 {len(analyzed)} 条事件")
            merged = _merge_events(existing, analyzed)
            _save_persistent_events({"events": merged})
            _set_progress(cache_key, "caching", f"合并完成，共 {len(merged)} 条事件")
            timeline = _classify_timeline_events(merged)
            all_stats = {"total": len(merged), "raw_count": len(official) + len(social)}
            data = {"timeline": timeline, "stats": all_stats, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            write_cache(cache_key, data, module="macro")
            _set_progress(cache_key, "done", f"更新完成，共 {len(merged)} 条事件")
        except Exception as e:
            logger.error(f"宏观日历后台更新失败: {e}")
            _set_progress(cache_key, "done", f"更新失败: {e}")
            try:
                fallback = _load_persistent_events().get("events", [])
                if fallback:
                    timeline = _classify_timeline_events(fallback)
                    all_stats = {"total": len(fallback), "raw_count": 0}
                    data = {"timeline": timeline, "stats": all_stats, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    write_cache(cache_key, data, module="macro")
            except Exception:
                pass
        finally:
            with _update_locks_lock:
                if cache_key in _update_locks:
                    _update_locks[cache_key].release()

    thread = threading.Thread(target=_background_update, daemon=True)
    thread.start()

    if cached:
        return cached
    return {"from_cache": False, "cache_status": "background_started"}

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
            return _attach_upcoming_calendar(cached)
        # 无缓存 → 自动触发后台采集，前端走 background_started 分支显示 loading
        return _attach_upcoming_calendar(_start_background_update(CACHE_KEY, days))
    if background:
        return _attach_upcoming_calendar(_start_background_update(CACHE_KEY, days))
    try:
        existing = _load_persistent_events().get("events", [])
        existing_fingerprints = set()
        for ev in existing:
            title_words = "".join(filter(str.isalnum, ev.get("title", "")[:20])).lower()
            date = ev.get("date", "")[:10]
            existing_fingerprints.add(f"{title_words}_{date}")
        official, social = _fetch_all_sources(days=days)
        if not official and not social:
            return _attach_upcoming_calendar({
                "timeline": {"past": {"events": [], "stats": {}}, "current": {"events": [], "stats": {}}, "future": {"events": [], "stats": {}}},
                "stats": {"total": 0, "raw_count": 0},
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_cache": False
            })
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
        return _attach_upcoming_calendar(data)
    except Exception as e:
        logger.error(f"宏观风险时间轴生成失败: {e}")
        return _attach_upcoming_calendar({
            "timeline": {"past": {"events": [], "stats": {}}, "current": {"events": [], "stats": {}}, "future": {"events": [], "stats": {}}},
            "stats": {"total": 0, "raw_count": 0},
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False, "error": str(e),
        })


@router.get("/macro/refresh-progress")
def get_refresh_progress(days: int = Query(30, description="天数，与 risk-timeline 对齐")):
    """查询宏观日历刷新进度"""
    CACHE_KEY = f"macro_risk_timeline_{days}d"
    progress = _update_progress.get(CACHE_KEY)
    if not progress:
        return {"stage": "idle", "detail": "暂无刷新任务", "percent": 0}
    return progress
