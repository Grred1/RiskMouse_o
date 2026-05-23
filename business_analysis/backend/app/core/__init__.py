"""
Core 模块 - 核心配置和工具
"""
from .config import (
    BACKEND_DIR,
    PROJECT_ROOT,
    CACHE_DIR,
    AI_CACHE_DIR,
    PROMPTS_DIR,
    format_num,
    format_pct,
    normalize_symbol,
    extract_pure_code,
    get_stock_name,
    read_cache,
    write_cache,
    load_prompts,
    _ensure_stock_names_cache,
)
from .llm import call_llm, cached_llm_call, get_llm_client
from .coze_agent import call_coze_agent, verify_news
from . import cache_rag

__all__ = [
    "BACKEND_DIR",
    "PROJECT_ROOT",
    "CACHE_DIR",
    "AI_CACHE_DIR",
    "PROMPTS_DIR",
    "format_num",
    "format_pct",
    "normalize_symbol",
    "extract_pure_code",
    "get_stock_name",
    "read_cache",
    "write_cache",
    "load_prompts",
    "_ensure_stock_names_cache",
    "call_llm",
    "cached_llm_call",
    "get_llm_client",
    "call_coze_agent",
    "verify_news",
]
