"""
本地缓存 RAG 引擎（兼容层）
委托给 core/cache/rag.py 的实现。

新代码请直接使用 core.cache.rag 或 core.cache.CacheRAG。
"""
from .cache.rag import (
    ensure_loaded,
    query,
    search,
    search_as_context,
    all_cached_codes,
    get_stock_name,
)

__all__ = [
    "ensure_loaded",
    "query",
    "search",
    "search_as_context",
    "all_cached_codes",
    "get_stock_name",
]
