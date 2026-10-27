"""
tests/test_tanglish_understanding.py

Comprehensive test suite for tanglish_understanding.py module.
Tests cover: token normalization, sentence type detection, tense inference,
topic extraction, entity recognition, operation routing, and end-to-end intents.

Organized into test classes by functionality.
"""

import pytest
from tanglish_understanding import (
    understand_tanglish,
    TanglishIntent,
    _normalize_token,
    _tokenize_tanglish,
    _detect_sentence_type,
    _infer_tense,
    _extract_topic_and_key,
    _extract_entity_value,
    _infer_operation,
    _detect_language_style,
)


# ── Token Normalization Tests ────────────────────────────────────────────────

class TestTokenNormalization:
    """Test _normalize_token() for spelling variants."""
    
    def test_pronoun_variants_naa(self):
        """Variants of 'naa' (I) map to canonical form."""
        assert _normalize_token('naa') == 'naa'
        assert _normalize_token('na') == 'naa'
        assert _normalize_token('naan') == 'naa'
        assert _normalize_token('NAA') == 'naa'  # case-insensitive
        assert _normalize_token('NaA') == 'naa'
    
    def test_pronoun_variants_en(self):
        """Variants of 'en' (my) map to canonical form."""
        assert _normalize_token('en') == 'en'
        assert _normalize_token('ennoda') == 'en'
        assert _normalize_token('ennodai') == 'en'
        assert _normalize_token('enakku') == 'en'
    
    def test_question_words(self):
        """Question word variants."""
        assert _normalize_token('enna') == 'enna'
        assert _normalize_token('ennu') == 'enna'
        assert _normalize_token('enga') == 'enga'
        assert _normalize_token('enge') == 'enga'
        assert _normalize_token('yaaru') == 'yaaru'
        assert _normalize_token('yaru') == 'yaaru'
    
    def test_study_verbs_past(self):
        """Past tense study verb variants."""
        assert _normalize_token('padichen') == 'padichen'
        assert _normalize_token('padichaen') == 'padichen'
        assert _normalize_token('padichae') == 'padichen'
        assert _normalize_token('padi') == 'padichen'
    
    def test_study_verbs_present(self):
        """Present tense study verb variants."""
        assert _normalize_token('padikuren') == 'padikuren'
        assert _normalize_token('padikittu') == 'padikuren'
        assert _normalize_token('padikitu') == 'padikuren'
        assert _normalize_token('padikren') == 'padikuren'
    
    def test_location_verbs(self):
        """Location verb variants."""
        assert _normalize_token('iruken') == 'iruken'
        assert _normalize_token('irukken') == 'iruken'
        assert _normalize_token('vasikiren') == 'vasikiren'
    
    def test_postpositions(self):
        """Locative postposition variants."""
        assert _normalize_token('la') == 'la'
        assert _normalize_token('ile') == 'ile'
        assert _normalize_token('il') == 'ile'
        assert _normalize_token('le') == 'la'
    
    def test_unknown_word(self):
        """Unknown words return lowercased form."""
        assert _normalize_token('hello') == 'hello'
        assert _normalize_token('Chennai') == 'chennai'
        assert _normalize_token('CSE') == 'cse'


# ── Tokenization Tests ───────────────────────────────────────────────────────

class TestTokenization:
    """Test _tokenize_tanglish() for splitting and cleaning."""
    
    def test_basic_split(self):
        """Split on whitespace."""
        tokens = _tokenize_tanglish('naa madurai la iruken')
        assert tokens == ['naa', 'madurai', 'la', 'iruken']
    
    def test_punctuation_removal(self):
        """Remove punctuation."""
        tokens = _tokenize_tanglish('naa enna padichen?')
        assert tokens == ['naa', 'enna', 'padichen']
        
        tokens = _tokenize_tanglish('naa, cse padichen!')
        assert tokens == ['naa', 'cse', 'padichen']
    
    def test_multiple_spaces(self):
        """Handle multiple spaces."""
        tokens = _tokenize_tanglish('naa  madurai   la')
        assert tokens == ['naa', 'madurai', 'la']
    
    def test_case_insensitive(self):
        """Tokens lowercased."""
        tokens = _tokenize_tanglish('NAA MADURAI La IRUKEN')
        assert tokens == ['naa', 'madurai', 'la', 'iruken']
    
    def test_empty_input(self):
        """Empty input returns empty list."""
        assert _tokenize_tanglish('') == []
        assert _tokenize_tanglish('   ') == []


# ── Sentence Type Detection Tests ────────────────────────────────────────────

class TestSentenceTypeDetection:
    """Test _detect_sentence_type() for statement/question/recall/greeting."""
    
    def test_statement_with_verb(self):
        """Statements contain action verbs."""
        tokens = _tokenize_tanglish('naa madurai la iruken')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'naa madurai la iruken') == 'statement'
        
        tokens = _tokenize_tanglish('naa cse padichen')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'naa cse padichen') == 'statement'
    
    def test_question_with_mark(self):
        """Question mark indicates question."""
        tokens = _tokenize_tanglish('naa enna padichen?')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'naa enna padichen?') == 'question'
    
    def test_question_with_question_word(self):
        """Question words (enna, enga, etc.) indicate question."""
        for qw in ['enna', 'enga', 'entha', 'yaaru', 'yeppa']:
            tokens = _tokenize_tanglish(f'{qw}?')
            tokens = [_normalize_token(t) for t in tokens]
            sentence_type = _detect_sentence_type(tokens, f'{qw}?')
            assert sentence_type == 'question', f"Failed for {qw}"
    
    def test_recall_pattern(self):
        """'nu sonnen' pattern indicates recall."""
        tokens = _tokenize_tanglish('naa enga iruken nu sonnen')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'naa enga iruken nu sonnen') == 'recall'
        
        tokens = _tokenize_tanglish('naa cse padichen nu sonnen')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'naa cse padichen nu sonnen') == 'recall'
    
    def test_recall_sollu(self):
        """'sollu' (tell/remind) indicates recall."""
        tokens = _tokenize_tanglish('naa enna padichen sollu')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'naa enna padichen sollu') == 'recall'
    
    def test_greeting(self):
        """Greeting keywords."""
        for greeting in ['vanakkam', 'namaskaram', 'hello', 'hi']:
            tokens = _tokenize_tanglish(greeting)
            tokens = [_normalize_token(t) for t in tokens]
            sentence_type = _detect_sentence_type(tokens, greeting)
            assert sentence_type == 'greeting', f"Failed for {greeting}"
    
    def test_unclear_no_markers(self):
        """No clear markers → unclear."""
        tokens = _tokenize_tanglish('random words here')
        tokens = [_normalize_token(t) for t in tokens]
        assert _detect_sentence_type(tokens, 'random words here') == 'unclear'


# ── Tense Inference Tests ────────────────────────────────────────────────────

class TestTenseInference:
    """Test _infer_tense() for past/current/unknown."""
    
    def test_past_tense(self):
        """Past verbs like 'padichen' indicate past tense."""
        tokens = _tokenize_tanglish('naa cse padichen')
        tokens = [_normalize_token(t) for t in tokens]
        assert _infer_tense(tokens) == 'past'
        
        tokens = _tokenize_tanglish('naa sonnen')
        tokens = [_normalize_token(t) for t in tokens]
        assert _infer_tense(tokens) == 'past'
    
    def test_current_tense(self):
        """Present verbs indicate current tense."""
        tokens = _tokenize_tanglish('naa madurai la iruken')
        tokens = [_normalize_token(t) for t in tokens]
        assert _infer_tense(tokens) == 'current'
        
        tokens = _tokenize_tanglish('naa college la padikuren')
        tokens = [_normalize_token(t) for t in tokens]
        assert _infer_tense(tokens) == 'current'
    
    def test_unknown_tense(self):
        """No tense verb → unknown."""
        tokens = _tokenize_tanglish('vanakkam')
        tokens = [_normalize_token(t) for t in tokens]
        assert _infer_tense(tokens) == 'unknown'


# ── Topic & Memory Key Extraction Tests ──────────────────────────────────────

class TestTopicExtraction:
    """Test _extract_topic_and_key() for identifying topics and memory keys."""
    
    def test_location_topic(self):
        """Detect location topic with location verbs or postpositions."""
        topic, key = _extract_topic_and_key(
            ['naa', 'madurai', 'la', 'iruken'], 'statement', 'current'
        )
        assert topic == 'location'
        assert key == 'user_location'
    
    def test_field_of_study_topic(self):
        """Detect field of study without explicit college keyword."""
        topic, key = _extract_topic_and_key(
            ['naa', 'cse', 'padichen'], 'statement', 'past'
        )
        assert topic == 'field_of_study'
        assert key == 'user_field_of_study'
    
    def test_school_topic(self):
        """Detect school when college/school keyword present."""
        topic, key = _extract_topic_and_key(
            ['naa', 'klnce', 'college', 'la', 'padichen'], 'statement', 'past'
        )
        assert topic == 'school'
        assert key == 'user_school'
    
    def test_name_topic(self):
        """Detect name topic when 'peru' present."""
        topic, key = _extract_topic_and_key(
            ['en', 'peru', 'sarandeep'], 'statement', 'unknown'
        )
        assert topic == 'name'
        assert key == 'user_name'
    
    def test_learning_topic(self):
        """Detect learning topic."""
        topic, key = _extract_topic_and_key(
            ['naa', 'padikiren'], 'statement', 'current'
        )
        assert topic == 'learning'
        assert key == 'user_learning'
    
    def test_no_topic(self):
        """No clear topic → None."""
        topic, key = _extract_topic_and_key(
            ['hello', 'how', 'are', 'you'], 'unclear', 'unknown'
        )
        assert topic is None
        assert key is None


# ── Entity Extraction Tests ──────────────────────────────────────────────────

class TestEntityExtraction:
    """Test _extract_entity_value() for finding entity values."""
    
    def test_location_entity_after_postposition(self):
        """Extract location after 'la'."""
        entities = _extract_entity_value(
            ['naa', 'madurai', 'la', 'iruken'],
            'naa madurai la iruken',
            'location'
        )
        assert entities.get('value') == 'Madurai'
        assert entities.get('subject') == 'user'
    
    def test_field_of_study_entity(self):
        """Extract field acronym."""
        entities = _extract_entity_value(
            ['naa', 'cse', 'padichen'],
            'naa cse padichen',
            'field_of_study'
        )
        assert entities.get('value') == 'CSE'
    
    def test_name_entity(self):
        """Extract name."""
        entities = _extract_entity_value(
            ['en', 'peru', 'sarandeep'],
            'en peru Sarandeep',
            'name'
        )
        assert entities.get('value') == 'Sarandeep'
    
    def test_subject_extraction(self):
        """Extract subject (always user for first-person pronouns)."""
        entities = _extract_entity_value(
            ['naa', 'madurai', 'la', 'iruken'],
            'naa madurai la iruken',
            'location'
        )
        assert entities['subject'] == 'user'
    
    def test_no_entity(self):
        """Return empty entities if no value found."""
        entities = _extract_entity_value(
            ['random', 'words'],
            'random words',
            None
        )
        assert 'value' not in entities


# ── Operation Inference Tests ────────────────────────────────────────────────

class TestOperationInference:
    """Test _infer_operation() for save/retrieve/acknowledge/chat."""
    
    def test_save_operation_statement(self):
        """Statements route to 'save'."""
        assert _infer_operation('statement', 'location') == 'save'
        assert _infer_operation('statement', 'field_of_study') == 'save'
    
    def test_retrieve_operation_question(self):
        """Questions route to 'retrieve'."""
        assert _infer_operation('question', 'location') == 'retrieve'
        assert _infer_operation('question', 'name') == 'retrieve'
    
    def test_retrieve_operation_recall(self):
        """Recalls route to 'retrieve'."""
        assert _infer_operation('recall', 'location') == 'retrieve'
    
    def test_chat_operation_greeting(self):
        """Greetings route to 'chat'."""
        assert _infer_operation('greeting', None) == 'chat'
    
    def test_chat_operation_unclear(self):
        """Unclear sentences route to 'chat'."""
        assert _infer_operation('unclear', None) == 'chat'


# ── Language Style Detection Tests ───────────────────────────────────────────

class TestLanguageStyleDetection:
    """Test _detect_language_style() for Tamil/Tanglish/English."""
    
    def test_english_style(self):
        """Pure English text."""
        assert _detect_language_style('hello how are you') == 'english'
        assert _detect_language_style('what is your name') == 'english'
        assert _detect_language_style('today is friday') == 'english'
    
    def test_tanglish_style(self):
        """Tanglish words recognized."""
        assert _detect_language_style('naa madurai la iruken') == 'tanglish'
        assert _detect_language_style('naa enna padichen') == 'tanglish'
    
    def test_tamil_style(self):
        """Tamil script detected."""
        tamil_text = "நான் என்ன படிச்சேன்"  # naan enna padichen in Tamil script
        assert _detect_language_style(tamil_text) == 'tamil'


# ── End-to-End Intent Tests ──────────────────────────────────────────────────

class TestUnderstandTanglish:
    """End-to-end tests for understand_tanglish() main API."""
    
    def test_location_statement(self):
        """Location statement: save to user_location."""
        intent = understand_tanglish('naa madurai la iruken')
        assert intent.sentence_type == 'statement'
        assert intent.topic == 'location'
        assert intent.memory_key == 'user_location'
        assert intent.operation == 'save'
        assert intent.entities.get('value') == 'Madurai'
        assert intent.is_personal_fact()
        assert intent.confidence > 0.7
    
    def test_field_of_study_statement(self):
        """Field of study statement."""
        intent = understand_tanglish('naa cse padichen')
        assert intent.sentence_type == 'statement'
        assert intent.topic == 'field_of_study'
        assert intent.memory_key == 'user_field_of_study'
        assert intent.operation == 'save'
        assert intent.entities.get('value') == 'CSE'
        assert intent.confidence > 0.7
    
    def test_name_statement(self):
        """Name statement."""
        intent = understand_tanglish('en peru sarandeep')
        assert intent.sentence_type == 'statement'
        assert intent.topic == 'name'
        assert intent.memory_key == 'user_name'
        assert intent.operation == 'save'
    
    def test_location_question(self):
        """Location question: retrieve from memory."""
        intent = understand_tanglish('naa enga iruken?')
        assert intent.sentence_type == 'question'
        assert intent.topic == 'location'
        assert intent.memory_key == 'user_location'
        assert intent.operation == 'retrieve'
    
    def test_recall_pattern(self):
        """Recall pattern: retrieve from memory."""
        intent = understand_tanglish('naa enga iruken nu sonnen')
        assert intent.sentence_type == 'recall'
        assert intent.topic == 'location'
        assert intent.operation == 'retrieve'
    
    def test_greeting(self):
        """Greeting routes to chat."""
        intent = understand_tanglish('vanakkam')
        assert intent.sentence_type == 'greeting'
        assert intent.operation == 'chat'
        assert intent.memory_key is None
        assert not intent.is_personal_fact()
    
    def test_unclear_message(self):
        """Unclear message defaults to chat."""
        intent = understand_tanglish('random stuff here')
        assert intent.sentence_type == 'unclear'
        assert intent.operation == 'chat'
        assert intent.confidence <= 0.7
    
    def test_language_style_tanglish(self):
        """Detect Tanglish language style."""
        intent = understand_tanglish('naa madurai la iruken')
        assert intent.language_style == 'tanglish'
    
    def test_original_message_preserved(self):
        """Original message preserved in intent."""
        msg = 'naa madurai la iruken'
        intent = understand_tanglish(msg)
        assert intent.original_message == msg


# ── Edge Cases & Regression Tests ────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and corner scenarios."""
    
    def test_mixed_case_input(self):
        """Mixed case input handled correctly."""
        intent1 = understand_tanglish('naa madurai la iruken')
        intent2 = understand_tanglish('NAA MADURAI LA IRUKEN')
        intent3 = understand_tanglish('Naa Madurai La Iruken')
        
        assert intent1.topic == intent2.topic == intent3.topic == 'location'
        assert intent1.memory_key == intent2.memory_key == intent3.memory_key
    
    def test_extra_punctuation(self):
        """Extra punctuation handled."""
        intent1 = understand_tanglish('naa madurai la iruken')
        intent2 = understand_tanglish('naa madurai la iruken!!!')
        intent3 = understand_tanglish('naa, madurai, la, iruken.')
        
        assert intent1.topic == intent2.topic == intent3.topic
    
    def test_question_and_recall_distinction(self):
        """Question vs. recall differ on 'nu sonnen' presence."""
        # Question: just question word
        intent_q = understand_tanglish('naa enga iruken?')
        assert intent_q.sentence_type == 'question'
        
        # Recall: has 'nu sonnen'
        intent_r = understand_tanglish('naa enga iruken nu sonnen')
        assert intent_r.sentence_type == 'recall'
    
    def test_empty_string(self):
        """Empty string handled gracefully."""
        intent = understand_tanglish('')
        assert intent.sentence_type == 'unclear'
        assert intent.operation == 'chat'
    
    def test_whitespace_only(self):
        """Whitespace-only string handled."""
        intent = understand_tanglish('   ')
        assert intent.sentence_type == 'unclear'
    
    def test_single_word(self):
        """Single-word inputs."""
        intent = understand_tanglish('vanakkam')
        assert intent.sentence_type == 'greeting'
    
    def test_school_vs_field_heuristic(self):
        """School detected when college keyword present."""
        # Without college keyword → field_of_study
        intent1 = understand_tanglish('naa cse padichen')
        assert intent1.topic == 'field_of_study'
        
        # With college keyword → school
        intent2 = understand_tanglish('naa klnce college la padichen')
        assert intent2.topic == 'school'
    
    def test_variant_question_words(self):
        """All question word variants recognized."""
        for qw in ['enna', 'ennu', 'enga', 'enge', 'yaaru', 'yaru']:
            intent = understand_tanglish(f'{qw}?')
            assert intent.sentence_type == 'question', f"Failed for {qw}"
    
    def test_typo_tolerance(self):
        """Common typos handled via normalization."""
        intent1 = understand_tanglish('na madurai la iruken')  # 'na' variant of 'naa'
        intent2 = understand_tanglish('naa madurai la iruken')  # standard
        
        assert intent1.topic == intent2.topic == 'location'
    
    def test_multiple_postpositions(self):
        """Handle multiple postposition variants."""
        for postp in ['la', 'ile', 'il']:
            intent = understand_tanglish(f'naa madurai {postp} iruken')
            assert intent.topic == 'location', f"Failed for {postp}"
    
    def test_confidence_ranges(self):
        """Confidence scores reasonable."""
        # High confidence: clear topic + entity
        intent1 = understand_tanglish('naa madurai la iruken')
        assert intent1.confidence > 0.7
        
        # Low confidence: unclear
        intent2 = understand_tanglish('random words')
        assert intent2.confidence <= 0.7
    
    def test_no_false_positives_on_english(self):
        """Pure English shouldn't trigger personal intent routing."""
        intent = understand_tanglish('hello how are you')
        assert intent.operation == 'chat'
        assert intent.memory_key is None


# ── Backward Compatibility Tests ─────────────────────────────────────────────

class TestBackwardCompatibility:
    """Ensure new module doesn't break existing chat_memory patterns."""
    
    def test_personal_fact_classification(self):
        """is_personal_fact() correctly identifies saveable facts."""
        # Personal facts
        for topic in ['name', 'location', 'school', 'field_of_study', 'learning',
                      'workplace', 'job', 'skill', 'goal', 'interest', 'language']:
            intent = understand_tanglish('test')
            intent.topic = topic
            assert intent.is_personal_fact()
        
        # Not personal
        intent = understand_tanglish('hello')
        intent.topic = None
        assert not intent.is_personal_fact()
    
    def test_intent_structure(self):
        """TanglishIntent has all expected fields."""
        intent = understand_tanglish('naa madurai la iruken')
        
        # All fields present
        assert hasattr(intent, 'sentence_type')
        assert hasattr(intent, 'topic')
        assert hasattr(intent, 'tense')
        assert hasattr(intent, 'operation')
        assert hasattr(intent, 'entities')
        assert hasattr(intent, 'memory_key')
        assert hasattr(intent, 'confidence')
        assert hasattr(intent, 'language_style')
        assert hasattr(intent, 'original_message')
        
        # Fields have correct types
        assert isinstance(intent.sentence_type, str)
        assert isinstance(intent.topic, (str, type(None)))
        assert isinstance(intent.tense, str)
        assert isinstance(intent.operation, str)
        assert isinstance(intent.entities, dict)
        assert isinstance(intent.memory_key, (str, type(None)))
        assert isinstance(intent.confidence, float)
        assert isinstance(intent.language_style, str)
        assert isinstance(intent.original_message, str)


# ── Performance & Stress Tests ───────────────────────────────────────────────

class TestPerformance:
    """Test performance on various input sizes."""
    
    def test_very_long_input(self):
        """Long input handled without error."""
        long_msg = 'naa madurai la iruken ' * 50
        intent = understand_tanglish(long_msg)
        assert intent.memory_key is not None
    
    def test_many_unknown_words(self):
        """Many unknown words don't crash."""
        msg = 'random word1 word2 word3 word4 word5 naa madurai la iruken'
        intent = understand_tanglish(msg)
        # Should still detect location since we have proper location pattern
        assert intent.topic == 'location'
    
    def test_special_characters(self):
        """Special characters handled."""
        msg = 'naa madurai @#$% la iruken'
        intent = understand_tanglish(msg)
        # Should still detect location despite special chars
        assert intent.topic == 'location'


# ── Integration Tests ───────────────────────────────────────────────────────

class TestIntegration:
    """Tests simulating real usage patterns."""
    
    def test_user_onboarding_sequence(self):
        """Simulate user providing multiple facts."""
        facts = [
            ('en peru sarandeep', 'name'),
            ('naa madurai la iruken', 'location'),
            ('naa cse padichen', 'field_of_study'),
        ]
        
        for msg, expected_topic in facts:
            intent = understand_tanglish(msg)
            assert intent.topic == expected_topic
            assert intent.operation == 'save'
            assert intent.entities.get('value') is not None
    
    def test_user_recall_sequence(self):
        """Simulate user recalling facts."""
        recalls = [
            ('naa enga iruken?', 'location'),
            ('naa enna padichen?', 'field_of_study'),
            ('en peru enna?', 'name'),
        ]
        
        for msg, expected_topic in recalls:
            intent = understand_tanglish(msg)
            assert intent.topic == expected_topic
            assert intent.operation == 'retrieve'
    
    def test_mixed_conversation(self):
        """Simulate mixed conversation with statements, questions, greetings."""
        sequence = [
            ('vanakkam', 'greeting', 'chat', None),
            ('naa madurai la iruken', 'statement', 'save', 'user_location'),
            ('naa enga iruken?', 'question', 'retrieve', 'user_location'),
            ('naa cse college la padichen', 'statement', 'save', 'user_school'),
        ]
        for msg, exp_type, exp_op, exp_key in sequence:
            intent = understand_tanglish(msg)
            assert intent.sentence_type == exp_type
            assert intent.operation == exp_op
            assert intent.memory_key == exp_key


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
