#!/usr/bin/env python3
"""List candidate recurring slips in the author's samples, with context, for Claude to verify.

usage:
  python find_slips.py sample1.tex sample2.md ... [-o slip_candidates.md] [--min-count 1]

The patterns (esl_candidates.py) are generic and over-match on purpose. Read every hit
in context and keep only slips that are real and recur; those go into watchlist.json.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "template" / "scripts"))
import prose                                   # noqa: E402
from esl_candidates import CANDIDATES          # noqa: E402

COMPILED = [(label, re.compile(rx, re.I), fix, re.compile(ex, re.I) if ex else None)
            for label, rx, fix, ex in CANDIDATES]


def _context(text: str, start: int, end: int, width: int = 55) -> str:
    a, b = max(0, start - width), min(len(text), end + width)
    return ("..." if a else "") + text[a:start] + "**" + text[start:end] + "**" + text[end:b] + ("..." if b < len(text) else "")


def scan(paths):
    found = {label: {"fix": fix, "hits": []} for label, _, fix, _ in COMPILED}
    for path in paths:
        doc = prose.extract(Path(path))
        for s in doc.sentences():
            for label, rx, _, ex in COMPILED:
                for m in rx.finditer(s.text):
                    if ex and ex.search(s.text[:m.start()]):
                        continue
                    found[label]["hits"].append({"file": Path(path).name, "line": s.line_of(m.start()),
                                                 "match": m.group(0),
                                                 "context": _context(s.text, m.start(), m.end())})
    return found


def to_markdown(found, min_count=1) -> str:
    rows = sorted(((k, v) for k, v in found.items() if len(v["hits"]) >= min_count), key=lambda kv: -len(kv[1]["hits"]))
    out = ["# Slip candidates (verify each one in context)", "",
           "Generic patterns, deliberately broad. Keep a slip for the watchlist only if it is a real error",
           "in context and it recurs (two or more hits, or clearly systematic).", ""]
    if not rows:
        out.append("No candidates found. Read the samples for slips a pattern cannot catch.")
    for label, v in rows:
        out.append(f"## {label}: {len(v['hits'])} hit(s); usual fix: {v['fix']}")
        for h in v["hits"][:5]:
            out.append(f"- {h['file']}:{h['line']}  {h['context']}")
        if len(v["hits"]) > 5:
            out.append(f"- ... {len(v['hits']) - 5} more")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("samples", nargs="+")
    ap.add_argument("-o", "--out", help="write markdown here (default: stdout)")
    ap.add_argument("--min-count", type=int, default=1)
    a = ap.parse_args()
    md = to_markdown(scan(a.samples), a.min_count)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"candidates: {a.out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
