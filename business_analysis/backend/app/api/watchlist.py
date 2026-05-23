"""
自选风控 API
持久化自选股 + 规则算法四维评分 + 词云 + 新闻链接 + AI 解读
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from datetime import datetime

import akshare as ak
from fastapi import APIRouter, HTTPException

from ..core import (
    CACHE_DIR,
    AI_CACHE_DIR,
    PROMPTS_DIR,
    call_llm,
    cached_llm_call,
    get_stock_name,
    normalize_symbol,
    extract_pure_code,
)
from .. import risk_engine
from .. import db as watchlist_db

router = APIRouter(prefix="/api/watchlist", tags=["自选风控"])

# 加载 watchlist AI 提示词
_WATCHLIST_RISK_PROMPT = ""
_prompt_path = os.path.join(PROMPTS_DIR, "watchlist_risk.txt")
if os.path.exists(_prompt_path):
    with open(_prompt_path, "r", encoding="utf-8") as _f:
        _WATCHLIST_RISK_PROMPT = _f.read()


# ── 图片识别 ────────────────────────────────────────────────────

_VISION_PROMPT = (
    "请识别图片中所有A股股票代码（6位数字，以0、3、6、8、4开头）。"
    "仅输出代码列表，用英文逗号分隔，不要包含其他文字。"
    "如果没有找到任何股票代码，请输出：无"
)


def _extract_codes_from_image(image_base64: str, mime_type: str = "image/png") -> tuple[list, str]:
    """
    从截图中提取6位股票代码，使用 easyocr 本地识别。
    返回 (codes, method)，method 为 "easyocr" 或 "unavailable"。
    """
    try:
        import easyocr
    except ImportError:
        return [], "unavailable"
    try:
        import numpy as np
        from PIL import Image
        img_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_bytes))
        img_array = np.array(img)
        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
        results = reader.readtext(img_array, detail=0)
        text = " ".join(results)
        codes = re.findall(r'\b\d{6}\b', text)
        codes = [c for c in codes if c[0] in ('0', '3', '6', '8', '4')]
        return list(dict.fromkeys(codes)), "easyocr"
    except Exception:
        return [], "easyocr"


@router.post("/parse-image")
def parse_watchlist_image(data: dict):
    """从截图中识别股票代码列表（Qwen-VL 优先，easyocr 回退）"""
    image_b64 = data.get("image", "")
    mime_type = data.get("mime_type", "image/png")
    if not image_b64:
        raise HTTPException(status_code=400, detail="缺少图片数据")

    codes, method = _extract_codes_from_image(image_b64, mime_type)

    ocr_available = method != "unavailable"
    return {"codes": codes, "ocr_available": ocr_available, "method": method}


# ── 持久化 CRUD ──────────────────────────────────────────────────

@router.get("/list")
def api_watchlist_list():
    """获取所有已保存的自选股"""
    return {"stocks": watchlist_db.get_watchlist()}


@router.post("/add")
def api_watchlist_add(data: dict):
    """添加股票到自选股列表"""
    code = data.get("code", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="缺少股票代码")
    try:
        symbol = normalize_symbol(code)
        pure = extract_pure_code(symbol)
        name = get_stock_name(pure)
        result = watchlist_db.add_stock(pure, name)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["msg"])
        return {"code": pure, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remove")
def api_watchlist_remove(data: dict):
    """从自选股列表移除"""
    code = data.get("code", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="缺少股票代码")
    watchlist_db.remove_stock(code)
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
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        font_path = next((f for f in font_candidates if os.path.exists(f)), None)

        wc = WordCloud(
            font_path=font_path,
            width=400, height=220,
            background_color="white",
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
        df = ak.stock_news_em(symbol=code)
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
        df = ak.stock_comments_em(symbol=code)
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

        # 2f. AI 解读（带磁盘缓存，与财报风险模块保持一致）
        brief = "暂无 AI 解读"
        if _WATCHLIST_RISK_PROMPT:
            news_titles_str = "\n".join(
                f"- {n['title']}" for n in news_list[:8]
            ) or "暂无新闻"
            today = datetime.now().strftime("%Y-%m-%d")
            cache_key = f"watchlist_{today}"
            try:
                prompt = _WATCHLIST_RISK_PROMPT.format(
                    name=name or code, code=code,
                    fundamental_stars=f_result["score"],
                    fundamental_basis=f_result["basis"],
                    news_stars=n_result["score"],
                    news_basis=n_result["basis"],
                    risk_stars=r_result["score"],
                    risk_basis=r_result["basis"],
                    overall_stars=o_result["score"],
                    news_titles=news_titles_str,
                )
                result_ai = cached_llm_call(code, cache_key, lambda: call_llm(prompt, max_tokens=200))
                # 过滤掉 API 调用失败时返回的错误字符串
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
