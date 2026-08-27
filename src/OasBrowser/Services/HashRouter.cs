using Microsoft.JSInterop;

namespace OasBrowser.Services;

/// <summary>
/// Where the app is: which spec, and which operation or schema.
/// Routing is hash based deliberately. A static host needs no rewrite rules for
/// it, and the link shape (#/operations/{operationId}) is a commitment rather
/// than an implementation detail: it is already published as deep links by the
/// site this browser was first built for, so changing it would break links this
/// app does not own.
/// </summary>
public readonly record struct Route(RouteKind Kind, string? Id)
{
    public static readonly Route Overview = new(RouteKind.Overview, null);

    public static Route Parse(string? hash)
    {
        var h = (hash ?? "").TrimStart('#').Trim('/');
        if (h.Length == 0) return Overview;

        var parts = h.Split('/', 2);
        return parts[0] switch
        {
            "operations" when parts.Length > 1 => new Route(RouteKind.Operation, Uri.UnescapeDataString(parts[1])),
            "schemas" when parts.Length > 1 => new Route(RouteKind.Schema, Uri.UnescapeDataString(parts[1])),
            "resources" when parts.Length > 1 => new Route(RouteKind.Resource, Uri.UnescapeDataString(parts[1])),
            _ => Overview
        };
    }

    public string ToHash() => Kind switch
    {
        RouteKind.Operation => $"#/operations/{Id}",
        RouteKind.Schema => $"#/schemas/{Id}",
        RouteKind.Resource => $"#/resources/{Uri.EscapeDataString(Id ?? "")}",
        _ => "#/"
    };
}

public enum RouteKind { Overview, Operation, Schema, Resource }

/// <summary>
/// Reads and writes the location hash, and raises <see cref="Changed"/> for
/// back/forward navigation. The JS side is a listener and two accessors: the
/// app itself stays C#.
/// </summary>
public sealed class HashRouter(IJSRuntime js) : IAsyncDisposable
{
    private DotNetObjectReference<HashRouter>? _self;

    public event Action<Route>? Changed;

    public Route Current { get; private set; } = Route.Overview;

    public async Task InitialiseAsync()
    {
        _self = DotNetObjectReference.Create(this);
        var hash = await js.InvokeAsync<string>("oasBrowser.startHashRouter", _self);
        Current = Route.Parse(hash);
    }

    [JSInvokable]
    public void OnHashChanged(string hash)
    {
        var next = Route.Parse(hash);
        if (next == Current) return;
        Current = next;
        Changed?.Invoke(next);
    }

    public async Task GoAsync(Route route)
    {
        if (route == Current) return;
        Current = route;
        await js.InvokeVoidAsync("oasBrowser.setHash", route.ToHash());
        Changed?.Invoke(route);
    }

    public ValueTask ScrollTopAsync() => js.InvokeVoidAsync("oasBrowser.scrollTop");

    public async ValueTask DisposeAsync()
    {
        if (_self is not null)
        {
            try { await js.InvokeVoidAsync("oasBrowser.stopHashRouter"); } catch (JSDisconnectedException) { }
            _self.Dispose();
        }
    }
}
