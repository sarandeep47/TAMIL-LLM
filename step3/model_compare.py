#!/usr/bin/env python3
"""
Model comparison: stream responses from Ollama, measure timing and quality flags.
Usage: python model_compare.py --model NAME --label LABEL [--system-mode clean|baked] [--limit N]
"""

import json
import re
import sys
import socket
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Load test cases
cases_file = Path(__file__).parent / "cases.json"
with open(cases_file, encoding="utf-8") as f:
    CASES = json.load(f)

# CLEAN system prompt (identical for every model)
CLEAN_SYSTEM = """You are a friendly Tamil voice assistant that helps people book cabs. Reply in one short, natural, correct spoken-Tamil sentence. If the user writes Tamil in English letters (Tanglish), understand it and reply in Tamil script. If the user writes English, reply in English. Ask for the pickup location, drop location or time when needed. If you do not know something, say so briefly. Never repeat the user's words back. Examples:
User: Anna Nagar la iruken
A: சரி, எங்கே போகணும்?
User: unga peru enna
A: என் பெயர் PersonAI, உங்களுக்கு என்ன உதவி வேணும்?
User: Can you help me?
A: Of course! Where would you like to go?"""

def get_free_ram_mb():
    """Get free RAM in MB using Windows kernel32 API."""
    try:
        import ctypes
        
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullExtendedVirtual", ctypes.c_ulonglong),
            ]
        
        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        
        kernel32 = ctypes.windll.kernel32
        if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status)):
            return int(mem_status.ullAvailPhys / (1024 * 1024))
        else:
            return None
    except Exception:
        return None

def check_ram_warning(model_name, free_mb):
    """Check if free RAM is below threshold for model and return warning message.
    Returns None if RAM could not be read or is above threshold.
    """
    if free_mb is None:
        return None  # Could not read RAM
    
    if model_name in ["qwen3:1.7b", "qwen2.5:3b"]:
        threshold = 2000
    elif model_name in ["qwen3:4b"]:
        threshold = 3000
    elif model_name in ["gemma3:4b"]:
        threshold = 3600
    else:
        threshold = 2000
    
    if free_mb < threshold:
        return f"TIMINGS MAY BE INVALID (swapping) - only {free_mb} MB free (threshold {threshold} MB)"
    return None

def call_ollama(model, user_msg, system_msg=None, retry_no_think=False):
    """
    Stream response from Ollama, measure ttft and total time.
    Return (reply, ttft_ms, total_ms, eval_count, prompt_eval_count, eval_duration, prompt_eval_duration, think_chars).
    """
    url = "http://127.0.0.1:11434/api/chat"
    
    # For qwen3 models (except instruct), ALWAYS append /no_think to user message
    actual_user_msg = user_msg
    # Skip /no_think for instruct models
    if "instruct" not in model:
        models_with_thinking = ["qwen3:4b", "qwen3:1.7b"]
        if any(m in model for m in models_with_thinking) and not user_msg.endswith("/no_think"):
            actual_user_msg = user_msg + " /no_think"
    
    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": actual_user_msg})
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "num_ctx": 2048,
            "num_predict": 80,
            "temperature": 0.2,
            "top_p": 0.8,
            "num_thread": 4
        },
        "keep_alive": "5m"
    }
    
    # Add think field only for models with thinking capability (exclude instruct)
    if "instruct" not in model:
        models_with_thinking = ["qwen3:4b", "qwen3:1.7b"]
        if any(m in model for m in models_with_thinking):
            payload["think"] = False
    
    # DEBUG: Print payload before sending (only for smoke tests with limit 1)
    import os
    if "--limit" in " ".join(sys.argv) and "1" in " ".join(sys.argv):
        print("\n=== PAYLOAD DEBUG ===")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("=== END PAYLOAD ===\n")
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    reply = ""
    thinking = ""
    ttft_ms = None
    first_token_time = None
    total_start = time.time()
    eval_count = 0
    prompt_eval_count = 0
    eval_duration = 0
    prompt_eval_duration = 0
    load_duration = 0
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line_bytes in resp:
                line = line_bytes.decode("utf-8").strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                except:
                    continue
                
                # Record first token time (for content, not thinking)
                if first_token_time is None and data.get("message", {}).get("content"):
                    first_token_time = time.time()
                    ttft_ms = int((first_token_time - total_start) * 1000)
                
                # Accumulate thinking separately
                if "message" in data and "thinking" in data["message"]:
                    thinking += data["message"]["thinking"]
                
                # Accumulate reply content
                if "message" in data and "content" in data["message"]:
                    reply += data["message"]["content"]
                
                # Get final metrics
                if data.get("done"):
                    eval_count = data.get("eval_count", 0)
                    prompt_eval_count = data.get("prompt_eval_count", 0)
                    eval_duration = data.get("eval_duration", 0)
                    prompt_eval_duration = data.get("prompt_eval_duration", 0)
                    load_duration = data.get("load_duration", 0)
    
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        # Check if it's a timeout
        if isinstance(e, urllib.error.URLError) and "timed out" in str(e).lower():
            return "TIMEOUT", 0, 0, 0, 0, 0, 0, len(thinking)
        
        # Check if it's a think rejection - retry once with /no_think
        if "qwen3" in model and not retry_no_think and ("think" in str(e) or "400" in str(e)):
            return call_ollama(model, user_msg, system_msg, retry_no_think=True)
        raise
    except socket.timeout:
        return "TIMEOUT", 0, 0, 0, 0, 0, 0, len(thinking)
    
    total_ms = int((time.time() - total_start) * 1000)
    
    if ttft_ms is None:
        ttft_ms = total_ms  # No streaming response
    
    # Strip <think>...</think> blocks from reply
    reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()
    
    return reply, ttft_ms, total_ms, eval_count, prompt_eval_count, eval_duration, prompt_eval_duration, len(thinking)

def check_flags(reply, input_text, expect_lang, timeout=False):
    """Check auto flags for quality issues."""
    flags = []
    
    # timeout flag
    if timeout:
        flags.append("timeout")
    
    # reasoning_leak: reply starts with common reasoning phrases or contains reasoning markers
    reasoning_starters = ("Okay,", "Let me", "Let's", "Wait", "<think")
    if any(reply.startswith(starter) for starter in reasoning_starters) or "the user wrote" in reply or "the user said" in reply:
        flags.append("reasoning_leak")
    
    # empty
    if not reply.strip() or reply == "TIMEOUT":
        flags.append("empty")
    
    # no_tamil_script
    if expect_lang == "ta":
        tamil_chars = len([c for c in reply if '\u0B80' <= c <= '\u0BFF'])
        if tamil_chars == 0:
            flags.append("no_tamil_script")
    
    # not_english
    if expect_lang == "en":
        tamil_chars = len([c for c in reply if '\u0B80' <= c <= '\u0BFF'])
        if tamil_chars > 3:
            flags.append("not_english")
    
    # has_cjk (Chinese, Japanese)
    cjk_chars = len([c for c in reply if ('\u4E00' <= c <= '\u9FFF') or ('\u3040' <= c <= '\u30FF')])
    if cjk_chars > 0:
        flags.append("has_cjk")
    
    # other_script (Arabic, Cyrillic, Hebrew, Hangul)
    other_chars = len([c for c in reply if 
                      ('\u0600' <= c <= '\u06FF') or  # Arabic
                      ('\u0400' <= c <= '\u04FF') or  # Cyrillic
                      ('\u0590' <= c <= '\u05FF') or  # Hebrew
                      ('\uAC00' <= c <= '\uD7AF')])   # Hangul
    if other_chars > 0:
        flags.append("other_script")
    
    # fallback_phrase
    if "புரியவில்லை" in reply:
        flags.append("fallback_phrase")
    
    # too_long
    sentence_count = reply.count('.') + reply.count('?') + reply.count('!')
    if sentence_count > 2 or len(reply) > 160:
        flags.append("too_long")
    
    # repetition (3-word sequence repeated 3+ times)
    words = reply.split()
    if len(words) >= 9:  # Need at least 9 words for a 3-word sequence to repeat 3 times
        for i in range(len(words) - 8):
            seq = ' '.join(words[i:i+3])
            count = sum(1 for j in range(len(words) - 2) if ' '.join(words[j:j+3]) == seq)
            if count >= 3:
                flags.append("repetition")
                break
    
    # role_prefix_leak (reply starts with "A:" or "Assistant:")
    if reply.startswith("A:") or reply.startswith("Assistant:"):
        flags.append("role_prefix_leak")
    
    # mixed_script_noise (Latin words in Tamil reply, excluding place names)
    if expect_lang == "ta" and len([c for c in reply if '\u0B80' <= c <= '\u0BFF']) > 0:
        # Simple heuristic: look for English words (sequences of Latin letters > 3 chars)
        # excluding common place names and abbreviations
        latin_words = re.findall(r'\b[a-zA-Z]{4,}\b', reply)
        place_names = {'Chennai', 'Anna', 'Nagar', 'Madurai', 'Tidel', 'Park', 'PersonAI', 'Central', 'Tamil', 'English'}
        foreign_words = [w for w in latin_words if w not in place_names]
        if foreign_words:
            flags.append("mixed_script_noise")
    
    return flags

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Model name (e.g., qwen2.5:3b)")
    parser.add_argument("--label", required=True, help="Output label (e.g., qwen25-3b-clean)")
    parser.add_argument("--system-mode", choices=["clean", "baked"], default="clean")
    parser.add_argument("--limit", type=int, default=None, help="Limit to N cases (for testing)")
    
    args = parser.parse_args()
    
    model = args.model
    label = args.label
    system_mode = args.system_mode
    limit = args.limit
    
    # Get free RAM
    free_mb = get_free_ram_mb()
    ram_warning = check_ram_warning(model, free_mb)
    
    print(f"\n=== Model: {model} (label: {label}) ===")
    if free_mb is None:
        print(f"Free RAM: unknown")
    else:
        print(f"Free RAM: {free_mb} MB")
    if ram_warning:
        print(f"WARNING: {ram_warning}")
    print()
    
    # Warm-up (unrecorded)
    print("Warming up...")
    try:
        result = call_ollama(
            model,
            "Hi",
            CLEAN_SYSTEM if system_mode == "clean" else None
        )
        reply, ttft_ms, total_ms, eval_count, prompt_eval_count, eval_duration, prompt_eval_duration, think_chars = result
        # Convert load_duration from nanoseconds to milliseconds
        load_duration_ms = prompt_eval_duration / 1_000_000 if prompt_eval_duration else 0
        print(f"  Warm-up complete (load_duration: {load_duration_ms:.1f}ms)")
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    
    # Prepare CSV
    output_file = Path(__file__).parent / f"results_{label}.csv"
    
    csv_header = "id,category,input,reply,ttft_ms,total_ms,prefill_ms,eval_count,prompt_eval_count,tokens_per_sec,think_chars,empty,no_tamil_script,not_english,has_cjk,other_script,fallback_phrase,too_long,repetition,role_prefix_leak,mixed_script_noise,reasoning_leak,timeout,meaning_0_2,grammar_0_2,natural_0_2\n"
    
    rows = []
    cases_to_run = CASES[:limit] if limit else CASES
    
    for case in cases_to_run:
        case_id = case["id"]
        category = case["category"]
        input_text = case["input"]
        expect_lang = case["expect_lang"]
        
        try:
            reply, ttft_ms, total_ms, eval_count, prompt_eval_count, eval_duration, prompt_eval_duration, think_chars = call_ollama(
                model,
                input_text,
                CLEAN_SYSTEM if system_mode == "clean" else None
            )
            
            # Check for timeout
            is_timeout = (reply == "TIMEOUT")
            
            # Compute timing metrics
            # tokens_per_sec = eval_count / (eval_duration / 1e9) where eval_duration is in nanoseconds
            tokens_per_sec = 0
            if eval_duration > 0 and eval_count > 0:
                tokens_per_sec = round(eval_count / (eval_duration / 1e9), 2)
            
            # Prefill time (prompt_eval_duration in ms)
            prefill_ms = round(prompt_eval_duration / 1e6) if prompt_eval_duration > 0 else 0
            
            # Check flags
            flags = check_flags(reply, input_text, expect_lang, timeout=is_timeout)
            flag_values = {
                "empty": 1 if "empty" in flags else 0,
                "no_tamil_script": 1 if "no_tamil_script" in flags else 0,
                "not_english": 1 if "not_english" in flags else 0,
                "has_cjk": 1 if "has_cjk" in flags else 0,
                "other_script": 1 if "other_script" in flags else 0,
                "fallback_phrase": 1 if "fallback_phrase" in flags else 0,
                "too_long": 1 if "too_long" in flags else 0,
                "repetition": 1 if "repetition" in flags else 0,
                "role_prefix_leak": 1 if "role_prefix_leak" in flags else 0,
                "mixed_script_noise": 1 if "mixed_script_noise" in flags else 0,
                "reasoning_leak": 1 if "reasoning_leak" in flags else 0,
                "timeout": 1 if is_timeout else 0,
            }
            
            # Build row
            row = [
                str(case_id),
                category,
                input_text,  # Will be written to CSV as-is (UTF-8)
                reply,       # Will be written to CSV as-is (UTF-8)
                str(ttft_ms),
                str(total_ms),
                str(prefill_ms),
                str(eval_count),
                str(prompt_eval_count),
                str(tokens_per_sec),
                str(think_chars),
                str(flag_values["empty"]),
                str(flag_values["no_tamil_script"]),
                str(flag_values["not_english"]),
                str(flag_values["has_cjk"]),
                str(flag_values["other_script"]),
                str(flag_values["fallback_phrase"]),
                str(flag_values["too_long"]),
                str(flag_values["repetition"]),
                str(flag_values["role_prefix_leak"]),
                str(flag_values["mixed_script_noise"]),
                str(flag_values["reasoning_leak"]),
                str(flag_values["timeout"]),
                "",  # meaning_0_2 (manual)
                "",  # grammar_0_2 (manual)
                "",  # natural_0_2 (manual)
            ]
            rows.append(row)
            
            # Print (use errors="replace" for console output)
            try:
                print_reply = reply.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                print(f"Case {case_id}:")
                print(f"  FULL REPLY: {print_reply}")
                print(f"  eval_count={eval_count}, think_chars={think_chars}, ttft_ms={ttft_ms}, prefill_ms={prefill_ms}, total_ms={total_ms}, tokens_per_sec={tokens_per_sec}")
            except Exception as print_err:
                print(f"Case {case_id}: (print error: {print_err})")
                print(f"  eval_count={eval_count}, think_chars={think_chars}, ttft_ms={ttft_ms}, prefill_ms={prefill_ms}, total_ms={total_ms}, tokens_per_sec={tokens_per_sec}")
        
        except Exception as e:
            print(f"Case {case_id}: ERROR - {e}")
            rows.append([str(case_id), category, input_text, f"ERROR: {str(e)}", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    
    # Write CSV with BOM
    # Count duplicate replies
    reply_counts = {}
    for row in rows:
        reply_text = row[3]
        if reply_text and reply_text != "TIMEOUT":
            reply_counts[reply_text] = reply_counts.get(reply_text, 0) + 1
    
    most_common_reply = None
    most_common_count = 0
    if reply_counts:
        most_common_reply, most_common_count = max(reply_counts.items(), key=lambda x: x[1])
    
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        # Write comment header with RAM warning if present
        if ram_warning:
            f.write(f"# {ram_warning}\n")
        elif free_mb is not None:
            f.write(f"# Free RAM at run: {free_mb} MB\n")
        # If free_mb is None, don't write a RAM comment line
        
        # Write duplicate replies comment
        if most_common_reply:
            truncated_reply = (most_common_reply[:50] + "...") if len(most_common_reply) > 50 else most_common_reply
            f.write(f"# most common reply x{most_common_count}: {truncated_reply}\n")
        
        # Write header
        f.write(csv_header)
        
        # Write rows
        for row in rows:
            # Escape quotes in cells
            escaped_row = []
            for cell in row:
                if '"' in cell:
                    cell = cell.replace('"', '""')
                if ',' in cell or '\n' in cell:
                    cell = f'"{cell}"'
                escaped_row.append(cell)
            f.write(','.join(escaped_row) + '\n')
    
    print(f"\nResults saved to {output_file}")
    print(f"Completed {len(rows)} cases\n")

if __name__ == "__main__":
    main()
