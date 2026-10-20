"""04_frameworks / 10: ASP.NET Core 8/9, EF Core 8/9 y el ecosistema .NET para backend."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Minimal APIs vs controladores; organización por grupos, TypedResults y OpenAPI en .NET 9 (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Empezamos una API nueva en .NET 9. ¿Minimal APIs o controladores? Me preocupa que con Minimal APIs acabemos con un `Program.cs` de 2.000 líneas.",
            },
            {
                "role": "assistant",
                "content": r"""Para una API nueva en .NET 9, **Minimal APIs**, con una condición: que el `Program.cs` solo arranque cosas y cada funcionalidad registre sus rutas en su propio fichero. El `Program.cs` gigante no es culpa del modelo, es falta de estructura, y se evita desde el primer día.

### Cuándo elegiría cada uno

| | Minimal APIs | Controladores |
|---|---|---|
| Rendimiento y arranque | algo mejores; compatibles con Native AOT | buenos |
| Validación automática del modelo | no en .NET 8/9 (sí en .NET 10 con `AddValidation()`) | sí, con `[ApiController]` |
| Filtros | *endpoint filters*, más simples | filtros de MVC, más potentes y más complejos |
| Equipo que viene de MVC | curva corta | ninguna |
| Proyecto existente con controladores | no mezcles sin motivo | sigue igual |

Si el equipo ya domina MVC y la API es grande y homogénea, los controladores siguen siendo una opción perfectamente válida. Para un servicio nuevo, Minimal APIs da menos ceremonia y tipos de retorno que documentan solos la API.

### Estructura

```
src/Shop.Api/
  Program.cs                   # solo arranque
  Products/
    ProductEndpoints.cs        # MapProducts(): la tabla de rutas de la funcionalidad
    ProductService.cs
    ProductDtos.cs
  Orders/
    OrderEndpoints.cs
    ...
```

```csharp
// Program.cs
using Microsoft.EntityFrameworkCore;
using Shop.Api.Data;
using Shop.Api.Products;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();
builder.Services.AddProblemDetails();
builder.Services.AddDbContext<ShopDbContext>(o =>
    o.UseNpgsql(builder.Configuration.GetConnectionString("Shop")));
builder.Services.AddScoped<ProductService>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi(); // /openapi/v1.json
}
app.UseExceptionHandler();
app.UseStatusCodePages();

app.MapProducts();

app.Run();

public partial class Program { } // visible para WebApplicationFactory en los tests
```

```csharp
// Products/ProductEndpoints.cs
using Microsoft.AspNetCore.Http.HttpResults;

namespace Shop.Api.Products;

public static class ProductEndpoints
{
    public static IEndpointRouteBuilder MapProducts(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/products").WithTags("Products");

        group.MapGet("/{id:int}", GetById).WithName("GetProduct");
        group.MapPost("/", Create);

        return app;
    }

    public static async Task<Results<Ok<ProductDto>, NotFound>> GetById(
        int id, ProductService service, CancellationToken ct)
    {
        var product = await service.GetAsync(id, ct);
        return product is null ? TypedResults.NotFound() : TypedResults.Ok(product);
    }

    public static async Task<Created<ProductDto>> Create(
        CreateProductRequest request, ProductService service, CancellationToken ct)
    {
        var created = await service.CreateAsync(request, ct);
        return TypedResults.Created($"/api/products/{created.Id}", created);
    }
}
```

```csharp
// Products/ProductDtos.cs
namespace Shop.Api.Products;

public sealed record CreateProductRequest(string Name, long PriceCents, string Sku);
public sealed record ProductDto(int Id, string Name, long PriceCents, string Sku);
```

Por qué así:

- **Handlers como métodos con nombre**, no lambdas en línea: se leen, se navegan con el IDE y se prueban directamente.
- **`Results<Ok<ProductDto>, NotFound>`**: el tipo dice qué puede devolver el endpoint, y el generador de OpenAPI lo usa para documentar ambas respuestas sin atributos.
- **`MapGroup`** pone prefijo, etiquetas y, más adelante, autorización o filtros a todo el grupo de una vez.
- **OpenAPI nativo**: desde .NET 9 la plantilla ya no incluye Swashbuckle; `AddOpenApi()`/`MapOpenApi()` generan el documento y puedes añadir la interfaz que prefieras (Scalar, Swagger UI) aparte.
- **`CancellationToken` en cada handler**: se enlaza solo con `HttpContext.RequestAborted`; si el cliente se va, la consulta a la base de datos se cancela.

### Comprobación

Como los handlers son métodos estáticos que devuelven tipos concretos, el caso de «no encontrado» se prueba sin servidor:

```csharp
public class ProductEndpointsTests
{
    [Fact]
    public async Task GetById_returns_NotFound_when_missing()
    {
        var service = new ProductService(TestDb.CreateContext()); // contexto con base de datos de test

        var result = await ProductEndpoints.GetById(999, service, CancellationToken.None);

        Assert.IsType<NotFound>(result.Result);
    }
}
```

Y en desarrollo, `curl localhost:5000/openapi/v1.json` debe listar `GET /api/products/{id}` con las respuestas 200 y 404. Si solo aparece la 200, el handler está devolviendo `IResult` en vez de `Results<...>`.""",
            },
        ]
    },
    # 2) Lifetimes de DI: dependencia cautiva (scoped en singleton) en un BackgroundService (usuario trae error).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Añadí un `BackgroundService` que limpia pedidos caducados y la aplicación ya no arranca en local:

```
System.AggregateException: Some services are not able to be constructed (Error while validating the service descriptor 'ServiceType: Microsoft.Extensions.Hosting.IHostedService Lifetime: Singleton ImplementationType: Shop.Api.Orders.OrderExpiryWorker': Cannot consume scoped service 'Shop.Api.Data.ShopDbContext' from singleton 'Microsoft.Extensions.Hosting.IHostedService'.)
```

```csharp
public class OrderExpiryWorker(ShopDbContext db, ILogger<OrderExpiryWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var expired = await db.Orders.Where(o => o.Status == OrderStatus.Pending && o.CreatedAt < DateTime.UtcNow.AddHours(-1)).ToListAsync(stoppingToken);
            foreach (var order in expired) order.Status = OrderStatus.Expired;
            await db.SaveChangesAsync(stoppingToken);
            await Task.Delay(TimeSpan.FromMinutes(1), stoppingToken);
        }
    }
}
```

Lo curioso es que en el entorno de staging sí arrancaba. ¿Lo registro como scoped y listo?""",
            },
            {
                "role": "assistant",
                "content": r"""No: un `IHostedService` siempre es singleton, y que en staging arrancara **es peor**, no mejor. Te explico las dos cosas.

### Qué dice el error

Los *hosted services* se crean una vez y viven lo que vive la aplicación. `ShopDbContext` está registrado como **scoped**: pensado para vivir lo que dura una unidad de trabajo (una petición HTTP). Al inyectarlo en el constructor del worker, ese contexto quedaría capturado para siempre: es lo que se llama una **dependencia cautiva**.

En `Development`, el contenedor valida los ámbitos al construir (`ValidateScopes` y `ValidateOnBuild` están activos por defecto en ese entorno) y se niega a arrancar. En staging, con otro entorno, esa validación está desactivada: arranca, y el worker usa **un único `DbContext` durante días**. Consecuencias: el *change tracker* acumula entidades sin límite (memoria creciendo), las lecturas devuelven entidades cacheadas obsoletas y, si algo más usara ese contexto en paralelo, excepciones de concurrencia. El error de local te está salvando de eso.

### Arreglo: un ámbito por iteración

```csharp
public sealed class OrderExpiryWorker(
    IServiceScopeFactory scopeFactory,
    ILogger<OrderExpiryWorker> logger) : BackgroundService
{
    private static readonly TimeSpan Interval = TimeSpan.FromMinutes(1);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(Interval);
        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            // Un ámbito nuevo = un DbContext nuevo, que se libera al acabar la iteración.
            await using var scope = scopeFactory.CreateAsyncScope();
            var expiry = scope.ServiceProvider.GetRequiredService<OrderExpiryService>();
            var count = await expiry.ExpirePendingAsync(stoppingToken);
            if (count > 0)
            {
                logger.LogInformation("Expired {Count} pending orders", count);
            }
        }
    }
}
```

```csharp
public sealed class OrderExpiryService(ShopDbContext db, TimeProvider time)
{
    private static readonly TimeSpan MaxPendingAge = TimeSpan.FromHours(1);

    public Task<int> ExpirePendingAsync(CancellationToken ct)
    {
        var cutoff = time.GetUtcNow().UtcDateTime - MaxPendingAge;
        // Una sola sentencia UPDATE: no carga entidades en memoria (EF Core 7+).
        return db.Orders
            .Where(o => o.Status == OrderStatus.Pending && o.CreatedAt < cutoff)
            .ExecuteUpdateAsync(s => s.SetProperty(o => o.Status, OrderStatus.Expired), ct);
    }
}
```

```csharp
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddScoped<OrderExpiryService>();
builder.Services.AddHostedService<OrderExpiryWorker>();
```

Tres mejoras de paso, cada una con su motivo:

- **La lógica sale del worker** a un servicio *scoped* normal. El worker solo orquesta el ciclo; el servicio se prueba como cualquier otro.
- **`ExecuteUpdateAsync`** hace el cambio en una sentencia en la base de datos, en vez de traer todos los pedidos caducados a memoria y guardarlos uno a uno.
- **`TimeProvider`** (.NET 8) en vez de `DateTime.UtcNow`: en los tests puedes fijar la hora.

Queda un punto que no es de lifetimes pero sí de workers: si una iteración lanza una excepción (la base de datos se reinicia, por ejemplo), por defecto el host entero se detiene. Envuelve el cuerpo del bucle en un `try/catch` que registre el error y siga con la siguiente iteración.

### Regla general de lifetimes

| Quien depende | Puede recibir |
|---|---|
| Singleton | solo singletons |
| Scoped | singletons y scoped |
| Transient | cualquiera (pero hereda el problema si lo consume un singleton) |

Nunca inyectes algo de vida más corta en algo de vida más larga. Si un singleton necesita algo scoped, recibe `IServiceScopeFactory` (como aquí) o, para `DbContext` en concreto, `IDbContextFactory<T>`.

### Comprobación

Haz que la validación sea igual en todos los entornos y que la cubra un test:

```csharp
builder.Host.UseDefaultServiceProvider(o =>
{
    o.ValidateScopes = true;
    o.ValidateOnBuild = true;
});
```

```csharp
public class ServiceRegistrationTests
{
    [Fact]
    public void All_services_can_be_built()
    {
        using var factory = new WebApplicationFactory<Program>();
        var exception = Record.Exception(() => factory.Services);
        Assert.Null(exception);
    }
}
```

Con el worker original, este test falla con el mismo mensaje que viste; con el arreglo, pasa. Y ya no dependes de en qué entorno se despliega para enterarte.""",
            },
        ]
    },
    # 3) Orden del pipeline de middleware: CORS después de autorización; middleware propio; después dónde va UseExceptionHandler (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Nuestro frontend (otro dominio) recibe errores de CORS en todas las llamadas a endpoints protegidos, pero los públicos funcionan. El `Program.cs`:

```csharp
app.UseHttpsRedirection();
app.UseAuthentication();
app.UseAuthorization();
app.UseCors("frontend");
app.MapControllers();
```

La política `frontend` permite el origen del SPA, cualquier cabecera y cualquier método.""",
            },
            {
                "role": "assistant",
                "content": r"""El problema es el **orden**: `UseCors` va después de `UseAuthorization`, y en ASP.NET Core los middlewares se ejecutan en el orden en que los registras.

Lo que pasa con un endpoint protegido:

1. El navegador manda primero un *preflight* `OPTIONS` (por la cabecera `Authorization` o el `Content-Type: application/json`). El preflight **nunca lleva credenciales**.
2. `UseAuthorization` ve una petición anónima a un endpoint con `[Authorize]` y responde 401.
3. Esa respuesta sale sin cabeceras CORS, porque `UseCors` no llegó a ejecutarse. El navegador no puede ni leer el 401: informa de un «error de CORS».

En los públicos no hay 401, la petición llega a `UseCors` y todo funciona. Por eso el síntoma parecía de CORS y la causa era de orden.

El orden recomendado:

```csharp
app.UseExceptionHandler();
app.UseHttpsRedirection();
app.UseCors("frontend");      // antes de autenticación: el preflight se responde aquí
app.UseAuthentication();
app.UseAuthorization();
app.UseMiddleware<CorrelationIdMiddleware>();
app.MapControllers();
```

`UseRouting` no aparece porque `WebApplication` lo añade solo al principio. Si alguna vez lo escribes de forma explícita, `UseCors` tiene que ir **después** de `UseRouting` y **antes** de `UseAuthentication`.

Ya que estás tocando el pipeline, así se escribe un middleware propio reutilizable (el `CorrelationIdMiddleware` de arriba):

```csharp
public sealed class CorrelationIdMiddleware(RequestDelegate next, ILogger<CorrelationIdMiddleware> logger)
{
    public const string HeaderName = "X-Correlation-Id";
    private const int MaxLength = 64;

    public async Task InvokeAsync(HttpContext context)
    {
        var incoming = context.Request.Headers[HeaderName].ToString();
        var correlationId = IsValid(incoming) ? incoming : Guid.NewGuid().ToString("N");

        // OnStarting: la cabecera se añade justo antes de enviar la respuesta, sea cual sea el camino.
        context.Response.OnStarting(() =>
        {
            context.Response.Headers[HeaderName] = correlationId;
            return Task.CompletedTask;
        });

        using (logger.BeginScope(new Dictionary<string, object> { ["CorrelationId"] = correlationId }))
        {
            await next(context);
        }
    }

    private static bool IsValid(string value) =>
        value.Length is > 0 and <= MaxLength && value.All(c => char.IsAsciiLetterOrDigit(c) || c == '-');
}
```

El `IsValid` evita aceptar cualquier cosa que mande el cliente: sin él, alguien puede meter saltos de línea o 10 KB en tus logs.

Comprobación del arreglo de CORS, con un preflight simulado:

```bash
curl -i -X OPTIONS https://localhost:5001/api/orders \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization"
# Esperado: 204 con Access-Control-Allow-Origin: https://app.example.com
```

Antes del cambio, ese mismo comando devuelve 401 sin cabeceras `Access-Control-*`.""",
            },
            {
                "role": "user",
                "content": "Gracias. Otra duda del mismo estilo: tengo `UseExceptionHandler` configurado con ProblemDetails, pero cuando el error salta dentro de mi `CorrelationIdMiddleware` el cliente recibe un 500 vacío. ¿Por qué?",
            },
            {
                "role": "assistant",
                "content": r"""Mismo principio: un middleware solo puede capturar excepciones de lo que se ejecuta **después** de él, porque funciona envolviendo la llamada a `next`. Si en tu `Program.cs` real `UseExceptionHandler` está registrado más abajo que `CorrelationIdMiddleware`, una excepción en este último sube por encima del manejador y la atrapa Kestrel, que responde 500 sin cuerpo.

Piensa en el pipeline como capas de cebolla:

```
UseExceptionHandler      ← captura todo lo de dentro
  UseHttpsRedirection
    UseCors
      UseAuthentication
        UseAuthorization
          CorrelationIdMiddleware
            endpoint
```

Por eso `UseExceptionHandler` va **el primero**. En el orden que te propuse ya lo está; si aun así ves el 500 vacío, hay dos causas más que comprobar:

1. **La respuesta ya había empezado.** Si la excepción ocurre después de que se enviaran las cabeceras (por ejemplo, a mitad de escribir un cuerpo grande o un *stream*), ya no se puede cambiar el status ni escribir ProblemDetails. El manejador lo detecta, lo registra y deja la conexión cortada. Se ve en el log como `The response has already started, the error handler will not be executed`.
2. **Falta `AddProblemDetails()`.** Sin ese servicio, `UseExceptionHandler()` sin parámetros no sabe qué escribir.

Para confirmarlo, una prueba de integración que haga fallar **tu** middleware. El truco es sustituir su logger por uno que lanza en `BeginScope`, que es lo primero que el middleware usa:

```csharp
[Fact]
public async Task Exception_in_correlation_middleware_returns_problem_details()
{
    await using var factory = new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
        b.ConfigureTestServices(s =>
            s.AddSingleton<ILogger<CorrelationIdMiddleware>, ThrowingLogger>()));
    var client = factory.CreateClient();

    var response = await client.GetAsync("/api/products/1");

    Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
    Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
}

// Un registro cerrado de ILogger<T> tiene prioridad sobre el genérico abierto de AddLogging.
file sealed class ThrowingLogger : ILogger<CorrelationIdMiddleware>
{
    public IDisposable? BeginScope<TState>(TState state) where TState : notnull =>
        throw new InvalidOperationException("boom");

    public bool IsEnabled(LogLevel logLevel) => false;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
    }
}
```

Si el test da un cuerpo vacío o un `Content-Type` distinto, el orden sigue mal o falta `AddProblemDetails()`. Con `UseExceptionHandler` el primero del pipeline, pasa.""",
            },
        ]
    },
    # 4) IOptions, IOptionsSnapshot e IOptionsMonitor con validación al arrancar (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cuál es la diferencia real entre `IOptions<T>`, `IOptionsSnapshot<T>` e `IOptionsMonitor<T>`? Y ya que estamos: ¿cómo hago que la app no arranque si falta una configuración obligatoria?",
            },
            {
                "role": "assistant",
                "content": r"""Los tres leen la misma sección de configuración; cambian **cuándo** se recalcula el valor y **dónde** puedes inyectarlos.

| | Lifetime | Cuándo se lee | Úsalo para |
|---|---|---|---|
| `IOptions<T>` | singleton | una vez, la primera vez que se pide `.Value` | casi todo: configuración que no cambia sin reiniciar |
| `IOptionsSnapshot<T>` | scoped | una vez por petición | valores que pueden cambiar en caliente y que quieres consistentes durante toda una petición |
| `IOptionsMonitor<T>` | singleton | siempre el actual (`CurrentValue`), con aviso de cambios (`OnChange`) | singletons y servicios en segundo plano que deben reaccionar a cambios |

Dos matices que se olvidan:

- **`IOptionsSnapshot<T>` no se puede inyectar en un singleton** (es scoped). Si lo necesitas en uno, es `IOptionsMonitor<T>`.
- **«En caliente» solo funciona si el proveedor recarga.** `appsettings.json` se recarga al cambiar el fichero (`reloadOnChange` está activo por defecto); las variables de entorno no cambian sin reiniciar el proceso. En Kubernetes, con configuración por variables de entorno, en la práctica todo es `IOptions<T>`.

### Validación al arrancar

```csharp
using System.ComponentModel.DataAnnotations;

public sealed class PaymentsOptions
{
    public const string SectionName = "Payments";

    [Required, Url]
    public string BaseUrl { get; set; } = "";

    [Required, MinLength(20)]
    public string ApiKey { get; set; } = "";

    [Range(1, 60)]
    public int TimeoutSeconds { get; set; } = 5;
}
```

```csharp
builder.Services.AddOptions<PaymentsOptions>()
    .BindConfiguration(PaymentsOptions.SectionName)
    .ValidateDataAnnotations()
    .Validate(o => !o.BaseUrl.StartsWith("http://", StringComparison.OrdinalIgnoreCase),
              "Payments:BaseUrl debe usar https")
    .ValidateOnStart();
```

Lo que hace cada línea:

- **`BindConfiguration`** enlaza la sección `Payments` sin que tengas que pasar el `IConfiguration` a mano.
- **`ValidateDataAnnotations`** aplica los atributos; **`Validate`** añade reglas que no caben en un atributo.
- **`ValidateOnStart`** es lo que responde a tu pregunta. Sin él, la validación ocurre la primera vez que alguien pide `.Value`, que puede ser la primera petición de pago, horas después del despliegue. Con él, el host no arranca y el error dice qué propiedad falla:

```
Microsoft.Extensions.Options.OptionsValidationException: DataAnnotation validation failed for 'PaymentsOptions' members: 'ApiKey' with the error: 'The ApiKey field is required.'.
```

Uso en un servicio:

```csharp
public sealed class PaymentsClient(HttpClient http, IOptions<PaymentsOptions> options)
{
    private readonly PaymentsOptions _options = options.Value; // ya validado al arrancar

    public Task<HttpResponseMessage> PingAsync(CancellationToken ct) =>
        http.GetAsync(new Uri(new Uri(_options.BaseUrl), "ping"), ct);
}
```

Si apuntas a Native AOT, la validación por reflexión no está disponible: .NET 8 trae un generador de código (`[OptionsValidator]` sobre una clase `partial` que implementa `IValidateOptions<T>`) que produce el mismo resultado sin reflexión.

### Comprobación

```csharp
public class PaymentsOptionsTests
{
    [Fact]
    public void Missing_api_key_fails_validation()
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Payments:BaseUrl"] = "https://pay.example.com",
            })
            .Build();

        var services = new ServiceCollection();
        services.AddSingleton<IConfiguration>(configuration);
        services.AddOptions<PaymentsOptions>()
            .BindConfiguration(PaymentsOptions.SectionName)
            .ValidateDataAnnotations();
        using var provider = services.BuildServiceProvider();

        var ex = Assert.Throws<OptionsValidationException>(
            () => provider.GetRequiredService<IOptions<PaymentsOptions>>().Value);
        Assert.Contains("ApiKey", ex.Message);
    }
}
```

Y la prueba de verdad: arranca la aplicación sin `Payments__ApiKey` definido. Debe terminar en segundos con el mensaje de arriba, no quedarse escuchando en el puerto.""",
            },
        ]
    },
    # 5) Configuración: variables de entorno con "__" en Linux y precedencia; después user-secrets (multiturno, usuario trae bug).
    {
        "messages": [
            {
                "role": "user",
                "content": "En Windows hacemos `set Payments:ApiKey=xxx` y la app la usa. En el contenedor Linux, el script de arranque hace `export Payments:ApiKey=$PAYMENTS_KEY` antes de `dotnet Shop.Api.dll`, y la app sigue usando el valor de `appsettings.json`. ¿Qué cambia entre sistemas?",
            },
            {
                "role": "assistant",
                "content": r"""Cambia lo que admite cada shell en el **nombre** de una variable. En Windows, `set` acepta `:` y .NET lo interpreta como separador de secciones. En bash y sh, un nombre de variable solo puede tener letras, dígitos y `_`: tu `export` falla con `export: 'Payments:ApiKey=...': not a valid identifier`, el mensaje sale por stderr, el script sigue (no tiene `set -e`) y la aplicación arranca sin la variable. Por eso usa el valor del JSON sin quejarse.

La forma portable es el **doble guion bajo**: .NET convierte `__` en `:` al leer variables de entorno, en cualquier sistema.

```bash
#!/bin/sh
set -eu                                   # que un export fallido pare el arranque
export Payments__ApiKey="$PAYMENTS_KEY"
exec dotnet Shop.Api.dll                  # exec: dotnet pasa a ser el PID 1 y recibe SIGTERM
```

Y si lo pasas desde compose, igual:

```yaml
# docker-compose.yml
services:
  api:
    image: shop-api:latest
    environment:
      ASPNETCORE_ENVIRONMENT: Production
      Payments__ApiKey: ${PAYMENTS_API_KEY}
      ConnectionStrings__Shop: ${SHOP_DB}
```

Úsalo también en Windows y en Kubernetes: un solo formato en todas partes.

### Precedencia, para saber quién gana

Con `WebApplication.CreateBuilder`, de menor a mayor prioridad:

1. `appsettings.json`
2. `appsettings.{Environment}.json`
3. *User secrets* (solo en `Development`)
4. Variables de entorno
5. Argumentos de línea de comandos

Lo que está más abajo sobrescribe lo de arriba, clave a clave.

### Cómo comprobar qué valor ve la aplicación y de dónde viene

`IConfigurationRoot.GetDebugView()` lista cada clave con su valor y el proveedor que lo aportó. Úsalo un momento en desarrollo, **enmascarando los secretos**:

```csharp
if (app.Environment.IsDevelopment())
{
    var root = (IConfigurationRoot)app.Configuration;
    Console.WriteLine(root.GetDebugView(ctx =>
        ctx.Key.Contains("Key", StringComparison.OrdinalIgnoreCase)
        || ctx.Key.Contains("Password", StringComparison.OrdinalIgnoreCase)
            ? "***"
            : ctx.Value ?? ""));
}
```

La salida tiene líneas como `ApiKey=*** (EnvironmentVariablesConfigurationProvider Prefix: '')`. Si en el contenedor ves `(JsonConfigurationProvider for 'appsettings.json' (Optional))`, la variable no está llegando con el nombre esperado.

Y desde fuera, sin tocar código:

```bash
docker compose exec api printenv | grep -i payments
# Payments__ApiKey=...
```

Si `printenv` no muestra la variable, el problema está en el `compose` o en la plataforma, no en .NET.""",
            },
            {
                "role": "user",
                "content": "Vale. ¿Y en local cómo manejamos los secretos sin meterlos en `appsettings.Development.json`, que acaba en el repo?",
            },
            {
                "role": "assistant",
                "content": r"""Con **user secrets**: un fichero JSON fuera del repositorio, en tu perfil de usuario, que .NET carga automáticamente cuando el entorno es `Development`.

```bash
cd src/Shop.Api
dotnet user-secrets init                       # añade <UserSecretsId> al .csproj
dotnet user-secrets set "Payments:ApiKey" "clave-de-sandbox"
dotnet user-secrets set "ConnectionStrings:Shop" "Host=localhost;Database=shop;Username=shop;Password=shop"
dotnet user-secrets list
```

Aquí sí se usa `:`: es la clave de configuración, no el nombre de una variable de entorno.

El fichero vive en `%APPDATA%\Microsoft\UserSecrets\<id>\secrets.json` en Windows y en `~/.microsoft/usersecrets/<id>/secrets.json` en Linux y macOS. `WebApplication.CreateBuilder` lo añade solo en `Development`, entre los `appsettings` y las variables de entorno.

Lo que conviene saber para no llevarse sorpresas:

- **No está cifrado.** Es un JSON en tu disco. Protege contra subir secretos al repositorio, no contra alguien con acceso a tu máquina.
- **No existe fuera de `Development`.** En staging y producción, los secretos llegan por variables de entorno inyectadas por la plataforma o por un proveedor de configuración del gestor de secretos de tu nube.
- **Documenta qué claves hacen falta.** Deja en `appsettings.json` las claves con valor vacío y un comentario en el README con los `dotnet user-secrets set` necesarios. Junto con el `ValidateOnStart`, un compañero nuevo sabe en el primer arranque qué le falta.

Para que no vuelva a entrar un secreto en el repositorio, añade un escáner en el *pre-commit* o en CI (gitleaks, por ejemplo). Y si alguno ya se subió, cámbialo: borrarlo del fichero no lo borra del historial.

Comprobación: con el secreto definido, `dotnet run` arranca; `dotnet user-secrets remove "Payments:ApiKey"` y vuelve a arrancar: la validación al inicio debe fallar diciendo que falta `ApiKey`.""",
            },
        ]
    },
    # 6) EF Core: DbContext, configuración por tipo, migraciones y cómo aplicarlas en producción.
    {
        "messages": [
            {
                "role": "user",
                "content": "Con EF Core 9 y Postgres, ¿cuál es el flujo correcto de migraciones? Ahora mismo hacemos `db.Database.Migrate()` al arrancar la app y tenemos 3 réplicas en Kubernetes.",
            },
            {
                "role": "assistant",
                "content": r"""Migrar al arrancar funciona en un portátil y da problemas en producción. EF Core 9 añadió un bloqueo para que dos réplicas no apliquen migraciones a la vez, así que el choque directo ya no es el riesgo principal. Lo que sigue estando mal:

- **Permisos.** La aplicación necesita permisos de DDL (`CREATE`, `ALTER`, `DROP`) en producción solo para migrar. El usuario con el que atiende peticiones no debería tenerlos.
- **Fallos a mitad de despliegue.** Si la migración falla, las réplicas entran en bucle de reinicios y el despliegue se queda a medias, con la versión vieja y la nueva mezcladas.
- **Migraciones largas.** Un `ALTER` sobre una tabla grande hace que la aplicación tarde minutos en arrancar, y las sondas de Kubernetes la matan antes de terminar.

El flujo que propongo separa «cambiar el esquema» de «arrancar la aplicación».

### 1. Modelo y configuración

```csharp
public sealed class ShopDbContext(DbContextOptions<ShopDbContext> options) : DbContext(options)
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Product> Products => Set<Product>();

    protected override void OnModelCreating(ModelBuilder modelBuilder) =>
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ShopDbContext).Assembly);
}

internal sealed class ProductConfiguration : IEntityTypeConfiguration<Product>
{
    public void Configure(EntityTypeBuilder<Product> builder)
    {
        builder.ToTable("products");
        builder.Property(p => p.Name).HasMaxLength(120).IsRequired();
        builder.Property(p => p.Sku).HasMaxLength(8).IsRequired();
        builder.HasIndex(p => p.Sku).IsUnique();
    }
}
```

Una clase de configuración por entidad mantiene el `DbContext` corto, y el esquema se revisa junto a la entidad.

### 2. Crear migraciones (desarrollo)

```bash
dotnet tool install --global dotnet-ef
dotnet ef migrations add AddProductSku --project src/Shop.Api
```

Revisa **siempre** el fichero generado antes de hacer commit. Un renombrado de propiedad, por ejemplo, EF puede interpretarlo como «borrar columna + crear columna», y eso pierde datos. Si pasa, cámbialo a mano por `migrationBuilder.RenameColumn(...)`.

### 3. Comprobar en CI que no falta ninguna migración

```bash
dotnet ef migrations has-pending-model-changes --project src/Shop.Api
```

Falla si alguien cambió el modelo y no generó la migración. Desde EF Core 9, además, `Migrate()` lanza una excepción en ese mismo caso, así que el error saldría tarde y en producción; mejor en CI.

### 4. Aplicar en producción: un paso de despliegue

Genera un **bundle**, un ejecutable autocontenido que aplica las migraciones pendientes:

```bash
dotnet ef migrations bundle --project src/Shop.Api --self-contained -r linux-x64 -o efbundle
./efbundle --connection "$MIGRATIONS_CONNECTION_STRING"
```

Ejecútalo como un `Job` de Kubernetes (o un paso del pipeline) **antes** de actualizar el `Deployment`, con un usuario de base de datos que sí tiene permisos de DDL. La aplicación arranca con un usuario sin ellos.

Si tu equipo de base de datos prefiere revisar SQL, la alternativa es un script idempotente:

```bash
dotnet ef migrations script --idempotent --project src/Shop.Api -o migrate.sql
```

### 5. Migraciones compatibles con el despliegue gradual

Durante el *rolling update* conviven la versión vieja y la nueva contra el **mismo** esquema. Cada migración debe ser compatible con la versión anterior del código:

- Añadir una columna: anulable o con valor por defecto.
- Renombrar o borrar: en dos despliegues (primero el código deja de usarla, después la migración la elimina).

### Comprobación

En CI, contra un Postgres efímero (Testcontainers o un servicio del pipeline):

```bash
./efbundle --connection "$CI_DB"   # aplica todo desde cero
./efbundle --connection "$CI_DB"   # segunda vez: no debe hacer nada ni fallar
```

La segunda ejecución demuestra que el paso es repetible: si el `Job` se reintenta, no rompe nada.""",
            },
        ]
    },
    # 7) EF Core: N+1 con lazy loading, proyección a DTO, Include + AsSplitQuery y AsNoTracking (usuario trae log).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""El endpoint que lista los pedidos de un cliente tarda 2 segundos. Tenemos `UseLazyLoadingProxies()` activado y en el log de EF salen 81 consultas para un cliente con 80 pedidos:

```
info: Microsoft.EntityFrameworkCore.Database.Command[20101]
      Executed DbCommand (4ms) [Parameters=[@__customerId_0='?' (DbType = Int32)], CommandType='Text', CommandTimeout='30']
      SELECT o."Id", o."CreatedAt", o."CustomerId", o."Status" FROM orders AS o WHERE o."CustomerId" = @__customerId_0
info: Microsoft.EntityFrameworkCore.Database.Command[20101]
      Executed DbCommand (1ms) [Parameters=[@__p_0='?' (DbType = Int32)], CommandType='Text', CommandTimeout='30']
      SELECT o."Id", o."OrderId", o."ProductId", o."Quantity", o."UnitPriceCents" FROM order_lines AS o WHERE o."OrderId" = @__p_0
(la segunda se repite 80 veces)
```

El código:

```csharp
var orders = await db.Orders.Where(o => o.CustomerId == customerId).ToListAsync(ct);
return orders.Select(o => new OrderSummaryDto(o.Id, o.CreatedAt, o.Lines.Count, o.Lines.Sum(l => l.Quantity * l.UnitPriceCents)));
```""",
            },
            {
                "role": "assistant",
                "content": r"""Es un N+1 provocado por la carga diferida: 1 consulta para los pedidos y 80 más, una por pedido, cuando el `Select` en memoria toca `o.Lines`. Cada acceso a una navegación no cargada dispara una consulta. El `ToListAsync` está en el sitio equivocado: materializa los pedidos y deja todo lo demás para C#.

### Arreglo: que la base de datos haga la agregación

```csharp
var summaries = await db.Orders
    .Where(o => o.CustomerId == customerId)
    .OrderByDescending(o => o.CreatedAt)
    .Select(o => new OrderSummaryDto(
        o.Id,
        o.CreatedAt,
        o.Lines.Count,
        o.Lines.Sum(l => l.Quantity * l.UnitPriceCents)))
    .ToListAsync(ct);
```

La única diferencia es que el `Select` va **antes** del `ToListAsync`. EF traduce todo a **una** consulta SQL con subconsultas agregadas; no carga entidades, así que tampoco hay *tracking* ni proxies. Para un listado es lo ideal: trae exactamente las columnas que pinta la pantalla.

### Cuando sí necesitas las entidades completas

Por ejemplo, para mostrar el detalle con todas las líneas:

```csharp
var orders = await db.Orders
    .AsNoTracking()
    .Where(o => o.CustomerId == customerId)
    .Include(o => o.Lines)
        .ThenInclude(l => l.Product)
    .AsSplitQuery()
    .ToListAsync(ct);
```

- **`Include`** carga las líneas de forma explícita, sin carga diferida.
- **`AsSplitQuery`**: con varios `Include` de colecciones, una sola consulta con `JOIN` repite las columnas del pedido por cada línea (la «explosión cartesiana»). Partirla en una consulta por colección suele ser más rápido cuando los grafos son anchos. Con una sola colección pequeña, la consulta única (`AsSingleQuery`, el comportamiento por defecto) puede ganar: mídelo.
- **`AsNoTracking`**: si no vas a modificar, no pagues el coste de registrar cada entidad en el *change tracker*.

### Sobre la carga diferida

Te recomiendo **desactivar `UseLazyLoadingProxies()`**. Hace que cualquier acceso a una propiedad pueda ser una consulta a la base de datos, sin que el código lo muestre, y es exactamente lo que te ha pasado. Sin ella, acceder a una navegación no cargada devuelve una colección vacía o `null`; con `Include` o proyecciones explícitas, cada consulta se ve en el código. Si no puedes quitarla todavía, convierte cada carga diferida en excepción **solo en desarrollo y tests**, y así aparecen todos los puntos que dependen de ella:

```csharp
if (builder.Environment.IsDevelopment())
{
    options.ConfigureWarnings(w => w.Throw(CoreEventId.NavigationLazyLoading));
}
```

### Comprobación: un test que cuenta comandos

```csharp
public sealed class CommandCounter : DbCommandInterceptor
{
    private int _count;
    public int Count => _count;

    public override ValueTask<DbDataReader> ReaderExecutedAsync(
        DbCommand command, CommandExecutedEventData eventData, DbDataReader result,
        CancellationToken cancellationToken = default)
    {
        Interlocked.Increment(ref _count);
        return base.ReaderExecutedAsync(command, eventData, result, cancellationToken);
    }
}
```

```csharp
[Fact]
public async Task Customer_summary_uses_a_single_query()
{
    var counter = new CommandCounter();
    await using var db = TestDb.Create(counter); // añade el interceptor con options.AddInterceptors(counter)
    await TestDb.SeedOrdersAsync(db, customerId: 7, orders: 20, linesPerOrder: 3);

    var result = await new OrderQueries(db).SummariesAsync(7, CancellationToken.None);

    Assert.Equal(20, result.Count);
    Assert.Equal(1, counter.Count);
}
```

Con el código original el contador da 21; con la proyección, 1. Siembra los datos con un contexto distinto del que consulta: si es el mismo, las entidades ya están en memoria y el test no mide lo que crees.""",
            },
        ]
    },
    # 8) EF Core: transacción explícita con estrategia de reintentos (usuario trae excepción).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Activamos `EnableRetryOnFailure()` en Npgsql para aguantar cortes breves de la base de datos y ahora el endpoint de transferencias falla siempre:

```
System.InvalidOperationException: The configured execution strategy 'NpgsqlRetryingExecutionStrategy' does not support user-initiated transactions. Use the execution strategy returned by 'DbContext.Database.CreateExecutionStrategy()' to execute all the operations in the transaction as a retriable unit.
```

```csharp
await using var tx = await db.Database.BeginTransactionAsync(ct);
var from = await db.Accounts.SingleAsync(a => a.Id == req.FromId, ct);
var to = await db.Accounts.SingleAsync(a => a.Id == req.ToId, ct);
from.Withdraw(req.Amount);
to.Deposit(req.Amount);
await db.SaveChangesAsync(ct);
db.Transfers.Add(Transfer.Record(req));
await db.SaveChangesAsync(ct);
await tx.CommitAsync(ct);
```""",
            },
            {
                "role": "assistant",
                "content": r"""El mensaje es exacto: la estrategia de reintentos necesita poder **repetir la transacción entera** si se corta la conexión, y una transacción que abres tú a mano no sabe repetirla. Si la conexión cayera entre los dos `SaveChangesAsync`, reintentar solo el segundo dejaría un estado sin sentido. Por eso EF se niega en vez de hacer algo incorrecto.

### Primero: ¿hace falta la transacción explícita?

Un solo `SaveChangesAsync` ya es transaccional. Aquí tienes dos solo porque añades el `Transfer` después del primero. Si lo añades antes y guardas una vez, la transacción manual sobra y la estrategia de reintentos funciona sin más:

```csharp
from.Withdraw(req.Amount);
to.Deposit(req.Amount);
db.Transfers.Add(Transfer.Record(req));
await db.SaveChangesAsync(ct); // una transacción; reintentable por la estrategia
```

Es el cambio mínimo y el que te recomiendo si el caso real es este.

### Si de verdad necesitas varios pasos en una transacción

Por ejemplo, porque entre medias ejecutas SQL a mano o necesitas un ID generado. Entonces envuelve **todo** en la estrategia:

```csharp
var strategy = db.Database.CreateExecutionStrategy();

await strategy.ExecuteAsync(async () =>
{
    // Cada reintento empieza de cero: nada de lo cargado en un intento fallido debe sobrevivir.
    db.ChangeTracker.Clear();

    await using var tx = await db.Database.BeginTransactionAsync(ct);

    var from = await db.Accounts.SingleAsync(a => a.Id == req.FromId, ct);
    var to = await db.Accounts.SingleAsync(a => a.Id == req.ToId, ct);
    from.Withdraw(req.Amount);
    to.Deposit(req.Amount);
    await db.SaveChangesAsync(ct);

    db.Transfers.Add(Transfer.Record(req));
    await db.SaveChangesAsync(ct);

    await tx.CommitAsync(ct);
});
```

Tres reglas para que esto sea correcto:

1. **El delegado debe poder ejecutarse varias veces.** Por eso empieza con `ChangeTracker.Clear()` y vuelve a leer las cuentas: un reintento con entidades del intento anterior aplicaría la retirada dos veces sobre un saldo viejo.
2. **Nada con efectos externos dentro.** Ni emails, ni llamadas HTTP, ni mensajes a una cola. Si el delegado se reintenta, se repiten. Hazlos después del `ExecuteAsync`, o mejor con una tabla *outbox* escrita en la misma transacción.
3. **El caso del commit dudoso.** Si la conexión se corta **durante** el `CommitAsync`, no sabes si se confirmó. La estrategia reintentará y podrías transferir dos veces. Protégete con una clave de idempotencia: `Transfer` con un `RequestId` que viene del cliente y un índice único sobre él. El segundo intento choca con el índice y sabes que el primero sí se confirmó.

```csharp
builder.Property(t => t.RequestId).IsRequired();
builder.HasIndex(t => t.RequestId).IsUnique();
```

### Comprobación

Simula un fallo transitorio con un interceptor que lance una vez una excepción de Npgsql marcada como transitoria, y verifica:

- con el código original, la `InvalidOperationException` de tu traza;
- con la versión envuelta, el saldo final correcto (retirada aplicada **una** vez) y un solo `Transfer`;
- llamando dos veces con el mismo `RequestId`, la segunda falla por el índice único y los saldos no cambian.

El tercer caso es el que más importa: es lo que te protege del commit dudoso, que en producción ocurre poco, pero ocurre.""",
            },
        ]
    },
    # 9) Inglés: concurrencia optimista con EF Core (xmin en Npgsql / rowversion) y ExecuteUpdate atómico.
    {
        "messages": [
            {
                "role": "user",
                "content": "Two admins edit the same product in our back office and the last save silently wins. We use EF Core 8 with Postgres. How do I detect the conflict and return a 409? And separately, stock decrements under load sometimes go wrong.",
            },
            {
                "role": "assistant",
                "content": r"""Two different problems, two different tools: a **concurrency token** for the human edits, and an **atomic update** for the stock.

### 1. Conflicting edits: concurrency token

With Npgsql's EF Core provider (7+), map Postgres's system column `xmin` as the token. Every row update changes it, so you don't need to maintain a version column yourself:

```csharp
public sealed class Product
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public long PriceCents { get; set; }
    public int Stock { get; set; }

    [Timestamp]
    public uint Version { get; set; } // mapped to xmin by Npgsql
}
```

On SQL Server the equivalent is `[Timestamp] public byte[] Version { get; set; } = [];` mapped to `rowversion`.

Now the important part, the one most implementations miss: EF compares the token it **loaded**, not the one the admin **saw**. If you reload the product in the PUT handler, EF loads the current version and the conflict that happened minutes ago between "admin A opened the form" and "admin B saved" is invisible. The client has to send back the version it was shown, and you tell EF to use it as the original value:

```csharp
public sealed record UpdateProductRequest(string Name, long PriceCents, uint Version);
public sealed record ProductDto(int Id, string Name, long PriceCents, int Stock, uint Version);

app.MapPut("/api/admin/products/{id:int}", async Task<Results<Ok<ProductDto>, NotFound, Conflict<ProblemDetails>>> (
    int id, UpdateProductRequest request, ShopDbContext db, CancellationToken ct) =>
{
    var product = await db.Products.FindAsync([id], ct);
    if (product is null)
    {
        return TypedResults.NotFound();
    }

    // The WHERE clause of the UPDATE will use the version the admin had on screen.
    db.Entry(product).Property(p => p.Version).OriginalValue = request.Version;
    product.Name = request.Name;
    product.PriceCents = request.PriceCents;

    try
    {
        await db.SaveChangesAsync(ct);
    }
    catch (DbUpdateConcurrencyException)
    {
        return TypedResults.Conflict(new ProblemDetails
        {
            Title = "The product changed while you were editing it",
            Detail = "Reload to see the current values, then apply your changes again.",
        });
    }

    return TypedResults.Ok(new ProductDto(product.Id, product.Name, product.PriceCents, product.Stock, product.Version));
});
```

`SaveChangesAsync` issues `UPDATE ... WHERE "Id" = @id AND xmin = @version`. Zero rows affected means someone else got there first, and EF throws `DbUpdateConcurrencyException`. The response carries the new `Version` so the next edit starts from it.

### 2. Stock: don't read-modify-write

Loading a product, subtracting in C# and saving is a race: two requests read `Stock = 5`, both write 4. A concurrency token would turn that into a 409 for one of them, which is wrong for a checkout: the second customer should just get the next unit. Make the database do it in one statement (`ExecuteUpdateAsync`, EF Core 7+):

```csharp
public static async Task<bool> TryReserveAsync(ShopDbContext db, int productId, int quantity, CancellationToken ct)
{
    var affected = await db.Products
        .Where(p => p.Id == productId && p.Stock >= quantity)
        .ExecuteUpdateAsync(s => s.SetProperty(p => p.Stock, p => p.Stock - quantity), ct);
    return affected == 1; // 0: not enough stock (or no such product)
}
```

The condition and the decrement run atomically in the database, so stock can never go below zero and no request ever fails just because another one ran at the same time. Back it with a `CHECK (stock >= 0)` constraint as the last line of defense. Note that `ExecuteUpdateAsync` bypasses the change tracker: if the same `DbContext` already holds that `Product`, its in-memory `Stock` is now stale.

### Verification

```csharp
[Fact]
public async Task Stale_version_returns_409_and_keeps_first_edit()
{
    var client = _factory.CreateClient();
    var original = await client.GetFromJsonAsync<ProductDto>("/api/admin/products/1");

    var first = await client.PutAsJsonAsync("/api/admin/products/1",
        new UpdateProductRequest("Keyboard ES", original!.PriceCents, original.Version));
    var second = await client.PutAsJsonAsync("/api/admin/products/1",
        new UpdateProductRequest("Keyboard", 3999, original.Version)); // same, now stale, version

    Assert.Equal(HttpStatusCode.OK, first.StatusCode);
    Assert.Equal(HttpStatusCode.Conflict, second.StatusCode);
    var current = await client.GetFromJsonAsync<ProductDto>("/api/admin/products/1");
    Assert.Equal("Keyboard ES", current!.Name);
}
```

For the stock, run 50 concurrent `TryReserveAsync(…, quantity: 1)` against a product with `Stock = 10` (each with its own `DbContext`) and assert exactly 10 return `true` and the final stock is 0. Run it against real Postgres; the in-memory provider doesn't model either `xmin` or row locking.""",
            },
        ]
    },
    # 10) Validación en Minimal APIs con FluentValidation y endpoint filter (system variante: solo código).
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y comentarios breves."},
            {
                "role": "user",
                "content": "Minimal APIs en .NET 8: validación de los bodies con FluentValidation aplicada a todos los endpoints que la necesiten, respondiendo 400 con ValidationProblemDetails por campo. Sin repetir el `if (!result.IsValid)` en cada handler.",
            },
            {
                "role": "assistant",
                "content": r"""```csharp
// Validation/ValidationFilter.cs
using System.Text.Json;
using FluentValidation;

namespace Shop.Api.Validation;

// Filtro genérico: busca el argumento de tipo T y lo valida antes de llamar al handler.
public sealed class ValidationFilter<T> : IEndpointFilter where T : class
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var argument = context.Arguments.OfType<T>().FirstOrDefault();
        if (argument is null)
        {
            return TypedResults.Problem("El cuerpo de la petición es obligatorio.", statusCode: StatusCodes.Status400BadRequest);
        }

        // Se resuelve por petición: los validadores se registran como scoped.
        var validator = context.HttpContext.RequestServices.GetRequiredService<IValidator<T>>();
        var result = await validator.ValidateAsync(argument, context.HttpContext.RequestAborted);
        if (result.IsValid)
        {
            return await next(context);
        }

        // FluentValidation usa el nombre C# (PascalCase); el cliente ve el JSON en camelCase.
        var errors = result.Errors
            .GroupBy(e => JsonNamingPolicy.CamelCase.ConvertName(e.PropertyName))
            .ToDictionary(g => g.Key, g => g.Select(e => e.ErrorMessage).ToArray());
        return TypedResults.ValidationProblem(errors);
    }
}

public static class ValidationExtensions
{
    // Azúcar para que el endpoint diga qué valida: .WithValidation<CreateProductRequest>()
    public static RouteHandlerBuilder WithValidation<T>(this RouteHandlerBuilder builder) where T : class =>
        builder.AddEndpointFilter<ValidationFilter<T>>()
               .ProducesValidationProblem();
}
```

```csharp
// Products/CreateProductRequestValidator.cs
using FluentValidation;

namespace Shop.Api.Products;

public sealed class CreateProductRequestValidator : AbstractValidator<CreateProductRequest>
{
    public CreateProductRequestValidator()
    {
        RuleFor(x => x.Name).NotEmpty().MaximumLength(120);
        RuleFor(x => x.PriceCents).GreaterThan(0);
        RuleFor(x => x.Sku).NotEmpty().Matches("^[A-Z0-9]{8}$")
            .WithMessage("8 caracteres en mayúsculas o dígitos");
    }
}
```

```csharp
// Program.cs (fragmento)
using FluentValidation;

builder.Services.AddValidatorsFromAssemblyContaining<CreateProductRequestValidator>();

// Products/ProductEndpoints.cs (fragmento)
group.MapPost("/", Create).WithValidation<CreateProductRequest>();
group.MapPut("/{id:int}", Update).WithValidation<UpdateProductRequest>();
```

```csharp
// Tests/ProductValidationTests.cs
// JSON mal formado no llega al filtro: el enlace del body falla antes y responde 400 por su cuenta.
public sealed class ProductValidationTests(WebApplicationFactory<Program> factory)
    : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task Invalid_body_returns_400_with_errors_per_field()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/products",
            new CreateProductRequest(Name: "", PriceCents: 0, Sku: "abc"));

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        var problem = await response.Content.ReadFromJsonAsync<HttpValidationProblemDetails>();
        Assert.Equal(new[] { "name", "priceCents", "sku" }, problem!.Errors.Keys.Order(StringComparer.Ordinal));
    }

    [Fact]
    public async Task Valid_body_reaches_the_handler()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/products",
            new CreateProductRequest("Teclado", 4999, "KEYB0001"));

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
    }
}

// Nota: en .NET 10, builder.Services.AddValidation() añade validación integrada para Minimal APIs
// con DataAnnotations; en .NET 8/9 este filtro es la forma limpia de no repetir código.
```""",
            },
        ]
    },
    # 11) ProblemDetails + IExceptionHandler (.NET 8): errores de dominio centralizados y 500 sin filtrar detalles.
    {
        "messages": [
            {
                "role": "user",
                "content": "En nuestra API .NET 8 cada endpoint tiene su try/catch y devuelve errores con formatos distintos. ¿Cómo lo centralizo para que todo salga como ProblemDetails?",
            },
            {
                "role": "assistant",
                "content": r"""Con tres piezas que .NET 8 trae de serie: `AddProblemDetails()` para el formato, un `IExceptionHandler` para traducir tus excepciones y `UseExceptionHandler()` + `UseStatusCodePages()` para que cualquier error, lanzado o no, salga igual.

Antes del código, una distinción que evita la mitad de los problemas: **las excepciones son para lo excepcional**. «El producto no existe» es una respuesta esperada de un `GET`: devuélvela con `TypedResults.NotFound()` desde el endpoint. Reserva las excepciones para reglas de negocio violadas en lo profundo del dominio y para fallos de verdad. Hay además un motivo práctico: en .NET 8 y 9, el middleware registra **como error** toda excepción que le llega, aunque tu handler la convierta después en un 404, y los logs de errores se llenan de ruido.

### Excepciones de dominio

```csharp
public abstract class DomainException(string message) : Exception(message) { }

public sealed class ConflictException(string code, string message) : DomainException(message)
{
    public string Code { get; } = code;
}

public sealed class BusinessRuleException(string message) : DomainException(message) { }
```

### El traductor

```csharp
public sealed class DomainExceptionHandler(IProblemDetailsService problemDetails) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(HttpContext httpContext, Exception exception, CancellationToken cancellationToken)
    {
        if (exception is not DomainException domain)
        {
            return false; // no es nuestra: que la trate el comportamiento por defecto (500)
        }

        var status = domain switch
        {
            ConflictException => StatusCodes.Status409Conflict,
            BusinessRuleException => StatusCodes.Status422UnprocessableEntity,
            _ => StatusCodes.Status400BadRequest,
        };
        httpContext.Response.StatusCode = status;

        var context = new ProblemDetailsContext
        {
            HttpContext = httpContext,
            Exception = exception,
            ProblemDetails =
            {
                Status = status,
                Title = "La operación no se puede completar",
                Detail = exception.Message, // mensajes de dominio: escritos para el cliente
            },
        };
        if (domain is ConflictException conflict)
        {
            context.ProblemDetails.Extensions["code"] = conflict.Code;
        }
        return await problemDetails.TryWriteAsync(context);
    }
}
```

### Registro y orden

```csharp
builder.Services.AddProblemDetails(options =>
    options.CustomizeProblemDetails = ctx =>
    {
        ctx.ProblemDetails.Instance = $"{ctx.HttpContext.Request.Method} {ctx.HttpContext.Request.Path}";
        ctx.ProblemDetails.Extensions["traceId"] = Activity.Current?.Id ?? ctx.HttpContext.TraceIdentifier;
    });
builder.Services.AddExceptionHandler<DomainExceptionHandler>();

var app = builder.Build();

app.UseExceptionHandler();   // el primero: envuelve todo lo demás
app.UseStatusCodePages();    // 404 de ruta, 405, 401... sin cuerpo pasan a ProblemDetails
```

Qué consigues:

- **Una sola forma de error** para tus excepciones, para los fallos inesperados (500) y para los códigos que genera el propio framework.
- **El 500 no filtra nada.** Para excepciones que no son de dominio, el handler devuelve `false` y el middleware escribe un ProblemDetails genérico: sin mensaje interno ni traza. El detalle completo queda en el log.
- **`traceId` en cada respuesta.** Cuando un cliente reporta un error, ese valor te lleva directamente a las líneas de log y a la traza distribuida de esa petición.
- **Los endpoints pierden sus try/catch.** Solo capturan lo que de verdad saben manejar.

Puedes registrar varios `IExceptionHandler`; se ejecutan en el orden de registro hasta que uno devuelve `true`.

### Comprobación

```csharp
public sealed class ErrorFormatTests(WebApplicationFactory<Program> factory) : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task Domain_conflict_is_409_with_code()
    {
        var client = factory.CreateClient();
        await client.PostAsJsonAsync("/api/products", new { name = "Teclado", priceCents = 4999, sku = "DUPL0001" });

        var response = await client.PostAsJsonAsync("/api/products", new { name = "Otro", priceCents = 100, sku = "DUPL0001" });

        Assert.Equal(HttpStatusCode.Conflict, response.StatusCode);
        var problem = await response.Content.ReadFromJsonAsync<ProblemDetails>();
        Assert.Equal("duplicate_sku", problem!.Extensions["code"]?.ToString());
        Assert.True(problem.Extensions.ContainsKey("traceId"));
    }

    [Fact]
    public async Task Unknown_route_is_problem_json()
    {
        var response = await factory.CreateClient().GetAsync("/api/no-existe");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
    }
}
```

Añade un tercer test con un endpoint que lance `InvalidOperationException` y comprueba que la respuesta 500 **no** contiene el mensaje de la excepción. Ese es el que protege contra filtrar detalles internos el día que alguien cambie la configuración.""",
            },
        ]
    },
    # 12) JWT Bearer: User.FindFirst("sub") nulo por el mapeo de claims; después tokens propios HS256 (multiturno, usuario trae bug).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Configuré JWT Bearer en .NET 8 contra nuestro IdP y la autenticación funciona, pero `User.FindFirst("sub")` devuelve null y `User.IsInRole("admin")` da false, aunque en jwt.io veo que el token trae `"sub": "u-123"` y `"roles": ["admin"]`.

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        o.Authority = "https://sso.acme.com/realms/shop";
        o.Audience = "shop-api";
    });
```""",
            },
            {
                "role": "assistant",
                "content": r"""Los claims están ahí, pero **con otro nombre**. Por compatibilidad histórica, el manejador JWT de ASP.NET Core traduce los nombres cortos del estándar a los URI largos de WS-Federation: `sub` se convierte en `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier`. Y `IsInRole` busca el tipo de claim de rol de la identidad, que por defecto es `http://schemas.microsoft.com/ws/2008/06/identity/claims/role`, no tu `roles`.

Puedes confirmarlo en un minuto con un endpoint temporal:

```csharp
app.MapGet("/debug/claims", (ClaimsPrincipal user) =>
    user.Claims.Select(c => new { c.Type, c.Value })).RequireAuthorization();
```

Verás `nameidentifier` donde esperabas `sub`.

### Arreglo: desactivar el mapeo y declarar los tipos

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        o.Authority = "https://sso.acme.com/realms/shop";
        o.Audience = "shop-api";
        o.MapInboundClaims = false; // los claims llegan con el nombre que trae el token
        o.TokenValidationParameters.NameClaimType = "sub";
        o.TokenValidationParameters.RoleClaimType = "roles";
    });
```

- **`MapInboundClaims = false`** (en `JwtBearerOptions` desde .NET 8): se acabó la traducción. `User.FindFirst("sub")` funciona tal cual.
- **`NameClaimType = "sub"`** hace que `User.Identity.Name` devuelva el `sub`.
- **`RoleClaimType = "roles"`** hace que `IsInRole("admin")` y `[Authorize(Roles = "admin")]` miren tu claim. Si `roles` es un array en el token, el manejador crea un claim por elemento, así que funciona sin más.

Para no repetir el literal por el código:

```csharp
public static class ClaimsPrincipalExtensions
{
    public static string UserId(this ClaimsPrincipal user) =>
        user.FindFirstValue("sub") ?? throw new InvalidOperationException("Authenticated user without 'sub' claim");
}
```

### Comprobación

```csharp
[Fact]
public void Claims_keep_their_original_names()
{
    var options = new JwtBearerOptions { MapInboundClaims = false };
    options.TokenValidationParameters.NameClaimType = "sub";
    options.TokenValidationParameters.RoleClaimType = "roles";
    var identity = new ClaimsIdentity(
        [new Claim("sub", "u-123"), new Claim("roles", "admin")],
        authenticationType: "Bearer",
        nameType: options.TokenValidationParameters.NameClaimType,
        roleType: options.TokenValidationParameters.RoleClaimType);
    var user = new ClaimsPrincipal(identity);

    Assert.Equal("u-123", user.Identity!.Name);
    Assert.True(user.IsInRole("admin"));
}
```

La prueba que de verdad cierra el caso es la de integración: llama a `/debug/claims` con un token real del IdP y comprueba que aparecen `sub` y `roles` con esos nombres. Después borra el endpoint de depuración.""",
            },
            {
                "role": "user",
                "content": "Perfecto. Otro servicio no tiene IdP: emitimos nosotros los tokens con HS256 en un endpoint de login. ¿Cómo configuro la validación y la emisión?",
            },
            {
                "role": "assistant",
                "content": r"""Sin `Authority` no hay descubrimiento de claves: tienes que darle la clave y fijar tú cada comprobación. Pon la configuración del token en un solo objeto que usen tanto la emisión como la validación, para que no se desalineen.

```csharp
public sealed class JwtSettings
{
    public const string SectionName = "Jwt";

    [Required] public string Issuer { get; set; } = "";
    [Required] public string Audience { get; set; } = "";
    [Required, MinLength(32)] public string Secret { get; set; } = ""; // HS256 exige claves de al menos 256 bits
    [Range(1, 120)] public int LifetimeMinutes { get; set; } = 15;

    public SymmetricSecurityKey SigningKey() => new(Encoding.UTF8.GetBytes(Secret));
}
```

```csharp
builder.Services.AddOptions<JwtSettings>()
    .BindConfiguration(JwtSettings.SectionName)
    .ValidateDataAnnotations()
    .ValidateOnStart();

var jwt = builder.Configuration.GetSection(JwtSettings.SectionName).Get<JwtSettings>()
    ?? throw new InvalidOperationException("Missing Jwt section");

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        o.MapInboundClaims = false;
        o.TokenValidationParameters = new TokenValidationParameters
        {
            ValidIssuer = jwt.Issuer,
            ValidAudience = jwt.Audience,
            IssuerSigningKey = jwt.SigningKey(),
            ValidAlgorithms = [SecurityAlgorithms.HmacSha256],
            ClockSkew = TimeSpan.FromSeconds(30), // el valor por defecto es 5 minutos
            NameClaimType = "sub",
            RoleClaimType = "role",
        };
    });
```

La emisión, con el mismo objeto:

```csharp
public sealed class TokenIssuer(IOptions<JwtSettings> options, TimeProvider time)
{
    private readonly JwtSettings _settings = options.Value;
    private readonly JsonWebTokenHandler _handler = new();

    public string Issue(string userId, IEnumerable<string> roles)
    {
        var now = time.GetUtcNow().UtcDateTime;
        var claims = new List<Claim> { new("sub", userId) };
        claims.AddRange(roles.Select(r => new Claim("role", r)));

        return _handler.CreateToken(new SecurityTokenDescriptor
        {
            Issuer = _settings.Issuer,
            Audience = _settings.Audience,
            Subject = new ClaimsIdentity(claims),
            IssuedAt = now,
            NotBefore = now,
            Expires = now.AddMinutes(_settings.LifetimeMinutes),
            SigningCredentials = new SigningCredentials(_settings.SigningKey(), SecurityAlgorithms.HmacSha256),
        });
    }
}
```

Por qué cada ajuste:

- **`ValidAlgorithms`** acepta solo HS256: un token que declare otro algoritmo se rechaza antes de mirar la firma.
- **`ClockSkew` de 30 s.** Con los 5 minutos por defecto, un token «de 15 minutos» vale en la práctica 20.
- **`MinLength(32)`**: con menos de 256 bits, la librería de tokens se niega a firmar (error `IDX10720`), pero es mejor que lo detecte `ValidateOnStart` al arrancar que el primer login.
- **`JsonWebTokenHandler`**: es el manejador que usa ASP.NET Core 8 por dentro para validar; usar el mismo para emitir evita diferencias sutiles.

Una pregunta que conviene hacerse: si la API y su único cliente son tuyos y están en el mismo dominio, una **cookie de sesión** con ASP.NET Core Identity es más simple y más segura que JWT (revocación inmediata, nada de tokens en el almacenamiento del navegador). JWT compensa cuando hay varios consumidores o servicios que validan sin estado compartido.

Comprobación: un test de integración que emita un token con `TokenIssuer`, llame a `/debug/claims` y compruebe `sub` y `role`; otro con un token emitido con un `IssuedAt` de hace una hora (usando un `FakeTimeProvider` en el emisor), que debe dar 401; y otro firmado con otra clave, también 401.""",
            },
        ]
    },
    # 13) Autorización por políticas, requisitos con handler y autorización basada en recurso (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tenemos `[Authorize(Roles = \"admin,support\")]` repartido por todos lados y ahora necesitamos reglas tipo «un cliente solo ve sus pedidos, soporte ve todos los de su región». ¿Cómo lo modelo en ASP.NET Core 8 sin llenar los endpoints de ifs?",
            },
            {
                "role": "assistant",
                "content": r"""Con dos herramientas distintas, porque son dos tipos de regla:

- **Políticas con nombre** para reglas que dependen solo del usuario («tiene el permiso X»). Sustituyen a los roles repartidos por atributos.
- **Autorización basada en recurso** para reglas que dependen del objeto («es el dueño de **este** pedido»). No se pueden evaluar en un atributo, porque el pedido aún no se ha cargado cuando corre el atributo.

### 1. Políticas

```csharp
public static class Policies
{
    public const string ManageRefunds = "ManageRefunds";
    public const string ReadAnyOrder = "ReadAnyOrder";
}

builder.Services.AddAuthorizationBuilder()
    // Todo endpoint sin [AllowAnonymous] exige usuario autenticado: el olvido falla del lado seguro.
    .SetFallbackPolicy(new AuthorizationPolicyBuilder().RequireAuthenticatedUser().Build())
    .AddPolicy(Policies.ManageRefunds, p => p.RequireClaim("permissions", "refunds:write"))
    .AddPolicy(Policies.ReadAnyOrder, p => p.RequireRole("support", "admin"));

builder.Services.AddSingleton<IAuthorizationHandler, OrderAccessHandler>();
```

```csharp
app.MapPost("/api/refunds", CreateRefund).RequireAuthorization(Policies.ManageRefunds);
```

El endpoint dice **qué** se necesita («gestionar reembolsos»), no **quién** («admin o soporte»). Si mañana un rol nuevo puede reembolsar, cambias la política en un sitio.

### 2. Reglas sobre el recurso

```csharp
public sealed class OrderAccessRequirement : IAuthorizationRequirement { }

public sealed class OrderAccessHandler : AuthorizationHandler<OrderAccessRequirement, Order>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context, OrderAccessRequirement requirement, Order order)
    {
        var user = context.User;
        var isOwner = user.FindFirstValue("sub") == order.CustomerId;
        var isSupportInRegion = user.IsInRole("support") && user.HasClaim("region", order.Region);

        if (isOwner || isSupportInRegion || user.IsInRole("admin"))
        {
            context.Succeed(requirement);
        }
        return Task.CompletedTask; // no llamar a Fail: otro handler podría conceder el acceso
    }
}
```

```csharp
app.MapGet("/api/orders/{id:int}", async Task<Results<Ok<OrderDto>, NotFound>> (
    int id, ShopDbContext db, IAuthorizationService authorization, ClaimsPrincipal user, CancellationToken ct) =>
{
    var order = await db.Orders.AsNoTracking().FirstOrDefaultAsync(o => o.Id == id, ct);
    if (order is null)
    {
        return TypedResults.NotFound();
    }

    var result = await authorization.AuthorizeAsync(user, order, new OrderAccessRequirement());
    // 404 y no 403: a quien no tiene acceso no le confirmamos que el pedido existe.
    return result.Succeeded ? TypedResults.Ok(OrderDto.From(order)) : TypedResults.NotFound();
});
```

### 3. Los listados, en la consulta

Para «mis pedidos», no cargues todo y filtres con el handler uno por uno: traduce la misma regla a un filtro de la consulta.

```csharp
public static IQueryable<Order> VisibleTo(this IQueryable<Order> orders, ClaimsPrincipal user)
{
    if (user.IsInRole("admin"))
    {
        return orders;
    }
    var userId = user.FindFirstValue("sub");
    var regions = user.FindAll("region").Select(c => c.Value).ToList();
    return user.IsInRole("support")
        ? orders.Where(o => o.CustomerId == userId || regions.Contains(o.Region))
        : orders.Where(o => o.CustomerId == userId);
}
```

Aquí la regla existe dos veces (handler y filtro), y eso es una deuda. Mitígala con un test que recorra los mismos casos contra ambos.

### Comprobación

El handler se prueba sin servidor:

```csharp
public class OrderAccessHandlerTests
{
    private static ClaimsPrincipal User(params Claim[] claims) =>
        new(new ClaimsIdentity(claims, "test", "sub", "role"));

    [Theory]
    [InlineData("c-1", null, null, true)]          // dueño
    [InlineData("c-2", null, null, false)]         // otro cliente
    [InlineData("s-1", "support", "EU", true)]     // soporte de la región del pedido
    [InlineData("s-1", "support", "US", false)]    // soporte de otra región
    public async Task Evaluates_access(string sub, string? role, string? region, bool expected)
    {
        var claims = new List<Claim> { new("sub", sub) };
        if (role is not null) claims.Add(new Claim("role", role));
        if (region is not null) claims.Add(new Claim("region", region));
        var order = new Order { Id = 1, CustomerId = "c-1", Region = "EU" };
        var context = new AuthorizationHandlerContext([new OrderAccessRequirement()], User([.. claims]), order);

        await new OrderAccessHandler().HandleAsync(context);

        Assert.Equal(expected, context.HasSucceeded);
    }
}
```

Usa estos mismos cuatro casos en un test de `VisibleTo` contra la base de datos de test: si un día divergen, el test te lo dirá antes que un cliente.""",
            },
        ]
    },
    # 14) ASP.NET Core Identity (.NET 8): MapIdentityApi vs IdP externo; después cookies para una SPA (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Vi que .NET 8 trae `MapIdentityApi` con registro, login y refresh ya hechos. ¿Lo uso para el login de nuestra SPA o es mejor montar Keycloak o Entra ID?",
            },
            {
                "role": "assistant",
                "content": r"""Depende de una pregunta: **¿cuántas aplicaciones van a autenticar usuarios contra esto?**

`MapIdentityApi` expone endpoints JSON (`/register`, `/login`, `/refresh`, `/confirmEmail`, `/manage/2fa`...) sobre ASP.NET Core Identity. Es una buena opción cuando:

- Hay **una** aplicación (tu SPA y tu API) y nadie más necesita esos usuarios.
- No necesitas inicio de sesión único entre varias aplicaciones, ni federación con Google o con el directorio corporativo, ni que terceros obtengan tokens.

No es un servidor OpenID Connect. Si mañana aparece una segunda aplicación que debe compartir usuarios, una app móvil de terceros o un requisito de SSO, necesitas un proveedor de identidad (Keycloak, Entra ID, Auth0) o montar uno con OpenIddict. Migrar usuarios después es posible, pero es un proyecto.

Si encaja, el montaje es corto:

```csharp
builder.Services.AddDbContext<AppIdentityDbContext>(o =>
    o.UseNpgsql(builder.Configuration.GetConnectionString("Identity")));

builder.Services.AddIdentityApiEndpoints<IdentityUser>(o =>
    {
        o.Password.RequiredLength = 12;
        o.Lockout.MaxFailedAccessAttempts = 5;
        o.SignIn.RequireConfirmedEmail = true;
    })
    .AddEntityFrameworkStores<AppIdentityDbContext>();

builder.Services.AddAuthorization();

// Con varias réplicas, las claves de Data Protection deben ser compartidas.
builder.Services.AddDataProtection()
    .PersistKeysToDbContext<AppIdentityDbContext>()
    .SetApplicationName("shop");

var app = builder.Build();

app.MapGroup("/account").MapIdentityApi<IdentityUser>();
```

```csharp
public sealed class AppIdentityDbContext(DbContextOptions<AppIdentityDbContext> options)
    : IdentityDbContext<IdentityUser>(options), IDataProtectionKeyContext
{
    public DbSet<DataProtectionKey> DataProtectionKeys => Set<DataProtectionKey>();
}
```

Dos detalles que no están en el ejemplo de la documentación y que dan problemas en producción:

- **Los tokens *bearer* de Identity no son JWT.** Son tokens propios protegidos con Data Protection; solo los valida la misma aplicación. No los puede validar otro servicio.
- **Data Protection con varias réplicas.** Cookies y tokens se cifran con claves que, por defecto, viven en el disco del contenedor. Con 3 réplicas, cada una tiene las suyas: un usuario que inicia sesión en la réplica A recibe 401 en la B, y todos pierden la sesión en cada despliegue. Por eso `PersistKeysToDbContext` (o Redis, o almacenamiento de blobs).

Comprobación: con dos instancias de la API apuntando a la misma base de datos, inicia sesión contra una y llama a un endpoint protegido de la otra con la misma cookie o token. Debe responder 200. Sin la persistencia compartida, verás el 401.""",
            },
            {
                "role": "user",
                "content": "Vamos con `MapIdentityApi`. Para la SPA, ¿uso la cookie (`useCookies=true`) o el bearer token guardado en el navegador?",
            },
            {
                "role": "assistant",
                "content": r"""**Cookie**, si la SPA y la API se sirven desde el mismo sitio (mismo dominio registrable, por ejemplo `app.acme.com` y `api.acme.com`, o la SPA servida por la propia API).

La razón es dónde vive el secreto:

| | Cookie `HttpOnly` | Token en `localStorage` |
|---|---|---|
| Accesible desde JavaScript | no | sí |
| Si hay una vulnerabilidad XSS | el atacante puede hacer peticiones mientras la página está abierta, pero no se lleva la credencial | se lleva el token y lo usa desde su máquina hasta que caduque |
| CSRF | hay que protegerse (SameSite + cabecera) | no aplica |
| Varios dominios no relacionados | complicado | sencillo |

Configuración de la cookie para una API:

```csharp
builder.Services.ConfigureApplicationCookie(o =>
{
    o.Cookie.Name = "shop.auth";
    o.Cookie.HttpOnly = true;
    o.Cookie.SecurePolicy = CookieSecurePolicy.Always;
    o.Cookie.SameSite = SameSiteMode.Strict;
    o.ExpireTimeSpan = TimeSpan.FromHours(8);
    o.SlidingExpiration = true;

    // Una API no redirige a una página de login: responde 401/403.
    o.Events.OnRedirectToLogin = ctx =>
    {
        ctx.Response.StatusCode = StatusCodes.Status401Unauthorized;
        return Task.CompletedTask;
    };
    o.Events.OnRedirectToAccessDenied = ctx =>
    {
        ctx.Response.StatusCode = StatusCodes.Status403Forbidden;
        return Task.CompletedTask;
    };
});
```

**CSRF.** Con `SameSite=Strict`, el navegador no envía la cookie en peticiones iniciadas desde otro sitio, lo que bloquea el CSRF clásico. Como segunda capa, exige una cabecera propia en las peticiones que modifican datos: un formulario de otro sitio no puede añadir cabeceras y una petición `fetch` entre orígenes con cabeceras propias necesita un *preflight* que tu política CORS rechaza.

```csharp
public sealed class RequireAjaxHeaderFilter : IEndpointFilter
{
    public ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var request = context.HttpContext.Request;
        var isUnsafe = !HttpMethods.IsGet(request.Method) && !HttpMethods.IsHead(request.Method)
                       && !HttpMethods.IsOptions(request.Method);
        if (isUnsafe && request.Headers["X-Requested-With"] != "fetch")
        {
            return ValueTask.FromResult<object?>(TypedResults.Problem("Missing X-Requested-With header", statusCode: 400));
        }
        return next(context);
    }
}

var api = app.MapGroup("/api").AddEndpointFilter<RequireAjaxHeaderFilter>();
```

En la SPA, un envoltorio de `fetch` con `credentials: "include"` y la cabecera `X-Requested-With: fetch` en todas las llamadas.

Si la SPA estuviera en un dominio totalmente distinto, `SameSite=Strict` impediría enviar la cookie. En ese caso, la opción robusta es un **BFF**: un backend pequeño en el dominio de la SPA que guarda la sesión con cookie y llama a la API con el token del lado del servidor. El token nunca llega al navegador.

Comprobación:

1. Login con `POST /account/login?useCookies=true`: la respuesta trae `Set-Cookie` con `HttpOnly; Secure; SameSite=Strict`.
2. `document.cookie` en la consola del navegador no muestra `shop.auth`.
3. Un `POST` a la API sin la cabecera `X-Requested-With` devuelve 400; con ella, 200.
4. Un endpoint protegido sin cookie devuelve 401, no un 302 a `/Account/Login`.""",
            },
        ]
    },
    # 15) Logging estructurado: plantillas vs interpolación, LoggerMessage, scopes, Serilog o consola JSON.
    {
        "messages": [
            {
                "role": "user",
                "content": "El analizador de .NET me marca `CA2254` en `logger.LogInformation($\"Pedido {order.Id} creado\")`. Funciona igual, ¿no? ¿Por qué tanto lío con el logging?",
            },
            {
                "role": "assistant",
                "content": r"""No funciona igual. Con interpolación (`$"..."`) el mensaje se construye **antes** de llegar al logger, y el logger solo recibe un texto. Con una plantilla, recibe el texto **y** los valores por separado:

```csharp
// Interpolación: un string. El sistema de logs ve «Pedido 123 creado».
logger.LogInformation($"Pedido {order.Id} creado");

// Plantilla: el sistema de logs ve el mensaje y una propiedad OrderId = 123.
logger.LogInformation("Pedido {OrderId} creado", order.Id);
```

Lo que pierdes con la interpolación:

1. **Búsqueda por campo.** En Seq, Elastic, Loki o Application Insights, con plantillas puedes filtrar `OrderId = 123` o agrupar por cliente. Con texto, solo te queda buscar con comodines.
2. **Agrupación por tipo de mensaje.** Todas las líneas de «Pedido {OrderId} creado» comparten plantilla; con interpolación, cada línea es un mensaje distinto.
3. **Rendimiento.** La interpolación construye el string aunque el nivel esté desactivado. Con la plantilla, si `Information` no está habilitado, no se formatea nada.

### Para los logs frecuentes: `LoggerMessage`

El generador de código de .NET crea métodos de log fuertemente tipados que no reservan memoria cuando el nivel está desactivado y validan la plantilla al compilar:

```csharp
public static partial class OrderLog
{
    [LoggerMessage(EventId = 1001, Level = LogLevel.Information,
        Message = "Order {OrderId} placed by {CustomerId} for {TotalCents} cents")]
    public static partial void OrderPlaced(this ILogger logger, int orderId, string customerId, long totalCents);

    [LoggerMessage(EventId = 1002, Level = LogLevel.Warning,
        Message = "Payment declined for order {OrderId}: {Reason}")]
    public static partial void PaymentDeclined(this ILogger logger, int orderId, string reason);
}

// Uso
logger.OrderPlaced(order.Id, order.CustomerId, order.TotalCents);
```

Los `EventId` te dan además un identificador estable para alertas («avísame si el 1002 supera 50 por minuto»).

### Contexto compartido: scopes

Para que todas las líneas de una operación lleven el mismo dato sin pasarlo a cada llamada:

```csharp
using (logger.BeginScope(new Dictionary<string, object> { ["TenantId"] = tenantId, ["OrderId"] = order.Id }))
{
    await payments.ChargeAsync(order, ct);   // sus logs también llevan TenantId y OrderId
    logger.OrderPlaced(order.Id, order.CustomerId, order.TotalCents);
}
```

### Salida: ¿hace falta Serilog?

No siempre. Si tu plataforma recoge la salida estándar, el formateador JSON integrado basta:

```csharp
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(o => o.IncludeScopes = true);
```

Serilog compensa cuando quieres enriquecedores, varios destinos o su ecosistema de *sinks*:

```csharp
// Serilog.AspNetCore
builder.Services.AddSerilog((services, lc) => lc
    .ReadFrom.Configuration(builder.Configuration)
    .ReadFrom.Services(services)
    .Enrich.FromLogContext()
    .WriteTo.Console(new Serilog.Formatting.Compact.RenderedCompactJsonFormatter()));

var app = builder.Build();
app.UseSerilogRequestLogging(); // una línea por petición con método, ruta, status y duración
```

Con las plantillas bien escritas, cambiar de uno a otro no toca el código de la aplicación: solo esta configuración.

Una regla de contenido: **nunca registres secretos ni datos personales completos** (tokens, contraseñas, números de tarjeta, emails enteros). Una vez en el sistema de logs, se replican y se retienen fuera de tu control.

### Comprobación

`FakeLogger` (paquete `Microsoft.Extensions.Diagnostics.Testing`, .NET 8) captura los registros con sus propiedades:

```csharp
[Fact]
public void OrderPlaced_logs_structured_fields()
{
    var logger = new FakeLogger<OrderService>();

    logger.OrderPlaced(42, "c-7", 1999);

    var record = logger.Collector.LatestRecord;
    Assert.Equal(1001, record.Id.Id);
    Assert.Contains(record.StructuredState!, kv => kv.Key == "OrderId" && kv.Value == "42");
}
```

Si alguien vuelve a la interpolación, `StructuredState` deja de tener `OrderId` y el test falla: así el CA2254 deja de ser una sugerencia y pasa a ser una garantía.""",
            },
        ]
    },
    # 16) Caché: IMemoryCache, IDistributedCache y HybridCache (.NET 9) con protección contra estampidas (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tenemos un endpoint de catálogo que consulta lo mismo miles de veces por minuto. ¿`IMemoryCache`, Redis con `IDistributedCache` o el `HybridCache` nuevo de .NET 9? Corremos 4 réplicas.",
            },
            {
                "role": "assistant",
                "content": r"""Con 4 réplicas y lecturas muy repetidas, **`HybridCache`**. Combina lo que hacen bien los otros dos y resuelve un problema que ninguno de ellos resuelve solo.

| | `IMemoryCache` | `IDistributedCache` (Redis) | `HybridCache` (.NET 9) |
|---|---|---|---|
| Dónde vive | memoria de cada réplica | Redis, compartido | memoria local (L1) + distribuida opcional (L2) |
| Latencia de un acierto | nanosegundos | un viaje de red | nanosegundos si está en L1 |
| Coherencia entre réplicas | cada una con su copia | una sola copia | L2 compartida; L1 caduca antes |
| Serialización | no (guarda el objeto) | la haces tú (`byte[]`) | automática |
| Protección contra estampidas | no | no | sí |

**Estampida** es lo que pasa cuando una entrada caduca y llegan 500 peticiones a la vez: con `IMemoryCache.GetOrCreateAsync`, las 500 ven el fallo y las 500 consultan la base de datos. `HybridCache` deja pasar una sola por clave; las demás esperan su resultado.

### Configuración

```csharp
// Microsoft.Extensions.Caching.Hybrid + Microsoft.Extensions.Caching.StackExchangeRedis
builder.Services.AddStackExchangeRedisCache(o =>
    o.Configuration = builder.Configuration.GetConnectionString("Redis"));

builder.Services.AddHybridCache(o =>
{
    o.DefaultEntryOptions = new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromMinutes(10),          // en Redis (L2)
        LocalCacheExpiration = TimeSpan.FromMinutes(1), // en cada réplica (L1)
    };
});
```

Si hay un `IDistributedCache` registrado, `HybridCache` lo usa como L2; si no, funciona solo en memoria.

### Uso

```csharp
public sealed class CatalogService(ShopDbContext db, HybridCache cache)
{
    public ValueTask<ProductDto?> GetProductAsync(int id, CancellationToken ct) =>
        cache.GetOrCreateAsync(
            $"product:{id}",
            async cancel => await db.Products.AsNoTracking()
                .Where(p => p.Id == id)
                .Select(p => new ProductDto(p.Id, p.Name, p.PriceCents, p.Sku))
                .FirstOrDefaultAsync(cancel),
            tags: ["products"],
            cancellationToken: ct);

    public async Task UpdatePriceAsync(int id, long priceCents, CancellationToken ct)
    {
        await db.Products.Where(p => p.Id == id)
            .ExecuteUpdateAsync(s => s.SetProperty(p => p.PriceCents, priceCents), ct);
        await cache.RemoveAsync($"product:{id}", ct); // invalida al escribir
    }
}
```

### Decisiones y límites

- **L1 más corta que L2.** Cuando invalidas, `RemoveAsync` borra la entrada en Redis y en la réplica que hace la llamada, pero las otras tres pueden servir su copia local hasta un minuto. Ese minuto es el máximo de dato viejo que aceptas: ajústalo a lo que tolera el negocio (un precio, quizá 30 s; una descripción, 10 minutos).
- **Cachea DTOs, no entidades.** Una entidad de EF lleva navegaciones y estado de seguimiento; un `record` pequeño se serializa barato y no arrastra el `DbContext`.
- **Instancias por lectura.** `HybridCache` deserializa en cada acierto, así que cada llamada recibe su propio objeto (no hay riesgo de que alguien modifique la copia compartida). Si el tipo es `sealed` y lo marcas con `[ImmutableObject(true)]`, puede reutilizar la instancia y ahorrarse ese trabajo.
- **No cachees lo que depende del usuario** en claves globales. Si la respuesta cambia por cliente, la clave debe incluirlo.

Para respuestas HTTP completas e idénticas para todos (una página pública del catálogo), mira también **output caching** (`AddOutputCache()` y `.CacheOutput()`): evita incluso ejecutar el endpoint.

### Comprobación de la protección contra estampidas

```csharp
[Fact]
public async Task Concurrent_misses_run_the_factory_once()
{
    var services = new ServiceCollection();
    services.AddLogging();
    services.AddHybridCache();
    await using var provider = services.BuildServiceProvider();
    var cache = provider.GetRequiredService<HybridCache>();
    var calls = 0;

    var requests = Enumerable.Range(0, 50).Select(_ => cache.GetOrCreateAsync("product:1", async ct =>
    {
        Interlocked.Increment(ref calls);
        await Task.Delay(100, ct); // simula una consulta lenta
        return new ProductDto(1, "Teclado", 4999, "KEYB0001");
    }).AsTask());
    await Task.WhenAll(requests);

    Assert.Equal(1, calls);
}
```

Cambia `HybridCache` por `IMemoryCache.GetOrCreateAsync` en el mismo test y verás `calls` cerca de 50: es la diferencia que justifica la elección.""",
            },
        ]
    },
    # 17) BackgroundService que tumba el host (StopHost); bucle robusto con backoff y TimeProvider (usuario trae log).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Esta noche la API entera se cayó durante un reinicio de la base de datos. En el log:

```
fail: Microsoft.Extensions.Hosting.Internal.Host[9]
      BackgroundService failed
      Npgsql.NpgsqlException (0x80004005): Exception while reading from stream
       ---> System.IO.EndOfStreamException: Attempted to read past the end of the stream.
crit: Microsoft.Extensions.Hosting.Internal.Host[10]
      The HostOptions.BackgroundServiceExceptionBehavior is configured to StopHost. A BackgroundService has thrown an unhandled exception, and the IHost instance is stopping. To avoid this behavior, configure this to Ignore; however the BackgroundService will not be restarted.
```

¿Pongo `BackgroundServiceExceptionBehavior.Ignore` como dice el mensaje?""",
            },
            {
                "role": "assistant",
                "content": r"""No. Con `Ignore` la API seguiría viva, pero el worker estaría **muerto en silencio**: el mensaje lo dice, «will not be restarted». Dejarías de expirar pedidos (o lo que haga) hasta el siguiente despliegue y nadie se enteraría. El comportamiento por defecto desde .NET 6 (`StopHost`) es el correcto: un fallo que nadie maneja debe ser ruidoso. Lo que falta es manejar los fallos **esperables**, como un reinicio de la base de datos, dentro del propio worker.

### Qué pasó

Tu `ExecuteAsync` tiene un bucle sin `try/catch`. La excepción de Npgsql por el corte de conexión salió de `ExecuteAsync`, el host la vio como fallo del servicio y se detuvo entero, API incluida. Un problema de 30 segundos en la base de datos se convirtió en una caída completa.

### Arreglo: cada iteración aislada, con espera creciente

```csharp
public sealed class OrderExpiryWorker(
    IServiceScopeFactory scopeFactory,
    WorkerHealth health,
    ILogger<OrderExpiryWorker> logger,
    TimeProvider time) : BackgroundService
{
    private static readonly TimeSpan Interval = TimeSpan.FromMinutes(1);
    private static readonly TimeSpan MaxBackoff = TimeSpan.FromMinutes(5);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(Interval, time);
        var consecutiveFailures = 0;

        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                await using var scope = scopeFactory.CreateAsyncScope();
                var expiry = scope.ServiceProvider.GetRequiredService<IOrderExpiryService>();
                await expiry.ExpirePendingAsync(stoppingToken);

                consecutiveFailures = 0;
                health.ReportSuccess(time.GetUtcNow());
            }
            catch (Exception ex) when (!stoppingToken.IsCancellationRequested)
            {
                consecutiveFailures++;
                logger.LogError(ex, "Order expiry failed ({ConsecutiveFailures} in a row)", consecutiveFailures);
                await Task.Delay(Backoff(consecutiveFailures), time, stoppingToken);
            }
        }
    }

    private static TimeSpan Backoff(int failures) =>
        TimeSpan.FromSeconds(Math.Min(MaxBackoff.TotalSeconds, Math.Pow(2, failures)));
}
```

Detalles que importan:

- **`when (!stoppingToken.IsCancellationRequested)`**: durante el apagado, la cancelación debe salir del método para que el host termine limpio. Cualquier otra excepción se registra y el bucle sigue.
- **Espera exponencial con tope**: con la base de datos caída, no machacas los logs ni la base de datos cuando vuelva.
- **Un ámbito por iteración**: si el `DbContext` quedó con una conexión rota, la siguiente iteración empieza con uno nuevo.
- **`TimeProvider`** en el temporizador y en la espera: el test de abajo controla el tiempo sin dormir.

### Que el silencio no vuelva a ser posible

Que el worker no tumbe la API no debe significar que pueda fallar indefinidamente sin que nadie lo vea. Expón su estado en un *health check*:

```csharp
public sealed class WorkerHealth
{
    private long _lastSuccessTicks;
    public void ReportSuccess(DateTimeOffset at) => Interlocked.Exchange(ref _lastSuccessTicks, at.UtcTicks);
    public DateTimeOffset? LastSuccess =>
        Interlocked.Read(ref _lastSuccessTicks) is var t and > 0 ? new DateTimeOffset(t, TimeSpan.Zero) : null;
}

public sealed class OrderExpiryHealthCheck(WorkerHealth health, TimeProvider time) : IHealthCheck
{
    private static readonly TimeSpan MaxSilence = TimeSpan.FromMinutes(10);

    public Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken ct = default)
    {
        var last = health.LastSuccess;
        var healthy = last is not null && time.GetUtcNow() - last < MaxSilence;
        return Task.FromResult(healthy
            ? HealthCheckResult.Healthy()
            : HealthCheckResult.Degraded($"No successful run since {last?.ToString("O") ?? "startup"}"));
    }
}
```

Con una alerta sobre ese estado `Degraded`, te enteras en 10 minutos en vez de al día siguiente. Y si tienes varias réplicas, recuerda que el worker corre en **todas**: la operación debe ser idempotente (como un `UPDATE ... WHERE status = 'pending'`) o necesitas un bloqueo distribuido.

### Test de regresión

```csharp
[Fact]
public async Task Worker_survives_a_failed_iteration()
{
    var time = new FakeTimeProvider();
    var expiry = new FlakyExpiryService(failuresBeforeSuccess: 1);
    using var services = new ServiceCollection()
        .AddScoped<IOrderExpiryService>(_ => expiry)
        .BuildServiceProvider();
    var worker = new OrderExpiryWorker(services.GetRequiredService<IServiceScopeFactory>(),
        new WorkerHealth(), NullLogger<OrderExpiryWorker>.Instance, time);

    await worker.StartAsync(CancellationToken.None);
    time.Advance(TimeSpan.FromMinutes(1));                 // 1.ª iteración: lanza
    await WaitUntil(() => expiry.Calls == 1);
    time.Advance(TimeSpan.FromSeconds(2));                 // termina la espera de backoff
    time.Advance(TimeSpan.FromMinutes(1));                 // 2.ª iteración: funciona
    await WaitUntil(() => expiry.Calls == 2);
    await worker.StopAsync(CancellationToken.None);

    Assert.True(worker.ExecuteTask!.IsCompletedSuccessfully || worker.ExecuteTask.IsCanceled);
}

private static async Task WaitUntil(Func<bool> condition)
{
    var deadline = DateTime.UtcNow.AddSeconds(5);
    while (!condition())
    {
        if (DateTime.UtcNow > deadline) throw new TimeoutException("condition not met");
        await Task.Delay(10);
    }
}
```

Con el worker original, la primera excepción termina `ExecuteTask` como fallida y la segunda llamada nunca llega. `FakeTimeProvider` está en el paquete `Microsoft.Extensions.TimeProvider.Testing`.""",
            },
        ]
    },
    # 18) Cola en memoria con Channels y 202 Accepted; después durabilidad con tabla y SKIP LOCKED (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos un endpoint que genera un informe PDF y tarda unos 20 segundos; el balanceador corta a los 30 y a veces falla. Quiero responder enseguida y procesarlo en segundo plano. ¿Cómo lo hago en ASP.NET Core sin meter todavía un broker?",
            },
            {
                "role": "assistant",
                "content": r"""El patrón es **202 Accepted + cola + consulta de estado**: el `POST` encola el trabajo y responde al instante con la URL donde consultar cómo va; un `BackgroundService` procesa la cola. Para la cola en memoria, `System.Threading.Channels`.

### La cola

```csharp
public sealed record ReportJob(Guid Id, int CustomerId, DateOnly Month);

public sealed class ReportQueue
{
    // Acotada: si se llena, se rechaza en vez de acumular memoria sin límite.
    private readonly Channel<ReportJob> _channel = Channel.CreateBounded<ReportJob>(
        new BoundedChannelOptions(capacity: 100) { FullMode = BoundedChannelFullMode.Wait });

    public bool TryEnqueue(ReportJob job) => _channel.Writer.TryWrite(job);

    public IAsyncEnumerable<ReportJob> DequeueAllAsync(CancellationToken ct) => _channel.Reader.ReadAllAsync(ct);
}

public enum ReportState { Queued, Running, Done, Failed }

public sealed class ReportStatusStore
{
    private readonly ConcurrentDictionary<Guid, ReportState> _states = new();
    public void Set(Guid id, ReportState state) => _states[id] = state;
    public ReportState? Get(Guid id) => _states.TryGetValue(id, out var s) ? s : null;
}
```

`TryWrite` en una cola acotada con modo `Wait` devuelve `false` cuando está llena: ese `false` es tu señal de contrapresión.

### Los endpoints

```csharp
app.MapPost("/api/reports", Results<Accepted<ReportAccepted>, ProblemHttpResult> (
    CreateReportRequest request, ReportQueue queue, ReportStatusStore statuses) =>
{
    var job = new ReportJob(Guid.NewGuid(), request.CustomerId, request.Month);
    if (!queue.TryEnqueue(job))
    {
        return TypedResults.Problem("Hay demasiados informes en cola. Reintenta en unos minutos.",
            statusCode: StatusCodes.Status503ServiceUnavailable);
    }
    statuses.Set(job.Id, ReportState.Queued);
    return TypedResults.Accepted($"/api/reports/{job.Id}", new ReportAccepted(job.Id));
});

app.MapGet("/api/reports/{id:guid}", Results<Ok<ReportStatusDto>, NotFound> (Guid id, ReportStatusStore statuses) =>
    statuses.Get(id) is { } state ? TypedResults.Ok(new ReportStatusDto(id, state)) : TypedResults.NotFound());
```

### El consumidor

```csharp
public sealed class ReportWorker(
    ReportQueue queue, ReportStatusStore statuses, IServiceScopeFactory scopes, ILogger<ReportWorker> logger)
    : BackgroundService
{
    private const int MaxParallelReports = 2; // el PDF es intensivo en CPU: no más que esto por réplica

    protected override Task ExecuteAsync(CancellationToken stoppingToken) =>
        Parallel.ForEachAsync(queue.DequeueAllAsync(stoppingToken),
            new ParallelOptions { MaxDegreeOfParallelism = MaxParallelReports, CancellationToken = stoppingToken },
            async (job, ct) =>
            {
                statuses.Set(job.Id, ReportState.Running);
                try
                {
                    await using var scope = scopes.CreateAsyncScope();
                    var generator = scope.ServiceProvider.GetRequiredService<ReportGenerator>();
                    await generator.GenerateAsync(job, ct);
                    statuses.Set(job.Id, ReportState.Done);
                }
                catch (Exception ex) when (!ct.IsCancellationRequested)
                {
                    logger.LogError(ex, "Report {ReportId} failed", job.Id);
                    statuses.Set(job.Id, ReportState.Failed);
                }
            });
}
```

```csharp
builder.Services.AddSingleton<ReportQueue>();
builder.Services.AddSingleton<ReportStatusStore>();
builder.Services.AddScoped<ReportGenerator>();
builder.Services.AddHostedService<ReportWorker>();
```

El cliente hace `POST`, recibe 202 con `Location: /api/reports/{id}` y consulta esa URL cada pocos segundos hasta ver `Done`.

### Comprobación

- `POST` debe responder en milisegundos con 202 y la cabecera `Location`.
- Llena la cola en un test (capacidad 1 con un generador falso que nunca termina): el segundo `POST` debe dar 503.
- Lanza 10 informes y mira que nunca hay más de 2 en `Running` a la vez.

**Limitación importante:** todo esto vive en memoria. Si el proceso se reinicia, se pierden los trabajos en cola y los estados; y con varias réplicas, el `GET` de estado puede caer en una réplica que no conoce ese id. Para un primer paso con una sola réplica vale; para más, hay que persistir.""",
            },
            {
                "role": "user",
                "content": "Tenemos 3 réplicas y los despliegues reinician pods a menudo. ¿Cuál es el siguiente paso sin montar RabbitMQ?",
            },
            {
                "role": "assistant",
                "content": r"""Usar la **base de datos como cola**. Con Postgres y `FOR UPDATE SKIP LOCKED`, varias réplicas pueden tomar trabajos de la misma tabla sin pisarse, y nada se pierde en un reinicio.

### La tabla es la cola y el estado a la vez

```csharp
public sealed class ReportJobRow
{
    public Guid Id { get; set; }
    public int CustomerId { get; set; }
    public DateOnly Month { get; set; }
    public ReportState State { get; set; }
    public int Attempts { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? LockedUntil { get; set; }
    public string? Error { get; set; }
}
```

El `POST` inserta una fila con `State = Queued` y responde 202. El `GET` de estado lee esa fila: da igual qué réplica conteste.

### Tomar un trabajo de forma segura

```csharp
public sealed class ReportJobClaimer(ShopDbContext db, TimeProvider time)
{
    private static readonly TimeSpan Lease = TimeSpan.FromMinutes(5);

    public async Task<ReportJobRow?> TryClaimAsync(CancellationToken ct)
    {
        var now = time.GetUtcNow().UtcDateTime;
        await using var tx = await db.Database.BeginTransactionAsync(ct);

        // SKIP LOCKED: si otra réplica tiene bloqueada una fila, se salta en vez de esperar.
        // Nombres en snake_case (asumo UseSnakeCaseNamingConvention de EFCore.NamingConventions).
        var job = await db.ReportJobs
            .FromSql($@"SELECT * FROM report_jobs
                        WHERE (state = 0 OR (state = 1 AND locked_until < {now}))
                        ORDER BY created_at
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED")
            .SingleOrDefaultAsync(ct);
        if (job is null)
        {
            return null;
        }

        job.State = ReportState.Running;
        job.Attempts++;
        job.LockedUntil = now + Lease;
        await db.SaveChangesAsync(ct);
        await tx.CommitAsync(ct);
        return job;
    }
}
```

Y el worker, en un bucle: reclamar, generar, marcar `Done` (o `Failed` con el error si `Attempts` supera el máximo). Si no hay trabajo, espera unos segundos con un `PeriodicTimer` antes de volver a mirar.

Por qué este diseño aguanta reinicios:

- **El trabajo no se pierde**: está en la tabla desde el `POST`.
- **El *lease* (`LockedUntil`)**: si un pod muere a mitad de un informe, la fila queda en `Running` con un plazo vencido, y otra réplica la retoma pasado ese tiempo. Ajusta el plazo a algo mayor que el informe más lento.
- **`Attempts` con máximo**: un informe que siempre falla no se reintenta para siempre.
- **La generación debe ser idempotente**: si un pod termina el PDF pero muere antes de marcar `Done`, se generará otra vez. Escribe el PDF con un nombre derivado del `Id` para que el segundo intento sobrescriba en vez de duplicar.

Y para el apagado ordenado, el `stoppingToken` del worker llega cuando Kubernetes manda `SIGTERM`; el host espera hasta `HostOptions.ShutdownTimeout` (30 s por defecto). Si un informe tarda más, quedará a medias y el *lease* lo rescatará.

Un detalle de seguridad del código: `FromSql` recibe una cadena **interpolada**, así que `{now}` viaja como parámetro de la consulta y no se concatena en el SQL. Con `FromSqlRaw` y concatenación tendrías una inyección SQL esperando su momento.

### Comprobación

Un test contra Postgres real (Testcontainers) con dos `ReportJobClaimer` en paralelo sobre 10 trabajos: cada trabajo debe ser reclamado exactamente una vez. Después, simula un pod muerto: reclama un trabajo, no lo completes, avanza el `FakeTimeProvider` 6 minutos y comprueba que otro *claimer* lo recupera con `Attempts = 2`.

Cuando el volumen crezca (miles de trabajos por minuto) o necesites enrutar mensajes entre servicios, ese es el momento del broker. Hasta entonces, esto es más simple de operar y transaccional con tus datos.""",
            },
        ]
    },
    # 19) SignalR: hub tipado, grupos, JWT por query string; después escalado con varias réplicas (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Queremos avisar en tiempo real al cliente cuando cambia el estado de su pedido. ASP.NET Core 8 con SignalR, la API ya usa JWT Bearer. ¿Cómo lo monto para que cada cliente solo reciba lo suyo?",
            },
            {
                "role": "assistant",
                "content": r"""Con un hub **tipado**, un **grupo por cliente** al que se une cada conexión al conectarse, y el envío desde tus servicios con `IHubContext`. Hay un detalle de autenticación propio de WebSockets que conviene resolver desde el principio.

### El hub

```csharp
public sealed record OrderStatusChanged(int OrderId, string Status, DateTimeOffset At);

// Métodos que el servidor puede invocar en el cliente: el compilador comprueba nombres y argumentos.
public interface IOrderClient
{
    Task OrderStatusChanged(OrderStatusChanged message);
}

[Authorize]
public sealed class OrdersHub : Hub<IOrderClient>
{
    public static string CustomerGroup(string customerId) => $"customer:{customerId}";

    public override async Task OnConnectedAsync()
    {
        var customerId = Context.User?.FindFirst("sub")?.Value;
        if (customerId is null)
        {
            Context.Abort();
            return;
        }
        await Groups.AddToGroupAsync(Context.ConnectionId, CustomerGroup(customerId));
        await base.OnConnectedAsync();
    }
}
```

El hub no tiene métodos que el cliente pueda invocar: solo recibe. Menos superficie que proteger.

### Enviar desde cualquier servicio

```csharp
public sealed class OrderNotifier(IHubContext<OrdersHub, IOrderClient> hub)
{
    public Task StatusChangedAsync(Order order, CancellationToken ct) =>
        hub.Clients.Group(OrdersHub.CustomerGroup(order.CustomerId))
            .OrderStatusChanged(new OrderStatusChanged(order.Id, order.Status.ToString(), DateTimeOffset.UtcNow));
}
```

Llámalo **después** de confirmar la transacción que cambia el estado: si avisas antes y la transacción falla, el cliente habrá visto un estado que nunca existió.

### Autenticación: el token en la query string

El navegador no permite añadir la cabecera `Authorization` a una conexión WebSocket ni a Server-Sent Events. El cliente de SignalR manda el token en el parámetro `access_token`, y hay que decirle al manejador JWT que lo lea ahí, **solo** para la ruta del hub:

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        // ...configuración de Authority, Audience, MapInboundClaims, etc.
        o.Events = new JwtBearerEvents
        {
            OnMessageReceived = context =>
            {
                var token = context.Request.Query["access_token"];
                if (!string.IsNullOrEmpty(token) && context.HttpContext.Request.Path.StartsWithSegments("/hubs"))
                {
                    context.Token = token;
                }
                return Task.CompletedTask;
            },
        };
    });

builder.Services.AddSignalR();
builder.Services.AddScoped<OrderNotifier>();

app.MapHub<OrdersHub>("/hubs/orders");
```

Como el token viaja en la URL, asegúrate de que ni tu *logging* de peticiones ni el del proxy registran la query string de `/hubs`.

En el cliente:

```javascript
import * as signalR from "@microsoft/signalr";

const connection = new signalR.HubConnectionBuilder()
  .withUrl("/hubs/orders", { accessTokenFactory: () => auth.getAccessToken() })
  .withAutomaticReconnect()
  .build();

connection.on("OrderStatusChanged", (msg) => updateOrderInUi(msg.orderId, msg.status));
await connection.start();
```

`accessTokenFactory` se llama en cada (re)conexión, así que un token renovado se usa al reconectar.

**Por qué grupos y no `Clients.User(id)`:** `Clients.User` depende de `IUserIdProvider`, que por defecto lee el claim `NameIdentifier`. Si desactivaste el mapeo de claims (`MapInboundClaims = false`), ese claim no existe y `Clients.User` no encuentra a nadie, sin error. El grupo explícito deja claro qué claim se usa.

### Comprobación

Un test de integración con `Microsoft.AspNetCore.SignalR.Client` contra `WebApplicationFactory`: conecta dos clientes con tokens de clientes distintos, dispara un cambio de estado de un pedido del primero y comprueba que el primero recibe el mensaje y el segundo no en un plazo de un par de segundos. Usa `HttpMessageHandlerFactory = _ => factory.Server.CreateHandler()` y transporte `LongPolling` en las opciones de conexión del cliente, porque el servidor de test no admite WebSockets reales.""",
            },
            {
                "role": "user",
                "content": "En producción tenemos 3 réplicas detrás de un balanceador. ¿Funciona igual?",
            },
            {
                "role": "assistant",
                "content": r"""No. Cada réplica solo conoce **sus** conexiones y **sus** grupos. Si el cambio de estado lo procesa la réplica A y el cliente está conectado a la réplica C, `Clients.Group(...)` en A no encuentra a nadie y el mensaje se pierde sin error.

Hay dos problemas distintos que resolver.

### 1. Repartir los mensajes entre réplicas: un backplane

Con Redis, cada réplica publica los mensajes en un canal y todas los reciben y entregan a sus conexiones locales:

```csharp
// Microsoft.AspNetCore.SignalR.StackExchangeRedis
builder.Services.AddSignalR()
    .AddStackExchangeRedis(builder.Configuration.GetConnectionString("Redis")!, o =>
    {
        // Prefijo para que varias aplicaciones no compartan canales en el mismo Redis.
        o.Configuration.ChannelPrefix = RedisChannel.Literal("shop");
    });
```

Los grupos siguen funcionando igual: la pertenencia es local, pero el mensaje al grupo llega a todas las réplicas, y cada una entrega a los miembros que tiene.

La alternativa sin infraestructura propia es **Azure SignalR Service**, que gestiona las conexiones fuera de tus réplicas. Merece la pena con muchas conexiones (decenas de miles) o si ya estás en Azure.

### 2. La negociación: sesiones persistentes

La conexión de SignalR empieza con un `POST /hubs/orders/negotiate` y luego abre el transporte. Si esas dos peticiones caen en réplicas distintas, la conexión falla. Opciones:

- **Afinidad de sesión** (*sticky sessions*) en el balanceador o el ingress, por cookie. Es lo más habitual.
- **Solo WebSockets y sin negociación**: en el cliente, `skipNegotiation: true` y `transport: signalR.HttpTransportType.WebSockets`. Funciona sin afinidad porque todo ocurre en una única conexión, pero pierdes el *fallback* a otros transportes en redes que bloquean WebSockets.

### Lo que no cambia, pero hay que tener presente

- **Los grupos no se persisten.** Al reconectar, el cliente es una conexión nueva; tu `OnConnectedAsync` lo vuelve a añadir a su grupo. Por eso la pertenencia se calcula en la conexión y no se guarda.
- **Los mensajes no son garantizados.** Un cliente desconectado durante un minuto pierde lo que se envió en ese minuto. Al reconectar (`connection.onreconnected`), la interfaz debe pedir el estado actual por HTTP. SignalR es el aviso; la fuente de verdad sigue siendo la API.
- **Despliegues**: al reiniciar una réplica, sus clientes reconectan contra otra. Con `withAutomaticReconnect()` es transparente, pero escalona los reinicios para no provocar una avalancha de reconexiones a la vez.

### Comprobación

En un entorno con 2 réplicas: conecta el cliente, mira en qué réplica está (registra el nombre del pod en `OnConnectedAsync`), y dispara el cambio de estado con una petición que forzosamente vaya a la **otra** réplica. Sin backplane no llega; con Redis, llega. Repite tras reiniciar el pod del cliente para comprobar que la reconexión lo devuelve a su grupo.""",
            },
        ]
    },
    # 20) Inglés: tests de integración con WebApplicationFactory, xUnit y Testcontainers (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "How should I write integration tests for an ASP.NET Core 8 API with EF Core and Postgres? Today we use the EF in-memory provider and tests pass while production fails on constraints and transactions.",
            },
            {
                "role": "assistant",
                "content": r"""Drop the in-memory provider for this: it is not a relational database. It ignores unique constraints, foreign keys and transactions, and translates LINQ differently. A test suite that passes on it tells you little about Postgres. Use **`WebApplicationFactory`** to host the real app in memory and **Testcontainers** to give it a real Postgres.

### The factory

```csharp
using DotNet.Testcontainers.Builders;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Testcontainers.PostgreSql;
using Xunit;

public sealed class ApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly PostgreSqlContainer _postgres = new PostgreSqlBuilder()
        .WithImage("postgres:16-alpine") // same major version as production
        .Build();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        // Overrides the connection string Program.cs reads; no need to re-register the DbContext.
        builder.UseSetting("ConnectionStrings:Shop", _postgres.GetConnectionString());
        builder.ConfigureTestServices(services =>
        {
            // Replace only what crosses the process boundary to third parties.
            services.RemoveAll<IPaymentsGateway>();
            services.AddSingleton<IPaymentsGateway, FakePaymentsGateway>();
        });
    }

    public async Task InitializeAsync()
    {
        await _postgres.StartAsync();
        await using var scope = Services.CreateAsyncScope();
        await scope.ServiceProvider.GetRequiredService<ShopDbContext>().Database.MigrateAsync();
    }

    async Task IAsyncLifetime.DisposeAsync()
    {
        await base.DisposeAsync();     // stop the app first
        await _postgres.DisposeAsync(); // then its database
    }

    public async Task ResetDatabaseAsync()
    {
        await using var scope = Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
        await db.Database.ExecuteSqlRawAsync("TRUNCATE order_lines, orders, products RESTART IDENTITY CASCADE");
    }

    public async Task SeedAsync(Action<ShopDbContext> seed)
    {
        await using var scope = Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
        seed(db);
        await db.SaveChangesAsync();
    }

    public async Task<T> QueryAsync<T>(Func<ShopDbContext, Task<T>> query)
    {
        await using var scope = Services.CreateAsyncScope();
        return await query(scope.ServiceProvider.GetRequiredService<ShopDbContext>());
    }
}
```

Points that are easy to get wrong:

- **`public partial class Program { }`** at the end of `Program.cs` (up to .NET 9), or the test project cannot reference the top-level-statements `Program`.
- **`IAsyncLifetime.DisposeAsync` is implemented explicitly** because `WebApplicationFactory` already has a `DisposeAsync` returning `ValueTask`, while xUnit v2's interface expects a `Task`.
- **`UseSetting` instead of re-registering the `DbContext`.** It is one line, and it tests the real registration code instead of a copy of it.
- **Only external systems are faked.** The database, EF mappings, middleware and serialization are the real ones; that is the point of the test.

### Tests

```csharp
public sealed class OrdersApiTests(ApiFactory factory) : IClassFixture<ApiFactory>, IAsyncLifetime
{
    public Task InitializeAsync() => factory.ResetDatabaseAsync(); // every test starts clean
    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Placing_an_order_decrements_stock()
    {
        await factory.SeedAsync(db => db.Products.Add(
            new Product { Name = "Keyboard", PriceCents = 4999, Sku = "KEYB0001", Stock = 5 }));
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders",
            new { items = new[] { new { productId = 1, quantity = 2 } } });

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var stock = await factory.QueryAsync(db => db.Products.Where(p => p.Id == 1).Select(p => p.Stock).SingleAsync());
        Assert.Equal(3, stock);
    }

    [Fact]
    public async Task Duplicate_sku_is_409()
    {
        await factory.SeedAsync(db => db.Products.Add(
            new Product { Name = "Keyboard", PriceCents = 4999, Sku = "DUPL0001", Stock = 1 }));
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/products",
            new { name = "Other", priceCents = 100, sku = "DUPL0001" });

        Assert.Equal(HttpStatusCode.Conflict, response.StatusCode); // only a real unique index can produce this
    }
}
```

The second test is the kind the in-memory provider can never fail: the 409 comes from Postgres rejecting the insert.

### Cost and isolation

- With `IClassFixture`, each test class gets its own `ApiFactory` and therefore its own container, so classes can run in parallel safely. With `ICollectionFixture` several classes share one container (faster startup), and xUnit runs the classes of a collection sequentially.
- `TRUNCATE` per test keeps tests independent. If the schema grows, the Respawn library computes the delete order for you.
- Tests within a class run sequentially in xUnit by default, so a per-class database is safe without extra locking.

For endpoints that require authentication, register a test authentication scheme in `ConfigureTestServices`; that deserves its own setup so tests can choose the user and roles per request.

### Verification

Before trusting the new suite, make it fail for the right reason: drop the unique index on `sku` in a local migration and run `Duplicate_sku_is_409`. It must fail. Put the index back and it must pass. That proves the test exercises Postgres, not a mock.""",
            },
        ]
    },
    # 21) Tests de integración que dan 401: esquema de autenticación de test (usuario trae test que falla).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Al añadir `[Authorize]` a los endpoints de pedidos, todos los tests de integración de pedidos fallan:

```
Assert.Equal() Failure: Values differ
Expected: OK
Actual:   Unauthorized
   at OrdersApiTests.Get_my_orders_returns_only_mine() in OrdersApiTests.cs:line 41
```

```csharp
[Fact]
public async Task Get_my_orders_returns_only_mine()
{
    var client = _factory.CreateClient();
    var response = await client.GetAsync("/api/orders/mine");
    Assert.Equal(HttpStatusCode.OK, response.StatusCode);
}
```

¿Genero un JWT de verdad en cada test? El IdP es externo y no quiero depender de él.""",
            },
            {
                "role": "assistant",
                "content": r"""El test falla porque la aplicación hace lo correcto: la petición no lleva identidad y el endpoint la exige. El error no está en la API, sino en que el test no dice **quién** hace la petición. Y además el test no puede expresar lo que quiere comprobar («solo veo **mis** pedidos») sin un usuario concreto.

Hay dos formas de dárselo:

| | Token JWT firmado en el test | Esquema de autenticación de test |
|---|---|---|
| Prueba la validación del JWT (emisor, audiencia, firma) | sí | no |
| Elegir usuario y roles por petición | más montaje | trivial |
| Depende del IdP | no, si firmas con una clave de test | no |

Para tests de **lógica de negocio con usuarios**, el esquema de test. La validación del JWT se prueba aparte, en unos pocos tests dedicados.

### El manejador de autenticación de test

```csharp
public sealed class TestAuthHandler(
    IOptionsMonitor<AuthenticationSchemeOptions> options, ILoggerFactory logger, UrlEncoder encoder)
    : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    public const string SchemeName = "Test";
    public const string UserHeader = "X-Test-User";
    public const string RolesHeader = "X-Test-Roles";

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        var userId = Request.Headers[UserHeader].ToString();
        if (string.IsNullOrEmpty(userId))
        {
            return Task.FromResult(AuthenticateResult.NoResult()); // anónimo: el endpoint decidirá (401)
        }

        var claims = new List<Claim> { new("sub", userId) };
        claims.AddRange(Request.Headers[RolesHeader].ToString()
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(role => new Claim("role", role)));

        // Mismos tipos de nombre y rol que la configuración real (MapInboundClaims = false).
        var identity = new ClaimsIdentity(claims, SchemeName, nameType: "sub", roleType: "role");
        var ticket = new AuthenticationTicket(new ClaimsPrincipal(identity), SchemeName);
        return Task.FromResult(AuthenticateResult.Success(ticket));
    }
}
```

### Registrarlo en la factoría

```csharp
public sealed class ApiFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder) =>
        builder.ConfigureTestServices(services =>
        {
            services.AddAuthentication()
                .AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(TestAuthHandler.SchemeName, _ => { });

            // PostConfigure se aplica después de la configuración de Program.cs: el esquema de test gana.
            services.PostConfigure<AuthenticationOptions>(o =>
            {
                o.DefaultScheme = TestAuthHandler.SchemeName;
                o.DefaultAuthenticateScheme = TestAuthHandler.SchemeName;
                o.DefaultChallengeScheme = TestAuthHandler.SchemeName;
            });
        });

    public HttpClient CreateClientAs(string userId, params string[] roles)
    {
        var client = CreateClient();
        client.DefaultRequestHeaders.Add(TestAuthHandler.UserHeader, userId);
        if (roles.Length > 0)
        {
            client.DefaultRequestHeaders.Add(TestAuthHandler.RolesHeader, string.Join(',', roles));
        }
        return client;
    }
}
```

Fíjate en el `PostConfigure`: si `Program.cs` fija `DefaultAuthenticateScheme` o `DefaultChallengeScheme` para JWT, un simple `AddAuthentication("Test")` no los sobrescribe y seguirías viendo 401. Y si alguna política declara `AuthenticationSchemes = JwtBearerDefaults.AuthenticationScheme` explícitamente, esa política seguirá usando JWT: tendrás que añadir el esquema de test a esa política en el entorno de pruebas o, mejor, no fijar esquemas en las políticas.

### Los tests, ahora expresando lo que importa

```csharp
public sealed class OrdersApiTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    [Fact]
    public async Task Get_my_orders_returns_only_mine()
    {
        await factory.SeedOrdersAsync(("c-1", 2), ("c-2", 3)); // 2 pedidos de c-1, 3 de c-2

        var orders = await factory.CreateClientAs("c-1").GetFromJsonAsync<List<OrderSummaryDto>>("/api/orders/mine");

        Assert.Equal(2, orders!.Count);
    }

    [Fact]
    public async Task Anonymous_request_is_401()
    {
        var response = await factory.CreateClient().GetAsync("/api/orders/mine");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task Support_role_can_read_any_order()
    {
        var response = await factory.CreateClientAs("s-1", "support").GetAsync("/api/orders/1");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
}
```

El test anónimo no es relleno: comprueba que el esquema de test **no** autentica a todo el mundo. Sin él, un error en `TestAuthHandler` haría pasar todos los tests de seguridad sin probar nada.

Un último punto: `TestAuthHandler` vive **solo** en el proyecto de tests. Nunca lo registres detrás de un `if (env.IsDevelopment())` en la aplicación: un entorno mal configurado convertiría una cabecera en una puerta trasera.""",
            },
        ]
    },
    # 22) Blazor en .NET 8/9: modos de renderizado; después cuál para un backoffice interno y DbContext en Blazor Server (multiturno, principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Soy de backend .NET y nunca toqué Blazor. Leo «Static SSR», «InteractiveServer», «InteractiveWebAssembly», «InteractiveAuto»... ¿qué es cada cosa, en corto?",
            },
            {
                "role": "assistant",
                "content": r"""Desde .NET 8, Blazor es un solo modelo de componentes (`.razor`) y el **modo de renderizado** decide dónde se ejecuta cada componente y cómo se vuelve interactivo. Se elige por componente o para toda la aplicación.

| Modo | Dónde corre | Interactividad | Coste |
|---|---|---|---|
| **Static SSR** | servidor, una vez por petición | ninguna: HTML plano (formularios con `POST` normales) | el más barato; como Razor Pages |
| **InteractiveServer** | servidor, de forma continua | sí: cada clic viaja por una conexión SignalR y el servidor devuelve el cambio del DOM | memoria en el servidor por usuario conectado; latencia en cada interacción |
| **InteractiveWebAssembly** | navegador (.NET compilado a WebAssembly) | sí, local, sin viaje al servidor | descarga inicial de varios MB; el código y la lógica están en el cliente |
| **InteractiveAuto** | primero servidor, después navegador | sí | lo mejor de ambos y la complejidad de ambos |

Un componente con interactividad de servidor:

```razor
@page "/counter"
@rendermode InteractiveServer

<h1>Contador</h1>
<p>Valor actual: @count</p>
<button class="btn" @onclick="Increment">Sumar</button>

@code {
    private int count;

    private void Increment() => count++;
}
```

Sin la línea `@rendermode`, la página se renderiza como Static SSR: el botón aparece, pero no hace nada, porque no hay nada ejecutándose después de enviar el HTML. Es la confusión número uno al empezar.

Dos piezas más que verás pronto:

- **`[StreamRendering]`** en páginas Static SSR: envía primero el HTML con un «cargando» y, cuando terminan las llamadas asíncronas, el resto en la misma respuesta. Da sensación de rapidez sin interactividad.
- **Formularios en Static SSR** con `<EditForm FormName="...">` y `[SupplyParameterFromForm]`: funcionan como un formulario HTML clásico, con validación en el servidor.

Para comprobar qué modo tiene cada componente: abre las herramientas del navegador. Con InteractiveServer verás una conexión WebSocket a `_blazor`; con WebAssembly, la descarga de `dotnet.wasm` y de tus ensamblados; con Static SSR, nada después de la carga del documento.""",
            },
            {
                "role": "user",
                "content": "Tenemos que hacer un backoffice interno para unos 30 usuarios, con formularios y tablas contra nuestra base de datos. ¿Qué modo elegirías?",
            },
            {
                "role": "assistant",
                "content": r"""**InteractiveServer.** Para 30 usuarios internos es el modo que menos piezas tiene: los componentes llaman directamente a tus servicios y a EF Core en el servidor, sin escribir ni mantener una API para el frontend. El coste por usuario conectado (memoria del circuito) es irrelevante con 30 personas, y en una red corporativa la latencia por interacción apenas se nota.

Hay un error que casi todo el mundo comete al empezar con Blazor Server: **inyectar el `DbContext` directamente en los componentes**.

En Blazor Server, un ámbito de inyección de dependencias no dura una petición: dura **todo el circuito**, es decir, lo que el usuario tenga la pestaña abierta, a veces horas. Un `DbContext` *scoped* inyectado en un componente se reutiliza durante toda la sesión: acumula entidades en el *change tracker*, devuelve datos viejos, y dos operaciones asíncronas que se solapen (un clic mientras otra tabla carga) lanzan la excepción de que el contexto no admite operaciones concurrentes.

La solución es una fábrica y un contexto por operación:

```csharp
// Program.cs
builder.Services.AddDbContextFactory<ShopDbContext>(o =>
    o.UseNpgsql(builder.Configuration.GetConnectionString("Shop")));
builder.Services.AddRazorComponents().AddInteractiveServerComponents();
```

```razor
@page "/admin/products"
@rendermode InteractiveServer
@inject IDbContextFactory<ShopDbContext> DbFactory

<QuickGrid Items="products" Pagination="pagination">
    <PropertyColumn Property="p => p.Name" Sortable="true" />
    <PropertyColumn Property="p => p.PriceCents" Title="Precio (céntimos)" />
</QuickGrid>
<Paginator State="pagination" />

@code {
    private IQueryable<ProductRow>? products;
    private readonly PaginationState pagination = new() { ItemsPerPage = 25 };
    private List<ProductRow> loaded = [];

    protected override async Task OnInitializedAsync()
    {
        // Un contexto para esta operación y se libera al terminar.
        await using var db = await DbFactory.CreateDbContextAsync();
        loaded = await db.Products.AsNoTracking()
            .OrderBy(p => p.Name)
            .Select(p => new ProductRow(p.Id, p.Name, p.PriceCents))
            .ToListAsync();
        products = loaded.AsQueryable();
    }

    private sealed record ProductRow(int Id, string Name, long PriceCents);
}
```

`QuickGrid` es el componente de tabla oficial (`Microsoft.AspNetCore.Components.QuickGrid`). Para tablas grandes tiene un adaptador de EF Core que pagina en la base de datos; para un catálogo de unos miles de filas en un backoffice, cargar y paginar en memoria como aquí es suficiente.

Otras dos cosas a prever:

- **Reconexión.** Si el servidor se reinicia o se corta la red, el circuito se pierde y el estado de la pantalla con él. Mantén los formularios cortos o guarda borradores, y despliega fuera del horario de uso.
- **Varias réplicas** necesitan afinidad de sesión, porque el circuito vive en una réplica concreta. Para 30 usuarios, una réplica (o dos con afinidad) sobra.

Si algún día el backoffice se abre a usuarios externos con mala conexión, o crece a miles de usuarios simultáneos, es el momento de evaluar WebAssembly o Auto, que sí exigen una API. Ese cambio se puede hacer componente a componente.

Comprobación del punto del `DbContext`: abre la página, edita un producto desde otra pestaña y recarga la tabla en la primera con un botón que vuelva a llamar a la carga. Con la fábrica, ves el cambio; con un `DbContext` inyectado en el componente, ves el valor viejo.""",
            },
        ]
    },
    # 23) Docker para ASP.NET Core 8/9: imagen chiseled, usuario no root, puerto 8080, cabeceras reenviadas (system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde primero con el Dockerfile y después explica solo lo que no sea obvio."},
            {
                "role": "user",
                "content": "Dockerfile para una API ASP.NET Core 9 que va detrás de un ingress en Kubernetes. Imagen pequeña y segura. Ahora usamos `mcr.microsoft.com/dotnet/aspnet:6.0` y `EXPOSE 80`.",
            },
            {
                "role": "assistant",
                "content": r"""```dockerfile
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Primero solo los .csproj: la capa de restore se reutiliza mientras no cambien las dependencias.
COPY ["src/Shop.Api/Shop.Api.csproj", "src/Shop.Api/"]
RUN dotnet restore "src/Shop.Api/Shop.Api.csproj"

COPY . .
RUN dotnet publish "src/Shop.Api/Shop.Api.csproj" -c Release -o /app/publish --no-restore /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:9.0-noble-chiseled AS final
WORKDIR /app
COPY --from=build /app/publish .
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "Shop.Api.dll"]
```

Lo que no es obvio:

**El puerto es 8080, no 80.** Desde .NET 8, las imágenes oficiales escuchan en 8080 (variable `ASPNETCORE_HTTP_PORTS`). El 80 exige privilegios de root dentro del contenedor, y ya no se usa root. Al migrar desde la imagen de .NET 6, actualiza el `containerPort` del Deployment y el `targetPort` del Service, o el tráfico no llegará.

**`USER $APP_UID`.** Las imágenes de .NET 8+ traen un usuario sin privilegios (`app`) y la variable `APP_UID` con su identificador numérico. Usar el número, y no el nombre, permite a Kubernetes comprobar `runAsNonRoot: true` sin ambigüedad.

**Imagen *chiseled*.** Ubuntu recortado: sin shell, sin gestor de paquetes, solo lo necesario para ejecutar .NET. Es mucho más pequeña que la estándar y con muchas menos CVE que parchear. El precio: no puedes hacer `kubectl exec -- sh` para depurar. Para eso existen los contenedores efímeros (`kubectl debug`) con una imagen de herramientas. Tampoco hay `curl` para un `HEALTHCHECK` de Docker; en Kubernetes no lo necesitas, las sondas las hace el kubelet.

**Sin Dockerfile, si prefieres.** El SDK puede construir la imagen directamente: `dotnet publish -c Release /t:PublishContainer -p:ContainerBaseImage=mcr.microsoft.com/dotnet/aspnet:9.0-noble-chiseled`. Útil en CI sin Docker instalado.

### Detrás del ingress: cabeceras reenviadas

El TLS lo termina el ingress, así que la aplicación ve peticiones HTTP desde la IP del ingress. Sin configurar nada, `Request.Scheme` es `http` (las URL generadas y las redirecciones salen mal) y `RemoteIpAddress` es la del ingress (los límites por IP y los logs no sirven).

```csharp
builder.Services.Configure<ForwardedHeadersOptions>(o =>
{
    o.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
    // Solo se confía en X-Forwarded-* si la conexión viene de la red del clúster.
    o.KnownNetworks.Add(new Microsoft.AspNetCore.HttpOverrides.IPNetwork(IPAddress.Parse("10.0.0.0"), 8));
});

var app = builder.Build();
app.UseForwardedHeaders(); // el primero del pipeline
```

Existe un atajo, `ASPNETCORE_FORWARDEDHEADERS_ENABLED=true`, que activa el middleware confiando en **cualquier** origen. Úsalo solo si la aplicación es inalcanzable salvo a través del ingress; si no, cualquiera puede falsificar su IP con una cabecera.

Y quita `app.UseHttpsRedirection()` si el TLS termina en el ingress: dentro del clúster no hay HTTPS al que redirigir.

### Comprobación

```bash
docker build -t shop-api:local .
docker run --rm -p 8080:8080 -e ConnectionStrings__Shop="..." shop-api:local
curl -s localhost:8080/health/live
docker image inspect shop-api:local --format '{{.Config.User}}'   # un número, no vacío ni root
docker images shop-api:local                                       # del orden de 100-130 MB
```

En el clúster, registra un momento `Request.Scheme` y `RemoteIpAddress` en una petición de prueba: deben ser `https` y la IP real del cliente.""",
            },
        ]
    },
    # 24) Inanición del thread pool por sync-over-async (.Result) en un filtro (system variante, usuario trae síntoma).
    {
        "messages": [
            {"role": "system", "content": "Actúa como ingeniero de guardia: primero cómo estabilizar, después la causa y el arreglo definitivo."},
            {
                "role": "user",
                "content": r"""API .NET 8. Con carga moderada la latencia sube a 20-30 segundos, la CPU está al 15 % y la base de datos tranquila. Al reiniciar el pod mejora un rato y vuelve a pasar. Lo único «raro» que veo es este filtro que valida la API key contra otro servicio:

```csharp
public sealed class ApiKeyFilter(KeyServiceClient keys) : IAuthorizationFilter
{
    public void OnAuthorization(AuthorizationFilterContext context)
    {
        var key = context.HttpContext.Request.Headers["X-Api-Key"].ToString();
        var valid = keys.IsValidAsync(key).Result;
        if (!valid)
        {
            context.Result = new UnauthorizedResult();
        }
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Los síntomas (latencia enorme, CPU baja, dependencias tranquilas, mejora al reiniciar) son los de **inanición del thread pool**, y ese `.Result` es el sospechoso principal.

### Estabilizar ahora

1. **Escala horizontalmente** (más réplicas): reparte la carga y reduce la cola en cada proceso. Es lo único que no requiere desplegar código.
2. Si necesitas un parche en el mismo despliegue que el arreglo, sube el mínimo de hilos al arrancar. Es una **venda**, no un arreglo:

```csharp
// Temporal: retirar cuando el filtro sea asíncrono.
ThreadPool.SetMinThreads(workerThreads: 200, completionPortThreads: 200);
```

### Confirmar el diagnóstico (5 minutos)

```bash
dotnet-counters monitor -n Shop.Api --counters System.Runtime
```

Bajo carga, mira la longitud de la cola del thread pool y el número de hilos (en .NET 8, `ThreadPool Queue Length` y `ThreadPool Thread Count`). Si la cola crece sin parar y el número de hilos sube despacio, de uno en uno, es inanición. Para ver **dónde** están bloqueados:

```bash
dotnet-stack report -n Shop.Api
```

Encontrarás muchas pilas detenidas en la espera de una tarea (`Task.Wait`, `GetResult`) que salen de `ApiKeyFilter.OnAuthorization`.

### La causa

`IsValidAsync(...).Result` **bloquea** un hilo del pool hasta que termine la llamada HTTP. Pero la llamada, al completarse, necesita **otro** hilo del pool para ejecutar su continuación. Con carga, todas las peticiones entran en el filtro, cada una bloquea un hilo, y las continuaciones que las desbloquearían esperan en una cola a que haya hilos libres. El runtime añade hilos nuevos, pero despacio (es deliberado, para no crear miles ante un pico breve). Resultado: latencia de decenas de segundos con la CPU ociosa, porque los hilos no trabajan, esperan. Al reiniciar, la cola se vacía y el ciclo empieza de nuevo.

### El arreglo definitivo: asíncrono de punta a punta

ASP.NET Core tiene versión asíncrona de cada tipo de filtro:

```csharp
public sealed class ApiKeyFilter(KeyServiceClient keys) : IAsyncAuthorizationFilter
{
    public async Task OnAuthorizationAsync(AuthorizationFilterContext context)
    {
        var key = context.HttpContext.Request.Headers["X-Api-Key"].ToString();
        if (string.IsNullOrEmpty(key)
            || !await keys.IsValidAsync(key, context.HttpContext.RequestAborted))
        {
            context.Result = new UnauthorizedResult();
        }
    }
}
```

Y ya que cada petición llama a otro servicio para validar la misma clave, cachea el resultado unos minutos dentro de `KeyServiceClient` (con `HybridCache` o `IMemoryCache`): reduce la latencia y deja de depender de ese servicio en cada petición. Decide cuánto tiempo puede seguir siendo válida una clave revocada; ese es el TTL.

### Que no vuelva a pasar

- Busca el resto: `grep -rnE "\.Result\b|\.Wait\(\)|GetAwaiter\(\)\.GetResult\(\)" src/`. Cada coincidencia en código que corre durante una petición es un candidato.
- Añade el analizador `Microsoft.VisualStudio.Threading.Analyzers`: sus reglas `VSTHRD002` (esperas síncronas) y `VSTHRD103` (llamar a la versión síncrona existiendo la asíncrona) marcan estos patrones al compilar. Ponlas como error.
- Si una interfaz tuya es síncrona y su implementación necesita I/O, la interfaz está mal: cámbiala a `Task`. Los «adaptadores» con `.Result` son exactamente este incidente.

### Verificación

Prueba de carga con k6 a la concurrencia que provocó el incidente, antes y después del despliegue. Después: la cola del thread pool debe mantenerse cerca de cero y el número de hilos estable; la p99 debe quedar en el orden de la latencia del servicio de claves (o menos, con la caché). Y retira el `SetMinThreads` en cuanto lo confirmes: si se queda, esconderá el próximo caso.""",
            },
        ]
    },
    # 25) Rate limiting integrado (.NET 7+): políticas por endpoint, límite global por usuario/IP y 429 con Retry-After.
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesitamos limitar peticiones en una API .NET 8: el login a 5 intentos por minuto por IP y, en general, un máximo razonable por usuario. ¿Uso una librería o hay algo integrado?",
            },
            {
                "role": "assistant",
                "content": r"""Está integrado desde .NET 7: el middleware de *rate limiting* (`Microsoft.AspNetCore.RateLimiting`) sobre `System.Threading.RateLimiting`. Tiene ventana fija, ventana deslizante, *token bucket* y límite de concurrencia, con particiones por la clave que quieras.

```csharp
using System.Globalization;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.RateLimiting;

public static class RateLimitPolicies
{
    public const string Login = "login";
}

builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    options.OnRejected = async (context, ct) =>
    {
        if (context.Lease.TryGetMetadata(MetadataName.RetryAfter, out var retryAfter))
        {
            context.HttpContext.Response.Headers.RetryAfter =
                ((int)retryAfter.TotalSeconds).ToString(CultureInfo.InvariantCulture);
        }
        await context.HttpContext.Response.WriteAsJsonAsync(
            new { title = "Demasiadas peticiones", status = 429 }, ct);
    };

    // Login: 5 intentos por minuto por IP, sin cola.
    options.AddPolicy(RateLimitPolicies.Login, http => RateLimitPartition.GetFixedWindowLimiter(
        partitionKey: http.Connection.RemoteIpAddress?.ToString() ?? "unknown",
        factory: _ => new FixedWindowRateLimiterOptions
        {
            PermitLimit = 5,
            Window = TimeSpan.FromMinutes(1),
            QueueLimit = 0,
        }));

    // Global: token bucket por usuario autenticado, o por IP si es anónimo.
    options.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(http =>
    {
        var key = http.User.FindFirst("sub")?.Value is { } userId
            ? $"user:{userId}"
            : $"ip:{http.Connection.RemoteIpAddress}";
        return RateLimitPartition.GetTokenBucketLimiter(key, _ => new TokenBucketRateLimiterOptions
        {
            TokenLimit = 100,                          // ráfaga máxima
            TokensPerPeriod = 50,
            ReplenishmentPeriod = TimeSpan.FromSeconds(10), // ritmo sostenido: 5 por segundo
            QueueLimit = 0,
        });
    });
});

var app = builder.Build();

app.UseForwardedHeaders();   // si hay proxy: RemoteIpAddress debe ser la del cliente
app.UseAuthentication();     // antes del limiter: la partición global usa el usuario
app.UseRateLimiter();
app.UseAuthorization();

app.MapPost("/auth/login", Login).RequireRateLimiting(RateLimitPolicies.Login);
app.MapHealthChecks("/health/live").DisableRateLimiting();
```

Decisiones y sus porqués:

- **Ventana fija para el login**: la regla de negocio es literalmente «5 por minuto», y es fácil de explicar al usuario. Con *token bucket* para el resto: permite ráfagas razonables (una pantalla que carga 10 recursos a la vez) sin superar un ritmo sostenido.
- **`QueueLimit = 0`**: rechaza de inmediato en vez de retener peticiones esperando un permiso. En una API, una respuesta 429 rápida es mejor que una petición colgada.
- **Orden del pipeline**: el limitador global particiona por `sub`, así que la autenticación debe ir antes. Si va después, todos los usuarios autenticados caen en la partición de su IP.
- **`Retry-After`**: los clientes bien hechos esperan ese tiempo en vez de reintentar en bucle.
- **Las sondas de salud excluidas**: un pico no debe hacer que Kubernetes crea que la aplicación está caída.

Dos limitaciones que conviene conocer antes de confiar en él:

1. **Los contadores son por proceso.** Con 4 réplicas, el login admite hasta 20 intentos por minuto por IP en total. Para un límite global estricto, aplícalo en el gateway o el ingress, o usa un almacén compartido (Redis) con una implementación propia de `RateLimiter`.
2. **Limitar el login por IP no basta** contra ataques distribuidos: añade bloqueo por cuenta tras varios fallos (ASP.NET Core Identity lo trae con `Lockout`).

### Comprobación

```csharp
[Fact]
public async Task Sixth_login_attempt_in_a_minute_is_429_with_retry_after()
{
    var client = _factory.CreateClient();
    var body = new { email = "ana@example.com", password = "incorrecta" };

    for (var i = 0; i < 5; i++)
    {
        var allowed = await client.PostAsJsonAsync("/auth/login", body);
        Assert.NotEqual(HttpStatusCode.TooManyRequests, allowed.StatusCode);
    }
    var rejected = await client.PostAsJsonAsync("/auth/login", body);

    Assert.Equal(HttpStatusCode.TooManyRequests, rejected.StatusCode);
    Assert.True(rejected.Headers.Contains("Retry-After"));
}
```

En el servidor de test, `RemoteIpAddress` es la misma para todas las peticiones, así que el test ejercita una única partición: justo el caso que quieres comprobar.""",
            },
        ]
    },
    # 26) Inglés: IHttpClientFactory, clientes tipados y AddStandardResilienceHandler (.NET 8).
    {
        "messages": [
            {
                "role": "user",
                "content": "Our .NET 8 service does `new HttpClient()` in a few places and sometimes we hit socket exhaustion; elsewhere a static HttpClient doesn't pick up DNS changes after a failover. What's the right setup, including retries and timeouts?",
            },
            {
                "role": "assistant",
                "content": r"""Both symptoms come from managing `HttpClient` lifetime by hand. `new HttpClient()` per call opens new connections each time and leaves sockets in `TIME_WAIT` until the OS runs out; a single static instance keeps its connections (and the DNS answer behind them) forever. **`IHttpClientFactory`** solves both by pooling and rotating the underlying handlers. Add **`Microsoft.Extensions.Http.Resilience`** for retries, timeouts and circuit breaking.

### Registration: a typed client per downstream service

```csharp
builder.Services.AddOptions<InventoryOptions>()
    .BindConfiguration("Inventory")
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddHttpClient<InventoryClient>((sp, client) =>
    {
        var options = sp.GetRequiredService<IOptions<InventoryOptions>>().Value;
        client.BaseAddress = new Uri(options.BaseUrl); // e.g. "https://inventory.internal/api/" with trailing slash
    })
    .AddStandardResilienceHandler(options =>
    {
        options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(2);      // each try
        options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(6); // all tries together
        options.Retry.MaxRetryAttempts = 2;
        options.Retry.DisableForUnsafeHttpMethods();                   // never retry POST/PUT/PATCH/DELETE
    });
```

`AddStandardResilienceHandler` stacks, in order: a rate limiter, the total timeout, retries with exponential backoff and jitter, a circuit breaker, and the per-attempt timeout. Defaults are sensible; the overrides above tighten the timeouts for an internal service and make the retry policy safe for writes.

### The typed client

```csharp
public sealed class InventoryClient(HttpClient http)
{
    public async Task<StockDto?> GetStockAsync(string sku, CancellationToken ct)
    {
        using var response = await http.GetAsync($"stock/{Uri.EscapeDataString(sku)}", ct);
        if (response.StatusCode == HttpStatusCode.NotFound)
        {
            return null; // unknown SKU is an answer, not a failure
        }
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<StockDto>(ct);
    }
}

public sealed record StockDto(string Sku, int Available);
```

Inject `InventoryClient` wherever you need it. The factory hands it an `HttpClient` whose handler is pooled and recycled periodically, so connections are reused and DNS is re-resolved.

### The traps

- **Don't capture a typed client in a singleton.** Typed clients are registered as transient. A singleton that receives one keeps that `HttpClient` (and its handler) forever, which brings back the stale-DNS problem. If a singleton needs it, inject `IHttpClientFactory` and create the client per operation, or make the consumer scoped.
- **Relative URLs and the trailing slash.** With `BaseAddress = "https://inventory.internal/api"` (no slash), `"stock/X"` resolves to `https://inventory.internal/stock/X`. Keep the trailing slash and use relative paths without a leading one.
- **`HttpClient.Timeout`** defaults to 100 s and wraps the whole pipeline. With the resilience handler's total timeout at 6 s, the handler fires first; just don't set `HttpClient.Timeout` lower than the total timeout or retries get cut off.
- **Idempotency for writes.** With retries disabled for `POST`, a timeout on a payment call surfaces as an error. If you need retries there, the downstream API must accept an idempotency key, and you add the retry deliberately for that call.

### Testing the client

No factory needed for unit tests; give it an `HttpClient` with a stub handler:

```csharp
public sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
{
    public List<HttpRequestMessage> Requests { get; } = [];

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
    {
        Requests.Add(request);
        return Task.FromResult(respond(request));
    }
}

[Fact]
public async Task Unknown_sku_returns_null()
{
    var handler = new StubHandler(_ => new HttpResponseMessage(HttpStatusCode.NotFound));
    var client = new InventoryClient(new HttpClient(handler) { BaseAddress = new Uri("https://inventory.test/api/") });

    var stock = await client.GetStockAsync("NOPE 01", CancellationToken.None);

    Assert.Null(stock);
    Assert.Equal("https://inventory.test/api/stock/NOPE%2001", handler.Requests.Single().RequestUri!.ToString());
}
```

The URL assertion catches both the trailing-slash trap and missing escaping. To check the resilience configuration itself, an integration test with WireMock.Net returning 503 twice and then 200 should see three requests for a `GET` and exactly one for a `POST`.""",
            },
        ]
    },
    # 27) Health checks: liveness vs readiness, DbContext check, check propio y la trampa de la fallback policy (system variante: México).
    {
        "messages": [
            {"role": "system", "content": "Responde breve y práctico, en español de México."},
            {
                "role": "user",
                "content": "¿Cómo configuro los health checks de una API .NET 8 para las sondas de Kubernetes? Usamos Postgres y Redis.",
            },
            {
                "role": "assistant",
                "content": r"""La clave es separar dos preguntas que Kubernetes hace por separado:

- **Liveness**: «¿el proceso está vivo o se colgó?». Si falla, Kubernetes **reinicia** el pod.
- **Readiness**: «¿puede atender tráfico ahorita?». Si falla, lo **saca del balanceo** sin reiniciarlo.

Las dependencias (Postgres, Redis) van **solo** en readiness. Si las pones en liveness, una caída de Postgres hace que Kubernetes reinicie todos tus pods en cadena, y reiniciar no arregla una base de datos.

```csharp
builder.Services.AddHealthChecks()
    .AddDbContextCheck<ShopDbContext>("postgres", tags: ["ready"])
    .AddCheck<RedisHealthCheck>("redis", tags: ["ready"]);

var app = builder.Build();

// Liveness: no ejecuta ningún check; responde si el proceso atiende peticiones.
app.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false })
   .AllowAnonymous()
   .DisableRateLimiting();

// Readiness: solo los checks marcados "ready".
app.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") })
   .AllowAnonymous()
   .DisableRateLimiting();
```

`AddDbContextCheck` viene en `Microsoft.Extensions.Diagnostics.HealthChecks.EntityFrameworkCore` y comprueba que el contexto puede conectarse.

Un check propio para Redis, con umbral de latencia:

```csharp
public sealed class RedisHealthCheck(IConnectionMultiplexer redis) : IHealthCheck
{
    private static readonly TimeSpan SlowThreshold = TimeSpan.FromMilliseconds(200);

    public async Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext context, CancellationToken ct = default)
    {
        try
        {
            var latency = await redis.GetDatabase().PingAsync();
            return latency < SlowThreshold
                ? HealthCheckResult.Healthy()
                : HealthCheckResult.Degraded($"Redis responde lento: {latency.TotalMilliseconds:F0} ms");
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Unhealthy("Redis no responde", ex);
        }
    }
}
```

`Degraded` responde 200 por defecto: el pod sigue recibiendo tráfico, pero el estado queda visible para tus alertas.

Y en el Deployment:

```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /health/ready, port: 8080 }
  periodSeconds: 5
  failureThreshold: 2
startupProbe:
  httpGet: { path: /health/live, port: 8080 }
  periodSeconds: 5
  failureThreshold: 24   # hasta 2 minutos para arrancar
```

Tres trampas que vale la pena revisar:

1. **`AllowAnonymous()`**: si tienes una *fallback policy* que exige usuario autenticado, sin esto las sondas reciben 401 y Kubernetes cree que todo está caído.
2. **`DisableRateLimiting()`**: en un pico, el limitador no debe rechazar las sondas.
3. **No expongas el detalle**: el escritor por defecto solo devuelve `Healthy`/`Unhealthy`. Si agregas uno con detalle (versiones, hosts), que sea en una ruta interna, no pública.

Para comprobarlo: con la app corriendo, `curl -i localhost:8080/health/ready` debe dar 200; para Postgres (o bloquéalo con una regla de red) y debe pasar a 503, mientras `/health/live` sigue en 200. En el clúster, `kubectl get endpoints` debe mostrar que el pod sale del Service sin que aumente su contador de reinicios.""",
            },
        ]
    },
    # 28) EF Core: filtros globales de consulta para multi-tenant y borrado lógico; trampas de caché del modelo y pooling.
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestra API es multi-tenant con una sola base de datos y columna `TenantId` en cada tabla. Cada consulta lleva su `Where(x => x.TenantId == tenantId)` y una vez alguien lo olvidó y un cliente vio datos de otro. ¿Cómo lo hacemos a prueba de olvidos con EF Core 8? También queremos borrado lógico.",
            },
            {
                "role": "assistant",
                "content": r"""Con **filtros globales de consulta** (`HasQueryFilter`): una condición que EF añade automáticamente a todas las consultas de una entidad. El filtro se escribe una vez y deja de depender de la memoria de cada desarrollador.

### El contexto

```csharp
public interface ITenantContext
{
    int TenantId { get; }
}

public interface ITenantOwned
{
    int TenantId { get; set; }
}

public interface ISoftDeletable
{
    bool IsDeleted { get; set; }
    DateTimeOffset? DeletedAt { get; set; }
}

public sealed class ShopDbContext : DbContext
{
    private readonly ITenantContext _tenant;

    public ShopDbContext(DbContextOptions<ShopDbContext> options, ITenantContext tenant) : base(options) =>
        _tenant = tenant;

    // Propiedad de la instancia: EF la trata como parámetro y la evalúa en cada consulta.
    public int CurrentTenantId => _tenant.TenantId;

    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Product> Products => Set<Product>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Order>().HasQueryFilter(o => o.TenantId == CurrentTenantId && !o.IsDeleted);
        modelBuilder.Entity<Product>().HasQueryFilter(p => p.TenantId == CurrentTenantId && !p.IsDeleted);

        // Un SKU único por tenant entre los no borrados.
        modelBuilder.Entity<Product>()
            .HasIndex(p => new { p.TenantId, p.Sku })
            .IsUnique()
            .HasFilter("\"IsDeleted\" = false");
    }

    public override Task<int> SaveChangesAsync(CancellationToken ct = default)
    {
        foreach (var entry in ChangeTracker.Entries<ITenantOwned>().Where(e => e.State == EntityState.Added))
        {
            entry.Entity.TenantId = CurrentTenantId; // el tenant de las inserciones tampoco se olvida
        }
        foreach (var entry in ChangeTracker.Entries<ISoftDeletable>().Where(e => e.State == EntityState.Deleted))
        {
            entry.State = EntityState.Modified;      // Remove() pasa a ser un borrado lógico
            entry.Entity.IsDeleted = true;
            entry.Entity.DeletedAt = DateTimeOffset.UtcNow;
        }
        return base.SaveChangesAsync(ct);
    }
}
```

`ITenantContext` lo implementa un servicio *scoped* que lee el tenant del usuario autenticado (un claim), nunca de un parámetro que el cliente pueda cambiar.

### Las trampas, que son el motivo real de esta respuesta

1. **El modelo se construye una sola vez y se cachea.** El filtro funciona porque referencia `CurrentTenantId`, una propiedad **del contexto**: EF la convierte en un parámetro que lee de cada instancia. Si en `OnModelCreating` hubieras escrito `var tenantId = _tenant.TenantId;` y filtrado por `tenantId`, ese valor quedaría **congelado** en el modelo con el tenant de la primera petición, y todos los tenants verían los datos de ese. Es exactamente el tipo de fuga que quieres evitar.
2. **`AddDbContextPool` no admite dependencias *scoped* en el constructor.** Un contexto del pool se reutiliza entre peticiones y su constructor solo se ejecuta una vez. Con pooling, el tenant hay que asignarlo en cada préstamo (por ejemplo, una propiedad que se fija tras obtener el contexto). Sin pooling, como arriba, no hay problema.
3. **`IgnoreQueryFilters()` quita todos los filtros de golpe** (hasta EF Core 9; EF Core 10 añade filtros con nombre para desactivarlos de uno en uno). Si un panel de administración lo usa para ver los borrados, también deja de filtrar por tenant. Úsalo solo en sitios revisados y añade el `Where` del tenant a mano en esas consultas.
4. **SQL directo no pasa por el filtro.** `FromSql` sobre un `DbSet` sí lo aplica (EF envuelve tu SQL), pero `ExecuteSqlRaw` y Dapper no. Esas consultas deben llevar el tenant explícito.

Si el aislamiento entre tenants es crítico, añade una segunda capa en la base de datos: *Row-Level Security* de Postgres con el tenant en una variable de sesión. Así, ni un `IgnoreQueryFilters` olvidado ni una consulta en SQL directo pueden cruzar tenants.

### Comprobación

```csharp
[Fact]
public async Task Tenants_cannot_see_each_other()
{
    await using var connection = new SqliteConnection("DataSource=:memory:");
    await connection.OpenAsync();
    var options = new DbContextOptionsBuilder<ShopDbContext>().UseSqlite(connection).Options;

    await using (var tenantA = new ShopDbContext(options, new FixedTenant(1)))
    {
        await tenantA.Database.EnsureCreatedAsync();
        tenantA.Orders.Add(new Order { CustomerId = "c-1" });
        await tenantA.SaveChangesAsync();
    }

    await using var tenantB = new ShopDbContext(options, new FixedTenant(2));
    Assert.Empty(await tenantB.Orders.ToListAsync());

    await using var tenantA2 = new ShopDbContext(options, new FixedTenant(1));
    Assert.Single(await tenantA2.Orders.ToListAsync());
}

private sealed record FixedTenant(int TenantId) : ITenantContext;
```

El test crea los dos contextos con las **mismas** opciones, es decir, con el mismo modelo cacheado: si el filtro hubiera capturado un valor fijo (trampa 1), `tenantB` vería el pedido y el test fallaría. SQLite basta para esta comprobación; el índice filtrado con sintaxis de Postgres pruébalo contra Postgres real.""",
            },
        ]
    },
    # 29) CancellationToken en endpoints y EF Core; después cancelación a mitad de SaveChanges e idempotencia (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi jefe quiere que pasemos `CancellationToken` en todos los endpoints y métodos async. A mí me parece ruido en las firmas. ¿Sirve de verdad en una API?",
            },
            {
                "role": "assistant",
                "content": r"""Sirve, y mucho más en una API que en una aplicación de escritorio. El caso concreto: el cliente se va (cerró la pestaña, su timeout de 10 s expiró, el balanceador cortó a los 30 s) mientras tu servidor sigue ejecutando una consulta pesada para nadie. Sin el token, esa consulta ocupa una conexión del pool y CPU de la base de datos hasta terminar. Con carga, esas consultas huérfanas se acumulan justo cuando el sistema ya va lento, y lo hunden más.

En Minimal APIs (y en controladores) el parámetro `CancellationToken` se enlaza solo con `HttpContext.RequestAborted`, que se cancela cuando el cliente se desconecta:

```csharp
app.MapGet("/api/reports/sales", async (DateOnly from, DateOnly to, ShopDbContext db, CancellationToken ct) =>
{
    var rows = await db.Orders
        .Where(o => o.CreatedOn >= from && o.CreatedOn <= to)
        .GroupBy(o => o.CreatedOn)
        .Select(g => new SalesRow(g.Key, g.Count(), g.Sum(o => o.TotalCents)))
        .ToListAsync(ct); // si el cliente se va, Npgsql cancela la consulta en Postgres
    return TypedResults.Ok(rows);
});
```

Con EF Core sobre Npgsql (y SqlClient), cancelar el token envía una cancelación real al servidor de base de datos: la consulta se detiene allí, no solo se deja de esperar.

Dónde pasarlo siempre:

- A EF Core (`ToListAsync(ct)`, `SaveChangesAsync(ct)`, `ExecuteUpdateAsync(..., ct)`).
- A `HttpClient` (`GetAsync(url, ct)`), para que las llamadas a otros servicios también se corten.
- A cualquier método tuyo que haga I/O, como último parámetro.

Para que no dependa de la disciplina de cada uno, activa el analizador **CA2016** («reenviar el parámetro CancellationToken») como advertencia o error: marca cada llamada que acepta un token y no lo recibe.

Un detalle de logs: cuando el cliente se va, sube una `OperationCanceledException`. No es un error de tu aplicación; si tienes código que registra excepciones, distingue ese caso para no llenar los logs de falsos errores:

```csharp
catch (OperationCanceledException) when (ct.IsCancellationRequested)
{
    // El cliente canceló: nada que registrar como error.
    throw;
}
```

Comprobación: un endpoint de prueba con una consulta lenta (`SELECT pg_sleep(30)` vía `FromSql`), una petición con `curl --max-time 2` y, en Postgres, `SELECT state, query FROM pg_stat_activity WHERE query LIKE '%pg_sleep%'`. Con el token, la consulta desaparece a los 2 segundos; sin él, sigue 30.""",
            },
            {
                "role": "user",
                "content": "Vale, convencido. Pero ¿qué pasa si el cliente cancela justo en mitad del `SaveChangesAsync(ct)` de un pedido? ¿Queda a medias?",
            },
            {
                "role": "assistant",
                "content": r"""No queda a medias, pero puede quedar **hecho sin que el cliente lo sepa**, que es el caso que hay que diseñar.

`SaveChangesAsync` envuelve todos los cambios en una transacción. Según en qué momento llegue la cancelación:

| Momento | Resultado en la base de datos | Lo que ve el cliente |
|---|---|---|
| Antes o durante los `INSERT`/`UPDATE` | *rollback*: nada guardado | error (o nada, se fue) |
| Después del *commit* | todo guardado | error o desconexión: **cree que falló** |

La segunda fila es el problema real: el pedido existe, el cliente no recibió el 201, y lo normal es que reintente. Sin protección, tienes un pedido duplicado. Esto no lo causa el `CancellationToken`: pasa igual si se corta la red o vence el timeout del balanceador. El token solo hace más evidente un caso que ya existía.

La solución es la **idempotencia**: el cliente genera una clave única por intento lógico de compra y la reenvía en los reintentos.

```csharp
public sealed record PlaceOrderRequest(Guid IdempotencyKey, List<OrderLineRequest> Lines);

// En la configuración de la entidad:
builder.HasIndex(o => o.IdempotencyKey).IsUnique();
```

```csharp
app.MapPost("/api/orders", async Task<Results<Created<OrderDto>, Ok<OrderDto>>> (
    PlaceOrderRequest request, ShopDbContext db, ClaimsPrincipal user, CancellationToken ct) =>
{
    // ¿Ya se procesó este intento? Devolvemos el mismo pedido, no uno nuevo.
    var existing = await db.Orders.AsNoTracking()
        .FirstOrDefaultAsync(o => o.IdempotencyKey == request.IdempotencyKey, ct);
    if (existing is not null)
    {
        return TypedResults.Ok(OrderDto.From(existing));
    }

    var customerId = user.FindFirstValue("sub")!; // el endpoint exige autenticación
    var order = Order.Place(customerId, request.IdempotencyKey, request.Lines);
    db.Orders.Add(order);
    try
    {
        await db.SaveChangesAsync(ct);
    }
    catch (DbUpdateException ex) when (ex.InnerException is PostgresException { SqlState: PostgresErrorCodes.UniqueViolation })
    {
        // Dos reintentos simultáneos: ganó el otro. Devolvemos su resultado.
        var winner = await db.Orders.AsNoTracking()
            .SingleAsync(o => o.IdempotencyKey == request.IdempotencyKey, CancellationToken.None);
        return TypedResults.Ok(OrderDto.From(winner));
    }
    return TypedResults.Created($"/api/orders/{order.Id}", OrderDto.From(order));
});
```

Dos decisiones sobre los tokens dentro de este flujo:

- **Antes del *commit*, respeta la cancelación**: si el cliente se fue, no tiene sentido guardar.
- **Después del *commit*, decide qué debe completarse sí o sí.** Si tras guardar el pedido tienes que publicar un evento o enviar un email, esa parte no debería abortarse porque el cliente cerró la pestaña: el pedido ya existe. Usa `CancellationToken.None` (o el token de parada de la aplicación) para esos pasos, o mejor, escríbelos en una tabla *outbox* dentro de la misma transacción y que un worker los procese. Por eso la consulta del caso de conflicto usa `CancellationToken.None`: necesitamos la respuesta correcta aunque el cliente ya no esté.

### Comprobación

- Dos `POST` secuenciales con la misma `IdempotencyKey`: el primero 201, el segundo 200 con el **mismo** `Id`, y una sola fila en la tabla.
- Dos `POST` simultáneos con la misma clave (`Task.WhenAll` en un test de integración contra Postgres): ambos devuelven el mismo `Id` y hay una sola fila. Ese test es el que demuestra que el índice único y el `catch` cubren la carrera, no solo el caso secuencial.""",
            },
        ]
    },
    # 30) Inglés: "A second operation was started on this context instance" por Task.WhenAll con el mismo DbContext (usuario trae excepción).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""To speed up a dashboard endpoint I parallelized three queries and now it fails intermittently:

```
System.InvalidOperationException: A second operation was started on this context instance before a previous operation completed. This is usually caused by different threads concurrently using the same instance of DbContext. For more information on how to avoid threading issues with DbContext, see https://go.microsoft.com/fwlink/?linkid=2097913.
```

```csharp
var ordersTask = db.Orders.Where(o => o.CustomerId == id).CountAsync(ct);
var spentTask = db.Orders.Where(o => o.CustomerId == id).SumAsync(o => o.TotalCents, ct);
var ticketsTask = db.SupportTickets.Where(t => t.CustomerId == id && t.Open).CountAsync(ct);
await Task.WhenAll(ordersTask, spentTask, ticketsTask);
```""",
            },
            {
                "role": "assistant",
                "content": r"""A `DbContext` is not thread-safe and supports **one operation at a time**: it wraps a single database connection and a change tracker, neither of which can serve two queries concurrently. Starting three queries before awaiting any of them is exactly what the message describes. It is intermittent because sometimes the first query finishes before the second one starts; under load it doesn't.

Before choosing a fix, ask whether parallelism buys anything. Three small aggregate queries take a few milliseconds each. Run sequentially, that is a few milliseconds more, on one connection. Run in parallel, it needs three connections from the pool per request, which under load means waiting for the pool instead.

### Option 1: one query (best here)

All three numbers can come from a single round trip:

```csharp
var summary = await db.Customers
    .Where(c => c.Id == id)
    .Select(c => new CustomerDashboard(
        c.Orders.Count(),
        c.Orders.Sum(o => (long?)o.TotalCents) ?? 0,
        c.SupportTickets.Count(t => t.Open)))
    .SingleOrDefaultAsync(ct);
```

EF translates this into one SQL statement with correlated subqueries. One connection, one round trip, no concurrency question at all. The `(long?)` cast makes the sum of zero orders come back as `null` and default to 0 instead of throwing.

### Option 2: sequential awaits

If the queries can't be combined (different shapes, different tables with no navigation), simply await them in order:

```csharp
var orders = await db.Orders.CountAsync(o => o.CustomerId == id, ct);
var spent = await db.Orders.Where(o => o.CustomerId == id).SumAsync(o => o.TotalCents, ct);
var tickets = await db.SupportTickets.CountAsync(t => t.CustomerId == id && t.Open, ct);
```

### Option 3: real parallelism, one context per query

Only when the queries are genuinely slow (hundreds of milliseconds each) and independent. Use a factory so each query gets its own context and connection:

```csharp
builder.Services.AddDbContextFactory<ShopDbContext>(
    o => o.UseNpgsql(builder.Configuration.GetConnectionString("Shop")),
    ServiceLifetime.Scoped); // scoped so it coexists with the AddDbContext registration
```

```csharp
public sealed class DashboardQueries(IDbContextFactory<ShopDbContext> factory)
{
    public async Task<CustomerDashboard> LoadAsync(int customerId, CancellationToken ct)
    {
        var orders = CountOrdersAsync(customerId, ct);
        var spent = SumSpentAsync(customerId, ct);
        var tickets = CountOpenTicketsAsync(customerId, ct);
        await Task.WhenAll(orders, spent, tickets);
        return new CustomerDashboard(orders.Result, spent.Result, tickets.Result); // already completed: no blocking
    }

    private async Task<int> CountOrdersAsync(int customerId, CancellationToken ct)
    {
        await using var db = await factory.CreateDbContextAsync(ct);
        return await db.Orders.CountAsync(o => o.CustomerId == customerId, ct);
    }

    private async Task<long> SumSpentAsync(int customerId, CancellationToken ct)
    {
        await using var db = await factory.CreateDbContextAsync(ct);
        return await db.Orders.Where(o => o.CustomerId == customerId).SumAsync(o => (long?)o.TotalCents, ct) ?? 0;
    }

    private async Task<int> CountOpenTicketsAsync(int customerId, CancellationToken ct)
    {
        await using var db = await factory.CreateDbContextAsync(ct);
        return await db.SupportTickets.CountAsync(t => t.CustomerId == customerId && t.Open, ct);
    }
}
```

The cost is explicit now: three pooled connections per request. Size the pool for it, or you have moved the bottleneck rather than removed it.

### The same error from a different cause

If you see it without any `Task.WhenAll`, look for a missing `await` (a query started and never awaited before the next one), an `async void` method, or a fire-and-forget `Task.Run` that uses the request's scoped `DbContext`. The last one usually shows up later as an `ObjectDisposedException` when the request ends and disposes the context under the background task.

### Verification

Write a test that runs the endpoint 200 times concurrently against Postgres (`Task.WhenAll` over `HttpClient` calls from `WebApplicationFactory`). With the original code it fails within the first few dozen calls; with option 1 or 2 it never does. For option 1, also check with `ToQueryString()` or the EF command log that exactly one SQL statement is executed per request.""",
            },
        ]
    },
]
