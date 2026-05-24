"""
缓存清理模块
按 TTL 规则清理过期的日级缓存文件，避免磁盘堆积。
"""
from __future__ import annotations

import os
import re
import time
import logging
from datetime import datetime, timedelta

from ..config import CACHE_DIR, AI_CACHE_DIR

logger = logging.getLogger(__name__)

# 日级快照文件的 TTL（秒）
_NEWS_TTL = 7 * 86400       # news_full_* 保留 7 天
_SPARKLINE_TTL = 7 * 86400  # sparkline_* 保留 7 天

# 文件名匹配模式 → (TTL 秒, 说明)
_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"^news_full_\d{6}_\d{8}\.json$"), _NEWS_TTL, "新闻快照"),
    (re.compile(r"^sparkline_\d{6}_\d{8}\.json$"), _SPARKLINE_TTL, "K线快照"),
]


def is_daily_snapshot(fname: str) -> bool:
    """判断文件名是否为日级快照"""
    for pattern, _, _ in _PATTERNS:
        if pattern.match(fname):
            return True
    return False


def _clean_directory(directory: str, now: float):
    """清理单个目录中过期的缓存文件"""
    if not os.path.exists(directory):
        return
    removed = 0
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue
        for pattern, ttl, label in _PATTERNS:
            if pattern.match(fname):
                mtime = os.path.getmtime(fpath)
                age = now - mtime
                if age > ttl:
                    try:
                        os.remove(fpath)
                        removed += 1
                        logger.info("清理过期%s: %s (已存 %.1f 天)", label, fname, age / 86400)
                    except Exception as e:
                        logger.warning("清理失败 %s: %s", fname, e)
                break
    return removed


def cleanup_cache() -> dict:
    """
    清理所有过期缓存文件。
    返回清理统计信息。
    """
    now = time.time()
    stats: dict[str, int] = {}

    stats["cache"] = _clean_directory(CACHE_DIR, now) or 0
    stats["ai"] = _clean_directory(AI_CACHE_DIR, now) or 0

    total = sum(stats.values())
    if total:
        logger.info("缓存清理完成: 共移除 %d 个过期文件 (%s)", total, stats)
    else:
        logger.info("缓存清理完成: 无过期文件")

    return stats
