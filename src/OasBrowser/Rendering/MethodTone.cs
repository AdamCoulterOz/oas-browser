using Keel.Components;

namespace OasBrowser.Rendering;

/// <summary>
/// The HTTP verb as a keel tone. keel draws the marker; which verb is which
/// colour is this app's domain knowledge, so the map lives here and nowhere
/// else. Every site that shows a verb reads it from this one method, so the
/// sidebar, the resource listing and the request line cannot drift apart.
///
/// A GET is safe, a POST is the informational primary act, a DELETE removes.
/// PUT and PATCH deliberately share Warning: both mutate a resource that
/// already exists, so they are one class of act, and the label says which of
/// the two a reader is looking at. A verb set of six or more mapped onto six
/// tones has to collide somewhere, and this is the cheapest place for it, so
/// the collision is a choice and not a leftover. The tone PATCH gives up is
/// New, which keel keeps for pops, a live dot or a New badge; a routine verb is
/// not a pop, whatever New happens to look like. Everything else is
/// unremarkable and grey.
/// </summary>
public static class MethodTone
{
    public static Tone For(string method) => method.ToUpperInvariant() switch
    {
        "GET" => Tone.Good,
        "POST" => Tone.Info,
        "PUT" => Tone.Warning,
        "DELETE" => Tone.Bad,
        "PATCH" => Tone.Warning,
        _ => Tone.Neutral,
    };
}
