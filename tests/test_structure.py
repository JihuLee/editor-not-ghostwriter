import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _paths import BUILDER, DEMO, ENGINE, SAMPLES
import ai_tell_lint
import structure
import style_profile
import voice_rules

PY = sys.executable
INPUTS = DEMO / "build-inputs"

PAPER = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We study a small problem and report what we found in a short abstract here.
\end{abstract}
\section{Introduction}
We introduce the problem in a few sentences. The second sentence adds context for the reader.
% \section{Old related work}
% This commented section must not count.
\iffalse
\section{Dropped section}
Text that was switched off and must not count either.
\fi
\section{Preliminaries}
We fix the notation in this section. Each symbol is defined before it is used.
\input{sec/method}
\section{Conclusion}
We close the paper with a short summary of the findings.
\section{Acknowledgments}
We thank the people who helped with this work in many ways.
\appendix
\input{sec/extra}
\end{document}
"""
METHOD = r"""\section{Matched sampling for small problems}
We describe the method in a short lead paragraph before its parts.
\subsection{The sampler}
The sampler draws one value at a time and keeps it when the test passes.
\paragraph{Cost.} Each step costs one evaluation of the target density.
"""
EXTRA = r"""\section{Additional results}
We report more results here for the interested reader of the appendix.
"""


def run(*args):
    return subprocess.run([PY, *map(str, args)], capture_output=True, text=True)


class TestMeasure(unittest.TestCase):
    def test_demo_papers(self):
        papers = structure.measure([DEMO / "samples"])
        by = {p["source"]: p for p in papers}
        self.assertTrue(by["breeze_sampling.tex"]["complete"])
        self.assertEqual(by["breeze_sampling.tex"]["order"],
                         ["introduction", "related", "body", "experiments", "discussion", "conclusion"])
        self.assertFalse(by["field_notes.md"]["complete"])
        self.assertGreater(by["breeze_sampling.tex"]["appendix_words"], 0)

    def test_inputs_comments_and_appendix(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sec").mkdir()
            (root / "main.tex").write_text(PAPER, encoding="utf-8")
            (root / "sec" / "method.tex").write_text(METHOD, encoding="utf-8")
            (root / "sec" / "extra.tex").write_text(EXTRA, encoding="utf-8")
            papers = structure.measure([root])
        self.assertEqual(len(papers), 1)                      # the input files are part of main.tex
        p = papers[0]
        self.assertEqual(p["order"], ["introduction", "preliminaries", "body", "conclusion"])
        titles = [t[1] for t in p["titles"]]
        self.assertNotIn("Old related work", titles)
        self.assertNotIn("Dropped section", titles)
        self.assertNotIn("Acknowledgments", titles)           # back matter is left out
        self.assertIn(["1", "Additional results", "appendix"], [[str(t[0]), t[1], t[2]] for t in p["titles"]])
        self.assertGreater(p["appendix_words"], 0)
        self.assertEqual(p["run_in_headings"], 1)

    def test_ieee_appendices_and_title_case(self):
        tex = PAPER.replace("\\appendix", "\\appendices").replace("\\input{sec/extra}", EXTRA)
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "paper.tex"
            f.write_text(tex.replace("\\input{sec/method}", METHOD), encoding="utf-8")
            p = structure.measure([f])[0]
        self.assertEqual(p["titles"][-1][2], "appendix")
        self.assertEqual(structure.title_case("Matched Gibbs posterior for fair variational inference"),
                         "sentence")
        self.assertEqual(structure.title_case("Omitted Results and Details"), "title")
        self.assertIsNone(structure.title_case("Introduction"))


class TestProfileAndLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.with_structure = style_profile.build_profile(SAMPLES, structure=True)
        cls.without = style_profile.build_profile(SAMPLES)

    def test_optional(self):
        self.assertNotIn("structure", self.without)
        s = self.with_structure["structure"]["summary"]
        self.assertEqual(s["n_complete"], 2)
        self.assertIn("## Section structure", style_profile.to_markdown(self.with_structure))
        self.assertNotIn("## Section structure", style_profile.to_markdown(self.without))

    def test_lint_reports_structure_only_with_a_baseline(self):
        res = ai_tell_lint.lint(DEMO / "draft.tex", self.with_structure)
        md = ai_tell_lint.to_markdown(res, self.with_structure)
        self.assertIn("## 5. Structure against the author's baseline", md)
        self.assertIn("| related section | missing |", md)
        res = ai_tell_lint.lint(DEMO / "draft.tex", self.without)
        self.assertNotIn("## 5.", ai_tell_lint.to_markdown(res, self.without))

    def test_voice_rules_describe_structure(self):
        self.assertIn("Section structure", voice_rules.render(self.with_structure))
        self.assertNotIn("Section structure", voice_rules.render(self.without))

    def test_cli_and_build(self):
        with TemporaryDirectory() as tmp:
            work = Path(tmp)
            r = run(ENGINE / "style_profile.py", *SAMPLES, "-o", work / "p.json", "--structure")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("structure", json.loads((work / "p.json").read_text(encoding="utf-8")))
            out = work / "build" / "demo-voice"
            r = run(BUILDER / "build_skill.py", "--name", "demo-voice", "--profile", work / "p.json",
                    "--notes", INPUTS / "voice_notes.md", "--watchlist", INPUTS / "watchlist.json", "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            voice = (out / "references" / "author_voice.md").read_text(encoding="utf-8")
            self.assertIn("## Structure (generated)", voice)
            self.assertLess(voice.index("## Structure (generated)"), voice.index("## Recurring slips"))
            r = run(BUILDER / "validate_skill.py", out, "--samples", *SAMPLES)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
