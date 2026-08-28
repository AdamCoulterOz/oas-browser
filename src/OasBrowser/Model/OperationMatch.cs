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
