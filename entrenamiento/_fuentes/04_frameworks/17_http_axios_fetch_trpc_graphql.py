"""HTTP: Axios en profundidad, fetch moderno, tRPC 11, GraphQL (Apollo/Yoga, DataLoader, clientes) y REST bien hecho."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# ---------------------------------------------------------------------------
# 1-10: Axios (instancia, interceptores, refresh de token, cancelación, reintentos,
#       timeouts, isAxiosError, tipado, subida con progreso, comparación con fetch)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy empezando con Axios en un frontend con TypeScript. Veo que unos hacen `axios.get(url)` directamente y otros crean una «instancia». ¿Cuál es la diferencia y cómo la configuro bien?",
            },
            {
                "role": "assistant",
                "content": r"""Usa siempre una instancia: `axios.create()` te da un cliente con su propia configuración (URL base, timeout, cabeceras, interceptores) sin tocar el `axios` global, que es compartido por cualquier librería que también lo use. Llamar a `axios.get(url)` directamente obliga a repetir la URL completa y el timeout en cada llamada, y cualquier interceptor que registres afecta a todo el proceso.

```ts
// src/api/client.ts
import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,   // 'https://api.example.com/v1'
  timeout: 10_000,                          // ms; sin esto una petición puede colgarse indefinidamente
  headers: { Accept: 'application/json' },
})
```

Y las llamadas quedan cortas y tipadas:

```ts
// src/api/users.ts
import { api } from './client'

export interface User {
  id: number
  name: string
  email: string
}

export async function getUser(id: number): Promise<User> {
  const { data } = await api.get<User>(`/users/${id}`)
  return data
}

export async function createUser(input: Omit<User, 'id'>): Promise<User> {
  const { data } = await api.post<User>('/users', input)
  return data
}
```

Qué hace Axios por ti en estas dos funciones:

- **Resuelve la URL** contra `baseURL`: `/users/7` → `https://api.example.com/v1/users/7`.
- **Serializa el cuerpo**: el objeto `input` viaja como JSON con `Content-Type: application/json` sin que lo indiques.
- **Parsea la respuesta**: `data` ya es el objeto, no un `Response` que haya que leer.
- **Lanza en 4xx/5xx**: a diferencia de `fetch`, un 404 es una excepción; no tienes que comprobar `res.ok`.

Sobre el genérico `api.get<User>`: le dice a TypeScript qué forma tiene `data`, pero **no comprueba nada en tiempo de ejecución**. Si el servidor devuelve otra cosa, el tipo miente. Para datos que no controlas, valida con zod en el borde (`UserSchema.parse(data)`); para una API propia y versionada, el genérico suele bastar.

Dos ajustes que conviene decidir desde el principio:

```ts
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10_000,
  headers: { Accept: 'application/json' },
  withCredentials: true,                  // solo si autenticas con cookie de sesión y la API está en otro origen
  paramsSerializer: { indexes: null },    // ?ids=1&ids=2 en vez de ?ids[]=1&ids[]=2 (lo que esperan la mayoría de backends)
})
```

Comprobación rápida de que la instancia está bien montada, en la consola del navegador o en un test:

```ts
const res = await api.get('/health')
console.log(res.config.baseURL, res.config.timeout, res.status)   // 'https://api.example.com/v1' 10000 200
```

Si `baseURL` sale `undefined`, la variable de entorno no está definida en ese modo de Vite (`.env.development` frente a `.env.production`), que es el error más común en el primer despliegue.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo uso los interceptores de Axios para meter el token en cada petición y para que los errores de la API lleguen a mis componentes con una forma uniforme? Y una duda: si registro varios, ¿en qué orden se ejecutan?",
            },
            {
                "role": "assistant",
                "content": r"""Un interceptor de **request** modifica la configuración antes de enviar; uno de **response** transforma la respuesta o el error antes de que llegue a quien llamó. Cada uno recibe dos funciones: la de éxito y la de error.

```ts
// src/api/client.ts
import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getAccessToken } from '../auth/session'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL, timeout: 10_000 })

// Request: añade el token si existe
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config          // obligatorio devolver config; si no, la petición nunca sale
})

// Response: normaliza cualquier fallo a un ApiError con forma conocida
export class ApiError extends Error {
  constructor(
    public readonly status: number | null,   // null = no hubo respuesta (red, timeout, cancelación)
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error)
    const err = error as AxiosError<{ message?: string; code?: string; details?: unknown }>

    if (err.response) {
      const body = err.response.data
      return Promise.reject(
        new ApiError(err.response.status, body?.code ?? `HTTP_${err.response.status}`, body?.message ?? err.message, body?.details),
      )
    }
    if (err.code === 'ERR_CANCELED') return Promise.reject(new ApiError(null, 'CANCELED', 'Petición cancelada'))
    if (err.code === 'ECONNABORTED') return Promise.reject(new ApiError(null, 'TIMEOUT', 'El servidor tardó demasiado'))
    return Promise.reject(new ApiError(null, 'NETWORK', 'Sin conexión con el servidor'))
  },
)
```

En los componentes ya no hay `axios.isAxiosError` ni `error.response?.data?.message` repartidos por todas partes:

```ts
try {
  await createUser(input)
} catch (e) {
  if (e instanceof ApiError && e.status === 422) setFieldErrors(e.details)
  else if (e instanceof ApiError && e.code === 'CANCELED') return
  else toast.error(e instanceof ApiError ? e.message : 'Error inesperado')
}
```

**Orden de ejecución.** Es lo que sorprende a casi todo el mundo:

- Los interceptores de **request** se ejecutan en **orden inverso** al de registro: el último que añades es el primero que corre.
- Los de **response** se ejecutan en el **orden** de registro.

```ts
api.interceptors.request.use((c) => { console.log('req A'); return c })
api.interceptors.request.use((c) => { console.log('req B'); return c })
api.interceptors.response.use((r) => { console.log('res A'); return r })
api.interceptors.response.use((r) => { console.log('res B'); return r })

await api.get('/x')
// req B → req A → (petición) → res A → res B
```

Piensa en ellos como capas de cebolla: la última capa añadida es la más externa, y la petición la atraviesa de fuera hacia dentro; la respuesta, de dentro hacia fuera. En la práctica: registra primero lo genérico (logging) y después lo específico (auth) si quieres que auth vea la config final.

Dos detalles más:

- `use()` devuelve un id; `api.interceptors.request.eject(id)` lo quita. Útil en tests o para interceptores que dependen de una sesión.
- Un interceptor de response que **relanza** debe hacerlo con `Promise.reject` (o `throw`); si devuelves un valor normal, Axios lo interpreta como «error manejado» y el `await` de quien llamó recibe ese valor como respuesta válida.

Verificación mínima: un test con msw que devuelva `422 { code: 'VALIDATION', message: 'email inválido', details: {...} }` y afirme `await expect(createUser(x)).rejects.toMatchObject({ status: 422, code: 'VALIDATION' })`. Si llega un `AxiosError` en vez de `ApiError`, el interceptor no está registrado en la instancia que usas.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Mi interceptor de refresh de token entra en bucle: cuando el refresh también devuelve 401 la app se queda llamando a `/auth/refresh` sin parar, y además cuando abro el panel con 6 peticiones a la vez se dispara el refresh 6 veces y el backend invalida el refresh token (rotación). Este es el código:

```ts
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const { data } = await api.post('/auth/refresh', { refreshToken: getRefreshToken() })
      setTokens(data)
      error.config.headers.Authorization = `Bearer ${data.accessToken}`
      return api(error.config)
    }
    return Promise.reject(error)
  },
)
```""",
            },
            {
                "role": "assistant",
                "content": r"""Hay tres defectos y los tres se ven en el código:

1. **El refresh pasa por la misma instancia `api`**, así que su 401 entra en el mismo interceptor, que vuelve a llamar a `/auth/refresh`: bucle infinito.
2. **No hay marca de reintento**: si la petición reintentada vuelve a dar 401 (token nuevo pero permisos insuficientes), se refresca otra vez, y otra.
3. **No hay refresh «en vuelo» compartido**: seis 401 simultáneos producen seis refresh en paralelo; con rotación, el segundo ya usa un refresh token revocado y el backend cierra la sesión.

El arreglo es un **único refresh en curso** del que cuelgan todas las peticiones que lo esperan, hecho con una instancia sin interceptores, y una marca para reintentar una sola vez.

```ts
// src/api/client.ts
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { clearSession, getAccessToken, getRefreshToken, setTokens } from '../auth/session'

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL, timeout: 10_000 })

// Instancia "desnuda" para el refresh: sin interceptores, no puede entrar en recursión
const authClient = axios.create({ baseURL: import.meta.env.VITE_API_URL, timeout: 10_000 })

let refreshInFlight: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const { data } = await authClient.post<{ accessToken: string; refreshToken: string }>('/auth/refresh', {
    refreshToken: getRefreshToken(),
  })
  setTokens(data)
  return data.accessToken
}

function refreshOnce(): Promise<string> {
  // Todas las peticiones que fallen mientras hay un refresh en curso esperan a ESTA promesa
  refreshInFlight ??= refreshAccessToken().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined
    if (error.response?.status !== 401 || !config || config._retried) {
      return Promise.reject(error)
    }
    config._retried = true

    let token: string
    try {
      token = await refreshOnce()
    } catch (refreshError) {
      clearSession()                 // refresh inválido: cerrar sesión y propagar el 401 original
      return Promise.reject(error)
    }
    config.headers.Authorization = `Bearer ${token}`
    return api(config)
  },
)
```

Traza con tus seis peticiones simultáneas:

```
t0  6 peticiones → 6 × 401
t1  la 1.ª llama refreshOnce(): refreshInFlight = promesa P
t1  las otras 5 llaman refreshOnce(): refreshInFlight ya existe → reciben P
t2  P resuelve con el token nuevo (UNA llamada a /auth/refresh)
t2  las 6 reintentan con el token nuevo, cada una marcada _retried = true
t3  finally → refreshInFlight = null, listo para la próxima caducidad
```

Y el caso del bucle: si `/auth/refresh` devuelve 401, lo recibe `authClient`, que no tiene interceptor; `refreshOnce()` rechaza, entras en el `catch`, cierras sesión y rechazas con el error original. Ninguna segunda llamada.

Tres puntos para no reintroducirlo:

- **`??=`** es la clave del *single-flight*; con `if (!refreshInFlight) refreshInFlight = ...` es equivalente, pero no lo separes en dos pasos con un `await` en medio o vuelves a tener la carrera.
- `_retried` vive en el `config` de esa petición, que es un objeto nuevo por llamada; no contamina otras.
- Si el backend distingue «token caducado» de «sin permiso» (`401` frente a `403`, o un `code` en el cuerpo), filtra por eso y no refresques ante un 401 de credenciales incorrectas en el login: añade `config.url?.endsWith('/auth/login')` a la condición de salida.

Verificación con un test (msw + Vitest): un handler que devuelve 401 a las dos primeras peticiones a `/me` y 200 después, y un contador en `/auth/refresh`. Lanza `Promise.all([api.get('/me'), api.get('/me'), api.get('/me')])` y afirma que el contador vale **1** y las tres resuelven. Con tu código actual ese test da 3.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un buscador con autocompletado en React que llama a la API con Axios en cada tecla. A veces llega antes la respuesta de «ca» que la de «cas» y se pintan resultados viejos. ¿Cómo cancelo la petición anterior?",
            },
            {
                "role": "assistant",
                "content": r"""Con `AbortController`: pasas su `signal` a Axios y, cuando llega una tecla nueva, abortas el anterior. La petición cancelada rechaza con `CanceledError` (`code: 'ERR_CANCELED'`), que ignoras. Así nunca se pinta una respuesta que ya no corresponde al texto actual, porque la vieja no llega a resolver.

```ts
// src/api/search.ts
import { api } from './client'

export interface Suggestion { id: string; label: string }

export async function searchSuggestions(query: string, signal: AbortSignal): Promise<Suggestion[]> {
  const { data } = await api.get<Suggestion[]>('/search/suggest', { params: { q: query }, signal })
  return data
}
```

```tsx
// src/components/SearchBox.tsx
import axios from 'axios'
import { useEffect, useState } from 'react'
import { searchSuggestions, type Suggestion } from '../api/search'

export function SearchBox() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Suggestion[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        setResults(await searchSuggestions(query, controller.signal))
        setError(null)
      } catch (e) {
        if (axios.isCancel(e)) return            // la cancelamos nosotros: no es un error
        setError('No se pudieron cargar sugerencias')
      }
    }, 250)                                       // debounce: no dispares una petición por tecla

    return () => {
      clearTimeout(timer)
      controller.abort()                          // tecla nueva o desmontaje: cancela la anterior
    }
  }, [query])

  return (
    <div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Buscar" />
      {error && <p role="alert">{error}</p>}
      <ul>{results.map((r) => <li key={r.id}>{r.label}</li>)}</ul>
    </div>
  )
}
```

Por qué cada pieza:

- **El cleanup del `useEffect`** se ejecuta antes del siguiente efecto (cada cambio de `query`) y al desmontar. Es el sitio natural para abortar: un controlador por valor de `query`, sin refs ni estado extra.
- **`axios.isCancel(e)`** distingue la cancelación de un error real. Si no la filtras, cada tecla muestra «No se pudieron cargar» durante un instante.
- **Debounce de 250 ms** reduce peticiones; la cancelación resuelve las que aun así se solapan. Son complementarios: el debounce ahorra red, el abort garantiza el orden.
- **`AbortController` es el mecanismo estándar**; `CancelToken` de Axios está deprecado desde 1.x. El mismo `signal` sirve para `fetch` si algún día cambias de cliente.

Qué pasa en el navegador cuando abortas: la petición HTTP se corta de verdad (verás `(canceled)` en la pestaña Network), no solo se ignora la respuesta, así que también liberas conexiones.

Dos extensiones cuando las necesites:

- **Timeout por petición combinado con cancelación manual** (Node 20.3+ y navegadores modernos): `signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5_000)])`.
- Si usas TanStack Query, no hagas nada de esto a mano: `useQuery({ queryKey: ['suggest', query], queryFn: ({ signal }) => searchSuggestions(query, signal) })` te pasa el `signal` y cancela al cambiar la clave.

Verificación: en Network, escribe «casa» rápido. Debe quedar como mucho una petición completada (la de «casa») y las anteriores marcadas como canceladas; en pantalla nunca aparecen resultados de «ca» después de los de «cas».""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y un comentario breve."},
            {
                "role": "user",
                "content": "Reintentos con backoff exponencial y jitter para una instancia de Axios, solo en errores de red y 5xx/429, respetando `Retry-After`, y nunca en POST. TypeScript.",
            },
            {
                "role": "assistant",
                "content": r"""```ts
// src/api/retry.ts
// Interceptor de respuesta: reintenta la misma petición con espera exponencial + jitter completo.
// Solo métodos idempotentes, solo fallos transitorios, y respeta Retry-After si el servidor lo envía.
import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

export interface RetryOptions {
  retries?: number       // intentos adicionales (default 3)
  baseMs?: number        // espera base (default 200)
  maxMs?: number         // tope de espera por intento (default 8000)
}

type RetryConfig = InternalAxiosRequestConfig & { _retryCount?: number }

const IDEMPOTENT = new Set(['get', 'head', 'options', 'put', 'delete'])
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504])

function isTransient(error: AxiosError): boolean {
  if (error.code === 'ERR_CANCELED') return false                    // cancelado por el usuario: nunca reintentar
  if (!error.response) return error.code !== 'ERR_BAD_OPTION'        // red, timeout, DNS → sí
  return TRANSIENT_STATUS.has(error.response.status)
}

function retryAfterMs(error: AxiosError): number | null {
  const header = error.response?.headers?.['retry-after']
  if (!header) return null
  const seconds = Number(header)
  if (!Number.isNaN(seconds)) return seconds * 1000
  const date = Date.parse(String(header))                            // formato HTTP-date
  return Number.isNaN(date) ? null : Math.max(0, date - Date.now())
}

function backoffMs(attempt: number, baseMs: number, maxMs: number): number {
  const cap = Math.min(maxMs, baseMs * 2 ** attempt)
  return Math.random() * cap                                         // "full jitter": evita que N clientes reintenten a la vez
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const id = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => { clearTimeout(id); reject(signal.reason) }, { once: true })
  })

export function installRetry(client: AxiosInstance, { retries = 3, baseMs = 200, maxMs = 8_000 }: RetryOptions = {}) {
  client.interceptors.response.use(undefined, async (error: unknown) => {
    if (!axios.isAxiosError(error) || !error.config) throw error
    const config = error.config as RetryConfig
    const method = (config.method ?? 'get').toLowerCase()
    const attempt = config._retryCount ?? 0

    if (!IDEMPOTENT.has(method) || !isTransient(error) || attempt >= retries) throw error

    config._retryCount = attempt + 1
    const wait = retryAfterMs(error) ?? backoffMs(attempt, baseMs, maxMs)
    await sleep(wait, config.signal as AbortSignal | undefined)       // si abortan durante la espera, sale con el motivo del abort
    return client(config)
  })
}
```

```ts
// src/api/client.ts
import axios from 'axios'
import { installRetry } from './retry'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL, timeout: 10_000 })
installRetry(api, { retries: 3 })
```

```ts
// src/api/retry.test.ts — comprueba el contrato: 3 reintentos en GET 503, ninguno en POST
import axios from 'axios'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { installRetry } from './retry'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('reintenta un GET con 503 y acaba resolviendo', async () => {
  let calls = 0
  server.use(http.get('http://t/x', () => (++calls < 3 ? new HttpResponse(null, { status: 503 }) : HttpResponse.json({ ok: 1 }))))
  const client = axios.create({ baseURL: 'http://t' })
  installRetry(client, { retries: 3, baseMs: 1, maxMs: 2 })          // esperas de ~1 ms para no ralentizar el test

  await expect(client.get('/x')).resolves.toMatchObject({ data: { ok: 1 } })
  expect(calls).toBe(3)
})

it('nunca reintenta un POST', async () => {
  let calls = 0
  server.use(http.post('http://t/x', () => { calls++; return new HttpResponse(null, { status: 503 }) }))
  const client = axios.create({ baseURL: 'http://t' })
  installRetry(client)

  await expect(client.post('/x', {})).rejects.toMatchObject({ response: { status: 503 } })
  expect(calls).toBe(1)
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
                "content": "¿Qué cubre exactamente el `timeout` de Axios? Tengo `timeout: 5000` y aun así he visto peticiones en Node que tardan 40 segundos en fallar contra un host que no responde.",
            },
            {
                "role": "assistant",
                "content": r"""`timeout` no es «tiempo total de la petición» en todos los entornos, y esa es la causa de tus 40 segundos.

**Qué hace `timeout` según el adaptador:**

| Entorno | Adaptador | Qué mide `timeout` |
|---|---|---|
| Navegador | `xhr` | tiempo total desde el envío hasta recibir la respuesta completa |
| Node | `http` | **inactividad del socket** (`req.setTimeout`): se reinicia cada vez que llega un byte |
| Navegador/Node/edge | `fetch` (opcional desde 1.7) | tiempo total, implementado con `AbortSignal` |

En Node, un host que **acepta la conexión TCP pero no envía nada** sí dispara los 5 s. Pero un host al que no se llega (IP que descarta paquetes, firewall) deja la petición en la fase de conexión, y ahí Axios aún no ha podido fijar el timeout del socket con fiabilidad; el que manda es el del sistema operativo (habitualmente 20-120 s para el `SYN` sin respuesta). Esos son tus 40 segundos. Además, con `timeout` no existe un «timeout de conexión» separado del de respuesta.

**Arreglo: un límite de tiempo total con `AbortSignal.timeout`,** que corta en cualquier fase, sea conexión, cabeceras o cuerpo:

```ts
import axios from 'axios'

export const api = axios.create({
  baseURL: 'https://api.example.com',
  timeout: 5_000,   // mantenlo: cubre la inactividad del socket y es barato
})

export async function getWithDeadline<T>(url: string, totalMs = 8_000): Promise<T> {
  const { data } = await api.get<T>(url, { signal: AbortSignal.timeout(totalMs) })
  return data
}
```

`AbortSignal.timeout` existe en Node 17.3+ y en todos los navegadores actuales. Cuando vence, Axios rechaza con `CanceledError` (`code: 'ERR_CANCELED'`), no con `ECONNABORTED`; si necesitas distinguir «timeout total» de «cancelado por el usuario», mira `signal.reason` (es un `DOMException` con `name === 'TimeoutError'`) o usa controladores distintos.

**Cómo distinguir cada fallo en el `catch`:**

```ts
import axios from 'axios'

try {
  await getWithDeadline('/reports/slow')
} catch (e) {
  if (!axios.isAxiosError(e)) throw e
  switch (e.code) {
    case 'ECONNABORTED':  // timeout de Axios (socket inactivo en Node, total en navegador)
    case 'ETIMEDOUT':     // el mismo caso si activas transitional.clarifyTimeoutError
    case 'ERR_CANCELED':  // AbortSignal: timeout total o cancelación manual
      return retryLater()
    case 'ERR_NETWORK':   // DNS, conexión rechazada, CORS en navegador
      return showOffline()
    default:
      throw e
  }
}
```

`transitional: { clarifyTimeoutError: true }` en la config de la instancia hace que el timeout propio de Axios se reporte como `ETIMEDOUT` en vez de `ECONNABORTED`, que es más honesto; el valor por defecto se mantiene por compatibilidad.

**Si estás en Node y quieres un timeout de conexión de verdad**, configúralo en el agente HTTP, que es quien abre los sockets:

```ts
import { Agent } from 'node:https'

export const api = axios.create({
  baseURL: 'https://api.example.com',
  timeout: 5_000,
  httpsAgent: new Agent({ keepAlive: true, timeout: 3_000 }),   // timeout del socket, incluida la fase de conexión
})
```

Con `keepAlive: true` además reutilizas conexiones entre peticiones, que en un servicio con muchas llamadas salientes reduce la latencia más que cualquier otro ajuste.

Verificación: apunta la instancia a una IP no enrutable (`http://10.255.255.1`) y mide con `console.time`. Con solo `timeout: 5000` verás los 20-40 s; con `AbortSignal.timeout(8_000)` o el agente con `timeout: 3_000`, el rechazo llega a los 8 s o 3 s exactos.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Un compañero me ha marcado esto en la revisión y no entiendo qué tiene de malo:

```ts
async function loadOrder(id: string) {
  try {
    const res = await api.get(`/orders/${id}`)
    return res.data
  } catch (e: any) {
    console.error(e.response.data.message)
    throw new Error(e.response.data.message)
  }
}
```

Dice que «se va a caer con un timeout». A mí me funciona.""",
            },
            {
                "role": "assistant",
                "content": r"""Tiene razón: `e.response` **no existe** cuando no hubo respuesta HTTP, y eso pasa en un timeout, un fallo de red, una cancelación o un error de CORS. En esos casos `e.response.data` lanza `TypeError: Cannot read properties of undefined (reading 'data')` dentro del `catch`, y lo que sale de `loadOrder` es ese `TypeError`, no un error con sentido. Te funciona porque en desarrollo siempre recibes respuesta.

Un `AxiosError` tiene tres formas, y el `catch` tiene que cubrir las tres:

| Situación | `e.response` | `e.request` | `e.code` típico |
|---|---|---|---|
| El servidor respondió con 4xx/5xx | objeto con `status`, `data`, `headers` | sí | `ERR_BAD_REQUEST` (4xx), `ERR_BAD_RESPONSE` (5xx) |
| La petición salió pero no hubo respuesta | `undefined` | sí | `ECONNABORTED`, `ETIMEDOUT`, `ERR_NETWORK`, `ERR_CANCELED` |
| La petición ni se envió (config inválida) | `undefined` | `undefined` | `ERR_BAD_OPTION`, `ERR_INVALID_URL` |

Y el `any` esconde todo esto: con `catch (e: unknown)` TypeScript te habría obligado a comprobar antes de acceder.

**Versión corregida:**

```ts
import axios from 'axios'

export class OrderLoadError extends Error {
  constructor(message: string, public readonly status: number | null, public readonly cause?: unknown) {
    super(message)
    this.name = 'OrderLoadError'
  }
}

interface ApiErrorBody { message?: string }

export async function loadOrder(id: string): Promise<Order> {
  try {
    const { data } = await api.get<Order>(`/orders/${id}`)
    return data
  } catch (e: unknown) {
    if (!axios.isAxiosError<ApiErrorBody>(e)) throw e          // un bug nuestro (p. ej. TypeError): no lo disfraces

    if (e.response) {
      const message = e.response.data?.message ?? `Error ${e.response.status} al cargar el pedido`
      throw new OrderLoadError(message, e.response.status, e)
    }
    if (e.code === 'ERR_CANCELED') throw e                      // la cancelación la gestiona quien canceló
    throw new OrderLoadError('No se pudo contactar con el servidor', null, e)
  }
}
```

Qué cambia y por qué:

- **`axios.isAxiosError<ApiErrorBody>(e)`** es un *type guard*: dentro del `if`, `e` es `AxiosError<ApiErrorBody>` y `e.response?.data?.message` está tipado. Sin el genérico, `data` es `any`.
- **`e.response.data?.message` con `?.`**: un 502 de un proxy suele traer HTML, no JSON; `data` es un string y `.message` es `undefined`. El `??` pone un mensaje útil en vez de `undefined`.
- **Relanzar lo que no es `AxiosError`.** Un `TypeError` por un bug en tu código debe llegar tal cual al monitor de errores, no convertido en «no se pudo cargar el pedido».
- **La cancelación se deja pasar.** Si un componente aborta al desmontar, no quieres loguear ni mostrar un error.
- **`cause`** conserva el error original para Sentry o para los logs, sin exponerlo a la UI.

Sobre el `console.error`: quítalo del `catch`. Quien llama decide si lo registra; si cada capa loguea, el mismo fallo aparece cuatro veces.

Verificación, dos tests con msw: uno con `HttpResponse.error()` (fallo de red) y otro con `delay('infinite')` más `timeout: 50` en la instancia. Tu versión original lanza `TypeError` en ambos; la corregida lanza `OrderLoadError` con `status: null`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero tipar bien un cliente Axios en TypeScript: opciones propias por petición (`skipAuth`, `retry`) sin castear, y que `api.get<User>` no sea una mentira. ¿Cómo lo haces tú?",
            },
            {
                "role": "assistant",
                "content": r"""Dos técnicas: **ampliación de módulo** para que `skipAuth` y `retry` sean campos legítimos de la config, y **validación con zod en el borde** para que el tipo de respuesta sea verdad en tiempo de ejecución y no un `as`.

**1. Opciones propias sin castear.** Axios expone `AxiosRequestConfig` como interfaz; TypeScript permite extenderla desde tu código:

```ts
// src/api/axios.d.ts  (o al principio de client.ts; debe estar incluido en tsconfig)
import 'axios'

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** No añadir Authorization (login, endpoints públicos). */
    skipAuth?: boolean
    /** Reintentos ante fallos transitorios; 0 desactiva. */
    retry?: number
  }
}
```

`InternalAxiosRequestConfig` (lo que ven los interceptores) extiende `AxiosRequestConfig`, así que los campos llegan tipados sin más:

```ts
api.interceptors.request.use((config) => {
  if (!config.skipAuth) {
    const token = getAccessToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

await api.post('/auth/login', credentials, { skipAuth: true })   // compila; sin el d.ts, error TS2353
```

**2. Respuestas validadas.** `api.get<User>()` solo anota; si el backend cambia `email` por `emailAddress`, el tipo sigue diciendo `email` y el bug aparece lejos. Un envoltorio que recibe el esquema cierra el hueco:

```ts
// src/api/typed.ts
import type { AxiosRequestConfig } from 'axios'
import { z } from 'zod'
import { api } from './client'

export class ResponseShapeError extends Error {
  constructor(public readonly url: string, public readonly issues: z.ZodIssue[]) {
    super(`Respuesta de ${url} con forma inesperada: ${issues.map((i) => i.path.join('.') + ' ' + i.message).join('; ')}`)
    this.name = 'ResponseShapeError'
  }
}

async function parse<T>(url: string, schema: z.ZodType<T>, data: unknown): Promise<T> {
  const result = schema.safeParse(data)
  if (!result.success) throw new ResponseShapeError(url, result.error.issues)
  return result.data
}

export const typed = {
  async get<T>(url: string, schema: z.ZodType<T>, config?: AxiosRequestConfig): Promise<T> {
    const res = await api.get<unknown>(url, config)
    return parse(url, schema, res.data)
  },
  async post<T>(url: string, body: unknown, schema: z.ZodType<T>, config?: AxiosRequestConfig): Promise<T> {
    const res = await api.post<unknown>(url, body, config)
    return parse(url, schema, res.data)
  },
}
```

Y los tipos salen del esquema, de modo que hay **una sola fuente de verdad**:

```ts
// src/api/users.ts
import { z } from 'zod'
import { typed } from './typed'

export const UserSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  email: z.string().email(),
  createdAt: z.coerce.date(),      // el JSON trae string; aquí ya es Date
})
export type User = z.infer<typeof UserSchema>

export const getUser = (id: number) => typed.get(`/users/${id}`, UserSchema)
export const listUsers = () => typed.get('/users', z.array(UserSchema))
export const createUser = (input: Omit<User, 'id' | 'createdAt'>) => typed.post('/users', input, UserSchema)
```

`getUser` devuelve `Promise<User>` sin que nadie escriba `<User>` ni `as User`; `createdAt` es un `Date` real gracias a `coerce`.

**Trade-offs, en voz alta:**

- La validación cuesta microsegundos por respuesta; en una lista de 10 000 filas se nota (milisegundos). Para esos endpoints puedes validar solo en desarrollo (`import.meta.env.DEV ? schema.parse(data) : data as T`) y mantener el contrato con tests de contrato.
- Si el backend es tuyo y ya genera tipos desde OpenAPI (`openapi-typescript`), puedes saltarte zod y usar esos tipos con `api.get<paths['/users/{id}']['get']['responses']['200']['content']['application/json']>`; es verboso, pero no hay duplicación. Con un backend ajeno o cambiante, zod.

Verificación: un test con msw que devuelva `{ id: '7', name: 'Ana' }` (id como string, sin email). `getUser(7)` debe rechazar con `ResponseShapeError` cuyo mensaje nombre `id` y `email`; con `api.get<User>` a secas, ese test «pasa» y el error aparece en un componente.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito subir archivos grandes (hasta 500 MB) con Axios desde React y mostrar una barra de progreso. ¿Cómo se hace y qué hay que tener en cuenta?",
            },
            {
                "role": "assistant",
                "content": r"""Envía un `FormData` y pasa `onUploadProgress`; Axios te da `loaded`, `total` y, desde 1.x, `progress`, `rate` y `estimated` ya calculados. Lo importante con 500 MB es **no** poner el `Content-Type` a mano, soportar cancelación y no leer el archivo en memoria.

```ts
// src/api/upload.ts
import axios, { type AxiosProgressEvent } from 'axios'
import { api } from './client'

export interface UploadProgress {
  percent: number        // 0-100
  bytesPerSecond?: number
  secondsLeft?: number
}

export async function uploadFile(
  file: File,
  onProgress: (p: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<{ id: string }> {
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('kind', 'invoice')

  const { data } = await api.post<{ id: string }>('/files', form, {
    signal,
    timeout: 0,                       // el timeout por inactividad de 10 s de la instancia mataría subidas lentas
    maxBodyLength: Infinity,          // solo relevante en Node; en navegador se ignora
    onUploadProgress: (e: AxiosProgressEvent) => {
      onProgress({
        percent: e.total ? Math.round((e.loaded / e.total) * 100) : 0,
        bytesPerSecond: e.rate,
        secondsLeft: e.estimated,
      })
    },
  })
  return data
}
```

```tsx
// src/components/UploadButton.tsx
import axios from 'axios'
import { useRef, useState } from 'react'
import { uploadFile, type UploadProgress } from '../api/upload'

export function UploadButton() {
  const [progress, setProgress] = useState<UploadProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    controller.current = new AbortController()
    setError(null)
    try {
      await uploadFile(file, setProgress, controller.current.signal)
      setProgress({ percent: 100 })
    } catch (err) {
      if (!axios.isCancel(err)) setError('La subida falló; inténtalo de nuevo')
      setProgress(null)
    }
  }

  return (
    <div>
      <input type="file" onChange={onChange} aria-label="Elegir archivo" />
      {progress && (
        <>
          <progress value={progress.percent} max={100} />
          <span>{progress.percent}%{progress.secondsLeft ? ` · ${Math.ceil(progress.secondsLeft)} s` : ''}</span>
          <button type="button" onClick={() => controller.current?.abort()}>Cancelar</button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
```

Puntos que marcan la diferencia con archivos grandes:

- **No fijes `Content-Type: multipart/form-data`.** El navegador lo añade con el `boundary` correcto; si lo pones tú sin boundary, el servidor no puede parsear el cuerpo. Es el error número uno en subidas con Axios.
- **`timeout: 0` en esta llamada.** El `timeout` de la instancia (10 s) está pensado para JSON; una subida de 500 MB por una conexión lenta lo supera con facilidad. La cancelación manual con `AbortSignal` sigue disponible.
- **`e.total` puede ser `undefined`** si el navegador no conoce el tamaño (raro con `File`, habitual con streams); de ahí el `? :`.
- **El progreso mide bytes enviados, no procesados.** Llegará al 100 % y la petición seguirá pendiente mientras el servidor guarda el archivo. Muestra «Procesando» entre el 100 % y la respuesta, o el usuario pensará que se colgó.
- Para archivos de gigabytes o redes inestables, el enfoque correcto es **subida por partes** (S3 multipart, tus, o trozos con `file.slice()` y reanudación); este código es el límite razonable de una subida simple.

Verificación: en DevTools, pestaña Network con *throttling* «Slow 3G», sube un archivo de 5 MB. La barra debe avanzar de forma continua, «Cancelar» debe dejar la petición en `(canceled)` sin mostrar error, y `Content-Type` de la petición debe contener `boundary=`.""",
            },
            {
                "role": "user",
                "content": "¿Y lo mismo desde Node? Tengo un script que sube backups a nuestra API y con `fs.readFileSync` se me va la memoria.",
            },
            {
                "role": "assistant",
                "content": r"""En Node no cargues el archivo: entrégale a Axios un **stream** o un `Blob` perezoso y deja que el adaptador `http` lo envíe por trozos. `readFileSync` de 500 MB mete 500 MB en el heap (y Axios puede copiarlo al construir el cuerpo), de ahí el `heap out of memory`.

Dos opciones, según tu versión de Node:

**Node 20+: `fs.openAsBlob` + `FormData` nativo.** Es la forma más parecida al navegador y usa el mismo código de progreso:

```ts
// scripts/upload-backup.ts
import { openAsBlob } from 'node:fs'
import { stat } from 'node:fs/promises'
import { basename } from 'node:path'
import axios from 'axios'

const api = axios.create({ baseURL: process.env.API_URL, timeout: 0, maxBodyLength: Infinity })

export async function uploadBackup(path: string): Promise<{ id: string }> {
  const { size } = await stat(path)
  const form = new FormData()
  form.append('file', await openAsBlob(path), basename(path))   // Blob respaldado por el archivo: no se lee a memoria

  const { data } = await api.post<{ id: string }>('/backups', form, {
    headers: { Authorization: `Bearer ${process.env.API_TOKEN}` },
    onUploadProgress: (e) => {
      process.stdout.write(`\r${Math.round((e.loaded / size) * 100)}%`)
    },
  })
  process.stdout.write('\n')
  return data
}
```

`onUploadProgress` funciona en el adaptador `http` desde Axios 1.7; con versiones anteriores el callback nunca se llama en Node (no falla, simplemente no hay progreso).

**Node 18 o cuerpo que no es multipart (subida «cruda»):** pasa un `ReadStream` como cuerpo y fija tú la longitud y el tipo:

```ts
import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'

export async function uploadRaw(path: string) {
  const { size } = await stat(path)
  const { data } = await api.put<{ id: string }>(`/backups/${encodeURIComponent(basename(path))}`, createReadStream(path), {
    headers: {
      'Content-Type': 'application/octet-stream',
      'Content-Length': size,            // sin esto Axios envía chunked; muchos servidores lo aceptan, S3 no
    },
  })
  return data
}
```

Diferencias con el navegador que conviene saber:

- **`maxBodyLength` y `maxContentLength`** existen solo en Node y por defecto limitan a 10 MB las subidas y respuestas; con archivos grandes, `Infinity` en ambas o un límite explícito.
- **Proxies**: en Node, Axios respeta `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` del entorno; en el navegador no aplica.
- **Reintentos**: un stream ya consumido no se puede reenviar. Si envuelves esto en reintentos, construye el `FormData`/`ReadStream` **dentro** de la función que se reintenta, no fuera.
- **Memoria esperada**: con cualquiera de las dos variantes, el proceso se queda en ~60-80 MB de RSS independientemente del tamaño del archivo. Mídelo con `process.memoryUsage().rss` antes y después; si crece con el archivo, algo lo está materializando (un interceptor que hace `JSON.stringify(config.data)` para log es el culpable habitual).

Verificación: `node --max-old-space-size=128 scripts/upload-backup.js backup-500MB.tar.gz`. Con 128 MB de heap, la versión con `readFileSync` muere; estas dos terminan.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Honest take: in 2025+ is there still a reason to add Axios to a new TypeScript project, or is `fetch` enough? I keep getting both answers.",
            },
            {
                "role": "assistant",
                "content": r"""Both answers are right for different projects. `fetch` is enough when you need a handful of calls and are willing to write a 40-line wrapper; Axios earns its 13 KB when you need interceptors, uniform errors, progress or Node/browser parity across a large codebase. Here is the actual feature gap, not the folklore.

| Capability | `fetch` (browser, Node 18+, edge) | Axios 1.x |
|---|---|---|
| Throws on 4xx/5xx | no: you check `res.ok` | yes (`validateStatus` to change) |
| JSON request/response | manual `JSON.stringify` + `res.json()` | automatic |
| Timeout | `AbortSignal.timeout(ms)` | `timeout` option (semantics differ by adapter) + `signal` |
| Cancellation | `AbortController` | same `AbortController` |
| Interceptors (auth, refresh, logging) | none: wrap it yourself | built in, per instance |
| Upload/download progress | download via streams; upload: no (in browsers) | `onUploadProgress` / `onDownloadProgress` |
| Query params serialization | `URLSearchParams` by hand | `params` option, arrays/nesting configurable |
| Response streaming | yes, `res.body` is a `ReadableStream` | Node only (`responseType: 'stream'`); not in browsers |
| Edge runtimes (Workers, Vercel Edge) | native | works via the `fetch` adapter (1.7+) |
| Next.js request caching/dedup | yes, Next patches `fetch` | no |
| Bundle | 0 | ~13 KB gzipped |
| XSRF cookie → header | manual | built in (`withXSRFToken`) |

**What a `fetch` wrapper actually costs.** The minimum that most teams end up writing:

```ts
export class HttpError extends Error {
  constructor(public readonly status: number, public readonly body: unknown, message?: string) {
    super(message ?? `HTTP ${status}`)
    this.name = 'HttpError'
  }
}

export async function http<T>(input: string, init: RequestInit & { json?: unknown; timeoutMs?: number } = {}): Promise<T> {
  const { json, timeoutMs = 10_000, headers, ...rest } = init
  const res = await fetch(new URL(input, import.meta.env.VITE_API_URL), {
    ...rest,
    headers: { Accept: 'application/json', ...(json !== undefined && { 'Content-Type': 'application/json' }), ...headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    signal: rest.signal ?? AbortSignal.timeout(timeoutMs),
  })
  const body = res.headers.get('content-type')?.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) throw new HttpError(res.status, body)
  return body as T
}
```

That covers base URL, JSON, timeout and errors. It does **not** cover token refresh with single-flight, retries, progress, or a plug-in point for logging. Each of those is another 20-60 lines you own and test.

**Decision rule I use:**

- **Pick `fetch`** when: Next.js App Router (you want its cache), edge/Workers, a small client, streaming responses (SSE, LLM tokens), or when a data layer like TanStack Query already handles retries and cancellation and you only need the transport.
- **Pick Axios** when: a large SPA or a Node service with many outbound calls, you need request/response interceptors (auth refresh, tenant headers, tracing ids), upload progress, or you want identical behaviour in Node and browsers without thinking about undici versus the DOM.
- **Do not pick Axios for**: streaming in the browser, Next.js server components, or because "it handles errors"; the wrapper above handles them in 15 lines.

Two things people get wrong in both camps: `fetch` does not retry either, and Axios is not "legacy": it has had a `fetch` adapter since 1.7, native `AbortSignal` support and no XHR requirement.

Sanity check for your own project: count the places that would need an interceptor (auth, refresh, correlation id, error normalisation, metrics). Zero or one: `fetch` plus the wrapper. Three or more: Axios, and put all of them in one `client.ts`.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 11-15: fetch moderno (4xx/5xx no lanzan, Request/Response/Headers, streams, caché, Node/undici)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": "Eres un mentor paciente para principiantes; explica sin jerga innecesaria."},
            {
                "role": "user",
                "content": r"""No entiendo por qué mi `catch` no atrapa el 404. Si pido un usuario que no existe, en vez de mostrar el error se me pinta un usuario vacío.

```js
async function loadUser(id) {
  try {
    const res = await fetch('/api/users/' + id)
    const user = await res.json()
    setUser(user)
  } catch (e) {
    setError('No se pudo cargar el usuario')
  }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""`fetch` solo lanza un error cuando **no consigue hablar con el servidor** (sin red, DNS que falla, petición cancelada). Si el servidor contesta, aunque conteste «404 no encontrado», para `fetch` eso es una respuesta válida: la promesa se resuelve y tu código sigue como si todo hubiera ido bien.

Lo que pasa en tu función con un 404:

1. `fetch` devuelve un `res` con `res.status === 404` y `res.ok === false`. No hay excepción.
2. `res.json()` lee el cuerpo. Si tu API devuelve `{ "message": "not found" }`, `user` vale eso.
3. `setUser({ message: 'not found' })`: el componente recibe un objeto sin `name` ni `email` y pinta un usuario vacío.

El `catch` nunca se ejecuta porque nada ha fallado desde el punto de vista de `fetch`.

**Arreglo: comprobar `res.ok` y lanzar tú el error.**

```js
async function loadUser(id) {
  try {
    const res = await fetch(`/api/users/${id}`)
    if (!res.ok) {
      // res.ok es true solo para códigos 200-299
      throw new Error(`Error ${res.status} al cargar el usuario`)
    }
    const user = await res.json()
    setUser(user)
  } catch (e) {
    setError(e.message)
  }
}
```

Ahora el 404 entra en el `catch` con el mensaje «Error 404 al cargar el usuario», y un fallo de red entra con el mensaje que genera el navegador (`Failed to fetch`).

Si quieres mostrar mensajes distintos según el caso, mira el código antes de lanzar:

```js
if (res.status === 404) throw new Error('Ese usuario no existe')
if (res.status === 401) throw new Error('Tienes que iniciar sesión')
if (!res.ok) throw new Error(`El servidor respondió ${res.status}`)
```

Dos detalles más para que no te pille después:

- **`res.json()` también puede fallar** si el cuerpo no es JSON (por ejemplo, una página HTML de error de un proxy). Ese sí lanza, y lo atrapa tu `catch`. Comprobar `res.ok` antes evita intentar parsear cuerpos de error raros.
- **Esta regla es solo de `fetch`.** Librerías como Axios sí lanzan en 4xx/5xx. Si cambias de una a otra, revisa todos los `catch`.

Prueba rápida en la consola del navegador:

```js
const r = await fetch('/api/users/999999')
console.log(r.ok, r.status)   // false 404  (y no ha saltado ningún error)
```

Si ves eso, ya entiendes el comportamiento, y el `if (!res.ok)` es todo lo que te faltaba.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "I keep seeing `new Request()`, `Response.json()`, and `Headers` in Cloudflare Workers and Next.js route handler examples. Can you explain in Spanish (I'm practising) what these objects are and why they matter beyond calling `fetch(url)`?",
            },
            {
                "role": "assistant",
                "content": r"""Son los **objetos del estándar Fetch** (`Request`, `Response`, `Headers`), y lo importante es que se usan en los dos sentidos: con `fetch` los envías y recibes como cliente, pero en Workers, Deno, Bun, Next.js (route handlers y middleware) o Hono, tu **servidor** recibe un `Request` y devuelve un `Response`. Aprender estos tres objetos te sirve para el cliente y para el servidor a la vez.

**`Request`: una petición como valor.** Puedes construirla, pasarla, clonarla e inspeccionarla antes de enviarla o de responderla:

```ts
const req = new Request('https://api.example.com/users', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'Ana' }),
})

req.method        // 'POST'
req.url           // 'https://api.example.com/users'
new URL(req.url).searchParams.get('page')   // así se leen los query params
await req.json()  // lee el cuerpo (una sola vez)
```

**`Headers`: un mapa de cabeceras insensible a mayúsculas**, con métodos en vez de un objeto plano:

```ts
const headers = new Headers({ 'content-type': 'application/json' })
headers.get('Content-Type')           // 'application/json' (da igual la capitalización)
headers.set('Authorization', 'Bearer x')
headers.append('Vary', 'Origin')      // append acumula; set sustituye
for (const [name, value] of headers) console.log(name, value)
```

**`Response`: la respuesta como valor**, con atajos para los casos comunes:

```ts
Response.json({ id: 1 })                                  // 200 con Content-Type: application/json
Response.json({ error: 'not found' }, { status: 404 })
Response.redirect('https://example.com/login', 302)
new Response('texto plano', { headers: { 'Content-Type': 'text/plain' } })
new Response(null, { status: 204 })
```

**Dónde los usas como servidor.** Un route handler de Next.js 15 y un Worker son, en el fondo, la misma función `(Request) => Response`:

```ts
// app/api/users/route.ts (Next.js 15)
export async function POST(request: Request) {
  const body = await request.json()
  if (typeof body.name !== 'string') {
    return Response.json({ error: 'name es obligatorio' }, { status: 400 })
  }
  const user = await db.users.create(body)
  return Response.json(user, { status: 201, headers: { Location: `/api/users/${user.id}` } })
}
```

```ts
// Cloudflare Worker
export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url)
    if (url.pathname === '/health') return Response.json({ ok: true })
    return new Response('Not found', { status: 404 })
  },
}
```

**Tres reglas que explican la mayoría de errores:**

1. **El cuerpo se lee una sola vez.** Después de `await req.json()`, `req.bodyUsed` es `true` y un segundo `json()` lanza `TypeError: Body is unusable`. Si necesitas leerlo dos veces (log + parseo, o reenviar la petición a otro servidor), haz `req.clone()` **antes** de leer.
2. **`Request` y `Response` son prácticamente inmutables.** Para cambiar una cabecera de una respuesta que te llega, creas otra: `new Response(res.body, { ...res, headers: nuevasHeaders })`. Es la base del patrón *proxy* en Workers y del middleware de Next.js.
3. **Un `Response` que creas tú no tiene `url`** (`''`) y **un `Request` sin `body` lo tiene en `null`**; no asumas que todos los campos vienen rellenos.

**Por qué importa de verdad:** puedes probar tu handler **sin servidor**: `await POST(new Request('http://t/api/users', { method: 'POST', body: JSON.stringify({ name: 'Ana' }) }))` y afirmar sobre `res.status` y `await res.json()`. Y el mismo handler corre en Node, Workers, Deno o Bun sin cambios, porque solo depende del estándar.

Comprobación de que lo has entendido: predice qué imprime esto antes de ejecutarlo.

```ts
const res = Response.json({ a: 1 })
await res.json()
console.log(res.bodyUsed, res.headers.get('content-type'))   // true 'application/json'
```""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un endpoint que devuelve la respuesta de un modelo de lenguaje por streaming (SSE, `data: {...}` por línea). Con `fetch` + `res.json()` obviamente no funciona. ¿Cómo leo el stream e imprimo los tokens según llegan, con cancelación?",
            },
            {
                "role": "assistant",
                "content": r"""Lee `res.body` como `ReadableStream`, decodifica los bytes a texto de forma **incremental** y corta por el separador de eventos SSE (`\n\n`). El detalle que casi todos fallan: un chunk de red puede partir un evento por la mitad, así que necesitas un búfer entre lecturas.

```ts
// src/api/stream.ts
export interface SseEvent {
  event?: string
  data: string
}

/** Lee un cuerpo text/event-stream y emite cada evento completo. */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })   // stream: true conserva bytes UTF-8 incompletos entre chunks

      let separator: number
      while ((separator = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, separator)
        buffer = buffer.slice(separator + 2)
        const event = parseEvent(raw)
        if (event) yield event
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseEvent(raw: string): SseEvent | null {
  let event: string | undefined
  const data: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith(':')) continue                     // comentario / keep-alive
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  return data.length ? { event, data: data.join('\n') } : null
}
```

Y el consumidor, con cancelación y manejo de errores:

```ts
// src/api/chat.ts
import { readSse } from './stream'

export async function streamCompletion(
  prompt: string,
  onToken: (text: string) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ prompt }),
    signal,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  if (!res.body) throw new Error('La respuesta no tiene cuerpo')

  for await (const event of readSse(res.body)) {
    if (event.data === '[DONE]') return
    const chunk = JSON.parse(event.data) as { delta?: string; error?: string }
    if (chunk.error) throw new Error(chunk.error)
    if (chunk.delta) onToken(chunk.delta)
  }
}
```

```ts
// uso
const controller = new AbortController()
stopButton.onclick = () => controller.abort()

try {
  await streamCompletion('Explica los monzones', (t) => output.append(t), controller.signal)
} catch (e) {
  if (e instanceof DOMException && e.name === 'AbortError') return   // el usuario pulsó "Parar"
  throw e
}
```

Por qué está hecho así:

- **`decoder.decode(value, { stream: true })`**: un carácter como «ñ» ocupa dos bytes y puede llegar partido entre dos chunks; sin `stream: true` verías `�`.
- **Búfer con `indexOf('\n\n')`** en bucle: un chunk puede traer cero, uno o varios eventos completos más un trozo. Se procesan todos los completos y el resto espera al siguiente `read()`.
- **`signal` en `fetch`**: al abortar, el `reader.read()` pendiente rechaza con `AbortError`, el `finally` libera el lector y el navegador cierra la conexión. No hace falta nada más para cancelar.
- **`[DONE]`** es la convención de OpenAI y compatibles; si tu backend marca el final de otra forma (un `event: end`), cambia esa línea.

Alternativas según el entorno:

- Node 18+, Deno y Chrome 124+ permiten `for await (const chunk of res.body)` directamente (iteración asíncrona del `ReadableStream`); Safari no, de ahí `getReader()`.
- Si no necesitas `POST` ni cabeceras personalizadas, `EventSource` hace el parseo SSE por ti y reconecta solo, pero solo soporta `GET` y no permite `Authorization`.

Comprobación: alimenta `readSse` con un stream artificial que entregue `'data: {"delta":"ho'` y `'la"}\n\ndata: [DONE]\n\n'` en dos chunks (`new ReadableStream({ start(c) { c.enqueue(enc.encode(a)); c.enqueue(enc.encode(b)); c.close() } })`). Debe producir exactamente dos eventos, el primero con `delta: 'hola'`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿`fetch` cachea? En mi SPA, después de editar un perfil, `GET /api/profile` sigue devolviendo los datos viejos durante un rato aunque el backend ya tiene los nuevos. En la pestaña Network aparece «(from disk cache)».",
            },
            {
                "role": "assistant",
                "content": r"""`fetch` no cachea por sí mismo: usa la **caché HTTP del navegador**, igual que una imagen o un script. Y ese «(from disk cache)» te dice exactamente qué pasa: el navegador decidió que la respuesta de `/api/profile` seguía fresca y ni siquiera preguntó al servidor.

**Por qué la considera fresca.** Dos posibilidades:

1. El servidor envía `Cache-Control: max-age=N` (o `Expires`) en la respuesta de `/api/profile`.
2. El servidor **no envía nada** de `Cache-Control` pero sí `Last-Modified`. Entonces el navegador aplica la *heurística*: considera la respuesta válida durante el 10 % del tiempo transcurrido desde `Last-Modified`. Es el caso típico de APIs detrás de nginx o de un framework que añade `Last-Modified` sin querer.

Compruébalo en Network → cabeceras de respuesta de `/api/profile`.

**Arreglo correcto: en el servidor.** Una API que devuelve datos del usuario debe decir explícitamente que no se almacene:

```
Cache-Control: no-store
```

o, si quieres permitir revalidación con `ETag` (ahorra ancho de banda con respuestas 304):

```
Cache-Control: private, no-cache
ETag: "a1b2c3"
```

`no-cache` no significa «no cachear»: significa «guarda, pero pregunta siempre al servidor antes de usar». `no-store` es «no guardes nada».

**Paliativo en el cliente** mientras el backend lo corrige, con la opción `cache` de `fetch`:

```ts
const res = await fetch('/api/profile', { cache: 'no-store' })
```

Valores útiles:

| `cache` | Comportamiento |
|---|---|
| `'default'` | reglas HTTP normales (lo que te está pasando) |
| `'no-store'` | ni lee ni escribe la caché |
| `'no-cache'` | revalida siempre con el servidor (usa `ETag`/`If-None-Match`) |
| `'reload'` | ignora la caché al leer, pero guarda la respuesta nueva |
| `'force-cache'` | usa la caché aunque esté caducada |

Lo que **no** hagas: añadir `?t=${Date.now()}` a la URL. Funciona, pero llena la caché de entradas basura, rompe cualquier caché intermedia legítima y esconde el problema de cabeceras, que seguirá afectando a otros clientes.

Verificación: tras el cambio, en Network la petición debe mostrar `200` (o `304` si usas `no-cache` + `ETag`) con tamaño real, nunca «(from disk cache)», y el perfil editado aparece de inmediato.""",
            },
            {
                "role": "user",
                "content": "Vale, en el navegador ya está. Pero tengo el mismo síntoma en Next.js 15: un Server Component hace `fetch` a la misma API y muestra datos viejos hasta que redespliego.",
            },
            {
                "role": "assistant",
                "content": r"""En el servidor de Next.js la caché HTTP del navegador no interviene; lo que te está ocurriendo es otra cosa: **la página se renderizó de forma estática en el build** y se sirve ese HTML hasta el siguiente despliegue. Es la *Full Route Cache*, no una caché de `fetch`.

Primero, lo que cambió en Next 15 para que no mezcles versiones: `fetch` en Server Components **ya no se cachea por defecto** (en 14 era `force-cache`). Así que tu `fetch` sí va al origen en cada render; el problema es que **no hay render**: la ruta es estática porque Next no detectó nada dinámico en ella (ni `cookies()`, ni `headers()`, ni `searchParams`, ni `connection()`), la prerenderizó en el build y la sirve tal cual.

Tienes tres formas de resolverlo, según lo que necesite esa página:

**1. Datos siempre frescos (perfil del usuario: casi seguro este).** Marca la ruta como dinámica:

```ts
// app/profile/page.tsx
export const dynamic = 'force-dynamic'

export default async function ProfilePage() {
  const res = await fetch(`${process.env.API_URL}/profile`, {
    headers: { cookie: (await cookies()).toString() },   // reenvía la sesión del usuario
  })
  const profile = await res.json()
  return <ProfileView profile={profile} />
}
```

En realidad, en cuanto usas `cookies()` la ruta ya es dinámica y el `export const dynamic` sobra; pero dejarlo explícito evita que alguien quite las cookies y la página vuelva a ser estática sin que nadie lo note.

**2. Datos que pueden tener N segundos de retraso (catálogo, estadísticas).** Mantén la ruta estática y revalida por tiempo:

```ts
const res = await fetch(`${process.env.API_URL}/catalog`, { next: { revalidate: 60 } })
```

Next regenera la página en segundo plano como mucho cada 60 s (ISR). La primera petición después del minuto aún ve la versión vieja; la siguiente ya ve la nueva.

**3. Revalidación bajo demanda (cuando el dato cambia por una acción tuya).** Etiqueta el `fetch` y purga la etiqueta al editar:

```ts
// lectura
const res = await fetch(`${process.env.API_URL}/profile/${id}`, { next: { tags: [`profile-${id}`] } })
```

```ts
// app/profile/actions.ts
'use server'
import { revalidateTag } from 'next/cache'

export async function updateProfile(id: string, data: ProfileInput) {
  await fetch(`${process.env.API_URL}/profile/${id}`, { method: 'PUT', body: JSON.stringify(data) })
  revalidateTag(`profile-${id}`)
}
```

Para datos por usuario, la opción 1 es la correcta: cachear un perfil en una página estática es además un riesgo de mostrar el perfil de un usuario a otro.

Cómo saber qué está haciendo cada ruta sin adivinar: `next build` imprime la lista de rutas con `○` (estática) o `ƒ` (dinámica). Tu `/profile` debe salir con `ƒ`. Y en desarrollo, `next dev` siempre renderiza dinámico, por eso ahí «funcionaba».

Verificación: `next build && next start`, edita el perfil desde otra pestaña y recarga `/profile`. Con la opción 1 el cambio aparece en la primera recarga; si sigue apareciendo el viejo, hay otra capa de caché delante (CDN o `Cache-Control` en tu API, que Next sí respeta en `fetch` del lado servidor cuando usas `force-cache`).""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "En Node 22 uso `fetch` para llamar a un servicio interno unas 500 veces por segundo y veo latencias raras (picos de 1-2 s) y de vez en cuando `ECONNRESET`. Con el cliente `http` antiguo y un agente keep-alive no pasaba. ¿Qué configuro?",
            },
            {
                "role": "assistant",
                "content": r"""El `fetch` de Node usa **undici** con un *dispatcher* global cuyos valores por defecto no están pensados para 500 req/s contra un mismo host: no limita conexiones y mantiene las inactivas abiertas más tiempo del que tu servidor las acepta. Los dos síntomas salen de ahí.

**Diagnóstico de cada síntoma:**

- **`ECONNRESET` esporádico**: carrera de keep-alive. Un servidor Node cierra las conexiones inactivas a los 5 s (`server.keepAliveTimeout` por defecto); el cliente undici las considera reutilizables hasta 4 s de inactividad **más** un margen, y a veces envía una petición justo cuando el servidor acaba de cerrar: la petición muere con reset. Con tu agente `http` antiguo pasaba menos por otros valores de tiempo, no porque no existiera.
- **Picos de 1-2 s**: sin límite de conexiones, bajo ráfagas undici abre sockets nuevos (handshake TCP + TLS) en vez de encolar sobre los existentes; además, `connections` ilimitadas pueden saturar el servidor destino, que responde más lento.

**Configuración explícita** (instala `undici` para acceder al `Agent`; la versión del paquete puede ir por delante de la embebida en Node, no importa):

```bash
npm i undici
```

```ts
// src/http/dispatcher.ts
import { Agent, setGlobalDispatcher } from 'undici'

export const internalAgent = new Agent({
  connections: 64,             // sockets por origen; encola el resto en vez de abrir más
  pipelining: 1,               // HTTP/1.1 sin pipelining: lo más compatible
  keepAliveTimeout: 4_000,     // debe ser MENOR que el keepAliveTimeout del servidor (5 s en Node)
  keepAliveMaxTimeout: 10_000,
  headersTimeout: 10_000,      // ms esperando cabeceras (por defecto 300 s)
  bodyTimeout: 10_000,         // ms entre bytes del cuerpo
})

setGlobalDispatcher(internalAgent)   // afecta a todos los fetch del proceso
```

Si prefieres no tocar el global (por ejemplo, un agente por servicio destino), pásalo por petición:

```ts
const res = await fetch('http://inventory.internal/items/42', { dispatcher: internalAgent } as RequestInit)
```

El cast es necesario porque `dispatcher` es una extensión de undici que no está en el tipo `RequestInit` del DOM; en tiempo de ejecución Node la respeta.

**El lado del servidor también cuenta.** Si el servicio interno es tuyo, sube su tolerancia por encima de la del cliente y pon `headersTimeout` por encima de `keepAliveTimeout` (si no, el propio Node puede cerrar conexiones a medio recibir cabeceras):

```ts
const server = app.listen(3000)
server.keepAliveTimeout = 65_000
server.headersTimeout = 66_000
```

Con `keepAliveTimeout` del cliente en 4 s y el del servidor en 65 s, la carrera desaparece: siempre es el cliente quien cierra.

**Qué medir para confirmar:** `internalAgent.stats` (undici 6+) expone por origen `connected`, `free`, `pending`, `running`, `size`. Si `pending` crece durante los picos, 64 conexiones son pocas o el servidor es lento; si `connected` oscila entre 0 y decenas, antes del ajuste estabas abriendo y cerrando sockets sin parar.

Un `ECONNRESET` residual puede seguir ocurriendo (red real); para GET idempotentes añade un reintento inmediato una sola vez cuando `error.cause?.code === 'ECONNRESET'`. En `fetch` de Node, el error de red llega como `TypeError: fetch failed` con la causa real en `error.cause`.""",
            },
            {
                "role": "user",
                "content": "Mejoró mucho. ¿Cómo pongo ahora un timeout por petición que además respete la cancelación del llamador (que me pasa su propio AbortSignal)?",
            },
            {
                "role": "assistant",
                "content": r"""Combina las dos señales con `AbortSignal.any` (Node 20.3+): la petición se aborta cuando cualquiera de ellas se dispare, y puedes saber cuál fue mirando `signal.reason`.

```ts
// src/http/request.ts
export class TimeoutError extends Error {
  constructor(public readonly ms: number) {
    super(`La petición superó ${ms} ms`)
    this.name = 'TimeoutError'
  }
}

export async function fetchWithDeadline(
  input: string | URL,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs = 5_000, signal: callerSignal, ...rest } = init
  const timeout = AbortSignal.timeout(timeoutMs)
  const signal = callerSignal ? AbortSignal.any([callerSignal, timeout]) : timeout

  try {
    return await fetch(input, { ...rest, signal })
  } catch (e) {
    if (timeout.aborted) throw new TimeoutError(timeoutMs)   // venció el plazo
    throw e                                                  // canceló el llamador (AbortError) o fallo de red
  }
}
```

Uso desde un handler que recibe la cancelación del cliente HTTP entrante (en Hono, Fastify o un route handler con `request.signal`):

```ts
export async function getItem(id: string, callerSignal: AbortSignal) {
  const res = await fetchWithDeadline(`http://inventory.internal/items/${id}`, {
    timeoutMs: 2_000,
    signal: callerSignal,
  })
  if (!res.ok) throw new Error(`inventory respondió ${res.status}`)
  return res.json()
}
```

Detalles que importan:

- **`timeout.aborted` como discriminador.** Cuando ambas señales podrían haberse disparado, preguntar a la de timeout es más fiable que inspeccionar `e.name`: `AbortSignal.timeout` aborta con un `DOMException` de nombre `TimeoutError`, pero la combinada propaga el `reason` de la primera que se disparó, y el llamador puede abortar con cualquier motivo.
- **El plazo cubre toda la petición**, incluida la lectura de cabeceras; si después haces `await res.json()` sobre un cuerpo grande, esa lectura también se corta al vencer la señal, porque el cuerpo pertenece a la misma petición.
- **No olvides que la cancelación no es un fallo.** En el `catch` de más arriba, un `AbortError` procedente del llamador debe propagarse tal cual; quien canceló sabe por qué. Solo el timeout se convierte en un error de dominio.
- Si necesitas **Node 18/20.0-20.2** (sin `AbortSignal.any`), crea un `AbortController` propio y reenvía: `callerSignal.addEventListener('abort', () => controller.abort(callerSignal.reason), { once: true })`, más un `setTimeout` que llame a `controller.abort(new TimeoutError(ms))`. Es el mismo comportamiento con cinco líneas más.

Verificación con dos tests y msw (`delay('infinite')` en el handler):

```ts
it('lanza TimeoutError al vencer el plazo', async () => {
  await expect(fetchWithDeadline('http://t/slow', { timeoutMs: 50 })).rejects.toBeInstanceOf(TimeoutError)
})

it('propaga la cancelación del llamador tal cual', async () => {
  const controller = new AbortController()
  const p = fetchWithDeadline('http://t/slow', { timeoutMs: 5_000, signal: controller.signal })
  controller.abort()
  await expect(p).rejects.toMatchObject({ name: 'AbortError' })
})
```

El primero debe terminar en ~50 ms; si tarda 5 s, la señal combinada no está llegando al `fetch` (lo típico: pasar `init.signal` en vez de `signal` en el spread).""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 16-20: tRPC 11 (router/procedures/context/zod, cliente React Query, middleware y roles,
#        errores en cliente, cuándo elegirlo)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero montar tRPC 11 en un proyecto Next.js 15 (App Router) con Prisma. ¿Cómo estructuro el servidor: contexto, router, procedures con validación zod? Un ejemplo con posts me vale.",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro archivos en el servidor: `context.ts` (qué recibe cada procedure), `trpc.ts` (la instancia y los *builders*), `routers/` (los endpoints) y el route handler que lo expone. La regla que mantiene esto sano: **`trpc.ts` se crea una vez y los routers solo importan de ahí**, nunca de `initTRPC` directamente.

```bash
npm i @trpc/server @trpc/client @trpc/tanstack-react-query @tanstack/react-query zod
```

**1. Contexto: lo que toda procedure puede usar.**

```ts
// server/trpc/context.ts
import type { FetchCreateContextFnOptions } from '@trpc/server/adapters/fetch'
import { db } from '@/server/db'
import { getSessionUser } from '@/server/auth'

export async function createContext({ req }: FetchCreateContextFnOptions) {
  const user = await getSessionUser(req.headers.get('cookie'))   // null si no hay sesión
  return { db, user }
}

export type Context = Awaited<ReturnType<typeof createContext>>
```

**2. Instancia y builders.**

```ts
// server/trpc/trpc.ts
import { initTRPC, TRPCError } from '@trpc/server'
import type { Context } from './context'

const t = initTRPC.context<Context>().create()

export const router = t.router
export const publicProcedure = t.procedure

export const protectedProcedure = t.procedure.use(async function requireUser({ ctx, next }) {
  if (!ctx.user) throw new TRPCError({ code: 'UNAUTHORIZED' })
  return next({ ctx: { user: ctx.user } })   // a partir de aquí ctx.user ya no es null para TypeScript
})
```

**3. Router de posts con zod.**

```ts
// server/trpc/routers/post.ts
import { TRPCError } from '@trpc/server'
import { z } from 'zod'
import { protectedProcedure, publicProcedure, router } from '../trpc'

export const postRouter = router({
  list: publicProcedure
    .input(z.object({ limit: z.number().int().min(1).max(50).default(20) }).default({}))
    .query(({ ctx, input }) =>
      ctx.db.post.findMany({ take: input.limit, orderBy: { createdAt: 'desc' } }),
    ),

  byId: publicProcedure
    .input(z.object({ id: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const post = await ctx.db.post.findUnique({ where: { id: input.id } })
      if (!post) throw new TRPCError({ code: 'NOT_FOUND', message: `Post ${input.id} no existe` })
      return post
    }),

  create: protectedProcedure
    .input(z.object({ title: z.string().trim().min(3).max(120), body: z.string().min(1) }))
    .mutation(({ ctx, input }) =>
      ctx.db.post.create({ data: { ...input, authorId: ctx.user.id } }),
    ),
})
```

```ts
// server/trpc/routers/_app.ts
import { router } from '../trpc'
import { postRouter } from './post'

export const appRouter = router({ post: postRouter })
export type AppRouter = typeof appRouter   // el ÚNICO tipo que el cliente importa
```

**4. Exposición en Next.js con el adaptador fetch.**

```ts
// app/api/trpc/[trpc]/route.ts
import { fetchRequestHandler } from '@trpc/server/adapters/fetch'
import { appRouter } from '@/server/trpc/routers/_app'
import { createContext } from '@/server/trpc/context'

const handler = (req: Request) =>
  fetchRequestHandler({
    endpoint: '/api/trpc',
    req,
    router: appRouter,
    createContext,
    onError: ({ path, error }) => {
      if (error.code === 'INTERNAL_SERVER_ERROR') console.error(`tRPC ${path}:`, error.cause ?? error)
    },
  })

export { handler as GET, handler as POST }
```

Decisiones y porqués:

- **`.input(schema)` valida antes de ejecutar**; un input inválido produce `BAD_REQUEST` con el `ZodError` en `error.cause`, sin que escribas un `if`. Y el tipo de `input` dentro del handler sale del esquema.
- **`query` para lecturas, `mutation` para escrituras.** No es cosmético: el cliente envía las queries por `GET` (cacheables, agrupables en lote) y las mutations por `POST`.
- **`next({ ctx })` en el middleware** estrecha el tipo: en `create`, `ctx.user.id` compila sin `!` ni comprobación repetida.
- **Errores de dominio como `TRPCError` con código**: el cliente recibe `NOT_FOUND` con estado HTTP 404 y el mensaje; una excepción cualquiera se convierte en `INTERNAL_SERVER_ERROR` y el mensaje original se oculta en producción.
- **`AppRouter` es un `type`**: el cliente importa solo tipos, así que Prisma y el código de servidor no entran en el bundle del navegador.

Verificación sin cliente, desde la terminal:

```bash
curl 'http://localhost:3000/api/trpc/post.byId?input=%7B%22json%22%3A%7B%22id%22%3A%22no-es-uuid%22%7D%7D'
```

Debe devolver `400` con `"code": "BAD_REQUEST"` y los issues de zod. Un uuid inexistente da `404` con `NOT_FOUND`. Si recibes `405` o `404` del propio Next, revisa el nombre de la carpeta `[trpc]` y el `endpoint`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Ya tengo el router de tRPC 11 funcionando. En el cliente React veo dos formas: `createTRPCReact` y una nueva con TanStack Query «nativo». ¿Cuál uso y cómo hago que al crear un post se refresque la lista?",
            },
            {
                "role": "assistant",
                "content": r"""Usa la integración nueva, `@trpc/tanstack-react-query`: es la recomendada en v11 y, en vez de envolver TanStack Query en hooks propios (`trpc.post.list.useQuery`), te da **opciones tipadas** que pasas a los hooks normales de TanStack (`useQuery(trpc.post.list.queryOptions())`). Ganas todo lo de TanStack sin capa intermedia: `useSuspenseQuery`, `useQueries`, prefetch en el servidor, devtools. `createTRPCReact` sigue funcionando, pero está en mantenimiento.

**1. Proveedor.**

```tsx
// app/providers.tsx
'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createTRPCClient, httpBatchLink } from '@trpc/client'
import { createTRPCContext } from '@trpc/tanstack-react-query'
import { useState } from 'react'
import type { AppRouter } from '@/server/trpc/routers/_app'

export const { TRPCProvider, useTRPC, useTRPCClient } = createTRPCContext<AppRouter>()

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } }))
  const [trpcClient] = useState(() =>
    createTRPCClient<AppRouter>({ links: [httpBatchLink({ url: '/api/trpc' })] }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      <TRPCProvider trpcClient={trpcClient} queryClient={queryClient}>
        {children}
      </TRPCProvider>
    </QueryClientProvider>
  )
}
```

`useState(() => ...)` garantiza un único cliente por montaje; crearlos en el cuerpo del componente haría uno nuevo en cada render y perderías la caché.

**2. Lista y creación, con invalidación.**

```tsx
// app/posts/PostsPanel.tsx
'use client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTRPC } from '@/app/providers'

export function PostsPanel() {
  const trpc = useTRPC()
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')

  const posts = useQuery(trpc.post.list.queryOptions({ limit: 20 }))

  const create = useMutation(
    trpc.post.create.mutationOptions({
      onSuccess: async () => {
        await queryClient.invalidateQueries({ queryKey: trpc.post.list.queryKey() })   // todas las variantes de post.list
        setTitle('')
        setBody('')
      },
    }),
  )

  if (posts.isPending) return <p>Cargando</p>
  if (posts.isError) return <p role="alert">{posts.error.message}</p>

  return (
    <section>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          create.mutate({ title, body })
        }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Título" />
        <textarea value={body} onChange={(e) => setBody(e.target.value)} aria-label="Cuerpo" />
        <button type="submit" disabled={create.isPending}>
          {create.isPending ? 'Publicando' : 'Publicar'}
        </button>
        {create.isError && <p role="alert">{create.error.message}</p>}
      </form>

      <ul>
        {posts.data.map((p) => <li key={p.id}>{p.title}</li>)}
      </ul>
    </section>
  )
}
```

Cómo funciona la invalidación:

- `trpc.post.list.queryKey()` sin input devuelve la clave **prefijo** de esa procedure; `invalidateQueries` con ella marca como obsoletas todas las `post.list` cargadas (con `limit: 20`, `limit: 50`, lo que sea) y las que estén montadas se refrescan solas.
- Para todo el router no hay `queryKey()`; usa `trpc.post.pathFilter()`: `invalidateQueries(trpc.post.pathFilter())` invalida `list`, `byId` y cualquier otra. Útil tras un borrado.
- `await` en `onSuccess` hace que `create.isPending` siga `true` hasta que la lista se ha vuelto a cargar; el botón no se reactiva con la lista vieja en pantalla.

**Tipos sin importar nada del servidor:** `posts.data` es `Post[]` inferido de Prisma a través de `AppRouter`; si cambias el `select` en el servidor, el componente deja de compilar en el campo que ya no existe. Si necesitas el tipo en una prop, `inferRouterOutputs<AppRouter>['post']['list'][number]`.

Si quieres **actualización optimista** (que el post aparezca antes de la respuesta), añade `onMutate` con `queryClient.setQueryData(trpc.post.list.queryKey({ limit: 20 }), ...)` y revierte en `onError`; para una lista de posts normal, invalidar tras el éxito es más simple y suficiente.

Verificación: abre React Query Devtools; tras publicar, la entrada `[["post","list"],{"input":{"limit":20},"type":"query"}]` pasa a *stale* y vuelve a *fresh* con el post nuevo arriba. Y en Network, las queries iniciales viajan **en un solo `GET`** con `?batch=1` gracias a `httpBatchLink`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "En tRPC 11, ¿cómo devuelvo al cliente los errores de validación de zod campo a campo (para pintarlos bajo cada input) sin exponer stack traces ni mensajes internos en producción?",
            },
            {
                "role": "assistant",
                "content": r"""Con `errorFormatter` en `initTRPC.create()`: recibe el `shape` por defecto y el `TRPCError`, y tú decides qué viaja al cliente. Para zod, el error de validación llega como `BAD_REQUEST` con el `ZodError` en `error.cause`; basta con copiar sus `issues` a `shape.data`.

```ts
// server/trpc/trpc.ts
import { initTRPC } from '@trpc/server'
import { ZodError } from 'zod'
import type { Context } from './context'

const t = initTRPC.context<Context>().create({
  errorFormatter({ shape, error }) {
    return {
      ...shape,
      data: {
        ...shape.data,          // conserva code, httpStatus y path; sin esto el cliente pierde error.data.code
        fieldErrors:
          error.code === 'BAD_REQUEST' && error.cause instanceof ZodError
            ? toFieldErrors(error.cause)
            : null,
      },
    }
  },
})

/** { "title": ["Debe tener al menos 3 caracteres"], "body": [...] } */
function toFieldErrors(err: ZodError): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const issue of err.issues) {
    const key = issue.path.join('.') || '_root'
    ;(out[key] ??= []).push(issue.message)
  }
  return out
}

export const router = t.router
export const publicProcedure = t.procedure
```

`toFieldErrors` recorre `issues` en vez de usar `flatten()`, que cambió entre zod 3 y 4; así el mismo código vale con ambas versiones.

**Qué pasa con los stack traces.** tRPC ya hace lo correcto por defecto: `shape.data.stack` solo se incluye cuando `NODE_ENV !== 'production'`, y cualquier excepción que no sea `TRPCError` se envuelve en `INTERNAL_SERVER_ERROR` con el mensaje genérico. Lo que **sí** debes vigilar son tus propios `throw new TRPCError({ message })`: ese `message` viaja tal cual, así que nunca pongas en él el error de Prisma o una ruta de archivo. Si quieres un cinturón extra:

```ts
errorFormatter({ shape, error }) {
  const isInternal = error.code === 'INTERNAL_SERVER_ERROR'
  return {
    ...shape,
    message: isInternal && process.env.NODE_ENV === 'production' ? 'Error interno' : shape.message,
    data: { ...shape.data, fieldErrors: ... },
  }
}
```

**En el cliente**, el formulario lee `error.data.fieldErrors`, que llega tipado porque `AppRouter` incluye el tipo del formatter:

```tsx
const create = useMutation(trpc.post.create.mutationOptions())
const fieldErrors = create.error?.data?.fieldErrors ?? {}

<input aria-invalid={!!fieldErrors.title} aria-describedby="title-error" />
{fieldErrors.title && <p id="title-error" role="alert">{fieldErrors.title.join('. ')}</p>}
```

Y para mensajes en español sin repetirlos en cada esquema, configura el mapa de errores de zod una vez (`z.setErrorMap` en zod 3, `z.config({ customError })` en zod 4) o escribe el mensaje en el esquema: `z.string().min(3, 'Debe tener al menos 3 caracteres')`.

Verificación: `curl -X POST .../api/trpc/post.create -H 'content-type: application/json' -d '{"json":{"title":"ab","body":""}}'` con sesión válida debe devolver `400` con `error.data.fieldErrors.title` y `.body`, y **sin** campo `stack` cuando `NODE_ENV=production`.""",
            },
            {
                "role": "user",
                "content": "Y para permisos: tengo `protectedProcedure`, pero ahora necesito que algunas procedures sean solo para `admin` y otras para `admin` o `editor`. No quiero repetir el `if` en cada una.",
            },
            {
                "role": "assistant",
                "content": r"""Declara los roles permitidos como **metadatos** de la procedure y deja que un único middleware los compruebe. Así cada endpoint dice `.meta({ roles: ['admin'] })` y la lógica vive en un solo sitio.

```ts
// server/trpc/trpc.ts
import { initTRPC, TRPCError } from '@trpc/server'
import type { Context } from './context'

export type Role = 'admin' | 'editor' | 'viewer'

interface Meta {
  roles?: Role[]   // ausente = cualquier usuario autenticado
}

const t = initTRPC.context<Context>().meta<Meta>().create({
  errorFormatter: formatError,   // el de antes
})

export const router = t.router
export const publicProcedure = t.procedure

export const protectedProcedure = t.procedure.use(async function authorize({ ctx, meta, next }) {
  if (!ctx.user) throw new TRPCError({ code: 'UNAUTHORIZED' })
  if (meta?.roles && !meta.roles.includes(ctx.user.role)) {
    throw new TRPCError({ code: 'FORBIDDEN', message: `Requiere rol ${meta.roles.join(' o ')}` })
  }
  return next({ ctx: { user: ctx.user } })
})
```

Y en los routers:

```ts
export const postRouter = router({
  create: protectedProcedure
    .meta({ roles: ['admin', 'editor'] })
    .input(createPostInput)
    .mutation(({ ctx, input }) => ctx.db.post.create({ data: { ...input, authorId: ctx.user.id } })),

  remove: protectedProcedure
    .meta({ roles: ['admin'] })
    .input(z.object({ id: z.string().uuid() }))
    .mutation(({ ctx, input }) => ctx.db.post.delete({ where: { id: input.id } })),

  mine: protectedProcedure   // sin meta: cualquier usuario con sesión
    .query(({ ctx }) => ctx.db.post.findMany({ where: { authorId: ctx.user.id } })),
})
```

Por qué `meta` y no builders por rol (`adminProcedure`, `editorProcedure`):

- Una combinación nueva («admin o editor») no exige un builder nuevo; es un array.
- Los permisos quedan **visibles junto a la procedure**, donde los busca quien lee el router, y puedes recorrer `appRouter._def.procedures` en un test para listar qué expone cada rol.
- El orden de evaluación es fijo: autenticación (`UNAUTHORIZED`) antes que autorización (`FORBIDDEN`), que es la distinción correcta para el cliente: 401 → ir al login; 403 → mostrar «sin permiso».

Cuando el permiso depende del **recurso** (editar solo mis posts), `meta` no basta porque necesita el input; ahí sí va un `if` dentro de la procedure, o un middleware que lea `input` con `.input()` encadenado antes del `.use()`:

```ts
const ownPostProcedure = protectedProcedure
  .input(z.object({ id: z.string().uuid() }))
  .use(async function requireOwnership({ ctx, input, next }) {
    const post = await ctx.db.post.findUnique({ where: { id: input.id }, select: { authorId: true } })
    if (!post) throw new TRPCError({ code: 'NOT_FOUND' })
    if (post.authorId !== ctx.user.id && ctx.user.role !== 'admin') throw new TRPCError({ code: 'FORBIDDEN' })
    return next()
  })

update: ownPostProcedure.input(z.object({ title: z.string().min(3) })).mutation(...)
```

Los inputs encadenados se **fusionan**: `update` recibe `{ id, title }`.

Verificación, un test por capa con `appRouter.createCaller(ctx)`:

```ts
const asViewer = appRouter.createCaller({ db, user: { id: 'u1', role: 'viewer' } })
await expect(asViewer.post.remove({ id })).rejects.toMatchObject({ code: 'FORBIDDEN' })

const anonymous = appRouter.createCaller({ db, user: null })
await expect(anonymous.post.remove({ id })).rejects.toMatchObject({ code: 'UNAUTHORIZED' })
```

`createCaller` ejecuta la procedure con todos sus middlewares sin HTTP, así que estos tests tardan milisegundos.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""tRPC 11 client problem. On the React side `error.data?.code` is always `undefined`, so I can't tell a 404 from a validation error:

```ts
// server/trpc.ts
const t = initTRPC.context<Context>().create({
  errorFormatter({ shape, error }) {
    return {
      ...shape,
      data: { zodError: error.cause instanceof ZodError ? error.cause.flatten() : null },
    }
  },
})
```

```tsx
const user = useQuery(trpc.user.byId.queryOptions({ id }))
if (user.isError) console.log(user.error.data?.code, user.error.message)   // undefined "User not found"
```

The message arrives, so the request works. What am I missing?""",
            },
            {
                "role": "assistant",
                "content": r"""Your `errorFormatter` **replaces** `shape.data` instead of extending it. The default `data` carries `code`, `httpStatus`, `path` and (in development) `stack`; your return value drops all of them and keeps only `zodError`. That is why `message` still arrives (it lives on `shape`, which you spread) while `data.code` is gone.

The fix is one spread:

```ts
const t = initTRPC.context<Context>().create({
  errorFormatter({ shape, error }) {
    return {
      ...shape,
      data: {
        ...shape.data,   // keep code, httpStatus, path, stack
        zodError: error.code === 'BAD_REQUEST' && error.cause instanceof ZodError ? error.cause.flatten() : null,
      },
    }
  },
})
```

Adding the `error.code === 'BAD_REQUEST'` guard matters too: a `ZodError` thrown from inside a resolver (say, you validate a third-party response with zod and it fails) would otherwise be reported as a client validation problem when it is really a server bug.

With that in place, the client gets a typed discriminator:

```tsx
import { TRPCClientError } from '@trpc/client'
import type { AppRouter } from '@/server/trpc/routers/_app'

const user = useQuery(trpc.user.byId.queryOptions({ id }))

if (user.isError) {
  switch (user.error.data?.code) {
    case 'NOT_FOUND':
      return <NotFound />
    case 'BAD_REQUEST':
      return <p role="alert">Invalid id: {JSON.stringify(user.error.data.zodError?.fieldErrors)}</p>
    case 'UNAUTHORIZED':
      redirectToLogin()
      return null
    default:
      return <p role="alert">Something went wrong</p>
  }
}
```

`user.error` is typed as `TRPCClientErrorLike<AppRouter>`, so `data.code` is the union of tRPC error codes and `data.zodError` has the shape your formatter returns; no casting. Outside React Query (a plain `trpcClient.user.byId.query()` in a `try/catch`) narrow with `e instanceof TRPCClientError` first, because a network failure there is a `TRPCClientError` too, with `data` undefined and `cause` set to the underlying `TypeError`.

Two related things worth fixing while you are there:

1. **Do not retry client errors.** TanStack Query retries failed queries three times by default; a `NOT_FOUND` will be requested four times before you see it. Set this once on the `QueryClient`:

```ts
new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        const status = (error as TRPCClientErrorLike<AppRouter>).data?.httpStatus ?? 500
        return status >= 500 && failureCount < 2
      },
    },
  },
})
```

2. **Batching and errors.** With `httpBatchLink`, several queries share one HTTP request, but errors are per procedure: one `NOT_FOUND` does not fail the siblings in the batch. If you ever see every query in a batch failing together, the whole request failed (auth middleware returning 401 for the batch, or a body-size limit), and `data.httpStatus` will be the same on all of them.

Check it: hit the route handler directly and look at the JSON.

```bash
curl 'http://localhost:3000/api/trpc/user.byId?input=%7B%22json%22%3A%7B%22id%22%3A%22missing%22%7D%7D'
```

Before the fix, `error.data` is `{ "zodError": null }`; after it, `{ "code": "NOT_FOUND", "httpStatus": 404, "path": "user.byId", "zodError": null }`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto de software; responde con trade-offs concretos."},
            {
                "role": "user",
                "content": "Monorepo TypeScript: una app Next.js, en seis meses una app iOS nativa (Swift) y el año que viene integraciones de partners. El equipo quiere tRPC porque «es todo tipado». ¿tRPC, REST con OpenAPI o GraphQL?",
            },
            {
                "role": "assistant",
                "content": r"""tRPC para la frontera **Next.js ↔ servidor** y una API REST documentada con OpenAPI para **iOS y partners**, compartiendo la capa de servicios por debajo. No es una respuesta salomónica: son dos problemas distintos y cada herramienta resuelve uno.

**Por qué tRPC solo para el cliente TypeScript propio.** Su ventaja (tipos inferidos del router sin generar nada) existe únicamente cuando el cliente **compila contra el mismo código**. Swift no puede; un partner tampoco. Lo que para Next.js es «cero fricción» para iOS sería un protocolo privado (`?input={"json":...}`, batching, códigos de error propios) sin contrato ni documentación. Puedes exponerlo a OpenAPI con `trpc-to-openapi`, pero entonces estás escribiendo anotaciones REST en procedures tRPC: lo peor de ambos.

**Por qué REST + OpenAPI para los demás.** Un contrato que Swift, Kotlin, Python y un partner que no conoces consumen con generadores estándar (`openapi-generator`, `swift-openapi-generator`), cacheable por HTTP, versionable, y que un revisor de seguridad externo entiende. Con un framework que genere la especificación desde el código (`@hono/zod-openapi`, `fastify-type-provider-zod` o NestJS con `@nestjs/swagger`), el coste de mantenerlo es cercano a cero y los tipos del cliente web también pueden salir de ahí (`openapi-typescript` + `openapi-fetch`) si algún día quieres retirar tRPC.

**Por qué no GraphQL aquí.** Resuelve «muchos clientes con necesidades de datos distintas sobre un grafo grande». Tienes un cliente hoy y dos el año que viene, con datos probablemente similares. Pagarías esquema, resolvers, N+1, caché normalizada en cliente y control de complejidad de queries para partners, sin el problema que lo justifica. Si en dos años tienes cinco clientes pidiendo formas distintas de los mismos datos, reconsidéralo.

| Criterio | tRPC | REST + OpenAPI | GraphQL |
|---|---|---|---|
| Tipos en el cliente TS | inferidos, sin build | generados desde la spec | generados desde el esquema |
| Cliente Swift / partners | no (protocolo privado) | sí, estándar | sí, con tooling específico |
| Caché HTTP / CDN | limitada (GET con batching) | nativa | difícil (POST) |
| Coste de empezar | horas | horas-días | días-semanas |
| Coste de mantener dos clientes distintos | alto fuera de TS | bajo | bajo |
| Riesgo típico | acoplar front y back en un solo deploy | drift si no se genera desde código | N+1, complejidad, sobreingeniería |

**Cómo estructurarlo para no duplicar lógica:**

```
packages/
  core/          # servicios de dominio: createOrder(), listPosts()... sin HTTP
  api-trpc/      # router tRPC: procedures de 3-5 líneas que llaman a core
  api-rest/      # Hono + zod-openapi: handlers de 3-5 líneas que llaman a core
apps/
  web/           # Next.js, cliente tRPC
  ios/           # cliente generado desde openapi.json
```

La regla que lo mantiene sano: **ninguna regla de negocio en `api-trpc` ni en `api-rest`**; ambos son adaptadores finos. Un test de `core` cubre a los dos.

**Qué le diría al equipo** sobre «es todo tipado»: es verdad y es valioso para la app web; úsalo. Pero el tipado de tRPC es una propiedad del *build*, no de la *API*. En el momento en que un consumidor no comparte el build, necesitas un contrato, y ese contrato se llama OpenAPI.

Decisión reversible más barata: empieza con `core` + `api-trpc` hoy (la web lo necesita ya) y añade `api-rest` cuando arranque iOS, con un *sprint* de margen. Si `core` está bien separado, ese sprint es generar endpoints, no reescribir nada; si no lo está, lo descubrirás a tiempo.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 21-26: GraphQL (schema y resolvers, N+1 y DataLoader, fragmentos, Apollo Client vs urql,
#        diseño de errores, cuándo no usarlo)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Primer servidor GraphQL en Node con TypeScript: posts con autor y una mutation para crear. ¿Apollo Server o Yoga? Y enséñame el mínimo bien hecho, con contexto para la BD y el usuario.",
            },
            {
                "role": "assistant",
                "content": r"""Los dos son correctos; elige por el entorno. **Apollo Server** (`@apollo/server` 4/5) si vas a Node con Express y quieres el ecosistema Apollo (Studio, federación). **GraphQL Yoga** si quieres algo más ligero, basado en `fetch` estándar, que corre igual en Node, Bun, Workers o Deno. El esquema y los resolvers son idénticos en ambos; solo cambia el arranque. Te muestro Apollo y al final el arranque equivalente en Yoga.

```bash
npm i @apollo/server graphql
```

```ts
// src/schema.ts
export const typeDefs = `#graphql
  type User {
    id: ID!
    name: String!
  }

  type Post {
    id: ID!
    title: String!
    body: String!
    author: User!
  }

  type Query {
    post(id: ID!): Post
    posts(limit: Int = 20): [Post!]!
  }

  type Mutation {
    createPost(title: String!, body: String!): Post!
  }
`
```

```ts
// src/context.ts
import type { PrismaClient } from '@prisma/client'
import { db } from './db'
import { getUserFromToken } from './auth'

export interface Context {
  db: PrismaClient
  user: { id: string; name: string } | null
}

export async function createContext(authorization: string | undefined): Promise<Context> {
  return { db, user: await getUserFromToken(authorization) }
}
```

```ts
// src/resolvers.ts
import { GraphQLError } from 'graphql'
import type { Context } from './context'

export const resolvers = {
  Query: {
    post: (_parent: unknown, args: { id: string }, ctx: Context) =>
      ctx.db.post.findUnique({ where: { id: args.id } }),           // null si no existe: el campo es nullable a propósito
    posts: (_parent: unknown, args: { limit: number }, ctx: Context) =>
      ctx.db.post.findMany({ take: Math.min(args.limit, 100), orderBy: { createdAt: 'desc' } }),
  },

  Mutation: {
    createPost: async (_parent: unknown, args: { title: string; body: string }, ctx: Context) => {
      if (!ctx.user) {
        throw new GraphQLError('Debes iniciar sesión', { extensions: { code: 'UNAUTHENTICATED' } })
      }
      if (args.title.trim().length < 3) {
        throw new GraphQLError('El título debe tener al menos 3 caracteres', {
          extensions: { code: 'BAD_USER_INPUT', field: 'title' },
        })
      }
      return ctx.db.post.create({ data: { title: args.title.trim(), body: args.body, authorId: ctx.user.id } })
    },
  },

  Post: {
    // Resolver de campo: se ejecuta por cada Post devuelto (ver nota sobre N+1)
    author: (post: { authorId: string }, _args: unknown, ctx: Context) =>
      ctx.db.user.findUniqueOrThrow({ where: { id: post.authorId } }),
  },
}
```

```ts
// src/server.ts
import { ApolloServer } from '@apollo/server'
import { startStandaloneServer } from '@apollo/server/standalone'
import { createContext, type Context } from './context'
import { resolvers } from './resolvers'
import { typeDefs } from './schema'

const server = new ApolloServer<Context>({ typeDefs, resolvers })

const { url } = await startStandaloneServer(server, {
  listen: { port: 4000 },
  context: ({ req }) => createContext(req.headers.authorization),
})
console.log(`GraphQL en ${url}`)
```

Decisiones:

- **`post(id)` devuelve `Post` nullable y no lanza**: en GraphQL, «no existe» es un valor, no un error; los errores se reservan para fallos (auth, validación, servidor).
- **Contexto por petición**: `createContext` corre en cada request, así que el usuario autenticado está disponible en cualquier resolver sin pasarlo como argumento. El `db` es compartido (un cliente Prisma por proceso).
- **`extensions.code`** es el canal estándar para que el cliente distinga tipos de error; `UNAUTHENTICATED` y `BAD_USER_INPUT` son los códigos que Apollo ya usa, con lo que el cliente los trata igual que los suyos.
- **El resolver `Post.author`** es correcto pero ingenuo: con 20 posts hace 20 consultas de usuario. Antes de salir a producción añade DataLoader; es el siguiente paso obligado, no una optimización opcional.
- Los tipos `(_parent: unknown, args, ctx)` escritos a mano son aceptables para empezar; en cuanto el esquema crezca, genera los tipos de resolvers desde el SDL con `@graphql-codegen/typescript-resolvers` y deja de escribirlos.

**El mismo esquema con Yoga:**

```ts
import { createServer } from 'node:http'
import { createSchema, createYoga } from 'graphql-yoga'

const yoga = createYoga<{ request: Request }, Context>({
  schema: createSchema<Context>({ typeDefs, resolvers }),
  context: ({ request }) => createContext(request.headers.get('authorization') ?? undefined),
})
createServer(yoga).listen(4000)
```

Verificación: abre `http://localhost:4000` (Apollo Sandbox o GraphiQL en Yoga) y ejecuta `mutation { createPost(title: "ab", body: "x") { id } }` sin cabecera `Authorization`. La respuesta debe traer `errors[0].extensions.code === "UNAUTHENTICATED"`; con token y título corto, `BAD_USER_INPUT` con `field: "title"`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Mi API GraphQL se arrastra con la query de la portada. Activé el log de Prisma y para `{ posts(limit: 50) { title author { name } } }` veo esto:

```
prisma:query SELECT ... FROM "Post" ORDER BY "createdAt" DESC LIMIT 50
prisma:query SELECT ... FROM "User" WHERE "id" = $1
prisma:query SELECT ... FROM "User" WHERE "id" = $1
prisma:query SELECT ... FROM "User" WHERE "id" = $1
(... 47 más iguales)
```

Resolver:

```ts
Post: {
  author: (post, _args, ctx) => ctx.db.user.findUnique({ where: { id: post.authorId } }),
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Es el problema **N+1** en su forma canónica: 1 consulta para los posts y N (50) para los autores, porque GraphQL ejecuta el resolver `Post.author` una vez por cada post y cada ejecución va a la base de datos por su cuenta. Con 50 posts son 51 consultas; con una lista de 500, 501.

La solución estándar es **DataLoader**: acumula todas las llamadas a `load(id)` que ocurren en el mismo *tick* del event loop y las resuelve con **una** consulta por lotes. El resolver no cambia de forma; cambia de dónde lee.

```bash
npm i dataloader
```

```ts
// src/loaders.ts
import DataLoader from 'dataloader'
import type { PrismaClient, User } from '@prisma/client'

export function createLoaders(db: PrismaClient) {
  return {
    userById: new DataLoader<string, User | null>(async (ids) => {
      const users = await db.user.findMany({ where: { id: { in: [...ids] } } })
      const byId = new Map(users.map((u) => [u.id, u]))
      return ids.map((id) => byId.get(id) ?? null)   // MISMO orden y MISMA longitud que ids: contrato de DataLoader
    }),
  }
}

export type Loaders = ReturnType<typeof createLoaders>
```

```ts
// src/context.ts
export interface Context {
  db: PrismaClient
  user: SessionUser | null
  loaders: Loaders
}

export async function createContext(authorization?: string): Promise<Context> {
  return { db, user: await getUserFromToken(authorization), loaders: createLoaders(db) }
}
```

```ts
// src/resolvers.ts
Post: {
  author: (post, _args, ctx: Context) => ctx.loaders.userById.load(post.authorId),
}
```

Qué pasa ahora con la misma query:

```
prisma:query SELECT ... FROM "Post" ORDER BY "createdAt" DESC LIMIT 50
prisma:query SELECT ... FROM "User" WHERE "id" IN ($1, $2, ..., $12)
```

Dos consultas. Y fíjate en que son 12 ids, no 50: DataLoader **deduplica** dentro del lote, así que si varios posts tienen el mismo autor, se pide una vez.

**Tres reglas para que DataLoader no te dé un bug peor que el N+1:**

1. **Un loader por petición**, creado en `createContext`. DataLoader cachea `load(id)` para siempre dentro de su instancia; si lo creas a nivel de módulo, un usuario verá el nombre viejo de otro usuario tras una actualización, y entre peticiones de distintos usuarios podrías filtrar datos que no deberían ver.
2. **La función de lote devuelve un array alineado con `ids`**: misma longitud, mismo orden, `null` (o un `Error`) donde no hay fila. Un `findMany` devuelve filas en el orden que le da la gana, de ahí el `Map` y el `ids.map`.
3. **Para relaciones uno-a-muchos** (comentarios de un post), el loader devuelve **arrays**: `new DataLoader<string, Comment[]>(async (postIds) => { const all = await db.comment.findMany({ where: { postId: { in: [...postIds] } } }); return postIds.map((id) => all.filter((c) => c.postId === id)) })`.

**Nota sobre Prisma:** su API «fluida» (`ctx.db.post.findUnique({ where: { id } }).author()`) también agrupa en lotes las llamadas del mismo tick, así que a veces basta con escribir el resolver así. Es menos explícito y no cubre consultas que no sean por clave primaria; DataLoader te sirve para todo, incluidos servicios HTTP externos.

Verificación: deja el log de Prisma activo y vuelve a lanzar la query de portada. Deben aparecer exactamente dos líneas `prisma:query`. Luego pide `{ posts(limit: 50) { author { name posts { title } } } }`: si ves que vuelve el N+1 en `User.posts`, ese campo necesita su propio loader (`postsByAuthorId`), y así con cada relación que expongas.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Para qué sirven los fragmentos en GraphQL más allá de «no repetir campos»? En mi app React cada página tiene una query enorme que lista todos los campos que usan sus 15 componentes y cada cambio en un componente obliga a tocar la query de la página.",
            },
            {
                "role": "assistant",
                "content": r"""El uso que de verdad cambia la arquitectura es la **colocación**: cada componente declara en un fragmento **qué campos necesita**, y la query de la página se compone con esos fragmentos. Añadir un campo a `PostCard` toca solo `PostCard.tsx`; la query de la página no cambia porque ya incluía `...PostCardFields`. El acoplamiento que describes desaparece.

**Componente con su fragmento:**

```tsx
// components/PostCard.tsx
import { gql, useFragment } from '@apollo/client'

export const POST_CARD_FRAGMENT = gql`
  fragment PostCardFields on Post {
    id
    title
    excerpt
    author {
      id
      name
      avatarUrl
    }
  }
`

export function PostCard({ postId }: { postId: string }) {
  const { data, complete } = useFragment({
    fragment: POST_CARD_FRAGMENT,
    from: { __typename: 'Post', id: postId },
  })
  if (!complete) return null

  return (
    <article>
      <h2>{data.title}</h2>
      <p>{data.excerpt}</p>
      <footer><img src={data.author.avatarUrl} alt="" /> {data.author.name}</footer>
    </article>
  )
}
```

**La página compone, no enumera:**

```tsx
// pages/Home.tsx
import { gql, useQuery } from '@apollo/client'
import { PostCard, POST_CARD_FRAGMENT } from '../components/PostCard'
import { SidebarAuthor, SIDEBAR_AUTHOR_FRAGMENT } from '../components/SidebarAuthor'

const HOME_QUERY = gql`
  query Home($limit: Int!) {
    posts(limit: $limit) {
      ...PostCardFields
    }
    featuredAuthor {
      ...SidebarAuthorFields
    }
  }
  ${POST_CARD_FRAGMENT}
  ${SIDEBAR_AUTHOR_FRAGMENT}
`

export function Home() {
  const { data, loading, error } = useQuery(HOME_QUERY, { variables: { limit: 20 } })
  if (loading) return <p>Cargando</p>
  if (error) return <p role="alert">{error.message}</p>

  return (
    <main>
      {data.posts.map((p: { id: string }) => <PostCard key={p.id} postId={p.id} />)}
      <SidebarAuthor authorId={data.featuredAuthor.id} />
    </main>
  )
}
```

Qué ganas, en orden de importancia:

1. **Cambios locales.** `PostCard` necesita `readingTime`: añádelo al fragmento y al JSX, en el mismo archivo. Ninguna de las páginas que lo usan cambia; todas lo reciben.
2. **Sin sobrepedir ni infrapedir.** La query pide exactamente la unión de lo que los componentes consumen. Sin fragmentos, las queries de página acumulan campos que nadie usa ya (nadie se atreve a quitarlos) y faltan los nuevos hasta que alguien se da cuenta.
3. **`useFragment` lee de la caché normalizada** por `__typename` + `id`. El componente se vuelve a renderizar solo cuando cambian **sus** campos, no cuando cambia cualquier parte de la respuesta de la página. En listas largas es una mejora de rendimiento medible.
4. **Tipos por componente.** Con GraphQL Code Generator (`client` preset), cada fragmento genera su tipo y el componente recibe un `FragmentType<typeof POST_CARD_FRAGMENT>` opaco: no puede leer campos que no pidió (*fragment masking*), lo que hace imposible la dependencia accidental entre componentes.

Dos reglas para que esto no se degrade:

- Un fragmento por componente, con el nombre del componente (`PostCardFields`). Un «fragmento global de Post con todo» reproduce el problema original.
- Los fragmentos se exportan junto al componente y la página los importa; nunca al revés. La dirección de dependencia es página → componente.

Verificación: abre Apollo DevTools, pestaña Cache, después de cargar `Home`. Cada `Post:<id>` debe tener solo los campos que piden los fragmentos. Luego añade un campo a `PostCardFields` sin tocar `HOME_QUERY` y comprueba en Network que la query enviada ya lo incluye.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Para un frontend React de tamaño medio (unas 30 pantallas, un backend GraphQL propio) dudamos entre Apollo Client y urql. ¿Cuál recomendarías y por qué?",
            },
            {
                "role": "assistant",
                "content": r"""Para 30 pantallas con un backend propio, **urql** salvo que necesites manipular la caché normalizada a mano con frecuencia (listas editables en muchos sitios, actualizaciones optimistas complejas) o ya dependas del ecosistema Apollo (Studio, federación en el cliente). La diferencia real está en el modelo de caché; el resto es tamaño y API.

| | Apollo Client 3/4 | urql 4/5 |
|---|---|---|
| Caché por defecto | **normalizada** (`__typename:id`): una entidad, un sitio | **documental**: por query; invalida las queries que contienen un `__typename` tocado por una mutation |
| Caché normalizada opcional | es la única | `@urql/exchange-graphcache` (añade ~8 KB) |
| Tamaño (gzip aprox.) | ~35-45 KB | ~7 KB núcleo (+ graphcache si lo usas) |
| Extensión | `ApolloLink` (cadena de enlaces) | *exchanges* (misma idea, más pequeña) |
| `useFragment`, *fragment masking* | sí (3.8+) | con graphcache y codegen |
| SSR / Next App Router | paquete oficial `@apollo/client-integration-nextjs` | `@urql/next` |
| Suspense | sí | sí |
| Curva de aprendizaje | mayor (políticas de caché, `typePolicies`, `cache.modify`) | menor |

**Por qué el modelo de caché decide.** Con la caché documental de urql, tras una mutation que devuelve un `Post`, urql **reejecuta** cualquier query activa que incluya `Post`. Es simple y casi siempre correcto; su coste es alguna petición de más. Con Apollo, la mutation actualiza la entidad en la caché y todas las vistas se refrescan sin red, pero una lista nueva (un post creado) **no aparece sola**: tienes que escribir un `update` que modifique la lista en caché, o usar `refetchQueries`. En 30 pantallas, eso son decenas de `update` que mantener; en mi experiencia es la fuente principal de «la lista no se actualiza» en proyectos Apollo.

**Cuándo Apollo gana de verdad:** apps con la misma entidad visible en muchos sitios a la vez (un panel con el mismo usuario en tres paneles) y edición frecuente, donde la normalización ahorra refetches y mantiene coherencia instantánea; o equipos que ya saben Apollo y tienen `typePolicies` escritas.

**Arranque con urql**, para que veas el tamaño del compromiso:

```tsx
// src/graphql/client.ts
import { Client, cacheExchange, fetchExchange } from 'urql'

export const client = new Client({
  url: '/graphql',
  exchanges: [cacheExchange, fetchExchange],
  fetchOptions: () => ({ headers: { authorization: `Bearer ${getToken()}` } }),
})
```

```tsx
// src/main.tsx
import { Provider } from 'urql'
<Provider value={client}><App /></Provider>
```

```tsx
// src/pages/Posts.tsx
import { gql, useMutation, useQuery } from 'urql'

const POSTS = gql`query Posts { posts(limit: 20) { id title } }`
const CREATE = gql`mutation Create($title: String!, $body: String!) { createPost(title: $title, body: $body) { id title } }`

export function Posts() {
  const [{ data, fetching, error }] = useQuery({ query: POSTS })
  const [{ fetching: creating }, create] = useMutation(CREATE)

  if (fetching) return <p>Cargando</p>
  if (error) return <p role="alert">{error.message}</p>
  return (
    <>
      <button disabled={creating} onClick={() => create({ title: 'Nuevo', body: 'x' })}>Crear</button>
      <ul>{data.posts.map((p: { id: string; title: string }) => <li key={p.id}>{p.title}</li>)}</ul>
    </>
  )
}
```

Tras `create`, la query `Posts` se vuelve a pedir sola porque la mutation devolvió un `Post`. Sin `update`, sin `refetchQueries`.

Decisión reversible: las queries, fragmentos y tipos generados son idénticos en ambos; migrar de urql a Apollo más adelante es cambiar el cliente y los hooks, no las queries. Empezar con el más simple no te encierra.""",
            },
            {
                "role": "user",
                "content": "Elegimos urql. Hay una pantalla donde el refetch automático tras crear un ítem se nota (la lista parpadea). ¿Cómo la actualizo sin volver a pedirla?",
            },
            {
                "role": "assistant",
                "content": r"""Para esa pantalla cambia a la caché normalizada de urql, **graphcache**, y declara cómo se actualiza la lista cuando llega el resultado de la mutation. Es el mismo trabajo que el `update` de Apollo, pero lo haces solo en las mutations que lo necesitan; el resto sigue funcionando por invalidación.

```bash
npm i @urql/exchange-graphcache
```

```ts
// src/graphql/client.ts
import { Client, fetchExchange, gql } from 'urql'
import { cacheExchange } from '@urql/exchange-graphcache'

const POSTS = gql`query Posts($limit: Int!) { posts(limit: $limit) { id title } }`

export const client = new Client({
  url: '/graphql',
  exchanges: [
    cacheExchange({
      updates: {
        Mutation: {
          createPost(result, _args, cache) {
            // Inserta el post nuevo al principio de cada variante de la query Posts que haya en caché
            cache
              .inspectFields('Query')
              .filter((field) => field.fieldName === 'posts')
              .forEach((field) => {
                cache.updateQuery({ query: POSTS, variables: field.arguments }, (data) => {
                  if (!data) return data
                  data.posts.unshift(result.createPost)
                  return data
                })
              })
          },
          deletePost(_result, args, cache) {
            cache.invalidate({ __typename: 'Post', id: args.id as string })   // borrar: invalidar la entidad basta
          },
        },
      },
      optimistic: {
        createPost: (args) => ({
          __typename: 'Post',
          id: `temp-${Date.now()}`,
          title: args.title,
        }),
      },
    }),
    fetchExchange,
  ],
})
```

Qué hace cada parte:

- **`updates.Mutation.createPost`** se ejecuta cuando llega la respuesta real. `inspectFields('Query')` lista todas las variantes de `posts(...)` cacheadas (con `limit: 20`, `limit: 50`), y `updateQuery` modifica cada una; sin red, sin parpadeo.
- **`optimistic.createPost`** pinta el ítem **antes** de la respuesta con un id temporal; cuando llega la real, graphcache sustituye el temporal por la entidad verdadera. Si la mutation falla, revierte sola. El `__typename` es obligatorio para que pueda normalizar.
- **`cache.invalidate`** para el borrado: marca la entidad como inexistente y las listas que la referenciaban la pierden en la siguiente lectura, que se sirve de caché.
- La mutation debe **devolver los campos que la lista usa** (`id title`); si devuelve solo `id`, la fila nueva saldrá con `title` nulo hasta un refetch.

Lo que **no** necesitas tocar: los componentes. `useQuery({ query: POSTS, variables: { limit: 20 } })` recibe la lista actualizada porque graphcache notifica a las queries cuyas entidades cambiaron. Y las pantallas que no definieron `updates` siguen funcionando como con la caché documental: ante una mutation que devuelve un `__typename` desconocido para ellas, graphcache vuelve a pedir (`refetch`) por seguridad.

Verificación: en Network, al crear un post debe verse **una sola** petición (la mutation) y la lista actualizada sin `query Posts` posterior. Si aparece el refetch, revisa que `fieldName === 'posts'` coincide con el nombre real del campo y que la mutation devuelve `__typename` (urql lo añade automáticamente a las selecciones; si construyes la query a mano, no lo quites).""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "How should a GraphQL API report errors? Right now every mutation returns HTTP 200 with an `errors` array, sometimes with `data: null`, and the frontend has a tangle of string matching on `error.message`. There must be a better convention.",
            },
            {
                "role": "assistant",
                "content": r"""Split errors into two kinds and give each its own channel: **expected outcomes** (insufficient stock, email already taken, validation) go in the **schema** as result types; **unexpected failures** (auth missing, server bug, upstream down) go in the **`errors` array with a machine-readable `extensions.code`**. String matching on `message` disappears because nothing the client branches on lives in a message anymore.

**1. Expected outcomes in the schema.** The result is a union the client has to handle explicitly:

```graphql
type Mutation {
  placeOrder(input: PlaceOrderInput!): PlaceOrderResult!
}

union PlaceOrderResult = PlaceOrderSuccess | InsufficientStock | InvalidInput

type PlaceOrderSuccess { order: Order! }
type InsufficientStock { sku: ID!, requested: Int!, available: Int! }
type InvalidInput { field: String!, message: String! }
```

```ts
// resolver
Mutation: {
  placeOrder: async (_p, { input }, ctx) => {
    const issue = validate(input)
    if (issue) return { __typename: 'InvalidInput', ...issue }
    const result = await ctx.orders.place(input, ctx.user)
    if (result.kind === 'insufficient_stock') return { __typename: 'InsufficientStock', ...result }
    return { __typename: 'PlaceOrderSuccess', order: result.order }
  },
},
```

Client side, the switch is on `__typename`, typed by codegen, and the compiler complains when a new case is added to the union:

```ts
const { data } = await client.mutation(PLACE_ORDER, { input })
switch (data.placeOrder.__typename) {
  case 'PlaceOrderSuccess':    return navigate(`/orders/${data.placeOrder.order.id}`)
  case 'InsufficientStock':    return showStock(data.placeOrder.sku, data.placeOrder.available)
  case 'InvalidInput':         return setFieldError(data.placeOrder.field, data.placeOrder.message)
}
```

Why this beats `errors` for business outcomes: they are **data** (they have fields: which SKU, how many available), they are typed, they can be partially successful alongside other fields in the same operation, and they never trigger "error" UI by accident.

**2. Unexpected failures in `errors`, with a code.** Throw `GraphQLError` with `extensions.code`; never throw raw `Error`:

```ts
import { GraphQLError } from 'graphql'

if (!ctx.user) throw new GraphQLError('Not authenticated', { extensions: { code: 'UNAUTHENTICATED', http: { status: 401 } } })
if (!ctx.user.can('orders:write')) throw new GraphQLError('Forbidden', { extensions: { code: 'FORBIDDEN' } })
```

Apollo Server already uses `UNAUTHENTICATED`, `FORBIDDEN`, `BAD_USER_INPUT`, `GRAPHQL_VALIDATION_FAILED` and `INTERNAL_SERVER_ERROR`; reuse them. Anything thrown that is not a `GraphQLError` becomes `INTERNAL_SERVER_ERROR`, and in production you should hide its message:

```ts
const server = new ApolloServer<Context>({
  typeDefs,
  resolvers,
  formatError(formatted, error) {
    if (formatted.extensions?.code === 'INTERNAL_SERVER_ERROR') {
      logger.error(error)                                    // full detail stays on the server
      return { ...formatted, message: 'Internal error' }     // no stack, no SQL, no file paths
    }
    return formatted
  },
})
```

**3. About the 200 status.** That is correct GraphQL: the HTTP layer succeeded; the operation's outcome is in the body. The `graphql-response+json` spec allows non-200 only when the whole request is unusable (malformed document, auth for the entire request), which is what `extensions.http.status` above does. Do not fight it by returning 400 for business outcomes; clients and caches expect 200.

**4. Nullability as an error boundary.** `data: null` on the whole response happens when a **non-null** field errors and the null has to bubble up to the root. Make fields that can fail independently nullable (`author: User` instead of `User!`) so one failing resolver yields `data.post.author = null` plus an entry in `errors` with `path`, and the rest of the page still renders. On the client, `errorPolicy: 'all'` (Apollo) or reading both `data` and `error` (urql) lets you show partial data.

The client code that results from all this: one `switch` on `__typename` per mutation, one global handler for `extensions.code` (`UNAUTHENTICATED` → login, `FORBIDDEN` → toast, `INTERNAL_SERVER_ERROR` → generic message plus report). No `message.includes('stock')` anywhere.

Check: run `placeOrder` with a bad token and with too large a quantity. The first must produce `errors[0].extensions.code === 'UNAUTHENTICATED'` and `data: null`; the second must produce **no** `errors` and `data.placeOrder.__typename === 'InsufficientStock'`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "Tengo un backend con 4 endpoints REST para una app interna (lista de turnos, crear turno, cancelar, buscar paciente) y un solo cliente web. Un compañero insiste en migrarlo a GraphQL «para estar preparados». ¿Vale la pena?",
            },
            {
                "role": "assistant",
                "content": r"""No. Con un cliente y cuatro endpoints, GraphQL te agrega una capa entera (esquema, resolvers, cliente con caché, control de N+1, seguridad de queries) para resolver un problema que no tenés: varios clientes pidiendo formas distintas de los mismos datos.

«Estar preparados» es una apuesta sobre un futuro concreto; conviene nombrarlo. GraphQL paga cuando aparece **alguna** de estas condiciones:

| Condición | ¿La tenés? |
|---|---|
| Varios clientes (web, móvil, partners) que necesitan subconjuntos distintos de los mismos datos | no: un cliente |
| Pantallas que hoy encadenan 3-5 llamadas REST para armar una vista | con 4 endpoints, no |
| Un grafo de datos grande donde el front explora relaciones (paciente → turnos → profesional → agenda) | tal vez en el futuro; hoy no |
| Equipos de front y back separados, con el front bloqueado esperando endpoints nuevos | ¿? Si es el mismo equipo, no |

Si ninguna aplica, lo que ganás es cero y lo que pagás es esto:

- **N+1 desde el primer día.** `turnos { paciente { nombre } }` necesita DataLoader o la base se arrastra. En REST, un `JOIN` en el endpoint y listo.
- **Caché HTTP perdida.** Las queries van por `POST`; el navegador, un CDN o un proxy ya no cachean la lista de turnos. Con REST, un `Cache-Control` o un `ETag` y lo tenés gratis.
- **Superficie de ataque nueva.** Queries anidadas o muy profundas que un cliente malicioso (o un bug) puede usar para tumbar el servidor; necesitás límites de profundidad y de complejidad, o *persisted queries*. Para una app interna, es trabajo que nadie te va a agradecer.
- **Cancelar turno es una mutation con efectos**, exactamente igual que un `DELETE /turnos/:id`; no hay ganancia expresiva.
- **Subidas de archivos y descargas** (un PDF del turno) siguen necesitando REST aparte.

**Lo que sí vale la pena hacer ahora**, que además deja el camino abierto si algún día las condiciones cambian:

1. Documentar los 4 endpoints con **OpenAPI** generado desde el código (si es FastAPI ya lo tenés; en Node, `@hono/zod-openapi` o `fastify-type-provider-zod`). Te da tipos para el cliente y un contrato para cualquier cliente futuro.
2. Separar **lógica de negocio** de los handlers HTTP: `cancelarTurno(id, usuario)` en un módulo propio que el handler REST llama. Si mañana aparece GraphQL, el resolver llama a la misma función; migrar es un adaptador, no una reescritura.
3. Dejar que la segunda pantalla que necesite «armar una vista con 4 llamadas» sea la señal para reevaluar, no una intuición.

Para la discusión con tu compañero, una pregunta concreta zanja el tema: «¿qué pantalla o qué cliente, en los próximos 12 meses, va a pedir una forma de los datos que hoy no podemos dar con un endpoint?». Si la respuesta es un caso real, lo diseñan juntos; si es «por las dudas», la respuesta es OpenAPI + lógica separada, y seguir.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 27-30: REST bien hecho (códigos y Problem Details + OpenAPI, idempotencia e If-Match,
#        paginación por cursor, CORS real)
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy diseñando la API REST de un sistema de reservas. ¿Qué códigos de estado uso para cada caso y cómo devuelvo los errores para que el frontend no tenga que adivinar? Ahora todo es 200 con `{ ok: false, error: '...' }` o 500.",
            },
            {
                "role": "assistant",
                "content": r"""Usa el código HTTP para la **categoría** del resultado y un cuerpo con formato estándar (`application/problem+json`, RFC 9457) para el **detalle**. Así los clientes, proxies y monitores entienden la categoría sin leer el cuerpo, y tu frontend recibe siempre la misma forma.

**Códigos que cubren una API de reservas:**

| Situación | Código | Cuándo |
|---|---|---|
| Lectura correcta | 200 | `GET /reservations/42` |
| Recurso creado | 201 + `Location` | `POST /reservations` |
| Aceptado, se procesará después | 202 | confirmación que depende de un pago asíncrono |
| Correcto sin cuerpo | 204 | `DELETE /reservations/42` |
| JSON malformado o tipo incorrecto | 400 | cuerpo que no parsea, `date: "ayer"` |
| Sin credenciales o inválidas | 401 | token caducado |
| Credenciales válidas, sin permiso | 403 | cancelar la reserva de otro |
| No existe | 404 | id desconocido (o que no debes revelar que existe) |
| Conflicto de estado | 409 | la mesa ya está reservada a esa hora; cancelar una reserva ya cancelada |
| Precondición fallida | 412 | `If-Match` con un `ETag` obsoleto |
| Validación semántica | 422 | fecha en el pasado, 0 comensales (sintaxis bien, significado mal) |
| Demasiadas peticiones | 429 + `Retry-After` | límite de tasa |
| Error nuestro | 500 | excepción no controlada (y se registra) |
| Dependencia caída | 503 + `Retry-After` | pasarela de pago no responde |

Reglas que evitan las discusiones habituales: 400 es «no te entiendo», 422 es «te entiendo pero no es válido»; 409 es «el estado actual lo impide» (otro cliente se adelantó); 404 también para recursos de otros usuarios cuando no quieres confirmar su existencia.

**El cuerpo: Problem Details.** Un solo formato para todos los errores:

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/slot-taken",
  "title": "La franja ya está reservada",
  "status": 409,
  "detail": "La mesa 4 tiene una reserva de 20:00 a 22:00 el 2025-06-14.",
  "instance": "/reservations",
  "conflictingReservationId": "r_8812"
}
```

- `type`: URI estable que **identifica la clase de problema**; es lo que el frontend compara (`if (problem.type.endsWith('/slot-taken'))`), nunca el texto.
- `title`: descripción corta y fija de la clase; `detail`: específico de esta ocurrencia, para mostrar al usuario.
- Campos extra (`conflictingReservationId`, o `errors` con la lista de campos inválidos en un 422) son legítimos: el formato es extensible.

Implementación mínima en Express con TypeScript:

```ts
// src/http/problem.ts
export class Problem extends Error {
  constructor(
    public readonly status: number,
    public readonly type: string,
    public readonly title: string,
    public readonly detail?: string,
    public readonly extra: Record<string, unknown> = {},
  ) {
    super(detail ?? title)
  }
}

export const problemHandler: ErrorRequestHandler = (err, req, res, _next) => {
  const problem = err instanceof Problem
    ? err
    : new Problem(500, 'about:blank', 'Error interno')          // nunca filtres err.message de un 500
  if (problem.status >= 500) req.log.error(err)
  res
    .status(problem.status)
    .type('application/problem+json')
    .json({ type: problem.type, title: problem.title, status: problem.status, detail: problem.detail, instance: req.originalUrl, ...problem.extra })
}
```

```ts
// en un servicio
throw new Problem(409, 'https://api.example.com/problems/slot-taken', 'La franja ya está reservada',
  `La mesa ${table} tiene una reserva de ${from} a ${to} el ${date}.`, { conflictingReservationId: existing.id })
```

Y para validación (422), `extra: { errors: [{ field: 'guests', message: 'debe ser mayor que 0' }] }`.

Lo que ganas frente a `200 { ok: false }`: `fetch` y Axios distinguen éxito de error sin inspeccionar el cuerpo, el navegador y los proxies no cachean errores como si fueran respuestas válidas, los paneles de monitorización cuentan 4xx/5xx de verdad, y el frontend tiene **un** `catch` que entiende todos los errores.

Verificación: `curl -i -X POST .../reservations -d '{"guests":0}'` debe devolver `422`, `Content-Type: application/problem+json` y un `errors` con `guests`. Un `curl` a un id inexistente, `404` con el mismo formato.""",
            },
            {
                "role": "user",
                "content": "Bien. ¿Y cómo documento esos errores en OpenAPI para que el equipo de frontend vea qué puede devolver cada endpoint sin leer el código?",
            },
            {
                "role": "assistant",
                "content": r"""Define el esquema `Problem` **una vez** en `components`, crea una respuesta reutilizable por código y referéncialas desde cada operación. Lo que debe documentar cada endpoint es exactamente **qué códigos y qué `type` de problema** puede devolver; el formato ya es común.

```yaml
# openapi.yaml (OpenAPI 3.1)
openapi: 3.1.0
info:
  title: Reservas API
  version: 1.0.0

components:
  schemas:
    Problem:
      type: object
      required: [type, title, status]
      properties:
        type: { type: string, format: uri, description: "Identificador estable de la clase de problema" }
        title: { type: string }
        status: { type: integer, minimum: 400, maximum: 599 }
        detail: { type: string }
        instance: { type: string }
      additionalProperties: true          # permite los campos de extensión (conflictingReservationId, errors)

    ValidationProblem:
      allOf:
        - $ref: "#/components/schemas/Problem"
        - type: object
          required: [errors]
          properties:
            errors:
              type: array
              items:
                type: object
                required: [field, message]
                properties:
                  field: { type: string }
                  message: { type: string }

  responses:
    NotFound:
      description: El recurso no existe o no es visible para el usuario
      content:
        application/problem+json:
          schema: { $ref: "#/components/schemas/Problem" }
    Unprocessable:
      description: La petición es sintácticamente válida pero sus datos no
      content:
        application/problem+json:
          schema: { $ref: "#/components/schemas/ValidationProblem" }
    Conflict:
      description: El estado actual del recurso impide la operación
      content:
        application/problem+json:
          schema: { $ref: "#/components/schemas/Problem" }
          examples:
            slotTaken:
              summary: Franja ya reservada
              value:
                type: https://api.example.com/problems/slot-taken
                title: La franja ya está reservada
                status: 409
                detail: La mesa 4 tiene una reserva de 20:00 a 22:00 el 2025-06-14.
                conflictingReservationId: r_8812

paths:
  /reservations:
    post:
      operationId: createReservation
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CreateReservation" }
      responses:
        "201":
          description: Reserva creada
          headers:
            Location: { schema: { type: string }, description: URL de la reserva creada }
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Reservation" }
        "401": { $ref: "#/components/responses/Unauthorized" }
        "409": { $ref: "#/components/responses/Conflict" }
        "422": { $ref: "#/components/responses/Unprocessable" }
```

Decisiones:

- **`additionalProperties: true`** en `Problem`: RFC 9457 permite extensiones y los generadores de clientes no deben rechazarlas. `ValidationProblem` con `allOf` tipa la extensión `errors` del 422 para que el cliente generado tenga `problem.errors[]` con tipos.
- **`examples` con nombre** en el 409: es lo que el frontend abre para ver qué `type` comparar. Un ejemplo por cada `type` que ese endpoint puede producir vale más que un párrafo de descripción.
- **El catálogo de `type`** merece una sección propia en `info.description` o un documento enlazado: lista de URIs con su significado. Los clientes se acoplan a esas URIs, así que son API pública y se versionan como tal.
- **OpenAPI 3.1** y no 3.0: su esquema es JSON Schema 2020-12 completo (`type: [string, "null"]`, `const`, `$dynamicRef`), y las herramientas actuales (`openapi-typescript`, Redocly, Swagger UI 5) lo soportan.

Para no mantener el YAML a mano, genera la especificación **desde el código**: con `@hono/zod-openapi` o `fastify-type-provider-zod` declaras cada respuesta junto a la ruta y la spec sale sincronizada; con FastAPI es automático a partir de los `responses={409: {"model": Problem}}`. La única forma de que la documentación mienta es escribirla aparte.

Verificación: `npx @redocly/cli lint openapi.yaml` debe pasar sin errores, y `npx openapi-typescript openapi.yaml -o src/api/schema.d.ts` debe generar un tipo `components['schemas']['ValidationProblem']` con `errors`. Si el frontend puede escribir `if (res.status === 422) problem.errors.map(...)` con autocompletado, la documentación está haciendo su trabajo.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tenemos `POST /payments` y de vez en cuando un cliente con mala red reintenta y cobramos dos veces. He leído de `Idempotency-Key`, ¿cómo lo implemento bien en Node + Postgres? Y de paso, los `PUT` de perfil se pisan entre dos pestañas.",
            },
            {
                "role": "assistant",
                "content": r"""Son dos mecanismos distintos para dos problemas distintos: **`Idempotency-Key`** hace que repetir un `POST` no repita el efecto; **`ETag` + `If-Match`** hace que un `PUT` falle si el recurso cambió desde que el cliente lo leyó. Te doy los dos; el primero es el que te está costando dinero.

**1. `Idempotency-Key` para `POST /payments`.**

El cliente genera un UUID por *intento lógico* de pago (no por reintento HTTP) y lo envía en la cabecera; el servidor guarda la respuesta asociada a esa clave y la devuelve tal cual en los reintentos. La parte difícil es la concurrencia: dos reintentos pueden llegar a la vez. Se resuelve reclamando la clave con un `INSERT` atómico **antes** de procesar.

```sql
CREATE TABLE idempotency_keys (
  user_id       text        NOT NULL,
  key           text        NOT NULL,
  request_hash  text        NOT NULL,              -- para detectar reutilización con otro cuerpo
  status        text        NOT NULL DEFAULT 'in_progress',   -- in_progress | completed
  response_code int,
  response_body jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, key)
);
CREATE INDEX ON idempotency_keys (created_at);   -- para purgar claves de más de 24 h
```

```ts
// src/http/idempotency.ts
import { createHash } from 'node:crypto'
import type { RequestHandler } from 'express'
import { pool } from '../db'
import { Problem } from './problem'

const hashRequest = (method: string, path: string, body: unknown) =>
  createHash('sha256').update(`${method} ${path} ${JSON.stringify(body)}`).digest('hex')

export const idempotent: RequestHandler = async (req, res, next) => {
  const key = req.header('Idempotency-Key')
  if (!key) return next(new Problem(400, 'https://api.example.com/problems/missing-idempotency-key', 'Falta Idempotency-Key'))
  const userId = req.user.id
  const requestHash = hashRequest(req.method, req.path, req.body)

  // Reclamar la clave: solo UNA petición concurrente consigue insertar
  const claimed = await pool.query(
    `INSERT INTO idempotency_keys (user_id, key, request_hash) VALUES ($1, $2, $3)
     ON CONFLICT (user_id, key) DO NOTHING RETURNING key`,
    [userId, key, requestHash],
  )

  if (claimed.rowCount === 0) {
    const { rows: [existing] } = await pool.query(
      'SELECT request_hash, status, response_code, response_body FROM idempotency_keys WHERE user_id = $1 AND key = $2',
      [userId, key],
    )
    if (existing.request_hash !== requestHash) {
      return next(new Problem(422, 'https://api.example.com/problems/idempotency-key-reused', 'Idempotency-Key reutilizada con otro cuerpo'))
    }
    if (existing.status === 'in_progress') {
      res.set('Retry-After', '2')
      return next(new Problem(409, 'https://api.example.com/problems/request-in-progress', 'La petición original aún se está procesando'))
    }
    return res.status(existing.response_code).set('Idempotent-Replayed', 'true').json(existing.response_body)
  }

  // Primera vez: interceptar la respuesta para guardarla
  const originalJson = res.json.bind(res)
  res.json = (body: unknown) => {
    void pool.query(
      `UPDATE idempotency_keys SET status = 'completed', response_code = $3, response_body = $4 WHERE user_id = $1 AND key = $2`,
      [userId, key, res.statusCode, body],
    )
    return originalJson(body)
  }
  next()
}
```

```ts
app.post('/payments', requireAuth, idempotent, createPayment)
```

Puntos que marcan la diferencia:

- **`ON CONFLICT DO NOTHING RETURNING`** es la exclusión mutua: con dos reintentos simultáneos, uno inserta y procesa; el otro ve `rowCount === 0`, encuentra `in_progress` y recibe 409 con `Retry-After`. El cliente reintenta y obtiene la respuesta guardada. Ningún cobro doble.
- **La clave es por usuario** (`PRIMARY KEY (user_id, key)`): un cliente no puede «reproducir» la respuesta de otro adivinando claves.
- **Se guarda también el error** (un 402 por tarjeta rechazada se reproduce igual): el reintento no vuelve a intentar el cobro. Si quieres permitir reintentar tras un 5xx tuyo, borra la fila en el `errorHandler` cuando `status >= 500`.
- **Purga** con un job: `DELETE FROM idempotency_keys WHERE created_at < now() - interval '24 hours'`. Stripe conserva 24 h; es un buen punto de partida.
- Si el procesamiento muere a mitad (proceso caído), la fila queda `in_progress` para siempre. Añade `AND created_at > now() - interval '1 minute'` a la condición de `in_progress`; pasado ese tiempo, trata la clave como libre y borra la fila antes de reinsertar.

**2. `ETag` + `If-Match` para `PUT /profile`.**

Añade una columna `version int` que se incrementa en cada escritura y exponla como `ETag`:

```ts
app.get('/profile', async (req, res) => {
  const profile = await getProfile(req.user.id)
  res.set('ETag', `"${profile.version}"`).json(profile)
})

app.put('/profile', async (req, res, next) => {
  const ifMatch = req.header('If-Match')
  if (!ifMatch) return next(new Problem(428, 'https://api.example.com/problems/precondition-required', 'Envía If-Match con el ETag actual'))
  const expected = Number(ifMatch.replace(/"/g, ''))

  const { rows: [updated] } = await pool.query(
    `UPDATE profiles SET name = $2, bio = $3, version = version + 1
     WHERE user_id = $1 AND version = $4 RETURNING *`,
    [req.user.id, req.body.name, req.body.bio, expected],
  )
  if (!updated) return next(new Problem(412, 'https://api.example.com/problems/stale-update', 'El perfil cambió desde que lo cargaste; recarga y vuelve a intentarlo'))
  res.set('ETag', `"${updated.version}"`).json(updated)
})
```

El `UPDATE ... WHERE version = $4` es la comprobación y la escritura **en una sola sentencia**: no hay ventana entre leer la versión y escribir. La segunda pestaña, que cargó la versión 3 cuando la primera ya guardó la 4, recibe 412 y puede mostrar «alguien ha modificado el perfil» en vez de pisarlo.

Verificación del primero con un test que lance `Promise.all` de cinco `POST /payments` con la misma clave contra la app en memoria: la pasarela (mockeada) debe recibir **una** llamada, cuatro respuestas deben ser 409 o réplicas con `Idempotent-Replayed: true`, y una fila en `idempotency_keys`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi endpoint `GET /events?page=3&size=50` empieza a tardar segundos en páginas altas y además los usuarios ven eventos repetidos al pasar de página cuando se están creando eventos nuevos. ¿Cómo lo hago bien?",
            },
            {
                "role": "assistant",
                "content": r"""Los dos síntomas son del mismo diseño: la paginación por **offset** (`OFFSET 100 LIMIT 50`). La base de datos tiene que leer y descartar las 100 primeras filas (de ahí la lentitud creciente), y si entre dos páginas entra un evento nuevo al principio, todo se desplaza una posición y el último de la página 2 reaparece como primero de la 3.

La solución es paginar por **cursor (keyset)**: en vez de «dame a partir de la posición 100», «dame los que van después de **este** evento». La posición se define por los valores de ordenación del último elemento visto, no por un número.

**SQL.** Ordena por una clave estable y única: `created_at` más `id` como desempate (dos eventos pueden compartir milisegundo).

```sql
-- índice que sirve la consulta sin ordenar en memoria
CREATE INDEX events_created_id_idx ON events (created_at DESC, id DESC);

-- primera página
SELECT id, title, created_at FROM events
ORDER BY created_at DESC, id DESC
LIMIT 51;

-- siguientes: todo lo "anterior" al último visto (comparación de tupla)
SELECT id, title, created_at FROM events
WHERE (created_at, id) < ($1, $2)
ORDER BY created_at DESC, id DESC
LIMIT 51;
```

`(created_at, id) < ($1, $2)` es comparación lexicográfica de tuplas (soportada por Postgres y MySQL 8), exactamente el orden del `ORDER BY`; con el índice compuesto, la página 1 000 cuesta lo mismo que la 1. Pido `51` para saber si hay más sin una consulta de `COUNT`.

**Endpoint.** El cursor es opaco para el cliente: codifica los valores en base64url y no documentes su interior.

```ts
// src/http/events.ts
import type { RequestHandler } from 'express'
import { pool } from '../db'
import { Problem } from './problem'

const PAGE_SIZE = 50

interface Cursor { createdAt: string; id: string }

const encodeCursor = (c: Cursor) => Buffer.from(JSON.stringify(c)).toString('base64url')
function decodeCursor(raw: string): Cursor {
  try {
    const parsed = JSON.parse(Buffer.from(raw, 'base64url').toString()) as Cursor
    if (typeof parsed.createdAt !== 'string' || typeof parsed.id !== 'string') throw new Error('shape')
    return parsed
  } catch {
    throw new Problem(400, 'https://api.example.com/problems/invalid-cursor', 'Cursor inválido')
  }
}

export const listEvents: RequestHandler = async (req, res) => {
  const after = typeof req.query.cursor === 'string' ? decodeCursor(req.query.cursor) : null

  const { rows } = after
    ? await pool.query(
        `SELECT id, title, created_at FROM events WHERE (created_at, id) < ($1, $2)
         ORDER BY created_at DESC, id DESC LIMIT $3`,
        [after.createdAt, after.id, PAGE_SIZE + 1],
      )
    : await pool.query('SELECT id, title, created_at FROM events ORDER BY created_at DESC, id DESC LIMIT $1', [PAGE_SIZE + 1])

  const hasMore = rows.length > PAGE_SIZE
  const items = hasMore ? rows.slice(0, PAGE_SIZE) : rows
  const last = items.at(-1)

  res.json({
    items,
    nextCursor: hasMore && last ? encodeCursor({ createdAt: last.created_at.toISOString(), id: last.id }) : null,
  })
}
```

Respuesta:

```json
{ "items": [ ... 50 eventos ... ], "nextCursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTA2LTE0VDEwOjAwOjAwLjAwMFoiLCJpZCI6ImV2XzEyMyJ9" }
```

`nextCursor: null` significa «no hay más». El cliente no construye cursores; solo reenvía el que recibió: `GET /events?cursor=eyJj...`.

**Lo que pierdes y cuándo importa:**

- **No hay «ir a la página 7».** El usuario navega con «siguiente». Para listas cronológicas (eventos, feeds, logs) nadie salta a la página 7; para tablas administrativas con *paginador numérico* quizá necesites mantener offset **con tope** (`page <= 100`) y aceptar sus defectos.
- **El orden debe estar fijado por el cursor.** Si permites `?sort=title`, el cursor debe incluir `title` e `id` y la consulta cambia a `(title, id) > ($1, $2)` ascendente. Una implementación genérica mantiene una tabla de órdenes permitidos → columnas, nunca interpola el parámetro.
- **Filtros** (`?type=concert`) van en el `WHERE` además del cursor y deben repetirse en cada página; para que el cliente no pueda cambiarlos a mitad, puedes incluirlos en el cursor y rechazar la petición si no coinciden.
- `COUNT(*)` total: no lo devuelvas en cada página; es la segunda causa de lentitud. Si la UI lo necesita, un endpoint aparte, cacheado o aproximado.

Verificación del problema original: inserta un evento nuevo entre la petición de la página 1 y la de la 2 (dos `curl` con un `INSERT` en medio). Con offset, el último ítem de la página 1 reaparece en la 2; con cursor, la página 2 continúa exactamente donde acabó la 1 y el evento nuevo aparecerá solo al recargar desde el principio, que es el comportamiento correcto para un listado cronológico.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""El frontend (React en `https://app.miapp.com`) no consigue llamar a la API (Express en `https://api.miapp.com`). En consola:

```
Access to fetch at 'https://api.miapp.com/orders' from origin 'https://app.miapp.com' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

En Postman funciona perfectamente. Tengo `app.use(cors())` puesto, pero después del middleware de autenticación.""",
            },
            {
                "role": "assistant",
                "content": r"""Ya has encontrado la causa en la última frase: el **preflight** (`OPTIONS`) llega sin cabecera `Authorization`, tu middleware de autenticación lo rechaza con 401 antes de que `cors()` añada las cabeceras, y el navegador interpreta ese 401 sin `Access-Control-Allow-Origin` como «CORS denegado». Postman no hace preflight ni aplica CORS, por eso allí funciona.

Lo que ocurre, paso a paso:

```
navegador: la petición lleva Authorization y Content-Type: application/json → no es "simple" → envía antes
           OPTIONS /orders  (Origin: https://app.miapp.com, Access-Control-Request-Method: GET,
                             Access-Control-Request-Headers: authorization, content-type)
express:   requireAuth → no hay token → 401  (cors() nunca llega a ejecutarse)
navegador: la respuesta del preflight no trae Access-Control-Allow-Origin → bloquea y ni envía el GET
```

**Arreglo: CORS antes de cualquier middleware que pueda rechazar, y con configuración explícita** (el `cors()` vacío responde `*`, que no sirve si usas cookies y abre la API a cualquier origen):

```ts
// src/app.ts
import cors from 'cors'
import express from 'express'

const ALLOWED_ORIGINS = new Set([
  'https://app.miapp.com',
  ...(process.env.NODE_ENV !== 'production' ? ['http://localhost:5173'] : []),
])

const app = express()

app.use(
  cors({
    origin: (origin, callback) => {
      // origin es undefined en peticiones sin Origin (curl, server-to-server): se permiten
      if (!origin || ALLOWED_ORIGINS.has(origin)) return callback(null, true)
      callback(null, false)   // origen no permitido: respondemos sin cabeceras CORS y el navegador bloquea
    },
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    exposedHeaders: ['ETag', 'Location'],   // cabeceras que el JS del front puede leer además de las básicas
    maxAge: 600,                              // el navegador cachea el preflight 10 min: menos OPTIONS
  }),
)

app.use(express.json())
app.use(requireAuth)        // ahora sí: el OPTIONS ya fue respondido por cors() con 204
app.use('/orders', ordersRouter)
```

Detalles que importan:

- **`cors()` responde el preflight por sí mismo** (204 con las cabeceras) y corta la cadena; no necesitas `app.options(...)`. Por eso tiene que ir antes de `requireAuth`.
- **Lista explícita de orígenes** en vez de `origin: true` (que refleja cualquier origen): con `*` o reflejo, cualquier web puede hacer peticiones autenticadas a tu API desde el navegador de un usuario con sesión.
- Cuando `origin` es una función o una lista, el paquete `cors` añade **`Vary: Origin`** automáticamente, necesario para que un CDN o proxy no sirva a `app.miapp.com` la respuesta cacheada para otro origen.
- **`allowedHeaders`** debe incluir todo lo que el front envíe más allá de las cabeceras simples: `Authorization`, `Content-Type: application/json`, cualquier `X-Request-Id`. Si falta una, el preflight falla con otro mensaje (`Request header field x-request-id is not allowed`).
- `maxAge` reduce la latencia: sin él, cada petición no simple paga un `OPTIONS` extra.

Verificación con `curl`, simulando el preflight:

```bash
curl -i -X OPTIONS https://api.miapp.com/orders \
  -H 'Origin: https://app.miapp.com' \
  -H 'Access-Control-Request-Method: GET' \
  -H 'Access-Control-Request-Headers: authorization,content-type'
```

Debe devolver `204` con `Access-Control-Allow-Origin: https://app.miapp.com`, `Access-Control-Allow-Headers: Content-Type,Authorization` y `Vary: Origin`. Con `Origin: https://evil.example`, 204 **sin** `Access-Control-Allow-Origin`.""",
            },
            {
                "role": "user",
                "content": "Ya pasa el preflight. Pero ahora el `GET /orders` llega sin la cookie de sesión y la API devuelve 401; en la misma pestaña, si abro `https://api.miapp.com/orders` directamente, la cookie sí va.",
            },
            {
                "role": "assistant",
                "content": r"""Es el comportamiento por defecto de `fetch`: con `credentials: 'same-origin'` (el valor por defecto) **no envía cookies a otro origen**, y `api.miapp.com` es otro origen aunque sea el mismo sitio. Al abrir la URL en la barra de direcciones es una navegación, no un `fetch`, y la cookie va. Hacen falta tres cosas alineadas: el cliente pide enviar credenciales, el servidor las acepta explícitamente y la cookie permite ese uso.

**1. Cliente: `credentials: 'include'`.**

```ts
const res = await fetch('https://api.miapp.com/orders', { credentials: 'include' })
// con Axios: axios.create({ baseURL: 'https://api.miapp.com', withCredentials: true })
```

**2. Servidor: `credentials: true` y origen exacto.**

```ts
app.use(
  cors({
    origin: (origin, cb) => cb(null, !origin || ALLOWED_ORIGINS.has(origin)),
    credentials: true,   // añade Access-Control-Allow-Credentials: true
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    maxAge: 600,
  }),
)
```

El navegador rechaza `Access-Control-Allow-Origin: *` cuando hay credenciales; por eso la lista explícita de orígenes de antes no era solo buena práctica, era requisito.

**3. La cookie.** `app.miapp.com` y `api.miapp.com` comparten el sitio (`miapp.com`), así que una cookie `SameSite=Lax` **sí** se envía en este `fetch` cross-origin: `SameSite` mira el sitio, no el origen. Con los dos pasos anteriores debería bastar. Revisa cómo la emite el login:

```ts
res.cookie('session', token, {
  httpOnly: true,
  secure: true,
  sameSite: 'lax',
  domain: undefined,     // host-only: válida para api.miapp.com, que es quien la lee
  path: '/',
  maxAge: 7 * 24 * 3600 * 1000,
})
```

No pongas `domain: '.miapp.com'` salvo que otro subdominio necesite leerla; cuanto más estrecho, mejor.

**Si los dominios fueran sitios distintos** (`miapp.com` y `miapp-api.com`), la cookie necesitaría `SameSite=None; Secure`, y aun así Safari y los perfiles de Chrome con cookies de terceros bloqueadas la descartarían. En ese escenario la solución no es CORS: sirve la API bajo el mismo sitio (`api.miapp.com`) o pon un proxy en el front (`/api/*` → API) para que sea mismo origen y CORS deje de existir.

Verificación en DevTools, pestaña Network, petición `GET /orders`:

- Request Headers debe incluir `Cookie: session=...`.
- Response Headers: `Access-Control-Allow-Origin: https://app.miapp.com` y `Access-Control-Allow-Credentials: true`.

Si la cookie no aparece en la petición, mira en Application → Cookies → `https://api.miapp.com` si existe: si no está, el login no la fijó (falta `secure` en HTTPS o el `Set-Cookie` fue rechazado); si está pero no viaja, falta el `credentials: 'include'`.""",
            },
        ]
    },
]
