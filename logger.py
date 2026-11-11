"""
The request log (Phase 4, Step 1, built first because Phase 3 writes to it).

Every request the router handles becomes one row in a SQLite database file,
autopilot.db. The verifier (Phase 3) and the dashboard (Phase 4) use it too.
"""

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DB_FILE = os.getenv("AUTOPILOT_DB", "autopilot.db")

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

# Columns added after the first version. init_db() adds any that an older
# autopilot.db is missing, so existing data is kept.
NEW_COLUMNS = {
    "task_type": "TEXT",          # extraction, classification, summarization, or open_ended
    "quality_passed": "INTEGER",  # 1 = passed, 0 = failed (a routing failure), empty = not checked
    "quality_detail": "TEXT",     # Why it passed or failed
    "escalated_score": "REAL",    # Quality score of the stronger model's answer
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
                   passed: bool | None, detail: str) -> None:
    """Save the verifier's verdict on one request."""
    conn = _connect()
    try:
        conn.execute(
            """UPDATE requests
               SET task_type = ?, quality_score = ?, quality_passed = ?, quality_detail = ?
               WHERE id = ?""",
            (task_type, score, None if passed is None else int(passed), detail, request_id),
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