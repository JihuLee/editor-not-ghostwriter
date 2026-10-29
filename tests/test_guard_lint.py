import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _paths import DEMO, SAMPLES
import ai_tell_lint
import diff_guard
import style_profile
import tells as tl

SAMPLE_TEX = DEMO / "samples" / "breeze_sampling.tex"
SAMPLE_MD = DEMO / "samples" / "field_notes.md"


def demo_profile():
    pr = style_profile.build_profile(SAMPLES)
    pr["watchlist"] = json.loads((DEMO / "build-inputs" / "watchlist.json").read_text(encoding="utf-8"))
    pr["config"] = {}
    return pr


PROFILE = demo_profile()


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_guard(self, src: Path, edits, profile=PROFILE, **kw):
        """edits: list of (old, new) replacements, each must occur exactly once."""
        text = src.read_bytes().decode("utf-8")          # keep CRLF line endings as they are
        for old, new in edits:
            self.assertEqual(text.count(old), 1, old)
            text = text.replace(old, new)
        orig = self.dir / ("orig" + src.suffix)
        shutil.copy(src, orig)
        ed = self.dir / ("edited" + src.suffix)
        ed.write_bytes(text.encode("utf-8"))
        return diff_guard.guard(orig, ed, profile, **kw)

    def statuses(self, res):
        return [h.status for h in res["hunks"]]


class TestGuardLatex(GuardCase):
    def test_slip_fix_is_clean_and_noted(self):
        res = self.run_guard(SAMPLE_TEX, [("takes less samples", "takes fewer samples")])
        self.assertEqual(self.statuses(res), ["OK"])
        self.assertIn("fixes recurring slip", res["hunks"][0].notes[0])

    def test_hard_rules_revert(self):
        cases = [
            ("Most of these devices", "Most of these pivotal devices", "tier-A"),
            ("This is wasteful in two directions.", "This is wasteful---in two directions.", "em dash"),
            ("deployment of 18 sensors over four months", "deployment of 19 sensors over four months", "number"),
            (r"\citep{kumar2015rise,morawska2018applications}", r"\citep{kumar2015rise}", "citation"),
            ("Then the error on this interval is at most", "Then the error on this interval is below", "theorem"),
            ("lemma below bounds how long it stays blind.",
             "lemma below bounds how long it stays blind. This sentence is new.", "new sentence"),
        ]
        for old, new, what in cases:
            with self.subTest(what):
                res = self.run_guard(SAMPLE_TEX, [(old, new)])
                self.assertEqual(self.statuses(res), ["FLAG"], res["hunks"][0].flags if res["hunks"] else None)
                self.assertNotIn(new, "\n".join(res["merged"]))

    def test_one_bad_line_does_not_revert_neighbours(self):
        res = self.run_guard(SAMPLE_TEX, [
            ("research groups run networks of", "research groups operate networks of"),
            (r"\citep{kumar2015rise,morawska2018applications}", r"\citep{kumar2015rise}"),
            ("batteries or small solar panels; their", "batteries or small solar cells; their"),
        ])
        self.assertEqual(sorted(self.statuses(res)), ["FLAG", "OK", "OK"])
        merged = "\n".join(res["merged"])
        self.assertIn("operate networks", merged)
        self.assertIn("solar cells", merged)
        self.assertIn("morawska2018applications", merged)

    def test_split_warns_and_strict_reverts_warnings(self):
        res = self.run_guard(SAMPLE_TEX, [("as it is on most nights, the sensor", "as it is on most nights. The sensor")])
        self.assertEqual(self.statuses(res), ["WARN"])
        res = self.run_guard(SAMPLE_TEX, [("In short, the controller", "Additionally, the controller")], strict=True)
        self.assertEqual(self.statuses(res), ["FLAG"])

    def test_multiline_inline_math(self):
        src = self.dir / "m.tex"
        src.write_text("\\begin{document}\nThe value $a +\nb_i$ is small here.\n\\end{document}\n", encoding="utf-8")
        res = self.run_guard(src, [("b_i$ is", "b_j$ is")])
        self.assertEqual(self.statuses(res), ["FLAG"])
        self.assertIn("inline math changed", res["hunks"][0].flags)

    def test_crlf_and_noop(self):
        crlf = self.dir / "crlf.tex"
        crlf.write_bytes(SAMPLE_TEX.read_bytes().replace(b"\n", b"\r\n"))
        res = self.run_guard(crlf, [("takes less samples", "takes fewer samples")])
        self.assertTrue(all(l.endswith("\r") for l in res["merged"][:-1]))
        res = self.run_guard(SAMPLE_TEX, [])
        self.assertEqual(res["hunks"], [])

    def test_circular_profile_detected(self):
        res = self.run_guard(SAMPLE_TEX, [])
        self.assertEqual(res["circular"], "breeze_sampling.tex")


class TestGuardMarkdown(GuardCase):
    def test_markdown_rules(self):
        res = self.run_guard(SAMPLE_MD, [("ours took fifteen", "ours took twenty")])
        self.assertEqual(self.statuses(res), ["OK"])
        res = self.run_guard(SAMPLE_MD, [("At minus ten degrees", "At minus 10 degrees")])
        self.assertEqual(self.statuses(res), ["FLAG"])
        res = self.run_guard(SAMPLE_MD, [("interval = min(", "interval = max(")])
        self.assertEqual(self.statuses(res), ["FLAG"])
        self.assertIn("touches a code block", res["hunks"][0].flags)


class TestAuthorWords(GuardCase):
    def test_own_tier_b_word_is_not_warned(self):
        pr = json.loads(json.dumps(PROFILE))
        res = self.run_guard(SAMPLE_TEX, [("a small controller that runs", "a novel controller that runs")], profile=pr)
        self.assertEqual(self.statuses(res), ["WARN"])
        pr["rates_per_1k"]["tierB"]["novel"] = 1.0
        res = self.run_guard(SAMPLE_TEX, [("a small controller that runs", "a novel controller that runs")], profile=pr)
        self.assertEqual(self.statuses(res), ["OK"])

    def test_allow_list(self):
        pr = json.loads(json.dumps(PROFILE))
        pr["config"] = {"allow": ["pivotal", "moreover"]}
        res = self.run_guard(SAMPLE_TEX, [("Most of these devices", "Most of these pivotal devices")], profile=pr)
        self.assertEqual(self.statuses(res), ["OK"])
        res = self.run_guard(SAMPLE_TEX, [("In short, the controller", "Moreover, the controller")], profile=pr)
        self.assertEqual(self.statuses(res), ["OK"])


class TestWatchlistMatching(unittest.TestCase):
    def test_regex_entries_match_whole_words(self):
        wl = tl.compile_watchlist([{"match": "less (?:samples|sensors)", "regex": True, "fix": "fewer"},
                                   {"match": "allows to", "fix": "allows us to"}])
        for text in ("unless sensors", "wireless sensors", "regardless samples", "it swallows to"):
            self.assertEqual(tl.watchlist_hits(text, wl), [], text)
        self.assertEqual(len(tl.watchlist_hits("It takes less samples and allows to run.", wl)), 2)


class TestAuthorRelativeRules(unittest.TestCase):
    def test_em_dash_user_is_not_hard(self):
        pr = json.loads(json.dumps(PROFILE))
        pr["rates_per_1k"]["structural"]["em_dash"] = 2.0
        self.assertNotIn("em_dash", tl.Rules(pr).hard_devices)
        self.assertIn("em_dash", tl.Rules(PROFILE).hard_devices)

    def test_tier_a_word_used_by_author_is_soft(self):
        pr = json.loads(json.dumps(PROFILE))
        pr["counts"]["tierA"] = {"intricate": 3}
        rules = tl.Rules(pr)
        self.assertNotIn("intricate", rules.tier_a_hard)
        self.assertIn("intricate", rules.tier_soft)

    def test_layout_rule(self):
        self.assertFalse(tl.Rules(PROFILE).keeps_one_sentence_per_line)


class TestLint(unittest.TestCase):
    def test_demo_draft(self):
        res = ai_tell_lint.lint(DEMO / "draft.tex", PROFILE)
        whats = {h["what"] for h in res["hard"]}
        self.assertIn("tier-A 'delve'", whats)
        self.assertIn("em dash", whats)
        lines = {h["what"]: h["line"] for h in res["hard"]}
        self.assertEqual(lines["em dash"], 21)
        self.assertEqual(lines["tier-A 'pave the way'"], 59)
        reasons = res["paragraphs"][1]["reasons"]
        self.assertEqual(sum("moreover" in r for r in reasons), 1)
        self.assertEqual({g["match"].lower() for g in res["grammar"]}, {"allows to", "less samples"})
        self.assertEqual(res["paragraphs"][0]["lines"][0], 18)
        self.assertIsNone(res["circular"])

    def test_own_samples_are_clean(self):
        for path in SAMPLES:
            res = ai_tell_lint.lint(path, PROFILE)
            self.assertEqual(res["hard"], [], path.name)
            self.assertEqual(res["circular"], path.name)


if __name__ == "__main__":
    unittest.main()
