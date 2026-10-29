# Editor rules

Claude's edits must be invisible as Claude's. The guard (`scripts/diff_guard.py`) enforces the hard
rules mechanically; these notes explain how to make edits that pass it and still read like the author.
Worked examples taken from the author's own writing are in `author_voice.md`.

## The ladder

Climb only as far as the problem forces you.

1. **Word**: agreement, article, preposition, tense, a wrong term. Most fixes stop here.
2. **Phrase**: a garbled verb chain, a misplaced modifier, a redundant connective.
3. **Clause**: delete or reorder a clause; split a run-on at an existing "and"/"which" into two sentences.
   The guard reports a split as a warning (not a revert) as long as almost no words are added.
4. **Sentence**: only when the sentence cannot be parsed or says something false. Then:
   - keep the author's subject and main verb;
   - reuse the words of the original sentence and its neighbours before inventing any;
   - stay near the length of the sentence you replace; if that sentence is a run-on of 35+ words,
     split it at an existing connective (step 3) instead of compressing it;
   - one sentence in, one sentence out;
   - re-read it next to the sentences before and after: it must not be smoother than they are.

Never go to the paragraph level. A paragraph that needs restructuring goes to the author with a note on
what is wrong.

## Generic examples

These are invented to show the size of an edit. The author's own cases are in `author_voice.md`.

**Word.**
- "The results shows that the method converge faster." -> "show", "converges".
- "We compare the three variants in term of memory." -> "in terms of".

**Phrase / clause.**
- "Although the model is small, but it generalizes well." -> delete "but". Nothing else changes.
- "This design allows to reduce the memory footprint." -> "allows us to reduce".
- "The scheduler, which runs every minute and it checks the queue, is cheap." -> "and checks the queue".

**What the guard rejects, and why.**
- "We study how sensors drift over time." rewritten as "We delve into the intricate dynamics of sensor
  drift.": two tier-A words. Reverted. The original needed no edit.
- Adding "Notably, this approach seamlessly integrates calibration into the pipeline." after a paragraph:
  a new sentence, a tier-A word and an AI-favoured opener. Reverted.
- "The buffer is flushed every 10 seconds." changed to "... every 15 seconds.": a changed number. Reverted;
  if the number is wrong, the author fixes it.
- "This baseline, proposed by earlier work, is simple." changed to "This baseline---proposed by earlier
  work---is simple.": an em dash, when the author's samples have none. Reverted.
- Rewriting three sentences of a motivation paragraph in cleaner prose: no tells, but most of the
  paragraph's words changed, over the 20% budget. Warned. Find the one real error and fix only that.

## Layout

- Keep the author's source layout (see "Layout" in `author_voice.md`): the same line breaks and blank
  lines. If the author writes one sentence per line, keep it that way; if they hard-wrap, edit in place
  and do not re-wrap the paragraph.
- Do not reflow paragraphs; it turns a three-word fix into a twenty-line diff.
- Do not add or remove comments, and do not leave notes inside the draft. Notes for the author go in the report.

## Frozen content

Do not change, even to "fix" it: display and inline math, theorem/lemma/proposition/definition statements
and proofs, code blocks, numbers in text or tables, citation keys, labels and references, table contents,
the preamble or front matter. If something frozen is wrong (a typo in an equation, a number that disagrees
with a table), report it to the author with its location. The guard reverts these edits anyway.

## Words and devices

- Do not introduce anything listed in `ai_tells.md`. Tier-A words are reverted automatically; tier-B words
  and AI-favoured openers produce warnings.
- No em dashes unless the author uses them (see `author_voice.md`). A comma or parentheses usually fit.
- No "not only ... but also", no "It is worth noting", no closing summary sentences.
- No intensifiers or hedges the author did not write.
- Prefer the author's own connectives, listed in `author_voice.md`.

## Before running the guard

For each changed line, check: Is the meaning the same (unless the meaning was the error)? Is any new word
on the tells list? Does the line sound like the lines around it? If a fix made a sentence noticeably
smoother than its neighbours, it is probably too big.
