import io
import unittest
import zipfile
from tempfile import TemporaryDirectory
from pathlib import Path

from _paths import DEMO  # noqa: F401  (sets sys.path)
import docxprose
import mdprose
import prose
import texprose
from textcore import split_sentences

TEX = r"""\documentclass{article}
\newtheorem{thm}{Theorem}
\newcommand{\sys}{\textsc{Breeze}\xspace}
\begin{document}
\section{Intro}
We present \sys, which works on phones, \eg in the field.
The bound is $x \le y.$ Then we stop.
% a comment that is not prose
\begin{thm}\label{thm:a} All clocks drift. \end{thm}
\begin{equation} a = b. \end{equation}
See \citet{smith2020} and \citep{a,b} for details\footnote{This note is prose too.}.
\begin{figure} \caption{Not prose.} \end{figure}
\section*{Acknowledgments}
We thank everyone involved in this.
\appendix
\section{More}
Appendix text is here for sure.
\end{document}
"""


class TestTextCore(unittest.TestCase):
    def test_abbreviations_do_not_split(self):
        s = split_sentences("We use e.g. a filter, as in Smith et al. for this. Then it stops here.")
        self.assertEqual(len(s), 2)

    def test_line_of_points_at_the_hit(self):
        doc = texprose.extract("\\begin{document}\nA sentence that starts here\ncontinues with a word---and\n"
                               "ends on the third line.\n\\end{document}\n")
        s = doc.sentences()[0]
        self.assertEqual(s.line, 2)
        self.assertEqual(s.line_of(s.text.index("continues")), 3)
        self.assertEqual(s.line_of(s.text.index("\u2014")), 3)
        self.assertEqual(s.line_of(s.text.index("third")), 4)


class TestLatex(unittest.TestCase):
    def setUp(self):
        self.doc = texprose.extract(TEX)
        self.texts = [s.text for s in self.doc.sentences()]

    def test_macros_and_math(self):
        self.assertIn("We present Breeze, which works on phones, e.g. in the field.", self.texts)
        self.assertIn("The bound is MATH.", self.texts)

    def test_frozen_and_floats_removed(self):
        joined = " ".join(self.texts)
        self.assertNotIn("All clocks drift", joined)
        self.assertNotIn("Not prose", joined)
        self.assertNotIn("comment", joined)
        self.assertEqual(self.doc.line_kind[9], "frozen")

    def test_declared_theorem_env_detected(self):
        self.assertIn("thm", self.doc.diagnostics["theorem_envs_declared"])
        self.assertIn("sys", self.doc.diagnostics["macros_expanded"])

    def test_citations_and_footnotes(self):
        self.assertTrue(any(t.startswith("See Author and for details") for t in self.texts))
        notes = [p for p in self.doc.paragraphs if p.footnote]
        self.assertEqual([p.text for p in notes], ["This note is prose too."])

    def test_acknowledgments_excluded_and_appendix_marked(self):
        self.assertNotIn("We thank everyone involved in this.", self.texts)
        regions = {p.text: p.region for p in self.doc.paragraphs}
        self.assertEqual(regions.get("Appendix text is here for sure."), "appendix")

    def test_config_unfreeze_and_macros(self):
        doc = prose.extract_text(TEX.replace(r"\sys,", r"\method,"), "tex",
                                 {"latex": {"unfrozen_envs": ["thm"], "macros": {"method": "FooNet"}}})
        texts = " ".join(s.text for s in doc.sentences())
        self.assertIn("All clocks drift", texts)
        self.assertIn("We present FooNet", texts)


MD = """---
title: A post
---

# Heading here

This is the first paragraph with a [link](https://example.org) and `code`.
It continues here with math $x^2$ and a citation [@smith2020; @jones].

```python
print("not prose at all, this is code")
```

> A quote from someone else that we exclude.

- A list item that is prose as well.

Second paragraph cites @smith2020 inline.[^n]

[^n]: The footnote is a separate paragraph.
"""


class TestMarkdown(unittest.TestCase):
    def setUp(self):
        self.doc = mdprose.extract(MD)
        self.texts = [s.text for s in self.doc.sentences()]

    def test_prose_cleaned(self):
        self.assertIn("This is the first paragraph with a link and CODE.", self.texts)
        self.assertIn("It continues here with math MATH and a citation.", self.texts)
        self.assertIn("Second paragraph cites Author inline.", self.texts)

    def test_blocks_classified(self):
        joined = " ".join(self.texts)
        self.assertNotIn("not prose", joined)
        self.assertNotIn("someone else", joined)
        self.assertEqual(self.doc.line_kind[1], "preamble")
        self.assertEqual(self.doc.line_kind[5], "heading")
        self.assertEqual(self.doc.line_kind[11], "frozen")
        self.assertTrue(any(p.footnote for p in self.doc.paragraphs))


def make_docx(paragraphs):
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = ""
    for style, text in paragraphs:
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        body += f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


class TestDocx(unittest.TestCase):
    def test_headings_skipped_and_citations_removed(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "s.docx"
            p.write_bytes(make_docx([("Heading1", "Introduction"),
                                     (None, "Sensors drift over time [3, 5-7]. We correct this (Smith et al., 2020).")]))
            doc = docxprose.extract(p)
            self.assertEqual([s.text for s in doc.sentences()], ["Sensors drift over time.", "We correct this."])
            self.assertFalse(doc.layout_meaningful)


class TestDemoCorpus(unittest.TestCase):
    def test_samples_extract_cleanly(self):
        for path in sorted((DEMO / "samples").iterdir()):
            doc = prose.extract(path)
            self.assertGreater(len(doc.words()), 300, path.name)
            self.assertEqual(doc.diagnostics.get("artifacts"), [], path.name)


if __name__ == "__main__":
    unittest.main()
