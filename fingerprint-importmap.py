#!/usr/bin/env python3
"""Point the Blazor loader at the fingerprinted runtime.

Asset fingerprinting has to stay on. Without it every asset keeps a stable
name, so after a deploy a returning visitor boots with a cached copy of the one
assembly that changed, its hash no longer matches what the runtime expects, and
the app fails to start until a hard refresh. Fingerprinted names make each
build's assets distinct, so a stale copy is simply never requested.

The gap this fills: with fingerprinting on, this SDK emits
`_framework/dotnet.<hash>.js` but leaves `blazor.webassembly.js` doing a plain
`import("./dotnet.js")`, and writes nothing that maps one to the other, so the
loader 404s on the very first import. Everything downstream is fine, because
the assembly list is embedded in the runtime module itself; only the entry
point needs redirecting. An import map does that, and is what the SDK injects
when it does this itself.

Run after publish, against the published wwwroot.
"""
import pathlib
import re
import sys


def main(wwwroot: pathlib.Path) -> int:
    framework = wwwroot / "_framework"
    index = wwwroot / "index.html"

    if not index.is_file():
        print(f"no index.html in {wwwroot}", file=sys.stderr)
        return 1

    # the runtime entry point, e.g. dotnet.ducu1w6ht9.js, and not
    # dotnet.native.*.js or dotnet.runtime.*.js which it pulls in itself
    hashed = [p.name for p in framework.glob("dotnet.*.js")
              if re.fullmatch(r"dotnet\.[a-z0-9]+\.js", p.name)]

    if not hashed:
        # fingerprinting off, or a future SDK that wires this up on its own
        print("no fingerprinted runtime found; leaving index.html alone")
        return 0
    if len(hashed) > 1:
        print(f"expected one fingerprinted runtime, found {hashed}", file=sys.stderr)
        return 1

    html = index.read_text()
    if "importmap" in html:
        print("index.html already carries an import map; leaving it alone")
        return 0

    # Import map keys are resolved specifiers, so they need the same base the
    # loader resolves against, which is the app's base href.
    base_match = re.search(r'<base href="([^"]+)"', html)
    base = base_match.group(1) if base_match else "/"

    import_map = (
        '    <script type="importmap">\n'
        '    {\n'
        '      "imports": {\n'
        f'        "{base}_framework/dotnet.js": "{base}_framework/{hashed[0]}"\n'
        '      }\n'
        '    }\n'
        '    </script>\n'
    )

    # must come before the loader that performs the import
    anchor = re.search(r'[ \t]*<script src="_framework/blazor\.webassembly[^"]*"></script>', html)
    if not anchor:
        print("could not find the blazor loader script tag in index.html", file=sys.stderr)
        return 1

    index.write_text(html[:anchor.start()] + import_map + html[anchor.start():])
    print(f"import map added: {base}_framework/dotnet.js -> {hashed[0]}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        print("usage: fingerprint-importmap.py <published-wwwroot>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1])))
