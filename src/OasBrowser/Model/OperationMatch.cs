using System.Text;
using System.Text.RegularExpressions;

namespace OasBrowser.Model;

/// <summary>
/// How a coverage mapping's call finds the operation it names.
///
/// <para>
/// This is contract logic, not rendering. It lived in a Razor code block, where
/// the test project cannot reach it, and it is the piece standing between a
/// correct coverage page and a false gap: applying it properly took the count
/// of calls naming no operation from 21 to 5, so sixteen operations would have
/// been reported as having no recorded caller while being both called and
/// documented. That is the exact failure the coverage view exists to prevent,
/// happening inside it.
/// </para>
///
/// <para>
/// A second implementation of the same written rule, in another language,
/// agreed with this one on every number. That is a fact about one afternoon
/// rather than a mechanism, which is why it is here with tests instead.
/// </para>
/// </summary>
public static partial class OperationMatch
{
    [GeneratedRegex(@"\{[^{}]*\}")] private static partial Regex Template();

    /// <summary>
    /// Whether a spec path matches a call path.
    ///
    /// A templated part of a spec segment matches any run of characters within
    /// one call segment. Everything else matches exactly, <b>including case</b>.
    ///
    /// <para>
    /// Both halves are load-bearing and they pull opposite ways. A spec
    /// templating its version where a caller pins one is a spelling convention,
    /// and refusing it reports false gaps by the dozen: 22 operations in one
    /// corpus are versioned that way. A caller spelling a segment in the wrong
    /// case is a defect in the caller, and absorbing it would hide a real bug
    /// inside the one file whose whole job is saying what the code does. Two
    /// live rows in that corpus are exactly that.
    /// </para>
    ///
    /// <para>
    /// Templates match <b>within</b> a segment rather than only as whole
    /// segments, because an OData path spells one as
    /// <c>{entitySetName}({recordId})</c>. Two implementations of the sentence
    /// "a templated segment matches any single literal segment" split on
    /// precisely that, which is how the sentence was discovered to have two
    /// readings. The looser reading is the correct one and the sentence was the
    /// thing at fault.
    /// </para>
    /// </summary>
    public static bool PathMatches(string specPath, string callPath)
    {
        var spec = specPath.Split('/');
        var call = callPath.Split('/');
        if (spec.Length != call.Length) return false;

        for (var i = 0; i < spec.Length; i++)
        {
            if (!Template().IsMatch(spec[i]))
            {
                if (!string.Equals(spec[i], call[i], StringComparison.Ordinal)) return false;
            }
            else if (!Regex.IsMatch(call[i], SegmentPattern(spec[i])))
            {
                return false;
            }
        }

        return true;
    }

    /// <summary>
    /// How specific a path is: the segments it spells out rather than
    /// templating. The tiebreak between candidates, because a catch-all
    /// otherwise shadows every specific path beside it. In one corpus that put
    /// 25 rows on a generic OData handler that names them all.
    /// </summary>
    public static int LiteralSegments(string path) =>
        path.Split('/').Count(segment => !Template().IsMatch(segment));

    /// <summary>
    /// The candidates a call path resolves to, most specific first, filtered to
    /// those tying for most specific.
    ///
    /// One is a resolution. Several is a real ambiguity and is reported rather
    /// than resolved, because picking one would make two consumers of this
    /// contract disagree with nothing to adjudicate between them. None is a
    /// call naming an operation the spec does not carry.
    /// </summary>
    public static IReadOnlyList<T> MostSpecific<T>(IEnumerable<T> candidates, Func<T, string> pathOf)
    {
        var all = candidates.ToList();
        if (all.Count <= 1) return all;

        var best = all.Max(c => LiteralSegments(pathOf(c)));
        return all.Where(c => LiteralSegments(pathOf(c)) == best).ToList();
    }

    /// <summary>
    /// The operation one identity names, or why this spec has none.
    ///
    /// <para>
    /// The decision procedure the two rules above compose into, and the thing a
    /// reader's numbers actually depend on. It has to see the spec's whole
    /// operation set rather than one candidate at a time, because ranking by
    /// literal segments is a comparison between candidates; that is why it
    /// cannot live in <see cref="CoverageMap"/>, which holds the mapping and
    /// not the spec.
    /// </para>
    ///
    /// <para>
    /// A tie is reported rather than resolved, at both steps. Two operations
    /// carrying one operationId, or two paths matching a call equally well, is
    /// the corpus and the mapping failing to determine an answer between them,
    /// and picking one would make this page's figures depend on which
    /// implementation read them.
    /// </para>
    ///
    /// <para>
    /// <b>The seam.</b> This takes an interface over three strings rather than
    /// the app's <c>Operation</c>. Not because <c>OpenApiModel.cs</c> cannot be
    /// compiled into the test project: it can, it is System.Text.Json and
    /// nothing else. It is because an <c>Operation</c> can only be reached
    /// through <c>OpenApiSpec.Parse</c>, so every case below would have to be
    /// written as a spec document, and a rule that reads three strings would be
    /// pinned by tests that also exercise the parser and drag SchemaRef and
    /// SpecNote in behind it. The narrower type is what the rule reads, so it
    /// is what the rule asks for, and <c>Operation</c> satisfies it as it
    /// already stands without an adapter. Generic rather than returning the
    /// interface, so the caller gets its own type back and needs no cast.
    /// </para>
    /// </summary>
    public static (T? Op, string? Why) Resolve<T>(OperationIdentity identity, IEnumerable<T> operations)
        where T : class, ISpecOperation
    {
        // Ordinal, matching the identity: two operationIds differing in case
        // are two operationIds, for the same reason a path segment's case is
        // significant a few lines down.
        if (identity.OperationId is { } id)
        {
            var found = operations.Where(o => string.Equals(o.OperationId, id, StringComparison.Ordinal)).ToList();
            return found.Count switch
            {
                1 => (found[0], null),
                0 => (null, "no operation in this spec has that operationId"),
                _ => (null, $"{found.Count} operations in this spec carry that operationId"),
            };
        }

        // The method is compared case-insensitively and the path is not. A
        // method is a fixed token of the protocol that a spec spells lower case
        // and this model uppercases, so its case carries no information; a path
        // segment's case is the caller's own spelling and carries a defect.
        var candidates = operations
            .Where(o => string.Equals(o.Method, identity.Method, StringComparison.OrdinalIgnoreCase)
                        && PathMatches(o.Path, identity.Path!))
            .ToList();

        if (candidates.Count == 0)
            return (null, "no path in this spec matches it, at that method and that spelling");

        // Most specific wins: a path spending a literal where another spends a
        // template is the one the caller meant. Without this a catch-all
        // shadows every specific path beside it.
        var top = MostSpecific(candidates, o => o.Path);

        return top.Count == 1
            ? (top[0], null)
            : (null, "several paths in this spec match it equally well: "
                     + string.Join(", ", top.Select(o => o.Path).OrderBy(p => p, StringComparer.Ordinal)));
    }

    private static string SegmentPattern(string segment)
    {
        var pattern = new StringBuilder("^");
        var last = 0;

        foreach (Match match in Template().Matches(segment))
        {
            pattern.Append(Regex.Escape(segment[last..match.Index])).Append("[^/]+");
            last = match.Index + match.Length;
        }

        return pattern.Append(Regex.Escape(segment[last..])).Append('$').ToString();
    }
}

/// <summary>
/// An operation of a spec, reduced to the three strings resolving a call reads
/// off it. The whole abstraction: a rule that compares an id, a method and a
/// path should say so in its signature, and the app's <c>Operation</c>
/// implements this as it already stands.
/// </summary>
public interface ISpecOperation
{
    string OperationId { get; }

    /// <summary>Whatever case the spec or the model spells it in; compared case-insensitively.</summary>
    string Method { get; }

    string Path { get; }
}
