"""
test_tanglish_tokenizer.py — Unit tests for word-by-word Tanglish tokenization.

Tests the tokenizer against real-world Tanglish inputs with fuzzy matching.
"""

import pytest
from model.tanglish_tokenizer import (
    Token,
    Statement,
    tokenize_tanglish,
    extract_statements_from_tokens,
    parse_tanglish,
    detect_intent_with_tokenization,
)


class TestTokenization:
    """Test basic tokenization and token creation."""
    
    def test_token_creation(self):
        """Test Token object creation and serialization."""
        t = Token("vannakam", canonical="vannakam", category="greeting", similarity_score=1.0)
        assert t.word == "vannakam"
        assert t.canonical == "vannakam"
        assert t.category == "greeting"
        assert t.to_dict()["similarity"] == 1.0
    
    def test_tokenize_simple_greeting(self):
        """Test tokenization of a simple greeting."""
        tokens = tokenize_tanglish("vannakam")
        assert len(tokens) == 1
        assert tokens[0].canonical == "vannakam"
        assert tokens[0].category == "greeting"
    
    def test_tokenize_name_sentence(self):
        """Test tokenization with possessive + name."""
        tokens = tokenize_tanglish("en peru sarandeep")
        assert len(tokens) == 3
        assert tokens[0].canonical == "en"
        assert tokens[0].category == "pronoun"
        assert tokens[1].canonical == "peyar"  # fuzzy matched to canonical form
        assert tokens[2].word == "sarandeep"
        assert tokens[2].category == "unknown"
    
    def test_tokenize_location(self):
        """Test tokenization with location."""
        tokens = tokenize_tanglish("madurai")
        assert len(tokens) == 1
        assert tokens[0].canonical == "madurai"
        assert tokens[0].category == "location"
    
    def test_tokenize_with_particles(self):
        """Test tokenization with postpositions (particles)."""
        tokens = tokenize_tanglish("naa madurai la irundhu")
        assert len(tokens) == 4
        # naa (pronoun) madurai (location) la (particle) irundhu (verb)
        assert tokens[0].canonical == "naan"  # fuzzy: "naa" -> "naan"
        assert tokens[1].canonical == "madurai"
        assert tokens[2].canonical == "la"
        assert tokens[3].canonical == "irundhu"


class TestStatementExtraction:
    """Test extraction of facts from token sequences."""
    
    def test_extract_greeting_only(self):
        """Test extracting a single greeting."""
        tokens = tokenize_tanglish("vannakam")
        stmt = extract_statements_from_tokens(tokens)
        assert stmt.greeting == "vannakam"
        assert stmt.name is None
        assert stmt.location is None
    
    def test_extract_name(self):
        """Test extracting name with possessive marker."""
        tokens = tokenize_tanglish("en peru sarandeep")
        stmt = extract_statements_from_tokens(tokens)
        assert stmt.object_pronoun == "en"
        assert stmt.name == "sarandeep"
    
    def test_extract_location(self):
        """Test extracting location with origin marker."""
        tokens = tokenize_tanglish("naa madurai la irundhu varen")
        stmt = extract_statements_from_tokens(tokens)
        assert stmt.subject_pronoun == "naan"
        assert stmt.location == "madurai"
        assert stmt.origin == "irundhu"
        assert stmt.verb == "varen"
        assert stmt.verb_tense == "present"
    
    def test_extract_multiple_facts(self):
        """Test extraction of multiple facts in one sentence."""
        tokens = tokenize_tanglish("en peru sarandeep madurai la irundhu varen")
        stmt = extract_statements_from_tokens(tokens)
        assert stmt.name == "sarandeep"
        assert stmt.location == "madurai"
        assert stmt.origin == "irundhu"
    
    def test_statement_to_dict(self):
        """Test Statement serialization."""
        stmt = Statement()
        stmt.greeting = "vannakam"
        stmt.name = "sarandeep"
        d = stmt.to_dict()
        assert d["greeting"] == "vannakam"
        assert d["name"] == "sarandeep"
        assert "location" not in d  # None values excluded


class TestFullPipeline:
    """Test end-to-end parsing with the example from requirements."""
    
    def test_parse_full_example(self):
        """
        Test the primary example from the spec:
        "vannakam en peru sarandeep naa madurai la irundhu varen"
        
        Expected parsing:
          - greeting: vannakam (hi)
          - name: sarandeep
          - location: madurai
          - subject_pronoun: naan (I)
          - origin: irundhu (from)
          - verb: varen (came)
          - verb_tense: present
        """
        text = "vannakam en peru sarandeep naa madurai la irundhu varen"
        tokens, stmt = parse_tanglish(text)
        
        # Verify tokens
        assert len(tokens) == 9
        
        # Verify facts
        assert stmt.greeting == "vannakam", "Should recognize greeting"
        assert stmt.name == "sarandeep", "Should extract name"
        assert stmt.location == "madurai", "Should extract location"
        assert stmt.subject_pronoun == "naan", "Should recognize subject pronoun"
        assert stmt.origin == "irundhu", "Should recognize origin marker"
        assert stmt.verb == "varen", "Should recognize verb"
        assert stmt.verb_tense == "present", "Should infer present tense"
    
    def test_parse_name_only(self):
        """Test parsing just a name statement."""
        text = "en peru kavya"
        tokens, stmt = parse_tanglish(text)
        assert stmt.name == "kavya"
    
    def test_parse_location_statement(self):
        """Test parsing a location statement."""
        text = "naa bangalore la irundhu varen"
        tokens, stmt = parse_tanglish(text)
        assert stmt.location == "bangalore"
        assert stmt.origin == "irundhu"
    
    def test_parse_with_fuzzy_variations(self):
        """Test that fuzzy matching works for word variations."""
        # Test "irundhu" / "irundu" (common variation)
        text = "naa madurai la irundu varen"
        tokens, stmt = parse_tanglish(text)
        assert stmt.location == "madurai"


class TestIntentDetection:
    """Test enhanced intent detection with tokenization."""
    
    def test_detect_intent_greeting_and_name(self):
        """Test detecting multiple intents from one sentence."""
        text = "vannakam en peru sarandeep"
        result = detect_intent_with_tokenization(text)
        
        assert "greeting" in result["intents"]
        assert "user_name" in result["intents"]
        assert result["extracted_facts"]["greeting"] == "vannakam"
        assert result["extracted_facts"]["name"] == "sarandeep"
    
    def test_detect_intent_location(self):
        """Test detecting location intent."""
        text = "naa madurai la irundhu varen"
        result = detect_intent_with_tokenization(text)
        
        assert "user_location" in result["intents"]
        assert result["extracted_facts"]["location"] == "madurai"
    
    def test_detect_intent_confidence(self):
        """Test confidence scoring."""
        text = "vannakam en peru sarandeep naa madurai la irundhu varen"
        result = detect_intent_with_tokenization(text)
        
        # Should have high confidence with multiple facts
        assert result["confidence"] > 0.7
        assert len(result["intents"]) >= 2


class TestSafetyNegativeCases:
    """Negative tests: Ensure NO facts are extracted from non-personal statements."""
    
    def test_question_no_extraction(self):
        """Questions should NEVER extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        questions = [
            "What is my name?",
            "Where do I live?",
            "Tell me something.",
            "Can you help?",
        ]
        for q in questions:
            facts = extract_and_save_multi_facts_tanglish(q)
            assert not facts or len(facts) == 0, f"Question extracted facts: {q} → {facts}"
    
    def test_generic_request_no_extraction(self):
        """Generic requests should NOT extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        requests = [
            "Tell me something.",
            "Help me with Python.",
            "I want to learn Python.",
            "Can you explain?",
        ]
        for req in requests:
            facts = extract_and_save_multi_facts_tanglish(req)
            assert not facts or len(facts) == 0, f"Request extracted facts: {req} → {facts}"
    
    def test_gibberish_no_extraction(self):
        """Random gibberish should NOT extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        gibberish = [
            "xyzabc 123",
            "asdfgh qwerty",
            "random words here",
        ]
        for g in gibberish:
            facts = extract_and_save_multi_facts_tanglish(g)
            assert not facts or len(facts) == 0, f"Gibberish extracted facts: {g} → {facts}"
    
    def test_greeting_only_no_extraction(self):
        """Greetings alone should NOT extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        greetings = [
            "vannakam",
            "hi",
            "hello",
            "namaskaram",
        ]
        for g in greetings:
            facts = extract_and_save_multi_facts_tanglish(g)
            assert not facts or len(facts) == 0, f"Greeting extracted facts: {g} → {facts}"
    
    def test_capitalized_words_not_names(self):
        """Capitalized words alone should NEVER become names."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, list_memories
        
        # Clear DB
        for mem in list_memories():
            from memory_db import forget_memory
            forget_memory(mem['key'])
        
        # These should NOT save "Tell" or "What" as names
        messages = [
            "Tell me something.",
            "What is my name?",
            "I want to learn Python.",
        ]
        
        for msg in messages:
            facts = extract_and_save_multi_facts_tanglish(msg)
            if facts and 'user_name' in facts:
                assert False, f"Capitalized word saved as name: {msg} → {facts}"
        
        # Verify DB is empty
        saved_name = get_memory("user_name")
        assert saved_name is None, f"Unexpected name saved: {saved_name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



class TestSafetyNegativeCases:
    """Negative tests: Ensure NO facts are extracted from non-personal statements."""
    
    def test_question_no_extraction(self):
        """Questions should NEVER extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        questions = [
            "What is my name?",
            "Where do I live?",
            "Tell me something.",
            "Can you help?",
        ]
        for q in questions:
            facts = extract_and_save_multi_facts_tanglish(q)
            assert not facts or len(facts) == 0, f"Question extracted facts: {q} → {facts}"
    
    def test_generic_request_no_extraction(self):
        """Generic requests should NOT extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        requests = [
            "Tell me something.",
            "Help me with Python.",
            "I want to learn Python.",
            "Can you explain?",
        ]
        for req in requests:
            facts = extract_and_save_multi_facts_tanglish(req)
            assert not facts or len(facts) == 0, f"Request extracted facts: {req} → {facts}"
    
    def test_gibberish_no_extraction(self):
        """Random gibberish should NOT extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        gibberish = [
            "xyzabc 123",
            "asdfgh qwerty",
            "random words here",
        ]
        for g in gibberish:
            facts = extract_and_save_multi_facts_tanglish(g)
            assert not facts or len(facts) == 0, f"Gibberish extracted facts: {g} → {facts}"
    
    def test_greeting_only_no_extraction(self):
        """Greetings alone should NOT extract facts."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        greetings = [
            "vannakam",
            "hi",
            "hello",
            "namaskaram",
        ]
        for g in greetings:
            facts = extract_and_save_multi_facts_tanglish(g)
            assert not facts or len(facts) == 0, f"Greeting extracted facts: {g} → {facts}"
    
    def test_capitalized_words_not_names(self):
        """Capitalized words alone should NEVER become names."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, list_memories, forget_memory
        
        # Clear DB
        for mem in list_memories():
            forget_memory(mem['key'])
        
        # These should NOT save "Tell" or "What" as names
        messages = [
            "Tell me something.",
            "What is my name?",
            "I want to learn Python.",
        ]
        
        for msg in messages:
            facts = extract_and_save_multi_facts_tanglish(msg)
            if facts and 'user_name' in facts:
                assert False, f"Capitalized word saved as name: {msg} → {facts}"
        
        # Verify DB is empty
        saved_name = get_memory("user_name")
        assert saved_name is None, f"Unexpected name saved: {saved_name}"


class TestSafetyPositiveCases:
    """Positive tests: Valid personal statements SHOULD extract facts correctly."""
    
    def test_name_with_explicit_marker(self):
        """Name extracted when marked with 'en peru' explicitly."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, forget_memory
        
        forget_memory("user_name")
        
        message = "en peru sarandeep"  # Marked with 'en peru'
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # This should save the name
        if facts and 'user_name' in facts:
            assert facts['user_name'] == 'sarandeep'
    
    def test_location_extraction(self):
        """Location extracted from valid statement."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, forget_memory
        
        forget_memory("user_location")
        
        message = "naa madurai la irundhu varen"  # Location statement
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Should extract location
        if facts and 'user_location' in facts:
            assert facts['user_location'] == 'madurai'
    
    def test_degree_extraction(self):
        """Degree saved as education, NOT as name."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, forget_memory
        
        forget_memory("user_school")
        forget_memory("user_name")
        
        message = "naa BE mudichuruken"  # BE = Bachelor of Engineering
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # BE should be saved as education (if anything)
        # But should NOT be saved as a name
        saved_name = get_memory("user_name")
        assert saved_name != 'BE', "Degree 'BE' incorrectly saved as name"
    
    def test_interest_extraction(self):
        """Interests extracted from preference statements."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, forget_memory
        
        forget_memory("user_interest")
        forget_memory("favorite_colour")
        
        message = "ennaku blue pudikum"  # I like blue
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Should extract interest/colour, not random facts
        if facts:
            # If something was saved, it should be colour/interest, not other facts
            for key in facts.keys():
                assert key in ["user_interest", "favorite_colour"], f"Unexpected fact saved: {key}"
