#!/usr/bin/env python3
"""Keep only the edits that preserve the author's voice; revert the rest.

usage:
  python diff_guard.py original.tex edited.tex --profile author_profile.json \\
      --merged merged.tex --report guard.md [--json guard.json] [--budget 0.2] \\
      [--allow-new-sentences] [--strict]

Works on LaTeX and Markdown/plain-text drafts. Each changed group of source lines (an
"edit") is judged on its own, so one bad line does not take clean neighbouring fixes with it.

FLAG (the edit is reverted in merged.tex):
  - touches the preamble/front matter, display math, a theorem-like statement, a proof or a code block
  - adds, removes or changes a citation key, a number, or inline/display math
  - introduces a tier-A word, or a device the author never uses (em dash, contraction, "!")
  - adds a sentence (unless --allow-new-sentences)
WARN (the edit is kept and listed for the author):
  - introduces tier-B words, AI-favoured sentence openers, or a device the author does use
  - deletes or splits a sentence, changes a paragraph break, edits a heading or a float
  - joins sentences onto one line when the author writes one sentence per line
  - the paragraph as a whole changed by more than --budget of its words
  - the paragraph's sentence rhythm got flatter, or it gained a summary-style closing sentence

Exit code: 0 when nothing was reverted, 1 when some edits were reverted (merged.tex is
written either way), 2 on usage errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prose                # noqa: E402
import tells as tl          # noqa: E402
import texprose             # noqa: E402
from textcore import split_sentences, words_of  # noqa: E402

TEX_CITE_RE = re.compile(r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|nocite|"
                         r"parencite|Parencite|textcite|Textcite|autocite|Autocite|footcite|supercite|smartcite)\*?"
                         r"(?:\s*\[[^\]]*\])*\s*\{([^}]*)\}")
MD_CITE_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9_][\w:.#$%&+?~/-]*\w)")
REFLIKE_RE = re.compile(r"\\(?:label|ref|cref|Cref|eqref|autoref|pageref|nameref|url|href|includegraphics|"
                        r"includesvg|input|include|bibliography|bibliographystyle)\*?(?:\s*\[[^\]]*\])*\s*\{[^}]*\}")
INLINE_MATH_RE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$", re.S)
DISPLAY_RE = re.compile(r"\\begin\s*\{(?:equation|align|gather|multline|eqnarray|displaymath|alignat|flalign)\*?\}|"
                        r"(?<!\\)\$\$|\\\[")
NUM_RE = re.compile(r"(?<![A-Za-z_\\])\d+(?:\.\d+)?%?")
LABELS = {"tex": {"preamble": "touches the preamble", "frozen": "touches a theorem/definition/proof"},
          "md": {"preamble": "touches the front matter", "frozen": "touches a code block"}}


def read_raw(path) -> str:
    """Read without newline translation so CRLF files come back out as CRLF."""
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def write_raw(path, text: str):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def profile_includes(pr, raw: str):
    """Name of the profile source whose hash matches this text, else None."""
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    for src in (pr or {}).get("sources", []):
        if src.get("sha256") == h:
            return src.get("file")
    return None


def _nocomment(raw: str, fmt: str) -> str:
    if fmt == "tex":
        return "\n".join(texprose.strip_comment(l) for l in raw.split("\n"))
    return re.sub(r"(?s)<!--.*?-->", " ", raw)


def cite_keys(raw: str, fmt: str) -> Counter:
    c = Counter()
    t = _nocomment(raw, fmt)
    if fmt == "tex":
        for m in TEX_CITE_RE.finditer(t):
            for k in m.group(1).split(","):
                if k.strip():
                    c[k.strip()] += 1
    else:
        t = re.sub(r"`[^`]*`", " ", t)
        t = re.sub(r"\S+@\S+\.\w+", " ", t)          # e-mail addresses are not citations
        for m in MD_CITE_RE.finditer(t):
            c[m.group(1)] += 1
    return c


def _norm_math(m: str) -> str:
    m = re.sub(r"\s+", "", m)
    m = re.sub(r"(\\[,;:! ]|\\q?quad)+$", "", m)
    return m.rstrip(".,;:")


def inline_math(raw: str, fmt: str):
    """Counter of normalised inline-math strings, or None when $ signs are unbalanced."""
    t = _nocomment(raw, fmt)
    if fmt == "md":
        t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", " ", t, flags=re.S)
    if len(re.findall(r"(?<!\\)\$", t)) % 2:
        return None
    return Counter(_norm_math(m) for m in INLINE_MATH_RE.findall(t))


def numbers(raw: str, fmt: str) -> Counter:
    t = _nocomment(raw, fmt)
    if fmt == "tex":
        t = TEX_CITE_RE.sub(" ", t)
        t = REFLIKE_RE.sub(" ", t)
    else:
        t = re.sub(r"`[^`]*`", " ", t)
        t = re.sub(r"\]\([^)]*\)", "]", t)          # link targets
        t = re.sub(r"https?://\S+", " ", t)
        t = re.sub(r"\[\^[^\]]+\]", " ", t)          # footnote markers
        t = MD_CITE_RE.sub(" ", t)
    t = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", " ", t, flags=re.S)
    t = INLINE_MATH_RE.sub(" ", t)
    t = re.sub(r"\\[A-Za-z]+\d*", " ", t)          # command names like \section2 are not numbers
    return Counter(NUM_RE.findall(t))


def word_change_ratio(a_words, b_words) -> float:
    a = [w.lower() for w in a_words]
    b = [w.lower() for w in b_words]
    sm = SequenceMatcher(None, a, b, autojunk=False)
    changed = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")
    return changed / max(1, len(a))


def short_diff(a: str, b: str, limit: int = 180) -> str:
    """Compact word-level description of what changed: 'old -> new; ...'"""
    aw, bw = a.split(), b.split()
    parts = []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, aw, bw, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        old, new = " ".join(aw[i1:i2]), " ".join(bw[j1:j2])
        parts.append(f"'{old}' -> '{new}'" if old and new else (f"+'{new}'" if new else f"-'{old}'"))
    s = "; ".join(parts)
    return s if len(s) <= limit else s[:limit] + " ..."


def _sim(x: str, y: str) -> float:
    return SequenceMatcher(None, x.strip(), y.strip(), autojunk=False).ratio()


def split_block(a_lines, b_lines, i1, i2, j1, j2, cutoff=0.5):
    """Split a changed block into the smallest independent edits.

    Lines are paired by best similarity (as difflib.Differ does), so one bad line does
    not drag its clean neighbours into the revert. A block whose text was only re-broken
    (a sentence split or joined across lines) stays together so it is judged as a whole.
    """
    if i2 <= i1 or j2 <= j1:
        return [(i1, i2, j1, j2)] if (i2 > i1 or j2 > j1) else []
    m, n = i2 - i1, j2 - j1
    if m != n:
        ja = " ".join(l.strip() for l in a_lines[i1:i2])
        jb = " ".join(l.strip() for l in b_lines[j1:j2])
        if _sim(ja, jb) >= 0.85:
            return [(i1, i2, j1, j2)]
    if m * n > 2500:
        return [(i1, i2, j1, j2)]
    best, bi, bj = cutoff, None, None
    for i in range(i1, i2):
        for j in range(j1, j2):
            r = _sim(a_lines[i], b_lines[j])
            if r > best:
                best, bi, bj = r, i, j
    if bi is None:
        return [(i1, i2, j1, j2)]
    mid = [] if a_lines[bi].rstrip() == b_lines[bj].rstrip() else [(bi, bi + 1, bj, bj + 1)]
    return (split_block(a_lines, b_lines, i1, bi, j1, bj, cutoff) + mid
            + split_block(a_lines, b_lines, bi + 1, i2, bj + 1, j2, cutoff))


class Hunk:
    def __init__(self, i1, i2, j1, j2, a_lines, b_lines):
        self.i1, self.i2, self.j1, self.j2 = i1, i2, j1, j2
        self.a = "\n".join(a_lines[i1:i2])
        self.b = "\n".join(b_lines[j1:j2])
        self.flags, self.warns, self.notes = [], [], []
        self.ratio, self.summary = 0.0, ""

    @property
    def status(self):
        return "FLAG" if self.flags else ("WARN" if self.warns else "OK")

    def where(self):
        a = (f"l.{self.i1 + 1}-{self.i2}" if self.i2 > self.i1 + 1 else
             (f"l.{self.i1 + 1}" if self.i2 > self.i1 else f"after l.{self.i1}"))
        b = (f"l.{self.j1 + 1}-{self.j2}" if self.j2 > self.j1 + 1 else
             (f"l.{self.j1 + 1}" if self.j2 > self.j1 else "(deleted)"))
        return a, b


def check_hunk(h: Hunk, kinds: dict, n_orig: int, fmt: str, rules: tl.Rules, allow_new_sentences: bool):
    # ---- where does it sit in the original?
    if h.i2 > h.i1:
        ks = {kinds.get(ln, "prose") for ln in range(h.i1 + 1, h.i2 + 1)}
    else:
        ks = {kinds.get(max(1, h.i1), "prose"), kinds.get(min(n_orig, h.i1 + 1), "prose")}
        ks.discard("blank")
        ks = ks or {"prose"}
        if ks & {"preamble", "frozen", "math"} and not ks <= {"preamble", "frozen", "math"}:
            ks -= {"preamble", "frozen", "math"}        # insertion at a boundary next to prose
    labels = LABELS[fmt]
    if "preamble" in ks:
        h.flags.append(labels["preamble"])
    if "frozen" in ks:
        h.flags.append(labels["frozen"])
    if "math" in ks:
        h.flags.append("touches display math")
    if "float" in ks:
        h.warns.append("edits text inside a float or table - check")
    if "heading" in ks:
        h.warns.append("changes a heading")

    # ---- frozen content
    if cite_keys(h.a, fmt) != cite_keys(h.b, fmt):
        h.flags.append("citation keys changed")
    na, nb = numbers(h.a, fmt), numbers(h.b, fmt)
    if nb - na:
        h.flags.append("new or changed number(s): " + ", ".join(sorted((nb - na).elements()))[:80])
    elif na - nb:
        h.warns.append("number(s) removed: " + ", ".join(sorted((na - nb).elements()))[:80])
    if len(DISPLAY_RE.findall(_nocomment(h.a, fmt))) != len(DISPLAY_RE.findall(_nocomment(h.b, fmt))):
        h.flags.append("display math added or removed")

    # ---- prose-level checks
    pa, pb = prose.fragment_prose(h.a, fmt), prose.fragment_prose(h.b, fmt)
    sa, sb = split_sentences(pa), split_sentences(pb)
    a_hard = tl.count_tier(pa, rules.tier_a_hard)
    for k, v in tl.count_tier(pb, rules.tier_a_hard).items():
        if v > a_hard.get(k, 0):
            h.flags.append(f"introduces tier-A '{k}'")
    ca, cb = tl.structural_counts(pa), tl.structural_counts(pb)
    more_dashes = tl.dashes(cb) > tl.dashes(ca) or (fmt == "tex" and h.b.count("---") > h.a.count("---"))
    for device, added, label in (("em_dash", more_dashes, "an em dash"),
                                 ("contraction", cb["contraction"] > ca["contraction"], "a contraction"),
                                 ("exclamation", cb["exclamation"] > ca["exclamation"], "an exclamation mark")):
        if added:
            if device in rules.hard_devices:
                h.flags.append(f"introduces {label}")
            else:
                h.warns.append(f"introduces {label} (the author uses them; check the rate)")
    if len(sb) > len(sa):
        wa_, wb_ = [w.lower() for w in words_of(pa)], [w.lower() for w in words_of(pb)]
        added = sum(j2 - j1 for op, i1, i2, j1, j2 in SequenceMatcher(None, wa_, wb_, autojunk=False).get_opcodes()
                    if op in ("insert", "replace"))
        if sa and added <= 2:
            h.warns.append("splits a sentence in two - check it still reads like the author")
        else:
            msg = f"adds {len(sb) - len(sa)} sentence(s)"
            (h.warns if allow_new_sentences else h.flags).append(msg)
    elif len(sb) < len(sa):
        h.warns.append(f"removes {len(sa) - len(sb)} sentence(s)")
    soft_a, soft_b = tl.count_tier(pa, rules.tier_soft), tl.count_tier(pb, rules.tier_soft)
    new_soft = [k for k, v in soft_b.items() if v > soft_a.get(k, 0) and k not in rules.own_soft]
    if new_soft:
        h.warns.append("introduces tier-B " + ", ".join(f"'{k}'" for k in new_soft))
    oa = [rules.avoided_opener(s.text) for s in sa]
    ob = [rules.avoided_opener(s.text) for s in sb]
    if sum(1 for o in ob if o) > sum(1 for o in oa if o):
        h.warns.append("adds an AI-favoured sentence opener (" + ", ".join(sorted({o for o in ob if o})) + ")")
    if rules.keeps_one_sentence_per_line:
        a_nonblank = [l for l in h.a.split("\n") if l.strip() and not l.strip().startswith("%")]
        b_nonblank = [l for l in h.b.split("\n") if l.strip() and not l.strip().startswith("%")]
        if len(sa) >= 2 and len(b_nonblank) < len(a_nonblank) and len(sb) >= len(sa):
            h.warns.append("joins sentences onto one source line (the author writes one sentence per line)")
    blank_a = sum(1 for l in h.a.split("\n") if not l.strip()) if h.i2 > h.i1 else 0
    blank_b = sum(1 for l in h.b.split("\n") if not l.strip()) if h.j2 > h.j1 else 0
    if blank_a != blank_b:
        h.warns.append("paragraph break added or removed")
    after = [x for x, _ in tl.watchlist_hits(pb, rules.watchlist)]
    fixed = [m for m, _ in tl.watchlist_hits(pa, rules.watchlist) if m not in after]
    if fixed:
        h.notes.append("fixes recurring slip: " + ", ".join(f"'{m}'" for m in fixed))
    h.ratio = word_change_ratio(words_of(pa), words_of(pb)) if pa else 1.0
    h.summary = short_diff(pa, pb) if pa != pb else "markup-only change (prose identical): " + short_diff(h.a, h.b)


def build(a_lines, b_lines, hunks, accepted):
    """Return merged lines and the 0-based orig->merged line map."""
    merged, o2m = [], [0] * (len(a_lines) + 1)
    pos_a = 0
    for h in hunks + [None]:
        stop = h.i1 if h else len(a_lines)
        for k in range(pos_a, stop):                 # unchanged block
            o2m[k] = len(merged)
            merged.append(a_lines[k])
        if h is None:
            break
        if h in accepted:
            start = len(merged)
            merged.extend(b_lines[h.j1:h.j2])
            for k in range(h.i1, h.i2):
                o2m[k] = start + min(k - h.i1, max(0, h.j2 - h.j1 - 1))
        else:
            for k in range(h.i1, h.i2):
                o2m[k] = len(merged)
                merged.append(a_lines[k])
        pos_a = h.i2
    o2m[len(a_lines)] = len(merged)
    return merged, o2m


def merged_paragraph(doc_m, ms, me, footnote=False):
    return [s for p in doc_m.paragraphs
            if p.footnote == footnote and not (p.end_line < ms or p.start_line > me) for s in p.sentences]


def guard(orig_path, edit_path, pr, budget=0.2, allow_new_sentences=False, strict=False, fmt=None):
    fmt = fmt or prose.detect_format(orig_path)
    if fmt not in prose.DRAFT_FORMATS:
        raise SystemExit(f"diff_guard works on LaTeX and Markdown/text drafts, not {fmt}")
    rules = tl.Rules(pr)
    config = (pr or {}).get("config")
    a_text = read_raw(orig_path)
    b_text = read_raw(edit_path)
    a_lines, b_lines = a_text.split("\n"), b_text.split("\n")
    doc_a = prose.extract_text(a_text, fmt, config)
    sm = SequenceMatcher(None, [l.rstrip() for l in a_lines], [l.rstrip() for l in b_lines], autojunk=False)
    spans = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace":
            spans += split_block(a_lines, b_lines, i1, i2, j1, j2)
        elif op != "equal":
            spans.append((i1, i2, j1, j2))
    hunks = [Hunk(i1, i2, j1, j2, a_lines, b_lines) for i1, i2, j1, j2 in spans]
    for h in hunks:
        check_hunk(h, doc_a.line_kind, len(a_lines), fmt, rules, allow_new_sentences)

    # inline math: compare the whole source block (between blank lines) with only this edit applied,
    # so $...$ that spans several lines is still compared as a unit
    for h in hunks:
        bs = h.i1
        while bs > 0 and a_lines[bs - 1].strip():
            bs -= 1
        be = h.i2
        while be < len(a_lines) and a_lines[be].strip():
            be += 1
        ra = "\n".join(a_lines[bs:be])
        rb = "\n".join(a_lines[bs:h.i1] + b_lines[h.j1:h.j2] + a_lines[h.i2:be])
        ma, mb = inline_math(ra, fmt), inline_math(rb, fmt)
        if ma is None or mb is None:
            if ma != mb:
                h.flags.append("unbalanced $ after the edit")
            elif "$" in h.a + h.b:
                h.warns.append("could not verify inline math in this block; check by eye")
        elif ma != mb:
            h.flags.append("inline math changed")

    accepted = {h for h in hunks if not h.flags}
    merged, o2m = build(a_lines, b_lines, hunks, accepted)
    doc_m = prose.extract_text("\n".join(merged), fmt, config)

    # paragraph-level checks on what will actually be delivered
    para_notes = []
    b_p10 = (pr or {}).get("paragraph", {}).get("cv_p10", 0.15)
    by_para = {}
    for h in accepted:
        lo, hi = h.i1 + 1, max(h.i1 + 1, h.i2)
        for k, p in enumerate(doc_a.paragraphs):
            if not (p.end_line < lo or p.start_line > hi):
                by_para.setdefault(k, []).append(h)
    for key, hs in by_para.items():
        p = doc_a.paragraphs[key]
        ms = o2m[p.start_line - 1] + 1
        me = o2m[p.end_line] if p.end_line < len(a_lines) else len(merged)
        sents_m = merged_paragraph(doc_m, ms, me, p.footnote)
        if not sents_m:
            continue
        wa = [w for s in p.sentences for w in s.words]
        wb = [w for s in sents_m for w in s.words]
        ratio = word_change_ratio(wa, wb)
        if ratio == 0:
            continue
        msgs = []
        what = "footnote" if p.footnote else "paragraph"
        if ratio > budget:
            msgs.append(f"{what} l.{p.start_line}-{p.end_line} changed by {ratio:.0%} of its words (budget {budget:.0%})")
        if len(sents_m) >= 4:
            ca = tl.cv(s.n_words for s in p.sentences)
            cb = tl.cv(s.n_words for s in sents_m)
            if cb < min(ca, b_p10) - 0.03:
                msgs.append(f"{what} rhythm flattened (sentence-length CV {ca:.2f} -> {cb:.2f})")
        if len(sents_m) >= 3 and tl.is_summary_closer(sents_m[-1].text) and not tl.is_summary_closer(p.sentences[-1].text):
            msgs.append(f"{what} now ends with a summary-style sentence")
        for h in hs:
            h.warns.extend(m for m in msgs if m not in h.warns)
        if msgs:
            para_notes.append({"lines": [p.start_line, p.end_line], "issues": msgs})

    if strict:                                   # unattended runs: keep only clean edits
        for h in hunks:
            if h.warns and not h.flags:
                h.flags.append("strict mode: " + h.warns[0])
        accepted = {h for h in hunks if not h.flags}
        merged, o2m = build(a_lines, b_lines, hunks, accepted)
        doc_m = prose.extract_text("\n".join(merged), fmt, config)

    # document-level figures
    overall = word_change_ratio(doc_a.words(), doc_m.words())
    deltas = {}
    fw = (pr or {}).get("function_words") or {}
    if fw.get("mu") and fw.get("delta_loo_p95"):
        for name, d in (("original", doc_a), ("merged", doc_m)):
            chunks = tl.chunk_words(d.paragraphs, fw.get("chunk_size", 500))
            vals = [tl.burrows_delta(tl.fw_freqs(c), fw["mu"], fw["sd"]) for c in chunks]
            deltas[name] = round(sum(vals) / len(vals), 3) if vals else None
        deltas["author_p95"] = fw.get("delta_loo_p95")
    soft = {}
    for name, d in (("original", doc_a), ("merged", doc_m)):
        txt = "\n".join(p.text for p in d.paragraphs)
        soft[name] = round(tl.rate(sum(tl.count_tier(txt, rules.tier_soft).values()), len(d.words())), 2)

    return {
        "circular": profile_includes(pr, a_text), "format": fmt,
        "original": str(orig_path), "edited": str(edit_path), "budget": budget,
        "hunks": hunks, "merged": merged, "overall_change": overall, "deltas": deltas, "tierB": soft,
        "para_notes": para_notes,
    }


def _fence(text: str, sign: str, limit=8) -> list:
    lines = text.split("\n")
    out = [f"{sign} {l}" for l in lines[:limit]]
    if len(lines) > limit:
        out.append(f"{sign} ... ({len(lines) - limit} more lines)")
    return out


def to_markdown(res) -> str:
    hs = res["hunks"]
    n_flag = sum(h.status == "FLAG" for h in hs)
    n_warn = sum(h.status == "WARN" for h in hs)
    n_ok = sum(h.status == "OK" for h in hs)
    d = res["deltas"]
    out = [f"# Diff guard: {Path(res['original']).name} -> {Path(res['edited']).name}", "",
           f"**{len(hs)} edits (changed line groups): {n_ok} kept clean, {n_warn} kept but need a look, "
           f"{n_flag} reverted.** The merged file is the original plus every edit that was not reverted.", "",
           f"- Prose words changed overall: {res['overall_change']:.1%}",
           f"- Tier-B words per 1k: {res['tierB']['original']} -> {res['tierB']['merged']}"]
    if d.get("original") is not None:
        out.append(f"- Function-word Delta vs author: {d['original']} -> {d['merged']} (author p95 {d['author_p95']})")
    if res.get("circular"):
        out.append(f"- Note: this draft is profile source '{res['circular']}', so baseline figures are partly "
                   "circular. Build a temporary profile from the author's other samples for a fair comparison.")
    out.append("")
    for title, status in (("Reverted (hard rule broken)", "FLAG"), ("Kept, please review", "WARN")):
        sel = [h for h in hs if h.status == status]
        out += [f"## {title} ({len(sel)})", ""]
        if not sel:
            out += ["- none", ""]
        for h in sel:
            a, b = h.where()
            reasons = h.flags + h.warns if status == "FLAG" else h.warns
            out.append(f"### original {a} / edited {b}")
            out.append("- " + "\n- ".join(reasons))
            out.append("```diff")
            out += _fence(h.a, "-") if h.a.strip() else []
            out += _fence(h.b, "+") if h.b.strip() else []
            out += ["```", ""]
    ok = [h for h in hs if h.status == "OK"]
    out += [f"## Kept clean ({len(ok)})", ""]
    for h in ok:
        a, _ = h.where()
        note = f"  [{'; '.join(h.notes)}]" if h.notes else ""
        out.append(f"- {a}: {h.summary}{note}")
    out.append("")
    return "\n".join(out)


def to_json(res) -> dict:
    return {
        "original": res["original"], "edited": res["edited"], "format": res["format"], "budget": res["budget"],
        "overall_change": round(res["overall_change"], 4), "deltas": res["deltas"], "tierB_per_1k": res["tierB"],
        "paragraph_issues": res["para_notes"], "circular": res["circular"],
        "hunks": [{"status": h.status, "original_lines": h.where()[0], "edited_lines": h.where()[1],
                   "flags": h.flags, "warnings": h.warns, "notes": h.notes, "change": h.summary,
                   "word_change_ratio": round(h.ratio, 3)} for h in res["hunks"]],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("edited")
    ap.add_argument("--profile", help="author_profile.json (enables author-relative rules)")
    ap.add_argument("--merged", help="output: original + accepted edits (default: merged.<ext>)")
    ap.add_argument("--report", default="guard.md", help="output: markdown report")
    ap.add_argument("--json", help="output: machine-readable results")
    ap.add_argument("--budget", type=float, default=0.20,
                    help="max share of a paragraph's words the edits may change before a warning")
    ap.add_argument("--allow-new-sentences", action="store_true",
                    help="the author asked for added sentences; report them as WARN instead of reverting")
    ap.add_argument("--strict", action="store_true",
                    help="also revert WARN edits (use when nobody will review the report)")
    a = ap.parse_args()
    pr = json.loads(Path(a.profile).read_text(encoding="utf-8")) if a.profile else None
    try:
        res = guard(a.original, a.edited, pr, budget=a.budget, allow_new_sentences=a.allow_new_sentences,
                    strict=a.strict)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
    merged_path = a.merged or ("merged" + Path(a.original).suffix)
    write_raw(merged_path, "\n".join(res["merged"]))
    Path(a.report).write_text(to_markdown(res), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(to_json(res), indent=1, ensure_ascii=False), encoding="utf-8")
    hs = res["hunks"]
    n_flag = sum(h.status == "FLAG" for h in hs)
    print(f"{len(hs)} edits: {sum(h.status == 'OK' for h in hs)} clean, "
          f"{sum(h.status == 'WARN' for h in hs)} review, {n_flag} reverted -> {merged_path}, report {a.report}")
    sys.exit(1 if n_flag else 0)


if __name__ == "__main__":
    main()
