import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .classifier import Classification
from .sources import Message

DEFAULT_DB_PATH = "~/.local/share/msgsift/sift.db"

PASSIVE_LABELS = ("FYI", "NEWSLETTER")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT,
    sender TEXT,
    subject TEXT,
    snippet TEXT,
    title TEXT NOT NULL,
    label TEXT,
    reason TEXT,
    suggested_reply TEXT,
    forward_to TEXT,
    forward_note TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS summaries (
    day TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def today_str() -> str:
    return date.today().isoformat()


@dataclass
class Item:
    id: int
    source: str
    external_id: str | None
    sender: str | None
    subject: str | None
    snippet: str | None
    title: str
    label: str | None
    reason: str | None
    suggested_reply: str | None
    forward_to: str | None
    forward_note: str | None
    done: bool
    day: str
    created_at: str

    @property
    def is_manual(self) -> bool:
        return self.source == "manual"


def _db_path(config: dict) -> Path:
    raw = config.get("storage", {}).get("db_path", DEFAULT_DB_PATH)
    return Path(raw).expanduser()


def connect(config: dict) -> sqlite3.Connection:
    path = _db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(items)")]
    if "day" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN day TEXT")
        conn.execute("UPDATE items SET day = substr(created_at, 1, 10) WHERE day IS NULL")
        conn.commit()


def item_exists(conn: sqlite3.Connection, source: str, external_id: str | None) -> bool:
    if external_id is None:
        return False
    row = conn.execute(
        "SELECT 1 FROM items WHERE source = ? AND external_id = ? LIMIT 1",
        (source, external_id),
    ).fetchone()
    return row is not None


def upsert_email(conn: sqlite3.Connection, msg: Message, cls: Classification) -> None:
    conn.execute(
        """
        INSERT INTO items (
            source, external_id, sender, subject, snippet, title,
            label, reason, suggested_reply, forward_to, forward_note, day, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            sender = excluded.sender,
            subject = excluded.subject,
            snippet = excluded.snippet,
            title = excluded.title,
            label = excluded.label,
            reason = excluded.reason,
            suggested_reply = excluded.suggested_reply,
            forward_to = excluded.forward_to,
            forward_note = excluded.forward_note
        """,
        (
            msg.source,
            msg.id,
            msg.sender,
            msg.subject,
            msg.snippet,
            msg.subject or "(no subject)",
            cls.label,
            cls.reason,
            cls.suggested_reply,
            cls.forward_to,
            cls.forward_note,
            today_str(),
            msg.timestamp.isoformat(),
        ),
    )
    conn.commit()


def add_manual_todo(conn: sqlite3.Connection, title: str, note: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO items (source, external_id, title, label, reason, day, created_at)
        VALUES ('manual', NULL, ?, 'ACTION_REQUIRED', ?, ?, ?)
        """,
        (title, note, today_str(), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def set_done(conn: sqlite3.Connection, item_id: int, done: bool = True) -> None:
    conn.execute("UPDATE items SET done = ? WHERE id = ?", (1 if done else 0, item_id))
    conn.commit()


def list_items(conn: sqlite3.Connection, include_done: bool = False) -> list[Item]:
    query = "SELECT * FROM items"
    if not include_done:
        query += " WHERE done = 0"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query).fetchall()
    return [_row_to_item(r) for r in rows]


def items_for_day(conn: sqlite3.Connection, day: str) -> list[Item]:
    rows = conn.execute(
        "SELECT * FROM items WHERE day = ? ORDER BY done, created_at DESC", (day,)
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def rollover(conn: sqlite3.Connection, cutoff_day: str | None = None) -> None:
    cutoff = cutoff_day or today_str()
    next_day = (date.fromisoformat(cutoff) + timedelta(days=1)).isoformat()
    placeholders = ", ".join("?" * len(PASSIVE_LABELS))
    # auto-close passive items (FYI / NEWSLETTER) on the closed day(s)
    conn.execute(
        f"UPDATE items SET done = 1 "
        f"WHERE done = 0 AND day <= ? AND label IN ({placeholders})",
        (cutoff, *PASSIVE_LABELS),
    )
    # push remaining unfinished items (action / manual) to the next day
    conn.execute(
        "UPDATE items SET day = ? WHERE done = 0 AND day <= ?",
        (next_day, cutoff),
    )
    conn.commit()


def set_summary(conn: sqlite3.Connection, day: str, text: str) -> None:
    conn.execute(
        "INSERT INTO summaries (day, text, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(day) DO UPDATE SET text = excluded.text, created_at = excluded.created_at",
        (day, text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_summary(conn: sqlite3.Connection, day: str) -> str | None:
    row = conn.execute("SELECT text FROM summaries WHERE day = ?", (day,)).fetchone()
    return row["text"] if row else None


def list_days(conn: sqlite3.Connection, limit: int = 14) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT day FROM items ORDER BY day DESC LIMIT ?", (limit,)
    ).fetchall()
    return [r["day"] for r in rows]


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        source=row["source"],
        external_id=row["external_id"],
        sender=row["sender"],
        subject=row["subject"],
        snippet=row["snippet"],
        title=row["title"],
        label=row["label"],
        reason=row["reason"],
        suggested_reply=row["suggested_reply"],
        forward_to=row["forward_to"],
        forward_note=row["forward_note"],
        done=bool(row["done"]),
        day=row["day"],
        created_at=row["created_at"],
    )
