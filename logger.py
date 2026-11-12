"""
The request log (Phase 4, Step 1, built first because Phase 3 writes to it).

Every request the router handles becomes one row in a SQLite database file,
autopilot.db. The verifier (Phase 3) and the dashboard (Phase 4) use it too.
"""

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from paths import DEFAULT_DB

# Where the database lives. Docker and the app set AUTOPILOT_DB; otherwise it is db/autopilot.db.
DB_FILE = os.getenv("AUTOPILOT_DB", str(DEFAULT_DB))

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,            -- When it happened (UTC)
    prompt_hash     TEXT    NOT NULL,            -- Fingerprint of the prompt; the text is not stored
    tier            INTEGER NOT NULL,            -- Predicted complexity tier (1, 2, or 3)
    model           TEXT    NOT NULL,            -- Model that answered
    fallback_from   TEXT,                        -- Routed model that failed, if a fallback answered
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    cost            REAL    NOT NULL,            -- USD, at registry prices
    latency         REAL    NOT NULL,            -- Seconds
    quality_score   REAL,                        -- Set by the verifier; empty until checked
    escalated       INTEGER NOT NULL DEFAULT 0,  -- 1 if re-run on a stronger model
    escalated_model TEXT,                        -- Which stronger model, if escalated
    escalation_cost REAL                         -- Extra USD spent on the re-run
)
"""

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_key    TEXT PRIMARY KEY,           -- SHA-256 fingerprint of the Google account ID; no name or email is stored
    first_seen  TEXT NOT NULL,              -- When they first signed in (their sign-up)
    last_seen   TEXT NOT NULL,              -- Their most recent visit
    visits      INTEGER NOT NULL DEFAULT 1  -- How many sessions they've started
)
"""

# Columns added after the first version. init_db() adds any that an older
# autopilot.db is missing, so existing data is kept.
NEW_COLUMNS = {
    "task_type": "TEXT",          # extraction, classification, summarization, or open_ended
    "quality_passed": "INTEGER",  # 1 = passed, 0 = failed (a routing failure), empty = not checked
    "quality_detail": "TEXT",     # Why it passed or failed
    "escalated_score": "REAL",    # Quality score of the stronger model's answer
    "verification_cost": "REAL",  # USD the verifier spent checking this answer (reference + judge)
    "user_rating": "INTEGER",     # From the chat app: 1 = thumbs up, 0 = thumbs down, empty = no rating
    "user_key": "TEXT",           # From the chat app: which signed-in account sent it (a fingerprint)
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Lets us read columns by name, like row["model"]
    return conn


def init_db() -> None:
    """Create the requests table if needed, and add any newer columns it's missing."""
    conn = _connect()
    try:
        conn.execute(SCHEMA)
        conn.execute(USERS_SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(requests)")}
        for column, column_type in NEW_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE requests ADD COLUMN {column} {column_type}")
        conn.commit()
    finally:
        conn.close()


def hash_prompt(prompt: str) -> str:
    """Return a SHA-256 fingerprint: the same prompt always gives the same hash."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def log_request(prompt: str, tier: int, model: str, input_tokens: int,
                output_tokens: int, cost: float, latency: float,
                fallback_from: str | None = None) -> int:
    """Save one request and return its row id, so the verifier can update it later."""
    conn = _connect()
    try:
        cursor = conn.execute(
            """INSERT INTO requests
               (timestamp, prompt_hash, tier, model, fallback_from,
                input_tokens, output_tokens, cost, latency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), hash_prompt(prompt), tier, model,
             fallback_from, input_tokens, output_tokens, cost, latency),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def record_quality(request_id: int, task_type: str, score: float | None,
                   passed: bool | None, detail: str, verification_cost: float = 0.0) -> None:
    """Save the verifier's verdict on one request, and what the check cost."""
    conn = _connect()
    try:
        conn.execute(
            """UPDATE requests
               SET task_type = ?, quality_score = ?, quality_passed = ?, quality_detail = ?,
                   verification_cost = ?
               WHERE id = ?""",
            (task_type, score, None if passed is None else int(passed), detail,
             verification_cost, request_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_escalation(request_id: int, escalated_model: str,
                      escalation_cost: float, escalated_score: float | None) -> None:
    """Save the details of a re-run on a stronger model (used in the escalation step)."""
    conn = _connect()
    try:
        conn.execute(
            """UPDATE requests
               SET escalated = 1, escalated_model = ?, escalation_cost = ?, escalated_score = ?
               WHERE id = ?""",
            (escalated_model, escalation_cost, escalated_score, request_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_rating(request_id: int, rating: int | None) -> None:
    """Save a person's thumbs up (1) or thumbs down (0) on a response."""
    conn = _connect()
    try:
        conn.execute("UPDATE requests SET user_rating = ? WHERE id = ?", (rating, request_id))
        conn.commit()
    finally:
        conn.close()


def get_request(request_id: int) -> sqlite3.Row | None:
    """Return one logged request, or None if it doesn't exist."""
    conn = _connect()
    try:
        return conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    finally:
        conn.close()


def register_user(user_key: str) -> bool:
    """Record a visit. Returns True the first time this account signs in (their sign-up)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (user_key, first_seen, last_seen) VALUES (?, ?, ?)",
            (user_key, now, now),
        )
        is_new = cursor.rowcount == 1
        if not is_new:
            conn.execute("UPDATE users SET last_seen = ?, visits = visits + 1 WHERE user_key = ?",
                         (now, user_key))
        conn.commit()
        return is_new
    finally:
        conn.close()


def set_request_user(request_id: int, user_key: str) -> None:
    """Link a logged request to the account that sent it, for daily limits."""
    conn = _connect()
    try:
        conn.execute("UPDATE requests SET user_key = ? WHERE id = ?", (user_key, request_id))
        conn.commit()
    finally:
        conn.close()


def count_requests_today(user_key: str | None = None) -> int:
    """Requests since midnight UTC, for one account or (with no user_key) for everyone."""
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    conn = _connect()
    try:
        if user_key is None:
            row = conn.execute("SELECT COUNT(*) FROM requests WHERE timestamp >= ?", (midnight,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM requests WHERE user_key = ? AND timestamp >= ?",
                               (user_key, midnight)).fetchone()
        return int(row[0])
    finally:
        conn.close()


def count_users() -> int:
    conn = _connect()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        conn.close()


def cost_rows() -> list[sqlite3.Row]:
    """Token counts and every cost component for each request, for savings totals."""
    conn = _connect()
    try:
        return conn.execute(
            """SELECT input_tokens, output_tokens, cost,
                      COALESCE(verification_cost, 0) AS verification_cost,
                      COALESCE(escalation_cost, 0) AS escalation_cost
               FROM requests"""
        ).fetchall()
    finally:
        conn.close()


def recent_requests(limit: int = 10) -> list[sqlite3.Row]:
    """Return the most recent rows, newest first."""
    conn = _connect()
    try:
        return conn.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()


# Make sure the table exists as soon as any file imports this one
init_db()


if __name__ == "__main__":
    rows = recent_requests()
    print(f"Last {len(rows)} requests in {DB_FILE}:\n")
    print(f"{'id':>3}  {'tier':>4}  {'model':<22} {'cost':>11} {'latency':>8}  {'quality':<10} note")
    for r in rows:
        if r["quality_passed"] is None:
            quality = "-"
        else:
            quality = f"{'pass' if r['quality_passed'] else 'FAIL'} {r['quality_score']:.0f}/5"
        notes = []
        if r["fallback_from"]:
            notes.append(f"fallback from {r['fallback_from']}")
        if r["quality_detail"]:
            notes.append(r["quality_detail"])
        print(f"{r['id']:>3}  {r['tier']:>4}  {r['model']:<22} "
              f"{'$' + format(r['cost'], '.7f'):>11} {r['latency']:>7.2f}s  {quality:<10} {'; '.join(notes)}")
