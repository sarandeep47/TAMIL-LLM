"""
memory_db.py — Single source of truth for all persistent personal memory.

Schema (memories table):
    fact_key         TEXT UNIQUE   – canonical key, e.g. "user_name"
    fact_value       TEXT          – primary (English / romanised) value
    tamil_value      TEXT          – Tamil-script equivalent (optional)
    category         TEXT          – e.g. "identity", "interest"
    confidence       REAL          – 0.0–1.0; manual = 1.0
    source           TEXT          – "manual", "regex", or "ai"
    updated_at       TEXT          – ISO-8601 timestamp of last update
    education_status TEXT          – 'current' | 'past' | NULL
                                     Only used for user_school rows.
                                     'current'  → user said "padikuren" / "am studying"
                                     'past'     → user said "padichen" / "studied at"
                                     NULL        → unknown / not specified

Migration: every initialize_database() call is safe to run on an existing DB;
missing columns are added and known category mismatches are corrected.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

# Use absolute path based on this file's location, not current working directory.
# If TAMIL_LLM_DB_ROOT environment variable is set (by backend/main.py),
# use that as the root. This ensures backend and terminal chatbot use same DB.
_db_root = os.environ.get('TAMIL_LLM_DB_ROOT')
if _db_root:
    DB_PATH = Path(_db_root) / "data" / "processed" / "memory.db"
else:
    DB_PATH = Path(__file__).parent / "data" / "processed" / "memory.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Category back-fill: correct known keys that have wrong category in DB ────

_CANONICAL_CATEGORIES: dict[str, str] = {
    "user_name":                "identity",
    "user_location":            "identity",
    "user_workplace":           "work",
    "user_job_title":           "work",
    "user_school":              "education",
    "user_field_of_study":      "education",
    "user_learning":            "learning",
    "user_interest":            "interest",
    "user_skill":               "skill",
    "user_goal":                "goal",
    "user_language_preference": "preference",
    "user_response_style":      "preference",
    "favorite_colour":          "preference",
    "preferred_language":       "preference",   # legacy key
}

# Columns that must exist — used for safe migration
_REQUIRED_COLUMNS: dict[str, str] = {
    "tamil_value":      "TEXT",
    "category":         "TEXT DEFAULT 'general'",
    "confidence":       "REAL DEFAULT 1.0",
    "source":           "TEXT DEFAULT 'manual'",
    "updated_at":       "TEXT",
    "education_status": "TEXT",
}

_COLUMN_DEFAULTS: dict[str, str] = {
    "tamil_value":      "NULL",
    "category":         "'general'",
    "confidence":       "1.0",
    "source":           "'manual'",
    "updated_at":       "NULL",
    "education_status": "NULL",
}


def initialize_database() -> None:
    """
    Create the memories table if it doesn't exist.
    Add any columns missing in older DBs.
    Correct category labels for known keys.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_key    TEXT NOT NULL UNIQUE,
                fact_value  TEXT NOT NULL,
                tamil_value TEXT,
                category    TEXT DEFAULT 'general',
                confidence  REAL DEFAULT 1.0,
                source      TEXT DEFAULT 'manual',
                updated_at  TEXT
            )
        """)
        conn.commit()

        # ── Add missing columns (safe for old DBs) ────────────────────────
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        for col, definition in _REQUIRED_COLUMNS.items():
            if col not in existing_cols:
                default = _COLUMN_DEFAULTS.get(col, "NULL")
                conn.execute(
                    f"ALTER TABLE memories ADD COLUMN {col} {definition} "
                    f"DEFAULT {default}"
                )
        conn.commit()

        # ── Back-fill correct categories for known keys ───────────────────
        for fact_key, correct_category in _CANONICAL_CATEGORIES.items():
            conn.execute(
                "UPDATE memories SET category = ? "
                "WHERE fact_key = ? AND category != ?",
                (correct_category, fact_key, correct_category),
            )
        conn.commit()


def save_memory(
    fact_key: str,
    fact_value: str,
    tamil_value: str | None = None,
    category: str = "general",
    confidence: float = 1.0,
    source: str = "manual",
    education_status: str | None = None,
) -> None:
    """
    Upsert a personal fact.

    Write rules (in priority order):
      1. Manual facts (source='manual') can ONLY be overwritten by manual writes.
      2. Regex/tanglish facts can overwrite AI facts (AI has higher false-positive rate).
      3. AI facts can only overwrite other AI facts if the new confidence is higher.
      4. Do not downgrade confidence for any source.
    """
    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            "SELECT confidence, source FROM memories WHERE fact_key = ?",
            (fact_key,),
        ).fetchone()

        if existing:
            ex_conf, ex_src = existing
            
            # Rule 1: Manual facts cannot be overwritten by non-manual
            if ex_src == "manual" and source != "manual":
                return
            
            # Rule 2: AI facts can be overwritten by regex/tanglish (AI is less reliable)
            if ex_src == "ai" and source in ("regex", "tanglish"):
                # Allow regex/tanglish to override AI
                # This fixes cases where AI misclassifies (e.g., college as location)
                pass
            
            # Rule 3: AI can only overwrite other AI if confidence improves
            elif source == "ai":
                if ex_src == "manual":
                    return
                if ex_src == "regex" and confidence < 1.0:
                    return   # AI cannot overwrite a regex fact
                if ex_src == "ai" and ex_conf >= confidence:
                    return   # don't downgrade AI confidence
            
            # Rule 4: Do not downgrade any fact
            elif confidence < ex_conf:
                return

        conn.execute(
            """
            INSERT INTO memories
                (fact_key, fact_value, tamil_value, category, confidence,
                 source, updated_at, education_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fact_key) DO UPDATE SET
                fact_value       = excluded.fact_value,
                tamil_value      = COALESCE(excluded.tamil_value, tamil_value),
                category         = excluded.category,
                confidence       = excluded.confidence,
                source           = excluded.source,
                updated_at       = excluded.updated_at,
                education_status = COALESCE(excluded.education_status, education_status)
            """,
            (
                fact_key,
                fact_value,
                tamil_value,
                category,
                confidence,
                source,
                datetime.now().isoformat(timespec="seconds"),
                education_status,
            ),
        )


def get_memory(fact_key: str, language: str = "english") -> str | None:
    """
    Return the stored value for fact_key, or None.

    If language == 'tamil' and a tamil_value is stored, return that.
    Otherwise return fact_value (English/romanised).
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT fact_value, tamil_value FROM memories WHERE fact_key = ?",
            (fact_key,),
        ).fetchone()

    if row is None:
        return None

    fact_value, tamil_value = row
    if language == "tamil" and tamil_value:
        return tamil_value
    return fact_value


def get_education_status(fact_key: str = "user_school") -> str | None:
    """
    Return the education_status for user_school: 'current', 'past', or None.
    None means the status was not recorded (e.g. saved via /remember).
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT education_status FROM memories WHERE fact_key = ?",
            (fact_key,),
        ).fetchone()
    if row is None:
        return None
    return row[0]  # may be None if column is NULL


def forget_memory(fact_key: str) -> bool:
    """Delete a stored fact. Returns True if a row was deleted."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE fact_key = ?", (fact_key,)
        )
        return cursor.rowcount > 0


def list_memories() -> list[dict]:
    """Return all stored facts as a list of dicts, ordered by category then key."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT fact_key, fact_value, tamil_value, category,
                   confidence, source, updated_at, education_status
            FROM memories
            ORDER BY category, fact_key
            """
        ).fetchall()
    return [
        {
            "key":              row[0],
            "value":            row[1],
            "tamil":            row[2],
            "category":         row[3],
            "confidence":       row[4],
            "source":           row[5],
            "updated_at":       row[6],
            "education_status": row[7],
        }
        for row in rows
    ]


def show_all_memories() -> list[tuple]:
    """Legacy helper for backward compatibility."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT fact_key, fact_value, tamil_value FROM memories ORDER BY fact_key"
        ).fetchall()


def get_memory_fuzzy(key: str, threshold: float = 0.80) -> tuple[str, str, float] | None:
    """
    Retrieve a fact from memory using fuzzy matching on the stored key.
    
    This allows approximate key matches, useful for synonyms or typos.
    Uses difflib.SequenceMatcher for similarity scoring.
    
    Args:
        key: The fact key to search for (may be approximate)
        threshold: Minimum similarity score (0.0–1.0) to accept a match
    
    Returns:
        (value, retrieval_method, confidence_score) if match >= threshold, else None
    
    Retrieval methods: 'exact', 'fuzzy', 'similar_key'
    """
    from difflib import SequenceMatcher
    
    # Try exact match first
    exact_match = get_memory(key, language="english")
    if exact_match:
        return (exact_match, "exact", 1.0)
    
    # Fuzzy search through all keys
    with sqlite3.connect(DB_PATH) as conn:
        all_rows = conn.execute(
            "SELECT fact_key, fact_value FROM memories ORDER BY fact_key"
        ).fetchall()
    
    best_match = None
    best_score = 0.0
    best_value = None
    
    key_lower = key.lower()
    for stored_key, stored_value in all_rows:
        stored_key_lower = stored_key.lower()
        similarity = SequenceMatcher(None, key_lower, stored_key_lower).ratio()
        
        if similarity > best_score:
            best_score = similarity
            best_match = stored_key
            best_value = stored_value
    
    if best_score >= threshold:
        return (best_value, "fuzzy", best_score)
    
    return None


# ── CLI entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    initialize_database()
    print("Database initialised!\n\nStored memories:")
    for m in list_memories():
        print(
            f"  {m['key']:25s} = {m['value']:20s}"
            f"  [{m['category']:10s}  src={m['source']:6s}  conf={m['confidence']:.2f}]"
        )
