# TAMIL-LLM Web API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

None (local development only). In production, add API key or JWT.

## Endpoints

### 1. Health Check

Check if the backend and Ollama are ready.

**Request:**
```http
GET /health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "ollama_ready": true,
  "model": "llama3.2:3b",
  "api_version": "1.0.0"
}
```

**Response (200, Ollama not ready):**
```json
{
  "status": "degraded",
  "ollama_ready": false,
  "model": "llama3.2:3b",
  "api_version": "1.0.0"
}
```

### 2. Send Message

Send a user message and get a response from the chatbot.

**Request:**
```http
POST /api/chat
Content-Type: application/json

{
  "message": "Hello, what is your name?"
}
```

**Response (200 OK):**
```json
{
  "reply": "I'm an AI assistant here to chat and remember facts about you.",
  "language": "english",
  "extracted_facts": []
}
```

**Response (200 OK, with fact extraction):**
```json
{
  "reply": "Seri! Unga field of study CSE nu save panniten.",
  "language": "tanglish",
  "extracted_facts": [
    {
      "key": "user_field_of_study",
      "value": "CSE"
    }
  ]
}
```

**Error (400 Bad Request):**
```json
{
  "error": "Message cannot be empty",
  "status_code": 400
}
```

**Error (503 Service Unavailable, Ollama down):**
```json
{
  "error": "Ollama connection failed. Make sure Ollama is running on http://localhost:11434/api/chat",
  "status_code": 503
}
```

**Request Parameters:**
- `message` (string, required): User message (1-5000 characters)

**Response Fields:**
- `reply` (string): Assistant's response
- `language` (string): Detected language (`tamil`, `tanglish`, or `english`)
- `extracted_facts` (array): Personal facts extracted from the message

### 3. Get Memories

List all stored personal facts from the database.

**Request:**
```http
GET /api/memories
```

**Response (200 OK):**
```json
[
  {
    "key": "user_field_of_study",
    "value": "CSE",
    "category": "education",
    "confidence": 0.97,
    "source": "regex",
    "updated_at": "2024-10-23T14:30:00"
  },
  {
    "key": "user_name",
    "value": "Sarandeep",
    "category": "identity",
    "confidence": 1.0,
    "source": "manual",
    "updated_at": "2024-10-23T12:00:00"
  }
]
```

**Response (empty list, no memories yet):**
```json
[]
```

**Error (500 Internal Server Error):**
```json
{
  "error": "Failed to retrieve memories: [error details]",
  "status_code": 500
}
```

---

## CORS

The API restricts requests to the configured `FRONTEND_ORIGIN` (default: `http://localhost:5173`).

**Allowed methods:** GET, POST, OPTIONS

**To disable CORS restrictions (development only):**
```bash
# In backend/.env
DEBUG=true
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | OK — request succeeded |
| 400 | Bad Request — invalid input (empty message, too long, etc.) |
| 422 | Validation Error — missing or wrong data type |
| 500 | Internal Server Error — database or processing error |
| 503 | Service Unavailable — Ollama not responding |

---

## Examples

### Using curl (Windows PowerShell)

**Health check:**
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method Get
$response.Content | ConvertFrom-Json
```

**Send message:**
```powershell
$body = @{ message = "Hello, what is my name?" } | ConvertTo-Json
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
$response.Content | ConvertFrom-Json
```

**Get memories:**
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/memories" -Method Get
$response.Content | ConvertFrom-Json
```

### Using JavaScript/Fetch

```javascript
// Send message
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Hello!' })
})

const data = await response.json()
console.log(data.reply)
```

### Using Python/requests

```python
import requests

# Send message
response = requests.post(
    'http://localhost:8000/api/chat',
    json={'message': 'Hello!'}
)
print(response.json()['reply'])

# Get memories
memories = requests.get('http://localhost:8000/api/memories').json()
for mem in memories:
    print(f"{mem['key']}: {mem['value']}")
```

---

## Rate Limiting

None currently (local only). In production, add rate limiting:
```python
# Add to FastAPI middleware
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

---

## Testing

Run the API test suite:

```powershell
cd backend
python -m pytest tests/test_api.py -v
```

Tests require Ollama to be running (they will fail gracefully if it's offline).

---

## Troubleshooting

### 503 — "Ollama connection failed"
**Cause:** Ollama is not running or not accessible on the configured URL.

**Solution:**
1. Start Ollama: `ollama serve` (in another terminal)
2. Check the URL in `backend/.env` matches your Ollama address
3. Test Ollama directly: `curl http://localhost:11434/api/tags`

### 422 — Validation error
**Cause:** Request body is malformed (missing field, wrong type, etc.)

**Solution:** Check that your request includes `"message"` field with a string value.

### CORS error in browser console
**Cause:** Frontend origin doesn't match `FRONTEND_ORIGIN` in `backend/.env`.

**Solution:** 
1. Check your frontend URL (http://localhost:5173 or other port)
2. Update `backend/.env`: `FRONTEND_ORIGIN=http://localhost:XXXX`
3. Restart backend

### Backend crashes on startup
**Cause:** Port 8000 is already in use.

**Solution:**
1. Check what's using port 8000: `netstat -ano | findstr :8000` (Windows)
2. Kill the process or change `API_PORT` in `backend/.env`

---

## Performance Notes

- Message processing typically takes 5-30 seconds (depends on Ollama model and hardware)
- Memory lookups are instant (SQLite indexed queries)
- Fact extraction runs in parallel without blocking the response
- Frontend shows loading spinner during processing

---

## Security Considerations

- **Local only:** No authentication, CORS, or rate limiting (assumes secure local network)
- **Database:** SQLite has no access control; both frontend and backend can access memory.db
- **Secrets:** Never commit `.env` with real API keys
- **Ollama:** Accessible locally only; add firewall rules if deploying on a server

---

## API Version History

| Version | Changes |
|---------|---------|
| 1.0.0 | Initial release (health, chat, memories endpoints) |

---

## Future Enhancements

- WebSocket streaming (real-time responses)
- Pagination for memories endpoint
- Conversation history per session ID
- Rate limiting
- API authentication (JWT or API key)
- Batch processing (multiple messages)
