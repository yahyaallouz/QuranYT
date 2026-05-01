"""
Variation Engine — anti-repetition system for QuranYT.
Tracks hooks, backgrounds, descriptions, queries, and posting times
to ensure no two consecutive videos look or feel identical.
"""

import os
import json
import random
import time

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(DATA_DIR, "data", "variation_history.json")

BG_QUERIES = [
    "ocean", "sky", "forest", "sunset", "clouds",
    "rain", "mountains", "river", "night sky",
    "desert dunes", "waterfall", "calm lake",
]

_DEFAULT_HISTORY = {
    "hooks": [],
    "backgrounds": [],
    "bg_queries": [],
    "descriptions": [],
    "last_post_timestamp": 0,
}


def load_history():
    """Load variation history from disk."""
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure all keys exist (forward compat)
            for k, v in _DEFAULT_HISTORY.items():
                data.setdefault(k, v if not isinstance(v, list) else [])
            return data
        except (json.JSONDecodeError, Exception):
            pass
    return {k: (list(v) if isinstance(v, list) else v) for k, v in _DEFAULT_HISTORY.items()}


def save_history(history):
    """Persist variation history to disk."""
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def pick_unique(pool, history_key, memory=10, history=None):
    """
    Pick a random item from *pool* that has not appeared in the last
    *memory* entries of history[history_key].
    Returns the chosen item (caller should append to history and save).
    """
    if history is None:
        history = load_history()

    recent = history.get(history_key, [])[-memory:]
    candidates = [item for item in pool if item not in recent]
    if not candidates:
        candidates = pool  # all exhausted — allow any

    return random.choice(candidates)


def record(history, key, value, memory=20):
    """Append *value* to history[key], trimming to last *memory* entries."""
    lst = history.setdefault(key, [])
    lst.append(value)
    history[key] = lst[-memory:]


def pick_background_query(history=None, memory=20):
    """Select a background search query avoiding recent ones."""
    if history is None:
        history = load_history()
    return pick_unique(BG_QUERIES, "bg_queries", memory=memory, history=history)


def get_subtitle_offset():
    """Return a small random vertical offset (±20 px) for subtitle placement."""
    return random.randint(-20, 20)


def get_ken_burns_params():
    """
    Return Ken Burns zoom parameters.
    - zoom_start / zoom_end: between 1.02 and 1.08
    - direction: 'in' (1.0→zoom) or 'out' (zoom→1.0)
    """
    magnitude = round(random.uniform(1.02, 1.08), 3)
    direction = random.choice(["in", "out"])
    if direction == "in":
        return {"zoom_start": 1.0, "zoom_end": magnitude, "direction": direction}
    else:
        return {"zoom_start": magnitude, "zoom_end": 1.0, "direction": direction}


def get_last_post_time(history=None):
    """Return the Unix timestamp of the last successful upload."""
    if history is None:
        history = load_history()
    return history.get("last_post_timestamp", 0)


def hours_since_last_post(history=None):
    """How many hours since the last successful upload."""
    ts = get_last_post_time(history)
    if ts == 0:
        return 999  # never posted — treat as very old
    return (time.time() - ts) / 3600


def record_post_time(history=None):
    """Record the current time as the last post timestamp."""
    if history is None:
        history = load_history()
    history["last_post_timestamp"] = time.time()
    return history
