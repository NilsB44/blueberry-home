"""Answer checking that is strict about meaning but forgiving about typing.

Verdicts:
  correct  exact match after normalising case, punctuation and spacing
  accent   right apart from accents (cafe vs café); counts, with a nudge
  typo     one letter off in one long word; counts, with a nudge
  wrong    anything else
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Verdict = Literal["correct", "accent", "typo", "wrong"]

_PUNCT = re.compile(r"[.,!?;:«»\"“”()…¿¡，。？！、：；（）《》]")
_SPACE = re.compile(r"\s+")

_EN_CONTRACTIONS = {
    "i'm": "i am",
    "you're": "you are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "we're": "we are",
    "they're": "they are",
    "that's": "that is",
    "what's": "what is",
    "there's": "there is",
    "don't": "do not",
    "doesn't": "does not",
    "isn't": "is not",
    "aren't": "are not",
    "can't": "cannot",
    "i'd": "i would",
    "i'll": "i will",
}


def normalize(text: str, lang: str = "fr") -> str:
    s = unicodedata.normalize("NFC", text).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("‐", "-")
    s = _PUNCT.sub(" ", s)
    s = s.replace("-", " ")
    # "j' ai" and "j'ai" should match; drop spaces after apostrophes.
    s = re.sub(r"'\s+", "'", s)
    s = _SPACE.sub(" ", s).strip()
    if lang == "en":
        s = " ".join(_EN_CONTRACTIONS.get(w, w) for w in s.split())
    return s


def strip_accents(text: str) -> str:
    text = text.replace("œ", "oe").replace("æ", "ae")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _distance_at_most_one(a: str, b: str) -> bool:
    """One insertion, deletion, substitution, or swap of two neighbouring letters."""
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 2 and diff[1] == diff[0] + 1:
            i, j = diff
            return a[i] == b[j] and a[j] == b[i]
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) == len(b):
            i += 1
        j += 1
    return edits + (len(b) - j) <= 1


def _one_typo(given: str, expected: str) -> bool:
    """Exactly one word differs, by one letter, and it's a long word.

    Short words are excluded on purpose: un/une, le/la, suis/suit are grammar, not typos.
    """
    g, e = given.split(), expected.split()
    if len(g) != len(e):
        return False
    diffs = [(a, b) for a, b in zip(g, e, strict=True) if a != b]
    return len(diffs) == 1 and len(diffs[0][1]) >= 5 and _distance_at_most_one(*diffs[0])


@dataclass
class Result:
    verdict: Verdict
    expected: str

    @property
    def correct(self) -> bool:
        return self.verdict != "wrong"


def grade(answer: str, accepted: list[str], lang: str = "fr") -> Result:
    """Grade `answer` against accepted answers written in `lang`."""
    given = normalize(answer, lang)
    best = accepted[0]
    if not given:
        return Result("wrong", best)
    normed = [normalize(a, lang) for a in accepted]
    if given in normed:
        return Result("correct", accepted[normed.index(given)])
    for original, n in zip(accepted, normed, strict=True):
        if strip_accents(given) == strip_accents(n):
            return Result("accent", original)
    for original, n in zip(accepted, normed, strict=True):
        if _one_typo(strip_accents(given), strip_accents(n)):
            return Result("typo", original)
    return Result("wrong", best)


# ---------- Chinese ----------

_TONED = {}
for base, marks in {
    "a": "āáǎà",
    "e": "ēéěè",
    "i": "īíǐì",
    "o": "ōóǒò",
    "u": "ūúǔù",
    "v": "ǖǘǚǜ",
}.items():
    for tone, ch in enumerate(marks, start=1):
        _TONED[ch] = (base, tone)
_TONED["ü"] = ("v", 0)


def pinyin_key(text: str) -> tuple[str, tuple[int, ...]] | None:
    """Split pinyin into (letters, tones) so "nǐ hǎo", "ni3 hao3" and "ni3hao3" compare equal.

    Tones may be marks or digits (5 or 0 for neutral, or nothing). Returns None if the text
    contains characters that aren't pinyin, e.g. hanzi.
    """
    s = normalize(text.lower().replace("u:", "v"))
    letters, tones = [], []
    for ch in s:
        if ch in _TONED:
            base, tone = _TONED[ch]
            letters.append(base)
            if tone:
                tones.append(tone)
        elif ch in "1234":
            tones.append(int(ch))
        elif ch in "05 '":
            continue
        elif "a" <= ch <= "z":
            letters.append(ch)
        else:
            return None
    return "".join(letters), tuple(tones)


def _hanzi(text: str) -> str:
    return normalize(text).replace(" ", "")


def grade_chinese(answer: str, hanzi: list[str], readings: list[str]) -> Result:
    """Accept characters, or pinyin with tones. Pinyin with wrong or missing tones counts as
    the "accent" verdict: right word, check your tones."""

    # Readings can outnumber the characters (tone-change variants like yí gè / yī gè);
    # extra readings belong to the last spelling.
    def show(i: int) -> str:
        h = hanzi[min(i, len(hanzi) - 1)]
        return f"{h} · {readings[i]}" if i < len(readings) else h

    if not normalize(answer):
        return Result("wrong", show(0))
    given = _hanzi(answer)
    for i, h in enumerate(hanzi):
        if given == _hanzi(h):
            return Result("correct", show(i))
    key = pinyin_key(answer)
    if key is None:
        return Result("wrong", show(0))
    keys = [pinyin_key(r) for r in readings]
    for i, k in enumerate(keys):
        if k == key:
            return Result("correct", show(i))
    for i, k in enumerate(keys):
        if k and k[0] == key[0]:
            return Result("accent", show(i))
    return Result("wrong", show(0))
