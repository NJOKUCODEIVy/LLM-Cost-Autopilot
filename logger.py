"""
The request log (Phase 4, Step 1, built first because Phase 3 writes to it).

Every request the router handles becomes one row in a SQLite database file,
autopilot.db. The verifier (Phase 3) and the dashboard (Phase 4) use it too.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone

DB_FILE = "autopilot.db"

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


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Lets us read columns by name, like row["model"]
    return conn


def init_db() -> None:
    """Create the requests table if it doesn't exist yet."""
    conn = _connect()
    try:
        conn.execute(SCHEMA)
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
    print(f"{'id':>3}  {'time (UTC)':<19}  {'tier':>4}  {'model':<22} {'cost':>11} {'latency':>8}  note")
    for r in rows:
        note = f"fallback from {r['fallback_from']}" if r["fallback_from"] else ""
        print(f"{r['id']:>3}  {r['timestamp'][:19]:<19}  {r['tier']:>4}  {r['model']:<22} "
              f"{'$' + format(r['cost'], '.7f'):>11} {r['latency']:>7.2f}s  {note}")