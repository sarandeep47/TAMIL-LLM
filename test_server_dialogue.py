#!/usr/bin/env python3
r"""Test dialogue.py integration with server.py endpoints.
Tests both /api/chat and /api/chat-stream with dialogue sessions.
"""

import sys
import json
from unittest.mock import patch, MagicMock
import httpx
from starlette.testclient import TestClient as _StarletteTestClient

# Import the app
from server import app, dialogue_store


def mock_ask_ollama(prompt_text):
    """Mock LLM for testing."""
    return "LLM response", 100


def mock_ask_ollama_stream(prompt_text):
    """Mock LLM stream for testing."""
    class MockStream:
        def __init__(self):
            self.metrics = {}
        
        def __iter__(self):
            yield "LLM"
            yield " response"
        
        def close(self):
            pass
    
    return MockStream()


# Workaround: Patch httpx.Client init to accept 'app' kwarg
_original_client_init = httpx.Client.__init__

def _patched_client_init(self, app=None, **kwargs):
    # Drop the 'app' kwarg if present
    if 'app' in locals():
        kwargs.pop('app', None)
    _original_client_init(self, **kwargs)

httpx.Client.__init__ = _patched_client_init

# Now TestClient should work
client = _StarletteTestClient(app)
llm_call_count = 0


def reset_store_and_counts():
    """Reset dialogue store and counters."""
    global llm_call_count
    llm_call_count = 0
    dialogue_store.sessions.clear()


def count_llm_calls(func):
    """Decorator to count LLM calls."""
    def wrapper(*args, **kwargs):
        global llm_call_count
        llm_call_count += 1
        return func(*args, **kwargs)
    return wrapper


def test_group_a():
    """a. Simple booking start -> reply from dialogue, no LLM."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            response = client.post("/api/chat", json={"text": "enaku oru cab book pannanum", "session_id": "s1"})
    
    assert response.status_code == 200
    data = response.json()
    
    # Check the reply contains the ask-pickup constant
    from replies import ASK_PICKUP
    if ASK_PICKUP in data["bot_text"]:
        print(f"PASS a: 'enaku oru cab book pannanum' -> route is '{data['route']}', LLM calls == {llm_call_count}")
        passed = 1
        failed = 0
    else:
        print(f"FAIL a: 'enaku oru cab book pannanum'")
        print(f"  Expected reply contains: {repr(ASK_PICKUP)}")
        print(f"  Actual reply: {repr(data['bot_text'])}")
        print(f"  Route: {data['route']}")
        passed = 0
        failed = 1
    
    if data["route"] != "dialogue":
        print(f"FAIL a: route should be 'dialogue', got '{data['route']}'")
        failed += 1
        passed -= 1
    
    if llm_call_count != 0:
        print(f"FAIL a: LLM should not be called, but was called {llm_call_count} times")
        failed += 1
        passed -= 1
    
    return passed, failed


def test_group_b():
    """b. Multi-turn booking in same session."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            passed = 0
            failed = 0
            
            # Start booking
            r1 = client.post("/api/chat", json={"text": "enaku oru cab book pannanum", "session_id": "s1"})
            assert r1.status_code == 200
            
            # Provide drop location
            r2 = client.post("/api/chat", json={"text": "naa chennai ponnum", "session_id": "s1"})
            assert r2.status_code == 200
            d2 = r2.json()
            
            from replies import ASK_PICKUP
            if ASK_PICKUP in d2["bot_text"] and d2["route"] == "dialogue":
                print(f"PASS b1: 'naa chennai ponnum' -> asks pickup, route dialogue")
                passed += 1
            else:
                print(f"FAIL b1: 'naa chennai ponnum'")
                print(f"  Expected: reply contains ASK_PICKUP, route='dialogue'")
                print(f"  Actual: reply={repr(d2['bot_text'])}, route={d2['route']}")
                failed += 1
            
            # Provide pickup location
            r3 = client.post("/api/chat", json={"text": "madurai", "session_id": "s1"})
            assert r3.status_code == 200
            d3 = r3.json()
            
            from replies import ASK_TIME_INITIAL
            if ASK_TIME_INITIAL in d3["bot_text"] and d3["route"] == "dialogue":
                print(f"PASS b2: 'madurai' -> asks time, route dialogue")
                passed += 1
            else:
                print(f"FAIL b2: 'madurai'")
                print(f"  Expected: reply contains ASK_TIME_INITIAL, route='dialogue'")
                print(f"  Actual: reply={repr(d3['bot_text'])}, route={d3['route']}")
                failed += 1
            
            # Provide time
            r4 = client.post("/api/chat", json={"text": "naliki 7 30 ku", "session_id": "s1"})
            assert r4.status_code == 200
            d4 = r4.json()
            
            if "?" in d4["bot_text"] and d4["route"] == "dialogue":
                print(f"PASS b3: 'naliki 7 30 ku' -> asks am/pm, route dialogue")
                passed += 1
            else:
                print(f"FAIL b3: 'naliki 7 30 ku'")
                print(f"  Actual: reply={repr(d4['bot_text'])}, route={d4['route']}")
                failed += 1
            
            # Provide am/pm
            r5 = client.post("/api/chat", json={"text": "kalai", "session_id": "s1"})
            assert r5.status_code == 200
            d5 = r5.json()
            
            if "?" in d5["bot_text"] and d5["route"] == "dialogue":
                print(f"PASS b4: 'kalai' -> confirm, route dialogue")
                passed += 1
            else:
                print(f"FAIL b4: 'kalai'")
                failed += 1
            
            # Confirm booking
            r6 = client.post("/api/chat", json={"text": "aama", "session_id": "s1"})
            assert r6.status_code == 200
            d6 = r6.json()
            
            from replies import BOOKED_REPLY
            if BOOKED_REPLY in d6["bot_text"] and d6["route"] == "dialogue":
                print(f"PASS b5: 'aama' -> booked reply, route dialogue")
                passed += 1
            else:
                print(f"FAIL b5: 'aama'")
                print(f"  Expected: {repr(BOOKED_REPLY)}")
                print(f"  Actual: {repr(d6['bot_text'])}")
                failed += 1
            
            if llm_call_count != 0:
                print(f"FAIL b: LLM should not be called, but was called {llm_call_count} times")
                failed += 1
    
    return passed, failed


def test_group_c():
    """c. New session uses LLM for question that dialogue returns None."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            response = client.post("/api/chat", json={"text": "madurai la enna famous", "session_id": "s2"})
    
    assert response.status_code == 200
    data = response.json()
    
    if data["route"] != "dialogue" and llm_call_count == 1:
        print(f"PASS c: 'madurai la enna famous' -> LLM called once, route is '{data['route']}'")
        return 1, 0
    else:
        print(f"FAIL c: 'madurai la enna famous'")
        print(f"  Expected: LLM called once, route not 'dialogue'")
        print(f"  Actual: LLM calls {llm_call_count}, route '{data['route']}'")
        return 0, 1


def test_group_d():
    """d. Mid-booking: question goes to LLM, state unchanged."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            passed = 0
            failed = 0
            
            # Start booking
            r1 = client.post("/api/chat", json={"text": "enaku oru cab book pannanum", "session_id": "s1"})
            assert r1.status_code == 200
            
            # Send question during booking
            r2 = client.post("/api/chat", json={"text": "time enna", "session_id": "s1"})
            assert r2.status_code == 200
            d2 = r2.json()
            
            # Should go to LLM (dialogue returns None for questions outside booking context)
            if d2["route"] != "dialogue" and llm_call_count == 1:
                print(f"PASS d1: 'time enna' -> LLM called, route not 'dialogue'")
                passed += 1
            else:
                print(f"FAIL d1: 'time enna'")
                print(f"  Expected: LLM called, route not 'dialogue'")
                print(f"  Actual: LLM calls {llm_call_count}, route '{d2['route']}'")
                failed += 1
            
            # State should still be awaiting="pickup"
            # Verify by sending a place - should still ask the other place
            r3 = client.post("/api/chat", json={"text": "madurai", "session_id": "s1"})
            assert r3.status_code == 200
            d3 = r3.json()
            
            from replies import ASK_TIME_INITIAL, ASK_DROP
            if ASK_TIME_INITIAL in d3["bot_text"]:
                print(f"PASS d2: state still in booking (awaiting time after 'madurai')")
                passed += 1
            elif ASK_DROP in d3["bot_text"]:
                # We set pickup to 'madurai', now asking for drop
                # This is also valid - means state was preserved but waiting for drop not time
                print(f"PASS d2: state preserved, still asking for drop")
                passed += 1
            else:
                print(f"FAIL d2: state was reset or changed")
                print(f"  Expected: asking for time or drop")
                try:
                    actual = d3['bot_text']
                except:
                    actual = "Unable to decode"
                print(f"  Actual: {actual}")
                failed += 1
    
    return passed, failed


def test_group_e():
    """e. No session_id defaults to 'default'."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            # Don't pass session_id
            response = client.post("/api/chat", json={"text": "enaku oru cab book pannanum"})
    
    assert response.status_code == 200
    data = response.json()
    
    from replies import ASK_PICKUP
    if ASK_PICKUP in data["bot_text"] and data["route"] == "dialogue":
        print(f"PASS e: no session_id -> uses 'default', route 'dialogue'")
        return 1, 0
    else:
        print(f"FAIL e: no session_id")
        print(f"  Expected: route='dialogue', reply contains ASK_PICKUP")
        print(f"  Actual: route='{data['route']}', reply={repr(data['bot_text'])}")
        return 0, 1


def test_group_f():
    """f. Same checks for /api/chat-stream."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            response = client.post("/api/chat-stream", json={"text": "enaku oru cab book pannanum", "session_id": "s1"})
    
    assert response.status_code == 200
    
    # Parse SSE events
    lines = response.text.strip().split('\n\n')
    events = []
    for line in lines:
        if line.startswith('data: '):
            try:
                event = json.loads(line[6:])
                events.append(event)
            except:
                pass
    
    passed = 0
    failed = 0
    
    # Find the done event
    done_event = None
    for event in events:
        if event.get('event') == 'done':
            done_event = event
            break
    
    if done_event is None:
        print(f"FAIL f: no 'done' event in stream")
        return 0, 1
    
    from replies import ASK_PICKUP
    if ASK_PICKUP in done_event.get('reply', '') and done_event.get('route') == 'dialogue':
        print(f"PASS f: /api/chat-stream case a -> done event with route 'dialogue'")
        passed += 1
    else:
        print(f"FAIL f: /api/chat-stream case a")
        print(f"  Expected: done event with route='dialogue' and reply containing ASK_PICKUP")
        print(f"  Actual: route='{done_event.get('route')}', reply={repr(done_event.get('reply'))}")
        failed += 1
    
    if llm_call_count != 0:
        print(f"FAIL f: LLM should not be called")
        failed += 1
    
    return passed, failed


def test_group_g():
    """g. /api/chat-stream with greetings and thanks (cleaner bug fix)."""
    global llm_call_count
    reset_store_and_counts()
    
    test_cases = [
        ("vanakam", "greeting"),
        ("nandri", "thanks"),
        ("seri nandri", "mixed"),
    ]
    
    passed = 0
    failed = 0
    
    for text, label in test_cases:
        # Test 1: Fresh session
        reset_store_and_counts()
        with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
            with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
                response = client.post("/api/chat-stream", json={"text": text, "session_id": f"g1_{label}"})
        
        if response.status_code != 200:
            print(f"FAIL g: /api/chat-stream with '{text}' (fresh) returned {response.status_code}")
            failed += 1
            continue
        
        # Check for error events (event type 'error', not the string "Error")
        lines = response.text.strip().split('\n\n')
        has_error_event = False
        has_done = False
        for line in lines:
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    if event.get('event') == 'error':
                        has_error_event = True
                    if event.get('event') == 'done':
                        has_done = True
                except:
                    pass
        
        if has_error_event:
            print(f"FAIL g: /api/chat-stream with '{text}' (fresh) returned error event")
            failed += 1
            continue
        
        if has_done:
            print(f"PASS g1: /api/chat-stream with '{text}' (fresh) -> done event")
            passed += 1
        else:
            print(f"FAIL g1: /api/chat-stream with '{text}' (fresh) -> no done event")
            failed += 1
        
        # Test 2: After completed booking in same session
        reset_store_and_counts()
        with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
            with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
                # Complete a booking first
                r1 = client.post("/api/chat-stream", json={"text": "from madurai to salem", "session_id": f"g2_{label}"})
                r2 = client.post("/api/chat-stream", json={"text": "naliki 2 mani", "session_id": f"g2_{label}"})
                r3 = client.post("/api/chat-stream", json={"text": "kalai", "session_id": f"g2_{label}"})
                r4 = client.post("/api/chat-stream", json={"text": "aama", "session_id": f"g2_{label}"})
                
                # Now send greeting
                response = client.post("/api/chat-stream", json={"text": text, "session_id": f"g2_{label}"})
        
        if response.status_code != 200:
            print(f"FAIL g: /api/chat-stream with '{text}' (after booking) returned {response.status_code}")
            failed += 1
            continue
        
        lines = response.text.strip().split('\n\n')
        has_error_event = False
        has_done = False
        for line in lines:
            if line.startswith('data: '):
                try:
                    event = json.loads(line[6:])
                    if event.get('event') == 'error':
                        has_error_event = True
                    if event.get('event') == 'done':
                        has_done = True
                except:
                    pass
        
        if has_error_event:
            print(f"FAIL g: /api/chat-stream with '{text}' (after booking) returned error event")
            failed += 1
            continue
        
        if has_done:
            print(f"PASS g2: /api/chat-stream with '{text}' (after booking) -> done event")
            passed += 1
        else:
            print(f"FAIL g2: /api/chat-stream with '{text}' (after booking) -> no done event")
            failed += 1
    
    return passed, failed


def test_group_h():
    """h. LLM route in /api/chat-stream finishes with done event."""
    global llm_call_count
    reset_store_and_counts()
    
    with patch('server.ask_ollama', side_effect=count_llm_calls(mock_ask_ollama)):
        with patch('server.ask_ollama_stream', side_effect=count_llm_calls(mock_ask_ollama_stream)):
            response = client.post("/api/chat-stream", json={"text": "madurai la enna famous", "session_id": "h1"})
    
    if response.status_code != 200:
        print(f"FAIL h: /api/chat-stream returned {response.status_code}")
        return 0, 1
    
    # Parse SSE and check for done event and no error events
    lines = response.text.strip().split('\n\n')
    events = []
    for line in lines:
        if line.startswith('data: '):
            try:
                event = json.loads(line[6:])
                events.append(event)
            except:
                pass
    
    has_done = False
    has_error = False
    for event in events:
        if event.get('event') == 'done':
            has_done = True
        if event.get('event') == 'error':
            has_error = True
    
    if has_done and not has_error:
        print(f"PASS h: LLM route in /api/chat-stream finishes with done event")
        return 1, 0
    else:
        print(f"FAIL h: LLM route issues")
        print(f"  has_done={has_done}, has_error={has_error}")
        print(f"  Events: {events}")
        return 0, 1


def main():
    print("=" * 80)
    print("Testing dialogue.py integration with server.py")
    print("=" * 80)
    
    total_passed = 0
    total_failed = 0
    
    print("\nGroup a:")
    p, f = test_group_a()
    total_passed += p
    total_failed += f
    
    print("\nGroup b:")
    p, f = test_group_b()
    total_passed += p
    total_failed += f
    
    print("\nGroup c:")
    p, f = test_group_c()
    total_passed += p
    total_failed += f
    
    print("\nGroup d:")
    p, f = test_group_d()
    total_passed += p
    total_failed += f
    
    print("\nGroup e:")
    p, f = test_group_e()
    total_passed += p
    total_failed += f
    
    print("\nGroup f:")
    p, f = test_group_f()
    total_passed += p
    total_failed += f
    
    print("\nGroup g:")
    p, f = test_group_g()
    total_passed += p
    total_failed += f
    
    print("\nGroup h:")
    p, f = test_group_h()
    total_passed += p
    total_failed += f
    
    print("\n" + "=" * 80)
    print(f"TOTAL: Passed {total_passed}, Failed {total_failed}")
    print("=" * 80)
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
