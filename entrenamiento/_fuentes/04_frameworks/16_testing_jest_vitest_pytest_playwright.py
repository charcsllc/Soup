"""Testing: principios, Vitest, Jest, Testing Library, pytest, Playwright, msw/respx, contratos, Testcontainers."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# ---------------------------------------------------------------------------
# 1-4: principios (pirámide, tests que sobreviven refactors, determinismo, TDD sobre un bug)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Acabo de entrar a un equipo y me piden «escribir tests» para un servicio de pedidos en Node. No sé ni por dónde empezar: ¿unitarios, de integración, e2e? ¿Qué pruebo y qué no?",
            },
            {
                "role": "assistant",
                "content": r"""Empieza por los tests unitarios de la lógica de negocio y añade pocos de integración en los bordes (base de datos, HTTP). Los e2e déjalos para dos o tres flujos críticos. Esa es la «pirámide»: muchos tests rápidos abajo, pocos lentos arriba.

**Qué probar (en este orden de valor):**

1. **Decisiones.** Cada `if`, cada cálculo, cada regla de negocio: «un pedido con cupón caducado no aplica descuento». Son baratos y fallan por una sola razón.
2. **Bordes.** Lista vacía, cantidad cero, importe negativo, fecha límite exacta. Ahí viven los bugs.
3. **Contratos con el exterior.** Que tu repositorio de pedidos guarda y recupera lo mismo contra una base de datos real (integración, uno o dos por repositorio).
4. **Flujos que, si se rompen, pierdes dinero.** «Crear pedido → pagar → ver confirmación» como e2e. Uno, no veinte.

**Qué no probar:**

- El framework (que Express enruta, que Prisma hace `INSERT`).
- Getters, mapeos triviales, constantes.
- Detalles internos: qué función privada llama a cuál. Eso se rompe con cada refactor y no detecta bugs.

Un test unitario de pedidos con Vitest, para que veas el tamaño que debe tener:

```ts
// order.test.ts
import { describe, expect, it } from 'vitest'
import { applyCoupon } from './order'

describe('applyCoupon', () => {
  it('aplica el descuento cuando el cupón está vigente', () => {
    const order = { total: 100, createdAt: new Date('2025-05-10') }
    const coupon = { percent: 10, expiresAt: new Date('2025-06-01') }

    expect(applyCoupon(order, coupon).total).toBe(90)
  })

  it('ignora el cupón caducado el mismo día de expiración', () => {
    const order = { total: 100, createdAt: new Date('2025-06-01T12:00:00Z') }
    const coupon = { percent: 10, expiresAt: new Date('2025-06-01T00:00:00Z') }

    expect(applyCoupon(order, coupon).total).toBe(100)
  })
})
```

Fíjate en tres cosas: el nombre dice **qué comportamiento** se espera (no «test 1» ni «funciona»), cada test tiene una sola aserción relevante, y el segundo cubre un borde (el límite exacto) que es donde alguien se equivocará al cambiar `<` por `<=`.

**Regla práctica para decidir el nivel:** si puedes probarlo sin arrancar nada (sin BD, sin red), es unitario y lo escribes primero. Si necesitas una BD, es de integración y usas una real en Docker, no un mock de la BD. Si necesitas el navegador, es e2e y lo reservas para lo que de verdad importa.

Comprobación de que vas bien: tu suite unitaria debería correr en segundos y, cuando un test falla, el nombre del test y el `expect` te deberían decir el bug sin abrir el depurador. Si no es así, el test está probando demasiado a la vez.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Cada vez que refactorizo se me rompen 40 tests aunque el comportamiento no cambió nada. Uso vitest con muchos `vi.fn()` y `toHaveBeenCalledWith`. ¿Qué estoy haciendo mal?",
            },
            {
                "role": "assistant",
                "content": r"""Tus tests están acoplados a la **implementación**, no al **comportamiento**. `toHaveBeenCalledWith` sobre colaboradores internos convierte cada test en una copia de cómo está escrito el código; al reescribirlo, el test falla aunque el resultado sea idéntico.

Diagnóstico rápido: un test que se rompe en un refactor que no cambia comportamiento es, por definición, un test incorrecto. No lo arregles para que pase: reescríbelo.

**El patrón que rompe:**

```ts
it('crea el pedido', async () => {
  const repo = { save: vi.fn(), findById: vi.fn() }
  const mailer = { send: vi.fn() }
  const service = new OrderService(repo, mailer)

  await service.create({ items: [{ sku: 'A1', qty: 2 }] })

  expect(repo.save).toHaveBeenCalledWith(expect.objectContaining({ status: 'pending' }))
  expect(mailer.send).toHaveBeenCalledTimes(1)
})
```

Esto prueba «llamas a `save` con `status: 'pending'` y a `send` una vez». Si mañana `save` pasa a llamarse `insert`, o agrupas el envío de correos, 40 tests así caen sin que haya un bug.

**El patrón que sobrevive:** aserciones sobre el estado observable, con colaboradores reales o dobles en memoria, y mocks solo en el borde donde hay I/O inevitable.

```ts
class InMemoryOrderRepo implements OrderRepo {
  private rows = new Map<string, Order>()
  async save(order: Order) { this.rows.set(order.id, order) }
  async findById(id: string) { return this.rows.get(id) ?? null }
}

class FakeMailer implements Mailer {
  sent: Array<{ to: string; subject: string }> = []
  async send(msg: { to: string; subject: string }) { this.sent.push(msg) }
}

it('un pedido nuevo queda pendiente y el cliente recibe confirmación', async () => {
  const repo = new InMemoryOrderRepo()
  const mailer = new FakeMailer()
  const service = new OrderService(repo, mailer)

  const order = await service.create({ customerEmail: 'ana@example.com', items: [{ sku: 'A1', qty: 2 }] })

  expect((await repo.findById(order.id))?.status).toBe('pending')
  expect(mailer.sent).toEqual([{ to: 'ana@example.com', subject: expect.stringContaining('confirmación') }])
})
```

Ahora puedes renombrar métodos, dividir `OrderService` en dos clases o cambiar el orden de las llamadas: el test sigue verde mientras el pedido quede pendiente y el correo salga.

**Reglas para decidir cuándo sí usar `vi.fn()`:**

- Mockea lo que **no puedes** ejecutar en el test: red, reloj, aleatoriedad, pasarela de pago. Y aun ahí, prefiere un fake con comportamiento (como `FakeMailer`) a un espía con `toHaveBeenCalledWith`.
- Afirma sobre la interacción solo cuando la interacción **es** el requisito: «no se cobra dos veces» justifica `expect(gateway.charge).toHaveBeenCalledTimes(1)`.
- Nunca mockees el módulo que estás probando ni sus funciones internas. Si te hace falta, el módulo está mal dividido, no el test.

Verificación: aplica un refactor trivial (renombra un método privado, extrae una función) sin tocar los tests. Los que se rompan son los que hay que reescribir con este patrón. Hazlo por lotes: primero los del módulo que más refactorizas.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un test que pasa en local y falla de vez en cuando en CI. La función genera un id de pedido con `Date.now()` y `Math.random()`. ¿Cómo lo hago determinista?",
            },
            {
                "role": "assistant",
                "content": r"""Haz que el tiempo y la aleatoriedad sean **dependencias inyectadas**, no globales. Un test determinista controla todo lo que puede variar entre ejecuciones; `Date.now()` y `Math.random()` son las dos fuentes más comunes, pero no las únicas.

**Arreglo en el código (preferido):**

```ts
export type Clock = () => number
export type Random = () => number

export function makeOrderId(clock: Clock = Date.now, random: Random = Math.random): string {
  const stamp = clock().toString(36)
  const noise = Math.floor(random() * 0xffff).toString(16).padStart(4, '0')
  return `ord_${stamp}_${noise}`
}
```

El test fija ambas:

```ts
it('genera un id estable para el mismo instante y semilla', () => {
  const id = makeOrderId(() => 1_735_689_600_000, () => 0.5)
  expect(id).toBe('ord_m5c3es9c_7fff')
})
```

**Arreglo sin tocar la firma (cuando el código no es tuyo):** Vitest puede falsear el reloj y espiar `Math.random`.

```ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2025-01-01T00:00:00Z'))
  vi.spyOn(Math, 'random').mockReturnValue(0.5)
})
afterEach(() => vi.useRealTimers())
```

Prefiero la inyección porque deja el acoplamiento a la vista en la firma; los fakes globales se olvidan y contaminan otros tests del mismo archivo.

**Las otras fuentes de no determinismo que debes revisar**, porque «falla solo en CI» casi siempre es una de estas:

| Fuente | Síntoma típico | Solución |
|---|---|---|
| Orden de ejecución / estado compartido | falla solo cuando corre con otros tests | sin estado a nivel de módulo; `beforeEach` que reconstruye |
| Zona horaria | fechas que cambian de día | `TZ=UTC` en `package.json` y en CI; fechas con `Z` explícita |
| Red o disco real | timeouts aleatorios | msw, `tmp_path`, fakes |
| Concurrencia (`Promise.all`, workers) | orden de resultados distinto | ordena antes de afirmar, o afirma con `toEqual(expect.arrayContaining(...))` solo si el orden no es requisito |
| Iteración de `Set`/`Map`/objetos | orden «cambia» | el orden de inserción es estable; si dependes de otro, ordena |

Comprobación: ejecuta el test en bucle hasta que confíes. Vitest tiene `repeats` para esto:

```ts
it('genera ids distintos para instantes distintos', { repeats: 200 }, () => {
  expect(makeOrderId(() => 1, () => 0)).not.toBe(makeOrderId(() => 2, () => 0))
})
```

Si con 200 repeticiones y `TZ=UTC` sigue fallando, la causa no es el id: es estado compartido entre tests.""",
            },
            {
                "role": "user",
                "content": "Lo hice y sigue fallando solo en CI, 1 de cada 10. El test crea tres pedidos en un bucle con `createdAt: new Date()`, los ordena por fecha descendente y espera los ids `[3, 2, 1]`.",
            },
            {
                "role": "assistant",
                "content": r"""Ya tienes la causa: los tres pedidos se crean en el mismo milisegundo y el orden «descendente» entre fechas iguales no está definido por tu criterio, sino por el algoritmo de ordenación. En CI la máquina es más rápida (o menos cargada), así que las colisiones de milisegundo son más frecuentes: 1 de cada 10.

Traza del caso que falla:

```
pedido 1: createdAt = 1735689600000
pedido 2: createdAt = 1735689600000   ← mismo ms
pedido 3: createdAt = 1735689600001
sort((a, b) => b.createdAt - a.createdAt)  →  [3, 1, 2]   (estable: 1 y 2 conservan su orden de entrada)
esperado                                   →  [3, 2, 1]
```

`Array.prototype.sort` es estable desde Node 11, así que los empates mantienen el orden de inserción: `[1, 2]`, no `[2, 1]`.

Hay dos bugs, y el test te ha encontrado los dos:

**1. El test depende del reloj real.** Dale instantes distintos y explícitos, con el `Clock` que ya inyectaste:

```ts
it('lista los pedidos del más reciente al más antiguo', () => {
  let now = 1_735_689_600_000
  const clock = () => now++            // cada llamada avanza 1 ms
  const service = new OrderService(repo, clock)

  const ids = [1, 2, 3].map((n) => service.create({ customerId: n }).id)
  const listed = service.listRecent().map((o) => o.id)

  expect(listed).toEqual([ids[2], ids[1], ids[0]])
})
```

**2. El código de producción tiene un orden ambiguo.** Dos pedidos reales también pueden compartir milisegundo (dos clientes a la vez), y entonces tu listado «reciente primero» mostrará un orden arbitrario que cambia entre peticiones. Añade un criterio de desempate determinista:

```ts
listRecent(): Order[] {
  return [...this.orders].sort(
    (a, b) => b.createdAt - a.createdAt || b.sequence - a.sequence,
  )
}
```

donde `sequence` es un contador monótono asignado al crear (o el id, si es creciente). Y escribe el test que fija ese contrato:

```ts
it('desempata pedidos del mismo instante por orden de creación', () => {
  const clock = () => 1_735_689_600_000  // mismo ms siempre
  const service = new OrderService(repo, clock)
  const first = service.create({ customerId: 1 })
  const second = service.create({ customerId: 2 })

  expect(service.listRecent().map((o) => o.id)).toEqual([second.id, first.id])
})
```

Este segundo test habría fallado el 100 % de las veces con el código viejo, que es exactamente lo que quieres de un test de regresión: nada de «1 de cada 10».""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Me reportaron que `slugify('Año Nuevo 2025!')` devuelve `ao-nuevo-2025` (se come la ñ). Quiero arreglarlo con TDD pero nunca lo he hecho de verdad, siempre escribo el test después. ¿Me guías paso a paso?",
            },
            {
                "role": "assistant",
                "content": r"""El ciclo para un bug es: reproducir con un test que falla → arreglo mínimo → verde → ampliar bordes → dejar el test como guardia. Lo hacemos con tu caso.

**Paso 1. Escribe el test que reproduce el bug, antes de tocar nada.** El nombre describe el comportamiento esperado, no el bug.

```ts
// slugify.test.ts
import { expect, it } from 'vitest'
import { slugify } from './slugify'

it('translitera la ñ en vez de eliminarla', () => {
  expect(slugify('Año Nuevo 2025!')).toBe('ano-nuevo-2025')
})
```

Ejecútalo y mira que falla **por la razón correcta**:

```
AssertionError: expected 'ao-nuevo-2025' to be 'ano-nuevo-2025'
```

Si fallara por otra cosa (import roto, nombre mal escrito), el test no está probando el bug. Este paso es el que casi todo el mundo se salta, y es el que da valor al test: ya sabes que detecta el problema.

**Paso 2. Entiende por qué.** La implementación actual probablemente es algo así:

```ts
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}
```

`ñ` no está en `[a-z0-9]`, así que el `replace` la convierte en guion y el guion se fusiona con el siguiente: `a-o` → se queda `ao` porque `ñ` estaba pegada a `a` y `o`. Hipótesis confirmada por el output `ao-nuevo-2025`.

**Paso 3. Arreglo mínimo.** Descompón los caracteres acentuados (NFD separa `ñ` en `n` + tilde combinante) y elimina las marcas diacríticas antes de filtrar:

```ts
export function slugify(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}
```

Ejecuta: verde. No añadas nada más todavía.

**Paso 4. Amplía con los bordes que el arreglo te sugiere**, uno por uno, viendo cada uno en rojo antes de que pase (si uno pasa a la primera, bien: documenta el comportamiento igualmente).

```ts
it.each([
  ['Camión y café', 'camion-y-cafe'],
  ['  espacios   dobles ', 'espacios-dobles'],
  ['Ça va? Straße', 'ca-va-strae'],
  ['emoji 🎉 fiesta', 'emoji-fiesta'],
  ['---', ''],
])('slugify(%j) → %j', (input, expected) => {
  expect(slugify(input)).toBe(expected)
})
```

El caso `Straße` → `strae` te obliga a una decisión: la `ß` no tiene diacrítico, se pierde. Si quieres `strasse`, es un requisito nuevo (mapa de sustituciones), no parte de este bug. Déjalo documentado en el test tal como se comporta hoy y abre un ticket aparte. TDD también sirve para **no** ampliar el alcance sin querer.

**Paso 5. Commit con test y arreglo juntos:** `fix(slugify): transliterate diacritics instead of dropping them`. Quien lea el historial ve el bug, el caso y la solución en un solo cambio.

Verificación final: vuelve a poner la implementación vieja un momento y ejecuta la suite. Deben fallar exactamente el test de la ñ y el de «Camión y café». Si falla alguno más, ese test estaba acoplado a otra cosa.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 5-11: Vitest (config, vi.mock/hoisted, fake timers, snapshots, cobertura, msw, velocidad)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y comentarios breves en español."},
            {
                "role": "user",
                "content": "Configúrame Vitest en un proyecto TypeScript + React con Vite. Quiero jsdom, jest-dom, cobertura con umbrales y que respete el alias `@/` que ya tengo en vite.config.ts.",
            },
            {
                "role": "assistant",
                "content": r"""```bash
npm i -D vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

```ts
// vitest.config.ts
// Se fusiona con vite.config.ts: hereda plugins (react) y resolve.alias, así `@/` funciona igual en tests.
import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      globals: true, // habilita describe/it/expect globales y el auto-cleanup de Testing Library
      setupFiles: ['./tests/setup.ts'],
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      css: false, // no procesa CSS en tests: más rápido
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,tsx}'],
        exclude: ['src/**/*.d.ts', 'src/main.tsx', 'src/**/*.stories.tsx'],
        reporter: ['text', 'html', 'lcov'],
        thresholds: { lines: 80, functions: 80, branches: 70, statements: 80 },
      },
    },
  }),
)
```

```ts
// tests/setup.ts
// Registra los matchers de jest-dom (toBeInTheDocument, toHaveTextContent...) en expect de Vitest.
import '@testing-library/jest-dom/vitest'
```

```jsonc
// tsconfig.json (solo lo que cambia)
{
  "compilerOptions": {
    // tipos de los globales de Vitest y de los matchers de jest-dom
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  }
}
```

```jsonc
// package.json (scripts)
{
  "scripts": {
    "test": "vitest",                      // modo watch en desarrollo
    "test:ci": "vitest run --coverage",    // una pasada; falla si no se cumplen los umbrales
    "typecheck": "tsc --noEmit"            // Vitest transpila con esbuild y NO comprueba tipos
  }
}
```

```tsx
// src/components/Greeting.test.tsx — prueba de humo para validar la configuración
import { render, screen } from '@testing-library/react'
import { Greeting } from '@/components/Greeting' // el alias resuelve gracias a mergeConfig

it('muestra el nombre', () => {
  render(<Greeting name="Ana" />)
  expect(screen.getByRole('heading', { name: /hola, ana/i })).toBeInTheDocument()
})
```""",
            },
        ]
    },
]
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Vitest no me mockea el módulo de base de datos. Este es el test:

```ts
import { expect, it, vi } from 'vitest'
import { getProfile } from './profile'

const mockFindUser = vi.fn()
vi.mock('./db', () => ({ findUser: mockFindUser }))

it('devuelve el nombre del usuario', async () => {
  mockFindUser.mockResolvedValue({ id: 1, name: 'Ana' })
  expect(await getProfile(1)).toEqual({ name: 'Ana' })
})
```

Y falla con:

```
Error: [vitest] There was an error when mocking a module. If you are using "vi.mock" factory, make sure there are no top level variables inside, since this call is hoisted to top of the file. Read more: https://vitest.dev/api/vi.html#vi-mock
Caused by: ReferenceError: Cannot access 'mockFindUser' before initialization
```""",
            },
            {
                "role": "assistant",
                "content": r"""El mensaje lo dice literalmente: `vi.mock` se **eleva** (hoisting) al principio del archivo, por encima de los `import` y de `const mockFindUser`. Cuando la fábrica se ejecuta, `mockFindUser` todavía está en la zona temporal muerta, de ahí el `ReferenceError`.

El orden real de ejecución de tu archivo es este:

```
1. vi.mock('./db', () => ({ findUser: mockFindUser }))   ← elevado
2. import { getProfile } from './profile'                 ← ./profile importa ./db, la fábrica corre aquí
3. const mockFindUser = vi.fn()                           ← demasiado tarde
```

Tienes tres arreglos válidos; elige según cuánto control necesites.

**1. `vi.hoisted` (el arreglo directo a tu código).** Eleva también la creación del mock, para que exista cuando la fábrica lo use:

```ts
import { expect, it, vi } from 'vitest'
import { getProfile } from './profile'

const { mockFindUser } = vi.hoisted(() => ({ mockFindUser: vi.fn() }))
vi.mock('./db', () => ({ findUser: mockFindUser }))

it('devuelve el nombre del usuario', async () => {
  mockFindUser.mockResolvedValue({ id: 1, name: 'Ana' })
  expect(await getProfile(1)).toEqual({ name: 'Ana' })
})
```

**2. Automock + `vi.mocked` (más corto si el módulo solo tiene funciones).** Sin fábrica, Vitest sustituye cada export por un `vi.fn()` y tú lo tipas al usarlo:

```ts
import { expect, it, vi } from 'vitest'
import { findUser } from './db'
import { getProfile } from './profile'

vi.mock('./db')

it('devuelve el nombre del usuario', async () => {
  vi.mocked(findUser).mockResolvedValue({ id: 1, name: 'Ana', email: 'ana@example.com' })
  expect(await getProfile(1)).toEqual({ name: 'Ana' })
})
```

Ventaja: `vi.mocked(findUser)` conserva la firma real, así que `mockResolvedValue` te exige el tipo de retorno correcto (fíjate en que tuve que añadir `email`). Con tu `vi.fn()` suelto, el mock devolvía cualquier cosa.

**3. Mock parcial con el módulo original**, cuando solo quieres sustituir una función y mantener el resto:

```ts
vi.mock(import('./db'), async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, findUser: vi.fn() }
})
```

La forma `vi.mock(import('./db'), ...)` (Vitest 2.1+) tipa `importOriginal` automáticamente.

Dos detalles que te ahorrarán el siguiente error:

- Si el módulo tiene `export default`, la fábrica debe devolver `{ default: ... }` explícitamente; Vitest lanza un error claro si falta.
- Los mocks acumulan llamadas entre tests. Pon `mockReset: true` en `test` de `vitest.config.ts` (o `vi.resetAllMocks()` en `beforeEach`) para que cada test empiece limpio.

Verificación: con la opción 1 o 2, añade un segundo test que haga `mockFindUser.mockResolvedValue(null)` y espere que `getProfile` lance `UserNotFound`. Si ese test ve el valor del test anterior, te falta el `mockReset`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo una función `debounce` y un `startPolling` que hace fetch cada 5 s con setInterval. Los tests con timers reales tardan y a veces fallan. ¿Cómo los pruebo con fake timers en Vitest sin que se cuelguen?",
            },
            {
                "role": "assistant",
                "content": r"""Con `vi.useFakeTimers()` controlas el reloj: avanzas el tiempo tú y el test termina en milisegundos. La regla que evita los cuelgues: si el código mezcla timers con promesas, avanza con la variante **`Async`** (`vi.advanceTimersByTimeAsync`), que además de disparar los timers vacía la cola de microtareas entre ellos.

**Caso 1: `debounce` (solo timers, síncrono).**

```ts
// debounce.ts
export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number) {
  let timer: ReturnType<typeof setTimeout> | undefined
  return (...args: A) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), ms)
  }
}
```

```ts
// debounce.test.ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { debounce } from './debounce'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

it('llama una sola vez, con el último argumento, tras el periodo de silencio', () => {
  const fn = vi.fn()
  const debounced = debounce(fn, 300)

  debounced('a')
  vi.advanceTimersByTime(200)
  debounced('b')
  vi.advanceTimersByTime(299)
  expect(fn).not.toHaveBeenCalled()   // el segundo evento reinició la cuenta

  vi.advanceTimersByTime(1)
  expect(fn).toHaveBeenCalledTimes(1)
  expect(fn).toHaveBeenCalledWith('b')
})
```

Avanzar `299` y luego `1` prueba el límite exacto; es la aserción que detecta un `<` por `<=` en una reimplementación.

**Caso 2: `startPolling` (timers + `await fetch`).**

```ts
// polling.ts
export function startPolling(url: string, onData: (d: unknown) => void, everyMs = 5_000) {
  const tick = async () => {
    const res = await fetch(url)
    if (res.ok) onData(await res.json())
  }
  void tick()
  const id = setInterval(tick, everyMs)
  return () => clearInterval(id)
}
```

```ts
// polling.test.ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { startPolling } from './polling'

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ ok: true })))
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it('consulta al arrancar y luego cada 5 s hasta que se detiene', async () => {
  const onData = vi.fn()
  const stop = startPolling('/api/status', onData)

  await vi.advanceTimersByTimeAsync(0)        // resuelve el primer fetch
  expect(onData).toHaveBeenCalledTimes(1)

  await vi.advanceTimersByTimeAsync(10_000)   // dos ticks más
  expect(onData).toHaveBeenCalledTimes(3)

  stop()
  await vi.advanceTimersByTimeAsync(10_000)
  expect(onData).toHaveBeenCalledTimes(3)     // nada después de parar
})
```

Si aquí usas `vi.advanceTimersByTime` (síncrono), el `setInterval` dispara `tick`, pero el `await fetch` queda pendiente y `onData` nunca se llama dentro del test: ese es el «se cuelga» o el «espera 1 llamada, recibe 0» que estabas viendo.

**Tres trampas más:**

- `vi.runAllTimers()` con un `setInterval` activo entra en bucle (Vitest corta a 10 000 timers y lanza error). Usa `advanceTimersByTime` o `runOnlyPendingTimers`.
- Los fake timers también sustituyen `Date`. Si el código compara `Date.now()`, fija el instante con `vi.setSystemTime(new Date('2025-01-01T00:00:00Z'))` para que las aserciones sean reproducibles.
- `useRealTimers()` en `afterEach` es obligatorio: si un test falla a mitad y no restaura, los siguientes archivos del mismo worker heredan el reloj falso y fallan de forma «aleatoria».

Comprobación: ejecuta `vitest run polling.test.ts` y mira la duración: debe estar por debajo de 50 ms. Si tarda 5 s, algún timer real sigue vivo (normalmente un `fetch` sin stub).""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Los snapshots son buena idea? En mi equipo hay como 300 archivos `.snap` de componentes React y la gente hace `vitest -u` sin mirar nada cuando fallan.",
            },
            {
                "role": "assistant",
                "content": r"""Los snapshots son buena idea para una clase concreta de salida; lo que describes (300 `.snap` de componentes completos, actualizados a ciegas) es el caso donde no aportan nada: nadie puede revisar un diff de 400 líneas de DOM, así que el test no protege de nada y solo cuesta tiempo.

**Cuándo sí.** La salida es **texto serializado, estable y que una persona puede leer de un vistazo**:

- Mensajes de error y de validación (`"email: formato inválido"`).
- SQL o consultas generadas por un query builder.
- Salida de un CLI (`--help`, una tabla).
- Configuración derivada (el objeto que produce `buildWebpackConfig()`).
- Un fragmento pequeño de HTML/JSX, si el *markup* es el requisito (un email transaccional).

**Cuándo no.** Objetos grandes, DOM entero, cualquier cosa con ids, fechas o estilos generados. Si el snapshot tiene más de ~20 líneas, casi seguro que estás en este caso.

**Tres reglas para que los que queden valgan:**

1. **Inline por defecto.** `toMatchInlineSnapshot()` escribe el valor esperado en el propio test, así que se revisa en el PR junto al código y nadie puede hacer `-u` sin que el diff salte a la vista:

```ts
it('describe el error de validación en español', () => {
  expect(formatIssues(parseUser({ email: 'x' }))).toMatchInlineSnapshot(`
    "email: formato inválido
    name: obligatorio"
  `)
})
```

2. **Un snapshot cubre una decisión.** Si falla, la razón debe caber en una frase. «Cambió el texto del error» sí; «cambió algo del formulario» no.

3. **`-u` solo con el diff delante.** En CI, `vitest run` falla si un snapshot no coincide y **no** escribe ninguno nuevo (`--ci` lo activa Vitest automáticamente cuando detecta `CI=true`). Eso evita que un snapshot nazca en el servidor sin que nadie lo vea.

Para los 300 archivos: no los borres de golpe. Cada vez que uno falle, sustitúyelo por aserciones sobre lo que ese componente debe hacer, y elimina el `.snap`. En tres meses los que queden serán los que de verdad detectaban algo.""",
            },
            {
                "role": "user",
                "content": "Vale, ¿y cómo sustituyo concretamente un snapshot de un `<OrderSummary order={...} />` entero? Es un componente con tabla de líneas, total y un botón de pagar.",
            },
            {
                "role": "assistant",
                "content": r"""Pregunta primero qué protegía ese snapshot. En un `OrderSummary` suelen ser tres cosas: que cada línea aparece con su importe, que el total es correcto, y que el botón de pagar está (o no) habilitado. Escribe un test por cada una, consultando el DOM **por rol y texto**, como lo vería un usuario:

```tsx
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OrderSummary } from './OrderSummary'

const order = {
  id: 'ord_1',
  lines: [
    { sku: 'A1', name: 'Teclado', qty: 2, unitPrice: 25 },
    { sku: 'B2', name: 'Cable', qty: 1, unitPrice: 5 },
  ],
  status: 'pending' as const,
}

describe('OrderSummary', () => {
  it('muestra cada línea con su importe', () => {
    render(<OrderSummary order={order} />)
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1) // sin cabecera

    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent(/Teclado.*2.*50,00/)
    expect(rows[1]).toHaveTextContent(/Cable.*1.*5,00/)
  })

  it('calcula el total con los importes de las líneas', () => {
    render(<OrderSummary order={order} />)
    expect(screen.getByText(/^total/i).closest('tr')).toHaveTextContent('55,00')
  })

  it('deshabilita el pago cuando el pedido ya está pagado', () => {
    render(<OrderSummary order={{ ...order, status: 'paid' }} />)
    expect(screen.getByRole('button', { name: /pagar/i })).toBeDisabled()
  })
})
```

Lo que ganas frente al snapshot:

- Cada test **falla por una razón nombrada**. «Total incorrecto» en vez de «algo cambió en 380 líneas».
- Sobrevive a refactors de presentación: cambiar `<div>` por `<section>`, clases de Tailwind, orden de atributos. El snapshot moría con todos ellos.
- Documenta el comportamiento. Alguien nuevo lee los tres nombres y sabe qué hace el componente.

Si hay un trozo de *markup* que sí es el requisito (por ejemplo, el total debe ir en un `<strong>` con `aria-live` por accesibilidad), captura **solo ese trozo** inline:

```tsx
expect(screen.getByTestId('order-total').outerHTML).toMatchInlineSnapshot(
  `"<strong data-testid="order-total" aria-live="polite">55,00 €</strong>"`,
)
```

Un snapshot de una línea sí se revisa en un PR. Luego borra `OrderSummary.test.tsx.snap` y comprueba que `vitest run` lo marca como obsoleto (`obsolete snapshot file`) y no como fallo: así sabes que no queda ninguna referencia.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Our Vitest coverage is at 62% and management wants 90%. Can you explain in Spanish (my team is in Mexico) how coverage actually works and whether chasing 90% makes sense?",
            },
            {
                "role": "assistant",
                "content": r"""Perseguir un 90 % global no tiene sentido como objetivo; sí lo tiene **no bajar nunca** y exigir cobertura alta en el código que decide cosas. Primero, qué mide la herramienta, porque la mitad de las discusiones vienen de ahí.

**Qué mide la cobertura.** Vitest instrumenta el código (proveedor `v8` por defecto, `istanbul` como alternativa) y cuenta qué se **ejecutó** durante los tests:

| Métrica | Significado | Lo que no te dice |
|---|---|---|
| `lines` / `statements` | líneas ejecutadas al menos una vez | si alguien comprobó el resultado |
| `functions` | funciones invocadas | con qué argumentos |
| `branches` | ramas de `if`, `? :`, `&&`, `??`, `switch` recorridas | que la rama sea correcta |

Este test produce **100 % de cobertura** de `calcularImpuesto` y no detecta ningún bug:

```ts
it('corre', () => {
  calcularImpuesto(100, 'MX')
  calcularImpuesto(100, 'US')
})
```

Ni un `expect`. La cobertura mide ejecución, no verificación. Por eso un 90 % conseguido «para cumplir» suele estar lleno de tests así.

**Lo que sí funciona (y es defendible ante dirección):**

1. **Umbrales por zona, no globales.** El dominio (reglas de negocio, cálculos) al 90 % de ramas; la infraestructura (adaptadores, wiring) sin umbral:

```ts
// vitest.config.ts
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.d.ts', 'src/main.ts', 'src/infra/generated/**'],
      thresholds: {
        'src/domain/**': { branches: 90, functions: 90, lines: 90, statements: 90 },
        'src/app/**':    { branches: 70, lines: 75 },
      },
    },
  },
})
```

2. **Trinquete: nunca bajar.** `thresholds.autoUpdate: true` reescribe los umbrales al valor alcanzado cuando sube; a partir de ahí, cualquier PR que baje la cobertura falla en CI. En seis meses estarás muy por encima del 62 % sin haber escrito un solo test «para cobertura».

3. **Mira ramas, no líneas.** `branches` es la métrica que detecta el `else` que nadie probó. Un 85 % de líneas con 60 % de ramas significa que los casos límite no están cubiertos.

4. **Excluye lo que no tiene lógica.** Tipos, barrels (`index.ts` que reexportan), código generado. Inflan el denominador y distraen.

**Cómo leer el informe:** `vitest run --coverage` imprime una tabla; `coverage/index.html` muestra el código con las líneas rojas. Abre los archivos de `src/domain` con menos ramas cubiertas y pregúntate, rama por rama, «¿qué bug pasaría desapercibido aquí?». Esos son los tests que valen; el resto es relleno.

Lo que yo le diría a dirección: «90 % de ramas en el dominio, umbral que no baja en todo el repo, y revisamos el informe en cada PR». Es más exigente que un 90 % global y produce tests que detectan bugs.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un cliente `fetchUser` que pega a una API con `fetch` y quiero testearlo sin mockear `fetch` a mano, que es un quilombo mantener. ¿msw sirve con Vitest en Node o es solo para el navegador?",
            },
            {
                "role": "assistant",
                "content": r"""Sirve en Node, y es el enfoque correcto: msw 2 intercepta las peticiones a nivel de red (el `fetch` global y el módulo `http`), así que tu cliente corre **sin ningún cambio** y el test comprueba la petición real: URL, cabeceras, serialización del cuerpo. Un `vi.fn()` sobre `fetch` no prueba nada de eso.

**El cliente, tal como lo tenés:**

```ts
// users-client.ts
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function fetchUser(id: number, baseUrl = 'https://api.example.com') {
  const res = await fetch(`${baseUrl}/users/${id}`, { headers: { accept: 'application/json' } })
  if (res.status === 404) return null
  if (!res.ok) throw new ApiError(res.status, `GET /users/${id} → ${res.status}`)
  return (await res.json()) as { id: number; name: string }
}
```

**Instalación y servidor de mocks:**

```bash
npm i -D msw
```

```ts
// tests/msw/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('https://api.example.com/users/:id', ({ params }) => {
    if (params.id === '404') return new HttpResponse(null, { status: 404 })
    return HttpResponse.json({ id: Number(params.id), name: 'Ana' })
  }),
]
```

```ts
// tests/msw/server.ts
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

```ts
// tests/setup.ts  (en vitest.config.ts: test.setupFiles = ['./tests/setup.ts'])
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './msw/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

`onUnhandledRequest: 'error'` es importante: cualquier petición que no tenga handler hace fallar el test en vez de salir a internet en silencio.

**Los tests:**

```ts
// users-client.test.ts
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../tests/msw/server'
import { ApiError, fetchUser } from './users-client'

describe('fetchUser', () => {
  it('devuelve el usuario', async () => {
    await expect(fetchUser(7)).resolves.toEqual({ id: 7, name: 'Ana' })
  })

  it('devuelve null en 404', async () => {
    await expect(fetchUser(404)).resolves.toBeNull()
  })

  it('lanza ApiError con el status en errores del servidor', async () => {
    server.use(http.get('https://api.example.com/users/:id', () => HttpResponse.json({}, { status: 503 })))

    await expect(fetchUser(1)).rejects.toMatchObject({ status: 503 })
    await expect(fetchUser(1)).rejects.toBeInstanceOf(ApiError)
  })

  it('propaga el fallo de red', async () => {
    server.use(http.get('https://api.example.com/users/:id', () => HttpResponse.error()))

    await expect(fetchUser(1)).rejects.toThrow(TypeError)   // fetch rechaza con TypeError: Failed to fetch
  })
})
```

`server.use(...)` añade un handler **por delante** solo para ese test; el `resetHandlers()` del `afterEach` lo retira, así que no contamina a los demás.

Dos cosas que vas a agradecer después:

- Si mañana cambiás `fetch` por axios, estos tests siguen valiendo tal cual: msw también intercepta `http` de Node.
- Los mismos `handlers` sirven para Storybook o para el navegador con `setupWorker` de `msw/browser`; escribís los mocks una vez.

Verificación de que el setup está activo: comentá el `beforeAll` y corré la suite. Debe fallar el primer test con un error de red real (o de `onUnhandledRequest`), no pasar en silencio.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestra suite de Vitest tarda 9 minutos en CI (unos 1.400 tests, TypeScript, mezcla de lógica pura y componentes React). En local tarda 3. ¿Por dónde empiezo a recortar?",
            },
            {
                "role": "assistant",
                "content": r"""Empieza midiendo dónde se va el tiempo; nueve minutos para 1 400 tests es ~400 ms por test, y los tests de lógica pura deberían estar por debajo de 5 ms. Casi seguro que el coste está en el arranque de cada archivo (entorno, setup) y en unos pocos tests lentos, no repartido.

**1. Medir (10 minutos).**

```bash
npx vitest run --reporter=verbose 2>&1 | grep -E '[0-9]+ms' | sort -t' ' -k2 -rn | head -30
```

Vitest marca en amarillo los tests que superan `slowTestThreshold` (300 ms por defecto). Mira también el resumen final: `Transform`, `Setup`, `Collect`, `Tests`, `Environment`. Si `Environment` + `Setup` suman más que `Tests`, el problema es por archivo, no por test.

**2. Las causas habituales, en orden de rendimiento por esfuerzo:**

**a) jsdom para tests que no tocan el DOM.** Crear un entorno jsdom cuesta 100-300 ms por archivo. Si `environment: 'jsdom'` está en la config global, los 900 tests de lógica pura lo pagan sin usarlo. Sepáralo en proyectos:

```ts
// vitest.config.ts  (Vitest 3.2+; en versiones anteriores, `workspace`)
export default defineConfig({
  test: {
    projects: [
      {
        extends: true,
        test: { name: 'unit', environment: 'node', include: ['src/**/*.test.ts'] },
      },
      {
        extends: true,
        test: {
          name: 'dom',
          environment: 'jsdom',
          include: ['src/**/*.test.tsx'],
          setupFiles: ['./tests/setup.dom.ts'],
        },
      },
    ],
  },
})
```

Solo con esto es normal recortar un 30-40 %.

**b) `setupFiles` pesados.** Todo lo que haya ahí corre **en cada archivo**. Importar msw con 80 handlers, inicializar i18n, cargar un tema completo: muévelo al proyecto que lo necesita o hazlo perezoso.

**c) Esperas reales.** Busca `setTimeout`, `waitFor` con timeouts largos y `sleep` en tests: `grep -rn "setTimeout\|waitFor" src --include=*.test.*`. Cada uno es tiempo muerto; sustitúyelos por fake timers o por aserciones que esperan algo concreto.

**d) Paralelismo en CI.** En local tienes más núcleos que en el runner. Opciones:

- `--shard=1/4` en una matriz de 4 jobs (lineal: 9 min → ~2,5 min más el arranque de cada job).
- `pool: 'threads'` arranca más rápido que el `forks` por defecto; pruébalo, pero vuelve a `forks` si algún módulo nativo o test con `process.chdir` se queja.
- `--changed origin/main` en PRs para ejecutar solo lo afectado, dejando la suite completa en `main`.

**e) `isolate: false` para el proyecto `unit`.** Reutiliza el contexto de módulo entre archivos y ahorra el *transform* repetido. Es el mayor recorte posible, pero solo es seguro si los tests no dependen de estado a nivel de módulo (singletons, mocks sin restaurar). Actívalo únicamente en el proyecto de lógica pura.

**3. Orden recomendado:** medir → (a) proyectos → (b) setup → (c) esperas → (d) shards. Deja (e) para el final y con la suite ya estable. Después de cada paso, vuelve a medir: si un cambio no mueve el número, revértelo; no acumules configuración «por si acaso».""",
            },
            {
                "role": "user",
                "content": "Probé `isolate: false` en el proyecto unit y ahora fallan unos 20 tests de forma aleatoria, distintos cada vez.",
            },
            {
                "role": "assistant",
                "content": r"""Es el resultado esperado: `isolate: false` no ha roto los tests, ha **destapado** estado que se filtraba entre archivos. Antes, cada archivo arrancaba con módulos limpios y el estado sucio moría con él; ahora el siguiente archivo lo hereda. Que fallen distintos cada vez cuadra: depende del orden en que el worker encadene los archivos.

Estrategia: encuentra las fugas y ciérralas. No vuelvas a `isolate: true` para todo; el objetivo es dejar el proyecto `unit` sin estado compartido, que además lo hace más fiable aunque luego cambies de opinión.

**1. Reproduce el orden que falla.** Ejecuta con un orden fijo y en un solo hilo para que sea determinista:

```bash
npx vitest run --project unit --no-file-parallelism --sequence.shuffle.seed=12345
```

Cambia la semilla hasta tener una combinación que falle siempre. Con dos archivos concretos (`A` pasa solo, `B` falla si va después de `A`), ya tienes el culpable: `A` deja algo.

**2. Las cuatro fugas que explican casi siempre esos 20 tests:**

- **Mocks y espías sin restaurar.** Un `vi.spyOn(Date, 'now')` o `vi.useFakeTimers()` de `A` sigue activo en `B`. Arreglo global en la config del proyecto:

```ts
test: { name: 'unit', environment: 'node', isolate: false, restoreMocks: true, unstubGlobals: true, unstubEnvs: true }
```

  Y un `afterEach(() => vi.useRealTimers())` en el `setupFiles` de ese proyecto.

- **Singletons a nivel de módulo.** `export const cache = new Map()` o un `let config` que un test muta. Antes se reiniciaba con cada archivo. O expones un `reset()` que llamas en `beforeEach`, o el módulo recibe su estado por parámetro (mejor diseño en cualquier caso).

- **`process.env` y `process.chdir`.** `unstubEnvs: true` cubre `vi.stubEnv`; si asignas `process.env.X = ...` a mano, cámbialo por `vi.stubEnv('X', ...)`.

- **Handlers de msw añadidos con `server.use` sin `resetHandlers` en `afterEach`.** Revisa que el `afterEach` esté en el setup del proyecto, no solo en el de `dom`.

**3. Mientras los arreglas, aísla los archivos problemáticos sin perder el resto:** mueve los que fallen a un tercer proyecto `unit-isolated` con `isolate: true`, y ve devolviéndolos a `unit` a medida que cierras su fuga. Así el CI vuelve a estar verde hoy y el recorte de tiempo se mantiene para los 880 archivos que ya están limpios.

Verificación: cuando `--sequence.shuffle` con cinco semillas distintas pase en verde tres veces seguidas, puedes dar la fuga por cerrada.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 12-14: Jest (migración a Vitest, ESM, tests de contrato con Pact)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero senior de pruebas. Prioriza tests mantenibles sobre cobertura."},
            {
                "role": "user",
                "content": "Vamos a migrar unos 600 tests de Jest 29 a Vitest. ¿Cuál es el mapa de cambios y en qué orden lo harías para no parar al equipo una semana?",
            },
            {
                "role": "assistant",
                "content": r"""Hazlo en paralelo y por lotes: Vitest y Jest conviven en el mismo repo, así que el equipo sigue trabajando mientras migras carpeta a carpeta. Con 600 tests, dos o tres días de una persona es lo normal; la mayoría pasan sin tocar.

**Paso 1. Configuración (una hora).** Traduce `jest.config` a `vitest.config.ts`:

| Jest | Vitest |
|---|---|
| `testEnvironment: 'jsdom'` | `test.environment: 'jsdom'` |
| `setupFilesAfterEnv` | `test.setupFiles` |
| `moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' }` | `resolve.alias: { '@': '/src' }` (o heredado de `vite.config`) |
| `transform` (ts-jest, babel-jest) | nada: esbuild transpila TS y JSX |
| `testMatch` | `test.include` |
| `collectCoverageFrom` / `coverageThreshold` | `coverage.include` / `coverage.thresholds` |
| `testTimeout` | `test.testTimeout` |

Activa `test.globals: true` al principio: los 600 archivos siguen usando `describe`/`it`/`expect` sin importar nada, y `jest-dom` se registra con `import '@testing-library/jest-dom/vitest'`. Ya decidirás después si quieres imports explícitos.

**Paso 2. Reemplazo mecánico de la API** (`sed` o un codemod; es seguro):

| Jest | Vitest |
|---|---|
| `jest.fn()`, `jest.spyOn()` | `vi.fn()`, `vi.spyOn()` |
| `jest.mock(path, factory)` | `vi.mock(path, factory)` |
| `jest.requireActual(path)` | `await vi.importActual(path)` (asíncrono) |
| `jest.useFakeTimers()`, `jest.advanceTimersByTime()` | `vi.useFakeTimers()`, `vi.advanceTimersByTime()` |
| `jest.mocked()`, `jest.resetModules()` | `vi.mocked()`, `vi.resetModules()` |
| `import { jest } from '@jest/globals'` | `import { vi } from 'vitest'` |
| `jest.setTimeout(20_000)` | `test.setTimeout(20_000)` o `it('x', fn, 20_000)` |

**Paso 3. Lo que no es mecánico** (aquí se van los dos días; revísalo por categorías con `grep`):

1. **Fábricas de `vi.mock`.** Deben devolver el módulo completo y, si hay `export default`, incluirlo como `{ default: ... }`. Jest era permisivo; Vitest lanza un error explícito. Y la fábrica no puede usar variables del archivo: envuélvelas en `vi.hoisted`.
2. **Callbacks `done`.** No existen. Convierte a `async`/promesa: `grep -rn "done)" --include=*.test.*`.
3. **`jest.requireActual` síncrono dentro de fábricas** → `vi.mock(import('./x'), async (importOriginal) => ({ ...(await importOriginal()), fn: vi.fn() }))`.
4. **Comprobación de tipos.** `ts-jest` fallaba con errores de TS; esbuild no. Añade `tsc --noEmit` al CI o perderás esa red.
5. **Snapshots.** Desde Jest 29 el formato por defecto coincide con el de Vitest (`printBasicPrototype: false`, `escapeString: false`). Si tenéis `snapshotFormat` personalizado, replícalo en `test.snapshotFormat` o regenerad con `-u` revisando el diff.
6. **Módulos que dependían de `transformIgnorePatterns`** (deps ESM). En Vitest desaparece el problema: todo es ESM.

**Paso 4. Orden de migración.** Por carpeta, de la más pura a la más acoplada: `utils/` → `domain/` → `services/` → `components/`. Cada lote: `sed` → `vitest run <carpeta>` → arreglar → mover el `include` de Jest para excluir esa carpeta → PR. Ambos runners en CI hasta que Jest se queda sin archivos; entonces borras `jest.config`, `ts-jest`, `babel-jest` y `@types/jest`.

**Qué aprovechar para dejar la suite mejor**, ya que vas a abrir cada archivo: cualquier test que se rompa en la migración por detalles de mocks es un test acoplado a la implementación. Reescríbelo contra comportamiento en vez de traducir el mock; es el momento más barato para hacerlo.

Verificación por lote: mismo número de tests en Jest antes y en Vitest después (`--reporter=json` en ambos y compara los `numTotalTests`). Si baja, hay `describe.skip` o archivos fuera del `include`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Al correr Jest 29 con ts-jest me sale esto desde que añadí la librería `ky`:

```
/home/dev/app/node_modules/ky/distribution/index.js:1
({"Object.<anonymous>":function(module,exports,require,__dirname,__filename,jest){import {Ky} from './core/Ky.js';
                                                                                      ^^^^^^

SyntaxError: Cannot use import statement outside a module

      at Runtime.createScriptFromCode (node_modules/jest-runtime/build/index.js:1505:14)
```

Mi código es TypeScript con `import`, así que no entiendo por qué se queja solo de ky.""",
            },
            {
                "role": "assistant",
                "content": r"""Tu código no es el problema: `ts-jest` lo transpila a CommonJS antes de que Jest lo ejecute. `ky` es un paquete **solo ESM** (`"type": "module"`, sin build CJS), y Jest por defecto **no transforma nada dentro de `node_modules`** (`transformIgnorePatterns` lo excluye), así que ejecuta el `import` original en un entorno CJS y falla.

La traza lo confirma: el archivo que revienta está en `node_modules/ky/distribution/index.js`, envuelto en la función CJS de Jest (`function(module,exports,require,...)`), y la primera línea es un `import`.

Tienes tres salidas; te las ordeno de menor a mayor cambio.

**1. Transformar ese paquete (arreglo habitual).** Dile a Jest que sí transforme `ky` (y cualquier otra dep ESM que aparezca) con Babel:

```bash
npm i -D babel-jest @babel/core @babel/preset-env
```

```js
// babel.config.js  (tiene que ser babel.config.js, no .babelrc: .babelrc no se aplica a node_modules)
module.exports = {
  presets: [['@babel/preset-env', { targets: { node: 'current' } }]],
}
```

```js
// jest.config.js
module.exports = {
  testEnvironment: 'node',
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: 'tsconfig.json' }],
    '^.+\\.jsx?$': 'babel-jest',
  },
  // Excluye de la transformación todo node_modules SALVO los paquetes listados
  transformIgnorePatterns: ['/node_modules/(?!(ky)/)'],
}
```

Cada vez que otra dependencia falle con el mismo error, la añades al grupo: `(?!(ky|p-retry|nanoid)/)`. Con pnpm la ruta real es `node_modules/.pnpm/ky@1.x/node_modules/ky`, así que el patrón pasa a ser `'/node_modules/(?!\\.pnpm|ky)'` y `'/node_modules/\\.pnpm/(?!ky@)'` (dos entradas).

Coste: cada test transpila `ky` al vuelo (la caché de Jest lo amortigua).

**2. Mockear la dependencia** si en esos tests no te interesa la red:

```js
moduleNameMapper: { '^ky$': '<rootDir>/tests/mocks/ky.ts' }
```

Solo vale si **ningún** test necesita el `ky` real; si no, mezcla la opción 1 con `jest.mock` puntual.

**3. ESM nativo en Jest.** Funciona, pero sigue siendo experimental y cambia cómo se mockea:

```json
{
  "scripts": { "test": "NODE_OPTIONS=--experimental-vm-modules jest" }
}
```

con `extensionsToTreatAsEsm: ['.ts']`, `ts-jest` con `useESM: true` y `"module": "ESNext"` en el tsconfig. A cambio, `jest.mock()` deja de funcionar con módulos ESM: hay que usar `jest.unstable_mockModule()` seguido de `await import()`. Para 600 tests con mocks, no te lo recomiendo.

**Mi recomendación:** opción 1 hoy (diez minutos). Si en los próximos meses el patrón de `transformIgnorePatterns` crece a cinco o seis paquetes, es la señal de que el ecosistema que usas ya es ESM y de que te compensa mover la suite a Vitest, donde este problema no existe.

Verificación: `npx jest --clearCache && npx jest tests/users.test.ts`. Debe pasar; si el error reaparece citando otro paquete, añádelo al patrón.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Our React frontend tests mock the users API with hand-written JSON fixtures, and the backend team keeps changing response shapes without us noticing until production. Both sides use Jest. How would contract tests fix this, concretely?",
            },
            {
                "role": "assistant",
                "content": r"""Contract tests replace your hand-written fixtures with a **contract the provider must verify**. The consumer (your frontend) records what it expects; the provider (the backend) runs those expectations against its real code in its own CI. A shape change then fails the backend build, not production.

The standard tool is Pact (`@pact-foundation/pact`, v13+). It works with Jest on both sides.

**Consumer side (frontend).** The test runs your real HTTP client against a Pact mock server. Matchers describe the *shape*, not exact values, so the contract survives data changes:

```ts
// users-client.pact.test.ts
import path from 'node:path'
import { MatchersV3, PactV3 } from '@pact-foundation/pact'
import { UsersClient } from './users-client'

const { like, integer, string } = MatchersV3

const provider = new PactV3({
  consumer: 'web-app',
  provider: 'users-api',
  dir: path.resolve(process.cwd(), 'pacts'),
})

it('fetches a user by id', async () => {
  provider
    .given('user 42 exists')
    .uponReceiving('a request for user 42')
    .withRequest({ method: 'GET', path: '/users/42', headers: { Accept: 'application/json' } })
    .willRespondWith({
      status: 200,
      headers: { 'Content-Type': 'application/json' },
      body: like({ id: integer(42), name: string('Ana'), email: string('ana@example.com') }),
    })

  await provider.executeTest(async (mockServer) => {
    const client = new UsersClient(mockServer.url)
    const user = await client.getUser(42)
    expect(user).toEqual({ id: 42, name: 'Ana', email: 'ana@example.com' })
  })
})
```

Running this writes `pacts/web-app-users-api.json`. That file *is* the contract: every field your client reads, with its type.

**Provider side (backend).** A single test starts the real API and replays the contract. `stateHandlers` seed the data each interaction needs:

```ts
// users-api.pact.test.ts
import path from 'node:path'
import { Verifier } from '@pact-foundation/pact'
import { startServer, seedUser } from './test-support'

it('honours the web-app contract', async () => {
  const server = await startServer(0)
  try {
    await new Verifier({
      provider: 'users-api',
      providerBaseUrl: `http://localhost:${server.port}`,
      pactUrls: [path.resolve(process.cwd(), '../web-app/pacts/web-app-users-api.json')],
      stateHandlers: {
        'user 42 exists': async () => { await seedUser({ id: 42, name: 'Ana', email: 'ana@example.com' }) },
      },
    }).verifyProvider()
  } finally {
    await server.close()
  }
}, 30_000)
```

If the backend renames `email` to `emailAddress`, this test fails with `Expected "email" but was missing`, in the backend's PR, before merge.

**Sharing the contract.** The `pactUrls` path above assumes a monorepo. Across repos, publish the JSON to a Pact Broker (self-hosted or PactFlow) and let the provider pull it by tag; the broker also gives you `can-i-deploy`, which blocks a deploy when the two sides disagree.

**What this does not replace:**

- Your existing component tests should keep using msw or fixtures for speed; they test the UI, not the API. The Pact test covers only the client module, so the fixtures you keep are the ones Pact proved correct.
- Contracts cover fields the consumer *uses*. If the backend adds a field, nothing fails, which is the point: additive changes are free.

**A lighter alternative** if the backend already publishes an OpenAPI spec: validate your fixtures against the spec in CI (`openapi-response-validator` or generate types with `openapi-typescript` and let `tsc` catch shape drift). It is weaker (nobody verifies the spec matches the server) but takes an afternoon instead of a week.

Check it works end to end: change the consumer test to expect a field that does not exist (`phone: string('x')`), regenerate the pact, run the provider verification. It must fail. If it passes, the provider is reading a stale pact file.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 15-18: Testing Library (roles, userEvent y formularios, act(), renderHook)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo le hago para no usar `data-testid` en todo? Mi lead dice que use `getByRole` pero no sé qué rol tiene cada cosa ni cómo checar el nombre que espera.",
            },
            {
                "role": "assistant",
                "content": r"""El rol lo da el HTML, no tú: cada elemento semántico tiene un rol implícito, y el «nombre accesible» sale de su etiqueta o texto. Si consultas por rol y nombre, el test se parece a lo que ve el usuario (y además te avisa cuando el formulario no es accesible). `data-testid` queda para lo que no tiene semántica (un `<div>` decorativo que necesitas localizar), que debería ser raro.

**Roles implícitos que cubren el 95 % de los casos:**

| HTML | Rol | Nombre accesible |
|---|---|---|
| `<button>`, `<input type="submit">` | `button` | su texto o `value` |
| `<a href>` | `link` | su texto |
| `<input type="text\|email\|password">`, `<textarea>` | `textbox` | el `<label>` asociado |
| `<input type="checkbox">` / `radio` | `checkbox` / `radio` | su `<label>` |
| `<select>` | `combobox` | su `<label>` |
| `<h1>`-`<h6>` | `heading` | su texto (filtra con `level`) |
| `<table>`, `<tr>`, `<td>` | `table`, `row`, `cell` | `<caption>` |
| `<ul>`/`<li>` | `list` / `listitem` | |
| `<dialog open>` o `role="dialog"` | `dialog` | `aria-labelledby` |
| `<img alt="x">` | `img` | el `alt` |
| `<nav>`, `<main>`, `<form aria-label>` | `navigation`, `main`, `form` | `aria-label` |

Para un formulario de login:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

it('envía las credenciales', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<LoginForm onSubmit={onSubmit} />)

  await user.type(screen.getByRole('textbox', { name: /correo/i }), 'ana@example.com')
  await user.type(screen.getByLabelText(/contraseña/i), 'secreto')   // password no tiene rol: usa el label
  await user.click(screen.getByRole('button', { name: /entrar/i }))

  expect(onSubmit).toHaveBeenCalledWith({ email: 'ana@example.com', password: 'secreto' })
})
```

Detalle que sorprende: `<input type="password">` **no** tiene rol `textbox` (por seguridad), así que se busca con `getByLabelText`. Es la segunda opción en la prioridad oficial: `getByRole` → `getByLabelText` → `getByPlaceholderText` → `getByText` → `getByTestId`.

**Cómo checar qué rol y nombre tiene algo** sin adivinar:

```ts
screen.logTestingPlaygroundURL()   // imprime una URL con tu DOM y las queries sugeridas
```

o `logRoles(container)` de `@testing-library/dom`, que lista todos los roles presentes con sus nombres. Y cuando una query falla, el propio error te lista los elementos de ese rol que sí encontró:

```
TestingLibraryElementError: Unable to find an accessible element with the role "textbox" and name `/correo/i`

Here are the accessible roles:
  textbox:
  Name "":
  <input type="email" id="email" />
```

Ese `Name ""` es el diagnóstico: el `<label>` no está asociado (falta `htmlFor="email"` o envolver el input en el label). Arreglar el componente arregla el test **y** el lector de pantalla; por eso tu lead insiste.

**Cuándo sí usar `data-testid`:** contenedores sin semántica que necesitas para `within()` (una tarjeta concreta en una lista) o elementos de terceros que no controlas. Si te ves poniéndolo en botones o inputs, el HTML está mal y el test te lo está diciendo.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy probando un formulario de registro con Testing Library. Uso `fireEvent.change` para escribir y el `onSubmit` no recibe el valor; además la validación de email (que se dispara al salir del campo) nunca aparece. ¿Qué hago mal?",
            },
            {
                "role": "assistant",
                "content": r"""`fireEvent.change` dispara **un solo evento sintético**; un usuario real genera `focus`, `keydown`, `input`, `change` y, al salir del campo, `blur`. Tu validación escucha `blur` (o `onBlur` de react-hook-form) y nunca llega; y si el estado del formulario se actualiza en `onInput` o por teclas, el valor tampoco. Usa `@testing-library/user-event`, que simula la interacción completa.

```bash
npm i -D @testing-library/user-event
```

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { SignupForm } from './SignupForm'

it('muestra el error de email al salir del campo con un valor inválido', async () => {
  const user = userEvent.setup()
  render(<SignupForm onSubmit={vi.fn()} />)

  await user.type(screen.getByRole('textbox', { name: /correo/i }), 'ana@')
  await user.tab()   // blur: salir del campo como lo haría el usuario

  expect(await screen.findByText(/correo no válido/i)).toBeInTheDocument()
})

it('envía los datos cuando el formulario es válido', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<SignupForm onSubmit={onSubmit} />)

  await user.type(screen.getByRole('textbox', { name: /correo/i }), 'ana@example.com')
  await user.type(screen.getByLabelText(/contraseña/i), 'secreto123')
  await user.click(screen.getByRole('button', { name: /crear cuenta/i }))

  expect(onSubmit).toHaveBeenCalledWith({ email: 'ana@example.com', password: 'secreto123' })
})
```

Tres puntos que explican tus dos síntomas:

1. **`userEvent.setup()` una vez por test** y todas sus llamadas con `await`: desde la v14 son asíncronas porque avanzan el reloj entre teclas. Sin `await`, la aserción corre antes de que se escriba nada: ese es tu `onSubmit` sin valor.
2. **`user.tab()`** produce el `blur` que dispara la validación. Con `fireEvent` tendrías que simular `fireEvent.blur` a mano y seguirías sin `focus`, `keydown`, etc.
3. **`findByText`** espera hasta que el error aparece (por defecto 1 s). La validación suele ser asíncrona (react-hook-form, zod), así que `getByText` justo después del `tab` falla a veces y pasa otras.

Si el formulario está con react-hook-form, comprueba además que el `mode` incluye `onBlur` (`useForm({ mode: 'onTouched' })` o `'onBlur'`); con el `mode: 'onSubmit'` por defecto la validación solo corre al enviar, y entonces el test que espera el error tras el `tab` está probando algo que el componente no hace.""",
            },
            {
                "role": "user",
                "content": "Perfecto, ya pasan. Ahora quiero probar que al enviar llama a `POST /api/signup` y muestra «Cuenta creada», y que el botón se deshabilita mientras tanto.",
            },
            {
                "role": "assistant",
                "content": r"""Intercepta la petición con msw y afirma sobre lo que ve el usuario: botón deshabilitado durante la espera y el mensaje al terminar. No espíes `fetch` ni compruebes argumentos; lo que importa es el estado de la pantalla y que la petición real salió con el cuerpo correcto, y eso lo captura el handler.

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { SignupForm } from './SignupForm'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole('textbox', { name: /correo/i }), 'ana@example.com')
  await user.type(screen.getByLabelText(/contraseña/i), 'secreto123')
  await user.click(screen.getByRole('button', { name: /crear cuenta/i }))
}

it('envía el registro y confirma la creación', async () => {
  let received: unknown
  server.use(
    http.post('/api/signup', async ({ request }) => {
      received = await request.json()
      await delay(50)                                 // da tiempo a observar el estado "enviando"
      return HttpResponse.json({ id: 1 }, { status: 201 })
    }),
  )
  const user = userEvent.setup()
  render(<SignupForm />)

  await fillAndSubmit(user)

  expect(screen.getByRole('button', { name: /creando/i })).toBeDisabled()
  expect(await screen.findByRole('status')).toHaveTextContent(/cuenta creada/i)
  expect(received).toEqual({ email: 'ana@example.com', password: 'secreto123' })
  expect(screen.getByRole('button', { name: /crear cuenta/i })).toBeEnabled()
})

it('muestra el error del servidor y permite reintentar', async () => {
  server.use(http.post('/api/signup', () => HttpResponse.json({ message: 'Correo ya registrado' }, { status: 409 })))
  const user = userEvent.setup()
  render(<SignupForm />)

  await fillAndSubmit(user)

  expect(await screen.findByRole('alert')).toHaveTextContent(/ya registrado/i)
  expect(screen.getByRole('button', { name: /crear cuenta/i })).toBeEnabled()
})
```

Decisiones:

- **`delay(50)`** en el handler: sin él, la respuesta llega antes de que React pinte el estado «creando» y la aserción de `toBeDisabled` sería intermitente. 50 ms es suficiente y no ralentiza la suite.
- **`role="status"`** para el mensaje de éxito y **`role="alert"`** para el error. Son los roles que un lector de pantalla anuncia; si el componente no los tiene, añádelos (`<p role="status">`): mejora la accesibilidad y te da una query estable.
- **Capturo el cuerpo en el handler** (`received`) y lo afirmo al final. Es la única aserción sobre la petición, y comprueba lo que de verdad viaja por la red, serialización incluida.
- Ruta relativa `/api/signup`: en jsdom, msw la resuelve contra `location.origin` (`http://localhost:3000` por defecto). Si tu cliente usa una URL absoluta, pon la misma en el handler.

Para que el segundo test funcione, el componente debe habilitar el botón al recibir el error; si ahora no lo hace, el test lo señala y es un bug real de UX.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Este test pasa pero me llena la consola de warnings y a veces rompe el test siguiente:

```tsx
it('muestra el estado de carga', () => {
  render(<UserList />)
  expect(screen.getByText('Cargando')).toBeInTheDocument()
})
```

```
Warning: An update to UserList inside a test was not wrapped in act(...).
When testing, code that causes React state updates should be wrapped into act(...)
```

`UserList` hace `fetch('/api/users')` en un `useEffect` y guarda el resultado con `setUsers`. React 19, Vitest, jsdom.""",
            },
            {
                "role": "assistant",
                "content": r"""El test termina mientras el `fetch` sigue en vuelo. Cuando la promesa resuelve, `setUsers` actualiza el estado de un componente cuyo test ya acabó: React avisa con el `act(...)` y, peor, ese render tardío ocurre durante el **siguiente** test, que es lo que te lo rompe a veces.

No envuelvas nada en `act` a mano: Testing Library ya lo hace en `render`, `userEvent` y las queries `findBy*`/`waitFor`. Lo que falta es **esperar a que el componente llegue a un estado estable** antes de salir del test.

**Arreglo:** controla la respuesta con msw y espera el estado final.

```tsx
import { render, screen, waitForElementToBeRemoved } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { UserList } from './UserList'

const server = setupServer(
  http.get('/api/users', () => HttpResponse.json([{ id: 1, name: 'Ana' }, { id: 2, name: 'Luis' }])),
)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('muestra "Cargando" y luego la lista de usuarios', async () => {
  render(<UserList />)

  expect(screen.getByText('Cargando')).toBeInTheDocument()
  await waitForElementToBeRemoved(() => screen.queryByText('Cargando'))

  expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Ana', 'Luis'])
})
```

Por qué desaparece el warning: `waitForElementToBeRemoved` espera (envuelto en `act`) hasta que el estado de carga se va, es decir, hasta que `setUsers` ya se ejecutó. Cuando el test termina no queda ninguna actualización pendiente.

**Si solo quieres probar el estado de carga**, aun así tienes que dejar el componente en reposo. Dos formas:

```tsx
it('muestra "Cargando" mientras espera', async () => {
  render(<UserList />)
  expect(screen.getByText('Cargando')).toBeInTheDocument()
  await screen.findAllByRole('listitem')   // consume la respuesta antes de salir
})
```

o, si la petición nunca debe resolver en ese test, hazla colgar explícitamente con un handler que devuelva `new Promise(() => {})` y desmonta al final (`unmount()`), de modo que el `setUsers` tardío no encuentre componente (en tu `useEffect` conviene además cancelar con `AbortController` en el cleanup, que es lo correcto también en producción).

**Lo que no debes hacer:** `vi.spyOn(console, 'error')` para silenciar el warning, o `await act(async () => {})` al final «para que calle». Ambos ocultan el problema real: un test que deja trabajo asíncrono vivo.

Verificación: ejecuta el archivo con `vitest run --reporter=verbose` y la consola debe quedar sin `Warning:`. Luego ejecuta la suite completa dos veces con `--sequence.shuffle`; si el test «siguiente» ya no falla, confirmas que la causa era este render tardío.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "How do I unit test a custom hook like `useDebouncedValue(value, delay)` with Testing Library and Vitest? Do I really need to render a dummy component?",
            },
            {
                "role": "assistant",
                "content": r"""No dummy component: `renderHook` from `@testing-library/react` does that for you and gives you `result.current` plus a `rerender` to change the inputs. Combine it with Vitest fake timers so the test runs in milliseconds and the delay is exact.

The hook under test:

```ts
// useDebouncedValue.ts
import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])

  return debounced
}
```

The test:

```ts
// useDebouncedValue.test.ts
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useDebouncedValue } from './useDebouncedValue'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

it('returns the initial value immediately', () => {
  const { result } = renderHook(() => useDebouncedValue('a', 300))
  expect(result.current).toBe('a')
})

it('updates only after the delay has elapsed without new changes', () => {
  const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
    initialProps: { value: 'a' },
  })

  rerender({ value: 'ab' })
  act(() => { vi.advanceTimersByTime(299) })
  expect(result.current).toBe('a')          // still the old value

  act(() => { vi.advanceTimersByTime(1) })
  expect(result.current).toBe('ab')
})

it('restarts the timer on every change', () => {
  const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
    initialProps: { value: 'a' },
  })

  rerender({ value: 'ab' })
  act(() => { vi.advanceTimersByTime(200) })
  rerender({ value: 'abc' })
  act(() => { vi.advanceTimersByTime(200) })
  expect(result.current).toBe('a')          // 400 ms total, but never 300 ms of silence

  act(() => { vi.advanceTimersByTime(100) })
  expect(result.current).toBe('abc')        // intermediate 'ab' was skipped
})
```

Why each piece is there:

- **`initialProps` + `rerender(newProps)`** is how you simulate the parent passing a new value. Calling the hook function with a different argument inside the callback would not re-render anything.
- **`act(() => vi.advanceTimersByTime(...))`**: the timer callback calls `setDebounced`, which is a state update. `act` flushes it so `result.current` reflects the new render. Without it you get the "not wrapped in act" warning and a stale `result.current`.
- **299 then 1** pins the boundary. A regression that changes `setTimeout` to fire early or late fails here, not in production.
- The third test asserts the *skip*: the intermediate `'ab'` never becomes the debounced value. That is the actual contract of a debounce, and the one most reimplementations get wrong.

If the hook needs context (a router, a query client, a theme), pass a `wrapper`:

```ts
renderHook(() => useCurrentUser(), {
  wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
})
```

When to test through a component instead: when the hook's only consumer is one component and the interesting behaviour is what the user sees. Then a `render` + `userEvent` test of that component covers the hook better and survives the day you inline it. `renderHook` is for hooks that are reused across components or have logic worth pinning on their own, like this one.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 19-25: pytest (fixtures/conftest, parametrize, monkeypatch/tmp_path, marcadores,
#        pytest-asyncio + respx, Hypothesis, Testcontainers)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "En pytest estoy creando el engine de SQLAlchemy y las tablas dentro de cada test y la suite tarda una barbaridad. He visto que existen fixtures con `scope`, pero no tengo claro dónde ponerlas ni cómo evitar que un test ensucie al siguiente.",
            },
            {
                "role": "assistant",
                "content": r"""Separa lo caro de lo que debe aislarse: el **engine y el esquema** se crean una vez por sesión; la **sesión de BD** se crea por test dentro de una transacción que se revierte al final. Así cada test empieza con tablas limpias sin pagar el `create_all`.

```python
# tests/conftest.py
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Base


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    '''Un engine y un esquema para toda la sesión de tests (caro: se hace una vez).'''
    engine = create_engine("postgresql+psycopg://test:test@localhost:5433/test")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    '''Una sesión por test, dentro de una transacción externa que siempre se revierte.'''
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
```

Y un test cualquiera recibe `db` por nombre:

```python
# tests/test_user_repo.py
from app.repos import UserRepo


def test_guarda_y_recupera_por_email(db):
    repo = UserRepo(db)
    repo.add(email="ana@example.com", name="Ana")
    db.commit()   # commit sobre el savepoint: no toca la transacción externa

    assert repo.by_email("ana@example.com").name == "Ana"
```

**Por qué funciona el aislamiento:** `join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0) hace que cada `session.commit()` del código bajo prueba libere un *savepoint* en vez de confirmar de verdad. Al terminar el test, `transaction.rollback()` deshace todo, incluidos los commits. El siguiente test ve las tablas vacías.

**Dónde va cada cosa:**

- `tests/conftest.py`: fixtures que usan varios módulos de tests (estas dos). pytest lo carga sin importarlo.
- `tests/api/conftest.py`: fixtures solo para esa carpeta (un `client` de FastAPI, por ejemplo). Puede usar las del `conftest.py` superior.
- Dentro del archivo de test: fixtures que solo usa ese archivo.

**Scopes, de caro a barato:** `session` → `package` → `module` → `class` → `function` (por defecto). Regla: scope alto para recursos **inmutables o reiniciables** (engine, cliente HTTP, contenedor Docker); scope `function` para todo lo que **acumula estado** (sesión, directorio temporal, mocks). Una fixture de scope alto no puede depender de una de scope más bajo; pytest lo rechaza con `ScopeMismatch`.

**Dos detalles útiles:**

- `yield` en la fixture es el *teardown*: lo que va después se ejecuta aunque el test falle. Con `return` no hay limpieza.
- `autouse=True` aplica la fixture a todos los tests de su alcance sin nombrarla. Úsalo solo para cosas realmente transversales (fijar la zona horaria, silenciar logs); si lo usas para `db`, los tests que no tocan la BD pagan la conexión igual.

Verificación de que el aislamiento es real: escribe dos tests seguidos, uno que inserte un usuario y otro que afirme `db.query(User).count() == 0`. Ejecútalos con `pytest -p no:randomly tests/test_user_repo.py` en ese orden; el segundo debe pasar.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "¿Cómo parametrizo tests en pytest con nombres que se entiendan? Tengo 12 casos de un parser de montos (`'1.234,56'`, `'$ 10'`, `'-3,5'`, etc.) y cuando uno falla el reporte me dice `test_parse[7]` y no sé cuál es.",
            },
            {
                "role": "assistant",
                "content": r"""Usá `ids` o, mejor, `pytest.param(..., id="...")` en cada caso: el reporte pasa de `test_parse[7]` a `test_parse[miles-con-punto]` y de un vistazo sabés qué se rompió.

```python
# tests/test_money.py
from decimal import Decimal

import pytest

from app.money import ParseError, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("10", Decimal("10"), id="entero"),
        pytest.param("10,50", Decimal("10.50"), id="coma-decimal"),
        pytest.param("1.234,56", Decimal("1234.56"), id="miles-con-punto"),
        pytest.param("$ 10", Decimal("10"), id="simbolo-con-espacio"),
        pytest.param("$10", Decimal("10"), id="simbolo-pegado"),
        pytest.param("-3,5", Decimal("-3.5"), id="negativo"),
        pytest.param("  7  ", Decimal("7"), id="espacios-alrededor"),
        pytest.param("1.000.000", Decimal("1000000"), id="millon-sin-decimales"),
        pytest.param("0,00", Decimal("0"), id="cero"),
        pytest.param(
            "1,234.56",
            Decimal("1234.56"),
            id="formato-ingles",
            marks=pytest.mark.xfail(reason="formato en-US no soportado todavía", strict=True),
        ),
    ],
)
def test_parse_amount(raw: str, expected: Decimal) -> None:
    assert parse_amount(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [pytest.param("", id="vacio"), pytest.param("abc", id="letras"), pytest.param("1,2,3", id="dos-comas")],
)
def test_parse_amount_rechaza_entradas_invalidas(raw: str) -> None:
    with pytest.raises(ParseError):
        parse_amount(raw)
```

Fijate en tres decisiones:

1. **Separé los casos válidos de los inválidos** en dos tests. Si mezclás `expected` con «debe lanzar» en una misma lista, el cuerpo del test se llena de `if` y el nombre deja de decir qué se prueba.
2. **`xfail` con `strict=True`** para el caso que todavía no soportás: documenta el límite conocido y, el día que lo implementes, el test **falla** por pasar inesperadamente (`XPASS(strict)`), recordándote que saques la marca.
3. **Ids en kebab-case sin espacios** para poder seleccionarlos desde la terminal:

```bash
pytest -k "miles-con-punto"          # un caso
pytest -k "test_parse_amount and not negativo"
```

Cuando falla uno, el reporte queda así:

```
FAILED tests/test_money.py::test_parse_amount[miles-con-punto] - AssertionError: assert Decimal('1.234') == Decimal('1234.56')
```

Dos variantes que te van a servir pronto:

- **Apilar `parametrize`** genera el producto cartesiano: `@parametrize("locale", ["es_AR", "es_ES"])` encima del anterior corre los 10 casos por cada locale (20 tests, ids `[es_AR-entero]`, etc.).
- **`ids=` como función** cuando los parámetros son objetos: `ids=lambda c: c.description` evita escribir el id a mano en cada `param`.

Comprobá que los ids quedaron bien sin ejecutar nada: `pytest --collect-only -q tests/test_money.py` lista los 13 nombres. Si ves `[raw0]` o `[7]`, a ese caso le falta el id.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo una función `save_cache(key, data)` que lee la variable de entorno `CONFIG_DIR` y escribe un JSON ahí. ¿Cómo la testeo sin tocar mi home ni el entorno real?",
            },
            {
                "role": "assistant",
                "content": r"""Con dos fixtures que pytest trae de serie: `tmp_path` te da un directorio vacío y único por test, y `monkeypatch` cambia el entorno solo durante el test y lo restaura al salir (incluso si falla).

Asumo esta implementación:

```python
# app/cache.py
import json
import os
from pathlib import Path


def cache_dir() -> Path:
    return Path(os.environ.get("CONFIG_DIR", Path.home() / ".myapp"))


def save_cache(key: str, data: dict) -> Path:
    target = cache_dir() / f"{key}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target
```

Los tests:

```python
# tests/test_cache.py
import json
from pathlib import Path

import pytest

from app.cache import cache_dir, save_cache


def test_escribe_el_json_en_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))

    written = save_cache("users", {"ana": 1})

    assert written == tmp_path / "users.json"
    assert json.loads(written.read_text(encoding="utf-8")) == {"ana": 1}


def test_crea_el_directorio_si_no_existe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "nested" / "dir"))

    save_cache("k", {})

    assert (tmp_path / "nested" / "dir" / "k.json").exists()


def test_sin_variable_usa_el_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFIG_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)   # tampoco toca el home real

    assert cache_dir() == tmp_path / ".myapp"
```

Por qué cada pieza:

- **`tmp_path`** vive en el directorio temporal del sistema (`/tmp/pytest-of-<usuario>/pytest-N/test_nombre0`); pytest conserva las tres últimas ejecuciones para que puedas inspeccionar un fallo y borra las anteriores.
- **`monkeypatch.setenv`** modifica `os.environ` y lo deshace al terminar el test. Nunca asignes `os.environ["X"] = ...` directamente: contamina el resto de la suite.
- **`delenv(..., raising=False)`** no falla si la variable no existía; sin eso el tercer test depende de tu máquina.
- **`monkeypatch.setattr(Path, "home", ...)`** sustituye el método de clase solo durante el test. Es la forma de aislar el *default* sin reestructurar el código.

Comprobación del aislamiento: después de correr `pytest tests/test_cache.py`, `echo $CONFIG_DIR` en tu terminal sigue vacío y en tu home no hay ningún `.myapp` nuevo.""",
            },
            {
                "role": "user",
                "content": "El problema es que mi módulo real hace `CONFIG_DIR = Path(os.environ[\"CONFIG_DIR\"])` a nivel de módulo, al importar. `setenv` no le afecta porque ya está cargado.",
            },
            {
                "role": "assistant",
                "content": r"""Exacto: el valor se fijó en el momento del `import`, antes de que corra ninguna fixture, así que cambiar el entorno después no cambia la constante. Tienes dos niveles de arreglo; el segundo es el bueno.

**Parche inmediato (sin tocar el módulo):** sustituye la constante, no la variable de entorno.

```python
import app.cache as cache


def test_escribe_el_json_en_config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CONFIG_DIR", tmp_path)

    written = cache.save_cache("users", {"ana": 1})

    assert written == tmp_path / "users.json"
```

Funciona porque `save_cache` lee `CONFIG_DIR` del espacio de nombres del módulo en cada llamada. Importa el módulo (`import app.cache as cache`), no el nombre (`from app.cache import CONFIG_DIR`): el `from` crea una copia local que `setattr` no toca.

Lo que **no** hagas: `importlib.reload(cache)` dentro del test. Reimporta el módulo con el entorno parcheado, sí, pero deja referencias viejas en cualquier otro módulo que lo hubiera importado, y además ejecuta de nuevo todos sus efectos de importación. Es la fuente clásica de tests que pasan solos y fallan en suite.

**Arreglo de raíz:** leer la configuración en tiempo de importación es un defecto de diseño, no solo un estorbo para los tests. Impide cambiarla por proceso, rompe si la variable no existe al importar (`KeyError` al arrancar herramientas que ni usan la caché) y oculta la dependencia. Haz la lectura perezosa o inyectable:

```python
# app/cache.py
import json
import os
from pathlib import Path


def cache_dir() -> Path:
    try:
        return Path(os.environ["CONFIG_DIR"])
    except KeyError as exc:
        raise RuntimeError("CONFIG_DIR no está definida; exporta la ruta del directorio de configuración") from exc


def save_cache(key: str, data: dict, base: Path | None = None) -> Path:
    target = (base or cache_dir()) / f"{key}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target
```

Ahora el test ni siquiera necesita `monkeypatch`: `save_cache("users", data, base=tmp_path)`. Y `setenv` también funciona para los tests que quieran cubrir la lectura del entorno. El mensaje de error accionable es un regalo extra: antes el `KeyError` pelado salía en cualquier `import app`.

Si hay varios sitios que leen `CONFIG_DIR` al importar, haz el cambio módulo a módulo, con el parche de `setattr` como puente para los que aún no hayas tocado. Verificación: `grep -rn "os.environ\[" app/ | grep -v "def "` debería devolver cero líneas a nivel de módulo cuando termines.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos tests lentos que pegan a servicios reales (Stripe en sandbox, un bucket S3) mezclados con los de unidad. Queremos que el pre-commit corra solo los rápidos y que CI corra todos. ¿Cómo los marcamos sin que a alguien se le olvide?",
            },
            {
                "role": "assistant",
                "content": r"""Marcadores registrados con `--strict-markers` para que un marcador mal escrito falle, y **asignación automática por carpeta** en `conftest.py` para que nadie tenga que acordarse de decorar.

**1. Registro en `pyproject.toml`:**

```toml
[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
markers = [
    "slow: tests que tardan más de un segundo",
    "external: tests que llaman a servicios reales (Stripe sandbox, S3); requieren credenciales",
]
testpaths = ["tests"]
```

`--strict-markers` convierte `@pytest.mark.slwo` (errata) en un error de colección en vez de un marcador fantasma que nunca se filtra. `-ra` muestra al final el resumen de *skipped*/*xfailed* con su motivo, para que lo que se salta no desaparezca en silencio.

**2. Marcado automático por ubicación.** Pon los tests externos en `tests/external/` y deja que el `conftest.py` raíz los marque:

```python
# tests/conftest.py
import os
from pathlib import Path

import pytest

EXTERNAL_DIR = Path(__file__).parent / "external"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if EXTERNAL_DIR in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.external)
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def stripe_key() -> str:
    key = os.environ.get("STRIPE_TEST_KEY")
    if not key:
        pytest.skip("STRIPE_TEST_KEY no definida: se omiten los tests contra Stripe")
    return key
```

La fixture `stripe_key` hace el segundo trabajo: si alguien corre `pytest` sin credenciales, los tests externos se saltan con un motivo visible (gracias a `-ra`) en vez de fallar con un 401 confuso.

**3. Dos comandos, dos contextos:**

```bash
# pre-commit / local: solo rápidos
pytest -m "not slow"

# CI: todo, y los externos con sus secretos
STRIPE_TEST_KEY=... pytest
```

En `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: pytest-fast
      name: pytest (rápidos)
      entry: pytest -m "not slow" -q -x
      language: system
      pass_filenames: false
```

**4. Para marcar casos sueltos** fuera de esa carpeta, el decorador sigue disponible y, con `--strict-markers`, está validado:

```python
@pytest.mark.slow
def test_indexado_completo_de_100k_documentos(): ...
```

Y `skipif` para condiciones de plataforma, no de credenciales: `@pytest.mark.skipif(sys.platform == "win32", reason="usa permisos POSIX")`.

Verificación de que el filtro no deja nada fuera: `pytest -m "not slow" --collect-only -q | grep external/` debe devolver cero líneas. Si aparece alguna, ese archivo está fuera de `tests/external/` y sin marcar; muévelo o decóralo.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Actualicé pytest-asyncio a 1.x y se me cayó media suite. Esta fixture ya no funciona:

```python
@pytest.fixture
def client(event_loop):
    return event_loop.run_until_complete(make_client())
```

```
E       fixture 'event_loop' not found
>       available fixtures: cache, capfd, capsys, doctest_namespace, monkeypatch, ...
```

`make_client()` construye un `httpx.AsyncClient` contra nuestra API de pagos. Además quiero dejar de pegarle a la API real en los tests; ¿qué uso para mockear httpx?""",
            },
            {
                "role": "assistant",
                "content": r"""Son dos cambios independientes: la fixture `event_loop` desapareció en pytest-asyncio 1.0 (estaba deprecada desde 0.23), y para httpx el mock estándar es `respx`.

**1. Fixtures asíncronas, sin `event_loop`.** La forma correcta es declarar la fixture como `async def` y dejar que el plugin la ejecute en su bucle:

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"                        # todo test/fixture async corre en asyncio sin decorar
asyncio_default_fixture_loop_scope = "function"
```

```python
# tests/conftest.py
from collections.abc import AsyncIterator

import httpx
import pytest

from app.payments import PaymentsClient


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url="https://pagos.example.com") as client:
        yield client


@pytest.fixture
def payments(http: httpx.AsyncClient) -> PaymentsClient:
    return PaymentsClient(http)
```

Con `asyncio_mode = "auto"`, `@pytest.fixture` sobre un `async def` basta. Si prefieres modo `strict` (el default), decora con `@pytest_asyncio.fixture` y marca cada test con `@pytest.mark.asyncio`.

Si alguna fixture debe compartir bucle entre tests (una conexión de sesión), indícalo con `loop_scope`:

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def pool(): ...
```

Un recurso de scope `session` creado en el bucle de un test de scope `function` falla al segundo test con «attached to a different loop»; `loop_scope` existe justo para eso.

**2. Mockear httpx con respx.** Intercepta en el transporte de httpx, así que tu `AsyncClient` real sigue haciendo todo (URL, cabeceras, JSON) salvo salir a la red:

```bash
pip install respx
```

```python
# tests/test_payments.py
import httpx
import pytest
import respx

from app.payments import PaymentDeclined, PaymentsClient


async def test_crea_un_cobro(payments: PaymentsClient, respx_mock: respx.MockRouter) -> None:
    route = respx_mock.post("https://pagos.example.com/charges").mock(
        return_value=httpx.Response(201, json={"id": "ch_1", "status": "succeeded"})
    )

    charge = await payments.charge(amount_cents=1250, currency="EUR")

    assert charge.id == "ch_1"
    assert route.called
    assert route.calls.last.request.headers["Idempotency-Key"]   # la cabecera viaja de verdad


async def test_traduce_el_rechazo_a_una_excepcion_propia(payments: PaymentsClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.post("https://pagos.example.com/charges").mock(
        return_value=httpx.Response(402, json={"error": "card_declined"})
    )

    with pytest.raises(PaymentDeclined, match="card_declined"):
        await payments.charge(amount_cents=1250, currency="EUR")


async def test_reintenta_una_vez_tras_error_de_red(payments: PaymentsClient, respx_mock: respx.MockRouter) -> None:
    route = respx_mock.post("https://pagos.example.com/charges").mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(201, json={"id": "ch_2", "status": "succeeded"})]
    )

    charge = await payments.charge(amount_cents=100, currency="EUR")

    assert charge.id == "ch_2"
    assert route.call_count == 2
```

`respx_mock` es la fixture que respx registra como plugin de pytest: activa el router para ese test, falla si sale una petición sin ruta (`assert_all_mocked=True` por defecto) y lo desactiva al terminar. `side_effect` con una lista devuelve cada elemento por turno, lo que te permite probar reintentos sin tocar el reloj.

Verificación: corre `pytest tests/test_payments.py -p no:cacheprovider` sin red (desconecta el Wi-Fi o exporta `HTTPS_PROXY=http://127.0.0.1:9`). Los tres deben pasar; si alguno intenta salir, respx lo corta con `AllMockedAssertionError` y te dice qué URL faltaba.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un `encode`/`decode` de un formato binario propio (cabecera + longitud + payload). Los tests con ejemplos pasan, pero en producción siguen apareciendo entradas que lo rompen. ¿Cómo lo pruebo con Hypothesis para encontrar lo que no se me ocurre?",
            },
            {
                "role": "assistant",
                "content": r"""Para un par `encode`/`decode` la propiedad es obvia y es la más potente que existe: **`decode(encode(x)) == x` para cualquier `x` válido**. Hypothesis genera miles de `x`, incluidos los que no se te ocurrirían (payload vacío, 255 bytes justos, bytes nulos, longitud máxima), y cuando encuentra un fallo lo **reduce** al ejemplo más pequeño que sigue fallando.

```bash
pip install hypothesis
```

Asumo este tipo de mensaje:

```python
# app/wire.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    kind: int        # 0-255
    payload: bytes   # hasta 65535 bytes
```

Los tests:

```python
# tests/test_wire.py
from hypothesis import assume, example, given, settings, strategies as st

from app.wire import Message, decode, encode

messages = st.builds(
    Message,
    kind=st.integers(min_value=0, max_value=255),
    payload=st.binary(min_size=0, max_size=65_535),
)


@given(messages)
@example(Message(kind=0, payload=b""))                 # borde que siempre quiero cubrir
@example(Message(kind=255, payload=b"\x00" * 65_535))  # máximo exacto
def test_roundtrip(msg: Message) -> None:
    assert decode(encode(msg)) == msg


@given(messages)
def test_la_longitud_codificada_coincide_con_el_payload(msg: Message) -> None:
    raw = encode(msg)
    assert int.from_bytes(raw[1:3], "big") == len(msg.payload)
    assert len(raw) == 3 + len(msg.payload)


@given(st.binary(max_size=200))
def test_decode_nunca_revienta_con_basura(raw: bytes) -> None:
    '''Entrada arbitraria: o decodifica o lanza nuestra excepción, nunca IndexError/ValueError.'''
    try:
        decode(raw)
    except WireError:
        pass


@given(messages, st.integers(min_value=1, max_value=4))
def test_decode_rechaza_mensajes_truncados(msg: Message, cut: int) -> None:
    raw = encode(msg)
    assume(len(raw) > cut)
    with pytest.raises(WireError):
        decode(raw[:-cut])
```

(Faltan `import pytest` y `from app.wire import WireError` arriba; los añades con el resto.)

**Qué hace cada test:**

1. **Roundtrip**: la propiedad central. `st.builds` construye `Message` con valores de las estrategias dadas; `@example` fija casos que quieres ver siempre, además de los aleatorios.
2. **Invariante estructural**: comprueba el formato sin pasar por `decode`, así un bug simétrico en ambas funciones (que haría pasar el roundtrip) se detecta igual.
3. **Robustez ante basura**: la propiedad «nunca lanza una excepción que no sea la nuestra» es la que suele estar fallando en producción.
4. **Truncamiento** con `assume` para descartar cortes que vaciarían el mensaje: Hypothesis genera otro ejemplo en vez de contar un fallo.

**Cómo leer un fallo.** Hypothesis imprime el ejemplo mínimo:

```
Falsifying example: test_roundtrip(
    msg=Message(kind=0, payload=b'\x00'),
)
```

Un payload de un byte nulo que no vuelve igual apunta, por ejemplo, a un `rstrip(b"\x00")` en `decode`. El ejemplo queda guardado en `.hypothesis/examples/` y se reintenta primero en la siguiente ejecución, así que el bug no «desaparece» cuando vuelves a correr. Cuando lo arregles, cópialo como `@example` explícito: es tu test de regresión.

**Ajustes prácticos:**

```python
@settings(max_examples=500, deadline=None)
```

`max_examples` sube de 100 a 500 para el roundtrip (es barato); `deadline=None` evita que un ejemplo grande de 65 KB falle por tardar más de 200 ms, que es el límite por defecto. En CI puedes definir un perfil con más ejemplos (`settings.register_profile("ci", max_examples=2000)` y `--hypothesis-profile=ci`).

Verificación de que las propiedades tienen dientes: introduce un bug a propósito (`max_size=65_534` en el encode, o quita el `big`) y ejecuta. Debe fallar en segundos con un ejemplo pequeño; si no, la estrategia no está generando ese borde y hay que ampliarla.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Mis tests de repositorio usan SQLite en memoria pero producción es Postgres, y ya nos pasó que un `ON CONFLICT ... DO UPDATE` funcionaba en uno y no en otro. ¿Vale la pena Testcontainers con pytest o es demasiado lento?",
            },
            {
                "role": "assistant",
                "content": r"""Vale la pena, y el coste es uno solo: unos 3-6 segundos para arrancar el contenedor **una vez por sesión**. Después, cada test cuesta lo mismo que con SQLite. Probar el repositorio contra otra base de datos es probar otra cosa; el `ON CONFLICT` que te falló es el ejemplo típico, pero hay más (tipos `JSONB`, `RETURNING`, orden de `NULL`, collation, `SELECT ... FOR UPDATE`).

```bash
pip install "testcontainers[postgres]" sqlalchemy psycopg
```

```python
# tests/conftest.py
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from app.models import Base


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    '''Un Postgres real en Docker durante toda la sesión; se destruye al terminar.'''
    container = PostgresContainer("postgres:16-alpine", driver="psycopg").with_command(
        "postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
    )
    with container as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def engine(postgres_url: str) -> Iterator[Engine]:
    engine = create_engine(postgres_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    '''Cada test en su transacción; rollback al final, tablas limpias para el siguiente.'''
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
```

Y el test que te habría avisado:

```python
# tests/test_user_repo.py
from app.repos import UserRepo


def test_upsert_actualiza_el_nombre_si_el_email_ya_existe(db):
    repo = UserRepo(db)
    repo.upsert(email="ana@example.com", name="Ana")
    repo.upsert(email="ana@example.com", name="Ana María")
    db.commit()

    assert [u.name for u in repo.all()] == ["Ana María"]
```

Decisiones:

- **`driver="psycopg"`**: la URL sale como `postgresql+psycopg://`, el driver moderno (psycopg 3). Sin ese argumento, testcontainers asume `psycopg2`.
- **`fsync=off` y compañía**: Postgres deja de esperar al disco. En tests es seguro (el contenedor se tira al final) y acelera las escrituras de forma notable.
- **`postgres:16-alpine`**: fija la **misma versión mayor que producción**; la gracia es reproducir su comportamiento, no «un Postgres».
- La transacción por test es la misma técnica que con SQLite; lo único que cambia es la URL.

Lo que necesitas en la máquina: Docker en marcha. Si no está, la fixture falla al arrancar con un error de conexión al socket; conviene convertirlo en un `pytest.skip` claro para quien corra solo los unitarios.

Comprobación: mide la suite antes y después con `pytest --durations=5`. Deberías ver `postgres_url` en el top con ~4 s de *setup* y el resto de tests por debajo de 50 ms cada uno. Si varios tests aparecen con cientos de ms, están haciendo `create_all` o abriendo engines propios.""",
            },
            {
                "role": "user",
                "content": "Funciona, pero en GitHub Actions el arranque del contenedor tarda 40 s en cada job (tenemos 6 jobs en matriz). ¿Se puede acortar?",
            },
            {
                "role": "assistant",
                "content": r"""Los 40 s son casi todos **descarga de la imagen** en un runner limpio, no arranque. Dos vías, y puedes combinarlas: que el runner levante Postgres como servicio (y tu fixture lo reutilice) o reducir lo que se descarga.

**Vía 1 (recomendada): `services:` de Actions + fixture que detecta un Postgres ya disponible.** El servicio arranca en paralelo con el *checkout* e instalación de dependencias, así que su coste queda enmascarado.

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.10", "3.11", "3.12"]
        group: [1, 2]
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U test"
          --health-interval 2s --health-timeout 5s --health-retries 15
    env:
      TEST_DATABASE_URL: postgresql+psycopg://test:test@localhost:5432/test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }
      - run: pip install -e ".[test]"
      - run: pytest --splits 2 --group ${{ matrix.group }}
```

Y la fixture prefiere la URL del entorno si existe:

```python
@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    from_env = os.environ.get("TEST_DATABASE_URL")
    if from_env:
        yield from_env           # CI: Postgres ya levantado como servicio
        return
    container = PostgresContainer("postgres:16-alpine", driver="psycopg").with_command(
        "postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
    )
    with container as pg:        # local: Testcontainers
        yield pg.get_connection_url()
```

Con `yield from_env` seguido de `return`, la fixture mantiene su forma de generador en ambas ramas. En local nadie exporta `TEST_DATABASE_URL`, así que sigue usando Docker como hasta ahora.

**Vía 2: reducir la descarga.** Si quieres mantener Testcontainers también en CI:

- `postgres:16-alpine` pesa ~100 MB frente a ~150 MB de la imagen Debian; ya lo tienes.
- Fija el *digest* (`postgres:16-alpine@sha256:...`) para que la caché de capas del runner no se invalide con cada rebuild de la etiqueta.
- Si tus jobs corren en runners propios, la imagen queda cacheada y los 40 s desaparecen solos.

**Lo que no te recomiendo:** `docker save` de la imagen a la caché de Actions (`actions/cache`). Restaurar 100 MB de caché y hacer `docker load` tarda casi lo mismo que descargar y añade un paso que se rompe.

Verificación: en el job de CI, el paso de `pytest` debería empezar a los pocos segundos de instalar dependencias y `--durations=5` ya no debe mostrar `postgres_url` en el top. Si sigue apareciendo con ~40 s, la variable no está llegando (revisa que `env:` esté a nivel de job, no de step).""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 26-30: Playwright (locators y page objects, fixtures y auth, test flaky, CI, mocks de red)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Voy a escribir el primer test e2e con Playwright para el login de nuestra app (Next.js). He visto lo de page objects y locators, pero no sé si usar page objects desde el principio o es sobreingeniería.",
            },
            {
                "role": "assistant",
                "content": r"""Empieza con locators y aserciones *web-first*; el page object lo extraes cuando la misma pantalla aparezca en tres o más tests. Para el login, que lo van a usar todos los tests que necesiten sesión, lo vas a extraer casi de inmediato, así que te muestro las dos etapas.

**Etapa 1: el test plano.**

```ts
// e2e/login.spec.ts
import { expect, test } from '@playwright/test'

test('un usuario válido llega al panel', async ({ page }) => {
  await page.goto('/login')

  await page.getByLabel('Correo electrónico').fill('ana@example.com')
  await page.getByLabel('Contraseña').fill('secreto123')
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: /hola, ana/i })).toBeVisible()
})

test('una contraseña incorrecta muestra el error y no navega', async ({ page }) => {
  await page.goto('/login')

  await page.getByLabel('Correo electrónico').fill('ana@example.com')
  await page.getByLabel('Contraseña').fill('mala')
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(page.getByRole('alert')).toHaveText(/credenciales no válidas/i)
  await expect(page).toHaveURL(/\/login$/)
})
```

Por qué está escrito así:

- **`getByLabel` / `getByRole`** en lugar de CSS: localizan como un usuario (y como un lector de pantalla). Si cambias clases o estructura, el test sigue; si rompes la accesibilidad, el test falla, que es lo que quieres.
- **Auto-wait.** `fill` y `click` esperan a que el elemento exista, sea visible y esté habilitado; `expect(locator).toBeVisible()` reintenta hasta 5 s. No necesitas `waitForSelector` ni `sleep`. Si te ves escribiendo `page.waitForTimeout`, algo está mal.
- **Un locator se evalúa al usarlo**, no al crearlo. Por eso puedes guardarlos en variables o en una clase sin que queden obsoletos tras una navegación.

**Etapa 2: page object**, cuando el login se repite. No es sobreingeniería si solo encapsula *cómo* se usa la pantalla y expone *acciones* con nombre de negocio:

```ts
// e2e/pages/login.page.ts
import type { Locator, Page } from '@playwright/test'

export class LoginPage {
  readonly email: Locator
  readonly password: Locator
  readonly submit: Locator
  readonly error: Locator

  constructor(private readonly page: Page) {
    this.email = page.getByLabel('Correo electrónico')
    this.password = page.getByLabel('Contraseña')
    this.submit = page.getByRole('button', { name: 'Entrar' })
    this.error = page.getByRole('alert')
  }

  async goto() {
    await this.page.goto('/login')
  }

  async loginAs(email: string, password: string) {
    await this.email.fill(email)
    await this.password.fill(password)
    await this.submit.click()
  }
}
```

```ts
// e2e/login.spec.ts
test('una contraseña incorrecta muestra el error', async ({ page }) => {
  const login = new LoginPage(page)
  await login.goto()
  await login.loginAs('ana@example.com', 'mala')

  await expect(login.error).toHaveText(/credenciales no válidas/i)
})
```

Regla para que el page object no degenere: **no pongas aserciones dentro** (`expect` vive en el test) y no lo conviertas en un «dios» que sabe de todas las pantallas. Un archivo por pantalla, métodos que son acciones de usuario, y los locators como campos públicos para que el test afirme sobre ellos.

Para arrancar sin adivinar nombres de labels: `npx playwright codegen http://localhost:3000/login` abre el navegador y te escribe los locators al interactuar. Tómalo como borrador, no como test final.

Comprobación: ejecuta `npx playwright test login --repeat-each 5`. Cinco pasadas limpias con `baseURL` configurado en `playwright.config.ts` (`use: { baseURL: 'http://localhost:3000' }`) y ya tienes la base.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Cada test de Playwright hace login por la interfaz y son 4 segundos extra por test; con 80 tests es demasiado. ¿Cómo hago el login una vez y lo reutilizo? He leído de fixtures y de storageState pero no sé combinarlos.",
            },
            {
                "role": "assistant",
                "content": r"""Haz el login **una vez en un proyecto de setup**, guarda las cookies y el `localStorage` en un archivo con `storageState`, y que el resto de proyectos lo carguen. Las fixtures entran después, para dar a cada test una página ya autenticada o datos creados por API sin repetir código.

**1. Proyecto de setup con `dependencies`.**

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  use: { baseURL: 'http://localhost:3000', trace: 'on-first-retry' },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' },
      dependencies: ['setup'],
    },
  ],
  webServer: { command: 'npm run start', url: 'http://localhost:3000', reuseExistingServer: !process.env.CI },
})
```

```ts
// e2e/auth.setup.ts
import { expect, test as setup } from '@playwright/test'

const authFile = 'playwright/.auth/user.json'

setup('autenticar usuario de pruebas', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Correo electrónico').fill(process.env.E2E_USER ?? 'ana@example.com')
  await page.getByLabel('Contraseña').fill(process.env.E2E_PASSWORD ?? 'secreto123')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: /hola/i })).toBeVisible()   // sesión confirmada antes de guardar

  await page.context().storageState({ path: authFile })
})
```

Añade `playwright/.auth/` al `.gitignore`. A partir de aquí, cada test del proyecto `chromium` arranca con la sesión ya iniciada: `await page.goto('/dashboard')` y listo. Los 4 s se pagan una vez por ejecución.

**2. Fixtures para lo que se repite dentro del test.** Extiende `test` una vez y úsalo en todos los specs:

```ts
// e2e/fixtures.ts
import { test as base, expect } from '@playwright/test'
import { DashboardPage } from './pages/dashboard.page'

type Fixtures = {
  dashboard: DashboardPage
  project: { id: string; name: string }
}

export const test = base.extend<Fixtures>({
  dashboard: async ({ page }, use) => {
    const dashboard = new DashboardPage(page)
    await dashboard.goto()
    await use(dashboard)
  },

  // Datos creados por API (rápido) y borrados al terminar, aunque el test falle
  project: async ({ request }, use) => {
    const res = await request.post('/api/projects', { data: { name: `e2e-${Date.now()}` } })
    expect(res.ok()).toBeTruthy()
    const project = await res.json()
    await use(project)
    await request.delete(`/api/projects/${project.id}`)
  },
})

export { expect }
```

`request` es la fixture de Playwright para llamadas HTTP; **comparte el `storageState`** del proyecto, así que las llamadas a tu API van autenticadas sin configurar nada.

```ts
// e2e/projects.spec.ts
import { expect, test } from './fixtures'

test('el proyecto recién creado aparece en el panel', async ({ dashboard, project }) => {
  await expect(dashboard.projectRow(project.name)).toBeVisible()
})
```

El test ya no sabe nada de login ni de cómo se crea un proyecto; lee como el requisito.

**3. Cuando los tests se pisan los datos.** Si varios workers comparten el mismo usuario y modifican el mismo estado, aísla por worker con una fixture de ámbito `worker` que cree su propio usuario (`{ scope: 'worker' }` en `base.extend`) y genere un `storageState` por worker con `request` contra `/api/login`. Es el paso siguiente; no lo hagas hasta que veas una colisión real.

Verificación: `npx playwright test --list` debe mostrar `[setup] › auth.setup.ts` primero y ningún spec del proyecto `chromium` haciendo `goto('/login')`. Y el tiempo total con `--workers=4` debería caer de ~80 × 4 s de login a unos 4 s en total.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto: señala problemas concretos y propone el arreglo mínimo."},
            {
                "role": "user",
                "content": r"""Este test de Playwright falla una de cada cinco veces en CI, nunca en local. Revísalo:

```ts
test('añade un producto al carrito', async ({ page }) => {
  await page.goto('http://localhost:3000/products')
  await page.waitForLoadState('networkidle')
  await page.click('.product-card button')
  await page.waitForTimeout(1000)
  const badge = await page.$('.cart-badge')
  expect(await badge?.textContent()).toBe('1')
  await page.click('text=Carrito')
  await page.waitForTimeout(2000)
  expect(await page.textContent('.total')).toContain('25,00')
})
```""",
            },
            {
                "role": "assistant",
                "content": r"""El test es intermitente porque **ninguna de sus esperas está ligada a lo que espera**: duerme tiempos fijos y luego lee el DOM una sola vez. En CI, más lento, el DOM aún no está listo cuando lo lee. Problemas por línea:

1. `goto('http://localhost:3000/products')`: URL absoluta. Rompe en cuanto CI use otro puerto. Usa `baseURL` en la config y `goto('/products')`.
2. `waitForLoadState('networkidle')`: espera 500 ms sin tráfico de red. Con *polling*, analíticas o websockets no llega nunca o llega tarde; y no garantiza que el producto esté pintado. Sobra: la siguiente acción ya espera al botón.
3. `page.click('.product-card button')`: hay varias tarjetas; `page.click` con un selector que casa con N elementos pulsa el primero sin avisar. Qué producto se añade depende del orden de carga. Localiza la tarjeta por su contenido.
4. `waitForTimeout(1000)` y `waitForTimeout(2000)`: tiempos fijos. Si el servidor tarda 1 100 ms, falla; si tarda 100 ms, pierdes 2,9 s. Es la causa directa del 1 de cada 5.
5. `page.$('.cart-badge')` devuelve un `ElementHandle` **sin auto-wait**: si el badge aún no existe, `badge` es `null`, `badge?.textContent()` devuelve `undefined` y la aserción falla con un mensaje que no dice nada.
6. `expect(await x.textContent()).toBe('1')`: aserción sobre un valor ya leído, sin reintento. Aunque el badge llegue 50 ms después, el test ya ha fallado.
7. `'text=Carrito'`: sintaxis de selector antigua; si hay un párrafo que dice «Carrito vacío», puede casar con él.

**Arreglo mínimo** (misma intención, sin esperas fijas):

```ts
import { expect, test } from '@playwright/test'

test('añade un producto al carrito', async ({ page }) => {
  await page.goto('/products')

  const card = page.getByRole('article').filter({ hasText: 'Teclado mecánico' })
  await card.getByRole('button', { name: 'Añadir' }).click()

  await expect(page.getByTestId('cart-badge')).toHaveText('1')

  await page.getByRole('link', { name: 'Carrito' }).click()
  await expect(page.getByTestId('cart-total')).toContainText('25,00')
})
```

Qué cambia en el comportamiento: `toHaveText` y `toContainText` **reintentan** hasta que se cumple o vence el timeout (5 s por defecto), así que absorben cualquier latencia sin dormir un milisegundo de más. El `filter({ hasText })` fija qué producto se añade; el precio esperado deja de depender del orden.

Si `.cart-badge` y `.total` no tienen `data-testid`, añádelos al componente (`data-testid="cart-badge"`): un badge no tiene rol semántico y es el caso legítimo para un test id.

**Cómo confirmar que el arreglo es real y no suerte:**

```bash
npx playwright test cart.spec.ts --repeat-each 20 --workers 4
```

Veinte pasadas en paralelo reproducen la carga de CI. Si alguna falla, ejecútala con `--trace on` y abre el `trace.zip` con `npx playwright show-trace`: la línea de tiempo muestra exactamente qué había en pantalla cuando la aserción venció, que es la información que el `waitForTimeout` te ocultaba.

Un último punto de configuración: si el proyecto ya tiene `retries: 2` en CI, ese reintento estaba **enmascarando** este test como «pasa a la segunda». Mira el reporte HTML: los tests marcados *flaky* son la lista de los que tienen este mismo patrón.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Set up Playwright in GitHub Actions for us: we have ~300 e2e tests that take 25 minutes on one runner. I want sharding, traces only when a test actually fails, and a single HTML report I can download.",
            },
            {
                "role": "assistant",
                "content": r"""Shard across four runners, collect a `blob` report from each, and merge them in a final job into one HTML report. Traces come for free with `trace: 'on-first-retry'`: Playwright records only when a test is being retried after a failure, so green runs pay nothing.

**1. Config.**

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,          // a stray test.only fails the build instead of skipping 299 tests
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? 'blob' : 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
```

**2. Workflow.**

```yaml
# .github/workflows/e2e.yml
name: e2e
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    container:
      image: mcr.microsoft.com/playwright:v1.56.0-noble   # must match the @playwright/test version in package.json
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci
      - run: npm run build
      - run: npx playwright test --shard=${{ matrix.shard }}/4
        env:
          HOME: /root   # workaround: the container image runs as root and Firefox/WebKit need a writable HOME
      - uses: actions/upload-artifact@v4
        if: ${{ !cancelled() }}
        with:
          name: blob-report-${{ matrix.shard }}
          path: blob-report
          retention-days: 1

  report:
    needs: [test]
    if: ${{ !cancelled() }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci
      - uses: actions/download-artifact@v4
        with:
          path: all-blob-reports
          pattern: blob-report-*
          merge-multiple: true
      - run: npx playwright merge-reports --reporter html ./all-blob-reports
      - uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report
          retention-days: 14
```

**Why each decision:**

- **The official container image** instead of `npx playwright install --with-deps`: browsers and system libraries are already there, which saves 1-2 minutes per shard. Pin the tag to your `@playwright/test` version; a mismatch fails at startup with a clear "Executable doesn't exist" error.
- **`fail-fast: false`**: one red shard should not cancel the others, or you lose their results and have to rerun everything.
- **`if: ${{ !cancelled() }}`** on the upload and the report job: artifacts must be uploaded even when tests fail; that is precisely when you need them.
- **`blob` → `merge-reports`**: the only way to get one HTML report (with traces embedded) out of four runners. The merged report shows per-test retries and the *flaky* label.
- **`workers: 2`** per shard: GitHub's standard runners have 4 vCPUs; two browser instances plus your app is about what they handle without timeouts creeping in. Measure before raising it.

**Reading a failure:** download `playwright-report`, unzip, `npx playwright show-report playwright-report`. Each failed test lists its attempts; the retried attempt has a *Trace* link with the timeline, DOM snapshots, network and console. You can also drag the `trace.zip` onto https://trace.playwright.dev.

**Expected numbers:** 25 min / 4 shards ≈ 6-7 min per shard plus ~1.5 min of setup, so a PR gets e2e feedback in about 9 minutes. If shards are uneven (one takes 12 min, another 3), Playwright balances by file, not by test: split the heaviest spec files.

Sanity check after the first run: open the merged report and confirm it shows all ~300 tests. If it shows ~75, the download step merged only one shard; verify the `pattern` and `merge-multiple: true`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "En Playwright, ¿mockeamos la API o pegamos al backend real? Mi equipo está dividido: unos dicen que si mockeas ya no es e2e, otros que contra el backend real los tests son lentos y frágiles.",
            },
            {
                "role": "assistant",
                "content": r"""Los dos tienen razón, porque hablan de dos tipos de test distintos. La decisión no es global; es por test:

| Tipo de test | Backend | Cuántos |
|---|---|---|
| Flujos críticos de negocio (registro, compra, pago) | **real**, con datos de prueba | pocos (5-15) |
| Comportamiento de la UI ante estados concretos (lista vacía, error 500, carga lenta, 1 000 filas) | **mockeado** con `page.route` | la mayoría |
| Contrato entre front y API | ni uno ni otro: tests de contrato (Pact / OpenAPI) | aparte |

Un flujo de compra contra un backend mockeado no prueba que compras; solo que la UI reacciona a un JSON que tú escribiste. Y un test de «la tabla muestra el estado vacío» contra el backend real te obliga a dejar la base de datos vacía, cosa que otro test en paralelo acaba de romper: ahí nace la fragilidad.

**Mock con `page.route`:**

```ts
import { expect, test } from '@playwright/test'

test('muestra el estado vacío cuando no hay pedidos', async ({ page }) => {
  await page.route('**/api/orders?*', (route) =>
    route.fulfill({ status: 200, json: { items: [], total: 0 } }),
  )

  await page.goto('/orders')

  await expect(page.getByRole('heading', { name: 'Todavía no tienes pedidos' })).toBeVisible()
  await expect(page.getByRole('table')).toHaveCount(0)
})
```

`page.route` intercepta en el navegador antes de que la petición salga; el resto de llamadas (las que no casan con el patrón) siguen yendo al servidor real. Puedes mezclar: backend real para la sesión y mock solo para el endpoint cuyo estado quieres forzar.

**Contra el real, cuando toca**, afirma sobre la red en vez de dormir:

```ts
test('crear un pedido lo persiste', async ({ page }) => {
  await page.goto('/orders/new')
  await page.getByLabel('Producto').fill('Teclado')

  const created = page.waitForResponse((res) => res.url().includes('/api/orders') && res.status() === 201)
  await page.getByRole('button', { name: 'Crear' }).click()
  const order = await (await created).json()

  await expect(page).toHaveURL(`/orders/${order.id}`)
})
```

`waitForResponse` se registra **antes** del `click`; si lo pones después, la respuesta puede haber llegado ya y el test se queda esperando una que no vendrá.

**Reglas que zanjan la discusión del equipo:**

1. Si el test se llama «el usuario puede X», backend real.
2. Si el test se llama «la pantalla muestra Y cuando Z», mock.
3. Los mocks se escriben a partir de respuestas reales (copia el JSON de la pestaña Network o graba un HAR con `page.routeFromHAR`), nunca inventados; y los tests de contrato garantizan que esas formas siguen vigentes.
4. Un mock que haya que actualizar en cada cambio del backend es un olor: ese test estaba probando el backend, no la UI.

Verificación de que el reparto es sano: cuenta cuántos tests fallan cuando apagas el backend. Deberían ser exactamente los de la primera fila de la tabla; si cae media suite, hay tests de UI que dependen de datos reales sin necesidad.""",
            },
            {
                "role": "user",
                "content": "Vale. ¿Y cómo pruebo el estado de error del checkout (el backend devuelve 500 al confirmar) sin tocar el backend ni meter un flag raro en producción?",
            },
            {
                "role": "assistant",
                "content": r"""Con `page.route` sobre el endpoint de confirmación, devolviendo el 500 solo en ese test. El resto del checkout (catálogo, carrito, sesión) sigue contra el backend real, así que pruebas la reacción de la UI en el contexto verdadero sin tocar producción ni añadir flags.

```ts
import { expect, test } from '@playwright/test'

test('un fallo al confirmar muestra el error y conserva el carrito', async ({ page }) => {
  await test.step('llegar al resumen con un producto en el carrito', async () => {
    await page.goto('/products')
    await page.getByRole('article').filter({ hasText: 'Teclado mecánico' })
      .getByRole('button', { name: 'Añadir' }).click()
    await page.getByRole('link', { name: 'Carrito' }).click()
    await page.getByRole('button', { name: 'Ir al pago' }).click()
    await expect(page.getByRole('heading', { name: 'Resumen del pedido' })).toBeVisible()
  })

  await test.step('el backend falla al confirmar', async () => {
    await page.route('**/api/checkout/confirm', (route) =>
      route.fulfill({ status: 500, json: { message: 'internal error' } }),
    )
    await page.getByRole('button', { name: 'Confirmar pedido' }).click()
  })

  await test.step('la UI informa sin perder el estado', async () => {
    await expect(page.getByRole('alert')).toHaveText(/no hemos podido confirmar/i)
    await expect(page.getByRole('button', { name: 'Confirmar pedido' })).toBeEnabled()
    await expect(page.getByText('Teclado mecánico')).toBeVisible()      // el carrito sigue ahí
    await expect(page).toHaveURL(/\/checkout$/)                           // no navegó a "pedido creado"
  })
})

test('un corte de red al confirmar se trata como error recuperable', async ({ page }) => {
  await page.goto('/checkout')
  await page.route('**/api/checkout/confirm', (route) => route.abort('connectionrefused'))

  await page.getByRole('button', { name: 'Confirmar pedido' }).click()

  await expect(page.getByRole('alert')).toHaveText(/comprueba tu conexión/i)
})
```

Detalles que importan:

- **La ruta se registra justo antes del clic**, no al principio: así los pasos anteriores usan el backend real y el mock afecta únicamente a la confirmación. `page.route` aplica a las peticiones que ocurren **después** de registrarlo.
- **`route.abort('connectionrefused')`** simula el fallo de red, que es un caso distinto del 500: `fetch` rechaza con `TypeError` en vez de devolver una respuesta. Si tu código solo mira `response.ok`, este segundo test lo descubre.
- **`test.step`** divide el reporte: cuando falle, verás en qué fase (llegar al resumen, provocar el fallo, comprobar) y la traza queda anotada por pasos.
- Las aserciones comprueban **lo que el usuario necesita**: mensaje, botón reutilizable, carrito intacto, no navegó. Son los cuatro bugs reales que suele tener un checkout ante un 500.

Comprobación de que el mock no se queda pegado: cada `page` es un contexto nuevo por test, así que la ruta muere con él. Si por alguna razón reutilizas `page` entre tests (`test.describe.configure({ mode: 'serial' })` con un contexto compartido), quita la ruta al salir con `await page.unroute('**/api/checkout/confirm')`.""",
            },
        ]
    },
]
