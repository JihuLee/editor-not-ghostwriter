# Evaluation

Two different questions, kept apart:

1. **Does the code do what its rules say?** Deterministic tests, run on every change.
2. **Does the skill make drafts better while keeping the author's meaning and voice?** An editing
   evaluation with models and people. **Not run yet.** Nothing in this repository should be read as
   evidence of editing quality until it is.

A drop in AI-tell counts is not an improvement on its own: an untouched draft has none added, and a
heavy rewrite can remove every listed word while losing the author.

## 1. Code tests (deterministic)

`python -m unittest discover -s tests -v` runs them. Besides extraction, building and installing, they
pin these guard behaviours:

| Case | Expected |
|---|---|
| Claim changes with everything else clean: increases→decreases, may→will, associated with→causes, some→all, upper→lower bound, suggest→show, dropped "not" | reverted, listed under "Meaning checks" |
| Numbers: two values swapped, fifteen→twenty, a number deleted, 15 ms→15 s, ten→10 | reverted |
| Grammar fixes: agreement, articles, prepositions, less→fewer, much→many, "the same as", grammar next to numbers | kept clean |
| A recorded slip whose fix swaps a claim word ("not favorable than"→"less favorable than") | kept with a warning |
| An author's own tier-B word added in many edits | each edit kept, total reported under "Cumulative changes" |
| Text that needs no edit | no edits |

How often the new checks block a correct fix, measured when they were added:

- 24 hand-made grammar fixes (`tests/test_guard_lint.py` holds most of them): 1 reverted, the
  "not favorable than" case, which is kept with a warning once it is on the author's watchlist.
- 31 real recurring-slip fixes applied to one author's own papers (private, not in the repository):
  0 reverted, 2 kept with a warning.

These are small fixed sets, not a sample of real editing.

## 2. Editing evaluation (protocol, not run)

**Conditions.** The same model, inputs and generation settings for each:

- A. a generic "polish this" request;
- B. a generic minimal-edit request;
- C. the skill before the change under test;
- D. the skill after it;
- plus the untouched draft as a baseline.

**Material.**

- Profile samples and evaluation manuscripts come from different documents.
- Several authors, and several section types (Introduction, Methods, Discussion).
- Public fixtures for regression tests are kept apart from authors' private material.

**Measures.**

- Rate of real errors fixed, against errors annotated in advance.
- Rate of unneeded edits.
- Claims, conditions and uncertainty preserved, judged edit by edit.
- Padding and repetition reduced, where the draft had them.
- The author's own judgement that the result still sounds like them.
- Naturalness and clarity for a reader who does not know the condition.
- Amount of change, and the follow-up work the author needed.

**Reading the results.**

- The untouched draft wins every preservation measure. Read preservation together with the error-fix
  rate.
- A detector's score is not an editing-quality score.
- Report untested measures as untested.

## 3. Sources, rules and what would test them

The 2026-11 entries were cited in a review of this repository and have not been re-read for this change;
they motivate a rule, they do not confirm it. No rule here has been tested by the editing evaluation.

| Source | Rule in this repository | Measure that would test it | Status |
|---|---|---|---|
| Kobak et al.; Czuma; MAKE 2026 (design.md §1) | tier-A/B word lists, em-dash rule | unneeded edits; author's voice judgement | in design.md since v0.1; untested |
| Liang et al. (design.md §2) | every rule relative to the author's samples | voice judgement for non-native authors | in design.md since v0.1; untested |
| ARIS; Nguyen et al. (design.md §4, §6) | fresh reviewers; two rounds | real errors found per round | in design.md since v0.1; operating choice |
| Hans et al. (design.md §5) | optional detector as a diagnostic | none (not an editing measure) | in design.md since v0.1 |
| Abdulhai et al., arXiv:2603.18161 (review, 2026-11) | meaning check on claim words; meaning review after the guard | claims, conditions and uncertainty preserved | cited, not re-read; rule tested on fixed cases only |
| Baumler et al., ACL 2026; Agarwal et al., arXiv:2409.11360 (review, 2026-11) | cumulative-use report; voice notes on stance and directness | voice judgement; unneeded edits | cited, not re-read; report only |
| Shan et al., EMNLP 2026; Miletić & Falk, LREC 2026 (review, 2026-11) | the separation in this file | all of section 2 | cited, not re-read; protocol not run |
