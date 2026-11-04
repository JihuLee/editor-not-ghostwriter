#!/usr/bin/env python3
"""One entry point for every supported input format.

  .tex .ltx .latex           LaTeX            samples and drafts
  .md .markdown .txt .text   Markdown / text  samples and drafts
  .docx                      Word             samples only

`config` is the "config" block of an author profile:
  {"latex": {"frozen_envs_extra": ["thmx"], "unfrozen_envs": ["proof"], "macros": {"method": "FooNet"}}}

Sample arguments may be folders: collect_sources() expands them into the supported files inside.
"""
from __future__ import annotations

import os
from pathlib import Path

import docxprose
import mdprose
import texprose

FORMATS = {".tex": "tex", ".ltx": "tex", ".latex": "tex",
           ".md": "md", ".markdown": "md", ".txt": "md", ".text": "md",
           ".docx": "docx"}
DRAFT_FORMATS = {"tex", "md"}
SKIP_DIRS = {"__pycache__", "node_modules"}


def _skipped(rel: Path) -> bool:
    """Hidden files and folders, tool folders, and Word lock files (~$name.docx)."""
    return any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts) or rel.name.startswith("~$")


def collect_sources(paths) -> list:
    """Expand folders into the supported files inside them (recursively, sorted); keep files as given.

    A file named explicitly is kept whatever its type, so extract() still reports an unsupported one.
    The same file reached twice is read once.
    """
    out, seen = [], set()
    for p in map(Path, paths):
        if p.is_dir():
            found = sorted(f for f in p.rglob("*")
                           if f.suffix.lower() in FORMATS and f.is_file() and not _skipped(f.relative_to(p)))
            if not found:
                raise SystemExit(f"no {' '.join(sorted(FORMATS))} files in folder {p}")
        else:
            found = [p]
        for f in found:
            key = f.resolve()
            if key not in seen:
                seen.add(key)
                out.append(f)
    return out


def source_labels(paths) -> dict:
    """Short display names: the file name, or the path below the common folder when names repeat."""
    paths = [Path(p) for p in paths]
    names = [p.name for p in paths]
    if len(set(names)) == len(names):
        return dict(zip(paths, names))
    full = [p.resolve() for p in paths]
    try:
        common = Path(os.path.commonpath([str(f.parent) for f in full]))
    except ValueError:                                  # different drives on Windows
        return {p: f.as_posix() for p, f in zip(paths, full)}
    return {p: f.relative_to(common).as_posix() for p, f in zip(paths, full)}


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
