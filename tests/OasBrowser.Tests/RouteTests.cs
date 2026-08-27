using OasBrowser.Services;
using Xunit;

namespace OasBrowser.Tests;

/// <summary>
/// The URL contract.
///
/// This is the surface other people's links are written against, so it is
/// tested rather than reasoned about. Nine of ten specs were undeep-linkable
/// before the spec dimension existed, and nothing failed: a link resolved
/// against the first catalogue entry and rendered a page that looked correct.
/// A bug in here does not throw.
/// </summary>
public class RouteTests
{
    // ---- bare forms, which are what every already-published link uses -------

    [Theory]
    [InlineData("")]
    [InlineData("#")]
    [InlineData("#/")]
    [InlineData(null)]
    public void Empty_is_the_overview_with_no_spec(string? hash)
    {
        var r = Route.Parse(hash);
        Assert.Equal(RouteKind.Overview, r.Kind);
        Assert.Null(r.SpecId);
        Assert.Null(r.Id);
    }

    [Theory]
    [InlineData("#/operations/environments_get", RouteKind.Operation, "environments_get")]
    [InlineData("#/schemas/Organization", RouteKind.Schema, "Organization")]
    [InlineData("#/resources/environments", RouteKind.Resource, "environments")]
    public void Bare_forms_keep_working_and_name_no_spec(string hash, RouteKind kind, string id)
    {
        var r = Route.Parse(hash);
        Assert.Equal(kind, r.Kind);
        Assert.Equal(id, r.Id);

        // The whole compatibility story. A published link that predates the
        // spec dimension must still parse, and must resolve against whatever
        // the catalogue declares as default rather than against position.
        Assert.Null(r.SpecId);
    }

    // ---- qualified forms ---------------------------------------------------

    [Theory]
    [InlineData("#/athena/operations/getCluster", "athena", RouteKind.Operation, "getCluster")]
    [InlineData("#/bapi/schemas/Organization", "bapi", RouteKind.Schema, "Organization")]
    [InlineData("#/ppapi/resources/environments", "ppapi", RouteKind.Resource, "environments")]
    public void Qualified_forms_carry_the_spec(string hash, string spec, RouteKind kind, string id)
    {
        var r = Route.Parse(hash);
        Assert.Equal(spec, r.SpecId);
        Assert.Equal(kind, r.Kind);
        Assert.Equal(id, r.Id);
    }

    [Fact]
    public void A_spec_id_alone_is_that_specs_overview()
    {
        // This is what a bare `spec:<id>` cross-spec reference resolves to, and
        // all ten links shipped in the corpus today are that form.
        var r = Route.Parse("#/powerapps");
        Assert.Equal("powerapps", r.SpecId);
        Assert.Equal(RouteKind.Overview, r.Kind);
        Assert.Null(r.Id);
    }

    [Fact]
    public void A_spec_followed_by_a_non_kind_keeps_the_spec()
    {
        // Not a route this app writes. The spec is the part that could be read,
        // and discarding it would send the reader to a different spec's
        // overview, which is the silent substitution this change exists to stop.
        var r = Route.Parse("#/athena/nonsense/x");
        Assert.Equal("athena", r.SpecId);
        Assert.Equal(RouteKind.Overview, r.Kind);
    }

    // ---- round trips -------------------------------------------------------

    [Theory]
    [InlineData("#/")]
    [InlineData("#/operations/environments_get")]
    [InlineData("#/schemas/Organization")]
    [InlineData("#/resources/environments")]
    [InlineData("#/athena/operations/getCluster")]
    [InlineData("#/bapi/schemas/Organization")]
    [InlineData("#/ppapi/resources/environments")]
    [InlineData("#/powerapps")]
    public void Parse_and_ToHash_round_trip(string hash)
    {
        Assert.Equal(hash, Route.Parse(hash).ToHash());
    }

    [Fact]
    public void A_route_has_exactly_one_spelling()
    {
        // "#/athena/" and "#/athena" parse identically, so emitting the first
        // would put two spellings of one location into other people's links and
        // make them look like different pages. Found by rendering a real
        // cross-spec link rather than by the round trip above, which only ever
        // fed itself hashes it already wrote.
        Assert.Equal("#/athena", new Route(RouteKind.Overview, null, "athena").ToHash());
        Assert.Equal(Route.Parse("#/athena"), Route.Parse("#/athena/"));
    }

    [Theory]
    [InlineData("environments (preview)")]
    [InlineData("a/b")]
    [InlineData("100%")]
    [InlineData("a?b#c")]
    public void Ids_needing_escaping_survive_a_round_trip(string id)
    {
        // Every kind escapes now. Resources always did; operations and schemas
        // did not, so an id containing a slash or a hash produced a URL that
        // parsed back as something else.
        foreach (var kind in new[] { RouteKind.Operation, RouteKind.Schema, RouteKind.Resource })
        {
            var round = Route.Parse(new Route(kind, id, "athena").ToHash());
            Assert.Equal(id, round.Id);
            Assert.Equal(kind, round.Kind);
            Assert.Equal("athena", round.SpecId);
        }
    }

    [Fact]
    public void A_spec_id_needing_escaping_survives_a_round_trip()
    {
        var round = Route.Parse(new Route(RouteKind.Operation, "op", "a b/c").ToHash());
        Assert.Equal("a b/c", round.SpecId);
        Assert.Equal("op", round.Id);
    }

    [Fact]
    public void Unescaped_legacy_links_still_parse()
    {
        // A link published before ids were escaped contains the raw character.
        // Unescaping a string with no percent sequences is the identity, so
        // these keep working; the change is only in what the app now writes.
        Assert.Equal("get(one)", Route.Parse("#/operations/get(one)").Id);
    }

    // ---- the reserved set, which the corpus check depends on ---------------

    [Fact]
    public void Reserved_ids_are_derived_from_the_kinds_that_exist()
    {
        // A corpus conformance check reads this rather than restating the
        // words. If a kind is ever added and this list does not grow with it,
        // that check silently stops protecting the new segment.
        //
        // "coverage" joined them when the coverage view got a route, and this
        // assertion is what said so: it went red on the segment table changing,
        // which is exactly the notice a corpus needs that an id it was allowed
        // to use yesterday is spoken for today.
        Assert.Equal(
            new[] { "operations", "schemas", "resources", "coverage" }.OrderBy(x => x),
            Route.ReservedIds.OrderBy(x => x));
    }

    [Theory]
    [InlineData("operations")]
    [InlineData("schemas")]
    [InlineData("resources")]
    [InlineData("coverage")]
    public void A_spec_id_colliding_with_a_kind_is_unreachable(string reserved)
    {
        // Demonstrates why the reserved set has to be enforced on a corpus
        // rather than merely documented: the URL cannot express such a spec, so
        // it is not a style rule, it is an ambiguity.
        var r = Route.Parse($"#/{reserved}");
        Assert.Null(r.SpecId);
        Assert.Equal(RouteKind.Overview, r.Kind);
        Assert.Contains(reserved, Route.ReservedIds);
    }
}
