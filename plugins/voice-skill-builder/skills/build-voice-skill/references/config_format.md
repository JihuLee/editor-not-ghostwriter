# config.json

Optional settings for one author. `build_skill.py --config` stores them in the built skill's profile,
and every script there reads them.

```json
{
  "latex": {
    "frozen_envs_extra": ["resultbox"],
    "unfrozen_envs": ["proof"],
    "macros": {"method": "FooNet"}
  },
  "allow": ["utilize", "moreover"]
}
```

- `latex.frozen_envs_extra`: LaTeX environments to treat as frozen (never edited, not counted as prose),
  for custom environments the extractor does not know. Environments declared with `\newtheorem`,
  `\declaretheorem` and similar are detected automatically.
- `latex.unfrozen_envs`: environments to treat as editable prose, typically `proof` when the author wants
  grammar fixes in proofs. Theorem statements should stay frozen.
- `latex.macros`: zero-argument macros to expand, for macros defined outside the samples (in a `.sty`
  file). Macros defined with `\newcommand` in the samples are expanded automatically.
- `allow`: words, tier labels from `scripts/lexicon_en.py`, or sentence openers that this author uses on
  purpose. They are never flagged, by the lint or the guard. Prefer this to deleting them from the lexicon.
  A tier-B word the author's samples already use at 0.5 per 1,000 words or more needs no entry; the guard
  already treats it as theirs.
