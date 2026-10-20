"""Filas de referencia (listón de calidad). NO forma parte del entrenamiento.

Cada fuente real define `ROWS = [...]` con dicts exactamente como estos. Se usan
cadenas con triple comilla para no tener que escapar saltos de línea ni comillas.
Si el contenido necesita barras invertidas (regex, "\\n" literal en código) usa
r\"\"\"...\"\"\" o escápalas. Nunca uses \"\"\" dentro del contenido; usa ''' si hace falta.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Español: respuesta directa y estructurada.
    {
        "messages": [
            {"role": "user", "content": "¿Cuándo se usa «sino» y cuándo «si no»? Siempre los confundo."},
            {
                "role": "assistant",
                "content": """Son dos cosas distintas y hay una prueba rápida para cada una.

**«Sino»** (junto) es una conjunción adversativa: corrige o contrapone lo que se acaba de negar. Prueba: puedes sustituirlo por «más bien» o «al contrario».

- No vine a discutir, **sino** a escuchar. → No vine a discutir, más bien a escuchar. ✓
- No es rojo, **sino** granate.

**«Si no»** (separado) es la condicional «si» seguida de la negación «no». Prueba: puedes meter algo entre las dos palabras («si tú no», «si ahora no») y la frase sigue teniendo sentido.

- **Si no** llegas a tiempo, empezamos sin ti. → Si tú no llegas a tiempo… ✓
- Avísame **si no** puedes venir.

Dos pistas más:

1. Detrás de «sino» casi nunca hay un verbo conjugado directamente (salvo «sino que» + verbo: «no llovió, sino que granizó»).
2. Si la frase anterior no contiene una negación, casi seguro que es «si no».

Tu frase de ejemplo resuelta: «No quiero que lo hagas por obligación, **sino** por gusto» (contrapone) frente a «**Si no** lo haces por gusto, mejor no lo hagas» (condición).""",
            },
        ]
    },
    # 2) Código: respuesta directa, código completo y verificable.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "En Python necesito una función que agrupe una lista de diccionarios por una clave y devuelva un dict de listas. ¿Cómo la harías bien, con tipos?"},
            {
                "role": "assistant",
                "content": """Usa `defaultdict(list)` y acepta la clave como un *callable* en vez de un nombre de campo: así sirve tanto para `d["ciudad"]` como para claves derivadas (`len(d["nombre"])`) sin cambiar la firma.

```python
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable
from typing import TypeVar

T = TypeVar("T")
K = TypeVar("K", bound=Hashable)


def agrupar_por(elementos: Iterable[T], clave: Callable[[T], K]) -> dict[K, list[T]]:
    \"\"\"Agrupa `elementos` por el valor que devuelve `clave`, conservando el orden de llegada.\"\"\"
    grupos: defaultdict[K, list[T]] = defaultdict(list)
    for elemento in elementos:
        grupos[clave(elemento)].append(elemento)
    return dict(grupos)
```

Uso:

```python
personas = [
    {"nombre": "Ana", "ciudad": "Lima"},
    {"nombre": "Luis", "ciudad": "Quito"},
    {"nombre": "Eva", "ciudad": "Lima"},
]
por_ciudad = agrupar_por(personas, lambda p: p["ciudad"])
# {'Lima': [{'nombre': 'Ana', ...}, {'nombre': 'Eva', ...}], 'Quito': [{'nombre': 'Luis', ...}]}
```

Tres decisiones y por qué:

- **Devuelvo `dict`, no `defaultdict`.** Un `defaultdict` que escapa de la función crea claves vacías al consultarlas (`grupos["Bogotá"]` devolvería `[]` y la insertaría), lo que esconde errores aguas abajo.
- **`Iterable` en la entrada.** Acepta generadores y no obliga a materializar una lista; el único recorrido es el del bucle.
- **Orden estable.** Los dicts conservan el orden de inserción desde Python 3.7, así que el primer grupo que aparece es el primero del resultado, igual que `itertools.groupby`, pero sin exigir que la entrada venga ordenada (ese es el error clásico con `groupby`).

Si el campo puede faltar en algún dict, decide explícitamente: `lambda p: p.get("ciudad", "desconocida")`. Un `KeyError` silencioso dentro de la lambda es mejor que no, pero es más claro nombrar el caso.

Prueba mínima:

```python
def test_agrupar_por_conserva_orden_y_separa_grupos():
    datos = [3, 1, 4, 1, 5, 9, 2, 6]
    assert agrupar_por(datos, lambda n: n % 2) == {1: [3, 1, 1, 5, 9], 0: [4, 2, 6]}
```""",
            },
        ]
    },
    # 3) Debugging: el método (significado del error → diagnóstico → causas → orden) va en la respuesta.
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi endpoint en FastAPI devuelve 500 de vez en cuando bajo carga, pero en local nunca falla. El log dice:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00
```

Uso `create_engine` con los valores por defecto y una dependencia `get_db` que hace `yield`. ¿Qué pasa?""",
            },
            {
                "role": "assistant",
                "content": """El error no es de la base de datos: es el **pool de conexiones agotado**. Con los valores por defecto tienes 5 conexiones + 10 de *overflow* = **15 por proceso**. Una petición pidió la 16.ª, esperó 30 s y falló. En local no reproduce porque nunca tienes 15 peticiones concurrentes.

Hay cuatro causas habituales. Antes de tocar nada, mide cuál es la tuya.

**1. Diagnóstico en 5 minutos.** Expón el estado del pool y míralo bajo carga:

```python
@app.get("/debug/pool")
def pool_status():
    pool = engine.pool
    return {"checked_out": pool.checkedout(), "size": pool.size(), "overflow": pool.overflow()}
```

- Si `checked_out` **sube y nunca baja** aunque pare el tráfico → fuga de sesiones (causa A).
- Si sube con el tráfico y baja al parar → simplemente te quedas corto o retienes conexiones demasiado tiempo (causas B y C).

**2. Causa A: la dependencia no cierra en caso de excepción.** Esta es la forma correcta; el `finally` es lo que garantiza la devolución al pool:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Y busca en el código cualquier `SessionLocal()` fuera de esta dependencia (tareas en segundo plano, scripts, *middlewares*): cada uno necesita su propio `try/finally` o un `with SessionLocal() as db:`.

**3. Causa B: concurrencia mayor que el pool.** Si corres `uvicorn --workers 4`, cada worker tiene su propio pool de 15; la base de datos ve hasta 60. Ajusta el pool al tráfico real y al límite del servidor de BD:

```python
engine = create_engine(
    url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,      # falla rápido en vez de colgar 30 s
    pool_pre_ping=True,   # descarta conexiones muertas tras reinicios de la BD
)
```

`pool_timeout` bajo no arregla nada, pero convierte una espera de 30 s en un error inmediato y visible, que es lo que quieres en producción.

**4. Causa C: retienes la conexión mientras haces otra cosa.** Esto es lo más frecuente en endpoints "lentos a veces":

```python
# Mal: la conexión queda ocupada durante toda la llamada HTTP externa
def crear_pedido(db: Session = Depends(get_db)):
    pedido = db.get(Pedido, 1)
    resp = httpx.post("https://pagos.example/cobrar", json=...)  # 2-3 s
    pedido.estado = resp.json()["estado"]
    db.commit()
```

Separa la I/O externa de la transacción: lee, suelta, llama fuera, y vuelve a abrir para escribir. Y si la ruta es `async def` con una sesión síncrona, cada consulta bloquea el *event loop*; usa rutas `def` (FastAPI las ejecuta en un hilo) o `AsyncSession`.

**Orden recomendado:** instrumenta el pool (1) → corrige la dependencia y cualquier sesión manual (2) → revisa las rutas que hacen I/O con la sesión abierta (4) → solo entonces sube `pool_size` (3). Subir el pool primero esconde una fuga durante unos días y luego vuelve a fallar.""",
            },
        ]
    },
    # 4) Multiturno: el asistente mantiene el contexto y no repite lo ya dicho.
    {
        "messages": [
            {"role": "user", "content": "¿Qué diferencia hay entre `let` y `const` en JavaScript?"},
            {"role": "assistant", "content": """`const` crea un enlace que no se puede reasignar; `let` sí permite reasignar. Las dos tienen alcance de bloque y zona temporal muerta (no puedes usarlas antes de declararlas).

```js
const a = 1;
a = 2;        // TypeError: Assignment to constant variable.

let b = 1;
b = 2;        // bien
```

Lo que `const` NO hace es congelar el valor: un objeto o array declarado con `const` sigue siendo mutable.

```js
const lista = [1, 2];
lista.push(3);   // bien: mutas el array, no reasignas la variable
lista = [];      // TypeError
```

Regla práctica: `const` por defecto; `let` solo cuando de verdad vas a reasignar (contadores, acumuladores). Así cada `let` que ves en el código te avisa de que esa variable cambia."""},
            {"role": "user", "content": "Entonces, ¿por qué veo código que hace `const obj = {}` y luego lo modifica en diez sitios? ¿No sería mejor `let`?"},
            {
                "role": "assistant",
                "content": """No: `let` sería peor, porque mentiría. `let` le dice al lector «esta variable se va a reasignar», y en ese código nunca se reasigna; solo se **muta** el objeto al que apunta. Son dos cosas independientes:

| | Reasignar el enlace (`obj = otro`) | Mutar el valor (`obj.x = 1`) |
|---|---|---|
| `let` | permitido | permitido |
| `const` | prohibido | permitido |
| `const` + `Object.freeze` | prohibido | prohibido (silenciosamente, o `TypeError` en modo estricto) |

Lo que te incomoda es legítimo, pero es otro problema: **mutar un objeto en diez sitios** dificulta saber en qué estado está en cada momento. La solución no es cambiar la palabra clave, sino una de estas dos:

1. **Construirlo de una vez** y no tocarlo después:

```js
const config = {
  puerto: leerPuerto(),
  host: process.env.HOST ?? "localhost",
  rutas: cargarRutas(),
};
```

2. Si de verdad evoluciona, **producir copias** en vez de mutar, para que cada paso sea explícito:

```js
const base = { puerto: 3000 };
const conHost = { ...base, host: "0.0.0.0" };
```

Y si quieres que el motor te proteja de mutaciones accidentales, `Object.freeze(config)` (congela solo el primer nivel; para anidados necesitas congelar recursivamente o usar una librería como Immer).

Resumen: `const` es correcto ahí. Si la mutación dispersa te molesta, ataca la mutación, no el `const`.""",
            },
        ]
    },
]
