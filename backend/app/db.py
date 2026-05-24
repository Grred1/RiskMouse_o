"""
SQLite 持久化层 — 自选股列表 + 分析结果缓存。
所有用户共用同一数据库（黑客松演示模式）。
"""
import sqlite3
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 部署环境使用当前工作目录（可写），本地开发保持原路径
if os.getenv("COZE_ENV") or os.getenv("PORT"):
    DB_PATH = os.path.join(os.getcwd(), "watchlist.db")
else:
    DB_PATH = os.path.join(BASE_DIR, "watchlist.db")

MAX_WATCHLIST = 10  # 自选股上限


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                code      TEXT UNIQUE NOT NULL,
                name      TEXT,
                added_at  TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_analysis (
                code               TEXT PRIMARY KEY,
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
        c.commit()


# ── 自选股 CRUD ─────────────────────────────────────────────────

def get_watchlist() -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT code, name, added_at FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def add_stock(code: str, name: str = "") -> dict:
    """返回 {"ok": bool, "msg": str}"""
    with _conn() as c:
        count = c.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        if count >= MAX_WATCHLIST:
            return {"ok": False, "msg": f"自选股最多 {MAX_WATCHLIST} 只"}
        try:
            c.execute(
                "INSERT OR IGNORE INTO watchlist(code, name, added_at) VALUES(?,?,?)",
                (code, name, datetime.now().isoformat()),
            )
            c.commit()
            return {"ok": True, "msg": "已添加"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}


def remove_stock(code: str) -> bool:
    with _conn() as c:
        c.execute("DELETE FROM watchlist WHERE code=?", (code,))
        c.execute("DELETE FROM watchlist_analysis WHERE code=?", (code,))
        c.commit()
    return True


def update_stock_name(code: str, name: str):
    with _conn() as c:
        c.execute("UPDATE watchlist SET name=? WHERE code=?", (name, code))
        c.commit()


# ── 分析结果缓存 ─────────────────────────────────────────────────

def get_analysis(code: str):
    """返回当日有效的分析结果，过期返回 None"""
    with _conn() as c:
        row = c.execute(
            """SELECT a.*, w.name FROM watchlist_analysis a
               LEFT JOIN watchlist w ON a.code = w.code
               WHERE a.code=?""",
            (code,)
        ).fetchone()
    if not row:
        return None
    row = dict(row)
    today = datetime.now().strftime("%Y-%m-%d")
    updated = (row.get("updated_at") or "")[:10]
    if updated != today:
        return None  # 缓存过期
    # 反序列化 JSON 字段
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
    with _conn() as c:
        c.execute("""
            INSERT INTO watchlist_analysis
              (code, fundamental_stars, news_stars, risk_stars, overall_stars,
               brief, score_basis, news_json, wordcloud_b64, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET
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
            code,
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


# 启动时初始化
init_db()
