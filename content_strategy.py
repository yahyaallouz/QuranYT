"""
Content Strategy — generates human-feeling titles, descriptions, and hashtags.
Ensures no two videos share the same title/description patterns.
"""

import random
from variation_engine import load_history, pick_unique, record

# ────────────────────────────────────────────────────────────────────────────
#  TITLE GENERATION
# ────────────────────────────────────────────────────────────────────────────

TITLE_PATTERNS = [
    "{hook} | Surah {surah_name} {surah_num}:{ayah_range}",
    "{hook} | Qur'an {surah_num}:{ayah_range}",
    "{hook} | {surah_num}:{ayah_range}",
]

MAX_TITLE_LENGTH = 65


def generate_title(hook, surah_name, surah_num, ayah_range):
    """
    Build a dynamic, human-feeling title (no hashtags, ≤65 chars).
    Falls back to shorter patterns if the first choice is too long.
    """
    random.shuffle(TITLE_PATTERNS)
    for pattern in TITLE_PATTERNS:
        title = pattern.format(
            hook=hook,
            surah_name=surah_name,
            surah_num=surah_num,
            ayah_range=ayah_range,
        )
        if len(title) <= MAX_TITLE_LENGTH:
            return title

    # Ultimate fallback — truncate hook
    short_hook = hook[:30] + "…" if len(hook) > 30 else hook
    return f"{short_hook} | {surah_num}:{ayah_range}"


# ────────────────────────────────────────────────────────────────────────────
#  DESCRIPTION GENERATION
# ────────────────────────────────────────────────────────────────────────────

_LINE1_POOL = [
    "A reminder that {theme}.",
    "Let this verse bring you peace.",
    "Reflect on this beautiful ayah.",
    "May these words soften your heart.",
    "A moment of calm from the Qur'an.",
    "Words your soul needs today.",
    "Take a moment and reflect.",
    "This verse carries deep meaning.",
    "Let Allah's words guide you.",
    "A verse to carry in your heart.",
    "Feel the peace in these words.",
    "Your heart was meant to hear this.",
    "Pause and let this sink in.",
    "Close your eyes and listen.",
    "This ayah is a gentle reminder.",
]

_LINE2_POOL = [
    "Reflect on this today.",
    "Share this with someone who needs it.",
    "Save this for when you need peace.",
    "Let it stay with you.",
    "Carry these words with you.",
    "Come back to this whenever you need to.",
    "Take this reminder with you today.",
    "Let these words be your comfort.",
]

# Synonym swap pairs for slight wording randomness
_SYNONYMS = [
    ("heart", "soul"),
    ("peace", "tranquility"),
    ("remember", "reflect on"),
    ("beautiful", "profound"),
    ("calm", "serenity"),
    ("words", "message"),
    ("reminder", "reflection"),
]

MANDATORY_HASHTAGS = ["#shorts", "#quran", "#islam"]
ROTATING_HASHTAGS = ["#reminder", "#allah", "#deen", "#muslim", "#peace", "#faith"]

DESC_MEMORY = 18  # no identical description reuse in last 18 videos


def _apply_synonym_swap(text):
    """Randomly swap one synonym pair to add subtle wording variation."""
    pair = random.choice(_SYNONYMS)
    if random.random() < 0.4 and pair[0] in text.lower():
        # Case-insensitive replacement of first occurrence
        idx = text.lower().find(pair[0])
        if idx >= 0:
            original = text[idx:idx + len(pair[0])]
            # Preserve original casing for first char
            replacement = pair[1]
            if original[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            text = text[:idx] + replacement + text[idx + len(pair[0]):]
    return text


def generate_description(translation, ref_text, history=None):
    """
    Generate a unique, human-feeling description.
    Returns (description_text, updated_history).
    """
    if history is None:
        history = load_history()

    # Pick a theme snippet from translation (first clause, short)
    theme = translation.split(",")[0].split(".")[0].strip().lower()
    if len(theme) > 50:
        theme = theme[:47] + "..."

    line1 = pick_unique(_LINE1_POOL, "descriptions", memory=DESC_MEMORY, history=history)
    line1 = line1.format(theme=theme) if "{theme}" in line1 else line1
    line1 = _apply_synonym_swap(line1)
    record(history, "descriptions", line1, memory=DESC_MEMORY)

    line2 = random.choice(_LINE2_POOL)
    line2 = _apply_synonym_swap(line2)

    # Hashtags: mandatory + 1-2 rotating
    rotating = random.sample(ROTATING_HASHTAGS, k=random.randint(1, 2))
    hashtags = " ".join(MANDATORY_HASHTAGS + rotating)

    desc = f"{line1}\n{line2}\n\n{hashtags}"
    return desc, history


# ────────────────────────────────────────────────────────────────────────────
#  EXPLANATION TEXT (12-15 emotional words)
# ────────────────────────────────────────────────────────────────────────────

_EXPLANATION_PREFIXES = [
    "A reminder that",
    "Subhan'Allah —",
    "Reflect on this:",
    "A beautiful reminder:",
    "Allah tells us:",
    "A gentle reminder —",
    "May this bring you peace:",
    "Let this touch your heart:",
]


def make_short_explanation(translation):
    """
    Create a 12-15 word emotional explanation from the translation.
    Truncates at a natural clause boundary.
    """
    prefix = random.choice(_EXPLANATION_PREFIXES)

    # Extract first meaningful clause from translation
    # Split on sentence/clause delimiters
    for delim in [".", ",", ";", " - ", " – "]:
        parts = translation.split(delim)
        if len(parts) > 1:
            clause = parts[0].strip()
            if 3 <= len(clause.split()) <= 12:
                break
    else:
        clause = translation

    # Truncate to fit within 12-15 words total (prefix + clause)
    prefix_words = prefix.split()
    max_clause_words = 15 - len(prefix_words)
    clause_words = clause.split()[:max_clause_words]
    clause = " ".join(clause_words)

    # Clean up trailing punctuation
    clause = clause.rstrip(".,;:!? ")

    result = f"{prefix} {clause}."
    return result
