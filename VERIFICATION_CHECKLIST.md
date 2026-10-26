# Verification Checklist — Web Interface

Use this checklist to verify the web interface is working correctly.

## ✅ Pre-flight (One-time Setup)

- [ ] Python 3.11+ installed: `python --version`
- [ ] Node.js installed: `node --version` and `npm --version`
- [ ] Ollama installed: `ollama --version`
- [ ] Backend dependencies installed: `pip install -r backend/requirements.txt`
- [ ] Frontend dependencies installed: `cd frontend && npm install`
- [ ] `.env` file exists in `backend/`: Check `.env` has `OLLAMA_URL`, `MODEL`, `API_PORT`

## 🚀 Startup Verification

### Terminal 1: Ollama
```powershell
ollama serve
```
**Expected output:**
- `Listening on [::]:11434`
- No errors

**Verify:** Open another terminal and run:
```powershell
curl http://localhost:11434/api/tags
```
Should return JSON with available models.

### Terminal 2: Backend
```powershell
cd backend
python main.py
```
**Expected output:**
```
============================================================
 TAMIL-LLM Web API Starting
============================================================
API URL:        http://localhost:8000
Frontend:       http://localhost:5173
Ollama:         http://localhost:11434
Model:          llama3.2:3b
Debug:          false
============================================================

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Verify:** Open another terminal and run:
```powershell
curl http://localhost:8000/health
```
Should return:
```json
{"status":"ok","ollama_ready":true,"model":"llama3.2:3b","api_version":"1.0.0"}
```

### Terminal 3: Frontend
```powershell
cd frontend
npm run dev
```
**Expected output:**
```
  VITE v5.0.8  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

**Verify:** Open http://localhost:5173 in your browser
- Page loads without errors
- No red errors in browser console (F12)
- Green indicator at bottom left says "Ollama ready"

## 🧪 Functional Tests

### Test 1: Simple Message
1. Type in input box: `Hello`
2. Click Send or press Enter
3. **Expected:** Loading spinner appears, then chatbot response appears in chat
4. **Verify:** Message shows as gray bubble on left (assistant)

### Test 2: Fact Extraction (Tanglish)
1. Type: `naa cse padichen college la` (I studied CSE at college)
2. Click Send
3. **Expected:** 
   - Chatbot responds in Tanglish (e.g., "Seri! Unga field of study CSE nu save panniten.")
   - No error message
   - Green bubble shows your message on right
4. **Verify:** Open http://localhost:8000/docs → GET /api/memories → Execute
   - Should see `user_field_of_study: CSE` in the list

### Test 3: Error Handling - Empty Message
1. Click Send with empty input
2. **Expected:** Red error at bottom says "Message cannot be empty"
3. **Verify:** Input stays focused, no message added to chat

### Test 4: Ollama Unavailable
1. Stop Ollama (Ctrl+C in Terminal 1)
2. Type a message and Send
3. **Expected:** 
   - Red error appears: "Ollama unavailable"
   - Health indicator turns red
4. **Verify:** Restart Ollama, error goes away

### Test 5: Conversation History
1. Send a few messages
2. Click "+ New chat" button
3. **Expected:** 
   - Chat cleared
   - Old conversation appears in sidebar
   - Can click to switch back

### Test 6: API Documentation
1. Open http://localhost:8000/docs
2. **Expected:** Interactive Swagger UI with 3 endpoints:
   - GET /health
   - POST /api/chat
   - GET /api/memories
3. **Verify:** Try POST /api/chat with message `"test"` → should get response

## 🔍 Backend Tests

```powershell
cd backend
python -m pytest tests/test_api.py -v
```
**Expected:** 8 passed

## 🔍 Chatbot Regression Tests

```powershell
python -m pytest tests/test_chatbot.py -q
```
**Expected:** 141 passed

## 📊 Performance Baseline

| Operation | Expected Time |
|-----------|---------------|
| Backend startup | < 3 seconds |
| Frontend dev server startup | < 5 seconds |
| First message (cold Ollama) | 5-30 seconds |
| Subsequent messages | 5-20 seconds |
| Health check | < 1 second |
| Get memories | < 1 second |

If slower than expected, check:
- Ollama is running and responsive
- Not using disk swap (check system resources)
- Network latency to Ollama

## 🚨 Troubleshooting

### Backend won't start
```powershell
# Check port 8000 is free
netstat -ano | findstr :8000

# If something is using it, kill the process or change API_PORT in backend/.env
```

### Frontend won't load
```powershell
# Check port 5173 is free
netstat -ano | findstr :5173

# Vite will auto-select a different port if needed, check the output
```

### "Ollama unavailable" in frontend
```powershell
# Check Ollama is running
curl http://localhost:11434/api/tags

# If fails, start Ollama: ollama serve
```

### CORS error in browser console
- Check `backend/.env` has correct `FRONTEND_ORIGIN`
- Should be `http://localhost:5173` (or your actual port if different)
- Restart backend after changing

### Backend crashes with chatbot initialization error
- Check `../chatbot.py` exists and is readable
- Verify `data/processed/` directory exists
- Check `memory.db` and `chatbot.db` are readable

### Messages not being saved
- Check `data/processed/memory.db` exists
- Verify database file is writable
- Check backend logs for SQL errors

## ✅ Final Checklist

- [ ] Backend running and responding to requests
- [ ] Frontend loads in browser without errors
- [ ] Health indicator is green (Ollama ready)
- [ ] Can send a message and get response
- [ ] Message appears in chat (gray bubble left)
- [ ] Fact extraction works (message appears in /api/memories)
- [ ] Error handling works (empty message rejected)
- [ ] All tests pass (149+ total)
- [ ] Terminal chatbot still works: `python chatbot.py`

## 🎉 If All Checks Pass

Your web interface is ready to use! 

Next steps:
- Try the examples in QUICKSTART.md
- Explore API documentation at http://localhost:8000/docs
- Read backend/main.py to understand the architecture
- Build additional features (WebSocket streaming, persistent history, etc.)

## 📞 Support

If something doesn't work:
1. Check the relevant section above
2. Look at terminal output for error messages
3. Check browser console (F12) for frontend errors
4. Verify prerequisites are installed correctly
5. Try restarting all services
