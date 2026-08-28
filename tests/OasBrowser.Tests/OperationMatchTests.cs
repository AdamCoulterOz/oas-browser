using OasBrowser.Model;
using Xunit;

namespace OasBrowser.Tests;

/// <summary>
/// The rule a coverage mapping's call uses to find its operation.
///
/// This is the piece that decides whether the coverage view tells the truth.
/// Applying it properly took the count of calls naming no operation from 21 to
/// 5, so without it sixteen operations render as having no recorded caller
/// while being both called and documented — a false gap, inside the view built
/// to make absence legible.
///
/// It lived in a Razor code block this project could not test, cross-checked
/// once by hand against an implementation in another language. Every case below
/// is from the real corpus rather than invented, because the ones that matter
/// are the ones two implementations of the written sentence disagreed about.
/// </summary>
public class OperationMatchTests
{
    // ---- the convention to absorb -------------------------------------------

    [Theory]
    [InlineData("/api/data/{apiVersion}/EntityDefinitions", "/api/data/v9.2/EntityDefinitions")]
    [InlineData("/api/data/{apiVersion}/publishers", "/api/data/v9.2/publishers")]
    public void A_templated_segment_matches_a_pinned_one(string spec, string call)
    {
        // A corpus templating its version where a caller pins one is a spelling
        // convention, not a mismatch. 22 operations in one corpus are versioned
        // this way, so refusing it reports false gaps by the dozen.
        Assert.True(OperationMatch.PathMatches(spec, call));
    }

    [Fact]
    public void A_template_inside_a_segment_matches()
    {
        // The case that split two implementations of one sentence. "A templated
        // segment matches any single literal segment" reads as whole-segment,
        // and OData spells a template inside a segment. The looser reading is
        // correct and the sentence was what was wrong.
        Assert.True(OperationMatch.PathMatches(
            "/api/data/{apiVersion}/{entitySetName}({recordId})",
            "/api/data/v9.2/systemusers(00000000-0000-0000-0000-000000000000)"));
    }

    // ---- the defect to surface ----------------------------------------------

    [Fact]
    public void Case_is_significant_in_a_literal_segment()
    {
        // A live defect in a real provider: it sends BillingPolicies where the
        // spec says billingPolicies, on the same host, in the same file as five
        // calls that spell it correctly. Absorbing the difference would hide a
        // real bug inside the one file whose whole job is saying what the code
        // does, so this must keep failing until somebody fixes the caller.
        Assert.False(OperationMatch.PathMatches(
            "/licensing/billingPolicies", "/licensing/BillingPolicies"));
        Assert.False(OperationMatch.PathMatches(
            "/licensing/billingPolicies/{billingPolicyId}", "/licensing/BillingPolicies/{billingId}"));
    }

    [Theory]
    [InlineData("/a/b/c", "/a/b")]
    [InlineData("/a/b", "/a/b/c")]
    [InlineData("/api/data/{v}/x", "/api/data/x")]
    public void Segment_counts_must_agree(string spec, string call)
    {
        Assert.False(OperationMatch.PathMatches(spec, call));
    }

    [Fact]
    public void A_template_does_not_span_a_separator()
    {
        // A templated segment stands for one segment, not for a path. Letting
        // it swallow a slash would make a two-segment template match anything
        // below it, which is a catch-all nobody declared.
        Assert.False(OperationMatch.PathMatches("/api/{one}", "/api/a/b"));
    }

    // ---- specificity, which is a contract rule and not an optimisation ------

    [Fact]
    public void The_most_specific_candidate_wins()
    {
        // A corpus that documents a generic OData surface beside specific paths
        // makes the match rule ambiguous: a call matches both, legitimately. On
        // the first real run this shadowed 25 rows behind one catch-all.
        string[] candidates =
        [
            "/api/data/{apiVersion}/{entitySetName}",
            "/api/data/{apiVersion}/publishers",
        ];

        var top = OperationMatch.MostSpecific(candidates, p => p);

        Assert.Single(top);
        Assert.Equal("/api/data/{apiVersion}/publishers", top[0]);
    }

    [Fact]
    public void A_catch_all_alone_still_resolves()
    {
        // It is a real operation, not a fallback. A corpus documenting the
        // generic surface once and nothing specific must still resolve.
        string[] candidates = ["/api/data/{apiVersion}/{entitySetName}"];
        Assert.Single(OperationMatch.MostSpecific(candidates, p => p));
    }

    [Fact]
    public void An_equal_tie_is_reported_rather_than_resolved()
    {
        // Two candidates equally specific is a real ambiguity. Picking one
        // would make two consumers of this contract disagree with nothing to
        // adjudicate between them, so the caller gets both and says so.
        string[] candidates = ["/api/{a}/x", "/api/{b}/x"];
        Assert.Equal(2, OperationMatch.MostSpecific(candidates, p => p).Count);
    }

    [Theory]
    [InlineData("/api/data/{apiVersion}/EntityDefinitions", 4)]
    [InlineData("/api/data/{apiVersion}/{entitySetName}", 3)]
    [InlineData("/connectivity/connectors/{c}/connections/{n}", 4)]
    public void Literal_segments_are_what_specificity_counts(string path, int expected)
    {
        // The empty string before the leading slash counts as a literal. That
        // is harmless because it is constant across every candidate, so it
        // shifts every score by one and changes no ranking.
        //
        // I wrote that sentence and then wrote these numbers one lower, as
        // though the count started after the slash. The test failed and the
        // code was right. Pinned at the real values so a later tidy-up cannot
        // change the ranking while looking like a cleanup, and left with the
        // off-by-one recorded, because knowing a quirk is evidently not the
        // same as applying it.
        Assert.Equal(expected, OperationMatch.LiteralSegments(path));
    }
}
