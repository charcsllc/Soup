"""Go 1.22/1.23: slices, maps, interfaces, errores, concurrencia, generics, testing, net/http, herramientas."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Slices y aliasing con append; multiturno con la expresión de tres índices
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un bug que no entiendo. Esta función debería devolver dos slices independientes, pero al modificar el segundo se cambia el primero:

```go
func split(all []int) (evens, odds []int) {
    evens = all[:0]
    for _, v := range all {
        if v%2 == 0 {
            evens = append(evens, v)
        } else {
            odds = append(odds, v)
        }
    }
    return evens, odds
}

func main() {
    all := []int{2, 4, 1, 3, 6}
    evens, odds := split(all)
    fmt.Println(evens, odds) // [2 4 6] [1 3]  ← correcto
    fmt.Println(all)         // [2 4 6 3 6]  ← ¡¿?!
}
```

¿Por qué `all` cambia si yo nunca lo toco?""",
            },
            {
                "role": "assistant",
                "content": r"""Sí lo tocas: `evens = all[:0]` **comparte el array subyacente** con `all`. Un slice son tres valores (puntero, longitud, capacidad); `all[:0]` crea un slice de longitud 0 pero con el mismo puntero y capacidad 5. Cada `append(evens, v)` que cabe en esa capacidad escribe **sobre los elementos de `all`**.

Traza:

| paso | `evens` (len/cap) | `all` |
|---|---|---|
| inicio | 0/5 | `[2 4 1 3 6]` |
| append 2 | 1/5 | `[2 4 1 3 6]` (escribe 2 en la posición 0, ya era 2) |
| append 4 | 2/5 | `[2 4 1 3 6]` (idem) |
| append 6 | 3/5 | `[2 4 6 3 6]` (escribe 6 en la posición 2, pisa el 1) |

Por eso el resultado parece correcto: `evens` lee `[2 4 6]` del array compartido, y `all` muestra el daño. Es el patrón «filtrar in situ» (`b := a[:0]`) que la propia documentación de Go menciona como truco para evitar asignar; es correcto **solo si nadie va a usar `a` después**. Tu función devuelve dos resultados y el llamador conserva `all`, así que no aplica.

Arreglo mínimo: empieza con `nil` y deja que `append` asigne:

```go
func split(all []int) (evens, odds []int) {
    for _, v := range all {
        if v%2 == 0 {
            evens = append(evens, v)
        } else {
            odds = append(odds, v)
        }
    }
    return evens, odds
}
```

Un slice `nil` tiene capacidad 0; el primer `append` crea un array nuevo. Si sabes que la entrada es grande, pre-reserva con `make([]int, 0, len(all)/2)` para ahorrar reasignaciones; sigue siendo memoria propia.

La regla general: `append` **solo** asigna un array nuevo cuando `len == cap`. Siempre que recortes un slice (`a[:n]`, `a[i:j]`) y después hagas `append`, pregúntate quién más ve ese array. Si la respuesta no es «nadie», copia (`slices.Clone(a)`) o usa la expresión de tres índices para limitar la capacidad.

Test que habría cazado esto:

```go
func TestSplitNoMutaEntrada(t *testing.T) {
    all := []int{2, 4, 1, 3, 6}
    want := slices.Clone(all)
    split(all)
    if !slices.Equal(all, want) {
        t.Fatalf("split mutó la entrada: %v, quería %v", all, want)
    }
}
```""",
            },
            {"role": "user", "content": "¿Y qué es eso de la expresión de tres índices? Nunca la he usado."},
            {
                "role": "assistant",
                "content": r"""`a[low:high:max]` crea un slice con longitud `high-low` y **capacidad `max-low`** en lugar de heredar toda la capacidad restante del array. Sirve para una cosa: garantizar que un `append` posterior no pueda escribir sobre lo que hay detrás.

```go
all := []int{2, 4, 1, 3, 6}

a := all[:2]       // len 2, cap 5  → append escribe en all[2]
b := all[:2:2]     // len 2, cap 2  → append asigna un array nuevo

a = append(a, 99)  // all es ahora [2 4 99 3 6]
b = append(b, 99)  // all no cambia; b vive en otro array
```

Se usa cuando entregas un trozo de un buffer a otro código y quieres que, si ese código hace `append`, se lleve su propia copia en vez de pisar tus datos. Es la forma de «cerrar» un slice por el final. Aplicado a tu ejemplo original, `evens = all[:0:0]` habría forzado la copia en el primer `append` y el bug habría desaparecido; aun así, para una función que construye resultados nuevos, empezar en `nil` es más claro que un `[:0:0]` que el lector tiene que descifrar.

Dos detalles:

- `max` no puede superar `cap(all)`; si lo hace, *panic* en tiempo de ejecución.
- No existe forma de «cerrar» un slice por el principio: `all[2:]` siempre comparte los elementos anteriores en memoria (aunque no sean accesibles), lo que importa para la retención de memoria, no para la corrección. Si recortas un slice pequeño de uno enorme y lo guardas mucho tiempo, el array enorme no se libera; ahí lo que toca es `slices.Clone`.

Comprobación rápida de que entiendes los tres números:

```go
s := make([]int, 3, 10)
fmt.Println(len(s[1:2]), cap(s[1:2]))     // 1 9
fmt.Println(len(s[1:2:4]), cap(s[1:2:4])) // 1 3
```""",
            },
        ]
    },
    # 2) Maps: nil map, orden de iteración, campos de struct en map. Principiante. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Soy nuevo en Go y los maps me dan tres problemas seguidos:

1. `panic: assignment to entry in nil map` en cuanto hago `var m map[string]int; m["a"] = 1`.
2. Cuando imprimo un map con un `for range`, cada ejecución sale en un orden distinto.
3. `m["x"].count++` no compila: «cannot assign to struct field m["x"].count in map».

¿Qué estoy entendiendo mal?""",
            },
            {
                "role": "assistant",
                "content": r"""Las tres cosas son decisiones deliberadas del lenguaje, no bugs tuyos.

**1. El map cero es `nil` y no se puede escribir.** `var m map[string]int` declara un map sin memoria detrás. Leer de él funciona (devuelve el valor cero, `0`), pero escribir hace *panic*. Hay que crearlo:

```go
m := make(map[string]int)           // vacío, listo para escribir
m := map[string]int{"a": 1}         // con valores iniciales
m := make(map[string]int, 1000)     // con capacidad sugerida si sabes el tamaño
```

Por qué leer sí y escribir no: un map `nil` se comporta como un map vacío para todo lo que no sea insertar, y eso permite que un struct con un campo map sin inicializar se pueda consultar sin comprobar `nil`. El *panic* al escribir es lo que te avisa de que olvidaste el `make`.

**2. El orden de iteración es aleatorio a propósito.** Desde Go 1.0 el *runtime* aleatoriza el punto de inicio de cada `range` sobre un map, precisamente para que nadie dependa del orden (que de todas formas cambiaría al crecer el map). Si necesitas orden, ordena las claves:

```go
import (
    "maps"
    "slices"
)

for _, k := range slices.Sorted(maps.Keys(m)) {
    fmt.Println(k, m[k])
}
```

`maps.Keys` devuelve un iterador y `slices.Sorted` lo recoge ordenado (ambos desde Go 1.23). Antes de 1.23: `keys := make([]string, 0, len(m))`, un bucle para rellenarlo y `sort.Strings(keys)`.

**3. Los valores de un map no son direccionables.** `m["x"]` devuelve una **copia** del struct; `m["x"].count++` modificaría la copia y la tiraría, así que el compilador lo prohíbe en lugar de dejar que hagas algo inútil. Dos soluciones:

```go
// a) Guardar punteros: el map contiene *Stats, el struct vive aparte
m := map[string]*Stats{}
if m["x"] == nil {
    m["x"] = &Stats{}
}
m["x"].count++

// b) Leer, modificar, reescribir: válido para structs pequeños
s := m["x"]
s.count++
m["x"] = s
```

La opción a) es la habitual cuando el struct se modifica mucho; la b) cuando el map es la única fuente de verdad y quieres evitar punteros compartidos.

Un cuarto punto que te vas a encontrar enseguida: **distinguir «no está» de «está con valor cero»**. `m["falta"]` devuelve `0` igual que `m["cero"]` cuando guardaste un 0. Usa la forma de dos valores:

```go
v, ok := m["falta"]
if !ok {
    // la clave no existe
}
```

Y `delete(m, "k")` borra sin fallar si la clave no existe.

Para comprobar los tres puntos en diez líneas:

```go
func main() {
    var nilMap map[string]int
    fmt.Println(nilMap["a"], len(nilMap)) // 0 0: leer un map nil es seguro

    m := map[string]Stats{"x": {}}
    s := m["x"]
    s.count++
    m["x"] = s
    fmt.Println(m["x"].count) // 1

    _, ok := m["y"]
    fmt.Println(ok) // false
}
```""",
            },
        ]
    },
    # 3) Interfaces implícitas: definirlas en el consumidor, pequeñas, comprobación en compilación
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de Java y no entiendo cómo organizar las interfaces en Go. ¿Las defino junto al struct que las implementa, como un `implements`? Tengo un `PostgresRepo` y quiero que el servicio no dependa de Postgres para poder testearlo.",
            },
            {
                "role": "assistant",
                "content": r"""Al revés que en Java: la interfaz la define **quien la consume**, no quien la implementa, y es tan pequeña como lo que ese consumidor usa. `PostgresRepo` no sabe que existe la interfaz; la satisface por tener los métodos.

```go
// package order (el servicio)
type Store interface {
    Save(ctx context.Context, o Order) error
    ByID(ctx context.Context, id string) (Order, error)
}

type Service struct {
    store Store
}

func NewService(s Store) *Service { return &Service{store: s} }
```

```go
// package postgres (el adaptador)
type Repo struct{ db *sql.DB }

func (r *Repo) Save(ctx context.Context, o order.Order) error { /* SQL */ }
func (r *Repo) ByID(ctx context.Context, id string) (order.Order, error) { /* SQL */ }
func (r *Repo) Migrate(ctx context.Context) error { /* ... */ }
```

`*postgres.Repo` satisface `order.Store` aunque tenga más métodos (`Migrate`) y aunque `postgres` no importe nada de `order` más que el tipo `Order`. En `main` conectas los dos:

```go
svc := order.NewService(postgres.NewRepo(db))
```

Y en los tests del servicio pasas un *fake* en memoria que implementa los dos métodos, sin *mocks* generados ni base de datos:

```go
type memStore struct{ m map[string]order.Order }

func (s *memStore) Save(_ context.Context, o order.Order) error { s.m[o.ID] = o; return nil }
func (s *memStore) ByID(_ context.Context, id string) (order.Order, error) {
    o, ok := s.m[id]
    if !ok {
        return order.Order{}, order.ErrNotFound
    }
    return o, nil
}
```

Por qué está diseñado así y qué cambia respecto a Java:

1. **Sin `implements` no hay acoplamiento entre paquetes.** `postgres` puede vivir en otro módulo, compilarse solo, y seguir siendo un `Store` válido. Puedes extraer una interfaz de un tipo que no es tuyo (`*http.Client`, `*sql.DB`) sin tocarlo.
2. **Interfaces de uno o dos métodos.** La biblioteca estándar es el modelo: `io.Reader`, `io.Writer`, `fmt.Stringer`, `http.Handler`. Una interfaz de 12 métodos obliga a los *fakes* a implementar 12 y acopla al consumidor con cosas que no usa. Si el servicio solo lee, acepta una `Reader` con `ByID` y nada más.
3. **Acepta interfaces, devuelve structs.** `NewRepo` devuelve `*Repo` (concreto, con todos sus métodos a la vista); `NewService` acepta `Store` (abstracto). Devolver una interfaz desde el constructor esconde métodos y rompe la inferencia cuando el llamador quiere algo más.
4. **Comprobación en tiempo de compilación.** Como nadie declara `implements`, un cambio de firma en `Repo` solo falla donde se pase a un `Store`. Para que falle en el propio paquete del adaptador, añade esta línea, que no genera código:

```go
var _ order.Store = (*Repo)(nil)
```

Dos trampas típicas al llegar de Java:

- **No crees una interfaz por cada struct «por si acaso».** Si solo hay una implementación y nadie la sustituye en tests, la interfaz es ruido. Añádela cuando aparezca el segundo uso (el *fake* del test cuenta como segundo uso).
- **Receptor puntero y valor.** Si los métodos tienen receptor `*Repo`, solo `*Repo` satisface la interfaz, no `Repo`. El compilador lo dice con «Repo does not implement Store (method Save has pointer receiver)». Pasa siempre el puntero.

Para verificar la estructura: `go vet ./...` no se queja, el paquete `order` no importa `database/sql` ni `postgres` (`go list -deps ./order | grep -c postgres` devuelve 0), y los tests del servicio corren sin Docker.""",
            },
        ]
    },
    # 4) Errores: %w, errors.Is/As, errores centinela vs tipados; multiturno con %v vs %w
    {
        "messages": [
            {
                "role": "user",
                "content": r"""En mi API tengo este manejo de errores y me dicen en la revisión que «pierdo el error original». ¿A qué se refieren?

```go
func (s *Service) Get(ctx context.Context, id string) (User, error) {
    u, err := s.repo.Find(ctx, id)
    if err != nil {
        return User{}, fmt.Errorf("get user %s: %v", id, err)
    }
    return u, nil
}

// en el handler:
u, err := svc.Get(ctx, id)
if err != nil {
    if err == sql.ErrNoRows {
        w.WriteHeader(404)
        return
    }
    w.WriteHeader(500)
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Se refieren a dos cosas que se combinan: `%v` **formatea** el error como texto y rompe la cadena, y `err == sql.ErrNoRows` compara el error envuelto con el original, que ya no es el mismo valor. El 404 **nunca** se devuelve: todo es 500.

**1. Envuelve con `%w`.** `fmt.Errorf` con `%w` crea un error que guarda el original y lo expone mediante `Unwrap()`. El texto es idéntico al de `%v`; lo que cambia es que el llamador puede recuperar la causa.

```go
return User{}, fmt.Errorf("get user %s: %w", id, err)
```

**2. Compara con `errors.Is`, no con `==`.** `errors.Is(err, target)` recorre la cadena de `Unwrap` y devuelve `true` si cualquier eslabón es `target`:

```go
if errors.Is(err, sql.ErrNoRows) {
```

**3. No dejes que `sql.ErrNoRows` llegue al handler.** Es un detalle del *driver*; si mañana cambias a Mongo, el handler se rompe. Define un error centinela en el dominio y traduce en el repositorio, que es la única capa que conoce `database/sql`:

```go
// package user
var ErrNotFound = errors.New("user not found")

// package postgres
func (r *Repo) Find(ctx context.Context, id string) (user.User, error) {
    row := r.db.QueryRowContext(ctx, `SELECT id, name FROM users WHERE id = $1`, id)
    var u user.User
    if err := row.Scan(&u.ID, &u.Name); err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return user.User{}, user.ErrNotFound
        }
        return user.User{}, fmt.Errorf("find user %s: %w", id, err)
    }
    return u, nil
}
```

Fíjate en que `ErrNotFound` se devuelve **sin envolver** el `sql.ErrNoRows`: el llamador no necesita la causa y así no filtras el *driver* en los mensajes. El resto de errores (conexión caída, timeout) sí se envuelven con `%w`, porque son los que alguien querrá inspeccionar o registrar con su causa.

**4. Cuando el error lleva datos, usa un tipo y `errors.As`.** Un centinela no puede decir *qué* campo falló:

```go
type ValidationError struct {
    Field string
    Msg   string
}

func (e *ValidationError) Error() string { return e.Field + ": " + e.Msg }

// en el handler
var ve *ValidationError
if errors.As(err, &ve) {
    http.Error(w, ve.Error(), http.StatusBadRequest)
    return
}
```

`errors.As` busca en la cadena un error del tipo del puntero que le pasas y lo copia ahí. El receptor es puntero (`*ValidationError`) para que dos errores con el mismo contenido no sean «iguales» por accidente y para que `Error()` no copie el struct.

Handler completo:

```go
u, err := svc.Get(r.Context(), id)
switch {
case errors.Is(err, user.ErrNotFound):
    http.Error(w, "not found", http.StatusNotFound)
    return
case err != nil:
    slog.ErrorContext(r.Context(), "get user", "id", id, "err", err)
    http.Error(w, "internal error", http.StatusInternalServerError)
    return
}
```

Lo que el 500 registra con `slog` incluye toda la cadena («get user 42: find user 42: dial tcp: connection refused»), que es lo que la revisión quería que no perdieras.

Test de regresión para el 404:

```go
func TestGetNotFoundMapsTo404(t *testing.T) {
    svc := NewService(&memStore{})           // vacío → ErrNotFound
    _, err := svc.Get(context.Background(), "nope")
    if !errors.Is(err, user.ErrNotFound) {
        t.Fatalf("got %v, want ErrNotFound", err)
    }
}
```""",
            },
            {"role": "user", "content": "Entonces, ¿`%v` en errores no se usa nunca? Lo veo en un montón de código."},
            {
                "role": "assistant",
                "content": r"""Se usa, pero con una intención concreta: **cortar la cadena a propósito**. `%w` dice «mi llamador puede inspeccionar lo que hay debajo»; `%v` dice «lo que hay debajo es un detalle de implementación mío y no forma parte de mi contrato».

Casos legítimos de `%v`:

1. **Frontera de paquete o de capa.** Si tu librería envuelve con `%w` un error de `net/http` o de un *driver*, estás prometiendo que `errors.Is(err, io.EOF)` funcionará para siempre; cambiar de *driver* se convierte en un cambio incompatible. En una API pública, envuelve con `%w` solo tus propios errores exportados y los de la biblioteca estándar que de verdad quieras exponer.
2. **Errores que terminan en un log y nada más.** Si el único destino es `slog`, la cadena no aporta: el texto ya la contiene.
3. **Cuando el error subyacente lleva información sensible** (una cadena de conexión con contraseña en el mensaje de un *driver*, una ruta interna) y no quieres que suba hacia una respuesta HTTP.

Mucho del `%v` que ves en código viejo no es ninguna de esas tres: es código anterior a Go 1.13 (cuando no existía `%w`) o copiado de él. `go vet` no lo marca, pero el *linter* `errorlint` de golangci-lint sí (`non-wrapping format verb for fmt.Errorf`), y sirve justo para cazar los `%v` sin intención.

Una tabla para decidir:

| Quieres que el llamador pueda... | Usa |
|---|---|
| hacer `errors.Is`/`errors.As` sobre la causa | `%w` |
| solo leer el mensaje | `%v` |
| envolver varias causas (varias validaciones, varios cierres) | `errors.Join(errs...)` o varios `%w` en el mismo `Errorf` (Go 1.20+) |
| devolver el error sin añadir contexto | `return err` tal cual, sin `Errorf` |

El último caso también importa: `fmt.Errorf("%w", err)` sin texto adicional es ruido; si no añades contexto («qué estabas haciendo con qué id»), devuelve `err` directamente.""",
            },
        ]
    },
    # 5) Goroutines y variable de bucle: cambio de semántica en Go 1.22, WaitGroup
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Un tutorial de 2021 dice que este código imprime «3 3 3» por culpa de la variable del bucle y que hay que hacer `i := i` dentro. Lo ejecuto con Go 1.23 y me imprime 0 1 2 (desordenados). ¿El tutorial está mal o tengo suerte?

```go
var wg sync.WaitGroup
for i := 0; i < 3; i++ {
    wg.Add(1)
    go func() {
        defer wg.Done()
        fmt.Println(i)
    }()
}
wg.Wait()
```""",
            },
            {
                "role": "assistant",
                "content": r"""Ni lo uno ni lo otro: el lenguaje cambió. Desde **Go 1.22**, cada iteración de un bucle `for` tiene su **propia** variable `i`; antes había una sola `i` compartida por todas las iteraciones y las *goroutines* la leían después de que el bucle terminara, de ahí el «3 3 3». El tutorial era correcto para Go ≤ 1.21 y el `i := i` era el remedio estándar.

El detalle que importa: la semántica nueva se activa según la línea `go` del `go.mod` del módulo, no según la versión del compilador. Con `go 1.21` en `go.mod` y compilador 1.23 sigues teniendo el comportamiento antiguo. Compruébalo:

```sh
grep '^go ' go.mod     # go 1.22 o superior → por iteración
```

Así que el `i := i` ya no hace falta en módulos modernos; si lo ves en código heredado no es dañino, solo redundante, y `gopls` lo marca como innecesario.

Dos cosas más sobre tu fragmento que sí siguen vigentes:

**1. El orden es aleatorio y lo seguirá siendo.** Las tres *goroutines* se planifican como el *runtime* quiera; «0 1 2» o «2 0 1» son ambos correctos. Si necesitas resultados en orden, escribe en un slice por índice en lugar de imprimir:

```go
results := make([]int, 3)
var wg sync.WaitGroup
for i := range 3 {           // Go 1.22: range sobre un entero
    wg.Add(1)
    go func() {
        defer wg.Done()
        results[i] = compute(i)   // cada goroutine toca solo su posición: sin carrera
    }()
}
wg.Wait()
fmt.Println(results)          // [r0 r1 r2]
```

Escribir en posiciones distintas de un slice desde varias *goroutines* es seguro; lo que no sería seguro es hacer `append` desde varias.

**2. `wg.Add(1)` va antes del `go`**, nunca dentro de la *goroutine*. Si lo pones dentro, `wg.Wait()` puede ejecutarse antes de que ninguna *goroutine* haya hecho `Add` y devolver de inmediato. Desde Go 1.25 existe `wg.Go(func() { ... })` que hace el `Add`/`Done` por ti; en 1.23 el patrón manual de arriba es el correcto.

Para convencerte sin fiarte de la salida, el detector de carreras distingue los dos mundos:

```sh
go run -race .
```

Con `go 1.21` en el `go.mod` avisa de una carrera sobre `i` (lectura en las *goroutines*, escritura en el `i++`); con `go 1.22` o superior, silencio. Y si quieres leer la lógica exacta del cambio, la nota oficial es «loopvar» en las *release notes* de Go 1.22; se puede probar con el compilador antiguo mediante `GOEXPERIMENT=loopvar`, pero ya no te hace falta.""",
            },
        ]
    },
    # 6) Channels: deadlock pegado, unbuffered vs buffered, close + range. System variante
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Explica la causa raíz antes del parche y verifica tu propuesta."},
            {
                "role": "user",
                "content": r"""Esto me muere con un deadlock y no veo por qué, si solo mando 3 cosas:

```go
func main() {
    ch := make(chan int)
    for i := 0; i < 3; i++ {
        ch <- i
    }
    close(ch)
    for v := range ch {
        fmt.Println(v)
    }
}
```

```
fatal error: all goroutines are asleep - deadlock!

goroutine 1 [chan send]:
main.main()
        /home/dev/x/main.go:8 +0x3c
exit status 2
```""",
            },
            {
                "role": "assistant",
                "content": r"""La traza lo dice: la *goroutine* 1 (la única que existe) está bloqueada en un `chan send` en la línea 8, el primer `ch <- i`. Un canal **sin buffer** no almacena nada: el envío se completa solo cuando otra *goroutine* está recibiendo en ese mismo instante. Como nadie recibe todavía (el `range` viene después, en la misma *goroutine*), el primer envío espera para siempre, y el *runtime* detecta que no queda nadie que pueda despertarla.

Causa raíz: productor y consumidor en la **misma** *goroutine* con un canal síncrono. El número de elementos (3) no importa; con uno habría pasado lo mismo.

Dos arreglos correctos, según lo que quieras modelar:

**a) Productor en otra *goroutine*** (la forma general: el canal coordina a dos partes concurrentes):

```go
func main() {
    ch := make(chan int)
    go func() {
        defer close(ch)        // quien envía cierra; nunca el receptor
        for i := 0; i < 3; i++ {
            ch <- i
        }
    }()
    for v := range ch {        // termina cuando el canal se cierra y se vacía
        fmt.Println(v)
    }
}
```

**b) Canal con buffer suficiente** (solo si de verdad quieres encolar antes de consumir, por ejemplo para recoger resultados de N tareas conocidas):

```go
ch := make(chan int, 3)
for i := 0; i < 3; i++ {
    ch <- i            // no bloquea mientras haya sitio
}
close(ch)
for v := range ch {
    fmt.Println(v)
}
```

Con buffer 3 y 3 envíos funciona; con un cuarto envío volverías al mismo deadlock. Por eso b) es frágil si el número de elementos no está fijado por el código justo al lado.

Reglas que evitan este tipo de bloqueo:

1. **Un canal sin buffer es un punto de encuentro, no una cola.** Si no hay receptor concurrente, el envío bloquea.
2. **Cierra desde el lado que envía**, cuando sabes que no habrá más envíos. Enviar a un canal cerrado hace *panic* (`send on closed channel`); recibir de uno cerrado devuelve el valor cero inmediatamente, y `v, ok := <-ch` te dice `ok == false` para distinguirlo de un cero legítimo.
3. **`range` sobre un canal necesita que alguien lo cierre.** Si nadie cierra, el `range` espera para siempre: ese es el segundo deadlock clásico, y la traza diría `[chan receive]` en vez de `[chan send]`.
4. **El tamaño del buffer no es «para que no bloquee»**, es una decisión de diseño sobre cuánto desacoplas al productor del consumidor. Si no sabes qué valor poner, casi siempre la respuesta es 0 o «tantos como tareas voy a lanzar».

Verificación: la versión a) imprime `0 1 2` en orden, porque hay un único productor y un único consumidor y el canal conserva el orden de envío. Y `go vet` no detecta deadlocks (son dinámicos), pero `go run -race` tampoco se quejaría aquí porque no hay carrera: es un bloqueo puro. La herramienta que sí los ve es la traza que pegaste; aprende a leer el estado entre corchetes (`chan send`, `chan receive`, `select`, `semacquire` para un `WaitGroup` o `Mutex`) y la línea: te dice exactamente quién espera a quién.""",
            },
        ]
    },
    # 7) select: timeout, cancelación, default, time.After en bucle
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Necesito leer de un canal de eventos pero rendirme si en 2 segundos no llega nada, y también parar si el usuario cancela. Escribí esto y funciona, pero alguien me dijo que «fuga timers»:

```go
for {
    select {
    case ev := <-events:
        handle(ev)
    case <-time.After(2 * time.Second):
        return errors.New("timeout")
    case <-ctx.Done():
        return ctx.Err()
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""La estructura del `select` es correcta. Lo de los *timers* era cierto hasta Go 1.22 y dejó de serlo en Go 1.23, así que la respuesta depende del `go` de tu `go.mod`.

**Qué pasaba.** `time.After(d)` crea un *timer* en cada iteración del bucle. Cuando llega un evento, el `select` elige el `case` de `events` y el *timer* recién creado queda huérfano, pero el *runtime* lo mantenía vivo (con su canal y su *closure*) hasta que expiraba. Con eventos cada 10 ms y un timeout de 2 s, acumulabas ~200 *timers* vivos en todo momento; con timeouts de minutos y mucho tráfico, miles. No era una fuga infinita, pero sí memoria y trabajo del *runtime* desperdiciados.

**Qué cambió en 1.23.** Los *timers* a los que nadie hace referencia pasan a ser recolectables por el GC inmediatamente, aunque no hayan expirado ni se haya llamado a `Stop`. Con `go 1.23` o superior en `go.mod`, tu código es correcto tal cual.

**Si tienes que soportar `go 1.22` o anterior**, o si quieres el patrón que además expresa mejor la intención («2 s sin eventos» vs «2 s en total»), reutiliza un *timer*:

```go
func consume(ctx context.Context, events <-chan Event, idle time.Duration) error {
    timer := time.NewTimer(idle)
    defer timer.Stop()

    for {
        select {
        case ev, ok := <-events:
            if !ok {
                return nil // el productor cerró: fin normal
            }
            handle(ev)
            // Rearmar el timer: Stop + Reset. Desde 1.23 Reset vacía el canal del
            // timer si hacía falta; en versiones anteriores hay que drenarlo a mano.
            if !timer.Stop() {
                select {
                case <-timer.C:
                default:
                }
            }
            timer.Reset(idle)
        case <-timer.C:
            return fmt.Errorf("sin eventos durante %s", idle)
        case <-ctx.Done():
            return ctx.Err()
        }
    }
}
```

El `Stop`/drenado/`Reset` es feo pero es el protocolo documentado para versiones < 1.23; en 1.23+ basta con `timer.Reset(idle)` porque `Reset` garantiza que no quedará un valor viejo en `timer.C`.

Dos observaciones sobre tu versión original que sí son independientes de la versión:

1. **¿Timeout por evento o total?** Tu `time.After` dentro del bucle significa «2 s **desde el último evento**», porque se crea uno nuevo en cada iteración. Si lo que quieres es «2 s en total», crea el *timer* (o un `context.WithTimeout`) **fuera** del bucle:

```go
ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
defer cancel()
for {
    select {
    case ev := <-events:
        handle(ev)
    case <-ctx.Done():
        return ctx.Err() // context.DeadlineExceeded o context.Canceled
    }
}
```

Con esto, además, el timeout y la cancelación del usuario viajan por el mismo canal y el llamador puede distinguirlos con `errors.Is(err, context.DeadlineExceeded)`.

2. **Canal cerrado.** Si `events` se cierra, `<-events` devuelve el valor cero sin bloquear y tu bucle llamaría a `handle` con un evento vacío en un bucle infinito. Lee siempre con `ev, ok := <-events` cuando el canal lo pueda cerrar otro.

Prueba que distingue los dos timeouts, con un reloj real pero corto:

```go
func TestConsumeIdleTimeout(t *testing.T) {
    events := make(chan Event)
    go func() {
        for i := 0; i < 3; i++ {
            events <- Event{}
            time.Sleep(30 * time.Millisecond)
        }
    }()
    err := consume(context.Background(), events, 50*time.Millisecond)
    if err == nil || !strings.Contains(err.Error(), "sin eventos") {
        t.Fatalf("got %v", err)
    }
}
```

Tres eventos cada 30 ms con *idle* de 50 ms no dispara el timeout hasta que el productor para; con «2 s en total» mal implementado como «por evento», un test así es el que lo delata.""",
            },
        ]
    },
    # 8) context: propagación, cancelación, valores, errores habituales. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "I keep seeing `ctx context.Context` as the first argument everywhere in Go code. In my service I just store a context in the struct at startup and use it in every method. A reviewer flagged it. What's the actual rule, and when do I create a new one vs pass the one I got?",
            },
            {
                "role": "assistant",
                "content": r"""The rule: a `Context` describes **one request or one unit of work** (its deadline, its cancellation, its request-scoped values), so it flows **down the call stack as a parameter** and is never stored in a struct that outlives the request. Storing one in the service struct means every request shares the lifetime of whatever you created at startup: cancelling a single request becomes impossible, and a per-request deadline becomes a global one.

**Where contexts come from.** Entry points create them; everything below receives them:

```go
// HTTP: the server creates one per request, cancelled when the client disconnects
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    user, err := h.svc.Find(ctx, r.PathValue("id"))
    // ...
}

// CLI / main: the root, cancelled on SIGINT
func main() {
    ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer stop()
    if err := run(ctx); err != nil { /* ... */ }
}

// Tests
func TestFind(t *testing.T) {
    ctx := t.Context() // Go 1.24; before that: context.Background()
}
```

**When to derive a new one.** Only to *narrow* what you received: a tighter deadline, or a cancel you control for a sub-task.

```go
func (s *Service) Find(ctx context.Context, id string) (User, error) {
    ctx, cancel := context.WithTimeout(ctx, 500*time.Millisecond) // this DB call gets 500 ms
    defer cancel()                                                 // always; releases the timer
    return s.repo.Find(ctx, id)
}
```

The child inherits the parent's cancellation: if the HTTP client goes away, the DB query is cancelled too, because `database/sql` drivers check `ctx.Done()`. That chain is the whole point, and it is broken the moment one layer stores a context instead of passing it on.

**When NOT to derive one.** Never start from `context.Background()` in the middle of the stack "to be safe". That detaches your work from the request, so it keeps running after the caller is gone. The one legitimate exception is work that must outlive the request (an audit log write after the response is sent): use `context.WithoutCancel(ctx)` (Go 1.21+), which keeps the values but drops cancellation, so the intent is explicit.

**Values.** `context.WithValue` is for request-scoped metadata that crosses API boundaries and that no function should *require* to work: trace IDs, the authenticated principal, a request logger. Not for optional parameters, not for dependencies (pass the DB, don't hide it in the context). Use an unexported key type so other packages cannot collide:

```go
type ctxKey struct{}

func WithRequestID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, ctxKey{}, id)
}

func RequestID(ctx context.Context) (string, bool) {
    id, ok := ctx.Value(ctxKey{}).(string)
    return id, ok
}
```

**Checking cancellation in your own loops.** Libraries that do I/O already honour `ctx`. Your CPU-bound loop does not, unless you check:

```go
for i, item := range items {
    if err := ctx.Err(); err != nil {
        return i, err // context.Canceled or context.DeadlineExceeded
    }
    process(item)
}
```

Check once per iteration if iterations are cheap; `ctx.Err()` is an atomic load, so it is fine inside hot loops.

**Fixing your service.** Remove the field, add `ctx context.Context` as the first parameter of every method that does I/O or can block, and let the compiler point out every call site. The signature convention (first parameter, named `ctx`) is what `go vet` and linters like `contextcheck` rely on; `staticcheck` will also flag a context stored in a struct (`SA1012` is for passing `nil`, but the storage pattern shows up as every method ignoring its own `ctx`).

Quick check that cancellation propagates end to end:

```go
func TestFindStopsWhenCancelled(t *testing.T) {
    ctx, cancel := context.WithCancel(context.Background())
    cancel() // already cancelled
    _, err := svc.Find(ctx, "42")
    if !errors.Is(err, context.Canceled) {
        t.Fatalf("got %v, want context.Canceled", err)
    }
}
```

If this test passes with your struct-stored context, it is because the repo ignores `ctx`, which is the second thing to fix.""",
            },
        ]
    },
    # 9) sync: Mutex copiado por valor (go vet copylocks), RWMutex, embebido. Usuario trae código
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Mi cache concurrente a veces devuelve datos corruptos con `-race` aunque tengo un mutex. `go vet` me dice algo de `copylocks` pero no entiendo qué copio.

```go
type Cache struct {
    mu   sync.Mutex
    data map[string][]byte
}

func NewCache() Cache {
    return Cache{data: make(map[string][]byte)}
}

func (c Cache) Get(k string) ([]byte, bool) {
    c.mu.Lock()
    defer c.mu.Unlock()
    v, ok := c.data[k]
    return v, ok
}

func (c Cache) Set(k string, v []byte) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.data[k] = v
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Copias el mutex en **cada llamada**. Los métodos tienen receptor por valor (`func (c Cache)`), así que `c` es una copia del struct, incluido `c.mu`. Cada `Get` y cada `Set` bloquean **su propia copia** del mutex, que nadie más ve; el map, en cambio, es una referencia compartida por todas las copias. Resultado: cero exclusión mutua sobre `data`, que es la carrera que `-race` reporta.

`go vet` lo detecta estáticamente (`copylocks: Get passes lock by value: Cache contains sync.Mutex`), y es de los pocos avisos de `vet` que son siempre un bug.

Arreglo: receptor puntero en todos los métodos y constructor que devuelve `*Cache`.

```go
type Cache struct {
    mu   sync.RWMutex
    data map[string][]byte
}

func NewCache() *Cache {
    return &Cache{data: make(map[string][]byte)}
}

func (c *Cache) Get(k string) ([]byte, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    v, ok := c.data[k]
    return v, ok
}

func (c *Cache) Set(k string, v []byte) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.data[k] = v
}
```

Tres decisiones adicionales:

1. **`RWMutex`**: si hay muchas más lecturas que escrituras, `RLock` permite lecturas concurrentes. Si las operaciones son tan cortas como estas, la diferencia con `Mutex` es pequeña y `Mutex` es más simple; lo dejo en `RWMutex` porque es el caso típico de una caché. No uses `RWMutex` si dentro de una sección de lectura puedes necesitar escribir: pasar de `RLock` a `Lock` sin soltar es un *deadlock*.
2. **El mutex no se exporta ni se devuelve.** Nunca escribas un método `Lock()` en `Cache` que exponga `c.mu`; el bloqueo es un detalle interno.
3. **Los `[]byte` que devuelves siguen compartidos.** `Get` devuelve el mismo *slice* que guardó `Set`; si un llamador lo modifica, modifica la caché sin pasar por el mutex. Si eso es posible en tu programa, devuelve una copia (`bytes.Clone(v)`) o documenta que los valores son de solo lectura.

Sobre la regla de receptores: cuando un tipo tiene un método con receptor puntero, **todos** sus métodos deberían tenerlo, y el tipo debe usarse siempre por puntero. Un struct que contiene un `sync.Mutex`, `sync.WaitGroup` o `sync.Once` nunca debe copiarse después del primer uso; por eso `go vet` también avisa si lo pasas por valor a una función o lo guardas en un *slice* de valores.

Verificación:

```go
func TestCacheConcurrent(t *testing.T) {
    c := NewCache()
    var wg sync.WaitGroup
    for i := range 100 {
        wg.Add(1)
        go func() {
            defer wg.Done()
            k := fmt.Sprintf("k%d", i%10)
            c.Set(k, []byte(k))
            c.Get(k)
        }()
    }
    wg.Wait()
}
```

`go test -race ./...` con la versión original reporta la carrera en el acceso al map; con los receptores puntero, limpio. Y `go vet ./...` pasa de avisar a silencio, que es el criterio más rápido: en CI, `go vet` debería ser obligatorio precisamente por este tipo de aviso.""",
            },
        ]
    },
    # 10) range sobre enteros (1.22) e iteradores iter.Seq (1.23): escribir uno propio
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo funcionan los iteradores nuevos de Go 1.23? Tengo una estructura de páginas (una API paginada) y quiero que el usuario haga `for item := range client.All(ctx)` sin cargar todo en memoria. Hoy devuelvo un `[]Item` completo.",
            },
            {
                "role": "assistant",
                "content": r"""Un iterador en Go 1.23 es simplemente **una función que recibe un `yield`**: `func(yield func(T) bool)`. El `for range` la llama y le pasa el cuerpo del bucle como `yield`; si `yield` devuelve `false`, el usuario hizo `break` (o `return`) y debes parar. El paquete `iter` da los dos nombres estándar: `iter.Seq[V]` para un valor por iteración y `iter.Seq2[K, V]` para dos.

Para una API paginada, el iterador pide una página, entrega sus elementos uno a uno y pide la siguiente solo si el consumidor sigue ahí:

```go
package api

import (
    "context"
    "iter"
)

type Item struct {
    ID   string
    Name string
}

type page struct {
    Items []Item
    Next  string // cursor; vacío en la última página
}

// All recorre todos los elementos, pidiendo páginas bajo demanda.
// El error se entrega como segundo valor en la última iteración, si lo hay.
func (c *Client) All(ctx context.Context) iter.Seq2[Item, error] {
    return func(yield func(Item, error) bool) {
        cursor := ""
        for {
            p, err := c.fetchPage(ctx, cursor)
            if err != nil {
                yield(Item{}, err)
                return
            }
            for _, it := range p.Items {
                if !yield(it, nil) {
                    return // el consumidor hizo break: no pedimos más páginas
                }
            }
            if p.Next == "" {
                return
            }
            cursor = p.Next
        }
    }
}
```

Uso:

```go
for item, err := range client.All(ctx) {
    if err != nil {
        return fmt.Errorf("listing items: %w", err)
    }
    if item.Name == "stop" {
        break // se detiene sin descargar el resto de páginas
    }
    fmt.Println(item.ID)
}
```

Decisiones de diseño:

- **`Seq2[Item, error]` para los errores.** Un iterador no puede devolver `error` al terminar (la firma es fija), así que las dos opciones son esta o un método `Err()` que se consulta después del bucle, como hace `bufio.Scanner`. Entregar el error como segundo valor obliga al consumidor a mirarlo en cada vuelta y es la convención más extendida para iteradores que pueden fallar. Si prefieres `Seq[Item]` limpio, guarda el error en el cliente y expón `client.Err()`; es menos seguro porque es fácil olvidar la comprobación.
- **Respetar el `false` de `yield` es obligatorio.** Si tras un `false` vuelves a llamar a `yield`, el *runtime* hace *panic* («range function continued iteration after function for loop body returned false»). Por eso cada llamada está en un `if !yield(...) { return }`.
- **`ctx` se captura una vez** al crear el iterador; cada `fetchPage` lo respeta, así que cancelar el contexto corta el bucle con un error en la siguiente página.
- **La *closure* se ejecuta de nuevo en cada `range`.** `seq := client.All(ctx)` y dos bucles sobre `seq` hacen dos recorridos completos (dos series de peticiones). Si no quieres eso, materializa con `slices.Collect` una vez.

Lo que te da gratis la biblioteca estándar sobre un `Seq`:

```go
names := slices.Collect(func(yield func(string) bool) {
    for it, err := range client.All(ctx) {
        if err != nil || !yield(it.Name) {
            return
        }
    }
})
```

Y en 1.23 también `maps.Keys`, `maps.Values`, `slices.Values`, `slices.Sorted`, `slices.Chunk`, todos devolviendo o consumiendo `iter.Seq`. Además, `for i := range n` sobre un entero (desde 1.22) es el caso trivial del mismo mecanismo: la variable va de 0 a `n-1`.

Prueba con un cliente falso de tres páginas que verifica la pereza:

```go
func TestAllStopsFetchingOnBreak(t *testing.T) {
    fake := &fakeClient{pages: 3, perPage: 2} // cuenta las llamadas a fetchPage
    n := 0
    for _, err := range fake.All(context.Background()) {
        if err != nil {
            t.Fatal(err)
        }
        n++
        if n == 2 {
            break
        }
    }
    if fake.calls != 1 {
        t.Fatalf("fetched %d pages, want 1", fake.calls)
    }
}
```

Si `calls` es 3, el iterador no está respetando `yield == false` o está cargando todo por adelantado, que era exactamente lo que querías evitar.""",
            },
        ]
    },
    # 11) Generics: constraints, cmp.Ordered, ~T, cuándo no usarlos; multiturno sobre métodos genéricos
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Quiero una función `Max` genérica y me da este error:

```go
func Max[T any](a, b T) T {
    if a > b {
        return a
    }
    return b
}
```

```
./main.go:4:5: invalid operation: a > b (type parameter T is not comparable with >)
```

Y ya puestos: tengo un `type Celsius float64` y quiero que `Max` también funcione con él.""",
            },
            {
                "role": "assistant",
                "content": r"""`any` solo promete que `T` es un tipo; no promete que soporte `>`. Las operaciones permitidas sobre un parámetro de tipo son la intersección de lo que permiten **todos** los tipos de su *constraint*, y para `>` necesitas una *constraint* que lo restrinja a números y cadenas. La biblioteca estándar ya la tiene: `cmp.Ordered` (Go 1.21).

```go
import "cmp"

func Max[T cmp.Ordered](a, b T) T {
    if a > b {
        return a
    }
    return b
}
```

Y para `Celsius` no tienes que hacer nada: `cmp.Ordered` está definido con **tildes** (`~int | ~int8 | ... | ~float64 | ~string`), y `~float64` significa «cualquier tipo cuyo tipo subyacente sea `float64`», que incluye `Celsius`. Sin la tilde, `float64` a secas solo aceptaría `float64` exacto; esa es la diferencia que la tilde resuelve.

```go
type Celsius float64

fmt.Println(Max(Celsius(21.5), Celsius(19)))  // 21.5, y el resultado es Celsius
fmt.Println(Max("pera", "manzana"))           // pera
```

Si escribieras tu propia *constraint* para, por ejemplo, solo enteros:

```go
type Integer interface {
    ~int | ~int8 | ~int16 | ~int32 | ~int64 |
        ~uint | ~uint8 | ~uint16 | ~uint32 | ~uint64 | ~uintptr
}

func Sum[T Integer](xs []T) T {
    var total T
    for _, x := range xs {
        total += x
    }
    return total
}
```

Dos avisos antes de que lo generalices todo:

1. **`max` y `min` ya son funciones predeclaradas desde Go 1.21** y aceptan cualquier tipo ordenado: `max(a, b, c)`. Tu `Max` es un buen ejercicio, pero en código real usa las del lenguaje. Lo mismo con `slices.Max`, `slices.Sort`, `slices.Index`, `slices.Contains`, `maps.Keys`: la mayoría de las funciones genéricas «de utilidad» ya existen y están optimizadas.
2. **`cmp.Ordered` y los `NaN`.** `Max(math.NaN(), 1.0)` devuelve `1.0` porque `NaN > 1` es falso, pero `Max(1.0, math.NaN())` devuelve `NaN`. Las predeclaradas `max`/`min` propagan `NaN` siempre, que es más coherente. Si tus datos pueden tener `NaN`, otra razón para usar las del lenguaje.

Cuándo generics y cuándo no:

- **Sí**: contenedores y algoritmos que no dependen del tipo (`Stack[T]`, `Filter`, `Map`, caché genérica con `comparable` como clave).
- **No**: cuando una interfaz pequeña ya lo resuelve. `func Print(s fmt.Stringer)` es mejor que `func Print[T fmt.Stringer](s T)`; el genérico no aporta nada y complica la firma.
- **No** para «evitar escribir dos funciones» si los cuerpos son distintos: eso es un `switch` de tipos disfrazado.

Comprobación de que `~` hace lo que digo:

```go
type Celsius float64
type Strict interface{ float64 }      // sin tilde
type Loose interface{ ~float64 }      // con tilde

func a[T Strict](x T) T { return x }
func b[T Loose](x T) T  { return x }

var c Celsius = 1
_ = b(c)   // compila
_ = a(c)   // error: Celsius does not satisfy Strict (possibly missing ~ for float64 in Strict)
```

El propio compilador sugiere la tilde en el mensaje, que es la forma más rápida de recordar la regla.""",
            },
            {"role": "user", "content": "Ahora quiero un método genérico en mi struct `Repo`, algo como `func (r *Repo) Find[T any](id string) T`, y no me deja."},
            {
                "role": "assistant",
                "content": r"""No existe en Go: los **métodos no pueden tener parámetros de tipo propios**. El error es «methods cannot have type parameters» (o «syntax error: method must have no type parameters» según la versión). Es una limitación de diseño deliberada: un método con tipos propios haría imposible saber qué conjunto de métodos tiene un tipo al comprobar si satisface una interfaz.

Tienes tres salidas, según qué varía:

**1. El tipo genérico está en el struct, no en el método.** Si cada repositorio maneja una entidad, parametriza `Repo`:

```go
type Repo[T any] struct {
    db    *sql.DB
    table string
    scan  func(*sql.Rows) (T, error)
}

func (r *Repo[T]) Find(ctx context.Context, id string) (T, error) {
    var zero T
    rows, err := r.db.QueryContext(ctx, "SELECT * FROM "+r.table+" WHERE id = $1", id)
    if err != nil {
        return zero, err
    }
    defer rows.Close()
    if !rows.Next() {
        return zero, ErrNotFound
    }
    return r.scan(rows)
}

users := &Repo[User]{db: db, table: "users", scan: scanUser}
u, err := users.Find(ctx, "42") // u es User, sin aserción
```

`var zero T` es la forma idiomática de devolver «el valor cero de T» en un error.

**2. Función genérica de paquete que recibe el receptor.** Si el struct no debe ser genérico (un solo `Repo` para todo), el tipo variable va en una función:

```go
func Find[T any](ctx context.Context, r *Repo, id string, scan func(*sql.Rows) (T, error)) (T, error) {
    // mismo cuerpo, usando r.db
}

u, err := Find(ctx, repo, "42", scanUser) // T se infiere de scanUser
```

Se lee peor que un método, pero es exactamente lo que hace la biblioteca estándar con `slices.SortFunc(s, cmp)` en vez de `s.Sort(cmp)`.

**3. No lo hagas genérico.** Si cada tipo tiene su propia consulta, su propio `scan` y su propia tabla, un método por entidad (`FindUser`, `FindOrder`) es más corto, más claro y no necesita que nadie entienda la *constraint*. La generalidad solo compensa cuando el cuerpo es idéntico salvo por el tipo.

Un detalle de la opción 1 que suele sorprender: `Repo[User]` y `Repo[Order]` son **tipos distintos** sin relación entre sí; no puedes meterlos en el mismo `[]*Repo` ni definir una interfaz que los abarque salvo por los métodos que no mencionen `T`. Si necesitas tratarlos uniformemente, extrae esa interfaz (`type Closer interface{ Close() error }`) con los métodos comunes.""",
            },
        ]
    },
    # 12) go.mod, versiones, replace, go work, v2. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "Two questions about Go modules. (1) I have a library `github.com/acme/kit` and an app that uses it; while developing both I want the app to use my local checkout, not the published version. (2) I need to make a breaking change to `kit`: how do I release it without breaking existing users?",
            },
            {
                "role": "assistant",
                "content": r"""**(1) Local development: use a workspace, not `replace`.**

`go work` (Go 1.18+) tells the toolchain to resolve a set of modules from local directories without touching any `go.mod`:

```sh
cd ~/code            # contains ./app and ./kit
go work init ./app ./kit
```

That creates `~/code/go.work`:

```
go 1.23.0

use (
    ./app
    ./kit
)
```

While `go.work` is present (it is found by walking up from the current directory), `app` builds against `~/code/kit` regardless of the version in `app/go.mod`. Nothing to undo before committing, because `go.work` is a local file: add it to `.gitignore`, or keep it only on your machine. CI, which has no `go.work`, builds against the published version, which is exactly what you want to test there.

Set `GOWORK=off` to temporarily ignore the workspace (`GOWORK=off go test ./...`) when you need to check that the app works with the released `kit`.

The older alternative, a `replace` directive in `app/go.mod`:

```
replace github.com/acme/kit => ../kit
```

works, but it lives in a committed file, it is easy to push by accident, and it is ignored when someone *depends on* `app` as a module. Use `replace` only for a permanent fork (`=> github.com/you/kit-fork v1.4.1`) that you genuinely want in version control.

**(2) Breaking change: bump the major version and change the import path.**

Go's rule is that a different major version is a different module. For `v2` and above, the module path must end in `/v2`:

1. In `kit/go.mod`:

```
module github.com/acme/kit/v2
```

2. Update every internal import in `kit` from `github.com/acme/kit/...` to `github.com/acme/kit/v2/...` with a plain find-and-replace across the repo (`gofmt -r` rewrites expressions, not import paths).

3. Tag the release as `v2.0.0`. Same repository, same branch is fine: the tag plus the `/v2` suffix is what distinguishes it.

Consumers upgrade explicitly:

```sh
go get github.com/acme/kit/v2@v2.0.0
```

and change their imports to `github.com/acme/kit/v2`. Existing users keep resolving `github.com/acme/kit` to the latest `v1.x.y` forever; `go get -u` never crosses a major boundary. Both versions can even coexist in one binary (useful during a migration), because they are different packages.

What counts as breaking, so you know when this is required: removing or renaming an exported identifier, changing a function signature, adding a method to an exported **interface** (every implementer breaks), changing a struct's exported fields in a way that breaks composite literals. Adding a new function or a new method to a concrete type is not breaking. Run `gorelease` (`golang.org/x/exp/cmd/gorelease`) before tagging: it diffs the API against the previous release and tells you whether your tag should be a patch, minor or major.

Two related conventions worth getting right now:

- **Before `v1.0.0`** (any `v0.x.y`), nothing is promised and you can break in a minor release; that is why many libraries stay on `v0` longer than they should. If `kit` is already used by other teams, tag `v1.0.0` and commit to the rules above.
- **`go.mod`'s `go` line** states the minimum language version your module requires, and since Go 1.21 the toolchain honours it strictly (it will download a newer toolchain if needed, via the `toolchain` line). Bumping it (say to `go 1.23.0` to use iterators) is not a breaking change in the semver sense, but it does force consumers to build with at least that version, so mention it in the release notes.

Verification for the v2 switch: in a scratch directory, `go mod init example.com/try && go get github.com/acme/kit/v2@v2.0.0 && go list -m all | grep acme/kit` should print only the `/v2` module, and `go build ./...` on `app` with `GOWORK=off` should still compile against v1 until you migrate it deliberately.""",
            },
        ]
    },
    # 13) Testing: revisión de tests, table-driven, t.Run, t.Parallel, benchmarks. System revisor
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala lo que falta y da la versión corregida completa."},
            {
                "role": "user",
                "content": r"""Revisa mis tests de `ParseDuration(s string) (time.Duration, error)`, que acepta cosas como "90s", "2m", "1h30m" y rechaza vacío o negativo:

```go
func TestParseDuration(t *testing.T) {
    d, _ := ParseDuration("90s")
    if d != 90*time.Second {
        t.Error("bad")
    }
    d, _ = ParseDuration("2m")
    if d != 2*time.Minute {
        t.Error("bad")
    }
    _, err := ParseDuration("")
    if err == nil {
        t.Error("expected error")
    }
}

func BenchmarkParseDuration(b *testing.B) {
    ParseDuration("1h30m")
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cinco problemas; el último hace que el *benchmark* no mida nada.

1. **Ignoras el error en los casos positivos.** Si `ParseDuration("90s")` devuelve `(0, err)`, el test falla con «bad» en vez de con el error, y si devuelve `(90s, err)` por un bug, pasa.
2. **Los mensajes no dicen qué pasó.** «bad» obliga a abrir el código. Un fallo debe mostrar entrada, obtenido y esperado.
3. **No hay subtests.** Cuando falle el segundo caso, no sabrás cuál es sin leer línea a línea, y no puedes ejecutar uno solo con `-run`.
4. **Faltan casos**: `1h30m` (el formato compuesto que mencionas), negativo, unidad inválida, número sin unidad, espacios. Son justo los que rompen un parser.
5. **El *benchmark* ejecuta la función una vez** y no usa `b.N`, así que el *framework* reporta un tiempo sin sentido.

Versión corregida, *table-driven* con subtests:

```go
func TestParseDuration(t *testing.T) {
    t.Parallel()
    tests := []struct {
        name    string
        in      string
        want    time.Duration
        wantErr bool
    }{
        {name: "segundos", in: "90s", want: 90 * time.Second},
        {name: "minutos", in: "2m", want: 2 * time.Minute},
        {name: "compuesto", in: "1h30m", want: 90 * time.Minute},
        {name: "vacio", in: "", wantErr: true},
        {name: "negativo", in: "-5s", wantErr: true},
        {name: "sin unidad", in: "15", wantErr: true},
        {name: "unidad invalida", in: "3x", wantErr: true},
        {name: "espacios", in: " 2m ", wantErr: true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got, err := ParseDuration(tt.in)
            if tt.wantErr {
                if err == nil {
                    t.Fatalf("ParseDuration(%q) = %v, want error", tt.in, got)
                }
                return
            }
            if err != nil {
                t.Fatalf("ParseDuration(%q) unexpected error: %v", tt.in, err)
            }
            if got != tt.want {
                t.Errorf("ParseDuration(%q) = %v, want %v", tt.in, got, tt.want)
            }
        })
    }
}

func BenchmarkParseDuration(b *testing.B) {
    b.ReportAllocs()
    for i := 0; i < b.N; i++ {
        if _, err := ParseDuration("1h30m"); err != nil {
            b.Fatal(err)
        }
    }
}
```

Notas sobre la versión nueva:

- **`t.Fatalf` cuando no tiene sentido seguir** (hubo error inesperado), `t.Errorf` cuando sí (el valor es incorrecto pero quieres ver todos los fallos de la tabla). `Fatal` dentro de un subtest solo aborta ese subtest.
- **`t.Parallel()` en ambos niveles** ejecuta los casos concurrentemente. Desde Go 1.22 no hace falta `tt := tt` antes de la *closure*: la variable del bucle es por iteración. Si tu `go.mod` dice `go 1.21` o menos, añade esa línea o todos los subtests verán el último caso.
- **El caso «espacios» es una decisión**, no una verdad: si quieres aceptar `" 2m "`, cambia `wantErr` por `want: 2 * time.Minute` y el test documenta esa decisión. Lo importante es que esté decidido y fijado.
- **`%q` en los mensajes** muestra las comillas, así que una cadena vacía o con espacios se ve en el fallo.
- **`b.ReportAllocs()`** añade asignaciones por operación al resultado, que para un *parser* es la métrica que más suele importar. En Go 1.24+ puedes escribir el bucle como `for b.Loop() { ... }`, que además impide que el compilador elimine la llamada por no usar el resultado; con `b.N`, el `if err != nil` cumple esa función.

Comandos para comprobar que todo lo anterior funciona como digo:

```sh
go test -run 'TestParseDuration/compuesto' -v ./...      # un solo caso
go test -race -count=3 ./...                             # tres pasadas con detector de carreras
go test -run '^$' -bench 'ParseDuration' -benchmem ./... # solo el benchmark
```

Si el *benchmark* reporta más de una o dos asignaciones por operación para una cadena tan corta, el *parser* está haciendo `strings.Split` o similares donde bastaría un recorrido por bytes; pero eso ya es optimización, no corrección.""",
            },
        ]
    },
    # 14) net/http con ServeMux de Go 1.22: patrones con método, PathValue, middlewares, timeouts
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Sigue haciendo falta gorilla/mux o chi para un servicio HTTP pequeño en Go 1.23? Necesito rutas con parámetros (`/users/{id}`), distinguir GET de POST, un middleware de logging y otro de autenticación.",
            },
            {
                "role": "assistant",
                "content": r"""Para eso, no: el `http.ServeMux` de la biblioteca estándar soporta método y parámetros de ruta desde Go 1.22, y los *middlewares* son funciones que envuelven `http.Handler`, que ya era así. Un *router* externo compensa si quieres grupos de rutas con *middlewares* distintos declarados de forma compacta, o expresiones regulares en los patrones; ninguna de las dos es tu caso.

```go
package main

import (
    "context"
    "encoding/json"
    "log/slog"
    "net/http"
    "os"
    "strings"
    "time"
)

func main() {
    mux := http.NewServeMux()
    mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusNoContent)
    })
    mux.HandleFunc("GET /users/{id}", getUser)
    mux.HandleFunc("POST /users", createUser)
    mux.HandleFunc("GET /files/{path...}", getFile) // comodín que captura el resto de la ruta

    handler := logging(auth(mux))

    srv := &http.Server{
        Addr:              ":8080",
        Handler:           handler,
        ReadHeaderTimeout: 5 * time.Second,
        ReadTimeout:       10 * time.Second,
        WriteTimeout:      30 * time.Second,
        IdleTimeout:       120 * time.Second,
    }
    slog.Info("listening", "addr", srv.Addr)
    if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
        slog.Error("server", "err", err)
        os.Exit(1)
    }
}

func getUser(w http.ResponseWriter, r *http.Request) {
    id := r.PathValue("id")
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"id": id})
}

func createUser(w http.ResponseWriter, r *http.Request) {
    var in struct{ Name string `json:"name"` }
    if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&in); err != nil {
        http.Error(w, "invalid body", http.StatusBadRequest)
        return
    }
    w.WriteHeader(http.StatusCreated)
}

func getFile(w http.ResponseWriter, r *http.Request) {
    http.ServeFileFS(w, r, os.DirFS("./static"), r.PathValue("path"))
}
```

Qué te da el `ServeMux` nuevo:

- **Método en el patrón**: `"GET /users/{id}"`. Una petición `DELETE /users/1` recibe un `405 Method Not Allowed` automático, con la cabecera `Allow` correcta. Un patrón sin método acepta todos.
- **`r.PathValue("id")`** lee el segmento capturado. `{path...}` al final captura el resto incluyendo barras; `{$}` fuerza coincidencia exacta (`"GET /{$}"` es solo la raíz, mientras `"GET /"` es «todo lo que no coincida con otra cosa»).
- **Precedencia por especificidad**: `/users/{id}` y `/users/me` pueden coexistir; gana el más específico. Si dos patrones se solapan sin que uno sea más específico, `HandleFunc` hace *panic* al registrarlos, lo que es preferible a una ambigüedad silenciosa.

Los *middlewares*. Un *middleware* es `func(http.Handler) http.Handler`; se componen de fuera hacia dentro, así que `logging(auth(mux))` registra también las peticiones rechazadas por `auth`:

```go
type ctxKey struct{}

func auth(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path == "/health" {
            next.ServeHTTP(w, r)
            return
        }
        token, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
        if !ok || !validToken(token) {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }
        ctx := context.WithValue(r.Context(), ctxKey{}, token)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

type statusRecorder struct {
    http.ResponseWriter
    status int
}

func (s *statusRecorder) WriteHeader(code int) {
    s.status = code
    s.ResponseWriter.WriteHeader(code)
}

func logging(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
        next.ServeHTTP(rec, r)
        slog.Info("request", "method", r.Method, "path", r.URL.Path,
            "status", rec.status, "dur", time.Since(start))
    })
}
```

El `statusRecorder` hace falta porque `http.ResponseWriter` no expone el código enviado. Si en algún *handler* usas `http.Flusher` o `Hijacker`, el envoltorio los oculta; para eso existe `http.NewResponseController(w)` (Go 1.20+), que los recupera a través del envoltorio si implementas `Unwrap() http.ResponseWriter`.

Los **timeouts del servidor** no son opcionales en producción: sin `ReadHeaderTimeout`, un cliente que abre la conexión y no envía nada la ocupa indefinidamente. `WriteTimeout` cuenta desde que termina de leerse la cabecera, así que para *streaming* largo ajústalo o usa `ResponseController.SetWriteDeadline` por petición.

Prueba de las rutas sin levantar un puerto:

```go
func TestRoutes(t *testing.T) {
    mux := http.NewServeMux()
    mux.HandleFunc("GET /users/{id}", getUser)

    rec := httptest.NewRecorder()
    mux.ServeHTTP(rec, httptest.NewRequest("GET", "/users/42", nil))
    if rec.Code != 200 || !strings.Contains(rec.Body.String(), `"42"`) {
        t.Fatalf("got %d %s", rec.Code, rec.Body.String())
    }

    rec = httptest.NewRecorder()
    mux.ServeHTTP(rec, httptest.NewRequest("DELETE", "/users/42", nil))
    if rec.Code != http.StatusMethodNotAllowed {
        t.Fatalf("got %d, want 405", rec.Code)
    }
}
```""",
            },
        ]
    },
    # 15) JSON: error de unmarshal pegado, tags, omitempty, números como float64, campos desconocidos
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Al parsear la respuesta de un proveedor de pagos me sale:

```
json: cannot unmarshal string into Go struct field Order.amount of type float64
```

El JSON es `{"id": "o_1", "amount": "1999", "currency": "EUR", "created_at": 1710000000, "meta": {"a": 1}}` y mi struct:

```go
type Order struct {
    ID        string  `json:"id"`
    Amount    float64 `json:"amount"`
    Currency  string  `json:"currency"`
    CreatedAt time.Time `json:"created_at"`
    Meta      map[string]any `json:"meta"`
}
```

¿Por qué me mandan el importe como string, y qué hago con `created_at`, que también fallará?""",
            },
            {
                "role": "assistant",
                "content": r"""Te mandan el importe como cadena **a propósito**: es la práctica habitual en APIs de pagos para que ningún cliente lo convierta a coma flotante y pierda céntimos. Y tienes razón con `created_at`: `time.Time` espera una cadena RFC 3339, no un entero de segundos, así que es el siguiente error que verías.

Tres cambios:

**1. `amount` como entero de céntimos, leído desde cadena.** La etiqueta `,string` le dice a `encoding/json` que el valor viene entrecomillado:

```go
Amount int64 `json:"amount,string"` // 1999 = 19,99 EUR
```

`,string` funciona con tipos numéricos y booleanos. No uses `float64` para dinero aunque lo pudieras parsear: `19.99` no es representable exactamente y las sumas acumulan error.

**2. `created_at` como *epoch*: un tipo propio con `UnmarshalJSON`.** `encoding/json` llama a ese método si el tipo lo implementa:

```go
type UnixTime struct{ time.Time }

func (u *UnixTime) UnmarshalJSON(b []byte) error {
    var secs int64
    if err := json.Unmarshal(b, &secs); err != nil {
        return fmt.Errorf("unix time: %w", err)
    }
    u.Time = time.Unix(secs, 0).UTC()
    return nil
}

func (u UnixTime) MarshalJSON() ([]byte, error) {
    return json.Marshal(u.Unix())
}
```

El receptor de `UnmarshalJSON` tiene que ser puntero (modifica el valor); el de `MarshalJSON`, valor, para que funcione tanto con `UnixTime` como con `*UnixTime`. Al embeber `time.Time` conservas todos sus métodos (`u.Format`, `u.Before`).

**3. `meta` con `map[string]any` convierte todo número a `float64`.** `{"a": 1}` te llega como `map[string]any{"a": float64(1)}`; para ids grandes (más de 2^53) pierdes precisión. Si solo necesitas guardarlo y reenviarlo, `json.RawMessage` lo mantiene como bytes sin tocar:

```go
Meta json.RawMessage `json:"meta,omitempty"`
```

Si necesitas leer los números, usa un `json.Decoder` con `UseNumber()`, que los deja como `json.Number` (una cadena con métodos `Int64()` y `Float64()`).

Struct final:

```go
type Order struct {
    ID        string          `json:"id"`
    Amount    int64           `json:"amount,string"`
    Currency  string          `json:"currency"`
    CreatedAt UnixTime        `json:"created_at"`
    Meta      json.RawMessage `json:"meta,omitempty"`
}
```

Dos reglas de `encoding/json` que te van a ahorrar el siguiente error:

- **Solo los campos exportados** (mayúscula inicial) se (de)serializan; un campo `amount` en minúscula se ignora en silencio.
- **Los campos desconocidos del JSON se ignoran** por defecto. Si quieres que un campo nuevo del proveedor te avise en vez de pasar inadvertido, `dec.DisallowUnknownFields()` sobre un `json.Decoder`. Con `omitempty`, un campo con valor cero no se emite al serializar (y desde Go 1.24 existe `omitzero`, que además respeta un método `IsZero()`, útil para `time.Time`).

Para leer el error que pegaste en el futuro: «cannot unmarshal **string** into Go struct field **Order.amount** of type **float64**» te da el tipo JSON que llegó, el campo exacto (ruta `Struct.campo`) y el tipo Go que esperabas; con eso casi siempre sabes el arreglo sin mirar el JSON.

Test con la respuesta real:

```go
func TestOrderUnmarshal(t *testing.T) {
    raw := `{"id":"o_1","amount":"1999","currency":"EUR","created_at":1710000000,"meta":{"a":1}}`
    var o Order
    if err := json.Unmarshal([]byte(raw), &o); err != nil {
        t.Fatal(err)
    }
    if o.Amount != 1999 || o.CreatedAt.Year() != 2024 || string(o.Meta) != `{"a":1}` {
        t.Fatalf("got %+v", o)
    }
}
```

`1710000000` es el 9 de marzo de 2024, así que `Year() == 2024` confirma que el *epoch* se interpretó en segundos y no en milisegundos.""",
            },
        ]
    },
    # 16) defer/panic/recover: orden, evaluación de argumentos, Close ignorado; multiturno con recover
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tres dudas de `defer` que me surgieron leyendo código ajeno:

```go
func a() {
    for i := 0; i < 3; i++ {
        defer fmt.Println(i)
    }
}

func b() (err error) {
    f, err := os.Create("out.txt")
    if err != nil {
        return err
    }
    defer f.Close()
    _, err = f.Write(data)
    return err
}

func c() {
    x := 1
    defer fmt.Println("x =", x)
    x = 2
}
```

¿Qué imprime `a`, por qué `b` «pierde errores» según el linter, y qué imprime `c`?""",
            },
            {
                "role": "assistant",
                "content": r"""**`a` imprime `2 1 0`.** Los `defer` se apilan y se ejecutan en orden inverso (LIFO) al salir de la función. Son tres `defer` distintos, cada uno con su `i` ya evaluado (ver `c`).

**`c` imprime `x = 1`.** Los **argumentos** del `defer` se evalúan en el momento del `defer`, no al ejecutarse; solo la llamada se pospone. Si quieres ver el valor final, difiere una *closure* que lea la variable:

```go
defer func() { fmt.Println("x =", x) }() // x = 2
```

**`b` pierde el error de `Close`.** Para un archivo que se **escribe**, `Close` puede fallar (el sistema de archivos vacía buffers al cerrar; en NFS o con disco lleno el error aparece ahí y no en `Write`). `defer f.Close()` descarta ese valor, y `errcheck` lo marca. El patrón correcto usa el valor de retorno con nombre, que un `defer` sí puede modificar:

```go
func b() (err error) {
    f, err := os.Create("out.txt")
    if err != nil {
        return err
    }
    defer func() {
        if cerr := f.Close(); cerr != nil && err == nil {
            err = cerr
        }
    }()
    _, err = f.Write(data)
    return err
}
```

`err == nil` en la condición evita pisar un error de `Write`, que es el más informativo, con el de `Close`. Si prefieres conservar los dos, `err = errors.Join(err, cerr)`.

Para archivos de **solo lectura**, ignorar el error de `Close` es aceptable y habitual: no hay nada que vaciar. Lo mismo con `resp.Body.Close()` en HTTP.

Dos reglas más de `defer` que verás en cuanto sigas leyendo código:

1. **`defer` dentro de un bucle no se ejecuta al final de la iteración**, sino al final de la función. Si abres mil archivos en un bucle con `defer f.Close()`, tienes mil descriptores abiertos hasta que la función termine. Extrae el cuerpo a una función para que cada iteración cierre lo suyo.
2. **El coste de `defer` es despreciable desde Go 1.14** (se compila como una llamada directa en los casos normales). No lo evites por rendimiento; evítalo solo en bucles por la razón anterior.

Comprobación de `c`, que es la que más sorprende, con los dos sabores lado a lado:

```go
func main() {
    x := 1
    defer fmt.Println("argumento:", x)      // 1
    defer func() { fmt.Println("closure:", x) }() // 2
    x = 2
}
// salida (orden inverso):
// closure: 2
// argumento: 1
```""",
            },
            {"role": "user", "content": "Y `recover`, ¿cuándo se usa? En nuestro servidor HTTP alguien puso un `recover` en cada handler y me parece que esconde errores."},
            {
                "role": "assistant",
                "content": r"""Tu instinto es correcto a medias. Un `recover` en los *handlers* HTTP es legítimo **si** convierte el *panic* en un 500 registrado con su traza, y es dañino si lo convierte en silencio. La diferencia está en qué hace con lo que recupera.

Cuándo tiene sentido `recover`:

1. **Frontera de un servidor que atiende muchas peticiones.** Un *panic* en una *goroutine* sin `recover` mata **todo el proceso**, no solo esa petición. `net/http` ya recupera *panics* en los *handlers* por ti (los registra y cierra la conexión), así que el `recover` manual solo aporta si quieres responder un 500 bien formado y registrar con tu *logger*. Y tiene que ser **un** *middleware*, no uno por *handler*:

```go
func recoverer(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if p := recover(); p != nil {
                if p == http.ErrAbortHandler {
                    panic(p) // el runtime lo usa para abortar a propósito; no lo tragues
                }
                slog.ErrorContext(r.Context(), "panic", "value", p, "stack", string(debug.Stack()))
                http.Error(w, "internal error", http.StatusInternalServerError)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

2. **Convertir un *panic* de una biblioteca en `error`** en una API que prometiste que no hace *panic* (un parser que usa `panic` internamente para abortar, como hace `encoding/json` con sus propios errores).

3. **Goroutines que lanzas tú.** El `recover` de `net/http` no cubre `go func()` dentro de un *handler*: un *panic* ahí tumba el proceso. Si lanzas *goroutines* de trabajo, envuélvelas con un `recover` que registre y, normalmente, termine el programa de forma ordenada (`os.Exit(2)` tras el log), porque un estado interno a medias es peor que un reinicio.

Cuándo **no**:

- **Para errores esperados.** Un archivo que no existe, un JSON inválido, un id que no está: eso es `error`, no `panic`. Si el código hace `panic` en esos casos y luego `recover` para «manejarlo», es un `try/catch` disfrazado y hay que arreglar el origen.
- **Sin registrar la traza.** `recover()` devuelve el valor del *panic*, no la pila; si no capturas `debug.Stack()` dentro del `defer`, pierdes el único dato que te dice dónde ocurrió. El `recover` «que esconde errores» casi siempre es este.
- **Para seguir como si nada.** Tras un *panic* el estado de la petición es desconocido; responder un 500 es lo único honesto.

Dos detalles mecánicos que explican la mitad de los `recover` que no funcionan:

- `recover()` solo tiene efecto **dentro de una función diferida**, llamada directamente desde el `defer`. Un `recover()` en el cuerpo de la función, o en una función que la diferida llama, devuelve `nil` siempre.
- Un *panic* dentro de una `goroutine` solo puede recuperarse en **esa misma** *goroutine*. No existe un «recover global».

Qué hacer con los `recover` de tu servidor: sustituirlos por el *middleware* de arriba, y revisar cada *panic* que aparezca en los logs como un bug a corregir, no como un evento normal. Si un *handler* dispara el `recoverer` con frecuencia, el problema está en ese *handler*; el *middleware* solo evita que se lleve el proceso por delante mientras lo arreglas.""",
            },
        ]
    },
    # 17) Race detector: informe pegado, lectura e interpretación, arreglo con atomic. System variante
    {
        "messages": [
            {"role": "system", "content": "Responde con el diagnóstico primero, en frases cortas, y termina con cómo verificarlo."},
            {
                "role": "user",
                "content": r"""`go test -race` me saca esto y no sé ni por dónde empezar a leerlo:

```
==================
WARNING: DATA RACE
Read at 0x00c0000a4010 by goroutine 8:
  app/metrics.(*Counter).Value()
      /src/app/metrics/counter.go:21 +0x3a
  app/metrics.TestCounterConcurrent.func2()
      /src/app/metrics/counter_test.go:30 +0x58

Previous write at 0x00c0000a4010 by goroutine 7:
  app/metrics.(*Counter).Inc()
      /src/app/metrics/counter.go:16 +0x44
  app/metrics.TestCounterConcurrent.func1()
      /src/app/metrics/counter_test.go:24 +0x3c

Goroutine 8 (running) created at:
  app/metrics.TestCounterConcurrent()
      /src/app/metrics/counter_test.go:28 +0x1b0
==================
```

```go
type Counter struct {
    n int64
}

func (c *Counter) Inc() {
    c.n++
}

func (c *Counter) Value() int64 {
    return c.n
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Diagnóstico: `Counter.n` se escribe en `Inc` (línea 16) y se lee en `Value` (línea 21) desde dos *goroutines* distintas sin ninguna sincronización. Es una carrera de datos real, no un falso positivo: el detector nunca da falsos positivos; solo reporta accesos que observó sin relación *happens-before*.

Cómo se lee el informe, bloque a bloque:

1. **`Read at 0x... by goroutine 8`**: la operación que disparó el aviso, con su pila. La primera línea de la pila es el sitio exacto (`counter.go:21`, el `return c.n`); las siguientes, quién la llamó (`func2` del test, línea 30).
2. **`Previous write at 0x... by goroutine 7`**: el acceso anterior a la **misma dirección** que entra en conflicto, con su pila (`counter.go:16`, el `c.n++`).
3. **`Goroutine 8 (running) created at`**: dónde se lanzó la *goroutine* del primer bloque (el `go func()` de la línea 28 del test). Sirve para saber qué parte del programa creó la concurrencia.

La dirección es la misma en ambos bloques: ese es el dato que confirma que es el mismo campo. Dos accesos a direcciones distintas nunca son carrera.

Arreglo. Para un contador, `sync/atomic` es más simple y más rápido que un mutex, y el tipo `atomic.Int64` (Go 1.19+) hace imposible olvidar la operación atómica en un acceso:

```go
import "sync/atomic"

type Counter struct {
    n atomic.Int64
}

func (c *Counter) Inc() {
    c.n.Add(1)
}

func (c *Counter) Value() int64 {
    return c.n.Load()
}
```

Por qué `atomic.Int64` y no `atomic.AddInt64(&c.n, 1)` sobre un `int64`: con la función suelta, un `return c.n` en otro método vuelve a ser una carrera y nadie lo nota hasta el siguiente `-race`; con el tipo, `c.n` no se puede leer sin `Load()`. Además garantiza la alineación de 64 bits que las funciones sueltas exigían en 32 bits.

Si el contador tuviera varios campos que deben cambiar juntos (contar y guardar el máximo, por ejemplo), un `atomic` por campo no basta, porque la combinación no es atómica; ahí toca `sync.Mutex`.

Dos cosas que la gente intenta y no arreglan nada:

- **«Es solo una lectura, no pasa nada».** Sí pasa: el modelo de memoria de Go no define el resultado de una lectura concurrente con una escritura. En la práctica un `int64` en x86-64 suele leerse entero, pero el compilador puede reordenar o cachear en registro la lectura y `Value()` devolver un valor viejo para siempre. Es comportamiento indefinido, no «un poco inexacto».
- **Un `time.Sleep` en el test** para que la escritura «termine antes». Oculta la carrera al detector en esa ejecución y la deja en producción.

Verificación:

```sh
go test -race -count=5 -run TestCounterConcurrent ./metrics/
```

`-count=5` repite el test para dar más oportunidades de entrelazado; con la versión de `atomic.Int64` no debe aparecer ningún `WARNING: DATA RACE`. Y un *benchmark* rápido (`go test -bench Inc -cpu 1,8`) te mostrará que el `Add` atómico cuesta unos pocos nanosegundos, frente a los ~20 ns de un `Mutex` sin contención; para un contador, es la elección correcta en los dos ejes.""",
            },
        ]
    },
    # 18) pprof: CPU y memoria, cómo capturar y leer; multiturno con heap
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi servicio en Go va lento bajo carga (p99 de 800 ms cuando debería ser 50) y no sé dónde se va el tiempo. ¿Cómo lo perfilo en producción sin reiniciarlo ni instalar nada raro?",
            },
            {
                "role": "assistant",
                "content": r"""Con `net/http/pprof`, que viene en la biblioteca estándar y expone perfiles por HTTP. Si el servicio ya lo tiene registrado, no hace falta reiniciar; si no, es un cambio de dos líneas para el próximo despliegue.

**1. Exponerlo** (en un puerto interno, nunca en el público: los perfiles revelan código y consumen CPU al capturarse):

```go
import (
    "net/http"
    _ "net/http/pprof" // registra /debug/pprof/* en http.DefaultServeMux
)

func main() {
    go func() {
        // solo accesible desde la máquina o la red interna
        http.ListenAndServe("127.0.0.1:6060", nil)
    }()
    // ... el servidor real en otro mux y otro puerto
}
```

Si tu servidor principal usa `http.DefaultServeMux`, los *endpoints* ya están expuestos ahí; muévelos a un mux interno antes de que lo descubra un escáner.

**2. Capturar un perfil de CPU de 30 s mientras hay carga**, desde tu máquina a través de un túnel o `kubectl port-forward`:

```sh
go tool pprof -http=:8080 http://127.0.0.1:6060/debug/pprof/profile?seconds=30
```

Abre una interfaz web con el *flame graph*. Lee de arriba abajo: cada bloque es una función; su anchura, la fracción del tiempo de CPU muestreado. Busca bloques anchos **tuyos** (de tu módulo) o de dependencias que no esperabas; `runtime.mallocgc` ancho significa «asigno demasiado», `syscall` ancho significa I/O, y mucho `runtime.gcBgMarkWorker` significa que el GC trabaja de más (también asignaciones).

**3. Si el p99 es alto pero la CPU está tranquila**, el tiempo no se va en calcular sino en **esperar**: *locks*, canales, base de datos, red. Para eso sirven los otros perfiles:

```sh
# Goroutines bloqueadas y en qué: dónde esperan 200 goroutines a la vez
curl 'http://127.0.0.1:6060/debug/pprof/goroutine?debug=2' | less

# Contención de mutex (hay que activarlo en el proceso):
#   runtime.SetMutexProfileFraction(1) en main
go tool pprof -http=:8080 http://127.0.0.1:6060/debug/pprof/mutex

# Tiempo bloqueado en canales y locks:
#   runtime.SetBlockProfileRate(1) en main (coste alto; actívalo solo mientras depuras)
go tool pprof -http=:8080 http://127.0.0.1:6060/debug/pprof/block
```

El volcado de *goroutines* con `debug=2` es el más barato y a menudo el más revelador: si ves cientos de *goroutines* en `database/sql.(*DB).conn` tienes un pool de conexiones agotado; si están en `net/http.(*persistConn).roundTrip`, esperan a un servicio externo.

**4. Sin interfaz web**, en una máquina sin navegador:

```sh
go tool pprof -top -nodecount=30 http://127.0.0.1:6060/debug/pprof/profile?seconds=30
go tool pprof -list 'myapp/handlers.Search' cpu.pprof   # líneas de una función con su coste
```

`-top` ordena por `flat` (tiempo en la propia función) y muestra `cum` (incluyendo lo que llama). Para encontrar al culpable mira `cum` en tus funciones; para saber qué optimizar dentro de ella, `flat` y `-list`.

Qué esperar con un p99 de 800 ms y p50 bueno: casi nunca es CPU, porque la CPU afectaría a todos los percentiles. Mi orden de sospecha sería: pool de conexiones o un *lock* global (perfil de *goroutines* y de *mutex*), pausas de GC por asignaciones grandes (perfil de *heap*, lo vemos si hace falta) y, en tercer lugar, una ruta de código lenta solo para ciertas entradas (perfil de CPU filtrado por *handler*).

Comprobación de que el perfil es representativo: captura dos de 30 s separados unos minutos y compáralos con `go tool pprof -diff_base primero.pprof segundo.pprof`; si el bloque ancho aparece en los dos, es estructural y no una casualidad del muestreo.""",
            },
            {"role": "user", "content": "El perfil de goroutines no muestra nada raro, pero el proceso usa 3 GB de RAM y crece. ¿Es el heap profile?"},
            {
                "role": "assistant",
                "content": r"""Sí, y para «crece sin parar» la pregunta no es cuánto se asigna sino **qué sigue vivo**. El perfil de *heap* tiene dos vistas y hay que mirar la correcta:

```sh
go tool pprof -http=:8080 -sample_index=inuse_space http://127.0.0.1:6060/debug/pprof/heap
```

- `inuse_space`: bytes vivos en la última recolección. Es la vista para una fuga: te dice qué tipo de objeto ocupa los 3 GB y qué pila los creó.
- `alloc_space`: bytes asignados en total desde el arranque, incluyendo los ya liberados. Es la vista para «el GC trabaja demasiado», no para fugas.

El *flame graph* en `inuse_space` muestra la pila de **asignación**, no quién retiene el objeto. Con ella sabrás qué se creó (por ejemplo, `bytes.makeSlice` desde `io.ReadAll` en tu *handler* de subida); el porqué sigue vivo lo deduces del código.

Para confirmar que es fuga y no un pico, compara dos capturas separadas por tiempo:

```sh
curl -o heap1.pprof http://127.0.0.1:6060/debug/pprof/heap
sleep 600
curl -o heap2.pprof http://127.0.0.1:6060/debug/pprof/heap
go tool pprof -http=:8080 -sample_index=inuse_space -diff_base heap1.pprof heap2.pprof
```

Lo que aparece en positivo en el *diff* es lo que creció en esos diez minutos.

Causas que explican el 90 % de las fugas en servicios Go, y cómo se ven en el perfil:

1. **Un map o slice global que solo crece** (caché sin expulsión, «registro» de peticiones, deduplicación de ids). Pila de asignación en `runtime.mapassign` o `growslice` desde tu código. Arreglo: tamaño máximo o TTL; para una caché, una librería con expulsión LRU.
2. **Goroutines que nunca terminan**, cada una con su pila y lo que referencian. Esto sí lo delata el perfil de *goroutines*: si el número crece con el tiempo (`curl .../goroutine?debug=1 | head -1` te da el total), busca la pila repetida. Dijiste que no muestra nada raro; comprueba el **número**, no solo las pilas.
3. **Subslices de buffers grandes** retenidos: guardas `line := buf[i:j]` de un buffer de 1 MB y conservas el megabyte entero. Pila en el `make` del buffer. Arreglo: `bytes.Clone` / `strings.Clone` de lo que guardas.
4. **`time.Ticker` o `context.WithCancel` sin `Stop`/`cancel`** en un bucle: cada uno retiene su *timer* y su *closure*.
5. **Cuerpos HTTP sin cerrar** (`resp.Body`): retienen la conexión y sus buffers; además agotan el pool de conexiones.

Si el perfil dice que lo vivo es pequeño (digamos 300 MB) pero el proceso ocupa 3 GB, no es una fuga de Go: es memoria que el *runtime* obtuvo del sistema y aún no ha devuelto, o fragmentación. Míralo en `/debug/pprof/heap?debug=1`, al final: `HeapInuse` frente a `HeapSys` y `HeapReleased`. Desde Go 1.19 puedes acotar el total con `GOMEMLIMIT=2500MiB`, que hace que el GC trabaje más agresivo al acercarse al límite en vez de dejar que el contenedor lo mate por OOM.

Para verificar el arreglo, deja un *gauge* de `runtime/metrics` (`/memory/classes/heap/objects:bytes`) o simplemente `runtime.ReadMemStats` cada minuto en los logs: una fuga arreglada se ve como una línea plana tras el calentamiento; una no arreglada, como una rampa.""",
            },
        ]
    },
    # 19) Interfaz nil que no es nil: *MyErr devuelto como error. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""No entiendo este comportamiento. `validate` devuelve `nil` cuando todo va bien, y aun así entra en el `if err != nil`:

```go
type ValidationError struct{ Field string }

func (e *ValidationError) Error() string { return "invalid " + e.Field }

func validate(name string) *ValidationError {
    if name == "" {
        return &ValidationError{Field: "name"}
    }
    return nil
}

func main() {
    var err error = validate("ana")
    if err != nil {
        fmt.Println("error:", err) // imprime "error: " y luego panic
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Es el error de interfaz más clásico de Go: **una interfaz solo es `nil` si su tipo y su valor son ambos `nil`**. `validate` devuelve un `*ValidationError` con valor `nil`; al asignarlo a `error`, la interfaz guarda el par (tipo = `*ValidationError`, valor = `nil`). El tipo no es `nil`, así que `err != nil` es verdadero. Después, `fmt.Println` llama a `err.Error()` sobre un puntero nulo y `e.Field` hace *panic*.

Lo puedes ver directamente:

```go
var err error = validate("ana")
fmt.Printf("%T %v\n", err, err == nil) // *main.ValidationError false
```

La regla práctica que lo evita: **las funciones que devuelven errores devuelven el tipo `error`, nunca un tipo concreto de puntero.**

```go
func validate(name string) error {
    if name == "" {
        return &ValidationError{Field: "name"}
    }
    return nil // nil de tipo error: tipo nil, valor nil
}
```

Ahora `return nil` produce una interfaz vacía de verdad y la comparación funciona. Quien necesite el tipo concreto lo recupera con `errors.As`:

```go
var ve *ValidationError
if errors.As(err, &ve) {
    fmt.Println("campo:", ve.Field)
}
```

Por qué Go está diseñado así en vez de tratar «puntero nil dentro de interfaz» como `nil`: una interfaz con tipo y valor `nil` sigue siendo útil, porque los métodos con receptor puntero se pueden llamar sobre un puntero `nil` (`func (e *T) String() string { if e == nil { return "<nil>" } ... }` es un patrón real). Aplanar los dos casos rompería eso.

Dónde se cuela el mismo bug sin que haya un `return nil` a la vista:

1. **Variables intermedias con tipo concreto**:

```go
var ve *ValidationError  // nil
if cond {
    ve = &ValidationError{Field: "x"}
}
return ve // ¡si cond es falso, devuelve una interfaz no nil!
```

Arreglo: declara `var err error` o devuelve explícitamente `nil` en la rama buena.

2. **`io.Writer` u otras interfaces** con un puntero nulo dentro, pasado a una función que comprueba `w != nil` y luego escribe. Mismo mecanismo, otro nombre.

`go vet` no detecta esto en general (es semántica, no sintaxis), pero `staticcheck` sí marca el caso 1 cuando puede probarlo (`SA4023: this comparison is never true`), y `nilness` de `golang.org/x/tools` cubre algunos más. La defensa más fiable es la regla de la firma: `error` en el tipo de retorno, siempre.

Test que fija el comportamiento:

```go
func TestValidateReturnsRealNil(t *testing.T) {
    if err := validate("ana"); err != nil {
        t.Fatalf("got %#v, want nil", err)
    }
    err := validate("")
    var ve *ValidationError
    if !errors.As(err, &ve) || ve.Field != "name" {
        t.Fatalf("got %v", err)
    }
}
```

Con la firma original, el primer `Fatalf` imprime `(*main.ValidationError)(nil)`, que es la forma visual de «interfaz con tipo pero sin valor»; con la firma corregida, pasa.""",
            },
        ]
    },
    # 20) Strings, bytes y runas: len, indexado, iteración, Builder. Principiante; multiturno con normalización
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Estoy haciendo un ejercicio que invierte una cadena y con acentos sale basura:

```go
func reverse(s string) string {
    out := ""
    for i := len(s) - 1; i >= 0; i-- {
        out += string(s[i])
    }
    return out
}

fmt.Println(reverse("año")) // o�±a   (más o menos)
```

¿Los strings de Go no son Unicode?""",
            },
            {
                "role": "assistant",
                "content": r"""Son Unicode, pero codificados en **UTF-8**, y `s[i]` te da el **byte** `i`, no el carácter `i`. «ñ» ocupa dos bytes (`0xC3 0xB1`); al invertirlos byte a byte los separas y cada uno por sí solo es inválido, de ahí el `�`.

Los tres hechos que hay que tener claros:

| Operación | Qué devuelve | Para `"año"` |
|---|---|---|
| `len(s)` | bytes | 4 |
| `s[i]` | un `byte` (`uint8`) | `s[1]` es `0xC3` |
| `for i, r := range s` | índice de byte y `rune` (punto de código) | `(0,'a') (1,'ñ') (3,'o')` |
| `utf8.RuneCountInString(s)` | caracteres | 3 |
| `[]rune(s)` | slice de puntos de código | `['a' 'ñ' 'o']` |

Para invertir por caracteres, convierte a `[]rune`, invierte y vuelve a `string`:

```go
func reverse(s string) string {
    r := []rune(s)
    for i, j := 0, len(r)-1; i < j; i, j = i+1, j-1 {
        r[i], r[j] = r[j], r[i]
    }
    return string(r)
}
```

`[]rune(s)` asigna un slice de 4 bytes por carácter; para el ejercicio es lo correcto y lo claro.

Sobre el `out += string(s[i])` original hay un segundo problema, independiente del Unicode: cada `+=` crea una cadena nueva y copia la anterior, así que construir una cadena larga así es cuadrático. Cuando acumules texto en un bucle, usa `strings.Builder`:

```go
var b strings.Builder
b.Grow(len(s))          // opcional: reserva de una vez
for _, r := range s {
    b.WriteRune(r)
}
return b.String()       // sin copia final
```

Y `string(s[i])` con un `byte` hace algo distinto de lo que parece: convierte el **número** a la runa con ese valor (`string(byte(0xC3))` es «Ã», dos bytes en UTF-8), no «el byte tal cual». `go vet` avisa de la variante con `int` (`string(int)`) precisamente porque casi nunca es lo que se quiere.

Comprobación:

```go
func TestReverse(t *testing.T) {
    cases := map[string]string{"": "", "a": "a", "año": "oña", "héllo wörld": "dlröw olléh"}
    for in, want := range cases {
        if got := reverse(in); got != want {
            t.Errorf("reverse(%q) = %q, want %q", in, got, want)
        }
    }
}
```""",
            },
            {"role": "user", "content": "Probé con \"niño\" escrito en un teclado de Mac y me dice que tiene 5 runas, no 4. ¿Qué pasa?"},
            {
                "role": "assistant",
                "content": r"""Que la «ñ» puede escribirse de dos formas en Unicode y tu Mac usó la larga:

- **Precompuesta** (NFC): `U+00F1` LATIN SMALL LETTER N WITH TILDE, una runa.
- **Descompuesta** (NFD): `n` + `U+0303` COMBINING TILDE, dos runas que se dibujan como una.

Ambas se ven igual y `"niño" == "niño"` es **falso** si una está en NFC y otra en NFD. Algunas aplicaciones de macOS (y el sistema de archivos HFS+ antiguo) producen NFD; casi todo lo demás produce NFC. Tu `[]rune` cuenta 5 porque hay 5 puntos de código, y tu `reverse` además separa la tilde de la «n» y la pega a la «o».

La unidad que un humano llama «carácter» es el **grupo de grafemas** (una base más sus marcas combinantes, o un emoji con modificadores), y la biblioteca estándar no lo expone. Dos herramientas:

1. **Normaliza a NFC en la entrada** con `golang.org/x/text/unicode/norm`, y compara y cuenta sobre eso. Resuelve el caso «ñ» y la mayoría de acentos del español:

```go
import "golang.org/x/text/unicode/norm"

s := norm.NFC.String(input)
fmt.Println(utf8.RuneCountInString(s)) // 4
```

2. **Si necesitas grafemas de verdad** (emoji con tono de piel, banderas, hangul descompuesto), usa `github.com/rivo/uniseg`, que implementa la segmentación oficial de Unicode:

```go
import "github.com/rivo/uniseg"

fmt.Println(uniseg.GraphemeClusterCount("niño 👨‍👩‍👧")) // 6
```

Y `reverse` por grafemas:

```go
func reverseGraphemes(s string) string {
    g := uniseg.NewGraphemes(s)
    var parts []string
    for g.Next() {
        parts = append(parts, g.Str())
    }
    slices.Reverse(parts)
    return strings.Join(parts, "")
}
```

Regla práctica para un servicio: normaliza a NFC **al recibir** texto de usuarios (formularios, nombres de archivo subidos desde Mac) y guarda siempre NFC; así las comparaciones, las búsquedas y los índices únicos de la base de datos se comportan. Si solo cuentas longitud para validar («máximo 50 caracteres»), cuenta runas tras normalizar; si dibujas o recortas texto para mostrar, cuenta grafemas.

Comprobación del diagnóstico sin instalar nada:

```go
for i, r := range "niño" {        // pega aquí la cadena que escribiste en el Mac
    fmt.Printf("%d: %U\n", i, r)
}
```

Si ves `U+006E` seguido de `U+0303`, es NFD; si ves `U+00F1`, NFC.""",
            },
        ]
    },
    # 21) Estructura de proyecto, internal/, nombres de paquete, linters. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "Starting a new Go service (HTTP API + a CLI for migrations). Every repo I look at has a different layout: `pkg/`, `internal/`, `cmd/`, `src/`, a `utils` package... What's the sane default for a team of four, and which linters should run in CI from day one?",
            },
            {
                "role": "assistant",
                "content": r"""Sane default: **flat at the top, `cmd/` for binaries, `internal/` for everything that is not a public library**, packages named after what they provide, and no `utils`.

```
myservice/
├── go.mod                      # module github.com/acme/myservice
├── cmd/
│   ├── api/main.go             # wires config, deps, http server; ~100 lines
│   └── migrate/main.go
├── internal/
│   ├── order/                  # domain: types, rules, the Store interface
│   │   ├── order.go
│   │   ├── service.go
│   │   └── service_test.go
│   ├── postgres/               # adapter: implements order.Store
│   ├── httpapi/                # handlers, routing, middleware
│   └── config/
├── migrations/                 # SQL files, embedded via go:embed in cmd/migrate
└── Makefile
```

Why each decision:

- **`internal/` is enforced by the compiler**: no module outside `github.com/acme/myservice` can import anything under it. That means you can refactor freely without worrying about external users, which is the normal state for a service. Create `pkg/` only when you intentionally publish a library for others; for a service, it is noise that invites `pkg/utils`.
- **`cmd/<name>/main.go` per binary**. `main` packages stay tiny: parse config, build dependencies, call `run(ctx)`. All logic lives in importable packages so tests can reach it.
- **No `src/`**: Go has no concept of a source root; the module root is the root.
- **Package names are the vocabulary**: `order.Service`, `postgres.Repo`, `httpapi.Router`. A package called `utils`, `common` or `helpers` is a sign that something has no owner; put the function next to the type it serves, or name the package after what the functions do (`retry`, `clock`, `money`).
- **Package by domain, not by layer** (`order/`, not `models/` + `services/` + `repositories/`). Layer packages produce import cycles the moment a service needs two models, and every feature touches four directories.
- **Tests next to the code**, `_test.go` in the same package (white box) or `package order_test` (black box, same directory) when you want to test only the exported API.

CI from day one, in this order (cheapest first):

```sh
gofmt -l . | tee /dev/stderr | test -z "$(cat)"   # formatting, non-negotiable
go vet ./...                                       # copylocks, printf, unreachable, loopclosure...
go test -race -count=1 ./...
govulncheck ./...                                  # known CVEs in your dependency graph
golangci-lint run                                  # the rest
```

For `golangci-lint`, start with a short, explicit list rather than "enable everything", so nobody learns to ignore it:

```yaml
# .golangci.yml (v2 format)
version: "2"
linters:
  default: none
  enable:
    - errcheck      # ignored error returns
    - staticcheck   # bugs and deprecated APIs (includes gosimple, stylecheck in v2)
    - govet
    - unused
    - errorlint     # == on wrapped errors, %v instead of %w
    - bodyclose     # resp.Body not closed
    - noctx         # http.NewRequest without context
    - gocritic
    - revive
```

Add `exhaustive` once you have enum-like switches, and `gosec` if you handle untrusted input (it is noisy; triage its findings once, then keep it). `goimports` replaces `gofmt` if you want imports grouped automatically.

Two conventions worth settling in week one, because they are expensive to change later:

1. **Errors**: sentinel errors and error types live in the domain package (`order.ErrNotFound`); adapters translate driver errors into them. Handlers switch on domain errors only.
2. **Configuration**: one `config.Load()` that reads env vars (and nothing else in production), returns a struct, and fails fast with a message naming the missing variable. No package reads `os.Getenv` on its own.

Verification that the layout holds: `go list -deps ./internal/order | grep -E 'database/sql|net/http'` should print nothing (the domain does not know about transports or drivers), and `go build ./...` from a fresh clone with no Makefile should succeed, because the build has no steps outside the toolchain.""",
            },
        ]
    },
    # 22) time: Duration, monotónico, zonas horarias, Ticker; multiturno con Parse. System variante
    {
        "messages": [
            {"role": "system", "content": "Explica como a alguien que viene de JavaScript, con comparaciones cortas entre ambos lenguajes."},
            {
                "role": "user",
                "content": r"""Tres cosas de `time` que me confunden viniendo de JS:

1. `time.Sleep(5)` no duerme 5 segundos, casi ni se nota.
2. `time.Since(start)` me da valores distintos de `end.Sub(start)` aunque `end := time.Now()` justo al terminar... o eso creo.
3. Quiero «las 9:00 de mañana en Bogotá» y no sé si usar `time.Now().Add(24*time.Hour)`.""",
            },
            {
                "role": "assistant",
                "content": r"""**1. `Duration` es un entero de nanosegundos, no de milisegundos.** En JS `setTimeout(fn, 5)` son milisegundos; en Go, `time.Sleep(5)` son 5 **nanosegundos**. La unidad va siempre explícita:

```go
time.Sleep(5 * time.Second)
time.Sleep(250 * time.Millisecond)
```

Y cuando la cantidad es una variable, multiplica un `Duration` por un `Duration`, no por un `int`:

```go
n := 5
time.Sleep(time.Duration(n) * time.Second) // correcto
// time.Sleep(n * time.Second)              // no compila: int * Duration
```

El tipo es tu amigo: `d.Seconds()` devuelve `float64`, `d.Milliseconds()` un `int64`, y `d.String()` imprime `1.5s`, `250ms`. En JS un número es un número y la unidad vive en tu cabeza.

**2. `time.Since(start)` y `end.Sub(start)` dan lo mismo** si `end` lo tomaste con `time.Now()` en el mismo proceso; lo que varía es simplemente que `time.Since` llama a `time.Now()` internamente unos nanosegundos más tarde que tu `end`. La diferencia real con JS está en el **reloj monotónico**: `time.Now()` en Go guarda dos lecturas, la de pared (la que ves al imprimir) y una monotónica que no retrocede aunque el sistema ajuste la hora (NTP, cambio manual, horario de verano). `Sub`, `Since` y `Until` usan la monotónica cuando ambos `Time` la tienen, así que medir una duración es fiable; en JS tienes que acordarte de usar `performance.now()` en vez de `Date.now()` para lo mismo.

Cuándo se pierde la lectura monotónica: al serializar (JSON, base de datos), al hacer `t.Round(0)`, `t.In(loc)`, `t.Truncate`, o al construir con `time.Date`. Un `Sub` entre un `Time` leído de la base de datos y `time.Now()` usa el reloj de pared, y puede dar negativo si el reloj saltó. Para medir, usa siempre dos `time.Now()` del mismo proceso.

**3. «Las 9:00 de mañana en Bogotá» no es `Now + 24h`.** Sumar 24 h es correcto en Colombia hoy (no hay horario de verano), pero es un cálculo de instante, no de calendario: en una zona con cambio de hora, «mañana a las 9» puede estar a 23 o 25 h. Y `time.Now()` lleva la zona del servidor (UTC en un contenedor), no la del usuario. Hazlo con fecha civil en la zona correcta:

```go
loc, err := time.LoadLocation("America/Bogota") // zona IANA; necesita tzdata
if err != nil {
    return err
}
now := time.Now().In(loc)
tomorrow9 := time.Date(now.Year(), now.Month(), now.Day()+1, 9, 0, 0, 0, loc)
```

`time.Date` normaliza: el día 32 de enero es el 1 de febrero, así que `now.Day()+1` funciona también a fin de mes y de año. Es el equivalente de `new Date(y, m, d + 1, 9)` en JS, con la diferencia de que aquí **eliges la zona** en vez de heredar la del navegador.

Sobre `tzdata`: en una imagen `scratch` o `distroless` no hay base de datos de zonas y `LoadLocation` falla. Importa `_ "time/tzdata"` en `main` (incrusta la base en el binario, ~450 KB) o instala el paquete `tzdata` en la imagen.

Un cuarto punto que va a aparecer en cuanto uses un `time.Ticker`: hay que pararlo (`defer ticker.Stop()`), igual que un `setInterval` necesita `clearInterval`; y `for range ticker.C` es la forma de consumirlo.

Comprobación del punto 3 con una zona que sí cambia de hora, para ver por qué `+24h` falla:

```go
loc, _ := time.LoadLocation("Europe/Madrid")
sat := time.Date(2025, time.March, 29, 9, 0, 0, 0, loc) // víspera del cambio
fmt.Println(sat.Add(24 * time.Hour))                     // 2025-03-30 10:00:00 +0200
fmt.Println(time.Date(2025, time.March, 30, 9, 0, 0, 0, loc)) // 2025-03-30 09:00:00 +0200
```""",
            },
            {"role": "user", "content": "¿Y para parsear fechas? En JS hago `new Date(\"2025-03-30\")` y listo. En Go `time.Parse` me pide un formato con unos números raros."},
            {
                "role": "assistant",
                "content": r"""Los «números raros» son la fecha de referencia de Go: **`Mon Jan 2 15:04:05 MST 2006`**, que en orden numérico es 1 2 3 4 5 6 7 (mes 1, día 2, hora 3 de la tarde = 15, minuto 4, segundo 5, año 6, zona -7). El formato se escribe mostrando cómo se vería **esa** fecha concreta:

```go
t, err := time.Parse("2006-01-02", "2025-03-30")
t, err := time.Parse("02/01/2006 15:04", "30/03/2025 09:30")
t, err := time.Parse(time.RFC3339, "2025-03-30T09:30:00-05:00")
```

Hay constantes para los formatos habituales: `time.RFC3339`, `time.DateOnly` (`"2006-01-02"`), `time.DateTime` (`"2006-01-02 15:04:05"`), `time.Kitchen` (`"3:04PM"`). Para el `"2025-03-30"` de tu ejemplo, `time.Parse(time.DateOnly, s)`.

Dos diferencias con `new Date(...)` que importan:

1. **`time.Parse` no adivina.** `new Date("30/03/2025")` en JS devuelve `Invalid Date` o una fecha americana según el motor; Go exige el formato y devuelve un `error` concreto si no cuadra: `parsing time "30/03/2025" as "2006-01-02": cannot parse "30/03/2025" as "2006"`. Es más trabajo y muchos menos bugs.
2. **Sin zona en la cadena, el resultado es UTC**, no la hora local como en JS. Si la fecha representa algo civil en una zona («el 30 de marzo» para un usuario de Bogotá), usa `time.ParseInLocation`:

```go
loc, _ := time.LoadLocation("America/Bogota")
t, err := time.ParseInLocation(time.DateOnly, "2025-03-30", loc) // 00:00 en Bogotá
```

Para formatear es la misma referencia al revés: `t.Format("02 Jan 2006")` da `30 Mar 2025`. Los nombres de mes y día salen en inglés; para español, `strings.Replace` o una tabla propia, porque `time` no tiene localización.

Y con JSON: `time.Time` se serializa y parsea como RFC 3339 automáticamente; si la API usa otro formato (solo fecha, *epoch* en segundos), define un tipo con `MarshalJSON`/`UnmarshalJSON`.

Comprobación de que entendiste la referencia: `time.Now().Format("2006")` imprime el año actual; `time.Now().Format("2025")` imprime literalmente `2025` porque no es ningún código. Ese es el error más común la primera semana.""",
            },
        ]
    },
    # 23) Worker pool con errgroup: límite de concurrencia, cancelación, resultados en orden. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo que procesar 10 000 URLs (descargar y parsear) con como mucho 20 a la vez, parar todo si alguna falla con un error no recuperable, y devolver los resultados en el mismo orden que las URLs. Mi versión con canales y WaitGroup tiene 80 líneas y no estoy seguro de que no fugue goroutines. ¿Cómo lo harías?",
            },
            {
                "role": "assistant",
                "content": r"""Con `errgroup` de `golang.org/x/sync`: te da el límite de concurrencia, la cancelación al primer error y la espera, y el orden lo resuelves escribiendo cada resultado en su índice de un slice preasignado. Son unas 30 líneas y ninguna *goroutine* puede quedar colgada.

```go
package fetch

import (
    "context"
    "fmt"
    "io"
    "net/http"

    "golang.org/x/sync/errgroup"
)

type Result struct {
    URL   string
    Title string
}

func All(ctx context.Context, client *http.Client, urls []string, limit int) ([]Result, error) {
    results := make([]Result, len(urls)) // cada goroutine escribe solo en su índice
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(limit)

    for i, u := range urls {
        g.Go(func() error {
            r, err := fetchOne(ctx, client, u)
            if err != nil {
                return fmt.Errorf("%s: %w", u, err)
            }
            results[i] = r
            return nil
        })
    }
    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}

func fetchOne(ctx context.Context, client *http.Client, u string) (Result, error) {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
    if err != nil {
        return Result{}, err
    }
    resp, err := client.Do(req)
    if err != nil {
        return Result{}, err
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK {
        return Result{}, fmt.Errorf("status %d", resp.StatusCode)
    }
    body, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
    if err != nil {
        return Result{}, err
    }
    return Result{URL: u, Title: extractTitle(body)}, nil
}
```

Qué hace cada pieza y por qué no fuga:

- **`errgroup.WithContext`** devuelve un `ctx` que se cancela cuando la primera `g.Go` devuelve error (o cuando `Wait` termina). Las descargas en curso reciben la cancelación a través de `client.Do`, que respeta el contexto de la petición, y terminan con `context.Canceled`. Nadie espera en un canal que nadie lee.
- **`g.SetLimit(20)`** hace que `g.Go` **bloquee** cuando hay 20 activas, así que el bucle de lanzamiento avanza al ritmo de los trabajadores; no creas 10 000 *goroutines* de golpe ni necesitas un semáforo a mano.
- **`g.Wait()`** espera a todas, incluso tras un error: las que ya habían empezado terminan (rápido, por la cancelación) y solo entonces vuelve. Devuelve el **primer** error; los demás se descartan, que es lo que quieres cuando el primero ya invalida el lote.
- **`results[i]`** por índice: escribir en posiciones distintas de un slice desde varias *goroutines* es seguro sin mutex. Con Go 1.22+ cada iteración tiene su propia `i` y `u`, así que la *closure* captura los valores correctos; con `go 1.21` o menos en `go.mod`, añade `i, u := i, u` al principio del bucle.
- **`io.LimitReader`** evita que una URL maliciosa de 10 GB te coma la memoria. Y `resp.Body.Close()` siempre, aunque no leas todo: sin él la conexión no vuelve al pool.

«Parar todo si alguna falla con un error **no recuperable**» pide distinguir errores. Si un 404 o un timeout de una URL no deben abortar el lote, trátalos dentro de la *goroutine* y devuelve `nil` con el resultado marcado:

```go
r, err := fetchOne(ctx, client, u)
switch {
case errors.Is(err, context.Canceled):
    return err                       // nos cancelaron: salir
case err != nil && !isFatal(err):
    results[i] = Result{URL: u, Err: err} // añade un campo Err a Result
    return nil
case err != nil:
    return fmt.Errorf("%s: %w", u, err)
}
```

Dos cosas que no hace esta versión y puede que necesites: **reintentos** con *backoff* (envuelve `fetchOne`, respetando `ctx`) y **límite por host** (20 en total pero 2 por dominio); para lo segundo, un `map[string]chan struct{}` de semáforos por host dentro de `fetchOne`, o simplemente ordena las URLs intercalando hosts.

Comprobación con un servidor de prueba que falla en una URL concreta y cuenta las peticiones:

```go
func TestAllStopsOnFatalError(t *testing.T) {
    var calls atomic.Int32
    srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        calls.Add(1)
        if r.URL.Path == "/boom" {
            w.WriteHeader(500)
            return
        }
        time.Sleep(20 * time.Millisecond)
        fmt.Fprint(w, "<title>ok</title>")
    }))
    defer srv.Close()

    urls := make([]string, 200)
    for i := range urls {
        urls[i] = srv.URL + "/ok"
    }
    urls[5] = srv.URL + "/boom"

    _, err := All(context.Background(), srv.Client(), urls, 20)
    if err == nil || !strings.Contains(err.Error(), "status 500") {
        t.Fatalf("got %v", err)
    }
    if n := calls.Load(); n > 60 {
        t.Fatalf("made %d requests after a fatal error; cancellation is not propagating", n)
    }
}
```

Si `calls` se acerca a 200, el contexto no está llegando a las peticiones (normalmente porque alguien usó `http.NewRequest` sin `WithContext`). Y `go test -race` sobre este test cubre la escritura concurrente en `results`.""",
            },
        ]
    },
    # 24) io.Reader/bufio: "token too long" pegado, leer archivos grandes línea a línea, Scanner vs Reader
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Leo un log de 8 GB línea a línea con `bufio.Scanner` y a mitad del archivo para con:

```
bufio.Scanner: token too long
```

```go
f, _ := os.Open(path)
defer f.Close()
sc := bufio.NewScanner(f)
for sc.Scan() {
    process(sc.Text())
}
if err := sc.Err(); err != nil {
    log.Fatal(err)
}
```

¿Es un bug de Go? El archivo tiene alguna línea muy larga (JSON de una traza), pero no sé cuánto.""",
            },
            {
                "role": "assistant",
                "content": r"""No es un bug: `bufio.Scanner` tiene un **tamaño máximo de token de 64 KiB** por defecto (`bufio.MaxScanTokenSize`), y una línea de tu log lo supera. El `Scanner` está diseñado para entradas «razonables» y prefiere fallar con un error claro antes que asignar sin límite por una línea gigante. El error te llega por `sc.Err()`, que es exactamente donde lo capturas, así que el programa se comportó como está documentado.

Tienes dos opciones, según si las líneas largas son normales o excepcionales.

**Opción A: subir el límite.** Si sabes una cota razonable (digamos 16 MiB para una traza JSON), configura el buffer **antes** del primer `Scan`:

```go
sc := bufio.NewScanner(f)
sc.Buffer(make([]byte, 0, 1<<20), 16<<20) // inicial 1 MiB, máximo 16 MiB
for sc.Scan() {
    process(sc.Text())
}
if err := sc.Err(); err != nil {
    return fmt.Errorf("scanning %s: %w", path, err)
}
```

El primer argumento es el buffer inicial; el segundo, el tamaño máximo al que puede crecer. Si una línea supera 16 MiB, vuelves al mismo error, que ahora sí indica algo anómalo. Ventaja: no cambias nada más. Desventaja: tienes que elegir un número.

**Opción B: `bufio.Reader`, sin límite.** `ReadString('\n')` (o `ReadBytes`) devuelve la línea entera sea del tamaño que sea, asignando lo necesario:

```go
r := bufio.NewReaderSize(f, 1<<20)
for {
    line, err := r.ReadString('\n')
    if len(line) > 0 {
        process(strings.TrimSuffix(line, "\n")) // la última línea puede no tener \n
    }
    if err == io.EOF {
        break
    }
    if err != nil {
        return fmt.Errorf("reading %s: %w", path, err)
    }
}
```

El orden importa: procesas `line` **antes** de mirar `err`, porque la última línea de un archivo sin salto final llega junto con `io.EOF`. Es el patrón documentado del paquete y el que más gente se salta.

Cuál elegir: A si el 99,9 % de las líneas son cortas y quieres el código más simple; B si de verdad no puedes acotar el tamaño o si quieres procesar sin que una línea de 2 GB sea un error. Para un log con trazas JSON incrustadas, A con 16-64 MiB suele ser lo correcto: una línea más grande que eso es un archivo corrupto, no un caso de uso.

Dos observaciones sobre el fragmento original, independientes del error:

1. **`os.Open` con error ignorado.** Si `path` no existe, `f` es `nil` y el `Scanner` falla con un mensaje confuso (`invalid argument`). Comprueba el error siempre.
2. **`sc.Text()` asigna una `string` por línea** copiando el buffer. Si `process` no retiene la línea, `sc.Bytes()` evita la copia, pero el slice **se invalida en el siguiente `Scan`**: si `process` lo guarda en algún sitio, el contenido cambiará bajo sus pies. `Text()` es seguro; `Bytes()` es rápido; elige sabiendo cuál usas.

Y para saber cuánto miden tus líneas antes de elegir el límite:

```sh
awk '{ if (length($0) > max) max = length($0) } END { print max }' app.log
```

Comprobación de la opción A con una línea artificial de 100 KiB, que con el límite por defecto falla y con 16 MiB pasa:

```go
func TestScannerHandlesLongLines(t *testing.T) {
    long := strings.Repeat("x", 100<<10)
    in := strings.NewReader("corta\n" + long + "\notra\n")
    sc := bufio.NewScanner(in)
    sc.Buffer(make([]byte, 0, 1<<20), 16<<20)
    n := 0
    for sc.Scan() {
        n++
    }
    if err := sc.Err(); err != nil || n != 3 {
        t.Fatalf("n=%d err=%v", n, err)
    }
}
```""",
            },
        ]
    },
    # 25) Receptores valor vs puntero: error "method has pointer receiver" pegado. Principiante
    {
        "messages": [
            {
                "role": "user",
                "content": r"""No entiendo este error, el struct tiene el método que pide la interfaz:

```go
type Shape interface {
    Area() float64
    Scale(f float64)
}

type Rect struct{ W, H float64 }

func (r Rect) Area() float64 { return r.W * r.H }
func (r *Rect) Scale(f float64) { r.W *= f; r.H *= f }

func main() {
    var s Shape = Rect{2, 3}
    s.Scale(2)
    fmt.Println(s.Area())
}
```

```
./main.go:14:16: cannot use Rect{…} (value of struct type Rect) as Shape value in variable declaration: Rect does not implement Shape (method Scale has pointer receiver)
```""",
            },
            {
                "role": "assistant",
                "content": r"""`Rect` (el valor) tiene `Area`, pero `Scale` está definido sobre `*Rect` (el puntero). El **conjunto de métodos** de `Rect` incluye solo los de receptor valor; el de `*Rect` incluye los dos. Para ser un `Shape` hacen falta ambos, así que solo `*Rect` lo es. El mensaje te lo dice al final: «method Scale has pointer receiver».

Arreglo: guarda un puntero en la interfaz.

```go
var s Shape = &Rect{2, 3}
s.Scale(2)
fmt.Println(s.Area()) // 24
```

Por qué `Rect` no puede ser `Shape` aunque «tenga» el método: si Go lo permitiera, `s.Scale(2)` recibiría la dirección de la **copia** guardada dentro de la interfaz y la modificaría; tú verías que `Scale` no hace nada y el error sería silencioso. El compilador prefiere rechazarlo.

Esto es distinto de lo que pasa fuera de interfaces, donde sí puedes llamar `r.Scale(2)` sobre una variable `r := Rect{2, 3}`: el compilador reescribe a `(&r).Scale(2)` porque `r` es direccionable. Una copia dentro de una interfaz, un valor de map (`m["k"].Scale(2)`) o el resultado de una función no lo son, y ahí vuelve a fallar.

La regla para elegir receptor:

| Usa receptor puntero `*T` si... | Usa receptor valor `T` si... |
|---|---|
| el método modifica el receptor | el método solo lee |
| el struct es grande (copiarlo cuesta) | el tipo es pequeño e inmutable (`time.Time`, `Point`) |
| el struct contiene un `sync.Mutex` o similar | quieres que funcione también sobre valores en maps y en interfaces por valor |
| **cualquier otro método del tipo ya usa puntero** | ningún método necesita puntero |

La última fila es la que más importa: **mezclar receptores en un mismo tipo es la fuente de este error**. Si `Scale` necesita puntero, pon `Area` también con puntero, y usa siempre `*Rect`. Así el conjunto de métodos es uno solo y no hay sorpresas:

```go
func (r *Rect) Area() float64 { return r.W * r.H }
func (r *Rect) Scale(f float64) { r.W *= f; r.H *= f }
```

Para que el compilador te avise en el sitio donde defines el tipo y no en el primer uso, añade esta línea junto al struct:

```go
var _ Shape = (*Rect)(nil)
```

No genera código; falla en compilación si `*Rect` deja de satisfacer `Shape`. Y si en algún momento quieres que el **valor** lo satisfaga, escribe `var _ Shape = Rect{}` y el compilador te obligará a quitar todos los receptores puntero.

Comprobación de que `Scale` ahora modifica lo que crees:

```go
r := &Rect{2, 3}
var s Shape = r
s.Scale(2)
fmt.Println(r.W, r.H) // 4 6: la interfaz y r apuntan al mismo Rect
```""",
            },
        ]
    },
    # 26) Enums con iota, String(), validación y JSON; multiturno con exhaustividad
    {
        "messages": [
            {
                "role": "user",
                "content": "Go no tiene enums y lo echo de menos. ¿Cuál es la forma idiomática de tener un `Status` con `Pending`, `Active`, `Closed` que se imprima bien, se serialice a JSON como texto y no acepte valores inválidos?",
            },
            {
                "role": "assistant",
                "content": r"""La forma idiomática es un tipo con nombre sobre `int`, constantes con `iota`, un `String()` y conversiones explícitas para JSON. No es un enum cerrado como en Rust o Kotlin (nada impide `Status(42)`), así que la validación la pones tú en los bordes.

```go
package order

import (
    "encoding/json"
    "fmt"
)

type Status int

const (
    Pending Status = iota + 1 // empieza en 1: el cero queda como "no asignado"
    Active
    Closed
)

var statusNames = map[Status]string{
    Pending: "pending",
    Active:  "active",
    Closed:  "closed",
}

func (s Status) String() string {
    if name, ok := statusNames[s]; ok {
        return name
    }
    return fmt.Sprintf("Status(%d)", int(s))
}

func (s Status) IsValid() bool {
    _, ok := statusNames[s]
    return ok
}

func ParseStatus(text string) (Status, error) {
    for s, name := range statusNames {
        if name == text {
            return s, nil
        }
    }
    return 0, fmt.Errorf("invalid status %q", text)
}

func (s Status) MarshalText() ([]byte, error) {
    if !s.IsValid() {
        return nil, fmt.Errorf("cannot marshal invalid status %d", int(s))
    }
    return []byte(s.String()), nil
}

func (s *Status) UnmarshalText(text []byte) error {
    parsed, err := ParseStatus(string(text))
    if err != nil {
        return err
    }
    *s = parsed
    return nil
}
```

Decisiones:

- **`iota + 1`**: el valor cero de `Status` (lo que tiene un struct recién creado) no coincide con ningún estado válido. Así, un `Order{}` sin asignar estado falla en `IsValid` en lugar de parecer `Pending` por accidente. Si tu dominio tiene un estado por defecto natural, empieza en `iota` y haz que el cero sea ese.
- **`MarshalText`/`UnmarshalText`** en vez de `MarshalJSON`: `encoding/json` los usa para el valor **y para claves de map** (`map[Status]int` se serializa con nombres), y también los usan `encoding/xml`, `flag` y otros. Con `MarshalJSON` solo cubrirías JSON.
- **El puntero en `UnmarshalText`** es obligatorio: tiene que modificar el receptor.
- **`String()` devuelve `Status(42)` para valores desconocidos** en lugar de hacer *panic*: imprimir un valor corrupto en un log es mejor que caerse mientras lo describes.

El `String()` y el map se pueden generar con `stringer` (`go install golang.org/x/tools/cmd/stringer@latest` y `//go:generate stringer -type=Status -linecomment`), lo que evita que se desincronicen al añadir un estado. Para tres valores, escribirlo a mano es más claro que añadir generación de código; a partir de diez, `stringer`.

Comprobación de las cuatro propiedades que pedías:

```go
func TestStatus(t *testing.T) {
    if got := fmt.Sprint(Active); got != "active" {
        t.Errorf("String = %q", got)
    }
    b, _ := json.Marshal(struct{ S Status }{Closed})
    if string(b) != `{"S":"closed"}` {
        t.Errorf("json = %s", b)
    }
    var in struct{ S Status }
    if err := json.Unmarshal([]byte(`{"S":"bogus"}`), &in); err == nil {
        t.Error("accepted invalid status")
    }
    if Status(0).IsValid() || Status(99).IsValid() {
        t.Error("zero or out-of-range status is valid")
    }
}
```""",
            },
            {"role": "user", "content": "Lo que más me preocupa es que si añado un estado nuevo se me olvide un `switch` en alguna parte. ¿Hay forma de que el compilador me avise?"},
            {
                "role": "assistant",
                "content": r"""El compilador no: un `switch` sobre `Status` sin `default` compila aunque falten casos, porque `Status` es un `int` con nombre y «todos los valores» serían 2^63. Lo que sí hay es un *linter* que entiende la convención y una técnica de diseño para los sitios críticos.

**1. `exhaustive`** (incluido en golangci-lint) detecta las constantes del tipo declaradas en el mismo paquete y avisa cuando un `switch` no las cubre todas:

```
order/transitions.go:12:2: missing cases in switch of type order.Status: order.Closed (exhaustive)
```

Actívalo en `.golangci.yml` y, si quieres que un `default` **no** cuente como cobertura (para que añadir un estado siga avisando), configura `default-signifies-exhaustive: false`, que es el valor por defecto. Desde la versión reciente también comprueba literales de map (`map[Status]string` con claves que faltan), que cubre justo tu `statusNames`.

**2. Para las transiciones de estado, una tabla en vez de un `switch`.** Un `switch` disperso por el código se olvida; una tabla única se revisa en un sitio y se puede testear por completo:

```go
var transitions = map[Status][]Status{
    Pending: {Active, Closed},
    Active:  {Closed},
    Closed:  {},
}

func (s Status) CanTransitionTo(next Status) bool {
    return slices.Contains(transitions[s], next)
}
```

Y un test que falla si añades un estado y no lo registras:

```go
func TestEveryStatusHasTransitions(t *testing.T) {
    for s := range statusNames {
        if _, ok := transitions[s]; !ok {
            t.Errorf("%s has no entry in transitions", s)
        }
    }
}
```

**3. Para el `String()` y el map de nombres**, el mismo truco: un test que recorre `Status(1)..Status(n)` hasta encontrar el primero sin nombre y comprueba que `n` coincide con una constante `statusCount` que mantienes junto a las demás. O `stringer`, que regenera el `String()` y hace que cualquier valor sin nombre se vea como `Status(4)` en el primer log.

Lo que no te recomiendo: hacer `panic` en el `default` de cada `switch` «para enterarte». Te enteras en producción. El *linter* en CI te entera en la PR, que es donde quieres enterarte.

Resumen operativo: `exhaustive` en CI para los `switch`, una tabla con test para las transiciones, y `iota + 1` para que el cero no se cuele como estado válido. Con esas tres cosas, añadir `Archived` mañana rompe el *pipeline* en cada sitio que haya que tocar, que es lo más parecido a un enum cerrado que Go te va a dar.""",
            },
        ]
    },
    # 27) http.Client: timeouts, reutilización, cerrar body, reintentos con backoff. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Our Go service calls a third-party API and every few days it gets stuck: goroutines pile up and the pod gets OOM-killed. The call looks like this:

```go
func getPrice(id string) (float64, error) {
    resp, err := http.Get("https://api.vendor.com/prices/" + id)
    if err != nil {
        return 0, err
    }
    var p struct{ Price float64 }
    json.NewDecoder(resp.Body).Decode(&p)
    return p.Price, nil
}
```

What's wrong with it?""",
            },
            {
                "role": "assistant",
                "content": r"""Three things, and the first two explain the pile-up:

1. **No timeout anywhere.** `http.Get` uses `http.DefaultClient`, whose `Timeout` is zero: a request waits forever if the vendor accepts the TCP connection and never answers. Every stuck call is a goroutine holding a connection, a buffer and a stack. That is your OOM.
2. **The body is never closed.** Without `resp.Body.Close()` the connection is never returned to the pool, so each call opens a new one; file descriptors and memory grow until the kernel or the vendor says no.
3. **The decode error is ignored**, so a 500 with an HTML body silently becomes `price = 0`.

Rewritten:

```go
package vendor

import (
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net"
    "net/http"
    "time"
)

type Client struct {
    http    *http.Client
    baseURL string
}

func New(baseURL string) *Client {
    return &Client{
        baseURL: baseURL,
        http: &http.Client{
            Timeout: 10 * time.Second, // hard upper bound for the whole call
            Transport: &http.Transport{
                MaxIdleConns:        100,
                MaxIdleConnsPerHost: 20, // default is 2: a bottleneck for one upstream
                IdleConnTimeout:     90 * time.Second,
                DialContext: (&net.Dialer{
                    Timeout: 3 * time.Second,
                }).DialContext,
                TLSHandshakeTimeout:   3 * time.Second,
                ResponseHeaderTimeout: 5 * time.Second,
            },
        },
    }
}

func (c *Client) Price(ctx context.Context, id string) (float64, error) {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/prices/"+id, nil)
    if err != nil {
        return 0, err
    }
    resp, err := c.http.Do(req)
    if err != nil {
        return 0, fmt.Errorf("price %s: %w", id, err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        io.Copy(io.Discard, io.LimitReader(resp.Body, 4096)) // drain so the conn is reused
        return 0, fmt.Errorf("price %s: status %d", id, resp.StatusCode)
    }
    var p struct{ Price float64 `json:"price"` }
    if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&p); err != nil {
        return 0, fmt.Errorf("price %s: decode: %w", id, err)
    }
    return p.Price, nil
}
```

Why each piece:

- **One `http.Client` for the lifetime of the process.** The client owns the connection pool; creating one per call throws the pool away. Store it in a struct and inject it.
- **`Timeout` on the client** covers dial, TLS, headers and body read. The finer-grained transport timeouts let you fail fast on the slow phases (a 3 s dial that fails is better than waiting the full 10 s), and `ResponseHeaderTimeout` is the one that catches "connected but never answers".
- **`NewRequestWithContext`** makes the call cancellable from the caller: when the incoming HTTP request that triggered this lookup is cancelled, so is the upstream call. Without it, the `Timeout` is your only escape hatch.
- **`defer resp.Body.Close()`** right after checking `err`. On error, `resp` is `nil`, so the close must come after the check.
- **Draining the body on a non-200** lets the transport reuse the connection; `LimitReader` caps how much you are willing to read for that.
- **`LimitReader` on the success path** protects you from a vendor bug that returns gigabytes.
- **`MaxIdleConnsPerHost`**: the default of 2 means that with 20 concurrent calls, 18 of them open and close a fresh connection each time, with a TLS handshake each. For a single upstream, raise it to your expected concurrency.

If the vendor is flaky, add retries **only for idempotent requests and retryable failures** (connection errors, 429, 502/503/504), with backoff and a cap, and always respecting `ctx`:

```go
func (c *Client) PriceWithRetry(ctx context.Context, id string) (float64, error) {
    var lastErr error
    for attempt := 0; attempt < 3; attempt++ {
        if attempt > 0 {
            delay := time.Duration(1<<attempt) * 200 * time.Millisecond // 400 ms, 800 ms
            select {
            case <-time.After(delay):
            case <-ctx.Done():
                return 0, ctx.Err()
            }
        }
        price, err := c.Price(ctx, id)
        if err == nil {
            return price, nil
        }
        lastErr = err
        if !retryable(err) {
            return 0, err
        }
    }
    return 0, fmt.Errorf("after 3 attempts: %w", lastErr)
}
```

where `retryable` checks for `net.Error` / `errors.Is(err, context.DeadlineExceeded)` on the transport side and inspects the status code you embedded in the error (a small `StatusError` type with `errors.As` is cleaner than string matching). Do not retry on `context.Canceled`: the caller has gone away.

How to confirm the diagnosis before and after the change: `curl localhost:6060/debug/pprof/goroutine?debug=1 | head -1` on the running pod gives the goroutine count; with the old code it climbs over days and the stacks show `net/http.(*persistConn).readLoop`. A test with `httptest.NewServer` whose handler sleeps 30 s should make `Price` return a timeout error in about 5 s (`ResponseHeaderTimeout`), and `go vet` plus the `bodyclose` linter catch the missing `Close` statically.""",
            },
        ]
    },
    # 28) Build: flags, cross-compile, -ldflags -X, go:embed, Docker multi-stage. System variante (vos)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense (vos), breve y práctico, con los comandos exactos."},
            {
                "role": "user",
                "content": "Tengo que armar el binario de un servicio Go para un contenedor, con la versión y el commit metidos adentro, los archivos de `templates/` incluidos en el binario, y que compile para linux/arm64 desde mi Mac. ¿Cómo lo hacés vos?",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro piezas: variables en tiempo de *link* para la versión, `embed` para las plantillas, variables de entorno para la plataforma destino y un Dockerfile de dos etapas.

**1. Versión y commit con `-ldflags -X`.** Declarás variables de paquete y el *linker* las sobreescribe; sin generación de código ni archivos de versión.

```go
// internal/buildinfo/buildinfo.go
package buildinfo

var (
    Version = "dev"
    Commit  = "none"
)
```

```sh
go build -trimpath \
  -ldflags="-s -w -X github.com/acme/svc/internal/buildinfo.Version=$(git describe --tags --always) \
            -X github.com/acme/svc/internal/buildinfo.Commit=$(git rev-parse --short HEAD)" \
  -o bin/svc ./cmd/svc
```

- `-X ruta.completa.Variable=valor`: la ruta es la del **paquete**, no la del archivo. Solo funciona con `string` no inicializadas por función.
- `-s -w`: sin tabla de símbolos ni DWARF; el binario pesa un 30 % menos. Las trazas de *panic* siguen teniendo nombres de función y líneas, así que no perdés nada en producción.
- `-trimpath`: quita las rutas absolutas de tu máquina de las trazas y hace el *build* reproducible.

Si solo necesitás el commit, no hace falta ni eso: `runtime/debug.ReadBuildInfo()` ya trae `vcs.revision`, `vcs.time` y `vcs.modified` cuando compilás dentro de un repo git. La versión semántica (el *tag*) sí hay que inyectarla.

**2. Plantillas dentro del binario con `embed`.**

```go
package web

import (
    "embed"
    "html/template"
)

//go:embed templates/*.html
var templateFS embed.FS

var Templates = template.Must(template.ParseFS(templateFS, "templates/*.html"))
```

La directiva va pegada a la variable, sin línea en blanco, y las rutas son relativas al archivo `.go` que la contiene. `embed.FS` es de solo lectura y se verifica en compilación: si `templates/` no existe o el patrón no matchea nada, `go build` falla, que es lo que querés. Para archivos estáticos servidos por HTTP, el mismo `embed.FS` va directo a `http.FileServerFS(templateFS)` (Go 1.22) o `http.FS`.

**3. Compilación cruzada.** Go la hace sin *toolchain* extra:

```sh
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -ldflags="..." -o bin/svc-linux-arm64 ./cmd/svc
```

`CGO_ENABLED=0` es la clave: sin cgo el binario es estático, no depende de la libc del contenedor y funciona en `scratch` o `distroless`. Si alguna dependencia necesita cgo (`sqlite3` clásico, por ejemplo), vas a necesitar un compilador cruzado de C; la alternativa es buscar la versión en Go puro (`modernc.org/sqlite`).

**4. Dockerfile de dos etapas**, compilando dentro de la imagen para no depender de tu Mac:

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.23 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
ARG TARGETOS TARGETARCH VERSION=dev COMMIT=none
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -trimpath \
    -ldflags="-s -w -X github.com/acme/svc/internal/buildinfo.Version=$VERSION -X github.com/acme/svc/internal/buildinfo.Commit=$COMMIT" \
    -o /out/svc ./cmd/svc

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/svc /svc
USER nonroot:nonroot
ENTRYPOINT ["/svc"]
```

```sh
docker buildx build --platform linux/arm64 \
  --build-arg VERSION=$(git describe --tags --always) --build-arg COMMIT=$(git rev-parse --short HEAD) \
  -t acme/svc:latest .
```

Detalles que ahorran tiempo: copiar `go.mod`/`go.sum` y hacer `go mod download` **antes** del resto hace que la capa de dependencias se cachee; `--platform=$BUILDPLATFORM` compila nativo en tu Mac y cruza con `GOARCH`, en vez de emular arm64 con QEMU (10 veces más lento); `distroless/static:nonroot` no tiene *shell* ni usuario *root*, y como el binario es estático no necesita nada más. Si usás `time.LoadLocation` o TLS hacia afuera, la imagen `static` ya trae certificados y `tzdata`; si en cambio elegís `scratch`, tenés que copiarlos vos o importar `_ "time/tzdata"`.

Para verificar: `docker run --rm acme/svc:latest --version` (si tu `main` imprime `buildinfo.Version`), y `go version -m bin/svc-linux-arm64` te muestra la plataforma, los *flags* de *build* y la revisión git con que se compiló, sin ejecutarlo.""",
            },
        ]
    },
    # 29) Shadowing con := dentro de if/for: err que nunca se devuelve. Usuario trae código
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Este código a veces devuelve `nil, nil` y no entiendo cómo: siempre asigno `user` o devuelvo un error.

```go
func loadUser(ctx context.Context, id string) (*User, error) {
    var user *User
    var err error
    if cached, ok := cache.Get(id); ok {
        user = cached
    } else {
        user, err := db.FindUser(ctx, id)
        if err != nil {
            return nil, err
        }
        cache.Set(id, user)
    }
    return user, err
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""La línea `user, err := db.FindUser(ctx, id)` dentro del `else` **declara dos variables nuevas** que solo existen en ese bloque. Las `user` y `err` externas no se tocan: cuando no hay caché, `cache.Set` recibe el `user` interno correcto, el bloque termina, y el `return user, err` de fuera devuelve el `user` externo, que sigue siendo `nil`, con `err` también `nil`. De ahí el `nil, nil`.

Es *shadowing* por `:=`. El operador `:=` declara nuevas variables **si al menos una de las de la izquierda es nueva en ese ámbito**; como dentro del `else` ninguna de las dos existe todavía (las externas están en el ámbito de la función, no del bloque), crea las dos. Que las externas tengan el mismo nombre no cambia nada.

Arreglo mínimo: asignación en vez de declaración.

```go
} else {
    user, err = db.FindUser(ctx, id) // = : usa las variables de fuera
    if err != nil {
        return nil, err
    }
    cache.Set(id, user)
}
```

Y mejor aún, reestructurar para que no haga falta ninguna variable declarada antes y el *shadowing* sea imposible:

```go
func loadUser(ctx context.Context, id string) (*User, error) {
    if cached, ok := cache.Get(id); ok {
        return cached, nil
    }
    user, err := db.FindUser(ctx, id)
    if err != nil {
        return nil, err
    }
    cache.Set(id, user)
    return user, nil
}
```

El patrón «retorno temprano» (*early return*) hace que cada camino termine donde se decide, y no deja variables «pendientes de asignar» que un bloque pueda ocultar.

Por qué el compilador no te avisó: el `user` interno **sí se usa** (en `cache.Set`), así que no salta el «declared and not used». Cuando el *shadowing* es sobre `err` y la variable interna solo se compara, a menudo sí salta ese error y te pone sobre la pista; aquí no hubo suerte.

Cómo detectarlo automáticamente:

- `go vet` no incluye el análisis de *shadowing* por defecto (demasiados falsos positivos en código idiomático como `if err := f(); err != nil`). Está disponible como herramienta aparte:

```sh
go install golang.org/x/tools/go/analysis/passes/shadow/cmd/shadow@latest
go vet -vettool=$(which shadow) ./...
```

- En golangci-lint, `govet` con `enable: [shadow]` en la configuración, o el *linter* `ineffassign`, que habría marcado que la asignación a la `err` externa nunca se lee en el camino del `else`.

Test de regresión, con un `cache` vacío para forzar el camino de la base de datos:

```go
func TestLoadUserMissesCacheAndReturnsUser(t *testing.T) {
    cache.Clear()
    u, err := loadUser(context.Background(), "42")
    if err != nil {
        t.Fatal(err)
    }
    if u == nil {
        t.Fatal("got nil user with nil error")
    }
}
```

Con el código original, este test falla en el segundo `Fatal`; con cualquiera de las dos versiones corregidas, pasa. Como regla para leer código ajeno: cada `:=` dentro de un `if`, `for` o `else` que reutiliza un nombre de fuera merece una segunda mirada.""",
            },
        ]
    },
    # 30) Apagado ordenado: signal.NotifyContext, srv.Shutdown, tareas en curso. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Cuando Kubernetes hace rolling update, mi API en Go corta peticiones a medias y los clientes ven errores de conexión. Uso `http.ListenAndServe` en `main` y nada más. ¿Qué me falta?",
            },
            {
                "role": "assistant",
                "content": r"""Te falta el apagado ordenado: Kubernetes envía `SIGTERM`, y el *runtime* de Go, si nadie lo captura, termina el proceso **inmediatamente**, con las conexiones abiertas y las peticiones a medio responder. `ListenAndServe` no sabe nada de señales.

La secuencia correcta es: capturar la señal → dejar de aceptar conexiones nuevas → esperar a que terminen las peticiones en curso (con un límite) → cerrar recursos → salir.

```go
package main

import (
    "context"
    "errors"
    "log/slog"
    "net"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func main() {
    if err := run(); err != nil {
        slog.Error("exit", "err", err)
        os.Exit(1)
    }
}

func run() error {
    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
    defer stop()

    srv := &http.Server{
        Addr:              ":8080",
        Handler:           newRouter(),
        ReadHeaderTimeout: 5 * time.Second,
        BaseContext:       func(net.Listener) context.Context { return ctx },
    }

    errCh := make(chan error, 1)
    go func() {
        errCh <- srv.ListenAndServe()
    }()
    slog.Info("listening", "addr", srv.Addr)

    select {
    case err := <-errCh:
        return err // fallo al arrancar (puerto ocupado) o cierre inesperado
    case <-ctx.Done():
        slog.Info("shutdown: signal received")
    }

    shutdownCtx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
    defer cancel()
    if err := srv.Shutdown(shutdownCtx); err != nil {
        return err // ErrDeadlineExceeded si quedaban peticiones al agotar el plazo
    }
    if err := <-errCh; !errors.Is(err, http.ErrServerClosed) {
        return err
    }
    return nil
}
```

Qué hace cada parte:

- **`signal.NotifyContext`** convierte la señal en una cancelación de contexto; es la forma moderna de `signal.Notify` + canal. `SIGINT` para `Ctrl+C` en local.
- **`srv.Shutdown(ctx)`** cierra el *listener* (ninguna conexión nueva), espera a que las conexiones activas queden ociosas y las cierra. Las peticiones en curso terminan normalmente. Si el plazo se agota, devuelve el error del contexto y las conexiones que queden se cortan.
- **El plazo de 25 s** tiene que ser **menor** que `terminationGracePeriodSeconds` del Pod (30 s por defecto): si tu `Shutdown` tarda más, Kubernetes manda `SIGKILL` y vuelves al corte brusco.
- **`BaseContext`** hace que `r.Context()` de cada petición descienda del contexto del proceso; con eso, las peticiones que hacen trabajo largo pueden ver `ctx.Done()` y abortar limpio durante el apagado.
- **`errCh` con buffer 1**: la *goroutine* de `ListenAndServe` puede terminar sin que nadie esté leyendo todavía; sin buffer se quedaría bloqueada para siempre.
- **`ErrServerClosed`** es el retorno normal de `ListenAndServe` tras un `Shutdown`; no es un error.

Hay un segundo problema que explica parte de los errores de conexión y que el código no resuelve solo: **Kubernetes sigue enviando tráfico durante unos instantes después del `SIGTERM`**, porque quitar el Pod de los *endpoints* del Service y propagarlo a los *kube-proxy* no es instantáneo. Si tu servidor deja de aceptar en el milisegundo cero, esas peticiones fallan. Dos remedios, que se combinan:

1. Un `preStop` en el Deployment que duerma unos segundos antes del `SIGTERM`, dando tiempo a que el tráfico deje de llegar:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sleep", "5"]
terminationGracePeriodSeconds: 30
```

2. Que el *readiness probe* empiece a fallar en cuanto recibes la señal, para que el balanceador te retire antes de cerrar. Un `atomic.Bool` que el *handler* de `/ready` consulta y que pones a `false` justo tras `ctx.Done()`, seguido de un `time.Sleep` corto antes de `Shutdown`.

Si además tienes trabajo de fondo (consumidores de cola, *tickers*), cada uno debe recibir el mismo `ctx`, y un `errgroup` o `WaitGroup` debe esperarlos tras `Shutdown` antes de salir, para que no se corte un mensaje a medio procesar.

Comprobación en local, sin Kubernetes:

```sh
go run ./cmd/api &
PID=$!
curl -s 'localhost:8080/slow' &     # un handler que tarda 3 s
sleep 0.5
kill -TERM $PID                      # el curl debe completar con 200, y luego el proceso sale
wait
```

Si el `curl` imprime «connection reset» o «empty reply», el `Shutdown` no está esperando; si el proceso tarda más de 25 s en salir, hay una petición que no mira `ctx` y agota el plazo.""",
            },
        ]
    },
]
