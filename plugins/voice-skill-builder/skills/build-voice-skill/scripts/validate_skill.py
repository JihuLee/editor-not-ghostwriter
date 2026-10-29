#!/usr/bin/env python3
"""Check a built voice skill: structure first, then self-tests on the author's own samples.

usage:
  python validate_skill.py work/build/alex-voice [--samples s1.tex s2.md ...] [--json report.json]

Structure: frontmatter rules (name = folder, kebab-case, at most 64 characters, no reserved
words; description at most 1,024 characters, no angle brackets), referenced files exist,
no unfilled placeholders, scripts compile, the profile and watchlist load.

Self-tests (with --samples): the extractor reads every sample cleanly; the lint finds no hard
tells in the author's own text; every watchlist entry occurs in the samples; the guard reverts
a planted tier-A word, em dash, number change, citation change, new sentence, theorem edit and
math edit, and keeps a harmless one-word edit; the lint ranks a planted AI-polished paragraph first.
Exit code 1 when anything fails.
"""
from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class Report:
    def __init__(self):
        self.rows = []

    def add(self, check, ok, detail="", level="error"):
        self.rows.append({"check": check, "ok": bool(ok), "detail": detail, "level": "info" if ok else level})

    @property
    def failed(self):
        return [r for r in self.rows if not r["ok"] and r["level"] == "error"]

    def print(self):
        for r in self.rows:
            mark = "PASS" if r["ok"] else ("WARN" if r["level"] == "warn" else "FAIL")
            print(f"{mark}  {r['check']}" + (f"  - {r['detail']}" if r["detail"] else ""))
        print(f"\n{len(self.failed)} failure(s), {sum(1 for r in self.rows if not r['ok'] and r['level'] == 'warn')} warning(s)")


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out = {}
    for line in text[3:end].strip().split("\n"):
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def check_structure(skill: Path, rep: Report):
    md = skill / "SKILL.md"
    if not md.exists():
        rep.add("SKILL.md exists", False, str(md))
        return None
    text = md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    name, desc = fm.get("name", ""), fm.get("description", "")
    rep.add("frontmatter has name and description", bool(name and desc))
    rep.add("name matches folder name", name == skill.name, f"name '{name}', folder '{skill.name}'")
    rep.add("name is kebab-case, at most 64 characters", bool(NAME_RE.match(name)) and len(name) <= 64, name)
    rep.add("name has no reserved words", not any(r in name for r in ("claude", "anthropic")), name)
    rep.add("description at most 1,024 characters", 0 < len(desc) <= 1024, f"{len(desc)} characters")
    rep.add("description has no angle brackets", "<" not in desc and ">" not in desc)
    n_lines = text.count("\n")
    rep.add("SKILL.md under 500 lines", n_lines < 500, f"{n_lines} lines", level="warn")
    refs = sorted(set(re.findall(r"`((?:references|scripts)/[\w./-]+)`", text)))
    missing = [r for r in refs if not (skill / r).exists()]
    rep.add("files named in SKILL.md exist", not missing, ", ".join(missing))
    leftovers = []
    for f in [md] + sorted((skill / "references").glob("*.md")):
        t = f.read_text(encoding="utf-8")
        if re.search(r"\{\{[a-z_]+\}\}", t) or re.search(r"<!--\s*FILL", t, re.I):
            leftovers.append(f.name)
    rep.add("no unfilled placeholders", not leftovers, ", ".join(leftovers))
    bad = []
    for f in sorted((skill / "scripts").glob("*.py")):
        try:
            py_compile.compile(str(f), doraise=True, cfile=str(Path(tempfile.gettempdir()) / (f.name + "c")))
        except py_compile.PyCompileError as e:
            bad.append(f"{f.name}: {e.msg}")
    rep.add("scripts compile", not bad, "; ".join(bad))
    prof = skill / "references" / "author_profile.json"
    try:
        pr = json.loads(prof.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        rep.add("author_profile.json loads", False, str(e))
        return None
    rep.add("author_profile.json loads", True)
    n_words = pr.get("n_words", 0)
    rep.add("profile has at least 3,000 words", n_words >= 3000, f"{n_words:,} words",
            level="warn" if n_words >= 1000 else "error")
    if n_words >= 3000:
        rep.add("profile has 8,000+ words (steadier baseline)", n_words >= 8000,
                f"{n_words:,} words; more samples make the rates steadier", level="warn")
    bad_wl = []
    for e in pr.get("watchlist", []):
        if e.get("regex"):
            try:
                re.compile(e["match"])
            except re.error as err:
                bad_wl.append(f"{e['match']}: {err}")
    rep.add("watchlist patterns compile", not bad_wl, "; ".join(bad_wl))
    return pr


# --------------------------------------------------------------------------- self-tests


def _plain_lines(lines, kinds, fmt):
    """Indices of prose lines that are safe to plant edits in."""
    out = []
    for i, line in enumerate(lines):
        if kinds.get(i + 1) != "prose":
            continue
        s = line.strip()
        if len(s.split()) < 10 or "$" in s or "%" in s or "@" in s or "`" in s:
            continue
        if fmt == "tex" and ("\\" in s or "{" in s):
            continue
        if fmt == "md" and (s.startswith(("#", ">", "|", "-", "*", "[")) or re.match(r"\d+[.)]", s)):
            continue
        out.append(i)
    return out


def run_self_tests(skill: Path, pr: dict, samples, rep: Report):
    sys.path.insert(0, str(skill / "scripts"))
    import ai_tell_lint   # noqa: E402
    import diff_guard     # noqa: E402
    import prose          # noqa: E402
    import tells as tl    # noqa: E402

    config = pr.get("config")
    rules = tl.Rules(pr)
    wl_counts = {(e.get("label") or e["match"]): 0 for e in pr.get("watchlist", [])}
    draftable = []
    for s in samples:
        path = Path(s)
        doc = prose.extract(path, config=config)
        arts = doc.diagnostics.get("artifacts") or []
        rep.add(f"extraction: {path.name}", not arts,
                f"{len(doc.words()):,} words; markup left in {len(arts)} sentence(s), e.g. line {arts[0][0]}" if arts
                else f"{len(doc.words()):,} words", level="warn")
        res = ai_tell_lint.lint(path, pr)
        hard = res["hard"]
        rep.add(f"lint finds no hard tells in own sample: {path.name}", not hard,
                "; ".join(f"l.{h['line']} {h['what']}" for h in hard[:5]), level="warn")
        for rx, _, label in rules.watchlist:
            wl_counts[label] += sum(len(rx.findall(x.text)) for x in doc.sentences())
        if doc.fmt in prose.DRAFT_FORMATS:
            draftable.append((path, doc))
    for label, n in wl_counts.items():
        rep.add(f"watchlist entry occurs in samples: '{label}'", n > 0, f"{n} hit(s)", level="warn")
    if not draftable:
        rep.add("guard self-tests", False, "no LaTeX/Markdown/text sample to test on", level="warn")
        return
    path, doc = max(draftable, key=lambda pd: len(pd[1].words()))
    fmt = doc.fmt
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    lines = raw.split("\n")
    plain = _plain_lines(lines, doc.line_kind, fmt)
    tmp = Path(tempfile.mkdtemp(prefix="voice-validate-"))
    orig = tmp / ("original" + path.suffix)
    orig.write_text(raw, encoding="utf-8")

    def guard_case(name, mutate, expect_flag, need):
        idx = next((i for i in need if mutate(lines[i]) not in (None, lines[i])), None)
        if idx is None:
            rep.add(f"guard: {name}", True, "skipped (no suitable line in the sample)")
            return
        edited = list(lines)
        edited[idx] = mutate(lines[idx])
        ed = tmp / ("edited" + path.suffix)
        ed.write_text("\n".join(edited), encoding="utf-8")
        res = diff_guard.guard(orig, ed, pr, fmt=fmt)
        statuses = [h.status for h in res["hunks"]]
        got_flag = "FLAG" in statuses
        ok = got_flag if expect_flag else (statuses == ["OK"])
        detail = f"line {idx + 1}: {statuses}" + (f" {res['hunks'][0].flags[:2]}" if res["hunks"] and res["hunks"][0].flags else "")
        rep.add(f"guard: {name} -> {'reverted' if expect_flag else 'kept'}", ok, detail)

    tier_a_word = next((w for w in ("pivotal", "intricate", "meticulous", "multifaceted", "seamless")
                        if w in {k.split(' ')[0] for k in rules.tier_a_hard}), "pivotal")
    guard_case("harmless one-word edit", lambda l: l.replace(" the ", " this ", 1) if " the " in l else None,
               False, plain)
    guard_case(f"tier-A word ('{tier_a_word}')",
               lambda l: l.replace(" the ", f" the {tier_a_word} ", 1) if " the " in l else None, True, plain)
    if "em_dash" in rules.hard_devices:
        dash = "---" if fmt == "tex" else " — "
        guard_case("em dash", lambda l: l.replace(", ", dash, 1) if ", " in l else None, True, plain)
    guard_case("new sentence", lambda l: l.rstrip() + " This sentence was added to test the guard."
               if l.rstrip().endswith(".") else None, True, plain)

    prose_idx = [i for i, l in enumerate(lines) if doc.line_kind.get(i + 1) == "prose"]

    def bump_number(l):
        if not diff_guard.numbers(l, fmt):
            return None
        stripped = diff_guard._nocomment(l, fmt)
        for m in re.finditer(r"(?<![A-Za-z_\\$])\d+", stripped):
            cand = l[:m.start()] + str(int(m.group(0)) + 1) + l[m.end():]
            if diff_guard.numbers(cand, fmt) != diff_guard.numbers(l, fmt):
                return cand
        return None
    guard_case("changed number", bump_number, True, prose_idx)

    def drop_cite(l):
        if fmt == "tex":
            m = re.search(r"(\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{)([^},]+),\s*([^}]+\})", l)
            return (l[:m.start()] + m.group(1) + m.group(3) + l[m.end():]) if m else None
        m = re.search(r"\[@[^;\]]+;\s*(@[^\]]+\])", l)
        return (l[:m.start()] + "[" + m.group(1) + l[m.end():]) if m else None
    guard_case("citation key removed", drop_cite, True, prose_idx)

    def touch_math(l):
        m = re.search(r"(?<!\\)\$([^$]+)(?<!\\)\$", l)
        return (l[:m.start(1)] + m.group(1) + "+0" + l[m.end(1):]) if m else None
    guard_case("inline math changed", touch_math, True, prose_idx)

    frozen_idx = [i for i, l in enumerate(lines)
                  if doc.line_kind.get(i + 1) == "frozen" and re.search(r"(?<![\\\w])[a-z]{4,}\b", l)]
    guard_case("theorem/code block edited",
               lambda l: re.sub(r"(?<![\\\w])([a-z]{4,})\b", lambda m: m.group(1).upper(), l, count=1), True, frozen_idx)

    # lint: a planted AI-polished paragraph should rank first
    target = None
    for p in doc.paragraphs:
        span = range(p.start_line - 1, p.end_line)
        if len(p.sentences) >= 3 and p.end_line - 1 in plain and all(doc.line_kind.get(i + 1) == "prose" for i in span):
            target = p
            break
    if target is None:
        rep.add("lint: planted AI paragraph ranks first", True, "skipped (no suitable paragraph)")
        return
    edited = list(lines)
    last = target.end_line - 1
    edited[last] = (edited[last].rstrip() + " Overall, this highlights the pivotal and multifaceted role of"
                    " the proposed approach.")
    planted = tmp / ("planted" + path.suffix)
    planted.write_text("\n".join(edited), encoding="utf-8")
    res = ai_tell_lint.lint(planted, pr)
    top = res["paragraphs"][0]["lines"] if res["paragraphs"] else None
    ok = bool(top) and top[0] <= target.end_line <= top[1] + 1
    rep.add("lint: planted AI paragraph ranks first", ok, f"planted at l.{target.start_line}-{target.end_line}, top {top}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("--samples", nargs="*", default=[], help="the author's samples, for self-tests")
    ap.add_argument("--json", help="write the results here")
    a = ap.parse_args()
    skill = Path(a.skill_dir).resolve()
    rep = Report()
    pr = check_structure(skill, rep)
    if pr is not None and a.samples:
        run_self_tests(skill, pr, a.samples, rep)
    elif pr is not None:
        rep.add("self-tests", False, "skipped: pass --samples to test on the author's own files", level="warn")
    rep.print()
    if a.json:
        Path(a.json).write_text(json.dumps(rep.rows, indent=1), encoding="utf-8")
    sys.exit(1 if rep.failed else 0)


if __name__ == "__main__":
    main()
