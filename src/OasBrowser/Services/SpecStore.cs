using System.Text.Json;
using System.Text.Json.Serialization;
using OasBrowser.Model;

namespace OasBrowser.Services;

/// <summary>
/// The object form of specs.json. A corpus declares things about itself here
/// that a bare array has nowhere to put: which spec a bare link resolves
/// against today, and the grade vocabulary, docs provider and branding that are
/// still to come.
/// </summary>
public sealed class CatalogueDocument
{
    [JsonPropertyName("default")] public string? Default { get; set; }
    [JsonPropertyName("index")] public string? Index { get; set; }
    [JsonPropertyName("specs")] public List<SpecEntry> Specs { get; set; } = [];
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
public sealed class SpecStore(HttpClient http)
{
    private readonly Dictionary<string, OpenApiSpec> _cache = new(StringComparer.Ordinal);

    // Everything the app reads is served beside index.html: specs.json at the
    // app's base href, and each spec at the relative url that catalogue gives.
    // So the prefix is empty and the base href does the work. Whoever assembles
    // the site owes it that layout; this app expresses it in one constant.
    private const string SiteRoot = "";

    public IReadOnlyList<SpecEntry> Catalogue { get; private set; } = Array.Empty<SpecEntry>();

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

    public async Task<IReadOnlyList<SpecEntry>> LoadCatalogueAsync()
    {
        if (Catalogue.Count > 0) return Catalogue;

        // Two shapes, told apart by reading the JSON rather than by a version
        // field. A bare array is the original catalogue and keeps its original
        // meaning exactly, first entry as the default. An object carries the
        // corpus-level declarations that an array has nowhere to put.
        using var doc = JsonDocument.Parse(await http.GetStringAsync(SiteRoot + "specs.json"));

        if (doc.RootElement.ValueKind == JsonValueKind.Array)
        {
            Catalogue = doc.RootElement.Deserialize<List<SpecEntry>>() ?? [];
            DefaultSpecId = Catalogue.FirstOrDefault()?.Id;
        }
        else
        {
            var read = doc.RootElement.Deserialize<CatalogueDocument>() ?? new CatalogueDocument();
            Catalogue = read.Specs;
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
        var json = await http.GetStringAsync(SiteRoot + entry.Url);
        var spec = OpenApiSpec.Parse(json);
        _cache[entry.Id] = spec;
        return spec;
    }
}
