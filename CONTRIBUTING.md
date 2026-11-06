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
`build-voice-skill.zip` and publishes release `v<version>` with generated notes and the zip attached. If
that release already exists, it only replaces the zip.
