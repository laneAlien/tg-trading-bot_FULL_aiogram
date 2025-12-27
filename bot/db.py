import aiosqlite
from datetime import datetime, timedelta, timezone

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  created_at TEXT NOT NULL,
  is_whitelisted INTEGER NOT NULL DEFAULT 0,
  access_until TEXT,
  active_symbol TEXT,
  accepted_disclaimer_at TEXT
);

CREATE TABLE IF NOT EXISTS favorites (
  user_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS tickets (
  ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  closed_at TEXT
);

CREATE TABLE IF NOT EXISTS ticket_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id INTEGER NOT NULL,
  sender TEXT NOT NULL,
  text TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  payload TEXT NOT NULL UNIQUE,
  stars_amount INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  paid_at TEXT
);
"""

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def upsert_user(db_path: str, user_id: int, username: str | None) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
            """,
            (user_id, username, now_iso()),
        )
        await db.commit()

async def set_disclaimer(db_path: str, user_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE users SET accepted_disclaimer_at=? WHERE user_id=?", (now_iso(), user_id))
        await db.commit()

async def set_active_symbol(db_path: str, user_id: int, symbol: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE users SET active_symbol=? WHERE user_id=?", (symbol, user_id))
        await db.commit()

async def get_user(db_path: str, user_id: int) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def is_access_active(db_path: str, user_id: int) -> bool:
    u = await get_user(db_path, user_id)
    if not u:
        return False
    if u.get("is_whitelisted") == 1:
        return True
    until = u.get("access_until")
    if not until:
        return False
    try:
        dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
    except Exception:
        return False
    return dt > datetime.now(timezone.utc)

async def grant_access_30d(db_path: str, user_id: int) -> None:
    until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE users SET access_until=? WHERE user_id=?", (until, user_id))
        await db.commit()

async def set_whitelist(db_path: str, user_id: int, value: bool) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE users SET is_whitelisted=? WHERE user_id=?", (1 if value else 0, user_id))
        await db.commit()

# Favorites
async def add_favorite(db_path: str, user_id: int, symbol: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO favorites (user_id, symbol, created_at) VALUES (?, ?, ?)",
            (user_id, symbol, now_iso()),
        )
        await db.commit()

async def remove_favorite(db_path: str, user_id: int, symbol: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM favorites WHERE user_id=? AND symbol=?", (user_id, symbol))
        await db.commit()

async def list_favorites(db_path: str, user_id: int, limit: int = 30) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT symbol FROM favorites WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

# Tickets
async def create_ticket(db_path: str, user_id: int, text: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "INSERT INTO tickets (user_id, status, created_at) VALUES (?, 'open', ?)",
            (user_id, now_iso()),
        )
        ticket_id = cur.lastrowid
        await db.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?, 'user', ?, ?)",
            (ticket_id, text, now_iso()),
        )
        await db.commit()
        return int(ticket_id)

async def add_ticket_message(db_path: str, ticket_id: int, sender: str, text: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, sender, text, now_iso()),
        )
        await db.commit()

async def close_ticket(db_path: str, ticket_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE tickets SET status='closed', closed_at=? WHERE ticket_id=?", (now_iso(), ticket_id))
        await db.commit()

async def get_open_tickets(db_path: str, limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE status='open' ORDER BY ticket_id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

# Journal
async def add_journal(db_path: str, user_id: int, text: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO journal_entries (user_id, text, created_at) VALUES (?, ?, ?)",
            (user_id, text, now_iso()),
        )
        await db.commit()

async def list_journal(db_path: str, user_id: int, limit: int = 20) -> list[tuple[str,str]]:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT created_at, text FROM journal_entries WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [(r[0], r[1]) for r in rows]

# Payments
async def create_payment(db_path: str, user_id: int, payload: str, stars_amount: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO payments (user_id, payload, stars_amount, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (user_id, payload, stars_amount, now_iso()),
        )
        await db.commit()

async def mark_payment_paid(db_path: str, payload: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE payments SET status='paid', paid_at=? WHERE payload=?", (now_iso(), payload))
        await db.commit()

async def get_payment(db_path: str, payload: str) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM payments WHERE payload=?", (payload,))
        row = await cur.fetchone()
        return dict(row) if row else None
