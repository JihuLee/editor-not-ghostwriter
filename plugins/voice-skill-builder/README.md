# voice-skill-builder (Claude Code plugin)

One skill, `build-voice-skill`. Point it at writing you did yourself (LaTeX, Markdown, plain text or
Word files) and it builds a private skill that revises your future drafts as a minimal-edit copy editor:
it measures your style, records your recurring slips, writes notes on your habits, runs self-tests on your
own text and installs the result in `~/.claude/skills/<name>/`.

Install it with

```
/plugin install voice-skill-builder --marketplace JihuLee/editor-not-ghostwriter
```

and run it with `/voice-skill-builder:build-voice-skill` followed by the paths of your samples. It needs
only Python 3.9+. See the [repository README](https://github.com/JihuLee/editor-not-ghostwriter#readme)
for older Claude Code versions, the claude.ai route and privacy notes.
