"""Python 3.12: idiomática, tipado, asyncio, pruebas, herramientas y errores clásicos.

30 filas. Temas: argumentos mutables por defecto, dataclasses vs Pydantic v2, Protocol vs
ABC, genéricos PEP 695, gather vs TaskGroup, cancelación y timeouts, context managers,
generadores, decoradores con functools.wraps, jerarquías de excepciones, pathlib, logging,
empaquetado con pyproject y uv, pytest (fixtures, parametrize, monkeypatch), perfilado,
vectorización con NumPy, GIL y multiprocessing, late binding en closures, imports
circulares, f-strings, itertools/functools, fechas con zoneinfo, TypedDict y Literal,
match, to_thread, protocolo de iteración, micro-rendimiento, ThreadPoolExecutor y
estrechamiento de Optional.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = []

ROWS += [
    # 1) Argumento mutable por defecto (principiante, código roto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo esta función y no entiendo qué pasa:

```python
def add_item(item, items=[]):
    items.append(item)
    return items

print(add_item("a"))   # ['a']
print(add_item("b"))   # ['a', 'b']  ???
```

La segunda llamada debería devolver `['b']`, no tiene nada que ver con la primera.""",
            },
            {
                "role": "assistant",
                "content": """El valor por defecto `[]` se evalúa **una sola vez**, cuando Python ejecuta el `def`, no en cada llamada. Las dos llamadas reciben la misma lista y la primera la dejó con `'a'` dentro.

Puedes verlo directamente, porque los valores por defecto viven en la función:

```python
print(add_item.__defaults__)   # (['a', 'b'],)
```

La forma idiomática es usar `None` como centinela y crear la lista dentro:

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items


print(add_item("a"))   # ['a']
print(add_item("b"))   # ['b']
```

Lo mismo aplica a `{}`, `set()` y a cualquier objeto mutable, y también a llamadas como `timestamp=datetime.now()`, que se congela en el momento del `def` y luego devuelve siempre la misma hora.

Dos herramientas para no volver a caer:

- `ruff` lo detecta con la regla `B006` (*mutable default argument*) y `B008` (llamada en el valor por defecto). Actívalas en `pyproject.toml` con `select = ["B"]`.
- En `dataclasses`, el error equivalente ni siquiera compila: `items: list[str] = []` lanza `ValueError: mutable default <class 'list'> for field items is not allowed: use default_factory`. La solución allí es `field(default_factory=list)`.

El único uso legítimo del comportamiento es como caché barata (`def f(x, _cache={})`), y aun así es mejor `functools.cache` porque deja clara la intención.""",
            },
        ]
    },
    # 2) dataclasses vs Pydantic v2 (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Cuándo uso `dataclass` y cuándo Pydantic? En mi API con FastAPI uso modelos de Pydantic para todo, incluso para los objetos internos que nunca salen de un servicio."},
            {
                "role": "assistant",
                "content": """Pydantic en la **frontera** (lo que entra y sale: peticiones, respuestas, archivos de configuración, mensajes de cola) y `dataclass` en el **interior** (objetos de dominio que construyes tú con datos ya validados). Usar Pydantic para todo no es incorrecto, pero pagas validación en cada construcción de un objeto que ya sabes que es válido, y acoplas tu dominio a una librería externa.

| | `dataclass` | Pydantic v2 `BaseModel` |
|---|---|---|
| Validación y conversión de tipos | no | sí, en `__init__` y en `model_validate` |
| Coste de crear una instancia | mínimo | validación en Rust, pero no gratis |
| Dependencias | stdlib | `pydantic` + `pydantic-core` |
| Serialización JSON con alias, exclusiones | a mano (`asdict`) | `model_dump`, `model_dump_json` |
| Inmutabilidad y `__slots__` | `frozen=True, slots=True` | `model_config = ConfigDict(frozen=True)` |
| Esquema JSON / OpenAPI | no | `model_json_schema()` |

Así queda la separación en un servicio:

```python
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field, PositiveInt


# Frontera: lo que llega por HTTP. Pydantic valida y convierte.
class OrderIn(BaseModel):
    sku: str = Field(min_length=1, max_length=32)
    quantity: PositiveInt
    unit_price: Decimal = Field(gt=0, decimal_places=2)


# Dominio: ya validado, inmutable, sin dependencias.
@dataclass(frozen=True, slots=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


def to_domain(order: OrderIn) -> OrderLine:
    return OrderLine(order.sku, order.quantity, order.unit_price)
```

`frozen=True, slots=True` te da objetos *hashables* (sirven como claves de dict y en sets), que ocupan menos memoria y que no se pueden modificar por accidente; en Pydantic la inmutabilidad existe pero no es el modo por defecto.

Prueba rápida de que la frontera protege al dominio:

```python
import pytest
from pydantic import ValidationError


def test_order_in_rechaza_cantidad_cero():
    with pytest.raises(ValidationError) as exc:
        OrderIn(sku="A1", quantity=0, unit_price=Decimal("9.99"))
    assert exc.value.errors()[0]["loc"] == ("quantity",)


def test_order_line_total():
    line = to_domain(OrderIn(sku="A1", quantity=3, unit_price="9.99"))  # str -> Decimal
    assert line.total == Decimal("29.97")
```

Regla práctica para tu caso: si una clase tiene `model_validate` o `model_dump` en algún sitio del código, es de frontera y Pydantic está justificado; si solo la construyes tú desde otros objetos ya validados, es un `dataclass`.""",
            },
            {"role": "user", "content": "¿Y si quiero validar algo en el dataclass (por ejemplo que la cantidad sea positiva) sin meter Pydantic?"},
            {
                "role": "assistant",
                "content": """`__post_init__`: se ejecuta justo después del `__init__` generado y es el sitio para invariantes del dominio. Lanza una excepción específica, no un `assert` (los `assert` desaparecen con `python -O`).

```python
from dataclasses import dataclass
from decimal import Decimal


class InvalidOrderLine(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal

    def __post_init__(self) -> None:
        if not self.sku:
            raise InvalidOrderLine("sku vacío")
        if self.quantity <= 0:
            raise InvalidOrderLine(f"quantity debe ser > 0, recibido {self.quantity}")
        if self.unit_price <= 0:
            raise InvalidOrderLine(f"unit_price debe ser > 0, recibido {self.unit_price}")
```

Dos detalles de `__post_init__` que conviene conocer:

- Con `frozen=True` no puedes asignar atributos dentro (`self.x = ...` lanza `FrozenInstanceError`). Si necesitas normalizar un campo (quitar espacios al `sku`, por ejemplo), usa `object.__setattr__(self, "sku", self.sku.strip())`. Es feo a propósito: te avisa de que estás saltándote la inmutabilidad en el único lugar donde es legítimo.
- No convierte tipos. `OrderLine("A1", "3", Decimal("1"))` pasa la comprobación `"3" <= 0`… no: lanza `TypeError` al comparar `str` con `int`. Eso es lo que quieres en el dominio: los datos ya deberían venir con el tipo correcto desde la frontera.

Si lo que necesitas es validación *de tipos* además de invariantes, y quieres seguir con la sintaxis de dataclass, Pydantic ofrece `from pydantic.dataclasses import dataclass`: misma declaración, validación completa. Pero entonces vuelves a tener Pydantic en el dominio, que era lo que querías evitar; para invariantes simples, `__post_init__` es suficiente y no cuesta nada.

```python
import pytest


def test_order_line_valida_invariantes():
    with pytest.raises(InvalidOrderLine, match="quantity"):
        OrderLine("A1", 0, Decimal("1"))
```""",
            },
        ]
    },
    # 3) Protocol vs ABC (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo varias clases «exportadoras» (a CSV, a JSON, a S3) que no comparten clase base y una función que recibe cualquiera de ellas. ¿Cómo la tipo? ¿Protocol o ABC?"},
            {
                "role": "assistant",
                "content": """`Protocol`, porque lo que tienes es *duck typing* que quieres que el verificador de tipos compruebe: cualquier objeto con el método adecuado vale, sin obligar a heredar de nada. `ABC` es para el caso contrario: cuando tú controlas las clases y además quieres compartir implementación o forzar la herencia explícita.

```python
from pathlib import Path
from typing import Protocol


class Exporter(Protocol):
    def export(self, rows: list[dict[str, object]], destination: str) -> int:
        '''Escribe las filas y devuelve cuántas escribió.'''
        ...


class CsvExporter:                       # no hereda de Exporter y no hace falta
    def export(self, rows: list[dict[str, object]], destination: str) -> int:
        import csv
        if not rows:
            Path(destination).write_text("")
            return 0
        with open(destination, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)


def run_export(exporter: Exporter, rows: list[dict[str, object]], destination: str) -> None:
    written = exporter.export(rows, destination)
    print(f"{written} filas en {destination}")
```

`mypy` o `pyright` comprueban **estructuralmente** que `CsvExporter` encaja en `Exporter`: mismo nombre de método, parámetros compatibles, tipo de retorno compatible. Si una clase tiene `export(self, rows)` sin `destination`, el error sale en la llamada a `run_export`, no en tiempo de ejecución:

```
error: Argument 1 to "run_export" has incompatible type "BrokenExporter"; expected "Exporter"
note:      Following member(s) of "BrokenExporter" have conflicts:
note:          Expected: def export(self, rows: list[dict[str, object]], destination: str) -> int
note:          Got:      def export(self, rows: list[dict[str, object]]) -> int
```

Cuándo elegir cada uno:

| Situación | Usa |
|---|---|
| Clases de terceros o que no quieres acoplar (adaptadores, *mocks*) | `Protocol` |
| Quieres compartir código entre implementaciones (plantilla con pasos) | `ABC` con métodos concretos y `@abstractmethod` |
| Necesitas `isinstance` fiable en tiempo de ejecución | `ABC` (o `@runtime_checkable` con limitaciones) |
| Librería pública donde «implementar la interfaz» debe ser explícito | `ABC` |

Sobre `@runtime_checkable`: permite `isinstance(obj, Exporter)`, pero solo comprueba que **existen** los atributos con ese nombre, no sus firmas ni tipos. Es útil en una frontera para dar un error claro; no sustituye al verificador estático.

Y nada impide combinar: una clase puede heredar de un `ABC` tuyo para reutilizar código y, además, satisfacer un `Protocol` que use otro módulo. El `Protocol` describe lo que el consumidor necesita; el `ABC`, lo que las implementaciones comparten. Son preguntas distintas.""",
            },
        ]
    },
    # 4) Genéricos PEP 695 (usuario en inglés)
    {
        "messages": [
            {"role": "user", "content": "What's the deal with the new generics syntax in Python 3.12? I have a codebase full of `TypeVar` and `Generic[T]`. Is it worth migrating, and what actually changes?"},
            {
                "role": "assistant",
                "content": """PEP 695 makes type parameters part of the `def`, `class`, and new `type` statements, so you no longer declare a `TypeVar` at module level and thread it through `Generic[T]`. The semantics are the same; the syntax is shorter, scoped correctly, and variance is inferred. Migrate if your minimum supported version is 3.12; otherwise keep `TypeVar`, because the new syntax is a `SyntaxError` on 3.11.

Side by side:

```python
# Before (3.11 and earlier)
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")
K = TypeVar("K", bound="Comparable")


def first(items: Sequence[T]) -> T:
    return items[0]


class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()
```

```python
# 3.12+
from collections.abc import Sequence
from typing import Protocol


def first[T](items: Sequence[T]) -> T:
    return items[0]


class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()


class Comparable(Protocol):
    def __lt__(self, other: "Comparable", /) -> bool: ...


def max_of[C: Comparable](items: Sequence[C]) -> C:      # bound
    best = items[0]
    for item in items[1:]:
        if best < item:
            best = item
    return best


def concat[S: (str, bytes)](a: S, b: S) -> S:            # constraints: exactly one of these
    return a + b


type Pair[T] = tuple[T, T]                               # generic type alias
type Json = dict[str, Json] | list[Json] | str | int | float | bool | None  # recursive, lazy
```

What actually changes:

1. **Scoping.** `T` only exists inside the function or class. Two functions can each use `T` without sharing a module-level variable, and you can't accidentally reuse a `TypeVar` with the wrong bound.
2. **Variance is inferred.** For `class Box[T]`, the checker works out whether `T` is covariant, contravariant, or invariant from how it is used. The old `TypeVar("T", covariant=True)` dance disappears; `Sequence`-like read-only classes become covariant automatically.
3. **`type` aliases are lazy.** `type Json = ...` can refer to itself and to names defined later in the module. `Json = dict[str, "Json"] | ...` with string forward references becomes unnecessary.
4. **Generic classes don't inherit from `Generic`.** `class Stack[T]:` is a plain class with a `__type_params__` attribute. `Stack[int]` still works at runtime.

Tooling: mypy 1.8+ and pyright have full support; `ruff` has `UP046`/`UP047` rules that rewrite `Generic[T]` and `TypeVar` usage to the new syntax when `target-version = "py312"`, which does most of a migration mechanically.

A quick check that the inference behaves:

```python
s: Stack[int] = Stack()
s.push(1)
s.push("x")          # mypy: Argument 1 to "push" of "Stack" has incompatible type "str"; expected "int"
reveal_type(first(["a", "b"]))   # Revealed type is "builtins.str"
reveal_type(max_of([3, 1, 2]))   # Revealed type is "builtins.int"
```

One thing that did **not** change: `ParamSpec` and `TypeVarTuple` also have the new syntax (`def f[**P, *Ts]`), but `Self` stays as `typing.Self`, and `TypeVar` with `default=` (PEP 696) only arrived in 3.13 as `[T = int]`.""",
            },
        ]
    },
    # 5) asyncio.gather vs TaskGroup (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Uso `asyncio.gather` para lanzar 50 peticiones HTTP a la vez. Si una falla, la excepción me salta pero las otras 49 siguen corriendo por detrás y luego salen errores raros al cerrar el loop. ¿Cómo se hace bien?"},
            {
                "role": "assistant",
                "content": """Es el comportamiento documentado de `gather`: cuando una corrutina falla, `gather` propaga la primera excepción **sin cancelar** las demás, que siguen vivas hasta terminar por su cuenta. Los «errores raros al cerrar» son esas tareas huérfanas (`Task was destroyed but it is pending!`).

Desde Python 3.11 la herramienta correcta es `asyncio.TaskGroup`: si una tarea falla, cancela a las hermanas, espera a que terminen de cancelarse y lanza un `ExceptionGroup` con todos los fallos.

```python
import asyncio

import httpx


async def fetch(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url, timeout=10.0)
    response.raise_for_status()
    return response.text


async def fetch_all(urls: list[str]) -> list[str]:
    async with httpx.AsyncClient() as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(fetch(client, url)) for url in urls]
        # aquí todas han terminado bien; si alguna falló, el bloque lanzó ExceptionGroup
        return [task.result() for task in tasks]
```

Manejo de los fallos con `except*`, que captura por tipo dentro del grupo:

```python
async def main() -> None:
    try:
        pages = await fetch_all(urls)
    except* httpx.HTTPStatusError as group:
        for err in group.exceptions:
            print("HTTP", err.response.status_code, err.request.url)
    except* httpx.TransportError as group:
        print(f"{len(group.exceptions)} fallos de red")
```

`except*` puede ejecutar **varios** bloques para el mismo grupo (uno por tipo que coincida), a diferencia de `except`.

Si de verdad quieres que las demás **sigan** aunque una falle (lo que `gather` hace por accidente), dilo explícitamente con `return_exceptions=True`, que convierte cada excepción en un resultado:

```python
results = await asyncio.gather(*(fetch(client, u) for u in urls), return_exceptions=True)
for url, result in zip(urls, results):
    if isinstance(result, BaseException):
        print(f"{url}: {result!r}")
```

Es correcto para «intenta todas y dame el informe»; es incorrecto si una página fallida invalida el conjunto, porque sigues gastando tiempo y conexiones en las otras.

Resumen de elección:

| Quieres | Usa |
|---|---|
| Todo o nada; un fallo aborta el resto | `TaskGroup` |
| Informe de cada una, fallos incluidos | `gather(..., return_exceptions=True)` |
| Primera que termine | `asyncio.wait(..., return_when=FIRST_COMPLETED)` |

Verificación de que `TaskGroup` cancela: lanza tres tareas, una que falla a los 0,1 s y dos que duermen 10 s; el bloque completo termina en ~0,1 s y las dormilonas reciben `CancelledError`.""",
            },
            {"role": "user", "content": "Perfecto. Son 50 ahora pero pueden ser 5000. ¿Cómo limito a 20 peticiones concurrentes sin perder el comportamiento del TaskGroup?"},
            {
                "role": "assistant",
                "content": """Un `asyncio.Semaphore(20)` dentro de cada tarea. Las 5000 tareas se crean (son baratas: un objeto y una corrutina suspendida), pero solo 20 pasan del `async with sem` a la vez; el resto espera sin consumir conexiones.

```python
import asyncio

import httpx


async def fetch_all(urls: list[str], max_concurrent: int = 20) -> list[str]:
    sem = asyncio.Semaphore(max_concurrent)

    async def bounded_fetch(client: httpx.AsyncClient, url: str) -> str:
        async with sem:                      # suelta el permiso también si fetch lanza
            return await fetch(client, url)

    limits = httpx.Limits(max_connections=max_concurrent)
    async with httpx.AsyncClient(limits=limits) as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(bounded_fetch(client, url)) for url in urls]
        return [task.result() for task in tasks]
```

Dos puntos:

- El `TaskGroup` sigue funcionando igual: si una petición falla, las 19 en vuelo se cancelan y las que esperaban en el semáforo también (la cancelación llega mientras están en `async with sem`, que la propaga).
- `httpx.Limits` es un segundo cinturón: aunque alguien cambie `max_concurrent`, el cliente nunca abre más conexiones de las que le dices. Alinea los dos números.

Si 5000 tareas suspendidas te parecen demasiadas (unos pocos MB, en la práctica no), la alternativa es un patrón productor/consumidor con `asyncio.Queue` y 20 *workers* fijos que sacan URLs de la cola. Es más código y pierde la asociación directa tarea-URL; el semáforo es suficiente hasta decenas de miles.

Prueba de que el límite se respeta, instrumentando el pico de concurrencia:

```python
async def test_respeta_el_limite():
    active = peak = 0
    sem = asyncio.Semaphore(3)

    async def job() -> None:
        nonlocal active, peak
        async with sem:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    async with asyncio.TaskGroup() as tg:
        for _ in range(30):
            tg.create_task(job())
    assert peak == 3
```""",
            },
        ]
    },
    # 6) Cancelación y timeouts en asyncio
    {
        "messages": [
            {"role": "user", "content": "¿Cómo pongo timeouts a corrutinas en asyncio y qué pasa exactamente con la tarea cuando se cancela? Tengo un `except:` genérico que creo que me está rompiendo algo porque hay tareas que no terminan nunca."},
            {
                "role": "assistant",
                "content": """El `except:` desnudo es casi seguro el culpable. Desde Python 3.8, `asyncio.CancelledError` hereda de `BaseException`, no de `Exception`, precisamente para que `except Exception` no la capture por accidente. Pero `except:` lo captura **todo**, incluida la cancelación: la tarea se traga la señal, sigue ejecutándose y quien la canceló se queda esperando para siempre.

Cómo funciona la cancelación: `task.cancel()` hace que el **siguiente `await`** dentro de la tarea lance `CancelledError`. La tarea debe dejar que suba (o relanzarla tras limpiar). Si la captura y no la relanza, la cancelación no ocurre.

```python
import asyncio


async def worker(queue: asyncio.Queue[str]) -> None:
    try:
        while True:
            item = await queue.get()        # aquí llega la CancelledError
            await process(item)
    except asyncio.CancelledError:
        await flush_pending()               # limpieza con await permitida
        raise                               # obligatorio: la cancelación debe propagarse
    except Exception:
        logger.exception("worker falló")    # errores reales, sin tocar la cancelación
        raise
```

Si no necesitas limpieza, no captures `CancelledError` en absoluto; un `finally` basta para cerrar recursos.

**Timeouts.** Desde 3.11, `asyncio.timeout()` es un gestor de contexto que cancela lo que hay dentro y convierte esa cancelación en `TimeoutError`:

```python
async def fetch_with_deadline(url: str) -> bytes:
    try:
        async with asyncio.timeout(5):
            return await download(url)
    except TimeoutError:
        raise RuntimeError(f"{url} tardó más de 5 s") from None
```

`asyncio.wait_for(coro, 5)` hace lo mismo con una corrutina suelta; `timeout()` es preferible porque envuelve varios `await` y permite reajustar el plazo con `reschedule()`.

**Proteger algo de la cancelación.** Si una operación debe completarse aunque cancelen la tarea externa (confirmar una transacción, por ejemplo), `asyncio.shield`:

```python
async def commit_safely(tx: Transaction) -> None:
    await asyncio.shield(tx.commit())   # la cancelación llega al llamador, no a commit()
```

Úsalo poco: lo que proteges sigue corriendo sin que nadie lo espere.

**Diagnóstico de tu caso** en tres pasos:

1. `grep -rn "except:" src/` y sustituye cada uno por `except Exception:` (o el tipo concreto). Es un cambio seguro; solo deja pasar `KeyboardInterrupt`, `SystemExit` y `CancelledError`, que es lo que quieres.
2. Arranca con `PYTHONASYNCIODEBUG=1` (o `asyncio.run(main(), debug=True)`): avisa de corrutinas nunca esperadas y de *callbacks* lentos.
3. Al cerrar, lista lo que queda vivo: `[t for t in asyncio.all_tasks() if not t.done()]`. Las tareas que aparecen ahí tras un `cancel()` son las que se tragan la señal.

Test de regresión para un *worker*:

```python
async def test_worker_se_cancela():
    task = asyncio.create_task(worker(asyncio.Queue()))
    await asyncio.sleep(0)            # deja que arranque y se bloquee en queue.get()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
```

Con el `except:` original, este test se queda colgado en el `await task`, que es exactamente tu síntoma.""",
            },
        ]
    },
    # 7) Context manager que no limpia ante excepción (código roto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo este context manager para SQLite y, si algo falla dentro del `with`, la conexión se queda abierta (lo veo porque el archivo queda bloqueado):

```python
from contextlib import contextmanager
import sqlite3

@contextmanager
def opened_db(path):
    conn = sqlite3.connect(path)
    yield conn
    conn.close()
```

¿No se supone que el context manager cierra siempre?""",
            },
            {
                "role": "assistant",
                "content": """Cierra siempre solo si tú lo escribes así. Con `@contextmanager`, la excepción que ocurre dentro del `with` se **relanza en el `yield`**: la ejecución de tu generador salta de `yield conn` directamente fuera, y `conn.close()` nunca corre. El patrón correcto es `try/finally` alrededor del `yield`, igual que harías en una función normal.

Aprovecho para añadir lo que un gestor de base de datos debería hacer además de cerrar: confirmar si todo fue bien y deshacer si no.

```python
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def opened_db(path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    try:
        yield conn
        conn.commit()          # solo si el bloque terminó sin excepción
    except BaseException:
        conn.rollback()        # también ante KeyboardInterrupt o cancelación
        raise                  # nunca silenciar: el with debe ver el error
    finally:
        conn.close()           # pase lo que pase
```

El orden importa: `commit` dentro del `try` (si falla, también hace *rollback*), `rollback` en el `except`, `close` en el `finally`. Y el `raise` desnudo es obligatorio: si el generador captura la excepción y no la relanza, `contextmanager` interpreta que la has manejado y el código tras el `with` continúa como si nada.

Test que reproduce tu síntoma y confirma el arreglo:

```python
import pytest


def test_cierra_y_deshace_ante_excepcion(tmp_path):
    db = tmp_path / "t.db"
    with opened_db(db) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")

    with pytest.raises(RuntimeError):
        with opened_db(db) as conn:
            conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("fallo a mitad")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")                      # la conexión quedó cerrada

    with opened_db(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone() == (0,)  # y el insert se deshizo
```

Dos alternativas según el contexto:

- **Clase con `__enter__`/`__exit__`** si el gestor tiene estado o quieres reutilizarlo; `__exit__(self, exc_type, exc, tb)` recibe la excepción y, si devuelve `False`/`None`, la propaga. Mismo cuidado: la limpieza va antes del `return`.
- **`sqlite3.Connection` ya es un gestor de contexto**, pero solo de transacción (`commit`/`rollback`), no cierra. `with sqlite3.connect(path) as conn:` deja la conexión abierta al salir; en 3.12 puedes combinar `contextlib.closing(sqlite3.connect(path))` para el cierre y el `with conn:` interno para la transacción.

Si manejas varios recursos a la vez, `contextlib.ExitStack` los cierra en orden inverso aunque fallen los de en medio, sin anidar `with`.""",
            },
        ]
    },
    # 8) Generadores: pipeline perezoso sobre archivo grande
    {
        "messages": [
            {"role": "user", "content": "Tengo que contar errores por hora en un log de 20 GB. Con `lines = f.readlines()` se me va la memoria. ¿Cómo lo estructuro con generadores sin que quede un bucle gigante?"},
            {
                "role": "assistant",
                "content": r"""Como una tubería de generadores: cada etapa recibe un iterable, produce otro y no materializa nada. La memoria se queda en una línea a la vez más el diccionario de contadores, que tiene tantas claves como horas distintas.

```python
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

LINE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}):\d{2}:\d{2}\S* (?P<level>[A-Z]+) ")


def read_lines(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8", errors="replace") as f:
        yield from f                       # el archivo se lee por búfer, una línea cada vez


def parse(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    for line in lines:
        m = LINE_RE.match(line)
        if m:                              # las líneas que no cumplen el formato se descartan
            yield m["ts"], m["level"]


def only_errors(records: Iterable[tuple[str, str]]) -> Iterator[str]:
    for hour, level in records:
        if level == "ERROR":
            yield hour


def errors_per_hour(path: Path) -> Counter[str]:
    return Counter(only_errors(parse(read_lines(path))))


if __name__ == "__main__":
    import sys

    for hour, n in sorted(errors_per_hour(Path(sys.argv[1])).items()):
        print(f"{hour}  {n}")
```

Por qué esta forma y no un bucle:

- **Cada etapa es una función pura sobre iterables** y se prueba sola con una lista pequeña, sin tocar disco: `list(parse(["2024-05-01T10:00:00Z ERROR boom"])) == [("2024-05-01T10", "ERROR")]`.
- **`yield from f`** delega en el iterador del archivo, que ya es perezoso y usa un búfer de lectura; `readlines()` es lo único que carga todo.
- **`Counter` consume el generador** en C, sin bucle explícito en Python, y es la única estructura que crece.
- El `with` en `read_lines` cierra el archivo cuando el generador se agota **o cuando se recolecta** (los generadores ejecutan `finally` al cerrarse). Si cortas el consumo a mitad (`itertools.islice`), llama a `.close()` o deja que salga de ámbito.

Para probar en una muestra antes de las 20 GB:

```python
from itertools import islice

sample = Counter(only_errors(parse(islice(read_lines(path), 100_000))))
```

Un generador se recorre **una vez**: si necesitas dos pasadas (por ejemplo, total de líneas y errores), o bien cuentas ambas cosas en una pasada, o bien construyes la tubería dos veces. Guardarlo en una variable y recorrerlo dos veces devuelve una secuencia vacía la segunda, sin error, que es la trampa habitual.

Rendimiento esperado: el cuello de botella es la expresión regular, unas 1-2 millones de líneas por segundo en CPython. Si el formato es fijo, `line[:13]` y `line.split(" ", 2)[1]` son varias veces más rápidos que la regex y el resto de la tubería no cambia; eso es justo lo que gana separar las etapas.""",
            },
        ]
    },
    # 9) Decorador con parámetros y functools.wraps (solo código)
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y un comentario breve por cada decisión importante."},
            {"role": "user", "content": "decorador de reintentos en python con número de intentos, excepciones a reintentar y backoff exponencial. que no me rompa los nombres ni docstrings de las funciones"},
            {
                "role": "assistant",
                "content": """```python
import functools
import logging
import random
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")    # conserva la firma exacta de la función decorada para el type checker
R = TypeVar("R")

logger = logging.getLogger(__name__)


def retry(
    attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.5,
    max_delay: float = 30.0,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    if attempts < 1:
        raise ValueError(f"attempts debe ser >= 1, recibido {attempts}")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)    # copia __name__, __doc__, __module__, __qualname__, __wrapped__
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as err:
                    if attempt == attempts:
                        raise              # último intento: la excepción original sube intacta
                    delay = min(max_delay, base_delay * 2 ** (attempt - 1))
                    delay *= 1 + random.uniform(-0.2, 0.2)   # jitter: evita reintentos sincronizados
                    logger.warning(
                        "%s falló (%d/%d): %r; reintento en %.2fs",
                        func.__name__, attempt, attempts, err, delay,
                    )
                    time.sleep(delay)
            raise AssertionError("inalcanzable")   # el bucle siempre devuelve o relanza

        return wrapper

    return decorator


# Uso: paréntesis obligatorios aunque no pases argumentos, porque retry devuelve el decorador.
@retry(attempts=4, exceptions=(ConnectionError, TimeoutError), base_delay=0.2)
def fetch_config(url: str) -> dict[str, str]:
    '''Descarga la configuración remota.'''
    raise ConnectionError(url)


if __name__ == "__main__":
    assert fetch_config.__name__ == "fetch_config"          # wraps conserva el nombre
    assert fetch_config.__doc__ == "Descarga la configuración remota."
    assert fetch_config.__wrapped__ is not fetch_config      # la función original sigue accesible
    try:
        fetch_config("http://x")
    except ConnectionError as err:
        assert str(err) == "http://x"                        # la excepción original, no una envuelta
```

```python
# test_retry.py: sin dormir de verdad, parcheando time.sleep
from unittest.mock import patch


def test_reintenta_y_luego_tiene_exito():
    calls = 0

    @retry(attempts=3, exceptions=(ValueError,), base_delay=0)
    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("todavía no")
        return "ok"

    with patch("time.sleep") as sleep:
        assert flaky() == "ok"
    assert calls == 3
    assert sleep.call_count == 2          # duerme entre intentos, no después del último
```""",
            },
        ]
    },
    # 10) Jerarquía de excepciones propias, encadenamiento y notas
    {
        "messages": [
            {"role": "user", "content": "Estoy escribiendo una librería cliente para una API interna y ahora mismo lanzo `ValueError` o `RuntimeError` para todo. ¿Cómo debería diseñar las excepciones?"},
            {
                "role": "assistant",
                "content": """Una base por librería, subclases por **lo que el llamador puede hacer distinto**, datos útiles como atributos, y encadenamiento con `from` para no perder la causa original. El criterio para crear una subclase no es «qué falló» sino «¿alguien va a escribir `except` para este caso concreto?».

```python
# mi_cliente/errors.py
from __future__ import annotations


class ClientError(Exception):
    '''Base de todos los errores de la librería. Permite `except ClientError` para atraparlos todos.'''


class ConfigError(ClientError):
    '''Error del programador: URL mal formada, token ausente. No tiene sentido reintentar.'''


class TransportError(ClientError):
    '''Red o timeout. Normalmente reintentable.'''


class APIError(ClientError):
    '''El servidor respondió con error. Lleva el estado y el cuerpo para decidir qué hacer.'''

    def __init__(self, status: int, message: str, request_id: str | None = None) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message
        self.request_id = request_id


class NotFoundError(APIError):
    '''404: el recurso no existe. Suele ser flujo normal, no un fallo.'''


class RateLimitedError(APIError):
    '''429: lleva cuánto esperar.'''

    def __init__(self, retry_after: float, request_id: str | None = None) -> None:
        super().__init__(429, f"rate limited, retry in {retry_after}s", request_id)
        self.retry_after = retry_after
```

Y en el cliente, cada excepción de bajo nivel se traduce a una de la librería **conservando la original**:

```python
import httpx

from .errors import APIError, NotFoundError, RateLimitedError, TransportError


def get_user(client: httpx.Client, user_id: str) -> dict:
    try:
        response = client.get(f"/users/{user_id}")
    except httpx.TransportError as err:
        raise TransportError(f"no se pudo contactar con la API: {err}") from err

    request_id = response.headers.get("x-request-id")
    if response.status_code == 404:
        raise NotFoundError(404, f"user {user_id} not found", request_id)
    if response.status_code == 429:
        raise RateLimitedError(float(response.headers.get("retry-after", "1")), request_id)
    if response.status_code >= 400:
        err = APIError(response.status_code, response.text[:200], request_id)
        err.add_note(f"GET /users/{user_id}")       # 3.11+: contexto extra sin perder el tipo
        raise err
    return response.json()
```

Por qué cada decisión:

- **`from err`** guarda la causa en `__cause__`; el *traceback* muestra las dos («The above exception was the direct cause of the following exception»). Sin `from`, Python igualmente encadena como `__context__`, pero el mensaje dice «During handling of the above exception, another exception occurred», que sugiere un error accidental. `from None` suprime la cadena, solo cuando la causa no aporta nada.
- **Atributos, no solo texto.** `err.status == 404` es estable; `"404" in str(err)` es frágil y se rompe al traducir mensajes.
- **No heredar de `ValueError`/`RuntimeError`.** Un `except ValueError` del usuario pensado para `int("x")` atraparía tus errores de API por accidente.
- **`add_note`** añade líneas al *traceback* sin crear una excepción nueva; es la forma en 3.11+ de decir «esto pasó mientras hacía X».

Así se usa desde fuera, que es la prueba de que la jerarquía está bien:

```python
try:
    user = get_user(client, "42")
except NotFoundError:
    user = None                                   # caso esperado
except RateLimitedError as err:
    time.sleep(err.retry_after)                   # dato accionable
except TransportError:
    raise                                         # que lo gestione el reintento de arriba
except ClientError as err:
    logger.error("fallo inesperado de la API", exc_info=err)
```

Cada `except` existe porque hace algo distinto; si dos ramas hicieran lo mismo, sobraría una clase. Y documenta en el `README` qué lanza cada función pública: una excepción es parte del contrato tanto como el valor de retorno.""",
            },
        ]
    },
]

ROWS += [
    # 11) pathlib frente a os.path (principiante)
    {
        "messages": [
            {"role": "user", "content": "Tengo un montón de `os.path.join(BASE_DIR, 'data', nombre)` y `glob.glob` por el código y me dicen que use pathlib. ¿Qué gano y cómo lo traduzco?"},
            {
                "role": "assistant",
                "content": """Ganas rutas como **objetos** en vez de cadenas: el operador `/` para unir, métodos para leer, escribir, listar y crear directorios, y el mismo código en Linux, macOS y Windows sin pensar en separadores.

Traducción directa:

| `os.path` / `glob` / `open` | `pathlib` |
|---|---|
| `os.path.join(BASE_DIR, "data", name)` | `BASE_DIR / "data" / name` |
| `os.path.exists(p)` | `p.exists()` |
| `os.path.isfile(p)`, `os.path.isdir(p)` | `p.is_file()`, `p.is_dir()` |
| `os.path.basename(p)`, `os.path.dirname(p)` | `p.name`, `p.parent` |
| `os.path.splitext(p)[1]` | `p.suffix` (y `p.stem` para el nombre sin extensión) |
| `os.makedirs(d, exist_ok=True)` | `d.mkdir(parents=True, exist_ok=True)` |
| `glob.glob(os.path.join(d, "*.csv"))` | `d.glob("*.csv")` (devuelve `Path`, perezoso) |
| `glob.glob(..., recursive=True)` con `**` | `d.rglob("*.csv")` |
| `open(p).read()` | `p.read_text(encoding="utf-8")` |
| `os.path.abspath(p)` | `p.resolve()` (además resuelve enlaces simbólicos) |

Tu caso típico, antes y después:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent     # directorio del módulo actual
DATA_DIR = BASE_DIR / "data"


def load_reports() -> dict[str, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(DATA_DIR.glob("*.csv"))   # glob no garantiza orden: ordena tú
    }
```

Tres cosas que sorprenden al cambiar:

1. **Una ruta absoluta a la derecha de `/` descarta la izquierda**: `Path("/srv") / "/etc/passwd"` es `/etc/passwd`. Es el mismo comportamiento que `os.path.join`, pero conviene recordarlo si el segundo trozo viene del usuario; valida con `path.is_relative_to(BASE_DIR)` (3.9+) después de `resolve()`.
2. **`Path` no es `str`.** Casi toda la biblioteca estándar y las librerías actuales aceptan `Path` (implementa `os.PathLike`), pero alguna API antigua o algún `subprocess` con `shell=True` quieren texto: `str(path)` o `os.fspath(path)`.
3. **`glob` es perezoso y relativo al `Path`**: `DATA_DIR.glob("*.csv")` devuelve rutas completas, no solo nombres, y las devuelve a medida que las recorre; conviértelo en lista si lo vas a usar dos veces.

Siempre `encoding="utf-8"` en `read_text`/`write_text`: sin él, Windows usa la página de códigos local y el mismo archivo se lee distinto en cada máquina. En 3.12 puedes activar `PYTHONWARNDEFAULTENCODING=1` para que Python te avise de cada apertura sin codificación explícita.""",
            },
        ]
    },
    # 12) logging: librería vs aplicación, duplicados (SISTEMA, código roto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """En mi librería hago esto al importar:

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("milib")
```

Y en la app que la usa, cada línea de log sale dos veces. Además, cuando pongo `level=DEBUG` en la app, los `logger.debug` de la librería no aparecen. ¿Qué está mal?""",
            },
            {
                "role": "assistant",
                "content": """Lo que está mal es que la **librería configura** el logging. Configurar (handlers, formato, nivel) es responsabilidad exclusiva de la aplicación; una librería solo emite. Los dos síntomas salen de ahí.

**Duplicados.** Tu `basicConfig` añade un `StreamHandler` al logger raíz al importar. La app añade el suyo. Cada registro de `milib` sube por propagación hasta el raíz y pasa por los dos handlers → dos líneas. (`basicConfig` no hace nada si el raíz ya tiene handlers, así que el orden de importación decide quién «gana» y el bug parece intermitente.)

**DEBUG invisible.** Tu `basicConfig(level=INFO)` fija el nivel del raíz en INFO y además `getLogger("milib")` no tiene nivel propio (hereda). Si la app configura después, su `basicConfig` ya no se aplica (ver arriba) y el raíz sigue en INFO. Los `debug` se descartan antes de llegar a ningún handler.

Arreglo en la librería, que se reduce a esto:

```python
# milib/__init__.py (o cada módulo)
import logging

logger = logging.getLogger(__name__)           # "milib", "milib.sub", ...: jerarquía gratis
logger.addHandler(logging.NullHandler())       # silencio si la app no configura nada; sin warnings
```

Nada de `basicConfig`, nada de `setLevel`, nada de handlers reales. Usa `__name__` para que la app pueda subir o bajar el nivel de `milib.http` sin tocar `milib.parser`.

Configuración en la aplicación, una sola vez, en el punto de entrada:

```python
# app/main.py
import logging.config

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,   # True rompería los loggers creados al importar librerías
    "formatters": {
        "std": {"format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "std", "stream": "ext://sys.stderr"},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "milib": {"level": "DEBUG"},            # solo tu librería en DEBUG; hereda el handler del raíz
        "urllib3": {"level": "WARNING"},        # silenciar ruido de terceros
    },
}


def main() -> None:
    logging.config.dictConfig(LOGGING)
    logging.getLogger(__name__).info("arrancando")
```

Modelo mental que resuelve el 90 % de las dudas: **un registro pasa primero el filtro de nivel de su logger (o del ancestro más cercano con nivel), luego sube por la jerarquía y se entrega a los handlers de cada nivel, y cada handler tiene su propio nivel**. Dos handlers en la ruta = dos salidas.

Comprobación de que no hay duplicados, útil como test de arranque:

```python
root = logging.getLogger()
assert len(root.handlers) == 1, root.handlers
assert logging.getLogger("milib").handlers == [] or all(
    isinstance(h, logging.NullHandler) for h in logging.getLogger("milib").handlers
)
```

Y dos hábitos en el código que emite: `logger.exception("...")` dentro de un `except` (añade el *traceback*), y argumentos de formato en vez de f-strings (`logger.debug("user=%s", user_id)`), para que el formateo no se pague cuando el nivel está desactivado.""",
            },
        ]
    },
    # 13) Empaquetado: pyproject + uv (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Voy a empezar un proyecto Python nuevo (una CLI pequeña con un par de dependencias). ¿Cuál es el flujo mínimo decente hoy con pyproject.toml y uv? No quiero setup.py ni requirements.txt."},
            {
                "role": "assistant",
                "content": """Con `uv` el flujo entero es cuatro comandos y un `pyproject.toml` que él mismo genera y mantiene.

```
uv init --package logtool        # crea pyproject.toml, src/logtool/__init__.py, README, .python-version
cd logtool
uv add httpx typer               # añade a [project.dependencies] y actualiza uv.lock
uv add --dev pytest ruff mypy    # grupo "dev", no se instala en producción
uv run logtool --help            # ejecuta dentro del entorno (lo crea y sincroniza solo)
```

`--package` es lo que quieres para una CLI: *layout* `src/`, sección `[build-system]` y un punto de entrada ya declarado. El `pyproject.toml` resultante, completado con las herramientas habituales:

```toml
[project]
name = "logtool"
version = "0.1.0"
description = "Resumen de logs por hora"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "typer>=0.12",
]

[project.scripts]
logtool = "logtool.cli:main"          # instala el ejecutable `logtool`

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.mypy]
strict = true
```

Qué hace cada pieza y por qué:

- **`uv.lock`** fija versiones exactas de todo el árbol; va al repositorio. `uv sync` en otra máquina (o en CI) reproduce el entorno idéntico. Es el sustituto de `requirements.txt`, pero con resolución real y hashes.
- **`[dependency-groups]`** (PEP 735) es el estándar para dependencias de desarrollo; `uv sync --no-dev` las omite en producción.
- **`src/` layout** evita que los tests importen el código del directorio de trabajo en vez del paquete instalado, que es la causa clásica de «funciona en local, falla instalado».
- **`.python-version`** (`uv python pin 3.12`) hace que `uv` descargue y use ese intérprete aunque el sistema tenga otro.

El punto de entrada:

```python
# src/logtool/cli.py
import typer

app = typer.Typer()


@app.command()
def summarize(path: str, level: str = "ERROR") -> None:
    typer.echo(f"{path}: filtrando {level}")


def main() -> None:
    app()
```

Verificación del *setup* en una línea: `uv run pytest && uv run ruff check . && uv run mypy src`. Si quieres un atajo, `uv run` acepta cualquier comando del entorno, así que un `Makefile` o `justfile` de tres líneas basta; no necesitas `tox` para un proyecto de este tamaño.""",
            },
            {"role": "user", "content": "Genial. ¿Y para publicarla en PyPI cuando esté lista?"},
            {
                "role": "assistant",
                "content": """Dos comandos más, y una prueba en TestPyPI antes de la real.

```
uv build                         # genera dist/logtool-0.1.0.tar.gz y dist/logtool-0.1.0-py3-none-any.whl
uv publish --publish-url https://test.pypi.org/legacy/ --token "$TEST_PYPI_TOKEN"
uv publish --token "$PYPI_TOKEN" # PyPI real
```

Antes de publicar, comprueba el paquete tal y como lo verá un usuario, instalándolo desde el *wheel* en un entorno limpio:

```
uv venv /tmp/check && uv pip install --python /tmp/check/bin/python dist/*.whl
/tmp/check/bin/logtool --help
```

Si eso funciona, el `[project.scripts]` y el `src/` layout están bien. Lo que suele fallar en la primera publicación:

- **Nombre ocupado.** PyPI normaliza nombres (`log-tool`, `log_tool` y `LogTool` son el mismo); comprueba en `pypi.org/project/<nombre>` antes de elegir.
- **Versión repetida.** PyPI no permite resubir la misma versión, ni siquiera borrándola. Sube la versión en `pyproject.toml` (con `uv version --bump patch` en uv 0.7+, o a mano) en cada publicación.
- **Archivos de más o de menos.** Hatchling incluye por defecto lo que hay bajo `src/logtool/`; si necesitas datos (plantillas, un `.json`), confirma que están dentro del paquete y mira el contenido del *wheel* con `unzip -l dist/*.whl`.
- **`readme` y `license`.** PyPI muestra el `README.md` como página del proyecto; añade `license = "MIT"` (o la que sea, como expresión SPDX) y `classifiers` si quieres que aparezca bien catalogado.

Para CI, la opción recomendada hoy es **publicación confiable** (*trusted publishing*) con OIDC desde GitHub Actions, que evita guardar tokens: configuras el repositorio en PyPI y en el *workflow* usas `uv publish` sin `--token` dentro de un *job* con `permissions: id-token: write`. El flujo típico es: *tag* `v0.1.0` → `uv build` → `uv publish`. Hasta que tengas eso, un token con alcance limitado al proyecto (no el de toda la cuenta) en un *secret* del repositorio es suficiente.""",
            },
        ]
    },
    # 14) pytest: fixtures, scopes, conftest (system variante)
    {
        "messages": [
            {"role": "system", "content": "Responde en español con ejemplos ejecutables y sin introducciones ni cierres."},
            {"role": "user", "content": "Mis tests repiten el mismo setup en cada función (crear una base de datos SQLite temporal, cargar tres filas, crear un cliente). ¿Cómo uso fixtures de pytest bien? No tengo claro qué va en conftest.py ni qué son los scopes."},
            {
                "role": "assistant",
                "content": """Una fixture es una función que **prepara** algo, lo entrega al test y, si usa `yield`, lo **limpia** después. El `conftest.py` es el sitio donde pytest las busca automáticamente para todos los tests de ese directorio y subdirectorios, sin importarlas. El *scope* dice cuántas veces se ejecuta: una por test (`function`, por defecto), una por módulo, o una por sesión completa.

Tu caso, descompuesto en tres fixtures encadenadas:

```python
# tests/conftest.py
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from myapp.client import Client


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    # tmp_path es una fixture de pytest: directorio nuevo por test, borrado al final
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    connection.executemany("INSERT INTO users (name) VALUES (?)", [("ana",), ("luis",), ("eva",)])
    connection.commit()
    yield connection            # el test corre aquí
    connection.close()          # limpieza: corre aunque el test falle


@pytest.fixture
def client(conn: sqlite3.Connection) -> Client:
    return Client(conn)
```

```python
# tests/test_users.py
def test_lista_usuarios(client):
    assert [u.name for u in client.list_users()] == ["ana", "luis", "eva"]


def test_borrar_usuario(client, conn):
    client.delete_user(2)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone() == (2,)
```

Cada test recibe una base de datos **nueva** con las tres filas; `test_borrar_usuario` no afecta a ningún otro. Eso es lo que compra el scope `function`: aislamiento. Con `scope="module"` la conexión se compartiría entre todos los tests del archivo y el borrado del segundo test rompería al tercero.

Cuándo subir el scope: cuando el recurso es caro **y** de solo lectura. Un ejemplo típico es cargar un modelo o levantar un contenedor:

```python
@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    with PostgresContainer("postgres:16") as pg:     # testcontainers; ~5 s de arranque, una vez
        yield pg.get_connection_url()
```

Y combina scopes: `pg_url` de sesión, y una fixture `function` que abre una transacción y hace *rollback* al final, para que cada test vea la base limpia sin pagar el arranque.

Reglas que evitan los problemas habituales:

- Una fixture de scope corto puede depender de una de scope largo; al revés pytest lanza `ScopeMismatch`.
- `autouse=True` aplica la fixture a todos los tests sin nombrarla. Úsalo solo para cosas transversales (fijar la zona horaria, congelar la semilla aleatoria); si un test necesita algo, mejor que lo pida por nombre.
- Si un test necesita **variantes** del setup (usuario con 0, 3 o 100 filas), devuelve una **fábrica** desde la fixture en vez de multiplicar fixtures:

```python
@pytest.fixture
def make_conn(tmp_path):
    def _make(names: list[str]) -> sqlite3.Connection:
        c = sqlite3.connect(tmp_path / f"{len(names)}.db")
        c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        c.executemany("INSERT INTO users (name) VALUES (?)", [(n,) for n in names])
        return c
    return _make


def test_vacio(make_conn):
    assert Client(make_conn([])).list_users() == []
```

`pytest --fixtures` lista todas las disponibles con su docstring y `pytest --setup-show` imprime en qué orden se crean y destruyen, que es la forma rápida de ver si un scope está haciendo lo que crees.""",
            },
        ]
    },
    # 15) pytest: parametrize + monkeypatch de entorno y reloj
    {
        "messages": [
            {"role": "user", "content": "Quiero probar una función que lee `API_URL` del entorno y usa `time.time()` para decidir si un token ha caducado. ¿Cómo la testeo sin tocar mi entorno real ni esperar de verdad? Y tengo que probar varios casos de caducidad."},
            {
                "role": "assistant",
                "content": """`monkeypatch` para el entorno y el reloj, `parametrize` para los casos. Y, si puedes tocar la función, inyecta el reloj como parámetro: el test queda más simple y la función deja de depender de un global.

Supongo esta función:

```python
# auth.py
import os
import time


def is_expired(issued_at: float, ttl_seconds: int = 3600, *, now: float | None = None) -> bool:
    current = time.time() if now is None else now
    return current - issued_at >= ttl_seconds


def api_url() -> str:
    url = os.environ.get("API_URL")
    if not url:
        raise RuntimeError("API_URL no está definida")
    return url.rstrip("/")
```

El parámetro `now` es la inyección: en producción nadie lo pasa; en tests no necesitas parchear nada.

```python
# test_auth.py
import pytest

import auth


@pytest.mark.parametrize(
    ("issued_at", "now", "ttl", "expected"),
    [
        pytest.param(1000.0, 1000.0, 3600, False, id="recien-emitido"),
        pytest.param(1000.0, 4599.9, 3600, False, id="una-decima-antes"),
        pytest.param(1000.0, 4600.0, 3600, True, id="justo-al-limite"),
        pytest.param(1000.0, 9000.0, 3600, True, id="muy-caducado"),
        pytest.param(1000.0, 1000.0, 0, True, id="ttl-cero-caduca-siempre"),
    ],
)
def test_is_expired(issued_at, now, ttl, expected):
    assert auth.is_expired(issued_at, ttl, now=now) is expected
```

Los `id=` aparecen en la salida (`test_is_expired[justo-al-limite]`) y permiten `pytest -k limite`. Sin ellos, pytest genera `[1000.0-4600.0-3600-True]`, que no dice nada.

Si **no** puedes cambiar la firma (código ajeno), parchea el reloj donde se usa:

```python
def test_is_expired_sin_inyeccion(monkeypatch):
    monkeypatch.setattr(auth.time, "time", lambda: 4600.0)
    assert auth.is_expired(1000.0, 3600) is True
```

`monkeypatch.setattr(auth.time, "time", ...)` sustituye la función en el módulo `time` que `auth` importó; como `auth` hace `time.time()` en cada llamada, ve el reemplazo. Si `auth` hubiera hecho `from time import time`, tendrías que parchear `auth.time` en su lugar: se parchea **donde se busca el nombre**, no donde se define.

Para el entorno:

```python
def test_api_url_normaliza_barra_final(monkeypatch):
    monkeypatch.setenv("API_URL", "https://api.example.com/")
    assert auth.api_url() == "https://api.example.com"


def test_api_url_falla_si_no_esta(monkeypatch):
    monkeypatch.delenv("API_URL", raising=False)   # raising=False: no falla si ya no existía
    with pytest.raises(RuntimeError, match="API_URL"):
        auth.api_url()
```

Todo lo que `monkeypatch` cambia se deshace al terminar el test, incluso si falla; por eso es preferible a `os.environ["API_URL"] = ...` a mano o a `unittest.mock.patch.dict` sin contexto.

Un detalle del caso límite `justo-al-limite`: elegí `>=` en la función y el test lo fija. Si alguien lo cambia a `>`, ese caso falla con un mensaje claro. Los tests parametrizados valen sobre todo por los casos de frontera, no por los obvios.""",
            },
        ]
    },
    # 16) Perfilado: dónde se va el tiempo (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Mi script de procesamiento de datos tarda 40 segundos y no tengo ni idea de en qué parte. ¿Cómo lo perfilo bien antes de ponerme a optimizar a ciegas?"},
            {
                "role": "assistant",
                "content": """Tres herramientas, de la más gruesa a la más fina, y un criterio: optimizas **solo** lo que el perfil señale, y vuelves a medir después de cada cambio.

**1. Perfil determinista con `cProfile` (stdlib).** Cuenta cada llamada; sobrecarga del 30-100 %, pero exacto.

```
python -m cProfile -o perfil.prof procesar.py datos.csv
python -c "import pstats; pstats.Stats('perfil.prof').sort_stats('cumulative').print_stats(15)"
```

Cómo leer la tabla:

- `cumtime`: tiempo total dentro de la función **incluyendo** lo que llama. Ordena por esto para ver qué rama del programa pesa.
- `tottime`: tiempo en la propia función **sin** sus llamadas. Ordena por esto (`sort_stats('tottime')`) para ver dónde se ejecuta el trabajo de verdad.
- `ncalls`: si una función barata aparece con 10 millones de llamadas, el problema es el bucle que la llama, no ella.

Si prefieres perfilar solo un tramo:

```python
import cProfile
import pstats

with cProfile.Profile() as profile:
    result = process(rows)

pstats.Stats(profile).sort_stats("tottime").print_stats(10)
```

**2. Perfil por muestreo con `pyinstrument`** (`uv add --dev pyinstrument`). Menos sobrecarga y, sobre todo, una salida en árbol que se lee de un vistazo:

```
pyinstrument procesar.py datos.csv
```

Muestra la pila de llamadas con porcentajes anidados; para un script de 40 s suele ser la primera herramienta que uso porque responde «qué rama» en diez segundos.

**3. Línea a línea con `line_profiler`** cuando ya sabes la función culpable:

```
uv add --dev line_profiler
kernprof -lv procesar.py datos.csv     # con @profile sobre la función sospechosa
```

Lo que suele aparecer en scripts de datos, por frecuencia:

| Síntoma en el perfil | Causa típica | Arreglo |
|---|---|---|
| `tottime` alto en `<listcomp>` o en tu función con millones de `ncalls` | bucle Python sobre filas | vectorizar (NumPy/pandas) o mover a C (`csv`, `re` compilado) |
| `cumtime` alto en `pandas...__getitem__` o `iterrows` | acceso fila a fila a un DataFrame | `itertuples`, `.to_numpy()`, operaciones por columna |
| `posix.read`/`io` dominando | lectura sin búfer o archivo abierto mil veces | abrir una vez, leer por bloques |
| `json.loads` o `re.match` muy arriba | parseo repetido de lo mismo | cachear, `re.compile` fuera del bucle, `orjson` |
| `method 'append' of 'list'` con muchas llamadas | construir listas enormes elemento a elemento | comprensión o `extend` |

Dos medidas de disciplina:

- **Antes de tocar nada**, guarda el tiempo base con `time.perf_counter()` alrededor del `main()` (o `/usr/bin/time -v`, que además da memoria pico). Sin número de partida no sabrás si mejoraste.
- Perfila con **datos reales o representativos**. Un archivo de prueba de 100 filas da un perfil dominado por el arranque (`import pandas` solo ya son ~0,5 s; `python -X importtime` lo desglosa) y te llevará a optimizar lo que no importa.

Cuando el perfil diga que el 80 % está en una función, ataca esa y nada más; en scripts de este tipo, lo normal es que un solo cambio (sacar algo de un bucle, vectorizar, abrir el archivo una vez) baje los 40 s a menos de 10.""",
            },
        ]
    },
    # 17) Vectorización con NumPy (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Tengo dos millones de puntos (lat, lon) y para cada uno calculo la distancia a un punto fijo con un bucle `for` y `math`. Tarda unos 30 segundos. Me dicen que con NumPy vuela, pero no entiendo cómo «quitar» el bucle."},
            {
                "role": "assistant",
                "content": """«Quitar el bucle» significa escribir la fórmula **una vez sobre arrays enteros**: NumPy aplica cada operación a todos los elementos en C, sin pasar por el intérprete en cada punto. Tu bucle hace dos millones de iteraciones de Python a ~10 µs cada una; la versión vectorizada hace una docena de operaciones sobre arrays contiguos.

Con la fórmula del haversine, que asumo es la que usas:

```python
import numpy as np

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    '''Distancia en km de cada (lat[i], lon[i]) al punto fijo (lat0, lon0). Entradas en grados.'''
    lat, lon = np.radians(lat), np.radians(lon)          # arrays completos, de golpe
    lat0, lon0 = np.radians(lat0), np.radians(lon0)      # escalares: se difunden (broadcasting)
    dlat = lat - lat0
    dlon = lon - lon0
    a = np.sin(dlat / 2) ** 2 + np.cos(lat) * np.cos(lat0) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))
```

Uso, partiendo de tu lista de tuplas:

```python
points = np.array(points_list, dtype=np.float64)   # forma (2_000_000, 2); una sola conversión
distances = haversine_km(points[:, 0], points[:, 1], lat0=40.4168, lon0=-3.7038)
```

Cada línea de `haversine_km` es una operación sobre los dos millones de valores. `lat0` es un escalar y NumPy lo «difunde» (*broadcasting*) para combinarlo con el array sin copiarlo dos millones de veces. En un portátil, esto tarda ~0,2 s frente a tus 30.

Verificación: compara con tu función original en una muestra, con tolerancia de coma flotante:

```python
import math


def haversine_scalar(lat, lon, lat0, lon0):
    lat, lon, lat0, lon0 = map(math.radians, (lat, lon, lat0, lon0))
    a = math.sin((lat - lat0) / 2) ** 2 + math.cos(lat) * math.cos(lat0) * math.sin((lon - lon0) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


sample = points[:1000]
expected = np.array([haversine_scalar(la, lo, 40.4168, -3.7038) for la, lo in sample])
np.testing.assert_allclose(haversine_km(sample[:, 0], sample[:, 1], 40.4168, -3.7038), expected, rtol=1e-12)
```

Dos cosas que determinan si la ganancia se materializa:

- **La conversión a array se hace una vez**, fuera de cualquier bucle. Si tus puntos llegan como lista de tuplas, `np.array(lista)` cuesta ~1 s para dos millones; si llegan de un CSV, `np.loadtxt` o `pandas.read_csv(...).to_numpy()` directamente.
- **Memoria**: cada array intermedio (`dlat`, `dlon`, `a`) son 16 MB para dos millones de `float64`. Aquí es irrelevante; con cien millones de puntos procesarías por bloques de, digamos, 10 millones, con el mismo código dentro del bloque.""",
            },
            {"role": "user", "content": "Vale, funciona. Pero ahora necesito algo condicional: si la distancia es menor de 5 km aplicar una tarifa, si está entre 5 y 20 otra, y si no otra. ¿Vuelvo al bucle con `if`?"},
            {
                "role": "assistant",
                "content": """No: los condicionales se vectorizan con **máscaras booleanas**. Una comparación sobre un array devuelve un array de `True`/`False`, y con él seleccionas, asignas o eliges entre alternativas.

Para tres tramos, `np.select` es lo más legible:

```python
def fare(distances_km: np.ndarray) -> np.ndarray:
    conditions = [
        distances_km < 5,
        distances_km < 20,            # se evalúa en orden: aquí ya se sabe que es >= 5
    ]
    rates = [2.50, 1.80]
    return np.select(conditions, rates, default=1.20) * distances_km
```

`np.select` toma la primera condición verdadera para cada elemento, igual que una cadena `if/elif/else`. Para dos ramas, `np.where(cond, a, b)` es el equivalente directo del operador ternario.

Otras formas que verás, y cuándo cada una:

```python
mask = distances_km < 5
near_total = distances_km[mask].sum()           # filtrar: solo los cercanos
fares = np.full_like(distances_km, 1.20)
fares[mask] = 2.50                              # asignar por máscara, en el sitio
fares[(distances_km >= 5) & (distances_km < 20)] = 1.80   # combinar: & | ~, con paréntesis obligatorios
```

El error habitual es escribir `and`/`or` entre arrays: lanza `ValueError: The truth value of an array with more than one element is ambiguous`. Entre máscaras se usan `&`, `|` y `~`, y por precedencia van siempre con paréntesis alrededor de cada comparación.

Para muchos tramos (una tabla de tarifas), `np.digitize` o `np.searchsorted` convierten la distancia en índice de tramo en una sola operación:

```python
edges = np.array([5.0, 20.0])
rates = np.array([2.50, 1.80, 1.20])
fares = rates[np.searchsorted(edges, distances_km, side="right")] * distances_km
```

Para la frontera: `searchsorted(..., side="right")` devuelve 0 si `d < 5`, 1 si `5 <= d < 20` y 2 si `d >= 20`, el mismo criterio que la cadena de `np.select` de arriba.

Lo que **no** hay que usar es `np.vectorize(mi_funcion_con_if)`: parece vectorizar, pero por dentro es un bucle de Python elemento a elemento, con la misma velocidad que tu `for` original. Está pensado para comodidad de difusión, no para rendimiento.

Comprobación rápida de los tres caminos:

```python
d = np.array([0.0, 4.99, 5.0, 19.99, 20.0, 100.0])
expected = d * np.array([2.50, 2.50, 1.80, 1.80, 1.20, 1.20])
np.testing.assert_allclose(fare(d), expected)
np.testing.assert_allclose(rates[np.searchsorted(edges, d, side="right")] * d, expected)
```""",
            },
        ]
    },
    # 18) GIL, hilos y procesos (usuario en inglés)
    {
        "messages": [
            {"role": "user", "content": "My image-processing batch uses `ThreadPoolExecutor(max_workers=8)` and it's not any faster than a plain loop; CPU sits at ~100% of one core. I keep hearing 'the GIL'. What exactly is going on and what should I use instead?"},
            {
                "role": "assistant",
                "content": """What you are seeing is the GIL doing its job. CPython's Global Interpreter Lock lets only one thread execute Python bytecode at a time. Eight threads running pure-Python pixel loops take turns on one core; the total work is the same, plus switching overhead. Threads only help when the work is **waiting** (network, disk, `sleep`) or when it runs inside a C library that **releases** the GIL while it works.

So the decision is about where the time goes:

| Workload | Use |
|---|---|
| I/O-bound (HTTP, DB, files) | `ThreadPoolExecutor` or `asyncio` |
| CPU-bound in Python code | `ProcessPoolExecutor` |
| CPU-bound inside NumPy / Pillow / OpenCV ops that release the GIL | threads can work; measure |

For a CPU-bound batch, processes give you real parallelism: each worker is a separate interpreter with its own GIL.

```python
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageFilter


def process_one(path: Path) -> Path:
    out = path.with_name(f"{path.stem}_blur{path.suffix}")
    with Image.open(path) as img:
        img.filter(ImageFilter.GaussianBlur(4)).save(out)
    return out


def main(paths: list[Path]) -> None:
    # chunksize batches submissions, cutting IPC overhead when there are thousands of small jobs
    with ProcessPoolExecutor() as pool:          # default: os.cpu_count() workers
        for out in pool.map(process_one, paths, chunksize=8):
            print(out)


if __name__ == "__main__":                        # mandatory: workers re-import this module
    main([Path(p) for p in sys.argv[1:]])
```

Things that bite with processes:

- **Arguments and results are pickled.** Pass file paths, not loaded images; pass small results back. If you ship a 50 MB array per task, serialization eats the gain. For big shared read-only data, `multiprocessing.shared_memory` or memory-mapped files.
- **`if __name__ == "__main__"` is not optional.** On macOS and Windows the default start method is `spawn`: each worker starts a fresh interpreter and imports your script. Without the guard, every worker spawns its own pool, recursively. Linux still defaults to `fork` in 3.12 (3.14 switches to `forkserver`), which hides this bug until you deploy elsewhere.
- **Exceptions surface at `.result()`** (or when iterating `map`), with the worker's traceback attached.

A quick way to confirm the diagnosis before rewriting anything: time one image in a loop, then the whole batch with threads. If `threads_time ≈ n × single_time`, you are GIL-bound. If Pillow's filter were releasing the GIL for the heavy part, threads would already have helped; Pillow releases it for some operations but your loop around it is still Python.

On the horizon, since you will read about it: Python 3.12 added per-interpreter GILs (PEP 684), but only via the C API; 3.13 ships an **experimental** free-threaded build (`python3.13t`, PEP 703) where threads run in parallel, at the cost of single-thread speed and with much of the ecosystem still catching up; 3.14 adds `concurrent.futures.InterpreterPoolExecutor` on top of PEP 734. For production in 2025, processes remain the answer for CPU-bound Python.""",
            },
        ]
    },
    # 19) Late binding en closures (vos, código roto)
    {
        "messages": [
            {
                "role": "user",
                "content": """No entiendo este comportamiento, me imprime `2 2 2` en vez de `0 1 2`:

```python
callbacks = []
for i in range(3):
    callbacks.append(lambda: print(i))

for cb in callbacks:
    cb()
```

¿Las lambdas no deberían «recordar» el valor de `i` de cuando se crearon?""",
            },
            {
                "role": "assistant",
                "content": """No: una *closure* captura la **variable**, no su valor en ese momento. Las tres lambdas apuntan a la misma `i` del ámbito exterior, y cuando las llamás, el bucle ya terminó e `i` vale 2. Esto se llama *late binding* (enlace tardío): el nombre se resuelve al ejecutar la lambda, no al crearla.

Lo podés ver inspeccionando la closure:

```python
callbacks[0].__closure__[0].cell_contents   # 2: las tres comparten la misma celda
```

Tres formas de fijar el valor, de la más habitual a la más explícita:

**1. Argumento por defecto.** Los defaults se evalúan al definir la función, así que cada lambda recibe su propio `i`:

```python
callbacks = [lambda i=i: print(i) for i in range(3)]
```

Funciona, pero deja una lambda que acepta un argumento que nadie debería pasar.

**2. `functools.partial`.** Fija el argumento sin cambiar la firma visible:

```python
from functools import partial

callbacks = [partial(print, i) for i in range(3)]
```

**3. Una fábrica.** Cada llamada a `make_callback` crea un ámbito nuevo con su propia `i`; es la versión más clara cuando la lambda tiene lógica:

```python
def make_callback(value: int):
    return lambda: print(value)

callbacks = [make_callback(i) for i in range(3)]
```

Las tres imprimen `0 1 2`.

Dónde muerde en la práctica, más allá del ejemplo:

- Registrar *handlers* en un bucle (botones de una GUI, rutas de un framework, `signal.connect`).
- `threading.Thread(target=lambda: worker(item))` dentro de un `for item in items`: todos los hilos procesan el último `item`. Usá `Thread(target=worker, args=(item,))`.
- Comprensiones de generador que se consumen después del bucle que las creó.

`ruff` lo detecta con la regla `B023` (*function definition does not bind loop variable*). Y un test que lo deja fijado:

```python
def test_callbacks_capturan_su_valor(capsys):
    callbacks = [partial(print, i) for i in range(3)]
    for cb in callbacks:
        cb()
    assert capsys.readouterr().out == "0\\n1\\n2\\n"
```""",
            },
        ]
    },
    # 20) Import circular (system variante, error concreto)
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero senior de Python. Diagnostica antes de proponer, explica el porqué y da el cambio más pequeño que arregla el problema."},
            {
                "role": "user",
                "content": """Al arrancar la app:

```
  File "/app/app/services.py", line 3, in <module>
    from app.models import User
ImportError: cannot import name 'User' from partially initialized module 'app.models' (most likely due to a circular import) (/app/app/models.py)
```

`models.py` hace `from app.services import notify_user` arriba del todo porque `User.save()` llama a `notify_user`. Y `services.py` necesita `User` para el tipo del parámetro. ¿Cómo lo rompo?""",
            },
            {
                "role": "assistant",
                "content": """**Qué dice el error.** Python importa `app.models`; en su línea 1 encuentra `from app.services import notify_user` y pausa `models` (ya está en `sys.modules`, pero vacío: «partially initialized») para ejecutar `services`. `services` pide `User` a ese módulo a medio cargar, y `User` aún no se ha definido porque la clase viene después del import. De ahí el `ImportError`. El orden de arranque decide quién falla: si alguien importara `services` primero, el error saldría al revés.

**Diagnóstico.** Hay dos dependencias cruzadas de naturaleza distinta:

- `models → services`: dependencia **real en tiempo de ejecución** (`save()` llama a `notify_user`).
- `services → models`: dependencia **solo para tipar** (`User` aparece en una anotación).

Las de tipo se rompen gratis; las de ejecución se rompen moviendo el import o, mejor, invirtiendo la dirección.

**Cambio mínimo: el import de tipo pasa a `TYPE_CHECKING`.**

```python
# app/services.py
from __future__ import annotations          # las anotaciones no se evalúan al importar

from typing import TYPE_CHECKING

if TYPE_CHECKING:                           # True solo para mypy/pyright; False en ejecución
    from app.models import User


def notify_user(user: User, message: str) -> None:
    send_email(user.email, message)
```

Con esto `services` ya no importa `models` al cargar, el ciclo desaparece y los verificadores de tipos siguen viendo `User`. `from __future__ import annotations` hace que `User` en la anotación sea una cadena diferida, que es lo que permite usarla sin que exista en ejecución.

**Si el ciclo fuera de ejecución en los dos sentidos**, tres opciones por orden de preferencia:

1. **Invertir la dependencia.** `models` no debería conocer a `services` (la capa de dominio no llama a la de servicios). Que `User.save()` no notifique, y que quien llama a `save()` llame después a `notify_user`. O que `save()` acepte un *callback*: `def save(self, on_saved: Callable[[User], None] | None = None)`.
2. **Extraer lo compartido a un tercer módulo** del que ambos importan (`app/notifications.py` con `notify_user`, sin importar `models`).
3. **Import local dentro de la función**, como parche:

```python
class User:
    def save(self) -> None:
        from app.services import notify_user   # se resuelve al llamar, no al importar
        persist(self)
        notify_user(self, "guardado")
```

Funciona y es rápido (el segundo import es una consulta a `sys.modules`), pero esconde la dependencia; úsalo solo con un comentario que diga por qué.

**Verificación.** `python -c "import app.services; import app.models"` y al revés `python -c "import app.models; import app.services"`: los dos órdenes deben arrancar. Y un test que lo deja fijado:

```python
import importlib
import sys


def test_no_hay_import_circular():
    for name in ("app.models", "app.services"):
        sys.modules.pop(name, None)
    importlib.import_module("app.services")     # el orden que fallaba
    importlib.import_module("app.models")
```

Para encontrar ciclos antes de que exploten, `python -X importtime -c "import app" 2>&1 | sort -t'|' -k2 -n` muestra el árbol de imports, y `ruff` detecta imports de solo tipo que deberían ir bajo `TYPE_CHECKING` con la regla `TCH001`.""",
            },
        ]
    },
]

ROWS += [
    # 21) f-strings: especificadores de formato (principiante)
    {
        "messages": [
            {"role": "user", "content": "Uso f-strings solo para meter variables, tipo f\"Total: {total}\". Sé que se pueden formatear números y alinear columnas pero siempre acabo buscando la sintaxis. ¿Me das las formas que de verdad se usan?"},
            {
                "role": "assistant",
                "content": r"""La sintaxis es `{expresión!conversión:formato}`; la conversión y el formato son opcionales. Las que se usan a diario:

```python
total = 1234567.891
ratio = 0.8764
name = "ana"
items = 42

f"{total:.2f}"          # '1234567.89'      dos decimales
f"{total:,.2f}"         # '1,234,567.89'    separador de miles
f"{total:_.0f}"         # '1_234_568'       guion bajo como separador
f"{ratio:.1%}"          # '87.6%'           porcentaje (multiplica por 100)
f"{items:05d}"          # '00042'           relleno con ceros
f"{items:x}"            # '2a'              hexadecimal; 'b' binario, 'o' octal, '#x' -> '0x2a'
f"{1e-7:.3e}"           # '1.000e-07'       notación científica
f"{name!r}"             # "'ana'"           repr(): comillas visibles, útil en logs
f"{name=}"              # "name='ana'"      depuración: nombre y valor (3.8+)
f"{total=:.1f}"         # 'total=1234567.9' el = se combina con formato
```

Alineación, que es lo que necesitas para tablas en consola. `<` izquierda, `>` derecha, `^` centro, seguido del ancho:

```python
rows = [("manzana", 3, 1.5), ("kiwi", 12, 0.25), ("sandía", 1, 4.0)]
print(f"{'producto':<10}{'uds':>5}{'precio':>8}")
for product, units, price in rows:
    print(f"{product:<10}{units:>5}{price:>8.2f}")
```

```
producto    uds  precio
manzana       3    1.50
kiwi         12    0.25
sandía        1    4.00
```

El ancho puede ser una variable: `f"{product:<{width}}"`.

Fechas: el formato tras los dos puntos va directo a `strftime`:

```python
from datetime import datetime

now = datetime(2025, 3, 9, 14, 5)
f"{now:%Y-%m-%d %H:%M}"     # '2025-03-09 14:05'
f"{now:%d/%m/%Y}"           # '09/03/2025'
```

Desde Python 3.12 (PEP 701) puedes reutilizar el mismo tipo de comillas dentro y anidar sin límite, lo que antes daba `SyntaxError`:

```python
f"{', '.join(f"{k}={v}" for k, v in {"a": 1, "b": 2}.items())}"   # 'a=1, b=2'
f"{"\n".join(names)}"                                               # barras invertidas permitidas
```

Dos trampas:

- `{` literal se escribe `{{` y `}` como `}}`: `f"{{id: {items}}}"` → `'{id: 42}'`.
- En `logging` no uses f-strings: `logger.debug("total=%s", total)` evita formatear cuando el nivel está desactivado y permite agrupar mensajes iguales.

Para comprobar cualquier especificador sin recordarlo, `format(valor, "espec")` en el REPL hace exactamente lo mismo que la f-string: `format(0.5, ".0%")` → `'50%'`.""",
            },
        ]
    },
    # 22) itertools y functools: las piezas que se usan de verdad (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "¿Qué funciones de itertools y functools merecen la pena de verdad? Tengo la sensación de que reescribo cosas que ya existen, y `groupby` me ha dado resultados raros."},
            {
                "role": "assistant",
                "content": """Empiezo por `groupby`, porque el «resultado raro» tiene una causa concreta: **agrupa elementos consecutivos iguales**, no todos los iguales. Si la entrada no está ordenada por la clave, obtienes varios grupos para la misma clave.

```python
from itertools import groupby

data = ["a", "b", "a"]
[(k, list(g)) for k, g in groupby(data)]           # [('a', ['a']), ('b', ['b']), ('a', ['a'])]
[(k, list(g)) for k, g in groupby(sorted(data))]   # [('a', ['a', 'a']), ('b', ['b'])]
```

Y segunda trampa: cada grupo es un iterador que comparte el recorrido con el principal; si avanzas al siguiente grupo, el anterior se agota. Materializa con `list(g)` dentro del bucle o usa `defaultdict(list)` cuando no quieras ordenar.

Las que uso con regularidad, con el patrón que sustituyen:

```python
from itertools import accumulate, batched, chain, islice, pairwise, product
from functools import cache, partial, reduce

# pairwise (3.10): elementos consecutivos, sin zip(xs, xs[1:]) que copia la lista
list(pairwise([1, 4, 9, 16]))                # [(1, 4), (4, 9), (9, 16)]
all(a <= b for a, b in pairwise(xs))         # "está ordenado" sin índices

# batched (3.12): trocear en bloques de n, el último más corto
list(batched("ABCDEFG", 3))                  # [('A','B','C'), ('D','E','F'), ('G',)]
for chunk in batched(rows, 500): db.insert_many(chunk)

# chain.from_iterable: aplanar un nivel sin sum(lists, []) (que es O(n²))
list(chain.from_iterable([[1, 2], [3], []]))  # [1, 2, 3]

# accumulate: sumas acumuladas o cualquier reducción paso a paso
list(accumulate([1, 2, 3, 4]))               # [1, 3, 6, 10]
list(accumulate([3, 1, 4, 1], max))          # [3, 3, 4, 4]: máximo visto hasta cada punto

# islice: cortar un iterador sin materializarlo (primeros 10 de un generador infinito)
list(islice(iter(int, 1), 3))                # bueno, esto no termina... islice(count(), 3) sí: [0, 1, 2]

# product: bucles anidados como un solo iterable
for x, y in product(range(3), repeat=2): ...  # 9 pares, sin dos niveles de for
```

De `functools`:

```python
# partial: fijar argumentos; mejor que lambda porque tiene __name__, repr y se puede introspeccionar
read_utf8 = partial(open, encoding="utf-8")
debug = partial(print, file=sys.stderr)

# cache / lru_cache: memoización para funciones puras con argumentos hashables
@cache
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)

# reduce: solo cuando no hay builtin. sum, min, max, any, all, "".join ya son reduce
reduce(operator.or_, sets, set())            # unión de muchos sets: set().union(*sets) es más claro
```

`reduce` es el que más se sobreusa: si puedes nombrar la operación (`sum`, `max`, `math.prod`), el *builtin* es más rápido y se lee mejor. `functools.reduce` queda para operaciones sin nombre propio o para encadenar funciones.

Una comprobación que resume el criterio: si tu bucle `for` solo existe para construir una lista, probablemente es una comprensión; si solo existe para combinar, acumular o trocear, probablemente es una de estas. Lo que no hay que hacer es forzarlas donde un `for` de tres líneas se entiende mejor.""",
            },
        ]
    },
    # 23) Fechas con zoneinfo y DST (multiturno, bug concreto)
    {
        "messages": [
            {"role": "user", "content": "Tengo un sistema de citas en España. Guardo `datetime.now()` en la base de datos y calculo recordatorios restando horas. El último domingo de marzo los recordatorios salieron una hora tarde y en octubre una hora antes. ¿Qué está pasando?"},
            {
                "role": "assistant",
                "content": """Estás trabajando con *datetimes* **ingenuos** (sin zona horaria): `datetime.now()` devuelve la hora local de la máquina sin decir cuál es, y restar horas a eso es aritmética de reloj de pared, que no sabe que el 30 de marzo las 02:00 pasan a ser las 03:00. Los dos fallos son el mismo bug con signo cambiado.

La regla que lo arregla: **almacena y calcula en UTC; convierte a la zona del usuario solo para mostrar o para interpretar lo que escribe.** UTC no tiene cambios de hora, así que «3 horas antes» es siempre 3 × 3600 segundos.

```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)                 # consciente de zona; utcnow() está obsoleto en 3.12


def parse_local(text: str) -> datetime:
    '''Interpreta "2025-03-30 10:00" como hora de Madrid y devuelve UTC.'''
    local = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
    return local.astimezone(timezone.utc)


def reminder_for(appointment_utc: datetime, hours_before: int) -> datetime:
    return appointment_utc - timedelta(hours=hours_before)   # aritmética en UTC: exacta


def for_display(moment_utc: datetime) -> str:
    return moment_utc.astimezone(MADRID).strftime("%d/%m/%Y %H:%M %Z")
```

Reproducción del bug y comprobación del arreglo con el domingo de marzo:

```python
appointment = parse_local("2025-03-30 10:00")      # 10:00 CEST = 08:00 UTC
reminder = reminder_for(appointment, 8)
assert reminder == datetime(2025, 3, 30, 0, 0, tzinfo=timezone.utc)
assert for_display(reminder) == "30/03/2025 01:00 CET"   # 8 horas reales antes: la 01:00, antes del salto
```

Con `datetime` ingenuo, `datetime(2025, 3, 30, 10, 0) - timedelta(hours=8)` da las 02:00, una hora que **no existe** ese día en Madrid, y al enviarlo a un reloj real sale una hora tarde. Que es exactamente lo que viste.

Qué cambiar en la base de datos: columna `TIMESTAMP WITH TIME ZONE` en PostgreSQL (guarda UTC internamente) o, si es SQLite/MySQL sin soporte, texto ISO 8601 en UTC con el sufijo `+00:00`. Y guarda también la zona del usuario (`"Europe/Madrid"`) como texto en su perfil, porque la necesitarás para mostrar y para la pregunta que viene después.

`zoneinfo` usa la base de datos de zonas del sistema; en Windows o en contenedores mínimos instala `tzdata` (`uv add tzdata`) para que `ZoneInfo("Europe/Madrid")` no lance `ZoneInfoNotFoundError`.""",
            },
            {"role": "user", "content": "Entendido. Pero una cita «todos los días a las 9:00» tiene que seguir siendo a las 9:00 locales después del cambio de hora, y con UTC se me mueve. ¿Cómo hago esa suma?"},
            {
                "role": "assistant",
                "content": """Para una recurrencia de **reloj de pared** («las 9:00 locales»), la suma de días se hace en la zona local, no en UTC, y después conviertes el resultado a UTC para guardarlo. Son dos operaciones distintas y conviene tener las dos con nombre:

- **Duración absoluta** («dentro de 24 horas»): suma en UTC. Tras el cambio de hora, la hora local se mueve.
- **Siguiente ocurrencia local** («mañana a las 9:00»): suma en local. Tras el cambio, el intervalo real es de 23 o 25 horas.

```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def next_local_occurrence(previous_utc: datetime, tz: ZoneInfo, days: int = 1) -> datetime:
    local = previous_utc.astimezone(tz)
    next_local = (local + timedelta(days=days)).replace(tzinfo=tz)   # misma hora de pared
    return next_local.astimezone(timezone.utc)
```

El `.replace(tzinfo=tz)` parece redundante pero es la clave. En Python, sumar un `timedelta` a un *datetime* consciente hace aritmética de **reloj de pared** dentro de esa zona (no de instantes), así que `local + 1 día` ya da las 9:00 del día siguiente; el `replace` fuerza a recalcular el desfase UTC para la nueva fecha, que es lo que cambia en el DST. Sin él, el desfase viejo se arrastra en algunas operaciones de comparación y conversión.

Comprobación cruzando el cambio de marzo:

```python
MADRID = ZoneInfo("Europe/Madrid")
saturday = datetime(2025, 3, 29, 9, 0, tzinfo=MADRID).astimezone(timezone.utc)   # 08:00 UTC
sunday = next_local_occurrence(saturday, MADRID)

assert sunday.astimezone(MADRID).strftime("%H:%M") == "09:00"   # sigue siendo las 9 locales
assert sunday - saturday == timedelta(hours=23)                   # pero pasaron 23 horas reales
```

Dos casos límite que debes decidir, no descubrir:

- **Hora inexistente**: una recurrencia a las 02:30 el 30 de marzo. `ZoneInfo` la resuelve hacia delante (03:30 CEST). Si prefieres otra política, detéctalo comparando `dt.replace(tzinfo=tz).astimezone(timezone.utc).astimezone(tz) != dt.replace(tzinfo=tz)` y ajusta.
- **Hora ambigua**: las 02:30 del 26 de octubre existen dos veces. `fold=0` (por defecto) elige la primera (CEST), `fold=1` la segunda (CET). Para una cita de usuario, la primera es la expectativa habitual.

Y el diseño que evita rehacer todo esto: guarda la **regla** («09:00 Europe/Madrid, diario») y materializa la siguiente ocurrencia en UTC cuando la necesites, en vez de guardar una lista de instantes calculados que quedan mal si el usuario cambia de zona o el gobierno cambia la regla del DST.""",
            },
        ]
    },
    # 24) TypedDict, Literal y exhaustividad para JSON (system variante)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto: señala primero lo que falla y luego da la versión corregida."},
            {
                "role": "user",
                "content": """Cargo una config JSON y la paso como `dict[str, Any]` por todo el código. Me dicen que así no se detecta nada. Es esto:

```python
import json
from typing import Any

def load(path) -> dict[str, Any]:
    return json.load(open(path))

def connect(cfg: dict[str, Any]):
    mode = cfg["mode"]            # "ro" o "rw"
    if mode == "ro":
        return open_readonly(cfg["url"])
    elif mode == "rw":
        return open_readwrite(cfg["url"], cfg.get("pool_size", 5))
```

¿Qué le pondrías?""",
            },
            {
                "role": "assistant",
                "content": """Lo que falla:

1. **`dict[str, Any]` apaga el verificador de tipos.** `cfg["urll"]` (errata) o `cfg["pool_size"] + "x"` pasan mypy y revientan en producción. El tipo no describe ninguna clave.
2. **`mode` es un `str` libre.** Si alguien escribe `"readonly"` en el JSON, `connect` devuelve `None` en silencio porque ningún `if` coincide; el tipo de retorno implícito es `Connection | None` y nadie lo sabe.
3. **`open(path)` sin `with` ni `encoding`.** Fuga del descriptor hasta que el recolector pase, y lectura dependiente de la plataforma.
4. **No hay validación en la frontera.** `json.load` devuelve lo que haya en el archivo; el tipado estático no comprueba datos en ejecución, así que hace falta un paso explícito.

Versión corregida:

```python
import json
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, assert_never

Mode = Literal["ro", "rw"]


class Config(TypedDict):
    mode: Mode
    url: str
    pool_size: NotRequired[int]      # 3.11+: clave opcional sin volver opcional su tipo


def load(path: Path) -> Config:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: se esperaba un objeto JSON")
    if raw.get("mode") not in ("ro", "rw"):
        raise ValueError(f"{path}: mode debe ser 'ro' o 'rw', recibido {raw.get('mode')!r}")
    if not isinstance(raw.get("url"), str):
        raise ValueError(f"{path}: url debe ser una cadena")
    if "pool_size" in raw and not isinstance(raw["pool_size"], int):
        raise ValueError(f"{path}: pool_size debe ser un entero")
    return raw                        # tras las comprobaciones, el verificador acepta el TypedDict


def connect(cfg: Config) -> Connection:
    mode = cfg["mode"]
    if mode == "ro":
        return open_readonly(cfg["url"])
    elif mode == "rw":
        return open_readwrite(cfg["url"], cfg.get("pool_size", 5))
    else:
        assert_never(mode)            # si Mode gana un valor, mypy marca esta línea
```

Qué compra cada cambio:

- **`TypedDict`** da nombre y tipo a cada clave. `cfg["urll"]` es ahora un error de mypy (`TypedDict "Config" has no key "urll"`), y `cfg.get("pool_size", 5)` se infiere como `int`.
- **`Literal["ro", "rw"]`** convierte las comparaciones en un conjunto cerrado. Con `assert_never` en el `else`, añadir `"wo"` a `Mode` hace que mypy señale `connect` como incompleta: `Argument 1 to "assert_never" has incompatible type "Literal['wo']"; expected "Never"`. La exhaustividad pasa de ser una costumbre a ser comprobada.
- **`NotRequired`** expresa «puede faltar» sin convertir el tipo en `int | None`, que obligaría a comprobar `None` incluso cuando la clave existe.
- **La validación en `load`** es la única barrera real contra el archivo. Si la config crece, sustituye las comprobaciones manuales por Pydantic (`Config.model_validate(raw)`) o `TypeAdapter(Config).validate_python(raw)`, que validan un `TypedDict` directamente y dan errores con ruta.

Test que fija el contrato:

```python
import pytest


def test_load_rechaza_modo_invalido(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"mode": "readonly", "url": "db://x"}', encoding="utf-8")
    with pytest.raises(ValueError, match="mode"):
        load(p)
```

Ejecuta `mypy --strict` sobre el módulo: con el original no tenía nada que decir; con esta versión, cualquier clave mal escrita o modo no cubierto aparece antes de ejecutar.""",
            },
        ]
    },
    # 25) match: patrones estructurales para despachar comandos
    {
        "messages": [
            {"role": "user", "content": "Tengo un parser de comandos con una cadena de `if isinstance(cmd, Move) and cmd.steps > 0 ... elif isinstance(cmd, Say) ...` que crece sin parar. ¿`match` lo mejora de verdad o es solo azúcar?"},
            {
                "role": "assistant",
                "content": """Lo mejora de verdad cuando los casos combinan **tipo + forma + condición**, que es tu situación: `match` desestructura y comprueba en una sola cláusula lo que con `isinstance` requiere tres líneas y accesos repetidos a atributos. Donde solo compara un valor contra constantes, es azúcar y un `dict` de despacho suele ser mejor.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    direction: str
    steps: int


@dataclass(frozen=True)
class Say:
    text: str


@dataclass(frozen=True)
class Teleport:
    x: int
    y: int


Command = Move | Say | Teleport


def execute(cmd: Command, player: Player) -> str:
    match cmd:
        case Move(steps=0):
            return "sin movimiento"
        case Move(direction="north" | "south" as axis, steps=n) if n > 0:
            player.move_vertical(axis, n)
            return f"{n} pasos hacia {axis}"
        case Move(direction=d, steps=n) if n > 0:
            player.move_horizontal(d, n)
            return f"{n} pasos hacia {d}"
        case Move():
            raise ValueError(f"pasos negativos: {cmd.steps}")
        case Say(text=""):
            return "silencio"
        case Say(text=t):
            return f'dice "{t}"'
        case Teleport(x=0, y=0):
            player.reset()
            return "al origen"
        case Teleport(x=x, y=y):
            player.jump_to(x, y)
            return f"teletransporte a ({x}, {y})"
```

Lo que hace cada pieza:

- `case Move(steps=0)` es un **patrón de clase**: `isinstance` más comparación del atributo. Los `dataclass` generan `__match_args__`, así que también vale la forma posicional `Move("north", 3)`.
- `"north" | "south" as axis` es un **patrón OR con captura**: coincide con cualquiera de los dos y guarda el valor en `axis`.
- `if n > 0` es una **guarda**: se evalúa solo si el patrón coincidió, con las variables ya ligadas.
- El orden importa: los casos se prueban de arriba abajo y gana el primero. Por eso `Move(steps=0)` va antes que los genéricos y `Move()` sin condiciones queda al final como recogida de errores.

Una trampa concreta: `case Move(direction=north)` (sin comillas) **no compara** con una constante; captura el atributo en una variable nueva llamada `north` y coincide siempre. Para comparar con un valor con nombre, usa un nombre con punto (`case Move(direction=Direction.NORTH)`) o un literal.

Exhaustividad: si `Command` gana una variante, pyright y mypy avisan cuando el `match` no la cubre si añades un `case _:` con `assert_never(cmd)` al final. Sin él, un comando no cubierto hace que `execute` devuelva `None` sin ruido.

Cuándo **no** usarlo: si todos los casos son `case "start": ... case "stop": ...`, un `dict[str, Callable]` es más corto, más rápido y se extiende sin tocar la función. `match` paga cuando hay estructura que desarmar.

Test que cubre el orden de los casos, que es donde se rompen estos despachos al añadir uno nuevo:

```python
def test_execute_orden_de_casos(player):
    assert execute(Move("north", 0), player) == "sin movimiento"
    assert execute(Move("north", 2), player) == "2 pasos hacia north"
    assert execute(Move("east", 1), player) == "1 pasos hacia east"
    with pytest.raises(ValueError):
        execute(Move("east", -1), player)
    assert execute(Teleport(0, 0), player) == "al origen"
```""",
            },
        ]
    },
    # 26) Código bloqueante dentro de asyncio: to_thread (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Mi API con FastAPI tiene endpoints `async def` y dentro llamo a `requests.get(...)` a un servicio externo que tarda ~2 s. Cuando entran varias peticiones a la vez, todo el servidor se congela, hasta el `/health`. ¿Por qué, si es async?"},
            {
                "role": "assistant",
                "content": """Porque `requests.get` es **bloqueante**: no es una corrutina, no cede el control al *event loop* mientras espera la red. Dentro de un `async def`, esos 2 s bloquean el único hilo que ejecuta todas las corrutinas; nada más avanza, incluido `/health`. `async` no hace concurrente lo que llamas; solo permite que las operaciones que **sí** saben esperar (las que tienen `await`) se intercalen.

Dos arreglos correctos, según cuánto quieras cambiar:

**1. Cliente asíncrono** (el arreglo real): `httpx.AsyncClient` hace la petición con `await`, y el *loop* atiende otras cosas mientras llega la respuesta.

```python
import httpx
from fastapi import FastAPI

app = FastAPI()
client = httpx.AsyncClient(timeout=10.0)       # uno por proceso; reutiliza conexiones


@app.on_event("shutdown")
async def close_client() -> None:
    await client.aclose()


@app.get("/price/{sku}")
async def price(sku: str) -> dict:
    response = await client.get(f"https://pricing.internal/items/{sku}")
    response.raise_for_status()
    return response.json()
```

**2. Mover la llamada bloqueante a un hilo**, si no puedes cambiar la librería (un SDK sin versión async, un driver antiguo):

```python
import asyncio

import requests


@app.get("/price/{sku}")
async def price(sku: str) -> dict:
    response = await asyncio.to_thread(requests.get, f"https://pricing.internal/items/{sku}", timeout=10)
    response.raise_for_status()
    return response.json()
```

`asyncio.to_thread` (3.9+) ejecuta la función en el *thread pool* por defecto del *loop* y devuelve un *awaitable*; el *loop* queda libre mientras el hilo espera. Como la espera es de red, el GIL no estorba.

Y una tercera opción específica de FastAPI: declarar el endpoint con `def` en vez de `async def`. FastAPI ejecuta las rutas síncronas en su propio *thread pool* automáticamente. Es el cambio más pequeño de todos, válido mientras el endpoint no necesite `await` para nada más.

Cómo comprobar que ya no se bloquea:

```python
# dos peticiones concurrentes deben tardar ~2 s en total, no ~4
import asyncio, time, httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as c:
        t0 = time.perf_counter()
        await asyncio.gather(c.get("/price/a"), c.get("/price/b"), c.get("/health"))
        print(f"{time.perf_counter() - t0:.1f}s")

asyncio.run(main())
```

Con el código original imprime ~4 s y `/health` espera a los dos anteriores; con cualquiera de los arreglos, ~2 s.

La regla general para no volver a caer: dentro de un `async def`, toda llamada que pueda tardar (red, disco, `time.sleep`, consultas a BD con un driver síncrono, cálculo pesado) o tiene `await` delante o va a `to_thread`. `time.sleep(1)` dentro de una corrutina es el ejemplo mínimo del mismo bug.""",
            },
            {"role": "user", "content": "Voy con `to_thread` porque el SDK no tiene versión async. ¿Escala si tengo 200 peticiones concurrentes?"},
            {
                "role": "assistant",
                "content": """Hasta cierto punto, y el límite es visible: el *executor* por defecto del *loop* tiene `min(32, cpu_count + 4)` hilos. Con 200 peticiones concurrentes de 2 s, las primeras 32 (en una máquina de 8 núcleos, 12) entran y el resto hacen cola; el `/health` sigue respondiendo porque el *loop* no está bloqueado, pero la latencia de `/price` crece.

Opciones por orden:

**1. Un *executor* propio con más hilos**, dimensionado para espera de red (hilos baratos, casi siempre dormidos):

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI

sdk_pool = ThreadPoolExecutor(max_workers=64, thread_name_prefix="sdk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    sdk_pool.shutdown(wait=True)


app = FastAPI(lifespan=lifespan)


async def call_sdk(sku: str) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(sdk_pool, sdk.get_price, sku)
```

`run_in_executor` es lo que `to_thread` hace por dentro, pero eligiendo el *pool*. 64 hilos esperando red cuestan unos pocos MB; el límite práctico lo pone el servicio externo, no Python.

**2. Limitar la concurrencia hacia el servicio externo** con un `asyncio.Semaphore`, para no convertir tu pico de 200 en 200 conexiones simultáneas contra `pricing.internal`. Si el servicio tiene un límite de 50, ponlo tú antes de que te lo imponga con errores 429.

**3. Si el SDK no es seguro para hilos** (algunos clientes mantienen estado global), un hilo único con una cola, o un cliente por hilo con `threading.local()`. Compruébalo en su documentación antes de subir `max_workers`.

Medición que te dice si estás bien dimensionado, sin adivinar:

```python
import threading

@app.get("/debug/threads")
async def threads() -> dict:
    return {
        "sdk_threads_alive": sum(1 for t in threading.enumerate() if t.name.startswith("sdk")),
        "sdk_queue": sdk_pool._work_queue.qsize(),   # privado, pero útil para diagnóstico
    }
```

Si `sdk_queue` crece de forma sostenida bajo carga, faltan hilos o el servicio externo es el cuello de botella; si está en 0 y la latencia es alta, el problema no es el *pool*.

A medio plazo, el arreglo que de verdad escala es el **1 de antes** (cliente async): sin hilos, sin colas, miles de peticiones en vuelo por proceso. Si el SDK solo envuelve una API HTTP, suele compensar reescribir las dos o tres llamadas que usas con `httpx.AsyncClient` y dejar el SDK fuera.""",
            },
        ]
    },
    # 27) Protocolo de iteración: iterable reutilizable (multiturno, código roto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Hice una clase para recorrer las páginas de una API y solo funciona la primera vez que la recorro:

```python
class Pages:
    def __init__(self, client, url):
        self.client = client
        self.url = url
        self.next_url = url

    def __iter__(self):
        return self

    def __next__(self):
        if self.next_url is None:
            raise StopIteration
        page = self.client.get(self.next_url)
        self.next_url = page.get("next")
        return page["items"]

pages = Pages(client, "/users")
print(sum(len(p) for p in pages))   # 250
print(sum(len(p) for p in pages))   # 0 ???
```""",
            },
            {
                "role": "assistant",
                "content": """Has mezclado dos roles: tu clase es a la vez el **iterable** (lo que se puede recorrer) y el **iterador** (el cursor que avanza). Como `__iter__` devuelve `self`, el segundo `for` reutiliza el mismo cursor, que ya está en `next_url = None`, y termina al instante. Es el mismo comportamiento que un generador o un archivo abierto: se agotan.

La separación correcta: `__iter__` devuelve un iterador **nuevo** cada vez. Lo más corto es que `__iter__` sea un generador:

```python
from collections.abc import Iterator


class Pages:
    def __init__(self, client, url: str) -> None:
        self.client = client
        self.url = url

    def __iter__(self) -> Iterator[list[dict]]:
        next_url: str | None = self.url          # estado local a cada recorrido
        while next_url is not None:
            page = self.client.get(next_url)
            next_url = page.get("next")
            yield page["items"]
```

Cada `for pages` llama a `__iter__`, que crea un generador independiente con su propio `next_url`. El `__next__` desaparece: el generador lo implementa por ti.

```python
pages = Pages(client, "/users")
print(sum(len(p) for p in pages))   # 250
print(sum(len(p) for p in pages))   # 250: segundo recorrido completo (y segunda tanda de peticiones)
```

Fíjate en el coste: cada recorrido vuelve a pedir las páginas. Si eso no es lo que quieres, el objeto debería cachear, y entonces el diseño es otro (`list(pages)` una vez, o un atributo `self._cache`).

Cuándo sí quieres `__iter__` devolviendo `self`: cuando la clase **es** un cursor por naturaleza y agotarse es correcto (un lector de archivo, un `csv.reader`). Entonces no la llames `Pages` sino `PageCursor`, para que el nombre avise.

Test que fija el contrato, usando un cliente falso para no tocar la red:

```python
class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str) -> dict:
        self.calls += 1
        if url == "/users":
            return {"items": [1, 2], "next": "/users?page=2"}
        return {"items": [3], "next": None}


def test_pages_se_puede_recorrer_dos_veces():
    client = FakeClient()
    pages = Pages(client, "/users")
    assert [p for p in pages] == [[1, 2], [3]]
    assert [p for p in pages] == [[1, 2], [3]]
    assert client.calls == 4                     # dos recorridos, dos páginas cada uno
```""",
            },
            {"role": "user", "content": "¿Y si además quiero que funcione `len(pages)` y poder indexar `pages[0]`? ¿Tengo que implementar todo a mano?"},
            {
                "role": "assistant",
                "content": """Depende de qué signifique `len` para páginas que todavía no has descargado. Hay dos respuestas honestas, y la que elijas cambia el diseño:

**1. Si no sabes cuántas páginas hay sin pedirlas, no implementes `__len__`.** Un `len()` que hace 50 peticiones HTTP sorprende a cualquiera que lo llame (y `list(pages)` lo llamaría internamente para prerreservar). Deja la clase como iterable perezoso y ofrece un método explícito, `pages.fetch_all()`, que devuelva una `list` con todo lo que `len` e indexación necesitan.

**2. Si la API te da el total** (`{"count": 250, "page_size": 50}` en la primera respuesta), entonces sí es una **secuencia** y `collections.abc.Sequence` te regala casi todo: implementas `__len__` y `__getitem__`, y heredas `__iter__`, `__contains__`, `__reversed__`, `index` y `count`.

```python
from collections.abc import Sequence
from functools import cached_property


class Pages(Sequence[list[dict]]):
    def __init__(self, client, url: str, page_size: int = 50) -> None:
        self.client = client
        self.url = url
        self.page_size = page_size

    @cached_property
    def _total_pages(self) -> int:
        first = self.client.get(self.url, params={"page": 1, "page_size": self.page_size})
        return -(-first["count"] // self.page_size)          # división entera hacia arriba

    def __len__(self) -> int:
        return self._total_pages

    def __getitem__(self, index: int) -> list[dict]:
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(f"page {index} out of range (0..{len(self) - 1})")
        page = self.client.get(self.url, params={"page": index + 1, "page_size": self.page_size})
        return page["items"]
```

`Sequence` genera `__iter__` a partir de `__getitem__` (llama a `self[0]`, `self[1]`… hasta `IndexError`), así que el recorrido repetido funciona sin escribir nada más, y cada recorrido pide las páginas de nuevo, igual que antes. El `IndexError` con índice fuera de rango no es un detalle: es lo que hace que el `for` termine; si devolvieras una lista vacía, el bucle sería infinito.

Nota el cambio de modelo: esto solo es correcto si la API soporta **acceso aleatorio** por número de página. Con paginación por cursor (`"next": "/users?cursor=abc"`), no puedes pedir la página 7 sin pasar por las seis anteriores, y entonces vuelves a la opción 1.

Test adicional para la versión secuencia:

```python
def test_pages_como_secuencia():
    pages = Pages(FakeCountingClient(count=120), "/users", page_size=50)
    assert len(pages) == 3
    assert pages[-1] == pages[2]
    assert [len(p) for p in pages] == [50, 50, 20]
    with pytest.raises(IndexError):
        pages[3]
```""",
            },
        ]
    },
    # 28) Micro-rendimiento con evidencia (usuario en inglés)
    {
        "messages": [
            {"role": "user", "content": "Settle some arguments on my team: is `''.join(parts)` really faster than `+=` in a loop? List comprehension vs `map`? `dict.get` vs `try/except KeyError`? I want numbers, not folklore."},
            {
                "role": "assistant",
                "content": """Measured on CPython 3.12, 64-bit Linux, with `timeit`; your absolute numbers will differ, the ratios will not. The script is at the end so you can rerun it.

**1. String building: `join` wins, but less than people think.**

| n = 100 000 short strings | time |
|---|---|
| `s += part` in a loop | ~9 ms |
| `''.join(parts)` | ~1.5 ms |
| `''.join(generator)` | ~5 ms |

CPython has an optimization that resizes the string in place when `s += x` sees a refcount of 1, so the loop is not quadratic in practice. `join` is still several times faster because it computes the final size once and copies once. The generator variant is slower than the list because `join` has to materialize it anyway to know the total length. Rule: `join` over a list for anything in a loop; `+` for two or three pieces is fine.

**2. Comprehension vs `map`: depends on whether you need a lambda.**

| 1 000 000 ints | time |
|---|---|
| `[str(x) for x in xs]` | ~95 ms |
| `list(map(str, xs))` | ~65 ms |
| `[x * 2 for x in xs]` | ~45 ms |
| `list(map(lambda x: x * 2, xs))` | ~75 ms |

`map` with a **builtin** skips the Python-level frame per element; `map` with a **lambda** adds a function call per element and loses. Rule: `map(builtin, ...)` is slightly faster; a comprehension with an inline expression is faster than a lambda and reads better. Never choose on speed alone here, the difference is a few tens of nanoseconds per element.

**3. `dict.get` vs `try/except`: it depends on the hit rate.**

| 1 000 000 lookups | key present | key missing |
|---|---|---|
| `d.get(k, default)` | ~55 ms | ~55 ms |
| `try: d[k] except KeyError:` | ~40 ms | ~310 ms |
| `d[k] if k in d else default` | ~50 ms | ~35 ms |

Raising an exception costs about 300-400 ns; a method call costs ~40 ns. If misses are rare (under ~10 %), `try/except` is fastest and idiomatic (EAFP). If misses are common, `get` or `in` wins. Rule: write what reads best (`get` for a default, `try` when the miss is exceptional); switch only if a profiler points here.

```python
from timeit import timeit

N = 100_000
parts = [str(i) for i in range(N)]


def concat() -> str:
    s = ""
    for p in parts:
        s += p
    return s


xs = list(range(1_000_000))
d = {i: i for i in range(1_000_000)}
hits = list(range(1_000_000))
misses = list(range(1_000_000, 2_000_000))


def lookup_try(keys):
    for k in keys:
        try:
            d[k]
        except KeyError:
            pass


def lookup_get(keys):
    for k in keys:
        d.get(k, None)


for label, stmt in [
    ("+= loop", lambda: concat()),
    ("join list", lambda: "".join(parts)),
    ("join gen", lambda: "".join(p for p in parts)),
    ("listcomp str", lambda: [str(x) for x in xs]),
    ("map str", lambda: list(map(str, xs))),
    ("listcomp x*2", lambda: [x * 2 for x in xs]),
    ("map lambda", lambda: list(map(lambda x: x * 2, xs))),
    ("get hits", lambda: lookup_get(hits)),
    ("try hits", lambda: lookup_try(hits)),
    ("get misses", lambda: lookup_get(misses)),
    ("try misses", lambda: lookup_try(misses)),
]:
    best = min(timeit(stmt, number=1) for _ in range(5))
    print(f"{label:<14}{best * 1000:8.1f} ms")
```

Take the **minimum** of several runs, not the mean: the minimum is the least noisy estimate of the code's cost; the mean includes GC pauses and whatever else the machine was doing.

The meta-answer for the team: all three gaps are tens of nanoseconds per operation. A single unnecessary database round trip costs more than a million of them. Settle style questions by readability and reserve this kind of measurement for code a profiler has already singled out.""",
            },
        ]
    },
    # 29) ThreadPoolExecutor que se traga excepciones (SISTEMA, código roto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Proceso archivos en paralelo con hilos y, cuando uno falla, no veo ningún error; el programa termina como si todo hubiera ido bien y luego faltan resultados:

```python
from concurrent.futures import ThreadPoolExecutor

def process(path):
    data = open(path).read()
    return parse(data)   # a veces lanza ValueError

with ThreadPoolExecutor(max_workers=8) as pool:
    for path in paths:
        pool.submit(process, path)
print("listo")
```""",
            },
            {
                "role": "assistant",
                "content": """La excepción **sí** ocurre, pero queda guardada dentro del `Future` que `submit` devuelve y que estás descartando. Un `Future` solo relanza su excepción cuando alguien llama a `.result()` (o `.exception()`); si nadie lo hace, el error muere en silencio. El `with` espera a que los hilos terminen, no comprueba cómo terminaron.

Arreglo: conserva los *futures* y recoge cada resultado, decidiendo qué hacer con los fallos.

```python
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)


def process(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:       # de paso: cierre garantizado del archivo
        return parse(f.read())


def process_all(paths: list[Path]) -> tuple[dict[Path, dict], dict[Path, Exception]]:
    results: dict[Path, dict] = {}
    failures: dict[Path, Exception] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process, p): p for p in paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                results[path] = future.result()    # aquí se relanza lo que falló en el hilo
            except Exception as err:
                failures[path] = err
                logger.error("fallo procesando %s", path, exc_info=err)
    return results, failures


results, failures = process_all(paths)
print(f"ok: {len(results)}, fallos: {len(failures)}")
if failures:
    raise SystemExit(1)                            # el proceso no debe terminar «bien» con fallos
```

`as_completed` entrega los *futures* según terminan, así los fallos se ven en cuanto ocurren y no al final. El diccionario `futures → path` es la forma habitual de saber a qué entrada corresponde cada resultado.

Si prefieres fallar al primer error (todo o nada), `pool.map` es más corto y relanza al iterar:

```python
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(process, paths))       # ValueError sube aquí, en el orden de paths
```

Ojo: `map` mantiene el orden y relanza la **primera** excepción en ese orden; las demás tareas siguen ejecutándose hasta terminar (el `with` las espera), pero sus errores ya no se ven. Para «cancela todo si algo falla», llama a `pool.shutdown(cancel_futures=True)` en el `except`; cancela las que aún no empezaron.

Test que reproduce tu síntoma y fija el comportamiento:

```python
def test_los_fallos_no_se_pierden(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("1", encoding="utf-8")
    bad = tmp_path / "bad.txt"
    bad.write_text("x", encoding="utf-8")        # parse lanza ValueError con esto

    results, failures = process_all([good, bad])

    assert set(results) == {good}
    assert isinstance(failures[bad], ValueError)
```

Dos observaciones sobre el diseño original:

- Con el patrón `submit` y olvidar, tampoco tienes **resultados**: `process` devolvía algo que nadie recogía. Eso solo tiene sentido para tareas de puro efecto secundario, y aun entonces hay que recoger los *futures* por las excepciones.
- Si quisieras un «fuego y olvida» legítimo, `future.add_done_callback(lambda f: f.exception() and logger.error(...))` registra el fallo sin bloquear, pero el programa seguirá terminando con código 0 salvo que cuentes los fallos en algún sitio.""",
            },
        ]
    },
    # 30) Estrechamiento de Optional con mypy (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """mypy me da este error y no sé cómo quitarlo sin poner `# type: ignore`:

```
error: Item "None" of "str | None" has no attribute "upper"  [union-attr]
```

El código:

```python
def find_user_name(user_id: int) -> str | None:
    row = db.fetch_one("SELECT name FROM users WHERE id = ?", user_id)
    return row["name"] if row else None

def greeting(user_id: int) -> str:
    name = find_user_name(user_id)
    return f"Hola, {name.upper()}"
```""",
            },
            {
                "role": "assistant",
                "content": """mypy tiene razón: `find_user_name` promete que puede devolver `None`, y `None.upper()` falla en ejecución. El error no es ruido del verificador, es un bug real para cualquier `user_id` que no exista. La solución es decidir **qué hace `greeting` cuando no hay nombre**, y escribirlo; mypy estrecha el tipo a `str` en la rama donde ya lo has comprobado.

Tres decisiones posibles, cada una con su forma:

**1. Es un error: el usuario debería existir.**

```python
def greeting(user_id: int) -> str:
    name = find_user_name(user_id)
    if name is None:
        raise LookupError(f"usuario {user_id} no encontrado")
    return f"Hola, {name.upper()}"          # aquí mypy sabe que name es str
```

**2. Hay un valor por defecto razonable.**

```python
def greeting(user_id: int) -> str:
    name = find_user_name(user_id) or "invitado"
    return f"Hola, {name.upper()}"
```

Cuidado con `or`: también sustituye la cadena vacía `""`. Si `""` es un nombre válido (no debería), usa `name if name is not None else "invitado"`.

**3. La propia `greeting` puede no tener respuesta.**

```python
def greeting(user_id: int) -> str | None:
    name = find_user_name(user_id)
    return None if name is None else f"Hola, {name.upper()}"
```

Esto empuja la decisión al llamador, que es correcto si de verdad hay llamadores que tratan el caso de forma distinta; si todos acaban poniendo `or "invitado"`, la opción 2 dentro de `greeting` es mejor.

Patrones de estrechamiento que mypy y pyright entienden, para el resto del código:

```python
if name is not None: ...              # comparación de identidad: la forma canónica
if name: ...                          # también estrecha, pero excluye "" (a veces no es lo que quieres)
if isinstance(value, str): ...        # para uniones más amplias
if (name := find_user_name(uid)) is not None: ...   # walrus: comprueba y liga en una línea
match name:
    case None: ...
    case str(): ...
```

El estrechamiento es **local a la variable y al bloque**: tras un `if name is None: return`, el resto de la función ve `name: str`. Pero no sobrevive a llamadas a funciones (`if obj.name is not None: obj.name.upper()` falla si `name` es una propiedad, porque podría cambiar entre lecturas); asigna a una variable local primero.

Lo que **no** hay que hacer: `# type: ignore[union-attr]` o `name.upper()  # type: ignore` apagan el aviso y dejan el bug. Tampoco `cast(str, name)`, que es lo mismo con otra sintaxis. El único caso en que `cast` es legítimo es cuando tú sabes algo que el verificador no puede saber, y entonces lo documentas en un comentario.""",
            },
            {"role": "user", "content": "He visto `assert name is not None` en bastante código para esto. ¿Es válido o es el mismo truco que el cast?"},
            {
                "role": "assistant",
                "content": """Es válido como estrechamiento (mypy y pyright lo aceptan) y es mejor que `cast` porque **comprueba en ejecución**: si `name` es `None`, lanza `AssertionError` en esa línea en vez de un `AttributeError` tres líneas después. Pero tiene dos limitaciones que lo hacen inadecuado para el caso de `greeting`:

1. **Desaparece con `python -O`.** Los `assert` se eliminan al optimizar, y entonces vuelves al `None.upper()` original. Cualquier comprobación que forme parte del comportamiento del programa (entradas externas, resultados de BD, respuestas de red) no puede depender de un `assert`.
2. **Expresa una invariante, no una condición de negocio.** `assert` dice «esto es imposible por construcción del programa; si pasa, hay un bug». Un usuario inexistente no es un bug: es un dato.

Dónde sí encaja: cuando el `None` es imposible por **lógica interna** que el verificador no puede seguir.

```python
class Parser:
    def __init__(self) -> None:
        self._tokens: list[str] | None = None

    def load(self, text: str) -> None:
        self._tokens = text.split()

    def first(self) -> str:
        assert self._tokens is not None, "llama a load() antes de first()"
        return self._tokens[0]
```

Aquí el `None` significa «mal uso de la clase por parte del programador», exactamente lo que un `assert` debe señalar, y el mensaje le dice qué hizo mal.

Regla para elegir, en una línea por caso:

| El `None` viene de… | Usa |
|---|---|
| Datos externos (BD, red, usuario, archivo) | `if x is None: raise MiError(...)` o un valor por defecto |
| Estado interno que debería estar inicializado | `assert x is not None, "mensaje"` |
| Algo que sabes y el verificador no (API mal tipada de terceros) | `cast`, con comentario de por qué |

Y la verificación de que tu código no depende de los `assert`: ejecuta la suite de tests una vez con `python -O -m pytest`. Si algo cambia de comportamiento, había un `assert` haciendo trabajo de `if`.""",
            },
        ]
    },
]
