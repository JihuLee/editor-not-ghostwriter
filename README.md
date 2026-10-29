# editor-not-ghostwriter

Turn samples of your own writing into a private Claude skill that revises your drafts and keeps them
sounding like you.

Asking an LLM to "polish" a paper usually means it rewrites the paper: the vocabulary, the dashes, the
tidy closing sentences and the even rhythm all change, and reviewers notice. Running the result through a
"humanizer" afterwards does not bring your voice back. This project takes the other route. The skill it
builds acts as a **copy editor and reviewer, never a ghostwriter**:

- it finds problems and makes the smallest edit that fixes each one;
- a guard script reverts any edit that adds AI-typical words or devices, adds sentences, or touches math,
  numbers, citations, theorem statements or code;
- every rule is judged against a **measured profile of your own writing**, so your habits are protected
  and only your recurring slips get fixed.

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

The builder needs nothing but Python 3.9+ and its standard library. Nothing leaves your machine except
what Claude itself reads.

## Quick start

### Claude Code

```
/plugin install voice-skill-builder --marketplace JihuLee/editor-not-ghostwriter
```

On Claude Code older than 2.1.275, add the marketplace first:
`/plugin marketplace add JihuLee/editor-not-ghostwriter`, then
`/plugin install voice-skill-builder@editor-not-ghostwriter`.

Then start the builder and point it at your writing:

```
/voice-skill-builder:build-voice-skill  ~/papers/2024-icml.tex ~/papers/2025-journal.tex ~/notes/blog/*.md
```

It interviews you briefly (skill name, which files you wrote yourself), measures your style, finds your
recurring slips, writes the voice notes, builds the skill, runs its self-tests and installs it in
`~/.claude/skills/<name>/`.

### claude.ai

1. Download `build-voice-skill.zip` from the
   [latest release](https://github.com/JihuLee/editor-not-ghostwriter/releases/latest)
   (or run `python tools/make_release.py`).
2. Upload it under **Customize > Skills** and turn it on. Code execution must be enabled.
3. In a chat, attach your papers and ask Claude to build your voice skill.
4. Claude hands back `<name>.zip`; upload it the same way.

### Scripts only

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

## Using your skill

```
/my-voice Section 3 only. Grammar and clarity, no content changes.
/my-voice Reviewer comments are in reviews/R2.md. Fix what is fixable in the text; list the rest.
/my-voice Just lint draft.tex and tell me which paragraphs read least like me. Don't edit.
```

You get `merged.tex` (your draft plus the accepted edits), `guard.md` (what was kept, what was reverted
and why), and a list of issues left for you: content problems, edits that needed you, and paragraphs the
lint suggests you rewrite yourself.

### What the guard does with an edit

| Reverted (FLAG) | Kept but listed for you (WARN) |
|---|---|
| touches math, numbers, citation keys, theorem statements, proofs, code, preamble | adds a tier-B word ("additionally", "comprehensive", ...) or an AI-favoured opener that you rarely use |
| adds a tier-A word ("delve", "pivotal", "seamless", ...) that you don't use yourself | splits or removes a sentence, changes a paragraph break |
| adds an em dash, contraction or "!" when your own samples have none | changes more than 20% of a paragraph's words |
| adds a sentence | flattens the paragraph's sentence rhythm, adds a summary-style closing sentence |

Each changed line group is judged on its own, so one bad line never takes a clean neighbouring fix with
it. `--strict` reverts the WARN edits too, for unattended runs. Words you use often are exempt
automatically; anything else you use on purpose can go in the build's `config.json` under `allow`.

## Try it on the demo author

`examples/demo-author/` holds three samples by a fictional author (invented papers about air-quality
sensors), a draft with two LLM-polished paragraphs, and the watchlist and voice notes a builder run
produced. The end-to-end test builds `demo-voice` from them:

```bash
python -m unittest discover -s tests -v
```

## Privacy

A built skill holds statistics, short phrases and a few quoted sentences from your samples. Build it
outside your repositories (the builder uses `~/voice-skill-work`), don't commit it, and share the zip only
if you mean to. The `.gitignore` here excludes `voice-skill-work/`, `build/`, `dist/` and `*.skill`.

The optional `detector_check.py` runs a local detector (Binoculars) only to veto edits that made a
paragraph look more machine-written. Never paste an unpublished manuscript into an online detector.

## Limits

- English only for now; see `docs/adding-a-language.md`.
- The tells are heuristics tuned to catch what an editing pass adds. A clean lint does not certify a text
  as human, and a flag does not prove LLM use.
- This is a tool for keeping **your** voice while you get editing help, not for passing off generated text
  as your own. Check your venue's policy on AI assistance; the built skill marks any passage Claude drafts
  so you can rewrite or disclose it.

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

## License

MIT
