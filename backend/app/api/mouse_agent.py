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

from fastapi import APIRouter, Depends, HTTPException, Query
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
    read_cache,
    write_cache,
)
from ..core.data import akshare as data_akshare
from ..core.data import guba as data_guba
from ..core.data import news as data_news
from ..agents import run_agent
from .. import db as watchlist_db
from ..auth import get_current_user
from ..agent_runtime.memory import build_context, consolidate_session, maybe_extract_explicit_memory, remember
from ..agent_runtime import create_patrol_plan, start as start_workflow

router = APIRouter(prefix="/api/agent", tags=["小老鼠Agent"])

# ── 全局状态 ────────────────────────────────────────────────────
_current_status = "idle"
_current_action = "🐭 小老鼠正在待命..."
_current_screen_lines: list[str] = []
_notifications: list[dict] = []
_email_config: dict = {}
_timer_thread: threading.Thread | None = None
_timer_running = False
_analyzed_news_ids: set[str] = set()
_surf_lock = threading.Lock()

# ── API Models ──────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    space_id: str = "default"


class MemoryRequest(BaseModel):
    memory_type: str
    content: str
    importance: int = 2
    space_id: str = "default"


class MemorySpaceRequest(BaseModel):
    name: str = ""


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
    run_id = start_workflow(create_patrol_plan())
    return {"ok": True, "run_id": run_id, "msg": "小老鼠已将巡检加入全局任务队列 🐭🌊"}


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
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    global _current_status
    _current_status = "chatting"

    session_id = (req.session_id or "default").strip()[:100]
    requested_space_id = (req.space_id or "default").strip()[:100]
    session = watchlist_db.get_agent_session(session_id)
    if not session:
        if not watchlist_db.get_agent_space(user["id"], requested_space_id):
            raise HTTPException(status_code=409, detail="请先新建一个记忆空间，再开始对话")
        watchlist_db.ensure_agent_session(session_id, requested_space_id)
        session = watchlist_db.get_agent_session(session_id) or {}
    elif not watchlist_db.get_agent_space(user["id"], session.get("space_id", "")):
        raise HTTPException(status_code=403, detail="无权访问该对话")
    space_id = session.get("space_id", "default")
    # 1. 记录本轮输入，并仅在用户明确要求时写入长期记忆
    watchlist_db.add_agent_message(session_id, "user", req.question)
    saved_memory = None
    try:
        saved_memory = maybe_extract_explicit_memory(req.question, space_id=space_id)
    except ValueError as exc:
        _push_screen(f"🧠 未保存记忆: {exc}")

    # 2. 意图识别
    intents = _identify_intents(req.question)

    # 3. 工具 dispatch：按意图调用 skill，合并结果
    tool_context = _dispatch_tools(req.question, intents)
    if tool_context:
        _push_screen(f"🛠️ 调用工具: {', '.join(intents)}")

    # 4. 查询 RAG 知识库
    rag_context = cache_rag.search_as_context(req.question)

    # 5. 查询使用文档
    usage_text = usage_doc.search_usage(req.question)
    usage_guide = f"📖 使用指南:\n{usage_text}" if usage_text else ""

    _push_screen("💬 正在思考你的问题...")

    # 6. 只注入最近会话和与当前问题相关的长期记忆
    memory_context = build_context(session_id, req.question)

    # 7. 调用 super_agent
    reply = run_agent("super_agent", {
        "question": req.question,
        "rag_context": rag_context,
        "usage_guide": usage_guide,
        "tool_context": tool_context,
        "status": _current_status,
        "last_action": _current_action,
        "screen": _get_screen(),
        **memory_context,
    })

    watchlist_db.add_agent_message(session_id, "assistant", reply)
    threading.Thread(target=consolidate_session, args=(session_id, req.question), daemon=True).start()
    _current_status = "idle"
    return {"reply": reply, "intents": intents, "session_id": session_id, "space_id": space_id, "memory_saved": saved_memory}


@router.get("/spaces")
def get_memory_spaces(user: dict = Depends(get_current_user)):
    """列出小老鼠的记忆空间（类似项目文件夹）。"""
    return {"spaces": watchlist_db.list_agent_spaces(user["id"])}


@router.post("/spaces")
def create_memory_space(req: MemorySpaceRequest, user: dict = Depends(get_current_user)):
    try:
        return {"space": watchlist_db.create_agent_space(user["id"], req.name)}
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}


@router.patch("/spaces/{space_id}")
def rename_memory_space(space_id: str, req: MemorySpaceRequest, user: dict = Depends(get_current_user)):
    try:
        return {"space": watchlist_db.rename_agent_space(user["id"], space_id, req.name)}
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}


@router.delete("/spaces/{space_id}")
def delete_memory_space(space_id: str, user: dict = Depends(get_current_user)):
    try:
        ok = watchlist_db.delete_agent_space(user["id"], space_id)
        return {"ok": ok, "message": "记忆空间不存在" if not ok else "记忆空间已删除"}
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}


@router.get("/spaces/{space_id}/sessions")
def get_space_sessions(space_id: str, user: dict = Depends(get_current_user)):
    return {"sessions": watchlist_db.list_agent_sessions(user["id"], space_id)}


@router.post("/spaces/{space_id}/sessions")
def create_space_session(space_id: str, user: dict = Depends(get_current_user)):
    try:
        return {"session": watchlist_db.create_agent_session(user["id"], space_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/spaces/{space_id}/sessions/{session_id}")
def delete_space_session(space_id: str, session_id: str, user: dict = Depends(get_current_user)):
    ok = watchlist_db.delete_agent_session(user["id"], space_id, session_id)
    return {"ok": ok, "message": "对话不存在或不属于当前空间" if not ok else "对话已删除"}


@router.get("/memory/session/{session_id}")
def get_session_memory(session_id: str, user: dict = Depends(get_current_user)):
    """调试/展示当前会话的短期记忆，不暴露其他会话。"""
    session = watchlist_db.get_agent_session(session_id)
    if session and not watchlist_db.get_agent_space(user["id"], session.get("space_id", "")):
        raise HTTPException(status_code=403, detail="无权访问该对话")
    return {"session": session, "messages": watchlist_db.get_agent_messages(session_id, limit=12)}


@router.get("/memory")
def get_long_term_memory(space_id: str = Query(...), user: dict = Depends(get_current_user)):
    """返回小老鼠可长期记住的稳定偏好与关注点。"""
    if not watchlist_db.get_agent_space(user["id"], space_id):
        raise HTTPException(status_code=404, detail="记忆空间不存在")
    return {"memories": watchlist_db.list_agent_memories(space_id=space_id)}


@router.post("/memory")
def create_long_term_memory(req: MemoryRequest, user: dict = Depends(get_current_user)):
    """显式保存长期记忆；前端或用户都可调用。"""
    try:
        if not watchlist_db.get_agent_space(user["id"], req.space_id):
            raise ValueError("记忆空间不存在，请先新建空间")
        return {"memory": remember(req.memory_type, req.content, source="manual", importance=req.importance, space_id=req.space_id)}
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}


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
    trigger_surf()
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
            trigger_surf()


# ── 深度巡检（每 10 分钟） ──────────────────────────────────────


def _deep_surf():
    """深度巡检：抓取宏观新闻 + 热门股吧 + 真伪鉴定（互斥，同时只允许一个巡检）"""
    if not _surf_lock.acquire(blocking=False):
        _push_screen("⏭️ 已有巡检任务进行中，跳过本次")
        return

    global _current_status, _current_action
    try:
        _current_status = "surfing"
        _set_screen("🌊 小老鼠开始深度网上冲浪...")
        _current_action = "🌊 深度巡检中..."

        _surf_news()
        _surf_guba_verify()

        _current_status = "idle"
        _current_action = "✅ 深度巡检完成"
        _push_screen("✅ 本轮深度巡检全部完成")
    finally:
        _surf_lock.release()


def _surf_news():
    """抓取宏观财经新闻，分析是否有重要事件，已分析过的跳过"""
    _push_screen("📰 正在抓取宏观财经新闻...")
    time.sleep(0.5)

    try:
        official_news, _ = data_news.fetch_all_news(days=1)
    except Exception:
        _push_screen("⚠️ 新闻抓取失败")
        return

    if not official_news:
        _push_screen("📭 暂无新的宏观新闻")
        return

    _push_screen(f"📋 获取到 {len(official_news)} 条新闻，筛选新内容...")

    new_news = []
    for n in official_news:
        news_id = f"{n['source']}:{n['title']}"
        if news_id not in _analyzed_news_ids:
            _analyzed_news_ids.add(news_id)
            new_news.append(n)

    if not new_news:
        _push_screen("📭 没有未分析过的新新闻")
        return

    _push_screen(f"🔍 发现 {len(new_news)} 条新新闻，分析是否包含重要宏观事件...")
    time.sleep(0.5)

    news_text = "\n".join(
        f"- [{n['source']}] {n['title']}（{n['date']}）" for n in new_news[:5]
    )
    prompt = f"""
你是一位宏观经济分析师。当前日期: {datetime.now().strftime("%Y-%m-%d")}

以下是最近几天的财经新闻：

{news_text}

判断哪些是重要的宏观事件（如政策变化、经济数据发布、重大行业监管等），需要提醒用户关注。
忽略普通的公司公告、市场日常波动等。

只需输出 JSON 数组，没有重要事件就输出空数组:
[{{"title": "事件标题", "date": "日期", "tag": "important/normal/warning", "reason": "简短理由"}}]
"""
    result = call_llm(messages=[{"role": "user", "content": prompt}], max_tokens=500)
    try:
        events = json.loads(result)
        if events:
            # 写入宏观日历持久化事件库
            try:
                persistent = read_cache("macro_risk_timeline_persistent", module="macro") or {"events": []}
                existing_titles = {e["title"] for e in persistent.get("events", [])}
                for ev in events:
                    if ev["title"] not in existing_titles:
                        tag = ev.get("tag", "info")
                        risk_level = "高" if tag == "warning" else "中" if tag == "important" else "低"
                        persistent["events"].append({
                            "title": ev["title"],
                            "date": ev.get("date", ""),
                            "first_occurrence": ev.get("date", ""),
                            "risk_level": risk_level,
                            "duration": "短期影响",
                            "duration_days": 14,
                            "time_status": "进行中",
                            "source": "小老鼠巡检",
                            "reason": ev.get("reason", ""),
                        })
                        existing_titles.add(ev["title"])
                write_cache("macro_risk_timeline_persistent", persistent, module="macro")
            except Exception:
                pass

            for ev in events:
                tag = ev.get("tag", "info")
                _add_notification(
                    tag,
                    f"📰 宏观事件: {ev['title']}",
                    f"日期: {ev.get('date', '')}\n{ev.get('reason', '')}",
                )
                _push_screen(f"📰 发现重要事件: {ev['title'][:30]}")
            _push_screen(f"✅ 分析完成，发现 {len(events)} 个重要事件，已写入宏观日历")
        else:
            _push_screen("📰 本轮新闻无重要宏观事件")
    except Exception:
        _push_screen("📰 新闻分析完成，暂无新增重要事件")


def _surf_guba_verify():
    """扫描自选股股吧帖子 + 真伪鉴定"""
    _push_screen("📡 扫描自选股的股吧帖子...")

    # 只扫描自选股
    stocks = watchlist_db.get_all_watchlist_stocks()
    hot_stocks = [{"code": s["code"], "name": s.get("name", s["code"])} for s in stocks]

    if not hot_stocks:
        _push_screen("🕊️ 暂无自选股，跳过股吧扫描")
        return

    _push_screen(f"🔍 从 {len(hot_stocks)} 只自选股中扫描股吧...")

    all_posts = []
    for i, stock in enumerate(hot_stocks[:3]):  # 最多扫描 3 只
        code = stock["code"]
        name = stock["name"]
        _current_action = f"📖 正在浏览 {name}({code}) 的股吧... ({i+1}/{min(len(hot_stocks),3)})"
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
            for p in posts[:20]:  # 每只最多取 20 条
                all_posts.append({**p, "stock_name": name, "stock_code": code})
        except Exception:
            pass

    if not all_posts:
        _push_screen("📭 没有获取到股吧帖子")
        return

    _push_screen(f"📋 共收集 {len(all_posts)} 条帖子，正在批量筛选重要信息...")
    time.sleep(0.5)

    # 用一次 LLM 调用批量筛选有实质性内容的帖子
    all_titles = [p.get("title", "") for p in all_posts if p.get("title") and len(p.get("title", "")) >= 6]
    if not all_titles:
        _push_screen("📭 没有有效帖子标题")
        return

    titles_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(all_titles[:30]))
    batch_prompt = f"""
你是一位金融信息筛选员。请判断以下帖子的标题是否包含值得关注的金融/市场信息。
只关注有实质性内容的帖子（政策变化、公司公告、行业动态、财报信息等），忽略灌水帖。

{titles_text}

只输出重要帖子的序号列表（JSON 数组），没有就输出 []:
"""
    try:
        batch_result = call_llm(messages=[{"role": "user", "content": batch_prompt}], max_tokens=200)
        indices = json.loads(batch_result.strip())
        if not isinstance(indices, list):
            raise ValueError
        important_posts = [all_posts[i-1] for i in indices if 1 <= i <= len(all_posts)]
    except Exception:
        # 回退：只保留前几条
        important_posts = all_posts[:5]

    if not important_posts:
        _push_screen("📭 未发现值得关注的重要消息")
        return

    _push_screen(f"🔬 发现 {len(important_posts)} 条重要消息，调用真伪鉴别 AI 鉴定...")
    time.sleep(0.5)

    # 串行调用 Coze 真伪鉴定
    verified_count = 0
    suspicious_count = 0
    for post in important_posts[:3]:  # 最多鉴定 3 条
        title = post.get("title", "")
        stock_name = post.get("stock_name", "")
        _current_action = f"🔬 鉴定中: {title[:30]}..."
        _push_screen(f"🔬 真伪鉴定: {title[:35]}...")
        time.sleep(0.5)

        result = verify_news(title)
        # 只有明确判定为虚假时才标记可疑；置信度低但未判定虚假的仅提示
        is_fake = result.get("authentic") is False and result.get("confidence") != "低"
        is_uncertain = result.get("authentic") is False and result.get("confidence") == "低"
        reason = result.get("reason", "")

        if is_fake:
            suspicious_count += 1
            _add_notification(
                "warning",
                f"⚠️ 可疑消息: {stock_name}",
                f"帖子: {title}\n研判: {reason}",
            )
            _push_screen(f"⚠️ 发现可疑消息: {title[:30]}")
        elif is_uncertain:
            _add_notification(
                "info",
                f"🔍 待核实: {stock_name}",
                f"帖子: {title}\n研判: 置信度低，建议人工核实\n{reason}",
            )
            _push_screen(f"🔍 待核实消息: {title[:30]}")
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



