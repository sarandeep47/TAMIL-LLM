#!/usr/bin/env python3
r"""Pure parsing functions for Tamil cab booking dialogue."""

import re
import unicodedata
from typing import Dict, Any


def normalize(text):
    """Normalize text: NFC, lowercase, strip, collapse doubled Latin letters."""
    if not isinstance(text, str):
        return ""
    
    text = unicodedata.normalize("NFC", text)
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u0B80-\u0BFF']", " ", text)
    text = re.sub(r"([a-z])\1+", r"\1", text)
    
    tokens = text.split()
    deduped = []
    for tok in tokens:
        if not deduped or deduped[-1] != tok:
            deduped.append(tok)
    
    text = " ".join(deduped).strip()
    return text


PLACES = {
    "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8": ["madurai", "madhurai"],
    "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF": ["trichy", "thrichy", "tiruchi", "tiruchirappalli"],
    "\u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8": ["chennai", "madras", "madra"],
    "\u0B95\u0BCB\u0BAF\u0BAE\u0BCD\u0BAA\u0BC1\u0BA4\u0BCD\u0BA4\u0BC2\u0BB0\u0BCD": ["coimbatore", "kovai"],
    "\u0B9A\u0BC7\u0BB2\u0BAE\u0BCD": ["salem"],
    "\u0B85\u0BA3\u0BCD\u0BA3\u0BBE \u0BA8\u0B95\u0BB0\u0BCD": ["anna nagar"],
    "\u0B95\u0BC7.\u0B95\u0BC7. \u0BA8\u0B95\u0BB0\u0BCD": ["kk nagar"],
    "\u0B9F\u0BBF \u0BA8\u0B95\u0BB0\u0BCD": ["t nagar"],
    "\u0BA4\u0BC6\u0BAA\u0BCD\u0BAA\u0B95\u0BCD\u0B95\u0BC1\u0BB3\u0BAE\u0BCD": ["teppakulam"],
    "\u0BAE\u0BC0\u0BA9\u0BBE\u0B9F\u0BCD\u0B9A\u0BBF \u0B85\u0BAE\u0BCD\u0BAE\u0BA9\u0BCD \u0B95\u0BCB\u0BB5\u0BBF\u0BB2\u0BCD": ["meenakshi", "meenakshi amman", "meenakshi temple"],
    "\u0BAE\u0BC6\u0BB0\u0BBF\u0BA9\u0BBE \u0B95\u0B9F\u0BB1\u0BCD\u0B95\u0BB0\u0BC8": ["marina", "marina beach"],
    "\u0BB5\u0BBF\u0BAE\u0BBE\u0BA9 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD": ["airport"],
    "\u0BB0\u0BAF\u0BBF\u0BB2\u0BCD \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD": ["railway station"],
    "\u0BAA\u0BC7\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD": ["bus stand"],
    "\u0BAA\u0BC6\u0BB0\u0BBF\u0BAF\u0BBE\u0BB0\u0BCD \u0BAA\u0BC7\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD": ["periyar bus", "periyar perundhu"],
}

PLACE_MAP = {}
for tamil_name, spellings in PLACES.items():
    for spelling in spellings:
        norm_spelling = normalize(spelling)
        PLACE_MAP[norm_spelling] = tamil_name
        if " " in spelling:
            PLACE_MAP[spelling.lower()] = tamil_name

FILLER_WORDS = {normalize(w) for w in ["naa", "nan", "enaku", "nee", "oru"]}
VAGUE_WORDS = {"kovil", "temple", "station"}

QUESTION_WORDS_BASE = ["enna", "epdi", "epidi", "evlo", "epo", "yaru", "pathi", "about", "sollu", "atha", "what", "how", "when", "why"]
QUESTION_WORDS = {normalize(w) for w in QUESTION_WORDS_BASE}


def parse_places(text: str) -> Dict[str, Any]:
    """Parse places from text. Returns {pickup, drop, bare, vague}"""
    result = {"pickup": None, "drop": None, "bare": None, "vague": False}
    
    text_norm = normalize(text)
    has_ponnum = any(w in text_norm for w in [normalize(p) for p in ["ponnum", "ponnu", "ponen", "pognu", "poren", "poganum", "pognum"]])
    has_to = "to" in text_norm
    has_drop = "drop" in text_norm
    
    pickup_match = re.search(r'(\w+)\s*la\s*irundhu', text_norm)
    if pickup_match:
        pickup_text = normalize(pickup_match.group(1))
        if pickup_text in PLACE_MAP:
            result["pickup"] = PLACE_MAP[pickup_text]
        else:
            result["pickup"] = pickup_match.group(1).title()
    
    if not result["pickup"]:
        iruken_match = re.search(r'(\w+)\s*la\s*iruken', text_norm)
        if iruken_match:
            pickup_text = normalize(iruken_match.group(1))
            if pickup_text in PLACE_MAP:
                result["pickup"] = PLACE_MAP[pickup_text]
            else:
                result["pickup"] = iruken_match.group(1).title()
    
    if result["pickup"]:
        la_irundhu_drop = re.search(r'la\s*irundhu\s+(\w+)\s+ku', text_norm)
        if la_irundhu_drop:
            drop_text = normalize(la_irundhu_drop.group(1))
            if drop_text in PLACE_MAP:
                result["drop"] = PLACE_MAP[drop_text]
            else:
                result["drop"] = la_irundhu_drop.group(1).title()
            return result
    
    compound_drop = re.search(r'(\w+)\s+(railway|bus)\s+(?:station|stand)\s+ku\s*(?:ponnum|ponum|ponen|pognu|poren|poganum|pognum)', text_norm)
    if compound_drop:
        place_text = normalize(compound_drop.group(1))
        station_type = compound_drop.group(2)
        base_name = PLACE_MAP.get(place_text, compound_drop.group(1).title())
        suffix = "\u0BB0\u0BAF\u0BBF\u0BB2\u0BCD \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD" if station_type == "railway" else "\u0BAA\u0BC7\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD"
        result["drop"] = base_name + " " + suffix
        return result
    
    if not result["drop"]:
        ponnum_ku = re.search(r'((?:\w+\s+)*\w+)\s+ku\s*(?:ponnum|ponum|ponen|pognu|poren|poganum|pognum)', text_norm)
        if ponnum_ku:
            drop_text = ponnum_ku.group(1)
            for part in drop_text.split():
                part_norm = normalize(part)
                if part_norm in PLACE_MAP:
                    result["drop"] = PLACE_MAP[part_norm]
                    return result
            if drop_text not in FILLER_WORDS:
                result["drop"] = drop_text.title()
            return result
    
    if not result["drop"] and has_ponnum:
        words = text_norm.split()
        for i, word in enumerate(words):
            if word in {normalize(p) for p in ["ponnum", "ponnu", "ponen", "pognu", "poren", "poganum", "pognum"]}:
                if i > 0:
                    if i >= 2:
                        prev_word1 = words[i-2]
                        prev_word2 = words[i-1]
                        if prev_word2 not in ["la", "ku", "irundhu", "iruken"] and prev_word1 not in FILLER_WORDS:
                            if prev_word2.endswith("ku"):
                                two_word_without_ku = prev_word1 + " " + prev_word2[:-2]
                                two_norm = normalize(two_word_without_ku)
                                if two_norm in PLACE_MAP:
                                    result["drop"] = PLACE_MAP[two_norm]
                                    return result
                                else:
                                    result["drop"] = two_word_without_ku.title()
                                    return result
                            else:
                                two_word = prev_word1 + " " + prev_word2
                                two_norm = normalize(two_word)
                                if two_norm in PLACE_MAP:
                                    result["drop"] = PLACE_MAP[two_norm]
                                    return result
                                else:
                                    result["drop"] = two_word.title()
                                    return result
                    
                    prev_word = words[i - 1]
                    if prev_word not in ["la", "ku", "naa", "ila", "to", "drop", "irundhu", "iruken"] and prev_word not in FILLER_WORDS:
                        prev_norm = normalize(prev_word)
                        if prev_norm in PLACE_MAP:
                            result["drop"] = PLACE_MAP[prev_norm]
                            return result
                        elif prev_word.endswith("ku"):
                            prev_without_ku = prev_word[:-2]
                            prev_norm_without = normalize(prev_without_ku)
                            if prev_norm_without in PLACE_MAP:
                                result["drop"] = PLACE_MAP[prev_norm_without]
                                return result
                            else:
                                result["drop"] = prev_without_ku.title()
                                return result
                        else:
                            result["drop"] = prev_word.title()
                            return result
    
    if not result["drop"] and has_to:
        is_from_to = re.search(r'\bfrom\s+', text_norm)
        if not is_from_to:
            to_match = re.search(r'\bto\s+(\w+)', text_norm)
            if to_match:
                drop_text = normalize(to_match.group(1))
                if drop_text in PLACE_MAP:
                    result["drop"] = PLACE_MAP[drop_text]
                else:
                    result["drop"] = to_match.group(1).title()
                return result
    
    if not result["drop"] and has_drop:
        drop_match = re.search(r'\bdrop\s+(\w+)', text_norm)
        if drop_match:
            drop_text = normalize(drop_match.group(1))
            if drop_text in PLACE_MAP:
                result["drop"] = PLACE_MAP[drop_text]
            else:
                result["drop"] = drop_match.group(1).title()
            return result
    
    from_to = re.search(r'\bfrom\s+((?:\w+\s+)*\w+)\s+to\s+((?:\w+\s+)*\w+)', text_norm)
    if from_to:
        from_text = from_to.group(1)
        to_text = from_to.group(2)
        
        if not result["pickup"]:
            from_norm = normalize(from_text)
            if from_norm in PLACE_MAP:
                result["pickup"] = PLACE_MAP[from_norm]
            else:
                for word in from_text.split():
                    word_norm = normalize(word)
                    if word_norm in PLACE_MAP:
                        result["pickup"] = PLACE_MAP[word_norm]
                        break
                else:
                    result["pickup"] = from_text.title()
        
        if not result["drop"]:
            to_norm = normalize(to_text)
            if to_norm in PLACE_MAP:
                result["drop"] = PLACE_MAP[to_norm]
            else:
                for word in to_text.split():
                    word_norm = normalize(word)
                    if word_norm in PLACE_MAP:
                        result["drop"] = PLACE_MAP[word_norm]
                        break
                else:
                    result["drop"] = to_text.title()
        return result
    
    if not result["pickup"] and not result["drop"]:
        compound_match = re.search(r'(\w+)\s+(railway|bus)\s+(?:station|stand)', text_norm)
        if compound_match:
            place_word = normalize(compound_match.group(1))
            station_type = compound_match.group(2)
            compound_name = (PLACE_MAP.get(place_word, compound_match.group(1).title()) + 
                           (" \u0BB0\u0BAF\u0BBF\u0BB2\u0BCD \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD" if station_type == "railway" else " \u0BAA\u0BC7\u0BB0\u0BC1\u0BA8\u0BCD\u0BA4\u0BC1 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD"))
            
            if "la irundhu" in text_norm or "from" in text_norm:
                result["pickup"] = compound_name
            elif "ponnum" in text_norm or "ponum" in text_norm or "to" in text_norm or "ku" in text_norm:
                result["drop"] = compound_name
            else:
                result["bare"] = compound_name
            return result
    
    if not result["pickup"] and not result["drop"] and not result["bare"]:
        for word in text_norm.split():
            if word in PLACE_MAP:
                result["bare"] = PLACE_MAP[word]
                return result
    
    if not result["pickup"] and not result["drop"] and not result["bare"]:
        loc_match = re.search(r'\blocation\s+(\w+)', text_norm)
        if loc_match:
            loc_text = normalize(loc_match.group(1))
            if loc_text in PLACE_MAP:
                result["bare"] = PLACE_MAP[loc_text]
            else:
                result["bare"] = loc_match.group(1).title()
            return result
    
    if any(word in text_norm.split() for word in VAGUE_WORDS):
        result["vague"] = True
    
    return result


def parse_time(text: str) -> Dict[str, Any]:
    """Parse time from text. Returns {date, now, hour, minute, ampm}"""
    result = {}
    text_norm = normalize(text)
    
    if any(w in text_norm for w in [normalize(p) for p in ["ippo", "ipove", "now"]]):
        result["now"] = True
        return result
    
    result["now"] = False
    
    if any(w in text_norm for w in [normalize(p) for p in ["naliki", "nalaiku", "nalai", "tomorrow"]]):
        result["date"] = "tomorrow"
    elif any(w in text_norm for w in [normalize(p) for p in ["inniki", "innaiku", "today"]]):
        result["date"] = "today"
    else:
        result["date"] = None
    
    hour = None
    minute = None
    
    time_match = re.search(r'(\d{1,2})\s*:?\s*(\d{2})', text_norm)
    if time_match:
        h = int(time_match.group(1))
        m = int(time_match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            if h >= 13:
                hour, minute = h - 12, m
                result["ampm"] = "pm"
            else:
                hour, minute = h if h != 0 else 12, m
    
    tamil_digits = {normalize(k): v for k, v in [
        ("onnu", 1), ("randu", 2), ("moonu", 3), ("nalu", 4), ("anju", 5),
        ("aru", 6), ("ezhu", 7), ("ettu", 8), ("onpathu", 9), ("pathu", 10)
    ]}
    
    half_hours_base = [("arai", 6, 30), ("ezharai", 7, 30), ("ettarai", 8, 30), 
                       ("onpatharai", 9, 30), ("patharai", 10, 30), 
                       ("padinnirarai", 11, 30), ("paddannirarai", 12, 30)]
    half_hours = {normalize(k): (h, m) for k, h, m in half_hours_base}
    
    for half_word, (h, m) in half_hours.items():
        if re.search(rf'\b{re.escape(half_word)}\b', text_norm):
            hour, minute = h, m
            result["hour"] = hour
            result["minute"] = minute
            if "ampm" not in result:
                result["ampm"] = None
            return result
    
    if hour is None:
        for digit_word, digit_val in tamil_digits.items():
            if digit_word in text_norm:
                hour = digit_val
                if minute is None:
                    minute = 0
                break
    
    if hour is None:
        mani_match = re.search(r'(\d{1,2})\s*mani', text_norm)
        if mani_match:
            hour = int(mani_match.group(1))
            minute = 0
    
    if hour is None:
        for digit_word, digit_val in tamil_digits.items():
            if digit_word + " mani" in text_norm:
                hour = digit_val
                minute = 0
                break
    
    if hour is not None:
        result["hour"] = hour
        result["minute"] = minute if minute is not None else 0
        if "ampm" not in result:
            if any(w in text_norm for w in [normalize(p) for p in ["kalai", "morning", "subah"]]):
                result["ampm"] = "am"
            elif any(w in text_norm for w in [normalize(p) for p in ["malai", "evening", "afternoon", "night", "raathri"]]):
                result["ampm"] = "pm"
            else:
                result["ampm"] = None
    else:
        if any(w in text_norm for w in [normalize(p) for p in ["kalai", "morning", "subah"]]):
            result["ampm"] = "am"
        elif any(w in text_norm for w in [normalize(p) for p in ["malai", "evening", "afternoon", "night", "raathri"]]):
            result["ampm"] = "pm"
        else:
            result["ampm"] = None
    
    return result


def is_question(text: str) -> bool:
    """Check if text is a question."""
    text_lower = text.lower()
    text_norm = normalize(text)
    
    # Check normalized tokens for question words (whole word match)
    norm_tokens = text_norm.split()
    for q_word in QUESTION_WORDS:
        if q_word in norm_tokens:
            return True
    
    # Check original text for question words (whole word match)
    lower_tokens = text_lower.split()
    for q_word in QUESTION_WORDS:
        if q_word in lower_tokens:
            return True
    
    if "?" in text:
        return True
    
    return False


PULLI = "\u0BCD"
MA_PULLI = "\u0BAE\u0BCD"
KKU = "\u0B95\u0BCD\u0B95\u0BC1"
UKKU = "\u0BC1" + KKU
TTHUKKU = "\u0BA4\u0BCD\u0BA4\u0BC1" + KKU[1:]
TTHIL = "\u0BA4\u0BCD\u0BA4\u0BBF\u0BB2\u0BCD"
YIL = "\u0BAF\u0BBF\u0BB2\u0BCD"
IL = "\u0BBF\u0BB2\u0BCD"
LA = "\u0BB2"


def _is_latin(name):
    """Check if name is pure ASCII (Latin)."""
    if name is None:
        return False
    return name.isascii()


def dat(name):
    """Apply dative ending to place name."""
    if name is None:
        return ""
    if _is_latin(name):
        return name + "-" + KKU
    if name.endswith(MA_PULLI):
        return name[:-2] + "\u0BA4\u0BCD\u0BA4\u0BC1" + KKU
    if name.endswith(PULLI):
        return name[:-1] + UKKU
    return name + KKU


def loc(name):
    """Apply locative ending to place name."""
    if name is None:
        return ""
    if _is_latin(name):
        return name + "-" + LA
    if name.endswith(MA_PULLI):
        return name[:-2] + TTHIL
    if name.endswith(PULLI):
        return name[:-1] + IL
    return name + YIL
