"""Gplex+'s word filter: common swear words, slurs and hateful phrases, including the usual ways of
dressing them up - F.uck, f*ck, sh1t, $h!t, fuuuck, "f u c k", accented or Cyrillic look-alike letters,
fullwidth or fancy Unicode letters and invisible characters. Words that merely contain one (class,
Scunthorpe, cocktail, assassin...) are left alone.

The lists are kept ROT13-encoded so this file isn't a wall of slurs to read; decode them with
codecs.decode(word, "rot13"). To add a word, add its ROT13 form to the right list."""

import codecs
import re
import unicodedata

_R = lambda s: codecs.decode(s, "rot13")
# found anywhere inside a word
_ANY = [_R(x) for x in ['shpx', 'shx', 'spx', 'shd', 'sipx', 'cuhpx', 'fuvg', 'phag', 'ovgpu', 'nffubyr', 'nefrubyr', 'onfgneq', 'juber', 'fyhg', 'jnax', 'pbpxfhpx', 'qvpxurnq', 'wnpxnff', 'qhzonff', 'zbgures', 'avttre', 'avttn', 'avttnu', 'snttbg', 'sntbg', 'jrgonpx', 'enturnq', 'gbjryurnq', 'wvtnobb', 'cbepuzbaxrl', 'fnaqavtt', 'fcrnepuhpxre', 'xxx']]
# only as the whole word, or with these endings
_WORD = {_R(k): v.split() for k, v in {'nff': 'es', 'nefr': 's', 'qvpx': 's', 'pbpx': 's', 'chffl': '', 'chffvrf': '', 'cevpx': 's', 'cvff': 'ed es ing er', 'gjng': 's', 'obyybpxf': '', 'snt': 's', 'ergneq': 's ed', 'genaal': '', 'genaavrf': '', 'furznyr': 's', 'qlxr': 's', 'xvxr': 's', 'fcvp': 's', 'puvax': 's', 'tbbx': 's', 'ornare': 's', 'pbba': 's', 'cnxv': 's', 'xlf': ''}.items()}
# phrases (words in a row)
_PHRASES = [_R(x) for x in ['xvyy lbhefrys', 'xvyy hefrys', 'urvy uvgyre', 'fvrt urvy', 'juvgr cbjre', 'tnf gur wrjf', 'unat lbhefrys']]
# ordinary words with one of the above inside them
_ALLOW = ['shiitake', 'scunthorpe', 'cockpit', 'cocktail', 'peacock', 'hancock', 'dickens', 'dickinson', 'assassin', 'bassist', 'class', 'pass', 'grass', 'mass', 'brass', 'bass', 'glass', 'lass', 'sass', 'embarrass', 'harass', 'compass', 'cassette', 'assume', 'assess', 'asset', 'assign', 'assist', 'associate', 'assort', 'passion', 'massive', 'classic', 'wankel', 'therapist', 'spicy', 'spice', 'matsushita']

# look-alike letters: Cyrillic, Greek and others that pass for Latin ones
_HOMO = str.maketrans({
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "х": "x", "і": "i", "ї": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ц": "u", "ѵ": "v",
    "ɡ": "g", "ɑ": "a", "ı": "i", "ł": "l", "ø": "o", "đ": "d", "ð": "d", "þ": "p", "ß": "ss", "æ": "ae", "œ": "oe",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u",
    "χ": "x", "ϲ": "c", "ω": "w", "μ": "u",
})
# symbols used for letters (first choice; "1", "|" and "!" may also be an l)
_LEET = {"0": "o", "1": "i", "2": "z", "3": "e", "4": "a", "5": "s", "6": "g", "7": "t", "8": "b", "9": "g",
         "@": "a", "$": "s", "!": "i", "|": "i", "+": "t", "€": "e", "£": "l", "¢": "c", "©": "c", "®": "r",
         "(": "c", "<": "c", "{": "c", "[": "c", "#": "h"}
_ALT = {"1": "l", "|": "l", "!": "l"}
_WILD = set("*%_?")            # a letter left out on purpose: f*ck, sh%t
_INVIS = re.compile("[­͏؜ᅟᅠ឴឵᠎​-‏‪-‮⁠-⁯ㅤ︀-️﻿]")
_EDGE_L = "([{'\"`<"
_EDGE_R = ".,!?;:)]}'\"`>"


def _runs(word):
    # "fuck" -> f+u+c+k+ ; a doubled letter must stay doubled ("ass" -> a+s{2,}) so "as" isn't caught
    out, i = [], 0
    while i < len(word):
        j = i
        while j < len(word) and word[j] == word[i]:
            j += 1
        out.append(re.escape(word[i]) + ("+" if j - i == 1 else "{%d,}" % (j - i)))
        i = j
    return "".join(out)


_ANY_RE = re.compile("|".join(_runs(w) for w in sorted(_ANY, key=len, reverse=True)))
_WORD_RE = [re.compile("^" + _runs(w) + "(?:" + "|".join(re.escape(s) for s in ([""] + sfx)) + ")$") for w, sfx in _WORD.items()]
_PHRASE_RE = re.compile(r"(?:^| )(?:" + "|".join(" ".join(_runs(x) for x in p.split()) for p in _PHRASES) + r")(?: |$)")
_NUM_RE = re.compile(r"(?<!\d)14\s*[/\\.\- ]?\s*88(?!\d)")


def _fold(text):
    t = _INVIS.sub("", text)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.casefold().translate(_HOMO)


def _letters(tok, alt=False):
    """One word as plain letters: symbols read as letters, other marks dropped; None where a letter is left out."""
    tok = tok.lstrip(_EDGE_L).rstrip(_EDGE_R)
    out = []
    for ch in tok:
        if ch.isalpha():
            out.append(ch)
        elif alt and ch in _ALT:
            out.append(_ALT[ch])
        elif ch in _LEET:
            out.append(_LEET[ch])
        elif ch in _WILD:
            out.append("*")
    return "".join(out)


def _variants(w):
    if "*" not in w:
        return [w]
    # f*ck, sh*t: the left-out letter is usually a vowel
    return [w.replace("*", v) for v in "aeiou"] + [w.replace("*", "")]


def _word_bad(w):
    for v in _variants(w):
        if not v.isascii():
            continue
        # a match counts unless an ordinary word (shiitake, Scunthorpe...) covers it completely
        for m in _ANY_RE.finditer(v):
            covered = False
            for a in _ALLOW:
                k = v.find(a)
                while k >= 0:
                    if k <= m.start() and k + len(a) >= m.end():
                        covered = True
                        break
                    k = v.find(a, k + 1)
                if covered:
                    break
            if not covered:
                return True
        if any(r.match(v) for r in _WORD_RE):
            return True
    return False


def check(text):
    """True when text has a filtered word or phrase in it."""
    if not text:
        return False
    if _NUM_RE.search(text):
        return True
    t = _fold(text)
    for alt in (False, True):
        toks = [_letters(x, alt) for x in t.split()]
        toks = [x for x in toks if x]
        words = []
        i = 0
        while i < len(toks):
            # letters written apart: "f u c k", "f. u. c. k."
            j = i
            while j < len(toks) and len(toks[j]) == 1:
                j += 1
            if j - i >= 3:
                words.append("".join(toks[i:j]))
                i = j
                continue
            words.append(toks[i])
            i += 1
        for k, w in enumerate(words):
            if _word_bad(w):
                return True
            # a word broken in two: "fu ck" (only as an exact whole, so "is hit" stays fine)
            if k + 1 < len(words):
                pair = w + words[k + 1]
                if any(r.match(pair) for r in _WORD_RE) or (_ANY_RE.fullmatch(pair) and not any(a in pair for a in _ALLOW)):
                    return True
        if _PHRASE_RE.search(" ".join(words)):
            return True
    return False


# ---- links: new members can't share them for their first hours (see plus_views.link_wait) ----
_TLDS = ("com|net|org|info|biz|io|co|me|gg|xyz|app|dev|site|online|live|tv|cc|ly|be|to|us|uk|ca|au|de|fr|nl|ru|cn|in|jp|br|it|es|"
         "eu|tk|ml|ga|cf|gq|link|click|top|shop|store|vip|club|fun|icu|buzz|cam|lol|pw|ws|gl|im|is|sh|ai|so|st|vc|fm|am|gd|su|"
         "one|world|website|space|tech|pro|news|blog|page|zip|mov|win|bid|loan|work|party|rest|bar|cyou|sbs|cfd|today|life")
_URL_RE = re.compile(
    r"(?:\b[a-z][a-z0-9+.-]{1,15}://|\bwww\s*\.|"
    # name.tld or name.tld/path, the way addresses are written without http://
    r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:" + _TLDS + r")\b(?![.\-]?[a-z0-9])(?:[/?#:]|\s|$|[),.!?;'\"])|"
    # name dot com, name(.)com, name [.] com, name . com
    r"\b[a-z0-9][a-z0-9-]*\s*(?:\(\s*(?:\.|dot)\s*\)|\[\s*(?:\.|dot)\s*\]|\{\s*(?:\.|dot)\s*\}|\s(?:dot|\.)\s|\.\s+|\s+\.)\s*(?:" + _TLDS + r")\b)",
    re.I)


def has_link(text):
    """True when text has a web address in it (also written as "name dot com" and the like)."""
    if not text:
        return False
    t = _INVIS.sub("", unicodedata.normalize("NFKC", text))
    for m in _URL_RE.finditer(t + " "):
        # "the dot com bubble": an ordinary word before "dot com" isn't an address
        w = re.match(r"[a-z0-9-]+", m.group(0), re.I)
        if w and w.group(0).lower() in _NOT_NAMES and "." not in m.group(0)[:len(w.group(0)) + 1]:
            continue
        return True
    return False


_NOT_NAMES = {"the", "a", "an", "this", "that", "my", "your", "our", "their", "his", "her", "its", "of", "and", "or", "is", "was",
              "be", "to", "in", "on", "at", "for", "big", "old", "new", "first", "whole"}


# ---- names that pass for someone else's ----
_SKEL = str.maketrans({"0": "o", "1": "l", "i": "l", "|": "l", "!": "l", "j": "l", "3": "e", "4": "a", "@": "a", "5": "s", "$": "s",
                       "7": "t", "8": "b", "9": "g", "6": "g", "2": "z"})
_RESERVED = ("admin", "administrator", "moderator", "mod", "staff", "official", "gplex", "support", "system", "owner", "google")


def skeleton(s):
    """What a name looks like on screen, with the look-alikes made the same: Ziptino9098, ZIPTINO 9098,
    Zíptino9098, Zіptіno9098 (Cyrillic і), Zlptino9O98 and Zipptino9098 all come out alike."""
    t = _fold(s or "")
    t = "".join(ch for ch in t if ch.isalnum() or ch in "|!@$")
    t = t.translate(_SKEL)
    t = t.replace("rn", "m").replace("vv", "w").replace("cl", "d")
    return re.sub(r"(.)\1+", r"\1", t)


def reserved(s):
    """True when a name uses a word only staff names may (admin, moderator, official, Gplex...)."""
    words = [skeleton(w) for w in re.split(r"[\s_.\-]+", _fold(s or "")) if w]
    whole = skeleton(s)
    for r in _RESERVED:
        k = skeleton(r)
        prefix = r in _RESERVED_PREFIX
        if any(w == k or (prefix and w.startswith(k)) for w in words) or (prefix and whole.endswith(k)) or (r == "gplex" and k in whole):
            return True
    return False


# these also count at the start of a word or the end of a name run together (Admin123, TheAdmin)
_RESERVED_PREFIX = ("admin", "administrator", "moderator", "official", "gplex")
