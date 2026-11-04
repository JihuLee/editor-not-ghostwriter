# editor-not-ghostwriter

**Let Claude edit your paper without making it sound like Claude.**

[![tests](https://github.com/JihuLee/editor-not-ghostwriter/actions/workflows/tests.yml/badge.svg)](https://github.com/JihuLee/editor-not-ghostwriter/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/JihuLee/editor-not-ghostwriter)](https://github.com/JihuLee/editor-not-ghostwriter/releases/latest)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Ask an LLM to polish a draft and you get back someone else's paper: "delve", "pivotal", em dashes, a tidy
summary sentence at the end of every paragraph. Reviewers notice, and a "humanizer" pass afterwards does
not bring your voice back.

This project takes the other route. Give it a few things you wrote yourself, and it builds a **private
skill that edits like a copy editor, never a ghostwriter**, for Claude Code, claude.ai or Codex. It makes
the smallest change that fixes each problem, and a guard script throws out any edit that doesn't sound
like you.

## What it looks like

Five edits proposed on a draft by the [demo author](examples/demo-author/). The guard keeps two and
reverts three:

```diff
@@ KEPT: fixes this author's recurring slips @@
- Batching the uploads allows to save most of that energy
+ Batching the uploads allows the sensor to save most of that energy
- The scheduler sends less samples per upload
+ The scheduler sends fewer samples per upload

@@ REVERTED: "Crucially" is a stock LLM opener (this author writes "We stress that") @@
- We stress that this rule needs no knowledge
+ Crucially, this rule needs no knowledge

@@ REVERTED: a copy editor does not change results @@
- Battery life went from 21 to 47 days
+ Battery life went from 21 to 48 days

@@ REVERTED: "novel" and "seamless" are not this author's words @@
- We presented a scheduler that batches uploads
+ We presented a novel scheduler that seamlessly batches uploads
```

Before any editing starts, the lint already ranks the two paragraphs an LLM "polished" as the ones that
read least like the author.

## Why it works

- **It edits, it doesn't rewrite.** A word, then a phrase, then a clause; one sentence in, one sentence
  out. Every word Claude doesn't write is a word that can't sound like Claude.
- **Your writing is the baseline.** It measures your sentence rhythm, punctuation, connectives and
  function words. If you really do write "intricate" or use em dashes, they stay. Only your own recurring
  slips get fixed.
- **Content is frozen.** Math, numbers, citations, theorem statements, proofs and code are off limits.
- **Reviewers start fresh.** Three independent reviews look for problems without being told what was
  fixed, so earlier rounds can't inflate their verdict.

The reasoning and sources are in [docs/design.md](docs/design.md).

## Quick start

You need about 3,000 words or more of your own writing (`.tex`, `.md`, `.txt` or `.docx`) and Python 3.9+.

**1. Install the builder** (the installer needs Node.js 22.20+)

```bash
npx skills add JihuLee/editor-not-ghostwriter -g
```

Choose Claude Code, Codex or both when it asks which agents to install to.

**2. Point it at your writing**

```
/build-voice-skill  ~/papers/2024-icml.tex ~/papers/2025-journal.tex ~/notes/blog/*.md
```

In Codex, type `$build-voice-skill` with the same paths, or just ask it to build your voice skill from
those files. It asks a few questions, measures your style, finds your recurring slips, builds the skill,
tests it on your own text and installs it next to the builder (`~/.claude/skills/<name>/` or
`~/.agents/skills/<name>/`).

### claude.ai

1. Download `build-voice-skill.zip` from the
   [latest release](https://github.com/JihuLee/editor-not-ghostwriter/releases/latest).
2. Upload it under **Customize > Skills** and turn it on. Code execution must be enabled.
3. In a chat, attach your papers and ask Claude to build your voice skill.
4. Claude hands back `<name>.zip`; upload it the same way.

<details>
<summary><b>Other ways to install</b>: Claude Code or Codex plugin, plain scripts</summary>

**Claude Code plugin**

```
/plugin install voice-skill-builder --marketplace JihuLee/editor-not-ghostwriter
```

Then start it with `/voice-skill-builder:build-voice-skill` followed by your files. On Claude Code older
than 2.1.275, run `/plugin marketplace add JihuLee/editor-not-ghostwriter` first, then
`/plugin install voice-skill-builder@editor-not-ghostwriter`.

**Codex plugin**

```
codex plugin marketplace add JihuLee/editor-not-ghostwriter
```

```
codex plugin add voice-skill-builder@editor-not-ghostwriter
```

**Plain scripts, no agent**: see [docs/usage.md](docs/usage.md#scripts-only).

</details>

## Using your skill

```
/my-voice Section 3 only. Grammar and clarity, no content changes.
/my-voice Reviewer comments are in reviews/R2.md. Fix what is fixable in the text; list the rest.
/my-voice Just lint draft.tex and tell me which paragraphs read least like me. Don't edit.
```

In Codex, start with `$my-voice` instead. You get `merged.tex` (your draft plus the accepted edits),
`guard.md` (what was kept, what was reverted and why), and a short list of what is left for you.

## Good to know

- **Private by default.** Nothing leaves your machine except what Claude itself reads. The built skill
  quotes a few sentences from your samples, so keep it out of your repositories.
  [More on privacy](docs/usage.md#privacy).
- **English only** for now; see [docs/adding-a-language.md](docs/adding-a-language.md).
- **Heuristics, not proof.** A clean lint does not certify a text as human, and a flag does not prove LLM
  use.
- **Your voice, your work.** This is for getting editing help without losing your voice, not for passing
  off generated text as your own. Check your venue's policy on AI assistance; the skill marks any passage
  Claude drafts so you can rewrite or disclose it.

## More

- [docs/usage.md](docs/usage.md): how the pieces fit, the full guard rules, the demo author, repository
  layout
- [docs/design.md](docs/design.md): why it works this way, with sources
- [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
