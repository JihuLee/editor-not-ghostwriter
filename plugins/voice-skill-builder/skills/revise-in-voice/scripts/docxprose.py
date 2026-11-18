#!/usr/bin/env python3
"""Extract prose from a Word (.docx) file, for building a style profile.

Reads word/document.xml with the standard library. Headings, captions, titles,
tables of contents and bibliography paragraphs are skipped; tables are skipped;
equations become MATH; tracked deletions are ignored. Numeric citations such as
[3] or [4, 7-9] and author-year citations such as (Smith et al., 2020) are removed.

Word files are supported as writing samples only. Line numbers here are paragraph
numbers, so layout statistics (one sentence per line) are not computed from them.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from textcore import PARBREAK, Doc, artifact_sentences, build_paragraphs, sentinel

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
SKIP_STYLES = ("heading", "title", "subtitle", "caption", "toc", "bibliography", "tableoffigures",
               "tocheading", "footer", "header")
_NUM_CITE_RE = re.compile(r"\s?\[\d+(?:\s*[,–—-]\s*\d+)*\]")
_AY_CITE_RE = re.compile(r"\s?\((?:[A-Z][A-Za-z'\-]+(?: et al\.)?(?:,| and [A-Z][A-Za-z'\-]+,)? \d{4}[a-z]?(?:;\s*)?)+\)")


def _para_text(p) -> str:
    out = []

    def walk(el):
        tag = el.tag
        if tag in (M + "oMath", M + "oMathPara"):
            out.append(" MATH ")
            return
        if tag in (W + "delText", W + "instrText", W + "footnoteReference", W + "endnoteReference"):
            return
        if tag == W + "del":
            return
        if tag == W + "t" and el.text:
            out.append(el.text)
        elif tag in (W + "tab", W + "br", W + "cr"):
            out.append(" ")
        for child in el:
            walk(child)

    walk(p)
    t = "".join(out)
    t = _NUM_CITE_RE.sub("", t)
    t = _AY_CITE_RE.sub("", t)
    return t


def _style(p) -> str:
    ppr = p.find(W + "pPr")
    if ppr is None:
        return ""
    st = ppr.find(W + "pStyle")
    return (st.get(W + "val") or "").lower() if st is not None else ""


def extract(source, min_words: int = 3) -> Doc:
    path = Path(source)
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    paras = []

    def collect(el):
        for child in el:
            if child.tag == W + "p":
                paras.append(child)
            elif child.tag == W + "sdt":
                content = child.find(W + "sdtContent")
                if content is not None:
                    collect(content)
            # tables (w:tbl) and section properties are skipped

    collect(body if body is not None else root)
    parts, kinds = [], {}
    for k, p in enumerate(paras, start=1):
        style = _style(p)
        if any(style.startswith(s) for s in SKIP_STYLES):
            kinds[k] = "heading"
            continue
        text = _para_text(p).strip()
        if not text:
            kinds[k] = "blank"
            continue
        kinds[k] = "prose"
        parts.append(PARBREAK + sentinel(k) + text)
    chunks = [(c, False) for c in "".join(parts).split(PARBREAK)]
    doc = Doc(paragraphs=build_paragraphs(chunks, min_words=min_words, region_marker=False),
              line_kind=kinds, n_lines=len(paras), fmt="docx", layout_meaningful=False)
    doc.diagnostics = {"artifacts": artifact_sentences(doc)}
    return doc


if __name__ == "__main__":
    import sys
    d = extract(sys.argv[1])
    for p in d.paragraphs:
        print(f"--- paragraph {p.start_line}")
        for s in p.sentences:
            print("   ", s.text)
