# PowerShell Setup Guide

Since you're using PowerShell, here are the correct commands for your environment.

## Installation

### Step 1: Install Backend Dependencies

```powershell
cd backend
pip install -r requirements.txt
cd ..
```

### Step 2: Install Frontend Dependencies

```powershell
cd frontend
npm install
cd ..
```

## Startup (Choose One Option)

### Option 1: Manual (Three Separate Terminal Windows) ⭐ Recommended

**This gives you the most control and visibility into each service.**

**Step 1: Open Terminal and start Ollama**
```powershell
ollama serve
```

**Step 2: Open a NEW terminal and start Backend**
```powershell
cd c:\ROBO WEB TECHNOLOGIES\TAMIL LLM\TAMIL-LLM
cd backend
python main.py
```

**Step 3: Open ANOTHER NEW terminal and start Frontend**
```powershell
cd c:\ROBO WEB TECHNOLOGIES\TAMIL LLM\TAMIL-LLM
cd frontend
npm run dev
```

**Step 4: Open browser**
- http://localhost:5173

### Option 2: PowerShell Script (Automatic)

Run this from the project root:

```powershell
.\start_web.ps1
```

This will:
- Check if services are already running
- Start any missing services in new PowerShell windows
- Show you the URLs to open

### Option 3: Batch File (cmd.exe)

```powershell
.\start_web.bat
```

This opens all services in Windows Command Prompt terminals.

## Stopping Services

To stop any service, go to its terminal window and press **Ctrl+C**.

## Troubleshooting

### "The term 'cd' is not recognized"

This shouldn't happen in PowerShell. Make sure you're in PowerShell (not cmd.exe).

Check your prompt:
- PowerShell: `PS C:\path>`
- Command Prompt: `C:\path>`

### "pip is not recognized"

Python isn't in your PATH. Try:

```powershell
python -m pip install -r requirements.txt
```

Or check Python is installed:

```powershell
python --version
```

### "npm is not recognized"

Node.js isn't installed or not in PATH. Check:

```powershell
node --version
npm --version
```

If not installed, download from https://nodejs.org/

### "Cannot find module 'react'"

Frontend dependencies not installed. Run:

```powershell
cd frontend
npm install
```

### Port already in use

If port 5173 or 8000 is already in use:

**Option A:** Kill the process using that port
```powershell
# Find process using port 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
  ForEach-Object { Get-Process -Id $_.OwningProcess }

# Kill it
Stop-Process -Id <PID> -Force
```

**Option B:** Change the port in `backend/.env`
```bash
API_PORT=8001
```

Then restart backend.

## Verifying Everything Works

### Check Ollama
```powershell
curl http://localhost:11434/api/tags
```

Should return JSON with available models.

### Check Backend
```powershell
curl http://localhost:8000/health
```

Should return:
```json
{"status":"ok","ollama_ready":true,"model":"llama3.2:3b","api_version":"1.0.0"}
```

### Check Frontend

Open http://localhost:5173 in your browser. You should see the chat interface.

## Next Steps

Once everything is running:

1. Type a message in the chat box
2. Press Enter
3. Wait for response (5-30 seconds first time)
4. See your message and the bot's response

Try these test messages:

```
Hello, what is your name?

naa cse padichen college la (I studied CSE at college)

naa enga irukken? (Where am I from?)
```

---

## Common Commands Reference

| What | Command |
|------|---------|
| Change directory | `cd path` |
| Go back one level | `cd ..` |
| Go to C:\ drive | `cd c:\` |
| List files | `ls` or `dir` |
| Install Python package | `pip install package` |
| Install npm package | `npm install` |
| Start npm dev server | `npm run dev` |
| Run Python file | `python file.py` |
| Stop a process | `Ctrl+C` |
| Open file | `code file.txt` |
| Find in PATH | `where python` |

## PowerShell vs Command Prompt

You're using **PowerShell** (better choice!). Key differences:

| Operation | PowerShell | cmd.exe |
|-----------|-----------|---------|
| Command separator | `;` | `&&` or `&` |
| Change drive | `cd d:\` | `d:` |
| List files | `ls` or `dir` | `dir` |
| Run command in PATH | Same | Same |

If you ever accidentally open cmd.exe, you can switch back to PowerShell by typing `powershell`.

---

## Need Help?

1. Check the error message carefully
2. Read QUICKSTART.md for overview
3. Read VERIFICATION_CHECKLIST.md for step-by-step testing
4. Check API.md for API details
5. Look at backend logs (Terminal 2) for server errors
6. Open browser console (F12) for frontend errors

---

## Done! 🎉

You're all set. Just follow Option 1 or 2 above to start the web interface.

**Next:** Try sending your first message to your personal AI assistant!
