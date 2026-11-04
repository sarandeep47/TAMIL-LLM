# Output Feature - Capture User Questions & Bot Replies

## Overview

The updated web interface now **automatically captures and exports both user questions and bot replies** in multiple formats.

---

## 🎯 Features

### 1. **Automatic Conversation Tracking**
- Every user message and bot reply is automatically recorded
- Stores:
  - User's question (what you asked)
  - Bot's reply (what the bot answered)
  - Latency times (STT and LLM)
  - Timestamps for each message

### 2. **View Output Button** 📋
- Click "View Output" to see all conversations formatted nicely
- Shows all turns in a readable format
- Displays in a modal popup

### 3. **Copy Output Button** 📋
- Copies the entire conversation to your clipboard
- Can paste into document, email, notes
- Shows confirmation when copied

### 4. **Download as TXT** ⬇️
- Saves the entire conversation as a .txt file
- Downloads to your computer
- Filename: `tamil-voice-output-[timestamp].txt`
- Ready to share or archive

### 5. **Clear History** 🗑️
- Deletes all conversations (with confirmation)
- Starts fresh for a new session

---

## 📋 Output Format

The output displays as:

```
═══════════════════════════════════════════════════
   TAMIL VOICE ASSISTANT - CONVERSATION OUTPUT
═══════════════════════════════════════════════════

[TURN 1]
───────────────────────────────────────────────────
📥 USER ASKED (14:23:45):
   நீ எப்படி இருக்கையா?
   [STT Latency: 1250ms]

📤 BOT REPLIED (14:23:46):
   வணக்கம்! நான் நன்றாக இருக்கிறேன்...
   [LLM Latency: 3450ms]

[TURN 2]
───────────────────────────────────────────────────
📥 USER ASKED (14:24:12):
   மாறிய வேற்றுமை என்றால் என்ன?
   [STT Latency: 1180ms]

📤 BOT REPLIED (14:24:15):
   மாறிய வேற்றுமை என்பது...
   [LLM Latency: 3890ms]

═══════════════════════════════════════════════════
Total Turns: 2
Timestamp: 12/03/2026, 14:24:15
═══════════════════════════════════════════════════
```

---

## 🚀 How to Use

### Step 1: Record Conversations
1. Open http://localhost:8000
2. Click the microphone button
3. Speak in Tamil or Tanglish
4. Release to get bot response
5. Repeat for multiple turns

**Each interaction is automatically recorded!**

### Step 2: View Results

After recording at least one conversation:

#### Option A: View in Modal
- Click **"📋 View Output"** button
- Reads all conversations in a popup
- Copy directly from the modal

#### Option B: Copy to Clipboard
- Click **"📋 Copy Output"** button
- Automatically copies to clipboard
- Paste anywhere (Word, Email, Notepad)

#### Option C: Download as File
- Click **"⬇️ Download TXT"** button
- Saves as `tamil-voice-output-[timestamp].txt`
- Download location: Your browser's default download folder

### Step 3: Clear (Optional)
- Click **"🗑️ Clear History"** to start fresh
- Requires confirmation to prevent accidental deletion

---

## 💾 What's Captured

For each turn, the output includes:

| Field | Example | Notes |
|-------|---------|-------|
| Turn Number | Turn 1, Turn 2, etc | Sequential numbering |
| User Question | நீ எப்படி இருக்கையா? | Transcribed speech |
| STT Latency | 1250ms | Time to transcribe |
| Bot Reply | வணக்கம்! நான்... | LLM response |
| LLM Latency | 3450ms | Time to generate |
| Timestamp | 14:23:45 | Time of interaction |

---

## 📝 Use Cases

### 1. **Documentation**
- Create a record of your conversation
- Share with others
- Keep for reference

### 2. **Testing**
- Track how the bot responds
- Compare different prompts
- Debug issues

### 3. **Learning**
- See what worked well
- Analyze latencies
- Improve Tamil prompts

### 4. **Sharing**
- Email conversations to team members
- Share results in meetings
- Document for reports

---

## 🔧 Technical Details

### Storage
- Conversations stored in browser memory (`conversationHistory` array)
- Lost when page is refreshed (intentional - no persistence)
- If you need to save, use Download or Copy before refreshing

### Data Structure
```javascript
{
  type: "user" or "bot",
  text: "The question or reply",
  latency: 1250,  // milliseconds
  timestamp: "14:23:45"
}
```

### JSON Export (Advanced)
The system can also export as JSON (not shown in UI, but available in code):
```json
[
  {
    "type": "user",
    "text": "நீ எப்படி இருக்கையா?",
    "latency": 1250,
    "timestamp": "14:23:45"
  },
  {
    "type": "bot",
    "text": "வணக்கம்! நான் நன்றாக இருக்கிறேன்...",
    "latency": 3450,
    "timestamp": "14:23:46"
  }
]
```

---

## ⚙️ Configuration

### Auto-export on Server
If you want to save conversations on the server side, edit `server.py`:

```python
# Add this to store conversations on disk
import json
from datetime import datetime

conversation_log = []

@app.post("/api/voice-turn")
async def voice_turn(file: UploadFile = File(...)):
    # ... existing code ...
    
    # Log the conversation
    conversation_log.append({
        "user_text": user_text,
        "bot_text": bot_text,
        "stt_latency": stt_latency,
        "llm_latency": llm_latency,
        "timestamp": datetime.now().isoformat()
    })
    
    # Save to file
    with open("conversations.json", "w") as f:
        json.dump(conversation_log, f, indent=2, ensure_ascii=False)
    
    # ... return response ...
```

---

## 🎯 Tips & Tricks

### 1. **Multi-Session Testing**
- Test with different Tamil prompts
- Use Download to save each session
- Compare results

### 2. **Performance Tracking**
- Monitor STT latencies over time
- Check if LLM slows down with longer conversations
- Identify optimization opportunities

### 3. **Batch Processing**
- Record multiple conversations
- Download all at once
- Process in bulk if needed

### 4. **Sharing Results**
- Copy output to share quickly
- Download for formal documentation
- Send to team members for review

---

## 🐛 Troubleshooting

### "View Output" button is disabled
- You need to record at least one conversation first
- Buttons enable automatically after first message

### Copy not working
- Check browser permissions for clipboard
- Try using the "Download" button instead

### Downloaded file is empty
- Refresh the page and record new conversations
- Files are lost on refresh (save before refreshing!)

### Want to keep conversations after refresh
- Download the file BEFORE refreshing the page
- Open the file later and copy the content back

---

## 📊 Example Output

Here's what a real session looks like:

```
═══════════════════════════════════════════════════
   TAMIL VOICE ASSISTANT - CONVERSATION OUTPUT
═══════════════════════════════════════════════════

[TURN 1]
───────────────────────────────────────────────────
📥 USER ASKED (10:30:15 AM):
   என்னுடைய பெயர் என்னவென்று சொல்லலாம்?
   [STT Latency: 1210ms]

📤 BOT REPLIED (10:30:18 AM):
   வணக்கம்! உங்களின் பெயரை நான் தெரிந்து கொள்ள முடியவில்லை.
   [LLM Latency: 3560ms]

[TURN 2]
───────────────────────────────────────────────────
📥 USER ASKED (10:30:45 AM):
   பதிமூன்று கூட்டல் ஏழு என்றால் எவ்வளவு?
   [STT Latency: 980ms]

📤 BOT REPLIED (10:30:49 AM):
   பதிமூன்று கூட்டல் ஏழு என்பது இருபது ஆகும்.
   [LLM Latency: 2890ms]

═══════════════════════════════════════════════════
Total Turns: 2
Timestamp: 12/03/2026, 10:30:49 AM
═══════════════════════════════════════════════════
```

---

## 🔐 Privacy

- All data stays in your browser
- Nothing sent to cloud
- Download creates a local file
- No tracking or logging (except server-side logs)

---

## 📞 Support

### Issue: I refreshed and lost my conversations
**Solution:** Conversations are stored in browser memory only. Download before refreshing to preserve them.

### Issue: Download button doesn't work
**Solution:** Check if pop-ups are blocked in your browser. Allow pop-ups for localhost.

### Issue: Can't copy to clipboard
**Solution:** This requires HTTPS or localhost (which you have). Try the Download button instead.

---

## 🎉 Summary

The output feature makes it easy to:
- ✅ Record all conversations automatically
- ✅ View formatted output anytime
- ✅ Copy to clipboard for sharing
- ✅ Download as .txt file
- ✅ Clear history when done

**No manual logging needed—everything happens automatically!**

---

## Next Steps

1. **Test it**: Record a few conversations
2. **Export**: Try all three export options (View, Copy, Download)
3. **Share**: Send the output to others
4. **Archive**: Keep downloaded files for reference

Enjoy capturing your Tamil conversations! 🎤
