#!/usr/bin/env python3
r"""Dialogue state machine for Tamil cab booking.
All strings are in \uXXXX escapes to avoid encoding issues.
"""

import sys
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Encoding check: ensure no non-ASCII characters in source
with open(__file__, 'rb') as f:
    content = f.read()
    if any(b > 127 for b in content):
        print("ERROR: dialogue.py contains non-ASCII characters")
        sys.exit(1)

from dialogue_parse import parse_places, parse_time, is_question, dat, loc
from replies import (
    ASK_PICKUP, ASK_DROP, ASK_TIME_INITIAL, ASK_TIME,
    ASK_TIME_TOMORROW, ASK_TIME_TODAY, ASK_AMPM_TEMPLATE,
    ACK_DROP_TEMPLATE, ACK_PICKUP_TEMPLATE, ACK_BOTH_TEMPLATE,
    CONFIRM_TEMPLATE, VAGUE_PLACE, BOOKED_REPLY, NO_AT_CONFIRM, CANCEL_REPLY
)


@dataclass
class DialogueState:
    """Booking state for one session."""
    pickup: Optional[str] = None
    drop: Optional[str] = None
    date: Optional[str] = None
    now: bool = False
    hour: Optional[int] = None
    minute: Optional[int] = None
    ampm: Optional[str] = None
    awaiting: Optional[str] = None
    last_slot: Optional[str] = None


@dataclass
class Result:
    """Result of handling a message."""
    reply: str
    intent: str = "booking"
    booked: Optional[Dict[str, Any]] = None


def _dat(place: str) -> str:
    """Apply dative ending to place name."""
    return dat(place)


def _loc(place: str) -> str:
    """Apply locative ending to place name."""
    loc_result = loc(place)
    return loc_result if loc_result else place


def _format_time(hour: int, minute: int, ampm: Optional[str]) -> str:
    """Format time for Tamil text."""
    if minute == 0:
        time_str = str(hour)
    else:
        time_str = f"{hour}:{minute:02d}"
    return time_str


def _get_period_name(hour: int, ampm: Optional[str]) -> str:
    """Get Tamil period name (morning/noon/evening/night)."""
    if ampm == "am":
        return "\u0B95\u0BBE\u0BB2\u0BC8"
    elif ampm == "pm":
        if hour >= 7:
            return "\u0B87\u0BB0\u0BB5\u0BC1"
        elif hour >= 4:
            return "\u0BAE\u0BBE\u0BB2\u0BC8"
        else:
            return "\u0BAE\u0BA4\u0BBF\u0BAF\u0BAE\u0BCD"
    return ""


def _build_confirm_message(state: DialogueState) -> str:
    """Build the confirmation message."""
    pickup_loc = _loc(state.pickup)
    drop_dat = _dat(state.drop)
    
    if state.now:
        when = "\u0B87\u0BAA\u0BCD\u0BAA\u0BCB\u0BB5\u0BC7"
    else:
        when_parts = []
        if state.date == "tomorrow":
            when_parts.append("\u0BA8\u0BBE\u0BB3\u0BC8\u0B95\u0BCD\u0B95\u0BC1")
        else:
            when_parts.append("\u0B87\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1")
        
        if state.hour is not None:
            period = _get_period_name(state.hour, state.ampm)
            time_str = _format_time(state.hour, state.minute or 0, state.ampm)
            when_parts.append(period)
            when_parts.append(time_str)
            when_parts.append("\u0BAE\u0BA3\u0BBF\u0B95\u0BCD\u0B95\u0BC1")
        
        when = " ".join(when_parts)
    
    return CONFIRM_TEMPLATE.format(pickup=pickup_loc, drop=drop_dat, when=when)


def _is_cab_word(text: str) -> bool:
    """Check if text contains cab/taxi/car keywords."""
    return any(kw in text.lower() for kw in ["cab", "taxi", "car"])


def _is_cancellation(text: str) -> bool:
    """Check if text is a cancellation request."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in ["cancel", "ratthu", "\u0BB0\u0BA4\u0BCD\u0BA4\u0BC1"])


def _normalize_for_match(text: str) -> list:
    """Normalize text and return list of whole tokens for matching."""
    from dialogue_parse import normalize
    normalized = normalize(text)
    return normalized.split()


def _is_affirmative(text: str) -> bool:
    """Check if text is an affirmative response (at confirm state)."""
    tokens = _normalize_for_match(text)
    affirmative_words = [
        "aama", "ama", "amam", "yes", "ok", "okay", "sari", "seri", "sariya",
        "corect", "confirm", "panu", "panidhu", "poturu", "pannunga", 
        "panunga", "podu", "podunga", "book",
        "\u0B9A\u0BB0\u0BBF", "\u0B86\u0BAE\u0BBE"
    ]
    for token in tokens:
        if token in affirmative_words:
            return True
    # Check for "book pannunga" or "book pannu" patterns
    text_lower = text.lower()
    if "book" in text_lower and any(p in text_lower for p in ["pannu", "pannunga", "panu"]):
        return True
    return False


def _is_negative(text: str) -> bool:
    """Check if text is a negative response."""
    tokens = _normalize_for_match(text)
    negative_words = ["no", "ila", "venam", "vendam", "venda", "mathu", "change"]
    for token in tokens:
        if token in negative_words:
            return True
    return False


def _is_greeting_or_thanks(text: str) -> bool:
    """Check if text is a greeting or thanks."""
    text_lower = text.lower()
    greeting_words = ["vanakam", "vanakkam", "nandri", "thank", "thanks"]
    return any(kw in text_lower for kw in greeting_words)


def _starts_booking_forbidden(text: str) -> bool:
    """Check if text contains only forbidden words that cannot start a booking."""
    tokens = _normalize_for_match(text)
    forbidden_starters = ["pannu", "seri", "ok", "confirm", "podu"]
    
    # If ALL tokens are in forbidden list (or are fillers), it cannot start a booking
    for token in tokens:
        if token not in forbidden_starters and token not in ["naa", "nan", "enaku", "nee", "oru"]:
            # Has a non-forbidden token, so it can proceed
            return False
    # All tokens are forbidden or fillers
    return True


def _is_consent_response(text: str) -> bool:
    """Check if text is consent (sari/aama) outside booking and confirm."""
    tokens = _normalize_for_match(text)
    return any(t in ["sari", "aama", "ama"] for t in tokens)


def _has_correction_pattern(places_result: Dict, time_result: Dict) -> bool:
    """Check if text has explicit pickup/drop or time pattern (for confirm state)."""
    has_place = places_result.get("pickup") or places_result.get("drop")
    has_time = time_result.get("now") or time_result.get("hour") or time_result.get("date")
    return has_place or has_time


def _has_slot_info(places_result: Dict, time_result: Dict) -> bool:
    """Check if there is pickup/drop or time information."""
    has_place = places_result["pickup"] or places_result["drop"] or places_result["bare"]
    has_time = time_result.get("now") or time_result.get("hour") or time_result.get("date")
    return has_place or has_time


def _is_forbidden_transport(places_result: Dict) -> bool:
    """Check if place mentions train/bus/flight/auto."""
    place_str = places_result.get("bare") or places_result.get("pickup") or places_result.get("drop") or ""
    place_lower = str(place_str).lower()
    return any(kw in place_lower for kw in ["train", "bus", "flight", "auto"])


def handle(state: DialogueState, text: str) -> Optional[Result]:
    """Process user message and update state. Returns Result or None (send to LLM)."""
    
    if not isinstance(text, str) or not text.strip():
        return None
    
    text = text.strip()
    
    if _is_cancellation(text):
        state.pickup = None
        state.drop = None
        state.date = None
        state.now = False
        state.hour = None
        state.minute = None
        state.ampm = None
        state.awaiting = None
        state.last_slot = None
        return Result(reply=CANCEL_REPLY, intent="booking")
    
    places_result = parse_places(text)
    time_result = parse_time(text)
    is_q = is_question(text)
    has_cab_word = _is_cab_word(text)
    
    # If question without cab word, go to LLM and leave state unchanged
    if is_q and not has_cab_word:
        return None
    
    if not state.awaiting:
        # Check if this starts a booking
        
        if _is_greeting_or_thanks(text):
            return None
        
        if _is_consent_response(text) and not state.awaiting:
            return None
        
        # Check if text is only forbidden words (cannot start a booking)
        if _starts_booking_forbidden(text):
            return None
        
        has_explicit = places_result["pickup"] or places_result["drop"]
        
        if places_result.get("bare") and not (has_cab_word or has_explicit):
            return None
        
        if _is_forbidden_transport(places_result):
            return None
        
        if not (has_cab_word or has_explicit):
            return None
        
        if places_result["vague"] and not has_cab_word:
            return None
        
        state.awaiting = "pickup"
        state.pickup = places_result["pickup"]
        state.drop = places_result["drop"]
        
        # Handle immediate booking (now=True)
        if time_result.get("now"):
            state.now = True
        
        # Set time fields if provided
        if time_result.get("hour") is not None:
            state.hour = time_result["hour"]
            state.minute = time_result.get("minute", 0)
            state.ampm = time_result.get("ampm")
        if time_result.get("date"):
            state.date = time_result["date"]
        
        if state.pickup and state.drop:
            state.awaiting = "time"
            if time_result.get("now"):
                state.now = True
                state.awaiting = "ampm"
                if state.hour is None:
                    return Result(reply=ASK_AMPM_TEMPLATE.format(time=_format_time(12, 0, None)), intent="booking")
                else:
                    return Result(reply=_build_confirm_message(state), intent="booking")
            elif time_result.get("hour") is not None:
                state.hour = time_result["hour"]
                state.minute = time_result.get("minute", 0)
                state.ampm = time_result.get("ampm")
                state.date = time_result.get("date") or "today"
                if state.ampm is None:
                    state.awaiting = "ampm"
                    return Result(reply=ASK_AMPM_TEMPLATE.format(time=_format_time(state.hour, state.minute, None)), intent="booking")
                else:
                    state.awaiting = "confirm"
                    return Result(reply=_build_confirm_message(state), intent="booking")
            else:
                if time_result.get("date"):
                    state.date = time_result["date"]
                    if state.date == "tomorrow":
                        ack = ACK_BOTH_TEMPLATE.format(pickup=_loc(state.pickup), drop=_dat(state.drop))
                        return Result(reply=ack + ASK_TIME_TOMORROW, intent="booking")
                    else:
                        ack = ACK_BOTH_TEMPLATE.format(pickup=_loc(state.pickup), drop=_dat(state.drop))
                        return Result(reply=ack + ASK_TIME_TODAY, intent="booking")
                ack = ACK_BOTH_TEMPLATE.format(pickup=_loc(state.pickup), drop=_dat(state.drop))
                return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
        elif state.pickup and not state.drop:
            return Result(reply=ASK_DROP, intent="booking")
        elif state.drop and not state.pickup:
            # Have drop but not pickup - acknowledge drop and ask for pickup
            ack = ACK_DROP_TEMPLATE.format(drop=_dat(state.drop))
            return Result(reply=ack + ASK_PICKUP, intent="booking")
        else:
            return Result(reply=ASK_PICKUP, intent="booking")
    
    if state.awaiting == "pickup":
        # Check for explicit pattern with both pickup and drop
        if places_result["pickup"] and places_result["drop"]:
            state.pickup = places_result["pickup"]
            state.drop = places_result["drop"]
            state.awaiting = "time"
            ack = ACK_BOTH_TEMPLATE.format(pickup=_loc(state.pickup), drop=_dat(state.drop))
            return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
        elif places_result["bare"]:
            if places_result["bare"] == state.drop:
                return Result(reply=ASK_PICKUP, intent="booking")
            state.pickup = places_result["bare"]
            state.last_slot = "pickup"
            ack = ACK_PICKUP_TEMPLATE.format(pickup=_loc(state.pickup))
            if state.drop:
                # Drop already set, move to time
                state.awaiting = "time"
                return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
            else:
                return Result(reply=ack + ASK_DROP, intent="booking")
        elif places_result["pickup"]:
            # Explicit pickup pattern fills pickup slot
            state.pickup = places_result["pickup"]
            state.last_slot = "pickup"
            ack = ACK_PICKUP_TEMPLATE.format(pickup=_loc(state.pickup))
            if state.drop:
                # Drop already set, move to time
                state.awaiting = "time"
                return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
            else:
                return Result(reply=ack + ASK_DROP, intent="booking")
        elif places_result["drop"]:
            state.drop = places_result["drop"]
            state.last_slot = "drop"
            if state.pickup:
                ack = ACK_BOTH_TEMPLATE.format(pickup=_loc(state.pickup), drop=_dat(state.drop))
                state.awaiting = "time"
                return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
            else:
                ack = ACK_DROP_TEMPLATE.format(drop=_dat(state.drop))
                # Still awaiting pickup
                return Result(reply=ack + ASK_PICKUP, intent="booking")
        elif places_result["vague"]:
            return Result(reply=VAGUE_PLACE, intent="booking")
        else:
            return Result(reply=ASK_PICKUP, intent="booking")
    
    if state.awaiting == "drop":
        # Check for explicit pattern with both pickup and drop
        if places_result["pickup"] and places_result["drop"]:
            state.pickup = places_result["pickup"]
            state.drop = places_result["drop"]
            state.awaiting = "time"
            ack = ACK_BOTH_TEMPLATE.format(pickup=_loc(state.pickup), drop=_dat(state.drop))
            return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
        elif places_result["bare"]:
            if places_result["bare"] == state.pickup:
                return Result(reply=ASK_DROP, intent="booking")
            state.drop = places_result["bare"]
            state.last_slot = "drop"
            state.awaiting = "time"
            ack = ACK_DROP_TEMPLATE.format(drop=_dat(state.drop))
            return Result(reply=ack + ASK_TIME_INITIAL, intent="booking")
        elif places_result["pickup"]:
            state.pickup = places_result["pickup"]
            state.last_slot = "pickup"
            ack = ACK_PICKUP_TEMPLATE.format(pickup=_loc(state.pickup))
            return Result(reply=ack + ASK_DROP, intent="booking")
        elif places_result["vague"]:
            return Result(reply=VAGUE_PLACE, intent="booking")
        else:
            return Result(reply=ASK_DROP, intent="booking")
    
    if state.awaiting == "time":
        # Check for explicit place pattern that overrides current booking
        if places_result.get("pickup") or places_result.get("drop"):
            # Explicit pattern found - overwrite slots
            if places_result.get("pickup"):
                state.pickup = places_result["pickup"]
            if places_result.get("drop"):
                state.drop = places_result["drop"]
            # After overwrite, stay in time-awaiting or ask for missing slots
            if state.pickup and state.drop:
                state.awaiting = "time"
                return Result(reply=ASK_TIME_INITIAL, intent="booking")
            elif state.pickup and not state.drop:
                state.awaiting = "drop"
                return Result(reply=ASK_DROP, intent="booking")
            elif state.drop and not state.pickup:
                state.awaiting = "pickup"
                return Result(reply=ASK_PICKUP, intent="booking")
        
        if time_result.get("now"):
            state.now = True
            state.awaiting = "ampm"
            return Result(reply=ASK_AMPM_TEMPLATE.format(time=_format_time(12, 0, None)), intent="booking")
        elif time_result.get("hour") is not None:
            state.hour = time_result["hour"]
            state.minute = time_result.get("minute", 0)
            state.ampm = time_result.get("ampm")
            state.date = time_result.get("date") or "today"
            if state.ampm is None:
                state.awaiting = "ampm"
                return Result(reply=ASK_AMPM_TEMPLATE.format(time=_format_time(state.hour, state.minute, None)), intent="booking")
            else:
                state.awaiting = "confirm"
                return Result(reply=_build_confirm_message(state), intent="booking")
        elif time_result.get("date"):
            state.date = time_result["date"]
            if state.date == "tomorrow":
                return Result(reply=ASK_TIME_TOMORROW, intent="booking")
            else:
                return Result(reply=ASK_TIME_TODAY, intent="booking")
        else:
            return Result(reply=ASK_TIME_INITIAL, intent="booking")
    
    if state.awaiting == "ampm":
        # Check for explicit place pattern that overrides current booking
        if places_result.get("pickup") or places_result.get("drop"):
            # Explicit pattern found - overwrite slots
            if places_result.get("pickup"):
                state.pickup = places_result["pickup"]
            if places_result.get("drop"):
                state.drop = places_result["drop"]
            # After overwrite, stay in ampm-awaiting or ask for missing slots
            if state.pickup and state.drop:
                state.awaiting = "ampm"
                return Result(reply=ASK_AMPM_TEMPLATE.format(time=_format_time(state.hour or 12, state.minute or 0, None)), intent="booking")
            elif state.pickup and not state.drop:
                state.awaiting = "drop"
                return Result(reply=ASK_DROP, intent="booking")
            elif state.drop and not state.pickup:
                state.awaiting = "pickup"
                return Result(reply=ASK_PICKUP, intent="booking")
        
        if time_result.get("ampm"):
            state.ampm = time_result["ampm"]
            state.awaiting = "confirm"
            return Result(reply=_build_confirm_message(state), intent="booking")
        else:
            return Result(
                reply=ASK_AMPM_TEMPLATE.format(time=_format_time(state.hour, state.minute or 0, None)),
                intent="booking"
            )
    
    if state.awaiting == "confirm":
        # Check for explicit place pattern that overrides current booking
        if places_result.get("pickup") or places_result.get("drop"):
            # Explicit pattern found - overwrite slots
            if places_result.get("pickup"):
                state.pickup = places_result["pickup"]
            if places_result.get("drop"):
                state.drop = places_result["drop"]
            # After overwrite, stay in confirm-awaiting
            state.awaiting = "confirm"
            return Result(reply=_build_confirm_message(state), intent="booking")
        
        # Check for time correction pattern (even if yes word is present, it's a correction not a booking)
        if _has_correction_pattern(places_result, time_result):
            # This is a correction, not a yes
            if places_result.get("pickup"):
                state.pickup = places_result["pickup"]
            if places_result.get("drop"):
                state.drop = places_result["drop"]
            if time_result.get("now"):
                state.now = True
                state.hour = None
                state.minute = None
                state.ampm = None
            elif time_result.get("hour") is not None:
                state.hour = time_result["hour"]
                state.minute = time_result.get("minute", 0)
                state.ampm = time_result.get("ampm")
                state.date = time_result.get("date") or state.date
            elif time_result.get("date"):
                state.date = time_result["date"]
            state.awaiting = "confirm"
            return Result(reply=_build_confirm_message(state), intent="booking")
        
        if _is_affirmative(text):
            booked_dict = {
                "pickup": state.pickup,
                "drop": state.drop,
                "when": {
                    "now": state.now,
                    "date": state.date,
                    "hour": state.hour,
                    "minute": state.minute,
                    "ampm": state.ampm
                }
            }
            state.pickup = None
            state.drop = None
            state.date = None
            state.now = False
            state.hour = None
            state.minute = None
            state.ampm = None
            state.awaiting = None
            state.last_slot = None
            return Result(reply=BOOKED_REPLY, intent="booking", booked=booked_dict)
        elif _is_negative(text):
            state.awaiting = "confirm"
            return Result(reply=NO_AT_CONFIRM, intent="booking")
        elif _is_cancellation(text):
            state.pickup = None
            state.drop = None
            state.date = None
            state.now = False
            state.hour = None
            state.minute = None
            state.ampm = None
            state.awaiting = None
            state.last_slot = None
            return Result(reply=CANCEL_REPLY, intent="booking")
        else:
            # Neither yes, no, nor correction -> return None, keep state
            return None
    
    return None


class SessionStore:
    """Store dialogue states with TTL."""
    
    def __init__(self, ttl_seconds: int = 1800):
        self.ttl = ttl_seconds
        self.sessions: Dict[str, tuple[DialogueState, float]] = {}
    
    def get(self, session_id: str) -> DialogueState:
        """Get or create a session state."""
        now = time.time()
        
        expired = [sid for sid, (_, ts) in self.sessions.items() if now - ts > self.ttl]
        for sid in expired:
            del self.sessions[sid]
        
        if session_id in self.sessions:
            state, _ = self.sessions[session_id]
            self.sessions[session_id] = (state, now)
            return state
        else:
            state = DialogueState()
            self.sessions[session_id] = (state, now)
            return state
