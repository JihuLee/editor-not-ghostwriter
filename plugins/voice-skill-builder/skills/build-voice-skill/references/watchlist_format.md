# watchlist.json

The author's recurring slips. The built skill's lint lists every hit in a draft as a safe minimal fix,
and the guard notes when an edit fixes one.

```json
[
  {"match": "discuss about", "fix": "discuss", "count": 3},
  {"match": "in the other hand", "fix": "on the other hand", "count": 2,
   "note": "fixed phrase"},
  {"match": "(?:informations|advices|equipments)", "regex": true, "label": "plural of an uncountable noun",
   "fix": "singular form", "count": 4}
]
```

Fields:
- `match` (required): a phrase. It matches whole words only, case-insensitively, so `discuss about`
  does not fire inside a longer word. With `"regex": true` it is a Python regular expression, still
  matched as whole words and case-insensitively; in JSON, write each backslash twice (`\\d`).
- `fix` (required): the usual minimal fix, as shown to the editor.
- `label`: a readable name shown instead of the regex in `author_voice.md` and the validation report.
- `note`: a short reason, shown in the "Why" column of `author_voice.md`.
- `count`: how often it occurs in the samples (from `slip_candidates.md` or your own count).

Guidelines:
- Include a slip only when it is a real error in context and recurs (two or more hits, or clearly systematic).
- Keep patterns narrow. A broad pattern fires on correct text in every future draft and teaches the
  author to ignore the list. "discuss about" is fine; "about" is not.
- Errors a regex cannot judge (subject-verb agreement, for instance) belong in the voice notes, not here.
- `[]` is a valid watchlist.
