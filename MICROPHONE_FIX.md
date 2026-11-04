# Microphone Access Denied - Complete Troubleshooting Guide

## Problem
You're seeing:
```
Microphone access denied. Please allow microphone permissions.
```

Even though you already gave permission in the browser.

---

## Quick Diagnostic Tool ✅

**NEW:** There's now a "🔧 Test Microphone" button on the interface!

### How to Use It:
1. Open http://localhost:8000
2. Click the "🔧 Test Microphone" button
3. A diagnostic report will show exactly what's wrong
4. Follow the specific instructions for your issue

This tool will tell you:
- ✅ Is your browser compatible?
- ✅ Can it access the MediaDevices API?
- ✅ Do you have a microphone connected?
- ✅ What's the exact error?
- ✅ How to fix it

---

## Root Causes & Fixes

### Issue 1: Browser Permissions Revoked

**Symptoms:**
- You gave permission once
- Now it's denying access
- Error: "NotAllowedError"

**Fix:**
1. Look for the **lock icon** in the address bar (left side)
2. Click it to open site permissions
3. Find "Microphone" setting
4. Change from "Block" to "Allow" (not "Ask")
5. Close the permission popup
6. **Refresh the page: Ctrl+R**
7. Try clicking the mic button again

**Visual Guide:**
```
Address Bar: http://localhost:8000 🔒
             ↑ Click this lock icon
             ↓
Site Permissions Popup:
├─ Microphone: [🔴 Block]  ← Change this
├─ Camera: [🔴 Block]
└─ Cookies: [Settings]

Click "Block" and change to "Allow"
Then Refresh page (Ctrl+R)
```

---

### Issue 2: Windows System Permission Denied

**Symptoms:**
- Permission was never asked
- Error: "PermissionDenied"
- Works in one browser but not another

**Fix (Windows 10/11):**

1. **Go to Windows Settings:**
   - Press: `Win + I` (or click Settings in Start)
   - Navigate to: "Privacy & Security"
   - Click: "Microphone"

2. **Check Enable Microphone:**
   - Toggle: "Microphone access" → ON
   - Toggle: "Allow applications to access your microphone" → ON

3. **Allow Specific Browser:**
   - Scroll down under "Allow access to the microphone for these apps"
   - Find your browser (Chrome, Firefox, Edge, Safari)
   - Toggle it to: ON

4. **Back to Browser:**
   - Refresh page: Ctrl+R
   - Try mic button again

**Windows Settings Path:**
```
Windows Settings
└─ Privacy & Security
   └─ Microphone
      ├─ Microphone access: [Toggle ON]
      ├─ Allow app access: [Toggle ON]
      └─ Allow on these apps:
         ├─ Google Chrome: [Toggle ON]
         ├─ Firefox: [Toggle ON]
         └─ Microsoft Edge: [Toggle ON]
```

---

### Issue 3: No Microphone Connected

**Symptoms:**
- Error: "NotFoundError"
- Message: "No microphone found"

**Fix:**
1. **Connect a microphone:**
   - USB microphone, or
   - Headphones with mic, or
   - Built-in laptop microphone

2. **Check in Windows Settings:**
   - Press: `Win + I`
   - Go to: "Sound"
   - Check: "Input" section shows your microphone
   - Do a test: Click "Volume test" or "Microphone test"

3. **Try the test button again**

**Check if Microphone Works:**
```
Windows Settings
└─ Sound
   └─ Input devices
      ├─ Your Microphone should be listed
      └─ Test: Speak and see volume bars move
```

---

### Issue 4: Browser Doesn't Support Audio

**Symptoms:**
- Error: "getUserMedia is not supported"
- Very old browser

**Fix:**
Use a modern browser:
- ✅ **Google Chrome** (best)
- ✅ **Firefox**
- ✅ **Microsoft Edge**
- ✅ **Safari** (newer versions)

**Don't use:**
- ❌ Internet Explorer
- ❌ Very old versions

---

### Issue 5: HTTPS Required (Rare)

**Symptoms:**
- Works on `https://` but not `http://localhost:8000`
- Error: Permission denied

**Fix:**
This shouldn't happen on localhost, but if it does:
1. Firefox: Sometimes is stricter
   - Go to: `about:config`
   - Search: `security.insecure_connection_allowed`
   - Set: true (for localhost only)

2. Try different browser like Chrome or Edge

---

## Step-by-Step Troubleshooting

### Step 1: Use the Test Button First
1. Open http://localhost:8000
2. Click "🔧 Test Microphone"
3. Read the diagnostic output
4. It will tell you exactly what's wrong

### Step 2: Check Browser Permissions
- Address bar lock icon → Microphone → Allow
- Refresh page (Ctrl+R)
- Try again

### Step 3: Check Windows Permissions
- Settings → Privacy & Security → Microphone
- Turn ON both toggles
- Ensure your browser is allowed
- Refresh page (Ctrl+R)
- Try again

### Step 4: Check Microphone Hardware
- Windows Settings → Sound
- Input section shows your microphone
- Test microphone to ensure it works
- If not working, try different microphone

### Step 5: Try Different Browser
- Download Chrome if you don't have it
- Try the same steps
- Works better than some other browsers

### Step 6: Restart Everything
- Close the browser
- Close the server (`Ctrl+C` in terminal)
- Restart the server: `.\start-web.ps1`
- Reopen browser: `http://localhost:8000`
- Click mic button

### Step 7: Check System Sounds
- Windows Settings → Sound
- Speakers/Output should show volume
- Click volume test
- If no sound at all, microphone might be muted

---

## Browser-Specific Fixes

### Google Chrome
```
1. Click three dots (menu) → Settings
2. Left sidebar → Privacy and security
3. Microphone → Localhost allowed
4. Refresh page (Ctrl+R)
```

### Firefox
```
1. Click hamburger menu (☰) → Settings
2. Permissions section
3. Microphone → Allow for http://localhost:8000
4. Refresh page (Ctrl+R)
```

### Microsoft Edge
```
1. Click three dots (menu) → Settings
2. Cookies and site permissions
3. Microphone
4. Allow localhost
5. Refresh page (Ctrl+R)
```

### Safari
```
1. Safari → Preferences
2. Security tab
3. Allow microphone access
4. Refresh page (Cmd+R)
```

---

## Advanced Diagnostics

### Check Browser Console (F12)
1. Open page: http://localhost:8000
2. Press: F12 (opens Developer Tools)
3. Click: "Console" tab
4. Click mic button or test microphone
5. Look for messages like:
   - ✅ "✓ Microphone access granted"
   - ❌ "NotAllowedError: Permission denied"
   - ❌ "NotFoundError: No microphone"
   - ❌ "SecurityError: Insecure context"

**Copy console output:**
- Right-click → Copy
- Paste to understand error better

### Check Network (if audio doesn't process)
1. Press: F12 (Developer Tools)
2. Click: "Network" tab
3. Click mic and record
4. Should see POST request to `/api/voice-turn`
5. Response should show transcription

---

## FAQ

### Q: I gave permission but it still asks?
**A:** Browser cache issue. Try:
- Close browser completely
- Reopen browser
- Or: Clear cache (Ctrl+Shift+Delete)

### Q: Permission works in Chrome but not Firefox?
**A:** Each browser has separate permissions. Set in each browser you use.

### Q: Microphone worked once, then stopped?
**A:** Permission may have reverted. Check browser and system settings again.

### Q: Can I test microphone without recording?
**A:** Yes! Click "🔧 Test Microphone" button to run diagnostics.

### Q: Multiple microphones - which one to use?
**A:** Browser uses the default one. Set default in Windows Sound Settings.

### Q: What if I want to use a different microphone?
**A:** Change default in Windows:
- Settings → Sound → Input devices
- Right-click your preferred mic
- Set as default device

### Q: Does it need internet?
**A:** No! Localhost works offline.

### Q: Will it work on phone?
**A:** Yes, mobile browsers also support microphone (with permission).

---

## Complete Checklist

- [ ] Click "🔧 Test Microphone" button
- [ ] Read diagnostic output
- [ ] Check browser address bar (lock icon)
- [ ] Set microphone to "Allow" (not "Block" or "Ask")
- [ ] Refresh page (Ctrl+R)
- [ ] Try mic button again
- [ ] If still fails, check Windows Settings
  - [ ] Privacy & Security → Microphone
  - [ ] Microphone access → ON
  - [ ] Allow app access → ON
  - [ ] Your browser → ON
- [ ] Refresh page again (Ctrl+R)
- [ ] Try mic button
- [ ] Check if microphone is connected
- [ ] Test microphone in Windows Sound settings
- [ ] Try different browser
- [ ] Restart server: `.\start-web.ps1`
- [ ] Clear browser cache: Ctrl+Shift+Delete
- [ ] Try again

---

## Success Indicators

✅ When it's working:

```
Click mic button
↓
"Listening..." shows with pulsing ring
↓
You speak in Tamil
↓
See message in right bubble (your speech)
↓
See message in left bubble (bot reply)
↓
Both can be exported
```

If you see any step not happening, you have a microphone permission issue.

---

## Quick Checklist

1. ✅ Open http://localhost:8000
2. ✅ Click "🔧 Test Microphone" button
3. ✅ Read what it says
4. ✅ Follow the specific fix for your issue
5. ✅ Refresh page (Ctrl+R)
6. ✅ Try clicking mic button
7. ✅ Should work! 🎤

---

## Still Not Working?

### Provide This Info:
1. Your browser: (Chrome, Firefox, Edge, Safari)
2. Windows version: (10, 11, etc.)
3. The exact error from "Test Microphone" button
4. Screenshot of browser permissions (lock icon)
5. What you've already tried

### Check These Logs:
1. Browser console (F12 → Console)
2. Server terminal
3. Test Microphone button output

---

## Support Resources

- **Quick fix:** See "Test Microphone" button (🔧)
- **Audio error:** See `FIX_AUDIO_ERROR.md`
- **Output feature:** See `OUTPUT_FEATURE.md`
- **General setup:** See `QUICK_START.md`

---

**Remember:** The "🔧 Test Microphone" button is your best troubleshooting tool! Use it first. 🚀
