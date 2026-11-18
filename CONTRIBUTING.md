# Contributing

- Run the tests before sending a change: `python -m unittest discover -s tests -v` (Python 3.9+, no
  third-party packages).
- Keep the scripts on the standard library. They run in Claude Code on users' machines and in claude.ai's
  sandbox, where installing packages may not be possible.
- Never add real people's writing (yours included) to `examples/` or `tests/`. Fixtures are synthetic.
- Changes to the word lists in `lexicon_en.py` should cite evidence that the word marks LLM-edited text,
  or explain the false positives a removal fixes. Update `docs/ai-tells.md` to match.
- New guard rules need a test that shows a planted edit being reverted or kept, as in
  `tests/test_guard_lint.py`.

## Releasing

1. Bump the version to the same number in `plugins/voice-skill-builder/.claude-plugin/plugin.json` and in
   `BUILDER_VERSION` (`scripts/build_skill.py`), and merge that to `main`.
2. In the repository's **Actions** tab, open **release** and click **Run workflow** on `main`. Pushing a
   tag such as `v0.3.0` does the same.

The workflow checks that the two version numbers and the tag agree, runs the tests, builds
`voice-skill-builder.zip` (the whole plugin, for claude.ai's Upload plugin) and publishes release
`v<version>` with generated notes and the zip attached. If that release already exists, it only replaces
the zip.

People who added the repository as a marketplace get a change from `main`, release or not, once the
version in `plugin.json` has gone up: marketplace sync and plugin updates follow the version, so bump it
for every change that should reach them. Every voice skill then uses the new workflow from its next run. Keep the engine
able to read profiles from older builds; when the profile format has to change, raise `version` in
`style_profile.py` and `PROFILE_FORMATS` in `voice_rules.py` together.
