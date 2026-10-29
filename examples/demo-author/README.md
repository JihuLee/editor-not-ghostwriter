# Demo author

A fictional author with invented papers about low-cost air-quality sensors. Nothing here is real research
or anyone's real writing; it exists so the builder can be tried and tested end to end.

- `samples/` - what the author "wrote": two LaTeX papers (hard-wrapped lines, custom `\sys` macro,
  `thm`/`lem` environments, natbib citations, footnotes, an appendix) and a Markdown blog post.
  About 3,300 words in total, just above the builder's minimum.
- `build-inputs/watchlist.json` and `build-inputs/voice_notes.md` - what Claude wrote in steps 4 and 5 of
  the builder after reading the samples: three recurring slips ("allows to", "despite of", "less" with
  countable nouns) and the author's habits ("We stress that", "Put differently,", semicolons).
- `draft.tex` - a new paper by the same author in which two paragraphs were "polished" by an LLM. The
  built skill's lint ranks exactly those two paragraphs first and lists the author's two slips.

Reproduce the build:

```bash
B=plugins/voice-skill-builder/skills/build-voice-skill
WORK=~/voice-skill-work/demo && mkdir -p $WORK
python3 $B/template/scripts/style_profile.py examples/demo-author/samples/* -o $WORK/profile.json --md $WORK/stats.md
python3 $B/scripts/build_skill.py --name demo-voice --author "the demo author" \
    --profile $WORK/profile.json --notes examples/demo-author/build-inputs/voice_notes.md \
    --watchlist examples/demo-author/build-inputs/watchlist.json --out $WORK/build/demo-voice --force
python3 $B/scripts/validate_skill.py $WORK/build/demo-voice --samples examples/demo-author/samples/*
python3 $WORK/build/demo-voice/scripts/ai_tell_lint.py examples/demo-author/draft.tex \
    --profile $WORK/build/demo-voice/references/author_profile.json
```
