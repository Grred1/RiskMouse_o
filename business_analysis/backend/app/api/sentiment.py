"""
热门关注 - 风险挖掘 API
整合涨停板和市场人气股数据，进行风险分析
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import akshare as ak
from fastapi import APIRouter, HTTPException, Query

from ..core import (
    format_num,
    format_pct,
    normalize_symbol,
    load_prompts,
    call_llm,
)

router = APIRouter(prefix="/api", tags=["风险挖掘"])

# 加载提示词
PROMPTS = load_prompts()
RISK_ANALYSIS_PROMPT = PROMPTS.get("RISK_ANALYSIS_PROMPT", """你是一位专业的风险分析师。请对以下热门关注标的进行风险评估。

======== 基本信息 ========
名称: {name}({code})
关注来源: {source}
所属行业: {industry}

======== 主营构成（最新报告期） ========
{zygc}

======== 分析要求 ========
请从以下维度评估风险（600字以内）：

1. **基本面风险**：主营业务的盈利能力、成长性、可持续性如何？
2. **舆情风险**：市场关注度是否有负面情绪聚集？
3. **经营风险**：主营业务是否面临竞争或经营压力？
4. **综合风险评级**：🔴高风险 / 🟡中风险 / 🟢低风险

请给出简洁、客观的风险评估，突出关键风险点。
""")


@router.get("/hot/pool")
def get_hot_pool(
    date: str = Query("", description="日期 YYYYMMDD，默认今天"),
):
    """获取热门关注标的池（涨停板 + 市场人气股）"""
    try:
        target_date = date if date else datetime.now().strftime("%Y%m%d")
        
        stocks = []
        
        # 1. 获取涨停板数据
        try:
            df_zt = ak.stock_zt_pool_em(date=target_date)
            if df_zt is not None and not df_zt.empty:
                for _, row in df_zt.iterrows():
                    stocks.append({
                        "代码": str(row.get("代码", "")),
                        "名称": str(row.get("名称", "")),
                        "涨跌幅": float(row.get("涨跌幅", 0) or 0),
                        "最新价": float(row.get("最新价", 0) or 0),
                        "成交额": float(row.get("成交额", 0) or 0),
                        "换手率": float(row.get("换手率", 0) or 0),
                        "流通市值": float(row.get("流通市值", 0) or 0),
                        "总市值": float(row.get("总市值", 0) or 0),
                        "所属行业": str(row.get("所属行业", "")),
                        "关注热度": int(row.get("连板数", 1) or 1),  # 连板数作为热度
                        "关注来源": "涨停板",
                        "异动类型": "涨停",
                    })
        except Exception as e:
            print(f"涨停池获取失败: {e}")

        # 2. 获取市场人气股（尝试东方财富人气榜）
        try:
            df_hot = ak.stock_hot_rank_em()
            if df_hot is not None and not df_hot.empty:
                # 取前50名人气股
                for _, row in df_hot.head(50).iterrows():
                    code = str(row.get("代码", ""))
                    # 避免重复（与涨停板去重）
                    if not any(s["代码"] == code for s in stocks):
                        stocks.append({
                            "代码": code,
                            "名称": str(row.get("名称", "")),
                            "涨跌幅": float(row.get("涨跌幅", 0) or 0),
                            "最新价": float(row.get("最新价", 0) or 0),
                            "成交额": float(row.get("成交额", 0) or 0),
                            "换手率": float(row.get("换手率", 0) or 0),
                            "流通市值": float(row.get("流通市值", 0) or 0),
                            "总市值": float(row.get("总市值", 0) or 0),
                            "所属行业": str(row.get("所属行业", "")),
                            "关注热度": 1,  # 人气股默认热度为1
                            "关注来源": "人气榜",
                            "异动类型": "人气",
                        })
        except Exception as e:
            print(f"人气榜获取失败: {e}")

        # 3. 按关注热度排序
        stocks.sort(key=lambda x: x.get("关注热度", 0), reverse=True)

        # 4. 统计
        zt_count = len([s for s in stocks if s["关注来源"] == "涨停板"])
        hot_count = len([s for s in stocks if s["关注来源"] == "人气榜"])

        return {
            "date": target_date,
            "total": len(stocks),
            "zt_count": zt_count,
            "hot_count": hot_count,
            "stocks": stocks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取热门数据失败: {str(e)}")


@router.post("/hot/analyze")
def analyze_hot_stock(data: dict):
    """AI 风险分析热门标的"""
    code = data.get("代码", data.get("code", ""))
    name = data.get("名称", data.get("name", ""))
    source = data.get("关注来源", "未知")
    industry = data.get("所属行业", "")
    heat_level = data.get("关注热度", 1)
    symbol = normalize_symbol(code)

    # 获取主营构成
    try:
        df = ak.stock_zygc_em(symbol=symbol)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "报告日期": str(row.get("报告日期", "")),
                    "分类类型": str(row.get("分类类型", "")),
                    "主营构成": str(row.get("主营构成", "")),
                    "主营收入": format_num(row.get("主营收入")),
                    "收入比例": format_pct(row.get("收入比例")),
                    "主营利润": format_num(row.get("主营利润")),
                    "利润比例": format_pct(row.get("利润比例")),
                    "毛利率": format_pct(row.get("毛利率")),
                })
            zygc_text = _zygc_summary(records)
        else:
            zygc_text = "未获取到主营构成数据"
    except Exception:
        zygc_text = "获取主营构成失败"

    # 热度等级描述
    heat_desc = "高" if heat_level >= 3 else ("中" if heat_level >= 2 else "一般")

    prompt = RISK_ANALYSIS_PROMPT.format(
        name=name,
        code=code,
        source=source,
        industry=industry,
        heat_level=heat_desc,
        zygc=zygc_text,
    )

    analysis = call_llm(prompt, max_tokens=600)

    return {
        "code": code,
        "name": name,
        "source": source,
        "industry": industry,
        "heat_level": heat_level,
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
