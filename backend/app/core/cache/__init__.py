"""
缓存管理层
统一管理所有缓存操作：读写、TTL 清理、RAG 索引。

分层关系：
  config.py read_cache/write_cache     — 底层文件读写（不涉及清理策略）
  cache/cleanup.py                      — TTL 清理策略
  cache/rag.py                          — 缓存内容 → RAG 知识库
"""
from .cleanup import cleanup_cache, is_daily_snapshot
from .rag import CacheRAG

__all__ = [
    "cleanup_cache",
    "is_daily_snapshot",
    "CacheRAG",
]
