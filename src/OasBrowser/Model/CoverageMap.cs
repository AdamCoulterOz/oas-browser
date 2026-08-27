using System.Text.Json;
using System.Text.Json.Serialization;

namespace OasBrowser.Model;

/// <summary>
/// The document form of a coverage mapping: an external repository's published
/// claim that these units of its code call these API operations.
///
/// <para>
/// The browser defines this format and knows nothing about any producer in
/// reading it. Every vocabulary in here is declared by the document itself, so
/// there is exactly one remembered vocabulary in this file, <c>full</c> and
/// <c>partial</c>, and that one is closed rather than pending: a call exercises
/// the whole of an operation or some of it, and a corpus reaching for a third
/// value has found a second question rather than a missing enum member.
/// </para>
///
/// <para>
/// <c>tools/validate_coverage.py</c> is the conformance check for this format
/// and it runs in the producer's CI, not here. This is a reader, so it is
/// tolerant where that is a checker: a call the checker would reject is
/// generally carried rather than thrown away, and the one place tolerance is
/// refused is the catalogue agreement in <see cref="CoverageReading"/>.
/// </para>
/// </summary>
public sealed class CoverageDocument
{
    /// <summary>
    /// The catalogue this mapping was written against, absolute. Required by the
    /// format, and the reason it is required is that a call's <c>spec</c> id
    /// means nothing except against a catalogue, so this is the only field that
    /// says which corpus every number in the file is about.
    /// </summary>
    [JsonPropertyName("catalogue")] public string? Catalogue { get; set; }

    [JsonPropertyName("grades")] public GradeVocabulary? Grades { get; set; }
    [JsonPropertyName("artifacts")] public ArtifactDeclaration? Artifacts { get; set; }

    /// <summary>
    /// The reason vocabulary for uncatalogued calls, id to display label. At the
    /// root rather than under <c>artifacts</c> because a declared vocabulary
    /// sits at the level of the thing it describes, and these describe
    /// uncatalogued entries, which have no container of their own.
    /// </summary>
    [JsonPropertyName("uncatalogued")] public Dictionary<string, string>? Uncatalogued { get; set; }

    [JsonPropertyName("items")] public List<CoverageItem> Items { get; set; } = [];
}

/// <summary>
/// The grade vocabulary, and which member of it counts as attested.
///
/// <para>
/// <b>Order is position in <see cref="Vocabulary"/>.</b> There is no order
/// field: one existed, it was retired, and a mapping still carrying it is
/// carrying a value that decides nothing. Ranking a set from a number written on
/// each member lets a document represent two firsts and a gap; ranking it from
/// the array makes both unrepresentable, so the rule disappears rather than
/// being enforced.
/// </para>
///
/// <para>
/// <see cref="Observed"/> names the attested grade once, from the set, for the
/// same reason: "exactly one" is a property of the set, and the shape that put a
/// boolean on every member could represent none and could represent five.
/// </para>
/// </summary>
public sealed class GradeVocabulary
{
    [JsonPropertyName("observed")] public string? Observed { get; set; }
    [JsonPropertyName("vocabulary")] public List<CoverageGrade> Vocabulary { get; set; } = [];
}

/// <summary>
/// One grade: what a claim about a call is founded on.
///
/// A separately declared vocabulary rather than a shared enum with the spec
/// corpus. Those grades are provenances of a claim about an API's behaviour,
/// these are provenances of a claim about what a codebase calls. Same mechanism,
/// same reader-facing meaning, different sets.
/// </summary>
public sealed class CoverageGrade
{
    [JsonPropertyName("id")] public string? Id { get; set; }
    [JsonPropertyName("title")] public string? Title { get; set; }
    [JsonPropertyName("caveat")] public string? Caveat { get; set; }

    /// <summary>
    /// Optional, and its vocabulary is keel's rather than this format's. Naming
    /// the accepted tones here would be a second remembered vocabulary rotting
    /// against a repository with no reason to tell this one when it grows.
    /// </summary>
    [JsonPropertyName("tone")] public string? Tone { get; set; }
}

/// <summary>
/// What this mapping's artifacts are. <c>kinds</c> and <c>entrypoints</c> live
/// here rather than at the root because they describe artifacts, which is the
/// same placement rule that keeps grades and uncatalogued reasons at the root.
/// </summary>
public sealed class ArtifactDeclaration
{
    /// <summary>What one artifact is, in prose: "provider component".</summary>
    [JsonPropertyName("kind")] public string? Kind { get; set; }

    [JsonPropertyName("kinds")] public Dictionary<string, string>? Kinds { get; set; }

    /// <summary>
    /// Optional. An artifact may reach different operations depending on which
    /// of its named entrypoints ran, and the producer's natural unit is
    /// (artifact, entrypoint, operation): one component reaching one operation
    /// from three lifecycle phases is three rows, and which phase is the useful
    /// fact. Collapsing that is lossy in a way nothing downstream can undo.
    /// </summary>
    [JsonPropertyName("entrypoints")] public Dictionary<string, string>? Entrypoints { get; set; }
}

/// <summary>One mapped unit of the producer's codebase.</summary>
public sealed class CoverageItem
{
    [JsonPropertyName("id")] public string? Id { get; set; }
    [JsonPropertyName("kind")] public string? Kind { get; set; }
    [JsonPropertyName("name")] public string? Name { get; set; }
    [JsonPropertyName("source")] public CoverageSource? Source { get; set; }
    [JsonPropertyName("calls")] public List<CoverageCall> Calls { get; set; } = [];

    /// <summary>
    /// Calls this artifact makes that no catalogue operation names: a URL
    /// returned in a Location header and polled, a URL the user supplies in
    /// configuration, a path whose segments are runtime values.
    ///
    /// <para>
    /// This is not a convenience field, it is the failure pattern the format
    /// exists to head off. A coverage view that silently omits a fifth of what
    /// an artifact does looks exactly like a complete one: nothing is missing on
    /// screen, and the page quietly asserts more than the data earned.
    /// </para>
    /// </summary>
    [JsonPropertyName("uncatalogued")] public List<UncataloguedCall> Uncatalogued { get; set; } = [];
}

/// <summary>Where the artifact lives, repository-relative.</summary>
public sealed class CoverageSource
{
    [JsonPropertyName("path")] public string? Path { get; set; }
    [JsonPropertyName("line")] public int? Line { get; set; }
}

/// <summary>
/// One call an artifact makes to one operation of one spec.
///
/// <para>
/// <see cref="Spec"/> is structured alongside the operation rather than folded
/// into a <c>spec:</c> URI, because operation identity is unique only within a
/// spec: a corpus with the same operationId in two specs would have those two
/// silently merged by a mapping keyed on the id alone.
/// </para>
/// </summary>
public sealed class CoverageCall
{
    [JsonPropertyName("spec")] public string? Spec { get; set; }

    /// <summary>The operationId, when the spec gives its operations ids.</summary>
    [JsonPropertyName("operation")] public string? Operation { get; set; }

    /// <summary>With <see cref="Path"/>, the other way to name an operation. Never both.</summary>
    [JsonPropertyName("method")] public string? Method { get; set; }

    [JsonPropertyName("path")] public string? Path { get; set; }

    /// <summary>
    /// <c>full</c> or <c>partial</c>, kept as written rather than parsed into a
    /// two-member enum. A closed binary needs no enum to defend it, and turning
    /// a third value into a parse failure would take a whole mapping off screen
    /// over one row that a checker in the producer's CI already refuses.
    /// </summary>
    [JsonPropertyName("coverage")] public string? Coverage { get; set; }

    [JsonPropertyName("grade")] public string? Grade { get; set; }

    /// <summary>Which declared entrypoint this call was reached from, if any.</summary>
    [JsonPropertyName("entrypoint")] public string? Entrypoint { get; set; }

    /// <summary>
    /// An annotation, never a disambiguator: which version of an API the
    /// artifact asked for. Absence means the operation's default. Deliberately
    /// no part of <see cref="OperationIdentity"/>, since two calls to one
    /// operation at two api-versions are two calls to one operation.
    /// </summary>
    [JsonPropertyName("apiVersion")] public string? ApiVersion { get; set; }

    /// <summary>
    /// The producer could not resolve this row with certainty. Absence means
    /// false. It softens nothing: it is a claim about the producer's confidence,
    /// and letting it suppress anything would make it a way to silence a real
    /// failure by declaring uncertainty about it.
    /// </summary>
    [JsonPropertyName("approximate")] public bool? Approximate { get; set; }

    [JsonPropertyName("note")] public string? Note { get; set; }

    /// <summary>
    /// How this call names its operation, or null when it names it in neither
    /// form or in both. Both forms at once is not redundancy, it is two claims
    /// that can drift apart with nothing to reconcile them, so it identifies
    /// nothing here either.
    /// </summary>
    public OperationIdentity? Identity => OperationIdentity.Of(this);
}

/// <summary>A call with no operation identity, and why it has none.</summary>
public sealed class UncataloguedCall
{
    [JsonPropertyName("reason")] public string? Reason { get; set; }
    [JsonPropertyName("count")] public int? Count { get; set; }
    [JsonPropertyName("note")] public string? Note { get; set; }
}

/// <summary>
/// How a call names an operation: by operationId, or by method and path.
///
/// <para>
/// One comparable value rather than an either-or threaded through every query.
/// The alternative is each site that looks a call up asking "does this one have
/// an operation id?" and each site answering it slightly differently; the first
/// place two of them disagree is a coverage view where an operation shows some
/// of its callers.
/// </para>
///
/// <para>
/// A record, so equality is the value's and not the reference's, which is what
/// makes this usable as a dictionary key. A class rather than a struct because a
/// struct has a default value and the default here would be an identity naming
/// nothing, which is a state the factories exist to make unreachable.
/// </para>
///
/// <para>
/// The method is folded to lower case and the path is not. GET and get are the
/// same operation; URL paths are case-sensitive, and a caller sending
/// <c>/licensing/BillingPolicies</c> where the spec says
/// <c>billingPolicies</c> is a defect in the caller that a fold would hide
/// inside the one file whose whole job is describing what the code does.
/// </para>
/// </summary>
public sealed record OperationIdentity
{
    private OperationIdentity(string? operationId, string? method, string? path)
    {
        OperationId = operationId;
        Method = method;
        Path = path;
    }

    /// <summary>Set when this identity is an operationId; null otherwise.</summary>
    public string? OperationId { get; }

    /// <summary>Set, lower case, when this identity is a method and path; null otherwise.</summary>
    public string? Method { get; }

    public string? Path { get; }

    public static OperationIdentity ById(string operationId) => new(operationId, null, null);

    public static OperationIdentity ByPath(string method, string path) =>
        new(null, method.ToLowerInvariant(), path);

    /// <summary>
    /// The identity of one call, or null when it has none. A call naming both
    /// forms has no identity here: the format says exactly one, and picking
    /// either would be this reader inventing the half of the contract that says
    /// which one wins.
    /// </summary>
    public static OperationIdentity? Of(CoverageCall call)
    {
        var hasOperation = call.Operation is { Length: > 0 };
        var hasPath = call.Method is { Length: > 0 } && call.Path is { Length: > 0 };

        if (hasOperation && (call.Method is not null || call.Path is not null)) return null;
        if (hasOperation) return ById(call.Operation!);
        return hasPath ? ByPath(call.Method!, call.Path!) : null;
    }

    /// <summary>For a message or a log line, never for comparison.</summary>
    public override string ToString() =>
        OperationId ?? $"{Method?.ToUpperInvariant()} {Path}";
}

/// <summary>
/// One artifact's claim to call one operation. The call is carried whole rather
/// than flattened, so a view reads entrypoint, coverage, grade, note and
/// approximate off the same row the producer wrote.
/// </summary>
public sealed record CoverageCitation(CoverageItem Item, CoverageCall Call);

/// <summary>
/// A parsed coverage mapping with the queries a coverage view needs, indexed
/// once at parse rather than scanned per operation. A corpus of a few hundred
/// operations against a few hundred artifacts is a few hundred thousand
/// comparisons per render otherwise, and the index is the same data.
/// </summary>
public sealed class CoverageMap
{
    private static readonly IReadOnlyDictionary<string, string> NoLabels =
        new Dictionary<string, string>(StringComparer.Ordinal);

    private static readonly IReadOnlyList<CoverageCitation> NoCitations = Array.Empty<CoverageCitation>();

    private static readonly IReadOnlyCollection<OperationIdentity> NoOperations = Array.Empty<OperationIdentity>();

    // spec id -> operation identity -> the artifacts claiming to call it.
    private readonly Dictionary<string, Dictionary<OperationIdentity, List<CoverageCitation>>> _callers =
        new(StringComparer.Ordinal);

    private readonly Dictionary<string, int> _gradeRank = new(StringComparer.Ordinal);

    internal CoverageMap(CoverageDocument document)
    {
        Declares = document.Catalogue ?? "";
        Items = document.Items;
        Grades = document.Grades?.Vocabulary ?? [];
        ObservedGradeId = document.Grades?.Observed;
        ArtifactKind = document.Artifacts?.Kind;
        Kinds = document.Artifacts?.Kinds ?? NoLabels;
        Entrypoints = document.Artifacts?.Entrypoints ?? NoLabels;
        UncataloguedReasons = document.Uncatalogued ?? NoLabels;

        // Position in the array is the rank. The first declaration this reader
        // sees for an id wins, because a duplicated id has two positions and
        // taking the later one would silently move every grade after it.
        for (var i = 0; i < Grades.Count; i++)
            if (Grades[i].Id is { Length: > 0 } id)
                _gradeRank.TryAdd(id, i);

        foreach (var item in Items)
        {
            foreach (var call in item.Calls)
            {
                if (call.Spec is not { Length: > 0 } spec) continue;
                if (call.Identity is not { } identity) continue;

                if (!_callers.TryGetValue(spec, out var bySpec))
                    _callers[spec] = bySpec = [];
                if (!bySpec.TryGetValue(identity, out var citations))
                    bySpec[identity] = citations = [];

                citations.Add(new CoverageCitation(item, call));
            }
        }
    }

    /// <summary>
    /// The catalogue this mapping declares it was written against, as written.
    /// Kept so that a refusal can quote it back: a reader told the mapping does
    /// not match has to be told which corpus it is about.
    /// </summary>
    public string Declares { get; }

    public IReadOnlyList<CoverageItem> Items { get; }

    /// <summary>The grade vocabulary in declared order, which is the ranking.</summary>
    public IReadOnlyList<CoverageGrade> Grades { get; }

    /// <summary>
    /// Which grade counts as attested, so a view can render observed evidence
    /// differently from every other kind. Null in a document that declares none,
    /// which the checker refuses and this reader survives.
    /// </summary>
    public string? ObservedGradeId { get; }

    /// <summary>What one artifact is, in prose, for the places a view says it.</summary>
    public string? ArtifactKind { get; }

    public IReadOnlyDictionary<string, string> Kinds { get; }
    public IReadOnlyDictionary<string, string> Entrypoints { get; }
    public IReadOnlyDictionary<string, string> UncataloguedReasons { get; }

    public bool IsObserved(string? gradeId) =>
        gradeId is { Length: > 0 } && ObservedGradeId == gradeId;

    /// <summary>Position in the declared vocabulary, or null for an id it does not declare.</summary>
    public int? RankOf(string? gradeId) =>
        gradeId is { Length: > 0 } id && _gradeRank.TryGetValue(id, out var rank) ? rank : null;

    /// <summary>The declaration of one grade, or null for an id this document does not declare.</summary>
    public CoverageGrade? Grade(string? gradeId) =>
        RankOf(gradeId) is { } rank ? Grades[rank] : null;

    /// <summary>
    /// The artifacts claiming to call one operation of one spec, in document
    /// order, with the call each claim was made by.
    ///
    /// <para>
    /// Identity is compared exactly. A call naming <c>method</c> and <c>path</c>
    /// matches a spec path that templates a segment, by the contract's matching
    /// rule, and that resolution deliberately does not happen here: ranking
    /// candidates by how many segments they match literally needs the spec's
    /// whole path set, which this document is not and cannot become. So a
    /// caller holding a spec is the one that can resolve a templated path to the
    /// identities in this index, and doing half of it here would be a second
    /// place for the rule to live.
    /// </para>
    /// </summary>
    public IReadOnlyList<CoverageCitation> Callers(string? specId, OperationIdentity? operation) =>
        specId is { Length: > 0 } spec
        && operation is not null
        && _callers.TryGetValue(spec, out var bySpec)
        && bySpec.TryGetValue(operation, out var citations)
            ? citations
            : NoCitations;

    /// <summary>
    /// Every operation identity called in one spec.
    ///
    /// The inverse view, "which operations does nothing call", is this
    /// subtracted from the catalogue by whoever holds both. Derived rather than
    /// materialised, so it stays true when either side changes; a materialised
    /// one is a claim about the spec living in the producer's repository, going
    /// stale the day an operation is added.
    /// </summary>
    public IReadOnlyCollection<OperationIdentity> CalledOperations(string? specId) =>
        specId is { Length: > 0 } spec && _callers.TryGetValue(spec, out var bySpec)
            ? bySpec.Keys
            : NoOperations;
}

/// <summary>
/// The outcome of reading a coverage mapping: a map to render, or a reason not
/// to render one. Never both, and never neither.
///
/// <para>
/// <b>The refusal is the point of this type.</b> A mapping names the catalogue
/// it was written against, and coverage shown against a different catalogue is
/// the worst kind of wrong available here: every spec id resolves, every item
/// renders, every count is plausible, and all of it is about a different API.
/// Nothing on screen looks off, so no reader can catch it, and the numbers are
/// exactly the sort a person then quotes in a decision. Compared with that, a
/// page saying "this mapping is about another corpus" is cheap.
/// </para>
///
/// <para>
/// So the data is not merely hidden when they disagree, it is not exposed:
/// <see cref="Map"/> is null and there is nothing behind it to read. A boolean
/// beside a populated map would leave every future call site one forgotten
/// check away from the failure this refuses.
/// </para>
/// </summary>
public sealed class CoverageReading
{
    private CoverageReading(CoverageMap? map, string? refusal)
    {
        Map = map;
        Refusal = refusal;
    }

    /// <summary>The mapping, or null when it was refused.</summary>
    public CoverageMap? Map { get; }

    /// <summary>Why there is no mapping, or null when there is one.</summary>
    public string? Refusal { get; }

    public static CoverageReading Refused(string reason) => new(null, reason);

    /// <summary>
    /// Parses a mapping and admits it only if it was written against the
    /// catalogue actually loaded.
    ///
    /// <para>
    /// <paramref name="loaded"/> is the catalogue this session read, which is
    /// the thing every spec id in the document is about to be resolved against.
    /// Null means the app could not name its own catalogue, and that is refused
    /// rather than waved through: "cannot compare" is not evidence of agreement,
    /// and treating it as a pass would make the check absent exactly when the
    /// situation is already unusual.
    /// </para>
    ///
    /// <para>
    /// Throws <see cref="JsonException"/> on a document that is not JSON, like
    /// every other load in this app. A parse failure is not a mismatch and
    /// should not be dressed as one.
    /// </para>
    /// </summary>
    public static CoverageReading Read(string json, Uri? loaded)
    {
        var document = JsonSerializer.Deserialize<CoverageDocument>(json) ?? new CoverageDocument();
        return Of(document, loaded);
    }

    /// <summary>The check on its own, for a document that is already parsed.</summary>
    public static CoverageReading Of(CoverageDocument document, Uri? loaded)
    {
        if (loaded is null)
            return Refused(
                "This coverage mapping was written against "
                + Quoted(document.Catalogue)
                + ", and the catalogue this session loaded cannot be named, so the two "
                + "cannot be compared. Coverage is not shown, because a mapping's spec "
                + "ids mean nothing except against the catalogue it was written for.");

        if (document.Catalogue is not { Length: > 0 } declared)
            return Refused(
                "This coverage mapping does not say which catalogue it was written "
                + $"against, so it cannot be checked against {loaded}. Coverage is not "
                + "shown: the mapping's spec ids would be resolved against a corpus "
                + "nothing has claimed they belong to.");

        // Absolute only. A relative reference has no base once the mapping is
        // read anywhere other than beside the catalogue, and the format requires
        // an absolute URL for exactly that reason, so a relative one here is a
        // declaration this cannot act on rather than one it can guess at.
        if (!Uri.TryCreate(declared.Trim(), UriKind.Absolute, out var against)
            || against.Scheme is not ("http" or "https"))
            return Refused(
                $"This coverage mapping declares its catalogue as {Quoted(declared)}, "
                + "which is not an absolute http or https URL, so it cannot be compared "
                + $"with the catalogue this session loaded, {loaded}. Coverage is not shown.");

        return SameDocument(against, loaded)
            ? new CoverageReading(new CoverageMap(document), null)
            : Refused(
                $"This coverage mapping was written against {against}, and the catalogue "
                + $"this session loaded is {loaded}. Coverage is not shown, because every "
                + "item in it names operations of that other corpus: the view would render "
                + "in full and every figure on it would be about an API you are not "
                + "looking at.");
    }

    private static string Quoted(string? value) =>
        value is { Length: > 0 } ? $"\"{value}\"" : "nothing";

    /// <summary>
    /// Whether two URLs name the same document.
    ///
    /// <para>
    /// Compared part by part rather than as strings, because a string comparison
    /// makes trivia significant: a declared <c>HTTPS://Example.invalid:443/x</c>
    /// and a loaded <c>https://example.invalid/x</c> are one document, and
    /// refusing them would be this check firing on the spelling of a URL rather
    /// than on the corpus it names. Scheme and host are case-insensitive by the
    /// URL rules and <see cref="Uri"/> has already normalised them; the port is
    /// its scheme's default when none was written; the path and query are
    /// case-sensitive and are compared as such, since a server may well serve
    /// two documents at two spellings.
    /// </para>
    ///
    /// <para>
    /// The fragment is excluded deliberately. It names a location within a
    /// document rather than a different document, so two URLs differing only
    /// there fetch the same bytes and disagreeing about them would be a refusal
    /// with no corpus behind it.
    /// </para>
    ///
    /// <para>
    /// What this cannot do, and no consumer-side check can: catch a mapping that
    /// declares the catalogue it was <em>meant</em> for while being generated
    /// against another. The declaration is the only evidence there is on this
    /// side. That gap is the producer's checker's, which resolves every call
    /// against the catalogue this names and fails their build when an operation
    /// is not in it.
    /// </para>
    /// </summary>
    private static bool SameDocument(Uri a, Uri b) =>
        string.Equals(a.Scheme, b.Scheme, StringComparison.OrdinalIgnoreCase)
        && string.Equals(a.Host, b.Host, StringComparison.OrdinalIgnoreCase)
        && a.Port == b.Port
        && string.Equals(a.AbsolutePath, b.AbsolutePath, StringComparison.Ordinal)
        && string.Equals(a.Query, b.Query, StringComparison.Ordinal);
}
