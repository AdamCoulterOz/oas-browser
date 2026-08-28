using System.Text.Json;
using System.Web;
using Microsoft.AspNetCore.Components;
using OasBrowser.Model;

namespace OasBrowser.Services;

/// <summary>
/// Loads the coverage mapping for the corpus on screen, if there is one.
///
/// <para>
/// A mapping is another repository's published claim about this corpus: these
/// units of our code call these operations of yours. It is optional in every
/// sense. Most corpora have nobody making that claim, a corpus that has one
/// still renders without it, and nothing else in this app depends on it having
/// loaded.
/// </para>
///
/// <para>
/// <b>Everything here is arranged so that no coverage is shown unless it is
/// coverage of the corpus actually loaded.</b> The single interesting failure of
/// this feature is a mapping written against another catalogue rendering in
/// full: every id resolves, every count is plausible, and every figure is about
/// a different API. <see cref="CoverageReading"/> holds that check and holds the
/// data behind it, so a mismatch has nothing to expose rather than something
/// this class must remember not to show.
/// </para>
/// </summary>
public sealed class CoverageStore(HttpClient http, NavigationManager nav, SpecStore specs)
{
    private const string CoverageParameter = "coverage";

    /// <summary>
    /// The read, held as the task rather than as a "have I started" flag. Two
    /// callers now await this, the shell and the coverage view, and a boolean
    /// would hand the second one a store whose fetch is still in flight: it
    /// would return immediately, see a null map, and render "no mapping" over a
    /// mapping that arrives a moment later.
    /// </summary>
    private Task? _read;

    /// <summary>
    /// The mapping, or null when there is none to show. Null covers three
    /// different situations, which <see cref="Refusal"/> tells apart: no mapping
    /// was named, one was named and could not be used, or one was read and
    /// refused.
    /// </summary>
    public CoverageMap? Map { get; private set; }

    /// <summary>
    /// Why there is no mapping, when a mapping was named and is not being shown.
    /// Null when none was named, which is the ordinary case and not a fault:
    /// there is nothing to tell a reader about a claim nobody has made.
    /// </summary>
    public string? Refusal { get; private set; }

    /// <summary>Whether anything named a mapping for this corpus at all.</summary>
    public bool Declared { get; private set; }

    /// <summary>
    /// Where the mapping was actually fetched from, once one has been resolved.
    ///
    /// <para>
    /// This is the browser's own record of the fetch and never anything the
    /// document says about itself, which is the whole reason a view shows it.
    /// A mapping is somebody else's claim about this corpus and every word
    /// inside it is that somebody's to write, including any url it might carry;
    /// the address it was served from is the one fact about it that its author
    /// does not get to choose. Same argument as the catalogue origin in the nav
    /// bar, one document further out.
    /// </para>
    /// </summary>
    public Uri? Source { get; private set; }

    /// <summary>
    /// Reads the mapping, at most once per session.
    ///
    /// <para>
    /// Call after the catalogue has loaded: the catalogue is one of the two
    /// sources for the url, it is what a relative url resolves against, and it
    /// is the other half of the agreement check.
    /// </para>
    ///
    /// <para>
    /// This does not throw for a mapping it cannot use, and that is the one
    /// place it departs from <see cref="SpecStore"/>, deliberately. A refused
    /// catalogue url has to be loud because there is no app left without a
    /// catalogue. Coverage is an addition to a page that renders fully without
    /// it, and <c>?coverage=</c> travels in links that other people write, so a
    /// throw here would let any link take the whole browser down over an
    /// optional view. The reason goes to <see cref="Refusal"/> and the reader
    /// still gets their spec.
    /// </para>
    /// </summary>
    public Task LoadAsync() => _read ??= ReadAsync();

    private async Task ReadAsync()
    {
        var (source, refusal) = ResolveCoverageUri();
        Declared = source is not null || refusal is not null;

        if (refusal is not null)
        {
            Refusal = refusal;
            return;
        }

        if (source is null) return;

        Source = source;

        try
        {
            var reading = CoverageReading.Read(await http.GetStringAsync(source), CatalogueLocation());
            Map = reading.Map;
            Refusal = reading.Refusal;
        }
        catch (Exception e) when (e is HttpRequestException or JsonException)
        {
            // Named rather than swallowed. A mapping that was declared and did
            // not arrive is a defect in whoever published it, and a coverage
            // view that is simply absent looks identical to a corpus that has
            // no mapping at all, which is the same silence this format exists
            // to refuse elsewhere.
            Refusal = $"The coverage mapping at {source} could not be read: {e.Message}";
        }
    }

    /// <summary>
    /// Where the mapping lives, or why there is none to fetch.
    ///
    /// <para>
    /// Two sources, in order. <c>?coverage=&lt;url&gt;</c> first, so one
    /// published copy of the browser can read a mapping that was not published
    /// with the corpus, which is the same argument <c>?catalogue=</c> already
    /// won. The catalogue's own <c>coverage</c> field second, so a corpus that
    /// has a mapping needs no query string to show it.
    /// </para>
    ///
    /// <para>
    /// Both resolve against the catalogue's url rather than the app's base, and
    /// that is one rule rather than two on purpose. The catalogue is the
    /// document that names a corpus's parts, so its own location is the only
    /// thing they can sensibly be relative to; that is already why a spec
    /// entry's url resolves there. Resolving against the app instead would mean
    /// a remote catalogue could only ever name a mapping on this origin, which
    /// is nobody's mapping.
    /// </para>
    /// </summary>
    private (Uri? Source, string? Refusal) ResolveCoverageUri()
    {
        // The query survives the hash router, and is read here exactly as
        // SpecStore reads its own parameter, including the decode: an absolute
        // url arrives percent-encoded and Uri.Query hands it back that way.
        var declared = HttpUtility.ParseQueryString(new Uri(nav.Uri).Query)[CoverageParameter];
        var source = $"the {CoverageParameter} parameter";

        if (string.IsNullOrWhiteSpace(declared))
        {
            declared = specs.DeclaredCoverageUrl;
            source = "the catalogue";
        }

        if (string.IsNullOrWhiteSpace(declared)) return (null, null);

        var against = CatalogueLocation();
        if (against is null)
            return (null, "A coverage mapping was named, but the catalogue it would be "
                          + "read alongside could not be located, so there is nothing to "
                          + "resolve it against or to check it against.");

        // The url is quoted back in every refusal below, and which of the two
        // sources it came from is said as well. A reader who did not write
        // either one has to be told where the value they are being refused
        // actually came from, and those two are fixed by different people.
        if (!Uri.TryCreate(against, declared.Trim(), out var wanted))
            return (null, $"The coverage mapping url \"{declared}\", named by {source}, "
                          + "is not a url this can resolve.");

        // http(s) only, and refused for the reason SpecStore refuses the same
        // schemes: a data: url is fetchable, so without this a crafted link
        // could carry an entire coverage mapping inside itself with no server in
        // the address bar to hold responsible for what it claims. Pointing the
        // browser at another host is the feature; pointing it at the link is not.
        // It carries further here than it does there, because a mapping is a
        // claim about somebody else's corpus rather than about its own.
        if (wanted.Scheme is not ("http" or "https"))
            return (null, $"The coverage mapping url \"{declared}\", named by {source}, "
                          + "must be an http or https URL.");

        return (wanted, null);
    }

    /// <summary>
    /// The catalogue this session read, or null when it cannot be named.
    ///
    /// Guarded rather than propagated: a refused catalogue url throws from
    /// <see cref="SpecStore.CatalogueUri"/>, and the shell has already rendered
    /// its error page for that. Null travels on into the agreement check, which
    /// treats "cannot compare" as a refusal, so the guard cannot turn into a
    /// pass by accident.
    /// </summary>
    private Uri? CatalogueLocation()
    {
        try { return specs.CatalogueUri; }
        catch (Exception e) when (e is InvalidOperationException or UriFormatException) { return null; }
    }
}
