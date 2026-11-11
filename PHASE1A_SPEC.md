# PHASE 1A: Tamil Cab Booking Dialogue Parser

## Overview
PHASE 1A implements a pure parsing layer for Tamil cab booking dialogue. The parser extracts and normalizes:
1. **Places**: pickup location, drop location, or bare location name
2. **Time**: date (today/tomorrow), time (hour/minute), AM/PM, or immediate booking
3. **Questions**: detection of informational queries vs booking requests
4. **Tamil Endings**: dative (dat, -ukkU) and locative (loc, -il) inflections

## Requirements

### Encoding
- All string literals must use `\uXXXX` Unicode escapes (no native UTF-8 bytes in source)
- Source files must be pure ASCII (validated at import time)
- Byte-by-byte check ensures portability: `all(b <= 127 for b in source_bytes)`

### Place Parsing
Extract locations from 15 reference places:
1. **Madurai** (மதுரை): spellings: madurai, madhurai
2. **Trichy** (திருச்சி): spellings: trichy, thrichy, tiruchi, tiruchirappalli
3. **Chennai** (சென்னை): spellings: chennai, madras, madra
4. **Coimbatore** (கோயம்புத்தூர்): spellings: coimbatore, kovai
5. **Salem** (சேலம்): spellings: salem
6. **Anna Nagar** (அண்ணா நகர்): spellings: anna nagar
7. **KK Nagar** (கே.கே. நகர்): spellings: kk nagar
8. **T Nagar** (டி. நகர்): spellings: t nagar
9. **Teppakulam** (தெப்பக்குளம்): spellings: teppakulam
10. **Meenakshi** (மீனாட்சி அம்மன் கோவில்): spellings: meenakshi, meenakshi amman, meenakshi temple
11. **Marina** (மெரीனா கடற்கரை): spellings: marina, marina beach
12. **Airport** (விமான நிலையம்): spellings: airport
13. **Railway Station** (ரயில் நிலையம்): spellings: railway station
14. **Bus Stand** (பேருந்து நிலையம்): spellings: bus stand

#### Output Format
```python
{
    "pickup": str | None,  # Source location (Tamil name or English title case)
    "drop": str | None,    # Destination location (Tamil name or English title case)
    "bare": str | None,    # Single location mention (when no direction indicated)
    "vague": bool          # True if kovil/temple/station mentioned without specifics
}
```

#### Patterns
1. **Pickup from pattern**: `<place> la irundhu` or `<place> la iruken`
2. **Drop to pattern**: `<place> ku` + trigger (ponnum, poganum, pognum, etc.)
3. **Compound drop**: `<place> railway/bus station ku` + trigger
4. **From-to**: `from <pickup> to <drop>`
5. **Single mention**: No direction indicator → bare
6. **Vague mention**: Contains "kovil", "temple", or "station" without specifics

#### Normalization Rules
- NFC Unicode normalization
- Lowercase all input
- Strip leading/trailing whitespace
- Collapse consecutive identical Latin letters (e.g., "maaddurai" → "madurai")
- Deduplicate consecutive tokens
- Remove punctuation except Tamil Unicode and apostrophe

### Time Parsing
Extract temporal information from input.

#### Output Format
```python
{
    "now": bool,           # True for immediate booking (ippo, ipove)
    "date": str | None,    # "today", "tomorrow", or None
    "hour": int | None,    # Hour in 12-hour format (1-12)
    "minute": int | None,  # Minute (0-59)
    "ampm": str | None     # "am", "pm", or None
}
```

#### Test Cases (14 total)
| Input | Expected |
|-------|----------|
| naliki 7 30 ku | {date: tomorrow, now: False, hour: 7, minute: 30, ampm: None} |
| naliki 730 ku | {date: tomorrow, now: False, hour: 7, minute: 30, ampm: None} |
| ezharai | {date: None, now: False, hour: 7, minute: 30, ampm: None} |
| arai | {date: None, now: False, hour: 6, minute: 30, ampm: None} |
| ettarai | {date: None, now: False, hour: 8, minute: 30, ampm: None} |
| 7 mani | {date: None, now: False, hour: 7, minute: 0, ampm: None} |
| ezhu mani | {date: None, now: False, hour: 7, minute: 0, ampm: None} |
| 19:30 | {date: None, now: False, hour: 7, minute: 30, ampm: pm} |
| kalai | {date: None, now: False, ampm: am} |
| malai | {date: None, now: False, ampm: pm} |
| inniki raathri 9 mani ku | {date: today, now: False, hour: 9, minute: 0, ampm: pm} |
| ippo cab venum | {now: True} |
| ippove | {now: True} |
| naliki | {date: tomorrow} |

#### Patterns
- **Immediate**: `ippo`, `ipove`, `now` → `now=True`
- **Date tomorrow**: `naliki`, `nalaiku`, `nalai` → `date=tomorrow`
- **Date today**: `inniki`, `innaiku` → `date=today`
- **Half hours**: `arai` (6:30), `ezharai` (7:30), `ettarai` (8:30), etc.
- **Digit hours**: Tamil numerals (`onnu`=1, ..., `pathu`=10) with optional `mani`
- **Clock time**: `HH:MM` or `HHMM` format; ≥13 → PM
- **AM/PM**: `kalai`=AM, `malai`/`raathri`/`evening`=PM

### Question Detection
Identify information queries vs. booking requests.

#### Output
- Boolean: True for question, False for booking/statement

#### Test Cases (8 total)
Questions (True):
1. madurai la enna famous
2. time enna
3. 2 * 3 evlo
4. nee epidi iruka
5. naa madurai la iruken atha pathi sollu

Non-questions (False):
1. madurai la irundhu trichy ku
2. cab venum
3. chenni ponnum

#### Question Words
Base list: `enna`, `epdi`, `epidi`, `evlo`, `epo`, `yaru`, `pathi`, `about`, `sollu`, `atha`, `what`, `how`, `when`, `why`
- Check both normalized and original case
- Also check for `?` in text

### Tamil Endings (Dative & Locative)

#### Dative Form (குறிப்பு உருപு, -ukkU / -ttukkU)
Used for "to" location (destination, goal).

**Rules:**
1. Latin names (ASCII): append `-KKU` (=`-kkU`)
2. Names ending in `ம्` (MA_PULLI): remove last 2 chars, append `त्त` + KKU
3. Names ending in `्` (PULLI): remove last char, append `ुक्कु`
4. Others: append `क्क` + `ु`

**Ground Truth Cases:**
| Tamil Input | Expected Dative | Notes |
|-------------|-----------------|-------|
| मधुरै | मधुरैक्कु | No suffix → append KKU |
| திருச்சி | திருச्சிக्कु | No suffix → append KKU |
| अण्णा नगर् | अण्णा नगरुक्कु | Ends in PULLI: remove, append UKKU |
| तेप्पक्कुलम् | तेप्पक्कुलत्तुक्कु | Ends in MA_PULLI: remove 2 chars, add TTHUKKU |
| विमान निलayम् | विमान निलayत्तुक्कु | Ends in MA_PULLI: remove 2 chars, add TTHUKKU |
| मीनाक्षि अम्मन् कोविल् | मीनाक्षि अम्मन् कोविलुक्कु | Ends in PULLI: remove, append UKKU |
| सेन्नai | सेन्नaiक्कु | No suffix → append KKU |

#### Locative Form (வடி உருபु, -il / -tthil)
Used for "at" location (place where something is/happens).

**Rules:**
1. Latin names (ASCII): append `-LA` (=`-l`)
2. Names ending in `म्` (MA_PULLI): remove last 2 chars, append `त्त` + IL
3. Names ending in `्` (PULLI): 
   - If previous char is vowel sign for /aː/ (ै): append YIL (`யில்`)
   - Otherwise: append IL (`ில்`)
4. Others: append YIL

**Ground Truth Cases:**
| Tamil Input | Expected Locative | Notes |
|-------------|-------------------|-------|
| मधुरै | मधुरैयिल् | Ends in ै: use YIL |
| திருச்சி | திருச்சியில் | Ends in ி: use YIL |
| अण्णा नगर् | None | No locative (location cannot be described as "at Anna Nagar") |
| तेप्पक्कुलम् | तेप्पक्कुलत्तिल् | Ends in MA_PULLI: remove 2 chars, add TTHIL |
| विमान निलayम् | विमान निलayत्तिल् | Ends in MA_PULLI: remove 2 chars, add TTHIL |
| मीनाक्षि अम्मन् कोविल् | None | No locative (proper noun, cannot use) |
| सेन्नai | सेन्नaiयिल् | Ends in ै: use YIL |

#### Unicode Constants
```python
PULLI = "\u0BCD"                      # ्
MA_PULLI = "\u0BAE\u0BCD"            # म्
KKU = "\u0B95\u0BCD\u0B95\u0BC1"     # क्कु
UKKU = "\u0BC1" + KKU                # ुक्कु
TTHUKKU = "\u0BA4\u0BCD\u0BA4\u0BC1\u0B95\u0BCD\u0B95\u0BC1"  # त्त + KKU
TTHIL = "\u0BA4\u0BCD\u0BA4\u0BBF\u0BB2\u0BCD"               # त्तिल्
YIL = "\u0BAF\u0BBF\u0BB2\u0BCD"                            # यिल्
IL = "\u0BBF\u0BB2\u0BCD"                                   # िल्
LA = "\u0BB2"                                               # ल
```

#### Test Cases (7 total with dative, 5 with locative)
All 7 test both dat() and loc() (loc is None for 2 cases):
1. मधुरै → मधुरैक्कु, मधुरैयिल्
2. திருச்சி → திருச்சிக்கु, திருச்சியில்
3. अण्णा नगर् → अण्णा नगरुक्कु, None
4. तेप्पक्कुलम् → तेप्पक्कुलत्तुक्कु, तेप्पक्कुलत्तिल्
5. विमान निलayम् → विमान निलayत्तुक्कु, विमान निलayत्तिल्
6. मीनाक्षि अम्मन् कोविल् → मीनाक्षि अम्मन् कोविलुक्कु, None
7. सेन्नai → सेन्नaiक्कु, सेन्नaiयिल्

## Implementation

### Files
- **dialogue_parse.py**: 4 pure functions (parse_places, parse_time, is_question, dat, loc)
  - No I/O, no side effects
  - All Unicode as `\uXXXX` escapes
  - ASCII-only source (validated at test import time)
- **test_parse.py**: 41 test cases across 4 categories
  - 15 place tests
  - 14 time tests
  - 8 question tests
  - 4 endings tests (dat/loc)
  - All tests pass when implementations are correct

### Testing Strategy
1. Run `python -X utf8 test_parse.py` → all 41 tests pass
2. Run `python -X utf8 check_endings.py` → failures: 0
3. Verify both scripts report 100% success

## Known Issues (Fixed in PHASE 1A-1c)

### Bug: Incorrect Tamil Morphology in dat() and loc()
**Symptom**: Endings tests failed because dat() and loc() functions did not correctly handle Tamil grammatical suffixes.

**Root Cause**:
- Did not remove pulli (्) before appending suffixes
- Did not distinguish between ् and म् endings
- Generated incorrect vowel signs in locative forms

**Examples of Broken Output**:
- "अण्णा नगर्" → dat() returned "अण्णा नगर्ुक्कु" (kept pulli, appended) instead of "अण्णा नगरुक्कु" (removed pulli, then appended)
- "सेन्नai" → loc() returned "सेन्नaiल्" (wrong vowel sign) instead of "सेन्नaiयिल्" (correct YIL)
- "तेप्पक्कुलम्" → dat() returned "तेप्पक्कुलमत्तुक्कु" (only removed ्, not म्) instead of "तेप्पक्कुलत्तुक्कु"

**Fix**: Replace dat() and loc() functions with corrected implementations that:
1. Check for MA_PULLI (म्) first and remove 2 characters
2. Check for PULLI (्) and remove 1 character
3. Append correct suffix based on context
4. Use YIL for vowel-ending names, IL for others in locative
