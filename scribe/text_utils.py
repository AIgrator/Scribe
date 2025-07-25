#text_utils.py
import difflib
import re


def normalize_text(s):
    """Convert to lowercase, remove extra spaces, and trim spaces at the edges."""
    return re.sub(r'\s+', ' ', s).strip().lower()

def fuzzy_match(trigger, text, threshold=0.9):
    """Returns True if trigger is sufficiently similar to any fragment of text (fuzzy matching)."""
    if not trigger:
        return False
    words = text.split()
    t_words = trigger.split()
    n = len(t_words)
    for i in range(len(words) - n + 1):
        candidate = ' '.join(words[i:i+n])
        ratio = difflib.SequenceMatcher(None, trigger, candidate).ratio()
        if ratio >= threshold:
            return True
    # Also check for substring inclusion (for short commands)
    if trigger in text:
        return True
    return False
