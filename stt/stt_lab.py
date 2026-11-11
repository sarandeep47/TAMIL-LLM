#!/usr/bin/env python3
"""
Speech-to-Text lab for comparing Whisper variants and Scribe.
"""
import argparse
import csv
import json
import os
import sys
import time
import unicodedata
import tempfile
import shutil
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from statistics import mean, median


def compute_cer(reference: str, hypothesis: str) -> float:
    """
    Character Error Rate (CER) using Levenshtein distance.
    Normalize: NFC, trim, collapse whitespace, remove punctuation, remove [bracketed] tags.
    Returns: error_count / len(reference)
    """
    def normalize(text):
        # NFC normalization
        text = unicodedata.normalize("NFC", text)
        # Trim leading/trailing whitespace
        text = text.strip()
        # Collapse multiple whitespace into single space
        text = " ".join(text.split())
        # Remove punctuation: . , ! ? ; : " ' and ...
        punctuation = '.,"!?;:\'"'
        for p in punctuation:
            text = text.replace(p, "")
        # Remove [bracketed] audio tags
        text = re.sub(r'\[.*?\]', '', text)
        # Collapse whitespace again after removing brackets
        text = " ".join(text.split())
        # Final trim
        text = text.strip()
        return text
    
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    
    if not ref and not hyp:
        return 0.0
    
    if not ref:
        return 1.0
    
    # Levenshtein distance
    def levenshtein(s1, s2):
        if len(s1) < len(s2):
            return levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        
        return prev_row[-1]
    
    distance = levenshtein(ref, hyp)
    return distance / len(ref)


def load_references(csv_path: str, audio_dir: str = None) -> dict:
    """Load references.csv: file -> expected text. Normalize keys to filenames."""
    refs = {}
    if not os.path.exists(csv_path):
        return refs
    
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("expected"):
                    # Use just the filename as the key
                    filename = os.path.basename(row.get("file", ""))
                    if filename:
                        refs[filename] = row["expected"]
    except Exception as e:
        print(f"Error loading references: {e}")
    
    return refs


def save_references(csv_path: str, log_path: str):
    """Generate references.csv from log.jsonl, merging with existing expected values."""
    # Load existing CSV to preserve non-empty expected values
    existing_expected = {}
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("expected"):
                        # Normalize key to just filename
                        filename = os.path.basename(row.get("file", ""))
                        if filename:
                            existing_expected[filename] = row["expected"]
        except Exception as e:
            print(f"Warning: Could not load existing CSV: {e}")
    
    # Load transcripts from log
    heard_dict = {}
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    filename = os.path.basename(entry.get("file", ""))
                    if filename:
                        heard_dict[filename] = entry.get("transcript", "")
        except Exception as e:
            print(f"Warning: Could not load log: {e}")
    
    # Get audio_dir from log_path
    audio_dir = os.path.dirname(log_path)
    
    # List all WAV files in audio_dir
    rows = []
    wav_files = sorted([f for f in os.listdir(audio_dir) if f.endswith(".wav")])
    
    for wav_file in wav_files:
        heard = heard_dict.get(wav_file, "")
        expected = existing_expected.get(wav_file, "")
        rows.append({
            "file": wav_file,
            "heard": heard,
            "expected": expected
        })
    
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "heard", "expected"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"Created {csv_path}: {len(rows)} rows")
    except Exception as e:
        print(f"Error writing references: {e}")


def get_free_memory_mb() -> tuple:
    """Get free memory in MB (Linux/macOS/Windows). Returns (mb, success)."""
    try:
        try:
            import psutil
            mb = psutil.virtual_memory().available / (1024 * 1024)
            return mb, True
        except ImportError:
            if sys.platform == "win32":
                import ctypes
                # Use GetGlobalMemoryStatus API via a simpler approach
                class MEMORYSTATUSEX(ctypes.Structure):
                    pass
                
                MEMORYSTATUSEX._fields_ = [
                    ("dwLength", ctypes.c_uint),
                    ("dwMemoryLoad", ctypes.c_uint),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                ]
                
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                result = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                if result:
                    mb = stat.ullAvailPhys / (1024 * 1024)
                    return mb, True
                else:
                    return None, False
            else:
                return None, False
    except Exception:
        return None, False


def get_audio_diagnostics(wav_path: str) -> dict:
    """Get audio file diagnostics: duration, peak, RMS."""
    try:
        import soundfile as sf
        import numpy as np
        audio_array, sr = sf.read(wav_path, dtype="float32")
        if len(audio_array.shape) > 1:
            audio_array = audio_array.mean(axis=1)
        
        duration = len(audio_array) / sr
        peak = float(np.max(np.abs(audio_array)))
        rms = float(np.sqrt(np.mean(audio_array ** 2)))
        
        return {
            "duration": duration,
            "peak": peak,
            "rms": rms,
            "success": True
        }
    except Exception as e:
        return {
            "duration": 0,
            "peak": 0,
            "rms": 0,
            "success": False,
            "error": str(e)
        }


def transcribe_whisper(wav_path: str, model_name: str, use_vad: bool = True) -> tuple:
    """
    Transcribe with Whisper (base or small).
    Returns: (text, latency_ms, diagnostics_dict)
    """
    try:
        from faster_whisper import WhisperModel
        
        # Get audio diagnostics
        diag = get_audio_diagnostics(wav_path)
        
        free_mb, mem_ok = get_free_memory_mb()
        
        # Load model and measure load time
        load_start = time.time()
        model = WhisperModel(
            model_name.replace("whisper-", ""),
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            num_workers=1
        )
        load_ms = int((time.time() - load_start) * 1000)
        
        # Print model load time for every model
        print(f"Model load time ({model_name}): {load_ms}ms")
        
        # Read audio
        import soundfile as sf
        audio_array, sr = sf.read(wav_path, dtype="float32")
        if len(audio_array.shape) > 1:
            audio_array = audio_array.mean(axis=1)
        
        # Transcribe with optional VAD and explicit language parameter
        # IMPORTANT: Move timer to include segment consumption (list(segments))
        start = time.time()
        segments, info = model.transcribe(
            audio_array,
            language="ta",  # Explicit Tamil language
            initial_prompt=None,  # No prompt for lab
            beam_size=2,
            best_of=2,
            temperature=0.0,
            condition_on_previous_text=False,
            repetition_penalty=1.2,
            vad_filter=use_vad,
            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.42) if use_vad else None
        )
        
        # Consume segments and measure latency (fixes lazy evaluation timing bug)
        segments_list = list(segments)
        latency_ms = int((time.time() - start) * 1000)
        
        text = "".join([seg.text for seg in segments_list]).strip()
        
        # Get detected language and probability
        detected_lang = info.language if hasattr(info, 'language') else "unknown"
        detected_prob = getattr(info, 'language_probability', 0.0)
        
        print(f"Detected language: {detected_lang} (probability: {detected_prob:.3f})")
        
        # Check for unreasonable latency (model_name is small and latency under 100ms for 1s+ clip and text is non-empty)
        if "small" in model_name and diag.get("duration", 0) >= 1.0 and latency_ms < 100 and text.strip():
            print(f"WARNING: {model_name} transcribed {diag['duration']:.1f}s in {latency_ms}ms (suspiciously fast)")
        
        # Free memory
        del model
        
        # Combine diagnostics
        diag["latency_ms"] = latency_ms
        diag["load_ms"] = load_ms
        diag["empty_output"] = len(text.strip()) == 0
        diag["vad"] = use_vad
        diag["mem_mb"] = free_mb if mem_ok else None
        diag["detected_language"] = detected_lang
        diag["detected_probability"] = detected_prob
        
        return text, latency_ms, diag
    except Exception as e:
        return "", 0, {"error": str(e), "success": False}


def transcribe_scribe(wav_path: str) -> tuple:
    """
    Transcribe with ElevenLabs Scribe API.
    Uses "model_id" field (value "scribe_v2"), "language_code" field (ISO 639-1),
    and "tag_audio_events" field (false to avoid audio event tagging).
    Retries once if language code is rejected.
    Returns: (text, latency_ms, diagnostics_dict)
    Never prints API key or headers.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY not set; skipping scribe")
        return None, 0, {"error": "ELEVENLABS_API_KEY not set"}
    
    # Try language codes in order: ta (ISO 639-1) first, then tam (ISO 639-3) as fallback
    language_codes = ["ta", "tam"]
    
    for attempt, lang_code in enumerate(language_codes):
        try:
            with open(wav_path, "rb") as f:
                wav_data = f.read()
            
            # Build multipart request with model_id, language_code, and tag_audio_events fields
            boundary = "----Boundary123"
            body_parts = [
                f"--{boundary}\r\n",
                f'Content-Disposition: form-data; name="model_id"\r\n',
                f"\r\n",
                f"scribe_v2\r\n",
                f"--{boundary}\r\n",
                f'Content-Disposition: form-data; name="language_code"\r\n',
                f"\r\n",
                f"{lang_code}\r\n",
                f"--{boundary}\r\n",
                f'Content-Disposition: form-data; name="tag_audio_events"\r\n',
                f"\r\n",
                f"false\r\n",
                f"--{boundary}\r\n",
                f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n',
                f"Content-Type: audio/wav\r\n",
                f"\r\n",
            ]
            body = "".join(body_parts).encode() + wav_data + f"\r\n--{boundary}--\r\n".encode()
            
            url = "https://api.elevenlabs.io/v1/speech-to-text"
            req = Request(
                url,
                data=body,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": f"multipart/form-data; boundary={boundary}"
                },
                method="POST"
            )
            
            start = time.time()
            try:
                with urlopen(req, timeout=30) as resp:
                    status_code = resp.status
                    result = json.loads(resp.read())
                    latency_ms = int((time.time() - start) * 1000)
                    
                    print(f"Scribe HTTP {status_code} (language_code={lang_code})")
                    
                    text = result.get("text", "")
                    diag = {
                        "latency_ms": latency_ms,
                        "empty_output": len(text.strip()) == 0,
                        "http_status": status_code,
                        "language_code": lang_code,
                        "success": True
                    }
                    return text, latency_ms, diag
            except HTTPError as e:
                error_code = e.code
                error_body = e.read().decode()
                
                # Check if error is due to language code not being accepted
                if "language" in error_body.lower() and attempt == 0:
                    print(f"Scribe HTTP {error_code}: language_code='{lang_code}' rejected, retrying with '{language_codes[1]}'")
                    continue  # Try next language code
                else:
                    print(f"Scribe HTTP {error_code}")
                    return "", 0, {"error": f"HTTP {error_code}", "http_status": error_code, "language_code": lang_code}
        except Exception as e:
            if attempt == 0:
                continue  # Try next language code on exception
            else:
                return "", 0, {"error": str(e), "success": False}
    
    # If we exhausted all attempts
    return "", 0, {"error": "All language code attempts failed", "success": False}


def run_variants(variants_str: str, limit: int = None, audio_dir: str = None):
    """Run transcription variants and generate results with per-file diagnostics."""
    if not audio_dir:
        audio_dir = "audio_samples"
    
    if not os.path.exists(audio_dir):
        print(f"Error: {audio_dir} not found")
        return
    
    log_path = os.path.join(audio_dir, "log.jsonl")
    csv_path = os.path.join(audio_dir, "references.csv")
    
    # Load references
    references = load_references(csv_path, audio_dir)
    
    # Startup summary (check before running)
    wav_files = [f for f in os.listdir(audio_dir) if f.endswith(".wav")]
    
    # Count rows in references.csv
    csv_rows = 0
    expected_rows = 0
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    csv_rows += 1
                    if row.get("expected"):
                        expected_rows += 1
        except:
            pass
    
    print(f"Startup: {len(wav_files)} WAV files, {csv_rows} rows in references.csv, {expected_rows} with non-empty 'expected'")
    
    if not references or expected_rows == 0:
        print("No references with non-empty 'expected' field. Stopping.")
        return
    
    variants = variants_str.split(",")
    results = []
    
    count = 0
    for wav_file in sorted(os.listdir(audio_dir)):
        if not wav_file.endswith(".wav"):
            continue
        
        wav_path = os.path.join(audio_dir, wav_file)
        expected = references.get(wav_file, "")
        
        if not expected:
            continue
        
        count += 1
        if limit and count > limit:
            break
        
        # Get audio diagnostics
        diag = get_audio_diagnostics(wav_path)
        duration = diag.get("duration", 0)
        peak = diag.get("peak", 0)
        rms = diag.get("rms", 0)
        
        # Print per-file diagnostic header
        status_str = ""
        if duration < 0.5 or rms < 0.005:
            status_str = " [too short or too quiet]"
        print(f"\n{wav_file}: duration={duration:.2f}s, peak={peak:.3f}, rms={rms:.4f}{status_str}")
        
        for variant in variants:
            if variant == "whisper-base":
                text, latency, var_diag = transcribe_whisper(wav_path, variant, use_vad=True)
            elif variant == "whisper-small":
                text, latency, var_diag = transcribe_whisper(wav_path, variant, use_vad=True)
            elif variant == "whisper-base-no-vad":
                text, latency, var_diag = transcribe_whisper(wav_path, "whisper-base", use_vad=False)
            elif variant == "whisper-small-no-vad":
                text, latency, var_diag = transcribe_whisper(wav_path, "whisper-small", use_vad=False)
            elif variant == "scribe":
                text, latency, var_diag = transcribe_scribe(wav_path)
                if text is None:
                    continue  # Skip if env var missing
            else:
                continue
            
            # Print variant line with latency
            vad_info = f" VAD={'on' if var_diag.get('vad', True) else 'off'}" if 'vad' in var_diag else ""
            empty_info = " (empty)" if var_diag.get("empty_output") else ""
            print(f"  {variant}: latency={latency}ms{vad_info}{empty_info}")
            
            # Print expected vs transcript on two lines (raw text)
            print(f"    Expected: {expected}")
            print(f"    Got:      {text}")
            
            cer = compute_cer(expected, text)
            
            results.append({
                "file": wav_file,
                "variant": variant,
                "expected": expected,
                "transcript": text,
                "cer": cer,
                "latency_ms": latency,
                "duration": duration,
                "peak": peak,
                "rms": rms,
                "detected_language": var_diag.get("detected_language", ""),
                "detected_probability": var_diag.get("detected_probability", "")
            })
    
    # Save results to CSV with expected and transcript columns
    results_path = os.path.join(audio_dir, "stt_results.csv")
    try:
        fieldnames = [
            "file", "variant", "expected", "transcript", "cer", "latency_ms",
            "duration", "peak", "rms", "detected_language", "detected_probability"
        ]
        with open(results_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved {results_path}")
    except Exception as e:
        print(f"Error saving results: {e}")
    
    # Print metrics per variant
    by_variant = {}
    for r in results:
        v = r["variant"]
        if v not in by_variant:
            by_variant[v] = []
        by_variant[v].append(r)
    
    print("\nMetrics by variant:")
    for variant in variants:
        if variant not in by_variant:
            print(f"\n{variant}: (no results)")
            continue
        
        rows = by_variant[variant]
        exact_matches = sum(1 for r in rows if compute_cer(r["expected"], r["transcript"]) == 0.0)
        empty_count = sum(1 for r in rows if not r["transcript"])
        cers = [r["cer"] for r in rows if r["transcript"]]
        latencies = [r["latency_ms"] for r in rows]
        
        print(f"\n{variant}:")
        print(f"  Files: {len(rows)}")
        print(f"  Exact matches: {exact_matches}")
        print(f"  Empty outputs: {empty_count}")
        if cers:
            print(f"  Mean CER: {mean(cers):.3f}")
            print(f"  Median CER: {median(cers):.3f}")
        if latencies:
            print(f"  Mean latency: {mean(latencies):.0f} ms")
            print(f"  Median latency: {median(latencies):.0f} ms")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--make-template", action="store_true", help="Generate references.csv from log.jsonl")
    parser.add_argument("--variants", type=str, help="Comma-separated variant list (whisper-base, whisper-small, scribe)")
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument("--audio-dir", type=str, help="Audio directory (default: audio_samples)")
    
    args = parser.parse_args()
    
    # Set UTF-8 encoding for stdout to handle Tamil characters
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    if args.make_template:
        audio_dir = args.audio_dir or "audio_samples"
        log_path = os.path.join(audio_dir, "log.jsonl")
        csv_path = os.path.join(audio_dir, "references.csv")
        save_references(csv_path, log_path)
    
    if args.variants:
        run_variants(args.variants, limit=args.limit, audio_dir=args.audio_dir)


if __name__ == "__main__":
    main()
