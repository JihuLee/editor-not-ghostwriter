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
build_skill.py ──► <name>/  (your private skill)  ──► validate_skill.py (self-tests on your own text)
                                                   ──► install_skill.py (Claude Code) / package_skill.py (claude.ai)

Using <name> on a draft:
  lint (AI tells, your slips, drift from your baseline)
  → three independent reviews that find but do not fix
  → minimal edits
  → diff_guard.py keeps clean edits, reverts the rest, lists the doubtful ones
  → merged draft + change report
```

The builder needs nothing but Python 3.9+ and its standard library. The scripts refuse fewer than 3,000
words of prose; 8,000 words or more gives steadier numbers.

## Scripts only

```bash
git clone https://github.com/JihuLee/editor-not-ghostwriter && cd editor-not-ghostwriter
ENGINE=plugins/voice-skill-builder/skills/build-voice-skill/template/scripts
BUILDER=plugins/voice-skill-builder/skills/build-voice-skill/scripts
WORK=~/voice-skill-work

python3 $ENGINE/style_profile.py ~/papers/*.tex -o $WORK/profile.json --md $WORK/stats.md --check
python3 $BUILDER/find_slips.py ~/papers/*.tex -o $WORK/slip_candidates.md
# write $WORK/watchlist.json and $WORK/voice_notes.md (formats in the skill's references/ folder)
python3 $BUILDER/build_skill.py --name my-voice --profile $WORK/profile.json \
    --notes $WORK/voice_notes.md --watchlist $WORK/watchlist.json --out $WORK/build/my-voice
python3 $BUILDER/validate_skill.py $WORK/build/my-voice --samples ~/papers/*.tex
python3 $BUILDER/install_skill.py $WORK/build/my-voice
```

The voice notes are the one step that needs reading rather than counting; without Claude, write them
yourself or build with `--allow-missing-notes`.

## What the guard does with an edit

| Reverted (FLAG) | Kept but listed for you (WARN) |
|---|---|
| touches math, numbers, citation keys, theorem statements, proofs, code, preamble | adds a tier-B word ("additionally", "comprehensive", ...) or an AI-favoured opener that you rarely use |
| adds a tier-A word ("delve", "pivotal", "seamless", ...) that you don't use yourself | splits or removes a sentence, changes a paragraph break |
| adds an em dash, contraction or "!" when your own samples have none | changes more than 20% of a paragraph's words |
| adds a sentence | flattens the paragraph's sentence rhythm, adds a summary-style closing sentence |

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
    scripts/                             find_slips, build_skill, validate_skill, package_skill, install_skill
    template/                            the skill that gets built: SKILL.md.tmpl, references/, scripts/
examples/demo-author/                    fictional samples, draft and build inputs
tests/                                   unittest suite (standard library only)
docs/design.md                           why it works this way, with sources
tools/make_release.py                    zips the builder for claude.ai
```
