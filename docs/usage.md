# Usage details

The parts of the workflow the README leaves out: running the scripts without the plugin, the guard's full
rule set, the demo author, privacy details and the repository layout. For the reasons behind each choice,
see [design.md](design.md).

## How it works

```
your samples (.tex .md .txt .docx)
   │
   ├─ style_profile.py ── numbers: rhythm, layout, connectives, devices, function words
   ├─ find_slips.py + Claude ── your recurring slips (watchlist)
   └─ Claude reads the samples ── voice notes: habits to keep, slips a pattern can't catch
   │
   ▼
build_skill.py ──► <name>/  (your private voice skill: data only)  ──► validate_skill.py (self-tests on your own text)
                                                                   ──► install_skill.py (Claude Code, Codex) / package_skill.py (claude.ai)

Using <name> on a draft: <name> loads revise-in-voice (the workflow, from the plugin) with your data
  lint (AI tells, your slips, drift from your baseline)
  → four independent reviews that find but do not fix (the fourth, delivery, only suggests)
  → minimal edits
  → diff_guard.py keeps clean edits, reverts the rest, lists the doubtful ones
  → merged draft + change report
```

The builder needs nothing but Python 3.9+ and its standard library. The scripts refuse fewer than 3,000
words of prose; 8,000 words or more gives steadier numbers.

## Your skill and the plugin

The plugin has two skills. `build-voice-skill` builds your voice skill; `revise-in-voice` is the editing
workflow with its scripts (lint, guard, reviewer prompt). Your voice skill holds only your data
(`author_profile.json`, `author_voice.md`, `author_stats.md`) and a short `SKILL.md` that loads
`revise-in-voice`. So:

- **A plugin update reaches your skill by itself.** In claude.ai, turn on Sync automatically for the
  marketplace (or use Check for updates); in Claude Code, enable auto-update for the marketplace or run
  `npx skills update`. No rebuild, no new upload.
- **You rebuild and upload only when your data changes**: new samples, or a standing request added.
- **Keep the plugin installed** wherever you use your voice skill. Without it, the voice skill says what
  to install and does not edit.
- **Standalone builds** (`build_skill.py --standalone`) copy the workflow and scripts into the skill, for
  places where the plugin cannot be installed. They do not follow plugin updates; rebuild them.

A voice skill built before version 0.9 is a standalone build. Rebuild it once with `--from-skill` (no
samples needed) to turn it into one that follows the plugin.

## Keeping your skill in a private repository (optional)

Your own data changes too: a new standing request, new samples. In Claude Code and Codex the builder
simply reinstalls the skill. On claude.ai a rebuilt skill has to be saved again; from a claude.ai chat that
is one click (Save skill, then Upload and replace), but Claude Code cannot save to your claude.ai account.
If you update often and do it from Claude Code, keep the skill in a private GitHub repository instead:

1. Create an empty **private** repository, for example `you/my-voice-skill`, and clone it.
2. Build or rebuild the skill as usual, then
   `python3 $BUILDER/publish_skill.py $WORK/build/my-voice --repo ~/src/my-voice-skill`. It lays the
   repository out as a plugin marketplace (`plugins/my-voice/skills/my-voice/`) and raises the plugin
   version, which is what marketplace sync follows. Commit and push, or merge a pull request.
3. On claude.ai, Customize > Plugins > Add > Add marketplace with `you/my-voice-skill`. Give the Claude
   GitHub App access to the repository when asked, turn on **Sync automatically**, and add the plugin.
   Then remove the copy you uploaded under Customize > Skills, so only one is active.

From then on, ask the builder in Claude Code to change your skill and to publish it to the repository;
once the change is on the default branch, claude.ai, Cowork and Claude Code pick it up (or use Check for
updates). The repository holds statistics and a few quoted sentences from your writing, never the
samples themselves: keep it private. In Claude Code the skill is then called `/my-voice:my-voice`.

## Scripts only

```bash
git clone https://github.com/JihuLee/editor-not-ghostwriter && cd editor-not-ghostwriter
ENGINE=plugins/voice-skill-builder/skills/revise-in-voice/scripts
BUILDER=plugins/voice-skill-builder/skills/build-voice-skill/scripts
WORK=~/voice-skill-work

python3 $ENGINE/style_profile.py ~/papers --list      # what a folder contributes, with word counts
python3 $ENGINE/style_profile.py ~/papers -o $WORK/profile.json --md $WORK/stats.md --check
python3 $BUILDER/find_slips.py ~/papers -o $WORK/slip_candidates.md
# write $WORK/watchlist.json and $WORK/voice_notes.md (formats in the skill's references/ folder)
python3 $BUILDER/build_skill.py --name my-voice --profile $WORK/profile.json \
    --notes $WORK/voice_notes.md --watchlist $WORK/watchlist.json --out $WORK/build/my-voice
python3 $BUILDER/validate_skill.py $WORK/build/my-voice --samples ~/papers
python3 $BUILDER/install_skill.py $WORK/build/my-voice     # add --agent codex for Codex
python3 $ENGINE/voice_rules.py --profile $WORK/build/my-voice/references/author_profile.json
python3 $ENGINE/ai_tell_lint.py draft.tex --profile $WORK/build/my-voice/references/author_profile.json
```

Without an agent, add `--standalone` to the build if you want the skill folder to carry the scripts too.

Each script that takes samples accepts files, folders or both. A folder means every `.tex`, `.md`, `.txt`
and `.docx` file inside it, subfolders included; hidden folders and Word lock files are skipped.

Standing requests (lasting preferences such as "keep figure captions short") go in with
`--requests requests.md` or `--add-request "..."`. To add one later without the samples, rebuild from the
installed skill: `build_skill.py --from-skill ~/.claude/skills/my-voice --add-request "..." --out
$WORK/build/my-voice --force`, then install it again.

The voice notes are the one step that needs reading rather than counting; without Claude, write them
yourself or build with `--allow-missing-notes`.

## What the guard does with an edit

| Reverted (FLAG) | Kept but listed for you (WARN) |
|---|---|
| touches math, numbers, citation keys, theorem statements, proofs, code, preamble | adds a tier-B word ("additionally", "comprehensive", ...) or an AI-favoured opener that you rarely use |
| adds a tier-A word ("delve", "pivotal", "seamless", ...) that you don't use yourself | splits or removes a sentence, changes a paragraph break |
| adds an em dash, contraction or "!" when your own samples have none | changes more than 20% of a paragraph's words |
| adds a sentence | flattens the paragraph's sentence rhythm, adds a summary-style closing sentence |
| reorders numbers, changes the word after one (its unit or object) or how it is written (ten -> 10) | swaps a claim word in an edit that fixes one of your recorded slips |
| adds, drops or swaps a word that carries the claim: not, may/will, some/all, increase/decrease, upper/lower, suggest/show, associated/causes, ... | |

After the per-edit checks, the report adds two sections. **Meaning checks** lists every edit that touched
a claim word. **Cumulative changes** lists words that the kept edits together added beyond your own rate,
your own words included; nothing is reverted for it. A kept edit has passed mechanical checks only: read
it against the original.

Each changed line group is judged on its own, so one bad line never takes a clean neighbouring fix with
it. `--strict` reverts the WARN edits too, for unattended runs. Words you use often are exempt
automatically; anything else you use on purpose can go in the build's `config.json` under `allow`.

## The demo author

`examples/demo-author/` holds three samples by a fictional author (invented papers about air-quality
sensors), a draft with two LLM-polished paragraphs, and the watchlist and voice notes a builder run
produced. The end-to-end test builds `demo-voice` from them:

```bash
python -m unittest discover -s tests -v
```

To build it by hand and lint the draft, follow [examples/demo-author/README.md](../examples/demo-author/README.md).

## Privacy

A built skill holds statistics, short phrases and a few quoted sentences from your samples. Build it
outside your repositories (the builder uses `~/voice-skill-work`), don't commit it, and share the zip only
if you mean to. The `.gitignore` here excludes `voice-skill-work/`, `build/`, `dist/` and `*.skill`.

The optional `detector_check.py` runs a local detector (Binoculars) only to veto edits that made a
paragraph look more machine-written. Never paste an unpublished manuscript into an online detector.

## Repository layout

```
.claude-plugin/marketplace.json          makes the repo installable as a Claude Code plugin marketplace
plugins/voice-skill-builder/
  .claude-plugin/plugin.json
  skills/build-voice-skill/
    SKILL.md                             the builder workflow Claude follows
    references/                          interview, voice-notes guide, watchlist format
    scripts/                             find_slips, build_skill, validate_skill, package_skill, install_skill,
                                         publish_skill
    template/                            SKILL.md of a voice skill; setup block of a standalone build
  skills/revise-in-voice/
    SKILL.md                             the editing workflow every voice skill loads
    references/reviewer_prompt.md        the review lenses
    scripts/                             style_profile, voice_rules, ai_tell_lint, diff_guard, extractors
examples/demo-author/                    fictional samples, draft and build inputs
tests/                                   unittest suite (standard library only)
docs/design.md                           why it works this way, with sources
tools/make_release.py                    zips the whole plugin for claude.ai's Upload plugin
```
