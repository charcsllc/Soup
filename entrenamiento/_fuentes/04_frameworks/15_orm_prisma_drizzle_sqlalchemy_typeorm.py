"""ORMs: Prisma 6, Drizzle, SQLAlchemy 2.x y TypeORM 0.3, más temas transversales de acceso a datos.

30 filas. Reparto aproximado: Prisma 9 · Drizzle 7 · SQLAlchemy 9 · TypeORM 5. Lo transversal
(unit of work, identity map, SQL a mano, transacciones e idempotencia, pooling, paginación,
soft delete, UUID) va repartido dentro de esas filas. Sigue entrenamiento/GUIA_DE_ESTILO.md.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Prisma: schema básico y migrate dev / deploy / db push (SISTEMA, principiante-intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Empiezo con Prisma 6 en un proyecto Node con Postgres. ¿Cómo defino bien el schema y qué diferencia hay entre `migrate dev`, `migrate deploy` y `db push`? En el equipo cada uno usa uno distinto y ya nos dio problemas.",
            },
            {
                "role": "assistant",
                "content": """Los problemas vienen de mezclar comandos que tienen propósitos distintos. Primero un schema razonable y después las reglas de uso.

```prisma
// prisma/schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(uuid()) @db.Uuid
  email     String   @unique
  name      String?
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz(3)
  orders    Order[]

  @@map("users")
}

model Order {
  id         String      @id @default(uuid()) @db.Uuid
  userId     String      @map("user_id") @db.Uuid
  user       User        @relation(fields: [userId], references: [id], onDelete: Cascade)
  totalCents Int         @map("total_cents")
  status     OrderStatus @default(PENDING)
  createdAt  DateTime    @default(now()) @map("created_at") @db.Timestamptz(3)

  @@index([userId])
  @@map("orders")
}

enum OrderStatus {
  PENDING
  PAID
  CANCELLED
}
```

Decisiones del schema:

- **`@map` / `@@map`**: en TypeScript, `createdAt`; en la base, `created_at`. Quien consulte la base con SQL no tiene que lidiar con comillas por las mayúsculas.
- **`@db.Timestamptz`**: guarda el instante con zona horaria. Un `timestamp` sin zona es la fuente número uno de bugs de horas desplazadas.
- **Dinero en céntimos (`Int`)**: los decimales en coma flotante no suman bien; si necesitas fracciones de céntimo, `Decimal` con `@db.Decimal(12, 4)`.
- **`@@index([userId])`**: Postgres no crea índices para las claves foráneas automáticamente, y casi siempre las vas a filtrar.

**Los comandos y cuándo usar cada uno:**

| Comando | Dónde | Qué hace |
|---|---|---|
| `prisma migrate dev --name add_orders` | tu máquina | compara el schema con el historial de migraciones, genera el SQL en `prisma/migrations/`, lo aplica a tu base local y regenera el cliente |
| `prisma migrate deploy` | CI y producción | aplica las migraciones pendientes de la carpeta; nunca genera nada ni borra datos |
| `prisma db push` | prototipos desechables | sincroniza la base con el schema **sin** crear migraciones; puede perder datos y no deja historial |
| `prisma migrate reset` | tu máquina | borra la base local, reaplica todo y ejecuta el seed |
| `prisma generate` | build | regenera los tipos del cliente |

**Reglas para el equipo**, que son las que evitan los problemas que describes:

1. **La carpeta `prisma/migrations` va al repositorio** y es la fuente de verdad del esquema.
2. **Una migración aplicada no se edita nunca.** Si está mal, se crea otra que la corrija.
3. **Producción solo recibe `migrate deploy`**, ejecutado por el pipeline, no por una persona.
4. **`db push` jamás contra una base compartida.** Cambia el esquema sin dejar rastro; después, el `migrate dev` de un compañero detecta *drift* («Drift detected: Your database schema is not in sync with your migration history») y le propone resetear su base.
5. **Revisa el SQL generado** antes de hacer commit. Para cambios delicados (renombrar una columna, que Prisma interpreta como borrar y crear), `migrate dev --create-only` genera el archivo sin aplicarlo y te deja editarlo.

Comprobación: en CI, levanta un Postgres vacío y ejecuta `prisma migrate deploy` seguido de `prisma migrate status`. Si el historial completo se aplica desde cero y el estado dice que está al día, las migraciones son reproducibles.""",
            },
        ]
    },
    # 2) Prisma: relación muchos a muchos explícita con datos propios (rioplatense)
    {
        "messages": [
            {
                "role": "user",
                "content": "En Prisma tengo usuarios y cursos: un usuario se inscribe en muchos cursos y un curso tiene muchos alumnos. Además quiero guardar la fecha de inscripción y el progreso. ¿Cómo lo modelo? ¿Uso la relación muchos a muchos implícita?",
            },
            {
                "role": "assistant",
                "content": """No: la implícita no te sirve en cuanto la relación tiene datos propios. La relación muchos a muchos implícita (`courses Course[]` en `User` y `users User[]` en `Course`) hace que Prisma cree una tabla intermedia oculta con solo las dos claves, y no podés agregarle columnas. Como querés fecha y progreso, la inscripción es una **entidad** y se modela explícitamente:

```prisma
model User {
  id          String       @id @default(uuid()) @db.Uuid
  email       String       @unique
  enrollments Enrollment[]
}

model Course {
  id          String       @id @default(uuid()) @db.Uuid
  title       String
  enrollments Enrollment[]
}

model Enrollment {
  userId     String   @map("user_id") @db.Uuid
  courseId   String   @map("course_id") @db.Uuid
  enrolledAt DateTime @default(now()) @map("enrolled_at") @db.Timestamptz(3)
  progress   Int      @default(0) // porcentaje 0-100
  user       User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  course     Course   @relation(fields: [courseId], references: [id], onDelete: Cascade)

  @@id([userId, courseId])
  @@index([courseId])
  @@map("enrollments")
}
```

Las consultas habituales:

```ts
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

// Inscribir
await prisma.enrollment.create({ data: { userId, courseId } });

// Mis cursos con su progreso, el más reciente primero
const myCourses = await prisma.enrollment.findMany({
  where: { userId },
  orderBy: { enrolledAt: "desc" },
  select: {
    progress: true,
    enrolledAt: true,
    course: { select: { id: true, title: true } },
  },
});

// Actualizar el progreso: la clave compuesta se nombra campo1_campo2
await prisma.enrollment.update({
  where: { userId_courseId: { userId, courseId } },
  data: { progress: 60 },
});

// Alumnos de un curso
const students = await prisma.enrollment.findMany({
  where: { courseId },
  select: { progress: true, user: { select: { id: true, email: true } } },
});
```

Decisiones:

- **`@@id([userId, courseId])`** como clave primaria compuesta: además de identificar la fila, impide inscribir dos veces al mismo usuario en el mismo curso. El segundo intento falla con `P2002`, que podés traducir a «ya estás inscripto».
- **`@@index([courseId])`**: la clave compuesta empieza por `userId`, así que sirve para «cursos de un usuario» pero no para «alumnos de un curso». Ese segundo índice cubre la otra dirección.
- **`onDelete: Cascade`** en ambos lados: si se borra el usuario o el curso, sus inscripciones no tienen sentido sin él.
- **El rango 0-100 del progreso**: el schema de Prisma no expresa restricciones `CHECK`. Validalo en la aplicación y, si querés la garantía en la base, generá la migración con `prisma migrate dev --create-only` y agregá al SQL `ALTER TABLE enrollments ADD CONSTRAINT progress_range CHECK (progress BETWEEN 0 AND 100);` antes de aplicarla.

La implícita sigue siendo cómoda cuando la relación es solo un vínculo sin datos (etiquetas de un artículo, por ejemplo). Si dudás, la explícita: pasar de implícita a explícita más adelante exige migrar los datos de la tabla oculta.

Comprobación: inscribí al mismo usuario dos veces en el mismo curso y verificá que la segunda falla con `P2002`; después consultá `EXPLAIN` de «alumnos de un curso» y tiene que usar el índice de `course_id`.""",
            },
        ]
    },
    # 3) Prisma: select frente a include, omit y tipos derivados (multiturno, seguridad)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuál es la diferencia entre `select` e `include` en Prisma? Tengo un endpoint de lista de usuarios que devuelve todo el modelo, incluido el hash de la contraseña, y me di cuenta tarde.",
            },
            {
                "role": "assistant",
                "content": """- **`include`**: devuelve **todos** los campos escalares del modelo **más** las relaciones que indiques.
- **`select`**: devuelve **solo** los campos que indiques, y dentro puedes seleccionar relaciones con sus propios campos.
- No se pueden combinar en el mismo nivel: o `select` o `include`.

Tu fuga viene de devolver el resultado sin ninguno de los dos (o con `include`): todos los escalares salen, `passwordHash` incluido. Dos capas de defensa:

**1. Excluir el campo sensible por defecto, en el cliente.** Desde Prisma 6.2, `omit` es estable y puede configurarse globalmente:

```ts
// src/db.ts
import { PrismaClient } from "@prisma/client";

export const prisma = new PrismaClient({
  omit: { user: { passwordHash: true } }, // no sale en ninguna consulta salvo que se pida
});
```

El único sitio que lo necesita, el login, lo pide explícitamente:

```ts
const user = await prisma.user.findUnique({
  where: { email },
  omit: { passwordHash: false },
});
```

**2. En los endpoints, `select` explícito**, para devolver exactamente el contrato de la API y nada más:

```ts
// src/users/queries.ts
import { Prisma } from "@prisma/client";
import { prisma } from "../db";

export const publicUserSelect = {
  id: true,
  name: true,
  email: true,
  createdAt: true,
  _count: { select: { orders: true } },
} satisfies Prisma.UserSelect;

export async function listUsers() {
  return prisma.user.findMany({
    select: publicUserSelect,
    orderBy: { createdAt: "desc" },
    take: 50,
  });
}
```

Por qué las dos capas:

- **`omit` global** protege de olvidos futuros: un endpoint nuevo escrito con prisas ya no puede filtrar el hash.
- **`select` explícito** hace que añadir una columna a la tabla (un `internalNotes`, un `stripeCustomerId`) no la publique automáticamente en la API. Con `include` o sin nada, cada columna nueva sale sin que nadie lo decida.
- **`satisfies Prisma.UserSelect`** valida el objeto contra los campos reales del modelo sin perder su tipo literal, que es lo que Prisma necesita para inferir el resultado.
- **`_count`** cuenta relaciones en la misma consulta, sin traer los pedidos.

Comprobación: un test que llame a `listUsers()` y verifique que ningún elemento tiene la clave `passwordHash` (`expect(users[0]).not.toHaveProperty("passwordHash")`). Y revisa el resto de endpoints buscando `findMany(` y `findUnique(` sin `select`.""",
            },
            {
                "role": "user",
                "content": "¿Y cómo tipo lo que devuelve para pasarlo a un componente de React sin duplicar la interfaz a mano?",
            },
            {
                "role": "assistant",
                "content": """Derivándolo del mismo objeto `select`, así el tipo no puede desincronizarse de la consulta:

```ts
// src/users/queries.ts
import { Prisma } from "@prisma/client";

export type PublicUser = Prisma.UserGetPayload<{ select: typeof publicUserSelect }>;
// { id: string; name: string | null; email: string; createdAt: Date; _count: { orders: number } }
```

Si mañana añades `avatarUrl: true` al `select`, `PublicUser` lo incluye solo; si lo quitas, el compilador marca cada componente que lo usaba. Una interfaz escrita a mano te dejaría compilar y fallar en ejecución.

Alternativa equivalente cuando el tipo es «lo que devuelve esta función»:

```ts
export type PublicUser = Awaited<ReturnType<typeof listUsers>>[number];
```

Uso en el componente:

```tsx
import type { PublicUser } from "@/users/queries";

export function UserRow({ user }: { user: PublicUser }) {
  return (
    <tr>
      <td>{user.name ?? "Sin nombre"}</td>
      <td>{user.email}</td>
      <td>{user._count.orders}</td>
    </tr>
  );
}
```

Un detalle que suele romper este patrón: **las fechas**. Si el componente recibe los datos de un Server Component en Next.js, `Date` llega como `Date`. Si llegan por una API JSON, llegan como **cadenas**, y el tipo derivado de Prisma (que dice `Date`) miente. En ese caso define el tipo del contrato HTTP aparte, transformando lo necesario:

```ts
export type PublicUserDto = Omit<PublicUser, "createdAt"> & { createdAt: string };

export function toDto(user: PublicUser): PublicUserDto {
  return { ...user, createdAt: user.createdAt.toISOString() };
}
```

Regla: el tipo derivado de Prisma vale mientras los datos no crucen un `JSON.stringify`; en cuanto lo cruzan, el contrato es otro tipo con su propia conversión.

Comprobación: añade un campo al `select` y otro que no exista (`foo: true`). El primero debe aparecer en el autocompletado de `user.` en el componente; el segundo, dar error de compilación en el `satisfies`.""",
            },
        ]
    },
    # 4) Prisma: N+1 en un bucle con await (system revisor de rendimiento, error concreto)
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un revisor de rendimiento de bases de datos: cuantifica el problema antes de proponer el arreglo, y deja una forma de evitar que vuelva.",
            },
            {
                "role": "user",
                "content": """Este endpoint tarda 2 segundos con 100 pedidos. Activé el log de queries de Prisma y salen más de 200 SELECT:

```ts
const orders = await prisma.order.findMany({ where: { status: "PAID" }, take: 100 });
const result = [];
for (const order of orders) {
  const user = await prisma.user.findUnique({ where: { id: order.userId } });
  const items = await prisma.orderItem.findMany({ where: { orderId: order.id } });
  result.push({ ...order, userName: user?.name, items });
}
```""",
            },
            {
                "role": "assistant",
                "content": """**Cuantificación.** Es un N+1 doble: 1 consulta de pedidos + 100 de usuarios + 100 de líneas = **201 consultas**, y además **en serie**, porque cada `await` del bucle espera a la anterior. Con 5-10 ms de ida y vuelta por consulta, 201 × 5-10 ms = 1-2 s. Tu medición cuadra: el tiempo se va en viajes a la base, no en el trabajo de la base.

**Arreglo:** pedirlo todo en la consulta inicial, con relaciones anidadas en un `select`:

```ts
const orders = await prisma.order.findMany({
  where: { status: "PAID" },
  orderBy: { createdAt: "desc" },
  take: 100,
  select: {
    id: true,
    totalCents: true,
    createdAt: true,
    user: { select: { name: true } },
    items: { select: { productId: true, quantity: true, unitPriceCents: true } },
  },
});
```

Prisma resuelve esto con **3 consultas** fijas, sea cual sea el número de pedidos: una de pedidos, una de usuarios con `WHERE id IN (...)` y una de líneas con `WHERE order_id IN (...)`. Hay también una estrategia que lo hace en **una** sola consulta con JOIN (`relationLoadStrategy: "join"`, tras la preview feature `relationJoins`); de 3 a 1 rara vez se nota, de 201 a 3 siempre.

Dos ideas que parecen arreglos y no lo son:

- **`Promise.all` sobre el bucle**: sigue lanzando 201 consultas, ahora a la vez, y agota el pool de conexiones. Pasa de lento a fallar con `P2024` bajo carga. (Matiz: Prisma agrupa automáticamente las llamadas a `findUnique` que coinciden en el mismo tick, así que los usuarios sí se juntarían; las de `findMany` de las líneas, no.)
- **Cachear usuarios en un `Map` dentro del bucle**: reduce consultas solo si se repiten usuarios, y añade código que el `select` hace innecesario.

**Índices** para que esas 3 consultas sean rápidas: `orders (status, created_at)` para el filtro con orden, y `order_items (order_id)` para la carga de líneas. En el schema, `@@index([status, createdAt])` en `Order` y `@@index([orderId])` en `OrderItem`. Confirma con `EXPLAIN ANALYZE` que no hay `Seq Scan` sobre tablas grandes.

**Evitar que vuelva:** un test que cuente consultas. Prisma emite un evento por consulta:

```ts
import { PrismaClient } from "@prisma/client";
import { expect, test } from "vitest";
import { listPaidOrders } from "./orders";

test("listar pedidos pagados usa un número constante de consultas", async () => {
  const prisma = new PrismaClient({ log: [{ emit: "event", level: "query" }] });
  let queryCount = 0;
  prisma.$on("query", () => {
    queryCount += 1;
  });

  await listPaidOrders(prisma); // con la base de test sembrada con 50 pedidos

  expect(queryCount).toBeLessThanOrEqual(3);
  await prisma.$disconnect();
});
```

El test recibe el cliente por parámetro (`listPaidOrders(prisma)`), así que la función de producción debe aceptarlo en vez de importar un singleton. Con 50 pedidos sembrados, el código original daría 101 o más y el test fallaría; el arreglo da 3 con 50 o con 5.000.""",
            },
        ]
    },
    # 5) Prisma: transferencia en transacción interactiva y clave de idempotencia (SISTEMA, multiturno, avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito transferir saldo entre dos cuentas con Prisma: restar de una, sumar a otra y registrar el movimiento. ¿Cómo garantizo que no quede a medias y que el saldo no quede negativo si llegan dos transferencias a la vez?",
            },
            {
                "role": "assistant",
                "content": r"""Son dos garantías distintas y conviene separarlas:

1. **Atomicidad** (no quedar a medias): una transacción. Si algo falla dentro, se deshace todo.
2. **Saldo no negativo con concurrencia**: no basta con la transacción. El patrón ingenuo «leo el saldo, compruebo, resto» tiene una carrera: dos transferencias leen 100 a la vez, las dos ven que alcanza para 80 y las dos restan. La solución es que **comprobar y restar sean la misma sentencia**.

```ts
import { Prisma, PrismaClient } from "@prisma/client";

export const prisma = new PrismaClient();

export class InsufficientFundsError extends Error {
  constructor(readonly accountId: string) {
    super(`Saldo insuficiente en la cuenta ${accountId}`);
    this.name = "InsufficientFundsError";
  }
}

export async function transferWithin(
  tx: Prisma.TransactionClient,
  fromId: string,
  toId: string,
  amountCents: number,
) {
  if (!Number.isInteger(amountCents) || amountCents <= 0) {
    throw new RangeError("El importe debe ser un entero positivo en céntimos");
  }
  if (fromId === toId) throw new RangeError("Origen y destino no pueden coincidir");

  // Resta solo si hay saldo: comprobación y escritura en una única sentencia atómica.
  const debited = await tx.account.updateMany({
    where: { id: fromId, balanceCents: { gte: amountCents } },
    data: { balanceCents: { decrement: amountCents } },
  });
  if (debited.count === 0) throw new InsufficientFundsError(fromId);

  await tx.account.update({
    where: { id: toId },
    data: { balanceCents: { increment: amountCents } },
  });

  return tx.ledgerEntry.create({
    data: { fromAccountId: fromId, toAccountId: toId, amountCents },
  });
}

export function transfer(fromId: string, toId: string, amountCents: number) {
  return prisma.$transaction((tx) => transferWithin(tx, fromId, toId, amountCents), {
    timeout: 10_000, // por defecto son 5 s
  });
}
```

Por qué funciona:

- **`updateMany` con la condición en el `where`** genera `UPDATE accounts SET balance_cents = balance_cents - $1 WHERE id = $2 AND balance_cents >= $1`. El `UPDATE` bloquea la fila; una segunda transferencia concurrente espera a que la primera termine y, en Postgres con `READ COMMITTED`, vuelve a evaluar el `WHERE` contra el valor ya actualizado. Si no alcanza, actualiza 0 filas y lanzamos el error. Sin `SERIALIZABLE` y sin reintentos.
- **Lanzar una excepción dentro del callback hace rollback** de todo lo anterior: no queda un débito sin su crédito.
- **`transferWithin` recibe `tx`** para poder componerla con otras operaciones en la misma transacción (lo vas a necesitar enseguida).
- **Última línea de defensa en la base**: una restricción `CHECK (balance_cents >= 0)`, añadida en una migración con `--create-only`. Si algún día otro código resta sin la condición, la base lo rechaza.

Dos cosas que no deben ir dentro de la transacción: llamadas HTTP (una pasarela de pagos lenta mantendría las filas bloqueadas) y trabajo que no sea de base de datos.

Sobre interbloqueos: una transferencia A→B y otra B→A simultáneas bloquean las filas en orden inverso, y Postgres aborta una de ellas; Prisma lo reporta como `P2034`. Es raro y la operación es segura de repetir, así que reintenta una o dos veces ante ese código.

Comprobación con concurrencia real: cuenta con saldo 100, lanza cinco transferencias de 30 a la vez con `Promise.allSettled`. Exactamente tres deben cumplirse, dos fallar con `InsufficientFundsError`, el saldo final debe ser 10 y debe haber tres movimientos.""",
            },
            {
                "role": "user",
                "content": "Funciona. Pero la app móvil reintenta la petición si hay timeout, y hemos visto transferencias duplicadas cuando la primera sí llegó a ejecutarse. ¿Cómo lo evito?",
            },
            {
                "role": "assistant",
                "content": """Con una **clave de idempotencia**: el cliente genera un identificador único por operación (no por petición) y lo envía en cada reintento, por ejemplo en la cabecera `Idempotency-Key`. El servidor registra la clave **en la misma transacción** que la transferencia; si la clave ya existe, no repite la operación y devuelve el resultado original.

```prisma
model TransferRequest {
  idempotencyKey String   @id @map("idempotency_key") @db.Uuid
  requestHash    String   @map("request_hash")
  ledgerEntryId  String   @unique @map("ledger_entry_id") @db.Uuid
  createdAt      DateTime @default(now()) @map("created_at") @db.Timestamptz(3)

  @@map("transfer_requests")
}
```

```ts
import { createHash } from "node:crypto";
import { Prisma } from "@prisma/client";
import { prisma, transferWithin } from "./transfer";

export class IdempotencyKeyReusedError extends Error {
  constructor() {
    super("La clave de idempotencia ya se usó con otros datos");
    this.name = "IdempotencyKeyReusedError";
  }
}

function hashRequest(fromId: string, toId: string, amountCents: number): string {
  return createHash("sha256").update(`${fromId}|${toId}|${amountCents}`).digest("hex");
}

async function replay(key: string, requestHash: string) {
  const previous = await prisma.transferRequest.findUniqueOrThrow({ where: { idempotencyKey: key } });
  if (previous.requestHash !== requestHash) throw new IdempotencyKeyReusedError();
  return prisma.ledgerEntry.findUniqueOrThrow({ where: { id: previous.ledgerEntryId } });
}

export async function transferIdempotent(key: string, fromId: string, toId: string, amountCents: number) {
  const requestHash = hashRequest(fromId, toId, amountCents);

  const existing = await prisma.transferRequest.findUnique({ where: { idempotencyKey: key } });
  if (existing) return replay(key, requestHash);

  try {
    return await prisma.$transaction(async (tx) => {
      const entry = await transferWithin(tx, fromId, toId, amountCents);
      await tx.transferRequest.create({
        data: { idempotencyKey: key, requestHash, ledgerEntryId: entry.id },
      });
      return entry;
    });
  } catch (error) {
    // Dos reintentos simultáneos: el segundo choca con la clave primaria y se hace rollback
    // de SU transferencia. Devolvemos el resultado del que ganó.
    if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === "P2002") {
      return replay(key, requestHash);
    }
    throw error;
  }
}
```

Por qué cada pieza:

- **La clave se inserta dentro de la transacción de la transferencia.** O se registran las dos cosas o ninguna. Si la guardaras antes, en otra transacción, un fallo entre ambas dejaría la clave «usada» sin transferencia.
- **La clave primaria resuelve la carrera.** La consulta previa (`findUnique`) es solo un atajo para el caso común; la garantía real es que dos inserciones de la misma clave no pueden confirmarse ambas.
- **`requestHash`**: si el cliente reutiliza por error la clave con otro importe, respondes con un error (HTTP 422) en lugar de devolver silenciosamente la transferencia anterior.
- **El cliente genera la clave una vez por intención del usuario** (al pulsar «Transferir») y la conserva entre reintentos. Si la genera en cada petición, no sirve de nada.

Operativa: borra las claves con más de 24-48 h con un job periódico; ningún reintento razonable llega más tarde.

Comprobación: llama dos veces seguidas a `transferIdempotent` con la misma clave y los mismos datos: debe haber un solo movimiento y las dos llamadas deben devolver el mismo `id`. Lánzalas a la vez con `Promise.all`: mismo resultado. Repite con la misma clave y otro importe: `IdempotencyKeyReusedError`.""",
            },
        ]
    },
    # 6) Prisma: P2002 por carrera entre comprobar y crear (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Al registrar usuarios a veces sale esto en producción, aunque antes comprobamos con `findUnique` que el email no existe:

```
PrismaClientKnownRequestError:
Invalid `prisma.user.create()` invocation:
Unique constraint failed on the fields: (`email`)
code: 'P2002'
```

¿Cómo puede pasar si lo comprobamos justo antes?""",
            },
            {
                "role": "assistant",
                "content": """Porque entre la comprobación y la inserción hay una ventana, y dos peticiones pueden colarse a la vez por ella. Es una carrera clásica de «comprobar y luego actuar»:

```
petición A: findUnique(email) → no existe
petición B: findUnique(email) → no existe
petición A: create(email)     → OK
petición B: create(email)     → P2002
```

Basta un doble clic en «Registrarme» o un reintento automático del cliente. La base de datos hizo exactamente su trabajo: el índice único es la única garantía real. **La comprobación previa no aporta corrección**; como mucho, un mensaje amable en el caso no concurrente.

El arreglo es dejar que la base decida y traducir su respuesta:

```ts
import { Prisma } from "@prisma/client";
import { prisma } from "./db";

export class EmailAlreadyRegisteredError extends Error {
  constructor(readonly email: string) {
    super(`El email ${email} ya está registrado`);
    this.name = "EmailAlreadyRegisteredError";
  }
}

function isUniqueViolationOn(error: unknown, field: string): boolean {
  if (!(error instanceof Prisma.PrismaClientKnownRequestError) || error.code !== "P2002") return false;
  const target = error.meta?.target; // lista de campos o nombre del índice, según el conector
  if (Array.isArray(target)) return target.includes(field);
  return typeof target === "string" && target.includes(field);
}

export async function registerUser(rawEmail: string, passwordHash: string) {
  const email = rawEmail.trim().toLowerCase();
  try {
    return await prisma.user.create({
      data: { email, passwordHash },
      select: { id: true, email: true },
    });
  } catch (error) {
    if (isUniqueViolationOn(error, "email")) throw new EmailAlreadyRegisteredError(email);
    throw error;
  }
}
```

Detalles que importan:

- **Normalizar el email antes de guardar.** `Ana@Correo.com` y `ana@correo.com` pasan el índice único como distintos y te dejan dos cuentas para la misma persona. Alternativa en Postgres: columna `citext`.
- **Comprobar el campo en `meta.target`**: si la tabla tiene varios índices únicos (email y username), el mismo código `P2002` puede venir de cualquiera, y cada uno merece su mensaje.
- **Relanzar todo lo demás.** Un `catch` que convierte cualquier error en «email repetido» esconde caídas de la base.

Si el caso de uso es «obtener o crear» y no «registrar», usa `upsert`. Prisma lo traduce a un `INSERT ... ON CONFLICT` nativo cuando la consulta es simple (un único campo único en el `where`, sin escrituras anidadas); si no cumple esas condiciones lo hace en dos pasos y puede volver a dar `P2002`, así que en ese caso reintenta una vez.

En la capa HTTP, `EmailAlreadyRegisteredError` suele mapearse a 409. Si la enumeración de cuentas es un riesgo para tu producto (saber si alguien está registrado), responde lo mismo en ambos casos («te enviamos un correo para continuar») y avisa por email al titular existente.

Comprobación: un test que llame dos veces a la vez a `registerUser` con el mismo email usando `Promise.allSettled`. Una debe cumplirse y la otra rechazarse con `EmailAlreadyRegisteredError`, nunca con el `PrismaClientKnownRequestError` crudo.""",
            },
        ]
    },
    # 7) Prisma en serverless: demasiadas conexiones y P2024 (pooling, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": "Desplegamos una API con Next.js y Prisma en Vercel. Con tráfico moderado empiezan a fallar peticiones con `FATAL: sorry, too many clients already` y a veces con `P2024: Timed out fetching a new connection from the connection pool`. En local nunca pasa. El Postgres gestionado admite 100 conexiones.",
            },
            {
                "role": "assistant",
                "content": """Es aritmética de conexiones. En local tienes un proceso con un pool. En serverless tienes **muchas instancias**, cada una con su propio `PrismaClient` y su propio pool:

- El pool de Prisma por defecto abre hasta `núcleos × 2 + 1` conexiones; en una función típica, unas 5.
- Con 30 instancias activas en un pico: 30 × 5 = **150 conexiones** contra un límite de 100. Postgres rechaza las que sobran: `too many clients already`.
- `P2024` es el síntoma dentro de una instancia: más consultas simultáneas que conexiones en su pool, y alguna espera más de `pool_timeout` (10 s por defecto).

El arreglo tiene tres capas, en este orden.

**1. Un solo `PrismaClient` por instancia.** En el ámbito del módulo, nunca dentro del handler. En desarrollo, además, el hot reload de Next.js re-evalúa los módulos y crearía un cliente nuevo en cada guardado; se guarda en `globalThis`:

```ts
// src/db.ts
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
```

**2. Un pooler externo delante de Postgres**, que es la pieza que de verdad resuelve el problema. PgBouncer en modo *transaction* (o el pooler que ofrezca tu proveedor: Supabase, Neon y la mayoría lo incluyen) acepta miles de conexiones de clientes y las multiplexa sobre unas pocas conexiones reales. Prisma necesita dos URLs:

```prisma
datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL") // a través del pooler, para la aplicación
  directUrl = env("DIRECT_URL")   // conexión directa, solo para migraciones
}
```

```bash
# .env (valores de ejemplo)
DATABASE_URL="postgresql://app:secret@pooler.example.com:6543/shop?pgbouncer=true&connection_limit=1"
DIRECT_URL="postgresql://app:secret@db.example.com:5432/shop"
```

- **`pgbouncer=true`** desactiva las sentencias preparadas con nombre, que el modo *transaction* de PgBouncer no soporta en versiones antiguas o sin configurar para ello.
- **`directUrl`**: `prisma migrate` necesita una conexión de sesión real (bloqueos de migración, varias sentencias), así que no pasa por el pooler.

**3. Un pool pequeño por instancia.** `connection_limit=1` es el punto de partida que recomienda Prisma para serverless: cada instancia atiende pocas peticiones a la vez y el pooler ya reparte. Si tu plataforma atiende varias peticiones concurrentes por instancia (el modo *Fluid* de Vercel lo hace), un límite de 1 provoca precisamente `P2024`: súbelo a 3-5 y vigila el total.

Alternativas según el caso: Prisma Accelerate (pooler gestionado por Prisma) o los *driver adapters* (`@prisma/adapter-pg`, `@prisma/adapter-neon`) si ejecutas en edge.

Comprobación: durante una prueba de carga (k6 o autocannon contra la API desplegada), consulta en la base:

```sql
SELECT application_name, state, count(*)
FROM pg_stat_activity
GROUP BY application_name, state
ORDER BY count(*) DESC;
```

Sin pooler verás que las conexiones crecen con las instancias hasta el límite. Con pooler deben estabilizarse en el tamaño del pool del pooler, independientemente del tráfico.""",
            },
        ]
    },
    # 8) Prisma: paginación keyset para un feed infinito (inglés, intermedio-avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "We're building an infinite-scroll feed API with Prisma. Offset pagination (`skip`) gets slow on deep pages, and users see duplicates when new posts arrive while they scroll. What's the right way to do it?",
            },
            {
                "role": "assistant",
                "content": r"""Keyset (cursor) pagination. Both of your symptoms come from `OFFSET`:

- **Slow deep pages**: `OFFSET 10000 LIMIT 20` makes the database produce and discard 10,000 rows before returning 20. Cost grows linearly with depth.
- **Duplicates**: offsets count rows from the top. When a new post is inserted at the top, every row shifts down by one, so the first item of page 2 is the last item of page 1 again.

Keyset pagination says "give me 20 rows **after this one**", using the sort key itself. The database seeks straight to that point in an index, and inserts at the top cannot shift what comes after the cursor.

```ts
// src/feed/getFeedPage.ts
import { prisma } from "../db";

const PAGE_SIZE = 20;

type Cursor = { createdAt: string; id: string };

export type FeedPage = {
  items: { id: string; title: string; createdAt: Date; author: { name: string | null } }[];
  nextCursor: string | null;
};

export class InvalidCursorError extends Error {}

function encodeCursor(cursor: Cursor): string {
  return Buffer.from(JSON.stringify(cursor)).toString("base64url");
}

function decodeCursor(raw: string): Cursor {
  try {
    const parsed: unknown = JSON.parse(Buffer.from(raw, "base64url").toString("utf8"));
    if (
      typeof parsed === "object" && parsed !== null &&
      typeof (parsed as Cursor).createdAt === "string" && typeof (parsed as Cursor).id === "string"
    ) {
      return parsed as Cursor;
    }
  } catch {
    // fall through to the error below: a malformed cursor is a client error, not a server one
  }
  throw new InvalidCursorError("Malformed cursor");
}

export async function getFeedPage(rawCursor: string | null): Promise<FeedPage> {
  const cursor = rawCursor ? decodeCursor(rawCursor) : null;
  const after = cursor ? new Date(cursor.createdAt) : null;

  const rows = await prisma.post.findMany({
    where: after
      ? {
          OR: [
            { createdAt: { lt: after } },
            { createdAt: after, id: { lt: cursor!.id } }, // tie-breaker for equal timestamps
          ],
        }
      : undefined,
    orderBy: [{ createdAt: "desc" }, { id: "desc" }],
    take: PAGE_SIZE + 1, // one extra row tells us whether another page exists
    select: { id: true, title: true, createdAt: true, author: { select: { name: true } } },
  });

  const hasMore = rows.length > PAGE_SIZE;
  const items = hasMore ? rows.slice(0, PAGE_SIZE) : rows;
  const last = items.at(-1);

  return {
    items,
    nextCursor: hasMore && last ? encodeCursor({ createdAt: last.createdAt.toISOString(), id: last.id }) : null,
  };
}
```

And the index that makes each page a single index seek:

```prisma
model Post {
  id        String   @id @default(uuid()) @db.Uuid
  title     String
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz(3)
  authorId  String   @map("author_id") @db.Uuid
  author    User     @relation(fields: [authorId], references: [id])

  @@index([createdAt(sort: Desc), id(sort: Desc)])
  @@map("posts")
}
```

Design decisions:

- **A tie-breaker in the sort.** `createdAt` alone is not unique; two posts in the same millisecond would be skipped or repeated at a page boundary. `(createdAt, id)` is a total order.
- **Manual keyset instead of Prisma's built-in `cursor` option.** `cursor: { id }` works, but it locates the cursor row by id first; if that post was deleted between requests, the next page comes back empty. Carrying the sort values in the cursor makes it independent of the row still existing.
- **Opaque base64url cursor.** Clients treat it as a token, so you can change its contents later without breaking them. Map `InvalidCursorError` to HTTP 400.
- **`take: PAGE_SIZE + 1`** answers "is there a next page?" without a `COUNT(*)`, which on a large table is often slower than the page itself.

What you give up: jumping to page 37 and showing "page X of Y". An infinite feed needs neither.

Verification: fetch page 1, insert three new posts, fetch page 2 with the cursor: no item from page 1 may repeat. Then run `EXPLAIN ANALYZE` on the generated query for a deep cursor; it should show an index scan on the `(created_at, id)` index with roughly the same cost as page 1.""",
            },
        ]
    },
    # 9) Prisma: soft delete con client extensions y unicidad del email (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Queremos soft delete en Prisma: un campo `deletedAt` y que todas las consultas ignoren los registros borrados sin tener que acordarnos de añadir el filtro en cada sitio. ¿Cómo se hace?",
            },
            {
                "role": "assistant",
                "content": """Con una *client extension* que intercepte las lecturas del modelo y añada `deletedAt: null`, más un método explícito para borrar. Te lo doy completo y, sobre todo, con sus límites, porque el soft delete automático tiene agujeros que conviene conocer antes de confiar en él.

```prisma
model User {
  id        String    @id @default(uuid()) @db.Uuid
  email     String    @unique
  name      String?
  deletedAt DateTime? @map("deleted_at") @db.Timestamptz(3)
  posts     Post[]

  @@map("users")
}
```

```ts
// src/db.ts
import { Prisma, PrismaClient } from "@prisma/client";

const notDeleted = { deletedAt: null };

export const prisma = new PrismaClient().$extends({
  name: "soft-delete-users",
  query: {
    user: {
      async findMany({ args, query }) {
        args.where = { ...args.where, ...notDeleted };
        return query(args);
      },
      async findFirst({ args, query }) {
        args.where = { ...args.where, ...notDeleted };
        return query(args);
      },
      async findUnique({ args, query }) {
        // Desde Prisma 5, findUnique admite filtros no únicos junto al campo único.
        args.where = { ...args.where, ...notDeleted };
        return query(args);
      },
      async count({ args, query }) {
        args.where = { ...args.where, ...notDeleted };
        return query(args);
      },
      async delete() {
        throw new Error("Borrado físico deshabilitado: usa prisma.user.softDelete(id)");
      },
    },
  },
  model: {
    user: {
      async softDelete(id: string) {
        const context = Prisma.getExtensionContext(this);
        return context.update({ where: { id }, data: { deletedAt: new Date() } });
      },
    },
  },
});
```

Uso: `await prisma.user.findMany()` ya no devuelve borrados, y `await prisma.user.softDelete(id)` borra. Toda la aplicación debe importar este `prisma` extendido; el cliente base no se exporta.

**Los agujeros, para que no te sorprendan:**

- **Las relaciones anidadas no pasan por la extensión.** `prisma.post.findMany({ include: { author: true } })` devuelve el autor aunque esté borrado, y `prisma.user.findMany({ include: { posts: true } })` no filtra los posts borrados. En esas lecturas, el filtro va explícito: `include: { posts: { where: { deletedAt: null } } }`.
- **`update` y `updateMany` siguen afectando a registros borrados.** Si eso importa (que nadie edite un usuario borrado), añádelos a la extensión igual que las lecturas.
- **`$queryRaw` ignora la extensión**: el SQL a mano lleva su propio `WHERE deleted_at IS NULL`.
- **Los informes que sí deben ver los borrados** (auditoría, soporte) necesitan otra puerta: un segundo cliente sin la extensión, de uso restringido.

Si necesitas una garantía más fuerte que «el código no se olvidó», el filtro va en la base: una vista `active_users` o políticas de *row level security* en Postgres.

Comprobación: un test que cree dos usuarios, borre uno con `softDelete` y verifique que `findMany`, `findUnique` por id y `count` ven solo uno, y que `prisma.user.delete(...)` lanza el error.""",
            },
            {
                "role": "user",
                "content": "Problema: si alguien borra su cuenta y luego se vuelve a registrar con el mismo email, falla por el `@unique`. ¿Qué hacemos?",
            },
            {
                "role": "assistant",
                "content": """El `@unique` crea un índice único sobre **todas** las filas, borradas incluidas. Hay dos soluciones; la segunda suele ser mejor con Prisma.

**Opción A: índice único parcial**, que solo aplica a las filas activas:

```sql
CREATE UNIQUE INDEX users_email_active_key ON users (email) WHERE deleted_at IS NULL;
```

El schema de Prisma no expresa índices parciales, así que el proceso es:

1. Quita `@unique` de `email` en el schema.
2. `prisma migrate dev --create-only --name partial_unique_email`.
3. Edita el SQL generado: deja el `DROP INDEX` del índice antiguo y añade el `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL`.
4. Aplica con `prisma migrate dev`.

El coste: Prisma no conoce ese índice. `findUnique({ where: { email } })` deja de compilar (para Prisma, `email` ya no es único) y pasa a ser `findFirst`. Y en migraciones futuras Prisma puede proponer borrarlo; revisa cada migración nueva y, si aparece un `DROP INDEX "users_email_active_key"`, elimínalo antes de aplicarla. Es una fricción permanente.

**Opción B: liberar el email al borrar.** El soft delete reescribe el email a un valor que no puede colisionar, y conserva el original en otra columna si lo necesitas para auditoría:

```ts
// dentro de la extensión, sustituyendo el softDelete anterior
model: {
  user: {
    async softDelete(id: string) {
      const context = Prisma.getExtensionContext(this);
      const user = await context.findUniqueOrThrow({ where: { id }, select: { email: true } });
      return context.update({
        where: { id },
        data: {
          deletedAt: new Date(),
          deletedEmail: user.email,                 // columna nueva, nullable
          email: `deleted+${id}@invalid.example`,   // único por id, nunca colisiona
        },
      });
    },
  },
},
```

`@unique` se queda como está, `findUnique` por email sigue funcionando y no hay SQL fuera del schema. Además encaja con la protección de datos: si la normativa te obliga a olvidar el email, basta con poner `deletedEmail` a `null` pasado el plazo.

Mi recomendación: **B**, salvo que necesites «restaurar cuenta» con el mismo email de forma automática, que es lo único que A hace más fácil.

Comprobación: registra un email, borra la cuenta, regístrala de nuevo con el mismo email: debe crearse un usuario nuevo con otro id, y en la tabla debe quedar el antiguo con `deleted_at` y `deleted_email` rellenos.""",
            },
        ]
    },
    # 10) Drizzle: schema en TypeScript, cliente y drizzle-kit generate/migrate/push (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Vamos a usar Drizzle con Postgres en un proyecto Node/TypeScript nuevo. ¿Cómo organizo el schema, la conexión y las migraciones? Vi `drizzle-kit push` y `drizzle-kit generate` y no sé cuál usar.",
            },
            {
                "role": "assistant",
                "content": """Estructura mínima: el schema en TypeScript, un cliente compartido y una configuración para `drizzle-kit`, que es la herramienta de migraciones.

```
src/db/
  schema.ts      ← tablas y relaciones
  client.ts      ← pool y cliente de Drizzle
  migrate.ts     ← aplica migraciones en el despliegue
drizzle/         ← SQL de migraciones generado (va al repositorio)
drizzle.config.ts
```

```ts
// src/db/schema.ts
import { relations } from "drizzle-orm";
import { index, pgTable, text, timestamp, uuid } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  name: text("name"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const posts = pgTable(
  "posts",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    authorId: uuid("author_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    title: text("title").notNull(),
    publishedAt: timestamp("published_at", { withTimezone: true }),
  },
  (table) => [index("posts_author_id_idx").on(table.authorId)],
);

// Relaciones para las consultas relacionales (db.query); no crean nada en la base.
export const usersRelations = relations(users, ({ many }) => ({
  posts: many(posts),
}));

export const postsRelations = relations(posts, ({ one }) => ({
  author: one(users, { fields: [posts.authorId], references: [users.id] }),
}));
```

```ts
// src/db/client.ts
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

export const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 10 });
export const db = drizzle({ client: pool, schema });
```

```ts
// drizzle.config.ts
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dbCredentials: { url: process.env.DATABASE_URL! },
});
```

```ts
// src/db/migrate.ts (se ejecuta en el despliegue, antes de arrancar la app; requiere ESM)
import { migrate } from "drizzle-orm/node-postgres/migrator";
import { db, pool } from "./client";

await migrate(db, { migrationsFolder: "./drizzle" });
await pool.end();
```

**Los comandos de drizzle-kit:**

| Comando | Qué hace | Cuándo |
|---|---|---|
| `drizzle-kit generate` | compara el schema con el último snapshot y escribe un archivo SQL nuevo en `drizzle/` | cada cambio de esquema que vaya a otros entornos |
| `drizzle-kit migrate` | aplica los SQL pendientes y los registra en una tabla de control | CI y despliegue (o `migrate.ts`) |
| `drizzle-kit push` | aplica el schema directamente a la base, sin archivos de migración | prototipos y tu base local desechable |
| `drizzle-kit pull` | genera el schema TypeScript a partir de una base existente | adoptar Drizzle sobre una base que ya existe |
| `drizzle-kit studio` | interfaz web para ver y editar datos | depurar en local |

La respuesta a tu duda: **`generate` + `migrate` para todo lo que sea compartido**, porque deja un historial revisable y reproducible. `push` está bien mientras iteras solo en tu máquina; usarlo contra staging o producción es cambiar esquemas sin rastro.

Decisiones del código:

- **`relations()` no son claves foráneas.** La FK la crea `.references()`; `relations()` solo informa a la API de consultas relacionales. Hacen falta las dos.
- **El `schema` se pasa a `drizzle()`.** Sin él, `db.query.users` no existe; el constructor de consultas (`db.select()`) sí funciona, y por eso el olvido pasa desapercibido hasta que alguien usa `db.query`.
- **Índice explícito en `author_id`**, por lo mismo de siempre en Postgres: las FK no se indexan solas.
- **Las relaciones usan la API de `drizzle-orm` 0.x** (`relations`). La rama 1.0 introduce una API nueva (`defineRelations`); si empiezas con ella, la idea es la misma con otra forma.

Comprobación: `npx drizzle-kit generate` debe crear `drizzle/0000_*.sql` con las dos tablas, la FK con `ON DELETE cascade` y el índice. Revísalo, aplícalo con `npx drizzle-kit migrate` sobre una base vacía y vuelve a ejecutar `generate`: debe decir que no hay cambios.""",
            },
        ]
    },
    # 11) Drizzle: query builder frente a relational queries (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "En Drizzle veo dos estilos: `db.select().from(...)` y `db.query.users.findMany({ with: ... })`. ¿Cuándo uso cada uno? En el equipo hay quien usa solo uno de los dos para todo.",
            },
            {
                "role": "assistant",
                "content": """Resuelven problemas distintos, y usar solo uno obliga a forzarlo donde no encaja.

- **Relational queries (`db.query`)**: para leer **un grafo de objetos anidado** (un usuario con sus publicaciones, un pedido con sus líneas). Devuelven objetos anidados ya montados y Drizzle lo resuelve en una sola consulta SQL. Son solo de lectura.
- **Query builder (`db.select()`, `insert`, `update`, `delete`)**: SQL con tipos. Joins, agregados, `GROUP BY`, subconsultas, columnas calculadas y todas las escrituras. Devuelve filas planas.

El mismo esquema, un caso de cada tipo (asumo el schema de `users` y `posts` con sus `relations` y el cliente creado con `drizzle({ client: pool, schema })`):

```ts
import { and, count, desc, eq, gte, isNotNull } from "drizzle-orm";
import { db } from "./db/client";
import { posts, users } from "./db/schema";

// 1) Grafo anidado: perfil de autor con sus 5 últimas publicaciones.
export async function getAuthorProfile(userId: string) {
  return db.query.users.findFirst({
    where: eq(users.id, userId),
    columns: { id: true, name: true },
    with: {
      posts: {
        where: isNotNull(posts.publishedAt),
        orderBy: [desc(posts.publishedAt)],
        limit: 5,
        columns: { id: true, title: true, publishedAt: true },
      },
    },
  });
}
// Tipo inferido: { id: string; name: string | null; posts: { id: string; title: string; publishedAt: Date | null }[] } | undefined

// 2) Agregado plano: los 10 autores con más publicaciones desde una fecha.
export async function getTopAuthors(since: Date) {
  return db
    .select({ authorId: users.id, name: users.name, postCount: count(posts.id) })
    .from(users)
    .innerJoin(posts, eq(posts.authorId, users.id))
    .where(and(isNotNull(posts.publishedAt), gte(posts.publishedAt, since)))
    .groupBy(users.id, users.name)
    .orderBy(desc(count(posts.id)))
    .limit(10);
}
```

Por qué no hacer el caso 1 con el query builder: un `leftJoin` de usuarios con publicaciones devuelve **una fila por publicación**, con los datos del usuario repetidos, y te toca agruparlas a mano en un `Map`. Además, «las 5 últimas por usuario» no se expresa con un `LIMIT` normal sobre un join. `db.query` hace ese trabajo por ti.

Por qué no hacer el caso 2 con `db.query`: no tiene `GROUP BY` ni agregados sobre relaciones; tendrías que traer todas las publicaciones y contarlas en JavaScript.

Criterio para el equipo:

| Necesito... | Uso |
|---|---|
| una entidad con sus hijos, para una pantalla o una respuesta de API | `db.query` |
| listas filtradas por columnas de varias tablas, informes, conteos | `db.select()` |
| insertar, actualizar o borrar | `db.insert` / `db.update` / `db.delete` |
| algo que no se expresa bien con ninguno (funciones de ventana, CTE recursivas) | `sql` a mano |

Un aviso de rendimiento con `db.query`: anidar colecciones grandes (un usuario con 10.000 publicaciones) sin `limit` monta un JSON enorme en una sola consulta. Pon siempre `limit` en las relaciones de tipo `many` que puedan crecer.

Comprobación: activa el log del cliente (`drizzle({ client: pool, schema, logger: true })`) y ejecuta las dos funciones. Cada una debe emitir exactamente **una** consulta SQL; la primera con la relación resuelta dentro de la propia consulta, la segunda con su `GROUP BY`.""",
            },
        ]
    },
    # 12) Drizzle frente a Prisma para un proyecto nuevo y migrar uno existente (España, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Vamos a empezar un backend nuevo en TypeScript con Postgres y una parte va a correr en Cloudflare Workers. ¿Drizzle o Prisma? El equipo sabe SQL más o menos bien.",
            },
            {
                "role": "assistant",
                "content": """Para ese contexto, **Drizzle**. Las dos condiciones que das (despliegue en Workers y un equipo que sabe SQL) son justo donde Drizzle saca ventaja. Prisma sería mi elección con otro perfil.

| Aspecto | Prisma 6 | Drizzle |
|---|---|---|
| Definición del esquema | DSL propio (`schema.prisma`) | TypeScript (`pgTable(...)`) |
| Estilo de consultas | API de alto nivel (`findMany`, `include`, escrituras anidadas) | SQL con tipos, más una API relacional para lecturas anidadas |
| Generación de código | sí: `prisma generate` tras cada cambio | no: los tipos salen del propio schema |
| Peso en el bundle y arranque | mayor; en edge necesita *driver adapters* | muy ligero; pensado para serverless y edge |
| Migraciones | `prisma migrate`, muy pulido | `drizzle-kit`, más joven pero suficiente |
| SQL a mano | `$queryRaw` con plantillas | `sql` integrado en el propio constructor |
| Curva para quien no sabe SQL | suave | más empinada |
| Herramientas | Studio, Accelerate, ecosistema grande | Studio, comunidad más pequeña |

Por qué Drizzle **en tu caso**:

- **Workers**: cada milisegundo de arranque y cada kilobyte del bundle cuentan. Drizzle es una capa fina sobre el driver. Prisma ha mejorado mucho aquí (los *driver adapters* y el cliente sin motor en Rust de las versiones 6.x recientes), y la brecha es menor que hace dos años, pero sigue siendo más pesado.
- **Un equipo que sabe SQL** lee una consulta de Drizzle y sabe qué SQL va a salir. Con Prisma, las consultas complejas obligan a pensar «cómo lo traducirá» o a bajar a `$queryRaw`.
- **Sin paso de generación**, los tipos nunca están desfasados respecto al schema.

Cuándo elegiría Prisma: un equipo con menos SQL, un dominio con muchas escrituras anidadas (crear un pedido con sus líneas y su dirección en una llamada), y despliegue en un servidor Node normal donde el tamaño del cliente no importa.

La misma consulta en ambos, para que el equipo lo vea:

```ts
import { and, eq, exists, isNotNull } from "drizzle-orm";
import { db } from "./db/client";          // cliente de Drizzle
import { posts, users } from "./db/schema";
import { prisma } from "./prisma";          // cliente de Prisma, solo para comparar

// Prisma
const authors = await prisma.user.findMany({
  where: { posts: { some: { publishedAt: { not: null } } } },
  select: { id: true, name: true, posts: { select: { title: true }, take: 3 } },
});

// Drizzle (API relacional)
const authorsDrizzle = await db.query.users.findMany({
  columns: { id: true, name: true },
  with: { posts: { columns: { title: true }, limit: 3 } },
  where: exists(db.select().from(posts).where(and(eq(posts.authorId, users.id), isNotNull(posts.publishedAt)))),
});
```

Fíjate en el `where`: en Prisma, `some` es una abstracción; en Drizzle escribes el `EXISTS` que en realidad se ejecuta. Esa diferencia, multiplicada por cien consultas, es la decisión.

Comprobación antes de comprometeros: implementad los tres endpoints más complejos del producto con ambos en una tarde, desplegadlos en un Worker de prueba y comparad tamaño del bundle, tiempo de arranque en frío y lo legibles que le resultan al equipo.""",
            },
            {
                "role": "user",
                "content": "Va, Drizzle. Pero tenemos otro servicio con Prisma y su base ya en producción. Si lo pasamos también, ¿cómo lo hacemos sin romper nada?",
            },
            {
                "role": "assistant",
                "content": """Por fases, con una sola herramienta dueña del esquema en cada momento y sin tocar la base el día del cambio.

**Fase 1: generar el schema de Drizzle desde la base real.**

```bash
npx drizzle-kit pull
```

Introspecciona la base de producción (o una copia) y escribe el schema TypeScript con tablas, índices y relaciones. El SQL inicial que acompaña a `pull` describe una base que **ya existe**: es tu línea base y no debe ejecutarse contra producción; compruébalo antes de aplicar ninguna migración.

**Fase 2: revisar lo que Prisma hacía y la base no sabe.** Es el punto que más rompe estas migraciones:

- **`@default(uuid())` y `@default(cuid())` los genera Prisma Client, no Postgres.** La columna en la base no tiene `DEFAULT`. Si Drizzle inserta sin id, la inserción falla. Añádelo en el schema de Drizzle:

```ts
id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
```

- **`@updatedAt` también lo pone Prisma Client.** En Drizzle:

```ts
updatedAt: timestamp("updated_at", { precision: 3 }).notNull().defaultNow().$onUpdate(() => new Date()),
```

- **Las tablas implícitas de muchos a muchos** (`_CategoryToPost`, con columnas `A` y `B`) aparecerán tal cual. Funcionan, pero conviene darles nombres explícitos en Drizzle.
- **Modelos sin `@@map`** tienen tablas con mayúsculas (`"User"`); `pull` lo respeta, no lo «arregles» a mano o las consultas fallarán.

`@default(now())` sí es un `DEFAULT` real de la base y no requiere nada.

**Fase 3: migrar el código por módulos.** Ambos clientes pueden convivir contra la misma base. Mueve un módulo cada vez (usuarios, luego pedidos...) y mantén sus tests de integración contra una base real: deben pasar igual con el repositorio de Prisma y con el de Drizzle.

**Fase 4: cambiar de dueño del esquema.** Mientras dure la convivencia, las migraciones las sigue haciendo **solo** Prisma. Cuando ya no quede código con Prisma, la siguiente migración la genera `drizzle-kit generate`, y la carpeta `prisma/migrations` queda como histórico. Dos herramientas generando migraciones a la vez es la forma segura de corromper el esquema.

Comprobación del paso más delicado: en una copia de la base, inserta un registro de cada tabla **sin indicar id ni `updatedAt`** usando Drizzle. Si alguna falla, te falta un `$defaultFn` o un `$onUpdate`.""",
            },
        ]
    },
    # 13) Drizzle: webhooks idempotentes con onConflictDoNothing en la misma transacción (intermedio-avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Recibimos webhooks de la pasarela de pagos y a veces llega el mismo evento dos o tres veces (su documentación dice que la entrega es «al menos una vez»). Usamos Drizzle con Postgres. ¿Cómo hago que procesar un evento dos veces no duplique nada?",
            },
            {
                "role": "assistant",
                "content": """Registra cada evento procesado en una tabla cuya clave primaria es el id del evento, **en la misma transacción** que sus efectos. La clave primaria convierte «procesar» en una operación que solo puede confirmarse una vez.

```ts
// src/db/schema.ts (añadido)
import { pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const processedEvents = pgTable("processed_events", {
  eventId: text("event_id").primaryKey(),
  type: text("type").notNull(),
  processedAt: timestamp("processed_at", { withTimezone: true }).notNull().defaultNow(),
});
```

```ts
// src/payments/handle-payment-event.ts
import { and, eq, ne } from "drizzle-orm";
import { db } from "../db/client";
import { orders, processedEvents } from "../db/schema";

export type PaymentEvent = {
  id: string;
  type: "payment.succeeded" | "payment.failed";
  orderId: string;
};

export async function handlePaymentEvent(event: PaymentEvent): Promise<"processed" | "duplicate"> {
  return db.transaction(async (tx) => {
    // 1. Reclamar el evento. Si ya existe, no se inserta nada y returning() viene vacío.
    const claimed = await tx
      .insert(processedEvents)
      .values({ eventId: event.id, type: event.type })
      .onConflictDoNothing({ target: processedEvents.eventId })
      .returning({ eventId: processedEvents.eventId });

    if (claimed.length === 0) return "duplicate";

    // 2. Efectos. Nunca degradar un pedido ya pagado por un evento que llegue tarde.
    const nextStatus = event.type === "payment.succeeded" ? "paid" : "payment_failed";
    await tx
      .update(orders)
      .set({ status: nextStatus, updatedAt: new Date() })
      .where(and(eq(orders.id, event.orderId), ne(orders.status, "paid")));

    return "processed";
  });
}
```

```ts
// en el handler HTTP, después de verificar la firma del webhook
const outcome = await handlePaymentEvent(event);
return new Response(null, { status: 200 }); // también 200 para duplicados: el proveedor deja de reintentar
```

Por qué es correcto incluso con entregas simultáneas:

- **Dos entregas a la vez**: ambas intentan insertar el mismo `event_id`. Postgres hace que la segunda **espere** a que la primera transacción termine. Si la primera confirma, la segunda encuentra el conflicto, `ON CONFLICT DO NOTHING` no inserta y devuelve vacío: «duplicate». Si la primera falla y hace rollback, la segunda inserta y procesa. En ningún caso se procesa dos veces.
- **Si el procesamiento falla**, la excepción deshace también la inserción en `processed_events`; el handler devuelve 500, el proveedor reintenta y el evento se procesa en el siguiente intento. Registrar el evento en una transacción aparte, antes del procesamiento, rompería esto: quedaría marcado sin haberse aplicado.
- **Eventos fuera de orden**: «al menos una vez» suele venir con «en cualquier orden». La condición `ne(orders.status, "paid")` es una pequeña máquina de estados: un `payment.failed` antiguo que llega después del `succeeded` no puede deshacer el pago.

Lo que este patrón **no** cubre: efectos fuera de la base (enviar un email, llamar a otra API). Esos no participan en la transacción. Para ellos, guarda una fila en una tabla de salida (*outbox*) dentro de la misma transacción y que un proceso aparte los envíe, a su vez con su propia idempotencia.

Mantenimiento: borra filas de `processed_events` más antiguas que la ventana máxima de reintentos del proveedor (suele ser de unos días).

Comprobación: llama a `handlePaymentEvent` con el mismo evento dos veces en paralelo (`Promise.all`). Debe devolver un «processed» y un «duplicate», y `processed_events` debe tener una sola fila. Después envía un `payment.failed` con otro id para ese pedido ya pagado: el pedido debe seguir en `paid`.""",
            },
        ]
    },
    # 14) Drizzle: tipos inferidos y validación de entrada sin duplicar (system variante)
    {
        "messages": [
            {"role": "system", "content": "Responde con código completo y comentarios breves; nada de introducciones."},
            {
                "role": "user",
                "content": "En Drizzle, ¿cómo saco los tipos de las filas para usarlos en el resto del código, y cómo valido la entrada de la API sin duplicar la definición de la tabla?",
            },
            {
                "role": "assistant",
                "content": """```ts
// src/db/types.ts
import type { posts, users } from "./schema";

export type User = typeof users.$inferSelect;    // fila leída: todos los campos, con sus null
export type NewUser = typeof users.$inferInsert; // fila a insertar: id y createdAt opcionales (tienen default)
export type Post = typeof posts.$inferSelect;
export type NewPost = typeof posts.$inferInsert;
```

```ts
// src/users/create-user.ts
import { z } from "zod";
import { db } from "../db/client";
import { users } from "../db/schema";
import type { NewUser, User } from "../db/types";

// Contrato de la API: más estricto que la tabla (formato, longitudes, normalización).
export const createUserInput = z.object({
  email: z.string().trim().toLowerCase().email(),
  name: z.string().trim().min(1).max(100).optional(),
});

export type CreateUserInput = z.infer<typeof createUserInput>;

export class InsertReturnedNothingError extends Error {}

export async function createUser(rawInput: unknown): Promise<User> {
  const input = createUserInput.parse(rawInput); // ZodError con el detalle de cada campo si no cumple

  // Anotar como NewUser hace que una columna nueva obligatoria en la tabla rompa la compilación aquí.
  const row: NewUser = { email: input.email, name: input.name ?? null };

  const [created] = await db.insert(users).values(row).returning();
  if (!created) throw new InsertReturnedNothingError("INSERT ... RETURNING no devolvió filas");
  return created;
}
```

```ts
// src/users/user-dto.ts
import type { User } from "../db/types";

// Lo que sale por la API: explícito, para que una columna nueva no se publique sola.
export type UserDto = Pick<User, "id" | "email" | "name"> & { createdAt: string };

export function toUserDto(user: User): UserDto {
  return { id: user.id, email: user.email, name: user.name, createdAt: user.createdAt.toISOString() };
}
```

- **`$inferSelect` / `$inferInsert`** salen del propio schema: sin generación de código y nunca desfasados.
- **El tipo de la tabla no es el contrato de la API.** La entrada se valida con un schema propio, más estricto; la salida pasa por un DTO, para que columnas internas (hashes, notas) no se filtren.
- **`const row: NewUser`** es la costura que avisa al compilar si la tabla y la API divergen.
- **`drizzle-zod`** puede generar el schema de zod a partir de la tabla (`createInsertSchema`) si prefieres partir de ahí y refinar; con contratos pequeños, el schema a mano es más legible.
- Comprobación: `createUser({ email: "  ANA@Correo.com " })` guarda `ana@correo.com`; `createUser({ email: "x" })` lanza `ZodError` sin tocar la base; añadir `phone: text("phone").notNull()` a la tabla debe hacer fallar `tsc` en `create-user.ts`.""",
            },
        ]
    },
    # 15) Drizzle: db.query undefined por no pasar el schema (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Con Drizzle esto revienta:

```ts
const user = await db.query.users.findFirst({ where: eq(users.id, id), with: { posts: true } });
```

```
TypeError: Cannot read properties of undefined (reading 'findFirst')
```

Pero `db.select().from(users)` funciona perfecto. El cliente lo creo así: `export const db = drizzle({ client: pool });`""",
            },
            {
                "role": "assistant",
                "content": """Falta pasarle el schema al cliente. `db.query` se construye a partir del objeto `schema` que recibe `drizzle()`: por cada tabla que encuentra crea `db.query.<tabla>`. Sin schema, `db.query` está vacío, `db.query.users` es `undefined` y la llamada a `findFirst` revienta. El query builder no lo necesita porque recibe la tabla como argumento (`.from(users)`), por eso esa parte funciona.

```ts
// src/db/client.ts
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

export const pool = new Pool({ connectionString: process.env.DATABASE_URL });
export const db = drizzle({ client: pool, schema });
```

**El siguiente error que te vas a encontrar** si las relaciones no están en ese mismo objeto: `with: { posts: true }` necesita las definiciones de `relations()`, y si no las encuentra falla con `There is not enough information to infer relation "users.posts"`. Por eso `schema` tiene que incluir tablas **y** relaciones. Si las tienes repartidas en varios archivos, reúnelas en un índice:

```ts
// src/db/schema/index.ts
export * from "./users";
export * from "./posts";
export * from "./relations"; // usersRelations, postsRelations
```

y el `import * as schema from "./schema"` recoge todo.

**Por qué no te avisó TypeScript**: sí te avisaba. Con `drizzle({ client: pool })`, el tipo de `db.query` es un objeto vacío y `db.query.users` es un error de compilación. Si el código llegó a ejecutarse, seguramente lo arrancas con `tsx`, `ts-node --transpile-only` o un bundler basado en esbuild, que **eliminan los tipos sin comprobarlos**. Añade la comprobación al flujo:

```json
{
  "scripts": {
    "typecheck": "tsc --noEmit",
    "dev": "tsx watch src/server.ts"
  }
}
```

y ejecuta `npm run typecheck` en CI (y en un hook de pre-commit si queréis). Este fallo en concreto, y toda una familia de errores parecidos, habría aparecido en el editor y en CI antes de llegar a ejecutarse.

Comprobación: tras el cambio, `tsc --noEmit` no debe dar errores en esa línea, el autocompletado debe ofrecer `db.query.users` y `db.query.posts`, y la consulta debe devolver el usuario con su array `posts` (vacío si no tiene ninguno, nunca `undefined`).""",
            },
        ]
    },
    # 16) Drizzle: cuándo escribir SQL a mano con sql`` y funciones de ventana (inglés, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "With Drizzle, when is it OK to drop down to raw SQL, and how do I do it safely? Concrete case: I need the top 3 most viewed posts per author, and I can't express that with the query builder.",
            },
            {
                "role": "assistant",
                "content": r"""It is OK when the query is clearer in SQL than in the builder, which in practice means: window functions, recursive CTEs, `LATERAL` joins, bulk updates from a `VALUES` list, and reporting queries. "Top N per group" is the textbook case: it needs `row_number()` over a partition, which no ORM abstracts well.

Drizzle's `sql` template keeps it safe and typed enough:

```ts
// src/posts/top-posts-per-author.ts
import { sql } from "drizzle-orm";
import { db } from "../db/client";

export type TopPostRow = {
  author_id: string;
  post_id: string;
  title: string;
  views: number;
  rank: number;
};

export async function topPostsPerAuthor(limitPerAuthor: number): Promise<TopPostRow[]> {
  if (!Number.isInteger(limitPerAuthor) || limitPerAuthor < 1) {
    throw new RangeError("limitPerAuthor must be a positive integer");
  }

  const result = await db.execute<TopPostRow>(sql`
    SELECT author_id, post_id, title, views, rank
    FROM (
      SELECT
        p.author_id,
        p.id AS post_id,
        p.title,
        p.views,
        row_number() OVER (PARTITION BY p.author_id ORDER BY p.views DESC, p.id)::int AS rank
      FROM posts p
      WHERE p.published_at IS NOT NULL
    ) ranked
    WHERE rank <= ${limitPerAuthor}
    ORDER BY author_id, rank
  `);

  return result.rows;
}
```

What makes this safe and correct:

- **`${limitPerAuthor}` is a bind parameter, not string concatenation.** Drizzle sends `$1` and the value separately, so there is no SQL injection even if the value came from a request.
- **`::int` on `row_number()`.** It returns `bigint`, and node-postgres returns `bigint` as a **string** to avoid precision loss. Without the cast, `rank` would be `"1"` at runtime while your type says `number`. The generic on `db.execute<TopPostRow>` is a promise you make, not something Drizzle checks, so the cast and an integration test are what keep it honest.
- **`p.id` as a tie-breaker** in the window's `ORDER BY` makes the ranking deterministic when two posts have the same views.

**The dangerous one is `sql.raw()`**: it inserts text verbatim, with no parameter. Use it only for trusted identifiers you control. A typical case where people reach for it is a user-chosen sort column; whitelist instead:

```ts
import { asc, desc } from "drizzle-orm";
import { posts } from "../db/schema";

const sortableColumns = {
  views: posts.views,
  title: posts.title,
  publishedAt: posts.publishedAt,
} as const;

type SortKey = keyof typeof sortableColumns;

export function orderByFromQuery(sortKey: SortKey, direction: "asc" | "desc") {
  const column = sortableColumns[sortKey];
  return direction === "asc" ? asc(column) : desc(column);
}
```

Invalid input can only pick one of three columns; nothing from the request ever becomes SQL text.

Inside `sql` you can also interpolate schema objects (`${posts}`, `${posts.authorId}`) instead of hard-coding names, so a renamed column breaks at compile time. It reads worse in long queries; I use it for short fragments and plain SQL for whole reporting queries.

Rules I would put in the team's guidelines:

1. CRUD and normal lists go through the builder or `db.query`. Raw SQL needs a reason.
2. Raw SQL lives in a repository function with a typed return, never inline in a route handler.
3. Every raw query has an integration test against a real Postgres with seeded data; types cannot verify it.
4. Check `EXPLAIN ANALYZE` once: hand-written does not mean fast. This one wants an index on `posts (author_id, views DESC) WHERE published_at IS NOT NULL` for large tables.

Verification: seed two authors with five posts each and distinct view counts, call `topPostsPerAuthor(3)`, and assert six rows, three per author, ordered by views, with `typeof row.rank === "number"`.""",
            },
        ]
    },
    # 17) SQLAlchemy 2.x: modelos con Mapped y mapped_column al migrar desde 1.x (España)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo modelos de SQLAlchemy 1.4 con `declarative_base()` y `Column(Integer, primary_key=True)`. Vamos a pasar a 2.x. ¿Cómo quedan los modelos con `Mapped` y `mapped_column`, y qué gano aparte de seguir la moda?",
            },
            {
                "role": "assistant",
                "content": """Ganas algo concreto: **tipos que entienden mypy y pyright**. Con `Column(...)`, `cliente.email` es para el analizador un `Column[str]` o directamente `Any`; con `Mapped[str]` es un `str`. Los errores de tipo en el acceso a datos aparecen en el editor, no en producción. Además, la nulabilidad sale de la anotación y se repite menos código.

Antes (1.4):

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False)
    full_name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    orders = relationship("Order", back_populates="customer")
```

Después (2.x):

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list[Order]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")

    customer: Mapped[Customer] = relationship(back_populates="orders")
```

Las reglas que hay que interiorizar:

- **La anotación decide la nulabilidad.** `Mapped[str]` genera `NOT NULL`; `Mapped[str | None]`, columna nullable. Ya no escribes `nullable=` salvo para casos raros. Ojo al migrar: si una columna era `nullable=True` y la anotas como `Mapped[str]`, has cambiado el esquema.
- **El tipo Python decide el tipo SQL por defecto**: `int` → `Integer`, `str` → `String`, `datetime` → `DateTime`, `Decimal` → `Numeric`. `mapped_column(...)` solo hace falta para lo que la anotación no expresa: longitud, clave foránea, `unique`, valores por defecto, zona horaria.
- **`relationship()` sin el nombre de la clase en cadena**: el destino sale de `Mapped[list[Order]]` (colección) o `Mapped[Customer]` (uno). Con `from __future__ import annotations`, las referencias adelantadas como `Order` funcionan sin comillas.
- **`default` frente a `server_default`**: `default="pending"` lo pone Python al insertar con el ORM; `server_default=func.now()` va al DDL y lo aplica la base, también en inserciones hechas con SQL a mano o desde otro servicio. Para marcas de tiempo, `server_default`.
- **`DeclarativeBase`** sustituye a `declarative_base()`, y en ella puedes centralizar decisiones con `type_annotation_map` (por ejemplo, que todo `str` sea `String(255)` si usas MySQL, que exige longitud).

Plan de migración sin sustos: convierte los modelos de una tabla cada vez y, después de cada una, genera una migración con Alembic. **Debe salir vacía**: si Alembic detecta cambios, la conversión ha alterado el esquema (casi siempre, una nulabilidad o una longitud) y lo corriges antes de seguir.

Comprobación final: `alembic revision --autogenerate -m "check"` sin operaciones, y `mypy` (o pyright) sin errores con `reveal_type(customer.orders[0].total)` mostrando `Decimal`.""",
            },
        ]
    },
    # 18) SQLAlchemy: ciclo de vida de la Session, unit of work e identity map (SISTEMA, avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "No termino de entender la Session de SQLAlchemy: cuándo se escriben los cambios, por qué si hago `session.get(User, 1)` dos veces no hace dos consultas, y por qué después del commit acceder a un atributo hace otra consulta. ¿Y cómo debería gestionar su ciclo de vida en una app web?",
            },
            {
                "role": "assistant",
                "content": """Las tres preguntas son tres patrones que la `Session` implementa a la vez: **unit of work**, **identity map** y **expiración tras el commit**. Entendidos esos tres, el ciclo de vida correcto sale solo.

**1. Unit of work: cuándo se escriben los cambios.** La sesión no ejecuta un `UPDATE` cuando asignas un atributo: anota el objeto como modificado. Acumula objetos nuevos, modificados y borrados, y los envía todos en un **flush**, ordenados según las dependencias (primero el cliente, luego sus pedidos). El flush ocurre en el `commit`, al llamar a `flush()`, y automáticamente antes de cada consulta (*autoflush*), para que una consulta dentro de la transacción vea tus propios cambios.

**2. Identity map: por qué no hay segunda consulta.** Dentro de una sesión hay **un único objeto Python por fila** (por clave primaria). `session.get(User, 1)` mira primero en ese mapa; si el objeto ya está cargado, lo devuelve sin ir a la base. Por eso las dos llamadas devuelven literalmente el mismo objeto.

**3. Expiración tras el commit.** Al confirmar, la transacción termina y otras transacciones pueden cambiar las filas. Con `expire_on_commit=True` (el valor por defecto), la sesión marca todos sus objetos como caducados, y el siguiente acceso a un atributo recarga la fila. Así nunca lees datos que asumías vigentes y ya no lo son.

Todo junto, con `echo=True` para ver el SQL real:

```python
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Order, User

engine = create_engine("postgresql+psycopg://app:secret@localhost/shop", echo=True)
SessionLocal = sessionmaker(engine)

with SessionLocal() as session, session.begin():
    user = session.get(User, 1)       # SELECT ... WHERE users.id = 1
    same = session.get(User, 1)       # sin SQL: identity map
    assert user is same               # el mismo objeto Python

    user.name = "Ana"                 # sin SQL: solo queda marcado como modificado
    session.add(Order(customer_id=1, total=Decimal("9.90")))  # sin SQL: pendiente

    paid = session.scalars(select(Order).where(Order.customer_id == 1)).all()
    # Antes de este SELECT, el autoflush envía el UPDATE y el INSERT.
# Al salir de begin(): COMMIT (o ROLLBACK si hubo excepción). Al salir del with: close().

with SessionLocal() as session:
    user = session.get(User, 1)
    user.name = "Luis"
    session.commit()
    print(user.name)                  # SELECT de nuevo: los atributos caducaron con el commit
```

**Ciclo de vida en una aplicación web: una sesión por petición**, corta, y nunca compartida entre hilos (la `Session` no es segura para hilos). Con FastAPI:

```python
from typing import Annotated
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

app = FastAPI()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@app.post("/users/{user_id}/name")
def rename_user(user_id: int, name: str, session: SessionDep) -> dict[str, str]:
    with session.begin():             # una unidad de trabajo = una transacción
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        user.name = name
    return {"name": user.name}        # recarga tras el commit; la sesión sigue abierta, así que funciona
```

Errores de diseño que esto evita:

- **Sesión global o de larga vida**: el identity map se convierte en una caché que nunca se invalida (lees datos de hace horas) y crece con cada objeto modificado.
- **Una sesión por consulta**: pierdes la atomicidad (cada operación en su transacción) y el identity map deja de servir.
- **`expire_on_commit=False` por defecto**: útil cuando devuelves objetos después del commit y ya no tocarás la sesión (habitual con `AsyncSession`), pero aceptas que esos valores puedan estar desfasados. Es una decisión consciente, no un arreglo de errores.

Comprobación: ejecuta el primer bloque con `echo=True` y cuenta las sentencias. Debe haber un solo `SELECT` para los dos `get`, y el `UPDATE` y el `INSERT` deben aparecer **justo antes** del `SELECT` de pedidos, no en las líneas donde asignaste o añadiste.""",
            },
        ]
    },
    # 19) SQLAlchemy: del Query legacy a select() 2.0, scalars frente a execute (inglés, pide español)
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm migrating a codebase from `session.query(User).filter_by(...).first()` to SQLAlchemy 2.0 style. What are the equivalents of the common patterns, and when do I use `scalars()` vs `execute()`? Please answer in Spanish, the team is in Bogotá.",
            },
            {
                "role": "assistant",
                "content": """Primero una buena noticia: en 2.0, `session.query()` sigue funcionando; está marcado como API *legacy*, no eliminado. Pueden migrar por módulos, sin un cambio masivo.

**Equivalencias más comunes:**

| Estilo 1.x (`Query`) | Estilo 2.0 (`select`) |
|---|---|
| `session.query(User).get(1)` | `session.get(User, 1)` |
| `session.query(User).filter_by(email=e).first()` | `session.scalars(select(User).filter_by(email=e)).first()` |
| `session.query(User).filter(User.active).all()` | `session.scalars(select(User).where(User.active)).all()` |
| `.one()` / `.one_or_none()` | `session.scalars(stmt).one()` / `.one_or_none()` |
| `session.query(User.id, User.name).all()` | `session.execute(select(User.id, User.name)).all()` |
| `session.query(User).count()` | `session.scalar(select(func.count()).select_from(User))` |
| `query.filter(...).update({...})` | `session.execute(update(User).where(...).values(...))` |
| `query.join(User.orders)` | `select(User).join(User.orders)` |

**`scalars()` frente a `execute()`**, que es la duda que más se repite:

- `session.execute(stmt)` devuelve filas (`Row`), que son tuplas con acceso por nombre. Con `select(User)`, cada fila es `(User,)`: una tupla de un elemento.
- `session.scalars(stmt)` toma **la primera columna** de cada fila. Con `select(User)`, eso te da directamente objetos `User`.
- `session.scalar(stmt)`: la primera columna de la primera fila, o `None`. Ideal para conteos y valores sueltos.

Regla práctica: **¿seleccionas entidades? `scalars`. ¿Varias columnas o expresiones? `execute`. ¿Un único valor? `scalar`.**

Ejemplos completos:

```python
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer, Order


def customers_with_paid_orders(session: Session, min_total: Decimal) -> list[Customer]:
    stmt = (
        select(Customer)
        .join(Customer.orders)
        .where(Order.status == "paid", Order.total >= min_total)
        .distinct()
        .order_by(Customer.id)
    )
    return list(session.scalars(stmt))


def revenue_by_customer(session: Session) -> list[tuple[str, Decimal]]:
    stmt = (
        select(Customer.email, func.sum(Order.total).label("revenue"))
        .join(Order, Order.customer_id == Customer.id)
        .group_by(Customer.email)
        .order_by(func.sum(Order.total).desc())
    )
    return [(row.email, row.revenue) for row in session.execute(stmt)]


def count_pending_orders(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Order).where(Order.status == "pending")) or 0
```

Dos trampas al migrar:

- **`execute(select(User)).all()` devuelve tuplas, no usuarios.** El código que hacía `for user in query.all(): user.email` y pasa a `execute` sin `scalars` falla con `AttributeError: 'Row' object has no attribute 'email'`... o, peor, funciona a medias si alguien accede por índice.
- **`.distinct()` con `join` a una colección**: sin él, un cliente con tres pedidos pagados aparece tres veces, igual que con `Query`.

Para comprobar cada función migrada: imprimen la sentencia (`print(stmt)`) y la comparan con el SQL de la versión anterior (`print(query)`); deben ser equivalentes. Y los tests existentes de esa capa deben pasar sin tocarlos, que es la verdadera prueba de que la migración no cambió el comportamiento.""",
            },
        ]
    },
    # 20) SQLAlchemy: lazy loading oculto en la plantilla y DetachedInstanceError (multiturno, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": "En una vista de Flask con SQLAlchemy 2.0 listo 50 clientes y para cada uno muestro cuántos pedidos tiene y la fecha del último. Con `echo=True` veo 51 consultas. ¿Por qué, si no hago ningún bucle de consultas?",
            },
            {
                "role": "assistant",
                "content": """Sí lo haces, solo que está escondido en la plantilla. Las relaciones de SQLAlchemy son **perezosas** por defecto (`lazy="select"`): `customer.orders` no se carga con el cliente, sino la primera vez que alguien lo lee. Tu plantilla hace `{{ customer.orders|length }}` dentro de un `for`, y cada acceso dispara un `SELECT ... WHERE customer_id = ?`. 1 consulta de clientes + 50 de pedidos = 51. Es un N+1.

Dos arreglos, según qué necesites mostrar.

**A. Si necesitas los pedidos de verdad**, cárgalos por adelantado con `selectinload`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Customer


def customers_with_orders(session: Session) -> list[Customer]:
    stmt = (
        select(Customer)
        .options(selectinload(Customer.orders))
        .order_by(Customer.id)
        .limit(50)
    )
    return list(session.scalars(stmt))
```

Son **2 consultas** fijas: clientes, y luego todos sus pedidos con `WHERE customer_id IN (...)`.

`selectinload` o `joinedload`: para colecciones (uno a muchos), `selectinload`. `joinedload` hace un único `JOIN`, pero repite los datos del cliente por cada pedido y obliga a llamar a `.unique()` sobre el resultado; encaja mejor con relaciones a uno (`Order.customer`).

**B. Si solo muestras el número y la fecha** (tu caso), cargar todos los pedidos es traer miles de filas para contarlas en Python. Pide el agregado:

```python
from sqlalchemy import func, select

from app.models import Customer, Order


def customer_order_summary_stmt():
    order_stats = (
        select(
            Order.customer_id,
            func.count(Order.id).label("order_count"),
            func.max(Order.created_at).label("last_order_at"),
        )
        .group_by(Order.customer_id)
        .subquery()
    )
    return (
        select(Customer.id, Customer.email, order_stats.c.order_count, order_stats.c.last_order_at)
        .outerjoin(order_stats, order_stats.c.customer_id == Customer.id)
        .order_by(Customer.id)
        .limit(50)
    )
```

Una sola consulta, y la base devuelve 50 filas ya resumidas (asumo que `Order` tiene `created_at`).

**Para que no vuelva a pasar**, haz que la carga perezosa sea un error en lugar de una consulta silenciosa:

```python
orders: Mapped[list[Order]] = relationship(back_populates="customer", lazy="raise")
```

Cualquier acceso a `customer.orders` sin haberlo cargado explícitamente lanza `InvalidRequestError: 'Customer.orders' is not available due to lazy='raise'`. Molesta una semana y después nadie vuelve a escribir un N+1 por accidente. Si prefieres no tocar el modelo, `.options(raiseload("*"))` hace lo mismo por consulta.

Comprobación: con `echo=True`, la página debe mostrar 2 consultas con la opción A o 1 con la B, tengas 50 clientes o 500.""",
            },
            {
                "role": "user",
                "content": "Puse `selectinload` y bajó a 2. Pero en otra vista ahora me sale `DetachedInstanceError: Parent instance <Customer at 0x7f3a...> is not bound to a Session; lazy load operation of attribute 'orders' cannot proceed`. La función que consulta abre la sesión con `with`, y devuelve los clientes a la plantilla.",
            },
            {
                "role": "assistant",
                "content": """El mensaje cuenta la secuencia exacta:

1. Tu función abre la sesión con `with`, consulta los clientes **sin** cargar `orders` y sale del `with`: la sesión se cierra.
2. Los objetos `Customer` quedan **desacoplados** (*detached*): siguen existiendo, con los atributos que se cargaron, pero ya no tienen sesión.
3. La plantilla lee `customer.orders`, que no estaba cargado. SQLAlchemy intenta la carga perezosa, no hay sesión con la que consultar y lanza `DetachedInstanceError`.

Es la otra cara del N+1: antes la carga perezosa funcionaba y era lenta; ahora no puede funcionar. Tres arreglos, de más a menos recomendable.

**1. Devolver datos, no objetos del ORM.** La función decide qué necesita la vista, lo carga y lo copia a estructuras simples. La plantilla deja de depender de la sesión:

```python
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class CustomerSummary:
    id: int
    email: str
    order_count: int
    last_order_at: datetime | None


def list_customer_summaries(session_factory: sessionmaker[Session]) -> list[CustomerSummary]:
    with session_factory() as session:
        rows = session.execute(customer_order_summary_stmt()).all()
    return [
        CustomerSummary(
            id=row.id,
            email=row.email,
            order_count=row.order_count or 0,
            last_order_at=row.last_order_at,
        )
        for row in rows
    ]
```

**2. Cargar todo lo que la plantilla usa dentro de la sesión**, con `selectinload` en esa consulta también. Funciona, pero el contrato es implícito: el día que alguien añada `customer.address.city` a la plantilla, vuelve el error.

**3. Mantener la sesión abierta toda la petición** (lo que hace Flask-SQLAlchemy, que la cierra en el *teardown*). Elimina el error, pero reabre la puerta al N+1 silencioso en las plantillas. Si vas por aquí, combínalo con `lazy="raise"`.

Una variante del mismo error que verás tarde o temprano: si la función hace `commit()` y luego devuelve objetos, `expire_on_commit=True` los ha caducado **todos**, y el mensaje cambia a `Instance <Customer at 0x...> is not bound to a Session; attribute refresh operation cannot proceed`, incluso para `customer.email`. Mismo origen: acceso fuera de la sesión. Con DTOs (opción 1) tampoco ocurre.

Comprobación: con la opción 1, añade a la plantilla un acceso a un atributo que no existe en `CustomerSummary`: debe fallar al renderizar con un error claro de atributo, no con una consulta escondida ni con `DetachedInstanceError`.""",
            },
        ]
    },
    # 21) SQLAlchemy async: MissingGreenlet por carga perezosa (system rioplatense, error concreto)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y con código completo."},
            {
                "role": "user",
                "content": """Pasé mi API de FastAPI a SQLAlchemy async con asyncpg y ahora este endpoint falla:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place?
```

```python
@app.get("/customers/{customer_id}")
async def get_customer(customer_id: int, session: AsyncSession = Depends(get_session)):
    customer = await session.get(Customer, customer_id)
    return {"email": customer.email, "orders": [o.id for o in customer.orders]}
```""",
            },
            {
                "role": "assistant",
                "content": """El mensaje es críptico pero la pregunta final lo resume: *Was IO attempted in an unexpected place?* Sí: en `customer.orders`.

**Qué pasa.** En modo síncrono, leer `customer.orders` sin haberlo cargado dispara una consulta perezosa, de forma invisible. En modo async eso no puede ocurrir: una consulta necesita un `await`, y leer un atributo no es algo que se pueda esperar. SQLAlchemy intenta igual hacer la consulta, descubre que está fuera del contexto donde puede hacer I/O asíncrono y lanza `MissingGreenlet`. Regla de oro con `AsyncSession`: **todo lo que vas a leer tiene que estar cargado antes**; no existe la carga perezosa implícita.

Arreglo: cargar la relación en la misma consulta.

```python
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.models import Customer

engine = create_async_engine(
    "postgresql+asyncpg://app:secret@localhost/shop",
    pool_size=10,
    max_overflow=5,
)
# expire_on_commit=False: después de un commit, leer atributos no debe disparar recargas (que fallarían igual).
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

app = FastAPI()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.get("/customers/{customer_id}")
async def get_customer(customer_id: int, session: SessionDep) -> dict[str, object]:
    stmt = (
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.orders))
    )
    customer = await session.scalar(stmt)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"email": customer.email, "orders": [order.id for order in customer.orders]}
```

Si preferís seguir con `session.get`, también acepta opciones: `await session.get(Customer, customer_id, options=[selectinload(Customer.orders)])`.

Otras salidas, para cuando de verdad no sabés de antemano qué vas a necesitar:

- **`AsyncAttrs`** en la base declarativa (`class Base(AsyncAttrs, DeclarativeBase)`) habilita `orders = await customer.awaitable_attrs.orders`: la carga perezosa, pero explícita y esperable.
- **`await session.refresh(customer, ["orders"])`** carga ese atributo puntual.

Y para que el próximo error sea claro en vez de críptico, poné `lazy="raise"` en las relaciones de los modelos que usás en async: un acceso sin cargar lanza `'Customer.orders' is not available due to lazy='raise'`, que dice exactamente qué falta.

Dos cosas más que muerden al pasar a async:

- **Una `AsyncSession` no se comparte entre tareas concurrentes.** Un `asyncio.gather` con dos consultas sobre la misma sesión falla, porque la sesión usa una sola conexión. Para paralelizar, una sesión por tarea.
- **Tu código original devolvía 500 si el cliente no existía** (`customer.email` sobre `None`). El `404` explícito lo resuelve.

Comprobación: pedí un cliente con pedidos y otro inexistente. El primero tiene que devolver la lista de ids con `echo=True` mostrando dos `SELECT` (cliente y pedidos con `IN`); el segundo, un 404.""",
            },
        ]
    },
    # 22) Alembic: autogenerate y renombrados; columna NOT NULL en tabla grande (multiturno, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Con Alembic cambié el nombre de una columna en el modelo (`fullname` a `full_name`) y el autogenerate me genera un `drop_column` y un `add_column`. ¿Es normal? Casi lo aplico en staging.",
            },
            {
                "role": "assistant",
                "content": """Es normal, y menos mal que lo revisaste: aplicado tal cual, **borra la columna con todos sus datos** y crea una vacía.

Autogenerate compara tus modelos con el esquema real de la base. Ve que en la base hay `fullname` y en el modelo no, y que en el modelo hay `full_name` y en la base no. No puede saber que es la misma columna con otro nombre, así que propone lo único que sabe expresar: borrar una y crear otra. **Autogenerate produce un borrador, no una migración.**

La migración correcta se escribe a mano:

```python
'''Renombra customers.fullname a full_name.

Revision ID: 3f2a9c1d7b10
Revises: 8b41e6a0c2d5
'''
from alembic import op

revision = "3f2a9c1d7b10"
down_revision = "8b41e6a0c2d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("customers", "fullname", new_column_name="full_name")


def downgrade() -> None:
    op.alter_column("customers", "full_name", new_column_name="fullname")
```

Lo que autogenerate **no detecta o detecta mal**, y conviene revisar siempre:

- Renombrados de tablas y columnas (los ve como borrar y crear).
- Cambios de `server_default` (solo si activas `compare_server_default=True` en `env.py`).
- Cambios en los valores de un `ENUM` de Postgres.
- Restricciones sin nombre explícito: define una `naming_convention` en el `MetaData` de tu base declarativa para que todas tengan nombres estables.

Y un aviso de despliegue: renombrar una columna rompe las instancias de la aplicación que sigan ejecutando la versión anterior durante el despliegue (buscan `fullname` y ya no existe). Si despliegas sin parada, haz el cambio en fases: añade `full_name`, escribe en las dos, copia los datos, cambia las lecturas y, en una versión posterior, borra `fullname`.

Comprobación: en una copia de la base con datos, aplica la migración y verifica que `full_name` conserva los valores (`SELECT count(*) FROM customers WHERE full_name IS NOT NULL` igual que antes con `fullname`). Luego `alembic downgrade -1` y `alembic upgrade head` deben ir y volver sin pérdidas.""",
            },
            {
                "role": "user",
                "content": "Ahora tengo que añadir una columna `country` NOT NULL a una tabla de 20 millones de filas en producción. ¿Cómo lo hago sin tumbar nada?",
            },
            {
                "role": "assistant",
                "content": """Depende de si existe un valor por defecto razonable.

**Caso fácil: hay un valor por defecto constante.** Desde Postgres 11, `ADD COLUMN ... NOT NULL DEFAULT 'ES'` con un valor constante es una operación de metadatos: no reescribe la tabla y tarda milisegundos, tenga 20 filas o 20 millones.

```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("country", sa.String(2), nullable=False, server_default="ES"),
    )
```

**Caso real: no hay valor por defecto y hay que calcularlo.** Tres fases, en **migraciones separadas**:

**Fase 1: columna nullable** (instantáneo):

```python
def upgrade() -> None:
    op.add_column("customers", sa.Column("country", sa.String(2), nullable=True))
```

Despliega en este punto código que ya rellene `country` en las filas nuevas.

**Fase 2: rellenar por lotes**, fuera de las migraciones (un script o un job), con una transacción corta por lote para no bloquear la tabla ni generar una transacción gigante:

```python
from sqlalchemy import Engine, text

BATCH_SIZE = 10_000

BACKFILL_BATCH = text(
    "UPDATE customers AS c SET country = a.country_code "
    "FROM addresses AS a "
    "WHERE a.customer_id = c.id AND c.id IN ("
    "  SELECT id FROM customers WHERE country IS NULL LIMIT :batch_size FOR UPDATE SKIP LOCKED"
    ")"
)


def backfill_country(engine: Engine) -> int:
    total = 0
    while True:
        with engine.begin() as connection:
            updated = connection.execute(BACKFILL_BATCH, {"batch_size": BATCH_SIZE}).rowcount
        total += updated
        if updated == 0:
            return total
```

Antes de la fase 3, comprueba que no queda ninguna fila sin valor (`SELECT count(*) FROM customers WHERE country IS NULL` debe dar 0); las filas sin dirección necesitan una decisión de negocio, no un `NOT NULL` a la fuerza.

**Fase 3: imponer el NOT NULL sin bloquear.** `ALTER COLUMN ... SET NOT NULL` a secas recorre los 20 millones de filas con un bloqueo exclusivo: nadie lee ni escribe mientras tanto. El truco es validar primero con una restricción `CHECK`, que se valida sin bloquear las escrituras, y Postgres 12+ la aprovecha para no recorrer la tabla otra vez. Dos migraciones, porque Alembic ejecuta cada una en una transacción y los bloqueos se mantienen hasta el final de la transacción:

```python
# migración 3a: añadir la restricción sin validar (instantáneo)
def upgrade() -> None:
    op.execute("SET lock_timeout = '5s'")
    op.execute(
        "ALTER TABLE customers ADD CONSTRAINT customers_country_not_null "
        "CHECK (country IS NOT NULL) NOT VALID"
    )
```

```python
# migración 3b: validar (recorre la tabla sin bloquear escrituras) e imponer NOT NULL
def upgrade() -> None:
    op.execute("SET lock_timeout = '5s'")
    op.execute("ALTER TABLE customers VALIDATE CONSTRAINT customers_country_not_null")
    op.alter_column("customers", "country", nullable=False)  # rápido: la CHECK válida lo demuestra
    op.drop_constraint("customers_country_not_null", "customers", type_="check")
```

`lock_timeout` hace que, si la tabla está ocupada por una transacción larga, la migración falle en 5 segundos en lugar de quedarse esperando el bloqueo y encolar detrás de ella todas las consultas de la aplicación. Si falla, se reintenta en otro momento.

Comprobación en una copia de producción con el mismo volumen: mide cuánto tarda cada fase y, mientras se ejecuta la 3b, lanza escrituras contra la tabla; deben seguir funcionando. En `pg_locks` no debe aparecer un `AccessExclusiveLock` sobre `customers` durante la validación.""",
            },
        ]
    },
    # 23) UUID como clave primaria: v4 frente a v7 y enteros, con SQLAlchemy (transversal, intermedio-avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Estamos diseñando una base nueva con SQLAlchemy y Postgres. ¿Usamos UUID como clave primaria o enteros autoincrementales? Y si UUID, ¿v4 o v7? Leí que los UUID son malos para los índices.",
            },
            {
                "role": "assistant",
                "content": """Lo que leíste es cierto para **UUIDv4**, no para los UUID en general. La diferencia está en el orden.

| | `bigint` identity | UUIDv4 | UUIDv7 |
|---|---|---|---|
| Tamaño | 8 bytes | 16 bytes | 16 bytes |
| Orden de inserción | creciente | aleatorio | creciente (prefijo de tiempo en ms) |
| Localidad en el índice B-tree | buena | mala | buena |
| Se genera fuera de la base | no (necesita la secuencia) | sí | sí |
| Revela algo | volumen y ritmo de altas (`/orders/1042`) | nada | el instante de creación |
| Enumerable por un atacante | sí | no | no en la práctica |

**Por qué v4 es malo para el índice:** cada id nuevo cae en una página aleatoria del índice de la clave primaria. Con tablas grandes, eso significa páginas que hay que leer del disco para insertar, divisiones de página por todo el árbol y más escritura en el WAL. Con v7 (o con `bigint`), los ids nuevos van siempre al final del índice: las páginas calientes caben en memoria.

**Recomendación:**

- **UUIDv7** para entidades cuyo id sale en URLs o APIs, o que se crean fuera de la base (clientes móviles offline, servicios que generan el id antes de insertar).
- **`bigint` identity** para tablas internas de mucho volumen que nunca se exponen (líneas de log, eventos), donde los 8 bytes extra por fila y por índice se notan.
- **No v4 como clave primaria** en tablas que vayan a crecer, salvo que necesites que el id no revele ni siquiera el momento de creación.

Con SQLAlchemy 2.x, `Mapped[uuid.UUID]` se mapea al tipo `UUID` nativo de Postgres. Para generar v7: Python 3.14 trae `uuid.uuid7()`; en 3.10-3.13, el paquete `uuid6` de PyPI ofrece la misma función.

```python
import uuid
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid6 import uuid7  # en Python 3.14+: from uuid import uuid7


class Base(DeclarativeBase):
    pass


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
```

Si prefieres que lo genere la base: Postgres 18 incluye la función `uuidv7()`, y la columna sería `mapped_column(primary_key=True, server_default=text("uuidv7()"))`. Generarlo en Python tiene una ventaja práctica: conoces el id antes del `INSERT`, así que puedes usarlo en logs o en otras filas sin esperar al flush.

Tres errores frecuentes:

- **Guardar UUID como texto** (`VARCHAR(36)`): ocupa más del doble, compara más lento y admite valores mal formados. Siempre el tipo nativo.
- **Tratar el UUID como un secreto.** Que no sea adivinable no lo convierte en autorización: el acceso se comprueba siempre, por muy opaco que sea el id.
- **Mezclar v4 y v7 en la misma tabla** al migrar: los v4 antiguos quedan dispersos en el índice; no rompe nada, pero no esperes la mejora completa hasta que dominen los nuevos.

Comprobación con datos: en una base de pruebas, inserta un millón de filas con v4 en una tabla y un millón con v7 en otra, y compara el tiempo total de inserción y el tamaño del índice de la clave primaria (`SELECT pg_size_pretty(pg_relation_size('invoices_pkey'))`). Y `SELECT id FROM invoices ORDER BY id LIMIT 5` con v7 debe devolver los ids en el orden en que se crearon.""",
            },
        ]
    },
    # 24) SQLAlchemy: bloqueo optimista con version_id_col contra actualizaciones perdidas (inglés, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Two admins edit the same product in our back office (SQLAlchemy 2.0 + FastAPI). The last save silently overwrites the first one's changes. How do I detect that instead of losing data?",
            },
            {
                "role": "assistant",
                "content": """That is a **lost update**, and the standard fix for edits that span human think-time is **optimistic locking**: every row carries a version number, every update says "only if the version is still the one I read", and a mismatch becomes a conflict instead of a silent overwrite.

SQLAlchemy has it built in with `version_id_col`:

```python
from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    version_id: Mapped[int] = mapped_column(Integer, nullable=False)

    __mapper_args__ = {"version_id_col": version_id}
```

With this mapping, SQLAlchemy sets `version_id = 1` on insert and turns every ORM update into:

```sql
UPDATE products SET name = ?, price = ?, version_id = ? WHERE products.id = ? AND products.version_id = ?
```

If another transaction already bumped the version, the `UPDATE` matches 0 rows and SQLAlchemy raises `StaleDataError`.

That covers two sessions racing inside the server. Your admins' case has one more step: the "read" happened in an **earlier request**, when the edit form loaded. So the version travels with the form, and the server checks it:

```python
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

app = FastAPI()
SessionDep = Annotated[Session, Depends(get_session)]  # one session per request


class ProductUpdate(BaseModel):
    name: str
    price: Decimal
    version_id: int  # the version the admin saw when the form loaded


CONFLICT_DETAIL = "This product was changed by someone else. Reload to see the latest version."


@app.put("/products/{product_id}")
def update_product(product_id: int, payload: ProductUpdate, session: SessionDep) -> dict[str, int]:
    try:
        with session.begin():
            product = session.get(Product, product_id)
            if product is None:
                raise HTTPException(status_code=404, detail="Product not found")
            if product.version_id != payload.version_id:
                raise HTTPException(status_code=409, detail=CONFLICT_DETAIL)  # stale form
            product.name = payload.name
            product.price = payload.price
    except StaleDataError as error:
        # Someone committed between our SELECT and our UPDATE, inside this very request.
        raise HTTPException(status_code=409, detail=CONFLICT_DETAIL) from error
    return {"id": product.id, "version_id": product.version_id}
```

The two checks cover different windows:

- **`product.version_id != payload.version_id`**: the admin edited a form loaded minutes ago and someone saved in between. This is the common case.
- **`StaleDataError`**: the narrow race between this request's `SELECT` and its `UPDATE`. Rare, but without it the check above would still have a gap.

Design notes:

- **Return the new `version_id`** in every response so the client can keep editing without reloading.
- **HTTP-native variant**: send the version as an `ETag` and require `If-Match` on `PUT`, answering `412 Precondition Failed` on mismatch. Same mechanism, standard headers; worth it if the API is public.
- **What the UI does with a 409** matters as much: show both versions and let the admin merge or overwrite deliberately.
- **Pessimistic locking (`SELECT ... FOR UPDATE`, `.with_for_update()`)** is for short critical sections inside one transaction, such as decrementing stock, never for the minutes a human spends on a form.

Verification test: load the product in two sessions (both see version 1), change and commit the first, then submit the second with `version_id=1`. The endpoint must answer 409, and the row must keep the first admin's values with `version_id = 2`.""",
            },
        ]
    },
    # 25) SQLAlchemy + pytest: cada test en una transacción que se deshace (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo monto los tests de integración con SQLAlchemy y Postgres para que cada test empiece con la base limpia, sin tardar una eternidad recreando tablas en cada uno? Ahora hago `drop_all` y `create_all` por test y la suite tarda 6 minutos.",
            },
            {
                "role": "assistant",
                "content": """Crea el esquema **una vez por sesión de pytest** y ejecuta cada test dentro de una transacción que se deshace al terminar. Deshacer una transacción cuesta milisegundos; recrear todas las tablas, segundos.

La pieza que lo hace posible aunque tu código llame a `session.commit()` es `join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0): la sesión se une a una transacción externa que controla el test, y sus `commit()` solo liberan *savepoints* dentro de ella.

```python
# tests/conftest.py
import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://test:test@localhost:5433/shop_test"
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # una vez para toda la suite
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with engine.connect() as connection:
        outer = connection.begin()  # transacción que el test nunca confirma
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            outer.rollback()        # todo lo que hizo el test desaparece
```

```python
# tests/test_customers.py
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.customers import register_customer  # hace session.add(...) y session.commit()
from app.models import Customer


def test_register_customer_persists(session: Session) -> None:
    customer = register_customer(session, email="ana@example.com")
    assert session.get(Customer, customer.id) is not None


def test_each_test_starts_clean(session: Session) -> None:
    assert session.scalar(select(func.count()).select_from(Customer)) == 0
```

Decisiones y límites:

- **Postgres de verdad, no SQLite.** Los tipos, las restricciones, `ON CONFLICT` y los bloqueos se comportan distinto; un test que pasa en SQLite no demuestra nada sobre producción. Un contenedor (con `docker compose` o `testcontainers`) en un puerto propio basta.
- **Mejor aún: crear el esquema con las migraciones** en lugar de `create_all`, llamando a `alembic.command.upgrade(Config("alembic.ini"), "head")` en la fixture de sesión. Así la suite también prueba que las migraciones producen el esquema que esperan los modelos.
- **El código bajo test debe recibir la sesión.** Si una función crea su propia sesión desde una fábrica global, escapa de la transacción del test, confirma de verdad y ensucia la base. Es una buena razón de diseño, no solo de tests, para inyectar la sesión o la fábrica.
- **Lo que este patrón no puede probar**: comportamiento entre dos conexiones (bloqueos, aislamiento, el `StaleDataError` del bloqueo optimista). Esos tests confirman de verdad y limpian con `TRUNCATE ... RESTART IDENTITY CASCADE` al final; márcalos aparte y que sean pocos.
- **Con `pytest-xdist`**, cada proceso necesita su propia base (por ejemplo, `shop_test_gw0`, `shop_test_gw1`), porque comparten el esquema y la limpieza de uno interferiría con los demás.

Comprobación: ejecuta la suite en orden aleatorio (`pytest -p randomly`) varias veces; `test_each_test_starts_clean` debe pasar siempre, también cuando se ejecuta justo después de un test que insertó clientes. Y compara el tiempo total: con 300 tests, la diferencia suele ser de minutos a segundos.""",
            },
        ]
    },
    # 26) TypeORM 0.3: entidades, DataSource, repositorios y synchronize (SISTEMA, intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo que trabajar con TypeORM 0.3 en un servicio Node existente. ¿Cómo se definen bien las entidades, el DataSource y los repositorios? Veo `synchronize: true` en la config y no sé si es buena idea.",
            },
            {
                "role": "assistant",
                "content": """Empiezo por `synchronize`, porque es lo urgente: **en cualquier base con datos que importen, `synchronize: true` es un riesgo serio.** Al arrancar, TypeORM compara las entidades con la base y aplica los cambios directamente, sin migración ni revisión. Si alguien renombra una propiedad, TypeORM borra la columna antigua (con sus datos) y crea una nueva. Sirve para prototipos desechables; en el resto, migraciones.

**DataSource:**

```ts
// src/data-source.ts
import "reflect-metadata";
import { DataSource } from "typeorm";
import { Customer } from "./entities/customer";
import { Order } from "./entities/order";

export const AppDataSource = new DataSource({
  type: "postgres",
  url: process.env.DATABASE_URL,
  entities: [Customer, Order],
  migrations: [__dirname + "/migrations/*.{ts,js}"],
  synchronize: false,
  logging: ["error", "warn", "migration"],
  extra: { max: 10 }, // tamaño del pool del driver pg
});
```

**Entidades:**

```ts
// src/entities/customer.ts
import { Column, CreateDateColumn, Entity, Index, OneToMany, PrimaryGeneratedColumn } from "typeorm";
import { Order } from "./order";

@Entity({ name: "customers" })
export class Customer {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Index({ unique: true })
  @Column({ type: "varchar", length: 320 })
  email!: string;

  @Column({ name: "full_name", type: "varchar", length: 200, nullable: true })
  fullName!: string | null;

  @CreateDateColumn({ name: "created_at", type: "timestamptz" })
  createdAt!: Date;

  @OneToMany(() => Order, (order) => order.customer)
  orders!: Order[];
}
```

```ts
// src/entities/order.ts
import { Column, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn } from "typeorm";
import { Customer } from "./customer";

@Entity({ name: "orders" })
export class Order {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Index()
  @Column({ name: "customer_id", type: "uuid" })
  customerId!: string;

  @ManyToOne(() => Customer, (customer) => customer.orders, { onDelete: "CASCADE" })
  @JoinColumn({ name: "customer_id" })
  customer!: Customer;

  @Column({ name: "total_cents", type: "integer" })
  totalCents!: number;

  @Column({ type: "varchar", length: 20, default: "pending" })
  status!: string;
}
```

**Repositorios y arranque:**

```ts
// src/customers/customer-repository.ts
import { AppDataSource } from "../data-source";
import { Customer } from "../entities/customer";

const customers = AppDataSource.getRepository(Customer);

export function findCustomerWithOrders(id: string) {
  return customers.findOne({ where: { id }, relations: { orders: true } });
}

export function createCustomer(email: string, fullName: string | null) {
  const customer = customers.create({ email: email.trim().toLowerCase(), fullName });
  return customers.save(customer);
}
```

```ts
// src/main.ts
import { AppDataSource } from "./data-source";

await AppDataSource.initialize(); // antes de usar cualquier repositorio
```

Decisiones que evitan los errores típicos de TypeORM:

- **`type` explícito en cada `@Column`.** TypeORM deduce el tipo con los metadatos de los decoradores, y una unión como `string | null` llega como `Object`: el arranque falla con *Data type "Object" in "Customer.fullName" is not supported by "postgres" database*. Con `type` explícito no hay deducción que falle.
- **`customerId` como columna además de la relación.** Puedes filtrar y asignar por id (`{ customerId }`) sin cargar el cliente entero.
- **`!` en las propiedades**: TypeORM las rellena al hidratar, así que se le dice al compilador que no exija inicializarlas. Requiere `experimentalDecorators` y `emitDecoratorMetadata` en `tsconfig.json`.
- **`EntityMetadataNotFoundError: No metadata for "Customer" was found`** significa que la entidad no está en `entities` o que el patrón de archivos apunta a `.ts` cuando ejecutas el `.js` compilado. La lista explícita de clases, como arriba, evita el problema de los patrones.
- **`@Index()` en la clave foránea**: Postgres no la indexa solo.

Comprobación: con `synchronize: false`, genera la migración inicial (`npx typeorm-ts-node-commonjs migration:generate src/migrations/Init -d src/data-source.ts`) y revisa el SQL: deben aparecer las dos tablas, el índice único de email, el índice de `customer_id` y la FK con `ON DELETE CASCADE`.""",
            },
        ]
    },
    # 27) TypeORM QueryBuilder: paginación con joins y agregados con getRawMany (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "En TypeORM tengo un listado de clientes con sus pedidos pagados usando QueryBuilder y paginación con `.offset(20).limit(10)`. Algunas páginas salen con menos de 10 clientes y otras repiten clientes de la página anterior. ¿Qué pasa?",
            },
            {
                "role": "assistant",
                "content": """`offset` y `limit` se traducen literalmente a `OFFSET` y `LIMIT` en SQL, y se aplican a las **filas del join**, no a los clientes. Un `leftJoinAndSelect` de clientes con pedidos devuelve una fila por pedido: un cliente con 5 pedidos ocupa 5 filas. Con `LIMIT 10`, una página puede contener solo 3 clientes, y un cliente puede quedar partido entre dos páginas, con algunos pedidos en una y el resto en la siguiente (de ahí los repetidos).

TypeORM tiene los métodos pensados para esto: **`skip` y `take`**. Con joins, hacen la paginación a nivel de entidad: primero una consulta que obtiene los ids de los 10 clientes de la página, y después otra que carga esos clientes con sus pedidos.

```ts
import { AppDataSource } from "./data-source";
import { Customer } from "./entities/customer";

export async function listCustomersPage(page: number, pageSize = 10) {
  if (!Number.isInteger(page) || page < 1) throw new RangeError("page debe ser un entero >= 1");

  const [items, total] = await AppDataSource.getRepository(Customer)
    .createQueryBuilder("customer")
    // la condición en el join filtra los pedidos, no los clientes: los que no tienen pagados salen con []
    .leftJoinAndSelect("customer.orders", "o", "o.status = :status", { status: "paid" })
    .orderBy("customer.createdAt", "DESC")
    .addOrderBy("customer.id", "DESC") // desempate: orden total y estable entre páginas
    .skip((page - 1) * pageSize)
    .take(pageSize)
    .getManyAndCount();

  return { items, total, page, pageSize };
}
```

Detalles:

- **Orden total.** Sin el desempate por `id`, dos clientes con el mismo `createdAt` pueden cambiar de orden entre consultas y aparecer en dos páginas o en ninguna. Esto pasa con cualquier ORM.
- **Parámetros con nombre (`:status`)** y el valor en el objeto: TypeORM los envía como parámetros. Nunca interpoles valores en la cadena del QueryBuilder.
- **El alias `o`** y no `order`: `ORDER` es palabra reservada en SQL, y usarla como alias es buscarse errores de sintaxis en algunas expresiones.
- **`getManyAndCount`** hace además un `COUNT(DISTINCT ...)`. En tablas muy grandes puede costar más que la página; si es un listado infinito, quita el total o pasa a paginación por cursor.

Comprobación: crea 15 clientes, algunos con varios pedidos pagados, y pide las páginas 1 y 2 con tamaño 10. La primera debe tener exactamente 10 clientes, la segunda 5, y ningún id debe aparecer en las dos.""",
            },
            {
                "role": "user",
                "content": "Ahora necesito solo el número de pedidos por cliente, no los pedidos. Probé `getMany()` con un `COUNT` en el select y el campo no aparece en el resultado.",
            },
            {
                "role": "assistant",
                "content": """`getMany()` solo hidrata **columnas de la entidad**: construye objetos `Customer` y descarta todo lo demás que venga en la fila, incluido tu `COUNT`. Para valores calculados hay dos caminos.

**1. `getRawMany()`, con alias explícitos.** Devuelve las filas tal cual las da la base, sin hidratar entidades:

```ts
import { AppDataSource } from "./data-source";
import { Customer } from "./entities/customer";

type CustomerOrderCountRow = { id: string; email: string; orderCount: string };

export type CustomerOrderCount = { id: string; email: string; orderCount: number };

export async function customersWithOrderCount(): Promise<CustomerOrderCount[]> {
  const rows = await AppDataSource.getRepository(Customer)
    .createQueryBuilder("customer")
    .leftJoin("customer.orders", "o")
    .select("customer.id", "id")
    .addSelect("customer.email", "email")
    .addSelect("COUNT(o.id)", "orderCount")
    .groupBy("customer.id")
    .addGroupBy("customer.email")
    .orderBy("COUNT(o.id)", "DESC")
    .getRawMany<CustomerOrderCountRow>();

  // COUNT devuelve bigint y el driver pg lo entrega como cadena: se convierte explícitamente.
  return rows.map((row) => ({ id: row.id, email: row.email, orderCount: Number(row.orderCount) }));
}
```

- **`leftJoin`, no `leftJoinAndSelect`**: no queremos las columnas de los pedidos, solo contarlos. Y `leftJoin` (no `innerJoin`) para que los clientes sin pedidos salgan con 0.
- **Alias en cada `select`**: sin ellos, las claves del resultado son del estilo `customer_id`, `customer_email`, que dependen de cómo TypeORM nombre las columnas.
- **`Number(row.orderCount)`**: el tipo genérico de `getRawMany<T>` es una promesa tuya, no una comprobación. El `bigint` llega como cadena, y por eso el tipo de la fila lo declara como `string` y la conversión es explícita.

**2. `loadRelationCountAndMap`**, si quieres seguir trabajando con entidades:

```ts
const customers = await AppDataSource.getRepository(Customer)
  .createQueryBuilder("customer")
  .loadRelationCountAndMap("customer.orderCount", "customer.orders")
  .getMany();
```

Necesita una propiedad no mapeada en la entidad (`orderCount?: number;`, sin decorador) y TypeORM lanza una consulta adicional para los conteos. Es cómodo cuando además necesitas el resto de la entidad.

Mi criterio: para listados e informes, `getRawMany` con un tipo de salida propio, porque el resultado no es un cliente sino un resumen y conviene que su tipo lo diga. `loadRelationCountAndMap` cuando la pantalla trabaja con entidades y el conteo es un dato más.

Comprobación: un cliente sin pedidos debe aparecer con `orderCount: 0` (número, no `"0"`), y el orden debe ir del que más pedidos tiene al que menos.""",
            },
        ]
    },
    # 28) TypeORM: flujo de migraciones en 0.3 y reconciliar cambios hechos a mano (system concisa)
    {
        "messages": [
            {"role": "system", "content": "Responde de forma concisa: pasos, comandos y el porqué en una línea cada uno."},
            {
                "role": "user",
                "content": "¿Cuál es el flujo correcto de migraciones en TypeORM 0.3? En el proyecto usan `synchronize` en local, y en producción alguien aplicó cambios a mano. Quiero ordenar esto.",
            },
            {
                "role": "assistant",
                "content": """**1. Scripts en `package.json`** (TypeORM 0.3 exige indicar el DataSource con `-d`):

```json
{
  "scripts": {
    "migration:generate": "typeorm-ts-node-commonjs migration:generate -d src/data-source.ts",
    "migration:create": "typeorm-ts-node-commonjs migration:create",
    "migration:run": "typeorm-ts-node-commonjs migration:run -d src/data-source.ts",
    "migration:revert": "typeorm-ts-node-commonjs migration:revert -d src/data-source.ts"
  }
}
```

**2. Ciclo de cada cambio de esquema:**

```bash
npm run migration:generate -- src/migrations/AddCustomerPhone   # compara entidades con la base y escribe el SQL
npm run migration:run                                            # aplica las pendientes
npm run migration:revert                                         # deshace la última, si hace falta
```

Resultado típico, que se revisa y se commitea:

```ts
import { MigrationInterface, QueryRunner } from "typeorm";

export class AddCustomerPhone1792454400000 implements MigrationInterface {
  name = "AddCustomerPhone1792454400000";

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`ALTER TABLE "customers" ADD "phone" character varying(20)`);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`ALTER TABLE "customers" DROP COLUMN "phone"`);
  }
}
```

**3. Reglas:**

- `synchronize: false` en todos los entornos compartidos: el esquema solo cambia vía migraciones revisadas.
- En local, si quieres iterar rápido, `synchronize` solo contra una base desechable; antes del commit, genera la migración contra una base limpia.
- `migration:generate` es un borrador: un renombrado aparece como `DROP` + `ADD`; corrígelo a `RENAME COLUMN` a mano.
- Para cambios de datos o SQL que el generador no conoce, `migration:create` da un archivo vacío donde escribirlo.
- En producción, `migration:run` como paso propio del despliegue, antes de arrancar la nueva versión. La opción `migrationsRun: true` del DataSource también funciona, pero con varias réplicas arrancando a la vez es mejor un único paso explícito.
- En producción se ejecuta el JS compilado: el patrón de `migrations` debe encontrar los `.js` de `dist/`.

**4. Reconciliar los cambios hechos a mano en producción:**

1. Restaura una copia de producción y ejecuta `migration:generate` contra ella: el archivo resultante describe exactamente la diferencia entre las entidades y la base real.
2. Decide en cada diferencia quién tiene razón: la entidad o el cambio manual. Ajusta las entidades hasta que la diferencia que queda sea solo lo que falta aplicar.
3. Si en producción ya existe algo que tu historial no recoge, crea una migración que lo describa y regístrala como aplicada en esa base, insertando su fila en la tabla `migrations` (columnas `timestamp` y `name`) en lugar de ejecutarla.
4. A partir de ahí, nadie toca el esquema de producción fuera de una migración.

Comprobación: sobre la copia restaurada, `migration:run` no debe tener nada pendiente y un nuevo `migration:generate` debe responder que no hay cambios.""",
            },
        ]
    },
    # 29) TypeORM: transacción que no deshace por usar repositorios globales, y bloqueo pesimista (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "En TypeORM tengo un servicio que crea un pedido y descuenta stock. Lo envolví en `dataSource.transaction(...)`, pero cuando falla el descuento de stock el pedido queda creado igual. ¿Por qué no hace rollback?",
            },
            {
                "role": "assistant",
                "content": r"""Casi seguro, dentro del callback usas los repositorios de siempre (inyectados en la clase o sacados de `AppDataSource.getRepository`) en lugar del `manager` que recibe el callback. Algo así:

```ts
// MAL: los repositorios globales usan otra conexión del pool, fuera de la transacción.
await AppDataSource.transaction(async (manager) => {
  await this.orderRepository.save(order);                                  // se confirma al instante
  await this.productRepository.decrement({ id: productId }, "stock", qty); // si falla, el pedido ya está guardado
});
```

Una transacción vive en **una conexión concreta**. `transaction()` toma una conexión del pool, ejecuta `BEGIN` y te da un `manager` atado a ella. Los repositorios globales piden su propia conexión al pool para cada operación, en modo *autocommit*: lo que hacen se confirma enseguida y el rollback del `manager` no puede tocarlo. Ningún error avisa de esto; simplemente no está dentro.

**Regla:** dentro del callback, todo pasa por `manager` (`manager.save`, `manager.findOne`, `manager.getRepository(X)`).

Versión correcta, que además resuelve la concurrencia del stock con bloqueo pesimista (asumo entidades `Product` con `stock` y `priceCents`, y `OrderItem`):

```ts
import { AppDataSource } from "./data-source";
import { Order } from "./entities/order";
import { OrderItem } from "./entities/order-item";
import { Product } from "./entities/product";

export class OutOfStockError extends Error {
  constructor(readonly productId: string) {
    super(`Sin stock suficiente para el producto ${productId}`);
    this.name = "OutOfStockError";
  }
}

export type OrderLine = { productId: string; quantity: number };

export async function placeOrder(customerId: string, lines: OrderLine[]): Promise<Order> {
  if (lines.length === 0 || lines.some((line) => !Number.isInteger(line.quantity) || line.quantity <= 0)) {
    throw new RangeError("El pedido necesita líneas con cantidades enteras positivas");
  }

  return AppDataSource.transaction(async (manager) => {
    const order = await manager.save(manager.create(Order, { customerId, status: "pending", totalCents: 0 }));

    let totalCents = 0;
    // Bloquear siempre en el mismo orden (por id) evita interbloqueos entre pedidos con productos en común.
    const sortedLines = [...lines].sort((a, b) => a.productId.localeCompare(b.productId));

    for (const line of sortedLines) {
      const product = await manager.findOne(Product, {
        where: { id: line.productId },
        lock: { mode: "pessimistic_write" }, // SELECT ... FOR UPDATE: nadie más lo modifica hasta el COMMIT
      });
      if (!product || product.stock < line.quantity) throw new OutOfStockError(line.productId);

      product.stock -= line.quantity;
      await manager.save(product);
      await manager.save(
        manager.create(OrderItem, {
          orderId: order.id,
          productId: product.id,
          quantity: line.quantity,
          unitPriceCents: product.priceCents,
        }),
      );
      totalCents += product.priceCents * line.quantity;
    }

    order.totalCents = totalCents;
    return manager.save(order);
  });
}
```

Por qué cada pieza:

- **Excepción dentro del callback = rollback de todo**: el pedido, las líneas y los descuentos de stock anteriores. `OutOfStockError` sale del `transaction()` y el llamador decide la respuesta HTTP.
- **`pessimistic_write`** bloquea la fila del producto entre la lectura y la escritura. Sin él, dos pedidos simultáneos leen `stock = 1`, los dos pasan la comprobación y el stock acaba en -1.
- **Orden de bloqueo por id**: si el pedido A bloquea X y luego Y mientras B bloquea Y y luego X, se interbloquean y Postgres aborta uno. Ordenando, ambos piden X primero.
- **Precio desde la base, no desde el cliente**: el `unitPriceCents` se copia del producto bloqueado, así que nadie puede pagar el precio que le apetezca.

Si el proyecto usa NestJS e inyecta repositorios por todas partes, pasar `manager` a mano se vuelve pesado; librerías como `typeorm-transactional` propagan la transacción por el contexto asíncrono. Funciona, pero entiende primero este modelo, porque esas librerías fallan exactamente de la misma forma cuando algo escapa de su contexto.

Comprobación: un test con dos líneas donde la segunda pide más stock del que hay. Después del `OutOfStockError`, el número de pedidos debe ser el mismo que antes y el stock del primer producto no debe haber cambiado. Y un test de concurrencia: stock 1 y dos `placeOrder` simultáneos con `Promise.allSettled`; exactamente uno debe cumplirse.""",
            },
        ]
    },
    # 30) TypeORM: ¿migrar a Prisma o Drizzle? Diagnóstico de eager relations y estrategia gradual (senior)
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestro backend usa TypeORM desde 2020: unas 80 entidades, relaciones con `eager: true` por todos lados y problemas raros de rendimiento. Hay presión para migrar a Prisma o Drizzle. ¿Lo hacemos?",
            },
            {
                "role": "assistant",
                "content": """Todavía no. Primero separad dos preguntas que suelen venir mezcladas: **¿los problemas los causa TypeORM o cómo se usa?** Con lo que describes, apostaría por lo segundo, y migrar 80 entidades sin resolverlo trasladaría los mismos problemas a otro ORM.

**El sospechoso principal: `eager: true`.** Una relación eager se carga en **cada** `find*` de esa entidad, la necesites o no. Con eager encadenados (el pedido carga el cliente, que carga su empresa, que carga su plan...), una lectura simple de pedidos acaba haciendo joins de media base. Además, las relaciones eager **no** se aplican en el QueryBuilder, así que la misma entidad devuelve datos distintos según cómo se consulte: otra fuente de bugs «raros».

**Dos semanas de estabilización, con datos:**

1. **Medir.** Activad el registro de consultas lentas:

```ts
export const AppDataSource = new DataSource({
  type: "postgres",
  url: process.env.DATABASE_URL,
  entities: [__dirname + "/entities/*.{ts,js}"],
  logging: ["error", "warn"],
  maxQueryExecutionTime: 200, // registra cada consulta que tarde más de 200 ms
});
```

y `pg_stat_statements` en la base para ver qué consultas consumen más tiempo en total.

2. **Quitar `eager` de forma gradual**, empezando por las relaciones de las consultas más caras, y que cada lectura pida lo que necesita:

```ts
// antes
@ManyToOne(() => Customer, { eager: true })
customer!: Customer;

// después: sin eager; quien necesita el cliente lo pide
@ManyToOne(() => Customer)
customer!: Customer;
```

```ts
const paidOrders = await orderRepository.find({
  where: { status: "paid" },
  relations: { customer: true },
  order: { id: "DESC" },
  take: 50,
});
```

Cada cambio, con los tests de integración del módulo y comparando el tiempo de esa consulta antes y después.

3. **Buscar N+1** en los mismos registros: muchas consultas idénticas salvo un id seguido.

**Después, decidir con números.** Si tras la estabilización los problemas desaparecen, migrar es un coste sin beneficio claro. Si persisten, o el equipo sufre con los decoradores, las relaciones *lazy* basadas en promesas y los tipos poco fiables (TypeORM no tipa el resultado según las relaciones cargadas: `order.customer` es `Customer` aunque no lo hayas cargado), entonces sí hay argumentos.

**Si migráis, nunca de golpe:**

- **Elección**: Drizzle si el equipo se maneja bien en SQL y queréis una capa fina con tipos exactos; Prisma si preferís una API de más alto nivel y su tooling.
- **Estrategia de estrangulamiento**: el código nuevo y cada módulo que se toque a fondo pasan al ORM nuevo, contra la misma base. Los tests de integración de cada módulo deben pasar igual antes y después.
- **Un único dueño del esquema**: las migraciones las sigue haciendo TypeORM hasta que el último módulo haya migrado; entonces el ORM nuevo toma el relevo. Dos herramientas generando migraciones a la vez corrompen el historial.
- **Coste realista**: con 80 entidades y una cobertura de tests razonable, hablamos de meses de trabajo intercalado con el producto, no de un sprint.

Comprobación de que la estabilización funcionó: compara el p95 de los endpoints principales y el top 10 de `pg_stat_statements` antes y después de quitar los eager más caros. Si el p95 baja de forma clara, ya sabéis dónde estaba el problema, y la decisión de migrar se toma sin urgencia.""",
            },
        ]
    },
]
