from typing import Optional
import os
import json
from datetime import datetime
import akshare as ak
import pandas as pd
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from config import DEEPSEEK_API_KEY, BASE_DIR

# 文件缓存目录
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# AI 分析结果缓存目录
AI_CACHE_DIR = os.path.join(CACHE_DIR, "ai")
os.makedirs(AI_CACHE_DIR, exist_ok=True)

PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# 加载 AI 提示词模板
ZYGC_PROMPT_TEMPLATE = ""
FINANCIAL_HEALTH_TEMPLATE = ""
FINANCIAL_GROWTH_TEMPLATE = ""

prompt_paths = {
    "zygc_analysis.txt": "ZYGC_PROMPT_TEMPLATE",
    "financial_health.txt": "FINANCIAL_HEALTH_TEMPLATE",
    "financial_growth.txt": "FINANCIAL_GROWTH_TEMPLATE",
}
for fname, var_name in prompt_paths.items():
    path = os.path.join(PROMPTS_DIR, fname)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            globals()[var_name] = f.read()

app = FastAPI(title="主营构成分析工具")

# 挂载静态文件目录
css_dir = os.path.join(BASE_DIR, "css")
js_dir = os.path.join(BASE_DIR, "js")
if os.path.exists(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")
if os.path.exists(js_dir):
    app.mount("/js", StaticFiles(directory=js_dir), name="js")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stock_name_cache = None


@app.on_event("startup")
def startup():
    _ensure_stock_names_cache()


def format_num(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    return round(float(val), 2)


def format_pct(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    return round(float(val) * 100, 2)


def normalize_symbol(code: str) -> str:
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


STOCK_NAMES_CACHE_PATH = os.path.join(CACHE_DIR, "stock_names.json")


def _ensure_stock_names_cache():
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


def cache_path(symbol: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}.json")


def read_cache(symbol: str) -> Optional[dict]:
    path = cache_path(symbol)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["from_cache"] = True
                return data
        except Exception:
            pass
    return None


def write_cache(symbol: str, data: dict):
    try:
        with open(cache_path(symbol), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


@app.get("/api/zygc")
def get_zygc(
    symbol: str = Query(..., description="股票代码，如 002081 或 600519"),
    refresh: bool = Query(False, description="是否强制刷新，绕过缓存"),
):
    try:
        symbol = normalize_symbol(symbol)

        # 非刷新模式下检查文件缓存
        if not refresh:
            cached = read_cache(symbol)
            if cached:
                return cached

        df = ak.stock_zygc_em(symbol=symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="未获取到数据，请检查股票代码")

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

        # 写入文件缓存
        write_cache(symbol, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@app.post("/api/analyze")
def analyze_zygc(data: dict):
    key = DEEPSEEK_API_KEY
    if not key:
        return JSONResponse({"analysis": "请先在 config.py 中配置 DEEPSEEK_API_KEY 以启用 AI 解读功能"}, status_code=200)

    symbol = data.get("symbol", "")
    latest_data = data.get("latestData", {})

    # 用股票代码和报告期生成缓存 key
    dates = sorted(set(r.get("报告日期", "") for cat in latest_data.values() for r in cat), reverse=True)
    cache_key = f"_zygc_{dates[0]}" if dates else "_zygc"

    def do_analyze():
        prompt = ZYGC_PROMPT_TEMPLATE.format(
            symbol=symbol,
            industry_data=json.dumps(latest_data.get("按行业分类", []), ensure_ascii=False, indent=2),
            product_data=json.dumps(latest_data.get("按产品分类", []), ensure_ascii=False, indent=2),
            region_data=json.dumps(latest_data.get("按地区分类", []), ensure_ascii=False, indent=2),
        )
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 500},
                timeout=30,
            )
            result = resp.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            return f"API 返回异常: {result}"
        except Exception as e:
            return f"AI 解读请求失败: {str(e)}"

    analysis = _cached_ai(symbol, cache_key, do_analyze)
    return {"analysis": analysis}


def _call_deepseek(prompt: str) -> str:
    key = DEEPSEEK_API_KEY
    if not key:
        return "请先在 config.py 中配置 DEEPSEEK_API_KEY 以启用 AI 解读功能"
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 600},
            timeout=30,
        )
        result = resp.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        return f"API 返回异常: {result}"
    except Exception as e:
        return f"AI 解读请求失败: {str(e)}"


_FINANCIAL_KEY_COLS = [
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


def _safe_val(row, col):
    v = row.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return round(float(v), 2)


def _pick_cols(df, cols):
    return {c: _safe_val(df, c) for c in cols if c in df.index}


def financial_cache_path(symbol: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}_financial.json")


def _ai_cache_path(symbol: str, suffix: str = "") -> str:
    return os.path.join(AI_CACHE_DIR, f"{symbol}{suffix}.json")


def _cached_ai(symbol: str, cache_key: str, prompt_fn) -> str:
    path = _ai_cache_path(symbol, cache_key)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)["result"]
        except Exception:
            pass
    result = prompt_fn()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"result": result}, f, ensure_ascii=False)
    except Exception:
        pass
    return result


@app.get("/api/financial")
def get_financial(
    symbol: str = Query(..., description="股票代码，如 002081 或 600519"),
    refresh: bool = Query(False, description="是否强制刷新"),
):
    try:
        symbol = normalize_symbol(symbol)
        code = extract_pure_code(symbol)
        name = get_stock_name(code)

        cache_file = financial_cache_path(symbol)
        if not refresh and os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["from_cache"] = True
                return data

        # 1. 利润表（报告期）
        profit_df = ak.stock_profit_sheet_by_report_em(symbol=symbol)
        profit_df = profit_df.sort_values("REPORT_DATE")
        profit_records = []
        for _, row in profit_df.iterrows():
            rec = {"REPORT_DATE": str(row["REPORT_DATE"])[:10]}
            for c in _FINANCIAL_KEY_COLS:
                if c in profit_df.columns:
                    rec[c] = _safe_val(row, c)
            profit_records.append(rec)

        # 2. 资产负债表（报告期）
        try:
            balance_df = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            balance_df = balance_df.sort_values("REPORT_DATE")
            balance_records = []
            for _, row in balance_df.iterrows():
                rec = {"REPORT_DATE": str(row["REPORT_DATE"])[:10]}
                for c in _BALANCE_KEY_COLS:
                    if c in balance_df.columns:
                        rec[c] = _safe_val(row, c)
                balance_records.append(rec)
        except Exception:
            balance_records = []

        # 3. 现金流量表（报告期）
        try:
            cash_df = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
            cash_df = cash_df.sort_values("REPORT_DATE")
            cash_records = []
            for _, row in cash_df.iterrows():
                rec = {"REPORT_DATE": str(row["REPORT_DATE"])[:10]}
                for c in _CASHFLOW_KEY_COLS:
                    if c in cash_df.columns:
                        rec[c] = _safe_val(row, c)
                cash_records.append(rec)
        except Exception:
            cash_records = []

        # 4. 财务摘要（同花顺）
        try:
            abstract = ak.stock_financial_abstract_ths(symbol=code)
            abstract_records = abstract.to_dict("records")
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

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财务数据失败: {str(e)}")


@app.post("/api/analyze/financial")
def analyze_financial(data: dict):
    symbol = data.get("symbol", "")
    code = data.get("code", "")
    name = data.get("name", "")

    latest_abstract = data.get("latestAbstract", {})
    latest_date = str(latest_abstract.get("报告期", ""))[:10] if latest_abstract.get("报告期") else ""

    # 缓存 key 基于最新报告期，有新数据时自动失效
    cache_key = f"_fin_{latest_date}" if latest_date else "_fin"

    def do_health():
        health_prompt = FINANCIAL_HEALTH_TEMPLATE
        profit_trend = data.get("profitTrend", [])
        balance_latest = data.get("balanceLatest", {})
        cash_latest = data.get("cashLatest", {})

        health_vars = {
            "symbol": symbol, "name": name,
            "latest_date": latest_date,
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
        }
        return _call_deepseek(health_prompt.format(**health_vars)) if health_prompt else "暂无模板"

    def do_growth():
        growth_prompt = FINANCIAL_GROWTH_TEMPLATE
        rd_data = data.get("rdData", [])
        business_growth = data.get("businessGrowth", {})
        asset_expansion = data.get("assetExpansion", [])
        profit_trend = data.get("profitTrend", [])

        growth_vars = {
            "symbol": symbol, "name": name,
            "rd_data": json.dumps(rd_data[-5:] if len(rd_data) > 5 else rd_data, ensure_ascii=False, indent=2),
            "business_growth": json.dumps(business_growth, ensure_ascii=False, indent=2),
            "asset_expansion": json.dumps(asset_expansion[-5:] if len(asset_expansion) > 5 else asset_expansion, ensure_ascii=False, indent=2),
            "profitability_trend": json.dumps(profit_trend[-5:] if len(profit_trend) > 5 else profit_trend, ensure_ascii=False, indent=2),
        }
        return _call_deepseek(growth_prompt.format(**growth_vars)) if growth_prompt else "暂无模板"

    health_result = _cached_ai(symbol, f"{cache_key}_health", do_health)
    growth_result = _cached_ai(symbol, f"{cache_key}_growth", do_growth)

    return {"health": health_result, "growth": growth_result}


@app.get("/api/zt/pool")
def get_zt_pool(
    date: str = Query("", description="日期 YYYYMMDD，默认今天"),
):
    """获取指定日期的涨停池数据"""
    try:
        target_date = date if date else datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=target_date)
        if df is None or df.empty:
            return {"stocks": [], "total": 0, "multi_board_total": 0, "date": target_date}

        stocks = df.to_dict("records")
        for s in stocks:
            for k in ("成交额", "流通市值", "总市值"):
                if k in s:
                    s[k] = float(s[k]) if s[k] else 0
            s["连板数"] = int(s.get("连板数", 0))

        multi = [s for s in stocks if s["连板数"] >= 2]
        return {
            "date": target_date,
            "total": len(stocks),
            "multi_board_total": len(multi),
            "stocks": stocks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取涨停数据失败: {str(e)}")


def _zygc_summary(records: list) -> str:
    if not records:
        return "未获取到主营构成数据"
    lines = []
    report_dates = sorted(set(r["报告日期"] for r in records), reverse=True)
    latest = report_dates[0] if report_dates else "未知"
    lines.append(f"最新报告期: {latest}")
    for cat_type in ("按行业分类", "按产品分类"):
        items = [r for r in records if r["报告日期"] == latest and r["分类类型"] == cat_type]
        if items:
            lines.append(f"\n{cat_type}:")
            for item in sorted(items, key=lambda x: x["收入比例"], reverse=True):
                lines.append(f"  {item['主营构成']}: 收入占比 {item['收入比例']}%, 毛利率 {item['毛利率']}%")
    return "\n".join(lines)


ZT_RISK_PROMPT = """你是一位专业的证券分析师。请对以下二板涨停股票进行**全面的风险评估**，结合其主营业务基本面和市场炒作逻辑，给出客观的风险提示。

======== 股票基本信息 ========
名称: {name}({code})
连板数: {board}连板
所属行业: {industry}

======== 主营构成（最新报告期） ========
{zygc}

======== 市场上涨逻辑（网络搜集） ========
{logic}

======== 分析要求 ========
请从以下几个维度进行风险评估（600字以内）：

1. **基本面风险**：主营业务的盈利能力、成长性、可持续性如何？是否有隐忧？
2. **炒作逻辑风险**：市场炒作的逻辑是否扎实？是否有被证伪的可能？
3. **估值风险**：连续大涨后估值是否合理？是否存在泡沫？
4. **资金面风险**：封板力度、换手率、炸板情况等反映的资金博弈状况
5. **综合风险评级**：给出 低风险/中低风险/中高风险/高风险 评级，并给出简要理由

请务必客观中立，不构成投资建议，仅为风险分析参考。"""


@app.post("/api/zt/analyze")
def analyze_zt_stock(data: dict):
    """对单只涨停股进行风险评估"""
    code = data.get("code", "")
    name = data.get("name", "")
    board = data.get("board", 1)
    industry = data.get("industry", "")
    logic = data.get("logic", "")
    symbol = normalize_symbol(code)

    # 获取主营构成
    try:
        df = ak.stock_zygc_em(symbol=symbol)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "报告日期": str(row["报告日期"]),
                    "分类类型": str(row["分类类型"]),
                    "主营构成": str(row["主营构成"]),
                    "主营收入": format_num(row["主营收入"]),
                    "收入比例": format_pct(row["收入比例"]),
                    "主营利润": format_num(row["主营利润"]),
                    "利润比例": format_pct(row["利润比例"]),
                    "毛利率": format_pct(row["毛利率"]),
                })
            zygc_text = _zygc_summary(records)
        else:
            zygc_text = "未获取到主营构成数据"
    except Exception:
        zygc_text = "获取主营构成失败"

    prompt = ZT_RISK_PROMPT.format(
        name=name, code=code, board=board,
        industry=industry, zygc=zygc_text, logic=logic,
    )

    analysis = _call_deepseek(prompt)

    return {
        "code": code,
        "name": name,
        "board": board,
        "zygc": zygc_text,
        "risk_analysis": analysis,
    }


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))
