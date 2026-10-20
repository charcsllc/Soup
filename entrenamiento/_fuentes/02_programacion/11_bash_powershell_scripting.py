"""Bash (~70 %) y PowerShell 7 (~30 %): scripting de sistemas, portabilidad y herramientas."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) quoting y expansión (principiante)
    {
        "messages": [
            {"role": "user", "content": "Mi script bash falla cuando los archivos tienen espacios en el nombre. Hago `for f in $(ls *.txt); do cp $f backup/; done`. ¿Qué está mal?"},
            {
                "role": "assistant",
                "content": r"""Dos errores que se combinan: `$(ls ...)` convierte la lista de archivos en texto, y luego bash **parte ese texto por espacios** (*word splitting*). Un archivo `informe final.txt` se convierte en dos palabras, `informe` y `final.txt`, y `cp` recibe rutas que no existen. Además, `$f` sin comillas vuelve a partirse y a expandir comodines.

La forma correcta no usa `ls` en absoluto: el *glob* del shell ya produce una lista donde cada archivo es un elemento, con espacios o sin ellos.

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p backup
for f in *.txt; do
    [[ -e "$f" ]] || continue      # si no hay ningún .txt, el glob queda literal; esto lo salta
    cp -- "$f" backup/
done
```

Las reglas que evitan el 90 % de estos bugs:

1. **Cita toda expansión de variable: `"$f"`, `"$dir/$f"`, `"${arr[@]}"`.** Sin comillas, el valor se parte por `$IFS` (espacio, tabulador, salto de línea) y los `*`, `?` y `[` que contenga se expanden como comodines. Con comillas, el valor es una sola palabra, tal cual.
2. **No parsees la salida de `ls`.** Los nombres pueden tener espacios, saltos de línea y caracteres raros; `ls` además cambia el formato según la terminal. Para listar, usa globs; para recorrer recursivamente, `find`.
3. **`--` antes de los argumentos** cuando un nombre pueda empezar por `-`: `cp -- "$f" backup/` evita que `-n.txt` se interprete como opción.

Lo que las comillas no hacen: `"$@"` es el caso especial donde las comillas **conservan** la separación por argumentos, uno por elemento; es la forma correcta de reenviar argumentos a otro comando. `"$*"` los junta en uno solo. Lo mismo con arrays: `"${files[@]}"` da un elemento por archivo.

Comprobación rápida de qué recibe un comando, antes y después:

```bash
touch 'informe final.txt' 'a b c.txt'
printf '[%s]\n' $(ls *.txt)     # [informe] [final.txt] [a] [b] [c.txt]
printf '[%s]\n' *.txt           # [a b c.txt] [informe final.txt]
```

`printf '[%s]\n'` imprime cada argumento entre corchetes; es la herramienta para ver exactamente cómo ha quedado partido algo. Y `shellcheck script.sh` te marca cada expansión sin comillas (código SC2086) antes de que el script llegue a un directorio con espacios.""",
            },
        ]
    },
    # 2) set -euo pipefail y sus trampas (el usuario trae un script)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Añadí `set -euo pipefail` a un script que funcionaba y ahora se muere en sitios raros, sin mensaje. Trozo:

```bash
#!/bin/bash
set -euo pipefail

count=0
errors=$(grep -c ERROR app.log)
for f in logs/*.gz; do
    ((count++))
    zcat "$f" | grep WARN | head -5
done
echo "procesados $count, errores $errors"
```

A veces muere en el `grep -c`, a veces en el bucle, y nunca llega al `echo`. ¿Me quito el `set -e`?""",
            },
            {
                "role": "assistant",
                "content": r"""No te lo quites: `set -e` está haciendo lo que promete, abortar ante cualquier comando que devuelva distinto de cero, y tu script tiene tres comandos que devuelven «fallo» sin que sea un error. Hay que arreglar los tres, no la red de seguridad.

**1. `grep -c ERROR app.log` devuelve 1 cuando no hay coincidencias.** Para `grep`, «no encontré nada» es código de salida 1 (y 2 para errores reales). Con `set -e`, la asignación `errors=$(...)` hereda ese código y el script muere ahí cuando el log no tiene errores. Solución: decide explícitamente que 0 coincidencias es válido.

```bash
errors=$(grep -c ERROR app.log || true)
```

Mejor aún, distingue «nada» de «error real» (archivo inexistente): `grep -c ERROR app.log || [[ $? -eq 1 ]]`; el `|| [[ $? -eq 1 ]]` convierte solo el 1 en éxito y deja pasar el 2.

**2. `((count++))` devuelve 1 la primera vez.** La expresión aritmética devuelve el valor **antes** del incremento (post-incremento): con `count=0`, `((count++))` evalúa a 0, y en bash un resultado aritmético 0 significa «falso», código 1. `set -e` lo mata en la primera iteración. Usa el pre-incremento o la asignación:

```bash
((++count))        # evalúa a 1: éxito
count=$((count + 1))   # siempre éxito
```

**3. `zcat | grep | head -5` con `pipefail`.** `head` cierra su entrada tras 5 líneas; `grep` recibe `SIGPIPE` al escribir en una tubería cerrada y termina con 141. Sin `pipefail` solo contaba `head` (éxito); con `pipefail` cuenta cualquier fallo de la tubería, y 141 lo es. Y cuando un archivo no tiene `WARN`, `grep` devuelve 1 aunque no haya `SIGPIPE`. Dos opciones:

```bash
zcat "$f" | { grep WARN || true; } | head -5
```

o, si de verdad solo quieres cinco líneas, evita que `head` corte a `grep`: `grep -m 5 WARN` para que sea `grep` quien pare.

Script corregido:

```bash
#!/usr/bin/env bash
set -euo pipefail

count=0
errors=$(grep -c ERROR app.log || [[ $? -eq 1 ]])
for f in logs/*.gz; do
    [[ -e "$f" ]] || continue
    count=$((count + 1))
    zcat "$f" | { grep -m 5 WARN || true; }
done
echo "procesados $count, errores $errors"
```

Para que los fallos **no sean silenciosos**, que era tu otra queja, añade un `trap` que diga dónde murió:

```bash
trap 'echo "error en la línea $LINENO: $BASH_COMMAND" >&2' ERR
```

Las otras trampas de `set -e` que te esperan, para reconocerlas: no actúa dentro de `if cmd`, `cmd && otra`, `cmd || otra` ni `! cmd` (ahí el fallo es parte de la condición); no ve el código de un comando dentro de `local x=$(cmd)` o `export x=$(cmd)` porque el que cuenta es el de `local`/`export` (sepáralos: `local x; x=$(cmd)`); y no se propaga a subshells en versiones antiguas. `set -u`, por su parte, falla con arrays vacíos en bash < 4.4 (`"${arr[@]}"` con `arr=()`), así que usa `"${arr[@]+"${arr[@]}"}"` o actualiza bash.

Verifica con un `app.log` sin la palabra `ERROR` y un `.gz` sin `WARN`: el script debe llegar al `echo` con `errores 0`.""",
            },
        ]
    },
    # 3) arrays en bash (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Necesito manejar listas en bash: construir una lista de servidores, añadir elementos, recorrerla, saber cuántos hay y pasársela entera a un comando. ¿Cuál es la forma correcta? He visto cosas con IFS y cadenas separadas por espacios y no me fío."},
            {
                "role": "assistant",
                "content": r"""Usa arrays de bash. Las cadenas separadas por espacios se rompen en cuanto un elemento lleva un espacio; los arrays no.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Declarar y añadir
servers=("web-01" "web-02")
servers+=("db-01")                 # añade un elemento
servers+=("cache-01" "cache-02")   # añade varios

# Tamaño y acceso
echo "${#servers[@]}"              # 5
echo "${servers[0]}"               # web-01
echo "${servers[-1]}"              # cache-02 (bash 4.3+)

# Recorrer: comillas y [@], siempre
for host in "${servers[@]}"; do
    echo "ping $host"
done

# Pasar la lista entera a un comando: un argumento por elemento
ssh-keyscan "${servers[@]}" >> ~/.ssh/known_hosts

# Rebanadas: desde el índice 1, dos elementos
echo "${servers[@]:1:2}"           # web-02 db-01

# Unir con un separador (coma) para un argumento de texto
IFS=, joined="${servers[*]}"; echo "$joined"   # web-01,web-02,db-01,cache-01,cache-02
```

Las tres reglas:

1. **`"${arr[@]}"` con comillas** expande a un argumento por elemento, respetando espacios dentro de cada uno. `${arr[@]}` sin comillas vuelve a partir por espacios; `"${arr[*]}"` junta todo en un único argumento con el primer carácter de `IFS` como separador (útil solo para construir texto, como en el ejemplo de la coma).
2. **`${#arr[@]}`** es el número de elementos; `${#arr}` sería la longitud del primer elemento, error clásico.
3. Los arrays **no se exportan** a procesos hijos ni se pueden devolver desde una función con `return`. Para pasarlos a una función, pasa los elementos (`f "${servers[@]}"` y dentro `local -a hosts=("$@")`) o usa una referencia por nombre (`local -n ref=$1`, bash 4.3+).

Construir un array a partir de la salida de un comando, sin que se parta mal:

```bash
mapfile -t files < <(find . -name '*.log' -newer marker)   # una línea = un elemento
mapfile -t lines < hosts.txt                               # cada línea del archivo
```

`-t` quita el salto de línea de cada elemento. Para nombres de archivo que puedan contener saltos de línea, `-d ''` con `find -print0`.

Arrays asociativos (diccionarios), bash 4+:

```bash
declare -A port=([web]=80 [db]=5432 [cache]=6379)
port[api]=8080
echo "${port[db]}"               # 5432
for name in "${!port[@]}"; do    # ! da las claves
    echo "$name -> ${port[$name]}"
done
[[ -v port[api] ]] && echo "api definido"
```

Dos límites a tener en cuenta: en macOS el bash del sistema es 3.2 (sin `declare -A`, sin `mapfile`, sin `${arr[-1]}`); instala uno moderno con Homebrew o usa `#!/usr/bin/env bash` y documenta la versión. Y con `set -u`, un array vacío expandido con `"${arr[@]}"` falla en bash anterior a 4.4; si tienes que soportar esas versiones, `"${arr[@]+"${arr[@]}"}"`.

Comprobación: `servers+=("host con espacio")` y luego `printf '[%s]\n' "${servers[@]}"` debe imprimir ese elemento en una sola línea entre corchetes.""",
            },
        ]
    },
    # 4) funciones: local, return vs stdout, nameref (principiante)
    {
        "messages": [
            {"role": "user", "content": "¿Cómo devuelvo un valor desde una función en bash? Probé `return \"resultado\"` y me da `numeric argument required`."},
            {
                "role": "assistant",
                "content": r"""`return` en bash solo devuelve un **código de salida** (0-255), igual que `exit`: sirve para decir «fui bien» o «fallé», no para devolver datos. Para devolver un valor hay dos mecanismos, y conviene usar cada uno para lo suyo.

**1. Imprimir en stdout y capturar con `$(...)`.** Es el idioma habitual: la función escribe el resultado y el llamador lo recoge.

```bash
get_latest_tag() {
    git describe --tags --abbrev=0 2>/dev/null
}

tag=$(get_latest_tag) || { echo "no hay tags" >&2; exit 1; }
echo "última versión: $tag"
```

Reglas: todo lo que la función imprima **forma parte del valor** (cuidado con `echo` de depuración; mándalos a `>&2`), y `$(...)` ejecuta la función en un subshell, así que cualquier variable que modifique dentro se pierde.

**2. Código de salida para éxito/fallo.** `return 0` es éxito, cualquier otro es fallo; se usa con `if`, `&&`, `||`:

```bash
is_root() {
    [[ $EUID -eq 0 ]]
}

if is_root; then echo "root"; else echo "usuario normal"; fi
```

Si la última línea de la función es un comando o un test, su código es el que devuelve la función; el `return` explícito es opcional.

Combinando los dos, que es lo normal: datos por stdout, estado por código:

```bash
read_config_value() {
    local key=$1 file=${2:-config.ini}
    local value
    value=$(grep -E "^${key}=" "$file" | cut -d= -f2-) || return 1
    [[ -n $value ]] || return 1
    printf '%s\n' "$value"
}

if port=$(read_config_value port); then
    echo "puerto: $port"
else
    echo "sin puerto configurado" >&2
fi
```

Tres detalles del ejemplo:

- **`local`** para cada variable de la función; sin él, son globales y pisan las del llamador.
- `local value` y la asignación **en líneas separadas**: `local value=$(cmd)` siempre devuelve 0 (el código de `local`), y el `|| return 1` no vería el fallo de `grep`.
- `printf '%s\n'` en vez de `echo` para imprimir el valor: `echo` interpreta `-n` o `-e` si el valor empieza así.

**3. Para devolver varios valores o un array,** stdout se queda corto. Pasa el nombre de una variable y escribe en ella con una referencia (`local -n`, bash 4.3+):

```bash
split_host_port() {
    local -n out_host=$1 out_port=$2
    local input=$3
    out_host=${input%:*}
    out_port=${input##*:}
}

split_host_port h p "db.internal:5432"
echo "$h en $p"      # db.internal en 5432
```

Sin subshell, sin parsear salida, y funciona con arrays (`local -n arr=$1; arr=(a b c)`). El único cuidado: el nombre que pasas no puede coincidir con el nombre local de la referencia.

Resumen: un valor de texto → stdout; éxito/fallo → `return`; varios valores o arrays → `local -n`.""",
            },
        ]
    },
    # 5) [[ ]] vs [ ] (system variante rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo, sin perder precisión técnica."},
            {"role": "user", "content": "¿Qué diferencia hay entre `[ ]` y `[[ ]]` en bash? Tengo un `if [ $name = \"admin\" ]` que explota con `unary operator expected` cuando name está vacío."},
                {
                "role": "assistant",
                "content": r"""`[` es un **comando** (existe `/usr/bin/[`, equivalente a `test`), así que sus argumentos pasan por la expansión normal del shell antes de que lo vea. `[[` es una **palabra reservada** de bash: el shell la interpreta con reglas propias, sin partir palabras ni expandir comodines dentro.

Tu error viene de ahí. Con `name` vacío, `[ $name = "admin" ]` se convierte, después de la expansión, en `[ = admin ]`: tres argumentos donde `=` queda en la posición de un operador unario, y `test` se queja. Con comillas, `[ "$name" = "admin" ]` pasa `""` como primer argumento y funciona. Con `[[ $name == "admin" ]]` funciona incluso sin comillas, porque `[[` sabe que `$name` es un único operando aunque esté vacío.

Lo que `[[ ]]` te da y `[ ]` no:

```bash
# Comparación de patrones (glob) sin comillas en el lado derecho
[[ $file == *.log ]]

# Expresiones regulares, con captura en BASH_REMATCH
if [[ $version =~ ^([0-9]+)\.([0-9]+)$ ]]; then
    echo "mayor=${BASH_REMATCH[1]} menor=${BASH_REMATCH[2]}"
fi

# && y || adentro, con paréntesis para agrupar
[[ -f $cfg && ( $mode == dev || $mode == test ) ]]

# Comparación lexicográfica sin escapar
[[ $a < $b ]]
```

Con `[ ]` el `<` es una redirección (tenés que escribirlo `\<`), `&&` termina el comando y no hay regex.

Lo que sigue igual en los dos:

- Números con `-eq`, `-ne`, `-lt`, `-le`, `-gt`, `-ge`. `==` compara **texto**: `[[ 10 == 10.0 ]]` es falso, `[[ 10 -eq 10.0 ]]` da error. Para aritmética cómoda tenés `(( ))`: `(( count > 10 ))`.
- Archivos con `-f`, `-d`, `-e`, `-r`, `-x`, `-s` (tamaño > 0), `-nt` (más nuevo que).
- Cadenas con `-z` (vacía) y `-n` (no vacía).

Cuándo usar `[ ]` igual: cuando el script debe correr con `#!/bin/sh` (dash, busybox, el sh de Alpine), donde `[[` no existe. Ahí la regla es citar siempre: `[ "$name" = "admin" ]`, y para combinar condiciones, `[ ... ] && [ ... ]` en vez del `-a` interno, que es ambiguo.

Tu `if` corregido:

```bash
if [[ $name == "admin" ]]; then
```

Y aunque `[[` no las necesite, muchos equipos siguen citando `"$name"` adentro por costumbre y para que el código se vea igual que fuera del test; es una convención válida. Lo que no es válido es citar el patrón del lado derecho cuando querés glob o regex: `[[ $file == "*.log" ]]` compara con el texto literal `*.log`.

Comprobá la diferencia en una línea:

```bash
name=; [ $name = admin ]; echo $?      # bash: [: =: unary operator expected  → 2
name=; [[ $name == admin ]]; echo $?   # 1 (falso, sin error)
```""",
            },
        ]
    },
    # 6) pipes y redirecciones (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Por qué `cmd 2>&1 > salida.log` me sigue mostrando los errores en pantalla? Quiero todo en el archivo."},
            {
                "role": "assistant",
                "content": r"""Porque las redirecciones se aplican **de izquierda a derecha**, y cada una copia el destino que el otro descriptor tiene **en ese momento**.

Tu orden, paso a paso, empezando con stdout (1) y stderr (2) apuntando a la terminal:

1. `2>&1`: stderr pasa a apuntar a donde apunta stdout ahora → la terminal.
2. `> salida.log`: stdout pasa a apuntar al archivo. stderr no se entera; sigue en la terminal.

El orden correcto es el contrario:

```bash
cmd > salida.log 2>&1
```

1. `> salida.log`: stdout → archivo.
2. `2>&1`: stderr → donde está stdout ahora → el archivo.

Bash tiene un atajo para exactamente esto: `cmd &> salida.log` (y `&>>` para añadir). Es específico de bash; en `sh` usa la forma larga.

Un mapa de las redirecciones que se usan de verdad:

| Sintaxis | Efecto |
|---|---|
| `> f` / `>> f` | stdout a `f`, truncando / añadiendo |
| `2> f` | stderr a `f` |
| `2>&1` | stderr al destino actual de stdout |
| `&> f` | ambos a `f` (bash) |
| `2> /dev/null` | descartar errores |
| `> /dev/null 2>&1` | descartar todo (portable) |
| `< f` | stdin desde `f` |
| `<<< "texto"` | stdin desde una cadena (bash) |
| `<< 'EOF'` | *here-doc*; con comillas en el delimitador no expande `$var` |

Y en tuberías: `cmd1 | cmd2` solo pasa stdout de `cmd1`; para pasar también stderr, `cmd1 2>&1 | cmd2` o el atajo `cmd1 |& cmd2`. Los errores de `cmd1` que no rediriges van directos a la terminal, lo que suele ser lo que quieres: ver los fallos mientras los datos siguen por la tubería.

Una trampa más: `>` **trunca el archivo antes** de ejecutar el comando. `sort datos.txt > datos.txt` vacía el archivo y `sort` lee uno vacío. Escribe a un temporal y renombra, o usa `sort -o datos.txt datos.txt`, que está diseñado para eso.

Verificación de tu caso con un comando que escribe en los dos sitios:

```bash
{ echo salida; echo error >&2; } > todo.log 2>&1
cat todo.log       # las dos líneas
```""",
            },
            {"role": "user", "content": "Vale. Y ahora quiero ver la salida en pantalla Y guardarla en el archivo, pero que si el comando falla el script lo sepa. Con `cmd | tee log` siempre me da éxito."},
            {
                "role": "assistant",
                "content": r"""`cmd | tee log` devuelve el código de `tee` (el último de la tubería), y `tee` casi siempre tiene éxito. Tienes dos maneras de recuperar el código de `cmd`.

**1. `set -o pipefail`.** La tubería devuelve el código del **último comando que falló** (o 0 si ninguno). Es lo que querías en una línea:

```bash
set -o pipefail
if cmd 2>&1 | tee build.log; then
    echo "ok"
else
    echo "falló cmd" >&2
fi
```

`2>&1` antes del `|` para que los errores también pasen por `tee` y acaben en el log.

**2. `PIPESTATUS`**, cuando necesitas el código de cada etapa por separado:

```bash
cmd 2>&1 | tee build.log
status=${PIPESTATUS[0]}      # código de cmd; [1] sería el de tee
```

`PIPESTATUS` se sobrescribe con el siguiente comando, así que cópialo en la línea inmediatamente posterior.

Si además quieres mantener separados stdout y stderr en pantalla pero juntos en el archivo, **sustitución de procesos** (`>(...)`), que te deja «redirigir a un comando» como si fuera un archivo:

```bash
cmd > >(tee -a build.log) 2> >(tee -a build.log >&2)
```

Aquí stdout va a un `tee` que lo muestra por stdout y stderr a otro `tee` que lo devuelve por stderr; los dos añaden al mismo log. El inconveniente es que las dos escrituras al log pueden intercalarse de forma desordenada si el comando escribe mucho en ambos; si el orden importa, usa la versión con `2>&1`.

La sustitución de procesos tiene un segundo uso muy frecuente, en sentido contrario (`<(...)`): darle a un comando que espera **archivos** la salida de otros comandos, sin temporales:

```bash
diff <(sort a.txt) <(sort b.txt)
comm -12 <(cut -d, -f1 hoy.csv | sort) <(cut -d, -f1 ayer.csv | sort)
```

Comprobación de que el código ya se propaga:

```bash
set -o pipefail
false | tee /dev/null; echo $?    # 1
true  | tee /dev/null; echo $?    # 0
```

Y `(exit 3) | tee /dev/null; echo "${PIPESTATUS[0]}"` imprime `3`.""",
            },
        ]
    },
    # 7) variable perdida en subshell: cat | while (bug del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Este bucle cuenta líneas largas y al final `count` vale 0, aunque dentro del bucle el echo muestra que sube:

```bash
count=0
cat access.log | while read -r line; do
    if [[ ${#line} -gt 200 ]]; then
        count=$((count + 1))
        echo "dentro: $count"
    fi
done
echo "fuera: $count"
```

Salida: `dentro: 1`, `dentro: 2`, `dentro: 3`, `fuera: 0`. ¿Bash pierde la variable?""",
            },
            {
                "role": "assistant",
                "content": r"""No la pierde: la incrementa en **otro proceso**. En bash, cada lado de una tubería se ejecuta en un **subshell** (una copia del shell). Tu `while` corre en el subshell de la derecha del `|`, el `count` que incrementa es la copia de ese subshell, y cuando la tubería termina el subshell muere con su copia. El `echo "fuera"` lee el `count` del shell padre, que nunca cambió.

La solución es que el bucle corra en el shell actual: alimenta el `while` con una **redirección** en vez de con `cat |`.

```bash
count=0
while IFS= read -r line; do
    if (( ${#line} > 200 )); then
        count=$((count + 1))
    fi
done < access.log
echo "fuera: $count"
```

Ahora el `while` es parte del shell principal y la variable persiste. De paso, `cat archivo | cmd` siempre se puede sustituir por `cmd < archivo` (ahorras un proceso), y `IFS=` evita que `read` recorte espacios al principio y al final de cada línea.

Cuando el productor **no** es un archivo sino un comando, la sustitución de procesos hace lo mismo:

```bash
while IFS= read -r line; do
    count=$((count + 1))
done < <(zcat access.log.gz | grep -v HEALTHCHECK)
```

El `<(...)` crea una tubería con nombre; el bucle sigue en el shell actual.

Tercera opción, si quieres conservar la sintaxis con `|`: `shopt -s lastpipe` hace que el **último** comando de una tubería corra en el shell actual (solo cuando el control de trabajos está desactivado, que es el caso en scripts, no en una terminal interactiva):

```bash
shopt -s lastpipe
cat access.log | while read -r line; do count=$((count + 1)); done
```

Funciona, pero es menos conocido y falla silenciosamente en una sesión interactiva; prefiero la redirección.

Lo mismo pasa con cualquier otra cosa que se ejecute en subshell: `$(...)`, `( ... )`, y cada comando de una tubería. Si alguna vez ves «asigno dentro y fuera no está», busca uno de esos tres.

Para este caso concreto, además, `awk` lo hace en una línea sin bucle en bash y mucho más rápido en archivos grandes:

```bash
awk 'length > 200 { n++ } END { print n + 0 }' access.log
```

Comprobación: con tres líneas de más de 200 caracteres, las dos versiones deben imprimir 3.""",
            },
        ]
    },
    # 8) trap y limpieza (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Mi script crea un directorio temporal con mktemp y a veces se queda ahí porque el script falla a mitad. ¿Cómo garantizo que se borre siempre?"},
            {
                "role": "assistant",
                "content": r"""Con `trap` sobre la señal `EXIT`: el comando registrado se ejecuta cuando el shell termina, sea por el final del script, por `exit`, o por `set -e` al fallar un comando.

```bash
#!/usr/bin/env bash
set -euo pipefail

tmpdir=$(mktemp -d)
trap 'rm -rf -- "$tmpdir"' EXIT

# trabajo
curl -fsSL "$url" -o "$tmpdir/paquete.tar.gz"
tar -xzf "$tmpdir/paquete.tar.gz" -C "$tmpdir"
cp "$tmpdir/bin/tool" /usr/local/bin/
```

Detalles que importan:

- **Comillas simples en el `trap`.** El texto se guarda tal cual y se expande **al ejecutarse**; `"$tmpdir"` dentro de comillas dobles se expandiría al registrar el trap, lo que aquí daría igual, pero en general quieres el valor del momento de la salida.
- **Registra el trap inmediatamente después de crear el recurso**, no al final del script. Si el fallo ocurre entre el `mktemp` y el `trap`, el directorio se queda; la ventana debe ser de una línea.
- **`rm -rf -- "$tmpdir"`**: el `--` protege si por algún motivo el nombre empezara por `-`, y las comillas, si lleva espacios (`TMPDIR` puede ser cualquier cosa).
- `mktemp -d` crea el directorio con permisos 700 en `$TMPDIR` o `/tmp`; no construyas el nombre a mano (`/tmp/miscript.$$` es predecible y atacable).

Si tienes varios recursos, acumula en una función en vez de encadenar traps (cada `trap ... EXIT` **sustituye** al anterior):

```bash
cleanup_tasks=()
cleanup() {
    local task
    for task in "${cleanup_tasks[@]}"; do
        eval "$task"
    done
}
trap cleanup EXIT

tmpdir=$(mktemp -d); cleanup_tasks+=("rm -rf -- '$tmpdir'")
mount "$img" "$mnt"; cleanup_tasks+=("umount '$mnt'")
```

Recórrelas en orden inverso si el orden de liberación importa (desmontar antes de borrar).

El código de salida se conserva: dentro del trap, `$?` es el código con el que el script estaba saliendo, y el trap no lo cambia a menos que llame a `exit` con otro valor. Si necesitas inspeccionarlo, cópialo en la primera línea de la función de limpieza (`local status=$?`).

Comprobación: añade `false` después del `mktemp` y ejecuta; el script debe fallar y `ls /tmp/tmp.*` no debe mostrar el directorio.""",
            },
            {"role": "user", "content": "¿Y si lo interrumpo con Ctrl+C? Me da la impresión de que entonces no limpia, y además quiero que un fallo me diga en qué línea ocurrió."},
            {
                "role": "assistant",
                "content": r"""Ctrl+C envía `SIGINT`. Bash ejecuta el trap de `EXIT` también al morir por una señal, así que la limpieza sí corre; lo que probablemente viste es otra cosa: si el Ctrl+C llega mientras corre un **comando hijo** (un `curl`, un `sleep`), es ese hijo el que recibe la señal, muere, y bash continúa con la siguiente línea como si el comando hubiera fallado normalmente. Con `set -e` el script termina y limpia; sin `set -e`, sigue ejecutando el resto del script con el trabajo a medias, que es lo que parece «no limpia».

Para tratar la interrupción de forma explícita y terminar con el código convencional (128 + número de señal, 130 para `SIGINT`):

```bash
#!/usr/bin/env bash
set -euo pipefail

tmpdir=$(mktemp -d)

cleanup() {
    local status=$?
    rm -rf -- "$tmpdir"
    exit "$status"
}
trap cleanup EXIT

on_interrupt() {
    echo "interrumpido" >&2
    exit 130            # dispara el trap de EXIT con 130
}
trap on_interrupt INT TERM

on_error() {
    echo "error en la línea $1: '$2' devolvió $3" >&2
}
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
```

Las piezas:

- **`INT` y `TERM` separados de `EXIT`.** `TERM` es lo que envía `kill` sin argumentos y lo que usa systemd o Docker para parar; conviene tratarlo igual que Ctrl+C. El trap llama a `exit`, y ese `exit` dispara `EXIT`, así que la limpieza está en un solo sitio.
- **`ERR` con `$LINENO` y `$BASH_COMMAND`.** Se ejecuta justo antes de que `set -e` aborte, con la línea y el comando que falló. Para que también salte dentro de funciones y subshells, añade `set -E` (`errtrace`); sin él, el trap `ERR` no se hereda.
- **`local status=$?` como primera línea de `cleanup`.** Cualquier comando posterior (el propio `rm`) sobrescribe `$?`; lo guardas antes y sales con él para no convertir un fallo en éxito.

Salida típica al interrumpir durante un `sleep`:

```
^Cinterrumpido
$ echo $?
130
```

Y al fallar un comando:

```
error en la línea 14: 'curl -fsSL "$url" -o "$tmpdir/paquete.tar.gz"' devolvió 22
```

Dos límites: `$LINENO` dentro de una función apunta a la línea dentro de la función en bash, no a la del llamador (para una traza completa está `caller`); y un `kill -9` (`SIGKILL`) no se puede capturar, así que ningún trap corre; para eso no hay más remedio que diseñar el script para que sea idempotente y limpie los restos de ejecuciones anteriores al arrancar.""",
            },
        ]
    },
    # 9) find/xargs con espacios y nombres raros
    {
        "messages": [
            {"role": "user", "content": "Quiero borrar todos los `.tmp` de más de 7 días en un árbol de directorios y comprimir los `.log` de más de 30. `find ... | xargs rm` me ha fallado con nombres con espacios. ¿Cuál es la forma robusta?"},
            {
                "role": "assistant",
                "content": r"""La forma robusta es no pasar nombres por texto separado por espacios o saltos de línea, que es lo que hace `find | xargs` por defecto. Tienes tres opciones, de más a menos simple.

**1. Deja que `find` ejecute la acción.** Sin tubería, sin `xargs`, sin problemas de nombres:

```bash
# Borrar .tmp con más de 7 días
find /var/app -type f -name '*.tmp' -mtime +7 -delete

# Comprimir .log con más de 30 días (uno por invocación)
find /var/app -type f -name '*.log' -mtime +30 -exec gzip -- {} \;
```

`-delete` es la acción de borrado integrada; ponla **al final** de la expresión (si la pones antes del `-name`, borra todo lo que coincida con lo anterior, que puede ser el árbol entero). `-exec cmd {} \;` lanza un proceso por archivo; para comandos que aceptan varios archivos, `-exec cmd {} +` los agrupa en pocas invocaciones, como haría `xargs`:

```bash
find /var/app -type f -name '*.log' -mtime +30 -exec gzip -- {} +
```

**2. `find -print0 | xargs -0`** cuando necesitas `xargs` (por ejemplo, para paralelizar con `-P`):

```bash
find /var/app -type f -name '*.log' -mtime +30 -print0 | xargs -0 -r -P 4 gzip --
```

`-print0` separa los nombres con el byte nulo, el único carácter que no puede aparecer en una ruta; `-0` hace que `xargs` lo use como separador. `-r` evita ejecutar el comando con cero argumentos si `find` no encuentra nada (en GNU; en BSD/macOS es el comportamiento por defecto). `-P 4` lanza cuatro `gzip` en paralelo.

**3. Bucle en bash con `read -d ''`**, cuando la acción es lógica de script y no un solo comando:

```bash
while IFS= read -r -d '' file; do
    size=$(stat -c %s -- "$file")
    (( size > 1048576 )) && gzip -- "$file"
done < <(find /var/app -type f -name '*.log' -mtime +30 -print0)
```

Sobre los predicados de tiempo, que confunden a todo el mundo: `-mtime +7` significa «más de 7 **días completos**», es decir, modificado hace 8 días o más; `-mtime 7` es exactamente entre 7 y 8 días; `-mtime -7` es menos de 7. Para precisión en minutos, `-mmin +60`. Y `-mtime` es la fecha de modificación del contenido; `-newer referencia` compara con otro archivo, útil para «desde la última ejecución».

Antes de borrar, ensaya la selección sustituyendo la acción por `-print`:

```bash
find /var/app -type f -name '*.tmp' -mtime +7 -print | head
```

Y para no salir del directorio por error (enlaces simbólicos a otros sistemas), `find` no sigue enlaces por defecto; `-xdev` además lo mantiene en el mismo sistema de archivos. Añade `-type f` siempre: sin él, `-name '*.log'` también casa con directorios y `-delete` los borraría si estuvieran vacíos.

Comprobación con nombres hostiles:

```bash
mkdir -p t && touch "t/con espacio.tmp" "t/-raro.tmp" $'t/salto\nlinea.tmp'
touch -d '10 days ago' t/*.tmp
find t -type f -name '*.tmp' -mtime +7 -delete && ls -A t     # vacío
```""",
            },
        ]
    },
    # 10) sed/awk y portabilidad macOS vs Linux (system variante: solo comandos)
    {
        "messages": [
            {"role": "system", "content": "Responde solo con los comandos y un comentario breve por cada uno. Sin introducciones."},
            {"role": "user", "content": "Dame los equivalentes portables (que funcionen igual en macOS y Linux) de estas tareas con sed y awk: 1) reemplazar in-place `foo` por `bar` en un archivo; 2) sumar la tercera columna de un CSV; 3) imprimir las líneas 10 a 20; 4) borrar líneas en blanco; 5) sacar el valor de `version:` de un YAML sencillo."},
            {
                "role": "assistant",
                "content": r"""```bash
# 1) Reemplazo in-place. GNU sed acepta `-i` sin argumento; BSD sed (macOS) exige un sufijo,
#    así que la única forma común es dar el sufijo pegado y borrar la copia después.
sed -i.bak 's/foo/bar/g' archivo.txt && rm -f archivo.txt.bak

# 1b) Alternativa sin -i, idéntica en todos los sed: temporal + mv (conserva permisos si usas cat >).
sed 's/foo/bar/g' archivo.txt > archivo.txt.tmp && mv archivo.txt.tmp archivo.txt

# 2) Suma de la tercera columna. -F, fija el separador; NR>1 salta la cabecera; +0 fuerza número.
awk -F, 'NR > 1 { total += $3 } END { print total + 0 }' datos.csv

# 2b) Si el CSV lleva comillas con comas dentro, awk -F, no sirve; usa un parser real.
python3 -c 'import csv,sys; print(sum(float(r[2]) for r in list(csv.reader(sys.stdin))[1:]))' < datos.csv

# 3) Líneas 10 a 20. `q` en la 20 evita leer el resto; funciona igual en GNU y BSD.
sed -n '10,20p; 20q' archivo.txt

# 3b) Misma cosa con awk, por si el rango viene de una variable.
awk -v a=10 -v b=20 'NR >= a && NR <= b { print } NR == b { exit }' archivo.txt

# 4) Borrar líneas en blanco, incluidas las que solo tienen espacios o tabuladores.
#    [[:space:]] es POSIX; \s solo existe en GNU sed.
sed '/^[[:space:]]*$/d' archivo.txt

# 4b) Equivalente en awk (NF es 0 cuando la línea no tiene campos).
awk 'NF' archivo.txt

# 5) Valor de `version:` en un YAML plano. Quita comillas y espacios; -m1/q paran en la primera.
sed -n 's/^version:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/p; /^version:/q' config.yaml

# 5b) Más legible con awk; sub() limpia comillas. Para YAML real (anidado, listas) usa yq.
awk -F': *' '$1 == "version" { gsub(/"/, "", $2); print $2; exit }' config.yaml

# Reglas que explican las diferencias:
#   - sed -i: GNU opcional, BSD obligatorio → siempre con sufijo o sin -i.
#   - sed -E (regex extendida) existe en ambos desde hace años; -r es solo GNU.
#   - Clases POSIX [[:space:]] [[:digit:]] en vez de \s \d (GNU/PCRE).
#   - awk: en macOS es BSD awk, en Linux suele ser gawk o mawk; evita funciones gawk
#     (gensub, strftime, arrays de arrays) si el script debe correr en los dos.
#   - Si de verdad necesitas GNU en macOS: brew install gnu-sed gawk → gsed, gawk.
```""",
            },
        ]
    },
    # 11) jq (usuario en inglés pide respuesta en español)
    {
        "messages": [
            {"role": "user", "content": "I have a JSON response from an API like `{\"items\": [{\"id\": 1, \"name\": \"a b\", \"tags\": [\"x\"], \"active\": true}, ...]}`. From bash I need: the names of active items one per line, a CSV of id,name, and to build a new JSON body with a value from a shell variable. Can you show me the jq way? Please answer in Spanish."},
            {
                "role": "assistant",
                "content": r"""Las tres cosas con `jq`, cada una con su detalle importante.

**1. Nombres de los activos, uno por línea:**

```bash
jq -r '.items[] | select(.active) | .name' respuesta.json
```

- `.items[]` recorre el array; `select(.active)` deja pasar solo los que tienen `active` verdadero; `.name` extrae el campo.
- **`-r`** (*raw*) imprime las cadenas sin comillas JSON. Sin él obtendrías `"a b"` con comillas, que luego rompe cualquier comparación en bash.

Si un nombre puede contener saltos de línea, usa `-j` con un separador nulo y léelo con `read -d ''`, o mejor `@sh` para generar algo citado para el shell.

**2. CSV de id,name:**

```bash
jq -r '.items[] | [.id, .name] | @csv' respuesta.json
```

`@csv` entrecomilla las cadenas y escapa las comillas internas según el estándar; `[.id, .name]` construye la fila como array. Salida: `1,"a b"`. Para tabuladores, `@tsv`; para una cabecera, antepón `'["id","name"], (.items[] | [.id, .name]) | @csv'`.

**3. Construir JSON con una variable del shell:**

```bash
name="O'Brien \"el grande\""
jq -n --arg name "$name" --argjson retries 3 \
   '{name: $name, retries: $retries, created: now | todate}'
```

- **`--arg`** pasa la variable como **cadena**, escapada correctamente: comillas, barras y saltos de línea dentro de `$name` salen bien en el JSON. Es la forma segura; nunca interpoles con `"{\"name\": \"$name\"}"`, que se rompe con cualquier comilla y es una inyección si el valor viene de fuera.
- **`--argjson`** pasa la variable como **valor JSON** (número, booleano, objeto): `3` llega como número, no como `"3"`.
- `-n` arranca sin entrada (`null`), porque aquí construyes desde cero.
- Para muchas variables, `--args` las deja en `$ARGS.positional`, y `env.HOME` lee variables de entorno directamente.

Dos patrones más que vas a necesitar enseguida:

```bash
# Iterar en bash sobre objetos completos, uno por línea (-c: compacto)
jq -c '.items[]' respuesta.json | while IFS= read -r item; do
    id=$(jq -r '.id' <<< "$item")
    name=$(jq -r '.name' <<< "$item")
    echo "procesando $id ($name)"
done

# Modificar un archivo JSON en sitio (jq no tiene -i; temporal + mv)
jq --arg v "$version" '.version = $v' package.json > package.json.tmp && mv package.json.tmp package.json
```

Un detalle del primer patrón: el `while` lee de una tubería, así que las variables que asignes dentro no sobreviven al bucle; si necesitas acumular, `done < <(jq -c ...)`.

Comprobación con el JSON de tu ejemplo: el punto 1 debe imprimir `a b` (sin comillas), el 2 `1,"a b"`, y `jq -n --arg name "$name" '{name: $name}' | jq -r .name` debe devolver exactamente el valor original de `$name`, comillas incluidas.""",
            },
        ]
    },
    # 12) procesado de logs (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo access.log de nginx en formato combinado. Necesito: las 10 IPs con más errores 5xx, y cuántos 5xx hubo por hora. Sin instalar nada, solo lo que hay en un servidor Linux normal."},
            {
                "role": "assistant",
                "content": r"""El formato combinado de nginx tiene estos campos por defecto:

```
203.0.113.7 - - [01/May/2024:13:45:02 +0000] "GET /api/x HTTP/1.1" 502 157 "-" "curl/8.0"
```

Separando por espacios: `$1` es la IP, `$4` la fecha con corchete inicial, `$9` el código de estado. El *user-agent* lleva espacios, pero va al final y no afecta a esas posiciones.

**Top 10 IPs con más 5xx:**

```bash
awk '$9 ~ /^5[0-9][0-9]$/ { print $1 }' access.log | sort | uniq -c | sort -rn | head -10
```

- `$9 ~ /^5[0-9][0-9]$/` filtra por regex sobre el campo del estado; es más seguro que `$9 >= 500`, porque si una línea está mal formada `$9` puede ser texto.
- `sort | uniq -c` cuenta ocurrencias (`uniq` solo agrupa líneas consecutivas, por eso el `sort` previo); `sort -rn` ordena por el número descendente.

Lo mismo en un solo `awk`, sin pasar dos veces por `sort`, que en un log de varios GB se nota:

```bash
awk '$9 ~ /^5[0-9][0-9]$/ { n[$1]++ } END { for (ip in n) print n[ip], ip }' access.log | sort -rn | head -10
```

**5xx por hora:**

```bash
awk '$9 ~ /^5[0-9][0-9]$/ { split($4, t, ":"); h = substr(t[1], 2) ":" t[2]; n[h]++ }
     END { for (h in n) print h, n[h] }' access.log | sort
```

`$4` es `[01/May/2024:13:45:02`; `split` por `:` deja la fecha en `t[1]` y la hora en `t[2]`; `substr(t[1], 2)` quita el corchete. La salida es `01/May/2024:13 42`, ordenada por `sort` (ordena como texto; dentro de un mismo día es correcto; entre meses no, pero para una hora de incidente basta).

**Si los logs están rotados y comprimidos**, procesa todos de una vez; `zcat -f` descomprime los `.gz` y pasa los demás tal cual:

```bash
zcat -f /var/log/nginx/access.log* | awk '...'
```

**Para acotar a un intervalo** (de 13:00 a 14:00 del 1 de mayo), filtra por prefijo de `$4` antes de contar:

```bash
awk '$4 >= "[01/May/2024:13" && $4 < "[01/May/2024:14" && $9 ~ /^5/ { n[$1]++ } END { for (ip in n) print n[ip], ip }' access.log | sort -rn | head
```

La comparación de cadenas funciona porque el formato tiene ancho fijo dentro de un mismo día.

Si tu `log_format` es personalizado, los índices cambian; confírmalos con una línea: `head -1 access.log | awk '{ for (i = 1; i <= NF; i++) print i, $i }'`.

Verificación: `awk '$9 ~ /^5/' access.log | wc -l` debe coincidir con la suma de la segunda columna de la salida por horas.""",
            },
        ]
    },
    # 13) scripts idempotentes
    {
        "messages": [
            {"role": "user", "content": "Tengo un script de aprovisionamiento que falla si lo ejecuto dos veces (el usuario ya existe, el directorio ya existe, la línea ya está en el archivo). ¿Cómo lo hago idempotente?"},
            {
                "role": "assistant",
                "content": r"""Idempotente significa que la segunda ejecución deja el sistema **igual que la primera** y termina con éxito. La regla práctica: cada paso describe un estado deseado y comprueba si ya se cumple antes de actuar, o usa un comando que ya sea idempotente de por sí.

Los casos que mencionas, con su forma correcta:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Directorios: -p no falla si existe y crea los intermedios
mkdir -p /opt/app/{bin,conf,logs}

# Usuario: comprueba antes de crear
if ! id -u app >/dev/null 2>&1; then
    useradd --system --home /opt/app --shell /usr/sbin/nologin app
fi

# Línea en un archivo: -q silencioso, -x línea completa, -F texto literal (sin regex)
line='export APP_ENV=production'
grep -qxF -- "$line" /etc/profile.d/app.sh 2>/dev/null || echo "$line" >> /etc/profile.d/app.sh

# Enlace simbólico: -f sustituye si existe, -n no entra en el directorio si el destino ya es un enlace a uno
ln -sfn /opt/app/releases/2024.05.01 /opt/app/current

# Copiar un archivo con permisos y propietario en un solo paso (crea o sobrescribe)
install -m 0640 -o app -g app conf/app.ini /opt/app/conf/app.ini

# Paquetes: apt-get es idempotente por naturaleza; -y para no preguntar
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

# Servicio: enable --now es idempotente; restart solo si cambió la configuración
systemctl enable --now nginx
```

Los patrones detrás:

1. **Comprobación + acción** (`if ! existe; then crear; fi`). Es la forma general. Cuidado con la ventana entre comprobar y actuar si varios procesos ejecutan el script a la vez; para eso, el siguiente punto.
2. **Comandos que ya son idempotentes**: `mkdir -p`, `ln -sfn`, `install`, `cp`, `chmod`, `chown`, `systemctl enable`, `apt-get install`. Prefiérelos a la comprobación manual.
3. **Reemplazar en vez de añadir.** Un `echo >> archivo` nunca es idempotente; escribir el archivo completo desde una plantilla sí lo es, y además deja el archivo en un estado conocido aunque alguien lo haya editado a mano:

```bash
cat > /etc/nginx/conf.d/app.conf <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
}
EOF
```

4. **Actuar solo si cambió algo**, para no reiniciar servicios en vano:

```bash
if ! cmp -s conf/nginx.conf /etc/nginx/nginx.conf; then
    install -m 0644 conf/nginx.conf /etc/nginx/nginx.conf
    nginx -t && systemctl reload nginx
fi
```

5. **Un cerrojo** si el script puede ejecutarse en paralelo (cron, varios operadores):

```bash
exec 9>/var/lock/provision.lock
flock -n 9 || { echo "ya hay una ejecución en curso" >&2; exit 1; }
```

Lo que **no** es idempotente y hay que vigilar: `useradd` y `groupadd` sin comprobar, `echo >>`, `sed -i` que añade texto (el reemplazo `s/a/b/` sí suele serlo), `git clone` en un directorio existente (comprueba `.git` y haz `git pull` o `fetch` + `checkout`), `openssl` generando claves (comprueba si el archivo existe), y cualquier contador o número de versión que se incremente.

La prueba es sencilla y debería estar en tu CI: ejecuta el script dos veces seguidas en una máquina limpia; la segunda debe terminar con código 0 y, si el script registra lo que hace, sin ninguna línea de «creado» o «modificado». Para los sistemas donde esto crece, Ansible o similares son exactamente esta idea elevada a herramienta; un script bash idempotente es el paso previo razonable.""",
            },
        ]
    },
    # 14) portabilidad sh vs bash, macOS vs Linux
    {
        "messages": [
            {"role": "user", "content": "Un script que va perfecto en mi Ubuntu falla en el contenedor de Alpine y otro distinto falla en el Mac de un compañero. ¿Qué cosas de bash no son portables y cómo escribo scripts que funcionen en los tres sitios?"},
            {
                "role": "assistant",
                "content": r"""Son dos problemas distintos: en Alpine `sh` es **BusyBox ash**, no bash, y probablemente no hay bash instalado; en macOS sí hay bash, pero es la **3.2 de 2007**, y las herramientas (`sed`, `date`, `readlink`, `grep`) son versiones BSD con opciones diferentes a las GNU.

**Decisión 1: ¿sh o bash?** Elige una y declárala con el *shebang*:

- `#!/bin/sh` → escribe POSIX puro. Funciona en dash (Debian/Ubuntu), ash (Alpine), bash y el sh de macOS. Renuncias a arrays, `[[ ]]`, `local -n`, `mapfile`, `${var//a/b}`, `<<<`, `<(...)`, `set -o pipefail` (hasta POSIX 2024).
- `#!/usr/bin/env bash` → todo lo anterior disponible, pero exige bash instalado (`apk add bash` en Alpine) y, en macOS, limitarte a lo que hay en 3.2 o documentar que hace falta un bash moderno (`brew install bash`).

Para scripts de más de cincuenta líneas, bash compensa; para *hooks* y *entrypoints* de contenedores, `sh` POSIX evita una dependencia.

**Lo que rompe en `sh` (dash/ash) y su equivalente POSIX:**

| Bash | POSIX sh |
|---|---|
| `[[ $a == b* ]]` | `case $a in b*) ... ;; esac` |
| `arr=(a b); "${arr[@]}"` | Usa `set -- a b; "$@"` (una sola lista) |
| `${var//x/y}` | `printf '%s' "$var" \| sed 's/x/y/g'` |
| `echo -e "a\tb"` / `echo -n` | `printf 'a\tb\n'` (`echo` varía entre shells) |
| `$'\n'` | `printf '\n'` o una variable con salto literal |
| `function f { }` | `f() { }` |
| `local x` | Funciona en dash y ash aunque no es POSIX estricto |
| `source f` | `. f` |
| `read -r -a arr` | `read -r a b c` |
| `set -o pipefail` | No existe hasta POSIX 2024; comprueba `$?` de cada etapa o usa un temporal |
| `(( i++ ))` | `i=$((i + 1))` |

**Lo que rompe entre GNU (Linux) y BSD (macOS)** aunque uses bash:

| Tarea | GNU | BSD/macOS | Portable |
|---|---|---|---|
| Editar in-place | `sed -i 's/a/b/' f` | `sed -i '' 's/a/b/' f` | `sed -i.bak ... && rm f.bak` o temporal + `mv` |
| Fecha relativa | `date -d '-1 day'` | `date -v-1d` | Calcular desde `epoch`: `date -u -r $(( $(date +%s) - 86400 ))` en BSD, `-d @N` en GNU; o usar Python |
| Ruta absoluta | `readlink -f` | No existe `-f` (hasta macOS 12.3) | `cd "$(dirname "$f")" && pwd -P` |
| Regex extendida | `grep -E`, `sed -E` | Igual | `-E` sí; `-P` (PCRE) solo GNU |
| `\s`, `\d` en sed | Sí | No | Clases POSIX `[[:space:]]`, `[[:digit:]]` |
| `xargs -r` | Sí | No (es el comportamiento por defecto) | Evita el caso vacío con `find ... -exec {} +` |
| `mktemp` | `mktemp -d` | `mktemp -d` ok; con plantilla exige `-t` | `mktemp -d` sin plantilla, o `mktemp -d "${TMPDIR:-/tmp}/app.XXXXXX"` |
| `stat` | `stat -c %s f` | `stat -f %z f` | `wc -c < f` para el tamaño |
| `cp -r` con directorio | `cp -r src/ dst` copia el contenido | Copia el directorio dentro | Evita la barra final o usa `rsync -a` |

**Herramientas para no descubrirlo en producción:**

1. `shellcheck -s sh script.sh` avisa de bashismos cuando el shebang es `sh` (código SC2039/SC3xxx).
2. Prueba en los tres con Docker: `docker run --rm -v "$PWD":/w -w /w alpine:3.20 sh script.sh` y `debian:bookworm-slim dash script.sh`. Para macOS no hay contenedor; un `bash --version` del compañero te dice qué versión estás soportando.
3. Instala `checkbashisms` (paquete `devscripts` en Debian) para scripts `sh`.

La regla que más portabilidad da por menos esfuerzo: usa `printf` en vez de `echo`, cita todo, no uses `-i` en `sed`, y cuando una tarea necesite más de una opción no portable (fechas, JSON, CSV), delega en `python3`, que está en casi todas partes y se comporta igual.""",
            },
        ]
    },
    # 15) salida de shellcheck (el usuario trae los avisos)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Pasé shellcheck por primera vez a un script de despliegue y me saca esto. ¿Cuáles son de verdad y cuáles puedo ignorar?

```
In deploy.sh line 8:
cd $RELEASE_DIR
   ^----------^ SC2086: Double quote to prevent globbing and word splitting.
^-------------^ SC2164: Use 'cd ... || exit' or 'cd ... || return' in case cd fails.

In deploy.sh line 12:
local version=$(git describe --tags)
      ^-----^ SC2155: Declare and assign separately to avoid masking return values.

In deploy.sh line 15:
for f in $(ls *.tar.gz); do
         ^-----------^ SC2045: Iterating over ls output is fragile. Use globs.

In deploy.sh line 21:
if [ $status == "ok" ]; then
     ^-----^ SC2086: Double quote to prevent globbing and word splitting.
             ^-- SC2039: In POSIX sh, == in place of = is undefined.

In deploy.sh line 30:
echo "Desplegado en $(date)" >> $LOG
                               ^--^ SC2086: Double quote to prevent globbing and word splitting.
```""",
            },
            {
                "role": "assistant",
                "content": r"""Todos son de verdad, y dos de ellos (SC2164 y SC2155) son de los que producen despliegues rotos en silencio. Van ordenados por gravedad, con la corrección de cada uno.

**SC2164, línea 8: `cd` sin comprobar.** Si `$RELEASE_DIR` no existe, `cd` falla, y **el resto del script se ejecuta en el directorio actual**: un `rm -rf ./*` o un `tar -x` posterior lo hace donde no debe. Es el aviso más peligroso de la lista.

```bash
cd "$RELEASE_DIR" || exit 1
```

Con `set -e` activo el `cd` fallido también aborta, pero el `|| exit` deja la intención explícita y protege si alguien quita el `set -e`.

**SC2155, línea 12: `local` enmascara el código de salida.** `local version=$(git describe --tags)` devuelve siempre 0, el código de `local`, aunque `git` falle (sin tags, fuera de un repo). Tu script seguiría con `version` vacía.

```bash
local version
version=$(git describe --tags) || { echo "sin tags" >&2; return 1; }
```

**SC2045, línea 15: iterar sobre `ls`.** Se rompe con nombres con espacios y con nombres que empiecen por `-`. El glob directo es más corto y correcto:

```bash
for f in *.tar.gz; do
    [ -e "$f" ] || continue     # sin coincidencias, el glob queda literal
    ...
done
```

**SC2039, línea 21: `==` dentro de `[ ]` con shebang `sh`.** El aviso te está diciendo que el script declara `#!/bin/sh`, y en dash `[ a == b ]` da `unexpected operator`. Dos salidas: `=` (POSIX) o cambiar el shebang a bash si ya usas bashismos (y `local` lo es, estrictamente). Si lo pasas a bash, usa `[[ ]]` y este aviso y el SC2086 de esa línea desaparecen juntos.

```bash
if [ "$status" = "ok" ]; then
```

**SC2086 (×3): expansiones sin comillas.** `cd $RELEASE_DIR`, `[ $status == ... ]`, `>> $LOG`. Cada una se parte por espacios y expande comodines. Con `RELEASE_DIR="/srv/releases/v2 beta"` el `cd` iría a `/srv/releases/v2`. Comillas en las tres:

```bash
cd "$RELEASE_DIR" || exit 1
if [ "$status" = "ok" ]; then
echo "Desplegado en $(date)" >> "$LOG"
```

**Cuándo ignorar un aviso.** Casi nunca en un script de despliegue, pero cuando sepas que una expansión sin comillas es intencional (quieres que una variable con varias opciones se parta: `$EXTRA_FLAGS`), dilo en el código, en la línea anterior, con el código concreto:

```bash
# shellcheck disable=SC2086  # EXTRA_FLAGS contiene varias opciones separadas por espacios
rsync $EXTRA_FLAGS -a src/ "$dest"/
```

Y mejor aún, evita la excepción usando un array: `extra_flags=(--delete --compress); rsync "${extra_flags[@]}" ...`.

Para que no vuelva a acumularse: añade `shellcheck -x deploy.sh` al CI, y en el editor la extensión de ShellCheck te lo marca al escribir. El `-x` sigue los `source` de otros archivos. Si el equipo usa bash a propósito, pon `#!/usr/bin/env bash` y `shellcheck` dejará de avisar de los bashismos y pasará a avisar de los errores de bash, que es lo que quieres.

Comprobación tras los cambios: `shellcheck deploy.sh` sin salida y código 0, y un `RELEASE_DIR` inexistente debe terminar el script en la línea 8 con código 1, sin ejecutar nada más.""",
            },
        ]
    },
    # 16) cron (multiturno, system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Un script de backup funciona perfecto si lo lanzo a mano, pero desde cron no hace nada y no hay ningún error en ningún sitio. La línea del crontab es `0 3 * * * /home/deploy/backup.sh`."},
            {
                "role": "assistant",
                "content": r"""«Funciona a mano y no en cron» tiene casi siempre la misma causa: cron ejecuta el script con un **entorno mínimo**, distinto del de tu sesión. Y «no hay error en ningún sitio» es porque la salida de cron va al correo local del usuario (`/var/mail/deploy`), que nadie lee, o se pierde si no hay agente de correo.

Primero haz visible el problema: captura la salida en un archivo.

```
0 3 * * * /home/deploy/backup.sh >> /home/deploy/backup.log 2>&1
```

Ejecuta a mano `run-parts` no; en su lugar simula el entorno de cron para reproducirlo ahora mismo sin esperar a las 3:

```bash
env -i HOME=/home/deploy SHELL=/bin/sh PATH=/usr/bin:/bin /bin/sh -c /home/deploy/backup.sh
```

Lo que casi seguro vas a ver en el log, por orden de frecuencia:

**1. `command not found`.** El `PATH` de cron es `/usr/bin:/bin`. Tu `pg_dump`, `aws`, `restic` o lo que uses está en `/usr/local/bin`, `~/.local/bin` o un `nvm`/`pyenv`. Arreglo: rutas absolutas en el script, o define `PATH` al principio del script (no dependas del crontab):

```bash
#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin
```

**2. Variables de entorno que no existen.** `AWS_PROFILE`, `PGPASSWORD`, tokens exportados en tu `.bashrc`: cron no lee `.bashrc` ni `.profile`. Cárgalas explícitamente desde un archivo con permisos 600:

```bash
set -a; . /home/deploy/.backup.env; set +a
```

**3. Shell equivocado.** Cron usa `/bin/sh` (dash en Debian/Ubuntu) para ejecutar la línea. Si el script tiene shebang y es ejecutable (`chmod +x`), el shebang manda y no hay problema; si en el crontab pusiste `sh backup.sh`, los bashismos fallan.

**4. Directorio de trabajo.** Cron arranca en `$HOME`. Rutas relativas como `./dumps/` apuntan a otro sitio que cuando lo lanzas desde el directorio del proyecto. `cd "$(dirname "$0")"` al principio, o rutas absolutas.

**5. El `%`.** En un crontab, `%` significa salto de línea; `date +%F` dentro de la línea del crontab rompe el comando. Dentro del script no afecta; en el crontab escápalo `\%`.

Dos mejoras mientras estás ahí:

- Evita que dos ejecuciones se solapen si el backup tarda más de lo previsto: `0 3 * * * flock -n /tmp/backup.lock /home/deploy/backup.sh >> ... 2>&1`.
- Si no quieres el log manual, `MAILTO=ops@example.com` al principio del crontab envía la salida (solo cuando la hay) a un buzón que sí se lee; para que no envíe nada en caso de éxito, el script debe ser silencioso cuando todo va bien.

Verificación: con la redirección puesta, fuerza una ejecución en dos minutos (`*/2 * * * *` temporalmente o la hora actual + 2) y lee el log. El primer error que aparezca es el que te estaba faltando.""",
            },
            {"role": "user", "content": "Era el PATH (pg_dump en /usr/lib/postgresql/16/bin). Ya funciona, pero me he dado cuenta de que corre a las 3 hora local y el servidor cambió de zona horaria con el horario de verano, así que un día corrió dos veces y otro ninguna. ¿Cómo evito eso?"},
            {
                "role": "assistant",
                "content": r"""Programa el trabajo en **UTC**, que no tiene horario de verano, y deja que la hora local sea un detalle de presentación.

Tienes tres niveles donde hacerlo, de más a menos recomendable:

**1. La variable `CRON_TZ` en el crontab** (cronie, el cron de RHEL/Fedora/Arch, y Debian desde cron 3.0pl1-150):

```
CRON_TZ=UTC
0 1 * * * /home/deploy/backup.sh >> /home/deploy/backup.log 2>&1
```

`CRON_TZ` fija la zona con la que cron interpreta las líneas que vienen después (puedes cambiarla varias veces en el mismo archivo). 01:00 UTC es 03:00 en Madrid en invierno y 02:00 en verano; elige la hora UTC que te convenga y deja de pensar en ello. Comprueba que tu cron la soporta: `man 5 crontab` debe mencionar `CRON_TZ`; si no, pasa al nivel 2.

**2. Poner el servidor en UTC**, que es la configuración razonable para cualquier máquina que no tenga usuarios interactivos:

```bash
sudo timedatectl set-timezone UTC
```

Todo (cron, logs del sistema, `date`) pasa a UTC. Las aplicaciones que necesiten hora local la convierten ellas. Es un cambio global; avisa al equipo, porque los logs cambian de hora de un día para otro.

**3. Un temporizador de systemd en lugar de cron**, si la máquina lo tiene:

```ini
# /etc/systemd/system/backup.timer
[Timer]
OnCalendar=*-*-* 01:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

`OnCalendar` acepta la zona en la propia expresión, y `Persistent=true` ejecuta la tarea al arrancar si la máquina estaba apagada a esa hora, cosa que cron no hace. `systemctl list-timers` te muestra la próxima ejecución ya calculada, lo que elimina las dudas.

Sobre lo que viste: en el cambio de **primavera** la hora 02:00-03:00 local no existe; los cron clásicos (Vixie) ejecutan los trabajos de esa hora inmediatamente después del salto, pero algunas implementaciones los saltan. En el de **otoño** la hora 02:00-03:00 existe dos veces y los trabajos se ejecutan dos veces. Un trabajo a las 03:00 queda justo en el borde, que es el peor sitio posible; en UTC no hay bordes.

Si por política el backup debe correr «a las 3 hora local» pase lo que pase, la solución es programarlo en UTC a una hora que nunca caiga en la transición (que en Europa ocurre a las 01:00 UTC) y aceptar que un día al año será a las 2 o a las 4 local; o usar el temporizador de systemd con `OnCalendar=*-*-* 03:00:00 Europe/Madrid`, que resuelve correctamente los días de cambio (ejecuta una vez).

Verificación tras el cambio: `grep CRON /var/log/syslog` (o `journalctl -u cron`) en el próximo cambio de hora debe mostrar exactamente una ejecución; y mientras tanto, `date -u` y la hora de la línea del crontab deben cuadrar con el log.""",
            },
        ]
    },
    # 17) getopts (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Cómo parseo opciones en un script bash de forma decente? Quiero `-v` (verbose), `-o archivo` (salida) y `-n 5` (número de reintentos), y que los argumentos restantes sean los archivos a procesar."},
            {
                "role": "assistant",
                "content": r"""Con `getopts`, que viene en bash y en cualquier `sh` POSIX. Maneja opciones cortas, con o sin argumento, agrupadas (`-vn 5`), y te deja los argumentos posicionales listos después de un `shift`.

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<EOF
Uso: ${0##*/} [-v] [-o salida] [-n reintentos] archivo...

  -v              salida detallada
  -o salida       archivo de salida (por defecto: stdout)
  -n reintentos   número de reintentos, entero >= 0 (por defecto: 3)
  -h              esta ayuda
EOF
}

verbose=0
output=""
retries=3

while getopts ':vo:n:h' opt; do
    case $opt in
        v) verbose=1 ;;
        o) output=$OPTARG ;;
        n)
            [[ $OPTARG =~ ^[0-9]+$ ]] || { echo "error: -n requiere un entero" >&2; exit 2; }
            retries=$OPTARG
            ;;
        h) usage; exit 0 ;;
        :)  echo "error: la opción -$OPTARG requiere un argumento" >&2; usage >&2; exit 2 ;;
        \?) echo "error: opción desconocida -$OPTARG" >&2; usage >&2; exit 2 ;;
    esac
done
shift $((OPTIND - 1))

(( $# > 0 )) || { echo "error: falta al menos un archivo" >&2; usage >&2; exit 2; }

for file in "$@"; do
    (( verbose )) && echo "procesando $file (reintentos: $retries)" >&2
    # trabajo con "$file"; la salida va a "$output" si está definida
done
```

Las piezas que importan:

- **La cadena `':vo:n:h'`.** Cada letra es una opción; los dos puntos **después** de una letra indican que lleva argumento (`o:`, `n:`). Los dos puntos **al principio** activan el modo silencioso: `getopts` no imprime sus propios mensajes y en su lugar te entrega `:` (falta argumento) o `?` (opción desconocida) para que los gestiones tú con un mensaje coherente.
- **`$OPTARG`** contiene el argumento de la opción actual (o, en los casos de error, la letra problemática).
- **`shift $((OPTIND - 1))`** descarta las opciones ya procesadas; a partir de ahí `"$@"` son solo los archivos. Sin esta línea, el bucle recibiría también `-v -o salida`.
- **Validar en el `case`**: `getopts` no sabe que `-n` debe ser un número; lo compruebas tú.
- Código de salida **2** para errores de uso (convención de las utilidades Unix), 0 para `-h`.

Se acepta `--` para separar opciones de argumentos: `script -v -- -archivo-raro.txt` procesa un archivo cuyo nombre empieza por guion; `getopts` para en el `--` y el `shift` lo consume.

Comprobaciones rápidas:

```bash
./script -vn 5 -o out.txt a.txt b.txt   # agrupadas: verbose, 5 reintentos
./script -n                             # error: la opción -n requiere un argumento (código 2)
./script -x a.txt                       # error: opción desconocida -x
./script                                # error: falta al menos un archivo
```""",
            },
            {"role": "user", "content": "Perfecto. ¿Y opciones largas tipo `--output archivo` y `--dry-run`? getopts no las entiende, ¿verdad?"},
            {
                "role": "assistant",
                "content": r"""Correcto: `getopts` solo sabe de opciones de una letra. Para opciones largas tienes dos caminos.

**1. Bucle manual con `case`.** Es lo que hace la mayoría de scripts serios: unas 20 líneas, cero dependencias, y controlas exactamente la sintaxis que aceptas.

```bash
output=""
retries=3
verbose=0
dry_run=0

while (( $# > 0 )); do
    case $1 in
        -v|--verbose)   verbose=1 ;;
        --dry-run)      dry_run=1 ;;
        -o|--output)
            [[ ${2-} ]] || { echo "error: $1 requiere un argumento" >&2; exit 2; }
            output=$2; shift ;;
        --output=*)     output=${1#*=} ;;
        -n|--retries)
            [[ ${2-} =~ ^[0-9]+$ ]] || { echo "error: $1 requiere un entero" >&2; exit 2; }
            retries=$2; shift ;;
        --retries=*)    retries=${1#*=} ;;
        -h|--help)      usage; exit 0 ;;
        --)             shift; break ;;
        -*)             echo "error: opción desconocida $1" >&2; usage >&2; exit 2 ;;
        *)              break ;;
    esac
    shift
done

files=("$@")
```

Cómo se lee: cada vuelta mira `$1`; las opciones con argumento consumen también `$2` (de ahí el `shift` extra dentro del `case`); la forma `--output=valor` se cubre con un patrón aparte y `${1#*=}` quita todo hasta el `=`. `--` termina las opciones; cualquier otra cosa que no empiece por `-` es el primer archivo y rompe el bucle. `${2-}` en vez de `$2` evita que `set -u` falle cuando no hay segundo argumento.

Lo que pierdes respecto a `getopts`: las opciones cortas agrupadas (`-vn 5`). Si las quieres, añade un caso que las expanda, o acepta que con opciones largas la gente no agrupa.

**2. `getopt` de GNU** (`util-linux`), que sí entiende opciones largas y reordena los argumentos para que puedas usar el mismo bucle:

```bash
parsed=$(getopt -o 'vo:n:h' --long 'verbose,output:,retries:,dry-run,help' -n "${0##*/}" -- "$@") || exit 2
eval set -- "$parsed"
```

Tras esto, `"$@"` contiene las opciones normalizadas (`--output archivo` y `--output=archivo` se vuelven iguales, las cortas agrupadas se separan) y un `--` antes de los posicionales, y entras en el bucle `case` de arriba. El problema: es **GNU**; el `getopt` de macOS y BSD es otro programa que no soporta `--long`. Si el script tiene que correr en Mac sin Homebrew, no lo uses. El `eval` es seguro aquí porque `getopt` cita su salida precisamente para eso.

Mi recomendación: el bucle manual. Es portable, se lee de un vistazo y, cuando un script crece hasta necesitar subcomandos y ayuda generada automáticamente, es señal de reescribirlo en Python con `argparse`, no de añadir más bash.

Comprobación del bucle manual:

```bash
./script --output=out.txt --retries 2 --dry-run -- -raro.txt   # output=out.txt retries=2 dry_run=1 files=(-raro.txt)
./script --retries                                            # error: --retries requiere un entero
```""",
            },
        ]
    },
    # 18) rm -rf con variable vacía y otros desastres (script del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Este script de limpieza borró más de la cuenta en un servidor de pruebas (por suerte). Antes de ponerlo en producción, ¿qué tiene mal?

```bash
#!/bin/bash
BUILD_DIR=$1
cd $BUILD_DIR
rm -rf *
rm -rf $BUILD_DIR/
cp -r ../artifacts/ $BUILD_DIR
echo "limpio"
```""",
            },
            {
                "role": "assistant",
                "content": r"""Tiene cuatro formas distintas de borrar lo que no debe. En orden de gravedad:

**1. `cd $BUILD_DIR` sin comprobar, seguido de `rm -rf *`.** Si `$1` no viene (`BUILD_DIR` vacío), `cd` sin argumento te lleva a `$HOME` y el `rm -rf *` lo vacía. Si `$1` no existe, `cd` falla, el script **continúa** en el directorio desde el que se lanzó y lo vacía. Esto es casi seguro lo que pasó en pruebas.

**2. `rm -rf $BUILD_DIR/` con la variable vacía.** Se convierte en `rm -rf /`. Las versiones modernas de GNU `rm` se niegan a borrar `/` sin `--no-preserve-root`, pero `rm -rf /*` o un `BUILD_DIR` con un espacio (`/srv/builds/app 1` → `rm -rf /srv/builds/app 1/`) no están protegidos.

**3. Expansiones sin comillas.** Un `BUILD_DIR` con espacios se parte en dos rutas; con `*` dentro, se expande como comodín.

**4. `cp -r ../artifacts/ $BUILD_DIR`.** Depende del directorio actual (el `..`) que, por el punto 1, no sabes cuál es. Y la barra final en `artifacts/` cambia el resultado entre GNU y BSD `cp` (copia el contenido o el directorio).

Versión que falla antes de hacer daño:

```bash
#!/usr/bin/env bash
set -euo pipefail

build_dir=${1:?uso: ${0##*/} <directorio_de_build>}
artifacts=$(cd "$(dirname "$0")/../artifacts" && pwd -P)

# Normaliza y valida: existe, es directorio, y está dentro de la zona permitida
build_dir=$(cd "$build_dir" && pwd -P)
case $build_dir in
    /srv/builds/*) ;;
    *) echo "error: $build_dir está fuera de /srv/builds" >&2; exit 2 ;;
esac

rm -rf -- "${build_dir:?}"/*
cp -R -- "$artifacts"/. "$build_dir"/
echo "limpio: $build_dir"
```

Qué protege cada línea:

- **`${1:?mensaje}`** aborta con ese mensaje si el argumento falta o está vacío. Es la forma más corta de exigir un parámetro.
- **`set -e` + `cd` dentro de `$(...)`**: si el directorio no existe, el `cd` falla, la sustitución falla y el script para antes de cualquier `rm`.
- **`pwd -P`** convierte la ruta en absoluta y sin enlaces simbólicos, para que la comprobación del `case` no se pueda saltar con `/srv/builds/../../etc`.
- **El `case` con lista blanca**: aunque todo lo demás falle, nunca se borra nada fuera de `/srv/builds`. Adáptalo a tu árbol.
- **`"${build_dir:?}"/*`**: `:?` dentro de la expansión del `rm` vuelve a fallar si por cualquier motivo la variable quedó vacía; es una defensa redundante y barata que vale la pena justo en los `rm -rf`.
- **`--`** antes de las rutas: un directorio llamado `-rf` o `--no-preserve-root` no se interpreta como opción.
- **`"$artifacts"/.`** copia el contenido de forma idéntica en GNU y BSD, sin la ambigüedad de la barra final.
- No hace `cd` en el shell principal: el `rm` y el `cp` reciben rutas absolutas, así que el directorio actual deja de importar.

Dos costumbres más para scripts que borran:

1. Un modo de ensayo: `DRY_RUN=1 ./limpiar.sh dir` que imprime los `rm` en vez de ejecutarlos (`run() { if (( DRY_RUN )); then printf '%q ' "$@"; echo; else "$@"; fi; }` y luego `run rm -rf -- ...`).
2. Pruébalo contra un directorio de mentira creado con `mktemp -d` dentro de `/srv/builds`, con nombres con espacios, y con el argumento vacío, inexistente y apuntando a `/`. Las tres últimas deben terminar con error y sin tocar nada.""",
            },
        ]
    },
    # 19) paralelismo en bash (en inglés)
    {
        "messages": [
            {"role": "user", "content": "I need to run an expensive conversion on ~2000 files in bash, using all 8 cores, and know at the end which files failed. What's the cleanest way without GNU parallel?"},
            {
                "role": "assistant",
                "content": r"""`xargs -P` is the standard tool: it keeps N workers busy from a stream of arguments and is available everywhere. The part that needs care is collecting failures, because `xargs` only tells you *that* something failed, not *what*.

**Pattern: one function per file, failures logged by the function itself.**

```bash
#!/usr/bin/env bash
set -euo pipefail

failed_log=$(mktemp)
trap 'rm -f -- "$failed_log"' EXIT
export failed_log

convert_one() {
    local src=$1 dst="${1%.wav}.flac"
    if ! ffmpeg -loglevel error -y -i "$src" "$dst" 2>"$src.err"; then
        printf '%s\n' "$src" >> "$failed_log"
        return 1
    fi
    rm -f -- "$src.err"
}
export -f convert_one

find audio -type f -name '*.wav' -print0 \
    | xargs -0 -P 8 -n 1 bash -c 'convert_one "$1"' _ || true

if [[ -s $failed_log ]]; then
    echo "failed ($(wc -l < "$failed_log")):" >&2
    cat "$failed_log" >&2
    exit 1
fi
echo "all files converted"
```

How the pieces fit:

- `-print0` / `-0` carry file names safely, including spaces.
- `-P 8` runs eight jobs at once; `-n 1` gives each job one file. For very short jobs, `-n 20` cuts process spawn overhead.
- `bash -c 'convert_one "$1"' _` runs the exported function in a child bash; `_` fills `$0` so the file lands in `$1`. `export -f` is what makes the function visible to the child shells (bash-only).
- Each failing job appends its own name to a shared log. Appends of a single short line are atomic on POSIX filesystems when the file is opened in append mode, so eight writers don't interleave.
- `|| true` after `xargs` stops `set -e` from aborting before you print the report; `xargs` exits 123 if any job failed, which you then replace with your own exit based on the log.

**Keep stdout readable.** Eight jobs writing progress at once interleave lines. Either make the worker quiet and report only at the end (as above, with per-file `.err` files), or prefix each line with the file name so the mixed output is still parseable.

**Alternative without xargs: background jobs and `wait -n`** (bash 4.3+), when you need per-job exit codes in the parent:

```bash
max_jobs=8
declare -A pid_file=()
failed=()

for f in audio/*.wav; do
    while (( ${#pid_file[@]} >= max_jobs )); do
        wait -n -p done_pid || failed+=("${pid_file[$done_pid]}")   # -p needs bash 5.1
        unset 'pid_file[$done_pid]'
    done
    convert_one "$f" & pid_file[$!]=$f
done
for pid in "${!pid_file[@]}"; do
    wait "$pid" || failed+=("${pid_file[$pid]}")
done
printf 'failed: %s\n' "${failed[@]}"
```

It avoids the shared log file but needs a recent bash, so on macOS's 3.2 it won't run. `xargs -P` is the one that works everywhere.

**Sizing.** `-P $(nproc)` on Linux, `-P $(sysctl -n hw.ncpu)` on macOS. For I/O-bound work (network, disk) go higher than the core count; for CPU-bound encoders like `ffmpeg`, which are already multithreaded, you may want `-P 4 -threads 2` rather than 8×8 threads fighting each other. Measure with `time` on a 50-file sample before committing the full run.

Verification: put a corrupt `.wav` in the set; the run must end with exit code 1, that file listed in the report, and every other file converted.""",
            },
        ]
    },
    # 20) expansiones de parámetros (en inglés, system variante)
    {
        "messages": [
            {"role": "system", "content": "Answer in English. Prefer shell builtins over external commands and say when something is bash-only."},
            {"role": "user", "content": "I keep spawning `basename`, `dirname`, `sed` and `tr` for tiny string operations in loops and it's slow. Which of these can bash do natively?"},
            {
                "role": "assistant",
                "content": r"""Nearly all of them, through parameter expansion. Each fork of `sed`/`basename` costs around a millisecond; in a loop over ten thousand files that's the difference between a 10 s script and an instant one.

```bash
path=/var/log/nginx/access.log.1

# dirname / basename
echo "${path%/*}"          # /var/log/nginx         (strip shortest suffix matching /*)
echo "${path##*/}"         # access.log.1           (strip longest prefix matching */)

# extension handling
file=${path##*/}
echo "${file%%.*}"         # access                 (strip longest suffix from first dot)
echo "${file%.*}"          # access.log             (strip shortest suffix: last extension)
echo "${file##*.}"         # 1                      (last extension)

# substitution: sed 's/a/b/' and 's/a/b/g'
s="2024-05-01"
echo "${s/-/.}"            # 2024.05-01             (first match)        bash
echo "${s//-/.}"           # 2024.05.01             (all matches)        bash
echo "${s/#20/19}"         # 1924-05-01             (anchored at start)  bash
echo "${s/%01/31}"         # 2024-05-31             (anchored at end)    bash

# case conversion: tr '[:lower:]' '[:upper:]'
name="Report"
echo "${name,,}"           # report                 bash 4+
echo "${name^^}"           # REPORT                 bash 4+
echo "${name^}"            # Report (first char)    bash 4+

# substring / length: cut -c, wc -c
echo "${s:0:4}"            # 2024                   bash
echo "${s: -2}"            # 01 (note the space before -: otherwise it's a default-value expansion)
echo "${#s}"               # 10

# defaults and required values
echo "${PORT:-8080}"       # 8080 if PORT unset or empty
: "${CONFIG:=/etc/app.conf}"   # assign default if unset or empty
: "${API_KEY:?API_KEY must be set}"   # abort with message if unset or empty
echo "${DEBUG:+--verbose}" # --verbose only if DEBUG is set and non-empty

# trim whitespace (no external command)
raw="  hello  "
trimmed=${raw#"${raw%%[![:space:]]*}"}    # strip leading
trimmed=${trimmed%"${trimmed##*[![:space:]]}"}   # strip trailing
echo "[$trimmed]"          # [hello]

# join an array with a separator: paste -sd,
items=(a b c)
IFS=,; echo "${items[*]}"; unset IFS   # a,b,c (set IFS only for that line in real scripts)
```

Mnemonics for the four operators people mix up: `#` removes from the **front** (`#` is to the left of `$` on a US keyboard), `%` from the **back**; one symbol is the shortest match, doubled is the longest.

Rules and limits:

- `${var%/*}`, `${var##*/}`, `${var:-x}`, `${var:=x}`, `${var:?x}`, `${var:+x}` and `${#var}` are **POSIX**; they work in `sh`, dash and busybox.
- `${var/a/b}`, `${var,,}`, `${var^^}`, `${var:off:len}` and arrays are **bash** (zsh and ksh have most of them with small differences).
- The patterns are **globs**, not regexes: `*`, `?`, `[...]`, plus `extglob` forms like `+(x)` if you `shopt -s extglob`. For real regex capture, `[[ $s =~ regex ]]` and `BASH_REMATCH` (bash-only).
- `dirname` has one edge case the expansion doesn't: `dirname file` prints `.`, while `${path%/*}` on a bare `file` returns `file` unchanged. Guard with `[[ $path == */* ]]` if inputs may lack a slash.
- Read a whole file without `cat`: `content=$(<file)` (bash); read lines into an array: `mapfile -t lines < file` (bash 4+).

Quick benchmark on 10 000 iterations to see why it matters:

```bash
time for i in {1..10000}; do b=$(basename "/a/b/c$i.txt"); done   # ~8-10 s
time for i in {1..10000}; do p="/a/b/c$i.txt"; b=${p##*/}; done   # ~0.05 s
```""",
            },
        ]
    },
    # 21) leer un archivo línea a línea -> CSV con comillas (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Cuál es la forma correcta de leer un archivo línea por línea en bash? Uso `for line in $(cat archivo)` y me parte las líneas por los espacios."},
            {
                "role": "assistant",
                "content": r"""`for ... in $(cat ...)` no itera por líneas sino por **palabras**: la salida de `cat` se parte por espacios, tabuladores y saltos de línea, y además cada palabra pasa por expansión de comodines (una línea con `*` se convierte en la lista de archivos del directorio).

La forma correcta es `while read`:

```bash
while IFS= read -r line || [[ -n $line ]]; do
    printf '%s\n' "$line"
done < archivo.txt
```

Cada pieza existe por una razón:

- **`read -r`**: sin `-r`, `read` interpreta las barras invertidas (`\n` se convierte en `n`, `\` al final de línea une la siguiente). Casi nunca quieres eso.
- **`IFS=`**: con el `IFS` por defecto, `read` recorta los espacios y tabuladores al principio y al final de la línea. Vaciarlo solo para ese `read` conserva la línea exacta.
- **`|| [[ -n $line ]]`**: si el archivo no termina en salto de línea, `read` devuelve fallo en la última línea aunque haya leído contenido, y el bucle la saltaría. Esta condición la rescata.
- **`< archivo.txt`** en vez de `cat archivo.txt |`: el bucle corre en el shell actual, así que las variables que modifiques dentro siguen existiendo después. Con la tubería corren en un subshell y se pierden.

Si dentro del bucle ejecutas un comando que lee de stdin (`ssh`, `ffmpeg`, `read` para preguntar algo), se **comerá el resto del archivo**. Dale al bucle otro descriptor:

```bash
while IFS= read -r -u 3 host; do
    ssh "$host" uptime          # ssh lee stdin, pero el bucle lee del descriptor 3
done 3< hosts.txt
```

(o `ssh -n`, que cierra stdin de ssh).

Para campos separados por un delimitador conocido y sin comillas (un `/etc/passwd`, un `.env`), `read` ya los separa si le das `IFS`:

```bash
while IFS=: read -r user _ uid gid _ home shell; do
    echo "$user -> $home ($shell)"
done < /etc/passwd
```

Las variables sobrantes se agrupan en la última; `_` descarta las que no te interesan.

Y si lo que necesitas es tener todas las líneas en un array para recorrerlas varias veces:

```bash
mapfile -t lines < archivo.txt         # bash 4+
echo "${#lines[@]} líneas"
```

Comprobación con un archivo hostil: tres líneas, una con espacios al principio, otra con `*` y una última sin salto de línea final. El bucle debe imprimir exactamente las tres, tal cual, con `printf '[%s]\n' "$line"`.""",
            },
            {"role": "user", "content": "Ahora el archivo es un CSV exportado de Excel, con campos entre comillas que llevan comas dentro (`\"Pérez, Ana\"`). El `IFS=,` me los rompe."},
            {
                "role": "assistant",
                "content": r"""Es el límite de bash para CSV: `IFS=,` no sabe de comillas, y un parser correcto de CSV (comillas, comas dentro, comillas escapadas como `""`, saltos de línea dentro de un campo) no es razonable escribirlo en bash. Hay dos salidas correctas y una trampa.

**1. Delegar el parseo a Python y seguir en bash.** `python3` está en casi cualquier máquina, y su módulo `csv` entiende exactamente el dialecto de Excel. Convierte el CSV a un formato que bash sí maneja: campos separados por tabulador (o por `\0` si los datos pueden llevar tabuladores):

```bash
python3 - exportado.csv <<'PY' | while IFS=$'\t' read -r name email amount; do
import csv, sys
with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:   # utf-8-sig quita el BOM de Excel
    for row in csv.reader(f):
        print('\t'.join(cell.replace('\t', ' ').replace('\n', ' ') for cell in row))
PY
    echo "nombre=$name correo=$email importe=$amount"
done
```

El bloque Python lee el CSV y lo reemite con tabuladores; el `while read` de bash recibe líneas limpias. El `heredoc` con `'PY'` entre comillas evita que bash toque el código Python. Si necesitas las variables después del bucle, invierte la estructura: `done < <(python3 ...)`.

**2. Hacer todo el procesado en Python** si el bucle crece. Diez líneas de bash alrededor de un parser suelen convertirse en treinta; en ese punto, un script Python con `csv.DictReader` es más corto y más seguro:

```python
import csv, sys

with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        print(f"{row['nombre']} -> {row['correo']}")
```

**La trampa: `awk -F,`.** Es lo primero que se intenta y falla igual que `IFS=,`. GNU awk 4+ tiene `FPAT` para describir «un campo es o bien texto sin comas o bien algo entre comillas»:

```bash
gawk -v FPAT='([^,]*)|("[^"]*")' '{ gsub(/"/, "", $2); print $1, $2 }' exportado.csv
```

Funciona para el caso de comas dentro de comillas, pero no para comillas escapadas (`""`) ni para saltos de línea dentro de un campo, y es solo GNU. Vale para una consulta rápida en la terminal; no para un script que procese exportaciones reales.

Dos detalles más de Excel que te van a aparecer:

- El archivo puede venir en **Windows-1252** en lugar de UTF-8 (tildes como `Ã©`): `encoding='cp1252'` en Python, o convierte antes con `iconv -f CP1252 -t UTF-8`.
- Los finales de línea son `\r\n`; `newline=''` en Python los maneja; en bash puro, `tr -d '\r'` antes del `read` o te queda un `\r` pegado al último campo.

Comprobación: una fila con `"Pérez, Ana"`, otra con un campo `"dijo ""hola"" ayer"` y otra con un salto de línea dentro de un campo. La opción 1 imprime tres filas con los campos correctos; `IFS=,` y `awk -F,` fallan en la primera, y `FPAT` en las otras dos.""",
            },
        ]
    },
    # 22) códigos de salida, dependencias, command -v (principiante)
    {
        "messages": [
            {"role": "user", "content": "Cuando mi script falla a mitad, el que lo llama (un pipeline de CI) cree que todo fue bien. ¿Cómo hago que un script bash informe bien de sus errores? ¿Y cómo compruebo al principio que las herramientas que necesita están instaladas?"},
            {
                "role": "assistant",
                "content": r"""Un script «informa bien» cuando termina con un código de salida distinto de cero ante cualquier fallo y escribe el motivo en stderr. El CI solo mira el código.

**Códigos de salida.** `$?` guarda el del último comando; `exit N` termina el script con `N`. Convenciones: 0 éxito, 1 error genérico, 2 uso incorrecto, 126 no ejecutable, 127 comando no encontrado, 128+señal (130 = Ctrl+C). Sin `exit` explícito, el script devuelve el código del **último comando ejecutado**, que es la causa de tu problema: si el fallo ocurre a mitad y el último comando es un `echo "fin"`, el script devuelve 0.

Esqueleto que resuelve ambas cosas:

```bash
#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "error: $*" >&2
    exit 1
}

require() {
    local missing=()
    for cmd in "$@"; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    (( ${#missing[@]} == 0 )) || die "faltan herramientas: ${missing[*]}"
}

require git docker jq curl

# trabajo
git fetch --tags || die "no se pudo hacer fetch"
version=$(git describe --tags) || die "el repositorio no tiene tags"
docker build -t "app:$version" . || die "falló la construcción de la imagen"
echo "construida app:$version"
```

Por qué así:

- **`set -e`** aborta en el primer comando que falle, con su código. **`-u`** convierte una variable sin definir en error (típico: un secreto que el CI no inyectó). **`-o pipefail`** hace que `cmd | tee log` falle si `cmd` falla.
- **`die`** centraliza el mensaje y el código. Los mensajes van a **stderr** (`>&2`) para que no se mezclen con la salida útil del script si alguien la captura.
- **`command -v`** es la forma POSIX de preguntar «¿existe este comando?». `which` no es estándar, imprime cosas distintas según el sistema y en algunos ni devuelve código de error. `type` también vale en bash.
- Comprobar **todas** las dependencias al principio y listar las que faltan de una vez evita el ciclo «instalo una, vuelvo a ejecutar, falta otra».

Para condiciones que no son «el comando falló», usa el código explícitamente:

```bash
[[ -f config.yaml ]] || die "falta config.yaml en $(pwd)"
[[ ${#} -ge 1 ]]     || { echo "uso: ${0##*/} <entorno>" >&2; exit 2; }
```

Si una versión mínima importa, compárala con `sort -V`:

```bash
need=2.40; have=$(git --version | awk '{print $3}')
[[ $(printf '%s\n' "$need" "$have" | sort -V | head -1) == "$need" ]] || die "git >= $need requerido (tienes $have)"
```

Y si el script tiene que **limpiar** algo al fallar (temporales, contenedores a medias), un `trap` en `EXIT` corre siempre, con cualquier código.

Comprobación desde la terminal, simulando lo que hace el CI:

```bash
./build.sh; echo "código: $?"          # debe ser 0 si todo fue bien
mv config.yaml config.bak; ./build.sh; echo "código: $?"   # mensaje en stderr y código 1
```

En GitHub Actions, GitLab CI o Jenkins, un paso que termina con código distinto de cero marca el trabajo como fallido sin ninguna configuración adicional; el único requisito es que tu script no lo oculte.""",
            },
        ]
    },
    # 23) PowerShell: objetos en la tubería (principiante, multiturno)
    {
        "messages": [
            {"role": "user", "content": "Vengo de bash y PowerShell me descoloca: hago `Get-Process | grep chrome` y no funciona, y `Get-Process | Sort-Object` ordena por algo que no entiendo. ¿Cómo se piensa en PowerShell?"},
            {
                "role": "assistant",
                "content": r"""La diferencia es una sola, y lo explica todo: en bash la tubería transporta **texto**; en PowerShell transporta **objetos** con propiedades tipadas. `Get-Process` no imprime líneas: emite objetos `System.Diagnostics.Process`, y lo que ves en pantalla es un formateador que los convierte en tabla al final.

Por eso `grep` no encaja: espera texto, y cuando PowerShell se lo da (convierte los objetos a su representación de tabla) filtra sobre esas columnas formateadas, que no es lo que quieres. El equivalente filtra por **propiedad**:

```powershell
Get-Process | Where-Object Name -like 'chrome*'
Get-Process | Where-Object { $_.CPU -gt 100 -and $_.WorkingSet64 -gt 500MB }
```

`$_` es el objeto actual; `-like` usa comodines, `-match` regex, `-eq`/`-gt` comparan valores de verdad (números con números). `500MB` es un literal numérico de PowerShell (= 524288000).

Para saber qué propiedades tiene un objeto, pregúntale:

```powershell
Get-Process | Get-Member               # propiedades y métodos del tipo
Get-Process chrome | Select-Object -First 1 | Format-List *   # todos los valores de uno
```

Con eso, el resto de la tubería es componer:

```powershell
Get-Process |
    Where-Object CPU -gt 10 |
    Sort-Object CPU -Descending |
    Select-Object -First 5 Name, Id, CPU, @{ Name = 'MemMB'; Expression = { [math]::Round($_.WorkingSet64 / 1MB) } }
```

- `Sort-Object` sin argumento ordena por la propiedad «por defecto» del tipo (para procesos, algo que no te sirve); dile siempre por cuál.
- `Select-Object` elige propiedades y puede **calcular** nuevas con el hash `@{ Name; Expression }`.
- La barra vertical al final de línea permite continuar en la siguiente sin acento grave.

Equivalencias de arranque, para traducir tus reflejos:

| bash | PowerShell |
|---|---|
| `grep patrón` sobre objetos | `Where-Object Prop -match 'patrón'` |
| `grep patrón` sobre texto/archivos | `Select-String 'patrón' archivo.log` |
| `awk '{print $1}'` | `Select-Object Prop` o `ForEach-Object { $_.Prop }` |
| `sort \| uniq -c` | `Group-Object Prop \| Sort-Object Count` |
| `wc -l` | `Measure-Object` (o `(...).Count`) |
| `head -5` / `tail -5` | `Select-Object -First 5` / `-Last 5` |
| `cut -d, -f2` | `ConvertFrom-Csv` y luego la propiedad |
| `xargs cmd` | `ForEach-Object { cmd $_ }` |

Un detalle que ahorra confusión: los alias `ls`, `cat`, `rm`, `cp` existen en Windows (apuntan a `Get-ChildItem`, `Get-Content`, etc.), pero **no en PowerShell para Linux/macOS**, donde dejan paso a los binarios reales. En scripts, escribe siempre el nombre completo del cmdlet.

Comprobación de que estás filtrando objetos y no texto: `(Get-Process | Where-Object Name -like 'chrome*').Count` devuelve un número, y `(Get-Process | Where-Object Name -like 'chrome*')[0].Id` el PID del primero. Con `grep` no tendrías ni `.Count` ni `.Id`.""",
            },
            {"role": "user", "content": "Entendido. ¿Y cómo saco ese resultado a un CSV y a JSON para pasárselo a otra herramienta?"},
            {
                "role": "assistant",
                "content": r"""Con los cmdlets `Export-Csv` y `ConvertTo-Json`, que serializan las **propiedades** de los objetos que les llegan. Lo que seleccionaste con `Select-Object` es exactamente lo que sale.

```powershell
$top = Get-Process |
    Where-Object CPU -gt 10 |
    Sort-Object CPU -Descending |
    Select-Object -First 5 Name, Id, CPU, @{ Name = 'MemMB'; Expression = { [math]::Round($_.WorkingSet64 / 1MB) } }

# CSV
$top | Export-Csv -Path top.csv -NoTypeInformation -Encoding utf8

# JSON (a archivo)
$top | ConvertTo-Json -Depth 3 | Set-Content -Path top.json -Encoding utf8
```

Detalles que evitan sorpresas:

- **`-NoTypeInformation`**: en PowerShell 5.1 (Windows PowerShell) `Export-Csv` añade una primera línea `#TYPE System.Management.Automation.PSCustomObject` que rompe a cualquier otra herramienta; en PowerShell 7 ya no la añade, pero el parámetro sigue siendo inofensivo y deja el script compatible.
- **`-Encoding utf8`**: en 5.1 el valor por defecto es ANSI y `utf8` escribe BOM; en 7 el valor por defecto es UTF-8 sin BOM. Si la herramienta destino es Excel en Windows y hay tildes, `utf8BOM` (solo 7) hace que las abra bien.
- **`ConvertTo-Json -Depth`**: el valor por defecto es **2** niveles; cualquier objeto anidado más profundo se serializa como su `ToString()` (una cadena inútil) **sin error**, solo con un aviso. Pon siempre `-Depth` explícito según tu estructura (hasta 100).
- `ConvertTo-Json` produce JSON con sangría; `-Compress` lo deja en una línea para logs o APIs.

Para enviarlo directamente a otro programa sin archivo intermedio, PowerShell convierte los objetos a texto al cruzar hacia un ejecutable nativo:

```powershell
$top | ConvertTo-Json -Compress | curl.exe -s -X POST -H 'Content-Type: application/json' --data-binary '@-' https://api.example.com/metrics
```

`curl.exe` con extensión, porque en Windows PowerShell `curl` es un alias de `Invoke-WebRequest`.

El camino inverso también existe y es lo que hace a PowerShell cómodo para datos: `Import-Csv top.csv` y `Get-Content top.json | ConvertFrom-Json` te devuelven objetos con propiedades, con los que vuelves a usar `Where-Object`, `Sort-Object` y el resto. Ten en cuenta que `Import-Csv` lee **todo como texto**: `[int]$_.Id` o `[double]$_.CPU` si vas a comparar números.

Comprobación: `Import-Csv top.csv | Measure-Object` debe dar `Count: 5`, y `(Get-Content top.json | ConvertFrom-Json)[0].MemMB` un número, no una cadena.""",
            },
        ]
    },
    # 24) PowerShell: manejo de errores (script roto del usuario, system variante)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de scripts estricto. Identifica cada fallo, explica por qué ocurre y entrega el script corregido completo."},
            {
                "role": "user",
                "content": r"""Este script de PowerShell 7 debería parar si falla algo, pero sigue adelante y al final dice «OK» aunque la copia falle o el servicio no exista:

```powershell
try {
    Copy-Item C:\build\app.dll -Destination \\srv01\apps\
    Stop-Service AppSvc
    & robocopy C:\build \\srv01\apps /MIR
    Start-Service AppSvc
    Write-Host "OK"
}
catch {
    Write-Host "Falló: $_"
    exit 1
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Tres fallos, y los tres son errores de modelo mental sobre cómo PowerShell trata los errores.

**1. `Copy-Item` y `Stop-Service` producen errores *no terminantes*.** La mayoría de cmdlets, cuando fallan, escriben el error en la secuencia de errores y **continúan**; `try/catch` solo captura errores *terminantes*. Por eso una copia fallida o un servicio inexistente imprimen rojo y el script sigue. Hay que convertirlos en terminantes con `-ErrorAction Stop` en cada cmdlet, o globalmente con `$ErrorActionPreference = 'Stop'`.

**2. `robocopy` es un ejecutable nativo, no un cmdlet.** Su fallo no es ni un error terminante ni uno no terminante: es un **código de salida** en `$LASTEXITCODE`, y `try/catch` lo ignora por completo. Además `robocopy` usa códigos propios: 0-7 son éxito (con matices: 1 = copió archivos, 2 = extras, 4 = desajustes), 8 o más es fallo. Hay que comprobarlo a mano. (`$?` tampoco sirve de mucho aquí: en PowerShell 7.4+ refleja el código de salida nativo, pero no sabe de la semántica 0-7 de robocopy.)

**3. `Write-Host` para el mensaje de error.** Va a la consola, no a la secuencia de errores: un pipeline de CI que capture stderr no lo ve, y no se puede redirigir. Usa `Write-Error` (o `throw`).

Corregido:

```powershell
#Requires -Version 7.0
[CmdletBinding()]
param(
    [string]$Source = 'C:\build',
    [string]$Target = '\\srv01\apps',
    [string]$ServiceName = 'AppSvc'
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # robocopy tiene códigos no estándar; lo evaluamos a mano

try {
    $svc = Get-Service -Name $ServiceName            # falla ya si no existe
    if ($svc.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName
        $svc.WaitForStatus('Stopped', [timespan]::FromSeconds(30))
    }

    & robocopy $Source $Target /MIR /R:2 /W:5 /NP | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -ge 8) {
        throw "robocopy falló con código $rc"
    }
    Write-Verbose "robocopy terminó con código $rc"

    Start-Service -Name $ServiceName
    $svc.WaitForStatus('Running', [timespan]::FromSeconds(30))
    Write-Output "Despliegue completado en $Target"
}
catch {
    Write-Error "Despliegue fallido: $($_.Exception.Message)"
    exit 1
}
```

Qué cambia y por qué:

- **`$ErrorActionPreference = 'Stop'`** al principio convierte todos los errores de cmdlets en terminantes dentro del script (es una variable de ámbito; no afecta a la sesión de quien lo llama).
- **`Get-Service` primero**: comprueba que el servicio existe antes de tocar nada, y `WaitForStatus` evita arrancar la copia mientras el proceso todavía tiene el DLL abierto.
- **`$LASTEXITCODE` leído inmediatamente** después del comando nativo, porque cualquier otro ejecutable lo sobrescribe. `-ge 8` es el umbral documentado de robocopy.
- **`$PSNativeCommandUseErrorActionPreference = $false`**: en PowerShell 7.4+ esta variable, cuando es `$true`, hace que **cualquier** código de salida distinto de 0 de un ejecutable lance error; con robocopy eso convertiría el éxito «1 = copié archivos» en fallo. La desactivamos explícitamente y evaluamos el código nosotros.
- **`Write-Output` para el resultado y `Write-Error` para el fallo**: cada uno en su secuencia, redirigibles y capturables.
- **`param` con valores por defecto**: deja de haber rutas incrustadas, y el script se puede probar contra un directorio de pruebas.
- La `Copy-Item` inicial sobraba: `/MIR` ya copia `app.dll`.

Comprobación: ejecuta con `-ServiceName NoExiste`; debe terminar con «Despliegue fallido: Cannot find any service with service name 'NoExiste'» en stderr y `$LASTEXITCODE` igual a 1. Luego con `-Target \\srv01\no_existe`: robocopy devuelve 16, el `throw` salta y el servicio no se queda parado sin que te enteres. Para comprobar que el servicio vuelve a arrancar aunque falle la copia, mueve `Start-Service` a un bloque `finally`; lo dejé fuera porque en un despliegue roto suele ser mejor no arrancar con archivos a medias, pero es una decisión tuya.""",
            },
        ]
    },
    # 25) PowerShell: script .ps1 con param, CmdletBinding, WhatIf (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Quiero convertir un script PowerShell que tiene las rutas y opciones «a fuego» en algo parametrizado que se comporte como un cmdlet: parámetros con validación, `-Verbose`, `-WhatIf`. ¿Cuál es la estructura mínima?"},
            {
                "role": "assistant",
                "content": r"""La estructura es un bloque `param` con `[CmdletBinding()]` encima. Solo con eso el script gana `-Verbose`, `-Debug`, `-ErrorAction` y, si lo declaras, `-WhatIf`/`-Confirm`, sin escribir el parseo.

```powershell
#Requires -Version 7.0
<#
.SYNOPSIS
    Archiva los logs de una aplicación más antiguos de N días.
.EXAMPLE
    ./Archive-Logs.ps1 -Path C:\app\logs -Days 30 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateScript({ Test-Path $_ -PathType Container }, ErrorMessage = "'{0}' no es un directorio")]
    [string]$Path,

    [ValidateRange(1, 3650)]
    [int]$Days = 30,

    [ValidateSet('zip', 'move', 'delete')]
    [string]$Action = 'zip',

    [string]$Archive = (Join-Path $Path 'archive')
)

$ErrorActionPreference = 'Stop'
$cutoff = (Get-Date).AddDays(-$Days)
Write-Verbose "Buscando en $Path archivos anteriores a $($cutoff.ToString('yyyy-MM-dd'))"

$old = Get-ChildItem -Path $Path -Filter '*.log' -File | Where-Object LastWriteTime -lt $cutoff
if (-not $old) {
    Write-Verbose 'Nada que archivar'
    return
}

if ($Action -ne 'delete' -and -not (Test-Path $Archive)) {
    New-Item -ItemType Directory -Path $Archive | Out-Null
}

foreach ($file in $old) {
    if ($PSCmdlet.ShouldProcess($file.FullName, $Action)) {
        switch ($Action) {
            'zip'    { Compress-Archive -Path $file.FullName -DestinationPath (Join-Path $Archive "$($file.BaseName).zip"); Remove-Item $file.FullName }
            'move'   { Move-Item -Path $file.FullName -Destination $Archive }
            'delete' { Remove-Item -Path $file.FullName }
        }
    }
}

[pscustomobject]@{ Processed = $old.Count; Action = $Action; Cutoff = $cutoff }
```

Lo que aporta cada parte:

- **`[CmdletBinding(SupportsShouldProcess)]`** activa `-WhatIf` y `-Confirm`. Cada acción destructiva se envuelve en `if ($PSCmdlet.ShouldProcess(objetivo, acción))`: con `-WhatIf` imprime «What if: Performing the operation "zip" on target "C:\app\logs\a.log"» y no hace nada; con `-Confirm` pregunta. Los cmdlets internos (`Remove-Item`) heredan la preferencia, así que también la respetan.
- **`[Parameter(Mandatory)]`**: si falta, PowerShell lo pide interactivamente o falla en modo no interactivo; no hace falta comprobar `$null`.
- **Atributos de validación** (`ValidateScript`, `ValidateRange`, `ValidateSet`): el error salta **antes** de ejecutar la primera línea del cuerpo, con un mensaje que nombra el parámetro. `ValidateSet` además da autocompletado con tabulador.
- **Valores por defecto calculados** (`$Archive`) pueden usar otros parámetros.
- **`Write-Verbose`** solo se ve con `-Verbose`; no ensucia la salida normal.
- **Devolver un objeto** (`[pscustomobject]`) en lugar de `Write-Host "Procesados 12"`: quien llame al script puede hacer `$r = ./Archive-Logs.ps1 ...; $r.Processed`, encadenarlo a `Export-Csv`, o comprobarlo en un test.
- El bloque de comentarios `.SYNOPSIS`/`.EXAMPLE` alimenta `Get-Help ./Archive-Logs.ps1 -Examples`.

Para que el script acepte entrada por tubería (`Get-ChildItem | ./script.ps1`), añade `ValueFromPipeline` al parámetro y bloques `begin/process/end`; para lo que describes no hace falta.

Comprobación: `./Archive-Logs.ps1 -Path C:\no\existe` debe fallar con el mensaje de `ValidateScript` sin ejecutar nada; `-Days 0` con el de `ValidateRange`; y `-WhatIf -Verbose` debe listar cada archivo que archivaría y dejar el directorio intacto (`(Get-ChildItem $Path -Filter *.log).Count` igual antes y después).""",
            },
        ]
    },
    # 26) ExecutionPolicy (principiante, multiturno)
    {
        "messages": [
            {"role": "user", "content": "En Windows intento ejecutar `.\\deploy.ps1` y me sale `cannot be loaded because running scripts is disabled on this system`. ¿Cómo lo arreglo sin desactivar la seguridad de todo el equipo?"},
            {
                "role": "assistant",
                "content": r"""Es la **política de ejecución** de PowerShell, que en Windows viene como `Restricted` (en clientes) o `RemoteSigned` (en servidores). No es un mecanismo de seguridad contra atacantes, sino una protección contra ejecutar scripts por accidente; por eso se puede cambiar por usuario sin tocar el sistema.

Lo razonable para tu usuario, sin privilegios de administrador:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

`RemoteSigned` significa: los scripts **locales** se ejecutan; los **descargados de Internet** (marcados por el navegador con la «zona» en un flujo alternativo del archivo) solo si están firmados. Es el equilibrio habitual: tus scripts corren y un `.ps1` bajado de cualquier sitio no.

Comprueba qué hay configurado y en qué ámbito manda:

```powershell
Get-ExecutionPolicy -List
```

Los ámbitos se evalúan de arriba abajo (`MachinePolicy`, `UserPolicy`, `Process`, `CurrentUser`, `LocalMachine`); el primero que no sea `Undefined` gana. Si `MachinePolicy` o `UserPolicy` están fijados, vienen de una directiva de grupo del dominio y el `Set-ExecutionPolicy` no los cambia; ahí hablas con el administrador o usas la opción de proceso de abajo.

Si el script lo descargaste (de un repositorio, de un correo) y `RemoteSigned` sigue bloqueándolo, quita la marca de Internet de ese archivo concreto, una vez revisado:

```powershell
Unblock-File .\deploy.ps1
```

Para ejecuciones puntuales o automatizadas (tareas programadas, CI) sin cambiar nada de forma permanente, la política se puede fijar **solo para ese proceso**:

```powershell
pwsh -ExecutionPolicy Bypass -File .\deploy.ps1
```

`-Scope Process` con `Set-ExecutionPolicy` hace lo mismo desde dentro de una sesión y se olvida al cerrarla.

Lo que no conviene: `Set-ExecutionPolicy Unrestricted -Scope LocalMachine` como administrador. Funciona, pero quita la protección a todos los usuarios de la máquina y se queda así para siempre.

En Linux y macOS no existe la política: `pwsh` ejecuta cualquier script, y `Get-ExecutionPolicy` devuelve `Unrestricted` siempre.

Verificación: tras el `Set-ExecutionPolicy ... CurrentUser`, `Get-ExecutionPolicy` (sin `-List`) debe devolver `RemoteSigned` y `.\deploy.ps1` debe arrancar.""",
            },
            {"role": "user", "content": "Ya corre. Pero quiero que lo ejecuten compañeros con doble clic, y al hacer doble clic en el .ps1 se abre el Bloc de notas."},
            {
                "role": "assistant",
                "content": r"""Es deliberado: la asociación por defecto de `.ps1` en Windows es «editar», justamente para que un script no se ejecute por un doble clic accidental. No la cambies (afectaría a todos los `.ps1` del equipo); da a tus compañeros un lanzador.

**Opción 1: un acceso directo (`.lnk`)**, que es lo más limpio. Crea un acceso directo junto al script con este destino:

```
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "C:\herramientas\deploy.ps1"
```

(`powershell.exe` si solo tienen Windows PowerShell 5.1.) En las propiedades del acceso directo puedes ponerle icono y «Iniciar en» la carpeta del script. `-NoProfile` evita que el perfil de cada usuario cambie el comportamiento; `-ExecutionPolicy Bypass` solo afecta a ese proceso, así que no tienen que configurar nada.

**Opción 2: un `.cmd` al lado**, que se ejecuta con doble clic y lanza el script. Útil si lo distribuyes en un zip, porque un `.lnk` con ruta absoluta se rompe al mover la carpeta:

```bat
@echo off
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1"
pause
```

`%~dp0` es la carpeta donde está el `.cmd`, así que funciona desde cualquier ubicación. El `pause` deja la ventana abierta para que vean el resultado; quítalo si el script ya espera al final.

Dos ajustes en el propio script para que funcione bien lanzado así:

```powershell
# Trabajar desde la carpeta del script, no desde donde lo lanzaron
Set-Location -Path $PSScriptRoot

# Que la ventana no se cierre antes de leer un error
try {
    # trabajo
}
catch {
    Write-Error $_
    Read-Host 'Pulsa Intro para cerrar'
    exit 1
}
```

Si los compañeros no tienen PowerShell 7 instalado, apunta a `powershell.exe` (5.1, siempre presente en Windows 10/11) y asegúrate de que el script no use nada exclusivo de 7 (`ConvertTo-Json -AsHashtable`, operadores `??` y `?.`, `ForEach-Object -Parallel`). Añadir `#Requires -Version 5.1` al principio documenta la compatibilidad y falla con un mensaje claro si no se cumple.

Y si el equipo crece, el paso siguiente es firmar el script con un certificado de la organización y dejar la política en `RemoteSigned` o `AllSigned`, de forma que el `Bypass` deje de ser necesario; para dos o tres compañeros, el acceso directo es suficiente.

Comprobación: copia la carpeta a otro equipo con política `Restricted`, doble clic en el `.cmd`: el script debe ejecutarse y la ventana mostrar la salida antes de cerrarse.""",
            },
        ]
    },
    # 27) equivalencias bash -> PowerShell (en inglés)
    {
        "messages": [
            {"role": "user", "content": "I'm porting a few bash helper scripts to PowerShell 7 so they run on Windows and Linux. What are the equivalents for the usual suspects: variables, env vars, `$(cmd)`, `&&`/`||`, exit codes, `find`, `grep -r`, `sed -i`, here-docs, and `$?`?"},
            {
                "role": "assistant",
                "content": r"""Most of it maps one-to-one; the places where it doesn't are the ones that bite, so they're marked.

| Task | bash | PowerShell 7 |
|---|---|---|
| Variable | `name=value` (no spaces) | `$name = 'value'` |
| Env var read | `$HOME`, `$PATH` | `$env:HOME`, `$env:PATH` |
| Env var set (this process + children) | `export KEY=value` | `$env:KEY = 'value'` |
| Command substitution | `out=$(cmd)` | `$out = cmd` (objects) or `$out = cmd \| Out-String` (text) |
| Chain on success / failure | `a && b`, `a \|\| b` | `a && b`, `a \|\| b` (PowerShell 7+; not in 5.1) |
| Exit code of last **native** command | `$?` (0-255) | `$LASTEXITCODE` |
| Success of last **cmdlet** | `$?` | `$?` (`$true`/`$false`) |
| Exit the script | `exit 1` | `exit 1` |
| Script arguments | `$1`, `"$@"` | `param($a, $b)` block, or `$args` |
| Script directory | `$(dirname "$0")` | `$PSScriptRoot` |
| `find . -name '*.log'` | | `Get-ChildItem -Recurse -Filter '*.log' -File` |
| `grep -rn 'pat' src/` | | `Get-ChildItem -Recurse src -File \| Select-String 'pat'` |
| `grep -q pat file && ...` | | `if (Select-String -Quiet 'pat' file) { ... }` |
| `sed -i 's/a/b/g' f` | | `(Get-Content f -Raw) -replace 'a','b' \| Set-Content f -NoNewline` |
| `cat f \| head -5` | | `Get-Content f -TotalCount 5` |
| `tail -f f` | | `Get-Content f -Wait -Tail 10` |
| `wc -l f` | | `(Get-Content f).Count` or `(Get-Content f \| Measure-Object -Line).Lines` |
| `mkdir -p d` | | `New-Item -ItemType Directory -Force d` |
| `rm -rf d` | | `Remove-Item d -Recurse -Force` |
| `cp -r a b` | | `Copy-Item a b -Recurse` |
| `which cmd` | | `Get-Command cmd` |
| `sleep 2` | | `Start-Sleep -Seconds 2` |
| `date +%F` | | `Get-Date -Format 'yyyy-MM-dd'` |
| `read -p 'x: ' v` | | `$v = Read-Host 'x'` |
| Here-doc | `cat <<'EOF' ... EOF` | `@' ... '@` (literal) or `@" ... "@` (expands `$vars`) |
| `set -e` | | `$ErrorActionPreference = 'Stop'` (cmdlets only; see below) |
| `set -u` | | `Set-StrictMode -Version Latest` |
| `trap ... EXIT` | | `try { } finally { }` |

Things that don't translate literally:

**1. Two kinds of errors.** Cmdlets throw (or write) PowerShell errors; native executables (`git`, `docker`, `curl.exe`) only set `$LASTEXITCODE`. `try/catch` and `$ErrorActionPreference` see the first kind only. For native commands, check `$LASTEXITCODE` yourself right after the call, or set `$PSNativeCommandUseErrorActionPreference = $true` (7.4+) so a non-zero exit becomes a terminating error.

**2. Quoting.** Single quotes are literal, double quotes expand `$var` and `$(expr)`; same spirit as bash. But the escape character is the backtick `` ` ``, not backslash, and backslash is just a path separator. `"C:\temp\$name"` works; to put a literal `$`, write `` "`$5" ``.

**3. Paths.** Use `Join-Path` and forward slashes; PowerShell accepts `/` on Windows and `\` is wrong on Linux. `~` expands in most cmdlets, `$HOME` always works.

**4. Output is objects.** `$files = Get-ChildItem` gives you `FileInfo` objects; `$files.Name`, `$files.Length`, `$files | Where-Object Length -gt 1MB`. Don't convert to text and parse it back; that's the bash reflex to unlearn.

**5. `sed -i` has no in-place cmdlet.** The `Get-Content -Raw` / `Set-Content` pair above rewrites the file; `-Raw` reads it as one string so multi-line regexes work, `-NoNewline` avoids appending a trailing newline. Encoding defaults to UTF-8 without BOM in PowerShell 7.

Minimal cross-platform script skeleton:

```powershell
#!/usr/bin/env pwsh
#Requires -Version 7.0
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Target)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
& git -C $root rev-parse --is-inside-work-tree | Out-Null
if ($LASTEXITCODE -ne 0) { throw "$root is not a git repository" }

Get-ChildItem -Path (Join-Path $root 'src') -Recurse -Filter '*.cs' -File |
    Select-String 'Console\.WriteLine' |
    ForEach-Object { "{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() }
```

The shebang makes it runnable as `./script.ps1` on Linux after `chmod +x`; on Windows it's ignored. Test on both with `pwsh -File script.ps1 -Target x` and compare `$LASTEXITCODE` after a deliberate failure.""",
            },
        ]
    },
    # 28) PowerShell: rendimiento y comparaciones (script del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Este script de PowerShell 7 tarda 20 minutos con un log de 2 GB y, además, cuenta como «error» líneas que no deberían contar. Lo que hace:

```powershell
$lines = Get-Content big.log
$errors = @()
foreach ($line in $lines) {
    if ($line -match "error") {
        $errors += $line
    }
}
$byHost = @{}
foreach ($e in $errors) {
    $host = ($e -split ' ')[1]
    if ($byHost[$host] -eq $null) { $byHost[$host] = 0 }
    $byHost[$host]++
}
$byHost
```""",
            },
            {
                "role": "assistant",
                "content": r"""Hay tres problemas de rendimiento y dos de corrección, y uno de los de corrección es el que explica los «errores de más».

**Corrección**

1. **`-match "error"` no distingue mayúsculas.** Los operadores de comparación de PowerShell (`-eq`, `-match`, `-like`) son *case-insensitive* por defecto. Esa condición casa con `ERROR`, `Error` y también con `errors_total=0` o `/api/error-pages`. Usa la variante sensible y una regex que delimite: `-cmatch '\bERROR\b'` (la `c` de *case-sensitive*). Lo mismo para `-ceq`, `-clike`.
2. **`$host` es una variable automática de PowerShell** (el objeto de la consola). Asignarla funciona en apariencia, pero pisa algo que otros cmdlets usan y confunde al lector. Llámala `$hostName`. (`$error`, `$input`, `$args`, `$matches` son otras que no debes reutilizar.)
3. Menor: `$byHost[$host] -eq $null` con el `$null` a la derecha funciona aquí porque el valor es escalar, pero la convención es `$null -eq $x`, porque si `$x` es un array la comparación con `$null` a la derecha devuelve los elementos nulos en vez de un booleano.

**Rendimiento**

1. **`Get-Content` sin `-Raw` ni `-ReadCount` crea un objeto `string` por línea y, al asignarlo a `$lines`, mantiene los 2 GB en memoria** como un array de millones de cadenas. Es lento y ocupa varias veces el tamaño del archivo.
2. **`$errors += $line` copia el array entero en cada iteración.** Los arrays de PowerShell son de tamaño fijo; `+=` crea uno nuevo con un elemento más. Con *n* coincidencias, eso es O(n²): con 500 000 errores son 125 000 millones de copias de referencias. Es, de largo, la causa de los 20 minutos.
3. El `-split ' '` y el hash por cada línea son razonables; el segundo bucle no es el problema.

Versión corregida: una sola pasada en *streaming*, sin arrays intermedios:

```powershell
$byHost = @{}
$pattern = [regex]::new('\bERROR\b')          # compilada una vez, sensible a mayúsculas

foreach ($line in [System.IO.File]::ReadLines('big.log')) {
    if ($pattern.IsMatch($line)) {
        $hostName = $line.Split(' ', 3)[1]      # solo parte lo necesario
        $byHost[$hostName] = 1 + $byHost[$hostName]   # $null + 1 = 1 en PowerShell
    }
}

$byHost.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 20
```

Por qué cada cambio:

- **`[System.IO.File]::ReadLines`** devuelve las líneas perezosamente, una a una; la memoria se queda en una línea, no en 2 GB. Es la forma más rápida de recorrer un archivo grande en PowerShell. La alternativa con cmdlets es `Get-Content big.log -ReadCount 10000 | ForEach-Object { foreach ($line in $_) { ... } }`, que lee por bloques y también evita cargar todo.
- **Sin `$errors`**: contamos directamente en la tabla hash. Si necesitaras conservar las líneas, usa una lista de tamaño variable, que añade en O(1): `$errors = [System.Collections.Generic.List[string]]::new(); $errors.Add($line)`.
- **Regex precompilada** fuera del bucle, en vez de que `-match` la interprete en cada iteración. Para dos millones de líneas se nota.
- **`Split(' ', 3)`** (método .NET) limita a tres trozos; `-split ' '` parte toda la línea aunque solo quieras el segundo campo.

Si el archivo es mucho mayor o el servidor tiene varios núcleos, el siguiente paso es `Select-String -Pattern '\bERROR\b' -CaseSensitive -Path big.log`, que está optimizado en C# y devuelve solo las coincidencias con número de línea; y para procesar varios archivos a la vez, `ForEach-Object -Parallel`.

Medida esperada: `Measure-Command { ... }` alrededor de la versión nueva con un log de 2 GB debería dar decenas de segundos, no minutos, y el consumo de memoria del proceso `pwsh` quedarse por debajo de 100 MB. Comprueba la corrección con un log de prueba que incluya `error-pages` en una ruta y `ERROR` como nivel: solo la segunda debe contar.""",
            },
        ]
    },
    # 29) Get-Help y descubrir cmdlets (principiante)
    {
        "messages": [
            {"role": "user", "content": "¿Cómo descubro qué cmdlet hace una cosa en PowerShell sin buscar en Google cada vez? Por ejemplo, «listar servicios», «convertir a base64», «leer un registro de Windows»."},
            {
                "role": "assistant",
                "content": r"""PowerShell está diseñado para descubrirse desde dentro. Tres herramientas: `Get-Command` para encontrar el cmdlet, `Get-Help` para aprender a usarlo y `Get-Member` para ver qué devuelve.

**1. Encontrar el cmdlet.** Los nombres siguen la forma `Verbo-Sustantivo` con un conjunto fijo de verbos (`Get`, `Set`, `New`, `Remove`, `Start`, `Stop`, `Convert`, `Export`, `Import`), así que buscas por sustantivo o por verbo con comodines:

```powershell
Get-Command -Noun Service              # Get-Service, Start-Service, Stop-Service, Restart-Service, ...
Get-Command -Verb Convert*             # ConvertTo-Json, ConvertFrom-Csv, ConvertTo-SecureString, ...
Get-Command *base64*                   # nada: no hay cmdlet; es un método .NET (abajo)
Get-Command -Noun Item*                # Get-Item, Get-ItemProperty, ... (así se lee el registro)
Get-Verb                               # la lista de verbos aprobados
```

Para tus tres ejemplos:

```powershell
Get-Service | Where-Object Status -eq Running

[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('hola'))      # aG9sYQ==
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('aG9sYQ=='))

Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -Name ProductName, CurrentBuild
```

El registro de Windows se expone como una unidad (`HKLM:`, `HKCU:`), así que los cmdlets de archivos (`Get-ChildItem`, `Get-ItemProperty`, `Set-ItemProperty`, `New-Item`) funcionan sobre él. Cuando no hay cmdlet, como con base64, está todo .NET a mano con la sintaxis `[Tipo]::Metodo()`; `[Convert] | Get-Member -Static` lista lo que ofrece.

**2. Aprender a usarlo.** `Get-Help` con los modificadores que importan:

```powershell
Get-Help Get-Service                   # sinopsis y sintaxis
Get-Help Get-Service -Examples         # ejemplos de uso; casi siempre lo que necesitas
Get-Help Get-Service -Parameter Name   # un parámetro concreto
Get-Help Get-Service -Full             # todo, incluidos tipos de entrada y salida
Get-Help Get-Service -Online           # abre la página de docs en el navegador
Get-Help about_Comparison_Operators    # temas conceptuales (about_*)
```

La ayuda local viene resumida; la primera vez ejecuta `Update-Help` (como administrador en Windows) para descargar la completa, o usa `-Online`. Las tres opciones de ayuda que se usan a diario son `-Examples`, `-Parameter` y `-Online`.

**3. Ver qué devuelve.** Antes de encadenar, mira las propiedades reales:

```powershell
Get-Service | Get-Member                          # tipo ServiceController, propiedades Status, Name, StartType...
Get-Service | Select-Object -First 1 | Format-List *   # todos los valores de uno
```

Lo que aparece en pantalla por defecto es solo un subconjunto formateado; `Get-Member` te enseña el resto (`DependentServices`, `StartType`, `CanStop`).

Dos ayudas más que aceleran todo:

- **Tabulador**: completa nombres de cmdlets, parámetros (`Get-Service -St<Tab>` → `-StartType`) y valores de `ValidateSet`. `Ctrl+Espacio` muestra todas las opciones a la vez.
- **`Show-Command Get-Service`** (Windows) abre un formulario con todos los parámetros para rellenar y copia el comando resultante; útil las primeras semanas.

Para módulos que no están cargados, `Find-Module -Name *Azure*` busca en la galería (`PSGallery`) e `Install-Module` instala; `Get-Command -Module Pester` lista lo que un módulo instalado aporta.

Prueba el flujo completo con algo nuevo: «¿cómo calculo un hash SHA256?» → `Get-Command *hash*` → `Get-FileHash` → `Get-Help Get-FileHash -Examples` → `Get-FileHash .\archivo.iso -Algorithm SHA256`. Tres comandos, sin salir de la terminal.""",
            },
        ]
    },
    # 30) PowerShell: Invoke-RestMethod, JSON, rutas (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Necesito un script PowerShell 7 que llame a una API REST con token, pagine los resultados, los filtre y los guarde en JSON, y que funcione igual en Windows y Linux. ¿Qué tengo que tener en cuenta?"},
            {
                "role": "assistant",
                "content": r"""`Invoke-RestMethod` hace la llamada **y** deserializa el JSON a objetos, así que el filtrado es `Where-Object` directo. Lo que hay que vigilar es la paginación, la profundidad al volver a serializar y las rutas.

```powershell
#!/usr/bin/env pwsh
#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BaseUrl,
    [Parameter(Mandatory)][string]$Token,
    [string]$OutFile = (Join-Path $PSScriptRoot 'issues.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$headers = @{
    Authorization = "Bearer $Token"
    Accept        = 'application/json'
}

$all = [System.Collections.Generic.List[object]]::new()
$url = "$BaseUrl/issues?state=open&per_page=100"

while ($url) {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -ResponseHeadersVariable respHeaders -RetryIntervalSec 2 -MaximumRetryCount 3
    $all.AddRange([object[]]$response)

    # Paginación por cabecera Link (estilo GitHub); si la API usa un cursor en el cuerpo, lee $response.next en su lugar
    $url = $null
    if ($respHeaders.ContainsKey('Link')) {
        $next = $respHeaders['Link'] -split ',' | Where-Object { $_ -match 'rel="next"' }
        if ($next -and $next -match '<([^>]+)>') { $url = $Matches[1] }
    }
    Write-Verbose "Acumulados $($all.Count) elementos"
}

$selected = $all |
    Where-Object { $_.labels.name -contains 'bug' -and -not $_.pull_request } |
    Select-Object number, title, state, @{ Name = 'labels'; Expression = { $_.labels.name } }, created_at

$selected | ConvertTo-Json -Depth 5 | Set-Content -Path $OutFile -Encoding utf8
Write-Output "Guardados $($selected.Count) elementos en $OutFile"
```

Lo que tiene en cuenta cada parte:

- **`Invoke-RestMethod` frente a `Invoke-WebRequest`**: el primero devuelve objetos ya parseados; el segundo devuelve la respuesta cruda (`StatusCode`, `Content`, `Headers`) y hay que hacer `ConvertFrom-Json` a mano. Para APIs JSON, el primero.
- **`-ResponseHeadersVariable`** (PS 7+) es la única forma de leer las cabeceras de la respuesta con `Invoke-RestMethod`; necesaria para la paginación por `Link`.
- **`-MaximumRetryCount` / `-RetryIntervalSec`** (PS 7+) reintentan ante 5xx y errores de red sin bucle propio. No reintentan 4xx: un 401 es un error terminante y se captura con `try/catch` si quieres un mensaje mejor (`$_.Exception.Response.StatusCode`).
- **`List[object]` + `AddRange`** en vez de `$all += $response`: añadir a un array de PowerShell copia el array entero cada vez; con cien páginas de cien elementos se nota.
- **`[object[]]$response`**: si una página trae **un solo elemento**, `Invoke-RestMethod` devuelve el objeto suelto, no un array de uno; el cast lo normaliza y `AddRange` no falla. Es la trampa más frecuente al paginar.
- **`-Depth 5` en `ConvertTo-Json`**: el valor por defecto es 2 y los niveles más profundos se convierten en cadenas inútiles sin error. Ajusta al nivel de anidamiento real; hasta 100.
- **`Join-Path` y `$PSScriptRoot`** para rutas: funcionan con `\` en Windows y `/` en Linux, y no dependen del directorio desde el que se ejecute.
- **`-Encoding utf8`**: en PS 7 ya es el valor por defecto (sin BOM), pero dejarlo explícito evita sorpresas si alguien lo ejecuta con Windows PowerShell 5.1, donde el valor por defecto era otro.

Para leer el archivo de vuelta conservando la estructura, `Get-Content $OutFile -Raw | ConvertFrom-Json` (con `-AsHashtable` si prefieres diccionarios a `PSCustomObject`, útil cuando las claves tienen caracteres raros o solo difieren en mayúsculas).

El token: no lo pongas en el script ni en el historial. Pásalo desde una variable de entorno (`-Token $env:API_TOKEN`) o, mejor, como `[securestring]` leído con `Read-Host -AsSecureString` y convertido solo en el momento de construir la cabecera.

Comprobación cruzada: ejecuta el script en Windows y en Linux contra la misma API y compara los archivos con `Compare-Object (Get-Content a.json) (Get-Content b.json)`; no debe devolver diferencias. Y con `-Verbose` verás cuántas páginas descargó, que debe cuadrar con el total que indique la API.""",
            },
        ]
    },
]
