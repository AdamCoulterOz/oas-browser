#!/usr/bin/env python3
"""Contrast for the ink pairs this app puts side by side, across two keel versions.

Why this exists, since it is not a test and does not gate anything.

keel commits a contrast ratio for ink against ground. It commits nothing about
two inks a layout places next to each other, because until now nobody had
measured any. So a keel release can improve every guarantee it makes and still
degrade a pair this app depends on, with no check anywhere able to flag it,
because nothing was violated at either end. That is not hypothetical: 0.4.3
improved every ink-against-ground ratio here and degraded every ink-against-ink
pair, and the same token movement did both.

Two versions rather than one, deliberately. A pair that is bad in isolation is
visible from a single state. A pair that got *worse* is not, and that is the
class of defect this exists to catch. Reading only the current version would
answer a different question from the one being asked.

What it does NOT tell you is whether a pair is a problem. A low ratio is fine
where another cue separates the pair, and this app's healthiest pair scores
lower than its broken one:

    request line  host|path   2.57   broken. Same family, size and weight,
                                     no separator, no whitespace. Colour is
                                     not the primary cue, it is the only one.
    property meta rest|type   1.39   healthy. Mono against sans, a separator
                                     glyph and a gap. Colour contributes
                                     nothing and is not asked to.

So the rule this measurement serves is "colour must not be the sole cue
distinguishing two things a reader has to tell apart", and the number is one
input to that judgement rather than the judgement. Do not turn it into a
threshold: no flat cutoff sorts those two rows, because they are in the wrong
order for one.

Usage:
    python3 tools/contrast_pairs.py 0.4.2 0.4.3
    python3 tools/contrast_pairs.py 0.4.2 0.4.3 --packages ~/.nuget/packages/keel
"""

import argparse
import pathlib
import re
import sys

# Pairs this app actually renders adjacent, each named by what a reader has to
# separate. Add a row when a layout here puts two inks side by side; that is the
# event this file exists to track, and nothing else will notice it.
PAIRS = [
    ("request line   host|path", "text-tertiary", "text-primary"),
    ("property meta  rest|type", "text-tertiary", "text-secondary"),
]

INKS = ["text-primary", "text-secondary", "text-tertiary"]
GROUND = "surface-subtle"


def relative_luminance(hex_colour):
    """WCAG 2.x relative luminance."""
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def declarations(text):
    """Every `--name: value` in a chunk of CSS, last write winning."""
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"--([\w-]+)\s*:\s*([^;}]+)", text)}


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def block(text, selector):
    """The body of one flat top-level `selector { ... }` rule, or ''.

    Flat is enough here: every block this reads is a bare declaration list.
    It would not survive nesting, and it does not need to.
    """
    m = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", text)
    return m.group(1) if m else ""


def resolve(name, table, seen=None):
    """Follow var(--x) chains down to a literal colour."""
    seen = seen or set()
    if name in seen:
        raise ValueError(f"cyclic token: {name}")
    seen.add(name)
    value = table.get(name)
    if value is None:
        raise KeyError(name)
    ref = re.fullmatch(r"var\(\s*--([\w-]+)\s*\)", value)
    return resolve(ref.group(1), table, seen) if ref else value


def palette(tokens_dir):
    """Light and dark token tables for one installed keel version.

    `theme-dark.css` holds four blocks, and reading it whole gets the wrong
    answer: a `:root` block declaring the --kd-* dark values, two triggers
    mapping the shared names onto them (`@media prefers-color-scheme: dark` and
    `.keel-dark`), and a `.keel-light` block mapping them back for a light
    subtree inside a dark page. Last-write-wins over the file picks `.keel-light`
    and silently reports light numbers under the heading "dark". This function
    was written that way first and reproduced light twice, which is the only
    reason the bug was visible at all.

    So: light is every file except theme-dark.css. Dark is that, plus the --kd-*
    source of truth, plus the `.keel-dark` map specifically.
    """
    light = {}
    for f in sorted(tokens_dir.glob("*.css")):
        if f.name != "theme-dark.css":
            light.update(declarations(strip_comments(f.read_text())))

    theme = strip_comments((tokens_dir / "theme-dark.css").read_text())
    dark = dict(light)
    dark.update(declarations(block(theme, ":root")))        # --kd-* values
    dark.update(declarations(block(theme, ".keel-dark")))   # the map onto them

    if dark.get("text-tertiary") == light.get("text-tertiary"):
        raise SystemExit(
            "dark and light resolved --text-tertiary to the same token, so the "
            "theme parse is wrong and every dark figure below would be a light "
            "one. Check the block names in theme-dark.css.")
    return {"light": light, "dark": dark}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before", help="earlier keel version, e.g. 0.4.2")
    ap.add_argument("after", help="later keel version, e.g. 0.4.3")
    ap.add_argument("--packages", default="~/.nuget/packages/keel",
                    help="where keel packages are installed")
    args = ap.parse_args()

    root = pathlib.Path(args.packages).expanduser()
    versions = {}
    for v in (args.before, args.after):
        tokens = root / v / "staticwebassets" / "tokens"
        if not tokens.is_dir():
            sys.exit(f"no tokens for keel {v} at {tokens}. "
                     f"Restore that version, or pass --packages.")
        versions[v] = palette(tokens)

    def ratio(version, theme, a, b):
        table = versions[version][theme]
        return contrast(resolve(a, table), resolve(b, table))

    for theme in ("light", "dark"):
        print(f"\n=== {theme} ===")
        print(f"  {'':26s} {args.before:>7s}    {args.after:>7s}")

        print("  -- ink against ink: what a layout puts side by side --")
        for name, a, b in PAIRS:
            old, new = ratio(args.before, theme, a, b), ratio(args.after, theme, a, b)
            delta = (new - old) / old * 100
            print(f"  {name:26s} {old:7.2f} -> {new:7.2f}   ({delta:+.0f}%)")

        print(f"  -- ink against ground: measured on --{GROUND} --")
        for ink in INKS:
            old = ratio(args.before, theme, ink, GROUND)
            new = ratio(args.after, theme, ink, GROUND)
            delta = (new - old) / old * 100
            note = "" if new >= 4.5 else "   below AA 4.5"
            print(f"  {ink:26s} {old:7.2f} -> {new:7.2f}   ({delta:+.0f}%){note}")

    print("\nA pair moving down is not automatically a defect, and a pair moving")
    print("up is not automatically safe. Ask what separates the pair when colour")
    print("is removed; if the answer is nothing, the ratio is the whole cue.")


if __name__ == "__main__":
    main()
