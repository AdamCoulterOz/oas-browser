using Keel;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using OasBrowser;
using OasBrowser.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

// Every fetch resolves against the app's own base href, because specs.json and
// the specs it names are expected to be served beside index.html. That is the
// arrangement the host has to provide; the app itself knows no absolute paths.
builder.Services.AddScoped(_ => new HttpClient { BaseAddress = new Uri(builder.HostEnvironment.BaseAddress) });
builder.Services.AddScoped<SpecStore>();
builder.Services.AddScoped<HashRouter>();
builder.Services.AddKeel();

await builder.Build().RunAsync();
