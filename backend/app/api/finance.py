"""
财报风险分析 API
"""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import os
import glob

from fastapi import APIRouter, HTTPException, Query

from ..core import (
    format_num,
    format_pct,
    normalize_symbol,
    extract_pure_code,
    get_stock_name,
    search_stock,
    read_cache,
    write_cache,
    load_prompts,
    CACHE_DIR,
    AI_CACHE_DIR,
)
from ..core.data import akshare as data_akshare
from ..agents import run_agent

router = APIRouter(prefix="/api", tags=["财报风险"])

# 加载提示词
PROMPTS = load_prompts()
ZYGC_PROMPT_TEMPLATE = PROMPTS.get("ZYGC_PROMPT_TEMPLATE", "")
FINANCIAL_HEALTH_TEMPLATE = PROMPTS.get("FINANCIAL_HEALTH_TEMPLATE", "")
FINANCIAL_GROWTH_TEMPLATE = PROMPTS.get("FINANCIAL_GROWTH_TEMPLATE", "")
FINANCIAL_COMBINED_TEMPLATE = PROMPTS.get("FINANCIAL_COMBINED_TEMPLATE", "")

# 财务数据列定义
_PROFIT_KEY_COLS = [
    "TOTAL_OPERATE_INCOME", "TOTAL_OPERATE_INCOME_YOY",
    "OPERATE_INCOME", "TOTAL_OPERATE_COST", "OPERATE_COST",
    "OPERATE_PROFIT", "OPERATE_PROFIT_YOY",
    "TOTAL_PROFIT", "TOTAL_PROFIT_YOY",
    "NETPROFIT", "NETPROFIT_YOY",
    "PARENT_NETPROFIT", "PARENT_NETPROFIT_YOY",
    "DEDUCT_PARENT_NETPROFIT", "DEDUCT_PARENT_NETPROFIT_YOY",
    "BASIC_EPS",
    "RESEARCH_EXPENSE", "RESEARCH_EXPENSE_YOY",
    "SALE_EXPENSE", "SALE_EXPENSE_YOY",
    "MANAGE_EXPENSE", "MANAGE_EXPENSE_YOY",
    "FINANCE_EXPENSE", "FINANCE_EXPENSE_YOY",
    "OPERATE_TAX_ADD",
]

# 前端期望字段名 → akshare 实际列名（不一致时映射）
_PROFIT_ALIASES = {
    "TOTAL_OPERATE_INCOME": "OPERATE_INCOME",
    "TOTAL_OPERATE_INCOME_YOY": "OPERATE_INCOME_YOY",
    "TOTAL_OPERATE_COST": "OPERATE_COST",
}

_BALANCE_KEY_COLS = [
    "MONETARYFUNDS", "ADVANCE_RECEIVABLES", "INVENTORY",
    "TOTAL_CURRENT_ASSETS", "TOTAL_NONCURRENT_ASSETS", "TOTAL_ASSETS",
    "TOTAL_CURRENT_LIAB", "TOTAL_NONCURRENT_LIAB", "TOTAL_LIABILITIES",
    "TOTAL_EQUITY", "TOTAL_PARENT_EQUITY",
    "FIXED_ASSET", "CIP",
]

_CASHFLOW_KEY_COLS = [
    "NETCASH_OPERATE", "NETCASH_INVEST",
    "NETCASH_FINANCE", "END_CASH_EQUIVALENTS",
]


def _safe_val(row, col: str):
    """安全获取数值"""
    if col not in row:
        return None
    val = row[col]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


@router.get("/stock/search")
def api_search_stock(
    q: str = Query(..., description="搜索关键词，股票代码或名称"),
    limit: int = Query(10, description="返回条数上限"),
):
    """按名称或代码模糊搜索股票"""
    return {"results": search_stock(q, limit=limit)}


@router.get("/zygc")
def get_zygc(
    symbol: str = Query(..., description="股票代码"),
    refresh: bool = Query(False, description="是否强制刷新"),
):
    """获取主营构成数据"""
    try:
        symbol = normalize_symbol(symbol)

        # 检查缓存
        if not refresh:
            cached = read_cache(symbol)
            if cached:
                return cached

        df = data_akshare.get_stock_zygc(symbol=symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="未获取到数据")

        records = []
        for _, row in df.iterrows():
            records.append({
                "股票代码": str(row["股票代码"]),
                "报告日期": str(row["报告日期"]),
                "分类类型": str(row["分类类型"]),
                "主营构成": str(row["主营构成"]),
                "主营收入": format_num(row["主营收入"]),
                "收入比例": format_pct(row["收入比例"]),
                "主营成本": format_num(row["主营成本"]),
                "成本比例": format_pct(row["成本比例"]),
                "主营利润": format_num(row["主营利润"]),
                "利润比例": format_pct(row["利润比例"]),
                "毛利率": format_pct(row["毛利率"]),
            })

        report_dates = sorted(list(set(r["报告日期"] for r in records)), reverse=True)
        categories = sorted(list(set(r["分类类型"] for r in records)))
        code = extract_pure_code(symbol)
        name = get_stock_name(code)

        result = {
            "symbol": symbol,
            "code": code,
            "name": name,
            "records": records,
            "report_dates": report_dates,
            "categories": categories,
            "total": len(records),
            "from_cache": False,
        }

        write_cache(symbol, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.post("/analyze/zygc")
def analyze_zygc(data: dict):
    """AI 解读主营构成"""
    symbol = data.get("symbol", "")
    latest_data = data.get("latestData", {})

    dates = sorted(
        set(r.get("报告日期", "") for cat in latest_data.values() for r in cat),
        reverse=True,
    )

    prompt = ZYGC_PROMPT_TEMPLATE.format(
        symbol=symbol,
        industry_data=json.dumps(latest_data.get("按行业分类", []), ensure_ascii=False, indent=2),
        product_data=json.dumps(latest_data.get("按产品分类", []), ensure_ascii=False, indent=2),
        region_data=json.dumps(latest_data.get("按地区分类", []), ensure_ascii=False, indent=2),
    )
    analysis = run_agent("analyze_zygc", {
        "prompt_text": prompt,
        "code": symbol,
    })
    return {"analysis": analysis}


@router.get("/financial")
def get_financial(
    symbol: str = Query(..., description="股票代码"),
    refresh: bool = Query(False, description="是否强制刷新"),
):
    """获取财务数据"""
    try:
        symbol = normalize_symbol(symbol)
        code = extract_pure_code(symbol)
        name = get_stock_name(code)

        # 检查缓存
        cache_file = f"{symbol}_financial.json"
        if not refresh:
            cached = read_cache(code, module="financial")
            if cached:
                return cached

        # 1. 利润表
        try:
            profit_df = data_akshare.get_profit_sheet(symbol=symbol)
            profit_records = []
            if profit_df is not None:
                profit_df = profit_df.sort_values("REPORT_DATE")
                for _, row in profit_df.iterrows():
                    date_val = str(row["REPORT_DATE"])
                    # 统一日期格式：纯8位数字 -> YYYY-MM-DD
                    if len(date_val) == 8 and date_val.isdigit():
                        rec_date = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    else:
                        rec_date = date_val[:10]
                    rec = {"REPORT_DATE": rec_date, "REPORT_TYPE": row.get("REPORT_TYPE", "")}
                    for c in _PROFIT_KEY_COLS:
                        actual_col = _PROFIT_ALIASES.get(c, c)
                        if actual_col in profit_df.columns:
                            rec[c] = _safe_val(row, actual_col)
                    profit_records.append(rec)
        except Exception:
            profit_records = []

        # 2. 资产负债表
        try:
            balance_df = data_akshare.get_balance_sheet(symbol=symbol)
            balance_records = []
            if balance_df is not None:
                balance_df = balance_df.sort_values("REPORT_DATE")
                for _, row in balance_df.iterrows():
                    date_val = str(row["REPORT_DATE"])
                    if len(date_val) == 8 and date_val.isdigit():
                        rec_date = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    else:
                        rec_date = date_val[:10]
                    rec = {"REPORT_DATE": rec_date, "REPORT_TYPE": row.get("REPORT_TYPE", "")}
                    for c in _BALANCE_KEY_COLS:
                        if c in balance_df.columns:
                            rec[c] = _safe_val(row, c)
                    balance_records.append(rec)
        except Exception:
            balance_records = []

        # 3. 现金流量表
        try:
            cash_df = data_akshare.get_cash_flow_sheet(symbol=symbol)
            cash_records = []
            if cash_df is not None:
                cash_df = cash_df.sort_values("REPORT_DATE")
                for _, row in cash_df.iterrows():
                    date_val = str(row["REPORT_DATE"])
                    if len(date_val) == 8 and date_val.isdigit():
                        rec_date = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    else:
                        rec_date = date_val[:10]
                    rec = {"REPORT_DATE": rec_date, "REPORT_TYPE": row.get("REPORT_TYPE", "")}
                    for c in _CASHFLOW_KEY_COLS:
                        if c in cash_df.columns:
                            rec[c] = _safe_val(row, c)
                    cash_records.append(rec)
        except Exception:
            cash_records = []

        # 4. 财务摘要
        try:
            abstract = data_akshare.get_financial_abstract(symbol=code)
            abstract_records = abstract.to_dict("records") if abstract is not None else []
        except Exception:
            abstract_records = []

        result = {
            "symbol": symbol,
            "code": code,
            "name": name,
            "profit_sheet": profit_records,
            "balance_sheet": balance_records,
            "cash_flow": cash_records,
            "financial_abstract": abstract_records,
            "from_cache": False,
        }

        write_cache(code, result, module="financial")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财务数据失败: {str(e)}")


@router.post("/analyze/financial")
def analyze_financial(data: dict):
    """AI 分析财务数据"""
    symbol = data.get("symbol", "")
    code = data.get("code", "")
    name = data.get("name", "")
    latest_abstract = data.get("latestAbstract", {})
    latest_date = str(latest_abstract.get("报告期", ""))[:10] if latest_abstract.get("报告期") else ""

    profit_trend = data.get("profitTrend", [])
    balance_latest = data.get("balanceLatest", {})
    cash_latest = data.get("cashLatest", {})

    health_prompt_text = FINANCIAL_HEALTH_TEMPLATE.format(**{
        "symbol": symbol, "name": name, "latest_date": latest_date,
        "revenue": f"{latest_abstract.get('营业总收入', 'N/A')}",
        "revenue_yoy": f"{latest_abstract.get('营业总收入同比增长率', 'N/A')}",
        "net_profit": f"{latest_abstract.get('净利润', 'N/A')}",
        "net_profit_yoy": f"{latest_abstract.get('净利润同比增长率', 'N/A')}",
        "gross_margin": f"{latest_abstract.get('销售毛利率', 'N/A')}",
        "net_margin": f"{latest_abstract.get('销售净利率', 'N/A')}",
        "roe": f"{latest_abstract.get('净资产收益率', 'N/A')}",
        "debt_ratio": f"{latest_abstract.get('资产负债率', 'N/A')}",
        "operate_cash_flow": f"{latest_abstract.get('每股经营现金流', 'N/A')}",
        "profit_sheet": json.dumps(balance_latest, ensure_ascii=False, indent=2),
        "balance_sheet": json.dumps(balance_latest, ensure_ascii=False, indent=2),
        "cash_flow_sheet": json.dumps(cash_latest, ensure_ascii=False, indent=2),
        "revenue_trend": json.dumps(profit_trend[-5:] if len(profit_trend) > 5 else profit_trend, ensure_ascii=False, indent=2),
        "profit_trend": json.dumps(profit_trend[-5:] if len(profit_trend) > 5 else profit_trend, ensure_ascii=False, indent=2),
    }) if FINANCIAL_HEALTH_TEMPLATE else "暂无模板"
    health_result = run_agent("analyze_financial", {"prompt_text": health_prompt_text, "code": code, "name": name})

    rd_data = data.get("rdData", [])
    business_growth = data.get("businessGrowth", {})
    asset_expansion = data.get("assetExpansion", [])
    growth_prompt_text = FINANCIAL_GROWTH_TEMPLATE.format(**{
        "symbol": symbol, "name": name,
        "rd_data": json.dumps(rd_data[-5:] if len(rd_data) > 5 else rd_data, ensure_ascii=False, indent=2),
        "business_growth": json.dumps(business_growth, ensure_ascii=False, indent=2),
        "asset_expansion": json.dumps(asset_expansion[-5:] if len(asset_expansion) > 5 else asset_expansion, ensure_ascii=False, indent=2),
        "profitability_trend": json.dumps(profit_trend[-5:] if len(profit_trend) > 5 else profit_trend, ensure_ascii=False, indent=2),
    }) if FINANCIAL_GROWTH_TEMPLATE else "暂无模板"
    growth_result = run_agent("analyze_financial", {"prompt_text": growth_prompt_text, "code": code, "name": name})

    return {"health": health_result, "growth": growth_result}


@router.post("/analyze/financial-combined")
def analyze_financial_combined(data: dict):
    """AI 财务健康与增长整合分析（量化评分版）"""
    symbol = data.get("symbol", "")
    code = data.get("code", "")
    name = data.get("name", "")
    latest_abstract = data.get("latestAbstract", {})
    latest_date = str(latest_abstract.get("报告期", ""))[:10] if latest_abstract.get("报告期") else ""

    cache_key = f"_combined_{latest_date}" if latest_date else "_combined"

    prompt = FINANCIAL_COMBINED_TEMPLATE
    profit_trend = data.get("profitTrend", [])
    balance_latest = data.get("balanceLatest", {})
    cash_latest = data.get("cashLatest", {})
    rd_data = data.get("rdData", [])

    vars_dict = {
        "symbol": symbol,
        "name": name,
        "financial_data": json.dumps({
            "abstract": latest_abstract,
            "balance": balance_latest,
            "cash": cash_latest,
            "profit_trend": profit_trend[-5:] if len(profit_trend) > 5 else profit_trend,
            "rd_data": rd_data[-5:] if len(rd_data) > 5 else rd_data,
        }, ensure_ascii=False, indent=2),
        "historical_data": json.dumps(profit_trend[-5:] if len(profit_trend) > 5 else profit_trend, ensure_ascii=False, indent=2),
        "industry_data": "暂无行业对比数据",
    }
    result_text = run_agent("analyze_financial", {
        "prompt_text": prompt.format(**vars_dict),
        "code": code, "name": name,
    })

    # 尝试解析 JSON
    import re
    scores = {"solvency": 0, "operating_capacity": 0, "profitability": 0, "growth_and_cashflow": 0}
    overall_conclusion = ""
    final_conclusion = ""

    try:
        # 提取 JSON 块
        start = result_text.find("{")
        end = result_text.rfind("}")
        if start >= 0 and end > start:
            json_str = result_text[start:end+1]
            parsed = json.loads(json_str)
            overall_conclusion = parsed.get("overall_conclusion", "")
            final_conclusion = parsed.get("final_conclusion", "")
            s = parsed.get("scores", {})
            scores = {
                "solvency": int(s.get("solvency", 0)),
                "operating_capacity": int(s.get("operating_capacity", 0)),
                "profitability": int(s.get("profitability", 0)),
                "growth_and_cashflow": int(s.get("growth_and_cashflow", 0)),
            }
    except (json.JSONDecodeError, ValueError, KeyError):
        final_conclusion = result_text

    return {
        "overall_conclusion": overall_conclusion,
        "scores": scores,
        "final_conclusion": final_conclusion,
        "raw": result_text,
    }


@router.post("/financial/clear-cache")
def clear_finance_cache(data: dict):
    """清除指定股票在所有模块的缓存数据"""
    code = data.get("code", "").strip()
    if not code or not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="无效股票代码")

    prefixes = ["SH", "SZ", "BJ"]
    removed = 0

    # 1. cache/{SZ/SH/BJ}{code}.json（主营构成）
    for p in prefixes:
        path = os.path.join(CACHE_DIR, f"{p}{code}.json")
        if os.path.exists(path):
            try:
                os.remove(path)
                removed += 1
            except Exception:
                pass

    # 2. cache/financial_{code}.json
    path = os.path.join(CACHE_DIR, f"financial_{code}.json")
    if os.path.exists(path):
        try:
            os.remove(path)
            removed += 1
        except Exception:
            pass

    # 3. cache/watchlist_analysis_{code}.json
    path = os.path.join(CACHE_DIR, f"watchlist_analysis_{code}.json")
    if os.path.exists(path):
        try:
            os.remove(path)
            removed += 1
        except Exception:
            pass

    # 4. cache/guba_{code}*.json
    for f in glob.glob(os.path.join(CACHE_DIR, f"guba_{code}*.json")):
        try: os.remove(f); removed += 1
        except: pass

    # 5. cache/news_full_{code}_*.json
    for f in glob.glob(os.path.join(CACHE_DIR, f"news_full_{code}_*.json")):
        try: os.remove(f); removed += 1
        except: pass

    # 6. cache/sparkline_{code}_*.json
    for f in glob.glob(os.path.join(CACHE_DIR, f"sparkline_{code}_*.json")):
        try: os.remove(f); removed += 1
        except: pass

    # 7. cache/agent_*{code}*.json
    for f in glob.glob(os.path.join(CACHE_DIR, f"agent_*{code}*.json")):
        try: os.remove(f); removed += 1
        except: pass

    # 8. cache/ai/*_{code}*.json
    for f in glob.glob(os.path.join(AI_CACHE_DIR, f"*{code}*.json")):
        try: os.remove(f); removed += 1
        except: pass

    return {"ok": True, "removed": removed, "code": code}
