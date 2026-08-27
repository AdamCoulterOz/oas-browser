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
            // in-app hash links stay in the SPA; anything else opens away from it
            return href.StartsWith('#')
                ? $"<a href=\"{href}\">{label}</a>"
                : $"<a href=\"{href}\" target=\"_blank\" rel=\"noopener\">{label}</a>";
        });
        return html;
    }
}
