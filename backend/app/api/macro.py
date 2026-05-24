"""
宏观风险日历 API
多数据源采集 + LLM 智能过滤 + 时间分析 + 语义去重 + 增量缓存
"""
from __future__ import annotations

import re
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, Query

from ..core import call_llm, read_cache, write_cache
from ..core.config import CACHE_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["宏观风险"])

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
# 数据采集
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_caixin_news(pages: int = 3) -> list[dict]:
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
            if r.status_code != 200: break
            items = r.json().get("data", {}).get("data", [])
            if not items: break
            for item in items:
                raw_time = item.get("time") or item.get("publishTime") or item.get("createTime") or ""
                title = item.get("title") or ""
                if not title or len(title) < 5: continue
                all_news.append({
                    "title": title.strip(),
                    "summary": str(item.get("summary", "") or "").strip(),
                    "url": str(item.get("url", "") or "").strip(),
                    "date": _parse_date(raw_time),
                    "source": "caixin",
                })
            time.sleep(0.3)
        except: break
    return all_news

def _fetch_guba_posts(days: int = 30) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://guba.eastmoney.com/",
    }
    all_posts = []
    seen = set()
    cutoff = datetime.now() - timedelta(days=days)
    for page in range(1, 6):
        try:
            url = f"https://guba.eastmoney.com/list,zssh000001_{page}.html"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200: break
            titles = re.findall(r'"post_title"\s*:\s*"([^"]+)"', r.text)
            post_ids = re.findall(r'"post_id"\s*:\s*"?(\d+)"?', r.text)
            pub_times = re.findall(r'"post_publish_time"\s*:\s*"([^"]+)"', r.text)
            for i, t in enumerate(titles):
                t = t.strip()
                if len(t) < 5 or t in seen: continue
                if any(kw in t for kw in ["反诈", "网警", "举报", "广告"]): continue
                pid = post_ids[i] if i < len(post_ids) else ""
                pt = pub_times[i] if i < len(pub_times) else ""
                date_str = _parse_date(pt)
                try:
                    if datetime.strptime(date_str, "%Y-%m-%d") < cutoff: continue
                except: pass
                seen.add(t)
                all_posts.append({
                    "title": t, "url": f"https://guba.eastmoney.com/news,zssh000001,{pid}.html" if pid else "",
                    "date": date_str, "source": "guba",
                })
            time.sleep(0.5)
        except: break
    return all_posts

def _fetch_cls_news(days: int = 30) -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cls.cn/"}
    all_news = []
    cutoff = datetime.now() - timedelta(days=days)
    try:
        url = "https://www.cls.cn/api/sw?app=CLS&sv=7.7.5"
        for page in range(1, 4):
            params = {"page": page, "size": 20}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code != 200: break
            items = r.json().get("data", {}).get("roll_data", [])
            if not items: break
            for item in items:
                title = item.get("title", "").strip()
                if not title or len(title) < 5: continue
                date_str = _parse_date(item.get("ctime", ""))
                try:
                    if datetime.strptime(date_str, "%Y-%m-%d") < cutoff: continue
                except: pass
                all_news.append({
                    "title": title, "summary": item.get("summary", "")[:200],
                    "url": item.get("share_url", ""), "date": date_str, "source": "cls",
                })
            time.sleep(0.3)
    except: pass
    return all_news

def _fetch_xinhua_news(days: int = 30) -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    all_news = []
    cutoff = datetime.now() - timedelta(days=days)
    try:
        import xml.etree.ElementTree as ET
        url = "http://www.xinhuanet.com/fortune/rss.xml"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            try:
                root = ET.fromstring(r.text)
                for item in root.iter('item'):
                    title = item.findtext('title', '').strip()
                    if not title or len(title) < 5: continue
                    date_str = _parse_date(item.findtext('pubDate', ''))
                    try:
                        if datetime.strptime(date_str, "%Y-%m-%d") < cutoff: continue
                    except: pass
                    all_news.append({
                        "title": title, "summary": item.findtext('description', '')[:200],
                        "url": item.findtext('link', ''), "date": date_str, "source": "xinhua",
                    })
            except: pass
    except: pass
    return all_news

def _fetch_all_sources(days: int = 30) -> tuple[list[dict], list[dict]]:
    official, social = [], []
    official.extend(_fetch_caixin_news(pages=3))
    official.extend(_fetch_cls_news(days=days))
    official.extend(_fetch_xinhua_news(days=days))
    social.extend(_fetch_guba_posts(days=days))
    return official, social

# ══════════════════════════════════════════════════════════════════════════════
# LLM 提示词
# ══════════════════════════════════════════════════════════════════════════════

RISK_FILTER_PROMPT = """
你是一位专业的宏观经济风险分析师。你的任务是严格筛选真正具有宏观风险影响的事件。

【宏观风险定义 - 必须满足以下至少一条】

✅ 保留的事件类型：
1. 地缘政治风险：战争、冲突、制裁、贸易战、领土争端、大国博弈
2. 货币政策变动：央行利率决策、量化宽松/紧缩、汇率政策重大调整
3. 金融系统性风险：银行危机、债务违约、市场崩盘、流动性危机
4. 重大政策转向：重要国家/机构的监管政策、财政政策重大变化
5. 经济数据重大偏离：GDP、通胀、就业等核心数据明显偏离预期
6. 大宗商品剧烈波动：石油、黄金、粮食等战略物资价格剧烈波动
7. 国际组织重大决策：IMF、世界银行、OPEC等重要组织声明

❌ 必须过滤掉的事件：
1. 日常市场波动：正常涨跌幅、个股分析、技术性调整
2. 短期情绪反应：当日市场反应、盘中波动、无实质影响的消息
3. 纯个人观点：股评、预测、缺乏数据支撑的分析
4. 行业内部新闻：不涉及宏观层面的企业/行业动态
5. 已完结事件：影响已经结束、不会持续或复发的短期事件
6. 营销/推广内容：广告、荐股、推广信息
7. 未经证实的传言：无法核实来源的信息

【输入数据】
{news_data}

【输出要求】
严格按以下JSON格式输出（只输出JSON，不要任何其他内容）：
[
  {{
    "keep": true或false,
    "reason": "保留或过滤的理由（20字以内）",
    "title": "事件标题（20字以内）",
    "summary": "事件摘要（60字以内）",
    "date": "YYYY-MM-DD",
    "url": "原始链接",
    "source": "来源名称",
    "category": "地缘政治|货币政策|金融风险|政策变化|经济数据|大宗商品|国际组织|其他",
    "risk_level": "高|中|低"
  }}
]
"""

RISK_TIME_ANALYSIS_PROMPT = """
你是一位专业的宏观风险分析师。请分析以下事件的时间特征。

【当前时间】
{current_date}

【待分析事件】
{events_data}

【分析要求】

对于每个事件，请分析并确定：

1. **最早发生时间（first_occurrence）**
   - 如果新闻报道的是"某事件已经发生一段时间"，取事件实际开始的时间
   - 如果新闻报道的是"某事件今日正式生效"，取该生效日期
   - 如果事件有明确的起始日期，取该日期
   - 格式：YYYY-MM-DD

2. **影响持续时间（duration）**
   根据事件性质判断影响持续时间：
   - "一次性冲击"：1-7天（如：市场单日暴跌、短期情绪波动）
   - "短期影响"：1-4周（如：政策公布后的短期市场反应）
   - "中期影响"：1-6个月（如：央行政策调整、区域冲突升级）
   - "长期影响"：6个月以上（如：贸易战升级、长期制裁、重大政策转变）
   - "持续性风险"：持续至今且无法预估结束时间

3. **时间状态（time_status）**
   - "已结束"：影响已经完全结束，不再持续
   - "进行中"：影响正在持续，对现在和未来都有影响
   - "预期发生"：事件尚未发生，预计在未来某个时间点发生

【输出格式 - 只输出JSON，不要任何其他内容】
[
  {{
    "original_date": "原始报道日期",
    "title": "事件标题",
    "first_occurrence": "YYYY-MM-DD（最早发生时间）",
    "duration": "一次性冲击|短期影响|中期影响|长期影响|持续性风险",
    "duration_days": 预估天数（整数）,
    "time_status": "已结束|进行中|预期发生",
    "reasoning": "分析理由（50字以内）"
  }}
]
"""

# ══════════════════════════════════════════════════════════════════════════════
# LLM 处理
# ══════════════════════════════════════════════════════════════════════════════

def _filter_risk_events(official: list[dict], social: list[dict]) -> list[dict]:
    all_items = official + social
    if not all_items: return []
    all_filtered = []
    batch_size = 10
    for i in range(0, len(all_items), batch_size):
        batch = all_items[i:i+batch_size]
        news_lines = []
        for item in batch:
            news_lines.append(
                f"[{item['date']}] [{item['source']}] {item['title']}\n"
                f"摘要: {item.get('summary', '')[:100]}\n"
                f"链接: {item.get('url', '')}"
            )
        news_text = "\n\n".join(news_lines)
        try:
            prompt = RISK_FILTER_PROMPT.format(news_data=news_text)
            response = call_llm(prompt, max_tokens=3000)
            result = _parse_llm_json(response)
            if result and isinstance(result, list):
                for item in result:
                    if item.get("keep", False):
                        all_filtered.append({
                            "title": item.get("title", ""),
                            "summary": item.get("summary", ""),
                            "date": item.get("date", ""),
                            "url": item.get("url", ""),
                            "source": item.get("source", ""),
                            "category": item.get("category", "其他"),
                            "risk_level": item.get("risk_level", "中"),
                        })
        except Exception as e:
            logger.error(f"LLM过滤失败: {e}")
        time.sleep(0.3)
    return all_filtered

def _analyze_event_times(events: list[dict], batch_size: int = 8) -> list[dict]:
    if not events: return []
    current_date = datetime.now().strftime("%Y-%m-%d")
    analyzed = []
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        events_lines = []
        for item in batch:
            events_lines.append(
                f"- 报道日期: {item['date']}\n"
                f"  标题: {item['title']}\n"
                f"  摘要: {item.get('summary', '')[:100]}\n"
                f"  分类: {item.get('category', '其他')}"
            )
        events_text = "\n".join(events_lines)
        try:
            prompt = RISK_TIME_ANALYSIS_PROMPT.format(current_date=current_date, events_data=events_text)
            response = call_llm(prompt, max_tokens=3000)
            result = _parse_llm_json(response)
            if result and isinstance(result, list):
                for j, item in enumerate(result):
                    if j < len(batch):
                        batch[j]["first_occurrence"] = item.get("first_occurrence", batch[j]["date"])
                        batch[j]["duration"] = item.get("duration", "中期影响")
                        batch[j]["duration_days"] = item.get("duration_days", 30)
                        batch[j]["time_status"] = item.get("time_status", "进行中")
                        batch[j]["time_reasoning"] = item.get("reasoning", "")
                        analyzed.append(batch[j])
        except Exception as e:
            logger.error(f"时间分析失败: {e}")
            for item in batch:
                item["first_occurrence"] = item["date"]
                item["duration"] = "中期影响"
                item["duration_days"] = 30
                item["time_status"] = "进行中"
                item["time_reasoning"] = "分析失败，默认设置"
                analyzed.append(item)
        time.sleep(0.3)
    return analyzed

# ══════════════════════════════════════════════════════════════════════════════
# 语义去重
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?', '', t)
    t = re.sub(r'\d{1,2}[-/月]\d{1,2}[日号]?', '', t)
    t = re.sub(r'\d{1,2}[点时]\d{0,2}分?', '', t)
    t = re.sub(r'\d+[\.,]?\d*%', '', t)
    t = re.sub(r'\d+[\.,]?\d*', '', t)
    for org in ['高盛', '摩根', '瑞银', '摩根士丹利', '美银', '中信', '国泰', '华尔街', '市场', '全球', '国际', '国内']:
        t = t.replace(org.lower(), '')
    t = re.sub(r'[^\w\u4e00-\u9fff]', '', t)
    return t.strip()

def _calculate_similarity(title1: str, title2: str) -> float:
    s1 = set(_normalize_title(title1))
    s2 = set(_normalize_title(title2))
    if not s1 or not s2: return 0.0
    return len(s1 & s2) / len(s1 | s2) if len(s1 | s2) > 0 else 0.0

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
            if _calculate_similarity(ev.get("title", ""), existing.get("title", "")) >= threshold:
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
                filtered = _filter_risk_events(official, social)
                analyzed = _analyze_event_times(filtered)
                merged = _merge_events(existing, analyzed)
                _save_persistent_events({"events": merged, "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
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
            return {"timeline": {"past": {"events": [], "stats": {}}, "current": {"events": [], "stats": {}}, "future": {"events": [], "stats": {}}}, "stats": {"total": 0, "raw_count": 0}, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "from_cache": False}
        new_social = []
        for ev in social:
            title_words = "".join(filter(str.isalnum, ev.get("title", "")[:20])).lower()
            date = ev.get("date", "")[:10]
            fp = f"{title_words}_{date}"
            if fp not in existing_fingerprints: new_social.append(ev)
        logger.info(f"增量处理: 官方{len(official)}条, 社交新{len(new_social)}条, 已有缓存{len(existing)}条")
        filtered = _filter_risk_events(official, new_social)
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
