"""C# 12/13 y .NET 8/9: idiomática, async, LINQ, memoria, DI, pruebas y herramientas."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) records vs class (multiturno, principiante)
    {
        "messages": [
            {"role": "user", "content": "¿Qué diferencia hay entre un record y una clase en C#? ¿Cuándo uso cada uno?"},
            {
                "role": "assistant",
                "content": r"""Un `record` es una clase (o struct, con `record struct`) a la que el compilador le genera igualdad por valor, `ToString()` legible, deconstrucción y la expresión `with`. Una `class` normal compara por referencia: dos objetos con los mismos datos son distintos.

```csharp
public record Customer(string Name, string Email);

var a = new Customer("Ana", "ana@example.com");
var b = new Customer("Ana", "ana@example.com");

Console.WriteLine(a == b);          // True  (igualdad por valor)
Console.WriteLine(ReferenceEquals(a, b)); // False
Console.WriteLine(a);               // Customer { Name = Ana, Email = ana@example.com }

var c = a with { Email = "ana@corp.com" };  // copia con un cambio, `a` no se toca
```

La forma posicional `record Customer(string Name, string Email)` genera propiedades `init` (solo asignables al construir) y un constructor. Puedes añadir miembros dentro de las llaves igual que en una clase.

Cuándo usar cada uno:

| Usa `record` cuando | Usa `class` cuando |
|---|---|
| El tipo representa **datos**: DTOs, mensajes, eventos, resultados de consulta | El tipo tiene **identidad**: una entidad de EF Core, un servicio, una conexión |
| Quieres igualdad por contenido (claves de diccionario, tests con `Assert.Equal`) | La igualdad por referencia es la correcta (dos pedidos con los mismos campos siguen siendo dos pedidos) |
| El objeto es inmutable y lo "modificas" creando copias con `with` | El objeto muta a lo largo de su vida |

Dos avisos:

- Un `record` con propiedades `set` públicas pierde la gracia: la igualdad por valor con objetos mutables da claves de diccionario que cambian de hash después de insertarse. Si lo haces inmutable (`init`), el problema desaparece.
- EF Core funciona con records, pero las entidades con identidad mutan (se les asigna el Id, cambian de estado), así que ahí una `class` es más honesta.

Regla corta: datos sin identidad → `record`; cosas con ciclo de vida → `class`.""",
            },
            {"role": "user", "content": "Entonces si mi record tiene una propiedad List<string>, ¿dos records con la misma lista son iguales?"},
            {
                "role": "assistant",
                "content": r"""No. La igualdad generada compara cada propiedad con `EqualityComparer<T>.Default`, y para `List<string>` eso es igualdad por referencia. Dos listas distintas con el mismo contenido no son iguales.

```csharp
public record Order(int Id, List<string> Tags);

var x = new Order(1, new List<string> { "urgente" });
var y = new Order(1, new List<string> { "urgente" });

Console.WriteLine(x == y);  // False: las listas son objetos distintos
```

Y hay un segundo efecto: `with` hace una copia superficial, así que `x with { Id = 2 }` comparte la **misma** lista que `x`. Si una de las dos la muta, la otra lo ve.

Tienes tres salidas, de más a menos recomendable:

1. **Usar un tipo con igualdad por valor.** `ImmutableArray<string>` no sirve (también compara por referencia), pero puedes exponer la colección como `IReadOnlyList<string>` y comparar a mano (opción 2), o guardar un `string` normalizado si los tags son pocos.

2. **Implementar la igualdad de esa propiedad.** Un record permite definir `Equals` y `GetHashCode` propios; el resto de la maquinaria (`with`, deconstrucción, `ToString`) se conserva:

```csharp
public record Order(int Id, IReadOnlyList<string> Tags)
{
    public virtual bool Equals(Order? other) =>
        other is not null
        && Id == other.Id
        && Tags.SequenceEqual(other.Tags);

    public override int GetHashCode()
    {
        var hash = new HashCode();
        hash.Add(Id);
        foreach (var tag in Tags) hash.Add(tag);
        return hash.ToHashCode();
    }
}
```

El `Equals(Order?)` debe ser `virtual` y con ese tipo exacto, porque es la firma que el compilador genera y enlaza desde `==`.

3. **Aceptar la igualdad por referencia** y no usar ese record como clave ni en `Assert.Equal`. Válido si solo lo usas como DTO de paso.

Prueba rápida para no olvidarlo: `new Order(1, ["a"]) == new Order(1, ["a"])` debe dar `True` con la opción 2 y `False` sin ella.""",
            },
        ]
    },
    # 2) pattern matching moderno (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo un switch con un montón de ifs dentro para procesar comandos de un bot. El comando llega ya partido en un string[] (por ejemplo [\"add\", \"3\", \"4\"] o [\"echo\", \"hola\", \"mundo\"]). ¿Cómo lo haría con pattern matching moderno?"},
            {
                "role": "assistant",
                "content": r"""Con una *switch expression* y **list patterns** (C# 11) el despacho queda declarativo: cada brazo describe la forma del array, y `when` añade condiciones.

```csharp
using System.Globalization;

static string Handle(string[] args) => args switch
{
    [] => "Escribe un comando.",
    ["help"] => "Comandos: add, echo, repeat.",

    ["add", var a, var b]
        when int.TryParse(a, out var x) && int.TryParse(b, out var y)
        => (x + y).ToString(CultureInfo.InvariantCulture),
    ["add", ..] => "Uso: add <entero> <entero>",

    ["echo", .. var rest] => string.Join(' ', rest),

    ["repeat", var n, .. var words]
        when int.TryParse(n, out var times) && times is > 0 and <= 10
        => string.Join(' ', Enumerable.Repeat(string.Join(' ', words), times)),
    ["repeat", ..] => "Uso: repeat <1-10> <texto>",

    [var unknown, ..] => $"Comando desconocido: {unknown}",
};
```

Qué hace cada pieza:

- `[]` y `["help"]` casan por longitud y contenido exacto.
- `["add", var a, var b]` exige exactamente tres elementos y captura el segundo y el tercero.
- `..` es el *slice pattern*: «cero o más elementos». `.. var rest` captura ese tramo como `string[]`.
- `times is > 0 and <= 10` es un patrón relacional combinado; se lee mejor que `times > 0 && times <= 10` cuando lo mezclas con otros patrones.
- Los brazos se evalúan en orden, por eso el `["add", ..]` genérico va **después** del específico: recoge los `add` mal formados sin repetir la validación.
- `[var unknown, ..]` cierra el switch: cualquier array con al menos un elemento. Como `[]` ya está arriba, el compilador sabe que el switch es exhaustivo y no emite el aviso CS8509.

Si el bot crece, el siguiente paso es parsear primero a un record y casar sobre él con *property patterns*:

```csharp
public abstract record Command;
public sealed record Add(int A, int B) : Command;
public sealed record Echo(string Text) : Command;

static string Run(Command cmd) => cmd switch
{
    Add { A: 0, B: 0 } => "0",
    Add(var a, var b) => (a + b).ToString(),
    Echo { Text.Length: 0 } => "(vacío)",
    Echo(var text) => text,
    _ => throw new UnreachableException(),
};
```

`Text.Length: 0` es un patrón de propiedad extendido (C# 10): entra en la propiedad anidada sin paréntesis extra. `UnreachableException` (.NET 7+) documenta que ese `_` no debería ejecutarse nunca.

Verificación mínima:

```csharp
Debug.Assert(Handle(["add", "3", "4"]) == "7");
Debug.Assert(Handle(["echo", "hola", "mundo"]) == "hola mundo");
Debug.Assert(Handle(["add", "x", "4"]) == "Uso: add <entero> <entero>");
Debug.Assert(Handle([]) == "Escribe un comando.");
```

`["add", "3", "4"]` como argumento es una *collection expression* (C# 12): el compilador infiere `string[]`.""",
            },
        ]
    },
    # 3) nullable reference types: el usuario trae warnings
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Activé <Nullable>enable</Nullable> en un proyecto viejo y tengo 400 warnings. Los más repetidos:

```
warning CS8618: Non-nullable property 'Name' must contain a non-null value when exiting constructor. Consider adding the 'required' modifier or declaring the property as nullable.
warning CS8602: Dereference of a possibly null reference.
warning CS8625: Cannot convert null literal to non-nullable reference type.
```

¿Lo arreglo poniendo `!` en todos lados y ya?""",
            },
            {
                "role": "assistant",
                "content": r"""No. `!` solo silencia el análisis en ese punto; en tiempo de ejecución no cambia nada. Con 400 `!` tendrías el mismo código inseguro de antes y, además, habrías perdido la única herramienta que te dice dónde está el riesgo. Úsalo solo donde **tú sabes algo que el compilador no puede saber** y deja un comentario con el porqué.

Los tres códigos tienen cada uno una solución de patrón.

**CS8618: propiedad no inicializada al salir del constructor.** Decide qué significa esa propiedad:

```csharp
public sealed class Customer
{
    // 1) Obligatoria y la asigna quien construye (DTO, opciones, binding):
    public required string Name { get; init; }

    // 2) Puede no existir de verdad: dilo en el tipo.
    public string? Nickname { get; set; }

    // 3) Entidad de EF Core: EF la rellena después del constructor.
    //    Patrón documentado por el propio equipo de EF; comenta por qué.
    public string Email { get; set; } = null!;

    // 4) Si tiene un valor neutro razonable, inicialízala.
    public List<Order> Orders { get; } = [];
}
```

`required` (C# 11) convierte el olvido en error de compilación en el sitio de construcción, que es justo lo que quieres.

**CS8602: desreferencia de algo posiblemente null.** El aviso suele ser verdad. Tres respuestas válidas, según el caso:

```csharp
// a) Es un error de programación si es null: falla pronto y con mensaje.
var user = repo.Find(id) ?? throw new InvalidOperationException($"User {id} not found");
Console.WriteLine(user.Name.Length);

// b) Null es un caso normal: propaga el null.
var length = repo.Find(id)?.Name.Length ?? 0;

// c) Tus propios métodos Try: anota el contrato para que el flujo lo entienda.
using System.Diagnostics.CodeAnalysis;

public bool TryGetUser(int id, [NotNullWhen(true)] out User? user)
{
    user = repo.Find(id);
    return user is not null;
}

if (TryGetUser(7, out var found))
    Console.WriteLine(found.Name); // sin warning: el atributo lo garantiza
```

El caso (c) es el que más warnings quita de golpe en código viejo: cada `TryX` sin atributo genera un CS8602 en cada llamada.

**CS8625: pasas `null` a un parámetro no anulable.** La firma miente. O el parámetro acepta null (`string? note = null`) o la llamada no debe pasarlo. No lo tapes con `null!`.

**Cómo abordarlo sin parar el equipo:**

1. Deja `<Nullable>enable</Nullable>` en el csproj pero convierte los warnings en errores solo para archivos limpios: añade `#nullable enable` arriba de los que vayas migrando y, mientras tanto, `<WarningsNotAsErrors>nullable</WarningsNotAsErrors>` si ya usas `TreatWarningsAsErrors`.
2. Arregla primero los modelos (CS8618): cada `required` o `?` bien puesto elimina decenas de CS8602 aguas abajo porque el tipo ya dice la verdad.
3. Anota los `TryX` y los helpers con `[NotNullWhen]`, `[MaybeNullWhen]`, `[NotNull]`.
4. Lo que quede son decisiones reales de dominio; esas sí merecen leerse una a una.

Al final, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` para que no vuelvan.""",
            },
        ]
    },
    # 4) deadlock con .Result (el usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo una app WinForms (.NET 8) y al pulsar un botón se queda congelada para siempre. El código:

```csharp
private void btnLoad_Click(object sender, EventArgs e)
{
    var data = _service.GetDataAsync().Result;
    grid.DataSource = data;
}

// en otro proyecto (librería)
public async Task<List<Item>> GetDataAsync()
{
    var json = await _http.GetStringAsync("https://api.example.com/items");
    return JsonSerializer.Deserialize<List<Item>>(json)!;
}
```

No hay excepción ni nada, simplemente no vuelve. En una consola de prueba el mismo servicio funciona.""",
            },
            {
                "role": "assistant",
                "content": r"""Es un *deadlock* por `SynchronizationContext`, no un bug de red. Pasa esto, en orden:

1. `btnLoad_Click` corre en el hilo de UI y lo **bloquea** con `.Result`.
2. Dentro de `GetDataAsync`, el `await` captura el contexto actual (en WinForms, el hilo de UI) para reanudar ahí cuando llegue la respuesta.
3. La respuesta llega, la continuación se encola «para el hilo de UI»… que está bloqueado en el paso 1 esperando a que termine la continuación.

En consola no hay `SynchronizationContext`, las continuaciones corren en el *thread pool* y por eso ahí funciona.

**Arreglo correcto: no bloquees. Haz el handler asíncrono.** Es el único caso legítimo de `async void`, porque la firma del evento no admite `Task`:

```csharp
private async void btnLoad_Click(object sender, EventArgs e)
{
    btnLoad.Enabled = false;
    try
    {
        var data = await _service.GetDataAsync();
        grid.DataSource = data;          // seguimos en el hilo de UI: correcto
    }
    catch (HttpRequestException ex)
    {
        MessageBox.Show($"No se pudieron cargar los datos: {ex.Message}");
    }
    finally
    {
        btnLoad.Enabled = true;
    }
}
```

El `try/catch` es obligatorio: una excepción que escapa de un `async void` tumba el proceso. Deshabilitar el botón evita el doble clic mientras carga.

**Blindaje en la librería: `ConfigureAwait(false)`.** El código de `GetDataAsync` no toca UI, así que no necesita volver al contexto original:

```csharp
public async Task<List<Item>> GetDataAsync()
{
    var json = await _http.GetStringAsync("https://api.example.com/items").ConfigureAwait(false);
    return JsonSerializer.Deserialize<List<Item>>(json)
        ?? throw new InvalidOperationException("Empty response from items API");
}
```

Con esto, aunque otro consumidor vuelva a bloquear con `.Result`, no se queda colgado (la continuación corre en el pool). Pero no es un sustituto del primer arreglo: la UI seguiría congelada durante toda la petición.

Dos variantes que **no** arreglan nada:

- `.GetAwaiter().GetResult()`: mismo deadlock; solo cambia que la excepción no viene envuelta en `AggregateException`.
- `Task.Run(() => _service.GetDataAsync()).Result`: evita el deadlock porque el `await` interno ya no captura la UI, pero sigue bloqueando el hilo de UI. Es un parche que esconde el problema.

Nota para cuando lleves este servicio a un backend: ASP.NET Core no tiene `SynchronizationContext`, así que este deadlock concreto no aparece, pero bloquear con `.Result` bajo carga agota el *thread pool* y produce cuelgues igual de feos. La regla es la misma en todas partes: `async` de arriba abajo.""",
            },
        ]
    },
    # 5) LINQ: ejecución diferida y múltiple enumeración (bug del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""No entiendo este comportamiento. Proceso pedidos pendientes y al final quiero loguear cuántos procesé, pero el log siempre dice 0:

```csharp
IEnumerable<Order> pending = orders.Where(o => o.Status == OrderStatus.Pending);

_logger.LogInformation("Procesando {Count} pedidos", pending.Count());

foreach (var order in pending)
{
    await _processor.ProcessAsync(order);
    order.Status = OrderStatus.Done;
}

_logger.LogInformation("Procesados {Count} pedidos", pending.Count());  // siempre 0
```

El primer log sí dice el número correcto. `orders` es una `List<Order>`.""",
            },
            {
                "role": "assistant",
                "content": r"""`Where` no filtra nada en ese momento: construye una **consulta diferida** que se vuelve a ejecutar cada vez que la enumeras. Tu `pending` se enumera tres veces:

1. Primer `Count()`: evalúa el filtro → 3 pendientes (por ejemplo).
2. `foreach`: evalúa el filtro de nuevo, y cada pedido que procesas pasa a `Done`.
3. Segundo `Count()`: evalúa el filtro **otra vez**, y ya no queda ninguno con `Status == Pending` → 0.

El resultado es correcto para lo que la consulta dice («los que están pendientes ahora»); lo que no es correcto es la expectativa de que `pending` sea una lista fija.

**Arreglo:** materializa una vez y trabaja sobre la instantánea.

```csharp
List<Order> pending = orders
    .Where(o => o.Status == OrderStatus.Pending)
    .ToList();

_logger.LogInformation("Procesando {Count} pedidos", pending.Count);

foreach (var order in pending)
{
    await _processor.ProcessAsync(order);
    order.Status = OrderStatus.Done;
}

_logger.LogInformation("Procesados {Count} pedidos", pending.Count);  // mismo número
```

Fíjate en dos cambios además del `ToList()`:

- El tipo de la variable pasa de `IEnumerable<Order>` a `List<Order>`. `IEnumerable<T>` esconde si lo que tienes es una consulta o una colección; con `List<T>` cualquiera que lea el código sabe que es una instantánea y que recorrerla es gratis.
- `Count` (propiedad, O(1)) en vez de `Count()` (método, que en una consulta diferida recorre todo).

**Por qué importa más de lo que parece:** con `List<Order>` como origen, reenumerar solo cuesta CPU. Si `orders` fuera un `IQueryable` de EF Core, cada enumeración sería una consulta SQL distinta, y el segundo `Count()` iría a la base de datos, posiblemente con otra transacción. El mismo código tendría tres idas al servidor.

**Regla práctica:**

- Encadena operadores diferidos (`Where`, `Select`, `OrderBy`) mientras construyes la consulta.
- Materializa (`ToList`, `ToArray`, `ToDictionary`) en el momento en que la vas a recorrer **más de una vez**, a mutar lo que devuelve, o a devolverla fuera del método.
- Nunca devuelvas un `IEnumerable<T>` diferido que capture estado mutable (una conexión, un `DbContext`, una lista que otro va a cambiar).

El analizador `CA1851` («Possible multiple enumerations of IEnumerable collection») marca justo este patrón; actívalo en `.editorconfig` con `dotnet_diagnostic.CA1851.severity = warning` y te lo señalará en revisión en vez de en producción.""",
            },
        ]
    },
    # 6) IAsyncEnumerable (usuario en inglés pide respuesta en español)
    {
        "messages": [
            {"role": "user", "content": "I'm reading a huge table page by page from a REST API and want to expose it to callers as a stream instead of loading everything into a list. How do I do that with IAsyncEnumerable in C#, including cancellation? Please answer in Spanish."},
            {
                "role": "assistant",
                "content": r"""Usa un método `async IAsyncEnumerable<T>` con `yield return`: cada página se pide cuando el consumidor la necesita, y nada se acumula en memoria. La cancelación entra por un parámetro con `[EnumeratorCancellation]`.

```csharp
using System.Net.Http.Json;
using System.Runtime.CompilerServices;

public sealed class ItemsClient(HttpClient http)
{
    private const int PageSize = 500;

    public async IAsyncEnumerable<Item> GetAllAsync(
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        string? cursor = null;
        do
        {
            var url = $"items?limit={PageSize}" + (cursor is null ? "" : $"&cursor={Uri.EscapeDataString(cursor)}");
            var page = await http.GetFromJsonAsync<Page<Item>>(url, ct).ConfigureAwait(false)
                       ?? throw new InvalidOperationException("Empty page from items API");

            foreach (var item in page.Items)
                yield return item;

            cursor = page.NextCursor;
        } while (cursor is not null);
    }
}

public sealed record Page<T>(IReadOnlyList<T> Items, string? NextCursor);
```

Consumo:

```csharp
await foreach (var item in client.GetAllAsync(cts.Token))
{
    Console.WriteLine(item.Id);
}
```

Puntos que importan:

- **`[EnumeratorCancellation]`** hace que el token que pasas por `WithCancellation(token)` al consumir se combine con el del parámetro. Sin el atributo, `WithCancellation` no llega al cuerpo del método. Con el atributo puedes pasar el token por cualquiera de las dos vías; si pasas uno en cada sitio, el compilador los enlaza.
- **Es diferido**, como `IEnumerable<T>`: llamar a `GetAllAsync()` no hace ninguna petición. La primera página se pide en el primer `MoveNextAsync`. Si enumeras dos veces, pides todo dos veces.
- **`ConfigureAwait(false)`** en el `await` interno porque esto es código de librería; el `await foreach` del consumidor decide por su cuenta si vuelve a su contexto.
- `GetFromJsonAsync` ya lanza `HttpRequestException` si el estado no es 2xx; no hace falta comprobarlo a mano.

**Transformar el flujo.** `System.Linq` no trae operadores para `IAsyncEnumerable<T>`; el paquete `System.Linq.Async` sí (`Where`, `Select`, `Take`, `ToListAsync`):

```csharp
var firstActive = await client.GetAllAsync(ct)
    .Where(i => i.IsActive)
    .Take(10)
    .ToListAsync(ct);
```

**Devolverlo desde una API.** En ASP.NET Core, un endpoint que devuelve `IAsyncEnumerable<Item>` se serializa en *streaming*: el cliente empieza a recibir el array JSON antes de que termine la última página.

```csharp
app.MapGet("/items", (ItemsClient client, CancellationToken ct) => client.GetAllAsync(ct));
```

Verificación rápida de que de verdad es perezoso: pon un `Console.WriteLine` antes de la petición HTTP y enumera solo con `.Take(1)`; debe imprimirse una vez, no una por página.""",
            },
        ]
    },
    # 7) Span<T> para parsear sin asignaciones (avanzado)
    {
        "messages": [
            {"role": "user", "content": "Parseo millones de líneas tipo `2024-05-01T10:00:00Z;sensor-12;23.5` y el profiler dice que `string.Split` es el 40 % de las asignaciones. ¿Cómo lo hago con Span<T>? ¿Y qué limitaciones tiene?"},
            {
                "role": "assistant",
                "content": r"""Trocea la línea como `ReadOnlySpan<char>` y parsea cada trozo directamente desde el span. Las APIs numéricas y de fecha aceptan spans desde .NET Core 2.1, así que el único string por línea será la línea misma.

```csharp
using System.Globalization;

public readonly record struct Reading(DateTimeOffset At, int SensorId, double Value);

public static class ReadingParser
{
    private const string SensorPrefix = "sensor-";

    public static bool TryParse(ReadOnlySpan<char> line, out Reading reading)
    {
        reading = default;

        // .NET 8: rellena rangos sin asignar; devuelve cuántos campos encontró
        Span<Range> fields = stackalloc Range[4];
        if (line.Split(fields, ';', StringSplitOptions.TrimEntries) != 3)
            return false;

        var timestamp = line[fields[0]];
        var sensor = line[fields[1]];
        var value = line[fields[2]];

        if (!DateTimeOffset.TryParse(timestamp, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var at))
            return false;

        if (!sensor.StartsWith(SensorPrefix, StringComparison.Ordinal)
            || !int.TryParse(sensor[SensorPrefix.Length..], NumberStyles.None, CultureInfo.InvariantCulture, out var id))
            return false;

        if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var v))
            return false;

        reading = new Reading(at, id, v);
        return true;
    }
}
```

Uso:

```csharp
var ok = 0;
foreach (var line in File.ReadLines(path))
{
    if (ReadingParser.TryParse(line, out var r)) ok++;
}
```

Por qué está así:

- **`Span<Range>` con `stackalloc`**: `MemoryExtensions.Split` (.NET 8) escribe los rangos de cada campo en ese buffer y no asigna nada. Pido 4 rangos para detectar líneas con campos de más: si hubiera 4 campos devolvería 4 y rechazo la línea. En .NET 9 también existe `line.Split(';')` que devuelve un enumerador de spans para `foreach`.
- **`TryParse` en vez de lanzar**: con millones de líneas, una excepción por línea mala cuesta microsegundos cada una y destroza el rendimiento. Devolver `false` deja que el llamador cuente y siga.
- **`InvariantCulture` explícita**: sin ella, `23.5` se parsea como `235` en una máquina con coma decimal.
- **`readonly record struct`**: 24 bytes, sin asignación en el heap, igualdad por valor gratis.
- **El id como `int`**: parsear `sensor-12` a `12` evita un string por línea. Si los ids no fueran numéricos, el siguiente paso sería un diccionario de internado; en .NET 9 `Dictionary<string, T>.GetAlternateLookup<ReadOnlySpan<char>>()` permite buscar con un span sin crear el string.

**Limitaciones de `Span<T>` que te vas a encontrar:**

1. Es un `ref struct`: vive en la pila. No puede ser campo de una clase, elemento de un array ni argumento genérico (salvo .NET 9 con `allows ref struct`).
2. No cruza un `await` ni un `yield return`. Si el parseo está en un método `async`, recibe `ReadOnlyMemory<char>` y haz `memory.Span` dentro de un método síncrono, como el `TryParse` de arriba.
3. No se captura en lambdas ni en LINQ. El código con spans es imperativo por diseño.

**Lo que esta versión no elimina:** `File.ReadLines` sigue creando un string por línea. Suele ser aceptable (una asignación corta en vez de cuatro). Si el profiler todavía se queja, el siguiente nivel es leer el archivo por bloques en un buffer de `ArrayPool<byte>` y buscar los saltos de línea con `IndexOf((byte)'\n')`, parseando UTF-8 directamente con `Utf8Parser`; es más código y solo compensa si el archivo es realmente grande.

Mide antes y después con BenchmarkDotNet y `[MemoryDiagnoser]`: la columna *Allocated* del método `TryParse` debe quedar en 0 B.""",
            },
        ]
    },
    # 8) struct vs class
    {
        "messages": [
            {"role": "user", "content": "¿Cuándo debo usar struct en vez de class? Tengo un tipo Money con decimal Amount y string Currency y no sé cuál elegir."},
            {
                "role": "assistant",
                "content": r"""Para `Money`, un `readonly record struct`. Es un valor pequeño, inmutable, sin identidad, y se compara por contenido: el caso de libro para un struct.

```csharp
public readonly record struct Money(decimal Amount, string Currency)
{
    public static Money operator +(Money a, Money b)
    {
        if (a.Currency != b.Currency)
            throw new InvalidOperationException($"Cannot add {a.Currency} and {b.Currency}");
        return a with { Amount = a.Amount + b.Amount };
    }

    public override string ToString() => $"{Amount:0.00} {Currency}";
}
```

Criterios para decidir, en orden de peso:

1. **Semántica.** Un struct se copia al asignarlo o pasarlo; una clase se comparte por referencia. Si dos variables que apuntan «al mismo» objeto deben ver los cambios de la otra, necesitas una clase. `Money` no tiene identidad: 10 EUR son 10 EUR.
2. **Tamaño.** La guía oficial dice ≤ 16 bytes para structs que se copian mucho. `Money` son 24 (16 del `decimal` + 8 de la referencia al string) y sigue estando bien; el coste de copiar 24 bytes es menor que el de asignar en el heap y que el GC lo rastree. A partir de ~64 bytes, pásalo con `in` o usa clase.
3. **Inmutabilidad.** Un struct mutable es una fuente de bugs: modificas una copia y el original no cambia. `readonly` en el struct lo garantiza y además evita las **copias defensivas** que el compilador inserta cuando llamas a un método de un struct no-readonly almacenado en un campo `readonly`.
4. **Boxing.** Cada vez que un struct se convierte a `object` o a una interfaz, se asigna una caja en el heap. Si vas a meter muchos `Money` en una `List<object>` o a pasarlos por `IComparable` sin genéricos, pierdes la ventaja.
5. **`default`.** `default(Money)` existe siempre y tiene `Currency == null`. Un struct no puede impedirlo; defiende el invariante en el constructor y asume que `default` puede aparecer (arrays recién creados, `Dictionary.TryGetValue` fallido). Si el valor por defecto no tiene sentido y no puedes vivir con él, eso apunta a clase.

Lo que `record struct` añade sobre `struct`: igualdad y `GetHashCode` generados (y mucho más rápidos que los de `ValueType`, que usan reflexión), `ToString`, deconstrucción y `with`. Lo que `readonly` añade: todas las propiedades son `init` y los métodos no pueden mutar `this`.

Comprobación de que la semántica es la que quieres:

```csharp
var price = new Money(10m, "EUR");
var copy = price;
copy = copy with { Amount = 20m };
Console.WriteLine(price);                       // 10.00 EUR  (la copia no afectó al original)
Console.WriteLine(price == new Money(10m, "EUR")); // True
```

Si mañana `Money` necesita historial de conversiones, listas de impuestos o referencias a otras entidades, deja de ser un valor pequeño y pasa a `record class` sin cambiar a quien lo usa, salvo el `default`.""",
            },
        ]
    },
    # 9) genéricos con restricciones y generic math
    {
        "messages": [
            {"role": "user", "content": "Quiero una función `Sum` genérica que sirva para int, double y decimal sin escribir tres sobrecargas. Probé `where T : struct` pero no me deja hacer `a + b`."},
            {
                "role": "assistant",
                "content": r"""`where T : struct` solo dice «es un tipo de valor»; no promete que exista `+`. Lo que necesitas es la restricción a `INumber<T>` (.NET 7+), que expone los operadores como **miembros estáticos abstractos** de la interfaz.

```csharp
using System.Numerics;

public static class Stats
{
    public static T Sum<T>(IEnumerable<T> values) where T : INumber<T>
    {
        var total = T.Zero;
        foreach (var v in values)
            total += v;
        return total;
    }

    public static T Average<T>(IReadOnlyCollection<T> values) where T : INumber<T>
    {
        if (values.Count == 0)
            throw new ArgumentException("Cannot average an empty collection", nameof(values));
        return Sum(values) / T.CreateChecked(values.Count);
    }
}
```

- `T.Zero` y `+=` existen porque `INumber<T>` hereda de `IAdditionOperators<T,T,T>`, `IAdditiveIdentity<T,T>` y compañía.
- `T.CreateChecked(int)` convierte un `int` al tipo `T` lanzando `OverflowException` si no cabe (para `byte`, por ejemplo). Hay también `CreateSaturating` y `CreateTruncating`.
- Para `int` la suma desborda en silencio igual que con `+` normal; si quieres que lance, usa `checked(total + v)` o `T.CreateChecked`.

Uso y prueba:

```csharp
Console.WriteLine(Stats.Sum(new[] { 1, 2, 3 }));            // 6
Console.WriteLine(Stats.Sum(new[] { 1.5, 2.5 }));           // 4
Console.WriteLine(Stats.Average(new[] { 1m, 2m, 4m }));     // 2.3333333333333333333333333333
```

Las restricciones que tienes disponibles, para elegir siempre la más estrecha que cumpla el trabajo:

| Restricción | Garantiza |
|---|---|
| `class` / `struct` | Tipo de referencia / de valor |
| `notnull` | No es un tipo anulable (solo afecta al análisis de nullability) |
| `unmanaged` | Struct sin referencias; permite `sizeof(T)` y punteros |
| `new()` | Constructor público sin parámetros |
| `IAlgo<T>` / `BaseClass` | Miembros de esa interfaz o clase, incluidos los estáticos abstractos |
| `where T : U` | Relación entre dos parámetros genéricos |

Si solo necesitas comparar (ordenar, mínimo), `IComparable<T>` o `IComparisonOperators<T,T,bool>` bastan y admiten más tipos (`string`, `DateTime`). Si necesitas aritmética, `INumber<T>`. Si necesitas solo `+`, `IAdditionOperators<T,T,T>` junto con `IAdditiveIdentity<T,T>` para el `Zero`: cuanto más estrecha la restricción, más tipos la cumplen.

Un detalle: las interfaces con miembros estáticos abstractos no se pueden usar como tipo de variable (`INumber<T> x` no compila con sentido), solo como restricción. Es por diseño: el operador se resuelve en tiempo de compilación según `T`, sin despacho virtual ni boxing.""",
            },
        ]
    },
    # 10) excepciones: throw vs throw ex, filtros (system variante rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo, sin perder precisión técnica."},
            {"role": "user", "content": "¿Qué diferencia hay entre `throw;` y `throw ex;`? Y vi un `catch (Exception e) when (...)` en el código de un compañero, ¿qué hace ese when?"},
            {
                "role": "assistant",
                "content": r"""`throw;` relanza la excepción **conservando el stack trace original**. `throw ex;` la lanza de nuevo desde esa línea, así que el stack trace pasa a apuntar al `catch` y perdés dónde se produjo de verdad. Casi nunca querés `throw ex;`.

```csharp
try
{
    await repo.SaveAsync(order);
}
catch (DbUpdateException)
{
    _logger.LogError("Fallo al guardar el pedido {Id}", order.Id);
    throw;              // el stack trace sigue señalando a SaveAsync
}
```

Si lo que querés es envolver con más contexto, creá una excepción nueva **con la original como inner**:

```csharp
catch (DbUpdateException ex)
{
    throw new OrderPersistenceException($"No se pudo guardar el pedido {order.Id}", ex);
}
```

El `when` es un **filtro de excepción**: decide si ese `catch` atrapa la excepción *antes* de desenrollar la pila. Si el filtro da `false`, es como si el `catch` no existiera y la excepción sigue subiendo con su stack intacto.

```csharp
try
{
    var response = await http.GetAsync(url);
    response.EnsureSuccessStatusCode();
}
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
{
    return null;        // 404 es un caso normal acá
}
catch (HttpRequestException ex) when (ex.StatusCode is >= HttpStatusCode.InternalServerError)
{
    _logger.LogWarning(ex, "Error del servidor, reintentando");
    throw;
}
```

Tres ventajas frente a un `if` adentro del `catch`:

1. **No desenrolla la pila si no aplica.** Con `catch { if (!cond) throw; }` ya entraste al catch, ejecutaste código y relanzaste; con `when`, la excepción no te pasa por encima. Para el depurador y para el *dump* de un crash es la diferencia entre ver el punto real del error o el `catch`.
2. **Orden claro.** Podés tener varios `catch` del mismo tipo con filtros distintos; se prueban de arriba hacia abajo.
3. **Logueo sin atrapar.** Un truco conocido: `catch (Exception ex) when (Log(ex))` donde `Log` devuelve `false`. Registra y deja pasar, sin tocar el flujo.

Cuidado con esto último: el filtro corre en un contexto raro (la pila todavía no se desenrolló, los `finally` intermedios no se ejecutaron). Mantenelo simple y sin efectos secundarios más allá de loguear; si el filtro lanza, esa excepción se traga y el filtro cuenta como `false`.

Regla práctica: `throw;` para relanzar, `throw new X(msg, ex)` para envolver, `when` para atrapar solo lo que sabés manejar. Si en un `catch` no hacés nada útil con la excepción, mejor no la atrapes.""",
            },
        ]
    },
    # 11) IDisposable -> HttpClient (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Cómo implemento IDisposable bien en una clase que tiene un FileStream y un HttpClient? He visto el patrón con el finalizador y `Dispose(bool)` y me parece muchísimo código."},
            {
                "role": "assistant",
                "content": r"""Ese patrón completo (finalizador + `Dispose(bool)`) es para clases que poseen recursos **no gestionados** directamente (handles nativos). Si solo tienes objetos .NET que ya son `IDisposable`, la versión corta basta:

```csharp
public sealed class ReportExporter : IDisposable, IAsyncDisposable
{
    private readonly FileStream _output;
    private bool _disposed;

    public ReportExporter(string path)
    {
        _output = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None, 4096, useAsync: true);
    }

    public async Task WriteAsync(ReadOnlyMemory<byte> chunk, CancellationToken ct = default)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        await _output.WriteAsync(chunk, ct).ConfigureAwait(false);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _output.Dispose();
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed) return;
        _disposed = true;
        await _output.DisposeAsync().ConfigureAwait(false);
    }
}
```

Las decisiones:

- **`sealed`**: sin herencia no hace falta `Dispose(bool)` virtual ni `GC.SuppressFinalize` (no hay finalizador). El patrón largo existe para que las subclases puedan añadir su limpieza.
- **Idempotente**: llamar `Dispose` dos veces no debe fallar. Es parte del contrato de `IDisposable`.
- **`IAsyncDisposable`** porque `FileStream` tiene `DisposeAsync` y vaciar el buffer puede bloquear. El consumidor usa `await using`.
- **`ObjectDisposedException.ThrowIf`** (.NET 7+) para fallar con un mensaje claro si alguien usa el objeto después de cerrarlo.

Al consumir, las *using declarations* (C# 8) evitan la indentación extra:

```csharp
await using var exporter = new ReportExporter("informe.bin");
await exporter.WriteAsync(data);
// se cierra al salir del ámbito, también si hay excepción
```

Sobre el `HttpClient`: **no lo metas en esta clase ni lo deseches con ella.** Aunque implementa `IDisposable`, está pensado para vivir mucho tiempo y reutilizarse. Crear y desechar uno por operación agota los sockets (quedan en `TIME_WAIT`) y es el error más documentado de .NET. Recíbelo desde fuera y no lo toques en `Dispose`.""",
            },
            {"role": "user", "content": "Pero entonces si HttpClient no se debe desechar, ¿lo hago static y listo?"},
            {
                "role": "assistant",
                "content": r"""`static` resuelve el agotamiento de sockets pero crea el problema contrario: un `HttpClient` eterno con el handler por defecto **no respeta los cambios de DNS**, porque mantiene las conexiones abiertas indefinidamente. Si el servicio al que llamas cambia de IP (despliegues, failover), tu cliente sigue hablando con la vieja hasta que la conexión muera.

Tienes dos soluciones correctas.

**1. Si no usas inyección de dependencias** (consola, script): un cliente compartido con `SocketsHttpHandler` y vida limitada por conexión.

```csharp
public static class Http
{
    public static readonly HttpClient Client = new(new SocketsHttpHandler
    {
        PooledConnectionLifetime = TimeSpan.FromMinutes(5),   // recicla conexiones: DNS al día
    })
    {
        Timeout = TimeSpan.FromSeconds(30),
    };
}
```

`PooledConnectionLifetime` cierra cada conexión del pool pasados 5 minutos y abre una nueva, que vuelve a resolver DNS. Las peticiones en curso no se cortan.

**2. Si usas el host genérico o ASP.NET Core** (lo normal): `IHttpClientFactory` con un cliente tipado. La fábrica gestiona el ciclo de vida de los handlers por ti (los rota cada 2 minutos por defecto) y te deja configurar cada cliente por nombre.

```csharp
// Program.cs
builder.Services.AddHttpClient<ItemsClient>(client =>
{
    client.BaseAddress = new Uri("https://api.example.com/");
    client.Timeout = TimeSpan.FromSeconds(10);
});

// El cliente tipado recibe un HttpClient ya configurado
public sealed class ItemsClient(HttpClient http)
{
    public Task<Item?> GetAsync(int id, CancellationToken ct) =>
        http.GetFromJsonAsync<Item>($"items/{id}", ct);
}

// Y se inyecta donde haga falta
app.MapGet("/items/{id:int}", (int id, ItemsClient client, CancellationToken ct) => client.GetAsync(id, ct));
```

El `HttpClient` que recibe `ItemsClient` es de usar y tirar: la fábrica lo crea por resolución y es el *handler* subyacente el que se comparte y se recicla. Por eso aquí sí da igual no desecharlo.

Con el paquete `Microsoft.Extensions.Http.Resilience` añades reintentos, *circuit breaker* y timeouts por cliente con `.AddStandardResilienceHandler()`, sin tocar el código del cliente.

Resumen: `static` + `PooledConnectionLifetime` para programas pequeños; `IHttpClientFactory` en cuanto tengas un contenedor de DI.""",
            },
        ]
    },
    # 12) DI lifetimes y captive dependency (multiturno, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Al arrancar mi API en .NET 8 me salta: `System.InvalidOperationException: Cannot consume scoped service 'AppDbContext' from singleton 'CacheWarmer'`. CacheWarmer es un BackgroundService que precarga una tabla en memoria. ¿Lo cambio a singleton y listo?"},
            {
                "role": "assistant",
                "content": r"""No. El error te está salvando de un bug peor. `AppDbContext` es *scoped* (una instancia por petición, no es segura para hilos y acumula entidades rastreadas). Si lo conviertes en singleton, todas las peticiones compartirían el mismo contexto: errores de concurrencia (`A second operation was started on this context instance`) y memoria que nunca se libera.

Los tres tiempos de vida:

| Lifetime | Una instancia por | Típico |
|---|---|---|
| `Transient` | cada resolución | servicios sin estado y baratos |
| `Scoped` | *scope* (en ASP.NET Core, por petición HTTP) | `DbContext`, unidad de trabajo, usuario actual |
| `Singleton` | toda la vida de la aplicación | caché, configuración, clientes HTTP tipados por fábrica |

La regla que rompe tu `CacheWarmer`: **un servicio no puede depender de otro con vida más corta**, porque lo «captura» y lo mantiene vivo para siempre (*captive dependency*). El contenedor de Microsoft lo detecta solo en desarrollo (`ValidateScopes`, activado por defecto en `Development`); en producción fallaría en silencio.

Un `BackgroundService` es singleton por naturaleza. La solución es que **cree su propio scope** cuando necesite servicios scoped:

```csharp
public sealed class CacheWarmer(
    IServiceScopeFactory scopeFactory,
    IMemoryCache cache,
    ILogger<CacheWarmer> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        var countries = await db.Countries.AsNoTracking().ToListAsync(stoppingToken);
        cache.Set("countries", countries);
        logger.LogInformation("Precargados {Count} países", countries.Count);
    }
}
```

`IServiceScopeFactory` es singleton, así que inyectarlo es legal. El `using` cierra el scope y con él el `DbContext`. `AsNoTracking` porque solo lees: el contexto no necesita vigilar esas entidades.

Si el servicio hiciera trabajo periódico, el scope debe crearse **dentro** de cada iteración, no una vez al principio: un `DbContext` que vive días acumula rastreo y conexiones viejas.""",
            },
            {"role": "user", "content": "Lo hice y funciona. Pero ahora otro BackgroundService que procesa una cola de 200 000 filas con el mismo patrón hace que la memoria suba sin parar hasta que lo mato. Usa un solo scope para todo el lote."},
            {
                "role": "assistant",
                "content": r"""La memoria sube porque un `DbContext` **rastrea** cada entidad que pasa por él: guarda la instancia y una copia de sus valores originales para detectar cambios. Con un único scope para 200 000 filas tienes 200 000 entidades (y sus instantáneas) vivas hasta que el scope muere. Y no solo es memoria: cada `SaveChangesAsync` ejecuta `DetectChanges` sobre todo lo rastreado, así que cada lote es más lento que el anterior.

El arreglo es acotar la vida del contexto al **tamaño del lote**:

```csharp
public sealed class QueueProcessor(
    IServiceScopeFactory scopeFactory,
    ILogger<QueueProcessor> logger) : BackgroundService
{
    private const int BatchSize = 1000;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        long lastId = 0;
        while (!stoppingToken.IsCancellationRequested)
        {
            using var scope = scopeFactory.CreateScope();          // un contexto nuevo por lote
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

            var batch = await db.QueueItems
                .Where(q => q.Id > lastId && q.ProcessedAt == null)
                .OrderBy(q => q.Id)
                .Take(BatchSize)
                .ToListAsync(stoppingToken);

            if (batch.Count == 0)
            {
                await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
                lastId = 0;                                        // vuelve a empezar: pueden llegar ids nuevos
                continue;
            }

            foreach (var item in batch)
            {
                await ProcessAsync(item, stoppingToken);
                item.ProcessedAt = DateTimeOffset.UtcNow;
            }

            await db.SaveChangesAsync(stoppingToken);              // una transacción por lote
            lastId = batch[^1].Id;
            logger.LogInformation("Lote hasta Id {Id} procesado", lastId);
        }
    }
}
```

Qué cambia y por qué:

- **Scope por lote.** Al terminar el `using`, el `DbContext` y su *change tracker* se liberan. La memoria describe un serrucho de 1000 filas, no una rampa de 200 000.
- **Paginación por keyset (`Id > lastId`)**, no `Skip`. `Skip(n)` recorre y descarta n filas en cada lote; con `Id > lastId` cada consulta usa el índice y cuesta lo mismo sea el lote 1 o el 200.
- **Commit por lote.** Si el proceso muere a mitad, lo ya guardado tiene `ProcessedAt`; al reiniciar continúa donde iba. Con un solo `SaveChanges` al final, un fallo en la fila 199 999 perdería todo.
- **`ProcessedAt == null` en el filtro** hace el bucle idempotente: reprocesar un lote no repite trabajo ya marcado.

Dos alternativas si no puedes cambiar la estructura:

- Mantener un contexto y llamar `db.ChangeTracker.Clear()` después de cada `SaveChangesAsync`. Libera el rastreo, pero el contexto sigue vivo con su conexión y es fácil olvidar la llamada.
- Si la actualización es simple (marcar filas), `ExecuteUpdateAsync` (EF Core 7+) la hace en SQL sin cargar entidades:

```csharp
await db.QueueItems
    .Where(q => ids.Contains(q.Id))
    .ExecuteUpdateAsync(s => s.SetProperty(q => q.ProcessedAt, DateTimeOffset.UtcNow), stoppingToken);
```

Verifica con `dotnet-counters monitor --process-id <pid> --counters System.Runtime`: `gc-heap-size` debe quedar plano con pequeñas oscilaciones. Si sigue subiendo, el que retiene es `ProcessAsync` (una lista estática, un caché sin límite), no EF.""",
            },
        ]
    },
    # 13) Options pattern con validación (system variante)
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto .NET. Responde de forma directa, con código completo y las razones de cada decisión."},
            {"role": "user", "content": "¿Cómo leo una sección de appsettings.json tipada y que la app falle al arrancar si falta un campo obligatorio? Ahora hago `builder.Configuration[\"Smtp:Host\"]` por todos lados y a veces es null en producción."},
            {
                "role": "assistant",
                "content": r"""Usa el patrón *Options* con validación al arranque. La configuración se enlaza a una clase, se valida una vez, y si falta algo el host no arranca y te dice exactamente qué.

```jsonc
// appsettings.json
{
  "Smtp": {
    "Host": "smtp.example.com",
    "Port": 587,
    "From": "noreply@example.com",
    "UseTls": true
  }
}
```

```csharp
using System.ComponentModel.DataAnnotations;

public sealed class SmtpOptions
{
    public const string SectionName = "Smtp";

    [Required] public required string Host { get; init; }
    [Range(1, 65535)] public int Port { get; init; } = 587;
    [Required, EmailAddress] public required string From { get; init; }
    public bool UseTls { get; init; } = true;
}
```

```csharp
// Program.cs
builder.Services
    .AddOptions<SmtpOptions>()
    .BindConfiguration(SmtpOptions.SectionName)
    .ValidateDataAnnotations()
    .Validate(o => !o.UseTls || o.Port != 25, "Port 25 cannot be used with TLS")
    .ValidateOnStart();
```

Consumo:

```csharp
public sealed class MailSender(IOptions<SmtpOptions> options)
{
    private readonly SmtpOptions _smtp = options.Value;
}
```

Por qué cada pieza:

- **`ValidateOnStart()`** mueve el fallo del primer uso al arranque. Sin él, la validación ocurre la primera vez que alguien accede a `.Value`, que en producción puede ser horas después del despliegue. El error es una `OptionsValidationException` con el nombre del campo.
- **`[Required]` + `required`**: `required` protege la construcción en código; el atributo protege el *binding* desde configuración (el binder usa reflexión y no respeta `required`).
- **`Validate(...)`** para reglas que cruzan campos. Las anotaciones validan campos sueltos.
- **Valores por defecto en la clase**, no esparcidos en lecturas con `??`.

Qué interfaz inyectar:

| Interfaz | Cuándo se lee la config | Úsala en |
|---|---|---|
| `IOptions<T>` | Una vez, al primer acceso; nunca cambia | Singletons; lo normal |
| `IOptionsSnapshot<T>` | Por scope (por petición) | Servicios scoped que deben ver cambios tras editar el archivo |
| `IOptionsMonitor<T>` | Siempre actual, con `OnChange` | Singletons que necesitan recarga en caliente |

Para sobrescribir en producción no editas el JSON: usas variables de entorno con doble guion bajo como separador, `Smtp__Host=smtp.prod.internal`, o `dotnet user-secrets` en desarrollo. Mismo nombre de sección, misma clase.

Prueba de que la validación funciona, con `WebApplicationFactory` y sin el campo `Host`:

```csharp
[Fact]
public void Host_fails_to_start_when_smtp_host_is_missing()
{
    var factory = new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
        b.ConfigureAppConfiguration((_, cfg) =>
            cfg.AddInMemoryCollection(new Dictionary<string, string?> { ["Smtp:Host"] = null })));

    var ex = Assert.Throws<OptionsValidationException>(() => factory.CreateClient());
    Assert.Contains("Host", ex.Message);
}
```

Con esto desaparecen los `Configuration["Smtp:Host"]` sueltos: hay un único sitio que sabe cómo se llama la sección y qué forma tiene.""",
            },
        ]
    },
    # 14) System.Text.Json (multiturno)
    {
        "messages": [
            {"role": "user", "content": "System.Text.Json me serializa las propiedades en PascalCase y los enums como números. ¿Cómo lo configuro una sola vez para toda la app? Es una API en .NET 8."},
            {
                "role": "assistant",
                "content": r"""En ASP.NET Core la configuración global va en `ConfigureHttpJsonOptions` (minimal APIs) o en `AddControllers().AddJsonOptions` (controladores). Es el mismo `JsonSerializerOptions` por debajo.

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

builder.Services.ConfigureHttpJsonOptions(o =>
{
    o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    o.SerializerOptions.DictionaryKeyPolicy = JsonNamingPolicy.CamelCase;
    o.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    o.SerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
});

// Si usas controladores:
builder.Services.AddControllers().AddJsonOptions(o =>
{
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
});
```

Dos aclaraciones:

- ASP.NET Core ya usa `JsonSerializerDefaults.Web` (camelCase y lectura sin distinguir mayúsculas), así que en la API los nombres **ya** deberían salir en camelCase. Si te salen en PascalCase, lo más probable es que estés llamando a `JsonSerializer.Serialize(obj)` a mano en algún sitio, y ahí no aplica la configuración del host.
- Para esos usos manuales, crea **una sola instancia** de `JsonSerializerOptions` y reutilízala. Cada instancia nueva recalcula y cachea los metadatos de los tipos; crear una por llamada es el error de rendimiento más común con esta librería:

```csharp
public static class Json
{
    public static readonly JsonSerializerOptions Default = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) },
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };
}

var text = JsonSerializer.Serialize(order, Json.Default);
```

Para un nombre concreto que no siga la política, `[JsonPropertyName("order_id")]` en la propiedad. Para un enum concreto, `[JsonConverter(typeof(JsonStringEnumConverter))]` sobre el tipo del enum.

Comprobación: `JsonSerializer.Serialize(new { Status = OrderStatus.Pending }, Json.Default)` debe devolver `{"status":"pending"}`.""",
            },
            {"role": "user", "content": "¿Y para deserializar una lista de `Shape` que puede ser Circle o Rectangle? Ahora me da `JsonException: Deserialization of types without a parameterless constructor` o directamente me crea Shapes vacíos."},
            {
                "role": "assistant",
                "content": r'''Necesitas **polimorfismo con discriminador** (.NET 7+). Declaras en la clase base qué subtipos existen y con qué etiqueta; el serializador escribe y lee un campo extra (`$type` por defecto) para saber qué instanciar.

```csharp
using System.Text.Json.Serialization;

[JsonPolymorphic(TypeDiscriminatorPropertyName = "kind")]
[JsonDerivedType(typeof(Circle), "circle")]
[JsonDerivedType(typeof(Rectangle), "rectangle")]
public abstract record Shape;

public sealed record Circle(double Radius) : Shape;
public sealed record Rectangle(double Width, double Height) : Shape;
```

```csharp
var json = """
[
  { "kind": "circle", "radius": 2 },
  { "kind": "rectangle", "width": 3, "height": 4 }
]
""";

var shapes = JsonSerializer.Deserialize<List<Shape>>(json, Json.Default)!;
Console.WriteLine(shapes[0]);  // Circle { Radius = 2 }
```

Lo que tienes que saber:

- **El discriminador debe ser la primera propiedad del objeto** al leer. Si el JSON lo trae al final, lanza `JsonException` diciendo que el discriminador «must be the first property». Al escribir, System.Text.Json lo coloca primero por ti. Si el productor del JSON no controla el orden, tendrás que escribir un `JsonConverter<Shape>` propio que lea a `JsonDocument` y decida.
- **Sin discriminador no hay polimorfismo.** Si el JSON no trae `kind`, por defecto falla; puedes permitir que caiga al tipo base con `UnknownDerivedTypeHandling = JsonUnknownDerivedTypeHandling.FallBackToBaseType`, pero con una base `abstract` eso tampoco es posible. En tu caso el `abstract` es correcto: una `Shape` «a secas» no significa nada.
- Los records posicionales se deserializan por su constructor, así que no hace falta constructor sin parámetros. El error que viste aparecía porque `Shape` no tenía forma de saber qué construir.
- Serializar también escribe `kind`, así que el *round-trip* es simétrico.

Si en el proyecto usas el generador de código fuente de JSON (`JsonSerializerContext`), el polimorfismo funciona igual; solo registra el tipo base:

```csharp
[JsonSerializable(typeof(List<Shape>))]
internal partial class AppJsonContext : JsonSerializerContext;
```

Prueba de ida y vuelta:

```csharp
var original = new List<Shape> { new Circle(1), new Rectangle(2, 3) };
var text = JsonSerializer.Serialize(original, Json.Default);
Assert.Contains("\"kind\":\"circle\"", text);
Assert.Equal(original, JsonSerializer.Deserialize<List<Shape>>(text, Json.Default));
```

La última aserción funciona porque los records comparan por valor.''',
            },
        ]
    },
    # 15) xUnit: test async mal escrito (el usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Mis tests de xUnit pasan siempre, incluso cuando rompo el código a propósito. Esto es uno:

```csharp
public class OrderServiceTests
{
    [Fact]
    public async void Rejects_negative_quantity()
    {
        var service = new OrderService();
        Assert.ThrowsAsync<ArgumentException>(() => service.AddAsync(new Order(-1)));
    }

    [Fact]
    public async Task Calculates_total()
    {
        var service = new OrderService();
        var total = service.TotalAsync(new Order(2));
        Assert.Equal(20m, total.Result);
    }
}
```

¿Qué estoy haciendo mal?""",
            },
            {
                "role": "assistant",
                "content": r"""El primer test no comprueba nada y el segundo funciona por accidente.

**Test 1: la aserción nunca se espera.** `Assert.ThrowsAsync` devuelve una `Task`; la comprobación ocurre cuando esa `Task` completa. Como no la esperas, el método termina antes, xUnit lo marca como pasado y el resultado real se pierde. El compilador te lo decía: `warning CS4014: Because this call is not awaited, execution of the current method continues before the call is completed`. Y `async void` lo empeora: una excepción que escape no se puede asociar al test (xUnit v3 ya no admite tests `async void`).

**Test 2: `.Result` en vez de `await`.** No bloquea para siempre, pero si `TotalAsync` lanza, la excepción llega envuelta en `AggregateException` y el mensaje del test es peor. Además el método es `async Task` sin ningún `await` (`warning CS1998`), señal de que algo falta.

Versión correcta, con los casos de cantidad como `Theory`:

```csharp
public class OrderServiceTests
{
    private readonly OrderService _service = new();

    [Theory]
    [InlineData(-1)]
    [InlineData(0)]
    public async Task Rejects_non_positive_quantity(int quantity)
    {
        var ex = await Assert.ThrowsAsync<ArgumentException>(() => _service.AddAsync(new Order(quantity)));
        Assert.Equal("quantity", ex.ParamName);
    }

    [Theory]
    [InlineData(1, 10)]
    [InlineData(2, 20)]
    [InlineData(10, 90)]   // descuento por volumen
    public async Task Calculates_total(int quantity, decimal expected)
    {
        var total = await _service.TotalAsync(new Order(quantity));
        Assert.Equal(expected, total);
    }
}
```

Detalles:

- xUnit crea **una instancia de la clase por test**, así que el campo `_service` se inicializa limpio cada vez. Si construirlo fuera caro (una base de datos, un contenedor), eso va en una clase que implemente `IAsyncLifetime` y se comparte con `IClassFixture<T>`.
- Comprobar `ParamName` convierte «lanza algo» en «lanza por la razón correcta».
- `Theory` + `InlineData` documenta los límites (0 también se rechaza) sin duplicar métodos.

Para que esto no vuelva a compilar, los analizadores de xUnit vienen con el paquete `xunit` (regla `xUnit1048` para `async void`, `xUnit1031` para `.Result`/`.Wait()` en tests) y el compilador emite CS4014. Conviértelos en errores en el proyecto de tests:

```xml
<PropertyGroup>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
</PropertyGroup>
```

Verificación de que el test ahora sí vigila: comenta la validación en `AddAsync` y ejecuta `dotnet test`; `Rejects_non_positive_quantity` debe fallar con «Expected ArgumentException but no exception was thrown». Antes del arreglo seguía en verde.""",
            },
        ]
    },
    # 16) dotnet CLI y csproj (system exacto, principiante)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Vengo de Node. ¿Cómo creo un proyecto .NET con una librería, una API y tests, y qué es exactamente el csproj? ¿Es como el package.json?"},
            {
                "role": "assistant",
                "content": r"""El `.csproj` es el `package.json` **y** la configuración de build en un solo archivo XML: dependencias, versión del runtime, opciones del compilador y qué archivos se compilan (por defecto, todos los `.cs` de la carpeta). La solución (`.sln` o `.slnx`) es solo un índice de proyectos, como un *workspace* de npm.

Estructura típica y comandos para crearla:

```bash
mkdir Shop && cd Shop
dotnet new sln -n Shop

dotnet new classlib -n Shop.Core   -o src/Shop.Core
dotnet new webapi   -n Shop.Api    -o src/Shop.Api
dotnet new xunit    -n Shop.Tests  -o tests/Shop.Tests

dotnet sln add src/Shop.Core src/Shop.Api tests/Shop.Tests

dotnet add src/Shop.Api   reference src/Shop.Core
dotnet add tests/Shop.Tests reference src/Shop.Core

dotnet add src/Shop.Api package Serilog.AspNetCore
```

El csproj de la librería tras esto:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

Equivalencias con Node:

| Node | .NET |
|---|---|
| `package.json` dependencies | `<PackageReference Include="X" Version="1.2.3" />` |
| `npm install` | `dotnet restore` (implícito en `build`, `run`, `test`) |
| `package-lock.json` | No hay por defecto; `<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>` genera `packages.lock.json` |
| `node_modules` | Caché global en `~/.nuget/packages`, compartida entre proyectos |
| `npm run dev` | `dotnet watch run --project src/Shop.Api` |
| `npm test` | `dotnet test` |
| `npm run build` | `dotnet build`; para desplegar, `dotnet publish -c Release` |
| importar un paquete local | `<ProjectReference Include="../Shop.Core/Shop.Core.csproj" />` |

Para no repetir opciones en cada csproj, un `Directory.Build.props` en la raíz se aplica a todos los proyectos que cuelgan de ella:

```xml
<Project>
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
```

Ciclo diario:

```bash
dotnet build                      # compila toda la solución
dotnet test                       # ejecuta los tests
dotnet run --project src/Shop.Api # arranca la API (escucha en el puerto de launchSettings.json)
dotnet publish src/Shop.Api -c Release -o out   # binarios listos para desplegar
```

`publish` por defecto es *framework-dependent* (necesita el runtime instalado en el destino). Con `-r linux-x64 --self-contained` incluye el runtime, y con `-p:PublishAot=true` compila a nativo (.NET 8+), pero eso tiene restricciones de reflexión que no necesitas al empezar.

Un último contraste: en .NET las versiones de paquetes son fijas en el csproj (no hay `^1.2.0`); si quieres rangos, se escriben como `[1.2.0,2.0.0)`, pero lo habitual es fijar y actualizar con `dotnet outdated` (herramienta externa) o manualmente.""",
            },
        ]
    },
    # 17) source generators: noción
    {
        "messages": [
            {"role": "user", "content": "¿Qué es un source generator? Mi IDE me sugiere usar `GeneratedRegex` en vez de `new Regex(...)` y también vi algo de `LoggerMessage`. ¿Qué gano?"},
            {
                "role": "assistant",
                "content": r"""Un *source generator* es un componente de Roslyn que se ejecuta **durante la compilación**, inspecciona tu código y añade archivos `.cs` nuevos al proyecto. Nada de reflexión en tiempo de ejecución: el código que antes se construía dinámicamente al arrancar ya está escrito, compilado y optimizado antes de que el programa exista.

Lo que ganas con los dos que te sugiere el IDE:

**`[GeneratedRegex]`** (.NET 7+). `new Regex(pattern)` analiza el patrón al ejecutarse y, si pides `RegexOptions.Compiled`, genera IL en caliente; ambas cosas cuestan en el arranque y cada `new Regex` repetido en un método caliente vuelve a pagarlo. El generador escribe el autómata como código C# normal en compilación:

```csharp
using System.Text.RegularExpressions;

public static partial class Validators
{
    [GeneratedRegex(@"^\+?[1-9]\d{6,14}$", RegexOptions.ExplicitCapture)]
    private static partial Regex PhoneRegex();

    public static bool IsPhone(string input) => PhoneRegex().IsMatch(input);
}
```

La clase y el método son `partial`: tú declaras la firma, el generador aporta el cuerpo. Puedes ver el código generado en el IDE (en Visual Studio, bajo *Dependencies → Analyzers*). Resultado: arranque más rápido, sin coste por llamada, compatible con *Native AOT* (donde `RegexOptions.Compiled` no funciona) y los errores de sintaxis del patrón aparecen **al compilar**. El analizador `SYSLIB1045` es el que te sugiere el cambio.

**`[LoggerMessage]`** (`Microsoft.Extensions.Logging`, .NET 6+). `logger.LogInformation("Pedido {Id} creado", id)` empaqueta los argumentos en un `object[]` y hace *boxing* del `int` en cada llamada, aunque el nivel esté desactivado. El generador produce un delegado fuertemente tipado que comprueba `IsEnabled` primero y no asigna nada:

```csharp
public static partial class Log
{
    [LoggerMessage(EventId = 1001, Level = LogLevel.Information, Message = "Pedido {OrderId} creado en {Elapsed} ms")]
    public static partial void OrderCreated(ILogger logger, int orderId, double elapsed);
}

// uso
Log.OrderCreated(_logger, order.Id, sw.Elapsed.TotalMilliseconds);
```

Además fija el `EventId` y el texto en un sitio, y el generador falla la compilación si los nombres de las plantillas no coinciden con los parámetros.

Otros generadores del propio .NET que probablemente ya usas sin saberlo:

- `JsonSerializerContext` con `[JsonSerializable]`: System.Text.Json sin reflexión (obligatorio en AOT).
- `[LibraryImport]`: P/Invoke con el *marshalling* generado en vez de `DllImport` dinámico.
- Los `Minimal APIs` en .NET 8 con `<EnableRequestDelegateGenerator>` generan los delegados de los endpoints.

Cuándo escribirías uno tú: cuando hoy usas reflexión al arrancar para «descubrir» tipos (mapear DTOs, registrar handlers, generar builders) y el coste o la incompatibilidad con AOT te molestan. Es un proyecto `netstandard2.0` que referencia `Microsoft.CodeAnalysis.CSharp` e implementa `IIncrementalGenerator`. Antes de llegar ahí, mira si ya existe uno: Mapperly (mapeo), Refit (clientes HTTP), MediatR tiene variantes generadas.

La contrapartida: el código generado aparece en los *stack traces* y en el depurador, y un generador mal escrito ralentiza cada compilación. Para los de Microsoft eso ya está resuelto.""",
            },
        ]
    },
    # 18) ArrayPool y asignaciones en bucle caliente (código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un servicio que recibe mensajes por TCP y el GC está loco: `dotnet-counters` me da 300 colecciones gen0 por segundo. El bucle es este:

```csharp
while (!ct.IsCancellationRequested)
{
    var buffer = new byte[64 * 1024];
    var read = await stream.ReadAsync(buffer, ct);
    if (read == 0) break;
    var message = Encoding.UTF8.GetString(buffer, 0, read);
    await HandleAsync(message, ct);
}
```

Cada mensaje son unos 200 bytes. ¿Es el `new byte[]`?""",
            },
            {
                "role": "assistant",
                "content": r"""Sí. Cada iteración asigna 64 KB que mueren en milisegundos: a cientos de mensajes por segundo son decenas de MB/s de basura, y gen0 se dispara para limpiarla. El string de `GetString` (~200 bytes) es la otra asignación, pero es la que de verdad necesitas.

**Arreglo mínimo: un buffer fuera del bucle.** Es un bucle secuencial, nunca hay dos lecturas a la vez, así que un único array reutilizado es correcto y elimina casi toda la basura:

```csharp
var buffer = new byte[8 * 1024];   // 200 bytes por mensaje: 64 KB era desproporcionado
while (!ct.IsCancellationRequested)
{
    var read = await stream.ReadAsync(buffer, ct);
    if (read == 0) break;
    var message = Encoding.UTF8.GetString(buffer.AsSpan(0, read));
    await HandleAsync(message, ct);
}
```

`ArrayPool<T>` es la herramienta cuando el buffer tiene que **salir** del bucle (lo retiene el handler, lo usan varios métodos, hay miles de conexiones y quieres devolver memoria en reposo). Para ese caso:

```csharp
var buffer = ArrayPool<byte>.Shared.Rent(8 * 1024);
try
{
    while (!ct.IsCancellationRequested)
    {
        var read = await stream.ReadAsync(buffer, ct);
        if (read == 0) break;
        await HandleAsync(Encoding.UTF8.GetString(buffer, 0, read), ct);
    }
}
finally
{
    ArrayPool<byte>.Shared.Return(buffer);
}
```

Reglas del pool que no perdonan:

- `Rent(n)` devuelve un array de **al menos** `n` bytes; puede ser mayor. Usa siempre `read` o un `Span` acotado, nunca `buffer.Length`.
- Después de `Return` no lo toques ni lo guardes: otro hilo puede recibir el mismo array. Si `HandleAsync` lo retuviera, tendrías corrupción silenciosa.
- `Return(buffer, clearArray: true)` si contiene datos sensibles; por defecto no se limpia.
- Para buffers pequeños (< 1 KB) y de ámbito síncrono, `stackalloc` es aún más barato y no necesita devolución.

**Un bug que el GC te está tapando.** TCP es un flujo, no mensajes: `ReadAsync` puede devolver medio mensaje, o dos pegados. Tu código asume «una lectura = un mensaje» y fallará bajo carga o con latencia. La solución habitual es `PipeReader` (`System.IO.Pipelines`) buscando un delimitador:

```csharp
var reader = PipeReader.Create(stream);
while (true)
{
    var result = await reader.ReadAsync(ct);
    var buffer = result.Buffer;
    while (TryReadLine(ref buffer, out var line))
        await HandleAsync(Encoding.UTF8.GetString(line), ct);
    reader.AdvanceTo(buffer.Start, buffer.End);
    if (result.IsCompleted) break;
}

static bool TryReadLine(ref ReadOnlySequence<byte> buffer, out ReadOnlySequence<byte> line)
{
    var position = buffer.PositionOf((byte)'\n');
    if (position is null) { line = default; return false; }
    line = buffer.Slice(0, position.Value);
    buffer = buffer.Slice(buffer.GetPosition(1, position.Value));
    return true;
}
```

`PipeReader` gestiona sus propios buffers del pool; tú no asignas nada hasta el `GetString`.

Verifica con `dotnet-counters monitor --counters System.Runtime`: `gen-0-gc-count` debe bajar de 300/s a unidades, y `alloc-rate` a unos cientos de bytes por mensaje. Si sigue alto, el siguiente sospechoso es `HandleAsync`.""",
            },
        ]
    },
    # 19) captura de closures en bucle for (principiante, código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Esto imprime `3 3 3` y yo esperaba `0 1 2`:

```csharp
var tasks = new List<Task>();
for (int i = 0; i < 3; i++)
{
    tasks.Add(Task.Run(() => Console.WriteLine(i)));
}
await Task.WhenAll(tasks);
```

¿Por qué? Con un foreach sobre una lista sí funciona.""",
            },
            {
                "role": "assistant",
                "content": r"""La lambda captura la **variable** `i`, no su valor en ese momento. En un `for` hay una sola variable `i` para todo el bucle; cuando las tareas por fin se ejecutan, el bucle ya terminó e `i` vale 3. Las tres lambdas apuntan a la misma `i`.

Con `foreach` funciona porque, desde C# 5, la variable de iteración es **nueva en cada vuelta**: cada lambda captura la suya. El `for` no cambió porque su variable se declara explícitamente fuera del cuerpo y mutarla es parte del contrato del bucle.

Arreglo: copia el valor a una variable local del cuerpo, que sí es una por iteración.

```csharp
for (int i = 0; i < 3; i++)
{
    int current = i;
    tasks.Add(Task.Run(() => Console.WriteLine(current)));
}
```

O evita el `for` y deja que LINQ te dé una variable por elemento:

```csharp
var tasks = Enumerable.Range(0, 3)
    .Select(n => Task.Run(() => Console.WriteLine(n)))
    .ToList();
await Task.WhenAll(tasks);
```

Aquí `n` es un parámetro de la lambda externa, distinto en cada llamada.

Lo mismo ocurre en cualquier sitio donde una lambda sobreviva al bucle: suscribir manejadores de eventos (`button.Click += (_, _) => Open(i)`), registrar callbacks, construir diccionarios de delegados. Y también con `while` y un contador declarado fuera.

Nota: el orden de salida con `Task.Run` no está garantizado (`1 0 2` es válido); si la prueba necesita orden, imprime en el `await` y no dentro de la tarea.

Verificación mental con el código original: las tres `Task.Run` se encolan en microsegundos; antes de que ninguna llegue a ejecutarse, el bucle ha hecho `i++` tres veces y salido con `i == 3`. Es lo que ves. Si pusieras un `Thread.Sleep(100)` dentro del bucle, «funcionaría» y te daría la falsa impresión de que está bien: la copia local es la única solución correcta.""",
            },
        ]
    },
    # 20) DateTime vs DateTimeOffset -> TimeProvider (multiturno, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "¿DateTime o DateTimeOffset para guardar cuándo se creó un pedido? Ahora uso `DateTime.Now` y los pedidos de la sucursal de Canarias salen con una hora de diferencia respecto a Madrid."},
            {
                "role": "assistant",
                "content": r"""`DateTimeOffset`, generando el instante con `DateTimeOffset.UtcNow`. Un pedido se crea en un **instante** concreto, y un instante es el mismo en Madrid, en Canarias y en Bogotá; lo que cambia es cómo se muestra.

El problema con `DateTime.Now`:

- Devuelve la hora **local del servidor** (o del cliente, si corre allí) y la etiqueta con `Kind = Local`, pero esa etiqueta no viaja: al guardar en base de datos o serializar a JSON, el `Kind` se pierde y queda un «2024-05-01 10:00» sin saber de qué zona. Dos servidores en zonas distintas producen valores incomparables. Es exactamente tu síntoma.
- `DateTime` tiene tres `Kind` (`Utc`, `Local`, `Unspecified`) y las comparaciones **ignoran** el `Kind`: `10:00 Local == 10:00 Utc` da `true` aunque sean instantes distintos.

`DateTimeOffset` lleva el desplazamiento dentro del valor (`2024-05-01T10:00:00+01:00`), se compara como instante, se serializa sin ambigüedad y se mapea bien: `timestamptz` en PostgreSQL, `datetimeoffset` en SQL Server.

```csharp
public sealed class Order
{
    public int Id { get; init; }
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.UtcNow;
}
```

Para **mostrar** en la zona del usuario conviertes en el borde (vista, API de salida), nunca al guardar:

```csharp
var madrid = TimeZoneInfo.FindSystemTimeZoneById("Europe/Madrid");
var canarias = TimeZoneInfo.FindSystemTimeZoneById("Atlantic/Canary");

var created = order.CreatedAt;                                    // 2024-05-01T08:00:00+00:00
Console.WriteLine(TimeZoneInfo.ConvertTime(created, madrid));     // 01/05/2024 10:00:00 +02:00
Console.WriteLine(TimeZoneInfo.ConvertTime(created, canarias));   // 01/05/2024 9:00:00 +01:00
```

Desde .NET 6 los identificadores IANA (`Europe/Madrid`) funcionan en Windows, Linux y macOS; en versiones anteriores en Windows tenías que usar «Romance Standard Time».

Cuándo sigue teniendo sentido `DateTime`: fechas sin instante (un cumpleaños, un vencimiento «el día 30») y para eso en .NET 6+ es mejor `DateOnly`; y horas de reloj de pared sin fecha, `TimeOnly`. Un «pedido creado» no es ninguna de las dos.

Migración mínima: cambia el tipo de la columna y de la propiedad, sustituye `DateTime.Now` por `DateTimeOffset.UtcNow`, y convierte a zona solo en la capa de presentación.""",
            },
            {"role": "user", "content": "Hecho. Ahora los tests que comprueban «pedidos de hoy» fallan a las 23:30 y justo al pasar medianoche. ¿Cómo los hago deterministas?"},
            {
                "role": "assistant",
                "content": r"""Dos cosas distintas fallaban, y la segunda es un bug real que el test te estaba enseñando.

**1. El código lee el reloj del sistema.** Inyecta `TimeProvider` (.NET 8, en `System`) en vez de llamar a `DateTimeOffset.UtcNow`. En producción se registra `TimeProvider.System`; en los tests, un reloj falso.

**2. «Hoy» no existe sin zona horaria.** A las 23:30 UTC ya es 01:30 del día siguiente en Madrid. Si el rango de «hoy» se calcula en UTC y el negocio piensa en hora de Madrid, los pedidos de la franja 22:00-00:00 UTC caen en el día equivocado. El test fallaba justo ahí. Fija la zona de negocio explícitamente y calcula el rango como instantes.

```csharp
public sealed class OrderQueries(AppDbContext db, TimeProvider clock, TimeZoneInfo businessZone)
{
    public Task<List<Order>> TodayAsync(CancellationToken ct)
    {
        var (start, end) = TodayRange(clock.GetUtcNow(), businessZone);
        return db.Orders
            .Where(o => o.CreatedAt >= start && o.CreatedAt < end)   // semiabierto: no pierde las 23:59:59.999
            .ToListAsync(ct);
    }

    public static (DateTimeOffset Start, DateTimeOffset End) TodayRange(DateTimeOffset nowUtc, TimeZoneInfo zone)
    {
        var localDate = TimeZoneInfo.ConvertTime(nowUtc, zone).Date;      // medianoche local de hoy
        var start = new DateTimeOffset(localDate, zone.GetUtcOffset(localDate));
        var nextDate = localDate.AddDays(1);
        var end = new DateTimeOffset(nextDate, zone.GetUtcOffset(nextDate)); // offset propio: cubre el cambio de hora
        return (start, end);
    }
}
```

Registro:

```csharp
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton(TimeZoneInfo.FindSystemTimeZoneById("Europe/Madrid"));
```

Test determinista con `FakeTimeProvider` (paquete `Microsoft.Extensions.TimeProvider.Testing`), fijado precisamente en el caso que fallaba:

```csharp
[Fact]
public void TodayRange_uses_business_zone_not_utc()
{
    var madrid = TimeZoneInfo.FindSystemTimeZoneById("Europe/Madrid");
    var clock = new FakeTimeProvider(new DateTimeOffset(2024, 5, 1, 22, 30, 0, TimeSpan.Zero)); // 00:30 del 2 de mayo en Madrid

    var (start, end) = OrderQueries.TodayRange(clock.GetUtcNow(), madrid);

    Assert.Equal(new DateTimeOffset(2024, 5, 1, 22, 0, 0, TimeSpan.Zero), start);  // 2 de mayo 00:00 +02:00
    Assert.Equal(new DateTimeOffset(2024, 5, 2, 22, 0, 0, TimeSpan.Zero), end);

    var lateYesterday = new DateTimeOffset(2024, 5, 1, 21, 0, 0, TimeSpan.Zero);  // 23:00 del 1 de mayo en Madrid
    Assert.False(lateYesterday >= start && lateYesterday < end);
}
```

Este test pasa a cualquier hora real y documenta la regla. Añade otro con la fecha del cambio de horario (último domingo de marzo) para fijar que `end - start` es de 23 horas ese día.

`FakeTimeProvider` también permite `clock.Advance(TimeSpan.FromMinutes(31))` para probar expiraciones y `Task.Delay`/`PeriodicTimer` creados a partir del `TimeProvider`, sin esperar de verdad.""",
            },
        ]
    },
    # 21) async void (principiante)
    {
        "messages": [
            {"role": "user", "content": "¿Por qué dicen que `async void` es malo si el compilador lo acepta sin quejarse? Yo lo uso en varios métodos y funciona."},
            {
                "role": "assistant",
                "content": r"""Funciona hasta que algo falla dentro. Un método `async void` no devuelve nada que el llamador pueda observar, y eso rompe tres cosas:

1. **Las excepciones tumban el proceso.** En un `async Task`, la excepción se guarda en la `Task` y aparece cuando haces `await`. En `async void` no hay `Task`: la excepción se lanza en el `SynchronizationContext` (o en el *thread pool*) y nadie la atrapa. En una app de escritorio cierra la aplicación; en un servicio, mata el proceso.
2. **No se puede esperar.** El llamador sigue antes de que termine. Un test que llame a un `async void` acaba antes de que el método haga nada.
3. **No se puede componer.** Sin `Task` no hay `Task.WhenAll`, ni timeout, ni cancelación encadenada.

```csharp
// Mal: si Save lanza, el proceso cae y el llamador no se entera de nada
public async void SaveInBackground(Order order)
{
    await _repo.SaveAsync(order);
}

// Bien: la excepción viaja en la Task
public async Task SaveAsync(Order order)
{
    await _repo.SaveAsync(order);
}
```

Un método `async` que no devuelve valor devuelve `Task`; si devuelve algo, `Task<T>`. La firma solo cambia en el tipo de retorno; el cuerpo es idéntico.

**La única excepción legítima: manejadores de eventos.** La firma del evento está fijada (`void Handler(object sender, EventArgs e)`) y no puedes cambiarla. Ahí sí usas `async void`, y por eso mismo el cuerpo debe atrapar cualquier excepción:

```csharp
private async void OnSaveClicked(object sender, EventArgs e)
{
    try
    {
        await SaveAsync(_currentOrder);
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "Error al guardar");
        ShowError(ex.Message);
    }
}
```

Fíjate en el patrón: el `async void` es una cáscara de una línea que delega en un `async Task` y atrapa. Toda la lógica vive en el método que sí se puede probar y esperar.

Si de verdad quieres «lanzar y olvidar» una tarea (por ejemplo, enviar una métrica sin bloquear), hazlo explícito en vez de con `async void`:

```csharp
_ = Task.Run(async () =>
{
    try { await _metrics.SendAsync(); }
    catch (Exception ex) { _logger.LogWarning(ex, "Metric send failed"); }
});
```

El descarte `_` dice a quien lea el código que la omisión del `await` es intencional, y el `try/catch` evita que la excepción quede sin observar.

Comprueba cuántos tienes con el analizador: la regla `VSTHRD100` (paquete `Microsoft.VisualStudio.Threading.Analyzers`) marca cada `async void` que no sea manejador de eventos.""",
            },
        ]
    },
    # 22) C# 12/13 features (en inglés, system variante)
    {
        "messages": [
            {"role": "system", "content": "Answer in English. Be concise and code-first; mention the exact language or runtime version each feature needs."},
            {"role": "user", "content": "We're moving a backend from .NET 6 to .NET 8 (and probably .NET 9 later). Which new C# language features are actually worth adopting in a typical service codebase, with short examples?"},
            {
                "role": "assistant",
                "content": r"""Worth adopting in a service codebase, in rough order of payoff.

**C# 12 (.NET 8)**

1. **Primary constructors on classes.** Removes constructor boilerplate for DI-heavy classes. The parameters are captured, not `readonly` fields, so don't reassign them.

```csharp
public sealed class OrderService(IOrderRepository repo, ILogger<OrderService> logger)
{
    public Task<Order?> GetAsync(int id, CancellationToken ct) => repo.FindAsync(id, ct);
}
```

2. **Collection expressions.** One syntax for arrays, spans, lists and anything with a collection builder, with `..` to spread.

```csharp
int[] primes = [2, 3, 5];
List<int> more = [.. primes, 7, 11];
ReadOnlySpan<byte> header = [0x1F, 0x8B];
```

3. **Alias any type.** Tuples and generic instantiations get readable names without a new type.

```csharp
using Money = (decimal Amount, string Currency);
using UserCache = System.Collections.Concurrent.ConcurrentDictionary<int, User>;
```

4. **Default lambda parameters.** Handy for minimal API filters and test helpers: `var retry = (int attempts = 3) => Policy(attempts);`

5. **`ref readonly` parameters.** Only if you already pass large structs by `in`; it makes the intent explicit. Skip otherwise.

**C# 13 (.NET 9)**

6. **`params` with spans and collections.** `params ReadOnlySpan<T>` avoids the array allocation on every call; existing callers don't change.

```csharp
static string Join(params ReadOnlySpan<string> parts) => string.Join(',', parts);
```

7. **`System.Threading.Lock`.** A dedicated lock type; `lock (myLock)` compiles to `EnterScope()` and is cheaper than monitor-based locking. Replace `private readonly object _gate = new();` with `private readonly Lock _gate = new();`. Mixing it with `Monitor.Enter` is a compile error, which is the point.

8. **Partial properties.** Lets source generators (like `[GeneratedRegex]`) target properties, not just methods.

9. **Implicit index access in initializers.** `new TimerSettings { Buffer = { [^1] = 0 } }`, rarely needed.

**Also in .NET 8 as libraries, not syntax**

- `TimeProvider` for testable time.
- `FrozenDictionary` / `FrozenSet` for read-heavy lookups built once.
- `SearchValues<T>` for fast `IndexOfAny` over a fixed set of chars or bytes.
- Keyed DI services: `AddKeyedSingleton<IPayment, Stripe>("stripe")` and `[FromKeyedServices("stripe")]`.

**Skip for now**

- `field` keyword: still preview in C# 13.
- Inline arrays: only for interop or very hot paths.
- Interceptors: experimental; generated by ASP.NET's request delegate generator, not meant for hand-written use.

Set the language version through the SDK, not by hand: `<TargetFramework>net8.0</TargetFramework>` already gives you C# 12. Forcing `<LangVersion>13</LangVersion>` on net8.0 compiles most syntax but features that need runtime support (`Lock`, `params ReadOnlySpan<T>` overloads in the BCL) won't work until you target net9.0.""",
            },
        ]
    },
    # 23) cultura y comparación de strings (en inglés)
    {
        "messages": [
            {"role": "user", "content": "Our app breaks for a Turkish customer: a check like `name.ToUpper() == \"FILE\"` fails for input `file`. Why does that happen, and what's the right way to compare strings in C#?"},
            {
                "role": "assistant",
                "content": r"""Turkish has two letter i's: dotted `i` uppercases to `İ` (U+0130), and `ı` (dotless) uppercases to `I`. Under the `tr-TR` culture, `"file".ToUpper()` is `"FİLE"`, which is not equal to `"FILE"`. `ToUpper()` and `ToLower()` without arguments use the **current culture**, so the result depends on the machine the code runs on.

The rule: pick the comparison by what the strings *are*.

| Strings are | Use |
|---|---|
| Identifiers, keys, file names, protocol tokens, anything programmatic | `StringComparison.Ordinal` / `OrdinalIgnoreCase` |
| Text shown to or sorted for a human | `StringComparison.CurrentCulture` (or a specific `CultureInfo`) |
| Text that must sort the same on every machine but is still linguistic | `InvariantCulture` |

Your check is a programmatic comparison, so:

```csharp
if (string.Equals(name, "FILE", StringComparison.OrdinalIgnoreCase))
```

Ordinal compares code units: fast, deterministic, and immune to culture. `OrdinalIgnoreCase` folds using invariant rules, so `i`/`I` match everywhere.

Fixes for the patterns that usually surround this bug:

```csharp
// Case normalisation for keys: invariant, never current culture
var key = name.ToUpperInvariant();

// Dictionaries and sets: bake the comparer in once
var byName = new Dictionary<string, User>(StringComparer.OrdinalIgnoreCase);

// StartsWith / EndsWith / IndexOf default to CURRENT CULTURE; say what you mean
if (path.EndsWith(".csv", StringComparison.OrdinalIgnoreCase)) { }

// Sorting a list for display: culture is right here
users.Sort((a, b) => string.Compare(a.Name, b.Name, StringComparison.CurrentCulture));
```

Two traps beyond Turkish:

- `string.Compare(a, b)` and `a.CompareTo(b)` are **culture-sensitive**. `"a".CompareTo("B")` can be negative in one culture and positive in another, and culture-sensitive compare on ICU ignores some characters (`"co-op".IndexOf("coop")` finds a match in some cultures). Use `CompareOrdinal` for keys.
- `IndexOf(char)` is ordinal, but `IndexOf(string)` is culture-sensitive. Same name, different semantics.

Let the compiler police it. In `.editorconfig`:

```ini
dotnet_diagnostic.CA1304.severity = warning   # specify CultureInfo
dotnet_diagnostic.CA1305.severity = warning   # specify IFormatProvider
dotnet_diagnostic.CA1309.severity = warning   # use ordinal StringComparison
dotnet_diagnostic.CA1310.severity = warning   # specify StringComparison for correctness
```

Regression test that reproduces the customer's machine without changing yours:

```csharp
[Fact]
public void Matches_file_under_turkish_culture()
{
    var original = CultureInfo.CurrentCulture;
    CultureInfo.CurrentCulture = new CultureInfo("tr-TR");
    try
    {
        Assert.True(FileKind.IsFile("file"));
    }
    finally
    {
        CultureInfo.CurrentCulture = original;
    }
}
```

If the service has no user-facing text at all, `<InvariantGlobalization>true</InvariantGlobalization>` in the csproj drops ICU entirely: smaller image, and culture bugs become impossible rather than unlikely.""",
            },
        ]
    },
    # 24) limitar concurrencia (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Tengo que llamar a una API externa para 5000 ids. Con `Task.WhenAll` sobre los 5000 me devuelve 429 Too Many Requests. ¿Cómo limito a 10 llamadas a la vez?"},
            {
                "role": "assistant",
                "content": r"""`Parallel.ForEachAsync` (.NET 6+) hace exactamente eso: un grado de paralelismo fijo y cancelación integrada.

```csharp
var results = new ConcurrentBag<ItemResult>();

await Parallel.ForEachAsync(
    ids,
    new ParallelOptions { MaxDegreeOfParallelism = 10, CancellationToken = ct },
    async (id, token) =>
    {
        var item = await client.GetAsync(id, token);
        results.Add(new ItemResult(id, item));
    });
```

Qué garantiza y qué no:

- Como mucho 10 lambdas en vuelo; la siguiente arranca cuando una termina. Es el *throttle* que necesitas.
- Una excepción en una lambda cancela el resto (vía el `token` que recibe la lambda) y `ForEachAsync` lanza esa excepción. Si quieres que un fallo no pare el lote, atrápalo dentro y guarda el error como resultado.
- El orden de `results` es el de finalización, no el de `ids` (de ahí el `ConcurrentBag`).

Si no quieres cancelar todo por un 404 de un id:

```csharp
async (id, token) =>
{
    try
    {
        results.Add(new ItemResult(id, await client.GetAsync(id, token), Error: null));
    }
    catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
    {
        results.Add(new ItemResult(id, null, Error: "not found"));
    }
}
```

La alternativa clásica es `SemaphoreSlim` + `Task.WhenAll`:

```csharp
using var gate = new SemaphoreSlim(10);
var tasks = ids.Select(async id =>
{
    await gate.WaitAsync(ct);
    try { return await client.GetAsync(id, ct); }
    finally { gate.Release(); }
});
var items = await Task.WhenAll(tasks);
```

Crea 5000 tareas de golpe (cada una esperando en el semáforo), así que consume más memoria que `ForEachAsync`, pero tiene una ventaja que veremos enseguida: `items` sale en el orden de `ids`.

Dos cosas más que importan con un 429:

- El servidor suele devolver `Retry-After`. Con `Microsoft.Extensions.Http.Resilience` y `AddStandardResilienceHandler()` en el `HttpClient` los reintentos respetan esa cabecera sin que escribas el bucle.
- 10 en paralelo puede seguir siendo demasiado si el límite es «por segundo», no «simultáneas». Para eso, un `RateLimiter` de `System.Threading.RateLimiting` (`TokenBucketRateLimiter`) delante de cada llamada.""",
            },
            {"role": "user", "content": "¿Y si necesito los resultados en el mismo orden que los ids? Luego los escribo en un CSV y tienen que coincidir línea a línea."},
            {
                "role": "assistant",
                "content": r"""Reserva el array de salida y escribe cada resultado **en su índice**. El paralelismo sigue limitado y el orden lo da la posición, no el tiempo de llegada.

```csharp
var items = new Item?[ids.Count];

await Parallel.ForEachAsync(
    Enumerable.Range(0, ids.Count),
    new ParallelOptions { MaxDegreeOfParallelism = 10, CancellationToken = ct },
    async (i, token) =>
    {
        items[i] = await client.GetAsync(ids[i], token);
    });

// items[i] corresponde a ids[i]
```

Escribir en posiciones distintas de un array desde varios hilos es seguro: no hay dos lambdas que toquen el mismo índice, y `ForEachAsync` sincroniza al terminar, así que después del `await` ves todas las escrituras. No necesitas `ConcurrentBag` ni `lock`.

Si prefieres la versión con `SemaphoreSlim`, ya viene ordenada: `Task.WhenAll` devuelve los resultados en el orden de las tareas, que es el orden de `ids`. Es la razón por la que a veces compensa pese a crear todas las tareas de golpe.

Para el CSV, escribe directamente desde el array:

```csharp
await using var writer = new StreamWriter("items.csv");
await writer.WriteLineAsync("id,name,price");
for (var i = 0; i < ids.Count; i++)
{
    var item = items[i];
    await writer.WriteLineAsync(item is null
        ? $"{ids[i]},,"
        : $"{ids[i]},{Csv(item.Name)},{item.Price.ToString(CultureInfo.InvariantCulture)}");
}

static string Csv(string value) =>
    value.Contains(',') || value.Contains('"') || value.Contains('\n')
        ? $"\"{value.Replace("\"", "\"\"")}\""
        : value;
```

`InvariantCulture` en el precio para que no salga `12,5` en una máquina española, y el escapado de comillas porque un nombre con coma rompería la correspondencia línea a línea que necesitas.

Prueba rápida de orden: ejecuta con ids `[3, 1, 2]` contra un cliente falso que tarde más en el 3; `items[0]` debe ser el del id 3 aunque haya llegado el último.""",
            },
        ]
    },
    # 25) trampas de rendimiento con LINQ
    {
        "messages": [
            {"role": "user", "content": "Revisando código veo cosas como `if (lista.Count() > 0)` y un `foreach` que dentro hace `otraLista.Contains(x)`. ¿Está mal o es manía mía?"},
            {
                "role": "assistant",
                "content": r"""Las dos son mejorables, y la segunda puede ser un problema serio.

**`lista.Count() > 0`.** Si `lista` es `List<T>` o array, `Count()` detecta `ICollection<T>` y devuelve la propiedad en O(1); el coste es despreciable, pero `lista.Count > 0` (propiedad) es más claro y no depende de esa optimización. Si `lista` es un `IEnumerable<T>` diferido, `Count()` recorre **todo** para contestar «¿hay alguno?». Usa `Any()`: para en el primer elemento.

```csharp
if (pending.Any())            // O(1) con cualquier origen
if (pending.Count > 0)        // solo si es List<T>/array/ICollection
```

En .NET 6+ `TryGetNonEnumeratedCount(out var n)` te da el número sin enumerar cuando es posible; útil para preasignar.

**`otraLista.Contains(x)` dentro de un bucle.** `List<T>.Contains` es lineal. Con `n` elementos fuera y `m` dentro es O(n·m): 10 000 × 10 000 son cien millones de comparaciones. Pásalo a un `HashSet<T>` una vez, fuera del bucle:

```csharp
var known = otraLista.ToHashSet();          // O(m), una vez
foreach (var x in lista)
    if (known.Contains(x)) { }              // O(1) por consulta
```

Si los elementos son strings y la comparación debe ignorar mayúsculas, `ToHashSet(StringComparer.OrdinalIgnoreCase)`. Y si lo que haces es «los de `lista` que están en `otraLista`», eso es `lista.Intersect(otraLista)` o un `Join`, que ya usan un hash por dentro.

Otros tres patrones del mismo tipo que suelen ir juntos:

- `OrderBy(x => x.Price).First()` ordena todo (O(n log n)) para sacar uno. `MinBy(x => x.Price)` (.NET 6+) es O(n) y expresa la intención.
- `ToList()` dentro de un bucle sobre la misma consulta: materializa cada vuelta. Materializa una vez fuera.
- `lista.ElementAt(i)` en un `for` sobre un `IEnumerable<T>`: cada acceso vuelve a enumerar desde el principio. Si necesitas índices, es una lista o un array, o `foreach` con `Select((x, i) => ...)`.

Cómo saber si importa: mide con el tamaño real de los datos. Para 50 elementos nada de esto se nota; para 50 000, el `Contains` en bucle es la diferencia entre 0,1 s y varios minutos. Los analizadores `CA1827` (`Count()` para comprobar vacío) y `CA1860` (preferir `Count`/`Length` a `Any()` en colecciones concretas) marcan el primer caso automáticamente.""",
            },
        ]
    },
    # 26) CancellationToken y timeouts (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "¿Cómo paso bien un CancellationToken por una cadena de métodos y aplico un timeout de 5 segundos a una llamada HTTP concreta sin romper la cancelación que viene del usuario?"},
            {
                "role": "assistant",
                "content": r"""Enlaza los dos tokens con `CreateLinkedTokenSource` y aplica el timeout al enlazado. Así la llamada se cancela si el usuario cancela **o** si pasan 5 segundos, y puedes distinguir cuál de los dos ocurrió.

```csharp
public async Task<Quote> GetQuoteAsync(string symbol, CancellationToken ct)
{
    using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
    timeout.CancelAfter(TimeSpan.FromSeconds(5));

    try
    {
        return await _http.GetFromJsonAsync<Quote>($"quotes/{symbol}", timeout.Token)
               ?? throw new InvalidOperationException($"Empty quote for {symbol}");
    }
    catch (OperationCanceledException) when (ct.IsCancellationRequested)
    {
        throw;                                   // cancelación del usuario: propaga tal cual
    }
    catch (OperationCanceledException ex)
    {
        throw new TimeoutException($"Quote service did not answer in 5 s for {symbol}", ex);
    }
}
```

Por qué así:

- **El filtro `when (ct.IsCancellationRequested)`** separa los dos casos. Si el token original está cancelado, fue el usuario: relanzas y el llamador verá su propia cancelación. Si no, fue el `CancelAfter`: lo conviertes en `TimeoutException`, que es lo que de verdad pasó.
- **`using` en el CTS enlazado**: el `CancelAfter` crea un temporizador; desecharlo lo libera aunque la llamada termine antes.
- **`HttpClient.Timeout`** es otra opción, pero es global al cliente y en .NET 8 se manifiesta como `TaskCanceledException` con `InnerException` de tipo `TimeoutException`. El enlace manual te deja timeouts distintos por operación.

Convenciones para la cadena de llamadas:

1. `CancellationToken ct` es el **último parámetro** y se llama igual en toda la cadena. En métodos públicos, `= default` para que sea opcional.
2. Pásalo a **todo** lo que lo acepte: `ReadAsync`, `Task.Delay`, `SemaphoreSlim.WaitAsync`, EF Core, `Parallel.ForEachAsync`. Un método que lo recibe y no lo pasa rompe la cadena.
3. En bucles largos de CPU, `ct.ThrowIfCancellationRequested()` al principio de cada iteración; sin I/O nadie lo comprobará por ti.
4. No lo guardes en un campo para usarlo después: representa *esta* operación.
5. Nunca `catch (OperationCanceledException) { }` para silenciarla. Si cancelas, la cancelación debe subir hasta quien la pidió. En ASP.NET Core, cuando el cliente cierra la conexión, `HttpContext.RequestAborted` se cancela y la excepción que sube es la forma correcta de abortar la petición.

Para probar sin red: un `HttpMessageHandler` falso que espere `Task.Delay(10_000, ct)` reproduce el timeout en 5 segundos; otro que ignore el token comprueba que el `CancelAfter` corta igualmente la espera del `await`.

```csharp
[Fact]
public async Task Times_out_after_five_seconds()
{
    var handler = new DelayingHandler(TimeSpan.FromSeconds(30));
    var client = new QuoteClient(new HttpClient(handler) { BaseAddress = new("https://x/") });

    var ex = await Assert.ThrowsAsync<TimeoutException>(() => client.GetQuoteAsync("ACME", CancellationToken.None));
    Assert.IsType<OperationCanceledException>(ex.InnerException, exactMatch: false);
}
```

`exactMatch: false` admite `TaskCanceledException`, que es la subclase que lanza `HttpClient`.""",
            },
        ]
    },
    # 27) ValueTask vs Task (en inglés)
    {
        "messages": [
            {"role": "user", "content": "When should I return ValueTask instead of Task? Our team lead wants ValueTask on every async method because it \"avoids allocations\"."},
            {
                "role": "assistant",
                "content": r"""Only when the method **frequently completes synchronously** and is called on a hot path. Everywhere else, `Task` is the better default: it's cheaper to get right and the allocation it saves is usually one that never happens.

What `ValueTask<T>` actually saves: when an `async Task<T>` method hits an `await` that isn't already complete, the runtime allocates a `Task<T>` to represent the pending work. When the method completes synchronously (cache hit, buffered data already available), .NET already avoids most of that cost for `Task` too, except the result wrapper for non-trivial `T`. `ValueTask<T>` is a struct that holds either the result or a `Task<T>`, so the synchronous path allocates nothing.

The textbook case:

```csharp
public ValueTask<Product?> GetAsync(int id, CancellationToken ct)
{
    if (_cache.TryGetValue(id, out var product))
        return ValueTask.FromResult<Product?>(product);     // sync path: zero allocations

    return new ValueTask<Product?>(LoadAndCacheAsync(id, ct));  // async path: one Task as before
}
```

If 95 % of calls hit the cache, you removed 95 % of the allocations. If the method always does I/O, `ValueTask` saves nothing and adds a 16-byte struct to copy around.

The rules that make it dangerous as a blanket policy. A `ValueTask` may be backed by a pooled `IValueTaskSource` (socket and pipe reads are), and that object is reused as soon as you consume the result once:

- **Await it exactly once.** A second `await` or `.Result` can read someone else's result.
- **No `Task.WhenAll`**, no storing in a list to await later, no `.GetAwaiter().GetResult()` while incomplete. Call `.AsTask()` first if you need any of that, which allocates and cancels the benefit.
- **Don't await it after `.Preserve()` either**, unless you know why you need that.

Each rule is a silent bug, not a compile error. On a team where every method returns `ValueTask`, someone will eventually write `var t = GetAsync(1); if (t.IsCompleted) Use(t.Result); await t;` and corrupt state.

Practical policy:

| Situation | Return type |
|---|---|
| Public API, service layer, controllers, anything called by other teams | `Task` / `Task<T>` |
| Interface implemented by both sync and async providers (`IAsyncDisposable`, custom stream wrappers) | `ValueTask` |
| Hot path with a measured synchronous fast path (cache, buffered parser, in-memory queue) | `ValueTask<T>` |
| Method with no `await` that just returns a known value | `ValueTask.FromResult` or `Task.FromResult`; both are cheap |

"Measured" is the key word: `BenchmarkDotNet` with `[MemoryDiagnoser]` on the actual call pattern. If the *Allocated* column doesn't move, the lead's rule is costing readability for nothing.

One more thing it won't do: `ValueTask` doesn't make the method faster to execute; it only changes what happens at the return boundary. The async state machine, the `await`s inside, and the I/O cost exactly the same.""",
            },
        ]
    },
    # 28) igualdad en claves de diccionario (system variante: revisor estricto, código del usuario)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala primero el bug más grave, luego el resto, y propone el arreglo mínimo."},
            {
                "role": "user",
                "content": r"""Guardo celdas visitadas en un diccionario pero las búsquedas fallan y repito trabajo:

```csharp
public class Coord
{
    public int X;
    public int Y;
}

var visited = new Dictionary<Coord, int>();
visited[new Coord { X = 1, Y = 2 }] = 5;

var probe = new Coord { X = 1, Y = 2 };
Console.WriteLine(visited.ContainsKey(probe));  // False ???
```""",
            },
            {
                "role": "assistant",
                "content": r"""**Bug grave: `Coord` compara por referencia.** Una `class` sin `Equals`/`GetHashCode` propios usa los de `object`: dos instancias distintas nunca son iguales aunque tengan los mismos campos. `Dictionary` calcula el hash de `probe`, cae en otro cubo (o en el mismo y `Equals` da `false`) y no lo encuentra. No es un fallo del diccionario: es que tu tipo dice que (1,2) y (1,2) son cosas diferentes.

**Arreglo mínimo:** conviértelo en un `readonly record struct`. Obtienes igualdad por valor, `GetHashCode` coherente, inmutabilidad y sin asignación en el heap, en una línea:

```csharp
public readonly record struct Coord(int X, int Y);

var visited = new Dictionary<Coord, int>();
visited[new Coord(1, 2)] = 5;
Console.WriteLine(visited.ContainsKey(new Coord(1, 2)));  // True
```

Si por alguna razón debe seguir siendo una clase (herencia, EF), implementa la igualdad completa; a medias es peor que nada:

```csharp
public sealed class Coord : IEquatable<Coord>
{
    public int X { get; }
    public int Y { get; }

    public Coord(int x, int y) => (X, Y) = (x, y);

    public bool Equals(Coord? other) => other is not null && X == other.X && Y == other.Y;
    public override bool Equals(object? obj) => Equals(obj as Coord);
    public override int GetHashCode() => HashCode.Combine(X, Y);
}
```

Las tres partes son obligatorias: `Equals(object)` para colecciones no genéricas y `==` sobre `object`, `IEquatable<T>` para que `Dictionary` no haga *boxing*, y `GetHashCode` coherente con `Equals` (si dos objetos son iguales, sus hashes deben coincidir; lo contrario no hace falta).

**Segundo problema: los campos son públicos y mutables.** Aunque arregles la igualdad, si alguien hace `key.X = 9` después de insertarla, el hash almacenado ya no corresponde al cubo donde está y esa entrada queda perdida para siempre: ni `ContainsKey` ni `Remove` la encuentran, y sigue ocupando memoria. Las claves de un diccionario deben ser inmutables; el `readonly record struct` lo garantiza, la clase de arriba también (propiedades solo de lectura).

**Tercero, menor:** `public int X;` expone campos en vez de propiedades. No cambia el comportamiento aquí, pero rompe la encapsulación y el *data binding*. Las dos versiones de arriba lo corrigen de paso.

Prueba de regresión que fija las dos propiedades que necesitas:

```csharp
[Fact]
public void Equal_coords_are_the_same_key()
{
    var visited = new Dictionary<Coord, int> { [new Coord(1, 2)] = 5 };
    Assert.True(visited.ContainsKey(new Coord(1, 2)));
    Assert.Equal(new Coord(1, 2).GetHashCode(), new Coord(1, 2).GetHashCode());
}
```

Para detectar esto en revisión sin leer cada tipo: `CA1067` avisa cuando sobrescribes `Equals` sin implementar `IEquatable<T>`, y `CS0659` cuando sobrescribes `Equals` sin `GetHashCode`. Lo que ningún analizador avisa es «usas como clave una clase sin igualdad»; esa es la revisión humana.""",
            },
        ]
    },
    # 29) ImplicitUsings, global using, file-scoped namespace (multiturno, principiante)
    {
        "messages": [
            {"role": "user", "content": "Al crear un proyecto nuevo con `dotnet new console` no veo ningún `using System;` ni el `namespace X { }` con llaves que salía en los tutoriales. ¿Dónde está todo eso?"},
            {
                "role": "assistant",
                "content": r"""Tres cambios de C# 10 y el SDK de .NET 6 lo explican.

**1. `ImplicitUsings`.** El csproj trae `<ImplicitUsings>enable</ImplicitUsings>`, y con eso el SDK genera un archivo `GlobalUsings.g.cs` en `obj/` con los namespaces más comunes. Para `Microsoft.NET.Sdk`:

```csharp
global using global::System;
global using global::System.Collections.Generic;
global using global::System.IO;
global using global::System.Linq;
global using global::System.Net.Http;
global using global::System.Threading;
global using global::System.Threading.Tasks;
```

El SDK Web añade además `Microsoft.AspNetCore.Builder`, `Microsoft.Extensions.DependencyInjection`, `Microsoft.Extensions.Logging` y algunos más. Puedes verlo en `obj/Debug/net8.0/<Proyecto>.GlobalUsings.g.cs`.

**2. Top-level statements.** `Program.cs` ya no necesita `class Program` ni `static void Main`: el compilador los genera alrededor de las sentencias sueltas. `args` sigue disponible como variable implícita, y puedes usar `await` directamente.

```csharp
Console.WriteLine($"Hola, {args.FirstOrDefault() ?? "mundo"}");
```

Solo un archivo del proyecto puede tener sentencias de nivel superior.

**3. Namespaces de ámbito de archivo.** `namespace Shop.Core;` seguido de punto y coma aplica a todo el archivo, sin llaves ni un nivel de indentación:

```csharp
namespace Shop.Core;

public sealed record Product(int Id, string Name);
```

Es equivalente al bloque con llaves; la única limitación es que no puedes tener dos namespaces en el mismo archivo (que tampoco deberías).

Si abres un proyecto antiguo verás el estilo viejo; conviven sin problema. El IDE ofrece la conversión automática (`dotnet format` con la regla `csharp_style_namespace_declarations = file_scoped` en `.editorconfig`).""",
            },
            {"role": "user", "content": "Entendido. ¿Y cómo añado un using global para todo el proyecto, por ejemplo mi namespace de utilidades y el `Math` estático?"},
            {
                "role": "assistant",
                "content": r"""Dos formas equivalentes; elige una y no mezcles.

**En código:** un archivo `GlobalUsings.cs` en la raíz del proyecto con directivas `global using`:

```csharp
global using Shop.Core.Utils;
global using static System.Math;
global using Json = System.Text.Json.JsonSerializer;
```

- `global using static System.Math` permite escribir `Sqrt(x)` y `PI` sin prefijo en todo el proyecto.
- El alias `Json` evita repetir `JsonSerializer` por todas partes.
- Las directivas `global using` deben ir **antes** de cualquier `using` normal en ese archivo, y no pueden ir dentro de un namespace.

**En el csproj:** el mismo efecto, útil cuando quieres que sea parte de la configuración compartida (`Directory.Build.props`):

```xml
<ItemGroup>
  <Using Include="Shop.Core.Utils" />
  <Using Include="System.Math" Static="true" />
  <Using Include="System.Text.Json.JsonSerializer" Alias="Json" />
  <Using Remove="System.Net.Http" />
</ItemGroup>
```

`<Using Remove>` quita uno de los implícitos; se usa cuando un namespace implícito choca con un tipo tuyo (por ejemplo, tienes una clase `Timer` y `System.Threading.Timer` te la ambigua).

Dos criterios para no abusar:

1. Solo van a global los namespaces que usa **la mayoría** de los archivos. Un `global using` para algo que usan dos archivos oculta dependencias en vez de simplificar.
2. Los `using static` globales son los más peligrosos: `Sqrt` sin prefijo se lee bien, pero `Abs` o `Round` sin saber de dónde salen confunden a quien lee. Limítalos a uno o dos tipos.

Comprobación: tras añadir el archivo, borra un `using Shop.Core.Utils;` de cualquier archivo y compila; debe seguir funcionando. Si el IDE marca el `using` local como innecesario (atenuado), el global está activo.""",
            },
        ]
    },
    # 30) BackgroundService que no se detiene (código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Mi worker en .NET 8 tarda 30 segundos en parar cuando hago Ctrl+C o cuando Kubernetes manda SIGTERM, y en el log aparece `Hosting failed to stop gracefully`. El servicio:

```csharp
public class SyncWorker : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (true)
        {
            await SyncAsync();
            await Task.Delay(TimeSpan.FromSeconds(60));
        }
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""El worker **ignora `stoppingToken`**. Al recibir SIGTERM el host cancela ese token y espera a que `ExecuteAsync` termine; como tu bucle nunca lo mira y el `Task.Delay` no lo recibe, el host espera el `HostOptions.ShutdownTimeout` (30 s por defecto), se rinde y registra ese mensaje. En Kubernetes es peor: si el `terminationGracePeriodSeconds` del pod es igual o menor, el proceso muere a mitad de un `SyncAsync`.

Arreglo mínimo: pasar el token a todo lo que espere y salir limpiamente cuando se cancele.

```csharp
public sealed class SyncWorker(ISyncService sync, ILogger<SyncWorker> logger) : BackgroundService
{
    private static readonly TimeSpan Interval = TimeSpan.FromSeconds(60);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(Interval);
        try
        {
            do
            {
                await sync.RunAsync(stoppingToken);
            }
            while (await timer.WaitForNextTickAsync(stoppingToken));
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
            logger.LogInformation("SyncWorker detenido");
        }
    }
}
```

Qué cambia y por qué:

- **`PeriodicTimer` (.NET 6+)** en vez de `Task.Delay`: `WaitForNextTickAsync` devuelve `false` cuando el temporizador se desecha y lanza `OperationCanceledException` al cancelar el token, así que la espera de 60 s se corta en el instante. Además no acumula deriva: el siguiente tic se calcula desde el anterior, no desde que terminó `RunAsync`.
- **`stoppingToken` hacia dentro** de `RunAsync`: si la sincronización está a mitad de una petición HTTP o una consulta, también se cancela. Si hay un tramo que no debe interrumpirse (un commit), ese tramo concreto no recibe el token, pero el resto sí.
- **El `catch` con filtro** convierte la cancelación esperada en una salida normal y deja pasar cualquier otra excepción. En .NET 6+ una excepción no controlada en `ExecuteAsync` **detiene el host** (`BackgroundServiceExceptionBehavior.StopHost`), que suele ser lo correcto para un worker: mejor reinicio del contenedor que un proceso vivo que no hace nada.

Dos ajustes alrededor:

```csharp
builder.Services.Configure<HostOptions>(o =>
{
    o.ShutdownTimeout = TimeSpan.FromSeconds(15);   // menor que terminationGracePeriodSeconds
});
```

Y si `RunAsync` puede tardar más que ese margen, divide el trabajo en lotes y comprueba `stoppingToken.IsCancellationRequested` entre lote y lote, de modo que parar nunca cueste más que un lote.

Cómo verificar: `dotnet run`, espera un tic, pulsa Ctrl+C y mide. Debe apagarse en menos de un segundo con el mensaje «SyncWorker detenido» y sin el aviso de *failed to stop gracefully*. Para probarlo sin reloj real, `PeriodicTimer` acepta un `TimeProvider` en .NET 8 (`new PeriodicTimer(Interval, timeProvider)`), y `FakeTimeProvider` te deja avanzar el tiempo en el test.""",
            },
        ]
    },
]
