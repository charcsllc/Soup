"""Debugging sistemático: síntoma + traza -> significado, reproducción, hipótesis ordenadas,
evidencia que las distingue, arreglo mínimo y test de regresión. Formato chatml, 30 filas.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

ROWS += [
    # 1) Python asyncio: excepción no recuperada en una tarea lanzada con create_task.
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo un servicio en Python 3.12 con asyncio que consume mensajes de una cola. De vez en cuando deja de procesar sin morir, y en el log solo aparece esto:

```
Task exception was never retrieved
future: <Task finished name='Task-17' coro=<procesar_mensaje() done, defined at /app/worker.py:41> exception=KeyError('customer_id')>
Traceback (most recent call last):
  File "/app/worker.py", line 48, in procesar_mensaje
    cliente = payload["customer_id"]
KeyError: 'customer_id'
```

Las tareas se lanzan con `asyncio.create_task(procesar_mensaje(msg))` dentro del bucle que lee la cola, y hay un `asyncio.Semaphore(20)` para no procesar más de 20 a la vez. ¿Por qué no se cae el proceso y por qué deja de procesar?""",
            },
            {
                "role": "assistant",
                "content": """**Qué dice el error.** `Task exception was never retrieved` no es un crash: es asyncio avisando, cuando recolecta la tarea, de que terminó con una excepción que nadie leyó. `create_task` es «dispara y olvida»: la excepción se guarda dentro del `Task` y solo sale a la luz si alguien hace `await` o `.result()`. Como nadie lo hace, el proceso sigue vivo y el mensaje aparece tarde y fuera de contexto.

**Por qué deja de procesar.** Hipótesis, de más a menos probable:

1. **El semáforo nunca se libera en las tareas que fallan.** Si `procesar_mensaje` hace `await sem.acquire()` y el `release()` está después del código que lanza `KeyError`, cada mensaje malformado consume un permiso para siempre. Tras 20 mensajes malos, el bucle se queda bloqueado en `acquire()` sin ningún error visible. Encaja con «deja de procesar sin morir».
2. **Las tareas se recolectan a medias.** El bucle de eventos solo guarda referencias débiles a las tareas; si no conservas la referencia que devuelve `create_task`, el GC puede destruir una tarea en vuelo. Eso pierde mensajes, pero no bloquea el consumo, así que explica menos el síntoma.
3. **La propia corutina del bucle muere en silencio** porque también fue lanzada con `create_task` y nadie la espera.

**Evidencia que las distingue.** Añade un volcado de estado al recibir `SIGUSR1`:

```python
import asyncio, signal, sys

def volcar_estado(sem: asyncio.Semaphore) -> None:
    tareas = asyncio.all_tasks()
    print(f"tareas vivas={len(tareas)} semaforo_libre={sem._value}", file=sys.stderr)
    for t in tareas:
        print(" ", t.get_name(), t.get_coro().__qualname__, file=sys.stderr)

loop = asyncio.get_running_loop()
loop.add_signal_handler(signal.SIGUSR1, volcar_estado, sem)
```

Si cuando el servicio «se para» ves `semaforo_libre=0` y pocas tareas vivas, es la hipótesis 1. Si el bucle lector no aparece en la lista, es la 3. Ejecuta además con `PYTHONASYNCIODEBUG=1`: el aviso sale al momento, con la traza de dónde se creó la tarea.

**Arreglo mínimo.** El semáforo como *context manager* (se libera también con excepción) y un `done_callback` que registre la excepción en el momento:

```python
import logging

log = logging.getLogger(__name__)
tareas_vivas: set[asyncio.Task] = set()

async def procesar_mensaje(msg: dict, sem: asyncio.Semaphore) -> None:
    async with sem:
        payload = msg["payload"]
        cliente = payload["customer_id"]
        await guardar(cliente, payload)

def _al_terminar(tarea: asyncio.Task) -> None:
    tareas_vivas.discard(tarea)
    if not tarea.cancelled() and (exc := tarea.exception()) is not None:
        log.error("mensaje descartado por %r", exc, exc_info=exc)

async def consumir(cola: asyncio.Queue, sem: asyncio.Semaphore) -> None:
    while True:
        msg = await cola.get()
        tarea = asyncio.create_task(procesar_mensaje(msg, sem), name=f"msg-{msg['id']}")
        tareas_vivas.add(tarea)
        tarea.add_done_callback(_al_terminar)
```

El `set` resuelve la hipótesis 2 de paso, y `tarea.exception()` marca la excepción como recuperada, así que el aviso desaparece. Si puedes esperar a todas las tareas de un lote, `asyncio.TaskGroup` (3.11+) hace esto solo y además cancela a las hermanas cuando una falla; para un consumidor infinito el patrón de arriba es más adecuado.

**Test de regresión.** Un mensaje malo seguido de 25 buenos: si el semáforo se fugara, el test se quedaría colgado y el `timeout` lo haría fallar.

```python
import pytest

@pytest.mark.asyncio
async def test_un_mensaje_malo_no_bloquea_el_consumo(monkeypatch):
    guardados: list[str] = []
    async def guardar_falso(cliente, payload): guardados.append(cliente)
    monkeypatch.setattr("worker.guardar", guardar_falso)

    cola: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(1)
    await cola.put({"id": 0, "payload": {}})
    for i in range(1, 26):
        await cola.put({"id": i, "payload": {"customer_id": f"c{i}"}})

    consumidor = asyncio.create_task(consumir(cola, sem))
    async with asyncio.timeout(2):
        while len(guardados) < 25:
            await asyncio.sleep(0.01)
    consumidor.cancel()
    assert guardados == [f"c{i}" for i in range(1, 26)]
```

Con `Semaphore(1)` el fallo original bloquearía al primer mensaje malo, así que el test lo detecta en la primera ejecución.""",
            },
        ]
    },
    # 2) Node/Express: rechazo de promesa no capturado reinicia el proceso.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Mi API en Express 4 (Node 20) se reinicia sola en producción varias veces al día. PM2 muestra el contador de restarts subiendo y en el log de errores aparece:

```
/app/src/routes/orders.js:27
    const order = await Order.findById(req.params.id);
                              ^
MongooseServerSelectionError: connect ECONNREFUSED 10.0.3.12:27017
    at _handleConnectionErrors (/app/node_modules/mongoose/lib/connection.js:1110:11)
    at NativeConnection.openUri (/app/node_modules/mongoose/lib/connection.js:1041:11)
Node.js v20.11.1
```

Tengo un middleware de errores con cuatro parámetros al final de `app.js`. ¿Por qué no lo captura?""",
            },
            {
                "role": "assistant",
                "content": """Hay dos problemas distintos en esa traza y conviene separarlos:

- **Por qué muere el proceso**: Express 4 no sabe nada de promesas. Si un handler `async` rechaza, Express no recibe el error, Node lo ve como `unhandledRejection` y, desde Node 15, eso termina el proceso. Tu middleware de cuatro parámetros solo recibe errores pasados con `next(err)` o lanzados de forma síncrona.
- **Por qué hay un error que capturar**: `ECONNREFUSED 10.0.3.12:27017` significa que Mongo no aceptó la conexión en ese momento. Es la causa raíz de cada reinicio, pero el bug del código es que *cualquier* rechazo tumba la API.

**Reproducir.** No hace falta Mongo caído: fuerza un rechazo en el handler.

```js
// temporal, en una ruta de prueba
app.get("/boom", async () => { throw new Error("prueba"); });
```

Con `curl localhost:3000/boom` el proceso cae con `Error: prueba`. Si el middleware de errores sí respondiera, verías un 500. Eso confirma la causa en diez segundos.

**Hipótesis sobre el ECONNREFUSED, por probabilidad:**

1. Mongo se reinicia o hay *failover* del réplica set y durante unos segundos nadie escucha en esa IP. Evidencia: `pm2 logs --err --lines 200` y compara horas con los logs de Mongo (`db.adminCommand({getLog: "global"})`) o con el *uptime* del contenedor.
2. Un límite de conexiones o el `serverSelectionTimeoutMS` (30 s por defecto) agotado bajo carga. Evidencia: `mongoose.connection.on("disconnected", () => log.warn("mongo disconnected"))` y `db.serverStatus().connections`.
3. DNS o IP cambiante del servicio (típico en Docker/Kubernetes cuando Mongo se recrea). Evidencia: si la IP de la traza no coincide con `getent hosts mongo`.

**Arreglo mínimo (una sola línea por handler no es necesario).** Un envoltorio que convierta el rechazo en `next(err)`:

```js
// src/async-handler.js
export const asyncHandler = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};
```

```js
// src/routes/orders.js
import { asyncHandler } from "../async-handler.js";

router.get("/:id", asyncHandler(async (req, res) => {
  const order = await Order.findById(req.params.id);
  if (!order) return res.status(404).json({ error: "order not found" });
  res.json(order);
}));
```

Si estás en condiciones de migrar, Express 5 (estable desde 5.1) propaga los rechazos al middleware de errores sin envoltorio; el cambio relevante es que las rutas con comodines cambian de sintaxis (`/files/*splat`).

No pongas `process.on("unhandledRejection", () => {})` para «silenciarlo»: oculta el bug y deja el proceso en un estado desconocido. Si lo añades, que sea para registrar y salir con código distinto de cero.

Para el segundo problema, configura el cliente para que una desconexión breve no sea un error por petición:

```js
await mongoose.connect(process.env.MONGO_URL, {
  serverSelectionTimeoutMS: 5000,
  maxPoolSize: 20,
});
```

Mongoose reintenta la selección de servidor durante esos 5 s; una caída de 2 s se absorbe y una de 30 s produce 503 controlados en vez de reinicios.

**Test de regresión** con supertest, sin base de datos:

```js
import request from "supertest";
import { jest } from "@jest/globals";
import { app } from "../src/app.js";
import { Order } from "../src/models/order.js";

test("un rechazo en el handler produce 500 y no mata el proceso", async () => {
  jest.spyOn(Order, "findById").mockRejectedValue(new Error("ECONNREFUSED"));
  const res = await request(app).get("/orders/abc");
  expect(res.status).toBe(500);
  expect(res.body).toEqual({ error: "internal error" });
});
```

Antes del arreglo, este test termina el proceso de Jest con el rechazo; después, pasa.""",
            },
        ]
    },
    # 3) Java/Spring: OutOfMemoryError por caché sin límite (fuga, no falta de memoria).
    {
        "messages": [
            {
                "role": "user",
                "content": """Nuestra app Spring Boot 3.2 se cae cada dos o tres días con esto:

```
java.lang.OutOfMemoryError: Java heap space
	at java.base/java.util.HashMap.resize(HashMap.java:702)
	at java.base/java.util.HashMap.putVal(HashMap.java:659)
	at java.base/java.util.HashMap.put(HashMap.java:618)
	at com.acme.reports.ReportCache.put(ReportCache.java:31)
	at com.acme.reports.ReportService.generar(ReportService.java:88)
	at com.acme.reports.ReportController.descargar(ReportController.java:44)
```

Le subimos el heap de 1 GB a 4 GB y nomás ganamos un día más. Corremos con `-Xmx4g` en un contenedor de 6 GB. ¿Es un leak o nos falta memoria? Quiero checar antes de volver a subirla.""",
            },
            {
                "role": "assistant",
                "content": """Es una fuga, y el dato que lo demuestra ya lo tienes: **cuadruplicar el heap solo ganó un día**. Si fuera falta de memoria, con 4 GB aguantaría indefinidamente o, como mínimo, cuatro veces más. Un crecimiento que consume cualquier tamaño que le des es memoria que nunca se libera.

**Qué dice la traza.** El OOM saltó mientras un `HashMap` dentro de `ReportCache` crecía (`resize`). Es el punto donde se acabó la memoria, no necesariamente el único culpable, pero una caché basada en `HashMap` sin política de expulsión es el sospechoso número uno.

**Reproducir en minutos, no en días.** Lanza un bucle de peticiones a `/reports` variando los parámetros (fechas, filtros) y mira el heap *después* de cada GC completo:

```bash
for i in $(seq 1 5000); do curl -s "http://localhost:8080/reports?from=2024-01-$((i % 28 + 1))&tipo=$i" > /dev/null; done
jcmd <pid> GC.run
jcmd <pid> GC.heap_info
```

Si el valor de `used` tras `GC.run` sube de forma monótona con el número de parámetros distintos, confirmado.

**Hipótesis en orden:**

1. **Caché sin límite ni expiración**, indexada por los parámetros de la petición. Cada combinación nueva es una entrada que vive para siempre.
2. **Clave con `equals`/`hashCode` mal definidos** (por ejemplo un objeto de filtros sin `record` ni `equals`): aunque los parámetros se repitan, cada petición inserta una entrada nueva. Mismo síntoma, incluso con tráfico repetitivo.
3. **Entradas gigantes**: el valor guardado es el informe completo (`byte[]` del PDF) y no sus metadatos.

**Evidencia que las separa.** Un histograma de clases cuesta un segundo y no para la app:

```bash
jcmd <pid> GC.class_histogram | head -15
```

Si dominan `byte[]` y `com.acme.reports.Report`, es la 3 (o 1 con valores grandes). Si domina `HashMap$Node` con tus clases de filtro como clave, es 1 o 2; para distinguirlas, cuenta claves únicas frente a peticiones únicas en el log. Para el caso definitivo, activa el volcado en el próximo OOM y ábrelo en Eclipse MAT (vista *dominator tree*):

```
-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps
```

**Arreglo mínimo.** Sustituye el `HashMap` por una caché acotada. Caffeine ya viene como *starter* en Spring Boot:

```java
// build.gradle: implementation("com.github.ben-manes.caffeine:caffeine")
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import java.time.Duration;

public final class ReportCache {
    private final Cache<ReportKey, Report> cache = Caffeine.newBuilder()
            .maximumSize(500)
            .expireAfterWrite(Duration.ofMinutes(30))
            .recordStats()
            .build();

    public Report get(ReportKey key) { return cache.getIfPresent(key); }
    public void put(ReportKey key, Report report) { cache.put(key, report); }
    public long size() { return cache.estimatedSize(); }
}

public record ReportKey(String tipo, LocalDate desde, LocalDate hasta) {}
```

El `record` como clave resuelve de paso la hipótesis 2. Expón `cache.stats()` con Micrometer: la tasa de aciertos te dirá si la caché siquiera sirve.

Sobre el contenedor: `-Xmx4g` en 6 GB deja 2 GB para metaspace, hilos y memoria nativa, está bien. Mejor `-XX:MaxRAMPercentage=70` para que siga siendo correcto si cambian el límite del pod.

**Test de regresión:**

```java
@Test
void laCacheNoCreceSinLimite() {
    var cache = new ReportCache();
    for (int i = 0; i < 10_000; i++) {
        cache.put(new ReportKey("ventas", LocalDate.of(2024, 1, 1).plusDays(i), LocalDate.now()), new Report(new byte[1024]));
    }
    cache.cleanUp();
    assertTrue(cache.size() <= 500, "la caché superó su máximo: " + cache.size());
}
```

Con el `HashMap` original, `size()` devuelve 10 000 y el test falla.""",
            },
        ]
    },
    # 4) Go: fatal error por escrituras concurrentes en un map (condición de carrera).
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi servidor en Go 1.23 se muere en producción con esto, pero en local nunca lo he visto:

```
fatal error: concurrent map writes

goroutine 142 [running]:
main.(*Metrics).Inc(0xc000112000, {0xc0001a4030, 0xb})
	/app/metrics.go:22 +0x6e
main.handleOrder({0x8b2f40, 0xc0002c4000}, 0xc0001c8500)
	/app/handlers.go:57 +0x1f4
net/http.HandlerFunc.ServeHTTP(0x7f1b20, {0x8b2f40, 0xc0002c4000}, 0xc0001c8500)
	/usr/local/go/src/net/http/server.go:2171 +0x29
```

`Metrics` tiene un `map[string]int` con contadores. ¿Cómo lo arreglo sin meter un mutex en cada sitio donde se usa?""",
            },
            {
                "role": "assistant",
                "content": """**Qué significa.** El runtime detectó dos goroutines escribiendo en el mismo `map` a la vez. `net/http` atiende cada petición en su propia goroutine, así que dos peticiones simultáneas que llamen a `Inc` bastan. Los maps de Go no son seguros para escritura concurrente, y este `fatal error` no se puede capturar con `recover`: el proceso muere sí o sí. En local no lo ves porque nunca hay dos peticiones en el mismo microsegundo; en producción, sí.

Aquí no hay varias hipótesis sobre la causa: la traza es inequívoca. Lo que sí vale la pena averiguar es **si hay más maps con el mismo problema**, y para eso está el detector de carreras.

**Reproducir en local, determinista:**

```go
// metrics_test.go
func TestIncConcurrente(t *testing.T) {
	m := NewMetrics()
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 1000; j++ {
				m.Inc("orders_total")
			}
		}()
	}
	wg.Wait()
	if got := m.Get("orders_total"); got != 100_000 {
		t.Fatalf("contador = %d, esperaba 100000", got)
	}
}
```

```bash
go test -race -run TestIncConcurrente ./...
```

Con `-race` el test falla con `WARNING: DATA RACE` y la pila de ambas escrituras, aunque el map no llegue a corromperse. Sin `-race`, el `if` final también falla casi siempre porque se pierden incrementos.

**Arreglo mínimo.** No necesitas un mutex «en cada sitio»: el mutex va **dentro** de `Metrics`, y los llamadores no cambian.

```go
package main

import "sync"

type Metrics struct {
	mu       sync.Mutex
	counters map[string]int
}

func NewMetrics() *Metrics {
	return &Metrics{counters: make(map[string]int)}
}

func (m *Metrics) Inc(name string) {
	m.mu.Lock()
	m.counters[name]++
	m.mu.Unlock()
}

func (m *Metrics) Get(name string) int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.counters[name]
}
```

Dos alternativas y por qué no las elijo como primer paso:

- `sync.Map`: pensado para claves que se escriben una vez y se leen mucho. Un contador necesita leer-y-escribir atómico, y `Load` + `Store` no lo es; acabarías perdiendo incrementos igual.
- `atomic.Int64` por contador, con el map rellenado al arrancar y después solo leído: es la opción más rápida bajo mucha contención, pero exige registrar los nombres por adelantado. Pásate a ella solo si el perfil (`go tool pprof`) muestra el mutex como cuello de botella; con contadores HTTP normales no lo será.

**Para no repetirlo.** Añade `-race` a la CI (`go test -race ./...`) y, si tenéis un entorno de *staging*, compila el binario con `go build -race` una temporada: cuesta memoria y CPU (2-10x), pero encuentra las carreras que un test unitario no cubre. Y revisa el resto de maps compartidos (`grep -n "map\\[" --include=*.go -r .`) con la pregunta: ¿quién escribe aquí y desde qué goroutine?""",
            },
        ]
    },
    # 5) Rust principiante: unwrap() sobre None al leer configuración.
    {
        "messages": [
            {"role": "system", "content": "Explica para alguien que está empezando con Rust, sin jerga innecesaria y con el método a la vista."},
            {
                "role": "user",
                "content": """Estoy aprendiendo Rust y mi programa que lee un archivo de configuración explota:

```
thread 'main' panicked at src/main.rs:14:48:
called `Option::unwrap()` on a `None` value
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

La línea 14 es:

```rust
let port: u16 = config.get("port").unwrap().parse().unwrap();
```

`config` es un `HashMap<String, String>` que lleno leyendo `config.toml` línea a línea. El archivo tiene `port = 8080`, lo acabo de comprobar.""",
            },
            {
                "role": "assistant",
                "content": """**Qué dice el error.** `Option::unwrap() on a None value` significa que `config.get("port")` devolvió `None`: la clave `"port"` **no está en el mapa**. No es un problema de `parse` (ese fallaría con `Result::unwrap()` on an `Err` value). Así que el archivo dice `port = 8080`, pero lo que llega al mapa no tiene una clave exactamente igual a `port`.

**Cómo verlo con tus propios ojos.** Antes de adivinar, imprime lo que hay en el mapa justo antes de la línea 14:

```rust
eprintln!("claves: {:?}", config.keys().collect::<Vec<_>>());
```

**Hipótesis, de más a menos probable:**

1. **La clave lleva espacios o comillas**: si partes cada línea con `split('=')`, la clave es `"port "` (con espacio final) y el valor `" 8080"`. Verías `claves: ["port "]`. Es lo más habitual al parsear a mano.
2. **La clave está dentro de una sección**: con `[server]` encima, tu lector quizá guarda `"[server]"` como clave o la ignora, pero `port` sigue siendo `port`. Esto se descarta rápido con el `eprintln!`.
3. **No estás leyendo el archivo que crees**: `cargo run` usa como directorio de trabajo el de donde lo lanzas, no el de `src/`. Si abres `"config.toml"` con ruta relativa desde otra carpeta, puede que estés leyendo un archivo vacío o antiguo. Verías `claves: []`.

**Arreglo mínimo.** Recorta clave y valor al leer, y sustituye los `unwrap` por errores que digan qué faltó:

```rust
use std::collections::HashMap;
use std::fs;

fn leer_config(ruta: &str) -> Result<HashMap<String, String>, String> {
    let texto = fs::read_to_string(ruta).map_err(|e| format!("no pude leer {ruta}: {e}"))?;
    let mut config = HashMap::new();
    for linea in texto.lines() {
        let linea = linea.trim();
        if linea.is_empty() || linea.starts_with('#') || linea.starts_with('[') {
            continue;
        }
        if let Some((clave, valor)) = linea.split_once('=') {
            config.insert(clave.trim().to_string(), valor.trim().trim_matches('"').to_string());
        }
    }
    Ok(config)
}

fn puerto(config: &HashMap<String, String>) -> Result<u16, String> {
    let valor = config.get("port").ok_or("falta la clave 'port' en la configuración")?;
    valor.parse::<u16>().map_err(|e| format!("'port' no es un número válido ({valor}): {e}"))
}

fn main() -> Result<(), String> {
    let config = leer_config("config.toml")?;
    let port = puerto(&config)?;
    println!("escuchando en el puerto {port}");
    Ok(())
}
```

Qué cambia: `ok_or` convierte el `None` en un `Err` con mensaje, el `?` lo devuelve hacia arriba, y `main` lo imprime en vez de hacer *panic*. En Rust, `unwrap` es para «sé que esto no puede fallar»; una clave de un archivo que escribe un humano sí puede fallar.

**Test para que no vuelva a pasar:**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lee_port_con_espacios_y_secciones() {
        let mut config = HashMap::new();
        for linea in "[server]\nport = 8080\n".lines() {
            if let Some((k, v)) = linea.split_once('=') {
                config.insert(k.trim().to_string(), v.trim().to_string());
            }
        }
        assert_eq!(puerto(&config), Ok(8080));
    }

    #[test]
    fn sin_port_devuelve_error_claro() {
        let config = HashMap::new();
        assert_eq!(puerto(&config).unwrap_err(), "falta la clave 'port' en la configuración");
    }
}
```

Cuando el proyecto crezca, usa el crate `toml` con `serde`: te ahorra el parser casero y los errores traen número de línea.""",
            },
        ]
    },
]

ROWS += [
    # 6) C: desbordamiento de heap detectado por Valgrind (usuario en inglés).
    {
        "messages": [
            {
                "role": "user",
                "content": """My C program crashes with `Segmentation fault (core dumped)`, but only when the input file has more than about 1000 lines. Valgrind says:

```
==4821== Invalid write of size 1
==4821==    at 0x4C3A0F3: strcpy (vg_replace_strmem.c:553)
==4821==    by 0x10923B: load_lines (reader.c:38)
==4821==    by 0x1094E0: main (main.c:22)
==4821==  Address 0x4a4d0f8 is 0 bytes after a block of size 64,000 alloc'd
==4821==    at 0x4C2FB0F: malloc (vg_replace_malloc.c:299)
==4821==    by 0x1091F2: load_lines (reader.c:25)
```

reader.c:

```c
#define MAX_LINES 1000
#define LINE_LEN 64

char *load_lines(FILE *f, int *count) {
    char *buf = malloc(MAX_LINES * LINE_LEN);
    char line[256];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        strcpy(buf + n * LINE_LEN, line);
        n++;
    }
    *count = n;
    return buf;
}
```""",
            },
            {
                "role": "assistant",
                "content": """**What Valgrind is telling you.** "Invalid write of size 1 ... 0 bytes after a block of size 64,000" means `strcpy` wrote the first byte past the end of your buffer. The buffer is `1000 * 64 = 64,000` bytes, so line number 1001 lands at offset 64,000, exactly one byte past the end. The segfault only shows up above ~1000 lines because the heap overflow usually corrupts neighbouring allocator metadata silently; whether and when it crashes depends on what sits after the block, which is why the crash threshold feels fuzzy.

There is a **second bug** in the same line that Valgrind has not hit yet: `line` holds up to 255 characters, but each slot in `buf` is 64 bytes. Any line longer than 63 characters (62 plus the newline, plus the terminator) overflows into the next slot, and the last slot overflows the block.

**Reproduce both deterministically:**

```bash
seq 1 1001 | ./prog                      # bug 1: too many lines
printf '%0300d\\n' 0 | ./prog            # bug 2: a line longer than the slot
```

Build with AddressSanitizer for the fastest signal; it aborts on the first bad byte with the exact line instead of crashing somewhere later:

```bash
gcc -g -O1 -fsanitize=address,undefined -o prog main.c reader.c
```

**Minimal fix.** Grow the buffer on demand and copy with a bound. Keeping the fixed-width layout (so `main` does not change) is the smallest change:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_LEN 64

char *load_lines(FILE *f, int *count) {
    size_t cap = 1024;
    char *buf = malloc(cap * LINE_LEN);
    if (!buf) return NULL;
    char line[256];
    size_t n = 0;
    while (fgets(line, sizeof line, f)) {
        if (n == cap) {
            cap *= 2;
            char *tmp = realloc(buf, cap * LINE_LEN);
            if (!tmp) { free(buf); return NULL; }
            buf = tmp;
        }
        line[strcspn(line, "\\n")] = '\\0';
        snprintf(buf + n * LINE_LEN, LINE_LEN, "%s", line);   /* truncates, always terminates */
        n++;
    }
    *count = (int)n;
    return buf;
}
```

`snprintf` with the slot size is the bounded copy; `strncpy` would not guarantee the terminator. If silently truncating long lines is unacceptable for your data, return an error instead of truncating, but decide it explicitly. The caller must `free(buf)` and check for `NULL`.

**Regression test** (plain C, runs under ASan in CI):

```c
#include <assert.h>

static void test_many_lines(void) {
    FILE *f = tmpfile();
    for (int i = 0; i < 5000; i++) fprintf(f, "line %d\\n", i);
    rewind(f);
    int n = 0;
    char *buf = load_lines(f, &n);
    assert(buf && n == 5000);
    assert(strcmp(buf + 4999 * LINE_LEN, "line 4999") == 0);
    free(buf);
    fclose(f);
}

static void test_long_line_is_truncated_not_overflowed(void) {
    FILE *f = tmpfile();
    for (int i = 0; i < 300; i++) fputc('x', f);
    fputc('\\n', f);
    rewind(f);
    int n = 0;
    char *buf = load_lines(f, &n);
    assert(n == 1 && strlen(buf) == LINE_LEN - 1);
    free(buf);
    fclose(f);
}
```

With the original code, the first test overflows at line 1025 and ASan aborts; the second overflows on the very first line.""",
            },
        ]
    },
    # 7) Django ORM: N+1, luego el tiempo restante (multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Un endpoint de listado en Django 5 tarda casi 4 s con solo 200 pedidos. Django Debug Toolbar dice «1201 queries in 3.8 s». La vista:

```python
def pedidos(request):
    data = [
        {
            "id": p.id,
            "cliente": p.cliente.nombre,
            "lineas": [linea.producto.nombre for linea in p.lineas.all()],
        }
        for p in Pedido.objects.filter(estado="abierto")
    ]
    return JsonResponse(data, safe=False)
```

Cada pedido tiene unas 4 líneas.""",
            },
            {
                "role": "assistant",
                "content": """Es el problema **N+1** por partida triple. Las 1201 consultas se descomponen exactamente así:

- 1 consulta para los 200 pedidos.
- 200 consultas para `p.cliente` (una por pedido, al acceder a la clave foránea).
- 200 consultas para `p.lineas.all()`.
- 800 consultas para `linea.producto` (4 líneas × 200 pedidos).

1 + 200 + 200 + 800 = 1201. La cuenta cuadra, así que no hace falta buscar otra causa todavía.

**Arreglo mínimo:** decirle al ORM que cargue las relaciones de antemano. `select_related` para claves foráneas directas (hace un JOIN), `prefetch_related` para relaciones inversas o anidadas (hace una consulta extra por nivel y une en Python):

```python
def pedidos(request):
    consulta = (
        Pedido.objects.filter(estado="abierto")
        .select_related("cliente")
        .prefetch_related("lineas__producto")
    )
    data = [
        {
            "id": p.id,
            "cliente": p.cliente.nombre,
            "lineas": [linea.producto.nombre for linea in p.lineas.all()],
        }
        for p in consulta
    ]
    return JsonResponse(data, safe=False)
```

Resultado: 3 consultas (pedidos con JOIN a cliente, líneas, productos), independientemente del número de pedidos. Importante: el `p.lineas.all()` del bucle debe quedarse tal cual; si lo cambias por `p.lineas.filter(...)` el *prefetch* se descarta y vuelves a N+1.

**Test de regresión** que fija el número de consultas, para que nadie lo rompa al añadir un campo:

```python
from django.test import TestCase

class PedidosViewTests(TestCase):
    def test_listado_hace_tres_consultas_sin_importar_el_volumen(self):
        for i in range(30):
            pedido = Pedido.objects.create(cliente=Cliente.objects.create(nombre=f"c{i}"), estado="abierto")
            for j in range(4):
                Linea.objects.create(pedido=pedido, producto=Producto.objects.create(nombre=f"p{i}-{j}"))
        with self.assertNumQueries(3):
            respuesta = self.client.get("/pedidos/")
        self.assertEqual(len(respuesta.json()), 30)
```""",
            },
            {
                "role": "user",
                "content": "Lo apliqué y bajó a 3 queries, pero el endpoint sigue tardando 1,2 s. ¿Qué más puede ser?",
            },
            {
                "role": "assistant",
                "content": """Con 3 consultas y ~1000 objetos, 1,2 s es demasiado. Hay que saber **dónde** se va el tiempo, y la Debug Toolbar ya lo separa: mira el panel SQL (tiempo total de las 3 consultas) frente al tiempo de la petición.

**Si el SQL ocupa casi todo el tiempo** (lo más probable), la sospechosa es la primera consulta, `filter(estado="abierto")`: si la tabla de pedidos tiene cientos de miles de filas y `estado` no tiene índice, es un recorrido completo. Compruébalo en la base de datos:

```sql
EXPLAIN ANALYZE SELECT ... FROM pedidos_pedido WHERE estado = 'abierto';
```

Un `Seq Scan` con `rows=400000` lo confirma. Arreglo: un índice, preferiblemente parcial, porque los pedidos abiertos son pocos y se consultan mucho:

```python
class Pedido(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["estado"], name="pedido_estado_idx", condition=Q(estado="abierto")),
        ]
```

Tras `makemigrations` y `migrate`, el mismo `EXPLAIN` debe mostrar `Index Scan`.

**Si el SQL es rápido y el tiempo está en Python**, los culpables típicos son: un `JsonResponse` serializando objetos pesados (campos `TextField` enormes que no usas: recórtalos con `.only("id", "cliente__nombre")` y `Prefetch("lineas", queryset=Linea.objects.select_related("producto").only("producto__nombre", "pedido_id"))`), o *middleware* de terceros. Un `cProfile` de la vista lo zanja:

```bash
python -m cProfile -s cumulative manage.py test_pedidos_view | head -30
```

Orden recomendado: `EXPLAIN` primero (cinco segundos), índice si hace falta, y solo después `only()`/perfil. Añade al test anterior un `assertLess(duracion, 0.2)` con 30 pedidos; no detecta el índice que falta en producción, pero sí una regresión en el código de la vista.""",
            },
        ]
    },
    # 8) Rendimiento: cuadrático oculto en una deduplicación con `in` sobre lista.
    {
        "messages": [
            {
                "role": "user",
                "content": """Tenemos un script que deduplica correos de una exportación (unos 300 000) y tarda 40 minutos. No hace nada raro:

```python
def deduplicar(correos: list[str]) -> list[str]:
    unicos = []
    for correo in correos:
        normalizado = correo.strip().lower()
        if normalizado not in unicos:
            unicos.append(normalizado)
    return unicos
```

Con 10 000 correos va rápido. ¿Es Python que es lento o estoy haciendo algo mal?""",
            },
            {
                "role": "assistant",
                "content": """Es el código: tiene un **cuadrático escondido**. `normalizado not in unicos` recorre la lista entera (O(n)) y lo haces una vez por correo, así que el total es O(n²). Con 300 000 correos y, digamos, 250 000 únicos, son del orden de 3,7 × 10¹⁰ comparaciones de cadenas. Eso son los 40 minutos. Con 10 000 son 900 veces menos, por eso ahí no se nota.

**Cómo confirmarlo en un minuto**, sin fiarse de la teoría: mide con el doble de datos. Si tarda el cuádruple, es cuadrático.

```python
import time, random, string

def muestra(n):
    return [f"{''.join(random.choices(string.ascii_lowercase, k=8))}@x.com" for _ in range(n)]

for n in (10_000, 20_000, 40_000):
    datos = muestra(n)
    t = time.perf_counter()
    deduplicar(datos)
    print(n, round(time.perf_counter() - t, 2), "s")
```

Salida esperada con la versión actual: algo como `0.6 s`, `2.4 s`, `9.7 s` (×4 por cada ×2). Con la versión corregida, los tres números serán de milisegundos y lineales.

**Arreglo mínimo:** un `set` para la comprobación de pertenencia, que es O(1) de media. Si el orden de aparición importa (normalmente sí en una exportación), mantén la lista además del conjunto, o usa `dict.fromkeys`, que conserva el orden desde Python 3.7:

```python
def deduplicar(correos: list[str]) -> list[str]:
    return list(dict.fromkeys(c.strip().lower() for c in correos))
```

Una línea, O(n), y el mismo resultado que antes (primera aparición gana). Si no te importa el orden, `set(...)` a secas vale, pero devuelve las cadenas en orden arbitrario y eso suele sorprender aguas abajo.

Dos detalles de paso:

- `strip().lower()` sobre el correo entero está bien para deduplicar, pero técnicamente la parte local (`Juan@`) distingue mayúsculas según el RFC; en la práctica nadie lo hace y normalizar todo es lo correcto para este caso.
- Si el mismo script luego construye un string de salida con `+=` en un bucle, en CPython es amortizado lineal, pero `"\\n".join(unicos)` es más claro y portable.

**Test de regresión** (corrección y una cota de tiempo generosa que el cuadrático no puede cumplir):

```python
import time

def test_deduplicar_conserva_primera_aparicion():
    assert deduplicar(["A@x.com", " b@x.com", "a@x.com", "B@X.COM "]) == ["a@x.com", "b@x.com"]

def test_deduplicar_es_lineal():
    datos = [f"u{i % 150_000}@x.com" for i in range(300_000)]
    t = time.perf_counter()
    assert len(deduplicar(datos)) == 150_000
    assert time.perf_counter() - t < 2.0
```

La versión original tarda minutos en el segundo test; la nueva, menos de medio segundo.""",
            },
        ]
    },
    # 9) Zona horaria y DST: tarea programada que se salta un día y se duplica en otro (rioplatense).
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y sin vueltas."},
            {
                "role": "user",
                "content": """Tengo una tarea con APScheduler 3.10 que manda un resumen todos los días a las 02:30 hora de Madrid. Este año el 29 de marzo no se mandó y el 26 de octubre del año pasado se mandó dos veces. El trigger es `CronTrigger(hour=2, minute=30, timezone="Europe/Madrid")` y el server corre en UTC. ¿Me explicás qué pasa? No quiero volver a comerme el reclamo del cliente.""",
            },
            {
                "role": "assistant",
                "content": """Lo que te pasó es el horario de verano, y las dos fechas lo delatan:

- **29 de marzo de 2026**: en Madrid los relojes saltan de las 02:00 a las 03:00. Las 02:30 de ese día **no existen**. Un trigger que busca «02:30 hora local» no encuentra ese instante y se salta el día.
- **26 de octubre de 2025**: los relojes vuelven de las 03:00 a las 02:00. Las 02:30 **existen dos veces** (primero en CEST, luego en CET). El trigger las encuentra dos veces y dispara dos veces.

No es un bug de APScheduler en sentido estricto: es que elegiste una hora que vive en la zona de transición. Cualquier horario entre las 02:00 y las 03:00 hora de Madrid tiene este problema una vez por semestre.

**Cómo verificarlo sin esperar a marzo.** Pedile al trigger sus próximos disparos alrededor de la fecha:

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.triggers.cron import CronTrigger

madrid = ZoneInfo("Europe/Madrid")
trigger = CronTrigger(hour=2, minute=30, timezone=madrid)

anterior = None
ahora = datetime(2026, 3, 28, 12, 0, tzinfo=madrid)
for _ in range(3):
    siguiente = trigger.get_next_fire_time(anterior, ahora)
    print(siguiente)
    anterior = siguiente
    ahora = siguiente
```

Vas a ver que del 28 salta al 30: ahí está el día perdido. Repetilo con `datetime(2025, 10, 25, 12, 0)` y ves el doble disparo.

**Arreglo mínimo, dos partes:**

1. **Mové la hora fuera de la ventana de cambio.** Las 03:30 de Madrid existen siempre y una sola vez. Si el cliente exige «02:30 en invierno», la alternativa es programar en UTC (`CronTrigger(hour=1, minute=30, timezone="UTC")`): son las 02:30 de Madrid con horario de invierno y las 03:30 con el de verano, sin saltos ni duplicados. Elegí una de las dos y dejala escrita en el contrato.

```python
scheduler.add_job(enviar_resumen, CronTrigger(hour=3, minute=30, timezone="Europe/Madrid"), id="resumen-diario", replace_existing=True)
```

2. **Hacé idempotente el envío**, porque un reintento, un redeploy a esa hora o un cambio de horario futuro pueden volver a dispararlo. Guardá la fecha local del último envío y no mandes dos veces el mismo día:

```python
from datetime import date

def enviar_resumen() -> None:
    hoy = datetime.now(madrid).date()
    if repositorio.ya_enviado(hoy):
        return
    enviar(hoy)
    repositorio.marcar_enviado(hoy)
```

Con esto, el doble disparo de octubre hubiera mandado uno solo aunque no tocaras el horario.

**Test de regresión**, que recorre los dos cambios de horario del año y cuenta exactamente un disparo por día:

```python
from datetime import datetime, timedelta

def disparos_entre(trigger, inicio, fin):
    anterior, ahora, fechas = None, inicio, []
    while True:
        siguiente = trigger.get_next_fire_time(anterior, ahora)
        if siguiente is None or siguiente > fin:
            return fechas
        fechas.append(siguiente.date())
        anterior = ahora = siguiente

def test_un_disparo_por_dia_en_los_cambios_de_horario():
    trigger = CronTrigger(hour=3, minute=30, timezone=madrid)
    for inicio in (datetime(2026, 3, 27, tzinfo=madrid), datetime(2026, 10, 23, tzinfo=madrid)):
        fechas = disparos_entre(trigger, inicio, inicio + timedelta(days=5))
        assert fechas == sorted(set(fechas)), fechas
        assert len(fechas) == 5, fechas
```

Con `hour=2` el test falla en marzo (4 fechas) y en octubre (6 fechas, una repetida). Con `hour=3` pasa en ambos.""",
            },
        ]
    },
    # 10) Encoding: CSV en cp1252 leído como UTF-8.
    {
        "messages": [
            {
                "role": "user",
                "content": """Al leer un CSV que nos manda un proveedor, pandas peta:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 1834: invalid continuation byte
```

Si abro el archivo en Excel se ve bien. El código es `pd.read_csv("clientes.csv")`. ¿Lo arreglo con `encoding_errors="ignore"`?""",
            },
            {
                "role": "assistant",
                "content": """No. `encoding_errors="ignore"` convertiría «José» en «Jos» y «Muñoz» en «Muoz» sin avisar: datos corruptos en silencio, que es peor que un error.

**Qué dice el error.** El byte `0xE9` no es UTF-8 válido en esa posición. En las codificaciones de un solo byte (`cp1252`, `latin-1`) `0xE9` es la `é`. El archivo **no está en UTF-8**; casi seguro lo exportaron desde Excel en Windows, que por defecto guarda CSV en `cp1252`. Excel «lo ve bien» precisamente porque usa esa misma codificación al abrirlo.

**Comprobarlo antes de tocar código:**

```bash
file clientes.csv                       # "ISO-8859 text" o "Non-ISO extended-ASCII text"
xxd -s 1820 -l 32 clientes.csv          # los bytes alrededor de la posición 1834
```

Si en el volcado ves `4a 6f 73 e9` (`Jos` + `0xE9`), es una `é` en codificación de un byte. Para distinguir `cp1252` de `latin-1`: son iguales salvo en el rango `0x80-0x9F`, donde `cp1252` tiene `€` (`0x80`), las comillas tipográficas y el guion largo. Busca ese rango:

```bash
grep -c -P '[\\x80-\\x9f]' clientes.csv
```

Si hay coincidencias, es `cp1252` (con `latin-1` esos bytes serían caracteres de control, que nadie escribe). Si no hay, las dos decodifican idéntico y da igual cuál uses; elige `cp1252` porque es la que produce Excel.

**Arreglo mínimo:**

```python
import pandas as pd

df = pd.read_csv("clientes.csv", encoding="cp1252")
```

Y conviértelo a UTF-8 en el punto de entrada, para que el resto del sistema no herede la ambigüedad:

```python
from pathlib import Path

def normalizar_csv_proveedor(origen: Path, destino: Path) -> None:
    texto = origen.read_bytes().decode("cp1252")
    destino.write_text(texto, encoding="utf-8", newline="")
```

Si el proveedor cambia de herramienta y un día manda UTF-8, `decode("cp1252")` no fallará, pero verás «JosÃ©». Para protegerte, intenta primero UTF-8 estricto y cae a `cp1252` solo si falla; es un orden válido porque un archivo `cp1252` con tildes casi nunca es UTF-8 válido por accidente:

```python
def decodificar(datos: bytes) -> str:
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return datos.decode("cp1252")
```

**Test de regresión:**

```python
def test_decodifica_cp1252_y_utf8():
    assert decodificar("nombre\\nJosé Muñoz\\n".encode("cp1252")) == "nombre\\nJosé Muñoz\\n"
    assert decodificar("nombre\\nJosé Muñoz\\n".encode("utf-8")) == "nombre\\nJosé Muñoz\\n"
    assert decodificar("precio\\n5 €\\n".encode("cp1252")) == "precio\\n5 €\\n"
```

El tercer `assert` es el que distingue `cp1252` de `latin-1`: con `latin-1` el `€` no se podría codificar.""",
            },
        ]
    },
]

ROWS += [
    # 11) BOM: KeyError en la primera columna de un CSV (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": """Estoy empezando con Python y no entiendo este error. Leo un CSV con `csv.DictReader` y al pedir `fila["id"]` me da `KeyError: 'id'`, pero la primera columna SE LLAMA id, lo veo en el editor. Si imprimo `fila.keys()` sale esto:

```
dict_keys(['\\ufeffid', 'nombre', 'email'])
```

¿Qué es ese `\\ufeff`?""",
            },
            {
                "role": "assistant",
                "content": r"""Ese `﻿` es el **BOM** (*byte order mark*): tres bytes invisibles (`EF BB BF`) que algunos programas, sobre todo Excel y el Bloc de notas de Windows, ponen al principio de un archivo UTF-8 para marcar su codificación. Tu editor no lo muestra, pero Python lo lee como un carácter más y lo pega al nombre de la primera columna. Por eso la clave es `'﻿id'` y no `'id'`.

**Cómo comprobarlo:**

```bash
head -c 3 clientes.csv | xxd
# 00000000: efbb bf
```

Si ves `efbb bf`, ahí está.

**Arreglo mínimo:** abre el archivo con la codificación `utf-8-sig`. Es UTF-8 que descarta el BOM si existe y no hace nada si no existe, así que vale para los dos casos:

```python
import csv

with open("clientes.csv", encoding="utf-8-sig", newline="") as archivo:
    for fila in csv.DictReader(archivo):
        print(fila["id"], fila["nombre"])
```

El `newline=""` es la recomendación del propio módulo `csv` para que los saltos de línea dentro de campos entrecomillados no se rompan.

Lo que **no** debes hacer: `fila["﻿id"]` o `nombre.lstrip("﻿")` por todo el código. Funciona hoy y se rompe el día que el proveedor exporte sin BOM.

Si usas pandas, es lo mismo: `pd.read_csv("clientes.csv", encoding="utf-8-sig")`.

**Para que no vuelva a pasar**, un test con un CSV que lleva BOM a propósito:

```python
import csv
import io

def leer_clientes(texto_bytes: bytes) -> list[dict]:
    archivo = io.TextIOWrapper(io.BytesIO(texto_bytes), encoding="utf-8-sig", newline="")
    return list(csv.DictReader(archivo))

def test_lee_la_primera_columna_aunque_haya_bom():
    datos = "﻿id,nombre\n1,Ana\n".encode("utf-8")
    filas = leer_clientes(datos)
    assert filas[0]["id"] == "1"
    assert "﻿id" not in filas[0]
```

Con `encoding="utf-8"` el test falla con el mismo `KeyError` que tienes ahora; con `utf-8-sig` pasa.""",
            },
        ]
    },
    # 12) Coma flotante y NaN: totales que no cuadran en un test.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Un test de facturación falla y no entiendo por qué, los números son los mismos:

```
>       assert calcular_total(lineas) == 1234.56
E       assert 1234.5600000000002 == 1234.56
```

Y en otro informe, al sumar una columna de pandas con `df["importe"].sum()`, el resultado sale `nan` aunque casi todos los valores están. ¿Están relacionados?""",
            },
            {
                "role": "assistant",
                "content": """Están relacionados solo en que los dos son propiedades de los números en coma flotante (IEEE 754); las causas son distintas y los arreglos también.

**1. `1234.5600000000002 != 1234.56`.** Ni `0.1`, ni `12.34`, ni la mayoría de decimales tienen representación exacta en binario; cada suma acumula un error de redondeo del orden de 10⁻¹⁶ relativo. El test compara con igualdad exacta y falla por ese residuo. Hay dos arreglos y cuál elegir depende de qué calcula `calcular_total`:

- **Si es dinero**, el error no está en el test sino en el tipo. Usa `Decimal`, que representa `12.34` exactamente y redondea con la regla que tú digas:

```python
from decimal import Decimal, ROUND_HALF_UP

def calcular_total(lineas: list[dict]) -> Decimal:
    total = sum(Decimal(str(linea["precio"])) * linea["cantidad"] for linea in lineas)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

`Decimal(str(x))` y no `Decimal(x)`: `Decimal(12.34)` arrastra el error binario (`12.339999...`). Lo ideal es que `precio` ya llegue como `Decimal` o como entero en céntimos desde la base de datos (`NUMERIC`, no `FLOAT`).

- **Si es una magnitud física o estadística**, el float es correcto y lo que sobra es la igualdad exacta: `pytest.approx` o `math.isclose`.

```python
import pytest

def test_total():
    assert calcular_total(lineas) == pytest.approx(1234.56)
```

**2. `sum()` que devuelve `nan`.** Un solo `NaN` contamina cualquier operación: `nan + 1 == nan`, y además `nan != nan`, así que `df["importe"] == float("nan")` nunca encuentra nada. Pandas por defecto **salta** los `NaN` en `sum()` (`skipna=True`), así que si te sale `nan` hay dos explicaciones, en orden:

1. **La columna no es numérica.** Si se leyó como `object` (texto con comas decimales, un «N/D» en alguna celda), `sum()` concatena o devuelve basura. Evidencia: `df["importe"].dtype`.
2. Alguien llamó a `sum(skipna=False)` o la columna está **entera** vacía. Evidencia: `df["importe"].isna().sum()` frente a `len(df)`.

Diagnóstico en tres líneas:

```python
print(df["importe"].dtype)
print(df["importe"].isna().sum(), "de", len(df))
print(df.loc[pd.to_numeric(df["importe"], errors="coerce").isna() & df["importe"].notna(), "importe"].unique())
```

La tercera línea lista los valores que **no** se pudieron convertir: ahí verás el «N/D» o el «1.234,56» culpable.

Arreglo mínimo: convierte en la carga, con decisión explícita sobre qué hacer con lo no numérico, y no confíes en que `sum()` «se salte» cosas:

```python
df["importe"] = pd.to_numeric(df["importe"].str.replace(".", "", regex=False).str.replace(",", "."), errors="coerce")
faltantes = df["importe"].isna().sum()
if faltantes:
    raise ValueError(f"{faltantes} importes no numéricos en el informe")
total = df["importe"].sum()
```

**Tests de regresión:**

```python
def test_total_es_exacto_en_centimos():
    lineas = [{"precio": 0.1, "cantidad": 3}, {"precio": 0.2, "cantidad": 1}]
    assert calcular_total(lineas) == Decimal("0.50")

def test_importes_no_numericos_fallan_en_voz_alta():
    df = pd.DataFrame({"importe": ["1.234,56", "N/D"]})
    with pytest.raises(ValueError, match="1 importes no numéricos"):
        cargar_importes(df)
```

El primero falla con float puro (`0.30000000000000004 + 0.2`); el segundo falla con el `sum()` original porque devuelve `1234.56` sin avisar de la fila perdida.""",
            },
        ]
    },
    # 13) CORS: preflight bloqueado; luego credenciales con comodín (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi front en React (Vite, localhost:5173) no puede llamar a mi API en FastAPI (localhost:8000). En la consola del navegador:

```
Access to fetch at 'http://localhost:8000/api/items' from origin 'http://localhost:5173' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

Con curl la API responde bien. ¿Qué le falta?""",
            },
            {
                "role": "assistant",
                "content": """Lo que falta está en el mensaje: la API no envía la cabecera `Access-Control-Allow-Origin`, y el navegador, al ver que `5173` y `8000` son orígenes distintos (basta con que cambie el puerto), bloquea la respuesta. `curl` funciona porque CORS es una política **del navegador**, no del servidor: el servidor responde igual en ambos casos, pero solo el navegador la descarta.

El detalle «Response to preflight request» indica que la petición no es «simple» (probablemente `Content-Type: application/json` o un método distinto de GET/POST), así que el navegador envía antes un `OPTIONS` y espera las cabeceras CORS en esa respuesta.

**Reproducir fuera del navegador**, para ver exactamente qué devuelve la API al *preflight*:

```bash
curl -i -X OPTIONS http://localhost:8000/api/items \\
  -H "Origin: http://localhost:5173" \\
  -H "Access-Control-Request-Method: GET"
```

Si no ves `access-control-allow-origin` en la respuesta, confirmado: la API no tiene CORS configurado.

**Arreglo mínimo** en FastAPI:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

Añádelo antes de registrar las rutas. Repite el `curl` de arriba: ahora debe aparecer `access-control-allow-origin: http://localhost:5173`.

Dos errores habituales que no son este pero dan el mismo síntoma:

- Una excepción en el servidor (500) **antes** de que el middleware añada las cabeceras: el navegador reporta «CORS» cuando en realidad es un error de tu endpoint. Mira el log de uvicorn.
- Un proxy o nginx delante que descarta `OPTIONS`.

En producción, pon los orígenes reales (`https://app.tudominio.com`) y léelos de una variable de entorno; nunca `"*"` si vas a usar cookies o `Authorization`.

**Test de regresión:**

```python
from fastapi.testclient import TestClient

def test_preflight_permite_el_origen_del_front():
    cliente = TestClient(app)
    respuesta = cliente.options(
        "/api/items",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
```""",
            },
            {
                "role": "user",
                "content": "Ya funciona para GET, pero cuando mando la cookie de sesión con `credentials: 'include'` vuelve a fallar. Puse `allow_origins=[\"*\"]` para no complicarme y `allow_credentials=True`.",
            },
            {
                "role": "assistant",
                "content": """Esa combinación está prohibida por la especificación: con credenciales (cookies o `Authorization`), el navegador exige que `Access-Control-Allow-Origin` sea un origen **concreto**, no `*`. Starlette, por seguridad, cuando ve `allow_origins=["*"]` con `allow_credentials=True` no refleja el origen de la petición, así que el navegador rechaza la respuesta. El mensaje en consola lo dice casi literal: `The value of the 'Access-Control-Allow-Origin' header in the response must not be the wildcard '*' when the request's credentials mode is 'include'`.

Arreglo: lista explícita de orígenes y `allow_credentials=True`.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://app.tudominio.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

Con credenciales también importa la cookie en sí: para que el navegador la envíe entre `5173` y `8000` necesita `SameSite=None; Secure`, y `Secure` exige HTTPS salvo en `localhost`, que los navegadores tratan como seguro. Si en producción el front y la API viven en subdominios del mismo sitio, `SameSite=Lax` basta y es más seguro.

Si de verdad necesitas aceptar muchos orígenes variables (subdominios por cliente), usa `allow_origin_regex=r"https://.*\\.tudominio\\.com"` en lugar de `"*"`: Starlette refleja el origen concreto que coincide, que es lo que el navegador acepta.

Amplía el test anterior con el caso de credenciales:

```python
def test_cors_con_credenciales_devuelve_origen_concreto():
    respuesta = TestClient(app).options(
        "/api/items",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert respuesta.headers["access-control-allow-credentials"] == "true"
```

Con `"*"` + credenciales, la primera aserción falla porque Starlette omite la cabecera.""",
            },
        ]
    },
    # 14) Dependencias rotas: ImportError por una transitiva sin fijar.
    {
        "messages": [
            {
                "role": "user",
                "content": """Ayer el despliegue funcionaba y hoy, sin tocar código, el contenedor arranca y muere con:

```
Traceback (most recent call last):
  File "/app/app.py", line 1, in <module>
    from flask import Flask
  File "/usr/local/lib/python3.11/site-packages/flask/__init__.py", line 5, in <module>
    from .app import Flask as Flask
  File "/usr/local/lib/python3.11/site-packages/flask/app.py", line 30, in <module>
    from werkzeug.urls import url_quote
ImportError: cannot import name 'url_quote' from 'werkzeug.urls' (/usr/local/lib/python3.11/site-packages/werkzeug/urls.py)
```

El requirements.txt tiene `flask==2.2.5`. ¿Cómo puede romperse si no cambié nada?""",
            },
            {
                "role": "assistant",
                "content": """Sí cambió algo: **una dependencia transitiva que no tienes fijada**. Flask 2.2 importa `url_quote` de Werkzeug, y Werkzeug 3.0 eliminó esa función. Tu `requirements.txt` fija Flask pero no Werkzeug, así que cada `pip install` coge la última Werkzeug que cumpla `Werkzeug>=2.2.2` (el rango que declara Flask 2.2), y en algún momento esa «última» pasó a ser la 3.x. El día que se publicó, tu *build* dejó de ser reproducible. Que la imagen de ayer funcione y la de hoy no, sin cambios en el repo, es la firma exacta de este problema.

**Confirmarlo** en el contenedor roto:

```bash
docker run --rm --entrypoint pip tu-imagen:hoy show werkzeug | head -2
docker run --rm --entrypoint pip tu-imagen:ayer show werkzeug | head -2
```

Verás `Version: 3.x` en la de hoy y `2.x` en la de ayer.

**Hipótesis descartadas** (por si la versión de Werkzeug fuera la misma): cambio de imagen base (`python:3.11` apunta a una versión nueva cada semana) o caché de capas invalidada que reinstaló todo. Ambas se ven con `docker history` y `pip list` en las dos imágenes; en tu caso la traza ya señala a Werkzeug.

**Arreglo mínimo, hoy:** fija la transitiva.

```
flask==2.2.5
werkzeug==2.3.8
```

**Arreglo de fondo:** fija el árbol completo con un *lockfile*, para que esto no vuelva a pasar con ninguna otra librería. Con `pip-tools`:

```bash
pip install pip-tools
echo "flask==2.2.5" > requirements.in
pip-compile --generate-hashes requirements.in     # produce requirements.txt con el árbol completo y hashes
```

Y en el Dockerfile instala con `pip install --require-hashes -r requirements.txt`. Con `uv` es `uv lock` + `uv sync --frozen`, misma idea. El `requirements.txt` resultante lleva Werkzeug, Jinja2, click, itsdangerous y MarkupSafe con versiones exactas; actualizarlas pasa a ser una decisión (`pip-compile --upgrade`) con su *pull request*, no un accidente a las 3 de la mañana.

De paso: Flask 2.2 lleva sin soporte desde 2023; cuando tengas el *lockfile*, sube a Flask 3.x en una rama aparte, donde `url_quote` ya no se usa.

**Test de regresión** que impide que el contenedor arranque con un árbol incompatible, en CI:

```bash
pip check                     # falla si alguna dependencia instalada viola los rangos declarados
python -c "import flask"      # falla con el ImportError antes de desplegar
```

`pip check` no habría detectado este caso concreto (Flask 2.2 declaraba `Werkzeug>=2.2.2` sin tope, así que 3.0 «cumplía»), por eso el `import` explícito es el test que de verdad protege; añade uno por cada paquete de primer nivel o, mejor, ejecuta la suite de tests dentro de la imagen construida.""",
            },
        ]
    },
    # 15) npm ERESOLVE: conflicto de peer dependencies (usuario en inglés).
    {
        "messages": [
            {
                "role": "user",
                "content": """`npm install` fails on a fresh clone of our project:

```
npm error code ERESOLVE
npm error ERESOLVE unable to resolve dependency tree
npm error
npm error While resolving: dashboard@1.4.0
npm error Found: react@19.0.0
npm error node_modules/react
npm error   react@"^19.0.0" from the root project
npm error
npm error Could not resolve dependency:
npm error peer react@"^17.0.0 || ^18.0.0" from react-beautiful-dnd@13.1.1
npm error node_modules/react-beautiful-dnd
npm error   react-beautiful-dnd@"^13.1.1" from the root project
```

A teammate says to just add `--legacy-peer-deps`. Is that safe?""",
            },
            {
                "role": "assistant",
                "content": """It is not a fix; it is a way to stop npm from telling you about the problem. The message is precise: `react-beautiful-dnd@13.1.1` declares that it works with React 17 or 18, and your project is on React 19. `--legacy-peer-deps` installs it anyway and you find out at runtime whether it actually works, usually as a warning in the console or a broken drag-and-drop in production.

**What to establish first:** does the library work with React 19 at all? `react-beautiful-dnd` is archived (no releases since 2022) and relies on APIs React 19 tightened, so the honest answer is "no guarantee". Three options, in order of preference:

1. **Switch to a maintained fork.** `@hello-pangea/dnd` is the community continuation with the same API; its recent versions declare React 18 and 19 as peers. Migration is usually a change of import path:

```bash
npm uninstall react-beautiful-dnd
npm install @hello-pangea/dnd
```

```diff
- import { DragDropContext, Droppable, Draggable } from "react-beautiful-dnd";
+ import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
```

Check the exact peer range before installing: `npm view @hello-pangea/dnd peerDependencies`.

2. **Override the peer range deliberately**, if you have tested the library on React 19 and you accept the risk. This is the explicit version of what `--legacy-peer-deps` does implicitly, and it lives in `package.json` so the next person sees it:

```json
{
  "overrides": {
    "react-beautiful-dnd": {
      "react": "$react",
      "react-dom": "$react-dom"
    }
  }
}
```

3. **Stay on React 18** until the dependency is replaced. Valid if the React 19 upgrade is not finished anyway.

**Why `--legacy-peer-deps` is worse than option 2:** it is a flag someone has to remember on every machine and in CI, it disables peer resolution for *every* package (so the next conflict goes unnoticed too), and it does not end up in the lockfile as a decision anyone can review. If you ever use it, put it in `.npmrc` (`legacy-peer-deps=true`) so at least it is versioned; but prefer `overrides`.

**Make the regression impossible to miss:** run the install in CI exactly as a fresh clone would, with `npm ci` (which refuses to proceed if `package-lock.json` is inconsistent with `package.json`), and add a smoke test that renders the component:

```tsx
import { render } from "@testing-library/react";
import { Board } from "./Board";

test("the board renders with the drag-and-drop provider", () => {
  const { getByText } = render(<Board columns={[{ id: "todo", title: "To do", cards: [] }]} />);
  expect(getByText("To do")).toBeInTheDocument();
});
```

With the archived library on React 19, this test is where you would see the runtime warnings or errors before users do.""",
            },
        ]
    },
]

ROWS += [
    # 16) Variables de entorno: funciona en local con .env, falla en el contenedor.
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero SRE. Prioriza el diagnóstico por evidencia y da órdenes concretas para ejecutar."},
            {
                "role": "user",
                "content": """Qué pena molestar con esto, pero llevo dos horas. En mi máquina la app arranca perfecto, y en el contenedor en el servidor se cae al instante:

```
Traceback (most recent call last):
  File "/app/main.py", line 7, in <module>
    DATABASE_URL = os.environ["DATABASE_URL"]
KeyError: 'DATABASE_URL'
```

La variable está en el `.env` del repo y en local la carga `python-dotenv`. El Dockerfile copia todo el proyecto con `COPY . .`, así que el `.env` debería estar ahí. ¿Me colaboras?""",
            },
            {
                "role": "assistant",
                "content": """La traza dice una sola cosa: en el momento de ejecutar la línea 7, el proceso **no tiene** `DATABASE_URL` en su entorno. Que el `.env` esté en el disco del contenedor no significa que esté en el entorno del proceso; son dos cosas distintas.

**Evidencia primero.** Dos comandos en el servidor:

```bash
docker run --rm --entrypoint sh tu-imagen -c 'ls -la /app/.env; env | grep -c DATABASE_URL'
docker inspect <contenedor> --format '{{json .Config.Env}}'
```

El primero te dice si el archivo existe dentro de la imagen y si la variable está en el entorno (verás `0`). El segundo, qué variables le pasa el orquestador.

**Hipótesis, de más a menos probable:**

1. **El `.env` no está en la imagen**: lo excluye `.dockerignore` (que casi siempre lleva `.env`, y es lo correcto). El `ls` lo confirma con `No such file`.
2. **El `.env` está, pero nadie lo carga en producción**: `load_dotenv()` se llama solo bajo `if __debug__`/`if DEBUG`, o `main.py` lo ejecuta después de la línea 7, o en el contenedor el directorio de trabajo no es `/app` y `python-dotenv` busca el archivo relativo al *cwd*. El `ls` lo muestra presente y aun así la cuenta es `0`.
3. **El orquestador debía inyectarla y no lo hace**: `docker run` sin `--env-file`, `docker-compose` con `env_file:` apuntando a otra ruta, o un `Secret` de Kubernetes sin montar. El `inspect` lo muestra.

**Arreglo mínimo, y el correcto en producción:** no metas el `.env` en la imagen. Inyecta la variable desde fuera. Elige el que corresponda:

```bash
docker run --env-file /etc/miapp/prod.env tu-imagen
```

```yaml
# docker-compose.yml
services:
  api:
    image: tu-imagen
    env_file: /etc/miapp/prod.env
```

Y en el código, que `dotenv` sea opcional y no sobrescriba lo que venga del entorno real:

```python
import os
from dotenv import load_dotenv

load_dotenv(override=False)   # solo rellena lo que falte; en producción no hay .env y no hace nada

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("falta DATABASE_URL: define la variable de entorno o el archivo .env")
```

El `SystemExit` con mensaje es a propósito: el `KeyError` que tienes ahora es correcto en el fondo, pero quien lea el log a las 3 de la mañana agradece una frase que diga qué configurar. Mantén `.env` en `.gitignore` y en `.dockerignore`; un `.env.example` sin valores es lo que va al repo.

**Comprobación de regresión**, en el *pipeline* de despliegue antes de arrancar la app:

```bash
docker run --rm --env-file /etc/miapp/prod.env tu-imagen python -c "import os; assert os.environ.get('DATABASE_URL'), 'falta DATABASE_URL'"
```

Falla en el *pipeline*, no en producción.""",
            },
        ]
    },
    # 17) Permisos: usuario no root en el contenedor y volumen propiedad de root.
    {
        "messages": [
            {
                "role": "user",
                "content": """Cambié el Dockerfile para no correr como root y ahora la app no arranca:

```
Traceback (most recent call last):
  File "/app/main.py", line 12, in <module>
    handler = logging.FileHandler("/app/logs/app.log")
PermissionError: [Errno 13] Permission denied: '/app/logs/app.log'
```

Dockerfile (resumido):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN useradd -m appuser
USER appuser
CMD ["python", "main.py"]
```

Y arranco con `docker run -v ./logs:/app/logs miapp`. Sin el `USER appuser` funcionaba.""",
            },
            {
                "role": "assistant",
                "content": """El error es literal: `appuser` no puede escribir en `/app/logs`. Antes funcionaba porque root puede escribir en cualquier sitio; al quitar root has destapado un problema de propiedad del directorio, no has creado uno nuevo.

**Dónde está el directorio, en realidad.** `-v ./logs:/app/logs` es un *bind mount*: dentro del contenedor, `/app/logs` es la carpeta `./logs` de la máquina anfitriona, con **sus** permisos y su propietario. Lo que haya en la imagen en esa ruta queda tapado. Así que da igual lo que hagas en el Dockerfile con `/app/logs`: manda el propietario de `./logs` en el host.

**Evidencia:**

```bash
ls -ldn ./logs                                   # en el host: UID y GID numéricos del propietario
docker run --rm --entrypoint id miapp            # uid=1000(appuser) gid=1000(appuser), normalmente
```

Si `./logs` pertenece a `0:0` (root, típico si la creó un `docker run` anterior como root) o a tu usuario con un UID distinto de 1000, ahí está.

**Hipótesis en orden:**

1. `./logs` la creó Docker como root en un arranque anterior. Muy probable: «sin `USER appuser` funcionaba» significa que ese contenedor root la creó.
2. `./logs` es tuya pero tu UID en el host no es 1000, y dentro del contenedor `appuser` es 1000. Los nombres no importan entre host y contenedor; **solo los números**.
3. SELinux (Fedora/RHEL) bloqueando el *bind mount*: el error sería el mismo, pero `ls -Z` y `ausearch -m avc` lo delatan, y se arregla con `:z` en el volumen.

**Arreglo mínimo (hipótesis 1 y 2):** haz que el UID del contenedor coincida con el del propietario de la carpeta, fijando el UID en la imagen en vez de dejar que `useradd` elija:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY --chown=1000:1000 . .
RUN pip install --no-cache-dir -r requirements.txt \\
 && useradd --uid 1000 --no-create-home appuser \\
 && mkdir -p /app/logs && chown 1000:1000 /app/logs
USER appuser
CMD ["python", "main.py"]
```

Y en el host, una sola vez: `sudo chown -R 1000:1000 ./logs` (o arranca con `--user "$(id -u):$(id -g)"` si prefieres que el contenedor use tu UID). El `mkdir` + `chown` dentro de la imagen cubre el caso de arrancar **sin** el volumen montado.

Alternativa más limpia a largo plazo: no escribas logs a archivo dentro del contenedor. Escribe a `stdout` y deja que `docker logs`, journald o el agente de logs del clúster los recojan; desaparece el volumen y con él el problema.

**Test de regresión**, un *script* en CI que construye la imagen y comprueba la escritura con un volumen recién creado:

```bash
set -e
docker build -t miapp:test .
tmp=$(mktemp -d)
docker run --rm -v "$tmp:/app/logs" miapp:test python -c "open('/app/logs/app.log', 'a').write('ok\\n')"
test -s "$tmp/app.log"
```

Con el Dockerfile original, `mktemp -d` crea la carpeta con tu UID del *runner* y el contenedor (UID 1000 elegido por `useradd`) falla si no coinciden; con la versión corregida y `--user` acordado, pasa.""",
            },
        ]
    },
    # 18) Diferencia dev/prod: sistema de archivos sensible a mayúsculas.
    {
        "messages": [
            {
                "role": "user",
                "content": """En mi Mac todo va bien y en el servidor Linux la misma rama falla:

```
Traceback (most recent call last):
  File "/srv/app/main.py", line 3, in <module>
    from app.Services.billing import InvoiceBuilder
ModuleNotFoundError: No module named 'app.Services'
```

He hecho `git pull`, está en el mismo commit. La carpeta `app/services` existe, la veo con `ls`. ¿Por qué Python no la encuentra?""",
            },
            {
                "role": "assistant",
                "content": """Tú mismo has escrito la respuesta: la carpeta se llama `services` y el import dice `Services`. En macOS el sistema de archivos (APFS por defecto) **no distingue mayúsculas**, así que `app/Services` y `app/services` son la misma carpeta y el import funciona. En Linux (ext4, xfs) sí distingue, y `app/Services` no existe. Es una diferencia entre entornos, no un problema de Python ni de git.

**Confirmarlo en el Mac**, para que no quede duda:

```bash
ls -d app/services app/Services        # en macOS, los dos «existen»
grep -rn "app\\.Services" --include=*.py . # cuántos imports llevan la mayúscula
git ls-files app | grep -i services     # cómo se llama en git, que sí distingue
```

`git ls-files` es la referencia: git guarda la ruta exacta, y el servidor Linux ha reproducido esa ruta fielmente.

**Hipótesis adicionales**, menos probables pero del mismo tipo (vale la pena revisarlas de una vez):

- Falta `__init__.py` en `app/services` y en local se resolvía como *namespace package* por un `PYTHONPATH` distinto. Se ve en `git ls-files`.
- Un archivo con mayúscula renombrado solo en el nombre (`Billing.py` → `billing.py`): git en macOS a veces no detecta ese cambio y en el repo queda el nombre antiguo. Se ve comparando `ls` con `git ls-files`.

**Arreglo mínimo:** corrige los imports a la ruta real.

```python
from app.services.billing import InvoiceBuilder
```

Si el renombrado afecta a un archivo y git no lo registra, fuerza el cambio en dos pasos: `git mv Billing.py billing_tmp.py && git mv billing_tmp.py billing.py`.

**Que no vuelva a pasar**, dos medidas:

1. Haz que git en los Macs del equipo distinga mayúsculas a efectos de seguimiento: `git config core.ignorecase false` (en el repo). Con eso, un `git mv` con solo cambio de mayúsculas se registra bien.
2. Un test que importe todos los módulos del paquete, ejecutado en CI sobre Linux. Falla con exactamente el error que has visto, pero antes de desplegar:

```python
import importlib
import pkgutil

import app

def test_todos_los_modulos_importan():
    for modulo in pkgutil.walk_packages(app.__path__, prefix="app."):
        importlib.import_module(modulo.name)
```

Este test también caza imports circulares y módulos que fallan al cargar; es barato y conviene tenerlo en cualquier proyecto que se desarrolle en macOS o Windows y se despliegue en Linux.""",
            },
        ]
    },
    # 19) Caché obsoleta: Redis cache-aside sin invalidación; luego caché HTTP (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Soporte reporta que cuando cambian el precio de un producto en el admin, en la tienda sigue saliendo el precio viejo «un rato», a veces casi una hora. Tenemos Redis delante de la BD con este código (FastAPI, redis-py):

```python
async def obtener_producto(id: int) -> Producto:
    clave = f"producto:{id}"
    if (cacheado := await redis.get(clave)) is not None:
        return Producto.model_validate_json(cacheado)
    producto = await repo.obtener(id)
    await redis.set(clave, producto.model_dump_json(), ex=3600)
    return producto

async def actualizar_precio(id: int, precio: Decimal) -> None:
    await repo.actualizar_precio(id, precio)
```

El TTL es una hora, así que «casi una hora» cuadra, pero no sé si quitar la caché o bajar el TTL.""",
            },
            {
                "role": "assistant",
                "content": """Ni quitarla ni bajar el TTL: la caché hace exactamente lo que le dijiste, y lo que le falta es **invalidación al escribir**. `actualizar_precio` cambia la base de datos y deja la copia de Redis intacta hasta que expire; de ahí el «hasta una hora». Bajar el TTL a 1 minuto solo convierte una hora de dato viejo en un minuto de dato viejo, y multiplica por 60 las lecturas a la base de datos.

**Reproducir en local** (determinista, no hace falta esperar):

```python
producto = await obtener_producto(42)         # llena la caché
await actualizar_precio(42, Decimal("9.99"))
assert (await obtener_producto(42)).precio == Decimal("9.99")   # falla: devuelve el precio anterior
```

**Arreglo mínimo:** borrar la clave después de escribir en la BD (patrón *cache-aside* con invalidación por borrado, no por actualización):

```python
async def actualizar_precio(id: int, precio: Decimal) -> None:
    await repo.actualizar_precio(id, precio)
    await redis.delete(f"producto:{id}")
```

Por qué **borrar** y no **reescribir** la clave con el producto nuevo: si dos actualizaciones concurrentes escriben la caché en orden distinto al de la BD, la caché se queda con la versión perdedora durante una hora. Borrar deja que la siguiente lectura traiga lo que haya en la BD. Y por qué borrar **después** del commit y no antes: si borras antes y la transacción falla, has vaciado la caché para nada (inofensivo) pero, peor, otra petición entre el borrado y el commit vuelve a cachear el valor viejo.

Queda una ventana pequeña: una lectura que falló en caché, leyó la BD **antes** del `UPDATE` y escribe en Redis **después** del `DELETE`. Es poco probable (la lectura tiene que ser lenta y cruzarse con la escritura) y el TTL la acota. Si para vosotros un minuto de precio viejo también es inaceptable, la solución es versionar: guarda `version` en el producto, inclúyela en la clave (`producto:42:v7`) y haz que la lectura obtenga la versión actual de la BD con una consulta barata. Para una tienda, el borrado basta.

**Test de regresión** (con `fakeredis` para no depender de un Redis real):

```python
import pytest
from fakeredis import aioredis as fakeredis

@pytest.mark.asyncio
async def test_actualizar_precio_invalida_la_cache(monkeypatch):
    monkeypatch.setattr("catalogo.redis", fakeredis.FakeRedis())
    await obtener_producto(42)
    await actualizar_precio(42, Decimal("9.99"))
    assert (await obtener_producto(42)).precio == Decimal("9.99")
```""",
            },
            {
                "role": "user",
                "content": "Hecho, y ya actualiza al momento en la API. Pero en la web pública algunos usuarios siguen viendo el precio viejo si no refrescan con Ctrl+F5. ¿Es otra caché?",
            },
            {
                "role": "assistant",
                "content": """Sí, y el síntoma lo identifica: si Ctrl+F5 lo arregla, es la **caché HTTP** (navegador, CDN o ambos), que vive delante de tu API y no sabe nada de Redis.

**Qué comprobar.** Mira las cabeceras de la respuesta de `/api/productos/42` en la pestaña Red del navegador o con:

```bash
curl -sI https://tienda.example/api/productos/42 | grep -i -E "cache-control|age|x-cache|etag|expires"
```

Tres casos:

1. `Cache-Control: max-age=3600` (o `public`) puesto por ti o por un *middleware*: el navegador y la CDN reutilizan la respuesta sin preguntar durante ese tiempo. `Age: 1500` o `X-Cache: HIT` confirman que lo sirve la CDN.
2. Sin `Cache-Control` ni `Expires`: los navegadores aplican **caché heurística** (un porcentaje del tiempo desde `Last-Modified`) y pueden reutilizar la respuesta un rato sin pedirla.
3. `Cache-Control: no-store` y aun así ven precio viejo: entonces no es HTTP, es el estado del front (un *store* o React Query con `staleTime` largo), y lo que necesitas es revalidar al volver a la página.

**Arreglo mínimo para datos que cambian y deben verse al momento:** que el navegador siempre revalide, pero sin descargar si no cambió:

```python
from fastapi import Response

@app.get("/api/productos/{id}")
async def producto(id: int, response: Response) -> Producto:
    producto = await obtener_producto(id)
    response.headers["Cache-Control"] = "no-cache"
    response.headers["ETag"] = f'"{producto.version}"'
    return producto
```

`no-cache` no significa «no cachear»: significa «guarda, pero pregunta antes de usar». Con `ETag`, la pregunta cuesta una petición de 304 sin cuerpo. Si usas CDN, añade `s-maxage=0` o purga la ruta desde `actualizar_precio`; cada CDN tiene su API de purga.

Para el catálogo que cambia poco (descripción, imágenes) puedes mantener `max-age` alto; para el precio y el stock, `no-cache`. Esa distinción, por endpoint, es más útil que una regla global.

**Test:**

```python
def test_el_precio_no_se_cachea_sin_revalidar():
    respuesta = TestClient(app).get("/api/productos/42")
    assert respuesta.headers["cache-control"] == "no-cache"
    assert respuesta.headers["etag"].startswith('"')
```""",
            },
        ]
    },
    # 20) Despliegue: la app escucha en 127.0.0.1 dentro del contenedor.
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi API en Node arranca en Docker, el log dice `Server listening on http://localhost:3000`, `docker ps` muestra `0.0.0.0:3000->3000/tcp`, pero desde el host:

```
$ curl -v http://localhost:3000/health
*   Trying 127.0.0.1:3000...
* Connected to localhost (127.0.0.1) port 3000
> GET /health HTTP/1.1
* Recv failure: Connection reset by peer
curl: (56) Recv failure: Connection reset by peer
```

Dentro del contenedor con `docker exec` el curl sí funciona. No es el firewall, ya lo miré.""",
            },
            {
                "role": "assistant",
                "content": """Las tres pistas juntas apuntan a una causa concreta: la app escucha **solo en la interfaz de loopback del contenedor**. `localhost` dentro del contenedor es *su* `127.0.0.1`, no el del host. Docker publica el puerto (por eso `curl` conecta y luego recibe `reset`: el *proxy* de Docker acepta y, al no encontrar a nadie escuchando en la IP del contenedor, cierra), pero el tráfico que llega por la red del contenedor entra por su IP `172.17.x.x`, donde no hay nadie escuchando. Desde `docker exec` funciona porque ahí sí estás en el loopback del contenedor.

**Evidencia en diez segundos:**

```bash
docker exec <contenedor> sh -c "cat /proc/net/tcp | awk 'NR>1 && \\$4==\\"0A\\" {print \\$2}'"
```

Si sale `0100007F:0BB8` (127.0.0.1:3000 en hexadecimal invertido), está escuchando solo en loopback. Si saliera `00000000:0BB8`, escucharía en todas las interfaces y la causa sería otra. Si la imagen tiene `ss` o `netstat`, `ss -ltn` es más legible.

**Hipótesis alternativas**, por si el socket estuviera en `0.0.0.0`:

- La app escucha en otro puerto (`PORT` de entorno distinto de 3000): verías `00000000:1F90` (8080) o similar.
- El contenedor muere y se reinicia entre petición y petición: `docker ps` mostraría `Restarting` o un *uptime* de segundos.

**Arreglo mínimo:** escucha en `0.0.0.0` dentro del contenedor.

```js
const host = process.env.HOST ?? "0.0.0.0";
const port = Number(process.env.PORT ?? 3000);

app.listen(port, host, () => {
  console.log(`Server listening on http://${host}:${port}`);
});
```

En tu máquina, fuera de Docker, puedes seguir usando `HOST=127.0.0.1` para no exponer el puerto a la red local; dentro del contenedor, `0.0.0.0` es seguro porque la exposición real la controla `-p` (y puedes limitarla con `-p 127.0.0.1:3000:3000` si solo lo quiere ver un *proxy* local).

Mismo bug, otros frameworks: `uvicorn` sin `--host 0.0.0.0`, `flask run` sin `--host`, `vite` sin `--host`, `rails s` sin `-b 0.0.0.0`. Es el error de despliegue en contenedores más frecuente que existe.

**Comprobación de regresión** en CI, que construye la imagen y la prueba **desde fuera**, no con `docker exec`:

```bash
set -e
docker build -t api:test .
id=$(docker run -d -p 3000:3000 api:test)
trap 'docker rm -f "$id" >/dev/null' EXIT
for i in $(seq 1 20); do
  curl -fsS http://localhost:3000/health && exit 0
  sleep 0.5
done
echo "la API no respondió desde el host"; exit 1
```

Con `localhost` en el `listen`, este *script* falla con `(56)` en los 20 intentos; con `0.0.0.0`, pasa en el primero.""",
            },
        ]
    },
]

ROWS += [
    # 21) Kubernetes: CrashLoopBackOff por liveness probe prematura; luego Service sin endpoints (multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Desplegué una API Spring Boot en Kubernetes y el pod entra en CrashLoopBackOff. `kubectl describe pod` muestra:

```
  Warning  Unhealthy  2m (x9 over 4m)   kubelet  Readiness probe failed: Get "http://10.244.1.17:8080/actuator/health": dial tcp 10.244.1.17:8080: connect: connection refused
  Warning  Unhealthy  2m (x3 over 3m)   kubelet  Liveness probe failed: Get "http://10.244.1.17:8080/actuator/health": dial tcp 10.244.1.17:8080: connect: connection refused
  Normal   Killing    2m                kubelet  Container api failed liveness probe, will be restarted
```

Los logs del contenedor terminan siempre en `Starting ApiApplication using Java 21` y nada más. En Docker local arranca sin problema. Probes:

```yaml
livenessProbe:
  httpGet: { path: /actuator/health, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /actuator/health, port: 8080 }
  periodSeconds: 5
```""",
            },
            {
                "role": "assistant",
                "content": """La app no está fallando: **la están matando antes de que termine de arrancar**. Lee los eventos con el reloj en la mano: liveness arranca a los 5 s, prueba cada 10 s y a los 3 fallos (unos 35 s) el kubelet mata el contenedor. El log se corta en `Starting ApiApplication` porque es justo lo que una app Spring Boot muestra durante los primeros 30-60 s en un pod con poca CPU. Luego reinicia, vuelve a no llegar a tiempo, y así: CrashLoopBackOff sin que la app haya lanzado nunca una excepción.

**Evidencia que lo confirma:** quita temporalmente la *liveness probe* (o pon `failureThreshold: 30`) y mide cuánto tarda en aparecer `Started ApiApplication in N seconds`:

```bash
kubectl logs -f deploy/api | grep -m1 "Started ApiApplication"
kubectl top pod -l app=api
```

Si tarda más de 35 s, es esto. `kubectl top` te dirá además si el pod está siendo estrangulado por `limits.cpu` (una JVM con `cpu: 250m` arranca 3-4 veces más lento que en tu portátil).

**Hipótesis alternativas**, menos probables con este log:

- Escucha en otro puerto (`server.port` distinto de 8080): verías `Tomcat started on port 9090` en el log si llegara a arrancar.
- Falla de verdad al arrancar (sin conexión a la BD, por ejemplo): verías una excepción y `Application run failed`, no un corte limpio.

**Arreglo mínimo:** una `startupProbe`, que es para esto exactamente. Mientras no pase, liveness y readiness no se evalúan; cuando pasa, mandan ellas.

```yaml
startupProbe:
  httpGet: { path: /actuator/health/liveness, port: 8080 }
  periodSeconds: 5
  failureThreshold: 36        # hasta 3 minutos para arrancar
livenessProbe:
  httpGet: { path: /actuator/health/liveness, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /actuator/health/readiness, port: 8080 }
  periodSeconds: 5
  failureThreshold: 3
```

Dos cambios más además del tiempo:

1. **Endpoints separados.** Con `management.endpoint.health.probes.enabled=true` (automático en Kubernetes desde Spring Boot 2.3), `/liveness` solo dice «el proceso está vivo» y `/readiness` dice «puedo atender tráfico». Si apuntas liveness al `/health` general, una base de datos caída hace que Kubernetes **reinicie** tu app, que es lo contrario de lo que quieres: reiniciar no arregla la BD y además pierdes el pod que podría servir respuestas de caché o degradadas.
2. **CPU para arrancar.** Si tienes `limits.cpu: 250m`, sube el límite o quítalo y deja solo `requests`; la JVM compila y carga clases en paralelo y con un cuarto de núcleo el arranque se dispara.

**Comprobación de regresión:** un test de despliegue en el *pipeline* que espere a que el rollout termine con un tiempo acotado:

```bash
kubectl rollout status deploy/api --timeout=240s
```

Con las probes originales, el rollout nunca llega a `successfully rolled out` y el comando falla; con la `startupProbe`, termina en un par de minutos.""",
            },
            {
                "role": "user",
                "content": "Ya arranca y el pod está `Running 1/1`, pero el Service no responde: `curl api.default.svc.cluster.local` desde otro pod da `connection refused`. El Service es ClusterIP, puerto 80 → targetPort 8080.",
            },
            {
                "role": "assistant",
                "content": """`connection refused` desde el ClusterIP con el pod `1/1` apunta a que el Service **no tiene endpoints**: kube-proxy no tiene a quién reenviar y rechaza. Compruébalo antes de nada:

```bash
kubectl get endpoints api
```

Si la columna `ENDPOINTS` está vacía (`<none>`), el selector del Service no coincide con las etiquetas del pod. Es la causa más común con diferencia. Compara:

```bash
kubectl get svc api -o jsonpath='{.spec.selector}'
kubectl get pods -l app=api --show-labels
```

Un `app: api` frente a `app.kubernetes.io/name: api`, o un `tier: backend` que está en el Service y no en el pod, basta. Arreglo: que el selector del Service sea un subconjunto de las etiquetas del pod.

Si **sí** hay endpoints y aun así da `refused`, siguientes hipótesis en orden:

- `targetPort` no coincide con el puerto real del contenedor (nombrado `http` en el pod pero numérico en el Service, o 8080 frente a 8081). `kubectl get endpoints api` muestra `IP:puerto`; prueba `curl` directo a esa IP y puerto desde el otro pod.
- Una `NetworkPolicy` que bloquea el tráfico entre namespaces: el síntoma suele ser *timeout*, no *refused*, así que va la última.

**Test de regresión** en el *pipeline*, después del rollout:

```bash
test "$(kubectl get endpoints api -o jsonpath='{.subsets[*].addresses[*].ip}')" != "" || { echo "el Service api no tiene endpoints"; exit 1; }
kubectl run curl-test --rm -i --restart=Never --image=curlimages/curl -- -fsS http://api.default.svc.cluster.local/actuator/health/readiness
```

El primero caza el selector mal escrito; el segundo, el `targetPort` y cualquier otra cosa que impida el tráfico real.""",
            },
        ]
    },
    # 22) OOMKilled: worker que carga una tabla entera en memoria.
    {
        "messages": [
            {
                "role": "user",
                "content": """Tenemos un job en Kubernetes que exporta una tabla a CSV cada noche y desde hace unas semanas se muere. `kubectl describe pod` dice:

```
    State:          Terminated
      Reason:       OOMKilled
      Exit Code:    137
    Limits:
      memory:  1Gi
```

El código es Python con psycopg:

```python
with conn.cursor() as cur:
    cur.execute("SELECT * FROM eventos WHERE fecha >= %s", (desde,))
    filas = cur.fetchall()
with open(ruta, "w", newline="") as f:
    escritor = csv.writer(f)
    escritor.writerow([d.name for d in cur.description])
    escritor.writerows(filas)
```

La tabla crece unas 200 000 filas al día. ¿Le subimos el límite a 4 Gi y ya?""",
            },
            {
                "role": "assistant",
                "content": """Subirlo a 4 Gi compra unas semanas; la tabla sigue creciendo y volverás a estar aquí. El job tiene un consumo de memoria **proporcional al tamaño de la tabla**, y el arreglo es hacerlo constante.

**Qué dice el error.** `Exit Code: 137` = 128 + 9: el kernel mató el proceso con SIGKILL por superar el límite de memoria del *cgroup*. No es una excepción de Python; no hay traza porque el proceso no tuvo oportunidad de escribir nada.

**Dónde está la memoria.** `cur.fetchall()` materializa **todas** las filas como tuplas de objetos Python. Una fila de 10 columnas con fechas y textos ocupa fácilmente 500 bytes-1 KB en memoria (los objetos Python pesan mucho más que los bytes en disco). Con varios millones de filas acumuladas, el gigabyte se va. «Desde hace unas semanas» es el día en que el tamaño cruzó el límite.

**Confirmarlo** sin esperar a la noche: ejecuta el job con la mitad del rango de fechas y mide el pico:

```bash
/usr/bin/time -v python exportar.py 2>&1 | grep "Maximum resident set size"
```

Si el pico crece linealmente con el número de filas, confirmado. También sirve `kubectl top pod` durante la ejecución.

**Arreglo mínimo:** un cursor del lado del servidor y escritura en *streaming*, para que en memoria solo haya un lote a la vez. En psycopg 3, con nombre de cursor:

```python
import csv

LOTE = 5_000

def exportar(conn, ruta: str, desde) -> int:
    total = 0
    with conn.cursor(name="exportacion_eventos") as cur, open(ruta, "w", newline="") as f:
        cur.itersize = LOTE
        cur.execute("SELECT * FROM eventos WHERE fecha >= %s", (desde,))
        escritor = csv.writer(f)
        escritor.writerow([d.name for d in cur.description])
        for fila in cur:
            escritor.writerow(fila)
            total += 1
    return total
```

Un cursor con nombre hace que PostgreSQL mantenga el resultado en el servidor y lo entregue en trozos de `itersize`; la memoria del proceso queda acotada a unos miles de filas, independientemente del tamaño de la tabla. Exige estar dentro de una transacción, que es lo que psycopg hace por defecto.

Si quieres que vaya aún más rápido y con menos CPU, deja que PostgreSQL genere el CSV:

```python
with conn.cursor() as cur, open(ruta, "wb") as f:
    with cur.copy("COPY (SELECT * FROM eventos WHERE fecha >= %s) TO STDOUT WITH (FORMAT csv, HEADER)", (desde,)) as copia:
        for trozo in copia:
            f.write(trozo)
```

`COPY` no pasa por tuplas de Python: suele ser 5-10 veces más rápido y la memoria es la de un *buffer*.

Sobre el límite: déjalo en 1 Gi o incluso bájalo. Un límite ajustado es tu test de regresión en producción: si alguien vuelve a meter un `fetchall()`, el job falla la primera noche y no cuando la tabla pese 20 GB.

**Test de regresión** que mide memoria con `tracemalloc`:

```python
import tracemalloc

def test_exportar_usa_memoria_constante(conn_con_200k_eventos, tmp_path):
    tracemalloc.start()
    exportar(conn_con_200k_eventos, tmp_path / "salida.csv", desde=date(2020, 1, 1))
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert pico < 50 * 1024 * 1024, f"pico de {pico / 2**20:.0f} MiB"
```

Con `fetchall()` sobre 200 000 filas el pico pasa de 100 MiB; con el cursor del servidor se queda en unos pocos.""",
            },
        ]
    },
    # 23) Test intermitente: estado compartido a nivel de módulo y orden de ejecución.
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Sé breve y concreto; nada de generalidades."},
            {
                "role": "user",
                "content": """Tengo un test de pytest que pasa solo pero falla cuando corro toda la suite, y no siempre:

```
FAILED tests/test_pricing.py::test_descuento_por_volumen - assert Decimal('90.00') == Decimal('80.00')
```

El test:

```python
def test_descuento_por_volumen():
    assert precio_final(cantidad=100, base=Decimal("1.00")) == Decimal("80.00")
```

Y `precio_final` lee las reglas de descuento con esto:

```python
_REGLAS: dict[str, Decimal] | None = None

def reglas() -> dict[str, Decimal]:
    global _REGLAS
    if _REGLAS is None:
        _REGLAS = cargar_reglas_desde_config()
    return _REGLAS
```

¿Cómo lo cazo?""",
            },
            {
                "role": "assistant",
                "content": """Ya lo has cazado: `_REGLAS` es **estado global que sobrevive entre tests**. Algún test anterior carga las reglas con otra configuración (un `monkeypatch` de `cargar_reglas_desde_config`, un `settings` de prueba con descuentos distintos) y las deja cacheadas; tu test recibe esas reglas en vez de las suyas. Pasa «solo» porque el caché está vacío; falla «a veces» porque depende de qué tests corren antes, y el orden varía según qué archivos cambiaron, `pytest-randomly` o la selección de la CI.

**Demostrarlo, no suponerlo:**

```bash
pytest -p no:randomly --lf           # ¿falla de forma estable con el último orden?
pytest tests/ -p no:cacheprovider -x --co -q | head   # lista el orden real de ejecución
pytest tests/test_otro.py tests/test_pricing.py       # bisección: ¿qué archivo lo contamina?
```

Y para encontrar al contaminador en una línea, imprime quién llenó el caché:

```python
import traceback
def reglas():
    global _REGLAS
    if _REGLAS is None:
        traceback.print_stack(limit=6)
        _REGLAS = cargar_reglas_desde_config()
    return _REGLAS
```

En la salida con `-s` verás el test que llamó primero y con qué configuración.

**Arreglo mínimo:** un *fixture* `autouse` que vacíe el caché antes de cada test, en `conftest.py`:

```python
import pytest
import pricing

@pytest.fixture(autouse=True)
def reglas_limpias():
    pricing._REGLAS = None
    yield
    pricing._REGLAS = None
```

**Arreglo correcto:** elimina el global. Si el caché es necesario en producción, que sea un objeto con ciclo de vida explícito que los tests puedan construir:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def reglas() -> dict[str, Decimal]:
    return cargar_reglas_desde_config()
```

y en el `conftest`, `reglas.cache_clear()` en el mismo *fixture*. `lru_cache` expone el reinicio como API; el `global` lo escondía.

**Test de regresión** que falla si el caché vuelve a filtrarse entre tests, independientemente del orden:

```python
def test_las_reglas_no_sobreviven_a_un_monkeypatch(monkeypatch):
    monkeypatch.setattr(pricing, "cargar_reglas_desde_config", lambda: {"volumen": Decimal("0.5")})
    assert pricing.precio_final(cantidad=100, base=Decimal("1.00")) == Decimal("50.00")

def test_despues_del_monkeypatch_vuelven_las_reglas_reales():
    assert pricing.precio_final(cantidad=100, base=Decimal("1.00")) == Decimal("80.00")
```

Ejecútalos en ese orden con `-p no:randomly`: sin el *fixture*, el segundo falla con `50.00`; con él, pasan los dos. Luego activa `pytest-randomly` en CI para que cualquier dependencia de orden futura aparezca pronto en vez de dentro de seis meses.""",
            },
        ]
    },
    # 24) Playwright: timeout intermitente (usuario en inglés, pide respuesta en español).
    {
        "messages": [
            {
                "role": "user",
                "content": """Our Playwright E2E suite is flaky in CI, maybe 1 in 8 runs. Always the same test:

```
  1) [chromium] › checkout.spec.ts:18:5 › completes a purchase

    TimeoutError: locator.click: Timeout 30000ms exceeded.
    Call log:
      - waiting for getByRole('button', { name: 'Pay now' })
      -   locator resolved to <button disabled class="btn-primary">Pay now</button>
      - attempting click action
      -   waiting for element to be visible, enabled and stable
      -   element is not enabled
```

The test:

```ts
await page.goto("/checkout");
await page.getByLabel("Card number").fill("4242424242424242");
await page.waitForTimeout(500);
await page.getByRole("button", { name: "Pay now" }).click();
await expect(page.getByText("Order confirmed")).toBeVisible();
```

Locally it never fails. (Puedes responder en español.)""",
            },
            {
                "role": "assistant",
                "content": """El *call log* ya dice qué pasa: el botón existe, Playwright lo encuentra, pero está **`disabled`** y sigue así durante los 30 s. No es un problema de localizar el botón ni de velocidad del clic; es que la condición que lo habilita nunca se cumple en esa ejecución.

**Hipótesis, de más a menos probable:**

1. **El botón se habilita cuando termina una validación o una llamada de red** (validar tarjeta, calcular impuestos). En CI la red es más lenta y el `waitForTimeout(500)` no espera a esa llamada: espera 500 ms fijos, que en local sobran y en CI a veces no. Pero ojo: `click()` ya espera a que el botón esté habilitado, hasta 30 s. Si tras 30 s sigue deshabilitado, la llamada no está tardando: **no termina** o termina con error.
2. **El `fill` llega antes de que el formulario esté hidratado** (React/Next): escribes en el input, la hidratación reemplaza el DOM, el valor se pierde o el estado no se actualiza, y el botón queda deshabilitado para siempre. Encaja con «1 de cada 8» y con «en local nunca»: en local la hidratación acaba antes de que el test escriba.
3. Un error de la app (petición de validación que falla con 500 en el entorno de CI) que deja el botón bloqueado. Se vería en consola.

**Evidencia que las separa**, con la traza de Playwright activada solo en reintentos para no ralentizar la suite:

```ts
// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: { trace: "on-first-retry" },
});
```

Abre `trace.zip` del fallo con `npx playwright show-trace`. En la pestaña de red verás si la validación respondió (hipótesis 1 y 3) y en la línea de tiempo, si el `fill` ocurrió antes de que la página terminara de cargar scripts (hipótesis 2). Para reproducir en local, fuerza el escenario: `npx playwright test checkout --repeat-each 30` con `--project=chromium` y, para simular CI, estrangula la CPU con `launchOptions: { args: ["--js-flags=--max-old-space-size=256"] }` o la red con `page.route` y un `await new Promise(r => setTimeout(r, 2000))` antes de `route.continue()`.

**Arreglo mínimo:** quitar la espera fija y esperar a la **condición** real.

```ts
test("completes a purchase", async ({ page }) => {
  await page.goto("/checkout");
  const cardNumber = page.getByLabel("Card number");
  await expect(cardNumber).toBeEditable();            // formulario hidratado y listo
  await cardNumber.fill("4242424242424242");
  await expect(cardNumber).toHaveValue("4242424242424242");   // el valor sobrevivió a la hidratación

  const payNow = page.getByRole("button", { name: "Pay now" });
  await expect(payNow).toBeEnabled();                 // falla con mensaje claro si la validación no vuelve
  await payNow.click();
  await expect(page.getByText("Order confirmed")).toBeVisible();
});
```

Las aserciones `expect(...).toBe*` reintentan hasta cumplirse (*web-first assertions*) y, si no se cumplen, el mensaje de error dice **qué** condición falló, no un *timeout* genérico del clic. Si la hipótesis 2 es la real, `toHaveValue` será la aserción que falle, y entonces el arreglo está en la app: deshabilitar el formulario hasta hidratar, o que el input sea controlado desde el primer render.

Si resulta ser la hipótesis 3, el test está haciendo su trabajo: hay un bug de la app en CI, y lo que hay que arreglar es el entorno (la URL del servicio de validación en CI) o el manejo de errores del formulario.

**Para que no vuelva:** `--repeat-each 10` sobre este archivo en el *pipeline* nocturno, y una regla de lint (`eslint-plugin-playwright`, regla `no-wait-for-timeout`) para que `waitForTimeout` no vuelva a entrar en la suite.""",
            },
        ]
    },
    # 25) Condición de carrera entre workers: comprobar y actuar sin bloqueo (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Tenemos 4 workers que sacan tareas de una tabla `jobs` en Postgres y a veces dos workers procesan la misma tarea (se mandan dos correos al cliente). El código:

```python
def tomar_job(conn) -> Job | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id, payload FROM jobs WHERE estado = 'pendiente' ORDER BY creado LIMIT 1")
        fila = cur.fetchone()
        if fila is None:
            return None
        cur.execute("UPDATE jobs SET estado = 'procesando', worker = %s WHERE id = %s", (WORKER_ID, fila[0]))
        conn.commit()
        return Job(*fila)
```

Pasa poco, una o dos veces al día, con unos 50 000 jobs diarios. ¿Es un bug de Postgres?""",
            },
            {
                "role": "assistant",
                "content": """No: es una **condición de carrera de comprobar-y-actuar** en tu código. Entre el `SELECT` y el `UPDATE` hay una ventana de unos milisegundos; si dos workers ejecutan el `SELECT` dentro de esa ventana, ambos ven la misma fila `pendiente`, ambos la marcan como `procesando` (el segundo `UPDATE` sobrescribe el primero sin error) y ambos la procesan. Con 50 000 jobs y 4 workers, una o dos colisiones al día es exactamente la frecuencia que cabría esperar.

**Reproducirlo a voluntad.** Agranda la ventana para que la colisión sea segura, no probable: mete un `time.sleep(0.5)` entre el `SELECT` y el `UPDATE` y lanza dos workers con un único job pendiente. Los dos lo procesarán. Ese mismo montaje es tu test de regresión.

**Hipótesis descartadas**, por completar: aislamiento `SERIALIZABLE` lo detectaría y abortaría una de las transacciones, pero usas el `READ COMMITTED` por defecto, que no protege contra esto. Un índice único no aplica: la fila es la misma, no hay dos inserciones.

**Arreglo mínimo:** que la selección y el bloqueo sean **una sola operación atómica**. En Postgres es idiomático y de una línea de SQL:

```python
def tomar_job(conn) -> Job | None:
    with conn.cursor() as cur:
        cur.execute(
            '''
            UPDATE jobs
               SET estado = 'procesando', worker = %s, tomado_en = now()
             WHERE id = (
                   SELECT id FROM jobs
                    WHERE estado = 'pendiente'
                    ORDER BY creado
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
             )
            RETURNING id, payload
            ''',
            (WORKER_ID,),
        )
        fila = cur.fetchone()
        conn.commit()
        return Job(*fila) if fila else None
```

Cómo funciona: `FOR UPDATE` bloquea la fila elegida dentro de la transacción; `SKIP LOCKED` hace que otro worker que llegue a la vez **no espere** por ella sino que coja la siguiente pendiente. El `UPDATE` ocurre en la misma sentencia, así que no hay ventana. Esto es la cola de trabajos canónica en Postgres y escala bien a decenas de workers.

Dos detalles que importan para no cambiar un bug por otro:

- El `ORDER BY creado` necesita un índice `(estado, creado)`, idealmente parcial: `CREATE INDEX jobs_pendientes_idx ON jobs (creado) WHERE estado = 'pendiente'`. Sin él, con millones de jobs históricos, cada toma recorre la tabla.
- Un worker que muera a mitad deja el job en `procesando` para siempre. Añade un *reaper*: `UPDATE jobs SET estado = 'pendiente' WHERE estado = 'procesando' AND tomado_en < now() - interval '10 minutes'`. Y como eso reintroduce la posibilidad de procesar dos veces (si el worker no había muerto, solo iba lento), el envío del correo debe ser **idempotente**: guarda `correo_enviado_en` en el job y no reenvíes si ya está.

**Test de regresión:**

```python
import threading

def test_dos_workers_no_toman_el_mismo_job(conn_factory, job_pendiente):
    tomados: list[int] = []
    barrera = threading.Barrier(2)

    def worker():
        conn = conn_factory()
        barrera.wait()                     # los dos entran a la vez
        job = tomar_job(conn)
        if job is not None:
            tomados.append(job.id)

    hilos = [threading.Thread(target=worker) for _ in range(2)]
    for h in hilos: h.start()
    for h in hilos: h.join()
    assert tomados == [job_pendiente.id]
```

Con el código original y un `sleep` entre las dos sentencias, `tomados` tiene dos elementos; con `SKIP LOCKED`, siempre uno.""",
            },
            {
                "role": "user",
                "content": "¿Y si en vez de eso pongo un lock en Redis con SETNX antes de procesar? Ya tenemos Redis.",
            },
            {
                "role": "assistant",
                "content": """Funcionaría en el caso feliz, pero cambia un problema que Postgres resuelve de forma atómica y transaccional por dos sistemas que hay que mantener coherentes. Lo que pierdes:

- **Atomicidad.** El lock de Redis y el `UPDATE` en Postgres son dos operaciones. Si el worker consigue el lock, marca el job, y muere antes de procesarlo, tienes un job `procesando` y un lock con TTL; si muere después de procesar pero antes de liberar, el siguiente worker espera al TTL. En la versión `SKIP LOCKED`, el bloqueo vive y muere con la transacción.
- **Expiración.** Un `SETNX` necesita un TTL para no quedarse colgado, y un TTL mal elegido permite que dos workers procesen el mismo job si el primero tarda más que el TTL. Es el mismo bug que tienes hoy, con otra cara. Redlock y los *fencing tokens* existen precisamente porque este caso se complica rápido.
- **Un punto de fallo más.** Si Redis no está, los workers no pueden tomar trabajo aunque Postgres esté perfecto.

Cuándo sí tendría sentido Redis: si la cola **viviera** en Redis (Streams con grupos de consumidores, o una librería como RQ/arq/Celery con Redis), porque entonces la atomicidad la da Redis. Mezclar «cola en Postgres, lock en Redis» es lo peor de ambos.

Como ya tienes Redis, el sitio donde sí aporta aquí es el **idempotency key del envío**: `SET correo:{job_id} 1 NX EX 86400` justo antes de llamar a la API de correo. Es una segunda barrera barata contra el reenvío (incluido el caso del *reaper* que comentamos), y si Redis falla, el `correo_enviado_en` en Postgres sigue protegiéndote. Pero la toma del job déjala en `FOR UPDATE SKIP LOCKED`.""",
            },
        ]
    },
]

ROWS += [
    # 26) Node: fuga de memoria por listeners acumulados (usuario en inglés).
    {
        "messages": [
            {
                "role": "user",
                "content": """Our Node 20 service dies after about 6 hours in production:

```
<--- Last few GCs --->
[1:0x5b2c3a0]  21600432 ms: Mark-Compact 2041.2 (2089.9) -> 2039.8 (2090.1) MB, 1832.4 / 0.0 ms  (average mu = 0.102, current mu = 0.041) allocation failure; scavenge might not succeed

FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
```

Earlier in the log, which we had been ignoring:

```
(node:1) MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 close listeners added to [Server]. MaxListeners is 10. Use emitter.setMaxListeners() to increase limit
```

We tried `--max-old-space-size=4096` and it just takes 12 hours instead. Where do we start?""",
            },
            {
                "role": "assistant",
                "content": """Start with the warning you were ignoring: it is Node telling you, six hours in advance, exactly what is leaking. `11 close listeners added to [Server]` means something registers a `close` listener on the HTTP server object **repeatedly**, and the server object lives for the whole process, so every listener (and every closure it captures) stays reachable forever. Doubling the heap doubled the time to death, which is the signature of a linear leak, not of a service that genuinely needs 2 GB.

**Confirm it is the same leak.** Count listeners and heap over time without restarting anything:

```js
setInterval(() => {
  const { heapUsed } = process.memoryUsage();
  console.log(JSON.stringify({ heapMB: Math.round(heapUsed / 1e6), closeListeners: server.listenerCount("close") }));
}, 60_000);
```

If `closeListeners` grows roughly with the number of requests (or connections, or jobs) and `heapMB` follows, you have the culprit. If listeners stay flat but the heap grows, take two heap snapshots an hour apart and compare them in Chrome DevTools (Memory tab, "Comparison" view): send `kill -USR2 <pid>` after starting Node with `--heapsnapshot-signal=SIGUSR2`. The object type with the largest positive delta is the leak.

**Where this usually comes from**, most likely first:

1. A listener registered inside a request handler or middleware: `server.on("close", ...)` or `process.on("SIGTERM", ...)` in code that runs per request. Classic when graceful shutdown logic was copy-pasted into a route or into a factory called per request.
2. A library that attaches listeners per instance and the instance is created per request (a new database client, a new logger transport, a new `AbortController` wired to the server).
3. Listeners on a long-lived `EventEmitter` of your own (a bus, a cache) added by short-lived objects that never call `off`.

Find them with a stack trace at the point of registration, temporarily:

```js
const originalOn = server.on.bind(server);
server.on = (event, listener) => {
  if (event === "close") console.trace("close listener added");
  return originalOn(event, listener);
};
```

The trace shows the file and line that registers it, under load, in one minute.

**Minimal fix:** move the registration to startup so it runs once, or if the listener genuinely belongs to a per-request object, remove it when that object is done:

```js
// bad: runs per request
app.use((req, res, next) => {
  server.on("close", () => req.log.info("server closing"));
  next();
});

// good: once, at startup
server.on("close", () => logger.info("server closing"));
```

```js
// if a per-request listener is really needed, pair it with removal
const onClose = () => controller.abort();
server.on("close", onClose);
res.on("finish", () => server.off("close", onClose));
```

Do **not** call `setMaxListeners(0)`; that silences the only alarm you had.

**Regression test**, cheap enough to run in CI:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../src/app.js";

test("request handling does not accumulate server listeners", async () => {
  const { server, start, stop } = createApp();
  const url = await start();
  const before = server.listenerCount("close");
  await Promise.all(Array.from({ length: 200 }, () => fetch(`${url}/health`)));
  assert.equal(server.listenerCount("close"), before);
  await stop();
});
```

With the leak, the count goes from 1 to 201 and the assertion fails on the first run.""",
            },
        ]
    },
    # 27) Java/Hibernate: LazyInitializationException que solo aparece en producción.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """En producción nos salta esto y en desarrollo nunca:

```
org.hibernate.LazyInitializationException: failed to lazily initialize a collection of role: com.acme.Order.items: could not initialize proxy - no Session
	at org.hibernate.collection.spi.AbstractPersistentCollection.throwLazyInitializationException(AbstractPersistentCollection.java:635)
	at org.hibernate.collection.spi.PersistentBag.iterator(PersistentBag.java:364)
	at com.acme.api.OrderMapper.toDto(OrderMapper.java:31)
	at com.acme.api.OrderController.get(OrderController.java:40)
```

`Order.items` es `@OneToMany(mappedBy = "order")` sin más. El controlador llama a `orderRepository.findById(id)` y luego al mapper. Spring Boot 3.3. ¿Qué cambia entre un entorno y otro?""",
            },
            {
                "role": "assistant",
                "content": """Lo que cambia es casi seguro `spring.jpa.open-in-view`. En desarrollo está en `true` (el valor por defecto; Spring Boot avisa de ello con un WARN al arrancar) y en producción alguien lo ha puesto en `false`, que es la recomendación habitual. Con *open-in-view* la sesión de Hibernate vive durante toda la petición HTTP, así que el mapper puede cargar `items` perezosamente desde el controlador. Sin ella, la sesión se cierra al salir del repositorio, y la primera vez que alguien toca `order.getItems()` fuera de una transacción, Hibernate lanza exactamente esa excepción.

**Comprobar la hipótesis** en treinta segundos:

```bash
grep -rn "open-in-view" src/main/resources/ config/
```

Y para reproducir en local sin tocar producción, añade `spring.jpa.open-in-view=false` a `application-dev.properties` y llama al endpoint. Debe fallar igual.

**Hipótesis secundaria**, si el flag es el mismo en ambos: el método del servicio está anotado con `@Transactional` pero en producción se llama a través de otra ruta (un `@Async`, un *scheduler*, una llamada interna dentro de la misma clase que no pasa por el *proxy*), y por tanto sin transacción.

**El arreglo correcto no es volver a `open-in-view=true`.** Eso esconde el problema y encima mantiene una conexión de base de datos abierta durante todo el tiempo de la petición, incluida la serialización JSON y cualquier llamada externa; bajo carga agota el pool. La causa real es que el código **asume** que la entidad sigue conectada fuera de la capa de persistencia. Arreglo mínimo: cargar lo que el mapper necesita dentro del repositorio, de forma explícita.

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query("select o from Order o left join fetch o.items where o.id = :id")
    Optional<Order> findByIdWithItems(@Param("id") Long id);
}
```

```java
@GetMapping("/orders/{id}")
public OrderDto get(@PathVariable Long id) {
    return orderRepository.findByIdWithItems(id)
            .map(orderMapper::toDto)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
}
```

Alternativa equivalente si prefieres no escribir JPQL: `@EntityGraph(attributePaths = "items")` sobre un método `findWithItemsById`. Y si el DTO solo necesita tres campos, una proyección (`interface OrderSummary { Long getId(); ... }` o un `record` con `select new`) evita cargar la entidad entera.

Un detalle de `join fetch` con colecciones: si `Order` tuviera dos colecciones (`items` y `payments`) y las traes ambas con `fetch`, Hibernate produce un producto cartesiano y puede lanzar `MultipleBagFetchException` si son `List`. Para ese caso, dos consultas o `Set` en vez de `List`.

**Test de regresión**, que reproduce el entorno de producción cerrando la transacción antes de mapear:

```java
@DataJpaTest
@TestPropertySource(properties = "spring.jpa.open-in-view=false")
class OrderRepositoryTest {

    @Autowired OrderRepository repository;
    @Autowired TestEntityManager em;

    @Test
    void findByIdWithItemsCargaLosItemsFueraDeLaSesion() {
        Order order = em.persistFlushFind(orderWithItems(2));
        em.clear();

        Order cargado = repository.findByIdWithItems(order.getId()).orElseThrow();
        TestTransaction.end();   // cierra la transacción del test: a partir de aquí no hay sesión

        assertThat(cargado.getItems()).hasSize(2);
    }
}
```

Con `findById` a secas, `getItems()` tras `TestTransaction.end()` lanza la misma `LazyInitializationException`; con `findByIdWithItems`, pasa. Y pon `spring.jpa.open-in-view=false` también en desarrollo: es la única manera de que estos errores aparezcan en tu máquina y no en la del cliente.""",
            },
        ]
    },
    # 28) Go: deadlock por canal sin receptor; luego "¿y si le pongo buffer?" (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi programa en Go se muere al momento con esto:

```
fatal error: all goroutines are asleep - deadlock!

goroutine 1 [chan send]:
main.main()
	/home/ana/proc/main.go:19 +0x9c
```

main.go:

```go
func main() {
	resultados := make(chan string)
	var wg sync.WaitGroup
	for _, url := range urls {
		wg.Add(1)
		go func(u string) {
			defer wg.Done()
			resultados <- descargar(u)
		}(url)
	}
	wg.Wait()
	close(resultados)
	for r := range resultados {
		fmt.Println(r)
	}
}
```

Hmm, la línea 19 es el `wg.Wait()`. No entiendo por qué, las goroutines terminan rapidísimo.""",
            },
            {
                "role": "assistant",
                "content": """No terminan: **todas están bloqueadas en el envío**. `resultados` es un canal sin búfer, y un envío en un canal sin búfer no completa hasta que alguien recibe. Tu único receptor es el `for r := range resultados`, que está **después** de `wg.Wait()`. Así que cada goroutine se queda parada en `resultados <- descargar(u)` esperando un receptor, `wg.Done()` nunca se ejecuta, `wg.Wait()` nunca vuelve, y el runtime detecta que ninguna goroutine puede avanzar: deadlock. La pista está en la traza: el estado es `[chan send]`, no `[semacquire]`; sí, dice `main.go:19`, pero las otras goroutines, si las listaras con `GOTRACEBACK=all`, estarían todas en `chan send`.

**Verlo con tus ojos:**

```bash
GOTRACEBACK=all go run .
```

Verás N goroutines en `main.main.func1` con estado `chan send`. Eso es la prueba.

**Arreglo mínimo:** que el cierre del canal ocurra en **otra goroutine**, para que `main` pueda ponerse a recibir inmediatamente:

```go
func main() {
	resultados := make(chan string)
	var wg sync.WaitGroup
	for _, url := range urls {
		wg.Add(1)
		go func(u string) {
			defer wg.Done()
			resultados <- descargar(u)
		}(url)
	}
	go func() {
		wg.Wait()
		close(resultados)
	}()
	for r := range resultados {
		fmt.Println(r)
	}
}
```

Secuencia ahora: `main` entra en el `range` y recibe; cada goroutine envía, recibe el relevo y termina; cuando todas han hecho `Done`, la goroutine de cierre cierra el canal y el `range` termina. Es el patrón estándar de «fan-in» en Go.

Si lo que quieres es recoger resultados en orden o con error, `errgroup` (`golang.org/x/sync/errgroup`) con un `slice` indexado por posición suele ser más claro que el canal.

**Test de regresión**, con límite de tiempo para que un deadlock sea un fallo de test y no un cuelgue:

```go
func TestRecolectaTodosLosResultados(t *testing.T) {
	urls := []string{"a", "b", "c"}
	hecho := make(chan []string)
	go func() { hecho <- recolectar(urls, func(u string) string { return "ok:" + u }) }()
	select {
	case got := <-hecho:
		if len(got) != 3 {
			t.Fatalf("esperaba 3 resultados, hay %d", len(got))
		}
	case <-time.After(2 * time.Second):
		t.Fatal("recolectar no terminó: posible deadlock")
	}
}
```

Para eso extrae el cuerpo de `main` a `func recolectar(urls []string, descargar func(string) string) []string`, que además es lo que hace el código testeable.""",
            },
            {
                "role": "user",
                "content": "Lo probé poniendo `make(chan string, 100)` y también funciona. ¿Me quedo con eso? Es más corto.",
            },
            {
                "role": "assistant",
                "content": """Funciona por casualidad, no por diseño. Con un búfer de 100, los envíos completan sin receptor mientras haya hueco; con 100 URLs o menos, todas caben, `wg.Wait()` vuelve y luego lees. Con **101 URLs**, la goroutine 101 se bloquea en el envío, `Done` no llega, y vuelves al mismo deadlock, solo que ahora en producción y no en tu máquina. Un búfer «suficientemente grande» es un número mágico que acopla la corrección del programa al tamaño de la entrada.

Para que no sea teoría:

```go
urls := make([]string, 101)
```

Con el búfer de 100 y ese `slice`, el programa vuelve a morir con `all goroutines are asleep`.

Cuándo sí tiene sentido un búfer: para **desacoplar ritmos** (el productor va a ráfagas y el consumidor a velocidad constante) o para hacer que un envío no bloquee en un caso concreto que conoces, como un canal de señal de tamaño 1. Nunca como sustituto de un receptor que falta. La versión con la goroutine de cierre es correcta para cualquier número de URLs y es dos líneas más; quédate con esa, y si quieres, añade `make(chan string, len(urls))` **además**, que entonces sí está justificado: cabe exactamente todo y nadie bloquea.""",
            },
        ]
    },
    # 29) PostgreSQL: deadlock detectado por orden de bloqueo distinto en dos transacciones.
    {
        "messages": [
            {
                "role": "user",
                "content": """Desde que añadimos la transferencia entre cuentas, Postgres nos devuelve esto unas cuantas veces por hora:

```
ERROR:  deadlock detected
DETAIL:  Process 18234 waits for ShareLock on transaction 991271; blocked by process 18240.
Process 18240 waits for ShareLock on transaction 991270; blocked by process 18234.
HINT:  See server log for query details.
CONTEXT:  while updating tuple (44,7) in relation "cuentas"
```

La transferencia hace, dentro de una transacción:

```sql
UPDATE cuentas SET saldo = saldo - :importe WHERE id = :origen;
UPDATE cuentas SET saldo = saldo + :importe WHERE id = :destino;
```

¿Postgres no debería encargarse de esto?""",
            },
            {
                "role": "assistant",
                "content": """Postgres se encarga: detecta el ciclo y mata una de las dos transacciones, que es lo único que puede hacer. Evitar que el ciclo se forme es responsabilidad del código, y en tu caso el ciclo tiene una forma concreta y conocida.

**Qué dice el DETAIL.** El proceso 18234 espera a que termine la transacción del 18240, y el 18240 espera a la del 18234. Cada uno tiene bloqueada una fila que el otro necesita. Con tu SQL eso ocurre exactamente cuando dos transferencias cruzadas corren a la vez:

| | Transacción A: 1 → 2 | Transacción B: 2 → 1 |
|---|---|---|
| t1 | bloquea cuenta 1 | |
| t2 | | bloquea cuenta 2 |
| t3 | espera cuenta 2 | |
| t4 | | espera cuenta 1: **ciclo** |

«Unas cuantas veces por hora» es la frecuencia con la que dos transferencias entre el mismo par de cuentas, en sentido contrario, se solapan.

**Confirmarlo** con el detalle de las consultas implicadas. En `postgresql.conf` (o por sesión) activa `log_lock_waits = on` y baja `deadlock_timeout` a `200ms` en un entorno de pruebas; el log del servidor mostrará las dos sentencias `UPDATE` y los ids de cuenta de cada proceso. Si son el mismo par de ids en orden invertido, confirmado.

**Reproducir** en dos terminales de `psql`:

```sql
-- terminal 1                                    -- terminal 2
BEGIN;                                           BEGIN;
UPDATE cuentas SET saldo = saldo - 1 WHERE id = 1;
                                                 UPDATE cuentas SET saldo = saldo - 1 WHERE id = 2;
UPDATE cuentas SET saldo = saldo + 1 WHERE id = 2;   -- se queda esperando
                                                 UPDATE cuentas SET saldo = saldo + 1 WHERE id = 1;   -- deadlock detected
```

**Arreglo mínimo: bloquear siempre en el mismo orden.** Si todas las transacciones toman las filas en orden ascendente de `id`, no puede haber ciclo (es la regla general contra *deadlocks*: orden total sobre los recursos). La forma limpia en Postgres es bloquear las dos filas de golpe, ordenadas, antes de tocarlas:

```sql
BEGIN;
SELECT id FROM cuentas WHERE id IN (:origen, :destino) ORDER BY id FOR UPDATE;
UPDATE cuentas SET saldo = saldo - :importe WHERE id = :origen;
UPDATE cuentas SET saldo = saldo + :importe WHERE id = :destino;
COMMIT;
```

El `ORDER BY id FOR UPDATE` adquiere los bloqueos en orden de `id` sea cual sea el sentido de la transferencia. La transacción B del ejemplo ahora espera en el `SELECT` a que A termine, y luego continúa: serialización sin ciclo.

Y aunque el orden lo elimine aquí, en un sistema real conviene **reintentar** ante `40P01` (el SQLSTATE de *deadlock detected*), porque otras rutas futuras pueden introducir uno:

```python
import psycopg
from psycopg.errors import DeadlockDetected

def transferir(conn, origen: int, destino: int, importe: Decimal, intentos: int = 3) -> None:
    for intento in range(intentos):
        try:
            with conn.transaction():
                conn.execute("SELECT id FROM cuentas WHERE id IN (%s, %s) ORDER BY id FOR UPDATE", (origen, destino))
                conn.execute("UPDATE cuentas SET saldo = saldo - %s WHERE id = %s", (importe, origen))
                conn.execute("UPDATE cuentas SET saldo = saldo + %s WHERE id = %s", (importe, destino))
            return
        except DeadlockDetected:
            if intento == intentos - 1:
                raise
```

Reintentar es seguro porque la transacción abortada no dejó nada escrito.

**Test de regresión**, que lanza las dos transferencias cruzadas en paralelo muchas veces:

```python
from concurrent.futures import ThreadPoolExecutor

def test_transferencias_cruzadas_no_producen_deadlock(conn_factory):
    def ida(_): transferir(conn_factory(), 1, 2, Decimal("1"), intentos=1)
    def vuelta(_): transferir(conn_factory(), 2, 1, Decimal("1"), intentos=1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(ida, range(200)))
        list(pool.map(vuelta, range(200)))
        list(pool.map(lambda i: (ida(i), vuelta(i)), range(200)))
    assert saldo_total(conn_factory()) == saldo_inicial
```

Con `intentos=1` el test no se apoya en los reintentos: si el orden de bloqueo está mal, alguna ejecución lanza `DeadlockDetected`. Con el `SELECT ... ORDER BY id FOR UPDATE`, pasa siempre, y la aserción final comprueba que ninguna transacción dejó dinero a medias.""",
            },
        ]
    },
    # 30) React principiante: "Maximum update depth exceeded" por setState en cada render.
    {
        "messages": [
            {"role": "system", "content": "Explica para alguien que está empezando, sin jerga innecesaria, y muestra cómo comprobar cada paso."},
            {
                "role": "user",
                "content": """Estoy aprendiendo React y mi página se congela y luego sale esto en la consola:

```
Uncaught Error: Maximum update depth exceeded. This can happen when a component repeatedly calls setState inside componentWillUpdate or componentDidUpdate. React limits the number of nested updates to prevent infinite loops.
    at getRootForUpdatedFiber (react-dom-client.development.js:5893:11)
    at Lista (Lista.jsx:9:3)
```

Mi componente:

```jsx
function Lista({ productos }) {
  const [filtrados, setFiltrados] = useState([]);

  useEffect(() => {
    setFiltrados(productos.filter((p) => p.stock > 0));
  });

  return <ul>{filtrados.map((p) => <li key={p.id}>{p.nombre}</li>)}</ul>;
}
```

No uso componentWillUpdate ni nada de eso, ¿qué es lo que se repite?""",
            },
            {
                "role": "assistant",
                "content": """Lo que se repite es tu `useEffect`. El mensaje habla de `componentDidUpdate` porque es antiguo, pero el mecanismo es el mismo: **un efecto que cambia el estado y se vuelve a ejecutar por ese cambio de estado**, sin fin.

**Paso a paso de lo que hace React con tu código:**

1. Renderiza `Lista`.
2. Ejecuta el efecto. Como no le pasaste segundo argumento (`useEffect(fn)` sin `[]`), el efecto corre **después de cada render**.
3. El efecto llama a `setFiltrados(nuevoArray)`. `filter` devuelve siempre un array nuevo, y para React un array nuevo es un estado distinto aunque tenga los mismos elementos.
4. El estado cambió, así que React vuelve a renderizar. Vuelve al paso 2.

Después de unas decenas de vueltas, React corta con ese error. La pestaña se congela mientras tanto.

**Cómo comprobarlo tú mismo:** pon `console.log("efecto")` dentro del `useEffect`. Verás cientos de líneas en un instante. Ahora añade `[productos]` como segundo argumento y recarga: verás una sola línea (o una por cambio real de `productos`).

**Arreglo mínimo (y el correcto):** aquí no hace falta ni estado ni efecto. `filtrados` se **calcula** a partir de `productos`; no es algo que el usuario cambie ni que venga de fuera. Calcúlalo en el render:

```jsx
function Lista({ productos }) {
  const filtrados = productos.filter((p) => p.stock > 0);

  return (
    <ul>
      {filtrados.map((p) => (
        <li key={p.id}>{p.nombre}</li>
      ))}
    </ul>
  );
}
```

Regla que te va a ahorrar muchos errores de este tipo: **si puedes calcular algo a partir de las props o del estado que ya tienes, no lo guardes en estado**. El estado es para cosas que cambian por acciones (un texto que escribe el usuario, si un panel está abierto) y el efecto es para sincronizarte con algo externo a React (una petición al servidor, un `setInterval`, el título de la pestaña).

Si la lista fuera enorme y el filtro costoso, `useMemo(() => productos.filter(...), [productos])` evita recalcularlo en renders que no cambian `productos`. Con decenas o cientos de elementos no lo necesitas.

**Para que no vuelva a pasar:** activa la regla `react-hooks/exhaustive-deps` de ESLint (viene con `eslint-plugin-react-hooks`). Te avisa cuando un `useEffect` usa algo que no está en sus dependencias, que es la antesala de este bucle. Y un test sencillo que renderiza el componente y comprueba el resultado; con el bucle, el test falla con el mismo error en lugar de pasar:

```jsx
import { render, screen } from "@testing-library/react";
import { Lista } from "./Lista";

test("muestra solo los productos con stock", () => {
  render(<Lista productos={[{ id: 1, nombre: "Taza", stock: 2 }, { id: 2, nombre: "Plato", stock: 0 }]} />);
  expect(screen.getByText("Taza")).toBeInTheDocument();
  expect(screen.queryByText("Plato")).toBeNull();
});
```""",
            },
        ]
    },
]
