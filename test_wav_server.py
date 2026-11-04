#!/usr/bin/env python3
"""
Quick test to verify the server can parse WAV files correctly.
Generates a test WAV file and sends it to the /api/voice-turn endpoint.
"""

import requests
import numpy as np
import io
import soundfile as sf
import struct

def create_test_wav(duration_sec=1.0, freq_hz=440, sample_rate=16000):
    """Create a simple test WAV file (sine wave tone)."""
    num_samples = int(duration_sec * sample_rate)
    samples = np.sin(2 * np.pi * freq_hz * np.arange(num_samples) / sample_rate).astype(np.float32)
    
    # Encode to WAV
    wav_buffer = io.BytesIO()
    sf.write(wav_buffer, samples, sample_rate, format='WAV')
    wav_bytes = wav_buffer.getvalue()
    
    return wav_bytes, len(samples)

def test_server():
    """Test the server endpoint."""
    print("Creating test WAV file...")
    wav_bytes, num_samples = create_test_wav(duration_sec=2.0, freq_hz=880)
    
    print(f"Generated WAV: {len(wav_bytes)} bytes, {num_samples} samples")
    print(f"Expected: {44 + num_samples * 2} bytes (44 header + data)")
    
    # Check WAV header
    print(f"\nWAV Header (first 44 bytes, hex):")
    print(' '.join(f'{b:02x}' for b in wav_bytes[:44]))
    
    # Check RIFF/WAVE signatures
    riff_sig = wav_bytes[0:4].decode('ascii', errors='ignore')
    wave_sig = wav_bytes[8:12].decode('ascii', errors='ignore')
    print(f"\nRIFF Signature: {riff_sig} (should be 'RIFF')")
    print(f"WAVE Signature: {wave_sig} (should be 'WAVE')")
    
    # Send to server
    print(f"\nSending to http://127.0.0.1:8000/api/voice-turn...")
    
    files = {'file': ('test.wav', wav_bytes, 'audio/wav')}
    
    try:
        response = requests.post('http://127.0.0.1:8000/api/voice-turn', files=files, timeout=30)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"User Text: {data.get('user_text', 'N/A')}")
            print(f"Bot Text: {data.get('bot_text', 'N/A')}")
            print(f"STT Latency: {data.get('stt_latency_ms', 'N/A')}ms")
            print(f"LLM Latency: {data.get('llm_latency_ms', 'N/A')}ms")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == '__main__':
    test_server()
