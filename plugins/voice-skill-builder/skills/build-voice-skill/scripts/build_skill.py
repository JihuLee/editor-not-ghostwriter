#!/usr/bin/env python3
"""Assemble a personal voice skill from an author's profile, notes, slips and requests.

usage:
  python build_skill.py --name alex-voice --author "Alex" \\
      --profile work/profile.json --notes work/voice_notes.md \\
      [--watchlist work/watchlist.json] [--config work/config.json] \\
      [--requests work/requests.md] [--add-request "..."] \\
      --out work/build/alex-voice [--force]
  python build_skill.py --from-skill ~/.claude/skills/alex-voice --add-request "..." \\
      --out work/build/alex-voice [--force]

By default the skill holds only the author's data (profile, voice notes, slips, requests) and hands
the editing to the revise-in-voice skill of the same plugin, so a newer plugin improves every voice
skill without a rebuild. --standalone copies the workflow and scripts in as well, for a skill that
works without the plugin; it then changes only when rebuilt.

--requests is a markdown file of the author's standing requests (lasting preferences such as
"keep figure captions short"); --add-request appends one, and may be repeated. --from-skill
rebuilds from a skill this script built earlier, reading its profile, watchlist, settings,
voice notes and requests from its own files, so no samples are needed; any other input given
replaces the one read from the skill.

Produces <out>/SKILL.md and references/ (author_profile.json, author_voice.md, author_stats.md);
--standalone adds references/reviewer_prompt.md and scripts/. The folder name equals the skill name,
as claude.ai and Claude Code require. Run validate_skill.py on the result next.
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
sys.path.insert(0, str(HERE))
from enginepath import use_engine   # noqa: E402
ENGINE = use_engine()
import style_profile   # noqa: E402
import tells as tl     # noqa: E402

BUILDER_VERSION = "0.9.2"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED = ("claude", "anthropic")
FILL_RE = re.compile(r"<!--\s*FILL", re.I)
NOTES_HEADING = "## Notes from reading the samples"
REQUESTS_HEADING = "## Standing requests from the author"
NO_NOTES = "_No notes were written for this build._"
SETUP_START, SETUP_END = "<!-- setup:start -->", "<!-- setup:end -->"
ENGINE_TITLE = "# Voice-preserving revision\n"
DESCRIPTION = ("Revise {who} own paper, manuscript or other long-form draft (a .tex, .md or .txt file) as a "
               "minimal-edit copy editor and reviewer, calibrated to their measured writing style, so the result "
               "still reads as their own writing and not as AI text. Use when the user wants to revise, proofread, "
               "tighten, fix grammar in, answer reviewer comments on such a draft, or review how clearly it reads, "
               "or asks to make it sound less AI-generated or more like their own style. Not for Word or Google "
               "Docs files, emails, or other short texts.")


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


def render(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[a-z_]+\}\}", text)
    if left:
        raise SystemExit(f"template placeholders left unfilled: {sorted(set(left))}")
    return text


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


def read_built_skill(skill_dir) -> dict:
    """Recover the inputs of a skill this script built, from the skill's own files."""
    skill = Path(skill_dir).expanduser()
    merged = load_json(skill / "references" / "author_profile.json", None) \
        if (skill / "references" / "author_profile.json").exists() else None
    voice_path = skill / "references" / "author_voice.md"
    if not merged or "skill" not in merged or "sentence_length" not in merged or not voice_path.exists():
        raise SystemExit(f"{skill} does not look like a voice skill made by build_skill.py")
    _, found, rest = voice_path.read_text(encoding="utf-8").partition("\n" + NOTES_HEADING + "\n")
    if not found:
        raise SystemExit(f"{voice_path} has no '{NOTES_HEADING}' section")
    notes, _, requests = rest.partition("\n" + REQUESTS_HEADING + "\n")
    notes = notes.strip()
    return {"profile": {k: v for k, v in merged.items() if k not in ("watchlist", "config", "skill")},
            "watchlist": merged.get("watchlist", []), "config": merged.get("config", {}),
            "notes": "" if notes == NO_NOTES else notes, "requests": requests.strip(),
            "name": merged["skill"].get("name"), "author": merged["skill"].get("author")}


def gather_requests(base: str, extra) -> str:
    lines = [base.strip()] if base and base.strip() else []
    for r in extra or []:
        r = " ".join(r.split())
        if r:
            lines.append(r if r.startswith("- ") else "- " + r)
    text = "\n".join(lines)
    if FILL_RE.search(text):
        raise SystemExit("the standing requests still contain <!-- FILL ... --> markers")
    return text


def standalone_skill_md(values: dict) -> str:
    """The engine's SKILL.md with the author's frontmatter, title and a one-folder setup block."""
    text = (ENGINE / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n") or text.count(SETUP_START) != 1 or text.count(SETUP_END) != 1 \
            or ENGINE_TITLE not in text:
        raise SystemExit(f"{ENGINE / 'SKILL.md'} lacks the frontmatter, title or setup markers a standalone build needs")
    body = text[text.index("\n---\n", 4) + 5:]
    head, _, rest = body.partition(SETUP_START)
    _, _, tail = rest.partition(SETUP_END)
    setup = render((TEMPLATE / "standalone_setup.md.tmpl").read_text(encoding="utf-8"), values).rstrip("\n")
    head = head.replace(ENGINE_TITLE, f"# Voice-preserving revision for {values['author']}\n", 1)
    front = f"---\nname: {values['name']}\ndescription: {values['description']}\n---\n"
    return render(front + head + setup + tail, {})


def build(args):
    old = read_built_skill(args.from_skill) if args.from_skill else {}
    args.name = args.name or old.get("name")
    args.author = args.author or old.get("author")
    if not args.name:
        raise SystemExit("--name is required (or --from-skill)")
    problems = check_name(args.name)
    if problems:
        raise SystemExit(f"invalid skill name '{args.name}': " + "; ".join(problems))
    out = Path(args.out)
    if out.name != args.name:
        raise SystemExit(f"the output folder must be named after the skill: .../{args.name} (got {out.name})")
    if not args.profile and not old:
        raise SystemExit("--profile is required (or --from-skill)")
    pr = load_json(args.profile, None) if args.profile else old["profile"]
    if not pr or "sentence_length" not in pr:
        raise SystemExit("--profile must be a profile written by style_profile.py")
    watchlist = load_json(args.watchlist, []) if args.watchlist else old.get("watchlist", [])
    validate_watchlist(watchlist)
    config = load_json(args.config, {}) if args.config else old.get("config", {})
    validate_config(config)
    notes = Path(args.notes).read_text(encoding="utf-8").strip() if args.notes else old.get("notes", "")
    if not notes and not args.allow_missing_notes and not old:
        raise SystemExit("--notes is required (voice notes written from the samples); pass --allow-missing-notes to skip")
    if FILL_RE.search(notes):
        raise SystemExit("the voice notes still contain <!-- FILL ... --> markers")
    base = Path(args.requests).read_text(encoding="utf-8") if args.requests else old.get("requests", "")
    requests = gather_requests(base, args.add_request)

    if out.exists():
        if not args.force:
            raise SystemExit(f"{out} exists; pass --force to replace it")
        prev = out / "SKILL.md"
        if not prev.exists() or f"name: {args.name}" not in prev.read_text(encoding="utf-8", errors="replace"):
            raise SystemExit(f"refusing to replace {out}: it does not look like a previous build of '{args.name}'")
        shutil.rmtree(out)
    (out / "references").mkdir(parents=True)
    kind = "standalone" if args.standalone else "voice"
    if args.standalone:
        shutil.copytree(ENGINE / "scripts", out / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for f in (ENGINE / "references").glob("*.md"):
            shutil.copy2(f, out / "references" / f.name)

    built = datetime.date.today().isoformat()
    author = args.author or "the author"
    merged = dict(pr)
    merged["watchlist"] = watchlist
    merged["config"] = config
    merged["skill"] = {"name": args.name, "author": author, "built": built, "builder_version": BUILDER_VERSION,
                       "kind": kind}
    (out / "references" / "author_profile.json").write_text(json.dumps(merged, indent=1, ensure_ascii=False),
                                                           encoding="utf-8")
    (out / "references" / "author_stats.md").write_text(style_profile.to_markdown(pr), encoding="utf-8")
    voice = voice_auto(pr, watchlist, author, built, config)
    voice += NOTES_HEADING + "\n\n" + (notes or NO_NOTES) + "\n"
    if requests:
        voice += "\n" + REQUESTS_HEADING + "\n\n" + requests + "\n"
    (out / "references" / "author_voice.md").write_text(voice, encoding="utf-8")

    values = {
        "name": args.name,
        "description": DESCRIPTION.format(who=possessive(author)),
        "author": author,
        "author_possessive": possessive(author),
        "author_title": possessive(author)[0].upper() + possessive(author)[1:],
        "n_sources": len(pr["sources"]),
        "n_words": f"{pr['n_words']:,}",
        "built": built,
    }
    if args.standalone:
        skill_md = standalone_skill_md(values)
    else:
        skill_md = render((TEMPLATE / "voice_skill.md.tmpl").read_text(encoding="utf-8"), values)
    (out / "SKILL.md").write_text(skill_md, encoding="utf-8")
    print(f"built {'standalone ' if args.standalone else ''}skill '{args.name}' in {out}")
    if not args.standalone:
        print("It uses the revise-in-voice skill of the voice-skill-builder plugin for the editing workflow; "
              "keep the plugin installed wherever you use this skill.")
    source = Path(args.from_skill).expanduser().resolve().as_posix() if args.from_skill else ""
    if "/.claude/skills/synced/" in source:
        print("NOTE: the source is a claude.ai account skill synced into Claude Code, which cannot save to the "
              "account. The same request made in a claude.ai chat replaces it with one click (Save skill, then "
              "Upload and replace); otherwise upload the packaged zip under Customize > Skills.")
    elif "/.claude/plugins/" in source:
        print("NOTE: the source was installed from a plugin, such as your private repository. Publish the "
              "rebuild there with publish_skill.py and push it; reinstalling it locally would be overwritten.")
    if git_unignored(out):
        print(f"WARNING: {out} is inside a git repository and not ignored. The skill holds statistics and short "
              "quotes from your writing; add it to .gitignore or build outside the repository.")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", help="skill name, e.g. alex-voice (kebab-case); taken from --from-skill if omitted")
    ap.add_argument("--author", help="how the notes refer to the author, e.g. 'Alex' (default: 'the author')")
    ap.add_argument("--from-skill", help="rebuild from a skill this script built (no samples needed)")
    ap.add_argument("--profile", help="profile.json from style_profile.py")
    ap.add_argument("--notes", help="voice_notes.md written from the samples")
    ap.add_argument("--watchlist", help="watchlist.json: the author's recurring slips")
    ap.add_argument("--config", help="config.json: LaTeX settings and allowed words (references/config_format.md)")
    ap.add_argument("--requests", help="requests.md: the author's standing requests (replaces those of --from-skill)")
    ap.add_argument("--add-request", action="append", help="append one standing request (repeatable)")
    ap.add_argument("--out", required=True, help="output folder, named after the skill")
    ap.add_argument("--force", action="store_true", help="replace a previous build in --out")
    ap.add_argument("--allow-missing-notes", action="store_true")
    ap.add_argument("--standalone", action="store_true",
                    help="copy the editing workflow and scripts into the skill, so it works without the plugin "
                         "(it then changes only when rebuilt)")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
