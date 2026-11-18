#!/usr/bin/env python3
"""Zip the plugin for manual upload: dist/voice-skill-builder.zip (folder voice-skill-builder/ at the top).

usage: python tools/make_release.py [-o dist]

The archive holds the whole plugin (.claude-plugin/plugin.json and both skills, build-voice-skill and
revise-in-voice), as claude.ai's Customize > Plugins > Add > Upload plugin expects. Adding the repository
as a marketplace is the better route, since the plugin then updates by itself; the zip is for people who
cannot do that. The release workflow (.github/workflows/release.yml) runs this script and attaches the zip.
"""
import argparse
import fnmatch
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "voice-skill-builder"
SKILLS = ("build-voice-skill", "revise-in-voice")
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc", ".DS_Store", "*.swp"}


def package(out_dir) -> Path:
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{manifest['name']}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PLUGIN.rglob("*")):
            rel = f.relative_to(PLUGIN.parent)
            if not f.is_file() or any(p in EXCLUDE_DIRS for p in rel.parts):
                continue
            if any(fnmatch.fnmatch(f.name, g) for g in EXCLUDE_GLOBS):
                continue
            z.write(f, rel.as_posix())
    with zipfile.ZipFile(target) as z:
        names = set(z.namelist())
    top = PLUGIN.name
    need = {f"{top}/.claude-plugin/plugin.json"} | {f"{top}/skills/{s}/SKILL.md" for s in SKILLS}
    if not need <= names or any(not n.startswith(top + "/") for n in names):
        raise SystemExit(f"archive layout check failed: missing {sorted(need - names)}")
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    print(f"packaged: {package(a.out)}")


if __name__ == "__main__":
    main()
