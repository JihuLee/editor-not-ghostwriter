#!/usr/bin/env python3
"""One entry point for every supported input format.

  .tex .ltx .latex           LaTeX            samples and drafts
  .md .markdown .txt .text   Markdown / text  samples and drafts
  .docx                      Word             samples only

`config` is the "config" block of an author profile:
  {"latex": {"frozen_envs_extra": ["thmx"], "unfrozen_envs": ["proof"], "macros": {"method": "FooNet"}}}
"""
from __future__ import annotations

from pathlib import Path

import docxprose
import mdprose
import texprose

FORMATS = {".tex": "tex", ".ltx": "tex", ".latex": "tex",
           ".md": "md", ".markdown": "md", ".txt": "md", ".text": "md",
           ".docx": "docx"}
DRAFT_FORMATS = {"tex", "md"}


def detect_format(path) -> str:
    fmt = FORMATS.get(Path(path).suffix.lower())
    if not fmt:
        raise ValueError(f"unsupported file type: {path} (supported: {', '.join(sorted(FORMATS))})")
    return fmt


def _latex_opts(config):
    lx = (config or {}).get("latex", {}) if isinstance(config, dict) else {}
    return {"frozen_extra": lx.get("frozen_envs_extra", ()), "unfrozen": lx.get("unfrozen_envs", ()),
            "macros_extra": lx.get("macros", {})}


def extract(path, fmt=None, config=None, min_words: int = 3):
    fmt = fmt or detect_format(path)
    if fmt == "tex":
        return texprose.extract(Path(path), min_words=min_words, **_latex_opts(config))
    if fmt == "md":
        return mdprose.extract(Path(path), min_words=min_words)
    if fmt == "docx":
        return docxprose.extract(Path(path), min_words=min_words)
    raise ValueError(f"unknown format {fmt}")


def extract_text(text: str, fmt: str, config=None, min_words: int = 3):
    """Like extract() but for a string already in memory (tex or md only)."""
    if fmt == "tex":
        return texprose.extract(text if "\n" in text else text + "\n", min_words=min_words, **_latex_opts(config))
    if fmt == "md":
        return mdprose.extract(text if "\n" in text else text + "\n", min_words=min_words)
    raise ValueError(f"cannot extract {fmt} from a string")


def fragment_prose(raw: str, fmt: str) -> str:
    return texprose.fragment_prose(raw) if fmt == "tex" else mdprose.fragment_prose(raw)
