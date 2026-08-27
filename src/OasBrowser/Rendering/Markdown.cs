using System.Text;
using System.Text.RegularExpressions;

namespace OasBrowser.Rendering;

/// <summary>
/// Inline markdown only: links, code spans and bold. Anything richer would be a
/// markdown library carried into the browser, and nothing in the descriptions
/// this was written against uses more than these three.
///
/// PENDING GENERALISATION: that was measured over one corpus, whose prose came
/// from a known pair of sources. A spec written elsewhere may well use headings
/// or lists, and this renders their markers literally rather than failing, so
/// the gap is silent. How wide the subset should be for an arbitrary spec is
/// the generalisation pass's call.
/// </summary>
public static partial class Markdown
{
    [GeneratedRegex(@"\[([^\]]+)\]\(([^)\s]+)\)")] private static partial Regex LinkPattern();
    [GeneratedRegex(@"`([^`]+)`")] private static partial Regex CodePattern();
    [GeneratedRegex(@"\*\*([^*]+)\*\*")] private static partial Regex BoldPattern();

    public static string ToHtml(string? text)
    {
        if (string.IsNullOrEmpty(text)) return "";

        var sb = new StringBuilder(text.Length + 32);
        foreach (var c in text)
        {
            switch (c)
            {
                case '&': sb.Append("&amp;"); break;
                case '<': sb.Append("&lt;"); break;
                case '>': sb.Append("&gt;"); break;
                default: sb.Append(c); break;
            }
        }

        var html = sb.ToString();
        html = CodePattern().Replace(html, m => $"<code>{m.Groups[1].Value}</code>");
        html = BoldPattern().Replace(html, m => $"<strong>{m.Groups[1].Value}</strong>");
        html = LinkPattern().Replace(html, m =>
        {
            var label = m.Groups[1].Value;
            var href = m.Groups[2].Value;

            if (!IsFollowable(href, out var refused))
                return $"<span class=\"link-refused\" title=\"Refused: this browser does not follow {refused} links.\">{label} [refused link]</span>";

            // The escape pass above covers & < >, and the href group cannot
            // contain whitespace or a closing bracket. It can contain a quote,
            // which would close the attribute and turn the rest of the target
            // into attributes of this element, so the attribute context needs
            // its own escape.
            var target = href.Replace("\"", "&quot;");

            // in-app hash links stay in the SPA; anything else opens away from it
            return href.StartsWith('#')
                ? $"<a href=\"{target}\">{label}</a>"
                : $"<a href=\"{target}\" target=\"_blank\" rel=\"noopener\">{label}</a>";
        });
        return html;
    }

    /// <summary>
    /// Schemes a link in a description may use. An allow-list, because a
    /// deny-list is a list of the attacks somebody thought of: javascript:,
    /// data: and vbscript: are the ones known today and the set is open.
    /// </summary>
    private static readonly HashSet<string> FollowableSchemes =
        new(StringComparer.Ordinal) { "http", "https", "mailto" };

    [GeneratedRegex(@"^[a-z][a-z0-9+.-]*$")] private static partial Regex SchemeShape();

    /// <summary>
    /// Whether a link target may be emitted as an href, and if not, what to
    /// call the scheme that was refused.
    ///
    /// The judgement is made on the target with control characters removed and
    /// case folded, because a browser ignores both when it reads a scheme: a
    /// target written "Java&#9;SCRIPT:" reaches the URL parser as "javascript:".
    /// Comparing the target as written would be decoration rather than a check.
    ///
    /// A target with no scheme is followable. Relative links are ordinary
    /// content and cannot name an executable scheme, so there is nothing here
    /// to judge them on.
    /// </summary>
    private static bool IsFollowable(string href, out string refused)
    {
        refused = "";

        var normalised = string.Concat(
            href.Where(c => !char.IsWhiteSpace(c) && !char.IsControl(c))).ToLowerInvariant();

        if (normalised.Length == 0) return false;
        if (normalised[0] == '#') return true;

        var colon = normalised.IndexOf(':');
        if (colon < 0) return true;

        // A colon after a slash belongs to a path or a port, not to a scheme.
        var slash = normalised.IndexOf('/');
        if (slash >= 0 && slash < colon) return true;

        var scheme = normalised[..colon];
        if (FollowableSchemes.Contains(scheme)) return true;

        // Named back to the reader only when it is shaped like a scheme, so
        // that what lands in the title attribute is bounded by this check
        // rather than by whatever the description happened to contain.
        refused = SchemeShape().IsMatch(scheme) ? $"{scheme}:" : "unrecognised";
        return false;
    }
}
