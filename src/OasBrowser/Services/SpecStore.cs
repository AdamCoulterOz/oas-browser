using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Components;
using System.Web;
using OasBrowser.Model;

namespace OasBrowser.Services;

/// <summary>
/// The object form of specs.json. A corpus declares things about itself here
/// that a bare array has nowhere to put: which spec a bare link resolves
/// against today, what it calls itself, and the grade vocabulary and docs
/// provider that are still to come.
/// </summary>
public sealed class CatalogueDocument
{
    [JsonPropertyName("default")] public string? Default { get; set; }
    [JsonPropertyName("index")] public string? Index { get; set; }
    [JsonPropertyName("brand")] public CatalogueBrand? Brand { get; set; }

    /// <summary>
    /// Where the coverage mapping for this corpus lives, if it has one.
    ///
    /// Declared by the catalogue rather than configured into the app, for the
    /// same reason the specs are: a general browser that has to be told about a
    /// corpus before it can show one is not general. Optional, because coverage
    /// is a claim some other repository makes about this corpus and most corpora
    /// have nobody making it.
    /// </summary>
    [JsonPropertyName("coverage")] public string? Coverage { get; set; }

    [JsonPropertyName("specs")] public List<SpecEntry> Specs { get; set; } = [];
}

/// <summary>
/// What a corpus calls itself, as the catalogue declares it. This is the only
/// place a corpus name can enter the app: the browser is general and its source
/// carries no corpus's branding, so a catalogue that declares none gets the
/// neutral default rather than the last corpus this app happened to grow up
/// beside.
/// </summary>
public sealed class CatalogueBrand
{
    [JsonPropertyName("long")] public string? Long { get; set; }
    [JsonPropertyName("short")] public string? Short { get; set; }
    [JsonPropertyName("description")] public string? Description { get; set; }
}

/// <summary>
/// Branding with every field resolved, so the shell renders it without deciding
/// anything. Fallbacks belong here rather than in the markup: there are three
/// sites that show a name and they must all fall back the same way.
/// </summary>
public sealed record Branding(string Long, string Short, string? Description)
{
    /// <summary>
    /// Says what the app is, not what any corpus is. The one wrong answer for a
    /// general OpenAPI browser with no catalogue loaded is somebody's product
    /// name, so this string is deliberately about the tool.
    /// </summary>
    public static readonly Branding Neutral = new("API browser", "API browser", null);

    public static Branding From(CatalogueBrand? brand)
    {
        var full = brand?.Long is { Length: > 0 } declared ? declared : Neutral.Long;

        // Short falls back to long rather than to the neutral short. A corpus
        // that named itself and did not abbreviate wants its own name in the
        // narrow bar, and the alternative is a bar that says "API browser" on a
        // phone and something else on a laptop.
        var abbreviated = brand?.Short is { Length: > 0 } shortened ? shortened : full;

        return new Branding(full, abbreviated, brand?.Description is { Length: > 0 } about ? about : null);
    }
}

/// <summary>One entry of the specs.json served alongside the app.</summary>
public sealed class SpecEntry
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("url")] public string Url { get; set; } = "";
    [JsonPropertyName("repo")] public string Repo { get; set; } = "";
}

/// <summary>
/// Loads the spec catalogue and the specs themselves. Parsed specs are cached
/// for the session: they are static files and re-parsing a 350-schema document
/// on every navigation would be wasteful.
/// </summary>
public sealed class SpecStore(HttpClient http, NavigationManager nav)
{
    private readonly Dictionary<string, OpenApiSpec> _cache = new(StringComparer.Ordinal);

    private const string CatalogueParameter = "catalogue";

    private Uri? _catalogueUri;

    public IReadOnlyList<SpecEntry> Catalogue { get; private set; } = Array.Empty<SpecEntry>();

    /// <summary>Branding for the corpus on screen, neutral until one is loaded.</summary>
    public Branding Brand { get; private set; } = Branding.Neutral;

    /// <summary>
    /// The spec a link with no spec in it resolves against, declared by the
    /// catalogue. Null only when the catalogue is empty.
    ///
    /// Declared rather than positional. First-entry-wins reads as tidy and is an
    /// unstated rule: it holds only while the largest spec happens to be listed
    /// first, and reordering the catalogue would silently change what every bare
    /// link in the world means.
    /// </summary>
    public string? DefaultSpecId { get; private set; }

    /// <summary>
    /// The coverage mapping this catalogue declares, as written and unresolved,
    /// or null when it declares none.
    ///
    /// Unresolved because resolving it is <c>CoverageStore</c>'s job and it has
    /// a second source to consider first. Left as the catalogue wrote it so that
    /// there is one place a relative value is turned into a location, rather
    /// than a half-resolved value travelling between the two.
    /// </summary>
    public string? DeclaredCoverageUrl { get; private set; }

    /// <summary>
    /// Where the catalogue lives. specs.json beside index.html by default, which
    /// is what every deploy has done so far and stays exactly today's behaviour,
    /// overridden by ?catalogue=&lt;url&gt; so one published copy of the browser
    /// can read a corpus it was not served with.
    ///
    /// A URL and not a corpus name, because the alternative is a registry, and a
    /// general browser that has to be told about a corpus before it can show one
    /// is not general. Cross-origin values are allowed and need CORS from
    /// whoever serves them, which is a fact about that host and not something
    /// this app can arrange.
    ///
    /// <para>
    /// Public, and it throws when the url was refused. The two display
    /// properties below guard it because they are read while the error page
    /// renders; a caller reached during a load that has already succeeded is
    /// past that. It is the <see cref="Uri"/> and not <see cref="CatalogueUrl"/>
    /// that <c>CoverageStore</c> needs, on both counts that matter to it: a
    /// relative coverage url resolves against this the way a spec entry's does,
    /// and the mismatch check compares URLs part by part rather than as strings.
    /// Handing it the string would make it parse this value a second time,
    /// which is a second place for the parse to differ.
    /// </para>
    /// </summary>
    public Uri CatalogueUri => _catalogueUri ??= ResolveCatalogueUri();

    /// <summary>
    /// The origin the catalogue was actually fetched from, as
    /// scheme://host[:port]. Null only when the url was refused, which is the
    /// one case where there is no origin to name.
    ///
    /// Everything else this app shows about a corpus is the corpus's own claim.
    /// The nav bar name, the short name, the tab title and the tooltip all come
    /// out of the catalogue's brand block, so a catalogue served from anywhere
    /// can make this browser display any name it likes on somebody else's
    /// domain. Branding is exactly what an impersonator controls; the url the
    /// bytes came from is exactly what they do not, so that is the thing worth
    /// putting on screen beside the name.
    ///
    /// An origin allow-list was the other candidate and was rejected. It needs
    /// a list, it needs somebody to maintain the list, it needs a decision
    /// about who is on it, and it fails closed against every corpus nobody has
    /// thought of yet, which is the population a general browser exists for.
    /// Showing where the bytes came from needs none of that and leaves the
    /// judgement with the reader, who is the only party who knows which origin
    /// they expected.
    ///
    /// Wrong by construction is what to want here, and this is as close as C#
    /// gets: read-only, no setter and no backing field, computed from the Uri
    /// that ResolveCatalogueUri built out of the app's base href and the query
    /// string. Nothing deserialised is in scope, so no field added to
    /// CatalogueDocument or CatalogueBrand can ever reach it. Making this show
    /// a corpus's own claim takes an edit to this line, which is a different
    /// and much louder kind of mistake than the one being defended against.
    ///
    /// It does not throw, deliberately. A refused catalogue url makes
    /// CatalogueUri throw, the shell catches that during load and renders its
    /// error page, and the header renders alongside that page: a throw from
    /// here would turn a readable message into a dead app.
    /// </summary>
    public string? CatalogueOrigin
    {
        get
        {
            try { return CatalogueUri.GetLeftPart(UriPartial.Authority); }
            catch (Exception e) when (e is InvalidOperationException or UriFormatException) { return null; }
        }
    }

    /// <summary>
    /// The whole catalogue URL, for the supplementary text beside the origin.
    ///
    /// The origin answers the trust question, because it is the security
    /// boundary and it is what a lookalike host cannot forge. It does not
    /// answer *which catalogue this is*: two corpora published from one account
    /// share an origin and differ only in path, which is exactly the case here,
    /// where the demo corpus and the Power Platform corpus both read
    /// "adamcoulteroz.github.io" and nothing on screen separates them.
    ///
    /// Found by loading the real corpus through the redirect rather than by
    /// testing against a second local origin, which is the only arrangement
    /// where the two questions come apart.
    ///
    /// Same source as the origin, the resolved <see cref="Uri"/>, so it is
    /// equally beyond anything a catalogue can declare about itself.
    /// </summary>
    public string? CatalogueUrl
    {
        get
        {
            try { return CatalogueUri.ToString(); }
            catch (Exception e) when (e is InvalidOperationException or UriFormatException) { return null; }
        }
    }

    private Uri ResolveCatalogueUri()
    {
        var appBase = new Uri(nav.BaseUri);

        // The query survives the hash router: a query sits before the fragment,
        // so ?catalogue=... and #/athena/schemas/Foo coexist in one URL and each
        // is read by the part that owns it.
        //
        // HttpUtility rather than the ASP.NET QueryHelpers I reached for first,
        // because Microsoft.AspNetCore.WebUtilities is not on the WebAssembly
        // package's reference set and this app has no reason to take a package
        // for one line. The decode matters: an absolute catalogue url arrives
        // percent-encoded and Uri.Query hands it back that way.
        var declared = HttpUtility.ParseQueryString(new Uri(nav.Uri).Query)[CatalogueParameter];

        if (string.IsNullOrWhiteSpace(declared)) return new Uri(appBase, "specs.json");

        // Resolved against the app's base href, so a relative value names a
        // sibling of index.html and an absolute one replaces the location whole.
        var wanted = new Uri(appBase, declared.Trim());

        // http(s) only. A data: URL is fetchable, so without this a crafted link
        // could carry an entire catalogue in itself and nothing in the address
        // bar would name a server to hold responsible for it. Pointing the
        // browser at another host is the feature; pointing it at the link is not.
        if (wanted.Scheme is not ("http" or "https"))
            throw new InvalidOperationException(
                $"The {CatalogueParameter} parameter must be an http or https URL.");

        return wanted;
    }

    public async Task<IReadOnlyList<SpecEntry>> LoadCatalogueAsync()
    {
        if (Catalogue.Count > 0) return Catalogue;

        // Two shapes, told apart by reading the JSON rather than by a version
        // field. A bare array is the original catalogue and keeps its original
        // meaning exactly, first entry as the default. An object carries the
        // corpus-level declarations that an array has nowhere to put.
        using var doc = JsonDocument.Parse(await http.GetStringAsync(CatalogueUri));

        if (doc.RootElement.ValueKind == JsonValueKind.Array)
        {
            Catalogue = doc.RootElement.Deserialize<List<SpecEntry>>() ?? [];
            DefaultSpecId = Catalogue.FirstOrDefault()?.Id;
            // An array has nowhere to declare a brand, so the neutral default
            // stands. That is the correct outcome and not a gap to fill later:
            // the legacy shape says nothing about branding, so the app must not
            // invent an answer on its behalf.
        }
        else
        {
            var read = doc.RootElement.Deserialize<CatalogueDocument>() ?? new CatalogueDocument();
            Catalogue = read.Specs;
            Brand = Branding.From(read.Brand);

            // An array has nowhere to declare this either, so the legacy shape
            // gets coverage only from ?coverage=. Same argument as the brand: a
            // form that says nothing about coverage must not have an answer
            // invented on its behalf.
            DeclaredCoverageUrl = read.Coverage is { Length: > 0 } declaredCoverage
                ? declaredCoverage
                : null;

            DefaultSpecId = read.Default is { Length: > 0 } declared
                            && Catalogue.Any(s => s.Id == declared)
                ? declared
                // A default naming a spec that is not in the catalogue is a
                // corpus defect, and falling back keeps the app usable. It is
                // not silently correct: every bare link then resolves somewhere
                // the corpus did not choose, so the conformance check owes this
                // assertion and this branch should be unreachable in a checked
                // corpus.
                : Catalogue.FirstOrDefault()?.Id;
        }

        return Catalogue;
    }

    public SpecEntry? Resolve(string? specId) =>
        Catalogue.FirstOrDefault(s => s.Id == (specId ?? DefaultSpecId));

    public async Task<OpenApiSpec> LoadSpecAsync(SpecEntry entry)
    {
        if (_cache.TryGetValue(entry.Id, out var cached)) return cached;

        // Entry urls resolve against the catalogue's own location, not against
        // the app's. The catalogue is the document that names them, so it is the
        // only thing they can sensibly be relative to. Resolve them against the
        // app instead and a remote catalogue can only ever name specs on this
        // origin, which is nobody's catalogue. Unchanged for the default case,
        // where the catalogue sits at the base href and its siblings are the
        // app's siblings too.
        var json = await http.GetStringAsync(new Uri(CatalogueUri, entry.Url));
        var spec = OpenApiSpec.Parse(json);
        _cache[entry.Id] = spec;
        return spec;
    }
}
