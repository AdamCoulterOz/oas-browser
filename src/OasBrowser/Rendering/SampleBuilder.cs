using System.Text;
using OasBrowser.Model;

namespace OasBrowser.Rendering;

/// <summary>Builds the request and response samples shown beside an operation.</summary>
public static class SampleBuilder
{
    private const int MaxDepth = 6;

    public static string Json(SchemaRef? schema)
    {
        if (schema is null) return "{}";
        var sb = new StringBuilder();
        Write(sb, schema, 0, new HashSet<string>(StringComparer.Ordinal));
        return sb.ToString();
    }

    private static void Write(StringBuilder sb, SchemaRef node, int depth, HashSet<string> seen)
    {
        var s = node.Unwrapped;
        var name = s.RefName;
        var target = s.Target;

        // cycle guard: a model can reference itself through a property
        if (name is not null && !seen.Add(name))
        {
            sb.Append('"').Append(name).Append(" { … }\"");
            return;
        }
        if (depth > MaxDepth) { sb.Append("\"…\""); return; }

        try
        {
            if (target.Enum.Count > 0) { sb.Append('"').Append(target.Enum[0]).Append('"'); return; }

            var type = target.Type;

            if (type == "array" || target.Items is not null)
            {
                sb.Append("[\n");
                Indent(sb, depth + 1);
                if (target.Items is { } item) Write(sb, item, depth + 1, seen);
                else sb.Append("\"…\"");
                sb.Append('\n');
                Indent(sb, depth);
                sb.Append(']');
                return;
            }

            var props = target.Properties;
            if (props.Count > 0 || target.AdditionalProperties is not null || type == "object")
            {
                sb.Append("{\n");
                var written = 0;
                foreach (var p in props)
                {
                    if (written > 0) sb.Append(",\n");
                    Indent(sb, depth + 1);
                    sb.Append('"').Append(p.Name).Append("\": ");
                    Write(sb, p.Schema, depth + 1, seen);
                    written++;
                }
                if (props.Count == 0 && target.AdditionalProperties is { } ap)
                {
                    Indent(sb, depth + 1);
                    sb.Append("\"key\": ");
                    Write(sb, ap, depth + 1, seen);
                    written++;
                }
                if (written > 0) sb.Append('\n');
                Indent(sb, depth);
                sb.Append('}');
                return;
            }

            sb.Append(Scalar(type, target.Format));
        }
        finally
        {
            if (name is not null) seen.Remove(name);
        }
    }

    private static string Scalar(string? type, string? format) => type switch
    {
        "integer" => "0",
        "number" => "0",
        "boolean" => "true",
        _ => format switch
        {
            "uuid" => "\"00000000-0000-0000-0000-000000000000\"",
            "date-time" => "\"2026-01-01T00:00:00Z\"",
            "uri" => "\"https://…\"",
            "binary" => "\"<binary>\"",
            _ => "\"string\""
        }
    };

    private static void Indent(StringBuilder sb, int depth) => sb.Append(' ', depth * 2);

    /// <summary>
    /// The request as an HTTP file: the request line, headers, then the body.
    /// This is the shape the API actually speaks, and it pastes straight into
    /// a .http file or REST client, which curl with escaped line breaks does
    /// not.
    /// </summary>
    public static string HttpRequest(Operation op, string server)
    {
        var sb = new StringBuilder();

        var query = op.Parameters
            .Where(p => p.In == "query")
            .Select(p => $"{p.Name}={Placeholder(p)}")
            .ToList();

        sb.Append(op.Method).Append(' ').Append(server).Append(op.Path);
        if (query.Count > 0) sb.Append('?').Append(string.Join("&", query));
        sb.Append('\n');

        sb.Append("Authorization: Bearer $TOKEN\n");

        foreach (var h in op.Parameters.Where(p => p.In == "header"))
        {
            sb.Append(h.Name).Append(": ").Append(Placeholder(h)).Append('\n');
        }

        if (op.RequestBody is { Schema: { } schema })
        {
            var mediaType = op.RequestBody.MediaType ?? "application/json";
            sb.Append("Content-Type: ").Append(mediaType).Append('\n');
            sb.Append('\n');
            sb.Append(Body(schema, mediaType));
        }

        return sb.ToString().TrimEnd('\n');
    }

    /// <summary>
    /// The response in the same form: status line, the headers the spec
    /// documents, then the body.
    /// </summary>
    public static string HttpResponse(Response response)
    {
        var sb = new StringBuilder();
        sb.Append("HTTP/1.1 ").Append(response.Code).Append(' ').Append(ReasonPhrase(response)).Append('\n');

        foreach (var h in response.Headers)
        {
            sb.Append(h.Name).Append(": ").Append(HeaderPlaceholder(h)).Append('\n');
        }

        if (response.Schema is { } schema)
        {
            var mediaType = response.MediaType ?? "application/json";
            sb.Append("Content-Type: ").Append(mediaType).Append('\n');
            sb.Append('\n');
            sb.Append(Body(schema, mediaType));
        }

        return sb.ToString().TrimEnd('\n');
    }

    /// <summary>Render a body in whatever the content type asks for.</summary>
    private static string Body(SchemaRef schema, string mediaType)
    {
        if (mediaType.Contains("json", StringComparison.OrdinalIgnoreCase)) return Json(schema);
        if (mediaType.Contains("xml", StringComparison.OrdinalIgnoreCase)) return Xml(schema);
        if (mediaType.Contains("form-data", StringComparison.OrdinalIgnoreCase)) return FormData(schema);
        return "<body>";
    }

    private static string Xml(SchemaRef schema)
    {
        var node = schema.Unwrapped;
        var name = node.RefName ?? "root";
        var sb = new StringBuilder();
        sb.Append('<').Append(name).Append(">\n");
        foreach (var p in node.Target.Properties)
        {
            var value = p.Schema.Unwrapped.Target.Type == "object" ? "…" : Scalar(p.Schema.Unwrapped.Target.Type, p.Schema.Unwrapped.Target.Format).Trim('"');
            sb.Append("  <").Append(p.Name).Append('>').Append(value).Append("</").Append(p.Name).Append(">\n");
        }
        sb.Append("</").Append(name).Append('>');
        return sb.ToString();
    }

    private static string FormData(SchemaRef schema)
    {
        var sb = new StringBuilder();
        foreach (var p in schema.Unwrapped.Target.Properties)
        {
            sb.Append("--boundary\n");
            sb.Append("Content-Disposition: form-data; name=\"").Append(p.Name).Append("\"\n\n");
            sb.Append(p.Schema.Unwrapped.Target.Format == "binary" ? "<file>" : "value").Append('\n');
        }
        sb.Append("--boundary--");
        return sb.ToString();
    }

    /// <summary>The reason phrase for the common codes, so the status line reads properly.</summary>
    private static string ReasonPhrase(Response response) => response.Code switch
    {
        "200" => "OK",
        "201" => "Created",
        "202" => "Accepted",
        "204" => "No Content",
        "400" => "Bad Request",
        "401" => "Unauthorized",
        "403" => "Forbidden",
        "404" => "Not Found",
        "409" => "Conflict",
        "429" => "Too Many Requests",
        "500" => "Internal Server Error",
        _ => (response.Description ?? "").Split('\n')[0].Trim()
    };

    private static string HeaderPlaceholder(Header h)
    {
        var format = h.Schema?.Target.Format;
        return format switch
        {
            "uri" => "https://…",
            "date-time" => "2026-01-01T00:00:00Z",
            _ => "…"
        };
    }

    private static string Placeholder(Parameter p)
    {
        var d = p.Schema?.Target;
        if (d is not null && d.Enum.Count > 0) return d.Enum[0];
        if (d?.Raw.ValueKind == System.Text.Json.JsonValueKind.Object
            && d.Raw.TryGetProperty("default", out var def))
        {
            var text = def.ValueKind == System.Text.Json.JsonValueKind.String ? def.GetString() : def.ToString();
            if (!string.IsNullOrEmpty(text)) return text!;
        }
        return "{" + p.Name + "}";
    }
}
