---
name: build-voice-skill
description: Build a personal skill that revises the user's drafts in their own voice, from samples of their own writing (LaTeX, Markdown, plain text or Word). Use when the user wants the assistant to learn their writing style from their papers or documents, to create or update a skill that edits their drafts without making them sound AI-written, or to install such a skill in Claude Code, Codex or claude.ai.
---

# Build a voice-preserving revision skill

This skill turns a person's own writing samples into a private skill, `<name>/`, that revises their
future drafts as a minimal-edit copy editor and reviewer. The built skill keeps the assistant's words out
of the draft: it finds problems, makes the smallest fix, and a guard script reverts any edit that adds AI
tells or changes math, numbers, citations or theorem statements. Everything is judged against a measured
profile of the author's own writing, so their habits are protected and only their slips get fixed.

Steps 3, 4, 6, 7 and 8 run scripts. Steps 4 and 5 also need careful reading of the samples, which is the
part no script can do.

## Paths

- `SKILL_DIR` is this skill's folder. Claude Code replaces `${CLAUDE_SKILL_DIR}` in this file with that
  folder when the skill loads (a text substitution, not an environment variable). Codex and claude.ai do
  not: there, use the folder this SKILL.md was loaded from, and write it in place of `${CLAUDE_SKILL_DIR}`
  in the commands below.
- `ENGINE` is `SKILL_DIR/template/scripts`.
- `WORK` is a working folder outside any git repository, by default `~/voice-skill-work`, so nothing
  private gets committed by accident.

Shell variables usually do not survive from one command to the next in an agent's shell, so set them at
the start of every command, or write the full paths in. For example:

```
SKILL_DIR="${CLAUDE_SKILL_DIR}"; ENGINE="$SKILL_DIR/template/scripts"; WORK="$HOME/voice-skill-work"; mkdir -p "$WORK"
```

The scripts need only Python 3.9+ and its standard library (use `python` if `python3` is missing).

## 1. Interview (one round)

Read `references/interview.md` and ask its questions in one round, with the defaults it gives. If nobody
is there to answer, use the defaults and say which ones you used.

## 2. Collect samples

Get the files the user wrote: `.tex`, `.md`, `.txt` or `.docx`. Keep only text the user drafted
themselves: drop sections a co-author wrote and text an LLM already polished, because whatever is in the
samples becomes the baseline. Finished pieces are better than rough drafts. Copy nothing into the
repository the user is working in.

Size: the scripts refuse fewer than 3,000 words of prose; 8,000+ words gives steadier numbers, 10,000+ is
better. You only learn the prose word count in step 3, so if it comes out under 8,000, tell the user once
and ask whether they have more of their own writing to add. If they don't, or nobody is there to ask,
continue and mention the thin baseline in your final message.

## 3. Measure

```
python3 "$ENGINE/style_profile.py" SAMPLE1 SAMPLE2 ... -o "$WORK/profile.json" --md "$WORK/stats.md" --check
```

Read the `--check` output before going on:
- "markup left in a sentence": the extractor missed an environment or macro. If it is an environment that
  is not prose (a custom result box, a listing), add it to `latex.frozen_envs_extra` in `$WORK/config.json`.
- "commands unwrapped blindly": usually formatting and harmless. If a macro stands for words (a method
  name defined in a .sty file), add it to `latex.macros`.
- A warning that the samples are not in English: stop. The lexicon is English-only.
- If the user wants proofs editable (interview question 3), put `"proof"` in `latex.unfrozen_envs`.

The format of `config.json` is in `references/config_format.md`. After writing it, rerun the command
above with `--config "$WORK/config.json"`.

## 4. Find the author's recurring slips

```
python3 "$SKILL_DIR/scripts/find_slips.py" SAMPLE1 SAMPLE2 ... -o "$WORK/slip_candidates.md"
```

The candidates are generic patterns that over-match on purpose. Check every hit in context (the line
numbers point at the hit itself). Keep a slip only when it is a real error and recurs (two or more times,
or clearly systematic). Then read the samples yourself for recurring slips the generic list lacks. Write
the result to `$WORK/watchlist.json` in the format of `references/watchlist_format.md`, with a `count` for
each entry. An empty list `[]` is fine when the author makes no recurring slips.

## 5. Write the voice notes

Follow `references/voice_notes_guide.md`: read a spread of the samples next to `$WORK/stats.md` and fill
in `$WORK/voice_notes.md` from the template there. These notes become the qualitative half of the built
skill's `author_voice.md`.

## 6. Build

```
python3 "$SKILL_DIR/scripts/build_skill.py" --name NAME --author "LABEL" \
    --profile "$WORK/profile.json" --notes "$WORK/voice_notes.md" \
    --watchlist "$WORK/watchlist.json" [--config "$WORK/config.json"] \
    --out "$WORK/build/NAME"
```

`NAME` and `LABEL` come from the interview. Add `--force` to replace an earlier build of the same name.

## 7. Validate

```
python3 "$SKILL_DIR/scripts/validate_skill.py" "$WORK/build/NAME" --samples SAMPLE1 SAMPLE2 ...
```

Every FAIL must be fixed before installing; WARN lines need a judgment call:
- A failed guard self-test usually means the samples use LaTeX conventions the extractor missed: fix
  `config.json` (step 3), rebuild with `--force`, validate again.
- Hard tells in the author's own samples mean either a sample was LLM-polished (drop it and remeasure) or
  the author genuinely uses that word (tier-A words used twice or more are already treated as theirs; add
  others to `allow` in `config.json`).
- A watchlist entry with zero hits is mistyped or too narrow; fix or drop it.
- A thin-baseline warning was already handled in step 2.

## 8. Install

- **Claude Code**: `python3 "$SKILL_DIR/scripts/install_skill.py" "$WORK/build/NAME"` copies it to
  `~/.claude/skills/NAME/` (add `--scope project` for `./.claude/skills/`). To replace an installed version,
  add `--force`; the old copy goes to `~/.claude/skill-backups/`. Then `/skills` should list it, and
  `/NAME` followed by what to revise runs it.
- **Codex**: the same command with `--agent codex` copies it to `~/.agents/skills/NAME/` (`--scope project`
  gives `./.agents/skills/`), with the same `--force` and backup behaviour. Then `/skills` should list it
  (restart Codex if it does not), and `$NAME` followed by what to revise runs it.
- **claude.ai**: `python3 "$SKILL_DIR/scripts/package_skill.py" "$WORK/build/NAME" -o "$WORK/dist"` writes
  `NAME.zip` (folder `NAME/` at the top, as claude.ai requires). The user uploads it under Customize >
  Skills and turns it on. If you can hand files to the user in the chat, pass `--ext skill` and send the
  `.skill` file; its card offers a "Save skill" button where the organization allows it.
- If another skill with the same purpose is installed (an older voice skill, or a generic revision skill),
  tell the user: two skills with near-identical descriptions compete for the same requests. Suggest
  removing the old one, or invoking the new one by name.

## 9. Optional dry run

With a subagent tool, give a fresh subagent only the installed skill's path, one section of a real draft
and a request such as "Lint this section and fix grammar only; don't change content", and read the guard
report it produces. Many WARN items on harmless edits mean a rule is too strict for this author: add the
word or opener to `allow` in `config.json`, or a missed slip to the watchlist, then rebuild and reinstall
with `--force`. Without a subagent tool, skip this step and suggest the user try the skill on a short
section (`/NAME` in Claude Code, `$NAME` in Codex).

## Updating the skill

Rerun steps 3 to 8 with all samples, old and new. Reuse `watchlist.json`, `voice_notes.md` and
`config.json`, refreshing the watchlist counts from a new `find_slips.py` run and editing the notes where
the new samples change the picture. Build and install with `--force`.

## Privacy

The built skill holds statistics, short phrases and a few quoted sentences from the samples. Keep it
private: build in `WORK`, do not commit it, and do not share the .zip unless the user wants to. The
scripts make no network calls. The optional detector check runs a local model only; never paste an
unpublished manuscript into an online detector.
