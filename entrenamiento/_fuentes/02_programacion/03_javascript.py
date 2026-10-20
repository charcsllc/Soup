"""JavaScript moderno (ES2023+, Node 20/22): runtime, asincronía, datos, herramientas y errores clásicos.

30 filas. Temas: event loop y microtareas, forEach async y rechazos no capturados, closures,
this/bind/arrow, ESM vs CommonJS, generadores asíncronos, Map/Set, WeakMap, copias y
structuredClone, fechas con Intl (Temporal como propuesta), regex, fetch con AbortController,
streams de Node, errores con `cause`, npm/pnpm y package.json, depuración con --inspect,
memoización, debounce, == frente a ===, coma flotante, hoisting y TDZ, toSorted y
Object.groupBy, límite de concurrencia, worker_threads, node:test, ?? frente a ||, herramientas
del proyecto, JSON y BigInt, AsyncLocalStorage y ordenación con Intl.Collator.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Event loop: microtareas frente a macrotareas (intermedio, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """No entiendo el orden de este código. Esperaba `A C E B D` porque el `setTimeout` está antes que la promesa:

```js
async function main() {
  console.log('A');
  await null;
  console.log('B');
}

setTimeout(() => console.log('C'), 0);
main();
Promise.resolve().then(() => console.log('D'));
console.log('E');
```

Pero sale `A E B D C`. ¿Por qué el timeout de 0 ms se va al final?""",
            },
            {
                "role": "assistant",
                "content": """Porque `setTimeout(fn, 0)` no significa «ahora»: significa «encola una **macrotarea** para cuando venza el temporizador». Y el motor no toca ninguna macrotarea hasta vaciar por completo la cola de **microtareas**, que es donde van las continuaciones de `await` y los `.then`. Por eso B y D adelantan a C aunque se registren después.

Traza paso a paso:

| Paso | Qué se ejecuta | Microtareas | Timers | Salida |
|---|---|---|---|---|
| 1 | `setTimeout(...)` registra C | — | [C] | |
| 2 | `main()` corre síncrono hasta el `await` | — | [C] | A |
| 3 | `await null` suspende `main` y encola su continuación | [B] | [C] | |
| 4 | `Promise.resolve().then(...)` | [B, D] | [C] | |
| 5 | `console.log('E')` | [B, D] | [C] | E |
| 6 | Pila vacía: se vacían las microtareas en orden FIFO | [] | [C] | B, D |
| 7 | El event loop entra en la fase de timers | [] | [] | C |

La regla completa: código síncrono → **todas** las microtareas (incluidas las que se encolen mientras se vacía la cola) → una macrotarea → otra vez todas las microtareas → siguiente macrotarea.

Consecuencia práctica: una cadena de microtareas que se reencola a sí misma bloquea timers y E/S igual que un bucle infinito.

```js
function starve() {
  Promise.resolve().then(starve); // el loop nunca llega a la fase de timers
}
```

Tres matices de Node que conviene conocer:

- **`process.nextTick` tiene su propia cola.** En un archivo CommonJS (`.cjs`) se vacía antes que las promesas: si añades `process.nextTick(() => console.log('tick'))` a tu ejemplo, `tick` sale justo después de E y antes de B. En ESM el módulo se evalúa dentro de un trabajo asíncrono y ese orden relativo puede invertirse, así que no construyas lógica que dependa de él.
- **`setTimeout(fn, 0)` frente a `setImmediate(fn)`** en el script principal no tiene orden garantizado (depende de cuánto tardó en arrancar el loop). Dentro de un callback de E/S, `setImmediate` va siempre primero.
- **Para ceder el control** a la E/S en mitad de un trabajo largo, una microtarea no sirve; necesitas una macrotarea:

```js
import { setImmediate as yieldToLoop } from 'node:timers/promises';

export async function handleAll(items, handleItem) {
  for (const [index, item] of items.entries()) {
    handleItem(item);
    if (index % 1000 === 0) await yieldToLoop(); // deja respirar a timers y sockets
  }
}
```

Comprobación: añade `setTimeout(() => console.log('C2'), 0)` dentro del `.then` de D. Saldrá `A E B D C C2`: C2 se registra cuando C ya estaba esperando en la lista de timers, y ambos tienen el mismo retardo.""",
            },
        ]
    },
    # 2) forEach con callback async y rechazo no capturado (intermedio, código roto, México)
    {
        "messages": [
            {
                "role": "user",
                "content": """Oigan, tengo un script que sincroniza usuarios con una API y hace cosas raras: imprime «listo» antes de terminar y a veces truena el proceso completo.

```js
// sync.mjs
const ids = [41, 42, 43];

async function saveUser(id) {
  const res = await fetch(`https://api.example.com/users/${id}`, { method: 'PUT' });
  if (!res.ok) throw new Error(`HTTP ${res.status} para ${id}`);
}

try {
  ids.forEach(async (id) => {
    await saveUser(id);
  });
  console.log('listo');
} catch (err) {
  console.error('falló la sincronización', err);
}
```

Cuando la API regresa 500 sale esto y el proceso se muere, aunque tengo try/catch:

```
listo
file:///home/dev/sync.mjs:6
  if (!res.ok) throw new Error(`HTTP ${res.status} para ${id}`);
                     ^

Error: HTTP 500 para 42
    at saveUser (file:///home/dev/sync.mjs:6:22)

Node.js v20.12.2
```""",
            },
            {
                "role": "assistant",
                "content": """Son dos síntomas del mismo error: **`forEach` ignora lo que devuelve su callback**. Tu callback es `async`, así que devuelve una promesa por cada id, y nadie las espera.

1. **«listo» sale primero.** `forEach` lanza los tres callbacks, cada uno se suspende en su primer `await` y `forEach` termina de forma síncrona. El `console.log('listo')` corre antes de que llegue cualquier respuesta HTTP.
2. **El try/catch no atrapa nada.** Solo envuelve la parte síncrona. Cuando la promesa del id 42 se rechaza, ya saliste del `try` hace rato y esa promesa no tiene ningún `.catch`. Desde Node 15 el modo por defecto es `--unhandled-rejections=throw`: un rechazo sin manejar se convierte en excepción no capturada y el proceso termina con código 1.

El arreglo es usar una construcción que **sí espere**. Elige según lo que necesites.

**En paralelo, reportando todos los fallos** (lo normal si la API aguanta las peticiones simultáneas):

```js
// sync.mjs (Node 20+, ESM: se permite await en el nivel superior)
const ids = [41, 42, 43];

async function saveUser(id) {
  const res = await fetch(`https://api.example.com/users/${id}`, { method: 'PUT' });
  if (!res.ok) throw new Error(`HTTP ${res.status} para ${id}`);
}

const results = await Promise.allSettled(ids.map((id) => saveUser(id)));
const failures = results
  .map((result, index) => ({ id: ids[index], result }))
  .filter(({ result }) => result.status === 'rejected');

if (failures.length > 0) {
  for (const { id, result } of failures) {
    console.error(`falló ${id}:`, result.reason.message);
  }
  process.exitCode = 1; // deja terminar la salida pendiente, a diferencia de process.exit(1)
} else {
  console.log('listo');
}
```

`allSettled` no se corta en el primer error: obtienes el estado de los tres. Con `Promise.all` el primer rechazo descartaría el resultado de los demás (aunque las peticiones seguirían en vuelo).

**En secuencia** (si la API tiene límite de peticiones o el orden importa):

```js
for (const id of ids) {
  await saveUser(id); // un error corta el bucle y sí lo atrapa un try/catch que lo envuelva
}
```

Dos cosas para que no vuelva a pasar:

- Si usas TypeScript con `typescript-eslint`, la regla `@typescript-eslint/no-misused-promises` marca exactamente este patrón: una función `async` pasada donde se espera un callback que devuelve `void`.
- Un `process.on('unhandledRejection', ...)` sirve como red de seguridad para registrar el error y poner `process.exitCode = 1`, no para silenciarlo. Si lo usas para tragarte rechazos, el bug sigue ahí, solo que invisible.

Comprobación rápida: sustituye `saveUser` por `async (id) => { if (id === 42) throw new Error('HTTP 500 para 42'); }`. Debe imprimir `falló 42: HTTP 500 para 42`, no imprimir «listo», y `echo $?` debe dar `1`.""",
            },
        ]
    },
    # 3) Closures y var en un bucle (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": """estoy aprendiendo js, por qué esto imprime 3, 3, 3 y no 0, 1, 2??

```js
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100);
}
```""",
            },
            {
                "role": "assistant",
                "content": """Porque las tres funciones flecha comparten **la misma variable `i`**, y cuando se ejecutan (100 ms después) el bucle ya terminó y dejó `i` en 3.

Dos ideas lo explican:

1. **Una closure captura la variable, no su valor.** La función `() => console.log(i)` guarda una referencia al «sitio» donde vive `i`. Lee lo que haya ahí en el momento de ejecutarse, no lo que había al crearse.
2. **`var` tiene alcance de función, no de bloque.** Solo existe una `i` para todo el bucle. Las tres closures apuntan a ella.

Línea de tiempo: el bucle corre entero de forma síncrona (`i` pasa por 0, 1, 2 y termina en 3), registra tres timers y, después, cada timer lee la única `i`, que vale 3.

**El arreglo: `let`.**

```js
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100);
}
// 0, 1, 2
```

Con `let`, el lenguaje crea **una variable nueva en cada iteración** (copiando el valor de la anterior). Cada closure captura su propia `i`.

Las closures no son un problema, son una herramienta. Por ejemplo, para tener estado privado sin clases:

```js
function makeCounter() {
  let count = 0; // nadie puede tocarla desde fuera
  return {
    increment: () => ++count,
    current: () => count,
  };
}

const a = makeCounter();
const b = makeCounter();
a.increment();
a.increment();
b.increment();
console.log(a.current(), b.current()); // 2 1
```

Cada llamada a `makeCounter` crea un `count` distinto, y las funciones devueltas lo recuerdan.

Comprobación sin esperar timers:

```js
const withVar = [];
for (var j = 0; j < 3; j++) withVar.push(() => j);
console.log(withVar.map((fn) => fn())); // [3, 3, 3]

const withLet = [];
for (let k = 0; k < 3; k++) withLet.push(() => k);
console.log(withLet.map((fn) => fn())); // [0, 1, 2]
```

Regla práctica: en código moderno no uses `var`. ESLint tiene la regla `no-var` para avisarte, y `no-loop-func` señala funciones creadas dentro de un bucle que leen variables que el bucle modifica.""",
            },
        ]
    },
    # 4) this, bind y funciones flecha (intermedio, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo esta clase y cuando se resuelve la promesa me salta `TypeError: Cannot read properties of undefined (reading 'cache')`. Si llamo `loader.handleResponse(data)` a mano funciona perfecto.

```js
class UserLoader {
  constructor(api) {
    this.api = api;
    this.cache = new Map();
  }

  handleResponse(user) {
    this.cache.set(user.id, user);
    return user;
  }

  load(id) {
    return this.api.getUser(id).then(this.handleResponse);
  }
}
```""",
            },
            {
                "role": "assistant",
                "content": """`this` no depende de dónde se define la función, sino de **cómo se llama**. Al escribir `.then(this.handleResponse)` pasas la función suelta, sin el objeto. Cuando la promesa se resuelve, `.then` la invoca como `fn(user)`, sin nada delante del punto. El cuerpo de una clase siempre está en modo estricto, así que `this` vale `undefined` y `this.cache` revienta.

Cuando haces `loader.handleResponse(data)`, el `loader.` delante de la llamada es lo que fija `this`. Por eso a mano funciona.

El cambio más pequeño es una función flecha en el punto de la llamada. Las flechas no tienen `this` propio: usan el de la función que las rodea, que aquí es `load`, donde `this` sí es la instancia.

```js
load(id) {
  return this.api.getUser(id).then((user) => this.handleResponse(user));
}
```

Prueba mínima con una API falsa:

```js
const fakeApi = { getUser: async (id) => ({ id, name: 'Ana' }) };
const loader = new UserLoader(fakeApi);

const user = await loader.load(7);
console.assert(loader.cache.get(7) === user, 'debería quedar en caché');
```

El mismo error aparece en otros sitios con la misma causa: `element.addEventListener('click', this.onClick)` (ahí `this` será el elemento), `setTimeout(this.tick, 1000)` o desestructurar un método: `const { handleResponse } = loader`.""",
            },
            {"role": "user", "content": "Ok, y entre las opciones, ¿cuál es mejor? En el equipo unos usan campos con arrow para todo (`handleResponse = (user) => {...}`) y otros hacen bind en el constructor."},
            {
                "role": "assistant",
                "content": """Ninguna es «la buena» para todo; difieren en dónde vive la función y eso tiene consecuencias.

| | Flecha en la llamada | `bind` en el constructor | Campo de clase con flecha |
|---|---|---|---|
| Dónde vive el método | prototipo (uno compartido) | prototipo + copia ligada por instancia | solo en la instancia |
| Memoria con 10 000 instancias | 1 método | 10 000 funciones ligadas | 10 000 funciones |
| Subclase que lo redefine | funciona | funciona | **se rompe** (ver abajo) |
| `vi.spyOn(UserLoader.prototype, 'handleResponse')` | funciona | solo si espías antes de crear la instancia | no funciona: no está en el prototipo |
| Referencia estable para `removeEventListener` | no | sí | sí |

La trampa de los campos con flecha en herencia:

```js
class Base {
  handleResponse = (user) => 'base';
}
class Child extends Base {
  handleResponse(user) { return 'child'; } // método del prototipo
}
console.log(new Child().handleResponse()); // 'base'
```

El campo se asigna en la instancia durante el constructor de `Base`, y una propiedad propia de la instancia tapa cualquier método del prototipo. El método de `Child` nunca se ejecuta y no hay error que te avise.

Mi recomendación:

1. **Por defecto, métodos normales** y flecha en el punto de la llamada cuando pasas el método como callback. Es explícito y no cuesta memoria por instancia.
2. **Campo con flecha** solo cuando necesitas una referencia estable para quitar el listener después, que es su razón de ser real.
3. **`bind` en el constructor** queda como alternativa al punto 2 si la clase tiene subclases; hoy apenas aporta nada más.

Y para el caso de los listeners hay una opción moderna que evita la referencia estable: `AbortController`.

```js
class ResizeWatcher {
  #controller = new AbortController();

  start() {
    window.addEventListener('resize', () => this.measure(), { signal: this.#controller.signal });
  }

  stop() {
    this.#controller.abort(); // quita todos los listeners registrados con esa señal
  }

  measure() {
    this.width = window.innerWidth;
  }
}
```

Con eso la regla del equipo puede ser simple: métodos en el prototipo siempre, flechas solo en el punto de uso.""",
            },
        ]
    },
    # 5) ESM vs CommonJS: __dirname y archivos de configuración (inglés pidiendo español)
    {
        "messages": [
            {
                "role": "user",
                "content": """Quick one, but please answer in Spanish so I can share it with my team in Lima. After adding `"type": "module"` to our package.json (Node 20) I get:

```
ReferenceError: __dirname is not defined in ES module scope
```

And our `jest.config.js`, which uses `module.exports`, now fails with `ReferenceError: module is not defined in ES module scope`. What changed and what's the clean fix?""",
            },
            {
                "role": "assistant",
                "content": """Lo que cambió: `"type": "module"` hace que **todo `.js` de ese paquete se cargue como módulo ES (ESM)**, no como CommonJS (CJS). Y ESM no tiene las variables que Node inyectaba en cada archivo CJS: `require`, `module`, `exports`, `__filename` y `__dirname`. No es un bug, es otro sistema de módulos.

Cómo decide Node el formato de cada archivo:

| Archivo | Formato |
|---|---|
| `.mjs` | siempre ESM |
| `.cjs` | siempre CommonJS |
| `.js` | según el campo `"type"` del `package.json` más cercano (`"commonjs"` si no existe) |

**1. `__dirname` y `__filename`.** Desde Node 20.11 hay equivalentes directos:

```js
import { join } from 'node:path';

const templatesDir = join(import.meta.dirname, 'templates');
console.log(import.meta.filename); // ruta absoluta de este archivo
```

Si alguien del equipo usa una versión 20.x anterior a la 20.11, la forma portable es:

```js
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const currentFile = fileURLToPath(import.meta.url);
const currentDir = dirname(currentFile);
```

`fileURLToPath` importa: `import.meta.url` es una URL `file:///...` y en Windows su `pathname` no es una ruta válida.

**2. `jest.config.js`.** Tienes dos salidas; elige una y aplícala a todos los archivos de configuración:

- Renombrarlo a `jest.config.cjs` y dejar el `module.exports`. Es el cambio mínimo y sirve para cualquier herramienta que todavía cargue su configuración con `require`.
- Convertirlo a ESM: `export default { testEnvironment: 'node' };`. Jest acepta configuración ESM.

Revisa también `.eslintrc.js`, `postcss.config.js` y similares: les pasa lo mismo.

**3. Si necesitas `require` dentro de un archivo ESM** (por ejemplo, para cargar un JSON o un paquete CJS de forma síncrona):

```js
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const pkg = require('./package.json');
```

**4. Interoperabilidad entre los dos mundos:**

- ESM puede importar CJS: `module.exports` llega como `default`, y Node intenta detectar también exportaciones con nombre.
- CJS **no** podía hacer `require()` de un ESM: fallaba con `ERR_REQUIRE_ESM` y la salida era `await import()`. Desde Node 22.12 y 20.19 se permite `require()` de módulos ESM que no usen `await` en el nivel superior.

Comprobación para el equipo:

```bash
node -p "process.versions.node"            # debe ser 20.11 o mayor para import.meta.dirname
node -e "import('./src/paths.js').then(m => console.log(m))"
```

Y un `grep -rn "__dirname\\|module.exports\\|require(" src/` antes del cambio les dice exactamente qué archivos hay que tocar.""",
            },
        ]
    },
    # 6) Generadores asíncronos para paginar una API (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una API paginada por cursor (`?cursor=...`, devuelve `{ items, nextCursor }`). Quiero recorrer todos los items sin cargarlo todo en memoria y poder cortar en cuanto encuentre lo que busco. ¿Generadores asíncronos? ¿Cómo se hace bien, incluyendo que no pida páginas de más?",
            },
            {
                "role": "assistant",
                "content": """Sí: un generador asíncrono (`async function*`) consumido con `for await...of` es exactamente esa herramienta. El generador se **suspende en cada `yield`** y solo continúa cuando el consumidor pide el siguiente elemento, así que la página 2 no se pide hasta que alguien termina de leer la página 1.

```js
// paginate.js (Node 20+, ESM)
export async function* paginate(baseUrl, { signal } = {}) {
  let cursor = null;
  let pages = 0;
  try {
    do {
      const url = new URL(baseUrl);
      if (cursor) url.searchParams.set('cursor', cursor);

      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`GET ${url} -> HTTP ${res.status}`);
      const { items, nextCursor } = await res.json();
      pages += 1;

      yield* items; // entrega los items de uno en uno
      cursor = nextCursor;
    } while (cursor);
  } finally {
    // se ejecuta al agotar las páginas, si el consumidor hace break o si algo lanza
    console.debug(`paginate: ${pages} página(s) leídas`);
  }
}
```

Uso con corte temprano:

```js
import { paginate } from './paginate.js';

for await (const order of paginate('https://api.example.com/orders')) {
  if (order.status === 'failed') {
    console.log('primer pedido fallido:', order.id);
    break; // llama a return() del generador: corre el finally y no se piden más páginas
  }
}
```

Por qué funciona el corte: `break` dentro de `for await` invoca `return()` sobre el generador, que estaba suspendido en un `yield`. El generador se reanuda con una «salida forzada», ejecuta el `finally` y termina. No queda ningún `fetch` pendiente.

Detalles que suelen morder:

1. **Un generador se consume una sola vez.** Si lo recorres dos veces, la segunda no devuelve nada. Llama a `paginate(...)` de nuevo.
2. **`signal` para cancelar desde fuera.** Si el usuario cierra la página o vence un plazo, `AbortSignal.timeout(10_000)` corta el `fetch` en curso y el error sale por el `for await`.
3. **Los iterator helpers de Node 22** (`.map`, `.filter`, `.take`, `.toArray`) existen para iteradores **síncronos**; para asíncronos siguen siendo una propuesta. Un `take` propio es corto:

```js
export async function* take(iterable, limit) {
  if (limit <= 0) return;
  let count = 0;
  for await (const item of iterable) {
    yield item;
    if (++count >= limit) return; // return dentro de for await también cierra la fuente
  }
}

// Node 22+: Array.fromAsync recoge un iterable asíncrono en un array
const first50 = await Array.fromAsync(take(paginate('https://api.example.com/orders'), 50));
```

Test que demuestra que no se piden páginas de más, con el runner nativo de Node:

```js
// paginate.test.js -> node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { paginate } from './paginate.js';

test('no pide la página siguiente si el consumidor corta antes', async (t) => {
  const pages = {
    '': { items: [1, 2, 3], nextCursor: 'p2' },
    p2: { items: [4, 5, 6], nextCursor: null },
  };
  const fetchMock = t.mock.method(globalThis, 'fetch', async (url) => {
    const cursor = new URL(url).searchParams.get('cursor') ?? '';
    return Response.json(pages[cursor]);
  });

  const seen = [];
  for await (const item of paginate('https://api.test/items')) {
    seen.push(item);
    if (seen.length === 2) break;
  }

  assert.deepEqual(seen, [1, 2]);
  assert.equal(fetchMock.mock.callCount(), 1);
});
```

Si quitas el `break`, `seen` debe acabar en `[1, 2, 3, 4, 5, 6]` y `callCount()` en 2: es el segundo caso que conviene añadir al mismo archivo.""",
            },
        ]
    },
    # 7) Map frente a objeto y operaciones con Set (intermedio, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Hice un contador de palabras con un objeto y hay una palabra que sale con un valor rarísimo:

```js
function countWords(text) {
  const counts = {};
  for (const word of text.toLowerCase().split(/\s+/)) {
    counts[word] = (counts[word] || 0) + 1;
  }
  return counts;
}

console.log(countWords('the constructor called the constructor').constructor);
// 'function Object() { [native code] }11'
```""",
            },
            {
                "role": "assistant",
                "content": r"""El objeto `{}` no está vacío: **hereda de `Object.prototype`**, que ya tiene propiedades como `constructor`, `toString` o `hasOwnProperty`.

Traza con la palabra `constructor`:

1. Primera vez: `counts['constructor']` no es tuyo, es el heredado: la función `Object`. Es *truthy*, así que `|| 0` no actúa, y `Object + 1` concatena como texto: `'function Object() { [native code] }1'`.
2. Segunda vez: ahora sí hay una propiedad propia (ese texto), y `+ 1` añade otro `1`.

Hay un caso peor: la palabra `__proto__`. Asignar un número a `counts['__proto__']` llama al *setter* que cambia el prototipo, que ignora valores que no son objetos. La palabra desaparece del recuento sin error.

Para un diccionario con claves arbitrarias, usa `Map`:

```js
function countWords(text) {
  const counts = new Map();
  for (const word of text.toLowerCase().split(/\s+/).filter(Boolean)) {
    counts.set(word, (counts.get(word) ?? 0) + 1);
  }
  return counts;
}
```

El `filter(Boolean)` descarta la cadena vacía que produce `split` cuando el texto empieza o acaba con espacios.

| | Objeto `{}` | `Map` |
|---|---|---|
| Claves | strings y símbolos | cualquier valor (objetos incluidos) |
| Claves heredadas | sí (`constructor`, `__proto__`...) | no |
| Orden | claves tipo entero primero, en orden numérico | orden de inserción, siempre |
| Tamaño | `Object.keys(o).length`, O(n) | `map.size`, O(1) |
| Altas y bajas frecuentes | lento con `delete` | optimizado para eso |
| JSON | directo | `Object.fromEntries(map)` |

Si necesitas un objeto plano (por ejemplo, para serializarlo), `Object.create(null)` crea uno sin prototipo y evita el problema.

Comprobación:

```js
const counts = countWords(' the constructor called the constructor __proto__ ');
console.log(counts.get('constructor')); // 2
console.log(counts.get('__proto__'));   // 1
console.log(counts.size);               // 4
```""",
            },
            {"role": "user", "content": "Buenísimo. Otra: tengo dos listas de ids (las del CRM y las de la base) y necesito saber cuáles faltan de cada lado. Ahora hago `filter` + `includes` y con 50.000 ids tarda una eternidad."},
            {
                "role": "assistant",
                "content": """El problema es la complejidad: `includes` recorre el array entero en cada llamada, así que `filter` + `includes` hace del orden de 50 000 × 50 000 = 2500 millones de comparaciones. Un `Set` responde `has()` en tiempo constante y baja el total a unas 100 000 operaciones.

```js
const crmIds = new Set(crmList);
const dbIds = new Set(dbList);

// Node 22+ (métodos de Set de ES2025)
const missingInDb = crmIds.difference(dbIds);   // están en el CRM y no en la base
const missingInCrm = dbIds.difference(crmIds);  // al revés
```

Node 20 no tiene esos métodos. El equivalente, con la misma complejidad:

```js
const missingInDb = new Set([...crmIds].filter((id) => !dbIds.has(id)));
const missingInCrm = new Set([...dbIds].filter((id) => !crmIds.has(id)));
```

En Node 22 también tienes `intersection`, `union`, `symmetricDifference`, `isSubsetOf` e `isSupersetOf`.

La trampa típica en este cruce: `Set` compara con *SameValueZero*, sin coerción. `1` y `'1'` son elementos distintos. Si el CRM te da los ids como texto y la base como números, todo saldrá como «faltante». Normaliza antes de construir los conjuntos:

```js
const crmIds = new Set(crmList.map(String));
const dbIds = new Set(dbList.map(String));
```

Comprobación con datos pequeños:

```js
const a = new Set(['1', '2', '3']);
const b = new Set(['2', '3', '4']);
console.log([...a].filter((id) => !b.has(id))); // ['1']
console.log([...b].filter((id) => !a.has(id))); // ['4']
```

Y para confirmar la mejora, `console.time('diff')` / `console.timeEnd('diff')` alrededor de cada versión con tus 50 000 ids: la de `Set` debería quedar en milisegundos.""",
            },
        ]
    },
    # 8) WeakMap para metadatos sin fugas (inglés, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm writing a small UI library that needs to attach computed metadata (layout measurements) to DOM elements I don't own. Right now I keep a `Map<Element, Metadata>` and memory keeps growing in long-lived SPAs. Is WeakMap the right fix, and what are the gotchas?",
            },
            {
                "role": "assistant",
                "content": """Yes. A `Map` holds **strong** references to its keys, so every element you ever measured stays alive for as long as the map does, even after the app removes it from the DOM. A `WeakMap` holds its keys weakly: once nothing else references the element, the entry becomes collectable together with it.

```js
const metadataByElement = new WeakMap();

export function getMetadata(element) {
  let metadata = metadataByElement.get(element);
  if (metadata === undefined) {
    const rect = element.getBoundingClientRect();
    metadata = { width: rect.width, height: rect.height, measuredAt: performance.now() };
    metadataByElement.set(element, metadata);
  }
  return metadata;
}

export function invalidate(element) {
  metadataByElement.delete(element);
}
```

The gotchas, roughly in the order people hit them:

1. **No iteration, no `size`, no `clear()`.** That is by design: garbage collection is nondeterministic, so the contents can't be observable. If you need "all tracked elements", you need a different design, such as a registry the host app explicitly owns.
2. **Keys must be objects** (or, since ES2023, non-registered symbols). `metadataByElement.set('id-1', ...)` throws `TypeError: Invalid value used as weak map key`.
3. **Values are held strongly while their key lives.** If the metadata object references something large, that stays in memory until the element goes away.
4. **A value that points back to its own key does not keep the entry alive.** Entries behave as ephemerons, so `{ owner: element }` inside the value is safe. A `Map` would leak in that case.
5. **Weakness doesn't solve staleness.** The element can be resized while still alive. Pair the cache with a `ResizeObserver` that calls `invalidate` for the affected elements.
6. **`WeakRef` and `FinalizationRegistry` are a different tool.** They help when the key is a primitive (for example, an id pointing to a heavy object). Never put correctness logic in a finalization callback: it may run late or not at all.

How to verify the leak is gone, which matters more than the theory:

- In Chrome DevTools, open **Memory → Heap snapshot**, mount and unmount the component a few times, take a second snapshot and filter by `Detached`. With the `Map`, the count of detached elements grows on every cycle; with the `WeakMap`, it should stay flat after a forced GC (the trash-can button).
- In Node, a quick sanity check of the semantics:

```js
// weakmap-check.mjs, run with: node --expose-gc weakmap-check.mjs
const registry = new FinalizationRegistry((label) => console.log(`collected: ${label}`));
const cache = new WeakMap();

let key = { payload: new Array(1_000_000).fill(0) };
cache.set(key, { note: 'metadata' });
registry.register(key, 'key object');

key = null;
globalThis.gc();
setTimeout(() => {}, 100); // keeps the process alive so the cleanup callback can run
```

It should print `collected: key object`. Swap the `WeakMap` for a `Map` and nothing is printed, because the map still references the key. Treat this as a diagnostic, not a unit test: GC timing is not guaranteed, so never assert on it in CI.""",
            },
        ]
    },
    # 9) Copias superficiales, structuredClone e inmutabilidad (principiante-intermedio, España)
    {
        "messages": [
            {
                "role": "user",
                "content": """Me he liado con las copias. Hago un «clon» del estado para editar un borrador y al cambiar el borrador se me cambia también el original:

```js
const original = { title: 'Pedido 12', lines: [{ sku: 'A1', qty: 1 }], createdAt: new Date() };
const draft = { ...original };
draft.lines[0].qty = 5;
console.log(original.lines[0].qty); // 5 ¿?
```

¿No se suponía que el spread copiaba?""",
            },
            {
                "role": "assistant",
                "content": """Copia, pero **solo un nivel**. `draft` es un objeto nuevo, pero sus propiedades se copian por valor, y el valor de `lines` es una referencia al mismo array. Los dos objetos apuntan a la misma lista y a la misma línea:

```
original ──► { title, lines ─┐, createdAt ─┐ }
                             ├──► [ { sku: 'A1', qty } ]
draft    ──► { title, lines ─┘, createdAt ─┘ }   (y el mismo Date)
```

Tienes dos salidas, según lo que quieras hacer.

**1. Copia profunda real: `structuredClone`** (disponible en Node 17+ y en todos los navegadores actuales):

```js
const draft = structuredClone(original);
draft.lines[0].qty = 5;
console.log(original.lines[0].qty);           // 1
console.log(draft.createdAt instanceof Date);  // true: conserva Date
```

Conserva `Date`, `Map`, `Set`, `RegExp`, arrays tipados e incluso referencias circulares. Sus límites:

- Las funciones no se pueden clonar: lanza `DataCloneError`.
- Las instancias de tus clases salen como objetos planos: pierdes los métodos.
- Las propiedades con clave `Symbol` se ignoran.

Evita `JSON.parse(JSON.stringify(x))`: convierte las fechas en strings, borra los `undefined`, transforma un `Map` en `{}` y falla con referencias circulares y con `BigInt`.

**2. Copiar solo lo que cambias** (lo habitual en estado de UI, como en React o Redux):

```js
const draft = {
  ...original,
  lines: original.lines.with(0, { ...original.lines[0], qty: 5 }), // ES2023
};
```

`Array.prototype.with(index, value)` devuelve un array nuevo con ese elemento sustituido. Lo que no tocas se comparte, lo cual es barato y permite comparar por referencia (`draft.title === original.title`).

**Para pillar mutaciones accidentales en desarrollo**, congela el original. `Object.freeze` también es superficial, así que hace falta recorrerlo:

```js
function deepFreeze(value) {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const key of Reflect.ownKeys(value)) deepFreeze(value[key]);
  }
  return value;
}

const frozen = deepFreeze({ lines: [{ sku: 'A1', qty: 1 }] });
frozen.lines[0].qty = 5;
// En módulos ES (modo estricto): TypeError: Cannot assign to read only property 'qty' of object '#<Object>'
```

Ojo: un `Date` congelado sigue aceptando `setDate()`, porque su valor vive en un campo interno, no en una propiedad.

Comprobación de las dos variantes con tu ejemplo: tras crear `draft` y cambiar la cantidad, `original.lines[0].qty` debe seguir siendo `1` y `draft.lines[0].qty` debe ser `5`.""",
            },
        ]
    },
    # 10) Fechas: date-only en UTC, Intl y Temporal (intermedio, Colombia)
    {
        "messages": [
            {
                "role": "user",
                "content": """En mi app (estoy en Bogotá) el usuario elige su fecha de cumpleaños en un `<input type="date">`, la guardo con `new Date(valor)` y cuando la muestro sale un día antes. Elige 2024-03-10 y aparece 9 de marzo. ¿Qué está pasando, parce?""",
            },
            {
                "role": "assistant",
                "content": """Lo que pasa es que `new Date('2024-03-10')` no significa «10 de marzo»: significa **«10 de marzo a medianoche en UTC»**. Bogotá está en UTC−5, así que ese instante es el 9 de marzo a las 7:00 p. m. hora local, y eso es lo que muestras.

```js
const d = new Date('2024-03-10');
console.log(d.toISOString()); // 2024-03-10T00:00:00.000Z
console.log(d.toLocaleDateString('es-CO', { dateStyle: 'long', timeZone: 'America/Bogota' }));
// 9 de marzo de 2024
```

La regla del parser, que confunde a todo el mundo:

| Cadena | Se interpreta como |
|---|---|
| `'2024-03-10'` (solo fecha) | UTC |
| `'2024-03-10T00:00'` (fecha y hora sin zona) | hora **local** |
| `'2024-03-10T00:00Z'` o con `-05:00` | el instante exacto indicado |

El problema de fondo es de modelo: **un cumpleaños no es un instante, es una fecha de calendario**. No tiene hora ni zona horaria. `Date` siempre representa un instante, así que cualquier conversión lo puede mover de día.

**El arreglo:** trata la fecha como texto `YYYY-MM-DD` de punta a punta (en la base, una columna `DATE`, no `TIMESTAMP`) y conviértela a `Date` solo para formatear, fijando UTC en los dos extremos:

```js
function formatCalendarDate(isoDate, locale = 'es-CO') {
  // isoDate: 'YYYY-MM-DD'. Se construye y se formatea en UTC: ningún huso lo puede mover.
  const [year, month, day] = isoDate.split('-').map(Number);
  const instant = new Date(Date.UTC(year, month - 1, day));
  return new Intl.DateTimeFormat(locale, { dateStyle: 'long', timeZone: 'UTC' }).format(instant);
}

console.log(formatCalendarDate('2024-03-10')); // 10 de marzo de 2024
```

El valor del `<input type="date">` ya llega como `'2024-03-10'`: guárdalo tal cual.

**Cuándo sí usar instantes:** para cosas que ocurren en un momento concreto (una cita, un pago). Guárdalas en UTC con zona explícita (`toISOString()`) y formatea con la zona de quien mira (`timeZone: 'America/Bogota'`).

**Temporal**, la propuesta que reemplazará a `Date`, separa estos conceptos: `Temporal.PlainDate` es exactamente «fecha sin hora ni zona». Todavía no viene en Node 20 ni 22; se puede probar con el polyfill `@js-temporal/polyfill`:

```js
import { Temporal } from '@js-temporal/polyfill';

const birthday = Temporal.PlainDate.from('2024-03-10');
console.log(birthday.day);                            // 10
console.log(birthday.add({ years: 1 }).toString());   // 2025-03-10
```

Comprobación de que tu función no depende del huso del servidor: Node respeta la variable `TZ`, así que corre lo mismo con dos zonas extremas y compara.

```bash
TZ=America/Bogota node -e "console.log(new Date('2024-03-10').getDate())"     # 9
TZ=Pacific/Kiritimati node -e "console.log(new Date('2024-03-10').getDate())" # 10
```

Con `formatCalendarDate`, las dos zonas deben dar `10 de marzo de 2024`.""",
            },
        ]
    },
    # 11) Regex con flag g y lastIndex; grupos con nombre y matchAll (intermedio, código roto)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un validador de códigos de producto que falla una vez sí y otra no con el MISMO input. No tiene sentido:

```js
const SKU_PATTERN = /^[A-Z]{3}-\d{4}$/g;

function isValidSku(code) {
  return SKU_PATTERN.test(code);
}

console.log(isValidSku('ABC-1234')); // true
console.log(isValidSku('ABC-1234')); // false ???
console.log(isValidSku('ABC-1234')); // true
```""",
            },
            {
                "role": "assistant",
                "content": r"""Tiene sentido, aunque sorprende: con la bandera `g` (o `y`), **un objeto `RegExp` guarda estado** en su propiedad `lastIndex`. `test()` y `exec()` empiezan a buscar desde ahí y la actualizan:

1. Primera llamada: busca desde 0, encuentra `ABC-1234` y deja `lastIndex = 8`.
2. Segunda: busca desde la posición 8 de `'ABC-1234'`, no queda nada, devuelve `false` y reinicia `lastIndex = 0`.
3. Tercera: vuelta al paso 1.

Como `SKU_PATTERN` es una constante del módulo, ese estado lo comparten **todas** las llamadas, incluso con cadenas distintas. Puedes verlo:

```js
const re = /^[A-Z]{3}-\d{4}$/g;
re.test('ABC-1234');
console.log(re.lastIndex); // 8
re.test('ABC-1234');
console.log(re.lastIndex); // 0
```

**El arreglo: quita la `g`.** Para validar una cadena completa (`^...$`) nunca la necesitas:

```js
const SKU_PATTERN = /^[A-Z]{3}-\d{4}$/;

export function isValidSku(code) {
  return SKU_PATTERN.test(code);
}
```

**Cuándo sí necesitas `g`: para extraer todas las coincidencias.** Ahí usa `matchAll`, que exige la `g` (sin ella lanza `TypeError`) pero trabaja sobre una copia interna de la regex, así que no toca el `lastIndex` de tu constante. Con grupos con nombre el resultado se lee solo:

```js
const LINE_ITEM = /(?<sku>[A-Z]{3}-\d{4})\s+x(?<qty>\d+)/g;

function parseOrder(text) {
  return [...text.matchAll(LINE_ITEM)].map(({ groups }) => ({
    sku: groups.sku,
    qty: Number(groups.qty),
  }));
}

console.log(parseOrder('ABC-1234 x2, XYZ-0001 x10'));
// [ { sku: 'ABC-1234', qty: 2 }, { sku: 'XYZ-0001', qty: 10 } ]
```

Dos banderas más que conviene tener a mano:

- `u` (o `v`, desde ES2024) activa el modo Unicode. Sin ella, `\p{L}` no funciona y los emojis cuentan como dos caracteres. Para nombres con tildes y eñes: `/^\p{L}+(?: \p{L}+)*$/u`.
- `replaceAll` con una regex también exige `g`; con un string no hace falta.

Comprobación (Node 20+):

```js
import assert from 'node:assert/strict';

for (let attempt = 0; attempt < 3; attempt++) {
  assert.equal(isValidSku('ABC-1234'), true); // estable en llamadas repetidas
}
assert.equal(isValidSku('abc-1234'), false);
assert.equal(isValidSku('ABC-12345'), false);
assert.deepEqual(parseOrder('sin pedidos'), []);
```""",
            },
        ]
    },
    # 12) fetch con AbortController: carreras, timeout y reintentos (intermedio, SISTEMA, multiturno)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo un buscador con autocompletado. Cada tecla hace un fetch y a veces se pintan resultados viejos (escribo «react» y se queda mostrando los de «rea»). Además quiero un timeout de 5 s. ¿Cómo lo hago con fetch, sin librerías?",
            },
            {
                "role": "assistant",
                "content": """Lo que ves es una **condición de carrera**: las respuestas no llegan en el orden en que salen las peticiones. Si la de «rea» tarda más que la de «react», llega la última y pisa los resultados buenos. El arreglo es **cancelar la petición anterior** cada vez que sale una nueva, y `AbortController` hace justo eso.

```js
// search.js (navegador moderno o Node 20.3+)
export function createSearch(endpoint, { timeoutMs = 5000 } = {}) {
  let inFlight = null;

  return async function search(query) {
    inFlight?.abort(); // cancela la búsqueda anterior, si sigue en vuelo
    const controller = new AbortController();
    inFlight = controller;

    const url = new URL(endpoint, location.origin);
    url.searchParams.set('q', query);

    const res = await fetch(url, {
      // se aborta por lo que pase primero: una búsqueda nueva o el timeout
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(timeoutMs)]),
    });
    if (!res.ok) throw new Error(`búsqueda falló: HTTP ${res.status}`);
    return res.json();
  };
}
```

Y en el manejador, distingue los tres tipos de fallo:

```js
const search = createSearch('/api/search');

input.addEventListener('input', async (event) => {
  try {
    renderResults(await search(event.target.value));
  } catch (err) {
    if (err.name === 'AbortError') return; // la reemplazó otra búsqueda: no es un error
    if (err.name === 'TimeoutError') {
      showMessage('La búsqueda está tardando demasiado.');
      return;
    }
    showMessage('No se pudo buscar.');
    console.error(err);
  }
});
```

Por qué cada pieza:

- **`fetch` no rechaza con un 404 o un 500.** Solo rechaza por fallo de red o por cancelación. Sin el `if (!res.ok)` tratarías una página de error como resultados.
- **La cancelación también cubre el cuerpo.** Si abortas mientras se ejecuta `res.json()`, esa promesa también rechaza con `AbortError`. No queda ninguna respuesta vieja a medio procesar.
- **`AbortSignal.timeout(ms)` rechaza con `TimeoutError`**, no con `AbortError`. Así distingues «el usuario siguió escribiendo» de «el servidor no responde».
- **`AbortSignal.any`** combina señales. Está en Node 20.3+ y en las versiones actuales de Chrome, Firefox y Safari.

Comprobación del timeout en Node 20.3+:

```js
try {
  await fetch('https://httpbin.org/delay/10', { signal: AbortSignal.timeout(1000) });
} catch (err) {
  console.log(err.name); // TimeoutError
}
```

Y en el navegador: escribe rápido con la pestaña Network abierta; las peticiones reemplazadas deben aparecer como *(canceled)*.""",
            },
            {
                "role": "user",
                "content": "Perfecto. ¿Y si quiero reintentar hasta 2 veces cuando falle la red o el servidor devuelva 503, pero sin reintentar si el usuario ya escribió otra cosa?",
            },
            {
                "role": "assistant",
                "content": """La regla es reintentar solo lo que es **transitorio e idempotente**:

- Sí: errores de red (`TypeError` de `fetch`) y los estados 429, 502, 503 y 504.
- No: `AbortError` ni `TimeoutError` (el usuario siguió adelante o ya agotaste el plazo), ni los 4xx (repetir la misma petición dará el mismo error).
- Un `GET` de búsqueda es idempotente. Un `POST` que cobra algo no se reintenta sin una clave de idempotencia.

La espera entre intentos también tiene que ser cancelable; si no, una búsqueda ya reemplazada seguiría durmiendo y reintentando.

```js
const RETRYABLE_STATUS = new Set([429, 502, 503, 504]);

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export async function fetchWithRetry(url, { signal, retries = 2, baseDelayMs = 300 } = {}) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, { signal });
      if (!RETRYABLE_STATUS.has(res.status) || attempt === retries) return res;
      await res.body?.cancel(); // libera la conexión antes de reintentar
    } catch (err) {
      if (signal?.aborted || attempt === retries) throw err; // cancelada: no se reintenta
    }
    // backoff exponencial con jitter: 150-450 ms, 300-900 ms...
    await sleep(baseDelayMs * 2 ** attempt * (0.5 + Math.random()), signal);
  }
}
```

En `createSearch` solo cambia la llamada: `fetchWithRetry(url, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(timeoutMs)]) })` en lugar del `fetch` directo. Como la señal combinada incluye el `controller` de la búsqueda, escribir otra letra corta tanto la petición en vuelo como la espera del backoff.

Tres detalles:

- **El jitter** (el factor aleatorio) evita que mil clientes que fallaron a la vez reintenten todos en el mismo milisegundo.
- **`res.body?.cancel()`**: en Node, una respuesta cuyo cuerpo nadie lee mantiene ocupada la conexión hasta que la recolecta el GC.
- Con 429 el servidor suele mandar `Retry-After`. Si lo envía, respeta ese valor en lugar del backoff calculado.

Test con `node:test`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fetchWithRetry } from './fetch-with-retry.js';

test('reintenta los 503 y devuelve el 200', async (t) => {
  const statuses = [503, 503, 200];
  const fetchMock = t.mock.method(globalThis, 'fetch', async () =>
    new Response('ok', { status: statuses.shift() }));

  const res = await fetchWithRetry('https://api.test/x', { baseDelayMs: 1 });
  assert.equal(res.status, 200);
  assert.equal(fetchMock.mock.callCount(), 3);
});

test('no reintenta si la señal ya está abortada', async (t) => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response('', { status: 503 }));
  const controller = new AbortController();
  controller.abort();

  await assert.rejects(fetchWithRetry('https://api.test/x', { signal: controller.signal, baseDelayMs: 1 }));
  assert.equal(fetchMock.mock.callCount(), 1);
});
```

El segundo test fija el comportamiento importante: un 503 con la señal ya abortada lanza en el `sleep` y no vuelve a llamar a `fetch`.""",
            },
        ]
    },
    # 13) Streams: procesar un CSV.gz enorme con pipeline (avanzado, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo que sumar ventas por país de un CSV comprimido de 3 GB (`ventas.csv.gz`) en Node 20. Lo hice con `zlib.gunzipSync(fs.readFileSync(ruta)).toString()` y revienta con:

```
Error: Cannot create a string longer than 0x1fffffe8 characters
    at Buffer.toString (node:buffer)
  code: 'ERR_STRING_TOO_LONG'
```

¿Le subo la memoria con `--max-old-space-size`?""",
            },
            {
                "role": "assistant",
                "content": r"""No te va a servir: ese límite no es de memoria. `0x1fffffe8` (unos 512 millones de caracteres) es la **longitud máxima de un string en V8**, y no cambia con el tamaño del heap. E incluso si no existiera, cargar 3 GB descomprimidos para quedarte con unas pocas sumas es el enfoque equivocado.

La solución es procesarlo como **stream**: leer, descomprimir, partir en líneas y acumular, trozo a trozo, con memoria constante.

```js
// sum-by-country.mjs (Node 20+)
import { createReadStream } from 'node:fs';
import { pipeline } from 'node:stream/promises';
import { createGunzip } from 'node:zlib';

// bytes -> líneas de texto, sin romper caracteres UTF-8 que caigan entre dos chunks
export async function* splitLines(chunks) {
  const decoder = new TextDecoder('utf-8');
  let rest = '';
  for await (const chunk of chunks) {
    rest += decoder.decode(chunk, { stream: true });
    const lines = rest.split(/\r?\n/);
    rest = lines.pop(); // la última puede estar incompleta
    yield* lines;
  }
  rest += decoder.decode();
  if (rest) yield rest;
}

export async function sumByCountry(path) {
  const totalsCents = new Map();

  await pipeline(
    createReadStream(path),
    createGunzip(),
    splitLines,
    async function aggregate(lines) {
      let columns = null;
      for await (const line of lines) {
        if (columns === null) {
          const header = line.split(',');
          columns = { country: header.indexOf('country'), amount: header.indexOf('amount') };
          if (columns.country < 0 || columns.amount < 0) {
            throw new Error(`cabecera inesperada: ${line}`);
          }
          continue;
        }
        const fields = line.split(',');
        const cents = Math.round(Number(fields[columns.amount]) * 100);
        if (!Number.isFinite(cents)) throw new Error(`importe inválido en: ${line}`);
        const country = fields[columns.country];
        totalsCents.set(country, (totalsCents.get(country) ?? 0) + cents);
      }
    },
  );

  return totalsCents;
}
```

El punto de entrada va aparte, para que los tests puedan importar el módulo sin ejecutar nada:

```js
// cli.mjs
import { sumByCountry } from './sum-by-country.mjs';

const totals = await sumByCountry(process.argv[2]);
for (const [country, cents] of totals) console.log(country, (cents / 100).toFixed(2));
```

Por qué esta forma y no otra:

- **`pipeline` de `node:stream/promises`** conecta las etapas, propaga los errores de cualquiera de ellas (archivo inexistente, gzip corrupto, excepción en `aggregate`) y cierra todos los streams. Con `.pipe()` encadenado, un error en la lectura no llega a las etapas siguientes y el proceso puede quedarse colgado.
- **Contrapresión**: la lectura avanza solo al ritmo al que `aggregate` consume. Nunca hay más de unos pocos chunks de 64 KiB en memoria.
- **`TextDecoder` con `stream: true`**: un carácter como la «ú» ocupa 2 bytes y puede quedar partido entre dos chunks. Decodificar cada chunk por separado con `toString()` metería caracteres corruptos.
- **Céntimos enteros** al acumular: sumar millones de `19.99` en coma flotante deriva.
- `split(',')` vale si el CSV no tiene comas dentro de campos entrecomillados. Si las tiene, cambia `splitLines` y `aggregate` por el parser en streaming de `csv-parse`, que ya maneja comillas y escapes.

Dos comprobaciones.

**Memoria constante**: si el diseño es correcto, funciona incluso con un heap ridículo.

```bash
node --max-old-space-size=64 cli.mjs ventas.csv.gz
```

**El caso límite del UTF-8**, con un test que parte la «ú» justo por la mitad:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitLines } from './sum-by-country.mjs';

test('splitLines no rompe caracteres multibyte entre chunks', async () => {
  const bytes = Buffer.from('country,amount\nPerú,1.50\n');
  const cut = bytes.indexOf(0xba); // segundo byte de 'ú' (0xC3 0xBA)
  const lines = [];
  for await (const line of splitLines([bytes.subarray(0, cut), bytes.subarray(cut)])) {
    lines.push(line);
  }
  assert.deepEqual(lines, ['country,amount', 'Perú,1.50']);
});
```""",
            },
        ]
    },
    # 14) Errores con cause y clases propias (intermedio, system: revisor estricto)
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un revisor de código estricto. Señalas cada problema con su porqué, por orden de gravedad, y propones el cambio mínimo.",
            },
            {
                "role": "user",
                "content": """Revisa esto, por fa. Es la carga de configuración de un servicio:

```js
export async function loadConfig(path) {
  try {
    const raw = await readFile(path, 'utf8');
    return JSON.parse(raw);
  } catch (e) {
    console.log(e);
    throw new Error('No se pudo cargar la configuración');
  }
}

export function getPort(config) {
  if (!config.port) throw 'puerto no definido';
  return config.port;
}
```""",
            },
            {
                "role": "assistant",
                "content": """Seis problemas, de más a menos grave.

1. **Falta el import de `readFile`.** Tal como está, la primera línea del `try` lanza `ReferenceError: readFile is not defined`, el `catch` la captura y la convierte en «No se pudo cargar la configuración». Es justo el tipo de bug que este manejo de errores esconde. Falta `import { readFile } from 'node:fs/promises';`.
2. **Se pierde el error original.** El `new Error(...)` descarta el `code` (`ENOENT`, `EACCES`), la posición del error de JSON y la traza. Desde ES2022 (Node 16.9+) existe la opción `cause`: `new Error('...', { cause: e })`. Node la imprime como `[cause]: ...` en los errores no capturados.
3. **`throw 'puerto no definido'`.** Lanzar un string no tiene traza, `err instanceof Error` da `false` y `err.message` es `undefined`. Cualquier manejador genérico lo mostrará mal. Lanza siempre un `Error` o una subclase.
4. **Registrar y relanzar.** El `console.log(e)` duplica el error en los logs: lo registras aquí y lo registrará también quien lo capture. Registra en un solo sitio, el que decide qué hacer con el fallo.
5. **Mensaje sin contexto.** «No se pudo cargar la configuración»: ¿qué archivo? Incluye la ruta.
6. **`!config.port` valida mal.** Acepta `'3000'` (string), `-1` o `99999`, y rechaza `0`. Valida tipo y rango.

Versión corregida, separando «no se puede leer» de «no es JSON válido», que son fallos con remedios distintos:

```js
import { readFile } from 'node:fs/promises';

export class ConfigError extends Error {
  constructor(message, options) {
    super(message, options); // options puede llevar { cause }
    this.name = 'ConfigError';
  }
}

export async function loadConfig(path) {
  let raw;
  try {
    raw = await readFile(path, 'utf8');
  } catch (cause) {
    throw new ConfigError(`no se pudo leer la configuración en ${path}`, { cause });
  }
  try {
    return JSON.parse(raw);
  } catch (cause) {
    throw new ConfigError(`la configuración en ${path} no es JSON válido`, { cause });
  }
}

export function getPort(config) {
  const { port } = config;
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new ConfigError(`port debe ser un entero entre 1 y 65535; recibido ${JSON.stringify(port)}`);
  }
  return port;
}
```

Quien llama decide y registra una sola vez:

```js
try {
  const config = await loadConfig('./config.json');
  startServer(getPort(config));
} catch (err) {
  if (!(err instanceof ConfigError)) throw err; // lo inesperado sigue subiendo
  console.error(`${err.message} (causa: ${err.cause?.message ?? 'n/a'})`);
  process.exitCode = 1;
}
```

`this.name = 'ConfigError'` hace que la traza diga `ConfigError: ...` en lugar de `Error: ...`, lo que ayuda mucho al buscar en los logs.

Tests que fijan el contrato:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ConfigError, getPort, loadConfig } from './config.js';

test('conserva la causa cuando el archivo no existe', async () => {
  await assert.rejects(loadConfig('/no/existe.json'), (err) => {
    assert.ok(err instanceof ConfigError);
    assert.equal(err.cause.code, 'ENOENT');
    return true;
  });
});

test('rechaza puertos que no son enteros válidos', () => {
  for (const port of ['3000', 0, 70_000, undefined]) {
    assert.throws(() => getPort({ port }), ConfigError);
  }
  assert.equal(getPort({ port: 8080 }), 8080);
});
```""",
            },
        ]
    },
    # 15) npm ci, rangos semver y dependencias fantasma con pnpm (intermedio, multiturno, ustedes)
    {
        "messages": [
            {
                "role": "user",
                "content": """En mi equipo hay pleito: unos dicen que `npm install` en el CI está bien y otros que hay que usar `npm ci`. Y de paso, ¿qué significa exactamente el `^`? Tenemos `"express": "^4.19.2"` en el package.json.""",
            },
            {
                "role": "assistant",
                "content": """En el CI, `npm ci`. Y el `^` explica por qué.

**Rangos de versión** (semver):

| Rango | Acepta | Ejemplo con `4.19.2` |
|---|---|---|
| `^4.19.2` | menores y parches: `>=4.19.2 <5.0.0` | 4.21.0 sí, 5.0.0 no |
| `~4.19.2` | solo parches: `>=4.19.2 <4.20.0` | 4.19.9 sí, 4.20.0 no |
| `4.19.2` | exactamente esa | |
| `^0.3.1` | ojo: `>=0.3.1 <0.4.0` | en `0.x` el `^` trata la menor como si fuera mayor |

Con `^4.19.2`, dos personas que instalen con un mes de diferencia pueden obtener versiones distintas de Express y de cada una de sus dependencias transitivas. Eso lo resuelve el **lockfile** (`package-lock.json`): fija la versión exacta resuelta de todo el árbol. Por eso va al repositorio, siempre.

**`npm install` frente a `npm ci`:**

| | `npm install` | `npm ci` |
|---|---|---|
| Usa el lockfile | sí, pero puede **modificarlo** si `package.json` cambió | lo sigue al pie de la letra |
| Si `package.json` y el lockfile no cuadran | los reconcilia en silencio | **falla** |
| `node_modules` previo | lo reutiliza | lo borra y empieza de cero |
| Pensado para | desarrollo, añadir dependencias | CI y builds reproducibles |

Lo que ustedes quieren del CI es que construya **exactamente** lo que se revisó en el PR, y que falle si alguien cambió `package.json` sin actualizar el lockfile. Eso es `npm ci`. Para imágenes de producción, `npm ci --omit=dev`.

Tres prácticas que cierran el círculo:

- Fijen la versión de Node con `"engines": { "node": ">=20.11" }` en `package.json` y un `.nvmrc`, para que «en mi máquina funciona» no dependa de la versión del runtime.
- Las actualizaciones, deliberadas: `npm outdated` para ver qué hay, y Renovate o Dependabot para que lleguen como PR revisable.
- Comprobación de que el lockfile está sano: `npm ci` en limpio en local debe terminar sin cambios en `git status`.""",
            },
            {
                "role": "user",
                "content": "Ya. Otra cosa: pasamos a pnpm y ahora la app truena en producción con `Error: Cannot find module 'debug'`, pero con npm funcionaba. Nunca instalamos `debug` directamente.",
            },
            {
                "role": "assistant",
                "content": """Eso es una **dependencia fantasma**, y pnpm acaba de hacerles el favor de descubrirla.

Qué pasaba con npm: npm «aplana» el árbol y sube a `node_modules/` casi todas las dependencias transitivas. Express depende de `debug`, así que `node_modules/debug` existía y su código podía hacer `import debug from 'debug'` aunque `package.json` no lo declarara. Funcionaba por casualidad: si Express dejara de depender de `debug` en una versión menor, la app se rompería sin que nadie tocara nada.

Qué hace pnpm: en `node_modules/` solo pone **enlaces a lo que ustedes declararon**. Lo transitivo vive en `node_modules/.pnpm/` y solo es visible para el paquete que lo pidió. Su código ya no ve `debug`.

**El arreglo correcto es declararla:**

```bash
pnpm why debug     # confirma quién la trae (aquí, express)
pnpm add debug     # pasa a ser dependencia directa, con su propio rango
```

Eviten `shamefully-hoist=true` en `.npmrc`: devuelve el comportamiento de npm y esconde el problema. Úsenlo, si acaso, como parche temporal mientras declaran lo que falta.

**Para encontrar todas las fantasmas de una vez**, no a base de caídas en producción:

- `knip` lista dependencias usadas pero no declaradas (y también las declaradas que nadie usa).
- En ESLint, `n/no-extraneous-import` (de `eslint-plugin-n`) o `import/no-extraneous-dependencies` (de `eslint-plugin-import`) marcan cada import de un paquete que no está en `package.json`.

**Para que no vuelva a pasar en el CI:**

```json
{
  "packageManager": "pnpm@9.12.0",
  "engines": { "node": ">=20.11" }
}
```

Con `corepack enable` (Corepack viene con Node 20 y 22), todo el equipo y el CI usan esa versión exacta de pnpm. En CI, `pnpm install` ya usa `--frozen-lockfile` por defecto: falla si el `pnpm-lock.yaml` no cuadra, igual que `npm ci`.

Comprobación: un build limpio con `pnpm install --frozen-lockfile && pnpm build && node dist/server.js` en un contenedor sin caché. Si arranca, no queda ninguna fantasma en el camino de arranque. Las que estén en rutas poco usadas las caza `knip`, no el arranque.""",
            },
        ]
    },
    # 16) Fuga de memoria con listeners: --trace-warnings, heap snapshots y test (avanzado, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Tengo un servicio en Node 22 (servidor de eventos SSE) que va subiendo de memoria hasta que Kubernetes lo mata por OOMKilled cada ~6 horas. En los logs aparece de vez en cuando:

```
(node:1) MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 message listeners added to [EventEmitter]. Use emitter.setMaxListeners() to increase limit
```

¿Cómo lo depuro? ¿Subo el límite de listeners?""",
            },
            {
                "role": "assistant",
                "content": r"""No subas el límite: ese aviso es el síntoma de la fuga, no un falso positivo. Node avisa cuando un mismo emisor acumula más de 10 listeners para un evento, porque casi siempre significa que alguien se suscribe y nunca se desuscribe. Subir el límite apaga la alarma y deja el incendio.

El método, de lo más barato a lo más caro:

**1. ¿Quién añade los listeners?** Arranca con `--trace-warnings`. El aviso saldrá con la traza completa del `on(...)` número 11, que apunta a la línea culpable.

```bash
node --trace-warnings server.js
```

**2. Confirmar qué retiene la memoria.** La prueba definitiva son los heap snapshots:

- Arranca con `node --inspect server.js`. Por defecto escucha solo en `127.0.0.1:9229`; **nunca** lo expongas en `0.0.0.0` en producción, porque el inspector permite ejecutar código arbitrario. En Kubernetes, `kubectl port-forward pod/<pod> 9229:9229`.
- Abre `chrome://inspect` en Chrome, entra en el proceso y ve a **Memory**.
- Toma tres snapshots con carga entre medias, y en la vista **Comparison** ordena por *Size Delta*. Mira los **Retainers** de lo que crece: verás la cadena `EventEmitter → _events → message → [array] → closure → ServerResponse`.

Si no puedes conectar DevTools en el clúster, haz que Node vuelque los snapshots a disco:

```bash
node --heapsnapshot-signal=SIGUSR2 server.js   # luego: kill -USR2 <pid>
node --heapsnapshot-near-heap-limit=2 server.js  # vuelca automáticamente antes del OOM
```

Los `.heapsnapshot` se abren después en la misma pestaña Memory de DevTools.

**3. El patrón culpable típico** en un servidor SSE es suscribirse a un bus por conexión y no limpiar al desconectarse. Cada closure retiene su `res`, con su socket y sus buffers:

```js
// Fuga: el listener (y con él res) vive para siempre
bus.on('message', (msg) => res.write(`data: ${JSON.stringify(msg)}\n\n`));
```

**4. El arreglo**: desuscribirse cuando se cierra la respuesta.

```js
// events-server.js
import { createServer } from 'node:http';

export function createEventsServer(bus) {
  return createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
    res.flushHeaders(); // sin esto el cliente no recibe cabeceras hasta el primer mensaje

    const onMessage = (msg) => res.write(`data: ${JSON.stringify(msg)}\n\n`);
    bus.on('message', onMessage);
    res.on('close', () => bus.off('message', onMessage)); // cliente desconectado: se libera
  });
}
```

Con 500 clientes conectados de forma legítima volverás a ver el aviso, aunque ya no haya fuga. Ahí sí procede `bus.setMaxListeners(0)` o, mejor, un límite acorde a la capacidad, porque ahora sabes que el número de listeners es igual al de conexiones vivas.

**5. Test de regresión** que falla (por timeout) si el listener no se libera:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter, once } from 'node:events';
import { createEventsServer } from './events-server.js';

test('libera el listener cuando el cliente se desconecta', async () => {
  const bus = new EventEmitter();
  const server = createEventsServer(bus).listen(0);
  await once(server, 'listening');
  const { port } = server.address();

  const controller = new AbortController();
  await fetch(`http://127.0.0.1:${port}/`, { signal: controller.signal });
  assert.equal(bus.listenerCount('message'), 1);

  const removed = once(bus, 'removeListener'); // EventEmitter lo emite al quitar un listener
  controller.abort();
  await removed;
  assert.equal(bus.listenerCount('message'), 0);
  server.close();
});
```

Comprobación en el entorno real: tras el despliegue, expón `bus.listenerCount('message')` como métrica junto al número de conexiones abiertas. Deben moverse juntas, y la memoria tras cada GC debe quedar plana en lugar de subir en diente de sierra.""",
            },
        ]
    },
    # 17) Memoización de funciones async: deduplicación, TTL y LRU (avanzado, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero memoizar una función async que consulta el tipo de cambio (`getRate('USD', 'COP')`). El problema es que al arrancar el servicio llegan 30 peticiones a la vez y las 30 van a la API antes de que la primera llene la caché.",
            },
            {
                "role": "assistant",
                "content": """Eso pasa porque guardas el **valor** cuando llega, y durante la espera la caché está vacía. La solución es guardar la **promesa** en el momento de la primera llamada. Las 29 siguientes encuentran la promesa en vuelo y la comparten.

```js
// memoize-async.js
export function memoizeAsync(fn, { key = (...args) => JSON.stringify(args) } = {}) {
  const cache = new Map();

  return function memoized(...args) {
    const cacheKey = key(...args);
    const cached = cache.get(cacheKey);
    if (cached) return cached;

    const promise = fn(...args).catch((err) => {
      cache.delete(cacheKey); // los fallos no se cachean: el siguiente intento vuelve a llamar
      throw err;
    });
    cache.set(cacheKey, promise);
    return promise;
  };
}
```

Las tres decisiones importantes:

1. **Se cachea la promesa, no el resultado.** Es lo que deduplica las llamadas concurrentes. Las 30 peticiones reciben el mismo objeto promesa y se resuelven juntas.
2. **Los rechazos se borran.** Si la API falla una vez y lo cacheas, el servicio queda roto hasta reiniciarse. Con el `delete`, las llamadas que ya esperaban reciben el error, y la siguiente vuelve a intentarlo.
3. **La clave es explícita.** `JSON.stringify(args)` sirve para argumentos primitivos como los tuyos. Con objetos, `{ a: 1, b: 2 }` y `{ b: 2, a: 1 }` darían claves distintas; en ese caso pasa tu propia función `key`.

Test que demuestra la deduplicación:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { memoizeAsync } from './memoize-async.js';

test('30 llamadas concurrentes producen una sola consulta', async () => {
  let calls = 0;
  const getRate = memoizeAsync(async (from, to) => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 50));
    return 4100;
  });

  const rates = await Promise.all(Array.from({ length: 30 }, () => getRate('USD', 'COP')));
  assert.equal(calls, 1);
  assert.ok(rates.every((rate) => rate === 4100));
});
```""",
            },
            {
                "role": "user",
                "content": "Bien, pero el tipo de cambio se mueve: necesito que caduque a los 10 minutos. Y si piden cientos de pares distintos no quiero que la caché crezca sin límite.",
            },
            {
                "role": "assistant",
                "content": """Dos añadidos: un **TTL** por entrada y un **tamaño máximo con desalojo LRU** (se va la entrada usada hace más tiempo). Un `Map` ya da el LRU casi gratis, porque itera en orden de inserción: si al usar una entrada la borras y la vuelves a insertar, pasa al final, y la primera clave del `Map` es siempre la menos usada.

Inyecto el reloj (`now`) para poder probar la caducidad sin esperar 10 minutos.

```js
// memoize-async.js
export function memoizeAsync(
  fn,
  { key = (...args) => JSON.stringify(args), ttlMs = 10 * 60_000, maxEntries = 500, now = Date.now } = {},
) {
  const cache = new Map(); // cacheKey -> { promise, expiresAt }

  return function memoized(...args) {
    const cacheKey = key(...args);
    const entry = cache.get(cacheKey);
    if (entry) cache.delete(cacheKey); // sale de su posición: o se reinserta al final o se renueva

    if (entry && entry.expiresAt > now()) {
      cache.set(cacheKey, entry); // al final del Map = usada recientemente
      return entry.promise;
    }

    const promise = fn(...args).catch((err) => {
      // solo borra si la entrada sigue siendo la suya (pudo renovarse mientras tanto)
      if (cache.get(cacheKey)?.promise === promise) cache.delete(cacheKey);
      throw err;
    });
    cache.set(cacheKey, { promise, expiresAt: now() + ttlMs });

    if (cache.size > maxEntries) {
      cache.delete(cache.keys().next().value); // la primera clave es la menos usada
    }
    return promise;
  };
}
```

Por qué el `delete` antes de reinsertar: `Map.prototype.set` sobre una clave que ya existe **actualiza el valor pero conserva su posición**. Sin el borrado, el orden dejaría de reflejar el uso y el LRU desalojaría la entrada equivocada.

Un matiz de diseño: el TTL cuenta desde que se lanza la consulta, no desde que responde. Con respuestas de milisegundos da igual; si la API tardara segundos, cambiarías `expiresAt` dentro de un `.then`.

Tests con reloj controlado:

```js
test('caduca al cumplirse el TTL', async () => {
  let clock = 0;
  let calls = 0;
  const getRate = memoizeAsync(async () => ++calls, { ttlMs: 1000, now: () => clock });

  await getRate('USD', 'COP');
  clock = 999;
  await getRate('USD', 'COP');
  assert.equal(calls, 1); // todavía vigente

  clock = 1000;
  await getRate('USD', 'COP');
  assert.equal(calls, 2); // caducada: nueva consulta
});

test('desaloja la entrada menos usada', async () => {
  let calls = 0;
  const getRate = memoizeAsync(async () => ++calls, { maxEntries: 2 });

  await getRate('a'); // 1
  await getRate('b'); // 2
  await getRate('a'); // acierto: 'a' pasa a ser la más reciente
  await getRate('c'); // 3, desaloja 'b'
  await getRate('b'); // 4: 'b' ya no estaba
  assert.equal(calls, 4);
});
```

Si esto crece (métricas de aciertos, *stale-while-revalidate*, límite por tamaño en bytes), en producción yo usaría `lru-cache`: ya trae TTL, `max` y un `fetchMethod` que deduplica las consultas concurrentes de la misma clave.""",
            },
        ]
    },
    # 18) Debounce con cancel/flush y prueba con mock timers (intermedio, system: mentor)
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un mentor de frontend. Das código moderno, explicas las decisiones en pocas líneas e incluyes siempre una prueba.",
            },
            {
                "role": "user",
                "content": "Necesito un debounce para el buscador (esperar 300 ms desde la última tecla), pero que pueda cancelarlo al desmontar el componente y forzar la ejecución al pulsar Enter. ¿Cómo lo escribo sin lodash?",
            },
            {
                "role": "assistant",
                "content": """Un debounce es un temporizador que se reinicia en cada llamada: la función solo corre cuando pasan `waitMs` sin llamadas nuevas. `cancel` y `flush` salen casi solos si guardas los argumentos pendientes.

```js
// debounce.js
export function debounce(fn, waitMs) {
  let timer = null;
  let pendingArgs = null;
  let pendingThis = null;

  function invoke() {
    const args = pendingArgs;
    const thisArg = pendingThis;
    timer = null;
    pendingArgs = null;
    pendingThis = null;
    return fn.apply(thisArg, args);
  }

  function debounced(...args) {
    pendingArgs = args; // siempre gana la última llamada
    pendingThis = this;
    clearTimeout(timer);
    timer = setTimeout(invoke, waitMs);
  }

  debounced.cancel = () => {
    clearTimeout(timer);
    timer = null;
    pendingArgs = null;
    pendingThis = null;
  };

  debounced.flush = () => {
    if (timer === null) return undefined; // nada pendiente: no ejecuta dos veces
    clearTimeout(timer);
    return invoke();
  };

  return debounced;
}
```

Decisiones:

- **`debounced` es una `function`, no una flecha**, para conservar el `this` de quien la llama si la usas como método.
- **Se guardan los últimos argumentos**: al buscador le importa el texto final, no el intermedio.
- **`flush` solo ejecuta si hay algo pendiente.** Si el usuario pulsa Enter después de que el debounce ya disparó, no se repite la búsqueda.

Uso:

```js
const search = debounce((query) => runSearch(query), 300);

input.addEventListener('input', (event) => search(event.target.value));
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') search.flush();
});

// al desmontar el componente:
search.cancel();
```

No lo confundas con *throttle*: el throttle ejecuta como mucho una vez cada N ms **mientras** siguen llegando eventos (útil para `scroll`); el debounce espera a que paren (útil para escribir).

Prueba con el runner de Node y temporizadores simulados (Node 20.11+ o 22), sin esperas reales:

```js
// debounce.test.js -> node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { debounce } from './debounce.js';

test('solo ejecuta la última llamada tras 300 ms de silencio', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls = [];
  const search = debounce((query) => calls.push(query), 300);

  search('r');
  search('re');
  t.mock.timers.tick(299);
  search('rea'); // reinicia la espera
  t.mock.timers.tick(299);
  assert.deepEqual(calls, []);

  t.mock.timers.tick(1);
  assert.deepEqual(calls, ['rea']);
});

test('flush ejecuta en el acto y cancel descarta lo pendiente', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls = [];
  const search = debounce((query) => calls.push(query), 300);

  search('a');
  search.flush();
  search('b');
  search.cancel();
  t.mock.timers.tick(1000);
  assert.deepEqual(calls, ['a']);
});
```

Al habilitar `setTimeout` en los mocks, Node también sustituye `clearTimeout`, así que el test cubre el reinicio del temporizador.""",
            },
        ]
    },
    # 19) == frente a === y coerción (principiante, system: rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, de forma clara y con ejemplos cortos."},
            {
                "role": "user",
                "content": "che, ¿cuál es la diferencia entre == y ===? mi jefe me dijo que nunca use == pero no me explicó por qué",
            },
            {
                "role": "assistant",
                "content": """`===` compara **sin convertir tipos**: si los tipos son distintos, da `false` y listo. `==` primero **convierte** los dos lados según unas reglas de coerción bastante enredadas y después compara. Ahí está el problema: el resultado depende de reglas que casi nadie recuerda.

Mirá estos casos:

| Expresión | Resultado | Qué pasó |
|---|---|---|
| `0 == ''` | `true` | `''` se convierte a `0` |
| `0 == '0'` | `true` | `'0'` se convierte a `0` |
| `'' == '0'` | `false` | dos strings: se comparan como texto |
| `[] == false` | `true` | `false` → `0`, `[]` → `''` → `0` |
| `null == undefined` | `true` | regla especial |
| `null == 0` | `false` | `null` solo es `==` a `undefined` |
| `NaN == NaN` | `false` | `NaN` no es igual a nada, ni a sí mismo |

Fijate en las tres primeras filas: `0` es igual a `''`, `0` es igual a `'0'`, pero `''` no es igual a `'0'`. Con `==` la igualdad ni siquiera es transitiva. Por eso tu jefe tiene razón.

Con `===` todo eso desaparece:

```js
console.log(0 === '');      // false
console.log('1' === 1);     // false
console.log([] === false);  // false
```

Ahora, `===` también tiene sus detalles:

- `NaN === NaN` es `false`. Para detectarlo usá `Number.isNaN(valor)`.
- Los objetos se comparan por referencia: `{} === {}` es `false`, porque son dos objetos distintos aunque tengan el mismo contenido.
- `0 === -0` es `true`. Si alguna vez necesitás distinguirlos, `Object.is(0, -0)` da `false`.

El único uso de `==` que vas a ver en código serio es `valor == null`, que da `true` para `null` y para `undefined` a la vez. Hoy casi siempre lo reemplazás con `??` u `?.`.

Y cuando los datos vienen como texto (un formulario, un query string), convertí vos de forma explícita en lugar de dejar que lo haga `==`:

```js
const quantity = Number(input.value);
if (quantity === 3) {
  console.log('son tres');
}
```

Para que no se te escape, activá la regla `eqeqeq` de ESLint (`"eqeqeq": ["error", "always", { "null": "ignore" }]` si querés permitir el `== null`).

Probá predecir estos antes de ejecutarlos: `'1' == 1`, `'1' === 1`, `null == false`. Respuestas: `true`, `false`, `false`. El último sorprende: `null` no se convierte a número con `==`. Pero `null >= 0` da `true`, porque los operadores `<`, `>`, `<=` y `>=` sí lo convierten. Otro motivo para no fiarse de la coerción.""",
            },
        ]
    },
    # 20) Coma flotante y dinero (inglés, principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Why does 0.1 + 0.2 give 0.30000000000000004 in JS? I'm building a shopping cart and the totals are sometimes off by a cent. What's the right way to handle money?",
            },
            {
                "role": "assistant",
                "content": """It's not a JavaScript bug. Numbers in JS are IEEE 754 binary64 floats, and `0.1` has no exact binary representation, just like `1/3` has no exact decimal one. The stored value is the closest double, slightly off, and those tiny errors show up when you add. Python, Java and C# `double` behave the same way.

In a cart this bites twice: errors accumulate across lines, and rounding then lands on the wrong side.

```js
console.log((1.005).toFixed(2));             // '1.00', because 1.005 is stored as 1.00499999...
console.log(Math.round(1.005 * 100) / 100);  // 1, same reason
```

**The fix: keep money as integer minor units (cents) everywhere** (API, database, state), and convert to a decimal string only for display. Integers are exact in a JS number up to `Number.MAX_SAFE_INTEGER` (9,007,199,254,740,991), which is far more cents than any cart will hold.

```js
// Prices live as integer cents end to end.
const cart = [
  { sku: 'A1', unitPriceCents: 1999, qty: 3 },
  { sku: 'B2', unitPriceCents: 1005, qty: 1 },
];

const subtotalCents = cart.reduce((sum, line) => sum + line.unitPriceCents * line.qty, 0); // 7002

// Round once, explicitly, where the business rule says so.
const TAX_RATE_BASIS_POINTS = 800; // 8 %
const taxCents = Math.round((subtotalCents * TAX_RATE_BASIS_POINTS) / 10_000); // 560
const totalCents = subtotalCents + taxCents; // 7562

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
console.log(usd.format(totalCents / 100)); // $75.62
```

Three details that matter in real carts:

1. **Splitting amounts must preserve the total.** Dividing $10.00 three ways can't give three equal shares; hand the leftover cents out explicitly:

```js
// For non-negative amounts.
function splitCents(totalCents, parts) {
  const base = Math.floor(totalCents / parts);
  const remainder = totalCents % parts;
  return Array.from({ length: parts }, (_, index) => base + (index < remainder ? 1 : 0));
}

console.log(splitCents(1000, 3)); // [334, 333, 333]
```

2. **Rounding mode is a business decision.** `Math.round` rounds halves toward +∞ (`Math.round(-2.5)` is `-2`), which may not be what your accounting rules say for refunds. Write the rule down and test it.
3. **Not every currency has two decimals.** JPY has zero and KWD has three. Ask `Intl` instead of hard-coding 100:

```js
const digits = new Intl.NumberFormat('en', { style: 'currency', currency: 'JPY' })
  .resolvedOptions().maximumFractionDigits; // 0
```

For interest calculations or very large amounts, use `BigInt` cents or a decimal library such as `big.js` or `dinero.js`, rather than inventing your own.

Quick checks you can paste into a test:

```js
console.assert(0.1 + 0.2 !== 0.3);    // floats drift
console.assert(10 + 20 === 30);       // integer cents don't
console.assert(splitCents(1000, 3).reduce((a, b) => a + b, 0) === 1000);
```""",
            },
        ]
    },
    # 21) Hoisting y zona temporal muerta (principiante, código roto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Me sale `ReferenceError: Cannot access 'PORT' before initialization` y no lo entiendo, la variable SÍ está declarada:

```js
start();

const PORT = Number(process.env.PORT ?? 3000);

function start() {
  console.log(`Escuchando en ${PORT}`);
}
```

Lo más raro es que `start` sí se puede llamar antes de su declaración.""",
            },
            {
                "role": "assistant",
                "content": """Las dos cosas que ves tienen la misma causa: el **hoisting**. Antes de ejecutar una sola línea, JavaScript registra todas las declaraciones del ámbito. Lo que cambia entre ellas es **qué valor tienen antes de llegar a su línea**:

| Declaración | ¿Se puede usar antes de su línea? | Valor hasta entonces |
|---|---|---|
| `function f() {}` | sí | la función completa |
| `var x = 1` | sí | `undefined` |
| `let x` / `const x` | no | zona temporal muerta (TDZ): `ReferenceError` |
| `class C {}` | no | TDZ |
| `const f = () => {}` | no | TDZ (es un `const`) |

Traza de tu archivo:

1. Antes de ejecutar: `start` queda creada con su cuerpo entero; `PORT` queda registrada pero **sin inicializar**.
2. Línea 1: `start()` se ejecuta sin problema, porque la función ya existe.
3. Dentro de `start`, se lee `PORT`. Todavía no se ejecutó la línea del `const`, así que `PORT` está en la TDZ y salta el `ReferenceError`.

El arreglo es ordenar el archivo: primero las constantes, luego las funciones y la llamada al final.

```js
const PORT = Number(process.env.PORT ?? 3000);

function start() {
  console.log(`Escuchando en ${PORT}`);
}

start(); // Escuchando en 3000
```

La TDZ te hizo un favor. Mira lo que pasaría con `var`:

```js
start();
var PORT = 3000;
function start() {
  console.log(`Escuchando en ${PORT}`); // Escuchando en undefined
}
```

Sin error, con un `undefined` silencioso que reventaría más tarde y lejos de aquí. Por eso `let` y `const` se diseñaron para fallar en voz alta.

Si alguna vez ves este mismo error con una variable **importada** de otro archivo, la causa casi siempre es un import circular: `a.js` importa `b.js`, que importa `a.js` y usa algo suyo antes de que `a.js` termine de evaluarse. `npx madge --circular src/` te lista los ciclos.

Un detalle curioso para comprobar que lo entendiste: `typeof variableQueNoExiste` devuelve `'undefined'` sin error, pero `typeof PORT` antes de su `const` lanza el mismo `ReferenceError`. La variable existe; lo que está prohibido es tocarla antes de tiempo.""",
            },
        ]
    },
    # 22) sort muta y toSorted no; Object.groupBy no existe en Node 20 (intermedio, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """En React tengo una lista de productos en el estado y un botón para ordenar por precio. Al darle al botón la tabla no cambia, pero si toco cualquier otra cosa aparece ordenada. Hago esto:

```jsx
const [products, setProducts] = useState(initialProducts);

function sortByPrice() {
  setProducts(products.sort((a, b) => a.price - b.price));
}
```""",
            },
            {
                "role": "assistant",
                "content": """`Array.prototype.sort` **ordena en el sitio y devuelve el mismo array**. Le pasas a `setProducts` exactamente la misma referencia que ya tenía el estado. React compara el estado nuevo con el anterior usando `Object.is`, ve que son el mismo objeto y no vuelve a renderizar. El array sí quedó ordenado (lo mutaste), y por eso aparece en cuanto otra cosa provoca un render.

Además, si `initialProducts` es un array definido fuera del componente, también lo acabas de mutar.

El arreglo es `toSorted` (ES2023: Node 20+, Chrome 110+, Firefox 115+, Safari 16+), que devuelve un array **nuevo**:

```jsx
function sortByPrice() {
  setProducts((current) => current.toSorted((a, b) => a.price - b.price));
}
```

La forma con función (`current => ...`) parte siempre del estado más reciente, aunque haya varias actualizaciones encoladas. Si tuvieras que soportar navegadores antiguos, el equivalente es `[...current].sort(...)`.

La familia completa de métodos que copian en lugar de mutar:

| Muta el original | Devuelve una copia |
|---|---|
| `sort()` | `toSorted()` |
| `reverse()` | `toReversed()` |
| `splice()` | `toSpliced()` |
| `arr[i] = x` | `arr.with(i, x)` |

Dos trampas del comparador:

- Sin comparador, `sort` convierte a texto: `[10, 9, 1].sort()` da `[1, 10, 9]`.
- Para textos, usa `a.name.localeCompare(b.name)`, no la resta.

Comprobación:

```js
const original = [{ price: 3 }, { price: 1 }];
const sorted = original.toSorted((a, b) => a.price - b.price);
console.log(sorted === original); // false: array nuevo
console.log(original[0].price);   // 3: el original no se tocó
console.log(sorted[0].price);     // 1
```""",
            },
            {
                "role": "user",
                "content": "Va. Ahora quise agrupar por categoría con `Object.groupBy` y en local (Node 22) funciona, pero en el servidor de staging revienta con `TypeError: Object.groupBy is not a function`.",
            },
            {
                "role": "assistant",
                "content": """Casi seguro que staging corre Node 20. `Object.groupBy` es de ES2024 y llegó con V8 11.7, es decir, a partir de **Node 21**. Node 20 trae V8 11.3 y no lo tiene. Confírmalo en el servidor:

```bash
node -v
node -p "typeof Object.groupBy"   # 'undefined' en Node 20, 'function' en 22
```

Tienes dos salidas.

**1. Subir staging a Node 22 LTS.** Es lo correcto: Node 20 llegó al final de su soporte en abril de 2026 y staging debería correr la misma versión que producción y que tu máquina. Fija la versión en `engines` y en la imagen de Docker para que no vuelva a divergir.

**2. Si de momento no puedes, una función propia** con el mismo contrato:

```js
// Devuelve un objeto sin prototipo, igual que Object.groupBy.
export function groupBy(items, keyOf) {
  const groups = Object.create(null);
  for (const item of items) {
    (groups[keyOf(item)] ??= []).push(item);
  }
  return groups;
}

const byCategory = groupBy(products, (product) => product.category);
```

El detalle del prototipo nulo no es capricho: `Object.groupBy` también lo hace, para que una categoría llamada `constructor` o `__proto__` no choque con propiedades heredadas. Por eso `console.log` lo muestra como `[Object: null prototype]`.

Si las claves no son strings (por ejemplo, agrupar por un objeto `Date` o por un booleano sin convertirlo a texto), el equivalente es `Map.groupBy`, que devuelve un `Map`.

Y para que esto se detecte antes de desplegar: si usas TypeScript, un `lib` en `tsconfig.json` que no incluya ES2024 marca `Object.groupBy` como inexistente en compilación. Si no, que el CI ejecute los tests con la versión de Node de producción.

Comprobación de que la versión propia y la nativa coinciden (en Node 22):

```js
import assert from 'node:assert/strict';

const items = [{ c: 'a' }, { c: 'b' }, { c: 'a' }];
assert.deepEqual({ ...groupBy(items, (x) => x.c) }, { ...Object.groupBy(items, (x) => x.c) });
```""",
            },
        ]
    },
    # 23) Límite de concurrencia: pool de workers sin librerías (avanzado, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo que descargar unas 2000 imágenes por URL y subirlas a S3. Con `Promise.all(urls.map(download))` el proceso empieza a tirar `ECONNRESET` y `EMFILE: too many open files`. ¿Cómo limito a, digamos, 10 a la vez, sin meter librerías?",
            },
            {
                "role": "assistant",
                "content": """`Promise.all` no controla la concurrencia: solo **espera**. Lo que lanza las 2000 descargas es `urls.map(download)`, que llama a `download` 2000 veces seguidas antes de que `Promise.all` reciba nada. Así abres 2000 sockets y descriptores a la vez: el sistema operativo se queda sin descriptores (`EMFILE`, el límite típico de `ulimit -n` es 1024) y el servidor remoto empieza a cortar conexiones (`ECONNRESET`).

La solución es un **pool de N workers** que van tomando la siguiente URL de una cola compartida:

```js
// map-with-concurrency.js
export async function mapWithConcurrency(items, limit, mapper) {
  if (!Number.isInteger(limit) || limit < 1) {
    throw new RangeError(`limit debe ser un entero >= 1; recibido ${limit}`);
  }
  const results = new Array(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const index = nextIndex++; // seguro: entre esta línea y la anterior no hay await
      try {
        results[index] = { status: 'fulfilled', value: await mapper(items[index], index) };
      } catch (reason) {
        results[index] = { status: 'rejected', reason };
      }
    }
  }

  const workerCount = Math.min(limit, items.length);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return results;
}
```

Por qué está escrito así:

- **No hay condición de carrera en `nextIndex++`.** JavaScript ejecuta un solo hilo; otro worker solo puede intervenir en un `await`, y entre leer y aumentar el índice no hay ninguno.
- **El orden se conserva**: cada resultado se guarda en su índice, termine cuando termine.
- **Los errores no cortan el lote.** Devuelve la misma forma que `Promise.allSettled`. En un trabajo por lotes quieres el informe completo de las 2000, no abortar en la imagen 37 con las demás a medias.

Recordatorio de los combinadores, porque la elección importa:

| | Se resuelve cuando... | Rechaza cuando... |
|---|---|---|
| `Promise.all` | todas se cumplen | la primera rechaza (las demás **siguen corriendo**) |
| `Promise.allSettled` | todas terminan | nunca |
| `Promise.any` | la primera se cumple | todas rechazan (`AggregateError`) |
| `Promise.race` | la primera termina, bien o mal | la primera termina mal |

Uso con tu caso (`uploadToS3` y `keyFor` son tus funciones actuales):

```js
const results = await mapWithConcurrency(urls, 10, async (url) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} en ${url}`);
  const body = Buffer.from(await res.arrayBuffer());
  await uploadToS3(keyFor(url), body);
  return url;
});

const failed = results.filter((result) => result.status === 'rejected');
console.log(`${results.length - failed.length} subidas, ${failed.length} fallidas`);
for (const { reason } of failed) console.error(reason.message);
```

Test que comprueba las dos garantías (límite y orden):

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mapWithConcurrency } from './map-with-concurrency.js';

test('nunca supera el límite y conserva el orden', async () => {
  let active = 0;
  let maxActive = 0;
  const results = await mapWithConcurrency([5, 1, 3, 2, 4], 2, async (ms) => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise((resolve) => setTimeout(resolve, ms));
    active -= 1;
    return ms * 10;
  });

  assert.equal(maxActive, 2);
  assert.deepEqual(results.map((result) => result.value), [50, 10, 30, 20, 40]);
});
```

Si más adelante quieres cancelación o prioridades, `p-limit` hace lo mismo en pocas líneas y está muy probado; para este caso, las 20 líneas de arriba bastan.""",
            },
        ]
    },
    # 24) Trabajo de CPU que bloquea el event loop: medirlo y moverlo a worker_threads (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una API en Express con un endpoint que genera un reporte CSV de unas 200k filas con cálculos (tarda ~4 s). Mientras corre, el health check `/healthz` da timeout y Kubernetes reinicia el pod. ¿Node no era asíncrono? Si el reporte es una función async...",
            },
            {
                "role": "assistant",
                "content": r"""Node es asíncrono **para la E/S**, no para el cálculo. Tu código JavaScript corre en un único hilo: mientras ese hilo está 4 s ocupado en el bucle del reporte, no atiende ninguna otra petición, ni timers, ni el `/healthz`. Marcar la función como `async` no cambia nada: el cuerpo se ejecuta igualmente en el mismo hilo, solo que devuelve una promesa.

**1. Medirlo antes de arreglarlo.** El retraso del event loop es la métrica exacta de este problema:

```js
import { monitorEventLoopDelay } from 'node:perf_hooks';

const loopDelay = monitorEventLoopDelay({ resolution: 20 });
loopDelay.enable();

setInterval(() => {
  // los valores vienen en nanosegundos
  console.log(`event loop p99: ${(loopDelay.percentile(99) / 1e6).toFixed(1)} ms`);
  loopDelay.reset();
}, 10_000).unref();
```

En reposo verás valores de unos 20 ms (la resolución del muestreo). Con un reporte en marcha, el p99 saltará a unos 4000 ms. Eso confirma el diagnóstico.

**2. Las opciones, de menor a mayor esfuerzo:**

| Opción | Cuándo |
|---|---|
| Partir el trabajo en trozos y ceder con `setImmediate` | cálculo moderado; el reporte tarda algo más en total |
| `worker_threads` | CPU real de segundos; quieres el hilo principal libre |
| Cola de trabajos (otro proceso o servicio) | minutos de cálculo o reportes que pueden llegar por correo |

Para 4 s, un worker es lo adecuado.

**3. El worker.** Supongo que hoy tienes una función `buildReport(params)` pura que devuelve el CSV como string.

```js
// report-worker.js
import { parentPort, workerData } from 'node:worker_threads';
import { buildReport } from './build-report.js';

parentPort.postMessage(buildReport(workerData));
```

```js
// run-report.js
import { Worker } from 'node:worker_threads';

export function runReportInWorker(params, { signal } = {}) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./report-worker.js', import.meta.url), { workerData: params });
    const onAbort = () => worker.terminate();
    signal?.addEventListener('abort', onAbort, { once: true });

    worker.once('message', resolve);
    worker.once('error', reject);
    worker.once('exit', (code) => {
      signal?.removeEventListener('abort', onAbort);
      if (code !== 0) reject(new Error(`el worker del reporte terminó con código ${code}`));
    });
  });
}
```

```js
// en la app de Express
app.get('/reports/:id', async (req, res, next) => {
  const controller = new AbortController();
  res.on('close', () => controller.abort()); // si el cliente se va, se mata el worker
  try {
    const csv = await runReportInWorker({ id: req.params.id }, { signal: controller.signal });
    res.type('text/csv').send(csv);
  } catch (err) {
    next(err);
  }
});
```

El `res.on('close')` también se dispara tras una respuesta completa, pero entonces el worker ya terminó y `terminate()` no hace nada.

**4. Costes que hay que conocer:**

- Cada worker es un *isolate* de V8 con su propio heap: arrancarlo cuesta decenas de milisegundos y algunos MB. Con muchas peticiones simultáneas, usa un pool con tamaño fijo, como `piscina`, en lugar de un worker por petición.
- Lo que envías y recibes se **copia** con el algoritmo de clonado estructurado. Para resultados grandes en binario, transfiere un `ArrayBuffer` en lugar de copiarlo.
- `params` no puede contener funciones ni conexiones a la base: pasa datos y abre lo que necesites dentro del worker.

**5. Comprobación.** Lanza un reporte y, mientras corre:

```bash
for i in 1 2 3 4 5; do curl -s -o /dev/null -w '%{time_total}\n' localhost:3000/healthz; done
```

Antes del cambio, cada respuesta tardaba hasta 4 s; después, deben quedar en milisegundos, y el p99 del event loop debe mantenerse cerca de la resolución del muestreo.""",
            },
        ]
    },
    # 25) node:test frente a Jest (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Our small Node 22 library uses Jest for ~40 unit tests, and the Jest + ESM setup keeps causing pain (`SyntaxError: Cannot use import statement outside a module`). Is the built-in `node:test` runner good enough to replace it? What do we lose?",
            },
            {
                "role": "assistant",
                "content": """For a small ESM library on Node 22, yes. The built-in runner has been stable since Node 20, runs native ESM with zero configuration (which removes your current error at the root), and adds no dependencies.

What you keep:

- `describe` / `it` / `test`, plus `before`, `after`, `beforeEach` and `afterEach` hooks.
- Function and method mocks (`t.mock.fn()`, `t.mock.method()`), with call counts and arguments.
- Fake timers (`t.mock.timers`).
- Watch mode, name filtering (`--test-name-pattern`), and reporters (`spec`, `tap`, `dot`, `junit`, `lcov`).
- Coverage with `--experimental-test-coverage`: still flagged, but usable.

What you lose or have to replace:

| Jest | `node:test` |
|---|---|
| `expect(...)` matchers | `node:assert/strict` (fewer helpers, clear diffs) |
| `jest.mock('module')` | `mock.module()`, behind `--experimental-test-module-mocks` (Node 22.3+); prefer dependency injection |
| `jsdom` environment | not built in; for DOM code, Vitest is the better fit |
| large plugin ecosystem | small, and growing |

A migrated test:

```js
// test/slugify.test.js
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { slugify } from '../src/slugify.js';

describe('slugify', () => {
  it('lowercases and joins words with dashes', () => {
    assert.equal(slugify('Hello World'), 'hello-world');
  });

  it('rejects non-string input', () => {
    assert.throws(() => slugify(42), TypeError);
  });
});
```

The matcher mapping covers almost everything in a typical suite:

| Jest | `node:assert/strict` |
|---|---|
| `toBe(x)` | `assert.equal(actual, x)` (uses `Object.is` in strict mode) |
| `toEqual(x)` | `assert.deepEqual(actual, x)` (strict deep equality) |
| `toThrow(Type)` | `assert.throws(fn, Type)` |
| `await expect(p).rejects.toThrow()` | `await assert.rejects(p)` |
| `toMatch(/re/)` | `assert.match(actual, /re/)` |
| `toHaveBeenCalledTimes(n)` | `assert.equal(fn.mock.callCount(), n)` |

Scripts:

```json
{
  "scripts": {
    "test": "node --test",
    "test:watch": "node --test --watch",
    "test:coverage": "node --test --experimental-test-coverage"
  }
}
```

With no arguments, `node --test` finds files named like `*.test.js`, `*-test.js` or `*_test.js`, and files inside `test/` directories.

Migration plan that keeps you safe:

1. Port the tests file by file while both runners still work.
2. Compare the totals: the summary at the end of `node --test` must report the same number of tests that Jest reported, and all passing. A lower count means a file wasn't picked up by the default patterns.
3. Remove Jest, Babel, and their config only after the counts match on CI.

If you later need DOM tests or snapshot-heavy suites, move to Vitest rather than back to Jest: it also handles ESM natively and keeps an `expect` API close to Jest's.""",
            },
        ]
    },
    # 26) || frente a ??, ?. y ??= (principiante, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo una función con opciones y cuando paso `timeout: 0` para desactivar el timeout, igual usa 5000. ¿Qué hice mal?

```js
function createClient(options = {}) {
  const timeout = options.timeout || 5000;
  const retries = options.retries || 3;
  return { timeout, retries };
}

console.log(createClient({ timeout: 0, retries: 0 })); // { timeout: 5000, retries: 3 }
```""",
            },
            {
                "role": "assistant",
                "content": """`||` devuelve el lado derecho cuando el izquierdo es **falsy**, y `0` es falsy. Tu código no distingue «no me pasaron nada» de «me pasaron 0».

Los valores falsy en JavaScript son: `false`, `0`, `-0`, `0n`, `''`, `null`, `undefined` y `NaN`.

Lo que quieres es `??` (*nullish coalescing*, ES2020), que solo usa el valor por defecto cuando el izquierdo es `null` o `undefined`:

```js
function createClient(options = {}) {
  const timeout = options.timeout ?? 5000;
  const retries = options.retries ?? 3;
  return { timeout, retries };
}

console.log(createClient({ timeout: 0, retries: 0 })); // { timeout: 0, retries: 0 }
console.log(createClient());                           // { timeout: 5000, retries: 3 }
```

| Valor de la izquierda | `valor \\|\\| 'def'` | `valor ?? 'def'` |
|---|---|---|
| `undefined` | `'def'` | `'def'` |
| `null` | `'def'` | `'def'` |
| `0` | `'def'` | `0` |
| `''` | `'def'` | `''` |
| `false` | `'def'` | `false` |

Otra forma válida son los valores por defecto en la desestructuración:

```js
function createClient({ timeout = 5000, retries = 3 } = {}) {
  return { timeout, retries };
}
```

Ojo con una diferencia: el valor por defecto de la desestructuración solo actúa con `undefined`, no con `null`. `createClient({ timeout: null })` devuelve `timeout: null`. Con `??` obtendrías 5000.

Regla práctica: usa `||` solo cuando de verdad quieras tratar `0`, `''` y `false` como «vacío». Para valores por defecto, `??`.""",
            },
            {"role": "user", "content": "Ah, ok. ¿Y el `?.` que veo por todos lados? ¿Y qué es `??=`?"},
            {
                "role": "assistant",
                "content": """Son de la misma familia: los dos reaccionan solo ante `null` y `undefined`.

**`?.` (encadenamiento opcional)**: si lo de la izquierda es `null` o `undefined`, corta toda la expresión y devuelve `undefined` en vez de lanzar un `TypeError`.

```js
const user = { profile: null };

console.log(user.profile?.city);  // undefined (sin ?. sería TypeError)
console.log(user.orders?.[0]);    // undefined, también con corchetes
options.onDone?.();               // llama a onDone solo si existe
```

**`??=` (asignación nula)**: asigna solo si la variable o propiedad es `null` o `undefined`.

```js
const options = {};
options.headers ??= {};          // la crea porque no existía
options.headers ??= { a: 1 };    // no hace nada: ya hay un objeto
```

Y, como `??`, no evalúa el lado derecho si no hace falta. `config.port ??= readPortFromDisk()` solo lee el disco cuando falta el puerto. Existen también `||=` y `&&=`, con la lógica de truthy y falsy de `||` y `&&`.

Un patrón muy común que los combina:

```js
const byCategory = {};
for (const product of [{ name: 'té', category: 'bebidas' }, { name: 'pan', category: 'panadería' }]) {
  (byCategory[product.category] ??= []).push(product.name);
}
console.log(byCategory); // { bebidas: [ 'té' ], 'panadería': [ 'pan' ] }
```

Dos advertencias:

- **No llenes el código de `?.` por las dudas.** Si un pedido *siempre* debe tener cliente, `order.customer?.email` esconde el bug: en lugar de un error claro en el sitio correcto, tendrás un `undefined` que aparecerá tres funciones más allá. Usa `?.` solo donde la ausencia es un caso legítimo.
- **`??` no se puede mezclar con `||` o `&&` sin paréntesis**: `a || b ?? c` es un `SyntaxError`. Escribe `(a || b) ?? c` o lo que realmente quieras decir.""",
            },
        ]
    },
    # 27) Proyecto Node 22 desde cero: ESLint 9, Prettier, --watch y --env-file (intermedio, system: conciso)
    {
        "messages": [
            {
                "role": "system",
                "content": "Responde de forma concisa: comandos y archivos completos, con una línea de explicación por paso.",
            },
            {
                "role": "user",
                "content": "Arranco un proyecto Node 22 en ESM desde cero. Quiero ESLint (la versión nueva), Prettier, recarga al guardar y variables de entorno desde un .env, con las mínimas dependencias posibles.",
            },
            {
                "role": "assistant",
                "content": r"""Node 22 ya trae recarga (`--watch`) y lectura de `.env` (`--env-file`), así que no necesitas `nodemon` ni `dotenv`.

**1. Proyecto y dependencias de desarrollo:**

```bash
mkdir api && cd api
npm init -y
npm pkg set type=module
npm install --save-dev eslint @eslint/js globals prettier eslint-config-prettier
```

**2. `eslint.config.js`** (formato *flat config*, el único por defecto en ESLint 9):

```js
import js from '@eslint/js';
import globals from 'globals';
import prettier from 'eslint-config-prettier';

export default [
  { ignores: ['dist/', 'coverage/'] },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: globals.node,
    },
    rules: {
      eqeqeq: ['error', 'always', { null: 'ignore' }],
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  prettier, // siempre al final: apaga las reglas de formato que chocarían con Prettier
];
```

**3. `.prettierrc.json`**: ESLint se ocupa de los bugs; Prettier, del formato.

```json
{ "singleQuote": true, "printWidth": 100 }
```

**4. Scripts en `package.json`:**

```json
{
  "scripts": {
    "dev": "node --watch --env-file=.env src/server.js",
    "start": "node src/server.js",
    "lint": "eslint .",
    "format": "prettier --write .",
    "check": "prettier --check . && eslint . && node --test"
  }
}
```

- `--watch` reinicia el proceso al guardar cualquier archivo importado (estable desde Node 22).
- `--env-file` falla si el archivo no existe; si en algún entorno puede faltar, usa `--env-file-if-exists` (Node 22.9+).
- `start` no lee `.env`: en producción las variables las inyecta la plataforma.

**5. Secretos fuera del repositorio:**

```bash
printf 'PORT=3000\nDATABASE_URL=postgres://localhost/dev\n' > .env
cp .env .env.example   # este sí va al repo, con valores de ejemplo
printf 'node_modules/\n.env\ncoverage/\n' > .gitignore
```

**6. Comprobación:**

```bash
mkdir -p src
echo "if (process.env.PORT == 3000) console.log('dev');" > src/server.js
npm run lint    # debe fallar con eqeqeq en src/server.js
npm run format && npm run check
```

Cambia `==` por `===` comparando con `'3000'` y `npm run check` debe pasar. Luego `npm run dev`: al guardar `src/server.js` verás que el proceso se reinicia solo.""",
            },
        ]
    },
    # 28) JSON.stringify con BigInt y revivir tipos al parsear (intermedio, multiturno, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": "Uso BigInt para unos ids tipo Snowflake (pasan de 2^53) y al responder en la API con `JSON.stringify(payload)` truena: `TypeError: Do not know how to serialize a BigInt`. ¿Cómo lo arreglo?",
            },
            {
                "role": "assistant",
                "content": """JSON no tiene un tipo para enteros grandes, y la especificación prefiere lanzar un error antes que perder precisión en silencio. Y aunque lo serializaras como número, el cliente lo rompería al leerlo: `JSON.parse` convierte cualquier número a `Number`, que solo es exacto hasta 2^53 − 1.

```js
console.log(JSON.parse('{"id": 9007199254740993}').id); // 9007199254740992: perdió una unidad
```

Para un id eso es un bug grave: apuntaría a **otro** registro.

La solución estándar es **enviar los BigInt como strings**. Es lo que hacen las APIs públicas con ids grandes. Con un *replacer*:

```js
export function toJson(value) {
  return JSON.stringify(value, (_key, val) => (typeof val === 'bigint' ? val.toString() : val));
}

console.log(toJson({ id: 2n ** 63n - 1n, title: 'hola' }));
// {"id":"9223372036854775807","title":"hola"}
```

Evita el atajo de `BigInt.prototype.toJSON = function () { ... }`: cambia el comportamiento de todo el proceso, incluidas las librerías que no esperan esa conversión.

Ya que estás aquí, las otras sorpresas de `JSON.stringify`:

| Valor | Resultado |
|---|---|
| `undefined`, funciones, símbolos en un objeto | la propiedad desaparece |
| los mismos dentro de un array | `null` |
| `Date` | string ISO (llama a `toJSON`) |
| `Map`, `Set` | `{}`: pierdes los datos sin aviso |
| `NaN`, `Infinity` | `null` |
| referencia circular | `TypeError: Converting circular structure to JSON` |

La fila de `Map` es la más traicionera: conviértelo antes con `Object.fromEntries(map)`.""",
            },
            {
                "role": "user",
                "content": "Ok, y del otro lado, cuando el cliente recibe el JSON, ¿cómo recupero el BigInt y las fechas?",
            },
            {
                "role": "assistant",
                "content": """Con el segundo argumento de `JSON.parse`, el *reviver*, que recibe cada par clave-valor y puede devolver otro valor. Una precaución importante: el reviver recibe los números **ya convertidos**, así que solo puedes recuperar el BigInt si viajó como string, que es justo lo que hace el `toJson` de antes.

Revive por **nombre de campo conocido**, no adivinando por el formato. Un reviver que convierte en fecha todo lo que «parece una fecha» acabará transformando el texto que escribió un usuario.

```js
const BIGINT_KEYS = new Set(['id', 'authorId']);
const DATE_KEYS = new Set(['createdAt', 'updatedAt']);

export function parsePayload(text) {
  return JSON.parse(text, (key, value) => {
    if (BIGINT_KEYS.has(key) && typeof value === 'string') return BigInt(value);
    if (DATE_KEYS.has(key) && typeof value === 'string') return new Date(value);
    return value;
  });
}
```

`BigInt('abc')` lanza `SyntaxError`, lo cual está bien: un id corrupto debe fallar al entrar, no tres capas más adentro.

Prueba de ida y vuelta que fija el contrato entre los dos lados:

```js
import assert from 'node:assert/strict';
import { parsePayload, toJson } from './json-codec.js';

const original = {
  id: 2n ** 63n - 1n,
  authorId: 9007199254740993n,
  createdAt: new Date('2024-05-01T12:00:00Z'),
  title: 'hola',
};
const back = parsePayload(toJson(original));

assert.equal(back.id, original.id);
assert.equal(back.authorId, 9007199254740993n);       // sin perder la unidad
assert.equal(back.createdAt.getTime(), original.createdAt.getTime());
assert.equal(back.title, 'hola');
```

Funciona porque `JSON.stringify` llama a `toJSON` de la fecha **antes** de pasar el valor al replacer: el replacer ve el string ISO y lo deja pasar.

Cuando el payload crezca, mantener listas de claves a mano se vuelve frágil. En ese punto conviene validar en la frontera con un esquema que además convierta los tipos (zod o valibot, si usas TypeScript), y así un solo archivo describe la forma del JSON y cómo se revive.""",
            },
        ]
    },
    # 29) AsyncLocalStorage para un requestId en todos los logs (avanzado, SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero que todos los logs de una petición lleven el mismo `requestId` sin pasarlo como parámetro por 15 funciones (servicios, repositorios...). Node 22, servidor HTTP propio. ¿Hay algo mejor que una variable global?",
            },
            {
                "role": "assistant",
                "content": r"""Sí: `AsyncLocalStorage`, de `node:async_hooks` (estable desde Node 16). Una variable global no sirve porque las peticiones se **intercalan**: mientras la petición A espera a la base de datos, entra la B y sobrescribe el id, y los logs de A salen con el de B. `AsyncLocalStorage` guarda un contexto que viaja con la cadena asíncrona: todo lo que se ejecute dentro de `run()`, incluidos los `await`, timers y callbacks que se creen ahí, ve el mismo valor.

```js
// request-context.js
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomUUID } from 'node:crypto';

const storage = new AsyncLocalStorage();

export function runWithRequestContext(req, fn) {
  const requestId = req.headers['x-request-id'] ?? randomUUID();
  return storage.run({ requestId }, fn);
}

export function currentRequestId() {
  return storage.getStore()?.requestId;
}
```

```js
// logger.js
import { currentRequestId } from './request-context.js';

export function log(level, message, fields = {}) {
  const entry = { time: new Date().toISOString(), level, message, requestId: currentRequestId(), ...fields };
  process.stdout.write(`${JSON.stringify(entry)}\n`);
}
```

Un servicio cualquiera, sin saber nada del id:

```js
// orders-service.js
import { setTimeout as sleep } from 'node:timers/promises';
import { log } from './logger.js';

export async function getOrder(id) {
  await sleep(20); // simula la consulta a la base de datos
  log('debug', 'pedido leído', { orderId: id }); // sale con el requestId correcto
  return { id, status: 'paid' };
}
```

```js
// server.js
import { createServer } from 'node:http';
import { log } from './logger.js';
import { getOrder } from './orders-service.js';
import { runWithRequestContext } from './request-context.js';

createServer((req, res) => {
  runWithRequestContext(req, async () => {
    try {
      log('info', 'petición recibida', { url: req.url });
      const order = await getOrder(req.url.slice(1));
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify(order));
    } catch (err) {
      log('error', 'falló la petición', { error: err.message });
      res.statusCode = 500;
      res.end();
    }
  });
}).listen(3000);
```

Lo que conviene saber antes de adoptarlo:

1. **El contexto se captura al crear el recurso asíncrono.** Algunas librerías con colas o pools propios ejecutan tus callbacks desde un contexto creado antes de la petición, y ahí `getStore()` devuelve `undefined`. Si te pasa con un callback concreto, envuélvelo con `AsyncResource.bind(fn)` en el momento de registrarlo.
2. **Guarda poco y no lo mutes desde varios sitios.** Un objeto pequeño con el id y, como mucho, el usuario autenticado. No es un sustituto de pasar dependencias.
3. **No reemplaza los parámetros explícitos** para datos de negocio. Úsalo para lo transversal (trazas, logs, métricas), donde pasar el id por 15 firmas sería ruido.
4. Si usas Fastify, `request.log` ya incluye el `reqId`; `AsyncLocalStorage` cubre el código que no recibe `request`.

Test de lo que de verdad importa, que dos peticiones intercaladas no se mezclen:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { currentRequestId, runWithRequestContext } from './request-context.js';

test('cada petición concurrente conserva su requestId', async () => {
  const seen = [];
  const handle = (id, delayMs) =>
    runWithRequestContext({ headers: { 'x-request-id': id } }, async () => {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      seen.push([id, currentRequestId()]);
    });

  await Promise.all([handle('a', 20), handle('b', 5)]);
  assert.deepEqual(seen, [['b', 'b'], ['a', 'a']]); // b termina antes, y cada una ve su id
});
```

Con una variable global en lugar de `AsyncLocalStorage`, el mismo test daría `[['b', 'b'], ['a', 'b']]`.""",
            },
        ]
    },
    # 30) Ordenar texto en español con Intl.Collator (principiante-intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Ordeno una lista de ciudades con `.sort()` y me quedan «Ávila» y «Écija» al final, después de «Zaragoza». Y las que empiezan en minúscula salen todas detrás de las mayúsculas. ¿Cómo ordeno bien en español?",
            },
            {
                "role": "assistant",
                "content": r"""`sort()` sin comparador ordena por **código de unidad UTF-16**, no alfabéticamente. Para él, `'Á'` es el número 193 y `'Z'` el 90, así que toda letra con tilde va detrás de la Z. Y las minúsculas (`'a'` = 97) van detrás de todas las mayúsculas.

Para ordenar como lo haría una persona, usa `Intl.Collator`, que aplica las reglas del idioma:

```js
const cities = ['Zaragoza', 'Ávila', 'barcelona', 'Écija', 'Madrid', 'Ñuñoa', 'Navarra'];

const collator = new Intl.Collator('es');
console.log(cities.toSorted(collator.compare));
// ['Ávila', 'barcelona', 'Écija', 'Madrid', 'Navarra', 'Ñuñoa', 'Zaragoza']
```

Fíjate en la Ñ: en español es una letra propia, entre la N y la O. El collator `'es'` lo sabe; un orden «quitando tildes» no.

Por qué `Intl.Collator` y no `localeCompare` en cada comparación: `a.localeCompare(b, 'es')` da el mismo resultado, pero puede preparar las reglas del idioma en cada llamada. Ordenar 100 000 elementos hace unos 1,7 millones de comparaciones; crear el collator una vez y reutilizar `collator.compare` es notablemente más rápido.

Dos opciones que resuelven casos frecuentes:

```js
// numeric: 'archivo2' antes que 'archivo10'
const natural = new Intl.Collator('es', { numeric: true });
console.log(['archivo10', 'archivo2', 'archivo1'].toSorted(natural.compare));
// ['archivo1', 'archivo2', 'archivo10']

// sensitivity: 'base' para buscar ignorando tildes y mayúsculas
const loose = new Intl.Collator('es', { sensitivity: 'base' });
console.log(loose.compare('avila', 'Ávila') === 0); // true
console.log(loose.compare('nandu', 'ñandú') === 0); // false: la ñ no es una n
```

Si en lugar de un collator usas la receta de quitar diacríticos para comparar:

```js
const strip = (text) => text.normalize('NFD').replace(/\p{Diacritic}/gu, '');
console.log(strip('ñandú')); // 'nandu'
```

ten presente que también convierte la ñ en n, porque en la forma descompuesta la ñ es una n más una tilde combinable. Para buscar puede valer; para ordenar o comparar en español, mejor el collator.

Comprobación:

```js
import assert from 'node:assert/strict';

const sorted = ['Zaragoza', 'Ávila', 'Ñuñoa', 'Navarra'].toSorted(new Intl.Collator('es').compare);
assert.deepEqual(sorted, ['Ávila', 'Navarra', 'Ñuñoa', 'Zaragoza']);
```

Node incluye los datos completos de ICU desde la versión 13, así que estos resultados son iguales en Node que en el navegador.""",
            },
        ]
    },
]
