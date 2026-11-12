#!/usr/bin/env python3
r"""Test dialogue state machine for Tamil cab booking.
All strings are in \uXXXX escapes to avoid encoding issues.
"""

import sys

# Encoding check: ensure no non-ASCII characters in source
with open(__file__, 'rb') as f:
    content = f.read()
    if any(b > 127 for b in content):
        print("ERROR: test_dialogue.py contains non-ASCII characters")
        sys.exit(1)

from dialogue import DialogueState, handle
from replies import (
    ASK_PICKUP, ASK_DROP, ASK_TIME_INITIAL, ASK_TIME,
    ASK_TIME_TOMORROW, ASK_TIME_TODAY, CONFIRM_TEMPLATE, 
    VAGUE_PLACE, BOOKED_REPLY, NO_AT_CONFIRM, CANCEL_REPLY
)


def test_group_a():
    """A. The real conversation, one state."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    # enaku oru cab book pannanum -> asks pickup
    result = handle(state, "enaku oru cab book pannanum")
    if result and result.reply == ASK_PICKUP:
        print("PASS A1: enaku oru cab book pannanum -> ASK_PICKUP")
        passed += 1
    else:
        print(f"FAIL A1: enaku oru cab book pannanum")
        print(f"  Input: enaku oru cab book pannanum")
        print(f"  Expected: {repr(ASK_PICKUP)}")
        print(f"  Actual: {repr(result.reply if result else None)}")
        print(f"  State: {ascii(state)}")
        failed += 1
    
    # naa chennai ponnum -> drop, asks pickup
    result = handle(state, "naa chennai ponnum")
    if result and "\u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8" in result.reply:
        print("PASS A2: naa chennai ponnum -> drop, asks pickup")
        passed += 1
    else:
        print(f"FAIL A2: naa chennai ponnum -> expected drop in reply")
        print(f"  Input: 'naa chennai ponnum'")
        print(f"  Expected: Chennai in reply")
        print(f"  Actual reply: {ascii(result.reply) if result else None}")
        print(f"  State: {ascii(state)}")
        failed += 1
    
    # chennai -> asks pickup again
    result = handle(state, "chennai")
    if result and result.reply == ASK_PICKUP:
        print("PASS A3: chennai -> ASK_PICKUP again")
        passed += 1
    else:
        print(f"FAIL A3: chennai -> expected ASK_PICKUP, got {result}")
        failed += 1
    
    # madurai -> pickup, asks time
    result = handle(state, "madurai")
    if result and "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8" in result.reply:
        print("PASS A4: madurai -> pickup, asks time")
        passed += 1
    else:
        print(f"FAIL A4: madurai -> expected pickup in reply, got {result}")
        failed += 1
    
    # naliki 7 30 ku -> tomorrow 7:30, asks am/pm
    result = handle(state, "naliki 7 30 ku")
    if result and ("7:30" in result.reply or "7" in result.reply) and ("\u0B95\u0BBE\u0BB2\u0BC8" in result.reply or "\u0BAE\u0BBE\u0BB2\u0BC8" in result.reply):
        print("PASS A5: naliki 7 30 ku -> tomorrow 7:30, asks am/pm")
        passed += 1
    else:
        print(f"FAIL A5: naliki 7 30 ku -> expected am/pm question, got {result}")
        failed += 1
    
    # kalai -> confirm
    result = handle(state, "kalai")
    if result and "?" in result.reply and "\u0BAA\u0BC1\u0B95\u0BCD" in result.reply:
        print("PASS A6: kalai -> confirm")
        passed += 1
    else:
        print(f"FAIL A6: kalai -> expected confirm, got {result}")
        failed += 1
    
    # aama -> booked, reset
    result = handle(state, "aama")
    if result and result.booked and result.reply == BOOKED_REPLY:
        print("PASS A7: aama -> booked, state reset")
        passed += 1
    else:
        print(f"FAIL A7: aama -> expected booked, got {result}")
        failed += 1
    
    return passed, failed


def test_group_b():
    """B. One sentence: full booking info."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    result = handle(state, "enaku madurai la irundhu trichy ku naliki 730 ku cab book pannu")
    if result and ("\u0B95\u0BBE\u0BB2\u0BC8" in result.reply or "\u0BAE\u0BBE\u0BB2\u0BC8" in result.reply):
        print("PASS B1: Full sentence -> asks am/pm")
        passed += 1
    else:
        print(f"FAIL B1: Full sentence -> expected am/pm, got {result}")
        failed += 1
    
    return passed, failed


def test_group_c():
    """C. Time without am/pm triggers am/pm question."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    result = handle(state, "naa madurai la irundhu trichy ku naliki poganum")
    if result and ("?" in result.reply):
        print("PASS C1: Time without am/pm -> asks am/pm")
        passed += 1
    else:
        print(f"FAIL C1: -> expected question, got {result}")
        failed += 1
    
    result = handle(state, "ezharai")
    if result and ("7:30" in result.reply or "7" in result.reply):
        print("PASS C2: ezharai -> 7:30")
        passed += 1
    else:
        print(f"FAIL C2: -> expected 7:30, got {result}")
        failed += 1
    
    result = handle(state, "malai")
    if result and "?" in result.reply and "\u0BAA\u0BC1\u0B95\u0BCD" in result.reply:
        print("PASS C3: malai -> confirm with pm")
        passed += 1
    else:
        print(f"FAIL C3: -> expected confirm, got {result}")
        failed += 1
    
    return passed, failed


def test_group_d():
    """D. Each starts a booking."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    test_cases = [
        ("kk nagar poganum", "drop"),
        ("naa trichy pognum", "drop"),
        ("thrichy la irundhu poganum", "pickup"),
        ("Madurai la iruken", "pickup"),
        ("teppakulam poganum", "drop"),
        ("airport ku poganum", "drop"),
        ("madurai railway station ku poganum", "drop"),
        ("from anna nagar to airport", "both"),
        ("location trichy", "bare"),
    ]
    
    for text, expected_type in test_cases:
        state = DialogueState()
        result = handle(state, f"cab book pannanum {text}")
        if result:
            print(f"PASS D ({expected_type}): {text} starts booking")
            passed += 1
        else:
            print(f"FAIL D ({expected_type}): {text} -> expected booking start, got None")
            failed += 1
    
    return passed, failed


def test_group_e():
    """E. Correction with explicit pattern."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    result = handle(state, "madurai la irundhu chennai ku cab venum")
    if result:
        print("PASS E1: Initial booking")
        passed += 1
    else:
        print(f"FAIL E1: -> expected result, got None")
        failed += 1
    
    result = handle(state, "ila trichy la irundhu madurai ku poganum")
    if result and "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF" in str(state.pickup):
        print("PASS E2: Explicit pattern corrects slots")
        passed += 1
    else:
        print(f"FAIL E2: ila trichy la irundhu madurai ku poganum -> expected Trichy as pickup")
        print(f"  Input: 'ila trichy la irundhu madurai ku poganum'")
        print(f"  Expected pickup: Trichy")
        print(f"  Actual pickup: {ascii(state.pickup)}")
        print(f"  Actual drop: {ascii(state.drop)}")
        print(f"  State: {ascii(state)}")
        failed += 1
    
    # E3: Override when awaiting=drop
    state2 = DialogueState()
    handle(state2, "kk nagar poganum")
    result = handle(state2, "naa trichy la irundhu madurai ku poganum")
    if result and state2.pickup == "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF" and state2.drop == "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8":
        print("PASS E3: Override after drop sets pickup and drop")
        passed += 1
    else:
        print(f"FAIL E3: naa trichy la irundhu madurai ku poganum -> expected pickup=Trichy, drop=Madurai")
        print(f"  Actual pickup: {ascii(state2.pickup)}")
        print(f"  Actual drop: {ascii(state2.drop)}")
        failed += 1
    
    # E4: Override when awaiting=confirm
    state3 = DialogueState()
    handle(state3, "madurai la irundhu chennai ku cab venum")
    handle(state3, "naliki 7 30 ku")
    handle(state3, "kalai")
    # Now in confirm state, override drop only
    original_pickup = state3.pickup
    original_hour = state3.hour
    result = handle(state3, "illa madurai ku poganum")
    if result and state3.drop == "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8":
        if state3.pickup == original_pickup and state3.hour == original_hour:
            print("PASS E4: Override in confirm state changes drop only, pickup and time unchanged")
            passed += 1
        else:
            print(f"FAIL E4: ill madurai ku poganum -> pickup/time changed when they shouldn't")
            print(f"  Pickup before: {ascii(original_pickup)}, after: {ascii(state3.pickup)}")
            print(f"  Hour before: {original_hour}, after: {state3.hour}")
            failed += 1
    else:
        print(f"FAIL E4: illa madurai ku poganum -> expected drop=Madurai")
        print(f"  Actual drop: {ascii(state3.drop)}")
        failed += 1
    
    return passed, failed


def test_group_f():
    """F. Various time and place scenarios."""
    passed = 0
    failed = 0
    
    # F1: today, 9pm
    state = DialogueState()
    result = handle(state, "inniki raathri 9 mani ku cab venum")
    if result and state.date == "today" and state.hour == 9 and state.ampm == "pm":
        print("PASS F1: inniki raathri 9 mani ku -> today, 9pm")
        passed += 1
    else:
        print(f"FAIL F1: inniki raathri 9 mani ku -> expected today 9pm")
        print(f"  Input: 'inniki raathri 9 mani ku cab venum'")
        print(f"  Expected: date='today', hour=9, ampm='pm'")
        print(f"  Actual: date={ascii(state.date)}, hour={ascii(state.hour)}, ampm={ascii(state.ampm)}")
        print(f"  Reply: {ascii(result.reply) if result else None}")
        print(f"  State: {ascii(state)}")
        failed += 1
    
    # F2: immediate
    state = DialogueState()
    result = handle(state, "ippo cab venum")
    if result and state.now:
        print("PASS F2: ippo cab venum -> immediate")
        passed += 1
    else:
        print(f"FAIL F2: -> expected now=True, got {state}")
        failed += 1
    
    # F3: vague place
    state = DialogueState()
    result = handle(state, "cab venum")
    if result and result.reply == ASK_PICKUP:
        print("PASS F3: cab venum -> asks pickup")
        passed += 1
    else:
        print(f"FAIL F3: -> got {result}")
        failed += 1
    
    result = handle(state, "kovil ku")
    if result and result.reply == VAGUE_PLACE:
        print("PASS F4: kovil ku -> vague place")
        passed += 1
    else:
        print(f"FAIL F4: -> expected vague place, got {result}")
        failed += 1
    
    return passed, failed


def test_group_g():
    """G. Cancel in the middle."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    result = handle(state, "cab venum")
    if result:
        print("PASS G1: Start booking")
        passed += 1
    else:
        failed += 1
    
    result = handle(state, "cancel")
    if result and result.reply == CANCEL_REPLY and state.awaiting is None:
        print("PASS G2: cancel -> reset")
        passed += 1
    else:
        print(f"FAIL G2: -> expected cancel, got {result}, state={state.awaiting}")
        failed += 1
    
    return passed, failed


def test_group_h():
    """H. Return None (not hijacked)."""
    passed = 0
    failed = 0
    
    test_cases = [
        "vanakam",
        "nandri",
        "nee epidi iruka",
        "madurai la enna famous",
        "2 * 3 evlo",
        "enna macha pannure",
        "en peru sarandeep",
        "enaku oru paatu sollu",
        "naa pesurathu puriyutha",
        "naa madurai la iruken atha pathi sollu",
        "train la poganum",
        "madurai",
        "sari",
        "aama",
    ]
    
    for text in test_cases:
        state = DialogueState()
        result = handle(state, text)
        if result is None:
            print(f"PASS H: {text} -> None")
            passed += 1
        else:
            print(f"FAIL H: {text} -> expected None, got {result}")
            failed += 1
    
    return passed, failed


def test_group_i():
    """I. Mid-booking question."""
    state = DialogueState()
    passed = 0
    failed = 0
    
    result = handle(state, "cab venum")
    if result:
        print("PASS I1: cab venum -> start")
        passed += 1
    else:
        failed += 1
    
    result = handle(state, "naa madurai la irundhu")
    if result:
        print("PASS I2: naa madurai la irundhu -> pickup set")
        passed += 1
    else:
        failed += 1
    
    result = handle(state, "time enna")
    if result is None and state.pickup:
        print("PASS I3: time enna -> None, state unchanged")
        passed += 1
    else:
        print(f"FAIL I3: -> expected None with state unchanged, got {result}, pickup={state.pickup}")
        failed += 1
    
    return passed, failed


def test_group_j():
    """J. Reply length and session store."""
    passed = 0
    failed = 0
    
    state = DialogueState()
    
    # Check that replies are at most 2 sentences
    test_messages = [
        "enaku oru cab book pannanum",
        "naa chennai ponnum",
        "madurai",
    ]
    
    for msg in test_messages:
        result = handle(state, msg)
        if result:
            sentence_count = result.reply.count("?") + result.reply.count("\u0964")
            if sentence_count <= 2:
                print(f"PASS J: {msg} reply has <= 2 sentences")
                passed += 1
            else:
                print(f"FAIL J: {msg} reply has > 2 sentences")
                failed += 1
        else:
            failed += 1
    
    return passed, failed


def test_group_k():
    """K. Confirm state: each yes word books and resets."""
    passed = 0
    failed = 0
    
    yes_words = [
        "aama", "ama", "aamam", "yes", "ok", "okay", "sari", "seri", "sariya",
        "correct", "confirm", "pannu", "pannidhu", "potturu", "pannunga",
        "panunga", "podu", "podunga", "book pannu", "book pannunga"
    ]
    
    for yes_word in yes_words:
        state = DialogueState()
        # Start booking
        result = handle(state, "enaku oru cab book pannanum")
        if not result or state.awaiting != "pickup":
            print(f"FAIL K: Could not start booking for word '{yes_word}'")
            failed += 1
            continue
        
        # Add pickup and drop with from/to pattern
        result = handle(state, "from madurai to chennai")
        if not result or state.pickup is None or state.drop is None:
            print(f"FAIL K: Could not set locations for '{yes_word}', pickup={state.pickup}, drop={state.drop}")
            failed += 1
            continue
        
        # Get to confirm
        while state.awaiting != "confirm" and state.awaiting is not None:
            if state.awaiting == "time":
                result = handle(state, "naliki 2 mani")
                if not result:
                    break
            elif state.awaiting == "ampm":
                result = handle(state, "kalai")
                if not result:
                    break
            else:
                break
        
        if state.awaiting != "confirm":
            print(f"FAIL K: Could not reach confirm state for word '{yes_word}', stuck at {state.awaiting}")
            failed += 1
            continue
        
        # Send yes word
        result = handle(state, yes_word)
        if result and result.booked and state.awaiting is None:
            print(f"PASS K: '{yes_word}' -> booked, state reset")
            passed += 1
        else:
            print(f"FAIL K: '{yes_word}' at confirm")
            print(f"  Expected: booked, state reset")
            print(f"  Actual: result={result}, state.awaiting={state.awaiting}")
            failed += 1
    
    return passed, failed


def test_group_l():
    """L. Confirm state: each no word gives change reply."""
    passed = 0
    failed = 0
    
    no_words = ["illa", "ila", "no", "venam", "vendam", "venda", "maathu", "change"]
    
    for no_word in no_words:
        state = DialogueState()
        # Start booking
        result = handle(state, "cab venum")
        if not result:
            failed += 1
            continue
        
        # Add places and time with from/to pattern
        result = handle(state, "from madurai to chennai")
        if not result or state.pickup is None or state.drop is None:
            print(f"FAIL L: Could not set locations for '{no_word}'")
            failed += 1
            continue
        
        # Get to confirm
        while state.awaiting != "confirm" and state.awaiting is not None:
            if state.awaiting == "time":
                result = handle(state, "naliki 2 mani")
                if not result:
                    break
            elif state.awaiting == "ampm":
                result = handle(state, "kalai")
                if not result:
                    break
            else:
                break
        
        if state.awaiting != "confirm":
            print(f"FAIL L: Could not reach confirm for '{no_word}'")
            failed += 1
            continue
        
        # Send no word
        result = handle(state, no_word)
        if result and result.reply == NO_AT_CONFIRM:
            print(f"PASS L: '{no_word}' -> NO_AT_CONFIRM reply")
            passed += 1
        else:
            print(f"FAIL L: '{no_word}' at confirm")
            print(f"  Expected: {repr(NO_AT_CONFIRM)}")
            print(f"  Actual: {repr(result.reply if result else None)}")
            failed += 1
    
    return passed, failed


def test_group_m():
    """M. Fresh state: forbidden words return None."""
    passed = 0
    failed = 0
    
    forbidden_words = ["pannu", "seri", "ok", "podu", "confirm"]
    
    for word in forbidden_words:
        state = DialogueState()
        result = handle(state, word)
        if result is None:
            print(f"PASS M: '{word}' with fresh state -> None")
            passed += 1
        else:
            print(f"FAIL M: '{word}' with fresh state")
            print(f"  Expected: None")
            print(f"  Actual: {repr(result)}")
            failed += 1
    
    return passed, failed


def test_group_n():
    """N. Confirm state: explicit pattern with yes word is correction."""
    passed = 0
    failed = 0
    
    state = DialogueState()
    # Start and reach confirm
    result = handle(state, "cab venum")
    result = handle(state, "from madurai to chennai")
    
    while state.awaiting != "confirm":
        if state.awaiting == "time":
            result = handle(state, "naliki 2 mani")
        elif state.awaiting == "ampm":
            result = handle(state, "kalai")
        else:
            break
    
    if state.awaiting != "confirm":
        print(f"FAIL N: Could not reach confirm state")
        return 0, 1
    
    # Send correction with yes-like word: "illa madurai to salem"
    # This should change locations and stay in confirm, not book
    original_pickup = state.pickup
    result = handle(state, "illa from salem to trichy")
    
    if result and state.awaiting == "confirm" and not result.booked:
        print(f"PASS N: 'illa from salem to trichy' at confirm -> correction, stays in confirm")
        passed += 1
    else:
        print(f"FAIL N: 'illa from salem to trichy' at confirm")
        print(f"  Expected: correction, stays in confirm, no booking")
        print(f"  Actual: state.awaiting={state.awaiting}, booked={result.booked if result else None}")
        failed += 1
    
    return passed, failed


def test_group_o():
    """O. Confirm state: question returns None, state unchanged."""
    passed = 0
    failed = 0
    
    state = DialogueState()
    # Start and reach confirm
    result = handle(state, "cab venum")
    result = handle(state, "from madurai to chennai")
    
    while state.awaiting != "confirm":
        if state.awaiting == "time":
            result = handle(state, "naliki 2 mani")
        elif state.awaiting == "ampm":
            result = handle(state, "kalai")
        else:
            break
    
    if state.awaiting != "confirm":
        print(f"FAIL O: Could not reach confirm state")
        return 0, 1
    
    original_state = (state.pickup, state.drop, state.hour, state.awaiting)
    
    # Send question: "enna time"
    result = handle(state, "enna time")
    
    if result is None and state.awaiting == "confirm" and (state.pickup, state.drop, state.hour, state.awaiting) == original_state:
        print(f"PASS O: 'enna time' at confirm -> None, state unchanged")
        passed += 1
    else:
        print(f"FAIL O: 'enna time' at confirm")
        print(f"  Expected: None, state unchanged")
        print(f"  Actual: result={result}, state.awaiting={state.awaiting}")
        failed += 1
    
    return passed, failed


def test_group_p():
    """P. No doubled endings in replies (using established patterns)."""
    from dialogue_parse import loc, dat
    
    passed = 0
    failed = 0
    double_ending_loc = "\u0BBF\u0BB2\u0BCD\u0BBF\u0BB2\u0BCD"  # Doubled locative
    double_ending_dat = "\u0B95\u0BCD\u0B95\u0BC1\u0B95\u0BCD\u0B95\u0BC1"  # Doubled dative
    
    # Test with actual booking patterns to reach confirm
    state = DialogueState()
    
    # Start booking
    r1 = handle(state, "enaku oru cab book pannanum")
    r2 = handle(state, "naa madurai irundhu chennai ponnum")
    r3 = handle(state, "naliki 2 mani")
    r4 = handle(state, "kalai")
    
    # Now in confirm - r4 should have the confirm message
    if r4:
        confirm_text = r4.reply
        if double_ending_loc in confirm_text:
            print(f"FAIL P: Doubled locative ending in confirm message")
            print(f"  Reply: {ascii(confirm_text)}")
            failed += 1
        elif double_ending_dat in confirm_text:
            print(f"FAIL P: Doubled dative ending in confirm message")
            print(f"  Reply: {ascii(confirm_text)}")
            failed += 1
        else:
            print(f"PASS P1: No doubled endings in confirm message")
            passed += 1
    else:
        print(f"FAIL P: Could not reach confirm state")
        failed += 1
    
    # Check ack message - r2 should have it
    if r2:
        ack_text = r2.reply
        if double_ending_loc in ack_text:
            print(f"FAIL P: Doubled locative ending in ack message")
            failed += 1
        elif double_ending_dat in ack_text:
            print(f"FAIL P: Doubled dative ending in ack message")
            failed += 1
        else:
            print(f"PASS P2: No doubled endings in ack message")
            passed += 1
    else:
        print(f"FAIL P: Could not get ack message")
        failed += 1
    
    return passed, failed


def test_group_q():
    r"""Q. Exact expected text tests with \u escapes."""
    from dialogue_parse import loc, dat
    
    passed = 0
    failed = 0
    
    # Test 4a: Multi-step conversation with exact expected replies
    messages = [
        "cab venum",
        "madurai la irundhu chennai ku",
        "naliki 8 mani",
        "malai"
    ]
    
    expected_replies = {
        1: "\u0B9A\u0BB0\u0BBF, \u0BAE\u0BA4\u0BC1\u0BB0\u0BC8\u0BAF\u0BBF\u0BB2\u0BCD \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1. ",
        3: "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8\u0BAF\u0BBF\u0BB2\u0BCD \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1 \u0BA8\u0BBE\u0BB3\u0BC8\u0B95\u0BCD\u0B95\u0BC1 \u0B87\u0BB0\u0BB5\u0BC1 8 \u0BAE\u0BA3\u0BBF\u0B95\u0BCD\u0B95\u0BC1 \u0BAA\u0BC1\u0B95\u0BCD \u0BAA\u0BA3\u0BCD\u0BA3\u0B9F\u0BCD\u0B9F\u0BC1\u0BAE\u0BBE?"
    }
    
    state = DialogueState()
    for i, msg in enumerate(messages):
        result = handle(state, msg)
        if result is None:
            print(f"FAIL Q4a: step {i}: '{msg}' returned None")
            failed += 1
            continue
        
        if i == 1:
            # Check reply starts with ack
            if not result.reply.startswith(expected_replies[1]):
                print(f"FAIL Q4a step {i}: Expected start:")
                print(f"  {repr(expected_replies[1])}")
                print(f"  Actual start:")
                print(f"  {repr(result.reply[:len(expected_replies[1])])}")
                print(f"  Full reply: {ascii(result.reply)}")
                failed += 1
            else:
                print(f"PASS Q4a step {i}: Correct ack + time question")
                passed += 1
        elif i == 3:
            # Check exact confirm message
            if result.reply == expected_replies[3]:
                print(f"PASS Q4a step {i}: Exact confirm message")
                passed += 1
            else:
                print(f"FAIL Q4a step {i}: Confirm message mismatch")
                print(f"  Expected: {repr(expected_replies[3])}")
                print(f"  Actual: {repr(result.reply)}")
                print(f"  Expected ascii: {ascii(expected_replies[3])}")
                print(f"  Actual ascii: {ascii(result.reply)}")
                failed += 1
    
    # Test 4b: Single message with both pickup and drop
    state2 = DialogueState()
    result = handle(state2, "madurai la irundhu chennai ku cab venum")
    
    expected_ack_start = "\u0B9A\u0BB0\u0BBF, \u0BAE\u0BA4\u0BC1\u0BB0\u0BC8\u0BAF\u0BBF\u0BB2\u0BCD \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1. "
    
    if result and result.reply.startswith(expected_ack_start):
        print(f"PASS Q4b: Single message with both pickup/drop has ack")
        passed += 1
    else:
        print(f"FAIL Q4b: Single message should start with ack")
        print(f"  Expected start: {repr(expected_ack_start)}")
        print(f"  Actual: {repr(result.reply[:len(expected_ack_start)] if result else 'None')}")
        failed += 1
    
    # Test 4c: All 15 place names as pickup
    with open("PLACE_NAMES.txt", "r", encoding="utf-8") as f:
        place_lines = f.read().strip().split('\n')
    
    place_names = [line.strip() for line in place_lines if line.strip()][:15]
    double_ending_loc = "\u0BBF\u0BB2\u0BCD\u0BBF\u0BB2\u0BCD"
    
    for place_name in place_names:
        # Build the expected messages using loc() and dat()
        ack_template = "\u0B9A\u0BB0\u0BBF, {pickup} \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1. "
        ack_msg = ack_template.format(pickup=loc(place_name))
        
        confirm_template = "{pickup} \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1 \u0B87\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1 \u0B87\u0BB0\u0BB5\u0BC1 2 \u0BAE\u0BA3\u0BBF\u0B95\u0BCD\u0B95\u0BC1 \u0BAA\u0BC1\u0B95\u0BCD \u0BAA\u0BA3\u0BCD\u0BA3\u0B9F\u0BCD\u0B9F\u0BC1\u0BAE\u0BBE?"
        confirm_msg = confirm_template.format(pickup=loc(place_name))
        
        # Check for doubled ending
        if double_ending_loc in ack_msg or double_ending_loc in confirm_msg:
            print(f"FAIL Q4c: {place_name[:20]} has doubled ending")
            print(f"  Ack: {ascii(ack_msg)}")
            print(f"  Confirm: {ascii(confirm_msg)}")
            failed += 1
        else:
            print(f"PASS Q4c: {place_name[:20]} has correct endings")
            passed += 1
    
    # Test 4d: am/pm question format
    state4 = DialogueState()
    state4.awaiting = "ampm"
    state4.hour = 8
    state4.minute = 0
    
    result = handle(state4, "blah")
    
    expected_ampm = "8 \u0BAE\u0BA3\u0BBF \u0B95\u0BBE\u0BB2\u0BC8\u0BAF\u0BBE, \u0BAE\u0BBE\u0BB2\u0BC8\u0BAF\u0BBE?"
    
    if result and expected_ampm in result.reply:
        print(f"PASS Q4d: am/pm question has correct format with space")
        passed += 1
    else:
        print(f"FAIL Q4d: am/pm question format wrong")
        print(f"  Expected to contain: {repr(expected_ampm)}")
        print(f"  Actual: {repr(result.reply if result else 'None')}")
        failed += 1
    
    return passed, failed


def test_group_r():
    r"""R. Print exact acknowledgement and confirm sentences for 5 pickups."""
    from dialogue_parse import loc, dat
    
    pickups = [
        ("\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8", "Madurai"),
        ("\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", "Trichy"),
        ("\u0B85\u0BA3\u0BCD\u0BA3\u0BBE \u0BA8\u0B95\u0BB0\u0BCD", "Anna Nagar"),
        ("\u0BA4\u0BC6\u0BAA\u0BCD\u0BAA\u0B95\u0BCD\u0B95\u0BC1\u0BB3\u0BAE\u0BCD", "Teppakulam"),
        ("\u0BB5\u0BBF\u0BAE\u0BA8 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD", "Airport"),
    ]
    
    for place_tamil, label in pickups:
        # Ack message
        ack_template = "\u0B9A\u0BB0\u0BBF, {pickup} \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1. "
        ack_msg = ack_template.format(pickup=loc(place_tamil))
        
        # Confirm message (fixed time for consistency)
        confirm_template = "{pickup} \u0B87\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1 \u0B87\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1 \u0B87\u0BB0\u0BB5\u0BC1 2 \u0BAE\u0BA3\u0BBF\u0B95\u0BCD\u0B95\u0BC1 \u0BAA\u0BC1\u0B95\u0BCD \u0BAA\u0BA3\u0BCD\u0BA3\u0B9F\u0BCD\u0B9F\u0BC1\u0BAE\u0BBE?"
        confirm_msg = confirm_template.format(pickup=loc(place_tamil))
        
        print(f"{label}:")
        print(f"  Ack: {ascii(ack_msg)}")
        print(f"  Confirm: {ascii(confirm_msg)}")
    
    return 0, 0  # No failures, just printing


def main():
    print("=" * 80)
    print("Testing dialogue state machine")
    print("=" * 80)
    
    total_passed = 0
    total_failed = 0
    
    groups = [
        ("A", test_group_a),
        ("B", test_group_b),
        ("C", test_group_c),
        ("D", test_group_d),
        ("E", test_group_e),
        ("F", test_group_f),
        ("G", test_group_g),
        ("H", test_group_h),
        ("I", test_group_i),
        ("J", test_group_j),
        ("K", test_group_k),
        ("L", test_group_l),
        ("M", test_group_m),
        ("N", test_group_n),
        ("O", test_group_o),
        ("P", test_group_p),
        ("Q", test_group_q),
        ("R", test_group_r),
    ]
    
    for group_name, test_func in groups:
        print(f"\nGroup {group_name}:")
        try:
            p, f = test_func()
            total_passed += p
            total_failed += f
        except Exception as e:
            print(f"ERROR in group {group_name}: {e}")
            total_failed += 1
    
    print("\n" + "=" * 80)
    print(f"TOTAL: Passed {total_passed}, Failed {total_failed}")
    print("=" * 80)
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
