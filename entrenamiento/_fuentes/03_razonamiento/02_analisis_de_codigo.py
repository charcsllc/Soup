"""Análisis y revisión de código: corrección, complejidad real, invariantes, robustez ante
entradas no confiables, concurrencia, recursos, legibilidad, diseño, fallos en producción y
comparación de implementaciones. Cada revisión prioriza (bloqueante / importante / menor),
propone el diff mínimo y dice cómo comprobar el arreglo. Todo el razonamiento va visible.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Python: búsqueda binaria con off-by-one.
    {
        "messages": [
            {"role": "user", "content": """Mi búsqueda binaria a veces no encuentra elementos que SÍ están en la lista. No veo el fallo:

```python
def buscar(lista, objetivo):
    lo, hi = 0, len(lista) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if lista[mid] == objetivo:
            return mid
        elif lista[mid] < objetivo:
            lo = mid + 1
        else:
            hi = mid
    return -1
```"""},
            {
                "role": "assistant",
                "content": """El fallo está en la combinación de `hi = len(lista) - 1` con `while lo < hi`: el bucle termina cuando `lo == hi` **sin comprobar nunca la posición `lo`**. Cada vez que el objetivo es el último candidato que queda, se pierde.

**Reproducción mínima.** `buscar([1, 2, 3], 3)`:

| iteración | lo | hi | mid | lista[mid] | acción |
|---|---|---|---|---|---|
| 1 | 0 | 2 | 1 | 2 | 2 < 3 → lo = 2 |
| fin | 2 | 2 | — | — | `lo < hi` es falso, sale sin mirar `lista[2]` |

Devuelve −1 aunque el 3 está en la posición 2. Lo mismo pasa con `buscar([5], 5)`: nunca entra en el bucle.

**Arreglo mínimo (una línea).** Hay dos convenciones coherentes; mezclarlas es lo que produce el bug.

Opción A, intervalo cerrado `[lo, hi]`: entonces el bucle debe ser `while lo <= hi` y el descarte por la derecha `hi = mid - 1`:

```python
    lo, hi = 0, len(lista) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if lista[mid] == objetivo:
            return mid
        elif lista[mid] < objetivo:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
```

Opción B, intervalo semiabierto `[lo, hi)`: deja `while lo < hi` y `hi = mid`, pero inicializa `hi = len(lista)`. Tu código es la opción B con la inicialización de la A.

**Por qué no hay bucle infinito en ninguna de las dos.** En A, cada vuelta reduce `hi - lo` al menos en 1 porque `mid` siempre se descarta. En B, `hi = mid` con `mid < hi` (ya que `mid = (lo + hi) // 2 < hi` cuando `lo < hi`) también encoge el intervalo.

**Cómo comprobar el arreglo.** Un test que recorra todas las posiciones y todos los huecos, que es lo que un caso suelto no cubre:

```python
import bisect

def test_buscar_todas_las_posiciones():
    for n in range(0, 10):
        lista = list(range(0, 2 * n, 2))          # pares: 0, 2, 4, …
        for x in range(-1, 2 * n + 1):
            esperado = bisect.bisect_left(lista, x) if x in lista else -1
            assert buscar(lista, x) == esperado, (lista, x)
```

Con tu versión original falla en el primer `n = 1` (`buscar([0], 0)`); con cualquiera de las dos opciones pasa. Si quieres una regla para no volver a caer: elige intervalo cerrado o semiabierto *antes* de escribir el `while`, y que las tres líneas (inicialización, condición, actualización de `hi`) sigan la misma convención.""",
            },
        ]
    },
    # 2) Python: inyección SQL y secreto en logs.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": """Revisa esta función de login, es para un panel interno:

```python
import logging
import psycopg

log = logging.getLogger(__name__)

def autenticar(conn_str: str, usuario: str, password: str) -> bool:
    log.info("Conectando con %s", conn_str)
    with psycopg.connect(conn_str) as conn:
        q = f"SELECT 1 FROM usuarios WHERE nombre = '{usuario}' AND pass_hash = md5('{password}')"
        row = conn.execute(q).fetchone()
        log.debug("Login de %s con %s: %s", usuario, password, row)
        return row is not None
```"""},
            {
                "role": "assistant",
                "content": """Tres problemas bloqueantes y uno importante. «Panel interno» no rebaja ninguno: los internos también se filtran.

**Bloqueante 1: inyección SQL.** `usuario` y `password` se interpolan en la consulta. Con `usuario = "admin' --"` la cláusula de contraseña queda comentada y entra sin ella. Con `' OR 1=1 --` entra como el primer usuario de la tabla.

**Bloqueante 2: secretos en los logs.** `conn_str` contiene normalmente la contraseña de la base de datos, y la línea de `debug` escribe la contraseña del usuario en claro. En cuanto alguien suba el nivel a DEBUG para investigar otra cosa, los logs se convierten en un volcado de credenciales.

**Bloqueante 3: MD5 sin sal para contraseñas.** Es reversible con tablas precalculadas para cualquier contraseña habitual. Hay que usar un hash de contraseñas lento (argon2id o bcrypt) y comparar en la aplicación, no en SQL.

**Importante: la comparación revela qué usuarios existen** (si el nombre no existe, la consulta es más rápida que si existe y falla el hash). Con un hash de contraseñas en la aplicación se mitiga verificando siempre contra *algún* hash.

**Diff mínimo que cierra los tres bloqueantes:**

```python
import logging
import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

log = logging.getLogger(__name__)
hasher = PasswordHasher()
HASH_FALSO = hasher.hash("contraseña-ficticia-para-tiempo-constante")

def autenticar(conn_str: str, usuario: str, password: str) -> bool:
    log.info("Conectando a la base de datos")
    with psycopg.connect(conn_str) as conn:
        row = conn.execute(
            "SELECT pass_hash FROM usuarios WHERE nombre = %s",
            (usuario,),
        ).fetchone()
    hash_guardado = row[0] if row else HASH_FALSO
    try:
        hasher.verify(hash_guardado, password)
    except VerifyMismatchError:
        log.info("Login fallido para usuario=%r", usuario)
        return False
    log.info("Login correcto para usuario=%r", usuario)
    return row is not None
```

Decisiones: la consulta va parametrizada (`%s` con tupla; psycopg escapa por ti); el `conn_str` y la contraseña no aparecen en ningún log; cuando el usuario no existe se verifica contra un hash falso para que el tiempo de respuesta no delate la existencia; y la verificación final `row is not None` evita que la contraseña ficticia autentique a nadie.

Migración: hay que rehashear las contraseñas existentes. Lo habitual es guardar un campo `algoritmo` y, en el primer login correcto con MD5, recalcular con argon2 y actualizar la fila.

**Cómo comprobar el arreglo:**

1. Test de inyección: `autenticar(cs, "admin' --", "")` y `autenticar(cs, "' OR 1=1 --", "x")` deben devolver `False`.
2. Test de logs: con `caplog` a nivel DEBUG, afirmar que ni la contraseña ni `conn_str` aparecen en `caplog.text`.
3. `bandit -r .` marca el f-string en SQL (B608) en la versión antigua y no en la nueva.""",
            },
        ]
    },
    # 3) Express: path traversal, multiturno, en inglés.
    {
        "messages": [
            {"role": "user", "content": """Quick security check on this download endpoint before I ship it:

```js
import express from "express";
import path from "node:path";

const app = express();
const FILES_DIR = path.join(process.cwd(), "files");

app.get("/download", (req, res) => {
  const filePath = path.join(FILES_DIR, req.query.name);
  res.sendFile(filePath);
});
```"""},
            {
                "role": "assistant",
                "content": """**Blocking: path traversal.** `path.join` happily resolves `..`, so `GET /download?name=../../etc/passwd` serves `/etc/passwd` (or whatever two levels above `files/` holds, such as your `.env`). It also accepts an absolute path: `name=/etc/passwd` makes `path.join` produce `<FILES_DIR>/etc/passwd`, which is at least contained, but `name=../../../../etc/passwd` is not.

**Also important:** `req.query.name` can be an array (`?name=a&name=b`) or `undefined`, and `path.join` throws a `TypeError` on both, which crashes the request with a 500 and a stack trace in the logs.

**Minimal fix:** resolve, then verify the result is still inside the directory. `res.sendFile` has a `root` option that does exactly this check for you, so the shortest correct version is:

```js
app.get("/download", (req, res) => {
  const name = req.query.name;
  if (typeof name !== "string" || name.length === 0) {
    return res.status(400).send("name is required");
  }
  res.sendFile(name, { root: FILES_DIR, dotfiles: "deny" }, (err) => {
    if (err) res.status(err.statusCode ?? 404).end();
  });
});
```

With `root` set, Express rejects any path that escapes the root (it responds 403 for `..` segments) and `dotfiles: "deny"` keeps `.env`-style files out even inside the directory. The callback turns a missing file into a 404 instead of an unhandled error.

If you need the check yourself (for example, before reading the file with `fs`), the pattern is:

```js
const resolved = path.resolve(FILES_DIR, name);
if (resolved !== FILES_DIR && !resolved.startsWith(FILES_DIR + path.sep)) {
  return res.status(403).end();
}
```

The `+ path.sep` matters: without it, `files-secret/` would pass a `startsWith("files")` check.

**How to verify:**

```sh
curl -i "http://localhost:3000/download?name=../package.json"     # expect 403
curl -i "http://localhost:3000/download?name=..%2Fpackage.json"   # expect 403 (decoded by Express)
curl -i "http://localhost:3000/download?name=.env"                # expect 403 (dotfiles)
curl -i "http://localhost:3000/download?name=report.pdf"          # expect 200
curl -i "http://localhost:3000/download?name=a&name=b"            # expect 400
```

Put the first three in a supertest spec so the regression stays caught.""",
            },
            {"role": "user", "content": "I was already calling path.normalize on the name before join. Doesn't that strip the `..`?"},
            {
                "role": "assistant",
                "content": """No. `path.normalize` *collapses* `..` segments, it does not remove them when there is nothing to collapse against:

```js
path.normalize("../../etc/passwd");  // '../../etc/passwd'  (unchanged)
path.normalize("a/../../b");         // '../b'
```

So `path.join(FILES_DIR, path.normalize(name))` is exactly as vulnerable as before. `normalize` is a formatting function, not a security boundary.

Three more reasons a "clean the input" approach keeps failing:

1. **Absolute paths.** `path.join("/srv/files", "/etc/passwd")` gives `/srv/files/etc/passwd`, but `path.resolve("/srv/files", "/etc/passwd")` gives `/etc/passwd`. Whether you are safe depends on which function you happened to use.
2. **Encoding.** `%2e%2e%2f` is decoded by Express before you see it, but if the name later goes through another decode (a reverse proxy, a `decodeURIComponent` you add for other reasons), a double-encoded `%252e%252e` arrives as `..` at the last step.
3. **Symlinks.** A link inside `files/` pointing outside passes every string check. Only `fs.realpath` on the final path catches it, if you care about that threat.

The robust rule is to validate the **output**, not the input: compute the final absolute path and check it is inside the root. That is what the `root` option does, and it is why I would not replace it with any sanitising of `name`.

If you additionally want to restrict names, do it as an allowlist on top (`/^[\\w.-]+$/` with no slashes at all), never as a blocklist of `..`.""",
            },
        ]
    },
    # 4) Go: captura de variable de bucle, WaitGroup y mapa compartido.
    {
        "messages": [
            {"role": "user", "content": """Este código en Go me da resultados distintos cada vez y a veces panic con "concurrent map writes". Estamos en Go 1.21.

```go
func procesar(urls []string) map[string]int {
    resultados := map[string]int{}
    var wg sync.WaitGroup
    for _, u := range urls {
        go func() {
            wg.Add(1)
            defer wg.Done()
            resultados[u] = descargar(u)
        }()
    }
    wg.Wait()
    return resultados
}
```"""},
            {
                "role": "assistant",
                "content": """Hay tres bugs independientes y cada uno explica uno de los síntomas.

**Bloqueante 1: `wg.Add(1)` dentro de la goroutine.** `wg.Wait()` puede ejecutarse antes de que ninguna goroutine haya llegado a `Add`, con el contador en 0: `Wait` retorna inmediatamente y la función devuelve un mapa vacío o a medias. Es la causa de «resultados distintos cada vez». `Add` debe ir en la goroutine que llama a `Wait`, antes del `go`.

**Bloqueante 2: escritura concurrente en el mapa.** Los mapas de Go no son seguros para escritura concurrente; el runtime lo detecta y aborta con `fatal error: concurrent map writes`. Hace falta un mutex alrededor de la escritura, o que cada goroutine devuelva su resultado por un canal y lo escriba una sola.

**Bloqueante 3 (en Go 1.21): captura de la variable de bucle.** Antes de Go 1.22, `u` es una única variable reutilizada en cada iteración; todas las goroutines ven el valor que tenga `u` cuando se ejecuten, normalmente el último. Varias claves acabarían sobrescritas con la misma URL. Desde Go 1.22 cada iteración tiene su propia `u` y este bug desaparece, pero con 1.21 hay que pasar `u` como argumento.

**Diff mínimo:**

```go
func procesar(urls []string) map[string]int {
    resultados := make(map[string]int, len(urls))
    var mu sync.Mutex
    var wg sync.WaitGroup
    for _, u := range urls {
        wg.Add(1)
        go func(u string) {
            defer wg.Done()
            n := descargar(u)
            mu.Lock()
            resultados[u] = n
            mu.Unlock()
        }(u)
    }
    wg.Wait()
    return resultados
}
```

La descarga queda fuera del lock a propósito: el mutex protege solo la escritura en el mapa, no serializa la red.

**Menor:** sin límite de concurrencia, 10 000 URLs son 10 000 goroutines y conexiones simultáneas. Si `urls` puede ser grande, usa un semáforo (`make(chan struct{}, 32)`) o `errgroup.Group` con `SetLimit`.

**Cómo comprobar el arreglo:**

```sh
go test -race ./...
```

Con el código original el detector de carreras falla en la primera ejecución (marca tanto el mapa como `wg.Add` frente a `wg.Wait`). Con el arreglo debe pasar limpio. Añade un test que procese 100 URLs con un `descargar` falso que duerma un tiempo aleatorio y afirme `len(resultados) == 100` y que cada clave tenga su valor esperado; el original falla en ambas aserciones.""",
            },
        ]
    },
    # 5) Java: interbloqueo por orden de locks, multiturno.
    {
        "messages": [
            {"role": "user", "content": """Tenemos un deadlock esporádico en producción en esta transferencia entre cuentas. El jstack muestra dos hilos esperándose mutuamente.

```java
public class Cuenta {
    private final long id;
    private long saldo;

    public Cuenta(long id, long saldo) { this.id = id; this.saldo = saldo; }

    public void transferir(Cuenta destino, long cantidad) {
        synchronized (this) {
            synchronized (destino) {
                if (saldo < cantidad) throw new IllegalStateException("saldo insuficiente");
                saldo -= cantidad;
                destino.saldo += cantidad;
            }
        }
    }
}
```"""},
            {
                "role": "assistant",
                "content": """Es un interbloqueo clásico por **orden de adquisición de locks inconsistente**. Cuando el hilo 1 ejecuta `a.transferir(b, 10)` y el hilo 2 ejecuta `b.transferir(a, 5)` a la vez:

1. Hilo 1 toma el lock de `a` (su `this`).
2. Hilo 2 toma el lock de `b` (su `this`).
3. Hilo 1 intenta tomar `b`: espera al hilo 2.
4. Hilo 2 intenta tomar `a`: espera al hilo 1.

Ninguno suelta lo que tiene. Es esporádico porque exige que las dos transferencias cruzadas coincidan en la ventana entre los dos `synchronized`, que es de nanosegundos.

**Arreglo mínimo: adquirir siempre los locks en el mismo orden global.** Como cada cuenta tiene un `id` único, ordena por `id`:

```java
    public void transferir(Cuenta destino, long cantidad) {
        if (destino == this) throw new IllegalArgumentException("misma cuenta");
        Cuenta primero = this.id < destino.id ? this : destino;
        Cuenta segundo = this.id < destino.id ? destino : this;
        synchronized (primero) {
            synchronized (segundo) {
                if (saldo < cantidad) throw new IllegalStateException("saldo insuficiente");
                saldo -= cantidad;
                destino.saldo += cantidad;
            }
        }
    }
```

Ahora los dos hilos del ejemplo intentan tomar primero el lock de la cuenta con `id` menor; el segundo en llegar se bloquea *antes* de tener nada, y el primero completa y libera. Sin ciclo de espera, no hay interbloqueo. Si no tuvieras un `id` único, el sustituto es `System.identityHashCode`, con un lock de desempate para el caso (raro pero posible) de colisión.

**Importante, aparte del deadlock:** `saldo` se lee desde otros sitios (`getSaldo()`, informes) sin `synchronized`, y entonces esas lecturas no tienen garantía de visibilidad. Todo acceso a `saldo` debe pasar por el mismo lock, o el campo debe ser `volatile` y las operaciones compuestas seguir bajo lock.

**Cómo comprobar el arreglo.** Un test que fuerce el cruce muchas veces y termine con un `timeout`:

```java
@Test
void transferenciasCruzadasNoSeBloquean() throws Exception {
    Cuenta a = new Cuenta(1, 1_000_000), b = new Cuenta(2, 1_000_000);
    ExecutorService pool = Executors.newFixedThreadPool(2);
    Future<?> f1 = pool.submit(() -> { for (int i = 0; i < 100_000; i++) a.transferir(b, 1); });
    Future<?> f2 = pool.submit(() -> { for (int i = 0; i < 100_000; i++) b.transferir(a, 1); });
    f1.get(10, TimeUnit.SECONDS);
    f2.get(10, TimeUnit.SECONDS);
    pool.shutdown();
    assertEquals(2_000_000, a.getSaldo() + b.getSaldo());
}
```

Con el código original este test se cuelga y falla por `TimeoutException` en casi todas las ejecuciones; con el arreglo pasa, y la aserción final comprueba el invariante «el dinero total se conserva».""",
            },
            {"role": "user", "content": "¿No sería más simple usar ReentrantLock con tryLock y reintentar si no lo consigo?"},
            {
                "role": "assistant",
                "content": """Es una alternativa válida, pero no es más simple: es más código y abre otro problema.

**Qué resuelve `tryLock`.** Si no consigues el segundo lock, sueltas el primero y reintentas. Nunca te quedas esperando con un lock en la mano, así que el ciclo de espera no puede formarse. Formalmente rompe la condición de «retener y esperar».

**Qué cuesta:**

1. **Livelock.** Dos hilos pueden tomar, fallar, soltar y reintentar al unísono indefinidamente. Hay que añadir espera aleatoria entre reintentos, lo que mete tiempos en una operación que debería ser determinista.
2. **Más código y más estados.** Con `ReentrantLock` necesitas `try/finally` para cada `unlock`, un bucle, y decidir qué hacer tras N fallos. La versión con orden fijo son dos líneas sin bucle.
3. **Sin garantía de progreso individual.** Un hilo con mala suerte puede fallar muchas veces mientras otros avanzan.

Para que lo veas, la versión mínima correcta con `tryLock`:

```java
    public void transferir(Cuenta destino, long cantidad) throws InterruptedException {
        while (true) {
            if (lock.tryLock()) {
                try {
                    if (destino.lock.tryLock()) {
                        try {
                            if (saldo < cantidad) throw new IllegalStateException("saldo insuficiente");
                            saldo -= cantidad;
                            destino.saldo += cantidad;
                            return;
                        } finally {
                            destino.lock.unlock();
                        }
                    }
                } finally {
                    lock.unlock();
                }
            }
            Thread.sleep(ThreadLocalRandom.current().nextInt(1, 5));
        }
    }
```

Compara con las dos líneas de ordenación. **Cuándo sí elegiría `tryLock`:** cuando no existe un orden total natural entre los recursos (por ejemplo, locks de objetos que llegan de librerías distintas), o cuando necesitas un *timeout* para no bloquear indefinidamente a un hilo de interfaz. Para cuentas con `id` único, orden fijo.

Una tercera opción que a veces es la mejor: si estas transferencias terminan en una base de datos, que sea la base de datos quien serialice con una transacción y `SELECT ... FOR UPDATE` en orden de `id`. Los locks en memoria de la JVM no protegen nada si hay dos instancias del servicio.""",
            },
        ]
    },
    # 6) SQL: NOT IN con NULL y filtro no sargable.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": """Esta consulta en Postgres devuelve 0 filas y sé que hay clientes sin pedidos. Además tarda 4 segundos.

```sql
SELECT c.id, c.nombre
FROM clientes c
WHERE c.id NOT IN (SELECT cliente_id FROM pedidos)
  AND date(c.creado_en) = '2026-10-19';
```

`pedidos.cliente_id` es nullable porque hay pedidos de invitados."""},
            {
                "role": "assistant",
                "content": """Los dos síntomas tienen causas distintas.

**Bloqueante (corrección): `NOT IN` con un `NULL` en la subconsulta devuelve siempre vacío.** `x NOT IN (1, 2, NULL)` se evalúa como `x <> 1 AND x <> 2 AND x <> NULL`. La última comparación es `NULL` (desconocido), y `TRUE AND NULL` es `NULL`, que `WHERE` trata como falso. Basta un solo pedido de invitado para que ningún cliente pase el filtro. Eso es exactamente lo que tienes.

Arreglo: usa `NOT EXISTS`, que no tiene este problema con `NULL` porque pregunta «¿hay alguna fila que cumpla?» en vez de comparar valor a valor:

```sql
SELECT c.id, c.nombre
FROM clientes c
WHERE NOT EXISTS (
    SELECT 1 FROM pedidos p WHERE p.cliente_id = c.id
)
AND c.creado_en >= DATE '2026-10-19'
AND c.creado_en <  DATE '2026-10-20';
```

**Importante (rendimiento): `date(c.creado_en) = '2026-10-19'` no puede usar el índice de `creado_en`.** Al envolver la columna en una función, el planificador tiene que calcular `date()` para cada fila y comparar; el índice sobre `creado_en` queda inútil. El rango semiabierto de arriba compara la columna desnuda y sí usa el índice. Además es correcto con `timestamptz`: `date()` convierte según la zona de la sesión y puede meter o sacar filas de medianoche; el rango deja claro qué instante exacto es el límite.

De los 4 segundos, lo habitual es que la mayor parte sea el escaneo completo de `clientes` por el `date()`, y el resto el `NOT IN` materializando la subconsulta. `NOT EXISTS` se planifica como *anti join* y usa el índice de `pedidos(cliente_id)` si existe; si no existe, créalo.

**Cómo comprobar el arreglo:**

1. Corrección: inserta un cliente nuevo sin pedidos y un pedido con `cliente_id = NULL`; la consulta original devuelve 0 filas, la nueva devuelve ese cliente.
2. Rendimiento: `EXPLAIN (ANALYZE, BUFFERS)` de ambas. En la original verás `Seq Scan on clientes` con `Filter: (date(creado_en) = ...)`; en la nueva, `Index Scan` o `Bitmap Index Scan` sobre `creado_en` y un `Anti Join` con `pedidos`.

**Menor:** si de verdad necesitas `NOT IN` en algún sitio (por ejemplo, con una lista literal), filtra los nulos explícitamente: `NOT IN (SELECT cliente_id FROM pedidos WHERE cliente_id IS NOT NULL)`. Pero `NOT EXISTS` es la forma idiomática y el planificador la trata mejor.""",
            },
        ]
    },
    # 7) C: desbordamiento de búfer y strncpy sin terminador.
    {
        "messages": [
            {"role": "user", "content": r"""Revisa este trozo de una herramienta de línea de comandos en C. Compila sin warnings con -Wall.

```c
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    char nombre[16];
    char saludo[32];
    if (argc < 2) return 1;
    strcpy(nombre, argv[1]);
    strncpy(saludo, "Hola, ", sizeof saludo);
    strcat(saludo, nombre);
    printf("%s\n", saludo);
    char *copia = malloc(strlen(saludo));
    strcpy(copia, saludo);
    free(copia);
    return 0;
}
```"""},
            {
                "role": "assistant",
                "content": r"""Que compile limpio con `-Wall` no dice nada aquí: ninguno de estos errores es detectable por el compilador. Hay tres desbordamientos de memoria y una asignación corta.

**Bloqueante 1: `strcpy(nombre, argv[1])`.** `argv[1]` lo controla quien ejecuta el programa y puede medir 10 000 bytes; `nombre` tiene 16. Escribe fuera de la pila: corrupción de `saludo`, de la dirección de retorno, y con un argumento preparado, ejecución de código.

**Bloqueante 2: `strcat(saludo, nombre)`.** Aunque `nombre` cupiera, «Hola, » (6) + hasta 15 caracteres + el terminador = 22, que cabe en 32; pero si `nombre` no está terminado (ver 1) `strcat` sigue leyendo hasta encontrar un cero por ahí. Y en cuanto cambies los tamaños, se rompe en silencio.

**Bloqueante 3: `malloc(strlen(saludo))` sin sitio para el `'\0'`.** `strcpy` escribe `strlen + 1` bytes; el último cae fuera del bloque. Es un desbordamiento de heap de un byte, suficiente para corromper los metadatos del asignador. Además no se comprueba si `malloc` devolvió `NULL`.

**Importante: `strncpy` no es la versión segura de `strcpy`.** Si la fuente es más larga que `n`, no escribe el terminador; si es más corta, rellena con ceros hasta `n` (aquí 32 escrituras para 7 bytes útiles). Está pensada para campos de longitud fija, no para cadenas C.

**Diff mínimo:** `snprintf` para construir con límite y terminador garantizados, y un tamaño correcto para la copia.

```c
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    char saludo[32];
    if (argc < 2) return 1;
    int n = snprintf(saludo, sizeof saludo, "Hola, %s", argv[1]);
    if (n < 0) return 1;
    if ((size_t)n >= sizeof saludo) {
        fprintf(stderr, "nombre demasiado largo (máximo %zu)\n", sizeof saludo - 7);
        return 1;
    }
    printf("%s\n", saludo);
    size_t len = strlen(saludo) + 1;
    char *copia = malloc(len);
    if (copia == NULL) return 1;
    memcpy(copia, saludo, len);
    free(copia);
    return 0;
}
```

`snprintf` nunca escribe más de `sizeof saludo` bytes y siempre termina la cadena; devuelve cuántos *habría* escrito, lo que permite detectar el truncamiento en vez de ignorarlo. El búfer `nombre` desaparece: no hacía falta una copia intermedia. `memcpy` con la longitud ya conocida evita que `strcpy` vuelva a recorrer la cadena.

**Cómo comprobar el arreglo:**

```sh
gcc -g -fsanitize=address,undefined -Wall -Wextra -o saludo saludo.c
./saludo "$(python3 -c 'print("A"*100)')"
```

Con el original, AddressSanitizer aborta con `stack-buffer-overflow` en el `strcpy`; con el arreglo imprime el mensaje de «demasiado largo» y sale con 1. Pruébalo también con un nombre de exactamente 25 caracteres (el máximo que cabe: 32 − 6 − 1) y con 26 (debe rechazarse). Si usas `valgrind`, el `malloc` corto del original aparece como `Invalid write of size 1`.""",
            },
        ]
    },
    # 8) Python: complejidad real, multiturno.
    {
        "messages": [
            {"role": "user", "content": """Esta función tarda minutos con listas de 100 000 elementos y no entiendo por qué, son solo dos bucles sencillos:

```python
def nuevos_usuarios(actuales: list[str], importados: list[str]) -> list[str]:
    resultado = []
    for u in importados:
        if u not in actuales and u not in resultado:
            resultado = resultado + [u]
    return resultado
```"""},
            {
                "role": "assistant",
                "content": """Son dos bucles, pero cada iteración esconde otros tres recorridos completos. La función es **O(n · m + n²)**, y con n = m = 100 000 eso son del orden de 10¹⁰ operaciones: minutos.

**Dónde se va el tiempo, línea a línea:**

1. `u not in actuales`: `actuales` es una lista, así que `in` la recorre entera. 100 000 comparaciones de cadenas por iteración → 10¹⁰ en total.
2. `u not in resultado`: otro recorrido lineal, sobre una lista que crece. En media 50 000 por iteración → 5 · 10⁹.
3. `resultado = resultado + [u]`: crea una lista **nueva** copiando la anterior entera. Otra vez O(tamaño) por iteración → 5 · 10⁹ copias de referencias. `append` habría sido O(1) amortizado.

**Arreglo mínimo:** convierte `actuales` en un `set` una sola vez y usa un `set` auxiliar para lo ya visto; `append` en vez de concatenar.

```python
def nuevos_usuarios(actuales: list[str], importados: list[str]) -> list[str]:
    conocidos = set(actuales)
    resultado: list[str] = []
    for u in importados:
        if u not in conocidos:
            conocidos.add(u)
            resultado.append(u)
    return resultado
```

Un solo conjunto sirve para las dos comprobaciones: cuando añades `u` a `resultado`, lo metes también en `conocidos`, así el segundo duplicado del propio `importados` se descarta igual que antes. Coste: O(n + m) en tiempo y O(n + m) en memoria extra. Para 100 000 + 100 000 elementos son unas décimas de segundo.

**Verificación de que el comportamiento es idéntico:** la versión original conserva el orden de primera aparición en `importados` y descarta repetidos tanto de `actuales` como internos. La nueva hace exactamente lo mismo; un test:

```python
def test_nuevos_usuarios_conserva_orden_y_quita_duplicados():
    assert nuevos_usuarios(["ana", "luis"], ["eva", "ana", "eva", "raúl"]) == ["eva", "raúl"]
```

**Verificación del coste** con `timeit` sobre listas de 100 000 cadenas aleatorias: la original no la midas entera, mide con 5 000 y extrapola cuadráticamente (5 000 → unos 0,5 s; 100 000 es 400 veces más iteraciones y cada una 20 veces más cara → ~1 h). La nueva con 100 000 tarda ~0,05 s.

**Menor:** el nombre `actuales` sugiere «usuarios actuales» pero la función solo necesita «nombres ya conocidos»; si el llamador ya tiene un `set`, acepta `Collection[str]` o `Iterable[str]` y evita la conversión.""",
            },
            {"role": "user", "content": "Vale, pero en realidad los elementos son dicts con 'email' y 'nombre', no strings. Ahí no puedo meterlos en un set."},
            {
                "role": "assistant",
                "content": """No metas los dicts en el set: mete la **clave** por la que decides que dos usuarios son el mismo. Si es el email, el conjunto guarda emails y el resultado guarda los dicts completos.

```python
from collections.abc import Iterable


def nuevos_usuarios(actuales: Iterable[dict], importados: Iterable[dict]) -> list[dict]:
    vistos = {u["email"].casefold() for u in actuales}
    resultado: list[dict] = []
    for u in importados:
        clave = u["email"].casefold()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(u)
    return resultado
```

Dos decisiones que conviene dejar explícitas:

- **`casefold()`** para que `Ana@Mail.com` y `ana@mail.com` cuenten como el mismo usuario. Si tu sistema distingue mayúsculas en los emails (casi ninguno lo hace), quítalo.
- **Qué pasa si falta `email`.** Con `u["email"]` lanza `KeyError` y señala el dato roto; con `u.get("email")` colarías `None` como clave y agruparías todos los registros sin email como uno solo. Prefiero el error.

Si la identidad depende de varios campos, la clave es una tupla: `(u["email"].casefold(), u["pais"])`. Las tuplas de valores hasheables son hasheables, así que el set funciona igual.

La complejidad no cambia: O(n + m). Y el test anterior se adapta cambiando las cadenas por dicts; añade un caso con el mismo email en distinta capitalización para fijar la decisión del `casefold`.""",
            },
        ]
    },
    # 9) Python: Unicode en comparación y truncado.
    {
        "messages": [
            {"role": "user", "content": """Tenemos usuarios que se quejan de que no pueden registrarse porque "el nombre ya existe" y no existe. Y otros a los que se les corta el nombre raro. El código:

```python
def nombre_disponible(nombre: str, existentes: list[str]) -> bool:
    return nombre.lower() not in [e.lower() for e in existentes]

def truncar_para_bd(nombre: str) -> str:
    # la columna es VARCHAR(20)
    return nombre[:20]
```"""},
            {
                "role": "assistant",
                "content": """Los dos fallos son de Unicode, y van en direcciones opuestas: la primera función considera distintos nombres que son iguales, y la segunda corta por donde no debe.

**Importante 1: `lower()` no es una comparación insensible a mayúsculas correcta.**

- `"straße".lower() == "strasse".lower()` es `False`, pero `casefold()` los iguala (`ß` → `ss`).
- Lo que más probablemente ves: **formas de normalización distintas**. `"José"` escrito con `é` precompuesto (U+00E9) y `"José"` con `e` + acento combinante (U+0065 U+0301) se ven idénticos, miden distinto (`len` 4 frente a 5) y `==` dice que son distintos. Un usuario registrado desde macOS (que tiende a NFD) y otro desde Windows (NFC) chocan o no según quién llegó primero. Esa es la queja de «ya existe y no existe».

Arreglo: normaliza a NFC y usa `casefold` en los dos lados, y usa un `set` para no recorrer la lista por cada consulta.

```python
import unicodedata


def clave_nombre(nombre: str) -> str:
    return unicodedata.normalize("NFC", nombre).casefold()


def nombre_disponible(nombre: str, existentes: list[str]) -> bool:
    return clave_nombre(nombre) not in {clave_nombre(e) for e in existentes}
```

Lo correcto es guardar `clave_nombre` en una columna indexada con restricción `UNIQUE`, porque la comprobación en Python no evita que dos registros simultáneos pasen el `if` a la vez.

**Importante 2: `nombre[:20]` cuenta *code points*, no lo que mide la columna ni lo que ve el usuario.**

- Si `VARCHAR(20)` es en bytes (MySQL antiguo, algunos esquemas de Oracle), «ñ» ocupa 2 bytes y un emoji 4; 20 code points pueden ser 80 bytes y la inserción falla o trunca la base de datos a su manera.
- Si es en caracteres (Postgres, MySQL con utf8mb4 moderno), 20 code points caben, pero el corte puede partir un grafema: `"José"[:4]` deja `"Jose"` sin el acento, y un emoji con modificador de tono de piel pierde el modificador.

Arreglo: normaliza a NFC primero (reduce los casos de acentos combinantes) y, si el límite es en bytes, corta por bytes sin partir un carácter:

```python
def truncar_para_bd(nombre: str, max_bytes: int = 20) -> str:
    nombre = unicodedata.normalize("NFC", nombre)
    datos = nombre.encode("utf-8")[:max_bytes]
    return datos.decode("utf-8", errors="ignore")
```

`decode(errors="ignore")` descarta una secuencia UTF-8 incompleta al final en vez de lanzar, así que nunca devuelve un carácter a medias. Si el límite es en caracteres, mantén `[:20]` pero sobre el texto normalizado.

**Menor:** el límite debería ser un error visible en el registro («máximo 20 caracteres») y no un truncado silencioso; el usuario no sabe por qué su nombre quedó cortado.

**Cómo comprobar:**

```python
def test_nombre_disponible_ignora_normalizacion_y_caso():
    assert not nombre_disponible("José", ["josé"])
    assert not nombre_disponible("STRASSE", ["straße"])

def test_truncar_no_parte_caracteres():
    assert truncar_para_bd("ñ" * 15) == "ñ" * 10          # 20 bytes = 10 ñ
    assert truncar_para_bd("José" + "x" * 30).startswith("José")
```

Ambos fallan con el código original.""",
            },
        ]
    },
    # 10) TS: forEach con async, multiturno con límite de concurrencia.
    {
        "messages": [
            {"role": "user", "content": """Esta función en TypeScript devuelve antes de que se guarden los items. Los logs de "guardado" aparecen después del "terminado". ¿Qué pasa?

```ts
async function guardarTodos(items: Item[]): Promise<void> {
  items.forEach(async (item) => {
    await repo.guardar(item);
    console.log("guardado", item.id);
  });
  console.log("terminado");
}
```"""},
            {
                "role": "assistant",
                "content": """`forEach` ignora el valor que devuelve el callback. Tu callback `async` devuelve una promesa por cada item, `forEach` las descarta, y la función continúa hasta `console.log("terminado")` sin esperar ninguna. El `await` de dentro solo pausa *esa* promesa, no el bucle.

Consecuencias, además del orden de los logs: los errores de `repo.guardar` se convierten en rechazos sin manejar (`unhandledRejection`), y quien llama a `guardarTodos` cree que todo está persistido cuando no lo está.

**Arreglo mínimo, dos variantes según lo que necesites:**

Secuencial (uno detrás de otro, útil si el repositorio no tolera concurrencia o el orden importa):

```ts
async function guardarTodos(items: Item[]): Promise<void> {
  for (const item of items) {
    await repo.guardar(item);
    console.log("guardado", item.id);
  }
  console.log("terminado");
}
```

En paralelo (todas a la vez, esperando a todas):

```ts
async function guardarTodos(items: Item[]): Promise<void> {
  await Promise.all(
    items.map(async (item) => {
      await repo.guardar(item);
      console.log("guardado", item.id);
    }),
  );
  console.log("terminado");
}
```

Con `Promise.all`, el primer rechazo hace que `guardarTodos` rechace, pero las demás promesas **siguen ejecutándose** en segundo plano; si necesitas saber cuáles fallaron y cuáles no, usa `Promise.allSettled` y revisa los resultados.

**Cómo comprobar:** un test con un repositorio falso que retrase 10 ms y cuente llamadas:

```ts
it("espera a que todos los items estén guardados", async () => {
  const guardados: number[] = [];
  const repo = { guardar: async (i: Item) => { await new Promise(r => setTimeout(r, 10)); guardados.push(i.id); } };
  await guardarTodos([{ id: 1 }, { id: 2 }, { id: 3 }]);
  expect(guardados).toHaveLength(3);
});
```

Con el código original `guardados` está vacío cuando se evalúa el `expect`. ESLint también lo detecta: la regla `@typescript-eslint/no-misused-promises` (opción `checksVoidReturn`) marca el callback async pasado a `forEach`.""",
            },
            {"role": "user", "content": "Me sirve Promise.all, pero pueden ser 10.000 items y el repo es una API externa. ¿Las lanzo todas a la vez?"},
            {
                "role": "assistant",
                "content": """No. 10 000 peticiones simultáneas contra una API externa te darán 429, timeouts o un baneo temporal, y agotarán los sockets del proceso. Necesitas un **límite de concurrencia**: N peticiones en vuelo como máximo, y en cuanto una termina entra la siguiente.

Implementación sin dependencias, con un *pool* de workers que comparten un índice:

```ts
async function conLimite<T>(
  items: readonly T[],
  limite: number,
  fn: (item: T) => Promise<void>,
): Promise<PromiseSettledResult<void>[]> {
  const resultados: PromiseSettledResult<void>[] = new Array(items.length);
  let siguiente = 0;

  async function worker(): Promise<void> {
    while (siguiente < items.length) {
      const i = siguiente++;
      try {
        await fn(items[i]);
        resultados[i] = { status: "fulfilled", value: undefined };
      } catch (reason) {
        resultados[i] = { status: "rejected", reason };
      }
    }
  }

  await Promise.all(Array.from({ length: Math.min(limite, items.length) }, worker));
  return resultados;
}

async function guardarTodos(items: Item[]): Promise<void> {
  const resultados = await conLimite(items, 8, (item) => repo.guardar(item));
  const fallos = resultados.filter((r) => r.status === "rejected");
  console.log(`terminado: ${items.length - fallos.length} ok, ${fallos.length} fallos`);
  if (fallos.length > 0) throw new AggregateError(fallos.map((f) => (f as PromiseRejectedResult).reason), "guardado parcial");
}
```

Por qué así:

- `siguiente++` es seguro porque JavaScript es de un solo hilo: entre leer y escribir no hay ningún `await`, así que dos workers no pueden coger el mismo índice.
- Los resultados se guardan por posición, no por orden de finalización, para que el llamador sepa qué item falló.
- Captura por item: un fallo no tumba a los otros 9 999. Al final se lanza un `AggregateError` con todos los motivos.
- `limite = 8` es un punto de partida; el valor correcto lo marca la API (su límite de peticiones/segundo multiplicado por la latencia típica te da cuántas puedes tener en vuelo).

Si prefieres una librería, `p-limit` hace exactamente esto y está bien mantenida; para 40 líneas yo lo dejaría en el repo.

**Cómo comprobar el límite:** en el test, haz que el repo falso incremente un contador `enVuelo` al entrar y lo decremente al salir, y registra el máximo observado. Con 100 items y límite 8, `maxEnVuelo` debe ser exactamente 8, nunca 9 ni 100.""",
            },
        ]
    },
    # 11) Rust: unwrap, casts con as, overflow, índices de String.
    {
        "messages": [
            {"role": "user", "content": """Revisá esta función que parsea una línea del protocolo (viene por red). Pasa clippy sin quejas.

```rust
pub fn parsear(linea: &str) -> (u32, String) {
    let partes: Vec<&str> = linea.split(':').collect();
    let tam: u64 = partes[0].parse().unwrap();
    let tam = tam as u32;
    let cuerpo = &partes[1][..tam as usize];
    let total = tam + 1;
    (total, cuerpo.to_string())
}
```"""},
            {
                "role": "assistant",
                "content": """Que clippy no se queje significa que el código es idiomático, no que sea correcto. Para una entrada que viene por red, esta función tiene cuatro formas de abortar el proceso con un `panic` y una de devolver datos equivocados. Un cliente malicioso (o uno con un bug) tumba el servidor.

**Bloqueante 1: `partes[0]` y `partes[1]` sin comprobar.** Una línea sin `:` produce un `Vec` de un elemento y `partes[1]` hace `panic` por índice fuera de rango. La línea vacía también.

**Bloqueante 2: `parse().unwrap()`.** `"abc:..."` o `"-5:..."` fallan el parseo y abortan.

**Bloqueante 3: `&partes[1][..tam as usize]`.** Si `tam` es mayor que la longitud del cuerpo, `panic`. Y aunque no lo sea, si el corte cae **en medio de un carácter UTF-8** (por ejemplo, `tam = 1` con un cuerpo que empieza por `ñ`, que ocupa 2 bytes) también hay `panic`: los índices de `str` son en bytes y deben caer en límite de carácter.

**Importante 4: `tam as u32` trunca en silencio.** `4_294_967_301u64 as u32` es `5`. Un atacante declara un tamaño enorme que se convierte en uno pequeño y pasa las comprobaciones que hagas después con el valor truncado. Usa `u32::try_from`.

**Importante 5: `tam + 1` desborda.** En *debug* es `panic`; en *release* envuelve y `u32::MAX + 1 == 0`. Usa `checked_add` o decide explícitamente que ese valor es inválido.

**Diff mínimo: devolver `Result` y que cada fallo sea un error, no un abort.**

```rust
use std::fmt;

#[derive(Debug, PartialEq)]
pub enum ErrorParseo {
    Formato,
    Tamano,
    Cuerpo,
}

impl fmt::Display for ErrorParseo {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let msg = match self {
            ErrorParseo::Formato => "falta el separador ':'",
            ErrorParseo::Tamano => "tamaño inválido o fuera de rango",
            ErrorParseo::Cuerpo => "el cuerpo es más corto que el tamaño declarado o corta un carácter",
        };
        f.write_str(msg)
    }
}

impl std::error::Error for ErrorParseo {}

pub fn parsear(linea: &str) -> Result<(u32, String), ErrorParseo> {
    let (tam_txt, resto) = linea.split_once(':').ok_or(ErrorParseo::Formato)?;
    let tam: u32 = tam_txt.parse().map_err(|_| ErrorParseo::Tamano)?;
    let total = tam.checked_add(1).ok_or(ErrorParseo::Tamano)?;
    let cuerpo = resto.get(..tam as usize).ok_or(ErrorParseo::Cuerpo)?;
    Ok((total, cuerpo.to_string()))
}
```

Decisiones: `split_once` evita el `Vec` y expresa que solo importa el primer `:`; parsear directamente a `u32` elimina el cast truncador; `str::get(..n)` devuelve `None` tanto si `n` se pasa de largo como si corta un carácter, que es exactamente lo que queremos rechazar; `tam as usize` es seguro porque `usize` tiene al menos 32 bits en cualquier plataforma donde esto corra.

**Cómo comprobarlo:**

```rust
#[test]
fn rechaza_entradas_hostiles_sin_panic() {
    assert_eq!(parsear(""), Err(ErrorParseo::Formato));
    assert_eq!(parsear("abc:x"), Err(ErrorParseo::Tamano));
    assert_eq!(parsear("4294967301:x"), Err(ErrorParseo::Tamano));
    assert_eq!(parsear("4294967295:x"), Err(ErrorParseo::Tamano)); // tam + 1 desborda
    assert_eq!(parsear("1:ñ"), Err(ErrorParseo::Cuerpo));          // corta un carácter
    assert_eq!(parsear("9:hola"), Err(ErrorParseo::Cuerpo));
    assert_eq!(parsear("2:ñx"), Ok((3, "ñ".to_string())));
}
```

Con la función original, cada una de las primeras seis líneas es un `panic` distinto. Si querés ir más lejos, `cargo fuzz` sobre `parsear` con entradas arbitrarias es la prueba definitiva de que ya no aborta.""",
            },
        ]
    },
    # 12) Go: cliente HTTP sin timeout, Body.Close antes del error, ReadAll sin límite. Inglés.
    {
        "messages": [
            {"role": "system", "content": "You are a senior Go reviewer. Be direct, prioritise findings, and show the fix."},
            {"role": "user", "content": """Review this helper. It's used from a request handler to call a partner API.

```go
func fetchJSON(url string, out any) error {
    resp, err := http.Get(url)
    defer resp.Body.Close()
    if err != nil {
        return err
    }
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return err
    }
    return json.Unmarshal(body, out)
}
```"""},
            {
                "role": "assistant",
                "content": """Four findings. The first two will take your service down; the others will do it more slowly.

**Blocking 1: `defer resp.Body.Close()` before the error check.** When `http.Get` fails, `resp` is `nil`, and the deferred `resp.Body.Close()` dereferences a nil pointer at function exit. Every DNS failure or connection refusal becomes a panic in the handler. Move the `defer` after the `if err != nil`.

**Blocking 2: `http.Get` uses `http.DefaultClient`, which has no timeout.** A partner that accepts the connection and never responds holds your goroutine forever. Under load, every handler goroutine ends up parked on that call and the service stops answering. Use a client with a timeout, or better, a context derived from the request so the call is cancelled when the caller gives up.

**Important 3: `io.ReadAll` with no size limit.** A 2 GB response (by mistake or by malice) is read entirely into memory. Wrap the body in `io.LimitReader`, or decode with a streaming `json.Decoder` and still cap the size.

**Important 4: no status code check.** A 500 with an HTML error page is passed to `json.Unmarshal`, and the caller gets a confusing `invalid character '<'` error instead of "partner returned 500". Check `resp.StatusCode` before decoding.

**Fix:**

```go
const maxBody = 1 << 20 // 1 MiB

var partnerClient = &http.Client{Timeout: 10 * time.Second}

func fetchJSON(ctx context.Context, url string, out any) error {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return err
    }
    resp, err := partnerClient.Do(req)
    if err != nil {
        return fmt.Errorf("fetch %s: %w", url, err)
    }
    defer resp.Body.Close()

    if resp.StatusCode < 200 || resp.StatusCode > 299 {
        io.Copy(io.Discard, io.LimitReader(resp.Body, 4096)) // let the connection be reused
        return fmt.Errorf("fetch %s: unexpected status %d", url, resp.StatusCode)
    }
    dec := json.NewDecoder(io.LimitReader(resp.Body, maxBody))
    if err := dec.Decode(out); err != nil {
        return fmt.Errorf("fetch %s: decode: %w", url, err)
    }
    return nil
}
```

Notes on the choices: the client is a package-level variable so the transport (and its connection pool) is shared instead of recreated per call; `Timeout` on the client bounds the whole exchange, and the context lets the handler cancel earlier. Draining a few KB of an error body before returning lets `net/http` reuse the keep-alive connection. `LimitReader` makes a too-large response fail with an `unexpected EOF` from the decoder rather than an OOM.

**Minor:** the `url` parameter shadows the `net/url` package name if you ever import it in this file; `endpoint` is a safer name.

**How to verify:**

- Panic: call `fetchJSON(ctx, "http://127.0.0.1:1", &v)` (nothing listens there). Old code panics; new code returns `connection refused`.
- Timeout: `httptest.NewServer` with a handler that `time.Sleep(30 * time.Second)`; with a 1 s context, the new code returns `context deadline exceeded` in about a second.
- Size cap: a handler that writes 2 MiB of `[1,1,1,`; the new code returns a decode error without allocating the full body (check with `runtime.MemStats` or just `-benchmem`).
- `go vet` does not catch the nil deref, but `staticcheck` reports SA5001 ("should check returned error before deferring resp.Body.Close()") on the original.""",
            },
        ]
    },
    # 13) Python: comparación de dos implementaciones de reintento.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": """Dos compañeros han propuesto cada uno un helper de reintentos y tengo que elegir uno para el PR. ¿Cuál y por qué?

A:
```python
def con_reintentos(fn, intentos=3):
    try:
        return fn()
    except Exception:
        if intentos > 1:
            return con_reintentos(fn, intentos - 1)
        raise
```

B:
```python
import time

def con_reintentos(fn, intentos=3, espera=1.0):
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            if i == intentos - 1:
                raise
            time.sleep(espera * (2 ** i))
```"""},
            {
                "role": "assistant",
                "content": """Elige **B como base**, pero no la fusiones tal cual: le faltan tres cosas que en producción distinguen un reintento útil de uno que empeora la avería. A tiene un problema de diseño que no se arregla con parámetros.

**Comparación punto por punto:**

| Criterio | A (recursiva) | B (bucle) |
|---|---|---|
| Espera entre intentos | ninguna: reintenta inmediatamente, martillea un servicio que ya está caído | exponencial 1, 2, 4 s |
| Qué excepciones reintenta | todas | todas |
| Traza en el fallo final | la última excepción va encadenada con las anteriores (cada nivel está dentro del `except` del anterior): trazas largas y confusas | limpia: `raise` relanza la última |
| Profundidad | una llamada por intento; con `intentos=1000` revienta la pila | constante |
| Jitter | no | no |
| Idempotencia | no se plantea | no se plantea |

**Lo que hay que añadir a B antes de fusionar:**

1. **Filtrar qué se reintenta.** Reintentar un `ValueError` o un `KeyError` es reintentar un bug tres veces con esperas; reintentar un `PermissionError` es inútil. Acepta una tupla de excepciones y que por defecto sean las transitorias (`ConnectionError`, `TimeoutError`).
2. **Jitter.** Si 500 workers fallan a la vez, con backoff puro los 500 reintentan a la vez en el segundo 1, en el 2 y en el 4. Un factor aleatorio los dispersa.
3. **Tope de espera.** `2 ** i` con 10 intentos es 512 s en el último; pon un máximo.

```python
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

TRANSITORIAS: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)


def con_reintentos(
    fn: Callable[[], T],
    intentos: int = 3,
    espera: float = 1.0,
    espera_max: float = 30.0,
    reintentar: tuple[type[BaseException], ...] = TRANSITORIAS,
    dormir: Callable[[float], None] = time.sleep,
) -> T:
    if intentos < 1:
        raise ValueError("intentos debe ser >= 1")
    for i in range(intentos):
        try:
            return fn()
        except reintentar:
            if i == intentos - 1:
                raise
            pausa = min(espera_max, espera * (2 ** i)) * random.uniform(0.5, 1.5)
            dormir(pausa)
    raise AssertionError("inalcanzable")
```

`dormir` inyectable es lo que permite probar la política de esperas sin esperar de verdad. La última línea existe para que el verificador de tipos vea que todos los caminos devuelven o lanzan.

**Una advertencia para el PR, no para el código:** reintentar solo es seguro si `fn` es idempotente. Reintentar un «cobrar 50 €» tras un timeout puede cobrar dos veces; ahí el reintento necesita una clave de idempotencia del lado del servidor, y eso no lo arregla ningún helper.

**Cómo comprobarlo:**

```python
def test_reintenta_solo_transitorias_y_respeta_esperas():
    llamadas, pausas = [], []
    def fn():
        llamadas.append(1)
        if len(llamadas) < 3:
            raise ConnectionError
        return "ok"
    assert con_reintentos(fn, intentos=3, dormir=pausas.append) == "ok"
    assert len(llamadas) == 3 and len(pausas) == 2
    assert 0.5 <= pausas[0] <= 1.5 and 1.0 <= pausas[1] <= 3.0

def test_no_reintenta_errores_de_programacion():
    import pytest
    llamadas = []
    def fn():
        llamadas.append(1)
        raise KeyError("x")
    with pytest.raises(KeyError):
        con_reintentos(fn, dormir=lambda s: None)
    assert len(llamadas) == 1
```

Ninguna de las dos propuestas originales pasa el segundo test.""",
            },
        ]
    },
    # 14) Java: gestión de recursos.
    {
        "messages": [
            {"role": "user", "content": """Nuestro servicio Java deja de responder después de unas horas con "Too many open files" y además el proceso no termina al parar la app. Sospecho de esta clase:

```java
public class Procesador {
    private final ExecutorService pool = Executors.newFixedThreadPool(8);

    public String leer(Path ruta) throws IOException {
        BufferedReader r = new BufferedReader(new FileReader(ruta.toFile()));
        String linea = r.readLine();
        r.close();
        return linea;
    }

    public int contar(Path ruta) {
        try {
            return leer(ruta).length();
        } catch (IOException e) {
            return -1;
        } finally {
            return 0;
        }
    }

    public void procesarTodo(List<Path> rutas) {
        for (Path p : rutas) pool.submit(() -> contar(p));
    }
}
```"""},
            {
                "role": "assistant",
                "content": """Los dos síntomas salen de esta clase, y hay un tercer bug que no da síntomas todavía pero devuelve resultados falsos.

**Bloqueante 1: fuga de descriptores en `leer`.** Si `readLine()` lanza (fichero corrupto, disco que falla, codificación inválida), `r.close()` no se ejecuta. Cada excepción deja un descriptor abierto; tras unas horas se alcanza el límite del proceso y aparece «Too many open files». Arreglo: *try-with-resources*, que cierra siempre, también con excepción.

**Bloqueante 2: `return` dentro de `finally`.** El `finally` se ejecuta siempre y su `return 0` **sustituye** tanto al `return` del `try` como a la excepción del `catch`: `contar` devuelve 0 pase lo que pase, y se traga cualquier excepción, incluidas las que no son `IOException`. El compilador avisa con `-Xlint:finally`, pero por defecto lo deja pasar. Es el bug que todavía no has notado porque devuelve un número plausible.

**Importante 3: el `ExecutorService` nunca se cierra.** Los hilos de `newFixedThreadPool` no son *daemon*; mientras existan, la JVM no termina aunque `main` haya acabado. Ese es tu «el proceso no para». Hace falta un `shutdown()` en el ciclo de vida de la aplicación.

**Importante 4: `pool.submit` descarta el resultado y la excepción.** Si `contar` lanzara, la excepción quedaría guardada en un `Future` que nadie consulta: silencio total. Con `execute` al menos saldría por el `UncaughtExceptionHandler`; mejor, recoge los `Future` o registra el error dentro de la tarea.

**Diff mínimo:**

```java
public class Procesador implements AutoCloseable {
    private static final Logger log = LoggerFactory.getLogger(Procesador.class);
    private final ExecutorService pool = Executors.newFixedThreadPool(8);

    public String leer(Path ruta) throws IOException {
        try (BufferedReader r = Files.newBufferedReader(ruta, StandardCharsets.UTF_8)) {
            String linea = r.readLine();
            return linea == null ? "" : linea;
        }
    }

    public int contar(Path ruta) {
        try {
            return leer(ruta).length();
        } catch (IOException e) {
            log.warn("No se pudo leer {}", ruta, e);
            return -1;
        }
    }

    public void procesarTodo(List<Path> rutas) {
        for (Path p : rutas) {
            pool.execute(() -> {
                int n = contar(p);
                log.debug("{} -> {}", p, n);
            });
        }
    }

    @Override
    public void close() {
        pool.shutdown();
        try {
            if (!pool.awaitTermination(30, TimeUnit.SECONDS)) pool.shutdownNow();
        } catch (InterruptedException e) {
            pool.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
```

Cambios adicionales que van en la misma dirección: `Files.newBufferedReader` con `UTF_8` explícito en vez de `FileReader`, que usa la codificación de la plataforma (distinta en Windows y en Linux); y `readLine()` devuelve `null` en un fichero vacío, lo que en el original producía `NullPointerException` en `.length()`.

**Cómo comprobar:**

1. Descriptores: en un test, llama a `leer` 5 000 veces sobre un fichero que provoque excepción (por ejemplo, un directorio) y luego comprueba `ls /proc/<pid>/fd | wc -l` (o `lsof -p`) antes y después; con el original crece, con el arreglo se mantiene.
2. `contar` sobre un fichero inexistente debe devolver −1 (el original devuelve 0).
3. Apagado: un `main` que crea `Procesador` en un `try-with-resources`, procesa dos rutas y sale; con el arreglo el proceso termina en menos de un segundo.
4. Añade `-Xlint:all` al compilador: habría marcado el `finally` desde el primer día.""",
            },
        ]
    },
    # 15) JS: sort numérico, parseInt y ==; multiturno con acentos.
    {
        "messages": [
            {"role": "user", "content": "Ayuda, en JavaScript `[10, 9, 1, 100].sort()` me devuelve `[1, 10, 100, 9]`. ¿Está roto sort?"},
            {
                "role": "assistant",
                "content": """No está roto: `sort()` sin argumentos **convierte cada elemento a string y ordena alfabéticamente** (por unidades de código UTF-16). Como cadenas, `"10"` va antes que `"9"` porque `"1"` < `"9"` en el primer carácter. Es una de las decisiones más desafortunadas del lenguaje, pero es la especificación.

**Arreglo:** pasa una función de comparación que devuelva negativo, cero o positivo:

```js
[10, 9, 1, 100].sort((a, b) => a - b);   // [1, 9, 10, 100]
[10, 9, 1, 100].sort((a, b) => b - a);   // [100, 10, 9, 1]
```

`a - b` funciona para números finitos. No lo uses si puede haber `NaN` (el comparador devuelve `NaN` y el orden queda indefinido); filtra antes o compara con `(a > b) - (a < b)`.

**Dos cosas más que conviene saber:**

- `sort` **muta** el array original y además lo devuelve. Si quieres conservar el original, usa `toSorted` (ES2023, disponible en Node 20+ y navegadores actuales) o copia antes: `[...xs].sort(cmp)`.
- Desde ES2019 el orden es estable: dos elementos que comparan igual mantienen su orden relativo. Eso permite ordenar por varios criterios encadenando `sort` del menos al más importante, o mejor, con un comparador compuesto.

**Verificación mental del comparador:** `sort` llama a `cmp(a, b)` y pone `a` antes si el resultado es negativo. Con `a - b` y `a = 9`, `b = 10`: `9 - 10 = -1` → 9 antes que 10. ✓

Mientras estás en esto, hay dos parientes de este error que casi siempre aparecen en el mismo código: `parseInt(x)` sin radix (usa `Number(x)` o `parseInt(x, 10)`) y `==` entre tipos distintos (usa `===`). Los tres comparten la causa: conversiones implícitas a string o a número que nadie pidió.""",
            },
            {"role": "user", "content": "Perfecto. ¿Y para ordenar nombres con acentos? `['Zoe', 'ángela', 'Éric', 'bruno'].sort()` me pone 'ángela' al final."},
            {
                "role": "assistant",
                "content": """Mismo origen: el orden por defecto compara unidades de código, y en Unicode las mayúsculas sin acento (`Z` = 90) van antes que las minúsculas (`b` = 98) y estas antes que cualquier letra acentuada (`á` = 225, `É` = 201). Para texto humano hay que usar la comparación **según la configuración regional**:

```js
const nombres = ["Zoe", "ángela", "Éric", "bruno"];
nombres.sort((a, b) => a.localeCompare(b, "es", { sensitivity: "base" }));
// ['ángela', 'bruno', 'Éric', 'Zoe']
```

`localeCompare` con el idioma `"es"` ordena como un diccionario español: ignora mayúsculas y trata `á` como una variante de `a` en el primer nivel. `sensitivity: "base"` hace además que `"Éric"` y `"eric"` comparen igual (0); si quieres que las diferencias de acento desempaten, usa `"accent"`.

Para listas grandes, crea el comparador una vez con `Intl.Collator`, que evita reconstruir la configuración en cada comparación:

```js
const collator = new Intl.Collator("es", { sensitivity: "base", numeric: true });
nombres.sort(collator.compare);
```

`numeric: true` es un extra útil: ordena `"archivo2"` antes que `"archivo10"`, que es lo que la gente espera y lo que ni `sort()` ni `localeCompare` básico hacen.

**Verificación:** `collator.compare("ángela", "bruno")` devuelve un número negativo (á < b) y `collator.compare("Éric", "eric")` devuelve 0. Si el segundo no devuelve 0, el `sensitivity` no está aplicado.""",
            },
        ]
    },
    # 16) Python: función larga, diseño y testabilidad; multiturno sobre sobreingeniería.
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Clasifica cada hallazgo como bloqueante, importante o menor, propón el cambio mínimo y di cómo comprobarlo."},
            {"role": "user", "content": """Esta función hace el trabajo pero nadie se atreve a tocarla y no tiene tests. ¿Cómo la reestructurarías sin reescribir el proyecto?

```python
import json
import sqlite3
import urllib.request

def sincronizar_precios(url, ruta_bd):
    resp = urllib.request.urlopen(url, timeout=30)
    datos = json.loads(resp.read())
    conn = sqlite3.connect(ruta_bd)
    cur = conn.cursor()
    n = 0
    for item in datos["productos"]:
        if "sku" not in item or "precio" not in item:
            print("item inválido", item)
            continue
        precio = float(item["precio"])
        if precio < 0:
            print("precio negativo", item["sku"])
            continue
        cur.execute("UPDATE productos SET precio = ? WHERE sku = ?", (precio, item["sku"]))
        if cur.rowcount == 0:
            cur.execute("INSERT INTO productos (sku, precio) VALUES (?, ?)", (item["sku"], precio))
        n += 1
    conn.commit()
    conn.close()
    print("sincronizados", n)
    return n
```"""},
            {
                "role": "assistant",
                "content": """La función mezcla cuatro responsabilidades (descargar, validar, persistir, informar) y por eso no se puede probar sin red ni sin base de datos. El cambio mínimo es **separar lo puro de lo impuro**: la validación se queda en una función sin efectos, y las dos dependencias externas se inyectan.

**Hallazgos:**

- **Importante:** `conn.close()` no se ejecuta si algo lanza a mitad; la conexión y la transacción quedan abiertas. Usa `with` / `closing`.
- **Importante:** `float(item["precio"])` lanza `ValueError` con `"12,50"` y aborta toda la sincronización por un item. Debe contarse como item inválido, igual que los otros casos.
- **Importante:** sin tests porque nada es sustituible: `urlopen` y `sqlite3.connect` están cableados dentro.
- **Menor:** `print` en vez de `logging`; el llamador no puede silenciarlo ni dirigirlo.
- **Menor:** la pareja `UPDATE` + `INSERT` se expresa en una sola sentencia con `ON CONFLICT` (SQLite ≥ 3.24).

**Reestructuración mínima** (misma firma pública, mismo comportamiento):

```python
import json
import logging
import sqlite3
import urllib.request
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Precio:
    sku: str
    valor: float


def validar(items: Iterable[dict]) -> list[Precio]:
    validos: list[Precio] = []
    for item in items:
        if "sku" not in item or "precio" not in item:
            log.warning("item inválido: %r", item)
            continue
        try:
            valor = float(item["precio"])
        except (TypeError, ValueError):
            log.warning("precio no numérico en %s: %r", item["sku"], item["precio"])
            continue
        if valor < 0:
            log.warning("precio negativo en %s", item["sku"])
            continue
        validos.append(Precio(str(item["sku"]), valor))
    return validos


def guardar(conn: sqlite3.Connection, precios: Iterable[Precio]) -> int:
    filas = [(p.sku, p.valor) for p in precios]
    with conn:
        conn.executemany(
            "INSERT INTO productos (sku, precio) VALUES (?, ?) "
            "ON CONFLICT(sku) DO UPDATE SET precio = excluded.precio",
            filas,
        )
    return len(filas)


def descargar(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def sincronizar_precios(
    url: str,
    ruta_bd: str,
    descargar_fn: Callable[[str], dict] = descargar,
) -> int:
    datos = descargar_fn(url)
    precios = validar(datos["productos"])
    with closing(sqlite3.connect(ruta_bd)) as conn:
        n = guardar(conn, precios)
    log.info("sincronizados %d", n)
    return n
```

Ahora `validar` se prueba con listas en memoria, `guardar` con `sqlite3.connect(":memory:")`, y `sincronizar_precios` entera con un `descargar_fn` falso. `ON CONFLICT` exige que `sku` sea `PRIMARY KEY` o tenga índice `UNIQUE`; si no lo tiene, añádelo (sin él, el `UPDATE`+`INSERT` original también podía insertar duplicados bajo concurrencia).

**Cómo comprobar que el comportamiento no cambió:**

```python
def test_validar_descarta_invalidos_y_conserva_orden():
    items = [{"sku": "a", "precio": "1.5"}, {"sku": "b"}, {"sku": "c", "precio": "x"}, {"sku": "d", "precio": -1}, {"sku": "e", "precio": 2}]
    assert validar(items) == [Precio("a", 1.5), Precio("e", 2.0)]

def test_guardar_inserta_y_actualiza():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE productos (sku TEXT PRIMARY KEY, precio REAL)")
    guardar(conn, [Precio("a", 1.0)])
    guardar(conn, [Precio("a", 2.0), Precio("b", 3.0)])
    assert sorted(conn.execute("SELECT sku, precio FROM productos")) == [("a", 2.0), ("b", 3.0)]

def test_sincronizar_con_descarga_falsa(tmp_path):
    bd = tmp_path / "p.db"
    sqlite3.connect(bd).execute("CREATE TABLE productos (sku TEXT PRIMARY KEY, precio REAL)").connection.commit()
    n = sincronizar_precios("http://ignorada", str(bd), descargar_fn=lambda _u: {"productos": [{"sku": "z", "precio": 9}]})
    assert n == 1
```

El primer test con el código original no se puede ni escribir; ese es el síntoma que querías quitar.""",
            },
            {"role": "user", "content": "¿No es sobreingeniería meter un dataclass y tres funciones para 25 líneas?"},
            {
                "role": "assistant",
                "content": """Para 25 líneas que nadie toca, sí lo sería. Para 25 líneas que *nadie se atreve a tocar* y sin tests, no: la medida de sobreingeniería no es el número de funciones sino si cada pieza nueva paga su coste. Repasemos cada una:

- **`validar` separada.** Es lo que permite el primer test, el que cubre la lógica con más casos (cuatro formas de item inválido). Sin ella, cada caso necesita red falsa y base de datos. Se paga sola.
- **`descargar_fn` inyectable.** Un parámetro con valor por defecto; cero coste para los llamadores actuales. Es lo que permite el test de integración sin red.
- **`guardar` separada.** Discutible. Podría quedarse dentro de `sincronizar_precios`; la saqué porque el `ON CONFLICT` merece un test propio con `:memory:`. Si prefieres fusionarla, pierdes ese test y ganas 6 líneas menos.
- **`Precio` como dataclass.** Es la pieza más prescindible. Una tupla `(sku, valor)` funciona igual; el dataclass aporta nombres en los asserts (`Precio("a", 1.5)` frente a `("a", 1.5)`) y un sitio donde poner tipos. Son 5 líneas; si te sobran, tupla.

Lo que **no** quitaría bajo ningún concepto: el `with`/`closing` (corrección), el `try` alrededor de `float` (corrección) y la separación de la validación (testabilidad). Lo demás es gusto y lo negociaría en el PR sin problema.

La regla que uso: una abstracción nueva está justificada si permite escribir un test que antes no se podía, o si elimina una dependencia del módulo. Dataclass y `guardar` están en el límite; `validar` y la inyección están claramente dentro.""",
            },
        ]
    },
    # 17) SQL: comprobar-y-luego-insertar, actualización perdida.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": """Aparecen usuarios duplicados por email y cupones usados más veces de las permitidas. El código (Postgres, desde Python con psycopg):

```python
def registrar(conn, email, nombre):
    if conn.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,)).fetchone():
        raise ValueError("email ya registrado")
    conn.execute("INSERT INTO usuarios (email, nombre) VALUES (%s, %s)", (email, nombre))
    conn.commit()

def usar_cupon(conn, codigo):
    usos = conn.execute("SELECT usos FROM cupones WHERE codigo = %s", (codigo,)).fetchone()[0]
    if usos >= 10:
        raise ValueError("cupón agotado")
    conn.execute("UPDATE cupones SET usos = %s WHERE codigo = %s", (usos + 1, codigo))
    conn.commit()
```"""},
            {
                "role": "assistant",
                "content": """Las dos funciones tienen el mismo defecto: **comprobar y luego actuar en dos pasos**, con una ventana entre ambos en la que otra petición hace lo mismo. En un servidor con varias peticiones concurrentes esa ventana se cruza decenas de veces al día.

**Bloqueante 1: `registrar`, carrera comprobar-insertar.** Dos peticiones con el mismo email ejecutan el `SELECT` a la vez, las dos ven «no existe», las dos insertan. La única forma de impedirlo es que la **base de datos** sea quien garantice la unicidad:

```sql
ALTER TABLE usuarios ADD CONSTRAINT usuarios_email_unico UNIQUE (email);
```

y en el código, intentar insertar y tratar la violación como el caso «ya existe»:

```python
from psycopg.errors import UniqueViolation

def registrar(conn, email, nombre):
    try:
        with conn.transaction():
            conn.execute("INSERT INTO usuarios (email, nombre) VALUES (%s, %s)", (email, nombre))
    except UniqueViolation:
        raise ValueError("email ya registrado") from None
```

Antes de crear la restricción hay que deduplicar las filas existentes, o el `ALTER` falla. Y si comparáis emails sin distinguir mayúsculas, la restricción debe ser sobre `lower(email)` (índice único por expresión).

**Bloqueante 2: `usar_cupon`, actualización perdida.** Dos peticiones leen `usos = 9`, las dos pasan el `if`, las dos escriben `10`. Resultado: 11 usos reales, contador en 10. Aquí hay dos arreglos correctos:

*a) Actualización atómica con condición*, la más simple y sin bloqueos largos:

```python
def usar_cupon(conn, codigo):
    with conn.transaction():
        fila = conn.execute(
            "UPDATE cupones SET usos = usos + 1 WHERE codigo = %s AND usos < 10 RETURNING usos",
            (codigo,),
        ).fetchone()
    if fila is None:
        raise ValueError("cupón agotado o inexistente")
```

El `UPDATE` lee y escribe en una sola sentencia; Postgres serializa las dos peticiones sobre la misma fila y la segunda ve `usos = 10`, no cumple `usos < 10` y no actualiza nada. `RETURNING` te dice si tocaste la fila sin una consulta extra.

*b) `SELECT ... FOR UPDATE`* si necesitas leer varios campos antes de decidir (fecha de caducidad, usuario, importe): bloquea la fila hasta el `commit`, y la segunda petición espera y luego ve el valor actualizado. Es más flexible y un poco más lento; úsalo cuando la condición no cabe en el `WHERE`.

**Importante:** el `conn.commit()` manual con excepciones por medio deja transacciones abiertas si algo lanza antes; `conn.transaction()` hace *commit* o *rollback* según salga del bloque.

**Cómo comprobarlo** (test de carrera reproducible, no probabilístico):

```python
import threading

def test_registrar_no_duplica_bajo_concurrencia(dsn):
    errores = []
    def intento():
        with psycopg.connect(dsn) as c:
            try:
                registrar(c, "a@b.c", "x")
            except ValueError as e:
                errores.append(e)
    hilos = [threading.Thread(target=intento) for _ in range(20)]
    for h in hilos: h.start()
    for h in hilos: h.join()
    with psycopg.connect(dsn) as c:
        assert c.execute("SELECT count(*) FROM usuarios WHERE email = 'a@b.c'").fetchone()[0] == 1
    assert len(errores) == 19
```

Con el código original, el conteo da más de 1 en la mayoría de las ejecuciones; con la restricción `UNIQUE` da exactamente 1 siempre, porque ya no depende de la suerte sino de la base de datos. El equivalente para cupones: 20 hilos contra un cupón con `usos = 0`, y al final `usos == 10` y exactamente 10 excepciones.""",
            },
        ]
    },
    # 18) C: crecimiento de array dinámico.
    {
        "messages": [
            {"role": "user", "content": r"""Esta función para crecer un array dinámico en C a veces corrompe memoria en el programa que la usa. No veo nada raro:

```c
typedef struct {
    int *datos;
    size_t len;
    size_t cap;
} Vec;

int vec_push(Vec *v, int x) {
    if (v->len == v->cap) {
        v->cap = v->cap * 2;
        v->datos = realloc(v->datos, v->cap * sizeof(int));
        if (v->datos == NULL) return -1;
    }
    v->datos[v->len++] = x;
    return 0;
}
```"""},
            {
                "role": "assistant",
                "content": r"""Hay tres errores, y el primero produce corrupción en cuanto el `Vec` se inicializa a ceros, que es lo más habitual.

**Bloqueante 1: `cap * 2` con `cap == 0` sigue siendo 0.** Un `Vec` recién creado con `cap = 0` entra en el `if`, pide `realloc(ptr, 0)` (comportamiento definido por la implementación: puede devolver `NULL` o un puntero a cero bytes), y luego escribe `v->datos[0]`. Eso es escribir fuera de un bloque de tamaño 0. Esa es tu corrupción.

**Bloqueante 2: `v->datos = realloc(v->datos, ...)` pierde el bloque original si `realloc` falla.** `realloc` devuelve `NULL` y deja el bloque antiguo intacto, pero tú ya has sobrescrito el único puntero que lo referenciaba: fuga de memoria, y además `v->cap` ya está duplicada aunque la memoria no, así que el siguiente `push` escribe fuera. Guarda el resultado en una variable temporal y solo asigna si no es `NULL`.

**Importante 3: `v->cap * sizeof(int)` puede desbordar `size_t`.** Con `cap` cerca de `SIZE_MAX / 4` el producto da un número pequeño, `realloc` reserva poco y la escritura se sale. Es improbable en un `int` array real, pero el chequeo cuesta una línea y es el patrón correcto.

**Diff mínimo:**

```c
#include <stdint.h>
#include <stdlib.h>

int vec_push(Vec *v, int x) {
    if (v->len == v->cap) {
        size_t nueva_cap = v->cap == 0 ? 8 : v->cap * 2;
        if (nueva_cap < v->cap || nueva_cap > SIZE_MAX / sizeof(int)) return -1;
        int *nuevo = realloc(v->datos, nueva_cap * sizeof(int));
        if (nuevo == NULL) return -1;
        v->datos = nuevo;
        v->cap = nueva_cap;
    }
    v->datos[v->len++] = x;
    return 0;
}
```

Decisiones: la capacidad inicial de 8 evita cuatro `realloc` diminutos al principio; `nueva_cap < v->cap` detecta el desbordamiento de la duplicación y la segunda comparación el del producto; `cap` solo se actualiza cuando la memoria ya existe, así el estado del `Vec` es coherente aunque `push` falle (invariante: `len <= cap` y `datos` tiene sitio para `cap` enteros).

**Menor:** el llamador tiene que inicializar `Vec` a `{NULL, 0, 0}` para que `realloc(NULL, n)` actúe como `malloc`; conviene una función `vec_init` o una macro `VEC_INIT` para no depender de que todos lo recuerden.

**Cómo comprobar:**

```c
#include <assert.h>

int main(void) {
    Vec v = {NULL, 0, 0};
    for (int i = 0; i < 100000; i++) assert(vec_push(&v, i) == 0);
    for (int i = 0; i < 100000; i++) assert(v.datos[i] == i);
    assert(v.len == 100000 && v.cap >= v.len);
    free(v.datos);
    return 0;
}
```

Compila con `-fsanitize=address,undefined`: el original aborta en el primer `push` con `heap-buffer-overflow` (escritura de 4 bytes en un bloque de 0). Para el fallo de `realloc`, enlaza un `realloc` falso que devuelva `NULL` la tercera vez y comprueba que `vec_push` devuelve −1 y que `v.datos` sigue siendo válido y `v.cap` no cambió.""",
            },
        ]
    },
    # 19) Python: contador con hilos y el GIL; multiturno con asyncio.
    {
        "messages": [
            {"role": "user", "content": """Este contador con hilos en Python da menos de 1 000 000 aunque el GIL se supone que protege. ¿Por qué?

```python
import threading

contador = 0

def incrementar():
    global contador
    for _ in range(100_000):
        contador += 1

hilos = [threading.Thread(target=incrementar) for _ in range(10)]
for h in hilos: h.start()
for h in hilos: h.join()
print(contador)
```"""},
            {
                "role": "assistant",
                "content": """El GIL garantiza que solo un hilo ejecuta *bytecode* a la vez, no que una línea de Python sea atómica. `contador += 1` son varias instrucciones: cargar el valor global, sumar 1, guardar el valor global. El intérprete puede cambiar de hilo **entre** la carga y el guardado; entonces dos hilos leen el mismo valor, ambos suman 1 y ambos escriben el mismo resultado: un incremento perdido.

Puedes verlo con `dis`:

```pycon
>>> import dis
>>> dis.dis(incrementar)
  LOAD_GLOBAL     contador
  LOAD_CONST      1
  BINARY_OP       +=
  STORE_GLOBAL    contador
```

Cuatro instrucciones; el cambio de hilo puede caer en cualquiera de las tres junturas. Con 10 hilos y 100 000 vueltas la ventana se cruza miles de veces, de ahí el resultado corto.

**Arreglo mínimo:** un `Lock` alrededor de la operación compuesta.

```python
import threading

contador = 0
lock = threading.Lock()

def incrementar():
    global contador
    for _ in range(100_000):
        with lock:
            contador += 1
```

**Si el rendimiento importa**, no tomes el lock un millón de veces: acumula en una variable local y suma una sola vez al final.

```python
def incrementar():
    global contador
    local = 0
    for _ in range(100_000):
        local += 1
    with lock:
        contador += local
```

Diez tomas de lock en vez de un millón, mismo resultado.

**Verificación:** ejecuta el script 20 veces con el lock; debe imprimir exactamente 1 000 000 siempre. Sin el lock, en Python 3.12 suele dar entre 600 000 y 1 000 000 según el ritmo de cambio de hilo (el intervalo por defecto es de 5 ms, `sys.getswitchinterval()`); bajarlo a `sys.setswitchinterval(1e-6)` hace el fallo casi seguro en cada ejecución, útil para un test que quiera reproducirlo de forma fiable.

**Qué más protege (y qué no) el GIL.** Las operaciones individuales sobre estructuras nativas (`list.append`, `dict[k] = v`) sí son atómicas en CPython porque se ejecutan dentro de una sola instrucción de C. Las compuestas (leer-modificar-escribir, «si no está, insertar») nunca lo son. Y en el Python sin GIL (3.13 con `--disable-gil`, experimental) ni siquiera lo primero se garantiza sin lock.""",
            },
            {"role": "user", "content": "¿Y con asyncio? Como es un solo hilo entiendo que no hace falta lock."},
            {
                "role": "assistant",
                "content": """Depende de dónde están los `await`. En asyncio un cambio de tarea solo puede ocurrir en un `await` (o `async for`/`async with`), así que **este** incremento es seguro sin lock:

```python
async def incrementar():
    global contador
    for _ in range(100_000):
        contador += 1          # sin await en medio: atómico respecto a otras tareas
```

Pero en cuanto la operación compuesta tiene un `await` en medio, vuelve la carrera, exactamente la misma:

```python
async def retirar(cuenta_id, cantidad):
    saldo = await bd.leer_saldo(cuenta_id)        # tarea A lee 100
    if saldo >= cantidad:                          # tarea B lee 100 aquí
        await bd.escribir_saldo(cuenta_id, saldo - cantidad)   # ambas escriben 100 - 80
```

Dos retiradas de 80 sobre un saldo de 100 pasan las dos. El punto de cambio es explícito (los `await`), lo que lo hace más fácil de razonar que con hilos, pero no lo elimina.

Para ese caso tienes `asyncio.Lock`, que se usa con `async with`:

```python
lock = asyncio.Lock()

async def retirar(cuenta_id, cantidad):
    async with lock:
        saldo = await bd.leer_saldo(cuenta_id)
        if saldo < cantidad:
            raise ValueError("saldo insuficiente")
        await bd.escribir_saldo(cuenta_id, saldo - cantidad)
```

Un `threading.Lock` aquí sería un error: bloquearía el hilo entero del *event loop* mientras espera, y el `await` de dentro nunca podría progresar.

**Regla para decidir:** mira la sección crítica. Si entre la lectura y la escritura no hay ningún `await`, no hace falta lock. Si lo hay, hace falta `asyncio.Lock` o, mejor, mover la atomicidad a la base de datos (`UPDATE ... WHERE saldo >= %s`), que además protege cuando hay más de un proceso, cosa que ningún lock en memoria hace.

**Verificación:** lanza 50 tareas con `asyncio.gather(*[retirar(1, 80) for _ in range(50)])` contra un saldo falso en memoria de 100 con un `await asyncio.sleep(0)` dentro de `leer_saldo`. Sin lock, varias retiradas tienen éxito; con lock, exactamente una.""",
            },
        ]
    },
    # 20) Rust: guard de Mutex a través de un await; en inglés.
    {
        "messages": [
            {"role": "user", "content": """Our tokio service hangs under load. Minimal version of the suspicious handler:

```rust
use std::sync::{Arc, Mutex};
use std::collections::HashMap;

struct Cache { map: HashMap<String, String> }

async fn handle(cache: Arc<Mutex<Cache>>, key: String) -> String {
    let mut c = cache.lock().unwrap();
    if let Some(v) = c.map.get(&key) {
        return v.clone();
    }
    let v = fetch_remote(&key).await;
    c.map.insert(key, v.clone());
    v
}
```

It compiles, so I assumed it was fine."""},
            {
                "role": "assistant",
                "content": """It compiles because `std::sync::Mutex` has no idea what `.await` is. The problem: **the lock guard `c` is held across `fetch_remote(&key).await`**. While the remote call is in flight, every other task that calls `handle` blocks on `cache.lock()`, and because that is a *blocking* std lock, it parks the whole tokio worker thread, not just the task. With N worker threads and N concurrent cache misses, all workers are parked, nothing can make progress, and the `fetch_remote` futures never get polled to completion. That is your hang.

Two secondary issues:

- `unwrap()` on `lock()` panics if any task ever panicked while holding the lock (poisoning). In a server that turns one bug into a permanent outage.
- The cache is only ever populated, never bounded; under load it grows without limit. Not the cause of the hang, but it is next.

**Minimal fix: never hold the guard across an await.** Lock, check, unlock; do the slow work; lock again, insert.

```rust
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

struct Cache { map: HashMap<String, String> }

async fn handle(cache: Arc<Mutex<Cache>>, key: String) -> String {
    if let Some(v) = cache.lock().unwrap().map.get(&key) {
        return v.clone();
    }
    let v = fetch_remote(&key).await;
    cache.lock().unwrap().map.insert(key, v.clone());
    v
}
```

The temporary guard in each expression is dropped at the end of the statement, so no lock is alive at the `.await`. Keeping `std::sync::Mutex` is deliberate: it is cheaper than `tokio::sync::Mutex` and correct as long as critical sections are short and contain no awaits, which is what tokio's own docs recommend.

**What this fix does not do:** it allows a *thundering herd*. Ten misses on the same key fetch ten times before the first insert. If `fetch_remote` is expensive, that matters, and the cure is request coalescing: store a `tokio::sync::watch` or a shared future per in-flight key, so later callers await the first fetch instead of starting their own. That is a separate, larger change, so I would ship the fix above first.

**If you genuinely need to hold a lock across an await** (a stateful protocol, a connection you must keep exclusive while talking), then `tokio::sync::Mutex` is the right tool: its `lock().await` yields instead of blocking the thread. Use it only in that case; a tokio mutex for every tiny critical section costs more and hides the design smell.

**How to verify:**

1. Clippy catches this: `cargo clippy -- -W clippy::await_holding_lock` reports the original and is clean on the fix. Add it to CI.
2. Load test: `tokio::spawn` 1,000 `handle` calls with distinct keys against a `fetch_remote` that sleeps 100 ms, on a runtime with `worker_threads = 4`. The original takes 1,000 × 100 ms = 100 s (fully serialised) or deadlocks outright; the fix finishes in about 100 ms plus overhead.
3. Poisoning: replace `unwrap()` with `unwrap_or_else(|e| e.into_inner())` if you decide a panicked writer should not poison the cache for everyone.""",
            },
        ]
    },
    # 21) TS: validación en el borde de la API, asignación masiva, URL externa.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": """Endpoint de actualización de perfil en Express + Prisma. Pasó la revisión funcional pero quiero una de seguridad antes del despliegue.

```ts
app.patch("/users/:id", requireAuth, async (req, res) => {
  const user = await prisma.user.update({
    where: { id: Number(req.params.id) },
    data: req.body,
  });
  if (req.body.avatarUrl) {
    const img = await fetch(req.body.avatarUrl);
    await saveAvatar(user.id, Buffer.from(await img.arrayBuffer()));
  }
  res.json(user);
});
```"""},
            {
                "role": "assistant",
                "content": """Tres bloqueantes y dos importantes. Ninguno depende de un bug exótico: son los defectos estándar de un endpoint que confía en su entrada.

**Bloqueante 1: cualquier usuario autenticado edita a cualquier otro.** `requireAuth` comprueba que hay sesión, no que `req.params.id` sea el propio usuario. Falta la autorización: `req.user.id === id` o un rol de administrador.

**Bloqueante 2: asignación masiva.** `data: req.body` escribe **cualquier columna** que el cliente envíe: `role: "admin"`, `emailVerified: true`, `passwordHash`, `credits`. Lo que el modelo tenga. Hay que declarar la lista blanca de campos editables y validar su forma.

**Bloqueante 3: petición del servidor a una URL controlada por el cliente (SSRF).** `fetch(req.body.avatarUrl)` sale desde tu red interna: `http://169.254.169.254/` (metadatos de la nube), `http://localhost:9200/` (Elasticsearch interno), `http://10.0.0.5/admin`. El cliente lee lo que el servidor puede alcanzar. Las medidas mínimas: solo `https`, lista blanca de dominios (tu CDN, los proveedores de avatar que aceptes), sin seguir redirecciones, timeout y límite de tamaño. La resolución DNS a IP privada es un ataque adicional; si no puedes usar lista blanca de dominios, resuelve el host y rechaza rangos privados antes de conectar.

**Importante 4: `Number(req.params.id)`** acepta `"1e3"`, `"0x10"` o `" 7 "`, y `NaN` llega a Prisma como error 500. Valida como entero positivo.

**Importante 5: respuesta con el objeto completo.** `res.json(user)` devuelve todas las columnas, incluido el hash de la contraseña si existe. Selecciona los campos de salida.

**Diff mínimo** (validación con Zod, que ya es lo habitual en Express + TS; si usáis otra librería, el esquema se traduce igual):

```ts
import { z } from "zod";

const AVATAR_HOSTS = new Set(["cdn.miapp.com", "avatars.githubusercontent.com"]);

const avatarUrl = z.string().url().refine((u) => {
  const url = new URL(u);
  return url.protocol === "https:" && AVATAR_HOSTS.has(url.hostname);
}, "host de avatar no permitido");

const PatchUser = z.object({
  name: z.string().min(1).max(80).optional(),
  bio: z.string().max(500).optional(),
  avatarUrl: avatarUrl.optional(),
}).strict();

const Params = z.object({ id: z.coerce.number().int().positive() });

app.patch("/users/:id", requireAuth, async (req, res) => {
  const params = Params.safeParse(req.params);
  const body = PatchUser.safeParse(req.body);
  if (!params.success || !body.success) return res.status(400).json({ error: "entrada inválida" });
  if (req.user.id !== params.data.id && req.user.role !== "admin") return res.status(403).end();

  const { avatarUrl: nuevaUrl, ...campos } = body.data;
  const user = await prisma.user.update({
    where: { id: params.data.id },
    data: campos,
    select: { id: true, name: true, bio: true, avatarUrl: true },
  });

  if (nuevaUrl) {
    const img = await fetch(nuevaUrl, { redirect: "error", signal: AbortSignal.timeout(5000) });
    if (!img.ok) return res.status(400).json({ error: "no se pudo descargar el avatar" });
    const len = Number(img.headers.get("content-length") ?? 0);
    if (len > 2 * 1024 * 1024) return res.status(400).json({ error: "avatar demasiado grande" });
    await saveAvatar(user.id, Buffer.from(await img.arrayBuffer()));
  }
  res.json(user);
});
```

`.strict()` rechaza campos desconocidos en vez de ignorarlos, lo que convierte un intento de `role: "admin"` en un 400 visible en los logs. `redirect: "error"` impide que un dominio permitido redirija a uno interno. El `content-length` es una cota rápida, no una garantía (puede faltar o mentir); si el tamaño importa de verdad, lee el cuerpo en *stream* con un contador.

**Cómo comprobar**, con supertest:

1. Usuario 1 hace `PATCH /users/2` → 403.
2. `PATCH /users/1` con `{ role: "admin" }` → 400, y `role` en la base de datos sigue siendo `user`.
3. `{ avatarUrl: "http://169.254.169.254/latest/meta-data" }` → 400 sin que se haga ninguna petición saliente (mockea `fetch` y afirma que no se llamó).
4. `PATCH /users/abc` → 400.
5. La respuesta de un `PATCH` válido no contiene `passwordHash`.""",
            },
        ]
    },
    # 22) Python: secretos en logs y TLS desactivado.
    {
        "messages": [
            {"role": "user", "content": """Cliente HTTP interno para una API de pagos. Auditoría la semana que viene; ¿qué me van a señalar?

```python
import logging
import requests

log = logging.getLogger("pagos")

class ClientePagos:
    def __init__(self, token: str, base: str):
        self.headers = {"Authorization": f"Bearer {token}"}
        self.base = base

    def cobrar(self, tarjeta: str, importe: float):
        payload = {"card": tarjeta, "amount": importe}
        log.info("POST %s/charge headers=%s payload=%s", self.base, self.headers, payload)
        r = requests.post(f"{self.base}/charge", json=payload, headers=self.headers, verify=False)
        if r.status_code != 200:
            log.error("Fallo al cobrar: %s", r.text)
            raise RuntimeError(f"Error {r.status_code}: {r.text} (token {self.headers['Authorization']})")
        return r.json()
```"""},
            {
                "role": "assistant",
                "content": """Te van a señalar cuatro cosas, y tres son bloqueantes con cualquier estándar de pagos.

**Bloqueante 1: el token de la API y el número de tarjeta van a los logs.** La línea de `info` escribe `Authorization: Bearer ...` y `card` completos en cada llamada. Los logs se envían a sistemas con menos control de acceso que la base de datos (agregadores, tickets de soporte, copias en portátiles). Un número de tarjeta en un log es un hallazgo de incumplimiento directo.

**Bloqueante 2: el token también va en el mensaje de la excepción.** Las excepciones acaban en trazas, en Sentry, en correos de alerta. Nunca metas credenciales en un mensaje de error.

**Bloqueante 3: `verify=False` desactiva la validación del certificado TLS.** Cualquiera en la ruta de red puede suplantar la API de pagos y recibir tu token y las tarjetas. Si lo pusisteis por un certificado interno, la solución es `verify="/ruta/ca-interna.pem"`, no apagar la comprobación.

**Importante 4: `r.text` del proveedor se registra entero.** Las respuestas de error de pasarelas suelen devolver eco de la petición (tarjeta enmascarada, a veces no tan enmascarada). Registra código de estado y un identificador de la petición, no el cuerpo.

**Menor:** `importe: float` para dinero; usa `Decimal` o céntimos enteros. Y no hay timeout: `requests` espera indefinidamente por defecto.

**Diff mínimo:**

```python
import logging
from decimal import Decimal

import requests

log = logging.getLogger("pagos")
TIMEOUT = (3.0, 10.0)   # conexión, lectura


def enmascarar_tarjeta(numero: str) -> str:
    return "*" * (len(numero) - 4) + numero[-4:] if len(numero) >= 4 else "****"


class ClientePagos:
    def __init__(self, token: str, base: str, ca_bundle: str | bool = True):
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.verify = ca_bundle
        self.base = base

    def cobrar(self, tarjeta: str, importe_centimos: int) -> dict:
        log.info("POST /charge tarjeta=%s importe=%d", enmascarar_tarjeta(tarjeta), importe_centimos)
        r = self._session.post(
            f"{self.base}/charge",
            json={"card": tarjeta, "amount": importe_centimos},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            log.error("Fallo al cobrar: status=%d request_id=%s", r.status_code, r.headers.get("X-Request-Id"))
            raise RuntimeError(f"la pasarela devolvió {r.status_code}")
        return r.json()
```

El token vive en la sesión y no en un atributo que se imprima por accidente con `vars(cliente)`; el `__repr__` por defecto de la clase tampoco lo muestra. `ca_bundle` permite el certificado interno sin tocar la verificación.

**Cómo comprobarlo**, y esto es lo que conviene tener listo para la auditoría:

```python
def test_cobrar_no_registra_secretos(caplog, requests_mock):
    requests_mock.post("https://api.test/charge", json={"ok": True})
    cliente = ClientePagos("tok-SECRETO", "https://api.test")
    with caplog.at_level(logging.DEBUG):
        cliente.cobrar("4111111111111111", 1999)
    assert "tok-SECRETO" not in caplog.text
    assert "4111111111111111" not in caplog.text
    assert "1111" in caplog.text          # los últimos 4 sí, para soporte

def test_error_no_incluye_token(requests_mock):
    requests_mock.post("https://api.test/charge", status_code=500, text="boom")
    cliente = ClientePagos("tok-SECRETO", "https://api.test")
    with pytest.raises(RuntimeError) as exc:
        cliente.cobrar("4111111111111111", 1)
    assert "tok-SECRETO" not in str(exc.value)
```

Y en CI: `bandit -r .` marca `verify=False` (B501) en la versión actual; `grep -rn "verify=False"` como comprobación de segundo nivel. Un filtro de `logging` que enmascare patrones de tarjeta (13-19 dígitos) es una red de seguridad razonable además de lo anterior, no en su lugar.""",
            },
        ]
    },
    # 23) Go: Mutex copiado por valor; rioplatense.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y con el arreglo mínimo."},
            {"role": "user", "content": """Tengo un contador con mutex en Go y aun así el test con -race me marca una carrera. No entiendo, si estoy lockeando.

```go
type Contador struct {
    mu sync.Mutex
    n  int
}

func (c Contador) Inc() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.n++
}

func (c Contador) Valor() int {
    return c.n
}
```"""},
            {
                "role": "assistant",
                "content": """El mutex está, pero **no es el mismo mutex**. `Inc` tiene receptor por valor: cada llamada recibe una **copia** de `Contador`, con su propia copia de `mu` y de `n`. Lockeás la copia, incrementás la copia, y la copia se descarta al salir. El `Contador` original nunca cambia y nunca se lockea; de ahí que `-race` vea accesos sin sincronizar (si en algún lado leés `c.n` del original) y que además `Valor()` devuelva siempre 0.

Dos síntomas, una causa: receptores por valor en un tipo que contiene un `sync.Mutex`.

**Arreglo mínimo:** receptores por puntero en los dos métodos, y proteger también la lectura, porque un `int` leído mientras otro goroutine lo escribe es carrera igual.

```go
type Contador struct {
    mu sync.Mutex
    n  int
}

func (c *Contador) Inc() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.n++
}

func (c *Contador) Valor() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.n
}
```

Regla práctica: si un struct tiene un `sync.Mutex` (o un `sync.WaitGroup`, o un canal con estado), **todos** sus métodos van con receptor puntero y el struct nunca se copia después de usarse. Si querés que sea imposible copiarlo por accidente, pasalo siempre como `*Contador` y no lo guardes por valor en slices ni maps.

**Verificación:**

1. `go vet ./...` ya lo marca en el original: `Inc passes lock by value: Contador contains sync.Mutex` (chequeo `copylocks`). Si no lo corren en CI, agregalo; esto lo hubiera detectado sin tests.
2. Test:

```go
func TestContadorConcurrente(t *testing.T) {
    var c Contador
    var wg sync.WaitGroup
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() { defer wg.Done(); for j := 0; j < 1000; j++ { c.Inc() } }()
    }
    wg.Wait()
    if got := c.Valor(); got != 100_000 {
        t.Fatalf("Valor() = %d, esperaba 100000", got)
    }
}
```

Con el original da `Valor() = 0` y `go test -race` reporta la carrera; con el arreglo da 100 000 y `-race` queda limpio.

Si el contador es lo único que protegés, `atomic.Int64` (Go 1.19+) te ahorra el mutex: `c.n.Add(1)` y `c.n.Load()`. Pero el error de fondo, el receptor por valor, se aplica igual a cualquier struct con estado compartido.""",
            },
        ]
    },
    # 24) Java: == con Integer, equals/hashCode en claves de HashMap.
    {
        "messages": [
            {"role": "user", "content": """En Java esto me vuelve loco:

```java
Integer a = 100, b = 100;
Integer c = 1000, d = 1000;
System.out.println(a == b);   // true
System.out.println(c == d);   // false
```

¿Por qué 100 sí y 1000 no? Y tengo un HashMap con clave de una clase mía donde `map.get(new Clave("x"))` devuelve null aunque acabo de meter esa clave."""},
            {
                "role": "assistant",
                "content": """Los dos problemas son el mismo: **`==` compara referencias, no valores**, y lo que ves como «funciona con 100» es una coincidencia de implementación.

**1. `Integer` y la caché de −128 a 127.** `Integer a = 100` usa `Integer.valueOf(100)` por autoboxing, y `valueOf` devuelve objetos **cacheados** para los valores entre −128 y 127 (la especificación lo exige en ese rango). Así que `a` y `b` son el mismo objeto y `==` da `true`. Para 1000 se crean dos objetos distintos y `==` da `false`. Compara siempre con `equals` o, mejor, desempaqueta:

```java
System.out.println(a.equals(b));       // true
System.out.println(c.equals(d));       // true
System.out.println(c.intValue() == d); // true (d se desempaqueta)
```

Si la variable puede ser `null`, `Objects.equals(c, d)` evita el `NullPointerException`.

**2. `HashMap` y tu clase `Clave`.** `HashMap` localiza la entrada por `hashCode()` y luego confirma con `equals()`. Si `Clave` no sobrescribe ninguno de los dos, hereda los de `Object`: identidad. `new Clave("x")` es otro objeto, con otro `hashCode`, y el mapa no lo encuentra. Hay que sobrescribir **los dos**, y de forma coherente (objetos iguales → mismo hash):

```java
public final class Clave {
    private final String valor;

    public Clave(String valor) { this.valor = Objects.requireNonNull(valor); }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Clave otra)) return false;
        return valor.equals(otra.valor);
    }

    @Override
    public int hashCode() { return valor.hashCode(); }
}
```

O, si tu Java es 16 o posterior, un `record` lo genera todo correcto en una línea:

```java
public record Clave(String valor) {}
```

**Las dos trampas que siguen a esta:**

- Sobrescribir `equals` y no `hashCode`: dos claves «iguales» caen en cubetas distintas y el mapa sigue sin encontrarlas. El compilador no avisa; los IDE sí.
- Claves **mutables**: si cambias un campo que participa en `hashCode` después de insertar, la entrada queda en la cubeta antigua y es irrecuperable. Por eso `Clave` es `final` con campo `final`.

**Verificación:**

```java
@Test
void claveFuncionaComoClaveDeMapa() {
    Map<Clave, Integer> m = new HashMap<>();
    m.put(new Clave("x"), 1);
    assertEquals(1, m.get(new Clave("x")));
    assertEquals(new Clave("x").hashCode(), new Clave("x").hashCode());
    assertNotEquals(new Clave("x"), new Clave("y"));
}
```

Con la clase original la primera aserción falla con `null`. Y para el caso de `Integer`, un test que compare con `equals` pasa para 100 y para 1000; cualquier `==` entre `Integer` lo marca SpotBugs como `RC_REF_COMPARISON`, conviene tenerlo en CI.""",
            },
        ]
    },
    # 25) Python: qué puede fallar en producción; usuario en español pide respuesta en inglés.
    {
        "messages": [
            {"role": "user", "content": """Este script se va a ejecutar cada noche por cron en producción para actualizar precios desde un CSV que deja otro equipo. Dime qué puede fallar en producción. Respóndeme en inglés, que lo pego tal cual en el PR.

```python
import csv
import psycopg

conn = psycopg.connect("postgresql://app:app@db/prod", autocommit=True)
with open("/mnt/share/precios.csv") as f:
    for fila in csv.DictReader(f):
        try:
            conn.execute("UPDATE productos SET precio = %s WHERE sku = %s", (fila["precio"], fila["sku"]))
        except Exception:
            pass
print("hecho")
```"""},
            {
                "role": "assistant",
                "content": """Ordered by how likely each one is to page someone at 3 a.m.

**1. Blocking: `except Exception: pass` hides every failure.** A malformed row, a type error, a lost connection halfway through: the script keeps going and prints `hecho`. Nobody learns that 40% of prices were not updated until a customer does. Log the row and the exception, count failures, and exit non-zero if any occurred, so cron's mail or your alerting sees it.

**2. Blocking: no atomicity.** With `autocommit=True`, each `UPDATE` commits on its own. If the process dies at row 5,000 of 20,000, the catalogue is left half-updated with no way to tell which half. Wrap the whole load in one transaction: either all prices change or none do.

**3. Blocking: the file is read while another team may still be writing it.** Cron fires at a fixed time; the producer finishes "around then". You will occasionally read a truncated or empty CSV, and the script will happily apply it. Require the producer to write to a temp name and rename atomically, and refuse to run on an empty file or on one modified in the last N minutes.

**4. Important: unknown SKUs are silent.** `UPDATE ... WHERE sku = %s` with a SKU that does not exist updates zero rows and raises nothing. Check `cur.rowcount` and report unmatched SKUs; a typo in the producer's export should be visible, not absorbed.

**5. Important: no validation of `precio`.** Postgres will reject `"12,50"` (comma decimal) with an error that `pass` swallows, and will *accept* `"-5"` or `"1250000"`. Parse with `Decimal`, reject negatives and absurd values before touching the database.

**6. Important: credentials in the source.** `app:app@db/prod` is committed to the repo. Read the DSN from an environment variable or a secrets file.

**7. Important: no idempotency or run tracking.** If cron runs twice (manual rerun, overlapping schedules), the second run re-applies the same file. Harmless here because the update is idempotent, but record which file (name + checksum) was applied and when, so you can answer "what happened last night" without guessing.

**8. Minor:** `open()` without `encoding="utf-8"` depends on the locale of the cron environment, which is often `C`/ASCII and breaks on the first accented product name. No timeout on the connection. `print` instead of logging with a timestamp.

**Minimal rewrite that addresses 1-5 and 8:**

```python
import csv
import logging
import os
import sys
from decimal import Decimal, InvalidOperation

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("precios")
RUTA = "/mnt/share/precios.csv"
PRECIO_MAX = Decimal("100000")


def cargar(ruta: str) -> list[tuple[Decimal, str]]:
    filas, errores = [], 0
    with open(ruta, encoding="utf-8", newline="") as f:
        for n, fila in enumerate(csv.DictReader(f), start=2):
            try:
                precio = Decimal(fila["precio"].replace(",", "."))
            except (KeyError, InvalidOperation) as e:
                log.error("línea %d: precio inválido %r (%s)", n, fila.get("precio"), e)
                errores += 1
                continue
            if not (0 <= precio <= PRECIO_MAX):
                log.error("línea %d: precio fuera de rango %s", n, precio)
                errores += 1
                continue
            filas.append((precio, fila["sku"].strip()))
    if errores or not filas:
        raise SystemExit(f"abortado: {errores} filas inválidas, {len(filas)} válidas")
    return filas


def aplicar(dsn: str, filas: list[tuple[Decimal, str]]) -> None:
    no_encontrados = []
    with psycopg.connect(dsn, connect_timeout=10) as conn, conn.transaction():
        for precio, sku in filas:
            cur = conn.execute("UPDATE productos SET precio = %s WHERE sku = %s", (precio, sku))
            if cur.rowcount == 0:
                no_encontrados.append(sku)
    log.info("actualizados %d, sin coincidencia %d", len(filas) - len(no_encontrados), len(no_encontrados))
    if no_encontrados:
        log.warning("SKUs no encontrados: %s", ", ".join(no_encontrados[:50]))


if __name__ == "__main__":
    dsn = os.environ["PRECIOS_DSN"]
    aplicar(dsn, cargar(RUTA))
    sys.exit(0)
```

The policy choice here is "any invalid row aborts the whole run". For a nightly price load that is the safer default: a partially wrong file is better left unapplied, and the error log tells the producing team exactly which lines to fix. If the business prefers "apply what is valid", keep the loop but still exit non-zero.

**How to verify:** three fixture CSVs (valid, one bad price, empty) and a test database. Expected: valid → all rows updated in one transaction; bad price → exit code 1 and zero rows changed; empty → exit code 1. Then kill the process mid-run with a 20,000-row file and confirm the table is unchanged (transaction rolled back).""",
            },
        ]
    },
    # 26) SQL: DISTINCT + JOIN frente a EXISTS; multiturno con IN.
    {
        "messages": [
            {"role": "user", "content": """Dos consultas para "clientes con al menos un pedido en 2026". ¿Cuál es mejor?

A:
```sql
SELECT DISTINCT c.id, c.nombre
FROM clientes c
JOIN pedidos p ON p.cliente_id = c.id
WHERE p.fecha >= '2026-01-01';
```

B:
```sql
SELECT c.id, c.nombre
FROM clientes c
WHERE EXISTS (
  SELECT 1 FROM pedidos p
  WHERE p.cliente_id = c.id AND p.fecha >= '2026-01-01'
);
```"""},
            {
                "role": "assistant",
                "content": """**B.** Las dos devuelven el mismo conjunto de filas, pero B expresa lo que preguntas y A llega al resultado correcto por un rodeo que cuesta caro y se rompe fácil.

**Corrección.** A produce una fila por cada *pedido* y luego `DISTINCT` las colapsa. Funciona mientras las columnas seleccionadas sean solo de `clientes`; en cuanto alguien añada `p.fecha` o `p.importe` al `SELECT` «para ver algo más», el `DISTINCT` deja de deduplicar y vuelven los clientes repetidos. B no puede duplicar: `EXISTS` es una condición sobre cada fila de `clientes`, y cada cliente aparece exactamente una vez pase lo que pase en `pedidos`.

**Coste.** A construye el *join* completo (todas las filas de pedidos de 2026, que pueden ser millones), lo pasa por un `HashAggregate` o un `Sort` + `Unique` para el `DISTINCT`, y descarta casi todo. B se planifica como *semi join*: para cada cliente, en cuanto encuentra **un** pedido que cumple, para de buscar. Con el índice adecuado en `pedidos (cliente_id, fecha)` es una sonda por cliente.

Con 100 000 clientes y 5 millones de pedidos en 2026, A tiene que manejar 5 millones de filas intermedias; B toca como mucho 100 000 sondas de índice. La diferencia es de uno a dos órdenes de magnitud en tiempo y, sobre todo, en memoria.

**Legibilidad.** B se lee como la frase: «clientes para los que existe un pedido de 2026». A obliga al lector a entender que el `DISTINCT` está ahí para corregir la multiplicación del *join*, lo que es un olor: `DISTINCT` casi siempre señala un *join* que no debería estar.

**Cómo comprobarlo:**

1. Igualdad de resultados: `(A) EXCEPT (B)` y `(B) EXCEPT (A)` deben devolver 0 filas.
2. `EXPLAIN (ANALYZE, BUFFERS)` de ambas. En A verás `HashAggregate` o `Unique` sobre un `Hash Join` con millones de `rows`; en B, `Nested Loop Semi Join` o `Hash Semi Join` con `rows` del orden del número de clientes. Compara `shared hit` y `Execution Time`.
3. Confirma que existe `CREATE INDEX ON pedidos (cliente_id, fecha)`; sin él, B hace un escaneo por cliente y la ventaja se reduce.""",
            },
            {"role": "user", "content": "¿Y con `WHERE c.id IN (SELECT cliente_id FROM pedidos WHERE fecha >= '2026-01-01')`? Es lo que tenía antes."},
            {
                "role": "assistant",
                "content": """Para este caso concreto, `IN` es equivalente a `EXISTS`: en Postgres el planificador los convierte en el mismo *semi join* y el rendimiento es idéntico. Puedes quedarte con cualquiera de los dos.

La diferencia aparece en la **negación**. `NOT IN` con una subconsulta que puede devolver `NULL` no devuelve ninguna fila, porque `x NOT IN (1, NULL)` se evalúa como `x <> 1 AND x <> NULL`, y la segunda parte es desconocida. `NOT EXISTS` no tiene ese problema. Como `pedidos.cliente_id` es nullable en muchos esquemas (pedidos de invitado), la versión «clientes **sin** pedidos» con `NOT IN` es un bug esperando a que entre el primer `NULL`.

Mi regla:

| Pregunta | Forma |
|---|---|
| al menos uno | `EXISTS` o `IN` (indistinto) |
| ninguno | `NOT EXISTS` siempre |
| lista literal corta | `IN (1, 2, 3)` |

Un detalle más: `IN` obliga a que la subconsulta devuelva exactamente una columna y que su tipo sea comparable con `c.id`; `EXISTS` acepta cualquier condición en el `WHERE` interno (varias columnas, rangos, joins), así que escala mejor cuando la condición crece. Por consistencia, si la base usa `NOT EXISTS` para la negación, usar `EXISTS` para la afirmación hace que las dos consultas se parezcan y que el siguiente que las lea no tenga que recordar la trampa del `NULL`.""",
            },
        ]
    },
    # 27) Node: bloqueo del event loop y fugas por timers.
    {
        "messages": [
            {"role": "user", "content": """Nuestro servidor Node se congela unos segundos cada vez que alguien descarga el informe mensual y luego sigue. Y la memoria sube poco a poco hasta que reiniciamos. El handler:

```js
app.get("/informe", (req, res) => {
  const filas = db.prepare("SELECT * FROM ventas WHERE mes = ?").all(req.query.mes);
  const datos = fs.readFileSync("/data/plantilla.json", "utf8");
  const informe = construirInforme(JSON.parse(datos), filas);  // CPU, ~2 s para 500k filas
  setInterval(() => registrarProgreso(informe.id), 1000);
  res.json(informe);
});
```"""},
            {
                "role": "assistant",
                "content": """Son dos problemas independientes y el código los muestra a los dos.

**Bloqueante 1: el handler bloquea el *event loop* durante segundos.** Node atiende todas las peticiones en un solo hilo. Mientras `construirInforme` tarda 2 s de CPU, ninguna otra petición se procesa: ni los *health checks*, ni los *websockets*, ni las respuestas pequeñas. Eso es la «congelación». `readFileSync` y `db.prepare().all()` (better-sqlite3, síncrono) suman, pero el grueso es el cálculo.

**Bloqueante 2: `setInterval` sin `clearInterval` nunca.** Cada descarga crea un temporizador que vive para siempre y retiene `informe` (500 000 filas) en su clausura. Diez descargas, diez temporizadores, diez informes en memoria. Esa es la subida lenta hasta el reinicio. Si el progreso tiene sentido, el intervalo debe cancelarse cuando el informe termina o la conexión se cierra; aquí la respuesta ya se envió, así que no tiene sentido ninguno.

**Arreglo mínimo para la fuga** (una línea de borrado): quita el `setInterval`. Si hace falta registrar la descarga, una línea de log síncrona tras `res.json`.

**Arreglo para el bloqueo**, de menos a más cambio:

1. **Sacar la CPU del hilo principal** con `worker_threads`. El informe se construye en un worker y el *event loop* queda libre:

```js
import { Worker } from "node:worker_threads";
import { readFile } from "node:fs/promises";

function construirEnWorker(plantilla, filas) {
  return new Promise((resolve, reject) => {
    const w = new Worker(new URL("./informe-worker.js", import.meta.url), {
      workerData: { plantilla, filas },
    });
    w.once("message", resolve);
    w.once("error", reject);
    w.once("exit", (code) => { if (code !== 0) reject(new Error(`worker exit ${code}`)); });
  });
}

app.get("/informe", async (req, res, next) => {
  try {
    const filas = db.prepare("SELECT * FROM ventas WHERE mes = ?").all(req.query.mes);
    const plantilla = JSON.parse(await readFile("/data/plantilla.json", "utf8"));
    const informe = await construirEnWorker(plantilla, filas);
    res.json(informe);
  } catch (err) {
    next(err);
  }
});
```

Y `informe-worker.js`:

```js
import { parentPort, workerData } from "node:worker_threads";
import { construirInforme } from "./informe.js";

parentPort.postMessage(construirInforme(workerData.plantilla, workerData.filas));
```

Pasar 500 000 filas al worker implica copiarlas (clonado estructurado); si eso pesa, haz que el worker ejecute la consulta él mismo y reciba solo `mes`. Un *pool* de workers (por ejemplo, `piscina`) evita crear un hilo por petición.

2. **Mejor aún: no generar el informe en la petición.** Encolar el trabajo, responder `202 Accepted` con un identificador, y que el cliente consulte o reciba un enlace cuando esté listo. Es lo adecuado para cualquier cosa de más de unos cientos de milisegundos, y además permite reintentos y límites de concurrencia.

**Importante:** `SELECT *` de 500 000 filas a memoria y luego `res.json` de todo serializa megabytes de golpe (otro bloqueo de CPU en `JSON.stringify`). Si el cliente necesita de verdad todas las filas, envía CSV en *streaming*; si no, agrega en SQL y devuelve el resumen.

**Cómo comprobar:**

- Bloqueo: `node --require ./medir-lag.js` con un `setInterval` de 100 ms que mida el retraso real (`perf_hooks.monitorEventLoopDelay`); durante una descarga, el original muestra picos de 2 000 ms y la versión con worker se mantiene por debajo de 10 ms. O más simple: lanza la descarga y en paralelo `curl /health`; con el original tarda 2 s.
- Fuga: `process.memoryUsage().heapUsed` tras 20 descargas y un `global.gc()` (con `--expose-gc`); con el original sube unos cientos de MB y no baja, con el arreglo vuelve al nivel inicial. `process.getActiveResourcesInfo()` también lista los `Timeout` vivos: en el original crecen de uno en uno.""",
            },
        ]
    },
    # 28) Python: invariantes de una caché LRU.
    {
        "messages": [
            {"role": "system", "content": "Responde solo con lo esencial: diagnóstico, diff mínimo y cómo comprobarlo."},
            {"role": "user", "content": """Mi LRU con OrderedDict expulsa cosas que se acaban de usar. ¿Qué invariante rompo?

```python
from collections import OrderedDict

class LRU:
    def __init__(self, capacidad: int):
        self.capacidad = capacidad
        self.datos: OrderedDict[str, object] = OrderedDict()

    def get(self, clave: str):
        return self.datos.get(clave)

    def put(self, clave: str, valor: object) -> None:
        self.datos[clave] = valor
        if len(self.datos) > self.capacidad:
            self.datos.popitem(last=False)
```"""},
            {
                "role": "assistant",
                "content": """**Invariante roto:** «el orden del `OrderedDict` es el orden de último uso, del más antiguo al más reciente». Lo rompes en dos sitios:

1. `get` no mueve la clave al final. Un elemento leído mil veces sigue en la posición donde se insertó y es el primero en salir. Por eso expulsas lo que acabas de usar.
2. `put` sobre una clave existente tampoco la mueve: la asignación en un `OrderedDict` conserva la posición original.

El otro invariante, «`len(datos) <= capacidad`», sí se mantiene; y hay un caso límite: con `capacidad = 0`, `popitem` sobre un dict con un elemento funciona, pero con `capacidad < 0` el constructor acepta un valor absurdo.

**Diff mínimo:**

```python
from collections import OrderedDict

_AUSENTE = object()


class LRU:
    def __init__(self, capacidad: int):
        if capacidad < 1:
            raise ValueError("capacidad debe ser >= 1")
        self.capacidad = capacidad
        self.datos: OrderedDict[str, object] = OrderedDict()

    def get(self, clave: str, por_defecto: object = None):
        valor = self.datos.get(clave, _AUSENTE)
        if valor is _AUSENTE:
            return por_defecto
        self.datos.move_to_end(clave)
        return valor

    def put(self, clave: str, valor: object) -> None:
        self.datos[clave] = valor
        self.datos.move_to_end(clave)
        if len(self.datos) > self.capacidad:
            self.datos.popitem(last=False)
```

`move_to_end` es O(1) y es la operación para la que existe `OrderedDict` frente a un `dict` normal. El centinela `_AUSENTE` distingue «no está» de «está con valor `None`», que con el `get` original era imposible.

**Cómo comprobarlo** (cada test corresponde a un invariante):

```python
def test_get_cuenta_como_uso():
    c = LRU(2)
    c.put("a", 1); c.put("b", 2)
    c.get("a")             # a pasa a ser el más reciente
    c.put("c", 3)          # debe expulsar b, no a
    assert c.get("a") == 1 and c.get("b") is None and c.get("c") == 3

def test_put_de_clave_existente_la_refresca():
    c = LRU(2)
    c.put("a", 1); c.put("b", 2); c.put("a", 10); c.put("c", 3)
    assert c.get("b") is None and c.get("a") == 10

def test_nunca_supera_capacidad():
    c = LRU(3)
    for i in range(100):
        c.put(str(i), i)
        assert len(c.datos) <= 3
```

El primero y el segundo fallan con la versión original. Si la caché va a usarse desde varios hilos, envuelve `get` y `put` en un `threading.Lock`: `move_to_end` + `popitem` no son atómicos entre sí.""",
            },
        ]
    },
    # 29) C: off-by-one en bucle, signed/unsigned, números mágicos; léxico colombiano.
    {
        "messages": [
            {"role": "user", "content": r"""Profe de la universidad nos devolvió esto con "revisar límites y tipos" y nada más. ¿Ustedes qué le ven?

```c
#include <stdio.h>

int promedio(int arr[], int n) {
    int suma = 0;
    for (int i = 0; i <= n; i++) {
        suma += arr[i];
    }
    return suma / n;
}

int main(void) {
    int notas[5] = {80, 90, 70, 85, 95};
    printf("%d\n", promedio(notas, 5));
    return 0;
}
```"""},
            {
                "role": "assistant",
                "content": r"""Tiene razón en las dos cosas, y hay una tercera que no mencionó.

**Bloqueante: `i <= n` lee una posición más allá del arreglo.** Con `n = 5` los índices válidos son 0 a 4; la iteración con `i = 5` lee `arr[5]`, que no existe. En C eso es comportamiento indefinido: a veces lee basura de la pila y el promedio sale mal, a veces «funciona» y el error se esconde hasta que cambia el compilador o las optimizaciones. La condición correcta es `i < n`.

**Importante (tipos): `n` debería ser `size_t`, y la división truncada es una decisión que hay que tomar a propósito.** Un tamaño nunca es negativo; con `int n` el llamador puede pasar `-1`, el bucle no entra y `suma / n` divide 0 entre −1. Con `size_t` el compilador (`-Wsign-compare`) avisa si comparas con un `int`, que es justo el tipo de error que el profe quiere que vean. Además `suma / n` es división entera: `(80+90+70+85+95)/5 = 420/5 = 84` sale exacto, pero `{80, 85}` da 82 y no 82,5. Si quieren el promedio real, devuelvan `double`.

**Importante: `n == 0` divide por cero.** Un arreglo vacío es una entrada legítima; hay que decidir qué devolver (0, o un error) y documentarlo.

**Menor: `suma` puede desbordar** con muchos valores grandes (`int` llega a unos 2 mil millones; 30 000 notas de 100 000 ya se pasan). Acumulen en `long long` o en `double`.

**Versión corregida:**

```c
#include <stddef.h>
#include <stdio.h>

double promedio(const int arr[], size_t n) {
    if (n == 0) return 0.0;
    long long suma = 0;
    for (size_t i = 0; i < n; i++) {
        suma += arr[i];
    }
    return (double)suma / (double)n;
}

#define NUM_NOTAS 5

int main(void) {
    int notas[NUM_NOTAS] = {80, 90, 70, 85, 95};
    printf("%.2f\n", promedio(notas, NUM_NOTAS));
    return 0;
}
```

`const int arr[]` promete que la función no modifica el arreglo; `NUM_NOTAS` evita repetir el 5 en dos sitios (si cambian uno y no el otro, vuelve el error de límites). Y `sizeof notas / sizeof notas[0]` es la alternativa cuando el arreglo está a la vista.

**Cómo verificarlo:**

```sh
gcc -Wall -Wextra -Wconversion -fsanitize=address,undefined -o promedio promedio.c && ./promedio
```

Con el original, AddressSanitizer reporta `stack-buffer-overflow` en la lectura de `arr[5]`; con el corregido imprime `84.00` sin avisos. Prueben también `promedio(notas, 0)` (debe devolver 0 y no reventar) y un arreglo de dos elementos `{80, 85}` (debe dar 82.50).""",
            },
        ]
    },
    # 30) Python: dos formas de cargar configuración (eval frente a json); léxico de México.
    {
        "messages": [
            {"role": "user", "content": """Oye, en el equipo hay dos versiones de cargar la config y no nos ponemos de acuerdo. ¿Cuál dejamos?

A:
```python
def cargar_config(ruta):
    with open(ruta) as f:
        return eval(f.read())
```

B:
```python
import json

def cargar_config(ruta):
    with open(ruta) as f:
        return json.load(f)
```

A nos gusta porque el archivo puede tener tuplas y comentarios de Python."""},
            {
                "role": "assistant",
                "content": """**B, sin discusión.** A no es una forma de leer configuración: es una forma de ejecutar cualquier código que haya en ese archivo con los permisos de tu proceso.

**Por qué A es bloqueante.** `eval` evalúa expresiones de Python arbitrarias. Si el archivo contiene `__import__("os").system("rm -rf /datos")`, se ejecuta. «Nadie va a escribir eso en nuestra config» no es una garantía: el archivo viene de un repositorio, de un volumen compartido, de un `ConfigMap`, de un despliegue automatizado; cualquiera con acceso de escritura a cualquiera de esos sitios tiene ejecución de código en producción. Además `eval` convierte un error de sintaxis en una traza críptica y no da números de línea útiles.

**Qué pierden al pasar a B y cómo recuperarlo:**

- *Comentarios:* JSON no los permite. Si los necesitan, usen TOML (`tomllib` está en la biblioteca estándar desde Python 3.11, solo lectura) o YAML con `yaml.safe_load`. Las dos cosas admiten comentarios y no ejecutan código.
- *Tuplas:* JSON solo tiene listas. Conviertan en el punto de uso: `tuple(cfg["tamano"])`. Una config no debería depender de la diferencia entre lista y tupla.

**Si de verdad quieren sintaxis de Python** (literales, tuplas, `None`), existe `ast.literal_eval`: evalúa únicamente literales (números, cadenas, tuplas, listas, dicts, `True`/`False`/`None`) y lanza `ValueError` ante cualquier llamada, nombre o import. Es la versión segura de A:

```python
import ast

def cargar_config(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        datos = ast.literal_eval(f.read())
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta}: la configuración debe ser un dict")
    return datos
```

Pero sigue sin admitir comentarios, así que mi recomendación es TOML:

```python
import tomllib

def cargar_config(ruta: str) -> dict:
    with open(ruta, "rb") as f:
        return tomllib.load(f)
```

Y la validación de la forma (qué claves, qué tipos) con un `dataclass` o un modelo de Pydantic justo después de cargar, para que un valor mal puesto falle al arrancar y no a las tres de la mañana.

**Cómo comprobar que la decisión es segura:**

```python
def test_config_no_ejecuta_codigo(tmp_path):
    maligno = tmp_path / "c.txt"
    maligno.write_text('__import__("os").getcwd()')
    with pytest.raises(ValueError):
        cargar_config(str(maligno))     # literal_eval rechaza la llamada
```

Con la versión A, ese test no lanza y además ejecuta la llamada. `bandit -r .` marca `eval` (B307) para que no vuelva a entrar en una revisión.""",
            },
        ]
    },
]
