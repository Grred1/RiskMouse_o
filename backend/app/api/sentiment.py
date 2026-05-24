"""
风险挖掘分析 API
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from ..core import (
    format_num,
    format_pct,
    normalize_symbol,
    extract_pure_code,
    load_prompts,
    read_cache,
    write_cache,
)
from ..core.data import akshare as data_akshare
from ..core.data import guba as data_guba
from ..agents import run_agent

router = APIRouter(prefix="/api", tags=["风险挖掘"])

PROMPTS = load_prompts()
ZT_RISK_PROMPT = PROMPTS.get("ZT_RISK_PROMPT", "")


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
            df_zt = data_akshare.get_zt_pool(date=target_date)
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
            df_lhb = data_akshare.get_lhb_detail()
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
    """AI 风险评分热门关注标的（含财务数据+量化评分）
    
    新版本使用 ZT_RISK_PROMPT，返回 JSON 结构化评分。
    """
    code = data.get("code", "")
    name = data.get("name", "")
    source = data.get("source", "")
    industry = data.get("industry", "")
    board = data.get("board", 0)

    symbol = normalize_symbol(code)
    pure_code = extract_pure_code(symbol)

    # 1. 获取主营构成
    try:
        df = data_akshare.get_stock_zygc(symbol=symbol)
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

    # 2. 获取财务摘要（作为 extra_info）
    extra_info = "暂无财务数据"
    try:
        abstract_df = data_akshare.get_financial_abstract(symbol=pure_code)
        if abstract_df is not None and not abstract_df.empty:
            abstract_records = abstract_df.to_dict("records")
            latest = abstract_records[-1] if abstract_records else {}
            if latest:
                lines = []
                keys_show = [
                    ("营业总收入", "营收"),
                    ("营业总收入同比增长率", "营收同比"),
                    ("净利润", "净利润"),
                    ("净利润同比增长率", "净利润同比"),
                    ("销售毛利率", "毛利率"),
                    ("销售净利率", "净利率"),
                    ("净资产收益率", "ROE"),
                    ("资产负债率", "资产负债率"),
                    ("每股经营现金流", "每股现金流"),
                    ("基本每股收益", "每股收益"),
                ]
                for key, label in keys_show:
                    val = latest.get(key, "")
                    if val is not None and str(val) not in ("", "--", "false", "False"):
                        lines.append(f"  {label}: {val}")
                if lines:
                    extra_info = "近三年财务摘要:\n" + "\n".join(lines)
    except Exception:
        pass

    # 3. 获取股吧数据（作为 logic — 市场上涨逻辑）
    logic = _fetch_guba_logic(pure_code, symbol)

    # 4. 调用 LLM
    prompt = ZT_RISK_PROMPT.format(
        name=name,
        code=code,
        board=board,
        industry=industry,
        zygc=zygc_text,
        logic=logic,
        extra_info=extra_info,
    )

    raw_analysis = run_agent("analyze_sentiment", {
        "prompt_text": prompt,
        "code": code,
    })

    # 5. 尝试解析 JSON
    scores = {}
    overall_conclusion = ""
    final_conclusion = raw_analysis
    parse_ok = False

    try:
        json_str = _extract_json(raw_analysis)
        if json_str:
            parsed = json.loads(json_str)
            scores = parsed.get("scores", {})
            overall_conclusion = parsed.get("overall_conclusion", "")
            final_conclusion = parsed.get("final_conclusion", raw_analysis)
            parse_ok = True
    except Exception:
        pass

    # 构建维度标签映射
    dimension_labels = {
        "logic_match": "逻辑匹配度",
        "financial_health": "财务健康度",
        "valuation_bubble": "估值泡沫度",
        "capital_risk": "资金面风险",
        "governance_risk": "公司治理风险",
    }

    # 将 scores 转为前端友好格式
    score_list = []
    for key, val in scores.items():
        label = dimension_labels.get(key, key)
        score_list.append({
            "key": key,
            "label": label,
            "score": int(val),
            "max": 5,
        })

    return {
        "code": code,
        "name": name,
        "source": source,
        "board": board,
        "parse_ok": parse_ok,
        "overall_conclusion": overall_conclusion,
        "scores": score_list,
        "scores_raw": scores,
        "final_conclusion": final_conclusion,
        "risk_analysis": raw_analysis,
    }


def _extract_json(text: str) -> str | None:
    """从 LLM 回复中提取第一个 JSON 块（兼容 markdown 代码块）"""
    # 先尝试去掉 ```json ... ``` 包裹
    cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start:end + 1]
    # 回退到原始文本
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return None


def _fetch_guba_logic(pure_code: str, symbol: str) -> str:
    """获取股吧数据，组装成市场上涨逻辑文本"""
    return data_guba.fetch_stock_logic(pure_code, symbol)


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
            df_kw = data_akshare.get_hot_keywords(symbol=symbol)
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
            df_latest = data_akshare.get_hot_rank_latest(symbol=symbol)
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
            df_relate = data_akshare.get_hot_rank_relate(symbol=symbol)
            if df_relate is not None and not df_relate.empty:
                for _, row in df_relate.iterrows():
                    relate_stocks.append({
                        "code": str(row.get("相关股票代码", "")),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                    })
        except Exception:
            pass

        # 4. 抓取股吧帖子标题
        post_titles = data_guba.scrape_stock_posts(pure_code)

        # 5. LLM 分析市场逻辑
        kw_text = "\n".join([f"{k['keyword']}: 热度 {k['hotness']}" for k in keywords_data[:10]]) if keywords_data else "暂无关键词数据"
        rank_text = (
            f"当前人气排名: {rank_data.get('rank', 'N/A')}\n"
            f"总参评股票数: {rank_data.get('marketAllCount', 'N/A')}\n"
            f"排名变动(与昨日): {rank_data.get('rankChange', 'N/A')}"
        )
        post_text = "\n".join([f"- {t['title']}" for t in post_titles[:40]]) if post_titles else "暂无帖子数据"

        analysis = run_agent("analyze_guba", {
            "prompt_text": "",  # 让 Agent 自己从文件加载 prompt
            "code": pure_code,
            "name": code,
            "keywords": kw_text,
            "rank_data": rank_text,
            "post_titles": post_text,
        })

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
