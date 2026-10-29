#!/usr/bin/env python3
"""Measure an author's writing style from samples they wrote themselves.

usage:
  python style_profile.py sample1.tex sample2.md notes.docx -o author_profile.json \\
      [--md author_stats.md] [--check] [--no-appendix] [--min-words 3000]

Use text the author drafted on their own: not co-authors' sections, not text that an
LLM already polished. The profile is the baseline that ai_tell_lint.py and diff_guard.py
compare against. --check prints what the extractor saw in each file, so missed macros or
environments can be fixed before building a skill.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prose                # noqa: E402
import tells as tl          # noqa: E402

SPECIAL = {"math", "ref", "author", "url", "code"}


def _r(x, k=3):
    return round(float(x), k)


def _non_english_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if ord(ch) > 0x24F) / len(letters)


def build_profile(paths, include_appendix=True, min_words=3000, config=None):
    docs = []
    for p in paths:
        path = Path(p)
        docs.append((path, prose.extract(path, config=config)))
    paras = [p for _, d in docs for p in d.paragraphs if include_appendix or p.region == "main"]
    sents = [s for p in paras for s in p.sentences]
    words = [w for s in sents for w in s.words]
    text = "\n".join(p.text for p in paras)
    n_words, n_sents = len(words), len(sents)
    if n_words < min_words:
        raise SystemExit(f"Only {n_words:,} words of prose found in {len(paths)} file(s); need at least "
                         f"{min_words:,}. Add more samples, or pass --min-words to accept a thinner baseline.")

    L = [s.n_words for s in sents]
    sentence_length = {
        "mean": _r(statistics.mean(L), 2), "sd": _r(statistics.pstdev(L), 2), "cv": _r(tl.cv(L)),
        "median": _r(statistics.median(L), 1), "p10": _r(tl.quantile(L, .1), 1),
        "p25": _r(tl.quantile(L, .25), 1), "p75": _r(tl.quantile(L, .75), 1),
        "p90": _r(tl.quantile(L, .9), 1),
        "share_under_10": _r(sum(x < 10 for x in L) / n_sents),
        "share_over_35": _r(sum(x > 35 for x in L) / n_sents),
    }
    adj = []
    for p in paras:
        ls = [s.n_words for s in p.sentences]
        adj += [abs(a - b) for a, b in zip(ls, ls[1:])]
    para_cv = [tl.cv(s.n_words for s in p.sentences) for p in paras if len(p.sentences) >= 3]
    para_len = [len(p.sentences) for p in paras if p.n_words >= 25]

    layout_docs = [(path, d) for path, d in docs if d.layout_meaningful]
    boundaries = [s.ends_at_line_end for _, d in layout_docs for p in d.paragraphs
                  if include_appendix or p.region == "main" for s in p.sentences[:-1]]

    A, B, S = tl.count_tier(text, "A"), tl.count_tier(text, "B"), tl.structural_counts(text)
    ai_open = Counter(o for s in sents if (o := tl.ai_opener(s.text)))
    conn = Counter(c for s in sents if (c := tl.connective(s.text)))
    we_open = sum(1 for s in sents if re.match(r"(?i)we\b", s.text))
    closers = [tl.is_summary_closer(p.sentences[-1].text) for p in paras if len(p.sentences) >= 3]
    passive = sum(len(tl.PASSIVE_RE.findall(s.text)) for s in sents)

    op1 = Counter(tl.opener(s.text, 1) for s in sents)
    op2 = Counter(tl.opener(s.text, 2) for s in sents)
    op3 = Counter(tl.opener(s.text, 3) for s in sents)
    fw = set(tl.FUNCTION_WORDS)
    tri = Counter()
    for s in sents:
        w = [x.lower() for x in s.words]
        for g in zip(w, w[1:], w[2:]):
            if any(x in SPECIAL for x in g):
                continue
            if sum(x in fw for x in g) >= 2:
                tri[" ".join(g)] += 1

    size = 500 if n_words >= 3000 else max(150, n_words // 6)
    chunks = tl.chunk_words(paras, size)
    mu, sd, loo = tl.fw_baseline(chunks) if len(chunks) >= 6 else ({}, {}, [])

    sources, diagnostics, declared, macros = [], {}, set(), set()
    for path, d in docs:
        ws = d.words(include_appendix)
        sources.append({"file": path.name, "format": d.fmt,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
                        "words": len(ws), "sentences": len(d.sentences(include_appendix)),
                        "paragraphs": len(d.paragraphs)})
        diag = dict(d.diagnostics)
        declared |= set(diag.pop("theorem_envs_declared", []))
        macros |= set(diag.pop("macros_expanded", []))
        diag.pop("frozen_envs", None)
        diagnostics[path.name] = diag

    def rates(c):
        return {k: _r(tl.rate(v, n_words)) for k, v in sorted(c.items(), key=lambda kv: -kv[1])}

    profile = {
        "version": 2,
        "created": datetime.date.today().isoformat(),
        "language": "en",
        "include_appendix": include_appendix,
        "sources": sources,
        "n_words": n_words, "n_sentences": n_sents, "n_paragraphs": len(paras),
        "sentence_length": sentence_length,
        "adjacent_change": _r(statistics.mean(adj) / statistics.mean(L)) if adj else 0.0,
        "paragraph": {
            "sentences_mean": _r(statistics.mean(para_len), 2) if para_len else 0,
            "sentences_median": statistics.median(para_len) if para_len else 0,
            "cv_p10": _r(tl.quantile(para_cv, .1)), "cv_median": _r(tl.quantile(para_cv, .5)),
            "cv_p90": _r(tl.quantile(para_cv, .9)),
        },
        "layout": {
            "one_sentence_per_line": _r(statistics.mean(boundaries)) if boundaries else None,
            "measured_on": [p.name for p, _ in layout_docs],
        },
        "counts": {"tierA": dict(A), "tierB": dict(B), "structural": dict(S), "ai_openers": dict(ai_open)},
        "rates_per_1k": {"tierA": rates(A), "tierB": rates(B), "structural": rates(S)},
        "ai_openers_per_100_sentences": {k: _r(100 * v / n_sents) for k, v in ai_open.most_common()},
        "connectives_per_100_sentences": {k: _r(100 * v / n_sents) for k, v in conn.most_common(40)},
        "we_opener_share": _r(we_open / n_sents),
        "summary_closer_share": _r(sum(closers) / len(closers)) if closers else 0.0,
        "passive_per_sentence": _r(passive / n_sents),
        "top_openers_1": [[k, v] for k, v in op1.most_common(25)],
        "top_openers_2": [[k, v] for k, v in op2.most_common(30) if v >= 3],
        "top_openers_3": [[k, v] for k, v in op3.most_common(30) if v >= 3],
        "signature_trigrams": [[k, v] for k, v in tri.most_common(60) if v >= 4],
        "function_words": {
            "chunk_size": size, "n_chunks": len(chunks), "mu": {k: _r(v, 5) for k, v in mu.items()},
            "sd": {k: _r(v, 5) for k, v in sd.items()},
            "delta_loo_p50": _r(tl.quantile(loo, .5)) if loo else None,
            "delta_loo_p90": _r(tl.quantile(loo, .9)) if loo else None,
            "delta_loo_p95": _r(tl.quantile(loo, .95)) if loo else None,
        },
        "latex": {"theorem_envs_declared": sorted(declared), "macros_expanded": sorted(macros)},
        "diagnostics": diagnostics,
        "non_english_share": _r(_non_english_share(text)),
    }
    return profile


def to_markdown(pr: dict) -> str:
    sl, pa = pr["sentence_length"], pr["paragraph"]
    src = ", ".join(f"{s['file']} ({s['words']:,} words)" for s in pr["sources"])
    st = pr["rates_per_1k"]["structural"]
    osl = pr["layout"]["one_sentence_per_line"]
    lines = [
        "# Author style statistics (generated)",
        "",
        f"Built {pr['created']} from {src}. Regenerate with `scripts/style_profile.py`; do not edit by hand.",
        "",
        "## Rhythm and layout",
        f"- Sentence length (words): median {sl['median']}, mean {sl['mean']}, p10-p90 {sl['p10']}-{sl['p90']}, CV {sl['cv']}",
        f"- Short (<10 words) {sl['share_under_10']:.0%} / long (>35 words) {sl['share_over_35']:.0%} of sentences",
        f"- Adjacent-sentence length change: {pr['adjacent_change']} x mean length",
        f"- Sentences per paragraph: median {pa['sentences_median']}; within-paragraph CV p10 {pa['cv_p10']}, median {pa['cv_median']}",
        ("- Sentence boundaries that fall at a source line break: "
         + (f"{osl:.0%} (" + ("one sentence per line" if osl >= 0.8 else "hard-wrapped or mixed") + ")"
            if osl is not None else "not measured (no LaTeX/Markdown/text samples)")),
        "",
        "## Punctuation and devices (per 1,000 words)",
        f"- em dash {st.get('em_dash', 0)}, spaced en dash {st.get('spaced_en_dash', 0)}, spaced hyphen as dash {st.get('spaced_hyphen_dash', 0)}",
        f"- semicolon {st.get('semicolon', 0)}, colon {st.get('colon', 0)}, parenthesis {st.get('parenthesis', 0)}, e.g./i.e. {st.get('eg_ie', 0)}",
        f"- hedges {st.get('hedge', 0)}, intensifiers {st.get('intensifier', 0)}, we/our/us {st.get('we', 0)}, triad lists {st.get('triad', 0)}",
        f"- contractions {st.get('contraction', 0)}, exclamation marks {st.get('exclamation', 0)}",
        f"- passive constructions per sentence {pr['passive_per_sentence']}; summary-style closing sentences in {pr['summary_closer_share']:.0%} of paragraphs",
        "",
        "## Sentence-initial connectives (per 100 sentences)",
        ", ".join(f"{k} {v}" for k, v in list(pr["connectives_per_100_sentences"].items())[:30]) or "none",
        f"\nSentences that start with \"We\": {pr['we_opener_share']:.0%}",
        "",
        "## AI-associated vocabulary already in the author's own text",
        "Tier A (counts): " + (", ".join(f"{k} {v}" for k, v in pr["counts"]["tierA"].items()) or "none"),
        "",
        "Tier B (per 1,000 words): " + (", ".join(f"{k} {v}" for k, v in pr["rates_per_1k"]["tierB"].items()) or "none"),
        "",
        "AI-favoured sentence openers (per 100 sentences): "
        + (", ".join(f"{k} {v}" for k, v in pr["ai_openers_per_100_sentences"].items()) or "none"),
        "",
        "## Most frequent sentence openers",
        ", ".join(f"{k} ({v})" for k, v in pr["top_openers_2"][:25]) or "none",
        "",
        "## Function-word phrases the author repeats",
        ", ".join(f"{k} ({v})" for k, v in pr["signature_trigrams"][:40]) or "none",
    ]
    fwp = pr["function_words"]
    lines += ["", "## Stylometry"]
    if fwp.get("delta_loo_p95") is not None:
        lines.append(f"Function-word Delta (leave-one-out over {fwp['n_chunks']} chunks of ~{fwp['chunk_size']} words): "
                     f"median {fwp['delta_loo_p50']}, p90 {fwp['delta_loo_p90']}, p95 {fwp['delta_loo_p95']}. "
                     "A revised section far above p95 no longer reads like this author.")
    else:
        lines.append("Not enough text for a function-word baseline (needs six chunks).")
    lx = pr.get("latex") or {}
    if lx.get("theorem_envs_declared") or lx.get("macros_expanded"):
        lines += ["", "## LaTeX conventions found",
                  f"- theorem-like environments declared: {', '.join(lx.get('theorem_envs_declared') or []) or 'none'}",
                  f"- simple macros expanded: {', '.join(lx.get('macros_expanded') or []) or 'none'}"]
    lines.append("")
    return "\n".join(lines)


def print_check(pr: dict):
    print("\nExtraction check")
    problems = 0
    for s in pr["sources"]:
        d = pr["diagnostics"].get(s["file"], {})
        print(f"- {s['file']} [{s['format']}]: {s['words']:,} words, {s['sentences']} sentences, {s['paragraphs']} paragraphs")
        unk = d.get("unknown_commands") or {}
        if unk:
            print("    commands unwrapped blindly (content kept): " + ", ".join(f"\\{k} x{v}" for k, v in unk.items()))
        for line, text in (d.get("artifacts") or [])[:5]:
            problems += 1
            print(f"    markup left in a sentence, line {line}: {text}")
    lx = pr.get("latex") or {}
    if lx.get("theorem_envs_declared") or lx.get("macros_expanded"):
        print("LaTeX conventions found across the samples")
        if lx.get("theorem_envs_declared"):
            print("  theorem-like environments (kept frozen): " + ", ".join(lx["theorem_envs_declared"]))
        if lx.get("macros_expanded"):
            print("  macros expanded: " + ", ".join(lx["macros_expanded"]))
    if pr["non_english_share"] > 0.2:
        problems += 1
        print(f"WARNING: {pr['non_english_share']:.0%} of letters are non-Latin. The lexicon is English-only.")
    if pr["n_words"] < 8000:
        print(f"NOTE: {pr['n_words']:,} words is a thin baseline; 8,000+ words (ideally 10,000+) gives steadier numbers.")
    if not problems:
        print("No extraction problems found.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("samples", nargs="+", help="files the author wrote (.tex .md .txt .docx)")
    ap.add_argument("-o", "--out", default="author_profile.json")
    ap.add_argument("--md", help="also write a readable summary (markdown)")
    ap.add_argument("--check", action="store_true", help="print extraction diagnostics per file")
    ap.add_argument("--no-appendix", action="store_true", help="ignore appendix text")
    ap.add_argument("--min-words", type=int, default=3000)
    ap.add_argument("--config", help="config.json: {'latex': {'frozen_envs_extra', 'unfrozen_envs', 'macros'}}")
    a = ap.parse_args()
    config = json.loads(Path(a.config).read_text(encoding="utf-8")) if a.config else None
    pr = build_profile(a.samples, include_appendix=not a.no_appendix, min_words=a.min_words, config=config)
    Path(a.out).write_text(json.dumps(pr, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"profile: {a.out}  ({pr['n_words']:,} words, {pr['n_sentences']} sentences)")
    if a.md:
        Path(a.md).write_text(to_markdown(pr), encoding="utf-8")
        print(f"summary: {a.md}")
    if a.check:
        print_check(pr)


if __name__ == "__main__":
    main()
