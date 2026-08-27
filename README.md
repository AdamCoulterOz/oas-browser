# oas-browser

A browser for OpenAPI specifications. Blazor WebAssembly, built on
[keel](https://github.com/AdamCoulterOz/keel).

It is general: it reads a spec, not a particular API's spec.

Right now this repository is a scaffold. The app itself is not here yet, so
there is nothing to describe beyond the shape it will arrive into.

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

## `.nojekyll`

This site publishes to GitHub Pages, which runs Jekyll, which excludes any path
beginning with an underscore. Blazor serves its runtime from `_framework/` and
package assets from `_content/`, so without `.nojekyll` at the root the site
returns 404s for both and never boots. Do not tidy it away: the failure looks
like a broken build rather than a missing file.
