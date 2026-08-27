"""Reconcile tools/contrast_pairs.py against figures computed before it existed.

The tool reads keel's token files. These numbers were computed by hand from the
same files, by a different route, before the tool was written, and they are kept
deliberately rather than deleted as superseded.

That is the whole point of this file. The tool had a real bug: it resolved the
dark theme by taking the last declaration of each name in theme-dark.css, which
picked up the .keel-light block at the end and printed light figures under a
dark heading. Every number was correctly computed and the table answered a
different question from its own column header. Nothing in the output said so.

It was caught only because these hand-computed values already existed to
reconcile against. Written tool-first, it would have been self-consistent and
wrong. So the manual working is the only independent thing that can contradict
the tool, and deleting it would remove the sole means of falsifying it at
exactly the moment it starts being trusted.

The canary test is the other half: a resolver that collapses the two themes
into one satisfies every per-theme assertion and violates only the assertion
that they differ, which is the one nobody writes.

Proven by making it fail. Restoring the original last-write-wins resolver turns
this file red with 18 failures, caught by `test_themes_resolve_differently` and
by `test_every_pair_matches_the_hand_computation`. `test_the_direction_...` does
**not** catch it, and that is worth knowing rather than assuming: under the bug
both themes become light, and light's direction still holds, so that test is
green on a broken apparatus. It asserts something about keel, not about this
file's own correctness.

Requires keel 0.4.2 and 0.4.3 restored. Skips rather than fails if they are not,
because a missing package is not a defect in this app.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import contrast_pairs as cp  # noqa: E402

PACKAGES = pathlib.Path("~/.nuget/packages/keel").expanduser()
BEFORE, AFTER = "0.4.2", "0.4.3"

# Computed by hand from keel's token files before contrast_pairs.py existed.
# theme -> (ink, other) -> (0.4.2, 0.4.3)
EXPECTED = {
    "light": {
        ("text-tertiary", "text-primary"):   (4.65, 2.57),
        ("text-tertiary", "text-secondary"): (1.40, 1.39),
        ("text-primary", "surface-subtle"):  (15.46, 15.46),
        ("text-secondary", "surface-subtle"): (4.66, 8.38),
        ("text-tertiary", "surface-subtle"): (3.33, 6.01),
    },
    "dark": {
        ("text-tertiary", "text-primary"):   (2.91, 2.09),
        ("text-tertiary", "text-secondary"): (1.58, 1.13),
        ("text-primary", "surface-subtle"):  (11.01, 11.01),
        ("text-secondary", "surface-subtle"): (5.96, 5.96),
        ("text-tertiary", "surface-subtle"): (3.78, 5.28),
    },
}


def tokens(version):
    return PACKAGES / version / "staticwebassets" / "tokens"


def available():
    return tokens(BEFORE).is_dir() and tokens(AFTER).is_dir()


@unittest.skipUnless(available(), f"keel {BEFORE} and {AFTER} not restored")
class ReconcileWithHandComputedFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pal = {v: cp.palette(tokens(v)) for v in (BEFORE, AFTER)}

    def ratio(self, version, theme, a, b):
        table = self.pal[version][theme]
        return cp.contrast(cp.resolve(a, table), cp.resolve(b, table))

    def test_every_pair_matches_the_hand_computation(self):
        for theme, pairs in EXPECTED.items():
            for (a, b), (before, after) in pairs.items():
                for version, expected in ((BEFORE, before), (AFTER, after)):
                    with self.subTest(theme=theme, pair=(a, b), version=version):
                        self.assertAlmostEqual(
                            self.ratio(version, theme, a, b), expected, places=2,
                            msg=f"{theme} {a}|{b} on keel {version}")

    def test_themes_resolve_differently(self):
        """The canary. A resolver that collapses the themes passes everything else.

        If dark ever resolves to the light declarations, every per-theme
        assertion above still passes on the light half and the dark half becomes
        a silent duplicate. This is the only assertion here whose failure means
        the apparatus is broken rather than the values being wrong.
        """
        for version in (BEFORE, AFTER):
            light, dark = self.pal[version]["light"], self.pal[version]["dark"]
            for token in ("text-primary", "text-secondary", "text-tertiary",
                          "surface-subtle"):
                with self.subTest(version=version, token=token):
                    self.assertNotEqual(
                        cp.resolve(token, light), cp.resolve(token, dark),
                        msg=f"--{token} resolves the same in both themes on keel "
                            f"{version}, so the theme parse has collapsed and "
                            f"every dark figure is really a light one")

    def test_the_direction_that_makes_this_worth_measuring(self):
        """0.4.3 improved every ground ratio and degraded every pair.

        Stated as an assertion rather than a paragraph, because it is the reason
        keel's #41 exists and the reason this tool does. If a later keel release
        makes it false, that is worth finding out from a failure.
        """
        for theme in ("light", "dark"):
            for ink in ("text-secondary", "text-tertiary"):
                before = self.ratio(BEFORE, theme, ink, "surface-subtle")
                after = self.ratio(AFTER, theme, ink, "surface-subtle")
                self.assertGreaterEqual(after, before - 0.01,
                                        f"{theme} {ink} against ground got worse")

            for a, b in (("text-tertiary", "text-primary"),
                         ("text-tertiary", "text-secondary")):
                before = self.ratio(BEFORE, theme, a, b)
                after = self.ratio(AFTER, theme, a, b)
                self.assertLessEqual(after, before + 0.01,
                                     f"{theme} {a}|{b} pair got better, which "
                                     f"would be good news and make this stale")


if __name__ == "__main__":
    unittest.main()
