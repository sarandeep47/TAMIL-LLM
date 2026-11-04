import time
import requests
import numpy as np
import sounddevice as pd_sound
from faster_whisper import WhisperModel

# ----------------- CONFIGURATION -----------------
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "tamil-voice-qwen"
SAMPLE_RATE = 16000
RECORD_SECONDS = 4   # 4 seconds is ideal for turn-taking
SILENCE_THRESHOLD = 0.015  # RMS energy threshold for speech detection
# -------------------------------------------------

print("Initializing Faster-Whisper (optimized CPU settings)...")
whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8",
    cpu_threads=4,       # Prevent starving Ollama of CPU resources
    num_workers=1
)

def record_audio(duration=RECORD_SECONDS, fs=SAMPLE_RATE):
    print("\n[Listening...] Speak now in Tamil or Tanglish:")
    audio = pd_sound.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
    pd_sound.wait()
    return audio.flatten()

def is_silence(audio_data, threshold=SILENCE_THRESHOLD):
    rms = np.sqrt(np.mean(audio_data**2))
    return rms < threshold

def transcribe_audio(audio_data):
    if is_silence(audio_data):
        return ""
        
    start_time = time.time()
    
    # Prompt priming teaches Whisper the expected vocabulary and style
    tamil_prompt = "வணக்கம், எனக்கு ஒரு கேப் புக் பண்ணனும், ஒரு டவுட் இருக்கு, கார் வேணும், பிக்கப் லொகேஷன்."

    segments, info = whisper_model.transcribe(
        audio_data,
        language="ta",
        initial_prompt=tamil_prompt,       # Guides Whisper on common conversational Tamil/Tanglish words
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
        repetition_penalty=1.2,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500)
    )
    text = "".join([segment.text for segment in segments]).strip()
    latency = round((time.time() - start_time) * 1000)
    
    if text:
        print(f"[STT Latency: {latency}ms] Transcribed: {text}")
    return text

def ask_ollama(prompt_text):
    start_time = time.time()
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt_text,
        "stream": False,
        "options": {
            "num_thread": 4  # Dedicate 4 threads to LLM generation
        }
    }
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        result = response.json().get("response", "").strip()
        latency = round((time.time() - start_time) * 1000)
        print(f"[LLM Latency: {latency}ms] Response: {result}")
        return result
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        return "மன்னிக்கவும், என்னால் தொடர்பு கொள்ள முடியவில்லை."

def main():
    print(f"\n--- Tamil Voice Call Agent Active ({MODEL_NAME}) ---")
    print("Press Ctrl+C to stop.\n")
    
    while True:
        try:
            audio_data = record_audio()
            user_text = transcribe_audio(audio_data)
            
            if not user_text:
                continue
                
            agent_reply = ask_ollama(user_text)
            print(f"\nBot Speaking -> {agent_reply}\n" + "-"*40)
            
        except KeyboardInterrupt:
            print("\nCall ended.")
            break

if __name__ == "__main__":
    main()