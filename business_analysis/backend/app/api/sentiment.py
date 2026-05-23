"""
风险挖掘分析 API
"""
from __future__ import annotations

import math
from datetime import datetime

import akshare as ak
from fastapi import APIRouter, HTTPException, Query

from ..core import (
    format_num,
    format_pct,
    normalize_symbol,
    load_prompts,
    call_llm,
    cached_llm_call,
    read_cache,
    write_cache,
)

router = APIRouter(prefix="/api", tags=["风险挖掘"])

# 加载提示词
PROMPTS = load_prompts()
RISK_ANALYSIS_PROMPT = PROMPTS.get("RISK_ANALYSIS", """
你是一位专业的证券风险分析师。请对以下热门关注标的进行**全面的风险评估**。

======== 基本信息 ========
名称: {name}({code})
关注来源: {source}
所属行业: {industry}

======== 主营构成（最新报告期） ========
{zygc}

======== 市场关注点 ========
{attention}

======== 分析要求 ========
请从以下几个维度进行风险评估（500字以内）：

1. **基本面风险**：主营业务的盈利能力、成长性、可持续性如何？是否有隐忧？
2. **舆情风险**：市场关注度是否理性？是否存在过度炒作风险？
3. **估值风险**：当前估值是否合理？是否存在泡沫？
4. **潜在风险因素**：有哪些值得关注的潜在风险点？
5. **综合风险评级**：给出 低风险/中低风险/中高风险/高风险 评级，并给出简要理由

请务必客观中立，不构成投资建议，仅为风险分析参考。
""")


@router.get("/risk/pool")
def get_risk_pool(
    date: str = Query("", description="日期 YYYYMMDD，默认最新"),
):
    """获取热门关注池数据（涨停板 + 龙虎榜）"""
    try:
        # 1. 获取涨停池数据
        target_date = date if date else datetime.now().strftime("%Y%m%d")
        zt_stocks = []
        try:
            df_zt = ak.stock_zt_pool_em(date=target_date)
            if df_zt is not None and not df_zt.empty:
                for _, row in df_zt.iterrows():
                    zt_stocks.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "source": "涨停",
                        "source_label": "🟣涨停",
                        "board": int(row.get("连板数", 0) or 0),
                        "industry": str(row.get("所属行业", "") or ""),
                        "turnover": float(row.get("换手率", 0) or 0),
                        "amount": float(row.get("成交额", 0) or 0),
                        "market_cap": float(row.get("流通市值", 0) or 0),
                    })
        except Exception:
            pass  # 涨停数据获取失败不影响整体

        # 2. 获取龙虎榜数据
        lhb_stocks = []
        try:
            df_lhb = ak.stock_lhb_detail_em()
            if df_lhb is not None and not df_lhb.empty:
                # 按代码去重，取最新一条
                seen = {}
                for _, row in df_lhb.iterrows():
                    code = str(row.get("代码", ""))
                    if code not in seen:
                        net_amount = float(row.get("龙虎榜净买额", 0) or 0)
                        seen[code] = {
                            "code": code,
                            "name": str(row.get("名称", "")),
                            "source": "龙虎榜",
                            "source_label": "🔥人气",
                            "board": 0,
                            "industry": "",  # 龙虎榜数据中没有行业字段
                            "turnover": float(row.get("换手率", 0) or 0),
                            "amount": float(row.get("龙虎榜成交额", 0) or 0),
                            "market_cap": float(row.get("流通市值", 0) or 0),
                            "net_amount": net_amount,  # 龙虎榜特有
                            "reason": str(row.get("上榜原因", "") or ""),  # 龙虎榜特有
                            "change_pct": float(row.get("涨跌幅", 0) or 0),  # 龙虎榜特有
                        }
                lhb_stocks = list(seen.values())
        except Exception:
            pass  # 龙虎榜数据获取失败不影响整体

        # 3. 合并数据
        all_stocks = zt_stocks + lhb_stocks

        # 统计
        total = len(all_stocks)
        high_risk_count = 0  # 后续可由 AI 评估填充

        # 清理 NaN 值
        def clean_stock(stock):
            cleaned = {}
            for k, v in stock.items():
                if isinstance(v, float) and (v != v):  # NaN check
                    cleaned[k] = 0
                else:
                    cleaned[k] = v
            return cleaned

        # 限制返回数量：涨停5个 + 龙虎榜5个
        zt_limited = all_stocks[:5]
        lhb_limited = all_stocks[5:10]
        limited_stocks = zt_limited + lhb_limited

        return {
            "date": target_date,
            "total": total,
            "zt_count": len(zt_stocks),
            "lhb_count": len(lhb_stocks),
            "stocks": [clean_stock(s) for s in limited_stocks],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取热门关注池失败: {str(e)}")


@router.post("/risk/analyze")
def analyze_risk_stock(data: dict):
    """AI 风险评估热门关注标的"""
    code = data.get("code", "")
    name = data.get("name", "")
    source = data.get("source", "")  # 涨停 / 龙虎榜
    industry = data.get("industry", "")
    attention = data.get("attention", "")
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

    prompt = RISK_ANALYSIS_PROMPT.format(
        name=name,
        code=code,
        source=source,
        industry=industry,
        zygc=zygc_text,
        attention=attention,
    )

    analysis = call_llm(prompt, max_tokens=600)

    return {
        "code": code,
        "name": name,
        "source": source,
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
            for item in sorted(items, key=lambda x: x["收入比例"], reverse=True)[:10]:
                lines.append(f"  {item['主营构成']}: 收入占比 {item['收入比例']}%, 毛利率 {item['毛利率']}%")
    return "\n".join(lines)


GUBA_ANALYSIS_PROMPT = """
你是一位专业的股吧舆情分析师。请根据以下从东方财富股吧获取的数据，进行市场情绪分析。

======== 股票信息 ========
名称: {name}({code})

======== 股吧热门关键词 ========
{keywords}

======== 人气数据 ========
{rank_data}

======== 最新股吧帖子标题 ========
{post_titles}

======== 分析要求 ========
请从以下维度进行分析（300字以内）：

1. **市场核心逻辑**：股民们最关注的逻辑是什么？市场在交易什么预期？
2. **情绪判断**：当前市场情绪偏多还是偏空？情绪是否极端？
3. **主要分歧点**：多空双方的核心分歧在哪里？

请务必基于数据客观分析，不构成投资建议。
"""


def _scrape_guba_posts(symbol: str) -> list:
    """从东方财富股吧页面抓取帖子标题（多页爬取）"""
    import re
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://guba.eastmoney.com/",
    }
    all_titles = []
    seen = set()
    for page in range(1, 4):
        try:
            url = f"https://guba.eastmoney.com/list,{symbol}_{page}.html"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                break
            titles = re.findall(r'"post_title"\s*:\s*"([^"]+)"', r.text)
            for t in titles:
                t = t.strip()
                if len(t) > 4 and t not in seen and not any(kw in t for kw in ["反诈", "网警", "举报"]):
                    seen.add(t)
                    all_titles.append(t)
        except Exception:
            break
    return all_titles[:90]


def _clean_nan(obj):
    """递归清理 NaN/Infinity 值，转为 None"""
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_nan(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


@router.get("/risk/guba")
def get_guba_data(
    code: str = Query(..., description="股票代码"),
    refresh: bool = Query(False, description="是否强制刷新"),
):
    """获取股吧数据（热门关键词+人气排名+帖子分析）"""
    try:
        code = code.strip().upper()
        if code.startswith(("SH", "SZ", "BJ")):
            symbol = code
        else:
            if code.startswith(("6", "5")):
                symbol = f"SH{code}"
            elif code.startswith(("0", "3")):
                symbol = f"SZ{code}"
            else:
                symbol = f"SZ{code}"

        pure_code = code.lstrip("SH").lstrip("SZ").lstrip("BJ")

        # 检查缓存
        if not refresh:
            cached = read_cache(pure_code, module="guba")
            if cached:
                cached["from_cache"] = True
                return _clean_nan(cached)

        # 1. 热门关键词（来自股吧）
        keywords_data = []
        try:
            df_kw = ak.stock_hot_keyword_em(symbol=symbol)
            if df_kw is not None and not df_kw.empty:
                for _, row in df_kw.iterrows():
                    keywords_data.append({
                        "keyword": str(row.get("概念名称", "")),
                        "hotness": int(row.get("热度", 0) or 0),
                    })
        except Exception:
            pass

        # 2. 最新排名
        rank_data = {}
        try:
            df_latest = ak.stock_hot_rank_latest_em(symbol=symbol)
            if df_latest is not None and not df_latest.empty:
                for _, row in df_latest.iterrows():
                    val = row["value"]
                    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                        continue
                    rank_data[str(row["item"])] = str(val)
        except Exception:
            pass

        # 3. 相关股票
        relate_stocks = []
        try:
            df_relate = ak.stock_hot_rank_relate_em(symbol=symbol)
            if df_relate is not None and not df_relate.empty:
                for _, row in df_relate.iterrows():
                    relate_stocks.append({
                        "code": str(row.get("相关股票代码", "")),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                    })
        except Exception:
            pass

        # 4. 抓取股吧帖子标题
        post_titles = _scrape_guba_posts(pure_code)

        # 5. LLM 分析市场逻辑
        def do_analyze():
            kw_text = "\n".join([f"{k['keyword']}: 热度 {k['hotness']}" for k in keywords_data[:10]]) if keywords_data else "暂无关键词数据"
            rank_text = (
                f"当前人气排名: {rank_data.get('rank', 'N/A')}\n"
                f"总参评股票数: {rank_data.get('marketAllCount', 'N/A')}\n"
                f"排名变动(与昨日): {rank_data.get('rankChange', 'N/A')}"
            )
            post_text = "\n".join([f"- {t}" for t in post_titles[:40]]) if post_titles else "暂无帖子数据"

            prompt = GUBA_ANALYSIS_PROMPT.format(
                name=code,
                code=code,
                keywords=kw_text,
                rank_data=rank_text,
                post_titles=post_text,
            )
            return call_llm(prompt, max_tokens=500)

        analysis = cached_llm_call(pure_code, "_guba_analysis", do_analyze)

        # 6. 统计数据量
        total_data_points = (
            len(keywords_data)
            + (1 if rank_data else 0)
            + len(relate_stocks)
            + len(post_titles)
        )

        result = {
            "code": code,
            "symbol": symbol,
            "keywords": keywords_data[:10],
            "rank": rank_data,
            "relate_stocks": relate_stocks[:5],
            "post_titles": post_titles[:60],
            "analysis": analysis,
            "stats": {
                "total_data_points": total_data_points,
                "keyword_count": len(keywords_data),
                "post_count": len(post_titles),
                "relate_count": len(relate_stocks),
                "rank_days": sum(1 for _ in rank_data),
            },
            "from_cache": False,
        }

        # 写入缓存
        write_cache(pure_code, _clean_nan(result), module="guba")

        return _clean_nan(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取股吧数据失败: {str(e)}")
