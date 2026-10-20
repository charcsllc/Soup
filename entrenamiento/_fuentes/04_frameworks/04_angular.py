"""Angular 18/19: standalone, signals, control flow, @defer, DI, HttpClient e interceptores,
RxJS e interop, formularios tipados, enrutado, OnPush/zoneless, directivas y pipes, testing,
CLI, errores típicos, migración a standalone y NgRx SignalStore."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Standalone + bootstrapApplication + app.config.ts (principiante, system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Voy a empezar un proyecto nuevo con Angular 19 y todos los tutoriales que encuentro usan AppModule. ¿Cómo se arranca hoy una app sin módulos? Quiero rutas y HttpClient desde el principio.",
            },
            {
                "role": "assistant",
                "content": r"""Hoy una app de Angular arranca con `bootstrapApplication` y un objeto `ApplicationConfig` que lista los *providers*; los componentes son standalone y declaran lo que usan en su propio `imports`. `AppModule` ya no hace falta.

Son tres archivos:

```ts
// src/main.ts
import { bootstrapApplication } from "@angular/platform-browser";
import { AppComponent } from "./app/app.component";
import { appConfig } from "./app/app.config";

bootstrapApplication(AppComponent, appConfig).catch((err: unknown) => console.error(err));
```

```ts
// src/app/app.config.ts
import { ApplicationConfig, provideZoneChangeDetection } from "@angular/core";
import { provideHttpClient, withFetch } from "@angular/common/http";
import { provideRouter } from "@angular/router";
import { routes } from "./app.routes";

export const appConfig: ApplicationConfig = {
  providers: [
    // agrupa varios eventos del mismo tick en una sola detección de cambios
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    // HttpClient sobre fetch en lugar de XMLHttpRequest
    provideHttpClient(withFetch()),
  ],
};
```

```ts
// src/app/app.routes.ts
import { Routes } from "@angular/router";
import { HomeComponent } from "./home/home.component";

export const routes: Routes = [
  { path: "", component: HomeComponent },
  { path: "**", redirectTo: "" },
];
```

```ts
// src/app/app.component.ts
import { Component } from "@angular/core";
import { RouterLink, RouterOutlet } from "@angular/router";

@Component({
  selector: "app-root",
  imports: [RouterOutlet, RouterLink], // lo que usa ESTA plantilla, nada más
  template: `
    <nav><a routerLink="/">Inicio</a></nav>
    <router-outlet />
  `,
})
export class AppComponent {}
```

```ts
// src/app/home/home.component.ts
import { Component } from "@angular/core";

@Component({
  selector: "app-home",
  template: `<h1>Hola desde un componente standalone</h1>`,
})
export class HomeComponent {}
```

Lo que conviene entender de cada pieza:

- **`imports` en el componente** sustituye a las `declarations` e `imports` del módulo. Cada componente dice qué directivas, pipes y componentes usa su plantilla; si falta algo, el compilador falla en ese archivo y no en un módulo lejano.
- **`standalone`**: en Angular 19 es el valor por defecto y no se escribe. En Angular 18 tienes que poner `standalone: true` en cada `@Component`; si copias este código a un proyecto 18, añádelo.
- **`provideHttpClient(withFetch())`**: sustituye a `HttpClientModule`. `withFetch` es la opción recomendada si algún día activas SSR. Su único coste real: con `fetch` no hay eventos de progreso de **subida**; si necesitas una barra de progreso al subir archivos, quita `withFetch`.
- **`provideZoneChangeDetection({ eventCoalescing: true })`**: la app sigue usando zone.js (lo normal en 18/19), pero un clic que dispara varios manejadores al burbujear provoca una sola pasada de detección de cambios en vez de varias.

Para crear el proyecto así directamente: `ng new mi-app` en Angular 17+ ya genera esta estructura (sin `app.module.ts`).

Verificación:

1. `ng serve` y abre `http://localhost:4200`: debe verse el título y el enlace.
2. Navega a `/loquesea`: la ruta comodín te devuelve a `/`.
3. En la consola del navegador, en modo desarrollo, `ng.getComponent(document.querySelector("app-root"))` devuelve la instancia de `AppComponent`: confirma que arrancó el componente correcto sin ningún módulo de por medio.""",
            },
        ]
    },
    # 2) Signals: signal/computed/effect; multiturno sobre escribir en effect, linkedSignal y untracked.
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de usar BehaviorSubject para todo el estado. ¿Cómo funcionan `signal`, `computed` y `effect` en Angular y cuándo uso cada uno?",
            },
            {
                "role": "assistant",
                "content": r"""Los tres forman un grafo de dependencias que Angular sigue solo:

- **`signal(valor)`**: estado que cambia. Se lee llamándolo (`count()`) y se escribe con `set` o `update`.
- **`computed(() => ...)`**: valor **derivado** de otros signals. Es de solo lectura, perezoso (no calcula hasta que alguien lo lee) y memorizado (no recalcula si sus dependencias no cambiaron).
- **`effect(() => ...)`**: código que se ejecuta **como consecuencia** de un cambio y que toca algo de fuera: `localStorage`, un log, una librería de gráficos, el DOM manual.

No hay lista de dependencias: lo que lees dentro de `computed` o `effect` queda suscrito.

```ts
import { Component, computed, effect, signal } from "@angular/core";

interface CartItem {
  id: number;
  name: string;
  price: number;
  qty: number;
}

@Component({
  selector: "app-cart",
  template: `
    @for (item of items(); track item.id) {
      <p>{{ item.name }} × {{ item.qty }}</p>
    }
    <p>Total: {{ total() }} €</p>
    <button type="button" (click)="add()">Añadir café</button>
  `,
})
export class CartComponent {
  readonly items = signal<CartItem[]>([]);

  // derivado: se recalcula solo cuando cambia items
  readonly total = computed(() =>
    this.items().reduce((sum, item) => sum + item.price * item.qty, 0),
  );

  constructor() {
    // efecto: sincroniza con algo externo a Angular
    effect(() => {
      localStorage.setItem("cart", JSON.stringify(this.items()));
    });
  }

  add(): void {
    // actualización inmutable: nuevo array
    this.items.update((list) => [...list, { id: Date.now(), name: "Café", price: 3.5, qty: 1 }]);
  }
}
```

Tres cosas que cambian respecto a `BehaviorSubject`:

1. **Igualdad por referencia.** Un signal solo notifica si el valor nuevo es distinto según `Object.is`. Si haces `this.items().push(x)` y luego `this.items.set(this.items())`, la referencia es la misma y nadie se entera. Por eso `update` con un array nuevo.
2. **Lectura síncrona siempre.** Un signal siempre tiene valor; no hay `subscribe`, ni `async` pipe, ni que olvidar `unsubscribe`.
3. **Sin eventos en el tiempo.** Un signal es un valor actual, no un flujo. Si necesitas `debounceTime`, cancelar peticiones o reintentar, eso sigue siendo RxJS (y se conecta con `toSignal`/`toObservable`).

Regla para elegir: si quieres **un valor**, `computed`; si quieres que **pase algo fuera**, `effect`. Si te descubres asignando un signal dentro de un `effect`, casi seguro era un `computed`.

Verificación: añade dos cafés y comprueba que el total pasa a 7 y que en DevTools → Application → Local Storage la clave `cart` contiene dos elementos.""",
            },
            {
                "role": "user",
                "content": "En Angular 18 me salía un error al hacer `set` dentro de un effect y tuve que poner `allowSignalWrites: true`. ¿En 19 sigue igual? Mi caso: tengo una lista de opciones que llega por input y quiero que la opción seleccionada vuelva a la primera cuando cambie la lista.",
            },
            {
                "role": "assistant",
                "content": r"""En Angular 19 escribir signals dentro de un `effect` está permitido por defecto y `allowSignalWrites` quedó deprecado (no hace nada). El error que veías en 18 era `NG0600: Writing to signals is not allowed in a computed or an effect by default`.

Pero que esté permitido no lo convierte en la herramienta correcta para tu caso. Tu «seleccionada» es **estado que depende de otro estado pero que el usuario también puede cambiar**. Para eso Angular 19 trae `linkedSignal` (en *developer preview* en 19, estable después):

```ts
import { Component, input, linkedSignal } from "@angular/core";

@Component({
  selector: "app-option-picker",
  template: `
    @for (option of options(); track option) {
      <button type="button" [class.active]="option === selected()" (click)="selected.set(option)">
        {{ option }}
      </button>
    }
    <p>Seleccionada: {{ selected() }}</p>
  `,
})
export class OptionPickerComponent {
  readonly options = input.required<string[]>();

  // se reinicia cuando cambia options, pero es escribible con set()
  readonly selected = linkedSignal<string[], string>({
    source: this.options,
    computation: (opts, previous) =>
      // si la opción anterior sigue existiendo en la lista nueva, la conservo
      previous && opts.includes(previous.value) ? previous.value : opts[0],
  });
}
```

Por qué no un `effect` con `set`:

- **Momento.** El effect corre después de que cambie la lista, así que hay una pasada de render con la lista nueva y la selección vieja (que puede no existir). `linkedSignal` se recalcula de forma síncrona al leerlo: no existe ese estado intermedio.
- **Grafo legible.** Con `linkedSignal` la relación «selected depende de options» está en la declaración. Con un effect está escondida en el constructor.
- **Bucles.** Un effect que escribe lo que otro lee es la receta clásica de ciclos difíciles de seguir.

Si la selección **no** se pudiera cambiar a mano, ni siquiera haría falta `linkedSignal`: sería `computed(() => this.options()[0])`.

Cuándo sí escribir en un effect: cuando el origen es externo y no hay otra forma, por ejemplo copiar a un signal un valor que llega de una librería de terceros sin API reactiva.

Y `untracked`, para cuando dentro de un effect necesitas leer algo **sin** suscribirte:

```ts
import { effect, untracked } from "@angular/core";

effect(() => {
  const user = this.user(); // dependencia: el efecto se re-ejecuta al cambiar user
  untracked(() => {
    // leer preferences aquí NO crea dependencia
    this.analytics.track("user_changed", { id: user.id, theme: this.preferences().theme });
  });
});
```

Verificación del picker: pasa `["a", "b", "c"]`, selecciona `b`; cambia el input a `["b", "c"]` → sigue `b`; cambia a `["x", "y"]` → pasa a `x`. Con el effect de 18 verías un instante con `b` marcada sobre una lista que no la contiene.""",
            },
        ]
    },
    # 3) input/output/model con transformaciones (system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde con código TypeScript completo y comentarios breves."},
            {
                "role": "user",
                "content": "Necesito un componente selector de cantidad (botones - y +) con label obligatorio, min y max que se puedan pasar como atributos de texto (`min=\"1\"`), un `disabled` que funcione solo poniendo el atributo, two-way binding del valor y un evento cuando se llega al límite. Con la API nueva de signals.",
            },
            {
                "role": "assistant",
                "content": r"""Las piezas: `input.required` para el label, `input` con `transform` para que `min="1"` llegue como número y `disabled` como booleano, `model` para el valor con two-way binding y `output` para el aviso de límite.

```ts
// quantity-picker.component.ts
import { Component, booleanAttribute, input, model, numberAttribute, output } from "@angular/core";

export type QuantityLimit = "min" | "max";

@Component({
  selector: "app-quantity-picker",
  template: `
    <label [attr.for]="inputId()">{{ label() }}</label>
    <button type="button" (click)="change(-1)" [disabled]="disabled() || value() <= min()">−</button>
    <input [id]="inputId()" type="number" [value]="value()" readonly />
    <button type="button" (click)="change(1)" [disabled]="disabled() || value() >= max()">+</button>
  `,
})
export class QuantityPickerComponent {
  // obligatorio: el compilador falla si el padre no lo pasa
  readonly label = input.required<string>();
  readonly inputId = input("quantity");

  // "1" (atributo de texto) se convierte en 1
  readonly min = input(0, { transform: numberAttribute });
  readonly max = input(99, { transform: numberAttribute });

  // <app-quantity-picker disabled /> llega como "" y se convierte en true
  readonly disabled = input(false, { transform: booleanAttribute });

  // model = input + output valueChange: habilita [(value)]
  readonly value = model(1);

  readonly limitReached = output<QuantityLimit>();

  change(delta: number): void {
    const next = this.value() + delta;
    if (next < this.min()) {
      this.limitReached.emit("min");
      return;
    }
    if (next > this.max()) {
      this.limitReached.emit("max");
      return;
    }
    // set en un model notifica al padre
    this.value.set(next);
  }
}
```

```ts
// order-line.component.ts (uso)
import { Component, signal } from "@angular/core";
import { QuantityLimit, QuantityPickerComponent } from "./quantity-picker.component";

@Component({
  selector: "app-order-line",
  imports: [QuantityPickerComponent],
  template: `
    <app-quantity-picker
      label="Cantidad"
      min="1"
      max="10"
      [(value)]="quantity"
      (limitReached)="onLimit($event)"
    />
    <p>Pedido: {{ quantity() }} unidades</p>
    @if (warning()) {
      <p role="alert">{{ warning() }}</p>
    }
  `,
})
export class OrderLineComponent {
  // el two-way binding acepta un WritableSignal directamente
  readonly quantity = signal(2);
  readonly warning = signal("");

  onLimit(limit: QuantityLimit): void {
    this.warning.set(limit === "max" ? "Máximo 10 por pedido" : "Mínimo 1 unidad");
  }
}
```

Decisiones:

- **`transform` en vez de tipar `number | string`**: el componente trabaja siempre con `number`; la conversión vive en un sitio. `numberAttribute` devuelve `NaN` si el texto no es numérico, así que un `min="abc"` desactivaría el botón: es un error del uso, visible enseguida.
- **`model` y no `input` + `output` a mano**: `model` es escribible desde dentro (`set`) y emite `valueChange` automáticamente; un `input()` es de solo lectura.
- **`output` no es un `EventEmitter`**: no expone `subscribe` de RxJS ni hereda de `Subject`; solo `emit`. Menos superficie.

Verificación: pulsa `+` hasta 10 → el botón se desactiva; el `<p>` del padre muestra 10 (prueba de que `[(value)]` fluye hacia arriba). Pon `disabled` sin valor en la etiqueta → ambos botones quedan desactivados.""",
            },
        ]
    },
    # 4) Control flow nuevo: @if/@for/@switch/@let y migración.
    {
        "messages": [
            {
                "role": "user",
                "content": "En el equipo estamos migrando plantillas de `*ngIf` y `*ngFor` al control flow nuevo. ¿Cómo quedan los casos típicos (if con else, for con índice y lista vacía, switch)? Y no entiendo por qué `track` es obligatorio en `@for` si en `*ngFor` el trackBy era opcional.",
            },
            {
                "role": "assistant",
                "content": r"""El control flow con `@` está integrado en el compilador (no hay que importar `NgIf` ni `NgFor`) y cubre los tres casos así:

```html
<!-- if / else if / else; "as" guarda el valor ya comprobado -->
@if (user(); as u) {
  <p>Hola, {{ u.name }}</p>
} @else if (loading()) {
  <app-spinner />
} @else {
  <a routerLink="/login">Inicia sesión</a>
}

<!-- for con variables implícitas y bloque para lista vacía -->
<ul>
  @for (order of orders(); track order.id; let i = $index, total = $count) {
    <li [class.first]="$first">
      {{ i + 1 }}/{{ total }} · {{ order.code }} · {{ order.amount | currency: "EUR" }}
    </li>
  } @empty {
    <li>No hay pedidos todavía.</li>
  }
</ul>

<!-- switch: sin fallthrough, cada @case es un bloque independiente -->
@switch (status()) {
  @case ("paid") { <span class="ok">Pagado</span> }
  @case ("pending") { <span class="warn">Pendiente</span> }
  @default { <span>Desconocido</span> }
}

<!-- @let (Angular 18.1+): variable local de plantilla -->
@let subtotal = cartTotal();
@let shipping = subtotal > 50 ? 0 : 4.99;
<p>Total con envío: {{ subtotal + shipping | currency: "EUR" }}</p>
```

Variables disponibles en `@for`: `$index`, `$first`, `$last`, `$even`, `$odd`, `$count`.

**Por qué `track` es obligatorio.** Cuando la lista cambia, Angular tiene que decidir qué nodos del DOM reutiliza, mueve, crea o destruye. Para eso necesita la identidad de cada elemento. Con `*ngFor` sin `trackBy`, la identidad era la referencia del objeto: si tu servicio vuelve a pedir la lista a la API, cada objeto es nuevo aunque tenga el mismo `id`, y Angular **destruye y recrea todas las filas**. Se pierden el foco, el estado de los inputs y las animaciones, y en listas largas se nota. Era el error más común y casi nadie ponía `trackBy`. Hacerlo obligatorio te fuerza a pensarlo una vez:

- `track item.id`: lo correcto cuando hay identificador estable.
- `track $index`: listas estáticas o de primitivos que nunca se reordenan.
- `track item`: solo si mantienes las mismas referencias entre actualizaciones.

**Migración automática.** No lo hagan a mano:

```bash
ng generate @angular/core:control-flow
```

El schematic convierte `*ngIf`, `*ngFor` y `[ngSwitch]` y, cuando existía `trackBy: trackById`, lo traduce a `track trackById($index, item)`. Donde no había `trackBy`, genera `track $index` o la referencia: revisen esos casos y pásenlos a `track item.id` si los datos vienen de una API.

Dos detalles al migrar:

1. `@if (x; as alias)` solo admite `as` en el primer bloque, no en los `@else if`.
2. Cuando ya no quedan directivas estructurales en un componente, borren `NgIf`, `NgFor` o `CommonModule` de su `imports`; el compilador avisa de imports sin usar.

Verificación de que `track` funciona: en una lista con inputs, escribe algo en la tercera fila y recarga los datos desde el servidor. Con `track order.id` el texto y el foco siguen ahí; con `track order` sobre objetos nuevos, desaparecen. En el panel Elements de DevTools también se ve: con un buen `track` los `<li>` no parpadean al refrescar.""",
            },
        ]
    },
    # 5) @defer: triggers, bloques y por qué no aparece el chunk (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una página de producto con un bloque de reseñas pesadito (usa una librería de gráficos) que está abajo del todo. ¿Cómo uso `@defer` para que no se cargue hasta que el usuario haga scroll?",
            },
            {
                "role": "assistant",
                "content": r"""Es el caso de libro de `@defer (on viewport)`: el compilador saca el componente y sus dependencias a un chunk aparte y solo lo descarga cuando el placeholder entra en pantalla.

```html
<!-- product-page.component.html -->
<app-product-header [product]="product()" />

@defer (on viewport; prefetch on idle) {
  <app-reviews [productId]="product().id" />
} @placeholder (minimum 300ms) {
  <section class="reviews-skeleton">Reseñas</section>
} @loading (after 150ms; minimum 500ms) {
  <app-spinner />
} @error {
  <p>No se pudieron cargar las reseñas. Recarga la página.</p>
}
```

```ts
// product-page.component.ts
import { Component, input } from "@angular/core";
import { ProductHeaderComponent } from "./product-header.component";
import { ReviewsComponent } from "./reviews.component";
import { SpinnerComponent } from "../shared/spinner.component";
import { Product } from "./product.model";

@Component({
  selector: "app-product-page",
  imports: [ProductHeaderComponent, ReviewsComponent, SpinnerComponent],
  templateUrl: "./product-page.component.html",
})
export class ProductPageComponent {
  readonly product = input.required<Product>();
}
```

Qué hace cada parte:

- **`on viewport`**: dispara la carga cuando el placeholder entra en el viewport (usa `IntersectionObserver`). Por eso este trigger **exige `@placeholder`** con un único elemento raíz: es lo que se observa.
- **`prefetch on idle`**: descarga el JavaScript cuando el navegador está ocioso, pero no lo renderiza hasta el trigger principal. Al hacer scroll, aparece al instante.
- **`@placeholder (minimum 300ms)`**: se muestra antes del trigger; `minimum` evita un parpadeo si la carga es casi inmediata.
- **`@loading (after 150ms; minimum 500ms)`**: solo aparece si la carga tarda más de 150 ms y, si aparece, dura al menos 500 ms. Sin `after`, un spinner de 30 ms parpadea.
- **`@error`**: si falla la descarga del chunk (red caída, despliegue nuevo que borró el archivo viejo).

Otros triggers: `on idle` (por defecto), `on interaction` (clic o tecla sobre el placeholder), `on hover`, `on immediate`, `on timer(2s)` y `when condicion()` para una expresión booleana. Se combinan con `;` y basta con que se cumpla uno.

Requisito: lo que va dentro de `@defer` debe ser standalone. Si `ReviewsComponent` fuera declarado en un NgModule, no se puede diferir.

Verificación: `ng build` y mira la tabla «Lazy chunk files» de la salida: debe aparecer un chunk con `ReviewsComponent` y la librería de gráficos. En DevTools → Network, filtra por JS, recarga la página y haz scroll: el chunk se pide en el momento en que el placeholder asoma (o antes, por el `prefetch on idle`).""",
            },
            {
                "role": "user",
                "content": "Lo hice tal cual pero en la salida del build no aparece ningún chunk lazy nuevo y en Network las reseñas vienen en el main. ¿Qué me falta?",
            },
            {
                "role": "assistant",
                "content": r"""Casi seguro `ReviewsComponent` (o la librería de gráficos) se referencia de forma **eager** en algún otro sitio, y entonces el compilador no puede sacarlo del bundle principal. Un `@defer` solo separa las dependencias que se usan **exclusivamente** dentro del bloque. Si falla esa condición, no hay error: compila y carga todo de golpe.

Busca en este orden, de más a menos frecuente:

1. **La misma plantilla usa el componente fuera del `@defer`.** Por ejemplo, `<app-reviews>` aparece también en otro `@if` de la página. Basta una aparición fuera del bloque para que sea eager.
2. **El TypeScript del componente lo referencia como valor.** Una consulta como `viewChild(ReviewsComponent)` o `@ViewChild(ReviewsComponent)`, o usar la clase en código (`instanceof`, un provider). Las referencias solo de tipo (`import type`) no cuentan porque desaparecen al compilar.
3. **Otro componente cargado de forma eager lo importa**, por ejemplo un `SharedComponentsArray` que se usa en el layout. El chunk diferido existe, pero su contenido ya está en el main y esbuild no lo duplica.
4. **La librería de gráficos se importa en un servicio con `providedIn: 'root'`** que inyecta algo eager. El componente se separa, pero el peso de la librería no.

Cómo comprobarlo sin adivinar:

```bash
# busca usos de la clase y del selector fuera de la plantilla diferida
grep -rn "ReviewsComponent\|app-reviews" src/app

# genera estadísticas del bundle para ver qué módulos acaban en cada chunk
ng build --stats-json
```

Con `stats.json` puedes abrir `dist/<app>/stats.json` en un analizador (por ejemplo `npx esbuild-visualizer --metadata dist/<app>/stats.json` o la web de esbuild) y ver en qué chunk está la librería de gráficos.

Arreglo típico del caso 2, el más traicionero:

```ts
// mal: esta consulta obliga a cargar ReviewsComponent de forma eager
readonly reviews = viewChild(ReviewsComponent);
```

Si necesitas hablar con el componente diferido, no lo consultes desde el padre: pásale inputs y escucha sus outputs desde la propia plantilla del bloque `@defer`, que es lo que ya hace `[productId]`.

Una nota de SSR, por si lo activas: en el servidor se renderiza el `@placeholder`, no el contenido diferido. Angular 19 añade hidratación incremental (`hydrate on viewport`, en *developer preview*), que sí renderiza el contenido en el servidor y difiere solo la hidratación; es otra herramienta para otro problema.

Verificación del arreglo: tras quitar la referencia eager, `ng build` debe listar un chunk nuevo en «Lazy chunk files» y el tamaño de `main` debe bajar aproximadamente lo que pesa la librería de gráficos.""",
            },
        ]
    },
    # 6) DI en inglés: providedIn root vs providers de componente vs de ruta; InjectionToken.
    {
        "messages": [
            {
                "role": "user",
                "content": "In Angular, what's the actual difference between `providedIn: 'root'`, putting a service in a component's `providers`, and putting it in a route's `providers`? We have a wizard service and two wizards on the same page are sharing state, which is wrong.",
            },
            {
                "role": "assistant",
                "content": r"""Your wizards share state because the service is a singleton: it is resolved from the root injector, so both wizard instances get the same object. The three options create instances at different levels of the injector tree:

| Where it is provided | Instances | Lifetime | Typical use |
|---|---|---|---|
| `@Injectable({ providedIn: 'root' })` | one for the whole app | app lifetime | API clients, auth, app-wide state |
| `providers` on a route | one per route subtree (environment injector) | while that route config is loaded | feature-wide state for a lazy area |
| `providers` on a component | one per component instance, shared by its children | destroyed with the component | per-widget state: a wizard, a form, a table |

For your case, provide the service on the wizard component:

```ts
// wizard-state.service.ts
import { Injectable, computed, signal } from "@angular/core";

@Injectable() // no providedIn: whoever lists it in providers decides the scope
export class WizardStateService {
  private readonly stepIndex = signal(0);
  readonly step = this.stepIndex.asReadonly();
  readonly isLast = computed(() => this.stepIndex() === 2);

  next(): void {
    this.stepIndex.update((i) => Math.min(i + 1, 2));
  }
}
```

```ts
// wizard.component.ts
import { Component, inject } from "@angular/core";
import { WizardStateService } from "./wizard-state.service";
import { WizardStepComponent } from "./wizard-step.component";

@Component({
  selector: "app-wizard",
  imports: [WizardStepComponent],
  providers: [WizardStateService], // a new instance for every <app-wizard>
  template: `
    <app-wizard-step />
    <button type="button" (click)="state.next()" [disabled]="state.isLast()">Next</button>
  `,
})
export class WizardComponent {
  protected readonly state = inject(WizardStateService);
}
```

```ts
// wizard-step.component.ts: a child gets the SAME instance as its parent wizard
import { Component, inject } from "@angular/core";
import { WizardStateService } from "./wizard-state.service";

@Component({
  selector: "app-wizard-step",
  template: `<p>Step {{ state.step() + 1 }} of 3</p>`,
})
export class WizardStepComponent {
  protected readonly state = inject(WizardStateService);
}
```

How resolution works when `inject(WizardStateService)` runs: Angular walks up the **element injectors** (this component, its parent, and so on up the DOM tree); if none provides the token, it continues through the **environment injectors** (route injector, then root, then platform). If nothing matches, you get `NullInjectorError`. That walk is why the step component finds its own wizard's instance and not the other wizard's.

Two common traps:

- Listing a `providedIn: 'root'` service in a component's `providers` silently creates a **second** instance for that subtree. If someone "fixes" a bug that way, state stops being shared and the bug moves elsewhere.
- Removing `providedIn` (as above) is deliberate: if someone forgets to provide it, they get an immediate `NullInjectorError` instead of an accidental global singleton.

For configuration values, use an `InjectionToken` with a factory, which also makes it tree-shakable and overridable in tests:

```ts
import { InjectionToken } from "@angular/core";

export const API_BASE_URL = new InjectionToken<string>("API_BASE_URL", {
  providedIn: "root",
  factory: () => "/api", // default; override with { provide: API_BASE_URL, useValue: "..." }
});
```

`inject()` also accepts options: `inject(Token, { optional: true })` returns `null` instead of throwing, `{ skipSelf: true }` starts the lookup at the parent (useful for nested wizards that need the outer one).

Verification: render two `<app-wizard>` side by side, click Next on the first only. The first shows "Step 2 of 3", the second still shows "Step 1 of 3". In Angular DevTools, the Injector Tree view shows two `WizardStateService` providers, one under each wizard element.""",
            },
        ]
    },
    # 7) Interceptores funcionales: Bearer, HttpContextToken, 401, retry solo en GET (system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito interceptores en Angular 19 para: meter el token Bearer en todas las peticiones menos en el login, mandar al login si la API responde 401, y reintentar si falla la red o da 5xx. Lo tenía con clases `HttpInterceptor` y me dicen que ahora se hacen con funciones.",
            },
            {
                "role": "assistant",
                "content": r"""Son tres `HttpInterceptorFn`, uno por responsabilidad, registrados con `withInterceptors`. Los interceptores de clase siguen funcionando (con `withInterceptorsFromDi()`), pero los funcionales son la opción recomendada: usan `inject()`, se componen como una lista y no necesitan `HTTP_INTERCEPTORS` con `multi: true`.

```ts
// auth.service.ts (mínimo para el ejemplo)
import { Injectable, signal } from "@angular/core";

@Injectable({ providedIn: "root" })
export class AuthService {
  readonly token = signal<string | null>(null);

  logout(): void {
    this.token.set(null);
  }
}
```

```ts
// http-interceptors.ts
import { HttpContextToken, HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { Router } from "@angular/router";
import { catchError, retry, throwError, timer } from "rxjs";
import { AuthService } from "./auth.service";

// marca por petición: el login la activa para no enviar token
export const SKIP_AUTH = new HttpContextToken<boolean>(() => false);

const MAX_RETRIES = 2;
const BASE_DELAY_MS = 300;

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.context.get(SKIP_AUTH)) {
    return next(req);
  }
  const token = inject(AuthService).token();
  // las peticiones son inmutables: clone devuelve una copia con la cabecera
  return next(token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req);
};

export const unauthorizedInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        auth.logout();
        void router.navigate(["/login"], { queryParams: { returnUrl: router.url } });
      }
      // se relanza siempre: quien hizo la petición decide qué mostrar
      return throwError(() => error);
    }),
  );
};

export const retryInterceptor: HttpInterceptorFn = (req, next) => {
  // solo GET: reintentar un POST puede duplicar un pedido o un cobro
  if (req.method !== "GET") {
    return next(req);
  }
  return next(req).pipe(
    retry({
      count: MAX_RETRIES,
      delay: (error: unknown, retryCount: number) => {
        const transient =
          error instanceof HttpErrorResponse && (error.status === 0 || error.status >= 500);
        // 0 = fallo de red; 5xx = servidor. Un 4xx no mejora reintentando.
        return transient ? timer(BASE_DELAY_MS * 2 ** (retryCount - 1)) : throwError(() => error);
      },
    }),
  );
};
```

```ts
// app.config.ts
import { ApplicationConfig } from "@angular/core";
import { provideHttpClient, withFetch, withInterceptors } from "@angular/common/http";
import { provideRouter } from "@angular/router";
import { routes } from "./app.routes";
import { authInterceptor, retryInterceptor, unauthorizedInterceptor } from "./http-interceptors";

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withFetch(),
      // orden: la petición pasa de izquierda a derecha; la respuesta vuelve al revés
      withInterceptors([authInterceptor, unauthorizedInterceptor, retryInterceptor]),
    ),
  ],
};
```

El login se salta el token así:

```ts
import { HttpClient, HttpContext } from "@angular/common/http";

this.http.post<{ token: string }>("/api/login", credentials, {
  context: new HttpContext().set(SKIP_AUTH, true),
});
```

Decisiones que importan:

- **El orden de la lista.** `retryInterceptor` va el último, es decir, el más cercano a la red: cada reintento repite solo la llamada HTTP, con la cabecera ya puesta, y `unauthorizedInterceptor` ve el resultado final, no cada intento.
- **`HttpContextToken` en vez de comparar URLs.** Un `if (req.url.includes("login"))` se rompe el día que alguien renombra el endpoint; la marca viaja con la petición y es explícita.
- **Backoff exponencial y tope de dos reintentos.** 300 ms y 600 ms: suficiente para un parpadeo de red sin multiplicar la carga cuando el servidor está caído.
- **El 401 se relanza.** Si el interceptor se tragara el error, el componente se quedaría con un *spinner* eterno.

Un caso límite: si llegan cinco 401 a la vez, se navega cinco veces al login. Es inocuo (la navegación a la misma URL se ignora), pero si `logout` hace algo caro, protégelo con una comprobación de `token() !== null`.

Verificación: en DevTools → Network, una petición normal muestra `Authorization: Bearer ...` y la del login no. Con la opción *Offline* activada, un GET aparece tres veces (original + 2 reintentos) y un POST una sola. Los tests automáticos de esto se escriben con `provideHttpClientTesting()` y `HttpTestingController`.""",
            },
        ]
    },
    # 8) switchMap vs mergeMap vs concatMap vs exhaustMap.
    {
        "messages": [
            {
                "role": "user",
                "content": "nunca sé si poner switchMap, mergeMap, concatMap o exhaustMap. tengo un buscador que pega a la API mientras escribes y un botón de guardar que la gente pulsa dos veces. ¿cuál va en cada uno y por qué?",
            },
            {
                "role": "assistant",
                "content": r"""Buscador: `switchMap`. Botón de guardar: `exhaustMap`. Los cuatro operadores transforman cada valor en un observable interno (una petición); se diferencian en **qué hacen si llega un valor nuevo mientras la petición anterior sigue en curso**:

| Operador | Si llega un valor nuevo con una petición en curso | Caso típico |
|---|---|---|
| `switchMap` | cancela la anterior y empieza la nueva | búsqueda, filtros, cargar detalle al cambiar de id |
| `exhaustMap` | ignora el valor nuevo hasta que termine la actual | guardar, login, enviar formulario |
| `concatMap` | lo encola y lo ejecuta cuando termine la actual | autoguardado de cambios en orden, cola de operaciones |
| `mergeMap` | lanza otra en paralelo | subir varios archivos independientes |

El buscador:

```ts
import { Component, inject } from "@angular/core";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { toSignal } from "@angular/core/rxjs-interop";
import { catchError, debounceTime, distinctUntilChanged, map, of, switchMap } from "rxjs";
import { Product, ProductApi } from "./product-api.service";

@Component({
  selector: "app-product-search",
  imports: [ReactiveFormsModule],
  template: `
    <input [formControl]="query" placeholder="Buscar producto" />
    @for (product of results(); track product.id) {
      <p>{{ product.name }}</p>
    }
  `,
})
export class ProductSearchComponent {
  private readonly api = inject(ProductApi);
  readonly query = new FormControl("", { nonNullable: true });

  readonly results = toSignal(
    this.query.valueChanges.pipe(
      map((text) => text.trim()),
      debounceTime(300),          // espera a que deje de teclear
      distinctUntilChanged(),     // "ana" → "anas" → "ana" no repite la búsqueda
      switchMap((text) =>
        text.length < 2
          ? of<Product[]>([])
          // catchError DENTRO: un fallo no mata el flujo de búsquedas siguientes
          : this.api.search(text).pipe(catchError(() => of<Product[]>([]))),
      ),
    ),
    { initialValue: [] as Product[] },
  );
}
```

Por qué `switchMap` aquí: si el usuario escribe «zap» y luego «zapa», la respuesta de «zap» puede llegar **después** que la de «zapa» y pisarla. `switchMap` cancela la petición vieja (HttpClient aborta la petición real), así que solo puede pintarse la última. Con `mergeMap` tendrías exactamente ese bug de carrera.

El botón de guardar:

```ts
import { Component, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { Subject, exhaustMap, finalize } from "rxjs";
import { ProfileApi } from "./profile-api.service";

@Component({
  selector: "app-profile-save",
  template: `<button type="button" (click)="save$.next()" [disabled]="saving()">Guardar</button>`,
})
export class ProfileSaveComponent {
  private readonly api = inject(ProfileApi);
  readonly save$ = new Subject<void>();
  readonly saving = signal(false);

  constructor() {
    this.save$
      .pipe(
        exhaustMap(() => {
          this.saving.set(true);
          return this.api.save().pipe(finalize(() => this.saving.set(false)));
        }),
        takeUntilDestroyed(),
      )
      .subscribe();
  }
}
```

Por qué `exhaustMap`: el segundo clic llega con el primer guardado en vuelo y se descarta. Con `switchMap` cancelarías el primer guardado en el navegador, pero el servidor quizá ya lo procesó: el resultado depende del tiempo. Con `concatMap` guardarías dos veces. El `[disabled]` ayuda, pero no basta: un doble clic rápido entra antes de que Angular repinte el botón.

Atajo mental: «¿me importa solo el último?» → `switchMap`. «¿El primero manda y el resto sobra?» → `exhaustMap`. «¿Todos, en orden?» → `concatMap`. «¿Todos, sin orden?» → `mergeMap` (con límite de concurrencia: `mergeMap(fn, 3)`).

Verificación: en Network, con *throttling* «Slow 3G», escribe rápido en el buscador: verás peticiones marcadas como *(canceled)* y solo la última con respuesta pintada. Haz doble clic en Guardar: una sola petición POST.""",
            },
        ]
    },
    # 9) ERR: suscripciones sin cerrar en ngOnInit.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un dashboard que se actualiza cada 10 segundos. Si entro, salgo a otra ruta y vuelvo tres veces, en la pestaña Network veo 4 peticiones cada 10 s en vez de una, y la app se va poniendo lenta. Este es el componente:

```ts
@Component({
  selector: 'app-dashboard',
  imports: [ReactiveFormsModule],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private api = inject(DashboardApi);
  filter = new FormControl('');
  stats: Stats | null = null;
  results: Order[] = [];

  ngOnInit() {
    interval(10000).subscribe(() => {
      this.api.getStats().subscribe(s => this.stats = s);
    });
    this.filter.valueChanges.subscribe(v => {
      this.api.searchOrders(v ?? '').subscribe(r => this.results = r);
    });
  }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Es una fuga de suscripciones: `interval` no termina nunca y nadie lo cancela al destruir el componente. Cada visita al dashboard crea un intervalo nuevo y los anteriores siguen vivos, cada uno haciendo su petición y escribiendo en una instancia de componente que ya no está en pantalla. Tres visitas previas + la actual = 4 peticiones.

Hay un segundo problema en el filtro: el `subscribe` anidado no cancela nada. Si escribes «ab» y la respuesta de «a» llega después, `results` muestra los pedidos de «a».

Cómo lo distingo:

- **HttpClient** emite una vez y completa: una petición suelta no fuga.
- **`interval`** no completa nunca: sin cancelación explícita vive para siempre.
- **`valueChanges`** completa cuando se destruye el `FormControl`, que aquí se recoge con el componente; la fuga práctica está en el intervalo. Aun así, el `subscribe` anidado es un bug de carrera.

Arreglo recomendado: convertir los flujos en signals con `toSignal`, que se desuscribe solo al destruirse el componente, y aplanar con `switchMap`:

```ts
import { Component, inject } from "@angular/core";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { toSignal } from "@angular/core/rxjs-interop";
import { catchError, debounceTime, of, switchMap, timer } from "rxjs";
import { DashboardApi, Order, Stats } from "./dashboard-api.service";

const REFRESH_MS = 10_000;

@Component({
  selector: "app-dashboard",
  imports: [ReactiveFormsModule],
  template: `
    @if (stats(); as s) {
      <p>Pedidos hoy: {{ s.ordersToday }}</p>
    }
    <input [formControl]="filter" placeholder="Filtrar pedidos" />
    @for (order of results(); track order.id) {
      <p>{{ order.code }}</p>
    }
  `,
})
export class DashboardComponent {
  private readonly api = inject(DashboardApi);
  readonly filter = new FormControl("", { nonNullable: true });

  // timer(0, ...) emite ya y luego cada 10 s; switchMap descarta una petición lenta si llega la siguiente
  readonly stats = toSignal(
    timer(0, REFRESH_MS).pipe(
      switchMap(() => this.api.getStats().pipe(catchError(() => of(null)))),
    ),
    { initialValue: null as Stats | null },
  );

  readonly results = toSignal(
    this.filter.valueChanges.pipe(
      debounceTime(300),
      switchMap((text) => this.api.searchOrders(text).pipe(catchError(() => of<Order[]>([])))),
    ),
    { initialValue: [] as Order[] },
  );
}
```

Por qué así:

- **`toSignal` se desuscribe con el `DestroyRef` del componente.** No hay `ngOnInit`, ni `ngOnDestroy`, ni campos mutables que olvidar.
- **`catchError` dentro del `switchMap`.** Si la API falla una vez, el flujo exterior sigue vivo y el siguiente tick vuelve a intentarlo. Además, si el observable de `toSignal` termina en error, la señal relanza ese error al leerla y rompería la plantilla.
- **`timer(0, ...)` en vez de `interval`.** `interval` espera 10 s antes de la primera carga; `timer(0, ...)` carga al entrar.

Si necesitas efectos secundarios en vez de un valor (escribir en un WebSocket, registrar analítica), la herramienta es `takeUntilDestroyed`:

```ts
import { DestroyRef, inject } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";

private readonly destroyRef = inject(DestroyRef);

ngOnInit(): void {
  this.socket.messages$
    .pipe(takeUntilDestroyed(this.destroyRef)) // en ngOnInit hay que pasar el DestroyRef
    .subscribe((message) => this.log.push(message));
}
```

Dentro del constructor o en un inicializador de campo puedes llamar `takeUntilDestroyed()` sin argumentos; en `ngOnInit` no, porque ya no estás en contexto de inyección.

Verificación: repite la prueba de entrar y salir tres veces. En Network debe quedar una sola petición `stats` cada 10 s mientras estás en el dashboard y ninguna cuando estás en otra ruta. En un test, `fixture.destroy()` seguido de avanzar el reloj con `fakeAsync`/`tick(REFRESH_MS)` no debe provocar llamadas nuevas al espía de `getStats`.""",
            },
        ]
    },
    # 10) toSignal / toObservable; multiturno sobre crear signals en métodos.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuándo tiene sentido seguir con RxJS y cuándo pasarme a signals? Ahora mezclo los dos y no sé si `toSignal` y `toObservable` son un parche o la forma correcta.",
            },
            {
                "role": "assistant",
                "content": r"""Son la forma correcta: Angular los diseñó como el puente entre dos herramientas que resuelven cosas distintas.

- **Signals para estado**: el valor actual de algo (usuario, filtros, carrito, resultados). Lectura síncrona, sin suscripciones, y es lo que la plantilla y la detección de cambios entienden mejor.
- **RxJS para eventos en el tiempo**: esperar a que el usuario deje de escribir, cancelar una petición vieja, reintentar con backoff, combinar WebSockets, limitar frecuencia. Los signals no tienen noción de tiempo ni de cancelación.

El patrón habitual es: estado en signals → `toObservable` → operadores de tiempo → `toSignal` → plantilla.

```ts
import { Component, inject, signal } from "@angular/core";
import { toObservable, toSignal } from "@angular/core/rxjs-interop";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { catchError, debounceTime, of, startWith, switchMap } from "rxjs";
import { Customer, CustomerApi } from "./customer-api.service";

@Component({
  selector: "app-customer-list",
  imports: [ReactiveFormsModule],
  template: `
    <input [formControl]="search" />
    <button type="button" (click)="page.set(page() + 1)">Siguiente</button>
    <p>Buscando «{{ searchText() }}», página {{ page() }}</p>
    @for (customer of customers(); track customer.id) {
      <p>{{ customer.name }}</p>
    }
  `,
})
export class CustomerListComponent {
  private readonly api = inject(CustomerApi);
  readonly search = new FormControl("", { nonNullable: true });
  readonly page = signal(1);

  // valueChanges no emite al suscribirse; startWith lo hace síncrono y requireSync lo garantiza
  readonly searchText = toSignal(this.search.valueChanges.pipe(startWith(this.search.value)), {
    requireSync: true,
  });

  // signal → observable para poder usar debounce y switchMap
  readonly customers = toSignal(
    toObservable(this.page).pipe(
      debounceTime(200),
      switchMap((page) => this.api.list(page).pipe(catchError(() => of<Customer[]>([])))),
    ),
    { initialValue: [] as Customer[] },
  );
}
```

Detalles de cada función:

- **`toSignal(obs$)`** sin opciones devuelve `Signal<T | undefined>`: hasta la primera emisión vale `undefined`. Con `{ initialValue }` el tipo es `Signal<T>`. Con `{ requireSync: true }` también es `Signal<T>`, pero lanza un error si el observable no emite de forma síncrona al suscribirse (útil con `BehaviorSubject` o `startWith`).
- **`toObservable(signal)`** emite a través de un efecto, así que es **asíncrono** y solo emite el último valor: si haces `set(1)`, `set(2)`, `set(3)` en el mismo tick, el observable ve solo `3`. Para estado es lo que quieres; para contar eventos, no.
- Ambos deben llamarse en **contexto de inyección** (inicializador de campo o constructor), porque se atan al `DestroyRef` del componente para limpiar.

Regla práctica: si el valor tiene «ahora», signal. Si importa «cuándo» y «en qué orden», observable. Lo que no compensa es reescribir un servicio RxJS que funciona solo por moda: expón un `toSignal` en el borde donde lo consume la plantilla.

Verificación: escribe en el input y comprueba que `searchText` refleja el texto desde el primer render (gracias a `startWith`); pulsa «Siguiente» tres veces rápido y verás una sola petición en Network (el `debounceTime` de 200 ms agrupa los clics).""",
            },
            {
                "role": "user",
                "content": "Intenté crear el signal dentro de un método `loadCustomer(id)` que llamo desde un click, haciendo `this.customer = toSignal(this.api.get(id))`, y me tira error de contexto de inyección. Le pasé el injector como opción y ya funciona. ¿Está bien así?",
            },
            {
                "role": "assistant",
                "content": r"""Funciona, pero es el diseño equivocado. Pasar `{ injector }` evita el error, pero cada clic crea una suscripción nueva que vive hasta que se destruya el componente, y reemplaza el campo `customer` por otra señal. Si la plantilla leía la señal anterior, Angular tiene que redescubrir dependencias en cada clic. Diez clics son diez suscripciones vivas.

El error te avisaba de algo real: `toSignal` está pensado para crearse **una vez** y quedarse escuchando. Lo que cambia con el clic no es la señal, es su **fuente**. Modela el id como estado y deriva el cliente de él:

```ts
import { Component, inject, signal } from "@angular/core";
import { toObservable, toSignal } from "@angular/core/rxjs-interop";
import { catchError, filter, of, switchMap } from "rxjs";
import { Customer, CustomerApi } from "./customer-api.service";

@Component({
  selector: "app-customer-detail",
  template: `
    <button type="button" (click)="selectedId.set(42)">Cargar cliente 42</button>
    @if (customer(); as c) {
      <h2>{{ c.name }}</h2>
    } @else if (selectedId() !== null) {
      <p>Cargando…</p>
    }
  `,
})
export class CustomerDetailComponent {
  private readonly api = inject(CustomerApi);
  readonly selectedId = signal<number | null>(null);

  // se crea una sola vez; switchMap cancela la carga anterior si el id cambia
  readonly customer = toSignal(
    toObservable(this.selectedId).pipe(
      filter((id): id is number => id !== null),
      switchMap((id) => this.api.get(id).pipe(catchError(() => of(null)))),
    ),
    { initialValue: null as Customer | null },
  );

  loadCustomer(id: number): void {
    this.selectedId.set(id);
  }
}
```

Lo que ganas frente a tu versión:

- **Una suscripción** durante toda la vida del componente, cancelada con él.
- **Cancelación**: si el usuario pulsa dos clientes seguidos, `switchMap` aborta la primera petición; con tu versión las dos llegan y gana la que tarde más.
- **Lecturas antes de emitir controladas**: `initialValue: null` deja claro el estado «sin datos», y la plantilla lo trata con `@if`. Sin `initialValue`, la señal sería `Customer | undefined` y la primera lectura daría `undefined` aunque el id ya esté puesto.

Cuándo sí está justificado `{ injector }`: código que de verdad se ejecuta fuera de un constructor pero crea la señal una única vez, por ejemplo una función de utilidad llamada desde `ngOnInit` porque necesita un input ya resuelto. Aun así, en Angular 17.1+ con `input()` casi nunca hace falta esperar a `ngOnInit`.

Verificación: añade un `console.count("subscribe")` dentro de `switchMap` y un `finalize(() => console.count("finalize"))` al observable de la petición. Con el diseño nuevo, pulsar dos clientes rápido muestra dos `subscribe` y un `finalize` del primero (cancelado) antes de que termine el segundo; con tu versión, ningún `finalize` se adelanta.""",
            },
        ]
    },
    # 11) Formularios reactivos tipados con validador de grupo (system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Formulario de registro en Angular 19: email, contraseña, confirmación y aceptar términos. Quiero formularios reactivos tipados de verdad (nada de `any`), validar que las dos contraseñas coincidan y mostrar los errores debajo de cada campo solo cuando el usuario ya tocó el campo.",
            },
            {
                "role": "assistant",
                "content": r"""Con `NonNullableFormBuilder` los tipos se infieren solos desde los valores iniciales, y la coincidencia de contraseñas va en un **validador de grupo**, porque depende de dos controles a la vez.

```ts
// register.component.ts
import { ChangeDetectionStrategy, Component, inject, output } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';

// Validador de grupo: compara dos controles hermanos
export function matchFields(field: string, confirmField: string): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const value = group.get(field)?.value;
    const confirm = group.get(confirmField)?.value;
    return value && confirm && value !== confirm ? { fieldsMismatch: true } : null;
  };
}

export interface RegisterPayload {
  email: string;
  password: string;
  acceptTerms: boolean;
}

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule],
  templateUrl: './register.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegisterComponent {
  private readonly fb = inject(NonNullableFormBuilder);

  // El padre decide qué hacer (llamar a la API, navegar); este componente solo valida
  readonly registered = output<RegisterPayload>();

  readonly form = this.fb.group(
    {
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(12)]],
      confirmPassword: ['', Validators.required],
      acceptTerms: [false, Validators.requiredTrue],
    },
    { validators: matchFields('password', 'confirmPassword') },
  );

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched(); // enseña de golpe todos los errores pendientes
      return;
    }
    const { email, password, acceptTerms } = this.form.getRawValue();
    this.registered.emit({ email, password, acceptTerms });
  }
}
```

```html
<!-- register.component.html -->
<form [formGroup]="form" (ngSubmit)="submit()" novalidate>
  <label for="email">Email</label>
  <input id="email" type="email" formControlName="email" autocomplete="email" />
  @if (form.controls.email.touched && form.controls.email.errors; as errors) {
    @if (errors['required']) {
      <p class="error">El email es obligatorio.</p>
    } @else if (errors['email']) {
      <p class="error">El formato del email no es válido.</p>
    }
  }

  <label for="password">Contraseña</label>
  <input id="password" type="password" formControlName="password" autocomplete="new-password" />
  @if (form.controls.password.touched && form.controls.password.errors; as errors) {
    @if (errors['required']) {
      <p class="error">La contraseña es obligatoria.</p>
    } @else if (errors['minlength']) {
      <p class="error">Mínimo {{ errors['minlength'].requiredLength }} caracteres.</p>
    }
  }

  <label for="confirm">Repite la contraseña</label>
  <input id="confirm" type="password" formControlName="confirmPassword" autocomplete="new-password" />
  @if (form.controls.confirmPassword.touched && form.hasError('fieldsMismatch')) {
    <p class="error">Las contraseñas no coinciden.</p>
  }

  <label>
    <input type="checkbox" formControlName="acceptTerms" />
    Acepto los términos
  </label>
  @if (form.controls.acceptTerms.touched && form.controls.acceptTerms.hasError('required')) {
    <p class="error">Tienes que aceptar los términos.</p>
  }

  <button type="submit">Crear cuenta</button>
</form>
```

Las decisiones y por qué:

- **`NonNullableFormBuilder`.** Con el `FormBuilder` normal, cada control es `FormControl<string | null>` porque `reset()` lo deja en `null`. Con la versión *non-nullable*, `reset()` vuelve al valor inicial y el tipo queda `FormControl<string>`. `form.controls.email` autocompleta y un `form.controls.emial` no compila.
- **`getRawValue()` y no `value`.** `value` es `Partial<…>` porque excluye los controles deshabilitados; `getRawValue()` devuelve el objeto completo con tipos exactos.
- **El error de coincidencia vive en el grupo**, no en `confirmPassword`; por eso la plantilla pregunta `form.hasError('fieldsMismatch')`. El validador devuelve `null` mientras alguno de los dos esté vacío, para no gritar «no coinciden» antes de tiempo.
- **`touched` en vez de `dirty`.** `touched` se activa al salir del campo: el usuario no ve errores mientras escribe la primera vez, pero sí en cuanto abandona el campo. `markAllAsTouched()` en el submit cubre al que pulsa el botón sin tocar nada.
- **`Validators.requiredTrue`** para el checkbox: su error se llama `required`, no `requiredTrue`.
- **`novalidate`** apaga los globos nativos del navegador para que solo se vean tus mensajes. La validación que cuenta sigue estando en el servidor.

Verificación del validador sin montar el componente (funciona igual con Jasmine o Jest):

```ts
import { FormControl, FormGroup } from '@angular/forms';
import { matchFields } from './register.component';

describe('matchFields', () => {
  it('detecta contraseñas distintas y se limpia al corregirlas', () => {
    const group = new FormGroup(
      { password: new FormControl('correct-horse-1'), confirmPassword: new FormControl('otra-cosa') },
      { validators: matchFields('password', 'confirmPassword') },
    );
    expect(group.hasError('fieldsMismatch')).toBe(true);

    group.controls.confirmPassword.setValue('correct-horse-1');
    expect(group.hasError('fieldsMismatch')).toBe(false);
  });
});
```""",
            },
        ]
    },
    # 12) FormArray dinámico + validador asíncrono con debounce y cancelación (avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un formulario de pedido: email del cliente y una lista de líneas (producto, cantidad) donde se pueden añadir y quitar líneas. El email hay que validarlo contra la API para ver si el cliente existe, pero no quiero una petición por cada tecla. ¿Cómo lo armo con formularios tipados?",
            },
            {
                "role": "assistant",
                "content": r"""Dos piezas: un `FormArray` tipado de `FormGroup` para las líneas y un `AsyncValidatorFn` que espera 400 ms antes de llamar a la API. El truco del debounce es que Angular **se desuscribe del validador asíncrono anterior** cada vez que el valor cambia, así que un `timer` dentro del validador hace de debounce y de cancelación a la vez.

```ts
// order-form.component.ts
import { ChangeDetectionStrategy, Component, inject, output } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import {
  AbstractControl,
  AsyncValidatorFn,
  FormArray,
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Observable, catchError, map, of, switchMap, timer } from 'rxjs';

type OrderLineForm = FormGroup<{
  productId: FormControl<string>;
  quantity: FormControl<number>;
}>;

export interface OrderPayload {
  customerEmail: string;
  lines: { productId: string; quantity: number }[];
}

const EMAIL_CHECK_DELAY_MS = 400;

function customerExistsValidator(http: HttpClient): AsyncValidatorFn {
  return (control: AbstractControl<string>): Observable<ValidationErrors | null> =>
    timer(EMAIL_CHECK_DELAY_MS).pipe(
      // Si el valor cambia antes de 400 ms, Angular se desuscribe y esto nunca llega a ejecutarse
      switchMap(() =>
        http.get<{ exists: boolean }>('/api/customers/exists', {
          params: new HttpParams().set('email', control.value),
        }),
      ),
      map((res) => (res.exists ? null : { customerNotFound: true })),
      catchError(() => of({ customerCheckFailed: true })),
    );
}

@Component({
  selector: 'app-order-form',
  imports: [ReactiveFormsModule],
  templateUrl: './order-form.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrderFormComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly http = inject(HttpClient);

  readonly submitted = output<OrderPayload>();

  readonly form = this.fb.group({
    customerEmail: this.fb.control('', {
      validators: [Validators.required, Validators.email],
      asyncValidators: [customerExistsValidator(this.http)],
    }),
    lines: this.fb.array<OrderLineForm>([this.createLine()], Validators.minLength(1)),
  });

  get lines(): FormArray<OrderLineForm> {
    return this.form.controls.lines;
  }

  createLine(): OrderLineForm {
    return this.fb.group({
      productId: ['', Validators.required],
      quantity: [1, [Validators.required, Validators.min(1), Validators.max(99)]],
    });
  }

  addLine(): void {
    this.lines.push(this.createLine());
  }

  removeLine(index: number): void {
    if (this.lines.length > 1) this.lines.removeAt(index);
  }

  submit(): void {
    if (this.form.pending) return; // la comprobación del email sigue en curso
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.submitted.emit(this.form.getRawValue());
  }
}
```

```html
<!-- order-form.component.html -->
<form [formGroup]="form" (ngSubmit)="submit()">
  <label for="email">Email del cliente</label>
  <input id="email" type="email" formControlName="customerEmail" />
  @let email = form.controls.customerEmail;
  @if (email.pending) {
    <small>Comprobando…</small>
  }
  @if (email.touched && email.hasError('customerNotFound')) {
    <p class="error">No existe ningún cliente con ese email.</p>
  }
  @if (email.hasError('customerCheckFailed')) {
    <p class="error">No se pudo comprobar el email. Inténtalo de nuevo.</p>
  }

  <div formArrayName="lines">
    @for (line of lines.controls; track line; let i = $index) {
      <fieldset [formGroupName]="i">
        <legend>Línea {{ i + 1 }}</legend>
        <input formControlName="productId" placeholder="SKU" />
        <input type="number" formControlName="quantity" min="1" max="99" />
        <button type="button" (click)="removeLine(i)" [disabled]="lines.length === 1">Quitar</button>
      </fieldset>
    }
  </div>

  <button type="button" (click)="addLine()">Añadir línea</button>
  <button type="submit" [disabled]="form.pending">Enviar pedido</button>
</form>
```

Puntos finos:

- **Los validadores asíncronos solo corren si los síncronos pasan.** Con un email mal formado no sale ninguna petición: `required` y `email` cortan antes.
- **`track line`** usa la identidad del `FormGroup`, que es estable mientras la línea exista. Con `track $index`, al quitar la línea 2 Angular reutilizaría el DOM de la 3 para la 2.
- **`catchError` → `customerCheckFailed`.** Si la API cae, el formulario queda inválido y no se envía. Es una decisión de negocio: la alternativa es devolver `null` y dejar que el servidor rechace el pedido al final. Elige la tuya, pero que sea explícita.
- **`type="number"` vacío produce `null`** aunque el tipo diga `number`; el `Validators.required` de `quantity` cubre ese caso.
- **`@let`** (Angular 18.1+, estable en 19) evita repetir `form.controls.customerEmail` en cada condición.
- **Alternativa sin timer:** `updateOn: 'blur'` en el control valida solo al salir del campo. Menos peticiones todavía, pero el usuario no ve el aviso hasta que cambia de campo. El `timer` da respuesta mientras escribe.

Verificación en DevTools → Network: escribe un email completo de corrido; sale **una** petición a `/api/customers/exists` unos 400 ms después de dejar de teclear. Escribe, para 200 ms y sigue: no sale ninguna intermedia. Añade tres líneas, borra la segunda y comprueba que la tercera conserva su producto y su cantidad.""",
            },
        ]
    },
    # 13) Enrutado: loadComponent/loadChildren y withComponentInputBinding (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "mi app de angular 19 tiene todas las rutas cargadas de golpe y el main pesa 1,8 MB. ¿como hago lazy loading de las páginas? tambien quiero leer el `:id` de `/products/:id` sin inyectar ActivatedRoute en todos lados",
            },
            {
                "role": "assistant",
                "content": r"""Cambia `component:` por `loadComponent:` (o `loadChildren:` para una sección entera) y activa `withComponentInputBinding()`: con eso, `:id` llega directamente a un `input()` del componente.

```ts
// app.routes.ts
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'products',
    loadComponent: () => import('./products/product-list.component').then((m) => m.ProductListComponent),
  },
  {
    path: 'products/:id',
    loadComponent: () => import('./products/product-detail.component').then((m) => m.ProductDetailComponent),
  },
  {
    // Una sección entera con sus propias rutas: un chunk para todo /admin
    path: 'admin',
    loadChildren: () => import('./admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  {
    path: '**',
    loadComponent: () => import('./not-found.component').then((m) => m.NotFoundComponent),
  },
];
```

```ts
// admin/admin.routes.ts
import { Routes } from '@angular/router';

export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./admin-dashboard.component').then((m) => m.AdminDashboardComponent),
  },
  {
    path: 'users',
    loadComponent: () => import('./admin-users.component').then((m) => m.AdminUsersComponent),
  },
];
```

```ts
// app.config.ts
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch()),
  ],
};
```

```ts
// products/product-detail.component.ts
import { ChangeDetectionStrategy, Component, Injectable, inject, input } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { switchMap } from 'rxjs';

export interface Product {
  id: string;
  name: string;
  price: number;
}

@Injectable({ providedIn: 'root' })
export class ProductService {
  private readonly http = inject(HttpClient);

  getById(id: string) {
    return this.http.get<Product>(`/api/products/${encodeURIComponent(id)}`);
  }
}

@Component({
  selector: 'app-product-detail',
  template: `
    @if (product(); as p) {
      <h1>{{ p.name }}</h1>
      <p>{{ p.price }} €</p>
    } @else {
      <p>Cargando…</p>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductDetailComponent {
  private readonly products = inject(ProductService);

  // Llega de :id gracias a withComponentInputBinding; el nombre del input = nombre del parámetro
  readonly id = input.required<string>();

  readonly product = toSignal(
    toObservable(this.id).pipe(switchMap((id) => this.products.getById(id))),
    { initialValue: null },
  );
}
```

Lo que conviene saber:

- **Cada `import()` dinámico es un chunk aparte.** El router lo descarga la primera vez que se navega a esa ruta. Pero si `ProductDetailComponent` se importa de forma normal en cualquier otro archivo (un `imports: [...]` de otro componente, un barrel `index.ts`), vuelve al bundle principal. Revisa los barrels: son la causa número uno de que el lazy loading «no funcione».
- **`withComponentInputBinding()`** enlaza a inputs los parámetros de ruta, los query params, `data` y los resultados de resolvers, por nombre.
- **Por qué `toObservable` + `switchMap` y no leer el id una vez.** Al pasar de `/products/1` a `/products/2`, Angular **reutiliza** la misma instancia del componente y solo cambia el input. Con `switchMap`, el cambio de id lanza la nueva petición y cancela la anterior si seguía en vuelo.
- **`**` siempre al final**: el router prueba las rutas en orden y el comodín lo atrapa todo.
- Si quieres que los chunks se descarguen en segundo plano tras el arranque, añade `withPreloading(PreloadAllModules)` a `provideRouter`.

Verificación: ejecuta `ng build` antes y después. En la salida, «Initial chunk files» debe bajar y aparecer una sección «Lazy chunk files» con `product-detail-component`, `admin-routes`, etc. En el navegador, Network muestra cada chunk solo al entrar en su ruta, y navegar de un producto a otro desde un enlace cambia los datos sin recargar.""",
            },
        ]
    },
    # 14) Guards funcionales: CanActivateFn, CanMatchFn, CanDeactivateFn (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo protejo rutas en Angular 19? Quiero que `/account` exija sesión y que, si no hay, mande al login y después vuelva a donde iba. La sesión se comprueba con `GET /api/me`.",
            },
            {
                "role": "assistant",
                "content": r"""Con un guard funcional `CanActivateFn` que devuelve `true` o un `UrlTree` hacia el login con la URL de destino en `returnUrl`. La comprobación de sesión va en un servicio que cachea el resultado, para no llamar a `/api/me` en cada navegación.

```ts
// auth.service.ts
import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';

export interface User {
  id: string;
  name: string;
  roles: string[];
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  // undefined = aún no comprobado; null = sin sesión
  private readonly user = signal<User | null | undefined>(undefined);
  readonly currentUser = this.user.asReadonly();

  ensureSession(): Observable<boolean> {
    const known = this.user();
    if (known !== undefined) return of(known !== null);
    return this.http.get<User>('/api/me').pipe(
      tap((user) => this.user.set(user)),
      map(() => true),
      catchError(() => {
        this.user.set(null);
        return of(false);
      }),
    );
  }
}
```

```ts
// auth.guard.ts
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const toLogin = router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  return auth.ensureSession().pipe(map((loggedIn) => (loggedIn ? true : toLogin)));
};
```

```ts
// app.routes.ts (fragmento)
{
  path: 'account',
  canActivate: [authGuard],
  loadComponent: () => import('./account/account.component').then((m) => m.AccountComponent),
},
```

Y en el login, tras autenticar:

```ts
const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
// Solo rutas internas: evita un open redirect con returnUrl=https://evil.example
const safeUrl = returnUrl?.startsWith('/') && !returnUrl.startsWith('//') ? returnUrl : '/';
this.router.navigateByUrl(safeUrl);
```

Por qué así:

- **Devolver un `UrlTree` en vez de llamar a `router.navigate()` dentro del guard.** El `UrlTree` cancela la navegación actual y arranca la redirección como una sola operación. Con `navigate()` + `return false` lanzas dos navegaciones que compiten. Desde Angular 18 también puedes devolver `new RedirectCommand(router.parseUrl('/login'), { skipLocationChange: true })` si necesitas opciones de navegación.
- **`inject()` al principio del guard**, de forma síncrona: el guard se ejecuta en un contexto de inyección, pero dentro de un `pipe` asíncrono ya no lo estás.
- **El guard es UX, no seguridad.** Cualquiera puede saltárselo desde DevTools; la API tiene que rechazar igualmente las peticiones sin sesión.

Verificación: en una ventana privada abre `/account/orders` → acabas en `/login?returnUrl=%2Faccount%2Forders`; tras iniciar sesión vuelves a `/account/orders`. Prueba `/login?returnUrl=//evil.example` → tras el login acabas en `/`.""",
            },
            {
                "role": "user",
                "content": "Y para `/admin`: no quiero que alguien sin rol admin ni siquiera descargue el chunk. Además, en el editor de perfil quiero avisar si sale con cambios sin guardar.",
            },
            {
                "role": "assistant",
                "content": r"""Para lo primero, `canMatch` en lugar de `canActivate`. Para lo segundo, `CanDeactivateFn`.

**Por qué `canActivate` no basta para `/admin`.** El router resuelve la configuración lazy (descarga el chunk de `loadChildren`) al reconocer la ruta, **antes** de ejecutar `canActivate`. `canMatch` se evalúa durante el reconocimiento: si devuelve `false`, esa ruta no casa y el chunk no se pide.

```ts
// admin.guard.ts
import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

export const adminMatchGuard: CanMatchFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.ensureSession().pipe(
    map(() => (auth.currentUser()?.roles.includes('admin') ? true : router.createUrlTree(['/forbidden']))),
  );
};
```

Un matiz útil: si un `canMatch` devuelve `false` (no un `UrlTree`), el router sigue probando las rutas siguientes y normalmente acaba en `**`, es decir, un 404. Eso permite ocultar que `/admin` existe; con el `UrlTree` a `/forbidden` lo haces explícito. Elige según tu caso.

**Cambios sin guardar:**

```ts
// unsaved-changes.guard.ts
import { CanDeactivateFn } from '@angular/router';

export interface HasUnsavedChanges {
  hasUnsavedChanges(): boolean;
}

export const unsavedChangesGuard: CanDeactivateFn<HasUnsavedChanges> = (component) =>
  !component.hasUnsavedChanges() || confirm('Tienes cambios sin guardar. ¿Salir de todos modos?');
```

```ts
// profile-editor.component.ts (fragmento)
export class ProfileEditorComponent implements HasUnsavedChanges {
  private readonly fb = inject(NonNullableFormBuilder);
  readonly form = this.fb.group({ name: [''], bio: [''] });

  hasUnsavedChanges(): boolean {
    return this.form.dirty;
  }

  save(): void {
    // Tras guardar con éxito, el formulario deja de contar como modificado
    this.form.markAsPristine();
  }
}
```

```ts
// app.routes.ts (fragmento)
{
  path: 'admin',
  canMatch: [adminMatchGuard],
  loadChildren: () => import('./admin/admin.routes').then((m) => m.ADMIN_ROUTES),
},
{
  path: 'account/profile',
  canActivate: [authGuard],
  canDeactivate: [unsavedChangesGuard],
  loadComponent: () => import('./account/profile-editor.component').then((m) => m.ProfileEditorComponent),
},
```

La interfaz `HasUnsavedChanges` hace el guard reutilizable: cualquier componente que la implemente queda protegido sin que el guard conozca su clase. Ten en cuenta que `canDeactivate` solo cubre navegaciones del router; cerrar la pestaña o recargar se gestiona con el evento `beforeunload` (por ejemplo, `host: { '(window:beforeunload)': 'onBeforeUnload($event)' }` en el mismo componente).

Verificación:

1. Con un usuario sin rol admin, abre `/admin` con Network abierto: no aparece ninguna petición al chunk `admin-routes` y acabas en `/forbidden`. Con `canActivate` sí la verías.
2. En el editor, cambia el nombre y pulsa un enlace del menú: aparece el `confirm`. «Cancelar» te deja en la página con el texto intacto; tras guardar, navegar ya no pregunta.""",
            },
        ]
    },
    # 15) EN: resolvers, trade-offs y RedirectCommand.
    {
        "messages": [
            {
                "role": "user",
                "content": "Should I use route resolvers in Angular 19 to load data before showing a page? A teammate says they're an anti-pattern because the screen freezes while they load. When do they actually make sense?",
            },
            {
                "role": "assistant",
                "content": r"""Your teammate is describing a real cost, not an anti-pattern. A resolver **blocks the navigation**: the old page stays on screen until the data arrives, with no feedback unless you add it. That is the right trade-off in some cases and the wrong one in others.

| Use a resolver when | Load in the component when |
|---|---|
| The data is small and fast (tens of ms) | The data is slow or comes from several independent sources |
| The page is meaningless without it (an entity detail) | Part of the page is useful before the data arrives |
| You need to decide the outcome first (404 → redirect) | You want a skeleton or progressive rendering |
| Avoiding a "loading" flash matters more than instant feedback | Perceived speed matters more |

When you do use one, make it robust: handle errors inside the resolver (an unhandled error cancels the navigation silently) and show a global progress bar.

```ts
// product.resolver.ts
import { inject } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { RedirectCommand, ResolveFn, Router } from '@angular/router';
import { catchError, of } from 'rxjs';
import { Product, ProductService } from './product.service';

export const productResolver: ResolveFn<Product> = (route) => {
  // inject() must run synchronously, before any async work
  const router = inject(Router);
  const products = inject(ProductService);
  const id = route.paramMap.get('id') ?? '';

  return products.getById(id).pipe(
    catchError((err: unknown) => {
      const target = err instanceof HttpErrorResponse && err.status === 404 ? '/not-found' : '/error';
      // Angular 18+: a resolver can redirect instead of failing the navigation
      return of(new RedirectCommand(router.parseUrl(target)));
    }),
  );
};
```

```ts
// app.routes.ts (excerpt)
{
  path: 'products/:id',
  resolve: { product: productResolver },
  loadComponent: () => import('./products/product-detail.component').then((m) => m.ProductDetailComponent),
},
```

```ts
// product-detail.component.ts
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Product } from './product.service';

@Component({
  selector: 'app-product-detail',
  template: `<h1>{{ product().name }}</h1><p>{{ product().price }} €</p>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductDetailComponent {
  // Bound from resolve.product via withComponentInputBinding(); never undefined here
  readonly product = input.required<Product>();
}
```

And the feedback your teammate is missing, in the root component:

```ts
// app.component.ts
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  NavigationCancel, NavigationEnd, NavigationError, NavigationStart, Router, RouterOutlet,
} from '@angular/router';
import { filter, map } from 'rxjs';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: `
    @if (navigating()) {
      <div class="top-progress-bar" role="progressbar" aria-label="Loading page"></div>
    }
    <router-outlet />
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  readonly navigating = toSignal(
    inject(Router).events.pipe(
      filter(
        (e) =>
          e instanceof NavigationStart ||
          e instanceof NavigationEnd ||
          e instanceof NavigationCancel ||
          e instanceof NavigationError,
      ),
      map((e) => e instanceof NavigationStart),
    ),
    { initialValue: false },
  );
}
```

Why this shape:

- **The component gets a guaranteed `Product`.** No `@if (product)`, no `undefined` state to design for. That's the main benefit of resolvers and why they fit entity pages.
- **`RedirectCommand` turns failures into navigations.** Without the `catchError`, a 404 cancels the navigation and the user stays on the previous page wondering why the click did nothing.
- **Re-runs:** by default the resolver runs again when path params change (`runGuardsAndResolvers: 'paramsChange'`), so going from product 1 to product 2 re-fetches.

If a page needs a slow, secondary block (reviews, recommendations), resolve only the core entity and load the rest in the component with `@defer` or a loading state. Mixing both is usually the best answer to "resolver or not".

Verification: throttle to "Slow 3G" and click a product link; the progress bar appears, the previous page stays interactive, and the detail renders complete in one go. Visit `/products/does-not-exist`: you land on `/not-found`, and the detail component never renders.""",
            },
        ]
    },
    # 16) ERR: OnPush + mutación de un array de input (system revisor estricto).
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala primero el problema más grave."},
            {
                "role": "user",
                "content": r"""Revisa esto. El hijo no se actualiza cuando agrego tareas, aunque a veces sí (cuando paso el ratón por encima de la lista o algo así).

```ts
export interface Task { id: number; title: string; }

@Component({
  selector: 'app-task-list',
  template: `
    <p>{{ tasks.length }} tareas</p>
    @for (task of tasks; track task.id) { <li>{{ task.title }}</li> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TaskListComponent {
  @Input() tasks: Task[] = [];
}

@Component({
  selector: 'app-board',
  imports: [TaskListComponent],
  template: `
    <button (click)="add()">Añadir</button>
    <app-task-list [tasks]="tasks" />
  `,
})
export class BoardComponent {
  tasks: Task[] = [];
  private nextId = 1;

  add() {
    this.tasks.push({ id: this.nextId++, title: 'Tarea ' + this.nextId });
  }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""**1. Grave: mutas un array que un hijo `OnPush` recibe por input.** `push` modifica el mismo array; la referencia que ve `TaskListComponent` no cambia. Un componente `OnPush` solo se vuelve a comprobar cuando:

- cambia la **referencia** de alguno de sus inputs (comparación `===`),
- se dispara un evento en su propia plantilla o en sus hijos,
- emite un `async` pipe de su plantilla,
- cambia un signal que su plantilla lee,
- alguien llama a `markForCheck()`.

Al pulsar «Añadir», Angular revisa `BoardComponent`, ve que `[tasks]` sigue siendo el mismo array y se salta el hijo. Ese «a veces sí» es la pista: cualquier evento dentro de la lista (un `mouseenter` con listener, por ejemplo) marca el hijo y entonces pinta el estado acumulado. Un bug que depende de por dónde pasa el ratón es justo lo que hay que eliminar, no parchear con `markForCheck()`.

**2. Medio: error de uno en el título.** `this.nextId++` incrementa antes de construir el título, así que la tarea con `id: 1` se llama «Tarea 2».

**3. Menor: `<li>` sin `<ul>`**, HTML inválido que los lectores de pantalla anuncian mal. Y en código nuevo de Angular 17.1+ usa `input()` en lugar de `@Input()`.

Versión corregida con signals, donde la inmutabilidad la impone el tipo:

```ts
import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';

export interface Task {
  id: number;
  title: string;
}

@Component({
  selector: 'app-task-list',
  template: `
    <p>{{ tasks().length }} tareas</p>
    <ul>
      @for (task of tasks(); track task.id) {
        <li>{{ task.title }}</li>
      } @empty {
        <li>Sin tareas</li>
      }
    </ul>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TaskListComponent {
  // readonly Task[]: el hijo no puede mutar lo que recibe
  readonly tasks = input.required<readonly Task[]>();
}

@Component({
  selector: 'app-board',
  imports: [TaskListComponent],
  template: `
    <button type="button" (click)="add()">Añadir</button>
    <app-task-list [tasks]="tasks()" />
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BoardComponent {
  readonly tasks = signal<readonly Task[]>([]);
  private nextId = 1;

  add(): void {
    const id = this.nextId++;
    // Array nuevo: nueva referencia, el hijo OnPush se entera
    this.tasks.update((list) => [...list, { id, title: `Tarea ${id}` }]);
  }
}
```

Con `readonly Task[]`, un `push` sobre ese array ya no compila: el error pasa de ser visual e intermitente a ser de tipos y determinista. Si no puedes migrar a signals todavía, el arreglo mínimo es el mismo principio: `this.tasks = [...this.tasks, task]`.

Test de regresión (falla con el código original, que se queda en «0 tareas»):

```ts
import { TestBed } from '@angular/core/testing';
import { BoardComponent } from './board.component';

describe('BoardComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ imports: [BoardComponent] }));

  it('el hijo OnPush refleja las tareas añadidas', () => {
    const fixture = TestBed.createComponent(BoardComponent);
    fixture.detectChanges();

    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    button.click();
    button.click();
    fixture.detectChanges();

    const host: HTMLElement = fixture.nativeElement;
    expect(host.querySelector('p')?.textContent).toContain('2 tareas');
    expect(host.querySelectorAll('li')[0].textContent).toBe('Tarea 1');
  });
});
```""",
            },
        ]
    },
    # 17) ERR multiturno: NG0100 ExpressionChangedAfterItHasBeenCheckedError.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Me sale esto en la consola, solo en desarrollo:

```
ERROR RuntimeError: NG0100: ExpressionChangedAfterItHasBeenCheckedError: Expression has changed after it was checked. Previous value: 'false'. Current value: 'true'. Find more at https://angular.dev/errors/NG0100
```

Tengo un spinner global en `AppComponent` con `@if (loader.loading) { <app-spinner /> }`, y `loading` es un booleano público de un `LoaderService` (`providedIn: 'root'`). La página de informes hace `this.loader.loading = true` en `ngAfterViewInit` y lo pone a `false` cuando termina la petición.""",
            },
            {
                "role": "assistant",
                "content": r"""El error describe exactamente lo que pasa: un hijo cambia un valor que el padre **ya pintó** en la misma pasada de detección de cambios.

Secuencia:

1. Angular comprueba `AppComponent`: evalúa `loader.loading` → `false` y no pinta el spinner.
2. Baja a los hijos. Al terminar la vista del informe, se ejecuta su `ngAfterViewInit` y pone `loading = true`.
3. En desarrollo, Angular hace una segunda pasada de verificación (`checkNoChanges`) sin modificar nada: vuelve a evaluar `loader.loading`, obtiene `true` donde había pintado `false` y lanza NG0100.

No es un falso positivo: el DOM está mostrando un valor que ya no es el real. El flujo de datos de Angular es de arriba abajo en cada pasada, y aquí un hijo escribió hacia arriba en mitad de ella.

**El arreglo de fondo: que el estado de carga lo produzcan las propias peticiones, como signal.** El componente deja de tocar el spinner.

```ts
// loading.service.ts
import { Injectable, computed, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class LoadingService {
  private readonly pending = signal(0);
  readonly loading = computed(() => this.pending() > 0);

  start(): void {
    this.pending.update((n) => n + 1);
  }

  stop(): void {
    this.pending.update((n) => Math.max(0, n - 1));
  }
}
```

```ts
// loading.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { finalize } from 'rxjs';
import { LoadingService } from './loading.service';

export const loadingInterceptor: HttpInterceptorFn = (req, next) => {
  const loading = inject(LoadingService);
  loading.start();
  return next(req).pipe(finalize(() => loading.stop())); // éxito, error o cancelación
};
```

```ts
// app.config.ts (fragmento)
provideHttpClient(withFetch(), withInterceptors([loadingInterceptor])),
```

```html
<!-- app.component.html; en la clase: protected readonly loading = inject(LoadingService); -->
@if (loading.loading()) {
  <app-spinner />
}
<router-outlet />
```

Y en el informe, borra el `ngAfterViewInit` y lanza la carga al crear el componente (constructor con `toSignal`, o `ngOnInit`); el spinner aparece solo.

Por qué esto sí funciona:

- **Un signal leído en una plantilla sabe qué vistas dependen de él.** Si cambia durante la detección de cambios, Angular (17+) vuelve a refrescar esas vistas en la misma vuelta en lugar de dejar el valor viejo pintado. Con un booleano plano no hay forma de saberlo.
- **El contador** resuelve también un bug que tenías latente: con dos peticiones en paralelo, la primera en terminar ponía `loading = false` mientras la segunda seguía en curso.
- **`finalize`** cubre el error y la cancelación (un `switchMap` que aborta, salir de la página). Con un `false` en el `subscribe` de éxito, un error dejaba el spinner girando para siempre.

Lo que no recomiendo, aunque silencie el error: `setTimeout(() => this.loader.loading = true)` o llamar a `cdr.detectChanges()` en el padre. Funcionan aplazando o forzando otra pasada, pero esconden el flujo al revés, provocan un parpadeo y se vuelven a romper con `OnPush` o sin Zone.js.

Verificación: recarga la página de informes con la consola abierta: no hay NG0100 y el spinner se ve durante la petición. Con «Slow 3G» y dos widgets que piden datos a la vez, el spinner sigue visible hasta que termina el último.""",
            },
            {
                "role": "user",
                "content": "¿Y por qué en producción no sale el error? ¿No podría simplemente ignorarlo?",
            },
            {
                "role": "assistant",
                "content": r"""En producción no sale porque la segunda pasada de verificación (`checkNoChanges`) **solo existe en modo desarrollo**: cuesta una vuelta extra de detección de cambios y Angular se la ahorra en el build de producción. El bug sigue ahí; lo que desaparece es el detector.

Lo que ve el usuario en producción con tu código original:

- El DOM se queda con el valor de la primera pasada (`false`) hasta que **otra cosa** dispare detección de cambios: un clic, un timer, la respuesta HTTP.
- En tu caso, el spinner aparece tarde o no aparece en peticiones cortas: la respuesta llega, `loading` vuelve a `false` y el spinner nunca se pintó.
- Con `OnPush` en el padre o sin Zone.js, puede que esa «otra cosa» no llegue y el valor quede desincronizado indefinidamente.

Por eso NG0100 hay que tratarlo como un test que falla, no como ruido: te avisa en desarrollo de un estado de interfaz que en producción será inconsistente de forma intermitente, que es la peor clase de bug para reproducir.

Regla práctica para no volver a provocarlo: **ningún hook de ciclo de vida de un hijo (`ngOnInit`, `ngAfterViewInit`, `ngOnChanges`) debe escribir estado que lea un ancestro.** Si un hijo necesita influir arriba, que lo haga con un `output()` disparado por un evento o con un signal compartido en un servicio.""",
            },
        ]
    },
    # 18) Zoneless: activación en 18/19, qué se rompe y plan de migración (system exacta, avanzado).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero probar zoneless en una app Angular 19 que ya está en producción. ¿Qué cambia exactamente, cómo lo activo y qué se me va a romper?",
            },
            {
                "role": "assistant",
                "content": r"""Cambia **quién decide cuándo hay detección de cambios**. Con Zone.js, Angular parchea todas las APIs asíncronas del navegador (`setTimeout`, promesas, XHR, eventos) y, tras cualquiera de ellas, revisa el árbol de componentes por si acaso. Sin Zone.js, Angular solo programa una detección de cambios cuando recibe una notificación explícita:

- un signal que lee una plantilla cambia de valor,
- `markForCheck()` (el `async` pipe lo llama por ti),
- un evento escuchado en una plantilla o en un `host`,
- `ComponentRef.setInput()`, o se adjunta o separa una vista.

Todo lo que dependía de «Zone.js se entera solo» deja de actualizar la pantalla.

**Activación en Angular 18/19** (API experimental; en Angular 20 se renombró a `provideZonelessChangeDetection()` y se estabilizó en 20.2):

```ts
// app.config.ts
import { ApplicationConfig, provideExperimentalZonelessChangeDetection } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideExperimentalZonelessChangeDetection(), // sustituye a provideZoneChangeDetection(...)
    provideRouter(routes),
    provideHttpClient(withFetch()),
  ],
};
```

Después quita `"zone.js"` del array `polyfills` en `angular.json`, tanto en `build` como en `test` (ahí suele estar también `"zone.js/testing"`), y desinstala el paquete cuando nada lo importe.

**Qué se rompe, con ejemplo.** Este componente funciona hoy y deja de actualizar sin Zone.js:

```ts
export class StatusComponent implements OnInit {
  private readonly http = inject(HttpClient);
  message = '';
  user?: User;

  ngOnInit(): void {
    setTimeout(() => (this.message = 'Listo'), 1000);                     // nadie avisa a Angular
    this.http.get<User>('/api/me').subscribe((u) => (this.user = u));     // tampoco
  }
}
```

La versión que funciona con y sin Zone.js:

```ts
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';

interface User {
  id: string;
  name: string;
}

@Component({
  selector: 'app-status',
  template: `<p>{{ message() }}</p> @if (user(); as u) { <p>{{ u.name }}</p> }`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusComponent {
  private readonly http = inject(HttpClient);
  readonly message = signal('');
  readonly user = toSignal(this.http.get<User>('/api/me'));

  constructor() {
    setTimeout(() => this.message.set('Listo'), 1000); // set() notifica a Angular
  }
}
```

Otros puntos que fallan en la práctica:

- **Librerías de terceros** que dependen de `NgZone.onStable` u `onMicrotaskEmpty`: esos observables ya no emiten. Revisa mapas, gráficos y componentes de UI que actualizan desde callbacks.
- **Tests:** `fakeAsync` y `tick` dependen de Zone.js. Añade `provideExperimentalZonelessChangeDetection()` a los providers de `TestBed`, sustituye la mayoría de `fixture.detectChanges()` por `await fixture.whenStable()`, y usa los temporizadores falsos de tu runner donde hacía falta `tick`.
- **Código que llama a `NgZone.run()`** para «forzar» actualizaciones: sobra, y es una señal de que ese estado debería ser un signal.

**Plan de migración por pasos, con Zone.js todavía activo como red:**

1. Pon `ChangeDetectionStrategy.OnPush` en todos los componentes. Un componente `OnPush` ya solo se actualiza por inputs, eventos, `async` pipe, signals y `markForCheck`, casi las mismas reglas que sin zona. Los bugs aparecen ahora, con la zona aún instalada.
2. Pasa a signals o `async` pipe el estado que se escribe en callbacks; elimina los `detectChanges()` manuales.
3. En una rama, activa zoneless y recorre los flujos críticos con tests end-to-end.
4. Quita el polyfill y despliega.

Lo que ganas: un polyfill menos en el arranque, trazas de error sin los marcos de Zone.js, detección de cambios solo cuando hace falta, y que el CLI deje de transformar `async/await` (solo lo hace cuando `zone.js` está en los polyfills, porque Zone.js no puede parchear el `await` nativo).

Verificación: en la consola del navegador, `typeof Zone` debe dar `"undefined"`. Ejecuta los e2e de los flujos críticos y busca pantallas que se quedan sin actualizar tras una respuesta HTTP o un temporizador: cada una es un campo que debe pasar a signal.""",
            },
        ]
    },
    # 19) Directiva estructural *appHasRole con signals + directiva de atributo con host (avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito dos directivas en Angular 19: una estructural `*appHasRole=\"'admin'\"` que muestre el contenido solo si el usuario tiene ese rol y que reaccione si cambia la sesión sin recargar; y otra de atributo para inputs que resalte el campo con foco y recorte los espacios al salir, también cuando el input está en un formulario reactivo. ¿Cómo se hacen hoy, con signals?",
            },
            {
                "role": "assistant",
                "content": r"""La estructural combina `TemplateRef` + `ViewContainerRef` con un `effect` que lee el rol pedido y los roles de la sesión; la de atributo usa la propiedad `host` y, si hay un control de formulario, escribe a través de él.

**Servicio de sesión** (lo mínimo que necesitan las directivas):

```ts
// session.service.ts
import { Injectable, computed, signal } from '@angular/core';

export interface SessionUser {
  id: string;
  roles: string[];
}

@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly user = signal<SessionUser | null>(null);
  readonly roles = computed(() => this.user()?.roles ?? []);

  setUser(user: SessionUser | null): void {
    this.user.set(user);
  }
}
```

**Directiva estructural:**

```ts
// has-role.directive.ts
import { Directive, TemplateRef, ViewContainerRef, effect, inject, input } from '@angular/core';
import { SessionService } from './session.service';

@Directive({ selector: '[appHasRole]' })
export class HasRoleDirective {
  private readonly templateRef = inject(TemplateRef);
  private readonly viewContainer = inject(ViewContainerRef);
  private readonly session = inject(SessionService);

  // *appHasRole="'admin'" o *appHasRole="['admin', 'editor']"
  readonly appHasRole = input.required<string | string[]>();

  private hasView = false;

  constructor() {
    effect(() => {
      const required = this.appHasRole();
      const wanted = Array.isArray(required) ? required : [required];
      const roles = this.session.roles(); // dependencia: el effect se repite al cambiar la sesión
      const allowed = wanted.some((role) => roles.includes(role));

      if (allowed && !this.hasView) {
        this.viewContainer.createEmbeddedView(this.templateRef);
        this.hasView = true;
      } else if (!allowed && this.hasView) {
        this.viewContainer.clear();
        this.hasView = false;
      }
    });
  }
}
```

Uso:

```html
<button *appHasRole="'admin'" type="button" (click)="deleteUser()">Borrar usuario</button>

<ng-template [appHasRole]="['admin', 'editor']">
  <app-article-editor />
</ng-template>
```

- El asterisco es azúcar: `*appHasRole="'admin'"` envuelve el elemento en un `<ng-template>` y enlaza la expresión al input que se llama **igual que el selector**. Por eso el input se llama `appHasRole`.
- **`hasView`** evita destruir y recrear la vista cuando el effect se repite sin cambiar el resultado (por ejemplo, la sesión gana un rol que no influye). Recrearla perdería el estado interno del contenido, como el texto escrito en un editor.
- Ocultar un botón no es control de acceso: la API tiene que rechazar igualmente la operación.

**Directiva de atributo:**

```ts
// trim-focus.directive.ts
import { Directive, ElementRef, inject, signal } from '@angular/core';
import { NgControl } from '@angular/forms';

@Directive({
  selector: 'input[appTrimFocus], textarea[appTrimFocus]',
  host: {
    '[class.is-focused]': 'focused()',
    '(focus)': 'focused.set(true)',
    '(blur)': 'onBlur()',
  },
})
export class TrimFocusDirective {
  private readonly el = inject<ElementRef<HTMLInputElement | HTMLTextAreaElement>>(ElementRef);
  // El control de formulario del mismo elemento, si lo hay (formControlName, ngModel…)
  private readonly ngControl = inject(NgControl, { optional: true, self: true });

  readonly focused = signal(false);

  onBlur(): void {
    this.focused.set(false);
    const current = this.el.nativeElement.value;
    const trimmed = current.trim();
    if (trimmed === current) return;

    if (this.ngControl?.control) {
      this.ngControl.control.setValue(trimmed); // actualiza modelo y vista a la vez
    } else {
      this.el.nativeElement.value = trimmed;
    }
  }
}
```

- **`host` en el decorador** es la forma recomendada hoy frente a `@HostBinding`/`@HostListener`: todo el contrato con el elemento queda en un sitio.
- **Por qué `NgControl`.** Si solo cambias `nativeElement.value`, el `FormControl` conserva el valor con espacios y eso es lo que se envía. Escribiendo a través del control, formulario y DOM quedan iguales.
- **`self: true`** limita la búsqueda al propio elemento; sin él podrías recoger un control de un ancestro.

Verificación con un componente de prueba:

```ts
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { HasRoleDirective } from './has-role.directive';
import { SessionService } from './session.service';
import { TrimFocusDirective } from './trim-focus.directive';

@Component({
  imports: [HasRoleDirective, TrimFocusDirective, ReactiveFormsModule],
  template: `
    <button *appHasRole="'admin'">Borrar</button>
    <input appTrimFocus [formControl]="name" />
  `,
})
class HostComponent {
  readonly name = new FormControl('', { nonNullable: true });
}

describe('directivas', () => {
  beforeEach(() => TestBed.configureTestingModule({ imports: [HostComponent] }));

  it('muestra u oculta según la sesión y recorta al salir', () => {
    const fixture = TestBed.createComponent(HostComponent);
    const session = TestBed.inject(SessionService);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('button')).toBeNull();

    session.setUser({ id: 'u1', roles: ['admin'] });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('button')).not.toBeNull();

    const input: HTMLInputElement = fixture.nativeElement.querySelector('input');
    input.value = '  Ana  ';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('blur'));
    expect(fixture.componentInstance.name.value).toBe('Ana');
  });
});
```""",
            },
        ]
    },
    # 20) Pipe puro relativeTime con Intl.RelativeTimeFormat; puro vs impuro (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero mostrar fechas tipo «hace 5 minutos» en Angular. Ahora tengo un método `timeAgo(date)` en el componente que llamo desde la plantilla, pero leí que llamar métodos en la plantilla es malo. ¿Lo paso a un pipe? ¿Y cómo hago que se vaya actualizando con el tiempo?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, pásalo a un **pipe puro**. Angular solo vuelve a ejecutar un pipe puro cuando cambian sus argumentos; un método en la plantilla se ejecuta en **cada** pasada de detección de cambios, para cada fila. Con una función barata da igual; con un `Intl` por llamada y 500 comentarios en pantalla, se nota.

```ts
// relative-time.pipe.ts
import { LOCALE_ID, Pipe, PipeTransform, inject } from '@angular/core';

// [unidad, segundos que contiene], de mayor a menor
const UNITS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600], // aproximación: suficiente para «hace 2 meses»
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
];

@Pipe({ name: 'relativeTime' }) // puro por defecto; standalone por defecto en Angular 19
export class RelativeTimePipe implements PipeTransform {
  // Un formateador por instancia del pipe, no uno por llamada
  private readonly formatter = new Intl.RelativeTimeFormat(inject(LOCALE_ID), { numeric: 'auto' });

  transform(value: Date | string | number | null | undefined, now: number = Date.now()): string {
    if (value == null) return '';
    const time = value instanceof Date ? value.getTime() : new Date(value).getTime();
    if (Number.isNaN(time)) return '';

    const diffSeconds = Math.round((time - now) / 1000);
    for (const [unit, secondsInUnit] of UNITS) {
      if (Math.abs(diffSeconds) >= secondsInUnit) {
        return this.formatter.format(Math.round(diffSeconds / secondsInUnit), unit);
      }
    }
    return this.formatter.format(diffSeconds, 'second');
  }
}
```

**Para que se actualice con el tiempo**, no lo hagas impuro: pásale «ahora» como argumento desde un reloj compartido. Cuando el reloj avanza, cambia el argumento y el pipe se recalcula; entre ticks no hace nada.

```ts
// clock.service.ts
import { Injectable } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { interval, map } from 'rxjs';

const CLOCK_TICK_MS = 30_000;

@Injectable({ providedIn: 'root' })
export class ClockService {
  readonly now = toSignal(interval(CLOCK_TICK_MS).pipe(map(() => Date.now())), {
    initialValue: Date.now(),
  });
}
```

```ts
// comment-list.component.ts
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { ClockService } from './clock.service';
import { RelativeTimePipe } from './relative-time.pipe';

export interface Comment {
  id: string;
  author: string;
  createdAt: string;
}

@Component({
  selector: 'app-comment-list',
  imports: [RelativeTimePipe],
  template: `
    @for (comment of comments(); track comment.id) {
      <p>{{ comment.author }} · {{ comment.createdAt | relativeTime: clock.now() }}</p>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CommentListComponent {
  protected readonly clock = inject(ClockService);
  readonly comments = input.required<Comment[]>();
}
```

Por qué no `pure: false`: un pipe impuro se ejecuta en cada detección de cambios, igual que tu método. Solo tiene sentido cuando el resultado depende de algo que Angular no puede ver en los argumentos (el `async` pipe es impuro por eso).

`numeric: 'auto'` es lo que produce «ayer» o «mañana» en vez de «hace 1 día». El idioma sale de `LOCALE_ID`: configúralo en `app.config.ts` con `{ provide: LOCALE_ID, useValue: 'es' }` (para `Intl` no hace falta `registerLocaleData`; eso es para `DatePipe` y compañía).

Verificación con una hora fija, sin depender del reloj real:

```ts
import { LOCALE_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { RelativeTimePipe } from './relative-time.pipe';

describe('RelativeTimePipe', () => {
  const now = new Date('2025-01-10T12:00:00Z').getTime();

  beforeEach(() =>
    TestBed.configureTestingModule({ providers: [{ provide: LOCALE_ID, useValue: 'es' }] }),
  );

  it('formatea minutos, días y valores vacíos', () => {
    const pipe = TestBed.runInInjectionContext(() => new RelativeTimePipe());
    expect(pipe.transform(now - 5 * 60_000, now)).toBe('hace 5 minutos');
    expect(pipe.transform(now - 24 * 3600_000, now)).toBe('ayer');
    expect(pipe.transform(null, now)).toBe('');
  });
});
```""",
            },
        ]
    },
    # 21) Test de componente con TestBed: setInput, DOM, output (system QA).
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero de QA. Prioriza tests deterministas y legibles."},
            {
                "role": "user",
                "content": r"""¿Cómo testeo bien este componente con TestBed? Usa la API nueva de signals y no sé cómo pasarle el input ni cómo comprobar el output.

```ts
export interface Product { id: string; name: string; price: number; stock: number; }

@Component({
  selector: 'app-product-card',
  imports: [CurrencyPipe],
  template: `
    <article>
      <h2>{{ product().name }}</h2>
      <p class="price">{{ product().price | currency: 'EUR' }}</p>
      @if (product().stock === 0) { <p class="out-of-stock">Agotado</p> }
      <button type="button" [disabled]="product().stock === 0" (click)="addToCart.emit(product().id)">Añadir</button>
    </article>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductCardComponent {
  readonly product = input.required<Product>();
  readonly addToCart = output<string>();
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Testéalo a través del DOM, como lo usaría una persona: das valor al input con `fixture.componentRef.setInput`, ejecutas la detección de cambios, haces clic y compruebas lo que se ve y lo que se emite. Nada de leer propiedades internas.

```ts
// product-card.component.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Product, ProductCardComponent } from './product-card.component';

describe('ProductCardComponent', () => {
  let fixture: ComponentFixture<ProductCardComponent>;
  let host: HTMLElement;

  const inStock: Product = { id: 'p1', name: 'Teclado mecánico', price: 89.9, stock: 3 };
  const soldOut: Product = { ...inStock, id: 'p2', stock: 0 };

  // Falla con un mensaje claro en vez de un «cannot read properties of null»
  function query<T extends Element>(selector: string): T {
    const found = host.querySelector<T>(selector);
    if (!found) throw new Error(`No se encontró «${selector}» en el DOM`);
    return found;
  }

  function render(product: Product): void {
    fixture.componentRef.setInput('product', product);
    fixture.detectChanges();
  }

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ProductCardComponent] });
    fixture = TestBed.createComponent(ProductCardComponent);
    host = fixture.nativeElement;
  });

  it('muestra el nombre y el precio', () => {
    render(inStock);

    expect(query('h2').textContent).toBe('Teclado mecánico');
    expect(query('.price').textContent).toContain('89.90');
  });

  it('emite el id del producto al pulsar «Añadir»', () => {
    render(inStock);
    const emitted: string[] = [];
    fixture.componentInstance.addToCart.subscribe((id) => emitted.push(id));

    query<HTMLButtonElement>('button').click();

    expect(emitted).toEqual(['p1']);
  });

  it('sin stock: avisa, deshabilita el botón y no emite', () => {
    render(soldOut);
    const emitted: string[] = [];
    fixture.componentInstance.addToCart.subscribe((id) => emitted.push(id));

    const button = query<HTMLButtonElement>('button');
    button.click();

    expect(query('.out-of-stock').textContent).toBe('Agotado');
    expect(button.disabled).toBe(true);
    expect(emitted).toEqual([]);
  });

  it('se actualiza cuando cambia el input', () => {
    render(inStock);
    render(soldOut);

    expect(host.querySelector('.out-of-stock')).not.toBeNull();
  });
});
```

Por qué cada decisión:

- **`setInput` y no asignar la propiedad.** Un `input()` es de solo lectura, así que asignar ni compila. Además, `setInput` hace lo mismo que el padre real: marca la vista como pendiente de revisar, lo que importa con `OnPush`. Con los antiguos `@Input()`, asignar directamente en un componente `OnPush` producía tests que pasaban o fallaban según el orden.
- **El output se comprueba suscribiéndose.** `output()` devuelve un `OutputEmitterRef` con `subscribe`; acumular en un array permite afirmar «se emitió exactamente esto, una vez» y también «no se emitió nada».
- **El caso negativo incluye el clic.** Comprobar solo `disabled` no prueba que no se emita; un `(click)` en un contenedor o un cambio futuro a `<div>` lo rompería. El test cubre el comportamiento, no el atributo.
- **`toContain('89.90')` en el precio.** El formato completo depende de `LOCALE_ID` (`€89.90` en `en-US`, `89,90 €` en `es`). Si el formato exacto es requisito, fija el `LOCALE_ID` en el `TestBed` y compara la cadena entera; si no, no ates el test a la configuración regional.
- **Un comportamiento por test, sin temporizadores ni `setTimeout`.** Todo es síncrono: no hace falta `fakeAsync` ni esperas.

Contexto de herramientas: Angular 18 y 19 generan los proyectos con Karma + Jasmine (Karma está deprecado y hay builders experimentales para Jest y Web Test Runner). Este test solo usa `describe`, `it`, `expect`, `toBe`, `toEqual`, `toContain` y `toBeNull`, que existen igual en Jasmine, Jest y Vitest, así que sobrevive a un cambio de runner. Si activas zoneless, sustituye `fixture.detectChanges()` por `await fixture.whenStable()` dentro de `render` y haz los tests `async`.

Comprobación de que los tests sirven: borra el `[disabled]` de la plantilla y ejecuta `ng test`; el tercer test debe fallar en `expect(emitted).toEqual([])`. Restaura la línea y vuelve a verde.""",
            },
        ]
    },
    # 22) Usuario en inglés pide respuesta en español: Angular CLI, environments, budgets, ng update.
    {
        "messages": [
            {
                "role": "user",
                "content": "Can you answer in Spanish? I'm new to the Angular CLI. Which commands will I use every day, how do environments work now (my new project has no environments folder), and how do I safely update a project from Angular 18 to 19?",
            },
            {
                "role": "assistant",
                "content": r"""Son tres temas distintos; los separo.

**Comandos del día a día**

```bash
# Proyecto nuevo (Angular 17+ trae routing y standalone por defecto)
npx @angular/cli@19 new orders-app --style=scss --ssr=false

ng serve --open                                  # servidor de desarrollo con recarga
ng generate component features/orders/order-list # alias: ng g c
ng g service features/orders/orders-api          # ng g s
ng g guard core/auth                             # guard funcional
ng g interceptor core/auth                       # interceptor funcional
ng g pipe shared/relative-time
ng g c features/orders/order-detail --dry-run    # muestra qué crearía sin escribir nada
ng build                                         # producción por defecto
ng build --configuration development             # sin optimizar, con source maps
ng test                                          # tests unitarios
ng add @angular/material                         # instala una librería y ejecuta su configuración
```

`--dry-run` es tu amigo mientras aprendes la estructura que genera cada comando.

**Environments**

Desde Angular 15 el proyecto no trae la carpeta `environments`; se crea cuando la necesitas:

```bash
ng generate environments
```

Crea `src/environments/environment.ts` (el que se usa en producción) y `environment.development.ts`, y añade en `angular.json` el reemplazo de archivos para la configuración `development`:

```json
"configurations": {
  "production": {
    "budgets": [
      { "type": "initial", "maximumWarning": "500kB", "maximumError": "1MB" },
      { "type": "anyComponentStyle", "maximumWarning": "4kB", "maximumError": "8kB" }
    ],
    "outputHashing": "all"
  },
  "development": {
    "optimization": false,
    "extractLicenses": false,
    "sourceMap": true,
    "fileReplacements": [
      {
        "replace": "src/environments/environment.ts",
        "with": "src/environments/environment.development.ts"
      }
    ]
  }
}
```

```ts
// src/environments/environment.ts
export const environment = {
  production: true,
  apiUrl: 'https://api.example.com',
};
```

Dos advertencias importantes:

- **Lo que pongas ahí acaba dentro del JavaScript que descarga el navegador.** Nada de secretos: ni claves privadas de API ni contraseñas.
- **Se resuelve en tiempo de build.** Si quieres el mismo build para staging y producción con URLs distintas, carga un `/config.json` al arrancar con `provideAppInitializer` (Angular 19) en lugar de compilar dos veces.

Los **budgets** hacen fallar el build si el bundle inicial crece por encima del límite: es la alarma más barata contra una dependencia pesada que se cuela.

**Actualizar de 18 a 19 sin sustos**

1. Rama nueva y árbol de git limpio (`ng update` se niega a ejecutarse con cambios sin commitear, y es lo que quieres).
2. Comprueba en la guía de update.angular.dev los requisitos de la versión de destino: Node y TypeScript soportados (19 pide TypeScript 5.5 o superior).
3. Actualiza el núcleo y el CLI juntos, de **una versión mayor en una**:

```bash
ng update @angular/core@19 @angular/cli@19
```

4. Después, las librerías del ecosistema que uses, también de una en una: `ng update @angular/material@19`, NgRx, etc.
5. `ng update` ejecuta **migraciones automáticas** que modifican tu código. La más visible en 19: como los componentes pasan a ser standalone por defecto, añade `standalone: false` a los que siguen declarados en un NgModule. Revisa el diff archivo por archivo y haz un commit por paso.
6. `ng build`, `ng test` y una pasada manual por los flujos críticos antes de fusionar.

Si vas varias versiones atrás (de 16 a 19, por ejemplo), repite el paso 3 versión por versión: 17, 18, 19. Saltar directamente te deja sin las migraciones intermedias.""",
            },
        ]
    },
    # 23) Migración de NgModules a standalone con el schematic; SharedModule (multiturno, avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos una app Angular grande con NgModules (unos 40 módulos) que acabamos de subir a la 19. ¿Cómo la migramos a standalone sin romper todo? ¿Se hace a mano?",
            },
            {
                "role": "assistant",
                "content": r"""No a mano: hay un schematic oficial que hace el 90 % del trabajo. La clave es ejecutarlo **en tres pasadas separadas, en orden**, con build, tests y commit entre cada una.

```bash
ng generate @angular/core:standalone
```

Te pregunta el modo y la ruta. Las tres pasadas:

1. **«Convert all components, directives and pipes to standalone».** Cada declarable pasa a standalone y recibe en su `imports` lo que usa. Los NgModules siguen existiendo, ahora importando en vez de declarar. Es el paso que más archivos toca y el que menos riesgo tiene.
2. **«Remove unnecessary NgModule classes».** Borra los módulos que han quedado vacíos de sentido (sin providers ni configuración). Los que no puede borrar con seguridad los marca con un comentario para revisión manual.
3. **«Bootstrap the application using standalone APIs».** Cambia `platformBrowserDynamic().bootstrapModule(AppModule)` por `bootstrapApplication` y convierte los providers del `AppModule` en un `ApplicationConfig`.

En una app de 40 módulos, haz la pasada 1 por carpetas con la opción de ruta (por ejemplo, `src/app/features/billing`), una feature por PR. Así cada revisión es pequeña y un problema queda localizado.

Lo que suele quedar a mano tras la pasada 3:

```ts
// main.ts
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig).catch((err) => console.error(err));
```

```ts
// app.config.ts
import { ApplicationConfig, importProvidersFrom, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter } from '@angular/router';
import { LegacyChartsModule } from 'legacy-charts';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    // Conserva los interceptores de clase registrados con HTTP_INTERCEPTORS
    provideHttpClient(withInterceptorsFromDi()),
    provideAnimationsAsync(),
    // Librería que solo ofrece un NgModule con forRoot(): se envuelve, no se reescribe
    importProvidersFrom(LegacyChartsModule.forRoot({ theme: 'dark' })),
  ],
};
```

- **`withInterceptorsFromDi()`** mantiene vivos tus interceptores de clase durante la transición; los migras a funcionales después, uno a uno.
- **`importProvidersFrom`** es el puente para librerías que todavía no exponen funciones `provideX()`. Úsalo solo para providers; los componentes de esas librerías se importan en el `imports` de cada componente.
- **Rutas:** los `loadChildren: () => import('./billing/billing.module').then((m) => m.BillingModule)` siguen funcionando; conviértelos a archivos de rutas (`billing.routes.ts` que exporta `Routes`) cuando el módulo de esa feature desaparezca.

Después, opcionalmente, Angular 19 trae más migraciones automáticas que encajan bien a continuación: control flow (`ng generate @angular/core:control-flow`), `inject()` en lugar de inyección por constructor (`ng generate @angular/core:inject`) y signal inputs (`ng generate @angular/core:signal-input-migration`). Mismo método: una cada vez, con commit.

Verificación tras cada pasada: `ng build` sin errores, `ng test` en verde y una navegación por las rutas lazy (son las que antes rompen, porque los errores de dependencias faltantes en plantillas lazy aparecen al entrar en ellas). El tamaño de los chunks en la salida del build no debería empeorar; si un chunk lazy crece mucho, mira el siguiente punto: suele ser un módulo compartido gigante.""",
            },
            {
                "role": "user",
                "content": "Justo eso: tenemos un `SharedModule` enorme que exporta unas 60 cosas (CommonModule, FormsModule, Material, pipes y componentes propios) y todos los módulos lo importan. El schematic lo dejó casi igual. ¿Qué hacemos con él?",
            },
            {
                "role": "assistant",
                "content": r"""El schematic lo conserva porque es legal: un componente standalone puede importar un NgModule. Pero cada componente que importa `SharedModule` declara como dependencia **todo** lo que exporta, y eso arrastra las 60 piezas al chunk de cada ruta lazy que lo use. Es el motivo habitual de que el lazy loading «no adelgace» nada.

El objetivo es que cada componente importe exactamente lo que usa. Plan en cuatro pasos:

**1. Asegúrate de que todo lo que exporta es standalone.** La primera pasada del schematic ya lo hizo para tus pipes, directivas y componentes; los de Material ya lo son.

**2. Sustituye `SharedModule` por imports explícitos, feature a feature.** Angular 19 ayuda: el compilador avisa de los imports standalone que no se usan en la plantilla (diagnóstico `unusedStandaloneImports`). Un truco práctico: en cada componente, reemplaza `SharedModule` por la lista completa de lo que exportaba, compila, y borra lo que el compilador marque como no usado.

```ts
// Antes
@Component({
  selector: 'app-invoice-list',
  imports: [SharedModule],
  templateUrl: './invoice-list.component.html',
})
export class InvoiceListComponent {}

// Después
@Component({
  selector: 'app-invoice-list',
  imports: [CurrencyPipe, RouterLink, MatTableModule, RelativeTimePipe, EmptyStateComponent],
  templateUrl: './invoice-list.component.html',
})
export class InvoiceListComponent {}
```

**3. Para grupos que de verdad van siempre juntos, usa arrays constantes en lugar de módulos.** `imports` acepta arrays anidados, y un array no tiene providers ni configuración oculta:

```ts
// shared/form-imports.ts
import { ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { FieldErrorComponent } from './field-error.component';

export const FORM_IMPORTS = [
  ReactiveFormsModule,
  MatFormFieldModule,
  MatInputModule,
  FieldErrorComponent,
] as const;
```

```ts
@Component({
  selector: 'app-customer-form',
  imports: [FORM_IMPORTS],
  templateUrl: './customer-form.component.html',
})
export class CustomerFormComponent {}
```

Mantén estos grupos pequeños (cinco o seis piezas) y con un único propósito; si `FORM_IMPORTS` empieza a llevar una tabla y un gráfico, has reconstruido el `SharedModule`.

**4. Si `SharedModule` tenía `providers`, muévelos.** Los servicios pasan a `providedIn: 'root'` (o a `providers` de la ruta si deben tener un ámbito), y la configuración de librerías, a `app.config.ts`. Cuando ningún archivo importe `SharedModule`, bórralo.

Verificación con números: antes de empezar, genera `ng build --stats-json` y guarda el tamaño de cada chunk lazy. Repite al terminar cada feature. Lo esperable es que los chunks de las features bajen y que el `main` no suba. Si una feature crece, busca qué import nuevo arrastra una dependencia pesada (normalmente un módulo de Material completo donde bastaba un componente).""",
            },
        ]
    },
    # 24) Servicio con signals como store vs NgRx SignalStore (multiturno, avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": "Para estado compartido en Angular 19 (un carrito que usan la cabecera, la página del carrito y el checkout), ¿hace falta NgRx o basta un servicio con signals? Si basta, ¿cómo se escribe bien para que no acabe siendo un caos?",
            },
            {
                "role": "assistant",
                "content": r"""Para un carrito basta un servicio con signals. Lo que evita el caos no es la librería, sino tres reglas: **el estado escribible es privado**, **solo se modifica a través de métodos con nombre**, y **las actualizaciones son inmutables**.

```ts
// cart.store.ts
import { Injectable, computed, signal } from '@angular/core';

export interface CartItem {
  productId: string;
  name: string;
  unitPriceCents: number; // dinero en enteros: sin errores de coma flotante
  quantity: number;
}

@Injectable({ providedIn: 'root' })
export class CartStore {
  private readonly _items = signal<readonly CartItem[]>([]);

  // API pública de solo lectura
  readonly items = this._items.asReadonly();
  readonly count = computed(() => this._items().reduce((n, item) => n + item.quantity, 0));
  readonly totalCents = computed(() =>
    this._items().reduce((sum, item) => sum + item.unitPriceCents * item.quantity, 0),
  );
  readonly isEmpty = computed(() => this._items().length === 0);

  add(product: Omit<CartItem, 'quantity'>, quantity = 1): void {
    this._items.update((items) => {
      const exists = items.some((item) => item.productId === product.productId);
      return exists
        ? items.map((item) =>
            item.productId === product.productId ? { ...item, quantity: item.quantity + quantity } : item,
          )
        : [...items, { ...product, quantity }];
    });
  }

  remove(productId: string): void {
    this._items.update((items) => items.filter((item) => item.productId !== productId));
  }

  clear(): void {
    this._items.set([]);
  }
}
```

Por qué así:

- **`asReadonly()`** expone un `Signal` sin `set` ni `update`. Un componente no puede hacer `cart.items.set([])` por accidente; tiene que llamar a `clear()`, que es buscable y testeable.
- **Inmutable a la fuerza.** Los signals avisan cuando cambia la **referencia** (`Object.is`). Un `items.push()` sobre el array existente no notificaría a nadie. El `readonly CartItem[]` hace que ese `push` ni compile.
- **Derivados con `computed`.** `count` y `totalCents` se calculan una vez por cambio y se cachean; la cabecera y el checkout leen el mismo valor sin duplicar lógica.

Uso en la cabecera:

```ts
// cart-badge.component.ts
import { CurrencyPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CartStore } from './cart.store';

@Component({
  selector: 'app-cart-badge',
  imports: [CurrencyPipe, RouterLink],
  template: `<a routerLink="/cart">Carrito ({{ cart.count() }}) · {{ cart.totalCents() / 100 | currency: 'EUR' }}</a>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CartBadgeComponent {
  protected readonly cart = inject(CartStore);
}
```

Test sin componentes:

```ts
import { TestBed } from '@angular/core/testing';
import { CartStore } from './cart.store';

describe('CartStore', () => {
  it('acumula cantidades del mismo producto y calcula el total', () => {
    const cart = TestBed.inject(CartStore);
    const keyboard = { productId: 'k1', name: 'Teclado', unitPriceCents: 4_990 };

    cart.add(keyboard);
    cart.add(keyboard, 2);

    expect(cart.items().length).toBe(1);
    expect(cart.count()).toBe(3);
    expect(cart.totalCents()).toBe(14_970);

    cart.remove('k1');
    expect(cart.isEmpty()).toBe(true);
  });
});
```""",
            },
            {
                "role": "user",
                "content": "¿Y cuándo compensa NgRx SignalStore? En el equipo hay quien lo quiere usar para todo.",
            },
            {
                "role": "assistant",
                "content": r"""Compensa cuando tienes **muchos stores con la misma forma** y quieres que todos se escriban igual, no por un carrito.

Señales de que lo necesitas:

- Diez o más stores que repiten el patrón «cargar → `loading` → datos o `error`», y cada uno lo implementa a su manera.
- Colecciones grandes de entidades con altas, bajas y actualizaciones por id: `@ngrx/signals/entities` (`withEntities`) te ahorra ese código.
- Efectos asíncronos encadenados con RxJS (cancelación, reintentos) que quieres declarar de forma uniforme con `rxMethod`.
- Un equipo grande en el que la convención impuesta vale más que la libertad.

Señales de que no: dos o tres stores, lógica sencilla, o un equipo que todavía está aprendiendo signals. Añade una dependencia, un vocabulario nuevo (`withState`, `withComputed`, `patchState`) y una capa más que depurar.

El mismo carrito, ahora cargado del servidor, como SignalStore:

```ts
// cart.store.ts
import { computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { patchState, signalStore, withComputed, withHooks, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';
import { CartItem } from './cart-item';

type CartState = {
  items: CartItem[];
  loading: boolean;
  error: string | null;
};

const initialState: CartState = { items: [], loading: false, error: null };

export const CartStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withComputed(({ items }) => ({
    count: computed(() => items().reduce((n, item) => n + item.quantity, 0)),
    totalCents: computed(() => items().reduce((sum, item) => sum + item.unitPriceCents * item.quantity, 0)),
  })),
  withMethods((store, http = inject(HttpClient)) => ({
    remove(productId: string): void {
      patchState(store, { items: store.items().filter((item) => item.productId !== productId) });
    },
    load: rxMethod<void>(
      pipe(
        tap(() => patchState(store, { loading: true, error: null })),
        switchMap(() =>
          http.get<CartItem[]>('/api/cart').pipe(
            tap((items) => patchState(store, { items, loading: false })),
            // El catchError va dentro: si estuviera fuera, un error mataría el rxMethod para siempre
            catchError(() => {
              patchState(store, { loading: false, error: 'No se pudo cargar el carrito' });
              return EMPTY;
            }),
          ),
        ),
      ),
    ),
  })),
  withHooks({
    onInit(store) {
      store.load();
    },
  }),
);
```

Fíjate en el detalle que hace viable la transición: los componentes usan `inject(CartStore)`, `cart.count()`, `cart.remove(id)`, **igual que con el servicio**. Si diseñas el servicio con esa API pública (signals de lectura + métodos con nombre), migrar un store concreto a SignalStore el día que lo necesite no toca ningún componente.

Mi recomendación para el equipo: servicios con signals por defecto, con las tres reglas de antes como norma de revisión, y SignalStore solo en los dominios que cumplan las señales de arriba. Para decidirlo con datos, migra un store real y compara líneas de código, legibilidad del test y facilidad para depurar; si no gana en al menos dos de tres, no lo generalicéis.

Verificación de este store: con `HttpTestingController`, comprueba que tras `TestBed.inject(CartStore)` sale una petición a `/api/cart`; responde con un error 500 y verifica `error()` con el mensaje y `loading()` a `false`; llama otra vez a `load()` y comprueba que sale una segunda petición, señal de que el `rxMethod` sigue vivo tras el error.""",
            },
        ]
    },
    # 25) ERR principiante: NullInjectorError No provider for _HttpClient.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Al abrir la app me queda la pantalla en blanco y en la consola sale esto:

```
ERROR NullInjectorError: R3InjectorError(Standalone[_AppComponent])[_UserService -> _HttpClient -> _HttpClient]:
  NullInjectorError: No provider for _HttpClient!
```

Mi `UserService` tiene `private http = inject(HttpClient)` y es `providedIn: 'root'`. En el tutorial ponían `HttpClientModule` en el `AppModule`, pero yo no tengo `AppModule`.""",
            },
            {
                "role": "assistant",
                "content": r"""Te falta registrar `HttpClient`. En una app standalone se hace con `provideHttpClient()` en `app.config.ts`, que sustituye a importar `HttpClientModule` en el `AppModule`.

```ts
// app.config.ts
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withFetch()),
  ],
};
```

Y comprueba que `main.ts` usa ese objeto:

```ts
// main.ts
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig).catch((err) => console.error(err));
```

**Cómo leer el mensaje**, porque vas a ver muchos parecidos:

- `R3InjectorError(Standalone[_AppComponent])`: dónde empezó la búsqueda, el inyector de entorno de la app arrancada con `AppComponent`.
- `[_UserService -> _HttpClient -> _HttpClient]`: la **cadena de dependencias**, de izquierda a derecha. Algo pidió `UserService`, que pidió `HttpClient`, que nadie provee. El último eslabón es siempre lo que falta; que aparezca repetido es solo el recorrido por los inyectores.
- El guion bajo delante de los nombres lo añade el compilador a las clases en los builds de desarrollo; léelo como `HttpClient`.
- **Pantalla en blanco**: el error salta mientras se crea el primer componente, así que `bootstrapApplication` falla y no se pinta nada. Por eso el `.catch` de `main.ts` importa: sin él, el error puede quedar menos visible.

Tres variantes del mismo error que conviene reconocer:

1. **`HttpClientModule` en el `imports` de un componente.** En Angular 18 quedó deprecado y no es la forma de registrar providers globales en standalone. Usa `provideHttpClient()`.
2. **En los tests.** El `TestBed` no lee tu `app.config.ts`. Si el spec de un componente que usa `UserService` da este mismo error, añade los providers de prueba:

```ts
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

TestBed.configureTestingModule({
  imports: [UserProfileComponent],
  providers: [provideHttpClient(), provideHttpClientTesting()], // en este orden
});
```

3. **`No provider for _ActivatedRoute` o `_Router`.** Mismo patrón: falta `provideRouter(...)` en la config (o en el `TestBed`).

Por qué `withFetch()`: hace que `HttpClient` use `fetch` en lugar de `XMLHttpRequest`. Es lo recomendado si algún día activas SSR y no cambia tu código.

Verificación: reinicia `ng serve`, la app pinta, el error desaparece de la consola y en Network ves la petición que hace `UserService`.""",
            },
        ]
    },
    # 26) ControlValueAccessor para un componente propio en formularios reactivos (rioplatense).
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "Armé un componente `<app-star-rating>` de 1 a 5 estrellas y lo quiero usar con `formControlName=\"rating\"` dentro de un formulario reactivo. Que respete `disable()`, que marque el control como touched y que se actualice si hago `patchValue` desde afuera. Probé con `model()` y no me anda con el formulario. ¿Cómo lo hago?",
            },
            {
                "role": "assistant",
                "content": r"""Lo que necesitás es implementar `ControlValueAccessor` (CVA). Es el contrato que usan `formControlName`, `formControl` y `ngModel` para hablar con cualquier control. `model()` sirve para `[(valor)]` entre componentes, pero los formularios no lo conocen: no sabe de `disable()`, ni de touched, ni de validación.

```ts
// star-rating.component.ts
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  forwardRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'app-star-rating',
  template: `
    <div role="radiogroup" [attr.aria-label]="label()" (focusout)="onFocusOut($event)">
      @for (star of stars(); track star) {
        <button
          type="button"
          role="radio"
          [attr.aria-checked]="star === value()"
          [attr.aria-label]="star + ' de ' + max()"
          [class.filled]="star <= value()"
          [disabled]="disabled()"
          (click)="select(star)"
        >★</button>
      }
    </div>
  `,
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => StarRatingComponent), multi: true },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StarRatingComponent implements ControlValueAccessor {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly label = input('Puntuación');
  readonly max = input(5);
  protected readonly stars = computed(() => Array.from({ length: this.max() }, (_, i) => i + 1));

  protected readonly value = signal(0);
  protected readonly disabled = signal(false);

  private onChange: (value: number) => void = () => {};
  private onTouched: () => void = () => {};

  // El formulario → el componente (setValue, patchValue, reset)
  writeValue(value: number | null): void {
    this.value.set(value ?? 0);
  }

  registerOnChange(fn: (value: number) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled.set(isDisabled);
  }

  // El componente → el formulario
  protected select(star: number): void {
    if (this.disabled()) return;
    this.value.set(star);
    this.onChange(star);
  }

  // Touched solo cuando el foco sale del grupo entero, no al pasar de una estrella a otra
  protected onFocusOut(event: FocusEvent): void {
    const next = event.relatedTarget;
    if (!(next instanceof Node) || !this.host.nativeElement.contains(next)) {
      this.onTouched();
    }
  }
}
```

Uso:

```ts
readonly form = inject(NonNullableFormBuilder).group({
  rating: [0, Validators.min(1)],
  comment: [''],
});
```

```html
<form [formGroup]="form">
  <app-star-rating formControlName="rating" label="Tu puntuación" />
  @if (form.controls.rating.touched && form.controls.rating.invalid) {
    <p class="error">Elegí al menos una estrella.</p>
  }
</form>
```

Las piezas que suelen fallar:

- **`NG_VALUE_ACCESSOR` con `forwardRef` y `multi: true`.** Es como el formulario encuentra tu componente. `forwardRef` hace falta porque la clase todavía no está definida cuando se evalúa el decorador.
- **Estado interno en signals.** `writeValue` y `setDisabledState` los llama el formulario por fuera de cualquier evento de tu plantilla (un `patchValue` del padre, por ejemplo). Con `OnPush` y campos planos, la vista no se enteraría; con `signal`, sí. Esa es la causa típica de «el `patchValue` no se ve».
- **`onChange` solo ante acciones del usuario.** Nunca lo llames dentro de `writeValue`: el formulario ya conoce ese valor, y avisarle de vuelta marca el control como modificado sin que nadie lo haya tocado.
- **`focusout` con `relatedTarget`.** Así el control queda touched cuando el usuario sale del componente, no al moverse con Tab entre estrellas.
- **Validación afuera.** El componente no sabe de reglas: el `Validators.min(1)` vive en el formulario, que es donde corresponde.

Verificación con un host de prueba:

```ts
@Component({
  imports: [ReactiveFormsModule, StarRatingComponent],
  template: `<app-star-rating [formControl]="rating" />`,
})
class HostComponent {
  readonly rating = new FormControl(0, { nonNullable: true });
}

it('sincroniza valor, disabled y touched con el FormControl', () => {
  TestBed.configureTestingModule({ imports: [HostComponent] });
  const fixture = TestBed.createComponent(HostComponent);
  const control = fixture.componentInstance.rating;
  fixture.detectChanges();

  control.setValue(4); // de afuera hacia adentro
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelectorAll('button.filled').length).toBe(4);

  fixture.nativeElement.querySelectorAll('button')[1].click(); // de adentro hacia afuera
  expect(control.value).toBe(2);

  control.disable();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
});
```""",
            },
        ]
    },
    # 27) EN: proyección de contenido, ngTemplateOutlet y queries signal.
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm building a small component library in Angular 19: a Card with several content slots, a Tabs component, and a List where consumers can customize how each row renders. How do I do multi-slot projection, read the child tabs, and pass a row template with context? Old docs keep using @ViewChild and @ContentChildren with QueryList.",
            },
            {
                "role": "assistant",
                "content": r"""Three tools, one per need: `<ng-content select>` for static slots, `contentChildren()` to read projected components as a signal, and `ngTemplateOutlet` with a context for templates the consumer provides. The signal-based queries (`viewChild`, `contentChild`, `contentChildren`) are stable since Angular 19 and replace the decorators.

**1. Card with named slots**

```ts
import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-card',
  template: `
    <article class="card">
      <header><ng-content select="[cardTitle]" /></header>
      <section><ng-content /></section>
      <footer><ng-content select="[cardActions]" /></footer>
    </article>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CardComponent {}
```

```html
<app-card>
  <h2 cardTitle>Invoice #1042</h2>
  <p>Due in 5 days.</p>
  <div cardActions><button type="button">Pay</button></div>
</app-card>
```

Unmatched content goes to the `<ng-content>` without `select`. One caveat: projected content is created by the **parent**, always, even if you wrap the `<ng-content>` in an `@if`. If a slot must be lazy, conditional or repeated, ask for a template instead (section 3).

**2. Tabs that read their children**

```ts
import {
  ChangeDetectionStrategy, Component, TemplateRef, computed, contentChildren, input, model, viewChild,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

@Component({
  selector: 'app-tab',
  // The content lives in a template, so only the active tab is rendered
  template: `<ng-template><ng-content /></ng-template>`,
})
export class TabComponent {
  readonly label = input.required<string>();
  readonly content = viewChild.required(TemplateRef);
}

@Component({
  selector: 'app-tabs',
  imports: [NgTemplateOutlet],
  template: `
    <div role="tablist">
      @for (tab of tabs(); track tab; let i = $index) {
        <button type="button" role="tab" [attr.aria-selected]="i === activeIndex()" (click)="activeIndex.set(i)">
          {{ tab.label() }}
        </button>
      }
    </div>
    @if (activeTab(); as tab) {
      <div role="tabpanel">
        <ng-container [ngTemplateOutlet]="tab.content()" />
      </div>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TabsComponent {
  readonly tabs = contentChildren(TabComponent);
  readonly activeIndex = model(0);
  readonly activeTab = computed(() => this.tabs()[this.activeIndex()]);
}
```

```html
<app-tabs [(activeIndex)]="selectedTab">
  <app-tab label="Profile"><app-profile-form /></app-tab>
  <app-tab label="Billing"><app-billing-settings /></app-tab>
  @if (isAdmin()) {
    <app-tab label="Audit log"><app-audit-log /></app-tab>
  }
</app-tabs>
```

`contentChildren()` returns a `Signal<readonly TabComponent[]>` that updates when tabs appear or disappear (the `@if` above), so `activeTab` recomputes on its own. With `@ContentChildren` you had a `QueryList`, `ngAfterContentInit` timing and `changes` subscriptions to manage.

**3. List with a consumer-provided row template**

```ts
import { ChangeDetectionStrategy, Component, TemplateRef, contentChild, input } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

export interface RowContext<T> {
  $implicit: T;
  index: number;
}

@Component({
  selector: 'app-list',
  imports: [NgTemplateOutlet],
  template: `
    <ul>
      @for (item of items(); track trackBy()(item)) {
        <li>
          <ng-container
            [ngTemplateOutlet]="rowTemplate() ?? defaultRow"
            [ngTemplateOutletContext]="{ $implicit: item, index: $index }"
          />
        </li>
      }
    </ul>
    <ng-template #defaultRow let-item>{{ item }}</ng-template>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ListComponent<T> {
  readonly items = input.required<readonly T[]>();
  readonly trackBy = input.required<(item: T) => unknown>();
  readonly rowTemplate = contentChild<TemplateRef<RowContext<T>>>('row');
}
```

```html
<app-list [items]="users()" [trackBy]="byId">
  <ng-template #row let-user let-i="index">{{ i + 1 }}. {{ user.name }} ({{ user.email }})</ng-template>
</app-list>
```

`$implicit` is what `let-user` receives; named keys need `let-i="index"`. The `trackBy` input exists because the list can't know your items' identity, and tracking by index would reuse DOM for the wrong rows after a removal.

| Old | New |
|---|---|
| `@ViewChild(X) x!: X` | `x = viewChild(X)` / `viewChild.required(X)` |
| `@ContentChildren(X) xs!: QueryList<X>` | `xs = contentChildren(X)` |
| `{ static: true }` | gone: read the signal where you need it |
| read in `ngAfterViewInit` | read in a `computed`, `effect` or the template |

Verification: in a test host with two tabs, click the second tab button and assert the panel shows the second tab's content; toggle `isAdmin` and assert the tab list grows from two to three buttons without any manual subscription.""",
            },
        ]
    },
    # 28) ERR: TS2339 al intentar set() sobre un input(); model/output/linkedSignal.
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un selector de tamaño de página y quiero cambiar el valor desde el propio componente cuando el usuario elige otro, pero no compila:

```
error TS2339: Property 'set' does not exist on type 'InputSignal<number>'.
```

```ts
@Component({
  selector: 'app-page-size',
  template: `
    <select [value]="pageSize()" (change)="change(+$any($event.target).value)">
      @for (size of sizes; track size) { <option [value]="size">{{ size }}</option> }
    </select>
  `,
})
export class PageSizeComponent {
  readonly pageSize = input(20);
  readonly sizes = [10, 20, 50, 100];

  change(size: number) {
    this.pageSize.set(size);
  }
}
```

Antes con `@Input() pageSize = 20` hacía `this.pageSize = size` y funcionaba.""",
            },
            {
                "role": "assistant",
                "content": r"""Los `input()` son de solo lectura a propósito: el valor pertenece al padre. Con `@Input()` la asignación compilaba, pero creaba dos verdades: el padre seguía con 20, el hijo mostraba 50, y en cuanto el padre volvía a pasar un valor, pisaba la elección del usuario. El error de tipos te está señalando ese diseño.

La pregunta que decide el arreglo es **quién necesita saber el nuevo valor**.

**1. El padre debe enterarse (tu caso: el tamaño cambia la consulta de la tabla) → `model()`.** Es un input escribible que, al hacer `set`, emite `pageSizeChange` y habilita el two-way binding:

```ts
import { ChangeDetectionStrategy, Component, model } from '@angular/core';

@Component({
  selector: 'app-page-size',
  template: `
    <label>
      Filas por página
      <select [value]="pageSize()" (change)="change($event)">
        @for (size of sizes; track size) {
          <option [value]="size">{{ size }}</option>
        }
      </select>
    </label>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PageSizeComponent {
  readonly pageSize = model(20);
  readonly sizes = [10, 20, 50, 100] as const;

  change(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.pageSize.set(Number(select.value));
  }
}
```

```ts
// padre
@Component({
  selector: 'app-orders-page',
  imports: [PageSizeComponent],
  template: `
    <app-page-size [(pageSize)]="pageSize" />
    <p>Mostrando {{ pageSize() }} pedidos por página</p>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrdersPageComponent {
  readonly pageSize = signal(20); // el padre sigue siendo el dueño del estado
}
```

Con `[(pageSize)]="pageSize"` (pasando el signal, sin paréntesis), Angular enlaza en los dos sentidos: el hijo escribe y el signal del padre se actualiza.

**2. Solo quieres avisar, y que el padre decida → `output()`.** Mantienes `input()` y emites:

```ts
readonly pageSize = input(20);
readonly pageSizeChange = output<number>();
// en change(): this.pageSizeChange.emit(Number(select.value));
```

Es lo que `model()` hace por dentro, pero explícito. Útil si el padre puede rechazar el cambio (por ejemplo, validar contra un máximo).

**3. Estado local editable que se reinicia cuando el padre manda otro valor → `linkedSignal`** (Angular 19, en developer preview): `readonly localSize = linkedSignal(() => this.pageSize());`. Se puede escribir con `set`, y vuelve al valor del input cuando este cambia. Solo tiene sentido si el padre no necesita enterarse.

De paso, dos mejoras sobre tu plantilla: `$any($event.target)` desactiva la comprobación de tipos justo donde hay un error posible (prefiere el cast acotado en el método), y el `<select>` necesitaba una etiqueta para accesibilidad.

Verificación: en la página, elige 50: el texto del padre pasa a «Mostrando 50 pedidos por página». Si en el padre haces `pageSize.set(10)` (por ejemplo, desde un botón «restablecer»), el `<select>` muestra 10. Las dos direcciones funcionan y hay una sola verdad: el signal del padre.""",
            },
        ]
    },
    # 29) Test de servicio HTTP con HttpTestingController e interceptor (system exacta).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cómo testeo un servicio que usa HttpClient en Angular 19? Quiero comprobar la URL, los query params, la respuesta y el caso de error, y de paso que el interceptor de auth añade el token. Sin levantar ningún servidor.",
            },
            {
                "role": "assistant",
                "content": r"""Con `provideHttpClientTesting()` y `HttpTestingController`: `HttpClient` funciona de verdad (interceptores incluidos), pero las peticiones no salen a la red; quedan en un backend falso donde las inspeccionas y les respondes a mano.

El código bajo prueba:

```ts
// token.store.ts
import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class TokenStore {
  readonly token = signal<string | null>(null);
}
```

```ts
// auth.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { TokenStore } from './token.store';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(TokenStore).token();
  return next(token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req);
};
```

```ts
// orders.api.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export type OrderStatus = 'pending' | 'paid' | 'shipped';

export interface Order {
  id: string;
  status: OrderStatus;
  totalCents: number;
}

@Injectable({ providedIn: 'root' })
export class OrdersApi {
  private readonly http = inject(HttpClient);

  list(status?: OrderStatus): Observable<Order[]> {
    const params = status ? new HttpParams().set('status', status) : undefined;
    return this.http.get<Order[]>('/api/orders', { params });
  }
}
```

Los tests:

```ts
// orders.api.spec.ts
import { HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { authInterceptor } from './auth.interceptor';
import { Order, OrdersApi } from './orders.api';
import { TokenStore } from './token.store';

describe('OrdersApi', () => {
  let api: OrdersApi;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])), // la misma cadena que en producción
        provideHttpClientTesting(),                              // siempre después de provideHttpClient
      ],
    });
    api = TestBed.inject(OrdersApi);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  // Falla si quedó alguna petición sin atender o si salió una que nadie esperaba
  afterEach(() => httpTesting.verify());

  it('pide los pedidos filtrados por estado y devuelve el cuerpo', () => {
    TestBed.inject(TokenStore).token.set('test-token');
    const body: Order[] = [{ id: 'o1', status: 'pending', totalCents: 1_500 }];
    let result: Order[] | undefined;

    api.list('pending').subscribe((orders) => (result = orders));

    const req = httpTesting.expectOne(
      (r) => r.url === '/api/orders' && r.params.get('status') === 'pending',
      'GET /api/orders?status=pending',
    );
    expect(req.request.method).toBe('GET');
    expect(req.request.headers.get('Authorization')).toBe('Bearer test-token');

    req.flush(body);
    expect(result).toEqual(body);
  });

  it('sin token no envía la cabecera Authorization', () => {
    api.list().subscribe();

    const req = httpTesting.expectOne('/api/orders');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush([]);
  });

  it('propaga el error del servidor como HttpErrorResponse', () => {
    let error: HttpErrorResponse | undefined;

    api.list().subscribe({ error: (err: HttpErrorResponse) => (error = err) });

    httpTesting
      .expectOne('/api/orders')
      .flush({ message: 'boom' }, { status: 500, statusText: 'Internal Server Error' });

    expect(error?.status).toBe(500);
    expect(error?.error).toEqual({ message: 'boom' });
  });
});
```

Por qué está montado así:

- **El interceptor se prueba a través de la cadena real.** `withInterceptors([authInterceptor])` en el `TestBed` reproduce la configuración de producción; si mañana alguien reordena o quita el interceptor de `app.config.ts`, el test de integración de esa configuración es el que debe fallar, y este sigue documentando el contrato.
- **Matcher por función en `expectOne`.** Comparar el string completo con query params es frágil (el orden de los parámetros cambia la URL); la función comprueba `url` y `params` por separado. El segundo argumento es la descripción que verás si falla.
- **Todo es síncrono.** `flush` entrega la respuesta y ejecuta los suscriptores en el acto: no hace falta `fakeAsync`, `waitForAsync` ni esperas.
- **`verify()` en `afterEach`** detecta peticiones duplicadas o inesperadas, el bug más común en servicios que se suscriben dos veces.
- **El orden de los providers** importa: `provideHttpClientTesting()` sustituye el backend que registra `provideHttpClient()`, así que va después.

Comprobación de que los tests muerden: comenta el `req.clone(...)` del interceptor y ejecuta `ng test`; el primer test debe fallar en la cabecera `Authorization`. Haz que `list()` ignore el parámetro `status` y falla el `expectOne` con el mensaje «GET /api/orders?status=pending».""",
            },
        ]
    },
    # 30) Rendimiento de una lista de 5.000 filas: método, virtual scroll y métodos en plantilla (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una tabla de 5.000 filas en Angular 19 con un input de filtro arriba, y escribir en el filtro va a tirones, como medio segundo por tecla. ¿Por dónde empiezo?",
            },
            {
                "role": "assistant",
                "content": r"""Por medir, no por cambiar código. Medio segundo por tecla tiene cuatro sospechosos habituales y cada uno se arregla distinto; el profiler te dice cuál es en cinco minutos.

**1. Medir**

- **Angular DevTools → Profiler**: graba mientras escribes tres letras. Verás cuántos ciclos de detección de cambios hay por tecla y cuánto tarda cada componente.
- **Chrome DevTools → Performance**: graba lo mismo. Busca tareas largas (barras rojas) y abre «Bottom-Up» para ver qué funciones se llevan el tiempo.

**2. Hipótesis, en el orden en que suelen aparecer**

| Síntoma en el profiler | Causa probable | Arreglo |
|---|---|---|
| Mucho tiempo en «Recalculate Style» / «Layout» y creación de nodos | Se pintan 5.000 filas de DOM | Virtual scroll o paginación |
| Una función tuya llamada miles de veces por ciclo | Métodos o pipes impuros en la plantilla | Precalcular con `computed` o pipe puro |
| Todos los componentes de la app aparecen en cada tecla | Detección de cambios por defecto en todo el árbol | `OnPush` |
| El tiempo está en tu filtro | Filtrado caro por tecla | Debounce + preparar los datos una vez |

**3. La versión que cubre las causas estructurales**

```ts
// orders-table.component.ts
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { ScrollingModule } from '@angular/cdk/scrolling';
import { debounceTime, distinctUntilChanged, map } from 'rxjs';

export interface OrderRow {
  id: string;
  customer: string;
  sku: string;
  priceCents: number;
}

const FILTER_DEBOUNCE_MS = 150;

@Component({
  selector: 'app-orders-table',
  imports: [ReactiveFormsModule, ScrollingModule],
  template: `
    <input [formControl]="filter" placeholder="Filtrar por cliente o SKU" />
    <p>{{ visibleRows().length }} resultados</p>

    <cdk-virtual-scroll-viewport itemSize="40" class="viewport">
      <div *cdkVirtualFor="let row of visibleRows(); trackBy: trackById" class="row" role="row">
        <span role="cell">{{ row.customer }}</span>
        <span role="cell">{{ row.sku }}</span>
        <span role="cell">{{ formatPrice(row.priceCents) }}</span>
      </div>
    </cdk-virtual-scroll-viewport>
  `,
  styles: `.viewport { height: 600px; } .row { height: 40px; display: grid; grid-template-columns: 2fr 1fr 1fr; }`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrdersTableComponent {
  readonly rows = input.required<readonly OrderRow[]>();

  readonly filter = new FormControl('', { nonNullable: true });
  private readonly query = toSignal(
    this.filter.valueChanges.pipe(
      debounceTime(FILTER_DEBOUNCE_MS),
      map((value) => value.trim().toLowerCase()),
      distinctUntilChanged(),
    ),
    { initialValue: '' },
  );

  // Texto de búsqueda calculado una vez por cambio de datos, no por tecla
  private readonly searchable = computed(() =>
    this.rows().map((row) => ({ row, text: `${row.customer} ${row.sku}`.toLowerCase() })),
  );

  readonly visibleRows = computed(() => {
    const q = this.query();
    const all = this.searchable();
    return q ? all.filter((entry) => entry.text.includes(q)).map((entry) => entry.row) : this.rows();
  });

  readonly trackById = (_index: number, row: OrderRow): string => row.id;

  formatPrice(cents: number): string {
    return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(cents / 100);
  }
}
```

Qué ataca cada pieza:

- **Virtual scroll del CDK:** con 600 px de alto y filas de 40 px, el DOM tiene unas 15 filas visibles más un pequeño margen, no 5.000. Requiere altura fija de fila y de viewport, y usa `*cdkVirtualFor` con `trackBy`; no funciona con `@for`. Si el diseño exige una `<table>` real con alturas variables, la alternativa honesta es paginar.
- **`OnPush` + signals:** cada tecla solo revisa este componente, no la app entera.
- **Debounce de 150 ms:** filtras cuando la persona hace una pausa, no en cada carácter.
- **`searchable` en un `computed`:** los `toLowerCase` de 5.000 filas se hacen una vez cuando llegan los datos, no en cada tecla.

He dejado tu `formatPrice` en la plantilla a propósito: es el segundo sospechoso de la tabla, y cambiar una sola cosa cada vez es lo que permite atribuir cada mejora a su causa.

Mide otra vez con el mismo procedimiento y compara la duración de la tarea por tecla antes y después. Si sigue alta, el profiler te dirá cuál es el siguiente culpable.""",
            },
            {
                "role": "user",
                "content": "Medí con el profiler. Ya no va a tirones al escribir, pero al hacer scroll rápido sigue habiendo saltos, y en «Bottom-Up» casi el 70 % del tiempo está en `formatPrice`, que es el método que dejé en la plantilla.",
            },
            {
                "role": "assistant",
                "content": r"""Ahí está: `formatPrice` crea un `Intl.NumberFormat` **en cada llamada**, y la plantilla lo llama para cada fila visible **en cada ciclo de detección de cambios**. Durante un scroll rápido, el virtual scroll recicla filas y dispara ciclos continuamente; construir un formateador de `Intl` es caro (carga datos de la configuración regional) y lo estás haciendo cientos de veces por segundo.

Dos problemas superpuestos, dos arreglos:

**1. Crea el formateador una sola vez.** Es inmutable y reutilizable:

```ts
const PRICE_FORMAT = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });
```

**2. No formatees en la plantilla: precalcula la etiqueta junto a los datos.** Así el trabajo ocurre una vez por fila cuando cambian los datos, y la plantilla solo lee un string:

```ts
// orders-table.component.ts (cambios respecto a la versión anterior)
const PRICE_FORMAT = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });

interface OrderView extends OrderRow {
  priceLabel: string;
  searchText: string;
}

export class OrdersTableComponent {
  readonly rows = input.required<readonly OrderRow[]>();

  // Una pasada por cambio de datos: etiqueta de precio y texto de búsqueda juntos
  private readonly views = computed<readonly OrderView[]>(() =>
    this.rows().map((row) => ({
      ...row,
      priceLabel: PRICE_FORMAT.format(row.priceCents / 100),
      searchText: `${row.customer} ${row.sku}`.toLowerCase(),
    })),
  );

  readonly visibleRows = computed(() => {
    const q = this.query();
    const all = this.views();
    return q ? all.filter((view) => view.searchText.includes(q)) : all;
  });

  readonly trackById = (_index: number, row: OrderView): string => row.id;
}
```

```html
<span role="cell">{{ row.priceLabel }}</span>
```

`views` sustituye a `searchable`, `formatPrice` desaparece y `query`/`filter` quedan como estaban.

Por qué prefiero esto a un pipe puro (que también sería correcto): el pipe se evalúa por fila cada vez que el virtual scroll crea o recicla una vista, aunque el valor no cambie entre ciclos. Precalculado, el coste total es 5.000 formateos cuando llegan los datos y cero durante el scroll. Si la etiqueta dependiera de algo que cambia a menudo (la moneda que elige el usuario), entonces sí: pipe puro con la moneda como argumento.

La regla general que te deja esta medición: **en una plantilla, solo lecturas baratas** (propiedades, signals, `computed`, pipes puros). Cualquier llamada a un método se ejecuta por fila y por ciclo, y su coste se multiplica por ambos.

Verificación: repite la grabación de scroll rápido. `formatPrice` ya no aparece en «Bottom-Up», las tareas largas durante el scroll deberían desaparecer o quedar por debajo de 50 ms, y en el Profiler de Angular cada ciclo de este componente debería costar una fracción de lo que costaba. Si quieres una prueba directa, pon temporalmente un `console.count('format')` dentro del `map` de `views`: debe contar 5.000 al cargar y no volver a contar al hacer scroll ni al filtrar.""",
            },
        ]
    },
]
