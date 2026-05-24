"""
SQLite 持久化层 — 用户、自选股列表、分析结果缓存、风险日记。
"""
import sqlite3
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "watchlist.db")

MAX_WATCHLIST = 10  # 自选股上限


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
                user_id   INTEGER NOT NULL,
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
        # 兼容旧表：如果 name 列不存在则添加
        try:
            c.execute("ALTER TABLE watchlist_analysis ADD COLUMN name TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在
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
        c.commit()


# ── 用户 CRUD ────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> dict:
    with _conn() as c:
        try:
            cursor = c.execute(
                "INSERT INTO users(username, password, created_at) VALUES(?,?,?)",
                (username, password_hash, datetime.now().isoformat()),
            )
            c.commit()
            user_id = cursor.lastrowid
            return {"ok": True, "user_id": user_id}
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
    return True


def update_stock_name(code: str, name: str):
    """更新所有用户自选股中该股票的名称"""
    with _conn() as c:
        c.execute("UPDATE watchlist SET name=? WHERE code=?", (name, code))
        c.commit()


# ── 分析结果缓存 ─────────────────────────────────────────────────

def get_analysis(code: str):
    """返回当日有效的分析结果，过期返回 None"""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM watchlist_analysis WHERE code=?",
            (code,)
        ).fetchone()
    if not row:
        return None
    row = dict(row)
    today = datetime.now().strftime("%Y-%m-%d")
    updated = (row.get("updated_at") or "")[:10]
    if updated != today:
        return None
    try:
        row["score_basis"] = json.loads(row["score_basis"] or "{}")
    except Exception:
        row["score_basis"] = {}
    try:
        row["news_json"] = json.loads(row["news_json"] or "[]")
    except Exception:
        row["news_json"] = []
    return row


def save_analysis(code: str, data: dict):
    basis_str = json.dumps(data.get("score_basis", {}), ensure_ascii=False)
    news_str = json.dumps(data.get("news_json", []), ensure_ascii=False)
    name = data.get("name", "")
    with _conn() as c:
        c.execute("""
            INSERT INTO watchlist_analysis
              (code, name, fundamental_stars, news_stars, risk_stars, overall_stars,
               brief, score_basis, news_json, wordcloud_b64, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET
              name=excluded.name,
              fundamental_stars=excluded.fundamental_stars,
              news_stars=excluded.news_stars,
              risk_stars=excluded.risk_stars,
              overall_stars=excluded.overall_stars,
              brief=excluded.brief,
              score_basis=excluded.score_basis,
              news_json=excluded.news_json,
              wordcloud_b64=excluded.wordcloud_b64,
              updated_at=excluded.updated_at
        """, (
            code, name,
            data.get("fundamental_stars", 3),
            data.get("news_stars", 3),
            data.get("risk_stars", 3),
            data.get("overall_stars", 3),
            data.get("brief", ""),
            basis_str,
            news_str,
            data.get("wordcloud_b64", ""),
            datetime.now().isoformat(),
        ))
        c.commit()


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


# 启动时初始化
init_db()
