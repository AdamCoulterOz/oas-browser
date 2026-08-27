using System.Text.Json;

namespace OasBrowser.Model;

/// <summary>
/// A deliberately small OpenAPI 3.0 model over <see cref="JsonElement"/>.
/// It covers the subset of 3.0 the specs it was written against actually use,
/// which is why it is not a full OpenAPI library: one would cost payload and
/// version churn for coverage nothing here reads. Reading straight from the
/// JSON also means the x- extensions this app renders (x-notes,
/// x-ms-namespace, x-ms-preview) need no mapping.
///
/// PENDING GENERALISATION: that subset was chosen against one corpus, back when
/// this app and the generator that produced that corpus lived in the same
/// repository and the shape was known. They no longer do, so the assumption is
/// now this app's own and unattested. Deciding what it must cover for an
/// arbitrary spec is the generalisation pass, not something to widen ad hoc.
/// </summary>
public sealed class OpenApiSpec
{
    private readonly JsonElement _root;

    private OpenApiSpec(JsonElement root)
    {
        _root = root;
        Info = new SpecInfo(Obj(root, "info"));
        Servers = Arr(root, "servers").Select(s => Str(s, "url")).Where(u => u is not null).Select(u => u!).ToList();
        Tags = Arr(root, "tags")
            .Select(t => new SpecTag(Str(t, "name") ?? "", Str(t, "description"), SpecNote.Read(t)))
            .ToList();
        Schemas = Obj(root, "components") is { } c && Obj(c, "schemas") is { } s
            ? s.EnumerateObject().ToDictionary(p => p.Name, p => new SchemaRef(p.Value, this), StringComparer.Ordinal)
            : new Dictionary<string, SchemaRef>(StringComparer.Ordinal);

        var ops = new List<Operation>();
        if (Obj(root, "paths") is { } paths)
        {
            foreach (var path in paths.EnumerateObject())
            {
                foreach (var verb in path.Value.EnumerateObject())
                {
                    if (!Methods.Contains(verb.Name)) continue;
                    ops.Add(new Operation(path.Name, verb.Name, verb.Value, this));
                }
            }
        }
        Operations = ops;
    }

    private static readonly HashSet<string> Methods =
        new(StringComparer.OrdinalIgnoreCase) { "get", "put", "post", "delete", "patch", "options", "head", "trace" };

    public SpecInfo Info { get; }
    public IReadOnlyList<string> Servers { get; }
    public IReadOnlyList<SpecTag> Tags { get; }
    public IReadOnlyList<Operation> Operations { get; }
    public IReadOnlyDictionary<string, SchemaRef> Schemas { get; }

    public static OpenApiSpec Parse(string json)
    {
        var doc = JsonDocument.Parse(json);
        return new OpenApiSpec(doc.RootElement.Clone());
    }

    /// <summary>Tags in declared order, then any tag used by an operation but not declared.</summary>
    public IEnumerable<SpecTag> TagsInOrder()
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var t in Tags) { if (seen.Add(t.Name)) yield return t; }
        foreach (var op in Operations)
            foreach (var t in op.Tags)
                if (seen.Add(t)) yield return new SpecTag(t, null, Array.Empty<SpecNote>());
    }

    public SchemaRef? Resolve(string reference)
    {
        const string prefix = "#/components/schemas/";
        if (!reference.StartsWith(prefix, StringComparison.Ordinal)) return null;
        return Schemas.TryGetValue(reference[prefix.Length..], out var s) ? s : null;
    }

    public static string? SchemaName(string reference)
    {
        const string prefix = "#/components/schemas/";
        return reference.StartsWith(prefix, StringComparison.Ordinal) ? reference[prefix.Length..] : null;
    }

    /// <summary>The last segment of a local pointer, which for a component ref is its name.</summary>
    public static string? ComponentName(string? reference)
    {
        if (string.IsNullOrEmpty(reference)) return null;
        var slash = reference.LastIndexOf('/');
        var name = Unescape(slash >= 0 ? reference[(slash + 1)..] : reference);
        return name.Length == 0 ? null : name;
    }

    /// <summary>
    /// Resolve a local JSON pointer to the node it names, or null when nothing
    /// sits there. Deliberately generic over the component buckets: OpenAPI
    /// allows a `$ref` to any of eight of them, these specs use three, and a
    /// pointer walk is shorter than one special case, let alone three.
    /// </summary>
    internal JsonElement? ResolvePointer(string reference)
    {
        // Only same-document pointers. A ref into another file would need a
        // fetch, and none of these specs has one.
        if (!reference.StartsWith("#/", StringComparison.Ordinal)) return null;

        var node = _root;
        foreach (var token in reference[2..].Split('/'))
        {
            var key = Unescape(token);
            if (node.ValueKind == JsonValueKind.Object)
            {
                if (!node.TryGetProperty(key, out node)) return null;
            }
            else if (node.ValueKind == JsonValueKind.Array
                     && int.TryParse(key, out var index)
                     && index >= 0 && index < node.GetArrayLength())
            {
                node = node[index];
            }
            else
            {
                return null;
            }
        }
        return node;
    }

    /// <summary>
    /// Follow a `$ref` to the node it names, through a chain of them if the
    /// document has one.
    ///
    /// The node comes back as it sits in the document, never copied or rebuilt,
    /// so every key on it survives resolution: the `x-` extensions this app
    /// renders (`x-notes`, `x-stub`, `x-ms-enum`), the ones it does not
    /// (`x-source`, `x-probe-verified`), and any a later spec invents. Nothing
    /// here is allow-listed, so nothing here has to be revisited when the
    /// corpus grows a new extension.
    ///
    /// OpenAPI 3.0 gives `$ref` no siblings: a key beside it is ignored, so the
    /// target replaces the node outright rather than merging into it.
    ///
    /// A pointer that resolves to nothing, or a chain that loops, is not a
    /// silent miss. The original node comes back and the reference is reported
    /// through <paramref name="unresolved"/>, so the caller renders the pointer
    /// that failed instead of an empty row.
    /// </summary>
    internal static JsonElement Follow(JsonElement e, OpenApiSpec spec, out string? unresolved)
    {
        unresolved = null;
        if (Str(e, "$ref") is null) return e;

        var node = e;
        var seen = new HashSet<string>(StringComparer.Ordinal);
        for (var hop = 0; hop < MaxRefHops; hop++)
        {
            if (Str(node, "$ref") is not { } reference) return node;
            if (!seen.Add(reference) || spec.ResolvePointer(reference) is not { } target)
            {
                unresolved = reference;
                return e;
            }
            node = target;
        }
        unresolved = Str(e, "$ref");
        return e;
    }

    /// <summary>A chain this long is a document defect, not a shape worth following.</summary>
    private const int MaxRefHops = 8;

    /// <summary>RFC 6901 escaping. `~1` first, so `~01` decodes to `~1` and not to `/`.</summary>
    private static string Unescape(string token) => token.Replace("~1", "/").Replace("~0", "~");

    /// <summary>
    /// A detached empty object, for the places the model must produce a node it
    /// does not have. Cloned, so it outlives the document it was parsed from.
    /// </summary>
    internal static readonly JsonElement EmptyObject = JsonDocument.Parse("{}").RootElement.Clone();

    // ---- JsonElement helpers, shared with the types below ----
    internal static JsonElement? Obj(JsonElement e, string name) =>
        e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Object ? v : null;

    internal static IEnumerable<JsonElement> Arr(JsonElement e, string name) =>
        e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Array
            ? v.EnumerateArray() : Enumerable.Empty<JsonElement>();

    internal static string? Str(JsonElement e, string name) =>
        e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    internal static bool Bool(JsonElement e, string name) =>
        e.ValueKind == JsonValueKind.Object && e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.True;

    internal static IReadOnlyList<string> StrArr(JsonElement e, string name) =>
        Arr(e, name).Where(x => x.ValueKind == JsonValueKind.String).Select(x => x.GetString()!).ToList();
}

public sealed record SpecTag(string Name, string? Description, IReadOnlyList<SpecNote> Notes)
{
    public string Slug => Slugify(Name);

    public static string Slugify(string s)
    {
        var chars = s.ToLowerInvariant().Select(c => char.IsLetterOrDigit(c) ? c : '-').ToArray();
        return string.Join('-', new string(chars).Split('-', StringSplitOptions.RemoveEmptyEntries));
    }
}

public sealed class SpecInfo
{
    public SpecInfo(JsonElement? info)
    {
        var e = info ?? default;
        Title = OpenApiSpec.Str(e, "title") ?? "API";
        Version = OpenApiSpec.Str(e, "version");
        Description = OpenApiSpec.Str(e, "description");
    }

    public string Title { get; }
    public string? Version { get; }
    public string? Description { get; }
}

public sealed class Operation
{
    private readonly JsonElement _e;

    public Operation(string path, string method, JsonElement e, OpenApiSpec spec)
    {
        _e = e;
        Path = path;
        Method = method.ToUpperInvariant();
        OperationId = OpenApiSpec.Str(e, "operationId") ?? $"{method}{path}";
        Summary = OpenApiSpec.Str(e, "summary") ?? OperationId;
        Description = OpenApiSpec.Str(e, "description");
        Tags = OpenApiSpec.StrArr(e, "tags");
        Namespace = OpenApiSpec.Str(e, "x-ms-namespace");
        IsPreview = OpenApiSpec.Bool(e, "x-ms-preview");
        Notes = SpecNote.Read(e);
        DocsUrl = OpenApiSpec.Obj(e, "externalDocs") is { } ed ? OpenApiSpec.Str(ed, "url") : null;
        Parameters = OpenApiSpec.Arr(e, "parameters").Select(p => new Parameter(p, spec)).ToList();

        if (OpenApiSpec.Obj(e, "requestBody") is { } rb)
            RequestBody = new Body(rb, spec);

        Responses = OpenApiSpec.Obj(e, "responses") is { } rs
            ? rs.EnumerateObject().Select(p => new Response(p.Name, p.Value, spec)).OrderBy(r => r.Code, StringComparer.Ordinal).ToList()
            : new List<Response>();
    }

    public string Path { get; }
    public string Method { get; }
    public string OperationId { get; }
    public string Summary { get; }
    public string? Description { get; }
    public IReadOnlyList<string> Tags { get; }
    public string? Namespace { get; }
    public bool IsPreview { get; }
    public IReadOnlyList<SpecNote> Notes { get; }
    public string? DocsUrl { get; }
    public IReadOnlyList<Parameter> Parameters { get; }
    public Body? RequestBody { get; }
    public IReadOnlyList<Response> Responses { get; }

    public string PrimaryTag => Tags.Count > 0 ? Tags[0] : "Other";
}

/// <summary>
/// One parameter of an operation, whether it was written inline or as a `$ref`
/// into `components/parameters`.
/// </summary>
public sealed class Parameter
{
    public Parameter(JsonElement e, OpenApiSpec spec)
    {
        var node = OpenApiSpec.Follow(e, spec, out var unresolved);
        UnresolvedReference = unresolved;

        // The component's own name, not the key it was filed under: a spec may
        // file `x-ms-organization-id` under `xMsOrganizationId`. Falling back to
        // the pointer's last segment keeps a broken ref legible.
        Name = OpenApiSpec.Str(node, "name") ?? OpenApiSpec.ComponentName(unresolved) ?? "";
        In = OpenApiSpec.Str(node, "in") ?? "query";
        Required = OpenApiSpec.Bool(node, "required");
        Description = OpenApiSpec.Str(node, "description");

        // Never null. A parameter with no schema used to be dropped by the
        // renderer, which filters on exactly this, so a parameter the model
        // could not read costs the reader the whole row and says nothing. The
        // stand-in renders in its place and names what is missing.
        Schema = OpenApiSpec.Obj(node, "schema") is { } s
            ? new SchemaRef(s, spec)
            : SchemaRef.Missing(unresolved, spec);
    }

    public string Name { get; }
    public string In { get; }
    public bool Required { get; }
    public string? Description { get; }
    public SchemaRef Schema { get; }

    /// <summary>The `$ref` this parameter was written as, when it led nowhere.</summary>
    public string? UnresolvedReference { get; }
}

public sealed class Body
{
    public Body(JsonElement e, OpenApiSpec spec)
    {
        var node = OpenApiSpec.Follow(e, spec, out var unresolved);
        UnresolvedReference = unresolved;

        Required = OpenApiSpec.Bool(node, "required");
        Description = OpenApiSpec.Str(node, "description");
        if (OpenApiSpec.Obj(node, "content") is { } content)
        {
            var first = content.EnumerateObject().FirstOrDefault();
            if (first.Value.ValueKind == JsonValueKind.Object)
            {
                MediaType = first.Name;
                if (OpenApiSpec.Obj(first.Value, "schema") is { } s) Schema = new SchemaRef(s, spec);
            }
        }

        // The body renders only when it has a schema, so a ref that led nowhere
        // would take the whole body with it. Stand in for it and name it.
        Schema ??= unresolved is null ? null : SchemaRef.Missing(unresolved, spec);
    }

    public bool Required { get; }
    public string? Description { get; }
    public string? MediaType { get; }
    public SchemaRef? Schema { get; }

    /// <summary>The `$ref` this body was written as, when it led nowhere.</summary>
    public string? UnresolvedReference { get; }
}

public sealed class Response
{
    public Response(string code, JsonElement e, OpenApiSpec spec)
    {
        Code = code;
        var node = OpenApiSpec.Follow(e, spec, out var unresolved);
        UnresolvedReference = unresolved;

        // A status chip with nothing behind it reads as an API that documents
        // nothing, rather than as a browser that failed to follow a pointer.
        // Say which it is.
        Description = OpenApiSpec.Str(node, "description")
            ?? (unresolved is null ? null : $"This response is written as `{unresolved}`, which the specification does not define.");

        if (OpenApiSpec.Obj(node, "content") is { } content)
        {
            var first = content.EnumerateObject().FirstOrDefault();
            if (OpenApiSpec.Obj(first.Value, "schema") is { } s)
            {
                MediaType = first.Name;
                Schema = new SchemaRef(s, spec);
            }
        }
        Headers = OpenApiSpec.Obj(node, "headers") is { } h
            ? h.EnumerateObject().Select(p => new Header(p.Name, p.Value, spec)).ToList()
            : new List<Header>();
    }

    public string Code { get; }
    public string? Description { get; }
    public string? MediaType { get; }
    public SchemaRef? Schema { get; }
    public IReadOnlyList<Header> Headers { get; }

    /// <summary>The `$ref` this response was written as, when it led nowhere.</summary>
    public string? UnresolvedReference { get; }

    public bool IsSuccess => Code.StartsWith('2');
    public bool IsError => Code.StartsWith('4') || Code.StartsWith('5');
}

public sealed class Header
{
    public Header(string name, JsonElement e, OpenApiSpec spec)
    {
        Name = name;
        var node = OpenApiSpec.Follow(e, spec, out var unresolved);
        UnresolvedReference = unresolved;
        Description = OpenApiSpec.Str(node, "description");
        Schema = OpenApiSpec.Obj(node, "schema") is { } s
            ? new SchemaRef(s, spec)
            : unresolved is null ? null : SchemaRef.Missing(unresolved, spec);
    }

    public string Name { get; }
    public string? Description { get; }
    public SchemaRef? Schema { get; }

    /// <summary>The `$ref` this header was written as, when it led nowhere.</summary>
    public string? UnresolvedReference { get; }
}
