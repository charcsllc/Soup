"""Frameworks potentes y menos conocidos: qué los hace distintos, con casos reales.

30 filas, 2-3 por tecnología: Astro 5, Qwik, HTMX, Phoenix LiveView, Bun + Elysia, Hono en
Cloudflare Workers, Leptos y Dioxus, Tauri 2, React Router v7 (antes Remix), Effect-TS,
Zustand y Jotai, Deno 2 y Fresh, SvelteKit avanzado, Nuxt server routes y Nitro. Varias filas
comparan dos opciones para un caso concreto y recomiendan una. Sigue entrenamiento/GUIA_DE_ESTILO.md.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Astro 5: islas y directivas client:* con React y Svelte (SISTEMA, intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy armando un sitio de marketing con Astro 5 y necesito un carrusel hecho en React y un formulario de newsletter en Svelte. ¿Cómo funcionan las islas y qué directiva `client:` uso en cada uno?",
            },
            {
                "role": "assistant",
                "content": """La idea central de Astro: **todo se renderiza a HTML estático y no se envía JavaScript, salvo donde tú lo pidas.** Un componente de React o Svelte sin directiva se ejecuta solo en el servidor (o en el build) y llega al navegador como HTML inerte. Con una directiva `client:*` se convierte en una **isla**: un trozo de la página que se hidrata de forma independiente, con su propio JavaScript, mientras el resto sigue siendo HTML.

Las directivas deciden **cuándo** se hidrata cada isla:

| Directiva | Hidrata... | Úsala para |
|---|---|---|
| `client:load` | al cargar la página | lo interactivo que se ve nada más entrar (un menú) |
| `client:idle` | cuando el navegador queda libre (`requestIdleCallback`) | interactivo pero no urgente |
| `client:visible` | cuando entra en pantalla (`IntersectionObserver`) | lo que está por debajo del pliegue |
| `client:media="(max-width: 50em)"` | cuando se cumple la media query | lo que solo es interactivo en móvil |
| `client:only="react"` | solo en el cliente, sin HTML de servidor | componentes que dependen de `window` |

Para tu caso: el carrusel suele estar más abajo, así que `client:visible`; el newsletter no es urgente, `client:idle`.

```bash
npx astro add react svelte
```

```astro
---
// src/pages/index.astro
import Layout from "../layouts/Layout.astro";
import Hero from "../components/Hero.astro";
import ProductCarousel from "../components/ProductCarousel.tsx";
import NewsletterForm from "../components/NewsletterForm.svelte";
import { getFeaturedProducts } from "../lib/products";

// Se ejecuta en el build (o en el servidor si la ruta es dinámica), nunca en el navegador.
const products = await getFeaturedProducts();
---
<Layout title="Inicio">
  <Hero />
  <ProductCarousel client:visible products={products} />
  <NewsletterForm client:idle />
</Layout>
```

```svelte
<!-- src/components/NewsletterForm.svelte (Svelte 5) -->
<script lang="ts">
  let email = $state("");
  let status = $state<"idle" | "sending" | "done" | "error">("idle");

  async function subscribe(event: SubmitEvent) {
    event.preventDefault();
    status = "sending";
    try {
      const response = await fetch("/api/newsletter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      status = response.ok ? "done" : "error";
    } catch {
      status = "error";
    }
  }
</script>

<form onsubmit={subscribe}>
  <label for="newsletter-email">Correo electrónico</label>
  <input id="newsletter-email" type="email" bind:value={email} required />
  <button disabled={status === "sending"}>Suscribirme</button>
  {#if status === "done"}<p role="status">Listo. Revisa tu bandeja de entrada.</p>{/if}
  {#if status === "error"}<p role="alert">No se pudo completar la suscripción. Inténtalo de nuevo.</p>{/if}
</form>
```

Lo que conviene saber antes de que te muerda:

- **Las props de una isla viajan serializadas como JSON** dentro del HTML. Datos planos sí; funciones, clases o fechas con métodos, no. `products` funciona porque es un array de objetos simples.
- **Cada isla es una aplicación aparte.** El carrusel de React y el formulario de Svelte no comparten contexto. Si dos islas necesitan compartir estado (un contador de carrito en la cabecera y un botón «añadir» en otra isla), usa una store independiente del framework, como `nanostores` con sus adaptadores para React y Svelte.
- **`Hero.astro` no envía nada de JavaScript.** Mantén como `.astro` todo lo que no necesite interacción; es la mayor parte de un sitio de marketing.
- **El endpoint `/api/newsletter`** tiene que ejecutarse bajo demanda: en Astro 5 eso es un archivo en `src/pages/api/` con `export const prerender = false` y un adaptador de servidor (Node, Vercel, Netlify...) configurado.

Comprobación: `npm run build && npm run preview`, abre la pestaña *Network* filtrando por JS y recarga. Al entrar solo debe descargarse el código del formulario (cuando el navegador queda libre); el de React aparece únicamente al hacer scroll hasta el carrusel.""",
            },
        ]
    },
    # 2) Astro 5: content collections con Content Layer; entry.render() ya no existe (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Actualicé el blog de Astro 4 a Astro 5 y ahora la página de cada artículo falla con `TypeError: post.render is not a function`:

```astro
---
import { getCollection } from "astro:content";

export async function getStaticPaths() {
  const posts = await getCollection("blog");
  return posts.map((post) => ({ params: { slug: post.slug }, props: { post } }));
}

const { post } = Astro.props;
const { Content } = await post.render();
---
<Content />
```""",
            },
            {
                "role": "assistant",
                "content": """En Astro 5 las colecciones pasaron a la **Content Layer API**, y una de sus consecuencias es que las entradas ya no traen el método `.render()`: ahora se usa la función `render()` importada de `astro:content`. Con la nueva API, además, el identificador de cada entrada es `id`, no `slug`.

**1. La configuración cambia de sitio y declara un *loader*.** Pasa de `src/content/config.ts` a `src/content.config.ts`:

```ts
// src/content.config.ts
import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const blog = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    draft: z.boolean().default(false),
    tags: z.array(z.string()).default([]),
  }),
});

export const collections = { blog };
```

**2. La página usa `render(post)` y `post.id`:**

```astro
---
// src/pages/blog/[id].astro
import { getCollection, render } from "astro:content";
import BlogLayout from "../../layouts/BlogLayout.astro";

export async function getStaticPaths() {
  const posts = await getCollection("blog", ({ data }) => !data.draft);
  return posts.map((post) => ({ params: { id: post.id }, props: { post } }));
}

const { post } = Astro.props;
const { Content } = await render(post);
---
<BlogLayout title={post.data.title} description={post.data.description}>
  <h1>{post.data.title}</h1>
  <time datetime={post.data.pubDate.toISOString()}>
    {post.data.pubDate.toLocaleDateString("es-ES", { dateStyle: "long" })}
  </time>
  <Content />
</BlogLayout>
```

El archivo de la ruta pasa de `[slug].astro` a `[id].astro` para que el nombre del parámetro coincida.

**Qué ganas con el cambio**, para que no sea solo «la API cambió»:

- **Los *loaders* desacoplan el contenido de la carpeta.** `glob` lee archivos locales, pero el mismo `defineCollection` puede cargar desde un CMS o una API con otro loader, y el resto del código (`getCollection`, `render`, el schema con zod) no cambia.
- **Builds más rápidos** en sitios grandes, porque el contenido se cachea entre builds y solo se reprocesa lo que cambió.

**La trampa de la migración: las URLs.** El `id` lo genera el loader a partir de la ruta del archivo; si en Astro 4 usabas un `slug` personalizado en el frontmatter, comprueba que las URLs resultantes son las mismas, o romperás enlaces externos y posicionamiento. El loader `glob` respeta un campo `slug` del frontmatter como id cuando existe.

Comprobación: antes de migrar, guarda la lista de páginas generadas (`find dist -name "*.html" | sort > antes.txt`); después de migrar, genera la nueva lista y compáralas con `diff`. Debe salir vacío. Ejecuta también `npx astro sync` para regenerar los tipos: `post.data.pubDate` debe tiparse como `Date`.""",
            },
        ]
    },
    # 3) Qwik: resumabilidad frente a hidratación (intermedio-avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Leo que Qwik no «hidrata» sino que «resume». ¿Qué significa en la práctica y en qué se nota frente a React o frente a las islas de Astro?",
            },
            {
                "role": "assistant",
                "content": """Significa que el navegador **no vuelve a ejecutar tus componentes al cargar la página**. Para verlo, compara las tres estrategias con la misma página de producto renderizada en el servidor:

**Hidratación (React, Vue, SvelteKit...).** El servidor envía HTML. Luego el navegador descarga el JavaScript de **todos** los componentes de la página, los vuelve a ejecutar para reconstruir el estado y el árbol de componentes, y por último engancha los manejadores de eventos. Hasta que termina, la página se ve pero no responde. El coste crece con la complejidad de la página, y en un móvil modesto se mide en segundos.

**Islas (Astro).** Igual que la hidratación, pero solo para las partes marcadas como interactivas. Mucho menos trabajo, pero cada isla sigue hidratándose entera, y tienes que decidir a mano dónde están las fronteras.

**Resumabilidad (Qwik).** El servidor **serializa en el HTML** el estado de la aplicación y, en cada elemento interactivo, una referencia al código del manejador (un atributo como `on:click="chunk-a1b2.js#addToCart"`). El navegador carga un script diminuto (el *qwikloader*, alrededor de 1 KB) que escucha eventos de forma global. Cuando el usuario hace clic, descarga **solo** el fragmento con ese manejador y lo ejecuta con el estado ya serializado. No se reejecuta ningún componente al arrancar: la aplicación «continúa» donde la dejó el servidor.

Cómo se escribe, con Qwik 1.x:

```tsx
import { component$, useSignal } from "@builder.io/qwik";

export const AddToCart = component$<{ productId: string }>(({ productId }) => {
  const count = useSignal(0);
  const status = useSignal<"idle" | "saving" | "error">("idle");

  return (
    <div>
      <button
        onClick$={async () => {
          status.value = "saving";
          const response = await fetch("/api/cart", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ productId }),
          });
          if (response.ok) {
            count.value++;
            status.value = "idle";
          } else {
            status.value = "error";
          }
        }}
      >
        Añadir al carrito ({count.value})
      </button>
      {status.value === "error" && <p role="alert">No se pudo añadir</p>}
    </div>
  );
});
```

El `$` del final (`component$`, `onClick$`) es la clave: marca una **frontera de carga perezosa**. El optimizador de Qwik extrae cada función con `$` a su propio fragmento de código, y por eso puede descargarse por separado.

**Dónde se nota:**

- Páginas grandes y muy interactivas (tiendas, dashboards públicos) en móviles de gama media: el tiempo hasta que la página responde deja de depender de cuánto JavaScript tiene.
- Métricas como *Total Blocking Time* e *Interaction to Next Paint*, que la hidratación castiga.

**Dónde no compensa:**

- Páginas pequeñas o aplicaciones tras login donde el JavaScript ya está en caché: la hidratación es barata y el ecosistema de React pesa más.
- Equipos que dependen de muchas librerías de React: Qwik tiene un puente para usarlas (`qwikify$`), pero esas partes vuelven a hidratarse.

**Los costes**: las funciones con `$` solo pueden capturar valores serializables (es el error más habitual al empezar), y la primera interacción puede tener que descargar un fragmento. Qwik lo mitiga precargando los fragmentos probables en segundo plano. Y un apunte de versiones: la rama 2 de Qwik renombra el paquete a `@qwik.dev/core`; lo de arriba es la API estable 1.x.

Comprobación: en la pestaña *Network*, con la caché desactivada, carga una página de Qwik. Al entrar solo verás el HTML y el qwikloader; al pulsar el botón por primera vez aparecerá la descarga de un fragmento pequeño con el manejador. Repite con la misma página en una app de React hidratada y compara el JavaScript descargado antes del primer clic.""",
            },
        ]
    },
    # 4) Qwik: error de serialización al capturar una instancia de clase en un $ (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """En Qwik, al cargar esta página en dev sale `Error: Code(3): Only primitive and object literals can be serialized`. ¿Qué no se puede serializar?

```tsx
import { component$, useSignal } from "@builder.io/qwik";
import { CartService } from "~/lib/cart-service";

export const AddButton = component$<{ productId: string }>(({ productId }) => {
  const added = useSignal(false);
  const service = new CartService("/api/cart");

  return (
    <button onClick$={async () => { await service.add(productId); added.value = true; }}>
      Añadir
    </button>
  );
});
```""",
            },
            {
                "role": "assistant",
                "content": """`service`. Es una instancia de una clase, y el manejador `onClick$` la captura.

**Por qué importa lo que captura un `$`.** Todo lo que lleva `$` es una frontera de carga perezosa: Qwik puede descargar ese código mucho después, en el navegador, sin haber vuelto a ejecutar el componente. Para que el manejador funcione entonces, todas las variables que captura del componente tienen que viajar **serializadas en el HTML**. Qwik sabe serializar primitivos, objetos y arrays literales, señales, stores, props y otras funciones `$`. Una instancia de `CartService` tiene prototipo y métodos, y no hay forma de escribirla en el HTML y reconstruirla en el navegador. Por eso falla al renderizar en el servidor, cuando intenta serializar la página, y no al hacer clic.

El arreglo es **no capturarla**: crear el servicio dentro del manejador, a partir de datos que sí se serializan.

```tsx
import { $, component$, useSignal } from "@builder.io/qwik";
import { CartService } from "~/lib/cart-service";

export const AddButton = component$<{ productId: string }>(({ productId }) => {
  const added = useSignal(false);

  const addToCart = $(async () => {
    const service = new CartService("/api/cart"); // se crea en el navegador, al hacer clic
    await service.add(productId);                 // productId es un string: serializable
    added.value = true;
  });

  return (
    <button onClick$={addToCart} disabled={added.value}>
      {added.value ? "Añadido" : "Añadir"}
    </button>
  );
});
```

Otras dos salidas válidas, según el caso:

- **Un valor en el ámbito del módulo** (`const service = new CartService("/api/cart")` fuera del componente) tampoco se captura: el fragmento del manejador importa el módulo y lo obtiene de ahí. Sirve para objetos sin estado por usuario; en el servidor, ese módulo se comparte entre peticiones, así que no guardes en él nada de una sesión concreta.
- **`noSerialize()`** para cuando de verdad necesitas una instancia no serializable en el estado del componente (por ejemplo, un mapa de una librería de terceros): Qwik la omite al serializar y, al reanudar en el navegador, valdrá `undefined`, así que tienes que recrearla, normalmente en un `useVisibleTask$`.

La regla para el equipo: dentro de un `$`, solo datos. Los objetos con comportamiento se crean dentro o se importan del módulo.

Comprobación: con el cambio, la página carga sin error en dev, y en el HTML generado (*Ver código fuente*) el estado serializado contiene el `productId` y el valor de la señal, pero nada de `CartService`.""",
            },
        ]
    },
    # 5) HTMX: búsqueda en vivo con Flask sin React (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una app Flask con plantillas Jinja y quiero que al escribir en un buscador se filtre la tabla sin recargar la página, pero no quiero meter React ni un build de JavaScript. ¿HTMX sirve para esto?",
            },
            {
                "role": "assistant",
                "content": """Sí, es su caso de uso típico. HTMX añade atributos HTML que hacen que cualquier elemento lance una petición HTTP y sustituya una parte de la página por el **HTML** que devuelve el servidor. Tu backend sigue renderizando plantillas Jinja; solo devuelve un fragmento en lugar de la página completa.

Plantilla principal:

```html
<!-- templates/customers/index.html -->
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Clientes</title>
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body>
  <label for="customer-search">Buscar cliente</label>
  <input id="customer-search" type="search" name="q" value="{{ q }}"
         hx-get="/customers"
         hx-trigger="input changed delay:300ms, search"
         hx-target="#customer-rows"
         hx-swap="innerHTML"
         hx-push-url="true"
         hx-indicator="#search-status">
  <span id="search-status" class="htmx-indicator">Buscando…</span>

  <table>
    <thead><tr><th>Nombre</th><th>Email</th><th>Ciudad</th></tr></thead>
    <tbody id="customer-rows">
      {% include "customers/_rows.html" %}
    </tbody>
  </table>
</body>
</html>
```

Fragmento con las filas, reutilizado en la carga inicial y en cada búsqueda:

```html
<!-- templates/customers/_rows.html -->
{% for customer in customers %}
  <tr><td>{{ customer.name }}</td><td>{{ customer.email }}</td><td>{{ customer.city }}</td></tr>
{% else %}
  <tr><td colspan="3">Sin resultados para «{{ q }}»</td></tr>
{% endfor %}
```

La vista de Flask devuelve la página o el fragmento según quién pregunte:

```python
from flask import Flask, render_template, request

from app.customers import search_customers  # tu consulta, con parámetros enlazados

app = Flask(__name__)


@app.get("/customers")
def customers():
    query = request.args.get("q", "").strip()
    rows = search_customers(query)
    is_htmx_fragment = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )
    template = "customers/_rows.html" if is_htmx_fragment else "customers/index.html"
    return render_template(template, customers=rows, q=query)
```

Qué hace cada atributo:

- **`hx-get="/customers"`**: al dispararse, pide esa URL con los valores del campo (`?q=...`).
- **`hx-trigger="input changed delay:300ms, search"`**: se dispara al escribir, solo si el valor cambió, esperando 300 ms de pausa (un *debounce*); `search` cubre el botón de borrar del campo de búsqueda.
- **`hx-target` y `hx-swap`**: la respuesta sustituye el contenido de `<tbody id="customer-rows">`.
- **`hx-push-url="true"`**: la URL pasa a ser `/customers?q=ana`, así que la búsqueda se puede compartir y el botón de atrás funciona.
- **`hx-indicator`**: muestra «Buscando…» mientras hay una petición en curso.

Por qué la vista comprueba dos cabeceras: HTMX envía `HX-Request` en sus peticiones, y si alguien abre directamente `/customers?q=ana` (recargando, o desde un enlace), no llega esa cabecera y se devuelve la página completa. `HX-History-Restore-Request` aparece cuando HTMX restaura una página del historial que no tenía en caché: ahí también necesita la página entera.

Seguridad: Jinja escapa por defecto, así que lo que el usuario escribe no puede inyectar HTML en la tabla. Y en producción, sirve `htmx.min.js` desde tu propio dominio con la versión fijada, en lugar de depender de un CDN.

Comprobación: abre la pestaña *Network*, escribe «ana» rápido: debe salir **una** petición tras la pausa, y su respuesta debe ser solo `<tr>...</tr>`, no la página entera. Luego recarga con `?q=ana` en la URL: la página completa debe aparecer ya filtrada.""",
            },
        ]
    },
    # 6) HTMX: errores 422 que no se pintan, y hx-boost para un sitio antiguo (system rioplatense, multiturno)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y con código completo."},
            {
                "role": "user",
                "content": "Con HTMX hice un formulario con `hx-post` que, si la validación falla, devuelve el mismo formulario con los errores. El backend (Django) responde 422 con ese HTML, pero en la página no cambia nada. En la pestaña Network veo la respuesta correcta. ¿Qué pasa?",
            },
            {
                "role": "assistant",
                "content": """Pasa que, por defecto, **HTMX no inserta en la página las respuestas 4xx ni 5xx**. Las trata como errores: dispara el evento `htmx:responseError` y no hace el *swap*. Tu backend responde bien; HTMX descarta el HTML a propósito.

Tenés dos caminos, y el segundo es el que prefiero.

**1. Responder 200 con el formulario y los errores.** Es lo que hace mucha gente con HTMX y funciona, pero el código de estado deja de decir la verdad: un monitor, un test o un proxy no distinguen un envío fallido de uno correcto.

**2. Mantener el 422 y decirle a HTMX que esos sí se pintan.** En HTMX 2 se configura con `responseHandling`, una sola vez en la plantilla base:

```html
<meta name="htmx-config" content='{
  "responseHandling": [
    {"code": "204", "swap": false},
    {"code": "[23]..", "swap": true},
    {"code": "422", "swap": true},
    {"code": "[45]..", "swap": false, "error": true}
  ]
}'>
```

Las reglas se evalúan en orden: el 422 se inserta como cualquier respuesta correcta, y el resto de 4xx y 5xx sigue tratándose como error.

La vista de Django:

```python
# contact/views.py
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .forms import ContactForm


@require_POST
def contact(request):
    form = ContactForm(request.POST)
    if not form.is_valid():
        # 422: la petición se entendió pero los datos no son válidos
        return render(request, "contact/_form.html", {"form": form}, status=422)
    form.save()
    return render(request, "contact/_success.html")
```

Y el fragmento del formulario, que se reemplaza a sí mismo:

```html
<!-- contact/templates/contact/_form.html -->
<form hx-post="{% url 'contact' %}" hx-target="this" hx-swap="outerHTML" novalidate>
  {% csrf_token %}
  <label for="id_email">Correo</label>
  <input id="id_email" name="email" type="email" value="{{ form.email.value|default_if_none:'' }}"
         {% if form.email.errors %}aria-invalid="true" aria-describedby="email-error"{% endif %}>
  {% if form.email.errors %}
    <p id="email-error" class="error">{{ form.email.errors.0 }}</p>
  {% endif %}

  <label for="id_message">Mensaje</label>
  <textarea id="id_message" name="message">{{ form.message.value|default_if_none:'' }}</textarea>
  {% if form.message.errors %}<p class="error">{{ form.message.errors.0 }}</p>{% endif %}

  <button type="submit">Enviar</button>
</form>
```

Detalles:

- **`hx-target="this"` + `hx-swap="outerHTML"`**: la respuesta reemplaza el formulario entero, con los valores que el usuario ya escribió y los errores al lado de cada campo.
- **`{% csrf_token %}` dentro del form**: HTMX envía los campos del formulario, token incluido, así que la protección CSRF de Django funciona sin configurar nada más.
- **`aria-invalid` y `aria-describedby`**: el lector de pantalla anuncia el error al volver al campo.

Si en lugar de reemplazar el formulario querés mandar los errores a otro elemento, existe la extensión `response-targets` (`hx-target-422="#errores"`).

Comprobación: enviá el formulario con un correo inválido; en *Network* tiene que verse el 422 y, en la página, el formulario con el error. Con datos válidos, el 200 reemplaza el formulario por el mensaje de éxito.""",
            },
            {
                "role": "user",
                "content": "Buenísimo. Ahora quiero que todo el sitio viejo (links y formularios normales) navegue sin recargar la página completa, sin tocar cada enlace. Vi `hx-boost`. ¿Qué tengo que cuidar?",
            },
            {
                "role": "assistant",
                "content": """`hx-boost` hace exactamente eso: con un atributo en un contenedor, todos los enlaces y formularios de adentro pasan a hacerse por AJAX. HTMX pide la página, reemplaza el `<body>` y actualiza la URL y el historial. Si JavaScript falla o no carga, los enlaces siguen funcionando como siempre: es mejora progresiva pura.

```html
<body hx-boost="true">
  <nav>
    <a href="/">Inicio</a>
    <a href="/customers">Clientes</a>
    <a href="/reports/export.csv" hx-boost="false">Descargar CSV</a>
    <a href="https://docs.example.com" hx-boost="false">Documentación</a>
  </nav>
  <main>{% block content %}{% endblock %}</main>
</body>
```

Lo que tenés que cuidar, en orden de cuántos sustos da:

1. **Scripts que se ejecutan «al cargar la página».** Con boost no hay carga nueva: el `<head>` no se vuelve a procesar y `DOMContentLoaded` no se dispara otra vez. Un datepicker o un gráfico que se inicializaba ahí deja de funcionar en la segunda página. La solución es inicializar en `htmx.onLoad`, que corre para el contenido inicial y para cada fragmento nuevo:

```html
<script>
  htmx.onLoad((content) => {
    content.querySelectorAll("[data-datepicker]").forEach((input) => initDatepicker(input));
  });
</script>
```

2. **Descargas y enlaces externos**: marcalos con `hx-boost="false"`, como arriba. Una descarga por AJAX termina con el archivo insertado como texto en el `<body>`.
3. **Estilos o scripts específicos de una página** que solo están en su `<head>`: no se cargan al navegar con boost. Movelos a la plantilla base o usá la extensión `head-support` de HTMX, que fusiona el `<head>` nuevo con el actual.
4. **El título y el foco**: HTMX actualiza el `<title>`, pero el foco se queda donde estaba. Para lectores de pantalla conviene mover el foco al `<main>` o al `<h1>` después de cada navegación.
5. **Formularios con redirect**: si el POST responde con un 302, HTMX sigue la redirección y muestra la página final, como el navegador. No hace falta cambiar nada en Django.

Mi consejo para un sitio viejo: activalo primero en una sección (`<main hx-boost="true">` en vez del `body`), recorré esa sección entera con la consola abierta buscando errores de inicialización, y recién después ampliá al sitio completo.

Comprobación: navegá entre tres páginas con la pestaña *Network* abierta. Cada navegación tiene que ser una petición de tipo `fetch`/`xhr`, no un *document*; el botón de atrás tiene que funcionar; y cualquier widget de JavaScript tiene que andar también en la segunda página visitada, no solo en la primera.""",
            },
        ]
    },
    # 7) HTMX frente a Phoenix LiveView para un panel interno en tiempo real (inglés, comparación)
    {
        "messages": [
            {
                "role": "user",
                "content": "We need an internal ops dashboard: tables with filters, a few forms, and live updates when orders change status, for a few hundred concurrent users. Our backend is Python/Django. Would you go with HTMX, or build that part in Phoenix LiveView?",
            },
            {
                "role": "assistant",
                "content": """HTMX on your existing Django. LiveView is the better technology for real-time UIs, but your requirements do not need what it is best at, and adopting it means a second language, runtime and deployment pipeline for one dashboard.

**How they differ:**

| | HTMX + Django | Phoenix LiveView |
|---|---|---|
| Model | stateless requests; the server returns HTML fragments | one stateful process per connected user, over a WebSocket |
| Live updates | polling or Server-Sent Events | built in: server pushes minimal diffs |
| Server memory per user | none between requests | one lightweight process holding that user's state |
| Real-time between users | you wire it (SSE plus a pub/sub such as Redis) | `Phoenix.PubSub`, a few lines |
| Team cost | Django skills you already have | Elixir, OTP, a new deployment |
| Strongest at | CRUD, filters, forms, server-rendered apps | collaborative, highly interactive, real-time apps |

"A few hundred users, tables, forms, status changes" is CRUD with a live column. The live part comes in two levels:

**Level 1, start here: polling.** For an ops dashboard, data that is 10-15 seconds old is usually fine, and it is one attribute:

```html
<tbody id="orders" hx-get="/orders/rows" hx-trigger="every 15s" hx-swap="innerHTML">
  {% include "orders/_rows.html" %}
</tbody>
```

A few hundred users polling every 15 s is roughly 20-30 requests per second of cheap queries. Make sure the endpoint is indexed and returns only the visible page.

**Level 2, if seconds matter: Server-Sent Events.** Each order update is pushed as a rendered row. With the `htmx-ext-sse` extension loaded:

```html
<div hx-ext="sse" sse-connect="/orders/stream">
  <table>
    <tbody id="orders" sse-swap="order-updated" hx-swap="afterbegin">
      {% include "orders/_rows.html" %}
    </tbody>
  </table>
</div>
```

```python
# orders/views.py (Django 4.2+ under ASGI, so the streaming response can be async)
from django.http import StreamingHttpResponse
from django.template.loader import render_to_string

from .events import order_updates  # async iterator over your pub/sub channel (e.g. Redis)


def sse_message(event: str, html: str) -> str:
    data_lines = "".join(f"data: {line}\n" for line in html.splitlines())
    return f"event: {event}\n{data_lines}\n"


async def order_stream(request):
    async def events():
        async for order in order_updates():
            yield sse_message("order-updated", render_to_string("orders/_row.html", {"order": order}))

    return StreamingHttpResponse(events(), content_type="text/event-stream")
```

The cost to watch: each SSE client holds an open connection, so the app must run under ASGI (uvicorn, daphne) rather than a fixed pool of sync workers.

**For comparison, the LiveView version** of the same live table is short, and this is LiveView's real strength:

```elixir
def mount(_params, _session, socket) do
  if connected?(socket), do: Phoenix.PubSub.subscribe(Ops.PubSub, "orders")
  {:ok, stream(socket, :orders, Orders.list_recent())}
end

def handle_info({:order_updated, order}, socket) do
  {:noreply, stream_insert(socket, :orders, order, at: 0)}
end
```

**When I would pick LiveView instead:** if the product *is* real time (collaborative editing, live operations rooms where many users act on the same state, presence), if you have or want Elixir skills, or if this becomes a separate service that will grow. Then the BEAM's cheap processes and built-in PubSub pay for the new stack.

Verification for the HTMX route: load-test the polling endpoint with the expected concurrency (for example `locust` with 300 users hitting `/orders/rows` every 15 s) and confirm p95 latency and database load stay flat. If they do, level 1 is enough and SSE can wait.""",
            },
        ]
    },
    # 8) Phoenix LiveView: formulario con validación en vivo sin JavaScript (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de React y estoy probando Phoenix LiveView. ¿Cómo se hace un formulario de registro con validación en vivo, mostrando errores mientras escribo, sin escribir JavaScript?",
            },
            {
                "role": "assistant",
                "content": r"""Con dos eventos y el changeset de Ecto. La diferencia de fondo con React: **el estado del formulario vive en el servidor**. Cada cambio viaja por el WebSocket de LiveView, el servidor valida con las mismas reglas que usará para guardar, y devuelve solo el trozo de HTML que cambió (los mensajes de error). No hay validación duplicada en el cliente.

**1. Las reglas, en el schema** (una sola fuente de verdad para el formulario y la base de datos):

```elixir
# lib/shop/accounts/user.ex
defmodule Shop.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :password, :string, virtual: true, redact: true
    field :hashed_password, :string, redact: true
    timestamps()
  end

  def registration_changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :password])
    |> validate_required([:email, :password], message: "es obligatorio")
    |> validate_format(:email, ~r/^[^@\s]+@[^@\s]+$/, message: "debe tener una @ y no llevar espacios")
    |> validate_length(:password, min: 12, message: "debe tener al menos 12 caracteres")
    |> unsafe_validate_unique(:email, Shop.Repo, message: "ya está registrado")
    |> unique_constraint(:email, message: "ya está registrado")
  end
end
```

```elixir
# lib/shop/accounts.ex (extracto)
def change_user_registration(%User{} = user, attrs \\ %{}) do
  User.registration_changeset(user, attrs)
end
```

`register_user/1` hashea la contraseña (por ejemplo con `Bcrypt.hash_pwd_salt/1`) y la inserta con `Repo.insert/1`; es lo que generan los scaffolds de autenticación de Phoenix.

**2. La LiveView**: estado inicial en `mount`, y un `handle_event` por cada evento del formulario.

```elixir
# lib/shop_web/live/signup_live.ex
defmodule ShopWeb.SignupLive do
  use ShopWeb, :live_view

  alias Shop.Accounts
  alias Shop.Accounts.User

  def mount(_params, _session, socket) do
    {:ok, assign(socket, form: to_form(Accounts.change_user_registration(%User{})))}
  end

  def handle_event("validate", %{"user" => params}, socket) do
    changeset = Accounts.change_user_registration(%User{}, params)
    {:noreply, assign(socket, form: to_form(changeset, action: :validate))}
  end

  def handle_event("save", %{"user" => params}, socket) do
    case Accounts.register_user(params) do
      {:ok, _user} ->
        {:noreply,
         socket
         |> put_flash(:info, "Cuenta creada")
         |> push_navigate(to: ~p"/welcome")}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end
end
```

**3. La plantilla**, en un archivo junto al módulo (`signup_live.html.heex`); LiveView la encuentra sola si el módulo no define `render/1`:

```heex
<.form for={@form} id="signup-form" phx-change="validate" phx-submit="save">
  <.input field={@form[:email]} type="email" label="Correo" phx-debounce="300" />
  <.input field={@form[:password]} type="password" label="Contraseña" phx-debounce="blur" />
  <.button phx-disable-with="Creando…">Crear cuenta</.button>
</.form>
```

Qué hace cada pieza:

- **`phx-change="validate"`** envía el formulario completo en cada cambio; **`phx-debounce`** limita la frecuencia: 300 ms para el correo, y solo al salir del campo para la contraseña.
- **`action: :validate`** en `to_form` hace que los errores se muestren. Sin acción, el changeset es «nuevo» y los componentes no pintan errores. Además, el componente `<.input>` generado por Phoenix solo muestra errores de los campos que el usuario ya tocó, para no llenar de rojo un formulario recién abierto.
- **`unsafe_validate_unique`** consulta la base mientras escribes para avisar de un email repetido; es «inseguro» porque entre esa consulta y el insert otro usuario podría registrarse. Por eso va acompañado de **`unique_constraint`**, que traduce el error real del índice único en un mensaje del formulario.
- **`phx-disable-with`** deshabilita el botón mientras se procesa el envío: sin dobles registros.

Comprobación con `Phoenix.LiveViewTest`:

```elixir
test "muestra errores mientras se escribe", %{conn: conn} do
  {:ok, view, _html} = live(conn, ~p"/signup")

  html =
    view
    |> form("#signup-form", user: %{email: "sin-arroba", password: "corta"})
    |> render_change()

  assert html =~ "debe tener una @"
  assert html =~ "al menos 12 caracteres"
end
```""",
            },
        ]
    },
    # 9) Phoenix LiveView: tiempo real con PubSub y streams, y varios nodos (multiturno, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "En LiveView tengo una tabla de pedidos y quiero que se actualice en tiempo real cuando otro usuario cambia el estado de un pedido. ¿Cómo se hace sin que el servidor guarde miles de pedidos por cada usuario conectado?",
            },
            {
                "role": "assistant",
                "content": """Con dos piezas que vienen de serie: **`Phoenix.PubSub`** para avisar a todas las LiveViews conectadas, y **streams** para que la lista no se quede en la memoria del servidor.

**1. El contexto publica el cambio después de guardarlo:**

```elixir
# lib/shop/orders.ex
defmodule Shop.Orders do
  import Ecto.Query

  alias Shop.Orders.Order
  alias Shop.Repo

  @topic "orders"

  def subscribe, do: Phoenix.PubSub.subscribe(Shop.PubSub, @topic)

  def list_recent(limit \\\\ 100) do
    Repo.all(from o in Order, order_by: [desc: o.inserted_at], limit: ^limit)
  end

  def update_status(%Order{} = order, status) do
    with {:ok, order} <- order |> Order.status_changeset(%{status: status}) |> Repo.update() do
      Phoenix.PubSub.broadcast(Shop.PubSub, @topic, {:order_updated, order})
      {:ok, order}
    end
  end
end
```

**2. La LiveView se suscribe y aplica los cambios a un stream:**

```elixir
# lib/shop_web/live/orders_live.ex
defmodule ShopWeb.OrdersLive do
  use ShopWeb, :live_view

  alias Shop.Orders

  def mount(_params, _session, socket) do
    if connected?(socket), do: Orders.subscribe()
    {:ok, stream(socket, :orders, Orders.list_recent())}
  end

  def handle_info({:order_updated, order}, socket) do
    # Si el pedido ya está en la tabla, se actualiza su fila; si no, se añade.
    {:noreply, stream_insert(socket, :orders, order)}
  end

  def handle_event("mark_shipped", %{"id" => id}, socket) do
    order = Shop.Repo.get!(Shop.Orders.Order, id)
    {:ok, _order} = Orders.update_status(order, "shipped")
    {:noreply, socket}
  end
end
```

```heex
<%!-- lib/shop_web/live/orders_live.html.heex (LiveView 1.0+) --%>
<table>
  <thead><tr><th>Referencia</th><th>Estado</th><th></th></tr></thead>
  <tbody id="orders" phx-update="stream">
    <tr :for={{dom_id, order} <- @streams.orders} id={dom_id}>
      <td>{order.reference}</td>
      <td>{order.status}</td>
      <td><button phx-click="mark_shipped" phx-value-id={order.id}>Marcar enviado</button></td>
    </tr>
  </tbody>
</table>
```

Por qué cada decisión:

- **`if connected?(socket)`**: `mount` se ejecuta dos veces, una en el render HTTP inicial (para que la página llegue con contenido) y otra al abrirse el WebSocket. Solo la segunda es un proceso vivo que puede recibir mensajes; suscribirse en la primera no sirve de nada.
- **Streams en lugar de un `assign` con la lista**: con `assign(socket, orders: lista)`, cada usuario conectado mantiene en su proceso los 100 pedidos. Con `stream`, el servidor envía las filas al cliente y **las olvida**; solo guarda lo mínimo para identificarlas. Con miles de usuarios, es la diferencia entre megas y gigas de memoria.
- **El `handle_event` no actualiza su propio stream**: su `broadcast` le llega también a él como mensaje, y lo procesa como cualquier otro cambio. Un solo camino para actualizar la tabla.
- **`stream_insert` con un pedido que ya existe** reemplaza la fila con el mismo `dom_id`, así que sirve tanto para cambios como para pedidos nuevos.

Comprobación: abre la página en dos navegadores, marca un pedido como enviado en uno y el estado debe cambiar en el otro sin recargar. En el *LiveDashboard* (`/dev/dashboard`), la memoria de los procesos de LiveView no debe crecer con el número de pedidos mostrados.""",
            },
            {
                "role": "user",
                "content": "¿Y si la app corre en 3 nodos detrás de un balanceador? ¿El broadcast llega a los usuarios conectados a otro nodo?",
            },
            {
                "role": "assistant",
                "content": """Llega **si los nodos forman un clúster de Erlang**. `Phoenix.PubSub` con su adaptador por defecto distribuye los mensajes entre todos los nodos conectados entre sí: un `broadcast` en el nodo A llega a los suscriptores de B y C sin cambiar una línea del código anterior. Si los nodos no están conectados, cada uno es una isla y los usuarios de otros nodos no se enteran.

**Conectar los nodos.** Los proyectos generados con Phoenix 1.7.11 o posterior traen `DNSCluster`, que descubre a los otros nodos por DNS (lo habitual en Kubernetes o Fly.io):

```elixir
# lib/shop/application.ex (extracto de los hijos del supervisor)
children = [
  {DNSCluster, query: Application.get_env(:shop, :dns_cluster_query) || :ignore},
  {Phoenix.PubSub, name: Shop.PubSub},
  ShopWeb.Endpoint
]
```

```elixir
# config/runtime.exs
config :shop, :dns_cluster_query, System.get_env("DNS_CLUSTER_QUERY")
```

Con `DNS_CLUSTER_QUERY` apuntando al nombre DNS que resuelve a todas las instancias (un *headless service* en Kubernetes, por ejemplo), y los nodos arrancados con nombre y la misma cookie (`RELEASE_COOKIE`), se conectan solos. Si no podés formar clúster (algunas plataformas no lo permiten), el adaptador `Phoenix.PubSub.Redis` hace lo mismo pasando por Redis.

**Un detalle que con varios nodos se nota más: publica después del commit.** En el `update_status` anterior, el `broadcast` va después de `Repo.update`, que confirma la transacción. Si algún día esa actualización pasa a estar dentro de un `Repo.transaction` más grande, el broadcast tiene que salir **fuera**, después de que la transacción termine. Si no, otros usuarios pueden recibir el aviso, releer el pedido y ver el estado anterior (aún no confirmado), o recibir un cambio que luego se deshizo.

```elixir
def ship_order(order) do
  result =
    Repo.transaction(fn ->
      with {:ok, order} <- order |> Order.status_changeset(%{status: "shipped"}) |> Repo.update(),
           {:ok, _event} <- record_audit_event(order, "shipped") do
        order
      else
        {:error, reason} -> Repo.rollback(reason)
      end
    end)

  with {:ok, order} <- result do
    Phoenix.PubSub.broadcast(Shop.PubSub, @topic, {:order_updated, order})
    {:ok, order}
  end
end
```

Comprobación: con dos nodos en local (`iex --sname a -S mix phx.server` y otro con `--sname b` en otro puerto, conectados con `Node.connect(:"a@tu-maquina")`), abrí la página en cada nodo y cambiá un pedido en uno: el otro tiene que actualizarse. `Node.list()` en cada consola tiene que mostrar al otro nodo.""",
            },
        ]
    },
    # 10) Bun + Elysia: validación con t, cliente tipado Eden y tests (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm trying Bun with Elysia for a small API. How do validation and the end-to-end typed client (Eden) work, and what's the catch?",
            },
            {
                "role": "assistant",
                "content": """Elysia's core idea: **one schema per route does three jobs**. It validates the request at runtime, it types the handler's arguments, and it types the client that calls the route. You write the shape once with `t` (Elysia's TypeBox builder).

```ts
// src/app.ts
import { Elysia, t } from "elysia";

type Todo = { id: number; title: string; done: boolean };

// In-memory store, enough for the example.
const todos = new Map<number, Todo>();
let nextId = 1;

export const app = new Elysia()
  .get("/todos", () => [...todos.values()])
  .post(
    "/todos",
    ({ body, set }) => {
      const todo: Todo = { id: nextId++, title: body.title, done: false };
      todos.set(todo.id, todo);
      set.status = 201;
      return todo;
    },
    { body: t.Object({ title: t.String({ minLength: 1, maxLength: 200 }) }) },
  )
  .patch(
    "/todos/:id",
    ({ params, body, set }) => {
      const todo = todos.get(params.id);
      if (!todo) {
        set.status = 404;
        return { error: "Todo not found" };
      }
      const updated: Todo = { ...todo, ...body };
      todos.set(updated.id, updated);
      return updated;
    },
    {
      params: t.Object({ id: t.Numeric() }), // the path segment arrives as text; Numeric coerces and validates
      body: t.Partial(t.Object({ title: t.String({ minLength: 1 }), done: t.Boolean() })),
    },
  );

export type App = typeof app;
```

```ts
// src/index.ts
import { app } from "./app";

app.listen(3000);
console.log(`Listening on http://localhost:${app.server?.port}`);
```

Inside each handler, `body.title` is a `string` and `params.id` a `number`: inferred from the schema, not annotated. A request with `{ "title": "" }` never reaches the handler; Elysia rejects it with a validation error describing the failing field.

**Eden: the client, typed from the server's type.**

```ts
// src/client.ts
import { treaty } from "@elysiajs/eden";
import type { App } from "./app";

const api = treaty<App>("localhost:3000");

const created = await api.todos.post({ title: "Write tests" });
if (created.error) throw new Error(`Create failed with status ${created.error.status}`);

const updated = await api.todos({ id: created.data.id }).patch({ done: true });
console.log(updated.data);
```

`api.todos.post({ title: 42 })` does not compile, and renaming a field on the server breaks every client call at compile time. It is the same idea as tRPC, but over plain HTTP routes that any other client can still call.

**Tests** without opening a port, through `app.handle` and Bun's built-in runner:

```ts
// src/app.test.ts
import { describe, expect, it } from "bun:test";
import { app } from "./app";

describe("POST /todos", () => {
  it("rejects an empty title", async () => {
    const response = await app.handle(
      new Request("http://localhost/todos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "" }),
      }),
    );
    expect(response.status).toBe(422);
  });

  it("creates a todo", async () => {
    const response = await app.handle(
      new Request("http://localhost/todos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Buy coffee" }),
      }),
    );
    expect(response.status).toBe(201);
    expect(await response.json()).toMatchObject({ title: "Buy coffee", done: false });
  });
});
```

Exporting `app` from a module that does not call `listen` is what makes this possible: the test imports it without starting a server.

**The catches:**

- **Bun first.** Elysia is designed around Bun, and that is where its performance claims hold. Recent versions can run on other runtimes through adapters, but if you may need Node or Workers, check that path early.
- **Type inference depends on chaining.** Everything flows through `typeof app`, so routes must be chained (or composed with `.use()` from `new Elysia({ prefix: "/todos" })` plugins). Routes registered in ways the type system cannot follow disappear from the Eden client.
- **A younger ecosystem**, with breaking changes between minor versions historically. Pin versions and read the changelog before upgrading.
- **Eden needs the server's type at build time**: a monorepo or a shared package. A public API consumed by third parties still needs an OpenAPI description, which Elysia can generate with its Swagger plugin.

Verification: `bun test` must pass both tests, and changing the schema to `t.Object({ name: t.String() })` must make `src/client.ts` fail to type-check on `title`.""",
            },
        ]
    },
    # 11) Hono en Cloudflare Workers: bindings tipados (D1, KV), validación y errores (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero hacer una API pequeña en Cloudflare Workers con Hono, usando D1 como base de datos y KV como caché. ¿Cómo tipo los bindings y estructuro rutas, validación y errores?",
            },
            {
                "role": "assistant",
                "content": r"""En Workers no hay `process.env`: la base de datos, el KV y los secretos llegan como **bindings** en el objeto de entorno de cada petición. Hono los expone en `c.env`, y con un genérico quedan tipados en toda la app.

```toml
# wrangler.toml
name = "catalog-api"
main = "src/index.ts"
compatibility_date = "2025-06-01"

[[d1_databases]]
binding = "DB"
database_name = "catalog"
database_id = "3f6a2c1e-8d4b-4f2a-9c7e-1b5d0e9a7c42" # el que devuelve `wrangler d1 create catalog`

[[kv_namespaces]]
binding = "CACHE"
id = "9b1e4f7a2c3d4e5f8a6b7c8d9e0f1a2b" # el que devuelve `wrangler kv namespace create CACHE`
```

El secreto no va en el archivo: `npx wrangler secret put API_TOKEN`. Y `npx wrangler types` genera los tipos de los bindings a partir de esta configuración.

```ts
// src/index.ts
import { Hono } from "hono";
import { bearerAuth } from "hono/bearer-auth";
import { HTTPException } from "hono/http-exception";
import { zValidator } from "@hono/zod-validator";
import { z } from "zod";

type Bindings = {
  DB: D1Database;
  CACHE: KVNamespace;
  API_TOKEN: string;
};

type Product = { id: number; name: string; price_cents: number };

const CACHE_TTL_SECONDS = 300;

const app = new Hono<{ Bindings: Bindings }>();

// El token se lee del entorno de cada petición: por eso el middleware se crea dentro.
app.use("/admin/*", (c, next) => bearerAuth({ token: c.env.API_TOKEN })(c, next));

const productParams = z.object({ id: z.coerce.number().int().positive() });

app.get("/products/:id", zValidator("param", productParams), async (c) => {
  const { id } = c.req.valid("param");
  const cacheKey = `product:${id}`;

  const cached = await c.env.CACHE.get<Product>(cacheKey, "json");
  if (cached) return c.json(cached);

  const product = await c.env.DB.prepare("SELECT id, name, price_cents FROM products WHERE id = ?")
    .bind(id)
    .first<Product>();
  if (!product) throw new HTTPException(404, { message: "Producto no encontrado" });

  await c.env.CACHE.put(cacheKey, JSON.stringify(product), { expirationTtl: CACHE_TTL_SECONDS });
  return c.json(product);
});

const newProduct = z.object({
  name: z.string().trim().min(1).max(200),
  priceCents: z.number().int().nonnegative(),
});

app.post("/admin/products", zValidator("json", newProduct), async (c) => {
  const { name, priceCents } = c.req.valid("json");
  const created = await c.env.DB.prepare("INSERT INTO products (name, price_cents) VALUES (?, ?) RETURNING id")
    .bind(name, priceCents)
    .first<{ id: number }>();
  if (!created) throw new HTTPException(500, { message: "La inserción no devolvió id" });
  return c.json({ id: created.id, name, price_cents: priceCents }, 201);
});

app.onError((error, c) => {
  if (error instanceof HTTPException) return error.getResponse();
  console.error(error); // visible en `wrangler tail` y en el panel
  return c.json({ error: "Error interno" }, 500);
});

export default app;
```

Decisiones:

- **SQL con `?` y `.bind()`**: D1 envía los valores como parámetros. Nunca construyas la consulta concatenando el id, aunque venga validado.
- **`zValidator` en params y body**: el handler recibe datos ya convertidos y validados (`id` es un número), y una entrada inválida responde 400 sin llegar a tu código.
- **`bearerAuth`** compara el token de forma segura frente a ataques de temporización, cosa que un `!==` escrito a mano no hace.
- **Un único `onError`**: los `HTTPException` salen con su código; cualquier otra cosa se registra y responde 500 sin filtrar detalles internos.

La advertencia importante sobre **KV**: es **eventualmente consistente**. Una escritura puede tardar hasta un minuto en verse en otras ubicaciones de la red de Cloudflare. Para una caché de lecturas con TTL está bien; para datos que deben verse al instante tras una escritura (un stock, un saldo), no. Y al modificar un producto, borra su clave con `c.env.CACHE.delete(cacheKey)` en lugar de esperar a que caduque el TTL.

Comprobación: `npx wrangler d1 execute catalog --local --file=schema.sql` para crear la tabla en local y `npx wrangler dev`. Pide `/products/1` dos veces: la primera consulta D1 y la segunda debe salir de KV (añade temporalmente una cabecera `X-Cache: HIT`/`MISS` para verlo). Un POST a `/admin/products` sin token debe responder 401. Para tests automatizados con bindings reales, `@cloudflare/vitest-pool-workers` ejecuta Vitest dentro del runtime de Workers.""",
            },
        ]
    },
    # 12) Hono frente a Elysia para una API que hoy va en Node y mañana quizá en Workers (comparación)
    {
        "messages": [
            {
                "role": "user",
                "content": "Para una API nueva en TypeScript, ¿Hono o Elysia? Hoy desplegaríamos en Node con Docker, pero no descartamos Cloudflare Workers más adelante.",
            },
            {
                "role": "assistant",
                "content": """**Hono**, y el motivo decisivo es la frase «hoy Node, quizá Workers mañana».

| | Hono | Elysia |
|---|---|---|
| Diseño | estándares web (`Request`/`Response`): el mismo código corre en Workers, Deno, Bun, Node y Lambda | pensado para Bun; otros runtimes mediante adaptadores más recientes |
| Rendimiento | muy bueno en todos los runtimes | el mejor en Bun |
| Validación | middleware (`@hono/zod-validator`, Valibot...) | integrada en la definición de la ruta (`t`) |
| Cliente tipado | `hc<AppType>` (Hono RPC) | Eden Treaty |
| Middleware incluido | amplio (CORS, JWT, bearer, ETag, compresión...) | más reducido, vía plugins |
| Estabilidad de la API | alta | históricamente con cambios entre versiones menores |

La experiencia de tipos de Elysia es algo más cómoda, y en Bun es más rápido. Pero portar una API de Elysia a Workers es un riesgo; con Hono es cambiar el archivo de entrada. Ese es el diseño, no una promesa:

```ts
// src/app.ts: la aplicación, sin saber dónde corre
import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { z } from "zod";

const createTodo = z.object({ title: z.string().trim().min(1).max(200) });

export const app = new Hono()
  .get("/health", (c) => c.json({ status: "ok" }))
  .post("/todos", zValidator("json", createTodo), (c) => {
    const { title } = c.req.valid("json");
    return c.json({ id: crypto.randomUUID(), title, done: false }, 201);
  });

export type AppType = typeof app;
```

```ts
// src/node.ts: entrada para Docker/Node
import { serve } from "@hono/node-server";
import { app } from "./app";

serve({ fetch: app.fetch, port: Number(process.env.PORT ?? 3000) });
```

```ts
// src/worker.ts: entrada para Cloudflare Workers, el día que haga falta
import { app } from "./app";

export default app;
```

El cliente tipado, equivalente a Eden:

```ts
import { hc } from "hono/client";
import type { AppType } from "./app";

const client = hc<AppType>("http://localhost:3000");

const response = await client.todos.$post({ json: { title: "Probar Hono" } });
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const todo = await response.json(); // { id: string; title: string; done: boolean }
```

Dos condiciones para que la portabilidad sea real y no solo teórica:

1. **Las rutas encadenadas**, como arriba, para que `typeof app` lleve todas las rutas y el cliente las vea.
2. **Nada de APIs exclusivas de Node en `app.ts`** (`fs`, `process.env`, `Buffer` sin necesidad). La configuración entra por `c.env` (en Workers) o por una función que construye la app con sus dependencias; el acceso a datos, detrás de una interfaz que tenga una implementación para cada entorno.

Elegiría Elysia en un caso concreto: si el equipo ya está comprometido con Bun para todo, el despliegue va a ser siempre Bun y queréis exprimir el rendimiento.

Comprobación de la promesa: añadid al CI un paso que compile `src/worker.ts` con `wrangler deploy --dry-run`. Si algún día alguien mete una dependencia de Node en `app.ts`, ese paso falla mucho antes de que necesitéis migrar.""",
            },
        ]
    },
    # 13) Leptos: reactividad fina, señales y server functions (system Rust senior, avanzado)
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un ingeniero senior de Rust. Da código que compile con la versión indicada y explica las decisiones de ownership.",
            },
            {
                "role": "user",
                "content": "¿Cómo es programar frontend en Rust con Leptos? Enséñame un componente con estado y una llamada al servidor, y explícame en qué se diferencia de React.",
            },
            {
                "role": "assistant",
                "content": """La diferencia de fondo con React es la **reactividad fina**: en Leptos, la función del componente se ejecuta **una sola vez**. No hay re-render ni DOM virtual que comparar. Lo que cambia con el estado son closures concretas (`move || ...`) que Leptos convierte en nodos reactivos, y cada señal actualiza directamente los nodos del DOM que dependen de ella.

Ejemplo con Leptos 0.7 en modo fullstack (SSR + hidratación, compilado con `cargo-leptos`):

```rust
use leptos::prelude::*;

/// Server function: el cuerpo solo se compila en el servidor. En el cliente (WASM),
/// Leptos genera un stub que hace la petición HTTP y deserializa la respuesta.
#[server]
pub async fn get_greeting(name: String) -> Result<String, ServerFnError> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err(ServerFnError::new("El nombre no puede estar vacío"));
    }
    Ok(format!("Hola, {trimmed}, desde el servidor"))
}

#[component]
pub fn Greeter() -> impl IntoView {
    let (name, set_name) = signal(String::from("Ana"));

    // Señal derivada: una closure que lee otra señal. Se recalcula cuando cambia `name`.
    let char_count = move || name.with(|value| value.chars().count());

    // Recurso: vuelve a llamar al servidor cada vez que cambia su fuente (`name.get()`).
    let greeting = Resource::new(move || name.get(), get_greeting);

    view! {
        <label>
            "Tu nombre: "
            <input
                prop:value=name
                on:input=move |event| set_name.set(event_target_value(&event))
            />
        </label>
        <p>"Caracteres: " {char_count}</p>
        <Suspense fallback=|| view! { <p>"Cargando…"</p> }>
            {move || greeting.get().map(|result| match result {
                Ok(text) => view! { <p>{text}</p> }.into_any(),
                Err(error) => view! { <p class="error">{error.to_string()}</p> }.into_any(),
            })}
        </Suspense>
    }
}
```

Lo que pasa al escribir una letra: `set_name` actualiza la señal; se recalculan **solo** el texto de «Caracteres», el valor del input y el recurso, que lanza otra llamada al servidor. Nada más se ejecuta: ni la función `Greeter` ni el resto del árbol.

Las decisiones de ownership, que es donde Rust se nota:

- **Las señales son `Copy`.** `signal()` devuelve dos manejadores ligeros que apuntan a un valor guardado en el runtime reactivo, no el valor en sí. Por eso puedes moverlos (`move ||`) a tantas closures como quieras sin `clone()` ni `Rc`: copias un identificador, no la cadena.
- **`name.with(|value| ...)` en lugar de `name.get()`** para contar caracteres: `get()` clona el `String` en cada lectura; `with` presta una referencia. Con valores grandes la diferencia importa.
- **`.into_any()`** en las ramas del `match`: cada `view!` tiene un tipo concreto distinto, y las dos ramas tienen que devolver el mismo tipo. `into_any()` borra el tipo concreto (como `Box<dyn ...>`, pero para vistas).
- **`event_target_value(&event)`** extrae el `String` del input; el evento solo se presta.

En qué se parece a React: componentes como funciones, props, `Suspense`, el mismo modelo mental de «la vista es función del estado». En qué no: no hay reglas de los hooks (las señales se pueden crear en cualquier sitio), no hay `useMemo` ni `useCallback` (no hace falta evitar re-renders que no existen) y los errores de tipos se detectan al compilar, incluidos los de la frontera con el servidor.

Los costes reales: compilaciones bastante más lentas que un `vite dev`, un binario WASM de cientos de KB (se reduce con `opt-level = "z"`, LTO y `wasm-opt`), y un ecosistema de componentes mucho más pequeño que el de React. Compensa en equipos que ya escriben Rust en el backend y quieren compartir tipos y lógica sin una capa de API intermedia.

Comprobación: `cargo leptos watch`, abre la página y escribe en el campo. En la pestaña *Network* debe aparecer una petición a la server function por cada cambio; con el campo vacío, el mensaje de error debe venir del servidor. Si añades un `log!("render")` dentro de `Greeter`, aparece una sola vez, por mucho que escribas.""",
            },
        ]
    },
    # 14) Leptos frente a Dioxus para una herramienta web + escritorio en Rust (multiturno, comparación)
    {
        "messages": [
            {
                "role": "user",
                "content": "Queremos una herramienta interna en Rust con interfaz: en web y, si se puede, también como app de escritorio. ¿Leptos o Dioxus?",
            },
            {
                "role": "assistant",
                "content": r"""Para «web y también escritorio con el mismo código», **Dioxus**. Para «web primero, con SSR y SEO», Leptos.

| | Leptos | Dioxus |
|---|---|---|
| Objetivo principal | web: SSR, hidratación, server functions | multiplataforma: web, escritorio y móvil desde un código |
| Escritorio | envolviéndolo con Tauri | nativo del framework (webview del sistema) |
| Modelo | reactividad fina con señales, sin DOM virtual | señales con un DOM virtual ligero, estilo React |
| Sintaxis | `view!` parecido a HTML/JSX | `rsx!` con elementos como estructuras |
| Fullstack | muy maduro | server functions y fullstack disponibles |
| Herramienta de desarrollo | `cargo-leptos` | `dx` (CLI de Dioxus), con recarga en caliente |

Leptos puede llegar al escritorio a través de Tauri, pero entonces mantienes dos capas (Tauri y Leptos) y la comunicación entre ellas. Dioxus lo resuelve con un solo framework y el mismo componente se lanza como app web o de escritorio.

Un componente en Dioxus 0.6:

```rust
use dioxus::prelude::*;

fn main() {
    dioxus::launch(App);
}

#[component]
fn App() -> Element {
    let mut count = use_signal(|| 0);

    rsx! {
        h1 { "Contador: {count}" }
        button { onclick: move |_| count += 1, "Sumar" }
        button { onclick: move |_| count.set(0), "Reiniciar" }
    }
}
```

```bash
dx serve --platform web       # en el navegador
dx serve --platform desktop   # ventana nativa con el mismo código
```

Lo que tenéis que vigilar con Dioxus: la parte específica de cada plataforma (leer un archivo local en escritorio no existe en web) se separa con *features* de Cargo; y el ecosistema es más joven, así que algunas piezas (componentes de tabla complejos, gráficos) tendréis que hacerlas o envolverlas vosotros.

Comprobación antes de decidir: haced la pantalla más complicada de la herramienta en Dioxus y lanzadla en las dos plataformas. Si en escritorio necesitáis algo que solo da el sistema (bandeja, atajos globales), revisad que Dioxus lo cubre; si no, Tauri con Leptos vuelve a estar sobre la mesa.""",
            },
            {
                "role": "user",
                "content": "Vamos con Dioxus. ¿Cómo hacemos una llamada asíncrona, por ejemplo cargar el estado de un servicio interno desde una API, y mostrar carga y errores?",
            },
            {
                "role": "assistant",
                "content": r"""Con `use_resource`: ejecuta un futuro, lo vuelve a ejecutar si cambian las señales que lee, y expone el resultado como `Option<T>`, donde `None` significa «todavía cargando». Para la petición HTTP, `reqwest` funciona tanto en escritorio (nativo) como en web (compilado a WASM, sobre `fetch`).

```toml
# Cargo.toml (extracto)
[dependencies]
dioxus = { version = "0.6", features = ["web", "desktop"] }
reqwest = { version = "0.12", features = ["json"] }
serde = { version = "1", features = ["derive"] }
```

```rust
use dioxus::prelude::*;
use serde::Deserialize;

#[derive(Debug, Clone, PartialEq, Deserialize)]
struct ServiceStatus {
    name: String,
    healthy: bool,
    version: String,
}

async fn fetch_status(base_url: String) -> Result<Vec<ServiceStatus>, reqwest::Error> {
    reqwest::get(format!("{base_url}/api/status"))
        .await?
        .error_for_status()?
        .json::<Vec<ServiceStatus>>()
        .await
}

#[component]
fn StatusPanel(base_url: String) -> Element {
    let mut refresh_count = use_signal(|| 0u32);

    let statuses = use_resource(move || {
        let base_url = base_url.clone();
        let _ = refresh_count(); // leer la señal hace que el recurso se recargue cuando cambie
        async move { fetch_status(base_url).await }
    });

    rsx! {
        button { onclick: move |_| refresh_count += 1, "Actualizar" }
        match &*statuses.read_unchecked() {
            Some(Ok(list)) => rsx! {
                ul {
                    for service in list {
                        li { key: "{service.name}",
                            "{service.name} {service.version}: "
                            if service.healthy { "OK" } else { "CAÍDO" }
                        }
                    }
                }
            },
            Some(Err(error)) => rsx! { p { class: "error", "No se pudo cargar el estado: {error}" } },
            None => rsx! { p { "Cargando…" } },
        }
    }
}
```

Decisiones:

- **El botón no llama a la API**: incrementa una señal que el recurso lee. El recurso se recarga solo, y no hay dos caminos de carga que mantener sincronizados.
- **`base_url.clone()` dentro de la closure**: la closure de `use_resource` puede ejecutarse varias veces, y cada futuro necesita su propia copia; el `async move` se queda con esa copia.
- **`error_for_status()`**: sin él, un 500 del servidor llegaría como `Ok` y fallaría después, al deserializar, con un error menos claro.
- **`key` en la lista**: igual que en React, para que Dioxus identifique cada fila al actualizar.
- **`read_unchecked()`**: lee el valor sin mantener el préstamo activo durante todo el render, que es como lo usa la documentación de Dioxus para hacer `match` sobre recursos.

Una diferencia entre plataformas que os vais a encontrar: en web, la petición la hace el navegador y está sujeta a **CORS**, así que la API interna tiene que permitir el origen de la app; en escritorio no hay CORS. Probad siempre en las dos.

Comprobación: con la API apagada, ambas plataformas deben mostrar el mensaje de error; al encenderla y pulsar «Actualizar», la lista. En web, revisad en la consola del navegador que no haya errores de CORS.""",
            },
        ]
    },
    # 15) Tauri 2: comandos Rust, invoke desde React y capabilities (SISTEMA, intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy haciendo una app de escritorio con Tauri 2 y React. ¿Cómo llamo a código Rust desde el frontend y cómo funcionan los permisos nuevos (capabilities)?",
            },
            {
                "role": "assistant",
                "content": r"""Son dos mecanismos que se complementan: los **comandos** son funciones Rust que el frontend invoca por IPC, y las **capabilities** deciden qué ventanas pueden usar qué comandos de los plugins. Ejemplo completo: el usuario elige un archivo y Rust cuenta sus líneas.

**1. El comando en Rust:**

```rust
// src-tauri/src/lib.rs

/// Cuenta las líneas de un archivo de texto.
/// Es `async` y usa `spawn_blocking`: una lectura de disco grande no debe bloquear la interfaz.
#[tauri::command]
async fn count_lines(path: String) -> Result<usize, String> {
    tauri::async_runtime::spawn_blocking(move || {
        std::fs::read_to_string(&path)
            .map(|content| content.lines().count())
            .map_err(|error| format!("No se pudo leer {path}: {error}"))
    })
    .await
    .map_err(|error| format!("La tarea de lectura falló: {error}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![count_lines])
        .run(tauri::generate_context!())
        .expect("error al arrancar la aplicación Tauri");
}
```

**2. La llamada desde React:**

```ts
// src/lib/files.ts
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

export async function pickFileAndCountLines(): Promise<number | null> {
  const selected = await open({ multiple: false, directory: false });
  if (selected === null) return null; // el usuario canceló
  return invoke<number>("count_lines", { path: selected });
}
```

```tsx
// src/components/LineCounter.tsx
import { useState } from "react";
import { pickFileAndCountLines } from "../lib/files";

export function LineCounter() {
  const [message, setMessage] = useState("Ningún archivo elegido");

  async function handleClick() {
    try {
      const lines = await pickFileAndCountLines();
      if (lines !== null) setMessage(`El archivo tiene ${lines} líneas`);
    } catch (error) {
      setMessage(String(error)); // el Err(String) de Rust llega como promesa rechazada
    }
  }

  return (
    <div>
      <button type="button" onClick={handleClick}>Elegir archivo</button>
      <p role="status">{message}</p>
    </div>
  );
}
```

**3. Las capabilities**, en `src-tauri/capabilities/default.json`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Permisos de la ventana principal",
  "windows": ["main"],
  "permissions": ["core:default", "dialog:allow-open"]
}
```

Cómo funciona el modelo de Tauri 2:

- **Todo lo de los plugins está denegado por defecto.** Cada comando de plugin (abrir un diálogo, leer un archivo, lanzar una URL) necesita un permiso en una capability, y la capability dice a qué ventanas se aplica. El `allowlist` de Tauri 1 desaparece.
- **Tus propios comandos** registrados con `generate_handler!` están disponibles para la app sin declarar nada, salvo que decidas restringirlos con permisos propios.
- **Los errores cruzan el puente como valores serializados.** Por eso el comando devuelve `Result<usize, String>`: el `Err` llega a JavaScript como promesa rechazada con ese texto. Con un tipo de error propio, implementa `serde::Serialize` para él.
- **Comandos `async` para trabajo lento.** Un comando síncrono se ejecuta en el hilo principal y una operación lenta dentro congela la ventana.

El punto de seguridad que conviene interiorizar: **el frontend no es de confianza**. Si alguien consigue ejecutar JavaScript en tu webview (un XSS por mostrar HTML sin escapar), puede llamar a `count_lines` con cualquier ruta, no solo la que eligió el usuario. Para operaciones sensibles, abre el diálogo desde Rust y trabaja con la ruta que devuelve allí, sin aceptarla del frontend.

Comprobación: `npm run tauri dev`, elige un archivo de texto y verifica el número de líneas contra `wc -l`. Después quita `dialog:allow-open` de la capability y reinicia: el `open()` debe fallar con un error de permiso no concedido, que es el modelo funcionando.""",
            },
        ]
    },
    # 16) Tauri 2: lectura de archivo denegada por las capabilities del plugin fs (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": "En Tauri 2 intento leer un archivo de configuración desde el frontend con `await readTextFile('config.json', { baseDir: BaseDirectory.AppConfig })` y falla con un error de que `read_text_file` no está permitido, seguido de una lista de permisos. En Tauri 1 funcionaba con el allowlist. ¿Qué tengo que poner?",
            },
            {
                "role": "assistant",
                "content": """El error es el sistema de permisos de Tauri 2 funcionando: los comandos del plugin `fs` están **denegados por defecto**, y la lista que acompaña al error son los permisos que lo habilitarían. El `allowlist` de Tauri 1 ya no existe; su sustituto son las *capabilities*.

**Arreglo mínimo, con el permiso acotado a ese único archivo:**

Si aún no tienes el plugin, `npm run tauri add fs` instala el crate de Rust y el paquete de JavaScript, y lo registra en `lib.rs`. Después, en `src-tauri/capabilities/default.json`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    {
      "identifier": "fs:allow-read-text-file",
      "allow": [{ "path": "$APPCONFIG/config.json" }]
    }
  ]
}
```

```ts
// src/lib/config.ts
import { BaseDirectory, readTextFile } from "@tauri-apps/plugin-fs";

export type AppConfig = { theme: "light" | "dark"; language: string };

export async function loadConfig(): Promise<AppConfig> {
  const raw = await readTextFile("config.json", { baseDir: BaseDirectory.AppConfig });
  return JSON.parse(raw) as AppConfig;
}
```

Por qué así y no con un permiso amplio:

- **El permiso lleva *scope***: `fs:allow-read-text-file` habilita el comando, y `allow` limita las rutas. Con `$APPCONFIG/config.json`, el frontend puede leer ese archivo y ninguno más.
- **Lo tentador es poner un conjunto amplio** (todos los permisos de lectura sobre el directorio personal). Funciona, y convierte cualquier XSS en tu webview en una vía para leer los documentos del usuario. El objetivo del sistema de capabilities es precisamente que el daño de un fallo en el frontend sea pequeño.

**Alternativa que suelo preferir: que el frontend no toque el sistema de archivos.** Un comando propio lee el archivo en Rust, y el frontend solo pide «la configuración»:

```rust
// src-tauri/src/lib.rs (extracto)
use tauri::Manager;

#[tauri::command]
async fn load_config(app: tauri::AppHandle) -> Result<String, String> {
    let path = app
        .path()
        .app_config_dir()
        .map_err(|error| format!("Sin directorio de configuración: {error}"))?
        .join("config.json");
    std::fs::read_to_string(&path).map_err(|error| format!("No se pudo leer {}: {error}", path.display()))
}
```

Registrado en `generate_handler![load_config]` y llamado con `invoke<string>("load_config")`. Ganas tres cosas: no hace falta el plugin `fs` ni ningún permiso de archivos, la ruta la decide Rust y no el frontend, y es el sitio natural para validar el JSON con `serde` y devolver un error claro si está corrupto.

Regla práctica: permisos de plugin con *scope* estrecho para casos simples; comandos propios cuando la operación toca datos sensibles o tiene lógica.

Comprobación: con la capability acotada, `loadConfig()` debe funcionar, y `readTextFile("otro.json", { baseDir: BaseDirectory.AppConfig })` debe seguir fallando por permisos. Así compruebas que el scope limita de verdad y no solo que «ahora funciona».""",
            },
        ]
    },
    # 17) React Router v7 (modo framework): loaders, actions y tipos generados (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Empiezo con React Router v7 en modo framework (lo que antes era Remix). ¿Cómo funcionan los loaders y las actions, y de dónde salen los tipos `Route.LoaderArgs` que veo en los ejemplos?",
            },
            {
                "role": "assistant",
                "content": """La idea viene de Remix: **cada ruta declara cómo obtiene sus datos (`loader`) y cómo procesa sus mutaciones (`action`)**, y ambos se ejecutan en el servidor. El componente recibe los datos ya cargados; tras una mutación, React Router vuelve a ejecutar los loaders y la interfaz se actualiza sin que gestiones estado a mano.

**Las rutas se declaran en `app/routes.ts`:**

```ts
// app/routes.ts
import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/home.tsx"),
  route("contacts/:contactId", "routes/contact.tsx"),
] satisfies RouteConfig;
```

**Una ruta con loader, action, componente y gestión de errores:**

```tsx
// app/routes/contact.tsx
import { Form, data, isRouteErrorResponse } from "react-router";
import type { Route } from "./+types/contact";
import { getContact, setFavorite } from "../data/contacts.server";

export async function loader({ params }: Route.LoaderArgs) {
  const contact = await getContact(params.contactId); // params.contactId: string, por la ruta
  if (!contact) throw data("Contacto no encontrado", { status: 404 });
  return { contact };
}

export async function action({ params, request }: Route.ActionArgs) {
  const formData = await request.formData();
  await setFavorite(params.contactId, formData.get("favorite") === "true");
  return { ok: true };
}

export default function Contact({ loaderData }: Route.ComponentProps) {
  const { contact } = loaderData;
  return (
    <article>
      <h1>{contact.name}</h1>
      <p>{contact.email}</p>
      <Form method="post">
        <input type="hidden" name="favorite" value={String(!contact.favorite)} />
        <button type="submit">{contact.favorite ? "Quitar de favoritos" : "Marcar como favorito"}</button>
      </Form>
    </article>
  );
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  if (isRouteErrorResponse(error)) {
    return <p>{error.status}: {error.data}</p>;
  }
  return <p>Algo salió mal al cargar el contacto.</p>;
}
```

**De dónde salen los tipos:** React Router genera un archivo `+types/<ruta>.d.ts` para cada ruta a partir de `routes.ts` (lo hace el servidor de desarrollo, o `npx react-router typegen`). Por eso `params.contactId` es `string` y no `string | undefined`: la ruta `contacts/:contactId` garantiza el segmento. Y `loaderData` en el componente tiene exactamente el tipo de lo que devuelve tu `loader`, sin escribir interfaces.

Qué pasa en cada caso:

- **Primera carga**: el servidor ejecuta el `loader`, renderiza el HTML con los datos y lo envía; el navegador hidrata.
- **Navegación en el cliente**: React Router pide al servidor solo los datos del loader y renderiza en el navegador.
- **Envío del `<Form method="post">`**: se ejecuta la `action` en el servidor y después **se revalidan los loaders** de la página. El botón cambia de texto porque `contact.favorite` llega actualizado, no porque hayas tocado estado local.
- **`throw data(..., { status: 404 })`** corta la carga y renderiza el `ErrorBoundary` de la ruta con ese estado.

El sufijo **`.server.ts`** en el módulo de datos garantiza que ese código (y lo que importe: el cliente de base de datos, secretos) nunca acabe en el bundle del navegador; si alguien lo importa desde código de cliente, el build falla.

Comprobación de lo más característico del modelo: desactiva JavaScript en el navegador y pulsa el botón de favorito. Debe seguir funcionando, como un formulario HTML clásico con recarga completa. Con JavaScript activo, lo mismo sin recarga. Y una URL con un id inexistente debe mostrar «404: Contacto no encontrado».""",
            },
        ]
    },
    # 18) React Router v7: useFetcher con UI optimista y clics repetidos (multiturno, intermedio-avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "En una lista de tareas con React Router v7 quiero marcar una tarea como hecha sin navegar ni recargar, y que el check cambie al instante aunque el servidor tarde.",
            },
            {
                "role": "assistant",
                "content": """Para mutaciones que no deben provocar una navegación, **`useFetcher`**: envía a una `action` como un `<Form>`, pero sin cambiar de URL y con su propio estado. Y para la respuesta instantánea, **UI optimista**: mientras el envío está en curso, muestras el valor que se está enviando en lugar del que tienes del servidor.

```tsx
// app/routes/todos.tsx
import { useFetcher } from "react-router";
import type { Route } from "./+types/todos";
import { listTodos, setTodoDone } from "../data/todos.server";

type Todo = { id: string; title: string; done: boolean };

export async function loader() {
  return { todos: await listTodos() };
}

export async function action({ request }: Route.ActionArgs) {
  const formData = await request.formData();
  const id = String(formData.get("id"));
  const done = formData.get("done") === "true";
  await setTodoDone(id, done); // «poner a X», no «alternar»: repetirlo da el mismo resultado
  return { ok: true };
}

function TodoItem({ todo }: { todo: Todo }) {
  const fetcher = useFetcher();

  // Optimista: si hay un envío en curso, la verdad provisional es lo que se está enviando.
  const done = fetcher.formData ? fetcher.formData.get("done") === "true" : todo.done;

  return (
    <li>
      <fetcher.Form method="post">
        <input type="hidden" name="id" value={todo.id} />
        <input type="hidden" name="done" value={String(!done)} />
        <button type="submit" aria-pressed={done}>
          <span aria-hidden="true">{done ? "✓" : "○"}</span> {todo.title}
        </button>
      </fetcher.Form>
    </li>
  );
}

export default function Todos({ loaderData }: Route.ComponentProps) {
  return (
    <ul>
      {loaderData.todos.map((todo) => (
        <TodoItem key={todo.id} todo={todo} />
      ))}
    </ul>
  );
}
```

Por qué funciona sin estado local:

- **Un fetcher por tarea**: cada fila tiene su propio envío independiente; marcar tres tareas seguidas lanza tres peticiones en paralelo y cada fila muestra su valor optimista.
- **`fetcher.formData` existe solo mientras el envío está en curso.** Cuando termina, React Router revalida el `loader`, `todo.done` llega del servidor y el componente vuelve a leerlo de ahí. Si la action falló y no guardó nada, el valor «salta» de vuelta al real: el rollback sale gratis, sin código de deshacer.
- **La action es idempotente**: recibe el valor final (`done=true`), no la orden de alternar. Si una petición se repite, el resultado es el mismo.

Para mostrar el error en vez de solo revertir, la action puede devolver `data({ error: "No se pudo guardar" }, { status: 500 })` y la fila mostrar `fetcher.data?.error`.

Comprobación: en DevTools, *Network* → *Slow 3G*, marca una tarea. El check debe cambiar al instante y la petición seguir en curso. Luego haz que `setTodoDone` lance una excepción: el check debe volver a su estado anterior al terminar la petición.""",
            },
            {
                "role": "user",
                "content": "¿Y si el usuario hace clic tres veces muy rápido en la misma tarea? ¿Puede quedar en un estado incorrecto?",
            },
            {
                "role": "assistant",
                "content": """En la interfaz, no; en la base de datos, puede, y vale la pena entender por qué.

**Lo que hace React Router**: cada nuevo envío del **mismo** fetcher interrumpe el anterior. El navegador aborta la petición vieja y la interfaz solo atiende a la respuesta de la última. Como cada clic calcula su valor a partir del valor optimista actual, los tres clics envían `true`, `false`, `true`, y la interfaz termina mostrando `true`.

**Lo que no puede garantizar**: abortar una petición en el navegador no impide que haya llegado al servidor. Las tres pueden ejecutarse, y **no necesariamente en orden**: si la de `false` tarda más en procesarse (una conexión distinta, un servidor más cargado), puede escribir después de la de `true`. Resultado: la interfaz dice «hecha» hasta la siguiente revalidación, y la base dice «pendiente».

Dos formas de cerrarlo, de más simple a más robusta:

**1. No permitir envíos mientras hay uno en curso.** Para un check suele ser suficiente y es lo más fácil de razonar:

```tsx
<button type="submit" aria-pressed={done} disabled={fetcher.state !== "idle"}>
  <span aria-hidden="true">{done ? "✓" : "○"}</span> {todo.title}
</button>
```

**2. Que el servidor descarte escrituras antiguas.** El cliente envía el momento de su intención y la base solo acepta cambios más recientes que el último aplicado:

```tsx
<input type="hidden" name="requestedAt" value={String(Date.now())} />
```

```ts
// app/data/todos.server.ts (extracto, con un cliente SQL que parametriza los valores)
export async function setTodoDone(id: string, done: boolean, requestedAt: Date): Promise<void> {
  await sql`
    UPDATE todos
    SET done = ${done}, done_changed_at = ${requestedAt}
    WHERE id = ${id} AND (done_changed_at IS NULL OR done_changed_at < ${requestedAt})
  `;
}
```

La action lee `requestedAt`, lo convierte con `new Date(Number(...))` y se lo pasa. Si la petición de `false` llega tarde con un `requestedAt` anterior, el `WHERE` no la deja escribir. El reloj del cliente no tiene por qué ser exacto, porque solo se comparan intenciones del mismo cliente entre sí.

Mi recomendación: la opción 1 para la mayoría de listas; la 2 cuando el mismo dato puede cambiarse muy rápido desde varios sitios (varias pestañas, varios dispositivos), donde deshabilitar el botón no basta.

Comprobación: con *Slow 3G* y la opción 1, el botón queda deshabilitado durante el envío. Con la opción 2, simula el desorden añadiendo en la action un retraso aleatorio (`await new Promise((r) => setTimeout(r, Math.random() * 2000))`), haz clic tres veces y recarga: el estado de la base debe coincidir siempre con el último clic.""",
            },
        ]
    },
    # 19) De Remix v2 a React Router v7: orden de migración y json()/defer() (intermedio-avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos una app en Remix v2 y queremos pasar a React Router v7. ¿Qué cambia exactamente y en qué orden lo hacemos para no romper nada? Usamos mucho `json()` y algo de `defer()` en los loaders.",
            },
            {
                "role": "assistant",
                "content": """React Router v7 **es** Remix v3 con otro nombre: el equipo fusionó ambos proyectos. Por eso la migración es más un cambio de paquetes y de configuración que una reescritura, siempre que la hagáis en este orden.

**Paso 0: activar en Remix v2 todos los *future flags* y arreglar lo que rompan.** Es la parte con cambios de comportamiento reales, y conviene hacerla con la app todavía en Remix, flag a flag, con los tests pasando tras cada uno:

```ts
// vite.config.ts (todavía en Remix v2)
import { vitePlugin as remix } from "@remix-run/dev";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    remix({
      future: {
        v3_fetcherPersist: true,
        v3_relativeSplatPath: true,
        v3_throwAbortReason: true,
        v3_singleFetch: true,
        v3_lazyRouteDiscovery: true,
        v3_routeConfig: true,
      },
    }),
  ],
});
```

`v3_singleFetch` es el que toca vuestros loaders: con él, los loaders pueden devolver objetos normales (incluidos `Date`, `Map` o promesas), y `json()` y `defer()` dejan de ser necesarios.

**Paso 1: cambiar paquetes.** Existe un codemod que hace casi todo (`npx codemod remix/2/react-router/upgrade`); conceptualmente, la correspondencia es:

| Remix v2 | React Router v7 |
|---|---|
| `@remix-run/react` | `react-router` |
| `@remix-run/node`, `@remix-run/cloudflare` | `@react-router/node`, `@react-router/cloudflare` |
| `@remix-run/dev` | `@react-router/dev` |
| `@remix-run/serve` | `@react-router/serve` |
| `remix vite:dev` / `remix vite:build` | `react-router dev` / `react-router build` |

**Paso 2: configuración.**

```ts
// vite.config.ts
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

export default defineConfig({ plugins: [reactRouter()] });
```

```ts
// react-router.config.ts
import type { Config } from "@react-router/dev/config";

export default { ssr: true } satisfies Config;
```

```ts
// app/routes.ts: conserva vuestra convención de archivos de Remix tal cual
import { type RouteConfig } from "@react-router/dev/routes";
import { flatRoutes } from "@react-router/fs-routes";

export default flatRoutes() satisfies RouteConfig;
```

**Paso 3: loaders sin `json()` ni `defer()`**, con los tipos generados:

```ts
// antes (Remix v2)
import { json, type LoaderFunctionArgs } from "@remix-run/node";

export async function loader({ params }: LoaderFunctionArgs) {
  const product = await getProduct(params.id!);
  if (!product) throw json({ message: "No encontrado" }, { status: 404 });
  return json({ product });
}
```

```ts
// después (React Router v7)
import { data } from "react-router";
import type { Route } from "./+types/products.$id";

export async function loader({ params }: Route.LoaderArgs) {
  const product = await getProduct(params.id); // ya no hace falta el `!`: el tipo sabe que existe
  if (!product) throw data({ message: "No encontrado" }, { status: 404 });
  return { product };
}
```

- **`return json(x)` → `return x`.** Solo necesitas `data(x, { status, headers })` cuando quieras fijar estado o cabeceras.
- **`defer({ reviews: promise })` → `return { reviews: promise }`**: las promesas se devuelven directamente, y `<Await>` con `Suspense` funciona igual que antes.
- **`useLoaderData<typeof loader>()` → `loaderData` en las props** del componente (`Route.ComponentProps`), o el mismo hook sin genérico manual.

**Paso 4: TypeScript.** Añadid `.react-router/types/**/*` al `include` de `tsconfig.json` y `"rootDirs": [".", "./.react-router/types"]`, para que los imports de `./+types/...` resuelvan.

Orden de trabajo que funciona: una rama por paso, cada una desplegable. El paso 0 puede durar días (flag a flag, con pruebas); los pasos 1-4 suelen caber en uno o dos días, porque son mecánicos.

Comprobación por paso: tras el 0, la suite completa en verde con todos los flags activos; tras el 4, `npx react-router typegen && npx tsc --noEmit` sin errores, y los tests end-to-end (Playwright o similares) recorriendo los flujos principales en el entorno de staging antes de tocar producción.""",
            },
        ]
    },
    # 20) Effect-TS: errores tipados, timeout y reintentos frente a async/await (SISTEMA, avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Me recomendaron Effect-TS para manejar errores en un backend TypeScript. ¿Qué gano frente a async/await con try/catch? Enséñamelo con un caso real: llamar a una API externa con timeout, reintentos y errores tipados.",
            },
            {
                "role": "assistant",
                "content": r"""Lo que ganas se resume en una firma. Con async/await, una función que llama a una API devuelve `Promise<Rate>` y el `catch` recibe `unknown`: el tipo no dice **cómo** puede fallar. Con Effect devuelve `Effect<Rate, NetworkError | HttpError | ...>`: los errores posibles forman parte del tipo, el compilador te obliga a tratarlos o propagarlos, y timeout, reintentos y cancelación se componen como piezas en lugar de escribirse a mano.

El caso, con Effect 3:

```ts
// src/rates.ts
import { Data, Duration, Effect, Schedule, Schema } from "effect";

export class NetworkError extends Data.TaggedError("NetworkError")<{ readonly cause: unknown }> {}
export class HttpError extends Data.TaggedError("HttpError")<{ readonly status: number }> {}
export class InvalidJsonError extends Data.TaggedError("InvalidJsonError")<{ readonly cause: unknown }> {}

export const Rate = Schema.Struct({ currency: Schema.String, value: Schema.Number });
export type Rate = typeof Rate.Type;

const fetchJson = (url: string) =>
  Effect.gen(function* () {
    const response = yield* Effect.tryPromise({
      try: (signal) => fetch(url, { signal }), // la señal permite cancelar la petición de verdad
      catch: (cause) => new NetworkError({ cause }),
    });
    if (!response.ok) {
      return yield* Effect.fail(new HttpError({ status: response.status }));
    }
    return yield* Effect.tryPromise({
      try: () => response.json() as Promise<unknown>,
      catch: (cause) => new InvalidJsonError({ cause }),
    });
  });

export const getRate = (currency: string) =>
  fetchJson(`https://rates.example.com/v1/${encodeURIComponent(currency)}`).pipe(
    Effect.flatMap(Schema.decodeUnknown(Rate)), // valida la forma de la respuesta: ParseError si no cuadra
    Effect.timeout(Duration.seconds(3)),         // cada intento, como mucho 3 s
    Effect.retry({
      schedule: Schedule.exponential(Duration.millis(200)).pipe(Schedule.intersect(Schedule.recurs(3))),
      while: (error) =>
        error._tag === "NetworkError" ||
        error._tag === "TimeoutException" ||
        (error._tag === "HttpError" && error.status >= 500),
    }),
  );
// Tipo inferido:
// Effect<Rate, NetworkError | HttpError | InvalidJsonError | ParseError | TimeoutException, never>
```

En el borde de la aplicación (un handler HTTP), se ejecuta y se traduce a una respuesta:

```ts
import { Effect } from "effect";
import { getRate } from "./rates";

export async function handleGetRate(currency: string): Promise<Response> {
  return Effect.runPromise(
    getRate(currency).pipe(
      Effect.map((rate) => Response.json(rate)),
      Effect.catchTags({
        HttpError: (error) =>
          Effect.succeed(Response.json({ error: `El proveedor respondió ${error.status}` }, { status: 502 })),
        ParseError: () => Effect.succeed(Response.json({ error: "Respuesta inesperada del proveedor" }, { status: 502 })),
        TimeoutException: () => Effect.succeed(Response.json({ error: "El proveedor no respondió a tiempo" }, { status: 504 })),
      }),
      Effect.catchAll((error) => Effect.succeed(Response.json({ error: error._tag }, { status: 502 }))),
    ),
  );
}
```

Qué hace cada pieza y por qué importa:

- **`Data.TaggedError`** crea errores con un `_tag` discriminante. `catchTags` maneja cada uno por nombre, y si añades un error nuevo a `fetchJson`, el tipo del handler lo refleja: no hay errores «nuevos» que caigan en un `catch` genérico sin que nadie lo note.
- **`Effect.timeout` antes de `Effect.retry`**: el límite se aplica a cada intento. Al revés, sería un límite total para todos los intentos juntos. Es una decisión, y aquí queda visible en el orden de las líneas.
- **El timeout cancela la petición**: al interrumpirse el efecto, se aborta la `signal` que recibió `fetch`. Con async/await tendrías que montar tú el `AbortController` y el `setTimeout`, y es fácil olvidar limpiarlos.
- **`while` decide qué se reintenta**: errores de red, timeouts y 5xx sí; un 404 o un JSON con forma incorrecta no, porque reintentarlos no cambia nada.
- **`Schema.decodeUnknown`** valida en tiempo de ejecución lo que el tipo solo promete. Un `as Rate` no comprueba nada.

La versión con async/await que hace lo mismo necesita un bucle de reintentos con espera exponencial, un `AbortController` por intento, un `try/catch` con `unknown`, comprobaciones de `instanceof` para decidir qué reintentar y validación manual. Es factible, pero cada equipo la escribe distinta y los tipos no la protegen.

**El coste**, para decidir con honestidad: Effect es un modelo de programación nuevo (generadores, `pipe`, servicios) con una curva real, y añade una dependencia que acaba por todo el código que la toca. Adóptalo primero en una zona acotada donde los errores importen mucho (integraciones externas, pagos) y amplía si al equipo le compensa.

Comprobación: un test con un `fetch` falso que devuelva 503 dos veces y luego 200 debe terminar en éxito tras tres llamadas; uno que devuelva 404 debe fallar con `HttpError` tras una sola llamada; y uno que nunca responda debe fallar con `TimeoutException` (con `TestClock` de Effect se prueba sin esperar segundos reales).""",
            },
        ]
    },
    # 21) Effect-TS: servicios y layers para inyectar dependencias y testear (multiturno, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Me convenció lo de los errores tipados en Effect. ¿Cómo hago inyección de dependencias para poder testear la lógica sin llamar a la API real de tipos de cambio?",
            },
            {
                "role": "assistant",
                "content": """Con **servicios** y **layers**, que son la otra mitad de Effect. Un `Effect` tiene tres parámetros de tipo: `Effect<Éxito, Error, Requisitos>`. El tercero lista los servicios que necesita para ejecutarse, y el compilador no te deja ejecutarlo hasta que se los proporcionas. La inyección de dependencias queda verificada en tiempo de compilación.

**1. Declarar el servicio** como una etiqueta con su interfaz:

```ts
// src/rates-client.ts
import { Context, Effect, Layer } from "effect";
import type { Cause, ParseResult } from "effect";
import { getRate, type HttpError, type InvalidJsonError, type NetworkError, type Rate } from "./rates";

export type RatesError =
  | NetworkError
  | HttpError
  | InvalidJsonError
  | ParseResult.ParseError
  | Cause.TimeoutException;

export class RatesClient extends Context.Tag("RatesClient")<
  RatesClient,
  { readonly getRate: (currency: string) => Effect.Effect<Rate, RatesError> }
>() {}

// Implementación real: la función con timeout y reintentos de antes.
export const RatesClientLive = Layer.succeed(RatesClient, { getRate });
```

**2. La lógica pide el servicio y no sabe qué implementación recibe:**

```ts
// src/pricing.ts
import { Effect } from "effect";
import { RatesClient } from "./rates-client";

export const priceInCurrency = (amountEur: number, currency: string) =>
  Effect.gen(function* () {
    const rates = yield* RatesClient;
    const rate = yield* rates.getRate(currency);
    return Math.round(amountEur * rate.value * 100) / 100;
  });
// Tipo: Effect<number, RatesError, RatesClient>
```

**3. En producción, se proporciona la implementación real en el borde:**

```ts
// src/server.ts (extracto)
import { Effect } from "effect";
import { priceInCurrency } from "./pricing";
import { RatesClientLive } from "./rates-client";

const price = await Effect.runPromise(priceInCurrency(100, "USD").pipe(Effect.provide(RatesClientLive)));
```

Si olvidas el `Effect.provide`, no compila: `runPromise` solo acepta efectos cuyo tipo de requisitos sea `never`, y el error dice exactamente que falta `RatesClient`.

**4. En los tests, otra implementación**, sin mocks de módulos ni de `fetch`:

```ts
// src/pricing.test.ts
import { Effect, Exit, Layer } from "effect";
import { describe, expect, it } from "vitest";
import { priceInCurrency } from "./pricing";
import { HttpError } from "./rates";
import { RatesClient } from "./rates-client";

const fixedRate = (value: number) =>
  Layer.succeed(RatesClient, {
    getRate: (currency) => Effect.succeed({ currency, value }),
  });

describe("priceInCurrency", () => {
  it("convierte con el tipo de cambio y redondea a céntimos", async () => {
    const price = await Effect.runPromise(
      priceInCurrency(100, "USD").pipe(Effect.provide(fixedRate(1.0857))),
    );
    expect(price).toBe(108.57);
  });

  it("propaga el error tipado del proveedor", async () => {
    const failing = Layer.succeed(RatesClient, {
      getRate: () => Effect.fail(new HttpError({ status: 503 })),
    });
    const exit = await Effect.runPromiseExit(priceInCurrency(100, "USD").pipe(Effect.provide(failing)));
    expect(Exit.isFailure(exit)).toBe(true);
  });
});
```

Por qué es mejor que un mock de módulo:

- **El contrato es el tipo de la interfaz.** Un test con una implementación que no cumple la firma (devuelve otro tipo de error, le falta un método) no compila.
- **No hay estado global que limpiar** entre tests: cada uno construye su layer.
- **Los layers se componen.** Si mañana `RatesClientLive` necesita configuración o un cliente HTTP, pasa a ser `Layer.effect(...)` y declara sus propias dependencias; el código de `priceInCurrency` no cambia.

Las versiones recientes de Effect añaden `Effect.Service`, que reduce el código de declarar etiqueta y layer por separado; el modelo es el mismo.

Comprobación: borra el `Effect.provide` del test y verifica que TypeScript se queja de que falta `RatesClient`; esa queja es la inyección de dependencias funcionando.""",
            },
            {
                "role": "user",
                "content": "Todo esto me gusta, pero ¿no es demasiado para un equipo que viene de Express y async/await?",
            },
            {
                "role": "assistant",
                "content": """Puede serlo, y conviene decidirlo con criterios, no con entusiasmo. Effect es un modelo de programación distinto, no una librería de utilidades: generadores, `pipe`, servicios, el tercer parámetro de tipo. La curva es de semanas, y el código con Effect no lo lee con fluidez quien no lo conoce.

**Dónde compensa:**

- Integraciones con terceros donde los fallos son la norma: APIs externas, pagos, colas. Reintentos, timeouts y cancelación son el día a día.
- Lógica con muchos casos de error que el negocio distingue (no es lo mismo «sin saldo» que «proveedor caído»).
- Equipos que ya sufren con errores silenciosos en producción y tests que necesitan mocks frágiles.

**Dónde no**: un CRUD donde el 95 % de los errores acaban en un 500 genérico. Ahí, async/await y un manejador de errores central hacen el trabajo con menos conceptos.

**Cómo adoptarlo sin dividir el código en dos mundos:**

1. **Empieza por una frontera.** Un módulo (por ejemplo, el cliente del proveedor de tipos de cambio) se escribe con Effect; hacia fuera expone funciones normales que devuelven `Promise`, ejecutando el efecto con `Effect.runPromise` en el borde. El resto de la app Express no se entera.
2. **Mide después de un par de meses**: ¿bajaron los incidentes de esa integración?, ¿los tests son más simples?, ¿el equipo lo mantiene sin depender de una sola persona?
3. **Amplía solo si la respuesta es sí**, de dentro hacia fuera: más lógica de dominio en Effect y el borde HTTP lo último.

La señal de que no está funcionando es encontrar `Effect.runPromise` en mitad de la lógica, convirtiendo y reconvirtiendo entre promesas y efectos: eso es pagar el coste de los dos modelos sin el beneficio de ninguno.

Comprobación de la decisión: elige la integración que más incidentes os ha dado este trimestre, reescríbela con Effect detrás de la misma interfaz de promesas, y compara después el número de incidentes y lo que cuesta añadirle un caso de error nuevo.""",
            },
        ]
    },
    # 22) Zustand frente a Jotai para estado de UI y un editor con muchos campos (system tabla, comparación)
    {
        "messages": [
            {"role": "system", "content": "Responde con una tabla comparativa, código mínimo de cada opción y una recomendación clara al final."},
            {
                "role": "user",
                "content": "Para una app React mediana, ¿Zustand o Jotai? Tenemos estado de UI (modales, filtros), un editor con muchos campos que cambian muy rápido, y los datos del servidor ya los llevamos con TanStack Query.",
            },
            {
                "role": "assistant",
                "content": r"""| | Zustand | Jotai |
|---|---|---|
| Modelo | un store (o unos pocos) con estado y acciones, de arriba abajo | átomos pequeños que se combinan, de abajo arriba |
| Re-renders | por selector: el componente se suscribe a una porción del store | por átomo: el componente se suscribe solo a los átomos que lee |
| Estado derivado | selectores o valores calculados en el store | átomos derivados (`atom((get) => ...)`), con dependencias automáticas |
| Uso fuera de React | directo: `useStore.getState()` y `setState()` desde cualquier módulo | posible con un `store` explícito, menos natural |
| Estado por instancia (dos editores a la vez) | un store creado por instancia, con contexto | `Provider` de Jotai por subárbol, de serie |
| Curva | muy baja | baja, pero el modelo de átomos requiere cambiar el chip |

**Estado de UI con Zustand:**

```ts
import { create } from "zustand";

type ModalId = "invite" | "settings";

type UiState = {
  openModal: ModalId | null;
  showModal: (modal: ModalId) => void;
  closeModal: () => void;
};

export const useUiStore = create<UiState>()((set) => ({
  openModal: null,
  showModal: (modal) => set({ openModal: modal }),
  closeModal: () => set({ openModal: null }),
}));

// En un componente: solo se re-renderiza si cambia openModal.
// const openModal = useUiStore((state) => state.openModal);
```

**Editor con Jotai**, un átomo por campo y los cálculos como átomos derivados:

```tsx
import { atom, useAtom, useAtomValue } from "jotai";

export const titleAtom = atom("");
export const bodyAtom = atom("");

export const wordCountAtom = atom((get) => get(bodyAtom).split(/\s+/).filter(Boolean).length);
export const canPublishAtom = atom((get) => get(titleAtom).trim().length > 0 && get(wordCountAtom) >= 50);

export function TitleField() {
  const [title, setTitle] = useAtom(titleAtom); // solo se re-renderiza al cambiar el título
  return <input aria-label="Título" value={title} onChange={(event) => setTitle(event.target.value)} />;
}

export function WordCount() {
  const count = useAtomValue(wordCountAtom); // solo cuando cambia el número, no con cada tecla que no lo altera
  return <p>{count} palabras</p>;
}
```

El editor es donde la diferencia se nota: con un store único, cada tecla en el cuerpo notifica a todos los suscriptores del store, y cada uno ejecuta su selector para decidir si se re-renderiza. Con átomos, la tecla solo toca `bodyAtom` y lo que depende de él (`wordCountAtom`, `canPublishAtom`), y nada más se entera.

**Recomendación: Jotai para esta app.** Vuestro estado de cliente es pequeño (los datos del servidor ya están en TanStack Query), y la parte exigente, el editor, encaja de forma natural con átomos y estado derivado. Modales y filtros también se expresan bien como átomos. Elegiría Zustand si gran parte del estado se modificara desde fuera de React (mensajes de un WebSocket, un SDK), o si el equipo prefiere ver todo el estado y sus acciones en un solo archivo.

Evitad tener ambos: dos modelos de estado de cliente en la misma app duplican convenciones sin aportar nada.

Comprobación: con React DevTools y *Highlight updates when components render* activado, escribe en el cuerpo del editor. Solo deben destellar el campo del cuerpo y el contador de palabras, no el título ni la barra de herramientas.""",
            },
        ]
    },
    # 23) Jotai: átomos asíncronos, átomos de acción y unwrap (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "How do async atoms work in Jotai, and how do I write an action that saves a form and then refreshes the data without the whole UI flashing a loading state?",
            },
            {
                "role": "assistant",
                "content": """An async atom is an atom whose read function returns a promise. Components that read it **suspend** until it resolves, so they need a `Suspense` boundary above them, and an error boundary for rejections. Writes go through a separate **action atom** (a write-only atom), and refreshing is done by bumping a dependency.

```tsx
// src/profile/atoms.ts
import { atom } from "jotai";
import { unwrap } from "jotai/utils";

export type Profile = { id: string; displayName: string };

// Bumping this number re-runs every atom that reads it.
const profileVersionAtom = atom(0);

export const profileAtom = atom(async (get, { signal }) => {
  get(profileVersionAtom);
  const response = await fetch("/api/profile", { signal }); // aborted if a newer read supersedes it
  if (!response.ok) throw new Error(`Failed to load profile: HTTP ${response.status}`);
  return (await response.json()) as Profile;
});

// Same data, but while a refresh is in flight it keeps returning the previous value
// instead of suspending again. Before the first load it returns null.
export const profileOrPreviousAtom = unwrap(profileAtom, (previous) => previous ?? null);

// Write-only action atom: saves, then invalidates the profile.
export const saveDisplayNameAtom = atom(null, async (_get, set, displayName: string) => {
  const response = await fetch("/api/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ displayName }),
  });
  if (!response.ok) throw new Error(`Save failed: HTTP ${response.status}`);
  set(profileVersionAtom, (version) => version + 1);
});
```

```tsx
// src/profile/components.tsx
import { useAtomValue, useSetAtom } from "jotai";
import { useState, type FormEvent } from "react";
import { profileOrPreviousAtom, saveDisplayNameAtom } from "./atoms";

export function ProfileHeader() {
  const profile = useAtomValue(profileOrPreviousAtom);
  if (profile === null) return <p>Loading profile…</p>;
  return <h2>{profile.displayName}</h2>;
}

export function RenameForm() {
  const saveDisplayName = useSetAtom(saveDisplayNameAtom);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const displayName = String(new FormData(event.currentTarget).get("displayName") ?? "").trim();
    if (!displayName) {
      setError("Display name is required");
      return;
    }
    setSaving(true);
    try {
      await saveDisplayName(displayName);
      setError(null);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="displayName">Display name</label>
      <input id="displayName" name="displayName" required />
      <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
```

How the pieces fit:

- **The version atom is the invalidation mechanism.** `profileAtom` reads it, so Jotai records the dependency; incrementing it marks the profile stale and the next read fetches again. No manual cache.
- **`unwrap` is the fix for the flashing.** Reading `profileAtom` directly would suspend on every refresh and swap the header for the nearest `Suspense` fallback. Through `unwrap`, the component keeps showing the previous profile until the new one arrives.
- **Errors still need a boundary**: a rejected load is rethrown when the atom is read, so put an error boundary around components that read profile atoms.
- **`signal`** lets Jotai abort a fetch that a newer read has made obsolete.

Where this stops scaling: Jotai async atoms have no request deduplication across keys, no retries, no stale-time policy and no background refetch. For a few atoms like this, they are enough. For real server state across many screens, TanStack Query does that job (and `jotai-tanstack-query` bridges both if you want atoms on top).

Verification: throttle the network to *Slow 3G* and save a new name. The header must keep showing the old name (no loading text) until the refetch completes, then switch to the new one; and a failing PATCH must show the alert without touching the header.""",
            },
        ]
    },
    # 24) Deno 2: compatibilidad npm, permisos y tests; NotCapable al arrancar (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Qué cambia con Deno 2 respecto a Node? ¿Puedo usar mis paquetes de npm, y vale la pena para un servicio nuevo pequeño?",
            },
            {
                "role": "assistant",
                "content": """Deno 2 elimina el principal motivo para no usarlo: ahora es **compatible con Node y npm**. Puedes importar paquetes de npm (`npm:express`), usar un `package.json` existente y la mayoría de las APIs de Node (`node:fs`, `node:path`). Lo que lo diferencia es todo lo que trae de serie y, sobre todo, su **modelo de permisos**.

| | Node | Deno 2 |
|---|---|---|
| TypeScript | con un paso de compilación o un cargador | nativo, sin configurar |
| Herramientas | instalar formateador, linter, test runner, bundler | `deno fmt`, `deno lint`, `deno test`, `deno compile` incluidos |
| Permisos | el proceso puede hacer todo | sin acceso a red, disco, entorno ni subprocesos salvo que lo concedas |
| Paquetes | npm | npm y JSR (registro nativo de TypeScript) |
| Binario único | herramientas externas | `deno compile` |

Un servicio mínimo, con lo que quieres que sea testeable separado de lo que arranca el servidor:

```ts
// main.ts
export function handler(request: Request): Response {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return Response.json({ status: "ok" });
  }
  return new Response("No encontrado", { status: 404 });
}

if (import.meta.main) {
  const port = Number(Deno.env.get("PORT") ?? "8000");
  Deno.serve({ port }, handler);
}
```

```ts
// main_test.ts
import { assertEquals } from "@std/assert";
import { handler } from "./main.ts";

Deno.test("GET /health responde ok", async () => {
  const response = handler(new Request("http://localhost/health"));
  assertEquals(response.status, 200);
  assertEquals(await response.json(), { status: "ok" });
});

Deno.test("rutas desconocidas responden 404", () => {
  assertEquals(handler(new Request("http://localhost/nada")).status, 404);
});
```

```json
{
  "tasks": {
    "dev": "deno run --watch --allow-net=0.0.0.0:8000 --allow-env=PORT main.ts",
    "test": "deno test"
  },
  "imports": {
    "@std/assert": "jsr:@std/assert@^1.0.0"
  }
}
```

`deno task dev` arranca con recarga; `deno task test` ejecuta los tests sin instalar nada más. Si prefieres Express, `import express from "npm:express@^5"` funciona, aunque para un servicio pequeño `Deno.serve` con un router ligero (o Hono, que corre en Deno) es más natural.

¿Vale la pena para un servicio nuevo y pequeño? Sí, si valoras empezar sin configuración y el modelo de permisos. Me lo pensaría si dependes de paquetes de npm con módulos nativos o scripts de instalación complejos: la compatibilidad es muy alta, pero no total, y es lo primero que conviene probar.

Comprobación: `deno task test` debe pasar los dos tests, y `deno task dev` seguido de `curl localhost:8000/health` debe devolver `{"status":"ok"}`.""",
            },
            {
                "role": "user",
                "content": "Al ejecutarlo sin la task me salió `NotCapable: Requires net access to \"0.0.0.0:8000\", run again with the --allow-net flag`. ¿Le pongo `-A` y listo?",
            },
            {
                "role": "assistant",
                "content": """No. `-A` (`--allow-all`) concede todo y desactiva precisamente lo que hace distinto a Deno. El error es el modelo de permisos funcionando: el proceso intentó abrir un puerto sin que se lo hubieras concedido.

**Por qué importa:** en Node, cualquier dependencia (o dependencia de una dependencia) puede leer `~/.ssh`, las variables de entorno con tus credenciales o enviar datos a cualquier servidor. En Deno, un paquete comprometido solo puede hacer lo que el proceso tiene permitido. Con `-A`, esa protección desaparece entera.

**Concede lo justo**, con permisos acotados:

```bash
deno run \
  --allow-net=0.0.0.0:8000 \
  --allow-env=PORT,DATABASE_URL \
  --allow-read=./config \
  main.ts
```

- `--allow-net=0.0.0.0:8000` permite escuchar en ese puerto. Si el servicio también llama a una API externa, añade su host: `--allow-net=0.0.0.0:8000,api.example.com`.
- `--allow-env=PORT,DATABASE_URL` permite leer solo esas variables, no todo el entorno.
- `--allow-read=./config` limita la lectura a esa carpeta.

Para no repetir la lista, ponla en la task de `deno.json`, como en la respuesta anterior; es la forma de documentar qué necesita el servicio. Y al empaquetarlo, `deno compile` incrusta los permisos en el binario:

```bash
deno compile --allow-net=0.0.0.0:8000 --allow-env=PORT --output health-service main.ts
```

Dos casos que confunden al principio:

- **Paquetes de npm con scripts de instalación** (módulos nativos como `sharp`): Deno no ejecuta esos scripts por defecto. Se autorizan uno a uno con `deno install --allow-scripts=npm:sharp`.
- **En desarrollo, Deno pregunta** de forma interactiva cuando falta un permiso; en producción o en CI no hay a quién preguntar y falla con `NotCapable`, como te pasó. Es intencionado: mejor fallar al arrancar que descubrir un acceso no previsto.

Comprobación: arranca con los permisos acotados y añade temporalmente un `await fetch("https://example.com")` al handler. Debe fallar con `NotCapable` pidiendo acceso a `example.com`: así verificas que los permisos limitan de verdad lo que el proceso puede hacer.""",
            },
        ]
    },
    # 25) Deno Fresh: rutas con handlers, islas con Preact signals y API (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero probar Fresh para un catálogo pequeño con Deno. ¿Cómo funcionan las rutas, los handlers y las islas? Necesito una página de producto con un botón de «añadir al carrito».",
            },
            {
                "role": "assistant",
                "content": """Fresh renderiza cada página en el servidor y envía HTML sin JavaScript, salvo los componentes que pongas en la carpeta `islands/`: esos se hidratan en el navegador, como las islas de Astro. Las rutas se definen por archivos, y cada ruta puede tener un `handler` que se ejecuta en el servidor antes de renderizar. Te lo escribo con la API estable de Fresh 1.x; Fresh 2 cambia la forma de declarar los handlers, así que si empiezas con la 2, revisa su guía de migración.

**La página de producto**, con su handler:

```tsx
// routes/products/[id].tsx
import { Handlers, PageProps } from "$fresh/server.ts";
import AddToCart from "../../islands/AddToCart.tsx";
import { getProduct, type Product } from "../../lib/products.ts";

export const handler: Handlers<Product> = {
  async GET(_request, ctx) {
    const product = await getProduct(ctx.params.id);
    if (!product) return ctx.renderNotFound();
    return ctx.render(product);
  },
};

export default function ProductPage({ data }: PageProps<Product>) {
  return (
    <main>
      <h1>{data.name}</h1>
      <p>{data.description}</p>
      <p>{(data.priceCents / 100).toFixed(2)} €</p>
      <AddToCart productId={data.id} />
    </main>
  );
}
```

**La isla**, el único JavaScript que llega al navegador, con Preact signals:

```tsx
// islands/AddToCart.tsx
import { useSignal } from "@preact/signals";

type Status = "idle" | "saving" | "added" | "error";

export default function AddToCart({ productId }: { productId: string }) {
  const status = useSignal<Status>("idle");

  async function add() {
    status.value = "saving";
    try {
      const response = await fetch("/api/cart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productId }),
      });
      status.value = response.ok ? "added" : "error";
    } catch {
      status.value = "error";
    }
  }

  return (
    <div>
      <button type="button" onClick={add} disabled={status.value === "saving"}>
        {status.value === "added" ? "Añadido" : "Añadir al carrito"}
      </button>
      {status.value === "error" && <p role="alert">No se pudo añadir. Inténtalo de nuevo.</p>}
    </div>
  );
}
```

**El endpoint**, que es una ruta que solo tiene handler:

```ts
// routes/api/cart.ts
import { Handlers } from "$fresh/server.ts";
import { addToCart } from "../../lib/cart.ts";

export const handler: Handlers = {
  async POST(request) {
    const body: unknown = await request.json().catch(() => null);
    const productId = (body as { productId?: unknown } | null)?.productId;
    if (typeof productId !== "string" || productId.length === 0) {
      return Response.json({ error: "productId es obligatorio" }, { status: 400 });
    }
    await addToCart(productId);
    return Response.json({ ok: true }, { status: 201 });
  },
};
```

Lo que conviene saber:

- **Las props de una isla se serializan** para enviarlas al navegador: datos planos, nada de funciones ni clases. Por eso la isla recibe `productId` y no el objeto `Product` completo con métodos.
- **Fresh renderiza bajo demanda** en cada petición, no genera un sitio estático en el build. Es ideal para contenido que cambia (precios, stock) y para desplegar en Deno Deploy; para páginas que nunca cambian, pon delante una caché o considera un generador estático.
- **Todo es estándar web**: el handler recibe un `Request` y devuelve un `Response`, igual que `Deno.serve`. No hay objetos `req`/`res` propios que aprender.

Comprobación: `deno task start`, abre un producto y mira *Ver código fuente*: el HTML trae el nombre y el precio ya renderizados. En la pestaña *Network* solo debe descargarse el JavaScript de la isla `AddToCart`, y un id inexistente debe dar la página 404.""",
            },
        ]
    },
    # 26) SvelteKit: hooks del servidor para sesión, rutas protegidas y errores (SISTEMA, avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En SvelteKit necesito comprobar la sesión en todas las peticiones, tener el usuario disponible en los load y en las actions, proteger todo lo que esté bajo `/admin` y registrar los errores con un id para soporte. ¿Dónde va cada cosa?",
            },
            {
                "role": "assistant",
                "content": r"""Todo eso va en `src/hooks.server.ts`, que se ejecuta en **cada** petición al servidor antes de cualquier `load`, `action` o endpoint: páginas, formularios y rutas `+server.ts` por igual.

**1. Tipar lo que guardas por petición**, en `src/app.d.ts`:

```ts
// src/app.d.ts
declare global {
  namespace App {
    interface Locals {
      user: { id: string; email: string; role: "user" | "admin" } | null;
    }
    interface Error {
      message: string;
      errorId?: string;
    }
  }
}

export {};
```

**2. Los hooks:**

```ts
// src/hooks.server.ts
import { redirect, type Handle, type HandleServerError } from "@sveltejs/kit";
import { sequence } from "@sveltejs/kit/hooks";
import { getUserBySessionToken } from "$lib/server/sessions";

const authenticate: Handle = async ({ event, resolve }) => {
  const token = event.cookies.get("session");
  event.locals.user = token ? await getUserBySessionToken(token) : null;
  return resolve(event);
};

const protectAdmin: Handle = async ({ event, resolve }) => {
  if (event.url.pathname.startsWith("/admin") && event.locals.user?.role !== "admin") {
    redirect(303, `/login?redirectTo=${encodeURIComponent(event.url.pathname)}`);
  }
  return resolve(event);
};

export const handle = sequence(authenticate, protectAdmin);

export const handleError: HandleServerError = ({ error, event, status, message }) => {
  const errorId = crypto.randomUUID();
  console.error({ errorId, status, path: event.url.pathname, error });
  // Al usuario: un mensaje genérico y el id para soporte; nunca el detalle interno.
  return { message: status === 404 ? message : "Ha ocurrido un error inesperado", errorId };
};
```

**3. Usar el usuario en `load` y en las actions**, sin volver a leer la cookie:

```ts
// src/routes/admin/+layout.server.ts
import type { LayoutServerLoad } from "./$types";

export const load: LayoutServerLoad = async ({ locals }) => {
  return { user: locals.user };
};
```

```ts
// src/routes/login/+page.server.ts (extracto: al iniciar sesión)
cookies.set("session", token, {
  path: "/",
  httpOnly: true,
  secure: true,
  sameSite: "lax",
  maxAge: 60 * 60 * 24 * 30,
});
```

Por qué la protección va en el hook y no en `+layout.server.ts`, que es el error más frecuente:

- **Los `load` de un layout no protegen a las rutas hijas.** SvelteKit ejecuta en paralelo los `load` del layout y de la página; el `load` de `/admin/users/+page.server.ts` se ejecuta aunque el del layout lance un `redirect`, salvo que haga `await parent()`. Los datos pueden calcularse (y una acción con efectos, ejecutarse) antes de que el layout corte.
- **Las actions y los endpoints no pasan por el layout.** Un `POST` a `/admin/users?/delete` ejecuta la action directamente; un `fetch` a `/admin/api/export/+server.ts`, el endpoint. Ninguno de los dos ejecuta el `load` del layout. El hook sí intercepta los tres.

Otros detalles:

- **`redirect()` lanza por sí mismo** en SvelteKit 2: no hace falta `throw`.
- **`sequence`** encadena hooks en orden: primero se identifica al usuario y después se decide si puede pasar.
- **`handleError`** solo recibe errores inesperados. Los que lanzas tú con `error(404, ...)` ya son controlados y no pasan por él.
- **`event.locals`** vive solo durante esa petición: es el sitio correcto para el usuario, nunca una variable de módulo, que se compartiría entre usuarios.

Comprobación: con un usuario sin rol de administrador, prueba los tres caminos con `curl -i`: `GET /admin`, `POST /admin/users?/delete` y `GET /admin/api/export`. Los tres deben responder `303` hacia `/login`. Y provoca un error en un `load` (por ejemplo, la base de datos caída): la página de error debe mostrar el `errorId`, y ese mismo id debe aparecer en el log del servidor.""",
            },
        ]
    },
    # 27) SvelteKit con adapter-node en Docker: $env/static incrustado en el build (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": "Desplegamos SvelteKit con `adapter-node` en Docker. En producción la app se conecta a la base de datos de DESARROLLO, aunque arrancamos el contenedor con `-e DATABASE_URL=...` de producción. La importamos con `import { DATABASE_URL } from '$env/static/private'`.",
            },
            {
                "role": "assistant",
                "content": """La causa está en el nombre del módulo: **`$env/static/private` se resuelve en el build**. Vite sustituye `DATABASE_URL` por su valor literal al compilar, y ese valor queda escrito en el JavaScript generado. En tiempo de ejecución, la variable del contenedor ya no se consulta.

La secuencia que te lleva a la base de desarrollo:

1. El `Dockerfile` hace `COPY . .` antes de `npm run build`, y eso incluye tu archivo `.env` local.
2. El build lee ese `.env` y escribe la URL de desarrollo dentro de `build/`.
3. En producción, `-e DATABASE_URL=...` llega al proceso, pero el código ya no la lee: usa la cadena incrustada.

Además de conectarse a otra base, **la URL de desarrollo, con sus credenciales, está dentro de la imagen**. Si esa imagen se subió a un registro, rota esas credenciales.

**Arreglo:**

**1. Leer la variable en tiempo de ejecución** con `$env/dynamic/private`, y crear el cliente de forma perezosa:

```ts
// src/lib/server/db.ts
import { env } from "$env/dynamic/private";
import postgres from "postgres";

let client: ReturnType<typeof postgres> | undefined;

export function db() {
  if (!client) {
    if (!env.DATABASE_URL) throw new Error("Falta DATABASE_URL en el entorno");
    client = postgres(env.DATABASE_URL, { max: 10 });
  }
  return client;
}
```

La creación perezosa evita un segundo problema: SvelteKit importa los módulos del servidor durante el build para analizarlos, y si este módulo lanzara un error al importarse sin `DATABASE_URL`, el build fallaría.

**2. Que el `.env` nunca entre en la imagen:**

```
# .dockerignore
.env
.env.*
node_modules
.svelte-kit
build
```

**3. Un Dockerfile en dos etapas**, en el que la imagen final solo lleva el resultado del build:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
USER node
EXPOSE 3000
CMD ["node", "build"]
```

**4. `ORIGIN` en producción.** Ya que estás con el despliegue: detrás de un proxy, `adapter-node` necesita saber la URL pública, o los formularios con `POST` fallan con `Cross-site POST form submissions are forbidden`. Arranca con `-e ORIGIN=https://app.example.com`.

**Cuándo sí usar `$env/static/*`**: para valores que son de verdad parte del build y no secretos (la versión de la app, un *feature flag* de compilación). Al ser constantes, Vite puede eliminar código muerto con ellos. Todo lo que cambie entre entornos o sea secreto va en `dynamic`.

Comprobación: tras reconstruir la imagen, `grep -r "localhost:5432" build/` (o el host de tu base de desarrollo) no debe encontrar nada. Arranca el contenedor con la URL de producción y verifica en los logs de Postgres de producción que llegan conexiones; arráncalo sin `DATABASE_URL` y la primera consulta debe fallar con «Falta DATABASE_URL en el entorno».""",
            },
        ]
    },
    # 28) Nuxt: server routes con validación, useFetch tipado y errores en $fetch (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "En Nuxt 3 quiero crear endpoints propios en `server/api` para productos: listar con filtros y crear con validación. ¿Cómo se hace y cómo los consumo desde las páginas con tipos?",
            },
            {
                "role": "assistant",
                "content": """Los archivos de `server/api/` son endpoints que ejecuta Nitro, el servidor de Nuxt. El nombre del archivo define la ruta y el sufijo el método (`index.get.ts`, `index.post.ts`). Y lo mejor: Nuxt infiere el tipo de lo que devuelve cada endpoint, así que `useFetch` en las páginas queda tipado sin escribir interfaces.

**Listado con filtros validados:**

```ts
// server/api/products/index.get.ts
import { z } from "zod";

const querySchema = z.object({
  category: z.string().min(1).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

export default defineEventHandler(async (event) => {
  const { category, limit } = await getValidatedQuery(event, querySchema.parse);
  return listProducts({ category, limit });
});
```

**Creación**, con validación propia para devolver los errores por campo:

```ts
// server/api/products/index.post.ts
import { z } from "zod";

const productSchema = z.object({
  name: z.string().trim().min(1, "El nombre es obligatorio").max(200),
  priceCents: z.number().int().nonnegative("El precio no puede ser negativo"),
  category: z.string().min(1, "La categoría es obligatoria"),
});

export default defineEventHandler(async (event) => {
  const user = await requireAdmin(event);
  const result = productSchema.safeParse(await readBody(event));
  if (!result.success) {
    throw createError({
      statusCode: 422,
      statusMessage: "Datos inválidos",
      data: result.error.flatten().fieldErrors,
    });
  }
  const product = await createProduct(result.data, user.id);
  setResponseStatus(event, 201);
  return product;
});
```

`listProducts`, `createProduct` y `requireAdmin` viven en `server/utils/`: Nitro auto-importa lo que exporten esos archivos en todos los endpoints, sin `import`. Asumo que hablan con tu base de datos.

**En la página**, `useFetch` con la consulta reactiva:

```vue
<!-- pages/products/index.vue -->
<script setup lang="ts">
const route = useRoute();
const category = computed(() => (typeof route.query.category === "string" ? route.query.category : undefined));

const { data: products, status, error } = await useFetch("/api/products", {
  query: { category, limit: 20 },
});
</script>

<template>
  <section>
    <p v-if="status === 'pending'">Cargando…</p>
    <p v-else-if="error" role="alert">No se pudieron cargar los productos.</p>
    <ul v-else>
      <li v-for="product in products" :key="product.id">{{ product.name }}</li>
    </ul>
  </section>
</template>
```

Lo que hace cada pieza:

- **`getValidatedQuery(event, schema.parse)`**: valida la query string y responde 400 automáticamente si no cumple. `z.coerce.number()` convierte el `"20"` de la URL en número.
- **`useFetch` en el servidor y en el cliente**: en la primera carga se ejecuta durante el SSR y los datos viajan en el HTML; al navegar, se pide desde el navegador. En el servidor, la llamada a `/api/products` ni siquiera sale por la red: Nitro la resuelve internamente.
- **`query` con un `computed`**: cuando cambia `?category=` en la URL, `useFetch` vuelve a pedir solo.
- **El tipo de `products`** es el de lo que devuelve `listProducts`. Si cambias el endpoint, las páginas que lo usan dejan de compilar donde no cuadren.

Comprobación: `/api/products?limit=500` debe responder 400; `/products?category=cafe` debe renderizarse ya filtrado en el HTML inicial (*Ver código fuente*); y al cambiar la categoría en la URL, la pestaña *Network* debe mostrar una única petición a `/api/products`.""",
            },
            {
                "role": "user",
                "content": "Para crear uso `$fetch` desde un formulario, y cuando falla la validación no sé cómo leer los errores de cada campo.",
            },
            {
                "role": "assistant",
                "content": """`$fetch` lanza un `FetchError` cuando la respuesta no es 2xx, y en su propiedad `data` viene el cuerpo de la respuesta. Para un error creado con `createError`, ese cuerpo tiene la forma `{ statusCode, statusMessage, message, data }`, así que los errores por campo que pusimos en el endpoint están en `error.data.data`.

```vue
<!-- components/ProductForm.vue -->
<script setup lang="ts">
import { FetchError } from "ofetch";

type FieldErrors = Partial<Record<"name" | "priceCents" | "category", string[]>>;

const emit = defineEmits<{ created: [] }>();

const form = reactive({ name: "", priceCents: 0, category: "" });
const fieldErrors = ref<FieldErrors>({});
const formError = ref<string | null>(null);
const saving = ref(false);

async function submit() {
  fieldErrors.value = {};
  formError.value = null;
  saving.value = true;
  try {
    await $fetch("/api/products", { method: "POST", body: form });
    emit("created"); // el padre llama a refresh() de su useFetch
  } catch (error) {
    if (error instanceof FetchError && error.statusCode === 422) {
      fieldErrors.value = (error.data?.data ?? {}) as FieldErrors;
      return;
    }
    formError.value = "No se pudo guardar el producto. Inténtalo de nuevo.";
    console.error(error);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <form novalidate @submit.prevent="submit">
    <label for="product-name">Nombre</label>
    <input id="product-name" v-model="form.name" :aria-invalid="!!fieldErrors.name" />
    <p v-if="fieldErrors.name" class="error">{{ fieldErrors.name[0] }}</p>

    <label for="product-price">Precio (céntimos)</label>
    <input id="product-price" v-model.number="form.priceCents" type="number" :aria-invalid="!!fieldErrors.priceCents" />
    <p v-if="fieldErrors.priceCents" class="error">{{ fieldErrors.priceCents[0] }}</p>

    <label for="product-category">Categoría</label>
    <input id="product-category" v-model="form.category" :aria-invalid="!!fieldErrors.category" />
    <p v-if="fieldErrors.category" class="error">{{ fieldErrors.category[0] }}</p>

    <p v-if="formError" role="alert">{{ formError }}</p>
    <button type="submit" :disabled="saving">{{ saving ? "Guardando…" : "Crear producto" }}</button>
  </form>
</template>
```

Decisiones:

- **Solo el 422 se interpreta como errores de campo.** Un 401 (sesión caducada) o un 500 no tienen esa forma; para ellos, un mensaje general y el error en consola. Mezclarlos produce formularios que «no hacen nada».
- **`useFetch` para leer, `$fetch` para acciones del usuario.** `useFetch` está pensado para datos que se cargan con la página (SSR, caché, deduplicación); dentro de un manejador de evento, `$fetch` es lo correcto.
- **`FetchError` viene de `ofetch`**, la librería sobre la que está construido `$fetch`. Nuxt ya la incluye; si usas pnpm con dependencias estrictas, añádela a `package.json` para importarla.

Comprobación: envía el formulario vacío: deben aparecer los tres errores, cada uno bajo su campo, y en *Network* un 422. Corrige un campo y reenvía: ese error debe desaparecer y los demás seguir. Con datos válidos, 201 y la lista del padre actualizada.""",
            },
        ]
    },
    # 29) Nitro: caché de handlers, storage, routeRules y presets de despliegue (inglés pide español, system variante)
    {
        "messages": [
            {"role": "system", "content": "Responde en español neutro, con ejemplos concretos y sin rodeos."},
            {
                "role": "user",
                "content": "In Nuxt, what does Nitro actually give me beyond server/api? I need caching for an expensive endpoint, a key-value store, and to deploy the same app to Node today and Cloudflare later. Please answer in Spanish.",
            },
            {
                "role": "assistant",
                "content": """Nitro es el servidor sobre el que corre Nuxt, y aporta tres cosas que cubren justo tus tres necesidades: **caché declarativa**, una **capa de almacenamiento** con drivers intercambiables y **presets de despliegue** que compilan la misma app para distintos entornos.

**1. Caché de un endpoint costoso**, sin escribir la lógica de caché:

```ts
// server/api/stats.get.ts
export default defineCachedEventHandler(
  async () => computeExpensiveStats(), // en server/utils, autoimportada
  {
    name: "stats",
    maxAge: 60 * 5,      // 5 minutos
    swr: true,           // al caducar, responde con lo cacheado y recalcula en segundo plano
    getKey: () => "global",
  },
);
```

Con `swr: true`, ningún usuario espera al cálculo tras la caducidad: recibe el valor anterior y el siguiente ya verá el nuevo. Si la respuesta depende del usuario o de parámetros, `getKey` debe incluirlos (`(event) => getQuery(event).region as string`); una clave demasiado general sirve los datos de un usuario a otro.

Para cachear funciones en lugar de endpoints enteros, existe `defineCachedFunction` con las mismas opciones.

**2. Almacenamiento clave-valor con `useStorage`**, sobre *unstorage*:

```ts
// server/api/flags.get.ts
export default defineEventHandler(async () => {
  const storage = useStorage("data");
  return (await storage.getItem<Record<string, boolean>>("feature-flags")) ?? {};
});
```

El código no sabe qué hay detrás: en desarrollo, archivos en disco; en producción, Redis o Cloudflare KV, según la configuración:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  nitro: {
    storage: {
      data: { driver: "redis", url: process.env.REDIS_URL },
    },
    devStorage: {
      data: { driver: "fs", base: "./.data/kv" },
    },
  },
  routeRules: {
    "/blog/**": { swr: 3600 },                 // páginas del blog cacheadas una hora
    "/admin/**": { ssr: false },               // el panel se renderiza solo en el cliente
    "/api/legacy/**": { proxy: "https://legacy.example.com/api/**" },
  },
  runtimeConfig: {
    apiSecret: "", // se sobrescribe en ejecución con NUXT_API_SECRET
  },
});
```

`routeRules` es la otra pieza potente: caché, renderizado y redirecciones por patrón de ruta, en un solo sitio y sin tocar las páginas.

**3. Despliegue con presets**: el mismo código, compilado para cada destino.

```bash
npx nuxi build                                   # por defecto, node-server: .output/server/index.mjs
node .output/server/index.mjs                    # arranque en Node

NITRO_PRESET=cloudflare-pages npx nuxi build     # el mismo proyecto, para Cloudflare
```

Para Cloudflare, el almacenamiento cambia de driver: `{ driver: "cloudflare-kv-binding", binding: "DATA" }`, con el binding declarado en la configuración de Wrangler.

Lo que tienes que vigilar para que el «mismo código» sea verdad:

- **Nada de APIs exclusivas de Node** en `server/`: `fs`, `child_process` o librerías con módulos nativos no existen en Workers. `useStorage` es justo la abstracción que evita el `fs`.
- **Los secretos, vía `runtimeConfig`** y variables `NUXT_*` en ejecución, nunca leyendo `process.env` en el código de los endpoints.
- **Límites de CPU y memoria** de Workers: un `computeExpensiveStats` que en Node tarda dos segundos puede superar el límite de CPU por petición. Ahí la caché deja de ser una optimización y pasa a ser un requisito.

Comprobación: con el preset de Node, llama dos veces a `/api/stats` y mide el tiempo: la segunda debe responder en milisegundos. Después compila con el preset de Cloudflare y ejecuta `npx wrangler pages dev .output/public` (o el comando que indique el build): los endpoints deben funcionar, y cualquier dependencia exclusiva de Node aparecerá ahí como error, antes de llegar a producción.""",
            },
        ]
    },
    # 30) Sitio de documentación: Astro (Starlight) frente a Qwik y Fresh (comparación y recomendación)
    {
        "messages": [
            {
                "role": "user",
                "content": "Vamos a hacer el sitio de documentación de nuestro producto: unas 300 páginas en Markdown, un buscador, ejemplos de código interactivos en algunas páginas y versión en español e inglés. Dudamos entre Astro, Qwik y Fresh. ¿Cuál?",
            },
            {
                "role": "assistant",
                "content": """**Astro, con su tema de documentación Starlight.** Los cuatro requisitos que das son exactamente lo que resuelve sin código propio, y los otros dos están pensados para otro tipo de proyecto.

| Requisito | Astro + Starlight | Qwik (Qwik City) | Fresh |
|---|---|---|---|
| 300 páginas de Markdown/MDX | colecciones de contenido con esquema validado | soporta MDX, con menos herramientas de contenido | Markdown a mano o con librerías |
| Buscador | incluido (Pagefind, índice estático, sin servicio externo) | a construir o integrar | a construir o integrar |
| Ejemplos interactivos | islas con React, Svelte, Vue... solo donde se usan | toda la app es interactiva de forma eficiente | islas de Preact |
| Español e inglés | i18n incluido en Starlight (rutas, selector de idioma, textos de la interfaz) | a montar | a montar |
| Salida | HTML estático, servible desde cualquier CDN | SSR o estático | SSR en cada petición, en Deno |
| JavaScript en una página de texto | cero | mínimo, gracias a la resumabilidad | cero |

Por qué no los otros: **Qwik** brilla cuando la página es una aplicación muy interactiva; una documentación es sobre todo texto, así que su ventaja apenas se nota y te faltaría el ecosistema de contenido. **Fresh** renderiza en el servidor en cada petición y su ecosistema de documentación es pequeño: tendrías que construir buscador, navegación e internacionalización.

Configuración base:

```js
// astro.config.mjs
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import react from "@astrojs/react";

export default defineConfig({
  site: "https://docs.example.com",
  integrations: [
    starlight({
      title: "Acme Docs",
      defaultLocale: "root",
      locales: {
        root: { label: "Español", lang: "es" },
        en: { label: "English" },
      },
      sidebar: [
        { label: "Guías", autogenerate: { directory: "guides" } },
        { label: "Referencia", autogenerate: { directory: "reference" } },
      ],
    }),
    react(), // solo para los ejemplos interactivos
  ],
});
```

Con `defaultLocale: "root"`, el español vive en la raíz (`/guides/...`) y el inglés en `/en/guides/...`; las páginas van en `src/content/docs/` y `src/content/docs/en/`. Si a una página le falta su traducción, Starlight muestra la versión del idioma por defecto con un aviso, en lugar de un 404.

Un ejemplo interactivo dentro de una página MDX, como isla:

```mdx
---
title: Primeros pasos con el SDK
description: Instala el SDK y haz tu primera llamada.
---

import Playground from "../../../components/Playground.tsx";

Instala el paquete y prueba la llamada aquí mismo:

<Playground client:visible snippet="sdk.orders.list({ limit: 5 })" />
```

Con `client:visible`, el JavaScript del playground se descarga solo cuando el lector llega a esa parte; las otras 299 páginas siguen siendo HTML puro.

Plan de arranque: crea el proyecto con la plantilla de Starlight, migra 10 páginas representativas (una con tablas, una con código, una con el playground) y valida el buscador y el cambio de idioma antes de mover el resto.

Comprobación: `npm run build` y revisa una página de texto en el navegador con la pestaña *Network* filtrando por JavaScript: no debe descargarse ningún framework, solo el script del buscador cuando lo abres. Lighthouse debería dar rendimiento alto sin optimizaciones adicionales; y busca un término que solo aparezca en una página en inglés, desde la versión en inglés, para confirmar que el índice separa los idiomas.""",
            },
        ]
    },
]
