"""Next.js 15 App Router: estructura, Server/Client Components, datos y caché, Server Actions, rutas, despliegue y errores típicos."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# ---------------------------------------------------------------------------
# 1-10: estructura app/, Server vs Client, error "useState en Server Component" (multiturno), layouts,
#       loading/error/not-found, Server Actions, caché de fetch (multiturno), params async, Route Handlers, middleware
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Acabo de crear un proyecto con `create-next-app` (Next 15) y veo una carpeta `app/` con `page.tsx` y `layout.tsx`. ¿Qué archivos puedo poner ahí y qué significa cada uno? Vengo de Vite + React Router.",
            },
            {
                "role": "assistant",
                "content": r"""En el App Router **las carpetas son las rutas** y unos pocos nombres de archivo reservados definen qué se pinta en cada una. No hay archivo de configuración de rutas: la estructura del sistema de archivos es la configuración.

```
app/
  layout.tsx          # obligatorio en la raíz: <html> y <body>; envuelve todo
  page.tsx            # /            la UI de la ruta; sin page.tsx la carpeta no es accesible
  loading.tsx         # /            fallback de Suspense mientras page.tsx carga datos
  error.tsx           # /            error boundary de este segmento (es un Client Component)
  not-found.tsx       # /            lo que se muestra al llamar a notFound() o en 404
  globals.css
  products/
    page.tsx          # /products
    [id]/
      page.tsx        # /products/42   segmento dinámico: params.id === "42"
  dashboard/
    layout.tsx        # layout anidado: solo envuelve a /dashboard/*
    page.tsx          # /dashboard
    settings/
      page.tsx        # /dashboard/settings
  api/
    health/
      route.ts        # GET /api/health   endpoint HTTP, sin UI
  (marketing)/        # grupo de rutas: organiza sin afectar a la URL
    about/
      page.tsx        # /about
```

Los archivos reservados, en una frase cada uno:

| Archivo | Qué es |
|---|---|
| `page.tsx` | la UI única de una ruta; la que la hace pública |
| `layout.tsx` | UI compartida que **no se vuelve a montar** al navegar entre sus hijos (menú, barra lateral) |
| `template.tsx` | como `layout`, pero se monta de nuevo en cada navegación (útil para animaciones de entrada) |
| `loading.tsx` | Suspense automático: Next lo muestra mientras el `page.tsx` del mismo nivel espera datos |
| `error.tsx` | captura errores de render del segmento y sus hijos; recibe `error` y `reset()` |
| `not-found.tsx` | respuesta a `notFound()` desde cualquier componente del segmento |
| `route.ts` | handler HTTP (`GET`, `POST`…); no puede convivir con `page.tsx` en la misma carpeta |
| `default.tsx` | fallback de una *parallel route* (lo verás cuando uses carpetas `@slot`) |

Convenciones de nombre de carpeta:

- `[id]`: segmento dinámico. `[...slug]` captura varios niveles; `[[...slug]]` también la ruta vacía.
- `(grupo)`: agrupa carpetas sin añadir segmento a la URL. Sirve para tener dos layouts raíz distintos (`(marketing)/layout.tsx` y `(app)/layout.tsx`).
- `_private` (guion bajo): la carpeta queda fuera del enrutado; útil para colocar componentes junto a la ruta que los usa.

Lo que cambia respecto a React Router:

1. **Colocación.** Puedes poner `components/`, `utils.ts` o tests dentro de `app/products/`: solo `page.tsx` y los nombres reservados tienen significado. No hace falta separar «rutas» de «componentes» en carpetas distintas.
2. **Todo es Server Component por defecto.** Un `page.tsx` puede ser `async` y hacer `await db.query()` directamente. Para usar `useState` o eventos necesitas poner `"use client"` al principio del archivo.
3. **No hay `<Outlet>`.** Un layout recibe `children` y los pinta; el anidamiento es la jerarquía de carpetas.

El layout raíz mínimo:

```tsx
// app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Mi tienda" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
```

Comprobación rápida: crea `app/products/page.tsx` que exporte por defecto un componente, arranca `npm run dev` y abre `/products`. Si ves la página, has entendido el 80 % del enrutado; el 20 % restante son `loading`, `error` y los segmentos dinámicos.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "No tengo claro cuándo un componente debe ser Server Component y cuándo Client Component en Next 15. ¿Hay una regla? Y si un Client Component necesita contener uno de servidor, ¿se puede?",
            },
            {
                "role": "assistant",
                "content": r"""La regla: **Server Component por defecto; `"use client"` solo cuando el componente necesita algo que únicamente existe en el navegador**. La decisión se toma por capacidades, no por «página» o «componente».

| Necesita… | Tipo |
|---|---|
| Leer base de datos, archivos, secretos, `await` de datos | Server |
| `useState`, `useEffect`, `useRef`, cualquier hook con estado | Client |
| `onClick`, `onChange`, eventos del usuario | Client |
| `window`, `localStorage`, APIs del navegador | Client |
| Solo recibir props y pintar HTML | Server (o cualquiera; sin directiva, hereda del padre) |

Ventajas de dejar todo lo posible en servidor: el código de datos no viaja al navegador (ni las dependencias pesadas, ni las claves), y el HTML llega ya renderizado.

`"use client"` marca una **frontera**, no un componente aislado: todo lo que ese archivo importe pasa a ser parte del bundle del cliente. Por eso la directiva se pone lo más abajo posible del árbol, en la hoja interactiva, no en la página entera.

```tsx
// app/products/page.tsx — Server Component: accede a la BD sin API intermedia
import { db } from "@/lib/db";
import { AddToCartButton } from "./add-to-cart-button";

export default async function ProductsPage() {
  const products = await db.product.findMany();
  return (
    <ul>
      {products.map((p) => (
        <li key={p.id}>
          {p.name} — {p.price} €
          <AddToCartButton productId={p.id} />
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// app/products/add-to-cart-button.tsx — Client Component: solo la parte interactiva
"use client";

import { useState } from "react";

export function AddToCartButton({ productId }: { productId: string }) {
  const [added, setAdded] = useState(false);
  return (
    <button onClick={() => setAdded(true)} disabled={added}>
      {added ? "Añadido" : "Añadir"}
    </button>
  );
}
```

Las props que cruzan la frontera deben ser **serializables**: objetos planos, arrays, fechas, no funciones ni instancias de clase. Si pasas `onSave={() => …}` desde un Server Component a uno de cliente, Next falla con `Functions cannot be passed directly to Client Components`. La excepción son las Server Actions (`"use server"`), que sí se pueden pasar como props.

**Un Client Component sí puede contener Server Components, pero no importarlos.** Si `Sidebar` (cliente) importa `UserPanel` (servidor), `UserPanel` se convierte en componente de cliente y su `await db` deja de compilar. La solución es pasarlo como `children` desde un Server Component:

```tsx
// app/dashboard/sidebar.tsx
"use client";
import { useState } from "react";

export function Sidebar({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <aside data-open={open}>
      <button onClick={() => setOpen((o) => !o)}>Menú</button>
      {open && children}
    </aside>
  );
}
```

```tsx
// app/dashboard/layout.tsx — Server Component
import { Sidebar } from "./sidebar";
import { UserPanel } from "./user-panel"; // async, lee la BD

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Sidebar>
        <UserPanel />
      </Sidebar>
      <main>{children}</main>
    </>
  );
}
```

`UserPanel` se renderiza en el servidor y su resultado (no su código) llega a `Sidebar` como un «hueco» ya resuelto. El Client Component decide dónde y si lo muestra, pero nunca ejecuta su código.

Verificación de que la frontera está donde crees: ejecuta `npm run build`. En el resumen, el tamaño «First Load JS» de `/products` debe ser pequeño; si la página entera fuera cliente, verías el cliente de la BD intentando compilarse para el navegador (`Module not found: Can't resolve 'fs'`).""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Me sale esto al arrancar y no entiendo qué quiere:

```
Error: ×  You're importing a component that needs `useState`. This React hook only works in a client component. To fix, mark the file (or its parent) with the "use client" directive.
   ╭─[./app/products/filters.tsx:1:1]
 1 │ import { useState } from "react";
```

Es un componente de filtros normal, con un useState para el texto de búsqueda.""",
            },
            {
                "role": "assistant",
                "content": r"""El archivo `filters.tsx` es un Server Component (todo lo es por defecto en `app/`), y los Server Components no tienen estado: se ejecutan una vez en el servidor y producen HTML. `useState` solo existe en el cliente.

Arreglo: la primera línea del archivo debe ser la directiva.

```tsx
// app/products/filters.tsx
"use client";

import { useState } from "react";

export function Filters({ onChange }: { onChange: (query: string) => void }) {
  const [query, setQuery] = useState("");
  return (
    <input
      value={query}
      onChange={(e) => {
        setQuery(e.target.value);
        onChange(e.target.value);
      }}
      placeholder="Buscar"
    />
  );
}
```

Dos detalles sobre la directiva:

- Va **antes de cualquier import**, como cadena literal con comillas. Un comentario encima es válido; un `import` encima la invalida en silencio.
- Marca ese archivo y **todo lo que importe** como código de cliente. Por eso se pone en el componente de filtros, no en `page.tsx`: así la página sigue siendo de servidor y puede leer la base de datos.

El mensaje dice «or its parent» porque, si el padre ya es Client Component, los hijos que importa heredan la frontera y no necesitan la directiva. Pero no la pongas en el padre solo por eso: cuanta menos superficie de cliente, mejor.""",
            },
            {
                "role": "user",
                "content": "Ya compila, pero ahora la página que lo usa me da `Functions cannot be passed directly to Client Components unless you explicitly expose it by marking it with \"use server\"`. La página le pasa el `onChange` para filtrar la lista.",
            },
            {
                "role": "assistant",
                "content": r"""Ese es el segundo límite de la frontera: la página es un Server Component y el `onChange` que le pasa a `Filters` es una función. Las props que cruzan de servidor a cliente viajan serializadas, y una función no se puede serializar.

Hay dos diseños correctos; cuál elegir depende de dónde quieras filtrar.

**Opción A: filtrar en el servidor con la URL como estado.** El input escribe en `?q=`, la página lee `searchParams` y consulta la BD con el filtro. Es la forma idiomática del App Router: el filtro es compartible, sobrevive a la recarga y la página sigue siendo de servidor.

```tsx
// app/products/filters.tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";

export function Filters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  return (
    <input
      defaultValue={searchParams.get("q") ?? ""}
      onChange={(e) => {
        const params = new URLSearchParams(searchParams);
        if (e.target.value) params.set("q", e.target.value);
        else params.delete("q");
        router.replace(`/products?${params.toString()}`);
      }}
      placeholder="Buscar"
    />
  );
}
```

```tsx
// app/products/page.tsx
import { db } from "@/lib/db";
import { Filters } from "./filters";

export default async function ProductsPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const products = await db.product.findMany({ where: { name: { contains: q } } });
  return (
    <>
      <Filters />
      <ul>{products.map((p) => <li key={p.id}>{p.name}</li>)}</ul>
    </>
  );
}
```

En Next 15 `searchParams` es una promesa: hay que hacer `await`. Para no lanzar una navegación por tecla, aplica un debounce al `router.replace` (unos 300 ms).

**Opción B: filtrar en el cliente.** Si la lista es pequeña y ya está cargada, el estado del filtro y la lista filtrada viven juntos en un Client Component que recibe los datos como prop:

```tsx
// app/products/product-browser.tsx
"use client";

import { useState } from "react";

type Product = { id: string; name: string };

export function ProductBrowser({ products }: { products: Product[] }) {
  const [query, setQuery] = useState("");
  const visible = products.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()));
  return (
    <>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar" />
      <ul>{visible.map((p) => <li key={p.id}>{p.name}</li>)}</ul>
    </>
  );
}
```

Y la página de servidor hace `const products = await db.product.findMany(); return <ProductBrowser products={products} />;`. El `onChange` ya no cruza ninguna frontera porque vive dentro del componente de cliente.

Criterio: A si la lista puede ser grande o el filtro debe ir en la URL; B si son pocas decenas de elementos y quieres respuesta instantánea sin ir al servidor. En ambos casos la regla que has aprendido con el error se mantiene: **la función y el estado que la usa viven en el mismo lado de la frontera**.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Por qué mi `layout.tsx` de `/dashboard` no se vuelve a ejecutar cuando navego entre `/dashboard/users` y `/dashboard/billing`? Tengo ahí un `await getCurrentUser()` y quiero que se refresque.",
            },
            {
                "role": "assistant",
                "content": r"""Porque esa es la definición de layout: **se renderiza una vez y persiste** mientras navegas entre sus hijos. Next no vuelve a ejecutar `DashboardLayout` al pasar de `users` a `billing`; solo renderiza el `page.tsx` que cambia. Es lo que permite que la barra lateral conserve su scroll y su estado, y lo que hace rápidas las navegaciones.

Tienes tres opciones según qué signifique «refrescar»:

**1. Si el usuario puede cambiar durante la sesión (login, cambio de plan), fuerza el refresco cuando ocurra el cambio**, no en cada navegación. Después de la acción que lo modifica, llama a `revalidatePath` o `router.refresh()`:

```tsx
// app/actions.ts
"use server";

import { revalidatePath } from "next/cache";

export async function upgradePlan(planId: string) {
  await db.user.update({ where: { id: await currentUserId() }, data: { planId } });
  revalidatePath("/dashboard", "layout"); // vuelve a renderizar el layout y todas sus páginas
}
```

Con `"layout"` como segundo argumento se invalida el layout y todo lo que cuelga de él. Es el enfoque correcto: el dato cambia pocas veces y se refresca exactamente entonces.

**2. Si de verdad quieres ejecutar código en cada navegación**, usa `template.tsx` en lugar de `layout.tsx`. Un template se monta de nuevo con cada hijo:

```tsx
// app/dashboard/template.tsx
export default async function DashboardTemplate({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser(); // se ejecuta en cada navegación
  return (
    <>
      <p>Plan: {user.plan}</p>
      {children}
    </>
  );
}
```

El coste: pierdes la persistencia (estado de componentes cliente, scroll, animaciones no se conservan). Casi nunca compensa solo por un dato de usuario.

**3. Mueve el dato al nivel que cambia.** Si `getCurrentUser()` lo necesita cada página, llámalo en cada `page.tsx`. No hay doble consulta: dentro de una misma petición, Next deduplica `fetch` con la misma URL, y para consultas a la BD envuelves la función en `cache` de React:

```ts
// lib/current-user.ts
import { cache } from "react";

export const getCurrentUser = cache(async () => {
  const session = await getSession();
  return db.user.findUniqueOrThrow({ where: { id: session.userId } });
});
```

Layout y página pueden llamar a `getCurrentUser()` y la consulta se ejecuta una vez por petición.

Lo que no te preocupe: una **recarga completa** o entrar al dashboard desde fuera sí ejecuta el layout. El comportamiento que ves es solo en navegación cliente entre hermanos.

Para verificar cuál opción tienes activa, pon un `console.log("layout render")` en el layout y mira la terminal del servidor mientras navegas: con layout no aparece; con template aparece en cada clic; con `revalidatePath` aparece solo tras la acción.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo funcionan exactamente `loading.tsx`, `error.tsx` y `not-found.tsx`? Puse un `error.tsx` en `app/` y cuando el layout raíz lanza no lo captura.",
            },
            {
                "role": "assistant",
                "content": r"""Los tres son componentes que Next envuelve automáticamente alrededor del `page.tsx` **del mismo segmento**. La jerarquía que construye por cada carpeta es:

```
<Layout>
  <ErrorBoundary fallback={<Error />}>        ← error.tsx
    <Suspense fallback={<Loading />}>         ← loading.tsx
      <NotFoundBoundary fallback={<NotFound />}>   ← not-found.tsx
        <Page />
```

Fíjate en que **el `ErrorBoundary` está dentro del `Layout`**. Por eso tu `app/error.tsx` no captura un error del layout raíz: el boundary es hijo del layout, no padre. Un `error.tsx` captura errores de la página y de los layouts *anidados por debajo*, nunca del layout de su propio nivel.

Para el layout raíz existe `app/global-error.tsx`, que sustituye a todo, incluido `<html>`:

```tsx
// app/global-error.tsx
"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="es">
      <body>
        <h1>Algo ha fallado</h1>
        <button onClick={reset}>Reintentar</button>
      </body>
    </html>
  );
}
```

Como reemplaza al layout raíz, debe declarar `<html>` y `<body>`, y solo se activa en producción (en desarrollo verás el overlay de Next).

**`error.tsx`** de un segmento normal:

```tsx
// app/dashboard/error.tsx
"use client"; // obligatorio: un error boundary necesita estado

import { useEffect } from "react";

export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    reportError(error); // envíalo a tu monitorización; en producción el mensaje llega ofuscado
  }, [error]);

  return (
    <section role="alert">
      <h2>No se pudo cargar el panel</h2>
      <button onClick={reset}>Reintentar</button>
    </section>
  );
}
```

`reset()` vuelve a renderizar el segmento; si el fallo era transitorio (red), se recupera sin recargar. En producción, `error.message` de un Server Component se sustituye por un texto genérico y un `digest` que correlaciona con el log del servidor; no esperes ver el mensaje real en el cliente.

**`loading.tsx`** es un `<Suspense>` con ese fallback alrededor de la página. Se muestra mientras la página hace `await` de datos y, con streaming, el layout llega al navegador antes de que la página termine. Si quieres granularidad (que una tabla lenta no bloquee el resto), usa `<Suspense>` manual dentro de la página además de o en lugar de `loading.tsx`.

**`not-found.tsx`** responde a dos cosas: llamadas explícitas a `notFound()` y URLs que no coinciden con ninguna ruta (solo el de `app/`). Úsalo cuando el recurso no existe:

```tsx
// app/products/[id]/page.tsx
import { notFound } from "next/navigation";

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = await db.product.findUnique({ where: { id } });
  if (!product) notFound(); // lanza; Next renderiza el not-found.tsx más cercano con status 404
  return <h1>{product.name}</h1>;
}
```

`notFound()` lanza una excepción interna, así que no lo envuelvas en `try/catch` ni escribas código después de él esperando que se ejecute.

Resumen de alcances:

| Archivo | Captura / cubre | No cubre |
|---|---|---|
| `error.tsx` | página y segmentos hijos | el layout de su mismo nivel |
| `global-error.tsx` | layout raíz | nada más (es el último recurso) |
| `loading.tsx` | la página del segmento | layouts (se renderizan antes) |
| `not-found.tsx` | `notFound()` en el segmento; 404 global si está en `app/` | errores que no sean «no existe» |

Prueba para confirmar la jerarquía: lanza `throw new Error("x")` en `app/dashboard/page.tsx` y verás `app/dashboard/error.tsx`; muévelo a `app/dashboard/layout.tsx` y verás el `error.tsx` del nivel superior (`app/error.tsx`), no el del dashboard.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Responde en español con código TypeScript completo y explica el porqué de cada decisión."},
            {
                "role": "user",
                "content": "Quiero un formulario de «crear entrada de blog» con Server Actions en Next 15: validación con zod, errores por campo, estado de envío, y que al guardar la lista de entradas se actualice y redirija a la nueva. ¿Cómo lo haces bien?",
            },
            {
                "role": "assistant",
                "content": r"""La estructura: una acción `"use server"` que valida y devuelve los errores como datos, un formulario cliente con `useActionState` para mostrarlos, y `revalidatePath` + `redirect` al final de la acción.

```ts
// app/posts/actions.ts
"use server";

import { z } from "zod";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import { getSession } from "@/lib/session";

const PostSchema = z.object({
  title: z.string().trim().min(3, "Mínimo 3 caracteres").max(120, "Máximo 120"),
  body: z.string().trim().min(20, "Escribe al menos 20 caracteres"),
});

export type CreatePostState = {
  errors?: { title?: string[]; body?: string[]; form?: string[] };
  values?: { title: string; body: string };
};

export async function createPost(_prev: CreatePostState, formData: FormData): Promise<CreatePostState> {
  const session = await getSession();
  if (!session) return { errors: { form: ["Inicia sesión para publicar"] } };

  const values = { title: String(formData.get("title") ?? ""), body: String(formData.get("body") ?? "") };
  const parsed = PostSchema.safeParse(values);
  if (!parsed.success) {
    // Devolvemos los valores para que el formulario no se vacíe al mostrar errores
    return { errors: parsed.error.flatten().fieldErrors, values };
  }

  let post;
  try {
    post = await db.post.create({ data: { ...parsed.data, authorId: session.userId } });
  } catch {
    return { errors: { form: ["No se pudo guardar. Inténtalo de nuevo."] }, values };
  }

  revalidatePath("/posts"); // la lista se regenera en la próxima visita
  redirect(`/posts/${post.id}`); // fuera del try/catch: redirect lanza internamente
}
```

```tsx
// app/posts/new/post-form.tsx
"use client";

import { useActionState } from "react";
import { createPost, type CreatePostState } from "../actions";

const initialState: CreatePostState = {};

export function PostForm() {
  const [state, formAction, isPending] = useActionState(createPost, initialState);

  return (
    <form action={formAction}>
      <label>
        Título
        <input name="title" defaultValue={state.values?.title} aria-invalid={!!state.errors?.title} required />
      </label>
      {state.errors?.title && <p role="alert">{state.errors.title[0]}</p>}

      <label>
        Contenido
        <textarea name="body" defaultValue={state.values?.body} aria-invalid={!!state.errors?.body} required />
      </label>
      {state.errors?.body && <p role="alert">{state.errors.body[0]}</p>}

      {state.errors?.form && <p role="alert">{state.errors.form[0]}</p>}

      <button type="submit" disabled={isPending}>
        {isPending ? "Publicando…" : "Publicar"}
      </button>
    </form>
  );
}
```

```tsx
// app/posts/new/page.tsx — Server Component que solo compone
import { PostForm } from "./post-form";

export default function NewPostPage() {
  return (
    <main>
      <h1>Nueva entrada</h1>
      <PostForm />
    </main>
  );
}
```

Las decisiones:

- **La acción valida siempre**, aunque el HTML tenga `required`. Una Server Action es un endpoint POST público: cualquiera puede llamarla con `curl` saltándose el formulario. Lo mismo con la sesión: se comprueba **dentro** de la acción, no en la página que la muestra.
- **Errores como valor de retorno, no como excepción.** `useActionState` recibe lo que la acción devuelve; eso permite pintar errores por campo sin un error boundary. Las excepciones quedan para fallos imprevistos.
- **`redirect` fuera del `try/catch`.** `redirect()` funciona lanzando una excepción especial (`NEXT_REDIRECT`); si lo metes en el `try`, tu `catch` lo captura y la redirección no ocurre. Es el error más común con Server Actions.
- **`revalidatePath("/posts")` antes de redirigir** invalida la caché de la lista. Sin esto, `/posts` seguiría mostrando la versión anterior si estaba cacheada o prerenderizada.
- **`defaultValue={state.values?.title}`**: tras un error, React 19 reinicia los formularios no controlados; devolver los valores desde la acción evita que el usuario pierda lo escrito.
- **`useActionState` da `isPending`** sin que gestiones un `useState`. El botón se desactiva y, si el usuario envía dos veces, las acciones se encolan en orden en lugar de competir.

Verificación: envía el formulario vacío desde el navegador con `required` quitado en DevTools y comprueba que la acción devuelve los errores de zod. Luego, con sesión válida, publica y confirma que aterrizas en `/posts/<id>` y que `/posts` muestra la entrada nueva sin recargar a mano.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de Next 13/14 y en 15 mis páginas con `fetch` se han vuelto dinámicas: cada petición vuelve a pegar a la API. ¿Qué ha cambiado y cómo controlo la caché ahora?",
            },
            {
                "role": "assistant",
                "content": r"""Cambió el valor por defecto: en Next 15 **`fetch` ya no se cachea salvo que lo pidas**. En 13/14 era al revés (`force-cache` implícito) y provocaba datos obsoletos sin que nadie lo hubiera configurado. Ahora la caché es *opt-in* y explícita.

Las tres formas de `fetch` en un Server Component:

```ts
// 1. Sin caché (el comportamiento por defecto en 15): se pide en cada petición
const live = await fetch("https://api.example.com/prices");

// 2. Caché persistente hasta que la invalides a mano
const cached = await fetch("https://api.example.com/catalog", { cache: "force-cache" });

// 3. Caché con caducidad (ISR a nivel de fetch) y etiquetas para invalidar bajo demanda
const posts = await fetch("https://api.example.com/posts", {
  next: { revalidate: 3600, tags: ["posts"] },
});
```

`{ cache: "no-store" }` sigue existiendo y ahora equivale al valor por defecto; sirve para dejar la intención escrita.

Lo que sigue igual: dentro de **una misma petición**, dos `fetch` idénticos (misma URL y opciones) se deduplican, aunque uno esté en el layout y otro en la página. Es memoización por petición, no caché entre peticiones.

Dos cambios relacionados que te afectan:

- **Los Route Handlers `GET` tampoco se cachean por defecto.** Si quieres que uno sea estático, `export const dynamic = "force-static"` en el `route.ts`.
- **El Router Cache del cliente** ya no reutiliza páginas dinámicas al volver atrás: `staleTimes.dynamic` es 0. Puedes subirlo en `next.config.ts` con `experimental: { staleTimes: { dynamic: 30 } }` si echas de menos la navegación instantánea.

Cómo controlar la página entera en lugar de cada `fetch`:

```ts
// app/posts/page.tsx
export const revalidate = 3600; // toda la página se regenera como máximo cada hora
```

O `export const dynamic = "force-dynamic"` para lo contrario. Y si no usas `fetch` sino un cliente de BD, la caché de `fetch` no aplica: usa `unstable_cache` para persistir el resultado de una función con las mismas opciones:

```ts
import { unstable_cache } from "next/cache";

export const getPosts = unstable_cache(() => db.post.findMany(), ["posts"], {
  revalidate: 3600,
  tags: ["posts"],
});
```

Para ver qué está pasando sin adivinar: en `next.config.ts` activa `logging: { fetches: { fullUrl: true } }` y en desarrollo cada `fetch` aparece en la terminal con `(cache hit)` o `(cache skip)` y el motivo.""",
            },
            {
                "role": "user",
                "content": "Vale. Entonces si cacheo los posts con `tags: [\"posts\"]`, ¿cómo invalido justo cuando alguien publica uno nuevo, sin esperar la hora?",
            },
            {
                "role": "assistant",
                "content": r"""Con `revalidateTag("posts")` en el sitio donde ocurre la escritura. La próxima petición a cualquier página o `fetch` etiquetado con `posts` vuelve a generarse.

Desde una Server Action, que es el caso habitual:

```ts
// app/posts/actions.ts
"use server";

import { revalidateTag } from "next/cache";

export async function publishPost(formData: FormData) {
  await db.post.create({ data: { title: String(formData.get("title")) } });
  revalidateTag("posts"); // invalida todos los fetch y unstable_cache con esa etiqueta
}
```

Cuando la escritura ocurre **fuera** de Next (un CMS, un cron, otro servicio), expón un Route Handler protegido con un secreto y que el sistema externo lo llame vía webhook:

```ts
// app/api/revalidate/route.ts
import { revalidateTag } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const secret = request.headers.get("x-revalidate-secret");
  if (secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { tag } = (await request.json()) as { tag?: string };
  if (!tag) return NextResponse.json({ error: "tag required" }, { status: 400 });

  revalidateTag(tag);
  return NextResponse.json({ revalidated: true, tag, at: Date.now() });
}
```

Diferencias con `revalidatePath`:

| | `revalidateTag("posts")` | `revalidatePath("/posts")` |
|---|---|---|
| Invalida | todo dato etiquetado, esté en la página que esté | las entradas de caché de esa ruta |
| Sirve para | un dato que aparece en varias páginas (lista, portada, sidebar) | una URL concreta |
| Rutas dinámicas | no necesita conocerlas | `revalidatePath("/posts/[id]", "page")` para todas las instancias |

Para un blog, la etiqueta es mejor: el post nuevo aparece en `/`, `/posts` y el feed sin enumerar rutas.

Dos matices:

- La invalidación es **perezosa**: marca la caché como obsoleta y la siguiente petición regenera. Nadie paga el coste hasta que alguien visita.
- Si la acción se ejecuta desde un formulario, Next además refresca el Router Cache del cliente que la llamó; el usuario que publica ve el cambio al instante sin `router.refresh()`.

Prueba: con `logging.fetches` activado, visita `/posts` (debe decir `cache hit`), ejecuta la acción o el webhook, vuelve a visitar y debe aparecer `cache skip` seguido de un nuevo `hit` en la siguiente carga.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Acabo de actualizar a Next 15 y una página dinámica no compila:

```
Type error: Type '{ params: { slug: string; }; }' does not satisfy the constraint 'PageProps'.
  Types of property 'params' are incompatible.
    Type '{ slug: string; }' is missing the following properties from type 'Promise<any>': then, catch, finally, [Symbol.toStringTag]
```

```tsx
export default async function PostPage({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);
  return <h1>{post.title}</h1>;
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""En Next 15 `params` (y `searchParams`) pasaron a ser **promesas**. El tipo que declaras ya no coincide con lo que Next entrega, y además en tiempo de ejecución `params.slug` sería `undefined`.

Arreglo mínimo:

```tsx
// app/posts/[slug]/page.tsx
type Props = { params: Promise<{ slug: string }> };

export default async function PostPage({ params }: Props) {
  const { slug } = await params;
  const post = await getPost(slug);
  return <h1>{post.title}</h1>;
}
```

El motivo del cambio: hacer que las APIs que dependen de la petición (`params`, `searchParams`, `cookies()`, `headers()`) sean asíncronas permite a Next prerenderizar todo lo que *no* depende de ellas antes de que llegue la petición. Es la base del renderizado parcial y del streaming.

El mismo patrón aplica en todos los sitios donde recibías `params`:

```tsx
// generateMetadata
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  return { title: (await getPost(slug)).title };
}

// Route Handler
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return Response.json(await getPost(slug));
}

// Layout
export default async function PostLayout({ children, params }: { children: React.ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <section data-post={slug}>{children}</section>;
}
```

En un **Client Component**, que no puede ser `async`, se desenvuelve con `use`:

```tsx
"use client";
import { use } from "react";

export default function ClientPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  return <p>{slug}</p>;
}
```

Aunque para leer el segmento en cliente suele ser más simple `useParams()` de `next/navigation`.

Si tienes muchos archivos, no los edites a mano: el codemod oficial hace exactamente este cambio en todo el proyecto, incluidos `cookies()` y `headers()`:

```
npx @next/codemod@canary next-async-request-api .
```

Durante la 15, el acceso síncrono sigue funcionando con un aviso en consola (`params should be awaited before using its properties`) para facilitar la migración, pero el tipado ya exige la promesa y el acceso síncrono desaparece en la 16. Haz el cambio ahora.

Comprobación: `npx tsc --noEmit` limpio y la página muestra el título; si ves `Cannot read properties of undefined (reading 'title')`, es que algún `params.slug` sin `await` quedó por ahí.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito un endpoint `GET /api/orders?status=paid` y `POST /api/orders` en el App Router para que lo consuma una app móvil. ¿Cómo se hace un Route Handler bien, con validación y códigos de estado correctos?",
            },
            {
                "role": "assistant",
                "content": r"""Un Route Handler es un archivo `route.ts` que exporta funciones con el nombre del método HTTP. Reciben un `Request` estándar (o `NextRequest`, que añade `nextUrl` y `cookies`) y devuelven un `Response`.

```ts
// app/api/orders/route.ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";
import { verifyApiToken } from "@/lib/auth";

const StatusSchema = z.enum(["pending", "paid", "shipped"]);

const CreateOrderSchema = z.object({
  customerId: z.string().uuid(),
  items: z.array(z.object({ sku: z.string().min(1), qty: z.number().int().positive() })).min(1),
});

export async function GET(request: NextRequest) {
  const user = await verifyApiToken(request.headers.get("authorization"));
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const rawStatus = request.nextUrl.searchParams.get("status");
  const status = rawStatus ? StatusSchema.safeParse(rawStatus) : null;
  if (status && !status.success) {
    return NextResponse.json({ error: "invalid status" }, { status: 400 });
  }

  const orders = await db.order.findMany({
    where: { customerId: user.id, ...(status ? { status: status.data } : {}) },
    orderBy: { createdAt: "desc" },
    take: 50,
  });
  return NextResponse.json(orders);
}

export async function POST(request: NextRequest) {
  const user = await verifyApiToken(request.headers.get("authorization"));
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }

  const parsed = CreateOrderSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "validation", details: parsed.error.flatten() }, { status: 422 });
  }

  const order = await db.order.create({ data: { ...parsed.data, status: "pending" } });
  return NextResponse.json(order, { status: 201, headers: { Location: `/api/orders/${order.id}` } });
}
```

Y la ruta con parámetro:

```ts
// app/api/orders/[id]/route.ts
import { NextResponse } from "next/server";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const order = await db.order.findUnique({ where: { id } });
  if (!order) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(order);
}
```

Decisiones:

- **`request.json()` dentro de `try`**: un cuerpo malformado lanza, y sin el `try` responderías 500 a lo que es un 400 del cliente.
- **400 vs 422**: 400 para petición malformada (JSON roto, parámetro inválido), 422 para JSON válido que no pasa la validación de negocio. La app móvil puede distinguir «arregla tu petición» de «muestra estos errores de campo».
- **201 + `Location`** en la creación, que es lo que un cliente HTTP espera.
- **Autenticación en cada handler.** Un Route Handler es público por defecto; no hay guardas implícitas. Si todos los handlers de `/api` deben estar protegidos, centralízalo en `middleware.ts` con un `matcher: ["/api/:path*"]`, pero sigue comprobando el usuario aquí para tener su `id`.
- **Sin caché**: en Next 15 un `GET` es dinámico por defecto, que es lo que quieres para datos de usuario. Para un endpoint estático (catálogo público) añade `export const dynamic = "force-static"` y `export const revalidate = 3600`.

Lo que no soporta un Route Handler y suele sorprender: no puede convivir con un `page.tsx` en la misma carpeta, y los métodos que no exportes responden `405 Method Not Allowed` automáticamente (no hace falta escribirlo).

Prueba manual:

```
curl -s -X POST localhost:3000/api/orders -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"customerId":"no-es-uuid","items":[]}' -i
```

Debe responder `422` con `details.fieldErrors.customerId` y `details.fieldErrors.items`. Con un cuerpo válido, `201` y la cabecera `Location`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero que todo `/dashboard/*` redirija a `/login` si no hay sesión, y que `/login` redirija al dashboard si ya la hay. ¿Es trabajo del middleware? ¿Qué puedo y qué no puedo hacer ahí?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, es el caso de uso principal del middleware: una **comprobación barata antes de que la petición llegue a la ruta**. Se ejecuta para cada petición que coincida con `matcher`, en el runtime Edge, y decide si continuar, redirigir o reescribir.

```ts
// middleware.ts (en la raíz del proyecto, junto a app/)
import { NextResponse, type NextRequest } from "next/server";

const PROTECTED_PREFIX = "/dashboard";
const LOGIN_PATH = "/login";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get("session")?.value);

  if (pathname.startsWith(PROTECTED_PREFIX) && !hasSession) {
    const loginUrl = new URL(LOGIN_PATH, request.url);
    loginUrl.searchParams.set("next", pathname); // para volver tras el login
    return NextResponse.redirect(loginUrl);
  }

  if (pathname === LOGIN_PATH && hasSession) {
    return NextResponse.redirect(new URL(PROTECTED_PREFIX, request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Evita ejecutar el middleware para estáticos, imágenes y el favicon
  matcher: ["/dashboard/:path*", "/login"],
};
```

Qué está haciendo y por qué así:

- **Solo mira si la cookie existe.** No la verifica contra la base de datos ni descifra un JWT costoso. Es una comprobación *optimista*: suficiente para no mostrar el dashboard a un anónimo, insuficiente como única barrera de seguridad.
- **El `matcher` limita** las rutas; sin él, el middleware corre también para `/_next/static/*` y cada imagen, y cada ejecución cuesta.
- **`new URL(path, request.url)`** construye la redirección con el host correcto; una cadena relativa falla en `NextResponse.redirect`.

Lo que **no** debe hacer el middleware, y dónde va cada cosa:

| Tarea | ¿En middleware? | Dónde entonces |
|---|---|---|
| Comprobar que existe la cookie | sí | aquí |
| Verificar la sesión en la BD / comprobar roles | no | en el layout o la página del dashboard, con `cookies()` y tu `getSession()` |
| Leer o escribir en la base de datos | no (Edge, sin Node, conexiones costosas) | Server Components, Server Actions, Route Handlers |
| Rate limiting, cabeceras de seguridad, reescritura por país | sí | aquí |
| Lógica de negocio | no | donde viva el dato |

La verificación real, en el layout protegido:

```tsx
// app/dashboard/layout.tsx
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession(); // lee cookies(), verifica firma, consulta la BD si hace falta
  if (!session) redirect("/login");
  return <>{children}</>;
}
```

Con las dos capas tienes lo mejor de cada una: el middleware evita renderizar nada para anónimos, y el layout garantiza que una cookie falsa o caducada no pase. Y las Server Actions que mutan datos comprueban la sesión por su cuenta, porque se pueden invocar sin pasar por ninguna página.

Dos limitaciones del runtime Edge que conviene saber: no hay APIs de Node (`fs`, `crypto` nativo con todo; sí Web Crypto), y las librerías que las usan no cargan. Si necesitas lógica de Node en esta capa, Next 15.2+ ofrece el runtime Node para middleware de forma experimental (`experimental.nodeMiddleware`), y en Next 16 el archivo pasa a llamarse `proxy.ts` con Node por defecto; en 15 sigue siendo `middleware.ts`.

Prueba: sin cookie, `curl -I localhost:3000/dashboard` debe devolver `307` con `location: /login?next=%2Fdashboard`; con `-H "Cookie: session=x"`, `200`. Luego borra la cookie en el navegador estando en `/dashboard/settings`, recarga, y comprueba que vuelves a `/login` con el `next` correcto.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 11-20: metadata/SEO, next/image (multiturno), fuentes, streaming con Suspense, parallel/intercepting (EN),
#        variables de entorno, autenticación con cookies, Docker standalone (multiturno), hydration mismatch,
#        importar código de servidor en cliente
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cómo gestiono el SEO en el App Router? Necesito título y descripción por página de producto, Open Graph con la imagen del producto, canonical, y un sitemap. Ahora tengo un `<Head>` de Pages Router que ya no funciona.",
            },
            {
                "role": "assistant",
                "content": r"""En el App Router los metadatos son **datos exportados**, no JSX: `metadata` para valores estáticos y `generateMetadata` cuando dependen de la ruta. Next los fusiona de layout a página y genera el `<head>`.

Base en el layout raíz, con las partes que heredan todas las páginas:

```tsx
// app/layout.tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  metadataBase: new URL("https://tienda.example"), // resuelve URLs relativas de OG, canonical, etc.
  title: { default: "Tienda", template: "%s | Tienda" },
  description: "Muebles de diseño con envío en 48 h.",
  openGraph: { type: "website", locale: "es_ES", siteName: "Tienda" },
  robots: { index: true, follow: true },
};
```

Metadatos dinámicos en la página de producto:

```tsx
// app/products/[slug]/page.tsx
import type { Metadata, ResolvingMetadata } from "next";
import { notFound } from "next/navigation";
import { getProductBySlug } from "@/lib/products"; // envuelta en cache() de React

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props, parent: ResolvingMetadata): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) return { title: "Producto no encontrado" };

  const parentImages = (await parent).openGraph?.images ?? [];
  return {
    title: product.name, // el template del layout lo convierte en "Silla Nórdica | Tienda"
    description: product.summary,
    alternates: { canonical: `/products/${product.slug}` },
    openGraph: {
      title: product.name,
      description: product.summary,
      images: [{ url: product.imageUrl, width: 1200, height: 630, alt: product.name }, ...parentImages],
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) notFound();
  return <h1>{product.name}</h1>;
}
```

`generateMetadata` y la página llaman las dos a `getProductBySlug`. Para que solo haya una consulta, envuelve la función con `cache` de React (`export const getProductBySlug = cache(async (slug) => db.product.findUnique(…))`); si es un `fetch`, Next ya lo deduplica solo.

Sitemap y robots como archivos de ruta:

```ts
// app/sitemap.ts
import type { MetadataRoute } from "next";
import { db } from "@/lib/db";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const products = await db.product.findMany({ select: { slug: true, updatedAt: true } });
  return [
    { url: "https://tienda.example", lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    ...products.map((p) => ({
      url: `https://tienda.example/products/${p.slug}`,
      lastModified: p.updatedAt,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
  ];
}
```

```ts
// app/robots.ts
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/dashboard", "/api"] },
    sitemap: "https://tienda.example/sitemap.xml",
  };
}
```

Si no tienes una imagen OG por producto, `app/products/[slug]/opengraph-image.tsx` puede generarla con `ImageResponse` de `next/og` a partir del nombre y el precio; Next la enlaza automáticamente.

Por qué este modelo y no `<Head>`: los metadatos se resuelven en el servidor antes de enviar HTML, así que rastreadores y previsualizaciones de redes sociales los ven sin ejecutar JavaScript; con `<Head>` en componentes cliente eso no estaba garantizado. Y el `template` evita que cada página recuerde añadir el nombre del sitio.

Comprobación: `curl -s https://tienda.example/products/silla-nordica | grep -E "<title>|og:image|canonical"` debe mostrar las tres etiquetas con los valores del producto. Para el sitemap, `curl -s https://tienda.example/sitemap.xml | head` y comprueba que es XML válido con las URLs absolutas.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Al usar `<Image>` de Next me sale:

```
Error: Invalid src prop (https://cdn.example.com/p/silla.jpg) on `next/image`, hostname "cdn.example.com" is not configured under images in your `next.config.js`
```

¿Por qué tengo que configurar algo para mostrar una imagen? Con `<img>` funcionaba.""",
            },
            {
                "role": "assistant",
                "content": r"""Porque `<Image>` no muestra la imagen tal cual: la pasa por el **optimizador de Next** (`/_next/image?url=…&w=…&q=…`), que la descarga, la redimensiona y la sirve en WebP/AVIF. Un optimizador que acepte cualquier URL sería un proxy abierto que cualquiera podría usar para redimensionar imágenes ajenas a tu costa. Por eso exige una lista de orígenes permitidos.

```ts
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "cdn.example.com", pathname: "/p/**" },
    ],
  },
};

export default nextConfig;
```

`pathname: "/p/**"` restringe a esa carpeta; sin él, todo el host. Reinicia `next dev` tras cambiar la configuración.

El uso correcto del componente, que es lo otro que suele fallar:

```tsx
import Image from "next/image";

<Image
  src="https://cdn.example.com/p/silla.jpg"
  alt="Silla nórdica de roble"
  width={800}
  height={600}
  sizes="(max-width: 768px) 100vw, 50vw"
  priority
/>
```

- **`width` y `height`** son obligatorios: son el tamaño intrínseco, y con ellos Next reserva el espacio y evita el salto de layout (CLS). No tienen que ser el tamaño de pintado; el CSS puede escalar manteniendo la proporción.
- **`sizes`** le dice al navegador cuánto ocupará la imagen en cada ancho de pantalla, para que `srcset` elija el archivo más pequeño que sirva. Sin `sizes`, en móvil se descarga la versión grande.
- **`priority`** solo en la imagen principal visible al cargar (la del LCP): desactiva el lazy loading y añade `<link rel="preload">`. Si pones `priority` en todas, no priorizas nada.

Lo que ganas frente a `<img>`: tamaños por dispositivo, formatos modernos, lazy loading por defecto y cero CLS. Para una imagen de la carpeta `public/` basta con `src="/logo.png"` sin configuración.""",
            },
            {
                "role": "user",
                "content": "Ya va. Pero en el catálogo las fotos las suben los vendedores y no sé sus dimensiones de antemano. ¿Qué pongo en width/height?",
            },
            {
                "role": "assistant",
                "content": r"""Para imágenes de tamaño desconocido usa `fill`: la imagen rellena el contenedor y es el **contenedor** quien fija el tamaño. Así no necesitas `width`/`height`.

```tsx
import Image from "next/image";

export function ProductThumb({ src, alt }: { src: string; alt: string }) {
  return (
    <div style={{ position: "relative", aspectRatio: "4 / 3", width: "100%", overflow: "hidden" }}>
      <Image
        src={src}
        alt={alt}
        fill
        sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
        style={{ objectFit: "cover" }}
      />
    </div>
  );
}
```

Las tres condiciones para que `fill` funcione:

1. **El padre debe tener `position: relative`** (o `fixed`/`absolute`): `fill` pone la imagen en `position: absolute; inset: 0`, y sin un contenedor posicionado se sale al ancestro más cercano que lo esté, normalmente el `body`.
2. **El padre debe tener tamaño.** `aspect-ratio: 4 / 3` con `width: 100%` da una caja estable antes de que la imagen cargue; eso es lo que evita el salto de layout, igual que `width`/`height` en la variante anterior.
3. **`sizes` sigue siendo obligatorio** en la práctica: con `fill`, Next no puede deducir el ancho de pintado, y sin `sizes` asume `100vw` y descarga la imagen más grande para cada miniatura.

`objectFit: "cover"` recorta para llenar la caja sin deformar; `"contain"` muestra la imagen completa con bandas. Para un catálogo de miniaturas, `cover`; para una ficha donde importa ver el producto entero, `contain`.

Dos casos límite con imágenes subidas por usuarios:

- **SVG o GIF animado**: el optimizador no los procesa bien; añade `unoptimized` en esas imágenes (o valida el tipo al subir y conviértelas a JPEG/WebP en el servidor, que es mejor).
- **Muchos orígenes distintos**: si cada vendedor sube a un bucket distinto, no mantengas `remotePatterns` a mano. Sirve todas las imágenes desde un único CDN tuyo (un solo patrón) o define un `loader` propio que construya la URL de tu CDN con los parámetros de ancho y calidad.

Verificación: en DevTools, pestaña Network, filtra por `_next/image` y redimensiona la ventana. Deben pedirse variantes con `w=` distintos según el ancho, y ninguna miniatura debe superar el ancho real con el que se pinta.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo cargo fuentes (Inter de Google y una fuente propia en woff2) en Next 15 sin que la página parpadee al cargar y sin peticiones a Google? Uso Tailwind v4.",
            },
            {
                "role": "assistant",
                "content": r"""Con `next/font`: descarga la fuente en el **build**, la sirve desde tu dominio y genera una fuente de respaldo ajustada en métricas (`size-adjust`), lo que elimina el salto de texto. El navegador nunca contacta con Google.

```tsx
// app/layout.tsx
import { Inter } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const brand = localFont({
  src: [
    { path: "./fonts/Brand-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/Brand-Bold.woff2", weight: "700", style: "normal" },
  ],
  display: "swap",
  variable: "--font-brand",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${inter.variable} ${brand.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

Y en Tailwind v4 las fuentes se declaran en CSS, no en un `tailwind.config`:

```css
/* app/globals.css */
@import "tailwindcss";

@theme inline {
  --font-sans: var(--font-inter), ui-sans-serif, system-ui, sans-serif;
  --font-brand: var(--font-brand), var(--font-inter), sans-serif;
}
```

Con eso `font-sans` usa Inter y tienes una utilidad `font-brand` nueva. `@theme inline` hace que Tailwind use la variable tal cual en vez de copiar su valor, que es lo correcto para variables definidas por `next/font` en tiempo de ejecución.

Decisiones:

- **`variable` en vez de `className`**: aplicar la clase al `<html>` expone la variable CSS a todo el documento y deja que Tailwind o cualquier CSS la use. Con `inter.className` solo cambiarías la fuente del elemento donde la pongas.
- **`subsets: ["latin"]`** reduce el archivo; añade `"latin-ext"` si tienes textos en polaco o turco. Inter es variable, así que una sola descarga cubre todos los pesos sin listar `weight`.
- **`display: "swap"`** muestra la fuente de respaldo mientras llega la real; como `next/font` ajusta las métricas del respaldo, el cambio es casi imperceptible y no hay CLS.
- **Las fuentes locales se declaran una vez**, en el layout raíz. Instanciar `localFont` en varios archivos duplica las declaraciones `@font-face`.

Verificación: en la pestaña Network no debe aparecer ninguna petición a `fonts.googleapis.com` ni `fonts.gstatic.com`; las fuentes se sirven desde `/_next/static/media/`. Y en el `<head>` verás un `<link rel="preload" as="font">` por cada archivo, generado automáticamente.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Mi página de producto tarda 2,5 s porque las reseñas y las recomendaciones vienen de dos servicios lentos. El producto en sí carga en 100 ms. ¿Cómo hago que el usuario vea el producto ya y el resto vaya llegando?",
            },
            {
                "role": "assistant",
                "content": r"""Con **streaming**: separa lo lento en componentes propios, envuélvelos en `<Suspense>` y Next envía el HTML del producto en cuanto esté, seguido de las partes lentas a medida que resuelven, todo en la misma respuesta HTTP.

```tsx
// app/products/[id]/page.tsx
import { Suspense } from "react";
import { getProduct, getReviews, getRecommendations } from "@/lib/catalog";

type Props = { params: Promise<{ id: string }> };

export default async function ProductPage({ params }: Props) {
  const { id } = await params;
  const product = await getProduct(id); // 100 ms: bloquea solo lo imprescindible

  return (
    <main>
      <h1>{product.name}</h1>
      <p>{product.price} €</p>

      <Suspense fallback={<ReviewsSkeleton />}>
        <Reviews productId={id} />
      </Suspense>

      <Suspense fallback={<RecommendationsSkeleton />}>
        <Recommendations productId={id} />
      </Suspense>
    </main>
  );
}

async function Reviews({ productId }: { productId: string }) {
  const reviews = await getReviews(productId); // 1,5 s
  return (
    <ul>
      {reviews.map((r) => (
        <li key={r.id}>{r.text}</li>
      ))}
    </ul>
  );
}

async function Recommendations({ productId }: { productId: string }) {
  const items = await getRecommendations(productId); // 2 s
  return (
    <ul>
      {items.map((p) => (
        <li key={p.id}>{p.name}</li>
      ))}
    </ul>
  );
}
```

Qué ocurre en la red: a los ~100 ms llega el HTML con el producto y los dos esqueletos; a los ~1,6 s llega un fragmento con las reseñas y un pequeño script que lo coloca en su sitio; a los ~2,1 s, las recomendaciones. El tiempo hasta ver el producto pasa de 2,5 s a 0,1 s, y el total baja a 2,1 s porque **las dos cargas lentas ocurren en paralelo**: cada componente `async` arranca su `await` sin esperar al otro.

Reglas que hacen que funcione:

- **Un `<Suspense>` por unidad independiente.** Si pones las dos secciones dentro del mismo boundary, aparecen juntas cuando termine la más lenta.
- **No hagas `await` de lo lento en la página.** Un `await getReviews()` en `ProductPage` bloquearía todo el HTML, con o sin Suspense debajo.
- **El fallback debe tener el tamaño aproximado del contenido** (esqueleto, no spinner) para que la página no salte cuando llegue el fragmento.

Diferencia con `loading.tsx`: ese archivo es un Suspense alrededor de la **página entera**: útil para la primera navegación, pero no permite mostrar el producto antes que las reseñas. Puedes tener ambos.

Un matiz importante: el código de estado HTTP (200, 404) se envía con el primer fragmento. Si `getReviews` falla después, ya no puede convertirse en un 500: el boundary de error más cercano (`error.tsx` o uno propio) renderiza su fallback dentro de la sección. Por eso lo que decide el estado (existe el producto o no) va **antes** del primer `<Suspense>`; de ahí el `await getProduct` sin boundary.

Verificación: `curl -N http://localhost:3000/products/42` muestra la respuesta a medida que llega; verás el `<h1>` casi al instante y, segundos después, bloques `<div hidden id="S:1">` con el contenido de las reseñas y un `<script>` que los reubica. En el navegador, Performance muestra el LCP en el producto, no en las reseñas.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "I have a photo gallery. Clicking a photo should open it in a modal over the grid, but if you refresh or share the link `/photos/42` it should render as a full page. I read this is what parallel and intercepting routes are for, but the folder naming confuses me.",
            },
            {
                "role": "assistant",
                "content": r"""That is exactly their use case, and the confusion usually clears up once you see that the two features do different jobs: the **parallel route** gives the layout a second slot to render into, and the **intercepting route** decides that, during client-side navigation, `/photos/42` renders into that slot instead of replacing the page.

```
app/
  layout.tsx                      # renders {children} and {modal}
  page.tsx                        # /  the grid
  @modal/
    default.tsx                   # what the slot shows when nothing is intercepted: null
    (.)photos/[id]/
      page.tsx                    # modal version, used only on soft navigation from /
  photos/[id]/
    page.tsx                      # full page: refresh, shared link, direct visit
```

```tsx
// app/layout.tsx
export default function RootLayout({ children, modal }: { children: React.ReactNode; modal: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        {modal}
      </body>
    </html>
  );
}
```

```tsx
// app/@modal/default.tsx
export default function Default() {
  return null;
}
```

```tsx
// app/@modal/(.)photos/[id]/page.tsx
import { Modal } from "@/components/modal";
import { getPhoto } from "@/lib/photos";

export default async function PhotoModal({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const photo = await getPhoto(id);
  return (
    <Modal>
      <img src={photo.url} alt={photo.alt} />
    </Modal>
  );
}
```

```tsx
// components/modal.tsx
"use client";

import { useRouter } from "next/navigation";

export function Modal({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  return (
    <div role="dialog" aria-modal="true" onClick={() => router.back()}>
      <div onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  );
}
```

The grid links normally: `<Link href={`/photos/${photo.id}`}>`.

How the naming works:

- **`@modal`** is a slot, not a URL segment. It becomes a `modal` prop of the layout in the same folder. The URL never contains `@modal`.
- **`(.)photos`** means "intercept the route `photos` at the **same level** as this slot". The prefix is relative to the segment, not the file system: `(..)` is one level up, `(..)(..)` two, `(...)` from the app root. Since `@modal` lives in `app/`, `photos` is a sibling at the same level, hence `(.)`.
- **`default.tsx`** is required. On a hard navigation to `/` Next needs something to render in the `modal` slot, and without a default it returns a 404 for the whole route.

Why the two behaviors you asked for fall out of this:

| Navigation | What renders |
|---|---|
| Soft (click a `<Link>` from `/`) | `/` stays as `children`, interception fills `modal` with the photo: modal over the grid, URL becomes `/photos/42` |
| Hard (refresh, shared link, direct visit) | no interception: `photos/[id]/page.tsx` renders as `children`, `default.tsx` fills `modal` with `null` |

`router.back()` closes the modal and returns the URL to `/`. If the user arrived via the full page, there is no modal, so nothing to close.

Two things that bite in practice:

1. If the modal should also open from `/albums/3`, the interception must be reachable from there: add a `@modal` slot and `default.tsx` under `app/albums/[albumId]/` with `(..)(..)photos/[id]` (two levels up from `albums/[albumId]`). The `(.)` in the root slot only catches navigations that start at `/`.
2. Pressing back after closing with `router.back()` can reopen the modal, because the history entry still exists. If that annoys you, close with `router.push("/")` and accept the extra entry, or use `useSelectedLayoutSegment("modal")` to decide whether to render the dialog.

Check: open `/`, click a photo, the grid stays visible behind the modal and the URL reads `/photos/42`. Press F5: the same URL now shows the full page. Both paths served by the same `getPhoto` call, no duplicated page logic.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo `API_KEY=abc123` en `.env.local`. En un Server Component `process.env.API_KEY` funciona, pero en un componente con `\"use client\"` es `undefined`. ¿Hay que configurar algo?",
            },
            {
                "role": "assistant",
                "content": r"""No es un fallo de configuración: es la protección por diseño. **Al navegador solo llegan las variables con prefijo `NEXT_PUBLIC_`.** Todo lo demás se queda en el servidor, precisamente para que una clave como `API_KEY` no acabe en el bundle que cualquiera puede leer.

Antes de renombrarla, piensa qué es: una clave de API es un secreto. Si la pones como `NEXT_PUBLIC_API_KEY`, la estás publicando. La solución correcta es que la llamada que la usa ocurra en el servidor y el cliente reciba solo el resultado.

Tres formas de hacerlo según el caso:

**1. Datos de carga inicial → Server Component que pasa props:**

```tsx
// app/weather/page.tsx (servidor)
import { WeatherWidget } from "./weather-widget";

export default async function WeatherPage() {
  const res = await fetch(`https://api.weather.example/today?key=${process.env.API_KEY}`, {
    next: { revalidate: 600 },
  });
  const data = await res.json();
  return <WeatherWidget temperature={data.temp} />; // el cliente recibe el número, no la clave
}
```

**2. Datos bajo demanda (al pulsar un botón) → Server Action:**

```ts
// app/weather/actions.ts
"use server";

export async function fetchForecast(city: string) {
  const res = await fetch(`https://api.weather.example/forecast?city=${encodeURIComponent(city)}&key=${process.env.API_KEY}`);
  if (!res.ok) throw new Error("forecast unavailable");
  return (await res.json()) as { days: { date: string; temp: number }[] };
}
```

El Client Component la importa y la llama como una función; Next la convierte en una petición POST al servidor.

**3. Consumo desde fuera de React (app móvil, otro origen) → Route Handler** que actúa de proxy y añade la clave.

Para las variables que **sí** deben llegar al cliente (la URL pública de tu API, un ID de analítica):

```
# .env.local
API_KEY=abc123                       # solo servidor
NEXT_PUBLIC_API_URL=https://api.example.com   # servidor y cliente
```

Dos propiedades de `NEXT_PUBLIC_` que sorprenden:

- Se **incrustan en el build**: `process.env.NEXT_PUBLIC_API_URL` se sustituye por el texto literal al compilar. Cambiar la variable en el servidor después no afecta hasta que vuelvas a construir. Para Docker, eso significa una imagen por entorno o pasar esos valores como `ARG` en el build.
- Solo funcionan con acceso **estático**: `process.env.NEXT_PUBLIC_API_URL` sí; `process.env[name]` con un nombre dinámico no se sustituye.

Para que un olvido no acabe filtrando un secreto, valida y centraliza el acceso:

```ts
// lib/env.ts
import "server-only"; // importar este módulo desde un Client Component falla en el build
import { z } from "zod";

const schema = z.object({
  API_KEY: z.string().min(1),
  DATABASE_URL: z.string().url(),
});

export const env = schema.parse(process.env); // falla al arrancar si falta algo, no en la primera petición
```

Orden de carga, de menor a mayor prioridad: `.env`, `.env.development` o `.env.production` según el modo, `.env.local` (siempre, salvo en `test`). `.env.local` va en `.gitignore`; `.env` con valores por defecto no secretos puede ir en el repositorio.

Verificación de que nada se escapa: tras `npm run build`, `grep -r "abc123" .next/static` no debe devolver nada. Si aparece, alguna variable sin prefijo está llegando a un archivo de cliente a través de un import indebido.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito autenticación con email y contraseña en Next 15 sin librerías de auth: login, sesión con cookie, cerrar sesión y proteger rutas. ¿Cómo lo haces de forma segura? Y dime cuándo merece la pena pasar a Auth.js.",
            },
            {
                "role": "assistant",
                "content": r"""La pieza central es una **cookie de sesión `httpOnly` firmada**, creada en una Server Action y leída con `cookies()` donde haga falta. Lo escribo con `jose` para firmar un JWT (ya es dependencia transitiva de muchos proyectos y funciona en Edge) y `bcryptjs` para la contraseña.

```ts
// lib/session.ts
import "server-only";
import { cookies } from "next/headers";
import { SignJWT, jwtVerify } from "jose";

const COOKIE = "session";
const SECRET = new TextEncoder().encode(process.env.SESSION_SECRET);
const MAX_AGE_SECONDS = 60 * 60 * 24 * 7; // 7 días

type SessionPayload = { userId: string };

export async function createSession(userId: string) {
  const token = await new SignJWT({ userId } satisfies SessionPayload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${MAX_AGE_SECONDS}s`)
    .sign(SECRET);

  const store = await cookies();
  store.set(COOKIE, token, {
    httpOnly: true, // JavaScript del navegador no puede leerla: inmune a XSS que robe la sesión
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax", // no viaja en POST desde otros sitios: mitiga CSRF
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
}

export async function getSession(): Promise<SessionPayload | null> {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, SECRET, { algorithms: ["HS256"] });
    return { userId: payload.userId as string };
  } catch {
    return null; // firma inválida o caducado
  }
}

export async function destroySession() {
  (await cookies()).delete(COOKIE);
}
```

```ts
// app/login/actions.ts
"use server";

import { redirect } from "next/navigation";
import { z } from "zod";
import bcrypt from "bcryptjs";
import { db } from "@/lib/db";
import { createSession, destroySession } from "@/lib/session";

const Credentials = z.object({ email: z.string().email(), password: z.string().min(8) });

export async function login(_prev: { error?: string }, formData: FormData) {
  const parsed = Credentials.safeParse(Object.fromEntries(formData));
  if (!parsed.success) return { error: "Email o contraseña inválidos" };

  const user = await db.user.findUnique({ where: { email: parsed.data.email } });
  // Mismo mensaje exista o no el usuario: no revelamos qué emails están registrados
  const ok = user ? await bcrypt.compare(parsed.data.password, user.passwordHash) : false;
  if (!user || !ok) return { error: "Email o contraseña inválidos" };

  await createSession(user.id);
  redirect("/dashboard");
}

export async function logout() {
  await destroySession();
  redirect("/login");
}
```

Protección de rutas en el layout del área privada:

```tsx
// app/dashboard/layout.tsx
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) redirect("/login");
  return <>{children}</>;
}
```

Y **cada Server Action que mute datos** vuelve a llamar a `getSession()`: una acción es un endpoint POST que se puede invocar sin pasar por el layout.

Decisiones de seguridad, una por una:

- **`cookies().set` solo funciona en Server Actions y Route Handlers**, no en Server Components (el HTML ya puede haber empezado a enviarse). Por eso el login es una acción.
- **`httpOnly` + `secure` + `sameSite: "lax"`** es el mínimo. `lax` permite que el enlace desde un email abra el dashboard con sesión, pero bloquea un `<form method="post">` desde otro origen.
- **JWT firmado, no cifrado**: el payload es legible (base64), así que solo lleva el `userId`. Nada de roles ni emails dentro; se leen de la BD en cada petición, que es lo que permite revocar un acceso al instante.
- **Caducidad corta y renovación**: 7 días es razonable para una app de negocio. Si quieres poder «cerrar todas las sesiones», cambia el JWT por un id de sesión guardado en la BD y borra la fila; el coste es una consulta por petición.
- **`bcrypt.compare` también cuando el usuario no existe** (línea del `ok`): evita que el tiempo de respuesta delate si el email está registrado. El `user ?` lo acorta aquí; en producción, compara contra un hash fijo en la rama de usuario inexistente.

Cuándo pasar a **Auth.js** (`next-auth@5`): en cuanto necesites OAuth (Google, GitHub, Microsoft), magic links o enlazar varias cuentas al mismo usuario. Implementar OAuth a mano, con sus callbacks, estados y rotación de tokens, es donde se cometen los errores caros. Con Auth.js defines `auth.ts` con `NextAuth({ providers: [GitHub] })`, exportas `handlers` en `app/api/auth/[...nextauth]/route.ts` y usas `auth()` en servidor donde aquí usas `getSession()`. Para email + contraseña puro, lo de arriba es más simple y más transparente.

Verificación: haz login con `curl -i -X POST` al formulario y comprueba en `set-cookie` los atributos `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=604800`. Luego modifica un carácter del token en el navegador y recarga `/dashboard`: debe redirigir a `/login`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero desplegar Next 15 en nuestro propio servidor con Docker. La imagen que me sale con `COPY . .` y `npm run build` pesa 1,2 GB. ¿Cómo se hace una imagen razonable?",
            },
            {
                "role": "assistant",
                "content": r"""Con `output: "standalone"` y un Dockerfile multi-etapa. En modo standalone, `next build` genera en `.next/standalone` un servidor Node con **solo** los `node_modules` que la app usa en tiempo de ejecución; la imagen final copia eso y nada más. De 1,2 GB se baja a 150-250 MB.

```ts
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

```dockerfile
# Dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Las NEXT_PUBLIC_* se incrustan en el build: deben estar disponibles AQUÍ, no en runtime
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

```
# .dockerignore
node_modules
.next
.git
.env*.local
```

Por qué cada parte:

- **Tres etapas**: `deps` instala con `npm ci` (reproducible y cacheable: solo se repite si cambia el lockfile); `builder` compila; `runner` contiene únicamente el resultado. Ni el código fuente ni las dependencias de desarrollo llegan a la imagen final.
- **`.next/static` y `public` se copian aparte**: el modo standalone no los incluye a propósito, porque en despliegues grandes se sirven desde un CDN. En un servidor propio, los copias junto al servidor y Next los sirve.
- **`HOSTNAME=0.0.0.0`**: sin esto el servidor escucha en `localhost` dentro del contenedor y Docker no puede enrutarle tráfico. Es el fallo número uno de «el contenedor arranca pero no responde».
- **Usuario sin privilegios**: el proceso corre como `nextjs`, no como root.
- **`ARG` para `NEXT_PUBLIC_*`**: esas variables se sustituyen en el código del cliente durante `next build`. Pasarlas con `-e` al arrancar el contenedor no sirve; van con `docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .`. Los secretos de servidor (`DATABASE_URL`, `SESSION_SECRET`) sí van en runtime con `-e` o un archivo de entorno, y nunca en el Dockerfile.
- **`.dockerignore`** evita copiar `node_modules` locales (de otro sistema operativo) y el `.next` anterior, que invalidarían la caché y podrían romper el build.

Construcción y arranque:

```
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t tienda:1.0 .
docker run -p 3000:3000 -e DATABASE_URL="postgres://…" -e SESSION_SECRET="…" tienda:1.0
```

Dos matices para varios contenedores detrás de un balanceador: la caché de datos (ISR, `fetch` cacheado) vive en el sistema de archivos de cada instancia; si necesitas que la invalidación afecte a todas, configura un `cacheHandler` compartido (Redis) en `next.config.ts`. Y la optimización de imágenes usa `sharp`, que Next 15 instala por defecto; en Alpine funciona sin pasos extra.

Verificación: `docker images tienda:1.0` debe mostrar unos 200 MB; `curl -I localhost:3000` responde `200`; y `docker exec` en el contenedor con `ls node_modules | wc -l` muestra unas decenas de paquetes, no cientos.""",
            },
            {
                "role": "user",
                "content": "¿Y si al final lo desplegamos en Vercel? ¿Qué parte de esto se tira?",
            },
            {
                "role": "assistant",
                "content": r"""Todo el Dockerfile. Vercel construye desde el repositorio y despliega cada ruta en su infraestructura; no ejecutas un servidor Node tuyo. Lo que cambia, punto por punto:

| Tema | Docker propio | Vercel |
|---|---|---|
| `output: "standalone"` | necesario | ignorado; quítalo o déjalo, no afecta |
| Variables de entorno | `ARG` en build + `-e` en runtime | se definen en el panel por entorno (Production, Preview, Development); las `NEXT_PUBLIC_*` se inyectan en el build automáticamente |
| Caché de ISR y `fetch` | sistema de archivos de cada instancia; `cacheHandler` para compartirla | compartida y distribuida por defecto; `revalidateTag` afecta globalmente |
| Optimización de imágenes | `sharp` en tu contenedor | servicio gestionado, con cuota según el plan |
| Middleware | Edge local (mismo proceso) | se ejecuta en su red Edge, cerca del usuario |
| Escalado | tú (réplicas, balanceador) | automático por petición |
| Entornos de prueba | los montas tú | un despliegue por cada PR, con su URL |

Lo que **se conserva** tal cual: el código, `next.config.ts` (salvo `output`), el `.env.local` para desarrollo y la validación de variables con zod. Los secretos de servidor se crean en Settings → Environment Variables; marca los de producción como *sensitive* para que no se puedan leer después.

Dos cosas que conviene revisar al cambiar:

1. **Tiempo máximo de ejecución** de las funciones de servidor: por defecto 10 s en el plan Hobby (ampliable en los de pago, y más con `maxDuration` exportado desde la ruta: `export const maxDuration = 60`). Un informe que tarde 40 s en generarse funciona en tu contenedor y falla ahí; convierte ese trabajo en una tarea en segundo plano.
2. **Sistema de archivos efímero**: nada de escribir subidas en `./uploads`. En el contenedor propio también deberías evitarlo (se pierde al redesplegar), pero en Vercel falla directamente. Las subidas van a un almacenamiento externo (S3, R2, Vercel Blob).

Y un consejo para no casarte con ninguna de las dos: mantén el Dockerfile en el repositorio aunque despliegues en Vercel. Cuesta cero mientras no se usa, y es tu prueba de que la aplicación arranca fuera de la plataforma: `docker build` en CI una vez por semana te avisa si alguna dependencia empieza a requerir algo específico de Vercel.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""En desarrollo me sale este aviso en rojo en cada carga:

```
Hydration failed because the server rendered HTML didn't match the client. As a result this tree will be regenerated on the client. This can happen if a SSR-ed Client Component used:
- A server/client branch `if (typeof window !== 'undefined')`.
- Variable input such as `Date.now()` or `Math.random()` which changes each time it's called.
- Date formatting in a user's locale which doesn't match the server.
- External changing data without sending a snapshot of it along with the HTML.
- Invalid HTML tag nesting.
```

El componente muestra la hora de última sincronización y el tema (claro/oscuro) que leo de localStorage. ¿Cómo lo arreglo sin desactivar el SSR?""",
            },
            {
                "role": "assistant",
                "content": r"""Tienes dos de las causas de la lista en el mismo componente, y las dos tienen la misma raíz: **el HTML del servidor y el primer render del cliente deben ser idénticos**. La hora cambia entre ambos y `localStorage` no existe en el servidor.

Para diagnosticar cuál es cuál, el overlay de Next muestra un diff con el texto esperado y el recibido; en este caso verás algo como `- 14:02:11` / `+ 14:02:13` y `- data-theme="light"` / `+ data-theme="dark"`.

**1. Valores que solo existen en el navegador (localStorage, hora local, `window.innerWidth`)**: renderiza en el servidor un valor neutro y aplica el real **después** de hidratar. La forma limpia es un hook que dice si ya estamos en el cliente:

```tsx
"use client";

import { useSyncExternalStore } from "react";

const noop = () => () => {};

// false en el servidor y en la hidratación; true a partir del primer render de cliente
export function useIsClient() {
  return useSyncExternalStore(noop, () => true, () => false);
}
```

```tsx
"use client";

import { useIsClient } from "@/lib/use-is-client";

export function SyncStatus({ syncedAt }: { syncedAt: string }) {
  const isClient = useIsClient();
  const theme = isClient ? (localStorage.getItem("theme") ?? "light") : "light";

  return (
    <div data-theme={theme}>
      Última sincronización:{" "}
      <time dateTime={syncedAt} suppressHydrationWarning>
        {isClient ? new Date(syncedAt).toLocaleTimeString() : "—"}
      </time>
    </div>
  );
}
```

`useSyncExternalStore` con `getServerSnapshot` devolviendo `false` garantiza que la hidratación usa el mismo valor que el servidor, y React hace un segundo render con `true` inmediatamente después. Es la versión correcta del `useEffect(() => setMounted(true), [])` de toda la vida, sin el estado intermedio.

**2. Si no quieres el parpadeo del tema** (primero claro, luego oscuro), la fuente de verdad tiene que estar disponible en el servidor: guarda el tema en una **cookie** en vez de localStorage y léela en el layout raíz con `cookies()`. Así el HTML ya sale con `data-theme="dark"` y no hay desajuste ni parpadeo. Es lo que hacen las librerías de tema serias.

**3. Para una hora que de verdad quieres pintar en el servidor**, recibe el instante como dato (`syncedAt` ISO desde el servidor) y formatéalo con una zona fija o deja el formateo al cliente, como arriba. `suppressHydrationWarning` en el `<time>` silencia el aviso **solo para el texto de ese elemento**; úsalo cuando la diferencia es aceptable (segundos), nunca para tapar una estructura distinta.

Las otras dos causas de la lista, por si aparecen en otro sitio:

- **Anidamiento HTML inválido**: `<p><div>…</div></p>` o `<a>` dentro de `<a>`. El navegador «corrige» el HTML del servidor cerrando el `<p>` antes, y React en cliente genera otra estructura. El arreglo es HTML válido; el overlay te indica la etiqueta.
- **Extensiones del navegador** que inyectan atributos (traductores, gestores de contraseñas) producen el aviso solo en tu máquina. Compruébalo en una ventana de incógnito antes de buscar el bug.

Verificación: tras el cambio, recarga con la consola abierta: ningún aviso. Luego cambia el tema, recarga y confirma que el `data-theme` final es el correcto y que, con la cookie, el HTML inicial (`curl` o «Ver código fuente») ya lo trae.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala el problema, explica el porqué y da el arreglo."},
            {
                "role": "user",
                "content": r"""El build falla desde que añadí un botón de «recargar» a la lista de productos:

```
Module not found: Can't resolve 'fs'
Import trace for requested module:
./lib/products.ts
./app/products/product-list.tsx
```

```tsx
// app/products/product-list.tsx
"use client";

import { useState } from "react";
import { getProducts, type Product } from "@/lib/products";

export function ProductList({ initial }: { initial: Product[] }) {
  const [products, setProducts] = useState(initial);
  return (
    <>
      <button onClick={async () => setProducts(await getProducts())}>Recargar</button>
      <ul>{products.map((p) => <li key={p.id}>{p.name}</li>)}</ul>
    </>
  );
}
```

`lib/products.ts` lee un JSON del disco con `fs/promises`.""",
            },
            {
                "role": "assistant",
                "content": r"""**Problema:** un Client Component importa un módulo de servidor. `"use client"` convierte `product-list.tsx` y **todo lo que importa** en código para el navegador; `lib/products.ts` usa `fs`, que no existe ahí, y el bundler se detiene. El error aparece en el build y no antes porque en desarrollo solo compila lo que visitas.

Que antes funcionara se debe a que el componente solo importaba el **tipo** `Product`, que desaparece al compilar. Al usar `getProducts` en runtime, el import pasó a ser real.

**Arreglo:** la recarga debe pedirle los datos al servidor, no ejecutar código de servidor en el cliente. Con una Server Action el cambio es mínimo:

```ts
// app/products/actions.ts
"use server";

import { getProducts } from "@/lib/products";

export async function reloadProducts() {
  return getProducts(); // se ejecuta en el servidor; el cliente recibe el JSON
}
```

```tsx
// app/products/product-list.tsx
"use client";

import { useState, useTransition } from "react";
import type { Product } from "@/lib/products"; // solo tipo: no arrastra `fs`
import { reloadProducts } from "./actions";

export function ProductList({ initial }: { initial: Product[] }) {
  const [products, setProducts] = useState(initial);
  const [isPending, startTransition] = useTransition();

  return (
    <>
      <button
        disabled={isPending}
        onClick={() => startTransition(async () => setProducts(await reloadProducts()))}
      >
        {isPending ? "Recargando…" : "Recargar"}
      </button>
      <ul>
        {products.map((p) => (
          <li key={p.id}>{p.name}</li>
        ))}
      </ul>
    </>
  );
}
```

Dos observaciones más del revisor:

1. **`import type`**, no `import { type Product }` mezclado con valores. Con `verbatimModuleSyntax` activado, un import de tipo puro se elimina por completo; así es imposible que una refactorización futura vuelva a arrastrar el módulo entero.
2. **Marca el módulo de servidor** para que este error sea explícito y aparezca en el primer `import`, no cuando el bundler encuentra `fs` tres niveles más abajo:

```ts
// lib/products.ts
import "server-only";
import { readFile } from "node:fs/promises";
```

Con `server-only` (paquete de npm, sin dependencias), importar `lib/products.ts` desde cualquier archivo cliente falla con un mensaje claro: `You're importing a component that needs "server-only". That only works in a Server Component but one of its parents is marked with "use client"`. Ponlo en todo módulo que toque base de datos, disco o secretos.

Alternativa igualmente válida: en lugar de guardar los productos en `useState`, llamar a `router.refresh()` para que el Server Component padre vuelva a renderizar con datos nuevos. Es más simple si el cliente no necesita transformar los datos; la acción es mejor si quieres el resultado en una variable del cliente.

Comprobación: `npm run build` termina, y `grep -r "fs/promises" .next/static` no devuelve nada. Si pulsas «Recargar» con la pestaña Network abierta, verás una petición `POST` a la misma URL con la cabecera `Next-Action`: esa es la Server Action.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 21-30: cookies()/headers() async y renderizado dinámico, migración desde Pages Router (multiturno), ISR,
#        i18n (multiturno), compartir datos layout/página (EN), testing (EN), Route Handler vs Server Action (EN→ES),
#        useSearchParams sin Suspense, generateStaticParams (multiturno rioplatense), seguridad de Server Actions
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tras subir a Next 15 me sale esto en la terminal:

```
Error: Route "/dashboard" used `cookies().get('session')`. `cookies()` should be awaited before using its value. Learn more: https://nextjs.org/docs/messages/sync-dynamic-apis
```

Lo arreglé con `await` y ya no sale, pero ahora en el `next build` la página aparece con `ƒ (Dynamic)` y antes era `○ (Static)`. Solo uso la cookie para mostrar el nombre del usuario en la esquina. ¿Puedo tener lo demás estático?""",
            },
            {
                "role": "assistant",
                "content": r"""Las dos cosas están relacionadas. `cookies()`, `headers()` y `searchParams` son **APIs dinámicas**: leerlas significa que la respuesta depende de la petición, así que Next no puede prerenderizar la página en el build y la marca como dinámica. El `await` era obligatorio (en 15 son asíncronas), pero no es lo que la hizo dinámica: ya lo era desde que leyó la cookie; antes el build no lo detectaba tan explícitamente.

Tienes tres formas de recuperar lo estático, de menor a mayor cambio:

**1. Mueve la lectura de la cookie a un componente de cliente que la pida al servidor.** La página queda estática y el nombre llega después:

```tsx
// app/dashboard/page.tsx (estática)
import { Suspense } from "react";
import { UserBadge } from "./user-badge";

export default function DashboardPage() {
  return (
    <main>
      <h1>Panel</h1>
      <Suspense fallback={<span>…</span>}>
        <UserBadge />
      </Suspense>
      <p>Contenido que no depende del usuario.</p>
    </main>
  );
}
```

```tsx
// app/dashboard/user-badge.tsx
import { cookies } from "next/headers";

export async function UserBadge() {
  const session = (await cookies()).get("session")?.value;
  const name = session ? await getUserName(session) : "Invitado";
  return <span>{name}</span>;
}
```

Con la configuración por defecto de Next 15 esto **sigue siendo dinámico**: cualquier API dinámica en cualquier componente del árbol marca la ruta entera. Lo que hace que el esqueleto estático se sirva al instante y solo `UserBadge` espere es el **Partial Prerendering**, experimental en 15 (`experimental: { ppr: "incremental" }` en `next.config.ts` y `export const experimental_ppr = true` en la página). Si no quieres activar funcionalidades experimentales, usa la opción 2.

**2. Lee la cookie en el cliente, no en el servidor.** Si la cookie no es `httpOnly` (por ejemplo, una cookie de preferencia con el nombre para mostrar), un Client Component puede leerla tras hidratar, y la página es estática de verdad:

```tsx
"use client";
import { useSyncExternalStore } from "react";

function readName() {
  const match = document.cookie.match(/(?:^|; )display_name=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "Invitado";
}

export function UserBadge() {
  const name = useSyncExternalStore(() => () => {}, readName, () => "Invitado");
  return <span>{name}</span>;
}
```

Para una cookie de sesión `httpOnly` esto no vale (el navegador no la expone); entonces el nombre lo obtienes con un `fetch("/api/me")` desde el cliente, y la página sigue siendo estática.

**3. Acepta que la ruta sea dinámica y cachea los datos.** Si el dashboard muestra datos personales en todas partes, lo estático es ilusorio. Deja la página dinámica y asegúrate de que lo caro (consultas compartidas) está en `unstable_cache` o en `fetch` con `revalidate`, para que «dinámico» signifique «unos milisegundos de render», no «una consulta pesada por visita».

Para el caso que describes (todo estático salvo un nombre en la esquina), la opción 2 es la correcta y no requiere nada experimental.

Un apunte sobre la familia de estas APIs: `unstable_noStore()` fue sustituida por `connection()` de `next/server`, que hace lo mismo (esperar a la petición para forzar renderizado dinámico) con nombre estable. Si ves `unstable_noStore` en código migrado, cámbialo.

Verificación: `npm run build` debe listar `/dashboard` con `○` otra vez, y en la salida del build no debe aparecer ninguna página como `ƒ` que no quieras. Para confirmar que el nombre carga, abre la página con la cookie puesta y mira que `UserBadge` pasa de «Invitado» al nombre sin recargar.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos una app con Pages Router (unas 60 páginas, `getServerSideProps` por todas partes, `_app.tsx` con providers). ¿Cómo migramos al App Router sin parar el desarrollo? ¿Y qué equivale a qué?",
            },
            {
                "role": "assistant",
                "content": r"""Los dos routers **conviven en el mismo proyecto**: `pages/` y `app/` pueden coexistir mientras ninguna ruta esté definida en ambos. Eso permite migrar página a página y desplegar entre medias. El plan que funciona:

**Fase 0: preparar sin mover nada.** Sube a Next 15 y React 19 con `pages/` tal cual (`npx @next/codemod@canary upgrade latest`). Arregla lo que rompa (poco: sobre todo tipos de React 19). Despliega.

**Fase 1: el layout raíz.** Crea `app/layout.tsx` con lo que hoy está en `_app.tsx` y `_document.tsx`: `<html>`, `<body>`, fuentes, CSS global, providers. Los providers que usan contexto van en un Client Component:

```tsx
// app/providers.tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

```tsx
// app/layout.tsx
import { Providers } from "./providers";
import "@/styles/globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

`_app.tsx` sigue existiendo para las páginas que quedan en `pages/`; cada router usa el suyo.

**Fase 2: migrar por rutas, empezando por las hojas.** Primero las páginas simples (estáticas, sin `getServerSideProps`), luego las de datos, por último las que comparten layouts complejos. Cada migración es: crear `app/<ruta>/page.tsx`, borrar `pages/<ruta>.tsx`, desplegar.

Tabla de equivalencias:

| Pages Router | App Router |
|---|---|
| `getServerSideProps` | `async function Page()` que hace `await` directamente (dinámica por defecto en 15) |
| `getStaticProps` | el mismo componente `async` + `export const revalidate = N` o `fetch` con `{ next: { revalidate } }` |
| `getStaticPaths` | `generateStaticParams()` |
| `context.params` / `context.query` | props `params` y `searchParams` (promesas) |
| `context.req.cookies` | `await cookies()` de `next/headers` |
| `useRouter` de `next/router` | `useRouter`, `usePathname`, `useSearchParams`, `useParams` de `next/navigation` |
| `router.query.id` | `useParams()` o `params` de la página |
| `<Head>` de `next/head` | `export const metadata` / `generateMetadata` |
| `_app.tsx` | `app/layout.tsx` + `providers.tsx` |
| `_document.tsx` | `app/layout.tsx` (el `<html>`/`<body>`) |
| `_error.tsx` / `404.tsx` | `error.tsx` / `not-found.tsx` por segmento |
| `pages/api/*.ts` | `app/api/*/route.ts` (o déjalas en `pages/api`: siguen funcionando) |
| `Layout` por página con `getLayout` | `layout.tsx` anidados |

Una página típica, antes y después:

```tsx
// pages/orders/[id].tsx
export const getServerSideProps: GetServerSideProps = async ({ params, req }) => {
  const order = await getOrder(String(params?.id), req.cookies.session);
  if (!order) return { notFound: true };
  return { props: { order } };
};
export default function OrderPage({ order }) { return <h1>{order.number}</h1>; }
```

```tsx
// app/orders/[id]/page.tsx
import { cookies } from "next/headers";
import { notFound } from "next/navigation";

export default async function OrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = (await cookies()).get("session")?.value;
  const order = await getOrder(id, session);
  if (!order) notFound();
  return <h1>{order.number}</h1>;
}
```

Desaparece la función de datos, el tipo de props y la serialización: el componente lee lo que necesita.

Lo que más trabajo da en la práctica, por orden:

1. **`useRouter` de `next/router`** en componentes compartidos por ambos routers: falla en `app/`. Durante la convivencia, los componentes compartidos reciben la navegación por props o usan `next/navigation` solo en los que ya viven en `app/`.
2. **Componentes con `useState` importados desde páginas de `app/`** necesitan `"use client"`. Añádelo en las hojas interactivas, no en todo.
3. **Datos que pasaban por props desde `getServerSideProps` a muchos hijos**: en `app/` cada componente de servidor puede pedir lo suyo; con `cache` de React no se duplican consultas.

Las `pages/api` se pueden quedar hasta el final: no bloquean nada.""",
            },
            {
                "role": "user",
                "content": "Tenemos muchas páginas de catálogo con `getStaticProps` + `revalidate: 60` y `getStaticPaths` con `fallback: 'blocking'`. ¿Eso cómo queda?",
            },
            {
                "role": "assistant",
                "content": r"""Queda más corto. `getStaticProps` con `revalidate` es ISR, y en el App Router se expresa con una constante exportada; `getStaticPaths` es `generateStaticParams`, y `fallback: "blocking"` es el comportamiento por defecto.

```tsx
// app/catalog/[slug]/page.tsx
import { notFound } from "next/navigation";
import { getAllSlugs, getProductBySlug } from "@/lib/catalog";

export const revalidate = 60; // equivale a getStaticProps + revalidate: 60

// equivale a getStaticPaths: qué rutas se generan en el build
export async function generateStaticParams() {
  const slugs = await getAllSlugs();
  return slugs.map((slug) => ({ slug }));
}

// fallback: "blocking" es el valor por defecto (dynamicParams = true):
// una ruta no generada se renderiza en la primera visita y se cachea.
// export const dynamicParams = false; // sería fallback: false → 404 para rutas no listadas

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) notFound();
  return <h1>{product.name}</h1>;
}
```

Correspondencias exactas:

| Pages | App |
|---|---|
| `revalidate: 60` en `getStaticProps` | `export const revalidate = 60` |
| `fallback: "blocking"` | por defecto |
| `fallback: false` | `export const dynamicParams = false` |
| `fallback: true` (mostrar esqueleto mientras genera) | no existe como tal; usa `loading.tsx`, que cubre el mismo caso con streaming |
| `return { notFound: true }` | `notFound()` |
| `res.revalidate("/catalog/x")` en una API route | `revalidatePath("/catalog/x")` desde una Server Action o Route Handler |

Dos diferencias de comportamiento a tener en cuenta:

- **El `fetch` dentro de la página hereda el `revalidate` de la ruta** salvo que lo sobrescriba. Si tu `getProductBySlug` usa `fetch`, puedes afinar por llamada con `{ next: { revalidate: 300 } }`; si usa un cliente de BD, lo que manda es la constante de la página (o envuelves la consulta en `unstable_cache`).
- **`generateStaticParams` puede devolver un subconjunto.** Con 20.000 productos no generes todos en el build: devuelve los 500 más visitados y deja el resto a la generación bajo demanda de la primera visita. En Pages hacías lo mismo con `paths` parcial + `blocking`; la idea es idéntica.

Comprobación tras migrar una página: en `next build`, la ruta aparece como `●` (SSG con ISR) con el número de rutas generadas entre paréntesis. Visita una ruta no incluida: debe tardar lo que tarde la consulta la primera vez y ser instantánea la segunda. Y cuando cambies un producto, llama a `revalidatePath` y verifica que la siguiente visita trae el dato nuevo sin esperar los 60 s.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Responde de forma breve y directa, con el código justo."},
            {
                "role": "user",
                "content": "¿Cómo configuro ISR en el App Router y cómo compruebo que de verdad está regenerando? Blog con posts que cambian poco.",
            },
            {
                "role": "assistant",
                "content": r"""ISR en el App Router es una constante exportada por página más, opcionalmente, invalidación bajo demanda.

```tsx
// app/blog/[slug]/page.tsx
export const revalidate = 3600; // segundos: como máximo una regeneración por hora y por ruta

export async function generateStaticParams() {
  const posts = await getAllPosts();
  return posts.map((p) => ({ slug: p.slug }));
}

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getPost(slug);
  return <article>{post.body}</article>;
}
```

Cómo funciona: la página se genera en el build. Pasada una hora, la **siguiente** visita sigue recibiendo la versión cacheada (respuesta instantánea) y dispara la regeneración en segundo plano; la visita posterior ya ve la nueva. Nadie espera.

Para que un post editado se vea sin esperar la hora, invalida al guardar:

```ts
// donde ocurra la edición (Server Action o Route Handler de webhook del CMS)
import { revalidatePath } from "next/cache";

revalidatePath(`/blog/${slug}`);
revalidatePath("/blog"); // la lista también
```

Si los datos vienen de `fetch`, puedes afinar por petición en vez de por página: `fetch(url, { next: { revalidate: 3600, tags: ["posts"] } })` y luego `revalidateTag("posts")`.

Comprobar que regenera, sin adivinar:

1. **En el build**: la ruta sale como `●  /blog/[slug]` con «(ISR: 3600 Seconds)» y el número de rutas generadas.
2. **En producción** (`npm run build && npm start`): pide la página con `curl -sI localhost:3000/blog/mi-post | grep -i x-nextjs-cache`. Verás `HIT` (servida de caché), `STALE` (caducada, servida mientras regenera) o `MISS` (generada ahora). La secuencia esperada tras la hora es `STALE` → `HIT` con el contenido nuevo.
3. **Tras `revalidatePath`**: la primera petición debe dar `MISS` y mostrar el cambio.

En `next dev` no hay ISR (todo se renderiza en cada petición); prueba siempre contra el build de producción.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito la web en español e inglés con URLs tipo `/es/productos` y `/en/products`, detectando el idioma del navegador la primera vez. En Pages Router había `i18n` en `next.config`; en App Router no veo nada.",
            },
            {
                "role": "assistant",
                "content": r"""Correcto: la opción `i18n` de `next.config` solo funciona con Pages Router. En el App Router la internacionalización se construye con tres piezas que ya conoces: un segmento dinámico `[lang]`, un middleware que detecta y redirige, y diccionarios cargados en el servidor.

```
app/
  [lang]/
    layout.tsx
    page.tsx
    products/
      page.tsx
  dictionaries/
    es.json
    en.json
middleware.ts
i18n-config.ts
```

```ts
// i18n-config.ts
export const locales = ["es", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";
```

```ts
// middleware.ts
import { NextResponse, type NextRequest } from "next/server";
import Negotiator from "negotiator";
import { match } from "@formatjs/intl-localematcher";
import { defaultLocale, locales } from "./i18n-config";

function detectLocale(request: NextRequest): string {
  const cookie = request.cookies.get("locale")?.value;
  if (cookie && locales.includes(cookie as (typeof locales)[number])) return cookie;

  const headers = { "accept-language": request.headers.get("accept-language") ?? "" };
  const preferred = new Negotiator({ headers }).languages();
  return match(preferred, locales, defaultLocale);
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasLocale = locales.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`));
  if (hasLocale) return NextResponse.next();

  const locale = detectLocale(request);
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next|api|favicon.ico|.*\\..*).*)"], // todo salvo estáticos y API
};
```

```ts
// app/dictionaries/index.ts
import "server-only";
import type { Locale } from "@/i18n-config";

const loaders = {
  es: () => import("./es.json").then((m) => m.default),
  en: () => import("./en.json").then((m) => m.default),
};

export const getDictionary = (locale: Locale) => loaders[locale]();
```

```tsx
// app/[lang]/layout.tsx
import { locales, type Locale } from "@/i18n-config";

export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export default async function LangLayout({ children, params }: { children: React.ReactNode; params: Promise<{ lang: Locale }> }) {
  const { lang } = await params;
  return (
    <html lang={lang}>
      <body>{children}</body>
    </html>
  );
}
```

```tsx
// app/[lang]/products/page.tsx
import { getDictionary } from "@/app/dictionaries";
import type { Locale } from "@/i18n-config";

export default async function ProductsPage({ params }: { params: Promise<{ lang: Locale }> }) {
  const { lang } = await params;
  const t = await getDictionary(lang);
  return <h1>{t.products.title}</h1>;
}
```

Decisiones:

- **La cookie manda sobre `Accept-Language`.** El navegador dice «inglés» pero el usuario eligió español en el selector: la cookie `locale` guarda su elección y el middleware la respeta. El selector de idioma la escribe (Server Action con `cookies().set`) y navega a la misma ruta con el otro prefijo.
- **`negotiator` + `@formatjs/intl-localematcher`** hacen la negociación bien (`es-MX` → `es`, calidad `q=`); un `split(",")[0]` a mano falla en esos casos.
- **Los diccionarios se cargan con `import()` dinámico en servidor**: solo el idioma pedido se lee, y nunca viaja al cliente el JSON de todos los idiomas. `server-only` garantiza que nadie los importe desde un Client Component.
- **`generateStaticParams` en el layout** permite prerenderizar las dos versiones de cada página estática.

Lo que no cubre esta base y para lo que existe `next-intl`: plurales, fechas y números con `Intl` por locale, traducciones dentro de Client Components sin pasar el diccionario por props, y mensajes con variables tipadas. Si el proyecto va a tener más de dos idiomas o traductores externos, adopta `next-intl` desde el principio; su estructura es la misma que esta (`[locale]` + middleware), así que no se tira nada.""",
            },
            {
                "role": "user",
                "content": "¿Y las rutas traducidas? Quiero `/es/productos` y `/en/products`, no `/es/products`.",
            },
            {
                "role": "assistant",
                "content": r"""Con **rewrites**: la carpeta sigue siendo una (`app/[lang]/products`), y la URL pública en español se reescribe internamente a ella. El usuario ve `/es/productos`; Next renderiza `products`.

```ts
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/es/productos", destination: "/es/products" },
      { source: "/es/productos/:slug", destination: "/es/products/:slug" },
      { source: "/es/carrito", destination: "/es/cart" },
    ];
  },
};

export default nextConfig;
```

Para no mantener la lista a mano, genera los rewrites desde un mapa de segmentos:

```ts
// i18n-routes.ts
export const pathnames = {
  "/products": { es: "/productos", en: "/products" },
  "/products/[slug]": { es: "/productos/:slug", en: "/products/:slug" },
  "/cart": { es: "/carrito", en: "/cart" },
} as const;
```

```ts
// next.config.ts
import { pathnames } from "./i18n-routes";

async rewrites() {
  return Object.entries(pathnames).flatMap(([internal, byLocale]) =>
    Object.entries(byLocale)
      .filter(([, publicPath]) => publicPath !== internal.replace("[slug]", ":slug"))
      .map(([locale, publicPath]) => ({
        source: `/${locale}${publicPath}`,
        destination: `/${locale}${internal.replace("[slug]", ":slug")}`,
      })),
  );
}
```

El mismo mapa alimenta un helper `localizedHref("/products", "es")` para que los `<Link>` generen la URL pública correcta; sin él, un enlace a `/es/products` funcionaría (la carpeta existe) pero expondría la URL en inglés.

Dos cosas que hay que cuadrar:

1. **El middleware se ejecuta antes del rewrite** y ve la URL pública (`/es/productos`). Como empieza por un locale válido, hace `NextResponse.next()` y el rewrite actúa después. No hay conflicto.
2. **SEO**: cada idioma debe declarar sus alternativas. En `generateMetadata` de cada página añade `alternates: { languages: { es: "/es/productos", en: "/en/products" } }`, usando el mismo mapa.

`next-intl` incluye exactamente este mecanismo (`pathnames` en su configuración de navegación), con los helpers de `Link` y `redirect` ya resueltos; si ya estás valorándolo, este es el punto en el que compensa.

Verificación: `curl -sI localhost:3000/es/productos` debe dar `200` (no `307`), y `curl -sI localhost:3000/es/products` también `200`; si quieres que la URL interna no sea accesible, añade un `redirect` permanente de `/es/products` a `/es/productos` en la misma configuración.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "My layout and page both need the current workspace (name, plan, member count) from the database. I'm fetching it twice per request. What's the idiomatic way to share it in the App Router? Props from layout to page don't exist, right?",
            },
            {
                "role": "assistant",
                "content": r"""Right: a layout cannot pass props to its page, by design (they render independently and in parallel). The idiomatic answer is **request-scoped memoization**: both call the same function, and the function runs once per request.

For a database call, wrap it in React's `cache`:

```ts
// lib/workspace.ts
import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { db } from "@/lib/db";

export const getCurrentWorkspace = cache(async () => {
  const workspaceId = (await cookies()).get("workspace")?.value;
  if (!workspaceId) return null;
  return db.workspace.findUnique({
    where: { id: workspaceId },
    include: { _count: { select: { members: true } } },
  });
});
```

```tsx
// app/(app)/layout.tsx
import { getCurrentWorkspace } from "@/lib/workspace";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const workspace = await getCurrentWorkspace(); // query runs here…
  return (
    <>
      <header>{workspace?.name}</header>
      {children}
    </>
  );
}
```

```tsx
// app/(app)/settings/page.tsx
import { getCurrentWorkspace } from "@/lib/workspace";

export default async function SettingsPage() {
  const workspace = await getCurrentWorkspace(); // …and this returns the same promise
  return <p>Plan: {workspace?.plan}</p>;
}
```

`cache` keys on the function arguments (none here, so one entry) and lives for the duration of a single server render. The second call gets the same in-flight promise, so there is exactly one query even though layout and page start at the same time. Nothing leaks between requests or users.

If the data comes from `fetch` instead of a DB client, you do not need `cache`: Next memoizes identical `GET` fetches (same URL and options) within a request automatically.

Two related tools that answer different questions:

| Need | Tool | Scope |
|---|---|---|
| "Call once per request" | `cache()` from `react` | one server render |
| "Keep the result across requests" | `unstable_cache(fn, keys, { revalidate, tags })` from `next/cache` | the data cache, shared by all requests until revalidated |
| Same as above, as a directive | `"use cache"` at the top of a function or file | experimental in 15 (`experimental.useCache` or `dynamicIO`); stable form arrives in 16 |

They compose: `cache(unstable_cache(...))` is not needed, since `unstable_cache` already dedupes, but `cache` around a function that reads `cookies()` is the right call because `unstable_cache` cannot read request APIs inside it (the cached result must not depend on the request).

One pattern to avoid: a Context provider in the layout that holds the workspace for client components. It works, but it forces the workspace into the client bundle and the layout into the hydration path. If a client component needs the workspace name, pass it as a prop from the nearest server component that already has it.

Check it: add `console.log("workspace query")` inside the function body before the `db` call, load `/settings`, and confirm the server terminal prints it once per page load, not twice. Then remove the `cache` wrapper and watch it print twice; that is the behavior you had.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "How should I test a Next 15 app? Specifically: a client component with state, a Server Action that validates and writes, and an async Server Component page. I have Vitest set up but the async page test fails with a weird promise error.",
            },
            {
                "role": "assistant",
                "content": r"""Three different things, three different tools. The "weird promise error" is expected: **async Server Components are not supported by Vitest or React Testing Library** (the Next docs say so explicitly), because they need the RSC renderer. Those get end-to-end tests.

**1. Client component with state: Vitest + Testing Library.**

```ts
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()], // tsconfigPaths resolves the "@/..." alias
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: true },
});
```

```tsx
// app/products/product-list.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ProductList } from "./product-list";

vi.mock("./actions", () => ({
  reloadProducts: vi.fn().mockResolvedValue([{ id: "1", name: "Fresh" }]),
}));

test("reload replaces the list with server data", async () => {
  const user = userEvent.setup();
  render(<ProductList initial={[{ id: "0", name: "Stale" }]} />);

  await user.click(screen.getByRole("button", { name: /reload/i }));

  expect(await screen.findByText("Fresh")).toBeInTheDocument();
  expect(screen.queryByText("Stale")).not.toBeInTheDocument();
});
```

Mock the Server Action module, not `fetch`: from the component's point of view the action is just an async function, and that is the boundary you want to control. If the component uses `next/navigation`, mock that module too (`useRouter: () => ({ push: vi.fn(), refresh: vi.fn() })`).

**2. Server Action: a plain unit test of the function.** It is an async function that takes `FormData`; call it directly with the dependencies mocked.

```ts
// app/posts/actions.test.ts
import { vi } from "vitest";
import { createPost } from "./actions";

vi.mock("@/lib/db", () => ({ db: { post: { create: vi.fn().mockResolvedValue({ id: "42" }) } } }));
vi.mock("@/lib/session", () => ({ getSession: vi.fn().mockResolvedValue({ userId: "u1" }) }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("next/navigation", () => ({
  redirect: vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT:${url}`);
  }),
}));

function form(fields: Record<string, string>) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.set(k, v);
  return fd;
}

test("returns field errors for a short title", async () => {
  const state = await createPost({}, form({ title: "ab", body: "x".repeat(30) }));
  expect(state.errors?.title?.[0]).toMatch(/3/);
});

test("creates the post, revalidates and redirects", async () => {
  const { revalidatePath } = await import("next/cache");
  await expect(createPost({}, form({ title: "Hello", body: "x".repeat(30) }))).rejects.toThrow("NEXT_REDIRECT:/posts/42");
  expect(revalidatePath).toHaveBeenCalledWith("/posts");
});
```

The `redirect` mock throws on purpose: the real one throws too, and the test asserts both the destination and that `revalidatePath` ran before it.

**3. Async Server Component page: Playwright.**

```ts
// e2e/products.spec.ts
import { test, expect } from "@playwright/test";

test("product page renders server data and streams reviews", async ({ page }) => {
  await page.goto("/products/42");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Nordic chair");
  await expect(page.getByRole("list", { name: /reviews/i })).toBeVisible(); // arrives via streaming
});
```

```ts
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  webServer: { command: "npm run build && npm run start", url: "http://localhost:3000", reuseExistingServer: !process.env.CI },
  use: { baseURL: "http://localhost:3000" },
});
```

Run e2e against the **production build**, not `next dev`: caching, ISR and streaming behave differently in dev, and those are precisely what a page test should cover. Seed the test database before the run (a global setup script) so `/products/42` exists.

What not to do: unit-testing the page by extracting its JSX into a sync component you render with props. You end up testing a component that does not exist in production and skipping the data layer, which is where App Router bugs actually live (`await params`, cache options, `notFound()`).

Split that keeps the suite fast: dozens of Vitest tests for client components and actions (milliseconds each), a handful of Playwright tests per critical page (seconds each). Verify the setup with `npx vitest run` and `npx playwright test`; both should pass green before you add the next test.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "For a contact form in Next 15, should I use a Route Handler (`app/api/contact/route.ts`) or a Server Action? I keep seeing both. Please answer in Spanish.",
            },
            {
                "role": "assistant",
                "content": r"""Para un formulario que solo usa tu propia app, **Server Action**. Un Route Handler es para cuando el consumidor **no** es tu UI de React.

| Criterio | Server Action | Route Handler |
|---|---|---|
| Quién la llama | tus componentes, con `<form action>` o como función | cualquier cliente HTTP: app móvil, webhook, otro servicio, `curl` |
| Contrato | función TypeScript tipada; sin URL, sin serialización manual | URL + método + JSON: una API pública que debes versionar |
| Estado de envío y errores | `useActionState` te da `isPending` y el resultado sin `fetch` ni `useState` | lo gestionas tú en el cliente |
| Funciona sin JavaScript | sí (envío nativo del formulario, mejora progresiva) | no, salvo que escribas un formulario HTML clásico |
| Integración con caché | `revalidatePath`/`revalidateTag` y refresco del router al terminar | igual de disponible, pero el cliente debe refrescar por su cuenta |
| Método HTTP | siempre POST | el que definas (GET, PUT, DELETE…) |
| Caché de respuesta | no aplica | configurable (`dynamic`, `revalidate`) |

El formulario de contacto con una acción:

```ts
// app/contact/actions.ts
"use server";

import { z } from "zod";
import { sendMail } from "@/lib/mail";

const Schema = z.object({
  email: z.string().email("Email inválido"),
  message: z.string().trim().min(10, "Cuéntanos un poco más"),
});

export async function sendContact(_prev: { ok?: boolean; error?: string }, formData: FormData) {
  const parsed = Schema.safeParse(Object.fromEntries(formData));
  if (!parsed.success) return { error: parsed.error.issues[0].message };
  await sendMail({ to: "hola@example.com", replyTo: parsed.data.email, text: parsed.data.message });
  return { ok: true };
}
```

```tsx
// app/contact/contact-form.tsx
"use client";

import { useActionState } from "react";
import { sendContact } from "./actions";

export function ContactForm() {
  const [state, action, isPending] = useActionState(sendContact, {});
  if (state.ok) return <p>Mensaje enviado. Te respondemos en 24 h.</p>;
  return (
    <form action={action}>
      <input name="email" type="email" required />
      <textarea name="message" required />
      {state.error && <p role="alert">{state.error}</p>}
      <button disabled={isPending}>{isPending ? "Enviando…" : "Enviar"}</button>
    </form>
  );
}
```

Cuándo elegir el Route Handler para el mismo formulario: si además lo envía una app móvil, si un tercero (un chatbot, Zapier) debe poder crear mensajes, o si necesitas un método distinto de POST. En ese caso, escribe la lógica una vez en `lib/contact.ts` y llámala desde ambos: la acción para la web y el handler para el resto. Lo que no conviene es que la web haga `fetch("/api/contact")` a mano cuando una acción le da lo mismo con menos código y mejora progresiva.

Un matiz de seguridad común a los dos: validar siempre en el servidor y comprobar la sesión si el envío requiere usuario. Una Server Action también es un endpoint POST alcanzable desde fuera; que no tenga URL visible no la hace privada.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""El `next build` me falla con esto en una página que lee `?q=` para la búsqueda:

```
⨯ useSearchParams() should be wrapped in a suspense boundary at page "/search". Read more: https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout
```

En desarrollo funciona perfectamente.""",
            },
            {
                "role": "assistant",
                "content": r"""`useSearchParams` en un Client Component obliga a renderizar ese componente en el cliente, porque los parámetros de la URL no se conocen al prerenderizar una página estática. Next necesita un `<Suspense>` por encima para poder enviar el resto del HTML estático y rellenar ese hueco en el navegador. Sin boundary, tendría que renunciar al prerender de **toda** la página, y desde la 15 eso es un error de build en vez de una degradación silenciosa.

Arreglo: envuelve el componente que usa el hook en `<Suspense>`, en la página de servidor:

```tsx
// app/search/page.tsx
import { Suspense } from "react";
import { SearchBox } from "./search-box";

export default function SearchPage() {
  return (
    <main>
      <h1>Buscar</h1>
      <Suspense fallback={<input disabled placeholder="Buscar…" />}>
        <SearchBox />
      </Suspense>
    </main>
  );
}
```

```tsx
// app/search/search-box.tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";

export function SearchBox() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get("q") ?? "";

  return (
    <input
      defaultValue={q}
      placeholder="Buscar…"
      onChange={(e) => router.replace(`/search?q=${encodeURIComponent(e.target.value)}`)}
    />
  );
}
```

El límite del Suspense marca **qué parte** depende de la URL; el `<h1>` y el resto del `<main>` se prerenderizan.

Por qué en desarrollo no fallaba: `next dev` nunca prerenderiza, todo se renderiza bajo demanda, así que el problema solo aparece cuando el build intenta generar HTML estático.

Dos alternativas según el caso:

- **Si la página debe leer `q` en el servidor** (para consultar la base de datos), no uses el hook: recibe `searchParams` como prop de la página (`{ searchParams }: { searchParams: Promise<{ q?: string }> }`) y hazle `await`. La página pasa a ser dinámica, que es lo correcto si su contenido depende de la búsqueda.
- **Si la página entera es dinámica por otra razón** (lee `cookies()`, tiene `export const dynamic = "force-dynamic"`), el error no aparece porque no hay prerender. Pero no fuerces lo dinámico solo para esquivar el aviso; el `<Suspense>` es la solución barata.

Verificación: `npm run build` termina y `/search` aparece como `○ (Static)`. Visita `/search?q=silla`: el input debe mostrar «silla» tras hidratar. Y mira el HTML con `curl`: el `<h1>` está, y en el sitio del input hay el fallback con un marcador de Suspense (`<!--$?-->`).""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "Tengo un catálogo con `app/products/[slug]/page.tsx`. ¿Cómo hago para que las páginas se generen en el build y que una URL inventada dé 404 en vez de intentar renderizar?",
            },
            {
                "role": "assistant",
                "content": r"""Con `generateStaticParams` para listar los slugs y `dynamicParams = false` para que cualquier slug que no esté en esa lista responda 404 directamente, sin ejecutar la página.

```tsx
// app/products/[slug]/page.tsx
import { notFound } from "next/navigation";
import { getAllProductSlugs, getProductBySlug } from "@/lib/catalog";

export const dynamicParams = false; // slug fuera de la lista → 404 sin renderizar

export async function generateStaticParams() {
  const slugs = await getAllProductSlugs(); // ["silla-nordica", "mesa-roble", …]
  return slugs.map((slug) => ({ slug }));
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) notFound(); // por si el dato desapareció entre el build y la visita
  return <h1>{product.name}</h1>;
}
```

Qué hace cada pieza:

- **`generateStaticParams`** se ejecuta en el build (y solo ahí) y devuelve un objeto por ruta. Next renderiza cada una y guarda el HTML.
- **`dynamicParams = false`** cambia el comportamiento por defecto. Sin esta línea, un slug desconocido se renderiza bajo demanda en la primera visita (útil cuando hay más productos de los que querés generar); con ella, Next ni siquiera llama a tu componente: 404 inmediato, cero consultas a la base.
- **El `notFound()` igual queda**: si un producto se borra después del build y alguien tiene la URL, la página cacheada sigue existiendo hasta que la invalidás. El chequeo cubre ese hueco cuando regenera.

Fijate en la salida de `next build`: la ruta tiene que aparecer como `●  /products/[slug]` con la lista de slugs generados debajo (o un «+N more» si son muchos). Si aparece como `ƒ`, es que algo en la página usa una API dinámica (`cookies()`, `headers()`, `searchParams`) y eso te rompe el prerender.

Para probar el 404: `curl -sI localhost:3000/products/no-existe` contra el build de producción (`npm run build && npm start`) tiene que devolver `404` y, en la terminal del servidor, **no** debe aparecer ningún log de `getProductBySlug`.""",
            },
            {
                "role": "user",
                "content": "Bárbaro. Pero son 80.000 productos, no puedo generar todos en el build, tarda una eternidad.",
            },
            {
                "role": "assistant",
                "content": r"""Entonces el enfoque cambia: generás en el build **solo los que importan** y dejás el resto a la generación bajo demanda, que es exactamente para lo que existe `dynamicParams = true` (el valor por defecto).

```tsx
// app/products/[slug]/page.tsx
import { notFound } from "next/navigation";
import { getTopProductSlugs, getProductBySlug } from "@/lib/catalog";

export const revalidate = 86400; // cada página se regenera como máximo una vez al día

// dynamicParams queda en true (por defecto): los slugs no listados se generan en la primera visita

export async function generateStaticParams() {
  // Los 1.000 más visitados: el build tarda minutos, no horas
  const slugs = await getTopProductSlugs(1000);
  return slugs.map((slug) => ({ slug }));
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const product = await getProductBySlug(slug);
  if (!product) notFound();
  return <h1>{product.name}</h1>;
}
```

Cómo se comporta ahora:

| Situación | Qué pasa |
|---|---|
| Slug entre los 1.000 del build | HTML listo, respuesta instantánea |
| Slug real pero no generado | primera visita: se renderiza y se cachea (el usuario espera lo que tarde la consulta); visitas siguientes: instantáneas |
| Slug inventado | se renderiza, `getProductBySlug` devuelve `null`, `notFound()` → 404; el 404 también se cachea |
| Producto editado | `revalidatePath(`/products/${slug}`)` desde la acción de guardado, o esperás al `revalidate` diario |

Dos cuidados con 80.000 rutas:

1. **El 404 de slugs inventados cuesta una consulta** la primera vez. Si te preocupa que alguien barra URLs al azar, poné un rate limit en el middleware para `/products/:slug` o un índice en memoria de slugs válidos (un `Set` cargado con `unstable_cache`) para cortar antes de ir a la base.
2. **La caché vive en el filesystem** de cada instancia. Con varias réplicas detrás de un balanceador, cada una genera su copia; no es un problema de corrección, solo de trabajo repetido. Si eso pesa, configurá un `cacheHandler` compartido en `next.config.ts`.

Criterio para elegir cuántos generar: medí el tiempo de build por página (suele ser 50-200 ms) y el tráfico. Si el 90 % de las visitas cae en 2.000 productos, generá 2.000. El build es una inversión en los que de verdad se visitan; el resto se paga de a uno, cuando alguien lo pide.

Verificación: `next build` tiene que terminar en minutos y listar «1000 paths». Después, visitá un slug que no esté en la lista: en la terminal del servidor vas a ver la consulta una sola vez; la segunda visita no la hace.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala el problema, explica el porqué y da el arreglo."},
            {
                "role": "user",
                "content": r"""Revisa esta Server Action para borrar un proyecto. La página la llama con un formulario que tiene un input oculto con el id del usuario.

```ts
"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/lib/db";

export async function deleteProject(formData: FormData) {
  const projectId = formData.get("projectId") as string;
  const userId = formData.get("userId") as string;
  const isAdmin = formData.get("isAdmin") === "true";

  if (isAdmin) {
    await db.project.delete({ where: { id: projectId } });
  } else {
    await db.project.delete({ where: { id: projectId, ownerId: userId } });
  }
  revalidatePath("/projects");
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""**Problema principal: la acción confía en datos que controla el cliente.** `userId` e `isAdmin` llegan en el `FormData`, y el `FormData` lo construye el navegador. Cualquiera puede abrir DevTools, cambiar el input oculto a `isAdmin=true` o al `userId` de otra persona, y borrar cualquier proyecto. Una Server Action es un endpoint POST público: que el formulario tenga un campo oculto no significa que el servidor pueda fiarse de él.

Hay tres fallos más pequeños que señalo después. Primero el arreglo del grave:

```ts
"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { db } from "@/lib/db";
import { getSession } from "@/lib/session";

const Input = z.object({ projectId: z.string().uuid() });

export async function deleteProject(formData: FormData): Promise<{ error?: string }> {
  // 1. Identidad y permisos: SIEMPRE desde la sesión del servidor, nunca del formulario
  const session = await getSession();
  if (!session) return { error: "No has iniciado sesión" };

  // 2. Validación del único dato que legítimamente viene del cliente
  const parsed = Input.safeParse({ projectId: formData.get("projectId") });
  if (!parsed.success) return { error: "Proyecto inválido" };
  const { projectId } = parsed.data;

  // 3. Autorización contra la base de datos, no contra un flag
  const user = await db.user.findUniqueOrThrow({ where: { id: session.userId }, select: { role: true } });
  const where = user.role === "admin" ? { id: projectId } : { id: projectId, ownerId: session.userId };

  // 4. deleteMany no lanza si no coincide nada: devuelve count y nos deja responder bien
  const { count } = await db.project.deleteMany({ where });
  if (count === 0) return { error: "El proyecto no existe o no tienes permiso" };

  revalidatePath("/projects");
  return {};
}
```

Y el formulario ya no lleva `userId` ni `isAdmin`:

```tsx
<form action={deleteProject}>
  <input type="hidden" name="projectId" value={project.id} />
  <button type="submit">Borrar</button>
</form>
```

Los tres fallos menores del original:

1. **`formData.get("projectId") as string`** convierte un `null` (campo ausente) en un `string` solo para TypeScript; en runtime `db.project.delete({ where: { id: null } })` lanza. Con zod el caso ausente es un error de validación con mensaje.
2. **`delete` lanza si no encuentra la fila** (`RecordNotFound` en Prisma). Para un usuario sin permiso, eso se traduce en un error 500 genérico en vez de un mensaje. `deleteMany` con `count` permite distinguir y responder.
3. **La acción no devuelve nada**, así que la UI no puede mostrar «no tienes permiso». Devolver `{ error }` y leerlo con `useActionState` cierra el circuito.

Dos refuerzos que recomiendo en toda acción destructiva:

- **Rate limiting** por sesión en las acciones de borrado; una acción que se puede invocar en bucle desde un script es un vector de denegación de servicio barato.
- **Una capa `lib/projects.ts`** con `deleteProjectAs(session, projectId)` que contenga la regla de autorización, de modo que el Route Handler de la API móvil y esta acción compartan exactamente la misma comprobación. Las reglas de permisos duplicadas se desincronizan.

Prueba de regresión, como test unitario de la función:

```ts
test("un usuario no puede borrar el proyecto de otro aunque manipule el formulario", async () => {
  mockSession({ userId: "u2" });
  const fd = new FormData();
  fd.set("projectId", PROJECT_OF_U1);
  fd.set("isAdmin", "true"); // ignorado por diseño
  fd.set("userId", "u1");    // ignorado por diseño
  expect(await deleteProject(fd)).toEqual({ error: "El proyecto no existe o no tienes permiso" });
  expect(await db.project.findUnique({ where: { id: PROJECT_OF_U1 } })).not.toBeNull();
});
```""",
            },
        ]
    },
]
