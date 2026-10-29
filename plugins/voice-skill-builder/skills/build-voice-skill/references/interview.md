# Interview

Ask these in one round (one AskUserQuestion call when that tool exists; otherwise one short message).
Offer the default first. Skip any question the conversation already answered.

1. **Samples.** "Which files did you write yourself? Leave out sections a co-author wrote and anything you
   polished with an AI tool, since the samples become the baseline your future drafts are compared with."
   - Default: the files the user already shared, all treated as self-written.
   - If a file is co-authored, ask which sections are theirs and keep only those (copy them into a new
     file in `WORK/samples/`).

2. **Skill name and label.** "What should the skill be called, and how should its notes refer to you?"
   - Default name: the user's first name plus `-voice` (`alex-voice`) when you know it, otherwise
     `my-voice`. A personal name keeps the skill's description distinct from other writing skills.
     Lowercase letters, digits and hyphens; at most 64 characters; no "claude" or "anthropic".
   - Default label: the user's first name when you know it, otherwise "the author".

3. **Theorem-like text.** Only ask if the samples are LaTeX with theorem environments or proofs.
   "Should the editor leave theorem statements and proofs alone (safer), or may it fix grammar in proofs?"
   - Default: leave them alone. If the user wants proofs editable, put `"proof"` in
     `latex.unfrozen_envs` in `config.json`. Theorem statements stay frozen either way.

4. **Where to install.** "Where will you use the skill?"
   - Default in Claude Code: the personal skills folder (`~/.claude/skills/`); in Codex:
     `~/.agents/skills/`.
   - Other options: this project's `.claude/skills/` or `.agents/skills/` (do not commit it if the
     repository is public), or a .zip for claude.ai.
