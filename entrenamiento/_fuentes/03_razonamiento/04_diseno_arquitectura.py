"""Diseño de sistemas y de código con trade-offs explícitos: una recomendación clara con su
porqué, aplicada al caso concreto del usuario. Formato chatml, 30 filas.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

ROWS += [
    # 1) Consistencia frente a disponibilidad en un caso concreto (inventario multi-región).
    {
        "messages": [
            {
                "role": "user",
                "content": """Vendemos entradas para eventos y vamos a desplegar en dos regiones (Europa y Latinoamérica) para bajar la latencia. El equipo discute si la base de datos del stock de entradas debe ser multi-maestro (cada región escribe en la suya y se replican) o un único maestro. ¿Qué nos recomiendas? Nos preocupa vender dos veces la misma butaca.""",
            },
            {
                "role": "assistant",
                "content": """Un único maestro para el stock, con lecturas y todo lo demás distribuido. Vender dos veces la misma butaca es un error **irreversible frente al cliente**, y eso decide la cuestión: donde una operación no se puede deshacer, necesitas consistencia fuerte, y la consistencia fuerte entre regiones separadas por 150-200 ms de ida y vuelta se paga con latencia o con un único punto de escritura. Entre las dos, el único punto de escritura es más barato y más fácil de razonar.

**Por qué no multi-maestro para esta tabla.** Con dos maestros, la reserva de la butaca 12F en Madrid y en Bogotá en el mismo segundo tiene éxito en ambos sitios; la replicación descubre el conflicto después. Las estrategias de resolución (último escritor gana, versiones vectoriales, CRDT) sirven para datos que admiten fusión: un carrito, un contador de «me gusta», un perfil. Una butaca no se fusiona: alguien se queda sin entrada y lo descubres cuando ya has cobrado. Los sistemas que venden entradas globalmente (y los bancos con el saldo) hacen justo esto: un dueño por recurso.

**Diseño concreto:**

1. **Escrituras de stock en una región** (la que concentre más ventas, o donde esté el equipo de guardia). Todas las reservas van a ese maestro. Una reserva son un `SELECT ... FOR UPDATE` y un `UPDATE` sobre la fila de la butaca, o una restricción única `(evento_id, butaca)` en la tabla de reservas, que es aún más simple y a prueba de bugs de aplicación.
2. **La otra región paga 150-200 ms en la reserva** y nada más. Es un clic por compra; nadie lo nota en una operación que ya incluye pasarela de pago. Lo que sí notarían es que el catálogo, el mapa de butacas, las búsquedas y las imágenes vengan de la otra región: eso se sirve desde réplicas locales de solo lectura y CDN.
3. **Mapa de butacas desde réplica, reserva contra el maestro.** El mapa puede ir unos cientos de milisegundos atrasado; es una vista. La verdad se decide al reservar, y si la butaca ya voló, el cliente recibe «acaba de venderse» y el mapa se refresca. Ese mensaje es aceptable; una entrada duplicada no.
4. **Reserva con caducidad** (10 minutos, por ejemplo) antes del pago, para no bloquear butacas de carritos abandonados: `estado = 'reservada', expira_en = now() + interval '10 min'` y un proceso que libera las caducadas.

**Qué pasa si cae la región maestra.** Pierdes la capacidad de vender durante el *failover* (minutos con un *failover* automatizado a una réplica en la otra región). Es la disponibilidad que sacrificas, y para un sistema de entradas es el trade-off correcto: unos minutos sin vender durante un incidente raro contra entradas duplicadas en la operación normal. Practica el *failover* en un simulacro trimestral; un *failover* que nunca se ha ejercitado no existe.

**Cuándo cambiaría la recomendación.** Si cada evento se vendiera **solo** en una región (eventos en Madrid solo desde Europa), podrías particionar: cada región es maestra de sus propios eventos, sin conflictos posibles porque no hay escrituras cruzadas. Es multi-maestro por partición, no por réplica, y mantiene la garantía. Pregúntate si vuestro catálogo cumple esa condición antes de descartarlo; si un 5 % de los eventos se venden desde ambos continentes, ese 5 % decide y vuelves al único maestro.

Resumen: maestro único para el stock, réplicas y CDN para todo lo demás, restricción única en base de datos como red de seguridad final, y un simulacro de *failover* en el calendario.""",
            },
        ]
    },
    # 2) Monolito modular frente a microservicios para un equipo pequeño.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Somos 6 desarrolladores en una startup de logística (B2B, unos 200 clientes). Vamos a reescribir el backend porque el actual es un Django de 2019 sin tests. El CTO quiere ir directo a microservicios con Kubernetes «para no tener que migrar después». ¿Es buena idea?""",
            },
            {
                "role": "assistant",
                "content": """No. Con 6 personas, un **monolito modular** con fronteras explícitas entre módulos. Tendréis la mayor parte de los beneficios que el CTO busca y ninguno de los costes que os hundirían.

**El argumento «para no migrar después» está al revés.** Lo caro de los microservicios no es la migración: es operarlos. Cada servicio es un despliegue, un *pipeline*, un esquema de base de datos, un contrato de API que versionar, un punto de fallo de red, un conjunto de métricas y alertas, y una decisión de qué hacer cuando el servicio de al lado no responde. Seis personas que además tienen que entregar producto no pueden pagar eso por 8 o 10 servicios; terminaréis con un «monolito distribuido»: los mismos acoplamientos de siempre, pero con latencia y fallos de red en medio. Mientras que extraer un servicio de un monolito **bien modularizado** cuesta semanas, no meses, porque las fronteras ya existen.

**Qué quiere decir «modular» en concreto**, que es donde fallan la mayoría de monolitos (el vuestro de 2019, probablemente):

```
backend/
  pedidos/        # cada módulo: su API pública, sus modelos, su lógica
    api.py        # lo único que otros módulos pueden importar
    modelos.py
    servicios.py
    tests/
  flotas/
  facturacion/
  clientes/
  compartido/     # tipos y utilidades sin lógica de negocio
```

Tres reglas, que se hacen cumplir con herramientas y no con buena voluntad:

1. **Un módulo solo importa el `api.py` de otro módulo.** `import-linter` (Python) o reglas de ESLint/ArchUnit en otros lenguajes lo comprueban en CI. Es la regla que convierte «carpetas» en «módulos».
2. **Cada módulo es dueño de sus tablas.** `facturacion` no hace un `JOIN` con `pedidos`; le pide los pedidos a su API. Cuesta algo de rendimiento al principio y es lo que hace posible la extracción futura.
3. **Comunicación entre módulos por llamadas de función síncronas o por eventos en proceso** (una lista de *handlers* en memoria basta). Cuando un módulo se extraiga, el evento se publica en una cola y los *handlers* no cambian.

**Lo que sí conviene tomar prestado de los microservicios desde el día uno**, porque es barato:

- Un *pipeline* de CI con tests, *linting* y despliegue automático. Esto, no Kubernetes, es lo que os falta hoy.
- Observabilidad básica: logs estructurados con un id de petición, métricas de latencia por endpoint, trazas si el proveedor lo pone fácil.
- Despliegue en contenedor, en un servicio gestionado (Cloud Run, ECS, Fly, Railway, un *autoscaler* de VMs). Kubernetes para un solo contenedor es pagar una plataforma entera por una característica.

**Cuándo extraer el primer servicio** (y la señal de que llegó el momento): cuando un módulo tenga un perfil de escalado claramente distinto (el cálculo de rutas consume CPU a ráfagas y el resto no), o cuando un equipo lo toque a diario y sus despliegues bloqueen a los demás. Con 6 personas eso no va a pasar en 18 meses; con 25 quizá sí, y para entonces las fronteras del monolito modular os dirán exactamente por dónde cortar.

Una cosa que sí le daría al CTO: elegir el *framework* nuevo con los límites de módulo en mente desde el inicio (Django con *apps* y `import-linter`, FastAPI con *routers* por módulo, NestJS con sus `Module`), y escribir la decisión en un ADR corto para que, cuando toque extraer, se sepa qué se protegió y por qué.""",
            },
        ]
    },
    # 3) Síncrono frente a cola: envío de correo en el registro, con outbox.
    {
        "messages": [
            {
                "role": "user",
                "content": """En el registro de usuarios de mi API mando el correo de bienvenida dentro del mismo endpoint, después de guardar el usuario. Un compañero dice que lo meta en una cola (tenemos RabbitMQ). Yo lo veo como complicar algo que funciona. ¿Cuándo compensa?""",
            },
            {
                "role": "assistant",
                "content": """Compensa aquí, y el motivo no es el rendimiento sino la **corrección frente a fallos**. Piensa en los dos órdenes posibles dentro de un endpoint síncrono:

- **Guardar y luego enviar.** El proveedor de correo tarda 8 s o devuelve 503: el usuario ya está guardado, pero el endpoint responde error o *timeout*. El cliente reintenta, y el segundo intento falla con «el email ya existe». Usuario creado sin correo de bienvenida, y una experiencia confusa.
- **Enviar y luego guardar.** El correo sale, el `INSERT` falla por una restricción: le has dado la bienvenida a alguien que no existe.

El problema no es que sea lento: es que **dos sistemas sin transacción común** no pueden fallar juntos. Una cola separa las dos operaciones, con una regla clara: lo que define el éxito del registro es la base de datos; el correo es una consecuencia que puede retrasarse y reintentarse.

**Pero una cola a secas no cierra el hueco.** Si publicas en RabbitMQ después del `COMMIT` y el proceso muere entre ambos, pierdes el correo; si publicas antes y el `COMMIT` falla, mandas un correo fantasma. La solución estándar es el **outbox transaccional**: escribes el mensaje pendiente en la misma transacción que el usuario, y un proceso aparte lo publica.

```python
def registrar_usuario(session: Session, datos: RegistroDTO) -> Usuario:
    usuario = Usuario(email=datos.email, nombre=datos.nombre)
    session.add(usuario)
    session.flush()                      # obtiene usuario.id
    session.add(Outbox(
        tipo="usuario.registrado",
        payload={"usuario_id": usuario.id, "email": usuario.email},
    ))
    session.commit()                     # usuario y mensaje, o ninguno
    return usuario
```

```python
def publicar_pendientes(session: Session, canal) -> None:
    pendientes = session.scalars(
        select(Outbox).where(Outbox.publicado_en.is_(None)).order_by(Outbox.id).limit(100).with_for_update(skip_locked=True)
    ).all()
    for mensaje in pendientes:
        canal.basic_publish(exchange="eventos", routing_key=mensaje.tipo, body=json.dumps(mensaje.payload))
        mensaje.publicado_en = datetime.now(timezone.utc)
    session.commit()
```

El consumidor que manda el correo debe ser **idempotente** (guarda `correo_bienvenida_enviado_en` y no reenvía), porque el *relay* puede publicar dos veces si muere entre `basic_publish` y `commit`. Entrega «al menos una vez» más consumidor idempotente es la combinación que funciona; «exactamente una vez» no existe entre sistemas distintos.

**Qué ganas, en concreto:**

- El registro responde en 20 ms y nunca falla por culpa del proveedor de correo.
- Un proveedor caído durante una hora produce una hora de correos retrasados, no una hora de registros fallidos.
- Reintentos con *backoff* y una cola de mensajes muertos para los que fallan de verdad, sin tocar el endpoint.
- El mismo evento `usuario.registrado` sirve mañana para el CRM o la analítica sin cambiar el registro.

**Qué pagas:** una tabla más, un proceso más (el *relay*, que puede ser un *cron* cada 5 s o un *worker* dedicado), y que el correo llega «en unos segundos» en vez de «antes de la respuesta». Para un correo de bienvenida es irrelevante.

**Cuándo tendría razón tu intuición.** Si la acción secundaria tuviera que ser parte del resultado (el usuario necesita el código del correo para continuar y no hay otra vía), o si no tuvierais ya una cola operada. Como ya tenéis RabbitMQ, el coste marginal es la tabla de *outbox* y el *relay*, y a cambio eliminas una clase entera de incidentes.

**Verificación:** un test que simule la caída del proveedor (el consumidor lanza excepción) y compruebe que el registro devuelve 201, que el mensaje sigue en la cola y que, al recuperarse el proveedor, se manda **un** correo. Ese test es imposible de escribir para la versión síncrona, lo cual también dice algo.""",
            },
        ]
    },
    # 4) Versionado de una API REST pública (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Vamos a abrir nuestra API REST a terceros y necesitamos decidir cómo versionarla. ¿Versión en la URL (`/v1/`), en una cabecera, o en el `Accept`? Cada artículo dice una cosa.",
            },
            {
                "role": "assistant",
                "content": """Versión en la URL (`/v1/`), y versiona **poco**: casi todos los cambios deben ser compatibles y no necesitar versión nueva.

**Por qué la URL.** Para una API pública, el criterio que manda es qué les cuesta a terceros usarla bien, y la URL gana en todo lo práctico:

- Se ve en un enlace, en un log, en un *curl* pegado en un ticket. Con cabeceras, el 80 % de los reportes de soporte empezarán por «¿qué versión estás usando?».
- Funciona en el navegador, en *webhooks*, en documentación con ejemplos copiables, en *caches* y CDN (la URL es la clave de caché; una cabecera exige `Vary`).
- Los *gateways* enrutan por *path* sin configuración especial, lo que permite servir `/v1/` y `/v2/` desde despliegues distintos durante una transición.

La versión en `Accept` (`application/vnd.acme.v2+json`) es la «correcta» según REST estricto porque la URL identifica el recurso y no su representación. Es un argumento real, pero sus ventajas son teóricas y sus costes caen sobre el cliente. Stripe, GitHub y la mayoría de APIs grandes usan URL o una cabecera de fecha; ninguna de las que recomendaría usa `Accept` como mecanismo principal.

**La decisión importante no es dónde va el número, sino qué es un cambio incompatible.** Define por escrito qué puedes hacer sin subir versión:

- Añadir campos a respuestas, endpoints nuevos, parámetros opcionales nuevos, valores nuevos en enumeraciones **documentadas como abiertas**.

Y qué no:

- Quitar o renombrar campos, cambiar tipos o formatos, cambiar semántica (un `total` que pasa de incluir impuestos a no incluirlos), hacer obligatorio lo opcional, cambiar códigos de estado.

Con esa disciplina, muchas APIs públicas siguen en `/v1/` diez años después. Cada versión mayor es un cliente que no migra y dos bases de código que mantener; conviene que sean uno o dos en la vida del producto, no uno al año.

**Reglas operativas que acompañan a la URL:**

1. Los clientes deben **ignorar campos desconocidos**. Dilo en la documentación y en el SDK, porque es lo que te permite añadir sin romper.
2. Cabecera `Deprecation` y `Sunset` (RFC 9745 y RFC 8594) en las respuestas de la versión antigua, con fecha, y un *changelog* público.
3. Mide el uso por versión y por cliente (`api_key`, versión) desde el primer día. Sin ese dato no puedes retirar nada.
4. Tiempo mínimo de solapamiento documentado (12 meses es habitual en B2B).

**Cuándo elegiría otra cosa:** API interna entre servicios propios: cabecera o nada, porque controlas ambos lados y desplegáis juntos. API con muchísimos cambios pequeños y clientes sofisticados: versionado por fecha en cabecera (`Stripe-Version: 2024-06-20`), que permite congelar el comportamiento por cliente; es más potente y bastante más complejo de implementar correctamente.""",
            },
            {
                "role": "user",
                "content": "Vale, URL. Pero tenemos un cambio ya decidido: el campo `price` pasa de ser un número en euros a un objeto `{amount, currency}` porque vamos a vender en varios países. ¿Eso es v2 ya?",
            },
            {
                "role": "assistant",
                "content": """Cambiar el tipo de `price` es incompatible, sí, pero **no hace falta v2**: añade un campo nuevo y deja el viejo. Es el caso clásico donde «expandir, no sustituir» evita una versión.

```json
{
  "id": "prod_8f3",
  "price": 19.99,
  "price_detail": { "amount": 1999, "currency": "EUR" }
}
```

Reglas para que funcione:

- `price` sigue existiendo con el valor en euros mientras el producto tenga precio en euros. Para productos **sin** precio en euros, `price` es `null` y lo documentas: «`price` se mantiene por compatibilidad; usa `price_detail`». Los clientes antiguos que vendan solo en euros no se enteran; los que quieran otros países tienen que leer `price_detail`, lo cual es razonable porque esa funcionalidad es nueva.
- `amount` en **unidades menores** (céntimos) y entero, no decimal, para no arrastrar errores de coma flotante en todos los SDK. Es el formato de Stripe y de casi todas las APIs de pago por esa razón.
- Marca `price` como obsoleto en la documentación y en el esquema OpenAPI (`deprecated: true`), y empieza a contar cuántos clientes lo leen. No puedes saber quién lee un campo de la respuesta, así que la medida indirecta es cuántos clientes **no** han llamado nunca a un endpoint que exija `price_detail`, o una encuesta al retirar.

Cuándo sí sería v2: si el cambio fuera en la **entrada** (`POST /products` exige ahora `price_detail`) y no pudieras aceptar ambas formas, o si se acumulan cinco o seis cambios así y la respuesta se ha llenado de campos duplicados. Entonces agrupa los cambios y publica v2 con todos a la vez, con la ruta vieja activa 12 meses. Hoy, con un solo campo, el coste de v2 es mayor que el de un campo extra.""",
            },
        ]
    },
    # 5) Idempotencia en un endpoint de pago.
    {
        "messages": [
            {
                "role": "user",
                "content": """Nuestro endpoint `POST /payments` a veces cobra dos veces cuando el cliente móvil reintenta por un timeout. Pensé en rechazar duplicados mirando si hay un pago del mismo importe en los últimos 30 segundos, ¿vale?""",
            },
            {
                "role": "assistant",
                "content": """No vale: «mismo importe en 30 segundos» es una heurística que falla en los dos sentidos. Rechaza pagos legítimos (dos cafés de 2,50 € seguidos en el mismo local) y deja pasar duplicados (el reintento llega a los 31 segundos, o el primer intento sigue en vuelo cuando se evalúa el segundo). El mecanismo correcto es una **clave de idempotencia** que el cliente genera y envía con cada operación.

**Cómo funciona:**

1. El cliente móvil genera un UUID **antes** del primer intento y lo manda en todos los reintentos de esa misma operación: `Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7`. Si el usuario pulsa «pagar» de nuevo en una pantalla nueva, es otra operación y otra clave.
2. El servidor guarda la clave con el resultado de la primera ejecución. Un reintento con la misma clave devuelve **la misma respuesta** sin volver a ejecutar nada.
3. La clave caduca (24 h es habitual) para que la tabla no crezca sin límite.

**La parte que casi todo el mundo hace mal es la concurrencia.** Dos peticiones con la misma clave pueden llegar a la vez (el cliente reintenta mientras la primera sigue procesando). Si compruebas «¿existe la clave?» y luego la insertas, ambas pasan. La reserva de la clave tiene que ser atómica: una inserción con restricción única **antes** de procesar.

```sql
CREATE TABLE idempotency_keys (
    key          text PRIMARY KEY,
    account_id   bigint NOT NULL,
    request_hash text NOT NULL,
    status_code  int,
    response     jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);
```

```python
def pay(key: str, account_id: int, body: dict) -> tuple[int, dict]:
    request_hash = sha256(canonical_json(body)).hexdigest()
    with db.transaction():
        inserted = db.execute(
            "INSERT INTO idempotency_keys (key, account_id, request_hash) VALUES (%s, %s, %s) ON CONFLICT (key) DO NOTHING RETURNING key",
            (key, account_id, request_hash),
        ).fetchone()
    if inserted is None:
        existing = db.execute("SELECT account_id, request_hash, status_code, response FROM idempotency_keys WHERE key = %s", (key,)).fetchone()
        if existing.account_id != account_id or existing.request_hash != request_hash:
            return 422, {"error": "idempotency key reused with a different request"}
        if existing.status_code is None:
            return 409, {"error": "request with this key is still in progress"}
        return existing.status_code, existing.response

    status, response = charge(account_id, body)          # la operación real, una sola vez
    db.execute("UPDATE idempotency_keys SET status_code = %s, response = %s WHERE key = %s", (status, json.dumps(response), key))
    return status, response
```

Detalles que importan:

- La clave va asociada a la **cuenta** (`account_id`): un cliente no puede reproducir la respuesta de otro adivinando la clave.
- Se guarda un **hash del cuerpo**: la misma clave con un importe distinto es un error del cliente (422), no un «ya te respondí».
- Mientras la primera ejecución está en vuelo, el reintento recibe 409 y el cliente espera y vuelve a intentar; no debe recibir un segundo cobro ni un error definitivo.
- Si `charge` lanza una excepción, borra la clave (o guarda un 500) para que el reintento pueda ejecutar; de lo contrario un fallo transitorio queda «cacheado» 24 h.

**Hacia la pasarela de pago, lo mismo.** Stripe, Adyen y similares aceptan su propia clave de idempotencia; pasa la tuya (o una derivada). Si tu servidor muere **después** de cobrar y **antes** de guardar la respuesta, el reintento vuelve a llamar a la pasarela con la misma clave y la pasarela devuelve el cobro ya hecho en vez de repetirlo. Sin eso, tu idempotencia solo cubre fallos de tu lado.

**Verificación.** Un test que lance la misma petición 20 veces en paralelo con la misma clave y compruebe que `charge` se llamó exactamente una vez y que las 20 respuestas son idénticas (o 409 seguidos de la respuesta definitiva). Y otro con la misma clave y distinto importe que espere 422. El primero falla con tu heurística de los 30 segundos de forma intermitente, que es precisamente el problema que tienes hoy.""",
            },
        ]
    },
]

ROWS += [
    # 6) Paginación: offset frente a cursor (keyset).
    {
        "messages": [
            {
                "role": "user",
                "content": """Nuestro endpoint `GET /orders?page=340&size=50` tarda 3 segundos en las últimas páginas y a veces los clientes ven pedidos repetidos entre una página y la siguiente. ¿Es cosa de índices?""",
            },
            {
                "role": "assistant",
                "content": """Los dos síntomas tienen la misma causa y no se arreglan con índices: es la paginación por **offset**. Cambia a paginación por **cursor** (*keyset*).

**Por qué es lento.** `OFFSET 17000 LIMIT 50` obliga a la base de datos a leer y descartar 17 000 filas para devolver 50; el coste crece linealmente con la página. Un índice ayuda a leer las filas en orden, pero no evita recorrerlas. La página 340 siempre será 340 veces más cara que la primera.

**Por qué se repiten pedidos.** Entre la petición de la página 5 y la de la 6 entra un pedido nuevo que, por el orden (`created_at DESC`), cae en la primera página. Todo se desplaza una posición: el último de la página 5 reaparece como primero de la 6. Con borrados ocurre lo inverso y se saltan elementos. El offset apunta a una **posición**, y las posiciones cambian; un cursor apunta a un **valor**, que no cambia.

**Diseño con cursor:**

```sql
-- primera página
SELECT id, created_at, total FROM orders
 WHERE customer_id = $1
 ORDER BY created_at DESC, id DESC
 LIMIT 51;

-- siguientes: el cursor es (created_at, id) del último elemento devuelto
SELECT id, created_at, total FROM orders
 WHERE customer_id = $1 AND (created_at, id) < ($2, $3)
 ORDER BY created_at DESC, id DESC
 LIMIT 51;
```

Con el índice `(customer_id, created_at DESC, id DESC)`, cada página es una búsqueda en el índice más 51 filas, independientemente de la página. Tres detalles que lo hacen correcto:

- **Desempate por `id`.** `created_at` puede repetirse (dos pedidos en el mismo milisegundo); sin una segunda columna única, el cursor es ambiguo y se saltan filas. La comparación de tuplas `(a, b) < (x, y)` es la forma correcta en PostgreSQL y MySQL 8.
- **Pide `size + 1`.** Si vuelven 51, hay página siguiente y devuelves 50; si vuelven 50 o menos, es la última. Evita un `COUNT(*)` por página.
- **Cursor opaco en la API.** Codifica `(created_at, id)` en base64url y devuélvelo como `next_cursor`; el cliente lo pasa tal cual. Así puedes cambiar las columnas del cursor sin romper a nadie, y nadie construye cursores a mano.

```json
{
  "data": [ { "id": 9120, "created_at": "2025-03-04T10:21:00Z", "total": 120.5 } ],
  "next_cursor": "eyJjIjoiMjAyNS0wMy0wNFQxMDoyMTowMFoiLCJpIjo5MTIwfQ",
  "has_more": true
}
```

**Lo que pierdes y cómo lo compensas:**

- **Saltar a la página N.** No existe con cursores. En una API lo pide casi nadie; en una interfaz, sustitúyelo por filtros (por fecha, por estado) y «siguiente/anterior». Si un informe necesita «ir a la página 340», ese informe necesita una exportación, no una API paginada.
- **Número total de páginas.** Un `COUNT(*)` separado y cacheado unos segundos, o un «aproximadamente 17 000 pedidos» con `reltuples`. Mostrar el total exacto en cada página es lo que convierte 50 ms en 500.
- **Página anterior.** Invierte la comparación y el orden, y vuelve a invertir el resultado en la aplicación, o guarda el cursor de la página anterior en el cliente.

**Transición sin romper clientes.** Mantén `page`/`size` un tiempo (documentado como obsoleto y con un límite, por ejemplo `page <= 100`, que evita el peor caso), añade `cursor` y haz que las respuestas lleven siempre `next_cursor`. Los clientes migran cuando quieran; los nuevos no conocen otra cosa.

**Verificación:** un test que inserte 200 pedidos, recorra todas las páginas con el cursor mientras un hilo inserta 20 pedidos nuevos, y compruebe que no hay ids repetidos ni saltados entre los 200 originales. El mismo test con `OFFSET` falla casi siempre.""",
            },
        ]
    },
    # 7) Formato de errores de una API (usuario en inglés, RFC 9457).
    {
        "messages": [
            {
                "role": "user",
                "content": """We're designing the error responses for a new public REST API. Right now every endpoint returns something slightly different: some `{"error": "not found"}`, some `{"message": "not found", "code": 1042}`, one returns a plain string. What should the one format be?""",
            },
            {
                "role": "assistant",
                "content": """Use **RFC 9457 Problem Details** (`application/problem+json`). It is a standard, clients and frameworks already understand it, and it has exactly the fields you need without inventing a schema.

**The shape:**

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Validation failed",
  "status": 422,
  "detail": "2 fields are invalid.",
  "instance": "/orders/8f3a",
  "errors": [
    { "field": "email", "message": "must be a valid email address" },
    { "field": "items[2].quantity", "message": "must be greater than 0" }
  ],
  "trace_id": "4b7e6d1a0c9f"
}
```

What each field is for, and the design decisions behind them:

- **`type`** is the machine-readable identifier of the *kind* of error. Make it a URL under your domain that resolves to documentation; clients switch on it (`if (problem.type.endsWith("/insufficient-funds"))`), never on `title` or `detail`, which you are free to reword. This replaces the ad hoc `code` field, with the advantage that it is self-documenting.
- **`title`** is a short, stable, human-readable summary per `type`. **`detail`** is specific to this occurrence. Keep `detail` safe to show to an end user; never put stack traces, SQL or internal hostnames there.
- **`status`** duplicates the HTTP status so the body is self-contained in logs and in clients that lose the status (some SDK wrappers do).
- **Extensions** (`errors`, `trace_id`, `retry_after`) are allowed by the RFC; add the ones you need, document them per `type`. The `errors` array with `field` paths is the one that saves client developers the most time.
- **`trace_id`** lets a customer quote one identifier in a support ticket and lets you find the request in your tracing system. It is the single most useful field for operations.

**Rules that matter more than the format:**

1. **One shape for all errors, including the ones your framework or gateway emits.** A 404 from an unknown route, a 405, a 413 from the proxy, a 500 from an unhandled exception: all of them must be `problem+json`. The plain-text `nginx` 502 is the one clients forget to handle; configure the gateway to emit the same JSON.
2. **Use the HTTP status honestly.** 400 for malformed syntax, 422 for valid JSON that fails validation, 401 for missing or bad credentials, 403 for known identity without permission, 404 for resources that do not exist (and, deliberately, for resources the caller must not know exist), 409 for state conflicts, 429 with `Retry-After` for rate limits. Status codes are the first thing retry logic looks at: 5xx and 429 are retryable, 4xx are not.
3. **Never leak which part failed in authentication.** "Invalid credentials" for both unknown user and wrong password.
4. **Keep a registry of `type` values** in the repo, with the HTTP status each one uses. Adding a type is a reviewed change; it is part of your API contract.

**Implementation note:** most frameworks have this built in or as a small library: Spring Boot 3 (`ProblemDetail`), ASP.NET Core (`ProblemDetails`), FastAPI via a custom exception handler, Express via `http-problem-details`. Write one error handler at the edge that maps your domain exceptions to `(status, type)` pairs, and nothing else in the codebase constructs error bodies.

**Verification:** a contract test that walks every route with bad input (unknown route, wrong method, invalid body, missing auth) and asserts `Content-Type: application/problem+json` and the presence of `type`, `title`, `status`. Run it against the deployed gateway, not only the app, so the proxy's own errors are covered too.""",
            },
        ]
    },
    # 8) gRPC frente a REST entre servicios internos.
    {
        "messages": [
            {
                "role": "user",
                "content": """Tenemos 5 servicios internos en Go y Python que se hablan por REST con JSON. Un compañero propone pasar todo a gRPC por rendimiento. ¿Merece la pena el cambio?""",
            },
            {
                "role": "assistant",
                "content": """Por rendimiento solo, no. Por **contratos tipados y generación de clientes**, probablemente sí, y conviene decidirlo por ese motivo, porque es el que vais a notar.

**Lo que el rendimiento aporta de verdad.** gRPC usa Protobuf (binario, compacto) sobre HTTP/2 (multiplexado, conexiones persistentes). En mediciones típicas, serializar y deserializar es 3-10 veces más rápido que JSON y el tamaño en red un 30-70 % menor. Pero mira dónde está el tiempo en vuestras llamadas: si un endpoint tarda 40 ms y 35 ms son la consulta a la base de datos, pasar de 3 ms a 0,5 ms de serialización no cambia nada perceptible. Mide con un perfil antes de atribuir latencia a JSON; en la mayoría de sistemas con cinco servicios la respuesta es que no es el cuello de botella.

**Lo que sí cambia el día a día:**

| | REST + JSON | gRPC + Protobuf |
|---|---|---|
| Contrato | OpenAPI, si alguien lo mantiene | El `.proto` **es** el contrato; sin él no compila |
| Clientes Go y Python | A mano o generados de OpenAPI, calidad variable | Generados, tipados, idénticos en ambos lenguajes |
| Cambios incompatibles | Se descubren en producción | Se descubren al compilar (campos numerados, reglas de evolución claras) |
| Streaming | SSE o WebSockets, cada uno a su manera | Nativo, en ambos sentidos |
| Depuración | `curl` y leer la respuesta | `grpcurl`, reflexión; algo menos directo |
| Navegadores y *webhooks* | Natural | Necesita grpc-web o un *gateway* |
| Balanceo | Cualquier balanceador L7 | HTTP/2 persistente: el balanceo por conexión no reparte; hace falta balanceo por petición (*proxy* L7 con soporte gRPC o balanceo en cliente) |

Con Go y Python en el mismo sistema, la fila de «clientes generados» es la que vale el cambio: hoy cada servicio tiene su propia noción de qué devuelve `/orders/{id}`, y la primera vez que alguien renombra un campo lo averiguáis por un error 500 en otro servicio.

**Recomendación concreta:**

1. gRPC para las llamadas **servicio a servicio** que ya son internas y tipadas por naturaleza (consultar stock, calcular precio, validar un cliente). Un repositorio de `.proto` compartido con CI que ejecute `buf lint` y `buf breaking` contra la rama principal: así un cambio incompatible falla en el *pull request*.
2. REST se queda en el **borde**: la API pública, lo que consumen navegadores, los *webhooks*. No pongas gRPC donde haya un navegador o un tercero.
3. Migra **una llamada**, la más frecuente o la que más cambios de contrato haya sufrido, y vive con ella un mes. Si el equipo no nota mejora en seguridad de cambios, parad ahí; el coste de tener los dos protocolos para una llamada es pequeño.

**Qué os va a costar**, para que no sorprenda:

- El balanceo. Si usáis Kubernetes con un `Service` normal, las conexiones HTTP/2 se quedan pegadas a un pod y el escalado no reparte carga. Necesitáis un *proxy* con soporte gRPC (Envoy, Linkerd, el *ingress* que lo soporte) o balanceo en cliente.
- *Deadlines* y reintentos hay que configurarlos explícitamente; por defecto una llamada gRPC puede esperar para siempre.
- Observabilidad: los interceptores de trazas y métricas existen (OpenTelemetry los tiene), pero hay que instalarlos; con REST probablemente ya los tenéis en el *middleware* HTTP.

**Cuándo diría que no del todo:** si el equipo es de dos personas, si los servicios cambian de contrato una vez al año, o si la mitad del tráfico interno viene de navegadores. Entonces el coste de operar dos protocolos no se amortiza, y OpenAPI con generación de clientes (`oapi-codegen` en Go, `openapi-python-client`) y un *linter* de cambios incompatibles (`oasdiff`) os da el 70 % del beneficio sin tocar el transporte.""",
            },
        ]
    },
    # 9) Esquema de datos para dinero y varias monedas (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy haciendo mi primera app con pagos y guardo los precios en una columna `FLOAT` en Postgres. Un amigo me dijo que eso está mal pero no supo explicarme bien por qué. ¿Cómo debería guardarlos? Voy a tener euros y dólares.",
            },
            {
                "role": "assistant",
                "content": """Tu amigo tiene razón. Guarda cada precio como un **entero en la unidad menor** (céntimos) más una columna con la **moneda**.

**Por qué `FLOAT` está mal.** Un `FLOAT` guarda el número en binario, y en binario la mayoría de los decimales no son exactos: `0.10` se almacena como `0.1000000000000000055511151231257827`. Con un precio no se nota, pero suma mil importes de 0,10 y obtendrás 100,00000000000007 o 99,99999999999994. En contabilidad, un céntimo de diferencia es un cuadre que no sale, y los redondeos se acumulan en la dirección que menos esperas. Compruébalo en Postgres:

```sql
SELECT 0.1::float + 0.2::float;          -- 0.30000000000000004
SELECT 0.1::numeric + 0.2::numeric;      -- 0.3
```

**Dos opciones correctas:**

1. **`NUMERIC(12, 2)`** (decimal exacto). Fácil de leer en consultas y en el panel de administración. Vale perfectamente para una primera app.
2. **`BIGINT` en céntimos** (`1999` para 19,99 €). Es el estándar de las pasarelas de pago (Stripe, Adyen, PayPal) y de la mayoría de sistemas financieros, porque un entero no tiene redondeo posible, se suma más rápido y no depende de que nadie recuerde los decimales de la columna.

Elijo la 2 para ti precisamente porque vas a tener **varias monedas**: no todas tienen dos decimales (el yen tiene cero, el dinar kuwaití tres). Con un entero en la unidad menor y la moneda al lado, el esquema no cambia cuando añadas una moneda.

**Esquema:**

```sql
CREATE TABLE products (
    id             bigserial PRIMARY KEY,
    name           text NOT NULL,
    price_minor    bigint NOT NULL CHECK (price_minor >= 0),
    currency       char(3) NOT NULL CHECK (currency IN ('EUR', 'USD'))
);
```

Reglas que acompañan al esquema:

- **La moneda va siempre junto al importe.** Un importe sin moneda no es un dato, es un número suelto. En el código, un pequeño tipo `Money(amount_minor: int, currency: str)` que no permite sumar euros con dólares te ahorrará el error más común.
- **No conviertas entre monedas en la base de datos.** La conversión necesita un tipo de cambio y una fecha; guárdalos cuando ocurra (`exchange_rate`, `rate_date`) en la fila del pago, para poder explicar un importe meses después.
- **Redondea una sola vez**, al final de cada cálculo (impuestos, descuentos), con la regla que diga tu país (en la UE, normalmente «mitad hacia arriba» o «mitad al par»; elige una, escríbela y úsala en todas partes).
- **Muestra con formato en la interfaz**, nunca guardes «19,99 €» como texto: `Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(1999 / 100)` en el navegador.

**Migrar lo que ya tienes:**

```sql
ALTER TABLE products ADD COLUMN price_minor bigint, ADD COLUMN currency char(3);
UPDATE products SET price_minor = round(price * 100)::bigint, currency = 'EUR';
ALTER TABLE products ALTER COLUMN price_minor SET NOT NULL, ALTER COLUMN currency SET NOT NULL;
ALTER TABLE products DROP COLUMN price;
```

El `round` es necesario justo por el problema del `FLOAT`: `19.99 * 100` puede dar `1998.9999999999998`.

**Comprobación:** después de migrar, `SELECT SUM(price_minor) FROM products` debe coincidir con lo que te daba antes `SELECT SUM(price) * 100` redondeado; si difiere en algún céntimo, ese céntimo era el error del `FLOAT`, y acabas de verlo con tus propios ojos.""",
            },
        ]
    },
    # 10) Migración de esquema sin parada: renombrar una columna (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos que renombrar la columna `users.name` a `users.full_name` en producción (Postgres, app en Node con 6 instancias detrás de un balanceador, despliegue continuo). Un `ALTER TABLE RENAME` es instantáneo, ¿por qué el equipo de plataforma dice que no podemos hacerlo así?",
            },
            {
                "role": "assistant",
                "content": """Porque el `ALTER` es instantáneo pero el **despliegue no lo es**. Durante los minutos en que conviven instancias viejas y nuevas, alguna versión del código apunta a una columna que no existe. Si renombras primero, las 6 instancias viejas fallan hasta que se sustituyan; si despliegas primero, las instancias nuevas fallan hasta que renombres. En ambos casos hay errores 500 en producción durante el *rollout*, y si tienes que hacer *rollback* del código, la columna ya tiene el nombre nuevo y el código viejo tampoco funciona.

La regla general: **cada cambio de esquema tiene que ser compatible con la versión anterior y con la siguiente del código.** Un renombrado se hace en fases («expandir y contraer»), con despliegues entre medias:

**Fase 1: expandir.** Añade la columna nueva sin tocar la vieja.

```sql
ALTER TABLE users ADD COLUMN full_name text;
```

**Fase 2: escribir en las dos.** Despliega código que escribe en `name` **y** `full_name` y sigue leyendo de `name`. A partir de aquí, todo registro nuevo o modificado tiene las dos columnas sincronizadas.

**Fase 3: rellenar los datos antiguos**, por lotes para no bloquear la tabla ni saturar la replicación:

```sql
UPDATE users SET full_name = name
 WHERE id IN (SELECT id FROM users WHERE full_name IS NULL ORDER BY id LIMIT 5000);
-- repetir hasta que afecte a 0 filas
```

**Fase 4: leer de la nueva.** Despliega código que lee de `full_name` y sigue escribiendo en las dos. Si algo va mal, el *rollback* al código de la fase 2 funciona porque `name` sigue al día.

**Fase 5: dejar de escribir en la vieja.** Despliega código que ya no conoce `name`. Verifica que ninguna consulta, informe, vista o trabajo nocturno la use: `grep` en el repo y `pg_stat_statements` en la base de datos durante unos días.

**Fase 6: contraer.**

```sql
ALTER TABLE users DROP COLUMN name;
```

Mejor en dos pasos si quieres red de seguridad: primero `ALTER TABLE users RENAME COLUMN name TO name_deprecated` (cualquier uso olvidado falla de forma visible y reversible), y la semana siguiente el `DROP`.

**Por qué no un *trigger* en vez de la doble escritura en código.** Un *trigger* que copie `name` a `full_name` (y viceversa) hace la fase 2 sin tocar la app, y es una opción válida y a veces mejor con muchas rutas de escritura. Prefiero la doble escritura en código cuando las escrituras pasan por un solo repositorio o modelo, porque queda en el repo, se revisa y se borra en la fase 5 con un *commit* normal; los *triggers* se olvidan en producción.

Seis fases para un renombrado parece mucho; cada una es pequeña, ninguna puede romper nada y todas son reversibles. Un renombrado directo es un solo paso que puede tirar el servicio. Por eso plataforma dice que no.""",
            },
            {
                "role": "user",
                "content": "Entendido. ¿Y si en vez de renombrar lo que hago es cambiar el tipo, de `varchar(100)` a `text`? ¿También seis fases?",
            },
            {
                "role": "assistant",
                "content": """No: ese cambio en concreto es **compatible en los dos sentidos** y se hace en un solo paso.

`varchar(100)` → `text` en PostgreSQL es solo quitar una restricción de longitud: no reescribe la tabla, no bloquea más que un instante para tomar el *lock* y actualizar el catálogo, y cualquier versión del código sigue funcionando porque leer y escribir una cadena no cambia.

```sql
ALTER TABLE users ALTER COLUMN name TYPE text;
```

Los cambios de tipo que **sí** exigen fases son los que reescriben la tabla o cambian la semántica: `text` → `varchar(100)` (puede fallar por datos existentes y bloquea mientras valida), `int` → `bigint` (reescribe la tabla entera con *lock* exclusivo; en una tabla grande son minutos sin escrituras, y se hace con columna nueva + relleno + intercambio, igual que el renombrado), `timestamp` → `timestamptz` (cambia la interpretación de todos los valores existentes), o cualquier cambio donde el código viejo deje de entender lo que lee.

Criterio para decidir rápido: pregúntate «¿puede el código de **ayer** leer y escribir esta columna después del cambio, y el de **mañana** antes del cambio?». Si la respuesta es sí a las dos, un paso. Si alguna es no, expandir y contraer.

Dos detalles operativos para el paso único:

- Lánzalo con `SET lock_timeout = '2s'` delante. Si hay una transacción larga que impide tomar el *lock*, el `ALTER` falla en 2 s y lo reintentas, en vez de ponerse a la cola y bloquear a todas las consultas que llegan detrás, que es la forma habitual de convertir un `ALTER` «instantáneo» en una caída.
- Si tenéis un ORM con esquema declarado (Prisma, Drizzle, TypeORM), actualiza el modelo en el mismo despliegue para que la migración y el código cuenten lo mismo; con `text` el código viejo no se queja, pero el *diff* de esquema sí.""",
            },
        ]
    },
]

ROWS += [
    # 11) Caché e invalidación de un catálogo, con estampida.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """La página de producto de nuestra tienda hace 12 consultas a Postgres por visita (producto, variantes, precios por país, stock, valoraciones, relacionados). Tenemos picos de 3000 visitas por minuto en campañas y la base de datos sufre. Quiero meter Redis pero no sé cómo organizar la invalidación para que no se vean precios viejos.""",
            },
            {
                "role": "assistant",
                "content": """Cachea **la página de producto ensamblada** como un único objeto por `producto_id` y país, con TTL corto y invalidación por evento. No caches las 12 consultas por separado: multiplicarías por 12 las claves, los fallos de caché y los puntos donde la invalidación puede olvidarse.

**Por qué un objeto ensamblado.** Lo que quieres servir es «la página del producto 8f3 para España». Con una clave `producto:8f3:ES` un acierto de caché son 0 consultas a Postgres; con 12 cachés independientes, un acierto parcial sigue siendo varias consultas y el código de la página tiene que saber qué estaba y qué no.

**Qué puede estar «viejo» y cuánto.** Separa los datos por tolerancia al retraso, porque eso decide el mecanismo:

| Dato | ¿Tolera retraso? | Mecanismo |
|---|---|---|
| Nombre, descripción, imágenes, variantes | Minutos | TTL |
| Precio por país | Segundos; nunca «viejo» tras un cambio deliberado | Invalidación por evento + TTL de respaldo |
| Stock | Depende: «hay/no hay» tolera segundos; «quedan 2» no | Fuera de la caché o TTL de 5-10 s |
| Valoraciones, relacionados | Minutos u horas | TTL largo |

**Diseño:**

1. **Cache-aside con TTL de respaldo.** La página se construye desde Postgres solo en fallo de caché y se guarda con `EX 300`. El TTL no es el mecanismo principal de frescura; es la red de seguridad que garantiza que un evento de invalidación perdido se corrige solo en 5 minutos.
2. **Invalidación por evento al escribir.** Cada cambio de producto, variante o precio publica `producto.cambiado {id}` (desde el mismo lugar donde se hace el `COMMIT`, idealmente con *outbox*) y un consumidor borra `producto:{id}:*`. Borrar, no reescribir: la siguiente visita reconstruye desde la verdad. Para borrar por patrón sin `KEYS`, mantén un `SET` por producto con sus claves (`producto:8f3:claves` → `{producto:8f3:ES, producto:8f3:MX}`) y borra las que contenga.
3. **Stock fuera del objeto cacheado.** Pide el stock en una consulta separada y barata (`SELECT cantidad FROM stock WHERE producto_id = $1`, con índice, menos de 1 ms) o cachéalo aparte con TTL de 5 s. Así una compra no invalida la página entera y «quedan 2» es siempre reciente.
4. **Protección contra la estampida.** Con 3000 visitas por minuto, cuando una clave expira (o la borras tras un cambio de precio en plena campaña), cientos de peticiones fallan en caché a la vez y lanzan las 12 consultas cada una. Es el momento en que la base de datos cae. Dos medidas, combinadas:

   - **Bloqueo de reconstrucción:** la primera petición que falla toma un *lock* (`SET producto:8f3:ES:lock 1 NX EX 10`), reconstruye y escribe; las demás esperan 50-100 ms y releen la caché, o sirven la versión caducada si la guardas con un TTL lógico dentro del valor (`{"expira": 1712345678, "datos": {"nombre": "Taza"}}` con un TTL real mayor).
   - **Expiración escalonada:** TTL = 300 s ± 30 s aleatorios, para que las claves de los 200 productos de la campaña no caduquen en el mismo segundo tras un despliegue que vació la caché.

```python
def pagina_producto(producto_id: str, pais: str) -> dict:
    clave = f"producto:{producto_id}:{pais}"
    if (cacheado := redis.get(clave)) is not None:
        return json.loads(cacheado)
    lock = f"{clave}:lock"
    if redis.set(lock, "1", nx=True, ex=10):
        try:
            pagina = construir_pagina(producto_id, pais)          # las consultas, una sola vez
            redis.set(clave, json.dumps(pagina), ex=300 + random.randint(-30, 30))
            redis.sadd(f"producto:{producto_id}:claves", clave)
            return pagina
        finally:
            redis.delete(lock)
    time.sleep(0.05)
    return pagina_producto(producto_id, pais)                      # reintenta: casi seguro ya está
```

**Lo que no haría:** un *warm-up* que precargue todo el catálogo cada noche (coste alto, la mayoría de productos no se visita) ni caché de consultas SQL genérica (invisible para quien cambia los datos; nadie sabe qué invalidar).

**Números para comprobar que funciona.** Con 3000 visitas por minuto y un 95 % de aciertos, Postgres recibe 150 reconstrucciones por minuto (1800 consultas) en vez de 36 000: 20 veces menos. Mide la tasa de aciertos por clave desde el primer día (un contador en Redis o la métrica del cliente); si baja del 90 % en campaña, el TTL es demasiado corto o la clave incluye algo que varía por usuario y no debería.

**Verificación del requisito de precios:** un test de integración que cambie el precio, publique el evento y compruebe que la siguiente lectura devuelve el precio nuevo en menos de 1 s; y otro que simule 200 lecturas concurrentes tras una invalidación y cuente que `construir_pagina` se ejecutó una vez.""",
            },
        ]
    },
    # 12) Colas y reintentos: idempotencia, backoff y DLQ.
    {
        "messages": [
            {
                "role": "user",
                "content": """Procesamos pedidos desde una cola SQS. Cuando el servicio de facturación de un tercero falla, el consumidor relanza la excepción, SQS reentrega el mensaje al momento y así en bucle hasta que el tercero vuelve; mientras tanto, los demás pedidos esperan detrás. ¿Cómo debería ser el manejo de errores?""",
            },
            {
                "role": "assistant",
                "content": """Tres piezas, y las tres son necesarias: **reintentos con espera creciente**, **cola de mensajes muertos** (DLQ) y **consumidor idempotente**. Lo que tienes ahora es un reintento inmediato e infinito, que es la peor combinación: martillea a un tercero que ya está caído y bloquea el resto.

**1. Clasifica el error antes de decidir qué hacer.** No todos los fallos merecen reintento:

- **Transitorio** (timeout, 503, 429, conexión rechazada): reintentar con espera.
- **Permanente** (400 por datos inválidos, cliente inexistente, importe negativo): reintentar es inútil; el mensaje va directamente a la DLQ con el motivo.
- **Desconocido** (excepción inesperada): trátalo como transitorio pero con pocos intentos.

```python
class ErrorTransitorio(Exception): pass
class ErrorPermanente(Exception): pass

def facturar(pedido: dict) -> None:
    try:
        cliente_facturacion.emitir(pedido)
    except httpx.TimeoutException as exc:
        raise ErrorTransitorio(str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (429, 500, 502, 503, 504):
            raise ErrorTransitorio(str(exc)) from exc
        raise ErrorPermanente(exc.response.text) from exc
```

**2. Reintento con *backoff* exponencial y límite, delegado a la cola.** En SQS no reintentes dentro del consumidor con `sleep` (bloqueas el *worker* y el mensaje expira su *visibility timeout*). Devuelve el mensaje a la cola con una visibilidad creciente:

```python
ESPERAS = [30, 120, 600, 1800, 3600]       # segundos: 30 s, 2 min, 10 min, 30 min, 1 h

def procesar(mensaje) -> None:
    intento = int(mensaje.attributes.get("ApproximateReceiveCount", 1))
    try:
        facturar(json.loads(mensaje.body))
        mensaje.delete()
    except ErrorTransitorio:
        if intento >= len(ESPERAS):
            raise                              # supera maxReceiveCount: SQS lo mueve a la DLQ
        espera = ESPERAS[intento - 1] + random.randint(0, 15)
        mensaje.change_visibility(VisibilityTimeout=espera)
    except ErrorPermanente as exc:
        enviar_a_dlq(mensaje, motivo=str(exc))
        mensaje.delete()
```

El *jitter* aleatorio evita que 500 pedidos que fallaron a la vez vuelvan a la vez. Configura en la cola una `RedrivePolicy` con `maxReceiveCount = 6` y la DLQ como destino: cuando se agotan los intentos, SQS mueve el mensaje solo, sin código.

**3. Idempotencia en el consumidor.** SQS estándar entrega «al menos una vez», y además tus reintentos pueden repetir una factura si el tercero respondió *timeout* después de emitirla. Guarda el `pedido_id` facturado y usa la clave de idempotencia del tercero si la ofrece:

```python
def facturar(pedido: dict) -> None:
    if repositorio.factura_existe(pedido["id"]):
        return
    factura = cliente_facturacion.emitir(pedido, idempotency_key=f"pedido-{pedido['id']}")
    repositorio.guardar_factura(pedido["id"], factura["id"])
```

**4. Que un tercero caído no bloquee a los demás.** Con el *backoff* ya no hay bucle, pero si el tercero está caído una hora, todos los pedidos de esa hora van acumulando intentos. Dos medidas:

- Un **cortacircuitos**: tras N fallos seguidos, el consumidor deja de llamar al tercero durante un minuto y devuelve los mensajes a la cola con visibilidad de 60 s sin consumir intento. Evita gastar los 6 intentos de todos los pedidos en una caída larga.
- **Una cola por dependencia** si tienes varias (facturación, envío, notificación): la caída de una no retiene a las otras. Con una sola dependencia no hace falta.

**5. La DLQ tiene dueño y proceso.** Una DLQ sin alarma es un agujero negro. Alarma cuando tenga más de 0 mensajes durante 5 minutos, un panel para ver el motivo (guárdalo como atributo del mensaje) y un comando para **reinyectar** a la cola principal cuando el tercero se recupere o se corrijan los datos. Los permanentes se corrigen a mano o se descartan con registro; nunca se reintentan a ciegas.

**Verificación:** un test con un cliente de facturación falso que falle con 503 tres veces y responda a la cuarta, comprobando que se emite **una** factura y que los `change_visibility` fueron 30, 120 y 600 s; y otro con un 400 que compruebe que el mensaje llega a la DLQ al primer intento. Y en producción, la métrica `ApproximateAgeOfOldestMessage` de la cola principal: con el diseño nuevo, una caída del tercero la hace subir despacio y bajar sola; con el bucle actual, se dispara y se queda.""",
            },
        ]
    },
    # 13) Límite de tasa (usuario en inglés, pide la respuesta en español).
    {
        "messages": [
            {
                "role": "user",
                "content": """We need rate limiting on a public API (about 2,000 customers, each with an API key, 4 app servers behind a load balancer). Should it live in the app or in the gateway, and which algorithm? Please answer in Spanish, the team reads it better.""",
            },
            {
                "role": "assistant",
                "content": """En el *gateway* (o en un *middleware* común con estado en Redis), con **token bucket** por clave de API. La razón de cada decisión:

**Dónde.** Con 4 servidores detrás de un balanceador, un límite en memoria de cada proceso es en realidad un límite 4 veces mayor y además errático: según a qué servidor caiga cada petición, el mismo cliente ve 429 o no. El contador tiene que ser **compartido**. Dos sitios donde ponerlo:

- El *gateway* (Kong, Envoy, nginx con `limit_req` + Redis, el de tu nube) si ya tenéis uno: no toca el código de la API, protege también de peticiones que no llegan a autenticarse y suele traer el algoritmo hecho.
- Un *middleware* en la aplicación con Redis si no tenéis *gateway*. Un Redis gestionado pequeño basta: 2000 clientes son 2000 claves.

Lo que no haría es meter un *gateway* nuevo solo para esto; si no hay, el *middleware* es una tarde de trabajo.

**Qué algoritmo.** Los tres habituales y qué los distingue:

| Algoritmo | Permite ráfagas | Precisión | Memoria por cliente | Caso |
|---|---|---|---|---|
| Ventana fija | Sí, el doble en el borde (100 al final de un minuto + 100 al principio del siguiente) | Baja | 1 contador | Solo si da igual |
| Ventana deslizante (log o aproximada) | No | Alta | Un `ZSET` o 2 contadores | Límites estrictos («nunca más de N por minuto») |
| Token bucket | Sí, controladas (hasta el tamaño del cubo) | Alta | 2 números | APIs públicas |

**Token bucket** encaja con una API pública porque los clientes legítimos hacen ráfagas (una sincronización nocturna lanza 50 llamadas en 2 segundos y luego nada durante una hora) y lo que quieres limitar es el **ritmo sostenido**, no castigar la ráfaga. Cada cliente tiene un cubo con capacidad `B` (ráfaga permitida) que se rellena a `R` fichas por segundo (ritmo sostenido); cada petición consume una ficha; sin fichas, 429.

En Redis, la implementación atómica es un *script* Lua (para que leer, rellenar y descontar sea una sola operación):

```lua
-- KEYS[1] = clave del cliente; ARGV = capacidad, ritmo_por_segundo, ahora_ms, coste
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens') or ARGV[1])
local ultimo = tonumber(redis.call('HGET', KEYS[1], 'ts') or ARGV[3])
local recarga = (tonumber(ARGV[3]) - ultimo) / 1000 * tonumber(ARGV[2])
tokens = math.min(tonumber(ARGV[1]), tokens + recarga)
local permitido = 0
if tokens >= tonumber(ARGV[4]) then
  tokens = tokens - tonumber(ARGV[4])
  permitido = 1
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', ARGV[3])
redis.call('PEXPIRE', KEYS[1], 60000)
return { permitido, tokens }
```

Valores de partida razonables para un plan estándar: `R = 10` peticiones/s, `B = 100`. Un cliente puede disparar 100 de golpe y después mantener 10 por segundo. Ajusta por plan (`R` y `B` salen de la tabla de planes, indexada por la clave de API).

**Lo que el cliente necesita ver** (es parte del diseño, no un adorno):

```
HTTP/1.1 429 Too Many Requests
Retry-After: 3
RateLimit-Limit: 100
RateLimit-Remaining: 0
RateLimit-Reset: 3
```

`Retry-After` convierte el 429 en algo que los SDK manejan solos. Las cabeceras `RateLimit-*` (borrador de la IETF, ya usadas por GitHub y otros) permiten al cliente frenar **antes** del 429, que es lo que quieres.

**Decisiones de borde:**

- **Si Redis no responde**, deja pasar (*fail open*) y registra la alarma. Un límite de tasa caído no debe tirar la API entera; para abuso tenéis el *gateway* y la red.
- **Límite global además del de cliente**: un cubo para toda la API protege la base de datos cuando 300 clientes hacen su sincronización nocturna a la misma hora.
- **Coste por endpoint**: una búsqueda pesada consume 5 fichas y un `GET` por id consume 1 (el parámetro `coste` del *script*). Es más justo que un límite distinto por endpoint y mucho más simple.

**Verificación:** un test contra Redis real que lance 150 peticiones en un segundo con `B = 100, R = 10` y compruebe exactamente 100 permitidas y 50 rechazadas con `Retry-After` correcto; y luego, tras esperar 5 s, 50 más permitidas. Y un test de que dos procesos distintos comparten el mismo contador, que es lo que falla en la versión en memoria.""",
            },
        ]
    },
    # 14) Autenticación de una SPA: sesiones frente a JWT (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy montando la autenticación de una SPA en React con una API en Node. Todos los tutoriales usan JWT en localStorage. ¿Es lo correcto o hay algo mejor?",
            },
            {
                "role": "assistant",
                "content": """Para una SPA con su propia API en el mismo dominio (o subdominios), lo correcto es **sesión en el servidor con cookie `HttpOnly`**, no JWT en `localStorage`. Los tutoriales usan JWT porque es fácil de enseñar, no porque sea la mejor opción para este caso.

**El problema de `localStorage`:** cualquier JavaScript que se ejecute en tu página puede leerlo. Una dependencia comprometida, una extensión del navegador maliciosa o un XSS en cualquier rincón de la aplicación (un comentario mal escapado) roban el *token* y con él la sesión, desde otra máquina, hasta que caduque. Una cookie `HttpOnly` no es accesible desde JavaScript: el mismo XSS puede hacer peticiones en nombre del usuario mientras la pestaña está abierta, que es grave, pero no puede exfiltrar la credencial ni usarla después.

**El problema de los JWT como sesión:** no se pueden revocar. Si el usuario cierra sesión en todos los dispositivos, cambia la contraseña o le desactiváis la cuenta, el JWT emitido sigue siendo válido hasta que expira. Las soluciones (listas de revocación, *tokens* de corta duración con *refresh tokens*) terminan consultando el servidor en cada petición, que es exactamente lo que el JWT pretendía evitar. En ese punto, una sesión en servidor es más simple y tiene las mismas propiedades.

**Diseño recomendado:**

```js
import session from "express-session";
import RedisStore from "connect-redis";

app.use(session({
  store: new RedisStore({ client: redis }),
  secret: process.env.SESSION_SECRET,
  name: "sid",
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 1000 * 60 * 60 * 24 * 14,
  },
}));
```

- **`SameSite=Lax`** bloquea el CSRF en la mayoría de casos (el navegador no envía la cookie en peticiones `POST` iniciadas desde otro sitio). Si la API y la SPA están en dominios distintos que no comparten sitio (`app.com` y `api-otro.com`), necesitas `SameSite=None; Secure` y entonces sí añade un *token* CSRF (patrón *double submit* o cabecera personalizada que el navegador no envía en formularios).
- **Sesiones en Redis**, no en memoria: sobreviven a reinicios y se comparten entre instancias. Cerrar sesión es borrar una clave; revocar todo lo de un usuario es borrar sus claves.
- **Regenera el id de sesión al iniciar sesión** (`req.session.regenerate`) para evitar la fijación de sesión.
- En React, `fetch` con `credentials: "include"` y nada más: no hay *token* que guardar, renovar ni adjuntar.

**Cuándo sí usaría JWT:** cuando el consumidor **no es un navegador tuyo**: una API pública con clientes de terceros, aplicaciones móviles nativas (con el *token* en el almacén seguro del sistema), o comunicación entre servicios. Y con un proveedor de identidad externo (Auth0, Cognito, Keycloak) que emita *tokens*, la SPA sigue sin tener que guardarlos en `localStorage`: el patrón BFF (*backend for frontend*) hace que tu API intercambie el *token* por una sesión con cookie, y el navegador nunca ve el JWT.

**Verificación:** una prueba manual de dos minutos que vale más que cualquier argumento: abre la consola del navegador en tu app y escribe `document.cookie` y `localStorage`. Si la credencial aparece en cualquiera de los dos, un XSS se la lleva. Con cookie `HttpOnly`, no aparece en ninguno.""",
            },
            {
                "role": "user",
                "content": "El problema es que vamos a tener también una app móvil en React Native contra la misma API. ¿Entonces tengo que hacer JWT igualmente?",
            },
            {
                "role": "assistant",
                "content": """No hace falta elegir uno: la misma API puede aceptar **las dos credenciales**, y es el diseño habitual cuando hay web y móvil.

**Para la app móvil**, el navegador no está, así que las cookies pierden su ventaja y los *tokens* son lo natural. Pero no tienen por qué ser JWT: un **token opaco** (una cadena aleatoria de 32 bytes guardada en la base de datos o en Redis con el id de usuario, dispositivo y caducidad) tiene todo lo bueno del JWT para este caso y además es revocable al instante. La app lo guarda en el almacén seguro del sistema (Keychain en iOS, Keystore en Android; en React Native, `expo-secure-store` o `react-native-keychain`), nunca en `AsyncStorage`.

**En la API**, una capa de autenticación que resuelve «quién es» a partir de cualquiera de las dos:

```js
async function authenticate(req, res, next) {
  if (req.session?.userId) {
    req.user = await users.findById(req.session.userId);
    return next();
  }
  const header = req.get("authorization");
  if (header?.startsWith("Bearer ")) {
    const token = await tokens.findValid(header.slice(7));       // hash del token, caducidad, no revocado
    if (token) {
      req.user = await users.findById(token.userId);
      return next();
    }
  }
  return res.status(401).json({ type: "about:blank", title: "Unauthorized", status: 401 });
}
```

El resto de la API no sabe ni le importa por qué vía llegó `req.user`.

**Detalles que importan para el *token* móvil:**

- Guarda en la base de datos el **hash** del *token* (SHA-256), no el *token*; una fuga de la tabla no da acceso.
- Un *token* por dispositivo, con nombre y última actividad: permite la pantalla «sesiones activas» y revocar una sin tocar las demás.
- Caducidad larga (30-90 días) con renovación deslizante en cada uso, o corta con *refresh token*; para una app propia, la primera es más simple y suficiente, porque la revocación ya la tienes.
- Para el CSRF, el *token* en cabecera `Authorization` no lo sufre (el navegador no lo añade solo), así que el *middleware* CSRF debe aplicarse únicamente a las peticiones autenticadas por cookie.

**Cuándo JWT firmado de verdad:** si la API móvil va a escalar a muchos servicios que deban validar el *token* sin consultar una base de datos común, o si lo emite un proveedor de identidad externo. En ese caso, JWT de vida corta (5-15 minutos) + *refresh token* opaco y revocable, que es el patrón que recomiendan OAuth 2.1 y OpenID Connect para aplicaciones nativas (con PKCE si hay redirección). Para «una API, una app, un equipo», el *token* opaco cubre todo con menos piezas.""",
            },
        ]
    },
    # 15) Autorización: RBAC frente a ABAC en un caso concreto (rioplatense).
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y con una recomendación clara."},
            {
                "role": "user",
                "content": """Estamos armando el sistema de permisos de una plataforma para clínicas. Hoy tenemos roles (admin, médico, recepción) y funciona, pero ahora piden que un médico solo vea las historias clínicas de sus propios pacientes, y que un médico de guardia vea las de todos pero solo mientras dura la guardia. ¿Nos pasamos a ABAC o metemos más roles?""",
            },
            {
                "role": "assistant",
                "content": """Ni una cosa ni la otra en estado puro: **dejá los roles para decidir qué acciones existen y agregá reglas sobre el recurso** para decidir sobre qué datos. Es la combinación que usa casi todo sistema de salud, y las dos reglas que te piden son justo las que los roles solos no pueden expresar.

**Por qué no más roles.** «Médico de los pacientes X» no es un rol: es un rol más una relación con el dato. Si lo modelás como roles, terminás con un rol por médico, o con un rol `medico_guardia` que alguien tiene que asignar y quitar a mano cada turno, y que inevitablemente queda puesto. Los roles escalan por **tipo de usuario**, no por **relación con los datos**.

**Por qué no ABAC completo.** Un motor de políticas genérico (OPA, Cedar, Casbin con modelos ABAC) resuelve esto, pero a cambio de mover la lógica de autorización a un lenguaje aparte que el equipo tiene que aprender, testear y depurar. Para dos reglas no se justifica; para cuarenta, sí. Empezá con reglas en código y migrá a un motor cuando el número de reglas o la necesidad de que las administre alguien sin desplegar lo pida.

**Diseño concreto:**

1. **Roles para las acciones.** `medico` puede `historia:leer` y `historia:escribir`; `recepcion` puede `turno:crear`; `admin` todo. Esto ya lo tenés.
2. **Reglas de acceso al recurso**, en una sola función por recurso, que recibe el usuario, la acción y el recurso concreto:

```python
from datetime import datetime, timezone

def puede_acceder_historia(usuario: Usuario, accion: str, historia: Historia, ahora: datetime) -> bool:
    if not usuario.tiene_permiso(f"historia:{accion}"):
        return False
    if usuario.rol == "admin":
        return True
    if historia.paciente.medico_id == usuario.id:
        return True
    guardia = guardias.activa(usuario.id, ahora)
    return guardia is not None and guardia.clinica_id == historia.paciente.clinica_id
```

   La guardia es un **dato con inicio y fin** (`guardias(medico_id, clinica_id, desde, hasta)`), no un rol. Cuando termina, el acceso termina solo, sin que nadie se acuerde de quitar nada.

3. **Una sola puerta.** Toda lectura de historias pasa por esa función, incluidas las listas: el listado de historias **filtra** con la misma regla (`WHERE paciente.medico_id = :uid OR EXISTS (guardia activa)`), no trae todo y filtra después. Si la regla vive en dos lugares, en seis meses dicen cosas distintas.

4. **Registro de acceso.** En salud, el «quién vio qué y cuándo» suele ser obligación legal. Cada lectura de historia deja una fila `(usuario, historia, motivo, timestamp)`; el motivo para la guardia es el id de la guardia. Esto te sirve además para auditar la regla: si un médico ve historias que no son suyas fuera de guardia, el registro lo muestra.

**Acceso de emergencia («romper el vidrio»).** Te lo van a pedir en la siguiente reunión: un médico necesita ver una historia que no le corresponde porque el paciente llegó inconsciente. Modelalo explícito: el médico declara el motivo, obtiene acceso por 1 hora, y se genera una alerta para revisión. Es ABAC en su versión más útil, y con el diseño de arriba son diez líneas más.

**Cuándo sí migraría a un motor de políticas:** cuando haya más de tres o cuatro dimensiones (clínica, especialidad, convenio, consentimiento del paciente) que se combinen, o cuando las clínicas pidan configurar sus propias reglas sin que ustedes desplieguen. En ese momento, las reglas en código ya te dicen exactamente qué políticas escribir.

**Verificación:** tests por regla, con el reloj inyectado: médico ve su paciente; no ve el de otro; de guardia ve todos los de su clínica a las 03:00 de la guardia; a las 09:00, cuando terminó, no ve ninguno ajeno; y el admin ve todo. Cinco tests, un caso cada uno, y el reloj como parámetro para que no dependan de la hora real.""",
            },
        ]
    },
]

ROWS += [
    # 16) Multi-tenant: esquema compartido, esquema por cliente o base por cliente.
    {
        "messages": [
            {
                "role": "user",
                "content": """Estamos convirtiendo nuestro producto (gestión de inventario, Postgres, Django) en SaaS. Esperamos unos 500 clientes el primer año, la mayoría pequeños y dos o tres grandes. ¿Una base de datos por cliente, un esquema por cliente o todos en las mismas tablas con `tenant_id`?""",
            },
            {
                "role": "assistant",
                "content": """Tablas compartidas con `tenant_id` y **seguridad a nivel de fila** (RLS) en Postgres como red de seguridad. Deja la puerta abierta para sacar a los dos o tres grandes a su propia base de datos más adelante, pero no empieces por ahí.

**Por qué no una base por cliente.** Con 500 clientes son 500 bases: 500 migraciones por despliegue (y 500 posibilidades de que una falle a medias), 500 pools de conexiones, copias de seguridad y monitorización multiplicadas, y consultas globales («¿cuántos productos hay en total?», «¿qué clientes no han entrado en 30 días?») que exigen recorrer todo. Es el aislamiento máximo, y se paga en operación todos los días. Tiene sentido con decenas de clientes grandes que exigen contractualmente aislamiento físico, no con cientos de pequeños.

**Por qué no un esquema por cliente.** Parece el punto medio, pero hereda lo peor de ambos: sigues teniendo 500 migraciones (una por esquema), el *cache* de planes y el catálogo de Postgres crecen con 500 copias de cada tabla, y las herramientas (Django, `pg_dump`, ORMs) lo soportan a medias. Funciona hasta unos cientos de esquemas y luego degrada de maneras poco documentadas.

**Diseño con `tenant_id`:**

1. **`tenant_id` en todas las tablas de negocio**, `NOT NULL`, como primera columna de las claves e índices compuestos: `(tenant_id, sku)`, `(tenant_id, created_at)`. Las consultas de un cliente tocan solo su porción del índice.

2. **RLS como segunda barrera.** El error más probable en multi-tenant no es de diseño, es un `filter(tenant_id=...)` que alguien olvida en una consulta nueva. Con RLS, Postgres añade el filtro aunque el código no lo haga:

```sql
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE products FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON products
    USING (tenant_id = current_setting('app.tenant_id')::bigint);
```

   Y en Django, un *middleware* que fije la variable al inicio de cada petición: `SET LOCAL app.tenant_id = 42` dentro de la transacción (con `ATOMIC_REQUESTS = True`). La aplicación se conecta con un rol **sin** `BYPASSRLS`; las migraciones y las tareas administrativas, con otro.

3. **En el ORM, un `Manager` por defecto que filtre** por el *tenant* actual (en un `contextvar`), para que el código normal nunca escriba el filtro a mano y RLS quede como la red, no como el mecanismo.

4. **Claves externas que incluyan `tenant_id`** en las relaciones críticas (`FOREIGN KEY (tenant_id, product_id) REFERENCES products (tenant_id, id)`): impide que un pedido del cliente A referencie un producto del cliente B aunque el código lo intente.

**Para los dos o tres grandes**, el plan de salida sin cambiar el diseño:

- Un cliente grande que necesite aislamiento (contrato, rendimiento, región) se mueve a **su propia base de datos con el mismo esquema**; `tenant_id` sigue existiendo (con un solo valor). Django lo soporta con un *router* de bases de datos que elija la conexión por *tenant*. Las migraciones se aplican a N+1 bases, donde N son los grandes, que son pocos.
- Hasta que eso haga falta, el rendimiento de los grandes se protege con particionado de las tablas más grandes por `tenant_id` (`PARTITION BY LIST`), que mantiene un solo esquema y una sola migración.

**Lo que sí hay que decidir ahora** porque luego cuesta cambiarlo:

- Que **nada** identifique al *tenant* por el subdominio o la URL sin verificarlo contra la sesión del usuario. El *tenant* actual sale de la autenticación, nunca de la petición.
- Copias de seguridad: con base compartida, restaurar «solo el cliente 42» exige exportar sus filas (`COPY ... WHERE tenant_id = 42` por tabla) o un procedimiento de restauración a una base temporal. Escribe ese procedimiento y pruébalo antes de que lo pida un cliente.
- Límites por *tenant* (filas, peticiones por minuto, tamaño de adjuntos) desde el primer día: en base compartida, un cliente puede degradar a los demás, y el límite es lo que lo evita.

**Verificación:** un test que, con `app.tenant_id = 1`, intente leer y escribir filas del *tenant* 2 **sin pasar por el ORM** (SQL crudo) y compruebe que RLS devuelve cero filas y rechaza la inserción. Es el test que demuestra que la red de seguridad existe, y el que debe fallar si alguien conecta la app con un rol que salte RLS.""",
            },
        ]
    },
    # 17) Observabilidad: qué instrumentar en un servicio de pedidos.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Mi servicio de pedidos (Go, 3 réplicas, llama a inventario y a pagos, consume de Kafka) solo tiene logs en texto. Cuando algo falla tardamos horas en entender qué pasó. ¿Qué debería instrumentar y por dónde empiezo?""",
            },
            {
                "role": "assistant",
                "content": """Empieza por lo que convierte «horas» en «minutos»: un **identificador de correlación** que atraviese todo, logs estructurados que lo lleven y trazas distribuidas. Las métricas vienen después, y los paneles al final. En este orden, cada paso es útil por sí solo.

**1. Logs estructurados con contexto (primera semana).** Un log en texto obliga a buscar con `grep` y a adivinar qué líneas pertenecen a la misma petición. Un log JSON con campos fijos se filtra por `order_id` o `trace_id` y te da la historia completa en un segundo:

```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

// en cada petición o mensaje consumido
log := logger.With("trace_id", traceID, "order_id", order.ID, "tenant", order.TenantID)
log.Info("payment requested", "amount_minor", order.AmountMinor, "provider", "stripe")
log.Error("inventory reservation failed", "err", err, "sku", item.SKU, "attempt", attempt)
```

Reglas: un evento por línea, nivel correcto (`Error` solo para lo que alguien debe mirar), sin datos personales (correo, tarjeta), y **siempre** el `trace_id`. El `trace_id` llega en la cabecera `traceparent` (W3C) de la petición HTTP o en una cabecera del mensaje de Kafka; si no viene, lo creas en el borde y lo propagas en todas las llamadas salientes.

**2. Trazas distribuidas (segunda semana).** Con tres servicios y una cola, la pregunta «¿dónde se fueron los 4 segundos?» solo la responde una traza. OpenTelemetry para Go instrumenta `net/http`, gRPC y los clientes de Kafka con un *wrapper* cada uno; exporta a lo que uséis (Jaeger, Tempo, Honeycomb, Datadog):

```go
tp := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exporter), sdktrace.WithResource(res))
otel.SetTracerProvider(tp)
otel.SetTextMapPropagator(propagation.TraceContext{})

client := &http.Client{Transport: otelhttp.NewTransport(http.DefaultTransport)}
mux.Handle("/orders", otelhttp.NewHandler(handler, "create-order"))
```

Para Kafka, inyecta el contexto en las cabeceras al producir y extráelo al consumir; la librería `otelsarama` u `otelkafka` lo hace. Añade atributos de negocio al *span* (`order.id`, `payment.provider`): son lo que buscarás.

**3. Métricas (tercera semana): las cuatro señales por dependencia y por endpoint.** Latencia (histograma), tráfico, errores y saturación. Con OpenTelemetry o Prometheus:

- `http_server_request_duration_seconds{route, status}`: histograma, para percentiles.
- `dependency_request_duration_seconds{dependency="inventory"|"payments", status}`.
- `kafka_consumer_lag{topic, partition}`: la métrica que avisa de que te estás quedando atrás **antes** de que un cliente llame.
- `orders_created_total{tenant}`, `orders_failed_total{reason}`: las de negocio, pocas y con etiquetas de cardinalidad baja (nunca `order_id` como etiqueta).

**4. Alertas sobre síntomas, no sobre causas.** Dos o tres alertas que correspondan a lo que un cliente nota: tasa de errores de `POST /orders` > 2 % durante 5 minutos; p99 de latencia > 2 s durante 10 minutos; *lag* del consumidor > 10 000 mensajes. Una alerta por «CPU al 80 %» despierta a alguien sin que nadie esté sufriendo.

**5. Paneles, al final.** Uno por servicio con las cuatro señales y las dependencias; uno de negocio con pedidos por minuto y tasa de fallo por motivo. Los paneles que se hacen primero suelen mostrar lo que es fácil de medir, no lo que importa.

**Qué cambia en el próximo incidente.** Un cliente dice «el pedido 8f3 falló a las 10:42». Buscas `order_id=8f3` en los logs, sacas el `trace_id`, abres la traza y ves que inventario respondió en 20 ms, pagos tardó 3,9 s y devolvió 503, y el reintento llegó después del *timeout*. Cinco minutos. Y la métrica de `dependency_request_duration_seconds{dependency="payments"}` te dice si fue un pedido o todos.

**Coste honesto:** unos días de trabajo de instrumentación, un 2-5 % de CPU por el muestreo de trazas (muestrea al 10 % en producción, 100 % de las que tienen error), y disciplina para que cada log nuevo lleve los campos. La recompensa es el tiempo de resolución, que es lo que te está doliendo.""",
            },
        ]
    },
    # 18) SOLID aplicado: una clase con demasiadas responsabilidades (usuario trae código).
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala el problema concreto y propón el cambio mínimo que lo resuelve."},
            {
                "role": "user",
                "content": """Me han pedido que aplique SOLID a esta clase antes de añadirle «exportar a Excel». No quiero reescribirla entera. ¿Qué cambiarías y qué no?

```python
class ReportService:
    def __init__(self, db_url: str, smtp_host: str):
        self.engine = create_engine(db_url)
        self.smtp = smtplib.SMTP(smtp_host)

    def monthly_sales(self, month: str, email_to: str | None = None) -> bytes:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT day, total FROM sales WHERE month = :m"), {"m": month}).all()
        total = sum(r.total for r in rows)
        html = "<table>" + "".join(f"<tr><td>{r.day}</td><td>{r.total:.2f}</td></tr>" for r in rows) + f"<tr><td>Total</td><td>{total:.2f}</td></tr></table>"
        pdf = HTML(string=html).write_pdf()
        if email_to:
            msg = EmailMessage()
            msg["To"] = email_to
            msg["Subject"] = f"Ventas {month}"
            msg.add_attachment(pdf, maintype="application", subtype="pdf", filename="ventas.pdf")
            self.smtp.send_message(msg)
        return pdf
```""",
            },
            {
                "role": "assistant",
                "content": """El problema concreto: `monthly_sales` hace cuatro cosas (consultar, calcular, renderizar a PDF, enviar por correo) y la petición nueva («exportar a Excel») te obliga a abrir ese método y meter un `if formato == "xlsx"`. Es la violación de **responsabilidad única** que importa aquí, no por principio, sino porque es la que hace caro el cambio que te piden. Además el constructor crea sus propias dependencias (`create_engine`, `smtplib.SMTP`), lo que hace la clase imposible de probar sin base de datos ni servidor de correo.

**Lo que cambiaría (mínimo):** separar el **cálculo** del **formato** y del **envío**, e inyectar las dependencias. Tres piezas pequeñas y la clase original se reduce a orquestar.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class SalesReport:
    month: str
    rows: list[tuple[str, Decimal]]

    @property
    def total(self) -> Decimal:
        return sum((amount for _, amount in self.rows), Decimal(0))


class SalesRepository(Protocol):
    def daily_sales(self, month: str) -> list[tuple[str, Decimal]]: ...


class ReportRenderer(Protocol):
    extension: str
    def render(self, report: SalesReport) -> bytes: ...


class PdfRenderer:
    extension = "pdf"

    def render(self, report: SalesReport) -> bytes:
        rows = "".join(f"<tr><td>{day}</td><td>{amount:.2f}</td></tr>" for day, amount in report.rows)
        html = f"<table>{rows}<tr><td>Total</td><td>{report.total:.2f}</td></tr></table>"
        return HTML(string=html).write_pdf()


class XlsxRenderer:
    extension = "xlsx"

    def render(self, report: SalesReport) -> bytes:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Día", "Total"])
        for day, amount in report.rows:
            ws.append([day, float(amount)])
        ws.append(["Total", float(report.total)])
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()


class ReportService:
    def __init__(self, repository: SalesRepository, mailer: Mailer):
        self.repository = repository
        self.mailer = mailer

    def monthly_sales(self, month: str, renderer: ReportRenderer, email_to: str | None = None) -> bytes:
        report = SalesReport(month, self.repository.daily_sales(month))
        document = renderer.render(report)
        if email_to:
            self.mailer.send(to=email_to, subject=f"Ventas {month}", attachment=document, filename=f"ventas.{renderer.extension}")
        return document
```

Qué principio resuelve cada pieza, sin catecismo:

- `SalesReport` con `total` como propiedad: el cálculo deja de estar enterrado entre HTML. Ahora se prueba con una lista de tuplas, sin nada más.
- `ReportRenderer` como `Protocol`: añadir Excel es **añadir una clase**, no tocar `monthly_sales` (abierto/cerrado, y es la razón por la que te lo pidieron).
- `SalesRepository` y `Mailer` inyectados: la clase depende de abstracciones, los tests le pasan dobles, y producción le pasa `SqlSalesRepository(engine)` y `SmtpMailer(host)`. La composición ocurre en un solo lugar (el arranque de la app).
- `Decimal` en vez de `float` para dinero: no es SOLID, es corrección; aprovecho que toco la fila.

**Lo que no cambiaría:**

- No crearía una `ReportFactory`, un `ReportBuilder` ni un *bus* de eventos. Dos renderizadores y un método no lo justifican.
- No partiría `ReportService` en «servicio de aplicación» y «caso de uso». Es un método; cuando sean diez, ya se verá.
- No tocaría la firma pública más de lo necesario: quien llamaba `monthly_sales(month, email_to)` ahora pasa el renderizador; si hay muchos llamadores, un parámetro `renderer: ReportRenderer = PdfRenderer()` por defecto mantiene la compatibilidad.

**Verificación:** tres tests que antes eran imposibles. `SalesReport([("01", Decimal("10.50")), ("02", Decimal("4.50"))]).total == Decimal("15.00")`; `XlsxRenderer().render(report)` produce un libro cuya última fila es `["Total", 15.0]`; y `ReportService(repo_falso, mailer_falso).monthly_sales("2025-03", PdfRenderer(), email_to="a@b.c")` deja exactamente un envío en el `mailer_falso` con `filename="ventas.pdf"`. Ninguno necesita base de datos ni SMTP.""",
            },
        ]
    },
    # 19) Arquitectura limpia aplicada: dónde vive la validación.
    {
        "messages": [
            {
                "role": "user",
                "content": """En mi API con FastAPI tengo los modelos Pydantic de entrada, las entidades del dominio (dataclasses) y los modelos de SQLAlchemy. Me pierdo con dónde va cada validación: «el email tiene formato válido», «la fecha de fin es posterior a la de inicio», «el cliente no puede tener más de 5 proyectos activos». Ahora mismo hay comprobaciones repetidas en los tres sitios.""",
            },
            {
                "role": "assistant",
                "content": """Cada una de esas tres validaciones es de un tipo distinto, y el tipo decide dónde vive. La regla: **una validación vive en la capa más interna que tiene la información para decidirla, y en ninguna otra.**

**1. Forma de los datos → modelo de entrada (Pydantic).** «El email tiene formato válido», «la fecha es ISO 8601», «el nombre no está vacío», «el importe es positivo». Son propiedades del *payload*, no del negocio: un email mal formado no es un proyecto inválido, es una petición inválida (422). Pydantic lo hace con tipos:

```python
from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import date

class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner_email: EmailStr
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def ends_after_starts(self) -> "CreateProjectRequest":
        if self.ends_on <= self.starts_on:
            raise ValueError("ends_on must be after starts_on")
        return self
```

**2. Invariantes de la entidad → el dominio.** «La fecha de fin es posterior a la de inicio» aparece aquí también, y no es duplicación: en Pydantic protege la **API**; en el dominio protege la **entidad**, que puede construirse desde otros sitios (un *script* de importación, un consumidor de cola, un test). La entidad nunca debe poder existir en estado inválido:

```python
from dataclasses import dataclass

class DomainError(Exception):
    pass

@dataclass(frozen=True)
class Project:
    name: str
    owner_id: int
    starts_on: date
    ends_on: date

    def __post_init__(self) -> None:
        if self.ends_on <= self.starts_on:
            raise DomainError("a project must end after it starts")
```

Si te molesta la repetición de esa comprobación, acepta que es la **misma regla en dos contratos distintos**, con dos mensajes de error distintos (422 para el cliente de la API, excepción de dominio para el programador). Lo que no debes hacer es quitarla del dominio «porque Pydantic ya la comprueba».

**3. Reglas que necesitan estado externo → el caso de uso (servicio de aplicación).** «El cliente no puede tener más de 5 proyectos activos» no se puede decidir mirando un proyecto: necesita contar los demás. Vive en el caso de uso, que tiene acceso al repositorio, y se expresa con el lenguaje del dominio:

```python
MAX_ACTIVE_PROJECTS = 5

class CreateProject:
    def __init__(self, projects: ProjectRepository, customers: CustomerRepository):
        self.projects = projects
        self.customers = customers

    def execute(self, request: CreateProjectRequest) -> Project:
        owner = self.customers.by_email(request.owner_email)
        if owner is None:
            raise DomainError("unknown customer")
        if self.projects.count_active(owner.id) >= MAX_ACTIVE_PROJECTS:
            raise DomainError(f"customer already has {MAX_ACTIVE_PROJECTS} active projects")
        project = Project(request.name, owner.id, request.starts_on, request.ends_on)
        return self.projects.add(project)
```

Ojo con la concurrencia: dos peticiones simultáneas pueden pasar la comprobación con 4 proyectos y crear el 5.º y el 6.º. Si el límite es estricto, el repositorio lo refuerza con un bloqueo del cliente (`SELECT ... FOR UPDATE` sobre la fila del cliente dentro de la transacción) o con una restricción en la base de datos. La regla se **decide** en el caso de uso y se **garantiza** en el almacenamiento.

**4. Modelo de SQLAlchemy → ninguna validación de negocio.** Solo restricciones de integridad que la base de datos puede comprobar (`NOT NULL`, `UNIQUE`, `CHECK (ends_on > starts_on)`, claves externas). Son la última red, para datos que lleguen por caminos que no pasan por el dominio (migraciones, SQL a mano), no el lugar donde expresar reglas.

**El mapa que resuelve tu confusión:**

| Pregunta | Capa | Error que produce |
|---|---|---|
| ¿Está bien formada la petición? | Pydantic (borde) | 422 con campos |
| ¿Puede existir esta entidad así? | Dominio (`__post_init__`) | `DomainError` → 422 o 409 |
| ¿Puede ocurrir esta operación ahora, dado el resto del sistema? | Caso de uso | `DomainError` → 409 |
| ¿Es íntegro el almacenamiento? | Base de datos | `IntegrityError` → 500 (nunca debería llegar) |

Y un manejador de excepciones en FastAPI que traduzca `DomainError` a la respuesta HTTP, para que los casos de uso no sepan nada de códigos de estado.

**Verificación:** el test del dominio construye `Project` con fechas invertidas y espera `DomainError`, sin FastAPI ni base de datos. El del caso de uso usa un repositorio en memoria con 5 proyectos y espera el error del límite. El de la API manda un email inválido y espera 422. Si una regla solo se puede probar levantando toda la aplicación, está en la capa equivocada.""",
            },
        ]
    },
    # 20) Cuándo NO aplicar un patrón: repositorios sobre un ORM en un CRUD.
    {
        "messages": [
            {"role": "system", "content": "Responde en menos de 300 palabras, con una recomendación clara."},
            {
                "role": "user",
                "content": "Tengo una app de gestión interna (Django, 20 modelos, 2 desarrolladores, CRUD casi puro). En una revisión me han dicho que debería envolver el ORM en repositorios y casos de uso para «no acoplar el dominio a Django». ¿Lo hago?",
            },
            {
                "role": "assistant",
                "content": """No. En esa aplicación, el patrón de repositorio sobre el ORM de Django añade una capa que no abstrae nada.

**Por qué no aporta aquí:**

- El ORM de Django **ya es** el repositorio: `Proyecto.objects.filter(activo=True)` es la abstracción sobre SQL. Un `ProyectoRepository.activos()` que llame a esa línea es una indirección sin decisión dentro.
- «No acoplar el dominio a Django» protege de cambiar de framework o de base de datos. En 20 modelos CRUD con dos personas, ninguna de las dos va a ocurrir, y si ocurriera, el coste de reescribir 20 consultas es un día; el coste de mantener 20 repositorios con sus interfaces durante años es mucho mayor.
- Los casos de uso tienen sentido cuando una operación coordina varias entidades con reglas. En CRUD, el caso de uso es `form.save()`.

**Lo que sí haría con la misma energía:**

1. Lógica de negocio que exista (cálculos, transiciones de estado) en métodos del modelo o en funciones de un módulo `services.py` **por app**, probadas sin HTTP. Es la parte del consejo del revisor que vale: que la lógica no viva en las vistas.
2. `Manager`/`QuerySet` personalizados para las consultas con nombre (`Proyecto.objects.activos()`). Es el «repositorio» idiomático de Django.
3. Tests sobre los servicios y las consultas, no sobre capas de paso.

**Cuándo cambiaría de opinión:** si una operación tiene más de dos o tres reglas que coordinan modelos, si aparece una segunda fuente de datos (una API externa que se comporta como una tabla), o si el equipo crece y necesita fronteras entre apps. Entonces, repositorio **para ese caso**, no para los 20 modelos.

Responde al revisor con esto por escrito: la objeción es razonable en general y no aplica a este tamaño, y la decisión se revisa cuando aparezca alguno de esos tres detonantes.""",
            },
        ]
    },
    # 21) Estimación de capacidad con números: telemetría IoT (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Vamos a recibir telemetría de 50 000 dispositivos IoT; cada uno manda una lectura cada 10 segundos (temperatura, humedad y batería, unos 200 bytes en JSON). Producto quiere 13 meses de histórico y paneles por dispositivo. El equipo duda entre Postgres, que conocemos, o montar Kafka + Cassandra. ¿Cómo lo dimensionamos?""",
            },
            {
                "role": "assistant",
                "content": """Con números, antes de elegir tecnología. Asumo carga uniforme, picos de 3× (reconexiones tras un corte, cuando los dispositivos vacían su búfer local) y consultas casi siempre por dispositivo y rango de tiempo.

**1. Ritmo de escritura**

- Media: 50 000 / 10 s = **5 000 lecturas/s**.
- Pico: 3 × 5 000 = **15 000 lecturas/s**.
- Por día: 5 000 × 86 400 = **432 millones de filas**.

**2. Tamaño por fila en Postgres** (con columnas tipadas, no el JSON)

- `device_id int4`, `ts timestamptz` y tres `float4`: 24 bytes de datos, más relleno de alineación.
- Cabecera de tupla (24 bytes alineados) + puntero de línea (4 bytes): unos **60 bytes en la tabla**.
- Índice B-tree `(device_id, ts)`: unos **30 bytes por entrada**.
- Total: **≈ 90 bytes por lectura**. Los 200 bytes de JSON no se guardan tal cual.

**3. Volumen**

- Diario: 432 M × 90 B ≈ **39 GB/día**.
- 30 días: ≈ **1,2 TB**.
- 13 meses (≈ 395 días): 39 × 395 ≈ **15,4 TB**.

**4. Red y WAL**

- Carga útil: 5 000 × 200 B = 1 MB/s ≈ 8 Mbit/s; con HTTP y TLS, dos o tres veces más. Irrelevante.
- WAL: del mismo orden que los datos (algo más por las páginas completas tras cada *checkpoint*), ≈ 450 KB/s de media. Cualquier SSD lo absorbe.

**Qué dicen los números.** El ritmo de escritura (5 000-15 000 filas/s) está dentro de lo que hace un Postgres en una máquina mediana **si se escribe por lotes**. Lo que no encaja es guardar 15 TB de lecturas brutas en una base transaccional: copias de seguridad de días, `VACUUM` sobre tablas gigantes y restauraciones que nadie puede ensayar.

**Recomendación: Postgres, con dos decisiones que salen directamente de las cuentas.**

1. **Bruto 30 días, agregados 13 meses.** Un panel de 13 meses no pinta los ≈ 3,4 millones de puntos por dispositivo (8 640 al día × 395 días); pinta medias horarias o diarias.
   - Agregado horario por dispositivo (mínimo, máximo y media de cada métrica, ≈ 120 B por fila): 50 000 × 24 = 1,2 M filas/día → 144 MB/día → **≈ 57 GB en 13 meses**.
   - Bruto en particiones diarias (`PARTITION BY RANGE (ts)`): borrar un día es un `DROP TABLE` de su partición, instantáneo, en lugar de un `DELETE` de 432 M filas que deja la tabla llena de huecos.
   - Si hubiera obligación legal de conservar el bruto 13 meses, exportadlo cada día a almacenamiento de objetos en Parquet (columnar y comprimido); no en la base.
   - Si vuestro proveedor ofrece TimescaleDB, sus *hypertables*, compresión por columnas y agregados continuos hacen esto mismo con menos código propio. Con Postgres puro: particionado nativo y un trabajo programado que calcula el agregado de la hora anterior.

2. **Ingesta por lotes.** El servicio de ingesta acumula hasta 1 s o 1 000 lecturas y las escribe con `COPY` (o un `INSERT` multifila). 15 000 filas/s pasan a ser 15 transacciones por segundo. El dispositivo recibe el ACK solo después del `COMMIT`; si la ingesta cae, la lectura sigue en su búfer y la reenvía. Con eso no hace falta una cola intermedia para no perder datos.

**Por qué no Kafka + Cassandra hoy.** 1 MB/s no justifica operar dos sistemas distribuidos que el equipo no conoce. Kafka tendría sentido si varios consumidores independientes necesitaran releer el flujo (alertas en tiempo real, un *data lake*, facturación); Cassandra, si el bruto de 13 meses tuviera que consultarse en línea. Ninguna de las dos condiciones está en los requisitos.

**Verificación antes de comprometeros.** Una prueba de carga de una hora a 15 000 lecturas/s con datos sintéticos. Medid el crecimiento real con `pg_total_relation_size` sobre la partición del día: la estimación es 15 000 × 3 600 × 90 B ≈ 4,9 GB por hora. Si la realidad se desvía más de un 50 %, rehaced las cuentas con el tamaño medido antes de decidir nada más.""",
            },
            {
                "role": "user",
                "content": "¿Y si producto decide que los dispositivos manden cada segundo en vez de cada 10?",
            },
            {
                "role": "assistant",
                "content": """Todo lo que depende del ritmo se multiplica por 10; lo que depende de dispositivos y horas, no.

| | Cada 10 s | Cada 1 s |
|---|---|---|
| Escrituras medias | 5 000/s | 50 000/s |
| Pico (3×) | 15 000/s | 150 000/s |
| Bruto por día | 39 GB | ≈ 389 GB (4 320 M filas × 90 B) |
| Bruto 30 días | 1,2 TB | ≈ 11,7 TB |
| Agregados horarios 13 meses | ≈ 57 GB | ≈ 57 GB: sigue siendo una fila por dispositivo y hora |
| Red | 1 MB/s | 10 MB/s |

Aquí sí cambia la recomendación, y conviene decir exactamente dónde: 150 000 filas/s en pico con `COPY` por lotes es alcanzable en un Postgres potente, pero **11,7 TB de bruto caliente en una sola instancia ya no** es razonable de operar.

Opciones, de menos a más cambio:

1. **Retener menos bruto.** 3 días de bruto (≈ 1,2 TB) y agregados por minuto durante 30 días: 50 000 × 1 440 = 72 M filas/día × 120 B ≈ 8,6 GB/día, unos 260 GB en 30 días. Antes de cualquier tecnología, preguntad a producto qué consulta necesita resolución de 1 s más allá de unos días. Casi siempre la respuesta es «ninguna», y esa conversación vale más que cualquier base de datos.
2. **Compresión columnar** (TimescaleDB o un almacén columnar). Las series de sensores, con valores parecidos y marcas de tiempo regulares, se comprimen muy bien, a menudo un orden de magnitud; medidlo con vuestros datos antes de contar con ello.
3. **Agregar en el borde.** Que el dispositivo muestree cada segundo pero envíe cada 10 s un resumen (mínimo, máximo, media) y, aparte, los valores anómalos. Reduce red, ingesta y almacenamiento a la vez, y suele ser lo que producto quería de verdad: no perderse los picos.

Solo si producto confirma que necesita el bruto a 1 s, consultable en línea y durante meses, entra en juego una base de series temporales distribuida o un almacén columnar dedicado. Y entonces Kafka delante sí empieza a tener sentido: 150 000 mensajes/s en pico con varios consumidores es su terreno.

La verificación es la misma prueba de carga, ahora a 150 000/s. Si el `COPY` no sostiene ese ritmo con margen en una instancia del tamaño que estáis dispuestos a pagar, la opción 3 deja de ser opcional.""",
            },
        ]
    },
    # 22) Revisión de un diseño del usuario señalando riesgos (multiturno, system de revisor).
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de arquitectura. Ordena los riesgos por gravedad y propón la mitigación más barata para cada uno."},
            {
                "role": "user",
                "content": """Revisa nuestro diseño para un sistema de citas médicas antes de empezar a programarlo:

- Frontend → API en Node (3 réplicas en Kubernetes) → guarda la cita en Postgres.
- Después de guardar, la API publica `cita.creada` en Redis Pub/Sub.
- Un servicio de notificaciones (3 réplicas) escucha y manda SMS y correo de confirmación.
- Un servicio de recordatorios (3 réplicas) escucha el mismo evento y hace un `setTimeout` en memoria para mandar un SMS 24 h antes de la cita.

Las citas se pueden reservar con hasta 3 meses de antelación.""",
            },
            {
                "role": "assistant",
                "content": r"""Seis riesgos, de más a menos grave. Los tres primeros harán que el sistema falle desde el primer día, no «bajo carga».

**1. Recordatorios con `setTimeout` (crítico: falla siempre).**

- **Se pierden en cada despliegue, reinicio o reescalado.** Un `setTimeout` vive en la memoria del proceso. Con despliegues semanales, casi ninguna cita reservada con más de una semana de antelación recibe su recordatorio.
- **Desbordamiento.** Node guarda el retardo en un entero de 32 bits con signo: el máximo es 2 147 483 647 ms, unos **24,8 días**. Con un retardo mayor, Node emite un `TimeoutOverflowWarning` y **fija el retardo en 1 ms**: una cita a tres meses dispara su «recordatorio» en el momento de reservarla.
- **Triplicados.** Las 3 réplicas reciben el evento y cada una programa su temporizador: tres SMS por cita.

Mitigación: una tabla `reminders (appointment_id, send_at, sent_at)` que se escribe **en la misma transacción** que la cita, y un *worker* que cada minuto toma lo pendiente:

```sql
SELECT id, appointment_id FROM reminders
 WHERE send_at <= now() AND sent_at IS NULL
 ORDER BY send_at
 LIMIT 100
 FOR UPDATE SKIP LOCKED;
```

`SKIP LOCKED` deja que varias réplicas trabajen sin pisarse. Antes de enviar, relee la cita: si se canceló o se movió, no envíes.

**2. Redis Pub/Sub para eventos que importan (alto).**

- Pub/Sub es «disparar y olvidar»: si en ese instante no hay suscriptor conectado (un despliegue del servicio de notificaciones, una reconexión), el mensaje se pierde sin rastro.
- Entrega a **todos** los suscriptores: con 3 réplicas de notificaciones, tres SMS de confirmación por cita. Es el mismo error del punto 1, por la misma causa.

Mitigación: una cola con grupos de consumidores, donde cada mensaje lo procesa **una** réplica y se confirma al terminar. Ya tenéis Redis, así que lo más barato es **Redis Streams**: `XREADGROUP` para leer, `XACK` al terminar y `XAUTOCLAIM` para recuperar lo que dejó a medias una réplica caída.

**3. Doble escritura sin atomicidad (alto).** «Guardar en Postgres y después publicar» pierde el evento si el proceso muere entre las dos operaciones: cita creada y paciente sin confirmación. Mitigación: patrón *outbox*. El evento se inserta en una tabla `outbox` en la misma transacción que la cita, y un proceso aparte lo publica en el *stream*. Es el mismo mecanismo que la tabla de recordatorios: una vez montado uno, el otro es casi gratis.

**4. Doble reserva del mismo hueco (alto, y el más caro de explicarle a un paciente).** El diseño no dice cómo se impide que dos pacientes reserven al mismo médico a la misma hora con peticiones simultáneas. «¿Está libre?» seguido de un `INSERT` tiene una carrera. Que lo garantice la base de datos. Con huecos fijos basta `UNIQUE (doctor_id, starts_at)`; con duraciones variables, una restricción de exclusión sobre rangos:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE appointments ADD CONSTRAINT no_overlap
  EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at) WITH &&)
  WHERE (status <> 'cancelled');
```

**5. Zonas horarias (medio).** «A las 10:00» y «24 h antes» dependen de la zona de la clínica, con cambios de horario incluidos. Mitigación: `starts_at timestamptz`, la zona IANA de la clínica guardada (`Europe/Madrid`, `America/Bogota`) y el texto del SMS formateado en esa zona. Decidid además qué significa «24 h antes» la noche de un cambio de hora: `starts_at - interval '24 hours'` sobre `timestamptz` son 24 horas exactas, que no es lo mismo que «el día anterior a la misma hora».

**6. Envío duplicado ocasional (medio-bajo).** Incluso con todo lo anterior, un *worker* puede caerse tras enviar el SMS y antes de marcar `sent_at`. Usad una clave de idempotencia por `(appointment_id, tipo)` si el proveedor de SMS la admite; si no, aceptad «al menos una vez». La diferencia con el diseño actual es que el duplicado pasa a ser **raro**, no sistemático.

Ninguna mitigación añade infraestructura: todo es Postgres y el Redis que ya tenéis.

**Pruebas que confirman las mitigaciones:** crear una cita a 90 días y comprobar que no sale ningún SMS en el momento (el desbordamiento); lanzar 20 reservas simultáneas al mismo hueco y esperar exactamente una aceptada; y en un entorno con 3 réplicas de cada servicio, contar los SMS que llegan por cita: uno.""",
            },
            {
                "role": "user",
                "content": "Lo del setTimeout duele. Pero ¿no es más simple una cola con mensajes retrasados que una tabla con un worker que consulta cada minuto?",
            },
            {
                "role": "assistant",
                "content": """Parece más simple hasta que una cita se mueve o se cancela, y en citas médicas eso pasa todos los días. Por eso me quedo con la tabla.

| | Tabla + *worker* | Cola con mensajes retrasados |
|---|---|---|
| Cancelar o mover la cita | Un `UPDATE` o `DELETE` del recordatorio en la misma transacción que la cita | Localizar y borrar el mensaje en la cola, o dejarlo y filtrarlo al llegar |
| Retardos de meses | Sin límite | Depende del sistema: SQS admite como máximo 15 minutos de retardo por mensaje; RabbitMQ necesita un *plugin* o trucos con TTL y colas de mensajes muertos; BullMQ sobre Redis sí admite retardos largos |
| Ver qué hay pendiente | Un `SELECT` | Las herramientas de cada cola, si existen |
| Atomicidad con la cita | Misma transacción | Vuelve la doble escritura (riesgo 3) |
| Coste | Una consulta por minuto | Otra pieza con su propia semántica |

La consulta de cada minuto es barata con un índice parcial: `CREATE INDEX ON reminders (send_at) WHERE sent_at IS NULL` solo contiene lo pendiente, así que no crece con el histórico. Y la granularidad de un minuto significa que un recordatorio de 24 h puede salir con hasta 59 s de retraso, que no importa a nadie.

Cuándo sí elegiría una cola con retardo: millones de temporizadores cortos (segundos o minutos) donde un sondeo por minuto se queda corto, o un sistema sin base relacional a mano. Si aun así os decantáis por BullMQ, tres reglas: `jobId` derivado de la cita y del tipo (`reminder:${appointmentId}`) para que reprogramar no duplique, borrar el trabajo al cancelar, y **releer la cita en el momento de enviar**. Esa última comprobación hace falta en cualquier diseño, porque es la única que es correcta siempre.

**Prueba que decide la discusión:** crear una cita, moverla dos días más tarde, avanzar el reloj y ejecutar el *worker*. Debe salir un SMS a la hora nueva y ninguno a la vieja. Con la tabla es un `UPDATE` en la transacción de «mover cita»; con la cola es justo el test que suele fallar.""",
            },
        ]
    },
    # 23) Plan de migración por fases: MySQL 5.7 a PostgreSQL 16 con parada mínima (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Tenemos que salir de MySQL 5.7 (ya sin soporte) y dirección quiere aprovechar para pasar a PostgreSQL 16. Es una app Laravel con unos 400 GB y 120 tablas, y el negocio acepta como mucho 15 minutos de parada, un domingo de madrugada. ¿Cómo planteamos la migración?""",
            },
            {
                "role": "assistant",
                "content": """En fases, con el punto de no retorno lo más tarde posible y la vuelta atrás ensayada. Los 15 minutos de parada solo cubren el corte final: todo lo demás se hace con el sistema en marcha, gracias a replicación continua (CDC) de MySQL a Postgres.

**Fase 0. Inventario (1-2 semanas).** Lo que rompe una migración de MySQL a Postgres casi nunca son los datos: es el SQL que dependía de comportamientos de MySQL.

- Fechas cero (`0000-00-00`), que Postgres rechaza: buscarlas y decidir (`NULL` o una fecha real).
- Comparaciones insensibles a mayúsculas por la *collation*: `WHERE email = 'Ana@X.com'` encuentra `ana@x.com` en MySQL y no en Postgres. Solución: `citext` o `lower()` con índice.
- `GROUP BY` permisivo, conversiones implícitas (`WHERE id = '12abc'`), `ON DUPLICATE KEY UPDATE` frente a `ON CONFLICT`, `tinyint(1)` como booleano, `utf8` de 3 bytes.
- SQL crudo en el código: buscar `DB::raw`, `DB::select` y `whereRaw`. El *query builder* de Eloquent traduce el resto.

**Fase 1. La aplicación habla Postgres (2-4 semanas).** CI ejecuta la suite contra Postgres 16 además de contra MySQL, y se corrigen las diferencias con código que funcione en **los dos** motores, porque producción sigue en MySQL durante semanas. Es la fase más larga y la que más riesgo elimina.

**Fase 2. Esquema y carga inicial.** `pgloader` da un buen primer borrador del esquema (tipos, índices, claves) que hay que revisar a mano, y hace la carga inicial de los 400 GB. Desde aquí, las migraciones de Laravel generan el esquema de Postgres.

**Fase 3. Replicación continua.** CDC desde el *binlog* de MySQL hacia Postgres: Debezium (conector de MySQL y *sink* JDBC) o AWS DMS si estáis en AWS. Requisitos en MySQL: `binlog_format=ROW` y `binlog_row_image=FULL`. A partir de aquí, Postgres va unos segundos por detrás de MySQL de forma permanente.

**Fase 4. Validación con datos reales (1-2 semanas).**

- Recuentos por tabla y sumas de control por bloques de id (por ejemplo, el `md5` de las columnas clave concatenadas en orden, por bloques de 100 000 ids) en los dos lados, cada noche.
- **Lecturas en sombra**: un porcentaje de las consultas de lectura se ejecuta también contra Postgres y se comparan resultados y tiempos. Las diferencias se registran; al usuario se le sigue sirviendo MySQL.
- Ensayo completo del corte en *staging* con una copia de producción, cronometrado.

**Fase 5. Corte (domingo, 15 minutos como máximo).**

1. Modo mantenimiento (`php artisan down`): no entra ninguna escritura.
2. Esperar a que el retraso de la replicación sea cero y verificar recuentos de las tablas más activas.
3. **Reajustar las secuencias.** La replicación copia filas, no el estado del `AUTO_INCREMENT`. Para cada tabla con id autoincremental: `SELECT setval(pg_get_serial_sequence('orders', 'id'), (SELECT max(id) FROM orders));`. Olvidarlo es el fallo clásico: el primer `INSERT` del lunes choca con una clave duplicada.
4. Cambiar la conexión (`DB_CONNECTION=pgsql`) y desplegar.
5. Pruebas de humo (*login*, crear pedido, pagar) y `php artisan up`.

**Fase 6. Red de seguridad (2-4 semanas).** MySQL queda intacto y en solo lectura. Volver atrás **en las primeras horas** es apuntar de nuevo a MySQL si no ha entrado ninguna escritura relevante. Después, o tenéis replicación inversa (Postgres → MySQL) o la vuelta atrás exige reconciliar a mano. Decidid **antes** del corte cuál de las dos tenéis: sin replicación inversa, el punto de no retorno real es el `artisan up`, y todo el equipo debe saberlo.

**Criterios para avanzar:** no se sale de la fase 1 sin la suite completa en verde contra Postgres; no se pasa al corte sin una semana de lecturas en sombra sin diferencias inexplicadas y un ensayo cronometrado por debajo de 10 minutos, que deja margen sobre los 15.""",
            },
            {
                "role": "user",
                "content": "¿Y no podemos hacer doble escritura desde la aplicación (escribir en MySQL y en Postgres a la vez) en vez de CDC? Nos parece más controlable que meter Debezium.",
            },
            {
                "role": "assistant",
                "content": """Para esto, no. Escribir en dos bases desde la aplicación no es atómico: si la escritura en MySQL funciona y la de Postgres falla, o el proceso muere entre las dos, las bases divergen y nada lo detecta. Con 120 tablas y semanas de convivencia, habrá divergencias; la cuestión es si os enteráis.

Tres problemas concretos:

1. **Fallos parciales.** Para cubrirlos necesitáis reintentos, una cola de escrituras fallidas y un proceso de reconciliación. Habréis construido un CDC a mano, y peor.
2. **Orden.** Dos peticiones concurrentes que actualizan la misma fila pueden aplicarse en MySQL en un orden y en Postgres en el contrario. El *binlog* registra el orden real de los *commits*; la aplicación no lo conoce.
3. **Cobertura.** La doble escritura solo ve lo que pasa por el código instrumentado. Los comandos de `artisan`, los *jobs*, los *triggers*, los scripts de soporte y cualquier `UPDATE` a mano se escapan. El *binlog* los ve todos.

Lo que sí os da el control que buscáis es **CDC con verificación**: los recuentos y sumas de control de la fase 4 ejecutándose cada noche durante toda la convivencia, con una alerta si algo difiere. Eso responde a la pregunta que de verdad os preocupa («¿coinciden las dos bases?») sin los fallos de la doble escritura.

Si Debezium os parece demasiada pieza (necesita Kafka Connect y un *broker*), mirad la opción gestionada de vuestra nube, como AWS DMS, que replica MySQL a Postgres con carga inicial y cambios continuos. La doble escritura solo la consideraría para una tabla pequeña, aislada y con un único punto de escritura, y aun así con la reconciliación nocturna.""",
            },
        ]
    },
    # 24) Refactor de un módulo dado: webhooks de Stripe en Express (código del usuario).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Me toca mantener este módulo y antes de añadir más eventos quiero refactorizarlo. ¿Por dónde empiezo y cómo lo dejarías?

```ts
// webhooks.ts
import express from "express";
import Stripe from "stripe";
import { db } from "./db";
import { sendEmail } from "./email";

const stripe = new Stripe(process.env.STRIPE_KEY!);
let processed: string[] = [];

export const router = express.Router();

router.post("/stripe", express.raw({ type: "application/json" }), async (req, res) => {
  let event;
  try {
    event = stripe.webhooks.constructEvent(req.body, req.headers["stripe-signature"] as string, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch (e) {
    return res.status(400).send("bad signature");
  }
  if (processed.includes(event.id)) return res.sendStatus(200);
  processed.push(event.id);

  if (event.type === "checkout.session.completed") {
    const s = event.data.object as any;
    await db.query("UPDATE accounts SET plan = $1, status = 'active' WHERE stripe_customer = $2", [s.metadata.plan, s.customer]);
    const acc = await db.query("SELECT email FROM accounts WHERE stripe_customer = $1", [s.customer]);
    await sendEmail(acc.rows[0].email, "Bienvenido", "Tu plan está activo");
  } else if (event.type === "invoice.payment_failed") {
    const inv = event.data.object as any;
    await db.query("UPDATE accounts SET status = 'past_due' WHERE stripe_customer = $1", [inv.customer]);
    const acc = await db.query("SELECT email FROM accounts WHERE stripe_customer = $1", [inv.customer]);
    await sendEmail(acc.rows[0].email, "Pago fallido", "Revisa tu tarjeta");
  } else if (event.type === "customer.subscription.deleted") {
    const sub = event.data.object as any;
    await db.query("UPDATE accounts SET status = 'canceled', plan = NULL WHERE stripe_customer = $1", [sub.customer]);
  }
  res.sendStatus(200);
});
```""",
            },
            {
                "role": "assistant",
                "content": r"""Antes del refactor hay un **bug que pierde eventos**, y conviene arreglarlo por separado para que no quede escondido entre cambios de estructura.

**El bug.** `processed.push(event.id)` ocurre **antes** de procesar. Si la consulta o el correo lanzan una excepción, Express 4 no captura el rechazo de un *handler* `async`: la petición se queda colgada, Stripe agota el tiempo y reintenta, y el reintento encuentra el id en `processed` y responde 200. El evento se pierde para siempre: un cliente que pagó se queda sin plan. Además, `processed` vive en memoria: se vacía en cada reinicio, no se comparte entre instancias y crece sin límite.

**Orden de trabajo, un *commit* por paso:**

1. **Tests de caracterización** del comportamiento actual (los tres eventos y la firma inválida), para que el refactor tenga red.
2. **Arreglo del bug**: idempotencia persistente y transaccional, con su test de regresión.
3. **Refactor**: inyectar dependencias, un *handler* por tipo de evento, sacar el correo fuera de la transacción. Sin cambiar comportamiento.

Tabla para la idempotencia:

```sql
CREATE TABLE stripe_events (
  id           text PRIMARY KEY,
  processed_at timestamptz NOT NULL DEFAULT now()
);
```

Módulo resultante:

```ts
// stripe-webhooks.ts
import express, { type Router } from "express";
import type Stripe from "stripe";
import type { Pool, PoolClient } from "pg";

export type Notification = { customerId: string; template: "welcome" | "payment_failed" };
export type Notifier = (notification: Notification) => Promise<void>;
type Handler = (event: Stripe.Event, tx: PoolClient) => Promise<Notification[]>;

function customerIdOf(customer: string | { id: string } | null): string {
  if (customer === null) throw new Error("event without customer");
  return typeof customer === "string" ? customer : customer.id;
}

const handlers: Record<string, Handler | undefined> = {
  "checkout.session.completed": async (event, tx) => {
    const session = event.data.object as Stripe.Checkout.Session;
    const customerId = customerIdOf(session.customer);
    await tx.query("UPDATE accounts SET plan = $1, status = 'active' WHERE stripe_customer = $2", [session.metadata?.plan ?? null, customerId]);
    return [{ customerId, template: "welcome" }];
  },
  "invoice.payment_failed": async (event, tx) => {
    const invoice = event.data.object as Stripe.Invoice;
    const customerId = customerIdOf(invoice.customer);
    await tx.query("UPDATE accounts SET status = 'past_due' WHERE stripe_customer = $1", [customerId]);
    return [{ customerId, template: "payment_failed" }];
  },
  "customer.subscription.deleted": async (event, tx) => {
    const subscription = event.data.object as Stripe.Subscription;
    await tx.query("UPDATE accounts SET status = 'canceled', plan = NULL WHERE stripe_customer = $1", [customerIdOf(subscription.customer)]);
    return [];
  },
};

export async function processEvent(event: Stripe.Event, pool: Pool, notify: Notifier): Promise<void> {
  const handler = handlers[event.type];
  if (handler === undefined) return; // eventos que no nos interesan: 200 sin hacer nada

  const client = await pool.connect();
  let notifications: Notification[] = [];
  try {
    await client.query("BEGIN");
    const inserted = await client.query("INSERT INTO stripe_events (id) VALUES ($1) ON CONFLICT (id) DO NOTHING", [event.id]);
    if (inserted.rowCount === 0) {
      await client.query("ROLLBACK"); // ya procesado
      return;
    }
    notifications = await handler(event, client);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }

  for (const notification of notifications) {
    await notify(notification); // después del COMMIT: un correo fallido no deshace el cambio de plan
  }
}

export function stripeWebhookRouter(deps: { stripe: Stripe; webhookSecret: string; pool: Pool; notify: Notifier }): Router {
  const router = express.Router();
  router.post("/stripe", express.raw({ type: "application/json" }), async (req, res, next) => {
    let event: Stripe.Event;
    try {
      event = deps.stripe.webhooks.constructEvent(req.body, req.get("stripe-signature") ?? "", deps.webhookSecret);
    } catch {
      res.status(400).send("invalid signature");
      return;
    }
    try {
      await processEvent(event, deps.pool, deps.notify);
      res.sendStatus(200);
    } catch (error) {
      next(error); // 500: Stripe reintentará y, como el evento no quedó registrado, se reprocesa
    }
  });
  return router;
}
```

Y la composición, en el arranque de la aplicación, que es lo único que conoce las variables de entorno y el correo:

```ts
const TEMPLATES = {
  welcome: { subject: "Bienvenido", body: "Tu plan está activo" },
  payment_failed: { subject: "Pago fallido", body: "Revisa tu tarjeta" },
} as const;

const notify: Notifier = async ({ customerId, template }) => {
  const { rows } = await pool.query("SELECT email FROM accounts WHERE stripe_customer = $1", [customerId]);
  if (rows.length === 0) return;
  await sendEmail(rows[0].email, TEMPLATES[template].subject, TEMPLATES[template].body);
};

app.use("/webhooks", stripeWebhookRouter({ stripe, webhookSecret: env.STRIPE_WEBHOOK_SECRET, pool, notify }));
```

Qué resuelve cada cambio:

- **Idempotencia en la misma transacción que el efecto.** El evento solo queda registrado si el `UPDATE` se confirmó. Dos entregas simultáneas del mismo evento se serializan en la clave primaria: la segunda espera al `COMMIT` de la primera y luego no inserta nada. Sirve con cualquier número de instancias.
- **Un *handler* por evento en un mapa.** Añadir un evento es añadir una entrada, sin tocar el flujo común. La consulta del correo y el envío, que estaban copiados en dos ramas, viven en un único `notify`.
- **Dependencias inyectadas** (`stripe`, secreto, `pool`, `notify`): el módulo ya no lee `process.env` al importarse y se prueba sin red ni correo.
- **Errores visibles.** Un fallo produce un 500 y Stripe reintenta (lo hace durante días, con espera creciente). Antes, un fallo producía una petición colgada y un evento perdido.
- **Correo fuera de la transacción.** Si falla, el plan ya está activo y solo se pierde el correo. Si ese correo tiene que llegar sí o sí, el siguiente paso es guardar la notificación en una tabla *outbox* dentro de la misma transacción y enviarla desde un proceso aparte.

Test de regresión del bug, con Vitest, Supertest y un Postgres de prueba (`pool`); el SDK de Stripe firma el *payload* con `generateTestHeaderString`:

```ts
import express from "express";
import request from "supertest";
import Stripe from "stripe";
import type { Pool } from "pg";
import { expect, it, vi } from "vitest";
import { stripeWebhookRouter } from "./stripe-webhooks";

const stripe = new Stripe("sk_test_dummy");
const webhookSecret = "whsec_test";

it("si el primer intento falla, el reintento de Stripe sí se procesa", async () => {
  const flakyPool = {
    connect: vi.fn().mockRejectedValueOnce(new Error("db down")).mockImplementation(() => pool.connect()),
  } as unknown as Pool;
  const notify = vi.fn(async () => {});
  const app = express().use(stripeWebhookRouter({ stripe, webhookSecret, pool: flakyPool, notify }));

  const payload = JSON.stringify({
    id: "evt_retry", object: "event", type: "invoice.payment_failed",
    data: { object: { object: "invoice", customer: "cus_1" } },
  });
  const send = () =>
    request(app)
      .post("/stripe")
      .set("content-type", "application/json")
      .set("stripe-signature", stripe.webhooks.generateTestHeaderString({ payload, secret: webhookSecret }))
      .send(payload);

  await send().expect(500);
  await send().expect(200);
  expect(notify).toHaveBeenCalledTimes(1);
});
```

Con el código original, la segunda entrega respondería 200 sin procesar nada y `notify` no se llamaría nunca: ese es el test que tiene que fallar antes del arreglo y pasar después.""",
            },
        ]
    },
    # 25) Subida de archivos grandes con URLs prefirmadas y multipart (usuario en inglés).
    {
        "messages": [
            {
                "role": "user",
                "content": """Users upload videos of up to 5 GB through our Node API, which streams them to S3. The API pods keep running out of memory, and uploads on flaky mobile connections fail at 90% and start over. What's the right design?""",
            },
            {
                "role": "assistant",
                "content": r"""Take the bytes out of your API. The browser uploads **directly to S3** with presigned URLs, using **multipart upload** so each part can be retried on its own. Your API only authorizes the upload, hands out URLs, and records the result. Memory on the pods stops depending on file size, and a dropped connection costs one part, not the whole file.

**Flow**

1. Client → API: "I want to upload 4.2 GB, `video/mp4`." The API validates size and type, creates the multipart upload, generates a server-side key and returns one presigned URL per part.
2. Client → S3: `PUT` each part (in parallel, retrying failed parts) and reads the `ETag` of each response.
3. Client → API: "done, here are the part numbers and ETags." The API verifies the upload belongs to this user and completes it.
4. S3 → queue → worker: an `ObjectCreated` notification triggers processing (inspect the real file type, transcode, thumbnail). The video becomes visible only after that.

**Server side** (AWS SDK v3):

```ts
import {
  S3Client,
  CreateMultipartUploadCommand,
  UploadPartCommand,
  CompleteMultipartUploadCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { randomUUID } from "node:crypto";

const s3 = new S3Client({});
const BUCKET = process.env.UPLOAD_BUCKET ?? "";
const PART_SIZE = 64 * 1024 * 1024;         // 64 MiB: 80 parts for 5 GiB
const MAX_SIZE = 5 * 1024 * 1024 * 1024;    // 5 GiB
const URL_TTL_SECONDS = 3600;

export class UploadError extends Error {}

export interface UploadStore {
  insert(record: { key: string; uploadId: string; userId: string; sizeBytes: number }): Promise<void>;
  findPending(key: string, userId: string): Promise<{ uploadId: string } | null>;
  markUploaded(key: string): Promise<void>;
}

export async function startUpload(store: UploadStore, userId: string, sizeBytes: number, contentType: string) {
  if (!Number.isInteger(sizeBytes) || sizeBytes <= 0 || sizeBytes > MAX_SIZE) throw new UploadError("invalid size");
  if (!contentType.startsWith("video/")) throw new UploadError("unsupported content type");

  const key = `uploads/${userId}/${randomUUID()}`;
  const { UploadId } = await s3.send(new CreateMultipartUploadCommand({ Bucket: BUCKET, Key: key, ContentType: contentType }));
  if (!UploadId) throw new Error("S3 did not return an UploadId");

  const partCount = Math.ceil(sizeBytes / PART_SIZE);
  const partUrls = await Promise.all(
    Array.from({ length: partCount }, (_, index) =>
      getSignedUrl(s3, new UploadPartCommand({ Bucket: BUCKET, Key: key, UploadId, PartNumber: index + 1 }), {
        expiresIn: URL_TTL_SECONDS,
      }),
    ),
  );
  await store.insert({ key, uploadId: UploadId, userId, sizeBytes });
  return { key, partSize: PART_SIZE, partUrls };
}

export async function completeUpload(
  store: UploadStore,
  userId: string,
  key: string,
  parts: { partNumber: number; etag: string }[],
) {
  const pending = await store.findPending(key, userId);
  if (pending === null) throw new UploadError("unknown upload");
  await s3.send(
    new CompleteMultipartUploadCommand({
      Bucket: BUCKET,
      Key: key,
      UploadId: pending.uploadId,
      MultipartUpload: {
        Parts: [...parts]
          .sort((a, b) => a.partNumber - b.partNumber)
          .map((part) => ({ PartNumber: part.partNumber, ETag: part.etag })),
      },
    }),
  );
  await store.markUploaded(key);
}
```

**Client side**, sequential for clarity:

```ts
async function uploadParts(file: File, start: { partSize: number; partUrls: string[] }) {
  const parts: { partNumber: number; etag: string }[] = [];
  for (let index = 0; index < start.partUrls.length; index++) {
    const blob = file.slice(index * start.partSize, (index + 1) * start.partSize);
    const response = await fetch(start.partUrls[index], { method: "PUT", body: blob });
    if (!response.ok) throw new Error(`part ${index + 1} failed with ${response.status}`);
    parts.push({ partNumber: index + 1, etag: response.headers.get("ETag") ?? "" });
  }
  return parts;
}
```

In production, run 3-4 parts in parallel and retry each failed part a few times with backoff; that is what fixes the "fails at 90% and starts over" problem.

**Details that bite if you skip them**

- **CORS must expose `ETag`.** The browser cannot read the header otherwise, and completion fails. The bucket CORS rule needs `AllowedMethods: ["PUT"]`, your origin, and `ExposeHeaders: ["ETag"]`.
- **S3 limits.** Parts must be at least 5 MiB (except the last), at most 10,000 parts per upload. At 64 MiB, 5 GiB is 80 parts. A single non-multipart `PUT` tops out at 5 GB, so for smaller files (under ~100 MB) a single presigned `PutObject` URL is simpler.
- **The key is generated by the server**, never taken from the filename: no overwrites, no path tricks, and the `uploads/{userId}/` prefix makes ownership checks trivial.
- **Abandoned uploads cost money.** Parts of an upload that is never completed are stored and billed. Add a lifecycle rule with `AbortIncompleteMultipartUpload` (for example after 2 days).
- **Don't trust the declared type or size.** The worker checks the actual file (magic bytes, `ffprobe` for video) and the real object size before marking it ready. The presigned URLs only bound what the client *can* send.
- **URL lifetime.** One hour per part URL is plenty for a part; for very slow connections, let the client ask for fresh URLs for the remaining parts instead of issuing long-lived ones.

**Verification**

- API pod memory during a 5 GB upload should stay flat, since no file bytes pass through it.
- Upload a 1 GB file, cut the network halfway, restore it: only the in-flight parts are retried, and the final object's size matches the original.
- Call `completeUpload` with another user's key: it must fail with "unknown upload".""",
            },
        ]
    },
    # 26) Transacciones entre servicios: saga orquestada frente a 2PC (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Tenemos tres servicios: pedidos, pagos (con Stripe detrás) e inventario, cada uno con su base de datos. Al crear un pedido hay que reservar stock, cobrar y crear el envío. Un compañero propone una transacción distribuida (two-phase commit) para que sea todo o nada. ¿Es buena idea?""",
            },
            {
                "role": "assistant",
                "content": r"""No. Usa una **saga orquestada**: una secuencia de transacciones locales, cada una con su acción compensatoria, coordinada por el servicio de pedidos y con el progreso guardado en su base de datos.

**Por qué no 2PC aquí:**

- **Stripe no participa en tu transacción.** No hay forma de meter un cobro de un tercero en un protocolo de dos fases. Lo que sí existe es el equivalente de negocio de «preparar»: **autorizar sin capturar** (un `PaymentIntent` con `capture_method: "manual"`), y eso encaja en una saga, no en 2PC.
- **2PC bloquea.** Los participantes mantienen sus *locks* hasta que el coordinador decide; si el coordinador cae entre las dos fases, se quedan bloqueados hasta que vuelva.
- **Acopla la disponibilidad.** Crear un pedido exigiría que los tres servicios y el coordinador estén vivos a la vez.

**Diseño de la saga.** El orden de los pasos se elige para que deshacer sea lo más barato posible:

1. **Reservar stock.** Compensación: liberarlo. Invisible para el cliente.
2. **Autorizar el pago.** Compensación: anular la autorización. El cliente ve, como mucho, una retención temporal, nunca un cargo.
3. **Capturar el pago.** Es el **pivote**: si sale bien, a partir de aquí ya no se deshace nada.
4. **Crear el envío.** Posterior al pivote: si falla, se reintenta hasta que funcione; no se compensa el cobro por un fallo transitorio del servicio de envíos.

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class PermanentError(Exception):
    # El paso no puede tener éxito reintentando: tarjeta rechazada, sin stock.
    pass


class SagaLog(Protocol):
    def completed_steps(self, order_id: str) -> set[str]: ...
    def mark_completed(self, order_id: str, step: str) -> None: ...
    def mark_compensated(self, order_id: str, step: str) -> None: ...
    def mark_failed(self, order_id: str, reason: str) -> None: ...


@dataclass(frozen=True)
class Step:
    name: str
    action: Callable[[str], None]                      # idempotente; recibe order_id
    compensate: Callable[[str], None] | None = None    # deshace el efecto si un paso posterior falla
    forward_only: bool = False                         # posterior al pivote: no se deshace, se insiste


def run_saga(order_id: str, steps: list[Step], log: SagaLog) -> bool:
    # Ejecuta o reanuda la saga. Un error transitorio se propaga: el pedido se reintenta
    # más tarde y continúa desde el último paso completado.
    done = log.completed_steps(order_id)
    for index, step in enumerate(steps):
        if step.name in done:
            continue
        try:
            step.action(order_id)
        except PermanentError as error:
            if step.forward_only:
                log.mark_failed(order_id, f"{step.name} after pivot: {error}")
                raise                                  # no se deshace: alerta e intervención
            for previous in reversed(steps[:index]):
                if previous.compensate is not None:
                    previous.compensate(order_id)
                    log.mark_compensated(order_id, previous.name)
            log.mark_failed(order_id, f"{step.name}: {error}")
            return False
        log.mark_completed(order_id, step.name)
    return True


ORDER_SAGA = [
    Step("reserve_stock", inventory.reserve, compensate=inventory.release),
    Step("authorize_payment", payments.authorize, compensate=payments.void_authorization),
    Step("capture_payment", payments.capture),
    Step("create_shipment", shipping.create, forward_only=True),
]
```

(`inventory`, `payments` y `shipping` son los clientes de tus servicios.)

Lo que hace que esto sea correcto:

- **Cada acción es idempotente**, con el `order_id` como clave: el inventario no reserva dos veces el mismo pedido, y hacia Stripe va una clave de idempotencia derivada (`capture-{order_id}`). Gracias a eso, **reanudar es trivial**: un proceso programado vuelve a llamar a `run_saga` para los pedidos atascados, los pasos ya completados se saltan y el resto se repite sin efectos dobles.
- **El estado está en la base de datos de pedidos** (`saga_steps(order_id, step, status, at)`), no en memoria. Un reinicio a mitad de la saga no pierde nada.
- **El pedido es visible como «procesando»** hasta que la saga termina. Ese estado intermedio es parte del diseño: la consistencia es eventual, y la interfaz tiene que decirlo en lugar de prometer lo que aún no ha pasado.

**Verificación:** tests con servicios falsos que recorran los cuatro caminos: todo bien (cuatro pasos completados); sin stock (nada que compensar, pedido fallido); tarjeta rechazada en la autorización (stock liberado una vez); y error transitorio en el envío (la segunda ejecución de `run_saga` crea el envío y no vuelve a capturar).""",
            },
            {
                "role": "user",
                "content": "¿Y si la compensación también falla? Por ejemplo, anular la autorización da error porque Stripe no responde.",
            },
            {
                "role": "assistant",
                "content": r"""Las compensaciones no pueden «fallar» en el sentido definitivo: tienen que **acabar ejecutándose**. Se diseñan como acciones idempotentes que se reintentan hasta tener éxito, y el sistema tiene que recordar que estaba compensando aunque se caiga a mitad.

En la versión anterior hay un hueco: si `void_authorization` lanza un error transitorio, la excepción sale de `run_saga` sin haber registrado que la saga estaba deshaciendo. En la siguiente pasada volvería a intentar los pasos **hacia delante**. Se cierra persistiendo el estado «compensando» **antes** de compensar y tratándolo al reanudar:

```python
def run_saga(order_id: str, steps: list[Step], log: SagaLog) -> bool:
    if log.status(order_id) == "compensating":
        compensate_completed(order_id, steps, log)
        return False
    done = log.completed_steps(order_id)
    for step in steps:
        if step.name in done:
            continue
        try:
            step.action(order_id)
        except PermanentError as error:
            if step.forward_only:
                log.mark_failed(order_id, f"{step.name} after pivot: {error}")
                raise
            log.mark_compensating(order_id, f"{step.name}: {error}")   # se persiste ANTES de deshacer
            compensate_completed(order_id, steps, log)
            return False
        log.mark_completed(order_id, step.name)
    return True


def compensate_completed(order_id: str, steps: list[Step], log: SagaLog) -> None:
    done = log.completed_steps(order_id)
    compensated = log.compensated_steps(order_id)
    for step in reversed(steps):
        if step.name in done and step.name not in compensated and step.compensate is not None:
            step.compensate(order_id)                 # si lanza, la próxima pasada sigue desde aquí
            log.mark_compensated(order_id, step.name)
    log.mark_failed(order_id, "compensated")
```

`SagaLog` gana tres métodos (`status`, `mark_compensating` y `compensated_steps`). Ahora un error a mitad de compensación deja el pedido en «compensating», el proceso programado lo retoma y solo ejecuta las compensaciones que faltan.

Alrededor del código, tres defensas más:

1. **Reintentos con límite y escalado.** Espera creciente (1 min, 5 min, 30 min, 2 h). Si tras unas horas sigue fallando, el pedido pasa a `needs_attention`, salta una alerta y hay un procedimiento escrito para resolverlo a mano. Nada se queda atascado en silencio.
2. **Que el tiempo juegue a tu favor.** Diseña cada «reserva» para que caduque sola. Una autorización de tarjeta que nadie captura la libera el banco al cabo de unos días (en Stripe, normalmente siete), así que una anulación que no llega nunca no se convierte en un cargo. Haz lo mismo con el stock: una reserva sin confirmar caduca a los 30 minutos. Así, una compensación perdida degrada a «el recurso tardó en liberarse», no a «el recurso se perdió».
3. **Conciliación diaria.** Un trabajo que compara lo que dice Stripe (autorizaciones y cobros del día) con el estado de los pedidos. Es la red que caza lo que se escape de todo lo anterior, incluidos los bugs de esta misma saga.

**Verificación:** un servicio de pagos falso cuya anulación falla dos veces con un error transitorio y funciona a la tercera. Llamando a `run_saga` tres veces (como haría el proceso programado), el pedido termina en `failed`, el stock se libera **una** vez, la anulación se intenta tres veces y ningún paso hacia delante se vuelve a ejecutar.""",
            },
        ]
    },
    # 27) Esquema de datos: atributos variables por categoría (EAV, columnas o JSONB).
    {
        "messages": [
            {
                "role": "user",
                "content": """Estoy diseñando la base de datos de una tienda online con productos muy distintos: ropa (talla, color), electrónica (voltaje, potencia), libros (ISBN, páginas). ¿Hago una columna por atributo, una tabla de atributos clave-valor o uso JSONB en Postgres?""",
            },
            {
                "role": "assistant",
                "content": r"""**JSONB** para los atributos que dependen de la categoría, **columnas normales** para lo que comparten todos los productos (nombre, precio, stock, categoría), y la validación de cada categoría en la aplicación. Es el punto medio que funciona, y para entenderlo conviene ver por qué fallan los otros dos.

**Una columna por atributo.** Con tres categorías parece manejable; con treinta, la tabla tiene cien columnas casi siempre vacías, y cada atributo nuevo es una migración y un despliegue. Funciona si los atributos son pocos y estables, que no es tu caso.

**Tabla clave-valor (EAV: entidad, atributo, valor).** Flexible en teoría, cara en la práctica:

- Todo valor es texto (o hay una columna por tipo), así que la base de datos no puede comprobar que `power_w` es un número.
- Filtrar por dos atributos exige dos *joins* contra la misma tabla; por cinco, cinco *joins*.
- No hay restricciones: nada impide un producto de ropa sin talla o con la talla escrita de tres formas distintas.

**JSONB**, en cambio, guarda los atributos en el mismo registro, con tipos JSON (número, texto, booleano), se puede indexar y no necesita *joins*:

```sql
CREATE TABLE products (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category    text   NOT NULL CHECK (category IN ('clothing', 'electronics', 'books')),
  name        text   NOT NULL,
  price_minor bigint NOT NULL CHECK (price_minor >= 0),
  stock       int    NOT NULL DEFAULT 0,
  attributes  jsonb  NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes) = 'object')
);

-- Filtros por igualdad sobre cualquier atributo
CREATE INDEX products_attributes_gin ON products USING gin (attributes jsonb_path_ops);

-- Rango u orden sobre un atributo concreto y frecuente
CREATE INDEX products_power_w ON products (((attributes->>'power_w')::int))
  WHERE category = 'electronics';
```

Consultas:

```sql
-- camisetas rojas talla M: usa el índice GIN
SELECT id, name FROM products
 WHERE category = 'clothing' AND attributes @> '{"color": "red", "size": "M"}';

-- electrónica entre 500 y 1000 W: usa el índice de expresión
SELECT id, name FROM products
 WHERE category = 'electronics' AND (attributes->>'power_w')::int BETWEEN 500 AND 1000;
```

Por qué así:

- **`jsonb_path_ops`** hace el índice GIN más pequeño y rápido para el operador de contención `@>`, que es el de los filtros del catálogo. A cambio no sirve para `?` (existencia de clave); si la necesitas, usa el GIN por defecto.
- **El índice de expresión** cubre rangos y ordenaciones, que el GIN no hace. Créalo solo para los dos o tres atributos por los que de verdad se filtra con rangos. Un efecto útil: si un producto de electrónica llega con `"power_w": "1,5 kW"`, la conversión `::int` falla y el `INSERT` se rechaza.
- **Lo común va en columnas**: precio, stock y categoría tienen tipo, restricciones, claves externas y estadísticas propias. Si un atributo empieza a usarlo todo el catálogo (por ejemplo, `brand`), conviértelo en columna.

**La validación por categoría vive en la aplicación**, en un único sitio. Con Pydantic v2:

```python
from typing import Literal

from pydantic import BaseModel, Field


class ClothingAttributes(BaseModel):
    size: Literal["XS", "S", "M", "L", "XL"]
    color: str = Field(min_length=1)


class ElectronicsAttributes(BaseModel):
    voltage_v: int = Field(gt=0)
    power_w: int = Field(gt=0)


class BookAttributes(BaseModel):
    isbn: str = Field(pattern=r"^97[89]\d{10}$")
    pages: int = Field(gt=0)


ATTRIBUTE_SCHEMAS: dict[str, type[BaseModel]] = {
    "clothing": ClothingAttributes,
    "electronics": ElectronicsAttributes,
    "books": BookAttributes,
}


def validate_attributes(category: str, raw: dict) -> dict:
    schema = ATTRIBUTE_SCHEMAS.get(category)
    if schema is None:
        raise ValueError(f"unknown category: {category}")
    return schema.model_validate(raw).model_dump()
```

Añadir una categoría es añadir una clase y una entrada al diccionario, sin migraciones.

**Comprobación:**

- `validate_attributes("clothing", {"size": "XXL", "color": "red"})` lanza un `ValidationError` que nombra el campo `size`.
- Con unos miles de productos cargados, `EXPLAIN` de la consulta de camisetas debe mostrar `Bitmap Index Scan on products_attributes_gin`. En una tabla de cien filas el planificador preferirá recorrerla entera, y hace bien: no lo interpretes como que el índice no funciona.""",
            },
        ]
    },
    # 28) Diseño de webhooks salientes: firma, reintentos, orden y SSRF (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Vamos a ofrecer webhooks a nuestros clientes (eventos de pedidos: creado, pagado, enviado). ¿Qué tenemos que diseñar para que sea fiable y seguro, tanto para ellos como para nosotros?""",
            },
            {
                "role": "assistant",
                "content": r"""Seis decisiones, y casi todas se resuelven siguiendo la especificación **Standard Webhooks** (cabeceras `webhook-id`, `webhook-timestamp` y `webhook-signature`), que ya tiene bibliotecas de verificación en varios lenguajes. Así tus clientes no tienen que aprender un esquema propio.

**1. Sobre del evento estable.** Cada entrega lleva un id único, el tipo, la fecha y los datos:

```json
{
  "id": "evt_01J9Z6K3",
  "type": "order.paid",
  "created_at": "2025-03-04T10:21:00Z",
  "data": { "order_id": "ord_8f3", "amount_minor": 1999, "currency": "EUR" }
}
```

El `id` es lo que permite al receptor descartar duplicados. Los tipos siguen las mismas reglas de compatibilidad que tu API: añadir campos sí, quitar o cambiar no.

**2. Firma HMAC con marca de tiempo.** Un secreto por *endpoint*, generado por vosotros y mostrado una sola vez. Se firma `id.timestamp.cuerpo` con HMAC-SHA256:

```python
import base64
import hashlib
import hmac
import time


def sign(secret: bytes, msg_id: str, timestamp: int, body: bytes) -> str:
    signed = f"{msg_id}.{timestamp}.".encode() + body
    digest = hmac.new(secret, signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def verify(secret: bytes, headers: dict[str, str], body: bytes, tolerance_s: int = 300) -> bool:
    timestamp = int(headers["webhook-timestamp"])
    if abs(time.time() - timestamp) > tolerance_s:
        return False                                   # fuera de la ventana: posible repetición
    expected = sign(secret, headers["webhook-id"], timestamp, body)
    return any(hmac.compare_digest(expected, candidate) for candidate in headers["webhook-signature"].split(" "))
```

- La **marca de tiempo dentro de lo firmado** impide reenviar una petición capturada días después.
- Se firma el **cuerpo en bytes**, tal como sale. Documentad que el receptor debe verificar sobre el cuerpo crudo, antes de parsear el JSON: si lo parsea y lo vuelve a serializar, la firma no coincide. Es la primera causa de tickets de soporte.
- **Varias firmas separadas por espacios** permiten rotar el secreto: durante la rotación firmáis con el viejo y con el nuevo, y el cliente acepta cualquiera.
- `compare_digest` compara en tiempo constante.

**3. Entrega «al menos una vez» con reintentos.** Consideráis entregado solo un 2xx recibido en menos de 10-15 s. Si no, reintento con espera creciente durante unos tres días (por ejemplo: 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 10 h). El receptor **tiene** que deduplicar por `webhook-id`; decidlo en la documentación con esas palabras. Pedidle además que responda rápido y procese en segundo plano: un receptor que hace el trabajo dentro de la petición acaba superando el *timeout* y recibiendo duplicados.

**4. Sin garantía de orden.** Con reintentos, «pagado» puede llegar antes que «creado». No prometáis orden. Recomendad tratar el webhook como un aviso («el pedido ord_8f3 ha cambiado») y consultar el estado actual en vuestra API, o usar `created_at` para descartar eventos más viejos que lo que ya tienen. Prometer orden os obligaría a una cola por cliente en serie, donde un *endpoint* lento bloquea todo lo suyo.

**5. Aislamiento entre clientes.** Una cola o partición por *endpoint* y un límite de concurrencia por destino, para que un cliente con el servidor caído no retrase las entregas de los demás. Si un *endpoint* falla de forma continua durante días, se desactiva y se avisa por correo al cliente, con un botón para reactivarlo y reenviar lo pendiente.

**6. SSRF: el riesgo es vuestro.** Estáis haciendo peticiones a URLs que escribe un tercero. Sin defensas, un cliente registra `http://169.254.169.254/...` (los metadatos de la nube) o `http://10.0.0.5:6379` y vuestro *worker* se convierte en su puerta a la red interna.

- Solo `https`, solo puertos 443 (u 8443 si de verdad hace falta).
- Resolved el DNS y rechazad direcciones privadas, de *loopback*, *link-local* y de metadatos; **comprobadlo en el momento de conectar**, no solo al registrar la URL, porque el DNS puede cambiar entre una cosa y otra (*DNS rebinding*).
- Sin seguir redirecciones.
- Los *workers* de entrega, en una red de salida sin acceso a vuestra red interna. Es la defensa que funciona aunque las demás fallen.

**Producto alrededor, que reduce soporte:** registro de entregas visible para el cliente (petición, respuesta y código de estado de los últimos 30 días), botón de «enviar evento de prueba» y botón de «reenviar».

**Verificación:** tests de `verify` con una firma válida, con un byte del cuerpo cambiado (falla), con la marca de tiempo de hace 10 minutos (falla) y con dos firmas donde solo la segunda es válida (pasa). Y un test del validador de URLs con `http://localhost`, `https://10.1.2.3`, `https://169.254.169.254` y un dominio que resuelve a `127.0.0.1`: los cuatro rechazados.""",
            },
        ]
    },
    # 29) Búsqueda: Postgres frente a Elasticsearch, redactado como ADR (usuario pide la respuesta en inglés).
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto de software pragmático: da una recomendación, sus razones y la señal que la cambiaría."},
            {
                "role": "user",
                "content": """Tenemos un catálogo de 300 000 productos en Postgres y queremos búsqueda con tolerancia a erratas, filtros por categoría y precio, y orden por relevancia. El equipo propone montar Elasticsearch. Respóndeme en inglés, que lo voy a pegar tal cual en el ADR para el equipo de Polonia.""",
            },
            {
                "role": "assistant",
                "content": """# ADR: Product search on PostgreSQL

**Status:** Proposed

## Context

The catalog has 300,000 products in PostgreSQL. Requirements: full-text search in Spanish, tolerance to typos, filters by category and price, and results ordered by relevance. The team proposed adding Elasticsearch.

## Decision

Implement search inside PostgreSQL using its built-in full-text search plus the `pg_trgm` extension for typo tolerance. Do not introduce Elasticsearch at this stage.

## Rationale

- **Size.** 300,000 rows is small for PostgreSQL full-text search. The GIN indexes fit comfortably in memory, and queries of this shape typically run in milliseconds to tens of milliseconds. We will confirm with `EXPLAIN ANALYZE` on production-sized data before launch.
- **Consistency.** Search reads the same transactional data the rest of the application writes. There is no synchronization pipeline, no stale index, and no reindexing job to operate.
- **Operational cost.** Elasticsearch is a second stateful, distributed system: cluster sizing, upgrades, snapshots, monitoring, plus a change-data-capture or outbox pipeline to keep it in sync. None of today's requirements need what that cost buys.
- **Filters.** Category and price are ordinary `WHERE` clauses combined with the text match in a single query.

## Implementation

```sql
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Spanish stemming that also ignores accents ("cafe" matches "café")
CREATE TEXT SEARCH CONFIGURATION es_unaccent (COPY = spanish);
ALTER TEXT SEARCH CONFIGURATION es_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem;

ALTER TABLE products ADD COLUMN search tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('es_unaccent', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('es_unaccent', coalesce(description, '')), 'B')
  ) STORED;

CREATE INDEX products_search_idx ON products USING gin (search);
CREATE INDEX products_name_trgm_idx ON products USING gin (name gin_trgm_ops);
```

Main query (`websearch_to_tsquery` accepts what users type, including quotes and `-word`):

```sql
SELECT id, name, ts_rank(search, query) AS rank
FROM products, websearch_to_tsquery('es_unaccent', $1) AS query
WHERE search @@ query
  AND category_id = $2
  AND price_minor BETWEEN $3 AND $4
ORDER BY rank DESC
LIMIT 20;
```

Typo fallback, used when the main query returns nothing (full-text search matches word stems, not misspellings):

```sql
SELECT id, name, similarity(name, $1) AS score
FROM products
WHERE name % $1
  AND category_id = $2
ORDER BY score DESC
LIMIT 20;
```

The `%` operator uses `pg_trgm.similarity_threshold` (0.3 by default); tune it with real queries. One known trap: `unaccent()` is not immutable, so it cannot be used directly in an index expression. If trigram matching must also ignore accents, index an immutable wrapper function around it.

## Consequences

- Positive: one system to operate, no synchronization lag, search shipped in days rather than weeks.
- Negative: ranking with `ts_rank` is simpler than Elasticsearch's BM25 scoring and field boosting; synonyms require a synonym or thesaurus dictionary managed by engineers; faceted counts over large result sets are more expensive than in a search engine.

## Revisit when any of these happens

- The catalog grows past roughly 10 million documents, or p95 search latency exceeds the target (for example 200 ms) after index tuning.
- Product needs relevance tuning that `ts_rank` cannot express: per-field boosting experiments, synonyms maintained by non-engineers, many facets with counts, or search-as-you-type at high traffic.
- Search load starts to affect the transactional workload. The first step then is a read replica dedicated to search; a separate engine comes after that.

## Verification before launch

1. Take the 200 most frequent queries from the current site logs (or a list from the product team) and measure p95 latency with production-sized data.
2. For 30 representative queries, the product team grades whether the top 5 results are acceptable. Target: at least 80% acceptable before launch, and the same set becomes the regression suite for future ranking changes.""",
            },
        ]
    },
    # 30) Feature flags: hacer o comprar, tipos de flag y cómo evitar flags muertas (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Somos 12 desarrolladores, SaaS B2B en Node/TypeScript, desplegamos varias veces al día. Queremos empezar con feature flags para soltar funcionalidades poco a poco. ¿Las hacemos nosotros con una tabla o usamos un servicio? ¿Y cómo evitamos acabar con 200 flags muertas en el código?""",
            },
            {
                "role": "assistant",
                "content": r"""Empezad con una implementación propia mínima, y pasad a un servicio (Unleash o Flagsmith autoalojados, o LaunchDarkly gestionado) cuando aparezca la primera de estas necesidades: que alguien que no programa cambie la segmentación sin desplegar, auditoría de quién cambió qué, o experimentos con análisis estadístico. Hoy no tenéis ninguna, y una implementación propia bien hecha son unas 50 líneas.

Lo que sí hay que decidir desde el principio, porque es lo que evita las 200 flags muertas, es que **no todas las flags son iguales**:

| Tipo | Para qué | Vida | Quién la cambia |
|---|---|---|---|
| `release` | Soltar código a medias o poco a poco | Semanas; se borra al llegar al 100 % | El equipo dueño |
| `ops` | Interruptor de emergencia (desactivar la exportación a PDF si tumba la base) | Permanente | Guardia |
| `experiment` | Comparar variantes | Lo que dure el experimento | Producto |

Y una regla aparte: los permisos por plan («el plan Pro tiene exportación») **no son flags**: son reglas de negocio y van en vuestro modelo de planes.

```ts
// flags.ts
import { createHash } from "node:crypto";

export type FlagKind = "release" | "ops" | "experiment";

export interface FlagDefinition {
  readonly key: string;
  readonly kind: FlagKind;
  readonly owner: string;
  readonly expiresOn: string | null;        // fecha ISO; obligatoria salvo en las de tipo ops
  readonly rolloutPercent: number;          // 0-100, por tenant
  readonly allowTenants: readonly string[];
}

export const FLAGS = {
  newCheckout: {
    key: "new-checkout",
    kind: "release",
    owner: "team-payments",
    expiresOn: "2027-03-31",
    rolloutPercent: 10,
    allowTenants: ["tenant-internal"],
  },
  disablePdfExport: {
    key: "disable-pdf-export",
    kind: "ops",
    owner: "team-platform",
    expiresOn: null,
    rolloutPercent: 0,
    allowTenants: [],
  },
} as const satisfies Record<string, FlagDefinition>;

export function bucketOf(flagKey: string, tenantId: string): number {
  const digest = createHash("sha256").update(`${flagKey}:${tenantId}`).digest();
  return digest.readUInt32BE(0) % 100;
}

export function isEnabled(flag: FlagDefinition, tenantId: string): boolean {
  if (flag.allowTenants.includes(tenantId)) return true;
  return bucketOf(flag.key, tenantId) < flag.rolloutPercent;
}

export function expiredFlags(flags: readonly FlagDefinition[], today: Date): FlagDefinition[] {
  return flags.filter(
    (flag) => flag.kind !== "ops" && (flag.expiresOn === null || new Date(flag.expiresOn) < today),
  );
}
```

Decisiones:

- **El reparto es por tenant, no por usuario**: en B2B, toda la empresa del cliente ve lo mismo, y soporte no recibe tickets del tipo «mi compañero lo ve distinto».
- **El reparto es determinista y monótono.** El *hash* de `flag:tenant` coloca a cada tenant en un cubo del 0 al 99 que no cambia; quien entró al 10 % sigue dentro al 20 %. Incluir la clave de la flag en el *hash* hace que cada flag elija tenants distintos, así que no son siempre los mismos clientes los que prueban todo lo nuevo.
- **Definición en el código, estado fuera.** Clave, tipo, dueño y caducidad viven en el repositorio y pasan revisión. `rolloutPercent` y `allowTenants` se recargan cada 30 s desde una tabla `feature_flag_state`, para que una flag de tipo `ops` se active en segundos sin desplegar; los valores del código son el valor por defecto si la tabla no responde.
- **Se evalúa una vez, en el borde.** El *middleware* calcula las flags del tenant al empezar la petición y pasa booleanos hacia dentro. El código de dominio recibe `useNewCheckout: boolean`, no consulta el sistema de flags.

**Cómo no acumular flags muertas:** la caducidad es obligatoria para `release` y `experiment`, y CI falla cuando una flag caduca. Cuando una flag llega al 100 %, se abre la tarea de borrarla (el código del camino viejo y la propia flag), con el mismo dueño. Si se quiere más tiempo, se cambia la fecha en un *pull request*, y esa decisión queda visible.

```ts
import { describe, expect, it } from "vitest";
import { FLAGS, bucketOf, expiredFlags } from "./flags";

describe("feature flags", () => {
  it("no hay flags de release ni experimentos caducados", () => {
    expect(expiredFlags(Object.values(FLAGS), new Date()).map((flag) => flag.key)).toEqual([]);
  });

  it("el reparto es estable y monótono", () => {
    const tenants = Array.from({ length: 1000 }, (_, i) => `tenant-${i}`);
    const at10 = tenants.filter((t) => bucketOf("new-checkout", t) < 10);
    const at20 = new Set(tenants.filter((t) => bucketOf("new-checkout", t) < 20));
    expect(at10.every((t) => at20.has(t))).toBe(true);
    expect(at10.length).toBeGreaterThan(50);
    expect(at10.length).toBeLessThan(150);
  });
});
```

El primer test es el que hace cumplir la regla: el día que `new-checkout` caduque, CI se pone en rojo hasta que alguien la borre o justifique la prórroga.""",
            },
            {
                "role": "user",
                "content": "Vale. ¿Y cómo probamos todo esto? Con 10 flags activas hay 1024 combinaciones.",
            },
            {
                "role": "assistant",
                "content": """No se prueban las combinaciones: se diseña para que no importen. Las 1024 combinaciones solo son un problema si las flags **interactúan**, y que interactúen es un defecto de diseño que conviene evitar, no una realidad que haya que cubrir con tests.

**1. Flags independientes por construcción.** Cada flag protege un cambio acotado y no se anida dentro de otra. Si os veis escribiendo `if (newCheckout && newPricing)`, es que son una sola funcionalidad (fusionadlas) o que una depende de la otra (soltad primero una, retirad su flag y después empezad con la segunda).

**2. Cada flag se prueba en sus dos estados, con el resto en su valor de producción.** Como el código de dominio recibe booleanos (la evaluación ocurre en el borde), los tests unitarios pasan `useNewCheckout: true` y `false` sin tocar el sistema de flags. Son 2 casos por flag: 20 en total, no 1024.

**3. Dos perfiles en los tests de extremo a extremo:**

- **Producción**: el estado real actual de todas las flags. Es lo que ven hoy los clientes.
- **Todo lo nuevo activado**: todas las flags de tipo `release` encendidas. Es, aproximadamente, lo que verán en unas semanas, y detecta pronto si dos funcionalidades nuevas chocan entre sí.

**4. Las flags de tipo `ops` se prueban activadas en un test específico**, porque su estado normal es «apagada» y el día que se encienden es en mitad de un incidente: el peor momento para descubrir que el camino alternativo no funciona.

Si alguna vez dos flags tienen que convivir y afectan a la misma pantalla, entonces sí: probad esas dos en sus cuatro combinaciones. Es la excepción que confirma el diseño; con más de dos, la respuesta es simplificar.

Y la razón de fondo por la que la regla de caducidad importa: cada flag viva duplica los caminos posibles del código que toca. Borrar flags no es limpieza opcional; es lo que mantiene finito el número de cosas que hay que probar.""",
            },
        ]
    },
]
