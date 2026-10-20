"""SQL y bases de datos relacionales: PostgreSQL (principal), MySQL y SQLite."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) INNER vs LEFT JOIN y filtros en ON vs WHERE (principiante, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Quiero listar todos los clientes con el número de pedidos de 2024, incluyendo los que no tienen pedidos. Hice un LEFT JOIN pero los clientes sin pedidos desaparecen. ¿Por qué?"},
            {
                "role": "assistant",
                "content": """Porque el filtro del año está en el `WHERE`, y el `WHERE` se evalúa **después** del `LEFT JOIN`. Para un cliente sin pedidos, el join produce una fila con todas las columnas de `orders` en `NULL`; la condición `orders.created_at >= '2024-01-01'` sobre un `NULL` no es verdadera, y la fila se descarta. El `LEFT JOIN` se convierte en un `INNER JOIN` encubierto.

Seguramente tienes esto:

```sql
SELECT c.id, c.name, COUNT(o.id) AS orders_2024
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.created_at >= '2024-01-01' AND o.created_at < '2025-01-01'   -- mata los NULL
GROUP BY c.id, c.name;
```

Mueve la condición al `ON`: así forma parte de la regla de emparejamiento y los clientes sin pedidos conservan su fila con `NULL`:

```sql
SELECT c.id, c.name, COUNT(o.id) AS orders_2024
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.id
      AND o.created_at >= '2024-01-01'
      AND o.created_at <  '2025-01-01'
GROUP BY c.id, c.name
ORDER BY c.name;
```

`COUNT(o.id)` cuenta solo valores no nulos, así que los clientes sin pedidos salen con 0. `COUNT(*)` contaría la fila del cliente y daría 1, que es el segundo error típico de esta consulta.

La regla general:

| Dónde pones la condición | Efecto en un `LEFT JOIN` |
|---|---|
| En `ON`, sobre la tabla derecha | Decide **qué filas de la derecha emparejan**; las de la izquierda se conservan siempre |
| En `WHERE`, sobre la tabla derecha | Filtra el resultado final; elimina las filas con `NULL`, o sea, las «sin pareja» |
| En `WHERE`, sobre la tabla izquierda | Correcto: limita qué clientes aparecen, sin afectar al join |

El único caso en que **quieres** la condición de la derecha en el `WHERE` es el *anti-join*: «clientes que no tienen pedidos en 2024».

```sql
SELECT c.id, c.name
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.id
      AND o.created_at >= '2024-01-01' AND o.created_at < '2025-01-01'
WHERE o.id IS NULL;
```

Aunque para eso `NOT EXISTS` expresa mejor la intención y el planificador lo optimiza igual de bien.

Comprobación rápida con datos mínimos: dos clientes, uno con un pedido de 2023 y otro con dos de 2024. La consulta correcta devuelve `(1, 'Ana', 0)` y `(2, 'Luis', 2)`; la original solo devuelve a Luis.""",
            },
        ]
    },
    # 2) NULL: != NULL y NOT IN con NULL (principiante, el usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": """Dos consultas que no entiendo por qué fallan en Postgres:

```sql
-- 1) debería devolver los usuarios sin teléfono y devuelve 0 filas
SELECT * FROM users WHERE phone = NULL;

-- 2) debería devolver los productos que no están en ningún pedido y devuelve 0 filas,
--    pero sé que hay varios
SELECT * FROM products WHERE id NOT IN (SELECT product_id FROM order_items);
```

Si cambio la segunda por `NOT EXISTS` funciona. ¿Qué pasa con NOT IN?""",
            },
            {
                "role": "assistant",
                "content": """Las dos tienen la misma causa: en SQL, `NULL` no es un valor, es «desconocido», y cualquier comparación con él da `NULL`, no `TRUE` ni `FALSE`. Un `WHERE` solo deja pasar filas cuya condición es `TRUE`.

**Consulta 1.** `phone = NULL` es siempre `NULL` (desconocido), incluso cuando `phone` es `NULL`: no puedes saber si un desconocido es igual a otro desconocido. La sintaxis para preguntar «¿es nulo?» es `IS NULL`:

```sql
SELECT * FROM users WHERE phone IS NULL;
```

Lo mismo para `IS NOT NULL`. Y para comparar dos columnas que pueden ser nulas tratándolas como iguales, `IS NOT DISTINCT FROM`.

**Consulta 2.** `NOT IN (lista)` se expande a `id <> v1 AND id <> v2 AND ...`. Basta con que **un solo** `product_id` de `order_items` sea `NULL` para que uno de esos términos sea `NULL`, y entonces todo el `AND` es `NULL` o `FALSE` para cualquier `id`: ninguna fila pasa. Por eso devuelve 0 aunque haya productos sin pedidos. Tu tabla `order_items` tiene al menos un `product_id` nulo; compruébalo:

```sql
SELECT count(*) FROM order_items WHERE product_id IS NULL;
```

`NOT EXISTS` no tiene este problema porque no compara valores: pregunta si la subconsulta devuelve **alguna fila**, y una fila con `product_id` nulo simplemente no correlaciona con ningún producto.

```sql
SELECT p.*
FROM products p
WHERE NOT EXISTS (
    SELECT 1 FROM order_items oi WHERE oi.product_id = p.id
);
```

Si por legibilidad prefieres `NOT IN`, excluye los nulos explícitamente, pero es una trampa que volverá a morder a quien edite la consulta:

```sql
WHERE id NOT IN (SELECT product_id FROM order_items WHERE product_id IS NOT NULL)
```

Dos reglas para que no te vuelva a pasar:

1. **`NOT IN` solo con subconsultas sobre columnas `NOT NULL`.** Si la columna admite nulos, `NOT EXISTS`. (`IN` a secas no sufre el problema: con un `NULL` en la lista sigue devolviendo `TRUE` cuando hay coincidencia.)
2. **Define `NOT NULL` siempre que el dominio lo permita.** Un `product_id` nulo en `order_items` probablemente es un dato roto, no un caso de negocio; con `product_id INT NOT NULL REFERENCES products(id)` la segunda consulta habría funcionado desde el principio.

Para ver la lógica de tres valores con tus propios ojos:

```sql
SELECT NULL = NULL, NULL <> 1, NULL IS NULL, 1 NOT IN (1, NULL), 2 NOT IN (1, NULL);
-- NULL, NULL, true, false, NULL
```

La última columna es tu consulta 2 en miniatura: «2 no está en (1, NULL)» es desconocido, porque ese `NULL` podría ser un 2.""",
            },
        ]
    },
    # 3) GROUP BY / HAVING y el error "must appear in the GROUP BY clause" (principiante)
    {
        "messages": [
            {"role": "user", "content": "Postgres me tira `column \"c.name\" must appear in the GROUP BY clause or be used in an aggregate function` y en MySQL la misma consulta funciona. ¿Cuál de los dos tiene razón? Y ya de paso, ¿cuándo uso HAVING y cuándo WHERE?"},
            {
                "role": "assistant",
                "content": """Postgres tiene razón, y MySQL también la tendría si lo configuraras en modo estricto. Cuando agrupas, cada grupo se convierte en **una** fila de salida; toda columna que no esté en el `GROUP BY` tiene potencialmente varios valores distintos dentro del grupo, y SQL no tiene forma de elegir uno. Postgres te obliga a decidir; MySQL (sin `ONLY_FULL_GROUP_BY`, que es el valor por defecto desde 5.7 pero que muchos hostings desactivan) escoge un valor cualquiera del grupo, en silencio.

Tu consulta probablemente es:

```sql
SELECT c.id, c.name, COUNT(o.id)
FROM customers c
JOIN orders o ON o.customer_id = c.id
GROUP BY c.id;
```

Tienes dos soluciones correctas:

```sql
-- a) Añadir la columna al GROUP BY (lo más portable)
GROUP BY c.id, c.name

-- b) Usar un agregado que elija explícitamente
SELECT c.id, MAX(c.name), COUNT(o.id)
```

Y una tercera que es la que Postgres acepta de verdad en este caso: si `c.id` es la **clave primaria** de `customers`, Postgres sabe que `c.name` está determinada por ella (*dependencia funcional*) y permite `GROUP BY c.id` sin listar `c.name`. Si te sigue dando el error es porque `id` no está declarada como `PRIMARY KEY`, o porque la tabla llega a través de una vista o subconsulta donde esa dependencia se pierde.

En MySQL, activa el modo estricto en desarrollo para que te avise igual que Postgres: `SET sql_mode = 'ONLY_FULL_GROUP_BY'` (viene en el conjunto por defecto de `sql_mode`, así que suele bastar con no quitarlo). Si necesitas el comportamiento de «un valor cualquiera», dilo con `ANY_VALUE(c.name)`.

**`WHERE` frente a `HAVING`:** es cuestión de **cuándo** se aplica el filtro.

| | `WHERE` | `HAVING` |
|---|---|---|
| Se evalúa | Antes de agrupar, fila a fila | Después de agrupar, grupo a grupo |
| Puede usar agregados | No | Sí |
| Efecto en rendimiento | Reduce las filas que entran en el agrupado | Descarta grupos ya calculados |

```sql
SELECT c.id, c.name, COUNT(o.id) AS orders, SUM(o.total) AS revenue
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'paid'            -- filtra pedidos individuales ANTES de contar
GROUP BY c.id, c.name
HAVING COUNT(o.id) >= 5            -- filtra clientes DESPUÉS de contar
ORDER BY revenue DESC;
```

Regla práctica: si la condición no usa un agregado, va en `WHERE`; mover `o.status = 'paid'` al `HAVING` funcionaría en algunos motores pero haría el agrupado sobre todas las filas para luego tirarlas.

Orden lógico completo, que explica todo lo anterior: `FROM` → `WHERE` → `GROUP BY` → `HAVING` → `SELECT` → `ORDER BY` → `LIMIT`. Por eso un alias definido en `SELECT` (`AS revenue`) se puede usar en `ORDER BY` pero no en `WHERE` ni en `HAVING` (salvo en MySQL, que lo permite como extensión).""",
            },
        ]
    },
    # 4) subconsultas vs CTE (intermedio)
    {
        "messages": [
            {"role": "user", "content": "¿Es verdad que las CTE (WITH) en Postgres son más lentas que las subconsultas porque siempre se materializan? Un compañero me dice que nunca use WITH en consultas de producción."},
            {
                "role": "assistant",
                "content": """Era verdad hasta PostgreSQL 11. Desde **PostgreSQL 12** una CTE que se referencia una sola vez y no tiene efectos secundarios se **inlinea**: el planificador la trata exactamente como una subconsulta, con los mismos índices y las mismas condiciones empujadas hacia dentro. El consejo de tu compañero tiene siete años de retraso.

Las reglas actuales:

- Se inlinea si se usa **una vez**, es un `SELECT` (sin `INSERT/UPDATE/DELETE` dentro) y no es recursiva.
- Se materializa (se calcula una vez y se guarda en memoria o disco) si se referencia **más de una vez**, porque recalcularla sería peor.
- Puedes forzar cualquiera de las dos: `WITH x AS MATERIALIZED (...)` o `WITH x AS NOT MATERIALIZED (...)`.

Ejemplo donde el inlining importa:

```sql
WITH recent AS (
    SELECT * FROM orders WHERE created_at >= now() - interval '7 days'
)
SELECT * FROM recent WHERE customer_id = 42;
```

En PG 11 esto escaneaba todos los pedidos de la semana y luego filtraba por cliente. En PG 12+ el `customer_id = 42` se empuja dentro y usa el índice `(customer_id, created_at)` si existe. Compruébalo: `EXPLAIN` debe mostrar un `Index Scan` sobre `orders` sin ningún nodo `CTE Scan`.

Cuándo **quieres** materializar aunque se use una vez:

```sql
WITH expensive AS MATERIALIZED (
    SELECT customer_id, some_slow_function(payload) AS score FROM events
)
SELECT * FROM expensive WHERE score > 0.9;
```

Sin `MATERIALIZED`, el planificador podría empujar `score > 0.9` dentro y llamar a la función una vez por fila **y** otra vez para el filtro, o reordenar de forma que la función se evalúe más veces. Materializar es una barrera de optimización deliberada; también sirve cuando el planificador estima mal y quieres fijar el orden.

Cuándo una CTE sigue siendo claramente mejor que una subconsulta anidada, independientemente del rendimiento:

1. **Legibilidad**: tres niveles de subconsultas anidadas se leen de dentro afuera; tres CTE se leen de arriba abajo con nombres.
2. **Reutilización**: la misma derivación usada en dos sitios (ahí la materialización es un ahorro, no un coste).
3. **Recursión**: `WITH RECURSIVE` no tiene equivalente con subconsultas.
4. **CTE modificadoras**: `WITH moved AS (DELETE ... RETURNING *) INSERT INTO archive SELECT * FROM moved` hace un movimiento atómico en una sola sentencia.

En otros motores: MySQL 8 inlinea o materializa según su propio criterio (sin cláusula para forzarlo, salvo *optimizer hints*); SQLite trata las CTE como subconsultas y puede aplanarlas. En ninguno hay razón para prohibirlas.

La verificación que zanja la discusión con tu compañero es `EXPLAIN (ANALYZE, BUFFERS)` de las dos versiones de una consulta concreta: si los planes son idénticos, la CTE no cuesta nada; si aparece `CTE Scan` con muchas filas y luego un filtro, es que se materializó, y entonces decides si `NOT MATERIALIZED` o reescribir.""",
            },
        ]
    },
    # 5) window functions (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Necesito, por cada categoría, los 3 productos más vendidos, y además una columna con el acumulado de ventas por mes. Lo tengo con subconsultas correlacionadas y tarda una barbaridad. ¿Window functions?"},
            {
                "role": "assistant",
                "content": """Sí, son exactamente los dos casos de libro: ranking dentro de un grupo y acumulado sobre un orden. Una función de ventana calcula un valor por fila **mirando otras filas** sin colapsarlas como haría `GROUP BY`.

**Top 3 por categoría** con `ROW_NUMBER()`:

```sql
WITH ranked AS (
    SELECT
        p.category_id,
        p.id,
        p.name,
        SUM(oi.quantity) AS units,
        ROW_NUMBER() OVER (PARTITION BY p.category_id ORDER BY SUM(oi.quantity) DESC, p.id) AS rn
    FROM products p
    JOIN order_items oi ON oi.product_id = p.id
    GROUP BY p.category_id, p.id, p.name
)
SELECT category_id, id, name, units
FROM ranked
WHERE rn <= 3
ORDER BY category_id, rn;
```

- `PARTITION BY category_id` reinicia la numeración en cada categoría; `ORDER BY ... DESC` decide quién es el 1.
- La ventana se calcula **después** del `GROUP BY`, por eso puede usar `SUM(oi.quantity)` dentro del `ORDER BY`.
- El `, p.id` final desempata: sin él, dos productos con las mismas unidades reciben números en orden arbitrario y la consulta no es determinista.
- No puedes poner `WHERE rn <= 3` en la misma consulta que define `rn` (el `WHERE` se evalúa antes de las ventanas); de ahí la CTE.

Si quieres que los empates compartan puesto, cambia a `RANK()` (deja huecos: 1, 1, 3) o `DENSE_RANK()` (1, 1, 2); entonces el filtro puede devolver más de 3 filas, y eso suele ser lo correcto para «los más vendidos».

**Acumulado por mes**:

```sql
SELECT
    date_trunc('month', created_at)::date AS month,
    SUM(total) AS month_sales,
    SUM(SUM(total)) OVER (ORDER BY date_trunc('month', created_at)) AS running_total
FROM orders
WHERE status = 'paid'
GROUP BY 1
ORDER BY 1;
```

`SUM(SUM(total))` parece raro pero es legítimo: el `SUM` interior es el agregado por mes; el exterior es la ventana que suma esos agregados en orden. Sin `PARTITION BY`, la ventana es toda la tabla de resultados.

Por qué tus subconsultas correlacionadas tardaban: cada una se ejecuta **una vez por fila** de la consulta externa (O(n·m)); la ventana ordena una vez y recorre (O(n log n)). Con `EXPLAIN ANALYZE` verás desaparecer el `SubPlan` ejecutado miles de veces y aparecer un único `WindowAgg`.

Otras funciones de ventana que resuelven preguntas parecidas: `LAG(total) OVER (ORDER BY month)` para «ventas del mes anterior», `SUM(...) OVER (PARTITION BY customer_id ORDER BY created_at ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` para medias móviles, `FIRST_VALUE` / `LAST_VALUE` para el primer y último pedido de cada cliente.""",
            },
            {"role": "user", "content": "Funciona, pero el acumulado hace algo raro: cuando dos pedidos del mismo día tienen el mismo total, el running total por día (ahora lo hago por created_at sin truncar) salta los dos a la vez en vez de ir uno a uno."},
            {
                "role": "assistant",
                "content": """Es el **marco por defecto** de la ventana. Cuando escribes `OVER (ORDER BY created_at)` sin especificar marco, el estándar asume:

```sql
RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
```

Con `RANGE`, «fila actual» significa «todas las filas con el **mismo valor** de ordenación» (los *peers*). Si dos pedidos tienen exactamente el mismo `created_at`, para el motor son empatados, y el acumulado de ambos incluye a los dos. Por eso el salto.

Para que avance fila a fila, pide el marco físico:

```sql
SUM(total) OVER (
    ORDER BY created_at, id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
) AS running_total
```

Dos cambios y los dos importan:

1. **`ROWS` en vez de `RANGE`**: cuenta posiciones, no valores; cada fila añade solo lo suyo.
2. **`, id` en el `ORDER BY`**: con `ROWS`, el orden entre empatados decide el acumulado de cada uno; sin desempate, dos ejecuciones podrían asignar el salto a pedidos distintos. Con la clave primaria el resultado es estable.

Comprobación con dos pedidos de 10 a la misma hora:

| id | created_at | total | RANGE (por defecto) | ROWS + id |
|---|---|---|---|---|
| 1 | 10:00 | 10 | 20 | 10 |
| 2 | 10:00 | 10 | 20 | 20 |

El marco `RANGE` no es un defecto: es lo que quieres cuando el acumulado se define por valor («ventas hasta este día incluido», ordenando por fecha sin hora). La trampa es que sea el valor por defecto y que solo se note con empates.

Nota de rendimiento: `ROWS` suele ser algo más rápido que `RANGE` porque no tiene que buscar los límites del grupo de empatados. Y si necesitas marcos por intervalo real («las ventas de los últimos 7 días para cada fila»), desde PG 11 existe `RANGE BETWEEN interval '7 days' PRECEDING AND CURRENT ROW`, que sí usa el valor de la columna como distancia.""",
            },
        ]
    },
    # 6) consulta lenta con EXPLAIN ANALYZE: índice no usado (intermedio, el usuario trae el plan)
    {
        "messages": [
            {
                "role": "user",
                "content": """Esta consulta tarda 4 segundos aunque hay un índice en `email` y otro en `created_at`:

```sql
SELECT id, email, created_at
FROM users
WHERE lower(email) = 'ana@example.com'
   OR date(created_at) = '2024-05-01';
```

EXPLAIN ANALYZE:

```
Seq Scan on users  (cost=0.00..198432.00 rows=52 width=48) (actual time=0.031..4102.512 rows=3 loops=1)
  Filter: ((lower((email)::text) = 'ana@example.com'::text) OR (date(created_at) = '2024-05-01'::date))
  Rows Removed by Filter: 5199997
Planning Time: 0.182 ms
Execution Time: 4102.601 ms
```""",
            },
            {
                "role": "assistant",
                "content": """El plan lo dice: `Seq Scan` con 5,2 millones de filas descartadas por el filtro. Los índices existen pero **no sirven para estos predicados**, por dos razones independientes.

**1. Aplicas una función a la columna indexada.** El índice sobre `email` ordena los valores de `email`, no los de `lower(email)`. Para usarlo, el motor tendría que calcular `lower()` de cada entrada, que es lo mismo que leer la tabla. Lo mismo con `date(created_at)`: el índice conoce `created_at`, no su fecha truncada. Un predicado que el índice puede atender directamente se llama *sargable*; `función(columna) = valor` no lo es.

**2. Un `OR` entre dos columnas distintas** obliga a usar dos índices y unir los resultados (`BitmapOr`). Postgres sabe hacerlo, pero solo si cada rama es sargable; como ninguna lo es, cae a secuencial.

Dos arreglos, uno por predicado:

**Email:** o normalizas al escribir (lo mejor) o creas un **índice de expresión**:

```sql
CREATE INDEX CONCURRENTLY users_lower_email_idx ON users (lower(email));
```

A partir de ahí `WHERE lower(email) = ...` usa ese índice, porque la expresión coincide exactamente. Si puedes, además restringe la columna a minúsculas (`CHECK (email = lower(email))`) y compara sin función; o usa el tipo `citext`.

**Fecha:** reescribe como rango, que sí es sargable sobre el índice existente:

```sql
WHERE created_at >= '2024-05-01' AND created_at < '2024-05-02'
```

Cuidado con la zona horaria: si `created_at` es `timestamptz`, `date(created_at)` usa la zona de la sesión; el rango debe expresarse en esa misma zona para devolver las mismas filas (`'2024-05-01'::timestamptz` también la usa, así que coinciden).

Consulta final:

```sql
SELECT id, email, created_at
FROM users
WHERE lower(email) = 'ana@example.com'
   OR (created_at >= '2024-05-01' AND created_at < '2024-05-02');
```

Plan esperado:

```
Bitmap Heap Scan on users  (actual rows=3)
  Recheck Cond: ((lower(email) = 'ana@example.com') OR (created_at >= ... AND created_at < ...))
  ->  BitmapOr
        ->  Bitmap Index Scan on users_lower_email_idx
        ->  Bitmap Index Scan on users_created_at_idx
```

De 4 s a unos pocos milisegundos.

Dos detalles del plan original que confirman el diagnóstico:

- `rows=52` estimadas frente a `rows=3` reales: la estimación es mala porque el planificador no tiene estadísticas sobre `lower(email)` ni `date(created_at)`. El índice de expresión crea esas estadísticas de paso.
- `Rows Removed by Filter: 5199997`: la casi totalidad de la tabla se leyó para tirarla. Siempre que veas ese número cerca del tamaño de la tabla, el índice no está entrando.

Comprueba con `EXPLAIN (ANALYZE, BUFFERS)`: los `shared hit/read` deben bajar de cientos de miles de páginas a unas decenas.""",
            },
        ]
    },
    # 7) índices compuestos, covering y parciales (intermedio)
    {
        "messages": [
            {"role": "user", "content": "Tengo una tabla `orders` grande y las consultas típicas son `WHERE customer_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 20` y `WHERE status = 'pending'` para un worker. ¿Qué índices creo? ¿Importa el orden de las columnas?"},
            {
                "role": "assistant",
                "content": """Importa mucho. Un índice B-tree compuesto está ordenado por la primera columna, dentro de ella por la segunda, y así. Solo sirve para condiciones que fijan un **prefijo** de esa lista; es la misma lógica que una guía telefónica ordenada por apellido y luego nombre: encontrar a todos los «García» es inmediato, encontrar a todos los «Luis» obliga a leerla entera.

Para tu primera consulta, el índice ideal es:

```sql
CREATE INDEX CONCURRENTLY orders_customer_status_created_idx
    ON orders (customer_id, status, created_at DESC);
```

Por qué en ese orden:

1. Las columnas con **igualdad** (`customer_id = ?`, `status = 'pending'`) van primero: acotan el tramo del índice.
2. La columna del **`ORDER BY`** va después, con la misma dirección: el tramo ya sale ordenado y el `LIMIT 20` puede parar tras leer 20 entradas, sin ordenar nada. En el plan verás `Index Scan` sin nodo `Sort`.
3. Una columna de **rango** (`created_at > ?`) también iría al final; después de un rango, las siguientes columnas ya no acotan.

Si pusieras `(created_at, customer_id, status)`, el índice solo serviría para consultas que filtren por fecha; la tuya haría un escaneo del índice completo.

Para el worker, `WHERE status = 'pending'` no puede usar ese índice (no fija `customer_id`). Pero no crees un índice sobre `status` entera: casi todas las filas serán `delivered` y nadie las busca por ese campo. Crea un **índice parcial** con solo las filas que interesan:

```sql
CREATE INDEX CONCURRENTLY orders_pending_idx
    ON orders (created_at)
    WHERE status = 'pending';
```

Es diminuto (solo los pendientes), se mantiene barato y además deja el worker ordenado por antigüedad. La condición del `WHERE` de la consulta debe implicar la del índice para que el planificador lo elija; `status = 'pending'` literal lo cumple, `status = $1` con parámetro no siempre (el plan genérico no sabe el valor).

Tercer refinamiento, si la consulta solo lee unas pocas columnas: **índice cubridor** con `INCLUDE`, para que el motor no tenga que ir a la tabla por cada fila:

```sql
CREATE INDEX CONCURRENTLY orders_customer_status_created_idx
    ON orders (customer_id, status, created_at DESC)
    INCLUDE (total);
```

`SELECT id, created_at, total` se resuelve con un `Index Only Scan` (el `id` también está en el índice, porque Postgres guarda el TID y las columnas incluidas). Funciona bien solo si la tabla se vacía (`VACUUM`) con regularidad: el `Index Only Scan` necesita el *visibility map* al día; si ves `Heap Fetches` altos en el plan, es eso.

Lo que no hace falta: un índice sobre `customer_id` solo. El compuesto que empieza por `customer_id` ya lo cubre. Cada índice de más cuesta en cada `INSERT`/`UPDATE` y en espacio; revisa los que no se usan con:

```sql
SELECT indexrelname, idx_scan FROM pg_stat_user_indexes WHERE relname = 'orders' ORDER BY idx_scan;
```

`CONCURRENTLY` en todos los `CREATE INDEX` de producción: no bloquea escrituras mientras se construye, a cambio de tardar más y de no poder ir dentro de una transacción.""",
            },
        ]
    },
    # 8) transacciones y niveles de aislamiento (multiturno, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo una tabla `accounts` con saldo. Dos peticiones concurrentes leen el saldo (100), cada una resta 30 y escribe 70, y acabo con 70 en vez de 40. Las dos van dentro de una transacción, ¿cómo puede pasar?"},
            {
                "role": "assistant",
                "content": """Porque una transacción por sí sola no serializa nada: lo que hace es garantizar atomicidad (todo o nada) y el nivel de aislamiento que tengas configurado: por defecto **`READ COMMITTED`** en PostgreSQL y `REPEATABLE READ` en MySQL InnoDB, y ninguno de los dos evita este patrón. En esos niveles, dos transacciones pueden leer el mismo valor, calcular en la aplicación, y la segunda escritura pisa a la primera. Es la anomalía clásica de **actualización perdida** (*lost update*).

Tu patrón, en orden:

```
T1: SELECT balance FROM accounts WHERE id = 1;   -- 100
T2: SELECT balance FROM accounts WHERE id = 1;   -- 100
T1: UPDATE accounts SET balance = 70 WHERE id = 1; COMMIT;
T2: UPDATE accounts SET balance = 70 WHERE id = 1; COMMIT;   -- pisa a T1
```

Tres formas correctas de resolverlo, de más simple a más general.

**1. Hazlo en una sola sentencia.** La operación es atómica a nivel de fila: el motor bloquea la fila, lee el valor actual y escribe. No hay ventana entre leer y escribir.

```sql
UPDATE accounts
SET balance = balance - 30
WHERE id = 1 AND balance >= 30
RETURNING balance;
```

Si `RETURNING` no devuelve fila, no había saldo suficiente. Cubre el 80 % de los casos y es la solución que deberías intentar primero.

**2. Bloqueo pesimista: `SELECT ... FOR UPDATE`.** Cuando la lógica entre leer y escribir vive en la aplicación (validaciones, cálculos con otras tablas):

```sql
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;   -- T2 se queda esperando aquí
-- lógica en la aplicación
UPDATE accounts SET balance = 70 WHERE id = 1;
COMMIT;                                                 -- T2 despierta, lee 70 y resta sobre 70
```

El bloqueo dura hasta el `COMMIT`, así que mantén la transacción corta: nada de llamadas HTTP ni esperas de usuario dentro.

**3. Subir el aislamiento.** Con `SERIALIZABLE` (Postgres) el motor detecta el conflicto y aborta la segunda transacción con `could not serialize access due to concurrent update` (`SQLSTATE 40001`). Tu código debe **reintentar** la transacción entera. Es la opción más general (protege también contra anomalías que no viste venir) pero exige el bucle de reintento en toda la aplicación. `REPEATABLE READ` en Postgres también detecta este caso concreto (el `UPDATE` sobre una fila modificada tras la instantánea falla); en MySQL no, porque su `REPEATABLE READ` no detecta escrituras perdidas.

Resumen de los niveles, para tener el mapa:

| Nivel | Lectura sucia | Lectura no repetible | Fantasmas | Actualización perdida |
|---|---|---|---|---|
| `READ COMMITTED` | No | Sí | Sí | **Sí** |
| `REPEATABLE READ` (PG) | No | No | No | Aborta |
| `REPEATABLE READ` (MySQL) | No | No | Parcial | **Sí** |
| `SERIALIZABLE` | No | No | No | Aborta |

Para tu caso concreto, empieza por la opción 1. Verificación: dos sesiones `psql`, `BEGIN` en ambas, el `UPDATE` relativo en la primera sin `COMMIT`, el mismo en la segunda (se queda esperando), `COMMIT` en la primera, y la segunda termina con saldo 40.""",
            },
            {"role": "user", "content": "El problema es que entre leer el saldo y escribirlo tengo que llamar a un servicio externo de fraude que tarda hasta 2 segundos. Con FOR UPDATE bloquearía la cuenta todo ese tiempo, ¿no?"},
            {
                "role": "assistant",
                "content": """Sí, y además mantendrías una transacción (y una conexión del pool) abierta 2 segundos por operación. Para ese caso la solución es **bloqueo optimista**: no bloqueas nada durante la llamada externa; en su lugar, al escribir compruebas que nadie cambió la fila desde que la leíste.

Añade una columna de versión:

```sql
ALTER TABLE accounts ADD COLUMN version INT NOT NULL DEFAULT 0;
```

Flujo:

```sql
-- 1) Leer sin transacción larga
SELECT balance, version FROM accounts WHERE id = 1;     -- 100, 7

-- 2) Llamar al servicio de fraude (2 s), fuera de cualquier transacción

-- 3) Escribir solo si la versión no cambió
UPDATE accounts
SET balance = 70, version = version + 1
WHERE id = 1 AND version = 7
RETURNING version;
```

- Si `RETURNING` devuelve una fila, nadie tocó la cuenta: tu escritura es válida.
- Si no devuelve nada (0 filas afectadas), otra transacción escribió entre tu lectura y tu escritura: vuelves a leer, reevalúas (incluida la llamada a fraude si depende del saldo) y reintentas. Suele bastar con 2-3 intentos.

Comparado con las opciones anteriores:

| | Pesimista (`FOR UPDATE`) | Optimista (versión) |
|---|---|---|
| Bloquea durante la lógica | Sí | No |
| Coste cuando no hay contención | Un lock barato | Nada |
| Coste cuando hay contención | Esperas en cola | Reintentos (trabajo repetido) |
| Requiere cambios de esquema | No | Una columna |
| Funciona con I/O externa en medio | Mal | Bien |

La elección depende de la frecuencia de conflicto: si dos operaciones sobre la misma cuenta en 2 segundos son raras, el optimista gana claramente. Si son constantes (una cuenta muy caliente), el reintento repetiría la llamada de fraude muchas veces y te interesa encolar las operaciones de esa cuenta y procesarlas en serie.

Dos detalles de implementación:

1. La condición `AND balance >= 30` sigue teniendo sentido en el `UPDATE` como red de seguridad, además de la versión.
2. Un `updated_at` con precisión de microsegundos puede hacer de versión, pero dos escrituras en el mismo microsegundo o un reloj que retrocede lo rompen; el entero es más robusto y más barato de comparar.

Prueba de regresión, en dos sesiones: ambas leen `version = 7`; la primera escribe y obtiene `8`; la segunda escribe con `version = 7` y obtiene 0 filas. Ese 0 es la señal que tu código debe tratar como «reintentar», no como error.""",
            },
        ]
    },
    # 9) deadlock detected (avanzado, el usuario trae el log)
    {
        "messages": [
            {
                "role": "user",
                "content": """En producción, varias veces al día:

```
ERROR:  deadlock detected
DETAIL:  Process 2314 waits for ShareLock on transaction 88123; blocked by process 2290.
         Process 2290 waits for ShareLock on transaction 88120; blocked by process 2314.
HINT:  See server log for query details.
CONTEXT:  while updating tuple (812,4) in relation "inventory"
```

El código que lo provoca es un job que, por cada pedido, actualiza el stock de cada línea:

```python
for item in order.items:
    cur.execute("UPDATE inventory SET stock = stock - %s WHERE product_id = %s", (item.qty, item.product_id))
conn.commit()
```

Dos jobs en paralelo procesan pedidos distintos. ¿Cómo lo evito sin serializar los jobs?""",
            },
            {
                "role": "assistant",
                "content": """El mensaje describe un ciclo: el proceso A tiene bloqueada una fila de `inventory` y espera otra que tiene B, mientras B espera la de A. Pasa cuando dos transacciones actualizan **las mismas filas en distinto orden**:

```
Job A (pedido 1: productos 7, 3)        Job B (pedido 2: productos 3, 7)
UPDATE ... product_id = 7   -- lock 7
                                        UPDATE ... product_id = 3   -- lock 3
UPDATE ... product_id = 3   -- espera a B
                                        UPDATE ... product_id = 7   -- espera a A → deadlock
```

Postgres lo detecta tras `deadlock_timeout` (1 s por defecto), aborta a uno de los dos con `SQLSTATE 40P01` y el otro continúa. Que ocurra «varias veces al día» significa que el reintento no existe o que el orden es aleatorio.

**Arreglo principal: bloquear siempre en el mismo orden.** Si todas las transacciones adquieren los locks por `product_id` ascendente, no puede haber ciclo: quien tenga el menor id nunca espera a quien tenga uno mayor.

```python
for item in sorted(order.items, key=lambda i: i.product_id):
    cur.execute(
        "UPDATE inventory SET stock = stock - %s WHERE product_id = %s AND stock >= %s",
        (item.qty, item.product_id, item.qty),
    )
    if cur.rowcount == 0:
        raise InsufficientStock(item.product_id)
conn.commit()
```

Mejor aún, una sola sentencia que actualiza todas las líneas y deja al motor el orden; con `ORDER BY` explícito en el `SELECT ... FOR UPDATE` previo garantizas la secuencia de bloqueo:

```sql
WITH lines AS (
    SELECT product_id, qty
    FROM order_items
    WHERE order_id = %s
),
locked AS (
    SELECT i.product_id
    FROM inventory i
    JOIN lines l USING (product_id)
    ORDER BY i.product_id
    FOR UPDATE OF i
)
UPDATE inventory i
SET stock = i.stock - l.qty
FROM lines l
WHERE i.product_id = l.product_id
  AND i.stock >= l.qty
RETURNING i.product_id, i.stock;
```

Un `UPDATE ... FROM` a secas no garantiza el orden de bloqueo (depende del plan); el `SELECT ... ORDER BY ... FOR UPDATE` previo sí.

**Red de seguridad: reintentar ante `40P01`.** Un deadlock es un error transitorio por diseño: el motor eligió una víctima y espera que vuelva a intentarlo.

```python
import psycopg
from psycopg.errors import DeadlockDetected, SerializationFailure

def run_with_retry(fn, attempts=3):
    for attempt in range(attempts):
        try:
            return fn()
        except (DeadlockDetected, SerializationFailure):
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (2 ** attempt))   # backoff pequeño con jitter si quieres
```

`fn` debe contener la transacción **completa** (`BEGIN` a `COMMIT`); reintentar solo el `UPDATE` fallido dentro de una transacción abortada no es posible.

**Lo que no hace falta:** bajar `deadlock_timeout` (solo detecta antes, no evita), ni `LOCK TABLE inventory` (serializa todos los jobs, que es lo que querías evitar), ni `SERIALIZABLE` (aquí no aporta nada: el ciclo de locks de fila es el mismo).

Para confirmar que el orden era el problema, mira en el log del servidor las dos sentencias (`log_lock_waits = on` las muestra con la consulta): verás los mismos `product_id` en orden inverso. Tras el cambio, `SELECT count(*) FROM pg_stat_database WHERE deadlocks > 0` debe dejar de crecer.""",
            },
        ]
    },
    # 10) upsert en los tres dialectos (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Necesito un «insertar o actualizar si ya existe» para una tabla `settings(user_id, key, value)` con unique en (user_id, key). ¿Cómo se hace en Postgres, MySQL y SQLite? Trabajo con los tres según el proyecto."},
            {
                "role": "assistant",
                "content": """Los tres tienen *upsert* nativo, con sintaxis distinta pero la misma idea: intenta insertar; si choca con una restricción única, actualiza en su lugar.

**PostgreSQL** (9.5+) y **SQLite** (3.24+) comparten la sintaxis `ON CONFLICT`:

```sql
INSERT INTO settings (user_id, key, value)
VALUES (42, 'theme', 'dark')
ON CONFLICT (user_id, key)
DO UPDATE SET value = EXCLUDED.value,
              updated_at = now()
RETURNING user_id, key, value;
```

- `ON CONFLICT (user_id, key)` nombra las columnas del índice único que arbitra el conflicto. Debe existir un índice único o una `PRIMARY KEY` exactamente sobre esas columnas.
- `EXCLUDED` es la fila que **intentaste** insertar; `settings.value` sería la existente. Puedes combinarlas: `value = coalesce(EXCLUDED.value, settings.value)`.
- `RETURNING` devuelve la fila final tanto si insertó como si actualizó. En SQLite, `RETURNING` existe desde 3.35 y `now()` es `CURRENT_TIMESTAMP`.
- Para «insertar solo si no existe» sin tocar lo existente: `ON CONFLICT (user_id, key) DO NOTHING`.

**MySQL / MariaDB:**

```sql
INSERT INTO settings (user_id, key, value)
VALUES (42, 'theme', 'dark')
AS new
ON DUPLICATE KEY UPDATE value = new.value, updated_at = NOW();
```

- No eliges qué índice arbitra: cualquier `UNIQUE` o `PRIMARY KEY` que choque dispara la actualización. Si la tabla tiene varias restricciones únicas, puede actualizar una fila que no esperabas.
- El alias `AS new` (MySQL 8.0.19+) sustituye al antiguo `VALUES(value)`, hoy obsoleto. En MariaDB sigue siendo `VALUES(value)`.
- El valor de retorno de «filas afectadas» es 1 si insertó, **2** si actualizó, 0 si actualizó sin cambios. Útil para saber qué pasó sin consulta extra.
- `INSERT IGNORE` es el equivalente aproximado de `DO NOTHING`, pero ignora también otros errores (truncamientos, tipos); evítalo.

Dos efectos que conviene conocer en los tres:

1. **Consume ids aunque actualice.** Si la tabla tiene una columna `serial`/`AUTO_INCREMENT`, cada intento fallido de inserción gasta un valor de la secuencia. Los huecos son inofensivos; si ves ids que saltan de 100 en 100 es esto, no un bug.
2. **Escribe la fila aunque el valor no cambie.** Un `DO UPDATE` sobre una fila idéntica genera una versión nueva (en Postgres, trabajo para `VACUUM`; dispara triggers de `UPDATE`). Si es frecuente, añade `WHERE settings.value IS DISTINCT FROM EXCLUDED.value` al `DO UPDATE`.

Comprobación: ejecuta la sentencia dos veces seguidas; la primera inserta y la segunda deja una única fila con el mismo valor. `SELECT count(*) FROM settings WHERE user_id = 42 AND key = 'theme'` debe dar 1.""",
            },
            {"role": "user", "content": "¿Y el upsert es seguro si dos procesos insertan la misma clave a la vez? Antes hacía SELECT y luego INSERT o UPDATE según el caso y a veces me saltaba el unique."},
            {
                "role": "assistant",
                "content": """Sí, y esa es la razón principal para usarlo. Tu patrón anterior tiene una **ventana de carrera**:

```
P1: SELECT ... WHERE user_id = 42 AND key = 'theme'   -- no existe
P2: SELECT ... WHERE user_id = 42 AND key = 'theme'   -- no existe
P1: INSERT ...                                        -- ok
P2: INSERT ...                                        -- unique violation
```

Entre el `SELECT` y el `INSERT` de un proceso, el otro puede insertar. Ninguna transacción normal lo evita, porque en `READ COMMITTED` el segundo `SELECT` no ve la fila no confirmada del primero.

`INSERT ... ON CONFLICT` es **atómico** respecto al índice único: Postgres intenta insertar, y si en ese preciso momento detecta la entrada (incluida una no confirmada de otra transacción), espera a que esa transacción termine y entonces decide: si confirmó, actualiza; si abortó, inserta. No hay ventana. MySQL con `ON DUPLICATE KEY UPDATE` e InnoDB se comporta igual gracias a los bloqueos del índice único.

Lo que sigue sin estar garantizado, y suele sorprender:

1. **El orden entre dos upserts concurrentes es arbitrario.** Si P1 escribe `dark` y P2 escribe `light` al mismo tiempo, el valor final es el del que llegó segundo, y no controlas cuál. Si importa, añade una versión o un `updated_at` y condiciona: `DO UPDATE SET value = EXCLUDED.value WHERE EXCLUDED.updated_at > settings.updated_at`.

2. **Upserts de varias filas en distinto orden pueden interbloquearse.** `INSERT ... VALUES (a), (b) ON CONFLICT` en una transacción y `VALUES (b), (a)` en otra pueden producir `deadlock detected`, exactamente como dos `UPDATE` en orden cruzado. Ordena las filas por la clave antes de insertar.

3. **Solo un índice único arbitra.** En Postgres, si la fila choca con **otra** restricción única distinta de la que pusiste en `ON CONFLICT (...)`, obtienes el error de unicidad normal. Es el comportamiento correcto: el upsert solo maneja el conflicto que le has descrito.

Para el caso «insertar si no existe y devolverme la fila, exista o no», que es tu `SELECT`-luego-`INSERT` de antes:

```sql
INSERT INTO settings (user_id, key, value)
VALUES (42, 'theme', 'dark')
ON CONFLICT (user_id, key) DO UPDATE SET value = settings.value   -- no cambia nada
RETURNING *;
```

El `DO UPDATE` sin cambios reales es el truco para que `RETURNING` devuelva también la fila existente (con `DO NOTHING`, `RETURNING` no devuelve nada en caso de conflicto). Cuesta una escritura; si eso te importa, haz `DO NOTHING` y un `SELECT` después solo cuando no haya devuelto fila.

Prueba de la carrera: dos sesiones `psql`, `BEGIN` en ambas, el upsert en la primera sin `COMMIT`, el mismo upsert en la segunda (se queda esperando, no falla), `COMMIT` en la primera: la segunda termina como actualización. Con tu patrón viejo, la segunda habría fallado con `duplicate key value violates unique constraint`.""",
            },
        ]
    },
    # 11) keyset pagination (en inglés)
    {
        "messages": [
            {"role": "user", "content": "Our API paginates with `LIMIT 50 OFFSET n` and page 2000 takes seconds while page 1 is instant. Also users see duplicated or skipped rows when new records arrive. What's the proper way to paginate in PostgreSQL?"},
            {
                "role": "assistant",
                "content": """Both symptoms are inherent to `OFFSET`, not something you can tune away. Switch to **keyset pagination** (also called cursor or seek pagination): instead of "skip n rows", you ask for "rows after the last one I saw".

Why `OFFSET` degrades: `OFFSET 100000` makes the server read and discard 100 000 rows before returning 50. Cost grows linearly with the page number. And because each request is a fresh query, an insert between two requests shifts every row by one, so the boundary row either repeats or disappears.

Keyset version, ordering by creation time with the primary key as tiebreaker:

```sql
-- first page
SELECT id, created_at, title
FROM posts
ORDER BY created_at DESC, id DESC
LIMIT 50;

-- next page: pass the last (created_at, id) of the previous page
SELECT id, created_at, title
FROM posts
WHERE (created_at, id) < ($1, $2)
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

Supporting index, same columns and same direction:

```sql
CREATE INDEX CONCURRENTLY posts_created_id_idx ON posts (created_at DESC, id DESC);
```

With it, every page is an `Index Scan` that starts at the cursor and reads 50 entries, whether it's page 1 or page 2000. Plan check: no `Sort` node, and `Rows Removed by Filter` at zero.

Details that matter:

- **The row comparison `(created_at, id) < ($1, $2)`** is real tuple comparison, not two separate conditions. It means "earlier timestamp, or same timestamp with smaller id", which is exactly the next position in the sort order. Writing it as `created_at < $1 OR (created_at = $1 AND id < $2)` is equivalent but easier for the planner to get wrong; the tuple form uses the index directly.
- **The tiebreaker is mandatory.** Two posts with the same `created_at` and only `created_at < $1` would skip the second one. Any unique column works; the primary key is the natural choice.
- **The cursor is opaque to the client.** Encode `(created_at, id)` as a base64 token and return it as `next_cursor`. Clients can't jump to an arbitrary page number, which is the one thing keyset can't do; for a UI that needs "page 37", keep `OFFSET` for small page numbers and cap it (`OFFSET` beyond 10 000 returns an error), which is what most large APIs do.
- **Stable against inserts.** A new post gets a newer `created_at`; it appears at the top of a fresh listing but never shifts the rows after your cursor. No duplicates, no gaps.
- **Deletes are fine too**: the cursor is a position in the order, not a row that must exist.

If the sort key is nullable, `NULLS` sort before or after everything and the tuple comparison won't see them; either make the column `NOT NULL` or use `coalesce` consistently in both the index and the query.

Quick benchmark on a 5M-row table: `OFFSET 1000000 LIMIT 50` reads about a million index entries (hundreds of ms); the keyset query reads 50 (sub-millisecond). `EXPLAIN (ANALYZE, BUFFERS)` shows the difference in `shared hit` pages.

Same technique works in MySQL and SQLite; MySQL supports row comparison but doesn't always use the index for it, so there you may need the expanded `OR` form.""",
            },
        ]
    },
    # 12) JSONB (intermedio)
    {
        "messages": [
            {"role": "user", "content": "Guardo los atributos variables de cada producto (talla, color, voltaje, lo que sea) en una columna JSONB. ¿Cómo consulto y indexo eso bien? ¿O debería normalizarlo en una tabla de atributos?"},
            {
                "role": "assistant",
                "content": """Para atributos **heterogéneos y de consulta ocasional**, JSONB es la elección correcta; para los que filtras siempre o tienen reglas de integridad, una columna propia. La tabla EAV (entidad-atributo-valor) es la peor de las tres: consultas con un join por atributo, sin tipos y sin restricciones.

Supón:

```sql
CREATE TABLE products (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       text NOT NULL,
    price      numeric(10,2) NOT NULL,
    attrs      jsonb NOT NULL DEFAULT '{}'
);

INSERT INTO products (name, price, attrs) VALUES
('Camiseta', 12.00, '{"size": "M", "color": "red", "tags": ["cotton", "summer"]}'),
('Taladro',  89.90, '{"voltage": 18, "cordless": true}');
```

**Operadores que usarás:**

```sql
-- Extraer: -> devuelve jsonb, ->> devuelve text
SELECT name, attrs->>'color' AS color, (attrs->>'voltage')::int AS voltage FROM products;

-- Contención: ¿attrs incluye este subdocumento?  (el operador indexable)
SELECT name FROM products WHERE attrs @> '{"color": "red"}';
SELECT name FROM products WHERE attrs @> '{"tags": ["cotton"]}';   -- elemento en array

-- ¿Existe la clave?
SELECT name FROM products WHERE attrs ? 'voltage';

-- Rutas y comparaciones numéricas (PG 12+)
SELECT name FROM products WHERE attrs @? '$.voltage ? (@ >= 18)';

-- Modificar sin reescribir todo
UPDATE products SET attrs = attrs || '{"color": "blue"}' WHERE id = 1;
UPDATE products SET attrs = attrs - 'color' WHERE id = 1;
UPDATE products SET attrs = jsonb_set(attrs, '{dimensions,width}', '30') WHERE id = 2;
```

**Índice:** un GIN sobre la columna acelera `@>`, `?`, `@?` y `@@` para cualquier clave, sin saber de antemano cuáles existen:

```sql
CREATE INDEX CONCURRENTLY products_attrs_idx ON products USING gin (attrs);
```

Con la clase de operador `jsonb_path_ops` (`USING gin (attrs jsonb_path_ops)`) el índice es más pequeño y más rápido para `@>`, pero deja de soportar `?` (existencia de clave). Elige según lo que consultes.

Lo que el GIN **no** acelera: `attrs->>'color' = 'red'`. Ese predicado extrae texto y compara; para indexarlo necesitas un índice de expresión B-tree:

```sql
CREATE INDEX CONCURRENTLY products_color_idx ON products ((attrs->>'color'));
```

Y los rangos numéricos (`(attrs->>'voltage')::int > 12`) tampoco; mismo remedio con un índice de expresión sobre el cast.

**Cuándo sacar un atributo del JSON a una columna:** cuando cumple cualquiera de estas:

1. Lo filtras u ordenas en la mayoría de las consultas (`price`, `category`).
2. Necesita restricción: `NOT NULL`, `CHECK`, clave foránea, unicidad.
3. Tiene un tipo que importa (fechas, dinero): dentro del JSON es texto o número de doble precisión, y `numeric` no existe.
4. Lo actualizas con frecuencia de forma independiente: cada `UPDATE` de un JSONB reescribe la columna entera (y la fila, por el MVCC de Postgres), lo que con documentos grandes se nota.

Puedes imponer algo de estructura sin normalizar: `CHECK (jsonb_typeof(attrs->'voltage') IN ('number', 'null'))` o una columna generada para lo que necesites indexar «como columna»:

```sql
ALTER TABLE products ADD COLUMN color text GENERATED ALWAYS AS (attrs->>'color') STORED;
```

Comprobación de que el índice entra: `EXPLAIN SELECT name FROM products WHERE attrs @> '{"color": "red"}'` debe mostrar `Bitmap Index Scan on products_attrs_idx`. Si ves `Seq Scan` con una tabla pequeña es normal (el planificador prefiere leerla entera); prueba con `SET enable_seqscan = off` solo para verificar que el índice es utilizable.""",
            },
        ]
    },
    # 13) migraciones seguras sin bloquear (avanzado, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo que añadir una columna `tenant_id NOT NULL` a una tabla de 300 millones de filas en Postgres 15, en producción, sin tumbar la API. ¿Cuál es la secuencia segura?"},
            {
                "role": "assistant",
                "content": """La secuencia segura separa cada paso que pueda tomar un bloqueo largo en una sentencia corta, y nunca reescribe la tabla ni valida 300 millones de filas bajo un bloqueo exclusivo.

**Paso 0: protege cada sentencia con `lock_timeout`.** Un `ALTER TABLE` necesita `ACCESS EXCLUSIVE`; si una consulta larga tiene la tabla abierta, el `ALTER` espera y, mientras espera, **bloquea a todos los que lleguen detrás**. Con `lock_timeout` el `ALTER` se rinde en vez de formar la cola; lo reintentas.

```sql
SET lock_timeout = '3s';
```

**Paso 1: añade la columna como nullable, con default.** Desde PG 11, `ADD COLUMN ... DEFAULT <constante>` no reescribe la tabla: el valor se guarda en el catálogo y las filas viejas lo devuelven al leerse. Es instantáneo.

```sql
ALTER TABLE orders ADD COLUMN tenant_id bigint DEFAULT 0;
```

Si no hay un valor por defecto válido (lo normal con un `tenant_id` real), añádela sin default y rellena después:

```sql
ALTER TABLE orders ADD COLUMN tenant_id bigint;
```

**Paso 2: rellena por lotes, fuera de transacción larga.** Un `UPDATE` de 300 M filas en una transacción bloquea cada fila durante horas, genera un *bloat* enorme y puede agotar el WAL. Lotes de 10-50 k filas por clave primaria, con pausa:

```sql
UPDATE orders SET tenant_id = c.tenant_id
FROM customers c
WHERE orders.customer_id = c.id
  AND orders.id BETWEEN $1 AND $2
  AND orders.tenant_id IS NULL;
```

Ejecutado desde un script que avanza `$1..$2` y duerme 50-100 ms entre lotes para que `autovacuum` y el tráfico real respiren. Haz que el código de la aplicación **ya escriba `tenant_id`** en las inserciones nuevas antes de empezar el relleno; si no, nunca terminas.

**Paso 3: la restricción `NOT NULL` sin escaneo bloqueante.** `ALTER TABLE ... SET NOT NULL` tiene que verificar todas las filas con `ACCESS EXCLUSIVE`. El truco (PG 12+): primero una `CHECK` sin validar, luego validarla (solo `SHARE UPDATE EXCLUSIVE`, compatible con lecturas y escrituras), y entonces el `SET NOT NULL` reconoce la `CHECK` y no escanea.

```sql
ALTER TABLE orders ADD CONSTRAINT orders_tenant_not_null
    CHECK (tenant_id IS NOT NULL) NOT VALID;          -- instantáneo

ALTER TABLE orders VALIDATE CONSTRAINT orders_tenant_not_null;   -- escaneo largo, sin bloquear tráfico

ALTER TABLE orders ALTER COLUMN tenant_id SET NOT NULL;          -- instantáneo: usa la CHECK como prueba

ALTER TABLE orders DROP CONSTRAINT orders_tenant_not_null;       -- ya no hace falta
```

**Paso 4: índice y clave foránea, también sin bloquear.**

```sql
CREATE INDEX CONCURRENTLY orders_tenant_id_idx ON orders (tenant_id);

ALTER TABLE orders ADD CONSTRAINT orders_tenant_fk
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT orders_tenant_fk;
```

`CONCURRENTLY` no puede ir dentro de una transacción (tu herramienta de migraciones debe permitir desactivar la transacción para ese paso) y, si falla, deja un índice `INVALID` que hay que borrar antes de repetir.

**Paso 5: quita el default temporal** si lo pusiste en el paso 1: `ALTER TABLE orders ALTER COLUMN tenant_id DROP DEFAULT;`.

Lo que **no** debes hacer, y por qué:

- `ALTER TABLE orders ADD COLUMN tenant_id bigint NOT NULL DEFAULT 0` de una vez: funciona (PG 11+ no reescribe), pero te deja 300 M filas con un tenant falso y la pregunta de cómo corregirlas sin lo anterior.
- `ADD COLUMN ... NOT NULL` sin default: falla inmediatamente si la tabla tiene filas.
- Todo en una sola transacción de migración: el `VALIDATE` y el `CREATE INDEX CONCURRENTLY` lo prohíben, y el `UPDATE` masivo lo convierte en horas de bloqueo.

Para comprobar que ninguna sentencia bloqueó, antes de cada `ALTER` mira `pg_stat_activity` filtrando `wait_event_type = 'Lock'`; con `lock_timeout` activo verás como mucho 3 s de espera y un error reintentable, nunca una cola.

En MySQL 8 el equivalente es `ALTER TABLE ... ADD COLUMN ..., ALGORITHM=INSTANT` para el paso 1 y `pt-online-schema-change` o `gh-ost` para los que no admiten `INSTANT`; en SQLite, `ALTER TABLE ADD COLUMN` es siempre instantáneo pero no hay `NOT NULL` sin default ni validación diferida, así que se recrea la tabla.""",
            },
        ]
    },
    # 14) normalización vs desnormalización (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Me dicen que mi esquema de pedidos está «mal normalizado» porque `order_items` guarda `unit_price` cuando ese dato ya está en `products.price`. ¿Es un error de diseño?"},
            {
                "role": "assistant",
                "content": """No. Es una **desnormalización intencional y correcta**, porque `order_items.unit_price` y `products.price` son datos distintos que hoy coinciden por casualidad.

- `products.price` es el precio **actual** de venta. Cambia con el tiempo.
- `order_items.unit_price` es el precio **al que se vendió** esa línea. Es un hecho histórico; no debe cambiar nunca, aunque el producto suba o se descatalogue.

Si quitas la columna y la calculas con un join, el día que subas un precio todas las facturas antiguas cambian retroactivamente. Eso sí es un error de diseño (y, en muchos países, un problema legal).

La regla para decidir qué duplicar: **la normalización elimina redundancia de hechos que son el mismo hecho**. «El nombre del cliente» en dos tablas es el mismo hecho y debe vivir en un sitio. «Precio ahora» y «precio entonces» son dos hechos; que se parezcan no los convierte en uno.

Cosas que sí conviene copiar en una línea de pedido, por la misma razón:

```sql
CREATE TABLE order_items (
    order_id     bigint NOT NULL REFERENCES orders(id),
    line_no      int    NOT NULL,
    product_id   bigint NOT NULL REFERENCES products(id),
    product_name text   NOT NULL,          -- el nombre que vio el cliente
    unit_price   numeric(10,2) NOT NULL,   -- el precio que pagó
    quantity     int    NOT NULL CHECK (quantity > 0),
    tax_rate     numeric(5,4) NOT NULL,    -- el IVA vigente ese día
    PRIMARY KEY (order_id, line_no)
);
```

`product_id` se conserva para enlazar con el catálogo (informes, reposición); los campos copiados preservan el documento tal como se emitió.

Lo que seguiría siendo redundancia **mala** en ese mismo esquema:

- `orders.customer_email` copiado de `customers.email` «para no hacer el join». Si el cliente corrige su correo, ¿cuál es el bueno? Ese dato es el mismo hecho y pertenece a `customers`.
- `orders.total` calculado como suma de líneas y guardado sin ninguna regla que lo mantenga. Si se hace, es por rendimiento, y entonces hay que protegerlo (siguiente mensaje si te interesa).

Una prueba rápida para cualquier columna sospechosa: pregúntate «si el origen cambia mañana, ¿esta copia debe cambiar también?». Si la respuesta es no, es un dato histórico y la copia es correcta. Si es sí, es redundancia y necesita o eliminarse o un mecanismo que la mantenga sincronizada.""",
            },
            {"role": "user", "content": "Vale, pues justo tengo `orders.total` guardado porque la pantalla de listado tarda mucho sumando líneas. ¿Cómo lo mantengo correcto?"},
            {
                "role": "assistant",
                "content": """Tienes tres mecanismos, de más a menos recomendable según el caso.

**1. Calcularlo en la misma transacción que modifica las líneas.** El código que inserta, actualiza o borra líneas recalcula el total del pedido antes de confirmar:

```sql
BEGIN;
INSERT INTO order_items (order_id, line_no, product_id, product_name, unit_price, quantity, tax_rate)
VALUES (501, 3, 77, 'Cable HDMI', 9.90, 2, 0.21);

UPDATE orders o
SET total = s.total
FROM (
    SELECT order_id, SUM(unit_price * quantity * (1 + tax_rate)) AS total
    FROM order_items WHERE order_id = 501 GROUP BY order_id
) s
WHERE o.id = s.order_id;
COMMIT;
```

Es explícito y fácil de probar. Su debilidad: todos los caminos que tocan líneas tienen que acordarse; un script de soporte que borre una línea a mano deja el total desfasado.

**2. Trigger.** Mueve esa obligación a la base de datos, donde ningún camino puede olvidarla:

```sql
CREATE OR REPLACE FUNCTION refresh_order_total() RETURNS trigger AS $$
DECLARE
    target_id bigint := COALESCE(NEW.order_id, OLD.order_id);
BEGIN
    UPDATE orders
    SET total = COALESCE((
        SELECT SUM(unit_price * quantity * (1 + tax_rate))
        FROM order_items WHERE order_id = target_id
    ), 0)
    WHERE id = target_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER order_items_total
AFTER INSERT OR UPDATE OR DELETE ON order_items
FOR EACH ROW EXECUTE FUNCTION refresh_order_total();
```

Si una línea cambia de pedido (`UPDATE` de `order_id`), el `COALESCE(NEW, OLD)` solo refresca el nuevo; para cubrir ese caso raro, refresca ambos cuando difieran. El coste: una suma por cada cambio de línea, y lógica «invisible» desde la aplicación, que conviene documentar junto al esquema.

**3. Vista materializada** si el total solo se necesita en informes y puede ir con retraso:

```sql
CREATE MATERIALIZED VIEW order_totals AS
SELECT order_id, SUM(unit_price * quantity * (1 + tax_rate)) AS total
FROM order_items GROUP BY order_id;
CREATE UNIQUE INDEX ON order_totals (order_id);

REFRESH MATERIALIZED VIEW CONCURRENTLY order_totals;   -- periódico, sin bloquear lecturas
```

Para un listado operativo que el usuario espera al día, no sirve.

Sea cual sea la opción, añade una **comprobación de consistencia** que puedas ejecutar en cualquier momento, porque una columna derivada siempre acaba divergiendo por algún camino imprevisto:

```sql
SELECT o.id, o.total, s.calc
FROM orders o
JOIN (
    SELECT order_id, SUM(unit_price * quantity * (1 + tax_rate)) AS calc
    FROM order_items GROUP BY order_id
) s ON s.order_id = o.id
WHERE o.total <> s.calc;
```

Debe devolver cero filas. Ponla en un job nocturno que avise si no.

Para tu pantalla: con la opción 1 o 2 y un índice `orders (customer_id, created_at DESC)`, el listado deja de tocar `order_items` y pasa a leer una columna. Antes de decidir, mide: si el listado muestra 20 pedidos con 3 líneas de media, la suma en vivo con un índice `order_items (order_id)` quizá ya sea rápida y no necesites desnormalizar.""",
            },
        ]
    },
    # 15) muchos a muchos (principiante)
    {
        "messages": [
            {"role": "user", "content": "¿Cómo modelo que un estudiante puede estar en muchos cursos y un curso tiene muchos estudiantes? Pensé en una columna `courses TEXT` con los ids separados por comas."},
            {
                "role": "assistant",
                "content": """Con una **tabla intermedia** (de unión). La columna con ids separados por comas rompe lo que una base de datos relacional te da gratis: no puedes hacer join, no puedes indexar, no puedes garantizar que el id exista, y «¿qué estudiantes hay en el curso 7?» obliga a leer y partir todas las filas.

```sql
CREATE TABLE students (
    id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  text NOT NULL
);

CREATE TABLE courses (
    id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL
);

CREATE TABLE enrollments (
    student_id  bigint NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id   bigint NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    enrolled_at timestamptz NOT NULL DEFAULT now(),
    grade       numeric(4,2) CHECK (grade BETWEEN 0 AND 10),
    PRIMARY KEY (student_id, course_id)
);

CREATE INDEX enrollments_course_idx ON enrollments (course_id);
```

Cada fila de `enrollments` es una relación «este estudiante está en este curso». Decisiones:

- **Clave primaria compuesta `(student_id, course_id)`**: un estudiante no puede matricularse dos veces en el mismo curso, y el índice de la PK ya resuelve «cursos de un estudiante».
- **Índice extra por `course_id`**: la PK solo sirve para buscar empezando por `student_id`; para «estudiantes de un curso» hace falta el segundo índice.
- **`ON DELETE CASCADE`**: al borrar un curso desaparecen sus matrículas. Si prefieres que la base de datos impida borrar un curso con alumnos, usa el valor por defecto (`NO ACTION`) y fallará con un error de clave foránea.
- **Atributos de la relación** (`enrolled_at`, `grade`) viven aquí, no en ninguna de las dos tablas principales: la nota es *de la matrícula*, no del alumno ni del curso.

Las consultas típicas:

```sql
-- Cursos de un estudiante
SELECT c.title
FROM courses c
JOIN enrollments e ON e.course_id = c.id
WHERE e.student_id = 42;

-- Estudiantes de un curso, con su nota
SELECT s.name, e.grade
FROM students s
JOIN enrollments e ON e.student_id = s.id
WHERE e.course_id = 7
ORDER BY s.name;

-- Cursos con más de 30 matriculados
SELECT c.title, COUNT(*) AS enrolled
FROM courses c
JOIN enrollments e ON e.course_id = c.id
GROUP BY c.id, c.title
HAVING COUNT(*) > 30;

-- Matricular (falla si ya está)
INSERT INTO enrollments (student_id, course_id) VALUES (42, 7);
```

Si algún día necesitas que la relación tenga identidad propia (referenciarla desde otra tabla, por ejemplo `attendance` apuntando a una matrícula concreta), añade un `id` propio y conserva `UNIQUE (student_id, course_id)` para mantener la regla de no duplicar.

Verificación de las restricciones: inserta la misma matrícula dos veces (la segunda debe fallar con `duplicate key`), e inserta un `course_id` inexistente (debe fallar con `violates foreign key constraint`). Con la columna de texto ninguna de las dos cosas habría fallado.""",
            },
        ]
    },
    # 16) árboles con CTE recursiva (intermedio)
    {
        "messages": [
            {"role": "user", "content": "Tengo categorías anidadas con `parent_id`. Necesito sacar todos los descendientes de una categoría, la ruta completa de cada una (`Ropa > Hombre > Camisas`) y su profundidad. ¿Cómo lo hago sin bucles en la aplicación?"},
            {
                "role": "assistant",
                "content": """Con una **CTE recursiva**. Empieza por la raíz que te interesa y en cada vuelta añade los hijos de las filas encontradas en la anterior, acumulando ruta y profundidad.

```sql
CREATE TABLE categories (
    id        bigint PRIMARY KEY,
    parent_id bigint REFERENCES categories(id),
    name      text NOT NULL
);
CREATE INDEX categories_parent_idx ON categories (parent_id);
```

**Descendientes de la categoría 1, con ruta y profundidad:**

```sql
WITH RECURSIVE tree AS (
    -- caso base: el nodo de partida
    SELECT id, parent_id, name,
           name::text        AS path,
           0                 AS depth,
           ARRAY[id]         AS ids
    FROM categories
    WHERE id = 1

    UNION ALL

    -- paso recursivo: hijos de lo encontrado en la vuelta anterior
    SELECT c.id, c.parent_id, c.name,
           t.path || ' > ' || c.name,
           t.depth + 1,
           t.ids || c.id
    FROM categories c
    JOIN tree t ON c.parent_id = t.id
    WHERE NOT c.id = ANY(t.ids)        -- protección contra ciclos
)
SELECT id, path, depth
FROM tree
ORDER BY path;
```

Cómo funciona: el motor ejecuta el caso base, guarda el resultado como «vuelta 0», ejecuta el paso recursivo **solo contra las filas de la vuelta anterior**, y repite hasta que una vuelta no produce filas. No es recursión real; es iteración hasta punto fijo. `UNION ALL` conserva duplicados y es más rápido; `UNION` los elimina y sirve de freno adicional, pero con la protección de ciclos no hace falta.

**La protección contra ciclos** importa: si por un error de datos `parent_id` apunta a un descendiente, sin ella la consulta no termina nunca. El array `ids` acumula el camino y rechaza volver a un nodo visitado. Desde PostgreSQL 14 hay sintaxis propia que hace lo mismo:

```sql
WITH RECURSIVE tree AS (...)
CYCLE id SET is_cycle USING path_ids
```

**Ancestros** (la ruta hacia arriba) es la misma consulta con el join invertido: parte del nodo y sube por `c.id = t.parent_id`. Y para toda la jerarquía desde las raíces, el caso base es `WHERE parent_id IS NULL`.

**Ordenar como un árbol** (cada hijo debajo de su padre, hermanos por nombre) usando el array de ids no vale, porque ordena por id, no por nombre. Acumula una ruta ordenable:

```sql
ARRAY[name]            AS sort_path      -- caso base
t.sort_path || c.name  AS sort_path      -- paso recursivo
ORDER BY sort_path
```

Rendimiento: cada vuelta hace un join indexado por `parent_id`, así que el coste es proporcional al tamaño del subárbol, no de la tabla. Para árboles muy consultados y poco modificados (cientos de miles de nodos, lectura constante de rutas) el patrón alternativo es una columna `path` materializada con el tipo `ltree` (`'1.4.17'`) e índice GiST, que responde «descendientes de X» con `path <@ '1.4'` sin recursión; a cambio, mover un subárbol exige reescribir las rutas de todos sus nodos.

Comprobación con cuatro filas (`Ropa` → `Hombre` → `Camisas`, y `Mujer` colgando de `Ropa`): la consulta desde `id = 1` debe devolver 4 filas, con `Ropa > Hombre > Camisas` a profundidad 2 y `Ropa > Mujer` a profundidad 1. Si cambias el `parent_id` de `Ropa` para que apunte a `Camisas`, la consulta sigue terminando gracias al `NOT ... = ANY(t.ids)`.""",
            },
        ]
    },
    # 17) inyección SQL (system variante: revisor de seguridad, el usuario trae código)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de seguridad estricto. Señala cada vulnerabilidad con su impacto y da el código corregido."},
            {
                "role": "user",
                "content": """Endpoint de búsqueda en Flask + psycopg. ¿Ves algo raro?

```python
@app.get("/users")
def search_users():
    q = request.args.get("q", "")
    sort = request.args.get("sort", "name")
    sql = f"SELECT id, name, email FROM users WHERE name LIKE '%{q}%' ORDER BY {sort}"
    with conn.cursor() as cur:
        cur.execute(sql)
        return jsonify(cur.fetchall())
```""",
            },
            {
                "role": "assistant",
                "content": """Dos inyecciones SQL, una en cada parámetro, y una fuga menor.

**1. `q` se interpola en la cadena.** Un valor como `' OR 1=1 --` convierte la consulta en `... WHERE name LIKE '%' OR 1=1 --%'` y devuelve toda la tabla. Con `'; DROP TABLE users; --` o `' UNION SELECT id, password_hash, email FROM credentials --` el impacto es pérdida o exfiltración de datos. Impacto: crítico.

**2. `sort` se interpola sin validar.** `ORDER BY` no admite parámetros (un parámetro sería un valor constante, no un nombre de columna), así que mucha gente lo deja interpolado. `sort=(SELECT CASE WHEN (SELECT password_hash FROM credentials WHERE id=1) LIKE 'a%' THEN name ELSE email END)` es una inyección ciega que extrae datos carácter a carácter observando el orden. Impacto: alto.

**3. Fuga de información:** si la consulta falla, Flask en modo debug devuelve la traza con el SQL. Menor, pero facilita las dos anteriores.

Versión corregida:

```python
from psycopg import sql

ALLOWED_SORT = {"name": "name", "email": "email", "created": "created_at"}

def escape_like(value: str) -> str:
    # % y _ son comodines de LIKE; el usuario los escribe como texto literal
    return value.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_")

@app.get("/users")
def search_users():
    q = request.args.get("q", "")[:100]
    sort_key = request.args.get("sort", "name")
    column = ALLOWED_SORT.get(sort_key)
    if column is None:
        abort(400, "invalid sort")

    query = sql.SQL(
        "SELECT id, name, email FROM users WHERE name ILIKE %s ESCAPE '\\\\' ORDER BY {} LIMIT 100"
    ).format(sql.Identifier(column))

    with conn.cursor() as cur:
        cur.execute(query, (f"%{escape_like(q)}%",))
        return jsonify(cur.fetchall())
```

Qué hace cada cambio:

- **Parámetro `%s` para el valor.** El driver envía la consulta y el valor por separado; el servidor nunca interpreta el valor como SQL. Esto es lo que elimina la inyección 1. No es «escapar comillas»: es que el texto jamás se concatena.
- **Lista blanca para `sort`.** El nombre de columna se elige de un diccionario cerrado; cualquier otra cosa es un 400. `sql.Identifier` lo entrecomilla correctamente, pero la protección real es la lista: sin ella, `sql.Identifier("name; DROP")` produce un identificador raro, no una inyección, aunque sigue siendo un error.
- **Escapado de `%` y `_`.** No es seguridad, es corrección: sin ello, buscar `50%` coincide con cualquier cosa que empiece por 50. `ESCAPE '\\'` declara el carácter de escape explícitamente.
- **`LIMIT 100` y recorte de `q`.** Evita que una búsqueda de `%` devuelva millones de filas (denegación de servicio barata).

El patrón se aplica a cualquier parte **estructural** de la consulta (columnas, tablas, dirección `ASC`/`DESC`, nombres de esquema): lista blanca en código y composición con `sql.Identifier`/`sql.SQL`; nunca el texto del usuario. Para valores, siempre parámetros, incluso cuando «solo es un número» (`int(request.args["id"])` valida, pero el parámetro sigue siendo la forma correcta de enviarlo).

Prueba de regresión que debe pasar tras el cambio:

```python
def test_search_is_not_injectable(client):
    r = client.get("/users", query_string={"q": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json == []          # busca ese texto literal, no inyecta

    r = client.get("/users", query_string={"sort": "name; DROP TABLE users"})
    assert r.status_code == 400
```

Y un control más amplio: `grep -rn "f\\"SELECT\\|f'SELECT\\|% (" src/` para encontrar el resto de consultas construidas con formato de cadenas.""",
            },
        ]
    },
    # 18) constraints y triggers (intermedio)
    {
        "messages": [
            {"role": "user", "content": "¿Qué restricciones debería poner en una tabla de reservas de salas (room_id, starts_at, ends_at, user_id) para que la base de datos no deje meter datos incoherentes? ¿Y vale la pena un trigger para `updated_at`?"},
            {
                "role": "assistant",
                "content": """Pon en la base de datos todas las reglas que no dependan de contexto de negocio: son las únicas que ningún camino (API, script, migración, acceso manual) puede saltarse.

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE bookings (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id    bigint NOT NULL REFERENCES rooms(id),
    user_id    bigint NOT NULL REFERENCES users(id),
    starts_at  timestamptz NOT NULL,
    ends_at    timestamptz NOT NULL,
    status     text NOT NULL DEFAULT 'confirmed'
               CHECK (status IN ('confirmed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT bookings_time_order CHECK (ends_at > starts_at),
    CONSTRAINT bookings_max_length CHECK (ends_at - starts_at <= interval '8 hours'),

    -- dos reservas confirmadas de la misma sala no pueden solaparse
    CONSTRAINT bookings_no_overlap EXCLUDE USING gist (
        room_id WITH =,
        tstzrange(starts_at, ends_at, '[)') WITH &&
    ) WHERE (status = 'confirmed')
);
```

Qué hace cada una:

- **`NOT NULL` y `REFERENCES`**: lo básico; una reserva sin sala o de un usuario inexistente no existe.
- **`CHECK (ends_at > starts_at)`**: una `CHECK` puede mirar varias columnas de la misma fila. Es la primera restricción que la gente olvida y la que produce reservas de duración negativa.
- **`EXCLUDE ... WITH &&`**: es la joya. Una `UNIQUE` solo sabe de igualdad; `EXCLUDE` generaliza a cualquier operador: aquí «misma sala **y** rangos que se solapan» está prohibido. Resuelve la carrera clásica (dos usuarios reservando a la vez el mismo hueco) dentro del motor, sin `SELECT FOR UPDATE` ni comprobaciones en la aplicación. El rango `'[)'` (cerrado-abierto) permite que una reserva termine a las 10:00 y otra empiece a las 10:00. `btree_gist` es necesario para que `room_id WITH =` entre en un índice GiST.
- **`WHERE (status = 'confirmed')`**: las canceladas no bloquean el hueco. Es una restricción parcial, igual que un índice parcial.

Lo que **no** va en restricciones: «un usuario no puede tener más de 3 reservas activas» o «solo se reserva con 30 días de antelación» dependen de políticas que cambian y a veces tienen excepciones; eso vive en la aplicación (o en un trigger, si es inamovible).

**Trigger para `updated_at`:** sí, vale la pena, precisamente porque los ORMs lo hacen solo cuando pasan por el ORM. Una función reutilizable para todas las tablas:

```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bookings_set_updated_at
BEFORE UPDATE ON bookings
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION set_updated_at();
```

`BEFORE UPDATE` porque modifica la fila antes de escribirla (en `AFTER` ya es tarde). La cláusula `WHEN` evita tocar `updated_at` en actualizaciones que no cambian nada.

Criterio para triggers en general: úsalos para **invariantes técnicos** (auditoría, marcas de tiempo, mantener una columna derivada) y evita meter lógica de negocio: son invisibles desde el código, difíciles de probar y sorprenden a quien hace un `UPDATE` a mano.

Verificación de la exclusión, en dos sentencias:

```sql
INSERT INTO bookings (room_id, user_id, starts_at, ends_at) VALUES (1, 10, '2024-06-01 09:00+02', '2024-06-01 10:00+02');
INSERT INTO bookings (room_id, user_id, starts_at, ends_at) VALUES (1, 11, '2024-06-01 09:30+02', '2024-06-01 11:00+02');
-- ERROR: conflicting key value violates exclusion constraint "bookings_no_overlap"
```

Y una tercera de 10:00 a 11:00 debe entrar sin error.""",
            },
        ]
    },
    # 19) fechas y zonas horarias (multiturno, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Un informe de «ventas por día» en Postgres da números distintos según desde qué servidor lo ejecuto. La columna es `timestamp` y agrupo por `created_at::date`. ¿Qué está pasando?"},
            {
                "role": "assistant",
                "content": """Dos problemas combinados: el tipo de la columna y cómo se decide «qué día es».

**El tipo.** `timestamp` (sin zona, `timestamp without time zone`) guarda una hora de pared sin decir de dónde. `2024-05-01 23:30` no es un instante; es un número que alguien escribió. Si el servidor de la API en Madrid escribe su hora local y el de Bogotá la suya, en la misma columna conviven valores incomparables. Y al leer, `::date` corta por la medianoche de ese «reloj sin zona», que no es el de nadie en concreto.

`timestamptz` (`timestamp with time zone`) guarda un **instante** (internamente en UTC) y lo convierte a la zona de la sesión al mostrarlo o al truncarlo. Es lo que un `created_at` significa.

**El agrupado.** Con `timestamptz`, `created_at::date` usa la zona de la **sesión** (`SHOW timezone`), que depende de la configuración del cliente o del servidor desde el que lanzas el informe. Dos servidores con `timezone` distinto producen cortes de día distintos: ahí está tu diferencia. La solución es decir en qué zona se define el día, explícitamente:

```sql
SELECT
    (created_at AT TIME ZONE 'Europe/Madrid')::date AS day,
    SUM(total) AS sales
FROM orders
GROUP BY 1
ORDER BY 1;
```

`timestamptz AT TIME ZONE 'Europe/Madrid'` devuelve la hora de pared en Madrid como `timestamp` sin zona; truncarlo a `date` da el día de negocio en Madrid, lo ejecute quien lo ejecute.

Migración de la columna, sabiendo en qué zona se escribieron los valores antiguos (supongamos Madrid):

```sql
ALTER TABLE orders
    ALTER COLUMN created_at TYPE timestamptz
    USING created_at AT TIME ZONE 'Europe/Madrid';
```

Aquí `AT TIME ZONE` hace la operación inversa: «este reloj de pared era de Madrid, conviértelo a instante». Es el mismo operador con dos significados según el tipo de entrada, que es la trampa número uno de esta área:

| Entrada | `x AT TIME ZONE 'Z'` devuelve | Significa |
|---|---|---|
| `timestamp` (sin zona) | `timestamptz` | «interpreta x como hora de pared de Z» |
| `timestamptz` | `timestamp` (sin zona) | «muestra x como hora de pared de Z» |

Si los valores antiguos los escribieron servidores en zonas distintas, no hay conversión correcta posible: tienes que averiguar qué servidor escribió cada fila (por rango de fechas, por un campo de origen) y convertir por tramos.

Para que no vuelva a pasar: en la aplicación, genera siempre instantes (`now()` en SQL, `datetime.now(timezone.utc)` en Python, `DateTimeOffset.UtcNow` en .NET) y deja que `timestamptz` haga el resto. Y en el informe, la zona de negocio es un parámetro explícito, nunca «la del servidor».

Comprobación: inserta una fila con `'2024-05-01 23:30+02'` y otra con `'2024-05-02 00:30+02'`; con la consulta de arriba caen en días distintos (1 y 2 de mayo) desde cualquier servidor. Con `SET timezone = 'UTC'` y `created_at::date` a secas, las dos caerían en el 1 de mayo.""",
            },
            {"role": "user", "content": "¿Y en MySQL? Tengo otro proyecto con DATETIME y el mismo tipo de informe."},
            {
                "role": "assistant",
                "content": """MySQL tiene dos tipos y ninguno es exactamente `timestamptz`:

| Tipo | Qué guarda | Convierte según la zona de sesión | Rango |
|---|---|---|---|
| `DATETIME` | Reloj de pared, sin zona | **No**: devuelve lo que se escribió | 1000-9999 |
| `TIMESTAMP` | Instante (UTC internamente) | Sí, al escribir y al leer | 1970-2038 |

`DATETIME` es el equivalente del `timestamp` sin zona de Postgres y tiene el mismo problema: el valor significa lo que signifique la zona del proceso que lo escribió. `TIMESTAMP` se comporta como `timestamptz`, pero termina en enero de 2038 (32 bits), lo que descarta fechas futuras largas (vencimientos a 20 años).

La convención que funciona con `DATETIME`: **la aplicación escribe siempre UTC** y el informe convierte explícitamente.

```sql
SELECT
    DATE(CONVERT_TZ(created_at, '+00:00', 'Europe/Madrid')) AS day,
    SUM(total) AS sales
FROM orders
GROUP BY day
ORDER BY day;
```

`CONVERT_TZ(valor, desde, hasta)` necesita las tablas de zonas horarias cargadas en el servidor (`mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql mysql`); si no están, con nombres como `'Europe/Madrid'` devuelve `NULL` y el informe sale vacío sin error. Con desplazamientos fijos (`'+02:00'`) funciona siempre, pero no sabe de horario de verano. Comprueba con `SELECT CONVERT_TZ('2024-05-01 10:00', 'UTC', 'Europe/Madrid')`: debe dar `12:00`, no `NULL`.

Para garantizar la convención en el lado de la escritura, fija la zona de la conexión en UTC desde la aplicación (`SET time_zone = '+00:00'` al abrir, o `time_zone` en la cadena de conexión del driver) y usa `UTC_TIMESTAMP()` en lugar de `NOW()` en SQL. Así `NOW()` no depende de la configuración del servidor de base de datos, que es el otro origen clásico de discrepancias.

Si estás a tiempo de elegir el tipo y las fechas caben en el rango, `TIMESTAMP` te ahorra el `CONVERT_TZ` de lectura: con `SET time_zone = 'Europe/Madrid'` en la sesión del informe, `DATE(created_at)` ya corta por el día de Madrid. Pero el límite de 2038 hace que la mayoría de proyectos nuevos prefieran `DATETIME` + UTC + conversión explícita, que es portable y no caduca.

Misma comprobación que en Postgres: dos filas a `21:30` y `22:30` UTC del 1 de mayo deben caer en días distintos de Madrid (1 y 2 de mayo) con la consulta de arriba.""",
            },
        ]
    },
    # 20) N+1 y SELECT * (el usuario trae logs del ORM)
    {
        "messages": [
            {
                "role": "user",
                "content": """El endpoint de listado de pedidos tarda 1,8 s. Activé el log de SQL del ORM y veo esto repetido cientos de veces:

```
SELECT * FROM orders WHERE status = 'paid' ORDER BY created_at DESC LIMIT 100
SELECT * FROM customers WHERE id = 1017
SELECT * FROM order_items WHERE order_id = 5531
SELECT * FROM customers WHERE id = 1017
SELECT * FROM order_items WHERE order_id = 5532
SELECT * FROM customers WHERE id = 2201
SELECT * FROM order_items WHERE order_id = 5533
(... 200 consultas más)
```

Cada consulta tarda 2-4 ms. ¿Es la base de datos la lenta?""",
            },
            {
                "role": "assistant",
                "content": """No. Cada consulta es rápida; el problema es que haces **201** en vez de 3. Es el patrón **N+1**: una consulta para la lista y luego, por cada uno de los 100 pedidos, una para su cliente y otra para sus líneas. 200 × 3 ms de ida y vuelta son tus 1,8 s, y crecen linealmente con el tamaño de la página.

El log lo confirma: el mismo `customers WHERE id = 1017` aparece varias veces (clientes repetidos se consultan de nuevo) y las consultas de `order_items` van de una en una con ids consecutivos. Es el ORM resolviendo relaciones perezosas dentro de un bucle de la plantilla o del serializador.

**Arreglo: cargar las relaciones en bloque.** Tres consultas en total, independientemente de cuántos pedidos haya:

```sql
SELECT id, customer_id, status, total, created_at
FROM orders
WHERE status = 'paid'
ORDER BY created_at DESC
LIMIT 100;

SELECT id, name, email
FROM customers
WHERE id IN (1017, 2201, 1042, ...);        -- los customer_id distintos de la página

SELECT order_id, product_id, product_name, quantity, unit_price
FROM order_items
WHERE order_id IN (5531, 5532, 5533, ...);  -- los 100 ids de la página
```

Y la aplicación une los resultados en memoria por id (un diccionario). Todos los ORMs tienen esta operación con nombre propio: `selectinload` / `joinedload` en SQLAlchemy, `prefetch_related` / `select_related` en Django, `Include` en EF Core, `with` en Eloquent, `includes` en ActiveRecord. Lo que cambia es que la carga se declara **en la consulta principal**, no se descubre en el bucle.

Alternativa en una sola consulta con join, cuando la relación es a-uno (cliente):

```sql
SELECT o.id, o.total, o.created_at, c.name AS customer_name, c.email AS customer_email
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'paid'
ORDER BY o.created_at DESC
LIMIT 100;
```

Para la relación a-muchos (líneas) el join multiplica filas (un pedido con 5 líneas sale 5 veces) y suele ser mejor la segunda consulta con `IN`, o agregarlas con `json_agg` si la API devuelve JSON de todos modos.

**Segundo problema: `SELECT *`.** Es más barato de lo que parece hasta que no lo es:

- Transfiere columnas que no usas (`notes text`, blobs, JSON grandes): ancho de banda y memoria en el cliente por cada fila.
- Impide los `Index Only Scan`: si la consulta pide todas las columnas, el motor tiene que ir a la tabla aunque el índice cubra lo necesario.
- Rompe en silencio cuando alguien añade o reordena columnas, si el código mapea por posición.

Nombra las columnas que la pantalla necesita. El ORM lo permite (`only()`, `Select(o => new {...})`, `load_only`).

**Cómo detectarlo antes de producción:** un test que cuente consultas. En Django, `assertNumQueries(3)`; en SQLAlchemy, un listener sobre `before_cursor_execute` que incremente un contador; en EF Core, `ILogger` con nivel `Information` en `Microsoft.EntityFrameworkCore.Database.Command`. El test falla en cuanto alguien vuelve a tocar una relación perezosa en un bucle.

Verificación aquí: tras el cambio, el log del ORM debe mostrar 3 consultas para la misma página, y el endpoint bajar de 1,8 s a unas decenas de milisegundos. Si sigue lento con 3 consultas, entonces sí miramos `EXPLAIN ANALYZE` de cada una; antes de eso, la base de datos no era la sospechosa.""",
            },
        ]
    },
    # 21) estadísticas del planificador (avanzado, el usuario trae un plan con estimación errónea)
    {
        "messages": [
            {
                "role": "user",
                "content": """Una consulta sobre `events(tenant_id, type, created_at)` usa un Nested Loop horrible. En el plan veo esto en el nodo de abajo:

```
Index Scan using events_tenant_type_idx on events  (cost=0.56..8.58 rows=1 width=72) (actual time=0.040..1893.221 rows=2140377 loops=1)
  Index Cond: ((tenant_id = 8812) AND (type = 'pageview'))
```

Estima 1 fila y salen 2 millones. Acabo de hacer `ANALYZE events` y sigue igual.""",
            },
            {
                "role": "assistant",
                "content": """Ese error de estimación (1 fila frente a 2,1 millones) es lo que hace que el planificador elija un `Nested Loop`: para «una fila» es el plan correcto; para dos millones es una catástrofe. El `ANALYZE` no lo arregla porque el problema no es que las estadísticas estén viejas, sino **qué** estadísticas tiene.

Postgres estima `tenant_id = 8812 AND type = 'pageview'` multiplicando la selectividad de cada condición por separado, **asumiendo independencia**. Si `tenant_id = 8812` es el 0,1 % de las filas y `type = 'pageview'` el 10 %, estima 0,01 % del total. Pero en tus datos ese tenant es casi todo `pageview` (correlación), y la realidad es 100 veces mayor. Es el caso típico de un tenant enorme en una tabla multi-tenant.

**Arreglo 1: estadísticas multivariantes (PG 10+).** Le dices al planificador que esas columnas están correlacionadas y que recoja la distribución conjunta:

```sql
CREATE STATISTICS events_tenant_type_stats (dependencies, mcv)
    ON tenant_id, type FROM events;
ANALYZE events;
```

- `dependencies` mide la dependencia funcional entre columnas (si conocer `tenant_id` casi determina `type`).
- `mcv` guarda la lista de **combinaciones** más comunes con su frecuencia; es la que resuelve tu caso, porque `(8812, 'pageview')` entrará en esa lista con su 2 % real.

Vuelve a mirar el plan: `rows=` del nodo debería acercarse a los 2 millones y el planificador cambiará a `Hash Join` o `Merge Join`.

**Arreglo 2: más muestreo para la columna sesgada.** Si el tenant grande no aparece en la lista de valores más comunes de `tenant_id` porque hay miles de tenants, sube el detalle de esa columna:

```sql
ALTER TABLE events ALTER COLUMN tenant_id SET STATISTICS 1000;   -- por defecto 100
ANALYZE events;
```

Aumenta el tamaño de la muestra y la longitud de la lista MCV (hasta 1000 valores). Comprueba lo que el planificador «sabe» con:

```sql
SELECT most_common_vals, most_common_freqs, n_distinct
FROM pg_stats
WHERE tablename = 'events' AND attname = 'tenant_id';
```

Si `8812` no está en `most_common_vals`, el planificador lo estima como un valor «raro» cualquiera (`1 / n_distinct`), y de ahí sale el 1.

**Arreglo 3: verificar que `ANALYZE` corre lo bastante a menudo.** `autovacuum` analiza cuando cambia el 10 % de la tabla (`autovacuum_analyze_scale_factor = 0.1`); en una tabla de eventos de cientos de millones de filas eso son días. Baja el umbral para esa tabla:

```sql
ALTER TABLE events SET (autovacuum_analyze_scale_factor = 0.01, autovacuum_analyze_threshold = 50000);
```

Lo que **no** conviene: `SET enable_nestloop = off` globalmente. Arregla esta consulta y estropea las que de verdad devuelven una fila. Como parche local en una sesión mientras llega el arreglo real, es aceptable.

Para confirmar el diagnóstico antes de tocar nada, compara las dos selectividades por separado:

```sql
EXPLAIN SELECT * FROM events WHERE tenant_id = 8812;        -- ¿estima bien?
EXPLAIN SELECT * FROM events WHERE type = 'pageview';       -- ¿estima bien?
```

Si cada una por separado estima razonablemente y la combinación falla, es correlación (arreglo 1). Si la primera ya estima 1 fila, es la lista MCV (arreglo 2). En tu caso, con 2 millones de filas de un solo tenant, apostaría a que son las dos cosas; aplica ambas y `ANALYZE` una vez.""",
            },
        ]
    },
    # 22) UUID v7 vs serial/identity (en inglés, system variante)
    {
        "messages": [
            {"role": "system", "content": "Answer in English. Give a recommendation first, then the reasoning."},
            {"role": "user", "content": "New PostgreSQL schema. Should primary keys be bigint identity, UUID v4, or UUID v7? The team is split: some want UUIDs so the frontend can generate ids offline, others say UUIDs kill index performance."},
            {
                "role": "assistant",
                "content": """Recommendation: `bigint GENERATED ALWAYS AS IDENTITY` for internal tables, and **UUID v7** wherever the id leaves the system (public API, client-generated ids, cross-service references). Don't use UUID v4 as a primary key on a table that grows.

Both camps are right about different things.

**Why random UUIDs (v4) hurt.** A B-tree index on the primary key is ordered by value. Sequential ids always insert at the right end of the tree: the last leaf page stays hot in cache and page splits are rare. Random ids land anywhere: every insert touches a random leaf page, the whole index must stay in memory to avoid disk reads, pages split constantly, and the index ends up around 50 % fuller of empty space. On a 100M-row table the difference between v4 and sequential inserts is routinely 2-4x in write throughput and a much larger working set. Secondary effects: 16 bytes versus 8 per key, repeated in every secondary index and every foreign key.

**Why UUID v7 fixes most of it.** v7 (RFC 9562) puts a 48-bit millisecond timestamp in the high bits and randomness in the low bits. Ids generated at about the same time sort together, so inserts go to the right end of the tree just like a sequence, with cache locality and few splits. You keep the properties the frontend camp wants: globally unique, generated anywhere, no round-trip to the database, no coordination between services. What you don't get back is the 8 bytes.

**Why identity is still the default for internal tables.** Smaller keys, faster joins, human-readable in logs, and `GENERATED ALWAYS AS IDENTITY` (SQL standard, preferred over the older `serial`) cannot be overridden by accident. For tables nobody references from outside (join tables, line items, audit rows), there's no reason to pay for 16-byte keys.

Concrete schema:

```sql
-- internal table
CREATE TABLE order_items (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id  uuid NOT NULL REFERENCES orders(id),
    ...
);

-- public-facing table
CREATE TABLE orders (
    id          uuid PRIMARY KEY DEFAULT uuidv7(),   -- PostgreSQL 18; see below for older versions
    customer_id uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
```

`uuidv7()` is built in from PostgreSQL 18. On 13-17, generate v7 in the application (every major language has a library: `uuid7` in Python, `Uuid.CreateVersion7()` in .NET 9, `uuid.v7()` in Node 20+, `uuid.v7` in the Go `google/uuid` package) or use the `pg_uuidv7` extension. Clients generating ids offline is exactly the use case, so application-side generation is natural anyway.

Two caveats with v7:

- **The timestamp leaks creation time.** Usually fine; if "when was this created" is sensitive, it's not the right key.
- **Clock skew between generators** can produce slightly out-of-order ids. Harmless for uniqueness and locality; don't use the id as a substitute for `created_at`.

One thing to avoid in either case: exposing `bigint` ids publicly. They're guessable and reveal volume (`/orders/10432` tells competitors how many orders you have). If you want sequential internal keys *and* opaque public ids, add a `public_id uuid UNIQUE DEFAULT uuidv7()` column and expose only that.

Benchmark to settle the argument on your hardware: insert 10M rows into three tables (identity, v4, v7) with `pgbench` custom scripts, then compare `pg_relation_size` of the primary key index and inserts/second. Expect v7 within 10-20 % of identity and v4 far behind once the index stops fitting in `shared_buffers`.""",
            },
        ]
    },
    # 23) MySQL: ORDER BY ... LIMIT no determinista (en inglés)
    {
        "messages": [
            {"role": "user", "content": "MySQL 8 question. `SELECT * FROM products ORDER BY price LIMIT 10 OFFSET 10` returns a different set of rows on different runs, and some products appear on both page 1 and page 2. Nothing is being inserted. Is this a bug?"},
            {
                "role": "assistant",
                "content": """Not a bug: the sort is **not deterministic when there are ties**. If twenty products share the same `price`, SQL doesn't specify which of them comes first; the engine returns whatever order its chosen plan happened to produce. Page 1 and page 2 are two separate queries, each free to break the ties differently, so a product can land at position 10 in one run and position 11 in the next.

MySQL makes this more visible than other engines because `ORDER BY ... LIMIT` uses a different algorithm (a priority queue in memory) than a full sort, and the tie-breaking depends on which rows arrive first from the scan, which in turn depends on buffer pool state and the index used.

Fix: make the ordering total by adding a unique tiebreaker.

```sql
SELECT id, name, price
FROM products
ORDER BY price, id
LIMIT 10 OFFSET 10;
```

With `(price, id)` no two rows compare equal, so every run produces the same sequence and pages don't overlap. This is the rule for *any* paginated query in any database: the `ORDER BY` must end with a unique column.

Two things to do alongside:

**Index that matches the order.** `ORDER BY price, id` with an index on `(price, id)` lets MySQL read rows already sorted and stop after 20, instead of sorting the table for every page:

```sql
CREATE INDEX products_price_id_idx ON products (price, id);
```

`EXPLAIN` should show `Using index` and no `Using filesort`. In InnoDB every secondary index implicitly ends with the primary key, so an index on `(price)` alone already contains `id` as the final column and is usable for `ORDER BY price, id`; declaring it explicitly just makes the intent visible.

**Consider keyset pagination** once pages get deep. `OFFSET 10000` reads and discards 10 000 rows per request. Keyset uses the last row of the previous page as the starting point:

```sql
SELECT id, name, price
FROM products
WHERE (price, id) > (?, ?)       -- last price and id seen
ORDER BY price, id
LIMIT 10;
```

MySQL 8 supports row-value comparison and, with the `(price, id)` index, uses a range scan for it. Pages stay O(page size) regardless of depth and are stable under inserts.

The same tie problem shows up in two other places in MySQL worth knowing about:

- `GROUP BY` with a non-aggregated column (when `ONLY_FULL_GROUP_BY` is off) returns an arbitrary row from each group, with the same "different on each run" behaviour.
- `SELECT ... LIMIT 1` without `ORDER BY` to "get the first row". There is no first row without an order.

Quick check that the fix worked: run the two pages ten times in a loop and compare `id` sets; before the change you'll see overlaps, after it the union is always 20 distinct ids.""",
            },
        ]
    },
    # 24) SQLite: particularidades (multiturno, system variante mexicano, principiante)
    {
        "messages": [
            {"role": "system", "content": "Responde en español de México, de forma clara para alguien que está empezando, sin perder rigor."},
            {"role": "user", "content": "Estoy usando SQLite para una app de escritorio y me sorprendió que me dejara meter texto en una columna INTEGER y que no respetara una FOREIGN KEY. ¿SQLite es así de laxo o estoy haciendo algo mal?"},
            {
                "role": "assistant",
                "content": """Las dos cosas son comportamientos de SQLite por diseño, y las dos tienen remedio.

**1. Los tipos son «afinidades», no restricciones.** En SQLite cada columna tiene una *afinidad* (INTEGER, TEXT, REAL, NUMERIC, BLOB) que indica cómo **intenta** convertir lo que le das. Si declaras `INTEGER` y le pasas `'42'`, lo guarda como 42; si le pasas `'hola'`, como no puede convertirlo, lo guarda como texto tal cual. Así que una columna INTEGER puede contener texto, y es normal en SQLite.

Desde la versión 3.37 (2021) existe la solución: tablas **STRICT**, que sí rechazan valores de tipo incorrecto:

```sql
CREATE TABLE products (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0)
) STRICT;

INSERT INTO products (name, price) VALUES ('Taza', 'gratis');
-- Error: cannot store TEXT value in REAL column products.price
```

En tablas STRICT solo se permiten los tipos `INT`, `INTEGER`, `REAL`, `TEXT`, `BLOB` y `ANY`. Úsalas en todo lo nuevo. Para tablas que no puedas cambiar, un `CHECK (typeof(price) = 'real')` consigue lo mismo columna por columna.

**2. Las claves foráneas están apagadas por defecto.** SQLite las analiza y las guarda en el esquema, pero **no las aplica** a menos que la conexión lo pida, por compatibilidad con bases antiguas. Hay que activarlo **en cada conexión**, porque no es una propiedad del archivo:

```sql
PRAGMA foreign_keys = ON;
```

En Python sería lo primero que haces después de `sqlite3.connect()`:

```python
import sqlite3

conn = sqlite3.connect("app.db")
conn.execute("PRAGMA foreign_keys = ON")
```

Checa que quedó activo con `PRAGMA foreign_keys;` (debe regresar 1). Si tu librería usa un *pool* de conexiones, el PRAGMA tiene que correr en el evento de «conexión nueva», no una sola vez al arrancar.

Otros tres detalles que te van a salir pronto en una app de escritorio:

- **`INTEGER PRIMARY KEY` es especial**: es un alias del `rowid` interno, así que es la clave más rápida y se autoincrementa sola. `AUTOINCREMENT` casi nunca hace falta (solo garantiza que no se reutilicen ids borrados, a cambio de una tabla extra).
- **`PRAGMA journal_mode = WAL`**: permite que las lecturas no bloqueen a la escritura y viceversa. Para una app con interfaz gráfica que lee mientras guarda, es casi obligatorio. Se fija una vez por archivo (sí persiste).
- **Un solo escritor a la vez**: SQLite serializa las escrituras de toda la base de datos. Está bien para una app de escritorio; no lo uses como servidor con muchos procesos escribiendo.

Resumen para empezar bien: `STRICT` en las tablas, `PRAGMA foreign_keys = ON` en cada conexión, `WAL` una vez. Con eso SQLite se comporta como esperas de una base relacional.""",
            },
            {"role": "user", "content": "Activé WAL y las claves foráneas. Ahora a veces me sale `sqlite3.OperationalError: database is locked` cuando guardo desde un hilo mientras la interfaz lee. ¿Qué hago?"},
            {
                "role": "assistant",
                "content": """Ese error sale cuando una conexión quiere escribir y otra tiene un bloqueo que lo impide por más tiempo del límite de espera (`busy_timeout`), que por defecto es **cero**: SQLite no espera nada y falla al instante. Con WAL las lecturas ya no bloquean a la escritura, así que lo que te está chocando es casi seguro una de estas dos:

1. **Dos escrituras a la vez** (dos hilos guardando, o un hilo guardando mientras otro hace un `UPDATE` de «última apertura»).
2. **Una transacción abierta sin cerrar.** En Python, el módulo `sqlite3` abre una transacción implícita antes de cada `INSERT`/`UPDATE`/`DELETE` y la deja abierta hasta que llames `commit()`. Si un hilo ejecutó una escritura y nunca hizo commit, mantiene el bloqueo de escritura para siempre.

Tres ajustes, en este orden:

**a) Dale un tiempo de espera.** Con 5 segundos de `timeout`, la segunda escritura espera a que termine la primera en vez de fallar:

```python
conn = sqlite3.connect("app.db", timeout=5.0, check_same_thread=False)
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA busy_timeout = 5000")   # mismo efecto a nivel de SQLite, por si usas otra librería
```

**b) Cierra las transacciones siempre.** Usa la conexión como administrador de contexto, que hace commit al salir bien y rollback si hay excepción:

```python
def save_note(conn: sqlite3.Connection, title: str, body: str) -> int:
    with conn:                      # commit o rollback automático
        cur = conn.execute("INSERT INTO notes (title, body) VALUES (?, ?)", (title, body))
        return cur.lastrowid
```

Ojo: `with conn:` no cierra la conexión, solo la transacción; es justo lo que quieres.

**c) Una conexión por hilo, o un solo hilo escritor.** Las conexiones de SQLite no se comparten bien entre hilos. Lo más robusto para una app de escritorio es que la interfaz lea con su propia conexión y que **todas las escrituras pasen por un hilo** que las toma de una cola (`queue.Queue`). Así nunca hay dos escrituras compitiendo y el `timeout` queda como red de seguridad, no como mecanismo habitual.

Para encontrar la transacción colgada, si después de esto sigue apareciendo: en el hilo que falla, imprime `conn.in_transaction` de las demás conexiones justo antes de escribir; el que regrese `True` sin estar escribiendo es el culpable. En Python 3.12+ también puedes poner `autocommit=True` en `connect()` y manejar las transacciones tú con `BEGIN`/`COMMIT` explícitos, que es más predecible que el modo implícito.

Comprobación rápida: con el `timeout` puesto, lanza dos hilos que inserten 1 000 filas cada uno; debe terminar sin errores y `SELECT count(*)` dar 2 000. Antes del cambio, uno de los dos fallaba con `database is locked` en las primeras inserciones.""",
            },
        ]
    },
    # 25) fan-out en joins: doble conteo (el usuario trae la consulta)
    {
        "messages": [
            {
                "role": "user",
                "content": """Este informe da totales inflados. Si un pedido tiene 3 líneas y 2 pagos, el total del pedido sale multiplicado:

```sql
SELECT o.id,
       SUM(oi.quantity * oi.unit_price) AS items_total,
       SUM(p.amount)                    AS paid_total
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN payments p     ON p.order_id = o.id
GROUP BY o.id;
```

¿Qué hago mal?""",
            },
            {
                "role": "assistant",
                "content": """Haces dos joins uno-a-muchos **sobre la misma fila padre**, y el resultado es un producto cartesiano por pedido: 3 líneas × 2 pagos = 6 filas, donde cada línea aparece 2 veces y cada pago 3 veces. Las sumas lo recogen entero: `items_total` sale ×2 y `paid_total` ×3. Es el problema de *fan-out* (abanico), y aparece siempre que juntas dos colecciones independientes antes de agregar.

Tabla de lo que ve el `GROUP BY` para un pedido con líneas A, B, C y pagos P1, P2:

| línea | pago |
|---|---|
| A | P1 |
| A | P2 |
| B | P1 |
| B | P2 |
| C | P1 |
| C | P2 |

**Arreglo: agrega cada colección por separado y luego une los agregados.** Cada subconsulta devuelve una fila por pedido, así que el join final es uno-a-uno:

```sql
SELECT o.id,
       COALESCE(i.items_total, 0) AS items_total,
       COALESCE(p.paid_total, 0)  AS paid_total
FROM orders o
LEFT JOIN (
    SELECT order_id, SUM(quantity * unit_price) AS items_total
    FROM order_items
    GROUP BY order_id
) i ON i.order_id = o.id
LEFT JOIN (
    SELECT order_id, SUM(amount) AS paid_total
    FROM payments
    GROUP BY order_id
) p ON p.order_id = o.id;
```

`LEFT JOIN` + `COALESCE` para que un pedido sin pagos (o sin líneas) aparezca con 0 en vez de desaparecer, que es el segundo bug que tenía tu versión con `JOIN` interno.

Alternativa equivalente con subconsultas escalares, más legible cuando hay muchas colecciones:

```sql
SELECT o.id,
       (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_items WHERE order_id = o.id) AS items_total,
       (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE order_id = o.id) AS paid_total
FROM orders o;
```

Postgres las ejecuta como una subconsulta por fila; con índices en `order_items(order_id)` y `payments(order_id)` es rápido para miles de pedidos, y para millones el plan de las subconsultas agregadas (primera versión) suele ganar.

Lo que **no** arregla el problema: `SUM(DISTINCT oi.quantity * oi.unit_price)`. Elimina duplicados por valor, así que dos líneas distintas con el mismo importe se contarían una vez. `COUNT(DISTINCT oi.id)` sí sirve para contar, pero para sumar no hay versión «distinct por fila» que funcione.

Regla para detectarlo en revisión: si una consulta con `GROUP BY` tiene **más de un join hacia una tabla «hija»** (varias filas por padre), hay fan-out salvo que uno de los joins sea uno-a-uno. Y la prueba para cazarlo: compara `COUNT(*)` del join sin agrupar con la suma de filas hijas; si da más, estás multiplicando.

Comprobación con tus datos: para el pedido de 3 líneas y 2 pagos, la versión corregida debe devolver exactamente la suma de sus 3 líneas y la de sus 2 pagos. La original daba el doble y el triple, respectivamente.""",
            },
        ]
    },
    # 26) EXISTS vs IN vs JOIN (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Para «clientes que tienen al menos un pedido» veo tres formas: JOIN con DISTINCT, IN con subconsulta y EXISTS. ¿Son equivalentes? ¿Cuál es mejor?"},
            {
                "role": "assistant",
                "content": """Son equivalentes en resultado solo si pones cuidado; en intención y rendimiento, `EXISTS` es la que describe lo que quieres.

Las tres:

```sql
-- 1) JOIN + DISTINCT
SELECT DISTINCT c.id, c.name
FROM customers c
JOIN orders o ON o.customer_id = c.id;

-- 2) IN
SELECT c.id, c.name
FROM customers c
WHERE c.id IN (SELECT customer_id FROM orders);

-- 3) EXISTS
SELECT c.id, c.name
FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

**Semántica.** La pregunta es un *semi-join*: «¿existe al menos una fila relacionada?». Quieres cada cliente **una vez**, sin importar cuántos pedidos tenga.

- El `JOIN` multiplica: un cliente con 50 pedidos sale 50 veces, y por eso necesitas `DISTINCT`. Funciona, pero haces trabajo (producir duplicados y eliminarlos) para expresar algo que no es un join. Y si añades columnas de `orders` al `SELECT`, el `DISTINCT` deja de arreglarlo.
- `IN` y `EXISTS` son semi-joins nativos: nunca duplican.
- Diferencia entre `IN` y `EXISTS`: con `NULL`. Si `orders.customer_id` admite nulos, `IN` sigue funcionando para la versión positiva, pero **`NOT IN` devuelve vacío** en cuanto hay un `NULL` en la subconsulta. `NOT EXISTS` no tiene ese problema. Por coherencia, usa `EXISTS`/`NOT EXISTS` para ambas direcciones.

**Rendimiento.** En PostgreSQL moderno, `IN (subconsulta)` y `EXISTS` se transforman en el mismo plan (`Semi Join`, normalmente *hash* o *nested loop* según tamaños); la diferencia es cero en la mayoría de los casos. El `JOIN + DISTINCT` genera un plan con `HashAggregate` o `Unique` después del join, que cuesta más cuando hay muchos pedidos por cliente. MySQL 8 también convierte `IN` y `EXISTS` en semi-join; en versiones antiguas (5.5 y anteriores) `IN` con subconsulta se ejecutaba por fila y era el motivo histórico de la fama de lento.

Cuándo sí quieres el `JOIN`: cuando necesitas datos de `orders` en la salida (fecha del último pedido, importe). Entonces no es un semi-join y el `DISTINCT` tampoco es la herramienta: agrega:

```sql
SELECT c.id, c.name, MAX(o.created_at) AS last_order, COUNT(*) AS orders
FROM customers c
JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name;
```

Regla práctica:

| Pregunta | Forma |
|---|---|
| «¿Tiene alguno?» | `EXISTS` |
| «¿No tiene ninguno?» | `NOT EXISTS` |
| «Dame datos de los relacionados» | `JOIN` (+ `GROUP BY` si agregas) |
| Lista pequeña de valores literales | `IN (1, 2, 3)` |

Comprueba la equivalencia con `EXPLAIN` de las formas 2 y 3: en PG 12+ verás el mismo `Hash Semi Join`. Y para la 1 verás el nodo extra de deduplicación, que es el coste que te ahorras.""",
            },
        ]
    },
    # 27) última fila por grupo: DISTINCT ON, ventana, LATERAL (system variante DBA)
    {
        "messages": [
            {"role": "system", "content": "Eres un DBA de PostgreSQL. Responde con SQL ejecutable y una explicación breve de cada alternativa."},
            {"role": "user", "content": "Necesito el último pedido de cada cliente (toda la fila del pedido). ¿Cuál es la forma más eficiente en Postgres?"},
            {
                "role": "assistant",
                "content": """Tres formas correctas; la mejor depende de cuántos clientes y cuántos pedidos por cliente tengas. Índice común a las tres:

```sql
CREATE INDEX CONCURRENTLY orders_customer_created_idx ON orders (customer_id, created_at DESC, id DESC);
```

**1. `DISTINCT ON` (específico de Postgres, el más corto).**

```sql
SELECT DISTINCT ON (o.customer_id) o.*
FROM orders o
ORDER BY o.customer_id, o.created_at DESC, o.id DESC;
```

`DISTINCT ON (customer_id)` se queda con la **primera fila de cada grupo** según el `ORDER BY`, que debe empezar por las mismas columnas. El `id DESC` desempata dos pedidos con la misma marca de tiempo. Con el índice, es un recorrido ordenado del índice con `Unique`; rinde bien cuando la mayoría de los clientes tienen pedidos y los pedidos por cliente son pocos o moderados.

**2. Función de ventana (estándar SQL, portable).**

```sql
SELECT id, customer_id, created_at, total
FROM (
    SELECT o.*,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC, id DESC) AS rn
    FROM orders o
) ranked
WHERE rn = 1;
```

Mismo coste aproximado que `DISTINCT ON`; Postgres 15+ puede empujar el filtro `rn = 1` dentro del `WindowAgg` y parar en la primera fila de cada partición. Es la forma que funciona igual en MySQL 8, SQL Server y SQLite.

**3. `LATERAL` (gana cuando hay pocos clientes y muchos pedidos).**

```sql
SELECT c.id AS customer_id, c.name, last_order.*
FROM customers c
LEFT JOIN LATERAL (
    SELECT o.id, o.created_at, o.total
    FROM orders o
    WHERE o.customer_id = c.id
    ORDER BY o.created_at DESC, o.id DESC
    LIMIT 1
) last_order ON true;
```

`LATERAL` ejecuta la subconsulta **una vez por cliente** usando el índice para saltar directamente al último pedido: coste proporcional al número de clientes, no al de pedidos. Si tienes 10 000 clientes y 50 millones de pedidos, las formas 1 y 2 leen el índice entero (o la tabla); esta lee 10 000 entradas. Además devuelve a los clientes sin pedidos (`LEFT JOIN ... ON true`) con nulos, que las otras dos no hacen.

Cómo elegir, en números:

| Situación | Forma |
|---|---|
| Muchos clientes, pocos pedidos cada uno | 1 o 2 |
| Pocos clientes, muchos pedidos cada uno | 3 |
| Necesitas también clientes sin pedidos | 3 |
| Debe funcionar en otros motores | 2 |
| Quieres el top-N por grupo (no solo 1) | 2 con `rn <= N`, o 3 con `LIMIT N` |

Verificación: `EXPLAIN (ANALYZE, BUFFERS)` de cada una sobre tus datos. En la 3 verás `Nested Loop` con un `Index Scan ... Limit 1` por cliente y pocos `shared hit`; en las otras, un único recorrido del índice y más páginas leídas. La forma que lea menos buffers con tus proporciones es la respuesta.""",
            },
        ]
    },
    # 28) carga masiva (avanzado)
    {
        "messages": [
            {"role": "user", "content": "Tengo que cargar un CSV de 80 millones de filas en Postgres cada noche en una tabla que luego se consulta. Con INSERT fila a fila desde Python tarda 6 horas. ¿Cómo lo bajo a minutos?"},
            {
                "role": "assistant",
                "content": """Con `COPY`, que es la ruta de carga masiva nativa, y con la tabla preparada para recibir datos en bloque. Seis horas de `INSERT` fila a fila son 80 millones de idas y vueltas más un `fsync` por transacción; `COPY` hace una sola sentencia que lee el flujo entero.

**1. `COPY` desde Python con psycopg 3:**

```python
import psycopg

with psycopg.connect(DSN) as conn, conn.cursor() as cur:
    with open("events.csv", "rb") as f, cur.copy(
        "COPY events_staging (occurred_at, user_id, kind, value) FROM STDIN WITH (FORMAT csv, HEADER true)"
    ) as copy:
        while chunk := f.read(1 << 20):     # 1 MiB por bloque
            copy.write(chunk)
    conn.commit()
```

Solo esto suele bajar de horas a 10-20 minutos. `FORMAT csv` entiende comillas y escapes estándar; si el archivo lo generas tú, `FORMAT text` (tabulador, `\\N` para nulos) es algo más rápido de parsear.

**2. Carga en una tabla de *staging* sin índices ni restricciones**, y crea los índices **después**. Construir un índice sobre 80 M filas ya cargadas es mucho más rápido que mantenerlo fila a fila, y la validación de restricciones en bloque también:

```sql
CREATE UNLOGGED TABLE events_staging (LIKE events INCLUDING DEFAULTS);
-- COPY aquí
CREATE INDEX ON events_staging (user_id, occurred_at);
ALTER TABLE events_staging ADD CONSTRAINT ... ;
```

`UNLOGGED` evita escribir el WAL durante la carga (el doble de rápido o más). El precio: si el servidor cae a mitad, la tabla queda vacía, lo que para una carga nocturna que se puede repetir es aceptable. Antes de ponerla en servicio, `ALTER TABLE events_staging SET LOGGED` (reescribe la tabla una vez) o, mejor, usa el punto 4.

**3. Ajustes de sesión durante la carga** (solo en esa conexión):

```sql
SET maintenance_work_mem = '2GB';     -- acelera CREATE INDEX
SET synchronous_commit = off;         -- no espera el fsync en cada commit; seguro si puedes repetir la carga
```

Con un solo `COPY` en una sola transacción, `synchronous_commit` importa poco; importa si cargas en lotes.

**4. Intercambio atómico al final**, para que las consultas nunca vean una tabla a medias:

```sql
BEGIN;
ALTER TABLE events RENAME TO events_old;
ALTER TABLE events_staging RENAME TO events;
COMMIT;
DROP TABLE events_old;
ANALYZE events;
```

El `RENAME` es instantáneo y toma un bloqueo breve. `ANALYZE` al final es obligatorio: sin estadísticas, el planificador asume una tabla vacía y los planes de la mañana siguiente son malos. Si la tabla tiene vistas o claves foráneas que apuntan a ella, el renombrado las arrastra (las dependencias siguen al OID), así que en ese caso es más seguro `TRUNCATE events` + `INSERT INTO events SELECT * FROM events_staging` dentro de la misma transacción, que también es atómico para los lectores.

**5. Paralelismo** si todavía es lento: parte el CSV en 4-8 trozos y lanza un `COPY` por trozo en conexiones separadas sobre la misma tabla sin índices; `COPY` escala casi linealmente con los núcleos hasta que el disco satura.

Órdenes de magnitud razonables en un servidor normal: `COPY` sin índices, 200-500 k filas/s; con dos índices activos durante la carga, 3-5 veces menos. 80 M filas deberían quedar en 5-10 minutos incluidos los índices.

Para MySQL el equivalente es `LOAD DATA LOCAL INFILE` con la misma estrategia de índices después; para SQLite, un único `BEGIN`/`COMMIT` alrededor de `executemany` ya pasa de horas a minutos, porque el coste allí es el `fsync` por transacción implícita.""",
            },
        ]
    },
    # 29) soft delete y unicidad parcial (usuario en inglés pide respuesta en español)
    {
        "messages": [
            {"role": "user", "content": "We use soft deletes (`deleted_at` column). Problem: `UNIQUE (email)` on users prevents someone from re-registering with an email that belongs to a deleted account. How do we keep uniqueness only among live rows in PostgreSQL? Answer in Spanish, please."},
            {
                "role": "assistant",
                "content": """Con un **índice único parcial**: la unicidad se aplica solo a las filas que cumplen la condición, y las borradas quedan fuera.

```sql
ALTER TABLE users DROP CONSTRAINT users_email_key;   -- la restricción UNIQUE actual

CREATE UNIQUE INDEX CONCURRENTLY users_email_live_idx
    ON users (email)
    WHERE deleted_at IS NULL;
```

A partir de ahí:

- Dos usuarios activos con el mismo correo: error `duplicate key value violates unique constraint "users_email_live_idx"`.
- Un usuario borrado y uno activo con el mismo correo: permitido.
- Varios borrados con el mismo correo: permitido (cada baja y alta deja su rastro).

Dos efectos secundarios que conviene decidir ahora:

**1. Las claves foráneas no pueden apuntar a un índice parcial.** Si otra tabla tiene `REFERENCES users(email)`, deja de ser posible; las FK deben apuntar a una restricción `UNIQUE` o `PRIMARY KEY` completa. Lo normal es que apunten a `users(id)`, y entonces no afecta.

**2. Las consultas deben filtrar siempre `deleted_at IS NULL`.** Es el coste del borrado lógico, y el índice parcial no lo hace por ti. Dos ayudas:

```sql
-- Vista para el código de aplicación
CREATE VIEW active_users AS
SELECT * FROM users WHERE deleted_at IS NULL;

-- Índices parciales para el resto de consultas frecuentes sobre usuarios vivos
CREATE INDEX CONCURRENTLY users_live_created_idx ON users (created_at) WHERE deleted_at IS NULL;
```

Un índice parcial solo se usa cuando la consulta incluye la condición literal (`deleted_at IS NULL`); si el ORM genera `deleted_at = NULL` o la omite, el planificador no lo elige.

Una variante que a veces es mejor que el `deleted_at` compartido: **mover las filas borradas a otra tabla** (`users_archive`) en la misma transacción que el borrado. La tabla viva conserva `UNIQUE (email)` normal, las FK funcionan, ninguna consulta necesita el filtro y el histórico sigue existiendo. Tiene sentido cuando «restaurar» es raro y las consultas sobre borrados son solo auditoría.

Para re-registros, decide también qué pasa con el **correo normalizado**: `Ana@Example.com` y `ana@example.com` son el mismo buzón. El índice parcial sobre `lower(email)` cubre las dos cosas:

```sql
CREATE UNIQUE INDEX CONCURRENTLY users_email_live_idx
    ON users (lower(email))
    WHERE deleted_at IS NULL;
```

Comprobación en tres sentencias: inserta `ana@example.com`, márcalo como borrado (`UPDATE users SET deleted_at = now() WHERE ...`), inserta de nuevo `ana@example.com`: debe entrar. Un tercer `INSERT` del mismo correo sin borrar el segundo debe fallar.""",
            },
        ]
    },
    # 30) encontrar consultas lentas en producción (multiturno)
    {
        "messages": [
            {"role": "user", "content": "La base de datos (Postgres 16) va lenta «a ratos» y nadie sabe qué consulta es. ¿Cómo encuentro las culpables sin ponerme a leer el código de toda la aplicación?"},
            {
                "role": "assistant",
                "content": """Dos herramientas del propio Postgres, complementarias: `pg_stat_statements` para saber **qué consultas consumen más en total**, y `auto_explain` para capturar **el plan de las que se pasan de un umbral**.

**1. `pg_stat_statements`: el ranking.** Agrega todas las ejecuciones de cada consulta (normalizada, sin valores concretos) desde el último reinicio de estadísticas.

```ini
# postgresql.conf (requiere reinicio)
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
```

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

SELECT
    calls,
    round(total_exec_time::numeric / 1000, 1)    AS total_s,
    round(mean_exec_time::numeric, 2)            AS mean_ms,
    round(max_exec_time::numeric, 2)             AS max_ms,
    rows,
    shared_blks_read,
    left(query, 120)                             AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

Mira tres ordenaciones distintas, porque señalan culpables distintos:

- `ORDER BY total_exec_time DESC`: lo que más CPU/IO consume en conjunto. Suele ser una consulta rápida ejecutada millones de veces (N+1, un *polling* cada segundo).
- `ORDER BY mean_exec_time DESC`: las lentas por ejecución. Informes, consultas sin índice.
- `ORDER BY shared_blks_read DESC`: las que más leen de disco. Candidatas a índice o a caché.

Para «lento a ratos», compara `mean_exec_time` con `max_exec_time`: una consulta con media de 5 ms y máximo de 8 s es la que a ratos encuentra un bloqueo o un plan distinto.

**2. `auto_explain`: el plan de las lentas, cuando ocurren.** Registra en el log el `EXPLAIN ANALYZE` de cualquier consulta que supere el umbral, sin que tengas que reproducirla:

```ini
shared_preload_libraries = 'pg_stat_statements,auto_explain'
auto_explain.log_min_duration = '500ms'
auto_explain.log_analyze = on
auto_explain.log_buffers = on
auto_explain.log_format = json
auto_explain.log_timing = off     # reduce el coste de medir en servidores cargados
```

`log_analyze = on` tiene un coste (mide cada nodo de **todas** las consultas, aunque solo registre las lentas); en producción muy cargada, empieza con `log_analyze = off` y actívalo solo mientras cazas el problema.

**3. Qué está pasando ahora mismo**, cuando la lentitud está ocurriendo:

```sql
SELECT pid, now() - query_start AS running, state, wait_event_type, wait_event, left(query, 100)
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY query_start;
```

Si `wait_event_type = 'Lock'` aparece en varias filas, el problema son bloqueos, no consultas lentas: busca el `pid` que las bloquea con `pg_blocking_pids(pid)`.

Resetea el ranking después de un cambio para medir el efecto: `SELECT pg_stat_statements_reset();`.""",
            },
            {"role": "user", "content": "Ya lo tengo. La primera del ranking por tiempo total es un `SELECT` con 40 millones de llamadas y 3 ms de media, y la primera por media es un informe con 12 s. ¿Por cuál empiezo?"},
            {
                "role": "assistant",
                "content": """Por la de 40 millones de llamadas. Las cuentas mandan: 40 M × 3 ms son **33 horas de CPU** de base de datos acumuladas, frente al informe, que aunque tarde 12 s cada vez, si se ejecuta 50 veces al día son 10 minutos. La primera es la que mantiene el servidor ocupado y explica el «a ratos»: cuando coincide con cualquier otra cosa, todo se ralentiza.

Para la de 40 M de llamadas, la pregunta no es «cómo la hago más rápida» sino **«por qué se ejecuta tanto»**. Casi siempre es una de estas:

1. **N+1 en la aplicación**: una consulta por fila de un listado. Lo delata que `rows` por llamada sea 1 y que la consulta sea un `WHERE id = $1`. Arreglo: cargar en bloque con `IN (...)` o join; de 40 M pasas a unos cientos de miles.
2. **Polling**: workers que preguntan «¿hay trabajo?» cada 100 ms. Arreglo: `LISTEN/NOTIFY`, o subir el intervalo con *backoff* cuando no hay trabajo.
3. **Falta de caché**: la misma configuración o la misma fila de catálogo leída en cada petición HTTP. Arreglo: caché en la aplicación con unos segundos de TTL.

Confírmalo con `pg_stat_statements`: la columna `rows / calls` y el texto de la consulta te dicen cuál de las tres es. Si son 3 ms por fila devuelta, además revisa el plan: una búsqueda por clave primaria debería estar en 0,1 ms, así que probablemente también le falte un índice o esté haciendo un `Seq Scan` sobre una tabla pequeña que ha crecido.

El informe de 12 s va después, y se ataca con `EXPLAIN (ANALYZE, BUFFERS)`: busca el nodo donde `actual rows` se dispara frente a `rows` estimadas, los `Seq Scan` sobre tablas grandes y los `Sort` con `external merge` (ordenación en disco por `work_mem` insuficiente). Si es un informe que corre de noche, a veces la respuesta correcta es moverlo a una réplica de lectura o a una vista materializada y no tocar la consulta.

Orden de trabajo y cómo medir que ha servido:

1. Arregla la de 40 M. Resetea estadísticas. Al día siguiente, su `total_exec_time` debe haber caído al menos un orden de magnitud y la carga media del servidor con ella.
2. Vuelve a mirar el ranking: lo que antes era la segunda suele haber cambiado, porque sin la primera saturando, muchas «lentas a ratos» dejan de serlo.
3. Solo entonces el informe, con su plan en la mano.

Una regla para la próxima vez: `total_exec_time` ordena el impacto; `mean_exec_time` ordena la vergüenza. El impacto primero.""",
            },
        ]
    },
]
