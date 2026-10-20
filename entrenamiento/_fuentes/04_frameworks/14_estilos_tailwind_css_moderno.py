"""Estilos: CSS moderno, Tailwind v4, responsive y accesibilidad, arquitectura y debugging de CSS.

30 filas. Reparto aproximado: CSS moderno 14 · Tailwind v4 11 · responsive/accesibilidad,
CSS Modules frente a CSS-in-JS, layouts y debugging 5. Sigue entrenamiento/GUIA_DE_ESTILO.md.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Flexbox: el hijo no se encoge, texto que desborda (España, usuario trae código)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo una lista de chats con avatar, nombre y último mensaje. Quiero que el mensaje se corte con puntos suspensivos si no cabe, pero en vez de eso el texto empuja todo y se sale del contenedor. CSS:

```css
.item { display: flex; gap: 12px; align-items: center; }
.avatar { width: 40px; height: 40px; flex-shrink: 0; }
.texto { flex: 1; }
.mensaje { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
```

El `text-overflow` está puesto, ¿por qué no corta?""",
            },
            {
                "role": "assistant",
                "content": """Porque `.texto` no puede encogerse por debajo del ancho de su contenido, y el contenido es una línea que no se parte. Los hijos de un flex tienen `min-width: auto` por defecto, que significa «como mínimo, lo que mida mi contenido». Con `white-space: nowrap`, ese mínimo es el ancho completo del mensaje, así que `flex: 1` nunca llega a reducirlo y el `overflow: hidden` del nieto no tiene nada que recortar: el que desborda es el padre.

El arreglo es una línea:

```css
.texto { flex: 1; min-width: 0; }
```

Con `min-width: 0`, `.texto` acepta medir menos que su contenido, `flex: 1` lo ajusta al espacio disponible, y `.mensaje` (que ahora sí es más ancho que su padre) se recorta con los puntos suspensivos.

CSS completo y funcional:

```css
.item {
  display: flex;
  gap: 12px;
  align-items: center;
}

.avatar {
  width: 40px;
  height: 40px;
  flex-shrink: 0;          /* el avatar nunca cede espacio */
}

.texto {
  flex: 1;
  min-width: 0;            /* permite encoger por debajo del ancho del contenido */
}

.nombre,
.mensaje {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

Esto es el bug más frecuente de flexbox y aparece con cualquier contenido «incomprimible»: texto sin saltos, `<pre>`, tablas, imágenes sin `max-width`, un `<input>` con `size` por defecto. La regla general: **si un hijo flex no se encoge, ponle `min-width: 0`** (o `overflow: hidden`, que tiene el mismo efecto sobre el mínimo automático, pero también recorta, así que es menos explícito). En columnas (`flex-direction: column`) el equivalente es `min-height: 0`.

Lo mismo pasa en Grid: las pistas con `1fr` tienen `min-width: auto`; por eso `grid-template-columns: 1fr 1fr` se desequilibra cuando una celda tiene una palabra larga, y el arreglo es `minmax(0, 1fr)`.

Comprobación en las herramientas de desarrollo: selecciona `.texto` y mira el ancho calculado. Antes del cambio es mayor que el de `.item`; después, `.item` menos el avatar y el `gap`.""",
            },
        ]
    },
    # 2) Grid: layout de página con áreas y rejilla de tarjetas sin media queries (SISTEMA, multiturno)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero un layout clásico de app: cabecera arriba, barra lateral a la izquierda, contenido, pie. Y que en móvil la barra lateral pase abajo del contenido. ¿Grid o flex? Lo que tengo ahora son tres divs anidados con floats heredados.",
            },
            {
                "role": "assistant",
                "content": """Grid, porque el layout es bidimensional (filas y columnas a la vez) y `grid-template-areas` lo describe de forma literal. Flex sirve para una dimensión; aquí lo usarías dentro de la cabecera, no para la página.

```html
<body class="app">
  <header class="app__header">…</header>
  <nav class="app__sidebar">…</nav>
  <main class="app__main">…</main>
  <footer class="app__footer">…</footer>
</body>
```

```css
.app {
  display: grid;
  min-height: 100dvh;                     /* dvh: la altura real en móvil, sin la barra del navegador */
  grid-template-rows: auto 1fr auto;      /* cabecera y pie miden su contenido; el centro crece */
  grid-template-columns: 16rem minmax(0, 1fr);
  grid-template-areas:
    "header  header"
    "sidebar main"
    "footer  footer";
}

.app__header  { grid-area: header; }
.app__sidebar { grid-area: sidebar; }
.app__main    { grid-area: main; }
.app__footer  { grid-area: footer; }

@media (max-width: 48rem) {
  .app {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto 1fr auto auto;
    grid-template-areas:
      "header"
      "main"
      "sidebar"
      "footer";
  }
}
```

Por qué así:

- **`grid-template-areas` es el plano.** Cambiar el layout en móvil es reescribir el dibujo; no tocas el HTML ni el orden de los elementos en el DOM. El orden del DOM sigue siendo el semántico (nav antes de main), que es lo que leen los lectores de pantalla y lo que recorre el tabulador.
- **`1fr` en la fila central** empuja el pie al final aunque haya poco contenido (el «sticky footer» sin trucos).
- **`minmax(0, 1fr)` y no `1fr`** en la columna de contenido: `1fr` tiene mínimo `auto`, y una tabla ancha o una URL larga en `main` ensancharían la columna y romperían el layout. Con `minmax(0, …)` el contenido se ve obligado a caber (y a desbordar internamente, que es lo que quieres).
- **Media query en `rem`** para que el punto de corte escale con el tamaño de fuente del usuario.

Sobre los floats: elimínalos del todo. Un `float` dentro de una celda de grid sigue funcionando, pero ya no aporta nada y confunde a quien lea el CSS.

Comprobación rápida: en las herramientas de desarrollo, activa la superposición de grid sobre `.app`; verás las áreas con sus nombres. Reduce el ancho por debajo de 768 px y comprueba que la barra lateral aparece entre el contenido y el pie.""",
            },
            {
                "role": "user",
                "content": "Perfecto. Dentro de `main` tengo una rejilla de tarjetas. Ahora uso tres media queries para 1, 2 y 3 columnas. ¿Se puede hacer sin ellas?",
            },
            {
                "role": "assistant",
                "content": """Sí, con `repeat(auto-fit, minmax(...))`: la rejilla calcula cuántas columnas caben según el ancho disponible y el mínimo que le des a cada tarjeta.

```css
.cards {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(min(18rem, 100%), 1fr));
}
```

Cómo lo lee el navegador: «crea tantas columnas como quepan de al menos 18rem, y reparte el espacio sobrante entre ellas». Con 60rem de ancho entran 3; con 40rem, 2; con 30rem, 1. Sin una sola media query, y responde al ancho **del contenedor**, no de la ventana, así que funciona igual si `main` cambia de tamaño porque la barra lateral se pliega.

El `min(18rem, 100%)` evita el caso límite: si el contenedor mide menos de 18rem (móvil estrecho), `minmax(18rem, 1fr)` forzaría un mínimo mayor que el espacio y las tarjetas desbordarían. Con `min()`, el mínimo pasa a ser el 100 % disponible.

**`auto-fit` o `auto-fill`.** Con pocas tarjetas (dos en una fila de tres huecos), `auto-fit` colapsa las columnas vacías y las dos se estiran para ocupar todo; `auto-fill` mantiene el hueco vacío y las tarjetas conservan el tamaño de «tres por fila». Para tarjetas de contenido suele quedar mejor `auto-fill`, para que una fila de dos no tenga tarjetas gigantes; para paneles que deben llenar el espacio, `auto-fit`. Es la única decisión de diseño que te queda.

Si las tarjetas tienen partes que deben alinearse entre sí (título, descripción, botón al pie, todos a la misma altura en la fila), eso ya no lo resuelve la rejilla exterior sino `subgrid` en la tarjeta:

```css
.card {
  display: grid;
  grid-row: span 3;             /* la tarjeta ocupa 3 filas de la rejilla padre */
  grid-template-rows: subgrid;  /* y sus hijos usan esas mismas filas */
}
```

`subgrid` tiene soporte en todos los navegadores actuales desde 2023. Comprobación: pon una tarjeta con un título de dos líneas junto a una de una línea; con `subgrid` las descripciones de ambas empiezan a la misma altura.""",
            },
        ]
    },
    # 3) Container queries (rioplatense, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un componente «tarjeta de producto» que se usa en la home a ancho completo y en la barra lateral, angosto. Con media queries no puedo: a 1200 px de ventana la tarjeta de la barra lateral mide 280 px pero se renderiza en modo «ancho». ¿Cómo se hace esto bien hoy?",
            },
            {
                "role": "assistant",
                "content": """Con *container queries*: el componente consulta el ancho de **su contenedor**, no el de la ventana. Es exactamente el caso para el que se crearon, y tienen soporte en todos los navegadores desde 2023.

Dos pasos: declarar qué elemento es el contenedor, y escribir las reglas con `@container`.

```css
/* 1. El envoltorio de la tarjeta es un contenedor de consultas por ancho */
.product-card-wrapper {
  container-type: inline-size;
  container-name: product;
}

/* 2. Estilos base: la versión angosta, apilada */
.product-card {
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr;
}
.product-card__image { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; }
.product-card__title { font-size: 1.1rem; }

/* 3. Cuando el contenedor mide 32rem o más, pasa al modo ancho */
@container product (min-width: 32rem) {
  .product-card {
    grid-template-columns: 12rem 1fr;
    align-items: start;
  }
  .product-card__title { font-size: 1.5rem; }
}
```

```html
<div class="product-card-wrapper">
  <article class="product-card">
    <img class="product-card__image" src="…" alt="…">
    <div>
      <h3 class="product-card__title">…</h3>
      <p>…</p>
    </div>
  </article>
</div>
```

Detalles que importan:

- **El contenedor no puede ser la propia tarjeta.** Un elemento no puede consultar su propio tamaño (sería circular: el estilo cambia el tamaño, que cambia el estilo). Por eso el envoltorio. En la práctica, el padre que ya existe (la columna de la barra lateral, la celda de la rejilla) suele servir como contenedor; no hace falta un div extra si ya hay uno.
- **`container-type: inline-size`** consulta solo el ancho. `size` consultaría también la altura, pero obliga al contenedor a no tomar la altura de su contenido, que casi nunca es lo que querés.
- **`container-name`** es opcional; sin él, `@container (min-width: …)` usa el contenedor más cercano. Con nombre, la tarjeta consulta el que corresponde aunque haya otros contenedores entre medio (un acordeón, un modal).
- **Unidades `cqi`**: `font-size: clamp(1rem, 4cqi, 1.5rem)` escala con el ancho del contenedor (1cqi = 1 % del ancho inline del contenedor), lo que da tipografía fluida por componente sin ningún `@container`.

Lo que cambia en tu forma de pensar: las media queries quedan para el layout de la página (dónde va la barra lateral); los componentes consultan su contenedor y son reutilizables en cualquier sitio sin saber dónde están.

Comprobación: poné la misma tarjeta en la home y en la barra lateral a 1200 px de ventana. La de la home debe mostrar imagen a la izquierda y texto a la derecha; la de la barra, apilada. Reducí la ventana hasta que la columna principal baje de 32rem y la de la home también se apila, sin tocar nada.""",
            },
        ]
    },
    # 4) :has() para seleccionar el padre (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito que un `<label>` se ponga rojo cuando el input que contiene es inválido, y que una tarjeta sin imagen tenga otro layout. Siempre lo he resuelto con JavaScript añadiendo clases. ¿Hay forma en CSS puro ya?",
            },
            {
                "role": "assistant",
                "content": """Sí: `:has()`, el «selector de padre» que CSS no tuvo durante veinte años. Selecciona un elemento según lo que contenga (o lo que tenga al lado), y los dos casos que describes son sus ejemplos canónicos. Soporte completo desde finales de 2023 (Firefox 121 fue el último).

**1. Etiqueta que reacciona al estado del input que contiene:**

```css
label:has(input:user-invalid) {
  color: var(--color-error);
}

label:has(input:user-invalid)::after {
  content: " — revisa este campo";
  font-size: 0.875em;
}

label:has(input:focus-visible) {
  outline: 2px solid var(--color-focus);
  outline-offset: 4px;
}
```

`:user-invalid` y no `:invalid`: `:invalid` se cumple desde que la página carga (un campo `required` vacío ya es inválido) y pintarías todo el formulario de rojo antes de que el usuario toque nada. `:user-invalid` espera a que haya interactuado con el campo. Mismo soporte que `:has()`.

**2. Tarjeta con o sin imagen:**

```css
.card {
  display: grid;
  gap: 1rem;
  padding: 1rem;
}

.card:has(> img) {
  grid-template-columns: 8rem 1fr;
  padding: 0;
}

.card:not(:has(> img)) {
  border-inline-start: 4px solid var(--color-accent);
}
```

El combinador `>` dentro de `:has()` limita la búsqueda a hijos directos; sin él, una imagen dentro del texto de la tarjeta también activaría el layout de dos columnas.

**Más usos que sustituyen JavaScript:**

```css
/* El contenedor del formulario cambia cuando hay un checkbox marcado */
.plan:has(input[type="checkbox"]:checked) { background: var(--color-selected); }

/* Fila de una tabla con una celda de error */
tr:has(td.error) { background: var(--color-error-bg); }

/* La página bloquea el scroll mientras hay un diálogo abierto */
html:has(dialog[open]) { overflow: hidden; }

/* Un título seguido de subtítulo reduce su margen inferior */
h2:has(+ .subtitle) { margin-block-end: 0.25rem; }
```

Dos cosas que conviene saber antes de usarlo en todas partes:

- **Rendimiento.** El navegador tiene que reevaluar `:has()` cuando cambia el subárbol. En selectores acotados (`label:has(input…)`, `.card:has(> img)`) es imperceptible; `body:has(.cualquier-cosa)` sobre un DOM enorme que muta constantemente sí puede notarse. Mantén el ámbito pequeño.
- **Especificidad.** `:has()` toma la especificidad del argumento más específico que contenga, como `:is()`. `label:has(input:user-invalid)` vale (0,2,1), más que `label.error` (0,1,1). Si un override no se aplica, suele ser esto.

Comprobación del caso 1: campo `<input required>` dentro de un `<label>`; al cargar, la etiqueta debe verse normal; escribe algo, bórralo y sal del campo con tabulador: la etiqueta pasa a rojo con el texto añadido.""",
            },
        ]
    },
    # 5) Nesting nativo de CSS (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Puedo dejar Sass solo por el anidamiento? Es lo único que uso de verdad. ¿Y en qué se diferencia el nesting nativo de CSS del de Sass?",
            },
            {
                "role": "assistant",
                "content": r"""Puedes: el anidamiento nativo tiene soporte en todos los navegadores desde finales de 2023 (incluida la sintaxis relajada, sin `&` obligatorio, desde Chrome 120 y Safari 17.2). Si Sass solo te daba eso, sobra un paso de compilación. Las diferencias con Sass son tres, y una de ellas puede cambiar el comportamiento de tu CSS al migrar.

**Sintaxis:**

```css
.card {
  padding: 1rem;
  border: 1px solid var(--border);

  & h2 { margin-block: 0 0.5rem; }     /* .card h2 */
  h2 { }                                /* lo mismo: el & es opcional desde 2023 */

  &:hover { border-color: var(--accent); }
  &.is-active { background: var(--selected); }
  .theme-dark & { border-color: #444; }  /* & al final: .theme-dark .card */

  @media (width >= 48rem) {
    padding: 2rem;                       /* las at-rules se anidan igual */
  }

  > img { width: 100%; }
}
```

**Diferencia 1: no hay concatenación de nombres.** En Sass, `&__title` genera `.card__title`. En CSS nativo, `&` es un selector, no texto: `&__title` es inválido. Si usas BEM con `&__`, tendrás que escribir `.card__title` completo (dentro del bloque `.card` si quieres, pero con el nombre entero). Es la diferencia que más código toca al migrar.

**Diferencia 2: la especificidad.** CSS nativo trata `&` como `:is(.card)`, y `:is()` toma la especificidad del selector **más específico** de su lista. Con un solo selector no cambia nada, pero con una lista sí:

```css
#sidebar, .card {
  h2 { color: red; }
}
/* Sass genera:   #sidebar h2, .card h2   → .card h2 vale (0,1,1) */
/* CSS nativo es: :is(#sidebar, .card) h2 → AMBOS valen (1,0,1)   */
```

Un `.card h2 { color: blue }` escrito más abajo gana en Sass y **pierde** en CSS nativo. Es poco frecuente, pero cuando pasa es desconcertante. La regla práctica: no anides bajo listas de selectores que mezclen ids y clases.

**Diferencia 3: el orden de las declaraciones.** En CSS nativo, las declaraciones que vienen después de una regla anidada se tratan como si estuvieran antes (el navegador las sube):

```css
.card {
  color: red;
  & h2 { }
  color: blue;    /* se aplica como si estuviera junto a color: red; el resultado es blue, pero... */
}
```

Funciona, pero confunde. Pon las declaraciones primero y las reglas anidadas después, y no hay sorpresa. Los linters (`stylelint` con `declaration-block-no-redundant-longhand-properties` y `no-descending-specificity`) ya avisan.

**Lo que Sass sigue dando y CSS no:** mixins con argumentos, funciones, bucles, `@extend`, variables en tiempo de compilación con operaciones. Si no usas nada de eso, el cambio es quitar la dependencia y renombrar `.scss` a `.css`. Las variables de Sass las sustituyen las custom properties, que además funcionan en runtime.

Verificación de la migración: pasa tu CSS por `stylelint` con `stylelint-config-standard` (reconoce el nesting nativo) y busca con `grep -rn '&__\|&-' src/` las concatenaciones que hay que desplegar.""",
            },
        ]
    },
    # 6) Custom properties: sistema de theming y @property (system variante, intermedio)
    {
        "messages": [
            {"role": "system", "content": "Responde en español, con código completo y explicando el porqué de cada decisión."},
            {
                "role": "user",
                "content": "Estoy montando el sistema de diseño de una app. ¿Cómo organizo las custom properties para colores, espaciado y tipografía de forma que escalen? Ahora tengo 80 variables en `:root` y ya no sé cuál usar.",
            },
            {
                "role": "assistant",
                "content": """Ochenta variables planas en `:root` fallan porque mezclan dos niveles: los valores *brutos* de la paleta y los valores *semánticos* que usan los componentes. Sepáralos en dos capas y la mayoría de decisiones desaparecen.

```css
/* Capa 1: primitivas. Describen QUÉ valores existen. Nadie las usa en componentes. */
:root {
  --blue-50:  oklch(97% 0.02 250);
  --blue-500: oklch(55% 0.18 250);
  --blue-700: oklch(42% 0.16 250);
  --gray-100: oklch(96% 0.005 250);
  --gray-900: oklch(20% 0.01 250);

  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-4: 1rem;
  --space-8: 2rem;

  --font-sans: system-ui, sans-serif;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-xl: 1.25rem;
}

/* Capa 2: tokens semánticos. Describen PARA QUÉ sirve cada valor. Los componentes usan solo estos. */
:root {
  color-scheme: light dark;

  --color-bg:        light-dark(white, var(--gray-900));
  --color-text:      light-dark(var(--gray-900), var(--gray-100));
  --color-primary:   light-dark(var(--blue-500), var(--blue-50));
  --color-primary-hover: light-dark(var(--blue-700), white);
  --color-border:    light-dark(var(--gray-100), oklch(30% 0.01 250));

  --radius: 0.5rem;
  --shadow-sm: 0 1px 2px oklch(0% 0 0 / 0.1);
}

/* Componente: solo tokens semánticos */
.button {
  background: var(--color-primary);
  color: var(--color-bg);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  font: var(--text-base) var(--font-sans);

  &:hover { background: var(--color-primary-hover); }
}
```

Por qué dos capas:

- **El tema oscuro, una marca blanca o un modo de alto contraste cambian solo la capa 2.** Las primitivas no se tocan. `light-dark()` resuelve el tema según `color-scheme` sin media query; si necesitas un conmutador manual, redefine los tokens bajo `[data-theme="dark"]`.
- **La pregunta «¿cuál uso?» tiene respuesta**: en un componente, siempre un token semántico. Si no existe el que necesitas, se añade uno (con nombre por uso: `--color-danger`, no `--red-600`), no se usa la primitiva.
- **El ámbito es gratuito**: redefinir `--color-primary` dentro de `.sidebar` cambia todos los botones de la barra lateral sin tocar `.button`. Es la ventaja sobre las variables de Sass, que desaparecen en compilación.

**Tres detalles técnicos que evitan bugs:**

1. **Fallbacks solo en la frontera.** `var(--color-primary, blue)` en un componente de librería que puede vivir sin tu `:root`; dentro de tu app, un fallback esconde que falta un token.

2. **Las custom properties no tienen tipo**, así que no se animan: un `transition` sobre `--angle` salta de un valor a otro. `@property` les da tipo y las hace animables e interpolables:

```css
@property --progress {
  syntax: "<percentage>";
  inherits: false;
  initial-value: 0%;
}

.progress-bar {
  background: linear-gradient(to right, var(--color-primary) var(--progress), transparent 0);
  transition: --progress 400ms ease-out;
}
.progress-bar[data-done] { --progress: 100%; }
```

Soporte completo desde Firefox 128 (2024).

3. **Un valor inválido no cae al fallback, cae a `initial`/heredado.** `--space-4: 1rem` y luego `margin: var(--space-4)px` no es «1rempx» sino inválido en tiempo de cálculo: el margen pasa a 0, sin aviso. Las unidades van en la definición de la variable, nunca en el uso.

Comprobación de que la arquitectura está bien: busca en los componentes usos directos de primitivas (`grep -rn 'var(--blue\\|var(--gray\\|var(--space-[0-9]' src/components/`); cada coincidencia de color es un sitio que no cambiará de tema. Los de espaciado sí pueden ser primitivas; es aceptable.""",
            },
        ]
    },
    # 7) Cascade layers para domar CSS de terceros (inglés, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "We use a third-party component library plus a reset plus our own styles, and the specificity fights are getting ridiculous: we have `!important` in 40 places just to override the library. Is there a sane way out?",
            },
            {
                "role": "assistant",
                "content": """Cascade layers. `@layer` lets you declare the *priority order* of groups of styles once, and then specificity only matters **within** a layer. Your overrides win because they are in a later layer, not because they are more specific. Supported everywhere since 2022.

```css
/* 1. Declare the order once, first thing in your entrypoint. Later = stronger. */
@layer reset, vendor, base, components, overrides;

/* 2. Put each source in its layer */
@import url("modern-normalize.css") layer(reset);
@import url("@acme/ui/dist/styles.css") layer(vendor);

@layer base {
  body { font-family: var(--font-sans); color: var(--color-text); }
  a { color: var(--color-primary); }
}

@layer components {
  .card { padding: 1rem; border-radius: var(--radius); }
}

@layer overrides {
  /* Beats anything in vendor, however specific the vendor selector is */
  .acme-button { border-radius: var(--radius); }
}
```

What changes:

- The vendor rule `.acme-theme .acme-button.acme-button--primary` (0,3,0) loses to your `.acme-button` (0,1,0) because `overrides` comes after `vendor` in the layer order. Specificity never gets compared across layers.
- **Unlayered styles beat all layers.** That is the escape hatch and the trap: any CSS outside `@layer` wins over everything inside. Use it deliberately (a tiny set of utilities) or not at all. If the library injects styles at runtime without layers, they will be unlayered and will beat yours; wrap them at import time as above, or, if they are injected by JS, that is the one case where you may still need a specificity bump.
- **`!important` inverts the order.** An `!important` declaration in an *earlier* layer beats `!important` in a later one (`reset` > `vendor` > … for important rules). This is by design: it lets a reset say "this really must hold". Practically, remove your 40 `!important`s; the ones you keep should live in the lowest layer that needs them, not the highest.

**Migration plan that does not break the site:**

1. Add the `@layer` declaration line at the top of the entrypoint, with no rules in it yet. Nothing changes: all your CSS is still unlayered.
2. Move the vendor CSS into `layer(vendor)` via `@import … layer()` (or wrap the file's content in `@layer vendor { … }` if you bundle it). Now **all** of your own unlayered CSS beats the vendor. Most `!important`s become redundant at this step; delete them and visually check.
3. Move the reset into `layer(reset)`.
4. Move your own styles into `base`/`components` last, one file at a time. This is the step that can change rendering, because your files start competing with each other by layer order instead of source order; do it with visual regression tests or screenshot diffs per page.

**Debugging:** Chrome and Firefox DevTools show the layer name next to each rule in the Styles panel, and the "Computed" panel tells you which layer won. When a style "does not apply" after this change, the answer is always one of: it is in an earlier layer, or the winning rule is unlayered.

**One more tool for the same problem:** `:where()` has zero specificity, so a library that wraps its selectors in `:where()` can be overridden by any single class without layers. That is the library's job, not yours; but for your own base styles (`:where(a) { color: … }`) it keeps them trivially overridable.

Verification: after step 2, `grep -rn '!important' src/styles | wc -l` should drop sharply, and the remaining ones should each have a comment explaining which unlayered or runtime-injected rule they fight.""",
            },
        ]
    },
    # 8) Propiedades lógicas y RTL (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Nos piden soporte para árabe y hebreo. Tengo cientos de `margin-left`, `padding-right`, `left: 0` y `text-align: left`. ¿Hay que duplicar todo el CSS con `[dir=rtl]`?",
            },
            {
                "role": "assistant",
                "content": """No. Con **propiedades lógicas** el mismo CSS funciona en ambas direcciones: en vez de izquierda/derecha (físico) se escribe inicio/fin (lógico), y el navegador lo invierte solo cuando `dir="rtl"`. Lo que te queda es una sustitución mecánica y unos pocos casos manuales.

La correspondencia (con `writing-mode` horizontal, que es tu caso):

| Físico | Lógico | Qué significa |
|---|---|---|
| `margin-left` / `margin-right` | `margin-inline-start` / `margin-inline-end` | inicio y fin de la línea |
| `margin-top` / `margin-bottom` | `margin-block-start` / `margin-block-end` | inicio y fin del bloque |
| `padding-left` + `padding-right` | `padding-inline` | atajo para ambos |
| `left: 0` / `right: 0` | `inset-inline-start: 0` / `inset-inline-end: 0` | posición |
| `top` / `bottom` | `inset-block-start` / `inset-block-end` | |
| `width` / `height` | `inline-size` / `block-size` | (solo cambia con writing-mode vertical) |
| `border-left` | `border-inline-start` | |
| `border-top-left-radius` | `border-start-start-radius` | primer `start` = bloque, segundo = inline |
| `text-align: left` / `right` | `text-align: start` / `end` | |
| `float: left` | `float: inline-start` | |

```css
/* antes */
.sidebar { margin-left: 1rem; padding-right: 2rem; border-left: 1px solid; text-align: left; }
.badge   { position: absolute; top: 0; right: 0; }

/* después */
.sidebar { margin-inline-start: 1rem; padding-inline-end: 2rem; border-inline-start: 1px solid; text-align: start; }
.badge   { position: absolute; inset-block-start: 0; inset-inline-end: 0; }
```

Y en el HTML, `<html lang="ar" dir="rtl">`: el atributo `dir` es lo que activa la inversión. Ponerlo en `<html>` y no en un div interno hace que también se inviertan las barras de scroll y el `text-align` por defecto.

**Lo que no se traduce solo**, y hay que revisar a mano:

- **Iconos direccionales**: una flecha «siguiente» tiene que apuntar a la izquierda en RTL. `[dir="rtl"] .icon-next { transform: scaleX(-1); }`. Los que no son direccionales (una lupa, un reloj) no se invierten.
- **Sombras y gradientes con dirección** (`box-shadow: 2px 0 …`, `linear-gradient(to right, …)`): no tienen versión lógica; `[dir="rtl"]` para los pocos que haya, o usa `to inline-end`... que aún no existe. Gradientes verticales no necesitan nada.
- **Transformaciones y animaciones** con `translateX`: igual, caso a caso.
- **Flex y grid ya son lógicos**: `justify-content: flex-start` y `grid-column: 1` se invierten solos. Lo que no se invierte es `order` ni nada que dependa de coordenadas.
- **Números y fechas**: el texto árabe es RTL, pero los números y los números de teléfono se leen LTR; `unicode-bidi` y `<bdi>` para fragmentos mixtos.

**Cómo hacer la sustitución sin revisar cientos de líneas a mano:** `stylelint` con `stylelint-use-logical` (regla `csstools/use-logical: always`) marca cada propiedad física y tiene `--fix` para la mayoría. Después, `grep -rn 'left\\|right' src/styles/` lista lo que queda (sombras, transforms, iconos) para la revisión manual.

Verificación: abre la app con `dir="rtl"` en `<html>` y compara con una captura LTR en espejo. Todo lo que esté en el mismo sitio en ambas (no espejado) es una propiedad física que se escapó, salvo los casos de la lista.""",
            },
        ]
    },
    # 9) clamp() y tipografía fluida (usuario en inglés pide español, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "I keep seeing `font-size: clamp(1rem, 2vw + 0.5rem, 2rem)` for fluid typography. How do I actually compute those numbers for my own breakpoints, and is it accessible? Answer in Spanish please, my team reads Spanish.",
            },
            {
                "role": "assistant",
                "content": """`clamp(mínimo, preferido, máximo)` devuelve el valor preferido acotado entre los dos extremos. La tipografía fluida consiste en que el valor preferido sea una recta en función del ancho de la ventana, de modo que pase por dos puntos que tú eliges: «a 20rem de ancho quiero 1rem; a 80rem quiero 2rem». Los números se calculan, no se adivinan.

**La fórmula.** Con el tamaño mínimo `f₀` en el ancho `w₀` y el máximo `f₁` en el ancho `w₁` (todo en rem):

```
pendiente  = (f₁ − f₀) / (w₁ − w₀)
ordenada   = f₀ − pendiente × w₀
preferido  = ordenada rem + (pendiente × 100) vw
```

Para `f₀ = 1rem` en `w₀ = 20rem` y `f₁ = 2rem` en `w₁ = 80rem`:

```
pendiente = (2 − 1) / (80 − 20) = 0.01667
ordenada  = 1 − 0.01667 × 20 = 0.6667
preferido = 0.6667rem + 1.667vw
```

```css
h1 {
  font-size: clamp(1rem, 0.667rem + 1.667vw, 2rem);
}
```

Comprobación de la recta: a 20rem de ancho (320 px), `1.667vw` = 0.333rem, más 0.667rem = 1rem ✓; a 80rem (1280 px), `1.667vw` = 1.333rem, más 0.667 = 2rem ✓. Fuera de ese rango, `clamp` fija los extremos.

**La parte de accesibilidad: el término en `rem` es lo que la salva.** Un `font-size: 2vw` a secas no cambia cuando el usuario sube el tamaño de fuente del navegador o hace zoom con texto (WCAG 1.4.4 exige que el texto pueda escalar al 200 %). Al sumarle `0.667rem`, parte del tamaño sí escala con la preferencia del usuario. Dos reglas para que pase la auditoría:

1. **Nunca `vw` solo**; siempre `rem + vw`, como arriba. Si la pendiente te sale tan alta que la parte en `rem` es casi cero (o negativa), el rango de tamaños es demasiado agresivo: acerca `f₀` y `f₁`.
2. **Prueba con zoom del 200 %** (Ctrl +) y con el tamaño de fuente del sistema al máximo. El texto tiene que crecer de forma apreciable; si el `clamp` lo deja clavado en el máximo, sube el máximo o exprésalo también como `rem` (ya lo es) y acepta que crezca.

**Aplícalo a una escala, no a cada elemento.** Define los tokens una vez y úsalos:

```css
:root {
  --text-sm:  clamp(0.875rem, 0.83rem + 0.2vw, 1rem);
  --text-base: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
  --text-lg:  clamp(1.125rem, 1rem + 0.6vw, 1.5rem);
  --text-xl:  clamp(1.5rem, 1.2rem + 1.5vw, 2.5rem);
  --text-2xl: clamp(2rem, 1.3rem + 3.3vw, 4rem);

  --space-fluid: clamp(1rem, 0.5rem + 2.5vw, 3rem);   /* lo mismo sirve para márgenes y gaps */
}
```

El cuerpo de texto apenas debe moverse (de 1rem a 1.125rem); los títulos son los que ganan con la fluidez. Y `--space-fluid` para los márgenes de sección evita la otra docena de media queries.

Para no hacer las cuentas a mano, el generador de Utopia (utopia.fyi) calcula escalas completas con esta misma fórmula; el resultado es CSS plano sin dependencias.

Verificación final: en las herramientas de desarrollo, modo responsive, arrastra el ancho de 320 a 1280 px: el `h1` debe pasar de 16 a 32 px de forma continua, sin saltos, y quedarse en 32 px por encima.""",
            },
        ]
    },
    # 10) aspect-ratio, object-fit y scroll-snap para un carrusel (México, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero un carrusel horizontal de imágenes de productos que se deslice con el dedo y se «pegue» a cada imagen, sin librería de JavaScript. Las imágenes vienen de tamaños distintos y ahorita se ven todas chuecas.",
            },
            {
                "role": "assistant",
                "content": """Se hace con tres propiedades de CSS que hoy soportan todos los navegadores: `scroll-snap` para el deslizamiento que se pega, `aspect-ratio` para que todas las tarjetas midan lo mismo, y `object-fit` para que la imagen llene su caja sin deformarse.

```html
<ul class="carousel" aria-label="Productos">
  <li class="carousel__item"><img src="a.jpg" alt="Tenis blancos" loading="lazy"></li>
  <li class="carousel__item"><img src="b.jpg" alt="Gorra negra" loading="lazy"></li>
  <li class="carousel__item"><img src="c.jpg" alt="Mochila gris" loading="lazy"></li>
</ul>
```

```css
.carousel {
  display: flex;
  gap: 1rem;
  overflow-x: auto;
  scroll-snap-type: x mandatory;         /* al soltar, siempre queda alineado con un elemento */
  scroll-padding-inline: 1rem;           /* el punto de "pegado" respeta el padding del contenedor */
  padding-inline: 1rem;
  overscroll-behavior-x: contain;        /* no arrastra la página al llegar al final */
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;                 /* oculta la barra en Firefox; abajo, en WebKit */
  list-style: none;
  margin: 0;
}
.carousel::-webkit-scrollbar { display: none; }

.carousel__item {
  flex: 0 0 min(80%, 20rem);             /* ancho fijo por tarjeta: 80 % en móvil, 20rem como máximo */
  scroll-snap-align: start;
  scroll-snap-stop: always;              /* un deslizamiento fuerte no se salta tarjetas */
}

.carousel__item img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;                   /* todas las cajas tienen la misma proporción... */
  object-fit: cover;                     /* ...y la imagen la llena recortando, sin deformar */
  object-position: center;
  border-radius: 0.5rem;
  background: #eee;                      /* se ve mientras carga */
}
```

Por qué cada pieza:

- **`scroll-snap-type: x mandatory`** en el contenedor y **`scroll-snap-align: start`** en los hijos son el carrusel entero. `mandatory` obliga a parar en un elemento; `proximity` solo se pega si quedó cerca, que para productos se siente suelto.
- **`flex: 0 0 <ancho>`**: sin crecer ni encoger, cada tarjeta mide lo mismo. Si usas `flex: 1`, todas caben en pantalla y no hay nada que deslizar.
- **`aspect-ratio` + `object-fit: cover`** resuelve lo de las imágenes chuecas: la caja siempre es 4:3 y la imagen se recorta por los bordes para llenarla. Si prefieres ver la imagen completa con franjas, `object-fit: contain`. Y con `aspect-ratio` el navegador reserva el espacio antes de que cargue la imagen, así que el carrusel no brinca (sin *layout shift*).
- **`scroll-padding-inline`** alinea el elemento activo con el padding del contenedor, no con el borde del viewport; sin esto la primera tarjeta queda pegada al borde sin margen.
- **`scrollbar-width: none`** es decisión de diseño: en escritorio también se puede navegar con rueda o Shift + rueda; deja flechas si tus usuarios de escritorio lo necesitan.

Para una fila de «ir a la imagen 3» con botones, no hace falta librería tampoco: `item.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" })`, y el snap se encarga del resto.

Accesibilidad mínima: el `<ul>` con `aria-label`, cada imagen con `alt` descriptivo, y nada de `tabindex` raros; el contenedor con scroll ya recibe foco con teclado en Chrome y Firefox.

Comprobación: en el modo móvil de las herramientas de desarrollo, arrastra y suelta a medio camino entre dos imágenes: debe terminar alineado con una de ellas; y revisa que todas las tarjetas midan exactamente lo mismo aunque las imágenes originales sean verticales u horizontales.""",
            },
        ]
    },
    # 11) Especificidad y :where(): el usuario trae CSS que no se aplica (multiturno, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """No entiendo por qué no se aplica el color del enlace activo. Tengo esto en el CSS del menú y el enlace activo sigue gris:

```css
#main-nav ul li a { color: #555; text-decoration: none; }
.nav-link--active { color: #c00; font-weight: 700; }
```

El `font-weight` sí se aplica, el color no. Y la regla de `.nav-link--active` está después a propósito.""",
            },
            {
                "role": "assistant",
                "content": """Pierde por **especificidad**, y el orden en el archivo solo desempata cuando la especificidad es igual. El `font-weight` se aplica porque ninguna otra regla lo declara: ahí no hay pelea.

La especificidad se compara como una tupla (ids, clases/atributos/pseudoclases, elementos), de izquierda a derecha:

| Selector | Ids | Clases | Elementos | Resultado |
|---|---|---|---|---|
| `#main-nav ul li a` | 1 | 0 | 3 | (1,0,3) |
| `.nav-link--active` | 0 | 1 | 0 | (0,1,0) |

Un solo id gana a cualquier número de clases. Da igual que la segunda regla vaya después.

Tres arreglos, de peor a mejor:

1. **Subir la especificidad del activo**: `#main-nav .nav-link--active` (1,1,0). Funciona hoy y te obliga mañana a escribir otro id para el siguiente estado. Es la escalada que termina en `!important`.

2. **Bajar la del estilo base**, que es el que está mal: un estilo base no debería pesar más que un modificador. Con `:where()`, todo lo que va dentro cuenta cero:

```css
:where(#main-nav) a { color: #555; text-decoration: none; }   /* (0,0,1) */
.nav-link--active   { color: #c00; font-weight: 700; }        /* (0,1,0): gana */
```

3. **Mejor aún, marcar el activo con el atributo semántico** y estilarlo por él. `aria-current="page"` le dice al lector de pantalla cuál es la página actual y te ahorra la clase:

```html
<nav id="main-nav" aria-label="Principal">
  <ul>
    <li><a class="nav-link" href="/">Inicio</a></li>
    <li><a class="nav-link" href="/precios" aria-current="page">Precios</a></li>
  </ul>
</nav>
```

```css
.nav-link {
  color: #555;
  text-decoration: none;
}

.nav-link[aria-current="page"] {   /* (0,2,0) */
  color: #c00;
  font-weight: 700;
}
```

Todas las reglas del menú pesan ahora una o dos clases, y el estado activo gana porque añade un atributo, no por estar más abajo.

`:is()` y `:where()` se parecen y se confunden: los dos agrupan selectores, pero `:is(#main-nav, .menu) a` toma la especificidad del argumento **más** específico (1,0,1), mientras que `:where()` siempre vale cero. Regla práctica: `:where()` para estilos base y resets que deben ser fáciles de sobrescribir; `:is()` solo para acortar listas de selectores.

Comprobación: en Chrome, pasa el ratón sobre el selector en el panel *Styles* y te muestra su especificidad; la declaración tachada es la que perdió. Después del cambio, la regla de `aria-current` no debe aparecer tachada.""",
            },
            {"role": "user", "content": "¿Y no es más rápido ponerle `!important` al color y listo?"},
            {
                "role": "assistant",
                "content": """Más rápido hoy, más caro cada semana siguiente. `!important` no sube la especificidad: saca la declaración a otra liga que gana a todas las normales. Para sobrescribirla después solo te queda otro `!important` más específico o más abajo, y así es como un proyecto acumula cuarenta.

Los usos que sí se defienden:

- **Utilidades que deben ganar siempre por definición**, como `.visually-hidden` o `.hidden { display: none !important; }`: si alguien la pone, quiere ocultar el elemento diga lo que diga el componente.
- **Sobrescribir estilos en línea** que inyecta un script de terceros (`style="color: …"`), que ganan a cualquier selector.
- **Dentro de capas (`@layer`)**, donde la importancia invierte el orden: un `!important` en la capa más baja gana a uno en la más alta. Lo usan los resets para fijar algo que no debe romperse.

Tu caso no es ninguno de los tres: es un estilo base demasiado específico. Arreglar la causa (`:where()` o bajar a clases) es un cambio de una línea y no deja deuda.

Comprobación de que no hace falta: con el arreglo 2 o 3 aplicado, quita cualquier `!important` del menú y verifica que el enlace activo sigue rojo en todas las páginas.""",
            },
        ]
    },
    # 12) prefers-reduced-motion sin quitar animaciones a todos (system variante, intermedio)
    {
        "messages": [
            {"role": "system", "content": "Responde de forma concisa, con código listo para copiar y la razón de cada decisión."},
            {
                "role": "user",
                "content": "Tengo animaciones de entrada al hacer scroll (fundido + deslizamiento hacia arriba) y un parallax en el hero hecho con JS. Un usuario escribió que se mareaba. ¿Cómo lo arreglo sin quitarle las animaciones a todo el mundo?",
            },
            {
                "role": "assistant",
                "content": r"""Respeta `prefers-reduced-motion`: es la preferencia del sistema operativo que activa quien sufre mareos o trastornos vestibulares (macOS e iOS: «Reducir movimiento»; Windows: «Efectos de animación»; Android: «Quitar animaciones»). El principio es **reducir, no eliminar**: lo que marea es el desplazamiento, el zoom y el parallax; un fundido de opacidad no.

**1. Animaciones de entrada: el movimiento, solo con permiso explícito.**

```css
/* Base para todos: aparece con un fundido */
.js .reveal {
  opacity: 0;
  transition: opacity 400ms ease-out;
}
.js .reveal.is-visible {
  opacity: 1;
}

/* El desplazamiento, solo si el usuario no pidió menos movimiento */
@media (prefers-reduced-motion: no-preference) {
  .js .reveal {
    translate: 0 2rem;
    transition: opacity 400ms ease-out, translate 600ms cubic-bezier(0.2, 0.7, 0.2, 1);
  }
  .js .reveal.is-visible {
    translate: 0 0;
  }

  html {
    scroll-behavior: smooth;
  }
}
```

Dos decisiones:

- **`no-preference` en vez de `reduce`.** Escribir el movimiento dentro de `no-preference` lo hace opcional por construcción. Al revés (animar siempre y anularlo en `reduce`), cada animación nueva que alguien olvide anular vuelve a marear.
- **El prefijo `.js`** (lo pone `document.documentElement.classList.add("js")` en el `<head>`) evita que el contenido quede invisible si el JavaScript falla o tarda: sin JS, `.reveal` nunca se oculta.

**2. Parallax en JS: lee la preferencia y reacciona si cambia.**

```js
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const heroBackground = document.querySelector(".hero__bg");
let stopParallax = null;

function startParallax(element) {
  const onScroll = () => {
    element.style.transform = `translateY(${window.scrollY * 0.3}px)`;
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  return () => {
    window.removeEventListener("scroll", onScroll);
    element.style.transform = "";
  };
}

function syncMotionPreference() {
  if (reducedMotion.matches) {
    stopParallax?.();
    stopParallax = null;
  } else if (!stopParallax && heroBackground) {
    stopParallax = startParallax(heroBackground);
  }
}

syncMotionPreference();
reducedMotion.addEventListener("change", syncMotionPreference);
```

El listener de `change` importa: el usuario puede activar la opción con la página abierta y debe notar el cambio sin recargar.

**3. Red de seguridad para animaciones de terceros** (carruseles, librerías) que no controlas:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

`0.01ms` y no `0s` ni `none`: así se siguen disparando `animationend` y `transitionend`, y el código que espera esos eventos (cerrar un modal, desmontar un toast) no se queda colgado. Es uno de los pocos `!important` justificados.

Vídeos con reproducción automática: no los arranques si `reducedMotion.matches`; muestra el póster y un botón de reproducir.

Comprobación: en Chrome, DevTools → menú ⋮ → *More tools* → *Rendering* → *Emulate CSS media feature prefers-reduced-motion* → `reduce`. Recarga y haz scroll: las secciones aparecen con fundido, sin desplazarse, y el fondo del hero queda quieto. Quita la emulación con la página abierta y el parallax debe volver sin recargar.""",
            },
        ]
    },
    # 13) color-scheme: controles nativos y scrollbars en modo oscuro (SISTEMA, intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Hice el modo oscuro con `@media (prefers-color-scheme: dark)` cambiando el fondo y el color del texto del body, pero los inputs, los select, las barras de scroll y el fondo que aparece al hacer overscroll en el iPhone siguen blancos. ¿Tengo que estilar cada control a mano?",
            },
            {
                "role": "assistant",
                "content": r"""No. Te falta declarar `color-scheme`, que es la otra mitad del modo oscuro y la que casi todo el mundo olvida.

- `prefers-color-scheme` es una **consulta**: pregunta qué prefiere el usuario.
- `color-scheme` es una **declaración**: le dice al navegador qué esquemas soporta tu página. Con ella, el navegador pinta en oscuro lo que es suyo: controles de formulario, barras de scroll, el fondo del lienzo (lo que ves en el overscroll), el autocompletado y los colores de sistema.

Sin esa declaración el navegador asume que tu página solo sabe ser clara, aunque tu CSS cambie el fondo del body.

```html
<head>
  <meta name="color-scheme" content="light dark">
  <link rel="stylesheet" href="/styles.css">
</head>
```

```css
:root {
  color-scheme: light dark;
  accent-color: oklch(55% 0.18 250);   /* checkbox, radio, range y progress con tu color */

  /* Tus tokens, sin media query: light-dark() elige según el esquema en uso */
  --surface: light-dark(white, oklch(22% 0.01 250));
  --text-muted: light-dark(oklch(45% 0.01 250), oklch(75% 0.01 250));
}

body {
  background: Canvas;        /* color de sistema: blanco en claro, casi negro en oscuro */
  color: CanvasText;
}
```

Por qué cada pieza:

- **La etiqueta `<meta>`** se aplica antes de que llegue el CSS. Sin ella, con una conexión lenta, el usuario en modo oscuro ve un fogonazo blanco hasta que carga la hoja de estilos.
- **La propiedad en `:root`** es la que manda una vez cargado el CSS, y se puede cambiar por zonas: `.code-block { color-scheme: dark; }` fuerza un subárbol siempre oscuro (con sus scrollbars oscuras) aunque la página esté en claro.
- **`light-dark()`** (en todos los navegadores desde mayo de 2024) resuelve según el `color-scheme` efectivo del elemento. Por eso ya no necesitas la media query: el mismo token cambia solo. Y si mañana añades un conmutador manual, basta con cambiar `color-scheme` en `<html>`; todos los tokens lo siguen.

Una trampa al activarlo: los controles pasan a tener texto claro en modo oscuro. Si algún componente fija `background: white` en un input a mano, ahora tendrá texto claro sobre blanco, ilegible. Búscalos con `grep -rn "background: *white\|background: *#fff" src/` y cámbialos por un token o por `Field`, el color de sistema de los campos (`FieldText` para su texto).

Comprobación: DevTools → *Rendering* → *Emulate CSS media feature prefers-color-scheme* → `dark`. Los `<select>` desplegados, los checkbox, la barra de scroll y el fondo al estirar la página deben verse oscuros. En el panel *Computed* de `<html>` debe figurar `color-scheme: light dark`.""",
            },
        ]
    },
    # 14) Centrar un div: por qué margin auto no centra en vertical (principiante, informal)
    {
        "messages": [
            {
                "role": "user",
                "content": "pregunta tonta pero nunca me sale: como centro un div en medio de la pantalla?? probé `margin: auto` y solo se centra horizontal",
            },
            {
                "role": "assistant",
                "content": """No es tonta: en el flujo normal de bloques, `margin: auto` solo reparte el espacio **horizontal**. En vertical, los márgenes `auto` valen 0 porque un bloque no tiene altura «sobrante» que repartir: el padre mide lo que miden sus hijos. Para centrar en vertical necesitas que el padre tenga altura y un modo de layout que sepa repartirla: grid o flexbox.

La forma más corta, con grid:

```html
<body>
  <main class="center-screen">
    <div class="card">Hola</div>
  </main>
</body>
```

```css
body {
  margin: 0;
}

.center-screen {
  min-height: 100dvh;       /* el padre ocupa toda la pantalla visible */
  display: grid;
  place-items: center;      /* centra en los dos ejes */
}

.card {
  padding: 2rem;
  border: 1px solid #ddd;
  border-radius: 0.5rem;
}
```

`place-items: center` es el atajo de `align-items: center` (vertical) + `justify-items: center` (horizontal).

La equivalente con flexbox, por si ya tienes un contenedor flex:

```css
.center-screen {
  min-height: 100dvh;
  display: flex;
  justify-content: center;  /* eje principal: horizontal */
  align-items: center;      /* eje cruzado: vertical */
}
```

Tres detalles que te van a ahorrar sustos:

- **`min-height` y no `height`.** Con `height: 100dvh`, si el contenido crece más que la pantalla se sale del padre. Con `min-height`, el padre crece con él.
- **`dvh` y no `vh`.** En el móvil, `100vh` incluye la zona que tapa la barra del navegador y el contenido queda un poco por debajo del centro; `100dvh` es la altura visible real.
- **Si el contenido puede ser más alto que la pantalla** (un formulario largo en un móvil en horizontal), `place-items: center` lo centra igual y la parte de arriba queda cortada, sin poder llegar a ella con scroll. En ese caso usa `margin: auto` en el hijo dentro de un padre grid o flex: ahí sí funciona en vertical, y si no cabe, se pega arriba en vez de cortarse.

```css
.center-screen { min-height: 100dvh; display: grid; }
.card { margin: auto; }   /* centra si cabe; si no cabe, empieza arriba */
```

Comprobación: abre la página, reduce la ventana a lo ancho y a lo alto, y la tarjeta debe seguir en el centro. Luego mete mucho texto en la tarjeta y comprueba que puedes ver su principio haciendo scroll.""",
            },
        ]
    },
    # 15) Tailwind v4: configuración CSS-first con @theme en Vite (SISTEMA, principiante-intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Empiezo un proyecto con Vite + React y quiero Tailwind v4. Todos los tutoriales dicen `npx tailwindcss init` y `tailwind.config.js`, pero ese comando ya no me funciona. ¿Cómo se configura ahora, y dónde pongo mis colores de marca?",
            },
            {
                "role": "assistant",
                "content": """En v4 la configuración vive en el CSS (*CSS-first*): no hay `tailwind.config.js` ni `init`, y ese comando ya no existe. Los tutoriales que ves son de v3. Instalación con Vite:

```bash
npm install tailwindcss @tailwindcss/vite
```

```ts
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

```css
/* src/index.css: se importa una sola vez desde main.tsx */
@import "tailwindcss";

@theme {
  --color-brand-50: oklch(97% 0.02 160);
  --color-brand-500: oklch(62% 0.17 160);
  --color-brand-700: oklch(45% 0.14 160);

  --font-display: "Fraunces", ui-serif, serif;

  --radius-card: 0.75rem;

  --breakpoint-3xl: 120rem;
}
```

Con eso ya puedes escribir `bg-brand-500`, `text-brand-700`, `border-brand-50`, `font-display`, `rounded-card` y `3xl:grid-cols-4`.

**Cómo funciona `@theme`.** Cada variable pertenece a un *namespace* según su prefijo, y el prefijo decide qué utilidades genera:

| Variable | Genera |
|---|---|
| `--color-*` | `bg-*`, `text-*`, `border-*`, `fill-*`, `ring-*` y el resto de utilidades de color |
| `--font-*` | `font-*` (familia) |
| `--text-*` | `text-*` (tamaño) |
| `--radius-*` | `rounded-*` |
| `--breakpoint-*` | variantes responsive (`3xl:`) |
| `--spacing` | la unidad base: `p-4` es `calc(var(--spacing) * 4)` |

Además, cada token queda como variable CSS en `:root`, así que en CSS normal o en un `style` puedes usar `var(--color-brand-500)` sin duplicar el valor.

**`@theme` frente a `:root`.** Usa `@theme` para lo que debe tener clases; usa `:root` para variables que no quieres convertir en utilidades (un `--header-height` que solo usa un componente). `@theme` va en el nivel superior del archivo, no anidado dentro de un selector ni de una media query.

**¿Y el `content` de v3?** Ya no se configura: v4 detecta las fuentes automáticamente, escanea el proyecto e ignora lo que está en `.gitignore` y los binarios. Solo hace falta `@source` cuando las clases viven en un sitio ignorado, típicamente un paquete de componentes dentro de `node_modules`.

**Si heredas un `tailwind.config.js`** con plugins de v3 que aún no migraste, la directiva `@config "../tailwind.config.js";` lo carga desde el CSS. Es una pasarela de migración, no la forma de empezar un proyecto nuevo.

Si no usas Vite, el plugin para PostCSS es `@tailwindcss/postcss`, y ya no necesitas `autoprefixer` ni `postcss-import`: v4 hace ese trabajo.

Comprobación: arranca `npm run dev`, pon `<h1 className="font-display text-brand-700">` en `App.tsx` e inspecciona el elemento. El panel *Styles* debe mostrar `color: var(--color-brand-700)`, y en `:root` debe aparecer la variable con su valor en `oklch`.""",
            },
        ]
    },
    # 16) Clases dinámicas que Tailwind no genera (error concreto, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo este componente y en desarrollo a veces se ven los colores y a veces no; en producción casi nunca. ¿Es un bug de Tailwind v4?

```tsx
type Props = { color: "green" | "red" | "amber"; children: React.ReactNode };

export function Badge({ color, children }: Props) {
  return <span className={`bg-${color}-100 text-${color}-800 px-2 rounded-md`}>{children}</span>;
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""No es un bug: Tailwind nunca ejecuta tu código. Lee los archivos del proyecto como **texto plano** y genera CSS solo para los nombres de clase completos que encuentra escritos. En tu archivo aparece `bg-${color}-100`, que no es ninguna clase; `bg-green-100` no aparece en ningún sitio, así que no se genera.

Lo de «a veces sí» confirma el diagnóstico: cuando otro archivo contiene literalmente `bg-green-100` (otro componente, un comentario, un test), la clase se genera por él y tu badge la aprovecha de rebote. Si ese otro uso desaparece, el badge pierde el color.

**Arreglo: un mapa con las clases completas.**

```tsx
import type { ReactNode } from "react";

type BadgeColor = "green" | "red" | "amber";

// Clases escritas completas: el escáner las encuentra en este archivo.
const badgeColorClasses: Record<BadgeColor, string> = {
  green: "bg-green-100 text-green-800",
  red: "bg-red-100 text-red-800",
  amber: "bg-amber-100 text-amber-800",
};

type BadgeProps = { color: BadgeColor; children: ReactNode };

export function Badge({ color, children }: BadgeProps) {
  return (
    <span className={`${badgeColorClasses[color]} rounded-md px-2 py-0.5 text-sm font-medium`}>
      {children}
    </span>
  );
}
```

`Record<BadgeColor, string>` hace que TypeScript avise si añades `"blue"` al tipo y olvidas su entrada en el mapa. La interpolación que queda es correcta porque inserta cadenas que ya están escritas completas en el mismo archivo.

**Si el color es de verdad dinámico** (lo elige el usuario o viene de la base de datos como hex), no hay clase que generar por adelantado. Pasa el valor como variable CSS y usa una utilidad que la lea:

```tsx
import type { CSSProperties, ReactNode } from "react";

type TagProps = { hex: string; children: ReactNode };

export function Tag({ hex, children }: TagProps) {
  return (
    <span
      style={{ "--tag-color": hex } as CSSProperties}
      className="rounded-md bg-(--tag-color)/15 px-2 py-0.5 text-(--tag-color)"
    >
      {children}
    </span>
  );
}
```

`bg-(--tag-color)` es la sintaxis de v4 para `bg-[var(--tag-color)]`. Esa clase sí está escrita completa, y el valor cambia en runtime sin generar CSS nuevo.

**Último recurso: lista blanca.** Desde v4.1 puedes forzar la generación desde el CSS:

```css
@import "tailwindcss";
@source inline("{bg,text}-{green,red,amber}-{100,800}");
```

Lo dejo para el final porque separa la lista de colores del componente que la usa: el día que alguien añada `"blue"` al tipo, compilará y el badge saldrá sin color hasta que alguien recuerde tocar el CSS.

Comprobación: haz `npm run build` y busca la clase en el CSS generado con `grep -o "bg-amber-100" dist/assets/*.css`; debe aparecer aunque ningún otro archivo use ese color.""",
            },
        ]
    },
    # 17) Tailwind v4: dark mode manual con @custom-variant y sin parpadeo (multiturno, Colombia)
    {
        "messages": [
            {
                "role": "user",
                "content": "En Tailwind v4 el `dark:` me funciona según el sistema operativo, pero el cliente quiere un selector para elegir claro, oscuro o «según el sistema». En v3 ponía `darkMode: 'class'` en el config y ahora no tengo config. ¿Cómo se hace?",
            },
            {
                "role": "assistant",
                "content": """Se redefine la variante `dark` desde el CSS con `@custom-variant`. Por defecto, en v4 `dark:` usa `@media (prefers-color-scheme: dark)`; la cambias para que dependa de una clase en `<html>`:

```css
/* src/index.css */
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));
```

Desde ahí, `dark:bg-gray-900` se aplica cuando `<html>` (o cualquier ancestro) tiene la clase `dark`. El `:where()` hace que la variante no sume especificidad: `dark:bg-gray-900` pesa lo mismo que `bg-white` y gana por el orden en que Tailwind emite las variantes, sin sorpresas al combinarla con otras.

La lógica de los tres estados va en un módulo pequeño, sin efectos al importarlo:

```ts
// src/theme.ts
export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system"; // almacenamiento bloqueado: seguimos al sistema
  }
}

export function applyTheme(preference: ThemePreference): void {
  const isDark =
    preference === "dark" || (preference === "system" && window.matchMedia(DARK_QUERY).matches);
  const root = document.documentElement;
  root.classList.toggle("dark", isDark);
  root.style.colorScheme = isDark ? "dark" : "light"; // scrollbars y controles nativos
}

export function setPreference(preference: ThemePreference): void {
  try {
    if (preference === "system") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // sin almacenamiento, la preferencia dura solo esta visita; el tema se aplica igual
  }
  applyTheme(preference);
}

// Mientras la preferencia sea «sistema», sigue los cambios del SO. Devuelve cómo dejar de escuchar.
export function followSystemTheme(): () => void {
  const query = window.matchMedia(DARK_QUERY);
  const onChange = () => {
    if (readPreference() === "system") applyTheme("system");
  };
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
```

Decisiones:

- **«Sistema» no se guarda**: se borra la clave. Quien nunca tocó el selector sigue al sistema operativo para siempre y no queda congelado en lo que tenía el día de su primera visita.
- **`colorScheme` junto con la clase**: la clase cambia tus estilos; `color-scheme` cambia los del navegador (scrollbars, `<select>`, autocompletado). Sin ella tendrías una página oscura con scrollbars blancas.
- **`try/catch` alrededor de `localStorage`**: en iframes con almacenamiento bloqueado lanza una excepción, y un error ahí no debe dejar la app sin tema.

El selector es un `<select>` nativo que llama a `setPreference(event.target.value as ThemePreference)`: ya es accesible con teclado y lector de pantalla. Al arrancar la app, llama una vez a `followSystemTheme()`.

Comprobación: elige «oscuro», recarga y debe seguir oscuro; elige «sistema», cambia el tema del SO con la app abierta y la app debe cambiar sola.""",
            },
            {
                "role": "user",
                "content": "Lo monté en Next.js con un `useEffect` que llama a `applyTheme(readPreference())`, y al recargar en oscuro se ve un parpadeo blanco como de medio segundo. ¿Por qué, si la preferencia ya está guardada?",
            },
            {
                "role": "assistant",
                "content": """Porque `useEffect` se ejecuta **después** del primer pintado. La secuencia al recargar es: llega el HTML del servidor, que no conoce tu preferencia y viene sin la clase `dark` → el navegador lo pinta en claro → React hidrata → corre el efecto → aplica `dark`. Ese medio segundo es el tramo entre el pintado y el efecto.

El arreglo es decidir el tema **antes del primer pintado**, con un script pequeño y bloqueante en el `<head>`, que corre antes de que exista el `<body>`:

```tsx
// app/layout.tsx
import type { ReactNode } from "react";
import "./globals.css";

// Se ejecuta en el navegador antes de pintar. Debe ser autocontenido: no puede importar nada.
const themeScript = `
(function () {
  var stored = null;
  try { stored = localStorage.getItem("theme"); } catch (e) {}
  var dark = stored === "dark" ||
    (stored !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
})();
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100">{children}</body>
    </html>
  );
}
```

Tres detalles:

- **`suppressHydrationWarning` en `<html>`**: el servidor renderiza `<html>` sin la clase y el script la añade antes de hidratar; sin esa prop React avisa del desajuste. Solo afecta a los atributos de ese elemento, no a sus hijos, así que no tapa errores reales del resto de la página.
- **El script repite la lógica de `readPreference`** en JavaScript plano y sin imports porque se inyecta como texto. Es la única duplicación aceptable aquí; déjala junto a `theme.ts` con un test que compruebe que ambas eligen lo mismo para `"light"`, `"dark"` y la ausencia de clave.
- **El `useEffect` se queda**, pero ya no para aplicar el tema inicial sino para escuchar cambios: `useEffect(() => followSystemTheme(), [])`. La función devuelve el «dejar de escuchar», que es justo la limpieza que React espera.

Si prefieres no mantenerlo, `next-themes` hace exactamente esto (script en el `<head>`, tres estados, `suppressHydrationWarning`) y es la opción habitual en proyectos con shadcn/ui.

Comprobación: en DevTools → *Network* pon *Slow 4G*, elige oscuro y recarga: no debe aparecer ningún fotograma blanco. En el HTML recibido (*Ver código fuente*) `<html>` no trae la clase; en el DOM ya la tiene antes del primer pintado.""",
            },
        ]
    },
    # 18) Tailwind v4: responsive mobile-first y container queries de serie (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Con Tailwind puse `sm:flex-col` pensando que era «en móvil, en columna», y en el móvil sigue en fila. ¿Cómo funcionan los breakpoints? Y ya que estamos: ¿puedo hacer que una tarjeta cambie según el ancho de su contenedor y no de la pantalla?",
            },
            {
                "role": "assistant",
                "content": """Los breakpoints de Tailwind son **mobile-first**: una clase sin prefijo se aplica a todos los anchos, y `sm:` significa «de 40rem (640 px) **hacia arriba**». `sm:flex-col` pone la columna en tabletas y escritorio, justo lo contrario de lo que querías. Se escribe el móvil sin prefijo y se va sobrescribiendo hacia arriba:

```html
<!-- columna en móvil, fila desde 40rem -->
<div class="flex flex-col gap-4 sm:flex-row">
```

Los cortes por defecto en v4:

| Prefijo | Desde | Media query |
|---|---|---|
| `sm:` | 40rem (640 px) | `@media (width >= 40rem)` |
| `md:` | 48rem (768 px) | `@media (width >= 48rem)` |
| `lg:` | 64rem (1024 px) | `@media (width >= 64rem)` |
| `xl:` | 80rem (1280 px) | `@media (width >= 80rem)` |
| `2xl:` | 96rem (1536 px) | `@media (width >= 96rem)` |

Para los casos que no encajan en «de aquí hacia arriba»:

- **Solo por debajo**: `max-sm:hidden` oculta en anchos menores de 40rem.
- **Un rango**: `md:max-lg:grid-cols-2` aplica solo entre 48rem y 64rem.
- **Un corte puntual**: `min-[52rem]:flex-row`, sin tocar el tema.
- **Cortes propios**, en el CSS, porque v4 no tiene archivo de configuración:

```css
@theme {
  --breakpoint-xs: 30rem;    /* añade xs: */
  --breakpoint-2xl: 100rem;  /* cambia 2xl: */
}
```

**Container queries: vienen de serie en v4.** Marcas el contenedor con `@container` y los hijos usan variantes con `@`:

```html
<div class="@container">
  <article class="flex flex-col gap-4 rounded-xl border p-4 @md:flex-row">
    <img class="aspect-video w-full rounded-lg object-cover @md:w-48" src="/producto.jpg" alt="Zapatillas de running azules">
    <div class="min-w-0">
      <h3 class="text-lg font-semibold @lg:text-xl">Zapatillas Trail X</h3>
      <p class="text-sm text-gray-600">Amortiguación media, 280 g.</p>
    </div>
  </article>
</div>
```

La misma tarjeta se apila en una barra lateral estrecha y se pone en fila en la columna principal, sin saber dónde está. El `min-w-0` del bloque de texto es el de siempre en flex: sin él, un título largo impediría que el bloque se encoja.

**La trampa:** los tamaños de contenedor no coinciden con los de pantalla. `@md` es 28rem (448 px) y `md:` es 48rem. Son escalas distintas porque un contenedor suele ser bastante más estrecho que la ventana. Si copias `md:` a `@md:` esperando el mismo corte, cambiará mucho antes.

Más opciones: `@max-md:` (por debajo), `@min-[30rem]:` (valor arbitrario) y contenedores con nombre cuando hay varios anidados: `@container/sidebar` en el padre y `@lg/sidebar:` en el hijo.

Comprobación: modo responsive de DevTools a 375 px, el bloque debe salir en columna; a 700 px, en fila. Para la tarjeta, colócala en dos sitios de distinto ancho en la misma página y compara.""",
            },
        ]
    },
    # 19) Cuándo no usar @apply y el @reference de v4 (system variante, intermedio)
    {
        "messages": [
            {
                "role": "system",
                "content": "Responde de forma directa y con criterio; si el planteamiento del usuario es un error, dilo en la primera frase.",
            },
            {
                "role": "user",
                "content": "En mi equipo hay quien quiere dejar el HTML «limpio» metiendo todo en clases con @apply: `.btn-primary { @apply px-4 py-2 bg-blue-600 ... }`, `.card`, `.form-input`, etc. Yo no lo veo claro. ¿Quién tiene razón?",
            },
            {
                "role": "assistant",
                "content": """Tú. Reescribir cada componente como una clase con `@apply` es volver al CSS tradicional con un paso extra, y te quedas con los inconvenientes de ambos mundos.

Lo que se pierde:

- **El problema de los nombres vuelve.** `.btn-primary`, `.btn-primary-small`, `.card-compact`... Tailwind existe en buena parte para no tener que inventarlos ni mantenerlos.
- **Cambiar un estilo deja de ser local.** Con utilidades, tocas el elemento y sabes que no afectas a nada más. Con una `.card` compartida, cada cambio exige buscar dónde se usa.
- **El CSS crece.** Cada `@apply` copia las declaraciones dentro de tu selector; las utilidades, en cambio, se reutilizan. Con cien componentes la diferencia se nota.
- **Las variantes se complican.** `hover:`, `md:` y `dark:` dentro de `@apply` funcionan, pero depurar el CSS resultante cuesta más que leer las clases en el elemento.

El «HTML limpio» se consigue con la abstracción correcta, que es el **componente**, no la clase:

```tsx
import type { ComponentProps } from "react";

export function PrimaryButton(props: ComponentProps<"button">) {
  return (
    <button
      type="button"
      className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
      {...props}
    />
  );
}
```

Las clases largas viven en un solo sitio y el resto de la app escribe `<PrimaryButton>`. Para variantes, `cva` en lugar de ternarios.

**Dónde `@apply` sí tiene sentido:**

1. **HTML que no controlas**: lo que sale de un CMS o de Markdown, o un widget de terceros con sus propias clases.

```css
@layer components {
  .cms-content a {
    @apply font-medium text-blue-700 underline underline-offset-2 hover:text-blue-500;
  }
}
```

2. **Estilos base** de unos pocos elementos sueltos (`h1`, `a`) en `@layer base`.

3. **Sin componentes**: plantillas de servidor puras (Django, Rails) donde repetir veinte clases en cincuenta plantillas no tiene otra salida razonable.

**Un detalle de v4** que os vais a encontrar: en un `<style>` de Vue o Svelte, o en un CSS Module, `@apply` falla con `Cannot apply unknown utility class` porque ese archivo se procesa por separado y no conoce tu tema. Hay que referenciar la hoja principal sin duplicarla:

```vue
<style scoped>
@reference "../assets/main.css";

.legacy-datepicker :deep(.dp-day) {
  @apply rounded-md px-2 py-1;
}
</style>
```

Y muchas veces ni hace falta `@apply`: en v4 el tema está en variables CSS, así que `color: var(--color-blue-700)` en CSS normal hace lo mismo sin acoplarte a la sintaxis de Tailwind.

Para cerrar la discusión con datos: haced el mismo componente de las dos formas, compilad y comparad el tamaño del CSS y lo que cuesta añadir una variante «peligro». Eso suele zanjarlo.""",
            },
        ]
    },
    # 20) Variantes con cva + clsx + tailwind-merge (SISTEMA, multiturno, intermedio-avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo un `<Button>` en React + Tailwind v4 con un montón de ternarios en el className para las variantes (primary, secondary, ghost) y tres tamaños. Encima, cuando le paso `className=\"px-8\"` desde fuera, a veces gana y a veces no. ¿Cómo lo ordeno?",
            },
            {
                "role": "assistant",
                "content": """Son dos problemas con dos herramientas distintas: `cva` para organizar las variantes y `tailwind-merge` para que la clase de fuera gane siempre.

**Por qué `px-8` gana «a veces».** El orden de las clases en el atributo `class` no importa nada en CSS. Lo que decide entre `px-4` y `px-8`, que tienen la misma especificidad, es cuál aparece **después en la hoja de estilos** generada, y ese orden lo fija Tailwind, no tú. Por eso funciona con unas combinaciones y con otras no. La solución no es pelear con el orden sino no emitir nunca las dos: `tailwind-merge` elimina del resultado la clase que entra en conflicto con una posterior.

```bash
npm install class-variance-authority clsx tailwind-merge
```

```ts
// src/lib/cn.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// clsx resuelve los condicionales; twMerge deja solo la última clase de cada grupo en conflicto.
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

```tsx
// src/components/button.tsx
import type { ComponentProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-blue-600 text-white hover:bg-blue-700",
        secondary: "border border-gray-300 bg-white text-gray-900 hover:bg-gray-50",
        ghost: "text-gray-700 hover:bg-gray-100",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonProps = ComponentProps<"button"> & VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
```

Qué ganas:

- **Las variantes son datos**, no ternarios. `VariantProps` deriva los tipos del objeto: `variant="danger"` no compila hasta que añadas la variante.
- **`className` va el último en `cn`**, así que `<Button className="px-8">` sustituye a `px-4` en vez de convivir con él. Gana siempre.
- **`type="button"` por defecto**: un `<button>` sin tipo dentro de un `<form>` es `submit`, y el botón «Cancelar» que envía el formulario es un bug clásico.
- En React 19, `ref` llega como una prop más dentro de `...props`; no hace falta `forwardRef`.

Una trampa de `tailwind-merge`: conoce las escalas por defecto, pero no tus tokens con nombres ambiguos. Si defines `--text-display` en `@theme`, `text-display` es un tamaño de fuente, pero `twMerge` puede tomarlo por un color y eliminar `text-white`. Se le enseña una vez (tailwind-merge v3, la versión para Tailwind v4):

```ts
import { extendTailwindMerge } from "tailwind-merge";

const twMerge = extendTailwindMerge({ extend: { theme: { text: ["display"] } } });
```

Comprobación: `cn("px-4 py-2", "px-8")` debe devolver `"py-2 px-8"`, y `<Button variant="ghost" size="lg">` debe renderizar sin ninguna clase `bg-blue-600`.""",
            },
            {
                "role": "user",
                "content": "Genial. Ahora necesito botones que son solo un icono (cerrar, menú), cuadrados según el tamaño, y que en la variante ghost sean redondos. ¿Lo meto como otra variante?",
            },
            {
                "role": "assistant",
                "content": """Sí: el icono es un tamaño más, y la regla «ghost + icono = redondo» es una combinación de dos variantes, que es justo para lo que existe `compoundVariants`.

```tsx
// src/components/button.tsx: buttonVariants con el tamaño icon y la combinación
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-blue-600 text-white hover:bg-blue-700",
        secondary: "border border-gray-300 bg-white text-gray-900 hover:bg-gray-50",
        ghost: "text-gray-700 hover:bg-gray-100",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
        icon: "size-10",
      },
    },
    compoundVariants: [{ variant: "ghost", size: "icon", class: "rounded-full" }],
    defaultVariants: { variant: "primary", size: "md" },
  },
);
```

`cva` concatena base, variantes y combinaciones en ese orden, así que el resultado contiene `rounded-md ... rounded-full`. Quien resuelve el conflicto es el `cn` del botón: `twMerge` se queda con `rounded-full`, la última. Sin `tailwind-merge`, ganaría la que Tailwind emita después en la hoja.

Y un componente aparte para el caso icono, para que el tipo **obligue** a poner nombre accesible:

```tsx
// src/components/icon-button.tsx
import type { ReactNode } from "react";
import { Button, type ButtonProps } from "@/components/button";

type IconButtonProps = Omit<ButtonProps, "size" | "children"> & {
  "aria-label": string; // sin texto visible, es lo único que anuncia el lector de pantalla
  icon: ReactNode;
};

export function IconButton({ icon, ...props }: IconButtonProps) {
  return (
    <Button size="icon" {...props}>
      <span aria-hidden="true">{icon}</span>
    </Button>
  );
}
```

Uso: `<IconButton variant="ghost" aria-label="Cerrar" icon={<XIcon />} onClick={onClose} />`.

Por qué un componente y no solo `size="icon"`: con `<Button size="icon">` nada impide olvidar el `aria-label`, y un botón con un SVG dentro y sin nombre se anuncia como «botón», sin más. Con `IconButton`, olvidarlo es un error de compilación. El `aria-hidden` en el icono evita que el lector intente leer el SVG.

Comprobación: quita el `aria-label` de un uso y `tsc` debe fallar con *Property '"aria-label"' is missing*; con él, Lighthouse no debe reportar *Buttons do not have an accessible name*.""",
            },
        ]
    },
    # 21) Tailwind v4: @theme con paleta cerrada y fuentes de next/font (inglés, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "We're moving our design system to Tailwind v4 in a Next.js 15 app. Designers want only our brand palette available (no `bg-red-500` sneaking into PRs), and our fonts come from `next/font` as CSS variables. How should the `@theme` look?",
            },
            {
                "role": "assistant",
                "content": r"""Two moves: wipe the default color namespace before declaring yours, and wire the fonts through `@theme inline` so they resolve where `next/font` defines them.

```css
/* app/globals.css */
@import "tailwindcss";

@theme {
  /* Remove every default color: bg-red-500, text-slate-700 and friends stop existing. */
  --color-*: initial;

  --color-white: #fff;
  --color-black: #000;

  --color-ink-900: oklch(21% 0.02 265);
  --color-ink-600: oklch(45% 0.02 265);
  --color-ink-200: oklch(90% 0.01 265);

  --color-brand-100: oklch(95% 0.04 155);
  --color-brand-600: oklch(52% 0.15 155);
  --color-brand-800: oklch(38% 0.11 155);

  --color-danger-600: oklch(53% 0.2 27);
}

@theme inline {
  --font-sans: var(--font-inter);
  --font-mono: var(--font-jetbrains-mono);
}
```

```tsx
// app/layout.tsx
import type { ReactNode } from "react";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains-mono" });

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-white font-sans text-ink-900">{children}</body>
    </html>
  );
}
```

Why each piece:

- **`--color-*: initial`** clears the whole namespace, so only what you declare after it generates utilities. `transparent`, `current` and `inherit` keep working because they are keywords, not theme colors; `white` and `black` are theme colors, which is why they are declared again. The same pattern works per namespace (`--font-*: initial`), or `--*: initial` to start from a blank theme.
- **`@theme inline` for variables that point to other variables.** A regular `@theme` entry becomes `--font-sans: var(--font-inter)` on `:root`, and the utility uses `var(--font-sans)`. CSS resolves that reference where `--font-sans` is defined, at `:root`. If someone later moves the `next/font` classes from `<html>` to `<body>`, `--font-inter` no longer exists at `:root` and the font silently falls back. With `inline`, the utility emits `font-family: var(--font-inter)` directly, resolved on the element that uses it, so it works wherever the variable class sits.

**Enforcing "brand palette only".** After the reset, `bg-red-500` no longer generates CSS, but Tailwind does not error on unknown classes: the element just renders unstyled, and reviewers miss it. A cheap CI guard makes it fail loudly:

```bash
# fails the job if any default-palette color class appears in the source
! grep -rnE "\b(bg|text|border|ring|fill|stroke)-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-[0-9]{2,3}\b" app components
```

**Reading tokens from JavaScript** (charts, canvas): `getComputedStyle(document.documentElement).getPropertyValue("--color-brand-600")`. One catch: v4 only emits the CSS variables that some utility actually uses, so a token consumed only from JS can vanish from the output. Declare those inside a `@theme static` block and they are always emitted.

Verification: run `npm run build` and inspect the CSS in `.next/static/css`. It must not contain `--color-red-500`, it must contain `--color-brand-600`, and the `font-sans` rule must compile to `font-family: var(--font-inter)`.""",
            },
        ]
    },
    # 22) Tailwind v4: @utility, --value() y variantes propias; migrar @layer utilities (rioplatense, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenía en v3 un plugin con `addUtilities` para esconder la scrollbar y otro con `matchUtilities` para `tab-size` con valores del theme. Ahora que v4 no tiene config, ¿dónde meto eso? ¿Sigo con plugins en JS?",
            },
            {
                "role": "assistant",
                "content": """No hace falta JS para ninguno de los dos: en v4 las utilidades propias se declaran en el CSS con `@utility`, y las que reciben valores usan la función `--value()`.

**Utilidad estática** (lo que hacía `addUtilities`):

```css
@import "tailwindcss";

@utility scrollbar-hidden {
  scrollbar-width: none;            /* propiedad estándar */
  &::-webkit-scrollbar {
    display: none;                  /* WebKit sin soporte de scrollbar-width */
  }
}
```

**Utilidad funcional** (lo que hacía `matchUtilities`):

```css
@theme {
  --tab-size-2: 2;
  --tab-size-4: 4;
  --tab-size-github: 8;
}

@utility tab-* {
  tab-size: --value(--tab-size-*, integer, [integer]);
}
```

`--value()` prueba las opciones en orden:

- `--tab-size-*`: busca en el tema; `tab-github` → `var(--tab-size-github)`.
- `integer`: acepta un entero desnudo; `tab-3` → `3`.
- `[integer]`: acepta valores arbitrarios; `tab-[13]` → `13`.

Si ninguna encaja (`tab-foo`), la clase no genera nada, igual que una utilidad de serie.

Lo importante: lo que declarás con `@utility` funciona con **todas las variantes** sin hacer nada más (`md:scrollbar-hidden`, `hover:tab-4`, `dark:tab-2`) y entra en la capa de utilidades, ordenado junto a las de serie.

**Variantes propias**, que en v3 eran `addVariant`:

```css
@custom-variant contrast-high (&:where([data-contrast="high"], [data-contrast="high"] *));
```

y ya podés escribir `contrast-high:border-2`.

**¿Y si el plugin es de terceros o tiene lógica de verdad en JS?** Se carga desde el CSS con `@plugin`, y la API de plugins de v3 sigue funcionando:

```css
@plugin "@tailwindcss/typography";
@plugin "./tailwind/legacy-plugin.js";
```

Mi criterio: si el plugin solo declara CSS, pasalo a `@utility`; queda en el mismo archivo que el tema y lo entiende cualquiera que sepa CSS. `@plugin` solo cuando hay lógica que CSS no expresa, como generar decenas de utilidades a partir de datos.

Comprobación: poné `<pre class="tab-4 md:tab-github">` y `<div class="scrollbar-hidden overflow-x-auto">`. En el CSS compilado tienen que aparecer `.tab-4` con `tab-size: var(--tab-size-4)` y la versión `md:` dentro de `@media (width >= 48rem)`.""",
            },
            {
                "role": "user",
                "content": "Lo hice, pero tenía otras clases propias dentro de `@layer utilities { .content-auto { content-visibility: auto; } }` como en v3, y `md:content-auto` no hace nada. ¿Por qué?",
            },
            {
                "role": "assistant",
                "content": """Porque en v4 `@layer utilities` es una capa de cascada nativa, y Tailwind ya no la intercepta. En v3, todo lo que ponías dentro se registraba como utilidad y recibía variantes; en v4 esa regla se emite tal cual, sin variantes. Por eso `content-auto` sola funciona y `md:content-auto` no genera nada: para Tailwind no existe.

El arreglo es mecánico: cada clase de `@layer utilities` pasa a `@utility`, sin el punto:

```css
/* antes (v3) */
@layer utilities {
  .content-auto {
    content-visibility: auto;
  }
}

/* después (v4) */
@utility content-auto {
  content-visibility: auto;
}
```

Lo mismo con `@layer components`: si querés que una clase de componente acepte variantes, también va con `@utility`. Las reglas que no necesitan variantes (estilos de `h1`, de `a`, un reset) se quedan en `@layer base` sin problema.

La herramienta oficial (`npx @tailwindcss/upgrade`) hace esta conversión sola; si migraste a mano, buscá lo que quedó con `grep -rn "@layer utilities" src/`.

Una restricción: `@utility` declara una clase por su nombre, no acepta un selector compuesto como nombre. Si tu utilidad de v3 era `.toolbar > svg`, eso no es una utilidad; usá la variante de hijos en el HTML (`*:size-4` en la barra) o dejá la regla como CSS normal.

Comprobación: con `<section class="md:content-auto">`, el CSS compilado tiene que contener la regla dentro de `@media (width >= 48rem)`; antes del cambio, no aparecía.""",
            },
        ]
    },
    # 23) Tailwind v4: @source en un monorepo (Colombia, ustedes, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos un monorepo con pnpm: `apps/web` (Next.js) y `packages/ui` con los componentes compartidos, y Tailwind v4 instalado en `apps/web`. Las clases que solo aparecen en `packages/ui` no se generan; las que también usamos en la app, sí. ¿Qué nos falta?",
            },
            {
                "role": "assistant",
                "content": """Les falta decirle a Tailwind que escanee `packages/ui`. La detección automática de v4 parte de una **ruta base** (por defecto, el directorio desde el que corre el build, aquí `apps/web`) y solo recorre lo que hay debajo, ignorando `node_modules` y lo que esté en `.gitignore`. `packages/ui` queda fuera de esa raíz, y la copia enlazada en `apps/web/node_modules/@acme/ui` está en `node_modules`. Resultado: las clases de la librería solo se generan cuando, por casualidad, también aparecen en la app. Es exactamente el patrón que describen.

Arreglo: registrar la fuente con `@source`, con una ruta **relativa al archivo CSS**:

```css
/* apps/web/app/globals.css */
@import "tailwindcss";

@source "../../../packages/ui/src";
```

Desde `apps/web/app/` hay que subir tres niveles para llegar a la raíz del monorepo. Es el error más común aquí: escribir la ruta relativa al `package.json` en lugar de al CSS.

Decisiones que conviene tomar a propósito:

- **Escanear `src` o `dist`.** Si la app consume el código fuente de la librería (lo habitual en un monorepo, con `transpilePackages` en Next), escaneen `src`. Si la librería se publica compilada y la app importa `dist`, escaneen `dist`: lo que importa es dónde están escritas las clases que llegan al navegador.
- **No compilen Tailwind dentro de `packages/ui`.** Si la librería genera y exporta su propio CSS, terminan con dos copias de las utilidades y conflictos de orden entre ellas. La librería solo escribe clases; la app es la única que compila.
- **No muevan la ruta base a la raíz** con `@import "tailwindcss" source("../../..");` salvo que de verdad quieran escanear todo el monorepo: también recorrería `apps/admin`, `apps/docs` y lo que haya, y la web generaría clases que nunca usa.

Desde v4.1 también pueden excluir carpetas que no deben aportar clases, como los datos de prueba dentro de la librería:

```css
@source "../../../packages/ui/src";
@source not "../../../packages/ui/src/__fixtures__";
```

Comprobación: elijan una clase que solo use la librería, hagan `pnpm --filter web build` y búsquenla en el CSS generado. Antes del cambio no aparece; después, sí. Si quitan la línea `@source` y vuelve a desaparecer, la causa queda confirmada.""",
            },
        ]
    },
    # 24) Tailwind v4: variantes de estado (peer, group, has, open, data, aria) sin useState (España)
    {
        "messages": [
            {
                "role": "user",
                "content": "Con Tailwind, ¿cómo estilo cosas que dependen del estado de OTRO elemento? Por ejemplo: la etiqueta flotante de un input, la flecha de un acordeón que gira al abrirse y una tarjeta de plan que se resalta cuando su radio está marcado. Ahora mismo lo hago todo con useState y clases condicionales.",
            },
            {
                "role": "assistant",
                "content": """Los tres casos se resuelven solo con CSS, porque el navegador ya conoce esos estados (`:placeholder-shown`, `[open]`, `:checked`). Tailwind los expone como variantes que miran a otro elemento: `peer-*` (un hermano anterior), `group-*` (un ancestro) y `has-*` (un descendiente). Quitas el `useState` y el estado deja de poder desincronizarse con el DOM.

**1. Etiqueta flotante con `peer`:**

```html
<div class="relative">
  <input
    id="email"
    type="email"
    placeholder=" "
    class="peer w-full rounded-md border border-gray-300 px-3 pt-5 pb-2 outline-hidden focus:border-blue-600 focus:ring-2 focus:ring-blue-600/40 user-invalid:border-red-700"
  />
  <label
    for="email"
    class="pointer-events-none absolute left-3 top-1.5 text-xs text-gray-600 transition-all peer-placeholder-shown:top-3.5 peer-placeholder-shown:text-base peer-focus:top-1.5 peer-focus:text-xs"
  >
    Correo electrónico
  </label>
</div>
```

- `peer` funciona con el combinador de hermano siguiente (`~`), así que el `input` tiene que ir **antes** del `label` en el HTML. Visualmente el label queda arriba igual, por el `absolute`.
- `placeholder=" "` (un espacio) es el truco: `:placeholder-shown` solo existe si hay placeholder, y así se cumple mientras el campo está vacío.
- `outline-hidden` y no `outline-none`: deja un contorno transparente que reaparece en el modo de alto contraste de Windows, donde el `ring` (una sombra) no se ve.

**2. Acordeón con `<details>` y `group-open`:**

```html
<details class="group border-b py-3">
  <summary class="flex cursor-pointer list-none items-center justify-between font-medium [&::-webkit-details-marker]:hidden">
    ¿Hacéis envíos a Canarias?
    <svg class="size-4 transition-transform group-open:rotate-180" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path d="M5 7.5 10 12.5 15 7.5z" />
    </svg>
  </summary>
  <p class="mt-2 text-gray-600">Sí, con un plazo de 3 a 5 días laborables.</p>
</details>
```

`<details>` ya gestiona el estado abierto, el teclado (Enter y Espacio en el `summary`) y lo que anuncia el lector de pantalla. Cero JavaScript.

**3. Tarjeta de plan con `has-checked`:**

```html
<fieldset class="grid gap-3">
  <legend class="mb-2 font-semibold">Elige un plan</legend>
  <label class="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-300 p-4 has-checked:border-blue-600 has-checked:bg-blue-50 has-focus-visible:outline-2 has-focus-visible:outline-blue-700">
    <input type="radio" name="plan" value="basic" class="size-4 accent-blue-600" />
    <span>Básico, 5 € al mes</span>
  </label>
  <label class="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-300 p-4 has-checked:border-blue-600 has-checked:bg-blue-50 has-focus-visible:outline-2 has-focus-visible:outline-blue-700">
    <input type="radio" name="plan" value="pro" class="size-4 accent-blue-600" />
    <span>Pro, 12 € al mes</span>
  </label>
</fieldset>
```

`has-checked:` compila a `:has(*:checked)`. El `has-focus-visible:` dibuja el foco en toda la tarjeta cuando llegas al radio con el teclado.

**Cuando el estado sí vive en JavaScript** (componentes de Radix o React Aria), esas librerías lo publican en atributos, y también hay variantes para ellos: `aria-expanded:bg-gray-100`, `data-[state=open]:bg-gray-100`, o `data-active:font-semibold` para un atributo booleano `data-active`. Sigues sin necesitar clases condicionales.

Y si anidas grupos, nómbralos: `group/card` en el padre y `group-hover/card:underline` en el hijo, para que el hover de la tarjeta interior no active el de la exterior.

Un cambio de v4 que confunde: `hover:` solo se aplica en dispositivos que tienen hover de verdad (`@media (hover: hover)`), así que en móvil ya no se queda «pegado» tras tocar. Es intencionado.

Comprobación: recorre el formulario solo con el teclado. El label flota al entrar en el campo y vuelve si sales sin escribir; Enter en el `summary` abre el acordeón y gira la flecha; las flechas del teclado cambian de plan y la tarjeta resaltada sigue al radio marcado.""",
            },
        ]
    },
    # 25) Migración a Tailwind v4 en Next 15: error del plugin de PostCSS (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Actualicé `tailwindcss` a la 4 en un proyecto Next 15 que venía de v3 y al arrancar `next dev` me sale esto:

```
Error: It looks like you're trying to use `tailwindcss` directly as a PostCSS plugin. The PostCSS plugin has moved to a separate package, so to continue using Tailwind CSS with PostCSS you'll need to install `@tailwindcss/postcss` and update your PostCSS configuration.
```

Mi `postcss.config.js` tiene `tailwindcss: {}` y `autoprefixer: {}`, y el `globals.css` empieza con los tres `@tailwind`.""",
            },
            {
                "role": "assistant",
                "content": """El mensaje es literal: en v4 el plugin de PostCSS ya no vive en el paquete `tailwindcss` sino en `@tailwindcss/postcss`. Pero si solo cambias eso, arrancará y verás la web rota en detalles, porque subir de versión mayor trae más cambios. Hazlo en este orden.

**1. Prueba primero la herramienta oficial**, en una rama limpia (necesita Node 20 o superior):

```bash
git switch -c upgrade-tailwind-v4
npx @tailwindcss/upgrade
git diff --stat
```

Actualiza dependencias, reescribe la configuración de PostCSS, convierte `tailwind.config.js` a `@theme` en el CSS, sustituye las directivas `@tailwind` y renombra en las plantillas las clases que cambiaron de nombre. Revisa el diff: es grande, pero mecánico.

**2. Si prefieres hacerlo a mano**, el mínimo para que arranque:

```bash
npm uninstall autoprefixer
npm install tailwindcss@latest @tailwindcss/postcss
```

```js
// postcss.config.mjs (borra el postcss.config.js antiguo)
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
```

```css
/* app/globals.css: sustituye las tres directivas @tailwind */
@import "tailwindcss";
```

`autoprefixer` sobra: v4 ya añade los prefijos que hacen falta. Si tenías un `tailwind.config.js` con tema propio, cárgalo de momento con `@config "../tailwind.config.js";` debajo del `@import` y migra a `@theme` cuando todo funcione.

**3. Los cambios visuales que vas a notar.** La herramienta corrige los renombrados, no las decisiones de diseño:

| v3 | v4 | Efecto |
|---|---|---|
| `border` gris (`gray-200`) por defecto | `currentColor` | bordes oscuros donde no indicabas color |
| `ring` = 3 px azul | `ring` = 1 px `currentColor` | anillos de foco más finos; usa `ring-3` |
| `shadow-sm` / `shadow` | `shadow-xs` / `shadow-sm` | escala desplazada un paso |
| `rounded-sm` / `rounded` | `rounded-xs` / `rounded-sm` | ídem |
| `outline-none` | `outline-hidden` | `outline-none` ahora es `outline-style: none` de verdad |
| placeholder `gray-400` | color del texto al 50 % | placeholders más oscuros |
| botones con `cursor: pointer` | `cursor: default` | como el navegador |
| `hover:` siempre | solo en dispositivos con hover | en móvil ya no se queda pegado |
| `bg-[--brand]` | `bg-(--brand)` | nueva sintaxis para variables |

Para los bordes, si no quieres revisar cada `border` ahora, la guía de actualización propone este puente:

```css
@layer base {
  *,
  ::after,
  ::before,
  ::backdrop,
  ::file-selector-button {
    border-color: var(--color-gray-200, currentColor);
  }
}
```

**4. Navegadores.** v4 exige Safari 16.4+, Chrome 111+ y Firefox 128+, porque se apoya en `@property`, `color-mix()` y capas de cascada. Si tu analítica muestra tráfico relevante de navegadores más antiguos, quédate en v3.4 hasta que baje.

Comprobación: `next dev` arranca sin el error; `grep -rnE "bg-opacity-|text-opacity-|flex-shrink-|flex-grow-|overflow-ellipsis" app components` debe salir vacío (son utilidades eliminadas), y las páginas principales deben coincidir con capturas tomadas antes de la actualización.""",
            },
        ]
    },
    # 26) Accesibilidad: contraste, foco visible y errores solo por color (system variante, revisión)
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un revisor de accesibilidad estricto. Señala cada problema con el criterio WCAG que incumple, en orden de gravedad, y da el arreglo.",
            },
            {
                "role": "user",
                "content": """Revisa el CSS base de nuestra web antes de la auditoría externa:

```css
body { color: #333; background: #fff; }
.text-muted { color: #999; }
.btn-primary { background: #3b82f6; color: #fff; }
*:focus { outline: none; }
.field--error input { border-color: red; }
```""",
            },
            {
                "role": "assistant",
                "content": """Cuatro de las cinco reglas incumplen WCAG 2.2 nivel AA. En orden de gravedad:

**1. `*:focus { outline: none; }` incumple 2.4.7 (Foco visible).** Es lo más grave: quien navega con teclado no sabe dónde está. Elimina la regla y define un foco propio con `:focus-visible`, que solo se muestra cuando el foco llega por teclado y no al hacer clic con el ratón, que es lo que el diseño quería evitar al quitarlo:

```css
:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
```

Usa `outline` y no `box-shadow` para el anillo: en el modo de colores forzados de Windows las sombras desaparecen y el contorno se mantiene. El indicador necesita además 3:1 de contraste con lo que lo rodea (1.4.11), y no puede quedar tapado por una cabecera fija (2.4.11, nuevo en 2.2): `html { scroll-padding-top: 5rem; }`, con la altura de tu cabecera.

**2. `.text-muted`, #999 sobre blanco: 2,85:1. Incumple 1.4.3 (Contraste mínimo)**, que exige 4,5:1 para texto normal y 3:1 para texto grande (24 px, o 18,66 px en negrita). `#767676` es el gris más claro que pasa sobre blanco (4,54:1).

**3. `.btn-primary`, blanco sobre #3b82f6: 3,68:1. Incumple 1.4.3** salvo que el texto del botón sea grande, y no lo es. `#2563eb` da 5,17:1 con el mismo tono.

**4. `.field--error` comunica el error solo con color. Incumple 1.4.1 (Uso del color) y 3.3.1 (Identificación de errores).** Una persona daltónica no distingue el borde rojo, y un lector de pantalla no lo anuncia. Además, `red` puro sobre blanco da 4:1, insuficiente si lo usas para texto. El error necesita texto asociado al campo:

```html
<div class="field field--error">
  <label for="email">Correo electrónico</label>
  <input id="email" type="email" aria-invalid="true" aria-describedby="email-error">
  <p id="email-error" class="field__error">Falta la @. Escribe un correo como nombre@dominio.com</p>
</div>
```

`aria-describedby` hace que el lector lea el mensaje al llegar al campo, y `aria-invalid` lo anuncia como no válido. El texto dice qué falta y cómo arreglarlo, no solo «campo inválido».

**5. `body`, #333 sobre blanco: 12,6:1. Correcto.**

Todo junto, con los valores en tokens para que nadie vuelva a escoger un gris a ojo:

```css
:root {
  --color-text: #333;          /* 12,6:1 sobre blanco */
  --color-text-muted: #767676; /* 4,54:1 */
  --color-primary: #2563eb;    /* 5,17:1 con texto blanco */
  --color-danger: #b91c1c;     /* 6,47:1 sobre blanco */
  --color-focus: #1d4ed8;      /* 6,70:1 sobre blanco */
}

body { color: var(--color-text); background: #fff; }
.text-muted { color: var(--color-text-muted); }
.btn-primary { background: var(--color-primary); color: #fff; }
.field--error input { border-color: var(--color-danger); border-width: 2px; }
.field__error { color: var(--color-danger); }

:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
```

Cómo salen los ratios: con la fórmula de WCAG, `(L1 + 0,05) / (L2 + 0,05)` sobre la luminancia relativa. #999 tiene luminancia 0,318, así que contra el blanco (1,0) da 1,05 / 0,368 = 2,85. Contrástalos con el selector de color de Chrome DevTools, que muestra el ratio y marca AA y AAA.

Antes de la auditoría, pasa axe DevTools o Lighthouse por cada plantilla (detectan contraste y nombres accesibles que faltan) y recorre la web solo con Tab, Shift+Tab, Enter y Espacio. Lo que las herramientas automáticas no ven, el orden del foco y las trampas de teclado, aparece en esos cinco minutos.""",
            },
        ]
    },
    # 27) Semántica antes que ARIA: tarjeta clicable con botón dentro (México, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""El auditor de accesibilidad nos marcó esta tarjeta de producto, pero no entiendo qué le ve: ya le pusimos roles ARIA.

```tsx
<div className="card" onClick={() => navigate(`/productos/${p.id}`)}>
  <img src={p.imageUrl} />
  <div className="card-title" role="heading">{p.name}</div>
  <span>{p.price}</span>
  <div
    className="btn"
    role="button"
    aria-label="Añadir al carrito"
    onClick={(e) => { e.stopPropagation(); addToCart(p.id); }}
  >
    <CartIcon /> Añadir
  </div>
</div>
```""",
            },
            {
                "role": "assistant",
                "content": r"""El problema es justo ese: se usó ARIA para parchar elementos que no son lo que dicen ser. La primera regla de ARIA es no usarla si existe un elemento HTML nativo que ya hace lo que necesitas. Un `role="button"` solo cambia lo que **anuncia** el lector de pantalla; no da foco, ni teclado, ni comportamiento.

Lo que falla, de más a menos grave:

1. **El «botón» no se puede usar con teclado.** Un `<div>` no recibe foco con Tab ni responde a Enter o Espacio, así que quien no usa ratón no puede añadir al carrito. Un `<button>` trae todo eso de serie.
2. **La tarjeta navega con `onClick` en un `<div>`.** Tampoco es enfocable, y además no es un enlace: no se puede abrir en otra pestaña, el clic central no hace nada, el lector no la anuncia como enlace y los buscadores no siguen la URL. Navegar es trabajo de `<a href>`.
3. **Hay un control interactivo dentro de otro.** Aunque convirtieras la tarjeta en `<a>`, meter un `<button>` dentro de un enlace es HTML inválido, y los lectores lo anuncian de forma impredecible.
4. **`role="heading"` sin `aria-level`** se anuncia como nivel 2 por defecto, encaje o no en la jerarquía de la página. `<h3>` lo resuelve sin ARIA.
5. **La imagen no tiene `alt`.** Algunos lectores leen entonces el nombre del archivo.

La versión corregida usa el patrón de **enlace estirado**: el título es el enlace, y un pseudoelemento suyo cubre toda la tarjeta, así que un clic en cualquier parte navega; el botón queda por encima y funciona por separado.

```tsx
import { useState } from "react";
import { Link } from "react-router";
import { ShoppingCart } from "lucide-react";

type Product = { id: string; name: string; price: string; imageUrl: string };

type ProductCardProps = {
  product: Product;
  onAddToCart: (productId: string) => Promise<void>;
};

export function ProductCard({ product, onAddToCart }: ProductCardProps) {
  const [statusMessage, setStatusMessage] = useState("");

  async function handleAdd() {
    try {
      await onAddToCart(product.id);
      setStatusMessage(`${product.name} se añadió al carrito`);
    } catch {
      setStatusMessage(`No se pudo añadir ${product.name}. Inténtalo de nuevo.`);
    }
  }

  return (
    <article className="relative rounded-lg border p-4 hover:shadow-md has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-blue-700">
      {/* alt vacío: la imagen es decorativa, el nombre ya está en el enlace */}
      <img src={product.imageUrl} alt="" className="aspect-square w-full rounded-md object-cover" />
      <h3 className="mt-2 font-semibold">
        <Link to={`/productos/${product.id}`} className="outline-hidden after:absolute after:inset-0">
          {product.name}
        </Link>
      </h3>
      <p>{product.price}</p>
      <button
        type="button"
        onClick={handleAdd}
        className="relative z-10 mt-3 inline-flex items-center gap-2 rounded-md bg-blue-700 px-3 py-2 text-white"
      >
        <ShoppingCart aria-hidden="true" className="size-4" />
        Añadir al carrito
      </button>
      {/* role="status" anuncia el resultado sin mover el foco */}
      <p role="status" className="sr-only">
        {statusMessage}
      </p>
    </article>
  );
}
```

Qué resuelve cada decisión:

- **El texto visible del botón es su nombre accesible.** Sobra el `aria-label`; además, cuando no coincide con lo que se ve («Añadir» frente a «Añadir al carrito»), quien usa control por voz dice «clic en Añadir» y puede no funcionarle (WCAG 2.5.3).
- **El foco del enlace se dibuja en toda la tarjeta** con `has-[a:focus-visible]:`, porque el contorno del enlace solo rodearía el título.
- **La ARIA que sí aporta:** `aria-hidden` en el icono, para que no se lea dos veces, y `role="status"` para anunciar el resultado, algo que no tiene equivalente en HTML.

Comprobación: navega solo con Tab. Cada tarjeta debe ofrecer dos paradas (el enlace, con la tarjeta resaltada, y el botón); Enter en la primera navega y Espacio en el botón añade el producto. Con VoiceOver o NVDA debe oírse el nombre del producto como enlace dentro de un encabezado de nivel 3 y, tras añadir, el mensaje de estado.""",
            },
        ]
    },
    # 28) CSS Modules frente a CSS-in-JS con Server Components (inglés, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "We're starting a Next.js 15 App Router project. Half the team wants styled-components, the other half CSS Modules. What actually matters now that Server Components are the default?",
            },
            {
                "role": "assistant",
                "content": r"""What matters is **where the styles are produced**. A Server Component never ships JavaScript to the browser, so a styling solution that needs JavaScript at render time cannot style it. That single fact decides most of the debate.

**Runtime CSS-in-JS (styled-components, Emotion)** generates CSS while React renders, using React context to collect it. Server Components have no context and no client runtime, so:

- Every file that defines or renders a styled component needs `"use client"`. In practice the tree drifts to the client and you lose the main benefit of the App Router.
- SSR needs a style registry (`useServerInsertedHTML`) wired into the root layout to avoid a flash of unstyled content.
- Styles are serialized and injected at runtime, which costs CPU on every render, most visibly on low-end phones.
- styled-components announced maintenance mode in 2025: bug fixes, no new direction. A poor bet for a codebase you start today.

**Zero-runtime options** produce static `.css` files at build time, so they work in Server and Client Components alike:

| Option | Authoring | Typed | Notes |
|---|---|---|---|
| CSS Modules | plain CSS, scoped class names | via an editor plugin | built into Next, zero setup |
| Tailwind CSS | utility classes | IntelliSense | offered by `create-next-app` |
| vanilla-extract | TypeScript (`.css.ts`) | yes | closest to the styled-components experience |
| Panda CSS / StyleX | style objects in TS | yes | compile-time atomic CSS |

My recommendation: **CSS Modules** if the team wants to keep writing CSS, Tailwind if it is open to utilities. If the styled-components half mostly wants typed styles and co-location, vanilla-extract gives them that without the runtime.

CSS Modules for a component with variants, fully server-compatible:

```css
/* components/button.module.css */
.button {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid transparent;
  border-radius: 0.375rem;
  font-weight: 500;
}

.button[data-variant="primary"] {
  background: var(--color-primary);
  color: white;
}

.button[data-variant="secondary"] {
  background: white;
  border-color: var(--color-border);
  color: var(--color-text);
}
```

```tsx
// components/button.tsx (no "use client" needed)
import type { ComponentProps } from "react";
import styles from "./button.module.css";

type ButtonProps = ComponentProps<"button"> & { variant?: "primary" | "secondary" };

export function Button({ variant = "primary", className, type = "button", ...props }: ButtonProps) {
  const classes = className ? `${styles.button} ${className}` : styles.button;
  return <button type={type} data-variant={variant} className={classes} {...props} />;
}
```

Variants as `data-*` attributes instead of extra classes keep selectors readable, make the state visible in DevTools, and avoid string-building logic.

To settle it with evidence: build one route with ten styled components and the same route with CSS Modules, run `next build`, and compare the "First Load JS" column for both routes. The runtime library and the forced client boundary show up right there.""",
            },
            {
                "role": "user",
                "content": "OK, but the styled-components folks have a point about dynamic styles: a progress bar width, a user-picked accent color, props-driven stuff. How do you do that with CSS Modules?",
            },
            {
                "role": "assistant",
                "content": r"""With CSS custom properties. The stylesheet stays static and declares *how* a value is used; the component passes the value through `style`. That covers nearly every case where styled-components interpolate props.

```css
/* components/progress.module.css */
.track {
  height: 0.5rem;
  border-radius: 999px;
  background: var(--color-border);
  overflow: hidden;
}

.bar {
  height: 100%;
  width: var(--progress, 0%);
  background: var(--accent, var(--color-primary));
  transition: width 300ms ease-out;
}
```

```tsx
// components/progress.tsx
import type { CSSProperties } from "react";
import styles from "./progress.module.css";

type ProgressProps = { value: number; label: string; accentColor?: string };

export function Progress({ value, label, accentColor }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const barStyle = {
    "--progress": `${clamped}%`,
    ...(accentColor ? { "--accent": accentColor } : {}),
  } as CSSProperties;

  return (
    <div
      className={styles.track}
      role="progressbar"
      aria-label={label}
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={styles.bar} style={barStyle} />
    </div>
  );
}
```

Why this beats interpolation in CSS-in-JS:

- **No new CSS per value.** styled-components generates a class for every distinct value of an interpolated prop; a progress bar moving from 0 to 100 can create a hundred rules. Here there is one rule, and only the variable changes.
- **It still renders on the server.** Nothing here needs client JavaScript; if the value comes from the database, the server sends the final HTML.
- **Defaults are explicit.** `var(--accent, var(--color-primary))` documents the fallback exactly where it applies.

Themes (light/dark, white-label brands) are the same idea at the root: tokens as custom properties on `:root`, overridden under `[data-theme="dark"]` or a brand attribute. No `ThemeProvider` and no context, so it works in Server Components.

What you genuinely lose is computing CSS with arbitrary JS at render time, such as darkening a color with a JS color library. CSS now covers most of that with `color-mix(in oklch, var(--accent), black 20%)`, and anything left can be computed in TypeScript and passed in as a variable.

Verification: render `<Progress value={42} label="Upload" />` from a Server Component page. The HTML source must contain `style="--progress:42%"`, and with JavaScript disabled the bar must still be 42 % wide.""",
            },
        ]
    },
    # 29) z-index que no funciona: contextos de apilamiento, <dialog> y recorte por overflow (SISTEMA, multiturno)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo un modal con `position: fixed; inset: 0; z-index: 9999` y aun así queda DEBAJO del header sticky, que tiene `z-index: 10`. El modal se renderiza dentro de la tarjeta de producto que lo abre. ¿Cómo puede perder 9999 contra 10?",
            },
            {
                "role": "assistant",
                "content": r"""Porque `z-index` no es global: solo compara elementos dentro del mismo **contexto de apilamiento**. Tu 9999 compite dentro de la tarjeta (o de algún ancestro suyo); la tarjeta entera compite contra el header con su propio nivel, que probablemente es `auto` o 0. Un 9999 dentro de algo que vale 0 sigue valiendo 0 frente al 10 del header.

**Hipótesis, por probabilidad.** Algún ancestro del modal crea un contexto de apilamiento. Lo crean, entre otros:

- `transform`, `filter`, `perspective` o `clip-path` distintos de `none`. Sospechoso número uno: el típico `.card:hover { transform: translateY(-2px); }`, o una librería de animaciones que deja un `transform` aplicado.
- `opacity` menor que 1 (animaciones de aparición).
- `will-change: transform` u `opacity`.
- `position` distinta de `static` con `z-index` distinto de `auto`, o un hijo de flex o grid con `z-index`.
- `isolation: isolate`, `contain: paint`, `position: fixed` o `sticky`.

Con `transform` hay un segundo síntoma que delata la causa: un `position: fixed` dentro de un ancestro transformado deja de ser relativo a la ventana y pasa a serlo al ancestro. Si tu modal tampoco cubre toda la pantalla, ya sabes cuál es.

**Evidencia en un minuto.** Selecciona el modal en el panel *Elements* y ejecuta esto en la consola; lista los ancestros que crean contexto y por qué:

```js
function stackingContextAncestors(element) {
  const found = [];
  for (let node = element.parentElement; node; node = node.parentElement) {
    const style = getComputedStyle(node);
    const parentDisplay = node.parentElement ? getComputedStyle(node.parentElement).display : "";
    const isFlexOrGridItem = /flex|grid/.test(parentDisplay);
    const reasons = [];
    if (style.zIndex !== "auto" && (style.position !== "static" || isFlexOrGridItem)) reasons.push(`z-index ${style.zIndex}`);
    if (style.position === "fixed" || style.position === "sticky") reasons.push(style.position);
    if (Number(style.opacity) < 1) reasons.push(`opacity ${style.opacity}`);
    if (style.transform !== "none") reasons.push("transform");
    if (style.filter !== "none") reasons.push("filter");
    if (style.isolation === "isolate") reasons.push("isolation");
    if (/transform|opacity/.test(style.willChange)) reasons.push(`will-change: ${style.willChange}`);
    if (reasons.length > 0) found.push({ element: node, reasons: reasons.join(", ") });
  }
  return found;
}

console.table(stackingContextAncestors($0));
```

`$0` es el elemento seleccionado en *Elements*. La primera fila de la tabla es el culpable.

**El arreglo no es otro z-index,** sino sacar el modal de la tarjeta. Un `<dialog>` abierto con `showModal()` va a la *top layer*: se pinta por encima de todo el documento, ignora los contextos de apilamiento y los `transform` de sus ancestros, y trae de serie el foco atrapado, el cierre con Escape y el fondo `::backdrop`.

```tsx
import { useEffect, useId, useRef, type ReactNode } from "react";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

export function Modal({ open, onClose, title, children }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  // onClose también se dispara al cerrar con Escape: el estado del padre no se desincroniza.
  return (
    <dialog ref={dialogRef} onClose={onClose} aria-labelledby={titleId} className="modal">
      <h2 id={titleId}>{title}</h2>
      {children}
      <button type="button" onClick={onClose}>
        Cerrar
      </button>
    </dialog>
  );
}
```

```css
.modal::backdrop {
  background: rgb(0 0 0 / 0.5);
}
```

`useId` en lugar de un id fijo: con dos modales en la página, un `id="modal-title"` duplicado haría que ambos se anunciaran con el título del primero.

Si no puedes usar `<dialog>`, la alternativa es un portal (`createPortal(modal, document.body)`): el modal pasa a ser hijo del `body`, fuera de la tarjeta, y su `z-index` vuelve a competir en el contexto raíz.

Comprobación: el modal debe cubrir toda la ventana, header incluido, aunque la tarjeta siga teniendo su `transform`. En Chrome, el panel *Elements* muestra el `<dialog>` abierto bajo el nodo `#top-layer`.""",
            },
            {
                "role": "user",
                "content": "Lo pasé a `<dialog>` y perfecto. Pero ahora tengo un menú desplegable dentro de una tarjeta con `overflow: hidden` (lo usamos para redondear la imagen) y el menú se corta por el borde. Le subí el z-index y nada.",
            },
            {
                "role": "assistant",
                "content": r"""Es otro problema con el mismo síntoma: aquí no hay apilamiento sino **recorte**. `overflow: hidden` recorta a los descendientes cuyo bloque contenedor es la tarjeta o algo dentro de ella, y ningún `z-index` sale de un recorte: el `z-index` decide quién se pinta encima, no qué parte se pinta.

Tres salidas, de menor a mayor cambio:

**1. Quitar el recorte donde no hace falta.** Si el `overflow: hidden` solo está para que la imagen respete las esquinas redondeadas, redondea la imagen y deja la tarjeta sin recorte:

```css
.card {
  border-radius: 0.75rem;
  /* sin overflow: hidden */
}

.card > img:first-child {
  border-start-start-radius: inherit;
  border-start-end-radius: inherit;
}
```

Resuelve la mitad de los casos y no añade nada.

**2. Llevar el menú a la top layer con la API Popover**, igual que el diálogo. Un elemento `popover` abierto escapa de cualquier recorte y de cualquier contexto de apilamiento, y se cierra solo con un clic fuera o con Escape:

```html
<button type="button" id="card-menu-trigger" popovertarget="card-menu">Opciones</button>
<div id="card-menu" popover class="card-menu">
  <button type="button">Editar</button>
  <button type="button">Duplicar</button>
  <button type="button">Eliminar</button>
</div>
```

Lo que el popover no hace es colocarse junto al botón: por defecto aparece centrado en la ventana. Para posicionarlo, Floating UI:

```ts
import { autoUpdate, computePosition, flip, offset, shift } from "@floating-ui/dom";

const trigger = document.getElementById("card-menu-trigger");
const menu = document.getElementById("card-menu");
let stopUpdating: (() => void) | null = null;

if (trigger && menu) {
  menu.addEventListener("toggle", (event) => {
    if ((event as ToggleEvent).newState === "open") {
      stopUpdating = autoUpdate(trigger, menu, () => {
        void computePosition(trigger, menu, {
          placement: "bottom-start",
          strategy: "fixed",
          middleware: [offset(4), flip(), shift({ padding: 8 })],
        }).then(({ x, y }) => {
          menu.style.left = `${x}px`;
          menu.style.top = `${y}px`;
        });
      });
    } else {
      stopUpdating?.();
      stopUpdating = null;
    }
  });
}
```

```css
.card-menu {
  position: fixed;
  inset: auto;      /* anula el inset: 0 del popover para que manden left y top */
  margin: 0;        /* anula el centrado por defecto */
}
```

`flip()` lo abre hacia arriba si no cabe debajo y `shift()` lo mantiene dentro de la ventana; `autoUpdate` lo recoloca al hacer scroll o redimensionar, y se detiene al cerrarse.

**3. Portal + Floating UI** si el menú es un componente de React complejo: el mismo cálculo, renderizando el menú en `document.body`. Las librerías de componentes accesibles (Radix, React Aria) lo hacen así y además resuelven la navegación con flechas.

Comprobación: abre el menú en una tarjeta pegada al borde inferior de la ventana: debe verse entero, abrirse hacia arriba y cerrarse con Escape y con un clic fuera.""",
            },
        ]
    },
    # 30) Scroll horizontal fantasma en móvil: localizar el culpable antes que overflow-x: hidden (Colombia)
    {
        "messages": [
            {
                "role": "user",
                "content": "En el celular la página se puede arrastrar hacia los lados y aparece una franja blanca a la derecha. No encontramos qué la causa. Un compañero dice que pongamos `overflow-x: hidden` en el body y listo. ¿Lo hacemos?",
            },
            {
                "role": "assistant",
                "content": """Todavía no. `overflow-x: hidden` en el `body` esconde el síntoma y deja al elemento culpable desbordado, y tiene efectos secundarios: convierte al contenedor en contenedor de scroll, lo que rompe los `position: sticky` de la cabecera, y Safari de iOS a veces lo ignora en el `body`. Primero encuentren al culpable; casi siempre es uno solo y se arregla con una línea.

**1. Localizarlo.** Peguen esto en la consola con la vista móvil activa:

```js
const viewportWidth = document.documentElement.clientWidth;
for (const element of document.querySelectorAll("body *")) {
  const { left, right } = element.getBoundingClientRect();
  if (right > viewportWidth + 1 || left < -1) {
    console.log(Math.round(right - viewportWidth), element);
  }
}
```

Lista todo lo que se sale por la derecha (o por la izquierda) y cuántos píxeles. Los ancestros de un culpable también aparecen; el que buscan es el más profundo de la lista. Alternativa visual: una regla temporal `* { outline: 1px solid red; }` en DevTools muestra las cajas que sobresalen.

**2. Las causas habituales**, por frecuencia:

| Culpable | Arreglo |
|---|---|
| `width: 100vw` | `width: 100%`; `100vw` incluye el ancho de la barra de scroll en escritorio |
| Ancho fijo (`width: 480px`) | `width: 100%; max-width: 480px` |
| URL o palabra larga sin espacios | `overflow-wrap: anywhere` en ese texto |
| Imagen, `iframe` o vídeo sin límite | `img, video, iframe { max-width: 100%; height: auto; }` |
| Hijo de flex o grid que no encoge | `min-width: 0`, o `minmax(0, 1fr)` en la pista |
| Animación de entrada con `translateX` (librerías tipo AOS) | animar en vertical, o recortar la sección (abajo) |
| Tabla ancha | envolverla en un `div` con `overflow-x: auto` |
| Márgenes negativos de una fila de rejilla heredada | compensarlos con padding en el contenedor |

**3. Si después todavía quieren una red de seguridad**, usen `clip` en lugar de `hidden`, y en la sección afectada, no en el `body`. Ejemplo con el caso más común, la animación que entra desde la derecha:

```css
/* El elemento empieza 100px a la derecha y, mientras tanto, ensancha la página */
.reveal-from-right {
  opacity: 0;
  transform: translateX(100px);
  transition: opacity 400ms, transform 400ms;
}

/* Arreglo: la sección recorta lo que sobresale durante la animación */
.feature-section {
  overflow-x: clip;   /* recorta como hidden, pero sin crear contenedor de scroll: sticky sigue funcionando */
}
```

`overflow: clip` tiene soporte en todos los navegadores actuales desde 2022 (Safari 16).

Comprobación: vuelvan a ejecutar el script y debe salir vacío. Prueben a 320 px de ancho en DevTools, el de los teléfonos más estrechos, y en un celular real arrastrando hacia los lados: la página no debe moverse en horizontal y la cabecera sticky debe seguir fija al hacer scroll.""",
            },
        ]
    },
]
