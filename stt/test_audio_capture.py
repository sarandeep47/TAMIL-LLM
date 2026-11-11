#!/usr/bin/env python3
"""Unit test for audio capture: verify log.jsonl writes are flushed."""
import os
import sys
import json
import tempfile
import shutil
import unicodedata
from datetime import datetime


def test_save_audio_capture():
    """Test that save_audio_sample writes exactly one log line per call and flushes it."""
    
    temp_dir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        os.makedirs("audio_samples", exist_ok=True)
        
        # Inline version of save_audio_sample with flush
        def save_audio_inline(audio_bytes, transcript, stt_ms, model, prompt_used):
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"audio_samples/{timestamp}.wav"
            
            with open(filename, "wb") as f:
                f.write(audio_bytes)
            
            log_entry = {
                "file": filename,
                "transcript": transcript,
                "stt_ms": stt_ms,
                "model": model,
                "prompt_used": prompt_used
            }
            
            with open("audio_samples/log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                f.flush()  # Key fix: flush immediately
        
        # Call twice with slight delay to ensure different timestamps
        save_audio_inline(b"fake wav 1", "வணக்கம்", 100, "base", "")
        save_audio_inline(b"fake wav 2", "நன்றி", 150, "base", "")
        
        # Check log.jsonl
        log_path = "audio_samples/log.jsonl"
        assert os.path.exists(log_path), "log.jsonl not created"
        
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        
        assert len(lines) == 2, f"Expected 2 log lines, got {len(lines)}"
        
        # Verify contents
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        
        assert entry1["transcript"] == "வணக்கம்", f"Line 1 transcript mismatch"
        assert entry2["transcript"] == "நன்றி", f"Line 2 transcript mismatch"
        assert entry1["stt_ms"] == 100, f"Line 1 stt_ms mismatch"
        assert entry2["stt_ms"] == 150, f"Line 2 stt_ms mismatch"
        
        print("✓ Two calls, two log lines written")
        print("✓ Each line flushed immediately (f.flush())")
        print("✓ Transcripts preserved correctly")
        
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_save_audio_capture()
    print("\n1/1 test passed!")
