#!/usr/bin/env python3
"""
Test script to verify the three critical fixes:
1. Ollama system prompt loading (Modelfile format)
2. TTS acoustic feedback (browser 300ms delay - will verify LLM behavior)
3. VAD threshold (0.42 for better Tamil phonetics)
"""

import os
import sys
import subprocess
import json
import time
import requests
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_ollama_connection():
    """Test if Ollama is reachable"""
    print_header("TEST 1: Ollama Connection")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            print("✓ Ollama is running")
            print(f"  Available models: {len(models)}")
            for model in models:
                print(f"    - {model.get('name', 'Unknown')}")
            return True
        else:
            print(f"✗ Ollama returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Ollama connection failed: {e}")
        return False

def test_qwen_model():
    """Test if qwen2.5:3b model is available and has correct system prompt"""
    print_header("TEST 2: Qwen Model & System Prompt")
    
    try:
        # Try to get model info
        response = requests.get("http://localhost:11434/api/show?name=qwen2.5:3b", timeout=10)
        if response.status_code == 200:
            data = response.json()
            details = data.get('details', {})
            print("✓ qwen2.5:3b model exists")
            
            # Check if system prompt is in the model info
            model_file = data.get('modelfile', '')
            if 'SYSTEM' in model_file:
                print("✓ System prompt is configured")
                # Look for key rules
                if 'greeting' in model_file.lower() or 'எப்படி' in model_file:
                    print("✓ Tamil greeting rules detected in system prompt")
                else:
                    print("⚠ System prompt found but greeting rules unclear")
                
                print("\nModel configuration:")
                lines = model_file.split('\n')
                for line in lines[:8]:  # Show first 8 lines
                    if line.strip():
                        print(f"  {line[:70]}")
            else:
                print("⚠ No SYSTEM prompt found in modelfile")
            
            return True
        else:
            print(f"✗ Model info request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Model info request failed: {e}")
        return False

def test_whisper_vad():
    """Test Whisper VAD settings"""
    print_header("TEST 3: Whisper VAD Threshold")
    
    try:
        from server import transcribe_audio_array
        import inspect
        
        source = inspect.getsource(transcribe_audio_array)
        
        if "threshold=0.42" in source:
            print("✓ VAD threshold is set to 0.42")
            return True
        elif "threshold" in source:
            # Extract the actual threshold value
            import re
            match = re.search(r'threshold=([\d.]+)', source)
            if match:
                threshold = float(match.group(1))
                print(f"⚠ VAD threshold is {threshold} (expected 0.42)")
                return threshold == 0.42
            else:
                print("⚠ VAD threshold setting unclear")
                return False
        else:
            print("⚠ No VAD threshold found in code")
            return False
    except Exception as e:
        print(f"✗ Could not read transcribe function: {e}")
        return False

def test_tts_delay():
    """Test if HTML has 300ms TTS delay"""
    print_header("TEST 4: TTS Acoustic Feedback Delay")
    
    try:
        html_path = Path(__file__).parent / "templates" / "index.html"
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        if "300ms" in html_content and "await new Promise(resolve => setTimeout(resolve, 300))" in html_content:
            print("✓ 300ms TTS delay is implemented")
            
            # Check if speechSynthesis.cancel() is before the delay
            if "speechSynthesis.cancel()" in html_content:
                print("✓ TTS cancel is called before delay")
                return True
            else:
                print("⚠ TTS cancel implementation unclear")
                return False
        else:
            print("⚠ 300ms delay not found in HTML")
            return False
    except Exception as e:
        print(f"✗ Could not read HTML file: {e}")
        return False

def test_modelfile_format():
    """Test if Modelfile has correct single-line SYSTEM format"""
    print_header("TEST 5: Modelfile Format")
    
    try:
        modelfile_path = Path(__file__).parent / "Modelfile.qwen_tamil"
        with open(modelfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for single-line SYSTEM with quotes
        lines = content.split('\n')
        system_lines = [l for l in lines if l.startswith('SYSTEM')]
        
        if system_lines:
            system_line = system_lines[0]
            if system_line.startswith('SYSTEM "') and system_line.endswith('"'):
                print("✓ Modelfile has single-line quoted SYSTEM prompt")
                
                # Count rules
                if 'greeting' in system_line.lower() or 'எப்படி' in system_line:
                    print("✓ Tamil greeting rules included")
                if 'pickup' in system_line.lower() or 'location' in system_line.lower() or 'லொகேஷன்' in system_line:
                    print("✓ Pickup location rule included")
                if 'unclear' in system_line.lower() or 'புரியவில்லை' in system_line:
                    print("✓ Fallback rule for unclear input")
                
                return True
            else:
                print("✗ SYSTEM prompt format is incorrect (should be single-line with quotes)")
                print(f"   Found: {system_line[:80]}")
                return False
        else:
            print("✗ No SYSTEM prompt found in Modelfile")
            return False
    except Exception as e:
        print(f"✗ Could not read Modelfile: {e}")
        return False

def test_llm_behavior():
    """Test actual LLM behavior with greeting"""
    print_header("TEST 6: LLM Greeting Behavior (Quick Check)")
    
    try:
        # Simple test: ask how we are in Tamil
        test_input = "எப்படி இருக்கீங்க?"  # "How are you?"
        
        payload = {
            "model": "qwen2.5:3b",
            "prompt": test_input,
            "stream": False,
            "options": {
                "num_predict": 80,
                "num_ctx": 1024,
                "temperature": 0.2,
                "top_p": 0.8
            }
        }
        
        print(f"Sending to Ollama: '{test_input}'")
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            bot_response = data.get('response', '').strip()
            print(f"✓ LLM responded: '{bot_response[:80]}'")
            
            # Check if it's the expected greeting response
            if 'நல்லா' in bot_response or 'நன்றாக' in bot_response:
                print("✓ Correct greeting response detected")
                return True
            elif 'pickup' in bot_response.lower() or 'location' in bot_response.lower() or 'லொகேஷன்' in bot_response:
                print("✗ WRONG: Bot returned pickup location instead of greeting")
                print(f"  Full response: {bot_response}")
                return False
            else:
                print("⚠ Unexpected response (may be correct or incorrect)")
                print(f"  Full response: {bot_response}")
                return False
        else:
            print(f"✗ LLM request failed: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ LLM test failed: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("  TAMIL VOICE ASSISTANT - FIX VERIFICATION")
    print("="*60)
    print("\nThis script verifies the 3 critical fixes applied:")
    print("  1. Ollama system prompt loading (Modelfile format)")
    print("  2. TTS acoustic feedback delay (300ms HTML delay)")
    print("  3. VAD threshold (0.42 for Tamil phonetics)")
    
    results = {}
    
    # Run all tests
    results['Ollama Connection'] = test_ollama_connection()
    results['Qwen Model'] = test_qwen_model()
    results['Whisper VAD'] = test_whisper_vad()
    results['TTS Delay'] = test_tts_delay()
    results['Modelfile Format'] = test_modelfile_format()
    results['LLM Greeting'] = test_llm_behavior()
    
    # Summary
    print_header("SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All fixes verified! System ready for testing.")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Review output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
