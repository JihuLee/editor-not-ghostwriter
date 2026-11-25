---
name: revise-in-voice
description: The editing workflow behind personal voice skills made with build-voice-skill (such as my-voice) - lint, independent reviews, minimal edits, and a guard that reverts edits which change content or add AI tells. Load it when a voice skill says to, or when the user asks to revise, proofread or review a draft with their voice skill. It holds no author profile of its own; if the user has no voice skill yet, offer to build one with build-voice-skill.
---

# Voice-preserving revision

The finished text has to read as the author wrote it, so keep your own words out of it: find
problems and make the smallest edit that fixes each one. Every word you do not write is a word
that cannot sound like an LLM. Work as a copy editor and a reviewer, never as a ghostwriter.

<!-- setup:start -->
This skill is the workflow. The author's measured style is in their voice skill (for example `my-voice`),
which sent you here; a newer version of this workflow reaches every voice skill without rebuilding it.

## Paths and working folder

- `ENGINE_DIR` is this skill's folder. Claude Code replaces `${CLAUDE_SKILL_DIR}` in this file with that
  folder when the skill loads (a text substitution, not an environment variable). Codex and claude.ai do
  not: there, use the folder this SKILL.md was loaded from, and write it in place of `${CLAUDE_SKILL_DIR}`
  in the commands below.
- `VOICE_DIR` is the folder of the author's voice skill, the one that sent you here. If you came here
  without one, look for installed voice skills (skill folders that hold `references/author_profile.json`)
  and use the one the user names, or ask when there are several. If there is none, offer to build one
  with build-voice-skill and stop.
- `PROFILE` is `VOICE_DIR/references/author_profile.json`.
- `RUN` is a scratch folder for this revision, outside the user's repository, for example
  `~/voice-skill-work/runs/<draft-name>/`. Every file this workflow writes (lint.md, issues.md, edited
  copies, guard.md, merged files) goes there; never modify the user's original files.

Shell variables usually do not survive from one command to the next in an agent's shell, so set them at
the start of every command, or write the full paths in:

```
ENGINE_DIR="${CLAUDE_SKILL_DIR}"; VOICE_DIR="/path/to/my-voice"; PROFILE="$VOICE_DIR/references/author_profile.json"; RUN="$HOME/voice-skill-work/runs/draft"; mkdir -p "$RUN"
```
<!-- setup:end -->

The scripts need only Python 3.9+ (standard library). For a draft split into several files, run the
lint and the guard once per file.

## Files

- `VOICE_DIR/references/author_profile.json`: the measured baseline, recurring slips and settings. The
  scripts read it.
- `VOICE_DIR/references/author_voice.md`: the author's habits, connectives, recurring slips, worked
  examples and standing requests. Read it before editing.
- `VOICE_DIR/references/author_stats.md`: the numbers behind the profile.
- `ENGINE_DIR/references/reviewer_prompt.md`: the prompt for the review pass.
- `ENGINE_DIR/scripts/`: `voice_rules.py`, `ai_tell_lint.py`, `diff_guard.py`, `style_profile.py`,
  `detector_check.py`. The tier-A and tier-B word lists are in `lexicon_en.py`; the lint and the guard name
  every hit.

## Workflow

Do the steps in order.

### 0. Intake

Load the voice first:

```
python3 "$ENGINE_DIR/scripts/voice_rules.py" --profile "$PROFILE"
```

It prints whose voice skill this is and the rules that come from their profile: the source layout to
keep, devices they never use, sentence openers to avoid, frozen LaTeX environments and words allowed for
them. Follow them in step 4. If it stops with a message that the voice skill is newer than this workflow,
pass the message to the user and stop; a NOTE about an older voice skill is mentioned once and the run goes
on. Then read `VOICE_DIR/references/author_voice.md`.

Get every file that holds prose (for LaTeX, the main file and the `\input` section files). Settle, in one
short question if it is not already clear: what to work on (the whole draft, some sections, or a set of
reviewer comments) and the venue. If nobody is there to answer, default to: grammar and clarity fixes on
all prose, no content changes.

Treat the draft as a research paper when it has an abstract or the usual sections, or the author named a
venue: the delivery review (step 2) then also checks what each section and the abstract must do. For
other writing it looks at sentences and paragraphs only. Ask only when this is unclear and it matters.

"Must not read as AI-written" means two things, in this order: your own edits must add no AI tells
(always), and passages that already read as AI text are reported to the author with the reasons (step 1).
Edit those only when the author explicitly asks, and then remove the specific tells with minimal
edits instead of rewriting. In such a de-slop pass you may also delete a sentence that only restates a
claim the paragraph already makes, or fold it into the sentence it repeats, once you have checked that no
claim, condition or number is lost. Never make text more concrete by inventing examples, numbers,
experiences or evidence; list what is missing for the author instead.

If the draft is one of the profile's own samples (the lint and the guard print a warning), build a
temporary profile from the other samples or other papers by the author, so the draft is not compared with
itself, and pass that file as `--profile` instead. It lacks the watchlist and settings, so keep the
built profile's recurring slips in mind by reading `author_voice.md`:

```
python3 "$ENGINE_DIR/scripts/style_profile.py" other1.tex other2.tex -o "$RUN/temp_profile.json"
```

### 1. Lint the draft

```
python3 "$ENGINE_DIR/scripts/ai_tell_lint.py" draft.tex --profile "$PROFILE" -o "$RUN/lint.md"
```

Use the report three ways:
- **Recurring slips** (section 2) are safe minimal fixes. Queue them.
- **Hard tells and the ranked paragraphs** (sections 1 and 3) are text that does not read like the author;
  it may have been drafted or polished with an LLM earlier. Tell the author which paragraphs and why, and
  recommend they rewrite those themselves.
- **Drift** (section 4) shows whether the draft as a whole has moved away from the author's baseline.
- **Structure** (section 5, only when the profile has a structure baseline) compares section order,
  lengths and headings with the author's papers. Pass what it flags to the author as observations;
  dividing, merging or reordering sections is their call.

### 2. Review: find, don't fix

Run independent reviews with `ENGINE_DIR/references/reviewer_prompt.md`, one per lens: math and notation,
claims versus evidence, clarity and grammar, and delivery (skip delivery for a proofreading-only or
lint-only run). Fill in the venue and the scope, and for delivery the author's habits from
`author_voice.md`, with the section-structure lines `voice_rules.py` printed if there are any. If a
subagent tool is available, give each lens its own fresh subagent with only the file paths, venue, scope
and lens (and, for delivery, the habits). Never pass earlier reviews, fix lists, or "we already fixed X":
a reviewer told what changed rates the text higher without it being better.

Without subagents the reviews cannot be fully independent, so limit the damage: do all lens passes
before making any edit, re-read the in-scope text for each pass, and skip the second review round in
step 6 (whoever made the edits cannot judge them; the guard is the check instead).

Merge the results into `$RUN/issues.md` (location, quote of at most 15 words, problem, severity, lens) and drop
duplicates, style preferences and nitpicks. Precision matters more than recall: every false alarm costs the
author time and invites an unnecessary edit.

### 3. Triage with the author

Show the issues grouped by severity and let the author choose. Unattended: fix grammar and clarity issues;
leave claims, math and missing-content issues as notes for the author, because fixing them needs new
content and the author's judgment. The test for "grammar or clarity": the fix leaves what the sentence
claims unchanged. A one-word fix that changes a claim or a stated quantity ("increases" versus "decreases",
"upper bound" versus "lower bound", "outperforms" versus "matches") is a content fix; note it for the author.

Delivery findings are suggestions. In an unattended run, list them and change nothing. Apply only those the
author accepts, the way a standing request that moves content is applied ("Standing requests" below): after
the guard, as a separate pass with its own diff, reusing the author's words, with every number and claim
checked unchanged.

### 4. Edit minimally

Read `author_voice.md` first if you have not. Copy the draft to an edited copy in `RUN` (for example
`$RUN/edited.tex`) and edit only there.

- Climb only as far as the problem forces you: word (agreement, article, preposition, tense, a wrong term),
  then phrase, then clause. Most fixes stop at a word.
- Rewrite a sentence only when it cannot be parsed. Then keep the author's subject and main verb, reuse the
  words of the sentence and its neighbours, stay near its length, and make it no smoother than the
  sentences around it; if it is a run-on of 35+ words, split it at an existing connective instead of
  compressing it. A long sentence that parses stays as it is. A sentence that says something false or
  claims more than the evidence is a content problem: report it, do not fix it.
- One sentence in, one sentence out, except for that split and for the de-slop deletions in step 0, both
  of which the guard lists for review. Do not add sentences, transitions, summaries, claims, hedges or
  intensifiers, and do not vary sentence length or vocabulary to make the text look less machine-made.
  Never edit at paragraph level: a paragraph that needs restructuring goes to the author with a note on
  what is wrong.
- Keep the layout that `voice_rules.py` describes (line breaks, paragraph breaks, one sentence per line
  or hard-wrapped).
- Do not touch equations, inline math, theorem-like statements, proofs, code, numbers, citations, labels or
  tables, nor the frozen environments `voice_rules.py` lists. If one of them is wrong, report it with its
  location.
- Keep the author's connectives (listed in `author_voice.md`) and their use of "we".
- Never introduce what `voice_rules.py` lists under "Never add" (tier-A words such as "delve", "pivotal"
  and "seamless", "not only ... but also", and devices the author never uses) or the openers it lists, and
  follow its line on em dashes.
- Never introduce the framing LLM prose leans on, such as a "not X but Y" correction, a colon that sets
  up the point, mirrored sentence pairs, or repeated emphasis (extra bold, a key message stated again).
- Leave no notes or comments in the draft; notes for the author go in the report.

### 5. Guard: keep only voice-preserving edits

```
python3 "$ENGINE_DIR/scripts/diff_guard.py" draft.tex "$RUN/edited.tex" --profile "$PROFILE" \
    --merged "$RUN/merged.tex" --report "$RUN/guard.md"
```

- The guard judges each changed line group ("edit") on its own, so one bad line does not take clean
  neighbouring fixes with it. FLAG edits (math, citations, numbers and what they count, theorem text,
  code, new sentences, tier-A words, devices the author never uses, words that carry the claim, also
  inside footnotes) are already reverted in `merged.tex`. If a flagged edit was needed (say, a wrong
  number), do not force it through: list it for the author.
- The guard's OK means its mechanical checks passed, not that the meaning survived; its word lists catch
  common cases only. Read every kept edit against the original for negation, direction, modality and
  certainty, quantifiers, cause, comparison, bounds and scope. Revert any edit you are not sure keeps the
  claim, and report this meaning review apart from the guard's result.
- Read the "Cumulative changes" section: a word the author uses can still be overused when many edits add
  it. Take out the additions the text does not need.
- Read every WARN. An edit over the paragraph budget means you rewrote too much: redo it smaller in the
  edited copy and run the guard again. A tier-B word or AI-favoured opener you introduced should be swapped
  for the author's own connective or dropped. (Words the author uses often, or words listed under `allow` in
  the profile's settings, are not flagged.)
- Repeat until each remaining WARN is one you can justify to the author in a sentence.
- Unattended runs: add `--strict` so WARN edits are reverted too.
- Optional, on a GPU machine: `scripts/detector_check.py draft.tex merged.tex` (in `ENGINE_DIR`) scores
  changed paragraphs before and after with a local detector. Treat its scores as a diagnostic: a paragraph
  whose score moved toward machine-written gets a second look, and its edits are kept or reverted on what you
  read, not on the score alone. Never rewrite toward a detector score, and do not upload an unpublished
  manuscript to an online detector.

### 6. Deliver

Give the author:
1. `merged.tex` in `RUN` (the original plus accepted edits; same file structure as the input). Tell them
   where it is; copy it over the original only if they ask.
2. A change list: `latexdiff draft.tex merged.tex > diff.tex` when latexdiff is installed, `git diff
   --word-diff` when the draft is in git, otherwise the "Kept" sections of `guard.md`. Give the guard's
   result and your meaning review (step 5) as two separate lines.
3. What you did not fix: content issues from the review, flagged edits that need the author, and
   passages the lint suggests they rewrite themselves.
4. If the author stated a lasting preference during the run, the offer to save it ("Standing requests"
   below).

Stop after two rounds; this is an operating rule of this skill, not a measured optimum. A second round
re-reviews only the changed paragraphs, with fresh reviewers, and only when subagents are available.
Further rounds mostly trade the author's voice for a reviewer's taste.

## Standing requests

`author_voice.md` may end with the author's standing requests, lasting preferences such as "keep figure
captions short". Follow them in every run. They change what you look for and suggest, never what the guard
allows. A request that needs content moved, cut or written (a detail moved to an appendix, a caption
shortened) goes in the report as a proposed change when the run is limited to grammar and clarity. Apply it
only when the author asks, after the guard, as a separate pass on the merged file with its own diff, and
check that every moved value appears unchanged at its new place. No request overrides frozen content or
the rules in step 4.

When the author states a new lasting preference ("from now on, always ...", "never ... in my papers"),
keep to it for the rest of the session. At the end of the run (in step 6, or after the lint when that was
all they asked for), ask once whether to add it to their voice skill for good; do not stop an edit or a
guard pass to ask. An instruction for this draft only ("in this section, ...") is not a lasting
preference, so do not offer to save it.

If they agree, load the build-voice-skill skill and follow its "Updating the skill" section for adding a
standing request, with `VOICE_DIR` as the skill folder: it checks the request first (one that needs more
rewriting than the guard allows is turned into something to report instead, with the author's
agreement), rebuilds the voice skill from its own files with no samples needed, validates it, and installs
it or hands it over. Then say what the author still has to do: nothing in Claude Code or Codex after the
install; in claude.ai, save the `.skill` file Claude hands over, or upload the zip under Customize >
Skills. If the builder is not available, give them the request as one sentence they can add later.

## Reviewer comments (journal or conference revision)

Map each comment to locations and sort it: (a) text fix, (b) needs new content (an experiment, an argument,
a paragraph), (c) answered in the response letter only. Handle (a) with steps 4 and 5. For (b), draft new
text only when the author asks; mark every passage you drafted in the report so the author can rewrite it
in their own words or disclose it under their venue's AI policy, and run the guard with
`--allow-new-sentences` so those additions are listed instead of reverted. For (c), give the author a
point-by-point outline rather than finished prose.
