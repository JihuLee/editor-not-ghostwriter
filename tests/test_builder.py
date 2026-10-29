import json
import os
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from _paths import BUILDER, DEMO, ENGINE, SAMPLES
import build_skill
import find_slips

PY = sys.executable
INPUTS = DEMO / "build-inputs"


def run(*args, env=None, cwd=None):
    return subprocess.run([PY, *map(str, args)], capture_output=True, text=True, env=env, cwd=cwd)


class TestNames(unittest.TestCase):
    def test_name_rules(self):
        self.assertEqual(build_skill.check_name("alex-voice"), [])
        self.assertTrue(build_skill.check_name("Alex-Voice"))
        self.assertTrue(build_skill.check_name("my-claude-voice"))
        self.assertTrue(build_skill.check_name("a" * 65))
        self.assertTrue(build_skill.check_name("double--hyphen"))


class TestFindSlips(unittest.TestCase):
    def test_demo_slips_found(self):
        found = find_slips.scan(SAMPLES)
        self.assertEqual(len(found["allow/enable/permit to + verb"]["hits"]), 4)
        self.assertEqual(len(found["despite of"]["hits"]), 2)
        self.assertEqual(len(found["less + countable plural"]["hits"]), 2)


class TestEndToEnd(unittest.TestCase):
    """measure -> build -> validate -> package -> install, as the builder skill does it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        r = run(ENGINE / "style_profile.py", *SAMPLES, "-o", cls.work / "profile.json", "--md", cls.work / "stats.md")
        assert r.returncode == 0, r.stderr
        cls.out = cls.work / "build" / "demo-voice"
        r = run(BUILDER / "build_skill.py", "--name", "demo-voice", "--author", "the demo author",
                "--profile", cls.work / "profile.json", "--notes", INPUTS / "voice_notes.md",
                "--watchlist", INPUTS / "watchlist.json", "--out", cls.out)
        assert r.returncode == 0, r.stderr + r.stdout

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_layout(self):
        for rel in ["SKILL.md", "references/author_profile.json", "references/author_voice.md",
                    "references/author_stats.md", "references/editor_rules.md", "references/reviewer_prompt.md",
                    "references/ai_tells.md", "scripts/diff_guard.py", "scripts/ai_tell_lint.py"]:
            self.assertTrue((self.out / rel).exists(), rel)
        text = (self.out / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: demo-voice\n"))
        self.assertNotIn("{{", text)
        prof = json.loads((self.out / "references" / "author_profile.json").read_text(encoding="utf-8"))
        self.assertEqual(len(prof["watchlist"]), 3)
        self.assertEqual(prof["skill"]["name"], "demo-voice")

    def test_validate_passes(self):
        r = run(BUILDER / "validate_skill.py", self.out, "--samples", *SAMPLES)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 failure(s)", r.stdout)

    def test_built_skill_runs_on_draft(self):
        r = run(self.out / "scripts" / "ai_tell_lint.py", DEMO / "draft.tex",
                "--profile", self.out / "references" / "author_profile.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("tier-A 'delve'", r.stdout)
        self.assertIn('"allows to"', r.stdout)

    def test_package_layout(self):
        r = run(BUILDER / "package_skill.py", self.out, "-o", self.work / "dist")
        self.assertEqual(r.returncode, 0, r.stderr)
        with zipfile.ZipFile(self.work / "dist" / "demo-voice.zip") as z:
            names = z.namelist()
        self.assertIn("demo-voice/SKILL.md", names)
        self.assertTrue(all(n.startswith("demo-voice/") for n in names))
        self.assertFalse(any("__pycache__" in n for n in names))

    def test_install_and_backup(self):
        home = self.work / "home"
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        r = run(BUILDER / "install_skill.py", self.out, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((home / ".claude" / "skills" / "demo-voice" / "SKILL.md").exists())
        r = run(BUILDER / "install_skill.py", self.out, env=env)
        self.assertNotEqual(r.returncode, 0)
        r = run(BUILDER / "install_skill.py", self.out, "--force", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        skills = sorted(p.name for p in (home / ".claude" / "skills").iterdir())
        self.assertEqual(skills, ["demo-voice"])
        self.assertEqual(len(list((home / ".claude" / "skill-backups").iterdir())), 1)

    def test_install_for_codex(self):
        home = self.work / "codex-home"
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        r = run(BUILDER / "install_skill.py", self.out, "--agent", "codex", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((home / ".agents" / "skills" / "demo-voice" / "SKILL.md").exists())
        self.assertFalse((home / ".claude").exists())
        self.assertIn("$demo-voice", r.stdout)
        r = run(BUILDER / "install_skill.py", self.out, "--agent", "codex", "--force", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(list((home / ".agents" / "skill-backups").iterdir())), 1)
        project = self.work / "codex-project"
        project.mkdir()
        r = run(BUILDER / "install_skill.py", self.out, "--agent", "codex", "--scope", "project", cwd=project)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((project / ".agents" / "skills" / "demo-voice" / "SKILL.md").exists())

    def test_install_dest_backup_stays_beside_dest(self):
        dest = self.work / "elsewhere" / "skills"
        r = run(BUILDER / "install_skill.py", self.out, "--dest", dest)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run(BUILDER / "install_skill.py", self.out, "--dest", dest, "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([p.name for p in dest.iterdir()], ["demo-voice"])
        self.assertEqual(len(list((dest.parent / "skill-backups").iterdir())), 1)

    def test_config_is_checked(self):
        bad = self.work / "bad_config.json"
        bad.write_text('{"latex": {"frozen": ["x"]}}', encoding="utf-8")
        r = run(BUILDER / "build_skill.py", "--name", "cfg-voice", "--profile", self.work / "profile.json",
                "--notes", INPUTS / "voice_notes.md", "--config", bad, "--out", self.work / "build" / "cfg-voice")
        self.assertNotEqual(r.returncode, 0)

    def test_rebuild_rules(self):
        foreign = self.work / "build" / "other-skill"
        foreign.mkdir(parents=True)
        (foreign / "keep.txt").write_text("not a skill", encoding="utf-8")
        r = run(BUILDER / "build_skill.py", "--name", "other-skill", "--profile", self.work / "profile.json",
                "--notes", INPUTS / "voice_notes.md", "--out", foreign, "--force")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((foreign / "keep.txt").exists())
        notes = self.work / "unfinished.md"
        notes.write_text("### How the author writes\n<!-- FILL: habits -->\n", encoding="utf-8")
        r = run(BUILDER / "build_skill.py", "--name", "x-voice", "--profile", self.work / "profile.json",
                "--notes", notes, "--out", self.work / "build" / "x-voice")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FILL", r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
