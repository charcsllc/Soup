"""Fundamentos de algoritmos y estructuras de datos (agnóstico del lenguaje).

30 filas. Código en Python, JavaScript, Go, Rust y C según convenga. Temas: complejidad
real vs teórica, recursión e iteración, pilas/colas/heaps, hash maps, árboles y grafos,
Dijkstra, DP, two pointers, ventana deslizante, búsqueda binaria, ordenación estable,
invariantes, pruebas por propiedades, desbordamiento, aleatoriedad, unión-búsqueda,
tries y manipulación de bits.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = []

ROWS += [
    # 1) Complejidad real vs teórica
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Implementé merge sort en Python y para listas de 50 elementos es más lento que un bubble sort que escribí en clase. ¿No se supone que O(n log n) siempre gana a O(n²)? Estoy midiendo con time.time() alrededor de una sola llamada.",
            },
            {
                "role": "assistant",
                "content": """Sí se supone, pero solo para **n suficientemente grande**. Para 50 elementos estás midiendo las constantes que la notación O descarta, y encima las mides mal.

**Qué esconde la O.** O(n log n) significa «el tiempo crece como c₁·n·log n» y O(n²) «como c₂·n²». En Python, c₁ es grande en tu merge sort: cada nivel crea listas nuevas con *slicing*, hace `append` uno a uno y paga una llamada de función por subproblema. Bubble sort hace comparaciones e intercambios sobre la misma lista, sin asignar memoria. Con n = 50: 2500 operaciones baratas contra ~280 operaciones caras. El cruce suele estar entre 100 y 500 elementos en CPython.

**Cómo medir para verlo.** `time.time()` alrededor de una llamada de microsegundos devuelve ruido. Usa `timeit` con datos nuevos en cada repetición (si reutilizas la lista, la segunda vez ya está ordenada y bubble sort con salida temprana se vuelve O(n)):

```python
import random
import timeit


def bubble_sort(items: list[int]) -> list[int]:
    data = items[:]
    n = len(data)
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            if data[j] > data[j + 1]:
                data[j], data[j + 1] = data[j + 1], data[j]
                swapped = True
        if not swapped:  # salida temprana: lista ya ordenada
            break
    return data


def merge_sort(items: list[int]) -> list[int]:
    if len(items) <= 1:
        return items[:]
    mid = len(items) // 2
    left, right = merge_sort(items[:mid]), merge_sort(items[mid:])
    merged, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i]); i += 1
        else:
            merged.append(right[j]); j += 1
    merged.extend(left[i:]); merged.extend(right[j:])
    return merged


def bench(fn, n: int, reps: int = 200) -> float:
    rng = random.Random(42)  # misma semilla: comparación justa
    total = 0.0
    for _ in range(reps):
        data = [rng.randint(0, 10**6) for _ in range(n)]
        total += timeit.timeit(lambda: fn(data), number=1)
    return total / reps


for n in (50, 200, 1000, 5000):
    print(n, f"bubble={bench(bubble_sort, n):.6f}s", f"merge={bench(merge_sort, n):.6f}s")
```

En mi máquina el resultado típico es: a n = 50 gana bubble por poco; a n = 200 ya empatan; a n = 1000 merge gana por ~5x; a n = 5000 por ~40x. Esa tabla es la respuesta a tu pregunta: la curva n² crece más deprisa y acaba perdiendo, siempre, pero el punto de cruce depende de las constantes.

**La biblioteca estándar hace lo mismo que tú observaste.** `sorted()` usa Timsort, que ordena tramos de 32-64 elementos con *inserción* (un O(n²) con constante minúscula) y solo después mezcla. Aprovechar que el algoritmo «peor» gana en tamaños pequeños es una optimización estándar, no una anomalía.

Dos reglas que salen de aquí: la notación O te dice qué algoritmo elegir cuando n puede crecer; el *benchmark* te dice cuál es más rápido para **tu** n. Y nunca saques conclusiones de una sola medida con `time.time()`.""",
            },
        ]
    },
    # 2) Recursión vs iteración (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Cuándo conviene usar recursión en vez de un bucle? Mi profesor dice que la recursión es más elegante pero en el trabajo me dicen que la evite."},
            {
                "role": "assistant",
                "content": """Los dos tienen razón en contextos distintos. La regla práctica: **recursión cuando el problema es recursivo por naturaleza** (árboles, grafos, divide y vencerás, gramáticas); **bucle cuando la recursión sería solo un contador disfrazado** (sumar una lista, recorrer un rango, acumular).

Lo que de verdad diferencia a las dos:

| | Recursión | Bucle |
|---|---|---|
| Estado | implícito en la pila de llamadas | explícito en variables |
| Límite | profundidad de pila (Python ~1000 por defecto) | solo memoria |
| Coste por paso | llamada de función (más caro en Python, barato en C/Go/Rust) | salto |
| Legibilidad | gana cuando hay varios subproblemas por paso | gana cuando hay uno |

Un ejemplo donde la recursión es claramente mejor, porque cada nodo tiene varios hijos y la pila guarda «por dónde iba» sin que lo gestiones tú:

```python
def total_size(node: dict) -> int:
    # Suma el tamaño de un árbol de ficheros: {"size": int, "children": [...]}
    return node["size"] + sum(total_size(child) for child in node.get("children", []))
```

Y uno donde la recursión es solo un bucle con sombrero, y además peligroso por la profundidad:

```python
def total(values: list[int]) -> int:          # mal: profundidad = len(values)
    return 0 if not values else values[0] + total(values[1:])

def total(values: list[int]) -> int:          # bien
    acc = 0
    for value in values:
        acc += value
    return acc
```

La versión recursiva de `total` falla con `RecursionError` a partir de ~1000 elementos y además copia la lista en cada paso (O(n²)). Eso es lo que tus compañeros quieren evitar.

Criterio para decidir en 10 segundos: si al escribir la versión iterativa necesitas una pila explícita para no perderte, la recursión es la herramienta correcta. Si la versión iterativa cabe en un `for` con una o dos variables, el bucle gana.""",
            },
            {"role": "user", "content": "¿Y la recursión de cola? Me dijeron que si pongo la llamada al final el compilador la convierte en bucle."},
            {
                "role": "assistant",
                "content": """Depende del lenguaje, y en los que más usas probablemente no.

- **Python**: no optimiza la recursión de cola, por decisión explícita (Guido quiere trazas de pila completas). Una función de cola recursiva sigue consumiendo un marco por llamada.
- **JavaScript**: la especificación ES2015 la exige, pero solo Safari la implementó. Node y Chrome no.
- **Go**: no la hace.
- **C/C++ (gcc, clang)**: la hacen con `-O2`, pero no está garantizada; un cambio inocente (un destructor, una variable cuya dirección se toma) la desactiva en silencio.
- **Rust**: no garantizada; la palabra clave `become` existe como propuesta experimental.
- **Scheme, OCaml, Elixir/Erlang, Scala (con `@tailrec`), Kotlin (`tailrec`)**: sí, y en los dos últimos el compilador te avisa si la llamada no es realmente de cola.

Así que en Python/JS/Go la forma segura es convertirla tú. Toda función de cola recursiva se transforma mecánicamente: los parámetros pasan a ser variables y la llamada se vuelve una reasignación dentro de `while True`.

```python
def gcd(a: int, b: int) -> int:          # recursión de cola
    return a if b == 0 else gcd(b, a % b)

def gcd(a: int, b: int) -> int:          # misma lógica, sin pila
    while b != 0:
        a, b = b, a % b
    return a
```

Para recursión que **no** es de cola (la llamada no es lo último, como `n * fact(n - 1)` o un recorrido con dos hijos), la transformación necesita una pila explícita, que es lo que vimos en la respuesta anterior. Si quieres saber si tu función es de cola: pregúntate si después de la llamada recursiva queda algo por hacer con su resultado. Si la respuesta es «sí», no lo es.""",
            },
        ]
    },
    # 3) Pila: paréntesis balanceados en Go (system variante, principiante)
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y un comentario breve por cada decisión importante."},
            {"role": "user", "content": "en go, función que diga si una cadena con ()[]{} está balanceada"},
            {
                "role": "assistant",
                "content": """```go
package main

import "fmt"

// IsBalanced devuelve true si cada cierre coincide con la apertura más reciente sin cerrar.
func IsBalanced(s string) bool {
	pairs := map[rune]rune{')': '(', ']': '[', '}': '{'}
	stack := make([]rune, 0, len(s)) // capacidad reservada: evita realojos en el peor caso
	for _, ch := range s {           // range sobre string itera runas, no bytes: seguro con UTF-8
		switch ch {
		case '(', '[', '{':
			stack = append(stack, ch)
		case ')', ']', '}':
			if len(stack) == 0 || stack[len(stack)-1] != pairs[ch] {
				return false // cierre sin apertura, o de tipo distinto: "(]"
			}
			stack = stack[:len(stack)-1]
		default:
			// cualquier otro carácter se ignora: "f(x) + [y]" es válido
		}
	}
	return len(stack) == 0 // aperturas sin cerrar: "((" no está balanceado
}

func main() {
	cases := map[string]bool{
		"":          true,
		"()[]{}":    true,
		"([{}])":    true,
		"(]":        false,
		"([)]":      false,
		"((":        false,
		"))":        false,
		"a(b[c]{d})": true,
	}
	for input, want := range cases {
		if got := IsBalanced(input); got != want {
			fmt.Printf("FALLO %q: got %v want %v\\n", input, got, want)
		}
	}
	fmt.Println("ok")
}
```""",
            },
        ]
    },
    # 4) Heaps: top-k (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Tengo un archivo con como un millón de palabras y necesito las 10 más frecuentes. Lo que hago es contar con un dict, pasarlo a lista de tuplas y ordenar, pero se siente desperdicio ordenar un millón de cosas para quedarme con 10."},
            {
                "role": "assistant",
                "content": """Es desperdicio, aunque pequeño: ordenar cuesta O(d log d) con d = palabras distintas (no el millón; quizá 50 000). Lo correcto para «los k mayores» es un **heap de tamaño k**: O(d log k), y con k = 10 el `log k` es prácticamente constante.

En Python no hace falta escribirlo: `heapq.nlargest` hace exactamente eso, y `Counter.most_common` lo usa por debajo cuando le pasas `n`.

```python
import heapq
import re
from collections import Counter
from pathlib import Path

WORD = re.compile(r"[a-záéíóúñü]+", re.IGNORECASE)


def top_words(path: Path, k: int = 10) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as fh:
        for line in fh:                       # línea a línea: no cargas el archivo entero
            counts.update(w.lower() for w in WORD.findall(line))
    return heapq.nlargest(k, counts.items(), key=lambda item: item[1])
```

Por qué cada pieza:

- **Contar sigue siendo O(n)** sobre el millón; no hay forma de evitarlo, pero `Counter.update` con un generador lo hace en C.
- **`nlargest`** mantiene un min-heap de k elementos: cada palabra nueva se compara con el mínimo del heap y solo entra si lo supera. Para d = 50 000 y k = 10 son ~50 000 comparaciones más unas pocas inserciones de log 10 ≈ 3 niveles.
- **Cuándo ordenar es mejor:** si k se acerca a d (quieres el 50 % superior), ordena. `nlargest` lo detecta y cambia a `sorted` cuando k ≥ d.

Comprobación rápida: `heapq.nlargest(2, [("a", 5), ("b", 9), ("c", 7)], key=lambda t: t[1])` devuelve `[("b", 9), ("c", 7)]`, ya en orden descendente.""",
            },
            {"role": "user", "content": "¿Y si las palabras llegan por un stream infinito y no me caben ni las distintas en memoria? ¿Se puede seguir sacando el top 10?"},
            {
                "role": "assistant",
                "content": """Exacto no: cualquier algoritmo que garantice el top-k exacto sobre un stream necesita memoria proporcional a las claves distintas en el peor caso (una palabra que aparece una vez por cada millón puede acabar entre las 10 primeras). Lo que sí se puede es un **top-k aproximado con memoria fija**, y en la práctica es lo que usan los sistemas de métricas.

El algoritmo más simple es **Misra-Gries** (también llamado *Frequent*): mantienes como mucho `m - 1` contadores; cuando llega una palabra sin contador y no hay hueco, decrementas **todos** los contadores en 1 y eliminas los que llegan a cero.

```python
from collections import Counter
from collections.abc import Iterable


def misra_gries(stream: Iterable[str], m: int) -> Counter[str]:
    # Garantiza: toda palabra con frecuencia > n/m acaba en el resultado.
    # Los contadores subestiman la frecuencia real como mucho en n/m.
    counters: Counter[str] = Counter()
    for word in stream:
        if word in counters:
            counters[word] += 1
        elif len(counters) < m - 1:
            counters[word] = 1
        else:
            for key in list(counters):
                counters[key] -= 1
                if counters[key] == 0:
                    del counters[key]
    return counters
```

Propiedades, para saber qué estás comprando:

- Memoria O(m), independiente del tamaño del stream.
- No produce falsos negativos para elementos «pesados» (frecuencia > n/m). Sí puede incluir candidatos que no lo son.
- Las cuentas están **subestimadas**; si necesitas el valor, haz una segunda pasada contando solo los candidatos (si el stream se puede releer) o acepta el error.

Si quieres el top 10 real entre los pesados, usa m = 100 o 1000 (mucho mayor que k) y luego `heapq.nlargest(10, counters.items(), key=...)` sobre los candidatos. Para cuentas más precisas con memoria fija, el siguiente paso es **Space-Saving** (misma idea, sustituye el contador mínimo en vez de decrementar todos) o un **Count-Min Sketch** combinado con un heap; ambos están en la librería `datasketches` si no quieres implementarlos.""",
            },
        ]
    },
    # 5) Hash maps y colisiones
    {
        "messages": [
            {"role": "user", "content": "Si dos claves distintas tienen el mismo hash, ¿el dict de Python pierde una? Y otra duda: hice una clase Punto con __eq__ y ahora no puedo usarla como clave, dice unhashable type."},
            {
                "role": "assistant",
                "content": """No pierde ninguna. Una colisión de hash solo significa que las dos claves compiten por la misma posición inicial de la tabla; el dict las distingue comparándolas con `==`. Por eso el contrato es doble: **si `a == b`, entonces `hash(a) == hash(b)`**, y el recíproco no hace falta.

**Qué pasa en una búsqueda.** CPython usa direccionamiento abierto: calcula `hash(clave)`, toma los bits bajos como índice, y si esa casilla está ocupada por otra clave (distinto hash o misma hash pero `!=`), prueba otra casilla siguiendo una secuencia determinista (*probing*). Cuando la tabla supera 2/3 de ocupación, se redimensiona para que las cadenas de sondeo sigan siendo cortas. Con un hash razonable, el coste medio es O(1); con un hash malo (todas las claves al mismo valor) degenera a O(n) por operación, y eso es exactamente el ataque *HashDoS* por el que Python aleatoriza el hash de `str` en cada proceso.

**Tu error con `Punto`.** Cuando defines `__eq__` sin `__hash__`, Python pone `__hash__ = None` a propósito: el `__hash__` heredado (basado en la identidad) rompería el contrato, porque dos puntos iguales tendrían hashes distintos. Tienes que definir los dos de forma coherente:

```python
class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)

    def __hash__(self) -> int:
        return hash((self.x, self.y))   # mismos campos que __eq__: contrato cumplido


assert len({Point(1, 2), Point(1, 2)}) == 1
```

O, más corto y con las mismas garantías, un dataclass congelado, que genera ambos métodos por ti:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: int
    y: int
```

**Por qué `frozen`.** Si la clave se puede mutar después de insertarla, su hash cambia pero sigue guardada en la casilla antigua: `d[p]` ya no la encuentra aunque `p in d.keys()` por iteración diga que está. Las claves deben ser inmutables en los campos que participan en el hash; por eso `list` no es hashable y `tuple` sí.

Prueba de que las colisiones se resuelven y no se pierden datos:

```python
class BadHash:
    def __init__(self, v): self.v = v
    def __eq__(self, o): return isinstance(o, BadHash) and o.v == self.v
    def __hash__(self): return 7       # todas colisionan

d = {BadHash(i): i for i in range(1000)}
assert len(d) == 1000 and d[BadHash(500)] == 500   # correcto, pero cada acceso es O(n)
```""",
            },
        ]
    },
]

ROWS += [
    # 6) BFS vs DFS (usuario en inglés)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "What's the actual difference between BFS and DFS beyond 'queue vs stack'? When would I pick one over the other? I'm working in JavaScript on a graph stored as an adjacency list."},
            {
                "role": "assistant",
                "content": """The order in which they discover nodes is the whole difference, and it determines what each one can answer cheaply.

**BFS** visits nodes in increasing distance (number of edges) from the start. Consequences:
- The first time you reach a node, you reached it by a shortest path (unweighted graph). That is the only reason to use BFS for "shortest path".
- Memory is the width of the frontier: on a wide, shallow graph it can hold most of the graph at once.

**DFS** follows one path as deep as it goes before backtracking. Consequences:
- Memory is the depth of the current path, not the width.
- It gives you entry/exit order, which is what cycle detection, topological sort and strongly connected components need.
- It says nothing about distances.

Pick BFS for: shortest path with unit weights, "minimum number of moves", level-by-level processing. Pick DFS for: connectivity, cycles, topological order, backtracking searches, anything on a tree where you want parent-before-children with cheap memory.

BFS with a parent map, so you can reconstruct the path, not just the distance:

```js
/** @param {Map<string, string[]>} graph */
export function shortestPath(graph, start, goal) {
  const parent = new Map([[start, null]]);
  const queue = [start];
  let head = 0;                          // index instead of shift(): shift() is O(n) on arrays
  while (head < queue.length) {
    const node = queue[head++];
    if (node === goal) break;
    for (const next of graph.get(node) ?? []) {
      if (!parent.has(next)) {           // first visit = shortest; never re-enqueue
        parent.set(next, node);
        queue.push(next);
      }
    }
  }
  if (!parent.has(goal)) return null;
  const path = [];
  for (let n = goal; n !== null; n = parent.get(n)) path.unshift(n);
  return path;
}
```

Iterative DFS with an explicit stack (the recursive version is shorter but overflows the call stack at roughly 10k depth in V8):

```js
export function dfsOrder(graph, start) {
  const visited = new Set();
  const order = [];
  const stack = [start];
  while (stack.length) {
    const node = stack.pop();
    if (visited.has(node)) continue;     // a node can be pushed twice before it is visited
    visited.add(node);
    order.push(node);
    const neighbors = graph.get(node) ?? [];
    for (let i = neighbors.length - 1; i >= 0; i--) stack.push(neighbors[i]); // keep left-to-right order
  }
  return order;
}
```

Two traps worth knowing:

1. Marking visited **when you dequeue** instead of when you enqueue is fine for DFS (that is why the `continue` is there) but wrong for BFS: a node could be enqueued many times and the queue grows beyond O(V).
2. `queue.shift()` makes BFS O(V²) on large graphs; the `head` index keeps it O(V + E). If memory matters, use a real deque.

Quick check on `a→b, a→c, b→d, c→d`: `shortestPath` returns `["a","b","d"]` (first neighbor wins ties), and `dfsOrder` returns `["a","b","d","c"]`.""",
            },
        ]
    },
    # 7) Dijkstra: pesos negativos y lazy deletion
    {
        "messages": [
            {"role": "user", "content": "Mi Dijkstra con heapq en Python da distancias incorrectas en algunos grafos, pero no en todos. Pusheo (distancia, nodo), saco con heappop y marco el nodo como visitado. Algunas aristas tienen peso negativo porque representan descuentos en una ruta. ¿Dónde está el fallo?"},
            {
                "role": "assistant",
                "content": """El fallo está en el dato que dejaste casi al final: **Dijkstra no funciona con pesos negativos**, y no es un detalle de implementación. El algoritmo se apoya en que, cuando saca un nodo del heap, ninguna arista posterior puede mejorar su distancia. Una arista negativa rompe esa garantía.

Contraejemplo mínimo, para que lo reproduzcas:

```
A --1--> B
A --5--> C
C --(-10)--> B
```

Dijkstra saca B con distancia 1 y lo cierra. Luego procesa C (5) y encuentra B por 5 + (-10) = -5, pero B ya está visitado, así que ignora la mejora. Respuesta: 1. Correcta: -5. En grafos donde la arista negativa nunca mejora un nodo ya cerrado el resultado coincide por casualidad; por eso «a veces» funciona.

**Opción 1: Bellman-Ford**, que admite pesos negativos y además detecta ciclos negativos (si hay un ciclo de suma negativa, la distancia mínima no existe: puedes dar vueltas para siempre).

```python
from collections import defaultdict

Graph = dict[str, list[tuple[str, float]]]


def bellman_ford(graph: Graph, source: str) -> dict[str, float]:
    dist: dict[str, float] = defaultdict(lambda: float("inf"))
    dist[source] = 0.0
    nodes = set(graph) | {v for edges in graph.values() for v, _ in edges}
    for _ in range(len(nodes) - 1):          # un camino simple tiene a lo sumo V-1 aristas
        changed = False
        for u, edges in graph.items():
            for v, w in edges:
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    changed = True
        if not changed:
            break
    for u, edges in graph.items():           # una pasada más: si algo mejora, hay ciclo negativo
        for v, w in edges:
            if dist[u] + w < dist[v]:
                raise ValueError("el grafo contiene un ciclo de peso negativo")
    return dict(dist)
```

Coste O(V·E) frente a O((V+E) log V) de Dijkstra. Para unos miles de nodos es perfectamente usable.

**Opción 2: modela los descuentos de otra forma.** Si el descuento es una cantidad fija que nunca supera el coste de la arista a la que se aplica, réstalo a esa arista y todos los pesos quedan ≥ 0: Dijkstra vuelve a ser válido. Si es un porcentaje sobre el total de la ruta, el problema deja de ser aditivo y ninguno de los dos algoritmos lo modela.

**Y para cuando los pesos sean no negativos**, tu implementación tiene además un detalle que conviene hacer bien: con `heapq` no puedes bajar la prioridad de un elemento, así que pusheas duplicados y descartas los obsoletos al sacarlos (*lazy deletion*):

```python
import heapq


def dijkstra(graph: Graph, source: str) -> dict[str, float]:
    dist: dict[str, float] = {source: 0.0}
    heap: list[tuple[float, str]] = [(0.0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, float("inf")):
            continue                          # entrada obsoleta: ya salió una mejor
        for v, w in graph.get(u, []):
            if w < 0:
                raise ValueError(f"arista negativa {u}->{v}: usa bellman_ford")
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist
```

El `if d > dist[u]: continue` sustituye al conjunto de visitados y es más seguro: un nodo se cierra cuando sale con su mejor distancia, no cuando entra.

Comprobación con el grafo de arriba: `bellman_ford({"A": [("B", 1), ("C", 5)], "C": [("B", -10)]}, "A")` devuelve `{"A": 0, "B": -5, "C": 5}`; `dijkstra` con el mismo grafo lanza `ValueError` en vez de devolver 1 en silencio.""",
            },
        ]
    },
]

ROWS += [
    # 8) DP mochila 0/1 en 1D: por qué recorrer al revés (C)
    {
        "messages": [
            {"role": "user", "content": "En la mochila 0/1 con un solo array, ¿por qué hay que recorrer las capacidades de mayor a menor? Mi profesor lo dijo como si fuera obvio y no lo es. Estoy en C."},
            {
                "role": "assistant",
                "content": r"""Porque al comprimir la tabla a una fila, la celda `dp[w - weight]` que lees tiene que ser la de la **fila anterior** (sin el objeto actual), y si recorres de menor a mayor ya la has sobrescrito con la fila actual. El resultado es que el mismo objeto se cuenta varias veces: estarías resolviendo la mochila **ilimitada**, no la 0/1.

Partamos de la tabla completa, que es la definición sin trucos:

```
dp[i][w] = mejor valor usando los primeros i objetos con capacidad w
dp[i][w] = max(dp[i-1][w],                       // no cojo el objeto i
               dp[i-1][w - weight[i]] + value[i]) // lo cojo (si cabe)
```

Cada fila solo depende de la anterior, así que basta un array si garantizas que, al calcular `dp[w]`, `dp[w - weight]` todavía contiene el valor de la fila `i-1`. Recorriendo `w` de `W` hacia abajo, las posiciones menores que `w` aún no se han tocado en esta pasada: son fila `i-1`. Recorriendo hacia arriba, `dp[w - weight]` ya es fila `i`, es decir, ya incluye el objeto `i`, y lo vuelves a sumar.

```c
#include <stdio.h>

static int max(int a, int b) { return a > b ? a : b; }

/* Mochila 0/1: cada objeto se usa como mucho una vez. */
int knapsack_01(const int *weight, const int *value, int n, int capacity) {
    int dp[capacity + 1];
    for (int w = 0; w <= capacity; w++) dp[w] = 0;
    for (int i = 0; i < n; i++) {
        for (int w = capacity; w >= weight[i]; w--) {       /* descendente */
            dp[w] = max(dp[w], dp[w - weight[i]] + value[i]);
        }
    }
    return dp[capacity];
}

/* Mochila ilimitada: el mismo bucle ascendente es exactamente lo que queremos aquí. */
int knapsack_unbounded(const int *weight, const int *value, int n, int capacity) {
    int dp[capacity + 1];
    for (int w = 0; w <= capacity; w++) dp[w] = 0;
    for (int i = 0; i < n; i++) {
        for (int w = weight[i]; w <= capacity; w++) {       /* ascendente */
            dp[w] = max(dp[w], dp[w - weight[i]] + value[i]);
        }
    }
    return dp[capacity];
}

int main(void) {
    int weight[] = {2, 3};
    int value[]  = {3, 4};
    /* capacidad 4: 0/1 solo cabe uno de los dos -> 4; ilimitada cabe el de peso 2 dos veces -> 6 */
    printf("0/1 = %d (esperado 4)\n", knapsack_01(weight, value, 2, 4));
    printf("ilimitada = %d (esperado 6)\n", knapsack_unbounded(weight, value, 2, 4));
    return 0;
}
```

Traza del caso de prueba con el objeto (peso 2, valor 3) y capacidad 4, para ver la diferencia:

- Descendente: `w=4`: `dp[2]` es 0 (fila anterior) → `dp[4]=3`. `w=3`: `dp[1]=0` → `dp[3]=3`. `w=2`: `dp[0]=0` → `dp[2]=3`. Un solo uso del objeto.
- Ascendente: `w=2`: `dp[2]=3`. `w=3`: `dp[3]=3`. `w=4`: `dp[2]` **ya vale 3** → `dp[4]=6`. El objeto se usó dos veces.

Dos notas de C: el array de longitud variable `dp[capacity + 1]` vive en la pila; para capacidades grandes (más de unas decenas de miles) usa `malloc`. Y el bucle interior empieza en `weight[i]`, no en 0, para que `w - weight[i]` nunca sea negativo.""",
            },
        ]
    },
    # 9) LCS con reconstrucción (Python)
    {
        "messages": [
            {"role": "user", "content": "Tengo la DP de la subsecuencia común más larga que devuelve la longitud, pero necesito la subsecuencia en sí, no solo cuánto mide. ¿Cómo la reconstruyo?"},
            {
                "role": "assistant",
                "content": """Recorres la tabla hacia atrás desde la esquina `(n, m)` deshaciendo la decisión que la construyó: si los caracteres coinciden, forman parte de la respuesta y retrocedes en diagonal; si no, te mueves hacia la celda vecina de la que salió el máximo.

```python
def lcs(a: str, b: str) -> str:
    n, m = len(a), len(b)
    # dp[i][j] = longitud de la LCS de a[:i] y b[:j]
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Reconstrucción: desde (n, m) hacia (0, 0)
    out: list[str] = []
    i, j = n, m
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            out.append(a[i - 1])      # este carácter está en la LCS
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1                    # el máximo vino de arriba
        else:
            j -= 1                    # el máximo vino de la izquierda
    return "".join(reversed(out))     # se acumuló del final al principio
```

Pruebas, incluidas las que suelen fallar:

```python
def test_lcs():
    assert lcs("ABCBDAB", "BDCABA") in {"BCBA", "BDAB", "BCAB"}  # varias LCS válidas de longitud 4
    assert lcs("", "abc") == ""
    assert lcs("abc", "abc") == "abc"
    assert lcs("abc", "def") == ""
    assert len(lcs("AGGTAB", "GXTXAYB")) == 4 and lcs("AGGTAB", "GXTXAYB") == "GTAB"
```

Tres cosas que conviene saber:

- **La LCS no es única.** El empate `>=` en la reconstrucción decide cuál devuelves; con `>` obtendrías otra igualmente válida. Si tu test compara con una cadena fija, acabará siendo frágil: compara longitudes o pertenencia a un conjunto.
- **Memoria O(n·m).** Para calcular solo la longitud bastan dos filas, pero para reconstruir necesitas la tabla entera o el algoritmo de Hirschberg (divide y vencerás, memoria O(n + m), mismo tiempo). Para cadenas de pocos miles de caracteres la tabla completa es la opción simple y correcta.
- **Por qué `out` se invierte al final.** Añadir al principio de una lista es O(n) por operación; acumular y dar la vuelta una vez es O(n) total.""",
            },
        ]
    },
]

ROWS += [
    # 10) Two pointers sobre array ordenado (Python)
    {
        "messages": [
            {"role": "user", "content": "Tengo un array ordenado de hasta 10^5 enteros y quiero saber si hay dos que sumen un objetivo. Lo hice con dos bucles anidados y tarda segundos. ¿Hay algo mejor sin usar diccionarios?"},
            {
                "role": "assistant",
                "content": """Sí: dos punteros desde los extremos. O(n) tiempo, O(1) memoria, y usa justo lo que tienes (el array ordenado). El diccionario es la alternativa cuando el array **no** está ordenado.

```python
def two_sum_sorted(nums: list[int], target: int) -> tuple[int, int] | None:
    '''Devuelve índices (i, j) con i < j y nums[i] + nums[j] == target, o None.'''
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        total = nums[lo] + nums[hi]
        if total == target:
            return lo, hi
        if total < target:
            lo += 1   # la suma se queda corta: solo puede crecer subiendo el menor
        else:
            hi -= 1   # la suma se pasa: solo puede bajar bajando el mayor
    return None
```

**Por qué no se pierde ninguna pareja.** El invariante del bucle es: *si existe una pareja válida, sus dos índices están en `[lo, hi]`*. Cuando `total < target`, para cualquier `k <= hi` se cumple `nums[lo] + nums[k] <= nums[lo] + nums[hi] < target`, así que `nums[lo]` no puede emparejarse con nada del rango: descartarlo mantiene el invariante. El caso `total > target` es simétrico con `hi`. Cada iteración elimina exactamente un índice, de ahí las `n - 1` iteraciones como máximo.

Traza con `[1, 3, 5, 7, 11]` y `target = 10`:

- `(0, 4)`: 1 + 11 = 12 > 10 → `hi = 3`
- `(0, 3)`: 1 + 7 = 8 < 10 → `lo = 1`
- `(1, 3)`: 3 + 7 = 10 → devuelve `(1, 3)`

Funciona con negativos y con duplicados porque solo depende del orden. Con lista vacía, `hi = -1`, el bucle no entra y devuelve `None`.

Test contra fuerza bruta en listas pequeñas, que es la forma barata de ganar confianza en un algoritmo de este tipo:

```python
import random


def test_two_sum_sorted_coincide_con_fuerza_bruta():
    rng = random.Random(42)
    for _ in range(500):
        nums = sorted(rng.randint(-20, 20) for _ in range(rng.randint(0, 12)))
        target = rng.randint(-40, 40)
        brute = any(
            nums[i] + nums[j] == target
            for i in range(len(nums))
            for j in range(i + 1, len(nums))
        )
        assert (two_sum_sorted(nums, target) is not None) == brute
```

Si más adelante necesitas tríos que sumen un objetivo, fijas el primer elemento y aplicas esto mismo al resto: O(n²) en vez de O(n³).""",
            },
        ]
    },
    # 11) Ventana deslizante: subcadena sin repetidos (JS, código lento del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": """Esta función devuelve la longitud de la subcadena más larga sin caracteres repetidos, pero con cadenas de 20k caracteres tarda varios segundos:

```js
function longestUnique(s) {
  let best = 0;
  for (let i = 0; i < s.length; i++) {
    for (let j = i; j <= s.length; j++) {
      const sub = s.slice(i, j);
      if (new Set(sub).size === sub.length) best = Math.max(best, sub.length);
      else break;
    }
  }
  return best;
}
```

¿Cómo la hago rápida?""",
            },
            {
                "role": "assistant",
                "content": """Es cúbica en el peor caso: por cada `i` recorres `j`, y en cada paso construyes un `Set` de toda la subcadena. Con 20k caracteres y pocas repeticiones son miles de millones de operaciones. La versión lineal es una **ventana deslizante**: la subcadena `[left, right]` sin repetidos avanza de izquierda a derecha y nunca retrocede.

```js
function longestUnique(s) {
  const chars = [...s];          // puntos de código, no unidades UTF-16: "😀" cuenta como 1
  const lastSeen = new Map();    // carácter -> último índice donde apareció
  let left = 0;
  let best = 0;
  for (let right = 0; right < chars.length; right++) {
    const ch = chars[right];
    const prev = lastSeen.get(ch);
    if (prev !== undefined && prev >= left) {
      left = prev + 1;           // salta justo detrás del duplicado
    }
    lastSeen.set(ch, right);
    best = Math.max(best, right - left + 1);
  }
  return best;
}
```

**Invariante:** al final de cada iteración, `chars[left..right]` no tiene repetidos y `left` es el menor valor que lo cumple. Cuando aparece `ch` por segunda vez dentro de la ventana, el único modo de restaurar el invariante es mover `left` justo detrás de la aparición anterior. `left` y `right` solo crecen, así que cada índice entra y sale de la ventana una vez: O(n) tiempo, O(k) memoria con k = alfabeto.

La comprobación `prev >= left` es la que más gente se salta. Con `"abba"`: al llegar a la segunda `a` (índice 3), `prev = 0` pero `left` ya vale 2 por la doble `b`. Sin la comprobación, `left` retrocedería a 1 y la ventana `"bba"` contaría como válida.

Traza con `"pwwkew"`: `p`→[0,0]; `w`→[0,1]; `w` repetida (prev=1) → left=2, [2,2]; `k`→[2,3]; `e`→[2,4] (best=3); `w` (prev=2, ≥ left) → left=3, [3,5]. Resultado 3 (`"wke"`). ✓

```js
import { test } from "node:test";
import assert from "node:assert/strict";

test("longestUnique", () => {
  assert.equal(longestUnique(""), 0);
  assert.equal(longestUnique("abcabcbb"), 3);
  assert.equal(longestUnique("bbbbb"), 1);
  assert.equal(longestUnique("pwwkew"), 3);
  assert.equal(longestUnique("abba"), 2);
  assert.equal(longestUnique("a😀b😀"), 3);
});
```

Si solo manejas ASCII y necesitas exprimir, sustituye el `Map` por un `Int32Array(128)` inicializado a -1: misma lógica, sin *hashing*.""",
            },
        ]
    },
    # 12) Búsqueda binaria con invariantes (Go, bucle infinito, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi búsqueda binaria en Go se queda colgada con algunos inputs:

```go
func search(a []int, x int) int {
	lo, hi := 0, len(a)-1
	for lo < hi {
		mid := (lo + hi) / 2
		if a[mid] < x {
			lo = mid
		} else {
			hi = mid
		}
	}
	if a[lo] == x {
		return lo
	}
	return -1
}
```

Con `a = []int{1, 3, 5}` y `x = 5` no termina nunca.""",
            },
            {
                "role": "assistant",
                "content": """Reproducido: `lo=0, hi=2` → `mid=1`, `a[1]=3 < 5` → `lo=1`. Ahora `lo=1, hi=2` → `mid=(1+2)/2=1` otra vez, `a[1] < 5` → `lo=1`. El rango no se encoge. La causa es `lo = mid`: cuando `hi == lo+1`, la división entera da `mid == lo` y la asignación no cambia nada.

La forma de no equivocarse con búsquedas binarias es fijar el **invariante** antes de escribir el bucle y derivar las dos ramas de él. Uso rango semiabierto `[lo, hi)`:

> `a[0:lo]` son todos `< x` y `a[hi:]` son todos `>= x`.

Con eso, cada rama es forzosa: si `a[mid] < x`, todo hasta `mid` inclusive es `< x` → `lo = mid+1`; si no, `a[mid] >= x` → `hi = mid`. Las dos reducen el rango estrictamente porque `lo <= mid < hi`. Al terminar, `lo == hi` es el primer índice con `a[i] >= x`.

```go
// lowerBound devuelve el menor índice i con a[i] >= x, o len(a) si no existe.
// Invariante del bucle: a[0:lo] < x  y  a[hi:] >= x.
func lowerBound(a []int, x int) int {
	lo, hi := 0, len(a)
	for lo < hi {
		mid := lo + (hi-lo)/2
		if a[mid] < x {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return lo
}

func search(a []int, x int) int {
	i := lowerBound(a, x)
	if i < len(a) && a[i] == x {
		return i
	}
	return -1
}
```

Dos arreglos más que venían de regalo con el original:

- `a[lo]` con slice vacío hacía *panic* (`lo = 0`, `len = 0`). Ahora `lowerBound` devuelve `0 == len(a)` y `search` lo descarta.
- `lo + (hi-lo)/2` en vez de `(lo+hi)/2`: evita el desbordamiento con slices enormes.

Test: compara con una búsqueda lineal en muchos casos pequeños, que es donde viven los errores de ±1.

```go
func TestSearchContraLineal(t *testing.T) {
	rng := rand.New(rand.NewSource(1))
	for iter := 0; iter < 2000; iter++ {
		a := make([]int, rng.Intn(8))
		for i := range a {
			a[i] = rng.Intn(6)
		}
		sort.Ints(a)
		x := rng.Intn(8) - 1
		want := -1
		for i, v := range a {
			if v == x {
				want = i
				break
			}
		}
		if got := search(a, x); got != want {
			t.Fatalf("a=%v x=%d: got %d want %d", a, x, got, want)
		}
	}
}
```

Fíjate en que el test espera el **primer** índice cuando hay duplicados; `lowerBound` lo garantiza. En producción, la librería estándar ya trae esto: `sort.SearchInts(a, x)` y, desde Go 1.21, `slices.BinarySearch(a, x)`.""",
            },
            {"role": "user", "content": "Vale, ¿y si lo que quiero es el último índice con a[i] <= x? Tengo duplicados."},
            {
                "role": "assistant",
                "content": """Cambia una sola comparación. Define el invariante espejo: `a[0:lo] <= x` y `a[hi:] > x`. El bucle entonces converge al primer índice con `a[i] > x` (el *upper bound*), y el último `<= x` es justo el anterior.

```go
// upperBound devuelve el menor índice i con a[i] > x, o len(a) si no existe.
// Invariante: a[0:lo] <= x  y  a[hi:] > x.
func upperBound(a []int, x int) int {
	lo, hi := 0, len(a)
	for lo < hi {
		mid := lo + (hi-lo)/2
		if a[mid] <= x {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return lo
}

// lastLessOrEqual devuelve el mayor índice i con a[i] <= x, o -1 si todos son > x.
func lastLessOrEqual(a []int, x int) int {
	return upperBound(a, x) - 1
}
```

Traza con `[1, 2, 2, 2, 3]` y `x = 2`: `upperBound` devuelve 4 (el `3`), así que el resultado es 3, el último `2`. Con `x = 0` devuelve `0 - 1 = -1`: no hay ninguno. Con `x = 9`, `len(a) - 1 = 4`.

Con `sort.Search` es una línea, porque la función recibe el predicado que define la frontera (debe ser falso y luego verdadero a lo largo del slice):

```go
last := sort.Search(len(a), func(i int) bool { return a[i] > x }) - 1
```

Regla general: toda búsqueda binaria es «encuentra la frontera entre la zona donde el predicado es falso y la zona donde es verdadero». Si escribes el predicado primero (`a[i] >= x`, `a[i] > x`, `cabe(i)`, `tarda(i) > limite`), las ramas del bucle salen solas y no hay que pensar en ±1.""",
            },
        ]
    },
    # 13) Ordenación estable (Python vs Go, rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con precisión y sin relleno."},
            {"role": "user", "content": "Che, ordeno empleados por nombre y después por departamento con sort, y en Go el orden por nombre dentro de cada departamento se me rompe. En Python el mismo código anda bien. ¿Qué estoy haciendo mal?"},
            {
                "role": "assistant",
                "content": """Nada en la lógica: la diferencia es la **estabilidad** del algoritmo. Una ordenación es estable si los elementos con clave igual conservan su orden relativo de entrada. `list.sort` de Python es estable (Timsort); `sort.Slice` de Go **no** lo es (pdqsort). Por eso tu segunda pasada por departamento conserva el orden por nombre en Python y lo destroza en Go.

Tenés dos salidas:

**1. Usar la variante estable** (cambio mínimo): `sort.SliceStable` o, desde Go 1.21, `slices.SortStableFunc`.

**2. Una sola pasada con clave compuesta** (la que recomiendo): es explícita, no depende de la estabilidad y hace un solo recorrido.

```go
import (
	"cmp"
	"slices"
)

type Employee struct {
	Name, Dept string
}

slices.SortFunc(employees, func(a, b Employee) int {
	if c := cmp.Compare(a.Dept, b.Dept); c != 0 {
		return c
	}
	return cmp.Compare(a.Name, b.Name)
})
```

En Python lo mismo con una tupla como clave:

```python
employees.sort(key=lambda e: (e.dept, e.name))
```

Y si una de las claves va descendente y es numérica, negala en la tupla (`(-e.salary, e.name)`); si es texto, hacé dos pasadas estables en orden inverso de prioridad, que es exactamente el truco que usabas.

Lo que vale la pena saberse de memoria, porque cambia por lenguaje:

| Lenguaje | Estable | No estable |
|---|---|---|
| Python | `sort`, `sorted` | — |
| JavaScript | `Array.prototype.sort` (garantizado desde ES2019) | — |
| Go | `sort.SliceStable`, `slices.SortStableFunc` | `sort.Slice`, `slices.SortFunc` |
| Rust | `sort`, `sort_by_key` | `sort_unstable*` |
| C | — | `qsort` (no especificado) |

Un test chico que detecta el problema sin mirar datos reales: claves con pocos valores distintos para forzar empates, y verificar que dentro de cada empate los índices originales van creciendo.

```go
func TestOrdenEstablePorDepto(t *testing.T) {
	type row struct {
		idx  int
		dept string
	}
	rows := make([]row, 200)
	for i := range rows {
		rows[i] = row{i, []string{"a", "b", "c"}[i%3]}
	}
	slices.SortStableFunc(rows, func(x, y row) int { return cmp.Compare(x.dept, y.dept) })
	for i := 1; i < len(rows); i++ {
		if rows[i-1].dept == rows[i].dept && rows[i-1].idx > rows[i].idx {
			t.Fatalf("orden no estable en posición %d", i)
		}
	}
}
```

Cambiá `SortStableFunc` por `SortFunc` en ese test y vas a ver fallar lo mismo que te pasó en producción.""",
            },
        ]
    },
    # 14) Invariantes de bucle: demostrar Kadane (Rust)
    {
        "messages": [
            {"role": "user", "content": "Entiendo cómo funciona el algoritmo de Kadane (suma máxima de subarray) pero no sabría demostrar que es correcto. ¿Cómo se razona eso con invariantes? Si puede ser con código en Rust."},
            {
                "role": "assistant",
                "content": """La demostración cabe en tres pasos si antes defines con precisión qué guarda cada variable.

**Definiciones.** Para un array `a[0..n)`, sea `E(i)` la suma máxima de un subarray **que termina exactamente en `i`**. La respuesta es `max(E(0), E(1), …, E(n-1))`, porque todo subarray termina en algún índice.

**Recurrencia.** `E(i) = a[i] + max(0, E(i-1))`. El mejor subarray que termina en `i` o bien es solo `[a[i]]`, o bien es `a[i]` pegado a un subarray que termina en `i-1`; y de esos, el mejor es por definición el de suma `E(i-1)`. Si `E(i-1) < 0`, pegarse a él solo resta, así que el `max(0, ·)` lo descarta. Esto es un argumento de intercambio: si la solución óptima usara un subarray peor que `E(i-1)`, sustituirlo por el óptimo daría una suma mayor, contradicción.

**Invariante del bucle**, tras procesar el índice `i`:

1. `ending_here == E(i)`
2. `best == max(E(0..=i))`

- *Inicialización*: antes del bucle, `ending_here = best = a[0] = E(0)`. ✓
- *Mantenimiento*: la iteración `i` calcula `ending_here = a[i] + max(0, ending_here)`, que por la recurrencia es `E(i)`, y `best = max(best, ending_here) = max(E(0..=i))`. ✓
- *Terminación*: tras `i = n-1`, `best` es el máximo sobre todos los finales posibles, es decir, la respuesta. ✓

```rust
/// Suma máxima de un subarray no vacío. `None` si el slice está vacío.
pub fn max_subarray(a: &[i64]) -> Option<i64> {
    let (&first, rest) = a.split_first()?;
    let mut ending_here = first; // E(i): mejor suma de un subarray que termina en i
    let mut best = first;        // max(E(0..=i))
    for &x in rest {
        ending_here = x + ending_here.max(0);
        best = best.max(ending_here);
    }
    Some(best)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn casos_limite() {
        assert_eq!(max_subarray(&[]), None);
        assert_eq!(max_subarray(&[5]), Some(5));
        assert_eq!(max_subarray(&[-3, -1, -2]), Some(-1)); // todos negativos: el mayor elemento
        assert_eq!(max_subarray(&[-2, 1, -3, 4, -1, 2, 1, -5, 4]), Some(6));
    }

    #[test]
    fn coincide_con_fuerza_bruta() {
        let a: [i64; 8] = [3, -4, 2, -1, 6, -8, 3, 1];
        let brute = (0..a.len())
            .flat_map(|i| (i..a.len()).map(move |j| (i, j)))
            .map(|(i, j)| a[i..=j].iter().sum::<i64>())
            .max();
        assert_eq!(max_subarray(&a), brute);
    }
}
```

El error clásico que la demostración deja al descubierto: inicializar `best = 0`. Eso cambia la definición (permite el subarray vacío) y con `[-3, -1, -2]` devolvería 0 en vez de -1. Si tu problema sí admite el subarray vacío, entonces `best = 0` y `ending_here = 0` son correctos y el `Option` sobra. Las dos versiones son válidas; lo que no vale es mezclar la inicialización de una con la especificación de la otra.""",
            },
        ]
    },
    # 15) Pruebas por propiedades con Hypothesis (Python, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Implementé mi propio merge sort en Python para un curso (firma `merge_sort(xs, key=None)`, como `sorted`). ¿Cómo lo pruebo bien sin escribir cien listas a mano?"},
            {
                "role": "assistant",
                "content": """Con **pruebas por propiedades**: en vez de casos concretos, escribes lo que debe cumplirse para *cualquier* entrada y dejas que Hypothesis genere cientos de listas, incluidas las raras (vacía, un elemento, todos iguales, enteros enormes).

Para una ordenación, «está bien» significa exactamente dos cosas:

1. La salida está ordenada: `out[i] <= out[i+1]` para todo `i`.
2. La salida es una permutación de la entrada: mismos elementos con las mismas multiplicidades.

Ninguna de las dos sola basta (`[]` cumple la primera; la identidad cumple la segunda). Y como prometes `key=`, añade la estabilidad.

```python
# pip install hypothesis   (o: uv add --dev hypothesis)
from collections import Counter

from hypothesis import example, given, settings, strategies as st

from mi_sort import merge_sort


@given(st.lists(st.integers()))
@example([])
@example([1, 1, 1])
def test_ordenada_y_permutacion(xs):
    out = merge_sort(xs)
    assert all(a <= b for a, b in zip(out, out[1:]))
    assert Counter(out) == Counter(xs)


@given(st.lists(st.integers()))
def test_coincide_con_sorted(xs):
    # oráculo: sorted es correcto, así que cualquier diferencia es un bug tuyo
    assert merge_sort(xs) == sorted(xs)


@given(st.lists(st.integers(min_value=0, max_value=3)))
@settings(max_examples=500)
def test_es_estable(claves):
    # claves con pocos valores para forzar empates
    indexed = list(enumerate(claves))  # (posición original, clave)
    out = merge_sort(indexed, key=lambda p: p[1])
    for (i, ka), (j, kb) in zip(out, out[1:]):
        if ka == kb:
            assert i < j, f"empate {ka}: {i} debería ir antes que {j}"


@given(st.lists(st.integers()))
def test_idempotente(xs):
    once = merge_sort(xs)
    assert merge_sort(once) == once
```

Qué pasa cuando falla: Hypothesis **reduce** el ejemplo hasta el mínimo que sigue fallando. Un merge sort con un `<` donde debía ir `<=` no te devuelve una lista de 40 números: te devuelve `[(0, 0), (1, 0)]` y el mensaje `empate 0: 0 debería ir antes que 1`. El caso fallido queda guardado en `.hypothesis/` y se reintenta primero en la siguiente ejecución.

Tres consejos de uso:

- **No reimplementes el algoritmo en el test.** Si la propiedad es «igual que mi otra función de ordenar», estás comparando dos copias del mismo error. Las propiedades buenas hablan del *resultado*, no del método.
- **Cuidado con `float`.** `st.floats()` genera `nan`, que rompe el orden total (`nan <= nan` es `False`). Usa `st.floats(allow_nan=False)` o decide explícitamente qué hace tu función con `nan`.
- **Para claves arbitrarias**, `st.text()` y `st.tuples(...)` funcionan igual; con `key=len` sobre `st.text()` tendrás muchos empates y un buen test de estabilidad gratis.

El equivalente en JavaScript es `fast-check` (`fc.property(fc.array(fc.integer()), …)`), con la misma idea y la misma reducción de ejemplos.""",
            },
        ]
    },
    # 16) Desbordamiento de enteros (C, multiturno con Python/Rust)
    {
        "messages": [
            {"role": "user", "content": "Tengo una búsqueda binaria en C que funciona con arrays pequeños, pero con uno de 1.500 millones de enteros (máquina con mucha RAM) se cae con segfault. El `mid = (lo + hi) / 2` es el de toda la vida, no entiendo qué cambia."},
            {
                "role": "assistant",
                "content": """Cambia que `lo + hi` ya no cabe en un `int`. Con `lo` y `hi` cerca de 1.500 millones, la suma supera `INT_MAX` (2.147.483.647). En C el desbordamiento de enteros con signo es **comportamiento indefinido**; en la práctica el resultado se vuelve negativo, `mid` es negativo, `a[mid]` lee fuera del array y de ahí el segfault.

El arreglo es una línea, y de paso conviene usar `size_t` para índices:

```c
#include <stddef.h>

/* Devuelve el índice de x en a[0..n), o (size_t)-1 si no está. */
size_t binary_search(const int *a, size_t n, int x) {
    size_t lo = 0, hi = n;                  /* rango semiabierto [lo, hi) */
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;    /* nunca desborda: hi - lo <= n */
        if (a[mid] < x) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return (lo < n && a[lo] == x) ? lo : (size_t)-1;
}
```

`hi - lo` siempre es menor o igual que `n`, que por definición cupo en `size_t`, así que la expresión no puede desbordar. `(lo + hi) / 2` falla incluso con `size_t` en teoría (dos valores cercanos a `SIZE_MAX`), aunque ahí ningún array real llega.

Para **ver** el fallo en vez de deducirlo, compila con el *sanitizer* de comportamiento indefinido y ejecútalo con el array grande:

```
cc -O1 -g -fsanitize=undefined bs.c && ./a.out
runtime error: signed integer overflow: 1500000000 + 1499999999 cannot be represented in type 'int'
```

Ese mensaje te señala la línea exacta. Es el mismo bug que estuvo años en `java.util.Arrays.binarySearch` hasta 2006; no es un despiste raro, es el despiste estándar de este algoritmo.""",
            },
            {"role": "user", "content": "¿Y en Python o en Rust tengo que preocuparme por lo mismo?"},
            {
                "role": "assistant",
                "content": """Depende del lenguaje, y la respuesta no es la que uno espera a primera vista.

**Python: no, con una excepción.** Los `int` tienen precisión arbitraria, así que `(lo + hi) // 2` es correcto siempre. La excepción son los arrays de NumPy: `np.int32` y `np.int64` desbordan en silencio (a veces con un `RuntimeWarning`, a veces nada). Si calculas índices a partir de elementos de un array tipado, conviértelos con `int(...)` antes.

**Rust: sí, y el comportamiento cambia según el perfil de compilación.**

- En `debug` (`cargo build`, `cargo test`), un desbordamiento aritmético hace *panic*: `attempt to add with overflow`. Tus tests lo encontrarían si cubren valores grandes.
- En `release`, por defecto **envuelve en silencio** (`1500000000 + 1500000000` da un número negativo o pequeño) y vuelves al bug de C, sin UB pero con resultado incorrecto.

Opciones, de la más local a la más global:

```rust
// 1. Misma técnica que en C: nunca sumar dos índices grandes.
let mid = lo + (hi - lo) / 2;

// 2. Hacer explícita la intención (Rust 1.85+ para enteros sin signo).
let mid = usize::midpoint(lo, hi);

// 3. Decir qué quieres cuando desborde, en vez de dejarlo implícito.
let total = a.checked_add(b).ok_or("overflow")?;   // Option -> error
let wrapped = a.wrapping_add(b);                   // envolver a propósito
let clamped = a.saturating_add(b);                 // saturar en el máximo
```

Y si quieres que `release` también haga *panic* en vez de envolver:

```toml
# Cargo.toml
[profile.release]
overflow-checks = true
```

Cuesta algo de rendimiento en bucles aritméticos muy ajustados, pero para la mayoría de servicios es un precio razonable por convertir un dato corrupto en un fallo visible.

**Go**, por completar el cuadro: envuelve en silencio siempre, sin opción de activar comprobaciones; la única defensa es la forma `lo + (hi-lo)/2`.""",
            },
        ]
    },
]

ROWS += [
    # 17) Aleatoriedad: barajar con sort(random) está mal; Fisher-Yates y semillas (JS)
    {
        "messages": [
            {"role": "user", "content": "Para barajar un mazo uso `cards.sort(() => Math.random() - 0.5)`. Un compañero dice que está mal pero a mí me parece que funciona bien. ¿Quién tiene razón?"},
            {
                "role": "assistant",
                "content": """Tu compañero. El comparador de `sort` tiene un contrato (consistente y transitivo) y uno aleatorio lo rompe; el resultado depende del algoritmo interno del motor y **no es uniforme**: unas permutaciones salen bastante más que otras. «Parece que funciona» porque a ojo no se distingue un sesgo del 30 %.

Mídelo tú mismo con un mazo de 3 cartas, donde hay 6 permutaciones y cada una debería salir el 16,7 % de las veces:

```js
function countPermutations(shuffleFn, runs = 100_000) {
  const counts = new Map();
  for (let r = 0; r < runs; r++) {
    const key = shuffleFn([1, 2, 3]).join("");
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Object.fromEntries(
    [...counts].sort().map(([k, v]) => [k, ((v / runs) * 100).toFixed(1) + "%"]),
  );
}

console.log(countPermutations((a) => a.sort(() => Math.random() - 0.5)));
console.log(countPermutations((a) => shuffle(a)));
```

En Node 20/22 (V8, que ordena arrays cortos por inserción binaria) la primera línea imprime porcentajes desiguales: unas permutaciones alrededor del 25 % y otras del 12,5 %. La segunda, seis valores alrededor del 16,7 %.

El algoritmo correcto es **Fisher-Yates**: recorre desde el final y cambia cada posición por una elegida al azar entre las que quedan.

```js
/**
 * Baraja `array` en el sitio y lo devuelve. `random` debe devolver un número en [0, 1).
 */
function shuffle(array, random = Math.random) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1)); // j en [0, i], inclusive: puede quedarse donde está
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}
```

Por qué es uniforme: en el paso `i` hay `i + 1` candidatos y cada uno tiene la misma probabilidad de ocupar la posición `i`; multiplicando, cada una de las `n!` permutaciones sale con probabilidad `1/n!`. El error típico al escribirlo de memoria es `Math.floor(random() * array.length)` (elegir entre todos en cada paso): produce `n^n` resultados equiprobables, que no es múltiplo de `n!`, así que tampoco es uniforme.

Sobre **semillas**: `Math.random()` no se puede sembrar, por eso `shuffle` recibe `random` como parámetro. Para tests reproducibles inyecta un generador pequeño:

```js
// mulberry32: PRNG de 32 bits, suficiente para tests y simulaciones. NO para criptografía.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = mulberry32(42);
shuffle([1, 2, 3, 4, 5], rng); // misma salida en cada ejecución
```

Y si el barajado tiene valor real (sorteos, juego con dinero), usa aleatoriedad criptográfica: en Node, `crypto.randomInt(0, i + 1)` dentro del bucle en vez de `Math.floor(random() * (i + 1))`.""",
            },
        ]
    },
    # 18) Unión-búsqueda para componentes conexas (Go, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo hasta un millón de servidores y diez millones de enlaces (pares de ids) y necesito contar cuántas redes aisladas hay y responder muchas consultas del tipo «¿están A y B conectados?». Pensaba hacer BFS por cada consulta pero son cientos de miles de consultas. En Go."},
            {
                "role": "assistant",
                "content": """BFS por consulta es O(n + m) cada vez: con 10⁷ enlaces y 10⁵ consultas son 10¹² operaciones. La estructura para esto es **unión-búsqueda** (DSU, *disjoint set union*): cada `Union` y cada `Find` cuestan O(α(n)) amortizado, donde α es la inversa de Ackermann, en la práctica ≤ 4. Los 10⁷ enlaces se procesan en menos de un segundo y cada consulta es constante.

```go
package dsu

// DSU mantiene una partición de {0..n-1} en conjuntos disjuntos.
type DSU struct {
	parent []int32 // int32: la mitad de memoria que int para n = 10^6; cabe hasta 2^31 nodos
	size   []int32
	count  int // número de conjuntos (componentes)
}

func New(n int) *DSU {
	d := &DSU{parent: make([]int32, n), size: make([]int32, n), count: n}
	for i := range d.parent {
		d.parent[i] = int32(i)
		d.size[i] = 1
	}
	return d
}

// Find devuelve el representante de x. Comprime el camino por "path halving":
// cada nodo visitado pasa a apuntar a su abuelo, sin segunda pasada ni recursión.
func (d *DSU) Find(x int) int {
	for d.parent[x] != int32(x) {
		d.parent[x] = d.parent[d.parent[x]]
		x = int(d.parent[x])
	}
	return x
}

// Union junta los conjuntos de a y b. Devuelve false si ya estaban juntos.
func (d *DSU) Union(a, b int) bool {
	ra, rb := d.Find(a), d.Find(b)
	if ra == rb {
		return false
	}
	if d.size[ra] < d.size[rb] {
		ra, rb = rb, ra // el árbol pequeño cuelga del grande: la altura queda acotada por log n
	}
	d.parent[rb] = int32(ra)
	d.size[ra] += d.size[rb]
	d.count--
	return true
}

func (d *DSU) Connected(a, b int) bool { return d.Find(a) == d.Find(b) }
func (d *DSU) Components() int        { return d.count }
```

Las dos optimizaciones son las que dan la cota: **unión por tamaño** evita cadenas largas y **compresión de caminos** las aplana al consultarlas. Con solo una de las dos la cota es O(log n), que también valdría para tus números; con ninguna, un caso adverso degenera en O(n) por operación.

Uso y test:

```go
func TestRedes(t *testing.T) {
	d := New(6)
	links := [][2]int{{0, 1}, {1, 2}, {3, 4}}
	for _, l := range links {
		d.Union(l[0], l[1])
	}
	if got := d.Components(); got != 3 { // {0,1,2}, {3,4}, {5}
		t.Fatalf("components = %d, want 3", got)
	}
	if !d.Connected(0, 2) || d.Connected(2, 3) || d.Connected(5, 0) {
		t.Fatal("conectividad incorrecta")
	}
	if d.Union(0, 2) { // ya estaban unidos: no debe contar
		t.Fatal("Union devolvió true para un enlace redundante")
	}
}
```

Dos observaciones para tu caso concreto:

- Si **todos** los enlaces se conocen antes de la primera consulta y nunca cambian, un único BFS/DFS que etiquete cada nodo con su componente también es O(n + m) y responde consultas en O(1) comparando etiquetas. DSU gana cuando los enlaces llegan mezclados con las consultas.
- El `false` de `Union` tiene un uso extra: en un grafo no dirigido, un enlace que devuelve `false` cierra un ciclo. Es la base de Kruskal y de detectar redundancias en tu topología.

Memoria: dos slices de `int32` para 10⁶ nodos son 8 MB; los 10⁷ enlaces ni siquiera hace falta guardarlos, se consumen al vuelo.""",
            },
        ]
    },
    # 19) Trie vs lista ordenada + bisect para autocompletar (Python)
    {
        "messages": [
            {"role": "user", "content": "Para un autocompletado con unas 200 mil palabras, ¿me compensa montar un trie o con una lista ordenada y `startswith` me vale? Es Python y el diccionario no cambia."},
            {
                "role": "assistant",
                "content": """Para 200k palabras estáticas, la **lista ordenada con búsqueda binaria** te sobra y es más simple y más ligera que un trie en Python. El trie compensa cuando necesitas algo que la lista no da: contar cuántas palabras hay bajo un prefijo sin recorrerlas, inserciones y borrados frecuentes, o búsquedas con tolerancia a errores.

Costes para una consulta que devuelve `k` resultados:

| Enfoque | Tiempo por consulta | Memoria (200k palabras) |
|---|---|---|
| Recorrer todo con `startswith` | O(n) ≈ 200k comparaciones | la lista, ~15 MB |
| Lista ordenada + `bisect` | O(log n + k) ≈ 18 saltos + k | la lista, ~15 MB |
| Trie de dicts | O(len(prefijo) + k) | 50-200 MB según prefijos compartidos |

La opción 1 ya va en pocos milisegundos; la 2 es casi gratis y escala.

```python
import bisect


class PrefixIndex:
    def __init__(self, words: list[str]) -> None:
        self._words = sorted(set(words))

    def complete(self, prefix: str, limit: int = 10) -> list[str]:
        i = bisect.bisect_left(self._words, prefix)   # primera palabra >= prefix
        out: list[str] = []
        while i < len(self._words) and len(out) < limit and self._words[i].startswith(prefix):
            out.append(self._words[i])
            i += 1
        return out
```

Funciona porque, en orden lexicográfico, todas las palabras que empiezan por `prefix` son contiguas y empiezan justo donde `bisect_left` apunta.

Si de verdad necesitas el trie, esta es una versión compacta con `__slots__` para reducir la memoria por nodo:

```python
class TrieNode:
    __slots__ = ("children", "terminal")

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.terminal = False


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
        node.terminal = True

    def complete(self, prefix: str, limit: int = 10) -> list[str]:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return []
        out: list[str] = []
        stack = [(node, prefix)]
        while stack and len(out) < limit:
            cur, acc = stack.pop()
            if cur.terminal:
                out.append(acc)
            # apilar en orden inverso para sacar primero la rama menor: salida lexicográfica
            for ch, child in sorted(cur.children.items(), reverse=True):
                stack.append((child, acc + ch))
        return out
```

Test que fija el contrato de las dos y te permite cambiar de una a otra sin tocar al cliente:

```python
import random
import string


def test_bisect_y_trie_dan_lo_mismo():
    rng = random.Random(7)
    words = ["".join(rng.choices("abc", k=rng.randint(1, 5))) for _ in range(300)]
    index, trie = PrefixIndex(words), Trie()
    for w in set(words):
        trie.insert(w)
    for prefix in ["", "a", "ab", "abc", "c", "zz"]:
        assert index.complete(prefix, 50) == trie.complete(prefix, 50)
```

Un detalle que importa más que la estructura en español: normaliza antes de indexar y de consultar (`casefold()` y quitar acentos con `unicodedata.normalize("NFD", s)` filtrando los combinantes), porque el usuario que escribe «cancion» espera encontrar «canción».""",
            },
        ]
    },
    # 20) Bit manipulation en C (usuario en inglés)
    {
        "messages": [
            {"role": "user", "content": "Can you walk me through the common bit tricks in C (is power of two, count set bits, isolate the lowest set bit, set/clear/toggle a bit) and explain *why* each one works? I keep memorizing them and forgetting."},
            {
                "role": "assistant",
                "content": """Every one of these comes from a single fact: subtracting 1 from a binary number flips the lowest set bit to 0 and every bit below it to 1. Everything else is a consequence. Use `unsigned` types throughout; shifting into or out of the sign bit of a signed `int` is undefined behavior.

**`n & (n - 1)` clears the lowest set bit.**
`n = 0b1011000`, `n - 1 = 0b1010111`. The bits above the lowest set bit are identical in both; the lowest set bit is 1 in `n` and 0 in `n - 1`; everything below is 0 in `n`. The AND keeps only the bits above. Consequences:

- *Power of two*: exactly one bit set, so clearing it gives 0. `n != 0 && (n & (n - 1)) == 0`. The `n != 0` guard matters: `0 & 0xFFFFFFFF == 0` would otherwise claim 0 is a power of two.
- *Popcount in O(set bits)*: loop clearing the lowest bit until zero (Kernighan's method).

**`n & -n` isolates the lowest set bit.**
In two's complement, `-n = ~n + 1`. `~n` flips every bit; adding 1 ripples through the trailing ones (which were trailing zeros in `n`) and stops at the first 0 of `~n`, which is the lowest set bit of `n`. So `-n` agrees with `n` on that bit and below, and is its complement above. AND leaves only that bit. For unsigned types `-n` is well defined (modular arithmetic), which is one more reason to use them.

**Masks.** `1u << k` is a mask with only bit `k` set. Then: set with `|`, clear with `& ~`, toggle with `^`, test with `>> k & 1u`. Writing `1 << 31` with a plain `int` is UB because it overflows; `1u << 31` is fine. Shifting by `k >= width` is UB for any type, so validate `k` if it comes from input.

```c
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>

static bool is_power_of_two(uint32_t n) { return n != 0 && (n & (n - 1)) == 0; }

static unsigned popcount(uint32_t n) {
    unsigned count = 0;
    while (n) {
        n &= n - 1;   // drop the lowest set bit
        count++;
    }
    return count;
}

static uint32_t lowest_set_bit(uint32_t n) { return n & -n; }

static uint32_t set_bit(uint32_t x, unsigned k)    { return x | (UINT32_C(1) << k); }
static uint32_t clear_bit(uint32_t x, unsigned k)  { return x & ~(UINT32_C(1) << k); }
static uint32_t toggle_bit(uint32_t x, unsigned k) { return x ^ (UINT32_C(1) << k); }
static bool test_bit(uint32_t x, unsigned k)       { return (x >> k) & 1u; }

int main(void) {
    assert(is_power_of_two(1) && is_power_of_two(1024) && !is_power_of_two(0) && !is_power_of_two(12));
    assert(popcount(0) == 0 && popcount(0xFFu) == 8 && popcount(0x80000001u) == 2);
    assert(lowest_set_bit(0x58u) == 0x8u);          /* 0b1011000 -> 0b1000 */
    assert(set_bit(0, 3) == 8 && clear_bit(15, 0) == 14 && toggle_bit(5, 0) == 4);
    assert(test_bit(5, 2) && !test_bit(5, 1));
    assert(set_bit(0, 31) == 0x80000000u);          /* UB with a signed 1 << 31 */
    return 0;
}
```

Two things worth knowing beyond the tricks:

- For popcount in real code, use the compiler: `__builtin_popcount(n)` on GCC/Clang compiles to a single `POPCNT` instruction with `-mpopcnt` (or `-march=native`). C23 standardizes this as `stdc_count_ones` in `<stdbit.h>`, alongside `stdc_trailing_zeros` and `stdc_has_single_bit`, which is the standard spelling of the power-of-two test.
- `x >> k` on a negative signed value is implementation-defined (arithmetic on every mainstream compiler, but not guaranteed). If you need logical shifts, cast to the unsigned type first.""",
            },
        ]
    },
    # 21) Backtracking: N reinas, luego bitmasks (Python, multiturno)
    {
        "messages": [
            {"role": "user", "content": "Necesito generar todas las soluciones del problema de las N reinas en Python. Mi versión prueba cada casilla y comprueba el tablero entero en cada paso; con n=8 tarda minutos."},
            {
                "role": "assistant",
                "content": """Dos cambios convierten minutos en milisegundos: colocar **una reina por fila** (así nunca hay dos en la misma fila y el espacio de búsqueda baja de 64^8 a 8^8) y comprobar conflictos en **O(1)** con tres conjuntos en vez de recorrer el tablero.

La clave de los conjuntos: dos casillas `(r1, c1)` y `(r2, c2)` están en la misma diagonal si `r1 - c1 == r2 - c2`, y en la misma antidiagonal si `r1 + c1 == r2 + c2`. Basta guardar las columnas, las diferencias y las sumas ocupadas.

```python
from collections.abc import Iterator


def n_queens(n: int) -> Iterator[list[int]]:
    '''Genera cada solución como lista: solution[row] = columna de la reina en esa fila.'''
    cols: set[int] = set()
    diag: set[int] = set()       # row - col
    anti: set[int] = set()       # row + col
    placement: list[int] = []

    def place(row: int) -> Iterator[list[int]]:
        if row == n:
            yield placement.copy()
            return
        for col in range(n):
            if col in cols or (row - col) in diag or (row + col) in anti:
                continue                      # poda: la casilla está atacada
            cols.add(col); diag.add(row - col); anti.add(row + col)
            placement.append(col)
            yield from place(row + 1)
            placement.pop()                   # deshacer: vuelta atrás
            cols.remove(col); diag.remove(row - col); anti.remove(row + col)

    yield from place(0)
```

Es un generador para que puedas pedir la primera solución sin calcular las 92, o contarlas con `sum(1 for _ in n_queens(8))`.

El patrón de **backtracking** siempre tiene la misma forma: elegir → comprobar restricción → descender → **deshacer**. El `placement.copy()` al llegar al fondo es necesario porque la lista se sigue mutando después; sin la copia, todas las soluciones devueltas acabarían siendo la misma lista vacía.

Verificación con los valores conocidos de la secuencia (OEIS A000170):

```python
def test_n_queens_cuenta_conocida():
    assert [sum(1 for _ in n_queens(n)) for n in range(1, 9)] == [1, 0, 0, 2, 10, 4, 40, 92]


def test_n_queens_soluciones_validas():
    for sol in n_queens(6):
        assert len(set(sol)) == 6                                   # columnas distintas
        assert len({r - c for r, c in enumerate(sol)}) == 6         # diagonales distintas
        assert len({r + c for r, c in enumerate(sol)}) == 6         # antidiagonales distintas
```

En mi máquina, `n=8` tarda unos 10 ms y `n=10` (724 soluciones) menos de un segundo.""",
            },
            {"role": "user", "content": "Genial. Ahora solo necesito *contar* soluciones hasta n=14 y la versión con sets sigue tardando demasiado."},
            {
                "role": "assistant",
                "content": """Para contar, cambia los conjuntos por **máscaras de bits**: las tres restricciones caben en tres enteros y la poda pasa de tres búsquedas en `set` a una operación `&`. Además, en vez de iterar las `n` columnas y filtrar, iteras solo las columnas libres extrayendo bit a bit.

```python
def count_queens(n: int) -> int:
    full = (1 << n) - 1                      # n bits a 1: todas las columnas

    def solve(cols: int, left_diag: int, right_diag: int) -> int:
        if cols == full:
            return 1
        total = 0
        free = full & ~(cols | left_diag | right_diag)
        while free:
            bit = free & -free               # columna libre más baja
            free ^= bit                      # la consumimos
            total += solve(
                cols | bit,
                ((left_diag | bit) << 1) & full,   # la diagonal se desplaza una columna por fila
                (right_diag | bit) >> 1,
            )
        return total

    return solve(0, 0, 0)
```

Por qué funcionan las diagonales como desplazamientos: una reina en la columna `c` de la fila `r` ataca la columna `c+1` en la fila `r+1`, `c+2` en la `r+2`, etc. Si guardas «columnas atacadas por diagonales descendentes en la fila actual» y lo desplazas un bit a la izquierda al bajar de fila, obtienes exactamente las columnas atacadas en la siguiente. El `& full` descarta los bits que se salen del tablero.

```python
def test_count_queens():
    assert [count_queens(n) for n in range(1, 11)] == [1, 0, 0, 2, 10, 4, 40, 92, 352, 724]
    assert count_queens(12) == 14_200
```

Órdenes de magnitud en CPython 3.12: `n=12` (14.200 soluciones) alrededor de un segundo, `n=13` unos segundos y `n=14` (365.596 soluciones) decenas de segundos; cada `n` multiplica el trabajo por 5-6. Si necesitas más:

- **Simetría**: coloca la primera reina solo en la mitad izquierda del tablero y multiplica por 2 (con cuidado con la columna central cuando `n` es impar). Reduce el trabajo casi a la mitad.
- **PyPy** ejecuta esta misma función unas 20-30 veces más rápido sin cambiar nada.
- Si el objetivo es `n >= 16`, el algoritmo es el mismo pero en Go, Rust o C; `n=16` son 14,7 millones de soluciones y el árbol de búsqueda ya no es terreno de CPython.""",
            },
        ]
    },
    # 22) Memoización: caminos en cuadrícula, código exponencial del usuario (JS)
    {
        "messages": [
            {
                "role": "user",
                "content": """Esta función cuenta los caminos en una cuadrícula moviéndose solo a la derecha o abajo. Con 16×16 tarda segundos y con 18×18 no termina:

```js
function countPaths(rows, cols) {
  if (rows === 1 || cols === 1) return 1;
  return countPaths(rows - 1, cols) + countPaths(rows, cols - 1);
}
```

Es correcta (la probé con tableros pequeños), pero ¿por qué explota así?""",
            },
            {
                "role": "assistant",
                "content": """Explota porque calcula los mismos subproblemas una y otra vez. `countPaths(18, 18)` llama a `countPaths(17, 18)` y a `countPaths(18, 17)`, y las dos llaman a `countPaths(17, 17)`; a tres niveles de profundidad ya hay subproblemas repetidos 3 veces, a diez niveles cientos. El número de llamadas es del orden del propio resultado (cada hoja devuelve 1 y las sumas no se comparten): para 18×18 el resultado es 2.333.606.220, así que haces más de 4.600 millones de llamadas. Solo hay `rows × cols = 324` subproblemas distintos.

**Memoización**: la misma recursión, pero cada `(rows, cols)` se calcula una vez.

```js
function countPaths(rows, cols, memo = new Map()) {
  if (rows === 1 || cols === 1) return 1;
  const key = `${rows},${cols}`;
  if (memo.has(key)) return memo.get(key);
  const result = countPaths(rows - 1, cols, memo) + countPaths(rows, cols - 1, memo);
  memo.set(key, result);
  return result;
}
```

O(rows × cols) tiempo y memoria. La clave compuesta como cadena es necesaria porque `Map` compara arrays por referencia, no por contenido.

**De abajo arriba** (DP tabular): elimina la recursión y la caché, y solo necesita una fila porque `(r, c)` depende de `(r-1, c)` (lo que ya había en la celda) y `(r, c-1)` (la celda anterior en la misma pasada).

```js
function countPathsDP(rows, cols) {
  const row = new Array(cols).fill(1);   // primera fila: un único camino hasta cada celda
  for (let r = 1; r < rows; r++) {
    for (let c = 1; c < cols; c++) row[c] += row[c - 1]; // arriba + izquierda
  }
  return row[cols - 1];
}
```

**Fórmula cerrada**, porque este problema la tiene: un camino es una secuencia de `rows - 1` bajadas y `cols - 1` derechas en cualquier orden, es decir, `C(rows + cols - 2, rows - 1)`. A partir de ~30×30 el resultado supera `Number.MAX_SAFE_INTEGER` (2⁵³), así que con `BigInt`:

```js
function countPathsExact(rows, cols) {
  const n = BigInt(rows + cols - 2);
  const k = BigInt(Math.min(rows, cols) - 1);
  let result = 1n;
  for (let i = 1n; i <= k; i++) {
    result = (result * (n - k + i)) / i;   // división exacta en cada paso
  }
  return result;
}
```

Las tres coinciden en el rango seguro:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

test("countPaths: tres implementaciones coinciden", () => {
  for (let r = 1; r <= 12; r++) {
    for (let c = 1; c <= 12; c++) {
      const expected = countPathsDP(r, c);
      assert.equal(countPaths(r, c), expected);
      assert.equal(countPathsExact(r, c), BigInt(expected));
    }
  }
  assert.equal(countPathsDP(18, 18), 2_333_606_220);
  assert.equal(countPathsExact(31, 31), 118264581564861424n); // C(60, 30), fuera del rango de Number
});
```

Cuál usar: la memoizada cuando la recursión es natural y el espacio de estados es disperso (no visitas todos los `(r, c)`); la tabular cuando los visitas todos, por memoria y por evitar el límite de pila; la fórmula cuando existe, que aquí es el caso y es O(min(rows, cols)).""",
            },
        ]
    },
    # 23) Orden topológico con detección de ciclos (Go, revisor estricto, código roto)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto: señala primero los defectos, en orden de gravedad, y luego da la versión corregida."},
            {
                "role": "user",
                "content": """Orden de ejecución de tareas con dependencias (`deps[tarea] = tareas de las que depende`). Si hay un ciclo debería devolver error, pero con `a→b→a` se cae con `goroutine stack exceeds 1000000000-byte limit`:

```go
func topo(deps map[string][]string) []string {
	visited := map[string]bool{}
	var order []string
	var visit func(n string)
	visit = func(n string) {
		if visited[n] {
			return
		}
		for _, d := range deps[n] {
			visit(d)
		}
		visited[n] = true
		order = append(order, n)
	}
	for n := range deps {
		visit(n)
	}
	return order
}
```""",
            },
            {
                "role": "assistant",
                "content": """Defectos, de mayor a menor gravedad:

1. **Marca `visited` después de recorrer las dependencias.** Con `a→b→a`, `visit(a)` entra en `visit(b)`, que entra en `visit(a)`, que aún no está marcada, y así hasta agotar la pila. Un solo booleano no distingue «terminado» de «en curso», y esa distinción es exactamente lo que detecta un ciclo.
2. **No hay forma de devolver error.** La firma devuelve `[]string` y nada más; un ciclo es un dato de entrada inválido y debe salir como `error`, no como *panic* ni como lista incompleta.
3. **Salida no determinista.** `for n := range deps` itera el mapa en orden aleatorio por diseño de Go. El orden topológico resultante es válido cada vez, pero distinto, y eso hace tests intermitentes y despliegues que no se reproducen.
4. **Menor**: `order` empieza en `nil` y crece realojando; con el tamaño conocido conviene reservar.

Versión corregida con DFS de tres estados (blanco / gris / negro). «Gris» significa «en la pila de recursión»: llegar a un nodo gris es haber cerrado un ciclo.

```go
package tasks

import (
	"errors"
	"fmt"
	"slices"
	"strings"
)

var ErrCycle = errors.New("ciclo de dependencias")

type state uint8

const (
	unvisited state = iota
	inProgress       // en la pila de recursión
	done
)

// TopoOrder devuelve un orden en el que cada tarea aparece después de todas sus dependencias.
// Es determinista: a igual entrada, igual salida.
func TopoOrder(deps map[string][]string) ([]string, error) {
	states := make(map[string]state, len(deps))
	order := make([]string, 0, len(deps))
	var path []string // pila actual, solo para el mensaje de error

	var visit func(n string) error
	visit = func(n string) error {
		switch states[n] {
		case done:
			return nil
		case inProgress:
			cycle := append(slices.Clone(path), n)
			return fmt.Errorf("%w: %s", ErrCycle, strings.Join(cycle, " -> "))
		}
		states[n] = inProgress
		path = append(path, n)
		for _, d := range deps[n] {
			if err := visit(d); err != nil {
				return err
			}
		}
		path = path[:len(path)-1]
		states[n] = done
		order = append(order, n)
		return nil
	}

	keys := make([]string, 0, len(deps))
	for n := range deps {
		keys = append(keys, n)
	}
	slices.Sort(keys)
	for _, n := range keys {
		if err := visit(n); err != nil {
			return nil, err
		}
	}
	return order, nil
}
```

Tests que cubren los tres defectos graves:

```go
func TestTopoOrder(t *testing.T) {
	deps := map[string][]string{"build": {"lint", "test"}, "test": {"compile"}, "lint": {}, "compile": {}}
	got, err := TopoOrder(deps)
	if err != nil {
		t.Fatal(err)
	}
	pos := map[string]int{}
	for i, n := range got {
		pos[n] = i
	}
	for task, ds := range deps {
		for _, d := range ds {
			if pos[d] > pos[task] {
				t.Fatalf("%s aparece antes que su dependencia %s: %v", task, d, got)
			}
		}
	}
	again, _ := TopoOrder(deps)
	if !slices.Equal(got, again) {
		t.Fatalf("salida no determinista: %v vs %v", got, again)
	}
}

func TestTopoOrderCiclo(t *testing.T) {
	_, err := TopoOrder(map[string][]string{"a": {"b"}, "b": {"a"}})
	if !errors.Is(err, ErrCycle) {
		t.Fatalf("esperaba ErrCycle, got %v", err)
	}
}
```

El mensaje de error incluye el ciclo (`a -> b -> a`), que es lo que el usuario necesita para arreglar su configuración. Si los grafos pueden tener decenas de miles de nodos en cadena, la recursión de Go aguanta (la pila crece dinámicamente), pero la alternativa iterativa es el algoritmo de Kahn: grados de entrada, cola de nodos con grado 0, y si al terminar quedan nodos sin procesar, hay ciclo.""",
            },
        ]
    },
]

ROWS += [
    # 24) Intervalos: barrido para mínimo de salas (Python)
    {
        "messages": [
            {"role": "user", "content": "Tengo reservas de salas como (inicio, fin) en minutos desde medianoche y quiero saber cuántas salas necesito como mínimo para que ninguna reserva se solape. Lo intenté comparando cada reserva con todas las demás y no me cuadra cuando se solapan tres o más."},
            {
                "role": "assistant",
                "content": """Comparar parejas te dice si dos reservas chocan, pero el número de salas es el **máximo de reservas activas en un mismo instante**, y eso no sale de parejas. Se calcula con un barrido: conviertes cada reserva en dos eventos (`+1` al empezar, `-1` al terminar), los ordenas por tiempo y recorres llevando un contador. El máximo del contador es la respuesta. O(n log n) por la ordenación.

```python
def min_rooms(bookings: list[tuple[int, int]]) -> int:
    '''Mínimo de salas para alojar todas las reservas [start, end) sin solapes.'''
    events: list[tuple[int, int]] = []
    for start, end in bookings:
        if end <= start:
            raise ValueError(f"reserva inválida, fin <= inicio: {(start, end)}")
        events.append((start, +1))
        events.append((end, -1))
    # a igual tiempo, -1 (fin) ordena antes que +1 (inicio): una sala que se libera
    # a las 10:00 puede usarse por una reserva que empieza a las 10:00
    events.sort()
    active = best = 0
    for _, delta in events:
        active += delta
        best = max(best, active)
    return best
```

El detalle que decide la respuesta en los bordes es el orden de empate. Como las tuplas se comparan por componentes, `(600, -1)` va antes que `(600, +1)` y el fin se procesa primero. Eso implementa intervalos semiabiertos `[inicio, fin)`. Si en tu dominio una reserva de 9:00 a 10:00 y otra de 10:00 a 11:00 **sí** chocan (necesitas margen de limpieza, por ejemplo), invierte el criterio con `events.sort(key=lambda e: (e[0], -e[1]))` o, mejor, suma el margen al fin antes de generar los eventos.

Traza con `[(0, 30), (5, 10), (15, 20)]`: eventos ordenados `(0,+1) (5,+1) (10,-1) (15,+1) (20,-1) (30,-1)` → contador `1, 2, 1, 2, 1, 0` → 2 salas. ✓

```python
import pytest


def test_min_rooms():
    assert min_rooms([]) == 0
    assert min_rooms([(0, 30), (5, 10), (15, 20)]) == 2
    assert min_rooms([(0, 10), (10, 20)]) == 1          # se tocan, no se solapan
    assert min_rooms([(0, 10), (0, 10), (0, 10)]) == 3  # tres idénticas
    assert min_rooms([(0, 100), (10, 20), (30, 40), (35, 45)]) == 3
    with pytest.raises(ValueError):
        min_rooms([(10, 5)])
```

El mismo barrido resuelve la familia entera de problemas de intervalos con un pequeño cambio en lo que acumulas: fusionar intervalos solapados (emitir uno nuevo cada vez que el contador pasa de 0 a 1 y cerrarlo cuando vuelve a 0), tiempo total cubierto, o el instante con más reservas (guardar el tiempo cuando `best` cambia). Si además las reservas llegan en línea y necesitas asignar sala concreta a cada una, la variante es un *min-heap* con el fin de cada sala ocupada: reutilizas la sala cuyo fin es menor si ya ha terminado, y si no, abres otra.""",
            },
        ]
    },
    # 25) Cadenas y Unicode: normalización, unidades UTF-16, grafemas (JS, México)
    {
        "messages": [
            {"role": "system", "content": "Responde en español de México, en tono cercano pero técnico, y verifica cada afirmación con un ejemplo ejecutable."},
            {"role": "user", "content": "Oye, en JS `'mañana'.length` me da 6 pero la misma palabra pegada desde otro sistema me da 7 y además no son iguales con `===`. Y al invertir una cadena con banderas de países con `split('').reverse().join('')` me salen cuadritos. ¿Qué onda?"},
            {
                "role": "assistant",
                "content": r"""Son dos problemas distintos que se juntan: **normalización** (la «ñ» tiene dos representaciones) y **unidades de código UTF-16** (`length` y `split('')` no cuentan caracteres).

**1. La «ñ» de 7 letras.** Unicode permite escribir «ñ» como un solo punto de código precompuesto (U+00F1) o como «n» seguida de la tilde combinante (U+0303). Se ven igual, pero son secuencias distintas y `===` compara secuencias. La solución es normalizar antes de comparar o guardar; NFC es la forma precompuesta y la convención habitual.

```js
const a = "mañana";          // ñ precompuesta: U+00F1
const b = "mañana";    // n + U+0303 (tilde combinante)
a === b;                                    // false
a.length;                                   // 6
b.length;                                   // 7
a.normalize("NFC") === b.normalize("NFC");  // true
```

Normaliza en la frontera (al recibir datos de otro sistema, al guardar en base de datos) y asume NFC dentro de tu código. Lo mismo aplica a claves de objetos y a búsquedas.

**2. Las banderas rotas.** Las cadenas de JS son UTF-16: `length` cuenta unidades de 16 bits. Todo lo que está fuera del plano básico (emojis, muchos símbolos) ocupa dos unidades (un *par subrogado*), y `split('')` corta por unidad, partiendo cada par. Una bandera es además **dos** puntos de código (dos «indicadores regionales»), que juntos forman un solo grafema.

```js
const flag = "🇲🇽";
flag.length;          // 4 unidades UTF-16
[...flag].length;     // 2 puntos de código (el iterador de strings respeta los pares)
```

Para operar por «lo que el usuario ve como un carácter» necesitas segmentar en **grafemas** con `Intl.Segmenter` (Node 16+ y todos los navegadores actuales):

```js
function reverseGraphemes(text) {
  const segmenter = new Intl.Segmenter("es", { granularity: "grapheme" });
  return [...segmenter.segment(text)].map((s) => s.segment).reverse().join("");
}

reverseGraphemes("hola 🇲🇽");       // "🇲🇽 aloh"
reverseGraphemes("mañana");   // "anañam": la tilde viaja pegada a su n
```

Fíjate en que `[...text].reverse()` tampoco bastaría: invertiría los dos indicadores de la bandera (dando otra bandera o un cuadrito) y separaría la tilde combinante de su letra.

Resumen de qué usar para qué:

| Necesitas | Usa |
|---|---|
| Comparar o guardar texto | `normalize("NFC")` |
| Contar caracteres visibles | `[...new Intl.Segmenter(loc, {granularity: "grapheme"}).segment(s)].length` |
| Iterar puntos de código | `for (const ch of s)` o `[...s]` |
| Límite de longitud para una base de datos | `length` (si la columna es UTF-16) o `Buffer.byteLength(s, "utf8")` (si es bytes) |
| Comparar sin importar mayúsculas | `a.localeCompare(b, "es", { sensitivity: "base" }) === 0` |

Y en Python, por si compartes código con el backend: `len()` cuenta puntos de código (ni unidades ni grafemas), `unicodedata.normalize("NFC", s)` normaliza, y para grafemas necesitas el paquete `regex` con el patrón `\X`, porque la biblioteca estándar no segmenta.""",
            },
        ]
    },
    # 26) Análisis amortizado: append vs insert(0) (Python, multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Por qué se dice que `list.append` en Python es O(1) si cuando se llena la lista tiene que copiar todos los elementos a un array más grande? Eso es O(n)."},
            {
                "role": "assistant",
                "content": """Es O(1) **amortizado**: una operación concreta puede costar O(n), pero el coste total de `n` appends consecutivos es O(n), así que la media por operación es constante. No es una aproximación estadística ni una media sobre entradas aleatorias; es una cota exacta del coste acumulado.

El argumento (método agregado) con crecimiento por duplicación, que es el caso fácil de ver:

- Las copias ocurren cuando la lista tiene 1, 2, 4, 8, …, hasta `n` elementos.
- Elementos copiados en total: `1 + 2 + 4 + … + n < 2n`.
- Añadir los `n` elementos cuesta `n` escrituras.
- Total: menos de `3n` operaciones para `n` appends → menos de 3 por append.

La suma geométrica es lo que lo hace funcionar: cada copia es al menos el doble de grande que la anterior, así que las copias pequeñas se vuelven despreciables frente a la última. Si en vez de duplicar creciera en una cantidad fija (digamos 100 elementos cada vez), las copias costarían `100 + 200 + 300 + …`, que es O(n²) en total, y el append sería O(n) amortizado.

CPython no duplica: sobreasigna alrededor del 12,5 % más un pequeño fijo, redondeado a múltiplo de 4 (la fórmula en `listobject.c` es `new_allocated = (n + (n >> 3) + 6) & ~3`). Sigue siendo un factor multiplicativo, así que la suma sigue siendo geométrica y la cota sigue siendo O(1); solo hay más copias que con un factor 2, a cambio de desperdiciar menos memoria.

Puedes ver los saltos de capacidad midiendo el tamaño del objeto, que incluye el array de punteros:

```python
import sys

lst: list[int] = []
previous = sys.getsizeof(lst)
for i in range(64):
    lst.append(i)
    size = sys.getsizeof(lst)
    if size != previous:
        print(f"len={len(lst):>3}  bytes={size}")
        previous = size
```

Verás que el tamaño cambia en unas pocas longitudes (1, 5, 9, 17, 25, 33, 41 y 53 en CPython 3.12, por la fórmula de abajo) y se mantiene fijo entre ellas: esos appends intermedios son escrituras directas en espacio ya reservado.

La distinción importa cuando la latencia de una operación individual cuenta (un sistema de tiempo real no quiere una copia de 10⁸ punteros en medio de un append); ahí se usan estructuras que reparten el coste, como listas enlazadas de bloques. Para el resto de casos, «O(1) amortizado» es lo que necesitas saber: un bucle de `n` appends es lineal.""",
            },
            {"role": "user", "content": "Entonces `insert(0, x)` también es O(1) amortizado, ¿no? Es la misma lista."},
            {
                "role": "assistant",
                "content": """No. El análisis amortizado reparte un coste **ocasional** (la copia al crecer) entre muchas operaciones baratas. `insert(0, x)` tiene un coste **sistemático**: cada llamada desplaza los `n` elementos existentes una posición a la derecha, siempre, haya o no realojo. `n` inserciones al frente son `0 + 1 + 2 + … + (n-1) = O(n²)` desplazamientos, y ningún reparto lo arregla: O(n) por operación, también amortizado.

Mídelo:

```python
from collections import deque
from timeit import timeit

N = 50_000


def front_list() -> None:
    lst: list[int] = []
    for i in range(N):
        lst.insert(0, i)


def front_deque() -> None:
    dq: deque[int] = deque()
    for i in range(N):
        dq.appendleft(i)


print(f"list.insert(0, x): {timeit(front_list, number=1):.3f} s")
print(f"deque.appendleft:  {timeit(front_deque, number=1):.3f} s")
```

En un portátil, la lista tarda del orden de segundos y el `deque` unos pocos milisegundos; dobla `N` y la lista tardará cuatro veces más, el `deque` dos veces más.

`collections.deque` está implementado como una lista doblemente enlazada de bloques de 64 punteros, así que `append`, `appendleft`, `pop` y `popleft` son O(1) reales en los dos extremos. A cambio, el acceso por índice al medio es O(n), donde la lista es O(1). La regla de elección:

| Operación | `list` | `deque` |
|---|---|---|
| `append` / `pop` al final | O(1) amortizado | O(1) |
| insertar / quitar al frente | O(n) | O(1) |
| `x[i]` en el medio | O(1) | O(n) |
| `insert(i, x)` en el medio | O(n) | O(n) |

Si tu código hace `insert(0, …)` en un bucle, casi siempre es una cola (usa `deque`) o estás construyendo una lista al revés (haz `append` y un único `reverse()` al final, que es O(n) total).""",
            },
        ]
    },
    # 27) Caché LRU con Map en O(1) (JS, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "¿Cómo implemento una caché LRU con get y set en O(1) en JavaScript? Lo de la lista doblemente enlazada con hash map me parece muchísimo código para lo que es."},
            {
                "role": "assistant",
                "content": """En JavaScript no necesitas la lista enlazada: `Map` **conserva el orden de inserción** y permite borrar y reinsertar en O(1), así que el propio `Map` hace de lista de recencia. «Más reciente» es el final del mapa; «menos reciente», el principio.

```js
export class LRUCache {
  #map = new Map();
  #capacity;

  constructor(capacity) {
    if (!Number.isInteger(capacity) || capacity <= 0) {
      throw new RangeError(`capacity must be a positive integer, got ${capacity}`);
    }
    this.#capacity = capacity;
  }

  get(key) {
    if (!this.#map.has(key)) return undefined;
    const value = this.#map.get(key);
    this.#map.delete(key);      // borrar y reinsertar lo mueve al final: ahora es el más reciente
    this.#map.set(key, value);
    return value;
  }

  set(key, value) {
    if (this.#map.has(key)) {
      this.#map.delete(key);    // actualizar también cuenta como uso
    } else if (this.#map.size >= this.#capacity) {
      const oldest = this.#map.keys().next().value; // el primero del Map es el menos reciente
      this.#map.delete(oldest);
    }
    this.#map.set(key, value);
    return this;
  }

  has(key) {
    return this.#map.has(key);  // consultar existencia no cuenta como uso
  }

  get size() {
    return this.#map.size;
  }
}
```

Por qué cada operación es O(1): `has`, `get`, `delete` y `set` de `Map` son O(1) (amortizado, tabla hash), y `keys().next()` devuelve el primer elemento sin recorrer nada porque los iteradores de `Map` siguen la lista interna de inserción. Lo que la lista enlazada manual te daría a mano, V8 ya lo mantiene por ti.

Test con `node:test`, cubriendo el orden de expulsión, que es lo único que puede salir mal:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { LRUCache } from "./lru.js";

test("expulsa el menos usado recientemente", () => {
  const cache = new LRUCache(2);
  cache.set("a", 1).set("b", 2);
  assert.equal(cache.get("a"), 1);   // a pasa a ser el más reciente
  cache.set("c", 3);                 // expulsa b, no a
  assert.equal(cache.has("b"), false);
  assert.deepEqual([cache.get("a"), cache.get("c")], [1, 3]);
});

test("actualizar una clave la hace reciente", () => {
  const cache = new LRUCache(2);
  cache.set("a", 1).set("b", 2).set("a", 10);
  cache.set("c", 3);                 // expulsa b
  assert.deepEqual([cache.get("a"), cache.get("b"), cache.get("c")], [10, undefined, 3]);
});

test("rechaza capacidad inválida", () => {
  assert.throws(() => new LRUCache(0), RangeError);
});
```

Dos decisiones que conviene dejar explícitas en la API:

- `get` devuelve `undefined` tanto para «no está» como para «está y vale `undefined`». Si vas a cachear `undefined` como valor legítimo, usa `has` antes o devuelve un `{ hit, value }`.
- Si necesitas expiración por tiempo (TTL) además de LRU, guarda `{ value, expiresAt }` y comprueba la fecha en `get`, borrando la entrada si venció; el orden del `Map` sigue valiendo para la parte LRU.

Para referencia, Python ofrece lo mismo con `OrderedDict.move_to_end` y `popitem(last=False)`, y `functools.lru_cache` como decorador cuando lo que cacheas es una función pura.""",
            },
        ]
    },
    # 28) Prefix sums / difference array (Rust, usuario en inglés)
    {
        "messages": [
            {"role": "user", "content": "I have an array of 10^6 counters and 10^5 operations of the form \"add v to every index in [l, r]\". After all operations I need the final array. My nested loop is O(q·n) and takes minutes. Rust, if it matters."},
            {
                "role": "assistant",
                "content": """Use a **difference array**: record each range add as two point updates, then recover the final values with one prefix-sum pass. O(n + q) instead of O(n·q); your 10¹¹ inner-loop steps become about 1.2 × 10⁶.

The idea: if `diff[i] = a[i] - a[i-1]`, then adding `v` to `a[l..=r]` changes only two differences: `diff[l] += v` (the jump into the range) and `diff[r+1] -= v` (the jump out of it). Everything in between keeps the same differences. At the end, `a[i] = diff[0] + diff[1] + … + diff[i]`.

```rust
/// Applies `(l, r, v)` range additions to a zeroed array of length `n` and returns it.
/// Ranges are inclusive. Returns an error for any out-of-bounds or reversed range.
pub fn apply_range_adds(n: usize, ops: &[(usize, usize, i64)]) -> Result<Vec<i64>, String> {
    let mut diff = vec![0i64; n + 1]; // one extra slot so that r + 1 == n is always valid
    for &(l, r, v) in ops {
        if l > r || r >= n {
            return Err(format!("invalid range [{l}, {r}] for n = {n}"));
        }
        diff[l] += v;
        diff[r + 1] -= v;
    }
    let mut out = Vec::with_capacity(n);
    let mut running = 0i64;
    for d in &diff[..n] {
        running += d;
        out.push(running);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn brute(n: usize, ops: &[(usize, usize, i64)]) -> Vec<i64> {
        let mut a = vec![0i64; n];
        for &(l, r, v) in ops {
            for x in &mut a[l..=r] {
                *x += v;
            }
        }
        a
    }

    #[test]
    fn matches_brute_force() {
        let ops = [(0, 2, 5), (1, 4, -3), (4, 4, 10), (0, 4, 1)];
        assert_eq!(apply_range_adds(5, &ops).unwrap(), brute(5, &ops));
        assert_eq!(apply_range_adds(5, &ops).unwrap(), vec![6, 3, 3, -2, 8]);
    }

    #[test]
    fn rejects_bad_ranges() {
        assert!(apply_range_adds(3, &[(2, 1, 1)]).is_err());
        assert!(apply_range_adds(3, &[(0, 3, 1)]).is_err());
    }

    #[test]
    fn empty_input() {
        assert_eq!(apply_range_adds(0, &[]).unwrap(), Vec::<i64>::new());
    }
}
```

Trace for `(0, 2, 5)` on `n = 5`: `diff = [5, 0, 0, -5, 0, 0]`, prefix sums `5, 5, 5, 0, 0`. Correct.

Two notes on the details:

- `i64` rather than `i32`: 10⁵ operations with values up to 10⁹ overflow `i32` long before the end. If values can be larger, `i128` or checked arithmetic.
- The same trick works in 2D (add to a rectangle with four corner updates, then prefix-sum along rows and columns), and in reverse: prefix sums answer "sum of `a[l..=r]`" queries in O(1) after O(n) preprocessing.

When it stops applying: if range updates are **interleaved** with point queries, you cannot defer the prefix pass. Then use a Fenwick tree (binary indexed tree) over the difference array, which gives range update and point query in O(log n) each.""",
            },
        ]
    },
    # 29) Detección de ciclos en lista enlazada: Floyd (C)
    {
        "messages": [
            {"role": "user", "content": "¿Cómo detecto si una lista enlazada tiene un ciclo sin usar memoria extra, y por qué funciona lo de los dos punteros? Que no sea solo «funciona porque sí». En C."},
            {
                "role": "assistant",
                "content": """El algoritmo de Floyd («tortuga y liebre»): un puntero avanza de uno en uno y otro de dos en dos. Si la lista termina, el rápido llega a `NULL`. Si hay ciclo, se encuentran dentro de él. Memoria O(1), tiempo O(n).

**Por qué se encuentran.** Supón que la lista tiene μ nodos antes del ciclo y el ciclo tiene longitud λ. Tras μ pasos la tortuga entra en el ciclo; la liebre ya está dentro (entró antes, en el paso ⌈μ/2⌉). A partir de ahí los dos giran en el mismo anillo y la distancia de la liebre a la tortuga, medida en el sentido de avance, **disminuye exactamente en 1 por paso** (la liebre avanza 2, la tortuga 1). Como esa distancia es un entero entre 0 y λ-1, llega a 0 en menos de λ pasos. No pueden «saltarse» porque la distancia cambia de uno en uno.

**Por qué el segundo bucle encuentra el inicio del ciclo.** Cuando se encuentran, la tortuga ha dado `k` pasos y la liebre `2k`. La diferencia `k` es un múltiplo de λ (la liebre dio vueltas completas de más). La tortuga está a `k - μ` pasos de la entrada del ciclo, es decir, a `(múltiplo de λ) - μ`, lo que equivale a estar `μ` pasos **antes** de la entrada dando la vuelta al anillo. Si ahora un puntero sale desde `head` y otro desde el punto de encuentro, ambos a velocidad 1, tras μ pasos los dos están en la entrada del ciclo.

```c
#include <assert.h>
#include <stddef.h>
#include <stdio.h>

typedef struct Node {
    int value;
    struct Node *next;
} Node;

/* Devuelve el primer nodo del ciclo, o NULL si la lista termina. */
Node *find_cycle_start(Node *head) {
    Node *slow = head;
    Node *fast = head;
    while (fast != NULL && fast->next != NULL) {
        slow = slow->next;
        fast = fast->next->next;
        if (slow == fast) {             /* se encontraron dentro del ciclo */
            slow = head;
            while (slow != fast) {      /* ahora los dos avanzan de uno en uno */
                slow = slow->next;
                fast = fast->next;
            }
            return slow;                /* entrada del ciclo */
        }
    }
    return NULL;
}

int main(void) {
    Node nodes[5];
    for (int i = 0; i < 5; i++) {
        nodes[i].value = i;
        nodes[i].next = (i + 1 < 5) ? &nodes[i + 1] : NULL;
    }
    assert(find_cycle_start(&nodes[0]) == NULL);         /* lista lineal */
    assert(find_cycle_start(NULL) == NULL);              /* lista vacía */

    nodes[4].next = &nodes[2];                           /* 0 -> 1 -> 2 -> 3 -> 4 -> 2 */
    assert(find_cycle_start(&nodes[0]) == &nodes[2]);    /* mu = 2, lambda = 3 */

    nodes[4].next = &nodes[4];                           /* ciclo de un solo nodo */
    assert(find_cycle_start(&nodes[0]) == &nodes[4]);

    nodes[0].next = &nodes[0];                           /* el head se apunta a sí mismo */
    assert(find_cycle_start(&nodes[0]) == &nodes[0]);

    puts("ok");
    return 0;
}
```

La condición del `while` comprueba `fast` y `fast->next` antes de desreferenciar `fast->next->next`; es el único sitio donde este algoritmo se suele romper (lista de longitud par sin ciclo). Los dos últimos casos del test (ciclo de longitud 1 y ciclo que empieza en `head`, μ = 0) son los que cubren los extremos de la demostración.

Si además necesitas la longitud del ciclo, desde el punto de encuentro avanza un puntero hasta volver a él contando pasos: eso es λ.""",
            },
        ]
    },
    # 30) Greedy vs DP: cambio de monedas y sistemas canónicos (Rust, multiturno)
    {
        "messages": [
            {"role": "user", "content": "Para dar cambio con el mínimo de monedas uso greedy: siempre la moneda más grande que quepa. Con monedas {1, 3, 4} y cantidad 6 me devuelve 3 monedas (4+1+1) pero un test espera 2. ¿El test está mal?"},
            {
                "role": "assistant",
                "content": """El test está bien: `3 + 3` son dos monedas. Greedy solo es óptimo para sistemas de monedas «canónicos» (euro, dólar, peso: cada moneda es «suficientemente» mayor que la anterior); con `{1, 3, 4}` elegir el 4 te deja un 2 que cuesta dos monedas de 1, mientras que renunciar al 4 permite `3 + 3`. Greedy no mira hacia delante y por eso falla.

La solución general es programación dinámica: `best[x]` = mínimo de monedas para `x`, calculado desde 0 hacia arriba probando cada moneda como «la última».

```rust
/// Devuelve las monedas (en algún orden) que suman `amount` con el mínimo número de ellas,
/// o `None` si `amount` no es alcanzable. Todas las monedas deben ser > 0.
pub fn min_coins(coins: &[u32], amount: u32) -> Option<Vec<u32>> {
    assert!(coins.iter().all(|&c| c > 0), "las monedas deben ser positivas");
    let amount = amount as usize;
    // best[x] = Some((número de monedas, última moneda usada)) o None si x no es alcanzable
    let mut best: Vec<Option<(u32, u32)>> = vec![None; amount + 1];
    best[0] = Some((0, 0));
    for x in 1..=amount {
        for &c in coins {
            let c_us = c as usize;
            if c_us > x {
                continue;
            }
            if let Some((n, _)) = best[x - c_us] {
                let improves = best[x].map_or(true, |(m, _)| n + 1 < m);
                if improves {
                    best[x] = Some((n + 1, c));
                }
            }
        }
    }
    let mut out = Vec::new();
    let mut x = amount;
    while x > 0 {
        let (_, c) = best[x]?;   // reconstrucción hacia atrás por la última moneda
        out.push(c);
        x -= c as usize;
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn caso_del_usuario() {
        let mut got = min_coins(&[1, 3, 4], 6).unwrap();
        got.sort_unstable();
        assert_eq!(got, vec![3, 3]);
    }

    #[test]
    fn inalcanzable_y_cero() {
        assert_eq!(min_coins(&[2], 3), None);
        assert_eq!(min_coins(&[2], 0), Some(vec![]));
    }

    #[test]
    fn sistema_canonico_coincide_con_greedy() {
        assert_eq!(min_coins(&[1, 2, 5, 10, 20, 50], 93).unwrap().len(), 5); // 50+20+20+2+1
    }
}
```

Coste O(amount × coins) en tiempo y O(amount) en memoria. Traza de `best` para `{1, 3, 4}`: `best[1]=1, best[2]=2, best[3]=1, best[4]=1, best[5]=2 (4+1), best[6]=2 (3+3)`; en `x=6`, la moneda 3 llega desde `best[3]=1` y gana a la moneda 4, que llegaría desde `best[2]=2`.

El `Option` en el resultado es deliberado: con monedas `{2}` y cantidad 3 no hay solución, y devolver `0` o un vector vacío sería mentir.""",
            },
            {"role": "user", "content": "¿Hay alguna forma de saber si para un conjunto de monedas dado greedy sí sirve? La DP es más lenta y la mayoría de mis sistemas son normales."},
            {
                "role": "assistant",
                "content": """Sí, y se puede decidir con un test finito. El resultado de Kozen y Zaks (1994): si un sistema de monedas (con la moneda 1 incluida) **no** es canónico, el contraejemplo más pequeño es menor que la suma de las dos monedas mayores. Así que basta comparar greedy con la DP para todas las cantidades por debajo de `c_max + c_segunda`: si coinciden ahí, coinciden en todas partes.

```rust
pub fn greedy(coins_desc: &[u32], mut amount: u32) -> Vec<u32> {
    let mut out = Vec::new();
    for &c in coins_desc {
        while amount >= c {
            amount -= c;
            out.push(c);
        }
    }
    out
}

/// `true` si greedy es óptimo para toda cantidad con estas monedas.
/// Requiere que la moneda 1 esté presente (todo importe es alcanzable).
pub fn is_canonical(coins: &[u32]) -> bool {
    let mut asc = coins.to_vec();
    asc.sort_unstable();
    asc.dedup();
    assert_eq!(asc.first(), Some(&1), "el sistema necesita la moneda 1");
    if asc.len() == 1 {
        return true;
    }
    let limit = asc[asc.len() - 1] + asc[asc.len() - 2]; // cota de Kozen-Zaks
    let desc: Vec<u32> = asc.iter().rev().copied().collect();
    (1..limit).all(|x| {
        let optimal = min_coins(&asc, x).expect("alcanzable: hay moneda 1").len();
        greedy(&desc, x).len() == optimal
    })
}

#[cfg(test)]
mod canonical_tests {
    use super::*;

    #[test]
    fn sistemas_conocidos() {
        assert!(is_canonical(&[1, 2, 5, 10, 20, 50, 100, 200])); // euro
        assert!(is_canonical(&[1, 5, 10, 25]));                   // dólar sin el medio dólar
        assert!(!is_canonical(&[1, 3, 4]));                       // tu caso: falla en 6
        assert!(!is_canonical(&[1, 5, 8]));                       // falla en 10: 5+5 vs 8+1+1
        assert!(!is_canonical(&[1, 10, 25]));                     // falla en 30: 10+10+10 vs 25+1×5
    }
}
```

El coste del test es `O(limit × coins × limit)` por la DP en cada cantidad, pero `limit` es del orden de las monedas (unos cientos para sistemas reales) y se ejecuta **una vez** por sistema, al cargarlo. Después, para cada cambio real, usas greedy (O(coins)) si el sistema pasó el test y la DP si no.

Diseño que te deja un solo punto de decisión:

```rust
pub struct CoinSystem {
    desc: Vec<u32>,
    canonical: bool,
}

impl CoinSystem {
    pub fn new(coins: &[u32]) -> Self {
        let canonical = is_canonical(coins);
        let mut desc = coins.to_vec();
        desc.sort_unstable_by(|a, b| b.cmp(a));
        desc.dedup();
        Self { desc, canonical }
    }

    pub fn change(&self, amount: u32) -> Vec<u32> {
        if self.canonical {
            greedy(&self.desc, amount)
        } else {
            min_coins(&self.desc, amount).expect("la moneda 1 garantiza solución")
        }
    }
}
```

El cliente llama a `change` y no sabe ni le importa qué algoritmo corre por debajo; el test de arriba es la prueba de que las dos ramas dan el mismo número de monedas en el caso canónico.""",
            },
        ]
    },
]
