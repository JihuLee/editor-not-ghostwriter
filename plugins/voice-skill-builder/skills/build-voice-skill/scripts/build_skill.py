#!/usr/bin/env python3
"""Assemble a personal voice-preserving revision skill from the template.

usage:
  python build_skill.py --name alex-voice --author "Alex" \\
      --profile work/profile.json --notes work/voice_notes.md \\
      [--watchlist work/watchlist.json] [--config work/config.json] \\
      --out work/build/alex-voice [--force]

Produces <out>/SKILL.md, references/ (author_profile.json, author_voice.md, author_stats.md,
editor_rules.md, reviewer_prompt.md, ai_tells.md) and scripts/. The folder name equals the
skill name, as claude.ai and Claude Code require. Run validate_skill.py on the result next.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "template"
sys.path.insert(0, str(TEMPLATE / "scripts"))
import style_profile   # noqa: E402
import tells as tl     # noqa: E402

BUILDER_VERSION = "0.1.0"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED = ("claude", "anthropic")
FILL_RE = re.compile(r"<!--\s*FILL", re.I)


def check_name(name: str):
    problems = []
    if not NAME_RE.match(name):
        problems.append("use lowercase letters, digits and single hyphens only")
    if len(name) > 64:
        problems.append("at most 64 characters")
    if any(r in name for r in RESERVED):
        problems.append("must not contain 'claude' or 'anthropic'")
    return problems


def possessive(label: str) -> str:
    return label + ("'" if label.endswith("s") else "'s")


def _fmt_list(items, quote=True):
    items = [f"\"{x}\"" if quote else x for x in items]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def render(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[a-z_]+\}\}", text)
    if left:
        raise SystemExit(f"template placeholders left unfilled: {sorted(set(left))}")
    return text


def layout_rule(pr) -> str:
    osl = (pr.get("layout") or {}).get("one_sentence_per_line")
    if osl is None:
        return ("Keep the source layout: the same line breaks and paragraph breaks. Edit in place; do not "
                "reflow or re-wrap paragraphs.")
    if osl >= 0.8:
        return ("Keep the source layout: one sentence per line (the author's habit), the same line breaks and "
                "paragraph breaks. Edit inside lines.")
    return ("Keep the source layout: the author hard-wraps paragraphs, so edit words in place and do not re-wrap "
            "the rest of the paragraph, even when a line gets longer or shorter.")


def device_rules(pr) -> tuple:
    rules = tl.Rules(pr)
    never = []
    if "em_dash" in rules.hard_devices:
        never.append("em dashes (`---` in LaTeX)")
    if "contraction" in rules.hard_devices:
        never.append("contractions")
    if "exclamation" in rules.hard_devices:
        never.append("exclamation marks")
    dash = ("" if "em_dash" in rules.hard_devices else
            "\n- The author does use em dashes; keep them at the draft's existing rate and never add one to a "
            "sentence that reads fine without it.")
    return never, dash


def openers_to_avoid(pr, limit=8, config=None):
    merged = dict(pr)
    merged["config"] = config or pr.get("config") or {}
    avoid = tl.Rules(merged).avoid_openers
    return [o[0].upper() + o[1:] + "," for o in avoid[:limit]]


def own_connectives(pr, limit=8):
    conn = pr.get("connectives_per_100_sentences") or {}
    out = []
    for k, v in conn.items():
        if tl.ai_opener(k + ",") or v < 0.3:
            continue
        out.append(k[0].upper() + k[1:])
        if len(out) >= limit:
            break
    return out


def frozen_note(pr, config) -> str:
    envs = set((pr.get("latex") or {}).get("theorem_envs_declared") or [])
    envs |= set(((config or {}).get("latex") or {}).get("frozen_envs_extra") or [])
    unfrozen = set(((config or {}).get("latex") or {}).get("unfrozen_envs") or [])
    parts = []
    if envs:
        parts.append("the author's theorem-like environments (" + ", ".join(f"`{e}`" for e in sorted(envs)) + ")")
    if unfrozen:
        parts.append("except " + ", ".join(f"`{e}`" for e in sorted(unfrozen)) + ", which the author chose to keep editable")
    return (" Frozen LaTeX environments include " + "; ".join(parts) + ".") if parts else ""


def _n(x) -> str:
    """Readable number: 18.0 -> 18, 19.447 -> 19.4, 0.304 -> 0.3."""
    x = float(x)
    return str(int(round(x))) if abs(x - round(x)) < 0.05 else f"{x:.1f}"


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def voice_auto(pr, watchlist, author, built, config=None) -> str:
    sl, st = pr["sentence_length"], pr["rates_per_1k"]["structural"]
    osl = (pr.get("layout") or {}).get("one_sentence_per_line")
    src = ", ".join(f"{s['file']} ({s['words']:,} words)" for s in pr["sources"])
    conn = pr.get("connectives_per_100_sentences") or {}
    top_conn = [f"\"{k[0].upper() + k[1:]}\" {_n(v)}" for k, v in list(conn.items())[:14]]
    avoid = openers_to_avoid(pr, limit=12, config=config)
    merged = dict(pr)
    merged["config"] = config or {}
    rules = tl.Rules(merged)
    skip = {"math", "ref", "author", "url", "code"}
    frequent = [f"\"{k}\" ({v})" for k, v in pr.get("top_openers_2", [])
                if not (set(k.split()) & skip)][:12]
    allow = sorted(rules.allow)
    soft_rates = pr["rates_per_1k"]["tierB"]
    tier_a = pr["counts"]["tierA"]
    if osl is None:
        layout = "Not measured (samples were Word files)."
    elif osl >= 0.8:
        layout = f"One sentence per source line ({osl:.0%} of sentence boundaries fall at a line break). Edits stay inside lines."
    else:
        layout = (f"Hard-wrapped or mixed ({osl:.0%} of sentence boundaries fall at a line break). Edit in place and do "
                  "not re-wrap paragraphs, so the diff stays small.")
    dash_rate = st.get("em_dash", 0) + st.get("spaced_en_dash", 0)
    lines = [
        f"# {possessive(author)[0].upper() + possessive(author)[1:]} voice",
        "",
        f"Built {built} from {len(pr['sources'])} sample(s), {pr['n_words']:,} words: {src}.",
        "Numbers come from `author_profile.json` (full table in `author_stats.md`). The last section was written",
        "by reading the samples. Use this file to keep edits inside the author's habits and to know which of",
        "their habits are slips worth fixing.",
        "",
        "## Measured habits (generated)",
        "",
        f"**Layout.** {layout}",
        "",
        f"**Rhythm.** Median sentence {_n(sl['median'])} words, most between {_n(sl['p10'])} and {_n(sl['p90'])}. "
        f"{sl['share_under_10']:.0%} of sentences are short (under 10 words); keep them short rather than merging them. "
        f"Paragraphs have a median of {_n(pr['paragraph']['sentences_median'])} sentences.",
        "",
        f"**Person.** we/our/us {_n(st.get('we', 0))} per 1,000 words; {pr.get('we_opener_share', 0):.0%} of sentences start with \"We\".",
        "",
        "**Connectives the author uses** (sentence-initial, per 100 sentences): "
        + (", ".join(top_conn) if top_conn else "none measured") + ". When a transition is genuinely missing, take it from this list.",
        "",
        "**Most frequent sentence openers** (any two words, with counts): " + (", ".join(frequent) or "none")
        + ". Signposts that recur here but are missing from the connective list are still part of the voice.",
        "",
        "**AI-favoured openers the author (almost) never uses:** " + (", ".join(f"\"{o}\"" for o in avoid) or "none")
        + ". Do not add them.",
        "",
        f"**Devices** (per 1,000 words): colons {_n(st.get('colon', 0))}, semicolons {_n(st.get('semicolon', 0))}, "
        f"parentheses {_n(st.get('parenthesis', 0))}, e.g./i.e. {_n(st.get('eg_ie', 0))}, em dashes {_n(dash_rate)}"
        + (" (treated as a hard rule: never add one)." if "em_dash" in rules.hard_devices else " (the author uses them)."),
        "",
        f"**Claims.** Hedges {_n(st.get('hedge', 0))} and intensifiers {_n(st.get('intensifier', 0))} per 1,000 words. "
        "Do not add hedges or intensifiers the author did not write.",
        "",
        f"**Paragraph endings.** {pr['summary_closer_share']:.0%} of paragraphs end with a summary-style sentence "
        "(\"Overall, ...\", \"These results show ...\").",
        "",
        "**Vocabulary.** Tier-A words in the samples: "
        + (", ".join(f"{k} ({v}x)" for k, v in tier_a.items()) + " (the ones used twice or more are treated as the author's own words)"
           if tier_a else "none")
        + ". Tier-B words the author uses most: "
        + (", ".join(f"{k} {_n(v)}/1k" for k, v in list(soft_rates.items())[:6]) or "none") + ".",
        "",
    ]
    if allow:
        lines += ["**Allowed for this author** (never flagged, from config.json): "
                  + ", ".join(f"\"{w}\"" for w in allow) + ".", ""]
    lines += ["## Recurring slips (watchlist, generated)", ""]
    if watchlist:
        lines += ["Fix these with the smallest change; they are slips, not style.", "",
                  "| Slip | Fix | Why | Seen in samples |", "|---|---|---|---|"]
        for e in watchlist:
            shown = e.get("label") or (e["match"] + (" (pattern)" if e.get("regex") else ""))
            lines.append(f"| {_cell(shown)} | {_cell(e.get('fix', ''))} | {_cell(e.get('note', ''))} | "
                         f"{e.get('count', '')} |")
    else:
        lines.append("No recurring slips were recorded.")
    lines += ["", ""]
    return "\n".join(lines)


def load_json(path, default):
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_config(config):
    if not isinstance(config, dict):
        raise SystemExit("config must be a JSON object")
    unknown = set(config) - {"latex", "allow"}
    if unknown:
        raise SystemExit(f"unknown config keys: {sorted(unknown)} (allowed: latex, allow)")
    lx = config.get("latex", {})
    if not isinstance(lx, dict) or set(lx) - {"frozen_envs_extra", "unfrozen_envs", "macros"}:
        raise SystemExit("config.latex may hold frozen_envs_extra, unfrozen_envs and macros only")
    if not isinstance(config.get("allow", []), list):
        raise SystemExit("config.allow must be a list of words or labels")


def validate_watchlist(entries):
    if not isinstance(entries, list):
        raise SystemExit("watchlist must be a JSON list of {match, fix} objects")
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or "match" not in e or "fix" not in e:
            raise SystemExit(f"watchlist entry {i} needs 'match' and 'fix'")
        if e.get("regex"):
            try:
                re.compile(e["match"], re.I)
            except re.error as err:
                raise SystemExit(f"watchlist entry {i} is not a valid regex: {err}")


def git_unignored(path: Path) -> bool:
    """True when path sits in a git work tree and is not ignored (it could get committed)."""
    try:
        probe = path if path.exists() else path.parent
        top = subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        if top.returncode:
            return False
        ign = subprocess.run(["git", "-C", str(probe), "check-ignore", "-q", str(path)], capture_output=True)
        return ign.returncode != 0
    except (OSError, FileNotFoundError):
        return False


def build(args):
    problems = check_name(args.name)
    if problems:
        raise SystemExit(f"invalid skill name '{args.name}': " + "; ".join(problems))
    out = Path(args.out)
    if out.name != args.name:
        raise SystemExit(f"the output folder must be named after the skill: .../{args.name} (got {out.name})")
    pr = load_json(args.profile, None)
    if not pr or "sentence_length" not in pr:
        raise SystemExit("--profile must be a profile written by style_profile.py")
    watchlist = load_json(args.watchlist, [])
    validate_watchlist(watchlist)
    config = load_json(args.config, {})
    validate_config(config)
    notes = Path(args.notes).read_text(encoding="utf-8").strip() if args.notes else ""
    if not notes and not args.allow_missing_notes:
        raise SystemExit("--notes is required (voice notes written from the samples); pass --allow-missing-notes to skip")
    if FILL_RE.search(notes):
        raise SystemExit("the voice notes still contain <!-- FILL ... --> markers")

    if out.exists():
        if not args.force:
            raise SystemExit(f"{out} exists; pass --force to replace it")
        old = out / "SKILL.md"
        if not old.exists() or f"name: {args.name}" not in old.read_text(encoding="utf-8", errors="replace"):
            raise SystemExit(f"refusing to replace {out}: it does not look like a previous build of '{args.name}'")
        shutil.rmtree(out)
    (out / "references").mkdir(parents=True)
    shutil.copytree(TEMPLATE / "scripts", out / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in (TEMPLATE / "references").glob("*.md"):
        shutil.copy2(f, out / "references" / f.name)

    built = datetime.date.today().isoformat()
    author = args.author or "the author"
    merged = dict(pr)
    merged["watchlist"] = watchlist
    merged["config"] = config
    merged["skill"] = {"name": args.name, "author": author, "built": built, "builder_version": BUILDER_VERSION}
    (out / "references" / "author_profile.json").write_text(json.dumps(merged, indent=1, ensure_ascii=False),
                                                           encoding="utf-8")
    (out / "references" / "author_stats.md").write_text(style_profile.to_markdown(pr), encoding="utf-8")
    voice = voice_auto(pr, watchlist, author, built, config)
    voice += "## Notes from reading the samples\n\n" + (notes or "_No notes were written for this build._") + "\n"
    (out / "references" / "author_voice.md").write_text(voice, encoding="utf-8")

    never, dash = device_rules(pr)
    conn = own_connectives(pr)
    values = {
        "name": args.name,
        "author": author,
        "author_possessive": possessive(author),
        "n_sources": len(pr["sources"]),
        "n_words": f"{pr['n_words']:,}",
        "built": built,
        "layout_rule": layout_rule(pr),
        "dash_rule": dash,
        "never_devices": (", " + ", ".join(never)) if never else "",
        "author_connectives": _fmt_list(conn) if conn else "the connectives listed in `references/author_voice.md`",
        "avoid_openers": _fmt_list(openers_to_avoid(pr, config=config)),
        "frozen_note": frozen_note(pr, config),
    }
    skill_md = render((TEMPLATE / "SKILL.md.tmpl").read_text(encoding="utf-8"), values)
    (out / "SKILL.md").write_text(skill_md, encoding="utf-8")
    print(f"built skill '{args.name}' in {out}")
    if git_unignored(out):
        print(f"WARNING: {out} is inside a git repository and not ignored. The skill holds statistics and short "
              "quotes from your writing; add it to .gitignore or build outside the repository.")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="skill name, e.g. alex-voice (kebab-case)")
    ap.add_argument("--author", help="how the notes refer to the author, e.g. 'Alex' (default: 'the author')")
    ap.add_argument("--profile", required=True, help="profile.json from style_profile.py")
    ap.add_argument("--notes", help="voice_notes.md written from the samples")
    ap.add_argument("--watchlist", help="watchlist.json: the author's recurring slips")
    ap.add_argument("--config", help="config.json: LaTeX settings and allowed words (references/config_format.md)")
    ap.add_argument("--out", required=True, help="output folder, named after the skill")
    ap.add_argument("--force", action="store_true", help="replace a previous build in --out")
    ap.add_argument("--allow-missing-notes", action="store_true")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
