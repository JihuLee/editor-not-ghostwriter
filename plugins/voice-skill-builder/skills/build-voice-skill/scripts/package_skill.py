#!/usr/bin/env python3
"""Zip a built skill for claude.ai: <name>.zip containing <name>/SKILL.md and the rest.

usage:
  python package_skill.py work/build/alex-voice [-o dist/] [--ext zip|skill]

Upload the .zip in claude.ai under Customize > Skills, then turn the skill on. A .skill file
is the same archive under another name; claude.ai shows a "Save skill" button for it when
Claude hands it over in a chat.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import zipfile
from pathlib import Path

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc", ".DS_Store", "*.swp"}


def package(skill_dir, out_dir=".", ext="zip") -> Path:
    skill = Path(skill_dir).resolve()
    if not (skill / "SKILL.md").exists():
        raise SystemExit(f"{skill} has no SKILL.md")
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    if f"\nname: {skill.name}\n" not in "\n" + text.split("\n---", 1)[0] + "\n":
        raise SystemExit(f"the SKILL.md name must equal the folder name '{skill.name}'")
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{skill.name}.{ext}"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill.rglob("*")):
            rel = f.relative_to(skill.parent)
            if not f.is_file() or any(p in EXCLUDE_DIRS for p in rel.parts):
                continue
            if any(fnmatch.fnmatch(f.name, g) for g in EXCLUDE_GLOBS):
                continue
            z.write(f, rel.as_posix())
    with zipfile.ZipFile(target) as z:
        names = z.namelist()
    if f"{skill.name}/SKILL.md" not in names or any(not n.startswith(skill.name + "/") for n in names):
        raise SystemExit("archive layout check failed: every entry must start with the skill folder")
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir")
    ap.add_argument("-o", "--out", default=".", help="output folder")
    ap.add_argument("--ext", choices=["zip", "skill"], default="zip")
    a = ap.parse_args()
    target = package(a.skill_dir, a.out, a.ext)
    print(f"packaged: {target}")


if __name__ == "__main__":
    sys.exit(main())
