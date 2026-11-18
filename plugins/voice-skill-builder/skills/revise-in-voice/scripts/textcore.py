#!/usr/bin/env python3
"""Shared structures and sentence splitting for the prose extractors.

Every extractor (LaTeX, Markdown/plain text, Word) produces a Doc: paragraphs of
sentences that remember which source line they start on, plus a per-line "kind"
(prose, math, frozen, float, heading, excluded, preamble, blank). Standard library only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SENT = "\x00"        # line sentinel:  \x00<lineno>\x00
PARBREAK = "\x01"
APPXMARK = "\x02"
ABBRDOT = "\x03"
SENT_RE = re.compile(SENT + r"(\d+)" + SENT)

# when one line holds several kinds, the most protective one wins
KIND_PRIORITY = ["preamble", "frozen", "math", "float", "heading", "excluded", "prose"]


def sentinel(line: int) -> str:
    return f"{SENT}{line}{SENT}"


@dataclass
class Sentence:
    text: str
    line: int
    words: list
    ends_at_line_end: bool = True
    line_breaks: list = field(default_factory=list)   # [(offset in text, source line), ...]

    @property
    def n_words(self) -> int:
        return len(self.words)

    def line_of(self, offset: int) -> int:
        """Source line of the character at `offset` in self.text."""
        line = self.line
        for off, ln in self.line_breaks:
            if off > offset:
                break
            line = ln
        return line


@dataclass
class Paragraph:
    start_line: int
    end_line: int
    text: str
    sentences: list
    region: str = "main"          # "main" or "appendix"
    footnote: bool = False

    @property
    def n_words(self) -> int:
        return sum(s.n_words for s in self.sentences)


@dataclass
class Doc:
    paragraphs: list
    line_kind: dict = field(default_factory=dict)   # 1-based line -> kind
    n_lines: int = 0
    fmt: str = "tex"
    layout_meaningful: bool = True                  # do source line breaks mean anything?
    diagnostics: dict = field(default_factory=dict)

    def words(self, include_appendix: bool = True) -> list:
        out = []
        for p in self.paragraphs:
            if include_appendix or p.region == "main":
                for s in p.sentences:
                    out.extend(s.words)
        return out

    def sentences(self, include_appendix: bool = True) -> list:
        return [s for p in self.paragraphs if include_appendix or p.region == "main" for s in p.sentences]


_ABBR_RE = re.compile(
    r"\b(?:e\.g|i\.e|et al|etc|vs|cf|Figs?|Eqs?|Secs?|Props?|Thms?|Defs?|Lems?|Cors?|Algs?|"
    r"Tabs?|resp|approx|w\.r\.t|i\.i\.d|a\.k\.a|Ph\.D|U\.S|Dr|Mr|Ms|Prof|Jr|viz|Refs?|pp|Vol|No|Nos)\.",
    re.I)
_BOUNDARY_RE = re.compile(r"[.!?][\"')\]’”]*(\s+)(?=[A-Z0-9(\"“‘'\[])")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*[A-Za-z]|[A-Za-z]|\d+(?:[.,]\d+)*%?")
_ARTIFACT_RE = re.compile(r"[\\{}]|\b(?:begin|end)\b(?=\s*\{)")


def words_of(text: str) -> list:
    return WORD_RE.findall(text)


def sentences_from(raw: str, min_words: int = 3):
    """Split cleaned text that still holds line sentinels into sentences.

    Returns (sentences, first_line, last_line).
    """
    chars, line_at, nl_before = [], [], []
    cur, pending_nl = 0, False
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == SENT:
            j = raw.index(SENT, i + 1)
            cur = int(raw[i + 1:j])
            pending_nl = True
            i = j + 1
            continue
        ch = raw[i]
        if ch in "\n\t\r":
            ch = " "
        if ch == " " and chars and chars[-1] == " ":
            i += 1
            continue
        chars.append(ch)
        line_at.append(cur)
        nl_before.append(pending_nl)
        pending_nl = False
        i += 1
    text = "".join(chars)
    prot = _ABBR_RE.sub(lambda m: m.group(0).replace(".", ABBRDOT), text)
    starts = [0] + [m.end() for m in _BOUNDARY_RE.finditer(prot)]
    out = []
    for k, a in enumerate(starts):
        b = starts[k + 1] if k + 1 < len(starts) else len(prot)
        seg = prot[a:b]
        lead = len(seg) - len(seg.lstrip())
        core = seg.strip()
        first = a + lead
        kept, src = [], []                       # drop spaces before punctuation and after "("
        for j, ch in enumerate(core):
            if ch == " ":
                nxt = core[j + 1] if j + 1 < len(core) else ""
                if nxt in ".,;:!?)" or (kept and kept[-1] == "("):
                    continue
            kept.append(ch)
            src.append(first + j)
        stext = "".join(kept).replace(ABBRDOT, ".")
        if not stext:
            continue
        w = words_of(stext)
        if len(w) < min_words:
            continue
        line = line_at[first] if first < len(line_at) else cur
        breaks = [(j, line_at[x]) for j, x in enumerate(src)
                  if x < len(line_at) and (j == 0 or line_at[x] != line_at[src[j - 1]])]
        if k + 1 < len(starts):
            nb = starts[k + 1]
            ends_eol = any(nl_before[x] for x in range(max(a, nb - 3), min(nb + 1, len(nl_before))))
        else:
            ends_eol = True
        out.append(Sentence(text=stext, line=line, words=w, ends_at_line_end=ends_eol, line_breaks=breaks))
    lines = [x for x in line_at if x]
    return out, (min(lines) if lines else cur), (max(lines) if lines else cur)


def split_sentences(text: str, min_words: int = 3) -> list:
    """Sentence split for text that is already clean (no markup, no sentinels)."""
    return sentences_from(text, min_words=min_words)[0]


def build_paragraphs(chunks, min_words: int = 3, region_marker: bool = True):
    """chunks: cleaned paragraph texts with sentinels; APPXMARK switches to the appendix."""
    paragraphs, region = [], "main"
    for chunk, is_note in chunks:
        if region_marker and APPXMARK in chunk:
            region = "appendix"
            chunk = chunk.replace(APPXMARK, "")
        sents, a, b = sentences_from(chunk, min_words=min_words)
        if sents:
            paragraphs.append(Paragraph(start_line=a, end_line=b, text=" ".join(s.text for s in sents),
                                        sentences=sents, region=region, footnote=is_note))
    return paragraphs


def artifact_sentences(doc: Doc, limit: int = 10) -> list:
    """Sentences that still contain markup: a sign the extractor missed a macro or environment."""
    out = []
    for s in doc.sentences():
        if _ARTIFACT_RE.search(s.text):
            out.append((s.line, s.text[:160]))
            if len(out) >= limit:
                break
    return out
