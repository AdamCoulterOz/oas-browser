using Keel;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using OasBrowser;
using OasBrowser.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

// The base address is the app's own base href, which is where a catalogue is
// looked for when nothing points elsewhere. It is no longer the only place
// anything is fetched from: a catalogue named by ?catalogue= can live on
// another origin, and the specs and coverage mapping it names resolve against
// that catalogue's url rather than against this one.
builder.Services.AddScoped(_ => new HttpClient { BaseAddress = new Uri(builder.HostEnvironment.BaseAddress) });
builder.Services.AddScoped<SpecStore>();
builder.Services.AddScoped<CoverageStore>();
builder.Services.AddScoped<HashRouter>();
builder.Services.AddKeel();

await builder.Build().RunAsync();
