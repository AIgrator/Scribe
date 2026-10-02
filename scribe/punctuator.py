# punctuator.py
"""Offline punctuation and capitalization for final ASR results.

Pipeline (runs ONLY on final text, never on partials):
  1. neural punctuation, ONNX int8 (optional, Russian default) — marks ? ! . , : ...
  2. duplicate-punctuation cleanup (e.g. ".." -> ".", keeps "...")
  3. sentence-start capitalization (rules, stateful across finals)
  4. proper-noun capitalization via pymorphy2 (optional, Russian, works on lowercase)

All heavy dependencies (onnxruntime, tokenizers, pymorphy2) are optional imports.
If the model or a library is missing, the module gracefully degrades to rules only,
so the base install stays light ("core + plugins" approach from PLAN.md).
"""
import logging
import os
import re

logger = logging.getLogger(__name__)

_MARKS = {"B-!": "!", "B-,": ",", "B-.": ".", "B-...": "...", "B-:": ":", "B-?": "?", "O": ""}
_SENTENCE_END = (".", "!", "?", "...")
# First parts of multi-word geo names whose head alone has no proper tag ("санкт петербург").
_GEO_PREFIXES = {"санкт", "нью", "сан", "лос", "сен", "усть", "порт"}
_PROPER_TAGS = {"Name", "Surn", "Patr", "Geox"}
_PROPER_SCORE_MIN = 0.5

_morphs = {}

# Languages where a word after a comma must stay lowercase (proper nouns excepted).
_COMMA_LOWER_LANGS = ('ru', 'uk')
_WORD_RE = r'A-Za-zА-Яа-яЁёІіЇїЄєҐґ'


def _get_morph(lang='ru'):
    """Lazy singletons of pymorphy2 analyzers (Russian + Ukrainian).

    Note: Ukrainian dicts do not tag proper nouns, so for 'uk' the proper
    exception only catches names shared with Russian. Ukrainian vocatives
    ("Скажи, Марічко") are a known limitation, to be covered by the user
    dictionary later.
    """
    if lang not in ('ru', 'uk'):
        return None
    if lang not in _morphs:
        try:
            import pymorphy2
            if lang == 'ru':
                _morphs[lang] = pymorphy2.MorphAnalyzer()
            else:
                _morphs[lang] = pymorphy2.MorphAnalyzer(lang='uk')
        except Exception as e:
            logger.warning(f"[Punctuator] pymorphy2-{lang} unavailable: {e}")
            _morphs[lang] = False
    return _morphs[lang] or None


def _is_proper_top(word, morph):
    """True if the top pymorphy2 parse is a proper noun with decent score."""
    try:
        parses = morph.parse(word)
    except Exception:
        return False
    if not parses:
        return False
    top = parses[0]
    return top.score >= _PROPER_SCORE_MIN and any(t in top.tag for t in _PROPER_TAGS)


def _is_geo_head(word, morph):
    """True if word is most likely a geo name (for prefix/adj rules)."""
    try:
        parses = morph.parse(word)
    except Exception:
        return False
    if not parses:
        return False
    top = parses[0]
    return top.score >= _PROPER_SCORE_MIN and "Geox" in top.tag


class Punctuator:
    def __init__(self, settings_manager=None, model_dir=None, lang=None):
        self.settings_manager = settings_manager
        self.model_dir = model_dir  # resolved lazily
        self._lang = lang  # explicit override (tests, embeddings)
        self._session = None
        self._tokenizer = None
        self._id2mark = None
        self._loaded = False
        self._load_attempted = False

    @property
    def enabled(self):
        if self.settings_manager and hasattr(self.settings_manager, 'get'):
            try:
                return bool(self.settings_manager.get('enable_punctuation', True))
            except Exception:
                return True
        return True

    def _resolve_model_dir(self):
        if self.model_dir:
            return self.model_dir
        lang = self.lang
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Per-language folder: models/punct/<lang>/. Missing folder => rules-only mode.
        return os.path.join(base, 'models', 'punct', lang)

    @property
    def lang(self):
        if getattr(self, '_lang', None):
            return self._lang
        if self.settings_manager and hasattr(self.settings_manager, 'get'):
            try:
                custom = self.settings_manager.get('punctuation_model_dir', '')
                if custom and not self.model_dir:
                    self.model_dir = custom
                lang = self.settings_manager.get('language', 'ru') or 'ru'
                self._lang = lang
                return lang
            except Exception:
                pass
        if self.model_dir:
            base = os.path.basename(os.path.normpath(self.model_dir))
            # Only trust short codes ('ru', 'en', 'uk'); temp paths default to 'ru'.
            self._lang = base if len(base) == 2 else 'ru'
            return self._lang
        self._lang = 'ru'
        return 'ru'

    def _ensure_loaded(self):
        """Load ONNX session + tokenizer on first use. Returns True if neural path works."""
        if self._loaded:
            return True
        if self._load_attempted:
            return False
        self._load_attempted = True
        if not self.enabled:
            return False
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except Exception as e:
            logger.warning(f"[Punctuator] onnxruntime/tokenizers missing, rules-only mode: {e}")
            return False
        d = self._resolve_model_dir()
        onnx_path = os.path.join(d, 'model.int8.onnx')
        tok_path = os.path.join(d, 'tokenizer.json')
        if not (os.path.exists(onnx_path) and os.path.exists(tok_path)):
            alt = os.path.join(d, 'model.onnx')
            if os.path.exists(alt) and os.path.exists(tok_path):
                onnx_path = alt
            else:
                logger.warning(f"[Punctuator] model not found in {d}, rules-only mode")
                return False
        try:
            self._session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
            self._tokenizer = Tokenizer.from_file(tok_path)
            # Label decoding, see model.json sidecar. Two styles:
            #  - "after_each" (markusiko rubert ru): id -> mark appended after the word.
            #  - "this_word_case" (felflare bert en): "<mark><case>" per word, e.g.
            #    ".U" = period after + capitalize THIS word.
            self._style = "after_each"
            self._id2mark = {0: "!", 1: ",", 2: ".", 3: "...", 4: ":", 5: "?", 6: ""}
            try:
                import json as _json
                meta_path = os.path.join(d, 'model.json')
                if os.path.exists(meta_path):
                    with open(meta_path, encoding='utf-8') as f:
                        meta = _json.load(f)
                    self._style = meta.get('style', 'after_each')
                    id2label = meta.get('id2label')
                    if id2label:
                        if self._style == 'this_word_case':
                            self._id2mark = {int(k): v for k, v in id2label.items()}
                        else:
                            marks = meta.get('marks', {})
                            self._id2mark = {int(k): marks.get(v, "") for k, v in id2label.items()}
            except Exception as e:
                logger.warning(f"[Punctuator] bad model.json, using default labels: {e}")
            self._loaded = True
            logger.info(f"[Punctuator] neural model loaded from {d}")
            return True
        except Exception as e:
            logger.warning(f"[Punctuator] failed to load model, rules-only mode: {e}")
            return False

    def punctuate_neural(self, text):
        """Add punctuation marks with the neural model. Returns text unchanged on any failure."""
        if not text or not text.strip():
            return text
        if not self._ensure_loaded():
            return text
        try:
            import numpy as np
            words = text.split()
            enc = self._tokenizer.encode_batch([words], is_pretokenized=True)[0]
            ids = enc.ids
            word_ids = enc.word_ids
            if len(ids) > 250:  # model limit 256 with specials; truncate tail
                ids, word_ids = ids[:250], word_ids[:250]
            mask = [1] * len(ids)
            logits = self._session.run(
                ["logits"],
                {"input_ids": np.array([ids], dtype=np.int64),
                 "attention_mask": np.array([mask], dtype=np.int64)},
            )[0][0]
            out = []
            for i, w in enumerate(words):
                idxs = [j for j, wi in enumerate(word_ids) if wi == i]
                if not idxs:
                    out.append(w)
                    continue
                pred_id = int(logits[idxs[-1]].argmax())
                if getattr(self, '_style', 'after_each') == 'this_word_case':
                    lab = str(self._id2mark.get(pred_id, 'OO'))
                    ww = w.capitalize() if lab[-1:] == 'U' else w
                    if lab[:1] not in ('O', ''):
                        ww += lab[0]
                    out.append(ww)
                else:
                    out.append(w + self._id2mark.get(pred_id, ""))
            return " ".join(out)
        except Exception as e:
            logger.warning(f"[Punctuator] neural pass failed, keeping raw text: {e}")
            return text

    @staticmethod
    def cleanup_dupes(text):
        """Collapse accidental double marks, keep ellipsis. E.g. 'домой. .' handled by voice commands."""
        ph = "\ue000"
        text = text.replace("...", ph)
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',,+', ',', text)
        text = re.sub(r'\?\?+', '?', text)
        text = re.sub(r'!!+', '!', text)
        text = re.sub(r'::+', ':', text)
        text = re.sub(r';,+', ';', text)
        return text.replace(ph, "...")

    @staticmethod
    def capitalize_sentences(text, sentence_start):
        """Uppercase first letter of each sentence. Returns (text, next_sentence_start)."""
        if not text:
            return text, sentence_start
        chars = list(text)
        upper_next = sentence_start
        for i, ch in enumerate(chars):
            if ch.isalpha():
                if upper_next:
                    chars[i] = ch.upper()
                    upper_next = False
            elif ch in '.!?':
                # '...' is three dots; the loop naturally keeps upper_next True until alpha
                upper_next = True
        stripped = text.rstrip()
        # A final ending with . ! ? starts a new sentence => capitalize next.
        next_sentence_start = stripped.endswith(_SENTENCE_END)
        return "".join(chars), next_sentence_start

    @staticmethod
    def capitalize_proper(text, lang='ru'):
        """Uppercase likely proper nouns.

        Russian via pymorphy2 (works on lowercase); Ukrainian runs the same
        code but its dicts lack proper tags, so it only catches shared
        spellings — Ukrainian names are a known gap for now.
        """
        if lang not in ('ru', 'uk'):
            return text
        morph = _get_morph('ru')
        if morph is None or not text:
            return text
        words = text.split()
        # precompute geo-head flags
        is_geo = [_is_geo_head(re.sub(r'[,.!?:;...]+$', '', w).lower(), morph) for w in words]
        out = []
        for i, w in enumerate(words):
            m = re.match(r'^([^А-Яа-яЁёA-Za-z]*)([А-Яа-яЁёA-Za-z]+)(.*)$', w)
            if not m:
                out.append(w)
                continue
            pre, core, post = m.groups()
            low = core.lower()
            if core[0].isupper():
                out.append(w)
                continue
            cap = False
            if _is_proper_top(low, morph):
                cap = True
            elif low in _GEO_PREFIXES and i + 1 < len(words) and is_geo[i + 1]:
                cap = True  # "санкт петербург", "нью йорк"
            elif i + 1 < len(words) and is_geo[i + 1]:
                # adjective + geo: "нижний новгород" — only if word parses as adjective
                try:
                    cap = any('ADJF' in str(p.tag) for p in morph.parse(low)[:1])
                except Exception:
                    cap = False
            out.append(f"{pre}{core.capitalize()}{post}" if cap else w)
        return " ".join(out)

    def _looks_proper(self, word):
        """True if the word looks like a proper noun in ru/uk morphology."""
        low = word.lower()
        for lang in ('ru', 'uk'):
            morph = _get_morph(lang)
            if morph is not None and _is_proper_top(low, morph):
                return True
        return False

    def lowercase_after_comma_text(self, text):
        """Force lowercase right after a comma (ru/uk rule), except proper nouns.

        Safety net: no caps source should uppercase here (commas never start
        sentences), but cross-final state or voice commands can leak one through.
        """
        if self.lang not in _COMMA_LOWER_LANGS or not text:
            return text

        def _fix(m):
            pre, word = m.group(1), m.group(2)
            if not word[:1].isupper() or self._looks_proper(word):
                return m.group(0)
            return pre + word[0].lower() + word[1:]

        return re.sub(r',(\s+)([' + _WORD_RE + r']+)', _fix, text)

    def lowercase_after_comma_actions(self, actions):
        """Same as above for the action stream.

        Comma and word may sit in different fragments; keys in between
        are handled.
        """
        if self.lang not in _COMMA_LOWER_LANGS:
            return actions
        out = [dict(a) for a in actions]
        carry = False  # previous stream chunk ended with a comma
        for act in out:
            if act.get('type') == 'key':
                if act.get('value') in ('Enter', 'Backspace'):
                    carry = False
                continue
            v = self.lowercase_after_comma_text(act.get('value', ''))
            if carry:
                m = re.match(r'^(\s*)([' + _WORD_RE + r']+)', v)
                if m and m.group(2)[:1].isupper() and not self._looks_proper(m.group(2)):
                    w = m.group(2)
                    v = m.group(1) + w[0].lower() + w[1:] + v[m.end():]
            carry = bool(re.search(r',\s*$', v))
            act['value'] = v
        return out

    def process(self, text, sentence_start=True):
        """Full pipeline for one final chunk. Returns (text, next_sentence_start)."""
        if not text or not text.strip():
            return text, sentence_start
        if self.enabled:
            text = self.punctuate_neural(text)
            text = self.cleanup_dupes(text)
            text = self.capitalize_proper(text, self.lang)
        text, next_start = self.capitalize_sentences(text, sentence_start)
        text = self.lowercase_after_comma_text(text)
        return text, next_start

    def capitalize_actions(self, actions, sentence_start=True):
        """Capitalize text fragments inside replacement actions (keys untouched).

        Needed because voice commands (e.g. "точка" -> ".") insert sentence-final
        marks AFTER the neural pass. Enter forces a new sentence, other keys are neutral.
        Returns (new_actions, next_sentence_start).
        """
        upper_next = sentence_start
        new_actions = []
        for act in actions:
            if act.get('type') == 'key':
                if act.get('value') == 'Enter':
                    upper_next = True
                new_actions.append(dict(act))
                continue
            chars = list(act.get('value', ''))
            for i, ch in enumerate(chars):
                if ch.isalpha():
                    if upper_next:
                        chars[i] = ch.upper()
                        upper_next = False
                elif ch in '.!?':
                    upper_next = True
            new_actions.append({'type': 'text', 'value': "".join(chars)})
        # Next state from the tail of the whole stream: a sentence-final mark
        # means the next chunk starts a new sentence.
        tail = "".join(a.get('value', '') for a in new_actions if a.get('type') == 'text').rstrip()
        next_start = tail.endswith(_SENTENCE_END)
        new_actions = self.strip_punct_around_breaks(new_actions)
        new_actions = self.lowercase_after_comma_actions(new_actions)
        return new_actions, next_start

    @staticmethod
    def strip_punct_around_breaks(actions):
        r"""Post-replacement cleanup of the action stream.

        1. Orphan marks around line breaks: the neural pass may punctuate a command
           word ("новая строка" -> "строка,") that replacements then cut out,
           leaving "word,\n, next".
        2. Comma before an explicit mark: neural "домой," + spoken "точка" -> "."
           gives "домой,." — the explicit command wins, comma goes.
        """
        out = [dict(a) for a in actions]
        for i, act in enumerate(out):
            if act.get('type') == 'key' and act.get('value') == 'Enter':
                if i > 0 and out[i - 1].get('type') == 'text':
                    out[i - 1]['value'] = re.sub(r'[,.!?:;…]+$', '', out[i - 1]['value'])
                if i + 1 < len(out) and out[i + 1].get('type') == 'text':
                    out[i + 1]['value'] = re.sub(r'^[,.!?:;…]+', '', out[i + 1]['value'])
        # Boundary "mark + [Backspace] + mark": e.g. neural "домой, " + spoken
        # "точка" -> [Backspace]"." would give "домой,.". The Backspace only
        # eats the space, so drop the stale mark AND the now-purposeless key.
        # (If prev ends with a bare mark and no space, Backspace eats the mark
        # itself — nothing to do.)
        drop = set()
        for i, act in enumerate(out):
            if act.get('type') == 'key' and act.get('value') == 'Backspace':
                if 0 < i < len(out) - 1:
                    prev, nxt = out[i - 1], out[i + 1]
                    if prev.get('type') == 'text' and nxt.get('type') == 'text':
                        if (re.search(r'[,.!?:;…]\s+$', prev.get('value', ''))
                                and re.match(r'\s*[.!?…]', nxt.get('value', ''))):
                            prev['value'] = re.sub(r'[,.!?:;…]\s+$', '', prev['value'])
                            drop.add(i)
        out = [a for i, a in enumerate(out) if i not in drop]
        for act in out:
            if act.get('type') == 'text':
                act['value'] = Punctuator.cleanup_dupes(act['value'])
                act['value'] = re.sub(r',(\s*[.!?…])', r'\1', act['value'])
        return out
