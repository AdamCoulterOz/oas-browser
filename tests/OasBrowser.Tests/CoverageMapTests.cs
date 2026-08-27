using OasBrowser.Model;
using OasBrowser.Services;
using Xunit;

namespace OasBrowser.Tests;

/// <summary>
/// Reading a coverage mapping, and refusing to read one that is about another
/// corpus.
///
/// <para>
/// <b>The refusal is why this file exists.</b> A mapping names the catalogue it
/// was written against, and there is exactly one way this feature fails
/// invisibly: a mapping for corpus A rendered against corpus B. Every spec id
/// resolves, every item lists, every count is plausible, and all of it is about
/// an API the reader is not looking at. Nothing is missing on screen, so no
/// reader can catch it, and those are precisely the figures somebody then quotes
/// in a decision. A bug in here does not throw and does not look wrong.
/// </para>
///
/// <para>
/// <c>CoverageStore</c> is not exercised here and cannot be: it needs
/// <c>NavigationManager</c> and <c>HttpClient</c>, so compiling it into this
/// project would drag Blazor and the private keel feed into a test run that
/// proves nothing about either. The check itself was put in
/// <see cref="CoverageReading"/>, in the model, for exactly that reason: the one
/// thing here that must not be got wrong is the one thing a test project with no
/// Blazor in it can reach. What is left untested is the plumbing that finds the
/// url, which is the half whose failures are visible.
/// </para>
///
/// <para>
/// The authority on this format is <c>tools/validate_coverage.py</c>, which runs
/// in the producer's CI. This is a reader rather than a second checker: where a
/// document breaks a rule that checker enforces, the cases below pin what a
/// reader does with it rather than asserting a rejection that happens elsewhere.
/// </para>
/// </summary>
public class CoverageMapTests
{
    private const string Catalogue = "https://example.invalid/corpus/specs.json";

    /// <summary>
    /// Deliberately not minimal. It carries both ways of naming an operation, an
    /// entrypoint, an api version, an approximate flag, a note, a source line,
    /// an uncatalogued entry, two grades and two items sharing one operation, so
    /// that a case below changing one thing leaves the rest exercised.
    /// </summary>
    private const string Mapping = """
    {
      "catalogue": "https://example.invalid/corpus/specs.json",
      "grades": {
        "observed": "observed",
        "vocabulary": [
          {"id": "observed", "title": "Observed in recorded traffic",
           "caveat": "Seen on the wire.", "tone": "strong"},
          {"id": "derived", "title": "Derived from source",
           "caveat": "Read out of the implementation."}
        ]
      },
      "artifacts": {
        "kind": "provider component",
        "kinds": {"resource": "Resource", "datasource": "Data source"},
        "entrypoints": {"create": "Create", "delete": "Delete"}
      },
      "uncatalogued": {"polled-location": "Polled from a Location header"},
      "items": [
        {
          "id": "resource:powerplatform_environment",
          "kind": "resource",
          "name": "powerplatform_environment",
          "source": {"path": "internal/services/environment/resource.go", "line": 412},
          "calls": [
            {"spec": "ppapi", "operation": "environments_get", "coverage": "full",
             "grade": "observed", "entrypoint": "create", "apiVersion": "2023-06-01"},
            {"spec": "bapi", "method": "GET", "path": "/v1/environments",
             "coverage": "partial", "grade": "derived", "approximate": true,
             "note": "Only when the location changed."}
          ],
          "uncatalogued": [
            {"reason": "polled-location", "count": 3,
             "note": "Polled until the operation reports done."}
          ]
        },
        {
          "id": "datasource:powerplatform_environments",
          "kind": "datasource",
          "name": "powerplatform_environments",
          "calls": [
            {"spec": "ppapi", "operation": "environments_get",
             "coverage": "full", "grade": "derived"}
          ]
        }
      ]
    }
    """;

    /// <summary>Reads a mapping that is expected to be admitted.</summary>
    private static CoverageMap Read(string json, string loaded = Catalogue)
    {
        var reading = CoverageReading.Read(json, new Uri(loaded));
        Assert.Null(reading.Refusal);
        Assert.NotNull(reading.Map);
        return reading.Map;
    }

    // ---- the whole document ------------------------------------------------

    [Fact]
    public void A_full_document_parses_every_declaration_it_carries()
    {
        var map = Read(Mapping);

        // Each of these is a vocabulary the document declares and the browser
        // does not know. If any of them stops being read, the view renders an
        // id where a label belongs, which reads as a producer's bad data rather
        // than as this parser dropping a field.
        Assert.Equal("provider component", map.ArtifactKind);
        Assert.Equal("Resource", map.Kinds["resource"]);
        Assert.Equal("Data source", map.Kinds["datasource"]);
        Assert.Equal("Create", map.Entrypoints["create"]);
        Assert.Equal("Polled from a Location header", map.UncataloguedReasons["polled-location"]);
        Assert.Equal(Catalogue, map.Declares);

        Assert.Equal(2, map.Items.Count);
        var item = map.Items[0];
        Assert.Equal("resource:powerplatform_environment", item.Id);
        Assert.Equal("resource", item.Kind);
        Assert.Equal("powerplatform_environment", item.Name);
        Assert.Equal("internal/services/environment/resource.go", item.Source?.Path);
        Assert.Equal(412, item.Source?.Line);

        // The uncatalogued sibling of calls. It is the field that stops a
        // coverage view asserting completeness the data never earned, so a
        // silent failure to parse it is the exact failure it exists to prevent.
        var uncatalogued = Assert.Single(item.Uncatalogued);
        Assert.Equal("polled-location", uncatalogued.Reason);
        Assert.Equal(3, uncatalogued.Count);
        Assert.Equal("Polled until the operation reports done.", uncatalogued.Note);

        // Per-call annotations. `approximate` is the producer saying it could
        // not resolve this row with certainty, and a view that cannot see it
        // presents a guess with the same confidence as an observation.
        var byPath = item.Calls[1];
        Assert.Equal("partial", byPath.Coverage);
        Assert.Equal("derived", byPath.Grade);
        Assert.True(byPath.Approximate);
        Assert.Equal("Only when the location changed.", byPath.Note);
        Assert.Equal("2023-06-01", item.Calls[0].ApiVersion);
        Assert.Equal("create", item.Calls[0].Entrypoint);
    }

    [Fact]
    public void Every_optional_field_may_be_absent_without_throwing()
    {
        // A mapping is somebody else's file and the optional fields really are
        // optional: no entrypoints, no uncatalogued reasons, no source, no note,
        // no api version, no approximate flag. Throwing on any of these would
        // take the whole view off screen for a document the conformance checker
        // passes, which is the reader-side version of a check that rejects
        // correct data.
        var map = Read("""
        {
          "catalogue": "https://example.invalid/corpus/specs.json",
          "grades": {"observed": "observed",
                     "vocabulary": [{"id": "observed", "title": "T", "caveat": "C"}]},
          "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
          "items": [
            {"id": "one", "kind": "resource", "name": "one",
             "calls": [{"spec": "ppapi", "operation": "get_thing",
                        "coverage": "full", "grade": "observed"}]}
          ]
        }
        """);

        var item = Assert.Single(map.Items);
        Assert.Null(item.Source);
        Assert.Empty(item.Uncatalogued);
        Assert.Empty(map.Entrypoints);
        Assert.Empty(map.UncataloguedReasons);

        var call = Assert.Single(item.Calls);
        Assert.Null(call.Note);
        Assert.Null(call.ApiVersion);
        Assert.Null(call.Entrypoint);
        Assert.Null(call.Approximate);

        // And the query surface still answers rather than throwing, which is
        // what a view calls before it knows any of the above.
        Assert.Single(map.Callers("ppapi", OperationIdentity.ById("get_thing")));
        Assert.Empty(map.Callers("ppapi", OperationIdentity.ById("nothing_calls_this")));
        Assert.Empty(map.CalledOperations("no-such-spec"));
    }

    // ---- grades ------------------------------------------------------------

    [Fact]
    public void Grade_order_is_position_in_the_declared_array()
    {
        var map = Read(Mapping);

        Assert.Equal(["observed", "derived"], map.Grades.Select(g => g.Id));
        Assert.Equal(0, map.RankOf("observed"));
        Assert.Equal(1, map.RankOf("derived"));

        // An id the document does not declare has no rank at all rather than a
        // rank of zero. Zero would sort an undeclared grade above every declared
        // one, which is a strong claim invented out of a missing declaration.
        Assert.Null(map.RankOf("attested"));
        Assert.Null(map.Grade("attested"));
        Assert.Equal("Observed in recorded traffic", map.Grade("observed")?.Title);
        Assert.Equal("strong", map.Grade("observed")?.Tone);
    }

    [Fact]
    public void A_retired_order_key_does_not_move_a_grade()
    {
        // `order` was retired: position in the array is the ranking now. A file
        // still carrying one was written against the shape where the number
        // decided, so its author believes it means something. Honouring it here
        // would rank this document the opposite way round from every consumer
        // that reads the array, and neither could be shown to be wrong.
        var map = Read("""
        {
          "catalogue": "https://example.invalid/corpus/specs.json",
          "grades": {"observed": "derived", "vocabulary": [
            {"id": "derived", "title": "Derived", "caveat": "C", "order": 9},
            {"id": "observed", "title": "Observed", "caveat": "C", "order": 0}
          ]},
          "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
          "items": []
        }
        """);

        Assert.Equal(0, map.RankOf("derived"));
        Assert.Equal(1, map.RankOf("observed"));
    }

    [Fact]
    public void The_observed_grade_is_the_one_the_document_names()
    {
        var map = Read(Mapping);

        // Named once, from the set. The browser renders attested evidence
        // differently from every other kind, and the only thing that can say
        // which grade is attested is the document.
        Assert.Equal("observed", map.ObservedGradeId);
        Assert.True(map.IsObserved("observed"));
        Assert.False(map.IsObserved("derived"));

        // Not the first declaration, and not a guess. A vocabulary listing its
        // weakest grade first is legal and this must not promote it.
        var reordered = Read("""
        {
          "catalogue": "https://example.invalid/corpus/specs.json",
          "grades": {"observed": "attested", "vocabulary": [
            {"id": "guessed", "title": "Guessed", "caveat": "C"},
            {"id": "attested", "title": "Attested", "caveat": "C"}
          ]},
          "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
          "items": []
        }
        """);

        Assert.Equal("attested", reordered.ObservedGradeId);
        Assert.True(reordered.IsObserved("attested"));
        Assert.False(reordered.IsObserved("guessed"));
    }

    // ---- operation identity ------------------------------------------------

    [Fact]
    public void A_call_naming_an_operation_by_id_resolves()
    {
        var map = Read(Mapping);

        // Two items call this one operation and both have to come back. The
        // view's whole question is "who calls this", and an index keyed so that
        // the second overwrites the first answers it with a plausible half.
        var callers = map.Callers("ppapi", OperationIdentity.ById("environments_get"));
        Assert.Equal(2, callers.Count);
        Assert.Equal(["resource:powerplatform_environment", "datasource:powerplatform_environments"],
                     callers.Select(c => c.Item.Id));

        // The call comes back with the citation, not just the item, because
        // entrypoint, coverage and grade are properties of the call and differ
        // between two callers of one operation.
        Assert.Equal("create", callers[0].Call.Entrypoint);
        Assert.Equal("full", callers[0].Call.Coverage);
        Assert.Equal("observed", callers[0].Call.Grade);
        Assert.Null(callers[1].Call.Entrypoint);
        Assert.Equal("derived", callers[1].Call.Grade);
    }

    [Fact]
    public void A_call_naming_an_operation_by_method_and_path_resolves()
    {
        var map = Read(Mapping);

        var callers = map.Callers("bapi", OperationIdentity.ByPath("get", "/v1/environments"));
        var only = Assert.Single(callers);
        Assert.Equal("resource:powerplatform_environment", only.Item.Id);
        Assert.Equal("partial", only.Call.Coverage);

        // The mapping wrote GET and the lookup asks for get. A method is
        // case-insensitive by the HTTP rules, so a corpus writing one spelling
        // and a spec the other is not a defect and must not read as one.
        Assert.Single(map.Callers("bapi", OperationIdentity.ByPath("GET", "/v1/environments")));

        // The path is not folded, and that half is load-bearing. A caller
        // sending /V1/Environments where the spec says /v1/environments is a
        // real defect in the caller: that request does not reach that operation.
        // Matching it loosely would hide a bug inside the one file whose entire
        // job is describing what the code does.
        Assert.Empty(map.Callers("bapi", OperationIdentity.ByPath("get", "/V1/Environments")));
    }

    [Fact]
    public void An_operation_id_means_nothing_outside_its_spec()
    {
        // The reason the format carries {spec, operation} structured rather than
        // an id alone: operation ids collide across specs, and a mapping keyed
        // on the id would merge two operations that have nothing to do with each
        // other. The merge is silent and the merged view is plausible.
        var map = Read("""
        {
          "catalogue": "https://example.invalid/corpus/specs.json",
          "grades": {"observed": "observed",
                     "vocabulary": [{"id": "observed", "title": "T", "caveat": "C"}]},
          "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
          "items": [
            {"id": "one", "kind": "resource", "name": "one", "calls": [
              {"spec": "ppapi", "operation": "list", "coverage": "full", "grade": "observed"}
            ]},
            {"id": "two", "kind": "resource", "name": "two", "calls": [
              {"spec": "bapi", "operation": "list", "coverage": "full", "grade": "observed"}
            ]}
          ]
        }
        """);

        Assert.Equal("one", Assert.Single(map.Callers("ppapi", OperationIdentity.ById("list"))).Item.Id);
        Assert.Equal("two", Assert.Single(map.Callers("bapi", OperationIdentity.ById("list"))).Item.Id);
        Assert.Empty(map.Callers("athena", OperationIdentity.ById("list")));
    }

    [Fact]
    public void A_call_naming_its_operation_both_ways_identifies_nothing()
    {
        // Both forms at once is not redundancy, it is two claims that can drift
        // apart with nothing to reconcile them. Picking either one would be this
        // reader inventing the half of the contract that says which wins, and
        // two consumers inventing different halves is a disagreement nobody can
        // adjudicate. The conformance checker rejects the document; a reader
        // that has one anyway must not answer as though the ambiguity were not
        // there.
        var map = Read("""
        {
          "catalogue": "https://example.invalid/corpus/specs.json",
          "grades": {"observed": "observed",
                     "vocabulary": [{"id": "observed", "title": "T", "caveat": "C"}]},
          "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
          "items": [
            {"id": "one", "kind": "resource", "name": "one", "calls": [
              {"spec": "ppapi", "operation": "list", "method": "get", "path": "/v1/things",
               "coverage": "full", "grade": "observed"},
              {"spec": "ppapi", "coverage": "full", "grade": "observed"}
            ]}
          ]
        }
        """);

        Assert.Null(map.Items[0].Calls[0].Identity);
        Assert.Null(map.Items[0].Calls[1].Identity);
        Assert.Empty(map.Callers("ppapi", OperationIdentity.ById("list")));
        Assert.Empty(map.Callers("ppapi", OperationIdentity.ByPath("get", "/v1/things")));
        Assert.Empty(map.CalledOperations("ppapi"));
    }

    [Fact]
    public void The_operations_called_in_a_spec_are_the_set_of_identities()
    {
        var map = Read(Mapping);

        // The inverse view, "which operations does nothing call", is this
        // subtracted from the catalogue by whoever holds both, so this set has
        // to be the identities and not a count: an operation appearing twice is
        // one called operation, and two would understate the gap.
        Assert.Equal([OperationIdentity.ById("environments_get")], map.CalledOperations("ppapi"));
        Assert.Equal([OperationIdentity.ByPath("get", "/v1/environments")], map.CalledOperations("bapi"));

        // Identity is a value, so two identities spelled the same are one, which
        // is what makes the set above a set at all.
        Assert.Equal(OperationIdentity.ById("environments_get"), OperationIdentity.ById("environments_get"));
        Assert.NotEqual(OperationIdentity.ById("environments_get"), OperationIdentity.ById("environments_list"));
        Assert.Equal(OperationIdentity.ByPath("GET", "/x"), OperationIdentity.ByPath("get", "/x"));
        Assert.NotEqual(OperationIdentity.ByPath("get", "/x"), OperationIdentity.ByPath("post", "/x"));
    }

    // ---- the catalogue this mapping is about -------------------------------

    [Fact]
    public void A_mapping_written_against_the_loaded_catalogue_is_admitted()
    {
        // The other half of the refusal, and it is not decoration. A check that
        // refuses everything passes every mismatch case below while making the
        // feature useless, and nothing but this case would notice.
        var reading = CoverageReading.Read(Mapping, new Uri(Catalogue));
        Assert.Null(reading.Refusal);
        Assert.NotNull(reading.Map);
        Assert.Equal(2, reading.Map.Items.Count);
    }

    [Fact]
    public void A_mapping_written_against_another_catalogue_is_refused_whole()
    {
        var reading = CoverageReading.Read(Mapping, new Uri("https://other.invalid/corpus/specs.json"));

        // Not "hidden", not "flagged": absent. There is no map behind the
        // refusal to be read by a view that forgets to ask, because the failure
        // being defended against is precisely the one that looks correct on
        // screen, and a boolean beside a populated map would leave every future
        // call site one forgotten check away from it.
        Assert.Null(reading.Map);
        Assert.NotNull(reading.Refusal);

        // Both urls in the message. A reader who did not write either file
        // cannot act on "this mapping does not match" without being told which
        // two things disagree.
        Assert.Contains(Catalogue, reading.Refusal);
        Assert.Contains("https://other.invalid/corpus/specs.json", reading.Refusal);
    }

    [Fact]
    public void Two_catalogues_on_one_origin_are_two_catalogues()
    {
        // The most likely mismatch there is, and the one a comparison of origins
        // or hosts would wave straight through: two corpora published from one
        // account differ only in path. Both mappings are real, both are
        // conformant, and the wrong one renders in full.
        var reading = CoverageReading.Read(
            """
            {
              "catalogue": "https://pages.invalid/powerplatform/specs.json",
              "grades": {"observed": "observed",
                         "vocabulary": [{"id": "observed", "title": "T", "caveat": "C"}]},
              "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
              "items": []
            }
            """,
            new Uri("https://pages.invalid/demo/specs.json"));

        Assert.Null(reading.Map);
        Assert.NotNull(reading.Refusal);
    }

    [Theory]
    // Scheme and host are case-insensitive by the URL rules, and Uri has already
    // normalised them. Refusing these would be the check firing on the spelling
    // of a url rather than on the corpus it names, which is a check that rejects
    // correct data.
    [InlineData("HTTPS://Example.Invalid/corpus/specs.json")]
    // The default port is the port. A producer writing it out explicitly has
    // named the same document.
    [InlineData("https://example.invalid:443/corpus/specs.json")]
    // A fragment names a location within a document, not a different document.
    [InlineData("https://example.invalid/corpus/specs.json#specs")]
    // Dot segments resolve to the same path, and Uri normalises them.
    [InlineData("https://example.invalid/corpus/../corpus/specs.json")]
    public void A_url_spelled_differently_is_still_the_same_catalogue(string declared)
    {
        var reading = CoverageReading.Of(
            new CoverageDocument { Catalogue = declared }, new Uri(Catalogue));

        Assert.Null(reading.Refusal);
        Assert.NotNull(reading.Map);
    }

    /// <summary>
    /// Every refusal below asserts what it says as well as that it fired, and
    /// that is not decoration.
    ///
    /// <para>
    /// Four separate clauses refuse, they are checked in order, and each later
    /// one would also catch most of what an earlier one catches: an empty
    /// declaration is not an absolute url, and a <c>file:</c> url does not match
    /// an <c>https:</c> one either. So a test asserting only "refused" passes
    /// with any one of them deleted, and the reader who caused it then gets told
    /// their mapping is about another corpus when what they actually have is a
    /// relative url or no url at all. Those are fixed by different edits, and
    /// the message is the entire actionable content of the refusal.
    /// </para>
    ///
    /// <para>
    /// That is this repository's own lesson from the conformance checker's
    /// suite, where three checks were each caught twice over and the second
    /// catch named the same place while telling the reader something useless.
    /// </para>
    /// </summary>
    private static void Refuses(string? declared, string saying)
    {
        var reading = CoverageReading.Of(
            new CoverageDocument { Catalogue = declared }, new Uri(Catalogue));

        Assert.Null(reading.Map);
        Assert.NotNull(reading.Refusal);
        Assert.Contains(saying, reading.Refusal);
    }

    [Theory]
    // A different document on the same host, which is the case above in miniature.
    [InlineData("https://example.invalid/other/specs.json")]
    // A different host serving the same path. Same file name, nothing else.
    [InlineData("https://elsewhere.invalid/corpus/specs.json")]
    // A different scheme is a different origin, whatever the rest says.
    [InlineData("http://example.invalid/corpus/specs.json")]
    // Paths are case-sensitive, so this may or may not be the same file, and
    // "may" is not the standard for showing one corpus's numbers under another's
    // name.
    [InlineData("https://example.invalid/Corpus/specs.json")]
    // A query names a document too: one catalogue with ?v=2 is not the other.
    [InlineData("https://example.invalid/corpus/specs.json?v=2")]
    public void A_catalogue_that_is_a_different_document_is_refused(string declared)
    {
        // Refused as what it is, a mapping about another corpus, and the message
        // names both so the reader can see which two disagree.
        Refuses(declared, "Coverage is not shown");
        Refuses(declared, Catalogue);
    }

    [Theory]
    // Relative. The format requires an absolute url precisely because a relative
    // one has no base once the mapping is read anywhere but beside the
    // catalogue, so this is a declaration that cannot be acted on rather than
    // one to resolve hopefully.
    [InlineData("specs.json")]
    // A scheme this browser will not follow. It could name anything, and it
    // cannot name a catalogue this session could have loaded.
    [InlineData("file:///corpus/specs.json")]
    public void A_catalogue_declaration_that_names_no_document_is_refused_as_that(string declared)
    {
        // And is told apart from a mismatch. "Your mapping is about another
        // corpus" sends a producer looking for a wrong spec id; "your catalogue
        // field is not an absolute url" is the one-line fix they actually have.
        Refuses(declared, "absolute http or https URL");
    }

    [Fact]
    public void A_mapping_that_declares_no_catalogue_is_refused()
    {
        // The field is required by the format because a call's spec id means
        // nothing except against a catalogue. A mapping that omits it has not
        // said what its numbers are about, and "unstated" is not "ours": the
        // charitable reading is exactly the one that renders another corpus's
        // coverage under this corpus's name.
        Refuses(null, "does not say which catalogue");
        Refuses("", "does not say which catalogue");

        // Through the parser too, since an absent key and a null are the same
        // thing here and only one of them is what a producer will actually ship.
        var reading = CoverageReading.Read("""
        {
          "grades": {"observed": "observed",
                     "vocabulary": [{"id": "observed", "title": "T", "caveat": "C"}]},
          "artifacts": {"kind": "component", "kinds": {"resource": "Resource"}},
          "items": []
        }
        """, new Uri(Catalogue));

        Assert.Null(reading.Map);
        Assert.Contains("does not say which catalogue", reading.Refusal);
    }

    [Fact]
    public void A_catalogue_that_cannot_be_named_is_a_mismatch_and_not_a_pass()
    {
        // The app could not say which catalogue it loaded, which happens when
        // the catalogue url was refused. Nothing here is evidence of agreement.
        // Treating "cannot compare" as a pass would remove the check exactly
        // when the situation is already abnormal, which is the one moment it is
        // most needed.
        var reading = CoverageReading.Read(Mapping, null);

        Assert.Null(reading.Map);
        Assert.NotNull(reading.Refusal);
        Assert.Contains("cannot be named", reading.Refusal);
        Assert.Contains(Catalogue, reading.Refusal);
    }

    // ---- the route segment this view will live at --------------------------

    [Fact]
    public void Coverage_is_a_reserved_spec_id()
    {
        // The first path segment is read as a spec id unless it names a kind, so
        // adding a kind takes an id away from every catalogue in the world. The
        // reserved set is derived from the one segment table rather than listed
        // twice, and this is the assertion that the derivation still holds: a
        // corpus conformance check reads ReservedIds, and a corpus with a spec
        // called "coverage" would otherwise be told it was fine and then find
        // that spec unreachable.
        Assert.Contains("coverage", Route.ReservedIds);
        Assert.Equal(RouteKind.Coverage, Route.Parse("#/coverage/resource:env").Kind);
        Assert.Equal("resource:env", Route.Parse("#/coverage/resource:env").Id);
        Assert.Equal("#/coverage/resource%3Aenv",
                     new Route(RouteKind.Coverage, "resource:env").ToHash());

        // A spec id is still a spec id in the qualified form.
        var qualified = Route.Parse("#/ppapi/coverage/resource:env");
        Assert.Equal("ppapi", qualified.SpecId);
        Assert.Equal(RouteKind.Coverage, qualified.Kind);

        // And the bare kind with no id is the overview, which is what every
        // other kind does. Worth pinning rather than assuming: a coverage index
        // page has no route of its own under this shape, so whoever renders one
        // is choosing a URL for it rather than finding this one already works.
        Assert.Equal(RouteKind.Overview, Route.Parse("#/coverage").Kind);
    }
}
