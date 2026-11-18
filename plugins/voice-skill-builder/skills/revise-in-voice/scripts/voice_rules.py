#!/usr/bin/env python3
"""Print the editing rules that come from an author's profile, and check that the profile fits this engine.

usage:
  python voice_rules.py --profile VOICE_DIR/references/author_profile.json

The revise-in-voice workflow runs this before editing. It prints which voice skill the profile belongs
to, the source layout to keep, the devices the author never uses, the sentence openers to avoid, the
frozen LaTeX environments and the words allowed for this author. The builder uses the same functions
when it writes a standalone skill.

Exit code 2 when the profile cannot be used: it is not a voice profile, or a newer builder wrote it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tells as tl

PROFILE_FORMATS = (2,)      # "version" values of author_profile.json this engine reads


def fmt_list(items, quote=True):
    items = [f"\"{x}\"" if quote else x for x in items]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


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
    """(devices the author never uses, a sentence on em dashes when the author does use them)."""
    rules = tl.Rules(pr)
    never = []
    if "em_dash" in rules.hard_devices:
        never.append("em dashes (`---` in LaTeX)")
    if "contraction" in rules.hard_devices:
        never.append("contractions")
    if "exclamation" in rules.hard_devices:
        never.append("exclamation marks")
    dash = ("" if "em_dash" in rules.hard_devices else
            "The author does use em dashes; keep them at the draft's existing rate and never add one to a "
            "sentence that reads fine without it.")
    return never, dash


def openers_to_avoid(pr, limit=8, config=None):
    merged = dict(pr)
    merged["config"] = config if config is not None else (pr.get("config") or {})
    avoid = tl.Rules(merged).avoid_openers
    return [o[0].upper() + o[1:] + "," for o in avoid[:limit]]


def frozen_envs(pr, config=None) -> tuple:
    """(frozen theorem-like environments, environments the author chose to keep editable)."""
    config = config if config is not None else (pr.get("config") or {})
    envs = set((pr.get("latex") or {}).get("theorem_envs_declared") or [])
    envs |= set((config.get("latex") or {}).get("frozen_envs_extra") or [])
    unfrozen = set((config.get("latex") or {}).get("unfrozen_envs") or [])
    return sorted(envs), sorted(unfrozen)


def frozen_note(pr, config=None) -> str:
    envs, unfrozen = frozen_envs(pr, config)
    parts = []
    if envs:
        parts.append("the author's theorem-like environments (" + ", ".join(f"`{e}`" for e in envs) + ")")
    if unfrozen:
        parts.append("except " + ", ".join(f"`{e}`" for e in unfrozen) + ", which the author chose to keep editable")
    return (" Frozen LaTeX environments include " + "; ".join(parts) + ".") if parts else ""


def compatibility(pr) -> tuple:
    """(usable, message). A profile from an older builder still works; one from a newer builder may not."""
    if not isinstance(pr, dict) or "sentence_length" not in pr or "rates_per_1k" not in pr:
        return False, "This file is not an author profile written by the voice-skill builder."
    fmt = pr.get("version")
    if isinstance(fmt, int) and fmt > max(PROFILE_FORMATS):
        return False, (f"This voice skill was built in profile format {fmt}, newer than this workflow reads "
                       f"({max(PROFILE_FORMATS)}). Update the voice-skill-builder plugin (claude.ai: Customize > "
                       "Plugins, Check for updates; Claude Code or Codex: `npx skills update`), then try again.")
    if fmt not in PROFILE_FORMATS:
        return True, (f"This voice skill uses profile format {fmt}. It should still work; rebuilding it with "
                      "build-voice-skill (--from-skill) brings it up to date.")
    return True, ""


def render(pr) -> str:
    skill = pr.get("skill") or {}
    author = skill.get("author") or "the author"
    never, dash = device_rules(pr)
    envs, unfrozen = frozen_envs(pr)
    allow = sorted(tl.Rules(pr).allow)
    built = skill.get("built", "an unknown date")
    lines = [f"# Voice rules for {author}", ""]
    if skill.get("name"):
        lines.append(f"Voice skill `{skill['name']}`, built {built} with builder "
                     f"{skill.get('builder_version', '(unknown)')} from {len(pr.get('sources', []))} sample(s) "
                     f"({pr.get('n_words', 0):,} words).")
        lines.append("")
    lines.append(f"- Layout: {layout_rule(pr)}")
    lines.append("- Never add: tier-A words (\"delve\", \"pivotal\", \"seamless\", ...), \"not only ... but also\""
                 + "".join(", " + d for d in never) + ".")
    if dash:
        lines.append(f"- Em dashes: {dash}")
    openers = openers_to_avoid(pr)
    if openers:
        lines.append(f"- Openers to avoid unless the author wrote them: {fmt_list(openers)}.")
    if envs:
        lines.append("- Frozen LaTeX environments, besides math, proofs, code and tables: "
                     + ", ".join(f"`{e}`" for e in envs) + ".")
    if unfrozen:
        lines.append("- Editable by the author's choice: " + ", ".join(f"`{e}`" for e in unfrozen) + ".")
    if allow:
        lines.append("- Allowed for this author (never flagged): " + ", ".join(f"\"{w}\"" for w in allow) + ".")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True, help="the voice skill's references/author_profile.json")
    a = ap.parse_args()
    try:
        pr = json.loads(Path(a.profile).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read the profile: {e}", file=sys.stderr)
        return 2
    ok, message = compatibility(pr)
    if not ok:
        print(message, file=sys.stderr)
        return 2
    if message:
        print(f"NOTE: {message}\n")
    print(render(pr), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
