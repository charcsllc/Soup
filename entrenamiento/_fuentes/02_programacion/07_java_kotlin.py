"""Java 21 (records, sealed, pattern matching, virtual threads, Streams, JUnit 5, build, GC) y Kotlin 2.x
(null safety, data/sealed, extensiones, coroutines, Flow, delegación, interop). Mitad y mitad, con comparativas."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Java: records con validación, constructor compacto, "withers", cuándo no usar record
    {
        "messages": [
            {
                "role": "user",
                "content": "En Java 21, ¿puedo sustituir mis clases DTO con Lombok `@Value` por `record`? Tengo una `Money(amount, currency)` que valida que el importe no sea negativo y un método `plus`. ¿Cómo se hace la validación en un record?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, y para `Money` el `record` es mejor que `@Value`: te da `equals`, `hashCode`, `toString`, accesores y un constructor canónico sin generación de código externa, y el **constructor compacto** es el sitio para validar y normalizar.

```java
import java.math.BigDecimal;
import java.util.Currency;
import java.util.Objects;

public record Money(BigDecimal amount, Currency currency) {

    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        if (amount.signum() < 0) {
            throw new IllegalArgumentException("amount must not be negative: " + amount);
        }
        amount = amount.setScale(currency.getDefaultFractionDigits(), java.math.RoundingMode.HALF_EVEN);
    }

    public static Money of(String amount, String currencyCode) {
        return new Money(new BigDecimal(amount), Currency.getInstance(currencyCode));
    }

    public Money plus(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException("currency mismatch: " + currency + " vs " + other.currency);
        }
        return new Money(amount.add(other.amount), currency);
    }

    public Money withAmount(BigDecimal newAmount) {
        return new Money(newAmount, currency);
    }
}
```

Lo que conviene saber del constructor compacto:

- **No tiene paréntesis ni asigna los campos**: la asignación `this.amount = amount` la añade el compilador **al final**, después de tu código. Por eso reasignar el parámetro (`amount = amount.setScale(...)`) es la forma de normalizar: lo que se guarda es el valor modificado.
- **Toda vía de construcción pasa por él**, incluidos `of` y `withAmount`, así que un `Money` inválido no puede existir. Con Lombok, `@Value` + `@Builder` dejaba agujeros si alguien usaba el *builder* sin validación.
- **Los campos son `private final` y no hay setters**; un record es inmutable por construcción, salvo que un componente sea mutable (una `List` o un array), en cuyo caso copia en el constructor: `items = List.copyOf(items)`.

Los «withers» no existen en Java 21 (están en discusión como *derived record creation*); el método `withAmount` manual es la forma habitual, y para records de muchos campos se suele dejar solo los que de verdad cambian.

Diferencias con `@Value` que pueden afectarte:

| | `record` | Lombok `@Value` |
|---|---|---|
| accesores | `amount()` | `getAmount()` |
| herencia | no puede extender clases; sí implementar interfaces | igual, pero puede extender |
| `toString` | `Money[amount=1.00, currency=EUR]` | `Money(amount=1.00, currency=EUR)` |
| serialización | Jackson 2.12+ y Gson soportan records; JPA **no** (las entidades necesitan constructor sin argumentos y campos mutables) | igual limitación en JPA |
| *pattern matching* | `case Money(var a, var c) ->` | no |

Lo que **no** debe ser un record: entidades JPA, clases con identidad (dos usuarios con los mismos datos no son el mismo usuario), y cualquier cosa con estado mutable. Para DTOs, *value objects* y claves compuestas de maps, sí.

Comprobación con JUnit 5:

```java
@Test
void rejectsNegativeAndNormalizesScale() {
    assertThrows(IllegalArgumentException.class, () -> Money.of("-1", "EUR"));
    var m = Money.of("1.5", "EUR").plus(Money.of("0.25", "EUR"));
    assertEquals(new BigDecimal("1.75"), m.amount());
    assertEquals(Money.of("1.75", "EUR"), m); // equals por valor, incluida la escala normalizada
}
```

El último `assertEquals` es el que fallaría con `BigDecimal` sin normalizar (`1.75` y `1.750` no son `equals`); el `setScale` del constructor compacto lo garantiza para cualquier vía de creación.""",
            },
        ]
    },
    # 2) Java: sealed + pattern matching en switch, record patterns, guardas, exhaustividad
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo una jerarquía de eventos de pago con `instanceof` por todas partes:

```java
if (event instanceof PaymentAuthorized) {
    var e = (PaymentAuthorized) event;
    ...
} else if (event instanceof PaymentCaptured) {
    ...
} else if (event instanceof PaymentFailed) {
    ...
} else {
    throw new IllegalStateException("unknown event");
}
```

Me han dicho que con Java 21 esto se hace con `sealed` y `switch`. ¿Cómo queda y qué gano aparte de menos líneas?""",
            },
            {
                "role": "assistant",
                "content": r"""Lo que ganas de verdad es que el compilador comprueba la **exhaustividad**: si mañana añades `PaymentRefunded`, cada `switch` que no lo contemple deja de compilar, en vez de caer en un `else` que lanza en producción.

Primero, cierras la jerarquía:

```java
public sealed interface PaymentEvent
        permits PaymentAuthorized, PaymentCaptured, PaymentFailed {}

public record PaymentAuthorized(String paymentId, Money amount) implements PaymentEvent {}
public record PaymentCaptured(String paymentId, Money amount, Instant at) implements PaymentEvent {}
public record PaymentFailed(String paymentId, String reason, boolean retryable) implements PaymentEvent {}
```

`sealed` + `permits` dice que no hay más implementaciones que esas tres. Si están en el mismo archivo o paquete puedes omitir `permits` y el compilador las infiere; con `permits` explícito la lista queda documentada. Las implementaciones tienen que ser `final`, `sealed` o `non-sealed`; los records son `final` implícitamente.

Después, el `switch` con patrones:

```java
String describe(PaymentEvent event) {
    return switch (event) {
        case PaymentAuthorized(var id, var amount) ->
            "authorized %s for %s".formatted(id, amount);
        case PaymentCaptured(var id, var amount, var at) ->
            "captured %s for %s at %s".formatted(id, amount, at);
        case PaymentFailed f when f.retryable() ->
            "failed %s (%s), will retry".formatted(f.paymentId(), f.reason());
        case PaymentFailed f ->
            "failed %s permanently: %s".formatted(f.paymentId(), f.reason());
    };
}
```

Qué hay aquí:

- **Sin `default`**: el compilador verifica que las tres clases permitidas están cubiertas. Añade `PaymentRefunded` al `permits` y este método da «the switch expression does not cover all possible input values». Esa es la ganancia principal. Si pones `default`, la pierdes; no lo pongas en un `switch` sobre un tipo sellado.
- **Record patterns** (`PaymentAuthorized(var id, var amount)`) deconstruyen en el mismo `case`; se anidan (`PaymentCaptured(var id, Money(var value, var cur), var at)`).
- **Guardas con `when`**: el orden importa, el primer `case` que encaja gana, y el compilador rechaza un `case` inalcanzable (un `PaymentFailed f` antes del que tiene guarda daría «this case label is dominated by a preceding case label»).
- **`null`**: un `switch` con patrones lanza `NullPointerException` si `event` es `null`, salvo que añadas `case null ->`. Es mejor que el `instanceof`, que con `null` caía en el `else` y lanzaba un `IllegalStateException` engañoso.

Para un *handler* con efectos (no devuelve nada), la forma es la misma como sentencia:

```java
switch (event) {
    case PaymentAuthorized e -> ledger.hold(e.paymentId(), e.amount());
    case PaymentCaptured e -> ledger.settle(e.paymentId(), e.amount(), e.at());
    case PaymentFailed e -> alerts.notifyFailure(e.paymentId(), e.reason());
}
```

Desde Java 21, un `switch` **sentencia** sobre un tipo sellado con patrones también debe ser exhaustivo; el compilador lo exige igual que en la expresión.

Dos límites que conviene conocer antes de sellar todo:

1. **Las subclases tienen que estar en el mismo módulo** (o el mismo paquete si no usas módulos). Un tipo sellado no puede extenderse desde otro *jar*; es justo lo que quieres para eventos de dominio, y justo lo que no quieres para un punto de extensión de *plugins*.
2. **Frameworks de serialización**: Jackson necesita `@JsonTypeInfo`/`@JsonSubTypes` igual que antes; `sealed` no le dice nada al deserializador.

Comprobación de la exhaustividad en un test de compilación: añade temporalmente `record PaymentRefunded(String paymentId) implements PaymentEvent {}` al `permits` y ejecuta `./mvnw compile`; cada `switch` sin ese caso aparece en la lista de errores, que es exactamente el mapa de sitios que tendrías que tocar.""",
            },
        ]
    },
    # 3) Java: virtual threads, cuándo sí, pinning, no pool, ThreadLocal. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tenemos un servicio Spring Boot 3.3 con un `ThreadPoolTaskExecutor` de 200 hilos para llamadas a APIs externas, y aun así se nos queda sin hilos en picos. ¿Los hilos virtuales de Java 21 lo arreglan? ¿Hay algo que pueda salir mal al activarlos?",
            },
            {
                "role": "assistant",
                "content": r"""Para ese caso concreto (muchas llamadas bloqueantes de I/O con tiempos de espera largos) sí: los hilos virtuales están pensados exactamente para «un hilo por petición» sin que el número de hilos sea el límite. Un hilo de plataforma cuesta ~1 MB de pila reservada y un hilo del sistema operativo; un hilo virtual cuesta unos pocos KB en el *heap* y se desmonta del hilo portador (*carrier*) cada vez que bloquea en I/O, así que 10 000 llamadas en espera no ocupan 10 000 hilos del SO.

**Activarlo en Spring Boot 3.2+** es una propiedad:

```properties
spring.threads.virtual.enabled=true
```

Con eso Tomcat atiende cada petición en un hilo virtual y los `@Async`/`TaskExecutor` por defecto también. Para tu *executor* propio, sustituye el pool:

```java
@Bean
ExecutorService externalApiExecutor() {
    return Executors.newVirtualThreadPerTaskExecutor();
}
```

Fíjate en que **ya no hay número de hilos**: la concurrencia la limitas en otro sitio (un `Semaphore` si la API externa solo admite 50 llamadas simultáneas, o el `maxConnections` del cliente HTTP). Hacer un pool de hilos virtuales no tiene sentido; son baratos de crear y de tirar.

**Lo que puede salir mal**, en orden de probabilidad:

1. **Pinning por `synchronized`.** En Java 21, si un hilo virtual bloquea en I/O **dentro de un bloque o método `synchronized`**, no puede desmontarse y se queda clavado al *carrier*; con pocos *carriers* (por defecto, tantos como núcleos) eso te puede dejar sin paralelismo. Pasa con drivers JDBC antiguos y con código propio que sincroniza alrededor de una llamada de red. Diagnóstico: `-Djdk.tracePinnedThreads=full` imprime la pila cada vez que ocurre. Arreglo: `ReentrantLock` en vez de `synchronized` en ese sitio, o actualizar el driver. **En JDK 24 este problema desaparece** (JEP 491: `synchronized` ya no clava el hilo), así que si puedes subir de versión, es el camino más corto.
2. **Pools de conexión dimensionados para 200 hilos.** Con hilos virtuales puedes tener 5 000 peticiones en vuelo que compiten por 20 conexiones de HikariCP; el síntoma cambia de «sin hilos» a «timeout esperando conexión». No es peor, es más honesto: el cuello de botella real era la base de datos o la API externa, no el pool de hilos. Dimensiona el pool de conexiones y pon un `Semaphore` delante de la API externa.
3. **`ThreadLocal` usado como caché por hilo.** Con 200 hilos, 200 copias; con un hilo virtual por petición, una copia por petición que se crea y se tira. Funciona, pero si el objeto es caro (un `SimpleDateFormat`, un buffer grande) pierdes la amortización. Sustituye por un objeto compartido inmutable (`DateTimeFormatter`) o un pool explícito. El `ThreadLocal` del contexto de seguridad o de MDC funciona sin cambios.
4. **Código que depende de que haya pocos hilos.** Un `ExecutorService` de un solo hilo usado como «cola serializada» sigue funcionando (es un hilo de plataforma); lo que cambia es lo que corre en Tomcat.
5. **Trabajo intensivo en CPU.** Ahí los hilos virtuales no aportan nada: el *carrier* se ocupa igual. Para cálculo pesado, el pool de plataforma dimensionado a los núcleos sigue siendo lo correcto.

Cómo verificar que ha funcionado, antes y después:

```sh
# número de hilos de plataforma vivos (debería dejar de crecer con el tráfico)
jcmd <pid> Thread.print | grep -c 'java.lang.Thread.State'

# pinning durante una prueba de carga (Java 21)
java -Djdk.tracePinnedThreads=full -jar app.jar 2>&1 | grep -A5 'onPinned'
```

Y una prueba de carga con 2 000 peticiones concurrentes contra un *endpoint* que llama a la API externa con 500 ms de latencia: con el pool de 200, el p99 sube linealmente con la cola; con hilos virtuales, se queda cerca de los 500 ms hasta que te limite el semáforo o la API. Si no mejora, el tiempo no se iba en esperar hilos, y hay que mirar el perfil de la aplicación, no la configuración de hilos.""",
            },
        ]
    },
    # 4) Java Streams: "stream has already been operated upon", groupingBy, toList. Inglés, error pegado
    {
        "messages": [
            {
                "role": "user",
                "content": r"""I'm getting this in a report generator and I don't see why, the stream is used right there:

```
java.lang.IllegalStateException: stream has already been operated upon or closed
	at java.base/java.util.stream.AbstractPipeline.sourceStageSpliterator(AbstractPipeline.java:279)
	at java.base/java.util.stream.ReferencePipeline.forEach(ReferencePipeline.java:762)
	at com.acme.report.ReportService.build(ReportService.java:31)
```

```java
Stream<Order> orders = repo.findAll().stream().filter(o -> o.status() == PAID);
long count = orders.count();
Map<String, Double> byCustomer = orders.collect(
        Collectors.groupingBy(Order::customer, Collectors.summingDouble(Order::total)));
orders.forEach(o -> log.info("paid order {}", o.id()));
```""",
            },
            {
                "role": "assistant",
                "content": r"""A `Stream` is single-use: the first **terminal operation** (`count()`) consumes it, and every later terminal operation on the same object throws exactly that exception. Line 31 is the third one (`forEach`), but `collect` on the previous line would already have failed; the trace shows `forEach` only because that is the line your test or request reached first in this build.

The fix is to not hold the stream in a variable. Keep the **source** (the list) and build a fresh pipeline per result, or better, compute everything in one pass when the data is large:

```java
List<Order> paid = repo.findAll().stream()
        .filter(o -> o.status() == PAID)
        .toList();

long count = paid.size();
Map<String, Double> byCustomer = paid.stream().collect(
        Collectors.groupingBy(Order::customer, Collectors.summingDouble(Order::total)));
paid.forEach(o -> log.info("paid order {}", o.id()));
```

Why this shape:

- **`toList()`** (Java 16+) materializes once; the three consumers each get a cheap `List`. Note it returns an **unmodifiable** list, unlike `Collectors.toList()`, which returns an `ArrayList` in practice but does not promise it. Use `toList()` unless you need to mutate the result.
- Filtering once and reusing the list beats re-running the filter three times, and it makes the `count` and the `groupingBy` consistent (same snapshot), which matters if `repo.findAll()` could return different data on a second call.
- If `findAll()` is large enough that materializing is a problem, do the grouping in one `collect` and derive the count from it: `byCustomer.size()` is customers, and `paid.size()` is orders. For both numbers from a single pass, `Collectors.teeing(Collectors.counting(), Collectors.groupingBy(...), Pair::new)` runs two collectors over the same stream.

Two more things in that snippet worth changing while you are there:

1. **`summingDouble` on money** accumulates floating-point error. If `Order.total()` is a `BigDecimal` (it should be), use `Collectors.reducing(BigDecimal.ZERO, Order::total, BigDecimal::add)`.
2. **Logging inside `forEach`** on a stream is fine for a list, but if the source were a lazy stream from a database (`repo.streamAll()` with JPA), the side effect would interleave with the query and the resource would need `try-with-resources` to close the cursor.

A rule of thumb that prevents this class of bug: a `Stream` is a **statement**, not a value. If you ever write `Stream<T> x = ...;`, you are about to either reuse it or forget to consume it. Pass a `Supplier<Stream<T>>` when you really need to re-run a pipeline, and a `List`/`Collection` when you need a value.

Regression test:

```java
@Test
void buildUsesEachDerivedValueFromOneSnapshot() {
    var service = new ReportService(new InMemoryRepo(List.of(
            new Order("1", "ana", PAID, new BigDecimal("10.00")),
            new Order("2", "ana", PENDING, new BigDecimal("5.00")),
            new Order("3", "luis", PAID, new BigDecimal("2.50")))));

    var report = assertDoesNotThrow(service::build);
    assertEquals(2, report.count());
    assertEquals(new BigDecimal("10.00"), report.byCustomer().get("ana"));
}
```

With the original code this test fails on the `IllegalStateException` before any assertion runs.""",
            },
        ]
    },
    # 5) Java Optional: uso correcto, map/flatMap/orElseThrow, dónde no usarlo; multiturno
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Un compañero me dice que esto es «usar Optional como si fuera null» y que no aporta nada:

```java
Optional<User> user = userRepo.findByEmail(email);
if (user.isPresent()) {
    Optional<Address> addr = addressRepo.findPrimary(user.get().id());
    if (addr.isPresent()) {
        return addr.get().city();
    }
}
return "unknown";
```

¿Cómo lo escribiría él?""",
            },
            {
                "role": "assistant",
                "content": r"""Tiene razón: `isPresent()` + `get()` es un `null` check con más letras. `Optional` aporta cuando encadenas las transformaciones y resuelves la ausencia **una vez, al final**:

```java
return userRepo.findByEmail(email)
        .flatMap(user -> addressRepo.findPrimary(user.id()))
        .map(Address::city)
        .orElse("unknown");
```

Qué hace cada paso:

- `flatMap` cuando la función **devuelve otro `Optional`** (`findPrimary` lo hace). Con `map` tendrías `Optional<Optional<Address>>`.
- `map` cuando la función devuelve un valor normal (`city()` devuelve `String`). Si `city()` pudiera devolver `null`, `map` lo convierte en `Optional.empty()`; no explota.
- `orElse` cierra la cadena con el valor por defecto. Toda la ausencia (usuario que no existe, usuario sin dirección) cae al mismo sitio sin un `if` por nivel.

Los cierres que vas a necesitar, según el caso:

| Quieres... | Método |
|---|---|
| un valor por defecto ya calculado | `orElse(x)` |
| un valor por defecto caro de calcular | `orElseGet(() -> compute())` (solo se evalúa si está vacío) |
| lanzar si falta | `orElseThrow(() -> new NotFoundException(email))` o `orElseThrow()` (lanza `NoSuchElementException`) |
| hacer algo solo si está | `ifPresent(u -> ...)` |
| hacer algo en ambos casos | `ifPresentOrElse(u -> ..., () -> ...)` |
| probar otra fuente si está vacío | `or(() -> cacheRepo.findByEmail(email))` |
| convertir a stream para colecciones | `stream()` (vacío o un elemento) |

Un error frecuente con `orElse`: `opt.orElse(repo.loadDefault())` **siempre** ejecuta `loadDefault()`, esté o no vacío el `Optional`, porque el argumento se evalúa antes de la llamada. Si tiene efectos o cuesta, `orElseGet`.

Y cuándo **no** usar `Optional`, que es la otra mitad de lo que te decía tu compañero:

1. **Como campo de una clase o parámetro de método.** No es `Serializable`, complica `equals`, y un parámetro `Optional<String> name` obliga al llamador a envolver. Para parámetros opcionales, sobrecarga el método o usa un *builder*; para campos, `null` con `@Nullable` documentado.
2. **Como valor en colecciones.** `List<Optional<X>>` casi siempre debería ser una `List<X>` filtrada.
3. **Para evitar un `null` que nunca va a pasar.** Si `findById` por clave primaria en tu propio código siempre encuentra, devolver `Optional` traslada una comprobación inútil a todos los llamadores. `Optional` es para «puede legítimamente no haber resultado».

Comprobación de la versión encadenada con los tres caminos:

```java
@Test
void cityFallsBackToUnknownAtEachMissingLevel() {
    assertEquals("unknown", service.cityFor("nobody@x.io"));      // sin usuario
    assertEquals("unknown", service.cityFor("noaddr@x.io"));      // usuario sin dirección
    assertEquals("Lima", service.cityFor("ana@x.io"));            // completo
}
```""",
            },
            {"role": "user", "content": "¿Y si quiero distinguir «usuario no existe» (404) de «usuario sin dirección» (200 con ciudad vacía)? Con la cadena pierdo esa información."},
            {
                "role": "assistant",
                "content": r"""Cierto: en cuanto los dos vacíos caen al mismo `orElse` ya no se distinguen. La solución es **resolver el primer `Optional` donde su ausencia tiene un significado distinto**, y encadenar solo el resto:

```java
User user = userRepo.findByEmail(email)
        .orElseThrow(() -> new UserNotFoundException(email)); // 404

return addressRepo.findPrimary(user.id())
        .map(Address::city)
        .orElse("");                                             // 200 con ciudad vacía
```

Dos cadenas cortas, cada una con su propia política de ausencia. Es más claro que intentar meter ambas en una sola expresión con `map` anidados, y el lector ve de inmediato que «sin usuario» es un error y «sin dirección» no.

Si prefieres que el servicio no lance y devuelva un resultado tipado (por ejemplo para que el controlador decida el código HTTP), un `sealed interface` como resultado hace explícitos los tres casos:

```java
sealed interface CityLookup {
    record Found(String city) implements CityLookup {}
    record NoAddress() implements CityLookup {}
    record NoUser() implements CityLookup {}
}

CityLookup cityFor(String email) {
    return userRepo.findByEmail(email)
            .<CityLookup>map(user -> addressRepo.findPrimary(user.id())
                    .<CityLookup>map(a -> new CityLookup.Found(a.city()))
                    .orElseGet(CityLookup.NoAddress::new))
            .orElseGet(CityLookup.NoUser::new);
}
```

Y el controlador hace un `switch` exhaustivo sobre el resultado:

```java
return switch (service.cityFor(email)) {
    case CityLookup.Found f -> ResponseEntity.ok(f.city());
    case CityLookup.NoAddress na -> ResponseEntity.ok("");
    case CityLookup.NoUser nu -> ResponseEntity.notFound().build();
};
```

Los `<CityLookup>map(...)` con el tipo explícito hacen falta porque la inferencia de Java no unifica `Found` y `NoAddress` a la interfaz común por sí sola; es el precio de meter todo en una expresión, y por eso para dos niveles la versión con `orElseThrow` es la que escribiría yo. El `sealed` compensa cuando los casos son más de dos o cuando el mismo resultado lo consumen varios llamadores con políticas distintas.""",
            },
        ]
    },
    # 6) Java generics: invarianza, comodines, PECS, dónde no poner comodines
    {
        "messages": [
            {
                "role": "user",
                "content": "Nunca sé cuándo poner `? extends` y cuándo `? super` en Java. Tengo un método `double sumAll(List<Number> nums)` y no me deja pasarle una `List<Integer>`. ¿Por qué, si un Integer es un Number?",
            },
            {
                "role": "assistant",
                "content": r"""Porque los genéricos de Java son **invariantes**: `List<Integer>` no es subtipo de `List<Number>`, aunque `Integer` sí lo sea de `Number`. Y tiene que ser así; si el compilador lo permitiera, podrías corromper la lista:

```java
List<Integer> ints = new ArrayList<>(List.of(1, 2));
List<Number> nums = ints;      // supón que esto compilara
nums.add(3.14);                // un Double dentro de una lista de Integer
Integer last = ints.get(2);    // ClassCastException, lejos del error real
```

Los arrays sí son covariantes (`Integer[]` es un `Number[]`), y por eso el mismo caso con arrays falla en ejecución con `ArrayStoreException`. Los genéricos adelantan ese error a compilación.

Para decir «me vale una lista de `Number` o de cualquier subtipo» se usa un comodín. La regla para elegir es **PECS: *Producer Extends, Consumer Super***, mirando qué hace la colección desde el punto de vista de tu método:

- Si tu método **lee** de ella (la colección te *produce* valores) → `? extends T`.
- Si tu método **escribe** en ella (la colección *consume* tus valores) → `? super T`.
- Si hace las dos cosas → `T` exacto, sin comodín.

```java
import java.util.Collection;
import java.util.List;

final class Numbers {

    private Numbers() {}

    // Solo lee: acepta List<Integer>, List<Double>, Set<BigDecimal>...
    static double sumAll(Collection<? extends Number> nums) {
        double total = 0;
        for (Number n : nums) {
            total += n.doubleValue();
        }
        return total;
    }

    // Solo escribe Integer: acepta List<Integer>, List<Number>, List<Object>
    static void fillWithZeros(List<? super Integer> target, int count) {
        for (int i = 0; i < count; i++) {
            target.add(0);
        }
    }

    // Lee de src y escribe en dest: la misma forma que Collections.copy
    static <T> void copyInto(Collection<? super T> dest, Collection<? extends T> src) {
        dest.addAll(src);
    }
}
```

Qué te deja hacer cada declaración:

| Declaración | Leer | Escribir |
|---|---|---|
| `List<? extends Number>` | como `Number` | nada (salvo `null`) |
| `List<? super Integer>` | solo como `Object` | `Integer` |
| `List<Number>` | como `Number` | cualquier `Number` |

El «nada» de `? extends` sorprende al principio: el compilador no sabe si detrás hay una `List<Integer>` o una `List<Double>`, así que rechaza `add(1)` para no repetir el problema del primer ejemplo.

Ya lo usas sin saberlo en el JDK: `List.sort(Comparator<? super E> c)` es la razón de que puedas ordenar una `List<Integer>` con un `Comparator<Number>`.

Dos reglas prácticas más:

1. **Comodines en parámetros, no en tipos de retorno.** Devolver `List<? extends Number>` obliga a cada llamador a cargar con el comodín y no le deja añadir nada.
2. **Si el parámetro de tipo aparece una sola vez en la firma, usa comodín.** `void printAll(List<?> items)` dice lo mismo que `<T> void printAll(List<T> items)` con menos ruido.

Comprobación con JUnit 5:

```java
@Test
void wildcardsAcceptSubtypesAndSupertypes() {
    assertEquals(6.0, Numbers.sumAll(List.of(1, 2, 3)));
    assertEquals(2.0, Numbers.sumAll(List.of(0.5, 1.5)));

    List<Number> sink = new ArrayList<>();
    Numbers.fillWithZeros(sink, 2);        // una List<Number> consume Integer
    Numbers.copyInto(sink, List.of(7L));   // T = Long
    assertEquals(List.of(0, 0, 7L), sink);

    // Numbers.fillWithZeros(new ArrayList<Long>(), 1);  // no compila: Long no es supertipo de Integer
}
```""",
            },
        ]
    },
    # 7) Java checked vs unchecked: criterio, jerarquía de dominio sellada, IOException en lambdas
    {
        "messages": [
            {
                "role": "user",
                "content": "En el equipo hay discusión: unos quieren excepciones checked para los errores de negocio (`InsufficientStockException extends Exception`) y otros todo unchecked. Además, cuando uso `Files.readString` dentro de un `.map()` de un stream no compila por la IOException. ¿Qué criterio usarías para las dos cosas?",
            },
            {
                "role": "assistant",
                "content": r"""Criterio corto: **checked solo si el llamador inmediato puede y debe hacer algo distinto ante ese fallo; unchecked para todo lo demás**, incluidos los errores de negocio que se resuelven en un borde (un `@RestControllerAdvice`, un *handler* de mensajes).

Por qué los errores de negocio suelen acabar como unchecked:

1. **Casi nunca se recuperan donde se lanzan.** `InsufficientStockException` sale del dominio, atraviesa servicio y caso de uso, y termina convertida en un 409. Con checked, cada capa intermedia declara `throws` sin hacer nada con ella: ruido que acopla las firmas a detalles de las capas de abajo.
2. **No cruzan lambdas.** `Function`, `Supplier` y compañía no declaran excepciones, así que una checked no puede salir de un `map`. Es tu segundo problema, y es el mismo.
3. **Cambiar la lista de `throws` rompe a todos los llamadores**, lo que convierte un detalle interno en API pública.

Checked sigue teniendo sentido en librerías de bajo nivel donde el fallo es esperable y el llamador tiene una alternativa real (reintentar, usar otro fichero, pedir otra ruta). `IOException` es el ejemplo clásico.

Para el dominio: una jerarquía unchecked y sellada, y un único sitio que la traduce a HTTP.

```java
public abstract sealed class DomainException extends RuntimeException
        permits InsufficientStockException, OrderNotFoundException {
    protected DomainException(String message) {
        super(message);
    }
}

public final class InsufficientStockException extends DomainException {
    public InsufficientStockException(String sku, int requested, int available) {
        super("sku %s: requested %d, available %d".formatted(sku, requested, available));
    }
}

public final class OrderNotFoundException extends DomainException {
    public OrderNotFoundException(String orderId) {
        super("order not found: " + orderId);
    }
}
```

```java
@RestControllerAdvice
class DomainExceptionHandler {

    @ExceptionHandler(DomainException.class)
    ProblemDetail handle(DomainException ex) {
        HttpStatus status = switch (ex) {
            case InsufficientStockException e -> HttpStatus.CONFLICT;
            case OrderNotFoundException e -> HttpStatus.NOT_FOUND;
        };
        return ProblemDetail.forStatusAndDetail(status, ex.getMessage());
    }
}
```

Al ser sellada, el `switch` no necesita `default`: una excepción de dominio nueva sin código HTTP asignado no compila. La regla «checked para que nadie se olvide de tratarla» se cumple así mejor, en el único sitio donde de verdad se trata.

Para la `IOException` dentro del stream tienes dos opciones honestas:

- **Si el stream solo hace un `map`, usa un `for`.** Propaga la `IOException` sin trucos y es igual de legible.
- **Si el pipeline compensa**, envuelve en `UncheckedIOException` conservando la causa, y desenvuelve en el borde del método para que la firma siga siendo honesta:

```java
static List<String> readAll(List<Path> paths) throws IOException {
    try {
        return paths.stream()
                .map(path -> {
                    try {
                        return Files.readString(path);
                    } catch (IOException e) {
                        throw new UncheckedIOException("cannot read " + path, e);
                    }
                })
                .toList();
    } catch (UncheckedIOException e) {
        throw e.getCause(); // getCause() de UncheckedIOException devuelve IOException
    }
}
```

Lo que no haría: `catch (Exception e) { log.error(...); return null; }`, que convierte un fallo en un `NullPointerException` tres capas más arriba; `new RuntimeException(e.getMessage())`, que pierde la pila original; ni los trucos de *sneaky throw*, que lanzan una checked sin declararla y engañan al compilador y al lector.

Comprobación de que el envoltorio no cambia lo que ve el llamador:

```java
@Test
void readAllPropagatesTheOriginalIOException(@TempDir Path dir) {
    Path missing = dir.resolve("no-existe.txt");
    IOException ex = assertThrows(IOException.class, () -> TextFiles.readAll(List.of(missing)));
    assertInstanceOf(NoSuchFileException.class, ex);
}
```""",
            },
        ]
    },
    # 8) Java equals/hashCode: mutar un campo hasheado dentro de un HashSet. System variante (revisor)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala primero el problema más grave y después el resto, sin rodeos."},
            {
                "role": "user",
                "content": r"""Meto clientes en un `HashSet` y después les cambio el correo con `setEmail`. Luego `set.contains(cliente)` regresa `false` aunque es el mismo objeto, y `set.remove(cliente)` tampoco lo quita. ¿Qué onda?

```java
public class Customer {
    private String email;
    private String name;

    public Customer(String email, String name) {
        this.email = email;
        this.name = name;
    }

    public void setEmail(String email) { this.email = email; }

    @Override
    public boolean equals(Object o) {
        if (!(o instanceof Customer)) return false;
        Customer c = (Customer) o;
        return email.equals(c.email) && name.equals(c.name);
    }

    @Override
    public int hashCode() { return email.hashCode(); }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""**Grave: mutas un campo que participa en `hashCode` mientras el objeto está dentro de un `HashSet`.** Eso deja el elemento inalcanzable.

Cómo ocurre, paso a paso:

1. `add(c)` calcula `hashCode()` con el correo viejo y guarda el nodo en el *bucket* de ese hash. El nodo guarda también el hash calculado.
2. `setEmail(...)` cambia el correo. El nodo no se mueve: sigue en el *bucket* viejo, con el hash viejo.
3. `contains(c)` calcula el hash nuevo y busca en otro *bucket*; incluso si cayera en el mismo, compara primero el hash guardado y descarta el nodo. `remove` falla por lo mismo.

Resultado: el objeto sigue contando en `size()` y aparece al iterar, pero no se puede consultar ni borrar. En un set de larga vida es una fuga de memoria.

El código rompe el contrato de `hashCode`: mientras un objeto esté en una colección hash, los campos que usan `equals` y `hashCode` no pueden cambiar. La forma de cumplirlo sin depender de la disciplina de nadie es que esos campos sean inmutables.

**Arreglo:** un `record`, y cambiar el correo es sacar y volver a meter.

```java
import java.util.Locale;
import java.util.Objects;

public record Customer(String email, String name) {
    public Customer {
        Objects.requireNonNull(email, "email");
        Objects.requireNonNull(name, "name");
        email = email.strip().toLowerCase(Locale.ROOT);
    }

    public Customer withEmail(String newEmail) {
        return new Customer(newEmail, name);
    }
}
```

```java
customers.remove(current);
customers.add(current.withEmail("nuevo@empresa.mx"));
```

Si `Customer` es una entidad con identidad propia (sigue siendo el mismo cliente aunque cambie de correo), el correo no debe estar en `equals`: usa un identificador inmutable y guarda los clientes en un `Map<CustomerId, Customer>`.

**El resto, por orden de gravedad:**

- **`NullPointerException` en `equals` y `hashCode`** si `email` o `name` son `null`; el constructor no lo impide. Lo resuelve el `requireNonNull` del constructor compacto.
- **`equals` y `hashCode` usan campos distintos.** No es ilegal (dos objetos iguales comparten correo y, por tanto, hash), pero quien toque uno sin el otro rompe el contrato. El `record` genera los dos a partir de los mismos componentes.
- **Clase no `final` con `equals` basado en `instanceof`.** Una subclase que añada campos y sobrescriba `equals` rompe la simetría (`a.equals(b)` distinto de `b.equals(a)`). Un `record` es `final` implícitamente.
- **Correo sin normalizar.** `Ana@Empresa.mx` y `ana@empresa.mx` son el mismo buzón en la práctica; normalizar en el constructor evita duplicados que `equals` no ve.

Tests: el primero reproduce el bug con la clase original (renombrada `LegacyCustomer`), el segundo protege la nueva:

```java
@Test
void mutatingAHashedFieldLosesTheElement() {
    var legacy = new LegacyCustomer("a@empresa.mx", "Ana");
    Set<LegacyCustomer> set = new HashSet<>();
    set.add(legacy);
    legacy.setEmail("b@empresa.mx");

    assertFalse(set.contains(legacy)); // inalcanzable...
    assertEquals(1, set.size());       // ...pero sigue dentro
}

@Test
void replacedCustomerIsFoundByValue() {
    Set<Customer> set = new HashSet<>();
    var ana = new Customer("A@Empresa.mx", "Ana");
    set.add(ana);
    set.remove(ana);
    set.add(ana.withEmail("b@empresa.mx"));

    assertTrue(set.contains(new Customer("B@empresa.mx", "Ana")));
    assertEquals(1, set.size());
}
```""",
            },
        ]
    },
    # 9) Java CompletableFuture: fan-out con timeouts y degradación; multiturno sobre cancelación. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Para armar la ficha de producto llamo a tres servicios (precio, stock y reseñas) en serie y tarda 1,2 s. ¿Cómo los paralelizo con CompletableFuture? Si reseñas falla o tarda, quiero mostrar la ficha sin reseñas; si falla precio o stock, la ficha no se puede mostrar.",
            },
            {
                "role": "assistant",
                "content": r"""Lanza las tres llamadas a la vez, da a cada una su propia política de fallo y espera a todas con `allOf`. El tiempo total pasa a ser el de la más lenta en vez de la suma.

```java
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

public final class ProductPageService {

    private final PriceClient prices;
    private final StockClient stock;
    private final ReviewClient reviews;
    private final Executor ioExecutor;

    public ProductPageService(PriceClient prices, StockClient stock,
                              ReviewClient reviews, Executor ioExecutor) {
        this.prices = prices;
        this.stock = stock;
        this.reviews = reviews;
        this.ioExecutor = ioExecutor;
    }

    public ProductPage load(String sku) {
        CompletableFuture<Price> price = CompletableFuture
                .supplyAsync(() -> prices.priceFor(sku), ioExecutor)
                .orTimeout(800, TimeUnit.MILLISECONDS);
        CompletableFuture<Stock> available = CompletableFuture
                .supplyAsync(() -> stock.stockFor(sku), ioExecutor)
                .orTimeout(800, TimeUnit.MILLISECONDS);
        CompletableFuture<List<Review>> topReviews = CompletableFuture
                .supplyAsync(() -> reviews.topFor(sku), ioExecutor)
                .completeOnTimeout(List.of(), 500, TimeUnit.MILLISECONDS)
                .exceptionally(ex -> List.of());

        try {
            CompletableFuture.allOf(price, available, topReviews).join();
        } catch (CompletionException e) {
            throw new ProductPageUnavailableException(sku, e.getCause());
        }
        return new ProductPage(price.join(), available.join(), topReviews.join());
    }
}
```

`ProductPage` es un `record ProductPage(Price price, Stock stock, List<Review> reviews)` y `ProductPageUnavailableException` una `RuntimeException` con constructor `(String sku, Throwable cause)`.

Las decisiones que importan:

- **Executor propio, nunca el por defecto.** Sin segundo argumento, `supplyAsync` usa `ForkJoinPool.commonPool()`, dimensionado a núcleos − 1 y compartido con los *parallel streams* de toda la JVM. Llamadas HTTP bloqueantes ahí lo agotan. En Java 21, `Executors.newVirtualThreadPerTaskExecutor()` como *bean* es la opción natural para I/O.
- **Políticas distintas por dependencia.** Precio y stock usan `orTimeout` (Java 9+): si vencen, el futuro termina con `TimeoutException` y la ficha falla. Reseñas usa `completeOnTimeout` con lista vacía y `exceptionally` para errores: degrada en vez de fallar.
- **`allOf` + `join` individual.** `allOf` devuelve `CompletableFuture<Void>`; los valores se leen después con `join()`, que ya no bloquea porque todos han terminado. Si alguno falló, `allOf(...).join()` lanza `CompletionException` y lo traduces una sola vez.
- **`orTimeout` no cancela la llamada en curso.** El futuro se da por fallido, pero el hilo sigue esperando la respuesta HTTP. Configura también el *timeout* del cliente HTTP; si no, acumulas peticiones huérfanas bajo carga.

Comprobación: con dependencias falsas de 300 ms cada una, en serie tardaría más de 600 ms; en paralelo debe quedar cerca de 300.

```java
@Test
void loadsInParallelAndDegradesWithoutReviews() {
    PriceClient prices = sku -> { pause(300); return new Price("19.99"); };
    StockClient stock = sku -> { pause(300); return new Stock(3); };
    ReviewClient reviews = sku -> { throw new IllegalStateException("reviews down"); };

    try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
        var service = new ProductPageService(prices, stock, reviews, exec);
        ProductPage page = assertTimeoutPreemptively(Duration.ofMillis(500), () -> service.load("sku-1"));
        assertEquals(List.of(), page.reviews());
    }
}

private static void pause(long millis) {
    try {
        Thread.sleep(millis);
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new IllegalStateException(e);
    }
}
```""",
            },
            {
                "role": "user",
                "content": "Vale. ¿Y si el cliente cierra la conexión? Leí que `cancel(true)` en un CompletableFuture no interrumpe nada, así que las tres llamadas siguen vivas.",
            },
            {
                "role": "assistant",
                "content": r"""Es correcto: en `CompletableFuture`, el parámetro `mayInterruptIfRunning` de `cancel` se ignora. El futuro pasa a estado cancelado, pero el hilo que ejecuta `priceFor` no recibe ninguna interrupción y la llamada sigue hasta que el servidor responda o salte su *timeout*.

Si necesitas cancelación real, usa `ExecutorService.submit`, cuyos `Future` sí interrumpen el hilo con `cancel(true)`, y cancela en un `finally`:

```java
public ProductPage load(String sku, Duration budget) throws InterruptedException {
    try (ExecutorService exec = Executors.newVirtualThreadPerTaskExecutor()) {
        Future<Price> price = exec.submit(() -> prices.priceFor(sku));
        Future<Stock> available = exec.submit(() -> stock.stockFor(sku));
        Future<List<Review>> topReviews = exec.submit(() -> reviews.topFor(sku));
        long deadline = System.nanoTime() + budget.toNanos();
        try {
            Price p = price.get(remaining(deadline), TimeUnit.NANOSECONDS);
            Stock s = available.get(remaining(deadline), TimeUnit.NANOSECONDS);
            List<Review> r = getOrDefault(topReviews, deadline, List.of());
            return new ProductPage(p, s, r);
        } catch (ExecutionException | TimeoutException e) {
            throw new ProductPageUnavailableException(sku, e);
        } finally {
            price.cancel(true);
            available.cancel(true);
            topReviews.cancel(true);
        }
    }
}

private static long remaining(long deadline) {
    return Math.max(0, deadline - System.nanoTime());
}

private static <T> T getOrDefault(Future<T> future, long deadline, T fallback)
        throws InterruptedException {
    try {
        return future.get(remaining(deadline), TimeUnit.NANOSECONDS);
    } catch (ExecutionException | TimeoutException e) {
        return fallback;
    }
}
```

Por qué funciona:

1. **El `finally` cancela siempre.** `cancel(true)` sobre un futuro ya terminado no hace nada, así que es seguro llamarlo en todos los caminos: éxito, fallo, *timeout* o interrupción.
2. **La interrupción llega al hilo virtual que hace la llamada.** `HttpClient.send` declara `InterruptedException` y aborta la espera al ser interrumpido. Un cliente que no responda a interrupciones seguirá vivo hasta su propio *timeout*, por eso ese *timeout* sigue siendo obligatorio.
3. **El `try-with-resources` del `ExecutorService`** (Java 19+) espera a que terminen las tareas al cerrar. Como ya las has cancelado, la espera es corta y ningún hilo sobrevive a la petición.
4. **Un único presupuesto de tiempo** (`deadline`) reparte el *timeout* entre las tres esperas, en vez de sumar tres *timeouts* independientes.

Para que el cliente que cierra la conexión dispare todo esto, el hilo de la petición tiene que ser interrumpido: `get` lanza `InterruptedException`, el `finally` cancela, y la excepción sube. Por eso el método la declara en vez de tragársela.

En Java 21 existe `StructuredTaskScope`, que hace exactamente este patrón de forma declarativa, pero sigue en *preview* y su API ha cambiado entre versiones; no lo usaría en producción hasta que sea estable.

Comprobación: un `PriceClient` falso que registre la interrupción.

```java
@Test
void cancelsPendingCallsWhenTheBudgetExpires() throws Exception {
    var interrupted = new CountDownLatch(1);
    PriceClient slowPrices = sku -> {
        try {
            Thread.sleep(5_000);
        } catch (InterruptedException e) {
            interrupted.countDown();
            Thread.currentThread().interrupt();
        }
        return new Price("0");
    };
    var service = new ProductPageService(slowPrices, sku -> new Stock(1), sku -> List.of());

    assertThrows(ProductPageUnavailableException.class,
            () -> service.load("sku-1", Duration.ofMillis(100)));
    assertTrue(interrupted.await(1, TimeUnit.SECONDS));
}
```

Este servicio ya no recibe el `Executor` en el constructor, porque crea uno por petición.""",
            },
        ]
    },
    # 10) JUnit 5: tests parametrizados (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "tengo como diez tests casi iguales para validar un `PasswordPolicy.isValid(String)`, uno por cada caso, todos copy-paste. ¿hay forma en JUnit 5 de no repetir tanto?",
            },
            {
                "role": "assistant",
                "content": r"""Sí: **tests parametrizados**. Escribes el test una vez y JUnit lo ejecuta una vez por cada fila de datos, reportando cada caso por separado. Vienen en `junit-jupiter-params`, que ya está incluido si dependes del artefacto agregado `org.junit.jupiter:junit-jupiter`.

Para que el ejemplo compile completo, esta es una política mínima (longitud, dígito, minúscula y mayúscula):

```java
public final class PasswordPolicy {

    private final int minLength;

    public PasswordPolicy(int minLength) {
        this.minLength = minLength;
    }

    public boolean isValid(String candidate) {
        if (candidate == null || candidate.isBlank() || candidate.length() < minLength) {
            return false;
        }
        boolean hasDigit = candidate.chars().anyMatch(Character::isDigit);
        boolean hasLower = candidate.chars().anyMatch(Character::isLowerCase);
        boolean hasUpper = candidate.chars().anyMatch(Character::isUpperCase);
        return hasDigit && hasLower && hasUpper;
    }
}
```

Y los diez tests se convierten en esto:

```java
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

class PasswordPolicyTest {

    private final PasswordPolicy policy = new PasswordPolicy(12);

    @ParameterizedTest(name = "[{index}] {0} -> {1}")
    @CsvSource({
        "Correcto-Caballo-9, true",
        "corto1!,            false",
        "sinnumeros-Largos,  false",
        "SINMINUSCULAS-123,  false",
        "sinmayusculas-123,  false",
    })
    void appliesEachRule(String candidate, boolean expected) {
        assertEquals(expected, policy.isValid(candidate));
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   ", "\t"})
    void rejectsBlankInput(String candidate) {
        assertFalse(policy.isValid(candidate));
    }
}
```

Qué hace cada pieza:

- **`@CsvSource`**: cada cadena es una fila; las columnas se convierten solas al tipo del parámetro (`"true"` → `boolean`). Los espacios alrededor de cada valor se recortan, así que puedes alinear las columnas para leerlas mejor.
- **`name = "[{index}] {0} -> {1}"`**: el nombre que verás en el informe. Cuando falle una fila, sabrás cuál sin abrir el código.
- **`@NullAndEmptySource`** añade `null` y `""`; combinado con `@ValueSource` cubres todos los casos «vacíos» con un solo método.

Cuando los datos no caben en texto (objetos, listas), usa `@MethodSource` apuntando a un método `static` que devuelva `Stream<Arguments>`:

```java
static Stream<Arguments> policiesAndPasswords() {
    return Stream.of(
            Arguments.of(new PasswordPolicy(8), "Corto-1a", true),
            Arguments.of(new PasswordPolicy(16), "Corto-1a", false));
}

@ParameterizedTest
@MethodSource("policiesAndPasswords")
void lengthDependsOnPolicy(PasswordPolicy custom, String candidate, boolean expected) {
    assertEquals(expected, custom.isValid(candidate));
}
```

(Esos dos necesitan `import java.util.stream.Stream;`, `org.junit.jupiter.params.provider.Arguments` y `org.junit.jupiter.params.provider.MethodSource`.)

Un consejo: no metas en la misma tabla casos que prueban cosas distintas. Una tabla por regla («longitud», «caracteres requeridos», «entrada vacía») hace que, cuando algo falle, el nombre del método ya te diga qué regla se rompió.

Comprobación: `./mvnw test -Dtest=PasswordPolicyTest` debe reportar 9 ejecuciones (5 del CSV + 4 de entradas vacías), cada una con su nombre. Si cambias `"corto1!"` a `true`, falla solo la fila `[2]`, y el resto sigue en verde.""",
            },
        ]
    },
    # 11) Maven: NoSuchMethodError por conflicto de versiones transitivas. Inglés, error pegado
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Our service compiles fine and unit tests pass, but on staging it crashes right after startup with:

```
java.lang.NoSuchMethodError: 'void com.google.common.base.Preconditions.checkArgument(boolean, java.lang.String, java.lang.Object)'
	at com.acme.billing.InvoiceValidator.validate(InvoiceValidator.java:42)
```

We use Maven and we never call that method directly from anything weird. What's going on?""",
            },
            {
                "role": "assistant",
                "content": r"""`NoSuchMethodError` almost always means **the code was compiled against one version of a library and is running against another**. `checkArgument(boolean, String, Object)` was added in Guava 20; whatever Guava is on the staging classpath is older than that, while your compile classpath had a newer one.

Two hypotheses, and how to tell them apart:

**A. Maven resolved an old Guava for your build.** Maven's dependency mediation is *nearest wins*, not *highest wins*: if some library you depend on directly pulls Guava 19 at depth 2, and the Guava 33 you expect arrives at depth 3, you get 19. Tests pass because they never execute line 42, or because the test classpath differs.

```sh
./mvnw dependency:tree -Dincludes=com.google.guava:guava
```

If the tree shows something like `guava:jar:19.0:compile` reached through another artifact, that is your answer.

**B. The runtime environment adds its own Guava.** An application server, a shared lib directory, or an agent can put another copy ahead of yours. Check which jar the class actually came from on staging:

```sh
java -verbose:class -jar app.jar 2>&1 | grep 'com.google.common.base.Preconditions '
# [class,load] com.google.common.base.Preconditions source: file:/opt/shared/lib/guava-18.0.jar
```

The `source:` path settles it: your fat jar means A, anything outside it means B.

**Fix for A**: pin the version once in `dependencyManagement`, which overrides mediation for every transitive path:

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.google.guava</groupId>
      <artifactId>guava</artifactId>
      <version>33.3.1-jre</version>
    </dependency>
  </dependencies>
</dependencyManagement>
```

Then make the build fail the next time this happens, instead of staging:

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-enforcer-plugin</artifactId>
  <version>3.5.0</version>
  <executions>
    <execution>
      <id>enforce-dependency-versions</id>
      <goals>
        <goal>enforce</goal>
      </goals>
      <configuration>
        <rules>
          <requireUpperBoundDeps/>
        </rules>
      </configuration>
    </execution>
  </executions>
</plugin>
```

`requireUpperBoundDeps` fails when the resolved version of a dependency is lower than what some other dependency in the tree asked for, which is exactly the situation that produces this error. On a large project it will flag several existing conflicts at once; fix them one by one with the same `dependencyManagement` pin.

**Fix for B**: don't rely on the host's copy. Either remove it from the shared classpath, or, if you cannot control the environment, relocate Guava inside your jar with the shade plugin's `relocations` so the two copies cannot collide.

Two things worth knowing for later:

- **Gradle behaves differently**: it picks the highest requested version by default, so the same project could work under Gradle and fail under Maven.
- **Excluding Guava from the offending library** also works, but only if that library runs correctly on the newer version; check its changelog, because Guava has removed deprecated APIs over the years.

Verification: after pinning, `dependency:tree -Dincludes=com.google.guava:guava` shows a single version, `./mvnw verify` passes the enforcer, and a CI step that starts the packaged jar and hits a health endpoint would have caught this before staging. That last step is the real regression test, since unit tests run on a classpath that is not the one you ship.""",
            },
        ]
    },
    # 12) JVM en contenedores: OOMKilled vs OutOfMemoryError, ergonomía, G1 vs ZGC. Multiturno, system variante
    {
        "messages": [
            {"role": "system", "content": "Responde de forma concisa y técnica."},
            {
                "role": "user",
                "content": "Nuestro servicio Java 21 en Kubernetes (límite de 2 GiB) muere con OOMKilled, pero la JVM nunca lanza OutOfMemoryError. Arrancamos con `java -jar app.jar`, sin flags. ¿Por dónde empiezo?",
            },
            {
                "role": "assistant",
                "content": r"""`OOMKilled` no lo decide la JVM: es el kernel matando el contenedor porque **la memoria total del proceso** superó el límite del cgroup. El *heap* es solo una parte; por eso no ves `OutOfMemoryError`.

Memoria de una JVM: heap + metaspace + code cache + pilas de hilos + buffers directos (NIO, Netty) + estructuras del GC + memoria nativa de librerías.

Sin flags, Java 21 lee el límite del contenedor y fija el heap máximo en el 25 % (`MaxRAMPercentage=25`), unos 512 MiB. Si aun así os matan, hay dos hipótesis:

**1. Alguien sí fija el heap.** Puede venir de `JAVA_TOOL_OPTIONS`, `JDK_JAVA_OPTIONS` o del `ENTRYPOINT` de la imagen base. La JVM avisa al arrancar con `Picked up JAVA_TOOL_OPTIONS: ...`. Compruébalo dentro del pod (la JVM suele ser el PID 1):

```sh
jcmd 1 VM.flags | tr ' ' '\n' | grep -E 'MaxHeapSize|MaxRAMPercentage|Use.*GC'
```

Si la imagen es solo JRE y no trae `jcmd`, `java -XX:+PrintFlagsFinal -version | grep -E 'MaxHeapSize|Use.*GC'` con el mismo entorno da los mismos valores.

**2. Memoria nativa fuera del heap.** Arranca con *Native Memory Tracking* y compara bajo carga:

```sh
java -XX:NativeMemoryTracking=summary -jar app.jar
jcmd 1 VM.native_memory summary
```

- `Java Heap` cerca del límite → hipótesis 1.
- `Thread` grande → demasiados hilos de plataforma (un pool sin tope).
- `Other` creciendo sin parar → `ByteBuffer.allocateDirect` o Netty sin liberar; acótalo con `-XX:MaxDirectMemorySize`.

Configuración base razonable para 2 GiB:

```sh
java -XX:MaxRAMPercentage=75 \
     -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps \
     -jar app.jar
```

El porcentaje sigue al límite si alguien lo cambia en el *deployment*; `/dumps` debe ser un volumen, o el volcado desaparece con el pod. Dejar ~25 % fuera del heap (unos 500 MiB) es lo mínimo sensato para un servicio Spring típico.""",
            },
            {
                "role": "user",
                "content": "Era lo primero: alguien había puesto -Xmx2g en el Dockerfile. Ya está corregido. Otra duda: ¿G1 o ZGC para una API con objetivo de p99 de 50 ms?",
            },
            {
                "role": "assistant",
                "content": r"""Con `-Xmx2g` y 2 GiB de límite no quedaba nada para lo no-heap: el kernel mataba el proceso en cuanto el heap crecía.

Para el GC: **empieza con G1 y mide; cambia a ZGC solo si los logs muestran pausas que se comen el presupuesto.**

| | G1 (por defecto) | ZGC generacional |
|---|---|---|
| Pausas típicas con ~1,5 GiB | pocos ms a decenas de ms | < 1 ms |
| CPU / *throughput* | mejor | más CPU en hilos concurrentes |
| Memoria | menos margen necesario | necesita heap libre; si no, *allocation stalls* |
| Activación en Java 21 | nada | `-XX:+UseZGC -XX:+ZGenerational` |

Desde JDK 23 el modo generacional de ZGC es el predeterminado y en JDK 24 se eliminó el no generacional; en Java 21 hace falta el segundo flag.

Antes de comparar, comprueba qué GC tienes de verdad. Si el pod tiene límite de **1 CPU**, la JVM no se considera «máquina servidor» y elige **SerialGC**, con pausas que paran toda la aplicación. El `Use.*GC` del comando anterior lo muestra. Con 1 CPU, pide al menos 2 o fija `-XX:+UseG1GC` explícitamente.

Medición:

```sh
java -XX:MaxRAMPercentage=75 \
     -Xlog:gc*:file=/var/log/app/gc.log:time,uptime,level,tags \
     -jar app.jar

grep -E 'Pause (Young|Full)' /var/log/app/gc.log | tail -n 20
```

Criterio:

- Pausas jóvenes de G1 < 10 ms y ningún `Pause Full` → el GC no es tu problema de latencia; busca en otro sitio (pool de conexiones, llamadas externas).
- Pausas > 30 ms frecuentes o algún `Pause Full` → prueba ZGC en un pod canario con el mismo tráfico y compara p99 de la API y CPU.

No bajes `MaxGCPauseMillis` a 50 a ciegas: G1 lo cumple haciendo colecciones más frecuentes y menos eficientes, y puedes empeorar el *throughput* sin mejorar el p99.""",
            },
        ]
    },
    # 13) Java inmutabilidad y colecciones no modificables (principiante, voseo)
    {
        "messages": [
            {
                "role": "user",
                "content": "Che, hice `List<String> roles = List.of(\"admin\");` y después `roles.add(\"user\")` me tira `UnsupportedOperationException`. ¿No era que las List eran mutables? ¿Cuándo uso List.of, Arrays.asList o new ArrayList?",
            },
            {
                "role": "assistant",
                "content": r"""`List` es una interfaz: dice qué operaciones existen, no que todas las implementaciones las permitan. `add` está documentado como «operación opcional», y `List.of` devuelve una lista **no modificable** que lanza `UnsupportedOperationException` ante cualquier cambio. Es a propósito.

Las cuatro formas que vas a ver, y qué permite cada una:

| Cómo la creás | `add`/`remove` | `set` | Acepta `null` | Ligada a otra cosa |
|---|---|---|---|---|
| `new ArrayList<>(...)` | sí | sí | sí | no, es una copia |
| `Arrays.asList(...)` | no (tamaño fijo) | sí | sí | sí: escribe en el array original |
| `List.of(...)` / `List.copyOf(...)` | no | no | no (`NullPointerException`) | no |
| `Collections.unmodifiableList(x)` | no | no | sí | sí: es una **vista** de `x` |

Regla práctica:

- **¿La vas a modificar?** `new ArrayList<>(List.of("admin"))`.
- **¿Es un valor fijo o un resultado que nadie debe tocar?** `List.of(...)` o `stream().toList()`.
- **¿Recibís una lista de afuera y la guardás?** `List.copyOf(...)`.
- **`Arrays.asList`**: solo para adaptar un array existente; su tamaño fijo y su escritura en el array confunden.

La trampa de `unmodifiableList` es que **no es inmutable**, solo impide modificar a través de ella:

```java
List<String> source = new ArrayList<>(List.of("ana"));
List<String> view = Collections.unmodifiableList(source);
source.add("luis");
System.out.println(view); // [ana, luis]  ← la "lista no modificable" cambió
```

Por eso, para que una clase sea realmente inmutable, copiá en el constructor:

```java
import java.util.List;

public final class Team {

    private final String name;
    private final List<String> members;

    public Team(String name, List<String> members) {
        this.name = name;
        this.members = List.copyOf(members); // copia defensiva y no modificable
    }

    public String name() {
        return name;
    }

    public List<String> members() {
        return members; // se puede devolver tal cual: nadie puede cambiarla
    }
}
```

Con `List.copyOf`, ni quien te pasó la lista ni quien la recibe de `members()` puede alterar el estado del `Team`. Y si alguien te pasa una lista con un `null`, falla en el constructor, cerca del error, no tres pantallas más lejos. Si `members` ya venía de `List.of`, `copyOf` no copia: devuelve la misma instancia, así que no pagás nada extra.

Comprobación:

```java
@Test
void teamIsNotAffectedByChangesToTheOriginalList() {
    List<String> input = new ArrayList<>(List.of("ana"));
    Team team = new Team("core", input);
    input.add("luis");

    assertEquals(List.of("ana"), team.members());
    assertThrows(UnsupportedOperationException.class, () -> team.members().add("eva"));
}
```""",
            },
        ]
    },
    # 14) Java colecciones: LRU con LinkedHashMap, SequencedMap (Java 21), concurrencia
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito una caché LRU sencilla en memoria, máximo 1000 entradas, para un servicio Java 21. ¿Hace falta meter Caffeine o hay algo en el JDK que sirva?",
            },
            {
                "role": "assistant",
                "content": r"""Para una LRU con límite de tamaño, el JDK basta: `LinkedHashMap` en **orden de acceso** más `removeEldestEntry`. Caffeine compensa cuando necesitas expiración por tiempo, estadísticas o mucha concurrencia.

```java
import java.util.LinkedHashMap;
import java.util.Map;

public final class LruCache<K, V> {

    private final Map<K, V> entries;

    public LruCache(int maxEntries) {
        if (maxEntries <= 0) {
            throw new IllegalArgumentException("maxEntries must be positive: " + maxEntries);
        }
        // accessOrder = true: cada get mueve la entrada al final (la más reciente)
        this.entries = new LinkedHashMap<>(16, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
                return size() > maxEntries;
            }
        };
    }

    public synchronized V get(K key) {
        return entries.get(key);
    }

    public synchronized void put(K key, V value) {
        entries.put(key, value);
    }

    public synchronized int size() {
        return entries.size();
    }
}
```

Lo que no es obvio:

1. **El tercer argumento del constructor (`true`) es el que lo convierte en LRU.** Con el valor por defecto (`false`) el orden es de inserción y tendrías una FIFO.
2. **`removeEldestEntry` se consulta después de cada `put`.** Devolver `true` expulsa la primera entrada, que en orden de acceso es la usada hace más tiempo.
3. **En orden de acceso, `get` modifica la estructura**: mueve la entrada al final. Por eso un `ReadWriteLock` con lecturas concurrentes **no** sirve aquí; dos `get` simultáneos corrompen la lista enlazada. Hace falta exclusión total, como el `synchronized` de arriba.
4. **`synchronized` y los hilos virtuales de Java 21**: el bloqueo solo cubre operaciones en memoria de microsegundos, sin I/O dentro, así que no hay *pinning* relevante. No metas la carga del valor (la llamada a base de datos) dentro del `synchronized`.

Java 21 añadió `SequencedMap`, que `LinkedHashMap` implementa: `firstEntry()` te da la próxima víctima de la expulsión y `lastEntry()` la más reciente, útil para depurar o exponer métricas sin iterar.

Cuándo pasar a Caffeine (`com.github.ben-manes.caffeine:caffeine`):

- Expiración por tiempo (`expireAfterWrite`) o carga automática (`LoadingCache`).
- Mucho tráfico concurrente: el bloqueo global de esta versión serializa todos los accesos, mientras que Caffeine usa buffers y un algoritmo (W-TinyLFU) con mejor tasa de acierto que una LRU pura.
- Necesitas evitar que diez hilos carguen la misma clave a la vez.

Comparación rápida de los mapas del JDK para elegir en otros casos:

| Mapa | Orden | `get`/`put` | Concurrencia |
|---|---|---|---|
| `HashMap` | ninguno | O(1) | no |
| `LinkedHashMap` | inserción o acceso | O(1) | no |
| `TreeMap` | por clave | O(log n) | no |
| `ConcurrentHashMap` | ninguno | O(1) | sí, sin bloqueo global |

Test de la política de expulsión:

```java
@Test
void evictsTheLeastRecentlyUsedEntry() {
    var cache = new LruCache<String, Integer>(2);
    cache.put("a", 1);
    cache.put("b", 2);
    cache.get("a");     // "a" pasa a ser la más reciente
    cache.put("c", 3);  // expulsa "b", no "a"

    assertNull(cache.get("b"));
    assertEquals(1, cache.get("a"));
    assertEquals(3, cache.get("c"));
    assertEquals(2, cache.size());
}
```

Con `accessOrder = false`, este test falla en la primera aserción: se habría expulsado `"a"`.""",
            },
        ]
    },
    # 15) Kotlin null safety para quien viene de Java. System exacto, principiante
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Vengo de Java y en Kotlin me sale todo el rato un type mismatch de `String?` contra `String`. Al final acabo poniendo `!!` en todos lados para que compile. ¿Cómo se trabaja bien con los nulos en Kotlin?",
            },
            {
                "role": "assistant",
                "content": r"""Cada `!!` que pones es un `NullPointerException` aplazado: le dices al compilador «confía en mí» justo donde te estaba avisando. La idea de Kotlin es que la nulabilidad forma parte del tipo: `String` nunca es `null`, `String?` puede serlo, y el compilador te obliga a decidir qué pasa en el caso `null` **en el punto donde aparece**.

Las herramientas, de más a menos frecuentes:

```kotlin
data class User(val name: String, val email: String?)

// ?. : si es null, toda la cadena da null
fun domainOf(user: User): String? =
    user.email?.substringAfter('@')?.lowercase()

// ?: (Elvis): valor por defecto, o salir de la función
fun greeting(user: User?): String {
    val name = user?.name ?: return "Hola, invitado"
    return "Hola, $name" // aquí name ya es String, no String?
}

// smart cast: después de comprobar, el compilador sabe que no es null
fun emailLength(user: User): Int {
    if (user.email == null) return 0
    return user.email.length
}
```

El caso que más confunde: el *smart cast* **no funciona con propiedades `var`**, porque otro hilo podría cambiarlas entre la comprobación y el uso. La solución es copiar a un `val` local:

```kotlin
class Session {
    var token: String? = null

    fun authHeader(): String {
        val current = token ?: error("not logged in") // error() lanza IllegalStateException
        return "Bearer $current"
    }
}
```

Cuándo usar cada salida si el `null` es inesperado:

| Situación | Qué escribir | Lanza |
|---|---|---|
| Argumento inválido del llamador | `requireNotNull(x) { "x is required" }` | `IllegalArgumentException` |
| Estado interno roto | `checkNotNull(x) { "..." }` o `?: error("...")` | `IllegalStateException` |
| Seguro al 100 % y obvio en la misma línea | `!!` | `NullPointerException` sin mensaje |

Las dos primeras dejan un mensaje que explica qué falló; `!!` solo deja una línea en la traza. Si te descubres escribiendo `!!`, pregúntate si el tipo debería ser no nulable desde el origen. Casi siempre el problema está arriba: un campo declarado `String?` «por si acaso», o un valor que llega de Java.

Otras dos piezas:

- **`lateinit var`** para propiedades que se inicializan después de construir el objeto (inyección de dependencias, `@BeforeEach` en tests). Si se lee antes de asignarse, lanza `UninitializedPropertyAccessException` con el nombre de la propiedad, mucho más claro que un NPE.
- **Valores que vienen de Java** tienen «tipo de plataforma» (`String!`): Kotlin no sabe si pueden ser `null` y no te obliga a comprobar. Declara tú el tipo al recibirlos (`val name: String? = javaUser.getName()`) o anota el código Java con `@Nullable`/`@NonNull` para que Kotlin lo sepa.

Comprobación con `kotlin.test`:

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class NullSafetyTest {
    @Test
    fun domainIsNullWhenEmailIsMissing() {
        assertNull(domainOf(User("Ana", null)))
        assertEquals("x.io", domainOf(User("Ana", "ana@X.io")))
    }

    @Test
    fun guestGreetingWhenUserIsNull() {
        assertEquals("Hola, invitado", greeting(null))
        assertEquals("Hola, Ana", greeting(User("Ana", null)))
    }
}
```

Un buen indicador de progreso: busca `!!` en tu proyecto (`grep -rn '!!' src/`). Cada uno que elimines cambiando un tipo o usando `?:` es un fallo en producción que el compilador detectará por ti.""",
            },
        ]
    },
    # 16) Kotlin data class: qué genera, propiedades del cuerpo, copy superficial, cuándo no usarla, value class
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Qué genera exactamente una `data class` en Kotlin y cuándo no debería usarla? En el proyecto las usamos para todo, hasta para las entidades de JPA.",
            },
            {
                "role": "assistant",
                "content": r"""Genera, **solo a partir de las propiedades del constructor primario**: `equals`/`hashCode`, `toString`, `componentN()` (para desestructurar) y `copy()`. Lo que declares en el cuerpo de la clase no participa en nada de eso, y es la primera trampa:

```kotlin
data class Order(val id: String, val items: List<Item>) {
    var status: Status = Status.NEW
}

val a = Order("o-1", emptyList())
val b = a.copy().apply { status = Status.PAID }
println(a == b)            // true: status no cuenta para equals
println(b.copy().status)   // NEW: copy() solo copia el constructor primario
```

Tres reglas para que una data class se comporte como un valor:

1. **Todo el estado que define el valor va en el constructor primario.** Si `status` importa para la igualdad, va ahí: `data class Order(val id: String, val items: List<Item>, val status: Status = Status.NEW)`.
2. **`val`, no `var`.** Una data class con `var` dentro de un `HashSet` o como clave de un `Map` se pierde al mutarla, porque su `hashCode` cambia.
3. **`copy()` es superficial.** Si una propiedad es una `MutableList`, la copia y el original comparten la misma lista. Usa tipos de solo lectura (`List`) y construye listas nuevas al «modificar».

Cuándo **no** usarla:

- **Entidades JPA.** Una entidad tiene identidad: es el mismo pedido aunque cambie su estado, así que su igualdad debe basarse en el id, no en todos los campos. Además, el `equals`/`hashCode`/`toString` generados recorren las relaciones: con relaciones *lazy* disparan consultas o `LazyInitializationException`, y con relaciones bidireccionales `toString` entra en recursión infinita. Usa una `class` normal (con los plugins `kotlin-jpa` y `kotlin-spring`, que generan el constructor sin argumentos y abren las clases) e implementa `equals` por id.
- **Clases con comportamiento e invariantes complejas.** `copy()` crea instancias nuevas con cualquier combinación de valores. El bloque `init` sí se ejecuta en `copy()`, pero si validas en una fábrica con constructor `private`, históricamente `copy()` era pública y se la saltaba. Desde Kotlin 2.0.20 hay un ciclo de deprecación para que `copy()` tenga la visibilidad del constructor; puedes adelantarlo con `@ConsistentCopyVisibility`.
- **Envoltorios de un solo campo** (ids tipados): ahí es mejor una `value class`, que en la mayoría de usos no reserva objeto y evita confundir un `OrderId` con un `CustomerId`:

```kotlin
@JvmInline
value class OrderId(val value: String) {
    init {
        require(value.startsWith("o-")) { "invalid order id: $value" }
    }
}

data class Order(
    val id: OrderId,
    val items: List<Item>,
    val status: Status = Status.NEW,
)
```

Donde una data class encaja de verdad: DTOs, eventos, resultados de funciones, configuración, claves compuestas de mapas. Valores inmutables cuya identidad es su contenido.

Comprobación de la versión corregida:

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals

class OrderTest {
    @Test
    fun statusTakesPartInEqualityAndCopy() {
        val pending = Order(OrderId("o-1"), emptyList())
        val paid = pending.copy(status = Status.PAID)

        assertNotEquals(pending, paid)
        assertEquals(Status.PAID, paid.copy().status)
    }

    @Test
    fun invalidIdIsRejected() {
        assertFailsWith<IllegalArgumentException> { OrderId("123") }
    }
}
```""",
            },
        ]
    },
    # 17) Kotlin sealed + when exhaustivo, data object; multiturno comparando con Java 21
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un proceso de importación con estados (sin empezar, procesando con progreso, terminado con número de filas, error). ¿Cómo lo modelo en Kotlin para que el compilador me obligue a tratar todos los estados en cada sitio?",
            },
            {
                "role": "assistant",
                "content": r"""Con una jerarquía sellada y `when` sin `else`. Cada estado lleva solo los datos que tiene sentido que lleve:

```kotlin
sealed interface ImportState {
    data object Idle : ImportState
    data class Running(val processed: Int, val total: Int) : ImportState
    data class Done(val rows: Int) : ImportState
    data class Failed(val error: Throwable) : ImportState
}

fun describe(state: ImportState): String = when (state) {
    ImportState.Idle -> "sin empezar"
    is ImportState.Running -> "procesando ${state.processed}/${state.total}"
    is ImportState.Done -> "terminado: ${state.rows} filas"
    is ImportState.Failed -> "error: ${state.error.message}"
}
```

Qué te da cada pieza:

- **`sealed`**: el compilador conoce todas las implementaciones (tienen que estar en el mismo módulo y el mismo paquete). Si añades `data class Paused(...)`, cada `when` sin esa rama deja de compilar. Esa lista de errores es el mapa de sitios que tienes que revisar.
- **Sin `else`**. Un `else` hace que el `when` compile siempre y te devuelve al punto de partida: el estado nuevo cae en una rama genérica en silencio.
- **Smart cast**: dentro de `is ImportState.Running ->`, `state` ya es `Running` y accedes a `processed` sin conversiones.
- **`data object`** (Kotlin 1.9+) para estados sin datos: `toString()` imprime `Idle` en vez de `ImportState$Idle@1b6d3586`, y `equals` es el esperado incluso tras serializar.
- **También en sentencias.** Desde Kotlin 1.7, un `when` usado como sentencia sobre un tipo sellado, un `enum` o un `Boolean` también debe ser exhaustivo; antes solo era un aviso.

`sealed interface` frente a `sealed class`: la interfaz permite que un tipo pertenezca a varias jerarquías selladas y no impone constructor común; la clase te deja compartir estado o lógica en el padre. Para estados como estos, la interfaz basta.

Un patrón que encaja bien es que las transiciones también sean funciones totales:

```kotlin
fun ImportState.advance(batch: Int): ImportState = when (this) {
    ImportState.Idle -> error("cannot advance an import that has not started")
    is ImportState.Running -> {
        val processed = (processed + batch).coerceAtMost(total)
        if (processed == total) ImportState.Done(total) else copy(processed = processed)
    }
    is ImportState.Done, is ImportState.Failed -> this
}
```

Comprobación:

```kotlin
@Test
fun advancingToTheTotalFinishesTheImport() {
    val state = ImportState.Running(processed = 90, total = 100).advance(20)
    assertEquals(ImportState.Done(100), state)
    assertEquals("terminado: 100 filas", describe(state))
}
```""",
            },
            {
                "role": "user",
                "content": "En la parte Java del proyecto (Java 21) también tenemos sealed + switch con patrones. En la práctica, ¿qué diferencias hay entre los dos?",
            },
            {
                "role": "assistant",
                "content": r"""La idea es la misma (jerarquía cerrada + comprobación de exhaustividad); cambian la forma de extraer datos, el tratamiento de `null` y algunos detalles de ubicación.

| | Kotlin 2.x | Java 21 |
|---|---|---|
| Exhaustividad | `when` expresión y sentencia (desde 1.7) | `switch` expresión y `switch` con patrones como sentencia |
| Extraer datos | *smart cast* y acceso a propiedades | *record patterns* anidados: `case Running(var p, var t)` |
| Condiciones extra | guardas en `when` (`is Running if state.total == 0 ->`), estables desde Kotlin 2.2 | `case Running r when r.total() == 0 ->` |
| `null` | lo resuelve el tipo: `ImportState` no admite `null`; con `ImportState?` el compilador exige la rama `null ->` | `NullPointerException` salvo que añadas `case null ->` |
| Estados sin datos | `data object` | un `record` sin componentes o un `enum` aparte |
| Dónde viven los subtipos | mismo módulo y mismo paquete | mismo módulo (o mismo paquete sin módulos) |

Lo que más se nota al escribir código:

1. **Deconstrucción.** Java tiene patrones de deconstrucción y Kotlin no: en Kotlin escribes `is Running -> state.processed`. Para jerarquías planas da igual; con estructuras anidadas (`case Done(Report(var rows, var warnings))`), Java es más compacto.
2. **`null`.** En Kotlin el `null` no entra en el `when` si el tipo no es nulable, así que no hay caso olvidado. En Java un `switch` sobre un valor `null` lanza `NullPointerException` antes de evaluar ningún `case`; si el valor puede venir nulo, `case null` es obligatorio de facto.
3. **Interoperabilidad.** Si Java tiene que hacer un `switch` exhaustivo sobre la jerarquía Kotlin, comprueba que el bytecode lleve el atributo `PermittedSubclasses` (`javap -v ImportState.class | grep -A4 PermittedSubclasses`). Si no aparece, para `javac` la interfaz no está sellada y te exigirá `default`. En ese caso define la jerarquía compartida en Java: Kotlin entiende los tipos sellados de Java y comprueba la exhaustividad en su `when`.

Para lógica de dominio que vive en un solo lenguaje, las dos versiones son equivalentes en seguridad. La única regla común que importa: **nunca `else` ni `default` sobre un tipo sellado**, porque desactivan justo la comprobación por la que lo sellaste.""",
            },
        ]
    },
    # 18) Kotlin extension functions: despacho estático, miembros ganan, receptor nulable, Java. System rioplatense
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo."},
            {
                "role": "user",
                "content": "Las extension functions de Kotlin, ¿son métodos de verdad? Hice `fun String.isEmail()` y me pregunto si puedo sobrescribirla en una subclase, si tiene costo y cómo se ve desde Java.",
            },
            {
                "role": "assistant",
                "content": r"""No son métodos de verdad: son **funciones estáticas** con el receptor como primer parámetro y una sintaxis que las hace parecer miembros. De eso se deriva todo lo demás.

Tu función:

```kotlin
// archivo StringExtensions.kt
package com.acme.text

private val EMAIL = Regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")

fun String.isEmail(): Boolean = EMAIL.matches(this)
```

se compila, en esencia, a:

```java
public final class StringExtensionsKt {
    public static boolean isEmail(String receiver) { ... }
}
```

Consecuencias prácticas:

**1. No hay polimorfismo: se elige por el tipo declarado.** No podés «sobrescribirla» en una subclase:

```kotlin
open class Shape
class Circle : Shape()

fun Shape.name() = "shape"
fun Circle.name() = "circle"

fun printName(s: Shape) = println(s.name())

printName(Circle()) // imprime "shape": manda el tipo del parámetro, no el del objeto
```

Si necesitás que cada subtipo responda distinto, eso es un método miembro (`open fun name()`), no una extensión.

**2. Si existe un miembro con la misma firma, gana el miembro.** Una extensión `fun String.trim()` nunca se va a llamar; el compilador te avisa con «extension is shadowed by a member». Ojo cuando una librería agrega un método nuevo con el mismo nombre que tu extensión: tu código pasa a llamar al de ellos sin que cambies nada.

**3. No acceden a lo privado.** Solo ven la API pública (o `internal` del mismo módulo) del receptor. No rompen el encapsulamiento.

**4. Costo: el de una llamada estática.** Sin objeto intermedio, sin reflexión. Si además la marcás `inline` y recibe una lambda, ni siquiera hay llamada.

**5. Receptor nulable**, algo que con un método miembro es imposible:

```kotlin
fun String?.orDash(): String = if (this.isNullOrBlank()) "-" else this
```

`null.orDash()` funciona y devuelve `"-"`. La propia librería estándar hace esto con `isNullOrBlank()`.

**Desde Java** se llama como lo que es: `StringExtensionsKt.isEmail(email)`. Para un nombre más presentable, poné `@file:JvmName("Strings")` en la primera línea del archivo (antes del `package`) y queda `Strings.isEmail(email)`.

Cuándo usarlas:

- Para **leer mejor** operaciones sobre tipos que no son tuyos (`String`, `LocalDate`, tipos de una librería): `fecha.isWeekend()` en vez de `DateUtils.isWeekend(fecha)`.
- Para **acotar** utilidades a un contexto: una extensión `private` o declarada dentro de una clase solo existe ahí y no ensucia el autocompletado del resto del proyecto.

Cuándo no: para lógica central de tu propio dominio. Si `Order` es tuyo, `order.total()` va como miembro; repartir su comportamiento entre extensiones en cinco archivos hace difícil encontrarlo.

Prueba rápida que documenta el despacho estático y la validación:

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ExtensionsTest {
    @Test
    fun emailValidation() {
        assertTrue("ana@acme.com".isEmail())
        assertFalse("ana@acme".isEmail())
        assertFalse("ana @acme.com".isEmail())
    }

    @Test
    fun dispatchUsesTheDeclaredType() {
        val shape: Shape = Circle()
        assertEquals("shape", shape.name())
        assertEquals("-", null.orDash())
    }
}
```""",
            },
        ]
    },
    # 19) Kotlin coroutines: concurrencia limitada con Semaphore, semántica de fallo, CancellationException
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que enriquecer unos 5.000 registros llamando a una API que admite máximo 20 peticiones concurrentes. Hice `ids.forEach { scope.launch { api.fetch(it) } }` y la API me devuelve 429 a montones. Además no tengo claro qué pasa si una de las llamadas falla: ¿se cancelan las otras? Estoy con kotlinx.coroutines 1.9.",
            },
            {
                "role": "assistant",
                "content": r"""Tu código lanza las 5.000 corrutinas a la vez, y cada una dispara su petición en cuanto arranca: no hay nada que limite la concurrencia. Las corrutinas son baratas; lo que hay que limitar es **cuántas están dentro de la llamada a la API**. Para eso, un `Semaphore` de corrutinas:

```kotlin
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit

interface CustomerApi {
    suspend fun fetch(id: String): Customer
}

data class Customer(val id: String)

class Enricher(
    private val api: CustomerApi,
    maxConcurrency: Int = 20,
) {
    private val permits = Semaphore(maxConcurrency)

    suspend fun enrichAll(ids: List<String>): List<Customer> = coroutineScope {
        ids.map { id ->
            async { permits.withPermit { api.fetch(id) } }
        }.awaitAll()
    }
}
```

Por qué así:

- **`withPermit`** suspende (no bloquea un hilo) hasta que hay permiso y lo libera al salir, también si la llamada lanza. Nunca hay más de 20 llamadas en vuelo.
- **El semáforo es un campo de `Enricher`**, no una variable local: si dos peticiones de tu servicio llaman a `enrichAll` a la vez, comparten el mismo límite, que es lo que exige la API.
- **`coroutineScope` en vez de un `scope` externo**: la función no devuelve hasta que terminan todas sus corrutinas hijas. Con `scope.launch` la función retornaba al instante y las llamadas seguían vivas sin dueño.

**Qué pasa si una falla.** Dentro de `coroutineScope`, la primera excepción **cancela a todas las hermanas** y se relanza desde `enrichAll`. Es lo correcto si el resultado parcial no sirve. Si quieres los que salieron bien y un registro de los que fallaron, captura dentro de cada `async`:

```kotlin
import kotlin.coroutines.cancellation.CancellationException

suspend fun <T> attempt(block: suspend () -> T): Result<T> =
    try {
        Result.success(block())
    } catch (e: CancellationException) {
        throw e // la cancelación no es un fallo: hay que dejarla pasar
    } catch (e: Exception) {
        Result.failure(e)
    }

suspend fun Enricher.enrichAllTolerant(
    api: CustomerApi,
    ids: List<String>,
): Map<String, Result<Customer>> = coroutineScope {
    ids.map { id -> async { id to attempt { enrichOne(api, id) } } }
        .awaitAll()
        .toMap()
}
```

donde `enrichOne` es el `permits.withPermit { api.fetch(id) }` expuesto como método. El detalle importante es el `catch (e: CancellationException) { throw e }`. **No uses `runCatching` en código de corrutinas**: captura `Throwable`, incluida la `CancellationException`, y una corrutina cancelada sigue ejecutándose como si nada, convirtiendo la cancelación en un «fallo» más del mapa.

Dos ajustes según tu cliente HTTP:

- Si `fetch` es bloqueante (un SDK sin `suspend`), envuelve la llamada en `withContext(Dispatchers.IO) { ... }` dentro del `withPermit`.
- Para los 429 que aún lleguen (otros clientes comparten la cuota), reintenta respetando la cabecera `Retry-After` con `delay`, dentro del permiso, para no soltarlo y volver a la cola.

Comprobación con `kotlinx-coroutines-test`. El tiempo es virtual, así que 500 llamadas de 100 ms no tardan nada:

```kotlin
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.max
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest

class FakeApi : CustomerApi {
    private val inFlight = AtomicInteger()
    val maxInFlight = AtomicInteger()

    override suspend fun fetch(id: String): Customer {
        val now = inFlight.incrementAndGet()
        maxInFlight.updateAndGet { max(it, now) }
        delay(100)
        inFlight.decrementAndGet()
        return Customer(id)
    }
}

class EnricherTest {
    @Test
    fun neverExceedsTheConcurrencyLimit() = runTest {
        val api = FakeApi()
        val result = Enricher(api, maxConcurrency = 20).enrichAll((1..500).map { "c-$it" })

        assertEquals(500, result.size)
        assertEquals(20, api.maxInFlight.get())
    }
}
```

Con tu versión original, `maxInFlight` llegaría a 500.""",
            },
        ]
    },
    # 20) Kotlin Flow: frío vs caliente, stateIn/shareIn, WhileSubscribed; multiturno con test en tiempo virtual
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un repositorio que expone `fun prices(): Flow<Price>` y por dentro hace polling a una API cada 5 segundos. Cuando dos consumidores lo recogen, la API recibe el doble de peticiones. ¿Por qué? Pensaba que el Flow era uno solo.",
            },
            {
                "role": "assistant",
                "content": r"""Porque `Flow` es **frío**: el bloque `flow { ... }` no se ejecuta al crearlo, sino **cada vez que alguien llama a `collect`**, y cada colector tiene su propia ejecución independiente. Dos colectores, dos bucles de polling. Es el mismo comportamiento que una función: definirla no la ejecuta, y cada llamada es una ejecución nueva.

Lo que necesitas es convertirlo en un flujo **caliente** compartido: una sola ejecución del productor, cuyos valores reciben todos los colectores. Para eso existen `stateIn` y `shareIn`:

```kotlin
import kotlin.time.Duration.Companion.seconds
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.retry
import kotlinx.coroutines.flow.stateIn
import java.io.IOException

interface PriceApi {
    suspend fun latestPrice(): Price
}

class PriceRepository(
    private val api: PriceApi,
    externalScope: CoroutineScope,
) {
    private val polling: Flow<Price> = flow {
        while (true) {
            emit(api.latestPrice())
            delay(5.seconds)
        }
    }

    val prices: StateFlow<Price?> = polling
        .retry(3) { cause -> cause is IOException }
        .stateIn(
            scope = externalScope,
            started = SharingStarted.WhileSubscribed(stopTimeoutMillis = 5_000),
            initialValue = null,
        )
}
```

Las piezas:

- **`stateIn`** arranca el productor una vez en `externalScope` y guarda el último valor. Todos los colectores ven el mismo.
- **`WhileSubscribed(5_000)`** arranca el polling con el primer colector y lo para 5 s después de que se vaya el último. Así no haces peticiones cuando nadie escucha, y un colector que se reconecta enseguida (una pantalla que rota, un cliente que reintenta) no reinicia el ciclo.
- **`externalScope`** debe vivir tanto como el repositorio (el de la aplicación o el del componente que lo posee), no el de una petición; si ese scope se cancela, el flujo compartido muere con él.
- **Es una propiedad, no una función.** Si dejas `fun prices() = polling.stateIn(...)`, cada llamada crea un flujo compartido nuevo y vuelves al problema.

Cuál de los tres usar:

| | `Flow` | `SharedFlow` (`shareIn`) | `StateFlow` (`stateIn`) |
|---|---|---|---|
| Ejecución | una por colector | una compartida | una compartida |
| Valor actual | no | opcional (`replay`) | siempre (`.value`) |
| Valores repetidos | se emiten | se emiten | se descartan (`distinctUntilChanged`) |
| Uso típico | consultas, transformaciones | eventos (notificaciones, comandos) | estado (el precio actual) |

Para un precio, `StateFlow` es lo natural: interesa el último valor y no repetir el mismo dos veces. Para eventos que no deben perderse ni fusionarse (por ejemplo «pedido creado»), `SharedFlow`.""",
            },
            {
                "role": "user",
                "content": "Perfecto. ¿Y cómo lo testeo sin esperar 5 segundos reales y comprobando que de verdad se hace una sola petición por intervalo?",
            },
            {
                "role": "assistant",
                "content": r"""Con `runTest` de `kotlinx-coroutines-test`: el `delay` usa tiempo virtual que tú avanzas a mano, y `backgroundScope` hace de `externalScope` (se cancela solo al terminar el test, así que el bucle infinito no lo deja colgado).

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.Duration.Companion.seconds
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest

class CountingPriceApi : PriceApi {
    var calls = 0
        private set

    override suspend fun latestPrice(): Price {
        calls++
        return Price(calls.toBigDecimal())
    }
}

class PriceRepositoryTest {
    @Test
    fun twoCollectorsShareOnePollingLoop() = runTest {
        val api = CountingPriceApi()
        val repo = PriceRepository(api, backgroundScope)

        val first = mutableListOf<Price?>()
        val second = mutableListOf<Price?>()
        backgroundScope.launch { repo.prices.toList(first) }
        backgroundScope.launch { repo.prices.toList(second) }

        runCurrent()                 // t = 0: suscripciones y primera petición
        assertEquals(1, api.calls)

        advanceTimeBy(5.seconds)     // ejecuta lo programado antes de t = 5 s
        runCurrent()                 // ejecuta lo programado justo en t = 5 s
        assertEquals(2, api.calls)

        assertEquals(first.last(), second.last())
    }
}
```

Asumo `data class Price(val amount: BigDecimal)`.

Lo que hay que entender para que el test sea fiable:

1. **`runCurrent()`** ejecuta todo lo que está listo en el instante virtual actual. Lo necesitas después de lanzar los colectores, porque `launch` solo programa.
2. **`advanceTimeBy(5.seconds)`** ejecuta las tareas programadas **antes** de t = 5 s, no las que caen exactamente en t = 5 s. Por eso va seguido de otro `runCurrent()`. Es la causa más común de «el test espera 2 y recibe 1».
3. **El valor que discrimina es `calls`**: con la versión sin compartir, tras el primer `runCurrent()` valdría 2, y 4 tras el segundo intervalo. El test falla justo con el bug que querías evitar.

Si quieres probar también que el polling se detiene sin colectores, cancela los dos `launch` (guarda los `Job`), avanza 5 s más 1 ms, y comprueba que `calls` no sigue creciendo al avanzar otros 10 s. Esa es la garantía de `WhileSubscribed` que te protege de hacer peticiones cuando nadie escucha.""",
            },
        ]
    },
    # 21) Kotlin scope functions: tabla, cadenas de let anidados, trampa de ?.let ?: run. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "Kotlin scope functions: let, run, with, apply, also. I keep mixing them up, and my reviewer says my nested `?.let { }` chains are unreadable. Is there a simple rule for picking one?",
            },
            {
                "role": "assistant",
                "content": r"""Yes. They differ on only two axes: **how you refer to the object** inside the block (`this` or `it`) and **what the call returns** (the object itself or the block's result).

| Function | Object inside | Returns | Typical use |
|---|---|---|---|
| `apply` | `this` | the object | configure an object you just created |
| `also` | `it` | the object | side effect in a chain (logging, validation) |
| `let` | `it` | block result | transform a value, often after `?.` |
| `run` | `this` | block result | compute a result from an object's members |
| `with(x)` | `this` | block result | same as `run`, for a non-null value you already have |

The simple rule: **if you want the object back, `apply` or `also`; if you want a new value, `let` or `run`.** Then pick `this` when you will call many members, `it` when the object is an argument to something else.

```kotlin
val client = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(5))
    .build()
    .also { log.info("http client ready: {}", it.version()) }

val request = Request(url).apply {
    header("Accept", "application/json")
    timeout = 10.seconds
}

val port = System.getenv("PORT")?.let { it.toIntOrNull() } ?: 8080
```

(The `Request` type here is illustrative; `apply` works on any object with mutable members.)

Now your nested chains. This pattern:

```kotlin
user?.let { u ->
    u.address?.let { a ->
        a.city?.let { c ->
            println(c.uppercase())
        }
    }
}
```

is just a safe-call chain written the long way:

```kotlin
user?.address?.city?.uppercase()?.let(::println)
```

or, when the rest of the function depends on that value, an early return reads best:

```kotlin
val city = user?.address?.city ?: return
println(city.uppercase())
```

Scope functions are not a replacement for `if`, early returns, or plain local variables. If a block is longer than a few lines, or you need two scope functions nested, a named `val` is almost always clearer.

One trap worth knowing, because it causes real bugs: **`?.let { } ?: run { }` is not an if/else.**

```kotlin
val previous = cache[key]?.let { cache.put(key, it.refreshed()) } ?: run {
    log.warn("missing key {}", key)
}
```

`cache.put` on a `MutableMap` returns the *previous* value, which may be `null`. When it is, the `let` block evaluates to `null`, so the Elvis operator runs the `run` block as well, logging "missing key" for a key that was present. Write it as an `if`:

```kotlin
val current = cache[key]
if (current != null) {
    cache[key] = current.refreshed()
} else {
    log.warn("missing key {}", key)
}
```

Quick check of the trap:

```kotlin
@Test
fun letElvisRunsBothBranchesWhenLetReturnsNull() {
    var elseRan = false
    val value: String? = "present"
    value?.let { null } ?: run { elseRan = true }
    assertTrue(elseRan) // the value was present, but the "else" ran anyway
}
```""",
            },
        ]
    },
    # 22) Kotlin colecciones: Sequence vs List, inline, cuándo compensa; operaciones útiles
    {
        "messages": [
            {
                "role": "user",
                "content": "Un compañero pone `.asSequence()` delante de todas las cadenas de `filter`/`map` en Kotlin «porque es más rápido». ¿Es verdad? ¿Cuándo conviene usar Sequence?",
            },
            {
                "role": "assistant",
                "content": r"""No siempre; a menudo es al revés. Depende de cuántos elementos hay, cuántos pasos tiene la cadena y si la operación final puede terminar antes de recorrerlo todo.

**Cómo evalúa cada uno:**

- **`List`** (*eager*): cada paso recorre la colección entera y crea una lista intermedia. `filter` → lista nueva, `map` → otra lista nueva.
- **`Sequence`** (*lazy*): procesa elemento a elemento a través de toda la cadena, sin listas intermedias, y solo cuando una operación terminal (`toList`, `first`, `count`) lo pide.

Se ve con una traza:

```kotlin
val result = listOf(1, 2, 3, 4)
    .asSequence()
    .map { println("map $it"); it * 2 }
    .first { println("check $it"); it > 4 }
// map 1, check 2, map 2, check 4, map 3, check 6  -> result = 6
```

Con `List` verías `map 1..4` completos antes del primer `check`: el cuarto elemento se transforma sin necesidad.

**Por qué `List` suele ganar con colecciones pequeñas:** las operaciones de `Iterable` (`filter`, `map`, etc.) son funciones `inline`: la lambda se copia en el sitio de llamada y no se crea ningún objeto función. Las de `Sequence` no son `inline`: cada paso es un objeto iterador más una lambda, con llamadas virtuales por elemento. Para 50 elementos y dos pasos, esa sobrecarga pesa más que las listas intermedias que ahorras.

**Cuándo sí usar `Sequence`:**

1. **La operación terminal corta antes**: `first`, `firstOrNull`, `any`, `take(n)` sobre una colección grande con pasos caros.
2. **Muchos pasos sobre colecciones grandes** (decenas de miles de elementos o más), donde las listas intermedias sí cuestan memoria y GC.
3. **Fuentes que no caben en memoria o son infinitas**: `File.useLines { lines -> ... }` te da una `Sequence<String>` que lee línea a línea; `generateSequence` produce valores bajo demanda.

```kotlin
fun countErrors(log: File): Int =
    log.useLines { lines ->
        lines.filter { "ERROR" in it }
            .map { it.substringAfter("ERROR").trim() }
            .count { it.startsWith("db") }
    }
```

Aquí `Sequence` no es una optimización opcional: con `readLines()` cargarías un fichero de varios GB en memoria.

**Cuándo no:** colecciones pequeñas o medianas con dos o tres pasos y una operación terminal que recorre todo (`toList`, `sum`). Que es el caso de la mayoría de cadenas de código de negocio.

Mientras revisas esas cadenas, varias operaciones de la librería estándar sustituyen combinaciones habituales y son más claras que cualquier `asSequence`:

| En vez de | Usa |
|---|---|
| `map { it.id to it }.toMap()` | `associateBy { it.id }` |
| `filter { p }` y `filterNot { p }` por separado | `partition { p }` |
| `map { it.total }.sum()` | `sumOf { it.total }` |
| `groupBy { it.k }.mapValues { it.value.size }` | `groupingBy { it.k }.eachCount()` |

Cómo resolver la discusión con datos y no con opiniones: un *benchmark* con JMH (o `kotlinx-benchmark`) sobre las cadenas reales con tamaños reales. Medir con `System.nanoTime()` alrededor de un bucle no sirve en la JVM: el JIT, el calentamiento y la eliminación de código muerto falsean el resultado. Mi expectativa, que el *benchmark* debe confirmar o refutar: con menos de unos pocos miles de elementos y sin cortocircuito, la versión `List` empata o gana.""",
            },
        ]
    },
    # 23) Kotlin ↔ Java: @JvmStatic, @JvmOverloads, @JvmField/const, @Throws, @file:JvmName, nulabilidad
    {
        "messages": [
            {
                "role": "user",
                "content": "Hice una librería en Kotlin que ahora tiene que usar otro equipo desde Java. Se quejan de que tienen que escribir `Config.Companion.defaults()`, de que no pueden llamar a mis funciones sin pasar todos los parámetros por defecto, y de que no les deja hacer `catch (IOException e)` alrededor de `load`. ¿Cómo la dejo cómoda para Java?",
            },
            {
                "role": "assistant",
                "content": r"""Las tres quejas tienen solución con anotaciones de interoperabilidad, sin cambiar nada para quien la usa desde Kotlin:

```kotlin
@file:JvmName("Configs")

package com.acme.config

import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.util.Properties

class Config @JvmOverloads constructor(
    val host: String = "localhost",
    val port: Int = DEFAULT_PORT,
    val tls: Boolean = false,
) {
    companion object {
        const val DEFAULT_PORT = 8080

        @JvmStatic
        fun defaults(): Config = Config()

        @JvmStatic
        @Throws(IOException::class)
        fun load(path: Path): Config {
            val props = Properties()
            Files.newBufferedReader(path).use { props.load(it) }
            return Config(
                host = props.getProperty("host", "localhost"),
                port = props.getProperty("port", DEFAULT_PORT.toString()).toInt(),
                tls = props.getProperty("tls", "false").toBooleanStrict(),
            )
        }
    }
}

@JvmOverloads
fun parseHostPort(value: String, defaultPort: Int = Config.DEFAULT_PORT): Config {
    val host = value.substringBefore(':')
    val port = value.substringAfter(':', missingDelimiterValue = "").toIntOrNull() ?: defaultPort
    return Config(host = host, port = port)
}
```

Qué cambia en el lado Java, anotación por anotación:

| Anotación | Sin ella, en Java | Con ella |
|---|---|---|
| `@JvmStatic` | `Config.Companion.defaults()` | `Config.defaults()` |
| `@JvmOverloads` | un solo constructor con los tres argumentos | `new Config()`, `new Config("db")`, `new Config("db", 5432)` y el completo |
| `@Throws(IOException::class)` | `catch (IOException e)` no compila: «exception java.io.IOException is never thrown in body of corresponding try statement» | la firma declara `throws IOException` |
| `const val` | `Config.Companion.getDEFAULT_PORT()` | `Config.DEFAULT_PORT`, constante de compilación |
| `@file:JvmName("Configs")` | `ConfigKt.parseHostPort(...)` | `Configs.parseHostPort(...)` |

Notas sobre cada una:

- **`@JvmOverloads`** genera sobrecargas quitando parámetros **desde el final**. Si el que suele omitirse está en medio, Java no puede saltárselo; ordena los parámetros de más a menos usados.
- **`@Throws`** existe porque Kotlin no tiene excepciones *checked*: sin la anotación, el bytecode no declara nada y `javac` considera imposible que se lance `IOException`, aunque se lance de verdad.
- **`const val`** solo vale para primitivos y `String`. Para otros tipos (`val DEFAULT: Duration`), `@JvmField` expone el campo directamente en vez de un *getter*.
- **`@file:JvmName`** va en la primera línea del archivo, antes de `package`.

Dos cosas más que el equipo Java debe saber:

1. **La nulabilidad sí viaja.** Kotlin emite `@NotNull`/`@Nullable` en el bytecode, y el IDE avisa en Java. Además, cada función pública comprueba en tiempo de ejecución sus parámetros no nulables: pasar `null` a `host` desde Java lanza `NullPointerException: Parameter specified as non-null is null: ..., parameter host` en la entrada de la función, no tres capas más abajo.
2. **Evita exponer `internal`** a Java: se compila como público con el nombre alterado (`foo$nombre_modulo`), así que es visible pero feo y sin garantías.

La verificación que importa es un test **escrito en Java** dentro del mismo módulo de Gradle (`src/test/java`): si compila, la API es usable desde Java, y cualquier regresión (alguien quita un `@JvmStatic`) rompe el build.

```java
class ConfigJavaInteropTest {

    @Test
    void javaCallersUseTheIdiomaticApi(@TempDir Path dir) throws IOException {
        Path file = dir.resolve("app.properties");
        Files.writeString(file, "host=db.internal\nport=5432\n");

        Config loaded = Config.load(file);
        assertEquals("db.internal", loaded.getHost());
        assertEquals(5432, loaded.getPort());

        assertEquals(Config.DEFAULT_PORT, new Config("x").getPort());
        assertEquals(9000, Configs.parseHostPort("x", 9000).getPort());
        assertEquals("localhost", Config.defaults().getHost());
    }
}
```""",
            },
        ]
    },
    # 24) Kotlin delegación: by lazy, Delegates, ReadOnlyProperty, delegación de clase y su trampa
    {
        "messages": [
            {
                "role": "user",
                "content": "Veo `by lazy` y cosas como `class X(inner: Repo) : Repo by inner` en código Kotlin. ¿Qué hace `by` exactamente y para qué sirve en la práctica?",
            },
            {
                "role": "assistant",
                "content": r"""`by` significa «delega en este objeto». Tiene dos usos que comparten la palabra pero no el mecanismo: **propiedades delegadas** (el acceso a una propiedad se redirige a un objeto) y **delegación de clase** (la implementación de una interfaz se redirige a otro objeto).

## Propiedades delegadas

`val x by d` hace que leer `x` llame a `d.getValue(...)` (y escribir, a `d.setValue(...)` si es `var`). Las de la librería estándar cubren casi todo:

```kotlin
import kotlin.properties.Delegates

class ReportService(private val loader: TemplateLoader) {
    // se calcula la primera vez que se lee, y luego se reutiliza
    private val template: Template by lazy { loader.load("report.html") }

    // rechaza asignaciones fuera de rango (la asignación simplemente no ocurre)
    var retries: Int by Delegates.vetoable(3) { _, _, new -> new in 0..10 }

    // reacciona a cada cambio
    var mode: Mode by Delegates.observable(Mode.FAST) { _, old, new ->
        log.info("mode changed from {} to {}", old, new)
    }
}
```

Lo que conviene saber de `lazy`:

- Por defecto es `SYNCHRONIZED`: si dos hilos leen a la vez, solo uno ejecuta el inicializador. Si solo se accede desde un hilo, `lazy(LazyThreadSafetyMode.NONE)` evita el bloqueo.
- **Si el inicializador lanza, no se guarda nada**: el siguiente acceso lo vuelve a intentar. Útil si el fallo era transitorio; peligroso si el inicializador es caro y siempre falla.

Puedes escribir los tuyos con `ReadOnlyProperty`, por ejemplo para configuración desde variables de entorno con un error que diga qué falta:

```kotlin
import kotlin.properties.ReadOnlyProperty

fun env(name: String, default: String? = null) =
    ReadOnlyProperty<Any?, String> { _, property ->
        System.getenv(name) ?: default
            ?: error("missing env var $name for property '${property.name}'")
    }

class Settings {
    val databaseUrl by env("DATABASE_URL")
    val region by env("REGION", default = "eu-west-1")
}
```

Cada lectura vuelve a consultar el entorno; si quieres validar al arrancar, lee todas las propiedades en el constructor de quien use `Settings`.

## Delegación de clase

`: Repo by inner` le dice al compilador que genere todos los métodos de `Repo` reenviándolos a `inner`, salvo los que sobrescribas. Es el patrón decorador sin escribir los reenvíos a mano:

```kotlin
interface UserRepository {
    fun find(id: String): User?
    fun save(user: User)
    fun saveAll(users: List<User>) = users.forEach { save(it) }
}

class CountingRepository(
    private val inner: UserRepository,
) : UserRepository by inner {
    var saves = 0
        private set

    override fun save(user: User) {
        saves++
        inner.save(user)
    }
}
```

**La trampa:** `saveAll` también se delega a `inner`, y dentro de `inner` la llamada a `save` es `inner.save`, no `CountingRepository.save`. El decorador no se entera:

```kotlin
val repo = CountingRepository(InMemoryUserRepository())
repo.saveAll(listOf(ana, luis))
println(repo.saves) // 0, no 2
```

La delegación no es herencia: el objeto interno no sabe que está envuelto, así que sus llamadas a sí mismo no pasan por el envoltorio. Si el decorador debe ver todas las escrituras, sobrescribe también los métodos que las generan (`saveAll`) o intercepta en otro punto.

Test que deja documentado el comportamiento:

```kotlin
@Test
fun saveAllBypassesTheDecoratorUnlessOverridden() {
    val repo = CountingRepository(InMemoryUserRepository())
    repo.save(User("1", "Ana"))
    repo.saveAll(listOf(User("2", "Luis"), User("3", "Eva")))

    assertEquals(1, repo.saves)                // solo la llamada directa
    assertEquals("Eva", repo.find("3")?.name)  // pero los datos sí se guardaron
}
```

Si añades `override fun saveAll(users: List<User>) = users.forEach { save(it) }` en `CountingRepository`, el contador pasa a 3 y el test, como está escrito, falla: señal de que el decorador ya cubre ese camino.""",
            },
        ]
    },
    # 25) Comparativa: records de Java vs data class de Kotlin en monorepo mixto; multiturno con Jackson. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tenemos un monorepo mixto Java 21 + Kotlin 2.0. Para los DTOs compartidos entre módulos, ¿usamos records de Java o data classes de Kotlin? ¿Cómo se ven desde el otro lenguaje?",
            },
            {
                "role": "assistant",
                "content": r"""Regla corta: **escribe el DTO en el lenguaje del módulo que lo posee, y si lo consumen sobre todo desde Java, que sea un record** (de Java, o una data class con `@JvmRecord`). Los records se ven bien desde los dos lenguajes; las data classes, solo desde Kotlin.

Cómo se ve cada uno desde el otro lado:

**Record de Java usado desde Kotlin** (bien):

```java
public record Money(BigDecimal amount, String currency) {}
```

```kotlin
val m = Money(BigDecimal("9.99"), "EUR")
println(m.amount)   // Kotlin expone los componentes del record como propiedades
```

Lo que pierdes: `copy()` y los parámetros por defecto. Y la nulabilidad: `amount` llega como tipo de plataforma (`BigDecimal!`), así que Kotlin no te obliga a comprobar `null`. Anota los componentes con `@Nullable`/`@NonNull` (JSpecify, por ejemplo) para que Kotlin los vea como `BigDecimal?` o `BigDecimal`.

**Data class de Kotlin usada desde Java** (regular):

```kotlin
data class Money(val amount: BigDecimal, val currency: String = "EUR")
```

```java
Money m = new Money(new BigDecimal("9.99"), "EUR"); // sin parámetros por defecto
m.getAmount();                                      // getters, no amount()
m.copy(m.getAmount(), "USD");                       // copy exige todos los argumentos
m.component1();                                     // visible, pero inútil en Java
```

Funciona, pero se nota que no está pensada para Java, y un `switch` de Java con *record patterns* no puede deconstruirla.

**Lo mejor de los dos: `@JvmRecord`**

```kotlin
@JvmRecord
data class Money(val amount: BigDecimal, val currency: String)
```

El compilador de Kotlin genera un record de JVM real: Java ve `amount()`, puede usar `case Money(var a, var c)`, y Kotlin conserva `copy()` y la nulabilidad. Requisitos: destino JVM 16 o superior, todas las propiedades del constructor `val`, y la clase no puede extender otra clase (sí implementar interfaces).

| | Record de Java | Data class | `@JvmRecord` data class |
|---|---|---|---|
| Accesores en Java | `amount()` | `getAmount()` | `amount()` |
| Accesores en Kotlin | `m.amount` | `m.amount` | `m.amount` |
| `copy` con nombre | no | sí (Kotlin) | sí (Kotlin) |
| Nulabilidad para Kotlin | con anotaciones | nativa | nativa |
| *Record patterns* en Java | sí | no | sí |

Decisión para vuestro caso: módulo compartido en Kotlin con `@JvmRecord data class`, o en Java con records anotados con JSpecify. Las dos opciones dan una API cómoda a ambos lados; elige según qué lenguaje domine el equipo que mantiene ese módulo.

Verificación: un test en Java y otro en Kotlin en el módulo consumidor que construyan, comparen y deconstruyan el DTO. Si alguien quita el `@JvmRecord`, el `case Money(var a, var c)` de Java deja de compilar.""",
            },
            {
                "role": "user",
                "content": r"""Probamos con data classes y Jackson falla al deserializar:

```
com.fasterxml.jackson.databind.exc.InvalidDefinitionException: Cannot construct instance of `com.acme.shared.Money` (no Creators, like default constructor, exist): cannot deserialize from Object value (no delegate- or property-based Creator)
```

Con los records de Java no pasaba.""",
            },
            {
                "role": "assistant",
                "content": r"""Jackson construye objetos con un constructor sin argumentos más *setters*, o con un constructor cuyos parámetros sepa asociar a las propiedades del JSON. Una data class de Kotlin no tiene constructor vacío, y Jackson no conoce los nombres de sus parámetros porque no lee los metadatos de Kotlin. Con los records funciona porque Jackson 2.12+ los soporta de forma nativa: el constructor canónico y los nombres de los componentes están en el bytecode estándar.

Arreglo: el módulo de Kotlin para Jackson.

```kotlin
// build.gradle.kts del módulo que deserializa
dependencies {
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")
}
```

Sin versión si usas el BOM de Spring Boot o `jackson-bom`; si no, la misma versión que `jackson-databind`.

- **Con Spring Boot** no hay que hacer nada más: si el módulo está en el *classpath*, la autoconfiguración lo registra en el `ObjectMapper`.
- **Sin Spring**, regístralo al crear el mapper:

```kotlin
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.fasterxml.jackson.module.kotlin.readValue

val mapper = jacksonObjectMapper()
val money: Money = mapper.readValue("{\"amount\": 9.99, \"currency\": \"EUR\"}")
```

Además de arreglar el error, el módulo hace que Jackson respete la semántica de Kotlin:

- **Parámetros por defecto**: si el JSON no trae `currency`, se usa `"EUR"`.
- **Nulabilidad**: si falta un campo no nulable sin valor por defecto, falla en la deserialización con `MismatchedInputException` que nombra el parámetro, en vez de colar un `null` que explotará más tarde.

Si ese DTO también lo deserializa un servicio Java con un `ObjectMapper` sin el módulo, el problema reaparece allí. Es otro argumento a favor de `@JvmRecord`: Jackson lo trata como un record y no necesita el módulo de Kotlin.

Test de ida y vuelta, que es el que habría detectado esto antes de producción:

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import com.fasterxml.jackson.databind.exc.MismatchedInputException
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.fasterxml.jackson.module.kotlin.readValue
import java.math.BigDecimal

class MoneyJsonTest {
    private val mapper = jacksonObjectMapper()

    @Test
    fun roundTripKeepsValueAndAppliesDefaults() {
        val original = Money(BigDecimal("9.99"), "USD")
        assertEquals(original, mapper.readValue<Money>(mapper.writeValueAsString(original)))
        assertEquals("EUR", mapper.readValue<Money>("{\"amount\": 1}").currency)
    }

    @Test
    fun missingRequiredFieldFailsAtTheBoundary() {
        assertFailsWith<MismatchedInputException> { mapper.readValue<Money>("{\"currency\": \"EUR\"}") }
    }
}
```

Fíjate en el detalle de `BigDecimal("9.99")`: Jackson lo serializa como número y lo lee de vuelta como `BigDecimal` con la misma escala, así que `equals` se cumple. Si cambias a `Double` en algún momento, este test es el que te avisa de la pérdida de precisión.""",
            },
        ]
    },
    # 26) Comparativa: corrutinas de Kotlin vs hilos virtuales de Java en Spring Boot. Usuario en inglés pide español. System arquitecto
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto de software senior. Justifica cada recomendación con sus trade-offs."},
            {
                "role": "user",
                "content": "We have a Spring Boot 3.3 service written in Kotlin (Spring MVC, JPA, a couple of REST clients). Half the team wants to go all-in on coroutines and WebFlux; the other half says Java 21 virtual threads make that unnecessary. Can you answer in Spanish? It's going into a design doc for the team.",
            },
            {
                "role": "assistant",
                "content": r"""Recomendación: **Spring MVC con hilos virtuales como base, y corrutinas solo donde aporten concurrencia estructurada o *streaming***. Migrar todo a WebFlux con `suspend` de punta a punta rara vez compensa en un servicio de negocio sobre JPA.

## Qué resuelve cada opción

Las dos atacan el mismo problema: atender muchas peticiones que pasan casi todo su tiempo esperando I/O sin dedicar un hilo del sistema operativo a cada espera.

- **Hilos virtuales**: mantienen el código bloqueante de siempre. La JVM desmonta el hilo virtual cuando bloquea y lo vuelve a montar al recibir la respuesta. Con `spring.threads.virtual.enabled=true`, Tomcat atiende cada petición en uno.
- **Corrutinas + WebFlux**: el código se escribe con funciones `suspend` y el *runtime* de corrutinas multiplexa sobre pocos hilos. Necesita que toda la cadena de I/O sea no bloqueante (R2DBC en vez de JDBC, `WebClient` en vez de `RestTemplate`).

## Comparación

| Criterio | MVC + hilos virtuales | WebFlux + corrutinas |
|---|---|---|
| Cambio de código | una propiedad | reescribir controladores, repositorios y clientes |
| Acceso a datos | JPA/JDBC tal cual | R2DBC (sin JPA: sin *lazy loading* ni caché de primer nivel) |
| Cancelación y *timeouts* | manuales: *timeouts* de cliente, `Future.cancel` | estructurados: `withTimeout` cancela todo el árbol de llamadas |
| *Streaming* y *backpressure* | limitado (`SseEmitter`) | `Flow` nativo |
| Trazas de error | pilas completas | pilas fragmentadas por las suspensiones |
| MDC / `ThreadLocal` | funcionan | requieren propagar contexto (`MDCContext`, *context propagation*) |
| Riesgo principal | *pinning* con `synchronized` en Java 21 (resuelto en JDK 24) | llamadas bloqueantes ocultas que congelan el *event loop* |
| Curva para el equipo | ninguna | corrutinas + modelo reactivo de Spring |

## El argumento de cada mitad del equipo, evaluado

- **«Las corrutinas escalan más»**: para I/O bloqueante clásico, los hilos virtuales ya eliminan el límite del pool de hilos. El cuello de botella pasa a ser la base de datos o las APIs externas, y eso no lo cambia ningún modelo de concurrencia.
- **«Las corrutinas dan mejor código concurrente»**: esto sí es cierto, y es su ventaja real. `coroutineScope { async {...}; async {...} }` con cancelación automática del resto si una falla es más seguro que coordinar `Future` a mano.
- **«Los hilos virtuales hacen innecesarias las corrutinas»**: para el modelo «un hilo por petición», sí. Para *streaming*, flujos de eventos o lógica concurrente compleja, no.

## Cómo combinarlos

No es una elección binaria. Dentro de un servicio MVC con hilos virtuales, donde un caso de uso necesite *fan-out* estructurado:

```kotlin
private val virtualThreads = Executors.newVirtualThreadPerTaskExecutor().asCoroutineDispatcher()

fun productPage(sku: String): ProductPage = runBlocking(virtualThreads) {
    coroutineScope {
        val price = async { priceClient.priceFor(sku) }       // cliente bloqueante
        val stock = async { stockClient.stockFor(sku) }
        ProductPage(price.await(), stock.await())
    }
}
```

`runBlocking` bloquea el hilo virtual de la petición, que es barato, y cada `async` ejecuta su llamada bloqueante en otro hilo virtual. Usar ese *dispatcher* en vez de `Dispatchers.IO` evita su límite por defecto de 64 hilos. El coste es tener dos modelos de concurrencia en el mismo código: acotad este patrón a casos de uso concretos y documentadlo.

## Cuándo cambiaría la recomendación

- *Endpoints* de *streaming* (SSE, WebSocket) o decenas de miles de conexiones de larga duración.
- Un *stack* que ya es reactivo de extremo a extremo.
- Código compartido con Android o Kotlin Multiplatform, donde las corrutinas son el estándar.

## Cómo validar la decisión

Antes de comprometer el diseño, medid: activad hilos virtuales en una rama, ejecutad una prueba de carga (k6 o Gatling) al doble del pico real contra los tres *endpoints* más usados, y comparad p99, CPU, memoria y tasa de errores con la versión actual. Si el p99 ya cumple el objetivo, el coste de migrar a WebFlux no tiene retorno; si no lo cumple, el perfil dirá si el problema es el modelo de hilos o la base de datos, y en el segundo caso ninguna de las dos opciones lo arregla.""",
            },
        ]
    },
    # 27) Kotlin: carrera de datos en un contador con Dispatchers.Default, @Volatile, synchronized vs Mutex. Inglés, código roto
    {
        "messages": [
            {
                "role": "user",
                "content": r"""With 100,000 items, `processed` ends up somewhere between 97,000 and 99,000, different on every run:

```kotlin
var processed = 0

suspend fun processAll(items: List<Item>) = coroutineScope {
    items.forEach { item ->
        launch(Dispatchers.Default) {
            handle(item)
            processed++
        }
    }
}
```

I added `@Volatile` and nothing changed. Then I wrapped the body in `synchronized(this) { ... }`, but `handle` is a suspend function and it doesn't compile anymore.""",
            },
            {
                "role": "assistant",
                "content": r"""It's a data race. `Dispatchers.Default` runs your coroutines on several threads at once, and `processed++` is not one operation but three: read, add one, write. Two threads read 41,000, both write 41,001, and one increment is lost. The more cores, the more you lose.

Why your two attempts failed:

- **`@Volatile`** guarantees *visibility* (every thread sees the latest written value), not *atomicity*. The read-add-write sequence can still interleave between two threads.
- **`synchronized` cannot contain a suspension point.** The compiler rejects it with "The 'handle' suspension point is inside a critical section", because a coroutine could suspend while holding a monitor and resume on a different thread, which would then release a lock it never acquired.

Fixes, from best to most situational:

**1. Don't share mutable state.** Each coroutine returns its result and you aggregate once at the end. No locks, no races, and the counter can no longer drift from what really happened:

```kotlin
suspend fun processAll(items: List<Item>): Int = coroutineScope {
    items.map { item ->
        async(Dispatchers.Default) {
            handle(item)
            1
        }
    }.awaitAll().sum()
}
```

**2. An atomic counter**, when you need a live value other code can read while processing (progress reporting, metrics):

```kotlin
private val processed = AtomicInteger()

suspend fun processAll(items: List<Item>) = coroutineScope {
    items.forEach { item ->
        launch(Dispatchers.Default) {
            handle(item)
            processed.incrementAndGet()
        }
    }
}
```

`incrementAndGet` is atomic at the hardware level (`lock xadd` on x86, a compare-and-swap loop on other architectures); it never blocks a thread.

**3. `Mutex`** from `kotlinx.coroutines.sync`, when the critical section itself must suspend, for example updating shared state that requires a suspend call in the middle:

```kotlin
private val mutex = Mutex()
private val seen = mutableSetOf<String>()

suspend fun recordOnce(id: String, persist: suspend (String) -> Unit) {
    mutex.withLock {
        if (seen.add(id)) {
            persist(id) // allowed: Mutex suspends instead of blocking a thread
        }
    }
}
```

A `Mutex` is not reentrant and is slower than an atomic, so use it only when the protected block really suspends.

Also move `processed` out of top-level `var`. Global mutable state makes the function impossible to call twice concurrently or test in isolation.

How to verify the fix, given that races are probabilistic:

```kotlin
@RepeatedTest(20)
fun countsEveryItemExactlyOnce() = runBlocking {
    val items = List(100_000) { Item("i-$it") }
    assertEquals(100_000, processAll(items))
}
```

Two details matter here. **Repeat the test**: a single green run proves little for a race. And **make sure the code under test actually runs on multiple threads**: here `Dispatchers.Default` is hard-coded, so it does. If you inject the dispatcher and pass a `StandardTestDispatcher` from `runTest`, everything runs on one thread and the original bug would pass the test.""",
            },
        ]
    },
    # 28) Gradle Kotlin DSL: toolchains, version catalog, JUnit 5; multiturno con constraints para una transitiva vulnerable
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy montando un proyecto nuevo con Gradle (Kotlin DSL) que mezcla Java 21 y Kotlin 2.0. ¿Cómo dejo bien configurado el build: versión de Java, dependencias centralizadas y JUnit 5?",
            },
            {
                "role": "assistant",
                "content": r"""Tres piezas: **toolchain** para fijar el JDK, **version catalog** para las versiones, y la configuración de JUnit Platform. Con eso el build es reproducible en cualquier máquina, tenga el JDK que tenga instalado.

`settings.gradle.kts`:

```kotlin
plugins {
    // permite a Gradle descargar el JDK del toolchain si no está instalado
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.8.0"
}

rootProject.name = "pricing"
```

`gradle/libs.versions.toml` (Gradle lo detecta solo):

```toml
[versions]
kotlin = "2.0.21"
junit = "5.11.3"
jackson = "2.18.1"

[libraries]
jackson-bom = { module = "com.fasterxml.jackson:jackson-bom", version.ref = "jackson" }
jackson-module-kotlin = { module = "com.fasterxml.jackson.module:jackson-module-kotlin" }
junit-bom = { module = "org.junit:junit-bom", version.ref = "junit" }
junit-jupiter = { module = "org.junit.jupiter:junit-jupiter" }
junit-platform-launcher = { module = "org.junit.platform:junit-platform-launcher" }

[plugins]
kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }
```

`build.gradle.kts`:

```kotlin
plugins {
    alias(libs.plugins.kotlin.jvm)
    application
}

group = "com.acme"
version = "0.1.0"

repositories {
    mavenCentral()
}

kotlin {
    jvmToolchain(21) // fija el JDK para Kotlin y para Java
}

dependencies {
    implementation(platform(libs.jackson.bom))
    implementation(libs.jackson.module.kotlin)

    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testImplementation(kotlin("test"))
    testRuntimeOnly(libs.junit.platform.launcher)
}

tasks.test {
    useJUnitPlatform()
}

application {
    mainClass = "com.acme.pricing.MainKt"
}
```

Por qué cada decisión:

- **`jvmToolchain(21)`** en vez de `sourceCompatibility`/`jvmTarget` sueltos: el plugin de Kotlin aplica el de Java, y una sola línea alinea los dos compiladores con el mismo JDK. Si no coinciden, Gradle falla con un error de «inconsistent JVM target compatibility». El código Java va en `src/main/java` y el Kotlin en `src/main/kotlin`, en el mismo módulo.
- **BOM con `platform(...)`**: la versión se declara una vez y todos los artefactos de la familia (Jackson, JUnit) quedan alineados. Por eso las librerías del catálogo no llevan versión.
- **`junit-platform-launcher` explícito**: Gradle 8 avisa de que la carga automática del *launcher* está obsoleta, y Gradle 9 deja de hacerla.
- **`kotlin("test")`** con `useJUnitPlatform()`: el plugin elige solo la variante para JUnit 5, y puedes usar `kotlin.test.assertEquals` en los tests de Kotlin.

Comprobación:

```sh
./gradlew -q javaToolchains   # lista los JDK detectados y cuál usa el build
./gradlew build               # compila Java + Kotlin y ejecuta los tests
./gradlew -q dependencies --configuration testRuntimeClasspath | grep junit
```

En el último comando todas las piezas de JUnit deben mostrar la misma versión, 5.11.3. Si alguna aparece con otra, alguna dependencia la está trayendo por fuera del BOM.""",
            },
            {
                "role": "user",
                "content": "Ya está funcionando. El escáner de seguridad marca `commons-compress` 1.21, que viene transitiva por una librería que no controlamos. ¿Cómo la subo sin tocar esa librería?",
            },
            {
                "role": "assistant",
                "content": r"""Con una **restricción de dependencia** (*dependency constraint*): le dice a Gradle «si alguien trae este módulo, que sea como mínimo esta versión», sin declararlo como dependencia directa.

```kotlin
dependencies {
    constraints {
        implementation("org.apache.commons:commons-compress:1.27.1") {
            because("CVE-2024-25710 y CVE-2024-26308 afectan a versiones anteriores a 1.26.0")
        }
    }
}
```

O, siguiendo el catálogo, añade `commons-compress = { module = "org.apache.commons:commons-compress", version = "1.27.1" }` en `[libraries]` y usa `implementation(libs.commons.compress)` dentro del bloque `constraints`.

Por qué una restricción y no otras opciones:

- **Frente a añadirla como dependencia directa**: una dependencia directa queda en el *classpath* aunque la librería que la traía desaparezca algún día; la restricción solo actúa mientras alguien la necesite.
- **Frente a `resolutionStrategy.force`**: `force` sustituye la versión sin dejar rastro en los informes de Gradle; la restricción aparece en `dependencyInsight` con el texto del `because`, y el siguiente que lea el build sabe por qué está ahí.
- **Gradle elige la versión más alta** entre todas las solicitudes, así que la restricción solo sube el suelo. Para forzar una versión **más baja** que la pedida (raro, y casi siempre mala idea) haría falta `strictly`.

Verificación:

```sh
./gradlew -q dependencyInsight --dependency commons-compress --configuration runtimeClasspath
```

La salida debe mostrar `org.apache.commons:commons-compress:1.27.1` seleccionada «by constraint», con tu texto del `because`, y la 1.21 como versión solicitada por la librería transitiva.

Antes de darlo por cerrado, ejecuta los tests que pasan por esa librería: estás haciéndola funcionar con una versión de `commons-compress` con la que sus autores no la probaron. Entre 1.21 y 1.27 la API pública se mantuvo compatible en lo habitual, pero son seis versiones menores; si la librería usa algo eliminado, el fallo será un `NoSuchMethodError` en ejecución, no en compilación. Y vuelve a pasar el escáner: es el test de regresión de este cambio.""",
            },
        ]
    },
    # 29) Java ExecutorService: el programa no termina y las excepciones de submit se pierden
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un proceso batch en Java 21 que reparte el trabajo con `Executors.newFixedThreadPool(8)` y `submit`. Dos problemas: el programa no termina cuando acaba `main`, y cuando una tarea lanza una excepción no aparece nada en el log, simplemente falta ese resultado. ¿Qué estoy haciendo mal?",
            },
            {
                "role": "assistant",
                "content": r"""Son dos comportamientos documentados del `ExecutorService`, no errores de la JVM:

1. **No termina** porque los hilos de `newFixedThreadPool` no son *daemon*: la JVM no sale mientras haya un hilo no *daemon* vivo, y los del pool se quedan esperando tareas nuevas indefinidamente. Hay que cerrar el pool.
2. **Las excepciones desaparecen** porque `submit` las captura y las guarda dentro del `Future`. Solo reaparecen, envueltas en `ExecutionException`, cuando alguien llama a `future.get()`. Si nadie lo llama, nadie se entera. (`execute` sí las propaga al *handler* de excepciones no capturadas del hilo, que las imprime por `stderr`, pero no te da forma de saber qué entrada falló.)

Puedes confirmar el primer diagnóstico con el proceso colgado: `jcmd <pid> Thread.print` mostrará `pool-1-thread-1` a `pool-1-thread-8` en estado `WAITING` dentro de `LinkedBlockingQueue.take`.

La solución cubre las dos cosas: recoger cada `Future`, consultar su resultado y cerrar el pool con `try-with-resources` (`ExecutorService` es `AutoCloseable` desde Java 19; `close()` hace `shutdown` y espera a que terminen las tareas).

```java
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadFactory;

public final class BatchRunner {

    @FunctionalInterface
    public interface Task<T, R> {
        R apply(T input) throws Exception;
    }

    public record BatchResult(int succeeded, int failed) {}

    private static final System.Logger LOG = System.getLogger(BatchRunner.class.getName());

    private BatchRunner() {}

    public static <T, R> BatchResult runAll(List<T> inputs, Task<T, R> task, int threads)
            throws InterruptedException {
        ThreadFactory named = Thread.ofPlatform().name("batch-", 0).factory();
        int succeeded = 0;
        int failed = 0;
        try (ExecutorService pool = Executors.newFixedThreadPool(threads, named)) {
            List<Future<R>> futures = new ArrayList<>(inputs.size());
            for (T input : inputs) {
                futures.add(pool.submit(() -> task.apply(input)));
            }
            for (int i = 0; i < futures.size(); i++) {
                try {
                    futures.get(i).get();
                    succeeded++;
                } catch (ExecutionException e) {
                    failed++;
                    LOG.log(System.Logger.Level.ERROR, "task failed for " + inputs.get(i), e.getCause());
                }
            }
        }
        return new BatchResult(succeeded, failed);
    }

    public static void main(String[] args) throws InterruptedException {
        List<Path> inputs = Arrays.stream(args).map(Path::of).toList();
        BatchResult result = runAll(inputs, BatchRunner::process, 8);
        System.exit(result.failed() == 0 ? 0 : 1);
    }

    private static long process(Path input) throws Exception {
        return java.nio.file.Files.size(input); // aquí va tu procesamiento real
    }
}
```

Decisiones:

- **`e.getCause()`** en el log: la `ExecutionException` es solo el envoltorio; la pila útil es la de la causa.
- **Hilos con nombre** (`batch-0`, `batch-1`...): en un volcado de hilos o en el log sabes de dónde viene cada uno, en vez de `pool-3-thread-7`.
- **Código de salida distinto de cero si algo falló**: cron, Kubernetes o el CI que lance el batch lo ven como fallo. Antes, un batch con errores terminaba (cuando terminaba) igual que uno correcto.
- **`runAll` separado de `main`** para poder probarlo sin lanzar procesos.

Si estuvieras en Java 17 o anterior, sin `close()`, el equivalente es un `finally` con `pool.shutdown()` seguido de `pool.awaitTermination(...)`, y `shutdownNow()` si vence la espera.

Ojo con el caso contrario: las tareas lanzadas con `CompletableFuture.supplyAsync` sin *executor* van al `ForkJoinPool.commonPool()`, cuyos hilos **sí** son *daemon*. Ahí el problema es el opuesto: `main` termina y la JVM sale matando las tareas a medias, sin ningún error.

Test que cubre los dos síntomas:

```java
@Test
void failedTaskIsCountedAndTheRunFinishes() {
    BatchRunner.BatchResult result = assertTimeoutPreemptively(Duration.ofSeconds(5), () ->
            BatchRunner.runAll(List.of("ok", "boom", "fine"), name -> {
                if (name.equals("boom")) {
                    throw new IllegalStateException("boom");
                }
                return name.length();
            }, 2));

    assertEquals(new BatchRunner.BatchResult(2, 1), result);
}
```

El `assertEquals` cubre las excepciones perdidas: con la versión original, sin `get()`, `failed` sería 0. El cierre del pool se comprueba mejor de punta a punta: ejecuta el `main` real con un fichero inexistente entre los argumentos y verifica que el proceso termina y devuelve código 1 (`echo $?` en Linux). Con el pool sin cerrar, el proceso se quedaría colgado.""",
            },
        ]
    },
    # 30) Kotlin: testear funciones suspend con runTest, MockK e inyección de dispatcher; multiturno. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo un servicio Kotlin con funciones suspend: lee un producto de un repositorio JDBC (bloqueante) con `withContext(Dispatchers.IO)` y pide una tasa de cambio a un cliente HTTP suspendible con `withTimeout(2.seconds)`. Mis tests usan `runBlocking` y para probar el timeout tardan 2 segundos reales. ¿Cómo lo testeo bien? Usamos MockK.",
            },
            {
                "role": "assistant",
                "content": r"""Dos cambios: **inyecta el dispatcher** en vez de usar `Dispatchers.IO` directamente, y usa **`runTest`**, cuyo reloj virtual hace que el `withTimeout` de 2 s se dispare al instante.

El servicio:

```kotlin
import java.math.BigDecimal
import kotlin.time.Duration.Companion.seconds
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

data class Product(val id: String, val basePrice: BigDecimal)
data class Quote(val productId: String, val amount: BigDecimal, val currency: String)

class ProductNotFound(id: String) : RuntimeException("product not found: $id")
class RatesUnavailable(currency: String, cause: Throwable) :
    RuntimeException("no exchange rate for $currency", cause)

interface ProductRepository {
    fun find(id: String): Product?                    // JDBC, bloqueante
}

interface RatesClient {
    suspend fun rateFor(currency: String): BigDecimal // cliente HTTP suspendible
}

class QuoteService(
    private val products: ProductRepository,
    private val rates: RatesClient,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) {
    suspend fun quote(productId: String, currency: String): Quote {
        val product = withContext(ioDispatcher) { products.find(productId) }
            ?: throw ProductNotFound(productId)
        val rate = try {
            withTimeout(2.seconds) { rates.rateFor(currency) }
        } catch (e: TimeoutCancellationException) {
            throw RatesUnavailable(currency, e)
        }
        return Quote(productId, product.basePrice * rate, currency)
    }
}
```

El valor por defecto `Dispatchers.IO` mantiene la API igual para producción; solo los tests pasan otro.

Los tests:

```kotlin
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import java.math.BigDecimal
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest

class QuoteServiceTest {
    private val products = mockk<ProductRepository>()
    private val rates = mockk<RatesClient>()

    @Test
    fun convertsThePrice() = runTest {
        every { products.find("p-1") } returns Product("p-1", BigDecimal("10.00"))
        coEvery { rates.rateFor("USD") } returns BigDecimal("1.10")
        val service = QuoteService(products, rates, StandardTestDispatcher(testScheduler))

        assertEquals(BigDecimal("11.0000"), service.quote("p-1", "USD").amount)
    }

    @Test
    fun slowRatesTimeOutOnTheVirtualClock() = runTest {
        every { products.find("p-1") } returns Product("p-1", BigDecimal("10.00"))
        coEvery { rates.rateFor("USD") } coAnswers {
            delay(5_000)
            BigDecimal.ONE
        }
        val service = QuoteService(products, rates, StandardTestDispatcher(testScheduler))

        assertFailsWith<RatesUnavailable> { service.quote("p-1", "USD") }
        assertEquals(2_000L, currentTime) // 2 s virtuales, 0 reales
    }

    @Test
    fun missingProductNeverCallsTheRatesApi() = runTest {
        every { products.find("nope") } returns null
        val service = QuoteService(products, rates, StandardTestDispatcher(testScheduler))

        assertFailsWith<ProductNotFound> { service.quote("nope", "USD") }
        coVerify(exactly = 0) { rates.rateFor(any()) }
    }
}
```

Puntos clave:

- **`every` para funciones normales, `coEvery`/`coVerify` para `suspend`.** Con `every` sobre una función `suspend`, MockK no puede interceptarla bien.
- **`coAnswers { delay(5_000); ... }`** simula una API lenta. Bajo `runTest`, ese `delay` usa el reloj virtual: el `withTimeout(2.seconds)` vence en t = 2 000 ms virtuales y el test termina en milisegundos reales. `currentTime` lo demuestra.
- **`StandardTestDispatcher(testScheduler)`** comparte el reloj de `runTest`, así que el código dentro de `withContext(ioDispatcher)` también avanza en tiempo virtual y en un orden determinista.
- **`assertFailsWith` es `inline`**, por eso admite llamadas `suspend` dentro del bloque.
- **El `BigDecimal` esperado es `11.0000`**: `10.00 × 1.10` suma las escalas (2 + 2). Si comparas con `11.00`, `assertEquals` falla porque `BigDecimal.equals` tiene en cuenta la escala; o normalizas en el servicio o lo pruebas con `compareTo`.""",
            },
            {
                "role": "user",
                "content": "Una duda: si en el test dejo el `Dispatchers.IO` por defecto, los tres tests también pasan. ¿Para qué inyectarlo entonces?",
            },
            {
                "role": "assistant",
                "content": r"""Pasan **hoy** porque el único trabajo dentro de `withContext(ioDispatcher)` es un *mock* que responde al instante, y el `delay` que simula la API lenta está fuera de ese bloque. Lo que cambia al inyectar es **quién controla ese trozo de código**:

1. **Con el dispatcher de test**, el bloque se ejecuta en el hilo del test, planificado por `runTest`: orden determinista, tiempo virtual, y `advanceTimeBy`/`runCurrent` lo gobiernan.
2. **Con `Dispatchers.IO`**, el bloque sale a un hilo real del pool. Un `delay` que acabe ahí dentro (porque el repositorio pase a ser `suspend` y simules su latencia, o porque alguien mueva otra llamada dentro del bloque) espera tiempo real, porque ese dispatcher no usa el reloj de `runTest`. Y el orden respecto al resto del test pasa a depender de los hilos. De ahí salen los tests lentos y los que fallan una vez de cada cincuenta en CI.
3. **La dependencia queda oculta.** Un `Dispatchers.IO` fijo dentro de la clase es lo mismo que un `Clock` o un `Random` globales: el código funciona, pero el test no puede controlarlo. Inyectarlo con valor por defecto no cuesta nada en producción y deja explícito que el servicio hace I/O bloqueante.

Lo puedes ver sin cambiar el servicio, registrando desde el *mock* en qué hilo se ejecuta el repositorio:

```kotlin
@Test
fun repositoryRunsWhereTheTestDecides() = runTest {
    var repositoryThread = ""
    every { products.find("p-1") } answers {
        repositoryThread = Thread.currentThread().name
        Product("p-1", BigDecimal("10.00"))
    }
    coEvery { rates.rateFor("USD") } returns BigDecimal.ONE

    QuoteService(products, rates, StandardTestDispatcher(testScheduler)).quote("p-1", "USD")

    assertEquals(Thread.currentThread().name, repositoryThread)
}
```

Con el dispatcher de test pasa: el repositorio corre en el mismo hilo que el test. Quita el tercer argumento del constructor y falla, con un `DefaultDispatcher-worker-N` como hilo del repositorio: ese trabajo ya no está bajo el control de `runTest`.

Regla práctica para el equipo: **todo `CoroutineDispatcher` que use una clase entra por el constructor**, igual que el reloj. `Dispatchers.Main` es la excepción en Android, que se sustituye en tests con `Dispatchers.setMain`; para `IO` y `Default`, inyección.""",
            },
        ]
    },
]
