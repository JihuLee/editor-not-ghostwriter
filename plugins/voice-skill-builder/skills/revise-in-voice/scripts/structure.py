#!/usr/bin/env python3
"""Section structure of LaTeX and Markdown papers: the order of sections, how long each part runs, how
headings are used and how titles look.

Optional part of an author profile (style_profile.py --structure). The lint compares a draft with it and
only reports; voice_rules.py prints a short summary for the editor and the reviewers.

Commented-out text (%, \\iffalse ... \\fi, the comment environment) is ignored, and so are back-matter
sections such as acknowledgments and biographies. A LaTeX sample that \\input{}s other samples is read as
one paper, in input order. Word counts come from the same prose extractor as the rest of the profile.
"""
from __future__ import annotations

import re
import statistics
from pathlib import Path

import prose
from texprose import EXCLUDED_SECTION_RE, read_group

LEVELS = {"part": 0, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4}
HEAD_RE = re.compile(r"\\(part|chapter|section|subsection|subsubsection|paragraph)\*?(?![A-Za-z])")
INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
APPENDIX_RE = re.compile(r"\\appendix(?![A-Za-z])|\\appendices(?![A-Za-z])|\\begin\{appendices\}")
KINDS = [
    ("introduction", re.compile(r"\bintroduction\b|^intro\b", re.I)),
    ("related", re.compile(r"related|prior work|previous work|literature", re.I)),
    ("conclusion", re.compile(r"conclu|closing remarks|summary|future work", re.I)),
    ("discussion", re.compile(r"discussion|limitation", re.I)),
    ("experiments", re.compile(r"experiment|evaluation|empirical|simulation|numerical stud|\bresults?\b", re.I)),
    ("preliminaries", re.compile(r"prelim|background|notation|problem (?:setup|formulation|statement)|setting", re.I)),
]
KIND_ORDER = ["front", "introduction", "related", "preliminaries", "body", "experiments", "discussion",
              "conclusion"]
SMALL = {"a", "an", "the", "and", "or", "but", "nor", "for", "of", "on", "in", "to", "at", "by", "with", "from",
         "via", "vs", "as", "into", "onto", "over", "under", "per", "is", "are", "be"}
MIN_SECTIONS = 3          # a sample with fewer top-level sections is treated as part of a paper
SHOWN = {"front": "abstract", "body": "method/theory"}


def _r(x, k=3):
    return round(float(x), k)


def _blank_keep_lines(m):
    return "\n" * m.group(0).count("\n")


def clean_tex(raw: str) -> str:
    """Drop comments and dead blocks but keep every newline, so line numbers stay valid."""
    lines = [re.sub(r"(?<!\\)%.*", "", ln) for ln in raw.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\\begin\{comment\}.*?\\end\{comment\}", _blank_keep_lines, text, flags=re.S)
    text = re.sub(r"\\iffalse(?![A-Za-z]).*?\\fi(?![A-Za-z])", _blank_keep_lines, text, flags=re.S)
    return text


def clean_title(title: str) -> str:
    t = re.sub(r"\\texorpdfstring\s*\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", title)
    t = re.sub(r"\$[^$]*\$|\\\(.*?\\\)", "X", t)
    t = re.sub(r"\\(label|ref|cref|Cref|cite\w*)\s*\{[^}]*\}", "", t)
    t = re.sub(r"\\[A-Za-z]+\*?\s*", "", t)
    t = t.replace("{", "").replace("}", "").replace("~", " ")
    return " ".join(t.split())


def title_case(title: str):
    """'title' (Most Words Capitalised), 'sentence' (only the first word) or None when undecidable."""
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", title)
    content = [w for w in words[1:] if w.lower() not in SMALL and not (len(w) > 1 and w.isupper())]
    if not content:
        return None
    caps = sum(w[0].isupper() for w in content) / len(content)
    if caps >= 0.75:
        return "title"
    if caps <= 0.5:
        return "sentence"
    return None


def classify(title: str, region: str) -> str:
    if region == "appendix":
        return "appendix"
    for kind, rx in KINDS:
        if rx.search(title):
            return kind
    return "body"


def _tex_headings(path: Path):
    """[(line, level, title, region, excluded)], [(line, input target)] for one LaTeX file."""
    text = clean_tex(path.read_text(encoding="utf-8", errors="replace"))
    start = text.find("\\begin{document}")
    start = 0 if start < 0 else start
    appendix_at = [m.start() for m in APPENDIX_RE.finditer(text, start)]
    heads, inputs = [], []
    for m in HEAD_RE.finditer(text, start):
        j = m.end()
        while j < len(text) and text[j] in " \t\n":
            j += 1
        if j < len(text) and text[j] == "[":
            depth = 0
            while j < len(text):
                depth += text[j] == "["
                depth -= text[j] == "]"
                j += 1
                if depth == 0:
                    break
            while j < len(text) and text[j] in " \t\n":
                j += 1
        if j >= len(text) or text[j] != "{":
            continue
        raw_title, _ = read_group(text, j)
        title = clean_title(raw_title)
        line = text.count("\n", 0, m.start()) + 1
        region = "appendix" if any(a < m.start() for a in appendix_at) else "main"
        heads.append((line, LEVELS[m.group(1)], title, region, bool(EXCLUDED_SECTION_RE.search(title))))
    for m in INPUT_RE.finditer(text, start):
        inputs.append((text.count("\n", 0, m.start()) + 1, m.group(1).strip()))
    return heads, inputs, [text.count("\n", 0, a) + 1 for a in appendix_at]


def _md_headings(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
    heads, fence = [], False
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        m = None if fence else re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", ln)
        if m:
            title = re.sub(r"[*_`]", "", m.group(2))
            heads.append([i, len(m.group(1)), title, "main", bool(EXCLUDED_SECTION_RE.search(title))])
    h1 = [h for h in heads if h[1] == 1]
    if len(h1) == 1 and heads and heads[0][1] == 1:        # the document title, not a section
        heads = heads[1:]
        for h in heads:
            h[1] -= 1
    else:
        top = min((h[1] for h in heads), default=1)
        for h in heads:
            h[1] -= top - 1
    for h in heads:
        if re.match(r"(?i)appendi(x|ces)\b", h[2]):
            h[3] = "appendix"
    for k in range(1, len(heads)):
        if heads[k - 1][3] == "appendix":
            heads[k][3] = "appendix"
    return [tuple(h) for h in heads], [], []


def _units(path: Path, config, sample_set, seen: set):
    """Ordered list of ('head', line, level, title, region, excluded) and ('words', n, region) items."""
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    fmt = prose.detect_format(path)
    if fmt == "tex":
        heads, inputs, appx_lines = _tex_headings(path)
    elif fmt == "md":
        heads, inputs, appx_lines = _md_headings(path)
    else:
        return []
    doc = prose.extract(path, config=config)
    events = [(h[0], 0, ("head",) + h) for h in heads] + [(ln, 0, ("appx",)) for ln in appx_lines]
    for p in doc.paragraphs:
        events.append((p.start_line, 1, ("words", p.n_words, p.region)))
    for line, target in inputs:
        cand = (path.parent / target)
        cand = cand if cand.suffix else cand.with_suffix(".tex")
        if (cand.resolve() in sample_set) if sample_set is not None else cand.is_file():
            events.append((line, 2, ("input", cand.resolve())))
    out = []
    for _, _, ev in sorted(events, key=lambda e: (e[0], e[1])):
        if ev[0] == "input":
            out.extend(_units(ev[1], config, sample_set, seen))
        else:
            out.append(ev)
    return out


def paper_structure(units, label: str) -> dict:
    """Sections with their own words, and top-level sections with their total words."""
    sections, front, region = [], 0, "main"
    cur, concluded = None, False
    for u in units:
        if u[0] == "appx":
            region = "appendix"
            continue
        if u[0] == "head":
            _, line, level, title, reg, excluded = u
            if level <= 1 and not excluded and concluded and classify(title, "main") not in ("conclusion", "discussion"):
                region = "appendix"        # supplementary sections after the conclusion, with no \appendix
            region = "appendix" if (reg == "appendix" or region == "appendix") else "main"
            if level <= 1 and region == "main" and classify(title, region) == "conclusion":
                concluded = True
            cur = {"level": level, "title": title, "region": region, "excluded": excluded, "words": 0,
                   "kind": classify(title, region) if level <= 1 else None}
            sections.append(cur)
        else:
            _, n, reg = u
            if cur is None:
                front += n
            else:
                cur["words"] += n
    live = [s for s in sections if not s["excluded"]]
    # top-level sections: level <= 1, with the words of everything under them
    tops, top = [], None
    for s in sections:
        if s["level"] <= 1:
            top = dict(s, total=s["words"], lead=s["words"], children=0, run_in=0)
            tops.append(top)
        elif top is not None:
            top["total"] += s["words"]
            top["children"] += s["level"] == 2
            top["run_in"] += s["level"] == 4
    tops = [t for t in tops if not t["excluded"]]
    main = [t for t in tops if t["region"] == "main"]
    main_words = front + sum(t["total"] for t in main)
    appx_words = sum(t["total"] for t in tops if t["region"] == "appendix")
    by_kind = {}
    if front:
        by_kind["front"] = front
    for t in main:
        by_kind[t["kind"]] = by_kind.get(t["kind"], 0) + t["total"]
    order = []
    for t in main:
        if not order or order[-1] != t["kind"]:
            order.append(t["kind"])
    return {
        "source": label,
        "complete": "introduction" in order and len(main) >= MIN_SECTIONS and main_words >= 1000,
        "main_words": main_words, "appendix_words": appx_words,
        "appendix_share": _r(appx_words / (main_words + appx_words)) if main_words + appx_words else 0.0,
        "order": order,
        "words_by_kind": by_kind,
        "share_by_kind": {k: _r(v / main_words) for k, v in by_kind.items()} if main_words else {},
        "sections": len(main),
        "subsections_per_section": _r(statistics.median([t["children"] for t in main]), 1) if main else 0,
        "run_in_headings": sum(1 for s in live if s["level"] == 4),
        "subsubsections": sum(1 for s in live if s["level"] == 3),
        "lead_words": [t["lead"] for t in main if t["children"] or t["run_in"]],
        "titles": [[s["level"], s["title"], s["region"]] for s in live if s["level"] <= 3],
    }


def measure(paths, config=None, follow_inputs=False) -> list:
    """One structure record per paper; a sample \\input by another sample is part of that paper.

    follow_inputs: also read \\input files that were not given (for a draft's main file)."""
    paths = [Path(p) for p in prose.collect_sources(paths)]
    labels = prose.source_labels(paths)
    sample_set = {p.resolve() for p in paths}
    included = set()
    for p in paths:
        if prose.FORMATS.get(p.suffix.lower()) == "tex":
            _, inputs, _ = _tex_headings(p)
            for _, target in inputs:
                cand = p.parent / target
                cand = cand if cand.suffix else cand.with_suffix(".tex")
                if cand.resolve() in sample_set and cand.resolve() != p.resolve():
                    included.add(cand.resolve())
    papers = []
    for p in paths:
        if p.resolve() in included or prose.FORMATS.get(p.suffix.lower()) not in ("tex", "md"):
            continue
        units = _units(p, config, None if follow_inputs else sample_set, set())
        rec = paper_structure(units, labels[p])
        if rec["sections"] or rec["titles"]:
            papers.append(rec)
    return papers


def _span(values):
    values = sorted(values)
    return [_r(values[0]), _r(statistics.median(values)), _r(values[-1])] if values else None


def summarize(papers: list) -> dict:
    complete = [p for p in papers if p["complete"]]
    titles = [t for p in papers for t in p["titles"]]
    styles = [title_case(t[1]) for t in titles]
    decided = [s for s in styles if s]
    n_main_words = sum(p["main_words"] for p in complete) or 1
    kinds = sorted({k for p in complete for k in p["share_by_kind"]}, key=KIND_ORDER.index)
    summary = {
        "n_papers": len(papers), "n_complete": len(complete),
        "complete_papers": [p["source"] for p in complete],
        "order": [p["order"] for p in complete],
        "share_by_kind": {k: _span([p["share_by_kind"][k] for p in complete if k in p["share_by_kind"]])
                          for k in kinds},
        "words_by_kind": {k: _span([p["words_by_kind"][k] for p in complete if k in p["words_by_kind"]])
                          for k in kinds},
        "present_in": {k: sum(k in p["share_by_kind"] for p in complete) for k in kinds},
        "appendix_share": _span([p["appendix_share"] for p in complete]),
        "subsections_per_section": _span([p["subsections_per_section"] for p in complete]),
        "run_in_per_1k": _r(1000 * sum(p["run_in_headings"] for p in complete) / n_main_words, 2),
        "subsubsections": sum(p["subsubsections"] for p in complete),
        "lead_words_median": _r(statistics.median([w for p in complete for w in p["lead_words"]]), 0)
        if any(p["lead_words"] for p in complete) else None,
        "titles": {
            "n": len(titles),
            "words_median": _r(statistics.median([len(t[1].split()) for t in titles]), 1) if titles else 0,
            "case": {"sentence": decided.count("sentence"), "title": decided.count("title"),
                     "undecided": len(styles) - len(decided)},
            "colon_share": _r(sum(":" in t[1] for t in titles) / len(titles)) if titles else 0.0,
            "examples": [t[1] for t in titles if t[0] <= 2 and t[2] == "main"][:10],
        },
    }
    return summary


def profile_structure(paths, config=None) -> dict:
    papers = measure(paths, config)
    return {"papers": papers, "summary": summarize(papers)}


def dominant_case(summary):
    case = (summary.get("titles") or {}).get("case") or {}
    s, t = case.get("sentence", 0), case.get("title", 0)
    if s + t < 4:
        return None
    if s / (s + t) >= 0.7:
        return "sentence"
    if t / (s + t) >= 0.7:
        return "title"
    return None


def describe(summary: dict) -> list:
    """Short lines on the author's structure, for voice_rules.py and author_voice.md."""
    if not summary or not summary.get("n_papers"):
        return []
    out = []
    n = summary["n_complete"]
    if n:
        orders = [" → ".join(SHOWN.get(k, k) for k in o) for o in summary["order"]]
        if len(set(orders)) == 1:
            out.append(f"Section order in all {n} complete papers: {orders[0]}.")
        else:
            out.append("Section order: " + "; ".join(f"{o} ({orders.count(o)} of {n})"
                                                   for o in dict.fromkeys(orders)) + ".")
        parts = []
        for k in ("introduction", "conclusion"):
            w = summary["words_by_kind"].get(k)
            if w:
                parts.append(f"{k} {int(w[0])}-{int(w[2])} words")
        if summary.get("appendix_share"):
            a = summary["appendix_share"]
            parts.append(f"appendix {a[0]:.0%}-{a[2]:.0%} of all words")
        if parts:
            out.append("Lengths: " + "; ".join(parts) + ".")
    t = summary["titles"]
    case = dominant_case(summary)
    out.append(f"Titles: median {t['words_median']:g} word{'' if t['words_median'] == 1 else 's'}; "
               + (f"mostly {case} case" if case else "mixed capitalisation")
               + f" ({t['case']['sentence']} sentence-case, {t['case']['title']} title-case); "
               + f"colon in {t['colon_share']:.0%}.")
    heads = ("Headings: " + (f"about {summary['run_in_per_1k']:.1f} run-in paragraph headings per 1,000 words"
                             if summary["run_in_per_1k"] else "no run-in paragraph headings"))
    if summary.get("subsections_per_section"):
        heads += f", {summary['subsections_per_section'][1]:g} subsections per section (median)"
    if summary.get("lead_words_median") is not None:
        heads += f", and a lead of about {int(summary['lead_words_median'])} words before the first subsection"
    out.append(heads + ".")
    return out


def compare(draft_paths, base: dict, config=None) -> dict:
    """Structure of a draft against the author's baseline: rows to report, never rules."""
    papers = measure(draft_paths, config, follow_inputs=True)
    rows, notes = [], []
    if not papers:
        return {"rows": rows, "notes": ["No headings found in the draft."], "whole": False}
    p = papers[0]
    s = base.get("summary") or {}
    whole = "introduction" in p["order"] and p["sections"] >= MIN_SECTIONS
    if whole and s.get("n_complete"):
        for k, span in s.get("share_by_kind", {}).items():
            if k == "front":
                continue
            mine = p["share_by_kind"].get(k)
            if mine is None:
                if s["present_in"].get(k) == s["n_complete"]:
                    rows.append({"item": f"{SHOWN.get(k, k)} section", "draft": "missing",
                                 "author": f"in all {s['n_complete']} papers", "flag": True})
                continue
            lo, hi = span[0], span[2]
            rows.append({"item": f"{SHOWN.get(k, k)} share of the main text", "draft": f"{mine:.0%}",
                         "author": f"{lo:.0%}-{hi:.0%}", "flag": mine < lo / 1.5 or mine > hi * 1.5})
        a = s.get("appendix_share")
        if a and p["appendix_words"]:
            rows.append({"item": "appendix share", "draft": f"{p['appendix_share']:.0%}",
                         "author": f"{a[0]:.0%}-{a[2]:.0%}", "flag": False})
        base_run = s.get("run_in_per_1k", 0)
        mine_run = 1000 * p["run_in_headings"] / max(p["main_words"], 1)
        rows.append({"item": "run-in paragraph headings / 1k words", "draft": f"{mine_run:.1f}",
                     "author": f"{base_run:g}", "flag": base_run >= 1 and mine_run == 0})
    else:
        notes.append("The draft looks like part of a paper, so only its headings are compared.")
    case = dominant_case(s)
    if case:
        other = [t[1] for t in p["titles"] if title_case(t[1]) not in (None, case)]
        rows.append({"item": f"titles not in {case} case", "draft": str(len(other)), "author": f"mostly {case} case",
                     "flag": bool(other)})
        if other:
            notes.append("Titles in the other case: " + "; ".join(f"\"{t}\"" for t in other[:6]) + ".")
    tw = (s.get("titles") or {}).get("words_median")
    if tw and p["titles"]:
        mine = statistics.median([len(t[1].split()) for t in p["titles"]])
        rows.append({"item": "title length, median words", "draft": f"{mine:g}", "author": f"{tw:g}",
                     "flag": mine > 2 * tw or mine < tw / 2})
    return {"rows": rows, "notes": notes, "whole": whole}
