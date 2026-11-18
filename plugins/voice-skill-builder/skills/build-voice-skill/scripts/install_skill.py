#!/usr/bin/env python3
"""Install a built skill for Claude Code or Codex.

usage:
  python install_skill.py work/build/alex-voice [--agent claude|codex] [--scope personal|project]
                          [--dest DIR] [--force]

claude, personal -> ~/.claude/skills/<name>/   (every project on this machine)
claude, project  -> ./.claude/skills/<name>/   (this repository only)
codex,  personal -> ~/.agents/skills/<name>/
codex,  project  -> ./.agents/skills/<name>/

A voice skill (the default build) needs the revise-in-voice skill of the voice-skill-builder
plugin wherever it is used; the script says so when it cannot find it next to the new skill or
next to this builder. A standalone build carries its own copy.

Do not commit a project install if the repository is public, since the skill holds statistics
and short quotes from your writing.

An existing installation is moved to skill-backups/<name>-<timestamp>/ next to the skills folder
(~/.claude/skill-backups/ or ~/.agents/skill-backups/ for a personal install) rather than deleted,
and never into the skills folder itself, where it would load as a duplicate skill.
"""
from __future__ import annotations

import argparse
import datetime
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enginepath import ENGINE_NAME, find_engine   # noqa: E402

AGENT_DIRS = {"claude": ".claude", "codex": ".agents"}     # folder that holds skills/ for each agent


def install(skill_dir, scope="personal", dest=None, force=False, agent="claude") -> Path:
    skill = Path(skill_dir).resolve()
    if not (skill / "SKILL.md").exists():
        raise SystemExit(f"{skill} has no SKILL.md")
    if dest:
        root = Path(dest).expanduser()
    elif scope == "project":
        root = Path.cwd() / AGENT_DIRS[agent] / "skills"
    else:
        root = Path.home() / AGENT_DIRS[agent] / "skills"
    target = root / skill.name
    if target.resolve() == skill:
        raise SystemExit("the skill is already in place")
    if target.exists():
        if not force:
            raise SystemExit(f"{target} exists; pass --force to replace it (the old copy is backed up)")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = root.parent / "skill-backups" / f"{skill.name}-{stamp}"     # never inside the skills folder
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(backup))
        print(f"previous version moved to {backup}")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("--agent", choices=sorted(AGENT_DIRS), default="claude")
    ap.add_argument("--scope", choices=["personal", "project"], default="personal")
    ap.add_argument("--dest", help="install into this skills folder instead")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    target = install(a.skill_dir, a.scope, a.dest, a.force, a.agent)
    name = target.name
    print(f"installed: {target}")
    if not (target / "scripts").is_dir() and not (target.parent / ENGINE_NAME / "SKILL.md").exists():
        where = find_engine(required=False)
        print(f"This voice skill hands the editing to the {ENGINE_NAME} skill, which is not next to it in "
              f"{target.parent}" + (f" (the builder's copy is in {where})" if where else "") + ". Keep the "
              "voice-skill-builder plugin installed for this agent: `npx skills add "
              "JihuLee/editor-not-ghostwriter -g`, or the plugin from the same marketplace.")
    if a.dest:
        print("This folder is not one Claude Code or Codex scans by default; point your tool at it or copy "
              "the skill.")
    elif a.agent == "codex":
        print(f"In Codex, run /skills to check that '{name}' is listed (restart Codex if it was already "
              f"running), then invoke it with ${name} followed by what to revise.")
    else:
        print(f"In Claude Code, run /skills to check that '{name}' is listed, then invoke it with /{name} "
              "followed by what to revise.")


if __name__ == "__main__":
    main()
