"""Node 20/22: Express 5 (9 filas), NestJS 10/11 (9), Fastify 5 (6) y Hono (6)."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # ------------------------------------------------------------------
    # Express 5 (1-9)
    # ------------------------------------------------------------------
    # 1) Estructura de una app Express 5 y cambios respecto a Express 4.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Voy a empezar una API nueva con Express 5 y TypeScript. ¿Cómo la estructuro y qué cambió respecto a Express 4? Tengo bastante código viejo que pienso copiar y no quiero sorpresas.",
            },
            {
                "role": "assistant",
                "content": r"""Separa tres cosas: la **construcción** de la app (`app.ts`, sin `listen`), el **arranque** (`server.ts`) y un **router por recurso**. Así los tests importan `createApp()` sin abrir puertos, y cada recurso cambia sin tocar los demás.

```
src/
  app.ts          # middlewares, routers, 404 y manejador de errores
  server.ts       # solo listen
  routes/
    users.ts
```

```ts
// src/routes/users.ts
import { randomUUID } from "node:crypto";
import { Router } from "express";

type User = { id: string; name: string };
const users = new Map<string, User>();

export const usersRouter = Router();

usersRouter.get("/", (_req, res) => {
  res.json([...users.values()]);
});

usersRouter.get("/:id", (req, res) => {
  const user = users.get(req.params.id);
  if (!user) {
    res.status(404).json({ error: "user_not_found" });
    return;
  }
  res.json(user);
});

usersRouter.post("/", (req, res) => {
  // en Express 5, sin express.json() req.body es undefined (en 4 era {})
  const name = typeof req.body?.name === "string" ? req.body.name.trim() : "";
  if (!name) {
    res.status(400).json({ error: "name_required" });
    return;
  }
  const user: User = { id: randomUUID(), name };
  users.set(user.id, user);
  res.status(201).json(user);
});
```

```ts
// src/app.ts
import express, { type ErrorRequestHandler } from "express";
import { usersRouter } from "./routes/users.js";

const errorHandler: ErrorRequestHandler = (err, _req, res, next) => {
  if (res.headersSent) {
    next(err);
    return;
  }
  // body-parser marca sus errores con status (400 JSON inválido, 413 cuerpo demasiado grande)
  const status = typeof err?.status === "number" ? err.status : 500;
  if (status >= 500) console.error(err);
  res.status(status).json({ error: status >= 500 ? "internal_error" : String(err.message) });
};

export function createApp() {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "100kb" }));

  app.get("/health", (_req, res) => {
    res.json({ status: "ok" });
  });
  app.use("/users", usersRouter);

  // 404: después de todas las rutas y sin path, así no depende de la sintaxis de comodines
  app.use((req, res) => {
    res.status(404).json({ error: "not_found", path: req.path });
  });
  // el manejador de errores se reconoce por tener 4 parámetros
  app.use(errorHandler);
  return app;
}
```

```ts
// src/server.ts
import { createApp } from "./app.js";

const port = Number(process.env.PORT ?? 3000);
createApp().listen(port, () => {
  console.log(`Escuchando en http://localhost:${port}`);
});
```

## Lo que rompe al copiar código de Express 4

| Express 4 | Express 5 | Síntoma si no lo cambias |
|---|---|---|
| `app.all("*", …)`, `"/files/*"` | `"/*splat"` (no casa con `/`) o `"/{*splat}"` (incluye la raíz) | `TypeError: Missing parameter name…` al arrancar |
| `"/:id?"` | `"/{:id}"` | error de parseo al arrancar |
| `async` sin `try/catch` | el rechazo llega solo a `next(err)` | ninguno: es una mejora |
| `req.body` vale `{}` sin parser | vale `undefined` | `Cannot read properties of undefined` |
| `req.query` asignable, parser `extended` | getter de solo lectura, parser `simple` | `TypeError: Cannot set property query…`; `?a[b]=1` ya no da objeto |
| `app.del()` | `app.delete()` | `app.del is not a function` |
| `req.param("id")` | `req.params.id`, `req.query`, `req.body` | `req.param is not a function` |
| `res.redirect("back")` | `res.redirect(req.get("Referrer") ?? "/")` | redirección rota |
| `res.send(200)`, `res.json(obj, 201)` | `res.sendStatus(200)`, `res.status(201).json(obj)` | respuestas incorrectas |
| `express.urlencoded()` con `extended: true` | `extended: false` por defecto | formularios anidados llegan planos |

La causa de las dos primeras filas es que Express 5 usa `path-to-regexp` v8: los comodines tienen nombre (`*splat`, luego lo lees en `req.params.splat`, que es un array de segmentos), los opcionales van entre llaves y los caracteres de regex (`?`, `+`, `(`) ya no se aceptan dentro de un string. Si necesitas una expresión regular, pasa un `RegExp` de verdad.

Por qué el 404 sin path: un `app.use(handler)` sin ruta casa con todo lo que llegó hasta ahí, y evita justo el `app.all("*")` que ya no compila.

Requisitos: Node 18 o superior, `npm i express@5` y `npm i -D @types/express@5` (los tipos de la 4 no conocen los handlers que devuelven promesas).

Comprobación rápida:

```bash
curl -i localhost:3000/nada                       # 404 en JSON
curl -i -X POST localhost:3000/users \
  -H 'content-type: application/json' -d '{mal'   # 400 en JSON, no la página HTML por defecto
curl -i -X POST localhost:3000/users \
  -H 'content-type: application/json' -d '{"name":"Ana"}'   # 201
```

Si el segundo devuelve HTML, el manejador de errores no está registrado al final o no tiene los cuatro parámetros.""",
            },
        ]
    },
    # 2) Error: handler async en Express 4 que cuelga peticiones o tumba el proceso.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tenemos una API en Express 4 y a veces las peticiones se quedan colgadas hasta que el cliente corta por timeout. Antes el proceso directamente se caía con esto:

```
Error: connect ECONNREFUSED 127.0.0.1:5432
    at TCPConnectWrap.afterConnect [as oncomplete] (node:net:1607:16)
```

y un compañero añadió `process.on('unhandledRejection', console.error)` para que no se cayera. El handler es así:

```js
app.get("/orders/:id", async (req, res) => {
  const order = await db.query("SELECT * FROM orders WHERE id = $1", [req.params.id]);
  if (order.rows.length === 0) {
    return res.status(404).json({ error: "not found" });
  }
  res.json(order.rows[0]);
});
```

¿Qué está pasando?""",
            },
            {
                "role": "assistant",
                "content": r"""Es el mismo fallo con dos síntomas. **Express 4 ignora la promesa que devuelve un handler `async`.** Cuando `db.query` rechaza (Postgres no acepta conexiones), nadie captura ese rechazo:

1. **Sin el `process.on`**: desde Node 15 un rechazo no capturado termina el proceso. Ese es el primer síntoma, y se lleva por delante todas las peticiones en curso.
2. **Con el `process.on`**: el proceso sobrevive, pero nadie llama a `res.json` ni a `next(err)`. La petición queda abierta hasta que el cliente se cansa. Es el segundo síntoma, y es peor: el fallo ahora es silencioso y cada petición colgada retiene un socket.

El parche convirtió un crash visible en una fuga invisible. El arreglo tiene tres partes.

## 1. Que el error llegue a Express

Con **Express 5** no hay que hacer nada: si el handler devuelve una promesa rechazada, Express llama a `next(err)` por ti. Es la mejor razón para migrar.

Si de momento sigues en Express 4, envuelve los handlers:

```ts
import type { NextFunction, Request, RequestHandler, Response } from "express";

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<unknown>;

// solo para Express 4: en 5 sobra
export const asyncHandler =
  (fn: AsyncHandler): RequestHandler =>
  (req, res, next) => {
    fn(req, res, next).catch(next);
  };
```

## 2. Un único sitio que decide la respuesta de error

Distingue dos clases de error, porque se tratan distinto:

- **Operacionales**: esperables en un sistema sano (recurso inexistente, dependencia caída). Se responde con un código concreto.
- **Bugs**: un `TypeError`, un `undefined` inesperado. Se registran con todo el detalle y el cliente recibe un 500 genérico, sin stack.

```ts
// src/http/errors.ts
export class HttpError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message?: string) {
    super(message ?? code);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
  }
}
```

```ts
// src/http/error-handler.ts
import type { ErrorRequestHandler } from "express";
import { HttpError } from "./errors.js";

const isProduction = process.env.NODE_ENV === "production";
const TRANSIENT_CODES = new Set(["ECONNREFUSED", "ECONNRESET", "ETIMEDOUT"]);

export const errorHandler: ErrorRequestHandler = (err, req, res, next) => {
  if (res.headersSent) {
    // la respuesta ya empezó: Express cierra la conexión
    next(err);
    return;
  }
  if (err instanceof HttpError) {
    res.status(err.status).json({ error: err.code, message: err.message });
    return;
  }
  if (TRANSIENT_CODES.has(err?.code)) {
    // dependencia caída: error operacional, el cliente puede reintentar
    console.warn({ code: err.code, path: req.originalUrl }, "dependencia no disponible");
    res.set("Retry-After", "5").status(503).json({ error: "service_unavailable" });
    return;
  }
  // bug: detalle completo al log, nada sensible al cliente
  console.error({ err, method: req.method, path: req.originalUrl }, "error no controlado");
  res.status(500).json({
    error: "internal_error",
    ...(isProduction ? {} : { message: String(err?.message), stack: err?.stack }),
  });
};
```

El handler queda limpio, sin `try/catch`:

```ts
ordersRouter.get("/:id", async (req, res) => {
  const result = await db.query("SELECT id, status, total FROM orders WHERE id = $1", [req.params.id]);
  if (result.rows.length === 0) {
    throw new HttpError(404, "order_not_found");
  }
  res.json(result.rows[0]);
});
```

Y `app.use(errorHandler)` va el último, después de todas las rutas.

## 3. Quitar el parche del proceso

Un `unhandledRejection` que llega al proceso significa que algo escapó a todo lo anterior. No hay forma segura de seguir: regístralo y sal con código 1 para que el orquestador reinicie.

```ts
process.on("unhandledRejection", (reason) => {
  console.error({ err: reason }, "unhandledRejection: saliendo");
  process.exit(1);
});
```

## Verificación

1. Para Postgres (`docker stop pg`) y lanza `curl -i localhost:3000/orders/1`: respuesta inmediata `503` con `Retry-After: 5`, y el proceso sigue vivo.
2. `curl -i localhost:3000/orders/999999` con la BD arriba: `404` con `{"error":"order_not_found"}`.
3. Fuerza un `TypeError` en una ruta de prueba con `NODE_ENV=production`: `500` sin `stack` en el cuerpo y con el stack completo en el log.

Si el paso 1 sigue colgando, hay una ruta que no pasa por Express 5 ni por `asyncHandler`: busca `async (req, res)` en routers montados con otra instancia.""",
            },
        ]
    },
    # 3) Validación con zod 4 en un middleware genérico y el getter de req.query.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Estoy validando a mano los `req.body` en Express 5 y ya me cansé. Quiero usar zod 4 en un middleware que sirva para body, query y params. Intenté `req.query = schema.parse(req.query)` y me truena con:

```
TypeError: Cannot set property query of #<IncomingMessage> which has only a getter
```

¿Cómo lo armo bien y con tipos?""",
            },
            {
                "role": "assistant",
                "content": r"""El error es un cambio de Express 5: `req.query` pasó a ser un **getter** que parsea la URL cada vez que lo lees. No se puede asignar (en módulos ESM, que van en modo estricto, la asignación lanza; en código no estricto se ignoraría en silencio, que es peor). La solución no es pelear con el getter, sino guardar lo validado en otro sitio: `res.locals`, que existe justo para pasar datos entre middlewares de una petición.

```ts
// src/http/validate.ts
import type { RequestHandler, Response } from "express";
import { z } from "zod";

export type RequestSchemas = {
  params?: z.ZodType;
  query?: z.ZodType;
  body?: z.ZodType;
};

// Para cada parte: el tipo de salida del schema, o undefined si no se validó
export type Validated<S extends RequestSchemas> = {
  [K in keyof RequestSchemas]-?: S[K] extends z.ZodType ? z.output<S[K]> : undefined;
};

type Issue = { location: keyof RequestSchemas; path: string; message: string };

export function validate<S extends RequestSchemas>(schemas: S): RequestHandler {
  return (req, res, next) => {
    const issues: Issue[] = [];
    const result: Record<string, unknown> = {};

    for (const location of ["params", "query", "body"] as const) {
      const schema = schemas[location];
      if (!schema) continue;
      const parsed = schema.safeParse(req[location]);
      if (parsed.success) {
        result[location] = parsed.data;
      } else {
        for (const issue of parsed.error.issues) {
          issues.push({ location, path: issue.path.map(String).join("."), message: issue.message });
        }
      }
    }

    if (issues.length > 0) {
      res.status(400).json({ error: "validation_failed", issues });
      return;
    }
    res.locals.validated = result;
    next();
  };
}

// Lectura tipada: el segundo argumento solo sirve para que TypeScript infiera S
export function validated<S extends RequestSchemas>(res: Response, _schemas: S): Validated<S> {
  return res.locals.validated as Validated<S>;
}
```

Uso:

```ts
// src/routes/orders.ts
import { Router } from "express";
import { z } from "zod";
import { validate, validated } from "../http/validate.js";
import { createOrder, listOrders } from "../orders/service.js";

const listSchemas = {
  query: z.object({
    // todo lo que llega por query es string: hay que coaccionar
    page: z.coerce.number().int().min(1).default(1),
    status: z.enum(["pending", "paid", "shipped"]).optional(),
  }),
};

const createSchemas = {
  body: z.object({
    customerEmail: z.email(),
    items: z
      .array(z.object({ sku: z.string().min(1), qty: z.number().int().positive() }))
      .min(1),
  }),
};

export const ordersRouter = Router();

ordersRouter.get("/", validate(listSchemas), async (_req, res) => {
  const { query } = validated(res, listSchemas);
  // query.page: number; query.status: "pending" | "paid" | "shipped" | undefined
  res.json(await listOrders(query.page, query.status));
});

ordersRouter.post("/", validate(createSchemas), async (_req, res) => {
  const { body } = validated(res, createSchemas);
  res.status(201).json(await createOrder(body));
});
```

Decisiones y por qué:

- **Schemas como constantes con nombre**, compartidas entre `validate` y `validated`. El tipo sale del mismo objeto que valida en runtime: no hay forma de que se desincronicen.
- **`safeParse` y no `parse`**: acumulo los errores de las tres partes en una sola respuesta. Con `parse` el cliente arreglaría un campo, reenviaría y descubriría el siguiente.
- **`issue.path.map(String)`**: en zod 4 el path es `PropertyKey[]` y puede contener símbolos; `join` directo sobre un símbolo lanza.
- **`z.email()`** es la forma de zod 4; `z.string().email()` sigue existiendo pero está deprecada.
- **`z.coerce.number()` en query**: `?page=2` llega como `"2"`. Ojo con su borde: `z.coerce.number()` convierte `""` en `0`, así que el `.min(1)` es lo que rechaza `?page=`.

Otro cambio de Express 5 que afecta a la query: el parser por defecto es `simple`, así que `?filter[status]=paid` ya no produce un objeto anidado. Si tu API dependía de eso, usa claves planas (`?status=paid`) o `app.set("query parser", "extended")`.

Verificación:

```bash
curl -s 'localhost:3000/orders?page=abc'
# 400 {"error":"validation_failed","issues":[{"location":"query","path":"page",...}]}
curl -s -X POST localhost:3000/orders -H 'content-type: application/json' \
  -d '{"customerEmail":"no-es-email","items":[]}'
# 400 con dos issues: body.customerEmail y body.items
curl -s 'localhost:3000/orders?page=2&status=paid'   # 200
```

Y en tipos: escribe `query.page.toFixed()` en el handler (compila) y `query.status.length` sin comprobar `undefined` (no compila). Eso confirma que la inferencia llega hasta la ruta.""",
            },
        ]
    },
    # 4) Multiturno: JWT con jose y luego revocación/logout.
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero autenticación con JWT en Express 5. ¿Cómo genero y verifico los tokens bien? Vi tutoriales con jsonwebtoken y otros con jose y no sé cuál usar.",
            },
            {
                "role": "assistant",
                "content": r"""Usa **`jose`**: es ESM, está tipada, se basa en Web Crypto y el mismo código funciona en Node, Bun, Deno y Workers. `jsonwebtoken` sigue funcionando, pero es CommonJS, solo Node y con API de callbacks en su origen.

Lo importante no es la librería, sino cuatro reglas que los tutoriales se saltan:

1. **Fija `algorithms` al verificar.** Si aceptas lo que diga la cabecera `alg`, abres la puerta a ataques de confusión de algoritmo.
2. **Verifica `iss` y `aud`.** Un token emitido para otro servicio con el mismo secreto no debe valer aquí.
3. **Caducidad corta** (5-15 min) para el token de acceso.
4. **Secreto largo y aleatorio** (32 bytes o más) leído del entorno, y fallo al arrancar si falta.

```ts
// src/auth/tokens.ts
import { SignJWT, jwtVerify } from "jose";

const ISSUER = "https://api.example.com";
const AUDIENCE = "https://app.example.com";
const ACCESS_TTL = "15m";

export type AccessClaims = { sub: string; role: "user" | "admin" };

function loadSecret(): Uint8Array {
  const raw = process.env.JWT_SECRET;
  if (!raw || raw.length < 32) {
    throw new Error("JWT_SECRET debe existir y tener al menos 32 caracteres aleatorios");
  }
  return new TextEncoder().encode(raw);
}

const secret = loadSecret();

export function signAccessToken(claims: AccessClaims): Promise<string> {
  return new SignJWT({ role: claims.role })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(claims.sub)
    .setIssuer(ISSUER)
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .setExpirationTime(ACCESS_TTL)
    .sign(secret);
}

export async function verifyAccessToken(token: string): Promise<AccessClaims> {
  const { payload } = await jwtVerify(token, secret, {
    algorithms: ["HS256"],
    issuer: ISSUER,
    audience: AUDIENCE,
  });
  if (typeof payload.sub !== "string" || (payload.role !== "user" && payload.role !== "admin")) {
    throw new Error("claims inválidos");
  }
  return { sub: payload.sub, role: payload.role };
}
```

```ts
// src/auth/middleware.ts
import type { RequestHandler } from "express";
import { errors } from "jose";
import { type AccessClaims, verifyAccessToken } from "./tokens.js";

declare global {
  namespace Express {
    interface Request {
      auth?: AccessClaims;
    }
  }
}

export const requireAuth: RequestHandler = async (req, res, next) => {
  const header = req.get("authorization");
  // navegador: cookie httpOnly; móvil o servidor: cabecera Bearer
  const token = header?.startsWith("Bearer ") ? header.slice(7) : req.cookies?.access_token;
  if (!token) {
    res.status(401).json({ error: "missing_token" });
    return;
  }
  let claims: AccessClaims;
  try {
    claims = await verifyAccessToken(token);
  } catch (err) {
    const code = err instanceof errors.JWTExpired ? "token_expired" : "invalid_token";
    res.status(401).json({ error: code });
    return;
  }
  req.auth = claims;
  next();
};
```

`next()` va fuera del `try` a propósito: así un error de una ruta posterior nunca se confunde con un token inválido.

El login emite el token. Para navegador, en cookie `httpOnly` (el JavaScript de la página no puede leerla, así que un XSS no la roba); `req.cookies` requiere `app.use(cookieParser())`:

```ts
authRouter.post("/login", async (req, res) => {
  const user = await verifyCredentials(req.body?.email, req.body?.password); // argon2 o bcrypt
  if (!user) {
    res.status(401).json({ error: "invalid_credentials" });
    return;
  }
  const token = await signAccessToken({ sub: user.id, role: user.role });
  res.cookie("access_token", token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: 15 * 60 * 1000,
  });
  res.sendStatus(204);
});
```

Verificación: un token firmado con otro `aud` debe dar `401 invalid_token`; uno con `setExpirationTime("1s")` tras dos segundos, `401 token_expired`; y uno con `alg: "none"` construido a mano, `401`.""",
            },
            {
                "role": "user",
                "content": "Bien. ¿Y el logout? Si el token vale 15 minutos, aunque borre la cookie, alguien que lo haya copiado lo sigue usando, ¿no?",
            },
            {
                "role": "assistant",
                "content": r"""Exacto: un JWT sin estado **no se puede revocar** antes de su `exp`. Borrar la cookie solo desconecta a ese navegador. Para revocar necesitas estado en el servidor, y la pregunta es cuánto y dónde.

| Opción | Revocación | Coste por petición | Cuándo |
|---|---|---|---|
| Access corto + refresh rotativo en BD | en ≤ TTL del access (15 min) | ninguno (el access se verifica sin BD) | la mayoría de APIs |
| Lista de bloqueo por `jti` en Redis | inmediata | una consulta a Redis | revocación urgente puntual |
| Sesión en servidor (`express-session` + Redis) | inmediata (`req.session.destroy()`) | una consulta a Redis | apps web clásicas, banca, back-office |

Si necesitas revocación inmediata en todas las peticiones, la lista de bloqueo te obliga a consultar Redis siempre, y entonces el JWT ya no aporta nada frente a una sesión: usa sesiones. Si te vale una ventana de 15 minutos, la primera opción es la equilibrada.

Refresh tokens rotativos, con detección de reutilización:

```ts
// src/auth/refresh.ts
import { createHash, randomBytes, randomUUID } from "node:crypto";

export type RefreshRecord = {
  tokenHash: string;
  userId: string;
  familyId: string;
  expiresAt: Date;
  revokedAt: Date | null;
};

// Implementación con tu BD; tabla refresh_tokens con índice único en token_hash
export interface RefreshTokenStore {
  insert(record: RefreshRecord): Promise<void>;
  findByHash(tokenHash: string): Promise<RefreshRecord | null>;
  revoke(tokenHash: string): Promise<void>;
  revokeFamily(familyId: string): Promise<void>;
}

const REFRESH_TTL_MS = 30 * 24 * 60 * 60 * 1000;

// En BD solo se guarda el hash: una filtración de la tabla no da tokens usables
export const hashToken = (token: string) => createHash("sha256").update(token).digest("hex");

export async function issueRefreshToken(
  store: RefreshTokenStore,
  userId: string,
  familyId: string = randomUUID(),
): Promise<string> {
  const token = randomBytes(32).toString("base64url");
  await store.insert({
    tokenHash: hashToken(token),
    userId,
    familyId,
    expiresAt: new Date(Date.now() + REFRESH_TTL_MS),
    revokedAt: null,
  });
  return token;
}

export async function rotateRefreshToken(store: RefreshTokenStore, presented: string) {
  const record = await store.findByHash(hashToken(presented));
  if (!record || record.expiresAt.getTime() < Date.now()) return null;
  if (record.revokedAt) {
    // alguien presenta un token ya rotado: o lo robaron o lo reenvía un atacante; se corta la familia
    await store.revokeFamily(record.familyId);
    return null;
  }
  await store.revoke(record.tokenHash);
  const refreshToken = await issueRefreshToken(store, record.userId, record.familyId);
  return { userId: record.userId, refreshToken };
}
```

El logout revoca la familia entera y limpia las cookies:

```ts
authRouter.post("/logout", async (req, res) => {
  const presented: string | undefined = req.cookies?.refresh_token;
  if (presented) {
    const record = await refreshStore.findByHash(hashToken(presented));
    if (record) await refreshStore.revokeFamily(record.familyId);
  }
  res.clearCookie("access_token");
  res.clearCookie("refresh_token", { path: "/auth" });
  res.sendStatus(204);
});
```

La cookie del refresh va con `path: "/auth"`, `httpOnly`, `secure` y `sameSite: "strict"`: así solo viaja a los endpoints de autenticación y no en cada petición.

Un borde que conviene decidir: dos pestañas que refrescan a la vez presentan el mismo token; la segunda lo verá revocado y cortará la familia, cerrando la sesión del usuario. Para evitarlo, haz la revocación atómica (`UPDATE … SET revoked_at = now() WHERE token_hash = $1 AND revoked_at IS NULL RETURNING …`) y concede unos segundos de gracia a un token recién rotado antes de tratarlo como reutilización.

Verificación del flujo: login → refresh (token A pasa a B) → refresh con A otra vez → `401`, y a continuación refresh con B también `401`, porque la familia quedó revocada.""",
            },
        ]
    },
    # 5) Error de CORS en el navegador con credenciales; helmet y rate limiting.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Desde el front (https://app.example.com) hago `fetch("https://api.example.com/me", { credentials: "include", headers: { Authorization: `Bearer ${token}` } })` y el navegador me tira:

```
Access to fetch at 'https://api.example.com/me' from origin 'https://app.example.com' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

En el server (Express 5) tengo:

```js
app.use(requireAuth);
app.use(cors({ origin: "*" }));
app.use("/me", meRouter);
```

Con Postman funciona perfecto.""",
            },
            {
                "role": "assistant",
                "content": r"""Hay dos errores y el mensaje señala el primero.

**1. Orden de middlewares.** La cabecera `Authorization` hace que el navegador mande antes un **preflight** (`OPTIONS`) sin credenciales. Ese `OPTIONS` entra por `requireAuth`, que responde `401` sin cabeceras CORS, y `cors` nunca llega a ejecutarse. De ahí «No 'Access-Control-Allow-Origin' header». Postman funciona porque no aplica CORS ni hace preflight: CORS es una política del navegador, no del servidor.

**2. `origin: "*"` con credenciales.** Aunque arregles el orden, con `credentials: "include"` el navegador rechaza el comodín: exige el origen exacto en `Access-Control-Allow-Origin` y además `Access-Control-Allow-Credentials: true`. El siguiente error que verías sería «The value of the 'Access-Control-Allow-Origin' header in the response must not be the wildcard '*' when the request's credentials mode is 'include'».

Configuración corregida, con lista blanca, `helmet` y límite de peticiones:

```ts
// src/http/security.ts
import cors, { type CorsOptions } from "cors";
import type { Express } from "express";
import { rateLimit } from "express-rate-limit";
import helmet from "helmet";

const allowedOrigins = new Set(
  (process.env.CORS_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
);

const corsOptions: CorsOptions = {
  origin(origin, callback) {
    // sin cabecera Origin: curl, servidor a servidor o mismo origen
    if (!origin || allowedOrigins.has(origin)) return callback(null, true);
    // origen no permitido: sin cabeceras CORS; el navegador bloquea y el servidor no da 500
    return callback(null, false);
  },
  credentials: true,
  methods: ["GET", "POST", "PUT", "PATCH", "DELETE"],
  allowedHeaders: ["Content-Type", "Authorization"],
  maxAge: 600, // el navegador cachea el preflight 10 minutos
};

export function applySecurity(app: Express): void {
  // una sola capa de proxy (balanceador); `true` permitiría falsear la IP con X-Forwarded-For
  app.set("trust proxy", 1);
  app.use(helmet());
  // cors antes que cualquier middleware que pueda rechazar: también responde los OPTIONS
  app.use(cors(corsOptions));
  app.use(
    "/auth",
    rateLimit({
      windowMs: 15 * 60 * 1000,
      limit: 20, // en v7 se llama limit; max sigue aceptándose
      standardHeaders: "draft-7",
      legacyHeaders: false,
    }),
  );
}
```

```ts
// src/app.ts (extracto del orden)
applySecurity(app);
app.use(express.json({ limit: "100kb" }));
app.use(cookieParser());
app.use("/me", requireAuth, meRouter); // la auth por router, no global
```

Por qué cada pieza:

- **`app.use(cors(...))` cubre los preflights.** Responde los `OPTIONS` con `204` y corta ahí. No añadas `app.options("*", cors())`: en Express 5 `"*"` ya no es una ruta válida y fallará al arrancar.
- **`callback(null, false)` en vez de lanzar un error**: un origen no permitido no es un fallo del servidor; devolver error produce un 500 que ensucia los logs.
- **`trust proxy`**: detrás de un balanceador, sin él `req.ip` es la IP del balanceador y el límite se aplica a todos los usuarios juntos. `express-rate-limit` v7 lo detecta y avisa con `ERR_ERL_UNEXPECTED_X_FORWARDED_FOR` cuando ve `X-Forwarded-For` sin `trust proxy`.
- **Store compartido**: el store por defecto vive en memoria de cada proceso. Con tres réplicas, el límite real es el triple. Con varias instancias usa un store en Redis (por ejemplo el paquete `rate-limit-redis`).
- **`helmet()`** pone cabeceras seguras por defecto. Una que puede sorprenderte: `Cross-Origin-Resource-Policy: same-origin`. Si la API sirve imágenes que el front carga con `<img>`, ajusta `helmet({ crossOriginResourcePolicy: { policy: "cross-origin" } })`.

Verificación del preflight sin navegador:

```bash
curl -i -X OPTIONS https://api.example.com/me \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization"
```

Debe devolver `204` con `Access-Control-Allow-Origin: https://app.example.com`, `Access-Control-Allow-Credentials: true` y `Vary: Origin`. Repite con `-H "Origin: https://evil.example"`: misma respuesta pero sin `Access-Control-Allow-Origin`.""",
            },
        ]
    },
    # 6) EN: logging estructurado con pino y pino-http.
    {
        "messages": [
            {
                "role": "user",
                "content": "What's a solid pino setup for an Express 5 API? I want a request id that follows every log line, no tokens or passwords in the logs, pretty output locally, and errors logged at the right level.",
            },
            {
                "role": "assistant",
                "content": r"""Use `pino` for the logger and `pino-http` for per-request logging. The key idea: **one root logger, one child logger per request** (`req.log`), so the request id is attached once and appears on every line without you passing it around.

```ts
// src/logging.ts
import { randomUUID } from "node:crypto";
import pino from "pino";
import pinoHttp from "pino-http";

const isDev = process.env.NODE_ENV === "development";

export const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  redact: {
    paths: [
      "req.headers.authorization",
      "req.headers.cookie",
      'res.headers["set-cookie"]',
      "*.password",
      "*.token",
    ],
    censor: "[redacted]",
  },
  // pretty only for humans at a terminal; production writes JSON lines to stdout
  transport: isDev ? { target: "pino-pretty", options: { colorize: true } } : undefined,
});

const MAX_INCOMING_ID_LENGTH = 128;

export const httpLogger = pinoHttp({
  logger,
  genReqId(req, res) {
    // reuse the id from the edge proxy if present, so logs correlate across services
    const incoming = req.headers["x-request-id"];
    const id =
      typeof incoming === "string" && incoming.length <= MAX_INCOMING_ID_LENGTH ? incoming : randomUUID();
    res.setHeader("x-request-id", id);
    return id;
  },
  customLogLevel(_req, res, err) {
    if (err || res.statusCode >= 500) return "error";
    if (res.statusCode >= 400) return "warn";
    return "info";
  },
  // req.log lines carry only the request id, not the whole serialized request
  quietReqLogger: true,
  autoLogging: { ignore: (req) => req.url === "/health" },
});
```

```ts
// src/app.ts (excerpt)
import express from "express";
import { httpLogger } from "./logging.js";

const app = express();
app.use(httpLogger); // first, so even 404s and body-parser errors are logged

app.post("/orders", express.json(), async (req, res) => {
  const order = await createOrder(req.body);
  req.log.info({ orderId: order.id }, "order created"); // includes the request id
  res.status(201).json(order);
});
```

Design decisions:

- **Accept an incoming `x-request-id`, but bound its length.** It lets you follow one request from the load balancer through several services. The length check stops a client from stuffing kilobytes into every log line.
- **Redaction happens in the logger, not at call sites.** People will eventually log a whole object; `redact` makes that safe by default. `*.password` matches one level deep (`{ user: { password } }`), so keep sensitive fields shallow or add explicit paths. Wildcards have a small CPU cost, which is why I list a handful of paths rather than dozens.
- **pino-http does not log bodies.** Keep it that way: bodies are where PII and secrets live. Log identifiers (`orderId`), not payloads.
- **Levels by status code.** A 404 is a `warn`, a 500 is an `error`. That gives you a meaningful alert on `level >= 50` without paging anyone for client mistakes.
- **JSON to stdout in production.** No file rotation inside the process, no transport threads to tune. Docker, Kubernetes or systemd capture stdout, and your collector (Loki, Datadog, CloudWatch) indexes the fields. `pino-pretty` is a devDependency; never ship it to production.

For the error handler, log through `req.log` so failures carry the same id:

```ts
app.use((err: unknown, req: express.Request, res: express.Response, _next: express.NextFunction) => {
  req.log.error({ err }, "unhandled error");
  res.status(500).json({ error: "internal_error", requestId: req.id });
});
```

Returning `requestId` to the client is the cheapest support tool you will ever build: a user reports the id and you find the exact log lines.

Verification:

```bash
curl -s -i -H "x-request-id: test-123" -H "Authorization: Bearer secret" localhost:3000/orders
```

The response carries `x-request-id: test-123`; the completion log line contains `"id":"test-123"`, `"authorization":"[redacted]"` and a `responseTime` field. Hit `/health` and confirm nothing is logged.""",
            },
        ]
    },
    # 7) Subida de archivos con multer 2: límites, magic bytes y errores.
    {
        "messages": [
            {
                "role": "user",
                "content": "En el equipo tenemos que permitir subir avatares y PDFs (máximo 5 MB) en una API con Express 5. ¿Cómo lo hacemos con multer sin abrir un agujero de seguridad? ¿Basta con revisar el mimetype?",
            },
            {
                "role": "assistant",
                "content": r"""No basta: `file.mimetype` lo declara el **cliente** en la petición multipart. Cualquiera puede mandar un ejecutable diciendo que es `image/png`. Úsalo solo como filtro barato y comprueba el tipo real leyendo los primeros bytes del archivo (*magic bytes*) cuando ya está en disco.

Asumo multer 2 (misma API que 1.x, con correcciones de seguridad; actualizad si seguís en 1.x) y `file-type`, que es solo ESM.

```ts
// src/uploads/upload.ts
import { randomUUID } from "node:crypto";
import { mkdir, rename, unlink } from "node:fs/promises";
import path from "node:path";
import { Router } from "express";
import { fileTypeFromFile } from "file-type";
import multer from "multer";

const TMP_DIR = path.resolve("uploads/tmp");
const FINAL_DIR = path.resolve("uploads/files");
const MAX_BYTES = 5 * 1024 * 1024;

// tipo MIME real -> extensión que guardaremos (no la que trae el cliente)
const ALLOWED = new Map([
  ["image/png", "png"],
  ["image/jpeg", "jpg"],
  ["application/pdf", "pdf"],
]);

const upload = multer({
  storage: multer.diskStorage({
    destination: TMP_DIR, // como string, multer crea la carpeta si no existe
    filename: (_req, _file, cb) => cb(null, randomUUID()), // nunca el nombre original
  }),
  limits: { fileSize: MAX_BYTES, files: 1, fields: 5 },
  fileFilter: (_req, file, cb) => {
    // filtro previo no fiable: solo evita escribir a disco lo obviamente inválido
    cb(null, ALLOWED.has(file.mimetype));
  },
});

export const uploadsRouter = Router();

uploadsRouter.post("/", upload.single("file"), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ error: "file_required_or_type_not_allowed" });
    return;
  }
  const detected = await fileTypeFromFile(req.file.path);
  const extension = detected ? ALLOWED.get(detected.mime) : undefined;
  if (!detected || !extension) {
    await unlink(req.file.path);
    res.status(415).json({ error: "unsupported_media_type" });
    return;
  }
  await mkdir(FINAL_DIR, { recursive: true });
  const storedName = `${randomUUID()}.${extension}`;
  await rename(req.file.path, path.join(FINAL_DIR, storedName));
  res.status(201).json({ id: storedName, mime: detected.mime, size: req.file.size });
});

// Errores de multer -> códigos HTTP útiles; el resto sigue al manejador general
export const uploadErrorHandler = (
  err: unknown,
  _req: unknown,
  res: import("express").Response,
  next: import("express").NextFunction,
) => {
  if (err instanceof multer.MulterError) {
    const status = err.code === "LIMIT_FILE_SIZE" ? 413 : 400;
    res.status(status).json({ error: err.code, field: err.field });
    return;
  }
  next(err);
};
```

```ts
// src/app.ts (extracto)
app.use("/uploads", uploadsRouter, uploadErrorHandler);
```

Por qué así:

- **Nombre aleatorio y extensión derivada del contenido.** El nombre original puede traer `../../`, caracteres raros o `.html`. Guárdalo, si lo necesitáis, como dato en la BD, nunca como ruta.
- **`limits` es la defensa real contra abuso.** Multer corta el stream al pasar `fileSize` y lanza `LIMIT_FILE_SIZE`; sin límite, un cliente puede llenar el disco. `files: 1` y `fields: 5` cierran la puerta a multipart con miles de partes.
- **`fileFilter` con `cb(null, false)`** descarta sin error; por eso el handler distingue «no hay archivo» con un 400. Si llamas a `cb(new Error(...))`, termina en un 500 salvo que lo mapees.
- **Validación en dos fases**: el filtro evita escribir basura evidente; `fileTypeFromFile` decide. Si el contenido no coincide, se borra el temporal antes de responder.
- **Nada de SVG**: es XML que puede llevar JavaScript. Si algún día lo aceptáis, servidlo con `Content-Disposition: attachment` o desde un dominio aparte.

Para archivos grandes (vídeos, cientos de MB), no paséis los bytes por la API: emitid una **URL prefirmada** de S3 (`getSignedUrl` de `@aws-sdk/s3-request-presigner` con un `PutObjectCommand`) y que el cliente suba directo al bucket. La API solo firma y luego valida el objeto cuando S3 notifica la subida.

Verificación:

```bash
curl -i -F "file=@avatar.png" localhost:3000/uploads               # 201, mime image/png
cp programa.exe falso.png && curl -i -F "file=@falso.png;type=image/png" localhost:3000/uploads   # 415
head -c 6000000 /dev/urandom > grande.png && curl -i -F "file=@grande.png;type=image/png" localhost:3000/uploads   # 413 LIMIT_FILE_SIZE
```

Tras el segundo caso, `uploads/tmp` debe quedar vacío.""",
            },
        ]
    },
    # 8) Avanzado: bloqueo del event loop por CPU síncrona.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""En producción el login tarda unos 300 ms, pero en los picos (20 logins por segundo más o menos) toda la API se vuelve lenta: hasta `/health` tarda 4-5 segundos y el balanceador marca las instancias como caídas. El login hace esto:

```ts
const derived = crypto.pbkdf2Sync(password, user.salt, 600_000, 32, "sha256");
const ok = crypto.timingSafeEqual(derived, user.passwordHash);
```

Node 22, Express 5, 2 vCPU por instancia.""",
            },
            {
                "role": "assistant",
                "content": r"""El problema es `pbkdf2Sync`: son unos 300 ms de CPU **en el hilo principal**. Node ejecuta tu JavaScript en un solo hilo; mientras ese hilo calcula el hash, no atiende nada más, ni siquiera `/health`.

La cuenta lo confirma: 20 logins/s × 0,3 s = 6 s de CPU por cada segundo real en un hilo que solo tiene 1 s. La cola crece sin parar mientras dura el pico, y cualquier petición, por trivial que sea, espera detrás.

## 1. Medirlo antes de tocar nada

```ts
// src/metrics/event-loop.ts
import { monitorEventLoopDelay } from "node:perf_hooks";

const NS_PER_MS = 1e6;
const REPORT_EVERY_MS = 10_000;

export function startEventLoopMonitor(log: (data: Record<string, number>) => void): void {
  const histogram = monitorEventLoopDelay({ resolution: 20 });
  histogram.enable();
  setInterval(() => {
    // el histograma mide en nanosegundos
    log({
      p50Ms: histogram.percentile(50) / NS_PER_MS,
      p99Ms: histogram.percentile(99) / NS_PER_MS,
      maxMs: histogram.max / NS_PER_MS,
    });
    histogram.reset();
  }, REPORT_EVERY_MS).unref();
}
```

En reposo, `p99Ms` debe estar en un dígito. Si en el pico ves cientos o miles de ms, el event loop está bloqueado. Para saber **qué** lo bloquea, `node --cpu-prof dist/server.js`, reproduce la carga, para el proceso y abre el `.cpuprofile` generado en Chrome DevTools (pestaña Performance): `pbkdf2Sync` aparecerá como una barra ancha en el hilo principal.

## 2. Arreglo: sacar la CPU del hilo principal

La versión asíncrona de `pbkdf2` hace el mismo cálculo en el **threadpool de libuv**, no en el hilo de JavaScript:

```ts
// src/auth/password.ts
import { pbkdf2, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";

const pbkdf2Async = promisify(pbkdf2);

const ITERATIONS = 600_000; // recomendación OWASP para PBKDF2-HMAC-SHA256
const KEY_LENGTH = 32;

export async function verifyPassword(password: string, salt: Buffer, expected: Buffer): Promise<boolean> {
  const derived = await pbkdf2Async(password, salt, ITERATIONS, KEY_LENGTH, "sha256");
  return derived.length === expected.length && timingSafeEqual(derived, expected);
}
```

Con esto, `/health` responde aunque haya veinte hashes en curso. Pero el cambio no crea CPU: con 2 vCPU harás como mucho unos 6-7 logins/s por instancia (2 núcleos / 0,3 s). Lo que cambia es que el exceso **espera en la cola del pool** en vez de congelar toda la API. Para absorber 20/s necesitas más instancias o núcleos; y conviene un rate limit en `/login`, que además frena ataques de fuerza bruta.

Ajuste del pool: tiene 4 hilos por defecto y lo comparten `fs`, `dns.lookup`, `zlib` y `crypto`. Si veinte hashes lo ocupan, las lecturas de disco también esperan. Con 2 vCPU no ganas nada subiendo los hilos de cómputo; lo sensato es dejar `UV_THREADPOOL_SIZE` en 4 y limitar la concurrencia de logins. En máquinas grandes, fíjalo con la variable de entorno al arrancar (en el Dockerfile o el manifiesto), no desde el código, porque el pool se dimensiona en su primer uso.

## 3. CPU que no está en libuv

`pbkdf2`, `scrypt` y `zlib` tienen versión asíncrona. Un `JSON.parse` de 50 MB, generar un PDF o un cálculo propio no la tienen: van a un **worker thread**. Con un pool como Piscina:

```ts
// src/reports/pool.ts
import { Piscina } from "piscina";

export const reportPool = new Piscina({
  filename: new URL("./parse-report.worker.js", import.meta.url).href,
  maxThreads: 2, // no más que núcleos disponibles
});
```

```ts
// src/reports/parse-report.worker.ts
type ReportRow = { sku: string; total: number };

export default function parseReport(raw: string): ReportRow[] {
  const rows = JSON.parse(raw) as ReportRow[];
  return rows.filter((row) => row.total > 0);
}
```

En la ruta: `const rows = await reportPool.run(raw);`. Ojo al coste: los datos se copian entre hilos; para cargas pequeñas el viaje cuesta más que el cálculo.

## 4. Verificación

Antes y después, dos cargas simultáneas:

```bash
npx autocannon -c 20 -d 30 -m POST -H "content-type: application/json" \
  -b '{"email":"a@example.com","password":"x"}' http://localhost:3000/login
npx autocannon -c 5 -d 30 http://localhost:3000/health
```

Compara la columna 99 % de `/health`: con `pbkdf2Sync` estará en segundos; con la versión asíncrona, en milisegundos. El `p99Ms` del monitor debe bajar en la misma proporción. Si `/health` mejora pero el login sigue lento, ya no es un bloqueo: es falta de CPU, y se arregla escalando.""",
            },
        ]
    },
    # 9) Multiturno avanzado: graceful shutdown y errores fatales del proceso.
    {
        "messages": [
            {
                "role": "user",
                "content": "Cada vez que hacemos deploy en Kubernetes salen unos cuantos 502 en el balanceador. La API es Express 5 con un pool de pg. ¿Cómo implemento un apagado ordenado en condiciones?",
            },
            {
                "role": "assistant",
                "content": r"""Los 502 en cada despliegue suelen venir de una de dos cosas: el proceso muere con peticiones en curso, o el balanceador sigue enviando tráfico a un pod que ya está cerrando. Hay que resolver las dos.

La secuencia correcta al recibir `SIGTERM`:

1. Marcar la instancia como **no lista** (`/readyz` devuelve 503).
2. Esperar unos segundos a que el balanceador deje de enviar tráfico.
3. `server.close()`: no acepta conexiones nuevas y espera a que terminen las peticiones en curso.
4. Cerrar recursos (pool de BD, colas).
5. Salir. Con un **temporizador de seguridad** por si algo se cuelga.

```ts
// src/server.ts
import { setTimeout as sleep } from "node:timers/promises";
import express from "express";
import { pool } from "./db.js";
import { apiRouter } from "./routes/index.js";

const PORT = Number(process.env.PORT ?? 3000);
const READINESS_GRACE_MS = 5_000; // tiempo para que el balanceador vea el 503
const SHUTDOWN_TIMEOUT_MS = 20_000; // menor que terminationGracePeriodSeconds

let ready = true;
let shuttingDown = false;

const app = express();
app.get("/livez", (_req, res) => {
  res.sendStatus(200);
});
app.get("/readyz", (_req, res) => {
  res.sendStatus(ready ? 200 : 503);
});
app.use(apiRouter);

const server = app.listen(PORT, () => {
  console.info(`Escuchando en ${PORT}`);
});

function closeServer(): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
    // keep-alive inactivas: desde Node 19 close() ya las cierra; explícito no hace daño
    server.closeIdleConnections();
  });
}

export async function shutdown(reason: string, exitCode = 0): Promise<void> {
  if (shuttingDown) return;
  shuttingDown = true;
  ready = false;
  console.info({ reason }, "apagado ordenado iniciado");

  const forceExit = setTimeout(() => {
    console.error("apagado no terminó a tiempo: cierro conexiones y salgo");
    server.closeAllConnections();
    process.exit(1);
  }, SHUTDOWN_TIMEOUT_MS);
  forceExit.unref();

  try {
    await sleep(READINESS_GRACE_MS);
    await closeServer();
    await pool.end();
    console.info("apagado limpio");
  } catch (err) {
    console.error({ err }, "error durante el apagado");
    exitCode = 1;
  }
  process.exit(exitCode);
}

process.once("SIGTERM", () => void shutdown("SIGTERM"));
process.once("SIGINT", () => void shutdown("SIGINT"));
```

En el manifiesto:

```yaml
spec:
  terminationGracePeriodSeconds: 30
  containers:
    - name: api
      readinessProbe:
        httpGet: { path: /readyz, port: 3000 }
        periodSeconds: 2
      livenessProbe:
        httpGet: { path: /livez, port: 3000 }
      lifecycle:
        preStop:
          exec:
            command: ["sleep", "5"]
```

Por qué cada número:

- **`preStop` + espera de readiness.** Kubernetes envía `SIGTERM` y, en paralelo, saca el pod de los endpoints; el balanceador tarda unos segundos en enterarse. Sin esa pausa, el pod cierra mientras aún le llega tráfico: ese es tu 502. El `preStop` con `sleep` necesita el binario `sleep` en la imagen (no lo hay en distroless); en Kubernetes 1.30+ existe la acción `sleep` nativa del `preStop`.
- **`SHUTDOWN_TIMEOUT_MS` < `terminationGracePeriodSeconds`.** Si te pasas, Kubernetes manda `SIGKILL` y no hay limpieza. Cuenta: 5 s de `preStop` + 5 s de gracia + hasta 20 s de peticiones lentas cabe justo en 30.
- **Liveness separada de readiness.** Si `/livez` devolviera 503 al apagar, Kubernetes podría reiniciar el contenedor en mitad del cierre.
- **`process.exit` explícito al final**: algún handle olvidado (un `setInterval`, un cliente de Redis) puede mantener vivo el proceso; el apagado debe terminar de forma determinista.

Requisito previo: que la señal llegue a Node. Con `CMD npm start` en el Dockerfile, `npm` recibe el `SIGTERM` y no siempre lo reenvía; usa `CMD ["node", "dist/server.js"]`.

Verificación: con una ruta de prueba que tarde 3 s, lanza `curl localhost:3000/lenta &` y justo después `kill -TERM <pid>`. El curl debe completar con 200, `/readyz` debe dar 503 durante la gracia, una petición nueva tras el `close` debe ver la conexión rechazada, y el proceso debe salir con código 0.""",
            },
            {
                "role": "user",
                "content": "Ok. ¿Y qué hago con `unhandledRejection` y `uncaughtException`? Hay gente que los captura para que el proceso no muera nunca.",
            },
            {
                "role": "assistant",
                "content": r"""Capturarlos para seguir vivo es un error. Capturarlos para **registrar y salir de forma controlada** es lo correcto.

- **`uncaughtException`**: una excepción atravesó toda la pila sin que nadie la capturase. El proceso puede quedar con estado a medias (un lock sin soltar, una transacción abierta, un objeto mutado a mitad). La documentación de Node lo dice explícitamente: no es seguro reanudar. Registra y sal **ya**, sin apagado ordenado, porque el propio apagado podría depender del estado corrupto.
- **`unhandledRejection`**: desde Node 15, si no hay handler, se convierte en excepción y el proceso termina. Si registras un handler, anulas ese comportamiento: el proceso sigue como si nada y la petición afectada se queda colgada. Aquí sí es razonable un apagado ordenado, porque un rechazo suele ser un fallo localizado y las demás peticiones en curso pueden terminar.

```ts
// src/process-handlers.ts
import { shutdown } from "./server.js";

process.on("unhandledRejection", (reason) => {
  console.error({ err: reason }, "unhandledRejection");
  void shutdown("unhandledRejection", 1);
});

process.on("uncaughtException", (err, origin) => {
  console.error({ err, origin }, "uncaughtException: salida inmediata");
  process.exit(1);
});
```

Importa este módulo una sola vez, al principio de `server.ts`.

Qué consigues:

- El fallo **se ve**: queda en el log con stack y el reinicio del pod aparece en las métricas. Un proceso que «nunca muere» esconde el bug durante semanas.
- La disponibilidad no sufre: Kubernetes reinicia el contenedor y las otras réplicas absorben el tráfico mientras tanto.
- El código de salida 1 distingue un crash de un apagado normal (0) en los eventos del pod.

En Express 5 los errores de las rutas, síncronos o `async`, ya llegan al manejador de errores; estos dos handlers solo deberían saltar con fallos fuera de una petición: un `setInterval` que lanza, un `EventEmitter` que emite `'error'` sin listener, una promesa lanzada sin `await` («fire and forget»). Cada vez que salten en producción, el arreglo es capturar el error en el origen, no ampliar el handler global.

Verificación: añade temporalmente `setTimeout(() => Promise.reject(new Error("prueba")), 1000)` y comprueba que aparece el log `unhandledRejection`, que las peticiones en curso terminan y que el proceso sale con código 1 (`echo $?`). Con `setTimeout(() => { throw new Error("prueba") }, 1000)` debe salir con 1 de inmediato.""",
            },
        ]
    },
    # ------------------------------------------------------------------
    # NestJS 10/11 (10-18)
    # ------------------------------------------------------------------
    # 10) Principiante: módulos, controladores, providers y DI.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Vengo de Express y empiezo con NestJS 11. No entiendo bien qué es un módulo, un controlador y un provider, ni cómo funciona la inyección de dependencias. ¿Me lo explicas con un ejemplo de usuarios?",
            },
            {
                "role": "assistant",
                "content": r"""Las tres piezas reparten lo que en Express sueles mezclar en un router:

- **Controlador**: traduce HTTP a llamadas de código. Lee parámetros, llama a un servicio y devuelve el resultado. Sin lógica de negocio.
- **Provider**: cualquier clase marcada con `@Injectable()` que Nest puede crear e inyectar: servicios, repositorios, clientes externos.
- **Módulo**: la unidad de organización. Declara qué controladores y providers tiene, qué **exporta** a otros módulos y qué **importa** de ellos.

La inyección de dependencias funciona así: escribes en el constructor qué necesitas (`constructor(private readonly repo: UsersRepository)`) y Nest, al arrancar, crea una instancia de cada provider (por defecto, **una sola para toda la app**) y la pasa donde se pide. Sabe qué pasar porque TypeScript emite el tipo del parámetro como metadato (`emitDecoratorMetadata` en el `tsconfig.json` que genera `nest new`), y ese tipo es la clave de búsqueda.

Proyecto generado con `nest new` (CommonJS, imports sin extensión):

```ts
// src/users/users.repository.ts
import { Injectable } from "@nestjs/common";

export interface User {
  id: number;
  name: string;
  email: string;
}

@Injectable()
export class UsersRepository {
  private readonly users = new Map<number, User>();
  private nextId = 1;

  findAll(): User[] {
    return [...this.users.values()];
  }

  findById(id: number): User | undefined {
    return this.users.get(id);
  }

  create(data: Omit<User, "id">): User {
    const user: User = { id: this.nextId++, ...data };
    this.users.set(user.id, user);
    return user;
  }
}
```

```ts
// src/users/users.service.ts
import { Injectable, NotFoundException } from "@nestjs/common";
import { User, UsersRepository } from "./users.repository";

@Injectable()
export class UsersService {
  constructor(private readonly repo: UsersRepository) {}

  findAll(): User[] {
    return this.repo.findAll();
  }

  findOne(id: number): User {
    const user = this.repo.findById(id);
    if (!user) {
      // Nest convierte esta excepción en un 404 con cuerpo JSON
      throw new NotFoundException(`User ${id} not found`);
    }
    return user;
  }

  create(name: string, email: string): User {
    return this.repo.create({ name, email });
  }
}
```

```ts
// src/users/users.controller.ts
import { Body, Controller, Get, Param, ParseIntPipe, Post } from "@nestjs/common";
import { User } from "./users.repository";
import { UsersService } from "./users.service";

@Controller("users")
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  findAll(): User[] {
    return this.usersService.findAll();
  }

  @Get(":id")
  findOne(@Param("id", ParseIntPipe) id: number): User {
    return this.usersService.findOne(id);
  }

  @Post()
  create(@Body() body: { name: string; email: string }): User {
    return this.usersService.create(body.name, body.email);
  }
}
```

```ts
// src/users/users.module.ts
import { Module } from "@nestjs/common";
import { UsersController } from "./users.controller";
import { UsersRepository } from "./users.repository";
import { UsersService } from "./users.service";

@Module({
  controllers: [UsersController],
  providers: [UsersService, UsersRepository],
  exports: [UsersService], // el repositorio queda privado del módulo
})
export class UsersModule {}
```

```ts
// src/app.module.ts
import { Module } from "@nestjs/common";
import { UsersModule } from "./users/users.module";

@Module({ imports: [UsersModule] })
export class AppModule {}
```

```ts
// src/main.ts
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  await app.listen(process.env.PORT ?? 3000);
}
void bootstrap();
```

Lo que te ahorra frente a Express:

- **Los tests sustituyen dependencias sin tocar el código**: le das a `UsersService` un repositorio falso en el módulo de test.
- **Las fronteras son explícitas.** Si mañana un `OrdersModule` necesita usuarios, importa `UsersModule` y recibe `UsersService`; no puede alcanzar `UsersRepository` porque no se exporta. Eso evita que medio proyecto dependa de detalles de persistencia.

Sobre versiones: Nest 11 exige Node 20 o superior y usa Express 5 por debajo, así que las rutas con comodines siguen la sintaxis nueva (`*splat`). El `body` sin validar del `POST` es provisional: el paso siguiente es un DTO con `class-validator` y `ValidationPipe`.

Comprobación:

```bash
curl -s -X POST localhost:3000/users -H 'content-type: application/json' \
  -d '{"name":"Ana","email":"ana@example.com"}'     # 201 {"id":1,...}
curl -s localhost:3000/users/1                     # 200
curl -s localhost:3000/users/99                    # 404 "User 99 not found"
curl -s localhost:3000/users/abc                   # 400 "Validation failed (numeric string is expected)"
```

El último lo produce `ParseIntPipe` antes de llegar al servicio.""",
            },
        ]
    },
    # 11) ERR: «mi DTO no valida nada» (interface + sin ValidationPipe global).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Hice un DTO para crear usuarios en NestJS 11 pero no valida nada: mando `{"email": "no-es-email", "admin": true}` y llega tal cual al servicio. Ya instalé class-validator.

```ts
// create-user.dto.ts
export interface CreateUserDto {
  name: string;
  email: string;
}

// users.controller.ts
@Post()
create(@Body() dto: CreateUserDto) {
  return this.usersService.create(dto.name, dto.email);
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Faltan dos cosas, y cualquiera de las dos por separado ya produce tu síntoma:

1. **El DTO es una `interface`.** Las interfaces desaparecen al compilar a JavaScript. La validación de Nest funciona leyendo, en tiempo de ejecución, el tipo del parámetro (`design:paramtypes`); con una interfaz ese tipo es `Object`, y no hay decoradores de class-validator que aplicar porque no existe ninguna clase.
2. **No hay `ValidationPipe` registrado.** Sin pipe, `@Body()` entrega el JSON tal como llega.

El `admin: true` que se cuela es un tercer problema: aunque validaras `name` y `email`, las propiedades no declaradas pasan si no activas `whitelist`. Es la puerta de una asignación masiva (*mass assignment*).

**DTO como clase con decoradores:**

```ts
// src/users/dto/create-user.dto.ts
import { Transform } from "class-transformer";
import { IsEmail, IsString, Length, MaxLength } from "class-validator";

const trim = ({ value }: { value: unknown }) => (typeof value === "string" ? value.trim() : value);

export class CreateUserDto {
  @Transform(trim)
  @IsString()
  @Length(2, 80)
  name!: string;

  @Transform(({ value }) => (typeof value === "string" ? value.trim().toLowerCase() : value))
  @IsEmail()
  @MaxLength(254)
  email!: string;
}
```

Para query strings, donde todo llega como texto, `@Type` convierte antes de validar:

```ts
// src/users/dto/list-users.query.ts
import { Type } from "class-transformer";
import { IsInt, IsOptional, Max, Min } from "class-validator";

export class ListUsersQuery {
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page: number = 1;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit: number = 20;
}
```

**Pipe global en `main.ts`:**

```ts
// src/main.ts
import { ValidationPipe } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,            // descarta propiedades sin decoradores
      forbidNonWhitelisted: true, // mejor aún: responde 400 si llegan
      transform: true,            // el handler recibe una instancia del DTO, con los tipos convertidos
    }),
  );
  await app.listen(process.env.PORT ?? 3000);
}
void bootstrap();
```

**El controlador** solo cambia el tipo importado: `create(@Body() dto: CreateUserDto)`, ahora con la clase. Y para listar, `findAll(@Query() query: ListUsersQuery)` recibe `page` y `limit` como números.

Una trampa que reproduce exactamente tu síntoma aunque el DTO sea una clase: importarla con `import type { CreateUserDto }`. El import de solo tipos también se borra al compilar, el metadato vuelve a ser `Object` y la validación se salta en silencio. En los parámetros de controladores y constructores, importa siempre las clases con `import` normal.

Verificación:

```bash
curl -s -X POST localhost:3000/users -H 'content-type: application/json' \
  -d '{"name":"Ana","email":"no-es-email","admin":true}'
# 400 {"message":["property admin should not exist","email must be an email"],"error":"Bad Request","statusCode":400}

curl -s -X POST localhost:3000/users -H 'content-type: application/json' \
  -d '{"name":"  Ana  ","email":"ANA@Example.com"}'
# 201 con "name":"Ana" y "email":"ana@example.com"
```

Si escribes tests e2e, aplica el mismo `ValidationPipe` a la app de test; si no, estarás probando una API distinta de la que despliegas.""",
            },
        ]
    },
    # 12) Multiturno: guard JWT global con @Public() y luego roles con Reflector.createDecorator.
    {
        "messages": [
            {
                "role": "user",
                "content": "En NestJS 11 quiero que todas las rutas exijan JWT salvo unas pocas públicas (login, health). ¿Cómo lo monto sin poner `@UseGuards` en cada controlador?",
            },
            {
                "role": "assistant",
                "content": r"""Un guard global registrado con `APP_GUARD` y un decorador `@Public()` que marca las excepciones con metadatos. El guard lee esos metadatos con `Reflector` y deja pasar lo marcado. Así la seguridad es la opción por defecto: una ruta nueva sin decorar nace protegida.

```ts
// src/auth/public.decorator.ts
import { SetMetadata } from "@nestjs/common";

export const IS_PUBLIC_KEY = "isPublic";
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);
```

```ts
// src/auth/jwt-auth.guard.ts
import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from "@nestjs/common";
import { Reflector } from "@nestjs/core";
import { JwtService } from "@nestjs/jwt";
import type { Request } from "express";
import { IS_PUBLIC_KEY } from "./public.decorator";

export interface JwtPayload {
  sub: string;
  roles: string[];
}

export type AuthenticatedRequest = Request & { user?: JwtPayload };

@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(
    private readonly jwt: JwtService,
    private readonly reflector: Reflector,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    // El handler manda sobre la clase: @Public() en un método abre solo ese método
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;

    const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
    const token = this.extractBearer(request);
    if (!token) throw new UnauthorizedException("Missing bearer token");

    try {
      request.user = await this.jwt.verifyAsync<JwtPayload>(token);
    } catch {
      throw new UnauthorizedException("Invalid or expired token");
    }
    return true;
  }

  private extractBearer(request: Request): string | undefined {
    const [type, token] = request.headers.authorization?.split(" ") ?? [];
    return type === "Bearer" && token ? token : undefined;
  }
}
```

```ts
// src/auth/auth.module.ts
import { Module } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { APP_GUARD } from "@nestjs/core";
import { JwtModule } from "@nestjs/jwt";
import { JwtAuthGuard } from "./jwt-auth.guard";

@Module({
  imports: [
    JwtModule.registerAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        secret: config.getOrThrow<string>("JWT_SECRET"),
        signOptions: { expiresIn: "15m", issuer: "orders-api" },
        verifyOptions: { algorithms: ["HS256"], issuer: "orders-api" },
      }),
    }),
  ],
  providers: [{ provide: APP_GUARD, useClass: JwtAuthGuard }],
})
export class AuthModule {}
```

```ts
// uso
@Public()
@Get("health")
health() {
  return { ok: true };
}
```

Por qué cada pieza (asumo `ConfigModule` registrado como global):

- **`APP_GUARD` y no `app.useGlobalGuards(new JwtAuthGuard(...))`.** Con `APP_GUARD`, Nest crea el guard dentro del contenedor y le inyecta `JwtService` y `Reflector`. Con `useGlobalGuards` lo instancias tú, fuera de la inyección de dependencias.
- **`getAllAndOverride`** busca primero en el método y luego en la clase. Puedes marcar un controlador entero como público y seguir protegiendo uno de sus métodos con otro mecanismo, o al revés.
- **`verifyOptions` con `algorithms` e `issuer`.** Fija lo que aceptas en lugar de confiar en lo que declara el token.
- **`import type { Request }`** es correcto aquí: `Request` solo se usa como tipo, no como dependencia inyectada.

Verificación:

```bash
curl -i localhost:3000/health                                    # 200 sin token
curl -i localhost:3000/users                                     # 401 Missing bearer token
curl -i localhost:3000/users -H "Authorization: Bearer $TOKEN"   # 200
```""",
            },
            {
                "role": "user",
                "content": "Perfecto. Ahora quiero roles: algunas rutas solo para `admin` y otras para `admin` o `editor`. ¿Otro guard?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, un `RolesGuard` separado: autenticar («quién eres») y autorizar («qué puedes hacer») son responsabilidades distintas y conviene que fallen con códigos distintos, 401 y 403. Desde Nest 10, `Reflector.createDecorator` crea el decorador ya tipado, sin claves de texto sueltas.

```ts
// src/auth/roles.decorator.ts
import { Reflector } from "@nestjs/core";

export type Role = "admin" | "editor" | "viewer";

export const Roles = Reflector.createDecorator<Role[]>();
```

```ts
// src/auth/roles.guard.ts
import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from "@nestjs/common";
import { Reflector } from "@nestjs/core";
import type { AuthenticatedRequest } from "./jwt-auth.guard";
import { Roles } from "./roles.decorator";

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const required = this.reflector.getAllAndOverride(Roles, [context.getHandler(), context.getClass()]);
    if (!required || required.length === 0) return true; // la ruta no pide rol

    const { user } = context.switchToHttp().getRequest<AuthenticatedRequest>();
    const requiredRoles: readonly string[] = required;
    const allowed = user?.roles.some((role) => requiredRoles.includes(role)) ?? false;
    if (!allowed) throw new ForbiddenException("Insufficient role");
    return true;
  }
}
```

```ts
// src/auth/auth.module.ts (providers)
providers: [
  { provide: APP_GUARD, useClass: JwtAuthGuard }, // 1.º: autentica y rellena request.user
  { provide: APP_GUARD, useClass: RolesGuard },   // 2.º: autoriza con request.user ya presente
],
```

```ts
// src/users/users.controller.ts (fragmento)
@Roles(["admin", "editor"]) // por defecto, para todo el controlador
@Controller("users")
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  findAll(): User[] {
    return this.usersService.findAll(); // admin o editor
  }

  @Roles(["admin"]) // sustituye al de la clase para este método
  @Delete(":id")
  @HttpCode(204)
  remove(@Param("id", ParseIntPipe) id: number): void {
    this.usersService.remove(id); // solo admin
  }
}
```

Tres detalles que causan bugs:

- **El orden de registro es el orden de ejecución.** Los guards globales corren en el orden en que se declaran los `APP_GUARD`. Si `RolesGuard` fuera primero, no habría `request.user` y respondería 403 a todo el mundo, incluso a quien ni siquiera mandó token (que merece un 401).
- **`getAllAndOverride` frente a `getAllAndMerge`.** Con *override*, el `@Roles` del método reemplaza al de la clase (por eso `remove` queda solo para admin). Con *merge* se sumarían y `remove` aceptaría editores; elige a conciencia.
- **Las rutas `@Public()` no deben llevar `@Roles`.** Sin usuario, `RolesGuard` niega el acceso; es el comportamiento seguro, pero confunde si no lo sabes.

Verificación con tres tokens:

```bash
curl -i -X DELETE localhost:3000/users/1 -H "Authorization: Bearer $VIEWER"  # 403
curl -i -X DELETE localhost:3000/users/1 -H "Authorization: Bearer $EDITOR"  # 403
curl -i -X DELETE localhost:3000/users/1 -H "Authorization: Bearer $ADMIN"   # 204
curl -i localhost:3000/users -H "Authorization: Bearer $EDITOR"              # 200
curl -i -X DELETE localhost:3000/users/1                                     # 401 (falla el primer guard)
```""",
            },
        ]
    },
    # 13) EN: ciclo de vida de una petición en Nest e interceptores (logging, envelope, timeout).
    {
        "messages": [
            {
                "role": "user",
                "content": "In NestJS, what's the difference between middleware, guards, interceptors, pipes and exception filters, and in what order do they run? I want to log how long handlers take, wrap every response in `{ data: ... }`, and fail requests that take longer than 5 seconds.",
            },
            {
                "role": "assistant",
                "content": r"""The order of a request through Nest:

1. **Middleware**: plain Express/Fastify middleware. No access to which handler will run.
2. **Guards**: decide yes/no (authentication, authorization). They know the handler and its metadata.
3. **Interceptors, before the handler**: wrap the call; can time, cache or short-circuit it.
4. **Pipes**: validate and transform the handler arguments (`ValidationPipe`, `ParseIntPipe`).
5. **The handler.**
6. **Interceptors, after the handler**, in reverse order: they transform the result as it flows back.
7. **Exception filters**: only if something above threw; they turn the exception into a response.

Within each stage: global first, then controller-level, then route-level.

All three of your requirements are interceptor jobs, because they need to wrap the handler's result stream.

```ts
// src/common/interceptors.ts
import {
  CallHandler,
  ExecutionContext,
  Injectable,
  Logger,
  NestInterceptor,
  RequestTimeoutException,
} from "@nestjs/common";
import type { Request } from "express";
import { Observable, TimeoutError, catchError, map, tap, throwError, timeout } from "rxjs";

const REQUEST_TIMEOUT_MS = 5_000;

@Injectable()
export class TimingInterceptor implements NestInterceptor {
  private readonly logger = new Logger("Handler");

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest<Request>();
    const handler = `${context.getClass().name}.${context.getHandler().name}`;
    const started = performance.now();
    const elapsed = () => (performance.now() - started).toFixed(1);

    return next.handle().pipe(
      tap({
        next: () => this.logger.log(`${req.method} ${req.originalUrl} -> ${handler} in ${elapsed()}ms`),
        error: (err: unknown) =>
          this.logger.warn(
            `${req.method} ${req.originalUrl} -> ${handler} failed after ${elapsed()}ms: ${err instanceof Error ? err.message : String(err)}`,
          ),
      }),
    );
  }
}

@Injectable()
export class TimeoutInterceptor implements NestInterceptor {
  intercept(_context: ExecutionContext, next: CallHandler): Observable<unknown> {
    return next.handle().pipe(
      timeout(REQUEST_TIMEOUT_MS),
      catchError((err: unknown) =>
        throwError(() => (err instanceof TimeoutError ? new RequestTimeoutException() : err)),
      ),
    );
  }
}

export interface Envelope<T> {
  data: T;
}

@Injectable()
export class EnvelopeInterceptor<T> implements NestInterceptor<T, Envelope<T>> {
  intercept(_context: ExecutionContext, next: CallHandler<T>): Observable<Envelope<T>> {
    return next.handle().pipe(map((data) => ({ data })));
  }
}
```

```ts
// src/main.ts (excerpt)
app.useGlobalInterceptors(new TimingInterceptor(), new TimeoutInterceptor(), new EnvelopeInterceptor());
```

Why this order: on the way in it's Timing → Timeout → Envelope → handler; on the way out it's reversed. Timing is outermost, so it also measures (and logs) requests killed by the timeout. Envelope is innermost, so only real results get wrapped; a 408 or a validation error keeps Nest's normal error shape.

Things that trip people up:

- **I log handler time, not the HTTP status.** At the moment the handler's value flows through the interceptor, Nest hasn't necessarily written the final status yet (a `POST` becomes 201 afterwards). For access logs with status codes, use a request-logging middleware such as `pino-http`, which hooks the response's `finish` event. Interceptors are the right tool for per-handler timing.
- **`timeout` stops waiting; it doesn't stop the work.** The database query keeps running after the 408. If that matters, pass an `AbortSignal` down to the client libraries that support it, or set a statement timeout in the database.
- **Envelope and special responses.** Handlers that use `@Res()` or return a `StreamableFile` shouldn't be wrapped; skip them by checking a metadata flag in the interceptor, or bind `EnvelopeInterceptor` per controller instead of globally.
- **Needs DI?** Register with `{ provide: APP_INTERCEPTOR, useClass: TimingInterceptor }` in a module instead of `useGlobalInterceptors`, so Nest can inject a logger service or config.

Verification: add a test route that waits 6 seconds (`await new Promise((r) => setTimeout(r, 6_000))`). Calling it returns `408 Request Timeout` after about 5 s and logs "failed after 5000.x ms". A normal `GET /users/1` returns `{"data":{"id":1,...}}`, and a `GET /users/abc` still returns the plain 400 from `ParseIntPipe`, because pipes throw before the handler and nothing reaches the envelope.""",
            },
        ]
    },
    # 14) Multiturno: exception filter para errores de Prisma y por qué no un 500 genérico.
    {
        "messages": [
            {
                "role": "user",
                "content": "Uso Prisma con NestJS y cuando inserto un email repetido el cliente recibe un 500 «Internal server error». En el log veo `PrismaClientKnownRequestError` con código `P2002`. ¿Cómo lo convierto en un 409 sin llenar los servicios de try/catch?",
            },
            {
                "role": "assistant",
                "content": r"""Con un **exception filter** que capture solo los errores conocidos de Prisma y los traduzca a HTTP en un único sitio. Los servicios siguen lanzando lo que lanzan; la traducción vive en la frontera HTTP, que es donde tiene sentido hablar de 409.

```ts
// src/prisma/prisma-exception.filter.ts
import { ArgumentsHost, Catch, ExceptionFilter, HttpStatus, Logger } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import type { Response } from "express";

interface MappedError {
  status: HttpStatus;
  error: string;
  message: string;
}

// Solo los códigos que significan algo para el cliente; el resto es un fallo nuestro
const PRISMA_TO_HTTP: Record<string, MappedError> = {
  P2002: { status: HttpStatus.CONFLICT, error: "Conflict", message: "Resource already exists" },
  P2003: { status: HttpStatus.CONFLICT, error: "Conflict", message: "Related resource constraint failed" },
  P2025: { status: HttpStatus.NOT_FOUND, error: "Not Found", message: "Resource not found" },
};

@Catch(Prisma.PrismaClientKnownRequestError)
export class PrismaExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(PrismaExceptionFilter.name);

  catch(exception: Prisma.PrismaClientKnownRequestError, host: ArgumentsHost): void {
    const response = host.switchToHttp().getResponse<Response>();
    const mapped = PRISMA_TO_HTTP[exception.code];

    if (!mapped) {
      this.logger.error(`Unmapped Prisma error ${exception.code}`, exception.stack);
      response.status(HttpStatus.INTERNAL_SERVER_ERROR).json({
        statusCode: HttpStatus.INTERNAL_SERVER_ERROR,
        error: "Internal Server Error",
        message: "Internal server error",
      });
      return;
    }

    response.status(mapped.status).json({
      statusCode: mapped.status,
      error: mapped.error,
      message: mapped.message,
      // En P2002, Prisma indica qué campos violaron la restricción única
      ...(exception.code === "P2002" && exception.meta?.target ? { fields: exception.meta.target } : {}),
    });
  }
}
```

```ts
// src/main.ts (fragmento)
app.useGlobalFilters(new PrismaExceptionFilter());
```

Decisiones:

- **`@Catch(Prisma.PrismaClientKnownRequestError)`** y no `@Catch()`: el filtro solo actúa sobre lo que sabe traducir. Los `NotFoundException` de tus servicios y los 400 del `ValidationPipe` siguen su camino normal.
- **Mismo formato que los errores de Nest** (`statusCode`, `error`, `message`): el cliente no tiene que distinguir de dónde salió el error.
- **Los códigos no mapeados se registran con stack y responden un 500 sin detalles.** El mensaje de Prisma puede incluir nombres de tablas y fragmentos de la consulta; no debe llegar al cliente.
- **P2002 se detecta en la inserción, no con un `findUnique` previo.** Comprobar antes de insertar tiene una carrera: dos peticiones simultáneas pasan la comprobación y una falla igualmente al insertar. La restricción única de la base de datos es la fuente de verdad, y el filtro hace que ese fallo sea un 409 limpio.

Verificación:

```bash
curl -s -X POST localhost:3000/users -H 'content-type: application/json' -d '{"name":"Ana","email":"ana@example.com"}'
curl -s -X POST localhost:3000/users -H 'content-type: application/json' -d '{"name":"Ana","email":"ana@example.com"}'
# 409 {"statusCode":409,"error":"Conflict","message":"Resource already exists","fields":["email"]}
```""",
            },
            {
                "role": "user",
                "content": "¿Y no sería más simple un único filtro `@Catch()` que lo convierta todo a un 500 con nuestro formato? Así tenemos un formato de error uniforme. ¿Y cuándo hace falta `APP_FILTER`?",
            },
            {
                "role": "assistant",
                "content": r"""Uniforme sí; todo a 500, no. Un `@Catch()` que responde 500 a cualquier excepción convierte el 404 de un `NotFoundException`, el 400 del `ValidationPipe` y el 401 de los guards en errores del servidor. El cliente pierde la información para reaccionar (reintentar, corregir el formulario, volver a iniciar sesión) y tus alertas de 5xx se llenan de errores que son del usuario.

Si lo que buscas es un formato único, el filtro global tiene que **respetar** el estado de las `HttpException` y reservar el 500 para lo desconocido:

```ts
// src/common/all-exceptions.filter.ts
import { ArgumentsHost, Catch, ExceptionFilter, HttpException, HttpStatus, Logger } from "@nestjs/common";
import type { Request, Response } from "express";

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const http = host.switchToHttp();
    const response = http.getResponse<Response>();
    const request = http.getRequest<Request>();

    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const body = exception.getResponse();
      // Conserva el estado y el detalle (p. ej. la lista de errores de validación)
      response.status(status).json(typeof body === "string" ? { statusCode: status, message: body } : body);
      return;
    }

    this.logger.error(
      `Unhandled error on ${request.method} ${request.originalUrl}`,
      exception instanceof Error ? exception.stack : String(exception),
    );
    response.status(HttpStatus.INTERNAL_SERVER_ERROR).json({
      statusCode: HttpStatus.INTERNAL_SERVER_ERROR,
      error: "Internal Server Error",
      message: "Internal server error",
    });
  }
}
```

**`APP_FILTER` frente a `useGlobalFilters`:**

- `app.useGlobalFilters(new X())` crea la instancia fuera del contenedor de Nest: no puede recibir dependencias por constructor.
- `{ provide: APP_FILTER, useClass: X }` en un módulo deja que Nest la construya e inyecte lo que pida: un servicio de métricas, `ConfigService` para decidir cuánto detalle mostrar según el entorno, un logger propio.

```ts
// src/app.module.ts (fragmento)
import { APP_FILTER } from "@nestjs/core";

providers: [
  { provide: APP_FILTER, useClass: AllExceptionsFilter },  // el genérico, primero
  { provide: APP_FILTER, useClass: PrismaExceptionFilter }, // el específico, después
],
```

El orden importa y es contraintuitivo: según la documentación de Nest, cuando combinas un filtro que captura todo con uno ligado a un tipo concreto, el genérico debe declararse **primero** para que el específico pueda atender su tipo. Si los inviertes, el `@Catch()` se queda también con los errores de Prisma y vuelves a ver 500.

Verificación con tres llamadas, una por rama: el email duplicado sigue dando 409 (filtro de Prisma), `GET /users/999` sigue dando 404 con el mensaje del servicio (rama `HttpException`), y una ruta de prueba que hace `throw new Error("boom")` da un 500 sin la palabra «boom» en el cuerpo, pero con el stack en el log.""",
            },
        ]
    },
    # 15) Configuración y secretos con @nestjs/config + zod (system: español de España).
    {
        "messages": [
            {"role": "system", "content": "Responde en español de España, directo y con TypeScript."},
            {
                "role": "user",
                "content": "¿Cómo gestiono la configuración y los secretos en NestJS? Ahora tengo `process.env.X` repartido por todo el código y el otro día desplegamos sin `DATABASE_URL`: la app arrancó tan tranquila y petó en la primera petición.",
            },
            {
                "role": "assistant",
                "content": r"""La regla que te habría salvado: **la configuración se valida al arrancar, en un único sitio, y si falta algo el proceso no arranca**. Un despliegue que no levanta lo detecta el orquestador en segundos; uno que arranca y falla en la primera petición lo detectan tus usuarios.

Con `@nestjs/config` y un esquema de zod (asumo zod 4):

```ts
// src/config/env.ts
import { z } from "zod";

export const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.url(),
  JWT_SECRET: z.string().min(32, "debe tener al menos 32 caracteres"),
  CORS_ORIGINS: z
    .string()
    .default("")
    .transform((value) => value.split(",").map((origin) => origin.trim()).filter(Boolean)),
});

export type Env = z.infer<typeof envSchema>;

export function validateEnv(config: Record<string, unknown>): Env {
  const result = envSchema.safeParse(config);
  if (!result.success) {
    // Solo nombre de la variable y motivo: nunca el valor, que puede ser un secreto
    const problems = result.error.issues
      .map((issue) => `  - ${issue.path.join(".")}: ${issue.message}`)
      .join("\n");
    throw new Error(`Configuración inválida:\n${problems}`);
  }
  return result.data;
}
```

```ts
// src/app.module.ts
import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { validateEnv } from "./config/env";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      cache: true,
      validate: validateEnv,
      ignoreEnvFile: process.env.NODE_ENV === "production", // en producción, solo variables reales
    }),
  ],
})
export class AppModule {}
```

Uso tipado en cualquier servicio:

```ts
// src/http/cors-policy.ts
import { Injectable } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import type { Env } from "../config/env";

@Injectable()
export class CorsPolicy {
  constructor(private readonly config: ConfigService<Env, true>) {}

  isAllowed(origin: string): boolean {
    // string[] ya transformado; con { infer: true } el tipo sale del esquema
    return this.config.get("CORS_ORIGINS", { infer: true }).includes(origin);
  }
}
```

Y en `main.ts`:

```ts
const config = app.get<ConfigService<Env, true>>(ConfigService);
await app.listen(config.get("PORT", { infer: true }));
```

Por qué así:

- **`ConfigService<Env, true>`**: el segundo parámetro le dice a TypeScript que la configuración ya está validada, así que `get` devuelve `number` o `string[]`, no `T | undefined`. Si escribes mal una clave, no compila.
- **`z.coerce.number()` y el `transform`**: las variables de entorno siempre llegan como texto. Convertirlas en el esquema evita los `Number(process.env.PORT)` repartidos y sus `NaN` silenciosos.
- **El mensaje de error no incluye valores.** Un log de arranque con `JWT_SECRET=...` acaba en el agregador de logs, con permisos mucho más amplios que tu gestor de secretos.
- **`process.env` no se vuelve a tocar fuera de `env.ts`.** Una regla de lint (`no-process-env` o un `no-restricted-properties`) lo hace cumplir.

Sobre los secretos:

- `.env` solo en local y en `.gitignore`. Versiona un `.env.example` con las claves y sin valores.
- En producción, los secretos los inyecta la plataforma como variables de entorno (Kubernetes Secrets, el gestor de secretos de tu nube). Las variables reales tienen prioridad sobre el `.env`, y con `ignoreEnvFile` en producción eliminas la duda.
- Para scripts sueltos fuera de Nest, Node 20.6+ ya lee ficheros con `node --env-file=.env script.js`, sin `dotenv`.

Verificación: arranca sin `DATABASE_URL` y con un `JWT_SECRET` corto. El proceso debe terminar al instante con:

```
Error: Configuración inválida:
  - DATABASE_URL: Invalid input: expected string, received undefined
  - JWT_SECRET: debe tener al menos 32 caracteres
```

(el texto exacto del primer motivo depende de la versión de zod) y código de salida distinto de 0, que es lo que hará fallar el despliegue en vez de servir errores.""",
            },
        ]
    },
    # 16) Testing en Nest: unit test con repositorio simulado y e2e con supertest (system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cómo testeo en NestJS un servicio y un endpoint? Para el servicio quiero simular el repositorio, y para el endpoint quiero algo que pruebe de verdad la validación y los códigos HTTP. Es el `UsersService` típico con `UsersRepository` y un `CreateUserDto` con class-validator.",
            },
            {
                "role": "assistant",
                "content": r"""Dos niveles con objetivos distintos: el **unit test** comprueba la lógica del servicio aislada (rápido, sin HTTP); el **e2e** levanta la app real en memoria y le habla por HTTP con supertest, incluidos pipes, guards y filtros. Lo que más se olvida en el segundo es aplicar la misma configuración que `main.ts`; lo resuelvo extrayéndola a una función.

**Unit test del servicio** (Jest, que es lo que trae `nest new`):

```ts
// src/users/users.service.spec.ts
import { NotFoundException } from "@nestjs/common";
import { Test } from "@nestjs/testing";
import { UsersRepository } from "./users.repository";
import { UsersService } from "./users.service";

describe("UsersService", () => {
  let service: UsersService;
  let repo: { findById: jest.Mock; findAll: jest.Mock; create: jest.Mock };

  beforeEach(async () => {
    repo = { findById: jest.fn(), findAll: jest.fn(), create: jest.fn() };
    const moduleRef = await Test.createTestingModule({
      providers: [UsersService, { provide: UsersRepository, useValue: repo }],
    }).compile();
    service = moduleRef.get(UsersService);
  });

  it("devuelve el usuario cuando existe", () => {
    const ana = { id: 1, name: "Ana", email: "ana@example.com" };
    repo.findById.mockReturnValue(ana);

    expect(service.findOne(1)).toEqual(ana);
    expect(repo.findById).toHaveBeenCalledWith(1);
  });

  it("lanza NotFoundException cuando no existe", () => {
    repo.findById.mockReturnValue(undefined);

    expect(() => service.findOne(99)).toThrow(NotFoundException);
  });
});
```

`{ provide: UsersRepository, useValue: repo }` sustituye la dependencia usando la clase como token; el servicio no se entera. Si el repositorio fuera más complejo, una implementación falsa en memoria suele dar tests más robustos que los mocks, porque prueba comportamiento y no llamadas concretas.

**Configuración compartida entre `main.ts` y los tests:**

```ts
// src/configure-app.ts
import { INestApplication, ValidationPipe } from "@nestjs/common";

export function configureApp(app: INestApplication): void {
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
}
```

```ts
// src/main.ts
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";
import { configureApp } from "./configure-app";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  configureApp(app);
  await app.listen(process.env.PORT ?? 3000);
}
void bootstrap();
```

**E2E con supertest:**

```ts
// test/users.e2e-spec.ts
import { INestApplication } from "@nestjs/common";
import { Test } from "@nestjs/testing";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { configureApp } from "../src/configure-app";

describe("Users (e2e)", () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    configureApp(app); // exactamente lo mismo que en producción
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it("POST /users rechaza un cuerpo inválido con 400", async () => {
    const res = await request(app.getHttpServer())
      .post("/users")
      .send({ name: "Ana", email: "no-es-email", admin: true })
      .expect(400);

    expect(res.body.message).toEqual(
      expect.arrayContaining(["email must be an email", "property admin should not exist"]),
    );
  });

  it("crea un usuario y luego lo lee", async () => {
    const created = await request(app.getHttpServer())
      .post("/users")
      .send({ name: "Ana", email: "ana@example.com" })
      .expect(201);

    const fetched = await request(app.getHttpServer()).get(`/users/${created.body.id}`).expect(200);
    expect(fetched.body.email).toBe("ana@example.com");
  });

  it("GET /users/abc responde 400 por ParseIntPipe", async () => {
    await request(app.getHttpServer()).get("/users/abc").expect(400);
  });
});
```

Notas:

- **Base de datos en e2e:** si el repositorio habla con una BD real, usa una de test (un contenedor desechable) o sustitúyelo con `Test.createTestingModule({ imports: [AppModule] }).overrideProvider(UsersRepository).useValue(fake)`. Lo segundo es más rápido; lo primero prueba también las consultas.
- **`import request from "supertest"`** requiere `esModuleInterop`, activo en la plantilla de Nest 11; sin él, `import * as request from "supertest"`.
- **`app.close()` en `afterAll`** cierra el servidor y las conexiones; sin él, Jest avisa de *open handles* y puede no terminar.

Comprobación de que los tests protegen algo: quita `configureApp(app)` del e2e y el primer test pasa a fallar (llega un 201). Ese es justo el bug que tendrías en producción si `main.ts` olvidara el pipe, y ahora un test lo vigila.""",
            },
        ]
    },
    # 17) ERR principiante: «Nest can't resolve dependencies of the UsersService (?)».
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Moví el repositorio a un `DatabaseModule` aparte para reutilizarlo y desde entonces la app no arranca:

```
[Nest] 41235  - 03/10/2025, 10:12:01   ERROR [ExceptionHandler] Nest can't resolve dependencies of the UsersService (?). Please make sure that the argument UsersRepository at index [0] is available in the UsersModule context.

Potential solutions:
- Is UsersModule a valid NestJS module?
- If UsersRepository is a provider, is it part of the current UsersModule?
- If UsersRepository is exported from a separate @Module, is that module imported within UsersModule?
  @Module({
    imports: [ /* the Module containing UsersRepository */ ]
  })
```

¿Qué hice mal?""",
            },
            {
                "role": "assistant",
                "content": r"""El mensaje se lee así: al construir `UsersService`, el parámetro 0 del constructor (el `?`) es un `UsersRepository` que el **contexto de `UsersModule`** no puede ver. Cada módulo de Nest solo ve sus propios providers y los que **exportan** los módulos que **importa**. Al mover el repositorio, casi seguro se rompió uno de esos dos enlaces.

Cómo debe quedar:

```ts
// src/database/database.module.ts
import { Module } from "@nestjs/common";
import { UsersRepository } from "../users/users.repository";

@Module({
  providers: [UsersRepository],
  exports: [UsersRepository], // sin esto, nadie fuera de DatabaseModule lo ve
})
export class DatabaseModule {}
```

```ts
// src/users/users.module.ts
import { Module } from "@nestjs/common";
import { DatabaseModule } from "../database/database.module";
import { UsersController } from "./users.controller";
import { UsersService } from "./users.service";

@Module({
  imports: [DatabaseModule], // trae lo que DatabaseModule exporta
  controllers: [UsersController],
  providers: [UsersService], // UsersRepository ya NO va aquí
  exports: [UsersService],
})
export class UsersModule {}
```

Las causas posibles, por orden de probabilidad en tu caso:

1. **`DatabaseModule` no exporta `UsersRepository`.** Declararlo en `providers` lo hace existir solo dentro de ese módulo.
2. **`UsersModule` no importa `DatabaseModule`.** Exportar no basta; quien lo usa tiene que importar el módulo.
3. **El repositorio sigue también en `providers` de `UsersModule`.** No da este error, pero crea una **segunda instancia**: con un repositorio en memoria tendrías dos almacenes distintos y datos que «desaparecen». Un provider se declara en un solo módulo y se comparte exportándolo.
4. **El import de la clase es solo de tipo.** Si en `users.service.ts` pone `import type { UsersRepository }`, TypeScript borra la referencia y Nest no sabe qué inyectar. La pista está en el propio mensaje: en lugar de `UsersRepository` verías `Object` como nombre del argumento. En tu log aparece el nombre correcto, así que puedes descartarlo.
5. **Dependencia circular entre archivos o módulos** (por ejemplo, `DatabaseModule` importando `UsersModule` a la vez). Nest lo indica con un aviso de dependencia circular; se resuelve rediseñando quién depende de quién, y `forwardRef()` solo como último recurso.

Sobre el diseño: un `DatabaseModule` que contiene repositorios de cada dominio acaba dependiendo de todo el proyecto. Suele envejecer mejor que `DatabaseModule` exporte solo la conexión (el cliente de Prisma o el pool) y que cada feature declare su repositorio en su propio módulo. Así `UsersRepository` vuelve a `UsersModule` y `DatabaseModule` no conoce a nadie.

Verificación barata y permanente: un test que solo compila el módulo, para que un error de cableado salte en CI y no en el despliegue.

```ts
// src/users/users.module.spec.ts
import { Test } from "@nestjs/testing";
import { UsersModule } from "./users.module";
import { UsersService } from "./users.service";

it("UsersModule resuelve todas sus dependencias", async () => {
  const moduleRef = await Test.createTestingModule({ imports: [UsersModule] }).compile();
  expect(moduleRef.get(UsersService)).toBeInstanceOf(UsersService);
});
```

Con el cableado roto, `compile()` falla con el mismo mensaje que viste al arrancar.""",
            },
        ]
    },
    # 18) Multiturno: WebSockets con gateway de Nest y escalado con el adaptador de Redis.
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero notificaciones en tiempo real en mi API NestJS 11: que cada usuario reciba en el navegador los cambios de estado de sus pedidos. ¿Cómo se hace con WebSockets y cómo autentico la conexión?",
            },
            {
                "role": "assistant",
                "content": r"""Con un **gateway** de `@nestjs/websockets` sobre socket.io: autenticas en el *handshake*, metes cada socket en una sala con el id de su usuario, y el servicio de pedidos emite a esa sala.

```bash
npm i @nestjs/websockets @nestjs/platform-socket.io socket.io
```

```ts
// src/notifications/notifications.gateway.ts
import { Logger } from "@nestjs/common";
import { JwtService } from "@nestjs/jwt";
import {
  ConnectedSocket,
  MessageBody,
  OnGatewayConnection,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from "@nestjs/websockets";
import { Server, Socket } from "socket.io";

interface JwtPayload {
  sub: string;
  exp: number;
}

@WebSocketGateway({
  namespace: "/notifications",
  cors: { origin: ["https://app.example.com"], credentials: true },
})
export class NotificationsGateway implements OnGatewayConnection {
  @WebSocketServer() private readonly server!: Server;
  private readonly logger = new Logger(NotificationsGateway.name);

  constructor(private readonly jwt: JwtService) {}

  async handleConnection(client: Socket): Promise<void> {
    const token: unknown = client.handshake.auth?.token;
    if (typeof token !== "string") {
      client.disconnect(true);
      return;
    }
    try {
      const payload = await this.jwt.verifyAsync<JwtPayload>(token);
      client.data.userId = payload.sub;
      await client.join(`user:${payload.sub}`);
      // La conexión no debe sobrevivir al token que la autorizó
      const msUntilExpiry = payload.exp * 1000 - Date.now();
      const timer = setTimeout(() => client.disconnect(true), Math.max(0, msUntilExpiry));
      client.once("disconnect", () => clearTimeout(timer));
    } catch {
      this.logger.debug(`Rejected socket ${client.id}: invalid token`);
      client.disconnect(true);
    }
  }

  @SubscribeMessage("ping")
  handlePing(@ConnectedSocket() client: Socket, @MessageBody() body: { sentAt: number }) {
    // Lo devuelto con { event, data } se emite de vuelta a ese cliente
    return { event: "pong", data: { sentAt: body.sentAt, userId: client.data.userId } };
  }

  notifyUser(userId: string, event: string, payload: unknown): void {
    this.server.to(`user:${userId}`).emit(event, payload);
  }
}
```

```ts
// src/notifications/notifications.module.ts
import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module";
import { NotificationsGateway } from "./notifications.gateway";

@Module({
  imports: [AuthModule], // asumo que AuthModule exporta JwtModule
  providers: [NotificationsGateway],
  exports: [NotificationsGateway],
})
export class NotificationsModule {}
```

```ts
// src/orders/orders.service.ts (fragmento)
@Injectable()
export class OrdersService {
  constructor(
    private readonly orders: OrdersRepository,
    private readonly notifications: NotificationsGateway,
  ) {}

  async markShipped(orderId: string): Promise<void> {
    // Primero se persiste el cambio; solo si sale bien, se notifica
    const order = await this.orders.updateStatus(orderId, "shipped");
    this.notifications.notifyUser(order.userId, "order.updated", { orderId, status: order.status });
  }
}
```

Cliente:

```ts
import { io } from "socket.io-client";

const socket = io("https://api.example.com/notifications", { auth: { token: accessToken } });
socket.on("order.updated", (event: { orderId: string; status: string }) => {
  console.log("pedido actualizado", event);
});
```

Por qué así:

- **Token en `handshake.auth`, no en la query string.** Las URLs acaban en logs de proxies y balanceadores; el objeto `auth` viaja en el cuerpo del handshake.
- **Una sala por usuario** (`user:<id>`): emitir a la sala llega a todas sus pestañas y dispositivos sin que el servicio de pedidos sepa nada de sockets concretos.
- **Desconexión al expirar el token.** Una conexión WebSocket puede durar horas; si no la cortas, un token de 15 minutos da acceso indefinido. El cliente se reconecta con un token renovado.
- **Notificar después de persistir.** Si el orden es el inverso y la escritura falla, el usuario ve un estado que nunca existió.

Verificación: abre la app en dos navegadores con usuarios distintos, cambia el estado de un pedido del primero y comprueba que solo ese navegador recibe `order.updated`. Conecta sin token: el socket se desconecta al instante.""",
            },
            {
                "role": "user",
                "content": "En producción tenemos 3 réplicas detrás de un balanceador. ¿Funciona igual?",
            },
            {
                "role": "assistant",
                "content": r"""No. Las salas viven **en la memoria de cada proceso**. `server.to("user:42").emit(...)` solo llega a los sockets conectados a esa réplica. Si la petición que marca el pedido como enviado la atiende la réplica A y el navegador del usuario está conectado a la B, la notificación se pierde. En desarrollo no lo verás, porque solo hay un proceso.

Hacen falta dos cosas.

**1. Un adaptador que reparta los eventos entre réplicas.** El adaptador de Redis publica cada emisión en Redis y todas las réplicas la entregan a sus sockets locales. Es el patrón de la documentación de Nest:

```bash
npm i @socket.io/redis-adapter redis
```

```ts
// src/notifications/redis-io.adapter.ts
import { IoAdapter } from "@nestjs/platform-socket.io";
import { createAdapter } from "@socket.io/redis-adapter";
import { createClient } from "redis";
import { ServerOptions } from "socket.io";

export class RedisIoAdapter extends IoAdapter {
  private adapterConstructor: ReturnType<typeof createAdapter> | undefined;

  async connectToRedis(url: string): Promise<void> {
    const pubClient = createClient({ url });
    const subClient = pubClient.duplicate();
    await Promise.all([pubClient.connect(), subClient.connect()]);
    this.adapterConstructor = createAdapter(pubClient, subClient);
  }

  override createIOServer(port: number, options?: ServerOptions) {
    if (!this.adapterConstructor) {
      throw new Error("connectToRedis() must be awaited before the app starts listening");
    }
    const server = super.createIOServer(port, options);
    server.adapter(this.adapterConstructor);
    return server;
  }
}
```

```ts
// src/main.ts (fragmento)
const redisIoAdapter = new RedisIoAdapter(app);
await redisIoAdapter.connectToRedis(config.getOrThrow<string>("REDIS_URL"));
app.useWebSocketAdapter(redisIoAdapter);
await app.listen(3000);
```

**2. Sticky sessions, o solo transporte WebSocket.** socket.io empieza por defecto con *long-polling* HTTP y luego sube a WebSocket. Con polling, varias peticiones HTTP del mismo cliente deben llegar a la misma réplica; si el balanceador las reparte, verás errores `400 Session ID unknown`. Dos salidas:

- Afinidad de sesión en el balanceador (cookie o hash de IP).
- O forzar WebSocket en el cliente, sin polling: `io(url, { auth: { token }, transports: ["websocket"] })`. Pierdes el plan B para redes que bloquean WebSockets, cada vez más raras.

El adaptador resuelve **a quién se entrega**; la afinidad resuelve **que la conexión no se rompa**. Necesitas los dos problemas cubiertos.

Verificación local de la parte difícil: arranca dos instancias en los puertos 3001 y 3002 con el mismo Redis, conecta el navegador a la 3001 y dispara el cambio de pedido con un `curl` contra la 3002. Con el adaptador, el navegador recibe `order.updated`; quitándolo, no llega nada.""",
            },
        ]
    },
    # 19) Fastify 5: JSON Schema para validar y serializar, con TypeBox (system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy empezando con Fastify 5 y TypeScript. ¿Cómo valido el body y tipo la respuesta sin escribir los tipos dos veces? He leído que el schema de respuesta también «filtra» campos, ¿es así?",
            },
            {
                "role": "assistant",
                "content": r"""Sí: en Fastify el **JSON Schema** de cada ruta hace tres trabajos a la vez. Valida la entrada (con Ajv), serializa la salida (con fast-json-stringify, más rápido que `JSON.stringify`) y, al serializar, **solo emite las propiedades declaradas**. Con TypeBox escribes el schema una vez y TypeScript infiere los tipos de él.

Asumo `fastify` 5, `@fastify/type-provider-typebox` 5 y `@sinclair/typebox` 0.34.

```ts
// src/app.ts
import Fastify from "fastify";
import { randomBytes, scrypt } from "node:crypto";
import { promisify } from "node:util";
import { Type, type Static } from "@sinclair/typebox";
import type { TypeBoxTypeProvider } from "@fastify/type-provider-typebox";

const scryptAsync = promisify(scrypt);

const CreateUserBody = Type.Object(
  {
    name: Type.String({ minLength: 2, maxLength: 80 }),
    email: Type.String({ format: "email", maxLength: 254 }),
    password: Type.String({ minLength: 12, maxLength: 200 }),
  },
  { additionalProperties: false },
);

const UserResponse = Type.Object({
  id: Type.Integer(),
  name: Type.String(),
  email: Type.String(),
  createdAt: Type.String({ format: "date-time" }),
});

const UserParams = Type.Object({ id: Type.Integer({ minimum: 1 }) });
const ErrorResponse = Type.Object({ message: Type.String() });

// Lo que guardamos tiene más campos que lo que devolvemos
type UserRow = Static<typeof UserResponse> & { passwordHash: string };

async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = (await scryptAsync(password, salt, 64)) as Buffer;
  return `${salt.toString("hex")}:${key.toString("hex")}`;
}

export function buildApp() {
  const app = Fastify({ logger: true }).withTypeProvider<TypeBoxTypeProvider>();
  const users = new Map<number, UserRow>();
  let nextId = 1;

  app.post(
    "/users",
    { schema: { body: CreateUserBody, response: { 201: UserResponse } } },
    async (request, reply) => {
      const { name, email, password } = request.body; // tipado a partir del schema
      const row: UserRow = {
        id: nextId++,
        name,
        email: email.toLowerCase(),
        createdAt: new Date().toISOString(),
        passwordHash: await hashPassword(password),
      };
      users.set(row.id, row);
      return reply.code(201).send(row); // passwordHash no sale: no está en UserResponse
    },
  );

  app.get(
    "/users/:id",
    { schema: { params: UserParams, response: { 200: UserResponse, 404: ErrorResponse } } },
    async (request, reply) => {
      const user = users.get(request.params.id); // number: Ajv ya convirtió "7" en 7
      if (!user) return reply.code(404).send({ message: `User ${request.params.id} not found` });
      return user;
    },
  );

  return app;
}
```

```ts
// src/server.ts
import { buildApp } from "./app.js";

const app = buildApp();
await app.listen({ port: Number(process.env.PORT ?? 3000), host: "0.0.0.0" });
```

Lo importante:

- **Un solo origen de verdad.** `request.body` y `request.params` se tipan a partir de los schemas gracias a `withTypeProvider<TypeBoxTypeProvider>()`. Cambias el schema y el compilador te señala el código afectado.
- **El filtrado de la respuesta es una red de seguridad real.** Aunque el handler devuelva la fila completa, `passwordHash` no aparece en el JSON. Aun así, no lo uses como única defensa: devuelve objetos construidos para la respuesta cuando puedas.
- **`additionalProperties: false` y la configuración por defecto.** Fastify configura Ajv con `removeAdditional: true`, así que los campos extra del body **se eliminan en silencio** en lugar de rechazarse. Si prefieres un 400, crea la app con `Fastify({ ajv: { customOptions: { removeAdditional: false } } })`.
- **Coerción de tipos.** Ajv convierte los parámetros de ruta y la query (`"7"` → `7`) según el schema, por eso `request.params.id` es número.
- **`buildApp()` sin `listen`**: los tests usan `app.inject()` sin abrir puertos.

Verificación con curl:

```bash
curl -s -X POST localhost:3000/users -H 'content-type: application/json' \
  -d '{"name":"Ana","email":"ana@example.com","password":"correct-horse-battery","isAdmin":true}'
# 201 {"id":1,"name":"Ana","email":"ana@example.com","createdAt":"..."}  sin passwordHash ni isAdmin

curl -s localhost:3000/users/abc
# 400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"params/id must be integer"}
```""",
            },
        ]
    },
    # 20) Fastify: hooks del ciclo de vida, decorateRequest tipado y auth en onRequest.
    {
        "messages": [
            {
                "role": "user",
                "content": "En Fastify, ¿qué hooks hay y en qué orden van? Quiero autenticar con un Bearer token todas las rutas de `/api` salvo `/api/health`, dejar el usuario en `request.user` con tipos, y añadir el id de usuario al log de cada respuesta.",
            },
            {
                "role": "assistant",
                "content": r"""Orden de los hooks de una petición en Fastify 5:

1. `onRequest`: aún no se ha leído el body.
2. `preParsing`: puedes transformar el stream del body.
3. `preValidation`: body ya parseado, antes de validarlo contra el schema.
4. `preHandler`: todo validado; justo antes del handler.
5. **handler**
6. `preSerialization`: puedes modificar el objeto antes de serializarlo.
7. `onSend`: tienes el payload ya serializado.
8. `onResponse`: la respuesta ya se envió; solo sirve para registrar o medir.

Más `onError`, `onTimeout` y `onRequestAbort` para los casos raros, y hooks de aplicación como `onReady` y `onClose`.

La autenticación va en **`onRequest`**: así rechazas a quien no trae token **antes** de leer y parsear un body que podría ser de varios MB. Solo usarías `preHandler` si la verificación necesita el body (una firma HMAC sobre el contenido, por ejemplo).

```ts
// src/plugins/auth.ts
import fp from "fastify-plugin";
import { jwtVerify } from "jose";

export interface AuthUser {
  id: string;
  roles: string[];
}

declare module "fastify" {
  interface FastifyRequest {
    user: AuthUser | null;
  }
  interface FastifyContextConfig {
    public?: boolean; // config por ruta: { config: { public: true } }
  }
}

export interface AuthPluginOptions {
  jwtSecret: string;
}

export default fp<AuthPluginOptions>(
  async (app, opts) => {
    const secret = new TextEncoder().encode(opts.jwtSecret);

    async function verify(token: string): Promise<AuthUser | null> {
      try {
        const { payload } = await jwtVerify(token, secret, { algorithms: ["HS256"] });
        if (typeof payload.sub !== "string") return null;
        const roles = Array.isArray(payload.roles) ? payload.roles.map(String) : [];
        return { id: payload.sub, roles };
      } catch {
        return null;
      }
    }

    // Valor inicial null: Fastify 5 no admite objetos compartidos como valor por defecto
    app.decorateRequest("user", null);

    app.addHook("onRequest", async (request, reply) => {
      if (request.routeOptions.config.public) return;

      const header = request.headers.authorization;
      const token = header?.startsWith("Bearer ") ? header.slice("Bearer ".length) : undefined;
      const user = token ? await verify(token) : null;
      if (!user) {
        return reply.code(401).send({ message: "Unauthorized" }); // en hooks async: return reply
      }
      request.user = user;
    });

    app.addHook("onResponse", async (request, reply) => {
      request.log.info(
        { userId: request.user?.id ?? null, statusCode: reply.statusCode, ms: Number(reply.elapsedTime.toFixed(1)) },
        "request finished",
      );
    });
  },
  { name: "auth" },
);
```

```ts
// src/app.ts
import Fastify from "fastify";
import authPlugin from "./plugins/auth.js";

export function buildApp(jwtSecret: string) {
  const app = Fastify({ logger: true });

  // Todo lo de /api, con auth; fuera de este contexto no se aplica
  app.register(
    async (api) => {
      await api.register(authPlugin, { jwtSecret });

      api.get("/health", { config: { public: true } }, async () => ({ ok: true }));
      api.get("/me", async (request) => ({ id: request.user?.id, roles: request.user?.roles }));
    },
    { prefix: "/api" },
  );

  return app;
}
```

Por qué cada pieza:

- **`declare module "fastify"`** amplía los tipos: `request.user` y `config.public` quedan tipados en todas las rutas.
- **`decorateRequest("user", null)`** declara la propiedad al crear cada petición. Fastify lo exige para que todos los objetos `request` tengan la misma forma, lo que mantiene rápidas las optimizaciones de V8. En Fastify 5, un objeto como valor por defecto se rechaza porque lo compartirían todas las peticiones.
- **`fastify-plugin` + registro dentro del contexto `/api`.** `fp` hace que los hooks del plugin se apliquen al contexto que lo registra (`api`), no solo dentro del plugin. Como ese contexto tiene `prefix: "/api"`, una ruta fuera de `/api` no pasa por la autenticación.
- **`return reply.code(401).send(...)`** en un hook `async`: devolver `reply` le indica a Fastify que la respuesta ya está enviada y que no siga con el ciclo.
- **`reply.elapsedTime`** sustituye en Fastify 5 a `reply.getResponseTime()`. Ojo: con `logger: true`, Fastify ya registra cada respuesta con su `responseTime`; este hook solo añade `userId`. Si no necesitas ese campo, no lo dupliques.

Verificación con `inject`, sin abrir puertos:

```ts
const app = buildApp("x".repeat(32));
const health = await app.inject({ method: "GET", url: "/api/health" });
const me = await app.inject({ method: "GET", url: "/api/me" });
console.log(health.statusCode, me.statusCode); // 200 401
```

Con un token firmado con el mismo secreto en la cabecera `authorization`, `/api/me` responde 200 con el id, y el log muestra `"userId"` en la línea de esa petición.""",
            },
        ]
    },
    # 21) ERR: encapsulación de plugins en Fastify (decorate sin fastify-plugin).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""En Fastify registré un plugin que hace `fastify.decorate("db", pool)` y en el plugin de rutas `fastify.db` es `undefined`:

```
TypeError: Cannot read properties of undefined (reading 'query')
    at Object.<anonymous> (/app/src/routes/orders.ts:6:34)
```

```ts
// src/plugins/db.ts
import type { FastifyInstance } from "fastify";
import pg from "pg";

export default async function dbPlugin(fastify: FastifyInstance) {
  const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });
  fastify.decorate("db", pool);
}

// src/app.ts
app.register(dbPlugin);
app.register(ordersRoutes, { prefix: "/orders" });
```

Si el plugin se registra antes, ¿por qué no lo ve?""",
            },
            {
                "role": "assistant",
                "content": r"""No es un problema de orden sino de **encapsulación**, que en Fastify es deliberada. Cada `register` crea un **contexto hijo**. Lo que un plugin decora o engancha (decoradores, hooks, plugins) existe solo en su contexto y en los descendientes de ese contexto. `dbPlugin` y `ordersRoutes` son **hermanos** bajo la raíz: `db` vive en el contexto de `dbPlugin` y el de rutas nunca lo ve.

```
root
├── dbPlugin        → decora "db" aquí dentro
└── ordersRoutes    → no ve "db"
```

**El arreglo: envolver el plugin con `fastify-plugin`**, que le dice a Fastify «no crees contexto propio; aplica mis cambios al contexto que me registra». Así `db` queda en la raíz y lo heredan todos los hijos.

```ts
// src/plugins/db.ts
import fp from "fastify-plugin";
import pg from "pg";

declare module "fastify" {
  interface FastifyInstance {
    db: pg.Pool;
  }
}

export interface DbPluginOptions {
  connectionString: string;
}

export default fp<DbPluginOptions>(
  async (fastify, opts) => {
    const pool = new pg.Pool({ connectionString: opts.connectionString });
    await pool.query("SELECT 1"); // si la BD no responde, la app no arranca
    fastify.decorate("db", pool);
    fastify.addHook("onClose", async () => {
      await pool.end();
    });
  },
  { name: "db" },
);
```

```ts
// src/routes/orders.ts  (sin fp: las rutas SÍ deben estar encapsuladas)
import type { FastifyPluginAsync } from "fastify";

const ordersRoutes: FastifyPluginAsync = async (fastify) => {
  fastify.get("/", async () => {
    const { rows } = await fastify.db.query("SELECT id, status FROM orders ORDER BY id DESC LIMIT 50");
    return rows;
  });
};

export default ordersRoutes;
```

```ts
// src/app.ts
import Fastify from "fastify";
import dbPlugin from "./plugins/db.js";
import ordersRoutes from "./routes/orders.js";

export function buildApp(connectionString: string) {
  const app = Fastify({ logger: true });
  app.register(dbPlugin, { connectionString });
  app.register(ordersRoutes, { prefix: "/orders" });
  return app;
}
```

Las piezas que cambian:

- **`declare module "fastify"`**: sin esto, `fastify.db` es un error de tipos; con él, TypeScript sabe que existe en todas las instancias.
- **`name: "db"`** permite que otros plugins declaren `dependencies: ["db"]` en sus opciones de `fp`; si alguien olvida registrar `db`, Fastify falla al arrancar con un error que nombra la dependencia, en vez de un `undefined` en la primera petición.
- **`onClose` → `pool.end()`**: al cerrar la app (`app.close()` en el apagado o en los tests), el pool libera las conexiones.
- **Configuración por opciones, no `process.env` dentro del plugin**: el plugin no sabe de dónde sale la URL, y los tests le pasan la suya.

**Cuándo sí quieres encapsulación.** Es la herramienta para aplicar algo solo a una parte de la API: un hook de autenticación solo para `/admin`, un decorador distinto por versión de la API. Regla práctica: **infraestructura compartida (BD, config, auth genérica) con `fp`; rutas y lo específico de una sección, sin `fp`.** `@fastify/autoload` aplica exactamente esa convención si separas `plugins/` y `routes/` en carpetas.

Verificación: tras `await app.ready()`, `app.hasDecorator("db")` devuelve `true`, y `console.log(app.printPlugins())` muestra el árbol de contextos; con la versión sin `fp` verás `dbPlugin` como rama separada, y con `fp`, su decorador en la raíz. Después, `curl localhost:3000/orders` responde con los pedidos en lugar del `TypeError`.""",
            },
        ]
    },
    # 22) EN: pool de PostgreSQL con pg en Fastify: dimensionado, transacciones y diagnóstico.
    {
        "messages": [
            {
                "role": "user",
                "content": "We're on Fastify 5 + PostgreSQL with `pg`. Under load we get `timeout exceeded when trying to connect` from the app and sometimes `sorry, too many clients already` from Postgres. How should I size and use the pool, and how do I do transactions correctly?",
            },
            {
                "role": "assistant",
                "content": r"""Those are two different failures, and the fix for one can make the other worse, so separate them first.

- **`sorry, too many clients already`** comes from Postgres: the total number of connections from **all** your processes exceeded `max_connections`. With 6 pods × `max: 20` you can open 120 connections against a default limit of 100.
- **`timeout exceeded when trying to connect`** comes from `pg-pool`: a request waited longer than `connectionTimeoutMillis` for a free client. The pool was exhausted, because it's too small for the concurrency, because transactions hold clients too long, or because some code path never releases its client.

Raising `max` "fixes" the second by causing the first. The real budget is:

```
max per instance = floor((max_connections - reserved) / instances)
```

where `reserved` covers superuser slots, migrations, admin tools and cron jobs. Bigger pools also don't mean more throughput: Postgres does best with a modest number of *active* connections (a common rule of thumb, popularized by the HikariCP docs, is around `cores × 2`). If you need many app instances, put **PgBouncer in transaction mode** in front: thousands of client connections multiplexed onto a few dozen server connections. The catch is that session state (`SET`, session-level advisory locks, `LISTEN`) doesn't survive across transactions there.

A plugin that sizes the pool explicitly, exposes its stats and gives you a safe transaction helper:

```ts
// src/plugins/db.ts
import fp from "fastify-plugin";
import pg from "pg";

declare module "fastify" {
  interface FastifyInstance {
    db: pg.Pool;
    withTransaction<T>(work: (client: pg.PoolClient) => Promise<T>): Promise<T>;
  }
}

export interface DbOptions {
  connectionString: string;
  maxConnections: number;
}

export default fp<DbOptions>(
  async (app, opts) => {
    const pool = new pg.Pool({
      connectionString: opts.connectionString,
      max: opts.maxConnections,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 2_000, // fail fast instead of piling up waiting requests
      statement_timeout: 5_000,       // a runaway query can't hold a connection forever
    });

    // An idle client can error (DB restart, network). Without a listener, the process crashes.
    pool.on("error", (err) => app.log.error({ err }, "idle PostgreSQL client error"));

    async function withTransaction<T>(work: (client: pg.PoolClient) => Promise<T>): Promise<T> {
      const client = await pool.connect();
      let broken = false;
      try {
        await client.query("BEGIN");
        const result = await work(client);
        await client.query("COMMIT");
        return result;
      } catch (err) {
        try {
          await client.query("ROLLBACK");
        } catch {
          broken = true; // the connection itself is unusable
        }
        throw err;
      } finally {
        client.release(broken); // true destroys the client instead of returning it to the pool
      }
    }

    app.decorate("db", pool);
    app.decorate("withTransaction", withTransaction);
    app.addHook("onClose", async () => {
      await pool.end();
    });

    app.get("/internal/db-pool", async () => ({
      total: pool.totalCount,
      idle: pool.idleCount,
      waiting: pool.waitingCount,
    }));
  },
  { name: "db" },
);
```

Using it:

```ts
// src/routes/payments.ts
import type { FastifyPluginAsync } from "fastify";

type PayResult =
  | { kind: "not_found" }
  | { kind: "conflict"; status: string }
  | { kind: "paid"; orderId: string };

const paymentsRoutes: FastifyPluginAsync = async (app) => {
  app.post<{ Params: { id: string } }>("/orders/:id/pay", async (request, reply) => {
    const result = await app.withTransaction<PayResult>(async (tx) => {
      // FOR UPDATE: two concurrent payments for the same order serialize here
      const { rows } = await tx.query<{ status: string }>(
        "SELECT status FROM orders WHERE id = $1 FOR UPDATE",
        [request.params.id],
      );
      const order = rows[0];
      if (!order) return { kind: "not_found" };
      if (order.status !== "pending") return { kind: "conflict", status: order.status };

      await tx.query("INSERT INTO payments (order_id, paid_at) VALUES ($1, now())", [request.params.id]);
      await tx.query("UPDATE orders SET status = 'paid' WHERE id = $1", [request.params.id]);
      return { kind: "paid", orderId: request.params.id };
    });

    if (result.kind === "not_found") return reply.code(404).send({ message: "Order not found" });
    if (result.kind === "conflict") return reply.code(409).send({ message: `Order is ${result.status}` });
    return reply.code(200).send(result);
  });
};

export default paymentsRoutes;
```

Rules that prevent most pool incidents:

- **Never hold a client across slow I/O.** No HTTP calls to a payment provider inside `withTransaction`: the connection and the row locks stay held for the whole round trip. Call out first, then open a short transaction to record the result.
- **Use `pool.query()` for single statements.** It checks out and releases for you. Only take a client with `pool.connect()` for transactions, and only through the helper, so the `release` can't be forgotten.
- **Reading the stats:** `waiting > 0` with `total === max` under load means exhaustion (too small, or slow transactions). `total === max` with `idle === 0` while traffic is near zero means a leak.

Verification: run `npx autocannon -c 100 -d 30 http://localhost:3000/orders` while polling `/internal/db-pool`, and on the database side check `SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();`. With the budget formula applied, the Postgres count stays under `max_connections` at peak, `waiting` drains back to 0 after the burst, and the "too many clients" error disappears.""",
            },
        ]
    },
    # 23) Multiturno: migrar de Fastify 4 a 5 y arreglar un schema abreviado.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos una API en Fastify 4 y queremos pasar a la 5. ¿Qué es lo que más se rompe y cómo lo hacemos sin sustos?",
            },
            {
                "role": "assistant",
                "content": r"""Lo que más rompe, de más a menos frecuente en proyectos reales:

1. **Node 20 o superior.** Fastify 5 no soporta versiones anteriores; actualiza primero la imagen base y el CI.
2. **Los schemas tienen que ser JSON Schema completo.** Desaparece el formato abreviado (`jsonShorthand`) en `querystring`, `params`, `body` y `response`: ya no vale pasar solo el mapa de propiedades sin `type: "object"` y `properties`. Es el cambio que más archivos toca.
3. **`reply.redirect(url, code)`**: el orden de los argumentos se invierte respecto a `reply.redirect(code, url)`.
4. **`logger` ya no acepta una instancia de logger propia**: para pasar tu instancia de pino se usa la nueva opción `loggerInstance`. `logger` queda para la configuración (`true` o un objeto de opciones).
5. **APIs eliminadas que ya estaban deprecadas en la 4:** `request.connection` (usa `request.socket`), `reply.getResponseTime()` (usa `reply.elapsedTime`), `request.routeConfig` y `request.routeSchema` (usa `request.routeOptions.config` y `request.routeOptions.schema`), y la firma variádica `listen(port, host)` (usa `listen({ port, host })`).
6. **`decorateRequest`/`decorateReply` con un objeto como valor inicial** lanza error: usa `null` y asigna en un hook, o un getter.
7. **El punto y coma ya no separa parámetros de query** por defecto (`useSemicolonDelimiter: false`).
8. **Plugins del ecosistema:** cada `@fastify/*` tiene una versión mayor para Fastify 5. Hay que subirlos todos a la vez; mezclar un plugin para la 4 con el núcleo 5 falla al registrarlo.

Cómo hacerlo sin sustos:

1. **Primero, en la 4:** sube a la última 4.x y ejecuta los tests mirando los avisos de deprecación (códigos `FSTDEP…` en la salida). Casi todo lo del punto 5 aparece ahí. Arréglalo con la 4 todavía instalada, en commits pequeños.
2. Sube Node a 20/22 en local, CI e imagen.
3. En una rama: `fastify@5` y todos los `@fastify/*` a sus versiones compatibles en el mismo commit.
4. Arranca la app: muchos de los cambios fallan al registrar las rutas, que es justo lo que quieres. Los schemas abreviados son el riesgo principal, porque según cómo esté configurado Ajv pueden fallar al arrancar o, peor, aceptarse sin validar nada; más abajo te dejo cómo detectarlos.
5. Tests, una pasada manual por redirecciones y logs, y despliegue gradual.""",
            },
            {
                "role": "user",
                "content": r"""Tenemos decenas de rutas así. ¿Cómo queda esta y cómo encuentro todas las demás?

```ts
app.get("/products", {
  schema: {
    querystring: {
      page: { type: "integer", minimum: 1, default: 1 },
      q: { type: "string" },
    },
  },
}, listProducts);
```""",
            },
            {
                "role": "assistant",
                "content": r"""Hay que envolver el mapa de propiedades en un objeto JSON Schema real:

```ts
app.get(
  "/products",
  {
    schema: {
      querystring: {
        type: "object",
        properties: {
          page: { type: "integer", minimum: 1, default: 1 },
          q: { type: "string", maxLength: 100 },
        },
        additionalProperties: false,
      },
    },
  },
  listProducts,
);
```

Por qué Fastify 5 lo exige: el formato abreviado era ambiguo. Si tu query tenía un parámetro llamado `type` o `properties`, Fastify no podía saber si era una propiedad o una palabra clave del schema. Ahora el schema es siempre JSON Schema estándar, el mismo que entienden Ajv, OpenAPI y TypeBox. De paso he añadido `maxLength` a `q`: una búsqueda sin límite de longitud es una forma barata de cargar la base de datos.

**Para encontrar todas las rutas**, no confíes solo en `grep`: las rutas con schemas en archivos separados o construidos con funciones se escapan. Pon un guard temporal con el hook `onRoute`, que se ejecuta al registrar cada ruta:

```ts
// src/plugins/schema-guard.ts
import fp from "fastify-plugin";

const PARTS = ["querystring", "params", "body", "headers"] as const;

export default fp(
  async (app) => {
    app.addHook("onRoute", (route) => {
      for (const part of PARTS) {
        const schema = route.schema?.[part] as { type?: unknown } | undefined;
        if (schema !== undefined && schema.type === undefined) {
          throw new Error(`${route.method} ${route.url}: schema.${part} is not a full JSON Schema (missing "type")`);
        }
      }
    });
  },
  { name: "schema-guard" },
);
```

Regístralo **antes** que las rutas (`app.register(schemaGuard)` al principio de `buildApp`). Al arrancar, la primera ruta abreviada aborta el arranque con su método y URL. Corrígela, vuelve a arrancar y repite hasta que arranque limpio. Es una lista de tareas generada por la propia app.

Si son decenas, plantéate migrar esos schemas a TypeBox mientras los tocas: `Type.Object({ page: Type.Integer({ minimum: 1, default: 1 }) })` siempre genera el schema completo y además te da los tipos de `request.query` gratis.

Verificación: con el guard activo, la app arranca sin errores; `curl "localhost:3000/products?page=0"` responde 400 (`minimum: 1`), `curl "localhost:3000/products"` llega al handler con `page = 1` por el `default`, y `curl "localhost:3000/products?page=2&debug=1"` deja de pasar `debug` al handler gracias a `additionalProperties: false`. Cuando termines la migración, puedes quitar el guard o dejarlo como regla del proyecto.""",
            },
        ]
    },
    # 24) Tests de Fastify con inject() y el runner nativo node:test (system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde con código y una explicación breve; usa el runner nativo de Node."},
            {
                "role": "user",
                "content": "¿Cómo testeo las rutas de mi app Fastify sin levantar el servidor? Tengo una `buildApp()` que devuelve la instancia con las rutas de usuarios (POST /users y GET /users/:id).",
            },
            {
                "role": "assistant",
                "content": r"""Con `app.inject()`: simula la petición HTTP dentro del proceso, sin sockets ni puertos, pasando por todo el ciclo real (hooks, validación, serialización).

```ts
// test/users.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../src/app.js";

const validUser = { name: "Ana", email: "ana@example.com", password: "correct-horse-battery" };

test("POST /users crea el usuario y no expone passwordHash", async (t) => {
  const app = buildApp();
  t.after(() => app.close());

  const res = await app.inject({ method: "POST", url: "/users", payload: validUser });

  assert.equal(res.statusCode, 201);
  const body = res.json();
  assert.equal(body.email, "ana@example.com");
  assert.equal("passwordHash" in body, false);
});

test("POST /users rechaza un email inválido", async (t) => {
  const app = buildApp();
  t.after(() => app.close());

  const res = await app.inject({ method: "POST", url: "/users", payload: { ...validUser, email: "nope" } });

  assert.equal(res.statusCode, 400);
  assert.match(res.json().message, /email/);
});

test("GET /users/:id: 200 si existe, 404 si no, 400 si el id no es entero", async (t) => {
  const app = buildApp();
  t.after(() => app.close());

  const created = (await app.inject({ method: "POST", url: "/users", payload: validUser })).json();

  const found = await app.inject({ method: "GET", url: `/users/${created.id}` });
  assert.equal(found.statusCode, 200);
  assert.deepEqual(Object.keys(found.json()).sort(), ["createdAt", "email", "id", "name"]);

  assert.equal((await app.inject({ method: "GET", url: "/users/999" })).statusCode, 404);
  assert.equal((await app.inject({ method: "GET", url: "/users/abc" })).statusCode, 400);
});
```

```json
{
  "scripts": {
    "test": "node --import tsx --test \"test/**/*.test.ts\""
  }
}
```

- **Una app por test**: cada `buildApp()` empieza con estado limpio, así los tests no dependen del orden.
- **`t.after(() => app.close())`** ejecuta los hooks `onClose` (pools, conexiones) aunque el test falle; sin él, el proceso puede no terminar.
- **`inject` llama a `ready()` por ti**: los plugins se cargan antes de la primera petición.
- **`Object.keys(...).sort()`** fija el contrato exacto de la respuesta; si alguien añade un campo sensible al schema, el test lo detecta.
- **`--import tsx`** ejecuta TypeScript sin compilar antes. En Node 22.6+ también existe `--experimental-strip-types` (sin flag desde Node 23.6), pero solo elimina tipos: no transforma `enum` ni rutas `.js` hacia `.ts`, así que `tsx` es más predecible hoy.
- Si `buildApp` acepta opciones de Fastify, pásale `logger: false` en los tests para no llenar la salida.

Comprobación de que muerden: quita `additionalProperties`/`format` del schema o añade `passwordHash` a la respuesta y `npm test` debe fallar en el test correspondiente. Cobertura con `node --import tsx --test --experimental-test-coverage "test/**/*.test.ts"`.""",
            },
        ]
    },
    # 25) Principiante: Hono sobre Web Standards en Bun, Deno, Workers y Node.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Qué es Hono y por qué dicen que corre «en todos lados»? ¿Me enseñas una API mínima que funcione igual en Bun, Deno, Cloudflare Workers y Node?",
            },
            {
                "role": "assistant",
                "content": r"""Hono es un framework web pequeño construido **solo sobre estándares web**: `Request`, `Response`, `URL`, `Headers`, `fetch`, Web Crypto y streams. Una app de Hono es, en el fondo, una función `fetch(request) => Response`. Bun, Deno y Cloudflare Workers implementan esas APIs de forma nativa, y en Node un adaptador (`@hono/node-server`) traduce entre el `http` de Node y `Request`/`Response`. Por eso el mismo código de rutas corre en los cuatro: lo único que cambia es el archivo de arranque.

**La app, común a todos los runtimes:**

```ts
// src/app.ts
import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";

type Todo = { id: number; title: string; done: boolean };

// Estado en memoria solo para el ejemplo: en Workers cada isolate tendría el suyo
const todos = new Map<number, Todo>([[1, { id: 1, title: "Probar Hono", done: false }]]);
let nextId = 2;

export const app = new Hono();

app.get("/", (c) => c.text("ok"));

app.get("/todos", (c) => {
  const onlyPending = c.req.query("pending") === "true";
  const list = [...todos.values()].filter((todo) => !onlyPending || !todo.done);
  return c.json(list);
});

app.get("/todos/:id", (c) => {
  const id = Number(c.req.param("id"));
  const todo = todos.get(id);
  if (!todo) throw new HTTPException(404, { message: `Todo ${id} not found` });
  return c.json(todo);
});

app.post("/todos", async (c) => {
  const body = await c.req.json<{ title?: unknown }>();
  if (typeof body.title !== "string" || body.title.trim() === "") {
    throw new HTTPException(400, { message: "title is required" });
  }
  const todo: Todo = { id: nextId++, title: body.title.trim(), done: false };
  todos.set(todo.id, todo);
  return c.json(todo, 201);
});

app.notFound((c) => c.json({ message: "Not found" }, 404));

app.onError((err, c) => {
  if (err instanceof HTTPException) return c.json({ message: err.message }, err.status);
  console.error(err);
  return c.json({ message: "Internal server error" }, 500);
});
```

**Arranque en cada runtime:**

```ts
// src/bun.ts  →  bun run src/bun.ts
import { app } from "./app";
export default { port: 3000, fetch: app.fetch };
```

```ts
// src/deno.ts  →  deno run --allow-net src/deno.ts
// (en deno.json, mapea "hono" a "jsr:@hono/hono" en "imports")
import { app } from "./app.ts";
Deno.serve({ port: 3000 }, app.fetch);
```

```ts
// src/worker.ts  →  npx wrangler dev   (main = "src/worker.ts" en wrangler.toml)
import { app } from "./app";
export default app;
```

```ts
// src/node.ts  →  npx tsx src/node.ts
import { serve } from "@hono/node-server";
import { app } from "./app";

serve({ fetch: app.fetch, port: 3000 }, (info) => {
  console.log(`Escuchando en http://localhost:${info.port}`);
});
```

Lo que conviene entender:

- **`c` (el contexto)** agrupa la petición (`c.req.param`, `c.req.query`, `c.req.json`) y los constructores de respuesta (`c.json`, `c.text`, `c.html`). Cada handler devuelve un `Response`.
- **`HTTPException` + `onError`**: lanzas el error donde ocurre y lo conviertes en respuesta en un único sitio.
- **La portabilidad tiene un límite**: en cuanto usas `fs`, `process.env` o los *bindings* de Cloudflare (KV, D1) dentro de las rutas, ese código queda atado a un runtime. Mantén esas dependencias en los bordes y pásalas a la app.

Verificación sin levantar nada: Hono trae `app.request()`, que ejecuta la app en memoria y devuelve un `Response`, igual en todos los runtimes:

```ts
const ok = await app.request("/todos/1");
const missing = await app.request("/todos/999");
console.log(ok.status, await ok.json(), missing.status); // 200 { id: 1, ... } 404
```

Y con cualquiera de los arranques: `curl localhost:3000/todos/1` (o `:8787` con `wrangler dev`) devuelve el mismo JSON en los cuatro.""",
            },
        ]
    },
    # 26) Hono: validación con @hono/zod-validator y cliente RPC tipado con hc (system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo un backend en Hono y un frontend en React en el mismo monorepo. ¿Cómo valido las entradas con zod y consigo que el cliente del front esté tipado sin generar código ni escribir los tipos dos veces?",
            },
            {
                "role": "assistant",
                "content": r"""Hono lo resuelve con dos piezas: `zValidator` valida y tipa cada entrada a partir del schema, y el cliente RPC `hc` lee el **tipo** de tu app (solo el tipo, no el código) para ofrecer en el front llamadas tipadas de extremo a extremo. Asumo zod 4 y `@hono/zod-validator`.

**Servidor:**

```ts
// apps/api/src/routes/posts.ts
import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { z } from "zod";

const createPostSchema = z.object({
  title: z.string().trim().min(3).max(120),
  body: z.string().min(1).max(10_000),
  tags: z.array(z.string().max(30)).max(5).default([]),
});

const listQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
});

type Post = z.infer<typeof createPostSchema> & { id: string; createdAt: string };

const PAGE_SIZE = 20;
const posts: Post[] = [];

// Las rutas encadenadas conservan su tipo; separadas en sentencias sueltas, el tipo se pierde
export const postsRoutes = new Hono()
  .get("/", zValidator("query", listQuerySchema), (c) => {
    const { page } = c.req.valid("query"); // number, ya convertido
    const items = posts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    return c.json({ page, items }, 200);
  })
  .post(
    "/",
    zValidator("json", createPostSchema, (result, c) => {
      // Formato de error propio en lugar del que trae el validador por defecto
      if (!result.success) {
        return c.json({ message: "Invalid body", issues: result.error.issues }, 400);
      }
    }),
    (c) => {
      const input = c.req.valid("json");
      const post: Post = { ...input, id: crypto.randomUUID(), createdAt: new Date().toISOString() };
      posts.push(post);
      return c.json(post, 201);
    },
  )
  .get("/:id", (c) => {
    const post = posts.find((p) => p.id === c.req.param("id"));
    if (!post) return c.json({ message: "Post not found" }, 404);
    return c.json(post, 200);
  });
```

```ts
// apps/api/src/app.ts
import { Hono } from "hono";
import { postsRoutes } from "./routes/posts";

export const app = new Hono().basePath("/api").route("/posts", postsRoutes);

export type AppType = typeof app;
```

**Cliente en el front:**

```ts
// apps/web/src/api.ts
import { hc } from "hono/client";
import type { AppType } from "../../api/src/app"; // import de tipo: no entra código del servidor en el bundle

export const client = hc<AppType>(window.location.origin);

export async function createPost(title: string, body: string) {
  const res = await client.api.posts.$post({ json: { title, body } }); // json tipado con el schema
  if (!res.ok) throw new Error(`No se pudo crear el post (HTTP ${res.status})`);
  return res.json(); // tipado como Post
}

export async function getPost(id: string) {
  const res = await client.api.posts[":id"].$get({ param: { id } });
  if (res.status === 404) return null;
  return res.json(); // Post: la rama 404 ya está descartada
}

export async function listPosts(page: number) {
  const res = await client.api.posts.$get({ query: { page: String(page) } }); // la query viaja como texto
  return res.json(); // { page: number; items: Post[] }
}
```

Por qué así:

- **Un único origen de verdad**: el schema de zod valida en el servidor y, a través del tipo de la app, define lo que el cliente puede enviar. Cambias `title` por `heading` en el servidor y el front deja de compilar.
- **Rutas encadenadas** (`new Hono().get(...).post(...)`): el tipo de la app se construye acumulando cada ruta. Si escribes `app.get(...)` en sentencias separadas, `typeof app` no las incluye y el cliente queda sin tipos.
- **Status explícito en `c.json(data, 200)` y `c.json(..., 404)`**: el cliente conoce los códigos posibles de cada ruta y estrecha el tipo del cuerpo según `res.status`, como en `getPost`.
- **El hook de `zValidator`** te deja decidir el formato del 400; sin él, el validador responde con su formato por defecto.
- **Requisitos para que funcione la inferencia**: TypeScript en modo `strict` en los dos paquetes y la misma versión de `hono` en servidor y cliente.

Verificación: `npx tsc --noEmit` en `apps/web` pasa; cambia `title` por `heading` en `createPostSchema` y el mismo comando falla en `createPost`. En el servidor:

```bash
curl -s -X POST localhost:3000/api/posts -H 'content-type: application/json' -d '{"title":"Hi","body":""}'
# 400 {"message":"Invalid body","issues":[...]}  (título demasiado corto y cuerpo vacío)
```""",
            },
        ]
    },
    # 27) Multiturno rioplatense: middlewares de Hono y middleware propio con Variables tipadas.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "Estoy armando una API con Hono para Cloudflare Workers. ¿Qué middlewares de los que trae me conviene poner sí o sí? Necesito CORS para mi front, cabeceras de seguridad, logs y JWT en todo `/api/*`.",
            },
            {
                "role": "assistant",
                "content": r"""Para lo que contás, cuatro de los que vienen incluidos, y el orden importa:

```ts
// src/index.ts
import { Hono } from "hono";
import { cors } from "hono/cors";
import { jwt } from "hono/jwt";
import type { JwtVariables } from "hono/jwt";
import { logger } from "hono/logger";
import { secureHeaders } from "hono/secure-headers";

type Bindings = {
  JWT_SECRET: string;
  ALLOWED_ORIGINS: string; // "https://app.example.com,https://admin.example.com"
};

const app = new Hono<{ Bindings: Bindings; Variables: JwtVariables }>();

app.use(logger());
app.use(secureHeaders());

// En Workers la config llega por petición en c.env, así que el middleware se crea adentro
app.use("/api/*", (c, next) =>
  cors({
    origin: c.env.ALLOWED_ORIGINS.split(","),
    credentials: true,
    maxAge: 600,
  })(c, next),
);
app.use("/api/*", (c, next) => jwt({ secret: c.env.JWT_SECRET, alg: "HS256" })(c, next));

app.get("/health", (c) => c.json({ ok: true }));

app.get("/api/me", (c) => {
  const payload = c.get("jwtPayload"); // lo deja el middleware jwt
  return c.json({ sub: payload.sub });
});

export default app;
```

Por qué cada uno y en ese orden:

- **`logger()` primero**: envuelve todo lo demás, así registra también las respuestas 401 y los errores. En Workers lo ves con `npx wrangler tail`.
- **`secureHeaders()`**: agrega cabeceras como `X-Content-Type-Options`, `X-Frame-Options` y `Strict-Transport-Security` con valores razonables. Para una API JSON alcanza con los valores por defecto.
- **`cors` antes que `jwt`**: el navegador manda un *preflight* `OPTIONS` sin tu token. `cors` lo contesta y corta la cadena; si `jwt` fuera antes, el preflight recibiría un 401 y el navegador bloquearía la petición real con un error de CORS que despista.
- **Origins como lista explícita** y `credentials: true` solo si usás cookies; nunca `*` con credenciales.
- **`jwt` con `alg` fijo**: aceptás solo el algoritmo con el que firmás, en vez de confiar en el que declara el token.
- **El patrón `(c, next) => middleware(...)(c, next)`**: en Workers no hay `process.env` al cargar el módulo; los secretos llegan en `c.env` con cada petición. Construir el middleware adentro es la forma de leerlos.

Verificación:

```bash
curl -i localhost:8787/health                                  # 200, con las cabeceras de secureHeaders
curl -i localhost:8787/api/me                                  # 401
curl -i -X OPTIONS localhost:8787/api/me \
  -H "Origin: https://app.example.com" -H "Access-Control-Request-Method: GET"   # 204 con Access-Control-Allow-Origin
```""",
            },
            {
                "role": "user",
                "content": "Bárbaro. Ahora quiero un middleware mío que cargue el usuario desde D1 con el `sub` del token y otro que exija un rol. Y que `c.get(\"user\")` quede tipado en los handlers.",
            },
            {
                "role": "assistant",
                "content": r"""Para eso está `createMiddleware` de `hono/factory`: le pasás el tipo del entorno (bindings y variables) y `c.set`/`c.get` quedan tipados.

```ts
// src/auth.ts
import { createMiddleware } from "hono/factory";
import { HTTPException } from "hono/http-exception";
import type { JwtVariables } from "hono/jwt";

export type User = { id: string; email: string; role: "admin" | "member" };

export type AppEnv = {
  Bindings: {
    DB: D1Database;
    JWT_SECRET: string;
    ALLOWED_ORIGINS: string;
  };
  Variables: JwtVariables & { user: User };
};

export const loadUser = createMiddleware<AppEnv>(async (c, next) => {
  const { sub } = c.get("jwtPayload");
  if (typeof sub !== "string") throw new HTTPException(401, { message: "Invalid token subject" });

  const user = await c.env.DB.prepare("SELECT id, email, role FROM users WHERE id = ?")
    .bind(sub)
    .first<User>();
  // Token válido pero usuario borrado o desactivado: no se le deja pasar
  if (!user) throw new HTTPException(401, { message: "User no longer exists" });

  c.set("user", user);
  await next();
});

export const requireRole = (role: User["role"]) =>
  createMiddleware<AppEnv>(async (c, next) => {
    if (c.get("user").role !== role) throw new HTTPException(403, { message: "Forbidden" });
    await next();
  });
```

```ts
// src/index.ts (lo nuevo respecto a antes)
import { HTTPException } from "hono/http-exception";
import { type AppEnv, loadUser, requireRole } from "./auth";

const app = new Hono<AppEnv>();

// después de cors y jwt:
app.use("/api/*", loadUser);

app.get("/api/me", (c) => c.json(c.get("user"))); // User, tipado

app.delete("/api/users/:id", requireRole("admin"), async (c) => {
  await c.env.DB.prepare("DELETE FROM users WHERE id = ?").bind(c.req.param("id")).run();
  return c.body(null, 204);
});

app.onError((err, c) => {
  if (err instanceof HTTPException) return c.json({ message: err.message }, err.status);
  console.error(err);
  return c.json({ message: "Internal server error" }, 500);
});
```

Detalles que te van a ahorrar un rato:

- **`await next()` siempre con `await`**: lo que escribas después corre cuando la respuesta vuelve (ahí podés agregar cabeceras o medir). Sin `await`, el middleware termina antes de tiempo y los errores de más adentro se pierden.
- **`throw new HTTPException`** en vez de `return c.json(...)`: corta la cadena y deja el formato de error en un solo lugar, el `onError`.
- **401 frente a 403**: `loadUser` responde 401 (no sabemos quién sos o ya no existís); `requireRole`, 403 (sabemos quién sos y no te alcanza).
- **`D1Database`** viene de los tipos de Workers. Lo más prolijo es generarlos con `npx wrangler types`, que crea la interfaz `Env` a partir de tu `wrangler.toml`, y usarla en `Bindings`.
- **Una consulta a D1 por petición**: si te pesa, cacheá el usuario unos segundos en KV, sabiendo que un cambio de rol tardará ese tiempo en aplicarse.

Verificación con `wrangler dev` y tres tokens: el de un `member` recibe 403 en `DELETE /api/users/42`; el de un `admin`, 204; y el de un usuario que borraste de D1, 401 aunque el token siga sin expirar.""",
            },
        ]
    },
    # 28) ERR: «process is not defined» en Cloudflare Workers; bindings y secretos.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Pasé mi API de Hono de Node a Cloudflare Workers y con `wrangler dev` me sale esto nada más arrancar:

```
✘ [ERROR] Uncaught ReferenceError: process is not defined
    at null.<anonymous> (src/index.ts:6:16)
```

La línea 6 es `const secret = process.env.JWT_SECRET!;`. También leo `process.env.DATABASE_URL` en otro archivo.""",
            },
            {
                "role": "assistant",
                "content": r"""Workers no es Node: no existe el objeto global `process`. La configuración y los secretos llegan como **bindings** en el argumento `env` de cada petición, que en Hono es `c.env`. Y el error salta «nada más arrancar» porque lo lees a nivel de módulo, al cargar el archivo, cuando todavía no hay ninguna petición.

**El arreglo idiomático: bindings tipados y lectura dentro de la petición.**

```ts
// src/index.ts
import { Hono } from "hono";
import { jwt } from "hono/jwt";

type Bindings = {
  JWT_SECRET: string;   // secreto: npx wrangler secret put JWT_SECRET
  PUBLIC_BASE_URL: string; // variable normal: [vars] en wrangler.toml
  CACHE: KVNamespace;   // binding de KV
  DB: D1Database;       // binding de D1 (sustituye a tu DATABASE_URL)
};

const app = new Hono<{ Bindings: Bindings }>();

app.use("/api/*", async (c, next) => {
  if (!c.env.JWT_SECRET) throw new Error("JWT_SECRET binding is missing"); // falla claro, sin el `!`
  return jwt({ secret: c.env.JWT_SECRET, alg: "HS256" })(c, next);
});

app.get("/api/products/:id", async (c) => {
  const id = c.req.param("id");
  const cached = await c.env.CACHE.get(`product:${id}`, "json");
  if (cached) return c.json(cached);

  const product = await c.env.DB.prepare("SELECT id, name, price_cents FROM products WHERE id = ?")
    .bind(id)
    .first();
  if (!product) return c.json({ message: "Not found" }, 404);

  await c.env.CACHE.put(`product:${id}`, JSON.stringify(product), { expirationTtl: 60 });
  return c.json(product);
});

export default app;
```

```toml
# wrangler.toml
name = "products-api"
main = "src/index.ts"
compatibility_date = "2025-09-01"

[vars]
PUBLIC_BASE_URL = "https://shop.example.com"

[[kv_namespaces]]
binding = "CACHE"
id = "4f9c2a1e7b3d4c8a9e0f1a2b3c4d5e6f"

[[d1_databases]]
binding = "DB"
database_name = "products"
database_id = "0b6d3c1e-2f4a-4b5c-9d8e-7f6a5b4c3d2e"
```

Secretos, en local y en producción:

```bash
npx wrangler secret put JWT_SECRET   # producción: lo pide por consola y no queda en ningún archivo
```

```
# .dev.vars  (solo para wrangler dev; añádelo a .gitignore)
JWT_SECRET=un-secreto-local-de-al-menos-32-caracteres
```

Por qué así:

- **Bindings en vez de cadenas de conexión.** En Workers no abres una conexión TCP a tu base de datos con una URL; declaras un binding (D1, KV, R2, Hyperdrive para Postgres) y el runtime te da el objeto ya conectado. Por eso `DATABASE_URL` desaparece.
- **Tipos generados**: `npx wrangler types` crea la interfaz `Env` a partir de `wrangler.toml`; úsala como `new Hono<{ Bindings: Env }>()` y no mantengas el tipo a mano.
- **El `!` escondía el problema.** `process.env.JWT_SECRET!` le dice a TypeScript «confía en mí»; si el secreto falta, firmas o verificas con `undefined`. La comprobación explícita falla con un mensaje claro.

**Si tienes que mantener el mismo código en Node y en Workers**, usa el helper de Hono que lee la variable del sitio correcto en cada runtime (`c.env` en Workers, `process.env` en Node, `Deno.env` en Deno):

```ts
import { env } from "hono/adapter";

app.get("/api/config", (c) => {
  const { PUBLIC_BASE_URL } = env<{ PUBLIC_BASE_URL: string }>(c);
  return c.json({ baseUrl: PUBLIC_BASE_URL });
});
```

La alternativa rápida es activar `compatibility_flags = ["nodejs_compat"]`: con una `compatibility_date` reciente, `process.env` existe y se rellena con tus variables y secretos. Funciona, pero arrastra polyfills de Node al bundle, no te da ni `fs` ni conexiones TCP arbitrarias como en Node, y esconde la dependencia del runtime. Para código nuevo, mejor `c.env`.

Verificación: `npx wrangler dev` arranca sin el `ReferenceError`; `curl localhost:8787/api/products/1` sin token responde 401; con un token firmado con el secreto de `.dev.vars`, 200, y la segunda petición al mismo producto ya no toca D1 (lo ves en los logs de `wrangler dev`, o añadiendo temporalmente una cabecera `x-cache: hit` en la rama de KV).""",
            },
        ]
    },
    # 29) EN: Server-Sent Events con streamSSE de Hono, reconexión y Last-Event-ID.
    {
        "messages": [
            {
                "role": "user",
                "content": "With Hono, I need to push order status updates to an internal dashboard. Should I use WebSockets or Server-Sent Events? If SSE, how do I implement it properly, including reconnection without losing events?",
            },
            {
                "role": "assistant",
                "content": r"""Use **SSE**. The data flows one way (server → dashboard), and SSE gives you that over plain HTTP with reconnection built into the browser's `EventSource`: it reconnects on its own and sends the last event id it received in a `Last-Event-ID` header, so the server can replay what was missed. It works with cookies for auth, through HTTP/2 and most proxies. Reach for WebSockets when the client also sends frequent messages (chat, collaborative editing).

```ts
// src/orders-stream.ts
import { Hono } from "hono";
import { streamSSE } from "hono/streaming";

type OrderEvent = { id: number; orderId: string; status: string };

const HEARTBEAT_MS = 15_000;
const MAX_BUFFERED_EVENTS = 1_000;

// In-process event log for the example. With several instances, this must be a shared
// bus (Redis Streams, Postgres LISTEN/NOTIFY) or each instance only sees its own events.
const recentEvents: OrderEvent[] = [];
const listeners = new Set<(event: OrderEvent) => void>();
let lastEventId = 0;

export function publishOrderEvent(orderId: string, status: string): void {
  const event: OrderEvent = { id: ++lastEventId, orderId, status };
  recentEvents.push(event);
  if (recentEvents.length > MAX_BUFFERED_EVENTS) recentEvents.shift();
  for (const listener of listeners) listener(event);
}

export const ordersStream = new Hono();

ordersStream.get("/orders/stream", (c) =>
  streamSSE(c, async (stream) => {
    const resumeFrom = Number(c.req.header("Last-Event-ID") ?? 0);
    const queue: OrderEvent[] = recentEvents.filter((event) => event.id > resumeFrom); // replay
    let wake: (() => void) | undefined;
    let aborted = false;

    const listener = (event: OrderEvent) => {
      queue.push(event);
      wake?.();
    };
    listeners.add(listener);
    stream.onAbort(() => {
      aborted = true;
      wake?.();
    });

    try {
      await stream.writeSSE({ event: "ready", data: "connected", retry: 3_000 }); // reconnect after 3 s
      while (!aborted) {
        const next = queue.shift();
        if (next) {
          await stream.writeSSE({ id: String(next.id), event: "order-status", data: JSON.stringify(next) });
          continue;
        }
        // Wait for a new event or for the heartbeat interval, whichever comes first
        await new Promise<void>((resolve) => {
          const timer = setTimeout(resolve, HEARTBEAT_MS);
          wake = () => {
            clearTimeout(timer);
            resolve();
          };
        });
        wake = undefined;
        if (!aborted && queue.length === 0) {
          await stream.writeSSE({ event: "heartbeat", data: "" }); // keeps proxies from closing an idle connection
        }
      }
    } finally {
      listeners.delete(listener);
    }
  }),
);

ordersStream.post("/orders/:id/status", async (c) => {
  const { status } = await c.req.json<{ status: string }>();
  publishOrderEvent(c.req.param("id"), status);
  return c.body(null, 204);
});
```

Dashboard side:

```ts
type OrderEvent = { id: number; orderId: string; status: string };

const source = new EventSource("/orders/stream", { withCredentials: true });

source.addEventListener("order-status", (e) => {
  const event = JSON.parse((e as MessageEvent<string>).data) as OrderEvent;
  console.log(`order ${event.orderId} is now ${event.status}`);
});

source.onerror = () => {
  // The browser retries on its own using the "retry" value; this is just for visibility
  console.warn("order stream interrupted, reconnecting");
};
```

Why it's built this way:

- **`id` on every event** is what makes resumption work: on reconnect the browser sends `Last-Event-ID`, and the handler replays everything newer from the buffer before switching to live events.
- **The cleanup in `finally`** removes the listener when the client goes away; without it, every closed tab leaks a listener that keeps receiving events forever.
- **Heartbeats** matter in practice: many proxies and load balancers close connections that stay silent for 30-60 seconds.
- **Deployment gotchas:** reverse proxies that buffer responses (nginx by default) hold events back; disable buffering for this route (`proxy_buffering off;` or the `X-Accel-Buffering: no` header). Over HTTP/1.1 browsers allow only about six connections per host, so several dashboard tabs can starve other requests; serve it over HTTP/2.

Verification: `curl -N localhost:3000/orders/stream` in one terminal; in another, `curl -X POST localhost:3000/orders/42/status -H 'content-type: application/json' -d '{"status":"shipped"}'` three times. Each event appears immediately with ids 1, 2, 3. Stop the first curl, publish two more, then reconnect with `curl -N -H 'Last-Event-ID: 3' localhost:3000/orders/stream`: events 4 and 5 are replayed first, and nothing is lost.""",
            },
        ]
    },
    # 30) Revisión estricta de un Dockerfile de una sola etapa para una API Hono en Node 22.
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala primero el problema más grave."},
            {
                "role": "user",
                "content": r"""Revisa este Dockerfile de nuestra API (Hono sobre Node 22 con `@hono/node-server`; TypeScript compilado a `dist/`). La imagen pesa 1,4 GB y cuando Kubernetes reinicia el pod tarda 30 segundos en morir.

```dockerfile
FROM node:22
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build
ENV JWT_SECRET=dev-secret-123
EXPOSE 3000
CMD npm start
```""",
            },
            {
                "role": "assistant",
                "content": r"""Por orden de gravedad:

**1. Crítico: un secreto dentro de la imagen.** `ENV JWT_SECRET=...` queda grabado en la configuración de la imagen; cualquiera con acceso al registro lo lee con `docker inspect` o `docker history`. Además `COPY . .` copia lo que haya en el directorio: `.env`, `.git`, claves locales. Rota ese secreto ya, aunque «sea de desarrollo»: si la misma imagen llegó a producción, es el secreto de producción.

**2. Alto: la aplicación nunca recibe SIGTERM, y por eso tarda 30 s en morir.** `CMD npm start` en forma *shell* ejecuta `/bin/sh -c "npm start"`; el PID 1 es el shell, que no reenvía señales, y por debajo está npm, que tampoco es un buen PID 1. Kubernetes manda SIGTERM, nadie lo atiende, espera el `terminationGracePeriodSeconds` (30 s por defecto) y mata con SIGKILL, cortando las peticiones en curso. Tus 30 segundos son exactamente ese plazo.

**3. Alto: corre como root.** Una vulnerabilidad en la app o en una dependencia da root dentro del contenedor.

**4. Medio: `npm install` y dependencias de desarrollo en la imagen final.** `npm install` puede resolver versiones distintas a las del lockfile; `npm ci` instala exactamente lo bloqueado. Y TypeScript, linters y frameworks de test viajan a producción.

**5. Medio: imagen base completa y caché inútil.** `node:22` es la imagen Debian completa con herramientas de compilación. Y como `COPY . .` va antes de instalar, cualquier cambio en el código invalida la capa de dependencias y reinstala todo en cada build.

**6. Bajo:** falta `.dockerignore`, `NODE_ENV=production` y un healthcheck.

Versión corregida, multi-stage:

```dockerfile
# syntax=docker/dockerfile:1

# 1) Dependencias completas para compilar (capa cacheada mientras no cambie el lockfile)
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# 2) Compilación de TypeScript
FROM deps AS build
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# 3) Solo dependencias de producción
FROM node:22-slim AS prod-deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

# 4) Imagen final: sin compilador, sin devDependencies, sin código fuente
FROM node:22-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app
COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/health').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
# Forma exec: node es el PID 1 y recibe SIGTERM directamente
CMD ["node", "dist/server.js"]
```

```
# .dockerignore
node_modules
dist
.git
.env
.env.*
coverage
*.log
```

Y el otro lado del arreglo del punto 2: que la app sepa apagarse cuando por fin recibe la señal.

```ts
// src/server.ts
import { serve } from "@hono/node-server";
import { app } from "./app.js";

const SHUTDOWN_TIMEOUT_MS = 10_000;

const server = serve({ fetch: app.fetch, port: Number(process.env.PORT ?? 3000) }, (info) => {
  console.log(`listening on ${info.port}`);
});

function shutdown(signal: NodeJS.Signals): void {
  console.log(`${signal} received, draining connections`);
  server.close((err) => process.exit(err ? 1 : 0)); // deja de aceptar y espera a las peticiones en curso
  setTimeout(() => process.exit(1), SHUTDOWN_TIMEOUT_MS).unref(); // red de seguridad
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
```

Decisiones que no son obvias:

- **Los archivos de la imagen final pertenecen a root y la app corre como `node`.** Sin `--chown`: el proceso puede leer su código pero no modificarlo, lo que limita lo que puede hacer un atacante que tome el proceso.
- **`node:22-slim` y no alpine.** Alpine es más pequeña, pero usa musl y algunas dependencias nativas dan problemas; slim es el equilibrio seguro. Con esto la imagen baja del orden de 1,4 GB a unos pocos cientos de MB, según tus dependencias.
- **El secreto entra en tiempo de ejecución**: un Secret de Kubernetes expuesto como variable de entorno, o `docker run -e JWT_SECRET=...` en local. Nunca como `ENV` ni `ARG` del build.
- **`HEALTHCHECK` sirve para Docker y Compose**; Kubernetes lo ignora y usa sus propias `readinessProbe` y `livenessProbe` contra el mismo `/health`.
- Si tu app crea procesos hijos, añade un init mínimo (`docker run --init` o `tini` como `ENTRYPOINT`) para recoger procesos zombis; para una API que no lanza procesos, node como PID 1 con manejo de señales es suficiente.

Verificación:

```bash
docker build -t orders-api .
docker image ls orders-api                                        # tamaño final
docker history --no-trunc orders-api | grep -c JWT_SECRET         # 0
docker run -d --name api -e JWT_SECRET=local-secret-32-chars-minimum-ok -p 3000:3000 orders-api
docker exec api id -u                                             # 1000 (usuario node), no 0
time docker stop api                                              # ~1 s en lugar de esperar al plazo
```""",
            },
        ]
    },
]
