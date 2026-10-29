#!/usr/bin/env python3
"""Optional regression check: did any edited paragraph start to look MORE machine-written?

Scores each changed paragraph before and after editing with a LOCAL detector and flags
paragraphs whose score moved toward "machine". Default detector: Binoculars
(Hans et al., ICML 2024), which needs a GPU with room for two 7B models:

  git clone https://github.com/ahans30/Binoculars && pip install -e ./Binoculars

For Binoculars a LOWER score means more machine-like; the paper's global threshold is ~0.90.

usage:
  python detector_check.py original.tex merged.tex [--margin 0.02] [--report detector.md]
  (also works for .md/.txt drafts)
  python detector_check.py original.tex merged.tex --scorer mymodule:score --ai-direction higher

Rules of use:
  - Never rewrite text to raise this score. Use it only to REJECT edits: when a paragraph
    gets worse, revert that paragraph's edits (keep the original wording).
  - Keep unpublished manuscripts on your own machine; do not paste them into online detectors.
  - Scores on paragraphs under ~40 words are noise; they are skipped.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prose                # noqa: E402
from textcore import words_of  # noqa: E402

PLACEHOLDERS = {"MATH": "x", "REF": "Section 2", "Author": "Smith et al.", "URL": "the website", "CODE": "code"}


def readable(text: str) -> str:
    for k, v in PLACEHOLDERS.items():
        text = text.replace(k, v)
    return text


def changed_pairs(doc_a, doc_b):
    """Pairs (para_a, para_b) whose text differs, aligned by paragraph order."""
    ta = [p.text for p in doc_a.paragraphs]
    tb = [p.text for p in doc_b.paragraphs]
    pairs = []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op != "replace":
            continue
        if i2 - i1 == j2 - j1:
            pairs += list(zip(doc_a.paragraphs[i1:i2], doc_b.paragraphs[j1:j2]))
        else:                                   # merged/split paragraphs: compare the blocks
            pairs.append((doc_a.paragraphs[i1:i2], doc_b.paragraphs[j1:j2]))
    return pairs


def _text(p):
    return " ".join(x.text for x in p) if isinstance(p, list) else p.text


def _lines(p):
    if isinstance(p, list):
        return f"{p[0].start_line}-{p[-1].end_line}" if p else "-"
    return f"{p.start_line}-{p.end_line}"


def load_scorer(spec: str):
    if spec == "binoculars":
        try:
            from binoculars import Binoculars        # type: ignore
        except ImportError:
            sys.exit("Binoculars is not installed. See the header of this script, or pass --scorer module:function.")
        bino = Binoculars()

        def score(texts):
            out = bino.compute_score(texts)
            return list(out) if isinstance(out, (list, tuple)) else [out]
        return score
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("edited", help="usually merged.tex from diff_guard.py")
    ap.add_argument("--scorer", default="binoculars", help="'binoculars' or module:function taking list[str] -> list[float]")
    ap.add_argument("--ai-direction", choices=["lower", "higher"], default="lower",
                    help="which direction of the score means 'machine-like' (Binoculars: lower)")
    ap.add_argument("--threshold", type=float, default=0.901, help="decision threshold of the detector")
    ap.add_argument("--margin", type=float, default=0.02, help="allowed move toward 'machine' before flagging")
    ap.add_argument("--min-words", type=int, default=40)
    ap.add_argument("--report", default="detector.md")
    a = ap.parse_args()

    fmt = prose.detect_format(a.original)
    doc_a = prose.extract(Path(a.original), fmt=fmt)
    doc_b = prose.extract(Path(a.edited), fmt=fmt)
    pairs = [(pa, pb) for pa, pb in changed_pairs(doc_a, doc_b)
             if len(words_of(_text(pa))) >= a.min_words and len(words_of(_text(pb))) >= a.min_words]
    if not pairs:
        Path(a.report).write_text("# Detector check\n\nNo changed paragraph long enough to score.\n", encoding="utf-8")
        print("nothing to score")
        return
    score = load_scorer(a.scorer)
    before = score([readable(_text(pa)) for pa, _ in pairs])
    after = score([readable(_text(pb)) for _, pb in pairs])
    sign = 1 if a.ai_direction == "lower" else -1      # sign * (after - before) < 0 means more machine-like
    rows, n_bad = [], 0
    for (pa, pb), s0, s1 in zip(pairs, before, after):
        worse = sign * (s1 - s0) < -a.margin
        crossed = (s0 >= a.threshold > s1) if a.ai_direction == "lower" else (s0 <= a.threshold < s1)
        bad = worse or crossed
        n_bad += bad
        rows.append(f"| {_lines(pa)} | {_lines(pb)} | {s0:.3f} | {s1:.3f} | {s1 - s0:+.3f} | "
                    f"{'REVERT this paragraph' if bad else 'ok'} |")
    md = ["# Detector check", "",
          f"Scorer: {a.scorer} (machine-like = {a.ai_direction} score), margin {a.margin}, threshold {a.threshold}.",
          f"{len(pairs)} changed paragraphs scored, {n_bad} moved toward 'machine'.", "",
          "| original lines | edited lines | before | after | change | verdict |", "|---|---|---|---|---|---|"] + rows
    Path(a.report).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(pairs)} paragraphs scored, {n_bad} to revert -> {a.report}")
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
