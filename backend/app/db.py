"""
SQLite 持久化层 — 用户、自选股列表、分析结果缓存、风险日记。
"""
from __future__ import annotations

import sqlite3
import json
import os
import uuid
import re
from datetime import datetime

from .core.config import read_cache, write_cache, CACHE_DIR

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getenv("COZE_ENV") or os.getenv("PORT"):
    DB_DIR = "/tmp"
    DB_PATH = os.path.join(DB_DIR, "watchlist.db")
else:
    DB_PATH = os.path.join(BASE_DIR, "watchlist.db")

MAX_WATCHLIST = 10


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL DEFAULT 1,
                code      TEXT NOT NULL,
                name      TEXT,
                added_at  TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, code)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_analysis (
                code               TEXT PRIMARY KEY,
                name               TEXT,
                fundamental_stars  INTEGER,
                news_stars         INTEGER,
                risk_stars         INTEGER,
                overall_stars      INTEGER,
                brief              TEXT,
                score_basis        TEXT,
                news_json          TEXT,
                wordcloud_b64      TEXT,
                updated_at         TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS risk_diaries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                code       TEXT NOT NULL,
                name       TEXT,
                date       TEXT,
                risk_level TEXT,
                risk_score INTEGER,
                system_suggestion TEXT,
                user_note  TEXT,
                tag        TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id       TEXT PRIMARY KEY,
                status       TEXT NOT NULL,
                goal         TEXT,
                symbol       TEXT,
                plan_json    TEXT,
                result_json  TEXT,
                created_at   TEXT,
                completed_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS workflow_task_runs (
                run_id       TEXT NOT NULL,
                task_id      TEXT NOT NULL,
                tool         TEXT NOT NULL,
                status       TEXT NOT NULL,
                output_json  TEXT,
                error        TEXT,
                attempts     INTEGER DEFAULT 0,
                duration_ms  INTEGER DEFAULT 0,
                PRIMARY KEY (run_id, task_id),
                FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory_spaces (
                space_id     TEXT PRIMARY KEY,
                user_id      INTEGER NOT NULL DEFAULT 0,
                name         TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                session_id   TEXT PRIMARY KEY,
                space_id     TEXT NOT NULL DEFAULT 'default',
                title        TEXT NOT NULL DEFAULT '新对话',
                summary      TEXT NOT NULL DEFAULT '',
                active_goal  TEXT NOT NULL DEFAULT '',
                updated_at   TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                role         TEXT NOT NULL,
                content      TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_memories (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                space_id     TEXT NOT NULL DEFAULT 'default',
                memory_type  TEXT NOT NULL,
                content      TEXT NOT NULL,
                keywords     TEXT NOT NULL DEFAULT '',
                importance   INTEGER NOT NULL DEFAULT 1,
                source       TEXT NOT NULL DEFAULT 'user',
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                last_used_at TEXT
            )
        """)
        c.commit()

    # ── 数据库迁移：旧表缺列时补上 ─────────────────────────────────
    with _conn() as c:
        # 确保 watchlist 表有 user_id 列（兼容本地已有旧库）
        try:
            c.execute("ALTER TABLE watchlist ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # 列已存在
        # 确保 watchlist_analysis 表有 name 列
        try:
            c.execute("ALTER TABLE watchlist_analysis ADD COLUMN name TEXT")
        except sqlite3.OperationalError:
            pass
        # 小老鼠记忆空间迁移：历史数据进入“默认空间”，不丢失旧记忆。
        for statement in (
            "ALTER TABLE agent_sessions ADD COLUMN space_id TEXT NOT NULL DEFAULT 'default'",
            "ALTER TABLE agent_sessions ADD COLUMN title TEXT NOT NULL DEFAULT '新对话'",
            "ALTER TABLE agent_memories ADD COLUMN space_id TEXT NOT NULL DEFAULT 'default'",
            "ALTER TABLE agent_memory_spaces ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0",
        ):
            try:
                c.execute(statement)
            except sqlite3.OperationalError:
                pass

    # ── 数据库迁移：修复 UNIQUE(code) → UNIQUE(user_id, code) ──
    # 旧版 watchlist 表的 UNIQUE 约束只在 code 列上，导致不同用户无法添加同一只股票
    with _conn() as c:
        row = c.execute("SELECT sql FROM sqlite_master WHERE name='watchlist'").fetchone()
        sql_normalized = " ".join(row["sql"].split()) if row else ""
        if "code TEXT UNIQUE NOT NULL" in sql_normalized:
            c.execute("""
                CREATE TABLE watchlist_new (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id   INTEGER NOT NULL DEFAULT 1,
                    code      TEXT NOT NULL,
                    name      TEXT,
                    added_at  TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE(user_id, code)
                )
            """)
            c.execute("INSERT INTO watchlist_new (id, user_id, code, name, added_at) SELECT id, user_id, code, name, added_at FROM watchlist")
            c.execute("DROP TABLE watchlist")
            c.execute("ALTER TABLE watchlist_new RENAME TO watchlist")


# ── 用户 CRUD ────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> dict:
    with _conn() as c:
        try:
            cursor = c.execute(
                "INSERT INTO users(username, password, created_at) VALUES(?,?,?)",
                (username, password_hash, datetime.now().isoformat()),
            )
            c.commit()
            return {"ok": True, "user_id": cursor.lastrowid}
        except sqlite3.IntegrityError:
            return {"ok": False, "msg": "用户名已存在"}


def get_user_by_username(username: str):
    with _conn() as c:
        row = c.execute(
            "SELECT id, username, password, created_at FROM users WHERE username=?",
            (username,)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    with _conn() as c:
        row = c.execute(
            "SELECT id, username, created_at FROM users WHERE id=?",
            (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ── 自选股 CRUD ─────────────────────────────────────────────────

def get_watchlist(user_id: int) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT code, name, added_at FROM watchlist WHERE user_id=? ORDER BY added_at DESC",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_stock(user_id: int, code: str, name: str = "") -> dict:
    with _conn() as c:
        count = c.execute(
            "SELECT COUNT(*) FROM watchlist WHERE user_id=?", (user_id,)
        ).fetchone()[0]
        if count >= MAX_WATCHLIST:
            return {"ok": False, "msg": f"自选股最多 {MAX_WATCHLIST} 只"}
        try:
            c.execute(
                "INSERT OR IGNORE INTO watchlist(user_id, code, name, added_at) VALUES(?,?,?,?)",
                (user_id, code, name, datetime.now().isoformat()),
            )
            c.commit()
            return {"ok": True, "msg": "已添加"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}


def get_all_watchlist_stocks() -> list:
    """返回所有用户自选股去重列表，仅供后台任务（巡检/巡航）使用"""
    with _conn() as c:
        rows = c.execute(
            "SELECT DISTINCT code, name FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def remove_stock(user_id: int, code: str) -> bool:
    with _conn() as c:
        c.execute("DELETE FROM watchlist WHERE user_id=? AND code=?", (user_id, code))
        c.execute("DELETE FROM watchlist_analysis WHERE code=?", (code,))
        c.commit()
    # 同时清理 filesystem 缓存
    try:
        os.remove(os.path.join(CACHE_DIR, f"watchlist_analysis_{code}.json"))
    except Exception:
        pass
    return True


def update_stock_name(code: str, name: str):
    """更新所有用户自选股中该股票的名称"""
    with _conn() as c:
        c.execute("UPDATE watchlist SET name=? WHERE code=?", (name, code))
        c.commit()


# ── 分析结果缓存（统一走 filesystem）─────────────────────────

def get_analysis(code: str):
    """返回当日有效的分析结果，过期返回 None"""
    data = read_cache(f"watchlist_analysis_{code}", module="")
    if not data:
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    updated = (data.get("updated_at") or "")[:10]
    if updated != today:
        return None
    return data


def save_analysis(code: str, data: dict):
    """保存分析结果到 filesystem 缓存"""
    write_cache(f"watchlist_analysis_{code}", data, module="")


# ── 风险日记 CRUD ────────────────────────────────────────────────

def get_diaries(user_id: int, code: str = None) -> list:
    with _conn() as c:
        if code:
            rows = c.execute(
                "SELECT * FROM risk_diaries WHERE user_id=? AND code=? ORDER BY created_at DESC",
                (user_id, code)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM risk_diaries WHERE user_id=? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def add_diary(user_id: int, data: dict) -> dict:
    with _conn() as c:
        try:
            c.execute("""
                INSERT INTO risk_diaries
                  (user_id, code, name, date, risk_level, risk_score,
                   system_suggestion, user_note, tag, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                user_id,
                data.get("code", ""),
                data.get("name", ""),
                data.get("date", datetime.now().strftime("%Y-%m-%d")),
                data.get("risk_level", "低"),
                data.get("risk_score", 3),
                data.get("system_suggestion", ""),
                data.get("user_note", ""),
                data.get("tag", "关注"),
                datetime.now().isoformat(),
            ))
            c.commit()
            return {"ok": True, "id": c.lastrowid}
        except Exception as e:
            return {"ok": False, "msg": str(e)}


def delete_diary(user_id: int, diary_id: int) -> bool:
    with _conn() as c:
        c.execute(
            "DELETE FROM risk_diaries WHERE id=? AND user_id=?",
            (diary_id, user_id)
        )
        c.commit()
    return True


# ── Agent 工作流运行记录 ──────────────────────────────────────────

def create_workflow_run(run: dict):
    with _conn() as c:
        c.execute(
            "INSERT INTO workflow_runs(run_id,status,goal,symbol,plan_json,created_at) VALUES(?,?,?,?,?,?)",
            (run["run_id"], run["status"], run["plan"].get("goal", ""), run["plan"].get("symbol", ""),
             json.dumps(run["plan"], ensure_ascii=False), run["created_at"]),
        )
        for task in run["tasks"].values():
            c.execute(
                "INSERT INTO workflow_task_runs(run_id,task_id,tool,status) VALUES(?,?,?,?)",
                (run["run_id"], task["task_id"], task["tool"], task["status"]),
            )
        c.commit()


def update_workflow_run(run_id: str, status: str, completed_at: str | None = None, result: dict | None = None):
    with _conn() as c:
        c.execute(
            "UPDATE workflow_runs SET status=?, completed_at=COALESCE(?, completed_at), result_json=COALESCE(?, result_json) WHERE run_id=?",
            (status, completed_at, json.dumps(result, ensure_ascii=False) if result is not None else None, run_id),
        )
        c.commit()


def update_workflow_task(run_id: str, task: dict):
    with _conn() as c:
        c.execute(
            """UPDATE workflow_task_runs
               SET status=?, output_json=?, error=?, attempts=?, duration_ms=?
               WHERE run_id=? AND task_id=?""",
            (task["status"], json.dumps(task.get("output", {}), ensure_ascii=False), task.get("error", ""),
             task.get("attempts", 0), task.get("duration_ms", 0), run_id, task["task_id"]),
        )
        c.commit()


def get_workflow_run(run_id: str) -> dict | None:
    """服务重启后用于审计的工作流快照。"""
    with _conn() as c:
        run = c.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            return None
        tasks = c.execute("SELECT * FROM workflow_task_runs WHERE run_id=? ORDER BY task_id", (run_id,)).fetchall()
    result = dict(run)
    result["plan"] = json.loads(result.pop("plan_json") or "{}")
    result["result"] = json.loads(result.pop("result_json") or "null")
    result["tasks"] = {
        row["task_id"]: {
            "task_id": row["task_id"], "tool": row["tool"], "status": row["status"],
            "output": json.loads(row["output_json"] or "{}"), "error": row["error"] or "",
            "attempts": row["attempts"], "duration_ms": row["duration_ms"],
        }
        for row in tasks
    }
    return result


# ── 小老鼠记忆：记忆空间 → 对话 → 长短期记忆 ───────────────────

def ensure_agent_space(space_id: str, user_id: int, name: str = "未命名空间") -> None:
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO agent_memory_spaces(space_id,user_id,name,created_at,updated_at) VALUES(?,?,?,?,?)",
            (space_id, user_id, name[:80] or "未命名空间", now, now),
        )
        c.commit()


def create_agent_space(user_id: int, name: str = "") -> dict:
    clean = " ".join(name.split())[:80]
    if not clean:
        with _conn() as c:
            count = c.execute("SELECT COUNT(*) FROM agent_memory_spaces WHERE user_id=? AND name LIKE '新记忆空间%' ", (user_id,)).fetchone()[0]
        clean = f"新记忆空间 {count + 1}"
    space_id = f"space-{uuid.uuid4().hex[:12]}"
    ensure_agent_space(space_id, user_id, clean)
    return {"space_id": space_id, "name": clean}


def rename_agent_space(user_id: int, space_id: str, name: str) -> dict:
    clean = " ".join(name.split())[:80]
    if not clean:
        raise ValueError("空间名称不能为空")
    with _conn() as c:
        cursor = c.execute(
            "UPDATE agent_memory_spaces SET name=?, updated_at=? WHERE space_id=? AND user_id=?",
            (clean, datetime.now().isoformat(), space_id, user_id),
        )
        c.commit()
    if cursor.rowcount == 0:
        raise ValueError("记忆空间不存在")
    return {"space_id": space_id, "name": clean}


def delete_agent_space(user_id: int, space_id: str) -> bool:
    """删除空间、其会话和其长期记忆。"""
    with _conn() as c:
        exists = c.execute("SELECT 1 FROM agent_memory_spaces WHERE space_id=? AND user_id=?", (space_id, user_id)).fetchone()
        if not exists:
            return False
        c.execute("DELETE FROM agent_memories WHERE space_id=?", (space_id,))
        c.execute("DELETE FROM agent_messages WHERE session_id IN (SELECT session_id FROM agent_sessions WHERE space_id=?)", (space_id,))
        c.execute("DELETE FROM agent_sessions WHERE space_id=?", (space_id,))
        c.execute("DELETE FROM agent_memory_spaces WHERE space_id=?", (space_id,))
        c.commit()
    return True


def list_agent_spaces(user_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT spaces.*, COUNT(sessions.session_id) AS session_count
            FROM agent_memory_spaces spaces
            LEFT JOIN agent_sessions sessions ON sessions.space_id = spaces.space_id
            WHERE spaces.user_id=?
            GROUP BY spaces.space_id
            ORDER BY spaces.updated_at DESC
        """, (user_id,)).fetchall()
    return [dict(row) for row in rows]


def get_agent_space(user_id: int, space_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM agent_memory_spaces WHERE space_id=? AND user_id=?", (space_id, user_id)).fetchone()
    return dict(row) if row else None


def ensure_agent_session(session_id: str, space_id: str, title: str = "新对话") -> None:
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO agent_sessions(session_id,space_id,title,updated_at) VALUES(?,?,?,?)",
            (session_id, space_id, title[:80] or "新对话", now),
        )
        c.commit()


def create_agent_session(user_id: int, space_id: str, title: str = "新对话") -> dict:
    if not get_agent_space(user_id, space_id):
        raise ValueError("记忆空间不存在，请先新建空间")
    session_id = f"session-{uuid.uuid4().hex[:16]}"
    ensure_agent_session(session_id, space_id, title)
    return get_agent_session(session_id) or {"session_id": session_id, "space_id": space_id, "title": title}


def list_agent_sessions(user_id: int, space_id: str, limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT sessions.* FROM agent_sessions sessions JOIN agent_memory_spaces spaces ON spaces.space_id=sessions.space_id WHERE sessions.space_id=? AND spaces.user_id=? ORDER BY sessions.updated_at DESC LIMIT ?",
            (space_id, user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_agent_session(user_id: int, space_id: str, session_id: str) -> bool:
    """删除一段对话及其短期消息；长期记忆仍归属于记忆空间，不受影响。"""
    with _conn() as c:
        exists = c.execute(
            "SELECT 1 FROM agent_sessions sessions JOIN agent_memory_spaces spaces ON spaces.space_id=sessions.space_id WHERE sessions.session_id=? AND sessions.space_id=? AND spaces.user_id=?",
            (session_id, space_id, user_id),
        ).fetchone()
        if not exists:
            return False
        c.execute("DELETE FROM agent_messages WHERE session_id=?", (session_id,))
        c.execute("DELETE FROM agent_sessions WHERE session_id=?", (session_id,))
        c.commit()
    return True


def _derive_agent_session_title(content: str) -> str:
    """从首条输入提取一个简短、可辨识的对话主题，不调用额外 LLM。"""
    text = " ".join(content.split())
    text = re.sub(r"^(请问|请|帮我|麻烦你|我想|我需要|你能不能|能不能|可以|如何|怎么)", "", text)
    code = re.search(r"\b\d{6}\b", text)
    if code and any(word in text for word in ("风险", "股票", "财报", "分析")):
        return f"{code.group()} · 风险分析"
    for topic in ("抖音面试", "任务编排", "长期记忆", "宏观风险", "财报分析", "股吧舆情"):
        if topic in text:
            return topic
    text = re.split(r"[。！!？?；;，,\n]", text)[0].strip()
    return (text[:22] + "…") if len(text) > 22 else (text or "新对话")


def add_agent_message(session_id: str, role: str, content: str) -> None:
    now = datetime.now().isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO agent_messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
            (session_id, role, content[:4000], now),
        )
        c.execute(
            "UPDATE agent_sessions SET title=CASE WHEN title='新对话' AND ?='user' THEN ? ELSE title END, updated_at=? WHERE session_id=?",
            (role, _derive_agent_session_title(content), now, session_id),
        )
        c.execute(
            "UPDATE agent_memory_spaces SET updated_at=? WHERE space_id=(SELECT space_id FROM agent_sessions WHERE session_id=?)",
            (now, session_id),
        )
        c.commit()


def get_agent_messages(session_id: str, limit: int = 12) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content, created_at FROM agent_messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def update_agent_session_summary(session_id: str, summary: str, active_goal: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE agent_sessions SET summary=?, active_goal=?, updated_at=? WHERE session_id=?",
            (summary[:3000], active_goal[:500], datetime.now().isoformat(), session_id),
        )
        c.commit()


def get_agent_session(session_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM agent_sessions WHERE session_id=?", (session_id,)).fetchone()
    return dict(row) if row else None


def add_agent_memory(memory_type: str, content: str, keywords: str, importance: int = 1, source: str = "user", space_id: str = "") -> dict:
    now = datetime.now().isoformat()
    with _conn() as c:
        cursor = c.execute(
            "INSERT INTO agent_memories(space_id,memory_type,content,keywords,importance,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (space_id, memory_type, content[:1000], keywords[:500], max(1, min(5, importance)), source, now, now),
        )
        c.commit()
    return {"id": cursor.lastrowid, "space_id": space_id, "memory_type": memory_type, "content": content[:1000]}


def search_agent_memories(tokens: list[str], limit: int = 5, space_id: str = "default") -> list[dict]:
    with _conn() as c:
        rows = [dict(row) for row in c.execute("SELECT * FROM agent_memories WHERE space_id=? ORDER BY importance DESC, updated_at DESC", (space_id,)).fetchall()]
    token_set = {token.lower() for token in tokens if len(token.strip()) >= 2}
    ranked = []
    for row in rows:
        haystack = f"{row['content']} {row['keywords']}".lower()
        score = row["importance"] + sum(token in haystack for token in token_set)
        if not token_set or score > row["importance"]:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
    selected = [row for _, row in ranked[:limit]]
    if selected:
        now = datetime.now().isoformat()
        with _conn() as c:
            c.executemany("UPDATE agent_memories SET last_used_at=? WHERE id=?", [(now, row["id"]) for row in selected])
            c.commit()
    return selected


def list_agent_memories(limit: int = 50, space_id: str = "default") -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM agent_memories WHERE space_id=? ORDER BY importance DESC, updated_at DESC LIMIT ?", (space_id, limit)).fetchall()
    return [dict(row) for row in rows]


# 启动时初始化
init_db()
