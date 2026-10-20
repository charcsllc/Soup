"""React 19: componentes, hooks, Actions, formularios, rendimiento, testing y patrones."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# ---------------------------------------------------------------------------
# 1-5: componentes y props, useState y closures, useEffect/StrictMode, useRef, memoización
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy empezando con React. ¿Qué es exactamente un componente y cómo le paso datos? Veo `props` por todos lados pero no termino de entenderlo.",
            },
            {
                "role": "assistant",
                "content": r"""Un componente es una función de JavaScript que recibe un objeto (`props`) y devuelve lo que hay que pintar (JSX). Nada más: ni clases ni magia.

```jsx
function UserCard(props) {
  return (
    <article>
      <h2>{props.name}</h2>
      <p>{props.email}</p>
    </article>
  );
}

// Uso: cada atributo se convierte en una propiedad del objeto props
<UserCard name="Ana" email="ana@example.com" />
```

Cuando React ve `<UserCard name="Ana" email="ana@example.com" />` llama a `UserCard({ name: "Ana", email: "ana@example.com" })`. Ese es todo el mecanismo de «pasar datos».

Tres reglas que evitan la mayoría de los errores iniciales:

1. **Las props son de solo lectura.** Un componente nunca hace `props.name = "Luis"`. Si necesita algo que cambie con el tiempo, usa estado (`useState`) o le pide al padre que le pase otro valor.
2. **Desestructura en la firma** para que se vea de un vistazo qué necesita el componente:

```jsx
function UserCard({ name, email, isAdmin = false }) {
  return (
    <article>
      <h2>
        {name} {isAdmin && <span>(admin)</span>}
      </h2>
      <p>{email}</p>
    </article>
  );
}
```

El valor por defecto (`isAdmin = false`) es JavaScript normal, no una API de React.

3. **`children` es una prop más.** Lo que escribes entre la apertura y el cierre llega como `props.children`, y con eso construyes contenedores reutilizables:

```jsx
function Panel({ title, children }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

<Panel title="Perfil">
  <UserCard name="Ana" email="ana@example.com" />
</Panel>
```

Puedes pasar cualquier valor como prop: números, arrays, objetos, funciones (así el hijo avisa al padre: `onSelect={(id) => setSelected(id)}`) e incluso otros elementos JSX. Si el valor no es una cadena, va entre llaves: `<Lista items={["a", "b"]} />`.

Prueba mental: si en el padre cambias `name="Ana"` por `name="Eva"`, React vuelve a llamar a `UserCard` con las nuevas props y repinta solo lo que cambió. Esa es la idea central: la interfaz es una función de las props y del estado.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Tengo este contador y al pulsar el botón sube de 1 en 1 en vez de 3 en 3. ¿Qué estoy haciendo mal?

```jsx
import { useState } from "react";

export function Counter() {
  const [count, setCount] = useState(0);

  function addThree() {
    setCount(count + 1);
    setCount(count + 1);
    setCount(count + 1);
  }

  return <button onClick={addThree}>Total: {count}</button>;
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""No es un bug de React: es un **closure obsoleto** más el **agrupado de actualizaciones**.

En el render donde `count` vale `0`, la función `addThree` captura ese `0`. Las tres líneas son literalmente `setCount(0 + 1)`. React agrupa las tres actualizaciones del mismo evento (batching, automático desde React 18) y renderiza una sola vez con `1`.

Traza del clic: `count = 0` → `setCount(1)`, `setCount(1)`, `setCount(1)` → un re-render con `1`.

La solución es la **forma funcional** del setter. En vez de pasar un valor, pasas una función que recibe el estado más reciente:

```jsx
function addThree() {
  setCount((c) => c + 1);
  setCount((c) => c + 1);
  setCount((c) => c + 1);
}
```

React encola las tres funciones y las aplica en orden sobre el valor acumulado: `0 → 1 → 2 → 3`.

Regla práctica: **si el nuevo valor depende del anterior, usa el updater**. Si no depende (`setName("Ana")`), pasa el valor directo.

Para este caso concreto, lo más simple sería `setCount(count + 3)`. Pero el patrón que acabas de ver reaparece en sitios menos obvios, donde ya no hay atajo:

```jsx
function startTimer() {
  // MAL: `count` es el de este render; al disparar el timeout ya está viejo
  setTimeout(() => setCount(count + 1), 1000);

  // BIEN: el updater lee el estado real en el momento de aplicarse
  setTimeout(() => setCount((c) => c + 1), 1000);
}
```

Lo mismo ocurre en `useEffect`, en callbacks de WebSocket y en cualquier función que sobreviva al render en que se creó.

Prueba mínima con Testing Library:

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Counter } from "./Counter";

test("suma tres por clic", async () => {
  const user = userEvent.setup();
  render(<Counter />);
  await user.click(screen.getByRole("button"));
  expect(screen.getByRole("button")).toHaveTextContent("Total: 3");
});
```""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi useEffect se ejecuta dos veces al cargar la página, lo veo con un console.log repetido. Las dependencias son `[]`. ¿Es un bug de React 19?",
            },
            {
                "role": "assistant",
                "content": r"""No es un bug: es `<StrictMode>` en desarrollo. Desde React 18, en modo estricto React monta el componente, ejecuta el efecto, ejecuta su limpieza, y vuelve a ejecutar el efecto. Lo hace solo en desarrollo; en el build de producción el efecto corre una vez.

El objetivo es destapar efectos que no se limpian bien. Si tu efecto resiste un «montar, desmontar, montar» sin dejar basura, también resistirá la navegación real del usuario.

Mira la diferencia:

```jsx
// Sin limpieza: en StrictMode verás DOS listeners registrados
useEffect(() => {
  window.addEventListener("resize", onResize);
}, []);

// Con limpieza: el segundo montaje parte de cero
useEffect(() => {
  window.addEventListener("resize", onResize);
  return () => window.removeEventListener("resize", onResize);
}, []);
```

Para comprobar que es StrictMode y no otra cosa, busca en `main.jsx`:

```jsx
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

Quitarlo hace desaparecer el doble log, pero no lo hagas: pierdes el detector de fugas gratis. Lo correcto es que el efecto sea idempotente y se limpie. Si el `console.log` duplicado te molesta, sustitúyelo por un log dentro de la limpieza también y verás el patrón completo: `montado`, `limpiado`, `montado`.""",
            },
            {
                "role": "user",
                "content": "Vale, pero dentro del efecto hago un fetch con el id que viene por props, y se dispara dos veces. Y a veces, cuando cambio rápido de id, me pinta los datos del id anterior. ¿Cómo lo evito?",
            },
            {
                "role": "assistant",
                "content": r"""Son dos cosas distintas. El doble fetch en desarrollo es StrictMode y es inofensivo. Lo de «pinta los datos del id anterior» es una **condición de carrera** y ocurre también en producción: cambias de `id` A a B, la respuesta de A llega después que la de B y pisa el estado con datos viejos.

El arreglo para ambas es la limpieza del efecto con `AbortController`:

```jsx
import { useEffect, useState } from "react";

export function UserProfile({ id }) {
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    setUser(null);

    fetch(`/api/users/${id}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setUser)
      .catch((err) => {
        // Una petición abortada no es un error para el usuario
        if (err.name !== "AbortError") setError(err);
      });

    return () => controller.abort();
  }, [id]);

  if (error) return <p role="alert">No se pudo cargar: {error.message}</p>;
  if (!user) return <p>Cargando…</p>;
  return <h2>{user.name}</h2>;
}
```

Traza con A lento y B rápido: cambias a B → React ejecuta la limpieza del efecto de A → `abort()` → la promesa de A rechaza con `AbortError` y se ignora → solo B llama a `setUser`. En StrictMode pasa lo mismo: el primer montaje se aborta y solo el segundo pinta. Ya no te importa que se dispare dos veces.

Dos detalles que suelen fallar:

- `res.ok`: `fetch` no rechaza con un 404 o un 500. Si no lo compruebas, intentarás parsear una página de error como JSON.
- Reiniciar `setUser(null)` al cambiar de `id` evita mostrar el usuario anterior mientras carga el nuevo.

Si tu app tiene más de dos o tres fetches así, deja de escribirlos a mano: TanStack Query (`useQuery({ queryKey: ["user", id], queryFn })`) resuelve la carrera, la caché, los reintentos y el estado de carga, y además deduplica las peticiones de StrictMode.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Para qué sirve useRef aparte de acceder a un elemento del DOM? Tengo un setInterval y guardo su id en un useState, pero cada vez que lo guardo se re-renderiza todo el componente.",
            },
            {
                "role": "assistant",
                "content": r"""`useRef` es una caja mutable que sobrevive entre renders y cuyo cambio **no provoca re-render**. Esa es la diferencia con `useState`, y es exactamente lo que necesitas para el id del intervalo: es un dato que el componente necesita recordar, pero que no se pinta.

| | `useState` | `useRef` |
|---|---|---|
| Cambiarlo re-renderiza | sí | no |
| Se lee en el JSX | sí | no (no es fuente de verdad visual) |
| Sobrevive entre renders | sí | sí |
| Uso típico | lo que el usuario ve | ids de timers, instancias, valor previo, nodos DOM |

Tu intervalo, corregido:

```jsx
import { useEffect, useRef, useState } from "react";

export function Stopwatch() {
  const [seconds, setSeconds] = useState(0);
  const intervalRef = useRef(null);

  function start() {
    if (intervalRef.current !== null) return; // ya está corriendo
    intervalRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
  }

  function stop() {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }

  // Limpieza al desmontar: sin esto el intervalo sigue vivo y llama a setState
  useEffect(() => stop, []);

  return (
    <div>
      <p>{seconds} s</p>
      <button onClick={start}>Iniciar</button>
      <button onClick={stop}>Parar</button>
    </div>
  );
}
```

Observa el `setSeconds((s) => s + 1)`: el callback del intervalo se creó en un render concreto y capturó el `seconds` de entonces; la forma funcional evita ese closure obsoleto.

Otros dos usos habituales, además del DOM:

**Valor del render anterior** (comparar «antes y después»):

```jsx
function usePrevious(value) {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  });
  return ref.current;
}
```

**Guardar el callback más reciente** para que un listener registrado una sola vez no se quede con una versión vieja:

```jsx
function useEventCallback(fn) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  });
  return useCallback((...args) => ref.current(...args), []);
}
```

Dos reglas para no tener sorpresas:

1. **No leas ni escribas `ref.current` durante el render** (fuera de handlers y efectos). React no promete que el valor sea el que esperas, y con el React Compiler es directamente un error de lint.
2. Si el valor afecta a lo que se pinta, no es un ref: es estado.

Y una novedad de React 19: `ref` llega como una prop normal a los componentes de función, así que ya no necesitas `forwardRef` para exponer un nodo:

```jsx
function TextInput({ ref, ...props }) {
  return <input ref={ref} {...props} />;
}
```""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Debería envolver todo en useMemo y useCallback? Un compañero dice que sí, que es «por rendimiento», pero el código queda ilegible.",
            },
            {
                "role": "assistant",
                "content": r"""No. Memoizar todo es un error en las dos direcciones: no mejora el rendimiento en la mayoría de los casos y sí empeora la legibilidad. `useMemo` y `useCallback` solo pagan cuando **la identidad de referencia importa** a alguien más abajo.

Hay exactamente tres situaciones en las que sí:

**1. El valor va a un hijo envuelto en `memo`.** Si el hijo no está memoizado, memoizar la prop no evita nada: el hijo se re-renderiza porque su padre se re-renderizó.

```jsx
const Row = memo(function Row({ item, onSelect }) {
  return <li onClick={() => onSelect(item.id)}>{item.name}</li>;
});

function List({ items }) {
  const [selected, setSelected] = useState(null);
  // Sin useCallback, cada render crea una función nueva y `memo` no sirve de nada
  const onSelect = useCallback((id) => setSelected(id), []);
  return items.map((item) => <Row key={item.id} item={item} onSelect={onSelect} />);
}
```

**2. El valor está en las dependencias de un `useEffect` u otro hook.** Un objeto o función nuevos en cada render disparan el efecto en cada render; en el peor caso, un bucle infinito si el efecto actualiza estado.

```jsx
const options = useMemo(() => ({ page, pageSize }), [page, pageSize]);
useEffect(() => {
  load(options);
}, [options]);
```

**3. El cálculo es caro de verdad.** Ordenar o filtrar 50 elementos cuesta microsegundos; memoizarlo cuesta lo mismo más una comparación. Memoiza cuando el Profiler te enseñe milisegundos.

Todo lo demás es ruido:

```jsx
// Inútil: el valor se usa aquí mismo, nadie compara su identidad
const fullName = useMemo(() => `${first} ${last}`, [first, last]);

// Inútil: el handler va a un <button> nativo, que no es `memo`
const onClick = useCallback(() => setOpen(true), []);
```

Cómo decidirlo sin discutir: abre React DevTools, pestaña **Profiler**, graba una interacción y mira qué componentes se re-renderizan y cuánto tardan. Si un componente aparece en cada commit y su render cuesta algo medible, memoiza *ese* camino concreto (hijo con `memo` + props estables). Si no aparece nada, deja el código limpio.

Y la noticia que cambia la conversación: el **React Compiler** (estable desde la 1.0, se instala como `babel-plugin-react-compiler`) memoiza automáticamente valores y callbacks siguiendo las reglas de React. Con el compilador activado, el `useMemo` manual pasa a ser la excepción documentada, no la norma. Si tu proyecto puede adoptarlo, es una mejor inversión que llenar el código de hooks de memoización.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 6-10: useReducer, useContext (multiturno), custom hooks (EN), use() con promesas, Actions
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un formulario de checkout con unos 8 useState (dirección, método de pago, cupón, errores, paso actual…) y los handlers se pisan entre sí. ¿Es momento de useReducer o estoy exagerando?",
            },
            {
                "role": "assistant",
                "content": r"""Es momento. La señal no es el número de `useState`, sino que **varios se actualizan juntos** y que la transición válida depende del estado anterior (por ejemplo, «aplicar cupón» limpia el error, recalcula el total y no debe funcionar en el paso 1). Eso es una máquina de estados, y `useReducer` la hace explícita.

```tsx
import { useReducer } from "react";

type Step = "address" | "payment" | "review";

type State = {
  step: Step;
  address: { street: string; city: string };
  paymentMethod: "card" | "transfer" | null;
  coupon: string | null;
  error: string | null;
};

type Action =
  | { type: "address_changed"; field: "street" | "city"; value: string }
  | { type: "payment_selected"; method: State["paymentMethod"] }
  | { type: "coupon_applied"; code: string }
  | { type: "coupon_rejected"; reason: string }
  | { type: "next_step" }
  | { type: "prev_step" };

const ORDER: Step[] = ["address", "payment", "review"];

const initialState: State = {
  step: "address",
  address: { street: "", city: "" },
  paymentMethod: null,
  coupon: null,
  error: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "address_changed":
      return { ...state, address: { ...state.address, [action.field]: action.value } };
    case "payment_selected":
      return { ...state, paymentMethod: action.method, error: null };
    case "coupon_applied":
      return { ...state, coupon: action.code, error: null };
    case "coupon_rejected":
      return { ...state, coupon: null, error: action.reason };
    case "next_step": {
      // La validación de la transición vive en un único sitio
      if (state.step === "address" && !state.address.street) {
        return { ...state, error: "La dirección es obligatoria" };
      }
      if (state.step === "payment" && !state.paymentMethod) {
        return { ...state, error: "Elige un método de pago" };
      }
      const next = ORDER[Math.min(ORDER.indexOf(state.step) + 1, ORDER.length - 1)];
      return { ...state, step: next, error: null };
    }
    case "prev_step": {
      const prev = ORDER[Math.max(ORDER.indexOf(state.step) - 1, 0)];
      return { ...state, step: prev, error: null };
    }
  }
}

export function Checkout() {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <form onSubmit={(e) => { e.preventDefault(); dispatch({ type: "next_step" }); }}>
      {state.error && <p role="alert">{state.error}</p>}
      {state.step === "address" && (
        <input
          value={state.address.street}
          onChange={(e) => dispatch({ type: "address_changed", field: "street", value: e.target.value })}
        />
      )}
      <button type="submit">Continuar</button>
    </form>
  );
}
```

Qué ganas respecto a los 8 `useState`:

- **Las transiciones imposibles no existen.** No hay forma de avanzar sin dirección, porque esa regla está en el reducer y no repartida entre handlers.
- **El reducer se prueba sin React.** Es una función pura: `expect(reducer(s, { type: "next_step" }).error).toBe("La dirección es obligatoria")`.
- **Las actualizaciones que van juntas van juntas.** `coupon_rejected` limpia el cupón y pone el error en una sola acción; con `useState` eran dos setters que alguien olvidaba sincronizar.

Cuándo *no* usarlo: si los estados son independientes (un `isOpen` de un modal y un `search` de un buscador), `useReducer` solo añade ceremonia. La regla es: un reducer por **grupo de estado que cambia junto**, no uno por componente.

El tipo `Action` como unión discriminada es lo que hace que el `switch` esté completo: si añades una acción y olvidas el `case`, TypeScript avisa porque la función deja de devolver `State` en todos los caminos.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Responde en español, con código TypeScript y explicando el porqué de cada decisión."},
            {
                "role": "user",
                "content": "Quiero un contexto de tema (claro/oscuro) bien hecho en React 19 con TypeScript. Lo que tengo ahora exporta el contexto y cada componente hace useContext a pelo, y si olvidan el Provider se rompe en silencio.",
            },
            {
                "role": "assistant",
                "content": r"""La forma robusta es no exportar el contexto: exportas el `Provider` y un hook `useTheme` que **lanza si falta el proveedor**. Así el fallo es inmediato y con un mensaje claro, en vez de un `undefined` que explota tres componentes más abajo.

```tsx
// theme-context.tsx
import { createContext, use, useCallback, useMemo, useState, type ReactNode } from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
  theme: Theme;
  toggle: () => void;
};

// `null` por defecto: nunca hay un valor "válido" sin Provider
const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children, initial = "light" }: { children: ReactNode; initial?: Theme }) {
  const [theme, setTheme] = useState<Theme>(initial);
  const toggle = useCallback(() => setTheme((t) => (t === "light" ? "dark" : "light")), []);

  // Objeto estable: sin esto, cada render del Provider re-renderiza a TODOS los consumidores
  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);

  // React 19: el contexto se usa directamente como proveedor, sin `.Provider`
  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useTheme(): ThemeContextValue {
  const ctx = use(ThemeContext);
  if (ctx === null) {
    throw new Error("useTheme debe usarse dentro de <ThemeProvider>");
  }
  return ctx;
}
```

Uso:

```tsx
function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return <button onClick={toggle}>Tema actual: {theme}</button>;
}
```

Las decisiones, una por una:

- **`createContext<Value | null>(null)`** en lugar de un valor por defecto «falso» como `{ theme: "light", toggle: () => {} }`. Un default así *parece* funcionar sin Provider y esconde el olvido; el `null` lo convierte en un error con nombre.
- **El contexto no se exporta.** El único punto de acceso es `useTheme`, así que la comprobación no se puede saltar.
- **`use(ThemeContext)`** (React 19) en vez de `useContext`: hace lo mismo, pero además puede llamarse dentro de condicionales y bucles, lo que `useContext` no permite. Para este hook no cambia nada; es la API actual.
- **`useMemo` del valor**: aquí sí está justificado. El Provider suele estar arriba del árbol y re-renderiza por motivos ajenos al tema; sin memoizar, cada uno de esos renders crearía un objeto nuevo y despertaría a todos los consumidores.
- **`<ThemeContext value={value}>`**: en React 19 el contexto es su propio proveedor; `ThemeContext.Provider` sigue funcionando pero está en vías de deprecación.

Prueba del error:

```tsx
import { renderHook } from "@testing-library/react";

test("useTheme sin Provider lanza", () => {
  expect(() => renderHook(() => useTheme())).toThrow(/ThemeProvider/);
});
```""",
            },
            {
                "role": "user",
                "content": "Perfecto. Ahora el problema es que al cambiar el tema se re-renderizan componentes que solo usan `toggle`, no `theme`. ¿Hay forma de evitarlo?",
            },
            {
                "role": "assistant",
                "content": r"""Sí: **divide el contexto en dos**, uno para el valor que cambia y otro para la función que no cambia. Un consumidor se re-renderiza cuando cambia el valor del contexto que lee; si `toggle` vive en un contexto cuyo valor es estable, quien solo lee `toggle` nunca se despierta.

```tsx
const ThemeValueContext = createContext<Theme | null>(null);
const ThemeToggleContext = createContext<(() => void) | null>(null);

export function ThemeProvider({ children, initial = "light" }: { children: ReactNode; initial?: Theme }) {
  const [theme, setTheme] = useState<Theme>(initial);
  const toggle = useCallback(() => setTheme((t) => (t === "light" ? "dark" : "light")), []);

  return (
    <ThemeToggleContext value={toggle}>
      <ThemeValueContext value={theme}>{children}</ThemeValueContext>
    </ThemeToggleContext>
  );
}

export function useThemeValue(): Theme {
  const theme = use(ThemeValueContext);
  if (theme === null) throw new Error("useThemeValue debe usarse dentro de <ThemeProvider>");
  return theme;
}

export function useThemeToggle(): () => void {
  const toggle = use(ThemeToggleContext);
  if (toggle === null) throw new Error("useThemeToggle debe usarse dentro de <ThemeProvider>");
  return toggle;
}
```

`toggle` tiene identidad estable gracias a `useCallback` con dependencias vacías (usa el updater funcional, así no necesita `theme`), de modo que el valor de `ThemeToggleContext` es el mismo objeto en todos los renders y sus consumidores no se re-renderizan jamás por un cambio de tema.

Verificación rápida: un `<ThemeToggle />` que solo llama a `useThemeToggle()` no aparece en el Profiler al pulsar el botón; un `<ThemedCard />` que llama a `useThemeValue()` sí.

Esto ya no necesita el `useMemo` del valor: cada contexto transporta un primitivo o una función estable, no un objeto nuevo.

El límite de la técnica: funciona bien para dos o tres piezas. Si el contexto crece a un objeto con diez campos que cambian por separado, dividirlo en diez contextos deja de ser razonable y es el momento de un store con selectores (Zustand, Jotai), donde cada componente se suscribe exactamente al trozo que lee.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "I keep copy-pasting the same debounce logic into every search input. How do I turn it into a custom hook properly, and what are the rules I need to follow?",
            },
            {
                "role": "assistant",
                "content": r"""A custom hook is just a function whose name starts with `use` and that calls other hooks. Extracting the debounce is a good fit because the logic is stateful (it owns a timer) and reusable across inputs.

```tsx
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    // Cleanup runs before the next effect and on unmount, so a fast typist never fires
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}
```

Usage:

```tsx
function SearchBox() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 300);

  useEffect(() => {
    if (debouncedQuery === "") return;
    const controller = new AbortController();
    fetch(`/api/search?q=${encodeURIComponent(debouncedQuery)}`, { signal: controller.signal })
      .then((r) => r.json())
      .then(console.log)
      .catch((err) => {
        if (err.name !== "AbortError") console.error(err);
      });
    return () => controller.abort();
  }, [debouncedQuery]);

  return <input value={query} onChange={(e) => setQuery(e.target.value)} />;
}
```

The input stays controlled and responsive (`query` updates on every keystroke); only the *derived* value lags. That separation is the whole point: you debounce the consumer, not the typing.

Rules that make a custom hook safe:

1. **Name starts with `use`.** This is not cosmetic: the `eslint-plugin-react-hooks` lint and the React Compiler use the name to enforce the rules of hooks inside it.
2. **Same call order on every render.** No hooks inside `if`, loops or after an early `return`. Your hook calls `useState` and `useEffect` unconditionally, so callers inherit that guarantee.
3. **Every call site gets its own state.** Two `SearchBox` components each own an independent timer. Hooks share *logic*, never *state*; if you need shared state, lift it or use a store.
4. **Return the smallest useful shape.** A value, or a `[value, setter]` tuple like `useState`. Returning a bag of ten fields couples callers to your internals.
5. **Clean up what you start.** The `clearTimeout` in the cleanup is what prevents a stale update from landing after unmount, and it is what makes the hook survive StrictMode's double mount in development.

Test it with `renderHook` and fake timers:

```tsx
import { act, renderHook } from "@testing-library/react";
import { vi } from "vitest";
import { useDebouncedValue } from "./useDebouncedValue";

test("only the last value within the window is emitted", () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 300), {
    initialProps: { v: "a" },
  });

  rerender({ v: "ab" });
  rerender({ v: "abc" });
  expect(result.current).toBe("a");

  act(() => vi.advanceTimersByTime(300));
  expect(result.current).toBe("abc");
  vi.useRealTimers();
});
```""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Leí que en React 19 puedo usar `use(promise)` y olvidarme de useEffect para cargar datos. Hice esto y la pantalla parpadea sin parar:

```jsx
function Profile({ id }) {
  const user = use(fetch(`/api/users/${id}`).then((r) => r.json()));
  return <h1>{user.name}</h1>;
}
```

¿Qué pasa?""",
            },
            {
                "role": "assistant",
                "content": r"""El parpadeo es un **bucle de suspensión**: creas la promesa dentro del render, así que cada render produce una promesa nueva.

Traza: render 1 → `fetch()` crea la promesa P1 → `use(P1)` suspende → P1 se resuelve → React vuelve a renderizar → `fetch()` crea P2 → `use(P2)` suspende → y así sin fin. `use` necesita recibir **la misma promesa** en cada render hasta que cambie el `id`.

La regla es: la promesa se crea **fuera del render** y se cachea por clave. Sin framework, la forma honesta es una pequeña caché:

```jsx
import { Suspense, use } from "react";

const cache = new Map();

function getUser(id) {
  if (!cache.has(id)) {
    cache.set(
      id,
      fetch(`/api/users/${id}`).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
    );
  }
  return cache.get(id);
}

function Profile({ id }) {
  const user = use(getUser(id)); // misma promesa mientras `id` no cambie
  return <h1>{user.name}</h1>;
}

export function ProfilePage({ id }) {
  return (
    <Suspense fallback={<p>Cargando…</p>}>
      <Profile id={id} />
    </Suspense>
  );
}
```

Ahora el render 2 recibe la misma promesa P1 del `Map`, `use` la ve resuelta y devuelve el valor sin suspender.

Tres cosas que necesitas alrededor de `use`:

- **Un `<Suspense>`** por encima; sin él, la suspensión sube hasta la raíz y desmonta toda la app mientras carga.
- **Un error boundary**: si la promesa rechaza, `use` lanza el error. Sin boundary, se cae el árbol entero (abajo verás uno con `react-error-boundary`).
- **Invalidación**: una caché infinita como la del ejemplo no se actualiza nunca. Para datos que cambian, necesitas borrar la entrada (`cache.delete(id)`) tras una mutación.

Ese último punto es la razón por la que, en una app real, no escribes esta caché a mano. La documentación de React lo dice tal cual: `use` con promesas creadas en Client Components está pensado para frameworks y librerías con caché. Las dos rutas estables:

1. **Next.js (Server Components)**: creas la promesa en el servidor y la pasas como prop al componente cliente, que hace `use(promise)`. El servidor la crea una sola vez por petición.
2. **TanStack Query**: `useSuspenseQuery({ queryKey: ["user", id], queryFn })` te da Suspense, caché por clave, invalidación y reintentos sin escribir el `Map`.

Para el error boundary, el mínimo:

```jsx
import { ErrorBoundary } from "react-error-boundary";

<ErrorBoundary fallback={<p role="alert">No se pudo cargar el perfil</p>}>
  <Suspense fallback={<p>Cargando…</p>}>
    <Profile id={id} />
  </Suspense>
</ErrorBoundary>
```""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cómo se hace un formulario con las Actions nuevas de React 19? Quiero enviar un comentario, mostrar «enviando», el error si falla y limpiar el campo si va bien. Sin Next, es una SPA con Vite.",
            },
            {
                "role": "assistant",
                "content": r"""Con `useActionState` el formulario se reduce a: una función `async` que recibe el `FormData`, un estado de resultado y un `isPending` que React mantiene por ti.

```tsx
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

type ActionState = { error: string | null; submitted: boolean };

async function postComment(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const text = String(formData.get("text") ?? "").trim();
  if (text.length < 3) {
    return { error: "El comentario necesita al menos 3 caracteres", submitted: false };
  }
  const res = await fetch("/api/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    return { error: `No se pudo enviar (HTTP ${res.status})`, submitted: false };
  }
  return { error: null, submitted: true };
}

function SubmitButton() {
  // Lee el estado del <form> más cercano: no necesita props
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending}>
      {pending ? "Enviando…" : "Publicar"}
    </button>
  );
}

export function CommentForm() {
  const [state, formAction, isPending] = useActionState(postComment, { error: null, submitted: false });

  return (
    // `key` fuerza un formulario nuevo (campos vacíos) tras un envío correcto
    <form action={formAction} key={state.submitted ? "done" : "editing"}>
      <textarea name="text" required disabled={isPending} />
      {state.error && <p role="alert">{state.error}</p>}
      {state.submitted && <p>Comentario publicado.</p>}
      <SubmitButton />
    </form>
  );
}
```

Qué hace cada pieza y por qué:

- **`<form action={fn}>`**: cuando la acción es una función, React intercepta el envío, construye el `FormData` y la llama. No hay `onSubmit`, ni `preventDefault`, ni `useState` por campo: el formulario es **no controlado** y los datos se leen con `formData.get`.
- **`useActionState(action, initial)`** devuelve `[state, formAction, isPending]`. `state` es lo que devolvió la última ejecución de la acción. Devolver errores como datos (en vez de lanzarlos) es lo que permite pintarlos sin un error boundary.
- **`useFormStatus`** (de `react-dom`) se lee desde un componente *hijo* del formulario. Es la forma de tener un botón reutilizable que sabe si está enviando sin pasarle props.
- **Limpiar el campo**: React restablece automáticamente los formularios no controlados tras una acción correcta, pero de forma segura lo que hace el `key` es montar un `<form>` nuevo cuando `submitted` pasa a `true`. Es explícito y no depende de ese comportamiento.
- **Validación en dos capas**: `required` bloquea el envío vacío en el navegador; la longitud mínima se comprueba dentro de la acción, porque el HTML se puede manipular y porque así el mensaje es el mismo venga de donde venga el envío.

Lo que ganas frente al patrón `useState` + `onSubmit` + `isLoading`: el estado de carga y los envíos concurrentes los gestiona React (un segundo envío mientras el primero está en vuelo se encola, no se pisa), y el formulario funciona incluso antes de que JavaScript hidrate si algún día lo renderizas en servidor.

Prueba:

```tsx
test("muestra el error de validación", async () => {
  const user = userEvent.setup();
  render(<CommentForm />);
  await user.type(screen.getByRole("textbox"), "ok");
  await user.click(screen.getByRole("button", { name: /publicar/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/3 caracteres/);
});
```""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 11-15: useOptimistic, controlado vs no controlado (multiturno), keys por índice, condicionales, dónde vive el estado
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un botón de «me gusta» que tarda medio segundo en reflejarse porque espera al servidor. ¿Cómo hago que se vea instantáneo pero que se revierta si falla? Oí hablar de useOptimistic.",
            },
            {
                "role": "assistant",
                "content": r"""`useOptimistic` mantiene una copia «optimista» del estado que se muestra mientras una acción está en vuelo, y vuelve sola al estado real cuando la acción termina, tanto si tuvo éxito como si falló.

```tsx
import { useOptimistic, useState, startTransition } from "react";

type Post = { id: number; likes: number; likedByMe: boolean };

async function toggleLikeOnServer(id: number, liked: boolean): Promise<Post> {
  const res = await fetch(`/api/posts/${id}/like`, {
    method: liked ? "DELETE" : "POST",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function LikeButton({ initial }: { initial: Post }) {
  const [post, setPost] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  // El segundo argumento calcula el estado optimista a partir del real
  const [optimisticPost, setOptimisticPost] = useOptimistic(post, (current, liked: boolean) => ({
    ...current,
    likedByMe: liked,
    likes: current.likes + (liked ? 1 : -1),
  }));

  function handleClick() {
    const next = !post.likedByMe;
    setError(null);
    startTransition(async () => {
      setOptimisticPost(next); // se pinta ya
      try {
        const saved = await toggleLikeOnServer(post.id, post.likedByMe);
        setPost(saved); // estado real: la copia optimista se descarta
      } catch (err) {
        // Al terminar la transición sin cambiar `post`, React vuelve al valor real
        setError(err instanceof Error ? err.message : "Error desconocido");
      }
    });
  }

  return (
    <div>
      <button onClick={handleClick} aria-pressed={optimisticPost.likedByMe}>
        {optimisticPost.likedByMe ? "♥" : "♡"} {optimisticPost.likes}
      </button>
      {error && <p role="alert">No se guardó: {error}</p>}
    </div>
  );
}
```

Cómo funciona la reversión: `optimisticPost` solo existe mientras dura la transición. Si la petición falla, no llamas a `setPost`, la transición termina y React vuelve a derivar `optimisticPost` del `post` real, que nunca cambió. No escribes código de «deshacer».

Tres detalles que importan:

- **`setOptimisticPost` debe llamarse dentro de una transición** (`startTransition` o una Action de formulario). Fuera de una transición React avisa y el valor se descarta inmediatamente.
- **El estado real se actualiza con la respuesta del servidor**, no con lo que tú calculaste. Si otro usuario dio «me gusta» a la vez, el contador queda bien.
- **Clics rápidos**: cada clic lanza su propia transición y la última respuesta del servidor gana. Si tu API no es idempotente, desactiva el botón mientras `optimisticPost !== post`.

Si usas Next.js, la función `toggleLikeOnServer` sería un Server Action y el `startTransition` lo pone `<form action>` por ti; el `useOptimistic` queda exactamente igual.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Formularios controlados o no controlados? He leído opiniones para todos los gustos y en mi equipo no nos ponemos de acuerdo.",
            },
            {
                "role": "assistant",
                "content": r"""Depende de una sola pregunta: **¿necesitas reaccionar a cada tecla?** Si sí, controlado. Si solo necesitas los valores al enviar, no controlado. No hay una opción «correcta» en abstracto.

**Controlado**: el valor vive en estado de React y el input lo refleja.

```jsx
function Search() {
  const [query, setQuery] = useState("");
  return (
    <input
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      placeholder="Buscar"
    />
  );
}
```

Lo eliges cuando el valor alimenta algo *mientras* se escribe: filtrar una lista, validar en vivo, formatear (tarjeta de crédito con espacios), deshabilitar el botón hasta que sea válido, limitar caracteres.

**No controlado**: el DOM guarda el valor; tú lo lees al enviar.

```jsx
function Signup() {
  function handleSubmit(e) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    console.log(Object.fromEntries(data));
  }
  return (
    <form onSubmit={handleSubmit}>
      <input name="email" type="email" required />
      <input name="password" type="password" minLength={8} required />
      <button>Crear cuenta</button>
    </form>
  );
}
```

Lo eliges para formularios de «rellenar y enviar»: registro, contacto, filtros que se aplican con un botón. Ventajas concretas: cero re-renders por tecla, la validación nativa (`required`, `type`, `minLength`) funciona sola, y `FormData` es exactamente lo que reciben las Actions de React 19 (`<form action={fn}>`), así que este estilo es el que la plataforma empuja ahora.

| Criterio | Controlado | No controlado |
|---|---|---|
| Re-render por tecla | sí | no |
| Validar/formatear en vivo | fácil | difícil |
| Leer todo al enviar | manual (un estado por campo) | `FormData` |
| Formularios grandes (30 campos) | costoso y verboso | natural |
| Reiniciar valores | `setState` | `form.reset()` o cambiar `key` |

Errores típicos de cada bando:

- Controlado con `value` pero sin `onChange`: el campo queda bloqueado. React avisa en consola.
- Pasar de `value={undefined}` a un valor: React cambia el input de no controlado a controlado y avisa. Inicializa siempre con `""`.
- No controlado y leer el valor con `document.querySelector`: usa `FormData` o un `ref`.

Criterio de equipo que suele funcionar: **no controlado por defecto**; controlado solo en los campos concretos que lo necesiten (un formulario puede mezclar ambos). Y para formularios con validación compleja, React Hook Form usa refs por debajo precisamente para evitar el re-render por tecla.""",
            },
            {
                "role": "user",
                "content": "Y si quiero un campo de precio que formatee con separador de miles mientras escribo pero el resto del formulario no controlado, ¿se puede mezclar?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, y es el caso ideal para mezclar. El campo de precio es controlado porque necesita transformar cada tecla; el resto sigue siendo no controlado y se lee con `FormData` al enviar.

El truco es mantener **dos representaciones**: lo que ve el usuario (`"1.234,50"`) y lo que envías (`1234.50`). El input visible es controlado; un `<input type="hidden">` lleva el valor numérico al `FormData` con el nombre que espera tu API.

```jsx
import { useState } from "react";

const formatter = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

function parsePrice(text) {
  // Quita separadores de miles y convierte la coma decimal
  const normalized = text.replace(/\./g, "").replace(",", ".");
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

function PriceInput({ name }) {
  const [text, setText] = useState("");
  const value = parsePrice(text);

  function handleChange(e) {
    const raw = e.target.value.replace(/[^\d,]/g, ""); // solo dígitos y coma
    const n = parsePrice(raw);
    setText(n === null || raw === "" ? raw : formatter.format(n) + (raw.endsWith(",") ? "," : ""));
  }

  return (
    <>
      <input inputMode="decimal" value={text} onChange={handleChange} aria-label="Precio" />
      <input type="hidden" name={name} value={value ?? ""} />
    </>
  );
}

export function ProductForm() {
  function handleSubmit(e) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    console.log(data); // { title: "Silla", price: "1234.5" }
  }
  return (
    <form onSubmit={handleSubmit}>
      <input name="title" required />
      <PriceInput name="price" />
      <button>Guardar</button>
    </form>
  );
}
```

Por qué así y no de otra forma:

- **El hidden input** es lo que hace que el formulario siga siendo «no controlado» desde fuera: `ProductForm` no sabe nada del estado interno de `PriceInput`, solo recibe `price` en el `FormData`. Si mañana `PriceInput` cambia de implementación, el formulario no se toca.
- **`inputMode="decimal"`** abre el teclado numérico en móvil sin usar `type="number"`, que no admite separadores de miles y tiene comportamientos raros con la rueda del ratón.
- **La coma final** se conserva (`raw.endsWith(",")`) para que el usuario pueda escribir `12,` y seguir con los decimales; sin ese detalle, el formateador la borra y el campo parece roto.

Caso límite comprobado: escribir `1234,5` produce `text = "1.234,5"` y `value = 1234.5`; borrar todo deja `text = ""` y `value = ""`, que tu validación de servidor debe tratar como «falta el precio».""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala el problema, explica el porqué y da el arreglo."},
            {
                "role": "user",
                "content": r"""Lista de tareas con un input por fila. Cuando borro la primera tarea, el texto que había escrito en su input se queda en la que ahora es primera. ¿Por qué?

```jsx
function TodoList({ todos, onRemove }) {
  return (
    <ul>
      {todos.map((todo, index) => (
        <li key={index}>
          <span>{todo.title}</span>
          <input placeholder="nota" />
          <button onClick={() => onRemove(todo.id)}>x</button>
        </li>
      ))}
    </ul>
  );
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""**Problema: `key={index}`.** La key es la identidad que React usa para emparejar cada elemento con su instancia anterior. Con el índice, la identidad es la *posición*, no la tarea.

Traza de tu bug: tienes `[A, B]` con keys `0, 1` y escribes «hola» en el input de A. Borras A. El nuevo render produce `[B]` con key `0`. React busca el `<li>` anterior con key `0`, que era el de A, lo reutiliza, le cambia el texto del `<span>` a «B» y conserva su `<input>` con «hola». El `<li>` de key `1` es el que se destruye. Resultado: la nota de A aparece en B.

**Arreglo**: usar un identificador estable del dato.

```jsx
function TodoList({ todos, onRemove }) {
  return (
    <ul>
      {todos.map((todo) => (
        <li key={todo.id}>
          <span>{todo.title}</span>
          <input placeholder="nota" />
          <button onClick={() => onRemove(todo.id)}>x</button>
        </li>
      ))}
    </ul>
  );
}
```

Ahora al borrar A, React no encuentra ningún elemento nuevo con la key de A, destruye su `<li>` (input incluido) y conserva el de B intacto.

Lo que **no** vale como key:

- `Math.random()` o `crypto.randomUUID()` dentro del render: cambia en cada render, React destruye y recrea todas las filas, pierdes el foco y el estado en cada tecla.
- `todo.title`: se repite y cambia al editar.
- Si tus datos no traen id, genera uno **al crear la tarea** (`{ id: crypto.randomUUID(), title }`) y guárdalo con ella.

El índice es aceptable solo cuando la lista es **estática**: nunca se reordena, filtra, inserta ni borra. Una lista de tareas incumple las cuatro.

Segunda observación, independiente de la key: ese `<input>` no controlado no persiste su valor en ningún sitio. Con la key correcta ya no se «mueve», pero se pierde al recargar o si la tarea se desmonta por un filtro. Si la nota forma parte del dato, debería ser `todo.note` con un `onChange` que llame a `onUpdate(todo.id, note)`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Novato aquí. ¿Cómo muestro un componente solo si el usuario está logueado? Y si no lo está, ¿cómo pongo otro? Probé con un if dentro del return y da error de sintaxis.",
            },
            {
                "role": "assistant",
                "content": r"""Dentro del JSX no puedes escribir un `if` porque JSX es una expresión, y `if` es una sentencia. Tienes tres herramientas que sí son expresiones, y una cuarta que es poner el `if` *antes* del `return`.

**1. Operador ternario**: para «si A, esto; si no, aquello».

```jsx
function Header({ user }) {
  return (
    <header>
      {user ? <p>Hola, {user.name}</p> : <LoginButton />}
    </header>
  );
}
```

**2. `&&`**: para «si A, esto; si no, nada».

```jsx
{user && <LogoutButton />}
```

Cuidado con una trampa: si el lado izquierdo es un número `0`, React lo pinta. `{items.length && <List />}` muestra un `0` cuando la lista está vacía. Usa `{items.length > 0 && <List />}`.

**3. `if` antes del `return`** (retorno temprano): para casos grandes o varios niveles.

```jsx
function Dashboard({ user }) {
  if (!user) {
    return <LoginPage />;
  }
  if (!user.emailVerified) {
    return <VerifyEmailNotice email={user.email} />;
  }
  return (
    <main>
      <h1>Panel de {user.name}</h1>
    </main>
  );
}
```

Es la forma más legible cuando cada rama es un componente completo.

**4. Una variable** cuando quieres calcular un trozo y reutilizar el resto del JSX:

```jsx
let status;
if (order.shipped) {
  status = <span>Enviado</span>;
} else if (order.paid) {
  status = <span>Pagado</span>;
} else {
  status = <span>Pendiente</span>;
}
return <li>{order.id} — {status}</li>;
```

Regla práctica: ternario para dos ramas cortas, `&&` para «mostrar o no», retorno temprano para pantallas completas, variable para tres o más casos. Si te encuentras con un ternario dentro de otro, pásalo a variable o a retorno temprano.""",
            },
            {
                "role": "user",
                "content": "¿Y si son como 5 estados distintos (cargando, error, vacío, con datos, sin permisos)? La cadena de if se hace larga.",
            },
            {
                "role": "assistant",
                "content": r"""Con cinco estados, la cadena de `if` sigue siendo correcta, pero hay dos formas de que escale mejor.

**Opción A: un objeto que mapea estado → componente.** Funciona cuando el estado es una cadena discreta.

```jsx
const VIEWS = {
  loading: () => <Spinner />,
  error: ({ error }) => <ErrorMessage error={error} />,
  forbidden: () => <p>No tienes permiso para ver esto.</p>,
  empty: () => <p>Todavía no hay pedidos.</p>,
  ready: ({ orders }) => <OrderTable orders={orders} />,
};

function OrdersPanel({ status, error, orders }) {
  const View = VIEWS[status];
  return <View error={error} orders={orders} />;
}
```

Añadir un estado es añadir una línea al objeto; no tocas el componente.

**Opción B: calcular el estado antes y usar retorno temprano por orden de prioridad.** Es mejor cuando los estados *se derivan* de varios datos y tienen prioridad entre sí (un error manda sobre «vacío»; «sin permisos» manda sobre todo).

```jsx
function OrdersPanel({ user, query }) {
  if (!user.canViewOrders) return <p>No tienes permiso para ver esto.</p>;
  if (query.isPending) return <Spinner />;
  if (query.error) return <ErrorMessage error={query.error} />;
  if (query.data.length === 0) return <p>Todavía no hay pedidos.</p>;
  return <OrderTable orders={query.data} />;
}
```

El orden de los `if` **es** la prioridad, y se lee de arriba abajo como una especificación: «primero permisos, luego carga, luego error, luego vacío». Esto es exactamente lo que devuelve TanStack Query (`isPending`, `error`, `data`), así que encaja sin adaptadores.

Lo que no haría: anidar ternarios (`a ? x : b ? y : z`) ni un `switch` dentro del JSX. Ambos funcionan, pero cuestan de leer y de modificar.

Si varios paneles repiten la misma secuencia (cargando/error/vacío), extrae un componente:

```jsx
function AsyncState({ isPending, error, isEmpty, emptyMessage, children }) {
  if (isPending) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;
  if (isEmpty) return <p>{emptyMessage}</p>;
  return children;
}

<AsyncState isPending={q.isPending} error={q.error} isEmpty={q.data?.length === 0} emptyMessage="Sin pedidos">
  <OrderTable orders={q.data} />
</AsyncState>
```

Ojo con `children` aquí: `<OrderTable orders={q.data} />` se evalúa aunque `isPending` sea `true` (crear el elemento es barato, pero `q.data` será `undefined`). Si `OrderTable` no tolera `undefined`, pasa `children` como función: `{() => <OrderTable orders={q.data} />}` y llámala solo en la rama final.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto front-end. Da criterios concretos, no generalidades."},
            {
                "role": "user",
                "content": "App de React mediana (unas 40 pantallas). Ahora mismo tenemos el carrito, el usuario y las preferencias de UI en un Context gigante y cada cambio re-renderiza media app. ¿Levantar estado, varios contextos o meter Zustand? No quiero sobre-ingeniería.",
            },
            {
                "role": "assistant",
                "content": r"""El problema no es Context en sí: es que un solo contexto mezcla datos con **ritmos de cambio y alcances distintos**. Cualquier consumidor se re-renderiza cuando cambia *cualquier* campo, aunque solo lea uno. La decisión se toma dato por dato con dos preguntas: ¿cada cuánto cambia? y ¿cuántos componentes lo leen, y leen todo o una parte?

| Dato | Cambia | Lo leen | Herramienta |
|---|---|---|---|
| Preferencias de UI (tema, idioma) | casi nunca | casi todos, entero | **Context** pequeño |
| Usuario autenticado | login/logout | muchos, entero | **Context** (o TanStack Query si viene de la API) |
| Carrito | en cada clic | pocos, y **parcial** (el header solo quiere el número de artículos) | **Zustand** con selectores |
| Estado de un formulario o un modal | mucho | hermanos cercanos | **levantar estado** al padre común |

El carrito es el que rompe tu app: cambia a menudo y Context no tiene selectores, así que cada «añadir» despierta a todos los consumidores. Zustand resuelve exactamente eso: cada componente se suscribe al trozo que lee.

```tsx
// stores/cart.ts
import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

type Item = { productId: string; qty: number; price: number };

type CartState = {
  items: Item[];
  add: (item: Omit<Item, "qty">) => void;
  remove: (productId: string) => void;
  clear: () => void;
};

export const useCart = create<CartState>()((set) => ({
  items: [],
  add: (item) =>
    set((s) => {
      const existing = s.items.find((i) => i.productId === item.productId);
      if (existing) {
        return { items: s.items.map((i) => (i.productId === item.productId ? { ...i, qty: i.qty + 1 } : i)) };
      }
      return { items: [...s.items, { ...item, qty: 1 }] };
    }),
  remove: (productId) => set((s) => ({ items: s.items.filter((i) => i.productId !== productId) })),
  clear: () => set({ items: [] }),
}));

// Selectores derivados fuera del componente, reutilizables y testeables
export const selectCount = (s: CartState) => s.items.reduce((n, i) => n + i.qty, 0);
export const selectTotal = (s: CartState) => s.items.reduce((n, i) => n + i.qty * i.price, 0);
```

```tsx
// El header solo se re-renderiza cuando cambia el número de artículos
function CartBadge() {
  const count = useCart(selectCount);
  return <span>{count}</span>;
}

// Varias piezas a la vez sin re-render por objeto nuevo
function CartSummary() {
  const { total, clear } = useCart(useShallow((s) => ({ total: selectTotal(s), clear: s.clear })));
  return <button onClick={clear}>Vaciar ({total.toFixed(2)} €)</button>;
}
```

Verificación: cambiar la cantidad de una línea de 2 a 3 re-renderiza `CartBadge` (la cuenta cambió) pero no un componente que lea `useCart((s) => s.items.length)`, porque la longitud sigue siendo la misma. Con Context, ambos se re-renderizarían.

Plan de migración sin sobre-ingeniería, en este orden:

1. **Saca el carrito** del Context a un store de Zustand. Es el 90 % del problema y son unas 60 líneas.
2. **Divide lo que queda** en dos contextos: `UserContext` y `UiPreferencesContext`. Cambian poco; no necesitan más.
3. **No toques** el estado local de formularios y modales. Levantar estado al padre común sigue siendo la respuesta para hermanos cercanos.

Un matiz: si el carrito del usuario logueado se guarda en la API, la fuente de verdad es el servidor y lo correcto es TanStack Query (`useQuery(["cart"])` + `useMutation` con invalidación). Zustand quedaría solo para el carrito anónimo o para estado puramente de cliente. Decide eso antes de migrar, porque cambia qué código escribes.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 16-23: lazy/Suspense, error boundaries, portales, virtualización (multiturno), Testing Library + MSW,
#        compound components, exhaustive-deps, "Too many re-renders"
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi bundle de producción pesa 1,8 MB y la primera pantalla tarda bastante. Es una SPA con Vite y React Router 7 en modo declarativo. ¿Cómo parto el código por ruta sin que el usuario vea pantallas en blanco al navegar?",
            },
            {
                "role": "assistant",
                "content": r"""Con `lazy` para cada página y un único `<Suspense>` dentro del layout. Vite convierte cada `import()` dinámico en un chunk separado; React solo descarga el de la ruta que se visita.

```tsx
// app.tsx
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router";
import { Layout } from "./layout";
import { PageSkeleton } from "./shared/ui/page-skeleton";

const Dashboard = lazy(() => import("./pages/dashboard"));
const Reports = lazy(() => import("./pages/reports"));
const Settings = lazy(() => import("./pages/settings"));

export function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Suspense fallback={<PageSkeleton />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  );
}
```

Decisiones que evitan la pantalla en blanco:

- **El `<Suspense>` va dentro de `Layout`, no fuera.** Así la cabecera y la navegación siguen pintadas mientras carga la página; solo la zona de contenido muestra el esqueleto. Si envuelves toda la app, cada navegación borra todo.
- **Esqueleto, no spinner.** Un `PageSkeleton` con la forma aproximada de la página evita el salto de layout.
- **Las páginas ya visitadas no vuelven a suspender.** React recuerda el módulo cargado; el fallback aparece una sola vez por chunk.

`lazy` exige un `export default`. Si tus páginas usan exportación con nombre, adapta el import sin tocar el archivo:

```tsx
const Reports = lazy(() => import("./pages/reports").then((m) => ({ default: m.ReportsPage })));
```

Precarga al pasar el ratón por el enlace, para que el chunk ya esté en caché cuando el usuario haga clic:

```tsx
const preloadReports = () => import("./pages/reports");

<Link to="/reports" onMouseEnter={preloadReports} onFocus={preloadReports}>
  Informes
</Link>
```

Un `import()` repetido del mismo módulo devuelve la misma promesa, así que precargar no duplica descargas.

Un caso real que aparece tras el primer despliegue: el usuario tiene la app abierta, publicas una versión nueva, los chunks viejos desaparecen del servidor y al navegar ve `TypeError: Failed to fetch dynamically imported module`. Ponle un error boundary alrededor del `<Suspense>` que recargue la página una vez:

```tsx
import { ErrorBoundary } from "react-error-boundary";

function ChunkFallback({ error }: { error: Error }) {
  if (/dynamically imported module/.test(error.message) && !sessionStorage.getItem("reloaded")) {
    sessionStorage.setItem("reloaded", "1");
    window.location.reload();
  }
  return <p role="alert">No se pudo cargar la página. Recarga para continuar.</p>;
}

<ErrorBoundary FallbackComponent={ChunkFallback}>
  <Suspense fallback={<PageSkeleton />}>…</Suspense>
</ErrorBoundary>
```

Comprobación: ejecuta `npx vite build` y mira la tabla de salida. Debes ver un chunk por página (`reports-[hash].js`, etc.) y el `index-[hash].js` principal mucho más pequeño. Si una página sigue dentro del principal, es que algo la importa de forma estática (un barrel `pages/index.ts` suele ser el culpable): importa cada página por su ruta de archivo.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""En producción, cuando falla el componente de un gráfico, se queda TODA la página en blanco. En consola:

```
Uncaught TypeError: Cannot read properties of undefined (reading 'map')
    at SalesChart (SalesChart.tsx:18)
An error occurred in the <SalesChart> component. Consider adding an error boundary to your tree to customize error handling behavior.
```

¿Cómo aíslo el fallo para que solo se caiga el gráfico? React 19, todo con hooks, preferiría no escribir clases.""",
            },
            {
                "role": "assistant",
                "content": r"""Un error durante el render sin ningún *error boundary* por encima desmonta el árbol entero: eso es la página en blanco. La solución es un boundary alrededor de cada bloque que pueda fallar de forma independiente.

No hay hook para esto: un error boundary sigue siendo una clase con `getDerivedStateFromError`. Pero no tienes que escribirla; `react-error-boundary` la envuelve con una API de función:

```tsx
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

function ChartFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div role="alert">
      <p>El gráfico no se pudo mostrar.</p>
      <button onClick={resetErrorBoundary}>Reintentar</button>
    </div>
  );
}

export function SalesPanel({ period }: { period: string }) {
  return (
    <section>
      <h2>Ventas</h2>
      <ErrorBoundary
        FallbackComponent={ChartFallback}
        resetKeys={[period]}
        onError={(error, info) => reportToSentry(error, { componentStack: info.componentStack })}
      >
        <SalesChart period={period} />
      </ErrorBoundary>
    </section>
  );
}
```

Qué hace cada prop:

- **`FallbackComponent`** recibe el error y `resetErrorBoundary`, que vuelve a montar los hijos.
- **`resetKeys`**: si el usuario cambia de periodo, el boundary se reinicia solo. Sin esto, un fallo con los datos de enero dejaría el gráfico roto aunque pases a febrero.
- **`onError`** es donde envías el error a tu sistema de monitorización. Un boundary sin `onError` convierte errores en silencio.

Dónde colocar los boundaries: en los límites de **unidades que tienen sentido por separado**: cada widget de un panel, cada ruta, el carrito. Uno solo en la raíz evita la pantalla en blanco pero sustituye toda la app por un mensaje de error, que es casi igual de malo.

Lo que un boundary **no** captura, y cómo se cubre cada caso:

| Origen del error | ¿Lo captura? | Qué hacer |
|---|---|---|
| Render, efectos, constructores de hijos | sí | nada más |
| Manejadores de eventos (`onClick`) | no | `try/catch` en el handler y guardar el error en estado |
| Código asíncrono (`fetch`, `setTimeout`) | no | guardar el error en estado o usar `showBoundary` |
| El propio boundary o su fallback | no | que el fallback sea trivial, sin datos |

Para el caso asíncrono, la librería te da `useErrorBoundary`:

```tsx
import { useErrorBoundary } from "react-error-boundary";

function SalesChart({ period }: { period: string }) {
  const { showBoundary } = useErrorBoundary();
  useEffect(() => {
    loadSales(period).then(setData).catch(showBoundary);
  }, [period, showBoundary]);
  // …render del gráfico
}
```

Y para el error concreto del log, arregla la causa además del síntoma: `undefined.map` significa que `SalesChart` renderiza antes de tener datos. Un `if (!data) return <Skeleton />;` al principio lo evita; el boundary es la red de seguridad, no el plan.

Como complemento global, React 19 permite registrar un reportero en la raíz para cualquier error, capturado o no:

```tsx
createRoot(document.getElementById("root")!, {
  onUncaughtError: (error, info) => reportToSentry(error, info),
  onCaughtError: (error, info) => reportToSentry(error, info),
}).render(<App />);
```

Prueba de que el aislamiento funciona:

```tsx
function Bomb(): never {
  throw new Error("boom");
}

test("un widget roto no tumba el resto", () => {
  render(
    <>
      <h1>Panel</h1>
      <ErrorBoundary FallbackComponent={ChartFallback}>
        <Bomb />
      </ErrorBoundary>
    </>
  );
  expect(screen.getByRole("heading", { name: "Panel" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(/no se pudo mostrar/);
});
```""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Hice un modal pero se recorta porque el contenedor padre tiene `overflow: hidden`, y encima queda por debajo del header por el z-index. ¿Cuál es la forma correcta de hacer un modal en React?",
            },
            {
                "role": "assistant",
                "content": r"""Los dos síntomas tienen la misma causa: el modal está **dentro** del árbol DOM del contenedor, así que hereda su recorte y su contexto de apilamiento. La solución es un **portal**: el componente sigue en el árbol de React (conserva contexto, estado y eventos), pero su DOM se inserta en otro sitio, normalmente `document.body`.

Y si además usas el elemento nativo `<dialog>`, el navegador te regala el foco atrapado, el cierre con Escape y el fondo oscurecido en la *top layer*, que está por encima de cualquier `z-index`.

```tsx
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

export function Modal({ open, onClose, title, children }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  // Sincroniza la prop `open` con el estado nativo del <dialog>
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return createPortal(
    <dialog
      ref={dialogRef}
      aria-labelledby="modal-title"
      onClose={onClose}
      onClick={(e) => {
        // Un clic en el fondo tiene como target el propio <dialog>; dentro, el contenido
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-content">
        <h2 id="modal-title">{title}</h2>
        {children}
        <button type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </dialog>,
    document.body,
  );
}
```

Uso:

```tsx
function Products() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ overflow: "hidden" }}>
      <button onClick={() => setOpen(true)}>Nuevo producto</button>
      <Modal open={open} onClose={() => setOpen(false)} title="Nuevo producto">
        <ProductForm onSaved={() => setOpen(false)} />
      </Modal>
    </div>
  );
}
```

Por qué cada pieza:

- **`createPortal(jsx, document.body)`**: el `<dialog>` se monta como hijo de `body`, fuera del `overflow: hidden`. El JSX sigue siendo hijo de `Products` para React: `ProductForm` lee los mismos contextos (tema, router, i18n) que si estuviera en su sitio.
- **`showModal()` en vez de `open`**: solo `showModal()` activa la top layer, atrapa el foco y bloquea la interacción con el resto de la página. Con el atributo `open` tendrías un diálogo no modal.
- **`onClose` del `<dialog>`**: el evento nativo `close` se dispara al pulsar Escape; así tu estado `open` vuelve a `false` y no se desincroniza del DOM.
- **El `<div className="modal-content">`** envuelve el contenido para que un clic dentro no tenga como target el `<dialog>` (el área de padding del dialog cuenta como fondo).

Una sorpresa del portal que conviene conocer: los eventos de React **burbujean por el árbol de React**, no por el DOM. Un `onClick` en `Products` recibe también los clics que ocurren dentro del modal, aunque en el DOM estén en `body`. Casi siempre es lo que quieres (un `onClick` para cerrar menús desplegables lo nota); si no, `e.stopPropagation()` dentro del modal.

Para los tests: jsdom no implementa `showModal`. Añade en el archivo de setup de Vitest:

```ts
HTMLDialogElement.prototype.showModal ??= function () {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close ??= function () {
  this.removeAttribute("open");
  this.dispatchEvent(new Event("close"));
};
```

Con eso, `screen.getByRole("dialog")` encuentra el modal abierto y `await user.keyboard("{Escape}")` no funcionará (es comportamiento del navegador, no de jsdom), así que prueba el cierre con el botón.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una tabla con 12.000 filas que vienen de un CSV cargado en memoria. Al escribir en el campo de filtro va a tirones, casi un segundo por tecla. Ya envolví la fila en `memo` y no cambió nada. ¿Qué más puedo hacer?",
            },
            {
                "role": "assistant",
                "content": r"""`memo` no ayuda porque el filtro cambia **qué filas** se muestran, no sus props: cada tecla produce otra lista y React tiene que crear, mover o destruir miles de nodos DOM. El coste está en pintar 12.000 filas, no en volver a renderizarlas.

Dos palancas, y las dos juntas resuelven el problema:

1. **Virtualizar**: pintar solo las ~30 filas visibles y reciclarlas al hacer scroll.
2. **Diferir el filtrado**: que la tecla se refleje en el input al instante y la lista se actualice después, en un render interrumpible.

```tsx
import { useDeferredValue, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

type Row = { id: string; name: string; amount: number };

const ROW_HEIGHT = 36;

export function BigTable({ rows }: { rows: Row[] }) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const parentRef = useRef<HTMLDivElement>(null);

  // Justificado: filtrar 12.000 filas cuesta milisegundos y no debe repetirse si cambia otra cosa
  const filtered = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();
    return q ? rows.filter((r) => r.name.toLowerCase().includes(q)) : rows;
  }, [rows, deferredQuery]);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  return (
    <>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filtrar por nombre" />
      <p>{filtered.length} filas</p>
      <div ref={parentRef} style={{ height: 600, overflow: "auto" }}>
        <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = filtered[item.index];
            return (
              <div
                key={row.id}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: item.size,
                  transform: `translateY(${item.start}px)`,
                }}
              >
                {row.name} — {row.amount.toFixed(2)}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
```

Cómo funciona:

- **`useVirtualizer`** calcula, a partir del scroll del contenedor, qué índices están visibles (`getVirtualItems`) y la altura total (`getTotalSize`) para que la barra de scroll sea real. Solo esos elementos existen en el DOM: unos 27 (17 visibles + 10 de `overscan`).
- **`useDeferredValue(query)`**: el input es controlado por `query` y se actualiza en el render urgente. `filtered` depende de `deferredQuery`, que React actualiza en un render de baja prioridad; si llega otra tecla antes de terminar, lo descarta y empieza de nuevo. El usuario ve sus letras al momento y la lista «alcanza» al input.
- **`key={row.id}`**, no `item.index`: al filtrar, el índice 0 pasa a ser otra fila; con la key por índice React reutilizaría el nodo equivocado.

Traza de una tecla: `query` cambia → render urgente con la lista anterior (input ya actualizado) → render diferido con el nuevo `filtered` → el virtualizador pide ~27 filas → pintado de ~27 nodos. Antes: 12.000 nodos por tecla.

Verificación: en React DevTools, Profiler, graba mientras escribes. El commit del input debe durar < 5 ms y la lista debe aparecer como un commit separado. Si todavía ves tirones, mira si el contenedor tiene `height` fija: sin ella el virtualizador no sabe qué es «visible» y pinta todo.""",
            },
            {
                "role": "user",
                "content": "Funciona muchísimo mejor. El problema ahora es que algunas filas tienen una celda de comentarios con texto largo y se superponen porque no miden 36 px.",
            },
            {
                "role": "assistant",
                "content": r"""Para alturas variables, el virtualizador tiene que **medir** cada fila en el DOM en vez de confiar en `estimateSize`. Se hace con `measureElement`: le pasas un `ref` a cada fila y le indicas su índice con `data-index`.

Cambios respecto al código anterior:

```tsx
const virtualizer = useVirtualizer({
  count: filtered.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => ROW_HEIGHT, // sigue siendo la estimación inicial; se corrige al medir
  overscan: 10,
  getItemKey: (index) => filtered[index].id,
});

{virtualizer.getVirtualItems().map((item) => {
  const row = filtered[item.index];
  return (
    <div
      key={item.key}
      data-index={item.index}
      ref={virtualizer.measureElement}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        transform: `translateY(${item.start}px)`,
      }}
    >
      <strong>{row.name}</strong> — {row.amount.toFixed(2)}
      <p>{row.comment}</p>
    </div>
  );
})}
```

Tres detalles que hacen que funcione:

- **Quita el `height: item.size`** del estilo. Si fijas la altura, la fila nunca crece y la medición devuelve siempre 36. La fila debe tener la altura que le dé su contenido.
- **`data-index`** es obligatorio: `measureElement` lo lee para saber a qué índice pertenece la medida.
- **`getItemKey`** hace que la caché de medidas siga a la fila cuando el filtro cambia su índice. Sin ello, al filtrar, la altura medida de «Ana» se aplicaría a la fila que ahora ocupa su posición.

Por qué `estimateSize` sigue importando: es lo que el virtualizador usa para las filas que aún no ha medido, incluida la altura total de la barra de scroll. Si tu media real es 60 px, pon 60; una estimación muy baja hace que el scroll «salte» a medida que las filas se miden. Puedes calcularla una vez con la media de longitudes de comentario.

Verificación: haz scroll hasta una fila con comentario largo y vuelve arriba; las filas no deben solaparse ni dejar huecos, y la barra de scroll no debe cambiar de tamaño al pasar por filas ya vistas.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero de QA front-end. Prioriza tests que no se rompan con refactors internos."},
            {
                "role": "user",
                "content": "¿Cómo testeo un componente `UserList` que hace fetch a `/api/users` al montar y muestra la lista o un mensaje de error? Uso Vitest + Testing Library. Ahora mockeo `global.fetch` con `vi.fn()` y cada vez que toco el componente se rompen tres tests.",
            },
            {
                "role": "assistant",
                "content": r"""Mockear `fetch` acopla el test a *cómo* pide los datos el componente (firma de la llamada, orden de los argumentos, forma de la respuesta). Cambia `fetch` por Axios o por TanStack Query y los tests mueren aunque la pantalla siga igual. La alternativa es interceptar **la red**, no la función: MSW responde a la petición HTTP real que haga el componente, use lo que use.

Configuración (MSW 2):

```ts
// src/test/server.ts
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/users", () =>
    HttpResponse.json([
      { id: 1, name: "Ana" },
      { id: 2, name: "Luis" },
    ]),
  ),
];

export const server = setupServer(...handlers);
```

```ts
// src/test/setup.ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

```ts
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"] },
});
```

Los tests, escritos desde el punto de vista del usuario:

```tsx
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { UserList } from "./UserList";

test("muestra los usuarios que devuelve la API", async () => {
  render(<UserList />);
  expect(screen.getByText(/cargando/i)).toBeInTheDocument();

  const items = await screen.findAllByRole("listitem");
  expect(items.map((li) => li.textContent)).toEqual(["Ana", "Luis"]);
});

test("muestra un error si la API falla", async () => {
  server.use(http.get("/api/users", () => HttpResponse.json({ message: "down" }, { status: 500 })));
  render(<UserList />);

  expect(await screen.findByRole("alert")).toHaveTextContent(/no se pudieron cargar/i);
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
});

test("muestra el estado vacío si no hay usuarios", async () => {
  server.use(http.get("/api/users", () => HttpResponse.json([])));
  render(<UserList />);
  expect(await screen.findByText(/no hay usuarios/i)).toBeInTheDocument();
});
```

Por qué estos tests sobreviven a refactors:

- **Consultan por rol y texto** (`findAllByRole("listitem")`, `findByRole("alert")`), que es lo que ve el usuario. No tocan estado interno, ni nombres de clases, ni `data-testid` salvo que no haya otra opción.
- **`findBy*` espera**: resuelve cuando aparece el elemento (hasta 1 s por defecto). Sin `act()` manual, sin `waitFor` con `setTimeout`.
- **`server.use` en el test** sobreescribe un handler solo para ese caso; `resetHandlers` en `afterEach` lo deshace. Los tests no comparten estado.
- **`onUnhandledRequest: "error"`**: si el componente empieza a llamar a un endpoint que no has previsto, el test falla con el nombre de la URL en vez de colgarse esperando.

Lo que **no** tiene test, a propósito: que se llame a `fetch` una vez, con qué cabeceras, o que `useEffect` se ejecute. Eso es implementación. Si mañana `UserList` pasa a `useQuery`, los tres tests siguen verdes sin tocarlos; esa es la prueba de que miden lo correcto.

Una restricción que hay que respetar para que `findByRole("alert")` funcione: el componente debe pintar el error con `role="alert"` y la lista con `<ul>`/`<li>` (o roles equivalentes). Si el test te obliga a añadir semántica, es una mejora de accesibilidad gratis, no una concesión al test.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero un componente de pestañas que se use como el de Radix: `<Tabs defaultValue=\"general\"><Tabs.List><Tabs.Trigger value=\"general\">…</Tabs.Trigger></Tabs.List><Tabs.Content value=\"general\">…</Tabs.Content></Tabs>`. ¿Cómo se implementa ese patrón en React con TypeScript?",
            },
            {
                "role": "assistant",
                "content": r"""Es el patrón **compound components**: un padre que guarda el estado y lo comparte por contexto con hijos que solo saben pintar su parte. El consumidor decide la estructura y el orden; el padre decide el comportamiento.

```tsx
// tabs.tsx
import { createContext, use, useCallback, useId, useMemo, useState, type ReactNode } from "react";

type TabsContextValue = {
  value: string;
  setValue: (next: string) => void;
  baseId: string;
};

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(component: string): TabsContextValue {
  const ctx = use(TabsContext);
  if (ctx === null) throw new Error(`<${component}> debe usarse dentro de <Tabs>`);
  return ctx;
}

type TabsProps = {
  defaultValue: string;
  value?: string;
  onValueChange?: (next: string) => void;
  children: ReactNode;
};

export function Tabs({ defaultValue, value, onValueChange, children }: TabsProps) {
  const [internal, setInternal] = useState(defaultValue);
  const baseId = useId();
  const isControlled = value !== undefined;
  const current = isControlled ? value : internal;

  const setValue = useCallback(
    (next: string) => {
      if (!isControlled) setInternal(next);
      onValueChange?.(next);
    },
    [isControlled, onValueChange],
  );

  // Objeto estable: si el padre de <Tabs> se re-renderiza, los consumidores no se despiertan sin motivo
  const ctx = useMemo(() => ({ value: current, setValue, baseId }), [current, setValue, baseId]);

  return <TabsContext value={ctx}>{children}</TabsContext>;
}

function List({ children }: { children: ReactNode }) {
  return <div role="tablist">{children}</div>;
}

function Trigger({ value, children }: { value: string; children: ReactNode }) {
  const { value: current, setValue, baseId } = useTabsContext("Tabs.Trigger");
  const selected = current === value;
  return (
    <button
      type="button"
      role="tab"
      id={`${baseId}-tab-${value}`}
      aria-selected={selected}
      aria-controls={`${baseId}-panel-${value}`}
      tabIndex={selected ? 0 : -1}
      onClick={() => setValue(value)}
    >
      {children}
    </button>
  );
}

function Content({ value, children }: { value: string; children: ReactNode }) {
  const { value: current, baseId } = useTabsContext("Tabs.Content");
  if (current !== value) return null;
  return (
    <div role="tabpanel" id={`${baseId}-panel-${value}`} aria-labelledby={`${baseId}-tab-${value}`}>
      {children}
    </div>
  );
}

Tabs.List = List;
Tabs.Trigger = Trigger;
Tabs.Content = Content;
```

Uso:

```tsx
<Tabs defaultValue="general">
  <Tabs.List>
    <Tabs.Trigger value="general">General</Tabs.Trigger>
    <Tabs.Trigger value="security">Seguridad</Tabs.Trigger>
  </Tabs.List>
  <Tabs.Content value="general">
    <GeneralSettings />
  </Tabs.Content>
  <Tabs.Content value="security">
    <SecuritySettings />
  </Tabs.Content>
</Tabs>
```

Decisiones:

- **Controlado o no controlado con la misma API.** Si pasas `value`, el padre manda (útil para sincronizar la pestaña con la URL); si no, `Tabs` guarda el estado. `isControlled` se decide por `value !== undefined`, igual que hace un `<input>`.
- **El contexto no se exporta.** `useTabsContext` lanza con el nombre del componente mal colocado; un `<Tabs.Trigger>` fuera de `<Tabs>` falla en el primer render, no en silencio.
- **`useId`** genera ids únicos aunque haya varios `<Tabs>` en la página, y son estables entre servidor y cliente si algún día haces SSR.
- **Roles y `aria-*`** son parte del contrato: `tablist`, `tab`, `tabpanel`, `aria-selected` y `aria-controls` son lo que un lector de pantalla y Testing Library necesitan. El `tabIndex` deja un único tab en el orden de tabulación; la navegación con flechas se añade con un `onKeyDown` en `List` cuando lo necesites.
- **`Tabs.List = List`** sobre una declaración de función es válido en TypeScript (propiedades expando); no hace falta `Object.assign` ni un tipo manual.

Prueba:

```tsx
test("cambia de panel al pulsar una pestaña", async () => {
  const user = userEvent.setup();
  render(
    <Tabs defaultValue="a">
      <Tabs.List>
        <Tabs.Trigger value="a">A</Tabs.Trigger>
        <Tabs.Trigger value="b">B</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="a">Panel A</Tabs.Content>
      <Tabs.Content value="b">Panel B</Tabs.Content>
    </Tabs>,
  );
  expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel A");
  await user.click(screen.getByRole("tab", { name: "B" }));
  expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel B");
  expect(screen.getByRole("tab", { name: "B" })).toHaveAttribute("aria-selected", "true");
});
```""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""ESLint me marca esto:

```
React Hook useEffect has a missing dependency: 'loadData'. Either include it or remove the dependency array  react-hooks/exhaustive-deps
```

Pero si meto `loadData` en el array, el efecto se dispara en bucle. ¿Lo silencio con un `eslint-disable`?

```jsx
function Report({ filters }) {
  const [rows, setRows] = useState([]);

  async function loadData() {
    const res = await fetch(`/api/rows?${new URLSearchParams(filters)}`);
    setRows(await res.json());
  }

  useEffect(() => {
    loadData();
  }, []);

  return <Table rows={rows} />;
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""No lo silencies: la regla tiene razón y el bucle es la pista de que el efecto depende de algo que cambia en cada render.

Qué está pasando: `loadData` se crea de nuevo en cada render (es una función dentro del componente). Si la añades a las dependencias, la secuencia es: efecto → `setRows` → re-render → nueva `loadData` → el efecto ve una dependencia distinta → efecto → bucle. Y con `[]` tienes el bug contrario: el efecto captura la primera `loadData`, que a su vez capturó los primeros `filters`; cuando cambian los filtros, no se recarga nada.

El arreglo es mover la función **dentro** del efecto y declarar las dependencias reales:

```jsx
import { useEffect, useState } from "react";

function Report({ filters }) {
  const [rows, setRows] = useState([]);
  // Primitivo estable: evita re-ejecutar si el padre pasa un objeto nuevo con el mismo contenido
  const query = new URLSearchParams(filters).toString();

  useEffect(() => {
    const controller = new AbortController();

    async function loadData() {
      const res = await fetch(`/api/rows?${query}`, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRows(await res.json());
    }

    loadData().catch((err) => {
      if (err.name !== "AbortError") console.error(err);
    });

    return () => controller.abort();
  }, [query]);

  return <Table rows={rows} />;
}
```

Ahora la regla no se queja (todo lo que usa el efecto está declarado), el efecto se vuelve a ejecutar exactamente cuando cambian los filtros, y la petición anterior se cancela si el usuario cambia rápido.

El detalle de `query`: `filters` es un objeto, y si el padre lo construye inline (`<Report filters={{ year }} />`) es un objeto nuevo en cada render. Dependiendo de `filters` directamente, volverías al bucle. Convertirlo a cadena te da una dependencia que solo cambia cuando cambia el contenido.

Cuando la función **sí** se usa en más sitios (por ejemplo, también desde un botón «Recargar»), tienes dos opciones:

1. **`useCallback`** y añadirla a las dependencias:

```jsx
const loadData = useCallback(async (signal) => {
  const res = await fetch(`/api/rows?${query}`, { signal });
  setRows(await res.json());
}, [query]);

useEffect(() => {
  const controller = new AbortController();
  loadData(controller.signal);
  return () => controller.abort();
}, [loadData]);
```

2. **Separar «reactivo» de «no reactivo»** cuando el efecto debe dispararse por un valor pero leer la última versión de otro sin re-ejecutarse. Ese es el caso de `useEffectEvent` (estable desde React 19.2):

```jsx
import { useEffect, useEffectEvent } from "react";

function Page({ url, theme }) {
  const onVisit = useEffectEvent((visitedUrl) => logVisit(visitedUrl, theme));

  useEffect(() => {
    onVisit(url); // se dispara por `url`; lee el `theme` actual sin depender de él
  }, [url]);
}
```

Las funciones de `useEffectEvent` no van en el array de dependencias y la regla lo sabe. En versiones anteriores a 19.2 el equivalente es guardar la función en un `useRef` actualizado en cada render.

Qué pierdes si pones el `eslint-disable`: nadie te avisa cuando `filters` cambia y la tabla muestra datos viejos. Es el tipo de bug que llega a producción sin que ningún test lo vea.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Soy nuevo en React y me sale este error en cuanto abro la página:

```
Uncaught Error: Too many re-renders. React limits the number of renders to prevent an infinite loop.
```

```jsx
function Filters({ onChange }) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button onClick={setOpen(!open)}>Filtros</button>
      {open && <FilterPanel onApply={onChange} />}
    </div>
  );
}
```

No entiendo qué tiene de malo.""",
            },
            {
                "role": "assistant",
                "content": r"""El problema está en `onClick={setOpen(!open)}`: estás **llamando** a `setOpen` durante el render, en vez de darle al botón una función para que la llame cuando haga clic.

Traza de lo que ocurre: React renderiza `Filters` → al evaluar el JSX ejecuta `setOpen(!open)` → el estado cambia → React vuelve a renderizar → vuelve a ejecutar `setOpen(!open)` → cambia otra vez → … React detecta el bucle y lanza ese error.

El arreglo es envolverlo en una función:

```jsx
<button onClick={() => setOpen(!open)}>Filtros</button>
```

Ahora `onClick` recibe una función que React guarda y ejecuta solo cuando el usuario pulsa. La diferencia:

| Escribes | Qué recibe `onClick` | Cuándo se ejecuta `setOpen` |
|---|---|---|
| `onClick={setOpen(!open)}` | el resultado de llamar a `setOpen` (`undefined`) | en cada render |
| `onClick={() => setOpen(!open)}` | una función | al hacer clic |

Para un interruptor, mejor aún la forma que lee el estado más reciente, por si algún día el clic llega desde un sitio con un valor viejo:

```jsx
<button onClick={() => setOpen((isOpen) => !isOpen)}>Filtros</button>
```

El mismo error aparece con otras dos variantes que verás mucho:

```jsx
// Llamar al handler en vez de pasarlo
<button onClick={handleClick()}>…</button>     // mal
<button onClick={handleClick}>…</button>       // bien

// Cambiar estado directamente en el cuerpo del componente
function Form() {
  const [count, setCount] = useState(0);
  setCount(count + 1); // se ejecuta en cada render: bucle
}
```

Regla para recordarlo: dentro del JSX, `onAlgo={...}` siempre recibe **una función**, nunca el resultado de llamarla. Si ves paréntesis después del nombre y no hay una flecha delante, está mal.

Un error primo de este es `Maximum update depth exceeded`: mismo bucle, pero provocado desde un `useEffect` que actualiza estado sin array de dependencias (o con una dependencia que cambia en cada render). La causa es la misma idea: algo cambia el estado en cada render.""",
            },
        ]
    },
]

# ---------------------------------------------------------------------------
# 24-30: migración de clases (EN, multiturno), TypeScript (EN→ES), estado derivado (multiturno),
#        useTransition vs useDeferredValue (EN), memo roto, useSyncExternalStore (rioplatense), estructura de proyecto
# ---------------------------------------------------------------------------
ROWS += [
    {
        "messages": [
            {
                "role": "user",
                "content": r"""We still have a few class components from 2018. Can you convert this one to hooks and tell me what to watch for in the others?

```jsx
class Clock extends React.Component {
  state = { now: new Date(), tick: 0 };

  componentDidMount() {
    this.start();
  }

  componentDidUpdate(prevProps) {
    if (prevProps.interval !== this.props.interval) {
      clearInterval(this.timer);
      this.start();
    }
  }

  componentWillUnmount() {
    clearInterval(this.timer);
  }

  start() {
    this.timer = setInterval(() => {
      this.setState((s) => ({ now: new Date(), tick: s.tick + 1 }));
    }, this.props.interval);
  }

  render() {
    return <span>{this.state.now.toLocaleTimeString()} ({this.state.tick})</span>;
  }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""The three lifecycle methods collapse into one effect, because they are all doing the same job: keep an interval in sync with `props.interval`.

```jsx
import { useEffect, useState } from "react";

export function Clock({ interval }) {
  const [now, setNow] = useState(() => new Date());
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setNow(new Date());
      setTick((t) => t + 1);
    }, interval);
    return () => clearInterval(id);
  }, [interval]);

  return (
    <span>
      {now.toLocaleTimeString()} ({tick})
    </span>
  );
}
```

How each piece maps:

| Class | Hooks | Why |
|---|---|---|
| `componentDidMount` + `componentDidUpdate(prevProps)` + `componentWillUnmount` | one `useEffect` with `[interval]` | React runs the cleanup and re-runs the effect whenever `interval` changes; the "compare prevProps" code disappears |
| `this.timer` | local `const id` inside the effect | the cleanup closes over it, so no instance field is needed |
| `state = { now, tick }` | two `useState` calls | `setState` merged objects; `useState` replaces, so independent values get independent state |
| `new Date()` in the class field | `useState(() => new Date())` | the lazy initializer runs once; `useState(new Date())` would allocate a Date on every render |
| `setState((s) => …)` | `setTick((t) => t + 1)` | same updater semantics; required here because the interval callback is a stale closure |

Things to watch for in the other components:

1. **`componentDidUpdate` with `prevProps`/`prevState` comparisons** almost always becomes an effect whose dependency array *is* the comparison. If you find yourself needing the previous value inside the effect, that is usually a sign the logic should be derived during render instead.
2. **Instance fields** (`this.timer`, `this.cache`) become `useRef` when they must survive renders and are read outside the effect that created them. If only one effect touches them, keep them local like `id` above.
3. **`this.props.x` read inside a callback** behaved like "latest props" in a class. In a function component the callback captures the render it was created in. Either add the value to the dependencies (the effect restarts) or use `useEffectEvent` (React 19.2+) when you want "latest value, no restart".
4. **`setState(update, callback)`**: the second argument has no equivalent. Move the callback into an effect that depends on the state it was waiting for.
5. **`shouldComponentUpdate` / `PureComponent`** become `memo(Component)`.
6. **Methods bound in the constructor** are just functions now; `bind` goes away.

Classes are still fully supported in React 19, so there is no deadline. Convert when you touch a component for another reason, and keep this regression test around to prove the behavior did not change:

```jsx
test("ticks at the configured interval and restarts when it changes", () => {
  vi.useFakeTimers();
  const { rerender } = render(<Clock interval={1000} />);

  act(() => vi.advanceTimersByTime(3000));
  expect(screen.getByText(/\(3\)/)).toBeInTheDocument();

  rerender(<Clock interval={500} />);
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByText(/\(5\)/)).toBeInTheDocument();
  vi.useRealTimers();
});
```""",
            },
            {
                "role": "user",
                "content": "Two of them are harder: one uses `getDerivedStateFromProps` to reset a draft form whenever `userId` changes, and another has `componentDidCatch`. What do I do with those?",
            },
            {
                "role": "assistant",
                "content": r"""**Resetting state when a prop changes** has a better answer than `getDerivedStateFromProps` ever had: give the component a `key` from the parent.

```jsx
// Parent
<DraftForm key={userId} userId={userId} />
```

When `userId` changes, React unmounts the old `DraftForm` and mounts a fresh one: every `useState` goes back to its initial value, inputs clear, effects restart. No comparison code at all. This is the documented replacement and it works for the whole subtree, not just the fields you remembered to reset.

Use the `key` approach whenever "reset everything" is what you want. If you only need to reset *part* of the state and keep the rest, React allows adjusting state during render by storing the previous prop:

```jsx
function DraftForm({ userId }) {
  const [draft, setDraft] = useState("");
  const [prevUserId, setPrevUserId] = useState(userId);

  if (userId !== prevUserId) {
    // Runs during render; React re-renders immediately with the new state before committing
    setPrevUserId(userId);
    setDraft("");
  }

  return <textarea value={draft} onChange={(e) => setDraft(e.target.value)} />;
}
```

What you must *not* do is the obvious `useEffect(() => setDraft(""), [userId])`: it commits one frame with the old draft under the new user, then re-renders. The render-time version above never shows that frame.

**`componentDidCatch`** has no hook equivalent, and that is deliberate: error boundaries are the one thing that still requires a class. Two options:

1. Keep that single class. It is small, stable and never needs to change.
2. Replace it with `react-error-boundary`, which wraps the class for you and adds `resetKeys`, `onReset` and a `useErrorBoundary` hook for async errors:

```jsx
import { ErrorBoundary } from "react-error-boundary";

<ErrorBoundary
  fallbackRender={({ error, resetErrorBoundary }) => (
    <div role="alert">
      <p>{error.message}</p>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  )}
  onError={(error, info) => report(error, info.componentStack)}
>
  <Dashboard />
</ErrorBoundary>
```

Whatever `componentDidCatch` was doing with the error (logging, Sentry) moves to `onError`. If it was also rendering a fallback via `getDerivedStateFromError`, that is `fallbackRender`.

Quick check for the form: render `<DraftForm key="1" userId="1" />`, type something, rerender with `key="2"`, and assert the textarea is empty. For the boundary, the test from the error-boundary question applies unchanged.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm adding TypeScript to an existing React app. Could you show me, in Spanish please, how to type: props with children, event handlers, a generic list component, and a button component that accepts every prop of a native `<button>`?",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro patrones que cubren casi todo el tipado de componentes. Asumo `@types/react` 19 y `"jsx": "react-jsx"` en el `tsconfig`.

**1. Props con `children`.** `ReactNode` es el tipo correcto: admite elementos, cadenas, números, `null` y arrays de todo eso.

```tsx
import type { ReactNode } from "react";

type CardProps = {
  title: string;
  footer?: ReactNode;
  children: ReactNode;
};

export function Card({ title, footer, children }: CardProps) {
  return (
    <section>
      <h2>{title}</h2>
      {children}
      {footer && <footer>{footer}</footer>}
    </section>
  );
}
```

No uses `React.FC`: no aporta nada en React 19 y oculta la firma real. Tampoco `JSX.Element` para `children`, porque rechaza cadenas y `null`.

**2. Manejadores de eventos.** Si el handler es inline, TypeScript infiere el tipo y no escribes nada. Cuando lo declaras aparte, usa los tipos de `react` con el elemento concreto:

```tsx
import type { ChangeEvent, FormEvent } from "react";

function handleChange(e: ChangeEvent<HTMLInputElement>) {
  console.log(e.target.value); // string, no `any`
}

function handleSubmit(e: FormEvent<HTMLFormElement>) {
  e.preventDefault();
  const data = new FormData(e.currentTarget);
}
```

`e.currentTarget` tiene siempre el tipo del elemento; `e.target` es más amplio porque el evento puede venir de un hijo. Para inputs, `target` también funciona porque React lo tipa como el elemento del handler.

**3. Componente genérico.** La función se declara con un parámetro de tipo y las props lo usan:

```tsx
type ListProps<T> = {
  items: T[];
  getKey: (item: T) => string | number;
  renderItem: (item: T) => ReactNode;
};

export function List<T>({ items, getKey, renderItem }: ListProps<T>) {
  return <ul>{items.map((item) => <li key={getKey(item)}>{renderItem(item)}</li>)}</ul>;
}

// T se infiere como User a partir de `items`; renderItem recibe un User tipado
<List items={users} getKey={(u) => u.id} renderItem={(u) => <span>{u.name}</span>} />;
```

Con una *arrow function* en un archivo `.tsx`, `<T>` se confunde con JSX; escribe `<T,>` o usa `function`, que es más legible.

**4. Extender un `<button>` nativo.** `ComponentProps<"button">` te da todas las props del elemento, `ref` incluido (en React 19 `ref` es una prop normal). Añade las tuyas y pasa el resto con spread:

```tsx
import type { ComponentProps } from "react";

type ButtonProps = ComponentProps<"button"> & {
  variant?: "primary" | "ghost";
  loading?: boolean;
};

export function Button({ variant = "primary", loading = false, disabled, children, ...rest }: ButtonProps) {
  return (
    <button {...rest} className={`btn btn-${variant}`} disabled={disabled || loading} aria-busy={loading}>
      {loading ? "Cargando…" : children}
    </button>
  );
}
```

Ahora `<Button type="submit" onClick={…} variant="ghost" />` tipa cada atributo nativo sin que los declares, y un `variant="danger"` es un error de compilación.

Tres tipos más que vas a necesitar enseguida:

- `useState<User | null>(null)`: el argumento de tipo explícito cuando el valor inicial no basta para inferirlo.
- `useRef<HTMLInputElement>(null)`: el ref de un elemento. En `@types/react` 19, `useRef` exige argumento inicial.
- `ComponentProps<typeof Card>`: las props de un componente propio, para reutilizarlas sin exportar el tipo.

Verificación: `npx tsc --noEmit` debe terminar sin errores con `"strict": true`. Si al activarlo salen cientos de errores, actívalo por archivos con `// @ts-check` o migra carpeta a carpeta; bajar `strict` para que compile es perder lo que viniste a buscar.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo esto y me parece raro, pero funciona:

```jsx
const [items, setItems] = useState([]);
const [total, setTotal] = useState(0);

useEffect(() => {
  setTotal(items.reduce((sum, i) => sum + i.price * i.qty, 0));
}, [items]);
```

¿Está bien hacerlo así?""",
            },
            {
                "role": "assistant",
                "content": r"""Funciona, pero es un patrón que conviene quitar: `total` **no es estado**, es un valor que se calcula a partir de `items`. Guardarlo en estado y sincronizarlo con un efecto tiene tres costes:

1. **Dos renders por cambio.** Al hacer `setItems`, React renderiza con los nuevos `items` y el `total` viejo, ejecuta el efecto, hace `setTotal` y renderiza otra vez. Durante el primer render la pantalla muestra una combinación inconsistente (3 artículos, total de 2).
2. **Dos fuentes de verdad.** Cualquier código que haga `setItems` sin pasar por aquí deja `total` desincronizado.
3. **Más código** para algo que es una línea.

Calcúlalo durante el render:

```jsx
const [items, setItems] = useState([]);
const total = items.reduce((sum, i) => sum + i.price * i.qty, 0);
```

Cada render recalcula `total` con los `items` de ese render: siempre consistente, sin efecto, sin segundo render.

La regla: **si se puede calcular a partir de props o estado, no es estado.** Se aplica igual a `fullName` a partir de `first` y `last`, a `filteredItems` a partir de `items` y `query`, a `isValid` a partir de los campos del formulario. El efecto solo tiene sentido para sincronizar con algo *externo* a React (red, DOM manual, suscripciones), no para derivar datos.""",
            },
            {
                "role": "user",
                "content": "Ya, pero mi cálculo real agrupa unas 5.000 líneas por categoría y se vuelve a ejecutar en cada render, incluso cuando lo que cambia es el texto de un input que está en el mismo componente.",
            },
            {
                "role": "assistant",
                "content": r"""Ahí sí hay un coste real, y hay dos formas de evitarlo. La segunda suele ser mejor que la primera.

**Opción A: `useMemo`.** Memoriza el resultado y solo lo recalcula cuando cambia `items`:

```jsx
const byCategory = useMemo(() => groupByCategory(items), [items]);
```

Escribir en el input re-renderiza el componente, pero `useMemo` ve que `items` es la misma referencia y devuelve el resultado anterior. Esto está justificado porque el cálculo es caro **medido**, no por costumbre.

**Opción B: mover el estado del input hacia abajo.** El input no necesita vivir en el componente que agrupa 5.000 líneas. Si lo extraes a un hijo con su propio estado, teclear solo re-renderiza ese hijo, y el cálculo caro no se toca:

```jsx
function Summary({ items }) {
  const byCategory = groupByCategory(items); // solo cuando cambian los items
  return (
    <>
      <SearchBox onSearch={handleSearch} />
      <CategoryTable groups={byCategory} />
    </>
  );
}

function SearchBox({ onSearch }) {
  const [text, setText] = useState("");
  return <input value={text} onChange={(e) => { setText(e.target.value); onSearch(e.target.value); }} />;
}
```

Esta opción no añade ningún hook de memoización: elimina la causa del re-render en lugar de defenderse de ella. Es la primera que probaría; `useMemo` queda para cuando el estado que cambia *tiene* que vivir en el mismo componente.

Si el proyecto usa el React Compiler, la opción A la aplica él automáticamente y no escribes el `useMemo`; la opción B sigue siendo buena arquitectura con o sin compilador.

Comprobación: en el Profiler, teclear en el input no debe mostrar a `CategoryTable` entre los componentes renderizados.""",
            },
            {
                "role": "user",
                "content": "Última: cuando cambia `customerId` por props quiero vaciar `items`. Eso sí lo hago con otro useEffect, ¿no?",
            },
            {
                "role": "assistant",
                "content": r"""Tampoco. Un `useEffect(() => setItems([]), [customerId])` tiene el mismo defecto del principio: un render con los items del cliente anterior bajo el nuevo `customerId`, y luego otro render vacío. Si en medio hay un fetch, puedes mezclar datos de dos clientes.

La forma correcta es que el **padre** cambie la `key`:

```jsx
<OrderEditor key={customerId} customerId={customerId} />
```

Al cambiar `customerId`, React desmonta el `OrderEditor` viejo y monta uno nuevo: `items` vuelve a `[]`, el input se vacía, los efectos se reinician. Todo el estado interno se reinicia de golpe, sin que `OrderEditor` sepa nada del cambio.

Si solo quieres reiniciar `items` y conservar otro estado (por ejemplo, un filtro de vista), compara la prop con su valor anterior **durante el render**:

```jsx
function OrderEditor({ customerId }) {
  const [items, setItems] = useState([]);
  const [prevCustomerId, setPrevCustomerId] = useState(customerId);

  if (customerId !== prevCustomerId) {
    setPrevCustomerId(customerId);
    setItems([]); // React vuelve a renderizar antes de pintar: no hay frame inconsistente
  }
  // …
}
```

React permite llamar a un setter del propio componente durante el render; descarta la salida y renderiza otra vez con el nuevo estado antes de tocar el DOM. Es exactamente lo que el efecto no puede garantizar.

Elige `key` salvo que tengas una razón concreta para conservar parte del estado. Verificación: con `key`, un test que renderiza con `customerId="1"`, añade un item y re-renderiza con `"2"` debe mostrar la lista vacía en el primer `screen.getByRole("list")`, sin `await`.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "What's the actual difference between `useTransition` and `useDeferredValue`? Both seem to make slow updates non-blocking. When do I pick which?",
            },
            {
                "role": "assistant",
                "content": r"""Both tell React "this update is low priority: render it when nothing urgent is pending, and throw it away if something urgent arrives". The difference is **what you control**.

- `useTransition` wraps an **update** you own: you call `setState` inside `startTransition`.
- `useDeferredValue` wraps a **value** you do not own: a prop from a parent, a value from a library hook, or state you want to keep urgent for one consumer and lazy for another.

**Pick `useTransition` when you trigger the update.** Classic case: switching tabs where the new tab is expensive to render.

```tsx
import { useState, useTransition } from "react";

function Tabs() {
  const [tab, setTab] = useState<"posts" | "stats">("posts");
  const [isPending, startTransition] = useTransition();

  function select(next: typeof tab) {
    startTransition(() => setTab(next)); // the click stays responsive
  }

  return (
    <>
      <nav style={{ opacity: isPending ? 0.6 : 1 }}>
        <button onClick={() => select("posts")}>Posts</button>
        <button onClick={() => select("stats")}>Stats</button>
      </nav>
      {tab === "posts" ? <Posts /> : <HeavyStats />}
    </>
  );
}
```

You also get `isPending` for free, which is the natural place for a subtle loading hint. In React 19, the callback may be `async` (`startTransition(async () => { await save(); setDone(true); })`), which is what Actions are built on.

**Pick `useDeferredValue` when the value arrives from elsewhere.** Classic case: a search box whose text must stay urgent, while the filtered list can lag.

```tsx
function Search({ products }: { products: Product[] }) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  return (
    <>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <ProductList products={products} query={deferredQuery} />
    </>
  );
}
```

`query` updates immediately (the keystroke shows), `deferredQuery` updates in a background render. If `ProductList` is wrapped in `memo`, it does not even re-render until the deferred value lands. React 19 added a second argument, `useDeferredValue(value, initialValue)`, for the first render.

| | `useTransition` | `useDeferredValue` |
|---|---|---|
| You own the `setState` | yes | not necessarily |
| Gives `isPending` | yes | no (compare `value !== deferredValue`) |
| Typical use | navigation, tab switches, submits | derived props, search filters, values from hooks |
| Needs a `memo` consumer to skip work | no | yes, to avoid rendering the heavy child twice |

What neither one does: make the slow render faster. They let React **interrupt** it to handle input, so the UI stays responsive while the work still happens. If the expensive part is a synchronous computation (sorting 100k rows in render), fix that first with `useMemo`, a worker or virtualization; then transitions handle what is left.

Both require concurrent rendering, which you get automatically with `createRoot`. Check it works: in the DevTools Profiler, a transition render shows as a separate, longer commit that starts after the urgent one, and typing in the search box never drops characters.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala el problema, explica el porqué y da el arreglo."},
            {
                "role": "user",
                "content": r"""Puse `memo` en `ProductCard` pero el Profiler dice que se re-renderiza igual en cada cambio del carrito. ¿Qué se me escapa?

```jsx
const ProductCard = memo(function ProductCard({ product, onAdd, style }) {
  return (
    <article style={style}>
      <h3>{product.name}</h3>
      <button onClick={() => onAdd(product.id)}>Añadir</button>
    </article>
  );
});

function Catalog({ products }) {
  const [cart, setCart] = useState([]);
  return (
    <>
      <p>{cart.length} en el carrito</p>
      {products.map((p) => (
        <ProductCard
          key={p.id}
          product={p}
          style={{ marginBottom: 8 }}
          onAdd={(id) => setCart((c) => [...c, id])}
        />
      ))}
    </>
  );
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""**Problema:** `memo` compara cada prop con `Object.is`, y dos de las tres props son **nuevas en cada render** de `Catalog`:

- `style={{ marginBottom: 8 }}`: un objeto literal nuevo en cada render; `{} !== {}`.
- `onAdd={(id) => …}`: una función nueva en cada render.

Con una sola prop distinta, `memo` renderiza. Traza: añades un producto → `setCart` → `Catalog` se re-renderiza → crea un `style` y un `onAdd` nuevos para cada tarjeta → `memo` compara, ve referencias distintas y re-renderiza las 200 tarjetas. El `memo` está costando una comparación y no ahorrando nada.

**Arreglo:** hacer estables las dos props.

```jsx
import { memo, useCallback, useState } from "react";

const CARD_STYLE = { marginBottom: 8 }; // una sola referencia para toda la vida del módulo

const ProductCard = memo(function ProductCard({ product, onAdd }) {
  return (
    <article style={CARD_STYLE}>
      <h3>{product.name}</h3>
      <button onClick={() => onAdd(product.id)}>Añadir</button>
    </article>
  );
});

function Catalog({ products }) {
  const [cart, setCart] = useState([]);
  // Identidad estable: no depende de nada que cambie
  const addToCart = useCallback((id) => setCart((c) => [...c, id]), []);

  return (
    <>
      <p>{cart.length} en el carrito</p>
      {products.map((p) => (
        <ProductCard key={p.id} product={p} onAdd={addToCart} />
      ))}
    </>
  );
}
```

Ahora, al cambiar el carrito, cada `ProductCard` recibe el mismo `product` (la misma referencia del array `products`), el mismo `onAdd` y ninguna prop de estilo: `memo` las compara, coinciden todas y salta el render. El updater funcional en `setCart((c) => …)` es lo que permite que `addToCart` no dependa de `cart` y pueda tener `[]` como dependencias.

Dos cosas más que revisaría antes de dar el `memo` por bueno:

1. **¿`products` es estable?** Si el padre de `Catalog` hace `products.map((p) => ({ ...p, price: fmt(p.price) }))` en su render, cada `product` es un objeto nuevo y volvemos al mismo problema un nivel más arriba. Memoizar se hace de abajo arriba y cada eslabón cuenta.
2. **`children` como JSX** también rompe `memo`: `<ProductCard>{<Badge />}</ProductCard>` crea un elemento nuevo cada vez. Pásalo como dato (`badge="nuevo"`) o acepta el re-render.

Cómo confirmarlo sin adivinar: en React DevTools, ajustes del Profiler, activa «Record why each component rendered while profiling». Al grabar, cada `ProductCard` renderizada muestra la lista exacta de props que cambiaron. Si tras el arreglo la tarjeta no aparece en el commit, el `memo` está haciendo su trabajo.

Nota final: esto es precisamente lo que el React Compiler automatiza (hoisting del objeto constante y memoización del callback). Si lo adoptáis, este `useCallback` sobra; hasta entonces, es necesario.""",
            },
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "Che, necesito un hook `useLocalStorage` para guardar preferencias de usuario, y que si cambio el valor en una pestaña se actualice en las demás. Lo armé con useState + useEffect y a veces queda desincronizado entre pestañas.",
            },
            {
                "role": "assistant",
                "content": r"""Lo que tenés es un almacén **externo** a React (localStorage) y querés que los componentes se suscriban a él. Para eso existe `useSyncExternalStore`: le das una función de suscripción y una que lee el valor actual, y React se encarga de re-renderizar cuando avisás que cambió. Con `useState` + `useEffect` siempre hay una ventana donde el estado de React y el storage no coinciden.

```tsx
import { useCallback, useMemo, useSyncExternalStore } from "react";

const LOCAL_EVENT = "local-storage-change";

function subscribe(callback: () => void) {
  // `storage` llega desde OTRAS pestañas; el evento propio cubre la pestaña actual
  window.addEventListener("storage", callback);
  window.addEventListener(LOCAL_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(LOCAL_EVENT, callback);
  };
}

function readRaw(key: string): string | null {
  return localStorage.getItem(key);
}

export function useLocalStorage<T>(key: string, initial: T) {
  // El snapshot es el string crudo: es comparable con Object.is sin crear objetos nuevos
  const raw = useSyncExternalStore(
    subscribe,
    () => readRaw(key),
    () => null, // snapshot en el servidor: no hay localStorage
  );

  const value = useMemo<T>(() => {
    if (raw === null) return initial;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return initial;
    }
  }, [raw, initial]);

  const setValue = useCallback(
    (next: T | ((prev: T) => T)) => {
      const prevRaw = readRaw(key);
      const prev = prevRaw === null ? initial : (JSON.parse(prevRaw) as T);
      const resolved = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
      localStorage.setItem(key, JSON.stringify(resolved));
      window.dispatchEvent(new Event(LOCAL_EVENT));
    },
    [key, initial],
  );

  return [value, setValue] as const;
}
```

Uso:

```tsx
const [theme, setTheme] = useLocalStorage<"light" | "dark">("theme", "light");
<button onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}>Cambiar tema</button>
```

Fijate en tres decisiones, porque son donde se rompe este hook si lo hacés distinto:

1. **El evento `storage` no se dispara en la pestaña que escribe.** Por eso `setValue` emite un evento propio (`LOCAL_EVENT`) después de guardar: así los componentes de la misma pestaña también se enteran. Las otras pestañas reciben `storage` del navegador.
2. **`getSnapshot` devuelve el string, no el objeto parseado.** React llama a `getSnapshot` varias veces por render y compara con `Object.is`; si devolvés `JSON.parse(raw)` cada vez, es un objeto nuevo siempre, React cree que cambió y entrás en un bucle con el aviso «The result of getSnapshot should be cached». El `useMemo` parsea una sola vez por string distinto.
3. **`setValue` lee el storage, no el closure.** Si usara `value`, un clic rápido dos veces o una escritura desde otra pestaña te dejaría con un `prev` viejo. Leer `localStorage` en el momento de escribir es la fuente de verdad.

Un cuidado con `initial`: si pasás un objeto literal (`useLocalStorage("prefs", { lang: "es" })`), es una referencia nueva en cada render y el `useMemo` se recalcula siempre. Para objetos, declaralo como constante fuera del componente.

El tercer argumento (`() => null`) es el snapshot de servidor: si algún día renderizás con SSR, el servidor no tiene `localStorage`, devuelve `null` y el cliente hidrata con el valor real sin error de hidratación.

Para verificarlo: abrí la app en dos pestañas, cambiá el tema en una y mirá la otra. Tiene que actualizarse sin recargar. Y en la misma pestaña, dos componentes que usen la misma clave tienen que mostrar el mismo valor al instante.""",
            },
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "Vamos a arrancar un proyecto React con Vite y TypeScript: unas 20 pantallas, equipo de 4 personas. ¿Qué estructura de carpetas y qué configuración base recomendás para no arrepentirnos en seis meses?",
            },
            {
                "role": "assistant",
                "content": r"""Organiza por **funcionalidad**, no por tipo de archivo. Con 20 pantallas, las carpetas `components/`, `hooks/` y `utils/` globales se convierten en cajones de 80 archivos donde nadie sabe qué pertenece a qué.

```
src/
  app/                 # arranque: main.tsx, router.tsx, providers.tsx
  pages/               # una carpeta por ruta; solo compone features, sin lógica
    orders/
    customers/
  features/            # cada feature es dueña de su estado, API y componentes
    orders/
      api.ts           # fetchers y queries de TanStack Query
      components/
      hooks/
      types.ts
      index.ts         # ÚNICO punto de entrada público de la feature
    auth/
    customers/
  shared/
    ui/                # botones, modales, inputs: sin conocimiento del negocio
    lib/               # cliente HTTP, formateadores de fecha y moneda
    hooks/             # useDebouncedValue, useMediaQuery
  test/                # setup de Vitest, servidor MSW, utilidades de render
```

Tres reglas que mantienen la estructura sana:

1. **Una feature no importa los internos de otra.** `features/orders` puede importar `features/customers` solo a través de su `index.ts`. Si dos features se necesitan mucho, o son una, o lo común baja a `shared/`.
2. **`shared/` no sabe nada del negocio.** Si `shared/ui/Button` necesita saber qué es un pedido, está en el sitio equivocado.
3. **`pages/` solo compone.** Una página importa componentes de una o varias features y los coloca; la lógica vive en la feature para poder reutilizarla y testearla sin router.

Haz que ESLint vigile la regla 1 en vez de confiar en la revisión de código. Con `eslint-plugin-import`:

```js
// eslint.config.js (flat config)
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import importPlugin from "eslint-plugin-import";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs["recommended-latest"],
  reactRefresh.configs.vite,
  {
    plugins: { import: importPlugin },
    rules: {
      "import/no-restricted-paths": [
        "error",
        {
          zones: [
            { target: "./src/shared", from: "./src/features", message: "shared no depende de features" },
            { target: "./src/features", from: "./src/pages", message: "una feature no importa páginas" },
          ],
        },
      ],
      "no-restricted-imports": [
        "error",
        { patterns: [{ group: ["@/features/*/*"], message: "importa desde el index de la feature" }] },
      ],
    },
  },
);
```

Configuración base, lo mínimo que luego cuesta añadir:

- **Alias `@/`**: `"paths": { "@/*": ["./src/*"] }` en `tsconfig.json` y `vite-tsconfig-paths` en Vite, para no escribir `../../../shared`.
- **TypeScript**: `strict: true`, `noUncheckedIndexedAccess: true` (te obliga a tratar `arr[0]` como posible `undefined`, que es lo que es) y `verbatimModuleSyntax: true` (import de tipos explícito).
- **Vitest + Testing Library** con `environment: "jsdom"`, un `setupFiles` para `jest-dom` y MSW, y un `renderWithProviders` en `src/test/` que envuelva router y query client, para que ningún test monte providers a mano.
- **Datos**: TanStack Query para todo lo que venga del servidor; Zustand solo si aparece estado global *de cliente* real (tema, carrito anónimo). Empezar sin store global es correcto.
- **Variables de entorno**: `import.meta.env.VITE_API_URL`, tipadas en `src/vite-env.d.ts` con una interfaz `ImportMetaEnv`. Sin el prefijo `VITE_` no llegan al cliente, por diseño.
- **Barrels**: un `index.ts` por feature y ninguno más. Un `index.ts` en cada subcarpeta crea importaciones circulares y rompe el tree-shaking.

El trade-off honesto: organizar por feature cuesta más al principio, cuando hay tres pantallas y todo parece «compartido». Compensa a partir de la quinta o sexta feature, que es donde vais a estar en dos meses.

Prueba de que la estructura funciona: elige una feature y pregúntate «si borro `features/orders`, ¿qué se rompe?». La respuesta correcta es «`pages/orders` y nada más». Si se rompe `shared/` o `features/customers`, hay un acoplamiento que corregir ahora, cuando es barato.""",
            },
        ]
    },
]
