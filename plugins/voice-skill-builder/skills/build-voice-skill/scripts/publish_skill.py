#!/usr/bin/env python3
"""Put a built voice skill into a private Git repository laid out as a plugin marketplace.

usage:
  python publish_skill.py work/build/alex-voice --repo ~/src/alex-voice-skill [--owner "Alex"]

Optional. A voice skill uploaded to claude.ai has to be saved again whenever it is rebuilt (a new
standing request, new samples). Kept in a private repository that claude.ai follows as a marketplace
(Customize > Plugins > Add > Add marketplace, with Sync automatically on), a rebuild reaches claude.ai,
Cowork and Claude Code once it is merged into the repository's default branch.

--repo is a local clone of that repository. The script copies the skill to
plugins/<name>/skills/<name>/, writes plugins/<name>/.claude-plugin/plugin.json with the version raised
by one patch step (marketplace sync follows the version), and writes .claude-plugin/marketplace.json and
a README.md when they are missing. When the skill is unchanged it touches nothing. It runs no git
commands: review the change, then commit and push it yourself.

Keep the repository private: the skill holds statistics and a few quoted sentences from your writing.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
from pathlib import Path

FIRST_VERSION = "1.0.0"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
README = """# {name}

Private voice skill of {author}, built with the voice-skill-builder plugin
(https://github.com/JihuLee/editor-not-ghostwriter). It holds the author's data only; the editing workflow
is the plugin's revise-in-voice skill, so that plugin must be installed too.

Keep this repository private: the skill holds statistics and a few quoted sentences from the author's
writing. Rebuild it with the builder and update it with publish_skill.py; edit nothing here by hand.
"""


def bump(version: str) -> str:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version or "")
    if not m:
        return FIRST_VERSION
    major, minor, patch = map(int, m.groups())
    return f"{major}.{minor}.{patch + 1}"


def same_tree(a: Path, b: Path) -> bool:
    if not b.is_dir():
        return False
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__", ".DS_Store"])
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(same_tree(a / d, b / d) for d in cmp.common_dirs)


def read_skill(skill: Path) -> dict:
    prof = skill / "references" / "author_profile.json"
    if not (skill / "SKILL.md").exists() or not prof.exists():
        raise SystemExit(f"{skill} is not a voice skill built by build_skill.py")
    meta = json.loads(prof.read_text(encoding="utf-8")).get("skill") or {}
    if meta.get("name") != skill.name:
        raise SystemExit(f"{skill}: the folder name must equal the skill name ({meta.get('name')})")
    return meta


def publish(skill_dir, repo_dir, owner=None) -> dict:
    skill = Path(skill_dir).expanduser().resolve()
    repo = Path(repo_dir).expanduser().resolve()
    meta = read_skill(skill)
    if not repo.is_dir():
        raise SystemExit(f"{repo} does not exist; clone your private repository there first")
    if skill == repo or repo in skill.parents:
        raise SystemExit("build the skill outside the repository and publish it from there")
    name = skill.name
    author = owner or meta.get("author") or "the author"
    plugin = repo / "plugins" / name
    target = plugin / "skills" / name
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    old_version = manifest.get("version")

    if same_tree(skill, target) and old_version:
        return {"changed": False, "version": old_version, "target": target}

    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill, target, ignore=IGNORE)

    version = bump(old_version) if old_version else FIRST_VERSION
    manifest.update({
        "name": name,
        "version": version,
        "description": manifest.get("description") or
        f"{author}'s private voice skill (data only). Needs the voice-skill-builder plugin.",
    })
    manifest.setdefault("author", {"name": author})
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    market = repo / ".claude-plugin" / "marketplace.json"
    if not market.exists():
        market_name = re.sub(r"[^a-z0-9]+", "-", repo.name.lower()).strip("-") or f"{name}-skill"
        market.parent.mkdir(parents=True, exist_ok=True)
        market.write_text(json.dumps({
            "name": market_name,
            "description": f"{author}'s private voice skill.",
            "owner": {"name": author},
            "plugins": [{"name": name, "source": f"./plugins/{name}",
                         "description": f"{author}'s voice skill for the voice-skill-builder plugin."}],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readme = repo / "README.md"
    if not readme.exists() or not readme.read_text(encoding="utf-8").strip() \
            or readme.read_text(encoding="utf-8").strip() == f"# {repo.name}":
        readme.write_text(README.format(name=name, author=author), encoding="utf-8")
    return {"changed": True, "version": version, "previous": old_version, "target": target}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_dir", help="the built voice skill, e.g. ~/voice-skill-work/build/alex-voice")
    ap.add_argument("--repo", required=True, help="local clone of your private repository")
    ap.add_argument("--owner", help="name shown as the plugin's author (default: the skill's author label)")
    a = ap.parse_args()
    res = publish(a.skill_dir, a.repo, a.owner)
    if not res["changed"]:
        print(f"unchanged: {res['target']} already holds this build (version {res['version']}); nothing to push")
        return 0
    was = f" (was {res['previous']})" if res.get("previous") else ""
    print(f"published to {res['target']}, plugin version {res['version']}{was}")
    print("Next: review the change, commit and push it (or open a pull request and merge it) on the default "
          "branch. claude.ai picks it up through Sync automatically or Customize > Plugins > Check for updates.")
    if not (Path(a.repo).expanduser() / ".git").exists():
        print("WARNING: the --repo folder is not a git clone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
