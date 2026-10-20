"""Datos y ML: NumPy, pandas 2.x/3, Polars, PyTorch 2.x, scikit-learn, transformers/PEFT.

30 filas. Reparto aproximado: NumPy 5 · pandas 8 · Polars 3 · PyTorch 9 · scikit-learn 3 ·
transformers/PEFT 2. Incluye matplotlib, reproducibilidad y notebooks vs scripts dentro de
esas filas. Sigue entrenamiento/GUIA_DE_ESTILO.md.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) NumPy: broadcasting (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo un array `a` de shape (5, 3) y otro `b` de shape (5,) con un valor por fila. Quiero restarle `b` a cada fila (restar b[i] a toda la fila i) y NumPy me tira:

```
ValueError: operands could not be broadcast together with shapes (5,3) (5,)
```

¿Por qué falla si los dos tienen 5?""",
            },
            {
                "role": "assistant",
                "content": """Falla porque el broadcasting alinea las dimensiones **desde la derecha**, no desde la izquierda. NumPy compara el último eje de cada operando: `3` contra `5`. No son iguales y ninguno es 1, así que no hay forma de emparejarlos. Que el primer eje de `a` también mida 5 es casualidad; NumPy ni llega a mirarlo.

La regla completa, en orden:

1. Si un array tiene menos dimensiones, se le añaden ejes de tamaño 1 **por la izquierda**: `(5,)` se trata como `(1, 5)`.
2. Dos ejes son compatibles si miden lo mismo o si uno de ellos mide 1.
3. Un eje de tamaño 1 se "estira" (sin copiar memoria) hasta el tamaño del otro.

Con `(5, 3)` y `(1, 5)` el último eje es 3 frente a 5: incompatible. Lo que necesitas es que `b` tenga shape `(5, 1)`, para que el 1 se estire a lo largo de las columnas:

```python
import numpy as np

a = np.arange(15, dtype=float).reshape(5, 3)
b = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

resultado = a - b[:, None]      # b[:, None] tiene shape (5, 1); equivale a b[:, np.newaxis]
print(resultado.shape)          # (5, 3)
```

Comprobación rápida de que resta por filas y no por columnas:

```python
assert resultado[2, 1] == a[2, 1] - b[2]
assert np.array_equal(resultado[4], a[4] - b[4])
```

Dos detalles que ahorran bugs:

- **El caso peligroso es el que no falla.** Si `b` hubiera tenido shape `(3,)`, `a - b` se habría ejecutado sin error restando por *columnas*. Cuando las dimensiones coinciden por accidente, el broadcasting hace algo silenciosamente distinto a lo que querías. Por eso conviene ser explícito con `[:, None]` aunque "funcione" sin él.
- Si `b` sale de una reducción de `a`, usa `keepdims=True` y te ahorras el reshape: `a - a.mean(axis=1, keepdims=True)` ya devuelve `(5, 1)` en el lado derecho.""",
            },
        ]
    },
    # 2) NumPy: vistas vs copias (usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": """No entiendo cuándo NumPy copia y cuándo no. Mirá este código:

```python
import numpy as np
datos = np.arange(12, dtype=float).reshape(3, 4)

fila = datos[0]
fila /= 10               # esto SÍ modifica datos

cols = datos[:, [0, 2]]
cols *= 100              # esto NO modifica datos

datos[:, [0, 2]] *= 100  # ¡esto SÍ!
```

¿Cuál es la regla? Me dan miedo los efectos secundarios.""",
            },
            {
                "role": "assistant",
                "content": """La regla tiene dos mitades y tu tercer caso es un truco de sintaxis, no una excepción.

**Indexación básica → vista. Indexación avanzada → copia.**

- *Básica*: enteros, slices (`a[1:5]`, `a[::2]`), `None`/`np.newaxis`, `...`. NumPy puede describir el resultado con un puntero y unos *strides*, así que devuelve una vista que **comparte memoria** con el original.
- *Avanzada*: listas o arrays de enteros (`a[[0, 2]]`) y máscaras booleanas (`a[a > 5]`). Los elementos elegidos no están a distancia regular, no se pueden describir con strides, y NumPy **copia**.

Con eso, tus tres casos:

```python
fila = datos[0]            # básica → vista
fila /= 10                 # operación in situ sobre la vista → cambia datos

cols = datos[:, [0, 2]]    # avanzada → copia
cols *= 100                # muta la copia; datos no se entera
```

El tercero parece contradecir la regla, pero `datos[:, [0, 2]] *= 100` no es "obtener y mutar". Python lo traduce en tres pasos:

```python
tmp = datos[:, [0, 2]]     # copia (avanzada)
tmp *= 100                 # muta la copia
datos[:, [0, 2]] = tmp     # __setitem__: escribe la copia de vuelta en datos
```

La escritura final es lo que modifica `datos`. Un operador aumentado sobre una expresión de indexación siempre termina en una asignación.

**Cómo comprobarlo sin adivinar:**

```python
np.shares_memory(datos, fila)   # True
np.shares_memory(datos, cols)   # False
fila.base is datos              # True: fila es una vista de datos
cols.base is None               # True: cols es dueña de su memoria
```

**Chuleta de qué devuelve vista y qué copia:**

| Devuelve vista (comparte memoria) | Devuelve copia |
|---|---|
| slices, `a[i]`, `a[:, None]` | `a[[0, 2]]`, `a[mask]` |
| `a.T`, `a.view()`, `a.squeeze()` | `a.astype(...)` (incluso al mismo dtype) |
| `a.reshape(...)` y `a.ravel()` **si** la memoria es contigua | `a.flatten()`, `np.array(a)` |
| | cualquier aritmética no in situ: `a * 2`, `a + b` |

`reshape` y `ravel` son los traicioneros: devuelven vista cuando pueden y copia cuando no (por ejemplo tras un `.T`), así que el comportamiento depende del *layout*, no del código.

**Defensas prácticas:**

1. Cuando quieras un objeto independiente, pide la copia tú: `fila = datos[0].copy()`. Es barato y deja la intención escrita.
2. Cuando quieras que nadie mute el original, bloquéalo: `datos.flags.writeable = False`. Cualquier escritura a través de una vista lanza `ValueError: assignment destination is read-only`, que es exactamente el error que quieres ver en desarrollo.
3. Las operaciones in situ (`/=`, `*=`, `+=`) son las únicas que propagan cambios a través de vistas. `fila = fila / 10` crea un array nuevo y no toca `datos`.""",
            },
        ]
    },
    # 3) NumPy: vectorización (SISTEMA, intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Este bucle sobre un DataFrame de 2 millones de filas tarda más de un minuto. ¿Cómo lo vectorizo sin cambiar el resultado?

```python
resultado = []
for precio, cantidad, vip in zip(df["precio"], df["cantidad"], df["vip"]):
    total = precio * cantidad
    if vip and total > 1000:
        total *= 0.9
    elif total > 5000:
        total *= 0.95
    resultado.append(total)
df["total"] = resultado
```""",
            },
            {
                "role": "assistant",
                "content": """Un `if/elif` por fila se traduce a `np.select`, que evalúa todas las condiciones sobre el array completo y toma la primera que se cumple, igual que tu cadena de `if`.

```python
import numpy as np

precio = df["precio"].to_numpy()
cantidad = df["cantidad"].to_numpy()
vip = df["vip"].to_numpy(dtype=bool)

total = precio * cantidad
condiciones = [
    vip & (total > 1000),   # primera rama del if
    total > 5000,           # elif
]
factores = [0.9, 0.95]
df["total"] = total * np.select(condiciones, factores, default=1.0)
```

Por qué es equivalente y no solo parecido:

- **El orden importa en `np.select` exactamente igual que en `if/elif`.** Una fila VIP con total 8000 cumple las dos condiciones; tu bucle aplica 0.9 (la primera rama corta la cadena) y `np.select` también, porque elige la primera condición verdadera.
- `default=1.0` cubre el caso en que ninguna se cumple: multiplicar por 1 deja el total intacto, como tu bucle.
- Uso `&` y no `and`: `and` sobre arrays lanza `ValueError: The truth value of an array ... is ambiguous`. Los paréntesis alrededor de la comparación son obligatorios porque `&` tiene más prioridad que `>`.

Verifica antes de borrar el bucle, sobre una muestra:

```python
muestra = df.sample(50_000, random_state=0)
esperado = np.array([bucle_original(p, c, v) for p, c, v in zip(muestra["precio"], muestra["cantidad"], muestra["vip"])])
assert np.allclose(vectorizado(muestra), esperado)
```

(`np.allclose` y no `==`: el orden de las multiplicaciones en coma flotante puede diferir en el último bit.)

Qué esperar: el bucle hace ~2 millones de iteraciones de intérprete con creación de objetos Python en cada una; la versión vectorizada hace cinco pasadas en C sobre arrays contiguos. El salto habitual es de un minuto a menos de un segundo.

Dos trampas al vectorizar:

1. `np.vectorize` **no vectoriza**: es un bucle de Python con otra sintaxis. Sirve para que una función escalar acepte arrays, no para ir más rápido.
2. Si una rama fuera cara de calcular (una función no vectorizable), `np.select` la evaluaría igualmente para todas las filas. En ese caso calcula solo sobre el subconjunto con una máscara: `total[mask] = f(total[mask])`. Si de verdad no hay forma de expresarlo con arrays, Numba (`@njit`) compila el bucle tal cual lo tienes.""",
            },
        ]
    },
    # 4) NumPy: dtypes y desbordamiento (inglés, principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Why does `np.array([200], dtype=np.uint8) + 100` give me `[44]`? And then `+ 300` crashes with OverflowError instead of just giving a big number. I'm on NumPy 2.",
            },
            {
                "role": "assistant",
                "content": """Both behaviors come from the same fact: the dtype of your array is `uint8`, which holds 0 to 255, and NumPy keeps that dtype when you add a Python scalar.

**`+ 100` gives 44** because 200 + 100 = 300 does not fit in 8 bits, so it wraps around: 300 mod 256 = 44. Array arithmetic in NumPy does **not** check for integer overflow; it is C arithmetic on fixed-width integers. There is no warning for arrays (scalars like `np.uint8(200) + np.uint8(100)` do emit `RuntimeWarning: overflow encountered in scalar add`, arrays stay silent).

**`+ 300` raises** because of NumPy 2's promotion rules (NEP 50). A Python `int` is "weak": it adopts the array's dtype instead of forcing an upcast. The value 300 cannot even be represented as `uint8`, so NumPy refuses before computing anything:

```
OverflowError: Python integer 300 out of bounds for uint8
```

In NumPy 1.x the same expression silently upcast the array to `uint16` because promotion looked at the *value* of the scalar. NumPy 2 made the dtype of the result depend only on the dtypes involved, which is more predictable but surfaces this error.

What to do depends on what you want:

```python
import numpy as np

a = np.array([200], dtype=np.uint8)

a.astype(np.int64) + 300        # [500]: widen first, then compute
a + np.uint16(300)              # [500]: promotion uint8 + uint16 -> uint16
(a.astype(np.uint16) + 100) // 2   # safe averaging of two 8-bit images
```

Practical rules:

- Pick the dtype for the **largest intermediate value**, not for the final result. Averaging two `uint8` images with `(x + y) // 2` overflows in the addition; `x // 2 + y // 2` or a wider dtype avoids it.
- `np.iinfo(np.uint8)` and `np.finfo(np.float32)` tell you the limits when in doubt.
- Reductions are safer than elementwise ops: `a.sum()` accumulates in the platform's default integer (64-bit) and `a.mean()` in `float64`, so `np.array([200, 200], dtype=np.uint8).sum()` is 400, not 144.
- `float32` has its own version of this problem: only ~7 significant digits, so `np.float32(16_777_216) + 1` is still 16777216. Use `float64` for accumulators and `float32` for storage when memory matters.""",
            },
        ]
    },
    # 5) NumPy: generador aleatorio y reproducibilidad (España, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "En el equipo tenemos código con `np.random.seed(42)` por todas partes y otro compañero dice que hay que usar `default_rng`. ¿Es solo una cuestión de estilo o hay una razón de verdad? Vale cualquiera de las dos para que los experimentos sean reproducibles, ¿no?",
            },
            {
                "role": "assistant",
                "content": """Hay razones de verdad, y la reproducibilidad es precisamente la que falla con `np.random.seed`.

**El problema del estado global.** `np.random.seed(42)` fija el estado de *un* generador global compartido por todo el proceso. Cualquier cosa que consuma números aleatorios entre tu semilla y tu código (una librería, un `import` que inicializa algo, un test que se ejecuta antes en la misma sesión) desplaza la secuencia y tus resultados cambian sin que hayas tocado nada. Con un `Generator` propio, el estado es local al objeto y nadie más lo consume.

**La API moderna (NumPy ≥ 1.17):**

```python
import numpy as np

rng = np.random.default_rng(42)          # PCG64, más rápido y con mejores propiedades que MT19937

x = rng.normal(loc=0.0, scale=1.0, size=(1000, 3))
indices = rng.permutation(len(x))        # barajar sin tocar x
muestra = rng.choice(x, size=10, replace=False, axis=0)
enteros = rng.integers(0, 10, size=5)    # [0, 10): sustituye a randint
```

Pasa `rng` como argumento a las funciones que lo necesiten en vez de dejar que lo busquen en el aire. Es una dependencia más, y así se ve en la firma.

**Paralelismo sin colisiones.** Con `np.random.seed`, cuatro workers sembrados con `42, 43, 44, 45` producen secuencias que pueden solaparse. `SeedSequence.spawn` genera semillas hijas estadísticamente independientes:

```python
raiz = np.random.SeedSequence(42)
semillas = raiz.spawn(4)
generadores = [np.random.default_rng(s) for s in semillas]
```

**Qué hacer con el código existente.** No hace falta migrarlo todo de golpe, pero sí cortar el estado global en las fronteras:

- Nuevos módulos: aceptan `rng: np.random.Generator` y nunca llaman a `np.random.*`.
- scikit-learn: sus estimadores aceptan `random_state` como entero o `RandomState`, no como `Generator`. Pásale un entero derivado: `random_state=int(rng.integers(2**31 - 1))`.
- Tests: fixture `rng = np.random.default_rng(0)` por test, nunca una semilla global en `conftest.py`.

Sobre tu última pregunta: una semilla fija hace reproducible **una ejecución aislada**. No hace reproducible una suite de tests ejecutada en otro orden ni un script que importa una librería nueva. Esa es la diferencia que el `Generator` sí resuelve.""",
            },
        ]
    },
    # 6) pandas: SettingWithCopyWarning (usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": """Me sale esto en pandas y no sé si es grave:

```
SettingWithCopyWarning: A value is trying to be set on a copy of a slice from a DataFrame.
Try using .loc[row_indexer,col_indexer] = value instead
```

Mi código:

```python
activos = df[df["estado"] == "activo"]
activos["descuento"] = 0.1
```

Funciona, `activos` tiene la columna. ¿Lo ignoro?""",
            },
            {
                "role": "assistant",
                "content": """No lo ignores, pero tampoco es un bug en tu caso: es pandas diciendo «no sé si querías modificar `df` o no». Resuélvelo dejando la intención escrita y el warning desaparece.

**Por qué aparece.** `df[mask]` puede devolver una vista o una copia según cómo esté almacenado `df`; pandas 2.x no lo garantiza. Cuando luego asignas una columna sobre ese resultado, pandas no sabe si esperabas que el cambio llegara a `df`, y avisa. En tu caso quieres un objeto nuevo, así que el resultado es el correcto. Pero el mismo warning cubre un caso donde el resultado es **incorrecto en silencio**:

```python
df[df["estado"] == "activo"]["descuento"] = 0.1   # asigna sobre una copia temporal y la tira
"descuento" in df.columns                          # False: el cambio se perdió
```

**Arreglo según lo que quieras:**

1. Quieres un DataFrame independiente (tu caso):

```python
activos = df[df["estado"] == "activo"].copy()
activos["descuento"] = 0.1
```

El `.copy()` convierte la ambigüedad en una decisión: `activos` es tuyo, `df` no cambia, sin warning.

2. Quieres escribir en `df` solo para las filas activas:

```python
df.loc[df["estado"] == "activo", "descuento"] = 0.1
```

Una sola operación de indexación, pandas sabe exactamente sobre qué objeto escribe. Las filas no activas quedan con `NaN` en la columna nueva; si prefieres 0, crea la columna antes: `df["descuento"] = 0.0` y luego el `.loc`.

**Qué cambia con Copy-on-Write.** En pandas 3 (y en 2.x si activas `pd.options.mode.copy_on_write = True`) el modelo es simple: cualquier objeto derivado se comporta como una copia, siempre. Tu código original funciona sin warning y sin `.copy()`, y el caso peligroso (`df[mask]["col"] = x`) directamente no modifica nada y emite un `ChainedAssignmentError` como warning. Activarlo hoy en tus tests es la forma barata de descubrir qué partes del código dependían de la ambigüedad:

```python
import pandas as pd
pd.options.mode.copy_on_write = True    # o "warn" para ver los sitios afectados sin cambiar el comportamiento
```

Comprobación mínima para cada variante: `assert "descuento" not in df.columns` después de la opción 1 y `assert df.loc[df["estado"] == "activo", "descuento"].eq(0.1).all()` después de la 2.""",
            },
        ]
    },
    # 7) pandas: groupby/agg -> pivot_table (multiturno, system variante)
    {
        "messages": [
            {"role": "system", "content": "Responde en español neutro, con código completo y ejecutable y sin relleno."},
            {
                "role": "user",
                "content": "Tengo un DataFrame `ventas` con columnas region, producto, pedido_id, fecha, importe. Necesito por region y producto: ingresos totales, ticket medio, número de pedidos distintos y fecha de la última venta. Lo hago con cuatro groupby separados y luego los junto, seguro que hay una forma mejor.",
            },
            {
                "role": "assistant",
                "content": """Un solo `groupby` con *named aggregation*: cada columna de salida se define como `(columna_origen, función)`.

```python
resumen = (
    ventas.groupby(["region", "producto"], as_index=False, observed=True)
    .agg(
        ingresos=("importe", "sum"),
        ticket_medio=("importe", "mean"),
        pedidos=("pedido_id", "nunique"),
        ultima_venta=("fecha", "max"),
    )
)
```

Tres decisiones:

- `as_index=False` deja `region` y `producto` como columnas normales en vez de un `MultiIndex`. Para seguir operando (merge, exportar a CSV) es casi siempre lo que quieres.
- `observed=True` solo importa si `region` o `producto` son `category`: evita que aparezcan combinaciones sin datos. pandas 2.1 avisa de que el valor por defecto cambia a `True` en pandas 3; escribirlo explícito quita el warning y fija el comportamiento.
- `"nunique"` cuenta pedidos distintos; `"count"` contaría filas (líneas de pedido), que es otra métrica.

Si además quieres el porcentaje que cada fila aporta a su región, eso no es una agregación sino una **transformación** (el resultado tiene el tamaño original):

```python
ventas["pct_region"] = ventas["importe"] / ventas.groupby("region")["importe"].transform("sum")
```

`transform` devuelve una Serie alineada con `ventas`, así que la división es directa, sin merge.""",
            },
            {
                "role": "user",
                "content": "Perfecto. Ahora me piden lo mismo pero como tabla: regiones en filas, meses en columnas y los ingresos en las celdas, con un total por región.",
            },
            {
                "role": "assistant",
                "content": """Eso es `pivot_table`. Primero deriva el mes, luego pivota con agregación:

```python
tabla = (
    ventas.assign(mes=ventas["fecha"].dt.to_period("M"))
    .pivot_table(
        index="region",
        columns="mes",
        values="importe",
        aggfunc="sum",
        fill_value=0,
        margins=True,
        margins_name="total",
    )
)
```

- `dt.to_period("M")` agrupa por mes natural y ordena cronológicamente (una cadena `"2025-01"` también ordenaría, pero un `Period` sabe sumarse y compararse).
- `fill_value=0` rellena las combinaciones región-mes sin ventas; sin él aparecen `NaN` y los totales siguen siendo correctos pero la tabla es incómoda de leer.
- `margins=True` añade la fila y columna `total`. Si solo quieres el total por región y no por mes, quita `margins` y calcula `tabla["total"] = tabla.sum(axis=1)`.

**`pivot` frente a `pivot_table`.** `pivot` es un puro reordenamiento: exige que cada par (region, mes) aparezca una sola vez y, si no, falla con `ValueError: Index contains duplicate entries, cannot reshape`. Como tienes muchas ventas por región y mes, necesitas `pivot_table`, que agrega. Usa `pivot` solo cuando los datos ya estén agregados y quieras garantizar que no se está sumando nada por accidente.

Para volver al formato largo (por ejemplo, para graficar o cargar en una base de datos), `melt` es la inversa:

```python
largo = tabla.drop(columns="total").drop(index="total").reset_index().melt(
    id_vars="region", var_name="mes", value_name="ingresos"
)
```""",
            },
        ]
    },
    # 8) pandas: merge que duplica filas (usuario trae síntoma, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Hice un merge entre `pedidos` (120k filas) y `clientes` por `cliente_id` y la suma de `importe` pasó de 4.1M a 6.8M. No he tocado los importes. ¿Cómo puede un merge cambiar una suma?",
            },
            {
                "role": "assistant",
                "content": """Un merge no cambia valores, pero sí puede **repetir filas**. Si algún `cliente_id` aparece más de una vez en `clientes`, cada pedido de ese cliente se empareja con cada una de sus filas y el importe se cuenta dos, tres o más veces. El salto de 4.1M a 6.8M encaja con eso.

Compruébalo antes de arreglar nada:

```python
clientes["cliente_id"].is_unique              # si da False, aquí está el problema
clientes["cliente_id"].value_counts().head()  # qué ids están repetidos y cuántas veces
```

Y hazle decir a pandas qué relación esperas, para que falle en vez de inflar:

```python
unido = pedidos.merge(
    clientes,
    on="cliente_id",
    how="left",
    validate="many_to_one",   # muchos pedidos → un cliente; lanza MergeError si clientes tiene duplicados
    indicator=True,           # columna _merge: 'both', 'left_only', 'right_only'
)
```

`validate="many_to_one"` es la línea que debería estar en todos tus merges contra tablas maestras: convierte un error silencioso en una excepción con nombre (`pandas.errors.MergeError: Merge keys are not unique in right dataset; not a many-to-one merge`).

El arreglo depende de por qué hay duplicados en `clientes`:

- Son filas idénticas (exportación repetida): `clientes = clientes.drop_duplicates(subset="cliente_id")`.
- Son versiones históricas (cambio de dirección, etc.): quédate con la vigente, por ejemplo `clientes.sort_values("actualizado").drop_duplicates("cliente_id", keep="last")`.
- Son datos legítimamente distintos (varios contactos por cliente): entonces la tabla no es una maestra de clientes y el merge no debe hacerse a ese nivel; agrégala primero.

Prueba de regresión para que no vuelva a pasar:

```python
assert len(unido) == len(pedidos)
assert abs(unido["importe"].sum() - pedidos["importe"].sum()) < 1e-6
```""",
            },
            {
                "role": "user",
                "content": "Eran versiones históricas, ya lo arreglé con keep='last'. Pero ahora veo que `edad` se me ha convertido en float con NaN y antes era int. ¿Por qué?",
            },
            {
                "role": "assistant",
                "content": """Porque el `how="left"` ha dejado pedidos **sin cliente**: esas filas reciben `NaN` en `edad`, y el entero de NumPy (`int64`) no puede contener `NaN`, así que pandas promociona toda la columna a `float64`.

Primero mide cuántos son; ya tienes la columna `_merge` del `indicator=True`:

```python
unido["_merge"].value_counts()
# both          118_930
# left_only       1_070     ← pedidos cuyo cliente_id no está en clientes
```

Antes de decidir qué hacer con ellos, descarta la causa tonta: tipos distintos en la clave. Si `pedidos["cliente_id"]` es `int64` y `clientes["cliente_id"]` es `object` (texto), no casará ninguno y lo verás como `left_only` masivo. `pedidos["cliente_id"].dtype == clientes["cliente_id"].dtype` tiene que ser `True`.

Si los huérfanos son reales (clientes borrados, pedidos de prueba), tienes dos opciones honestas:

1. **Conservar el entero con nulos**, usando el dtype anulable de pandas:

```python
unido["edad"] = unido["edad"].astype("Int64")   # I mayúscula: entero con soporte de <NA>
```

Las operaciones aritméticas y los `groupby` funcionan igual; la diferencia es que el nulo es `pd.NA` y no `NaN`, y que al exportar a NumPy tendrás que decidir un relleno.

2. **Rellenar con un valor explícito** si el negocio lo define: `unido["edad"] = unido["edad"].fillna(-1).astype("int64")`. Solo si `-1` significa algo documentado; un relleno arbitrario es peor que un nulo.

Lo que no conviene es cambiar a `how="inner"` para que el problema desaparezca: perderías 1.070 pedidos de la suma de importes y volverías a tener un total que no cuadra, esta vez por defecto en vez de por exceso.""",
            },
        ]
    },
    # 9) pandas: fechas, zonas horarias, resample (México, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un CSV con una columna `fecha` tipo '15/03/2025 14:30' en hora de la Ciudad de México y necesito totales por mes y por semana en UTC. Ahorita lo hago con un apply y strptime fila por fila y tarda muchísimo, además me salen warnings de que 'M' está deprecado. ¿Cómo lo checo bien?",
            },
            {
                "role": "assistant",
                "content": """Tres pasos: parsear con formato explícito, localizar la zona horaria y luego `resample`. Todo vectorizado, sin `apply`.

```python
import pandas as pd

df = pd.read_csv("ventas.csv")

# 1. Parseo con formato explícito: vectorizado y sin ambigüedad día/mes
df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
malas = df["fecha"].isna().sum()   # filas que no cumplían el formato; revísalas, no las ignores

# 2. Zona horaria: de hora local a UTC
df["fecha"] = (
    df["fecha"]
    .dt.tz_localize("America/Mexico_City", ambiguous="NaT", nonexistent="shift_forward")
    .dt.tz_convert("UTC")
)

# 3. Agregados por periodo
serie = df.set_index("fecha")["importe"]
por_mes = serie.resample("ME").sum()        # ME = month end (pandas ≥ 2.2); 'M' está deprecado
por_semana = serie.resample("W-MON").sum()  # semanas que terminan en lunes; usa 'W' para domingo
```

Por qué cada decisión:

- **`format=` explícito** es lo que hace que `to_datetime` sea rápido: sin él pandas infiere el formato y, si falla, cae a un parseo lento fila a fila. Además evita que `15/03` se interprete como mes 15 y `03/04` como 4 de marzo. `errors="coerce"` convierte lo que no encaja en `NaT` en vez de reventar; cuenta los `NaT` y decide qué hacer con ellos.
- **`tz_localize` y no `tz_convert`** para el primer paso: tus fechas son *naive* (no llevan zona), y localizar les asigna la que les corresponde. `tz_convert` es para pasar de una zona a otra una vez localizadas. Hacerlo al revés es el error más común y produce desfases de 6 horas.
- `ambiguous` y `nonexistent` cubren los cambios de horario. México eliminó el horario de verano en 2022, pero si hay datos anteriores existen horas que ocurrieron dos veces (`ambiguous`) o ninguna (`nonexistent`). `"NaT"` las marca en vez de inventar; `"shift_forward"` empuja la hora inexistente a la siguiente válida.
- **Alias de frecuencia en pandas 2.2+**: `"ME"` fin de mes, `"MS"` inicio de mes, `"QE"`, `"YE"`; para horas y minutos ahora es `"h"` y `"min"` en minúscula. Los antiguos (`"M"`, `"H"`) siguen funcionando con warning y desaparecen en pandas 3.

Si el CSV es grande, el parseo de fechas es lo primero que conviene dejar de repetir: guarda el resultado en Parquet (`df.to_parquet("ventas.parquet")`), que conserva el dtype `datetime64[ns, UTC]`. Un CSV pierde la zona horaria y te obliga a volver a parsear cada vez.

Comprobación rápida de que el desfase es el esperado: una venta a las `14:30` de Ciudad de México debe aparecer como `20:30 UTC`.""",
            },
        ]
    },
    # 10) pandas: Copy-on-Write (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Vamos a migrar a pandas 3 y me dicen que Copy-on-Write viene activado por defecto. ¿Qué me va a romper exactamente? Tenemos bastante código viejo con `inplace=True` y asignaciones encadenadas.",
            },
            {
                "role": "assistant",
                "content": """El modelo mental de Copy-on-Write cabe en una frase: **cualquier DataFrame o Serie derivado de otro se comporta como si fuera una copia independiente, siempre.** Lo que se rompe es el código que dependía de que a veces fuera una vista.

**1. Lo que cambia en silencio (prioridad alta).** Las escrituras a través de un objeto derivado ya no llegan al original:

```python
df["a"][0] = 1                 # antes: a veces modificaba df. Ahora: nunca, y avisa con ChainedAssignmentError
df[df["a"] > 0]["b"] = 1       # ídem
col = df["a"]; col.iloc[0] = 1 # modifica col, no df
```

pandas 3 emite un warning `ChainedAssignmentError` en los dos primeros casos; el tercero no avisa porque es perfectamente legítimo (`col` es un objeto nuevo). Reescritura: toda escritura al original pasa por **una sola operación de indexación**, `df.loc[fila, "a"] = 1` o `df.loc[df["a"] > 0, "b"] = 1`.

**2. Lo que ahora lanza error.** `to_numpy()` y `.values` devuelven, cuando pueden, una vista de solo lectura del bloque interno:

```python
arr = df["a"].to_numpy()
arr[0] = 99     # ValueError: assignment destination is read-only
```

Si necesitas mutar el array, pide la copia: `df["a"].to_numpy(copy=True)` o `.copy()`. Es un error ruidoso, así que los tests lo encuentran.

**3. Lo que sigue igual aunque parezca sospechoso.**

- `inplace=True` en métodos del propio objeto (`df.fillna(0, inplace=True)`, `df.sort_values("a", inplace=True)`) funciona. Lo que no funciona es usarlo para modificar un padre a través de un hijo: `df[mask].fillna(0, inplace=True)` modifica el hijo temporal y lo tira.
- `df.copy()` sigue siendo una copia real; `df2 = df` sigue siendo el mismo objeto.
- Rendimiento: mejora. `df2 = df[["a", "b"]]`, `df.rename(...)`, `df.reset_index()` ya no copian datos hasta que alguien escribe. El `.copy()` defensivo que antes evitaba el `SettingWithCopyWarning` ahora es innecesario, aunque inofensivo.

**Cómo encontrar los sitios afectados antes de migrar.** pandas 2.2 trae un modo de aviso que no cambia el comportamiento pero señala cada operación cuyo resultado va a diferir:

```python
import pandas as pd
pd.options.mode.copy_on_write = "warn"
```

Actívalo en `conftest.py`, ejecuta la suite con `-W error::FutureWarning` (o simplemente mira el log) y corrige cada warning. Cuando la suite esté limpia, cambia a `True` y vuelve a ejecutar: eso es exactamente lo que verá pandas 3. Si el código viejo no tiene tests, el modo `"warn"` en un script que recorra los flujos principales es la alternativa barata.

Demostración de la diferencia para que la pongas en un test de migración:

```python
df = pd.DataFrame({"a": [1, 2, 3]})
sub = df.iloc[:2]
sub.iloc[0, 0] = 100
assert df.iloc[0, 0] == 1    # con CoW: pasa siempre. Sin CoW: depende del layout interno
```""",
            },
        ]
    },
    # 11) pandas: rendimiento de lectura y procesamiento (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "My pandas script takes ~10 minutes to process a 3 GB CSV (filter some rows, compute a couple of derived columns with apply, group by customer). It also eats 20 GB of RAM. Where do I start?",
            },
            {
                "role": "assistant",
                "content": """Start with the read, because it decides both the time and the memory of everything after it. Then remove `apply`. Then stop reading CSV at all.

**1. Read only what you need, with the right dtypes.**

```python
import pandas as pd

dtypes = {
    "customer_id": "int32",
    "country": "category",       # low-cardinality strings: 10-50x less memory than object
    "amount": "float32",
}
df = pd.read_csv(
    "data.csv",
    usecols=["customer_id", "country", "amount", "ts", "status"],
    dtype=dtypes,
    parse_dates=["ts"],
    engine="pyarrow",            # multithreaded parser; needs pyarrow installed
)
df.memory_usage(deep=True).sum() / 1e9   # check: GB actually used
```

A 3 GB CSV read with defaults becomes 10-20 GB in memory because every text column is an `object` column of Python strings and every integer is `int64`. `usecols` drops columns before they exist; `category` and narrow numeric types shrink the rest. If you only need rows matching a filter, read in chunks and filter each one:

```python
parts = []
for chunk in pd.read_csv("data.csv", usecols=cols, dtype=dtypes, chunksize=1_000_000):
    parts.append(chunk[chunk["status"] == "paid"])
df = pd.concat(parts, ignore_index=True)
```

**2. Replace `apply(axis=1)` with column operations.** Row-wise `apply` calls a Python function once per row, building a `Series` each time; it is the slowest thing pandas can do. Almost every row function is expressible with column arithmetic, `np.where`/`np.select`, string methods (`df["x"].str.lower()`), or `map` with a dict for lookups. If you post the function I can translate it, but the pattern is: compute each branch on the whole column, then combine with a mask.

**3. Use the groupby machinery, not Python.** `df.groupby("customer_id").agg(total=("amount", "sum"), n=("amount", "size"))` runs in C. `groupby(...).apply(custom_python)` does not; prefer `agg` with built-in names or `transform`.

**4. Stop paying the CSV tax.** Convert once to Parquet and read that from then on:

```python
df.to_parquet("data.parquet")          # keeps dtypes, categories and timezones
df = pd.read_parquet("data.parquet", columns=cols, filters=[("status", "==", "paid")])
```

Parquet is columnar and compressed: reading five columns out of forty touches only those five, and `filters` pushes the row filter down to the reader. The same 3 GB CSV is typically 300-600 MB in Parquet and loads in seconds.

**5. If it is still too big for RAM.** pandas is single-threaded and in-memory by design. For a dataset that does not fit, the honest move is Polars (`pl.scan_parquet(...).filter(...).group_by(...).collect()`, lazy and multithreaded) or DuckDB (`duckdb.sql("SELECT ... FROM 'data.parquet'").df()`), both of which read Parquet directly and return a DataFrame at the end. Switching the whole pipeline is a bigger decision; switching the heavy aggregation step is a few lines.

Quick way to know where the time goes before changing anything: wrap each stage in `time.perf_counter()` prints. In pipelines like yours the read is usually 40-60 % and `apply` most of the rest.""",
            },
        ]
    },
    # 12) pandas: alineación por índice, loc vs iloc (rioplatense, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo dos DataFrames filtrados, `antes` y `despues`, los dos con 100 filas, y cuando hago `despues[\"precio\"] - antes[\"precio\"]` me devuelve casi todo NaN. Los chequeé y ninguno tiene nulos. ¿Qué estoy haciendo mal?",
            },
            {
                "role": "assistant",
                "content": """No es un bug: pandas **alinea por índice** antes de operar, y tus dos DataFrames filtrados conservan las etiquetas originales. Si `antes` quedó con los índices `[0, 3, 7, 12, ...]` y `despues` con `[1, 2, 5, 8, ...]`, la resta busca el `precio` con la misma etiqueta en ambos lados; donde no coincide, pone `NaN`. Que ambos tengan 100 filas es irrelevante para pandas; lo que cuenta son las etiquetas.

Mirá los índices y lo ves:

```python
antes.index[:5], despues.index[:5]
antes.index.equals(despues.index)   # False
```

Tenés tres formas de arreglarlo, según qué significa "la fila i" en tu caso:

1. **Las filas se corresponden por posición** (la fila 1 de `antes` es la misma entidad que la fila 1 de `despues`): descartá las etiquetas viejas.

```python
diferencia = despues["precio"].to_numpy() - antes["precio"].to_numpy()
# o, si querés seguir en pandas:
diferencia = despues["precio"].reset_index(drop=True) - antes["precio"].reset_index(drop=True)
```

2. **Las filas se corresponden por una clave** (`producto_id`): entonces el índice *debería* ser esa clave, y la alineación pasa a ser una ventaja en vez de un problema.

```python
a = antes.set_index("producto_id")["precio"]
d = despues.set_index("producto_id")["precio"]
diferencia = d - a            # alinea por producto; NaN solo donde un producto falta en un lado
```

3. **Querés que falle si no coinciden**, en vez de rellenar con NaN: pandas no tiene un modo estricto para la aritmética, así que ponelo vos antes de operar: `pd.testing.assert_index_equal(a.index, d.index)` (el mensaje dice qué etiquetas sobran en cada lado).

La opción 1 es la rápida; la 2 es la correcta cuando existe una clave, porque la posición es frágil (basta con que un filtro cambie el orden).

**`loc` y `iloc` son la misma distinción.** `df.loc[0]` es la fila con **etiqueta** 0; `df.iloc[0]` es la **primera** fila. Después de filtrar, `antes.loc[0]` puede lanzar `KeyError` (la etiqueta 0 se fue con el filtro) mientras que `antes.iloc[0]` siempre devuelve algo. Regla: `iloc` para posiciones, `loc` para etiquetas y máscaras booleanas, y nunca `df[0]` para filas (eso selecciona la *columna* llamada 0).""",
            },
        ]
    },
    # 13) Polars vs pandas (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estamos evaluando pasar un pipeline de pandas a Polars. ¿Qué gana uno de verdad y qué cuesta? No quiero el discurso de 'es 30x más rápido', quiero saber si merece la pena para un ETL de unos 50 GB diarios en Parquet que hoy corre en pandas por trozos.",
            },
            {
                "role": "assistant",
                "content": """Para tu caso concreto (Parquet, 50 GB/día, agregaciones, hoy troceado a mano) sí merece la pena, y la razón no es "es más rápido" sino que **elimina el troceado**: Polars lee Parquet de forma perezosa y en paralelo, y su motor streaming procesa datos mayores que la RAM sin que tú gestiones los trozos. Lo que cuesta es una reescritura real, no una traducción línea a línea.

**Qué se gana, con la causa de cada ganancia:**

| Ganancia | De dónde sale |
|---|---|
| Sin troceado manual | `scan_parquet` + `collect(engine="streaming")` procesan por lotes internamente |
| Lee menos datos | Pushdown de columnas y predicados al lector de Parquet: si filtras por fecha, no lee las *row groups* que no cumplen |
| Usa todos los núcleos | Cada expresión se paraleliza; pandas es monohilo salvo en el parser |
| Menos memoria | Arrow en memoria, strings compactos, sin objetos Python por celda |
| Menos bugs de alineación | No hay índice: las operaciones son posicionales o por `join` explícito |

**Qué cuesta:**

- **Reescritura.** La API es de expresiones: `pl.col("x").sum().over("grupo")` en lugar de `groupby().transform()`. No hay índice, ni `loc`, ni alineación automática, ni `MultiIndex`. Un pipeline de 2.000 líneas de pandas no se migra en una tarde.
- **UDFs por fila.** Si hoy tienes `apply` con funciones Python, Polars no las acelera (`map_elements` es tan lento como `apply`). Hay que expresarlas con operaciones nativas; es trabajo, aunque suele ser también donde más se gana.
- **Ecosistema.** scikit-learn, statsmodels, matplotlib y la mayoría de librerías esperan pandas o NumPy. La conversión `df.to_pandas()` es barata (Arrow, a menudo sin copia), pero existe.
- **Estabilidad de API.** Polars 1.x es estable; en 0.x hubo renombres frecuentes (`groupby` → `group_by`, `pl.count` → `pl.len`). Si tienes código viejo de ejemplos, no compilará tal cual.

**Cómo se ve tu pipeline sin trozos:**

```python
import polars as pl

resultado = (
    pl.scan_parquet("eventos/fecha=2025-06-*/*.parquet")        # no lee nada todavía
    .filter(pl.col("tipo").is_in(["compra", "devolucion"]))      # pushdown al lector
    .select("cliente_id", "tipo", "importe", "ts")
    .with_columns(dia=pl.col("ts").dt.date())
    .group_by("cliente_id", "dia")
    .agg(
        importe=pl.col("importe").sum(),
        operaciones=pl.len(),
        devoluciones=(pl.col("tipo") == "devolucion").sum(),
    )
    .collect(engine="streaming")     # Polars ≥ 1.2x; en versiones anteriores era streaming=True
)
resultado.write_parquet("agregado/2025-06.parquet")
```

`lf.explain()` antes del `collect` te enseña el plan optimizado: verás el filtro y la selección de columnas empujados al `scan`, que es la confirmación de que no vas a leer 50 GB.

**Recomendación:** no migres el pipeline entero. Migra el paso pesado (lectura + filtro + agregación), devuelve un DataFrame pequeño con `.to_pandas()` y deja el resto (modelos, gráficos, informes) como está. Mide con tus datos reales en un día de muestra; en ETL de agregación sobre Parquet la mejora suele ser de un orden de magnitud en tiempo y de varias veces en memoria, pero el número que importa es el tuyo. Si tras eso el resto del pipeline sigue siendo el cuello de botella, entonces decides la segunda fase con datos.""",
            },
        ]
    },
    # 14) Polars: lazy API (system variante, intermedio)
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero de datos senior. Respondes con precisión, con ejemplos ejecutables y sin relleno."},
            {
                "role": "user",
                "content": "¿Cuál es la diferencia práctica entre `pl.read_parquet` y `pl.scan_parquet`? Si al final llamo a `collect()` y me devuelve lo mismo, ¿para qué el rodeo?",
            },
            {
                "role": "assistant",
                "content": """La diferencia es **cuándo** se ejecuta y, sobre todo, **qué se ejecuta**. `read_parquet` carga el archivo entero en memoria y luego aplicas operaciones una a una. `scan_parquet` devuelve un `LazyFrame`: un plan de consulta que Polars optimiza como un todo antes de tocar el disco. El resultado es el mismo; el trabajo para llegar a él, no.

```python
import polars as pl

lf = (
    pl.scan_parquet("eventos/*.parquet")
    .filter(pl.col("fecha") >= pl.date(2025, 1, 1))
    .select("usuario_id", "fecha", "tipo", "valor")
    .with_columns(mes=pl.col("fecha").dt.truncate("1mo"))
    .group_by("mes", "tipo")
    .agg(total=pl.col("valor").sum(), usuarios=pl.col("usuario_id").n_unique())
    .sort("mes", "tipo")
)
print(lf.explain())      # plan optimizado, sin ejecutar nada
df = lf.collect()
```

Lo que el optimizador hace con ese plan y que la versión *eager* no puede hacer:

1. **Projection pushdown.** Solo lee del Parquet las cuatro columnas del `select`, aunque el archivo tenga cuarenta. Con `read_parquet` leerías las cuarenta y luego descartarías.
2. **Predicate pushdown.** El filtro por fecha baja hasta el lector, que usa las estadísticas de cada *row group* del Parquet para saltarse bloques enteros sin descomprimirlos.
3. **Fusión y reordenación.** Varios `with_columns` consecutivos se ejecutan en una pasada; un filtro escrito después de un `select` se mueve antes si es más barato.
4. **Streaming.** `lf.collect(engine="streaming")` ejecuta el plan por lotes y permite agregar datasets mayores que la RAM. Para escribir directamente sin materializar: `lf.sink_parquet("salida.parquet")`.

El `explain()` lo muestra: en el plan verás algo como `Parquet SCAN ... PROJECT 4/40 COLUMNS; SELECTION: [(col("fecha")) >= (2025-01-01)]`. Esa línea es la prueba de que no vas a leer todo el archivo.

**Cuándo usar cada uno:**

- `scan_*` siempre que la fuente sea un archivo y el pipeline tenga más de un paso. Es la forma por defecto.
- `read_*` para datos pequeños que vas a inspeccionar interactivamente, o cuando necesitas el DataFrame ya materializado para pasarlo a otra librería.
- Un `DataFrame` se convierte en `LazyFrame` con `.lazy()` y viceversa con `.collect()`, así que puedes combinar ambos sin rehacer nada.

Dos detalles que sorprenden al venir de pandas: los errores de nombres de columna o de tipos no saltan al construir el plan sino en el `collect()` (o en `explain()`, que sí resuelve el esquema), y `lf.collect_schema()` te da los tipos resultantes sin ejecutar la consulta, útil para validar un pipeline en tests sin datos reales.""",
            },
        ]
    },
    # 15) Polars: traducir pandas (rioplatense, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """Estoy pasando código de pandas a Polars y me trabé con esto:

```python
df["pct"] = df["importe"] / df.groupby("usuario")["importe"].transform("sum")
df = df.merge(usuarios[["usuario", "pais"]], on="usuario", how="left")
```

¿Cómo lo escribo en Polars? Lo del `transform` no lo encuentro.""",
            },
            {
                "role": "assistant",
                "content": """El equivalente de `transform` es una **expresión de ventana** con `.over()`: calcula la agregación por grupo y la devuelve alineada con cada fila, sin cambiar el tamaño del DataFrame. El `merge` es `join`.

```python
import polars as pl

df = df.with_columns(
    pct=pl.col("importe") / pl.col("importe").sum().over("usuario")
).join(
    usuarios.select("usuario", "pais"),
    on="usuario",
    how="left",
)
```

Diferencias respecto a pandas que conviene tener en la cabeza:

- `with_columns` **devuelve un DataFrame nuevo**; no hay asignación `df["col"] = ...` ni `inplace`. Reasignás o encadenás.
- `.over("usuario")` acepta varias columnas (`.over("usuario", "mes")`) y cualquier agregación: `mean`, `max`, `n_unique`, `rank`.
- `join` no alinea por índice porque no hay índice; solo por las claves que le pasás. Si `usuarios` tiene usuarios repetidos, el `left` duplica filas igual que en pandas; `validate="m:1"` lo convierte en error.
- Si las columnas no clave coinciden en nombre, Polars les añade `_right` a las del lado derecho (pandas usa `_x`/`_y`).""",
            },
            {
                "role": "user",
                "content": "Buenísimo. Y una media móvil de 7 días del importe por usuario, ordenada por fecha, ¿también con over?",
            },
            {
                "role": "assistant",
                "content": """Sí, pero con una distinción que pandas no te obliga a hacer: **7 filas** o **7 días de calendario**.

Si querés las últimas 7 operaciones de cada usuario (ventana por número de filas):

```python
df = df.sort("usuario", "fecha").with_columns(
    media_7=pl.col("importe").rolling_mean(window_size=7, min_samples=1).over("usuario")
)
```

El `sort` previo es obligatorio: `rolling_mean` opera en el orden físico de las filas dentro de cada grupo, y `over` no ordena por vos. `min_samples=1` hace que las primeras filas de cada usuario tengan media en vez de null (pandas lo llama `min_periods`).

Si querés 7 días de calendario (una ventana temporal, que es lo que suele significar "media móvil de 7 días" en negocio):

```python
df = df.sort("fecha").with_columns(
    media_7d=pl.col("importe").rolling_mean_by("fecha", window_size="7d").over("usuario")
)
```

`rolling_mean_by` usa la columna `fecha` como eje temporal: la ventana de cada fila son las operaciones del mismo usuario en los 7 días anteriores (incluida la propia fila), aunque sean 2 o 30. Requiere que `fecha` sea `Date` o `Datetime` y que el DataFrame esté ordenado por ella.

Comprobación mínima para distinguir las dos: un usuario con 3 operaciones el día 1 y 1 el día 10. Con `window_size=7` filas, la media del día 10 incluye las del día 1; con `"7d"`, no.""",
            },
        ]
    },
    # 16) PyTorch: errores de dtype y device (usuario trae errores, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi primer modelo en PyTorch y me peleo con los tensores. Cargo los datos con NumPy y hago:

```python
X = torch.from_numpy(features)   # features es un ndarray de shape (N, 20)
y = torch.from_numpy(labels)
model = nn.Sequential(nn.Linear(20, 64), nn.ReLU(), nn.Linear(64, 1))
out = model(X)
```

y revienta con:

```
RuntimeError: mat1 and mat2 must have the same dtype, but got Double and Float
```""",
            },
            {
                "role": "assistant",
                "content": """`features` es un array de `float64` (el dtype por defecto de NumPy), así que `torch.from_numpy` produce un tensor `torch.float64`, que PyTorch llama `Double`. Los pesos de `nn.Linear` son `torch.float32` (`Float`). PyTorch no promociona tipos en una multiplicación de matrices: exige que coincidan, y falla.

Convierte los datos a `float32` en el momento de crear el tensor:

```python
import torch
import torch.nn as nn

X = torch.as_tensor(features, dtype=torch.float32)   # copia solo si hace falta cambiar el dtype
y = torch.as_tensor(labels, dtype=torch.float32).unsqueeze(1)   # (N,) -> (N, 1), como la salida del modelo
```

Por qué `float32` y no convertir el modelo a `float64`: la mitad de memoria, varias veces más rápido en GPU y es lo que esperan todas las capas, pérdidas y utilidades (AMP, `torch.compile`). `float64` en deep learning solo tiene sentido en casos numéricos muy concretos.

Dos detalles de `from_numpy` que conviene saber aunque ya no lo uses aquí:

- Comparte memoria con el array: modificar uno modifica el otro. `torch.as_tensor` también cuando no hay conversión; `torch.tensor(arr)` siempre copia.
- Hereda el dtype tal cual: un array `int64` de etiquetas se queda en `torch.int64` (`Long`), que es justo lo que `CrossEntropyLoss` necesita. Para regresión con `MSELoss`, en cambio, las etiquetas deben ser `float32` como arriba.

Si el dtype te llega de muchos sitios, un `torch.set_default_dtype` no es la solución: deja los datos en `float32` en la frontera (donde los cargas) y el resto del código no necesita pensar en ello.""",
            },
            {
                "role": "user",
                "content": """Ya va. Ahora quise usar la GPU, hice `model.to("cuda")` y `X.to("cuda")`, y me sale:

```
RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cuda:0 and cpu! (when checking argument for argument mat1 in method wrapper_CUDA_addmm)
```""",
            },
            {
                "role": "assistant",
                "content": """`X.to("cuda")` **no mueve `X`**: devuelve un tensor nuevo en la GPU y tú lo descartaste. `X` sigue en CPU, el modelo está en `cuda:0`, y la multiplicación encuentra operandos en dos dispositivos.

La asimetría que causa el error:

- Para **módulos**, `model.to(device)` es in situ: mueve los parámetros y además devuelve el propio módulo. `model.to("cuda")` sin reasignar funciona.
- Para **tensores**, `.to(device)` es funcional: el resultado hay que guardarlo. `X = X.to(device)`.

Patrón completo, con el dispositivo decidido una vez:

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = model.to(device)
X = X.to(device)
y = y.to(device)
out = model(X)
```

En un bucle de entrenamiento se hace por lote, no con el dataset entero (que puede no caber en la GPU):

```python
for xb, yb in loader:
    xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
    loss = criterion(model(xb), yb)
```

Y la tercera fuente habitual de este error, que te saldrá en cuanto escribas tu propio `nn.Module`: tensores creados dentro de `forward` con `torch.zeros(...)` o `torch.arange(...)` nacen en CPU. Dales el dispositivo de la entrada, `torch.zeros(n, device=x.device)`, o regístralos como *buffer* en `__init__` (`self.register_buffer("mask", mask)`) para que `model.to(device)` los mueva con el resto.""",
            },
        ]
    },
    # 17) PyTorch: autograd, acumulación de gradientes y memoria (usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi entrenamiento va bien las primeras 200 iteraciones y luego la pérdida se dispara a NaN, y además la memoria de la GPU sube hasta que peta con OOM. El bucle:

```python
epoch_loss = 0
for x, y in loader:
    x, y = x.to(device), y.to(device)
    out = model(x)
    loss = criterion(out, y)
    loss.backward()
    optimizer.step()
    epoch_loss += loss
print(epoch_loss / len(loader))
```

¿Es el learning rate?""",
            },
            {
                "role": "assistant",
                "content": """No es el learning rate. Tu bucle tiene dos bugs independientes y cada uno explica un síntoma.

**1. La pérdida se dispara porque los gradientes se acumulan.** `loss.backward()` no sobrescribe `param.grad`: **suma** sobre lo que ya hay. Sin `optimizer.zero_grad()`, en la iteración k el optimizador aplica la suma de k gradientes. El paso efectivo crece sin límite, el modelo se desestabiliza y llega a NaN. Que ocurra alrededor de la iteración 200 es solo cuándo la suma acumulada supera lo que el modelo tolera.

**2. La memoria crece porque `epoch_loss += loss` retiene el grafo.** `loss` es un tensor con `requires_grad=True` que referencia todo el grafo de ese lote, activaciones incluidas. Al sumarlo a `epoch_loss`, el acumulador referencia los grafos de todos los lotes y PyTorch no puede liberar ninguno hasta que termine la época. Acumula un número, no un tensor con historia.

El bucle corregido:

```python
model.train()
epoch_loss = 0.0
for x, y in loader:
    x, y = x.to(device), y.to(device)
    optimizer.zero_grad(set_to_none=True)   # antes del backward; set_to_none es el valor por defecto desde 2.0
    out = model(x)
    loss = criterion(out, y)
    loss.backward()
    optimizer.step()
    epoch_loss += loss.item()               # escalar de Python: sin grafo, sin GPU
print(epoch_loss / len(loader))
```

`loss.item()` sincroniza CPU y GPU una vez por lote; si eso te preocupa en modelos muy pequeños, acumula `loss.detach()` (tensor sin grafo) y llama a `.item()` una vez al final.

**Por qué PyTorch acumula a propósito.** Es la base de la *acumulación de gradientes*: procesar un lote grande en varios sublotes cuando no cabe en memoria.

```python
optimizer.zero_grad(set_to_none=True)
for i, (x, y) in enumerate(loader):
    loss = criterion(model(x.to(device)), y.to(device)) / pasos_acumulacion
    loss.backward()
    if (i + 1) % pasos_acumulacion == 0:
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
```

La misma mecánica que te estaba rompiendo el entrenamiento, usada a propósito y con el reseteo en el sitio correcto.

**Comprobación.** Dos líneas que te confirman cada arreglo:

```python
# tras optimizer.zero_grad(set_to_none=True): todos los .grad son None
assert all(p.grad is None for p in model.parameters())

# la memoria se estabiliza: imprime esto cada 50 iteraciones y debe dejar de crecer
print(torch.cuda.max_memory_allocated() / 1e9, "GB")
```

Si tras esto la pérdida sigue subiendo (pero sin llegar a NaN de golpe), entonces sí es momento de mirar el learning rate o añadir `torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)` antes de `optimizer.step()`.""",
            },
        ]
    },
    # 18) PyTorch: nn.Module y registro de parámetros (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": """Al crear el optimizador me sale `ValueError: optimizer got an empty parameter list`. Mi modelo:

```python
class MLP(nn.Module):
    def __init__(self, sizes):
        super().__init__()
        self.layers = [nn.Linear(a, b) for a, b in zip(sizes[:-1], sizes[1:])]

    def forward(self, x):
        for layer in self.layers[:-1]:
            x = torch.relu(layer(x))
        return self.layers[-1](x)
```

`forward` funciona, así que las capas existen.""",
            },
            {
                "role": "assistant",
                "content": """Las capas existen, pero `nn.Module` **no las ve**. Cuando asignas un atributo, `nn.Module.__setattr__` registra el valor como submódulo solo si es un `nn.Module`; una `list` de Python es opaca para él. Por eso `model.parameters()` está vacío, y por la misma razón `model.to("cuda")`, `model.state_dict()` y `model.eval()` tampoco llegarían a esas capas.

Sustituye la lista por `nn.ModuleList`, que es una lista que sí se registra:

```python
import torch
import torch.nn as nn


class MLP(nn.Module):
    def __init__(self, sizes: list[int]) -> None:
        super().__init__()
        self.layers = nn.ModuleList(
            nn.Linear(a, b) for a, b in zip(sizes[:-1], sizes[1:])
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for layer in self.layers[:-1]:
            x = torch.relu(layer(x))
        return self.layers[-1](x)


model = MLP([20, 64, 64, 1])
print(sum(p.numel() for p in model.parameters()))   # 5569, antes daba 0
```

Como tu `forward` es una cadena lineal, `nn.Sequential` lo deja aún más corto y sin bucle:

```python
def build_mlp(sizes: list[int]) -> nn.Sequential:
    layers: list[nn.Module] = []
    for a, b in zip(sizes[:-1], sizes[1:]):
        layers += [nn.Linear(a, b), nn.ReLU()]
    layers.pop()                       # sin ReLU tras la última capa
    return nn.Sequential(*layers)
```

La misma regla aplica a otros contenedores: un `dict` de capas necesita `nn.ModuleDict`, una lista de tensores entrenables `nn.ParameterList`, y un tensor suelto que deba entrenarse `nn.Parameter(torch.zeros(...))`. Para tensores que **no** se entrenan pero deben viajar con el modelo (máscaras, estadísticas), usa `self.register_buffer("mask", tensor)`: así los mueve `.to(device)` y los guarda `state_dict()`, pero el optimizador no los toca.

Comprobación rápida de que todo está registrado: `print(model)` lista los submódulos; si una capa no aparece ahí, el optimizador tampoco la verá.""",
            },
        ]
    },
    # 19) PyTorch: Dataset y DataLoader (system variante, multiturno)
    {
        "messages": [
            {"role": "system", "content": "Responde en español, con código completo y explicaciones breves."},
            {
                "role": "user",
                "content": "Tengo 200k imágenes en disco con sus etiquetas en un CSV. ¿Cómo monto un Dataset y un DataLoader que no sea un cuello de botella? Ahora cargo todo en una lista al principio y tarda 20 minutos antes de empezar a entrenar.",
            },
            {
                "role": "assistant",
                "content": """Carga perezosa: el `Dataset` guarda solo rutas y etiquetas, y abre cada imagen en `__getitem__`. El `DataLoader` paraleliza esas lecturas en procesos trabajadores mientras la GPU entrena con el lote anterior.

```python
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.transforms import v2


class ImagenesCSV(Dataset):
    def __init__(self, csv: Path, raiz: Path, transform) -> None:
        tabla = pd.read_csv(csv)
        self.rutas = [raiz / r for r in tabla["ruta"]]           # solo rutas: barato
        self.etiquetas = torch.as_tensor(tabla["etiqueta"].to_numpy(), dtype=torch.long)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rutas)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        with Image.open(self.rutas[i]) as img:
            x = self.transform(img.convert("RGB"))
        return x, self.etiquetas[i]


transform = v2.Compose([
    v2.Resize((224, 224)),
    v2.ToImage(),
    v2.ToDtype(torch.float32, scale=True),
    v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

dataset = ImagenesCSV(Path("etiquetas.csv"), Path("imagenes"), transform)
loader = DataLoader(
    dataset,
    batch_size=64,
    shuffle=True,
    num_workers=8,            # procesos que decodifican en paralelo; empieza por el número de núcleos
    pin_memory=True,          # memoria fijada: copia a GPU más rápida con .to(device, non_blocking=True)
    persistent_workers=True,  # no reinicia los procesos en cada época
    drop_last=True,
)
```

Por qué cada ajuste:

- **`num_workers`** es el que quita el cuello de botella: decodificar JPEG y redimensionar es trabajo de CPU, y con 0 workers ocurre en el proceso principal, en serie con la GPU. Súbelo hasta que `nvidia-smi` muestre la GPU ocupada de forma continua; más allá de eso solo gasta RAM.
- **`pin_memory`** y `non_blocking=True` solapan la copia a GPU con el cómputo.
- **`persistent_workers`** evita pagar el arranque de 8 procesos al inicio de cada época.
- En Windows y macOS los workers se lanzan con `spawn`, así que el código que crea el `DataLoader` debe estar bajo `if __name__ == "__main__":` o se duplicará en cada proceso.

Si incluso con workers la lectura sigue siendo el límite (discos de red, imágenes enormes), el siguiente paso es preprocesar una vez a un tamaño fijo y guardar en un formato de lectura secuencial (WebDataset, archivos `.npy` por shard), no cargar más en RAM.""",
            },
            {
                "role": "user",
                "content": "Gracias. Para otro proyecto tengo secuencias de longitud variable (tokens) y el DataLoader me falla al apilar: `RuntimeError: stack expects each tensor to be equal size`.",
            },
            {
                "role": "assistant",
                "content": """El `DataLoader` apila los elementos del lote con `torch.stack`, que exige tamaños iguales. Para longitudes variables necesitas un `collate_fn` propio que rellene (*padding*) hasta la secuencia más larga del lote y devuelva también las longitudes reales o una máscara.

```python
from torch.nn.utils.rnn import pad_sequence


def collate_secuencias(batch: list[tuple[torch.Tensor, int]]) -> dict[str, torch.Tensor]:
    secuencias, etiquetas = zip(*batch)
    longitudes = torch.tensor([len(s) for s in secuencias])
    rellenas = pad_sequence(secuencias, batch_first=True, padding_value=0)   # (B, L_max)
    mascara = torch.arange(rellenas.size(1))[None, :] < longitudes[:, None]  # True donde hay token real
    return {
        "tokens": rellenas,
        "mask": mascara,
        "lengths": longitudes,
        "labels": torch.tensor(etiquetas),
    }


loader = DataLoader(dataset, batch_size=32, shuffle=True, collate_fn=collate_secuencias, num_workers=4)
```

Decisiones:

- **`padding_value=0`** debe ser el id del token de relleno de tu vocabulario; si 0 es un token real, cambia el valor. El modelo nunca debe aprender del relleno: pásale `mask` (atención, `key_padding_mask` en `nn.TransformerEncoder`) o `lengths` (`pack_padded_sequence` para RNN).
- Rellenar **por lote**, no al máximo global del dataset: así un lote de secuencias cortas no arrastra cientos de ceros. Si quieres exprimirlo, ordena o agrupa el dataset por longitud (un *bucket sampler*) para que cada lote tenga longitudes parecidas.
- El `collate_fn` debe ser una función de nivel de módulo (no una lambda ni un método local) cuando `num_workers > 0`, porque los workers la reciben serializada con `pickle`.

Prueba mínima: un lote con secuencias de longitud 3 y 5 debe producir `tokens.shape == (2, 5)` y `mask.sum(dim=1).tolist() == [3, 5]`.""",
            },
        ]
    },
    # 20) PyTorch: bucle de entrenamiento completo con AMP, eval y curvas (SISTEMA, avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito un bucle de entrenamiento 'de verdad' en PyTorch 2.x para clasificación: train/val por época, mixed precision, gradient clipping, scheduler, guardar el mejor checkpoint y al final pintar las curvas. Lo que tengo es un script de tutorial que no hace nada de eso. ¿Me lo escribes bien de una vez?",
            },
            {
                "role": "assistant",
                "content": """Aquí tienes el bucle completo. Lo importante no son las líneas sino el orden de las operaciones y qué va dentro de cada contexto.

```python
from pathlib import Path

import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import DataLoader


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    scaler: torch.amp.GradScaler | None = None,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
    amp_dtype: torch.dtype = torch.bfloat16,
) -> tuple[float, float]:
    # Si hay optimizador entrenamos; si no, evaluamos. Un solo cuerpo evita que train y eval diverjan.
    training = optimizer is not None
    model.train(training)
    total_loss, correct, seen = 0.0, 0, 0
    context = torch.enable_grad() if training else torch.inference_mode()
    with context:
        for x, y in loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=device.type == "cuda"):
                logits = model(x)
                loss = criterion(logits, y)
            if training:
                optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)                                  # necesario para que el clipping vea gradientes reales
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
                if scheduler is not None:
                    scheduler.step()                                       # OneCycleLR avanza por lote, no por época
            total_loss += loss.item() * x.size(0)
            correct += (logits.argmax(dim=1) == y).sum().item()
            seen += x.size(0)
    return total_loss / seen, correct / seen


def train(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int,
    lr: float,
    out_dir: Path,
) -> dict[str, list[float]]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=lr, epochs=epochs, steps_per_epoch=len(train_loader)
    )
    # bf16 no necesita escalado de pérdida; fp16 sí. En GPUs sin bf16 (anteriores a Ampere) usa fp16 + scaler activo.
    amp_dtype = torch.bfloat16 if device.type == "cuda" and torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda" and amp_dtype == torch.float16))

    history: dict[str, list[float]] = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    best_val = float("inf")
    out_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, device, optimizer, scaler, scheduler, amp_dtype)
        va_loss, va_acc = run_epoch(model, val_loader, criterion, device, amp_dtype=amp_dtype)
        for k, v in zip(history, (tr_loss, va_loss, tr_acc, va_acc)):
            history[k].append(v)
        print(f"época {epoch:3d}  train {tr_loss:.4f}/{tr_acc:.3f}  val {va_loss:.4f}/{va_acc:.3f}")
        if va_loss < best_val:
            best_val = va_loss
            torch.save(
                {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "epoch": epoch, "val_loss": va_loss},
                out_dir / "best.pt",
            )
    plot_history(history, out_dir / "curvas.png")
    return history


def plot_history(history: dict[str, list[float]], path: Path) -> None:
    fig, (ax_loss, ax_acc) = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    epochs = range(1, len(history["train_loss"]) + 1)
    ax_loss.plot(epochs, history["train_loss"], label="train")
    ax_loss.plot(epochs, history["val_loss"], label="val")
    ax_loss.set(title="Pérdida", xlabel="época", ylabel="cross-entropy")
    ax_acc.plot(epochs, history["train_acc"], label="train")
    ax_acc.plot(epochs, history["val_acc"], label="val")
    ax_acc.set(title="Exactitud", xlabel="época", ylim=(0, 1))
    for ax in (ax_loss, ax_acc):
        ax.legend()
        ax.grid(alpha=0.3)
    fig.savefig(path, dpi=150)
    plt.close(fig)
```

Las decisiones que marcan la diferencia con el tutorial:

- **Un solo `run_epoch` para train y val.** El error clásico es que la validación olvida `model.eval()` (dropout y batchnorm activos) o el `no_grad`. Aquí el modo se deriva de si hay optimizador. `torch.inference_mode()` es `no_grad` más agresivo: además desactiva el *version counter* de los tensores, y es lo correcto cuando no vas a usar las salidas para ningún backward.
- **Orden dentro del paso**: `zero_grad` → forward bajo `autocast` → `backward` escalado → `unscale_` → clipping → `step` → `update`. El clipping antes de `unscale_` recortaría gradientes multiplicados por el factor de escala y sería inútil.
- **bf16 frente a fp16.** bf16 tiene el mismo rango que fp32, así que no hay *underflow* de gradientes y el `GradScaler` sobra (queda desactivado). fp16 necesita el scaler. El código elige según la GPU.
- **`OneCycleLR` se llama por lote**, dentro de `run_epoch`, porque está definido con `epochs * steps_per_epoch` pasos. Llamarlo una vez por época (el patrón de `StepLR` o `CosineAnnealingLR`) solo recorrería la primera fracción del ciclo y el *learning rate* nunca llegaría a bajar. Mezclar las dos convenciones es un bug silencioso: no hay error, solo un entrenamiento peor.
- **La pérdida se pondera por tamaño de lote** (`loss.item() * x.size(0)`) para que el último lote, más pequeño, no sesgue la media.
- **El checkpoint guarda `state_dict`**, no el modelo entero, y también el optimizador: así puedes reanudar y además cargar con `weights_only=True` sin problemas.

Si quieres probar `torch.compile`, es una línea tras mover el modelo al dispositivo: `model = torch.compile(model)`. Suele dar entre 1.3x y 2x en modelos convolucionales y transformers medianos; ten en cuenta que las claves del `state_dict` ganan el prefijo `_orig_mod.`, así que guarda `model._orig_mod.state_dict()` o quita el prefijo al cargar.""",
            },
        ]
    },
    # 21) PyTorch: shape mismatch en la capa lineal (inglés, usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": """I copied a CNN from a CIFAR-10 tutorial but my images are 64x64 RGB. Training crashes on the first batch:

```
RuntimeError: mat1 and mat2 shapes cannot be multiplied (32x8192 and 2048x10)
```

```python
import torch.nn as nn
import torch.nn.functional as F

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2)
        self.fc = nn.Linear(32 * 8 * 8, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(x.size(0), -1)
        return self.fc(x)
```

What do the two numbers mean?""",
            },
            {
                "role": "assistant",
                "content": """The error is the matmul inside `nn.Linear` complaining. `mat1` is your flattened activation, shape `(batch, features)` = `(32, 8192)`. `mat2` is the layer's weight seen as `(in_features, out_features)` = `(2048, 10)`. A matmul needs the inner dimensions to agree: 8192 is not 2048, so `fc` was built for a different input size than the one it receives.

Where the numbers come from. Both convs use `padding=1` with a 3x3 kernel, so they keep the spatial size; each `MaxPool2d(2)` halves it:

| stage | CIFAR (32x32) | yours (64x64) |
|---|---|---|
| input | 3x32x32 | 3x64x64 |
| conv1 + pool | 16x16x16 | 16x32x32 |
| conv2 + pool | 32x8x8 | 32x16x16 |
| flattened | 32·8·8 = **2048** | 32·16·16 = **8192** |

The tutorial's `32 * 8 * 8` is a hard-coded assumption about 32x32 input. Your images are twice as wide and twice as tall, so the flattened vector is four times longer.

Three fixes, from least to most robust:

**1. Fix the constant.** `nn.Linear(32 * 16 * 16, 10)`. Works, and breaks again the next time the input size or the architecture changes.

**2. Let PyTorch infer it.** `nn.LazyLinear(10)` resolves `in_features` on the first forward pass. Fine for prototyping; the weight does not exist until a batch has gone through, so run a dummy forward before creating the optimizer or saving a checkpoint.

**3. Make the head size-independent, which is what production CNNs do.** Pool each channel down to a single value before the classifier:

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class Net(nn.Module):
    def __init__(self, num_classes: int = 10) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2)
        self.gap = nn.AdaptiveAvgPool2d(1)      # (B, 32, H, W) -> (B, 32, 1, 1) for any H, W
        self.flatten = nn.Flatten()             # (B, 32, 1, 1) -> (B, 32)
        self.fc = nn.Linear(32, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        return self.fc(self.flatten(self.gap(x)))
```

Now 32x32, 64x64 or 224x224 inputs all work. The trade-off: global average pooling discards spatial layout, which is fine for classification and wrong for tasks where position matters (detection, segmentation). The head is also tiny (32 inputs), so if accuracy drops, widen the conv stack rather than going back to a giant `Linear`.

Two habits that catch this class of bug before training starts:

```python
model = Net()
with torch.no_grad():
    out = model(torch.zeros(2, 3, 64, 64))   # dummy batch of 2; never 1, BatchNorm would complain
assert out.shape == (2, 10), out.shape
```

And `nn.Flatten()` instead of `x.view(x.size(0), -1)`: same result, but `view` fails with `RuntimeError: view size is not compatible with input tensor's size and stride` on non-contiguous tensors (after a transpose, for instance), while `Flatten` copies only when it must.""",
            },
        ]
    },
    # 22) PyTorch: guardar y cargar, weights_only y map_location (Colombia, usuario trae error)
    {
        "messages": [
            {
                "role": "user",
                "content": """Entrené un modelo en el servidor con `torch.save(model, "modelo.pt")` y al cargarlo en mi portátil (sin GPU) con PyTorch 2.6 me sale un error larguísimo que termina en:

```
_pickle.UnpicklingError: Weights only load failed. This file can still be loaded, to do so you have two options, do those steps only if you trust the source of the checkpoint.
    (1) In PyTorch 2.6, we changed the default value of the `weights_only` argument in `torch.load` from `False` to `True`. Re-running `torch.load` with `weights_only` set to `False` will likely succeed, but it can result in arbitrary code execution.
```

Si pongo `weights_only=False` me sale otro: `AttributeError: Can't get attribute 'Net' on <module '__main__'>`. ¿Qué hago, pues?""",
            },
            {
                "role": "assistant",
                "content": """Los dos errores vienen de la misma decisión: guardaste el **objeto** modelo entero, y eso serializa con `pickle` la clase, su módulo de origen y hasta el dispositivo de cada tensor. Lo correcto es guardar el **`state_dict`** (solo los tensores) y reconstruir la clase desde el código. Con eso ninguno de los dos errores existe.

**Qué significa cada error.**

1. `Weights only load failed`. Desde PyTorch 2.6, `torch.load` usa `weights_only=True` por defecto: solo deserializa tensores, dicts, listas y tipos primitivos, porque un `pickle` arbitrario puede ejecutar código. Tu archivo contiene una instancia de `Net`, que no está en la lista permitida, y el cargador la rechaza. Es una medida de seguridad, no un bug.

2. `Can't get attribute 'Net' on <module '__main__'>`. Con `weights_only=False`, `pickle` sí intenta reconstruir la clase, pero la busca donde estaba al guardar: en `__main__` del script de entrenamiento. En tu portátil ese módulo no define `Net`, y falla. Funcionaría solo si el script de carga definiera `Net` exactamente igual y en el mismo sitio, que es una trampa que se rompe con cualquier refactor.

**Cómo rescatar el archivo que ya tienes.** Una sola vez, en el servidor, donde `Net` sí existe:

```python
import torch
from entrenamiento import Net    # o ejecútalo desde el mismo script que definió Net

model = torch.load("modelo.pt", weights_only=False)   # confías en el archivo porque lo generaste tú
torch.save(model.state_dict(), "modelo_pesos.pt")
```

**Cómo guardar y cargar de ahora en adelante.**

```python
# guardar (servidor)
checkpoint = {
    "model": model.state_dict(),
    "optimizer": optimizer.state_dict(),
    "epoch": epoch,
    "config": {"hidden": 256, "num_classes": 10},   # lo necesario para reconstruir Net
}
torch.save(checkpoint, "checkpoint.pt")

# cargar (portátil sin GPU)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
checkpoint = torch.load("checkpoint.pt", map_location=device)   # weights_only=True por defecto: solo tensores
model = Net(**checkpoint["config"]).to(device)
model.load_state_dict(checkpoint["model"])
model.eval()
```

Detalles que importan:

- **`map_location`** reubica los tensores al cargar. Sin él, un checkpoint guardado en `cuda:0` intenta volver a `cuda:0`, y en una máquina sin GPU falla con `RuntimeError: Attempting to deserialize object on a CUDA device but torch.cuda.is_available() is False`.
- **`load_state_dict` es estricto por defecto**: si falta una clave o sobra una, lanza `RuntimeError: Error(s) in loading state_dict` listando `Missing key(s)` y `Unexpected key(s)`. Eso es bueno. Los dos prefijos que suelen aparecer ahí son `module.` (modelo envuelto en `DataParallel` o `DistributedDataParallel`) y `_orig_mod.` (modelo pasado por `torch.compile`). Guarda siempre el `state_dict` del modelo desenvuelto (`model.module.state_dict()` o `model._orig_mod.state_dict()`); si ya tienes un archivo con prefijo, quítalo al cargar:

```python
pesos = {k.removeprefix("module."): v for k, v in checkpoint["model"].items()}
model.load_state_dict(pesos)
```

- **`model.eval()`** después de cargar, siempre que vayas a inferir: desactiva dropout y fija las estadísticas de BatchNorm. Es el olvido más frecuente y produce predicciones distintas en cada llamada.
- Guarda también la **configuración** necesaria para construir el modelo, como en el ejemplo. El `state_dict` no sabe cuántas capas tiene `Net`; si cambias la arquitectura, el archivo deja de cargar y el error de claves te lo dirá.

Comprobación de que el guardado es correcto, en el propio servidor antes de copiar nada: carga el `state_dict` en una instancia nueva y compara una predicción con la del modelo original sobre el mismo lote, `torch.allclose(model(x), model2(x))`. Si eso pasa, el archivo cargará en cualquier máquina con la misma clase.""",
            },
        ]
    },
    # 23) PyTorch: reproducibilidad (multiturno, intermedio/avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Pongo `torch.manual_seed(0)` al principio del script y aun así cada ejecución me da una accuracy distinta (±0.5 %). ¿Qué más hay que fijar?",
            },
            {
                "role": "assistant",
                "content": """`torch.manual_seed` fija el generador de PyTorch en CPU y GPU, pero tu script usa al menos otros dos generadores, los *workers* del `DataLoader` tienen el suyo, y además hay kernels de GPU que no son deterministas aunque fijes todo. Hay que cerrar cada fuente por separado.

**1. Todas las semillas, no una.**

```python
import random

import numpy as np
import torch


def seed_everything(seed: int) -> None:
    random.seed(seed)        # random de Python: barajados propios, augmentations con random.choice
    np.random.seed(seed)     # NumPy: augmentations de albumentations, splits de scikit-learn
    torch.manual_seed(seed)  # CPU y todas las GPUs (incluye torch.cuda.manual_seed_all)
```

`PYTHONHASHSEED` solo importa si algo depende del orden de iteración de un `set` de strings; si lo necesitas, expórtalo en el shell antes de arrancar el intérprete, porque dentro del script ya es tarde.

**2. El `DataLoader`.** El barajado toma su semilla del generador global de PyTorch, así que queda fijado, pero los *workers* son procesos nuevos: PyTorch siembra `torch` en cada uno a partir de la semilla base y **no** siembra `random` ni `numpy`. Si tus augmentations usan NumPy en `__getitem__`, con `num_workers > 0` cada worker produce la misma secuencia aleatoria en cada época (el bug clásico de «todas las épocas usan los mismos recortes»). Pásale un generador propio y un `worker_init_fn`:

```python
def seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % 2**32    # distinta por worker y por época
    np.random.seed(worker_seed)
    random.seed(worker_seed)


g = torch.Generator()
g.manual_seed(0)
loader = DataLoader(dataset, batch_size=64, shuffle=True, num_workers=4, worker_init_fn=seed_worker, generator=g)
```

**3. Los kernels no deterministas de la GPU.** cuDNN elige el algoritmo de convolución más rápido en cada ejecución, y algunas operaciones usan sumas atómicas cuyo orden depende del *scheduling* de la GPU. Para cerrarlo:

```python
torch.backends.cudnn.benchmark = False       # no pruebes algoritmos: usa siempre el mismo
torch.use_deterministic_algorithms(True)     # lanza error si una operación no tiene versión determinista
```

y en el shell, para cuBLAS: `export CUBLAS_WORKSPACE_CONFIG=:4096:8`.

El coste: entre un 10 % y un 30 % más lento según el modelo. Por eso no se deja activado siempre, solo cuando estás depurando y necesitas que dos ejecuciones sean idénticas bit a bit.

**Qué esperar después de esto.** Dos ejecuciones en la **misma máquina, misma versión de PyTorch y de CUDA** deben dar exactamente la misma pérdida en cada paso. Compruébalo con eso y no con la accuracy final: imprime la pérdida de los cinco primeros lotes en dos ejecuciones y compara. Si difiere ya en el primer lote, el problema está en los datos o en la inicialización; si diverge más tarde, es un kernel no determinista.""",
            },
            {
                "role": "user",
                "content": "Lo activé y ahora revienta: `RuntimeError: scatter_add_cuda_kernel does not have a deterministic implementation, but you set 'torch.use_deterministic_algorithms(True)'`. ¿Me rindo con la reproducibilidad?",
            },
            {
                "role": "assistant",
                "content": """No, pero sí toca decidir qué grado de reproducibilidad necesitas, porque el error te está diciendo que la versión bit a bit tiene un precio en tu modelo.

Tres salidas, de menos a más invasiva:

**1. Avisar en vez de fallar.** `torch.use_deterministic_algorithms(True, warn_only=True)` deja pasar la operación y emite un `UserWarning` con su nombre. Lo útil es que te da la **lista exacta** de operaciones no deterministas de tu modelo; suelen ser una o dos.

**2. Sustituir la operación.** `scatter_add_` en GPU suele venir de `index_add_`, del backward de `F.embedding` con `padding_idx`, de `EmbeddingBag` o de capas de grafos. Si la llamada es tuya y los índices son pocos, la alternativa determinista más simple es una matriz *one-hot* y un matmul, que da el mismo resultado:

```python
# equivalente determinista de: out.index_add_(0, idx, valores)   con out de shape (n, d)
out = F.one_hot(idx, num_classes=n).to(valores.dtype).T @ valores
```

Si el tensor es grande, haz esa operación concreta en CPU, donde `scatter_add_` sí es determinista. Si viene de una librería, mira si expone un modo determinista.

**3. Aceptar no determinismo a nivel de bit y exigirlo a nivel de conclusión.** Esta es la respuesta correcta para casi todos los proyectos. Lo que de verdad necesitas es que «el modelo A es mejor que el B» sea una afirmación reproducible, y eso no lo garantiza una semilla: lo garantiza **medir la varianza**. Entrena con 3 a 5 semillas y reporta media y desviación:

```python
resultados = [entrenar(seed=s) for s in (0, 1, 2, 3, 4)]
accs = np.array([r["val_acc"] for r in resultados])
print(f"{accs.mean():.4f} ± {accs.std(ddof=1):.4f}")
```

Si la diferencia entre dos configuraciones es menor que esa desviación, no es una diferencia. El ±0.5 % que viste al principio es, casi seguro, ruido de semilla y no un bug.

Regla práctica: determinismo estricto (opción 1 o 2) para depurar («¿por qué el paso 300 da NaN?»), donde necesitas reproducir un estado exacto; varianza entre semillas (opción 3) para cualquier comparación de modelos o hiperparámetros. Y deja la semilla fija igualmente, porque reduce el ruido aunque no lo elimine.""",
            },
        ]
    },
    # 24) PyTorch: el modelo no aprende, softmax + CrossEntropyLoss (SISTEMA, avanzado, debugging con método)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Clasificador de 10 clases con un ResNet pequeño. La pérdida arranca en 2.30 y se queda ahí 20 épocas, accuracy 10 %. Los datos están bien, los miré. Este es el forward y el bucle:

```python
def forward(self, x):
    x = self.backbone(x)
    x = self.head(x)
    return F.softmax(x, dim=1)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
for x, y in loader:
    optimizer.zero_grad()
    loss = criterion(model(x.to(device)), y.to(device))
    loss.backward()
    optimizer.step()
```""",
            },
            {
                "role": "assistant",
                "content": """El número ya es el diagnóstico: **2.30 = ln(10)**, la pérdida de un modelo que predice la distribución uniforme sobre 10 clases. No es que aprenda mal: es que casi no recibe gradiente. El bucle es correcto, así que la causa está en el `forward`: aplicas `softmax` y luego `CrossEntropyLoss`, que **ya incluye** `log_softmax`. Estás haciendo softmax dos veces.

Por qué eso lo congela y no solo lo ralentiza: `CrossEntropyLoss` espera *logits* de cualquier rango. Si le pasas probabilidades (valores en [0, 1] que suman 1), el `log_softmax` interno las vuelve a normalizar, y como la diferencia máxima entre dos entradas es 1, la razón entre la clase más y menos probable queda acotada por `e`, por muy seguro que esté el modelo. Para 10 clases, la pérdida mínima alcanzable pasa de 0 a unos 1.46, y los gradientes que llegan al *backbone* son minúsculos. Desde el uniforme apenas hay pendiente, y ahí se queda.

**Arreglo:** el `forward` devuelve logits.

```python
def forward(self, x: torch.Tensor) -> torch.Tensor:
    return self.head(self.backbone(x))      # logits: sin softmax
```

El `softmax` solo se aplica fuera, cuando necesitas probabilidades (calibración, umbrales, mostrar al usuario): `probs = model(x).softmax(dim=1)`. Para la clase predicha ni hace falta: `model(x).argmax(dim=1)` da lo mismo antes y después del softmax, porque es monótono.

**Cómo lo habría encontrado sin conocer la respuesta**, en el orden que descarta más con menos esfuerzo:

1. **Leer la pérdida inicial.** `ln(num_clases)` al empezar es lo normal con pesos aleatorios; que *se quede* ahí significa «no llega gradiente» y descarta un learning rate demasiado alto (eso explota, no se congela).
2. **Sobreajustar un solo lote.** Antes de 20 épocas con todo, 200 pasos con el mismo lote de 32 ejemplos. Un modelo sano lleva la pérdida a casi 0 en menos de 100 pasos. Si no puede memorizar 32 ejemplos, el problema es de modelo, pérdida o gradientes, nunca de datos insuficientes:

```python
x, y = next(iter(loader))
x, y = x.to(device), y.to(device)
model.train()
for step in range(200):
    optimizer.zero_grad(set_to_none=True)
    loss = criterion(model(x), y)
    loss.backward()
    optimizer.step()
    if step % 50 == 0:
        print(step, round(loss.item(), 4))
# con el softmax: 2.30, 2.29, 2.28, 2.27   ·   sin él: 2.30, 0.41, 0.02, 0.00
```

3. **Mirar la magnitud de los gradientes.** `sum(p.grad.norm() for p in model.parameters() if p.grad is not None)` tras un `backward`: con el softmax doble es órdenes de magnitud menor que sin él, y eso apunta directamente a la salida del modelo o a la pérdida.
4. Solo entonces las hipótesis caras: etiquetas desalineadas con las imágenes (barajar `x` e `y` por separado), normalización de entrada, `requires_grad` apagado por error en el backbone.

La misma familia de bugs: `nn.BCEWithLogitsLoss` con un `sigmoid` delante, y `nn.NLLLoss` **sin** `log_softmax` delante (ese sí lo necesita; es el único de los tres que no lo incluye). La regla: la última capa devuelve logits y la función de pérdida decide qué transformación aplica.

Verificación tras el cambio: la prueba del lote único debe bajar de 2.30 a menos de 0.1 en 200 pasos, y en el entrenamiento real la pérdida de la primera época debe quedar claramente por debajo de 2.30.""",
            },
        ]
    },
    # 25) scikit-learn: fuga de datos y Pipeline (usuario trae código, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi modelo da 0.94 de AUC en validación y en producción apenas 0.71. Esto es lo que hago antes de entrenar:

```python
df["ingresos"] = df["ingresos"].fillna(df["ingresos"].mean())
scaler = StandardScaler().fit(df[num_cols])
df[num_cols] = scaler.transform(df[num_cols])
df["ciudad_tasa"] = df.groupby("ciudad")["target"].transform("mean")   # target encoding
X_train, X_test, y_train, y_test = train_test_split(df.drop(columns="target"), df["target"], test_size=0.2)
clf = GradientBoostingClassifier().fit(X_train, y_train)
print(roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1]))
```

¿Es overfitting?""",
            },
            {
                "role": "assistant",
                "content": """No es overfitting: es **fuga de datos** (*leakage*), y de tres tipos en cuatro líneas. El 0.94 no mide la calidad del modelo, sino la del modelo cuando el conjunto de test ya ha contaminado el entrenamiento. El 0.71 de producción es el número real.

Las tres fugas, de menos a más grave:

1. **`fillna(mean())` sobre todo el dataset.** La media incluye filas de test. Fuga leve, pero el principio es el mismo que en las otras.
2. **`StandardScaler().fit(df)` antes del split.** Media y desviación calculadas con el test. También leve en la práctica; es la forma más común de empezar a contaminar.
3. **Target encoding con `groupby("ciudad")["target"].transform("mean")`.** Esta explica los 23 puntos. Cada fila recibe la tasa de positivos de su ciudad **calculada incluyendo su propio target**. En ciudades pequeñas, `ciudad_tasa` es casi una copia de la etiqueta; el modelo aprende a leer la respuesta, y en producción esa columna no la contiene.

La regla que resuelve las tres: **todo lo que se aprende de los datos (medias, escalas, codificaciones, selección de variables) se ajusta solo con entrenamiento y dentro del proceso de validación.** scikit-learn lo hace automático si el preprocesado vive en un `Pipeline`:

```python
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler, TargetEncoder

X = df.drop(columns="target")
y = df["target"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=0)

preprocesado = ColumnTransformer([
    ("num", make_pipeline(SimpleImputer(strategy="mean"), StandardScaler()), num_cols),
    ("cat", TargetEncoder(target_type="binary"), ["ciudad"]),
])
modelo = Pipeline([
    ("prep", preprocesado),
    ("clf", HistGradientBoostingClassifier(random_state=0)),
])

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
scores = cross_val_score(modelo, X_train, y_train, cv=cv, scoring="roc_auc")
print(f"AUC validación: {scores.mean():.3f} ± {scores.std():.3f}")

modelo.fit(X_train, y_train)
print("AUC test:", round(roc_auc_score(y_test, modelo.predict_proba(X_test)[:, 1]), 3))
```

Qué cambia con esto:

- `cross_val_score` ajusta el **pipeline completo** en cada pliegue de entrenamiento y lo aplica al de validación: el imputador, el escalador y el codificador nunca ven las filas que evalúan.
- `TargetEncoder` de scikit-learn (≥ 1.3) hace internamente una validación cruzada en `fit_transform`: cada fila de entrenamiento se codifica con la tasa calculada **sin ella**, justo lo que tu `transform("mean")` no hacía. Además suaviza las categorías pequeñas hacia la media global.
- `stratify=y` mantiene la proporción de positivos en train y test; sin él, con clases desbalanceadas el AUC de test oscila según qué le tocó a cada lado.
- `HistGradientBoostingClassifier` acepta `NaN` de forma nativa, así que la imputación podría sobrar; la dejo porque el escalador no acepta nulos y porque deja la decisión escrita.
- El test se separa **primero**, antes de cualquier `fit`. Es la única línea de tu script que estaba bien, pero llegaba tarde.

Cómo saber que cerraste las fugas: la AUC de validación cruzada y la del test apartado deben parecerse entre sí, y ambas deben acercarse al 0.71 de producción (o la diferencia explicarse por un cambio de distribución, que es otro problema). Si la validación sigue muy por encima, queda una fuga: busca columnas calculadas con información posterior al momento de predecir (fechas de cierre, estados finales, contadores acumulados).""",
            },
        ]
    },
    # 26) scikit-learn: GridSearchCV sobre Pipeline y validación por grupos (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un pipeline de sklearn con `StandardScaler` y `LogisticRegression` y quiero probar varios valores de `C` con GridSearchCV, pero me dice `ValueError: Invalid parameter 'C' for estimator Pipeline(...)`. ¿Cómo se pasan los parámetros a un paso del pipeline?",
            },
            {
                "role": "assistant",
                "content": """Con el nombre del paso, dos guiones bajos y el parámetro: `nombre_paso__parametro`. `GridSearchCV` recibe el pipeline, así que los parámetros se dirigen a él, y esa sintaxis le dice a qué componente interno pertenece cada uno.

```python
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(max_iter=1000)),
])

grid = {
    "clf__C": [0.01, 0.1, 1, 10, 100],
    "clf__class_weight": [None, "balanced"],
}
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
search = GridSearchCV(pipe, grid, cv=cv, scoring="f1", n_jobs=-1, refit=True)
search.fit(X_train, y_train)

print(search.best_params_, round(search.best_score_, 3))
modelo = search.best_estimator_          # pipeline completo, ya reentrenado con todo X_train
```

Los nombres válidos los lista `pipe.get_params().keys()`: ahí verás `clf__C`, `scaler__with_mean`, etc. Si usaste `make_pipeline`, los nombres son la clase en minúsculas: `logisticregression__C`.

Decisiones que suelen pasarse por alto:

- **`StratifiedKFold` con `shuffle=True`.** Es el `cv` por defecto para clasificación, pero sin barajar: si tus datos vienen ordenados por clase o por fecha, los pliegues no son representativos. `random_state` fijo para que la búsqueda sea reproducible.
- **`scoring` explícito.** Por defecto usa `accuracy`, que con clases desbalanceadas elige el peor modelo con mucha confianza. `"f1"`, `"roc_auc"` o `"average_precision"` según lo que te importe.
- **`refit=True`** (el valor por defecto) reentrena el mejor pipeline sobre todo `X_train` al terminar. `best_estimator_` es ese; no vuelvas a hacer `fit`.
- **`n_jobs=-1`** paraleliza los ajustes. Con `cv=5` y 10 combinaciones son 50; con un modelo lento, `RandomizedSearchCV` o `HalvingGridSearchCV` recortan.
- El `scaler` también se puede buscar: `"scaler": [StandardScaler(), MinMaxScaler(), "passthrough"]` prueba escaladores distintos o ninguno.

Para mirar algo más que el ganador: `pd.DataFrame(search.cv_results_)[["params", "mean_test_score", "std_test_score"]].sort_values("mean_test_score")`. Si el mejor y el segundo están dentro de una desviación estándar, la diferencia es ruido, y conviene elegir el más simple (la `C` más pequeña).""",
            },
            {
                "role": "user",
                "content": "Ok. Mis datos son de pacientes y cada paciente tiene varias filas (una por visita). Me da la sensación de que el F1 de validación es demasiado bueno.",
            },
            {
                "role": "assistant",
                "content": """Tu sensación es correcta: con varias filas por paciente, `StratifiedKFold` reparte las visitas de un mismo paciente entre entrenamiento y validación. El modelo aprende las características de ese paciente en unas visitas y las «reconoce» en las otras. Es una fuga, y el F1 que ves es el de identificar pacientes conocidos, no el de generalizar a pacientes nuevos, que es lo que ocurrirá en producción.

El arreglo es validar **por grupo**: todas las filas de un paciente van al mismo pliegue.

```python
from sklearn.model_selection import StratifiedGroupKFold

cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
search = GridSearchCV(pipe, grid, cv=cv, scoring="f1", n_jobs=-1)
search.fit(X_train, y_train, groups=X_train["paciente_id"])
```

- `groups` se pasa en el **`fit`**, no al constructor del `cv`; `GridSearchCV` lo reenvía a cada `split`.
- `StratifiedGroupKFold` intenta además equilibrar la proporción de clases entre pliegues; `GroupKFold` solo garantiza la separación por grupo. Con pocos positivos, el estratificado evita pliegues sin ningún caso positivo.
- **`paciente_id` no debe ser una variable del modelo.** Si está en `X_train`, quítala con el `ColumnTransformer` (`remainder="drop"`) o antes del `fit`; si no, el modelo la memoriza y tienes la misma fuga por otra vía.
- El split inicial train/test tiene que respetar lo mismo, y `train_test_split` no sabe de grupos. Usa `GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=0).split(X, y, groups)` para obtener los índices.

Y si las visitas tienen fecha y el modelo va a predecir visitas **futuras**, la pregunta cambia: el pliegue de validación debe ser posterior en el tiempo al de entrenamiento (`TimeSeriesSplit`), porque la fuga ya no es solo por paciente sino por calendario (la tasa de positivos de 2025 no debe informar predicciones de 2024).

Comprobación de que no hay solapamiento, que vale como test de la validación misma:

```python
for tr, va in cv.split(X_train, y_train, groups=X_train["paciente_id"]):
    assert not set(X_train.iloc[tr]["paciente_id"]) & set(X_train.iloc[va]["paciente_id"])
```

Espera un F1 más bajo. Ese es el número de verdad.""",
            },
        ]
    },
    # 27) scikit-learn: métricas con clases desbalanceadas y umbral (inglés, system variante)
    {
        "messages": [
            {"role": "system", "content": "You are a senior ML engineer. Answer in English, concisely, with runnable code."},
            {
                "role": "user",
                "content": "Our fraud model reports 99.3% accuracy on the test set, but the fraud team says it flags almost nothing. Fraud is about 0.6% of transactions. What metric should we be looking at, and how do we fix the model?",
            },
            {
                "role": "assistant",
                "content": """99.3 % accuracy is what you get by predicting "not fraud" for every transaction: 100 − 0.6 = 99.4 %. Your model is at or below the trivial baseline. Accuracy is the wrong lens here, and the fix is as much about the decision threshold as about the model.

**1. Look at the confusion matrix and the per-class report.**

```python
from sklearn.metrics import classification_report, confusion_matrix

y_pred = clf.predict(X_test)
print(confusion_matrix(y_test, y_pred))
print(classification_report(y_test, y_pred, target_names=["legit", "fraud"], digits=3))
```

For the fraud class you care about **recall** (what fraction of real fraud we catch) and **precision** (what fraction of our alerts are real). The fraud team's complaint is low recall. The number to report is precision at the recall the business can operate at, or F1 if you need a single figure.

**2. Compare models with a threshold-free metric: PR-AUC, not ROC-AUC.** With 0.6 % positives, ROC-AUC can look great (0.95) while the model is useless, because the false-positive *rate* stays tiny even with thousands of false alerts. Average precision (area under the precision-recall curve) is sensitive to exactly what matters here:

```python
from sklearn.metrics import average_precision_score, roc_auc_score

proba = clf.predict_proba(X_test)[:, 1]
print("ROC-AUC", roc_auc_score(y_test, proba))
print("PR-AUC ", average_precision_score(y_test, proba))   # baseline is the positive rate: 0.006
```

**3. Move the threshold.** `predict()` cuts at 0.5, which is arbitrary. Your model may already rank fraud well; it just never crosses 0.5. Pick the threshold from the precision-recall curve according to the cost of each error:

```python
import numpy as np
from sklearn.metrics import precision_recall_curve

precision, recall, thresholds = precision_recall_curve(y_val, proba_val)
target_recall = 0.80                                        # what the fraud team needs
idx = np.where(recall[:-1] >= target_recall)[0][-1]         # highest threshold that still reaches 80 % recall
threshold = thresholds[idx]
print(f"threshold={threshold:.3f} precision={precision[idx]:.3f} recall={recall[idx]:.3f}")
y_pred = (proba >= threshold).astype(int)
```

Tune this on a validation split, not on the test set, or you are grading yourself on the final exam. scikit-learn ≥ 1.5 does it inside cross-validation:

```python
from sklearn.model_selection import TunedThresholdClassifierCV

tuned = TunedThresholdClassifierCV(clf, scoring="f1", cv=5).fit(X_train, y_train)
print(tuned.best_threshold_)
```

**4. Then improve the model itself.**

- `class_weight="balanced"` (logistic regression, trees, SVM) or `scale_pos_weight` (XGBoost/LightGBM) makes each fraud example weigh as much as ~165 legit ones in the loss. It usually lifts recall at the same threshold.
- Resampling (SMOTE, undersampling) only inside the training folds, never before the split; `imbalanced-learn` has a `Pipeline` that does this correctly.
- Features that encode *behavior over time* (amount vs. the customer's usual amount, transactions in the last hour) typically matter more than any resampling trick.

**5. Report what the business understands.** At the chosen threshold: fraud caught per 1,000 transactions, alerts per 1,000, and the cost of each. "80 % recall at 30 % precision" means one alert in three is real; whether that is acceptable is their call, not the model's.

Sanity check before shipping: PR-AUC must beat 0.006 by a wide margin, and recall at the operating threshold on a held-out, *later-in-time* test set must match what you saw in validation. If it collapses on later data, fraud patterns drifted and you need to retrain on recent transactions.""",
            },
        ]
    },
    # 28) transformers: inferencia por lotes en GPU (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que clasificar el sentimiento de unas 50 mil reseñas en español. Probé el `pipeline` de transformers pasándole la lista entera y lleva 40 minutos y no va ni por la mitad, en una GPU T4. ¿Qué estoy haciendo mal?",
            },
            {
                "role": "assistant",
                "content": """Casi seguro tres cosas: el `pipeline` está en CPU, procesa las reseñas de una en una y las largas se tokenizan sin límite. Con lotes, GPU y `float16`, 50 mil reseñas cortas en una T4 son un par de minutos.

Versión manual, que es la que conviene cuando el volumen importa porque controlas cada decisión:

```python
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODELO = "pysentimiento/robertuito-sentiment-analysis"   # sustituye por el tuyo; este devuelve POS/NEG/NEU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODELO)
model = AutoModelForSequenceClassification.from_pretrained(
    MODELO,
    dtype=torch.float16 if device.type == "cuda" else torch.float32,   # transformers ≥ 4.56; antes se llamaba torch_dtype
).to(device).eval()


def clasificar(textos: list[str], batch_size: int = 64, max_length: int = 256) -> list[str]:
    # Ordenar por longitud: cada lote tiene textos parecidos y se rellena menos
    orden = sorted(range(len(textos)), key=lambda i: len(textos[i]))
    etiquetas: list[str | None] = [None] * len(textos)
    with torch.inference_mode():
        for inicio in range(0, len(orden), batch_size):
            idx = orden[inicio : inicio + batch_size]
            lote = tokenizer(
                [textos[i] for i in idx],
                padding=True,              # rellena hasta el más largo del lote, no hasta max_length
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            ).to(device)
            logits = model(**lote).logits
            for i, pred in zip(idx, logits.argmax(dim=-1).tolist()):
                etiquetas[i] = model.config.id2label[pred]
    return etiquetas
```

Por qué cada pieza:

- **Lotes.** Una T4 procesa 64 textos en casi el mismo tiempo que uno. Sube `batch_size` hasta que la memoria se acerque al límite (en `float16` y 256 tokens, 128 suele caber).
- **`padding=True` y no `padding="max_length"`.** El relleno dinámico ajusta cada lote a su texto más largo. Ordenar por longitud hace que ese «más largo» se parezca al resto; sin ordenar, una reseña de 250 tokens en un lote de reseñas de 20 multiplica el cómputo por diez.
- **`truncation=True, max_length=256`.** Sin ello, una reseña de 1.000 tokens falla (`IndexError: index out of range in self`, porque el modelo tiene 512 posiciones) o, con `max_length=512`, cuesta el doble. Para sentimiento, los primeros 256 tokens bastan; mídelo en una muestra si no te fías.
- **`torch.inference_mode()`** evita construir el grafo de autograd: menos memoria y más velocidad. `model.eval()` desactiva dropout.
- **`float16`** en GPU: la mitad de memoria y los *tensor cores* de la T4 trabajan. Para clasificación la pérdida de precisión es irrelevante. `bfloat16` no está soportado en T4 (arquitectura Turing); por eso `float16`.
- **`id2label`** sale de la configuración del modelo; no inventes el mapeo de índices a nombres.

Si prefieres quedarte con `pipeline`, la mayor parte de la ganancia también se consigue con los mismos argumentos: `pipeline("text-classification", model=MODELO, device=0, dtype=torch.float16)` y llamarlo con `batch_size=64, truncation=True, max_length=256`. Lo que no hace por ti es ordenar por longitud.

Comprobación de rendimiento y corrección antes de lanzar las 50 mil: cronometra 1.000 reseñas con `time.perf_counter()`, y compara las etiquetas de 50 de ellas con las que da el `pipeline` sin optimizar. Deben coincidir salvo algún empate numérico por el `float16`.""",
            },
        ]
    },
    # 29) PEFT: LoRA/QLoRA en una GPU de 24 GB (system variante, multiturno, avanzado)
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero de ML senior. Respondes en español, con código completo y los trade-offs de cada decisión."},
            {
                "role": "user",
                "content": "Quiero hacer fine-tuning de un modelo tipo Llama de 8B con mis datos de soporte (unas 20 mil conversaciones) en una sola GPU de 24 GB. Me dicen que con LoRA se puede. ¿Cómo se monta eso y qué estoy perdiendo respecto a un fine-tuning completo?",
            },
            {
                "role": "assistant",
                "content": """Se puede, y LoRA es la única forma de hacerlo en 24 GB. Las cuentas primero, porque explican todas las decisiones.

**Por qué el fine-tuning completo no cabe.** Entrenar un parámetro con AdamW en precisión mixta cuesta unos 16 bytes: 2 del peso en bf16, 2 del gradiente, 8 de los dos momentos de Adam en fp32 y 4 de la copia maestra en fp32. 8B × 16 ≈ **128 GB** antes de contar activaciones. Con LoRA congelas el modelo base (8B × 2 bytes = 16 GB en bf16) y entrenas matrices de rango bajo que suman decenas de millones de parámetros, no miles de millones. Y con QLoRA el modelo base se guarda cuantizado a 4 bits (unos 5 GB), que es lo que te deja margen para activaciones y secuencias largas en 24 GB.

**Montaje con transformers + PEFT + TRL:**

```python
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

BASE = "meta-llama/Llama-3.1-8B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(BASE)
tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    BASE,
    quantization_config=BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    ),
    device_map="auto",
)
model = prepare_model_for_kbit_training(model)   # congela el base, pasa las norms a fp32, activa gradient checkpointing

lora = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora)
model.print_trainable_parameters()   # trainable params: ~42M || all params: ~8.07B || trainable%: 0.52

dataset = load_dataset("json", data_files="soporte.jsonl", split="train")   # filas {"messages": [...]}

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        output_dir="salida/lora-soporte",
        num_train_epochs=2,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=8,          # lote efectivo 32
        learning_rate=2e-4,                     # LoRA tolera lr 10x mayores que el fine-tuning completo
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        logging_steps=20,
        save_strategy="epoch",
        max_length=2048,
    ),
)
trainer.train()
trainer.save_model("salida/lora-soporte/final")   # guarda SOLO el adaptador (unos 170 MB), no el modelo base
```

El dataset en formato `{"messages": [{"role": ..., "content": ...}]}` lo reconoce `SFTTrainer` y aplica la plantilla de chat del tokenizador; no formatees el texto a mano.

**Para usarlo después:**

```python
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, device_map="auto")
model = PeftModel.from_pretrained(base, "salida/lora-soporte/final")
model = model.merge_and_unload()     # fusiona B·A en los pesos: inferencia sin sobrecoste; opcional
```

**Qué pierdes respecto al fine-tuning completo:**

- **Capacidad.** LoRA restringe el cambio de cada matriz a rango `r`. Para adaptar estilo, formato y conocimiento de dominio moderado (tu caso: soporte, 20 mil conversaciones) sobra; para enseñar un idioma nuevo o cambiar capacidades profundas, se queda corto.
- **Algo de calidad por la cuantización.** El base a 4 bits cuesta una fracción de punto en benchmarks. Si cabes con el base en bf16 (con 8B y secuencias de 2048 en 24 GB no cabes; con un 3B sí), quita el `quantization_config` y mantén el resto.
- **Olvido catastrófico: menos.** Esto es una ventaja. Al congelar el base, el modelo conserva lo que sabía; un fine-tuning completo con 20 mil ejemplos lo degrada con facilidad.

**Lo que decidí y por qué:** `target_modules` con atención **y** MLP, porque el paper de QLoRA mostró que adaptar solo la atención deja calidad sobre la mesa; `r=16` como punto de partida (ver la siguiente pregunta antes de subirlo); `learning_rate=2e-4`, el rango habitual para LoRA y demasiado alto para pesos completos; 2 épocas, porque con datos de conversación la tercera suele empezar a memorizar.

Verificación mínima antes de las 2 épocas completas: `max_steps=50` en `SFTConfig` y comprobar que la pérdida baja (de ~2 a ~1.2 es lo típico) y que la memoria en `nvidia-smi` se estabiliza por debajo de 24 GB. Después, genera con 10 conversaciones apartadas y lee las respuestas: la pérdida no te dice si el tono es el correcto.""",
            },
            {
                "role": "user",
                "content": "¿Y cómo elijo r y alpha? Veo de todo, desde r=8 con alpha=16 hasta r=64 con alpha=16 o r=256.",
            },
            {
                "role": "assistant",
                "content": """Piensa en los dos como una sola cosa: `alpha / r` es el factor por el que se multiplica la actualización `B·A` antes de sumarla al peso. `r` decide **cuánta capacidad** tiene el adaptador; `alpha` decide **cuánto pesa** respecto al modelo base.

**`r` (rango).** Es el número de direcciones independientes en las que el adaptador puede modificar cada matriz. Guía práctica:

| Tarea | `r` razonable |
|---|---|
| Formato, tono, estilo de respuesta | 8-16 |
| Dominio nuevo con vocabulario propio (soporte, legal, médico) | 16-64 |
| Comportamiento muy distinto al base, datos abundantes (>100k ejemplos) | 64-256 |

Subir `r` cuesta memoria y tiempo de forma lineal, pero la mejora se satura pronto: el paper original de LoRA ya mostraba que `r=8` y `r=64` daban resultados casi iguales en sus tareas. El síntoma de un `r` demasiado bajo es que la pérdida de entrenamiento se estanca alta aunque subas el learning rate; el de un `r` demasiado alto con pocos datos, sobreajuste (pérdida de validación que sube desde la segunda época).

**`alpha`.** Con la LoRA clásica, la escala es `alpha / r`. Dos convenciones vivas:

- **`alpha = 2r`** (escala 2): la más común hoy; `r=16, alpha=32` es lo que puse antes.
- **`alpha = r`** (escala 1): más conservadora; funciona bien con un lr algo mayor.

Lo que no conviene es mover `r` y dejar `alpha` fija, porque cambias la escala sin darte cuenta: `r=64, alpha=16` escala a 0.25 y el adaptador apenas influye hasta que el optimizador lo compensa. Si vas a explorar varios `r`, activa **rsLoRA** (`use_rslora=True` en `LoraConfig`): cambia la escala a `alpha / sqrt(r)`, que mantiene la magnitud de la actualización estable al variar el rango, y con ella sí puedes subir `r` sin tocar `alpha` ni el lr.

**Cómo elegirlos sin fe:** fija `alpha = 2r`, entrena 300 pasos con `r=8`, `r=16` y `r=64` sobre un subconjunto de 2.000 conversaciones, y compara la pérdida de validación y, sobre todo, 10 generaciones leídas. Si `r=16` y `r=64` no se distinguen, quédate con 16: menos memoria, adaptador más pequeño y menos riesgo de sobreajuste con tus 20 mil ejemplos. Los `r=256` que ves por ahí suelen ser intentos de aproximar un fine-tuning completo; en tu caso sería gastar GPU en capacidad que no vas a usar.""",
            },
        ]
    },
    # 30) pandas: de notebook a módulo con tests (system variante, intermedio)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Responde en español, con el cambio mínimo y sin rodeos."},
            {
                "role": "user",
                "content": "Tenemos un notebook de 300 celdas con pandas que genera el informe mensual. Solo funciona si lo ejecutas de arriba abajo sin tocar nada, y la semana pasada un compañero lo corrió con una celda vieja y mandamos cifras mal. ¿Cómo lo convierto en algo serio sin reescribirlo entero?",
            },
            {
                "role": "assistant",
                "content": """El problema no son las 300 celdas sino el **estado oculto**: cada celda depende de variables globales que otra celda modificó, y el kernel permite ejecutarlas en cualquier orden. La solución no es reescribir sino **mover la lógica a un módulo con funciones puras** y dejar el notebook como cliente de ese módulo. Se hace por fases y cada fase deja el informe funcionando.

**Fase 1: encontrar los límites.** Un notebook de informe casi siempre tiene cuatro etapas: cargar, limpiar, calcular, presentar. Marca cada celda con una de ellas. Las que no encajan (`df.head()`, gráficos exploratorios, pruebas) se borran o van al final.

**Fase 2: extraer cada etapa a una función que recibe y devuelve DataFrames.** Nada de globales: lo que una función necesita entra por parámetros; lo que produce sale por `return`.

```python
# informe/pipeline.py
from pathlib import Path

import pandas as pd


def cargar_ventas(ruta: Path, mes: str) -> pd.DataFrame:
    ventas = pd.read_parquet(ruta, filters=[("mes", "==", mes)])
    esperadas = {"pedido_id", "cliente_id", "importe", "fecha", "mes"}
    faltan = esperadas - set(ventas.columns)
    if faltan:
        raise ValueError(f"faltan columnas en {ruta}: {sorted(faltan)}")
    return ventas


def limpiar(ventas: pd.DataFrame) -> pd.DataFrame:
    return (
        ventas.drop_duplicates("pedido_id")
        .loc[lambda d: d["importe"] > 0]
        .assign(fecha=lambda d: pd.to_datetime(d["fecha"], format="%Y-%m-%d"))
    )


def resumen_por_cliente(ventas: pd.DataFrame) -> pd.DataFrame:
    return ventas.groupby("cliente_id", as_index=False).agg(
        pedidos=("pedido_id", "nunique"),
        importe=("importe", "sum"),
        ultimo_pedido=("fecha", "max"),
    )


def generar_informe(ruta: Path, mes: str) -> pd.DataFrame:
    return resumen_por_cliente(limpiar(cargar_ventas(ruta, mes)))
```

Con esto el notebook queda en:

```python
from informe.pipeline import generar_informe

resumen = generar_informe(Path("datos/ventas.parquet"), mes="2025-09")
resumen.head()
```

y la ejecución desordenada ya no puede producir cifras mal, porque no hay celdas intermedias que mutar.

**Fase 3: un test por función, con datos pequeños escritos a mano.** Es lo que impide que lo de la semana pasada se repita, y además documenta qué significa «limpio»:

```python
# tests/test_pipeline.py
import pandas as pd
from pandas.testing import assert_frame_equal

from informe.pipeline import limpiar, resumen_por_cliente


def test_limpiar_quita_duplicados_e_importes_no_positivos():
    bruto = pd.DataFrame({
        "pedido_id": [1, 1, 2, 3],
        "cliente_id": ["a", "a", "a", "b"],
        "importe": [10.0, 10.0, -5.0, 20.0],
        "fecha": ["2025-09-01"] * 4,
    })
    assert limpiar(bruto)["pedido_id"].tolist() == [1, 3]


def test_resumen_por_cliente_agrega():
    ventas = pd.DataFrame({
        "pedido_id": [1, 2, 3],
        "cliente_id": ["a", "a", "b"],
        "importe": [10.0, 5.0, 20.0],
        "fecha": pd.to_datetime(["2025-09-01", "2025-09-03", "2025-09-02"]),
    })
    esperado = pd.DataFrame({
        "cliente_id": ["a", "b"],
        "pedidos": [2, 1],
        "importe": [15.0, 20.0],
        "ultimo_pedido": pd.to_datetime(["2025-09-03", "2025-09-02"]),
    })
    assert_frame_equal(resumen_por_cliente(ventas), esperado)
```

`assert_frame_equal` compara valores, dtypes e índice, y su mensaje dice exactamente qué columna y qué fila difieren.

**Fase 4: ejecución sin notebook.** Un punto de entrada que acepta el mes como argumento:

```python
# informe/__main__.py
import argparse
from pathlib import Path

from informe.pipeline import generar_informe

parser = argparse.ArgumentParser()
parser.add_argument("--mes", required=True)
parser.add_argument("--datos", type=Path, default=Path("datos/ventas.parquet"))
parser.add_argument("--salida", type=Path, default=Path("informes"))
args = parser.parse_args()

resumen = generar_informe(args.datos, args.mes)
args.salida.mkdir(exist_ok=True)
resumen.to_csv(args.salida / f"resumen_{args.mes}.csv", index=False)
```

`python -m informe --mes 2025-09` desde cron o desde CI, con los tests pasando antes.

Dos reglas para que no vuelva a degradarse: en el notebook, `%load_ext autoreload` y `%autoreload 2` para que recoja los cambios del módulo sin reiniciar el kernel; y «si una celda se ejecuta dos veces y da distinto resultado, es un bug», que es la definición operativa de estado oculto. Lo que quede en el notebook es exploración; nada de lo que se entrega sale de ahí.""",
            },
        ]
    },
]
