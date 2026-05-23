"""
舆论风险分析 API
"""
from __future__ import annotations

from datetime import datetime

import akshare as ak
from fastapi import APIRouter, HTTPException, Query

from ..core import (
    format_num,
    format_pct,
    normalize_symbol,
    load_prompts,
    call_llm,
)

router = APIRouter(prefix="/api", tags=["舆论风险"])

# 加载提示词
PROMPTS = load_prompts()
ZT_RISK_PROMPT = PROMPTS.get("ZT_RISK_PROMPT", "")


@router.get("/zt/pool")
def get_zt_pool(
    date: str = Query("", description="日期 YYYYMMDD，默认今天"),
):
    """获取涨停池数据"""
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


@router.post("/zt/analyze")
def analyze_zt_stock(data: dict):
    """AI 风险评估涨停股"""
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
        name=name,
        code=code,
        board=board,
        industry=industry,
        zygc=zygc_text,
        logic=logic,
    )

    analysis = call_llm(prompt, max_tokens=600)

    return {
        "code": code,
        "name": name,
        "board": board,
        "zygc": zygc_text,
        "risk_analysis": analysis,
    }


def _zygc_summary(records: list) -> str:
    """生成主营构成摘要"""
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
