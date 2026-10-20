"""Rust 2021/2024 estable: ownership, lifetimes, errores, traits, async, unsafe, cargo."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) E0382: valor movido. Principiante
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Estoy empezando con Rust y no entiendo este error, el código es trivial:

```rust
fn imprimir(nombres: Vec<String>) {
    for n in nombres {
        println!("{n}");
    }
}

fn main() {
    let nombres = vec![String::from("ana"), String::from("luis")];
    imprimir(nombres);
    println!("total: {}", nombres.len());
}
```

```
error[E0382]: borrow of moved value: `nombres`
  --> src/main.rs:10:27
   |
8  |     let nombres = vec![String::from("ana"), String::from("luis")];
   |         ------- move occurs because `nombres` has type `Vec<String>`, which does not implement the `Copy` trait
9  |     imprimir(nombres);
   |              ------- value moved here
10 |     println!("total: {}", nombres.len());
   |                           ^^^^^^^ value borrowed here after move
   |
help: consider cloning the value if the performance cost is acceptable
   |
9  |     imprimir(nombres.clone());
   |                     ++++++++
```

¿Por qué no puedo usar `nombres` después de pasarlo a la función?""",
            },
            {
                "role": "assistant",
                "content": r"""Porque `imprimir(nombres)` **entrega** el vector a la función, no se lo presta. Un `Vec<String>` es dueño de memoria en el heap; Rust no lo copia implícitamente (no es `Copy`), así que al pasarlo por valor la propiedad se mueve a `imprimir`, y al terminar esa función el vector se libera. En `main`, `nombres` queda como una variable inválida y el compilador te impide leerla.

El cambio correcto es que la función pida un **préstamo** (`&`), porque solo necesita mirar los nombres, no quedárselos:

```rust
fn imprimir(nombres: &[String]) {
    for n in nombres {
        println!("{n}");
    }
}

fn main() {
    let nombres = vec![String::from("ana"), String::from("luis")];
    imprimir(&nombres);
    println!("total: {}", nombres.len());
}
```

Dos detalles de la firma:

- `&[String]` (un *slice*) en vez de `&Vec<String>`: acepta vectores, arrays y trozos de ambos, y `clippy` te avisaría con `ptr_arg` si pones `&Vec`. Un `&Vec<String>` se convierte a `&[String]` solo.
- `for n in nombres` sobre un `&[String]` da `&String` en cada vuelta; `println!` lo imprime igual.

La sugerencia del compilador (`nombres.clone()`) también compila, pero copia los dos `String` enteros para que una función que solo imprime se quede con una copia que tira al terminar. Clonar es la salida cuando de verdad necesitas dos dueños; aquí no.

Regla mental para leer firmas: parámetro **por valor** (`Vec<String>`) significa «me lo quedo»; **por referencia** (`&[String]`, `&str`, `&T`) significa «lo miro y te lo devuelvo». Los tipos pequeños como `i32`, `bool`, `char` o las propias referencias sí son `Copy`, por eso con ellos nunca ves este error.""",
            },
        ]
    },
    # 2) E0502: push dentro de un for sobre el mismo Vec
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala el problema de raíz, no solo el parche, y verifica tu propuesta."},
            {
                "role": "user",
                "content": r"""quiero duplicar las puntuaciones altas y añadirlas al final del vector pero rust no me deja:

```rust
fn main() {
    let mut puntuaciones = vec![10, 20, 30, 5];
    for p in &puntuaciones {
        if *p > 15 {
            puntuaciones.push(*p * 2);
        }
    }
    println!("{puntuaciones:?}");
}
```

```
error[E0502]: cannot borrow `puntuaciones` as mutable because it is also borrowed as immutable
 --> src/main.rs:5:13
  |
3 |     for p in &puntuaciones {
  |              -------------
  |              |
  |              immutable borrow occurs here
  |              immutable borrow later used here
4 |         if *p > 15 {
5 |             puntuaciones.push(*p * 2);
  |             ^^^^^^^^^^^^^^^^^^^^^^^^^ mutable borrow occurs here
```""",
            },
            {
                "role": "assistant",
                "content": r"""El error es correcto y te está evitando un bug real. `for p in &puntuaciones` mantiene un préstamo inmutable (el iterador apunta al buffer del vector) durante todo el bucle; `push` puede **reasignar ese buffer** a otra dirección, dejando el iterador apuntando a memoria liberada. En C++ eso es *iterator invalidation* y comportamiento indefinido; en Rust no compila.

Hay además un problema de diseño en la idea: si pudieras añadir mientras recorres, los nuevos (40, 60) también superan 15 y generarían 80, 160… sin terminar nunca. Lo que quieres es recorrer el **contenido original** y añadir al final. Hazlo en dos fases:

```rust
fn main() {
    let mut puntuaciones = vec![10, 20, 30, 5];

    let dobles: Vec<i32> = puntuaciones
        .iter()
        .filter(|&&p| p > 15)
        .map(|&p| p * 2)
        .collect();
    puntuaciones.extend(dobles);

    println!("{puntuaciones:?}"); // [10, 20, 30, 5, 40, 60]
}
```

El préstamo inmutable termina cuando `collect()` devuelve el vector nuevo; `extend` toma el préstamo mutable después, sin solaparse.

Si los elementos son `Copy` (como aquí, `i32`) también vale recorrer por índice fijando la longitud **antes** del bucle:

```rust
let n = puntuaciones.len();
for i in 0..n {
    let p = puntuaciones[i]; // copia el i32; el préstamo acaba aquí
    if p > 15 {
        puntuaciones.push(p * 2);
    }
}
```

Fijar `n` es lo que evita el bucle infinito; `for i in 0..puntuaciones.len()` también compila (el `len()` se evalúa una sola vez al crear el rango), pero deja al lector dudando. Prefiero la versión con `collect` + `extend`: dice qué se añade y no depende de índices.

Verificación mental: entrada `[10, 20, 30, 5]`; pasan el filtro 20 y 30; dobles `[40, 60]`; salida `[10, 20, 30, 5, 40, 60]`.""",
            },
        ]
    },
    # 3) E0499: dos &mut sobre el mismo slice
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo una función que transfiere saldo entre dos cuentas de un vector y el compilador se queja de dos préstamos mutables:

```rust
struct Cuenta { id: u32, saldo: u64 }

fn transferir(cuentas: &mut Vec<Cuenta>, desde: usize, hacia: usize, monto: u64) {
    let origen = &mut cuentas[desde];
    let destino = &mut cuentas[hacia];
    origen.saldo -= monto;
    destino.saldo += monto;
}
```

```
error[E0499]: cannot borrow `*cuentas` as mutable more than once at a time
 --> src/main.rs:5:24
  |
4 |     let origen = &mut cuentas[desde];
  |                       ------- first mutable borrow occurs here
5 |     let destino = &mut cuentas[hacia];
  |                        ^^^^^^^ second mutable borrow occurs here
6 |     origen.saldo -= monto;
  |     --------------------- first borrow later used here
```

Sé que `desde` y `hacia` son distintos, ¿cómo se lo digo al compilador?""",
            },
            {
                "role": "assistant",
                "content": r"""No se lo dices: el compilador no razona sobre valores de `usize` en tiempo de ejecución, y además tu garantía es falsa en general (nada impide llamar con `desde == hacia`, y entonces tendrías dos `&mut` a la misma cuenta). Hay dos formas correctas según lo que necesites.

**1. No necesitas las dos referencias a la vez.** Secuencia las operaciones; cada indexación es un préstamo que termina en la misma línea. Aprovecha para validar lo que tu versión no validaba:

```rust
#[derive(Debug)]
pub struct Cuenta {
    pub id: u32,
    pub saldo: u64,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ErrorTransferencia {
    MismaCuenta,
    IndiceInvalido,
    SaldoInsuficiente,
}

pub fn transferir(
    cuentas: &mut [Cuenta],
    desde: usize,
    hacia: usize,
    monto: u64,
) -> Result<(), ErrorTransferencia> {
    if desde == hacia {
        return Err(ErrorTransferencia::MismaCuenta);
    }
    if desde >= cuentas.len() || hacia >= cuentas.len() {
        return Err(ErrorTransferencia::IndiceInvalido);
    }
    let nuevo_origen = cuentas[desde]
        .saldo
        .checked_sub(monto)
        .ok_or(ErrorTransferencia::SaldoInsuficiente)?;
    cuentas[desde].saldo = nuevo_origen;
    cuentas[hacia].saldo += monto;
    Ok(())
}
```

`checked_sub` evita el otro bug que tenía el original: con `u64`, `saldo -= monto` sin saldo suficiente hace *panic* en debug y en release da un saldo de 18 trillones.

**2. Sí necesitas ambas `&mut` simultáneas** (por ejemplo, para pasarlas a `fn mover(a: &mut Cuenta, b: &mut Cuenta)`). Desde Rust 1.86 el slice tiene `get_disjoint_mut`, que comprueba en tiempo de ejecución que los índices no se solapan:

```rust
let [origen, destino] = cuentas
    .get_disjoint_mut([desde, hacia])
    .map_err(|_| ErrorTransferencia::IndiceInvalido)?;
```

Devuelve `Err` tanto si un índice está fuera de rango como si `desde == hacia`, así que cubre las dos validaciones de golpe. Si tu toolchain es anterior a 1.86, la alternativa es `split_at_mut`:

```rust
let (menor, mayor) = (desde.min(hacia), desde.max(hacia));
let (izq, der) = cuentas.split_at_mut(mayor);
let (a, b) = (&mut izq[menor], &mut der[0]);
let (origen, destino) = if desde < hacia { (a, b) } else { (b, a) };
```

Funciona porque `split_at_mut` entrega dos slices disjuntos y el compilador sí sabe que no se solapan.

Prueba mínima de los casos que el original ignoraba:

```rust
#[test]
fn rechaza_misma_cuenta_y_saldo_insuficiente() {
    let mut cuentas = vec![Cuenta { id: 1, saldo: 50 }, Cuenta { id: 2, saldo: 0 }];
    assert_eq!(transferir(&mut cuentas, 0, 0, 10), Err(ErrorTransferencia::MismaCuenta));
    assert_eq!(transferir(&mut cuentas, 0, 1, 80), Err(ErrorTransferencia::SaldoInsuficiente));
    assert_eq!(transferir(&mut cuentas, 0, 1, 30), Ok(()));
    assert_eq!((cuentas[0].saldo, cuentas[1].saldo), (20, 30));
}
```""",
            },
        ]
    },
    # 4) E0597 + multiturno
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Leo líneas de stdin y quiero guardarlas recortadas en un vector, pero:

```rust
fn main() {
    let mut partes: Vec<&str> = Vec::new();
    for linea in std::io::stdin().lines() {
        let linea = linea.unwrap();
        partes.push(linea.trim());
    }
    println!("{partes:?}");
}
```

```
error[E0597]: `linea` does not live long enough
 --> src/main.rs:5:21
  |
4 |         let linea = linea.unwrap();
  |             ----- binding `linea` declared here
5 |         partes.push(linea.trim());
  |                     ^^^^^ borrowed value does not live long enough
6 |     }
  |     - `linea` dropped here while still borrowed
7 |     println!("{partes:?}");
  |               -------- borrow later used here
```""",
            },
            {
                "role": "assistant",
                "content": r"""`linea.trim()` devuelve un `&str` que apunta **dentro** del `String` `linea`, y ese `String` se libera al terminar cada vuelta del bucle (línea 6 del mensaje: «dropped here while still borrowed»). Guardar en `partes` una referencia a algo que ya no existe es justo lo que el compilador impide.

La solución directa es que el vector sea dueño de sus cadenas:

```rust
use std::io::{self, BufRead};

fn main() -> io::Result<()> {
    let mut partes: Vec<String> = Vec::new();
    for linea in io::stdin().lock().lines() {
        let linea = linea?;
        partes.push(linea.trim().to_owned());
    }
    println!("{partes:?}");
    Ok(())
}
```

Cambios:

- `Vec<String>` en vez de `Vec<&str>`: cada elemento posee su memoria, no depende de la variable del bucle.
- `trim().to_owned()` crea ese `String` recortado.
- `stdin().lock()` evita tomar el candado de stdin en cada línea, y `?` con `main() -> io::Result<()>` sustituye al `unwrap()`.

Regla general: una colección de `&T` solo puede vivir mientras viva el dueño de esos `T`. Si el dueño es una variable local del bucle, la colección no puede sobrevivirla.""",
            },
            {
                "role": "user",
                "content": "Vale, pero eso copia cada línea dos veces (la de `lines()` y la de `to_owned()`). Son ficheros grandes, ¿se puede evitar?",
            },
            {
                "role": "assistant",
                "content": r"""Sí: cambia quién es el dueño. En vez de un `String` por línea, lee **todo el contenido en un solo `String`** y guarda `&str` que apunten dentro de él. `trim()` entonces no copia nada, solo ajusta el rango; haces una asignación grande en lugar de 2N pequeñas.

```rust
use std::io::{self, Read};

fn partir_recortando(contenido: &str) -> Vec<&str> {
    contenido.lines().map(str::trim).collect()
}

fn main() -> io::Result<()> {
    let mut contenido = String::new();
    io::stdin().lock().read_to_string(&mut contenido)?;

    let partes = partir_recortando(&contenido);
    println!("{} líneas, primera: {:?}", partes.len(), partes.first());
    Ok(())
}
```

Aquí `partes: Vec<&str>` vive ligado a `contenido`; el compilador lo infiere por la regla de elisión (un solo parámetro con referencia → la salida toma su lifetime). Mientras `contenido` exista, las referencias son válidas; si intentas devolver `partes` de una función donde `contenido` es local, vuelves al E0597, que es correcto.

Coste de memoria: el mismo que antes en el peor caso (todo el fichero en memoria), pero sin la sobrecarga de N cabeceras de `String` ni de N asignaciones.

Lo que no soluciona: si el fichero **no cabe en memoria**, tampoco cabía tu `Vec<String>`. En ese caso el diseño correcto es no guardar las líneas, sino procesarlas al vuelo:

```rust
for linea in io::stdin().lock().lines() {
    let linea = linea?;
    procesar(linea.trim());
}
```

Una copia por línea, memoria constante. Guarda solo lo que de verdad necesitas conservar después (un contador, un agregado, las pocas líneas que cumplen una condición).""",
            },
        ]
    },
    # 5) Lifetimes para principiante
    {
        "messages": [
            {
                "role": "user",
                "content": "No entiendo qué significa el `'a` en `fn longest<'a>(x: &'a str, y: &'a str) -> &'a str`. ¿Es como decirle al compilador cuánto dura la variable?",
            },
            {
                "role": "assistant",
                "content": r"""No. `'a` no fija ninguna duración: es una **relación** entre las referencias de entrada y la de salida. Dice: «la referencia que devuelvo no vive más que `x` ni más que `y`». El compilador ya sabe cuánto vive cada cosa; lo que no puede adivinar en una firma es *de cuál de los argumentos sale* el resultado.

Quítalo y mira el error:

```
error[E0106]: missing lifetime specifier
 --> src/main.rs:1:33
  |
1 | fn longest(x: &str, y: &str) -> &str {
  |               ----     ----     ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `x` or `y`
```

Con `'a` en los tres sitios, al llamar `longest(&a, &b)` el compilador toma como `'a` la **intersección**: el resultado solo es válido mientras vivan las dos. Por eso esto falla, y debe fallar:

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let a = String::from("larga");
    let resultado;
    {
        let b = String::from("x");
        resultado = longest(&a, &b); // error[E0597]: `b` does not live long enough
    }
    println!("{resultado}");
}
```

`resultado` podría apuntar a `b`, y `b` muere antes del `println!`.

**Cuándo lo escribes y cuándo no.** El compilador aplica tres reglas de elisión y solo te pide anotar cuando no bastan:

1. Cada referencia de entrada recibe su propio lifetime.
2. Si hay **exactamente una** referencia de entrada, la salida la hereda: `fn first_word(s: &str) -> &str` no necesita `'a`.
3. Si hay `&self` o `&mut self`, la salida hereda la de `self`.

`longest` tiene dos entradas y ninguna es `self`: la regla 2 no aplica, de ahí el E0106.

Si el resultado sale **solo de uno** de los argumentos, anota solo ese, y el otro queda libre:

```rust
fn elegir<'a>(preferido: &'a str, _alternativo: &str) -> &'a str {
    preferido
}
```

Así el llamador puede pasar un `_alternativo` de vida corta sin restringir el resultado.

El otro sitio donde aparece es en structs que guardan referencias; ahí significa «este struct no puede vivir más que el texto que referencia»:

```rust
struct Lector<'a> {
    fuente: &'a str,
}
```

Resumen en una frase: `'a` nunca alarga nada; solo le cuenta al compilador qué referencia depende de cuál para que pueda rechazar los usos después de que el dueño muera.""",
            },
        ]
    },
    # 6) Option/Result y `?`. System exacto, multiturno
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Tengo esta función para leer el puerto y me parece muy anidada, ¿cómo se simplifica en Rust idiomático?

```rust
fn puerto() -> Result<u16, String> {
    match std::env::var("PORT") {
        Ok(valor) => match valor.parse::<u16>() {
            Ok(p) => Ok(p),
            Err(e) => Err(format!("PORT inválido: {e}")),
        },
        Err(_) => Ok(8080),
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Dos herramientas quitan los dos niveles: `let else` para el caso «si no está, valor por defecto» y `map_err` para convertir el error sin un `match`.

```rust
fn puerto() -> Result<u16, String> {
    let Ok(valor) = std::env::var("PORT") else {
        return Ok(8080);
    };
    valor
        .parse::<u16>()
        .map_err(|e| format!("PORT inválido ({valor:?}): {e}"))
}
```

Qué hace cada pieza:

- `let Ok(valor) = expr else { return ... }` (estable desde 1.65) desestructura o sale; evita el `match` externo cuando una rama es un retorno temprano.
- `map_err` transforma el `Err` de `parse` en tu `String` y deja pasar el `Ok` sin tocarlo. He añadido el valor recibido al mensaje porque «invalid digit found in string» sin saber qué cadena era no ayuda a nadie.

Un detalle que tu versión escondía: `env::var` falla por dos motivos distintos, `NotPresent` y `NotUnicode`. Tratar ambos como «usa 8080» es defendible para una variable opcional, pero conviene decidirlo a propósito. Si quieres distinguirlos:

```rust
use std::env::VarError;

fn puerto() -> Result<u16, String> {
    let valor = match std::env::var("PORT") {
        Ok(v) => v,
        Err(VarError::NotPresent) => return Ok(8080),
        Err(VarError::NotUnicode(_)) => return Err("PORT no es UTF-8 válido".into()),
    };
    valor
        .parse::<u16>()
        .map_err(|e| format!("PORT inválido ({valor:?}): {e}"))
}
```

Y si la función vive en un programa con más errores de este estilo, `String` como tipo de error se queda corto pronto: con `?` y un tipo de error propio (o `anyhow::Result` en un binario) la conversión es automática porque `?` llama a `From::from` sobre el error:

```rust
fn puerto() -> anyhow::Result<u16> {
    let Ok(valor) = std::env::var("PORT") else {
        return Ok(8080);
    };
    let p: u16 = valor.parse()?; // ParseIntError -> anyhow::Error vía From
    Ok(p)
}
```

Prueba rápida de las tres ramas:

```rust
#[test]
fn puerto_por_defecto_valido_e_invalido() {
    std::env::remove_var("PORT");
    assert_eq!(puerto(), Ok(8080));
    std::env::set_var("PORT", "9000");
    assert_eq!(puerto(), Ok(9000));
    std::env::set_var("PORT", "abc");
    assert!(puerto().unwrap_err().contains("PORT inválido"));
}
```

(Los tests de Rust corren en paralelo y comparten el entorno del proceso; si tienes varios tests que tocan `PORT`, ejecútalos con `--test-threads=1` o inyecta el valor como parámetro en vez de leer `env` dentro de la función. En edition 2024 `set_var` y `remove_var` son `unsafe` precisamente por esto, y tendrías que envolverlas en `unsafe { }`.)""",
            },
            {
                "role": "user",
                "content": "¿Y puedo usar `?` con un `Option` dentro de una función que devuelve `Result`? Me da un error raro.",
            },
            {
                "role": "assistant",
                "content": r"""No directamente. `?` sobre un `Option` solo funciona en una función que devuelve `Option`; en una que devuelve `Result` el compilador no sabe qué error fabricar a partir de `None`. El error que ves es este:

```
error[E0277]: the `?` operator can only be used on `Result`s, not `Option`s, in a function that returns `Result`
```

Conviértelo antes con `ok_or` (error fijo) u `ok_or_else` (error calculado, evita construirlo si no hace falta):

```rust
fn primer_argumento() -> Result<String, String> {
    let arg = std::env::args().nth(1).ok_or("falta el argumento")?;
    Ok(arg)
}

fn buscar(id: u32, tabla: &std::collections::HashMap<u32, String>) -> anyhow::Result<&String> {
    tabla
        .get(&id)
        .ok_or_else(|| anyhow::anyhow!("no existe el id {id}"))
}
```

En `primer_argumento`, `ok_or("falta el argumento")` produce `Result<String, &str>` y `?` convierte `&str` en `String` porque existe `From<&str> for String`.

El caso inverso también existe: en una función que devuelve `Option`, un `Result` se pasa a `Option` con `.ok()?`, descartando el error. Hazlo solo cuando el motivo del fallo de verdad no importa; si importa, la función debería devolver `Result`.""",
            },
        ]
    },
    # 7) Enums y pattern matching: comandos de un mini servidor
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy haciendo un mini servidor tipo Redis para aprender. Recibo líneas como `SET clave valor`, `GET clave`, `DEL clave` y `QUIT`. Ahora mismo lo parseo con ifs sobre strings y es un lío. ¿Cómo se modela esto bien en Rust?",
            },
            {
                "role": "assistant",
                "content": r"""Modela los comandos como un `enum` con datos y haz el parseo en un `impl FromStr`. El `match` exhaustivo sobre el enum es lo que ordena el resto del programa: cuando añadas un comando, el compilador te señala cada sitio que falta por tratar.

```rust
use std::collections::HashMap;
use std::str::FromStr;

#[derive(Debug, PartialEq, Eq)]
pub enum Comando {
    Set { clave: String, valor: String },
    Get(String),
    Del(String),
    Quit,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ErrorComando {
    Vacio,
    Desconocido(String),
    Aridad { comando: String, recibidos: usize },
}

impl FromStr for Comando {
    type Err = ErrorComando;

    fn from_str(linea: &str) -> Result<Self, Self::Err> {
        let partes: Vec<&str> = linea.split_whitespace().collect();
        match partes.as_slice() {
            [] => Err(ErrorComando::Vacio),
            ["SET", clave, valor] => Ok(Comando::Set {
                clave: clave.to_string(),
                valor: valor.to_string(),
            }),
            ["GET", clave] => Ok(Comando::Get(clave.to_string())),
            ["DEL", clave] => Ok(Comando::Del(clave.to_string())),
            ["QUIT"] => Ok(Comando::Quit),
            [nombre @ ("SET" | "GET" | "DEL" | "QUIT"), ..] => Err(ErrorComando::Aridad {
                comando: nombre.to_string(),
                recibidos: partes.len() - 1,
            }),
            [otro, ..] => Err(ErrorComando::Desconocido(otro.to_string())),
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum Respuesta {
    Ok,
    Valor(Option<String>),
    Eliminado(bool),
    Adios,
}

pub fn ejecutar(almacen: &mut HashMap<String, String>, comando: Comando) -> Respuesta {
    match comando {
        Comando::Set { clave, valor } => {
            almacen.insert(clave, valor);
            Respuesta::Ok
        }
        Comando::Get(clave) => Respuesta::Valor(almacen.get(&clave).cloned()),
        Comando::Del(clave) => Respuesta::Eliminado(almacen.remove(&clave).is_some()),
        Comando::Quit => Respuesta::Adios,
    }
}
```

Decisiones:

- **Patrones de slice** (`["SET", clave, valor]`) sobre `partes.as_slice()`: cada forma válida es una línea, y el orden de los brazos resuelve la aridad incorrecta: si llega `SET solo_clave`, no casa con el brazo de tres elementos y cae en `[nombre @ (...), ..]`, que reconoce el nombre y reporta cuántos argumentos llegaron. `..` dentro del patrón significa «lo que quede».
- **`FromStr`** en vez de una función suelta: te da `"GET x".parse::<Comando>()` gratis y es lo que cualquier lector de Rust espera.
- **`Respuesta` también es un enum.** La capa de red decide cómo serializarla; `ejecutar` no sabe de sockets. Así puedes testear la lógica sin abrir un puerto.
- Los errores llevan datos (`Desconocido(String)`, `Aridad { .. }`) para que el mensaje al cliente sea útil sin formatear dentro del parser.

Tests que fijan el contrato:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parsea_set_y_get() {
        assert_eq!(
            "SET color rojo".parse::<Comando>(),
            Ok(Comando::Set { clave: "color".into(), valor: "rojo".into() })
        );
        assert_eq!("GET color".parse::<Comando>(), Ok(Comando::Get("color".into())));
    }

    #[test]
    fn detecta_aridad_y_desconocidos() {
        assert_eq!(
            "SET color".parse::<Comando>(),
            Err(ErrorComando::Aridad { comando: "SET".into(), recibidos: 1 })
        );
        assert_eq!("FLUSH".parse::<Comando>(), Err(ErrorComando::Desconocido("FLUSH".into())));
        assert_eq!("   ".parse::<Comando>(), Err(ErrorComando::Vacio));
    }

    #[test]
    fn set_get_del_sobre_el_almacen() {
        let mut almacen = HashMap::new();
        ejecutar(&mut almacen, "SET a 1".parse().unwrap());
        assert_eq!(ejecutar(&mut almacen, Comando::Get("a".into())), Respuesta::Valor(Some("1".into())));
        assert_eq!(ejecutar(&mut almacen, Comando::Del("a".into())), Respuesta::Eliminado(true));
        assert_eq!(ejecutar(&mut almacen, Comando::Get("a".into())), Respuesta::Valor(None));
    }
}
```

Límite conocido: `split_whitespace` no permite valores con espacios. Cuando lo necesites, cambia el parser a un formato con longitudes explícitas (como hace el RESP real) y el enum se queda igual; esa es la ventaja de separar sintaxis de semántica.""",
            },
        ]
    },
    # 8) Generics vs dyn Trait. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "I keep going back and forth between `fn run<H: Handler>(h: &H)` and `fn run(h: &dyn Handler)`. When does each one actually matter? I'm building a small plugin system where handlers get registered at startup and dispatched per event.",
            },
            {
                "role": "assistant",
                "content": r"""For your case the answer is `dyn`: a registry filled at startup is a **heterogeneous collection whose concrete types are only known at runtime**, and generics cannot express that. `Vec<Box<dyn Handler>>` can; `Vec<H>` would force every handler to be the same type.

The general rule:

| Need | Use | Why |
|---|---|---|
| Different concrete types in one collection, or chosen at runtime | `dyn Trait` | one vtable per type, one code path |
| Called in a hot loop, want inlining | generics (`T: Trait`) | monomorphized, zero indirection |
| Trait has generic methods or returns `Self` | generics | such methods are not dyn-compatible |
| Public API, want small binaries and fast builds | `dyn` | no code duplication per type |
| Closed set of implementations you control | `enum` | exhaustive `match`, no boxing |

The dispatch cost of `dyn` is a pointer load and an indirect call; the cost of generics is a copy of the function per type. For a plugin registry, handler work dwarfs either.

```rust
pub struct Event {
    pub kind: String,
    pub payload: Vec<u8>,
}

#[derive(Debug)]
pub struct HandlerError(pub String);

pub trait Handler: Send + Sync {
    fn name(&self) -> &str;
    fn handle(&self, event: &Event) -> Result<(), HandlerError>;
}

#[derive(Default)]
pub struct Registry {
    handlers: Vec<Box<dyn Handler>>,
}

impl Registry {
    /// `impl Handler + 'static` here is sugar for a generic parameter: the caller passes a
    /// concrete type, and we erase it into a `Box<dyn Handler>` exactly once, at registration.
    pub fn register(&mut self, handler: impl Handler + 'static) {
        self.handlers.push(Box::new(handler));
    }

    /// Returns the name of every handler that failed, with its error.
    pub fn dispatch(&self, event: &Event) -> Vec<(String, HandlerError)> {
        self.handlers
            .iter()
            .filter_map(|h| h.handle(event).err().map(|e| (h.name().to_owned(), e)))
            .collect()
    }
}
```

`Send + Sync` as supertraits let the registry live in an `Arc` shared across threads; without them a `Box<dyn Handler>` is assumed single-threaded.

**Dyn compatibility.** A trait can only be used as `dyn Trait` if every method is callable through a vtable. This fails:

```rust
pub trait Handler {
    fn handle(&self, event: &Event) -> Result<(), HandlerError>;
    fn with_filter<F: Fn(&Event) -> bool>(self, f: F) -> Filtered<Self, F>; // generic + returns Self-ish
}
```

```
error[E0038]: the trait `Handler` is not dyn compatible
```

Fix: exclude the offending method from the vtable with `where Self: Sized`. It stays available on concrete types and disappears from `dyn Handler`:

```rust
fn with_filter<F: Fn(&Event) -> bool>(self, f: F) -> Filtered<Self, F>
where
    Self: Sized,
{
    Filtered { inner: self, pred: f }
}
```

Same trick for a `fn new() -> Self` constructor.

**Mixing both** is normal: the registry is `dyn`, while small hot helpers stay generic:

```rust
fn matches_any<P: Fn(&Event) -> bool>(events: &[Event], pred: P) -> bool {
    events.iter().any(pred)
}
```

Two clarifications that often cause the back-and-forth:

- `fn run(h: impl Handler)` and `fn run<H: Handler>(h: H)` are the same thing; `impl Trait` in argument position is a generic.
- `&dyn Handler` vs `Box<dyn Handler>` is an ownership question, not a dispatch one. The registry owns, so it boxes; a function that only inspects takes `&dyn Handler`.

One-line rule: **generic when the caller knows the type, `dyn` when the type is decided at runtime or must sit next to other types.**""",
            },
        ]
    },
    # 9) Iteradores + closures; multiturno con E0373
    {
        "messages": [
            {
                "role": "user",
                "content": r"""¿Cómo escribirías esto con iteradores? Me dicen que es muy "C" pero no veo cómo encadenarlo.

```rust
let mut total = 0.0;
for s in &lineas {
    if let Ok(p) = s.trim().parse::<f64>() {
        if p > 0.0 {
            total += p;
        }
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cada `if` es un adaptador: el `parse` que puede fallar es `filter_map`, la condición es `filter`, el acumulador es `sum`.

```rust
let total: f64 = lineas
    .iter()
    .filter_map(|s| s.trim().parse::<f64>().ok())
    .filter(|&p| p > 0.0)
    .sum();
```

- `filter_map` aplica la closure y se queda con los `Some`; `.ok()` convierte `Result<f64, _>` en `Option<f64>` tirando el error, que es exactamente lo que hacía tu `if let Ok(p)`.
- `filter(|&p| p > 0.0)`: el patrón `&p` desreferencia porque `filter` entrega `&f64`.
- `sum()` necesita saber el tipo del resultado; de ahí `let total: f64`.

Es igual de rápido que el bucle: los adaptadores son perezosos y se fusionan en un solo recorrido; no hay colecciones intermedias.

Un cambio semántico que vale la pena plantearse: tu versión **ignora en silencio** las líneas que no son números. Si prefieres que un dato corrupto detenga el cálculo, recoge en `Result`:

```rust
fn total_positivo(lineas: &[String]) -> Result<f64, std::num::ParseFloatError> {
    let valores = lineas
        .iter()
        .map(|s| s.trim().parse::<f64>())
        .collect::<Result<Vec<f64>, _>>()?;
    Ok(valores.into_iter().filter(|&p| p > 0.0).sum())
}
```

`collect` en un `Result<Vec<_>, _>` se detiene en el primer `Err` y lo devuelve; `?` lo propaga. Elige una de las dos según lo que signifique una línea inválida en tu dominio, pero elígelo a propósito.""",
            },
            {
                "role": "user",
                "content": r"""Perfecto. Ahora quería hacer la suma en otro hilo porque son muchas líneas y me sale esto:

```
error[E0373]: closure may outlive the current function, but it borrows `lineas`, which is owned by the current function
  --> src/main.rs:9:33
   |
9  |     let manejador = thread::spawn(|| {
   |                                   ^^ may outlive borrowed value `lineas`
10 |         lineas.iter().filter_map(|s| s.trim().parse::<f64>().ok()).sum::<f64>()
   |         ------ `lineas` is borrowed here
   |
note: function requires argument type to outlive `'static`
help: to force the closure to take ownership of `lineas` (and any other referenced variables), use the `move` keyword
```""",
            },
            {
                "role": "assistant",
                "content": r"""`thread::spawn` exige que la closure sea `'static`: el hilo nuevo puede seguir corriendo después de que termine la función que lo creó, así que no puede tener préstamos a variables locales de esa función. Tienes dos salidas y dependen de si necesitas `lineas` después.

**1. Si el hilo puede quedarse con el vector**, usa `move`, como sugiere el compilador. La propiedad pasa a la closure y `lineas` deja de existir en el hilo principal:

```rust
use std::thread;

let manejador = thread::spawn(move || {
    lineas
        .iter()
        .filter_map(|s| s.trim().parse::<f64>().ok())
        .sum::<f64>()
});
let total = manejador.join().expect("el hilo de suma hizo panic");
```

**2. Si quieres seguir usando `lineas` en el hilo principal**, usa hilos con ámbito (`thread::scope`, estable desde 1.63). El ámbito garantiza que todos los hilos terminan antes de salir del bloque, así que pueden tomar préstamos normales:

```rust
let total = thread::scope(|s| {
    let mitad = lineas.len() / 2;
    let (izq, der) = lineas.split_at(mitad);
    let sumar = |parte: &[String]| -> f64 {
        parte.iter().filter_map(|l| l.trim().parse::<f64>().ok()).sum()
    };
    let h = s.spawn(|| sumar(der));
    sumar(izq) + h.join().expect("el hilo de suma hizo panic")
});
println!("{total} (y sigo teniendo {} líneas)", lineas.len());
```

Aquí además divides el trabajo: el hilo principal suma una mitad mientras el otro suma la otra, que es la única razón por la que compensa un hilo para una suma.

Una advertencia sobre el rendimiento: parsear y sumar es tan barato que crear un hilo (decenas de microsegundos) solo se amortiza con millones de líneas. Mide antes con `--release`; si el cuello de botella es leer el fichero, el hilo no ayuda.""",
            },
        ]
    },
    # 10) Colecciones: HashMap/entry, comparado con Python. System variante
    {
        "messages": [
            {"role": "system", "content": "Explica como a alguien que viene de Python, con comparaciones cortas entre ambos lenguajes."},
            {
                "role": "user",
                "content": "Contar palabras con HashMap en Rust me parece verboso comparado con Counter o defaultdict. ¿Cómo se hace bien y qué equivale a cada cosa?",
            },
            {
                "role": "assistant",
                "content": r"""La pieza que te falta es la **API `entry`**: hace en una línea lo que `defaultdict(int)` hace implícitamente.

```rust
use std::collections::HashMap;

fn contar_palabras(texto: &str) -> HashMap<&str, usize> {
    let mut conteo = HashMap::new();
    for palabra in texto.split_whitespace() {
        *conteo.entry(palabra).or_insert(0) += 1;
    }
    conteo
}
```

`entry(palabra)` busca la clave; `or_insert(0)` devuelve una `&mut usize` al valor existente o al 0 recién insertado; `*… += 1` incrementa. Una sola búsqueda de hash por palabra, igual que `Counter`.

Fíjate en el tipo: `HashMap<&str, usize>`. Las claves son **préstamos del texto**, no copias; el mapa vive mientras viva `texto`. Si necesitas que el mapa sobreviva al texto, usa `HashMap<String, usize>` y `entry(palabra.to_owned())`.

Equivalencias:

| Python | Rust | Nota |
|---|---|---|
| `d[k] += 1` con `defaultdict(int)` | `*m.entry(k).or_insert(0) += 1` | o `or_default()` para el `Default` del tipo |
| `d.setdefault(k, []).append(x)` | `m.entry(k).or_default().push(x)` | `Vec::default()` es un vector vacío |
| `d.get(k, 0)` | `m.get(&k).copied().unwrap_or(0)` | `get` devuelve `Option<&V>` |
| `k in d` | `m.contains_key(&k)` | |
| `Counter(xs).most_common(1)` | `m.iter().max_by_key(\|(_, &n)\| n)` | devuelve `Option<(&K, &V)>` |
| `dict` ordenado por clave | `BTreeMap` | `HashMap` no tiene orden |
| `set` | `HashSet` / `BTreeSet` | |
| `collections.deque` | `VecDeque` | `push_front`/`pop_front` O(1) |

Dos diferencias que sorprenden viniendo de Python:

1. **`HashMap` no conserva orden de inserción** (los dicts de Python sí desde 3.7) y además el orden cambia entre ejecuciones porque la semilla del hash es aleatoria. Si necesitas orden por clave, `BTreeMap`; si necesitas orden de inserción, la crate `indexmap`.
2. **Hay que decidir quién posee la clave.** En Python todo son referencias compartidas; en Rust `&str` presta y `String` posee, y el tipo del mapa lo deja escrito.

Para sacar las N más frecuentes, que en `Counter` es `most_common(n)`:

```rust
fn mas_frecuentes<'a>(conteo: &HashMap<&'a str, usize>, n: usize) -> Vec<(&'a str, usize)> {
    let mut pares: Vec<(&str, usize)> = conteo.iter().map(|(&p, &c)| (p, c)).collect();
    pares.sort_unstable_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    pares.truncate(n);
    pares
}
```

El `.then(a.0.cmp(b.0))` desempata alfabéticamente para que el resultado sea determinista (recuerda: el orden de iteración del `HashMap` no lo es).

Prueba:

```rust
#[test]
fn cuenta_y_ordena() {
    let c = contar_palabras("a b a c b a");
    assert_eq!(c["a"], 3);
    assert_eq!(mas_frecuentes(&c, 2), vec![("a", 3), ("b", 2)]);
}
```""",
            },
        ]
    },
    # 11) String vs &str; multiturno con panic de char boundary
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Por qué Rust tiene `String` y `&str`? ¿Cuál uso en los parámetros de mis funciones?",
            },
            {
                "role": "assistant",
                "content": r"""Son el mismo contenido (UTF-8) con distinto dueño:

- `String`: **posee** su memoria en el heap. Puede crecer (`push_str`), se libera cuando sale de ámbito, se mueve al pasarla por valor.
- `&str`: **presta** una vista a texto que pertenece a otro: a un `String`, a un literal (`"hola"` es `&'static str`, vive en el binario), o a un trozo de otro `&str`.

En parámetros, la regla práctica es: **pide `&str` cuando solo lees; pide `String` cuando te lo vas a quedar.**

```rust
// Solo lee: acepta &String, &str, literales y slices sin que el llamador copie nada.
fn es_saludo(texto: &str) -> bool {
    texto.starts_with("hola")
}

// Se lo queda (lo guarda en un struct): pide la propiedad y evita un clone interno.
struct Usuario {
    nombre: String,
}

impl Usuario {
    fn nuevo(nombre: String) -> Self {
        Usuario { nombre }
    }
}

fn main() {
    let propio = String::from("hola mundo");
    assert!(es_saludo(&propio)); // &String se convierte en &str automáticamente (deref coercion)
    assert!(es_saludo("hola"));

    let u = Usuario::nuevo(propio); // propio se mueve; ya no se puede usar
    println!("{}", u.nombre);
}
```

Si `Usuario::nuevo` pidiera `&str`, tendría que hacer `nombre.to_owned()` dentro, y un llamador que ya tenía un `String` pagaría una copia innecesaria. Pedir `String` deja la decisión fuera: quien tiene un `String` lo mueve gratis; quien tiene un `&str` llama `.to_owned()` sabiendo que copia.

Conversiones que usarás cada día:

| De | A | Cómo |
|---|---|---|
| `&str` | `String` | `s.to_owned()`, `s.to_string()`, `String::from(s)` (equivalentes) |
| `String` | `&str` | `&s`, `s.as_str()` |
| `String` | trozo | `&s[inicio..fin]` (índices en **bytes**, ver abajo) |
| varias partes | `String` | `format!("{a}-{b}")` |

Dos señales de que algo va mal: `&String` en un parámetro (clippy lo marca; `&str` es estrictamente más general) y `.clone()` «para que compile» en un sitio donde un préstamo bastaría.""",
            },
            {
                "role": "user",
                "content": r"""Hice `&nombre[0..1]` para sacar la inicial y me peta con:

```
thread 'main' panicked at src/main.rs:4:20:
byte index 1 is not a char boundary; it is inside 'Á' (bytes 0..2) of `Álvaro`
```""",
            },
            {
                "role": "assistant",
                "content": r"""Los índices de `&s[a..b]` son **bytes**, no caracteres, y `Á` ocupa dos bytes en UTF-8 (`C3 81`). Cortar en el byte 1 parte el carácter por la mitad, y Rust prefiere hacer *panic* a entregarte un `&str` inválido.

Para la inicial, trabaja con `chars()`:

```rust
fn inicial(nombre: &str) -> Option<char> {
    nombre.chars().next()
}

fn main() {
    assert_eq!(inicial("Álvaro"), Some('Á'));
    assert_eq!(inicial(""), None);
}
```

Devuelve `Option<char>` porque la cadena vacía no tiene inicial; esconder ese caso con `unwrap` es el siguiente *panic*.

Si necesitas los primeros N caracteres como `&str` (sin copiar), calcula el límite en bytes con `char_indices`:

```rust
fn primeros(texto: &str, n: usize) -> &str {
    match texto.char_indices().nth(n) {
        Some((fin, _)) => &texto[..fin],
        None => texto, // tiene n caracteres o menos
    }
}

assert_eq!(primeros("Álvaro", 2), "Ál");
assert_eq!(primeros("ab", 5), "ab");
```

`char_indices().nth(n)` devuelve el byte donde empieza el carácter n+1, que es justo donde hay que cortar; si no existe, la cadena entera es la respuesta.

Tres cosas que conviene tener claras:

- `s.len()` es bytes. Para contar caracteres, `s.chars().count()` (O(n)).
- Un `char` es un *scalar value* Unicode, no un «carácter visible»: `"é"` puede ser un solo `char` (U+00E9) o dos (`e` + acento combinante U+0301). Si eso te importa (truncar texto de usuarios para mostrarlo), usa la crate `unicode-segmentation` y sus *grapheme clusters*.
- Para comprobar si un índice es válido antes de cortar: `s.is_char_boundary(i)`; `s.get(a..b)` devuelve `Option<&str>` en vez de hacer *panic*.""",
            },
        ]
    },
    # 12) thiserror en la librería, anyhow en el binario. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy escribiendo una librería para cargar ficheros de configuración TOML y una CLI que la usa. He visto `thiserror` y `anyhow` y no tengo claro cuál va dónde ni cómo se combinan.",
            },
            {
                "role": "assistant",
                "content": r"""`thiserror` en la librería, `anyhow` en el binario. La librería expone un **tipo de error con variantes** para que quien la use pueda distinguir casos con `match`; el binario solo quiere **propagar con contexto** y mostrar una cadena de causas legible al final.

**Librería (`config/src/lib.rs`)**, con `thiserror = "2"` y `toml = "0.8"`:

```rust
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("no se pudo leer {ruta}")]
    Io {
        ruta: PathBuf,
        #[source]
        origen: std::io::Error,
    },
    #[error("sintaxis TOML inválida en {ruta}")]
    Sintaxis {
        ruta: PathBuf,
        #[source]
        origen: toml::de::Error,
    },
    #[error("falta el campo obligatorio `{0}`")]
    CampoFaltante(&'static str),
    #[error("el puerto debe estar entre 1 y 65535, se recibió {0}")]
    PuertoInvalido(i64),
}

#[derive(Debug, PartialEq, Eq)]
pub struct Config {
    pub puerto: u16,
}

pub fn cargar(ruta: &Path) -> Result<Config, ConfigError> {
    let texto = std::fs::read_to_string(ruta).map_err(|origen| ConfigError::Io {
        ruta: ruta.to_path_buf(),
        origen,
    })?;
    let bruto: toml::Value = toml::from_str(&texto).map_err(|origen| ConfigError::Sintaxis {
        ruta: ruta.to_path_buf(),
        origen,
    })?;
    let puerto = bruto
        .get("puerto")
        .and_then(toml::Value::as_integer)
        .ok_or(ConfigError::CampoFaltante("puerto"))?;
    let puerto = u16::try_from(puerto)
        .ok()
        .filter(|p| *p > 0)
        .ok_or(ConfigError::PuertoInvalido(puerto))?;
    Ok(Config { puerto })
}
```

Por qué así:

- `#[error("…")]` genera `Display`; `#[source]` encadena la causa para que `Error::source()` la devuelva. Uso `#[source]` con un campo extra (`ruta`) en vez de `#[from]`: `#[from]` solo sirve cuando la variante contiene únicamente el error original, y un `io::Error` sin la ruta del fichero es inútil para el usuario.
- Las variantes son **datos**, no texto: la CLI puede tratar `CampoFaltante` distinto de `Io` sin parsear mensajes.
- `thiserror` no aparece en la API pública: el usuario de la librería solo ve un enum que implementa `std::error::Error`.

**Binario (`cli/src/main.rs`)**, con `anyhow = "1"`:

```rust
use std::path::Path;

use anyhow::{Context, Result};

fn main() -> Result<()> {
    let ruta = std::env::args()
        .nth(1)
        .context("uso: miapp <config.toml>")?;
    let config = config::cargar(Path::new(&ruta))
        .with_context(|| format!("cargando la configuración desde {ruta}"))?;
    println!("escuchando en el puerto {}", config.puerto);
    Ok(())
}
```

- `?` convierte cualquier `E: std::error::Error + Send + Sync + 'static` en `anyhow::Error`, de ahí que `ConfigError` pase sin adaptadores.
- `.context()` toma un valor fijo; `.with_context(|| …)` toma una closure y solo formatea si hay error, así no pagas el `format!` en el camino feliz.
- Cuando `main` devuelve `Err`, Rust imprime la cadena entera. Con un fichero inexistente:

```
Error: cargando la configuración desde app.toml

Caused by:
    0: no se pudo leer app.toml
    1: No such file or directory (os error 2)
```

Para imprimirla tú mismo en una sola línea, `format!("{err:#}")` usa el modo alternativo: `cargando la configuración desde app.toml: no se pudo leer app.toml: No such file or directory (os error 2)`.

**Qué no hacer:** `anyhow` dentro de la librería. Obligarías a tus usuarios a inspeccionar errores con `downcast_ref`, que es frágil y no aparece en la firma. Y al revés, un enum de `thiserror` en un binario con treinta variantes que nadie va a hacer `match` es trabajo sin retorno.

Test de la librería que fija las variantes:

```rust
#[test]
fn distingue_variantes() {
    let dir = std::env::temp_dir();
    let ruta = dir.join("sin_puerto.toml");
    std::fs::write(&ruta, "nombre = \"x\"\n").unwrap();
    assert!(matches!(cargar(&ruta), Err(ConfigError::CampoFaltante("puerto"))));

    let ruta = dir.join("puerto_malo.toml");
    std::fs::write(&ruta, "puerto = 70000\n").unwrap();
    assert!(matches!(cargar(&ruta), Err(ConfigError::PuertoInvalido(70000))));
}
```""",
            },
        ]
    },
    # 13) Módulos y workspaces de cargo; multiturno con visibilidad
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi proyecto Rust ya tiene 40 ficheros en un solo crate y compilar tarda. Quiero separarlo en core, api (HTTP) y cli. ¿Cómo se organiza un workspace y cómo mapeo módulos a ficheros sin liarme con mod.rs?",
            },
            {
                "role": "assistant",
                "content": r"""Un workspace es un `Cargo.toml` raíz sin `[package]` que lista los crates miembros; comparten `Cargo.lock`, `target/` y, si quieres, versiones de dependencias. Estructura objetivo:

```
inventario/
├── Cargo.toml              # workspace
├── Cargo.lock
└── crates/
    ├── core/               # inventario-core: dominio, sin I/O
    │   ├── Cargo.toml
    │   └── src/
    │       ├── lib.rs
    │       ├── modelo.rs
    │       ├── modelo/
    │       │   ├── articulo.rs
    │       │   └── almacen.rs
    │       └── repositorio.rs
    ├── api/                # inventario-api: HTTP, depende de core
    └── cli/                # inventario-cli: binario, depende de core
```

**`Cargo.toml` raíz:**

```toml
[workspace]
resolver = "2"
members = ["crates/core", "crates/api", "crates/cli"]

[workspace.package]
version = "0.4.0"
edition = "2021"
license = "MIT"
rust-version = "1.80"

[workspace.dependencies]
inventario-core = { path = "crates/core" }
serde = { version = "1", features = ["derive"] }
thiserror = "2"
tokio = { version = "1", features = ["rt-multi-thread", "macros"] }
```

**`crates/core/Cargo.toml`:**

```toml
[package]
name = "inventario-core"
version.workspace = true
edition.workspace = true
license.workspace = true
rust-version.workspace = true

[dependencies]
serde = { workspace = true }
thiserror = { workspace = true }
```

**`crates/cli/Cargo.toml`:**

```toml
[package]
name = "inventario-cli"
version.workspace = true
edition.workspace = true

[[bin]]
name = "inventario"
path = "src/main.rs"

[dependencies]
inventario-core = { workspace = true }
tokio = { workspace = true }
```

`[workspace.dependencies]` fija cada versión en un único sitio; los miembros escriben `{ workspace = true }` y pueden añadir `features` propias. Si un crate necesita `tokio` con `fs`, pone `tokio = { workspace = true, features = ["fs"] }`.

**Módulos y ficheros.** Las dos convenciones válidas:

- Antigua: `src/modelo/mod.rs` + `src/modelo/articulo.rs`.
- Actual (desde 2018, la que recomiendo): `src/modelo.rs` + `src/modelo/articulo.rs`. El fichero `modelo.rs` declara sus hijos y no tienes diez pestañas llamadas `mod.rs`.

```rust
// crates/core/src/lib.rs
pub mod modelo;
pub mod repositorio;

// Re-exportaciones: la API pública del crate es plana aunque la estructura interna no lo sea.
pub use modelo::{Almacen, Articulo};

// crates/core/src/modelo.rs
mod almacen;
mod articulo;

pub use almacen::Almacen;
pub use articulo::Articulo;

// crates/core/src/modelo/articulo.rs
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct Articulo {
    pub sku: String,
    pub stock: u32,
}
```

Con esto, desde `cli` escribes `use inventario_core::Articulo;` (guion a guion bajo en el nombre del crate) y nunca `inventario_core::modelo::articulo::Articulo`. Si mañana reorganizas los ficheros, los usuarios no se enteran.

**Lo que acelera la compilación:** Cargo compila crates en paralelo y recompila solo los afectados. Si tocas `cli`, `core` no se recompila. Para que la separación rinda, `core` no debe depender de `tokio` ni de `axum`: el dominio puro es el crate que más veces reutilizarás en tests y el que menos debería cambiar.

Comandos útiles:

```
cargo build --workspace
cargo test -p inventario-core
cargo run -p inventario-cli -- --help
cargo tree -p inventario-api --depth 1
```""",
            },
            {
                "role": "user",
                "content": "¿Y cómo hago que una función sea visible dentro de `core` para que la use `repositorio`, pero que no salga en la API pública del crate?",
            },
            {
                "role": "assistant",
                "content": r"""Con `pub(crate)`. Es visible en todo el crate `inventario-core` y en ningún otro:

```rust
// crates/core/src/modelo/almacen.rs
pub struct Almacen {
    articulos: Vec<super::Articulo>,
}

impl Almacen {
    /// Pública: forma parte de la API del crate.
    pub fn stock_total(&self) -> u32 {
        self.articulos.iter().map(|a| a.stock).sum()
    }

    /// Solo dentro de inventario-core; `repositorio` puede usarla, `cli` no la ve.
    pub(crate) fn articulos_mut(&mut self) -> &mut Vec<super::Articulo> {
        &mut self.articulos
    }
}
```

Niveles disponibles, de más cerrado a más abierto:

| Visibilidad | Quién la ve |
|---|---|
| (nada) | solo el módulo actual y sus hijos |
| `pub(super)` | el módulo padre y sus descendientes |
| `pub(in crate::modelo)` | un ancestro concreto y sus descendientes |
| `pub(crate)` | todo el crate |
| `pub` | todo el crate y, si la ruta hasta ella es `pub`, otros crates |

Un detalle que suele confundir: `pub` no basta para exportar. Un `pub struct` dentro de un `mod articulo` privado solo es accesible fuera si alguien lo re-exporta (`pub use articulo::Articulo`). La visibilidad efectiva es la del elemento **y** la de cada módulo del camino. Por eso el patrón de `lib.rs` con `pub use` controla exactamente qué sale.

Para comprobar qué expones de verdad, `cargo doc --no-deps -p inventario-core --open` muestra solo lo alcanzable desde fuera; si algo aparece ahí y no debería, le falta un `pub(crate)`.""",
            },
        ]
    },
    # 14) Cargo features. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "My crate optionally supports serde and an async client built on tokio. How should I structure cargo features so people who only want the blocking API don't pull in tokio?",
            },
            {
                "role": "assistant",
                "content": r"""Make each optional dependency an optional dep behind a named feature, keep features **additive**, and gate the async module with `#[cfg(feature = "async")]`.

```toml
[package]
name = "weatherkit"
version = "0.3.0"
edition = "2021"

[features]
default = ["blocking"]
blocking = ["dep:ureq"]
async = ["dep:tokio", "dep:reqwest"]
serde = ["dep:serde"]

[dependencies]
serde = { version = "1", features = ["derive"], optional = true }
ureq = { version = "3", optional = true }
tokio = { version = "1", features = ["rt", "net", "time"], optional = true }
reqwest = { version = "0.12", optional = true }

[package.metadata.docs.rs]
all-features = true
```

Key decisions:

- **`dep:` prefix.** Without it, Cargo creates an implicit feature named after each optional dependency (`tokio`, `reqwest`), and users could enable `reqwest` without the glue code that makes it useful. `dep:tokio` hides the implicit feature; only `async` exists.
- **Additive only.** A feature may only turn code *on*. Never define `no-serde` or a feature that changes the behavior of existing code: Cargo unifies features across the whole dependency graph, so if crate A enables `async` and crate B does not, both get `async`. Anything that breaks B in that situation is a bug in your design.
- **`default` is for the common case.** Someone who wants async only runs `--no-default-features --features async` and never compiles `ureq`.

Gating code:

```rust
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
#[derive(Debug, Clone, PartialEq)]
pub struct Forecast {
    pub city: String,
    pub temp_c: f32,
}

#[cfg(feature = "blocking")]
pub mod blocking {
    use crate::Forecast;

    pub fn fetch(city: &str) -> Result<Forecast, ureq::Error> {
        let url = format!("https://api.example.com/forecast?city={city}");
        let body = ureq::get(&url).call()?.body_mut().read_to_string()?;
        Ok(Forecast { city: city.to_owned(), temp_c: parse_temp(&body) })
    }
}

#[cfg(feature = "async")]
pub mod r#async {
    use crate::Forecast;

    pub async fn fetch(city: &str) -> Result<Forecast, reqwest::Error> {
        let url = format!("https://api.example.com/forecast?city={city}");
        let body = reqwest::get(&url).await?.text().await?;
        Ok(Forecast { city: city.to_owned(), temp_c: parse_temp(&body) })
    }
}

fn parse_temp(body: &str) -> f32 {
    body.trim().parse().unwrap_or(f32::NAN)
}
```

`cfg_attr` applies the derive only when the feature is on, so the struct itself is always available. The module is named `r#async` because `async` is a keyword; `weatherkit::r#async::fetch` is a bit ugly, so many crates call it `aio` or `nonblocking` instead.

**Testing the matrix.** The bug you will ship is a combination you never compiled. Add this to CI:

```
cargo build --no-default-features
cargo build --no-default-features --features async
cargo build --all-features
cargo test --all-features
```

For more than three features, `cargo hack --feature-powerset check` (from the `cargo-hack` tool) builds every combination so a missing `#[cfg]` cannot hide.

**Docs.** The `docs.rs` metadata above builds documentation with every feature so the async API is visible. To show the "Available on crate feature `async` only" badge you need `#![cfg_attr(docsrs, feature(doc_cfg))]` plus `#[cfg_attr(docsrs, doc(cfg(feature = "async")))]` on the module; it is nightly-only, which is fine because docs.rs builds on nightly, and the attribute is a no-op on stable.""",
            },
        ]
    },
    # 15) Revisión de tests y doctests. System variante, usuario trae código
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala lo que falta y da la versión corregida completa."},
            {
                "role": "user",
                "content": r"""Revísame los tests de mi parser de versiones. La función es `fn parse_version(s: &str) -> Result<Version, VersionError>` y `Version { major, minor, patch }`.

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parsea() {
        let r = parse_version("1.2.3").unwrap();
        assert!(r.major == 1);
        assert!(r.minor == 2);
    }

    #[test]
    fn falla_con_basura() {
        parse_version("abc").unwrap();
    }

    #[test]
    #[should_panic]
    fn falla_vacio() {
        parse_version("").unwrap();
    }

    #[test]
    fn imprime() {
        println!("{:?}", parse_version("2.0.0"));
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro problemas, dos de ellos hacen que la suite no pruebe lo que crees:

1. **`falla_con_basura` está roja siempre.** Hace `unwrap()` de un `Err`, así que el test hace *panic* y falla. Quieres afirmar que devuelve error, no provocar un *panic*: `assert!(parse_version("abc").is_err())` o, mejor, comprobar la variante.
2. **`#[should_panic]` sin `expected` pasa con cualquier *panic*.** Si mañana `parse_version("")` hace *panic* por un índice fuera de rango en vez de devolver `Err`, el test sigue verde. Además, tu función devuelve `Result`: probarla vía *panic* es probar `unwrap`, no tu código. Afirma sobre el `Err`.
3. **`imprime` no afirma nada.** Pasa siempre; es ruido. O comprueba el valor o bórralo.
4. **`assert!(a == b)` en vez de `assert_eq!`.** Cuando falle verás «assertion failed: r.major == 1» sin saber qué valor llegó. `assert_eq!` imprime ambos lados. Y falta `patch`.

Versión corregida. Asumo que `VersionError` tiene al menos las variantes `Vacio` y `Formato`; ajusta los nombres a los tuyos.

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parsea_los_tres_numeros() -> Result<(), VersionError> {
        let v = parse_version("1.2.3")?;
        assert_eq!((v.major, v.minor, v.patch), (1, 2, 3));
        Ok(())
    }

    #[test]
    fn rechaza_texto_que_no_es_version() {
        assert!(matches!(parse_version("abc"), Err(VersionError::Formato)));
        assert!(matches!(parse_version("1.2"), Err(VersionError::Formato)));
        assert!(matches!(parse_version("1.2.x"), Err(VersionError::Formato)));
    }

    #[test]
    fn rechaza_cadena_vacia() {
        assert_eq!(parse_version(""), Err(VersionError::Vacio));
    }

    #[test]
    fn ignora_espacios_alrededor() -> Result<(), VersionError> {
        assert_eq!(parse_version(" 2.0.0 ")?, Version { major: 2, minor: 0, patch: 0 });
        Ok(())
    }
}
```

Notas sobre la versión nueva:

- Un test puede devolver `Result`: `?` sustituye a `unwrap()` y, si falla, el informe muestra el error con `Debug` en vez de «called `Result::unwrap()` on an `Err` value».
- `matches!` compara contra un patrón sin exigir `PartialEq` en el error; `assert_eq!` sí lo exige (necesitas `#[derive(Debug, PartialEq)]` en `Version` y `VersionError`, que de todos modos conviene tener).
- Cada test cubre **un** comportamiento y su nombre lo dice; cuando falle `rechaza_cadena_vacia` sabrás qué se rompió sin abrir el fichero.
- Añadí `1.2` y `1.2.x` porque son los errores reales que un parser de versiones comete (aceptar dos componentes, parsear `1` de `1x`). Si alguno no está decidido, decídelo ahora y fíjalo con un test.

Lo que falta fuera del módulo: un **doctest** en la función, que además documenta el uso y se ejecuta con `cargo test`:

```rust
/// Parsea una versión `MAJOR.MINOR.PATCH`.
///
/// ```
/// use miversion::{parse_version, Version};
/// let v = parse_version("1.4.0").unwrap();
/// assert_eq!(v, Version { major: 1, minor: 4, patch: 0 });
/// ```
pub fn parse_version(s: &str) -> Result<Version, VersionError> {
    let s = s.trim();
    if s.is_empty() {
        return Err(VersionError::Vacio);
    }
    let mut partes = s.split('.').map(|p| p.parse::<u32>().map_err(|_| VersionError::Formato));
    let (Some(major), Some(minor), Some(patch), None) =
        (partes.next(), partes.next(), partes.next(), partes.next())
    else {
        return Err(VersionError::Formato);
    };
    Ok(Version { major: major?, minor: minor?, patch: patch? })
}
```

El doctest necesita la ruta del crate (`miversion::`), no `super::`. Para ejecutar solo los doctests: `cargo test --doc`; para ver la salida de un test concreto: `cargo test rechaza_cadena_vacia -- --nocapture`.""",
            },
        ]
    },
    # 16) tokio: MutexGuard de std a través de un .await. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Tengo un contador de peticiones por símbolo en un `Arc<Mutex<HashMap<String, u64>>>` y al meter la llamada HTTP dentro del spawn deja de compilar:

```rust
tokio::spawn(async move {
    let mut contadores = estado.lock().unwrap();
    let precio = obtener_precio(&cliente, &simbolo).await;
    *contadores.entry(simbolo).or_insert(0) += 1;
    registrar(precio);
});
```

```
error: future cannot be sent between threads safely
   --> src/main.rs:14:18
    |
14  |     tokio::spawn(async move {
    |                  ^^^^^^^^^^ future created by async block is not `Send`
    |
    = help: within `{async block@src/main.rs:14:18: 14:28}`, the trait `Send` is not implemented for `std::sync::MutexGuard<'_, HashMap<String, u64>>`
note: future is not `Send` as this value is used across an await
   --> src/main.rs:16:52
    |
15  |         let mut contadores = estado.lock().unwrap();
    |             -------------- has type `std::sync::MutexGuard<'_, HashMap<String, u64>>` which is not `Send`
16  |         let precio = obtener_precio(&cliente, &simbolo).await;
    |                                                        ^^^^^ await occurs here, with `contadores` maybe used later
note: required by a bound in `tokio::spawn`
```

He leído que debería usar `tokio::sync::Mutex`, ¿es eso?""",
            },
            {
                "role": "assistant",
                "content": r"""No. `tokio::sync::Mutex` haría que compile, pero conservaría el defecto real: **mantener un candado mientras esperas a la red**. Durante esos 50-500 ms ninguna otra tarea podría tocar el mapa. El error del compilador te está señalando ese diseño, no una incompatibilidad de tipos.

Lo que pasa: `tokio::spawn` exige un future `Send` porque la tarea puede cambiar de hilo en cada `.await`. `std::sync::MutexGuard` no es `Send` (liberar un candado desde otro hilo es indefinido en muchas plataformas), y como `contadores` sigue vivo después del `.await`, el future lo arrastra.

El arreglo es reordenar para que el candado **no cruce ningún `await`**:

```rust
tokio::spawn(async move {
    let precio = obtener_precio(&cliente, &simbolo).await;
    {
        let mut contadores = estado.lock().unwrap();
        *contadores.entry(simbolo).or_insert(0) += 1;
    } // el guard se suelta aquí, antes de cualquier otro await
    registrar(precio);
});
```

La sección crítica pasa de «una llamada HTTP» a «un incremento»: nanosegundos. Ese es el uso correcto de `std::sync::Mutex` en código async, y el que recomienda la propia documentación de tokio: si la sección crítica es corta y no contiene `await`, el mutex de la biblioteca estándar es más rápido y más simple.

Si el incremento tiene que ir **antes** de la llamada (por ejemplo, para contar intentos y no éxitos), el mismo bloque sirve: abre, incrementa, cierra, y luego `await`:

```rust
tokio::spawn(async move {
    {
        let mut contadores = estado.lock().unwrap();
        *contadores.entry(simbolo.clone()).or_insert(0) += 1;
    }
    let precio = obtener_precio(&cliente, &simbolo).await;
    registrar(precio);
});
```

**Cuándo sí `tokio::sync::Mutex`:** cuando la sección crítica necesita hacer `await` por dentro, por ejemplo proteger una única conexión por la que hay que escribir una petición y leer la respuesta sin que otra tarea se cuele en medio. Es más lento y tiene semántica de cola; se usa solo cuando el recurso protegido es asíncrono.

Dos apuntes:

- `.lock().unwrap()` hace *panic* si otra tarea hizo *panic* con el candado tomado (*poisoning*). Para un contador, el estado sigue siendo válido: `estado.lock().unwrap_or_else(|e| e.into_inner())` lo recupera.
- Si el mapa solo acumula contadores, un `DashMap<String, AtomicU64>` elimina el candado global; pero mide antes: con un incremento por petición HTTP, el `Mutex` no será tu cuello de botella.""",
            },
        ]
    },
    # 17) tokio: mpsc + select + cancelación; multiturno con oneshot
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito procesar trabajos que llegan por un canal con como mucho 4 en paralelo, y que al pulsar Ctrl+C se dejen de aceptar nuevos pero se terminen los que ya están en marcha. ¿Cómo se arma con tokio?",
            },
            {
                "role": "assistant",
                "content": r"""Tres piezas: un `mpsc` acotado para la cola (da *backpressure*), un `Semaphore` para limitar a 4 en vuelo, y un `CancellationToken` para el apagado ordenado. Un `JoinSet` guarda las tareas en marcha para poder esperarlas al final.

`Cargo.toml`:

```toml
[dependencies]
tokio = { version = "1", features = ["rt-multi-thread", "macros", "sync", "signal", "time"] }
tokio-util = "0.7"
```

```rust
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::{mpsc, Semaphore};
use tokio::task::JoinSet;
use tokio_util::sync::CancellationToken;

#[derive(Debug)]
struct Trabajo {
    id: u64,
}

async fn procesar(trabajo: Trabajo) {
    tokio::time::sleep(Duration::from_millis(300)).await;
    println!("terminado {}", trabajo.id);
}

async fn consumidor(mut cola: mpsc::Receiver<Trabajo>, paralelo: usize, cancelar: CancellationToken) {
    let permisos = Arc::new(Semaphore::new(paralelo));
    let mut en_vuelo = JoinSet::new();

    loop {
        tokio::select! {
            _ = cancelar.cancelled() => break,
            siguiente = cola.recv() => {
                let Some(trabajo) = siguiente else { break }; // todos los emisores cerrados
                let permiso = permisos.clone().acquire_owned().await.expect("el semáforo no se cierra");
                en_vuelo.spawn(async move {
                    procesar(trabajo).await;
                    drop(permiso);
                });
            }
        }
    }

    println!("dejando de aceptar; {} trabajos en marcha", en_vuelo.len());
    while let Some(resultado) = en_vuelo.join_next().await {
        if let Err(e) = resultado {
            eprintln!("una tarea falló: {e}");
        }
    }
}

#[tokio::main]
async fn main() {
    let (tx, rx) = mpsc::channel::<Trabajo>(64);
    let cancelar = CancellationToken::new();

    let consumidor = tokio::spawn(consumidor(rx, 4, cancelar.clone()));

    let productor = tokio::spawn(async move {
        for id in 0.. {
            if tx.send(Trabajo { id }).await.is_err() {
                break; // el consumidor cerró la cola
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
    });

    tokio::signal::ctrl_c().await.expect("no se pudo instalar el manejador de Ctrl+C");
    println!("Ctrl+C recibido");
    cancelar.cancel();
    productor.abort();
    consumidor.await.expect("el consumidor hizo panic");
}
```

Por qué cada decisión:

- **`mpsc::channel(64)`**, no `unbounded_channel`: si el productor va más rápido que los workers, `send().await` espera en vez de crecer sin límite en memoria. El tamaño es cuánto trabajo aceptas «en cola» antes de frenar al productor.
- **`Semaphore` + `JoinSet`** en lugar de 4 workers leyendo del mismo canal: `mpsc::Receiver` no se puede clonar (es *single consumer*). Un único bucle que reparte y un semáforo que limita es más simple y permite cambiar el paralelismo con un número.
- **`acquire_owned`** devuelve un permiso `'static` que viaja dentro de la tarea; se libera con `drop(permiso)` al terminar (o al hacer *panic*, porque `Drop` se ejecuta igual).
- **`select!` con `cancelled()`**: cuando llega Ctrl+C, salimos del bucle de aceptación pero **no abortamos** las tareas; el `while let` final espera a que acaben. Eso es el «terminar las que están en marcha».
- `productor.abort()` es correcto porque el productor no tiene nada que limpiar; a los trabajos en vuelo no los abortamos nunca.

Un límite conocido: si llega Ctrl+C mientras el bucle está esperando un permiso (`acquire_owned().await` con los 4 ocupados), no lo verá hasta que se libere uno, es decir, hasta 300 ms después. Si eso importa, mete también `acquire_owned` dentro de un `select!` con `cancelled()`.

Para probarlo: ejecuta, espera a ver varios «terminado», pulsa Ctrl+C y comprueba que imprime «dejando de aceptar; N trabajos en marcha» seguido de exactamente N «terminado» más y sale.""",
            },
            {
                "role": "user",
                "content": "Genial. ¿Y si el que envía el trabajo necesita el resultado de vuelta? Por ejemplo un handler HTTP que espera la respuesta del procesamiento.",
            },
            {
                "role": "assistant",
                "content": r"""Mete un `oneshot::Sender` dentro del trabajo. El emisor crea el par, envía la mitad `Sender` junto con los datos y se queda esperando en la mitad `Receiver`; el worker responde por ahí.

```rust
use tokio::sync::oneshot;

#[derive(Debug)]
struct Trabajo {
    id: u64,
    respuesta: oneshot::Sender<Result<u64, String>>,
}

async fn procesar(trabajo: Trabajo) {
    tokio::time::sleep(Duration::from_millis(300)).await;
    let resultado = if trabajo.id % 7 == 0 {
        Err(format!("el trabajo {} no es procesable", trabajo.id))
    } else {
        Ok(trabajo.id * 2)
    };
    // Si el emisor ya no espera (timeout, cliente desconectado), send falla; no es un error nuestro.
    let _ = trabajo.respuesta.send(resultado);
}
```

Lado del emisor (por ejemplo, dentro de un handler HTTP que tiene un `mpsc::Sender<Trabajo>` clonado):

```rust
async fn encolar_y_esperar(cola: &mpsc::Sender<Trabajo>, id: u64) -> Result<u64, String> {
    let (tx, rx) = oneshot::channel();
    cola.send(Trabajo { id, respuesta: tx })
        .await
        .map_err(|_| "el procesador está apagado".to_string())?;

    match tokio::time::timeout(Duration::from_secs(5), rx).await {
        Ok(Ok(resultado)) => resultado,
        Ok(Err(_)) => Err("el worker descartó el trabajo sin responder".into()),
        Err(_) => Err("tiempo de espera agotado".into()),
    }
}
```

Los tres casos del `match` son reales y distintos:

- `Ok(Ok(r))`: el worker respondió (con éxito o con su propio error de negocio).
- `Ok(Err(RecvError))`: el `Sender` se destruyó sin enviar. Pasa si la tarea hizo *panic* o si el consumidor se apagó con el trabajo todavía en la cola (el `Trabajo` se destruye con el canal y arrastra el `Sender`). Sin esto, el emisor se quedaría colgado para siempre.
- `Err(Elapsed)`: timeout. El trabajo puede seguir ejecutándose; el `let _ = send(...)` del worker es lo que evita que ese caso sea un error ruidoso.

`oneshot` es exactamente para esto: un único valor, un único receptor, sin coste de cola. Si en lugar de un valor necesitaras una secuencia de progreso, cambiarías ese campo por un `mpsc::Sender<Progreso>`; el resto del diseño no se toca.""",
            },
        ]
    },
    # 18) Arc<Mutex> vs RwLock vs RwLock<Arc>; multiturno sobre poisoning
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una configuración que se lee en cada petición y se recarga desde disco cada pocos minutos. ¿Uso `Arc<Mutex<Config>>` o `Arc<RwLock<Config>>`?",
            },
            {
                "role": "assistant",
                "content": r"""Ninguno de los dos tal cual: para «muchas lecturas, escritura rara y de reemplazo completo» la forma correcta es `Arc<RwLock<Arc<Config>>>`. Los lectores toman el candado de lectura solo para clonar un `Arc` (un incremento atómico) y lo sueltan; después usan su `Arc<Config>` todo el tiempo que quieran sin bloquear a nadie, incluida la recarga.

```rust
use std::sync::{Arc, RwLock};

#[derive(Debug, Clone)]
pub struct Config {
    pub limite_peticiones: u32,
    pub region: String,
}

#[derive(Clone)]
pub struct ConfigHandle {
    inner: Arc<RwLock<Arc<Config>>>,
}

impl ConfigHandle {
    pub fn new(config: Config) -> Self {
        Self { inner: Arc::new(RwLock::new(Arc::new(config))) }
    }

    /// Instantánea de la configuración actual. Barata: un clone de Arc bajo candado de lectura.
    pub fn actual(&self) -> Arc<Config> {
        self.inner.read().unwrap().clone()
    }

    /// Reemplaza la configuración entera. Los lectores con una instantánea anterior la conservan.
    pub fn reemplazar(&self, nueva: Config) {
        *self.inner.write().unwrap() = Arc::new(nueva);
    }
}
```

Uso en una petición:

```rust
fn atender(handle: &ConfigHandle, peticiones_en_ventana: u32) -> bool {
    let cfg = handle.actual(); // sin candado a partir de aquí
    peticiones_en_ventana < cfg.limite_peticiones
}
```

Por qué no las alternativas:

- **`Arc<Mutex<Config>>`**: serializa a todos los lectores entre sí. Con cientos de peticiones concurrentes que solo leen, es contención gratuita.
- **`Arc<RwLock<Config>>`** sin el `Arc` interior: parece lo mismo, pero el lector mantiene el candado de lectura **mientras usa** la configuración. Si una petición tarda 200 ms y en medio llega la recarga, el escritor espera, y en `std` eso puede además bloquear a los lectores nuevos hasta que el escritor pase (la política de prioridad depende del sistema operativo). Con el `Arc` interior la sección crítica dura nanosegundos.
- La versión sin candado de este patrón es la crate `arc-swap` (`ArcSwap<Config>` con `load()` y `store()`); si ya la tienes como dependencia, úsala. Para la mayoría de servicios el `RwLock<Arc<_>>` de la biblioteca estándar es indistinguible en rendimiento.

Consecuencia que hay que aceptar: una petición que tomó la instantánea antes de la recarga termina con la configuración vieja. Eso es lo deseable (una petición ve una configuración coherente de principio a fin), pero si necesitas que un cambio se aplique a mitad de petición, tendrías que llamar a `actual()` en cada punto de decisión.

Prueba:

```rust
#[test]
fn los_lectores_antiguos_conservan_su_instantanea() {
    let handle = ConfigHandle::new(Config { limite_peticiones: 10, region: "eu".into() });
    let antigua = handle.actual();
    handle.reemplazar(Config { limite_peticiones: 20, region: "us".into() });
    assert_eq!(antigua.limite_peticiones, 10);
    assert_eq!(handle.actual().limite_peticiones, 20);
}
```""",
            },
            {
                "role": "user",
                "content": "¿Y esos `.unwrap()` de `read()` y `write()`? ¿Pueden saltar en producción?",
            },
            {
                "role": "assistant",
                "content": r"""Pueden, pero solo por una causa: **envenenamiento** (*poisoning*). Si un hilo hace *panic* mientras tiene el candado tomado, el `Mutex`/`RwLock` queda marcado como envenenado y todas las llamadas posteriores a `lock()`/`read()`/`write()` devuelven `Err(PoisonError)`. El `unwrap()` convierte eso en un *panic* en cadena en cada petición.

La idea del envenenamiento es protegerte de leer datos a medio modificar. En tu caso no aplica: la única escritura es `*guard = Arc::new(nueva)`, que es una asignación atómica desde el punto de vista del dato; no hay estado intermedio. Un candado envenenado sigue conteniendo o la configuración vieja o la nueva, ambas válidas. Así que lo correcto es recuperar en vez de propagar:

```rust
use std::sync::PoisonError;

pub fn actual(&self) -> Arc<Config> {
    self.inner
        .read()
        .unwrap_or_else(PoisonError::into_inner)
        .clone()
}

pub fn reemplazar(&self, nueva: Config) {
    *self.inner.write().unwrap_or_else(PoisonError::into_inner) = Arc::new(nueva);
}
```

`PoisonError::into_inner` devuelve el guard igualmente; con él el candado sigue funcionando (desde Rust 1.77 también existe `clear_poison()` para limpiar la marca).

Cuándo sí dejar el `unwrap()`: cuando la sección crítica hace **varias** mutaciones que deben ser coherentes entre sí (restar de una cuenta y sumar a otra). Ahí un *panic* a medias deja datos inconsistentes y propagar el envenenamiento es la decisión segura.

La otra vía es `parking_lot::RwLock`, que no tiene envenenamiento (sus métodos devuelven el guard directamente), es algo más pequeño y rápido, y además garantiza que un escritor que espera no se muera de hambre. Es una dependencia extra; justificada si ya tienes muchos candados en el código y los `unwrap()` te molestan en cada línea.""",
            },
        ]
    },
    # 19) RefCell: BorrowMutError en tiempo de ejecución
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Mi caché con RefCell compila pero hace panic la primera vez que no encuentra la clave:

```rust
use std::cell::RefCell;
use std::collections::HashMap;

pub struct Cache {
    datos: RefCell<HashMap<String, String>>,
}

impl Cache {
    pub fn obtener(&self, clave: &str) -> String {
        match self.datos.borrow().get(clave) {
            Some(v) => v.clone(),
            None => {
                let v = calcular(clave);
                self.datos.borrow_mut().insert(clave.to_string(), v.clone());
                v
            }
        }
    }
}

fn calcular(clave: &str) -> String {
    clave.to_uppercase()
}
```

```
thread 'main' panicked at src/main.rs:15:28:
already borrowed: BorrowMutError
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```""",
            },
            {
                "role": "assistant",
                "content": r"""El *panic* viene de que el préstamo de lectura **sigue vivo dentro de la rama `None`**. `self.datos.borrow()` devuelve un guard `Ref`; en un `match`, los temporales de la expresión examinada viven hasta que termina el `match` entero, incluidas todas las ramas. Así que cuando llamas `borrow_mut()` en la línea 15, el `Ref` de la línea 11 aún no se ha soltado, y `RefCell` hace exactamente lo que haría el compilador con `&`/`&mut`, solo que en tiempo de ejecución.

El arreglo más simple es hacer **una sola operación** con la API `entry`, que no deja lugar a dos préstamos:

```rust
impl Cache {
    pub fn obtener(&self, clave: &str) -> String {
        self.datos
            .borrow_mut()
            .entry(clave.to_string())
            .or_insert_with(|| calcular(clave))
            .clone()
    }
}
```

Un `borrow_mut()`, que se suelta al terminar la sentencia. `or_insert_with` solo llama a `calcular` si la clave no estaba. El único coste es que `clave.to_string()` asigna aunque la clave exista; para una caché de strings es despreciable.

Si quieres evitar esa asignación en el camino rápido, termina el préstamo de lectura **antes** de decidir, sacando el valor con `cloned()` en un `let` (los temporales de un `let` mueren al acabar la sentencia):

```rust
pub fn obtener(&self, clave: &str) -> String {
    let en_cache = self.datos.borrow().get(clave).cloned();
    if let Some(v) = en_cache {
        return v;
    }
    let v = calcular(clave);
    self.datos.borrow_mut().insert(clave.to_string(), v.clone());
    v
}
```

Aquí el `Ref` muere al final de la primera línea; `en_cache` es un `Option<String>` propio, sin préstamo.

Dos cosas que **no** son la solución:

- `try_borrow_mut()`: convierte el *panic* en un `Err`, pero el préstamo solapado sigue ahí; solo esconderías el bug.
- Cambiar a `if let ... else`: en edición 2021 el temporal también vive durante el `else`, así que el mismo *panic*. (La edición 2024 acorta ese temporal antes del `else`, pero no conviene depender de eso para que un programa no explote.)

Y el límite de `RefCell`: solo sirve en un hilo. Si esta caché se comparte entre hilos no compilará (`RefCell` no es `Sync`), y el reemplazo es `Mutex<HashMap<..>>`, con el mismo cuidado: un único `lock()` por operación.

Prueba de regresión, que es la que faltaba:

```rust
#[test]
fn calcula_una_vez_y_luego_sirve_de_cache() {
    let cache = Cache { datos: RefCell::new(HashMap::new()) };
    assert_eq!(cache.obtener("hola"), "HOLA"); // primera vez: rama de cálculo (la que hacía panic)
    assert_eq!(cache.obtener("hola"), "HOLA");
    assert_eq!(cache.datos.borrow().len(), 1);
}
```""",
            },
        ]
    },
    # 20) Árbol con punteros al padre: arena vs Rc<RefCell>+Weak
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero un árbol donde cada nodo tenga hijos y además una referencia a su padre para subir hasta la raíz. En cualquier otro lenguaje es trivial y en Rust llevo dos días peleándome con el borrow checker. ¿Cómo se hace?",
            },
            {
                "role": "assistant",
                "content": r"""El bloqueo viene de que padre→hijo→padre es un **ciclo de referencias**, y la propiedad única no admite ciclos. En Rust no se modela con referencias sino con **índices en una arena**: el árbol es dueño de todos los nodos en un `Vec`, y «padre» e «hijos» son identificadores. Es lo que usan rustc, los motores de layout y los ECS, y hace que el borrow checker desaparezca del problema.

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId(usize);

#[derive(Debug)]
pub struct Node<T> {
    pub value: T,
    pub parent: Option<NodeId>,
    pub children: Vec<NodeId>,
}

#[derive(Debug)]
pub struct Tree<T> {
    nodes: Vec<Node<T>>,
}

impl<T> Tree<T> {
    pub fn new() -> Self {
        Self { nodes: Vec::new() }
    }

    pub fn add_root(&mut self, value: T) -> NodeId {
        self.push(value, None)
    }

    pub fn add_child(&mut self, parent: NodeId, value: T) -> NodeId {
        let id = self.push(value, Some(parent));
        self.nodes[parent.0].children.push(id);
        id
    }

    pub fn get(&self, id: NodeId) -> &Node<T> {
        &self.nodes[id.0]
    }

    pub fn get_mut(&mut self, id: NodeId) -> &mut Node<T> {
        &mut self.nodes[id.0]
    }

    /// Ancestros del más cercano a la raíz, sin incluir `id`.
    pub fn ancestors(&self, id: NodeId) -> impl Iterator<Item = NodeId> + '_ {
        std::iter::successors(self.nodes[id.0].parent, move |&p| self.nodes[p.0].parent)
    }

    fn push(&mut self, value: T, parent: Option<NodeId>) -> NodeId {
        let id = NodeId(self.nodes.len());
        self.nodes.push(Node { value, parent, children: Vec::new() });
        id
    }
}
```

Lo que ganas:

- `NodeId` es `Copy`: lo guardas, lo pasas, lo metes en un `HashMap`, sin lifetimes.
- Subir al padre es `tree.get(id).parent`; recorrer ancestros es un iterador perezoso.
- Todo el árbol es un solo bloque de memoria contiguo: recorridos rápidos, `Send` gratis, serializable con serde sin trucos.
- Mutar un nodo mientras lees otro no pelea con el borrow checker porque siempre pasas por `&mut self` del árbol, una operación a la vez.

Lo que pierdes y cómo se maneja: borrar nodos deja huecos en el `Vec` (si haces `remove`, los índices posteriores cambian). Para árboles con borrados, marca el nodo como libre y reutiliza (lista de huecos), o usa índices con generación (crate `slotmap`) para que un id viejo no apunte a un nodo nuevo. Si el árbol solo crece, no necesitas nada de eso.

Prueba:

```rust
#[test]
fn sube_hasta_la_raiz() {
    let mut t = Tree::new();
    let raiz = t.add_root("raíz");
    let a = t.add_child(raiz, "a");
    let b = t.add_child(a, "b");
    let camino: Vec<&str> = t.ancestors(b).map(|id| t.get(id).value).collect();
    assert_eq!(camino, vec!["a", "raíz"]);
    assert_eq!(t.get(raiz).children, vec![a]);
}
```

**La alternativa que probablemente intentabas**, `Rc<RefCell<Node>>` con `Weak` hacia el padre, también existe:

```rust
use std::cell::RefCell;
use std::rc::{Rc, Weak};

struct Node {
    value: String,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}
```

El `Weak` es obligatorio: con `Rc` en ambas direcciones el contador nunca llega a cero y el árbol entero se fuga. Y cada acceso pasa por `borrow()`/`upgrade()`, lo que mueve las comprobaciones a tiempo de ejecución (`BorrowMutError` si anidas mal) y no es `Send`. Es la traducción literal de Java; funciona, pero es más frágil y más lenta que la arena. Úsala solo si necesitas que los nodos sobrevivan por sí solos fuera del árbol.

Y una pregunta previa que a veces disuelve el problema: si solo necesitas el padre **durante un recorrido**, pásalo como parámetro de la recursión y no lo guardes. El puntero al padre persistente solo hace falta cuando llegas a un nodo desde fuera (por un id, por un clic) y tienes que subir.""",
            },
        ]
    },
    # 21) serde: missing field, rename_all, default y enums etiquetados. Usuario trae error
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Estoy deserializando la respuesta de una API con serde_json y me falla con esto:

```
Error("missing field `user_id`", line: 7, column: 1)
```

El JSON que llega es:

```json
{
  "userId": 42,
  "displayName": "Ana",
  "tags": null,
  "kind": "admin",
  "lastLogin": "2025-03-01T10:00:00Z"
}
```

Y mi struct:

```rust
#[derive(Debug, Deserialize)]
struct User {
    user_id: u64,
    display_name: String,
    tags: Vec<String>,
    kind: String,
}
```

Además `tags` a veces viene `null` y a veces ni siquiera viene. ¿Cómo lo arreglo sin renombrar todos mis campos a camelCase?""",
            },
            {
                "role": "assistant",
                "content": r"""Son tres problemas distintos, y el error solo te enseña el primero porque serde se detiene en el primer campo que no encuentra.

1. **Nombres**: el JSON usa `userId` y tu struct `user_id`. serde compara literalmente, así que `user_id` «falta». Se arregla con `#[serde(rename_all = "camelCase")]` en el struct: los identificadores siguen en snake_case en Rust y la conversión la hace serde.
2. **`tags: null`**: `Vec<String>` no acepta `null`. Para «viene null» necesitas `Option<Vec<String>>`; para «no viene» necesitas `#[serde(default)]`. Como pasan las dos cosas, hacen falta ambas.
3. **`kind`** es un conjunto cerrado de valores. Dejarlo como `String` funciona, pero te obliga a comparar cadenas por todo el código; un enum con `rename_all` lo valida al deserializar.

```rust
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct User {
    user_id: u64,
    display_name: String,
    #[serde(default)]
    tags: Option<Vec<String>>,
    kind: Kind,
    #[serde(default)]
    last_login: Option<String>,
}

#[derive(Debug, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
enum Kind {
    Admin,
    Member,
    Guest,
}
```

Por qué `Option` + `default` y no solo `Option`: `Option<T>` ya acepta `null`, y serde trata un `Option` **ausente** como `None` solo cuando el campo es `Option` directamente y no hay otros atributos que lo impidan; en la práctica funciona, pero `#[serde(default)]` lo hace explícito y además cubre el caso en que algún día lo cambies a `Vec<String>` con default vacío. Si prefieres no distinguir «null» de «ausente» de «vacío», usa `Vec<String>` con un deserializador que convierta `null` en `vec![]`:

```rust
fn null_as_empty<'de, D>(d: D) -> Result<Vec<String>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    Ok(Option::<Vec<String>>::deserialize(d)?.unwrap_or_default())
}

// en el struct:
#[serde(default, deserialize_with = "null_as_empty")]
tags: Vec<String>,
```

Dos ajustes más que conviene decidir ahora:

- **Campos desconocidos.** Por defecto serde los ignora, que es lo que quieres con una API que añade campos. Si por el contrario quieres que un campo nuevo te avise, `#[serde(deny_unknown_fields)]`.
- **Fechas.** `last_login` como `String` no valida nada. Con la *feature* `serde` de `chrono` o `time` puedes tiparlo: `last_login: Option<chrono::DateTime<chrono::Utc>>` deserializa RFC 3339 directamente.

Comprobación con los tres casos que te fallaban:

```rust
#[test]
fn deserializa_con_tags_null_o_ausentes() {
    let con_null = r#"{"userId":42,"displayName":"Ana","tags":null,"kind":"admin"}"#;
    let sin_tags = r#"{"userId":42,"displayName":"Ana","kind":"member"}"#;
    let con_tags = r#"{"userId":42,"displayName":"Ana","tags":["a"],"kind":"guest"}"#;

    let u: User = serde_json::from_str(con_null).unwrap();
    assert_eq!(u.tags, None);
    let u: User = serde_json::from_str(sin_tags).unwrap();
    assert_eq!((u.tags, u.kind), (None, Kind::Member));
    let u: User = serde_json::from_str(con_tags).unwrap();
    assert_eq!(u.tags.as_deref(), Some(&["a".to_string()][..]));
}
```

Y para leer errores de serde en el futuro: el mensaje `missing field` siempre nombra el campo **en Rust** tal como serde lo espera tras aplicar `rename`, y `line: 7, column: 1` apunta al cierre del objeto, no al campo, porque serde descubre la ausencia cuando termina de leer el objeto. Un `invalid type: null, expected a sequence` habría sido el error 2 en cuanto arreglaras el 1.""",
            },
        ]
    },
    # 22) clippy: salida pegada, qué corregir y cómo configurarlo en CI. System variante (rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y sin vueltas. Verificá lo que proponés."},
            {
                "role": "user",
                "content": r"""Corrí `cargo clippy` por primera vez en un proyecto que heredé y me tira 140 warnings. Pegué los tres más repetidos, decime si los arreglo o los silencio:

```
warning: the loop variable `i` is only used to index `items`
  --> src/report.rs:14:14
   |
14 |     for i in 0..items.len() {
   |              ^^^^^^^^^^^^^^
   = note: `#[warn(clippy::needless_range_loop)]` on by default

warning: writing `&Vec` instead of `&[_]` involves a new object where a slice will do
  --> src/report.rs:9:22
   |
 9 | fn summarize(items: &Vec<Item>) -> String {
   |                      ^^^^^^^^^ help: change this to: `&[Item]`
   = note: `#[warn(clippy::ptr_arg)]` on by default

warning: large size difference between variants
  --> src/event.rs:4:1
   |
 4 | / pub enum Event {
 5 | |     Tick,
 6 | |     Payload([u8; 4096]),
   | |     ------------------- the largest variant contains at least 4096 bytes
 7 | | }
   = note: `#[warn(clippy::large_enum_variant)]` on by default
```""",
            },
            {
                "role": "assistant",
                "content": r"""Los tres se arreglan, y los tres son baratos. Silenciar sin mirar es dejar deuda con otro nombre. Van en orden de impacto.

**`large_enum_variant` (event.rs): arreglalo primero, es el único con costo real.** Un enum ocupa lo que su variante más grande más el discriminante: cada `Event::Tick` pesa 4097+ bytes, y cada `Vec<Event>`, cada canal, cada `Option<Event>` lo paga. Mové el *payload* al *heap*:

```rust
pub enum Event {
    Tick,
    Payload(Box<[u8; 4096]>),
}
```

Ahora `size_of::<Event>()` son 16 bytes. Si el *payload* lo construís vos, `Box::new([0u8; 4096])` cuesta una asignación por evento, que casi siempre es más barato que copiar 4 KB en cada `match`, cada `push` y cada *send*. Comprobalo con un test para que nadie lo vuelva a inflar:

```rust
#[test]
fn event_es_chico() {
    assert!(std::mem::size_of::<Event>() <= 16);
}
```

**`ptr_arg` (report.rs:9): arreglalo, es un cambio de firma sin costo.** `&Vec<Item>` solo acepta vectores; `&[Item]` acepta vectores, *arrays*, *slices* de otro `Vec` y `Box<[Item]>`, y se lee igual adentro (`items.len()`, `items.iter()`, indexado). Un `&Vec` solo tendría sentido si necesitaras `capacity()`, que en una función que resume nunca pasa.

```rust
fn summarize(items: &[Item]) -> String {
```

Las llamadas existentes `summarize(&v)` siguen compilando por *deref coercion*; no tenés que tocar nada más.

**`needless_range_loop` (report.rs:14): arreglalo si el índice no se usa para otra cosa.** El bucle por índice hace una comprobación de límites en cada acceso y esconde qué recorrés. Si solo leés `items[i]`:

```rust
for item in items {
```

Si además necesitás el índice (para numerar, para mirar el vecino), `enumerate()`:

```rust
for (i, item) in items.iter().enumerate() {
```

El único caso en que el *lint* se equivoca es cuando dentro del bucle indexás **dos** colecciones con el mismo `i` sin `zip` posible; ahí poné `#[allow(clippy::needless_range_loop)]` en esa función, con un comentario de por qué.

**Cómo encarar los 140 sin que te coma la semana.** Primero mirá cuántos tipos de *lint* distintos hay, no cuántos avisos:

```sh
cargo clippy --all-targets 2>&1 | grep -o 'clippy::[a-z_]*' | sort | uniq -c | sort -rn
```

Seguro son 10 o 15 *lints* repetidos. Para los mecánicos, dejá que clippy los aplique: `cargo clippy --fix --allow-dirty` (hacé *commit* antes, y revisá el *diff*). Lo que quede a mano, un *lint* por *commit* para que el revisor pueda seguirlo.

**Y bloqueá la regresión.** En `Cargo.toml` (Rust 1.74 o más) configurás los niveles una sola vez:

```toml
[lints.clippy]
all = { level = "warn", priority = -1 }
large_enum_variant = "deny"
ptr_arg = "deny"
```

Y en CI, que los *warnings* corten el *pipeline*:

```sh
cargo clippy --all-targets --all-features -- -D warnings
```

Lo que no te recomiendo: activar `pedantic` entero en un proyecto heredado. Son opiniones, no bugs, y te va a sumar otros 300 avisos. Si querés algo de ahí, activá *lints* sueltos (`clippy::needless_pass_by_value` y `clippy::cast_possible_truncation` son los que más valen la pena).""",
            },
        ]
    },
    # 23) Clones innecesarios, with_capacity, Cow; multiturno sobre cuándo sí clonar. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Vengo de Java y en Rust pongo `.clone()` cada vez que el compilador se queja, hasta que compila. Un compañero me dijo que esta función «clona todo tres veces». Yo la veo normal:

```rust
#[derive(Clone)]
struct User {
    name: String,
    email: String,
    active: bool,
}

fn build_report(users: &Vec<User>) -> String {
    let mut out = String::new();
    for u in users.clone() {
        if u.active {
            let line = format!("{} <{}>", u.name.clone(), u.email.clone());
            out = out + &line + "\n";
        }
    }
    out
}
```

¿Qué está mal y cómo lo escribo bien?""",
            },
            {
                "role": "assistant",
                "content": r"""Tu compañero se queda corto: son cuatro copias por usuario más una reasignación del acumulador. Ninguna hace falta, porque la función solo **lee** los usuarios.

Vamos clone por clone:

1. `users.clone()` copia el `Vec` entero (cada `User`, cada `String` dentro) para recorrerlo y tirarlo. Se recorre por referencia: `for u in users` (equivale a `users.iter()`), y `u` es `&User`.
2. `u.name.clone()` y `u.email.clone()` copian dos `String` para que `format!` las lea. `format!` acepta referencias; no mueve nada, así que `u.name` basta.
3. `out + &line + "\n"` consume `out`, concatena y la devuelve; funciona, pero `format!` ya creó `line` solo para copiarla a `out`. Escribe directamente en `out`.
4. `&Vec<User>` en la firma: cambia a `&[User]`, que acepta lo mismo y más.

```rust
use std::fmt::Write;

fn build_report(users: &[User]) -> String {
    let mut out = String::with_capacity(users.len() * 48);
    for u in users.iter().filter(|u| u.active) {
        // writeln! sobre String no falla: el Err es imposible, se puede ignorar con `let _`
        let _ = writeln!(out, "{} <{}>", u.name, u.email);
    }
    out
}
```

Tres detalles del arreglo:

- **`with_capacity`**: cada vez que un `String` se queda sin sitio, pide el doble y copia. Con una estimación razonable (48 bytes por línea es generoso para nombre + correo) haces una sola asignación. Si te pasas, solo gastas algo de memoria; si te quedas corto, vuelve al comportamiento normal. No es obligatorio, pero en un bucle que construye salida es la optimización más barata que existe.
- **`writeln!` sobre `String`** necesita `use std::fmt::Write`. Escribe en el buffer existente sin crear cadenas intermedias.
- **`#[derive(Clone)]` en `User`** ya no lo usa esta función. Déjalo si otra parte del programa lo necesita; si no, quítalo y el compilador te dirá dónde clonabas sin pensar.

La regla que sustituye a «clono hasta que compila»: cuando el compilador pide un `clone`, pregúntate **quién necesita ser dueño**. Si nadie (solo lees), la respuesta es una referencia, no un clone. Si alguien sí (vas a guardarlo en un struct, enviarlo a otro hilo, devolverlo), entonces o bien **mueves** el valor original si ya no lo usas, o bien clonas, y ese clone es legítimo.

Para el caso intermedio, «casi nunca modifico pero a veces sí», existe `Cow`:

```rust
use std::borrow::Cow;

fn normalize_email(email: &str) -> Cow<'_, str> {
    if email.chars().any(|c| c.is_ascii_uppercase()) {
        Cow::Owned(email.to_ascii_lowercase())
    } else {
        Cow::Borrowed(email)
    }
}
```

Devuelve el préstamo si no hubo que cambiar nada y una copia solo cuando hizo falta; quien llama lo usa como `&str` sin saber cuál de los dos recibió.

Comprobación: `cargo clippy` con la versión original avisa de `ptr_arg` y, si activas `clippy::pedantic`, de `needless_pass_by_value` en patrones parecidos. La versión nueva compila sin avisos y produce la misma salida; un test rápido:

```rust
#[test]
fn solo_los_activos_y_en_orden() {
    let users = vec![
        User { name: "Ana".into(), email: "ana@x.io".into(), active: true },
        User { name: "Luis".into(), email: "luis@x.io".into(), active: false },
        User { name: "Eva".into(), email: "eva@x.io".into(), active: true },
    ];
    assert_eq!(build_report(&users), "Ana <ana@x.io>\nEva <eva@x.io>\n");
}
```""",
            },
            {"role": "user", "content": "Vale, ¿y entonces cuándo está bien clonar? Porque también he leído que `Arc::clone` es normal y se usa por todas partes."},
            {
                "role": "assistant",
                "content": r"""Clonar está bien cuando el clone **es la semántica que quieres**, no cuando es la salida del paso del compilador. Casos legítimos, de más a menos frecuente:

**1. El clone es barato por diseño.** `Rc::clone` y `Arc::clone` incrementan un contador; no copian el dato. Esa es su razón de existir: varios dueños del mismo valor. Por eso se escribe `Arc::clone(&x)` y no `x.clone()`: deja a la vista que es un contador, no una copia. Lo mismo con `Bytes`, con los *handles* de tokio (`mpsc::Sender`, `broadcast::Sender`) y con cualquier tipo documentado como «cheap to clone».

**2. Necesitas un dueño nuevo y el original sigue en uso.** Mandar datos a un hilo o a una tarea que vive más que tu función, guardar una `String` que te llegó por referencia en un struct que devuelves, meter el mismo valor en dos colecciones. Ahí la alternativa no es «no clonar» sino cambiar la arquitectura (compartir con `Arc`, pasar propiedad en vez de referencia), y a veces el clone es simplemente la solución correcta.

```rust
fn spawn_worker(config: &Config) -> std::thread::JoinHandle<()> {
    let config = config.clone(); // el hilo necesita su copia: el &Config no sobrevive
    std::thread::spawn(move || run(config))
}
```

Si `Config` es grande y de solo lectura, pásalo como `Arc<Config>` desde el principio y este clone pasa al caso 1.

**3. Tipos `Copy`.** `i32`, `bool`, `char`, `&T`, tuplas y *arrays* de `Copy`: copiarlos es gratis y el compilador lo hace solo; no verás `.clone()`.

**4. Salir de un préstamo que bloquea.** El patrón «leo un campo de `self` para después mutar `self`»:

```rust
let name = self.name.clone();
self.log(&name); // log toma &mut self
```

Es legítimo, aunque a menudo se evita reorganizando el código (sacar lo que necesitas antes, o separar el struct en dos).

**5. Tests y prototipos.** En un test, clonar para construir el caso es ruido aceptable; optimizarlo no aporta nada.

Donde el clone es un olor, no una solución:

- Dentro de un bucle caliente, sobre `String` o `Vec`, para contentar un préstamo. Ahí mide: un clone de `String` es una asignación más un `memcpy`; mil por petición se notan.
- Para «desbloquear» un `&mut` que tienes dos veces (E0499): el clone esconde que tu diseño pide dos dueños de lo mismo.
- `.clone()` sobre un `&T` por error, que te da otro `&T` y no un `T`: clippy lo marca como `clone_on_ref_ptr` o te lo avisa el propio compilador con «`T` does not implement `Clone`» más adelante.

Regla práctica: antes de escribir `.clone()`, di en voz alta quién es el dueño nuevo y por qué no puede ser una referencia. Si la frase sale («el hilo necesita su copia»), déjalo. Si no sale, es un préstamo mal colocado.""",
            },
        ]
    },
    # 24) unsafe con criterio: FFI a C con wrapper seguro, SAFETY, Miri. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": r"""I need to call a small C library from Rust. The header is:

```c
int32_t sum_array(const int32_t *data, size_t len);
char *make_greeting(const char *name);   // caller must free with free_greeting
void free_greeting(char *s);
```

I know I need `unsafe`, but I don't want unsafe spread all over my code. What's the right way to wrap this? Rust 1.85, edition 2024.""",
            },
            {
                "role": "assistant",
                "content": r"""The right shape is one small `ffi` module with the raw declarations and a safe API in front of it. `unsafe` stays inside that module, every unsafe block carries a `SAFETY:` comment stating which precondition you discharged, and ownership of the C string is modelled with a Rust type that frees it in `Drop`. Callers never see a raw pointer.

**1. Raw declarations.** In edition 2024, `extern` blocks must be marked `unsafe extern`, and you may mark individual items `safe` when calling them cannot violate memory safety on its own.

```rust
// src/ffi.rs
use std::ffi::{c_char, c_int};

unsafe extern "C" {
    pub fn sum_array(data: *const i32, len: usize) -> c_int;
    pub fn make_greeting(name: *const c_char) -> *mut c_char;
    pub fn free_greeting(s: *mut c_char);
}
```

None of these qualify as `safe`: all three take or return raw pointers with preconditions.

**2. Safe wrappers.**

```rust
// src/lib.rs
mod ffi;

use std::ffi::{CStr, CString, NulError};
use std::fmt;

pub fn sum(data: &[i32]) -> i32 {
    // SAFETY: `data.as_ptr()` is valid for reads of `data.len()` i32s for the duration
    // of the call, and the C side only reads through `const int32_t *`.
    unsafe { ffi::sum_array(data.as_ptr(), data.len()) }
}

/// A C string allocated by the library; freed with `free_greeting` on drop.
pub struct Greeting {
    ptr: *mut std::ffi::c_char,
}

impl Greeting {
    pub fn new(name: &str) -> Result<Self, NulError> {
        let c_name = CString::new(name)?; // fails if `name` contains an interior NUL
        // SAFETY: `c_name` is a valid NUL-terminated string that outlives the call.
        let ptr = unsafe { ffi::make_greeting(c_name.as_ptr()) };
        assert!(!ptr.is_null(), "make_greeting returned NULL");
        Ok(Self { ptr })
    }

    pub fn as_str(&self) -> &str {
        // SAFETY: `ptr` is non-null (checked in `new`), NUL-terminated, and stays valid
        // and unmodified until `drop`. Lifetime of the returned &str is tied to &self.
        let c = unsafe { CStr::from_ptr(self.ptr) };
        c.to_str().expect("library returned invalid UTF-8")
    }
}

impl Drop for Greeting {
    fn drop(&mut self) {
        // SAFETY: `ptr` came from `make_greeting` and is freed exactly once, here.
        unsafe { ffi::free_greeting(self.ptr) }
    }
}

impl fmt::Display for Greeting {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}
```

Why these decisions:

- **`Greeting` owns the pointer**, so a double free or a leak is impossible from safe code. It is deliberately not `Clone`, and it is not `Send`/`Sync` by default because it holds a raw pointer. If the C library is thread-safe for this value, add `unsafe impl Send for Greeting {}` with a comment citing the library's docs; do not add it just to make the borrow checker quiet.
- **`CString::new` returns `NulError`** instead of panicking: an interior `\0` from user input is an expected failure, not a bug.
- **The NULL check is an `assert!`**, not a `Result`, because the header does not document NULL as a return value; if it did (allocation failure), return `Option<Self>` instead.
- **`as_str` borrows from `&self`**, so the compiler prevents using the string after the `Greeting` is dropped. That is the whole point of the wrapper: the lifetime that C leaves to convention becomes a type-checked one.
- **`expect` on UTF-8**: the library is yours and its output is ASCII. If it could return arbitrary bytes, expose `as_bytes()` or return `Result<&str, Utf8Error>`.

**3. Building.** Compile the C side with the `cc` crate from `build.rs` so `cargo build` does everything:

```rust
// build.rs
fn main() {
    cc::Build::new().file("csrc/greet.c").compile("greet");
    println!("cargo:rerun-if-changed=csrc/greet.c");
}
```

For a real header with many functions, generate `ffi.rs` with `bindgen` instead of writing it by hand; mismatched signatures are the most common FFI bug and the compiler cannot catch them.

**4. Verification.** Two layers:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sums_and_handles_empty() {
        assert_eq!(sum(&[1, 2, 3]), 6);
        assert_eq!(sum(&[]), 0); // `as_ptr` on an empty slice is dangling but never read
    }

    #[test]
    fn greeting_round_trip_and_nul_rejection() {
        let g = Greeting::new("Ada").unwrap();
        assert!(g.as_str().contains("Ada"));
        assert!(Greeting::new("A\0da").is_err());
    }
}
```

Run them under AddressSanitizer to catch a double free or a use-after-free on the C side: `RUSTFLAGS="-Zsanitizer=address" cargo +nightly test --target x86_64-unknown-linux-gnu`. Miri (`cargo +nightly miri test`) is the stronger tool for unsafe Rust, but it cannot execute foreign code, so it will reject these tests; it is still worth running on any `unsafe` block in your crate that does not cross the FFI boundary (`from_raw_parts`, pointer casts, transmutes).

The rule to carry forward: unsafe code is acceptable when it is **small, local, documented with the invariant it relies on, and wrapped in a type whose safe API makes misuse impossible**. If you find yourself writing `unsafe` in business logic, the wrapper is missing an operation.""",
            },
        ]
    },
    # 25) Edición 2024: qué cambia, cómo migrar, qué se rompe
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos un monorepo con unos 15 crates en edición 2021 y Rust 1.86 en CI. ¿Vale la pena pasar a la edición 2024? ¿Qué se rompe de verdad y cómo se hace sin parar al equipo una semana?",
            },
            {
                "role": "assistant",
                "content": r"""Vale la pena, y con 1.86 ya puedes. La edición 2024 se estabilizó en Rust 1.85 y `cargo fix --edition` automatiza casi todo. En un monorepo típico la migración son un par de horas por crate, y la mayoría se reducen a revisar un *diff* mecánico.

**Lo que de verdad cambia** (lo que afecta a código normal, no la lista completa):

1. **`unsafe extern`.** Los bloques `extern "C" { ... }` deben ser `unsafe extern "C"`. Si tienes FFI, es el cambio más visible; `cargo fix` lo añade.
2. **Atributos `unsafe`.** `#[no_mangle]`, `#[export_name]` y `#[link_section]` pasan a `#[unsafe(no_mangle)]`. Mecánico.
3. **`unsafe_op_in_unsafe_fn`** pasa a *warn* por defecto: dentro de un `unsafe fn`, cada operación insegura necesita su propio bloque `unsafe { }`. Es la ocasión de poner un comentario `SAFETY:` en cada uno.
4. **Referencias a `static mut`** (`&STATIC` o `&mut STATIC`) se rechazan por el *lint* `static_mut_refs`, que pasa a *deny*. Sustituye por `AtomicX`, `Mutex`, `OnceLock` o `&raw mut`.
5. **`std::env::set_var` y `remove_var` son `unsafe`**, porque mutan estado global de proceso que otros hilos pueden estar leyendo. En tests que fijan variables de entorno tendrás que envolverlos en `unsafe` y asegurarte de que no corren en paralelo.
6. **Captura de lifetimes en `impl Trait` de retorno.** `fn f(x: &T) -> impl Iterator<Item = u32>` ahora captura el lifetime de `x` automáticamente. La mayoría de las veces compila lo que antes no; en algún caso raro un *iterator* que antes se podía guardar más allá del préstamo deja de poderse, y lo resuelves con `impl Iterator<Item = u32> + use<>` (captura precisa, estable desde 1.82).
7. **Alcance de temporales.** Los temporales de la expresión final de un bloque y los del *scrutinee* de `if let` se liberan antes (antes sobrevivían a los locales, y en `if let` llegaban al `else`). Afecta sobre todo a `MutexGuard` y a `RefCell::borrow()` en un `if let`: lo que antes era un *deadlock* o un `BorrowMutError` en el `else`, ahora funciona. Al revés casi nunca rompe, pero revisa los `if let` con *locks*.
8. **`gen` es palabra reservada.** Si tienes una variable o función llamada `gen`, pasa a `r#gen`. `cargo fix` lo hace.
9. **Macros `macro_rules!`:** el fragmento `expr` ahora acepta `const { }` y `_`; si tu macro tenía una rama que dependía de que `expr` no los aceptara, usa `expr_2021`.
10. **`Box<[T]>` implementa `IntoIterator` por valor**, así que `boxed_slice.into_iter()` devuelve elementos en lugar de referencias. El *lint* `boxed_slice_into_iter` te avisa en 2021 antes de migrar.
11. **`cargo`**: el resolver pasa a la versión 3, que respeta `rust-version` de las dependencias al elegir versiones. Ventaja real para un monorepo con MSRV declarada.

Lo que **no** cambia: nada de la semántica de propiedad, traits ni la biblioteca estándar. Las ediciones son por crate; un crate 2024 depende sin problema de crates 2021 y viceversa, lo que es exactamente lo que te permite migrar sin parar al equipo.

**Procedimiento por crate**, en una rama corta por cada uno:

```sh
# 1. Limpio y verde antes de tocar nada
cargo clippy --all-targets -- -D warnings && cargo test

# 2. Reescritura automática (sigue en edición 2021, solo prepara el código)
cargo fix --edition --all-targets --allow-dirty

# 3. Cambiar la edición a mano en Cargo.toml
#    edition = "2024"
#    rust-version = "1.85"   (si declaras MSRV)

# 4. Comprobar y reformatear con el estilo de 2024
cargo fix --edition-idioms --all-targets --allow-dirty   # opcional, aplica idiomas nuevos
cargo fmt
cargo clippy --all-targets -- -D warnings && cargo test
```

`cargo fix --edition` solo aplica las migraciones necesarias para que el código conserve el **mismo comportamiento** en la edición nueva; por eso el paso 3 es manual y viene después.

**Orden en el monorepo:** empieza por las hojas (crates sin dependencias internas) y sube hacia el binario. Un crate al día en una PR pequeña es mucho más revisable que las 15 juntas, y si una migración rompe algo raro (casi siempre es el punto 7 o un `set_var` en tests) lo aíslas al instante. Si usas `workspace.package.edition`, cambia cada crate a `edition.workspace = true` **al final**, cuando todos estén en 2024, para no forzar la migración simultánea.

**Comprobación de que terminaste**: `grep -rn 'edition = "2021"' --include=Cargo.toml` vacío, CI verde, y un `cargo +nightly miri test` sobre los crates con `unsafe` si tenías alguno de los puntos 3 y 4, que son los únicos donde la migración puede cambiar algo más que la sintaxis.""",
            },
        ]
    },
    # 26) Rendimiento: «Rust más lento que Python»; multiturno con I/O de líneas. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": r"""Reescribí en Rust un script de Python que cuenta palabras en un archivo de 2 GB y... el de Rust tarda 41 segundos y el de Python 19. Algo hago mal. Lo corro con `cargo run -- datos.txt`. Este es el núcleo:

```rust
use std::collections::HashMap;
use std::fs;

fn main() {
    let path = std::env::args().nth(1).expect("ruta");
    let text = fs::read_to_string(&path).expect("leer");
    let mut counts: HashMap<String, usize> = HashMap::new();
    for word in text.split_whitespace() {
        let w = word.to_lowercase();
        *counts.entry(w).or_insert(0) += 1;
    }
    let mut pairs: Vec<_> = counts.into_iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(&a.1));
    for (w, c) in pairs.iter().take(20) {
        println!("{w} {c}");
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Lo primero y casi seguro lo único: **estás midiendo un binario de depuración**. `cargo run` compila sin optimizaciones (`opt-level = 0`), con comprobaciones de desbordamiento y sin *inlining*; en código que hace millones de operaciones pequeñas (hashing, comparaciones de bytes) la diferencia con `--release` es de 10 a 50 veces. Python no tiene ese modo: su intérprete ya es «lo que hay».

```sh
cargo run --release -- datos.txt
```

Mide antes de cambiar nada más. Con 2 GB, un conteo de palabras razonable en *release* debería estar en 3-6 segundos en un portátil, limitado por la lectura del archivo.

Si después de eso quieres recortar más, estos son los costes reales del código, por orden:

**1. `read_to_string` carga 2 GB en memoria y valida UTF-8 de golpe.** Funciona, pero necesita 2 GB de RAM y no empieza a contar hasta terminar de leer. Procesar por líneas con `BufReader` mantiene el uso de memoria plano. Lo veremos si te interesa; para un archivo que cabe en RAM no es lo que domina.

**2. `to_lowercase()` asigna una `String` nueva por cada palabra**, aunque ya esté en minúsculas, y además es Unicode completo (lento) cuando probablemente te basta ASCII. Y `entry(w)` necesita una `String` propia solo para **buscar**, aunque la clave ya exista. Dos asignaciones por palabra en un bucle de cientos de millones de iteraciones.

```rust
use std::collections::HashMap;
use std::fs;

fn main() {
    let path = std::env::args().nth(1).expect("ruta");
    let text = fs::read_to_string(&path).expect("leer");
    let mut counts: HashMap<String, usize> = HashMap::with_capacity(1 << 16);

    for word in text.split_ascii_whitespace() {
        // Busca sin asignar; solo crea la String si la palabra es nueva
        if let Some(c) = counts.get_mut(word) {
            *c += 1;
        } else if word.bytes().any(|b| b.is_ascii_uppercase()) {
            *counts.entry(word.to_ascii_lowercase()).or_insert(0) += 1;
        } else {
            counts.insert(word.to_owned(), 1);
        }
    }

    let mut pairs: Vec<(String, usize)> = counts.into_iter().collect();
    pairs.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    for (w, c) in pairs.iter().take(20) {
        println!("{w} {c}");
    }
}
```

Un detalle de corrección: `get_mut(word)` busca la palabra **tal cual**, así que `Hola` no encuentra la clave `hola`. Por eso la segunda rama comprueba mayúsculas antes de insertar: `Hola`, `HOLA` y `hola` acaban todas en la misma clave, y solo la primera aparición de una palabra nueva paga una asignación. Si tu entrada es Unicode (acentos, ñ) y necesitas `to_lowercase` real, mantén la lógica pero cambia `to_ascii_lowercase` por `to_lowercase` y `is_ascii_uppercase` por `is_uppercase`.

**3. El *hasher* por defecto (SipHash) es resistente a colisiones maliciosas y por eso es lento.** Para un conteo local, `FxHashMap` (crate `rustc-hash`) o `ahash` suelen dar un 20-40 % más. Es un cambio de una línea de import, pero hazlo el último y midiendo.

**4. `sort_unstable_by` en vez de `sort_by`**: no necesitas estabilidad y el `then_with` da un orden determinista entre empates.

Cómo medir sin engañarte:

```sh
cargo build --release
time ./target/release/wordcount datos.txt > /dev/null   # redirige: imprimir también cuesta
```

Y si quieres ver dónde se va el tiempo de verdad, `cargo install flamegraph` y `cargo flamegraph --release -- datos.txt` te da un SVG; con `[profile.release] debug = 1` en `Cargo.toml` verás nombres de función en vez de direcciones. En tu caso, antes de optimizar nada, el *flamegraph* del binario de depuración habría mostrado el 80 % en comprobaciones de rango y llamadas no *inlineadas* de `HashMap`, que es la firma de «olvidé `--release`».""",
            },
            {
                "role": "user",
                "content": "Con --release bajó a 5 s. Ahora el problema es la memoria: el proceso llega a 2.5 GB. Me dijiste que se puede hacer por líneas, ¿cómo lo haría sin que se vuelva lento otra vez?",
            },
            {
                "role": "assistant",
                "content": r"""Por líneas, reutilizando **un** buffer. La trampa en la que cae casi todo el mundo es `reader.lines()`, que asigna una `String` nueva por línea; para un archivo de millones de líneas es otra vez el problema de «una asignación por elemento». `read_line` sobre el mismo `String` evita eso.

```rust
use std::collections::HashMap;
use std::fs::File;
use std::io::{self, BufRead, BufReader, BufWriter, Write};

fn main() -> io::Result<()> {
    let path = std::env::args().nth(1).expect("ruta");
    let mut reader = BufReader::with_capacity(1 << 20, File::open(&path)?); // 1 MiB
    let mut counts: HashMap<String, usize> = HashMap::with_capacity(1 << 16);
    let mut line = String::new();

    loop {
        line.clear();
        if reader.read_line(&mut line)? == 0 {
            break; // EOF
        }
        for word in line.split_ascii_whitespace() {
            if let Some(c) = counts.get_mut(word) {
                *c += 1;
            } else if word.bytes().any(|b| b.is_ascii_uppercase()) {
                *counts.entry(word.to_ascii_lowercase()).or_insert(0) += 1;
            } else {
                counts.insert(word.to_owned(), 1);
            }
        }
    }

    let mut pairs: Vec<(String, usize)> = counts.into_iter().collect();
    pairs.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    for (w, c) in pairs.iter().take(20) {
        writeln!(out, "{w} {c}")?;
    }
    out.flush()
}
```

Qué cambia y por qué no se vuelve lento:

- **Memoria**: la que ocupen las palabras distintas (el mapa) más 1 MiB de buffer más una línea. Para texto natural, el mapa son unos pocos cientos de MB como mucho; el pico de 2.5 GB desaparece.
- **`BufReader::with_capacity(1 << 20)`**: el valor por defecto son 8 KiB, lo que implica ~250 000 llamadas al sistema para 2 GB. Con 1 MiB son ~2 000. En un archivo local la diferencia es pequeña; en disco de red o contenedor se nota.
- **`line.clear()` + `read_line`**: conserva la capacidad del `String`, así que tras las primeras líneas no vuelve a asignar.
- **`read_line` incluye el `\n`**; `split_ascii_whitespace` lo ignora, así que no hace falta `trim`.
- **`BufWriter` + `stdout.lock()`**: con 20 líneas da igual, pero es el hábito correcto; `println!` bloquea y desbloquea `stdout` en cada llamada y, si la salida es una terminal, hace *flush* por línea.
- **`main` devuelve `io::Result`**: un archivo que desaparece a mitad de lectura se convierte en un error con mensaje en lugar de un `expect` que hace *panic*.

Un detalle de corrección respecto a la versión anterior: una palabra partida por un `\n` nunca existe, porque `split_whitespace` ya cortaba en saltos de línea. Así que el resultado es idéntico; puedes comprobarlo con `diff <(./v1 datos.txt) <(./v2 datos.txt)` antes de quedarte con la nueva.

Y si el archivo contiene líneas enormes (un JSON de una sola línea de 2 GB), `read_line` se comporta igual que `read_to_string`; para eso tendrías que leer bloques con `read` y manejar la palabra cortada en el borde del bloque. Para texto con líneas normales no lo necesitas.

Tiempo esperado: igual o ligeramente mejor que los 5 s, porque la lectura por bloques se solapa con el conteo en vez de hacer primero 2 GB de lectura y luego 2 GB de procesamiento.""",
            },
        ]
    },
    # 27) Implementar Iterator e IntoIterator para una colección propia
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo una rejilla 2D guardada en un `Vec` plano:

```rust
pub struct Grid<T> {
    width: usize,
    height: usize,
    cells: Vec<T>,
}
```

Quiero poder hacer `for cell in &grid`, recorrer filas, y tener un método `neighbors(x, y)` que devuelva un iterador sobre las 4 celdas vecinas sin salirse. Ahora mismo `neighbors` devuelve un `Vec<&T>` y me parece feo. ¿Cómo se implementa un iterador «de verdad»?""",
            },
            {
                "role": "assistant",
                "content": r"""Tres iteradores distintos, y cada uno se implementa de la forma más barata que le sirve:

- **Todas las celdas**: delega en el iterador de `Vec`. No escribas un struct para lo que `slice::Iter` ya hace.
- **Filas**: `chunks_exact(width)` es exactamente «filas de un `Vec` plano».
- **Vecinos**: un adaptador sobre un *array* de 4 desplazamientos con `filter_map`. Tampoco necesita struct.

Solo cuando el iterador tiene **estado propio** que no sale de combinar adaptadores vale la pena implementar `Iterator` a mano; te enseño uno al final para que veas la forma.

```rust
pub struct Grid<T> {
    width: usize,
    height: usize,
    cells: Vec<T>,
}

impl<T> Grid<T> {
    pub fn new(width: usize, height: usize, fill: T) -> Self
    where
        T: Clone,
    {
        Self { width, height, cells: vec![fill; width * height] }
    }

    pub fn get(&self, x: usize, y: usize) -> Option<&T> {
        (x < self.width && y < self.height).then(|| &self.cells[y * self.width + x])
    }

    /// Todas las celdas en orden de fila.
    pub fn iter(&self) -> std::slice::Iter<'_, T> {
        self.cells.iter()
    }

    /// Cada fila como un slice.
    pub fn rows(&self) -> impl ExactSizeIterator<Item = &[T]> {
        self.cells.chunks_exact(self.width)
    }

    /// Las celdas vecinas (arriba, abajo, izquierda, derecha) que existen.
    pub fn neighbors(&self, x: usize, y: usize) -> impl Iterator<Item = &T> {
        const OFFSETS: [(isize, isize); 4] = [(0, -1), (0, 1), (-1, 0), (1, 0)];
        OFFSETS.into_iter().filter_map(move |(dx, dy)| {
            let nx = x.checked_add_signed(dx)?;
            let ny = y.checked_add_signed(dy)?;
            self.get(nx, ny)
        })
    }
}

/// Permite `for cell in &grid`.
impl<'a, T> IntoIterator for &'a Grid<T> {
    type Item = &'a T;
    type IntoIter = std::slice::Iter<'a, T>;

    fn into_iter(self) -> Self::IntoIter {
        self.cells.iter()
    }
}
```

Decisiones:

- **`neighbors` devuelve `impl Iterator<Item = &T>`**, no `Vec<&T>`: cero asignaciones y el llamador decide si recoge, cuenta o se detiene en el primero. El `move` en la *closure* captura `x`, `y` (que son `Copy`) y `self` (que es `&Grid`, también `Copy`), así que el iterador vive mientras viva el préstamo de `self`; en edición 2024 ese lifetime se captura automáticamente, en 2021 también porque `self` ya está en la firma.
- **`checked_add_signed`** convierte «me salgo por abajo de 0» en `None` sin aritmética con `isize` sucia; el `?` dentro de `filter_map` descarta ese vecino. El límite superior lo filtra `get`.
- **`ExactSizeIterator` en `rows`**: `chunks_exact` lo implementa, y así quien llama puede hacer `rows().len()` sin consumir.
- **`IntoIterator for &Grid<T>`** es lo que hace funcionar el `for`. No implementes `IntoIterator for Grid<T>` por valor a menos que quieras que el `for grid` consuma la rejilla; normalmente no.

**Cuándo sí escribes un `Iterator` a mano.** Cuando el estado no es «índice sobre una colección existente». Ejemplo: coordenadas `(x, y)` de todas las celdas, que no están almacenadas en ningún sitio:

```rust
pub struct Coords {
    width: usize,
    next: usize,
    end: usize,
}

impl Iterator for Coords {
    type Item = (usize, usize);

    fn next(&mut self) -> Option<Self::Item> {
        if self.next >= self.end {
            return None;
        }
        let i = self.next;
        self.next += 1;
        Some((i % self.width, i / self.width))
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let restantes = self.end - self.next;
        (restantes, Some(restantes))
    }
}

impl ExactSizeIterator for Coords {}

impl<T> Grid<T> {
    pub fn coords(&self) -> Coords {
        Coords { width: self.width, next: 0, end: self.cells.len() }
    }
}
```

Solo hay que implementar `next`; `map`, `filter`, `zip`, `collect` y el resto vienen gratis. `size_hint` es opcional, pero hace que `collect::<Vec<_>>()` reserve el tamaño exacto, y permite `ExactSizeIterator`. Con `grid.coords().zip(grid.iter())` tienes `((x, y), &celda)` sin ninguna asignación intermedia.

Comprobación:

```rust
#[test]
fn vecinos_en_esquina_y_centro() {
    let g = Grid::new(3, 3, 0u8);
    assert_eq!(g.neighbors(0, 0).count(), 2);
    assert_eq!(g.neighbors(1, 1).count(), 4);
    assert_eq!(g.neighbors(2, 1).count(), 3);
    assert_eq!(g.rows().len(), 3);
    assert_eq!(g.coords().last(), Some((2, 2)));
    assert_eq!((&g).into_iter().count(), 9);
}
```

Si más adelante necesitas los 8 vecinos (diagonales), solo cambia la constante `OFFSETS`; el resto del código no se entera.""",
            },
        ]
    },
    # 28) E0277 Display: {} vs {:?}, derive Debug, impl Display, Eq+Hash para clave. Principiante
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Hola, estoy aprendiendo Rust y me sale este error con un struct de lo más simple:

```
error[E0277]: `Point` doesn't implement `std::fmt::Display`
 --> src/main.rs:8:20
  |
8 |     println!("{}", p);
  |                    ^ `Point` cannot be formatted with the default formatter
  |
  = help: the trait `std::fmt::Display` is not implemented for `Point`
  = note: in format strings you may be able to use `{:?}` (or {:#?} for pretty-print) instead
```

```rust
struct Point {
    x: i32,
    y: i32,
}

fn main() {
    let p = Point { x: 1, y: 2 };
    println!("{}", p);
}
```

En Python imprimir un objeto siempre funciona. ¿Por qué aquí no?""",
            },
            {
                "role": "assistant",
                "content": r"""Porque Rust no inventa una representación por ti: tienes que decir cómo se imprime un tipo. Hay dos formas de imprimir, y corresponden a dos *traits* distintos:

| Formato | Trait | Para quién | Cómo se obtiene |
|---|---|---|---|
| `{:?}` | `Debug` | el programador (logs, tests) | `#[derive(Debug)]` |
| `{}` | `Display` | el usuario final | lo escribes tú |

El compilador te lo sugiere en la nota: con `{:?}` y un `derive` ya funciona.

```rust
#[derive(Debug)]
struct Point {
    x: i32,
    y: i32,
}

fn main() {
    let p = Point { x: 1, y: 2 };
    println!("{:?}", p);   // Point { x: 1, y: 2 }
    println!("{:#?}", p);  // lo mismo, con saltos de línea e indentación
}
```

Es el equivalente de `__repr__` en Python: una representación para depurar, generada automáticamente a partir de los campos. **Pon `#[derive(Debug)]` en casi todos tus structs**; lo necesitas para `assert_eq!`, para `unwrap()` en `Result` con tu tipo de error y para `dbg!`.

Si quieres que `{}` funcione (el equivalente de `__str__`), implementas `Display` a mano, porque solo tú sabes cómo debe verse un punto para una persona:

```rust
use std::fmt;

impl fmt::Display for Point {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "({}, {})", self.x, self.y)
    }
}

// println!("{}", p)  →  (1, 2)
```

`Display` no se puede derivar a propósito: no hay una forma «correcta» universal de mostrar un dato a un usuario, y Rust prefiere que lo decidas a generar algo que luego cambie la salida de tu programa sin que te enteres. Implementar `Display` además te da `to_string()` gratis: `let s = p.to_string();`.

Con esto te vas a cruzar con el mismo patrón en otros sitios. Los *traits* que se derivan con `#[derive(...)]` y para qué sirven:

- `Clone`: poder hacer `p.clone()`. `Copy` (requiere `Clone`): que `let q = p;` copie en vez de mover; apto para tipos pequeños como este `Point`.
- `PartialEq`, `Eq`: poder comparar con `==` y usar `assert_eq!`.
- `Hash` (con `Eq`): poder usarlo como clave de `HashMap` o en un `HashSet`.
- `PartialOrd`, `Ord`: poder ordenar con `sort()` y comparar con `<`.
- `Default`: `Point::default()` con todos los campos a cero.

Para un punto de coordenadas enteras, lo habitual es:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
struct Point {
    x: i32,
    y: i32,
}
```

Y cuando veas en el futuro un error del tipo «the trait `Hash` is not implemented for `Point`» al meterlo en un `HashSet`, ya sabes que es el mismo mensaje con otro *trait*: añade el `derive` que falta.

Comprobación de que todo encaja:

```rust
fn main() {
    let p = Point { x: 1, y: 2 };
    let q = p;                      // copia, p sigue siendo usable gracias a Copy
    assert_eq!(p, q);               // PartialEq + Debug (para el mensaje de fallo)
    println!("{p} y {q:?}");        // Display y Debug; desde Rust 2021 las variables van dentro de las llaves
    let mut set = std::collections::HashSet::new();
    set.insert(p);                  // Hash + Eq
    assert!(set.contains(&Point { x: 1, y: 2 }));
}
```""",
            },
        ]
    },
    # 29) E0521 al hacer spawn con datos prestados: thread::scope y rayon. System variante (México)
    {
        "messages": [
            {"role": "system", "content": "Responde en español de México, con ejemplos cortos y sin rodeos."},
            {
                "role": "user",
                "content": r"""Quiero sumar un slice grande en dos hilos y el compilador no me deja:

```rust
fn total(data: &[u64]) -> u64 {
    let (a, b) = data.split_at(data.len() / 2);
    let h = std::thread::spawn(move || a.iter().sum::<u64>());
    let sb: u64 = b.iter().sum();
    h.join().unwrap() + sb
}
```

```
error[E0521]: borrowed data escapes outside of function
 --> src/main.rs:3:13
  |
1 | fn total(data: &[u64]) -> u64 {
  |          ----  - let's call the lifetime of this reference `'1`
  |          |
  |          `data` is a reference that is only valid in the function body
2 |     let (a, b) = data.split_at(data.len() / 2);
3 |     let h = std::thread::spawn(move || a.iter().sum::<u64>());
  |             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  |             |
  |             `data` escapes the function body here
  |             argument requires that `'1` must outlive `'static`
```

Yo hago `join()` antes de salir, entonces el hilo nunca sobrevive a `data`. ¿Por qué no lo entiende?""",
            },
            {
                "role": "assistant",
                "content": r"""Tienes razón en los hechos y el compilador tiene razón en la firma. `std::thread::spawn` exige `F: 'static` porque **no sabe que vas a hacer `join`**: la firma permite soltar el `JoinHandle` y dejar el hilo corriendo para siempre, y en ese caso `a` apuntaría a memoria liberada. El compilador no analiza lo que haces después; revisa el contrato de `spawn`, y ese contrato dice «nada prestado».

La herramienta para exactamente tu caso es `std::thread::scope` (estable desde 1.63): los hilos creados dentro del *scope* se unen automáticamente al salir, así que el compilador **sí** sabe que no sobreviven a `data` y acepta préstamos.

```rust
fn total(data: &[u64]) -> u64 {
    let (a, b) = data.split_at(data.len() / 2);
    std::thread::scope(|s| {
        let ha = s.spawn(|| a.iter().sum::<u64>());
        let sb: u64 = b.iter().sum();
        ha.join().unwrap() + sb
    })
}
```

Tres cosas a notar:

- Ya no hace falta `move`: la *closure* toma `a` por referencia, que es lo que querías.
- El *scope* devuelve el valor de la *closure*, por eso la función termina en él.
- Si un hilo hace *panic*, `join()` devuelve `Err` y el `unwrap` propaga el *panic*; si prefieres convertirlo en error, haz `match` sobre el resultado.

Para N hilos en vez de dos, reparte en `chunks` y junta los `handles`:

```rust
fn total_n(data: &[u64], threads: usize) -> u64 {
    let chunk = data.len().div_ceil(threads).max(1);
    std::thread::scope(|s| {
        let handles: Vec<_> = data
            .chunks(chunk)
            .map(|c| s.spawn(move || c.iter().sum::<u64>()))
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).sum()
    })
}
```

Aquí el `move` sí va: cada *closure* necesita su propio `c` (que es `&[u64]`, barato de copiar), no un préstamo compartido de la variable `c` del `map`.

**Si esto es un patrón recurrente, usa rayon.** Reparte el trabajo entre un *pool* del tamaño de tus núcleos, balancea *chunks* desiguales y te ahorra el código de arriba:

```rust
use rayon::prelude::*;

fn total_par(data: &[u64]) -> u64 {
    data.par_iter().sum()
}
```

Rayon también usa internamente préstamos con *scope*; por eso `par_iter()` acepta tu `&[u64]` sin `'static`.

**Cuándo compensa.** Sumar `u64` es tan barato que, con menos de unos cuantos millones de elementos, crear hilos cuesta más que el trabajo. Mídelo antes de dejarlo en paralelo:

```rust
#[test]
fn versiones_coinciden() {
    let data: Vec<u64> = (1..=1_000_000).collect();
    let esperado = 1_000_000u64 * 1_000_001 / 2;
    assert_eq!(total(&data), esperado);
    assert_eq!(total_n(&data, 8), esperado);
    assert_eq!(total_n(&[], 8), 0);
    assert_eq!(total_par(&data), esperado);
}
```

El caso `&[]` está ahí porque `chunks(0)` hace *panic*; el `.max(1)` lo evita. Y un detalle de corrección en todas las versiones: `sum::<u64>()` hace *panic* por desbordamiento en modo *debug* y da la vuelta en *release*. Si los valores pueden ser grandes, usa `u128` para acumular o `try_fold` con `checked_add`.""",
            },
        ]
    },
    # 30) Ergonomía de APIs: AsRef, Into<String>, IntoIterator, From, builder por valor
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Estoy diseñando la API pública de un crate interno y me pierdo con las firmas. ¿Cuándo pongo `&str`, `String`, `impl Into<String>`, `impl AsRef<str>` o `impl AsRef<Path>`? Me da la sensación de que cada crate famoso lo hace distinto. Ejemplo concreto: un `Client::new(base_url, token)` y un `Client::get(path)`.""",
            },
            {
                "role": "assistant",
                "content": r"""La regla que resuelve el 90 %: **mira qué hace la función con el valor**.

| La función... | Parámetro | Por qué |
|---|---|---|
| solo lo lee | `&str` / `&[T]` / `&Path` | préstamo, cero coste, acepta `String`, `&String`, literales |
| se lo queda (lo guarda en un struct, lo devuelve) | `String` / `Vec<T>` / `PathBuf` | quien llama decide si mueve o clona; sin copias ocultas |
| se lo queda y quieres que `"literal"` funcione sin `.to_string()` | `impl Into<String>` | azúcar para el llamador; una conversión en el borde |
| lo lee y quieres aceptar `String`, `&str`, `OsString`, `PathBuf`... | `impl AsRef<str>` / `impl AsRef<Path>` | flexibilidad sin asignar |
| lo recorre una vez | `impl IntoIterator<Item = T>` | acepta `Vec`, *arrays*, *slices*, iteradores, sin `collect` previo |

Aplicado a tu `Client`:

```rust
use std::path::Path;
use std::time::Duration;

pub struct Client {
    base_url: String,
    token: String,
    timeout: Duration,
}

impl Client {
    /// `new` se queda con los dos valores: `Into<String>` deja escribir literales.
    pub fn new(base_url: impl Into<String>, token: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            token: token.into(),
            timeout: Duration::from_secs(30),
        }
    }

    /// `get` solo lee la ruta: `&str`. Nada que ganar con genéricos.
    pub fn get(&self, path: &str) -> Result<Response, Error> {
        let url = format!("{}/{}", self.base_url.trim_end_matches('/'), path.trim_start_matches('/'));
        self.send(Request { method: Method::Get, url, body: None })
    }

    /// Una ruta de archivo de solo lectura: `AsRef<Path>` acepta &str, String, PathBuf, &Path.
    pub fn upload(&self, path: impl AsRef<Path>) -> Result<Response, Error> {
        let bytes = std::fs::read(path.as_ref())?;
        self.send(Request { method: Method::Post, url: self.url("upload"), body: Some(bytes) })
    }

    /// Varias cabeceras de golpe: cualquier colección o iterador de pares.
    pub fn with_headers<I, K, V>(mut self, headers: I) -> Self
    where
        I: IntoIterator<Item = (K, V)>,
        K: Into<String>,
        V: Into<String>,
    {
        for (k, v) in headers {
            self.headers.push((k.into(), v.into()));
        }
        self
    }
}
```

(Asumo `Response`, `Error`, `Request`, `Method`, `send` y un campo `headers: Vec<(String, String)>` definidos en el crate; no cambian el argumento.)

Por qué cada elección:

- **`new` con `impl Into<String>` y no `&str`**: con `&str` la función tendría que clonar *siempre*, incluso cuando el llamador ya tiene una `String` que no va a usar más. Con `Into<String>`, `Client::new("https://api", token)` compila sin `.to_string()` y `Client::new(url_string, token)` mueve sin copiar. El coste es que `impl Trait` en argumentos monomorfiza una versión por tipo; en un constructor da igual.
- **`get` con `&str` y no `impl AsRef<str>`**: no guarda nada, así que `&str` basta; `AsRef<str>` solo añadiría flexibilidad para tipos que casi nadie pasa (`Box<str>`, `Rc<str>`) a cambio de una firma más ruidosa y de perder `path: &str` en la documentación. Reserva `AsRef` para `Path` y `OsStr`, donde la variedad de tipos de entrada es real.
- **`upload` con `AsRef<Path>`**: es la firma que usa la propia biblioteca estándar (`fs::read`, `File::open`), y por eso tu función se integra con cualquier cosa que ya funcione ahí.
- **`with_headers` por valor (`mut self`) y devolviendo `Self`**: el patrón *builder* encadenable. Si el *builder* va a tener un `build()` que puede fallar, devuelve `Result` solo ahí, no en cada paso.

Dos reglas más que evitan los errores habituales:

1. **No uses `impl Into<T>` en funciones que solo leen.** Obliga al llamador a ceder propiedad (o a clonar) sin motivo.
2. **En *traits* públicos y en punteros a función, prefiere tipos concretos.** `impl Trait` no se puede usar en *trait objects* ni nombrar en un `fn(&str) -> ...`; una firma con `&str` es más fácil de implementar y de simular en tests.

Comprobación de que la API acepta lo que prometes, como test de compilación:

```rust
#[test]
fn acepta_todas_las_formas() {
    let token = String::from("t");
    let c = Client::new("https://api.example", &token)      // &String -> Into<String> vía &str
        .with_headers([("Accept", "application/json")])     // array de &str
        .with_headers(vec![(String::from("X-A"), String::from("1"))]); // Vec de String
    let _ = c.get("/users");
    let _ = c.get(&format!("/users/{}", 7));
    let _ = c.upload("fixtures/a.bin");
    let _ = c.upload(std::path::PathBuf::from("fixtures/a.bin"));
}
```

Si una de esas líneas no compila, la firma correspondiente es más estrecha de lo que quieres; el test documenta el contrato mejor que el `rustdoc`.""",
            },
        ]
    },
]
