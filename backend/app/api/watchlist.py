"""
自选风控 API
持久化自选股 + 规则算法四维评分 + 词云 + 新闻链接 + AI 解读
"""
from __future__ import annotations

from ..core.font_utils import find_chinese_font

import base64
import io
import json
import os
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from ..core import (
    CACHE_DIR,
    get_stock_name,
    normalize_symbol,
    extract_pure_code,
)
from ..core.data import akshare as data_akshare
from ..agents import run_agent
from ..auth import get_current_user
from .. import risk_engine
from .. import db as watchlist_db

router = APIRouter(prefix="/api/watchlist", tags=["自选风控"])


# ── 持久化 CRUD ──────────────────────────────────────────────────

@router.get("/list")
def api_watchlist_list(user: dict = Depends(get_current_user)):
    """获取当前用户的自选股"""
    return {"stocks": watchlist_db.get_watchlist(user["id"])}


@router.post("/add")
def api_watchlist_add(data: dict, user: dict = Depends(get_current_user)):
    """添加股票到当前用户的自选股"""
    code = data.get("code", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="缺少股票代码")
    try:
        symbol = normalize_symbol(code)
        pure = extract_pure_code(symbol)
        name = get_stock_name(pure)
        result = watchlist_db.add_stock(user["id"], pure, name)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["msg"])
        return {"code": pure, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sparkline/{code}")
def api_watchlist_sparkline(code: str):
    """获取近20个交易日收盘价走势（当日缓存）"""
    from datetime import timedelta
    code = code.strip()
    if not code.isdigit():
        return {"prices": [], "is_up": None}
    today = datetime.now().strftime("%Y%m%d")
    cache_file = os.path.join(CACHE_DIR, f"sparkline_{code}_{today}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        df = data_akshare.get_stock_history(
            symbol=code, period="daily",
            start_date=start_date, end_date=today, adjust="qfq"
        )
        if df is None or df.empty:
            result = {"prices": [], "is_up": None}
        else:
            prices = df["收盘"].tail(20).round(2).tolist()
            is_up = len(prices) >= 2 and prices[-1] > prices[0]
            result = {"prices": prices, "is_up": is_up}
        with open(cache_file, "w") as f:
            json.dump(result, f)
        return result
    except Exception:
        return {"prices": [], "is_up": None}


@router.post("/remove")
def api_watchlist_remove(data: dict, user: dict = Depends(get_current_user)):
    """从当前用户的自选股移除"""
    code = data.get("code", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="缺少股票代码")
    watchlist_db.remove_stock(user["id"], code)
    return {"ok": True}


# ── 词云 + 新闻 + 评论 辅助函数 ────────────────────────────────

def _generate_wordcloud(texts: list) -> str:
    """jieba 分词 → wordcloud → base64 PNG；失败返回空字符串"""
    try:
        import jieba
        from wordcloud import WordCloud
        stopwords = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "还",
            "月", "日", "年", "元", "亿", "万", "股", "市", "股票", "公司",
            "表示", "显示", "报告", "数据", "预计", "相关", "进行", "发展",
        }
        combined = " ".join(texts)
        words = jieba.cut(combined)
        filtered = [w for w in words if len(w) >= 2 and w not in stopwords]
        text_in = " ".join(filtered)

        font_candidates = [
            # macOS
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            # Windows
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        font_path = None
        for f in font_candidates:
            if os.path.exists(f):
                font_path = f
                break

        # 如果系统路径没找到，用智能查找（matplotlib / 项目内嵌 / 自动下载）
        if font_path is None:
            logger = __import__('logging').getLogger(__name__)
            font_path = find_chinese_font()

        wc = WordCloud(
            font_path=font_path,
            width=400, height=220,
            background_color=None,
            mode="RGBA",
            max_words=60,
            collocations=False,
        )
        wc.generate(text_in or "暂无内容")
        buf = io.BytesIO()
        wc.to_image().save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


def _fetch_news_with_url(code: str) -> list:
    """获取带 URL 的新闻列表（最多15条），带当日缓存"""
    today = datetime.now().strftime("%Y%m%d")
    cache_file = os.path.join(CACHE_DIR, f"news_full_{code}_{today}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        df = data_akshare.get_stock_news(symbol=code)
        if df is None or df.empty:
            return []
        url_col = next((c for c in ["新闻链接", "url", "link"] if c in df.columns), None)
        title_col = next((c for c in ["新闻标题", "title", "标题"] if c in df.columns), None)
        date_col = next((c for c in ["发布时间", "date", "时间"] if c in df.columns), None)
        results = []
        for _, row in df.head(15).iterrows():
            results.append({
                "title": str(row[title_col]) if title_col else "",
                "url": str(row[url_col]) if url_col else "",
                "date": str(row[date_col])[:10] if date_col else "",
            })
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False)
        return results
    except Exception:
        return []


def _fetch_comments(code: str) -> list:
    """获取东方财富股吧评论（最多50条），用于词云"""
    today = datetime.now().strftime("%Y%m%d")
    cache_file = os.path.join(CACHE_DIR, f"comments_{code}_{today}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        df = data_akshare.get_stock_comments(symbol=code)
        if df is None or df.empty:
            return []
        text_col = next((c for c in ["评论内容", "content", "内容", "正文"] if c in df.columns), None)
        if not text_col:
            return []
        texts = df[text_col].head(50).astype(str).tolist()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(texts, f, ensure_ascii=False)
        return texts
    except Exception:
        return []


# ── 完整详情分析 ─────────────────────────────────────────────────

@router.get("/detail/{code}")
def api_watchlist_detail(code: str):
    """
    返回单只股票完整分析：算法四维评分 + 打分依据 + 带 URL 新闻 + 词云 + AI 解读
    当日缓存命中直接返回，否则重新分析后存库。
    """
    code = code.strip().upper().lstrip("SH").lstrip("SZ").lstrip("BJ")
    if not code or not code.isdigit():
        raise HTTPException(status_code=400, detail="无效股票代码")

    # 1. 当日缓存命中直接返回
    cached = watchlist_db.get_analysis(code)
    if cached:
        if not cached.get("name"):
            cached["name"] = get_stock_name(code) or code
        return cached

    # 2. 重新分析
    try:
        symbol = normalize_symbol(code)
        name = get_stock_name(code)

        # 2a. 财务摘要
        fin_abstract = {}
        try:
            abstracts = ak.stock_financial_abstract_ths(symbol=code).to_dict("records")
            if abstracts:
                fin_abstract = abstracts[-1]
        except Exception:
            pass

        # 2b. 新闻（带 URL）
        time.sleep(1)
        news_list = _fetch_news_with_url(code)

        # 2c. 股吧评论（词云用）
        time.sleep(1)
        comments = _fetch_comments(code)

        # 2d. 算法四维评分
        f_result = risk_engine.score_fundamental(fin_abstract)
        n_result = risk_engine.score_news(news_list)
        r_result = risk_engine.score_risk(f_result, n_result, fin_abstract)
        o_result = risk_engine.score_overall(f_result, n_result, r_result)

        # 2e. 词云
        wc_texts = [item["title"] for item in news_list] + comments
        wordcloud_b64 = _generate_wordcloud(wc_texts)

        # 2f. AI 解读（通过 Agent 调用，自动处理缓存）
        brief = "暂无 AI 解读"
        try:
            news_titles_str = "\n".join(
                f"- {n['title']}" for n in news_list[:8]
            ) or "暂无新闻"
            today = datetime.now().strftime("%Y-%m-%d")
            result_ai = run_agent("analyze_watchlist_risk", {
                "name": name or code,
                "code": code,
                "date": today,
                "fundamental_stars": str(f_result["score"]),
                "fundamental_basis": f_result["basis"],
                "news_stars": str(n_result["score"]),
                "news_basis": n_result["basis"],
                "risk_stars": str(r_result["score"]),
                "risk_basis": r_result["basis"],
                "overall_stars": str(o_result["score"]),
                "news_titles": news_titles_str,
            })
            if result_ai and not any(result_ai.startswith(p) for p in (
                "AI 调用失败", "DeepSeek API Key", "DEEPSEEK_API_KEY", "未配置"
            )):
                brief = result_ai
        except Exception:
            pass

        result = {
            "code": code,
            "name": name or code,
            "fundamental_stars": f_result["score"],
            "news_stars": n_result["score"],
            "risk_stars": r_result["score"],
            "overall_stars": o_result["score"],
            "brief": brief,
            "score_basis": {
                "fundamental": f_result["basis"],
                "news": n_result["basis"],
                "risk": r_result["basis"],
                "overall": o_result["basis"],
            },
            "news_json": news_list[:8],
            "wordcloud_b64": wordcloud_b64,
            "updated_at": datetime.now().isoformat(),
        }

        # 只有 AI 解读成功时才缓存到 SQLite（避免错误结果被持久化）
        if brief != "暂无 AI 解读":
            watchlist_db.save_analysis(code, result)
        watchlist_db.update_stock_name(code, name or code)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


# ── 风险日记 API ─────────────────────────────────────────────────

@router.get("/diary/list")
def api_diary_list(code: str = None, user: dict = Depends(get_current_user)):
    """获取当前用户的风险日记，可按股票代码筛选"""
    return {"diaries": watchlist_db.get_diaries(user["id"], code)}


@router.post("/diary/add")
def api_diary_add(data: dict, user: dict = Depends(get_current_user)):
    """新增风险日记"""
    result = watchlist_db.add_diary(user["id"], data)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["msg"])
    return result


@router.post("/diary/delete")
def api_diary_delete(data: dict, user: dict = Depends(get_current_user)):
    """删除风险日记"""
    diary_id = data.get("id")
    if not diary_id:
        raise HTTPException(status_code=400, detail="缺少日记ID")
    watchlist_db.delete_diary(user["id"], diary_id)
    return {"ok": True}
