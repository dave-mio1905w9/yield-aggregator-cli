import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Set, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    last_checked_at TEXT,
    etag TEXT,
    last_modified TEXT
);

CREATE TABLE IF NOT EXISTS seen_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER NOT NULL,
    guid TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    FOREIGN KEY(feed_id) REFERENCES feeds(id) ON DELETE CASCADE,
    UNIQUE(feed_id, guid)
);

CREATE INDEX IF NOT EXISTS idx_seen_guid ON seen_items(feed_id, guid);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Open sqlite connection and run migrations if tables don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def add_feed(conn: sqlite3.Connection, url: str, title: Optional[str] = None) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feeds (url, title) VALUES (?, ?) ON CONFLICT(url) DO UPDATE SET title=COALESCE(excluded.title, feeds.title) RETURNING id;",
        (url, title)
    )
    row = cur.fetchone()
    conn.commit()
    return row[0]


def remove_feed(conn: sqlite3.Connection, url_or_id: str) -> bool:
    cur = conn.cursor()
    if url_or_id.isdigit():
        cur.execute("DELETE FROM feeds WHERE id = ?", (int(url_or_id),))
    else:
        cur.execute("DELETE FROM feeds WHERE url = ?", (url_or_id,))
    conn.commit()
    return cur.rowcount > 0


def list_feeds(conn: sqlite3.Connection) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
    cur = conn.cursor()
    cur.execute("SELECT id, url, title, last_checked_at FROM feeds ORDER BY id ASC")
    return cur.fetchall()


def get_feed(conn: sqlite3.Connection, feed_id: int) -> Optional[Tuple[int, str, Optional[str], Optional[str], Optional[str]]]:
    cur = conn.cursor()
    cur.execute("SELECT id, url, title, etag, last_modified FROM feeds WHERE id = ?", (feed_id,))
    return cur.fetchone()


def is_item_seen(conn: sqlite3.Connection, feed_id: int, guid: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM seen_items WHERE feed_id = ? AND guid = ? LIMIT 1", (feed_id, guid))
    return cur.fetchone() is not None


def filter_unseen_guids(conn: sqlite3.Connection, feed_id: int, guids: Iterable[str]) -> Set[str]:
    guid_list = list(guids)
    if not guid_list:
        return set()
    
    # sqlite has a variable limit (usually 999), chunk in batches of 500
    seen: Set[str] = set()
    for i in range(0, len(guid_list), 500):
        chunk = guid_list[i:i+500]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.cursor()
        cur.execute(
            f"SELECT guid FROM seen_items WHERE feed_id = ? AND guid IN ({placeholders})",
            [feed_id] + chunk
        )
        for row in cur.fetchall():
            seen.add(row[0])
            
    return set(guid_list) - seen


def mark_items_seen(conn: sqlite3.Connection, feed_id: int, guids: Iterable[str]) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = [(feed_id, g, now_iso) for g in guids]
    if not payload:
        return
    conn.executemany(
        "INSERT OR IGNORE INTO seen_items (feed_id, guid, seen_at) VALUES (?, ?, ?)",
        payload
    )
    conn.commit()


def update_feed_http_state(conn: sqlite3.Connection, feed_id: int, etag: Optional[str], last_modified: Optional[str]) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE feeds SET etag = ?, last_modified = ?, last_checked_at = ? WHERE id = ?",
        (etag, last_modified, now_iso, feed_id)
    )
    conn.commit()
