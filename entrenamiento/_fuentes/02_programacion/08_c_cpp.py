"""C (C11/C17: punteros, memoria, strings, structs, UB, valgrind/ASan, Makefile) y C++ (17/20: RAII,
smart pointers, move, const, templates y concepts, STL, optional/variant, errores, lambdas, reglas 0/3/5,
CMake, sanitizers, errores clásicos). Varias filas con segfaults y trazas de sanitizers."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) C: decaimiento de arrays a punteros, sizeof en parámetros, aritmética de punteros (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""En C, ¿por qué `sizeof(arr) / sizeof(arr[0])` me da 10 en `main` pero 2 dentro de la función a la que le paso el array? Estoy en Linux de 64 bits.

```c
#include <stdio.h>

void print_len(int arr[]) {
    printf("%zu\n", sizeof(arr) / sizeof(arr[0]));
}

int main(void) {
    int data[10] = {0};
    printf("%zu\n", sizeof(data) / sizeof(data[0]));  // 10
    print_len(data);                                  // 2
    return 0;
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Porque dentro de `print_len`, `arr` **no es un array: es un puntero**. En C un parámetro declarado como `int arr[]` (o incluso `int arr[10]`) se ajusta a `int *arr`. Y al pasar `data`, el array «decae» a un puntero a su primer elemento. La función recibe una dirección y nada más: el tamaño se pierde en la llamada.

Las cuentas en tu máquina:

- En `main`: `sizeof(data)` = 10 × 4 bytes = 40; 40 / 4 = **10**.
- En `print_len`: `sizeof(arr)` = tamaño de un `int *` = 8 bytes; 8 / 4 = **2**.

El compilador ya te avisa si compilas con avisos activados. GCC muestra algo como «'sizeof' on array function parameter 'arr' will return size of 'int *'» (`-Wsizeof-array-argument`, activo por defecto). Compila siempre con `-Wall -Wextra`.

**La solución idiomática es pasar la longitud explícitamente:**

```c
#include <stddef.h>
#include <stdio.h>

#define ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))

static long sum(const int *values, size_t len) {
    long total = 0;
    for (const int *p = values; p != values + len; ++p) {
        total += *p;
    }
    return total;
}

int main(void) {
    int data[] = {3, 1, 4, 1, 5};
    printf("len=%zu sum=%ld\n", ARRAY_LEN(data), sum(data, ARRAY_LEN(data)));
    printf("data=%p data+1=%p &data+1=%p\n",
           (void *)data, (void *)(data + 1), (void *)(&data + 1));
    return 0;
}
```

Sobre ese código:

- **`ARRAY_LEN` solo funciona donde el array es visible como array** (su declaración está en el mismo ámbito). Usado sobre un puntero da un resultado incorrecto en silencio; GCC avisa con `-Wsizeof-pointer-div`, incluido en `-Wall`.
- **`const int *`**: la función promete no modificar los datos, y el compilador lo hace cumplir.

**Aritmética de punteros**, que es lo que hace el bucle:

- `values + len` avanza `len` *elementos*, no bytes: el compilador multiplica por `sizeof(int)`. Por eso `data + 1` está 4 bytes después de `data`.
- `&data` tiene otro tipo, `int (*)[5]` (puntero a un array de 5 `int`), así que `&data + 1` avanza el array entero: **20 bytes**. Mismo valor numérico que `data`, distinto tipo, distinta aritmética. La segunda línea del `printf` lo muestra.
- El puntero «uno después del final» (`values + len`) es válido para comparar, pero no para leer. Calcular uno más allá ya es comportamiento indefinido, aunque no lo leas.

Comprobación: la salida debe ser `len=5 sum=14`, y en la segunda línea `data+1` debe estar 4 bytes por encima de `data` y `&data+1`, 20 bytes por encima (en hexadecimal, `+0x4` y `+0x14`).""",
            },
        ]
    },
    # 2) C: diseño de ownership con malloc/free por convención, tipo opaco, realloc seguro. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy escribiendo una pequeña librería en C: un buffer dinámico de bytes. ¿Cómo diseño quién reserva y quién libera la memoria para que no haya fugas ni dobles free? ¿Y cómo se usa realloc correctamente?",
            },
            {
                "role": "assistant",
                "content": r"""En C la propiedad de la memoria no la comprueba el compilador: es una **convención** que tu API tiene que hacer evidente. Las reglas que funcionan:

1. **Simetría**: quien crea, destruye. Cada `x_create` tiene su `x_destroy`, y el usuario nunca llama a `free` sobre algo que devolvió tu librería.
2. **Tipo opaco**: el usuario solo ve `bytebuf *`, no los campos. Así no puede liberar `buf->data` por su cuenta ni guardar punteros internos que luego se invaliden.
3. **Cada función documenta qué hace con la propiedad**: *toma posesión*, *presta* (puntero válido hasta cierto momento) o *devuelve algo que hay que liberar*.
4. **`destroy` acepta `NULL`**, igual que `free`, para simplificar los caminos de error.

Cabecera:

```c
/* bytebuf.h */
#ifndef BYTEBUF_H
#define BYTEBUF_H

#include <stddef.h>

typedef struct bytebuf bytebuf;

/* Crea un buffer vacío. El llamador es su dueño y debe liberarlo con
   bytebuf_destroy. Devuelve NULL si no hay memoria. */
bytebuf *bytebuf_create(size_t initial_capacity);

/* Libera el buffer y su contenido. Acepta NULL. */
void bytebuf_destroy(bytebuf *buf);

/* Copia len bytes de data al final. No toma posesión de data.
   Devuelve 0, o -1 si no hay memoria (el buffer queda intacto). */
int bytebuf_append(bytebuf *buf, const void *data, size_t len);

/* Puntero prestado: válido hasta la siguiente llamada que modifique buf. */
const unsigned char *bytebuf_data(const bytebuf *buf);
size_t bytebuf_len(const bytebuf *buf);

#endif
```

Implementación:

```c
/* bytebuf.c */
#include "bytebuf.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

struct bytebuf {
    unsigned char *data;
    size_t len;
    size_t cap;
};

bytebuf *bytebuf_create(size_t initial_capacity) {
    bytebuf *buf = malloc(sizeof *buf);
    if (buf == NULL) {
        return NULL;
    }
    buf->len = 0;
    buf->cap = initial_capacity > 0 ? initial_capacity : 16;
    buf->data = malloc(buf->cap);
    if (buf->data == NULL) {
        free(buf);
        return NULL;
    }
    return buf;
}

void bytebuf_destroy(bytebuf *buf) {
    if (buf == NULL) {
        return;
    }
    free(buf->data);
    free(buf);
}

static int grow(bytebuf *buf, size_t needed) {
    size_t new_cap = buf->cap;
    while (new_cap < needed) {
        if (new_cap > SIZE_MAX / 2) {
            return -1;
        }
        new_cap *= 2;
    }
    unsigned char *tmp = realloc(buf->data, new_cap);
    if (tmp == NULL) {
        return -1; /* buf->data sigue siendo válido y sigue siendo nuestro */
    }
    buf->data = tmp;
    buf->cap = new_cap;
    return 0;
}

int bytebuf_append(bytebuf *buf, const void *data, size_t len) {
    if (len == 0) {
        return 0;
    }
    if (len > SIZE_MAX - buf->len) {
        return -1;
    }
    size_t needed = buf->len + len;
    if (needed > buf->cap && grow(buf, needed) != 0) {
        return -1;
    }
    memcpy(buf->data + buf->len, data, len);
    buf->len = needed;
    return 0;
}

const unsigned char *bytebuf_data(const bytebuf *buf) { return buf->data; }
size_t bytebuf_len(const bytebuf *buf) { return buf->len; }
```

**`realloc`**, que es donde más se falla:

- **Nunca `p = realloc(p, n)`.** Si `realloc` falla devuelve `NULL` *sin liberar el bloque original*; al sobrescribir `p` pierdes la única referencia y tienes una fuga. Usa un temporal, como en `grow`.
- **El bloque puede moverse.** Cualquier puntero a los datos antiguos queda colgando tras un `realloc` con éxito. Por eso `bytebuf_data` documenta que el puntero es prestado «hasta la siguiente modificación».
- **Comprueba desbordamientos antes de calcular tamaños.** `buf->len + len` o `cap * 2` pueden dar la vuelta y producir una reserva pequeña seguida de una escritura enorme. Las dos comprobaciones contra `SIZE_MAX` lo impiden.
- **Crecer multiplicando** (×2) da coste amortizado O(1) por `append`; crecer sumando una cantidad fija lo convierte en O(n).

Tras un `bytebuf_destroy(buf)`, `buf` queda colgando: eso es responsabilidad del llamador. Si quieres ayudarle, ofrece `void bytebuf_destroy_and_clear(bytebuf **buf)` que libere y ponga `*buf = NULL`.

Comprobación, compilando con sanitizers para que detecten fugas y accesos fuera de rango:

```c
/* test_bytebuf.c */
#include <assert.h>
#include <string.h>

#include "bytebuf.h"

int main(void) {
    bytebuf *buf = bytebuf_create(1);
    assert(buf != NULL);
    for (int i = 0; i < 1000; ++i) {
        assert(bytebuf_append(buf, "ab", 2) == 0);
    }
    assert(bytebuf_len(buf) == 2000);
    assert(memcmp(bytebuf_data(buf) + 1998, "ab", 2) == 0);
    bytebuf_destroy(buf);
    bytebuf_destroy(NULL);
    return 0;
}
```

```sh
gcc -std=c17 -Wall -Wextra -g -fsanitize=address,undefined bytebuf.c test_bytebuf.c -o test_bytebuf
./test_bytebuf && echo OK
```

Si comentas el `bytebuf_destroy(buf)`, LeakSanitizer (activo por defecto con ASan en Linux) informa al salir de los bytes perdidos y de dónde se reservaron.""",
            },
        ]
    },
    # 3) C: strings seguros: strcpy/strncpy/snprintf/fgets; multiturno sobre strlcpy y glibc 2.38
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuál es la forma segura de copiar y concatenar strings en C? Me dijeron que strcpy es peligroso y que use strncpy, pero también leí que strncpy tampoco es seguro. Estoy confundido.",
            },
            {
                "role": "assistant",
                "content": r"""Las dos advertencias son ciertas. `strcpy` no conoce el tamaño del destino y escribe hasta encontrar el `'\0'` del origen: si no cabe, desborda el buffer. Y `strncpy` **no es una versión segura de `strcpy`**: se diseñó para campos de ancho fijo y tiene dos defectos para strings normales:

1. Si el origen tiene `n` caracteres o más, **no escribe el `'\0'` final**. El destino queda sin terminar y el siguiente `printf` o `strlen` lee más allá.
2. Si el origen es corto, **rellena con ceros** todo el resto del destino: copiar `"a"` en un buffer de 4 KiB escribe 4 KiB.

La herramienta estándar que sí sirve es **`snprintf`**: siempre termina en `'\0'` (si el tamaño es mayor que 0) y te dice cuánto *habría* escrito, lo que permite detectar el truncamiento.

```c
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

/* Copia src en dst. Devuelve false si no cabía (dst queda truncado y terminado). */
static bool copy_str(char *dst, size_t dst_size, const char *src) {
    int written = snprintf(dst, dst_size, "%s", src);
    return written >= 0 && (size_t)written < dst_size;
}

/* Añade src al final del string que ya hay en dst. */
static bool append_str(char *dst, size_t dst_size, const char *src) {
    size_t used = strnlen(dst, dst_size);
    if (used == dst_size) {
        return false; /* dst no estaba terminado: no tocamos nada */
    }
    return copy_str(dst + used, dst_size - used, src);
}

int main(void) {
    char path[16];
    if (!copy_str(path, sizeof path, "/var/log/")) {
        return 1;
    }
    if (!append_str(path, sizeof path, "aplicacion.log")) {
        fprintf(stderr, "ruta demasiado larga, truncada a: %s\n", path);
        return 1;
    }
    puts(path);
    return 0;
}
```

Con 16 bytes, `"/var/log/aplicacion.log"` (23 caracteres) no cabe: el programa informa del truncamiento en vez de corromper memoria. Con `char path[32]` imprime la ruta completa. Esa es la prueba de las dos ramas.

`strnlen` es POSIX (y C23); en Windows con MSVC existe también. Si necesitas C17 estricto sin POSIX, sustitúyelo por `memchr(dst, '\0', dst_size)`.

Para leer líneas, el mismo criterio:

```c
char line[256];
if (fgets(line, sizeof line, stdin) != NULL) {
    line[strcspn(line, "\n")] = '\0'; /* quita el salto de línea si lo hay */
}
```

`fgets` respeta el tamaño y termina en `'\0'`; si la línea era más larga, el resto queda en el flujo para la siguiente llamada. Y nunca `gets` (eliminada en C11) ni `scanf("%s", buf)` sin ancho: usa `scanf("%255s", buf)` con el ancho igual al tamaño menos uno.

Regla general: **toda función que escribe en un buffer debe recibir su tamaño**, y toda llamada debe comprobar si hubo truncamiento. Un string truncado en silencio (una ruta, un nombre de usuario) es un error lógico que puede ser tan grave como el desbordamiento.""",
            },
            {
                "role": "user",
                "content": "¿Y strlcpy? Lo vi en código de BSD y parece justo lo que quiero, pero en mi Linux no compilaba.",
            },
            {
                "role": "assistant",
                "content": r"""`strlcpy` y `strlcat` vienen de OpenBSD y hacen lo que buscas: copian como mucho `size - 1` caracteres, siempre terminan en `'\0'` y devuelven la longitud del origen, así que el truncamiento se detecta comparando:

```c
if (strlcpy(dst, src, sizeof dst) >= sizeof dst) {
    /* truncado */
}
```

Por qué no te compilaba: **glibc no las incluyó hasta la versión 2.38** (2023). Hoy también forman parte de POSIX.1-2024. Depende de tu distribución:

- **glibc 2.38 o superior** (Debian 13, Ubuntu 24.04, Fedora 39 y posteriores): están en `<string.h>`. Si compilas con `-std=c17` estricto, puede que la cabecera no las declare; añade `-D_DEFAULT_SOURCE`, o usa `-std=gnu17`.
- **glibc anterior**: la librería `libbsd` las ofrece (`#include <bsd/string.h>` y enlazar con `-lbsd`).
- **macOS y los BSD**: siempre han estado.
- **Windows/MSVC**: no existen; allí la alternativa es `strcpy_s`, del Anexo K, que casi nadie más implementa.

Comprueba tu versión con `ldd --version`.

Si tu código tiene que compilar en todas partes, la opción más simple es tu propia función con la misma semántica:

```c
#include <string.h>

/* Misma semántica que strlcpy: devuelve strlen(src). Truncado si el resultado >= dst_size. */
static size_t copy_trunc(char *dst, size_t dst_size, const char *src) {
    size_t src_len = strlen(src);
    if (dst_size > 0) {
        size_t n = src_len < dst_size - 1 ? src_len : dst_size - 1;
        memcpy(dst, src, n);
        dst[n] = '\0';
    }
    return src_len;
}
```

Una limitación que comparten `strlcpy` y esta versión: **recorren el origen entero** para calcular su longitud, aunque copien solo unos bytes. Con un origen enorme, cuesta; con un origen sin terminar (datos que vienen de la red, por ejemplo), lee fuera de rango. Para datos no confiables, usa `strnlen(src, max)` para acotar la lectura antes de copiar.

Comprobación de las dos ramas:

```c
char small[4];
assert(copy_trunc(small, sizeof small, "abc") == 3 && strcmp(small, "abc") == 0);
assert(copy_trunc(small, sizeof small, "abcdef") == 6 && strcmp(small, "abc") == 0);
```

El primer caso cabe justo (3 caracteres + `'\0'`); el segundo devuelve 6 ≥ 4, que es la señal de truncamiento, y deja `"abc"` correctamente terminado.""",
            },
        ]
    },
    # 4) C: traza de AddressSanitizer heap-buffer-overflow por malloc(strlen(s)) sin +1
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Activé ASan en el proyecto y me salta esto en una función que lleva años en producción sin dar problemas:

```c
char *dup_upper(const char *s) {
    char *out = malloc(strlen(s));
    for (size_t i = 0; i <= strlen(s); i++) {
        out[i] = toupper((unsigned char)s[i]);
    }
    return out;
}
```

```
=================================================================
==48213==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x502000000015 at pc 0x55d4c3a1b2f4 bp 0x7ffd8a3c1e70 sp 0x7ffd8a3c1e68
WRITE of size 1 at 0x502000000015 thread T0
    #0 0x55d4c3a1b2f3 in dup_upper src/text.c:9
    #1 0x55d4c3a1b45a in main src/main.c:14

0x502000000015 is located 0 bytes after 5-byte region [0x502000000010,0x502000000015)
allocated by thread T0 here:
    #0 0x7f1e2c8b4887 in malloc
    #1 0x55d4c3a1b2a1 in dup_upper src/text.c:7
    #2 0x55d4c3a1b45a in main src/main.c:14

SUMMARY: AddressSanitizer: heap-buffer-overflow src/text.c:9 in dup_upper
```

¿Es un falso positivo? Nunca ha fallado.""",
            },
            {
                "role": "assistant",
                "content": r"""No es un falso positivo: ASan casi nunca los da con `heap-buffer-overflow`. La traza dice exactamente qué pasa; se lee así:

1. **`WRITE of size 1`**: se escribe un byte (un `char`).
2. **`0 bytes after 5-byte region`**: el bloque mide 5 bytes y la escritura cae justo en el byte siguiente, el índice 5. Un clásico «uno de más».
3. **`allocated ... text.c:7`**: el bloque es el `malloc(strlen(s))`. Con `s = "hello"`, reserva 5 bytes.
4. **`text.c:9`**: la escritura es `out[i] = ...` con `i == 5`, que es cuando el bucle copia el `'\0'` (por eso el `<=`).

El bug: **`malloc(strlen(s))` no reserva sitio para el terminador**. El bucle copia 6 bytes (5 letras + `'\0'`) en 5.

**Por qué «nunca ha fallado»**: `malloc` redondea las reservas hacia arriba (en glibc de 64 bits, el bloque mínimo útil es de 24 bytes), así que ese byte extra caía en relleno que nadie usaba. Funcionaba por casualidad. Con una cadena cuya longitud coincida con el límite de un bloque, o con otro asignador (`jemalloc`, `musl`), el byte pisa los metadatos del bloque siguiente y el programa falla más tarde, en otra parte, en un `free` aparentemente inocente. Ese es el peor tipo de bug de memoria: la causa y el síntoma están lejos.

Arreglo:

```c
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

/* Devuelve una copia en mayúsculas que el llamador debe liberar con free, o NULL. */
char *dup_upper(const char *s) {
    size_t len = strlen(s);
    char *out = malloc(len + 1);
    if (out == NULL) {
        return NULL;
    }
    for (size_t i = 0; i < len; i++) {
        out[i] = (char)toupper((unsigned char)s[i]);
    }
    out[len] = '\0';
    return out;
}
```

Además del `+ 1`:

- **`strlen` una sola vez.** En el original se evaluaba en cada iteración: O(n²) para una función que debería ser O(n).
- **Comprobación de `NULL`** tras `malloc`.
- **El cast a `unsigned char` se queda**: pasar un `char` negativo (bytes ≥ 0x80 donde `char` es con signo) a `toupper` es comportamiento indefinido. Lo tenías bien.

Una limitación que conviene documentar: `toupper` trabaja byte a byte, así que con UTF-8 no convierte letras como `ñ` o `á` (son dos bytes cada una y no se tocan). Si necesitas mayúsculas Unicode reales, hace falta una librería como ICU.

Test de regresión, que debe ejecutarse **con ASan**, porque sin él el bug original también pasaría:

```c
/* test_text.c */
#include <assert.h>
#include <stdlib.h>
#include <string.h>

char *dup_upper(const char *s);

int main(void) {
    const char *inputs[] = {"", "a", "hola", "Mezcla 123"};
    const char *expected[] = {"", "A", "HOLA", "MEZCLA 123"};
    for (size_t i = 0; i < sizeof inputs / sizeof inputs[0]; i++) {
        char *got = dup_upper(inputs[i]);
        assert(got != NULL);
        assert(strcmp(got, expected[i]) == 0);
        free(got);
    }
    return 0;
}
```

```sh
gcc -std=c17 -g -O1 -fsanitize=address -fno-omit-frame-pointer src/text.c test_text.c -o test_text
./test_text
```

El caso `""` es el más revelador: con el código original hace `malloc(0)` y escribe un byte en él. Con el arreglo, el test termina sin informes y con código 0. Merece la pena que este binario con ASan sea un paso fijo del CI: ese «lleva años sin dar problemas» probablemente esconda más casos como este.""",
            },
        ]
    },
    # 5) C: segfault por strtok sobre un literal; diagnóstico con gdb (voseo)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Me tira segmentation fault y no entiendo por qué, el código es re simple:

```c
#include <stdio.h>
#include <string.h>

int main(void) {
    char *csv = "ana,luis,eva";
    for (char *tok = strtok(csv, ","); tok != NULL; tok = strtok(NULL, ",")) {
        printf("%s\n", tok);
    }
    return 0;
}
```

```
$ ./split
Segmentation fault (core dumped)
```""",
            },
            {
                "role": "assistant",
                "content": r"""El problema está en la primera línea: `char *csv = "ana,luis,eva";` hace que `csv` apunte a un **literal de cadena**, y los literales viven en memoria de solo lectura. `strtok` **modifica** la cadena que recibe: escribe un `'\0'` encima de cada separador para cortar los tokens. La primera escritura sobre memoria de solo lectura provoca un `SIGSEGV`.

En C, modificar un literal es comportamiento indefinido. En Linux, con GCC o Clang, el literal va en la sección `.rodata`, que el sistema mapea sin permiso de escritura, así que el fallo es inmediato y reproducible.

**Cómo confirmarlo con gdb** en vez de creérmelo:

```
$ gcc -g -O0 split.c -o split
$ gdb -q ./split
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
(gdb) bt
#0  0x00007ffff7e4a1c5 in strtok_r () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x0000555555555199 in main () at split.c:6
(gdb) frame 1
(gdb) print csv
$1 = 0x555555556004 "ana,luis,eva"
(gdb) info proc mappings
```

(El nombre exacto del marco de libc varía según la versión.) Lo que dice cada paso:

1. **`bt`**: el fallo ocurre dentro de libc (`#0`), llamado desde tu línea 6 (`#1`). Cuando la traza muere dentro de una función estándar, casi siempre le pasaste algo que no admite.
2. **`print csv`**: la dirección a la que apunta.
3. **`info proc mappings`**: buscá el rango que contiene esa dirección (`0x555555556004` en el ejemplo). Va a estar en una región con permisos `r--p`: legible, no escribible. Ahí tenés la prueba.

**Arreglo**: declarar un array, que es una copia modificable del literal:

```c
#include <stdio.h>
#include <string.h>

int main(void) {
    char csv[] = "ana,luis,eva"; /* array en la pila, inicializado con una copia */
    for (char *tok = strtok(csv, ","); tok != NULL; tok = strtok(NULL, ",")) {
        printf("%s\n", tok);
    }
    return 0;
}
```

La diferencia es una sola palabra, pero cambia el significado: `char *csv` es un puntero a datos que no te pertenecen; `char csv[]` es tu propio array de 13 bytes.

Para que el compilador te frene la próxima vez:

- **Declará los punteros a literales como `const char *`**. Así `strtok(csv, ",")` produce un aviso de «discards 'const' qualifier» en compilación, en vez de un segfault en ejecución.
- **`-Wwrite-strings`** hace que GCC trate los literales como `const char[]` y avise en la propia declaración `char *csv = "..."`.

Dos limitaciones de `strtok` que te van a morder con CSV de verdad:

1. **Junta separadores consecutivos**: `"ana,,eva"` da dos tokens, no tres con uno vacío. Para CSV, un campo vacío importa. Si necesitás campos vacíos, usá `strsep` (glibc y BSD) o recorré con `strchr`.
2. **Guarda estado interno global**: no es reentrante ni segura entre hilos, y no podés partir dos cadenas a la vez. `strtok_r` (POSIX) recibe ese estado como parámetro.

Comprobación: con el arreglo, el programa imprime `ana`, `luis` y `eva` en tres líneas y termina con código 0. Y con `-Wwrite-strings` el código original ya no compila sin avisos.""",
            },
        ]
    },
    # 6) C: padding y alineación de structs; multiturno sobre serialización para red (no packed)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""¿Por qué `sizeof` de este struct da 24 y no 14, si 1 + 8 + 1 + 4 = 14?

```c
struct record {
    char tag;
    double value;
    char flag;
    int count;
};
```""",
            },
            {
                "role": "assistant",
                "content": r"""Por el **relleno de alineación** (*padding*). Cada tipo tiene un requisito de alineación: en x86-64, un `double` debe empezar en una dirección múltiplo de 8 y un `int` en múltiplo de 4. El compilador inserta bytes de relleno entre campos para cumplirlo, y también al final, para que en un array de structs cada elemento quede alineado.

Disposición de tu struct:

| Desplazamiento | Campo | Bytes |
|---|---|---|
| 0 | `tag` | 1 |
| 1-7 | relleno | 7 |
| 8 | `value` | 8 |
| 16 | `flag` | 1 |
| 17-19 | relleno | 3 |
| 20 | `count` | 4 |
| | **total** | **24** |

El orden de los campos en C es fijo (el compilador no puede reordenarlos), así que **ordenar de mayor a menor alineación** reduce el relleno:

```c
#include <stddef.h>
#include <stdio.h>

struct record_compact {
    double value; /* 0 */
    int count;    /* 8 */
    char tag;     /* 12 */
    char flag;    /* 13 */
};                /* 14 bytes de datos + 2 de relleno final = 16 */

_Static_assert(sizeof(struct record_compact) == 16, "layout inesperado");
_Static_assert(offsetof(struct record_compact, count) == 8, "layout inesperado");

int main(void) {
    printf("sizeof=%zu value@%zu count@%zu tag@%zu flag@%zu\n",
           sizeof(struct record_compact),
           offsetof(struct record_compact, value),
           offsetof(struct record_compact, count),
           offsetof(struct record_compact, tag),
           offsetof(struct record_compact, flag));
    return 0;
}
```

Los 2 bytes finales siguen ahí porque el tamaño total debe ser múltiplo de la alineación más grande (8): en un array, el `double` del segundo elemento tiene que caer en un múltiplo de 8.

Tres consecuencias prácticas del relleno:

1. **No compares structs con `memcmp`.** Los bytes de relleno tienen valores indeterminados; dos structs con los mismos campos pueden diferir en ellos. Compara campo a campo.
2. **No escribas structs tal cual en ficheros o sockets.** Además de no ser portable, el relleno puede contener restos de memoria anterior: es una fuga de información real (ha pasado en kernels y en protocolos de red).
3. **En arrays grandes, el orden importa.** Un millón de `record` ocupa 24 MB; uno de `record_compact`, 16 MB, y caben más por línea de caché.

Para ver el relleno de tus structs, GCC tiene `-Wpadded`, que avisa de cada hueco, y `pahole` (del paquete `dwarves`) muestra la disposición exacta a partir de un binario compilado con `-g`.

Comprobación: los dos `_Static_assert` hacen que, si el compilador o la plataforma producen otra disposición, el código no compile. Y el `printf` debe mostrar `sizeof=16 value@0 count@8 tag@12 flag@13`.""",
            },
            {
                "role": "user",
                "content": "Justamente quiero mandar este struct por la red a otro servicio. ¿Uso `__attribute__((packed))` y lo envío con `send(sock, &r, sizeof r, 0)`?",
            },
            {
                "role": "assistant",
                "content": r"""No. `packed` resuelve solo el relleno, y es el menor de los problemas. Enviar la memoria del struct tal cual sigue atado a:

- **El orden de bytes** (*endianness*): x86 y ARM habitualmente son *little-endian*; si el otro lado no lo es, lee otros números.
- **El tamaño de los tipos**: `int` no tiene por qué medir 4 bytes en todas partes, ni `long` 8 (en Windows de 64 bits `long` mide 4).
- **El compilador y sus opciones**: la disposición no la garantiza el estándar.

Y `packed` añade un problema propio: los campos quedan desalineados. En x86 cuesta algo de rendimiento; en algunas arquitecturas el acceso desalineado provoca un fallo, y tomar la dirección de un campo empaquetado (`&r.value`) da un puntero desalineado, comportamiento indefinido que GCC señala con `-Waddress-of-packed-member`.

Lo robusto es **definir el formato de cable byte a byte** y serializar campo a campo, con tipos de ancho fijo y orden de red (*big-endian*):

```c
#include <stdint.h>
#include <string.h>

struct record {
    char tag;
    double value;
    char flag;
    int32_t count;
};

/* Formato de cable: tag(1) | value(8, IEEE 754, big-endian) | flag(1) | count(4, big-endian) */
enum { RECORD_WIRE_SIZE = 1 + 8 + 1 + 4 };

_Static_assert(sizeof(double) == 8, "se asume double IEEE 754 de 64 bits");

static void put_u32_be(unsigned char *p, uint32_t v) {
    p[0] = (unsigned char)(v >> 24);
    p[1] = (unsigned char)(v >> 16);
    p[2] = (unsigned char)(v >> 8);
    p[3] = (unsigned char)v;
}

static uint32_t get_u32_be(const unsigned char *p) {
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | (uint32_t)p[3];
}

void record_encode(const struct record *r, unsigned char out[RECORD_WIRE_SIZE]) {
    uint64_t bits;
    memcpy(&bits, &r->value, sizeof bits); /* reinterpretar el double sin violar el aliasing */
    out[0] = (unsigned char)r->tag;
    put_u32_be(out + 1, (uint32_t)(bits >> 32));
    put_u32_be(out + 5, (uint32_t)bits);
    out[9] = (unsigned char)r->flag;
    put_u32_be(out + 10, (uint32_t)r->count);
}

void record_decode(const unsigned char in[RECORD_WIRE_SIZE], struct record *r) {
    uint64_t bits = (uint64_t)get_u32_be(in + 1) << 32 | get_u32_be(in + 5);
    r->tag = (char)in[0];
    memcpy(&r->value, &bits, sizeof bits);
    r->flag = (char)in[9];
    r->count = (int32_t)get_u32_be(in + 10);
}
```

Por qué así:

- **Desplazamientos y máscaras** producen el mismo resultado en cualquier máquina, sea cual sea su *endianness*: operan sobre valores, no sobre la memoria.
- **`memcpy` para reinterpretar el `double`**: hacerlo con un cast de punteros (`*(uint64_t *)&r->value`) viola la regla de *strict aliasing*; `memcpy` es la forma definida, y los compiladores la reducen a un simple movimiento de registro.
- **`int32_t`** en el struct fija el tamaño del campo en origen.
- **El formato está documentado en un comentario**, que es lo que leerá quien implemente el otro lado, quizá en otro lenguaje.

Para enviar: `send(sock, buf, RECORD_WIRE_SIZE, 0)`, comprobando que `send` devuelva el total (puede enviar menos y hay que repetir con el resto).

Comprobación de ida y vuelta, incluyendo valores negativos y un `double` no trivial:

```c
#include <assert.h>

int main(void) {
    struct record in = {.tag = 'R', .value = -1234.5625, .flag = 1, .count = -42};
    unsigned char wire[RECORD_WIRE_SIZE];
    record_encode(&in, wire);

    assert(wire[10] == 0xFF && wire[13] == 0xD6); /* -42 en big-endian: FF FF FF D6 */

    struct record out;
    record_decode(wire, &out);
    assert(out.tag == in.tag && out.value == in.value);
    assert(out.flag == in.flag && out.count == in.count);
    return 0;
}
```

La aserción sobre `wire[10]` y `wire[13]` fija el formato: si alguien cambia el orden de bytes, falla aunque la ida y vuelta siga funcionando en la misma máquina. Si el protocolo va a crecer (versiones, campos opcionales), en vez de mantener esto a mano considera Protocol Buffers, FlatBuffers o CBOR.""",
            },
        ]
    },
    # 7) C: comportamiento indefinido real: overflow con signo eliminado por el optimizador, UBSan, ckd_add
    {
        "messages": [
            {
                "role": "user",
                "content": "He leído que el overflow de enteros con signo es «undefined behavior» en C. Pero en mi máquina simplemente da la vuelta a negativo. ¿Qué consecuencias reales tiene, más allá de la teoría?",
            },
            {
                "role": "assistant",
                "content": r"""La consecuencia real es que **el compilador optimiza suponiendo que nunca ocurre**, y eso puede borrar código que tú escribiste precisamente para detectarlo. «Da la vuelta» es lo que ves con `-O0`; con optimizaciones, el programa puede hacer otra cosa.

El ejemplo clásico:

```c
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>

bool will_overflow(int x) {
    return x + 1 < x; /* "si al sumar 1 da la vuelta, será menor" */
}

int main(void) {
    printf("%d\n", will_overflow(INT_MAX));
    return 0;
}
```

- Sin optimizaciones (`-O0`) lo habitual es que imprima `1`: la suma da la vuelta y la comparación es verdadera.
- Con `-O2`, GCC y Clang imprimen `0`. El razonamiento del compilador es legítimo según el estándar: «`x + 1` no puede desbordar, porque eso sería UB; por tanto `x + 1 < x` es siempre falso». La función se compila como `return false`.

Puedes verlo tú mismo en Compiler Explorer (godbolt.org): con `-O2`, `will_overflow` queda reducida a poner a cero el registro de retorno.

No es un caso de laboratorio. Comprobaciones de límites, contadores de bucle y validaciones de tamaños escritas así han producido vulnerabilidades reales cuando una nueva versión del compilador empezó a optimizar más.

**Cómo comprobar el overflow correctamente**: antes de operar, o con funciones que lo detectan:

```c
#include <limits.h>
#include <stdbool.h>

/* C portable: comprobar antes de sumar */
bool add_checked(int a, int b, int *out) {
    if ((b > 0 && a > INT_MAX - b) || (b < 0 && a < INT_MIN - b)) {
        return false;
    }
    *out = a + b;
    return true;
}
```

- **GCC y Clang**: `__builtin_add_overflow(a, b, &out)` devuelve `true` si desborda, y se compila a una suma seguida de una comprobación del *flag* de desbordamiento de la CPU.
- **C23**: `<stdckdint.h>` estandariza lo mismo como `ckd_add(&out, a, b)`; disponible en GCC 14 y Clang 18 en adelante.

**Otros comportamientos indefinidos que se comportan igual** (el compilador asume que no ocurren):

| UB | Ejemplo | Consecuencia típica |
|---|---|---|
| Acceso fuera de rango | `arr[n]` con `n == len` | lee basura o pisa otra variable |
| Desreferenciar `NULL` | `p->x` antes de `if (p)` | el compilador elimina el `if (p)` posterior |
| Usar memoria liberada | `free(p); p->x` | datos corruptos lejos del origen |
| Desplazar ≥ ancho del tipo | `1 << 32` con `int` de 32 bits | resultado distinto según CPU |
| Modificar dos veces sin punto de secuencia | `i = i++ + 1` | cualquier valor |
| *Strict aliasing* | leer un `float` a través de un `int *` | el compilador reordena y lees valores viejos |
| Leer variable sin inicializar | `int x; if (x) ...` | ramas imposibles |

**Cómo detectarlos**: compila los tests con UndefinedBehaviorSanitizer:

```sh
gcc -std=c17 -g -O1 -fsanitize=undefined -fno-sanitize-recover=undefined ub.c -o ub && ./ub
```

Con el `will_overflow` original y una llamada que desborde en tiempo de ejecución, UBSan informa `runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'` con archivo y línea. `-fno-sanitize-recover` hace que el programa termine en el primer error, que es lo que quieres en CI.

Existe `-fwrapv`, que obliga al compilador a tratar el overflow con signo como vuelta en complemento a dos. Es un parche útil para código heredado que no puedes auditar, pero no arregla el diseño: tu código sigue sin ser C portable, y los demás tipos de UB de la tabla siguen ahí.

Comprobación de `add_checked`: `add_checked(INT_MAX, 1, &r)` y `add_checked(INT_MIN, -1, &r)` deben devolver `false`; `add_checked(INT_MAX, -1, &r)` debe devolver `true` con `r == INT_MAX - 1`. Ejecutado bajo UBSan con `-O2`, sin ningún informe.""",
            },
        ]
    },
    # 8) C: valgrind con invalid read (use-after-free en list_free) y definitely lost (pop sin free). Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Valgrind gives me two different complaints on my linked list and I can't make sense of either:

```c
struct node { int value; struct node *next; };

void list_free(struct node *head) {
    for (struct node *n = head; n != NULL; n = n->next) {
        free(n);
    }
}

int list_pop(struct node **head) {
    struct node *first = *head;
    int value = first->value;
    *head = first->next;
    return value;
}
```

```
==31337== Invalid read of size 8
==31337==    at 0x109247: list_free (list.c:21)
==31337==    by 0x1092F1: main (main.c:17)
==31337==  Address 0x4a8e048 is 8 bytes inside a block of size 16 free'd
==31337==    at 0x484B27F: free (vg_replace_malloc.c:872)
==31337==    by 0x109242: list_free (list.c:22)
==31337==    by 0x1092F1: main (main.c:17)
==31337==  Block was alloc'd at
==31337==    at 0x4848899: malloc (vg_replace_malloc.c:381)
==31337==    by 0x1091E6: list_push (list.c:10)
==31337==    by 0x1092B4: main (main.c:12)
...
==31337== 16 bytes in 1 blocks are definitely lost in loss record 1 of 1
==31337==    at 0x4848899: malloc (vg_replace_malloc.c:381)
==31337==    by 0x1091E6: list_push (list.c:10)
==31337==    by 0x1092A0: main (main.c:11)
```""",
            },
            {
                "role": "assistant",
                "content": r"""They are two separate bugs, and each report tells you exactly where to look once you know how to read it.

## 1. Invalid read: use after free in `list_free`

Read the report top to bottom:

- **`Invalid read of size 8`**: something read 8 bytes it shouldn't have. On x86-64, 8 bytes is a pointer.
- **`8 bytes inside a block of size 16 free'd`**: your `struct node` is 16 bytes: `value` at offset 0, 4 bytes of padding, `next` at offset 8. So the read is of `n->next`, from a node that was already freed.
- **`free'd ... list.c:22`** and **`read at list.c:21`**: freed and then read in the same function.

The `for` loop runs its increment, `n = n->next`, *after* the body, and the body just freed `n`. It "works" in practice because freed memory usually still holds the old bytes, which is why this bug survives for years and then crashes once the allocator reuses that block.

Fix: save the successor before freeing.

```c
void list_free(struct node *head) {
    while (head != NULL) {
        struct node *next = head->next;
        free(head);
        head = next;
    }
}
```

## 2. Definitely lost: `list_pop` unlinks the node but never frees it

- **`definitely lost`** means that at exit no pointer anywhere refers to that block. Nobody can free it anymore.
- **`alloc'd ... list_push (list.c:10)`** called from `main.c:11`: a node created by a push. It is the one your pop removed: after `*head = first->next`, the list no longer points to `first`, and the function returns only the value.

The question to ask for every allocation in C is "who owns this now?" After a pop, the list no longer owns the node, so the pop must free it. It also dereferences `first` without checking for an empty list, which is a segfault waiting to happen:

```c
#include <stdbool.h>
#include <stdlib.h>

/* Removes the first node. Returns false if the list is empty. */
bool list_pop(struct node **head, int *out) {
    struct node *first = *head;
    if (first == NULL) {
        return false;
    }
    *out = first->value;
    *head = first->next;
    free(first);
    return true;
}
```

Returning `bool` and writing through `out` lets the caller distinguish "empty" from "popped a value", which an `int` return could not do for any value.

## Verification

```sh
gcc -std=c17 -g -O0 list.c main.c -o main
valgrind --leak-check=full --error-exitcode=1 ./main
```

The clean run ends with `All heap blocks were freed -- no leaks are possible` and `ERROR SUMMARY: 0 errors from 0 contexts`. `--error-exitcode=1` makes Valgrind fail the process on any error, so you can put it in CI.

A minimal `main` that exercises both paths:

```c
#include <assert.h>

int main(void) {
    struct node *list = NULL;
    for (int i = 0; i < 3; ++i) {
        assert(list_push(&list, i));
    }
    int v;
    assert(list_pop(&list, &v) && v == 2);
    list_free(list);

    struct node *empty = NULL;
    assert(!list_pop(&empty, &v));
    return 0;
}
```

(This assumes `list_push` returns `bool` and pushes at the head.) For faster feedback during development, AddressSanitizer (`-fsanitize=address`) catches both bugs too, reports the use-after-free as `heap-use-after-free`, and runs far faster than Valgrind.""",
            },
        ]
    },
    # 9) C: Makefile con dependencias automáticas; multiturno con modo debug y sanitizers
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy aprendiendo C y quiero dejar de compilar con `gcc src/*.c -o app`. Tengo `src/*.c` e `include/*.h`. ¿Cómo sería un Makefile decente que solo recompile lo que cambió?",
            },
            {
                "role": "assistant",
                "content": r"""Este es un Makefile pequeño pero completo para GNU Make. Recompila solo los `.c` que cambiaron **y** los que incluyen una cabecera modificada, que es lo que la mayoría de Makefiles caseros no hace bien.

```make
CC       ?= cc
CFLAGS   ?= -std=c17 -Wall -Wextra -Wpedantic -O2
CPPFLAGS += -Iinclude -MMD -MP

SRC := $(wildcard src/*.c)
OBJ := $(SRC:src/%.c=build/%.o)
DEP := $(OBJ:.o=.d)

app: $(OBJ)
	$(CC) $(LDFLAGS) $^ $(LDLIBS) -o $@

build/%.o: src/%.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

build:
	mkdir -p $@

clean:
	rm -rf build app

.PHONY: clean

-include $(DEP)
```

Qué hace cada parte:

- **`SRC`, `OBJ`, `DEP`**: busca todos los `.c` de `src/` y calcula los `.o` y `.d` correspondientes en `build/`. Añadir un archivo nuevo no requiere tocar el Makefile.
- **`app: $(OBJ)`**: el ejecutable depende de todos los objetos. `$^` son todas las dependencias, `$@` el objetivo.
- **`build/%.o: src/%.c`**: regla de patrón; cada `.o` se compila de su `.c`. `$<` es la primera dependencia.
- **`-MMD -MP`**: el compilador genera, junto a cada `.o`, un `.d` con la lista de cabeceras que incluye. El `-include $(DEP)` final los carga, así que Make sabe que `build/parser.o` depende de `include/parser.h`. `-MP` añade reglas vacías para cada cabecera, para que borrar un `.h` no rompa el build.
- **`| build`**: dependencia de solo orden. El directorio debe existir antes de compilar, pero su fecha de modificación no debe provocar recompilaciones.
- **`?=`**: valor por defecto que puedes sobrescribir sin editar el archivo: `make CC=clang` o `make CFLAGS="-O0 -g"`.
- **`CPPFLAGS` frente a `CFLAGS`**: opciones del preprocesador (rutas de *include*, macros) separadas de las del compilador; es la convención que siguen las reglas implícitas de Make.
- **`.PHONY: clean`**: `clean` no es un archivo; sin esto, un archivo llamado `clean` en el directorio impediría ejecutar la regla.

Un error que vas a ver tarde o temprano: `Makefile:9: *** missing separator.  Stop.`. Las líneas de las recetas (las que ejecutan comandos) **deben empezar con un tabulador**, no con espacios. Muchos editores convierten el tabulador en espacios; configura el tuyo para no hacerlo en Makefiles.

Comprobación del comportamiento incremental:

```sh
make -j"$(nproc)"     # primera vez: compila todo
make                  # make: 'app' is up to date.
touch src/main.c && make          # recompila solo main.c y vuelve a enlazar
touch include/util.h && make      # recompila los .c que incluyen util.h, y solo esos
```

Si el último paso no recompila nada, los `.d` no se están generando o cargando: revisa que existan en `build/` y que el `-include` esté al final.""",
            },
            {
                "role": "user",
                "content": "Funciona. ¿Cómo añado un modo debug con -g y sanitizers sin duplicar todo el Makefile?",
            },
            {
                "role": "assistant",
                "content": r"""Con una variable `MODE` que elija las opciones **y el directorio de salida**. Lo segundo es lo importante: los objetos de cada modo deben vivir separados.

```make
CC       ?= cc
MODE     ?= release
CPPFLAGS += -Iinclude -MMD -MP
WARNINGS := -std=c17 -Wall -Wextra -Wpedantic

ifeq ($(MODE),debug)
  CFLAGS  := $(WARNINGS) -O0 -g -fsanitize=address,undefined -fno-omit-frame-pointer
  LDFLAGS += -fsanitize=address,undefined
else ifeq ($(MODE),release)
  CFLAGS  := $(WARNINGS) -O2 -DNDEBUG
else
  $(error MODE debe ser debug o release, no '$(MODE)')
endif

BUILD := build/$(MODE)
SRC   := $(wildcard src/*.c)
OBJ   := $(SRC:src/%.c=$(BUILD)/%.o)
DEP   := $(OBJ:.o=.d)

$(BUILD)/app: $(OBJ)
	$(CC) $(LDFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD):
	mkdir -p $@

clean:
	rm -rf build

.PHONY: clean

-include $(DEP)
```

Uso:

```sh
make                 # build/release/app
make MODE=debug      # build/debug/app, con ASan y UBSan
```

Por qué cada decisión:

1. **Un directorio por modo.** Make decide si recompilar mirando fechas, no opciones. Si compartieran `build/`, pasar de release a debug no recompilaría nada y enlazarías objetos sin instrumentar con el *runtime* de ASan: en el mejor caso, un error de enlazado; en el peor, un binario que parece tener sanitizers y solo los tiene en parte.
2. **`-fsanitize` también en `LDFLAGS`.** El enlazado necesita la opción para incluir el *runtime* de los sanitizers; sin ella verás errores de «undefined reference to `__asan_...`».
3. **`-fno-omit-frame-pointer`** da trazas de ASan completas y fiables.
4. **`-DNDEBUG` en release** desactiva los `assert`. Es la convención, pero decide conscientemente: hay equipos que prefieren mantenerlos en producción.
5. **`$(error ...)`** ante un modo desconocido: `make MODE=degub` falla al instante en vez de compilar algo inesperado.

Comprobación de que el modo debug lleva de verdad los sanitizers:

```sh
make MODE=debug
nm build/debug/app | grep -c __asan_init    # mayor que 0
ls build/release build/debug                # objetos separados
```

Y una prueba funcional: añade temporalmente un `int a[2]; a[2] = 1;` en una función que se ejecute, compila en debug y ejecuta. ASan debe informar un `stack-buffer-overflow` con el archivo y la línea. Si no informa nada, los objetos no se compilaron con la opción.""",
            },
        ]
    },
    # 10) C: conversiones signed/unsigned, -1 < sizeof, bucle descendente con size_t. System variante principiante
    {
        "messages": [
            {"role": "system", "content": "Explica como a alguien que está empezando, con ejemplos cortos y sin dar nada por sabido."},
            {
                "role": "user",
                "content": "Leí que en C `if (-1 < sizeof(int))` da falso. ¿Cómo puede ser? ¿Qué más debería saber de mezclar números con signo y sin signo?",
            },
            {
                "role": "assistant",
                "content": r"""Da falso porque C **convierte el `-1` a un número sin signo** antes de comparar, y como número sin signo `-1` es enorme.

Paso a paso:

1. `sizeof(int)` no devuelve un `int`: devuelve un `size_t`, que es un entero **sin signo** (en Linux de 64 bits, `unsigned long`, de 0 a 2⁶⁴ − 1).
2. Para comparar dos números, C los lleva primero a un tipo común. Cuando uno es sin signo y al menos tan grande como el otro, gana el sin signo.
3. Convertir `-1` a sin signo da el valor máximo del tipo: `18446744073709551615`.
4. La comparación real es `18446744073709551615 < 4`, que es falsa.

```c
#include <stdio.h>

int main(void) {
    printf("%d\n", -1 < sizeof(int));          /* 0: falso */
    printf("%d\n", -1 < (int)sizeof(int));     /* 1: verdadero, los dos son int */
    printf("%zu\n", (size_t)-1);               /* 18446744073709551615 */
    return 0;
}
```

## Dónde te va a pasar de verdad

**1. Un bucle hacia atrás que no termina nunca:**

```c
for (size_t i = n - 1; i >= 0; i--) {   /* i >= 0 siempre es verdad */
    printf("%d\n", values[i]);
}
```

Un `size_t` nunca es negativo. Cuando `i` vale 0 y hace `i--`, pasa a ser el número más grande posible, y el bucle sigue (leyendo fuera del array). Además, si `n` es 0, `n - 1` ya empieza siendo enorme.

La forma correcta, que también funciona con `n == 0`:

```c
for (size_t i = n; i-- > 0; ) {
    printf("%d\n", values[i]);
}
```

Se lee «mientras `i` sea mayor que 0, réstale uno y úsalo». Con `n = 3` recorre 2, 1, 0 y se detiene.

**2. Restas que «deberían» ser negativas:**

```c
size_t used = 10, capacity = 8;
if (capacity - used < 5) {        /* 8 - 10 no es -2: es un número enorme */
    puts("casi lleno");           /* no se imprime */
}
```

Reescríbelo para no restar en el lado que puede quedar negativo: `if (used + 5 > capacity)`.

**3. Comparar un `int` con la longitud de algo:**

```c
int i = -1;
if (i < strlen(s)) { ... }   /* -1 se convierte a sin signo: la condición es falsa */
```

## Tres reglas para evitarlo

1. **Usa `size_t` para tamaños e índices**, y no lo mezcles con `int` en comparaciones.
2. **Si una variable puede ser negativa, no la compares con un `size_t`** sin comprobar antes que no es negativa (`i >= 0 && (size_t)i < len`).
3. **Deja que el compilador te avise.** Compila siempre con `-Wall -Wextra`:

```sh
gcc -Wall -Wextra ejemplo.c
```

Con eso, GCC avisa en el bucle de «comparison of unsigned expression in '>= 0' is always true» (`-Wtype-limits`) y en las comparaciones mezcladas de «comparison of integer expressions of different signedness» (`-Wsign-compare`). Los dos están incluidos en `-Wextra`.

Comprobación: compila el primer programa y verifica que imprime `0`, `1` y `18446744073709551615`. Luego compila el bucle con `size_t i = n - 1; i >= 0` usando `-Wall -Wextra`: el compilador debe avisarte antes de que lo ejecutes.""",
            },
        ]
    },
    # 11) C++: RAII sobre APIs de C con unique_ptr y deleter propio. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En un proyecto C++17 uso funciones de C que abren recursos (`fopen`, y también `sqlite3_open`). Tengo returns y excepciones en varios sitios y de vez en cuando se me escapa un `fclose`. ¿Cómo aplico RAII sin escribir una clase para cada recurso?",
            },
            {
                "role": "assistant",
                "content": r"""Con `std::unique_ptr` y un *deleter* propio. `unique_ptr` no es solo para memoria: es un «dueño único de un puntero que hay que liberar de una forma concreta». El destructor llama a tu función de cierre en **todos** los caminos de salida: `return` temprano, excepción o final normal.

```cpp
#include <cerrno>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <string>
#include <system_error>

struct FileCloser {
    void operator()(std::FILE* f) const noexcept { std::fclose(f); }
};

using FilePtr = std::unique_ptr<std::FILE, FileCloser>;

FilePtr open_file(const std::string& path, const char* mode) {
    FilePtr f{std::fopen(path.c_str(), mode)};
    if (!f) {
        throw std::system_error(errno, std::generic_category(), "cannot open " + path);
    }
    return f;
}

std::string read_first_line(const std::string& path) {
    FilePtr f = open_file(path, "r");
    std::string line;
    int c;
    while ((c = std::fgetc(f.get())) != EOF && c != '\n') {
        line.push_back(static_cast<char>(c));
    }
    if (std::ferror(f.get())) {
        throw std::runtime_error("read error in " + path); // fclose se ejecuta igual
    }
    return line;                                           // y aquí también
}
```

Detalles que importan:

- **`unique_ptr` no llama al *deleter* si el puntero es nulo**, así que `FileCloser` no necesita comprobarlo.
- **Un *struct* vacío como *deleter*, no `decltype(&std::fclose)`.** Con un puntero a función, el `unique_ptr` ocupa dos punteros en vez de uno y hay que pasar la función en cada construcción. Además, desde C++20 tomar la dirección de funciones de la biblioteca estándar no está garantizado (solo de las designadas como *addressable*). El *struct* vacío no ocupa espacio.
- **`.get()`** presta el puntero crudo a la API de C sin ceder la propiedad. Si alguna vez una función C **toma** la propiedad, usa `.release()` en esa llamada.

Para no escribir un *struct* por cada recurso, un *deleter* genérico parametrizado por la función de cierre (C++17, `template <auto>`):

```cpp
#include <sqlite3.h>

template <auto CloseFn>
struct CDeleter {
    template <typename T>
    void operator()(T* handle) const noexcept { CloseFn(handle); }
};

using DbPtr = std::unique_ptr<sqlite3, CDeleter<&sqlite3_close>>;

DbPtr open_db(const std::string& path) {
    sqlite3* raw = nullptr;
    int rc = sqlite3_open(path.c_str(), &raw);
    DbPtr db{raw}; // sqlite3_open puede devolver un handle aun fallando: hay que cerrarlo igual
    if (rc != SQLITE_OK) {
        throw std::runtime_error(std::string("sqlite: ") + sqlite3_errmsg(raw));
    }
    return db;
}
```

Fíjate en el orden en `open_db`: el handle se envuelve **antes** de comprobar el error, porque la documentación de SQLite indica que `sqlite3_open` puede asignar un handle incluso cuando falla, y debe cerrarse. Así el `throw` no lo filtra.

Un límite de RAII que conviene conocer: **el destructor no puede informar errores**. `fclose` sobre un fichero de escritura puede fallar al vaciar el buffer (disco lleno), y en el destructor ese error se pierde. Para escrituras, cierra explícitamente y comprueba, y deja el destructor como red de seguridad:

```cpp
void close_checked(FilePtr& f) {
    if (std::fclose(f.release()) != 0) {
        throw std::system_error(errno, std::generic_category(), "fclose failed");
    }
}
```

Comprobación de que el cierre ocurre también al lanzar, con una API falsa que cuenta los recursos abiertos:

```cpp
#include <cassert>
#include <memory>
#include <stdexcept>

namespace fake {
int open_handles = 0;
struct Handle {};
Handle* open() { ++open_handles; return new Handle; }
void close(Handle* h) { --open_handles; delete h; }
}

using HandlePtr = std::unique_ptr<fake::Handle, CDeleter<&fake::close>>;

void work_that_throws() {
    HandlePtr h{fake::open()};
    throw std::runtime_error("boom");
}

int main() {
    try {
        work_that_throws();
    } catch (const std::runtime_error&) {
    }
    assert(fake::open_handles == 0);
}
```""",
            },
        ]
    },
    # 12) C++: unique_ptr vs shared_ptr, ciclo de referencias en un árbol; multiturno con enable_shared_from_this
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuándo uso unique_ptr y cuándo shared_ptr? En nuestro código hay shared_ptr por todos lados «por si acaso», y tenemos una fuga de memoria en un árbol donde cada nodo guarda shared_ptr a sus hijos y a su padre.",
            },
            {
                "role": "assistant",
                "content": r"""La fuga es un **ciclo de referencias**: el padre mantiene vivo al hijo y el hijo mantiene vivo al padre. Cuando sueltas la raíz, cada nodo sigue teniendo al menos una referencia (la de su pariente), los contadores nunca llegan a cero y nada se libera. `shared_ptr` cuenta referencias; no detecta ciclos.

La regla para elegir:

| Situación | Qué usar |
|---|---|
| Un único dueño claro (lo normal) | `std::unique_ptr` |
| Varios dueños sin un orden claro de destrucción | `std::shared_ptr` |
| Observar algo que otro posee y que puede desaparecer | `std::weak_ptr` |
| Usar algo que otro posee y que seguro vive más que tú | `T&` o `T*` |

**`unique_ptr` por defecto.** No tiene coste respecto a un puntero crudo y deja la propiedad escrita en el tipo. `shared_ptr` cuesta un bloque de control, un contador atómico que se actualiza en cada copia y, sobre todo, claridad: con `shared_ptr` «por si acaso», nadie sabe cuándo se destruye nada.

Un árbol tiene un dueño obvio: **el padre posee a sus hijos**. El hijo solo necesita *ver* a su padre, y como el padre siempre vive más que sus hijos, basta un puntero crudo no propietario:

```cpp
#include <memory>
#include <string>
#include <utility>
#include <vector>

class Node {
public:
    explicit Node(std::string name, Node* parent = nullptr)
        : name_(std::move(name)), parent_(parent) {}

    // Los hijos guardan la dirección del padre: moverlo dejaría esos punteros colgando
    Node(Node&&) = delete;
    Node& operator=(Node&&) = delete;

    Node& add_child(std::string name) {
        children_.push_back(std::make_unique<Node>(std::move(name), this));
        return *children_.back();
    }

    const Node* parent() const { return parent_; }
    const std::string& name() const { return name_; }
    std::size_t child_count() const { return children_.size(); }

private:
    std::string name_;
    Node* parent_;                                 // no propietario
    std::vector<std::unique_ptr<Node>> children_;  // propietario
};
```

El `= delete` de las operaciones de movimiento no es decorativo: con `unique_ptr` como miembro, la clase sería movible por defecto, y mover un nodo dejaría a sus hijos apuntando a la dirección antigua.

Cuando **sí** necesites `shared_ptr` en ambos sentidos (por ejemplo, objetos con vidas independientes que se observan entre sí), rompe el ciclo con `weak_ptr` en el lado que observa:

```cpp
struct Session;

struct Subscription {
    std::weak_ptr<Session> session;  // no mantiene viva la sesión

    void notify() const {
        if (auto s = session.lock()) {  // shared_ptr válido o nulo si ya murió
            // usar *s
        }
    }
};
```

Comprobación de que el árbol libera todo, con un contador de nodos vivos (añade `static inline int alive = 0;` a `Node`, `++alive` en el constructor y un destructor `~Node() { --alive; }`):

```cpp
#include <cassert>

int main() {
    {
        Node root{"root"};
        Node& a = root.add_child("a");
        a.add_child("a1");
        root.add_child("b");
        assert(Node::alive == 4);
        assert(a.parent() == &root);
    }
    assert(Node::alive == 0);  // con shared_ptr en ambos sentidos, seguiría en 4
}
```""",
            },
            {
                "role": "user",
                "content": "Tengo otro caso: una clase `Connection` gestionada con shared_ptr que necesita registrarse en un event loop pasando un puntero a sí misma. Probé `std::shared_ptr<Connection>(this)` y el programa explota con un double free.",
            },
            {
                "role": "assistant",
                "content": r"""`std::shared_ptr<Connection>(this)` crea un **segundo bloque de control** para el mismo objeto. Ya había uno (el del `shared_ptr` que te creó); ahora hay dos contadores independientes, cada uno convencido de ser el único dueño. Cuando cualquiera llega a cero, borra el objeto; cuando llega el otro, lo borra otra vez. De ahí el *double free*.

La herramienta para esto es `std::enable_shared_from_this`: guarda una referencia débil al bloque de control existente y te da `shared_from_this()` y `weak_from_this()` (C++17) apuntando al mismo.

```cpp
#include <functional>
#include <memory>
#include <string>
#include <string_view>

// Asumo un event loop con esta interfaz
class EventLoop {
public:
    virtual ~EventLoop() = default;
    virtual void on_readable(std::function<void(std::string_view)> callback) = 0;
};

class Connection : public std::enable_shared_from_this<Connection> {
public:
    static std::shared_ptr<Connection> create(EventLoop& loop) {
        std::shared_ptr<Connection> conn{new Connection(loop)};
        conn->subscribe();  // ya existe un shared_ptr dueño: weak_from_this es válido
        return conn;
    }

    std::size_t bytes_received() const { return bytes_; }

private:
    explicit Connection(EventLoop& loop) : loop_(loop) {}

    void subscribe() {
        loop_.on_readable([weak = weak_from_this()](std::string_view data) {
            if (auto self = weak.lock()) {
                self->bytes_ += data.size();
            }
        });
    }

    EventLoop& loop_;
    std::size_t bytes_ = 0;
};
```

Las decisiones:

1. **Constructor privado y fábrica `create`.** `shared_from_this()` solo funciona si el objeto ya está gestionado por un `shared_ptr`; llamado antes (por ejemplo, en el constructor), lanza `std::bad_weak_ptr` desde C++17. La fábrica garantiza que nadie construye una `Connection` en la pila o con `new` suelto. (No uso `std::make_shared` porque no puede acceder al constructor privado; si quieres la asignación única de `make_shared`, la variante habitual es un *passkey*: un tipo privado como parámetro del constructor público.)
2. **`weak_from_this()` en el *callback*, no `shared_from_this()`.** Si la lambda guardara un `shared_ptr`, el event loop mantendría viva la conexión para siempre: el mismo ciclo de antes, con el event loop en medio. Con `weak_ptr`, cuando el último dueño suelta la conexión, el *callback* simplemente deja de hacer nada.
3. **`lock()` dentro del *callback***: obtiene un `shared_ptr` temporal que garantiza que el objeto no se destruye **mientras** se ejecuta el *callback*, aunque otro hilo suelte la última referencia a la vez.

Comprobación con un event loop falso:

```cpp
#include <cassert>
#include <vector>

class FakeLoop : public EventLoop {
public:
    void on_readable(std::function<void(std::string_view)> callback) override {
        callbacks_.push_back(std::move(callback));
    }
    void fire(std::string_view data) {
        for (auto& cb : callbacks_) cb(data);
    }
private:
    std::vector<std::function<void(std::string_view)>> callbacks_;
};

int main() {
    FakeLoop loop;
    auto conn = Connection::create(loop);
    loop.fire("hola");
    assert(conn->bytes_received() == 4);
    assert(conn.use_count() == 1);   // el callback no añade dueños

    std::weak_ptr<Connection> watcher = conn;
    conn.reset();
    assert(watcher.expired());       // destruida pese al callback registrado
    loop.fire("tarde");              // no hace nada y no falla
}
```

Ejecútalo con `-fsanitize=address`: con la versión `shared_ptr(this)`, ASan informa del `attempting double-free`; con esta, silencio.""",
            },
        ]
    },
    # 13) C++: qué hace realmente std::move, const T&&, return std::move, noexcept y vector
    {
        "messages": [
            {
                "role": "user",
                "content": "Dos dudas de move semantics en C++17. Hice `std::move` de un `std::vector` declarado `const` y en el profiler se ve que se copió. Y un compañero dice que `return std::move(local);` es mala práctica. ¿Qué hace realmente std::move?",
            },
            {
                "role": "assistant",
                "content": r"""`std::move` **no mueve nada**. Es un *cast*: convierte su argumento en una referencia a *rvalue* (`static_cast<T&&>(x)`). Eso solo cambia qué sobrecarga se elige después. El movimiento lo hace, si existe y encaja, el **constructor o el operador de asignación de movimiento** del tipo de destino.

Con esa idea se explican tus dos casos.

## 1. `std::move` de algo `const` copia

```cpp
const std::vector<int> source(1'000'000, 7);
std::vector<int> target = std::move(source);  // copia
```

`std::move(source)` produce un `const std::vector<int>&&`. El constructor de movimiento recibe `std::vector<int>&&` (no `const`), porque mover implica *modificar* el origen (robarle el buffer y dejarlo vacío). Un `const&&` no puede enlazarse ahí, pero sí al constructor de copia, que recibe `const std::vector<int>&`. Resultado: copia silenciosa, sin error ni aviso por defecto. `clang-tidy` lo detecta con `performance-move-const-arg`.

Conclusión práctica: lo que quieras mover no puede ser `const`. Si una variable es `const` y la necesitas mover al final, quítale el `const`.

## 2. `return std::move(local)` empeora las cosas

```cpp
std::vector<int> build() {
    std::vector<int> result(1000);
    // ... rellenar
    return result;              // bien
    // return std::move(result); // peor
}
```

Con `return result;` el compilador puede construir `result` directamente en el destino del llamador (**NRVO**, elisión de copia): cero copias y cero movimientos. Si no puede aplicarla, la norma obliga a tratar `result` como *rvalue* y moverlo de todos modos. Es decir, ya tienes el movimiento gratis como peor caso.

`return std::move(result);` cambia la expresión de retorno de «nombre de variable local» a «llamada a función», y eso **desactiva NRVO**: fuerzas un movimiento donde podía no haber nada. GCC lo avisa con `-Wpessimizing-move` (incluido en `-Wall`).

Dónde **sí** hace falta `std::move`:

- Pasar una variable que ya no vas a usar a una función que la guarda: `cache.insert(std::move(key))`.
- En tus constructores y asignaciones de movimiento, para mover los miembros: `name_(std::move(other.name_))`.
- Devolver un **miembro** desde una función calificada `&&`: `return std::move(data_);`.

## 3. El detalle que más rendimiento cuesta: `noexcept`

Cuando un `std::vector` crece, reubica sus elementos. Para mantener la garantía fuerte de excepciones (si algo falla, el vector queda como estaba), **solo mueve si el constructor de movimiento es `noexcept`**; si no, copia. Un tipo propio con movimiento sin `noexcept` se copia en cada realojamiento.

```cpp
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

struct Tracked {
    static inline int copies = 0;
    static inline int moves = 0;

    std::string payload;

    explicit Tracked(std::string p) : payload(std::move(p)) {}
    Tracked(const Tracked& other) : payload(other.payload) { ++copies; }
    Tracked(Tracked&& other) noexcept : payload(std::move(other.payload)) { ++moves; }
    Tracked& operator=(const Tracked&) = default;
    Tracked& operator=(Tracked&&) noexcept = default;
};

int main() {
    std::vector<Tracked> items;
    for (int i = 0; i < 100; ++i) {
        items.emplace_back("item-" + std::to_string(i));
    }
    std::printf("copies=%d moves=%d\n", Tracked::copies, Tracked::moves);
}
```

Comprobación: con GCC y libstdc++ (capacidad que se duplica: 1, 2, 4... 128) imprime `copies=0 moves=127`, los elementos reubicados en los siete realojamientos (1 + 2 + 4 + 8 + 16 + 32 + 64). Quita el `noexcept` del constructor de movimiento y verás `copies=127 moves=0`. Con MSVC los números cambian porque crece en factor 1,5, pero la diferencia entre las dos versiones es la misma.

Si dejas que el compilador genere el movimiento (`= default` o regla del cero), el `noexcept` se deduce de los miembros y normalmente sale bien. El riesgo está en escribirlo a mano y olvidarlo.""",
            },
        ]
    },
    # 14) C++: reglas del 0/3/5 con un buffer propio; copy-and-swap; versión regla del cero. System variante
    {
        "messages": [
            {"role": "system", "content": "Responde con el código completo primero y después una explicación breve."},
            {
                "role": "user",
                "content": "¿Qué son las reglas del 0, del 3 y del 5 en C++ y cómo se aplican a una clase que gestiona su propio buffer con new[]/delete[]?",
            },
            {
                "role": "assistant",
                "content": r"""Versión con regla del cinco (gestión manual):

```cpp
#include <algorithm>
#include <cstddef>
#include <utility>

class Buffer {
public:
    explicit Buffer(std::size_t size)
        : size_(size), data_(size > 0 ? new char[size]{} : nullptr) {}

    ~Buffer() { delete[] data_; }

    Buffer(const Buffer& other)
        : size_(other.size_), data_(other.size_ > 0 ? new char[other.size_] : nullptr) {
        std::copy(other.data_, other.data_ + other.size_, data_);
    }

    Buffer(Buffer&& other) noexcept
        : size_(std::exchange(other.size_, 0)), data_(std::exchange(other.data_, nullptr)) {}

    // copy-and-swap: un solo operador para copia y movimiento
    Buffer& operator=(Buffer other) noexcept {
        swap(*this, other);
        return *this;
    }

    friend void swap(Buffer& a, Buffer& b) noexcept {
        using std::swap;
        swap(a.size_, b.size_);
        swap(a.data_, b.data_);
    }

    std::size_t size() const noexcept { return size_; }
    char* data() noexcept { return data_; }
    const char* data() const noexcept { return data_; }

private:
    std::size_t size_;
    char* data_;
};
```

Versión con regla del cero (la recomendada):

```cpp
#include <cstddef>
#include <vector>

class Buffer {
public:
    explicit Buffer(std::size_t size) : data_(size) {}

    std::size_t size() const noexcept { return data_.size(); }
    char* data() noexcept { return data_.data(); }
    const char* data() const noexcept { return data_.data(); }

private:
    std::vector<char> data_;
};
```

Prueba común a las dos:

```cpp
#include <cassert>
#include <cstring>
#include <utility>

int main() {
    Buffer a(4);
    std::memcpy(a.data(), "abc", 4);

    Buffer b = a;                   // copia profunda
    b.data()[0] = 'X';
    assert(std::strcmp(a.data(), "abc") == 0);

    Buffer c = std::move(a);        // movimiento
    assert(c.size() == 4 && std::strcmp(c.data(), "abc") == 0);

    Buffer d(1);
    d = c;                          // asignación de copia
    assert(std::strcmp(d.data(), "abc") == 0);
}
```

**Las reglas:**

- **Regla del tres** (C++98): si necesitas escribir uno de destructor, constructor de copia u operador de asignación de copia, necesitas los tres. Si el destructor libera un recurso, las copias generadas por el compilador copiarían el puntero, y dos objetos acabarían liberando el mismo buffer (*double free*).
- **Regla del cinco** (C++11): añade constructor y asignación de movimiento. No escribirlos no rompe nada, pero el movimiento se convierte en copia.
- **Regla del cero**: diseña la clase para no escribir ninguno. Delega cada recurso en un miembro que ya sea RAII (`std::vector`, `std::string`, `std::unique_ptr`) y el compilador genera las cinco operaciones correctas, incluido el `noexcept` del movimiento.

**Detalles de la versión manual:**

- **`std::exchange`** en el movimiento deja el origen vacío y válido; su destructor hace `delete[] nullptr`, que no hace nada.
- **Copy-and-swap**: el parámetro por valor hace la copia (o el movimiento) *antes* de tocar `*this`; si la reserva lanza, el objeto queda intacto (garantía fuerte), y la autoasignación es segura sin un `if (this != &other)`. El coste es que una asignación de copia siempre reserva memoria nueva aunque el buffer actual fuera suficiente.
- **Trampa**: declarar solo el destructor hace que el compilador **no genere** el movimiento; las operaciones de copia implícitas siguen existiendo, así que todo «mueve» copiando, sin errores ni avisos.

Si necesitas un buffer que no se pueda copiar pero sí mover, la regla del cero sigue valiendo: `std::unique_ptr<char[]> data_` en vez de `std::vector<char>` deja la clase movible y no copiable sin escribir nada. Para compilar la prueba con esa variante, quita las líneas de copia.""",
            },
        ]
    },
    # 15) C++: ASan heap-use-after-free por string_view guardado de un temporal
    {
        "messages": [
            {
                "role": "user",
                "content": r"""ASan me da esto y no veo ningún `delete` en mi código:

```cpp
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

std::string load_name(int id) {
    return "customer-number-" + std::to_string(id);
}

int main() {
    std::vector<std::string_view> names;
    for (int id = 0; id < 3; ++id) {
        names.push_back(load_name(id));
    }
    for (auto name : names) {
        std::cout << name << '\n';
    }
}
```

```
==7712==ERROR: AddressSanitizer: heap-use-after-free on address 0x503000000040 at pc 0x7f3a6c4b5a62 bp 0x7ffc5b0e1f00 sp 0x7ffc5b0e16a8
READ of size 17 at 0x503000000040 thread T0
    #0 0x7f3a6c4b5a61 in fwrite
    #1 0x7f3a6c1d3b2c in std::basic_ostream<char, std::char_traits<char> >& std::__ostream_insert<char, std::char_traits<char> >(...)
    #2 0x55b0f1a0c7d1 in main src/names.cpp:16

0x503000000040 is located 0 bytes inside of 18-byte region [0x503000000040,0x503000000052)
freed by thread T0 here:
    #0 0x7f3a6c4f1a2d in operator delete(void*, unsigned long)
    #1 0x55b0f1a0c5e9 in std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::_M_dispose()
    #2 0x55b0f1a0c6a4 in main src/names.cpp:13

previously allocated by thread T0 here:
    #0 0x7f3a6c4f0b11 in operator new(unsigned long)
    #1 0x55b0f1a0c3f0 in load_name[abi:cxx11](int) src/names.cpp:7
    #2 0x55b0f1a0c681 in main src/names.cpp:13
```""",
            },
            {
                "role": "assistant",
                "content": r"""El `delete` existe, pero lo escribe el compilador: es el **destructor del `std::string` temporal** que devuelve `load_name`. La traza lo cuenta en tres bloques:

1. **`previously allocated ... load_name ... names.cpp:7`**: `load_name` crea un `std::string` de 17 caracteres. No cabe en el buffer interno pequeño (SSO, 15 caracteres en libstdc++), así que reserva 18 bytes en el *heap* (17 + `'\0'`).
2. **`freed by ... _M_dispose ... main names.cpp:13`**: en la línea 13, el destructor de `basic_string` libera ese bloque. Esa línea es `names.push_back(load_name(id));`: el temporal muere al final de la expresión completa, en el `;`.
3. **`READ of size 17 ... main names.cpp:16`**: en el segundo bucle, `std::cout << name` lee 17 bytes de ese bloque ya liberado.

La causa: **`std::string_view` no posee los datos**. Es un puntero y una longitud. `push_back(load_name(id))` convierte implícitamente el `std::string` temporal en un `string_view` que apunta a su buffer, guarda la vista en el vector, y el temporal se destruye. El vector acaba lleno de vistas a memoria liberada.

Un detalle que explica por qué este tipo de bug parece intermitente: si los nombres fueran cortos (`"user-0"`), cabrían en el SSO, el texto viviría dentro del propio objeto temporal en la pila, y ASan informaría `stack-use-after-scope`, o sin ASan el programa podría imprimir texto correcto por casualidad. El bug sería el mismo.

**Arreglo**: el vector debe poseer los strings.

```cpp
#include <iostream>
#include <string>
#include <vector>

std::string load_name(int id) {
    return "customer-number-" + std::to_string(id);
}

int main() {
    std::vector<std::string> names;
    names.reserve(3);
    for (int id = 0; id < 3; ++id) {
        names.push_back(load_name(id));   // mueve el temporal: sin copia
    }
    for (const std::string& name : names) {
        std::cout << name << '\n';
    }
}
```

`push_back` de un temporal usa el constructor de movimiento: no hay copia del texto, solo se transfiere el buffer.

**Regla para `string_view`**: úsalo como **parámetro** de funciones que leen texto (acepta `std::string`, literales y subcadenas sin copiar) y como valor local de vida corta. **No lo guardes** (en miembros, contenedores o variables que sobreviven a la expresión) salvo que puedas garantizar que el dueño de los datos vive más. Lo mismo vale para `std::span`.

```cpp
// Bien: la vista vive solo durante la llamada
bool is_vip(std::string_view name) { return name.starts_with("vip-"); }

// Mal: devuelve una vista a un objeto que muere al salir
std::string_view first_word(std::string text) {
    return std::string_view(text).substr(0, text.find(' '));  // text se destruye aquí
}
```

Sobre los avisos del compilador: Clang avisa en casos directos como `std::string_view sv = std::string("x");` (`-Wdangling-gsl`, activo por defecto), pero **ningún compilador detecta el caso del contenedor**: el temporal y el `push_back` están en la misma línea y la vista sobrevive dentro del vector. Por eso este tipo de error se encuentra con sanitizers, no con avisos.

Verificación:

```sh
g++ -std=c++20 -g -O1 -fsanitize=address -fno-omit-frame-pointer src/names.cpp -o names && ./names
```

La versión corregida imprime `customer-number-0` a `customer-number-2` sin ningún informe de ASan. Merece la pena dejar un binario de tests con ASan en el CI: este bug no da síntomas fiables sin él.""",
            },
        ]
    },
    # 16) C++: invalidación de iteradores al borrar en un bucle y push_back en range-for; segfault. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": r"""This crashes only with some input files:

```cpp
std::vector<Order> orders = load_orders(path);
for (auto it = orders.begin(); it != orders.end(); ++it) {
    if (it->cancelled) {
        orders.erase(it);
    }
}
```

```
Program received signal SIGSEGV, Segmentation fault.
0x000055555555a3c4 in purge_cancelled (orders=...) at orders.cpp:27
27	        if (it->cancelled) {
```

Also, in another function, I do `orders.push_back(...)` inside a range-based `for` over `orders` and that crashes too. Same root cause?""",
            },
            {
                "role": "assistant",
                "content": r"""Yes, same root cause: **iterator invalidation**. Both loops keep using an iterator after an operation that the standard says invalidates it, which is undefined behavior.

## The erase loop

`orders.erase(it)` shifts every following element one slot to the left and invalidates `it` and every iterator after it. Then the loop runs `++it` on that invalid iterator. In practice, with `std::vector`, the iterator is a pointer, so here is what really happens:

- **Two cancelled orders in a row**: after erasing the first, the second slides into `it`'s position, then `++it` skips it. No crash, just a wrong result: a cancelled order survives.
- **The last order is cancelled**: after the erase, `it` points to the new `end()`. `++it` moves past it, `it != orders.end()` is never true again, and the loop reads beyond the buffer until it hits unmapped memory. That's your segfault at line 27, and why it depends on the input file.

Fix it with the standard algorithm instead of a manual loop. In C++20:

```cpp
#include <vector>

std::size_t purge_cancelled(std::vector<Order>& orders) {
    return std::erase_if(orders, [](const Order& o) { return o.cancelled; });
}
```

Before C++20, the erase-remove idiom does the same:

```cpp
orders.erase(std::remove_if(orders.begin(), orders.end(),
                            [](const Order& o) { return o.cancelled; }),
             orders.end());
```

Besides being correct, it is faster: `remove_if` compacts the survivors in one pass, O(n), while erasing inside the loop shifts the tail on every erase, O(n²) for many cancellations.

If you really need a manual loop (for example, to log each removal), use the iterator that `erase` returns, and only advance when you did not erase:

```cpp
for (auto it = orders.begin(); it != orders.end();) {
    if (it->cancelled) {
        it = orders.erase(it);
    } else {
        ++it;
    }
}
```

## The `push_back` inside a range-for

A range-based `for` is sugar for a loop over hidden `begin()`/`end()` iterators. When `push_back` exceeds the capacity, the vector allocates a new buffer, moves the elements, and frees the old one. The hidden iterators, and any reference to an element such as the loop variable, now point to freed memory. Collect the new elements separately and append them after the loop, or iterate by index with the size captured beforehand, if the new elements should not be visited.

## Invalidation rules worth memorizing

| Container | Insert | Erase |
|---|---|---|
| `vector` | all, if it reallocates; otherwise those after the insertion point | the erased one and all after it |
| `deque` | all iterators (references survive if inserting at the ends) | all, unless erasing at the ends |
| `list`, `map`, `set` | none | only the erased one |
| `unordered_map` / `set` | all iterators if it rehashes; references to elements survive | only the erased one |

## Verification

libstdc++ has a debug mode that turns this UB into a clear error. Build your tests with it:

```sh
g++ -std=c++20 -g -D_GLIBCXX_DEBUG orders.cpp test_orders.cpp -o test_orders && ./test_orders
```

With the original loop it aborts with a message like "attempt to increment a singular iterator" pointing at the exact line, instead of crashing somewhere random. And a regression test that covers both bad cases:

```cpp
#include <cassert>

int main() {
    std::vector<Order> orders = {{1, false}, {2, true}, {3, true}, {4, false}, {5, true}};
    assert(purge_cancelled(orders) == 3);
    assert(orders.size() == 2 && orders[0].id == 1 && orders[1].id == 4);
}
```

This assumes `struct Order { int id; bool cancelled; };`. Orders 2 and 3 are consecutive and 5 is last, the two cases that break the original loop.""",
            },
        ]
    },
    # 17) C++: const correctness, métodos const, mutable para caché con mutex. System rioplatense
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo."},
            {
                "role": "user",
                "content": "¿Para qué sirve el `const` al final de un método en C++? En el código del laburo está por todos lados y también vi miembros `mutable`. ¿Cuándo tiene sentido cada cosa?",
            },
            {
                "role": "assistant",
                "content": r"""El `const` al final dice «este método no modifica el objeto». Técnicamente, dentro de ese método `this` es un `const T*`: el compilador rechaza cualquier asignación a miembros. Y la consecuencia práctica es la importante: **solo los métodos `const` se pueden llamar sobre un objeto `const` o a través de una referencia `const`**.

Eso último hace que el `const` se contagie, para bien:

```cpp
#include <string>

class Customer {
public:
    explicit Customer(std::string name) : name_(std::move(name)) {}
    const std::string& name() const { return name_; }   // const: no cambia nada
    void rename(std::string name) { name_ = std::move(name); }
private:
    std::string name_;
};

void print(const Customer& c) {   // por referencia const: sin copia y sin modificar
    c.name();                     // compila porque name() es const
    // c.rename("x");             // no compila: rename no es const
}
```

Si te olvidás el `const` en `name()`, `print` no compila, y la tentación es quitar el `const` del parámetro: a partir de ahí, nadie sabe qué funciones modifican qué. Por eso la regla es **marcar `const` todo método que no cambie el estado observable**, desde el principio.

**`mutable`** existe para la diferencia entre constancia *física* y *lógica*: hay miembros que cambian sin que el objeto cambie para quien lo usa. Los dos casos legítimos son una caché y un mutex:

```cpp
#include <mutex>
#include <optional>
#include <utility>
#include <vector>

class Report {
public:
    explicit Report(std::vector<double> values) : values_(std::move(values)) {}

    double total() const {
        std::lock_guard lock(mutex_);
        if (!cached_total_) {
            double sum = 0.0;
            for (double v : values_) {
                sum += v;
            }
            cached_total_ = sum;
        }
        return *cached_total_;
    }

    void add(double value) {
        std::lock_guard lock(mutex_);
        values_.push_back(value);
        cached_total_.reset();   // invalida la caché
    }

private:
    std::vector<double> values_;
    mutable std::optional<double> cached_total_;  // cambia, pero el total "lógico" no
    mutable std::mutex mutex_;                    // bloquear no cambia el informe
};
```

Fijate en el mutex, que es lo que más se olvida. Desde C++11, la biblioteca estándar asume que **llamar a métodos `const` desde varios hilos a la vez es seguro**. Si un método `const` escribe en un miembro `mutable` sin protección, dos hilos que llamen a `total()` a la vez generan una carrera de datos, aunque «solo estén leyendo». `mutable` sin sincronización rompe esa promesa.

Un efecto colateral a tener en cuenta: `std::mutex` no se puede copiar ni mover, así que `Report` tampoco. Si lo necesitás copiable, tenés que escribir la copia a mano copiando `values_` y dejando que cada copia tenga su propio mutex.

Cuándo **no** usar `mutable`: para esquivar el `const` de un método que en realidad sí cambia el estado visible. Si `total()` modificara `values_`, la solución es que no sea `const`, no hacer `mutable` a `values_`.

Y ya que estamos, el `const` en punteros, que confunde mucho: **se aplica a lo que tiene a la izquierda** (o a la derecha si no hay nada a la izquierda).

| Declaración | Qué es constante |
|---|---|
| `const char* p` | los caracteres (no podés hacer `*p = 'x'`) |
| `char* const p` | el puntero (no podés hacer `p = otro`) |
| `const char* const p` | ambos |

Comprobación:

```cpp
#include <cassert>

int main() {
    Report report({1.0, 2.0});
    const Report& view = report;
    assert(view.total() == 3.0);   // método const sobre referencia const
    report.add(4.0);
    assert(view.total() == 7.0);   // la caché se invalidó con add()
}
```

Y si querés comprobar la seguridad entre hilos, lanzá varios `std::thread` que llamen a `total()` mientras otro llama a `add()`, compilando con `-fsanitize=thread`. Sin el mutex, ThreadSanitizer informa la carrera en `cached_total_`; con el mutex, no.""",
            },
        ]
    },
    # 18) C++20: templates con concepts, requires, concepto propio, testear que no compila; multiturno sobre auto abreviado
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una función template `average` que funciona con contenedores de int o double, pero si alguien la llama con un `std::vector<std::string>` el error de compilación ocupa 200 líneas. ¿Cómo se resuelve con concepts de C++20?",
            },
            {
                "role": "assistant",
                "content": r"""Declarando los requisitos en la firma. Con un *concept*, el compilador rechaza la llamada **en el punto de la llamada**, con un mensaje que dice qué requisito no se cumple, en vez de fallar dentro del cuerpo de la plantilla con una cascada de errores de instanciación.

```cpp
#include <concepts>
#include <cstddef>
#include <ranges>
#include <stdexcept>

template <typename T>
concept Arithmetic = std::integral<T> || std::floating_point<T>;

template <std::ranges::input_range R>
    requires Arithmetic<std::ranges::range_value_t<R>>
double average(R&& values) {
    double sum = 0.0;
    std::size_t count = 0;
    for (auto v : values) {
        sum += static_cast<double>(v);
        ++count;
    }
    if (count == 0) {
        throw std::invalid_argument("average of an empty range");
    }
    return sum / static_cast<double>(count);
}
```

Qué expresa la firma:

- **`std::ranges::input_range R`**: acepta cualquier cosa recorrible (`vector`, `list`, arrays, vistas), no solo `std::vector`.
- **`requires Arithmetic<range_value_t<R>>`**: el tipo de los elementos debe ser entero o de coma flotante.

Con `std::vector<std::string>`, GCC ahora informa, en pocas líneas, algo como «no matching function for call to 'average'... constraints not satisfied... the expression 'Arithmetic<std::__cxx11::basic_string<char> >' evaluated to 'false'». El mensaje nombra el *concept* que falló.

Para requisitos propios que no existen en `<concepts>`, una *requires-expression* describe operaciones que el tipo debe soportar:

```cpp
#include <concepts>
#include <string>
#include <string_view>

template <typename T>
concept Serializable = requires(const T& value, std::string& out) {
    { value.serialize(out) } -> std::same_as<void>;
    { T::type_name() } -> std::convertible_to<std::string_view>;
};
```

Lo equivalente antes de C++20 era `std::enable_if_t<...>` en un parámetro de plantilla (SFINAE): funciona, pero es ilegible y los errores siguen siendo largos.

**Cómo probar que algo no compila**, que es la mitad del valor de un *concept*: con `static_assert` sobre un *concept* que envuelva la llamada.

```cpp
#include <list>
#include <string>
#include <vector>

template <typename R>
concept Averageable = requires(R r) { average(r); };

static_assert(Averageable<std::vector<int>>);
static_assert(Averageable<std::list<double>>);
static_assert(!Averageable<std::vector<std::string>>);
```

El *concept* intermedio no es capricho: una *requires-expression* escrita directamente en un `static_assert` fuera de una plantilla hace que el programa sea incorrecto si el requisito falla, en vez de evaluarse a `false`. Dentro de un *concept*, la sustitución fallida da `false` limpiamente.

Comprobación de valores, en tiempo de ejecución:

```cpp
#include <cassert>

int main() {
    assert(average(std::vector<int>{1, 2, 3, 4}) == 2.5);
    int raw[] = {10, 20};
    assert(average(raw) == 15.0);
}
```""",
            },
            {
                "role": "user",
                "content": "¿Y la sintaxis `void f(std::integral auto x)` que veo en código nuevo? ¿Es lo mismo que el template con requires?",
            },
            {
                "role": "assistant",
                "content": r"""Es la **plantilla de función abreviada** de C++20, y sí, es lo mismo con menos ceremonia:

```cpp
void f(std::integral auto x);

// equivale exactamente a
template <std::integral T>
void f(T x);

// y a
template <typename T>
    requires std::integral<T>
void f(T x);
```

Cada `auto` en un parámetro introduce un parámetro de plantilla nuevo, y el *concept* delante lo restringe.

Tres diferencias prácticas a la hora de elegir forma:

1. **Cada `auto` es independiente.** `void add(std::integral auto a, std::integral auto b)` acepta `add(1, 2L)`: `a` es `int` y `b` es `long`. Si necesitas que los dos sean del mismo tipo, usa la forma con nombre: `template <std::integral T> void add(T a, T b)`.
2. **No tienes nombre para el tipo.** Dentro del cuerpo tendrás que escribir `decltype(x)` (o `std::remove_cvref_t<decltype(x)>` si importa la referencia). Si el tipo aparece varias veces en el cuerpo, la forma con nombre se lee mejor.
3. **Los requisitos compuestos** (relaciones entre varios parámetros, como `requires std::convertible_to<U, T>`) solo caben en la forma con `requires`.

Regla práctica: `auto` restringido para funciones cortas con un parámetro genérico; plantilla con nombre cuando hay relaciones entre tipos o el tipo se usa en el cuerpo.

Algo que los *concepts* permiten y que con SFINAE era muy incómodo: **sobrecargar por restricciones**. Cuando varias sobrecargas encajan, gana la **más restringida**, siempre que una restricción incluya a la otra a través de *concepts* (lo que la norma llama *subsumption*):

```cpp
#include <cassert>
#include <concepts>
#include <string>

std::string describe(std::integral auto) { return "integral"; }
std::string describe(std::signed_integral auto) { return "signed integral"; }

int main() {
    assert(describe(5) == "signed integral");  // int encaja en ambas; gana la más restringida
    assert(describe(5u) == "integral");        // unsigned solo encaja en la primera
}
```

Funciona porque `std::signed_integral<T>` está definido como `std::integral<T> && std::is_signed_v<T>`: el compilador ve que incluye a `std::integral` y la considera más específica.

La trampa: si escribes la restricción a mano como `requires std::is_integral_v<T> && std::is_signed_v<T>`, sin pasar por el *concept* `std::integral`, el compilador **no** puede deducir esa inclusión (compara *concepts*, no expresiones booleanas arbitrarias), y `describe(5)` da error de ambigüedad. Por eso conviene construir los requisitos componiendo *concepts* con nombre, no *traits* sueltos.""",
            },
        ]
    },
    # 19) C++: map vs unordered_map, operator[] que inserta, try_emplace, hash propio, búsqueda heterogénea
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuándo uso std::map y cuándo std::unordered_map? Y otra cosa rara: para ver si una clave existe hago `if (counts[key] == 0)` y el map no para de crecer.",
            },
            {
                "role": "assistant",
                "content": r"""Lo raro primero, porque es un error clásico: **`operator[]` inserta**. Si la clave no existe, crea una entrada con un valor construido por defecto (0 para `int`) y te devuelve una referencia a ella. Cada consulta de una clave inexistente añade una entrada. Por eso, además, `operator[]` no se puede usar sobre un map `const` y exige que el valor tenga constructor por defecto.

Para consultar sin modificar:

```cpp
#include <map>
#include <string>

std::map<std::string, int> counts;

bool exists = counts.contains("ana");            // C++20
auto it = counts.find("ana");                    // si además necesitas el valor
int value = (it != counts.end()) ? it->second : 0;
```

Y para insertar con intención explícita (C++17):

| Quieres | Usa |
|---|---|
| leer o crear con valor por defecto (contadores) | `counts[key]++` (aquí `operator[]` es justo lo que quieres) |
| insertar solo si no existe, sin construir el valor si existe | `try_emplace(key, args...)` |
| insertar o sobrescribir | `insert_or_assign(key, value)` |

**`map` frente a `unordered_map`:**

| | `std::map` | `std::unordered_map` |
|---|---|---|
| Estructura | árbol rojo-negro | tabla hash |
| Búsqueda / inserción | O(log n) | O(1) en promedio, O(n) en el peor caso |
| Orden de iteración | ordenado por clave | sin orden definido |
| Consultas por rango | sí (`lower_bound`, `upper_bound`) | no |
| Iteradores al insertar | nunca se invalidan | se invalidan si hay *rehash* |
| La clave necesita | `operator<` (o `<=>`) | `std::hash` y `operator==` |

Por defecto, `unordered_map` cuando solo buscas por clave exacta; `map` cuando necesitas orden, rangos o iteración estable. Para mapas pequeños (decenas de elementos) que se recorren mucho, un `std::vector` de pares ordenado suele ganar a los dos por localidad de caché (C++23 lo formaliza como `std::flat_map`).

**Clave propia en `unordered_map`**: necesitas igualdad y un *hash*:

```cpp
#include <cstddef>
#include <functional>
#include <unordered_map>

struct GridPoint {
    int x;
    int y;
    bool operator==(const GridPoint&) const = default;  // C++20
};

struct GridPointHash {
    std::size_t operator()(const GridPoint& p) const noexcept {
        std::size_t h = std::hash<int>{}(p.x);
        // combinación al estilo boost::hash_combine
        h ^= std::hash<int>{}(p.y) + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
        return h;
    }
};

std::unordered_map<GridPoint, int, GridPointHash> visits;
```

No combines con un simple `x ^ y`: `(1, 2)` y `(2, 1)` colisionan, y todos los puntos de la diagonal dan 0. Con muchas colisiones, la tabla degenera a O(n). Para `std::map` basta con `auto operator<=>(const GridPoint&) const = default;`.

**Un detalle de rendimiento con claves `std::string`**: `counts.find(some_string_view)` no compila con el comparador por defecto, y `find("ana")` construye un `std::string` temporal. Declarando el comparador transparente, la búsqueda acepta `string_view` o literales sin asignar memoria:

```cpp
std::map<std::string, int, std::less<>> counts;   // búsqueda heterogénea
std::string_view key = "ana";
auto found = counts.find(key);                    // sin crear un std::string
```

Comprobación del problema original:

```cpp
#include <cassert>
#include <map>
#include <string>

int main() {
    std::map<std::string, int> counts{{"ana", 2}};
    if (counts["luis"] == 0) {}        // consulta "inocente"
    assert(counts.size() == 2);        // ...que insertó "luis"

    std::map<std::string, int> clean{{"ana", 2}};
    assert(!clean.contains("luis"));
    assert(clean.size() == 1);         // contains no modifica
}
```""",
            },
        ]
    },
    # 20) C++20: algoritmos y ranges en vez de bucles a mano; proyecciones, unique+erase, vistas. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "Our C++20 codebase is full of hand-written loops: find the first match, count, sort by a field, remove duplicates, sum. Code review keeps saying 'use algorithms'. What's the modern way to write these, and is it actually better or just style?",
            },
            {
                "role": "assistant",
                "content": r"""It's better for concrete reasons, not style: the algorithm name states the intent, the implementation is already tested (no off-by-one, no forgotten edge case), and complexity is guaranteed by the standard. Here are your five loops rewritten with C++20 ranges:

```cpp
#include <algorithm>
#include <iterator>
#include <numeric>
#include <ranges>
#include <string>
#include <vector>

struct Employee {
    std::string name;
    std::string team;
    int salary;
};

int main() {
    std::vector<Employee> staff = {
        {"Ana", "dev", 90'000}, {"Luis", "ops", 70'000},
        {"Eva", "dev", 85'000}, {"Raúl", "ops", 95'000},
    };

    // 1. Sort by a field: a projection instead of a hand-written comparator
    std::ranges::sort(staff, std::ranges::greater{}, &Employee::salary);

    // 2. Find the first match by field
    const std::string target = "ops";
    auto first_ops = std::ranges::find(staff, target, &Employee::team);

    // 3. Count with a predicate
    auto high_earners = std::ranges::count_if(staff, [](const Employee& e) { return e.salary > 80'000; });

    // 4. Sum (std::accumulate is not in std::ranges until C++23's fold_left)
    int payroll = std::accumulate(staff.begin(), staff.end(), 0,
                                  [](int acc, const Employee& e) { return acc + e.salary; });

    // 5. Distinct teams: collect, sort, unique, erase
    std::vector<std::string> teams;
    std::ranges::transform(staff, std::back_inserter(teams), &Employee::team);
    std::ranges::sort(teams);
    auto [dup_first, dup_last] = std::ranges::unique(teams);
    teams.erase(dup_first, dup_last);

    // Lazy pipeline: names of dev employees, no intermediate vector
    for (const std::string& name : staff
             | std::views::filter([](const Employee& e) { return e.team == "dev"; })
             | std::views::transform(&Employee::name)) {
        (void)name;  // use name
    }

    return (first_ops != staff.end() && high_earners == 3 && payroll == 340'000
            && teams.size() == 2) ? 0 : 1;
}
```

What is worth noticing:

- **Projections** (`&Employee::salary`) replace the most common lambda in C++: "compare by this field". `sort(staff, greater{}, &Employee::salary)` reads as what it does.
- **`std::ranges::unique` does not remove anything**. Like `std::unique`, it moves the duplicates to the end and returns the subrange you must `erase`. Forgetting the `erase` is the classic bug; in C++20, `std::erase_if` covers the predicate case, but there is no `std::erase_unique`.
- **Range algorithms take the whole container**, so you can't mismatch `begin()` of one vector with `end()` of another.
- **Views are lazy and non-owning.** The `filter | transform` pipeline does no work until iterated and allocates nothing. The flip side: a view over a temporary container dangles. Range algorithms protect you in one case: calling `std::ranges::find(make_vector(), x)` returns `std::ranges::dangling`, a type that refuses to be dereferenced, so the mistake becomes a compile error instead of a crash.

Where a plain loop is still the right tool: when the body does several unrelated things per element, or when the algorithm version needs a lambda so complex that the name no longer communicates anything. And be aware that view pipelines can be slow in unoptimized debug builds and add compile time; measure before using them in hot paths built with `-O0`.

Two more swaps that pay off in review:

| Hand-written | Algorithm |
|---|---|
| loop with a `found` flag | `std::ranges::any_of` / `all_of` / `none_of` |
| loop tracking the max element | `std::ranges::max_element(v, {}, &T::field)` |
| nested loops checking membership in a sorted vector | `std::ranges::binary_search` |
| `sort` just to get the top 3 | `std::ranges::partial_sort` or `nth_element` |

Verification: the `main` above returns 0 only if every result is right (Raúl's 95,000 sorts first, so the first `ops` employee is found; three salaries exceed 80,000; the total is 340,000; two distinct teams). Build it with `-std=c++20 -Wall -Wextra` and check `echo $?` prints `0`.""",
            },
        ]
    },
    # 21) C++17: optional vs variant, visit con overloaded, trampas, expected en C++23. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En C++17, ¿cómo modelo un resultado que puede ser «valor», «no encontrado» o «error con mensaje» sin excepciones ni punteros nulos? He visto std::optional y std::variant pero no tengo claro cuál usar.",
            },
            {
                "role": "assistant",
                "content": r"""Depende de cuántos «no valores» distintos hay:

- **`std::optional<T>`**: hay valor o no lo hay, y el motivo da igual. «No encontrado» sin más detalle.
- **`std::variant<A, B, C>`**: el resultado es exactamente uno de varios tipos, cada uno con sus datos. Tu caso de tres estados.
- **`std::expected<T, E>`** (C++23): valor o error tipado. Es lo ideal para «valor o error», pero en C++17 no existe en la biblioteca estándar.

`optional`, cuando la ausencia no necesita explicación:

```cpp
#include <optional>
#include <string>
#include <unordered_map>

struct User {
    int id;
    std::string name;
};

std::optional<User> find_user(const std::unordered_map<int, User>& users, int id) {
    auto it = users.find(id);
    if (it == users.end()) {
        return std::nullopt;
    }
    return it->second;
}
```

`variant` con un visitante, para tus tres casos:

```cpp
#include <string>
#include <variant>

struct NotFound {
    int id;
};

struct DbError {
    std::string message;
};

using LookupResult = std::variant<User, NotFound, DbError>;

// Patrón "overloaded": junta varias lambdas en un solo objeto con varios operator()
template <class... Ts>
struct overloaded : Ts... {
    using Ts::operator()...;
};
template <class... Ts>
overloaded(Ts...) -> overloaded<Ts...>;  // guía de deducción, necesaria en C++17

std::string describe(const LookupResult& result) {
    return std::visit(overloaded{
        [](const User& u) { return "user " + u.name; },
        [](const NotFound& nf) { return "no user with id " + std::to_string(nf.id); },
        [](const DbError& e) { return "database error: " + e.message; },
    }, result);
}
```

Lo que te da `std::visit`: si mañana añades un cuarto tipo al `variant` y olvidas su lambda, **no compila**. Es la misma garantía de exhaustividad que un `switch` sobre un tipo sellado en otros lenguajes. Para consultas puntuales, `std::holds_alternative<NotFound>(r)` y `std::get_if<User>(&r)` (devuelve puntero nulo si no es ese tipo) evitan el visitante.

Trampas conocidas:

1. **`*opt` sobre un `optional` vacío es comportamiento indefinido.** `opt.value()` lanza `std::bad_optional_access`, y `opt.value_or(def)` da un valor por defecto. Usa `*opt` solo justo después de comprobar `if (opt)`.
2. **Conversiones sorprendentes en `variant`.** Con `std::variant<std::string, bool> v = "texto";`, los compiladores anteriores a la corrección de C++20 (P0608) elegían `bool`, porque un puntero se convierte a `bool` con una conversión estándar y a `std::string` con una de usuario. Los compiladores actuales eligen `std::string` también en modo C++17, pero si mantienes código con compiladores antiguos, construye explícitamente: `v = std::string("texto")`.
3. **`valueless_by_exception()`**: si una asignación al `variant` lanza a mitad, puede quedar sin valor. Es raro (requiere que el constructor del tipo nuevo lance), pero `std::visit` lanzaría `bad_variant_access`.
4. **No hay `optional<T&>`** (hasta C++26). Para «referencia opcional» usa `T*`, que ya expresa exactamente eso.

Si puedes usar C++23 (GCC 12+ y Clang 16+ con `-std=c++23`), para «valor o error» `std::expected<User, DbError>` comunica mejor la intención que un `variant` de tres tipos, y trae `and_then`/`transform` para encadenar operaciones. En C++17, la librería de cabecera única `tl::expected` ofrece casi la misma interfaz.

Comprobación:

```cpp
#include <cassert>

int main() {
    assert(describe(User{1, "Ana"}) == "user Ana");
    assert(describe(NotFound{7}) == "no user with id 7");
    assert(describe(DbError{"timeout"}) == "database error: timeout");

    std::unordered_map<int, User> users{{1, User{1, "Ana"}}};
    assert(find_user(users, 1).has_value());
    assert(find_user(users, 2).value_or(User{0, "anon"}).name == "anon");
}
```""",
            },
        ]
    },
    # 22) C++: excepciones vs códigos de error en una librería con consumidores -fno-exceptions; multiturno. System arquitecto
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto de software senior. Justifica cada recomendación con sus trade-offs."},
            {
                "role": "user",
                "content": "Estamos diseñando una librería C++20 para parsear ficheros de medidas que van a usar otros equipos. Algunos compilan con -fno-exceptions (embebido) y otros no. ¿Excepciones o códigos de error en la API?",
            },
            {
                "role": "assistant",
                "content": r"""Con consumidores que compilan con `-fno-exceptions`, la decisión sobre la **API pública** está tomada: **no puede lanzar**. Una excepción que cruza a código compilado sin soporte de excepciones no tiene dónde capturarse y termina en `std::terminate`. Lo que queda por decidir es cómo representar el error, y si se usan excepciones *dentro* de la librería.

## Trade-offs generales

| | Excepciones | Códigos de error / tipos resultado |
|---|---|---|
| Ignorar un error | imposible: si nadie captura, el programa termina | posible; `[[nodiscard]]` lo mitiga |
| Camino feliz | limpio, sin comprobaciones | una comprobación por llamada |
| Coste si no hay error | prácticamente cero (tablas de desenrollado) | una comparación por llamada |
| Coste si hay error | alto y variable (microsegundos, reserva de memoria) | constante y bajo |
| Constructores que fallan | natural | requiere fábricas o objetos en estado inválido |
| `-fno-exceptions`, interfaces C, tiempo real | no aplicable | funciona |

Para un parser, hay un argumento adicional: los errores **no son excepcionales**. Un fichero con una línea mal formada es un caso esperado; si el usuario procesa miles de ficheros con un 5 % de errores, lanzar en cada uno cuesta tiempo real y hace ruido en los *profilers*.

## Diseño propuesto

Un tipo de error con información útil (no solo un entero) y un tipo resultado:

```cpp
#include <cstddef>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

namespace meas {

enum class ParseErrc {
    file_not_found = 1,
    bad_header,
    bad_value,
    truncated,
};

const std::error_category& parse_category() noexcept;

inline std::error_code make_error_code(ParseErrc e) noexcept {
    return {static_cast<int>(e), parse_category()};
}

struct ParseError {
    std::error_code code;
    std::size_t line = 0;  // 0 si no aplica
};

struct Measurement {
    double timestamp;
    double value;
};

struct ParseResult {
    std::vector<Measurement> values;
    ParseError error;  // error.code vacío si todo fue bien

    explicit operator bool() const noexcept { return !error.code; }
};

[[nodiscard]] ParseResult parse_file(const std::filesystem::path& path) noexcept;

}  // namespace meas

template <>
struct std::is_error_code_enum<meas::ParseErrc> : std::true_type {};
```

Por qué cada pieza:

- **`std::error_code` con categoría propia**: es el mecanismo estándar, se compara con `std::errc` y con códigos de otros sistemas, y `code.message()` da el texto. El usuario puede escribir `if (r.error.code == meas::ParseErrc::bad_value)` gracias a la especialización de `is_error_code_enum`.
- **`line` junto al código**: un parser que solo dice «valor incorrecto» sin decir dónde obliga a depurar a ciegas.
- **`[[nodiscard]]`**: el compilador avisa si alguien ignora el resultado.
- **`noexcept`** documenta y garantiza el contrato. Coste conocido: si una reserva de memoria falla dentro, el programa termina en vez de informar. Para la mayoría de usos es aceptable; si no lo es para el equipo de embebido, la librería debería aceptar un asignador o un buffer proporcionado por el llamador.

Cuando todos los consumidores puedan usar C++23, `std::expected<std::vector<Measurement>, ParseError>` sustituye a `ParseResult` con la misma semántica y mejor ergonomía; diseñar ahora con un tipo resultado hace esa migración casi mecánica.

## Cómo validar el diseño

Escribid el código cliente de cada equipo **antes** de implementar: un ejemplo de uso en embebido compilado con `-fno-exceptions` y uno de escritorio. Si el de escritorio queda incómodo, se le puede ofrecer una capa fina opcional que lance (`parse_file_or_throw`) construida sobre la API sin excepciones, nunca al revés.""",
            },
            {
                "role": "user",
                "content": "¿Y dentro de la librería podemos usar excepciones, siempre que no salgan por la API? El código interno queda mucho más limpio así.",
            },
            {
                "role": "assistant",
                "content": r"""Sí, con dos condiciones estrictas. Si no se cumplen, el equipo de embebido no podrá ni compilar.

**1. Las excepciones solo pueden vivir en archivos `.cpp`, nunca en cabeceras públicas.** El código de una cabecera (funciones `inline`, plantillas) se compila **en la unidad de traducción del consumidor**, con sus opciones. Un `throw` o un `try` en una plantilla pública, compilado con `-fno-exceptions`, da directamente un error de GCC: «exception handling disabled, use '-fexceptions' to enable». La librería se compila una vez, con excepciones activadas; lo que va en las cabeceras debe ser válido en los dos modos.

**2. Toda función pública tiene una frontera que captura todo y traduce.** Un único punto de traducción, privado, en el `.cpp`:

```cpp
// parse.cpp (compilado con excepciones)
#include <new>

namespace meas {
namespace {

class ParseFailure : public std::exception {
public:
    ParseFailure(ParseErrc code, std::size_t line) : error_{make_error_code(code), line} {}
    const ParseError& error() const noexcept { return error_; }
    const char* what() const noexcept override { return "parse failure"; }

private:
    ParseError error_;
};

template <typename Body>
ParseError at_boundary(Body&& body) noexcept {
    try {
        body();
        return {};
    } catch (const ParseFailure& failure) {
        return failure.error();
    } catch (const std::bad_alloc&) {
        return {std::make_error_code(std::errc::not_enough_memory), 0};
    } catch (...) {
        return {std::make_error_code(std::errc::state_not_recoverable), 0};
    }
}

}  // namespace

ParseResult parse_file(const std::filesystem::path& path) noexcept {
    ParseResult result;
    result.error = at_boundary([&] {
        // código interno limpio: lanza ParseFailure(ParseErrc::bad_value, line) donde haga falta
        result.values = parse_lines(open_or_throw(path));
    });
    return result;
}

}  // namespace meas
```

(`parse_lines` y `open_or_throw` son las funciones internas que lanzan.)

Trade-offs que conviene asumir conscientemente:

- **La librería necesita el runtime de excepciones** (en GCC, la parte de `libgcc`/`libstdc++` que desenrolla la pila), aunque el consumidor no las use. En la mayoría de plataformas embebidas con un toolchain completo está disponible; en algunas muy restringidas no. Confirmadlo con el equipo de embebido **antes** de elegir este camino: si su toolchain no lo trae, la librería entera tiene que ser sin excepciones.
- **Tamaño del binario**: las tablas de desenrollado añaden tamaño. En escritorio es irrelevante; en un microcontrolador puede no serlo. Medidlo con `size` sobre el binario final de un ejemplo de embebido.
- **Coste de lanzar**: con ficheros con muchos errores (el 5 % de antes), cada `throw` cuesta. Si el perfil lo muestra, los errores frecuentes y esperados pueden devolverse sin lanzar, reservando las excepciones internas para lo realmente excepcional.

Prueba que fija el contrato: un test compilado con `-fno-exceptions` que incluya **todas** las cabeceras públicas e invoque la API, en el CI. Si alguien añade un `throw` a una cabecera, ese test deja de compilar; si alguien olvida la frontera y algo escapa, el test termina en `std::terminate` en vez de pasar.""",
            },
        ]
    },
    # 23) C++: capturas en lambdas ([=], [&], [this], init-capture) y referencias colgantes en callbacks
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Qué diferencia hay entre capturar con `[=]`, `[&]`, `[this]` y `[x = std::move(x)]` en una lambda de C++? ¿Cuándo es peligroso cada uno?",
            },
            {
                "role": "assistant",
                "content": r"""La pregunta clave para cada captura es: **¿la lambda puede ejecutarse después de que termine la función que la creó?** Si no (se usa y se descarta en el momento, como en un `std::sort`), casi cualquier captura es segura. Si sí (se guarda en un `std::function`, se pasa a un hilo, se registra como *callback*), las capturas por referencia son una bomba de relojería.

| Captura | Qué guarda | Peligro |
|---|---|---|
| `[&]` / `[&x]` | referencias a variables locales | colgantes si la lambda sobrevive a la función |
| `[=]` / `[x]` | copias de las variables | copias caras; en métodos, captura `this`, no los miembros |
| `[this]` | el puntero `this` | colgante si el objeto se destruye antes |
| `[*this]` (C++17) | una copia del objeto entero | coste de la copia; los cambios no afectan al original |
| `[x = std::move(x)]` | lo que tú inicialices | ninguno propio; permite capturar tipos solo movibles |

**El error clásico con `[&]`:**

```cpp
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

std::vector<std::function<void()>> pending;

void schedule_greetings(const std::vector<std::string>& names) {
    for (const std::string& name : names) {
        std::string message = "hola, " + name;
        pending.push_back([&message] { std::puts(message.c_str()); });  // referencia colgante
    }
}
```

`message` muere al final de cada iteración, pero la lambda guarda una referencia a ella y se ejecuta más tarde. Compilado con `-fsanitize=address`, la primera ejecución de una tarea informa `stack-use-after-scope`. Sin ASan, imprime basura, el último mensaje repetido o nada, según el día.

La corrección es mover el valor dentro de la lambda:

```cpp
pending.push_back([message = std::move(message)] { std::puts(message.c_str()); });
```

La *init-capture* (C++14) crea un miembro de la lambda inicializado con la expresión que quieras. Es la única forma de capturar tipos que solo se pueden mover:

```cpp
auto buffer = std::make_unique<std::vector<char>>(4096);
auto task = [buffer = std::move(buffer)] { return buffer->size(); };
```

Una advertencia práctica: una lambda que captura un `unique_ptr` no se puede copiar, así que no cabe en un `std::function` (que exige copiabilidad). Usa `std::move_only_function` (C++23) o una plantilla.

**`[=]` dentro de un método engaña:**

```cpp
class Counter {
public:
    auto make_reader() {
        return [=] { return count_; };  // captura this, no una copia de count_
    }
private:
    int count_ = 0;
};
```

`count_` dentro de la lambda es en realidad `this->count_`, así que `[=]` captura `this` por valor, es decir, el puntero. Si el `Counter` se destruye antes de llamar a la lambda, lee memoria liberada. C++20 declaró obsoleta esta captura implícita de `this` con `[=]` y los compiladores avisan; escribe la intención explícitamente: `[this]` si de verdad quieres el objeto vivo, `[count = count_]` si quieres una copia del valor, `[*this]` si quieres una copia del objeto.

**Con `[this]` en hilos y *callbacks***, el objeto debe vivir más que la lambda. Dos formas de garantizarlo:

1. Que el propio objeto sea dueño de lo que ejecuta la lambda y lo detenga en su destructor. Por ejemplo, un miembro `std::jthread` declarado **el último**, para que se destruya (y haga `join`) antes que el resto de miembros que usa la lambda.
2. Si el objeto lo gestiona un `shared_ptr`, capturar `weak_from_this()` y hacer `lock()` dentro.

Comprobación del primer ejemplo, con la versión corregida:

```cpp
int main() {
    schedule_greetings({"Ana", "Luis"});
    for (auto& task : pending) {
        task();  // "hola, Ana" y "hola, Luis"
    }
}
```

Compílalo con `g++ -std=c++20 -g -fsanitize=address`: la versión con `[&message]` aborta con `stack-use-after-scope` en la primera tarea; la versión con `[message = std::move(message)]` imprime los dos saludos sin informes.""",
            },
        ]
    },
    # 24) CMake moderno orientado a targets + GoogleTest con FetchContent; multiturno con undefined reference. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero montar bien un proyecto C++20 con CMake: una librería, un ejecutable que la usa y tests con GoogleTest, sin instalar GoogleTest a mano. Lo que encuentro por internet mezcla estilos de hace diez años con cosas nuevas.",
            },
            {
                "role": "assistant",
                "content": r"""El criterio para separar lo moderno de lo antiguo: **en CMake moderno todo se declara sobre *targets***, no con variables globales. Si ves `include_directories(...)`, `add_definitions(...)` o `set(CMAKE_CXX_FLAGS ...)`, es el estilo antiguo.

Estructura:

```
geo/
├── CMakeLists.txt
├── include/geo/distance.hpp
├── src/distance.cpp
├── src/main.cpp
└── tests/distance_test.cpp
```

`CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.24)
project(geo LANGUAGES CXX)

option(GEO_BUILD_TESTS "Build the unit tests" ON)
option(GEO_SANITIZE "Build with AddressSanitizer and UBSan" OFF)

if(GEO_SANITIZE)
    # antes de crear targets: se aplica a todos los que se definan después
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
endif()

add_library(geo src/distance.cpp)
target_include_directories(geo PUBLIC include)
target_compile_features(geo PUBLIC cxx_std_20)
target_compile_options(geo PRIVATE
    "$<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>"
    "$<$<CXX_COMPILER_ID:MSVC>:/W4>")

add_executable(geo_cli src/main.cpp)
target_link_libraries(geo_cli PRIVATE geo)

if(GEO_BUILD_TESTS)
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.tar.gz
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    )
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)  # MSVC: misma CRT que el proyecto
    FetchContent_MakeAvailable(googletest)

    enable_testing()
    add_executable(geo_tests tests/distance_test.cpp)
    target_link_libraries(geo_tests PRIVATE geo GTest::gtest_main)
    include(GoogleTest)
    gtest_discover_tests(geo_tests)
endif()
```

Lo que importa de cada parte:

- **`PUBLIC` / `PRIVATE` / `INTERFACE`** son los «requisitos de uso». `target_include_directories(geo PUBLIC include)` significa: `geo` compila con `include/`, y **todo lo que enlace con `geo` también**. Por eso `geo_cli` y `geo_tests` no repiten la ruta. Los avisos van como `PRIVATE`: son asunto de la librería, no se imponen a quien la usa.
- **`target_compile_features(... cxx_std_20)`** en vez de `set(CMAKE_CXX_STANDARD 20)`: el requisito viaja con el target.
- **Expresiones generadoras entre comillas y con `;`**: sin comillas, el espacio partiría la expresión en varios argumentos y CMake no la reconocería.
- **`FetchContent`** descarga y compila GoogleTest como parte del proyecto, con tu compilador y tus opciones. La versión queda fijada en el `URL`.
- **`gtest_discover_tests`** registra cada `TEST(...)` como un test independiente de CTest, así que ves exactamente cuál falla.

Uso:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j
ctest --test-dir build --output-on-failure

# variante con sanitizers, en otro directorio
cmake -S . -B build-asan -DCMAKE_BUILD_TYPE=Debug -DGEO_SANITIZE=ON
cmake --build build-asan -j && ctest --test-dir build-asan --output-on-failure
```

Directorios de build separados por configuración, por la misma razón que en Make: no mezclar objetos compilados con opciones distintas.

Un test mínimo para comprobar que todo encaja (asumo `double haversine_km(const Point&, const Point&)` en el espacio de nombres `geo`):

```cpp
#include <gtest/gtest.h>
#include <geo/distance.hpp>

TEST(DistanceTest, SamePointIsZero) {
    geo::Point madrid{40.4168, -3.7038};
    EXPECT_DOUBLE_EQ(geo::haversine_km(madrid, madrid), 0.0);
}

TEST(DistanceTest, MadridToBarcelonaIsAbout505Km) {
    geo::Point madrid{40.4168, -3.7038};
    geo::Point barcelona{41.3874, 2.1686};
    EXPECT_NEAR(geo::haversine_km(madrid, barcelona), 505.0, 5.0);
}
```

Si `ctest` lista los dos tests y pasan, la librería, el ejecutable de tests y la dependencia descargada están bien conectados.""",
            },
            {
                "role": "user",
                "content": r"""Lo armé así, pero al compilar los tests me sale:

```
/usr/bin/ld: CMakeFiles/geo_tests.dir/tests/distance_test.cpp.o: in function `DistanceTest_SamePointIsZero_Test::TestBody()':
distance_test.cpp:(.text+0x5a): undefined reference to `geo::haversine_km(geo::Point const&, geo::Point const&)'
collect2: error: ld returned 1 exit status
```

El header y el .cpp existen, y `geo_tests` enlaza con `geo`.""",
            },
            {
                "role": "assistant",
                "content": r"""El enlazador busca exactamente el símbolo `geo::haversine_km(geo::Point const&, geo::Point const&)` y no lo encuentra en ninguna parte. Si el target enlaza con `geo`, las causas posibles, de más a menos frecuente, son:

1. **El `.cpp` define algo con otra firma o en otro espacio de nombres.** Por ejemplo, la definición está fuera de `namespace geo`, o recibe `Point` por valor en vez de `const Point&`. Para C++ son funciones distintas: el compilador acepta la definición sin quejarse (es una sobrecarga nueva) y el enlazador no encuentra la declarada.
2. **El `.cpp` no está en las fuentes del target** (por ejemplo, un `src/geo/distance.cpp` cuando `add_library` lista `src/distance.cpp`).
3. **La función está marcada `inline` en el `.cpp`**, o es una plantilla definida en el `.cpp`: el compilador no emite el símbolo para otras unidades.

No hace falta adivinar: mira qué símbolos contiene realmente la librería.

```sh
nm -C build/libgeo.a | grep haversine
```

- `T geo::haversine_km(geo::Point const&, geo::Point const&)` → el símbolo existe; el problema estaría en el enlazado (raro con CMake si `target_link_libraries` está bien).
- `T haversine_km(geo::Point const&, geo::Point const&)` → **está definida fuera del espacio de nombres** (causa 1).
- `T geo::haversine_km(geo::Point, geo::Point)` → **firma distinta** (causa 1).
- Ninguna línea → el `.cpp` no se compila dentro de `geo` (causa 2), o es `inline`/plantilla (causa 3).

El caso más habitual es el segundo, por escribir la definición así:

```cpp
// src/distance.cpp (incorrecto)
#include <geo/distance.hpp>
#include <cmath>

double haversine_km(const geo::Point& a, const geo::Point& b) {  // en el espacio global
    // ...
}
```

Corrección: definirla dentro del espacio de nombres, con la misma firma que la declaración:

```cpp
// src/distance.cpp
#include <geo/distance.hpp>

#include <cmath>
#include <numbers>

namespace geo {

double haversine_km(const Point& a, const Point& b) {
    constexpr double earth_radius_km = 6371.0;
    constexpr double to_rad = std::numbers::pi / 180.0;
    const double dlat = (b.lat - a.lat) * to_rad;
    const double dlon = (b.lon - a.lon) * to_rad;
    const double h = std::sin(dlat / 2) * std::sin(dlat / 2)
                   + std::cos(a.lat * to_rad) * std::cos(b.lat * to_rad)
                   * std::sin(dlon / 2) * std::sin(dlon / 2);
    return 2.0 * earth_radius_km * std::asin(std::sqrt(h));
}

}  // namespace geo
```

Para que este error no vuelva a llegar hasta el enlazador: con `-Wmissing-declarations` (GCC y Clang), el compilador avisa cuando defines una función con enlace externo que no tiene declaración previa visible. Una definición en el espacio global que «debería» ser la de `geo` dispara el aviso en `distance.cpp`, en compilación. Añádelo a los avisos `PRIVATE` del target.

Comprobación: `nm -C build/libgeo.a | grep haversine` debe mostrar `T geo::haversine_km(geo::Point const&, geo::Point const&)`, y `ctest --test-dir build --output-on-failure` debe pasar los dos tests (el de Madrid-Barcelona da unos 505 km).""",
            },
        ]
    },
    # 25) C++: informe de ThreadSanitizer por carrera de datos en un contador; atomic, acumulación local
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Esto debería imprimir 400000, pero cada vez sale un número distinto:

```cpp
#include <iostream>
#include <thread>
#include <vector>

int main() {
    long hits = 0;
    std::vector<std::thread> workers;
    for (int t = 0; t < 4; ++t) {
        workers.emplace_back([&hits] {
            for (int i = 0; i < 100000; ++i) {
                ++hits;
            }
        });
    }
    for (auto& w : workers) w.join();
    std::cout << hits << '\n';
}
```

Lo compilé con `-fsanitize=thread` y me sale esto:

```
==================
WARNING: ThreadSanitizer: data race (pid=90210)
  Read of size 8 at 0x7ffd3c9e5a28 by thread T2:
    #0 main::{lambda()#1}::operator()() const src/hits.cpp:11 (hits+0x1b2e)

  Previous write of size 8 at 0x7ffd3c9e5a28 by thread T1:
    #0 main::{lambda()#1}::operator()() const src/hits.cpp:11 (hits+0x1b45)

  Location is stack of main thread.

  Thread T2 (tid=90213, running) created by main thread at:
    #0 pthread_create <null> (libtsan.so.2+0x5e686)
    #2 main src/hits.cpp:9 (hits+0x1c03)

SUMMARY: ThreadSanitizer: data race src/hits.cpp:11 in main::{lambda()#1}::operator()() const
==================
```""",
            },
            {
                "role": "assistant",
                "content": r"""ThreadSanitizer te está dando el diagnóstico completo. Leído por partes:

- **`data race`**: dos hilos acceden a la misma posición de memoria sin sincronización y al menos uno escribe. En C++ eso es comportamiento indefinido, no solo «un resultado impreciso».
- **`Read of size 8 ... by thread T2`** y **`Previous write of size 8 ... by thread T1`**, ambos en **`hits.cpp:11`**: el `++hits`. Ocho bytes es el `long`.
- **`Location is stack of main thread`**: la variable es `hits`, local de `main`, compartida por referencia con las lambdas.
- **`created by main thread at ... hits.cpp:9`**: los hilos se crean en el `emplace_back`.

**Por qué se pierden incrementos:** `++hits` no es una operación, son tres: leer el valor, sumar uno, escribirlo. Si T1 y T2 leen 1000 a la vez, los dos escriben 1001, y se pierde una suma. Con cuatro hilos martilleando la misma variable, pasa miles de veces.

Puede que con `-O2` sin TSan veas 400000 a veces. Es probable que el compilador transforme el bucle en un único `hits += 100000` por hilo, reduciendo la ventana de la carrera a casi nada. Sigue siendo comportamiento indefinido; que el síntoma desaparezca con optimizaciones no lo arregla.

Tres arreglos, de más a menos recomendable para este caso:

**1. Acumular en local y combinar una vez** (sin contención):

```cpp
#include <atomic>
#include <iostream>
#include <thread>
#include <vector>

int main() {
    std::atomic<long> hits{0};
    {
        std::vector<std::jthread> workers;
        for (int t = 0; t < 4; ++t) {
            workers.emplace_back([&hits] {
                long local = 0;
                for (int i = 0; i < 100000; ++i) {
                    ++local;  // aquí iría el trabajo real que cuenta aciertos
                }
                hits.fetch_add(local, std::memory_order_relaxed);
            });
        }
    }  // cada jthread hace join al destruirse
    std::cout << hits.load() << '\n';
}
```

Cada hilo cuenta en su propia variable y publica el total una sola vez: cuatro operaciones atómicas en vez de 400 000.

**2. `std::atomic<long>` con `++hits` directamente.** Correcto, pero las cuatro CPU se pelean por la misma línea de caché en cada incremento; con contadores muy calientes puede ser varias veces más lento que la versión 1.

**3. `std::mutex`** alrededor del incremento. Correcto, pero aún más caro por operación. Tiene sentido cuando la sección crítica toca varias variables que deben cambiar juntas, no para un contador.

Sobre `memory_order_relaxed`: basta porque solo importa el valor final, y el `join` de los hilos ya sincroniza: todo lo que hicieron es visible para `main` después. Si otro hilo leyera `hits` para decidir algo sobre *otros* datos, haría falta un orden más fuerte.

Lo que **no** arregla nada: declarar `hits` como `volatile`. `volatile` evita que el compilador elimine accesos, pero no los hace atómicos ni establece orden entre hilos. No es una herramienta de concurrencia en C++.

Verificación:

```sh
g++ -std=c++20 -g -O1 -fsanitize=thread src/hits.cpp -o hits && ./hits
```

La versión corregida imprime `400000` sin ningún informe de TSan. Ejecútala varias veces (`for i in $(seq 20); do ./hits; done | sort -u` debe dar una única línea). Ten en cuenta que TSan no se puede combinar con ASan en el mismo binario: necesitas una compilación separada para cada uno.""",
            },
        ]
    },
    # 26) C++: ODR, inline en cabeceras, inline variables, violaciones silenciosas. Inglés
    {
        "messages": [
            {
                "role": "user",
                "content": "Is it OK to define functions in a header in C++? I put a small helper in `utils.h`, got 'multiple definition' linker errors, then someone told me to add `inline` and it worked. What does `inline` actually do there, and what is this ODR people mention?",
            },
            {
                "role": "assistant",
                "content": r"""Yes, it's fine, as long as you understand what `inline` means today: **"this definition may appear in several translation units; they are all the same, keep one"**. It has almost nothing to do with inlining as an optimization; the compiler decides that on its own.

## The ODR

The **One Definition Rule** says:

1. A non-inline function or variable must have **exactly one definition in the whole program**.
2. Classes, inline functions, inline variables, and templates may be defined in **several translation units**, but every definition must be **identical** (same tokens, same meaning).

A translation unit is a `.cpp` file after `#include`s are expanded. If `utils.h` defines a plain function and two `.cpp` files include it, the program has two definitions: rule 1 is broken and the linker reports `multiple definition of 'trim[abi:cxx11](std::basic_string_view<char, std::char_traits<char> >)'`. Marking it `inline` moves it to rule 2, which is exactly what a header needs.

```cpp
// utils.h
#pragma once

#include <string>
#include <string_view>

inline std::string trim(std::string_view s) {
    const auto first = s.find_first_not_of(" \t\n");
    if (first == std::string_view::npos) {
        return {};
    }
    const auto last = s.find_last_not_of(" \t\n");
    return std::string(s.substr(first, last - first + 1));
}

inline constexpr int kMaxRetries = 3;  // C++17 inline variable: one object program-wide
```

Things that are **implicitly inline**, so they never need the keyword in a header: member functions defined inside the class body, function templates, `constexpr` functions, and (since C++17) `static constexpr` data members.

## Why not `static` instead?

`static` (or an anonymous namespace) also silences the linker, but it means something else: **every translation unit gets its own private copy**. That bloats the binary and changes behavior silently when the function has state:

```cpp
// in a header
static int next_id() {
    static int counter = 0;
    return ++counter;
}
```

Each `.cpp` file has its own `counter`, so two files can hand out the same id. With `inline`, there is one function and one `counter` for the whole program. Use `static` or anonymous namespaces for helpers that live in a single `.cpp` file, not in headers.

## The dangerous part: ODR violations nobody reports

Rule 2 requires identical definitions, and the toolchain is **not required to check it**. The linker keeps one copy and discards the rest. If they differ, you get undefined behavior with no error:

```cpp
// a.cpp
struct Settings { int retries; };
// b.cpp
struct Settings { int retries; bool verbose; };  // same name, different layout
```

Code in `a.cpp` and `b.cpp` exchanging a `Settings` disagrees about its size. The same happens with an inline function in a header that changes with a macro (`#ifdef DEBUG` adding a member to a struct) when two libraries are compiled with different flags. Symptoms: crashes or corrupted values in code that "looks correct".

Defenses:

- Put every type that crosses files in **one header**, inside a **namespace**; give `.cpp`-local types an anonymous namespace.
- Never let macros change the layout of types in public headers.
- GCC with link-time optimization reports many of these: build with `-flto -Wodr`. AddressSanitizer also detects some ODR violations of global variables (`detect_odr_violation` is on by default).

## Verification

```sh
g++ -std=c++20 -c a.cpp b.cpp
nm -C a.o b.o | grep trim
```

Assuming both files call `trim` (an inline function nobody uses is not emitted at all), for the inline version `nm` shows the symbol as `W` (weak) in both object files: the linker is allowed to merge them. Remove `inline` and it becomes `T` (strong) in both, and linking `a.o b.o` reproduces the "multiple definition" error. That `W` versus `T` difference is the ODR, as seen by the linker.""",
            },
        ]
    },
    # 27) C vs C++: malloc/free frente a new/delete, delete vs delete[], mismatch con ASan (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de C. ¿Puedo seguir usando malloc y free en C++? ¿Y qué diferencia hay entre delete y delete[]?",
            },
            {
                "role": "assistant",
                "content": r"""Puedes, pero casi nunca debes. La diferencia clave es que **`malloc` solo reserva bytes; `new` reserva y además construye el objeto**. Igual con `free` (solo libera) frente a `delete` (destruye y libera).

En C eso da igual porque no hay constructores. En C++ importa en cuanto un tipo tiene miembros con constructor, como `std::string`:

```cpp
#include <cstdlib>
#include <string>

struct User {
    std::string name;
    int age;
};

int main() {
    // Mal: memoria sin construir; name no es un std::string válido
    User* u = static_cast<User*>(std::malloc(sizeof(User)));
    u->name = "Ana";  // comportamiento indefinido: asigna a un string que nunca se construyó
    std::free(u);     // y aunque funcionara, no llama al destructor: fuga del texto
}
```

Las parejas de reserva y liberación **no se pueden mezclar**:

| Reservas con | Liberas con |
|---|---|
| `malloc` / `calloc` / `realloc` | `free` |
| `new T` | `delete p` |
| `new T[n]` | `delete[] p` |

**`delete` frente a `delete[]`**: `new T[n]` construye `n` objetos y guarda en algún sitio cuántos son. `delete[] p` llama a los `n` destructores y libera el bloque. Si usas `delete p` sobre un array, se llama a un destructor (o a ninguno correctamente) y se libera con la función equivocada: comportamiento indefinido. Con tipos simples como `int` puede no notarse; con objetos, fugas o corrupción.

AddressSanitizer detecta todas estas mezclas. Este programa:

```cpp
int main() {
    int* values = new int[10];
    delete values;  // debería ser delete[]
}
```

compilado con `g++ -g -fsanitize=address` aborta con `ERROR: AddressSanitizer: alloc-dealloc-mismatch (operator new [] vs operator delete)` y la línea exacta. Lo mismo para `malloc` + `delete` (`malloc vs operator delete`).

**Lo idiomático en C++ moderno es no usar ni `new`/`delete` ni `malloc`/`free` en el código normal**, sino tipos que gestionan la memoria por ti:

| En vez de | Usa |
|---|---|
| `new T[n]` / `malloc(n * sizeof(T))` | `std::vector<T> v(n);` |
| `new T(...)` con un único dueño | `auto p = std::make_unique<T>(...);` |
| `char*` con `malloc` para texto | `std::string` |
| `realloc` para crecer | `v.push_back(...)` o `v.resize(...)` |

```cpp
#include <memory>
#include <string>
#include <vector>

struct User {
    std::string name;
    int age;
};

int main() {
    auto user = std::make_unique<User>(User{"Ana", 30});
    std::vector<int> values(10);
    values.push_back(42);
}   // todo se libera aquí, en orden, sin llamar a nada
```

Sin un solo `delete`, y sin posibilidad de olvidarlo ni de usar el equivocado.

Cuándo sí tiene sentido `malloc`/`free` en C++: al hablar con una API de C que te devuelve memoria que **ella** espera que liberes con `free`, o que libera ella misma algo que tú reservaste. En ese caso, respeta la pareja que pide la API y envuelve el puntero en un `std::unique_ptr` con un *deleter* que llame a `free`, para no olvidarlo.

Comprobación: compila los dos primeros ejemplos con `-fsanitize=address` y verás los errores; el último debe ejecutarse sin ningún informe, ni siquiera de fugas al salir.""",
            },
        ]
    },
    # 28) C++20: cola productor-consumidor con condition_variable_any, jthread y stop_token. System exacto
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito en C++20 una cola entre un hilo que lee mensajes y varios workers que los procesan. ¿Cómo la hago bien con condition_variable, y que se pueda parar limpiamente sin perder mensajes?",
            },
            {
                "role": "assistant",
                "content": r"""Una cola acotada protegida por un mutex, con dos variables de condición (hay hueco / hay elementos) y `std::stop_token` de C++20 para la parada. El tamaño máximo da *backpressure*: si los workers van lentos, el productor espera en vez de llenar la memoria.

```cpp
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>
#include <stop_token>
#include <utility>

template <typename T>
class BlockingQueue {
public:
    explicit BlockingQueue(std::size_t capacity) : capacity_(capacity) {}

    // false si se pidió parar antes de que hubiera hueco
    bool push(T item, std::stop_token stop) {
        std::unique_lock lock(mutex_);
        if (!not_full_.wait(lock, stop, [&] { return items_.size() < capacity_; })) {
            return false;
        }
        items_.push_back(std::move(item));
        lock.unlock();
        not_empty_.notify_one();
        return true;
    }

    // nullopt solo si se pidió parar y ya no quedan elementos
    std::optional<T> pop(std::stop_token stop) {
        std::unique_lock lock(mutex_);
        if (!not_empty_.wait(lock, stop, [&] { return !items_.empty(); })) {
            return std::nullopt;
        }
        T item = std::move(items_.front());
        items_.pop_front();
        lock.unlock();
        not_full_.notify_one();
        return item;
    }

private:
    std::mutex mutex_;
    std::condition_variable_any not_empty_;
    std::condition_variable_any not_full_;
    std::deque<T> items_;
    std::size_t capacity_;
};
```

Uso con un productor y cuatro workers:

```cpp
#include <atomic>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

int main() {
    BlockingQueue<std::string> queue(100);
    std::atomic<int> processed{0};

    std::vector<std::jthread> workers;
    for (int i = 0; i < 4; ++i) {
        workers.emplace_back([&](std::stop_token stop) {
            while (auto message = queue.pop(stop)) {
                processed.fetch_add(1, std::memory_order_relaxed);  // procesar *message
            }
        });
    }

    std::jthread producer([&](std::stop_token stop) {
        for (int i = 0; i < 1000; ++i) {
            if (!queue.push("msg-" + std::to_string(i), stop)) {
                break;
            }
        }
    });

    producer.join();
    for (auto& worker : workers) {
        worker.request_stop();
    }
    workers.clear();  // join de cada worker
    std::cout << processed.load() << '\n';
}
```

Las decisiones que hacen que esto funcione:

1. **Predicado en cada `wait`.** Las variables de condición pueden despertar sin que nadie notifique (*spurious wakeups*), y entre la notificación y la reactivación otro hilo puede haberse llevado el elemento. El predicado se reevalúa con el mutex tomado; sin él, `pop` podría hacer `front()` sobre una cola vacía.
2. **`condition_variable_any` en vez de `condition_variable`.** Solo la primera tiene la sobrecarga de `wait` con `stop_token` (C++20), que despierta al hilo cuando se pide parar. Con `condition_variable` necesitarías una bandera `stopped_` propia y un `notify_all` manual.
3. **Parada sin perder mensajes.** Esa sobrecarga de `wait` devuelve el resultado del predicado: si se pidió parar pero quedan elementos, devuelve `true` y el worker los sigue sacando. Solo con la cola vacía devuelve `false`. Por eso el orden es: terminar el productor, pedir la parada a los workers, y estos vacían la cola antes de salir.
4. **Notificar fuera del lock.** No cambia la corrección, pero evita que el hilo despertado choque inmediatamente con el mutex aún tomado.
5. **`std::jthread`** hace `request_stop()` y `join()` en su destructor. Si una excepción sale del ámbito donde viven los hilos y se captura más arriba, se paran y se unen solos, en vez de llamar a `std::terminate` como haría un `std::thread` destruido sin `join`. Y el orden de declaración importa: `queue` se declara antes que los hilos, así que se destruye después de que todos hayan terminado.

Comprobación:

```sh
g++ -std=c++20 -g -O1 -fsanitize=thread queue.cpp -o queue && ./queue
```

Debe imprimir `1000`, siempre, sin informes de ThreadSanitizer. Para probar la parada a mitad, llama a `producer.request_stop()` tras unos milisegundos: el productor sale del `push` que estuviera esperando, y los workers procesan lo que ya estaba en la cola y terminan. El número impreso será menor de 1000, pero igual al número de `push` que devolvieron `true`: ningún mensaje aceptado se pierde.""",
            },
        ]
    },
    # 29) C++: destructor virtual en clases base; multiturno sobre por qué shared_ptr "funciona" sin él
    {
        "messages": [
            {
                "role": "user",
                "content": r"""¿Por qué dicen que una clase base necesita destructor virtual? Mi código parece funcionar sin él:

```cpp
struct Shape {
    virtual double area() const = 0;
};

struct Polygon : Shape {
    std::vector<double> xs, ys;
    double area() const override { return 0.0; }
};

std::unique_ptr<Shape> s = std::make_unique<Polygon>();
```""",
            },
            {
                "role": "assistant",
                "content": r"""«Parece funcionar» es lo peor que puede hacer un comportamiento indefinido. Lo que pasa al destruir `s`:

1. `std::unique_ptr<Shape>` destruye con `delete` sobre un `Shape*`.
2. Como `~Shape()` **no es virtual**, la llamada se resuelve por el tipo estático: se ejecuta solo `~Shape()`. `~Polygon()` nunca se llama.
3. Por tanto, los destructores de `xs` y `ys` tampoco: si tenían elementos, su memoria se pierde.
4. Además, se libera un bloque de `sizeof(Polygon)` bytes diciéndole al asignador que mide `sizeof(Shape)`.

La norma lo declara comportamiento indefinido. En tu ejemplo los vectores están vacíos, así que no hay nada que perder y «funciona». Con datos, empiezan las fugas.

No hace falta creerlo: compila con `-fsanitize=address` y ASan lo informa al destruir `s`:

```
ERROR: AddressSanitizer: new-delete-type-mismatch on 0x... in thread T0:
  object passed to delete has wrong type:
  size of the allocated type:   56 bytes;
  size of the deallocated type: 8 bytes.
```

(Los tamaños dependen de la plataforma.) GCC y Clang también avisan en compilación con `-Wall` (`-Wdelete-non-virtual-dtor`): «deleting object of polymorphic class type 'Shape' which has non-virtual destructor might cause undefined behavior».

**El arreglo es una línea:**

```cpp
#include <memory>
#include <vector>

struct Shape {
    virtual ~Shape() = default;
    virtual double area() const = 0;
};

struct Polygon : Shape {
    std::vector<double> xs, ys;
    double area() const override { return 0.0; }
};
```

Con el destructor virtual, `delete` sobre un `Shape*` consulta la tabla virtual y llama primero a `~Polygon()` (que destruye `xs` e `ys`) y después a `~Shape()`.

**La regla**: si una clase tiene funciones virtuales y se va a destruir a través de un puntero a ella, necesita un destructor **público y virtual**. Si es una base que no debe destruirse polimórficamente (una clase de utilidades para herencia, por ejemplo), la alternativa es un destructor **protegido y no virtual**: entonces `delete` sobre un puntero a la base ni siquiera compila.

Un efecto colateral: declarar el destructor, aunque sea `= default`, hace que el compilador deje de generar el movimiento implícito de `Shape`. Para una interfaz abstracta como esta da igual; si la base tiene datos que se copian o mueven, declara también las operaciones de copia y movimiento como `= default`.

Comprobación: con el destructor virtual, este programa no produce ningún informe de ASan, ni siquiera de fugas:

```cpp
int main() {
    std::unique_ptr<Shape> s = std::make_unique<Polygon>();
    static_cast<Polygon&>(*s).xs.assign(1000, 1.0);
}
```

Sin `virtual`, el mismo programa produce el `new-delete-type-mismatch`, y si desactivas esa comprobación (`ASAN_OPTIONS=new_delete_type_mismatch=0`), LeakSanitizer informa de los 8000 bytes de `xs` perdidos.""",
            },
            {
                "role": "user",
                "content": "Curioso: probé `std::shared_ptr<Shape> p = std::make_shared<Polygon>();` sin el destructor virtual y ASan no se queja. ¿Por qué con shared_ptr sí funciona?",
            },
            {
                "role": "assistant",
                "content": r"""Porque `shared_ptr` **recuerda cómo destruir el objeto desde el momento en que se crea**, y `unique_ptr` no.

- `std::make_shared<Polygon>()` crea un bloque de control que sabe que el objeto es un `Polygon` y que debe destruirse como tal.
- Al convertir a `std::shared_ptr<Shape>`, el puntero visible cambia de tipo, pero **el bloque de control es el mismo**. Cuando el contador llega a cero, el bloque llama a `~Polygon()` directamente, sin pasar por la tabla virtual.

Es borrado de tipos (*type erasure*): el *deleter* viaja dentro del bloque de control, no en el tipo del puntero. En `std::unique_ptr<Shape>`, en cambio, el *deleter* forma parte del tipo (`std::default_delete<Shape>`), y lo único que sabe hacer es `delete` sobre un `Shape*`.

No te apoyes en esto, porque depende de **cómo** se creó el `shared_ptr`:

```cpp
std::shared_ptr<Shape> a = std::make_shared<Polygon>();            // destruye bien: Polygon
std::shared_ptr<Shape> b(new Polygon);                             // destruye bien: deduce Polygon
std::shared_ptr<Shape> c(static_cast<Shape*>(new Polygon));        // comportamiento indefinido: solo ve Shape*
std::unique_ptr<Shape> d = std::make_unique<Polygon>();
std::shared_ptr<Shape> e = std::move(d);                           // indefinido: hereda default_delete<Shape>
```

Los casos `c` y `e` son los peligrosos: el `shared_ptr` se construye a partir de algo que ya había perdido el tipo real, y vuelves al problema original. El caso `e` es especialmente traicionero, porque es un patrón normal: una fábrica que devuelve `unique_ptr<Shape>` y un llamador que lo convierte a `shared_ptr`.

Conclusión: el destructor virtual sigue siendo obligatorio. Que `make_shared` lo disimule solo hace que el error aparezca más tarde, en otro sitio del código.

Comprobación de los cinco casos, sin el destructor virtual y con `-fsanitize=address`: `a` y `b` no producen informe; `c` y `e` producen `new-delete-type-mismatch`. Con `virtual ~Shape() = default;`, ninguno produce informe.""",
            },
        ]
    },
    # 30) C/C++: interoperabilidad con extern "C" en ambos sentidos. Usuario en inglés pide la respuesta en español
    {
        "messages": [
            {
                "role": "user",
                "content": "How do I correctly call a C library from C++, and the other way around, expose a C++ library to C callers? Please answer in Spanish, it's for our onboarding docs.",
            },
            {
                "role": "assistant",
                "content": r"""La clave en los dos sentidos es la misma: **C y C++ nombran los símbolos de forma distinta**. C exporta `geo_distance_km` tal cual. C++ codifica en el nombre el espacio de nombres y los tipos de los parámetros (*name mangling*), porque permite sobrecargas: `geo_distance_km(geo_point, geo_point)` se convierte en algo como `_Z15geo_distance_km9geo_pointS_`. `extern "C"` le dice al compilador de C++ que use el nombre de C.

## De C++ a una librería C

La cabecera de la librería C debe declarar sus funciones dentro de `extern "C"` cuando la incluye un compilador de C++. El patrón estándar, que vale para los dos lenguajes:

```c
/* geo.h */
#ifndef GEO_H
#define GEO_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct geo_point {
    double lat;
    double lon;
} geo_point;

double geo_distance_km(geo_point a, geo_point b);
int geo_parse_point(const char *text, geo_point *out);

#ifdef __cplusplus
}
#endif

#endif /* GEO_H */
```

`__cplusplus` solo está definida al compilar como C++, así que un compilador de C ve una cabecera C normal.

Si la cabecera es de un tercero y no trae ese bloque, envuelve tú el `#include`:

```cpp
extern "C" {
#include "legacy_geo.h"
}
```

Sin esto, el error típico es: `undefined reference to 'geo_distance_km(geo_point, geo_point)'`. **Que el mensaje muestre los tipos de los parámetros es la pista**: el enlazador está buscando el nombre decorado de C++, y la librería C solo tiene el nombre plano.

## De una librería C++ hacia C

C no entiende clases, plantillas, referencias, excepciones ni `std::string`. La interfaz se construye con cuatro reglas:

1. **Tipo opaco**: C solo ve un puntero a una estructura declarada pero no definida.
2. **Funciones `extern "C"`** con tipos de C en la firma.
3. **Ninguna excepción cruza la frontera**: se capturan todas y se traducen a códigos de error. Una excepción que llega a código C es comportamiento indefinido (en la práctica, `std::terminate`).
4. **Quien reserva, libera**: la librería da `create` y `destroy`; el código C nunca hace `free` sobre lo que recibió.

```c
/* tokenizer_c.h — la interfaz que ve C */
#ifndef TOKENIZER_C_H
#define TOKENIZER_C_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tokenizer tokenizer;

tokenizer *tokenizer_create(const char *vocabulary_path);   /* NULL si falla */
int tokenizer_count(const tokenizer *t, const char *text, size_t *out_count); /* 0 = ok */
void tokenizer_destroy(tokenizer *t);                        /* acepta NULL */

#ifdef __cplusplus
}
#endif

#endif /* TOKENIZER_C_H */
```

```cpp
// tokenizer_c.cpp — compilado como C++
#include "tokenizer_c.h"
#include "tokenizer.hpp"  // la clase C++ real: Tokenizer

struct tokenizer {
    Tokenizer impl;
};

extern "C" tokenizer* tokenizer_create(const char* vocabulary_path) {
    if (vocabulary_path == nullptr) {
        return nullptr;
    }
    try {
        return new tokenizer{Tokenizer(vocabulary_path)};
    } catch (...) {
        return nullptr;
    }
}

extern "C" int tokenizer_count(const tokenizer* t, const char* text, size_t* out_count) {
    if (t == nullptr || text == nullptr || out_count == nullptr) {
        return -1;
    }
    try {
        *out_count = t->impl.count(text);
        return 0;
    } catch (...) {
        return -2;
    }
}

extern "C" void tokenizer_destroy(tokenizer* t) {
    delete t;
}
```

Asumo que `Tokenizer` tiene un constructor que acepta la ruta y un método `count(std::string_view) const` que devuelve el número de tokens. `delete` sobre `nullptr` no hace nada, así que `tokenizer_destroy(NULL)` es seguro.

## Enlazado

- **C++ que usa la librería C**: `g++ main.cpp -L. -lgeo`.
- **C que usa la librería C++**: el ejecutable necesita la biblioteca estándar de C++. Enlaza con `g++` en vez de `gcc`, o añade `-lstdc++` al final.

## Comprobación

`nm` muestra qué nombres hay realmente en cada objeto:

```sh
nm libgeo.a | grep geo_distance        # T geo_distance_km        (nombre de C)
nm main.o | grep geo_distance          # U geo_distance_km        (con extern "C": coincide)
                                       # U _Z15geo_distance_km9geo_pointS_  (sin extern "C": no coincide)
nm tokenizer_c.o | grep tokenizer_     # T tokenizer_count, T tokenizer_create, ...
```

Si el símbolo que el objeto necesita (`U`) y el que la librería define (`T`) se escriben igual, el enlace funciona. Si uno aparece decorado y el otro no, falta un `extern "C"`. Y un último test que conviene tener en el CI: un pequeño programa **escrito en C** y compilado con `gcc` que incluya `tokenizer_c.h` y llame a las tres funciones; es la única forma de comprobar que la cabecera es C válido.""",
            },
        ]
    },
]
