#!/usr/bin/env python3
"""Unit tests for CER (Character Error Rate) function."""
import sys
import os
import unicodedata
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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


def test_identical():
    """Identical strings -> CER = 0.0"""
    cer = compute_cer("வணக்கம்", "வணக்கம்")
    assert cer == 0.0, f"Expected 0.0, got {cer}"
    print("✓ identical Tamil -> 0.0")


def test_one_substitution():
    """One substitution in 10 characters -> CER = 0.1"""
    cer = compute_cer("HelloWorld", "HalloWorld")
    assert abs(cer - 0.1) < 0.01, f"Expected ~0.1, got {cer}"
    print("✓ one substitution -> ~0.1")


def test_empty_reference():
    """Empty reference with non-empty hypothesis -> CER = 1.0"""
    cer = compute_cer("", "hello")
    assert cer == 1.0, f"Expected 1.0, got {cer}"
    print("✓ empty reference -> 1.0")


def test_empty_both():
    """Both empty -> CER = 0.0"""
    cer = compute_cer("", "")
    assert cer == 0.0, f"Expected 0.0, got {cer}"
    print("✓ both empty -> 0.0")


def test_tamil_one_wrong_letter():
    """One wrong letter in short Tamil word gives small non-zero value"""
    # வணக்கம் (7 chars): change first char வ to ப -> ப ணக்கம்
    cer = compute_cer("வணக்கம்", "பணக்கம்")
    # 1 substitution out of 7 chars = 1/7 ≈ 0.143
    assert 0.13 < cer < 0.16, f"Expected ~0.143, got {cer}"
    print(f"✓ Tamil one wrong letter -> {cer:.3f}")


def test_tamil_with_period():
    """Tamil with period vs without -> CER = 0 (period removed)"""
    cer = compute_cer("வணக்கம்.", "வணக்கம்")
    assert cer == 0.0, f"Expected 0.0 (period removed), got {cer}"
    print("✓ Tamil with period normalized to 0")


def test_bracketed_audio_tag():
    """[இசை] (bracketed audio tag) -> empty string"""
    cer = compute_cer("[இசை]", "")
    assert cer == 0.0, f"Expected 0.0 (both empty after normalization), got {cer}"
    print("✓ [இசை] normalized to empty -> 0")


if __name__ == "__main__":
    test_identical()
    test_one_substitution()
    test_empty_reference()
    test_empty_both()
    test_tamil_one_wrong_letter()
    test_tamil_with_period()
    test_bracketed_audio_tag()
    print("\n7/7 tests passed!")
