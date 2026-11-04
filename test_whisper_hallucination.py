#!/usr/bin/env python3
"""
Test Whisper hallucination behavior with different audio inputs
to diagnose if the issue is acoustic feedback or STT hallucination.
"""

import numpy as np
import io
import wave
import requests

def test_audio(name, audio_data, sample_rate=16000):
    """Send audio to server and get transcription"""
    print(f"\n{name}:")
    print(f"  Input: {len(audio_data)} samples")
    
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        # Convert to int16 if needed
        if audio_data.dtype != np.int16:
            if audio_data.max() <= 1.0 and audio_data.min() >= -1.0:
                audio_data = (audio_data * 32767).astype(np.int16)
            else:
                audio_data = audio_data.astype(np.int16)
        
        wav_file.writeframes(audio_data.tobytes())
    
    wav_buffer.seek(0)
    files = {'file': ('test.wav', wav_buffer.getvalue(), 'audio/wav')}
    
    try:
        response = requests.post('http://localhost:8000/api/voice-turn', files=files, timeout=60)
        if response.status_code == 200:
            result = response.json()
            stt = result.get("user_text", "")
            bot = result.get("bot_text", "")
            stt_latency = result.get("stt_latency_ms", 0)
            
            print(f"  STT: '{stt}' (latency: {stt_latency}ms)")
            bot_display = f"'{bot[:60]}...'" if len(bot) > 60 else f"'{bot}'"
            print(f"  Bot: {bot_display}")
            
            # Analyze
            tamil_in_stt = sum(1 for c in stt if 0xB80 <= ord(c) <= 0xBFF)
            if tamil_in_stt > 0 and not stt:
                print(f"  ⚠ Empty input but {tamil_in_stt} Tamil chars generated (HALLUCINATION)")
            elif len(stt) > 50:
                print(f"  ⚠ Long STT output from short input (possible hallucination)")
            elif stt:
                print(f"  ✓ Normal transcription")
            else:
                print(f"  ✓ Correctly transcribed as empty")
        else:
            print(f"  ✗ Error {response.status_code}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

print("\n" + "="*60)
print("  WHISPER HALLUCINATION DIAGNOSTIC")
print("="*60)

# Test 1: Pure silence
print("\n[Test 1] Pure silence (0 amplitude)")
audio_data = np.zeros(16000, dtype=np.int16)
test_audio("1-second silence", audio_data)

# Test 2: White noise
print("\n[Test 2] White noise (low amplitude)")
audio_data = np.random.normal(0, 0.01, 16000).astype(np.float32)
test_audio("1-second white noise", audio_data)

# Test 3: More intense white noise
print("\n[Test 3] Intense white noise")
audio_data = np.random.normal(0, 0.05, 16000).astype(np.float32)
test_audio("1-second intense noise", audio_data)

# Test 4: Low-frequency tone (like the earlier test)
print("\n[Test 4] Low-frequency tone (200Hz + 700Hz)")
t = np.linspace(0, 1.0, 16000)
audio_data = (0.3 * np.sin(2 * np.pi * 200 * t) + 0.2 * np.sin(2 * np.pi * 700 * t)).astype(np.float32)
test_audio("1-second tone (200Hz + 700Hz)", audio_data)

# Test 5: Short audio (0.5 second)
print("\n[Test 5] Short tone (0.5 second)")
t = np.linspace(0, 0.5, 8000)
audio_data = (0.3 * np.sin(2 * np.pi * 200 * t) + 0.2 * np.sin(2 * np.pi * 700 * t)).astype(np.float32)
test_audio("0.5-second tone", audio_data)

print("\n" + "="*60)
print("INTERPRETATION:")
print("="*60)
print("""
If Whisper hallucinated Tamil words from silence/noise, it means:
  - The initial_prompt is TOO BIASED
  - Whisper is inferring Tamil speech where there is none
  
Solution: Reduce initial_prompt bias or disable it entirely
""")
