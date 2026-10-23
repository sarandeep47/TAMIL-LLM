
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

# Load the embedding model locally
model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    local_files_only=True,
)

# One fact stored in three language forms
memory = {
    "fact": "My name is Sarandeep.",
    "variants": [
        "என் பெயர் Sarandeep.",
        "En peyar Sarandeep.",
        "My name is Sarandeep.",
    ],
}

# Test questions
questions = [
    "என் பெயர் என்ன?",
    "En peyar enna?",
    "Enakku pasikkuthu",
    "What is my name?",
]

# Encode memory variants once
memory_vectors = model.encode(memory["variants"])
threshold = 0.55


def asks_for_name(question):
    q = question.lower().strip()

    patterns = [
        # Tamil
        "என் பெயர் என்ன",
        "என்னுடைய பெயர் என்ன",

        # Tanglish
        "en peyar enna",
        "ennoda peyar enna",
        "en peru enna",
        "ennoda peru enna",

        # English
        "what is my name",
        "what's my name",
        "whats my name",
    ]

    return any(pattern in q for pattern in patterns)


for question in questions:
    query_vector = model.encode(question)
    scores = cos_sim(query_vector, memory_vectors)[0]

    best_index = scores.argmax().item()
    score = scores[best_index].item()

    print(f"\nQuestion: {question}")
    print(f"Similarity: {score:.3f}")

    if asks_for_name(question):
        print(f"Retrieved fact: {memory['fact']}")
        print("Match method: Name intent")

    elif score >= threshold:
        print(f"Retrieved fact: {memory['fact']}")
        print("Match method: Semantic similarity")

    else:
        print("No reliable match found.")
