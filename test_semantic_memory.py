
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

# Load the local embedding model
model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    local_files_only=True,
)

# Store facts separately, with example questions for each fact
memories = {
    "user_name": {
        "value": "Sarandeep",
        "variants": [
            "என் பெயர் என்ன?",
            "En peyar enna?",
            "En peru enna?",
            "What is my name?",
        ],
    },
    "user_location": {
        "value": "Madurai",
        "variants": [
            "நான் எங்கே இருக்கிறேன்?",
            "Naan enga irukken?",
            "Naan enga irukken",
            "Where am I from?",
            "What is my location?",
        ],
    },
    "preferred_language": {
        "value": "Tamil and Tanglish",
        "variants": [
            "எனக்கு என்ன மொழி பிடிக்கும்?",
            "Enakku enna language pudikkum?",
            "What language do I prefer?",
        ],
    },
}

# Flatten the question variants and remember which fact each belongs to
all_variants = []
variant_keys = []

for key, memory in memories.items():
    for variant in memory["variants"]:
        all_variants.append(variant)
        variant_keys.append(key)

# Encode all variants once
variant_vectors = model.encode(all_variants)

# Basic intent patterns for Tamil and Tanglish
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
}


def detect_intent(question):
    q = question.lower().strip()

    for key, patterns in intent_patterns.items():
        if any(pattern in q for pattern in patterns):
            return key

    return None


questions = [
    "என் பெயர் என்ன?",
    "En peyar enna?",
    "Naan enga irukken?",
    "Where am I from?",
    "Enakku enna language pudikkum?",
    "Enakku pasikkuthu",
]


threshold = 0.55

for question in questions:
    intent = detect_intent(question)

    print(f"\nQuestion: {question}")

    if intent:
        print(f"Detected fact: {intent}")
        print(f"Answer: {memories[intent]['value']}")
        print("Method: Intent recognition")
    else:
        print("No reliable match found.")
