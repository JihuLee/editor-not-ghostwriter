# Contributing

- Run the tests before sending a change: `python -m unittest discover -s tests -v` (Python 3.9+, no
  third-party packages).
- Keep the scripts on the standard library. They run in Claude Code on users' machines and in claude.ai's
  sandbox, where installing packages may not be possible.
- Never add real people's writing (yours included) to `examples/` or `tests/`. Fixtures are synthetic.
- Changes to the word lists in `lexicon_en.py` should cite evidence that the word marks LLM-edited text,
  or explain the false positives a removal fixes.
- New guard rules need a test that shows a planted edit being reverted or kept, as in
  `tests/test_guard_lint.py`.
