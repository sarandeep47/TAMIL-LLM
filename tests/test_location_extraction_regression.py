"""
Regression tests for location extraction and retrieval.

Tests:
1. College name detection (KLNCE, IIT, etc. should not be locations)
2. Tanglish location patterns work (naa Madurai la iruken)
3. Location write rules (regex/tanglish override AI)
4. Database path consistency
"""

import pytest
from fact_extractor import _is_college_name
from memory_db import DB_PATH
from chat_memory import _INTENT_PATTERNS


class TestCollegeNameDetection:
    """Test that _is_college_name correctly identifies institutions."""
    
    def test_all_caps_college_name(self):
        """KLNCE (all caps) should be detected as college."""
        assert _is_college_name("KLNCE") is True
    
    def test_college_keyword_in_name(self):
        """Names containing college keywords should be detected."""
        assert _is_college_name("MIT") is True
        assert _is_college_name("IIT") is True
        assert _is_college_name("NIT") is True
        assert _is_college_name("IIIT") is True
    
    def test_legitimate_city_names(self):
        """Real cities should NOT be detected as colleges."""
        assert _is_college_name("Madurai") is False
        assert _is_college_name("Chennai") is False
        assert _is_college_name("Delhi") is False
        assert _is_college_name("Bangalore") is False
        assert _is_college_name("Kolkata") is False
    
    def test_college_keywords(self):
        """Names with college-related keywords detected."""
        assert _is_college_name("college") is True or _is_college_name("College") is True
        assert _is_college_name("university") is True or _is_college_name("University") is True


class TestTanglishLocationPatterns:
    """Test that Tanglish location patterns are present."""
    
    def test_location_patterns_exist(self):
        """Location should have multiple query patterns."""
        location_patterns = _INTENT_PATTERNS.get('user_location', [])
        assert len(location_patterns) > 0, "No location patterns found"
    
    def test_tanglish_patterns_for_location(self):
        """Should have Tanglish patterns for location queries."""
        location_patterns = _INTENT_PATTERNS.get('user_location', [])
        # Check for Tanglish variations
        tanglish_patterns = [p for p in location_patterns if any(kw in p.lower() for kw in ['ooru', 'irukken', 'iruken'])]
        assert len(tanglish_patterns) > 0, f"No Tanglish location patterns. Found: {location_patterns}"
    
    def test_location_query_pattern_enga(self):
        """Should have pattern for 'where' (enga) queries."""
        location_patterns = _INTENT_PATTERNS.get('user_location', [])
        enga_patterns = [p for p in location_patterns if 'enga' in p.lower()]
        assert len(enga_patterns) > 0, f"No 'enga' patterns. Found: {location_patterns}"
    
    def test_location_query_ooru(self):
        """Should have pattern for 'ooru' (town/city) queries."""
        location_patterns = _INTENT_PATTERNS.get('user_location', [])
        ooru_patterns = [p for p in location_patterns if 'ooru' in p.lower()]
        assert len(ooru_patterns) > 0, f"No 'ooru' patterns. Found: {location_patterns}"


class TestDatabasePathConsistency:
    """Test that backend and terminal use same canonical database."""
    
    def test_canonical_db_path_set(self):
        """DB_PATH should point to canonical root location."""
        # DB_PATH should be in the root data/processed directory
        db_path_str = str(DB_PATH)
        assert 'data' in db_path_str
        assert 'processed' in db_path_str
        assert db_path_str.endswith('memory.db')
        
        # Should not end with backend/... (unless it's a path like backend\..\..\)
        # The key is that it should point to the root data/processed
        assert 'data/processed/memory.db' in db_path_str or \
               'data\\processed\\memory.db' in db_path_str


class TestTanglishLocationRegexPatterns:
    """Test that regex patterns for Tanglish locations were added."""
    
    def test_tanglish_la_iruken_pattern(self):
        """Regex should support 'naa X la iruken' pattern."""
        from fact_extractor import _ASCII_REGEXES
        location_regexes = [r for k, r in _ASCII_REGEXES if k == 'user_location']
        
        # Check that at least one regex can match Tanglish location patterns
        test_cases = [
            "naa Madurai la iruken",
            "en Madurai la iruken",
        ]
        
        matches_found = False
        for test_case in test_cases:
            for regex in location_regexes:
                if regex.search(test_case):
                    matches_found = True
                    break
        
        assert matches_found, f"No regex matched Tanglish location patterns from {test_cases}"
    
    def test_tanglish_irundhu_pattern(self):
        """Regex should support 'naa X irundhu varen' pattern for origin (not location)."""
        from fact_extractor import _ASCII_REGEXES
        origin_regexes = [r for k, r in _ASCII_REGEXES if k == 'user_origin']
        
        test_cases = [
            "naa Madurai irundhu varen",
            "naa Madurai la irundhu varen",
        ]
        
        matches_found = False
        for test_case in test_cases:
            for regex in origin_regexes:
                if regex.search(test_case):
                    matches_found = True
                    break
        
        assert matches_found, f"No regex matched Tanglish origin patterns in user_origin"


class TestCollegeDetectionInExtraction:
    """Test that college names are not extracted as locations."""
    
    def test_college_name_filter_exists(self):
        """_is_college_name function should be used in validation."""
        import inspect
        from fact_extractor import _validate
        
        # Check that _is_college_name is mentioned in _validate
        source = inspect.getsource(_validate)
        assert '_is_college_name' in source, \
            "_is_college_name filter not found in _validate function"
    
    def test_college_filter_in_tanglish_extraction(self):
        """College filter should be in tanglish extraction path."""
        import inspect
        from fact_extractor import _extract_by_regex
        
        source = inspect.getsource(_extract_by_regex)
        assert '_is_college_name' in source, \
            "_is_college_name filter not found in _extract_by_regex function"


class TestWriteRulesForLocationOverride:
    """Test that write rules allow regex/tanglish to override AI."""
    
    def test_write_rules_documentation(self):
        """Write rules should explicitly allow regex to override AI."""
        import inspect
        from memory_db import save_memory
        
        source = inspect.getsource(save_memory)
        # Check that the docstring or code mentions regex overriding AI
        assert 'regex' in source.lower() and 'ai' in source.lower(), \
            "Write rules don't clearly document interaction between regex and AI sources"
        assert 'override' in source.lower() or 'overwrite' in source.lower(), \
            "Write rules don't mention override/overwrite logic"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
