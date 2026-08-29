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

    // ---- the decision the two rules above compose into -----------------------
    //
    // Resolve is the piece that produces a false gap when it is wrong: an
    // operation reported as having no recorded caller while being both called
    // and documented. Its "why" strings are read by a person in the coverage
    // view's unresolved callout, so they are asserted in full here rather than
    // by their shape.

    /// <summary>
    /// An operation of a spec, as this rule sees one. Three strings, which is
    /// the whole of what the seam asks for and the reason the real
    /// <c>Operation</c> can satisfy it without an adapter.
    /// </summary>
    private sealed record Op(string OperationId, string Method, string Path) : ISpecOperation;

    private static readonly Op Publishers =
        new("publishers_list", "GET", "/api/data/{apiVersion}/publishers");

    [Fact]
    public void An_operation_id_resolves_to_the_operation_carrying_it()
    {
        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ById("publishers_list"), new[] { Publishers });

        Assert.Same(Publishers, op);
        Assert.Null(why);
    }

    [Fact]
    public void An_operation_id_the_spec_does_not_carry_says_so()
    {
        // The common real miss: a mapping written against a corpus that has
        // since renamed or dropped the operation. It is a finding, not an
        // error, so it comes back as words a reader can act on.
        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ById("publishers_delete"), new[] { Publishers });

        Assert.Null(op);
        Assert.Equal("no operation in this spec has that operationId", why);
    }

    [Fact]
    public void An_operation_id_differing_only_in_case_is_a_different_operation_id()
    {
        // Added because a mutation survived: folding case here changed nothing
        // I had written down, which means the rule was only in the dictionary
        // comparer it was lifted from. An operationId is a name the corpus
        // chose, not a protocol token, so the same argument as the path rule
        // applies: a caller spelling it differently is a caller to fix, and
        // absorbing it here would hide that.
        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ById("Publishers_List"), new[] { Publishers });

        Assert.Null(op);
        Assert.Equal("no operation in this spec has that operationId", why);
    }

    [Fact]
    public void One_operation_id_on_two_operations_is_reported_rather_than_picked()
    {
        // Four operationIds in the corpus appear in more than one SPEC, which
        // is fine and is what spec ids are for. Twice within ONE spec should
        // not happen, so this pins what happens if it ever does: the ambiguity
        // is reported, because silently taking the first would make this page's
        // figures depend on the order the paths object was written in.
        Op[] operations =
        [
            new("environments_get", "GET", "/providers/Microsoft.BusinessAppPlatform/environments/{id}"),
            new("environments_get", "GET", "/providers/Microsoft.BusinessAppPlatform/scopes/admin/environments/{id}"),
        ];

        var (op, why) = OperationMatch.Resolve(OperationIdentity.ById("environments_get"), operations);

        Assert.Null(op);
        Assert.Equal("2 operations in this spec carry that operationId", why);
    }

    [Fact]
    public void A_method_and_path_resolve_through_the_versioning_convention()
    {
        // The convention that took the unresolved count from 21 to 5: the spec
        // templates the api-version, the caller pins it.
        var entityDefinitions = new Op(
            "entity_definitions_list", "GET", "/api/data/{apiVersion}/EntityDefinitions");

        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ByPath("GET", "/api/data/v9.2/EntityDefinitions"),
            new[] { entityDefinitions, Publishers });

        Assert.Same(entityDefinitions, op);
        Assert.Null(why);
    }

    [Theory]
    [InlineData("GET")]
    [InlineData("get")]
    [InlineData("Get")]
    public void The_method_is_compared_without_regard_to_case(string spelling)
    {
        // Deliberate, and the opposite of the path rule one test down. A method
        // is a fixed token of the protocol: the spec spells it lower case, this
        // app's model uppercases it, and an identity lowercases it again, so
        // its case says nothing about the caller. Two of those three spellings
        // are live in the app right now, which is why comparing them ordinally
        // would resolve nothing at all.
        var (op, _) = OperationMatch.Resolve(
            OperationIdentity.ByPath(spelling, "/api/data/v9.2/publishers"), new[] { Publishers });

        Assert.Same(Publishers, op);
    }

    [Fact]
    public void A_different_method_at_the_same_path_does_not_resolve()
    {
        // One of the two real misses in the other corpus is exactly this: a
        // PATCH against a path the spec documents at other methods only.
        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ByPath("PATCH", "/api/data/v9.2/publishers"), new[] { Publishers });

        Assert.Null(op);
        Assert.Equal("no path in this spec matches it, at that method and that spelling", why);
    }

    [Fact]
    public void A_path_the_spec_does_not_document_says_so()
    {
        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ByPath("GET", "/api/data/v9.2/nothingLikeThis"), new[] { Publishers });

        Assert.Null(op);
        Assert.Equal("no path in this spec matches it, at that method and that spelling", why);
    }

    [Fact]
    public void A_specific_path_wins_over_a_catch_all_that_also_matches()
    {
        // Both match, legitimately. On the first real run the generic OData
        // handler swallowed 25 rows that name specific operations, so this is
        // a contract rule and not a preference.
        var catchAll = new Op("odata_get", "GET", "/api/data/{apiVersion}/{entitySetName}");

        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ByPath("GET", "/api/data/v9.2/publishers"),
            new[] { catchAll, Publishers });

        Assert.Same(Publishers, op);
        Assert.Null(why);
    }

    [Fact]
    public void Two_equally_specific_paths_are_reported_with_both_named()
    {
        // Named, and in a fixed order, because the reader has to be able to go
        // and look at the two paths that collided. Sorted so the sentence does
        // not depend on the order the spec happened to declare them in.
        Op[] operations =
        [
            new("b", "GET", "/api/{b}/x"),
            new("a", "GET", "/api/{a}/x"),
        ];

        var (op, why) = OperationMatch.Resolve(OperationIdentity.ByPath("GET", "/api/v1/x"), operations);

        Assert.Null(op);
        Assert.Equal(
            "several paths in this spec match it equally well: /api/{a}/x, /api/{b}/x", why);
    }

    [Fact]
    public void A_segment_spelled_in_the_wrong_case_does_not_resolve()
    {
        // The live defect, end to end through the decision rather than through
        // PathMatches alone: the provider sends BillingPolicies where the spec
        // says billingPolicies. These are the two calls the coverage page
        // reports as unresolved today, and they must keep being reported. A
        // reader seeing them go quiet would read it as the caller being fixed.
        var billingPolicies = new Op("billing_policies_list", "GET", "/licensing/billingPolicies");

        var (op, why) = OperationMatch.Resolve(
            OperationIdentity.ByPath("GET", "/licensing/BillingPolicies"), new[] { billingPolicies });

        Assert.Null(op);
        Assert.Equal("no path in this spec matches it, at that method and that spelling", why);
    }
}
