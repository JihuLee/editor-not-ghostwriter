"""Shared paths for the test suite. Import this before the engine or builder modules."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "voice-skill-builder"
SKILL = PLUGIN / "skills" / "build-voice-skill"
ENGINE_SKILL = PLUGIN / "skills" / "revise-in-voice"
ENGINE = ENGINE_SKILL / "scripts"
BUILDER = SKILL / "scripts"
DEMO = ROOT / "examples" / "demo-author"
SAMPLES = sorted((DEMO / "samples").iterdir())

for p in (ENGINE, BUILDER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
