"""
Hook System — emotionally engaging hook texts for QuranYT Shorts.
Each hook is shown for the first ~2 seconds of the video as a strong opener.
"""

from variation_engine import load_history, pick_unique, record, save_history

HOOKS = [
    "When life gets hard… remember this",
    "Read this when you feel overwhelmed",
    "Allah says something powerful here",
    "This will calm your heart",
    "You need to hear this today",
    "A promise from Allah to you",
    "When you feel lost… read this",
    "Let this heal your heart",
    "Allah hasn't forgotten you",
    "This is your sign to keep going",
    "When hope feels far away…",
    "Your heart needs this right now",
    "A verse for the broken-hearted",
    "Read this and feel the peace",
    "Allah's words of comfort",
    "A reminder you need today",
    "Listen with your heart",
    "These words will stay with you",
]

HOOK_MEMORY = 10  # no repeat within last 10 videos


def get_hook(history=None):
    """
    Select a hook that hasn't been used in the last HOOK_MEMORY videos.
    Returns (hook_text, updated_history).
    """
    if history is None:
        history = load_history()

    hook = pick_unique(HOOKS, "hooks", memory=HOOK_MEMORY, history=history)
    record(history, "hooks", hook, memory=HOOK_MEMORY)
    return hook, history
