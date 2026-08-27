# oas-browser

A browser for OpenAPI specifications. Blazor WebAssembly, built on
[keel](https://github.com/AdamCoulterOz/keel).

It is general: it reads a spec, not a particular API's spec.

## What is here

The app is in `src/OasBrowser`. It loads a catalogue, `specs.json`, and the
OpenAPI 3.0 documents that catalogue names, and renders four kinds of page:
an overview, a resource listing grouped by tag, an operation, and a schema.
Navigation is a hash route, so the whole thing is a static site with no server
behind it.

The model in `Model/` reads OpenAPI straight from `JsonElement` rather than
through an OpenAPI library. That covers the subset of 3.0 it was written
against, which is not all of 3.0: the model and the inline markdown renderer
both carry a `PENDING GENERALISATION` note saying so. Deciding what the subset
has to be for an arbitrary spec is outstanding work, not a settled boundary.

Two other things are honest to say about how general it is today. The shell
still carries a fixed title rather than taking one from the spec it loaded, and
`specs.json` is not in the repository: the app resolves it against its own base
href and expects whoever assembles the site to put it there beside
`index.html`.

keel owns how the controls look. `wwwroot/css/app.css` only arranges them, and
the few places it styles rather than places are marked in that file as keel
gaps.

## Fixtures

`tests/fixtures` holds small OpenAPI 3.0.3 documents, each written to exercise
one thing, with a JSON sidecar per fixture recording what correct rendering
looks like. The sidecars carry a per-assertion `status`, so what the browser
cannot do yet is a query rather than a careful read of prose, and assertions
marked `pending` describe correct behaviour rather than current behaviour.
There is no harness running them yet. See
[tests/fixtures/README.md](tests/fixtures/README.md), which explains the layout
and the rules, in particular that pending and security assertions are not to be
softened to match what the app does.

`tests/test_fingerprint_importmap.py` is a real suite, standard library only,
covering the publish step described below:

```
python3 -m unittest discover -s tests -v
```

## Building

keel is a private package, so a restore needs a token carrying `read:packages`:

```
gh auth refresh -s read:packages
dotnet nuget add source https://nuget.pkg.github.com/AdamCoulterOz/index.json \
  --name keel --username AdamCoulterOz --password "$(gh auth token)" --store-password-in-clear-text
dotnet build src/OasBrowser
```

Without that scope the restore fails with `NU1301 ... 403 (Forbidden)`, which
reads exactly like the package not existing.

CI does the same thing with its own `GITHUB_TOKEN`, which works only because
this repository has been granted access on the package under its **Manage
Actions access** setting. That grant has no API behind it, so a green
[build](.github/workflows/build.yml) run is the only way to check it.

## Publishing

Assets are fingerprinted, so a returning visitor never boots with a cached copy
of an assembly whose hash has moved. This SDK emits
`_framework/dotnet.<hash>.js` but leaves the loader importing `./dotnet.js`
with nothing mapping the two, so a publish needs one more step:

```
dotnet publish src/OasBrowser -c Release -o dist
python3 fingerprint-importmap.py dist/wwwroot
```

Without that second command the published site 404s on its first import. It is
tested rather than trusted, because the way it fails is to skip quietly and
leave the build green.

## `.nojekyll`

This site publishes to GitHub Pages, which runs Jekyll, which excludes any path
beginning with an underscore. Blazor serves its runtime from `_framework/` and
package assets from `_content/`, so without `.nojekyll` at the root the site
returns 404s for both and never boots. Do not tidy it away: the failure looks
like a broken build rather than a missing file.
