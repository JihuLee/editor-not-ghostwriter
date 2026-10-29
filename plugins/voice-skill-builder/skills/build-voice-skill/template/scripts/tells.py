#!/usr/bin/env python3
"""Measurements and author-relative rules shared by style_profile.py, ai_tell_lint.py and
diff_guard.py. The word lists live in lexicon_en.py; the author's own baseline lives in
author_profile.json. Standard library only.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter

import lexicon_en as LEX

EM_DASH = "—"
EN_DASH = "–"

TIER_A = {k: re.compile(v, re.I) for k, v in LEX.TIER_A.items()}
TIER_B = {k: re.compile(v, re.I) for k, v in LEX.TIER_B.items()}
AI_OPENERS = list(LEX.AI_OPENERS)
CONNECTIVES = sorted(set(LEX.CONNECTIVES), key=len, reverse=True)
SUMMARY_CLOSER_RE = re.compile(LEX.SUMMARY_CLOSER, re.I)
HEDGE_RE = re.compile(LEX.HEDGE, re.I)
INTENSIFIER_RE = re.compile(LEX.INTENSIFIER, re.I)
CONTRACTION_RE = re.compile(LEX.CONTRACTION, re.I)
PASSIVE_RE = re.compile(LEX.PASSIVE, re.I)
TRIAD_RE = re.compile(LEX.TRIAD)
WE_RE = re.compile(LEX.FIRST_PERSON, re.I)
FUNCTION_WORDS = list(dict.fromkeys(LEX.FUNCTION_WORDS))

# A device is a hard rule for an author whose samples use it less often than this
# (occurrences per 1,000 words). Above it, the device is judged by rate instead.
DEVICE_THRESHOLDS = {"em_dash": 0.3, "contraction": 0.2, "exclamation": 0.1}
# A tier-A word the author's samples use at least this many times is treated as tier B.
TIER_A_OWN_USE = 2
# A tier-B word the author uses at least this often (per 1,000 words) is part of their voice:
# the guard does not warn when an edit adds it. Same for openers (per 100 sentences).
OWN_SOFT_RATE = 0.5
OWN_OPENER_RATE = 0.5


# --------------------------------------------------------------------------- counting


def count_patterns(text: str, patterns: dict) -> Counter:
    c = Counter()
    for k, rx in patterns.items():
        n = len(rx.findall(text))
        if n:
            c[k] += n
    return c


def count_tier(text: str, tier) -> Counter:
    if isinstance(tier, dict):
        return count_patterns(text, tier)
    return count_patterns(text, TIER_A if tier == "A" else TIER_B)


def structural_counts(text: str) -> Counter:
    c = Counter()
    c["em_dash"] = text.count(EM_DASH)
    c["spaced_en_dash"] = text.count(f" {EN_DASH} ")
    c["spaced_hyphen_dash"] = len(re.findall(r"(?<=\w) - (?=\w)", text))
    c["semicolon"] = text.count(";")
    c["colon"] = text.count(":")
    c["question"] = text.count("?")
    c["exclamation"] = text.count("!")
    c["contraction"] = len(CONTRACTION_RE.findall(text))
    c["parenthesis"] = text.count("(")
    c["eg_ie"] = len(re.findall(r"\b(?:e\.g\.|i\.e\.)", text))
    c["hedge"] = len(HEDGE_RE.findall(text))
    c["intensifier"] = len(INTENSIFIER_RE.findall(text))
    c["triad"] = len(TRIAD_RE.findall(text))
    c["we"] = len(WE_RE.findall(text))
    return c


def dashes(c: Counter) -> int:
    """Em dashes plus spaced en dashes (both read as the 'LLM dash')."""
    return c["em_dash"] + c["spaced_en_dash"]


def opener(sentence_text: str, n: int = 2) -> str:
    w = re.findall(r"[A-Za-z][A-Za-z'\-]*", sentence_text)
    return " ".join(w[:n]).lower()


def _starts_with(low: str, phrase: str) -> bool:
    return low.startswith(phrase + ",") or low.startswith(phrase + " ")


def ai_opener(sentence_text: str):
    low = sentence_text.lower()
    for o in AI_OPENERS:
        if _starts_with(low, o):
            return o
    return None


def connective(sentence_text: str):
    low = sentence_text.lower()
    for c in CONNECTIVES:
        if _starts_with(low, c):
            return c
    return None


def find_tells(text: str, patterns: dict) -> list:
    """[(label, offset)] for every match of every pattern."""
    out = []
    for k, rx in patterns.items():
        out.extend((k, m.start()) for m in rx.finditer(text))
    return sorted(out, key=lambda x: x[1])


DASH_RE = re.compile(EM_DASH + "| " + EN_DASH + " ")
EXCLAMATION_RE = re.compile(r"!")


def is_summary_closer(sentence_text: str) -> bool:
    return bool(SUMMARY_CLOSER_RE.match(sentence_text.strip()))


def rate(count: float, n_words: int) -> float:
    """occurrences per 1,000 words"""
    return 1000.0 * count / max(1, n_words)


def cv(xs) -> float:
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    m = statistics.mean(xs)
    return statistics.pstdev(xs) / m if m else 0.0


def quantile(xs, q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# --------------------------------------------------------------------------- author watchlist


def compile_watchlist(entries) -> list:
    """entries: [{"match": "allows to", "fix": "...", "regex": false}, ...] -> [(regex, fix, label)]

    Every entry matches whole words only, case-insensitively; with "regex": true the match is a
    Python regular expression, still wrapped in word boundaries.
    """
    out = []
    for e in entries or []:
        body = e["match"] if e.get("regex") else re.escape(e["match"])
        pat = r"(?<!\w)(?:" + body + r")(?!\w)"
        out.append((re.compile(pat, re.I), e.get("fix", ""), e.get("label") or e["match"]))
    return out


def watchlist_matches(text: str, compiled) -> list:
    """[(matched_text, fix, offset)] in text order."""
    out = []
    for rx, fix, _ in compiled or []:
        out.extend((m.group(0), fix, m.start()) for m in rx.finditer(text))
    return sorted(out, key=lambda x: x[2])


def watchlist_hits(text: str, compiled) -> list:
    """[(matched_text, fix)]"""
    hits = []
    for rx, fix, _ in compiled or []:
        for m in rx.finditer(text):
            hits.append((m.group(0), fix))
    return hits


# --------------------------------------------------------------------------- author-relative rules


class Rules:
    """What counts as a hard tell for this author, derived from their profile."""

    def __init__(self, profile=None):
        self.profile = profile or {}
        config = self.profile.get("config") or {}
        self.allow = {str(w).lower() for w in config.get("allow", [])}
        counts_a = (self.profile.get("counts") or {}).get("tierA", {})
        own = {k for k, v in counts_a.items() if v >= TIER_A_OWN_USE}
        self.tier_a_hard = {k: rx for k, rx in TIER_A.items() if k not in own and k not in self.allow}
        self.tier_soft = {k: rx for k, rx in TIER_B.items() if k not in self.allow}
        self.tier_soft.update({k: rx for k, rx in TIER_A.items() if k in own and k not in self.allow})
        n_words = self.profile.get("n_words") or 0
        soft_rates = dict((self.profile.get("rates_per_1k") or {}).get("tierB", {}))
        for k in own:
            soft_rates[k] = 1000.0 * counts_a.get(k, 0) / max(1, n_words)
        self.soft_rates = soft_rates
        self.own_soft = {k for k, r in soft_rates.items() if r >= OWN_SOFT_RATE}
        opener_rates = self.profile.get("ai_openers_per_100_sentences") or {}
        self.avoid_openers = [o for o in AI_OPENERS
                              if opener_rates.get(o, 0.0) < OWN_OPENER_RATE and o not in self.allow]
        rates = (self.profile.get("rates_per_1k") or {}).get("structural", {})
        self.has_baseline = bool(rates)
        dash_rate = rates.get("em_dash", 0.0) + rates.get("spaced_en_dash", 0.0)
        own_rates = {"em_dash": dash_rate, "contraction": rates.get("contraction", 0.0),
                     "exclamation": rates.get("exclamation", 0.0)}
        self.hard_devices = {d for d, t in DEVICE_THRESHOLDS.items() if own_rates[d] < t}
        self.device_rates = own_rates
        self.watchlist = compile_watchlist(self.profile.get("watchlist"))
        layout = self.profile.get("layout") or {}
        self.one_sentence_per_line = layout.get("one_sentence_per_line")

    @property
    def keeps_one_sentence_per_line(self) -> bool:
        v = self.one_sentence_per_line
        return v is not None and v >= 0.8

    def soft_rate(self, label: str) -> float:
        return self.soft_rates.get(label, 0.0)

    def avoided_opener(self, sentence_text: str):
        """The AI-favoured opener this sentence starts with, if the author does not use it."""
        o = ai_opener(sentence_text)
        return o if o in self.avoid_openers else None


# --------------------------------------------------------------------------- function-word stylometry


def fw_freqs(words) -> dict:
    lw = [w.lower() for w in words]
    total = max(1, len(lw))
    c = Counter(lw)
    return {f: c.get(f, 0) / total for f in FUNCTION_WORDS}


def chunk_words(paragraphs, size: int = 500):
    """Concatenate paragraphs into chunks of roughly `size` words."""
    chunks, cur = [], []
    for p in paragraphs:
        for s in p.sentences:
            cur.extend(s.words)
        if len(cur) >= size:
            chunks.append(cur)
            cur = []
    if len(cur) >= size // 2:
        chunks.append(cur)
    return chunks


def burrows_delta(freqs: dict, mu: dict, sd: dict) -> float:
    zs = [abs((freqs[f] - mu[f]) / sd[f]) for f in FUNCTION_WORDS if sd.get(f, 0) > 1e-9]
    return sum(zs) / len(zs) if zs else 0.0


def fw_baseline(chunks):
    """Mean/sd per function word across chunks, plus the leave-one-out Delta distribution."""
    vecs = [fw_freqs(c) for c in chunks]
    mu = {f: statistics.mean(v[f] for v in vecs) for f in FUNCTION_WORDS}
    sd = {f: statistics.pstdev([v[f] for v in vecs]) for f in FUNCTION_WORDS}
    loo = []
    for k in range(len(vecs)):
        rest = vecs[:k] + vecs[k + 1:]
        if len(rest) < 3:
            continue
        m = {f: statistics.mean(v[f] for v in rest) for f in FUNCTION_WORDS}
        s = {f: statistics.pstdev([v[f] for v in rest]) for f in FUNCTION_WORDS}
        loo.append(burrows_delta(vecs[k], m, s))
    return mu, sd, loo
