#!/usr/bin/env python3
"""
Debug message flow through the entire pipeline.
Logs each step: sentence detection, topic extraction, operation routing, response selection.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from datetime import datetime
from chat_memory import (
    detect_intent, detect_language_style, acknowledge_statement, answer_question,
    _detect_statement_intent, is_personal_history_question
)
from fact_extractor import extract_facts, _looks_like_personal_statement
from tanglish_understanding import understand_tanglish
from memory_db import initialize_database, get_memory, list_memories
from chatbot import ask_ollama

# Initialize
initialize_database()

def log_message_flow(user_input: str):
    """Log complete message processing flow."""
    print("\n" + "="*80)
    print(f"MESSAGE FLOW TRACE: {repr(user_input)}")
    print("="*80)
    
    log = {
        "timestamp": datetime.now().isoformat(),
        "original_message": user_input,
        "steps": {}
    }
    
    # Step 1: Language detection
    language = detect_language_style(user_input)
    log["steps"]["language_style"] = language
    print(f"\n[LANG] Detected language: {language}")
    
    # Step 2: Tanglish understanding
    tanglish = understand_tanglish(user_input)
    log["steps"]["tanglish_intent"] = {
        "sentence_type": tanglish.sentence_type,
        "topic": tanglish.topic,
        "tense": tanglish.tense,
        "operation": tanglish.operation,
        "confidence": tanglish.confidence,
        "memory_key": tanglish.memory_key,
        "entities": tanglish.entities
    }
    print(f"[TANGLISH]")
    print(f"  sentence_type: {tanglish.sentence_type}")
    print(f"  topic: {tanglish.topic}")
    print(f"  operation: {tanglish.operation}")
    print(f"  confidence: {tanglish.confidence:.2f}")
    print(f"  memory_key: {tanglish.memory_key}")
    print(f"  entities: {tanglish.entities}")
    
    # Step 3: Fact extraction pipeline
    looks_like_stmt = _looks_like_personal_statement(user_input)
    log["steps"]["looks_like_personal_statement"] = looks_like_stmt
    print(f"\n[EXTRACTION GATE] _looks_like_personal_statement: {looks_like_stmt}")
    
    extracted = extract_facts(user_input) if looks_like_stmt else []
    log["steps"]["extracted_facts"] = [
        {"key": f.key, "value": f.value, "source": f.source, "confidence": f.confidence}
        for f in extracted
    ]
    print(f"[EXTRACTION] Extracted {len(extracted)} facts:")
    for fact in extracted:
        print(f"  - {fact.key} = {fact.value} (source={fact.source}, conf={fact.confidence:.2f})")
    
    # Step 4: Memory queries
    print(f"\n[MEMORY STATE] Current saved facts:")
    current_facts = list_memories()
    if not current_facts:
        print(f"  (empty)")
    else:
        for mem in current_facts:
            print(f"  - {mem['key']} = {mem['value']} (source={mem['source']})")
    
    # Step 5: Intent detection for questions
    det_intent = detect_intent(user_input)
    log["steps"]["detect_intent"] = det_intent
    print(f"\n[DETECT_INTENT] Question intent: {det_intent}")
    
    stmt_intent = _detect_statement_intent(user_input)
    log["steps"]["detect_statement_intent"] = stmt_intent
    print(f"[DETECT_STATEMENT] Statement intent: {stmt_intent}")
    
    is_phq = is_personal_history_question(user_input)
    log["steps"]["is_personal_history_question"] = is_phq
    print(f"[PERSONAL_HISTORY_GUARD] Is personal-history question: {is_phq}")
    
    # Step 6: Deterministic response attempts
    print(f"\n[DETERMINISTIC SHORT-CIRCUITS]")
    
    ack_stmt = acknowledge_statement(user_input)
    log["steps"]["acknowledge_statement_result"] = ack_stmt
    print(f"  acknowledge_statement(): {ack_stmt}")
    
    ans_quest = answer_question(user_input)
    log["steps"]["answer_question_result"] = ans_quest
    print(f"  answer_question(): {ans_quest}")
    
    # Step 7: Ollama fallback
    if ack_stmt:
        response = ack_stmt
        source = "acknowledge_statement"
    elif ans_quest:
        response = ans_quest
        source = "answer_question"
    else:
        print(f"\n[OLLAMA FALLBACK] No deterministic response, calling Ollama...")
        response = ask_ollama(user_input)
        source = "ollama"
    
    log["steps"]["selected_response_source"] = source
    log["steps"]["final_response"] = response
    
    print(f"\n[RESPONSE SOURCE] {source}")
    print(f"[RESPONSE] {response[:100]}..." if len(response) > 100 else f"[RESPONSE] {response}")
    
    # Print JSON log
    print(f"\n[LOG] {json.dumps(log, indent=2)}")
    
    return log


# Test messages from the issue
test_messages = [
    "vannakam",
    "en peru Sarandeep",
    "naa Madurai la iruken",
    "naa enga iruken",
    "naa enna padichen nu sollu",
    "naa enga college la padichen",
    "Which degree have I completed"
]

for msg in test_messages:
    try:
        log_message_flow(msg)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("DEBUG SESSION COMPLETE")
print("="*80)
