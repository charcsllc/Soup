"""Vue 3.5 (10 filas), Nuxt 3 (7), Svelte 5 + SvelteKit (8) y SolidJS (5, incluida una comparativa de modelos de reactividad)."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# ---------------------------------------------------------------------------
# 1-10 Vue 3.5: script setup, ref/reactive (multiturno), watch/computed, props/emits/defineModel,
#               composables, provide/inject, Pinia (multiturno), Vue Router, Teleport + slots (EN→ES), $attrs
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {"role": "system", "content": "Responde en español, con código TypeScript completo."},
            {
                "role": "user",
                "content": "Estoy empezando con Vue 3. ¿Me explicas cómo se escribe un componente con `<script setup>`? Un contador con un valor inicial que venga del padre y que avise al padre cuando cambie.",
            },
            {
                "role": "assistant",
                "content": r"""`<script setup>` es la forma estándar de escribir componentes en Vue 3: todo lo que declaras arriba (variables, funciones, imports) está disponible en la plantilla sin `return` ni `export default`.

```vue
<!-- Counter.vue -->
<script setup lang="ts">
import { ref, computed } from "vue";

// Props tipadas: lo que el padre nos pasa
const props = defineProps<{
  initial?: number;
  step?: number;
}>();

// Eventos tipados: lo que emitimos hacia el padre
const emit = defineEmits<{
  change: [value: number];
}>();

// Estado local: `ref` envuelve el valor; en el script se lee con `.value`, en la plantilla no
const count = ref(props.initial ?? 0);

// Valor derivado: se recalcula solo cuando cambia `count`
const isEven = computed(() => count.value % 2 === 0);

function increment() {
  count.value += props.step ?? 1;
  emit("change", count.value);
}
</script>

<template>
  <div>
    <p>Valor: {{ count }} ({{ isEven ? "par" : "impar" }})</p>
    <button type="button" @click="increment">+{{ step ?? 1 }}</button>
  </div>
</template>
```

Uso desde el padre:

```vue
<script setup lang="ts">
import { ref } from "vue";
import Counter from "./Counter.vue";

const last = ref<number | null>(null);
</script>

<template>
  <Counter :initial="10" :step="5" @change="(value) => (last = value)" />
  <p v-if="last !== null">Último valor recibido: {{ last }}</p>
</template>
```

Las piezas, una por una:

- **`defineProps<{...}>()`** declara las props a partir de un tipo: Vue genera la validación en tiempo de ejecución y TypeScript te avisa si el padre pasa algo mal. `?` marca las opcionales.
- **`defineEmits<{ change: [value: number] }>()`** tipa el evento y su carga. `emit("change", "texto")` no compila.
- **`ref(valor)`** crea estado reactivo. El `.value` en el script es lo que permite a Vue saber cuándo lees y escribes; en la plantilla se desenvuelve solo.
- **`computed`** cachea el resultado y solo lo recalcula si sus dependencias cambian; usa `computed` para derivar, no un `ref` que actualices a mano.
- **`:initial="10"`** con dos puntos pasa una expresión (número); sin ellos sería la cadena `"10"`. **`@change`** es la forma corta de `v-on:change`.

Un detalle para no tropezar: `count` se inicializa con `props.initial` **una vez**. Si el padre cambia `initial` después, el contador no lo sigue (sería un «estado derivado de una prop», que requiere `watch`). Para un contador es lo correcto: el valor inicial es solo eso, inicial.

Comprobación: pulsa el botón dos veces con `step=5` desde `initial=10`; la pantalla muestra 15 y luego 20, y el padre recibe `change` con 15 y 20.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Esto no se actualiza en la plantilla cuando cambio el nombre. ¿Por qué?

```vue
<script setup lang="ts">
import { reactive } from "vue";

const user = reactive({ name: "Ana", age: 30 });
const { name, age } = user;

function rename() {
  user.name = "Eva";
}
</script>

<template>
  <p>{{ name }} ({{ age }})</p>
  <button @click="rename">Renombrar</button>
</template>
```""",
            },
            {
                "role": "assistant",
                "content": r"""Al desestructurar `reactive`, **copias los valores** y pierdes la reactividad. `const { name } = user` es `const name = user.name`: en ese instante vale `"Ana"` y es una cadena normal, sin conexión con el objeto. `rename()` cambia `user.name`, pero la plantilla lee `name`, que sigue siendo `"Ana"`.

Dos arreglos, según qué prefieras:

**1. No desestructures: usa el objeto en la plantilla.**

```vue
<template>
  <p>{{ user.name }} ({{ user.age }})</p>
</template>
```

**2. Desestructura con `toRefs`, que convierte cada propiedad en un `ref` enlazado al objeto.**

```vue
<script setup lang="ts">
import { reactive, toRefs } from "vue";

const user = reactive({ name: "Ana", age: 30 });
const { name, age } = toRefs(user); // name.value === user.name, siempre

function rename() {
  user.name = "Eva"; // name.value también pasa a "Eva"
}
</script>
```

Este es el motivo por el que mucha gente usa `ref` para todo, incluso objetos: un `ref` se pasa, se devuelve desde funciones y se desestructura sin romperse, porque la reactividad está en la caja (`.value`), no en el objeto.

| | `ref` | `reactive` |
|---|---|---|
| Primitivos | sí | no (solo objetos) |
| Acceso en el script | `.value` | directo |
| Desestructurar | seguro (pasas el ref entero) | pierde reactividad (necesita `toRefs`) |
| Reasignar entero | `state.value = {...}` funciona | `state = {...}` rompe la conexión |
| Uso típico | casi todo | grupos de campos que siempre van juntos (un formulario) |

Regla práctica: `ref` por defecto; `reactive` cuando tienes un objeto que nunca reasignas y cuyas propiedades siempre usas a través de él.""",
            },
            {
                "role": "user",
                "content": "Vale. Otra cosa relacionada: tengo un `ref` con un array de 20.000 filas que viene de la API y la primera carga va lenta. ¿La reactividad tiene algo que ver?",
            },
            {
                "role": "assistant",
                "content": r"""Sí. `ref([...])` con un array de objetos hace la reactividad **profunda**: Vue envuelve el array y cada objeto en un Proxy, de forma perezosa pero con coste al recorrerlos (que es lo que hace la plantilla al pintar la tabla). Con 20.000 filas de varias propiedades son decenas de miles de proxies.

Si las filas **no se editan una a una**, sino que se sustituyen en bloque cuando llega otra respuesta, usa `shallowRef`: solo es reactivo el cambio de `.value`, no el interior.

```ts
import { shallowRef, triggerRef } from "vue";

type Row = { id: string; name: string; amount: number };

const rows = shallowRef<Row[]>([]);

async function load() {
  rows.value = await fetch("/api/rows").then((r) => r.json()); // reasignar sí dispara el render
}

function markPaid(id: string) {
  // Mutar un objeto interno NO es reactivo con shallowRef; produce un array nuevo
  rows.value = rows.value.map((r) => (r.id === id ? { ...r, amount: 0 } : r));
}
```

Si de verdad necesitas mutar dentro y avisar a mano, `triggerRef(rows)` fuerza la actualización, pero el patrón de «array nuevo» es más claro.

Cuándo usar qué:

| Datos | Herramienta |
|---|---|
| Pocos elementos, se editan campo a campo | `ref` (profundo) |
| Miles de elementos, se sustituyen en bloque | `shallowRef` |
| Datos de solo lectura que nunca cambian tras cargar | `markRaw(data)` antes de guardarlos, o `shallowRef` |
| Instancias de clases externas (mapa de Leaflet, editor) | `shallowRef` o `markRaw`: proxificarlas rompe sus internos |

Comprueba antes de cambiar: en Vue DevTools, pestaña Performance, graba la carga. Si el tiempo está en «render» y baja al pasar a `shallowRef`, era la reactividad; si está en la petición de red o en pintar 20.000 nodos DOM, el siguiente paso es paginar o virtualizar la lista (`vue-virtual-scroller` o `@tanstack/vue-virtual`), porque ningún `ref` hace que 20.000 filas en el DOM sean rápidas.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuándo uso `watch`, cuándo `watchEffect` y cuándo `computed`? Los tres «reaccionan a cambios» y acabo usando `watch` para todo.",
            },
            {
                "role": "assistant",
                "content": r"""La pregunta que los separa es: **¿quieres un valor o quieres un efecto?**

- `computed`: produce un **valor** derivado de otros. Síncrono, cacheado, sin efectos secundarios.
- `watch` / `watchEffect`: ejecutan un **efecto** (petición, log, escritura en localStorage) cuando algo cambia.

Si estás usando `watch` para rellenar un `ref` a partir de otros, es un `computed` mal escrito:

```ts
// Mal: dos fuentes de verdad, un render de retraso, y `total` empieza en 0 hasta que algo cambie
const total = ref(0);
watch(items, (list) => { total.value = list.reduce((s, i) => s + i.price, 0); });

// Bien: un valor derivado, siempre consistente
const total = computed(() => items.value.reduce((s, i) => s + i.price, 0));
```

Entre `watch` y `watchEffect`, la diferencia es **quién declara las dependencias**:

```ts
import { watch, watchEffect, onWatcherCleanup } from "vue";

// watch: tú dices QUÉ observar; recibes valor nuevo y anterior; es perezoso (no corre al inicio)
watch(userId, async (id, previousId) => {
  profile.value = await fetchProfile(id);
});

// watchEffect: observa todo lo que LEE dentro; corre inmediatamente y en cada cambio de esas lecturas
watchEffect(async () => {
  const controller = new AbortController();
  onWatcherCleanup(() => controller.abort()); // Vue 3.5: cancela la petición anterior al re-ejecutar
  profile.value = await fetchProfile(userId.value, { signal: controller.signal });
});
```

Cuándo cada uno:

| Quieres… | Usa |
|---|---|
| Un valor derivado | `computed` |
| Reaccionar a una fuente concreta, con acceso al valor anterior | `watch(fuente, cb)` |
| Reaccionar solo cuando cambia, no al montar | `watch` (por defecto perezoso) |
| Que corra al montar y siga a lo que lea | `watchEffect` |
| Observar varias fuentes | `watch([a, b], ([a, b]) => …)` |
| Observar una propiedad de un `reactive` | `watch(() => state.user.id, cb)` (getter; `watch(state.user.id)` observaría un número, no una fuente) |

Opciones de `watch` que resuelven los casos límite:

- `{ immediate: true }`: ejecuta el callback al crear el watcher con el valor actual.
- `{ deep: true }`: observa cambios dentro de un objeto/array; caro, úsalo solo si de verdad necesitas reaccionar a mutaciones internas.
- `{ once: true }` (3.4+): se ejecuta una vez y se detiene.
- `{ flush: "post" }`: ejecuta el callback después de que el DOM se haya actualizado, para medir elementos.

La trampa de `watchEffect`: las dependencias se registran **solo en la parte síncrona**. Todo lo que leas después del primer `await` no se observa. Por eso en el ejemplo `userId.value` se lee antes del `await`; si lo leyeras dentro de un `.then`, el watcher no se volvería a ejecutar al cambiar.

Y para `watch` con un `async` que puede llegar desordenado (cambias de usuario rápido y responde antes la petición antigua), el `onWatcherCleanup` de arriba es la solución: cada re-ejecución aborta la anterior.

Comprobación mental: si borras el `watch` y la pantalla queda igual salvo por un valor que ya no se calcula, era un `computed`. Si borras el `watch` y deja de pasar algo (una petición, un guardado), era un efecto de verdad.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Componente `TextField` reutilizable en Vue 3.5 con TypeScript: `v-model` del valor, props con valores por defecto (label, placeholder, tamaño), y un evento `blur` tipado. ¿Cómo queda con las APIs actuales? Veo ejemplos con `withDefaults` y otros sin él.",
            },
            {
                "role": "assistant",
                "content": r"""Con Vue 3.5 las tres cosas tienen una forma directa: `defineModel` para el `v-model`, **desestructuración reactiva de props** para los valores por defecto (sin `withDefaults`) y `defineEmits` con tipos.

```vue
<!-- TextField.vue -->
<script setup lang="ts">
import { useId } from "vue";

// v-model: crea la prop `modelValue` y el evento `update:modelValue` por ti
const model = defineModel<string>({ default: "" });

// Vue 3.5: los defaults van en la desestructuración y siguen siendo reactivos
const {
  label,
  placeholder = "",
  size = "md",
  disabled = false,
} = defineProps<{
  label: string;
  placeholder?: string;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
}>();

const emit = defineEmits<{
  blur: [event: FocusEvent];
}>();

const id = useId(); // 3.5: id estable y único, también en SSR
</script>

<template>
  <div :class="['field', `field--${size}`]">
    <label :for="id">{{ label }}</label>
    <input
      :id="id"
      v-model="model"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      @blur="emit('blur', $event)"
    />
  </div>
</template>
```

Uso:

```vue
<script setup lang="ts">
import { ref } from "vue";
import TextField from "./TextField.vue";

const email = ref("");
</script>

<template>
  <TextField v-model="email" label="Correo" size="lg" @blur="() => console.log('salió', email)" />
</template>
```

Por qué cada decisión:

- **`defineModel`** (3.4+) sustituye al par `props.modelValue` + `emit("update:modelValue")`. Devuelve un `ref` que puedes leer y escribir, y Vue sincroniza con el padre. Si necesitas varios modelos, `defineModel<string>("firstName")` crea `v-model:firstName`.
- **Desestructurar `defineProps` con defaults** es la API de 3.5 y hace innecesario `withDefaults`. El compilador reescribe cada acceso a `size` como `props.size`, así que **sigue siendo reactivo** aunque parezca una constante. `withDefaults` sigue funcionando; en código nuevo ya no hace falta.
- **Una limitación de la desestructuración**: si pasas una prop a `watch`, pásala como getter: `watch(() => disabled, …)`, no `watch(disabled, …)`. Vue avisa en desarrollo si lo olvidas.
- **`useId()`** enlaza `label` e `input` sin ids a mano, y genera el mismo id en servidor y cliente.
- **`emit("blur", $event)`** reexpone el evento nativo con su tipo, para que el padre reciba un `FocusEvent` y no `any`.

Dos cosas que no hace este componente a propósito: validar (eso va en el formulario, con el estado de error como otra prop `error?: string`) y aceptar atributos arbitrarios. Si quieres que `maxlength`, `autocomplete`, etc. pasen al `<input>` y no al `<div>` raíz, añade `defineOptions({ inheritAttrs: false })` y `v-bind="$attrs"` en el input.

Verificación: escribe en el campo y comprueba que `email` cambia en el padre; pasa `:disabled="true"` y confirma que el input se bloquea sin recargar (eso demuestra que el default desestructurado es reactivo).""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo la misma lógica de «cargar datos con estado de carga y error» repetida en cinco componentes. ¿Cómo la convierto en un composable de Vue bien hecho? Que acepte la URL como ref para que recargue sola cuando cambie.",
            },
            {
                "role": "assistant",
                "content": r"""Un composable es una función `useAlgo` que usa las APIs de composición y devuelve estado reactivo. La parte importante para tu caso es aceptar la entrada como **ref, getter o valor** y convertirla con `toValue`.

```ts
// composables/useFetch.ts
import { ref, shallowRef, computed, watchEffect, onWatcherCleanup, toValue, type MaybeRefOrGetter, type Ref } from "vue";

type Status = "idle" | "loading" | "success" | "error";

export function useFetch<T>(url: MaybeRefOrGetter<string | null>) {
  const data = shallowRef<T | null>(null);
  const error = ref<Error | null>(null);
  const status = ref<Status>("idle");

  async function execute(signal: AbortSignal) {
    const target = toValue(url);
    if (!target) {
      status.value = "idle";
      return;
    }
    status.value = "loading";
    error.value = null;
    try {
      const res = await fetch(target, { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data.value = (await res.json()) as T;
      status.value = "success";
    } catch (err) {
      if ((err as Error).name === "AbortError") return; // la petición se canceló por un cambio de URL
      error.value = err as Error;
      status.value = "error";
    }
  }

  watchEffect(() => {
    const controller = new AbortController();
    onWatcherCleanup(() => controller.abort());
    execute(controller.signal);
  });

  return {
    data: data as Readonly<Ref<T | null>>,
    error,
    status,
    isLoading: computed(() => status.value === "loading"),
    refresh: () => execute(new AbortController().signal),
  };
}
```

Uso en un componente:

```vue
<script setup lang="ts">
import { ref } from "vue";
import { useFetch } from "@/composables/useFetch";

type User = { id: number; name: string };

const userId = ref(1);
// Getter: el composable se vuelve a ejecutar cuando cambia userId
const { data: user, status, error, refresh } = useFetch<User>(() => `/api/users/${userId.value}`);
</script>

<template>
  <button @click="userId++">Siguiente</button>
  <p v-if="status === 'loading'">Cargando…</p>
  <p v-else-if="error" role="alert">{{ error.message }}</p>
  <p v-else-if="user">{{ user.name }}</p>
  <button @click="refresh">Recargar</button>
</template>
```

Decisiones:

- **`MaybeRefOrGetter<string | null>` + `toValue`**: el llamante pasa `"/api/x"`, un `ref` o una función. `toValue` resuelve cualquiera de los tres y, al leerse dentro de `watchEffect`, registra la dependencia: cambiar `userId` relanza la petición sin que el componente escriba ningún `watch`.
- **`onWatcherCleanup` + `AbortController`** (3.5): cada re-ejecución cancela la anterior. Sin esto, cambiar de usuario rápido puede pintar la respuesta antigua si llega la última. En versiones anteriores a 3.5 el equivalente es `watchEffect((onCleanup) => { onCleanup(() => controller.abort()) })`.
- **`status` como unión** en lugar de dos booleanos (`loading`, `hasError`): no puede haber estados imposibles como «cargando y con error».
- **`shallowRef` para `data`**: la respuesta se sustituye entera, nunca se muta campo a campo; evita proxificar cada objeto de una lista grande.
- **`null` como «no pedir nada»**: `useFetch(() => id.value ? `/api/${id.value}` : null)` resuelve el caso de «no cargar hasta tener id» sin opción extra.

Reglas de todo composable: nombre `useX`, se llama en `setup` (síncronamente, no dentro de un `await` ni de un handler), devuelve refs (no valores desenvueltos) para que el llamante los desestructure sin perder reactividad, y limpia lo que arranca (aquí lo hace el cleanup del watcher al desmontar).

Prueba mínima con Vitest, sin montar un componente:

```ts
import { ref, nextTick } from "vue";
import { useFetch } from "./useFetch";

test("recarga cuando cambia la URL", async () => {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    calls.push(url);
    return new Response(JSON.stringify({ url }), { status: 200 });
  }));
  const id = ref(1);
  const { data } = useFetch<{ url: string }>(() => `/api/${id.value}`);
  await vi.waitFor(() => expect(data.value?.url).toBe("/api/1"));
  id.value = 2;
  await nextTick();
  await vi.waitFor(() => expect(data.value?.url).toBe("/api/2"));
  expect(calls).toEqual(["/api/1", "/api/2"]);
});
```

Si tus cinco componentes necesitan además caché compartida entre ellos y deduplicación, el siguiente escalón es `@tanstack/vue-query` (`useQuery`), que ofrece esta misma API con esas garantías.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuándo uso `provide`/`inject` y cuándo Pinia? Tengo un componente `DataTable` con `TableHeader`, `TableRow` y `Pagination` dentro que necesitan compartir la ordenación y la página actual.",
            },
            {
                "role": "assistant",
                "content": r"""Para tu caso, `provide`/`inject`: el estado pertenece a **una instancia** de `DataTable` y solo lo necesitan sus descendientes. Pinia es para estado **global** de la aplicación (sesión, carrito), único por app. Si pusieras la ordenación en Pinia, dos tablas en la misma página compartirían la misma ordenación, que no es lo que quieres.

La forma tipada y segura:

```ts
// components/data-table/context.ts
import { inject, provide, type InjectionKey, type Ref } from "vue";

export type SortDirection = "asc" | "desc";

export type TableContext = {
  sortBy: Ref<string | null>;
  direction: Ref<SortDirection>;
  page: Ref<number>;
  setSort: (column: string) => void;
};

// Symbol tipado: inject() devuelve TableContext | undefined, no `unknown`
export const TABLE_KEY: InjectionKey<TableContext> = Symbol("data-table");

export function provideTable(ctx: TableContext) {
  provide(TABLE_KEY, ctx);
}

export function useTable(): TableContext {
  const ctx = inject(TABLE_KEY);
  if (!ctx) throw new Error("useTable() debe usarse dentro de <DataTable>");
  return ctx;
}
```

```vue
<!-- DataTable.vue -->
<script setup lang="ts">
import { ref } from "vue";
import { provideTable, type SortDirection } from "./context";

const sortBy = ref<string | null>(null);
const direction = ref<SortDirection>("asc");
const page = ref(1);

function setSort(column: string) {
  if (sortBy.value === column) {
    direction.value = direction.value === "asc" ? "desc" : "asc";
  } else {
    sortBy.value = column;
    direction.value = "asc";
  }
  page.value = 1; // cambiar la ordenación vuelve a la primera página
}

provideTable({ sortBy, direction, page, setSort });
</script>

<template>
  <table><slot /></table>
</template>
```

```vue
<!-- TableHeader.vue -->
<script setup lang="ts">
import { useTable } from "./context";

defineProps<{ column: string; label: string }>();
const { sortBy, direction, setSort } = useTable();
</script>

<template>
  <th @click="setSort(column)" :aria-sort="sortBy === column ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'">
    {{ label }}
  </th>
</template>
```

Por qué así:

- **`InjectionKey<T>`** con un `Symbol` evita colisiones de nombre y da tipos a `inject`. Con una cadena (`inject("table")`) obtienes `unknown`.
- **Se proveen `ref`s, no valores**: `provide` no es reactivo por sí mismo; lo que hace reactivo al consumidor es que recibe el mismo `ref` y lee `.value`. Si proveyeras `page.value`, el hijo recibiría el número 1 para siempre.
- **El padre expone funciones (`setSort`), no los setters crudos.** Las reglas («cambiar de columna reinicia a `asc` y a la página 1») viven en un sitio. Si quieres impedir escrituras directas, envuelve los refs con `readonly()` antes de proveerlos.
- **`useTable` lanza si falta el proveedor**, igual que un `TableHeader` fuera de `DataTable` debería fallar pronto.

Cuándo Pinia:

| Estado | Herramienta |
|---|---|
| Compartido por un subárbol de componentes (tabla, formulario, wizard, acordeón) | `provide`/`inject` |
| Global, una instancia por app, accesible desde cualquier ruta (usuario, carrito, preferencias) | Pinia |
| Global y además devtools, persistencia, SSR y acciones testables | Pinia |
| Entre padre e hijo directo | props y emits; no hace falta más |

Y un matiz: Pinia también se puede usar «por instancia» creando el store con un id dinámico (`defineStore(`table-${id}`, …)`), pero eso es llevar un estado local a una herramienta global; `provide`/`inject` es más simple y se destruye con el componente.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un store de carrito con Pinia y en el componente el contador no se actualiza al añadir productos:

```ts
// stores/cart.ts
import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const useCartStore = defineStore("cart", () => {
  const items = ref<{ id: string; qty: number }[]>([]);
  const count = computed(() => items.value.reduce((n, i) => n + i.qty, 0));
  function add(id: string) {
    const found = items.value.find((i) => i.id === id);
    if (found) found.qty++;
    else items.value.push({ id, qty: 1 });
  }
  return { items, count, add };
});
```

```vue
<script setup lang="ts">
import { useCartStore } from "@/stores/cart";
const { count, add } = useCartStore();
</script>

<template>
  <button @click="add('sku-1')">Añadir</button>
  <span>{{ count }}</span>
</template>
```""",
            },
            {
                "role": "assistant",
                "content": r"""El store está bien. El fallo está en el componente: `const { count, add } = useCartStore()` **desestructura el store**, y el store es un objeto `reactive`. Al desestructurar, `count` deja de ser el `computed` enlazado al store y pasa a ser su valor en ese momento (`0`), una constante. `add` sí funciona, porque las funciones no necesitan reactividad; por eso el carrito crece pero la pantalla no.

Arreglo: `storeToRefs` para el estado y los getters; las acciones se pueden sacar directamente.

```vue
<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useCartStore } from "@/stores/cart";

const cart = useCartStore();
const { count, items } = storeToRefs(cart); // refs enlazados al store
const { add } = cart; // las acciones son funciones normales: se pueden desestructurar
</script>

<template>
  <button @click="add('sku-1')">Añadir</button>
  <span>{{ count }}</span>
</template>
```

O, más simple si no necesitas desestructurar: usa `cart.count` y `cart.add` en la plantilla. Es la misma regla que con `reactive`: desestructurar un objeto reactivo copia valores.

`storeToRefs` sabe distinguir: convierte estado y getters en refs y **omite las acciones**, que es lo que quieres (una acción envuelta en `ref` sería un error).

Sobre el store, dos comentarios:

- La mutación `found.qty++` es correcta: `items` es un `ref` profundo, así que mutar un objeto interno es reactivo y `count` se recalcula.
- Devuelves `items` directamente; cualquier componente puede hacer `cart.items.push(...)` saltándose `add`. Si quieres impedirlo, devuelve `items: readonly(items)` y deja las escrituras a las acciones. Pinia no lo exige, pero mantiene las reglas del carrito en un sitio.

Verificación: pulsa «Añadir» dos veces; el contador debe mostrar 2 y en Vue DevTools, pestaña Pinia, `items` tiene un elemento con `qty: 2`.""",
            },
            {
                "role": "user",
                "content": "Arreglado. ¿Cómo hago que el carrito sobreviva a una recarga de página?",
            },
            {
                "role": "assistant",
                "content": r"""Con el plugin `pinia-plugin-persistedstate`, que guarda el estado del store en `localStorage` (o donde le digas) y lo rehidrata al crear el store. Para un carrito es la solución estándar: no escribes ningún `watch`.

```ts
// main.ts
import { createApp } from "vue";
import { createPinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import App from "./App.vue";

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

createApp(App).use(pinia).mount("#app");
```

```ts
// stores/cart.ts
export const useCartStore = defineStore(
  "cart",
  () => {
    const items = ref<{ id: string; qty: number }[]>([]);
    const count = computed(() => items.value.reduce((n, i) => n + i.qty, 0));
    function add(id: string) {
      const found = items.value.find((i) => i.id === id);
      if (found) found.qty++;
      else items.value.push({ id, qty: 1 });
    }
    function clear() {
      items.value = [];
    }
    return { items, count, add, clear };
  },
  {
    persist: {
      pick: ["items"], // solo el estado; `count` es un getter y se recalcula
      key: "cart-v1",  // versiona la clave: si cambias la forma de `items`, cambia a cart-v2 y el viejo se ignora
    },
  },
);
```

Decisiones:

- **`pick: ["items"]`**: persistir solo lo que es estado. Si el store creciera con cosas efímeras (`isCheckingOut`, errores), no deben sobrevivir a la recarga.
- **La clave con versión** evita el bug clásico: despliegas un cambio de estructura y los usuarios con el carrito viejo guardado rompen la app al rehidratar. Cambiar la clave descarta lo antiguo limpiamente.
- **`localStorage` por defecto**; para que el carrito caduque con la sesión del navegador, `storage: sessionStorage`. Y en Nuxt, el módulo `@pinia-plugin-persistedstate/nuxt` usa cookies para que el estado esté disponible también en el render de servidor.

Si no quieres una dependencia, el equivalente manual son diez líneas en el propio store:

```ts
const STORAGE_KEY = "cart-v1";
const items = ref<{ id: string; qty: number }[]>(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]"));
watch(items, (value) => localStorage.setItem(STORAGE_KEY, JSON.stringify(value)), { deep: true });
```

Funciona, pero no cubre la validación del JSON corrupto ni el SSR; el plugin sí.

Verificación: añade dos productos, recarga: el contador sigue en 2 y en Application → Local Storage ves la clave `cart-v1` con `{"items":[…]}`. Llama a `clear()` y comprueba que la clave queda con `[]`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Vue Router 4: necesito rutas con carga perezosa, una zona `/admin` solo para usuarios con sesión (y que al hacer login vuelva a donde iba), y leer el `id` de `/users/:id` reaccionando cuando cambia sin desmontar el componente.",
            },
            {
                "role": "assistant",
                "content": r"""Tres necesidades, tres piezas del router: `import()` en `component`, un guard global con `meta`, y `useRoute` con un `watch` sobre el parámetro.

```ts
// router/index.ts
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";

// Tipado de meta: `to.meta.requiresAuth` deja de ser `unknown`
declare module "vue-router" {
  interface RouteMeta {
    requiresAuth?: boolean;
  }
}

const routes: RouteRecordRaw[] = [
  { path: "/", name: "home", component: () => import("@/views/HomeView.vue") },
  { path: "/login", name: "login", component: () => import("@/views/LoginView.vue") },
  { path: "/users/:id", name: "user", component: () => import("@/views/UserView.vue"), props: true },
  {
    path: "/admin",
    component: () => import("@/layouts/AdminLayout.vue"),
    meta: { requiresAuth: true }, // los hijos lo heredan vía to.matched
    children: [
      { path: "", name: "admin-home", component: () => import("@/views/admin/DashboardView.vue") },
      { path: "orders", name: "admin-orders", component: () => import("@/views/admin/OrdersView.vue") },
    ],
  },
  { path: "/:pathMatch(.*)*", name: "not-found", component: () => import("@/views/NotFoundView.vue") },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, saved) => saved ?? { top: 0 },
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  const needsAuth = to.matched.some((record) => record.meta.requiresAuth);
  if (needsAuth && !auth.isLoggedIn) {
    // Devolver una ubicación redirige; `redirect` guarda a dónde iba
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isLoggedIn) {
    return { name: "home" };
  }
});
```

Tras el login, el componente devuelve al usuario a donde iba:

```ts
// views/LoginView.vue (script setup)
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

async function onSubmit() {
  await auth.login(form);
  const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
  router.replace(redirect); // replace: el login no queda en el historial
}
```

Y la vista de usuario reacciona al cambio de `id` sin desmontarse (el router reutiliza el componente al pasar de `/users/1` a `/users/2`):

```vue
<!-- views/UserView.vue -->
<script setup lang="ts">
import { ref, watch } from "vue";

const { id } = defineProps<{ id: string }>(); // `props: true` convierte :id en prop
const user = ref<{ name: string } | null>(null);

watch(
  () => id,
  async (newId) => {
    user.value = null;
    user.value = await fetch(`/api/users/${newId}`).then((r) => r.json());
  },
  { immediate: true }, // carga inicial + cada cambio
);
</script>

<template>
  <p v-if="!user">Cargando…</p>
  <h1 v-else>{{ user.name }}</h1>
</template>
```

Por qué cada decisión:

- **`() => import(...)`** en cada `component` crea un chunk por vista; Vite lo divide solo. No lo hagas en la ruta raíz si quieres que la portada cargue sin una petición extra.
- **`to.matched.some(...)`** en lugar de `to.meta.requiresAuth`: Vue Router fusiona `meta` de padres a hijos, así que `to.meta` ya lo tendría, pero `matched` deja claro que la protección viene del padre y funciona aunque un hijo defina su propio `meta`.
- **Devolver una ubicación desde `beforeEach`** es la API actual; `next()` sigue funcionando pero es fácil olvidar llamarlo o llamarlo dos veces.
- **`props: true`** desacopla la vista del router: `UserView` recibe `id` como cualquier prop y se puede probar sin router. El `watch` con getter (`() => id`) es necesario porque `id` viene de la desestructuración de props.
- **`route.query.redirect` puede ser array** (`?redirect=a&redirect=b`), de ahí la comprobación de tipo; sin ella, `router.replace(["a","b"])` lanza.

Verificación: sin sesión, visita `/admin/orders`: debes acabar en `/login?redirect=%2Fadmin%2Forders`; tras el login, en `/admin/orders`. Y navega de `/users/1` a `/users/2` con un `console.log` en `onMounted` de `UserView`: debe aparecer una sola vez (no se desmonta), mientras el `watch` se dispara dos veces.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Could you explain, in Spanish, how to build a reusable Modal in Vue 3 with named and scoped slots, rendered at the end of body with Teleport, with typed slots?",
            },
            {
                "role": "assistant",
                "content": r"""Un modal reutilizable necesita tres cosas que Vue resuelve con herramientas distintas: salir del árbol DOM del padre (`Teleport`), dejar que el consumidor ponga su contenido en zonas concretas (slots con nombre) y darle acceso a funciones internas como `close` (slots con alcance).

```vue
<!-- Modal.vue -->
<script setup lang="ts">
import { watch, onBeforeUnmount } from "vue";

const open = defineModel<boolean>({ required: true });

defineProps<{ title: string }>();

// Tipado de slots: qué props recibe cada uno
defineSlots<{
  default(props: { close: () => void }): unknown;
  header?(props: { title: string }): unknown;
  footer?(props: { close: () => void }): unknown;
}>();

function close() {
  open.value = false;
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") close();
}

watch(
  open,
  (isOpen) => {
    if (isOpen) document.addEventListener("keydown", onKeydown);
    else document.removeEventListener("keydown", onKeydown);
  },
  { immediate: true },
);

onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="backdrop" @click.self="close">
      <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
        <header>
          <slot name="header" :title="title">
            <h2>{{ title }}</h2>
          </slot>
        </header>

        <section>
          <slot :close="close" />
        </section>

        <footer>
          <slot name="footer" :close="close">
            <button type="button" @click="close">Cerrar</button>
          </slot>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
```

Uso con los tres slots:

```vue
<script setup lang="ts">
import { ref } from "vue";
import Modal from "./Modal.vue";

const showConfirm = ref(false);

async function remove() {
  await deleteOrder();
  showConfirm.value = false;
}
</script>

<template>
  <button @click="showConfirm = true">Eliminar pedido</button>

  <Modal v-model="showConfirm" title="¿Eliminar el pedido?">
    <template #header="{ title }">
      <h2 class="danger">{{ title }}</h2>
    </template>

    <template #default="{ close }">
      <p>Esta acción no se puede deshacer.</p>
      <a href="#" @click.prevent="close">Prefiero revisarlo</a>
    </template>

    <template #footer="{ close }">
      <button @click="close">Cancelar</button>
      <button class="danger" @click="remove">Eliminar</button>
    </template>
  </Modal>
</template>
```

Las decisiones:

- **`<Teleport to="body">`** mueve el DOM del modal al final de `body`, fuera de cualquier `overflow: hidden` o `z-index` del padre. El componente sigue siendo hijo lógico de quien lo usa: recibe sus props, sus slots y su `provide`.
- **`v-if` dentro del Teleport, no fuera**: así el Teleport existe siempre y solo el contenido se monta y desmonta; evita avisos de montaje cuando `body` aún no está disponible en SSR.
- **Slots con contenido por defecto**: `<slot name="footer">` lleva un botón «Cerrar» dentro; si el consumidor no define el slot, se usa ese. El 80 % de los modales no necesitan personalizar el pie.
- **Slots con alcance** (`:close="close"`): el consumidor recibe `close` y decide cuándo llamarla. Sin esto, tendría que poner `showConfirm = false` en cada botón, duplicando la lógica que ya está en el modal.
- **`defineSlots`** (3.3+) tipa las props de cada slot: `#footer="{ clos }"` con una errata es un error de TypeScript, y `?` marca los opcionales.
- **`@click.self`** en el fondo: cierra solo si el clic fue en el fondo, no en un hijo; sin `.self`, un clic dentro del diálogo burbujea y lo cierra.
- **`defineModel<boolean>`** da `v-model` al consumidor y permite cerrar desde dentro (Escape, fondo) sin emitir eventos a mano.

Lo que falta para accesibilidad completa, si lo necesitas: atrapar el foco dentro del diálogo y devolverlo al botón que lo abrió. Lo más simple es usar el elemento nativo `<dialog>` con `showModal()`, que lo hace solo; el patrón de slots y Teleport se mantiene igual.

Verificación: abre el modal, pulsa Escape: se cierra y `showConfirm` vuelve a `false` en el padre. Inspecciona el DOM: el `.backdrop` está como último hijo de `<body>`, no dentro del componente que lo abrió.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Este aviso me sale al usar mi componente de input y no entiendo qué quiere:

```
[Vue warn]: Extraneous non-props attributes (class, data-testid) were passed to component but could not be automatically inherited because component renders fragment or text root nodes.
```

```vue
<!-- BaseInput.vue -->
<script setup lang="ts">
const model = defineModel<string>();
defineProps<{ label: string }>();
</script>

<template>
  <label>{{ label }}</label>
  <input v-model="model" />
</template>
```

Lo uso así: `<BaseInput v-model="name" label="Nombre" class="wide" data-testid="name" />`""",
            },
            {
                "role": "assistant",
                "content": r"""Vue aplica automáticamente los atributos que **no son props** (`class`, `style`, `data-*`, `id`, listeners) al **elemento raíz** del componente. Tu plantilla tiene dos raíces (`<label>` e `<input>`), así que no hay «la raíz» y Vue no sabe dónde ponerlos. Te avisa porque esos atributos se están perdiendo: el `class="wide"` no llega a ningún sitio.

Dos arreglos según lo que quieras:

**1. Decidir tú a qué elemento van**, que es lo correcto para un input: `class` y `data-testid` deben ir al `<input>`, no al `<label>`.

```vue
<!-- BaseInput.vue -->
<script setup lang="ts">
import { useId } from "vue";

defineOptions({ inheritAttrs: false }); // desactiva la herencia automática y el aviso

const model = defineModel<string>();
defineProps<{ label: string }>();
const id = useId();
</script>

<template>
  <label :for="id">{{ label }}</label>
  <input :id="id" v-model="model" v-bind="$attrs" />
</template>
```

`v-bind="$attrs"` vuelca todos los atributos no declarados como props en ese elemento: `class`, `data-testid`, `placeholder`, `maxlength`, `@blur`… Ganas que el componente acepte cualquier atributo nativo sin declararlo.

**2. Envolver en una raíz única**, si quieres que `class` afecte al contenedor:

```vue
<template>
  <div class="field">
    <label :for="id">{{ label }}</label>
    <input :id="id" v-model="model" />
  </div>
</template>
```

Aquí `class="wide"` se fusiona con `class="field"` en el `<div>` (Vue combina las clases, no las sustituye). Pero `placeholder` o `maxlength` también acabarían en el `<div>`, que no es lo que nadie quiere; para un input, la opción 1 es mejor.

Para repartir atributos entre varios elementos (por ejemplo, `class` al contenedor y el resto al input), `useAttrs()` en el script te da el objeto y lo divides a mano:

```ts
import { useAttrs, computed } from "vue";

defineOptions({ inheritAttrs: false });
const attrs = useAttrs();
const wrapperAttrs = computed(() => ({ class: attrs.class, style: attrs.style }));
const inputAttrs = computed(() => {
  const { class: _c, style: _s, ...rest } = attrs;
  return rest;
});
```

Un detalle: `$attrs` incluye los listeners (`onBlur`) y es reactivo, pero **no está incluido en `defineProps`**. Todo lo que declares como prop deja de aparecer en `$attrs`; si quieres recibir `placeholder` como prop para documentarla, perfecto, pero entonces pásala tú al input explícitamente.

Verificación: tras el cambio, inspecciona el DOM: el `<input>` debe tener `class="wide"` y `data-testid="name"`, y el aviso desaparece de la consola. Un test con `screen.getByTestId("name")` encuentra el input, no el label.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 11-17 Nuxt 3: estructura y auto-imports (multiturno), useFetch/useAsyncData/$fetch, server/api con h3,
#               middleware, layouts, SSR/SPA/híbrido y despliegue (multiturno), useState vs Pinia (EN)
# 18-20 Svelte 5: runes (multiturno), $props/snippets, migración desde Svelte 4
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Acabo de crear un proyecto con `npx nuxi init` y la carpeta está casi vacía. ¿Qué carpetas crea Nuxt 3 «por convención» y por qué puedo usar `ref` y `useRoute` sin importarlos?",
            },
            {
                "role": "assistant",
                "content": r"""Nuxt 3 funciona por **convención de carpetas**: cada directorio con nombre reservado activa un comportamiento, y los auto-imports hacen que las APIs de Vue, Nuxt y tus propios composables estén disponibles sin `import`.

Las carpetas que importan, y qué hace cada una al existir:

```
pages/          # enrutado por archivos: pages/users/[id].vue → /users/:id
layouts/        # plantillas envolventes: layouts/default.vue se aplica a todas las páginas
components/     # registrados automáticamente: components/ui/Button.vue → <UiButton />
composables/    # auto-importados: composables/useCart.ts → useCart() disponible en todas partes
utils/          # igual que composables, para funciones puras (formatDate, slugify)
middleware/     # guards de navegación: middleware/auth.ts → definePageMeta({ middleware: "auth" })
plugins/        # se ejecutan al crear la app (registrar librerías, inyectar helpers)
server/
  api/          # endpoints: server/api/users.get.ts → GET /api/users
  routes/       # rutas de servidor sin el prefijo /api
  middleware/   # se ejecuta en cada petición al servidor
  utils/        # auto-importados solo en el servidor
public/         # archivos estáticos servidos tal cual (/favicon.ico)
assets/         # recursos procesados por Vite (CSS, imágenes importadas)
app.vue         # raíz de la app; con pages/ debe contener <NuxtPage />
nuxt.config.ts  # configuración
```

Ninguna es obligatoria: un proyecto sin `pages/` es una app de una sola vista que vive en `app.vue`. Crear `pages/` activa Vue Router; crear `server/api/` activa el servidor Nitro. Es progresivo.

Por qué `ref` y `useRoute` no necesitan import: Nuxt escanea `composables/`, `utils/` y las APIs de Vue/Nuxt y genera una tabla de imports que el compilador inserta cuando ve el identificador. Es un `import` real que se añade en el build, no una variable global, así que el tree-shaking funciona y el editor lo entiende gracias a los tipos que Nuxt genera en `.nuxt/` (por eso conviene ejecutar `nuxi prepare` o arrancar el dev server antes de abrir el editor).

Un `app.vue` mínimo con páginas y layout:

```vue
<!-- app.vue -->
<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
```

```vue
<!-- pages/index.vue -->
<script setup lang="ts">
const route = useRoute(); // sin import
const count = ref(0);     // sin import
</script>

<template>
  <h1>Inicio ({{ route.path }})</h1>
  <button @click="count++">{{ count }}</button>
</template>
```

Dos convenciones más que tropiezan al principio:

- **Nombres de componentes por ruta**: `components/form/TextInput.vue` se llama `<FormTextInput />`. Si prefieres nombres planos, `components: [{ path: "~/components", pathPrefix: false }]` en la configuración.
- **Los archivos de `server/` no son Vue**: son funciones de Nitro (h3), se ejecutan en Node y no tienen acceso a `ref` ni a `useRoute`; allí los auto-imports son los de `server/utils/` y las utilidades de h3.

Una nota sobre versiones: en Nuxt 4 (2025) el código de la app se mueve por defecto a una carpeta `app/` (`app/pages`, `app/components`…) y `server/` queda al mismo nivel; la lógica es idéntica, solo cambia la raíz. En un proyecto Nuxt 3 la estructura es la de arriba.

Comprobación: crea `pages/about.vue` con cualquier plantilla, abre `/about` y verás la página sin tocar ningún archivo de rutas. Crea `composables/useHello.ts` que exporte `export const useHello = () => "hola"` y úsalo en la página sin import.""",
            },
            {
                "role": "user",
                "content": "¿Y si no quiero magia? En el equipo hay gente a la que los auto-imports le resultan opacos y prefiere ver de dónde viene cada cosa.",
            },
            {
                "role": "assistant",
                "content": r"""Puedes desactivarlos parcial o totalmente, y hay un punto medio que suele contentar a los dos bandos.

**Punto medio: imports explícitos desde `#imports`.** Los auto-imports siguen activos, pero quien quiera ser explícito escribe:

```ts
import { ref, computed } from "vue";
import { useRoute, useFetch } from "#imports"; // alias que agrupa todo lo que Nuxt auto-importa
import { useCart } from "~/composables/useCart";
```

Nada cambia para el resto del equipo, y el código explícito es válido y tipado. Es lo que recomendaría para empezar: el linter no obliga a nada y cada archivo deja claro su origen si el autor quiere.

**Desactivar los auto-imports de composables y utilidades** (los componentes siguen registrándose):

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  imports: {
    autoImport: false,
  },
});
```

A partir de ahí, todo `ref`, `useRoute`, `useFetch` y tus composables requieren `import`. Las macros del compilador (`definePageMeta`, `defineNuxtConfig`) siguen funcionando sin import porque son transformaciones, no funciones.

**Desactivar también el registro automático de componentes**:

```ts
export default defineNuxtConfig({
  imports: { autoImport: false },
  components: { dirs: [] },
});
```

Con esto, cada componente se importa como en Vue a secas. Ten en cuenta que los componentes de Nuxt (`<NuxtPage>`, `<NuxtLink>`, `<NuxtLayout>`) siguen disponibles; los módulos que instales pueden depender del registro automático para los suyos, así que mira su documentación.

Qué pierdes al desactivarlo del todo, con honestidad:

- Los módulos del ecosistema (`@nuxt/image`, `@pinia/nuxt`, `@nuxtjs/i18n`) documentan todo con auto-imports; tendrás que buscar la ruta de import de cada cosa (`#imports` resuelve la mayoría).
- Mover un composable de carpeta implica tocar imports en vez de nada.

Qué ganas: trazabilidad inmediata y ningún nombre «aparecido de la nada» para quien lee código fuera del editor (revisiones en GitHub, diffs).

Si la objeción del equipo es la opacidad más que la magia en sí, el `.nuxt/imports.d.ts` que Nuxt genera lista exactamente qué identificadores se auto-importan y desde dónde; enseñárselo suele resolver más dudas que desactivar la funcionalidad.

Verificación tras activar `autoImport: false`: `nuxi typecheck` marca cada uso sin import como `Cannot find name 'ref'`, que es justo la lista de sitios a corregir. Con `#imports` disponibles, un codemod sencillo (buscar y añadir imports) deja el proyecto compilando en una tarde.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En Nuxt 3 hay `useFetch`, `useAsyncData` y `$fetch` y no sé cuál usar. En una página uso `$fetch` dentro de `<script setup>` y veo la petición dos veces, una en la terminal y otra en el navegador.",
            },
            {
                "role": "assistant",
                "content": r"""Son tres niveles de la misma herramienta:

- **`$fetch`**: un cliente HTTP (ofetch). Hace la petición y devuelve la promesa. No sabe nada de SSR.
- **`useAsyncData(key, fn)`**: ejecuta `fn` en el servidor durante el render, **serializa el resultado en el HTML** y lo reutiliza en el cliente al hidratar, sin volver a pedirlo. Te da `data`, `status`, `error`, `refresh`.
- **`useFetch(url)`**: `useAsyncData` + `$fetch` con la clave generada a partir de la URL. Es el 90 % de los casos.

Tu doble petición es exactamente lo que `$fetch` a secas hace en `<script setup>`: el script se ejecuta en el servidor (primera petición, la de la terminal) y otra vez en el navegador al hidratar (segunda petición), porque nada transporta el resultado de un lado al otro.

Arreglo:

```vue
<script setup lang="ts">
type Product = { id: string; name: string; price: number };

const { data: products, status, error, refresh } = await useFetch<Product[]>("/api/products", {
  query: { category: "chairs" },
});
</script>

<template>
  <p v-if="status === 'pending'">Cargando…</p>
  <p v-else-if="error" role="alert">{{ error.statusMessage }}</p>
  <ul v-else>
    <li v-for="p in products" :key="p.id">{{ p.name }}</li>
  </ul>
  <button @click="refresh()">Actualizar</button>
</template>
```

Una sola petición, en el servidor; el cliente recibe los datos en el payload de la página.

Cuándo cada uno:

| Caso | Usa |
|---|---|
| Cargar datos para renderizar la página | `useFetch` |
| La fuente no es una URL (SDK, varias llamadas combinadas, base de datos en un server route) | `useAsyncData("key", () => …)` |
| Acción del usuario después de montar (enviar formulario, botón «me gusta») | `$fetch` dentro del handler |
| Dentro de `server/api/*` | `$fetch` o directamente la lógica |

Opciones de `useFetch` que resuelven lo habitual:

- **`lazy: true`**: no bloquea la navegación; la página se muestra y los datos llegan después (`status === "pending"` mientras tanto). Sin `lazy`, el `await` retrasa la navegación hasta tener datos.
- **`server: false`**: solo en cliente (datos que dependen del navegador o que no quieres en el HTML).
- **`watch: [page]`**: vuelve a pedir cuando cambia un `ref`. Si la URL es un getter (`() => `/api/products?page=${page.value}``), ya reacciona sola.
- **`transform: (res) => res.items`**: adapta la respuesta antes de guardarla; lo transformado es lo que se serializa.
- **`key`**: por defecto se deriva de URL y opciones; si llamas al mismo endpoint con el mismo query en dos sitios con `transform` distintos, dale una clave explícita a cada uno o compartirán caché.
- **`default: () => []`**: valor inicial para que la plantilla no trate con `null` antes de cargar.

Dos trampas más, aparte de la doble petición:

1. **`useFetch` dentro de una función o un handler** (no en el nivel superior de `setup`) funciona, pero pierde la deduplicación de SSR y Nuxt avisa. Para acciones, `$fetch`.
2. **`await useFetch` sin `lazy` en un componente que se renderiza muchas veces** (una fila de tabla) bloquea cada instancia; sube la carga al padre y pasa los datos por props.

Verificación: con el arreglo, en la terminal del servidor aparece una petición a `/api/products` por carga de página y en la pestaña Network del navegador **ninguna** a ese endpoint tras la navegación inicial (los datos vienen en el `<script id="__NUXT_DATA__">`). Al pulsar «Actualizar» sí verás una, hecha desde el cliente por `refresh()`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito en Nuxt 3 un endpoint `POST /api/orders` que valide el cuerpo con zod, uno `GET /api/orders/:id` que devuelva 404 si no existe, y que los errores salgan con el formato correcto. ¿Cómo se escriben los server routes?",
            },
            {
                "role": "assistant",
                "content": r"""Los server routes viven en `server/api/` y son funciones de **h3** (el framework HTTP de Nitro). El nombre del archivo define la ruta y, opcionalmente, el método: `orders.post.ts` solo responde a `POST`.

```ts
// server/api/orders.post.ts
import { z } from "zod";

const CreateOrder = z.object({
  customerId: z.string().uuid(),
  items: z.array(z.object({ sku: z.string().min(1), qty: z.number().int().positive() })).min(1),
});

export default defineEventHandler(async (event) => {
  // readValidatedBody lanza un 400 con los detalles de zod si el cuerpo no cumple
  const body = await readValidatedBody(event, CreateOrder.parse);

  const order = await db.order.create({ data: { ...body, status: "pending" } });

  setResponseStatus(event, 201);
  return order; // cualquier objeto devuelto se serializa como JSON
});
```

```ts
// server/api/orders/[id].get.ts
export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, "id");
  if (!id) throw createError({ statusCode: 400, statusMessage: "Missing id" });

  const order = await db.order.findUnique({ where: { id } });
  if (!order) {
    throw createError({ statusCode: 404, statusMessage: "Order not found" });
  }
  return order;
});
```

Y un listado con query validado:

```ts
// server/api/orders.get.ts
import { z } from "zod";

const Query = z.object({
  status: z.enum(["pending", "paid", "shipped"]).optional(),
  page: z.coerce.number().int().min(1).default(1), // coerce: los query params llegan como string
});

export default defineEventHandler(async (event) => {
  const { status, page } = await getValidatedQuery(event, Query.parse);
  return db.order.findMany({
    where: status ? { status } : undefined,
    skip: (page - 1) * 20,
    take: 20,
  });
});
```

Cómo funciona cada pieza:

- **`defineEventHandler`**, `readValidatedBody`, `getValidatedQuery`, `getRouterParam`, `createError`, `setResponseStatus` son utilidades de h3, auto-importadas en `server/`. Sin dependencias extra.
- **`readValidatedBody(event, schema.parse)`** combina leer el JSON y validarlo; si `parse` lanza, h3 responde `400` con `statusMessage: "Validation Error"` y los `issues` de zod en `data`. Si prefieres controlar el mensaje, usa `safeParse` y `createError` a mano.
- **`createError` + `throw`** es la forma canónica de responder con un error: Nitro genera el JSON `{ statusCode, statusMessage, message }`, y en el cliente `useFetch` lo entrega en `error.value` con esos mismos campos. Un `return { error: "..." }` con status 200 rompe esa cadena.
- **`setResponseStatus(event, 201)`** para el código de creación; sin él, 200.
- **Los `[id]` del nombre de archivo** se leen con `getRouterParam`; `[...slug].ts` captura varios segmentos.

Consumo desde la página, con el error tipado:

```vue
<script setup lang="ts">
const route = useRoute();
const { data: order, error } = await useFetch(`/api/orders/${route.params.id}`);

if (error.value?.statusCode === 404) {
  throw createError({ statusCode: 404, statusMessage: "Pedido no encontrado", fatal: true }); // muestra error.vue
}
</script>
```

Lo que no hay que hacer: acceder a `event.node.req` para leer el cuerpo a mano (pierdes la validación y la compatibilidad con otros runtimes), ni poner lógica de negocio en el handler. Deja el handler como adaptador HTTP y la lógica en `server/utils/orders.ts` (auto-importado en servidor), que así se prueba sin HTTP.

Verificación:

```
curl -s -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{"customerId":"x","items":[]}' -i
```

Debe responder `400` con `"statusMessage":"Validation Error"` y un array `data.issues`. Con un cuerpo válido, `201` y el pedido. `curl -si localhost:3000/api/orders/no-existe` devuelve `404` con `"statusMessage":"Order not found"`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo protejo rutas en Nuxt 3? Quiero que `/account/*` exija sesión y redirija a `/login`, y que el middleware no se ejecute en todas las páginas.",
            },
            {
                "role": "assistant",
                "content": r"""Con un **middleware de ruta con nombre** que se aplica solo a las páginas que lo declaran. Nuxt lo ejecuta antes de entrar en la ruta, tanto en el servidor (primera carga) como en el cliente (navegación posterior).

```ts
// middleware/auth.ts
export default defineNuxtRouteMiddleware((to) => {
  const { loggedIn } = useUserSession(); // tu composable de sesión (abajo)

  if (!loggedIn.value) {
    // Guarda a dónde iba para volver tras el login
    return navigateTo({ path: "/login", query: { redirect: to.fullPath } });
  }
});
```

```vue
<!-- pages/account/index.vue -->
<script setup lang="ts">
definePageMeta({ middleware: "auth" });
</script>
```

Para no repetir `definePageMeta` en cada página de `/account/*`, hay dos opciones:

**Opción A: un middleware global que decide por prefijo.** Se ejecuta en todas las navegaciones, pero sale inmediatamente si la ruta no está protegida:

```ts
// middleware/auth.global.ts  (el sufijo .global lo activa para todas las rutas)
const PROTECTED = ["/account", "/orders"];

export default defineNuxtRouteMiddleware((to) => {
  if (!PROTECTED.some((prefix) => to.path.startsWith(prefix))) return;

  const { loggedIn } = useUserSession();
  if (!loggedIn.value) {
    return navigateTo({ path: "/login", query: { redirect: to.fullPath } });
  }
});
```

**Opción B: `definePageMeta` en un layout no sirve** (las metas son por página), pero puedes marcar las páginas protegidas por carpeta usando el `routeRules` de `nuxt.config.ts` para añadir metas:

```ts
export default defineNuxtConfig({
  routeRules: {
    "/account/**": { appMiddleware: "auth" },
  },
});
```

Esto aplica el middleware `auth` a todo el subárbol sin tocar las páginas. Es la opción más limpia cuando la protección se define por URL.

El composable de sesión, en su versión mínima con cookie:

```ts
// composables/useUserSession.ts
export function useUserSession() {
  // useState: estado compartido entre servidor y cliente, serializado en el payload
  const user = useState<{ id: string; name: string } | null>("session-user", () => null);
  const loggedIn = computed(() => user.value !== null);
  return { user, loggedIn };
}
```

Y un plugin que lo rellena en cada petición a partir de la cookie, para que el middleware lo encuentre listo también en el servidor:

```ts
// plugins/session.server.ts  (.server: solo se ejecuta en SSR)
export default defineNuxtPlugin(async () => {
  const user = useState<{ id: string; name: string } | null>("session-user");
  const token = useCookie("session").value;
  if (token) {
    user.value = await $fetch("/api/me", { headers: useRequestHeaders(["cookie"]) }).catch(() => null);
  }
});
```

Puntos que importan:

- **`navigateTo` se devuelve**, no se llama y se sigue. En el servidor produce una redirección HTTP real (302); en el cliente, una navegación.
- **`useRequestHeaders(["cookie"])`** reenvía la cookie del navegador al `$fetch` interno durante el SSR; sin eso, el servidor pide `/api/me` sin cookie y siempre ve «no logueado».
- **El middleware de ruta es UX, no seguridad.** Los server routes de `/api/*` que devuelven datos privados comprueban la sesión por su cuenta (lee la cookie con `getCookie(event, "session")` y verifica). Un middleware de cliente se puede saltar.
- **`abortNavigation()`** en lugar de `navigateTo` cuando quieras mostrar un error (403) en vez de redirigir.

Para sesiones completas (hash de contraseña, cookies selladas, OAuth) sin escribir el plugin ni el composable, el módulo `nuxt-auth-utils` ofrece `useUserSession()` con esta misma forma y `requireUserSession(event)` para los server routes.

Verificación: sin cookie, `curl -I localhost:3000/account` debe devolver `302` con `location: /login?redirect=%2Faccount`; con la cookie válida, `200`. En el navegador, navegar de `/` a `/account` sin sesión debe redirigir sin recargar la página.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo tres zonas con aspecto distinto: la web pública, el panel de administración y las páginas de login (sin menú). ¿Cómo se hace eso con layouts en Nuxt 3?",
            },
            {
                "role": "assistant",
                "content": r"""Un layout por zona en `layouts/`, y cada página declara cuál usa con `definePageMeta`. El que no declara nada usa `default`.

```
layouts/
  default.vue   # web pública: cabecera + pie
  admin.vue     # panel: barra lateral + cabecera compacta
  blank.vue     # login: nada alrededor
```

```vue
<!-- layouts/default.vue -->
<template>
  <div class="site">
    <SiteHeader />
    <main>
      <slot />   <!-- aquí se inserta la página -->
    </main>
    <SiteFooter />
  </div>
</template>
```

```vue
<!-- layouts/admin.vue -->
<template>
  <div class="admin">
    <AdminSidebar />
    <div class="admin__content">
      <AdminTopbar />
      <slot />
    </div>
  </div>
</template>
```

```vue
<!-- layouts/blank.vue -->
<template>
  <slot />
</template>
```

```vue
<!-- app.vue -->
<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
```

Las páginas:

```vue
<!-- pages/admin/orders.vue -->
<script setup lang="ts">
definePageMeta({ layout: "admin", middleware: "auth" });
</script>
```

```vue
<!-- pages/login.vue -->
<script setup lang="ts">
definePageMeta({ layout: "blank" });
</script>
```

Las de la web pública no declaran nada.

Detalles que ahorran sorpresas:

- **El layout se conserva entre páginas que lo comparten**: navegar de `/admin/orders` a `/admin/users` no vuelve a montar `admin.vue` (la barra lateral conserva su estado). Al cambiar de layout, sí se monta el nuevo.
- **Cambiar el layout en tiempo de ejecución**: `setPageLayout("blank")` desde un middleware o un handler; útil para una vista de impresión.
- **Props al layout**: `<NuxtLayout name="admin" :collapsed="true">` en `app.vue` o en una página con `layout: false` que renderice su propio `<NuxtLayout>`. Para datos compartidos entre layout y página (usuario, tema), `useState` es más simple que las props.
- **`layout: false`** desactiva el layout para una página que quiere controlar todo su árbol.
- **Un layout debe tener una única raíz** (el `<div>` envolvente) si usas transiciones de página; con varias raíces, `<Transition>` no puede animar.

Para no escribir `layout: "admin"` en veinte páginas, aplica la meta por URL:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  routeRules: {
    "/admin/**": { appLayout: "admin" },
  },
});
```

Verificación: visita `/`, `/admin/orders` y `/login`: cabecera y pie solo en la primera, barra lateral solo en la segunda, nada alrededor en la tercera. En Vue DevTools, el árbol de componentes muestra `NuxtLayout → LayoutsAdmin → NuxtPage` en la ruta del panel.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "No tengo claro si mi app de Nuxt debería ser SSR, SPA o estática. Es un catálogo público con unas páginas de administración detrás de login. Además, me sale un error de hidratación con la fecha de «última actualización».",
            },
            {
                "role": "assistant",
                "content": r"""No tienes que elegir una para toda la app: Nuxt 3 permite decidir **por ruta** con `routeRules`. Para tu caso la combinación correcta es catálogo prerenderizado o con caché (SEO y velocidad) y administración en modo SPA (no necesita SEO y sí necesita sesión).

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  routeRules: {
    "/": { prerender: true },                 // generada en el build, servida como HTML estático
    "/products/**": { swr: 3600 },            // SSR con caché: regenera en segundo plano cada hora
    "/admin/**": { ssr: false },              // SPA: el HTML va vacío y Vue renderiza en el cliente
    "/old-catalog": { redirect: "/products" },
    "/api/**": { cors: true },
  },
});
```

| Modo | Qué hace | Cuándo |
|---|---|---|
| `prerender: true` | HTML generado en el build | páginas que no cambian entre despliegues (portada, legales) |
| `swr: N` / `isr: N` | SSR con caché que se revalida en segundo plano (`isr` para plataformas con soporte nativo como Vercel/Netlify) | catálogo, blog: contenido que cambia pero no por usuario |
| SSR por defecto | render en servidor en cada petición | páginas por usuario con SEO (poco habitual) |
| `ssr: false` | SPA | administración, dashboards, todo lo que está detrás de login |

Si **toda** la app fuera pública y estática, `nuxi generate` la convierte en archivos estáticos para cualquier CDN. Si fuera toda privada, `ssr: false` global en la config. El híbrido es lo normal.

**El error de hidratación** es independiente del modo y tiene una causa concreta: la fecha se formatea en el servidor con su zona horaria y locale, y en el cliente con las del navegador. El HTML dice `13/05/2025 10:00` y el cliente genera `13/05/2025 12:00`; Vue detecta la diferencia y avisa (`Hydration text mismatch`).

Tres arreglos, de más a menos recomendable:

1. **Formatear con una zona y locale fijos** en ambos lados, así el texto coincide:

```ts
const formatter = new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Madrid" });
const updatedLabel = computed(() => formatter.format(new Date(product.value.updatedAt)));
```

2. **Renderizar la fecha solo en el cliente** cuando de verdad quieres la hora local del usuario:

```vue
<ClientOnly>
  <time :datetime="product.updatedAt">{{ new Date(product.updatedAt).toLocaleString() }}</time>
  <template #fallback><time :datetime="product.updatedAt">—</time></template>
</ClientOnly>
```

3. **Mandar la fecha ya formateada desde el servidor** (en el server route), de modo que el cliente solo pinte un string.

Lo que no hay que hacer: meter `Date.now()` o `Math.random()` en una plantilla renderizada en servidor; es la misma categoría de error.

Verificación: tras el cambio, recarga la página con la consola abierta y no debe aparecer ningún aviso `Hydration`. Y para comprobar los `routeRules`, `curl -I localhost:3000/products/silla` dos veces: la segunda debe traer una cabecera de caché de Nitro (`x-nitro-prerender` o `cache-control` con `s-maxage`, según el preset) y responder al instante.""",
            },
            {
                "role": "user",
                "content": "Vale, híbrido entonces. ¿Y cómo se despliega eso? ¿Necesito un servidor Node o vale un hosting estático?",
            },
            {
                "role": "assistant",
                "content": r"""Con rutas en SSR o `swr` necesitas **algo que ejecute código en el servidor**: un proceso Node, una función serverless o un worker en el edge. Un hosting puramente estático solo vale si todo es `prerender` o SPA.

La buena noticia es que Nitro (el servidor de Nuxt) compila a cualquiera de esos destinos con un **preset**, sin cambiar el código:

```
npx nuxi build                         # preset por defecto: node-server
node .output/server/index.mjs          # arranca en el puerto 3000
```

El resultado en `.output/` es autocontenido (servidor + estáticos + dependencias necesarias), unos pocos MB. No hace falta `node_modules` en producción.

Otros destinos, cambiando solo el preset:

| Dónde | Preset | Cómo |
|---|---|---|
| Servidor propio / Docker | `node-server` (por defecto) | `node .output/server/index.mjs` |
| Vercel | `vercel` | se detecta solo; `swr` se traduce a ISR nativo |
| Netlify | `netlify` | se detecta solo |
| Cloudflare Pages / Workers | `cloudflare-pages` | `NITRO_PRESET=cloudflare-pages nuxi build` |
| Solo estático (si no hay SSR) | — | `nuxi generate` y sube `.output/public` a cualquier CDN |

El preset se fija con la variable `NITRO_PRESET` o en la configuración (`nitro: { preset: "cloudflare-pages" }`). Las plataformas grandes lo detectan por su propia variable de entorno, sin configurar nada.

Un Dockerfile mínimo para la opción de servidor propio:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.output ./.output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
```

La imagen final no lleva código fuente ni `node_modules`: solo `.output`.

Dos cosas que cambian según el destino:

- **La caché de `swr`** vive en memoria del proceso con `node-server`; con varias réplicas, cada una tiene la suya. Para compartirla, configura un `storage` de Nitro (Redis) para `cache`. En Vercel/Netlify la gestiona la plataforma.
- **Variables de entorno en runtime**: lo que esté en `runtimeConfig` de `nuxt.config.ts` se puede sobrescribir al arrancar con `NUXT_*` (`NUXT_API_SECRET=…`), sin reconstruir. Las claves bajo `runtimeConfig.public` llegan al cliente; el resto solo al servidor.

Verificación tras el build: `node .output/server/index.mjs` y `curl -I localhost:3000/` debe dar `200`; `/admin` debe devolver un HTML casi vacío (SPA) y `/products/silla` el HTML completo con el nombre del producto dentro (SSR). Si el HTML de producto llega vacío, el `routeRules` no se está aplicando a esa ruta.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "In Nuxt 3, when should I use `useState` versus Pinia? And I read that a plain `ref` at module level in a composable is dangerous on the server. Why?",
            },
            {
                "role": "assistant",
                "content": r"""Start with the danger, because it explains the rest.

**A module-level `ref` is shared by every request on the server.** Node loads the module once and keeps it alive; in SSR, all users are rendered by that same process. So this:

```ts
// composables/useCart.ts  —  WRONG on the server
const items = ref<string[]>([]); // created once per process, not per request

export function useCart() {
  return { items };
}
```

means user A's cart leaks into user B's rendered HTML, and the state never resets. It also breaks hydration: the server serializes nothing about it, and the client starts from its own empty `ref`.

`useState` exists to solve exactly this. It creates state **per request** on the server, serializes it into the page payload, and rehydrates it on the client with the same key:

```ts
// composables/useCart.ts
export function useCart() {
  const items = useState<string[]>("cart-items", () => []); // keyed, per-request, SSR-safe
  const count = computed(() => items.value.length);
  function add(sku: string) {
    items.value.push(sku);
  }
  return { items, count, add };
}
```

Any component calling `useCart()` gets the same `items` for that request/page, and after hydration the client continues with the server's value.

**`useState` vs Pinia:**

| | `useState` | Pinia (`@pinia/nuxt`) |
|---|---|---|
| SSR-safe, hydrated | yes | yes (the module handles it) |
| Shape | a single reactive value per key | store with state, getters, actions |
| Devtools | basic (payload) | full time-travel, action log |
| Plugins (persistence, undo) | write your own | ecosystem (`pinia-plugin-persistedstate`) |
| Testing | call the composable | `setActivePinia(createPinia())`, actions mockable |
| Good for | a few shared values: theme, locale, current user, a flag between pages | domain state with logic: cart with totals and rules, drafts, multi-step flows |

Rule of thumb: start with `useState`; move to Pinia when the composable grows actions that enforce rules or when you want devtools and persistence without hand-rolling them. Both can coexist, and neither should hold **server data** that belongs to `useFetch`/`useAsyncData`, which already cache and hydrate by key.

Two more SSR traps in the same family:

1. **Cookies are the only state that survives across requests on the server side.** For a locale or theme that must be right on first paint, `useCookie("locale")` is the source of truth; `useState` alone starts fresh on every full page load.
2. **`localStorage` does not exist during SSR.** Read it inside `onMounted` or guard with `import.meta.client`, and expect a hydration mismatch if the server rendered a different default.

A quick way to check you are not leaking: open the site in two browsers with different carts and run `curl` against a product page. The HTML's `__NUXT_DATA__` payload must not contain either cart, since `useState` is only populated by what *this* request computed.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy aprendiendo Svelte 5. ¿Cómo funcionan `$state`, `$derived` y `$effect`? Hice un contador con el doble calculado en un `$effect` y me dijeron que está mal, pero funciona.",
            },
            {
                "role": "assistant",
                "content": r"""Funciona, pero `$effect` es la herramienta equivocada para un valor derivado, igual que lo sería un `watch` en Vue o un `useEffect` en React. Las tres runas tienen papeles distintos:

- **`$state`**: estado que cambia. Svelte sigue sus lecturas y escrituras.
- **`$derived`**: un valor **calculado** a partir de otros. Se recalcula solo cuando cambian sus dependencias, síncronamente y sin efectos secundarios.
- **`$effect`**: código que debe ejecutarse **como consecuencia** de un cambio y que afecta a algo externo: el DOM manual, `localStorage`, un `fetch`, una librería de gráficos.

```svelte
<script lang="ts">
  let count = $state(0);
  let double = $derived(count * 2);           // valor derivado: así se hace
  let parity = $derived(count % 2 === 0 ? "par" : "impar");

  $effect(() => {
    // efecto legítimo: sincronizar con algo fuera de Svelte
    document.title = `Contador: ${count}`;
  });
</script>

<button onclick={() => count++}>+1</button>
<p>{count} × 2 = {double} ({parity})</p>
```

Lo que hacía tu versión con `$effect`:

```svelte
let count = $state(0);
let double = $state(0);
$effect(() => { double = count * 2; });
```

Tres problemas, aunque pinte lo mismo:

1. **Dos fuentes de verdad.** `double` es estado que alguien puede escribir por su cuenta y desincronizar.
2. **Un tick de retraso.** `$effect` corre después de que Svelte haya actualizado el DOM; durante ese instante `double` tiene el valor viejo. Con `$derived` no existe ese instante.
3. **Orden y bucles.** Un efecto que escribe estado que otro efecto lee crea dependencias difíciles de seguir, y si se lee y escribe lo mismo, Svelte lanza `effect_update_depth_exceeded`.

Para cálculos de varias líneas, `$derived.by`:

```svelte
let total = $derived.by(() => {
  let sum = 0;
  for (const item of items) sum += item.price * item.qty;
  return sum;
});
```

Detalles de `$effect` que conviene saber desde el principio:

- Las dependencias son **lo que lees síncronamente** dentro. Lo que leas tras un `await` no se sigue.
- Devuelve una función para limpiar (intervalos, listeners); se ejecuta antes de la siguiente ejecución y al destruir el componente.
- Corre solo en el navegador, nunca en SSR.

Regla rápida: si lo que quieres es **un valor**, `$derived`. Si lo que quieres es **que pase algo**, `$effect`. Si estás asignando una variable dentro de un `$effect`, casi seguro era un `$derived`.""",
            },
            {
                "role": "user",
                "content": "Entendido. Y para guardar el contador en localStorage y recuperarlo al abrir la página, ¿ahí sí es un $effect?",
            },
            {
                "role": "assistant",
                "content": r"""Sí: escribir en `localStorage` es un efecto secundario sobre algo externo, exactamente el caso de `$effect`. La lectura inicial, en cambio, no es un efecto: es el valor con el que arranca el estado.

```svelte
<script lang="ts">
  const KEY = "counter";

  function readInitial(): number {
    if (typeof localStorage === "undefined") return 0; // SSR: no hay localStorage
    const raw = localStorage.getItem(KEY);
    const n = Number(raw);
    return raw !== null && Number.isFinite(n) ? n : 0;
  }

  let count = $state(readInitial());

  $effect(() => {
    localStorage.setItem(KEY, String(count)); // se ejecuta al montar y cada vez que cambia `count`
  });
</script>

<button onclick={() => count++}>+1</button>
<p>{count}</p>
```

Por qué así:

- **La lectura va en la inicialización de `$state`**, no en un efecto. Un `$effect` que hiciera `count = Number(localStorage.getItem(KEY))` provocaría un primer render con `0` y luego otro con el valor guardado: un parpadeo, además de un efecto que escribe el mismo estado que luego otro efecto lee.
- **`$effect` lee `count`** al construir el string, así que queda suscrito y se re-ejecuta en cada cambio. No hay lista de dependencias: la lectura es la suscripción.
- **El guard de `localStorage`** importa en SvelteKit, donde el script puede ejecutarse en el servidor. `$effect` nunca corre en SSR, así que la escritura no necesita el guard, pero la función de lectura sí.

Para reutilizarlo en varios componentes, conviértelo en una clase con estado reactivo (el patrón idiomático de Svelte 5 para «estado con comportamiento»):

```ts
// lib/persisted.svelte.ts   (la extensión .svelte.ts habilita las runas fuera de componentes)
export class Persisted<T> {
  value = $state() as T;

  constructor(private key: string, initial: T) {
    this.value = this.read() ?? initial;
    $effect.root(() => {
      $effect(() => {
        localStorage.setItem(this.key, JSON.stringify(this.value));
      });
    });
  }

  private read(): T | null {
    if (typeof localStorage === "undefined") return null;
    try {
      const raw = localStorage.getItem(this.key);
      return raw === null ? null : (JSON.parse(raw) as T);
    } catch {
      return null;
    }
  }
}
```

```svelte
<script lang="ts">
  import { Persisted } from "$lib/persisted.svelte";
  const counter = new Persisted("counter", 0);
</script>

<button onclick={() => counter.value++}>+1</button>
<p>{counter.value}</p>
```

`$effect.root` crea un ámbito para efectos fuera del ciclo de vida de un componente; si la instancia vive lo que la app, no hace falta destruirlo. Si la creas por componente, guarda lo que devuelve `$effect.root` (una función de limpieza) y llámala al destruir.

Verificación: pulsa tres veces, recarga: el contador muestra 3 sin pasar por 0. En Application → Local Storage, la clave `counter` vale `3`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En Svelte 5, ¿cómo declaro las props de un componente `Button` con TypeScript, con un valor por defecto, una prop enlazable con `bind:` y contenido hijo? Vengo de `export let` y `<slot>` y me dicen que eso ya no se usa.",
            },
            {
                "role": "assistant",
                "content": r"""En Svelte 5 las props se declaran con la runa `$props()` y el contenido hijo llega como un **snippet** llamado `children`, que se renderiza con `{@render}`. `export let` y `<slot>` siguen funcionando en modo legado, pero el código nuevo usa esto:

```svelte
<!-- Button.svelte -->
<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes } from "svelte/elements";

  type Props = HTMLButtonAttributes & {
    variant?: "primary" | "ghost";
    loading?: boolean;
    pressed?: boolean;          // enlazable con bind:pressed
    children: Snippet;          // contenido entre las etiquetas
    icon?: Snippet<[size: number]>; // snippet con parámetro
  };

  let {
    variant = "primary",
    loading = false,
    pressed = $bindable(false),
    children,
    icon,
    ...rest
  }: Props = $props();
</script>

<button
  {...rest}
  class="btn btn--{variant}"
  disabled={loading || rest.disabled}
  aria-pressed={pressed}
  onclick={(e) => {
    pressed = !pressed;
    rest.onclick?.(e);
  }}
>
  {#if icon}
    {@render icon(16)}
  {/if}
  {#if loading}
    Cargando…
  {:else}
    {@render children()}
  {/if}
</button>
```

Uso:

```svelte
<script lang="ts">
  import Button from "./Button.svelte";
  let active = $state(false);
</script>

<Button variant="ghost" bind:pressed={active} type="button">
  {#snippet icon(size)}
    <svg width={size} height={size}><circle r={size / 2} cx={size / 2} cy={size / 2} /></svg>
  {/snippet}
  Favorito
</Button>

<p>Activo: {active}</p>
```

Qué hace cada pieza:

- **`let { … }: Props = $props()`**: la desestructuración declara las props; el valor por defecto va en la desestructuración (`variant = "primary"`). Las props son reactivas: si el padre cambia `loading`, el botón lo ve.
- **`$bindable(false)`** marca `pressed` como enlazable. Sin ello, `bind:pressed` en el padre es un error de compilación: Svelte 5 exige declarar qué props pueden fluir hacia arriba, para que el flujo de datos sea explícito.
- **`children: Snippet`**: el contenido entre `<Button>` y `</Button>` llega como snippet implícito. `{@render children()}` lo pinta. Si el contenido es opcional, `children?: Snippet` y `{@render children?.()}`.
- **Snippets con nombre y parámetros** (`icon`): sustituyen a los slots con nombre y a los *scoped slots*. `Snippet<[size: number]>` tipa el argumento; el padre lo define con `{#snippet icon(size)}` dentro del componente.
- **`HTMLButtonAttributes & {...}` + `{...rest}`**: cualquier atributo nativo (`type`, `aria-label`, `disabled`, `onclick`) pasa al `<button>` tipado. Como `onclick` es una prop más en Svelte 5 (no una directiva `on:`), lo intercepto para alternar `pressed` y luego lo reenvío.

Equivalencias para la cabeza que viene de Svelte 4:

| Svelte 4 | Svelte 5 |
|---|---|
| `export let variant = "primary"` | `let { variant = "primary" } = $props()` |
| `<slot />` | `{@render children()}` |
| `<slot name="icon" {size} />` | `{@render icon(size)}` con `icon?: Snippet<[number]>` |
| `on:click` / `createEventDispatcher` | prop `onclick` (callback) |
| `$$restProps` | `...rest` en la desestructuración |
| `bind:value` sin declarar nada | `value = $bindable()` |

Verificación: `npx svelte-check` sin errores; pasar `variant="danger"` debe fallar en el tipo; `bind:pressed` con `active` cambia al pulsar y `aria-pressed` refleja el valor en el DOM.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo este componente de Svelte 4 y quiero pasarlo a Svelte 5 con runas. ¿Qué cambia?

```svelte
<script>
  import { createEventDispatcher, onMount } from "svelte";
  export let items = [];
  export let filter = "";
  const dispatch = createEventDispatcher();

  $: visible = items.filter((i) => i.name.includes(filter));
  $: if (visible.length === 0) dispatch("empty");

  onMount(() => {
    const id = setInterval(() => dispatch("tick"), 1000);
    return () => clearInterval(id);
  });
</script>

<input bind:value={filter} />
{#each visible as item (item.id)}
  <div on:click={() => dispatch("select", item)}>{item.name}</div>
{/each}
<slot />
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cambian cuatro cosas: las props (`export let` → `$props`), los reactivos `$:` (→ `$derived` o `$effect` según el caso), los eventos (`createEventDispatcher` → props callback) y el slot (→ snippet). El resultado:

```svelte
<script lang="ts">
  import type { Snippet } from "svelte";

  type Item = { id: string; name: string };

  let {
    items = [],
    filter = $bindable(""),
    onselect,
    onempty,
    ontick,
    children,
  }: {
    items?: Item[];
    filter?: string;
    onselect?: (item: Item) => void;
    onempty?: () => void;
    ontick?: () => void;
    children?: Snippet;
  } = $props();

  // `$: visible = …` era un valor derivado → $derived
  let visible = $derived(items.filter((i) => i.name.includes(filter)));

  // `$: if (…) dispatch(…)` era un efecto → $effect
  $effect(() => {
    if (visible.length === 0) onempty?.();
  });

  // onMount con limpieza → $effect con función de retorno
  $effect(() => {
    const id = setInterval(() => ontick?.(), 1000);
    return () => clearInterval(id);
  });
</script>

<input bind:value={filter} />
{#each visible as item (item.id)}
  <div onclick={() => onselect?.(item)}>{item.name}</div>
{/each}
{@render children?.()}
```

Y el padre, que antes hacía `on:select={…}`, ahora pasa callbacks como cualquier prop:

```svelte
<List {items} bind:filter onselect={(item) => (selected = item)} onempty={() => console.log("vacío")} />
```

Las decisiones, una por una:

- **`filter = $bindable("")`**: en Svelte 4 cualquier prop se podía enlazar con `bind:`; en 5 hay que declararlo. Como el padre hacía `bind:filter`, se marca; `items` no se enlaza, así que no.
- **`$: visible = …` → `$derived`**: era un cálculo. **`$: if (…) dispatch(…)` → `$effect`**: era una acción. Esta distinción es la que `$:` ocultaba y la que más errores de migración produce: no conviertas todos los `$:` a `$effect`.
- **`createEventDispatcher` desaparece** (está deprecado en 5). Los eventos son props con nombre `onalgo`; el padre los pasa como funciones. Ventajas: tipados, sin `CustomEvent` con `detail`, y se ven en la firma del componente.
- **`onMount` sigue existiendo** y es válido; lo convierto a `$effect` por coherencia y porque, si el intervalo dependiera de una prop (`interval`), `$effect` se reiniciaría solo al cambiar y `onMount` no.
- **`on:click` → `onclick`**: en 5 los eventos del DOM son atributos. Sin los dos puntos.
- **`<slot />` → `{@render children?.()}`**, con `children?: Snippet` en las props. El `?.()` cubre que el padre no pase contenido.

Un cambio de semántica que debes revisar en el resto del código: en Svelte 5 el estado es **profundamente reactivo** (`items.push(x)` sobre un `$state` actualiza la vista; en 4 había que reasignar `items = items`). Las reasignaciones «forzadas» de Svelte 4 se pueden borrar.

Para una base de código grande, no migres a mano: `npx sv migrate svelte-5` convierte `export let`, `$:`, `on:` y slots en la mayoría de los casos, y deja comentarios `@migration-task` donde no pudo decidir (sobre todo en los `$:` ambiguos entre derivado y efecto). Revísalos uno a uno con la regla de arriba: ¿valor o acción?

Verificación: con el mismo padre adaptado a callbacks, escribe en el filtro hasta que no haya coincidencias: `onempty` se dispara una vez; vuelve a escribir algo válido y la lista reaparece; `ontick` llega cada segundo y deja de llegar al desmontar el componente (comprueba que no hay logs tras navegar fuera).""",
            },
        ]
    },
    # -----------------------------------------------------------------------
    # 21-25 SvelteKit load (+page.ts vs +page.server.ts, streaming), form actions (multiturno),
    #       snippets genéricos (rioplatense), estado compartido en .svelte.ts (error), carreras en $effect (EN)
    # -----------------------------------------------------------------------
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En SvelteKit no termino de entender cuándo usar `+page.ts` y cuándo `+page.server.ts`. Tengo una página de producto: el producto sale de mi base de datos (Prisma) y las reseñas de una API externa que es lenta, a veces 2-3 s. ¿Dónde va cada cosa y cómo le llegan los datos al componente en Svelte 5?",
            },
            {
                "role": "assistant",
                "content": r"""Las dos cosas van en `+page.server.ts`: el producto porque toca la base de datos, y las reseñas porque así puedes **transmitirlas en streaming** sin bloquear la página y sin exponer la API externa ni su clave al navegador.

La diferencia entre los dos archivos es dónde se ejecuta `load`:

| | `+page.server.ts` | `+page.ts` (universal) |
|---|---|---|
| Dónde corre | Solo en el servidor | En el servidor (SSR) y en el navegador (navegación en cliente) |
| Puede usar | BD, secretos (`$env/static/private`), cookies | Solo lo que también existe en el navegador |
| Qué puede devolver | Datos serializables (devalue: objetos, arrays, `Date`, `Map`, `Set`, `BigInt`) | Cualquier cosa, incluso componentes o instancias de clase |
| En navegación en cliente | El navegador pide `__data.json` a tu servidor | El navegador ejecuta `load` y llama a la API directamente |

Regla: si toca algo privado, `+page.server.ts`. `+page.ts` compensa cuando la API es pública, admite CORS y quieres ahorrarte el salto por tu servidor, o cuando necesitas devolver algo no serializable.

```ts
// src/routes/products/[id]/+page.server.ts
import { error } from "@sveltejs/kit";
import { REVIEWS_API_URL } from "$env/static/private";
import { db } from "$lib/server/db";
import type { PageServerLoad } from "./$types";

export type Review = { id: string; rating: number; text: string };

async function fetchReviews(fetchFn: typeof fetch, productId: string): Promise<Review[]> {
  const res = await fetchFn(`${REVIEWS_API_URL}/reviews?product=${encodeURIComponent(productId)}`);
  if (!res.ok) throw new Error(`reviews API: HTTP ${res.status}`);
  return (await res.json()) as Review[];
}

export const load: PageServerLoad = async ({ params, fetch }) => {
  // Crítico: sin producto no hay página, así que se espera
  const product = await db.product.findUnique({
    where: { id: params.id },
    select: { id: true, name: true, priceCents: true, description: true },
  });
  if (!product) error(404, "Producto no encontrado");

  // Secundario y lento: NO se espera. SvelteKit envía el HTML y transmite la promesa al resolverse
  const reviews = fetchReviews(fetch, product.id).catch(() => [] as Review[]);

  return { product, reviews };
};
```

```svelte
<!-- src/routes/products/[id]/+page.svelte -->
<script lang="ts">
  import type { PageProps } from "./$types";

  let { data }: PageProps = $props();

  const price = new Intl.NumberFormat("es", { style: "currency", currency: "EUR" });
</script>

<h1>{data.product.name}</h1>
<p>{price.format(data.product.priceCents / 100)}</p>
<p>{data.product.description}</p>

<h2>Reseñas</h2>
{#await data.reviews}
  <p>Cargando reseñas…</p>
{:then reviews}
  {#each reviews as review (review.id)}
    <article>★ {review.rating} · {review.text}</article>
  {:else}
    <p>Todavía no hay reseñas.</p>
  {/each}
{/await}
```

Por qué cada decisión:

- **`select` explícito.** Lo que devuelve `load` acaba serializado dentro del HTML. Devolver la fila entera filtra columnas internas. Además, un `Decimal` de Prisma no lo serializa devalue; por eso el precio va en céntimos enteros.
- **`error(404, …)` sin `throw`.** En SvelteKit 2, `error()` y `redirect()` lanzan por sí mismas.
- **`.catch(() => [])` en la promesa transmitida.** Si la API falla antes de que empiece el render, una promesa rechazada sin manejar puede tumbar el proceso de Node. El `catch` la marca como manejada y degrada a «sin reseñas», que para datos secundarios es lo razonable. Si prefieres mostrar el error, devuelve `reviews` sin transformar, añade aparte `reviews.catch(() => {})` para marcarla como manejada y usa `{:catch}` en el `{#await}`.
- **El `fetch` del evento, no el global.** Reenvía cookies a tu propio dominio y resuelve rutas relativas en SSR.
- **`$lib/server/`.** SvelteKit prohíbe importar ese directorio desde código de cliente: si alguien importa `db` en un componente, el build falla en lugar de filtrar credenciales.
- **`PageProps`** existe desde SvelteKit 2.16. En versiones anteriores: `let { data }: { data: PageData } = $props()`.

El trade-off del streaming: las reseñas no estarán en el HTML inicial, así que no cuentan para SEO y sin JavaScript no aparecen. Si las necesitas indexadas, haz `await` y paga los 2-3 s, o cachea la respuesta de la API.

`load` se vuelve a ejecutar sola cuando cambia lo que lee (aquí `params.id`); para forzarlo tienes `invalidate`/`invalidateAll`.

Verificación:

1. Simula la lentitud (un `await new Promise((r) => setTimeout(r, 3000))` temporal en `fetchReviews`): el título aparece al instante y «Cargando reseñas…» dura 3 s.
2. Ver código fuente (Ctrl+U): el nombre del producto está en el HTML.
3. Navega a otro producto desde un enlace: en Network verás una petición a `__data.json` y ninguna a la API de reseñas desde el navegador.
4. `/products/no-existe` responde 404.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero hacer un formulario de suscripción al newsletter en SvelteKit que funcione aunque no cargue el JS, que valide el email en el servidor y que, si hay error, lo muestre junto al campo sin borrar lo que escribió la persona. ¿Cómo se hace con form actions? Uso Prisma.",
            },
            {
                "role": "assistant",
                "content": r"""Con una acción en `+page.server.ts` que devuelve `fail()` en los errores y `redirect(303)` en el éxito. El `<form method="POST">` nativo hace el resto: sin JS es un POST normal y SvelteKit vuelve a renderizar la página con lo que devolviste.

```ts
// src/routes/newsletter/+page.server.ts
import { fail, redirect } from "@sveltejs/kit";
import { Prisma } from "@prisma/client";
import { db } from "$lib/server/db";
import type { Actions } from "./$types";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const actions = {
  default: async ({ request }) => {
    const formData = await request.formData();
    const email = String(formData.get("email") ?? "").trim().toLowerCase();

    if (!EMAIL_RE.test(email)) {
      return fail(400, { email, error: "Escribe un email válido." });
    }

    try {
      await db.subscriber.create({ data: { email } });
    } catch (err) {
      // La restricción UNIQUE es la fuente de verdad: sin carrera entre «comprobar» y «crear»
      if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2002") {
        return fail(409, { email, error: "Ese email ya está suscrito." });
      }
      throw err; // inesperado: que llegue a handleError y responda 500
    }

    redirect(303, "/newsletter/gracias");
  },
} satisfies Actions;
```

```svelte
<!-- src/routes/newsletter/+page.svelte -->
<script lang="ts">
  import type { PageProps } from "./$types";

  let { form }: PageProps = $props();
</script>

<form method="POST">
  <label for="email">Email</label>
  <input
    id="email"
    name="email"
    type="email"
    autocomplete="email"
    required
    value={form?.email ?? ""}
    aria-invalid={form?.error ? "true" : undefined}
    aria-describedby={form?.error ? "email-error" : undefined}
  />
  {#if form?.error}
    <p id="email-error" role="alert">{form.error}</p>
  {/if}
  <button>Suscribirme</button>
</form>
```

Cómo encaja:

- **`fail(status, data)`** responde con el código HTTP correcto (400, 409) y `data` llega al componente como la prop `form`. Por eso devuelvo `email`: es lo que repuebla el campo. Nunca devuelvas así una contraseña.
- **`redirect(303)`** aplica POST/Redirect/GET: si la persona recarga la página de gracias, no se reenvía el formulario. El 303 fuerza que la siguiente petición sea GET.
- **El duplicado se detecta con la restricción UNIQUE** (`P2002`), no con un `findUnique` previo: dos envíos simultáneos pasarían ambos la comprobación y uno fallaría igual al insertar.
- **`required` y `type="email"`** son comodidad para el usuario; la validación que cuenta es la del servidor, porque cualquiera puede hacer un POST a mano.
- **`satisfies Actions`** tipa `request` y deja que `PageProps` infiera la forma de `form`.

Verificación sin navegador (la cabecera `Origin` hace falta porque SvelteKit rechaza POST de formularios de otro origen):

```bash
curl -i -X POST http://localhost:5173/newsletter \
  -H "Origin: http://localhost:5173" -d "email=no-es-un-email"
# HTTP/1.1 400 y el HTML del formulario con «Escribe un email válido.»
```

Y en el navegador, desactiva JavaScript en DevTools: el envío válido redirige a `/newsletter/gracias`, y repetir el mismo email muestra el 409 con el campo relleno.""",
            },
            {
                "role": "user",
                "content": r"""Funciona. Le puse `use:enhance` y ahora quiero deshabilitar el botón mientras envía. Y otra cosa: envolví toda la acción en un try/catch para devolver un error bonito y desde entonces nunca redirige, siempre sale «Error inesperado»:

```ts
default: async ({ request }) => {
  try {
    const formData = await request.formData();
    const email = String(formData.get("email") ?? "").trim().toLowerCase();
    if (!EMAIL_RE.test(email)) return fail(400, { email, error: "Escribe un email válido." });
    await db.subscriber.create({ data: { email } });
    redirect(303, "/newsletter/gracias");
  } catch (err) {
    console.error(err);
    return fail(500, { email: "", error: "Error inesperado" });
  }
},
```""",
            },
            {
                "role": "assistant",
                "content": r"""El `catch` se está comiendo la redirección. `redirect()` no devuelve nada: **lanza** un objeto `Redirect` que SvelteKit captura más arriba para responder con el 303. Tu `catch` lo atrapa antes y lo convierte en un 500. Lo mismo pasaría con `error(404, …)`.

La prueba está en tu propio log: el `console.error(err)` del servidor imprime algo como `Redirect { status: 303, location: '/newsletter/gracias' }`, no un error de Prisma.

El arreglo es volver a acotar el `try` a la única operación que puede fallar de forma esperada, como en la versión anterior. Si de verdad necesitas un `try` amplio, relanza lo que es de SvelteKit con `if (isRedirect(err)) throw err;` (`isRedirect` se importa de `@sveltejs/kit`), pero el `try` corto es más claro.

Sobre el «error bonito»: no hace falta envolver nada. Un error inesperado que se propaga llega a `handleError` en `hooks.server.ts`, que es el sitio para registrarlo, y SvelteKit muestra tu `+error.svelte` con un 500. Convertirlo en `fail(500)` además borraba el email que había escrito la persona.

Para el botón, `use:enhance` acepta una función que corre antes de enviar y puede devolver otra que corre al llegar la respuesta:

```svelte
<!-- src/routes/newsletter/+page.svelte -->
<script lang="ts">
  import { enhance } from "$app/forms";
  import type { PageProps } from "./$types";

  let { form }: PageProps = $props();
  let submitting = $state(false);
</script>

<form
  method="POST"
  use:enhance={() => {
    submitting = true;
    return async ({ update }) => {
      try {
        await update(); // comportamiento por defecto: actualiza `form`, sigue el redirect o muestra el error
      } finally {
        submitting = false;
      }
    };
  }}
>
  <label for="email">Email</label>
  <input
    id="email"
    name="email"
    type="email"
    autocomplete="email"
    required
    value={form?.email ?? ""}
    aria-invalid={form?.error ? "true" : undefined}
    aria-describedby={form?.error ? "email-error" : undefined}
  />
  {#if form?.error}
    <p id="email-error" role="alert">{form.error}</p>
  {/if}
  <button disabled={submitting}>{submitting ? "Enviando…" : "Suscribirme"}</button>
</form>
```

Detalles que importan:

- **Si devuelves el callback, tienes que llamar a `update()`** (o a `applyAction`). Sin él, `enhance` deja de aplicar el resultado y el formulario parece no hacer nada.
- **`finally`** garantiza que el botón se reactiva aunque algo falle por el camino.
- **Sin JS no cambia nada:** `use:enhance` no se ejecuta, el botón nunca se deshabilita y el formulario sigue funcionando con el POST nativo. Esa es la mejora progresiva que pedías al principio.

Verificación: en DevTools pon la red en «Slow 3G». Al enviar, el botón muestra «Enviando…» y queda deshabilitado; con un email repetido aparece el 409 sin recargar la página y el campo conserva el texto; con uno nuevo navega a `/newsletter/gracias` y en el log del servidor ya no aparece ningún `Redirect`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo y sin vueltas."},
            {
                "role": "user",
                "content": "Che, necesito un `DataTable` genérico en Svelte 5: le paso un array de filas y quiero decidir desde afuera cómo se pinta cada celda y el encabezado, con tipado de verdad. En React lo haría con render props. ¿Cómo es acá?",
            },
            {
                "role": "assistant",
                "content": r"""Acá el equivalente de las render props son los **snippets** pasados como props, y el tipado genérico lo da el atributo `generics` del `<script>`. El tipo de fila se infiere solo a partir de lo que pases en `rows`.

```svelte
<!-- src/lib/DataTable.svelte -->
<script lang="ts" module>
  // Tipos exportables desde el módulo del componente
  export type Column<T> = {
    key: keyof T & string;
    label: string;
    align?: "left" | "right";
  };
</script>

<script lang="ts" generics="T extends { id: string | number }">
  import type { Snippet } from "svelte";

  type Props = {
    rows: T[];
    columns: Column<T>[];
    cell?: Snippet<[row: T, column: Column<T>]>;
    header?: Snippet<[column: Column<T>]>;
    empty?: Snippet;
  };

  let { rows, columns, cell, header, empty }: Props = $props();
</script>

<table>
  <thead>
    <tr>
      {#each columns as column (column.key)}
        <th style:text-align={column.align ?? "left"}>
          {#if header}{@render header(column)}{:else}{column.label}{/if}
        </th>
      {/each}
    </tr>
  </thead>
  <tbody>
    {#each rows as row (row.id)}
      <tr>
        {#each columns as column (column.key)}
          <td style:text-align={column.align ?? "left"}>
            {#if cell}{@render cell(row, column)}{:else}{String(row[column.key])}{/if}
          </td>
        {/each}
      </tr>
    {:else}
      <tr>
        <td colspan={columns.length}>
          {#if empty}{@render empty()}{:else}Sin datos{/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
```

Uso:

```svelte
<script lang="ts">
  import DataTable, { type Column } from "$lib/DataTable.svelte";

  type Account = { id: number; owner: string; email: string; balance: number };

  let { accounts }: { accounts: Account[] } = $props();

  const columns: Column<Account>[] = [
    { key: "owner", label: "Titular" },
    { key: "email", label: "Email" },
    { key: "balance", label: "Saldo", align: "right" },
  ];

  const money = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
</script>

<DataTable rows={accounts} {columns}>
  {#snippet cell(account, column)}
    {#if column.key === "balance"}
      <span class:negative={account.balance < 0}>{money.format(account.balance)}</span>
    {:else if column.key === "email"}
      <a href="mailto:{account.email}">{account.email}</a>
    {:else}
      {account[column.key]}
    {/if}
  {/snippet}

  {#snippet empty()}
    No hay cuentas. <a href="/accounts/new">Creá la primera</a>.
  {/snippet}
</DataTable>

<style>
  .negative {
    color: crimson;
  }
</style>
```

Lo que tenés que saber de cada pieza:

- **Snippets declarados dentro de las etiquetas del componente se convierten en props** con ese nombre. `{#snippet cell(account, column)}` es literalmente la prop `cell`. Si preferís, lo declarás afuera y lo pasás como `cell={miSnippet}`.
- **`Snippet<[row: T, column: Column<T>]>`** tipa los parámetros. Como `T` se infiere de `rows`, dentro del snippet `account` ya es `Account` sin anotar nada, y `account.balance` autocompleta.
- **`keyof T & string` en `key`** hace que una columna mal escrita (`"saldo"`) sea error de compilación, no una celda vacía en producción.
- **`T extends { id: string | number }`** existe porque el `#each` va con clave `(row.id)`. Sin clave, al reordenar o borrar filas Svelte reutiliza nodos por posición y el estado del DOM (un input con foco, una animación) queda en la fila equivocada.
- **`<script module>`** es la sintaxis de Svelte 5 para el bloque de módulo (antes `context="module"`). Ahí exportás tipos que el padre importa junto al componente.
- **Diferencia con React:** un snippet no es un componente; no tiene instancia ni ciclo de vida. Es un fragmento de plantilla con parámetros que se pinta donde hacés `{@render}`. Más barato y sin problemas de identidad entre renders.

Verificación: corré `npx svelte-check`. Cambiá `key: "owner"` por `key: "titular"` y tiene que fallar con algo como `Type '"titular"' is not assignable to type '"id" | "owner" | "email" | "balance"'`; pasá filas sin `id` y también falla. En el navegador, con `accounts = []` se ve el snippet `empty`, y con un saldo negativo la celda sale en rojo y alineada a la derecha.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Quiero compartir el usuario logueado entre varios componentes con Svelte 5 y armé esto en `src/lib/session.svelte.ts`:

```ts
import type { User } from "$lib/types";

export let currentUser = $state<User | null>(null);

export function login(user: User) {
  currentUser = user;
}

export function logout() {
  currentUser = null;
}
```

Al compilar me sale:

```
Cannot export state from a module if it is reassigned. Either export a function returning the state value or only mutate the state value's properties
```

¿Cómo se comparte estado entonces? La app es SvelteKit con SSR.""",
            },
            {
                "role": "assistant",
                "content": r"""El compilador te está protegiendo de un bug: `currentUser` dejaría de ser reactivo en cuanto otro archivo lo importara. Y hay un segundo problema más grave que el error no menciona: con SSR, un estado de módulo con el usuario logueado se comparte entre **todas las peticiones** del servidor.

**Por qué el error (código `state_invalid_export`).** `$state` no es una variable normal: en ese archivo, el compilador reescribe cada lectura y escritura de `currentUser` como accesos a una señal. Pero el archivo que hace `import { currentUser }` se compila por separado y recibe el enlace pelado, sin esa reescritura. Si el valor se **reasigna**, el importador nunca se entera. Si solo **mutas propiedades** de un objeto que nunca se reasigna, sí funciona, porque la reactividad vive en el propio objeto.

**Arreglo para estado de cliente: exportar una instancia que se muta, no un valor que se reasigna.**

```ts
// src/lib/ui-state.svelte.ts
class UiState {
  sidebarOpen = $state(false);
  theme = $state<"light" | "dark">("light");
  isDark = $derived(this.theme === "dark");

  // Funciones flecha: siguen funcionando si se pasan sueltas, p. ej. onclick={ui.toggleSidebar}
  toggleSidebar = () => {
    this.sidebarOpen = !this.sidebarOpen;
  };
}

export const ui = new UiState();
```

```svelte
<script lang="ts">
  import { ui } from "$lib/ui-state.svelte";
</script>

<button onclick={ui.toggleSidebar}>Menú</button>
{#if ui.sidebarOpen}<nav><a href="/">Inicio</a> <a href="/settings">Ajustes</a></nav>{/if}
```

`ui` nunca se reasigna; sus campos `$state` se compilan como getters/setters sobre señales, así que cualquier componente que lea `ui.sidebarOpen` se actualiza. Dos trampas: `const { sidebarOpen } = ui` lee el valor una vez y pierde la reactividad, y un método normal pasado como `onclick={ui.metodo}` pierde el `this` (por eso uso funciones flecha).

**Por qué no lo usaría para la sesión en SvelteKit.** Un módulo se evalúa una vez por proceso de Node. Si durante el SSR algo llama a `login(user)`, la petición siguiente, de otra persona, puede renderizarse con ese usuario. La sesión tiene que ser por petición, y SvelteKit ya trae el canal:

```ts
// src/app.d.ts
declare global {
  namespace App {
    interface Locals {
      user: { id: string; name: string } | null;
    }
  }
}
export {};
```

```ts
// src/hooks.server.ts
import type { Handle } from "@sveltejs/kit";
import { findUserBySession } from "$lib/server/auth";

export const handle: Handle = async ({ event, resolve }) => {
  const sessionId = event.cookies.get("session");
  event.locals.user = sessionId ? await findUserBySession(sessionId) : null;
  return resolve(event);
};
```

```ts
// src/routes/+layout.server.ts
import type { LayoutServerLoad } from "./$types";

export const load: LayoutServerLoad = ({ locals }) => ({ user: locals.user });
```

```svelte
<!-- cualquier componente -->
<script lang="ts">
  import { page } from "$app/state";
</script>

{#if page.data.user}
  <span>Hola, {page.data.user.name}</span>
  <form method="POST" action="/logout"><button>Salir</button></form>
{:else}
  <a href="/login">Entrar</a>
{/if}
```

(`findUserBySession` es tu función de `$lib/server/auth` que valida la cookie contra la base de datos.) `page` de `$app/state` existe desde SvelteKit 2.12; antes era `$page` de `$app/stores`. Login y logout pasan a ser form actions que escriben o borran la cookie y redirigen; tras el redirect, el layout vuelve a cargar y `page.data.user` cambia en toda la app.

Reparto final: **estado por usuario** → `locals` y `data` (viaja por petición). **Estado puro de interfaz** que solo se escribe en el navegador → instancia exportada de un `.svelte.ts`.

Verificación: el error de compilación desaparece. Para la fuga, abre la app en una ventana normal y otra de incógnito con usuarios distintos y recarga alternando: cada una debe mostrar su nombre. Con la versión de módulo escrita durante SSR, esa prueba es justo la que la delata.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Svelte 5 question. I have a search box that fetches results inside an `$effect` whenever `query` changes. When I type fast, the list sometimes shows results for an older query: a slow response arrives last and overwrites the newer one.

```svelte
<script lang="ts">
  let query = $state("");
  let results = $state<string[]>([]);

  $effect(() => {
    fetch(`/api/search?q=${query}`)
      .then((r) => r.json())
      .then((data) => (results = data));
  });
</script>

<input bind:value={query} />
<ul>{#each results as r}<li>{r}</li>{/each}</ul>
```

What's the proper fix?""",
            },
            {
                "role": "assistant",
                "content": r"""It's a race: every keystroke starts a request, nothing cancels the previous ones, and whichever response resolves last wins. The fix is to make each effect run own its request and cancel it when it's superseded. Svelte calls the teardown function returned from `$effect` right before the next run (and on unmount), which is exactly the hook you need.

```svelte
<script lang="ts">
  const DEBOUNCE_MS = 250;
  const MIN_LENGTH = 2;

  let query = $state("");
  let results = $state<string[]>([]);
  let status = $state<"idle" | "loading" | "error">("idle");

  $effect(() => {
    const q = query.trim(); // read synchronously: this is the effect's only dependency
    if (q.length < MIN_LENGTH) {
      results = [];
      status = "idle";
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      status = "loading";
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`, {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        results = (await res.json()) as string[];
        status = "idle";
      } catch (err) {
        if (controller.signal.aborted) return; // superseded by a newer query: not an error
        console.error(err);
        status = "error";
      }
    }, DEBOUNCE_MS);

    // Runs before the next execution and on unmount
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  });
</script>

<input bind:value={query} placeholder="Search…" />
{#if status === "loading"}<p>Searching…</p>{/if}
{#if status === "error"}<p role="alert">Search failed. Try again.</p>{/if}
<ul>
  {#each results as result (result)}
    <li>{result}</li>
  {/each}
</ul>
```

What each piece does, and why:

- **Abort in the teardown is the actual fix.** When `query` changes, the previous run's controller is aborted, its `fetch` (or its pending `res.json()`) rejects with an `AbortError`, and it never reaches `results = …`. Only the latest run can write.
- **The debounce is an optimization, not the fix.** It cuts requests from one per keystroke to one per pause. On its own it still races: a slow response from a pause two seconds ago can land after a fast one.
- **`controller.signal.aborted` in the `catch`** separates "cancelled on purpose" from "the server failed", so the error banner doesn't flash while the user types.
- **Dependency tracking.** `$effect` tracks what it reads synchronously. `query` is read at the top; everything inside `setTimeout` runs later and isn't tracked, which is what we want. The effect writes `results` and `status` but never reads them, so there's no `effect_update_depth_exceeded` loop.
- **`encodeURIComponent`** fixes a second bug in the original: a query containing `&` or `#` would have produced a different URL.
- **Keyed `#each`** uses the string itself as the key; if results can repeat, return objects with an id and key by that.

If this lives in SvelteKit and the search should be shareable, there's a design alternative: put the query in the URL (`?q=`), call `goto` with `{ keepFocus: true, replaceState: true, noScroll: true }` after the debounce, and fetch in `load`. SvelteKit drops stale navigations for you and the back button works. The cost is a navigation per search and more moving parts; for a simple widget the effect above is enough.

Verification that doesn't depend on luck: make the dev endpoint slower for shorter queries (for example, sleep `1000 / q.length` ms). With the original code, typing "svelte" ends with results for "sv". With the fix, DevTools → Network shows the earlier requests as `(canceled)` and the list always matches the input.""",
            },
        ]
    },
    # -----------------------------------------------------------------------
    # 26-30 SolidJS 1.9: props desestructuradas (error), createEffect/createMemo/on (multiturno),
    #       createResource + Suspense, For/Index y stores (EN), comparativa de reactividad (multiturno)
    # -----------------------------------------------------------------------
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Empecé con SolidJS viniendo de React y este componente no se actualiza cuando cambia `count` en el padre. Tampoco el `doubled`. Y el `console.log` solo sale una vez. ¿Me ayudas a ver qué está mal?

```tsx
import { createSignal } from "solid-js";

function Counter({ count, label }: { count: number; label: string }) {
  const doubled = count * 2;
  console.log("render");
  return <p>{label}: {count} (doble: {doubled})</p>;
}

export default function App() {
  const [count, setCount] = createSignal(0);
  return (
    <>
      <button onClick={() => setCount(count() + 1)}>+1</button>
      <Counter count={count()} label="Clics" />
    </>
  );
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""El fallo está en la primera línea del componente: **desestructurar las props**. En Solid eso lee el valor una sola vez y se queda con un número fijo. El `console.log` que sale una vez no es un síntoma: es el comportamiento normal de Solid.

**El modelo, en dos frases.** En React el componente es una función que se vuelve a ejecutar en cada render. En Solid el componente se ejecuta **una sola vez** para montar el DOM; lo que se actualiza después son las expresiones concretas del JSX que leen señales.

Para que eso funcione, el compilador convierte cada prop dinámica en un getter. `<Counter count={count()} />` se compila, aproximadamente, a:

```ts
createComponent(Counter, {
  get count() { return count(); }, // se evalúa cada vez que alguien lee props.count
  label: "Clics",
});
```

Y `{props.count}` dentro del JSX se convierte en un efecto pequeño que vuelve a leer `props.count` cuando la señal cambia. Al desestructurar en la firma (`{ count }`), invocas el getter una vez durante el montaje y guardas un `0` para siempre. `const doubled = count * 2` tiene el mismo problema: es un número calculado una vez, no una expresión viva.

Versión corregida:

```tsx
import { createEffect, createSignal, mergeProps } from "solid-js";

type CounterProps = { count: number; label?: string };

function Counter(props: CounterProps) {
  // Valores por defecto sin romper la reactividad: nada de desestructurar
  const merged = mergeProps({ label: "Total" }, props);

  // Derivado barato: una función; se reevalúa allí donde se lee
  const doubled = () => merged.count * 2;

  console.log("setup"); // una sola vez: el componente no se vuelve a ejecutar
  createEffect(() => console.log("count cambió a", merged.count)); // esto sí, en cada cambio

  return (
    <p>
      {merged.label}: {merged.count} (doble: {doubled()})
    </p>
  );
}

export default function App() {
  const [count, setCount] = createSignal(0);
  return (
    <>
      <button onClick={() => setCount((c) => c + 1)}>+1</button>
      <Counter count={count()} label="Clics" />
    </>
  );
}
```

Las reglas que se desprenden:

1. **Accede a `props.x` y a `signal()` donde los usas** (en el JSX o dentro de una función, memo o efecto), nunca en una variable suelta del cuerpo del componente.
2. **Valores por defecto con `mergeProps`**, no con `= "Total"` en la desestructuración.
3. **Separar props con `splitProps`** cuando quieras reenviar el resto a un elemento: `const [local, rest] = splitProps(props, ["count", "label"])` y luego `<p {...rest}>`. Las dos partes conservan los getters.
4. **`createMemo` en vez de una función** cuando el derivado es caro o se lee en muchos sitios: `const doubled = createMemo(() => merged.count * 2)` lo calcula una vez por cambio y lo cachea.

Para no volver a caer, instala `eslint-plugin-solid`: sus reglas `solid/no-destructure` y `solid/reactivity` marcan exactamente estos dos errores.

Verificación: pulsa +1 tres veces. El párrafo muestra `Clics: 3 (doble: 6)`, `setup` aparece una sola vez en la consola y `count cambió a` aparece cuatro (el valor inicial y tres cambios). Esa diferencia entre los dos logs es la prueba de que la reactividad vive en las expresiones, no en volver a ejecutar el componente.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Responde en español. Sé conciso: prioriza el código y una explicación breve del porqué."},
            {
                "role": "user",
                "content": "En SolidJS, ¿qué diferencia hay entre `createEffect` y `createMemo`? ¿Y por qué no llevan array de dependencias como `useEffect`?",
            },
            {
                "role": "assistant",
                "content": r"""- **`createMemo`**: un **valor derivado**. Puro, síncrono y cacheado. Devuelve un accessor que se lee como una señal y solo avisa a quien lo lee si el resultado cambió (comparación `===`).
- **`createEffect`**: un **efecto secundario** hacia fuera de Solid (título del documento, `localStorage`, una librería de gráficos, logging). No devuelve nada útil. Corre tras el montaje inicial y en cada cambio de lo que leyó.

No hay array de dependencias porque el seguimiento es automático y **dinámico**: las dependencias son las señales leídas durante la última ejecución. Si una rama no se ejecuta, lo que hay dentro no es dependencia.

```tsx
import { createEffect, createMemo, createSignal, For, onCleanup } from "solid-js";

type Product = { id: string; name: string };

export function ProductSearch(props: { products: Product[] }) {
  const [query, setQuery] = createSignal("");
  const [autoRefresh, setAutoRefresh] = createSignal(false);

  // Valor derivado: memo, no efecto que escribe otra señal
  const visible = createMemo(() => {
    const q = query().toLowerCase();
    return props.products.filter((p) => p.name.toLowerCase().includes(q));
  });

  // Efecto: sincronizar con algo externo
  createEffect(() => {
    document.title = `${visible().length} resultados`;
  });

  // Dependencias dinámicas: mientras autoRefresh() es false, query() no es dependencia
  createEffect(() => {
    if (!autoRefresh()) return;
    const q = query();
    const timer = setInterval(() => console.log("refrescando", q), 5000);
    onCleanup(() => clearInterval(timer)); // antes de la siguiente ejecución y al desmontar
  });

  return (
    <>
      <input value={query()} onInput={(e) => setQuery(e.currentTarget.value)} />
      <label>
        <input type="checkbox" checked={autoRefresh()} onChange={(e) => setAutoRefresh(e.currentTarget.checked)} />
        Auto
      </label>
      <ul>
        <For each={visible()}>{(p) => <li>{p.name}</li>}</For>
      </ul>
    </>
  );
}
```

Regla rápida: si dentro de un `createEffect` estás llamando a un setter para guardar algo calculado, era un `createMemo`. Ahorras una señal, un ciclo de actualización y un estado intermedio desincronizado.""",
            },
            {
                "role": "user",
                "content": "Vale. Tengo `createEffect(() => analytics.track(page(), user().id))` y solo quiero que se dispare al cambiar `page`, no cuando cambia el usuario: al refrescar el token se recrea el objeto `user` y me llegan eventos duplicados.",
            },
            {
                "role": "assistant",
                "content": r"""Usa `on` para declarar explícitamente la dependencia. Dentro de su callback las lecturas no se siguen, así que `user()` deja de disparar el efecto:

```tsx
import { createEffect, on } from "solid-js";

createEffect(
  on(page, (currentPage) => {
    analytics.track(currentPage, user().id); // user() se lee, pero no es dependencia
  }),
);
```

Con `on(page, fn, { defer: true })` te saltas la ejecución inicial si no quieres registrar la página de entrada.

Pero fíjate en la causa: el problema no es que dependa del usuario, sino que el refresco del token **crea un objeto nuevo con el mismo id**. Si un cambio real de usuario (cerrar sesión y entrar con otra cuenta) sí debe registrarse, deriva el id con un memo y depende de las dos cosas:

```tsx
import { createEffect, createMemo, on } from "solid-js";

const userId = createMemo(() => user().id); // solo notifica si el id cambia (===)

createEffect(
  on([page, userId], ([currentPage, id]) => {
    analytics.track(currentPage, id);
  }),
);
```

Traza para comprobarlo:

1. Montaje en `/` con `u1` → `track("/", "u1")`.
2. Refresco del token: `user()` es un objeto nuevo, pero `userId()` sigue siendo `"u1"`; el memo no notifica → ningún evento.
3. Navegas a `/precios` → `track("/precios", "u1")`, uno solo.
4. Cambias de cuenta a `u2` → `track("/precios", "u2")`.

La primera versión (solo `page`) se salta el paso 4; elige según qué quieras medir. Para una lectura puntual sin `on` también existe `untrack(() => user().id)`, pero `on` deja la intención escrita en la firma.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cómo cargo datos en SolidJS? Tengo una vista de detalle de usuario que depende de un `id` de la ruta (uso @solidjs/router), y quiero estado de carga, de error y un botón para refrescar. ¿`createResource` o un `fetch` dentro de `createEffect`?",
            },
            {
                "role": "assistant",
                "content": r"""`createResource`. Un `fetch` en `createEffect` te obliga a gestionar a mano las señales de carga y error, no se integra con `Suspense` y tiene una carrera: si cambias de `id` rápido, una respuesta lenta del `id` anterior puede pisar a la nueva. `createResource` resuelve las tres cosas: solo aplica el resultado de la última petición.

```tsx
// src/routes/UserDetail.tsx
import { createResource, ErrorBoundary, For, Show, startTransition, Suspense } from "solid-js";
import { useParams } from "@solidjs/router";

type User = { id: string; name: string; email: string; roles: string[] };

async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`No se pudo cargar el usuario ${id} (HTTP ${res.status})`);
  return (await res.json()) as User;
}

export default function UserDetail() {
  const params = useParams<{ id: string }>();

  // Fuente reactiva: cuando cambia params.id se vuelve a llamar a fetchUser
  const [user, { refetch }] = createResource(() => params.id, fetchUser);

  return (
    <ErrorBoundary
      fallback={(err, reset) => (
        <div role="alert">
          <p>{err instanceof Error ? err.message : "Error desconocido"}</p>
          <button
            onClick={() => {
              refetch(); // primero relanza la petición
              reset();   // después vuelve a montar el contenido
            }}
          >
            Reintentar
          </button>
        </div>
      )}
    >
      <Suspense fallback={<p>Cargando…</p>}>
        <Show when={user()}>
          {(u) => (
            <article>
              <h1>{u().name}</h1>
              <p>{u().email}</p>
              <ul>
                <For each={u().roles}>{(role) => <li>{role}</li>}</For>
              </ul>
              <button onClick={() => startTransition(() => refetch())} disabled={user.loading}>
                {user.loading ? "Refrescando…" : "Refrescar"}
              </button>
            </article>
          )}
        </Show>
      </Suspense>
    </ErrorBoundary>
  );
}
```

Qué hace cada pieza:

- **`createResource(source, fetcher)`**: el fetcher se ejecuta cada vez que cambia `source`. Si `source` devuelve `undefined`, `null` o `false`, no se llama; útil cuando el `id` aún no existe.
- **El recurso es un accessor con extras**: `user()` es el dato; `user.loading`, `user.error` y `user.state` (`"unresolved" | "pending" | "ready" | "refreshing" | "errored"`) describen el estado; `refetch` repite la petición y `mutate` permite actualizaciones optimistas sin ir a la red.
- **`Suspense`**: mientras un recurso leído dentro está pendiente, muestra el `fallback`. No hace falta un `if (loading)` en cada vista.
- **`ErrorBoundary`**: leer un recurso en estado de error lanza la excepción, y la frontera la captura. El orden en «Reintentar» importa: si llamas a `reset()` primero, el contenido se vuelve a montar, lee el recurso aún en error y cae otra vez en el fallback.
- **`<Show when={user()}>{(u) => …}</Show>`**: el callback recibe un accessor ya acotado a no nulo, así que `u().name` está tipado sin `!`.
- **`startTransition` en «Refrescar»**: sin él, el refetch vuelve a suspender y el usuario ve «Cargando…» en lugar de los datos actuales. Dentro de una transición, Solid mantiene la vista anterior hasta que llegan los nuevos y `user.loading` vale `true` mientras tanto.

Si usas la API de datos de @solidjs/router (0.15+), `query` + `createAsync` es el equivalente integrado con el router: añade caché por clave y precarga al pasar el ratón por un enlace. Para una vista suelta, `createResource` basta.

Verificación:

1. DevTools → Network → «Slow 3G». Navega rápido de `/users/1` a `/users/2`: termina mostrando el usuario 2 aunque la respuesta del 1 llegue después.
2. Haz que la API devuelva 500 para un id: aparece el mensaje con el estado HTTP; corrige la API y pulsa «Reintentar»: se recupera sin recargar la página.
3. Pulsa «Refrescar»: los datos actuales siguen visibles y el botón muestra «Refrescando…» hasta que llega la respuesta.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""In SolidJS, what's the actual difference between `<For>` and `<Index>`, and why shouldn't I just use `.map()` in JSX like in React? I have a todo list where typing in an item's input makes it lose focus after every keystroke:

```tsx
const [todos, setTodos] = createSignal<Todo[]>(initialTodos);

return (
  <ul>
    {todos().map((todo) => (
      <li>
        <input
          value={todo.text}
          onInput={(e) =>
            setTodos(todos().map((t) => (t.id === todo.id ? { ...t, text: e.currentTarget.value } : t)))
          }
        />
      </li>
    ))}
  </ul>
);
```""",
            },
            {
                "role": "assistant",
                "content": r"""Your input loses focus because every keystroke **destroys and recreates it**. Two things cause that, and switching to `<For>` alone fixes only one of them.

**1. `.map()` in JSX re-creates every row.** In Solid there's no virtual DOM. `{todos().map(...)}` is one reactive expression: when `todos()` changes, it runs again and builds brand-new DOM nodes for every item. Solid then swaps the old nodes for the new ones. The input you were typing in no longer exists.

**2. Immutable updates produce new objects.** `<For>` keys rows by **item reference**: same object → keep the row; new object → new row. Your `{ ...t, text }` creates a new object for the edited todo, so even with `<For>` that row is rebuilt and its input loses focus.

The idiomatic fix is a store with path-based updates: the object keeps its identity and only the `text` property, which is tracked on its own, changes.

```tsx
import { For } from "solid-js";
import { createStore } from "solid-js/store";

type Todo = { id: number; text: string; done: boolean };

export default function TodoList(props: { initial: Todo[] }) {
  const [todos, setTodos] = createStore<Todo[]>(props.initial);
  let nextId = Math.max(0, ...props.initial.map((t) => t.id)) + 1;

  const add = () => setTodos((list) => [...list, { id: nextId++, text: "", done: false }]);
  const remove = (id: number) => setTodos((list) => list.filter((t) => t.id !== id));

  return (
    <>
      <ul>
        <For each={todos}>
          {(todo) => (
            <li>
              <input
                type="checkbox"
                checked={todo.done}
                onChange={(e) => setTodos((t) => t.id === todo.id, "done", e.currentTarget.checked)}
              />
              <input
                value={todo.text}
                onInput={(e) => setTodos((t) => t.id === todo.id, "text", e.currentTarget.value)}
              />
              <button onClick={() => remove(todo.id)}>×</button>
            </li>
          )}
        </For>
      </ul>
      <button onClick={add}>Add</button>
    </>
  );
}
```

`setTodos((t) => t.id === todo.id, "text", value)` reads as "in the items matching this filter, set `text`". The store notifies only the readers of that item's `text`, which is the `value` binding of that one input. The `<li>`, the checkbox and every other row are untouched.

Now the `<For>` vs `<Index>` question:

| | `<For>` | `<Index>` |
|---|---|---|
| Rows keyed by | item reference | position in the array |
| `item` in the callback | the value | a signal: `item()` |
| `index` in the callback | a signal: `index()` | a plain number |
| Best for | lists of objects that get added, removed or reordered | primitives or fixed slots where the value at a position changes |

With `<Index>`, if position 3 changes from `"a"` to `"b"`, the row at position 3 stays and only `item()` updates; reorder the array and rows don't move, their contents do. That's ideal for something like a row of score inputs bound to `number[]`, and wrong for a sortable list of entities.

Rule of thumb: objects with identity → store + `<For>`; primitives by position → `<Index>`; `.map()` in JSX only for static data that never changes.

Verification: type a sentence in the first item; focus stays and the caret doesn't jump. In DevTools → Elements, right-click the `<ul>` → "Break on → subtree modifications": typing doesn't trigger the breakpoint (only the input's value changes), while clicking "Add" does, once, for the new `<li>`.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En mi equipo estamos eligiendo framework para un panel interno y la discusión se fue a la reactividad. ¿En qué se diferencian de verdad React, Vue, Svelte 5 y SolidJS en cómo detectan un cambio y cómo actualizan el DOM? Queremos algo más que «uno usa virtual DOM y otro no».",
            },
            {
                "role": "assistant",
                "content": r"""La diferencia útil es **qué unidad de trabajo se repite cuando cambia un dato**: un componente entero o una expresión concreta. De ahí salen el rendimiento por defecto, las optimizaciones manuales y los bugs típicos de cada uno.

| | Qué se vuelve a ejecutar | Cómo sabe qué cambió | Cómo toca el DOM |
|---|---|---|---|
| React 19 | El componente y, por defecto, todo su subárbol | No lo sabe con detalle: `setState` marca el componente como sucio | Virtual DOM: vuelve a renderizar y compara (reconciliación) |
| Vue 3.5 | La función de render de los componentes que leyeron el dato | Proxies y `ref` registran qué lee cada render | Virtual DOM optimizado por el compilador (nodos estáticos, *patch flags*) |
| Svelte 5 | La expresión concreta de la plantilla | Señales (runas) generadas por el compilador | Operaciones DOM directas compiladas |
| SolidJS 1.9 | La expresión concreta del JSX; el componente corre una vez | Señales en tiempo de ejecución | Operaciones DOM directas (plantillas + efectos finos) |

Un mismo caso para verlo: una cabecera con un contador y una tabla de 500 filas en el mismo componente. Cambia el contador.

- **React**: se ejecuta el componente, se crean de nuevo los elementos de las 500 filas y se comparan. El DOM solo cambia en el texto del contador, pero el trabajo de render y comparación se hizo para todo. Lo evitas con `memo` en la tabla o colocando el estado más abajo; el React Compiler (1.0 desde octubre de 2025) automatiza buena parte de esa memoización.
- **Vue**: se vuelve a ejecutar el render de ese componente y se compara su árbol, pero el compilador marca qué nodos son dinámicos y los componentes hijos cuyas props no cambiaron no se renderizan. Coste moderado sin hacer nada.
- **Svelte 5 y Solid**: se actualiza un nodo de texto. Nada más se ejecuta.

Lo que cada modelo te exige y dónde falla la gente:

- **React**: pensar en «cada render es una instantánea». Fallos típicos: closures obsoletos, arrays de dependencias incompletos en `useEffect`, cascadas de renders. Ventaja: el modelo mental es simple (UI = f(estado)) y el ecosistema es el más grande.
- **Vue**: entender proxies. Fallos típicos: desestructurar un `reactive` y perder la reactividad (por eso existe `toRefs`), olvidar `.value` fuera de la plantilla. Buen equilibrio por defecto.
- **Svelte 5**: las runas hacen explícito qué es estado (`$state`) y qué es derivado (`$derived`). Fallos típicos: usar `$effect` para calcular valores, exportar estado reasignado desde un módulo.
- **Solid**: el componente es código de montaje, no de render. Fallo típico: desestructurar props o leer una señal fuera del JSX y quedarse con el valor inicial. Necesitas `<Show>` y `<For>` en vez de ternarios y `.map()` para conservar la granularidad.

Angular va en la misma dirección que Svelte y Solid: sus signals y el modo sin Zone.js permiten actualizar solo las vistas que leyeron una señal, aunque sigue con detección de cambios por componente.

La forma corta de decirlo en la reunión: React y Vue **vuelven a ejecutar y comparan** (Vue con mucha más información sobre qué comparar); Svelte y Solid **se suscriben** al dato exacto y lo escriben donde va.""",
            },
            {
                "role": "user",
                "content": "¿Y en rendimiento real eso se nota? Es un panel interno con tablas de unos cientos de filas y algunos gráficos, y el equipo sabe React.",
            },
            {
                "role": "assistant",
                "content": r"""Con cientos de filas, no lo bastante como para cambiar de framework. Con un equipo que ya domina React, quédense con React salvo que una medición diga lo contrario.

Por qué:

- **La diferencia se nota con miles de nodos y actualizaciones frecuentes**: rejillas en tiempo real que cambian muchas celdas por segundo, editores con miles de elementos. En benchmarks como js-framework-benchmark, Solid y Svelte quedan cerca de JavaScript a mano y React detrás en actualizaciones parciales, pero hablamos de milisegundos en operaciones sobre miles de filas.
- **En paneles internos, los cuellos de botella reales suelen ser otros**: cascadas de peticiones, pintar 5.000 filas sin virtualizar, librerías de gráficos que redibujan todo el canvas, y re-renders de subárboles grandes en cada pulsación de un filtro. Todo eso se arregla en React con herramientas conocidas: estado colocado cerca de donde se usa, `memo` o React Compiler, virtualización (TanStack Virtual) y caché de datos (TanStack Query).
- **El coste de cambiar es seguro; el beneficio, hipotético.** Curva de aprendizaje, menos librerías de componentes y una base de código mezclada durante meses.

Cómo decidirlo con datos en vez de opiniones, en un par de días:

1. Elijan la pantalla más exigente que vaya a tener el panel (la tabla más grande con su filtro y su gráfico).
2. Constrúyanla en React con las prácticas de arriba. Si quieren comparar, hagan la misma pantalla en Solid o Svelte; es pequeña.
3. Midan con Chrome DevTools → Performance con la CPU ralentizada 4× (simula los portátiles modestos del equipo de operaciones): tiempo de *scripting* por interacción y el INP de las acciones típicas (escribir en el filtro, ordenar, paginar). En React, el Profiler les dice qué componentes se renderizan y por qué.
4. Criterio: si las interacciones quedan por debajo de ~100 ms con la CPU ralentizada, sobra margen (el umbral «bueno» de INP es 200 ms). Si no, miren primero qué se renderiza de más antes de culpar al framework.

Solo cambiaría de framework si el requisito es claramente de alta frecuencia (por ejemplo, cientos de celdas actualizadas por segundo desde un WebSocket) y el prototipo en React, ya optimizado, no llega. En ese caso, una opción intermedia es aislar solo ese widget con una solución de grano fino o escribiendo directamente al DOM o a un canvas, sin reescribir el panel entero.""",
            },
        ]
    },
]
