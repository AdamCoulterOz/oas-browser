
namespace OasBrowser.Services;

/// <summary>
/// Where the app is: which spec, and which operation or schema in it.
///
/// Routing is hash based deliberately. A static host needs no rewrite rules for
/// it, and a hash URL survives the app being deployed at any path.
///
/// <para>
/// <b>The URL names the spec.</b> It did not until this was written, and that
/// was a broken contract rather than a missing feature: every link resolved
/// against the first catalogue entry, so nine of ten specs could not be deep
/// linked at all and a shared link silently returned the reader to spec zero.
/// An earlier version of this comment argued the bare shape was a commitment
/// because deep links had been published against it. Those links resolved for
/// the first spec and for nothing else, so the compatibility surface is exactly
/// the bare form, which still works and still resolves to the declared default.
/// Fidelity to broken behaviour is not compatibility.
/// </para>
///
/// <para>
/// <see cref="SpecId"/> is last and optional because in-page navigation means
/// "this, in the spec I am looking at". The shell attaches the current spec
/// when it writes the URL, so a nav-tree click does not have to know where it
/// is.
/// </para>
/// </summary>
public readonly record struct Route(RouteKind Kind, string? Id, string? SpecId = null)
{
    public static readonly Route Overview = new(RouteKind.Overview, null);

    /// <summary>
    /// The one mapping between a kind and its URL segment. Everything else that
    /// needs either derives it from here, including <see cref="ReservedIds"/>,
    /// so adding a kind cannot leave a second list behind.
    /// </summary>
    private static readonly (RouteKind Kind, string Segment)[] Segments =
    [
        (RouteKind.Operation, "operations"),
        (RouteKind.Schema, "schemas"),
        (RouteKind.Resource, "resources"),
    ];

    /// <summary>
    /// Spec ids a catalogue may not use, because the first path segment is read
    /// as a spec id unless it is one of these. Derived rather than listed: a
    /// corpus conformance check should read this rather than restate it, or the
    /// restatement goes stale the moment a kind is added.
    /// </summary>
    public static readonly string[] ReservedIds = Segments.Select(s => s.Segment).ToArray();

    private static RouteKind? KindOf(string segment) =>
        Segments.FirstOrDefault(s => s.Segment == segment) is { Segment: not null } m ? m.Kind : null;

    /// <summary>
    /// Parses a location hash.
    ///
    /// <code>
    /// #/                          the default spec's overview
    /// #/&lt;specId&gt;                 that spec's overview
    /// #/&lt;kind&gt;/&lt;id&gt;              bare: resolved against the default spec
    /// #/&lt;specId&gt;/&lt;kind&gt;/&lt;id&gt;     fully qualified
    /// </code>
    ///
    /// The first segment is a spec id unless it names a kind, which is why a
    /// spec may not be called <c>operations</c>, <c>schemas</c> or
    /// <c>resources</c>.
    /// </summary>
    public static Route Parse(string? hash)
    {
        var h = (hash ?? "").TrimStart('#').Trim('/');
        if (h.Length == 0) return Overview;

        var parts = h.Split('/', 3);

        // Bare form: the first segment is a kind, so there is no spec in the URL.
        if (KindOf(parts[0]) is { } bareKind)
            return parts.Length > 1
                ? new Route(bareKind, Uri.UnescapeDataString(parts[1]))
                : Overview;

        var specId = Uri.UnescapeDataString(parts[0]);

        // A spec id on its own is that spec's overview. This is what a bare
        // `spec:<id>` cross-spec reference resolves to.
        if (parts.Length == 1) return new Route(RouteKind.Overview, null, specId);

        if (KindOf(parts[1]) is { } kind && parts.Length > 2)
            return new Route(kind, Uri.UnescapeDataString(parts[2]), specId);

        // A spec followed by something that is not a kind is not a route this
        // app writes. Land on that spec's overview rather than the default's:
        // the spec is the part we could read, and discarding it would send the
        // reader somewhere they did not ask for.
        return new Route(RouteKind.Overview, null, specId);
    }

    public string ToHash()
    {
        var kind = Kind;   // a lambda in a struct cannot reach `this`
        var segment = Segments.FirstOrDefault(s => s.Kind == kind).Segment;
        var spec = SpecId is null ? null : Uri.EscapeDataString(SpecId);

        // One spelling per route. An overview carrying a spec is "#/athena",
        // not "#/athena/": both parse the same, and emitting the second would
        // put two spellings of one location into other people's links.
        return (spec, segment is null || Id is null ? null : $"{segment}/{Uri.EscapeDataString(Id)}") switch
        {
            (null, null) => "#/",
            (null, var tail) => $"#/{tail}",
            (var s, null) => $"#/{s}",
            var (s, tail) => $"#/{s}/{tail}",
        };
    }
}

public enum RouteKind { Overview, Operation, Schema, Resource }
