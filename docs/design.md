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
So every rule is relative to the author's own samples:

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

## 5. Detectors veto; they are never a target

Once a measure becomes a target it stops measuring. Iteratively rewriting a paper against an LLM reviewer
raises its score without improving it ("paper laundering") [Review Arcade], and content-preserving
rhetorical changes move AI-review scores [Rhetoric reward-hacking]. The same holds for detectors. The
optional detector check (Binoculars, a zero-shot detector where a lower score means more machine-like
[Hans et al.]) compares each changed paragraph before and after and can only *revert* an edit that moved it
toward "machine". Nothing is ever rewritten to raise a score.

## 6. Two rounds

The paper-improvement loop above found that a first round catches structural issues, a second catches
presentation issues, and later rounds add little [ARIS]. For an editor whose goal is to preserve a voice,
later rounds mostly trade the author's voice for a reviewer's taste, so the skills stop after two.

## 7. Disclosure

Publishers treat AI help with editing differently from AI-generated text. IEEE, for example, requires
AI-generated text to be disclosed in the acknowledgments and only recommends disclosure for editing and
grammar assistance [IEEE]. The built skill marks every passage Claude drafts, so the author can rewrite it
in their own words or disclose it.

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
- [Sharimbayev and Kadyrov] Detection of AI-obfuscated, AI-refined, and humanized AI-generated text: a
  systematic review. Engineering, Technology & Applied Science Research 16(4), 2026.
