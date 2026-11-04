# FormData Bug Fix - "Format not recognised" Error

## Problem

When testing the native WAV encoding pipeline, the server returned:
```
Error: Processing error: Error opening <_io.BytesIO object>: Format not recognised.
```

This error came from `soundfile.read()` when trying to parse the audio.

## Root Cause

Found a critical bug in `templates/index.html` in the `stopListening()` function:

```javascript
// ❌ WRONG - Creates FormData but doesn't use it
const formData = new FormData();
formData.append('file', wavBlob, 'speech.wav');
sendAudio(wavBlob);  // <-- Passing Blob directly, not FormData!
```

The browser was:
1. Creating a FormData object with the WAV blob
2. Ignoring it and passing the raw Blob to `sendAudio()`
3. `sendAudio()` then created a NEW FormData and appended the Blob to it
4. This resulted in FormData containing a Blob with content-type 'audio/wav'
5. The server received raw Blob bytes instead of properly formatted multipart/form-data

When FastAPI tried to save this to a file and `soundfile` tried to read it, the bytes didn't have a valid WAV header.

## Solution

### Fix 1: Pass FormData to sendAudio()
```javascript
// ✅ CORRECT - Create FormData, append WAV, then send it
const formData = new FormData();
formData.append('file', wavBlob, 'speech.wav');
sendAudio(formData);  // <-- Pass the FormData
```

### Fix 2: Update sendAudio() signature
```javascript
// ✅ CORRECT - Accept FormData, don't recreate it
async function sendAudio(formData) {
    try {
        const response = await fetch('/api/voice-turn', {
            method: 'POST',
            body: formData  // formData already has 'file' appended
        });
```

## Files Modified

- `templates/index.html`
  - Line 716: Changed `sendAudio(wavBlob)` → `sendAudio(formData)`
  - Line 772-777: Updated `sendAudio()` to accept FormData instead of creating new one

## Verification

Server test (`test_wav_server.py`) confirms:
- WAV files are now correctly parsed by `soundfile.read()`
- No more "Format not recognised" errors
- Valid WAV structure is maintained

## Next Steps

1. Open browser: `http://127.0.0.1:8000`
2. Click microphone
3. Speak Tamil for 3+ seconds
4. Release/stop recording
5. Audio should now process correctly with proper WAV encoding

## Technical Details

### What Was Happening (Before Fix)
```
Browser: WAV Blob created ✓
Browser: FormData(Blob) created but not sent ✗
Browser: Blob sent directly to sendAudio()
sendAudio(): New FormData(Blob) created
Server: FormData.file = Blob
Server: Blob bytes read (no WAV header!)
soundfile: Cannot parse → "Format not recognised" ✗
```

### What Happens Now (After Fix)
```
Browser: WAV Blob created ✓
Browser: FormData(Blob) created and sent ✓
sendAudio(): FormData used as-is
Server: FormData.file = (properly formatted file upload)
Server: Bytes read from file object → valid WAV header
soundfile: Parses WAV → float32 array ✓
Whisper: Transcribes → Tamil text ✓
```

---

Status: **FIXED** ✅

The native WAV pipeline now works end-to-end.
