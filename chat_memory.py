from memory_db import (
    initialize_database,
    get_memory,
    save_memory,
)

initialize_database()

intent_patterns = {
    "user_name": [
        "என் பெயர் என்ன",
        "என்னுடைய பெயர் என்ன",
        "en peyar enna",
        "ennoda peyar enna",
        "en peru enna",
        "ennoda peru enna",
        "what is my name",
        "what's my name",
        "whats my name",
    ],
    "user_location": [
        "நான் எங்கே இருக்கிறேன்",
        "naan enga irukken",
        "naan enga iruken",
        "naan enga irukkiren",
        "where am i from",
        "what is my location",
    ],
    "preferred_language": [
        "எனக்கு என்ன மொழி பிடிக்கும்",
        "enakku enna language pudikkum",
        "what language do i prefer",
    ],
    "favorite_colour": [
        "en favourite colour enna",
        "my favourite colour",
        "what is my favourite colour",
        "what's my favourite colour",
        "எனக்கு பிடித்த நிறம் என்ன",
        "எனக்கு பிடித்த வண்ணம் என்ன",
    ],
}


def detect_intent(question):
    q = question.lower().strip()

    for key, patterns in intent_patterns.items():
        if any(pattern in q for pattern in patterns):
            return key

    return None


def detect_language_style(question):
    # If Tamil script is present, reply in Tamil script
    if any("\u0B80" <= char <= "\u0BFF" for char in question):
        return "tamil"

    q = question.lower()

    # Basic Tanglish indicators
    tanglish_words = [
        "enna", "en", "naan", "neenga", "enga",
        "irukken", "iruken", "pudikkum", "peru",
    ]

    if any(word in q.split() for word in tanglish_words):
        return "tanglish"

    return "english"



def learn_fact(message):
    q = message.lower().strip()

    # Ignore questions; they should retrieve facts, not save them.
    if q.endswith("?") or " enna" in q:
        return None

    patterns = [
        "en favourite colour ",
        "my favourite colour is ",
    ]

    for pattern in patterns:
        if q.startswith(pattern):
            colour = message[len(pattern):].strip().rstrip(".!?")

            # Don't save an empty value or a question word.
            if not colour:
                return None

            if colour.lower() in {"enna", "what", "unknown"}:
                return None

            colour_translations = {
                "blue": "நீலம்",
                "red": "சிவப்பு",
                "green": "பச்சை",
                "yellow": "மஞ்சள்",
                "black": "கருப்பு",
                "white": "வெள்ளை",
            }

            tamil_colour = colour_translations.get(colour.lower())

            save_memory("favorite_colour", colour, tamil_colour)

            return (
                f"சரி! உங்கள் விருப்பமான நிறம் {colour} "
                "என்று நினைவில் வைத்துக்கொள்கிறேன்."
            )

    return None




def answer_question(question):
    # First, check whether this message teaches us a new fact.
    learned_response = learn_fact(question)

    if learned_response:
        return learned_response

    # Otherwise, treat it as a question.
    intent = detect_intent(question)

    if intent is None:
        return "இந்தக் கேள்விக்கான பதில் இன்னும் எனக்குத் தெரியாது."

    style = detect_language_style(question)
    value = get_memory(intent, language=style)

    if value is None:
        return "இந்தத் தகவல் இன்னும் சேமிக்கப்படவில்லை."

    if intent == "user_name":
        responses = {
            "tamil": f"உங்கள் பெயர் {value}.",
            "tanglish": f"Unga peyar {value}.",
            "english": f"Your name is {value}.",
        }

    elif intent == "user_location":
        responses = {
            "tamil": f"நீங்கள் {value} பகுதியில் இருக்கிறீர்கள்.",
            "tanglish": f"Neenga {value} la irukkeenga.",
            "english": f"You are in {value}.",
        }

    elif intent == "preferred_language":
        responses = {
            "tamil": f"உங்களுக்கு {value} மொழிகள் பிடிக்கும்.",
            "tanglish": f"Ungalukku {value} pudikkum.",
            "english": f"Your preferred languages are {value}.",
        }

    elif intent == "favorite_colour":
        responses = {
            "tamil": f"உங்கள் விருப்பமான நிறம் {value}.",
            "tanglish": f"Unga favourite colour {value}.",
            "english": f"Your favourite colour is {value}.",
        }

    return responses[style]




if __name__ == "__main__":
    test_questions = [
        "En favourite colour blue.",
        "En favourite colour enna?",
        "எனக்கு பிடித்த நிறம் என்ன?",
        "What is my favourite colour?",
    ]

    for question in test_questions:
        print(f"\nYou: {question}")
        print(f"Assistant: {answer_question(question)}")
