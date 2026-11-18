# voice-skill-builder (Claude Code plugin)

Two skills. `build-voice-skill`: point it at writing you did yourself (LaTeX, Markdown, plain text or
Word files) and it builds a private voice skill that revises your future drafts as a minimal-edit copy
editor. It measures your style, records your recurring slips, writes notes on your habits, runs
self-tests on your own text and installs the result in `~/.claude/skills/<name>/`. `revise-in-voice`: the
editing workflow every voice skill loads, so a plugin update improves your voice skill without a rebuild.

Install it with

```
/plugin install voice-skill-builder --marketplace JihuLee/editor-not-ghostwriter
```

and run it with `/voice-skill-builder:build-voice-skill` followed by the paths of your samples. Codex reads
the same plugin: `codex plugin marketplace add JihuLee/editor-not-ghostwriter`, then
`codex plugin add voice-skill-builder@editor-not-ghostwriter`. It needs only Python 3.9+. See the [repository README](https://github.com/JihuLee/editor-not-ghostwriter#readme)
for older Claude Code versions, the claude.ai route and privacy notes.

