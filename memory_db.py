
import sqlite3
from pathlib import Path

DB_PATH = Path("data/processed/memory.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def initialize_database():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_key TEXT NOT NULL UNIQUE,
                fact_value TEXT NOT NULL,
                tamil_value TEXT
            )
        """)

        # Add the Tamil column if the database is older.
        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(memories)"
            ).fetchall()
        ]

        if "tamil_value" not in columns:
            connection.execute(
                "ALTER TABLE memories ADD COLUMN tamil_value TEXT"
            )


def save_memory(fact_key, fact_value, tamil_value=None):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            INSERT INTO memories (fact_key, fact_value, tamil_value)
            VALUES (?, ?, ?)
            ON CONFLICT(fact_key) DO UPDATE SET
                fact_value = excluded.fact_value,
                tamil_value = excluded.tamil_value
        """, (fact_key, fact_value, tamil_value))


def get_memory(fact_key, language="english"):
    with sqlite3.connect(DB_PATH) as connection:
        result = connection.execute(
            """
            SELECT fact_value, tamil_value
            FROM memories
            WHERE fact_key = ?
            """,
            (fact_key,),
        ).fetchone()

    if result is None:
        return None

    english_value, tamil_value = result

    if language == "tamil" and tamil_value:
        return tamil_value

    return english_value


def show_all_memories():
    with sqlite3.connect(DB_PATH) as connection:
        return connection.execute("""
            SELECT fact_key, fact_value, tamil_value
            FROM memories
            ORDER BY fact_key
        """).fetchall()


if __name__ == "__main__":
    initialize_database()

    save_memory("user_name", "Sarandeep", "சரண்தீப்")
    save_memory("user_location", "Madurai", "மதுரை")

    print("Database initialized!")
    print("\nSaved memories:")

    for key, english, tamil in show_all_memories():
        print(f"{key}: {english} | Tamil: {tamil}")
