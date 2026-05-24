"""
小老鼠 AI Agent — 自动网上冲浪 + 股吧真伪鉴定 + 自选股巡检
完全独立模块，不依赖其他 API 路由
"""
from __future__ import annotations

import json
import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText

from fastapi import APIRouter
from pydantic import BaseModel

from ..core import (
    call_llm,
    call_coze_agent,
    verify_news,
    normalize_symbol,
    get_stock_name,
    cached_llm_call,
    cache_rag,
    usage_doc,
    emotional_first_aid,
    is_emotional,
    risk_education,
    has_edu_match,
)
from ..core.data import akshare as data_akshare
from ..core.data import guba as data_guba
from ..agents import run_agent
from .. import db as watchlist_db

router = APIRouter(prefix="/api/agent", tags=["小老鼠Agent"])

# ── 全局状态 ────────────────────────────────────────────────────
_current_status = "idle"
_current_action = "🐭 小老鼠正在待命..."
_current_screen_lines: list[str] = []
_notifications: list[dict] = []
_email_config: dict = {}
_timer_thread: threading.Thread | None = None
_timer_running = False

# ── Prompt（News 筛选保留，Chat 切换到 super_agent）─────────────

NEWS_FILTER_PROMPT = """
你是一位金融信息筛选员。请判断以下股吧帖子是否包含值得关注的金融/市场信息。
只关注有实质性内容的帖子（政策变化、公司公告、行业动态、财报信息等），忽略灌水帖。

帖子标题: {title}

请只输出一个字的答案：是/否
"""

# ── API Models ──────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str


class EmailConfigRequest(BaseModel):
    enabled: bool
    smtp_server: str = ""
    smtp_port: int = 587
    sender: str = ""
    password: str = ""
    receiver: str = ""


# ── 屏幕管理 ────────────────────────────────────────────────────


def _push_screen(line: str):
    """向屏幕追加一行，保留最近 8 行"""
    ts = datetime.now().strftime("%H:%M:%S")
    _current_screen_lines.append(f"[{ts}] {line}")
    if len(_current_screen_lines) > 8:
        _current_screen_lines.pop(0)


def _set_screen(text: str):
    """直接设置屏幕为单行"""
    global _current_screen_lines
    ts = datetime.now().strftime("%H:%M:%S")
    _current_screen_lines = [f"[{ts}] {text}"]


def _get_screen() -> str:
    return "\n".join(_current_screen_lines) if _current_screen_lines else "🖥️ 准备就绪..."


# ── 通知管理 ────────────────────────────────────────────────────


def _add_notification(level: str, title: str, content: str):
    _notifications.append({
        "id": int(time.time() * 1000),
        "level": level,
        "title": title,
        "content": content,
        "time": datetime.now().strftime("%H:%M:%S"),
    })
    if _email_config.get("enabled"):
        _send_email(title, content)
    _push_screen(f"🔔 {title}")


def _send_email(subject: str, body: str):
    cfg = _email_config
    if not cfg.get("sender") or not cfg.get("receiver"):
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[小老鼠提醒] {subject}"
        msg["From"] = cfg["sender"]
        msg["To"] = cfg["receiver"]
        with smtplib.SMTP(cfg.get("smtp_server", "smtp.qq.com"), cfg.get("smtp_port", 587)) as server:
            server.starttls()
            server.login(cfg["sender"], cfg["password"])
            server.send_message(msg)
    except Exception:
        pass


# ── 意图识别 + 工具调度 ────────────────────────────────────────

def _identify_intents(question: str) -> list[str]:
    intents: list[str] = []
    if is_emotional(question):
        intents.append("emotional")
    if has_edu_match(question):
        intents.append("education")
    return intents or ["general"]


def _dispatch_tools(question: str, intents: list[str]) -> str:
    outputs: list[str] = []
    if "emotional" in intents:
        result = emotional_first_aid(question)
        if result:
            outputs.append(result)
    if "education" in intents:
        result = risk_education(question)
        if result:
            outputs.append(result)
    return "\n\n".join(outputs)


# ── API 端点 ────────────────────────────────────────────────────


@router.get("/status")
def get_status():
    return {
        "status": _current_status,
        "action": _current_action,
        "screen": _get_screen(),
        "notifications": _notifications[-5:],
        "timer_running": _timer_running,
    }


@router.post("/surf")
def trigger_surf():
    threading.Thread(target=_deep_surf, daemon=True).start()
    return {"ok": True, "msg": "小老鼠开始网上冲浪了 🐭🌊"}


@router.get("/surf-sync")
def surf_sync():
    _deep_surf()
    return {
        "ok": True,
        "screen": _get_screen(),
        "action": _current_action,
        "notifications": _notifications[-5:],
    }


@router.get("/timer-start")
def start_timer():
    global _timer_running, _timer_thread
    if _timer_running:
        return {"ok": True, "msg": "定时任务已在运行"}
    _timer_running = True
    _timer_thread = threading.Thread(target=_timer_loop, daemon=True)
    _timer_thread.start()
    _push_screen("⏰ 定时任务已启动，每 10 分钟巡检一次")
    return {"ok": True, "msg": "定时任务已启动"}


@router.get("/timer-stop")
def stop_timer():
    global _timer_running
    _timer_running = False
    _push_screen("⏹️ 定时任务已停止")
    return {"ok": True}


@router.post("/chat")
def chat(req: ChatRequest):
    global _current_status
    _current_status = "chatting"

    # 1. 意图识别
    intents = _identify_intents(req.question)

    # 2. 工具 dispatch：按意图调用 skill，合并结果
    tool_context = _dispatch_tools(req.question, intents)
    if tool_context:
        _push_screen(f"🛠️ 调用工具: {', '.join(intents)}")

    # 3. 查询 RAG 知识库
    rag_context = cache_rag.search_as_context(req.question)

    # 4. 查询使用文档
    usage_text = usage_doc.search_usage(req.question)
    usage_guide = f"📖 使用指南:\n{usage_text}" if usage_text else ""

    _push_screen("💬 正在思考你的问题...")

    # 5. 调用 super_agent
    reply = run_agent("super_agent", {
        "question": req.question,
        "rag_context": rag_context,
        "usage_guide": usage_guide,
        "tool_context": tool_context,
        "status": _current_status,
        "last_action": _current_action,
        "screen": _get_screen(),
    })

    _current_status = "idle"
    return {"reply": reply, "intents": intents}


@router.get("/notifications")
def get_notifications():
    return {"notifications": _notifications[-10:]}


@router.post("/notifications/clear")
def clear_notifications():
    _notifications.clear()
    return {"ok": True}


@router.post("/email-config")
def set_email_config(config: EmailConfigRequest):
    global _email_config
    _email_config = config.dict()
    return {"ok": True}


@router.get("/email-config")
def get_email_config():
    return _email_config


@router.get("/rag-info")
def get_rag_info():
    """获取缓存知识库统计信息"""
    try:
        cache_rag.ensure_loaded()
        codes = cache_rag.all_cached_codes()
        return {"total_stocks": len(codes), "codes": codes[:20]}
    except Exception as e:
        return {"total_stocks": 0, "error": str(e)}


# ── 定时器循环 ──────────────────────────────────────────────────


def _timer_loop():
    """每 10 分钟执行一次深度巡检"""
    global _timer_running
    # 启动后立即执行第一次
    _deep_surf()
    while _timer_running:
        for minute in range(10):
            if not _timer_running:
                return
            # 空闲时间：浏览自选股股吧
            if minute % 2 == 0:
                threading.Thread(target=_idle_patrol, daemon=True).start()
            time.sleep(60)
        # 每 10 分钟深度巡检
        if _timer_running:
            _deep_surf()


# ── 深度巡检（每 10 分钟） ──────────────────────────────────────


def _deep_surf():
    """深度巡检：宏观 + 热门股吧 + 真伪鉴定"""
    global _current_status, _current_action

    _current_status = "surfing"
    _set_screen("� 小老鼠开始深度网上冲浪...")
    _current_action = "🌊 深度巡检中..."

    # 1. 宏观巡检
    _surf_macro()

    # 2. 股吧扫描 + 真伪鉴定
    _surf_guba_verify()

    _current_status = "idle"
    _current_action = "✅ 深度巡检完成"
    _push_screen("✅ 本轮深度巡检全部完成")


def _surf_macro():
    """宏观数据巡检"""
    _push_screen("📈 正在查看宏观经济数据...")
    time.sleep(0.5)

    macro_info = []
    try:
        df = data_akshare.get_cpi_yearly()
        if df is not None and not df.empty:
            row = df.iloc[-1].to_dict()
            macro_info.append(f"CPI: {json.dumps(row, ensure_ascii=False)}")
            _push_screen(f"📊 CPI 数据已获取")
    except Exception:
        _push_screen("⚠️ CPI 数据获取失败")

    try:
        df = data_akshare.get_gdp()
        if df is not None and not df.empty:
            row = df.iloc[-1].to_dict()
            macro_info.append(f"GDP: {json.dumps(row, ensure_ascii=False)}")
            _push_screen(f"📊 GDP 数据已获取")
    except Exception:
        _push_screen("⚠️ GDP 数据获取失败")

    try:
        df = data_akshare.get_pmi()
        if df is not None and not df.empty:
            row = df.iloc[-1].to_dict()
            macro_info.append(f"PMI: {json.dumps(row, ensure_ascii=False)}")
            _push_screen(f"📊 PMI 数据已获取")
    except Exception:
        _push_screen("⚠️ PMI 数据获取失败")

    time.sleep(0.5)
    _push_screen("🤔 分析宏观数据中...")

    web_data = "\n".join(macro_info) if macro_info else "暂无最新数据"
    prompt = f"""
你是一位宏观经济分析师。当前日期: {datetime.now().strftime("%Y-%m-%d")}
已有事件: CPI月度数据, PMI月度数据, GDP数据

最新数据:
{web_data}

判断是否有需要添加到宏观日历的重要新事件。只需输出 JSON:
{{"should_add": true/false, "reason": "理由", "event": {{"name": "事件名", "date": "日期", "tag": "important/normal/warning"}}}}
"""
    result = call_llm(prompt, max_tokens=300)
    try:
        parsed = json.loads(result)
        if parsed.get("should_add") and parsed.get("event"):
            ev = parsed["event"]
            _add_notification(ev.get("tag", "info"), f"📅 宏观事件: {ev['name']}", f"日期: {ev['date']}\n{parsed.get('reason','')}")
            _push_screen(f"📅 发现重要宏观事件: {ev['name']}")
    except Exception:
        _push_screen("📰 宏观数据已查看，暂无新增事件")


def _surf_guba_verify():
    """扫描热门股吧帖子 + 真伪鉴定"""
    _push_screen("📡 扫描热门股票的股吧帖子...")

    # 获取涨停池作为热门标的
    hot_stocks = []
    try:
        df = data_akshare.get_zt_pool(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                hot_stocks.append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                })
    except Exception:
        pass

    # 没有涨停数据时用自选股
    if not hot_stocks:
        stocks = watchlist_db.get_all_watchlist_stocks()
        hot_stocks = [{"code": s["code"], "name": s.get("name", s["code"])} for s in stocks]

    if not hot_stocks:
        _push_screen("� 暂无热门股票数据，跳过股吧扫描")
        return

    _push_screen(f"🔍 从 {len(hot_stocks)} 只热门股票中扫描股吧...")

    all_posts = []
    for i, stock in enumerate(hot_stocks[:5]):  # 最多扫描 5 只
        code = stock["code"]
        name = stock["name"]
        _current_action = f"📖 正在浏览 {name}({code}) 的股吧... ({i+1}/{min(len(hot_stocks),5)})"
        _push_screen(f"📖 浏览 {name} 的股吧...")
        time.sleep(0.3)

        # 查阅缓存知识库，了解已有信息
        try:
            cached = cache_rag.query(code)
            if cached:
                _push_screen(f"📚 已查阅 {name} 的缓存知识")
        except Exception:
            pass

        try:
            posts = data_guba.scrape_stock_posts(code)
            for p in posts:
                all_posts.append({**p, "stock_name": name, "stock_code": code})
        except Exception:
            pass

    if not all_posts:
        _push_screen("📭 没有获取到股吧帖子")
        return

    _push_screen(f"📋 共收集 {len(all_posts)} 条帖子，正在筛选重要信息...")
    time.sleep(0.5)

    # 用 LLM 快速筛选有实质性内容的帖子
    important_posts = []
    for post in all_posts[:30]:  # 最多处理 30 条
        title = post.get("title", "")
        if not title or len(title) < 6:
            continue
        _push_screen(f"🔎 筛选: {title[:30]}...")
        try:
            filter_prompt = NEWS_FILTER_PROMPT.format(title=title)
            verdict = call_llm(filter_prompt, max_tokens=10)
            if "是" in verdict:
                important_posts.append(post)
        except Exception:
            pass

    if not important_posts:
        _push_screen("📭 未发现值得关注的重要消息")
        return

    _push_screen(f"🔬 发现 {len(important_posts)} 条重要消息，调用真伪鉴别 AI 鉴定...")
    time.sleep(0.5)

    # 串行调用 Coze 真伪鉴定
    verified_count = 0
    suspicious_count = 0
    for post in important_posts[:5]:
        title = post.get("title", "")
        stock_name = post.get("stock_name", "")
        _current_action = f"🔬 鉴定中: {title[:30]}..."
        _push_screen(f"🔬 真伪鉴定: {title[:35]}...")
        time.sleep(0.5)

        result = verify_news(title)
        if result.get("authentic") is False or result.get("confidence") == "低":
            suspicious_count += 1
            _add_notification(
                "warning",
                f"⚠️ 可疑消息: {stock_name}",
                f"帖子: {title}\n研判: {result.get('reason', '')}",
            )
            _push_screen(f"⚠️ 发现可疑消息: {title[:30]}")
        else:
            verified_count += 1
            _push_screen(f"✅ 消息可信: {title[:30]}")

    _push_screen(f"📊 鉴定完成：{verified_count} 条可信，{suspicious_count} 条存疑")


# ── 空闲巡检（每 2 分钟） ──────────────────────────────────────


def _idle_patrol():
    """空闲时浏览自选股股吧"""
    global _current_status, _current_action
    if _current_status != "idle":
        return

    _current_status = "idle"
    stocks = watchlist_db.get_all_watchlist_stocks()
    if not stocks:
        return

    for stock in stocks:
        if _current_status != "idle":
            break
        code = stock["code"]
        name = stock.get("name", code)
        _current_action = f"🐭 正在浏览 {name} 的股吧..."
        _push_screen(f"🐭 浏览 {name}({code}) 的股吧...")

        # 查阅缓存知识库
        try:
            cached = cache_rag.query(code)
            if cached:
                _push_screen(f"📚 已有 {name} 的历史分析记录")
        except Exception:
            pass

        try:
            posts = data_guba.scrape_stock_posts(code)
            if posts:
                for p in posts[:3]:
                    _push_screen(f"📄 {p.get('title','')[:50]}")
                    time.sleep(0.8)
        except Exception:
            pass

        time.sleep(0.5)

    _current_action = "✅ 自选股浏览完成"
    _push_screen("✅ 已浏览完所有自选股的股吧动态")


# ── 工具函数 ────────────────────────────────────────────────────



