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
    load_skill_md,
    _ensure_stock_names_cache,
)
from .llm import call_llm, cached_llm_call, get_llm_client
from .coze_agent import call_coze_agent, verify_news
from .skill_emotional import emotional_first_aid, detect_emotion, is_emotional
from .skill_risk_edu import risk_education, has_edu_match
from . import cache_rag
from . import usage_doc

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
    "load_skill_md",
    "_ensure_stock_names_cache",
    "call_llm",
    "cached_llm_call",
    "get_llm_client",
    "call_coze_agent",
    "verify_news",
    "emotional_first_aid",
    "detect_emotion",
    "is_emotional",
    "risk_education",
    "has_edu_match",
    "cache_rag",
    "usage_doc",
]
