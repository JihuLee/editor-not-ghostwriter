# Design notes

Why the builder and the skills it builds work the way they do. Each choice below answers a failure mode
of the obvious approach ("ask an LLM to polish the draft, then ask another one if it sounds human").

## 1. Editor, not ghostwriter

LLM involvement in scientific writing leaves population-level traces: a sharp rise in certain style words
after 2023 ("delves", "showcasing", "underscores", and common ones such as "crucial", "additionally",
"notably") [Kobak et al.], more em dashes in preprints [Czuma], and more polishing patterns such as
connective phrasing, value framing and contribution signalling [MAKE 2026]. These are exactly the features
an LLM *edit* adds to a human draft, and they are the features human reviewers notice.

Rewriting first and "humanizing" afterwards is a losing game. Detectors are trained against humanizers
[GPTZero; DAMAGE], while reviews of the field find detection unreliable on paraphrased, humanized or
co-written text [Sharimbayev and Kadyrov], so the outcome is a coin toss either way, and the author's voice
is gone in both cases. The robust fix is to keep generated text out of the draft: every word Claude does not
write is a word that cannot sound like Claude. Hence the editing ladder (word, phrase, clause, and only
then sentence), one sentence in and one sentence out, and no paragraph-level rewrites.

## 2. The baseline is the author

Commercial detectors misread non-native English as machine text [Liang et al.]. A fixed list of
"AI words" has the same problem in miniature: some people genuinely write "intricate" or use em dashes.
So every rule is relative to the author's own samples. This is meant to reduce that bias for the
author at hand; whether it does has not been measured (see [evaluation.md](evaluation.md)).


- a tier-A word the author uses twice or more becomes a soft (rate-based) signal for that author;
- em dashes, contractions and exclamation marks are hard rules only for authors whose samples have
  (almost) none;
- tier-B words, openers, hedges, intensifiers, summary closers and rhythm are compared with the author's
  own rates;
- layout rules (one sentence per line, or hard-wrapped paragraphs) follow what the author does;
- recurring slips come from the author's samples, so the editor fixes *their* errors and leaves their
  idiosyncrasies alone.

Function-word stylometry (Burrows' Delta over ~500-word chunks) [Burrows] gives a section-level check:
the profile stores how far the author's own chunks sit from their average, so a revised section can be
compared with the author's natural variation rather than with an arbitrary threshold.

## 3. Hard rules for content, warnings for style

Math, numbers, citation keys, theorem statements, proofs and code are frozen: an edit that changes them
is reverted no matter how good it looks, because a copy editor has no business changing results.
Style signals are graded instead. Unambiguous tells are reverted; borderline ones are kept and listed for
the author with the reason. Each changed line group is judged separately, so one bad line does not take a
clean neighbouring fix with it.

## 4. Reviewers that do not know what changed

A reviewer that is told "since last round we fixed X" rates the paper higher without it being better. One
open-source paper-improvement loop reports that carrying review context across rounds inflated a score
from a real 3/10 to 8/10, and that fresh reviewers recovered the 3/10 [ARIS]. The skills therefore run
each review lens in a fresh context with only the files, and never pass fix summaries along. The review
prompt follows the running-summary design of the best-performing open review harness in a recent
benchmark (check each passage against accumulated notation, definitions and claims) [Nguyen et al.], and
asks for locations and problems only, not replacement text.

The same benchmark found that AI review comments are complementary to human ones and that users mostly
complain about false positives and nitpicks, so the skills drop style preferences and nitpicks and favour
precision over recall.

## 5. Detectors are a diagnostic, never a target

Once a measure becomes a target it stops measuring. Iteratively rewriting a paper against an LLM reviewer
raises its score without improving it ("paper laundering") [Review Arcade], and content-preserving
rhetorical changes move AI-review scores [Rhetoric reward-hacking]. The same holds for detectors. The
optional detector check (Binoculars, a zero-shot detector where a lower score means more machine-like
[Hans et al.]) compares each changed paragraph before and after. A paragraph that moved toward "machine"
gets a second look, and its edits stand or fall on what a reader sees there: a detector's score for one
paragraph is not a validated measure of editing quality. Nothing is ever rewritten to raise a score.

## 6. Two rounds

The paper-improvement loop above found that a first round catches structural issues, a second catches
presentation issues, and later rounds add little [ARIS]. For an editor whose goal is to preserve a voice,
later rounds mostly trade the author's voice for a reviewer's taste, so the skills stop after two. This is
an operating choice based on one loop's report, not a measured optimum.

## 7. Disclosure

Publishers treat AI help with editing differently from AI-generated text. IEEE, for example, requires
AI-generated text to be disclosed in the acknowledgments and only recommends disclosure for editing and
grammar assistance [IEEE]. The built skill marks every passage Claude drafts, so the author can rewrite it
in their own words or disclose it.

## 8. Meaning and numbers are checked mechanically, then by reading

A copy edit can change what a sentence claims with one word ("increases" for "decreases", "may" for
"will", "some" for "all", "associated with" for "causes") while every other rule passes. The guard
therefore reverts an edit that adds, drops or swaps a word from a list of claim-carrying words (negation,
direction, modality, certainty, evidence, quantity, cause, comparison), unless the same edit fixes one of
the author's recorded slips, and compares numbers in order together with the word after each, so a swap,
a changed unit and a spelled-out quantity are caught too. These lists catch common cases, not meaning: a
kept edit can still change a claim in a way no list foresees, so the editor reads every kept edit against
the original and reports that review apart from the guard's result. Embedding similarity is not used as
a test of meaning. How often these checks block a correct grammar fix is measured on a small fixed set
(see [evaluation.md](evaluation.md)), not in real use.

## 9. Delivery: suggestions, measured against the author

A draft with no AI tells can still be hard to read: the main verb sits far from its subject, paragraphs
open with "There are", the abstract never states what was found. SciWrite [SciWrite] turns the editing
principles of Sainani's *Writing in the Sciences* course [Sainani] and Nature's guide to summary
paragraphs into a review skill. The built skill takes a short, reworded set of those principles as a
fourth review lens, delivery, credited in `reviewer_prompt.md` under SciWrite's CC BY 4.0 licence.

Three things change on the way in. First, the reviewer is given the author's habits from
`author_voice.md`, told that they are not problems, and asked to report a general rule (active voice,
shorter phrases) only where breaking it costs the reader; applied to everyone alike, such rules would
move every author toward one style, which this skill exists to prevent. Second, delivery findings are
suggestions. An unattended run lists them and changes nothing; an accepted one is applied after the
guard, as a separate pass with its own diff, because most of them restructure a sentence and the guard
would revert or flag that as an ordinary edit. Third, the checks on what each section must do (an
introduction that states the gap, an abstract that states the result) run only when the draft looks like
a research paper: it has an abstract or the usual sections, or the author named a venue. The author does
not declare a mode. SciWrite's pass on numbers and citations is left out, since the claims-evidence lens
and the guard cover it.

Whether the lens finds what a careful editor would, and how many of its suggestions authors accept, has
not been measured.

## References

- [ARIS] wanshuiyin/Auto-claude-code-research-in-sleep, `auto-paper-improvement-loop` skill (MIT).
  https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
- [Burrows] J. Burrows (2002). "Delta": a measure of stylistic difference and a guide to likely authorship.
  Literary and Linguistic Computing 17(3).
- [Czuma] P. Czuma (2026). Em-ergence of the em-dash: a population-level rise in em-dash frequency in medRxiv
  preprints at the dawn of the large-language-model era. arXiv:2606.29540.
- [DAMAGE] E. Masrour, B. Emi, M. Spero (2025). DAMAGE: Detecting adversarially modified AI generated text.
  GenAIDetect workshop. https://aclanthology.org/people/max-spero
- [GPTZero] G. A. Adam et al. (2026). GPTZero: Robust detection of LLM-generated texts. arXiv:2602.13042.
- [Hans et al.] A. Hans et al. (2024). Spotting LLMs with Binoculars: zero-shot detection of
  machine-generated text. ICML 2024. arXiv:2401.12070.
- [IEEE] IEEE Author Center, submission and peer review policies, "Guidelines for AI-generated text".
  https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/guidelines-and-policies/submission-and-peer-review-policies/
- [Kobak et al.] D. Kobak, R. González-Márquez, E.-Á. Horvát, J. Lause. Delving into LLM-assisted writing in
  biomedical publications through excess vocabulary. arXiv:2406.07016.
- [Liang et al.] W. Liang, M. Yuksekgonul, Y. Mao, E. Wu, J. Zou (2023). GPT detectors are biased against
  non-native English writers. arXiv:2304.02819.
- [MAKE 2026] Article measuring LLM-associated stylistic markers in PubMed abstracts. Machine Learning
  and Knowledge Extraction 8, 223 (2026). doi:10.3390/make8080223.
- [Nguyen et al.] D. Nguyen, W. Hao, Y. Elazar, C. Tan (2026). Benchmarking agentic review systems.
  arXiv:2606.19749.
- [Review Arcade] Review Arcade: on the human alignment and gameability of LLM reviews. arXiv:2605.28897.
- [Rhetoric reward-hacking] How can rhetoric reward-hack AI reviewers? Dissecting rhetorical sensitivity in
  AI-based peer review. arXiv:2608.08975.
- [Sainani] K. Sainani. Writing in the Sciences. Stanford University (online course).
  https://www.coursera.org/learn/sciwrite
- [SciWrite] L. A. Barba (2026). SciWrite: an Agent Skill for reviewing the writing quality of scientific
  manuscripts. Version 1.0.0. doi:10.5281/zenodo.23728600. https://github.com/labarba/sciwrite (skill text
  CC BY 4.0).
- [Sharimbayev and Kadyrov] Detection of AI-obfuscated, AI-refined, and humanized AI-generated text: a
  systematic review. Engineering, Technology & Applied Science Research 16(4), 2026.
