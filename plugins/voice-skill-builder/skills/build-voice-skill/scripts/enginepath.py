"""Find the revise-in-voice skill, which holds the engine scripts the builder measures and tests with.

It is installed next to build-voice-skill: the two skills come together in the voice-skill-builder plugin,
and `npx skills add JihuLee/editor-not-ghostwriter` installs both. VOICE_ENGINE_DIR overrides the lookup.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENGINE_NAME = "revise-in-voice"
HERE = Path(__file__).resolve().parent


def find_engine(required: bool = True):
    candidates = []
    if os.environ.get("VOICE_ENGINE_DIR"):
        candidates.append(Path(os.environ["VOICE_ENGINE_DIR"]).expanduser())
    candidates.append(HERE.parent.parent / ENGINE_NAME)
    for c in candidates:
        if (c / "scripts" / "style_profile.py").exists() and (c / "SKILL.md").exists():
            return c.resolve()
    if not required:
        return None
    raise SystemExit(f"cannot find the {ENGINE_NAME} skill next to build-voice-skill ({HERE.parent.parent}). "
                     "Install the whole voice-skill-builder plugin: in claude.ai add the marketplace "
                     "JihuLee/editor-not-ghostwriter under Customize > Plugins; in Claude Code or Codex run "
                     "`npx skills add JihuLee/editor-not-ghostwriter -g`, which installs both skills.")


def use_engine() -> Path:
    """Put the engine scripts on sys.path and return the engine skill folder."""
    engine = find_engine()
    scripts = str(engine / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return engine
