"""
本地缓存 RAG 引擎
将 cache/ 下的所有 JSON 文件构建为可检索的知识库，
供小老鼠和其他 Agent 查询使用。

用法:
    from ..core import cache_rag
    ctx = cache_rag.query("002081")
    # ctx = "... 根据缓存数据，金螳螂(002081) 的人气排名第214..."
"""
from __future__ import annotations

import json
import os
import re
import glob
from datetime import datetime
from typing import Optional

from .config import CACHE_DIR, AI_CACHE_DIR, STOCK_NAMES_CACHE_PATH

# ── 内存知识库 ────────────────────────────────────────────────

_knowledge_base: dict[str, list[dict]] = {}  # code -> [entries]
_stock_names: dict[str, str] = {}            # code -> name
_loaded = False


def _load_stock_names():
    """加载股票名称词典"""
    global _stock_names
    if not _stock_names and os.path.exists(STOCK_NAMES_CACHE_PATH):
        try:
            with open(STOCK_NAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                _stock_names = json.load(f)
        except Exception:
            _stock_names = {}


def ensure_loaded():
    """确保知识库已加载"""
    global _loaded, _knowledge_base
    if _loaded:
        return
    _load_stock_names()
    _knowledge_base = {}
    _scan_directory(CACHE_DIR)
    _scan_directory(AI_CACHE_DIR)
    _loaded = True


def _scan_directory(directory: str):
    """扫描目录下的所有 JSON 文件"""
    if not os.path.exists(directory):
        return
    for fpath in glob.glob(os.path.join(directory, "*.json")):
        fname = os.path.basename(fpath)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        _index_file(fname, data)


def _extract_code(fname: str, data: dict) -> str | None:
    """从文件名或数据中提取股票代码"""
    # 优先从数据中取
    for key in ("code", "symbol"):
        val = data.get(key, "")
        if val:
            val = str(val).upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
            if val.isdigit() and len(val) == 6:
                return val
    # 从文件名提取
    codes = re.findall(r'(\d{6})', fname)
    return codes[0] if codes else None


def _index_file(fname: str, data: dict):
    """将单个文件的内容索引到知识库"""
    code = _extract_code(fname, data)
    if not code:
        return

    if code not in _knowledge_base:
        _knowledge_base[code] = []

    # 判断文件类型
    fname_lower = fname.lower()

    # 1. AI 分析结果 (cache/ai/*.json)
    if "guba_analysis" in fname_lower:
        result = data.get("result", "")
        if result:
            _knowledge_base[code].append({
                "type": "ai_sentiment",
                "label": "AI 股吧舆情分析",
                "content": result[:500],
                "full": result,
            })

    elif "health" in fname_lower:
        result = data.get("result", "")
        if result:
            _knowledge_base[code].append({
                "type": "ai_health",
                "label": "AI 财务健康分析",
                "content": result[:500],
                "full": result,
            })

    elif "growth" in fname_lower:
        result = data.get("result", "")
        if result:
            _knowledge_base[code].append({
                "type": "ai_growth",
                "label": "AI 财务增长分析",
                "content": result[:500],
                "full": result,
            })

    elif "zygc" in fname_lower:
        result = data.get("result", "")
        if result:
            _knowledge_base[code].append({
                "type": "ai_zygc",
                "label": "AI 主营构成分析",
                "content": result[:500],
                "full": result,
            })

    # 2. 股吧数据 (cache/guba_*.json)
    elif "guba" in fname_lower:
        post_titles = data.get("post_titles", [])
        keywords = data.get("keywords", [])
        rank = data.get("rank", {})
        parts = []
        if rank:
            parts.append(f"人气排名第{rank.get('rank','?')}名（共{rank.get('marketAllCount','?')}只股票）")
        if keywords:
            parts.append("热门概念: " + ", ".join(f"{k['keyword']}(热度{k['hotness']})" for k in keywords[:5]))
        if post_titles:
            sample = [p.get("title", "") if isinstance(p, dict) else p for p in post_titles[:5]]
            parts.append("最新帖子: " + " | ".join(sample))
        summary = "；".join(parts)
        if summary:
            _knowledge_base[code].append({
                "type": "guba",
                "label": "东方财富股吧数据",
                "content": summary,
                "full": json.dumps(data, ensure_ascii=False)[:1000],
            })

    # 3. 财务数据 (cache/financial_*.json)
    elif "financial" in fname_lower:
        sheets = data.get("profit_sheet", [])
        if sheets:
            latest = sheets[-1] if sheets else {}
            eps = latest.get("BASIC_EPS", "N/A")
            revenue = latest.get("TOTAL_OPERATE_INCOME", "N/A")
            netprofit = latest.get("NETPROFIT", "N/A")
            summary = f"最新财报: 营收={revenue}, 净利润={netprofit}, EPS={eps}"
            _knowledge_base[code].append({
                "type": "financial",
                "label": "原始财务数据",
                "content": summary,
                "full": json.dumps(latest, ensure_ascii=False),
            })

    # 4. 主营构成等 (cache/{code}.json)
    elif fname.startswith("SH") or fname.startswith("SZ") or fname.startswith("BJ"):
        records = data.get("records", [])
        if records:
            latest = records[-1] if records else {}
            summary = f"主营构成(最新): {json.dumps(latest, ensure_ascii=False)[:200]}"
            _knowledge_base[code].append({
                "type": "zygc",
                "label": "主营构成数据",
                "content": summary,
                "full": json.dumps(data, ensure_ascii=False)[:1000],
            })


# ── 公开接口 ──────────────────────────────────────────────────


def get_stock_name(code: str) -> str:
    """获取股票中文名"""
    _load_stock_names()
    return _stock_names.get(code, "")


def query(code: str, max_entries: int = 3) -> str:
    """
    查询指定股票的所有缓存知识。

    返回格式化的文本，适合注入 LLM Prompt。
    """
    ensure_loaded()
    pure_code = code.upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
    name = get_stock_name(pure_code)

    entries = _knowledge_base.get(pure_code, [])
    if not entries:
        return ""

    # 去重（同类型只保留最新一条）
    seen_types = set()
    unique = []
    for e in entries:
        t = e["type"]
        if t not in seen_types:
            seen_types.add(t)
            unique.append(e)

    lines = [f"📚 【缓存知识】{name or pure_code}"]
    for e in unique[:max_entries]:
        lines.append(f"[{e['label']}] {e['content']}")
    lines.append("---")

    return "\n".join(lines)


def search(query_text: str, top_k: int = 3) -> list[dict]:
    """
    全文搜索知识库，返回匹配的知识条目。

    用于对话场景：用户问什么，就搜什么。
    """
    ensure_loaded()
    if not query_text.strip():
        return []

    results = []
    query_lower = query_text.lower()

    # 提取可能的股票代码
    code_match = re.findall(r'(\d{6})', query_text)
    target_codes = set(code_match) if code_match else set(_knowledge_base.keys())

    for code, entries in _knowledge_base.items():
        # 检查代码/名称是否匹配
        name = get_stock_name(code)
        code_match_ok = code in target_codes
        name_match_ok = name and query_lower in name.lower()

        for e in entries:
            content = (e.get("content", "") + " " + e.get("full", "")).lower()
            # 关键词匹配得分
            keywords = query_text.split()
            match_score = sum(1 for kw in keywords if kw.lower() in content)
            if match_score > 0 or code_match_ok or name_match_ok:
                results.append({
                    "code": code,
                    "name": name,
                    "type": e["type"],
                    "label": e["label"],
                    "content": e["content"],
                    "score": match_score + (2 if code_match_ok else 0) + (1 if name_match_ok else 0),
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def search_as_context(query_text: str) -> str:
    """搜索并格式化为上下文文本"""
    results = search(query_text, top_k=3)
    if not results:
        return ""

    lines = ["📚 以下是从缓存知识库中找到的相关信息："]
    for r in results:
        label = f"{r['name'] or r['code']} - {r['label']}"
        lines.append(f"[{label}] {r['content']}")
    lines.append("---")
    return "\n".join(lines)


def all_cached_codes() -> list[str]:
    """获取所有有缓存的股票代码"""
    ensure_loaded()
    codes = []
    for code in _knowledge_base:
        name = get_stock_name(code)
        codes.append({"code": code, "name": name or ""})
    codes.sort(key=lambda x: x["code"])
    return codes
