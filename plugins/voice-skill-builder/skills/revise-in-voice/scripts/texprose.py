#!/usr/bin/env python3
"""Extract prose from LaTeX source while keeping source line numbers.

What counts as prose: body text, abstract, list items, footnotes (as separate
paragraphs). What is removed: display math (replaced by the token MATH so the
sentence still parses), inline math (MATH), floats (figures, tables, algorithms),
theorem-like statements and proofs (they are frozen during revision), bibliography,
acknowledgments and biographies. Citations are dropped, \\citet becomes "Author",
cross-references become "REF".

Theorem-like environments declared with \\newtheorem, \\declaretheorem and friends
are detected automatically. Simple zero-argument macros (\\newcommand{\\sys}{Foo})
are expanded so sentences keep their words. Standard library only.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from textcore import (APPXMARK, KIND_PRIORITY, PARBREAK, SENT, SENT_RE, Doc, artifact_sentences,
                      build_paragraphs, sentinel)

DISPLAY_MATH_ENVS = {
    "equation", "align", "alignat", "aligned", "gather", "gathered", "multline",
    "flalign", "eqnarray", "displaymath", "math", "split", "dmath", "subequations",
}
DEFAULT_FROZEN_ENVS = {
    "theorem", "lemma", "proposition", "corollary", "definition", "assumption",
    "conjecture", "claim", "proof", "axiom", "hypothesis", "condition", "fact",
    "thm", "lem", "prop", "cor", "corr", "defn", "dfn", "defi", "conj", "assump",
    "asm", "hyp", "IEEEproof", "proofsketch",
}
FLOAT_ENVS = {
    "figure", "table", "algorithm", "algorithmic", "algorithm2e", "tabular", "tabularx",
    "tabulary", "longtable", "wrapfigure", "wraptable", "subfigure", "subtable",
    "minipage", "tikzpicture", "lstlisting", "verbatim", "minted", "comment",
    "thebibliography", "IEEEbiography", "IEEEbiographynophoto", "IEEEkeywords",
    "keywords", "CCSXML", "center", "filecontents", "titlepage", "framed", "tcolorbox",
    "Verbatim", "alltt", "pgfpicture", "forest",
}
APPENDIX_ENVS = {"appendices"}

SECTION_RE = re.compile(r"\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?(?![A-Za-z])")
EXCLUDED_SECTION_RE = re.compile(r"acknowledg|funding|biograph|author contributions?|declaration of|"
                                 r"competing interests?|conflicts? of interest", re.I)
_BEGIN_END_RE = re.compile(r"\\(begin|end)\s*\{([^}]*)\}")
_THEOREM_DECL_RES = [
    re.compile(r"\\(?:newtheorem|spnewtheorem|newmdtheoremenv|newtcbtheorem)\*?\s*\{([A-Za-z@]+)\}"),
    re.compile(r"\\declaretheorem\*?\s*(?:\[[^\]]*\]\s*)?\{([A-Za-z@,\s]+)\}"),
]
_MACRO_DEF_RES = [
    re.compile(r"\\(?:re)?newcommand\*?\s*\{?\s*\\([A-Za-z]+)\s*\}?\s*(?=\{)"),
    re.compile(r"\\providecommand\*?\s*\{?\s*\\([A-Za-z]+)\s*\}?\s*(?=\{)"),
    re.compile(r"\\DeclareRobustCommand\*?\s*\{?\s*\\([A-Za-z]+)\s*\}?\s*(?=\{)"),
    re.compile(r"\\def\s*\\([A-Za-z]+)\s*(?=\{)"),
]
BUILTIN_MACROS = {"eg": "e.g.", "ie": "i.e.", "etal": "et al.", "wrt": "w.r.t.", "etc": "etc.",
                  "vs": "vs.", "cf": "cf.", "iid": "i.i.d.", "aka": "a.k.a."}
_PROTECTED_MACROS = {"cite", "ref", "label", "section", "begin", "end", "item", "emph", "textbf",
                     "textit", "footnote", "caption", "url", "href", "input", "include"}


# --------------------------------------------------------------------------- helpers


def strip_comment(line: str) -> str:
    """Remove a LaTeX comment (unescaped %) from one source line."""
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            return line[:i]
        i += 1
    return line


def _skip_bracket(s: str, i: int) -> int:
    """s[i] == '['. Return index just after the matching ']'."""
    depth, j, n = 0, i + 1, len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "]" and depth <= 0:
            return j + 1
        j += 1
    return n


def read_group(s: str, i: int):
    """s[i] == '{'. Return (content, index after the matching '}')."""
    depth, j, n = 0, i, len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], n


def declared_theorem_envs(text: str) -> set:
    found = set()
    for rx in _THEOREM_DECL_RES:
        for m in rx.finditer(text):
            for name in m.group(1).split(","):
                if name.strip():
                    found.add(name.strip())
    return found


def simple_macros(text: str) -> dict:
    """Zero-argument text macros defined in the file, e.g. \\newcommand{\\sys}{\\textsc{Foo}\\xspace}."""
    out = {}
    clean = "\n".join(strip_comment(l) for l in text.split("\n"))
    for rx in _MACRO_DEF_RES:
        for m in rx.finditer(clean):
            name = m.group(1)
            j = m.end()
            if j >= len(clean) or clean[j] != "{" or name in _PROTECTED_MACROS:
                continue
            body, _ = read_group(clean, j)
            if "#" in body or "\n" in body or len(body) > 80 or "\\begin" in body or "newcommand" in body:
                continue
            out[name] = body
    return out


def _expander(macros: dict):
    if not macros:
        return lambda s: s
    names = sorted(macros, key=len, reverse=True)
    rx = re.compile(r"\\(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z@])")

    def expand(s: str) -> str:
        for _ in range(2):                           # one level of nesting
            new = rx.sub(lambda m: macros[m.group(1)], s)
            if new == s:
                break
            s = new
        return s
    return expand


# --------------------------------------------------------------------------- scanner


def _env_kind(name: str, frozen: set) -> str:
    base = name.rstrip("*")
    if base in DISPLAY_MATH_ENVS:
        return "math"
    if base in frozen or name in frozen:
        return "frozen"
    if base in FLOAT_ENVS:
        return "float"
    if base in APPENDIX_ENVS:
        return "appendix"
    return "prose"


def _scan(body: str, frozen: set):
    """Character-level pass: drop math/floats/frozen blocks, keep line sentinels."""
    out = []
    kinds = {}
    cur = 0
    i, n = 0, len(body)
    math = None          # '$', '$$', '\\(', '\\['
    math_start = 0
    skip = []            # stack of [env_name, depth, kind, start]
    skip_section = False
    iffalse = False

    def mark(k):
        kinds.setdefault(cur, set()).add(k)

    def brk(extra=""):
        out.append(PARBREAK + extra + sentinel(cur))

    def close_punct(content):
        """Sentence punctuation typed inside math ($x.$) is moved outside."""
        t = SENT_RE.sub("", content)
        t = re.sub(r"(\\[,;:! ]|\\q?quad|\s)+$", "", t)
        return t[-1] if t and t[-1] in ".,;:" else ""

    while i < n:
        c = body[i]
        if c == SENT:
            j = body.index(SENT, i + 1)
            cur = int(body[i + 1:j])
            out.append(body[i:j + 1])
            i = j + 1
            if math in ("$$", "\\["):
                mark("math")
            elif skip:
                mark(skip[-1][2])
            elif skip_section or iffalse:
                mark("excluded")
            else:
                mark("prose")
            continue
        if c == PARBREAK:
            out.append(PARBREAK)
            i += 1
            continue
        if math:
            if c == "\\":
                if (math == "\\(" and body.startswith("\\)", i)) or (math == "\\[" and body.startswith("\\]", i)):
                    out.append(close_punct(body[math_start:i]))
                    math = None
                i += 2
                continue
            if c == "$":
                if math == "$$" and body.startswith("$$", i):
                    out.append(close_punct(body[math_start:i]))
                    math = None
                    i += 2
                    continue
                if math == "$":
                    out.append(close_punct(body[math_start:i]))
                    math = None
            i += 1
            continue
        if iffalse:
            if body.startswith("\\fi", i) and not body[i + 3:i + 4].isalpha():
                iffalse = False
                i += 3
                continue
            i += 1
            continue
        if skip:
            m = _BEGIN_END_RE.match(body, i)
            if m:
                name = m.group(2).strip()
                if name == skip[-1][0]:
                    if m.group(1) == "begin":
                        skip[-1][1] += 1
                    else:
                        skip[-1][1] -= 1
                        if skip[-1][1] == 0:
                            _, _, kind, start = skip.pop()
                            if kind == "math":
                                out.append(close_punct(body[start:i]))
                            else:
                                brk()
                i = m.end()
                continue
            i += 2 if c == "\\" else 1
            continue
        if skip_section:
            if c == "\\" and (SECTION_RE.match(body, i) or body.startswith("\\appendi", i)
                              or body.startswith("\\begin{appendices}", i)):
                skip_section = False          # handled by the normal branch below
            else:
                i += 1
                continue

        # ---------------- normal prose mode
        if c == "\\":
            m = _BEGIN_END_RE.match(body, i)
            if m:
                name = m.group(2).strip()
                kind = _env_kind(name, frozen)
                i = m.end()
                if m.group(1) == "begin":
                    if name == "document":
                        continue
                    if kind == "math":
                        out.append(" MATH ")
                        skip.append([name, 1, "math", i])
                        mark("math")
                    elif kind in ("frozen", "float"):
                        brk()
                        skip.append([name, 1, kind, i])
                        mark(kind)
                    elif kind == "appendix":
                        brk(APPXMARK)
                    else:
                        brk()
                        while i < n and body[i] in " \t":
                            i += 1
                        if i < n and body[i] == "[":          # \begin{itemize}[topsep=0pt]
                            i = _skip_bracket(body, i)
                elif name != "document":
                    brk()
                continue
            ms = SECTION_RE.match(body, i)
            if ms:
                j = ms.end()
                while j < n and body[j] in " \t":
                    j += 1
                if j < n and body[j] == "[":
                    j = _skip_bracket(body, j)
                while j < n and body[j] in " \t":
                    j += 1
                title = ""
                if j < n and body[j] == "{":
                    title, j = read_group(body, j)
                mark("heading")
                for ln in SENT_RE.findall(title):      # keep line sentinels of multi-line titles
                    cur = int(ln)
                brk()
                skip_section = bool(EXCLUDED_SECTION_RE.search(SENT_RE.sub("", title)))
                i = j
                continue
            if body.startswith("\\appendices", i):
                brk(APPXMARK)
                i += len("\\appendices")
                continue
            if body.startswith("\\appendix", i) and not body[i + 9:i + 10].isalpha():
                brk(APPXMARK)
                i += len("\\appendix")
                continue
            if body.startswith("\\iffalse", i) and not body[i + 8:i + 9].isalpha():
                iffalse = True
                i += 8
                continue
            if re.match(r"\\(bibliography|printbibliography)(?![A-Za-z])", body[i:i + 20]):
                skip_section = True
                brk()
                i += 1
                continue
            if body.startswith("\\item", i) and not body[i + 5:i + 6].isalpha():
                j = i + 5
                while j < n and body[j] in " \t":
                    j += 1
                if j < n and body[j] == "[":
                    j = _skip_bracket(body, j)
                brk()
                i = j
                continue
            if body.startswith("\\[", i):
                out.append(" MATH ")
                math = "\\["
                mark("math")
                i += 2
                math_start = i
                continue
            if body.startswith("\\(", i):
                out.append(" MATH ")
                math = "\\("
                i += 2
                math_start = i
                continue
            out.append(body[i:i + 2])        # keeps \$ \% etc. away from the math detector
            i += 2
            continue
        if c == "$":
            if body.startswith("$$", i):
                out.append(" MATH ")
                math = "$$"
                mark("math")
                i += 2
                math_start = i
                continue
            out.append(" MATH ")
            math = "$"
            i += 1
            math_start = i
            continue
        out.append(c)
        i += 1
    return "".join(out), kinds


# --------------------------------------------------------------------------- command cleanup

REPLACE_CMDS = {
    "citet": "Author", "Citet": "Author", "citeauthor": "Author", "Citeauthor": "Author",
    "textcite": "Author", "Textcite": "Author",
    "cref": "REF", "Cref": "REF", "ref": "REF", "eqref": "REF", "autoref": "REF", "Autoref": "REF",
    "pageref": "REF", "nameref": "REF", "vref": "REF", "Vref": "REF", "cpageref": "REF", "url": "URL",
}
DROP_CMDS = {
    "cite": 1, "citep": 1, "citealp": 1, "citealt": 1, "citeyear": 1, "citeyearpar": 1,
    "parencite": 1, "Parencite": 1, "autocite": 1, "Autocite": 1, "footcite": 1, "supercite": 1,
    "smartcite": 1, "nocite": 1, "label": 1, "thanks": 1, "vspace": 1, "hspace": 1,
    "includegraphics": 1, "includesvg": 1, "input": 1, "include": 1,
    "bibliography": 1, "bibliographystyle": 1, "addbibresource": 1, "title": 1, "author": 1, "date": 1,
    "markboth": 2, "marginpar": 1, "marginnote": 1, "todo": 1, "graphicspath": 1, "hypersetup": 1,
    "setlength": 2, "addtolength": 2, "newcommand": 2, "renewcommand": 2, "providecommand": 2,
    "caption": 1, "hyphenation": 1, "color": 1, "pagestyle": 1, "thispagestyle": 1, "setcounter": 2,
    "addcontentsline": 3, "subfloat": 1, "index": 1, "newtheorem": 2, "usepackage": 1,
}
KEEP_LAST = {"textcolor": 2, "href": 2, "texorpdfstring": 2, "colorbox": 2, "hyperref": 1}
JOIN_ARGS = {"IEEEPARstart": 2}
DIM_CMDS = {"vskip", "hskip", "kern", "vspace*", "hspace*"}
FOOTNOTE_CMDS = {"footnote", "footnotetext"}
_DIM_RE = re.compile(r"\s*-?\s*[\d.]+\s*(?:in|pt|cm|mm|em|ex|bp|pc|sp)\b"
                     r"(?:\s*(?:plus|minus)\s*-?[\d.]+\s*(?:in|pt|cm|mm|em|ex|fil+))*")
_ACCENTS = set("'`^\"~=.")
_FORMATTING = {"textbf", "textit", "texttt", "textsc", "textrm", "textsf", "textup", "textmd", "textsl",
               "textnormal", "emph", "underline", "mbox", "hbox", "fbox", "text", "uline", "sout", "st", "hl",
               "MakeUppercase", "MakeLowercase", "uppercase", "lowercase", "ac", "acs", "acl", "acf", "acp",
               "gls", "Gls", "glspl", "Glspl", "acrshort", "acrlong", "acrfull", "textsuperscript",
               "textsubscript", "enquote", "mathrm", "mathbf", "operatorname", "ensuremath"}
_QUIET = _FORMATTING | {"xspace", "noindent", "centering", "maketitle", "newline", "linebreak", "par", "smallskip",
          "medskip", "bigskip", "clearpage", "newpage", "raggedright", "onecolumn", "twocolumn",
          "hfill", "vfill", "protect", "relax", "null", "displaystyle", "small", "footnotesize",
          "large", "Large", "normalsize", "tiny", "scriptsize", "bfseries", "itshape", "ttfamily",
          "em", "it", "bf", "tt", "sc", "rm", "today", "LaTeX", "TeX", "ldots", "dots", "cdots"}


def clean_commands(s: str, footnotes=None, stats=None) -> str:
    """Brace-aware removal/unwrapping of LaTeX commands. Keeps line sentinels.

    footnotes: a list collects raw footnote bodies (the caller turns them into separate
    paragraphs); None keeps footnote text inline, so fragment checks still see it.
    stats: a dict whose "unknown" Counter records command names that were unwrapped blindly.
    """
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 >= n:
                i += 1
                continue
            nxt = s[i + 1]
            if not nxt.isalpha() and nxt != "@":
                if nxt in _ACCENTS and i + 2 < n:
                    j = i + 2
                    if s[j] == "{":
                        inner, j = read_group(s, j)
                        out.append(inner)
                    else:
                        out.append(s[j])
                        j += 1
                    i = j
                    continue
                mapping = {"%": "%", "&": "&", "$": "$", "_": "_", "#": "#", "-": "",
                           "{": "", "}": "", "\\": " ", ",": " ", ";": " ", ":": " ",
                           "!": "", " ": " ", "\n": " ", "/": ""}
                out.append(mapping.get(nxt, ""))
                i += 2
                continue
            m = re.match(r"[A-Za-z@]+\*?", s[i + 1:])
            name = m.group(0)
            j = i + 1 + len(name)
            if name in DIM_CMDS or name.rstrip("*") in DIM_CMDS:
                md = _DIM_RE.match(s, j)
                if md:
                    j = md.end()
                i = j
                continue
            if name == "verb" and j < n:
                k = s.find(s[j], j + 1)
                out.append(" CODE ")
                i = (k + 1) if k > 0 else n
                continue

            got_sent = []

            def args(j, k):
                """Read up to k brace groups (optional [..] args allowed in between)."""
                got = []
                while len(got) < k:
                    jj = j
                    while jj < n and (s[jj] in " \t\n" or s[jj] == SENT):
                        if s[jj] == SENT:
                            e = s.index(SENT, jj + 1)
                            got_sent.append(s[jj:e + 1])
                            jj = e + 1
                        else:
                            jj += 1
                    if jj < n and s[jj] == "[":
                        j = _skip_bracket(s, jj)
                        continue
                    if jj < n and s[jj] == "{":
                        g, j = read_group(s, jj)
                        got.append(g)
                    else:
                        break
                return got, j

            base = name.rstrip("*")
            if base in FOOTNOTE_CMDS:
                got, j = args(j, 1)
                for g in got:
                    if footnotes is None:
                        out.append(" " + clean_commands(g, None, stats) + " ")
                    else:
                        prev = SENT_RE.findall(s, 0, i)          # line the footnote starts on
                        footnotes.append((sentinel(int(prev[-1])) if prev else "") + g)
                        out.extend(sentinel(int(x)) for x in SENT_RE.findall(g))
            elif base in REPLACE_CMDS:
                _, j = args(j, 1)
                out.append(" " + REPLACE_CMDS[base] + " ")
            elif base in DROP_CMDS:
                got, j = args(j, DROP_CMDS[base])
                for g in got:                    # keep sentinels from dropped groups
                    out.extend(sentinel(int(x)) for x in SENT_RE.findall(g))
            elif base in KEEP_LAST:
                got, j = args(j, KEEP_LAST[base])
                if got:
                    out.append(clean_commands(got[-1], footnotes, stats))
            elif base in JOIN_ARGS:
                got, j = args(j, JOIN_ARGS[base])
                out.append("".join(clean_commands(g, footnotes, stats) for g in got))
            else:
                # unknown command: drop its name, keep the content of directly attached groups
                if stats is not None and base not in _QUIET:
                    stats.setdefault("unknown", Counter())[base] += 1
                k = j
                while k < n and s[k] == "{":
                    g, k = read_group(s, k)
                    out.append(clean_commands(g, footnotes, stats))
                j = k
            out.extend(got_sent)
            i = j
            continue
        if c in "{}":
            i += 1
            continue
        if c == "~":
            out.append(" ")
            i += 1
            continue
        out.append(c)
        i += 1
    t = "".join(out)
    t = t.replace("---", "\u2014").replace("--", "\u2013")
    t = t.replace("``", '"').replace("''", '"').replace("`", "'")
    t = re.sub(r"MATH\s+-(?=[A-Za-z])", "MATH-", t)          # $K$-means -> MATH-means
    return t


# --------------------------------------------------------------------------- public API

_INLINE_MATH_RE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$", re.S)


def fragment_prose(raw: str) -> str:
    """Clean prose for a LaTeX fragment (e.g. one diff hunk) that may not be balanced."""
    t = " ".join(strip_comment(l) for l in raw.split("\n"))
    t = re.sub(r"\\begin\{(equation|align|gather|multline|eqnarray|displaymath)(\*?)\}.*?\\end\{\1\2\}",
               " MATH ", t, flags=re.S)
    t = re.sub(r"\$\$.*?\$\$", " MATH ", t, flags=re.S)
    t = re.sub(r"\\\[.*?\\\]", " MATH ", t, flags=re.S)

    def inl(m):
        c = re.sub(r"(\\[,;:! ]|\s)+$", "", m.group(1))
        return " MATH" + (c[-1] if c and c[-1] in ".,;:" else "") + " "

    t = _INLINE_MATH_RE.sub(inl, t)
    t = re.sub(r"(?<!\\)\$", " ", t)                    # unbalanced leftovers
    t = re.sub(r"\\(begin|end)\s*\{[^}]*\}(\[[^\]]*\])?", " ", t)
    t = re.sub(r"\\item(\[[^\]]*\])?", " ", t)
    t = clean_commands(t)
    t = re.sub(r"\s+([.,;:!?)])", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def extract(source, min_words: int = 3, frozen_extra=(), unfrozen=(), macros_extra=None) -> Doc:
    """source: path or LaTeX string. Returns a Doc with paragraphs, line kinds and diagnostics."""
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).exists()):
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    else:
        text = source
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    declared = declared_theorem_envs(text)
    frozen = (DEFAULT_FROZEN_ENVS | declared | set(frozen_extra)) - set(unfrozen)
    macros = dict(BUILTIN_MACROS)
    user_macros = simple_macros(text)
    macros.update(user_macros)
    macros.update(macros_extra or {})
    expand = _expander(macros)

    start, end = 0, len(lines)
    for k, ln in enumerate(lines):
        if re.search(r"\\begin\s*\{document\}", strip_comment(ln)):
            start = k + 1
            break
    for k in range(len(lines) - 1, -1, -1):
        if re.search(r"\\end\s*\{document\}", strip_comment(lines[k])):
            end = k
            break
    parts = []
    for k in range(start, end):
        raw = lines[k]
        if raw.strip() == "":
            parts.append(PARBREAK + "\n")
            continue
        parts.append(f"{sentinel(k + 1)}{expand(strip_comment(raw))}\n")
    scanned, kinds = _scan("".join(parts), frozen)

    line_kind = {}
    for k in range(len(lines)):
        ln = k + 1
        if k < start or k >= end:
            line_kind[ln] = "preamble"
        elif lines[k].strip() == "":
            line_kind[ln] = "blank"
        else:
            ks = kinds.get(ln, {"prose"})
            line_kind[ln] = next(p for p in KIND_PRIORITY if p in ks or p == "prose")

    stats = {}
    chunks = []
    for chunk in scanned.split(PARBREAK):
        notes = []
        chunks.append((clean_commands(chunk, footnotes=notes, stats=stats), False))
        for raw_note in notes:
            chunks.append((clean_commands(raw_note, stats=stats), True))
    doc = Doc(paragraphs=build_paragraphs(chunks, min_words=min_words), line_kind=line_kind,
              n_lines=len(lines), fmt="tex", layout_meaningful=True)
    doc.diagnostics = {
        "theorem_envs_declared": sorted(declared),
        "frozen_envs": sorted(frozen),
        "macros_expanded": sorted(user_macros),
        "unknown_commands": dict(stats.get("unknown", Counter()).most_common(15)),
        "artifacts": artifact_sentences(doc),
    }
    return doc


if __name__ == "__main__":       # quick inspection: python texprose.py paper.tex
    import sys
    d = extract(sys.argv[1])
    for p in d.paragraphs:
        tag = "footnote" if p.footnote else p.region
        print(f"--- [{tag}] lines {p.start_line}-{p.end_line} ({len(p.sentences)} sent, {p.n_words} words)")
        for s in p.sentences:
            print(f"  {s.line:5d}{'' if s.ends_at_line_end else '*'} | {s.text}")
    print("diagnostics:", d.diagnostics)
