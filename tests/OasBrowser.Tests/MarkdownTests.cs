using OasBrowser.Rendering;
using Xunit;

namespace OasBrowser.Tests;

/// <summary>
/// What a description renders as.
///
/// <para>
/// <b>This suite is one half of a two-party contract, and it is the half that
/// was owed.</b> A corpus ships cross-spec <c>spec:&lt;id&gt;</c> links and runs
/// its own checker proving those links resolve against its own data. That
/// checker cannot see this browser at all, so it stays green while every link
/// it validated 404s, because the vocabulary is honoured here and enforced
/// there. A corpus's green is evidence about its data; this file is the
/// evidence that the browser still translates what the data says.
/// </para>
///
/// <para>
/// The rest is the safety surface. Descriptions were first-party content while
/// the browser read one corpus out of the repository that generated it. A
/// browser that loads a catalogue from a URL renders arbitrary third-party
/// text into the DOM on its own origin, and that change arrives as a
/// consequence of the extraction rather than as a change anyone makes. Every
/// case below is a defect that was found the hard way rather than a hazard
/// somebody imagined.
/// </para>
/// </summary>
public class MarkdownTests
{
    // ---- the cross-spec vocabulary, which is the contract itself -----------

    [Theory]
    [InlineData("athena")]
    [InlineData("bapi")]
    [InlineData("powerapps")]
    public void A_bare_spec_reference_is_an_in_app_link(string id)
    {
        // The only form any corpus ships today, and the reason this file
        // exists. If this stops resolving, the corpus-side checker still
        // passes and every published cross-spec link lands nowhere.
        Assert.Equal(
            $"<a href=\"#/{id}\">the other spec</a>",
            Markdown.ToHtml($"[the other spec](spec:{id})"));
    }

    [Fact]
    public void The_spec_scheme_is_matched_without_regard_to_case()
    {
        // A scheme is case insensitive everywhere else, so a corpus author has
        // no reason to expect this one is not. Matching only the lowercase
        // spelling would refuse a link that is correct by every rule the
        // contract states.
        Assert.Equal("<a href=\"#/athena\">x</a>", Markdown.ToHtml("[x](SPEC:athena)"));
    }

    [Fact]
    public void A_spec_id_needing_escaping_still_resolves()
    {
        // The id comes from a corpus, not from this app, so it is not
        // guaranteed to be URL safe. Emitting it raw would produce a link that
        // parses back as a different route.
        Assert.Equal("<a href=\"#/a%3Fb\">x</a>", Markdown.ToHtml("[x](spec:a?b)"));

        // And it is a literal name rather than a pre-encoded URL, so a percent
        // in it is a percent. Treating the reference as already encoded would
        // make an id containing one resolve somewhere else.
        Assert.Equal("<a href=\"#/a%2520b\">x</a>", Markdown.ToHtml("[x](spec:a%20b)"));
    }

    // ---- the fragment forms, which are unresolved and not refused ----------

    [Theory]
    [InlineData("spec:athena#/operations/getCluster")]
    [InlineData("spec:athena#/schemas/Organization")]
    [InlineData("spec:athena#/resources/environments")]
    public void A_fragment_reference_renders_as_unresolved(string href)
    {
        var html = Markdown.ToHtml($"[x]({href})");

        // Documented in the contract with no live consumer, so it must not
        // become a link: translating it would ship a surface whose first test
        // is the first link somebody writes.
        Assert.Contains("link-unresolved", html);
        Assert.Contains("[unresolved reference]", html);
        Assert.DoesNotContain("<a ", html);

        // And it must not say "refused". A safety refusal and an unimplemented
        // contract are different facts, and asserting the first invites a
        // reader to conclude the corpus did something wrong when the corpus is
        // correct and the browser is the part that cannot do it yet. The specs
        // owner made exactly that point when it was reported.
        Assert.DoesNotContain("link-refused", html);
        Assert.DoesNotContain("[refused link]", html);
    }

    // ---- refused schemes ---------------------------------------------------

    [Theory]
    [InlineData("javascript:alert(1")]
    [InlineData("JaVaScRiPt:alert(1")]
    [InlineData("java\0script:alert(1")]
    [InlineData("data:text/html;base64,PHNjcmlwdD4=")]
    [InlineData("vbscript:msgbox")]
    public void An_executable_scheme_gets_no_href(string href)
    {
        var html = Markdown.ToHtml($"[the cataloguing guide]({href})");

        // The href is the whole risk: a marker that still emitted one would
        // look like a refusal and behave like a link. The case folded and
        // NUL-interior spellings are here because a browser ignores both when
        // it reads a scheme, so judging the target as written would be
        // decoration rather than a check.
        Assert.DoesNotContain("href", html);
        Assert.DoesNotContain("<a ", html);
        Assert.Contains("link-refused", html);
        Assert.Contains("[refused link]", html);
    }

    [Fact]
    public void A_refused_scheme_is_named_back_only_when_it_looks_like_one()
    {
        // The refused name lands in a title attribute, so what may appear there
        // has to be bounded by this check rather than by whatever the
        // description happened to contain.
        Assert.Contains("does not follow javascript: links", Markdown.ToHtml("[x](javascript:alert(1)"));
        Assert.Contains("does not follow unrecognised links", Markdown.ToHtml("[x](ja\"va:script)"));

        // The obfuscated spellings must be refused *as javascript*, which is
        // the assertion that the target was folded and stripped before the
        // scheme was read. Refusing them as "unrecognised" looks identical from
        // the outside and means the check never recognised the scheme at all,
        // so the allow-list is carrying the whole result and the normalisation
        // this file documents is decoration. Added because removing either the
        // case fold or the control strip left the suite green.
        Assert.Contains("does not follow javascript: links", Markdown.ToHtml("[x](JaVaScRiPt:alert(1)"));
        Assert.Contains("does not follow javascript: links", Markdown.ToHtml("[x](java\0script:alert(1)"));
    }

    // ---- attribute breakout, once per branch that writes an attribute ------
    //
    // The link pattern's target group cannot contain whitespace or a closing
    // bracket, and the escape pass at the top of ToHtml covers & < and > but
    // not the double quote. A quote closes the attribute, and a browser starts
    // a new attribute at the next character whether or not whitespace follows,
    // so no space is needed to inject one.
    //
    // Every branch is tested rather than the one that was reported, because the
    // commit that fixed the first branch reintroduced the identical bug one
    // branch over. The pull that produced a defect usually produced more than
    // one instance, and here the second instance was produced by the fix for
    // the first.

    [Fact]
    public void The_spec_branch_writes_no_extra_attribute()
    {
        // Two guards stand behind this one assertion and only one of them is
        // in this file. Measured rather than assumed: taking the attribute
        // escape off this branch leaves the suite green, because Route
        // percent-escapes the id when it writes the hash and no id can reach
        // the attribute carrying a quote. Taking Route's escaping off turns
        // this red instead. So what is pinned here is the composition, the
        // escape on this branch is the guard for a Route that stopped
        // escaping, and this is the one of the four branches where a lone
        // mistake in this file is not observable. Worth knowing, because a
        // reader would otherwise assume all four are equally covered.
        var html = Markdown.ToHtml("[x](spec:athena\"z)");
        Assert.Equal(new[] { "href" }, AttributeNames(html));
        Assert.Equal("<a href=\"#/athena%22z\">x</a>", html);
    }

    [Fact]
    public void The_unresolved_branch_writes_no_extra_attribute()
    {
        // This branch interpolates the raw target into a title, and it is the
        // branch that reintroduced the bug: it was written after the fix and
        // was not covered by it.
        var html = Markdown.ToHtml("[x](spec:athena#/operations/a\"z)");
        Assert.Equal(new[] { "class", "title" }, AttributeNames(html));
        Assert.Contains("spec:athena#/operations/a&quot;z", html);
    }

    [Fact]
    public void The_refused_branch_writes_no_extra_attribute()
    {
        // Nothing here goes through the escape, so what keeps the attribute
        // closed is that the scheme name is only echoed when it is shaped like
        // one. Loosen that and the target reaches the title raw.
        var html = Markdown.ToHtml("[x](ja\"va:script)");
        Assert.Equal(new[] { "class", "title" }, AttributeNames(html));
        Assert.DoesNotContain("ja\"va", html);
    }

    [Fact]
    public void The_plain_link_branch_writes_no_extra_attribute()
    {
        // The originally reported instance. An href is the easiest of the four
        // to reach, because the target is copied through untouched.
        var html = Markdown.ToHtml("[x](https://example.invalid/a\"z)");
        Assert.Equal(new[] { "href", "target", "rel" }, AttributeNames(html));
        Assert.Equal(
            "<a href=\"https://example.invalid/a&quot;z\" target=\"_blank\" rel=\"noopener\">x</a>",
            html);
    }

    [Fact]
    public void The_in_app_hash_branch_writes_no_extra_attribute()
    {
        // The fourth branch, and the one most likely to be thought safe on the
        // grounds that a hash link never leaves the app. Where the link goes
        // has nothing to do with whether the attribute stays closed.
        var html = Markdown.ToHtml("[x](#/schemas/A\"z)");
        Assert.Equal(new[] { "href" }, AttributeNames(html));
        Assert.Equal("<a href=\"#/schemas/A&quot;z\">x</a>", html);
    }

    /// <summary>
    /// The attribute names of the first tag in <paramref name="html"/>, read
    /// the way a browser reads them: a quoted value ends at its closing quote,
    /// and whatever follows begins a new attribute whether or not whitespace
    /// separates them. Counting quotes would not distinguish a closed attribute
    /// from a smuggled one, which is the only thing these tests care about.
    /// </summary>
    private static string[] AttributeNames(string html)
    {
        var i = html.IndexOf('<') + 1;
        while (i < html.Length && !char.IsWhiteSpace(html[i]) && html[i] != '>') i++;

        var names = new List<string>();
        while (i < html.Length && html[i] != '>')
        {
            while (i < html.Length && char.IsWhiteSpace(html[i])) i++;
            if (i >= html.Length || html[i] == '>') break;

            var start = i;
            while (i < html.Length && html[i] != '=' && html[i] != '>' && !char.IsWhiteSpace(html[i])) i++;
            names.Add(html[start..i]);

            if (i >= html.Length || html[i] != '=') continue;
            i++;

            if (i < html.Length && (html[i] == '"' || html[i] == '\''))
            {
                var quote = html[i++];
                while (i < html.Length && html[i] != quote) i++;
                i++;
            }
            else
            {
                while (i < html.Length && html[i] != '>' && !char.IsWhiteSpace(html[i])) i++;
            }
        }
        return names.ToArray();
    }

    // ---- raw HTML in a description -----------------------------------------

    [Theory]
    [InlineData("<script>window.__fired = true;</script>")]
    [InlineData("<script src=\"https://example.invalid/payload.js\"></script>")]
    [InlineData("<img src=x onerror=\"window.__fired=true\">")]
    [InlineData("<div onmouseover=\"window.__fired=true\">hover me</div>")]
    [InlineData("An unclosed tag that swallows what follows: <div title=\"")]
    public void Markup_in_a_description_is_text_and_never_an_element(string description)
    {
        // The escape pass runs before anything else, so the only markup in the
        // output is markup this file wrote. Asserting on the absence of the
        // delimiter rather than on the absence of "<script" is what makes this
        // hold for the tag nobody thought of.
        Assert.DoesNotContain("<", Markdown.ToHtml(description));
    }

    [Fact]
    public void An_unclosed_attribute_cannot_swallow_what_follows_it()
    {
        // A description that ran past its own end would consume the page around
        // it, and the damage would show up as a missing section somewhere else
        // rather than as anything wrong with this description.
        var html = Markdown.ToHtml("<div title=\" and this sentence must still be readable.");
        Assert.Contains("and this sentence must still be readable.", html);
        Assert.DoesNotContain("<", html);
    }

    // ---- the legitimate cases, which are the reason none of this may over correct

    [Theory]
    [InlineData("https://example.invalid/policy")]
    [InlineData("http://example.invalid/policy")]
    [InlineData("mailto:libraries@example.invalid")]
    public void An_allowed_scheme_opens_away_from_the_app(string href)
    {
        // Over correction is the other failure direction and it is silent: a
        // reader sees a marker where a working link belongs and has no way to
        // tell whether the corpus or the browser is at fault.
        Assert.Equal(
            $"<a href=\"{href}\" target=\"_blank\" rel=\"noopener\">the lending policy</a>",
            Markdown.ToHtml($"[the lending policy]({href})"));
    }

    [Theory]
    [InlineData("#/schemas/Organization")]
    [InlineData("#/operations/environments_get")]
    [InlineData("#/athena/resources/environments")]
    public void An_in_app_link_stays_in_the_app(string href)
    {
        // No target and no rel deliberately. A hash link that opened a new tab
        // would reload the whole app to move between two pages of it.
        Assert.Equal($"<a href=\"{href}\">Organization</a>", Markdown.ToHtml($"[Organization]({href})"));
    }

    [Fact]
    public void Code_spans_and_bold_still_render()
    {
        // The three inline forms this renderer supports. They are the whole
        // reason descriptions are not simply escaped and printed.
        Assert.Equal("<code>FI-204</code>", Markdown.ToHtml("`FI-204`"));
        Assert.Equal("<strong>204</strong>", Markdown.ToHtml("**204**"));
    }

    [Fact]
    public void A_code_span_shows_markup_literally()
    {
        // Both failure directions are wrong here and only one is dangerous: the
        // content must be visible and copyable as characters, and must not be
        // parsed. A renderer that stripped it would silently blank a paragraph
        // documenting an HTML payload.
        Assert.Equal(
            "<code>&lt;img src=x onerror=alert(1)&gt;</code>",
            Markdown.ToHtml("`<img src=x onerror=alert(1)>`"));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    public void Nothing_renders_as_nothing(string? description)
    {
        // Most fields carrying a description are optional, so this is the
        // common case rather than an edge one.
        Assert.Equal("", Markdown.ToHtml(description));
    }
}
