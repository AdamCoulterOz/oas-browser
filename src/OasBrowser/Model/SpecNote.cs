using System.Text.Json;

namespace OasBrowser.Model;

/// <summary>
/// One entry of `x-notes`: a place where the API's real behaviour contradicts
/// Microsoft's published documentation, or is otherwise worth calling out.
///
/// A note carries the evidence grade behind it, because the grades are not
/// equally solid and must never be shown as if they were. The axis is
/// provenance rather than confidence: `live` is a finding observed on the
/// wire; `pac-cli` comes from Microsoft's own decompiled client, which is
/// strong structural evidence but not an observation — the build can be older
/// than the running service; `provider` comes from the Terraform provider's
/// client, which is a third party's model of the API and is attested by
/// neither the wire nor Microsoft.
///
/// The shape is an array of `{"note", "source"}` objects.
/// </summary>
public sealed record SpecNote(string Text, string Source)
{
    public const string Live = "live";
    public const string PacCli = "pac-cli";
    public const string Provider = "provider";

    /// <summary>Grades in the order they should be shown; observation first.</summary>
    private static readonly string[] Order = [Live, PacCli, Provider];

    public static IReadOnlyList<SpecNote> Read(JsonElement e)
    {
        List<SpecNote>? notes = null;
        foreach (var n in OpenApiSpec.Arr(e, "x-notes"))
        {
            var note = n.ValueKind switch
            {
                JsonValueKind.Object when OpenApiSpec.Str(n, "note") is { } t
                    => new SpecNote(t, OpenApiSpec.Str(n, "source") ?? Live),
                _ => null,
            };
            if (note is not null) (notes ??= new()).Add(note);
        }
        return (IReadOnlyList<SpecNote>?)notes ?? Array.Empty<SpecNote>();
    }

    /// <summary>
    /// Notes bucketed by grade, known grades first and in <see cref="Order"/>,
    /// then anything a spec invented, so a new grade still renders — under its
    /// own heading rather than borrowed authority.
    /// </summary>
    public static IReadOnlyList<NoteGroup> Group(IReadOnlyList<SpecNote> notes)
    {
        if (notes.Count == 0) return Array.Empty<NoteGroup>();
        var seen = new List<string>();
        foreach (var n in notes)
            if (!seen.Contains(n.Source, StringComparer.Ordinal)) seen.Add(n.Source);

        return Order.Where(g => seen.Contains(g, StringComparer.Ordinal))
            .Concat(seen.Where(g => !Order.Contains(g, StringComparer.Ordinal)))
            .Select(g => NoteGroup.For(g, notes.Where(n => n.Source == g).ToList()))
            .ToList();
    }
}

/// <summary>Every note of one evidence grade, with the wording that grade earns.</summary>
public sealed record NoteGroup(string Source, string Title, string? Caveat, IReadOnlyList<SpecNote> Notes)
{
    /// <summary>True only for a grade that means "someone saw the service do this".</summary>
    public bool IsObserved => Source == SpecNote.Live;

    public static NoteGroup For(string source, IReadOnlyList<SpecNote> notes) => source switch
    {
        SpecNote.Live => new NoteGroup(source, "Verified against the live API", null, notes),
        SpecNote.PacCli => new NoteGroup(source, "From Microsoft's own client",
            "Read out of the first-party client Microsoft ships, not observed on the wire: "
            + "the build can be older than the running service.", notes),
        SpecNote.Provider => new NoteGroup(source, "From the Terraform provider's client",
            "Modelled by a third-party client, neither observed on the wire nor attested by "
            + "Microsoft's own client.", notes),
        _ => new NoteGroup(source, $"Reported by {source}",
            "An evidence grade this browser has no wording for. Treat it as unverified.", notes),
    };
}
