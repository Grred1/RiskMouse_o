"""
后端核心配置模块
包含缓存、AI 提示词加载等公共功能
"""
from __future__ import annotations

import os
import json
from typing import Optional

import akshare as ak
import pandas as pd


# 项目根目录（business_analysis/）
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)          # backend/app/
BACKEND_DIR = os.path.dirname(APP_DIR)       # backend/
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)  # business_analysis/

# 缓存目录：部署环境使用 /tmp（绝对可写），本地开发保持原路径
if os.getenv("COZE_ENV") or os.getenv("PORT"):
    CACHE_DIR = "/tmp/cache"
else:
    CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

AI_CACHE_DIR = os.path.join(CACHE_DIR, "ai")
os.makedirs(AI_CACHE_DIR, exist_ok=True)

# AI 提示词目录
PROMPTS_DIR = os.path.join(BACKEND_DIR, "prompts")

# 股票名称缓存
STOCK_NAMES_CACHE_PATH = os.path.join(CACHE_DIR, "stock_names.json")

stock_name_cache: Optional[dict] = None


def _ensure_stock_names_cache() -> dict:
    """确保股票名称缓存已加载"""
    global stock_name_cache
    if stock_name_cache is None:
        stock_name_cache = load_stock_names()
    return stock_name_cache


def format_num(val) -> float:
    """格式化数字"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    return round(float(val), 2)


def format_pct(val) -> float:
    """格式化百分比（转为 0-100）"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    return round(float(val) * 100, 2)


def normalize_symbol(code: str) -> str:
    """标准化股票代码"""
    code = code.strip().upper()
    if code.startswith(("SH", "SZ", "BJ")):
        return code
    if not code.isdigit():
        raise ValueError(f"无效的股票代码: {code}")
    if code.startswith(("6", "5")):
        return f"SH{code}"
    elif code.startswith(("0", "3")):
        return f"SZ{code}"
    elif code.startswith(("4", "8")):
        return f"BJ{code}"
    else:
        raise ValueError(f"无法识别的股票代码: {code}")


def extract_pure_code(symbol: str) -> str:
    """从 SZ002081 中提取 002081"""
    return symbol.strip().upper().lstrip("SH").lstrip("SZ").lstrip("BJ")


def _ensure_stock_names_cache():
    """确保股票名称缓存存在"""
    if os.path.exists(STOCK_NAMES_CACHE_PATH):
        return
    try:
        df = ak.stock_info_a_code_name()
        fresh = dict(zip(df["code"], df["name"]))
        with open(STOCK_NAMES_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(fresh, f, ensure_ascii=False)
    except Exception:
        pass


def get_stock_name(code: str) -> str:
    """获取股票名称"""
    global stock_name_cache
    if stock_name_cache is None:
        stock_name_cache = {}
        if os.path.exists(STOCK_NAMES_CACHE_PATH):
            try:
                with open(STOCK_NAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                    stock_name_cache = json.load(f)
            except Exception:
                pass
    if code in stock_name_cache:
        return stock_name_cache[code]
    try:
        df = ak.stock_info_a_code_name()
        fresh = dict(zip(df["code"], df["name"]))
        stock_name_cache.update(fresh)
        with open(STOCK_NAMES_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(stock_name_cache, f, ensure_ascii=False)
        return fresh.get(code, "")
    except Exception:
        return ""


def cache_path(symbol: str, module: str = "") -> str:
    """获取缓存文件路径"""
    if module:
        return os.path.join(CACHE_DIR, f"{module}_{symbol}.json")
    return os.path.join(CACHE_DIR, f"{symbol}.json")


def read_cache(symbol: str, module: str = "") -> Optional[dict]:
    """读取缓存"""
    path = cache_path(symbol, module)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["from_cache"] = True
                return data
        except Exception:
            pass
    return None


def write_cache(symbol: str, data: dict, module: str = ""):
    """写入缓存"""
    path = cache_path(symbol, module)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


SKILLS_DIR = os.path.join(PROMPTS_DIR, "skills")


def load_skill_md(skill_name: str) -> str:
    """
    从 backend/prompts/skills/<skill_name>.md 加载 skill 内容。
    找不到文件时返回空字符串。
    """
    path = os.path.join(SKILLS_DIR, f"{skill_name}.md")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""


def load_prompts() -> dict:
    """加载所有 AI 提示词模板"""
    prompts = {}
    prompt_files = {
        "zygc_analysis.txt": "ZYGC_PROMPT_TEMPLATE",
        "financial_health.txt": "FINANCIAL_HEALTH_TEMPLATE",
        "financial_growth.txt": "FINANCIAL_GROWTH_TEMPLATE",
        "financial_combined.txt": "FINANCIAL_COMBINED_TEMPLATE",
        "zt_risk.txt": "ZT_RISK_PROMPT",
    }
    for fname, var_name in prompt_files.items():
        path = os.path.join(PROMPTS_DIR, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                prompts[var_name] = f.read()
        else:
            prompts[var_name] = ""
    return prompts
