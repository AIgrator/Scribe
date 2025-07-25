#replacements.py
import re


def load_replacements(settings_manager, lang=None):
    """Loads replacements and flags from settings for the current language.

    Returns: (replacements, replacements_enabled, partial_replacements_enabled, lang).
    """
    replacements_enabled = True
    partial_replacements_enabled = True
    replacements = []
    _lang = lang or 'en'
    if settings_manager:
        settings = settings_manager.all() if hasattr(settings_manager, 'all') else {}
        _lang = settings.get('language', _lang)
        replacements_enabled = settings.get('enable_replacements', True)
        partial_replacements_enabled = settings.get('enable_partial_replacements', True)
        replacements = settings.get('replaces', {}).get(_lang, [])
    return replacements, replacements_enabled, partial_replacements_enabled, _lang



def parse_replace_string(replace):
    """Parses the replace string into a list of actions: plain text and special commands in [square brackets].

    Returns a list: [{'type': 'text', 'value': ...}, {'type': 'key', 'value': ...}, ...]
    Example: 'abc[Backspace][Enter]d' -> [text 'abc', key 'Backspace', key 'Enter', text 'd']
    Only allowed special commands: Space, Backspace, Tab, Enter
    Others are ignored.
    """
    allowed_keys = {'Space', 'Backspace', 'Tab', 'Enter'}
    actions = []
    # New pattern: special command in square brackets, does NOT capture punctuation after the bracket
    # Example: '[Backspace].' -> key: Backspace, text: '.'
    pattern = re.compile(r'\[(.*?)\]')
    pos = 0
    for m in pattern.finditer(replace):
        if m.start() > pos:
            # Plain text between commands
            actions.append({'type': 'text', 'value': replace[pos:m.start()]})
        cmd = m.group(1).strip()
        if cmd in allowed_keys:
            actions.append({'type': 'key', 'value': cmd})
        pos = m.end()
    if pos < len(replace):
        actions.append({'type': 'text', 'value': replace[pos:]})
    # Additionally: split text fragments if they start with punctuation after a special command
    # Example: [{'type': 'key', ...}, {'type': 'text', 'value': '. '}] -> key, text '.', text ' '
    final_actions = []
    for act in actions:
        if act['type'] == 'text' and act['value']:
            # Split into groups: punctuation + the rest of the text
            parts = re.findall(r'[^\w\s]+|[\w\s]+', act['value'])
            for part in parts:
                if part:
                    final_actions.append({'type': 'text', 'value': part})
        else:
            final_actions.append(act)
    return final_actions



def apply_replacements_actions(text, replacements):
    """Applies replacements to the text and returns a list of actions (text/key) for the entire result.

    Supports phrase replacements (multiple consecutive words).
    Each replacement is parsed into actions via parse_replace_string.
    """
    # Sort replacements by descending length of 'find' (so longer phrases are replaced first)
    sorted_replacements = sorted(
        [item for item in replacements if item.get('find')],
        key=lambda x: len(x['find']), reverse=True
    )
    # Prepare pattern for searching all phrases (escape special characters)
    def escape_phrase(phrase):
        # Remove extra spaces and escape
        return re.escape(phrase.strip())
    # For all replacements — only at word boundaries (\b...\b), so partial matches don't trigger
    patterns = []
    for item in sorted_replacements:
        find = item['find']
        # If find is not empty
        if find:
            # Word boundaries at the edges (works for phrases and single words)
            pat = re.compile(r'(?i)\b' + escape_phrase(find) + r'\b')
            patterns.append((item, pat))
    # Main loop: search and replace all phrases
    pos = 0
    actions = []
    text_len = len(text)
    while pos < text_len:
        match = None
        matched_item = None
        for item, pat in patterns:
            m = pat.match(text, pos)
            if m:
                if (not match) or (m.end() - m.start() > match.end() - match.start()):
                    match = m
                    matched_item = item
        if match:
            # Add replacement (parse special commands)
            replace = matched_item.get('replace', '')
            actions.extend(parse_replace_string(replace))
            pos = match.end()
        else:
            # No match — add current character as text
            actions.append({'type': 'text', 'value': text[pos]})
            pos += 1
    # Merge consecutive text actions
    final_actions = []
    for act in actions:
        if final_actions and act['type'] == 'text' and final_actions[-1]['type'] == 'text':
            final_actions[-1]['value'] += act['value']
        else:
            final_actions.append(act)
    return final_actions

# For backward compatibility: the old function returns a string
def apply_replacements(text, replacements):
    """Applies replacements to the text only by individual words (word boundaries).

    Returns the final text (with special commands as text).
    """
    actions = apply_replacements_actions(text, replacements)
    # Merge all actions back into a string (special commands as [Key])
    out = ''
    for act in actions:
        if act['type'] == 'text':
            out += act['value']
        elif act['type'] == 'key':
            out += f'[{act["value"]}]'
    return out
