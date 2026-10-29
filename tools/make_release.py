#!/usr/bin/env python3
"""Zip the builder skill for claude.ai: dist/build-voice-skill.zip (folder build-voice-skill/ at the top).

usage: python tools/make_release.py [-o dist]

Attach the zip to a GitHub release so claude.ai users can download it and upload it under
Customize > Skills. Claude Code users install the plugin instead (see README).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "voice-skill-builder" / "skills" / "build-voice-skill"
sys.path.insert(0, str(SKILL / "scripts"))
from package_skill import package  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    print(f"packaged: {package(SKILL, a.out, 'zip')}")


if __name__ == "__main__":
    main()
