"""
缓存 RAG 引擎
将 cache/ 下的 JSON 文件构建为可检索的知识库，供小老鼠查询。

改进：
  - 过滤噪音文件（news_full_* / sparkline_* / macro_* 不索引）
  - 增量加载：记录文件 mtime，只重载变化的文件
  - 统一入口，不再需要全局 ensure_loaded 阻塞
"""
from __future__ import annotations

import json
import os
import re
import glob
import time
from datetime import datetime
from typing import Optional

from ..config import CACHE_DIR, AI_CACHE_DIR, STOCK_NAMES_CACHE_PATH
from .cleanup import is_daily_snapshot

# ── 不索引的文件模式 ──────────────────────────────────────────
_SKIP_PATTERNS: list[re.Pattern] = [
    re.compile(r"^macro_.*\.json$"),
    re.compile(r"^stock_names\.json$"),
]


def _should_skip(fname: str) -> bool:
    """判断文件是否应跳过索引"""
    if is_daily_snapshot(fname):
        return True
    for p in _SKIP_PATTERNS:
        if p.match(fname):
            return True
    return False


# ── 股票名称缓存 ──────────────────────────────────────────────

_stock_names: dict[str, str] = {}


def _load_stock_names():
    if not _stock_names and os.path.exists(STOCK_NAMES_CACHE_PATH):
        try:
            with open(STOCK_NAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                _stock_names.update(json.load(f))
        except Exception:
            pass


def get_stock_name(code: str) -> str:
    _load_stock_names()
    return _stock_names.get(code, "")


# ── 内存知识库 + mtime 跟踪 ───────────────────────────────────

class CacheRAG:
    """
    缓存 RAG 查询引擎。
    使用延迟加载 + 增量更新策略。

    用法:
        rag = CacheRAG()
        ctx = rag.query("002081")
        results = rag.search("贵州茅台")
    """

    def __init__(self):
        self._knowledge_base: dict[str, list[dict]] = {}
        self._file_mtimes: dict[str, float] = {}  # fpath → mtime
        self._loaded = False

    def ensure_loaded(self):
        """确保知识库已加载（增量更新）"""
        _load_stock_names()
        self._scan_directory(CACHE_DIR)
        self._scan_directory(AI_CACHE_DIR)
        self._loaded = True

    def _scan_directory(self, directory: str):
        """扫描目录，只处理新增或修改过的文件"""
        if not os.path.exists(directory):
            return
        for fpath in glob.glob(os.path.join(directory, "*.json")):
            fname = os.path.basename(fpath)

            # 跳过噪音文件
            if _should_skip(fname):
                continue

            # 检查 mtime 是否变化
            try:
                current_mtime = os.path.getmtime(fpath)
            except Exception:
                continue
            last_mtime = self._file_mtimes.get(fpath, 0)
            if current_mtime <= last_mtime and fpath in self._file_mtimes:
                continue  # 文件未变化

            # 加载并索引
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            self._index_file(fname, data)
            self._file_mtimes[fpath] = current_mtime

    def _extract_code(self, fname: str, data: dict) -> str | None:
        """从文件名或数据中提取股票代码"""
        for key in ("code", "symbol"):
            val = data.get(key, "")
            if val:
                val = str(val).upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
                if val.isdigit() and len(val) == 6:
                    return val
        codes = re.findall(r'(\d{6})', fname)
        return codes[0] if codes else None

    def _index_file(self, fname: str, data: dict):
        """将单个文件内容索引到知识库"""
        code = self._extract_code(fname, data)
        if not code:
            return

        if code not in self._knowledge_base:
            self._knowledge_base[code] = []

        fname_lower = fname.lower()

        # AI 分析结果
        if "guba_analysis" in fname_lower:
            result = data.get("result", "")
            if result:
                self._knowledge_base[code].append({
                    "type": "ai_sentiment", "label": "AI 股吧舆情分析",
                    "content": result[:500], "full": result,
                })
        elif "health" in fname_lower:
            result = data.get("result", "")
            if result:
                self._knowledge_base[code].append({
                    "type": "ai_health", "label": "AI 财务健康分析",
                    "content": result[:500], "full": result,
                })
        elif "growth" in fname_lower:
            result = data.get("result", "")
            if result:
                self._knowledge_base[code].append({
                    "type": "ai_growth", "label": "AI 财务增长分析",
                    "content": result[:500], "full": result,
                })
        elif "zygc" in fname_lower:
            result = data.get("result", "")
            if result:
                self._knowledge_base[code].append({
                    "type": "ai_zygc", "label": "AI 主营构成分析",
                    "content": result[:500], "full": result,
                })
        elif "risk_interpret" in fname_lower:
            result = data.get("result", "")
            if result:
                self._knowledge_base[code].append({
                    "type": "ai_watchlist_risk", "label": "AI 自选股风险解读",
                    "content": result[:500], "full": result,
                })
        elif "risk_analyze" in fname_lower:
            result = data.get("result", "")
            if result:
                self._knowledge_base[code].append({
                    "type": "ai_risk_analyze", "label": "AI 涨停风险评分",
                    "content": result[:500], "full": result,
                })
        # 股吧数据
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
                self._knowledge_base[code].append({
                    "type": "guba", "label": "东方财富股吧数据",
                    "content": summary,
                    "full": json.dumps(data, ensure_ascii=False)[:1000],
                })
        # 财务数据
        elif "financial" in fname_lower and "combined" not in fname_lower:
            sheets = data.get("profit_sheet", [])
            if sheets:
                latest = sheets[-1] if sheets else {}
                eps = latest.get("BASIC_EPS", "N/A")
                revenue = latest.get("TOTAL_OPERATE_INCOME", "N/A")
                netprofit = latest.get("NETPROFIT", "N/A")
                summary = f"最新财报: 营收={revenue}, 净利润={netprofit}, EPS={eps}"
                self._knowledge_base[code].append({
                    "type": "financial", "label": "原始财务数据",
                    "content": summary,
                    "full": json.dumps(latest, ensure_ascii=False),
                })
        # 主营构成（SZ/SH/BJ 开头）
        elif fname.startswith(("SH", "SZ", "BJ")):
            records = data.get("records", [])
            if records:
                latest = records[-1] if records else {}
                summary = f"主营构成(最新): {json.dumps(latest, ensure_ascii=False)[:200]}"
                self._knowledge_base[code].append({
                    "type": "zygc", "label": "主营构成数据",
                    "content": summary,
                    "full": json.dumps(data, ensure_ascii=False)[:1000],
                })

    # ── 公开查询接口 ──────────────────────────────────────────

    def query(self, code: str, max_entries: int = 3) -> str:
        """查询指定股票的所有缓存知识"""
        self.ensure_loaded()
        pure_code = code.upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
        name = get_stock_name(pure_code)

        entries = self._knowledge_base.get(pure_code, [])
        if not entries:
            return ""

        seen_types = set()
        unique = []
        for e in entries:
            if e["type"] not in seen_types:
                seen_types.add(e["type"])
                unique.append(e)

        lines = [f"📚 【缓存知识】{name or pure_code}"]
        for e in unique[:max_entries]:
            lines.append(f"[{e['label']}] {e['content']}")
        lines.append("---")
        return "\n".join(lines)

    def search(self, query_text: str, top_k: int = 3) -> list[dict]:
        """全文搜索知识库"""
        self.ensure_loaded()
        if not query_text.strip():
            return []

        results = []
        query_lower = query_text.lower()
        code_match = re.findall(r'(\d{6})', query_text)
        target_codes = set(code_match) if code_match else set(self._knowledge_base.keys())

        for code, entries in self._knowledge_base.items():
            name = get_stock_name(code)
            code_match_ok = code in target_codes
            name_match_ok = name and query_lower in name.lower()

            for e in entries:
                content = (e.get("content", "") + " " + e.get("full", "")).lower()
                keywords = query_text.split()
                match_score = sum(1 for kw in keywords if kw.lower() in content)
                if match_score > 0 or code_match_ok or name_match_ok:
                    results.append({
                        "code": code, "name": name,
                        "type": e["type"], "label": e["label"],
                        "content": e["content"],
                        "score": match_score + (2 if code_match_ok else 0) + (1 if name_match_ok else 0),
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_as_context(self, query_text: str) -> str:
        """搜索并格式化为 LLM 上下文"""
        results = self.search(query_text, top_k=3)
        if not results:
            return ""
        lines = ["📚 以下是从缓存知识库中找到的相关信息："]
        for r in results:
            label = f"{r['name'] or r['code']} - {r['label']}"
            lines.append(f"[{label}] {r['content']}")
        lines.append("---")
        return "\n".join(lines)

    def all_cached_codes(self) -> list[dict]:
        """获取所有有缓存的股票代码"""
        self.ensure_loaded()
        codes = []
        for code in self._knowledge_base:
            name = get_stock_name(code)
            codes.append({"code": code, "name": name or ""})
        codes.sort(key=lambda x: x["code"])
        return codes


# ── 模块级单例（兼容旧导入方式） ────────────────────────────

_rag_instance: Optional[CacheRAG] = None


def _get_rag() -> CacheRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = CacheRAG()
    return _rag_instance


# 兼容旧接口
def ensure_loaded():
    _get_rag().ensure_loaded()


def query(code: str, max_entries: int = 3) -> str:
    return _get_rag().query(code, max_entries)


def search(query_text: str, top_k: int = 3) -> list[dict]:
    return _get_rag().search(query_text, top_k)


def search_as_context(query_text: str) -> str:
    return _get_rag().search_as_context(query_text)


def all_cached_codes() -> list[str]:
    return _get_rag().all_cached_codes()
