# Writing the voice notes

The profile captures what can be counted. The voice notes capture what has to be read: how this person
builds a paragraph, which odd phrasings are deliberate, which mistakes they repeat. The built skill's
editor reads these notes before every edit, so write them as instructions to that editor.

The built `author_voice.md` puts generated sections first (measured habits, the connectives and frequent
sentence openers, and the watchlist table from `watchlist.json`), then these notes. Do not repeat the
numbers or the watchlist here; add what reading reveals.

## How to read

1. Read `WORK/stats.md` and `WORK/watchlist.json` first, so you know what is already covered.
2. Read a spread of each sample rather than one section: the opening, a methods or argument section, a
   results or discussion section, and the closing. At least 2,000 words in total, more for a varied corpus.
3. Compare the connectives in `stats.md` with what you read. The connective list is a fixed vocabulary;
   a signpost the author repeats that the list missed belongs under "Keep as is".
4. Write `WORK/voice_notes.md` with the template below. Replace every `<!-- FILL ... -->` comment; the
   build refuses notes that still contain one.

## Rules

- Quote only the author's own words from the samples. Quotes are at most 12 words everywhere, except the
  worked examples, which may quote up to 30 words.
- Copy wording, never findings: no result numbers, data or claims from the samples, which may be
  unpublished. Leave out co-authors' text and the names of collaborators or reviewers.
- Describe habits; do not grade them. "Opens most paragraphs with the claim, then the evidence" is useful;
  "writes clearly" is not.
- "How the author writes": record a habit only if it appears in more than one sample, or many times in
  one. "Keep as is": any correct idiosyncrasy that appears at least twice.
- When you cannot tell whether something is a slip or a deliberate idiosyncrasy, list it under
  "Keep as is", so the editor leaves it alone.

## Template

```markdown
### How the author writes

<!-- FILL: 5-10 bullets on habits the numbers do not capture: how paragraphs open and close, how claims
and results are stated, how notation or terms are introduced, favourite constructions. Each bullet ends
with one short example quoted from the samples. -->

### Slips a pattern cannot catch

<!-- FILL: recurring errors that need reading to spot, such as subject-verb agreement across a long
subject, article use with plural nouns, verb patterns, tense switches. One short example each with the
minimal fix. Write "None found." if there are none. -->

### Keep as is

<!-- FILL: idiosyncratic but correct phrasings that are part of the voice, including signposts the
connective list missed, so that neither the editor nor the reviewers "fix" them. -->

### Worked examples of minimal fixes

<!-- FILL: 3-5 real sentences from the samples, each followed by the smallest fix and a one-line reason.
Draw on the watchlist slips and the section above. Format:
- Original: "..."
  Fix: "..." (reason)
If the samples have no errors worth showing, give 3 examples of edits the editor should NOT make, with
the reason. -->
```
