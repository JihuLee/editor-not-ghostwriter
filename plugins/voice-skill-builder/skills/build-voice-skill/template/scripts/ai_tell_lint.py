#!/usr/bin/env python3
"""Lint a draft for AI-sounding prose, judged against the author's own baseline.

usage:
  python ai_tell_lint.py draft.tex --profile author_profile.json [-o lint.md] [--json lint.json]

Reports (1) hard tells with line numbers, (2) the author's recurring slips, (3) the
paragraphs that read least like the author, ranked, and (4) document-level drift from
the baseline. It never edits anything. Paragraphs it ranks high are candidates for the
AUTHOR to rewrite; they are not an invitation for Claude to rewrite them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prose                # noqa: E402
import tells as tl          # noqa: E402


def load_profile(path):
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _get(pr, *keys, default=0.0):
    cur = pr
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def doc_metrics(doc, rules):
    paras = doc.paragraphs
    sents = [s for p in paras for s in p.sentences]
    words = [w for s in sents for w in s.words]
    text = "\n".join(p.text for p in paras)
    n_w, n_s = max(1, len(words)), max(1, len(sents))
    L = [s.n_words for s in sents] or [0]
    soft = tl.count_tier(text, rules.tier_soft)
    S = tl.structural_counts(text)
    closers = [tl.is_summary_closer(p.sentences[-1].text) for p in paras if len(p.sentences) >= 3]
    bounds = [s.ends_at_line_end for p in paras for s in p.sentences[:-1]]
    return {
        "n_words": len(words), "n_sentences": len(sents),
        "sent_median": statistics.median(L), "sent_mean": statistics.mean(L), "sent_cv": tl.cv(L),
        "share_over_35": sum(x > 35 for x in L) / n_s,
        "one_sentence_per_line": statistics.mean(bounds) if bounds else None,
        "em_dash": tl.rate(tl.dashes(S), n_w),
        "semicolon": tl.rate(S["semicolon"], n_w),
        "hedge": tl.rate(S["hedge"], n_w),
        "intensifier": tl.rate(S["intensifier"], n_w),
        "soft_total": tl.rate(sum(soft.values()), n_w),
        "ai_openers_per_100": 100 * sum(1 for s in sents if tl.ai_opener(s.text)) / n_s,
        "summary_closer_share": (sum(closers) / len(closers)) if closers else 0.0,
        "passive_per_sentence": sum(len(tl.PASSIVE_RE.findall(s.text)) for s in sents) / n_s,
        "soft_counts": dict(soft),
    }


def sentence_tells(s, rules):
    """Hard tells in one sentence: [(what, line)] at the line where each one occurs."""
    out = [(f"tier-A '{k}'", s.line_of(off)) for k, off in tl.find_tells(s.text, rules.tier_a_hard)]
    if "em_dash" in rules.hard_devices:
        out += [("em dash", s.line_of(m.start())) for m in tl.DASH_RE.finditer(s.text)]
    if "contraction" in rules.hard_devices:
        out += [("contraction", s.line_of(m.start())) for m in tl.CONTRACTION_RE.finditer(s.text)]
    if "exclamation" in rules.hard_devices:
        out += [("exclamation", s.line_of(m.start())) for m in tl.EXCLAMATION_RE.finditer(s.text)]
    return out


def paragraph_score(p, pr, rules):
    score, reasons = 0.0, []
    op_rates = _get(pr, "ai_openers_per_100_sentences", default={}) or {}
    for s in p.sentences:
        for k, off in tl.find_tells(s.text, rules.tier_a_hard):
            score += 3
            reasons.append(f"tier-A '{k}' (l.{s.line_of(off)})")
        for m in tl.DASH_RE.finditer(s.text):
            score += 3 / (1 + rules.device_rates["em_dash"])
            reasons.append(f"em dash (l.{s.line_of(m.start())})")
        for device, rx in (("contraction", tl.CONTRACTION_RE), ("exclamation", tl.EXCLAMATION_RE)):
            if device in rules.hard_devices:
                for m in rx.finditer(s.text):
                    score += 2
                    reasons.append(f"{device} (l.{s.line_of(m.start())})")
        o = tl.ai_opener(s.text)
        if o and o in rules.allow:
            o = None
        if o:
            score += 1 / (1 + op_rates.get(o, 0.0))
            reasons.append(f"opener '{o}' (l.{s.line})")
        for k, off in tl.find_tells(s.text, rules.tier_soft):
            if o and off == 0 and k == o:          # the opener was already counted once
                continue
            score += 1 / (1 + rules.soft_rate(k))
            reasons.append(f"'{k}' (l.{s.line_of(off)})")
    n = len(p.sentences)
    if n >= 4 and pr:
        c = tl.cv(s.n_words for s in p.sentences)
        if c < _get(pr, "paragraph", "cv_p10", default=0.15):
            score += 1.5
            reasons.append(f"uniform sentence lengths (CV {c:.2f})")
    if n >= 3 and tl.is_summary_closer(p.sentences[-1].text) and _get(pr, "summary_closer_share") < 0.15:
        score += 1
        reasons.append("summary-style closing sentence")
    sc = tl.structural_counts(p.text)
    words = max(1, p.n_words)
    for key, label in (("hedge", "hedging"), ("intensifier", "intensifiers")):
        base = _get(pr, "rates_per_1k", "structural", key, default=1.0)
        if sc[key] >= 2 and tl.rate(sc[key], words) > 3 * max(base, 1.0):
            score += 1
            reasons.append(f"dense {label} ({sc[key]})")
    return score, reasons


def chunk_deltas(doc, pr):
    fw = _get(pr, "function_words", default={})
    if not fw or not fw.get("mu") or not fw.get("delta_loo_p95"):
        return []
    out, cur, start = [], [], None
    size = fw.get("chunk_size", 500)
    for p in doc.paragraphs:
        if start is None:
            start = p.start_line
        for s in p.sentences:
            cur.extend(s.words)
        if len(cur) >= size:
            out.append((start, p.end_line, tl.burrows_delta(tl.fw_freqs(cur), fw["mu"], fw["sd"])))
            cur, start = [], None
    if len(cur) >= size // 2 and doc.paragraphs:
        out.append((start, doc.paragraphs[-1].end_line, tl.burrows_delta(tl.fw_freqs(cur), fw["mu"], fw["sd"])))
    return out


def profile_source_match(pr, raw: bytes):
    h = hashlib.sha256(raw).hexdigest()[:16]
    for src in (pr or {}).get("sources", []):
        if src.get("sha256") == h:
            return src.get("file")
    return None


def lint(path, pr, top=15):
    rules = tl.Rules(pr)
    doc = prose.extract(Path(path), config=(pr or {}).get("config"))
    res = {"file": str(path), "format": doc.fmt, "hard": [], "grammar": [], "paragraphs": [], "drift": [],
           "soft": [], "chunks": [], "circular": profile_source_match(pr, Path(path).read_bytes())}
    for p in doc.paragraphs:
        for s in p.sentences:
            for what, line in sentence_tells(s, rules):
                res["hard"].append({"line": line, "what": what, "sentence": s.text})
            for m, fix, off in tl.watchlist_matches(s.text, rules.watchlist):
                res["grammar"].append({"line": s.line_of(off), "match": m, "fix": fix, "sentence": s.text})
    scored = []
    for p in doc.paragraphs:
        sc, why = paragraph_score(p, pr, rules)
        if sc >= 2:
            scored.append({"lines": [p.start_line, p.end_line], "score": round(sc, 2), "reasons": why,
                           "start": p.text[:110]})
    res["paragraphs"] = sorted(scored, key=lambda d: -d["score"])[:top]

    m = doc_metrics(doc, rules)
    res["metrics"] = m
    if pr:
        sl = pr["sentence_length"]
        st = pr["rates_per_1k"]["structural"]

        def row(name, val, base, bad):
            res["drift"].append({"metric": name, "draft": round(val, 3), "author": round(base, 3), "flag": bool(bad)})

        row("sentence length, median", m["sent_median"], sl["median"], abs(m["sent_median"] - sl["median"]) > 4)
        row("sentence length, CV", m["sent_cv"], sl["cv"], m["sent_cv"] < sl["cv"] - 0.12)
        row("share of sentences > 35 words", m["share_over_35"], sl["share_over_35"],
            m["share_over_35"] > 2 * sl["share_over_35"] + 0.03)
        osl = _get(pr, "layout", "one_sentence_per_line", default=None)
        if osl is not None and m["one_sentence_per_line"] is not None and doc.layout_meaningful:
            row("sentence ends at a line break", m["one_sentence_per_line"], osl,
                osl >= 0.8 and m["one_sentence_per_line"] < osl - 0.15)
        base_dash = st.get("em_dash", 0) + st.get("spaced_en_dash", 0)
        row("em dashes / 1k words", m["em_dash"], base_dash, m["em_dash"] > 2 * base_dash + 0.3)
        row("semicolons / 1k words", m["semicolon"], st.get("semicolon", 0), m["semicolon"] > 2 * st.get("semicolon", 0) + 0.5)
        row("hedges / 1k words", m["hedge"], st.get("hedge", 0), m["hedge"] > 2 * st.get("hedge", 0) + 1)
        row("intensifiers / 1k words", m["intensifier"], st.get("intensifier", 0),
            m["intensifier"] > 2 * st.get("intensifier", 0) + 1)
        base_soft = sum(pr["rates_per_1k"]["tierB"].values())
        row("tier-B words / 1k words", m["soft_total"], base_soft, m["soft_total"] > 2 * base_soft + 1)
        base_op = sum(pr["ai_openers_per_100_sentences"].values())
        row("AI-favoured openers / 100 sentences", m["ai_openers_per_100"], base_op,
            m["ai_openers_per_100"] > 2 * base_op + 1)
        row("paragraphs ending in a summary sentence", m["summary_closer_share"], pr["summary_closer_share"],
            m["summary_closer_share"] > 2 * pr["summary_closer_share"] + 0.08)
        row("passives / sentence", m["passive_per_sentence"], pr["passive_per_sentence"],
            m["passive_per_sentence"] > 1.6 * pr["passive_per_sentence"] + 0.05)
        for k, v in sorted(m["soft_counts"].items(), key=lambda kv: -kv[1]):
            r = tl.rate(v, m["n_words"])
            base = rules.soft_rate(k)
            if v >= 2 and r > 2 * base + 0.3:
                res["soft"].append({"term": k, "count": v, "draft_per_1k": round(r, 2), "author_per_1k": base})
        p95 = _get(pr, "function_words", "delta_loo_p95", default=None)
        for a, b, d in chunk_deltas(doc, pr):
            res["chunks"].append({"lines": [a, b], "delta": round(d, 3), "flag": bool(p95 and d > p95)})
    return res


def to_markdown(res, pr):
    m = res["metrics"]
    out = [f"# AI-tell lint: {Path(res['file']).name}", "",
           f"{m['n_words']:,} words of prose, {m['n_sentences']} sentences. "
           + ("Compared against the author profile." if pr else "No profile given: baseline checks skipped."), ""]
    if res.get("circular"):
        out += [f"> **Warning:** this draft is profile source '{res['circular']}'. Sections 3 and 4 compare it partly "
                "with itself. Build a temporary profile from the author's other samples and lint again.", ""]
    out.append("## 1. Hard tells (fix or rewrite yourself)")
    if res["hard"]:
        for h in res["hard"]:
            out.append(f"- l.{h['line']}: {h['what']} | {h['sentence'][:140]}")
    else:
        out.append("- none")
    out += ["", "## 2. The author's recurring slips (safe minimal fixes)"]
    if not (pr or {}).get("watchlist"):
        out.append("- no watchlist in this profile")
    elif res["grammar"]:
        for g in res["grammar"]:
            out.append(f"- l.{g['line']}: \"{g['match']}\" -> {g['fix']}")
    else:
        out.append("- none")
    out += ["", "## 3. Paragraphs that read least like the author",
            "Candidates for the author to rewrite by hand. Each signal is weighted by how rarely the author uses it.", ""]
    if res["paragraphs"]:
        for p in res["paragraphs"]:
            reasons = list(dict.fromkeys(p["reasons"]))
            shown = "; ".join(reasons[:10]) + (f"; and {len(reasons) - 10} more" if len(reasons) > 10 else "")
            out.append(f"- l.{p['lines'][0]}-{p['lines'][1]} (score {p['score']}): {shown}")
            out.append(f"  > {p['start']}...")
    else:
        out.append("- none above threshold")
    if pr:
        out += ["", "## 4. Document-level drift from the author's baseline", "",
                "| metric | draft | author | flag |", "|---|---|---|---|"]
        for d in res["drift"]:
            out.append(f"| {d['metric']} | {d['draft']} | {d['author']} | {'**check**' if d['flag'] else ''} |")
        if res["soft"]:
            out += ["", "Tier-B words used well above the author's habit:"]
            for t in res["soft"]:
                out.append(f"- {t['term']}: {t['count']}x ({t['draft_per_1k']}/1k vs author {t['author_per_1k']}/1k)")
        if res["chunks"]:
            flagged = [c for c in res["chunks"] if c["flag"]]
            out += ["", f"Function-word drift: {len(flagged)} of {len(res['chunks'])} chunks exceed the author's p95."]
            for c in flagged:
                out.append(f"- l.{c['lines'][0]}-{c['lines'][1]}: Delta {c['delta']}")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("--profile", help="author_profile.json")
    ap.add_argument("-o", "--out", help="write the markdown report here (default: stdout)")
    ap.add_argument("--json", help="also write machine-readable results")
    ap.add_argument("--top", type=int, default=15, help="how many paragraphs to list")
    a = ap.parse_args()
    pr = load_profile(a.profile)
    res = lint(a.draft, pr, top=a.top)
    md = to_markdown(res, pr)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"lint report: {a.out}")
    else:
        print(md)
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
