# Tamil LLM — Chatbot & TinyTamilGPT

A personal AI chatbot that supports **Tamil**, **Tanglish** (Tamil written in English), and **English**, backed by a local LLM (Ollama) and persistent SQLite memory.

Also includes **TinyTamilGPT** — a custom character-level Transformer you can train on Tamil text from scratch.

---

## ⚡ Quick Start

### 1. Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11 + |
| [Ollama](https://ollama.com) | any |
| `llama3.2:3b` model | `ollama pull llama3.2:3b` |

### 2. Install dependencies

```powershell
pip install torch==2.14.0 requests pytest>=8.0 tqdm>=4.66
```

### 3. Run the chatbot

```powershell
cd "c:\ROBO WEB TECHNOLOGIES\TAMIL LLM\TAMIL-LLM"
python chatbot.py
```

Make sure Ollama is running in the background first:
```powershell
ollama serve
```

---

## 💬 Chatbot Commands

| Command | Description |
|---------|-------------|
| `/remember name=Sarandeep` | Save your name |
| `/remember location=Madurai` | Save your location |
| `/remember workplace=Tarcin Robotics` | Save your workplace |
| `/remember learning=Python` | Save what you are learning |
| `/remember interest=cricket` | Save an interest |
| `/remember skill=Python` | Save a skill |
| `/remember goal=AI engineer` | Save a career goal |
| `/remember language=Tanglish` | Save language preference |
| `/forget name` | Delete a saved fact |
| `/memories` | List all stored personal facts |
| `/review` | Interactively review training examples |
| `/export` | Export approved examples to JSONL |
| `/bye` | Exit |

### Supported keys for `/remember`
`name`, `location`, `colour`, `workplace`, `job`, `learning`, `interest`, `skill`, `goal`, `language`, `style`

---

## 🧠 Architecture

```
chatbot.py
  ├── chat_memory.py      ← deterministic fact retrieval (Tamil/Tanglish/English)
  ├── fact_extractor.py   ← AI-powered fact extraction via Ollama
  ├── memory_db.py        ← SQLite: data/processed/memory.db
  └── training_review.py  ← SQLite: data/processed/chatbot.db
```

### Two databases, clear separation

| Database | Purpose |
|----------|---------|
| `data/processed/memory.db` | Personal facts (name, location, interests, …) |
| `data/processed/chatbot.db` | Chat history + training examples |

### Memory fact structure

Each stored fact has:
- `fact_key` — canonical identifier (e.g. `user_name`)
- `fact_value` — English/romanised value
- `tamil_value` — Tamil-script translation (optional)
- `category` — `identity`, `work`, `learning`, `interest`, `skill`, `goal`, `preference`
- `confidence` — 0.0–1.0 (manual = 1.0, AI extraction = 0.75–0.95)
- `source` — `manual`, `ai`, or `regex`
- `updated_at` — ISO-8601 timestamp

**AI extractions never overwrite manually saved facts.**

---

## 🤖 AI-Powered Fact Extraction

When you chat naturally, the bot automatically extracts personal facts:

| What you say | What gets saved |
|---|---|
| `I work at Tarcin Robotics.` | `user_workplace = Tarcin Robotics` |
| `I'm learning Python.` | `user_learning = Python` |
| `Enakku cricket pudikkum.` | `user_interest = cricket` |
| `My goal is to become an AI engineer.` | `user_goal = AI engineer` |
| `I prefer Tanglish responses.` | `user_language_preference = Tanglish` |

Questions and unclear messages are silently skipped (no unnecessary LLM calls).

---

## 🗂️ Training-Example Review

Every conversation pair is saved as an unapproved training example.

```
/review       — open interactive review session
/export       — export approved examples to JSONL
```

Review CLI options:
```
[a]pprove <id>   – mark as approved
[r]eject <id>    – delete
[e]dit <id>      – fix the response, then approve
[s]kip           – skip to next batch
[q]uit           – exit review
```

Exported JSONL format (one record per line):
```json
{"user_message": "...", "assistant_response": "..."}
```

---

## 🤖 TinyTamilGPT (Custom Language Model)

A miniature character-level GPT trained from scratch on Tamil text.

### Train

```powershell
python -m model.train
python -m model.train --steps 2000 --batch_size 16 --lr 1e-3
```

Training data: `data/tamil.txt` — add more Tamil text (at least 1–5 MB recommended).

### Generate

```powershell
python generate.py --prompt "வணக்கம்" --max_new_tokens 200 --temperature 0.8
```

---

## 🧪 Tests

```powershell
# All tests
python -m pytest tests/ -v

# Only chatbot tests (no model training, faster)
python -m pytest tests/test_chatbot.py -v

# Full suite including model training tests
python -m pytest tests/test_train.py -v
```

Tests do **not** require a running Ollama instance — all LLM calls are mocked.

---

## 📁 Project Structure

```
TAMIL-LLM/
├── chatbot.py              # Main chatbot (entry point)
├── chat_memory.py          # Deterministic fact retrieval
├── fact_extractor.py       # AI-powered fact extraction
├── memory_db.py            # SQLite memory layer (memory.db)
├── training_review.py      # Training-example review & export
├── generate.py             # TinyTamilGPT text generation CLI
├── requirements.txt
├── model/
│   ├── tokenizer.py        # Character-level tokenizer
│   ├── transformer.py      # TinyTamilGPT model
│   └── train.py            # Training script
├── data/
│   ├── tamil.txt           # Training corpus (add more text here)
│   └── processed/          # SQLite databases (git-ignored)
├── tests/
│   ├── test_chatbot.py     # Chatbot component tests
│   └── test_train.py       # Model training tests
└── checkpoints/            # Saved .pt files (git-ignored)
```

---

## ⚠️ Known Limitations

1. **TinyTamilGPT corpus is tiny** — `data/tamil.txt` is only ~1 KB. Add real data from [Wikipedia Tamil dump](https://dumps.wikimedia.org/tawiki/) or [IndicCorp](https://ai4bharat.iitm.ac.in/) for meaningful results.
2. **Fact extraction requires Ollama** — if Ollama is offline, extraction is silently skipped; the chatbot remains usable.
3. **Tanglish detection is heuristic** — unusual Tanglish phrasing may be misclassified as English.
4. **No GPU training** — TinyTamilGPT trains on CPU only. Add `device = "cuda" if torch.cuda.is_available() else "cpu"` to `train.py` for GPU support.
5. **Multi-value facts** (interests, skills) are stored as a single comma-separated string — not indexed for individual lookups.

---

## 🔜 Next Steps (Priority)

1. Add a real Tamil corpus (1+ MB) to `data/tamil.txt`
2. GPU support in `train.py`
3. Top-k / nucleus sampling in `generate.py`
4. Web UI (Flask/FastAPI) for the chatbot
5. Semantic similarity memory retrieval (replace keyword-only matching)
