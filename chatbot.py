"""
chatbot.py — Tamil / Tanglish / English chatbot powered by Ollama.

Architecture
------------
* ONE SQLite database for personal memory  → data/processed/memory.db   (memory_db.py)
* ONE SQLite database for chat / training  → data/processed/chatbot.db  (training_review.py)
* Deterministic fact lookup                → chat_memory.py
* AI-powered fact extraction               → fact_extractor.py
* Training-example review & export        → training_review.py

Commands
--------
  /bye, /exit           – quit
  /remember key=value   – explicitly save a fact
  /forget key           – delete a stored fact
  /memories             – list all stored facts
  /review               – open the training-example review CLI
  /export               – export approved examples to JSONL
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import requests

from memory_db import (
    initialize_database,
    save_memory,
    get_memory,
    forget_memory,
    list_memories,
)
from chat_memory import answer_question, learn_fact, detect_language_style
from fact_extractor import extract_facts
from training_review import (
    initialize_training_db,
    save_training_example,
    export_approved_jsonl,
    run_review_cli,
)

# ── Configuration ────────────────────────────────────────────────────────────

MODEL      = "llama3.2:3b"
OLLAMA_URL = "http://localhost:11434/api/chat"

CHAT_DB_PATH = Path("data/processed/chatbot.db")
CHAT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── /remember key aliases → (canonical DB key, default Tamil value) ──────────

_REMEMBER_KEY_MAP: dict[str, tuple[str, str | None]] = {
    "name":      ("user_name",               None),
    "location":  ("user_location",           None),
    "colour":    ("favorite_colour",         None),
    "color":     ("favorite_colour",         None),
    "workplace": ("user_workplace",          None),
    "job":       ("user_job_title",          None),
    "learning":  ("user_learning",           None),
    "interest":  ("user_interest",           None),
    "skill":     ("user_skill",              None),
    "goal":      ("user_goal",               None),
    "language":  ("user_language_preference", None),
    "style":     ("user_response_style",     None),
}

_KEY_CATEGORY: dict[str, str] = {
    "user_name":               "identity",
    "user_location":           "identity",
    "favorite_colour":         "preference",
    "user_workplace":          "work",
    "user_job_title":          "work",
    "user_learning":           "learning",
    "user_interest":           "interest",
    "user_skill":              "skill",
    "user_goal":               "goal",
    "user_language_preference": "preference",
    "user_response_style":     "preference",
}


# ── Database initialisation ──────────────────────────────────────────────────

def initialize_chatbot() -> None:
    initialize_database()        # memory.db — personal facts
    initialize_training_db()     # chatbot.db — chat history + training examples

    with sqlite3.connect(CHAT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT NOT NULL,
                message    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


# ── Chat history ─────────────────────────────────────────────────────────────

def save_chat(role: str, message: str) -> None:
    with sqlite3.connect(CHAT_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_history (role, message, created_at) VALUES (?, ?, ?)",
            (role, message, datetime.now().isoformat(timespec="seconds")),
        )


def get_recent_history(limit: int = 10) -> list[dict]:
    with sqlite3.connect(CHAT_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT role, message FROM chat_history
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    rows.reverse()
    return [{"role": role, "content": msg} for role, msg in rows]


# ── Memory context builder ───────────────────────────────────────────────────

def build_memory_context() -> str | None:
    """
    Build a concise memory context string from all stored facts.
    Injected into the system prompt so Ollama is aware of the user's profile.
    """
    facts = list_memories()
    if not facts:
        return None
    lines = ["Known personal facts about the user:"]
    for f in facts:
        label = f["key"].replace("_", " ")
        lines.append(f"  • {label}: {f['value']}")
    return "\n".join(lines)


# ── Ollama chat call ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a helpful, respectful Tamil/Tanglish/English assistant.

Critical rules you must ALWAYS follow:
1. Reply in the SAME language and script the user used.
2. NEVER invent personal facts. If memory context is provided, use ONLY that.
   If it is not provided, say you don't know — do not guess.
3. NEVER claim the user lives somewhere, is learning something, or has a goal
   unless that fact appears in the memory block below.
4. Keep replies concise, warm, and natural. No sarcasm. No insults.
5. Technical terms (Python, AI Engineer, etc.) stay in English even in Tamil replies.
6. When the user introduces themselves ("My name is X"), acknowledge it simply.
   Example good reply to "My name is Sarandeep": "Nice to meet you, Sarandeep!"
   Example bad reply: "நீயும் Sarandeep!" (dismissive) or making jokes.
"""



def ask_ollama(user_message: str) -> str:
    # 1. Try deterministic memory lookup first
    memory_answer = learn_fact(user_message) or answer_question(user_message)
    if memory_answer:
        return memory_answer

    # 2. Build messages list
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    memory_ctx = build_memory_context()
    if memory_ctx:
        messages.append({
            "role":    "system",
            "content": (
                "Use the following memory when relevant. "
                "Treat it as factual — do not contradict it:\n\n"
                + memory_ctx
            ),
        })

    messages.extend(get_recent_history())
    messages.append({"role": "user", "content": user_message})

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    except requests.exceptions.ConnectionError:
        return (
            "Ollama connection failed. Make sure Ollama is running and try again."
        )
    except requests.exceptions.Timeout:
        return "Ollama took too long to respond. Try again."
    except requests.exceptions.RequestException as err:
        return f"Error contacting Ollama: {err}"


# ── Command handlers ─────────────────────────────────────────────────────────

def handle_remember(fact_str: str) -> str:
    """Handle /remember key=value command."""
    key_raw, sep, value = fact_str.partition("=")
    if not sep or not value.strip():
        keys = ", ".join(_REMEMBER_KEY_MAP)
        return f"Usage: /remember key=value   (keys: {keys})"

    key_raw = key_raw.strip().lower()
    value   = value.strip()

    if key_raw not in _REMEMBER_KEY_MAP:
        keys = ", ".join(_REMEMBER_KEY_MAP)
        return f"Unknown key '{key_raw}'. Valid keys: {keys}"

    fact_key, _ = _REMEMBER_KEY_MAP[key_raw]
    category     = _KEY_CATEGORY.get(fact_key, "general")

    save_memory(
        fact_key, value,
        category=category,
        confidence=1.0,
        source="manual",
    )
    return f"✓ Saved {key_raw} = {value}"


def handle_forget(key_str: str) -> str:
    """Handle /forget key command."""
    key_raw = key_str.strip().lower()
    if not key_raw:
        return "Usage: /forget key"

    # Accept either the short alias or the full DB key
    if key_raw in _REMEMBER_KEY_MAP:
        fact_key, _ = _REMEMBER_KEY_MAP[key_raw]
    else:
        fact_key = key_raw

    if forget_memory(fact_key):
        return f"✓ Forgotten: {key_raw}"
    return f"No memory found for '{key_raw}'."


def handle_memories() -> str:
    """Handle /memories command — list all stored facts."""
    facts = list_memories()
    if not facts:
        return "No memories stored yet."

    lines = ["Your stored memories:\n"]
    for f in facts:
        label = f["key"].replace("_", " ").title()
        tamil = f"  (Tamil: {f['tamil']})" if f["tamil"] else ""
        src   = f['source']
        conf  = f['confidence']
        lines.append(
            f"  • {label}: {f['value']}{tamil}"
            f"  [{f['category']}, {src}, conf={conf:.2f}]"
        )
    return "\n".join(lines)


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    initialize_chatbot()

    print("\n╔═══════════════════════════════════════╗")
    print("║        Tamil LLM Chatbot v2.0         ║")
    print("╠═══════════════════════════════════════╣")
    print("║  /remember key=value  – save a fact   ║")
    print("║  /forget key          – delete a fact ║")
    print("║  /memories            – list memories ║")
    print("║  /review              – review examples║")
    print("║  /export              – export JSONL  ║")
    print("║  /bye                 – exit           ║")
    print("╚═══════════════════════════════════════╝\n")

    while True:
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAssistant: Goodbye! See you again.")
            break

        if not user_message:
            continue

        # ── Exit ──────────────────────────────────────────────────────────
        if user_message.lower() in {"/bye", "/exit"}:
            print("Assistant: Goodbye! See you again.")
            break

        # ── /remember ─────────────────────────────────────────────────────
        if user_message.lower().startswith("/remember "):
            fact_str = user_message[len("/remember "):]
            print(f"Assistant: {handle_remember(fact_str)}\n")
            continue

        # ── /forget ───────────────────────────────────────────────────────
        if user_message.lower().startswith("/forget "):
            key_str = user_message[len("/forget "):]
            print(f"Assistant: {handle_forget(key_str)}\n")
            continue

        # ── /memories ─────────────────────────────────────────────────────
        if user_message.lower() == "/memories":
            print(f"Assistant: {handle_memories()}\n")
            continue

        # ── /review ───────────────────────────────────────────────────────
        if user_message.lower() in {"/review", "/review list"}:
            run_review_cli()
            continue

        # ── /export ───────────────────────────────────────────────────────
        if user_message.lower() == "/export":
            path = export_approved_jsonl()
            print(f"Assistant: Exported approved examples → {path}\n")
            continue

        # ── Normal chat ───────────────────────────────────────────────────
        save_chat("user", user_message)

        # AI fact extraction (non-blocking; fails silently)
        extracted = extract_facts(user_message)
        if extracted:
            labels = [f.key.replace("user_", "").replace("_", " ")
                      for f in extracted]
            print(f"  (Memory saved: {', '.join(labels)})")

        assistant_response = ask_ollama(user_message)
        print(f"Assistant: {assistant_response}\n")

        save_chat("assistant", assistant_response)
        save_training_example(user_message, assistant_response)


if __name__ == "__main__":
    main()
