#!/usr/bin/env python3
"""Extract prose from Markdown or plain text while keeping source line numbers.

Frozen: fenced code blocks. Math: $$ blocks (and inline $...$ becomes MATH).
Excluded: front matter, block quotes (usually someone else's words), HTML blocks,
link definitions, horizontal rules. Tables count as floats. Footnote definitions
become separate paragraphs. Pandoc citations ([@key], @key) are removed.
Standard library only.
"""
from __future__ import annotations

import re
from pathlib import Path

from textcore import PARBREAK, Doc, artifact_sentences, build_paragraphs, sentinel

NOTE = "\x04"

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
_SETEXT_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_HR_RE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$|^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_FOOTDEF_RE = re.compile(r"^\s{0,3}\[\^[^\]]+\]:\s*")
_LINKDEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*\S+")
_QUOTE_RE = re.compile(r"^\s{0,3}>")
_HTML_BLOCK_RE = re.compile(r"^\s{0,3}</?[A-Za-z][A-Za-z0-9-]*(\s[^>]*)?/?>\s*$")
_MATHBLOCK_RE = re.compile(r"^\s*\$\$")


def _inline_math(m):
    c = m.group(1).rstrip()
    return " MATH" + (c[-1] if c and c[-1] in ".,;:" else "") + " "


def clean_inline(t: str) -> str:
    """Strip inline Markdown so only the words remain."""
    t = re.sub(r"`+[^`]*`+", " CODE ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", t)
    t = re.sub(r"<(?:https?|mailto):[^>]+>", " URL ", t)
    t = re.sub(r"https?://[^\s)>\]]+", " URL ", t)
    t = re.sub(r"\[\^[^\]]+\]", "", t)
    t = re.sub(r"\[[^\]\[]*@[A-Za-z0-9_][^\]\[]*\]", " ", t)                 # [@key; @key2, p. 3]
    t = re.sub(r"(?<![\w.@])@[A-Za-z][\w:.#$%&+?~/-]*\w", " Author ", t)     # narrative @key
    t = re.sub(r"(?<![\\$\w])\$(?=\S)(.+?)(?<=\S)(?<!\\)\$(?!\d)", _inline_math, t)
    t = re.sub(r"\\\((.+?)\\\)", " MATH ", t)
    t = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", t)
    t = re.sub(r"(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?!\*)", r"\1", t)
    t = re.sub(r"(?<![_\w])_(?=\S)(.+?)(?<=\S)_(?![_\w])", r"\1", t)
    t = re.sub(r"~~(.+?)~~", r"\1", t)
    t = re.sub(r"<[^>\n]+>", " ", t)
    t = re.sub(r"\\([\\`*_{}\[\]()#+\-.!$|])", r"\1", t)
    t = t.replace("---", "—").replace("--", "–")
    return t


def fragment_prose(raw: str) -> str:
    """Clean prose for a Markdown fragment (e.g. one diff hunk)."""
    t = re.sub(r"(?ms)^\s{0,3}(`{3,}|~{3,}).*?^\s{0,3}\1\s*$", " ", raw)
    t = re.sub(r"(?s)\$\$.*?\$\$", " MATH ", t)
    lines = []
    for line in t.split("\n"):
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s{0,3}>\s?", "", line)
        line = _LIST_RE.sub("", line)
        line = _FOOTDEF_RE.sub("", line)
        lines.append(line)
    t = clean_inline(" ".join(lines))
    t = re.sub(r"\s+([.,;:!?)])", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def extract(source, min_words: int = 3) -> Doc:
    """source: path or Markdown/plain-text string."""
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).exists()):
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    else:
        text = source
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    n = len(lines)
    kinds, parts = {}, []
    i = 0
    if lines and lines[0].strip() == "---":                         # YAML front matter
        j = 1
        while j < n and lines[j].strip() not in ("---", "..."):
            j += 1
        if j < n:
            for k in range(j + 1):
                kinds[k + 1] = "preamble"
            i = j + 1
    fence, math_block, html_comment = None, False, False
    while i < n:
        line, ln = lines[i], i + 1
        s = line.strip()
        if fence:
            kinds[ln] = "frozen"
            if re.match(r"^\s{0,3}" + re.escape(fence[0]) + "{%d,}\\s*$" % len(fence), line):
                fence = None
            i += 1
            continue
        if math_block:
            kinds[ln] = "math"
            if s.endswith("$$"):
                math_block = False
                if s[:-2].rstrip().endswith("."):
                    parts.append(".")
            i += 1
            continue
        if html_comment:
            kinds[ln] = "excluded"
            if "-->" in line:
                html_comment = False
            i += 1
            continue
        if not s:
            kinds[ln] = "blank"
            parts.append(PARBREAK)
            i += 1
            continue
        m = _FENCE_RE.match(line)
        if m:
            fence = m.group(1)
            kinds[ln] = "frozen"
            parts.append(PARBREAK)
            i += 1
            continue
        if _MATHBLOCK_RE.match(line):
            kinds[ln] = "math"
            rest = s[2:]
            if not (len(rest) >= 2 and rest.endswith("$$")):
                math_block = True
            parts.append(" MATH ")
            i += 1
            continue
        if s.startswith("<!--"):
            kinds[ln] = "excluded"
            if "-->" not in s:
                html_comment = True
            i += 1
            continue
        if (i + 1 < n and _SETEXT_RE.match(lines[i + 1]) and lines[i + 1].strip()
                and not _LIST_RE.match(line) and (i == 0 or not lines[i - 1].strip())):
            kinds[ln] = kinds[ln + 1] = "heading"
            parts.append(PARBREAK)
            i += 2
            continue
        if _HEADING_RE.match(line):
            kinds[ln] = "heading"
            parts.append(PARBREAK)
            i += 1
            continue
        if _HR_RE.match(line):
            kinds[ln] = "excluded"
            parts.append(PARBREAK)
            i += 1
            continue
        if _TABLE_RE.match(line):
            kinds[ln] = "float"
            parts.append(PARBREAK)
            i += 1
            continue
        if _QUOTE_RE.match(line) or _HTML_BLOCK_RE.match(line):
            kinds[ln] = "excluded"
            parts.append(PARBREAK)
            i += 1
            continue
        m = _FOOTDEF_RE.match(line)
        if m:
            kinds[ln] = "prose"
            parts.append(PARBREAK + NOTE + sentinel(ln) + clean_inline(line[m.end():]) + "\n")
            i += 1
            continue
        if _LINKDEF_RE.match(line):
            kinds[ln] = "excluded"
            i += 1
            continue
        m = _LIST_RE.match(line)
        if m:
            kinds[ln] = "prose"
            parts.append(PARBREAK + sentinel(ln) + clean_inline(line[m.end():]) + "\n")
            i += 1
            continue
        kinds[ln] = "prose"
        parts.append(sentinel(ln) + clean_inline(line) + "\n")
        i += 1

    chunks = [(c.replace(NOTE, ""), NOTE in c) for c in "".join(parts).split(PARBREAK)]
    line_kind = {k + 1: kinds.get(k + 1, "prose") for k in range(n)}
    doc = Doc(paragraphs=build_paragraphs(chunks, min_words=min_words, region_marker=False),
              line_kind=line_kind, n_lines=n, fmt="md", layout_meaningful=True)
    doc.diagnostics = {"artifacts": artifact_sentences(doc)}
    return doc


if __name__ == "__main__":
    import sys
    d = extract(sys.argv[1])
    for p in d.paragraphs:
        print(f"--- [{'footnote' if p.footnote else 'main'}] lines {p.start_line}-{p.end_line}")
        for s in p.sentences:
            print(f"  {s.line:5d} | {s.text}")
