"""RiskMouse 既有数据能力的工具化封装。所有返回都含可追溯证据。"""
from __future__ import annotations

from ..core import extract_pure_code, get_stock_name, normalize_symbol
from ..core.data import akshare as data_akshare
from ..core.data import guba as data_guba
from .registry import register_tool


def _records(frame, limit: int = 4) -> list[dict]:
    if frame is None or frame.empty:
        return []
    return frame.tail(limit).fillna("").to_dict("records")


@register_tool("get_financials", "获取财务摘要与最近财务报表", timeout_seconds=25)
def get_financials(symbol: str) -> dict:
    code = extract_pure_code(normalize_symbol(symbol))
    frame = data_akshare.get_financial_abstract(code)
    records = _records(frame)
    return {
        "symbol": code,
        "name": get_stock_name(code) or code,
        "records": records,
        # 没有真实财务记录时绝不能生成占位证据，否则 Verifier 会错误地提高置信度。
        "evidence": ([{"id": "financial_1", "source": "akshare/同花顺财务摘要", "as_of": str(records[-1].get("报告期", ""))}] if records else []),
        "limitations": [] if records else ["未获取到财务摘要，不能据此判断基本面风险"],
    }


@register_tool("get_stock_news", "获取个股近期公开新闻", timeout_seconds=20)
def get_stock_news(symbol: str) -> dict:
    code = extract_pure_code(normalize_symbol(symbol))
    frame = data_akshare.get_stock_news(code)
    if frame is None or frame.empty:
        items = []
    else:
        title_col = next((col for col in ("新闻标题", "标题", "title") if col in frame.columns), None)
        date_col = next((col for col in ("发布时间", "日期", "date") if col in frame.columns), None)
        items = [
            {"title": str(row.get(title_col, "")), "date": str(row.get(date_col, ""))[:10] if date_col else ""}
            for _, row in frame.head(10).iterrows()
        ]
    return {
        "symbol": code,
        "items": items,
        "evidence": [{"id": f"news_{index + 1}", "source": "akshare/东方财富新闻", **item} for index, item in enumerate(items)],
        "limitations": [] if items else ["未获取到近期新闻，舆情结论置信度应降低"],
    }


@register_tool("get_guba_posts", "获取个股股吧公开帖子标题", timeout_seconds=20)
def get_guba_posts(symbol: str) -> dict:
    code = extract_pure_code(normalize_symbol(symbol))
    posts = data_guba.scrape_stock_posts(code, max_pages=1, max_posts=15)
    return {
        "symbol": code,
        "items": posts,
        "evidence": [{"id": f"guba_{index + 1}", "source": "东方财富股吧", **item} for index, item in enumerate(posts)],
        "limitations": [] if posts else ["未获取到股吧帖子，不能将沉默解释为没有风险"],
    }
