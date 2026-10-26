"""
FastAPI backend for TAMIL-LLM web interface.

Wraps the existing chatbot.py logic (ask_ollama, memory management)
without duplicating it. Provides HTTP endpoints for the frontend.

Architecture:
- GET /health — Check Ollama connection
- POST /api/chat — Send message, get response
- GET /api/memories — List saved personal facts
- CORS restricted to frontend origin (localhost:5173 in dev)
"""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

# ── Add parent directory to path so we can import from root chatbot.py ──────
PARENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PARENT_DIR))

from chatbot import ask_ollama, initialize_chatbot, save_chat
from memory_db import list_memories, get_memory
from chat_memory import detect_language_style

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("MODEL", "llama3.2:3b")
API_PORT = int(os.getenv("API_PORT", 8000))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="TAMIL-LLM Web API",
    description="Backend for TAMIL-LLM ChatGPT-style web interface",
    version="1.0.0",
)

# ── CORS middleware (restrict to frontend origin) ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if not DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize chatbot on startup ────────────────────────────────────────────
try:
    initialize_chatbot()
except Exception as e:
    print(f"Warning: Failed to initialize chatbot: {e}")


# ── Request/Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """User message for chat endpoint."""
    message: str

    class Config:
        example = {"message": "naa cse padichen college la"}


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    reply: str
    language: str  # "tamil", "tanglish", or "english"
    extracted_facts: list[dict] = []

    class Config:
        example = {
            "reply": "Seri! Unga field of study CSE nu save panniten.",
            "language": "tanglish",
            "extracted_facts": [
                {"key": "user_field_of_study", "value": "CSE"}
            ],
        }


class Memory(BaseModel):
    """A saved personal fact."""
    key: str
    value: str
    category: str
    confidence: float
    source: str
    updated_at: Optional[str] = None

    class Config:
        example = {
            "key": "user_field_of_study",
            "value": "CSE",
            "category": "education",
            "confidence": 0.97,
            "source": "regex",
            "updated_at": "2024-10-23T10:30:00",
        }


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Status"])
async def health_check():
    """
    Check if backend and Ollama are ready.
    
    Returns:
        - status: "ok" if all systems ready
        - ollama_ready: true/false
        - model: model name
    """
    try:
        # Try to verify Ollama is running by checking model
        resp = requests.get(
            OLLAMA_URL.replace("/api/chat", "/api/tags"),
            timeout=5,
        )
        ollama_ready = resp.status_code == 200
    except requests.exceptions.RequestException:
        ollama_ready = False

    return {
        "status": "ok" if ollama_ready else "degraded",
        "ollama_ready": ollama_ready,
        "model": MODEL,
        "api_version": "1.0.0",
    }


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message and get a response from the chatbot.
    
    The response includes:
    - reply: The assistant's message
    - language: Detected language style (tamil, tanglish, english)
    - extracted_facts: Any personal facts extracted and saved
    
    Error responses:
    - 400: Empty message
    - 503: Ollama not responding
    - 500: Other errors
    """
    # Validate input
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if len(message) > 5000:
        raise HTTPException(status_code=400, detail="Message too long (max 5000 chars)")

    try:
        # Get response from existing chatbot logic
        # This handles:
        # - Fact extraction and saving (via extract_facts)
        # - Memory lookup and acknowledgments
        # - Ollama LLM call if needed
        # - Language style preservation
        reply = ask_ollama(message)

        # Save to chat history
        save_chat("user", message)
        save_chat("assistant", reply)

        # Detect language style for frontend
        language = detect_language_style(message)

        # Get any facts that were saved (for UI feedback)
        # Note: we don't track which facts were newly extracted here,
        # so we return empty list. Frontend can call /api/memories if needed.
        extracted_facts = []

        return ChatResponse(
            reply=reply,
            language=language,
            extracted_facts=extracted_facts,
        )

    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ollama connection failed. Make sure Ollama is running on " + OLLAMA_URL,
        )
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="Ollama took too long to respond. Try again.",
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/api/memories", response_model=list[Memory], tags=["Memory"])
async def get_memories():
    """
    Return all stored personal facts from the database.
    
    Useful for:
    - Showing user what the chatbot knows about them
    - Debugging memory state
    - Frontend to display stored facts
    """
    try:
        memories = list_memories()
        return [
            Memory(
                key=m["key"],
                value=m["value"],
                category=m["category"],
                confidence=m["confidence"],
                source=m["source"],
                updated_at=m.get("updated_at"),
            )
            for m in memories
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve memories: {str(e)}",
        )


# No custom exception handler needed - FastAPI handles HTTPException automatically


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print(f"\n{'='*60}")
    print(f"TAMIL-LLM Web API Starting")
    print(f"{'='*60}")
    print(f"API URL:        http://localhost:{API_PORT}")
    print(f"Frontend:       {FRONTEND_ORIGIN}")
    print(f"Ollama:         {OLLAMA_URL}")
    print(f"Model:          {MODEL}")
    print(f"Debug:          {DEBUG}")
    print(f"{'='*60}\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=DEBUG,
        log_level="info",
    )
