"""
training_review.py — Training-example review, approval, and JSONL export.

Commands (used from chatbot.py or standalone):
    /review list          – list unapproved examples (newest first)
    /review approve <id>  – mark example as approved
    /review reject <id>   – delete example
    /review edit <id>     – edit assistant response before approving
    /review export        – export all approved examples to JSONL

The training pipeline (fine-tuning) is intentionally NOT triggered here.
Approved examples are stored as approved=1 in the DB and exported on demand.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/processed/chatbot.db")

# Export directory
EXPORT_DIR = Path("data/exports")


# ── Schema bootstrap ─────────────────────────────────────────────────────────

def initialize_training_db() -> None:
    """Create / migrate the training_examples table."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_examples (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message       TEXT NOT NULL,
                assistant_response TEXT NOT NULL,
                approved           INTEGER DEFAULT 0,
                created_at         TEXT NOT NULL,
                reviewed_at        TEXT
            )
        """)
        conn.commit()
        # Add reviewed_at column if it's missing from older DBs
        existing = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(training_examples)"
            ).fetchall()
        }
        if "reviewed_at" not in existing:
            conn.execute(
                "ALTER TABLE training_examples ADD COLUMN reviewed_at TEXT"
            )
            conn.commit()


# ── Record saving ─────────────────────────────────────────────────────────────

def save_training_example(
    user_message: str, assistant_response: str
) -> int:
    """
    Insert a new unapproved training example.
    Returns the rowid of the inserted record.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO training_examples
                (user_message, assistant_response, approved, created_at)
            VALUES (?, ?, 0, ?)
            """,
            (user_message, assistant_response,
             datetime.now().isoformat(timespec="seconds")),
        )
        return cursor.lastrowid


# ── Listing ───────────────────────────────────────────────────────────────────

def list_pending(limit: int = 20) -> list[dict]:
    """Return up to `limit` unapproved examples, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, user_message, assistant_response, created_at
            FROM training_examples
            WHERE approved = 0
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id":        row[0],
            "user":      row[1],
            "assistant": row[2],
            "created":   row[3],
        }
        for row in rows
    ]


def list_approved(limit: int = 50) -> list[dict]:
    """Return approved examples."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, user_message, assistant_response, created_at, reviewed_at
            FROM training_examples
            WHERE approved = 1
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id":          row[0],
            "user":        row[1],
            "assistant":   row[2],
            "created":     row[3],
            "reviewed_at": row[4],
        }
        for row in rows
    ]


# ── Approval / rejection / edit ───────────────────────────────────────────────

def approve_example(example_id: int) -> bool:
    """Mark an example as approved. Returns True if found."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE training_examples
            SET approved = 1,
                reviewed_at = ?
            WHERE id = ? AND approved = 0
            """,
            (datetime.now().isoformat(timespec="seconds"), example_id),
        )
        return cursor.rowcount > 0


def reject_example(example_id: int) -> bool:
    """Delete an example. Returns True if found."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM training_examples WHERE id = ?", (example_id,)
        )
        return cursor.rowcount > 0


def edit_and_approve(
    example_id: int, new_response: str
) -> bool:
    """Update the assistant response and mark as approved. Returns True if found."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE training_examples
            SET assistant_response = ?,
                approved = 1,
                reviewed_at = ?
            WHERE id = ?
            """,
            (new_response,
             datetime.now().isoformat(timespec="seconds"),
             example_id),
        )
        return cursor.rowcount > 0


# ── JSONL export ──────────────────────────────────────────────────────────────

def export_approved_jsonl(output_path: Optional[Path] = None) -> Path:
    """
    Export all approved examples to a JSONL file.

    Each line is a JSON object with keys: user_message, assistant_response.
    Returns the path of the exported file.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = EXPORT_DIR / f"approved_examples_{ts}.jsonl"

    approved = list_approved(limit=100_000)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in approved:
            record = {
                "user_message":       ex["user"],
                "assistant_response": ex["assistant"],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return output_path


# ── CLI (interactive review session) ─────────────────────────────────────────

def run_review_cli() -> None:
    """Interactive review CLI called from the chatbot's /review command."""
    initialize_training_db()

    while True:
        pending = list_pending(limit=5)
        if not pending:
            print("\n  No unapproved examples.")
            break

        print(f"\n  {len(pending)} example(s) pending (showing up to 5):\n")
        for ex in pending:
            print(f"  ─── ID {ex['id']} ({ex['created']}) ───")
            print(f"  User     : {ex['user'][:120]}")
            print(f"  Assistant: {ex['assistant'][:120]}")
            print()

        choice = input(
            "  [a]pprove <id> | [r]eject <id> | [e]dit <id> | "
            "[s]kip | [q]uit: "
        ).strip().lower()

        if choice in {"q", "quit"}:
            break
        if choice in {"s", "skip", ""}:
            continue

        parts = choice.split()
        if len(parts) < 2:
            print("  Usage: a 3  |  r 3  |  e 3")
            continue

        action, *rest = parts
        try:
            ex_id = int(rest[0])
        except (ValueError, IndexError):
            print("  Invalid ID.")
            continue

        if action in {"a", "approve"}:
            if approve_example(ex_id):
                print(f"  ✓ Approved #{ex_id}")
            else:
                print(f"  ✗ ID {ex_id} not found or already approved.")

        elif action in {"r", "reject"}:
            if reject_example(ex_id):
                print(f"  ✓ Rejected and deleted #{ex_id}")
            else:
                print(f"  ✗ ID {ex_id} not found.")

        elif action in {"e", "edit"}:
            new_resp = input("  New assistant response: ").strip()
            if new_resp:
                if edit_and_approve(ex_id, new_resp):
                    print(f"  ✓ Edited and approved #{ex_id}")
                else:
                    print(f"  ✗ ID {ex_id} not found.")
            else:
                print("  Empty response — skipped.")

        else:
            print("  Unknown command.")

    # Offer export at end
    approved_count = len(list_approved())
    if approved_count > 0:
        do_export = input(
            f"\n  {approved_count} approved example(s). Export to JSONL? [y/N]: "
        ).strip().lower()
        if do_export == "y":
            path = export_approved_jsonl()
            print(f"  Exported → {path}")


if __name__ == "__main__":
    initialize_training_db()
    run_review_cli()
