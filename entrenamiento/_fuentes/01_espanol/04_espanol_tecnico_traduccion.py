"""Español: español técnico y traducción. 30 filas SFT (chatml).

Temas: traducción EN→ES de documentación técnica, mensajes de error (qué se traduce y qué
no: códigos, nombres de API, flags, logs), glosario (deploy, commit, merge, thread, race
condition…), cuándo mantener el anglicismo, commits y PR en español frente a inglés,
comentarios de código, comprensión de textos técnicos en inglés, localización de UI
(plurales, fechas, números, registro), falsos amigos, calcos sintácticos y ES→EN de un
informe.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Traducción EN→ES de documentación técnica, con notas del traductor.
    {
        "messages": [
            {
                "role": "system",
                "content": "Responde solo con la traducción y, después, una lista breve de notas del traductor.",
            },
            {
                "role": "user",
                "content": """Traduce al español este fragmento de nuestra documentación:

## Rate limits

Each API key is limited to 600 requests per minute. When you exceed the limit, the API responds with `429 Too Many Requests` and includes a `Retry-After` header indicating how many seconds to wait before retrying. Requests are counted per key, not per IP address, so distributing calls across multiple servers won't help. If you need a higher limit, contact support with your expected peak throughput. We recommend implementing exponential backoff with jitter rather than retrying immediately, as immediate retries are counted against your quota too.""",
            },
            {
                "role": "assistant",
                "content": """## Límites de peticiones

Cada clave de API admite un máximo de 600 peticiones por minuto. Si superas el límite, la API responde con `429 Too Many Requests` e incluye una cabecera `Retry-After` que indica cuántos segundos debes esperar antes de reintentar. Las peticiones se cuentan por clave, no por dirección IP, así que repartir las llamadas entre varios servidores no sirve de nada. Si necesitas un límite mayor, escribe a soporte indicando el volumen máximo de peticiones que prevés. Recomendamos reintentar con espera exponencial y una variación aleatoria (*exponential backoff with jitter*) en lugar de hacerlo de inmediato, porque los reintentos inmediatos también cuentan para tu cuota.

---

**Notas del traductor**

- `429 Too Many Requests` y `Retry-After` se mantienen en inglés: son el código de estado y la cabecera que el cliente recibe literalmente. Traducirlos impediría buscarlos en el código o en los logs.
- «Rate limits» → «Límites de peticiones». Evité el calco «límites de tasa», que no dice nada a quien no conoce el término inglés.
- «API key» → «clave de API». Comprueba que es el término que usa el resto de vuestra documentación y el panel de control; si la interfaz dice «API key», mantenlo igual en todas partes.
- «Peak throughput» → «volumen máximo de peticiones que prevés». Traduje por el sentido: «rendimiento pico» sería un calco poco claro.
- «Exponential backoff with jitter» → traducido, con el original entre paréntesis en esta primera aparición, porque es el término que el lector buscará en internet. En apariciones posteriores basta con «espera exponencial».
- Usé «tú». Si la documentación trata de «usted», cambia «superas», «debes», «necesitas» y «prevés».""",
            },
        ]
    },
    # 2) Mensajes de error de una API: qué se traduce y qué no.
    {
        "messages": [
            {
                "role": "user",
                "content": """Estamos localizando la app al español. El backend devuelve errores así y el frontend los muestra tal cual. ¿Qué traduzco y qué no?

```json
{"error": {"code": "CARD_DECLINED", "message": "Your card was declined.", "field": "card_number", "request_id": "req_8f3a2c", "docs": "https://docs.example.com/errors#card_declined"}}
```

También tenemos cosas como `Invalid value for 'email': must be a valid email address` y `Request timed out after 30000ms`.""",
            },
            {
                "role": "assistant",
                "content": """El problema de fondo no es qué traducir, sino que el frontend muestra al usuario un texto que fue escrito para desarrolladores. Separa las dos audiencias y la respuesta sale sola:

| Campo | ¿Traducir? | Por qué |
|---|---|---|
| `code` | **Nunca** | Es el contrato entre backend y frontend. El frontend decide qué mostrar a partir de él. |
| `message` | **No; no lo muestres** | Es para desarrolladores y logs. Se queda en inglés. |
| `field` | **Nunca** | Es un identificador. Sirve para marcar en rojo el campo; la etiqueta visible («Número de tarjeta») ya está traducida en el formulario. |
| `request_id` | **Nunca** | Muéstralo tal cual como «código de referencia» para que soporte pueda buscarlo. |
| `docs` | No | Es para desarrolladores. Si algún día tenéis documentación en español, cambia la URL, no el campo. |

El frontend traduce a partir de `code`:

```ts
const MENSAJES: Record<string, string> = {
  CARD_DECLINED: "Tu tarjeta fue rechazada. Prueba con otra o contacta con tu banco.",
  INVALID_EMAIL: "Escribe un correo electrónico válido.",
  REQUEST_TIMEOUT: "El servidor tardó demasiado en responder. Inténtalo de nuevo.",
};

const MENSAJE_GENERICO = "Algo salió mal. Inténtalo de nuevo en unos minutos.";

export function mensajeParaUsuario(code: string, requestId: string): string {
  const base = MENSAJES[code] ?? MENSAJE_GENERICO;
  return `${base} (Referencia: ${requestId})`;
}
```

Tres decisiones de ese código:

1. **Respaldo genérico para códigos desconocidos.** Cuando el backend añada un código nuevo antes de que exista su traducción, el usuario verá un mensaje en español, nunca el `message` en inglés.
2. **La referencia siempre visible.** Es lo que permite a soporte encontrar el error exacto en los logs sin que el usuario tenga que describirlo.
3. **Nada de traducir parseando el texto inglés** (por ejemplo, buscar «declined» en `message`). En cuanto alguien corrija una errata en el backend, la traducción se rompe sin avisar.

Tus otros dos casos:

- `Invalid value for 'email': must be a valid email address` no tiene código, así que hoy no puedes traducirlo bien. Pide al backend un código (`INVALID_EMAIL`) y el nombre del campo por separado. Al usuario no le muestres `'email'`: el campo ya está marcado en el formulario.
- `Request timed out after 30000ms`: los 30000 ms no le sirven al usuario. Mapéalo a un código de tiempo de espera y muestra el mensaje genérico de reintento. El valor exacto se queda en los logs, en inglés, que es donde lo buscará quien depure.

Regla para el equipo: **todo lo que lee una máquina o un desarrollador queda en inglés; todo lo que lee el usuario final se traduce, y se elige a partir de un código, nunca de un texto.**""",
            },
        ]
    },
    # 3) Usuario en inglés que pide la explicación de un traceback en español.
    {
        "messages": [
            {
                "role": "user",
                "content": """Can you explain this error in Spanish? I'm forwarding it to a junior on my team who's more comfortable in Spanish.

```
Traceback (most recent call last):
  File "/app/report.py", line 42, in <module>
    total = sum(row["amount"] for row in rows)
  File "/app/report.py", line 42, in <genexpr>
    total = sum(row["amount"] for row in rows)
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```""",
            },
            {
                "role": "assistant",
                "content": """Here it is in Spanish, ready to forward:

---

**Cómo leer la traza.** En Python, una traza se lee de abajo arriba: la última línea dice qué falló y las de encima, dónde. «Most recent call last» significa justamente eso: la llamada más reciente está al final.

**Qué dice el error.** `TypeError: unsupported operand type(s) for +: 'int' and 'str'` significa «tipos de operando no admitidos para `+`: un entero y una cadena». Python intentó sumar un número y un texto, y no sabe hacerlo.

**Por qué pasa en esa línea.** `sum()` empieza en `0` (un `int`) y le va sumando cada `row["amount"]`. Al menos uno de esos valores es un texto, por ejemplo `"12.50"` en lugar de `12.5`. El `<genexpr>` de la traza es la expresión generadora `row["amount"] for row in rows`: el error ocurre mientras se recorre.

Lo más probable es que los datos vengan de un CSV: `csv.DictReader` devuelve **todos** los valores como texto, así que falla con la primera fila. Si vienen de un JSON, puede que solo algunas filas traigan el importe entre comillas.

**Arreglo.** Convierte cada valor antes de sumar. Para dinero usa `Decimal`, no `float`, para no acumular errores de redondeo:

```python
from decimal import Decimal

total = sum((Decimal(row["amount"]) for row in rows), Decimal("0"))
```

El segundo argumento de `sum()` es el valor inicial; si se lo pasas, el generador necesita sus propios paréntesis, como arriba.

**Comprobación.** Con `rows = [{"amount": "12.50"}, {"amount": "7.25"}]`, `total` vale `Decimal('19.75')`.

**Atención a un caso típico en datos en español:** si algún importe viene como `"12,50"` (coma decimal), `Decimal` lanzará `decimal.InvalidOperation`. En ese caso hay que normalizar el formato antes de convertir, y conviene averiguar de dónde salen esos datos.

Un consejo para buscar errores: copia en el buscador el mensaje tal cual, en inglés, sin traducirlo. Así encontrarás muchas más respuestas.""",
            },
        ]
    },
    # 4) Multiturno: glosario EN→ES con criterio, y ampliación.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estamos armando un glosario para la documentación interna en español. ¿Cómo traducís deploy, commit, merge, pull request, thread, race condition, rollback, build, release y branch? Quiero criterio, no solo la lista.",
            },
            {
                "role": "assistant",
                "content": """El criterio en tres reglas, y después la tabla aplicándolas:

1. **Se traduce** si existe un término español asentado que el lector ya usa y que no cambia el significado.
2. **Se mantiene en inglés** si nombra un objeto concreto de una herramienta y la traducción no está asentada o confunde.
3. **Cuando el término es polisémico, se decide por acepción**, no por palabra.

| Inglés | Recomendación | Notas |
|---|---|---|
| deploy | **desplegar / despliegue** | Asentado. Evita «deployar» en documentación. |
| commit | **el commit / los commits**; verbo: «hacer commit» o «confirmar» | La interfaz de Git en español usa «confirmar» («Cambios a ser confirmados»), pero el sustantivo «commit» es universal. Elige un verbo y úsalo siempre. |
| merge | **fusionar / fusión** | Asentado; es lo que usa Git en español. |
| pull request | **el pull request (PR)** | Nombre de un objeto de GitHub. La documentación de GitHub en español lo traduce como «solicitud de incorporación de cambios», pero nadie lo dice así. En GitLab el objeto se llama *merge request*. |
| thread | **hilo** | Asentado (hilo de ejecución). |
| race condition | **condición de carrera** | Calco, pero totalmente asentado y transparente. |
| rollback | **revertir / reversión**; en bases de datos, «rollback» se acepta | «Revertir el despliegue» se entiende mejor que «hacer rollback del despliegue». |
| build | **compilación** cuando significa compilar; **build** cuando es el artefacto o el trabajo de CI | Polisémico: «la compilación falló» frente a «descarga el build de ayer». |
| release | **versión** (el artefacto), **lanzamiento** (el evento), **publicar** (el verbo) | «Release notes» → «notas de la versión». |
| branch | **rama** | Asentado. |

Dos columnas que conviene añadir al glosario y que casi nadie pone:

- **Género y plural** de los términos que se mantienen: *el* commit, *los* commits, *el* pull request, *el* build. Si no se fijan, la misma página acaba diciendo «la build» y «el build».
- **Formas a evitar en documentación** (aunque se usen al hablar): «mergear», «deployar», «pushear». Un glosario que solo dice qué usar no impide que se cuele lo que no.""",
            },
            {
                "role": "user",
                "content": "Buenísimo. ¿Y issue, backlog y staging?",
            },
            {
                "role": "assistant",
                "content": """Aplicando las mismas reglas:

| Inglés | Recomendación | Notas |
|---|---|---|
| issue | **incidencia** | Asentado en gestión de proyectos y es lo que usa la documentación de GitHub en español. Mantén «issue» solo si la herramienta que usáis muestra la interfaz en inglés y el texto se refiere al botón o la pestaña. |
| backlog | **el backlog** | Nombre de un objeto de Scrum. «Pila de producto» existe, pero es minoritario y obliga a traducir mentalmente. Las traducciones al español de la Guía de Scrum lo dejan en inglés. |
| staging | **preproducción** (el entorno); **staging** si es el nombre literal del entorno en la infraestructura | «Preproducción» es transparente y se usa mucho en España y Latinoamérica. Pero si el entorno se llama `staging` en las URL o en los nombres de los clústeres, escribe `staging` con formato de código cuando hables de ese recurso concreto. |

Fíjate en que *staging* aplica la regla 3 de otra forma: el concepto se traduce, pero el **nombre propio de un recurso** (`staging.example.com`, el *namespace* `staging`) nunca, igual que no traducirías el nombre de una variable.""",
            },
        ]
    },
    # 5) Cuándo mantener el anglicismo.
    {
        "messages": [
            {
                "role": "user",
                "content": "En la documentación, ¿pongo «framework» o «marco de trabajo»? ¿Y middleware, endpoint, hook? Mi jefa quiere todo en español pero a mí me suena rarísimo.",
            },
            {
                "role": "assistant",
                "content": """Ni todo en español ni todo en inglés: decide término a término con cuatro preguntas.

1. **¿Existe un equivalente que tu lector use de verdad?** No basta con que exista en un diccionario.
2. **¿Es el nombre oficial de algo en una herramienta?** Si la API, la interfaz o la documentación oficial lo llaman así, traducirlo rompe la correspondencia.
3. **¿El lector lo va a buscar?** Si va a copiar el término en un buscador o en la documentación oficial, necesita la forma inglesa.
4. **¿La traducción es precisa?** Si introduce ambigüedad, pierde.

Aplicadas a tus cuatro:

- **framework** → mantenlo. «Marco de trabajo» (la propuesta habitual de la Fundéu, junto a «entorno de trabajo») es correcto, pero en documentación técnica suena a traducción y se confunde con el sentido general de «marco de trabajo» (una metodología). Si tu jefa insiste, úsalo en la primera aparición: «un *framework* (marco de trabajo) como Django».
- **middleware** → mantenlo. No hay equivalente asentado: «software intermedio» no lo usa nadie y no se puede buscar.
- **endpoint** → aquí sí hay una opción razonable. La documentación en español de Microsoft usa «punto de conexión», y se entiende. Si vuestra documentación habla mucho de APIs, «endpoint» sigue siendo más reconocible; elige uno y no alternes.
- **hook** → mantenlo cuando hablas de React: «Hooks» es el nombre oficial de la API, y la documentación de React en español no lo traduce. Traducirlo como «gancho» haría que nadie encontrara `useEffect` en la documentación oficial.

**Cómo convencer a tu jefa.** Su objetivo (que la documentación sea española de verdad) es bueno, y se cumple mejor con estas tres medidas que traduciéndolo todo:

1. Un glosario con la decisión de cada término, para que se mantenga igual en todos los documentos.
2. Explicar el término en su primera aparición en cada página.
3. Toda la sintaxis en español: verbos, conectores y explicaciones. Una frase como «el middleware valida el token antes de llegar al endpoint» es española; lo que la haría inglesa sería el orden y los calcos, no tres sustantivos técnicos.

Un detalle de forma: la norma pide cursiva para los extranjerismos no adaptados (*framework*). En documentación técnica muchos equipos la omiten para los términos de uso diario, porque con formato de código, negritas y cursivas el texto se vuelve ilegible. Cualquiera de las dos opciones vale si se aplica de forma consistente; anótalo en el glosario.""",
            },
        ]
    },
    # 6) Multiturno: commits y PR en español o en inglés; luego un mensaje concreto.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Somos un equipo entre Argentina y México y el código está en inglés. ¿Los mensajes de commit y las descripciones de PR los escribimos en español o en inglés? Hay discusión en el equipo.",
            },
            {
                "role": "assistant",
                "content": """Decide por quién va a leer el historial, no por gusto. Las preguntas que zanjan la discusión:

| Pregunta | Si la respuesta es sí → |
|---|---|
| ¿El repositorio es o puede ser *open source*? | Inglés |
| ¿Hay o habrá personas que no lean español (otra filial, un proveedor externo, auditores)? | Inglés |
| ¿Usáis herramientas que generan changelogs públicos a partir de los commits? | Inglés para el asunto del commit |
| ¿Todo el equipo y quienes heredarán el código hablan español, y el repositorio no saldrá de la empresa? | Español sin problema |

Si ninguna de las tres primeras aplica, el español es perfectamente profesional. Hay un argumento a su favor que suele olvidarse: una descripción de PR es una discusión, y en una discusión el matiz importa. Escribir en el idioma en el que piensas reduce malentendidos.

Hay un reparto intermedio que funciona bien en muchos equipos: **asunto del commit en inglés** (es corto, formulaico y viaja con el código) y **descripción de PR en español** (es donde va el razonamiento).

Sea cual sea la decisión:

- **Escríbela en `CONTRIBUTING.md`.** La discusión se repetirá con cada persona nueva si no está escrita.
- **Si usáis Conventional Commits**, el tipo y el ámbito se quedan en inglés aunque el resto sea español, porque las herramientas los procesan: `fix(pagos): evita el doble cobro al reintentar`.
- **Fijad un tiempo verbal.** En español conviven el presente («corrige el cálculo») y el infinitivo («corregir el cálculo»). Cualquiera vale; mezclarlos en el historial se nota.""",
            },
            {
                "role": "user",
                "content": "Vamos con todo en español. Escribime el mensaje de commit para esto: agregamos un lock con Redis (SET NX con expiración de 30 s) al job que manda las facturas, porque cuando corrían dos instancias a la vez se mandaban correos duplicados.",
            },
            {
                "role": "assistant",
                "content": """```text
fix(facturas): evita envíos duplicados con un candado en Redis

Si dos instancias del job de facturas arrancaban a la vez, ambas
enviaban los mismos correos. Ahora cada ejecución adquiere un candado
en Redis (SET NX con expiración de 30 s) antes de empezar; si otra
instancia ya lo tiene, termina sin enviar nada.
```

- **Asunto:** 62 caracteres, por debajo del límite habitual de 72, en presente («evita») según lo que acordasteis. Dice el efecto, no la técnica: quien lea el historial busca «duplicados», no «SET NX».
- **Cuerpo:** primero el síntoma que motivó el cambio y después cómo se resuelve. Es lo que `git blame` no puede explicar por sí solo dentro de un año.
- **`SET NX` sin traducir:** es el comando de Redis. Igual que «job», que es como lo llamáis en el equipo; mantenerlo facilita buscar en el historial.

Una cosa que revisaría antes de fusionar: **¿el job tarda siempre menos de 30 segundos?** Si una ejecución dura más, el candado caduca a mitad, otra instancia lo adquiere y vuelven los duplicados, ahora de forma intermitente y mucho más difícil de diagnosticar. Si la duración puede superar los 30 s, alarga la expiración por encima del peor caso o renueva el candado periódicamente mientras el job sigue vivo. Y libéralo solo si sigue siendo tuyo: guarda un valor único al adquirirlo y compáralo antes de borrarlo, para no liberar el candado que ya adquirió otra instancia.""",
            },
        ]
    },
    # 7) Descripción de PR en español a partir de una lista de cambios.
    {
        "messages": [
            {
                "role": "user",
                "content": "Escríbeme la descripción del PR en español. Cambios: migré la subida de avatares de disco local a S3 con URLs prefirmadas; el frontend ahora sube directo a S3; el backend solo genera la URL (expira en 5 min) y después valida que el objeto existe; agregué un script para migrar los avatares existentes; falta borrar la carpeta local después de verificar en producción.",
            },
            {
                "role": "assistant",
                "content": """```markdown
## Subida de avatares a S3 con URLs prefirmadas

### Qué cambia
- El frontend sube el avatar directamente a S3 usando una URL prefirmada.
- El backend ya no recibe el archivo: genera la URL prefirmada (válida 5 minutos) y, cuando el frontend confirma la subida, comprueba que el objeto existe en S3 antes de asociarlo al usuario.
- Nuevo script `migrar_avatares` para copiar a S3 los avatares que hoy están en disco local.

### Por qué
Guardar en disco local obliga a que cada avatar viva en una sola instancia del backend y hace que las subidas pasen por nuestros servidores. Con S3, los archivos no dependen de ninguna instancia y el backend no procesa el tráfico de subida.

### Cómo probarlo
1. Sube un avatar desde el perfil y comprueba que aparece el objeto en el bucket.
2. Intenta confirmar una subida con una clave que no exista en S3: el backend debe rechazarla.
3. Espera más de 5 minutos con una URL generada e intenta usarla: S3 debe responder con un error de acceso.
4. Ejecuta el script en local contra un bucket de pruebas y verifica que los avatares existentes se ven igual.

### Despliegue
1. Desplegar este PR.
2. Ejecutar `migrar_avatares` en producción.
3. Verificar una muestra de perfiles.
4. Borrar la carpeta local en un PR aparte, cuando la verificación esté completa.

### Fuera de alcance
- El borrado de la carpeta local (ver paso 4).
```

Notas:

- **Asumí el «por qué».** Tu lista dice qué cambiaste, pero no la motivación; puse la habitual (varias instancias, tráfico de subida por el backend). Corrígela si fue otra: es la sección que más ayuda al revisor a juzgar si la solución encaja.
- **El borrado de la carpeta va como paso de despliegue y como fuera de alcance**, para que nadie apruebe el PR creyendo que ya se puede borrar.
- **Términos:** «URL prefirmada» es la traducción habitual de *presigned URL*; «bucket» se mantiene porque es el nombre del recurso en S3.

Un punto que un revisor atento va a preguntar, y que conviene resolver antes: **¿la URL limita el tamaño y el tipo del archivo?** Una URL prefirmada para `PUT` no permite fijar un tamaño máximo: cualquiera que la obtenga puede subir un archivo de varios gigas. Si eso importa, la alternativa es un *presigned POST* con la condición `content-length-range` en la política, y validar el `Content-Type` al confirmar. Si ya lo tienes resuelto, añade una línea en «Qué cambia» para que no te lo pregunten.""",
            },
        ]
    },
    # 8) Traducir comentarios y docstrings de un módulo Python sin tocar el código.
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres traductor técnico EN→ES. Mantienes en inglés los identificadores, el código y las cadenas que procesa el programa; traduces comentarios y docstrings.",
            },
            {
                "role": "user",
                "content": """Traduce los comentarios y docstrings de este módulo; el equipo nuevo no lee bien inglés.

```python
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(fn: Callable[[], T], attempts: int = 3, base_delay: float = 0.5) -> T:
    '''Call fn until it succeeds or attempts run out.

    Waits base_delay * 2**n seconds between attempts (exponential backoff).
    Re-raises the last exception if every attempt fails.
    '''
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # broad on purpose: the caller decides what is retryable
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * 2**attempt)
    # attempts == 0 skips the loop entirely; guard against returning None silently
    if last_error is None:
        raise ValueError("attempts must be >= 1")
    raise last_error
```""",
            },
            {
                "role": "assistant",
                "content": """```python
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(fn: Callable[[], T], attempts: int = 3, base_delay: float = 0.5) -> T:
    '''Llama a fn hasta que tenga éxito o se agoten los intentos.

    Entre intentos espera base_delay * 2**n segundos (espera exponencial).
    Si todos los intentos fallan, vuelve a lanzar la última excepción.
    '''
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # amplio a propósito: quien llama decide qué errores merecen reintento
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * 2**attempt)
    # con attempts == 0 el bucle no se ejecuta; evita devolver None sin avisar
    if last_error is None:
        raise ValueError("attempts must be >= 1")
    raise last_error
```

Notas del traductor:

- **Sin cambios en el código.** Identificadores (`retry`, `attempts`, `base_delay`, `last_error`) y fórmulas (`2**n`) quedan igual; en la docstring, `fn` y `base_delay` son nombres de parámetros, así que no se traducen.
- **«Retryable» → «qué errores merecen reintento».** «Reintentable» se entiende, pero no está asentado y la paráfrasis es igual de corta.
- **«Exponential backoff» → «espera exponencial».** Sin el original entre paréntesis porque aquí la fórmula de la línea ya lo explica; en documentación para usuarios sí lo añadiría.
- **El mensaje de `ValueError` queda en inglés.** Aparece en trazas y logs, donde el resto del texto de Python está en inglés y donde alguien lo buscará tal cual. Ningún código lo compara, así que traducirlo no rompería nada; es una decisión de convención del equipo.

Una observación sobre el código, aunque no la pediste: la validación de `attempts` está al final, así que el error solo se detecta tras recorrer un bucle vacío. Moverla al principio de la función (`if attempts < 1: raise ValueError(...)`) haría que el comentario sobrara. No lo cambié porque el encargo era traducir.""",
            },
        ]
    },
    # 9) Multiturno: comprensión de un texto técnico en inglés con preguntas en español.
    {
        "messages": [
            {
                "role": "user",
                "content": """Leí esto en la documentación de un proveedor de pagos y tengo dudas:

«Idempotency keys let clients safely retry requests that create resources. The client generates a unique key (we recommend a UUIDv4) and sends it in the Idempotency-Key header. The first time the server sees a key, it processes the request and stores the response for 24 hours. Any subsequent request with the same key returns the stored response without re-executing the operation, even if the first request is still in progress, in which case the server responds with 409 Conflict. Keys are scoped to the API key that sent them. Reusing a key with a different request body results in a 422 error. GET and DELETE requests are idempotent by definition and ignore this header.»

1. ¿Qué pasa si reintento con la misma clave mientras la primera petición todavía se está procesando?
2. Si mando la misma clave desde dos cuentas distintas, ¿chocan?
3. ¿Puedo usar como clave el ID del pedido de mi base de datos?
4. ¿Tengo que mandar la cabecera en un DELETE?""",
            },
            {
                "role": "assistant",
                "content": """**1. Recibes un `409 Conflict`.** Ojo, porque esa frase del texto es ambigua: dice que una petición repetida «devuelve la respuesta guardada… incluso si la primera sigue en curso, en cuyo caso responde 409». Mientras la primera no ha terminado todavía no hay respuesta guardada, así que la lectura coherente es: si la primera terminó, recibes su respuesta; si sigue en curso, recibes 409. En ningún caso se ejecuta la operación dos veces, que es lo que importa.

**2. No chocan.** «Keys are scoped to the API key that sent them»: cada clave de idempotencia se interpreta dentro de la API key que la envió. La misma clave en dos cuentas son dos claves distintas.

**3. Depende, y es la pregunta con más trampa.** El texto recomienda UUIDv4, pero no lo exige. El ID del pedido sirve si se cumplen dos condiciones:

- **Una operación por pedido.** Si sobre el mismo pedido haces dos cobros distintos (por ejemplo, un cobro parcial y otro final), el segundo usaría la misma clave con otro cuerpo y recibirías un **422**, o peor, si el cuerpo coincide, recibirías la respuesta del primero y el segundo cobro nunca se haría.
- **Reintentos dentro de las 24 horas.** Pasado ese plazo, el servidor olvida la clave: un reintento ejecutaría la operación de nuevo.

Si no puedes garantizar las dos cosas, usa un UUID generado por operación y guárdalo junto al pedido para reutilizarlo en los reintentos. Tienes la misma trazabilidad sin las trampas.

**4. No hace falta.** GET y DELETE ignoran la cabecera porque ya son idempotentes: borrar dos veces el mismo recurso deja el mismo estado que borrarlo una. Enviarla no causa ningún error, simplemente no tiene efecto.

Un detalle del texto que no preguntaste, pero que importa: «stores the response» significa que, si la primera petición **falló** con un error, los reintentos con la misma clave devolverán ese mismo error guardado. Para reintentar de verdad una operación fallida hace falta una clave nueva; la documentación del proveedor debería aclarar qué errores se guardan.""",
            },
            {
                "role": "user",
                "content": "Sobre la 1: ¿cómo debería reaccionar mi cliente al 409?",
            },
            {
                "role": "assistant",
                "content": """Esperar y repetir **con la misma clave**, nunca con una nueva. Una clave nueva haría que el servidor tratara el reintento como otra operación: es exactamente el doble cobro que la clave evita.

Asumo Python con `httpx`:

```python
import time
import uuid

import httpx


def crear_pago(cliente: httpx.Client, cuerpo: dict, intentos: int = 5) -> httpx.Response:
    clave = str(uuid.uuid4())  # una sola clave para todos los reintentos de esta operación
    for intento in range(intentos):
        try:
            resp = cliente.post("/payments", json=cuerpo, headers={"Idempotency-Key": clave})
        except httpx.TransportError:
            time.sleep(0.5 * 2**intento)  # sin respuesta: no sabemos si se procesó, se reintenta con la misma clave
            continue
        if resp.status_code != 409:
            return resp
        time.sleep(0.5 * 2**intento)  # la primera petición sigue en curso: esperar y repetir
    raise TimeoutError(f"sin respuesta definitiva tras {intentos} intentos; clave {clave}")
```

Por qué está escrito así:

- **La clave se genera una vez, fuera del bucle.** Es el error más habitual: generarla dentro del bucle anula toda la protección.
- **También se reintentan los errores de red.** Es el caso para el que existen estas claves: si se corta la conexión, no sabes si el pago se hizo, y reintentar con la misma clave es seguro.
- **Un 422 no se reintenta.** Significa que tu cliente mandó otro cuerpo con la misma clave, es decir, un error de programación. Repetirlo daría el mismo resultado.
- **La clave va en el mensaje de error final.** Si se agotan los intentos, con ella puedes consultar al proveedor qué pasó con la operación o reintentarla más tarde, dentro de las 24 horas, sin riesgo de duplicarla.

Comprobación mental: si el primer `post` se corta por la red pero el servidor sí lo procesó, el segundo intento devuelve la respuesta guardada (o 409 si aún no terminó) y el pago se cobra una sola vez.""",
            },
        ]
    },
    # 10) Multiturno: plurales con ICU MessageFormat y el caso del cero.
    {
        "messages": [
            {
                "role": "user",
                "content": "En la app tenemos strings como `${n} archivo(s) eliminado(s)`. Queremos hacerlo bien en español con ICU MessageFormat. ¿Cómo sería?",
            },
            {
                "role": "assistant",
                "content": """En ICU, cada idioma define sus categorías de plural y el mensaje da una forma para cada una:

```text
{count, plural,
  one {# archivo eliminado}
  other {# archivos eliminados}
}
```

`#` se sustituye por el número formateado según el idioma. Con FormatJS en TypeScript:

```ts
import { IntlMessageFormat } from "intl-messageformat";

const mensaje = new IntlMessageFormat(
  "{count, plural, one {# archivo eliminado} other {# archivos eliminados}}",
  "es",
);

mensaje.format({ count: 1 });     // "1 archivo eliminado"
mensaje.format({ count: 3 });     // "3 archivos eliminados"
mensaje.format({ count: 12345 }); // "12.345 archivos eliminados"
```

Detalles del español que conviene saber:

- **También concuerda el participio**, no solo el sustantivo: «eliminado/eliminados». Por eso cada rama lleva la frase completa, no solo la palabra que cambia.
- **El 0 y los decimales caen en `other`**: «0 archivos eliminados», «1,5 GB liberados». Es lo gramaticalmente correcto.
- **En versiones recientes de CLDR, el español tiene una tercera categoría, `many`**, para los millones exactos: «1.000.000 de archivos», con «de». Si no la defines, ICU usa `other`, así que el mensaje anterior sigue funcionando; añádela solo si esas cifras son realistas en tu app.
- **El género** también puede cambiar la frase: «carpeta eliminada». Si el sustantivo es variable, necesitas otro mensaje o un `select` por género, no un plural.

Por qué no `archivo(s)` ni un `n === 1 ? … : …` en el código:

- `archivo(s)` se ve descuidado y los lectores de pantalla lo leen literalmente.
- El ternario funciona en español e inglés, pero mete la gramática en el código. En polaco o ruso hay tres o cuatro formas según el número, y en árabe seis; con ICU, quien traduce añade las ramas en el archivo de traducción sin tocar el código.""",
            },
            {
                "role": "user",
                "content": "¿Y si con 0 quiero que diga «No se eliminó ningún archivo»?",
            },
            {
                "role": "assistant",
                "content": """Usa una coincidencia exacta, `=0`, que tiene prioridad sobre las categorías:

```text
{count, plural,
  =0 {No se eliminó ningún archivo}
  one {Se eliminó # archivo}
  other {Se eliminaron # archivos}
}
```

Resultados: 0 → «No se eliminó ningún archivo»; 1 → «Se eliminó 1 archivo»; 7 → «Se eliminaron 7 archivos».

Fíjate en que reescribí las tres ramas, no solo la del cero. Al pasar a «se eliminó / se eliminaron», el verbo también concuerda con el número, así que cada rama tiene que ser una oración completa. Mezclar «No se eliminó ningún archivo» con «3 archivos eliminados» funcionaría, pero la interfaz sonaría inconsistente.

`=1` frente a `one`: si quieres el texto «Se eliminó un archivo», con la palabra «un», usa `=1 {Se eliminó un archivo}`. Para todo lo demás, deja `one` con `#`. La diferencia importa al traducir a otros idiomas: en ruso, por ejemplo, la categoría `one` incluye también el 21, el 31, etc., así que una rama `one` con «un» literal sería incorrecta allí. `=1` siempre es exactamente uno.

Comprobación rápida en un test (con Vitest o Jest):

```ts
const mensaje = new IntlMessageFormat(
  "{count, plural, =0 {No se eliminó ningún archivo} one {Se eliminó # archivo} other {Se eliminaron # archivos}}",
  "es",
);

const casos: Array<[number, string]> = [
  [0, "No se eliminó ningún archivo"],
  [1, "Se eliminó 1 archivo"],
  [2, "Se eliminaron 2 archivos"],
];
for (const [count, esperado] of casos) {
  expect(mensaje.format({ count })).toBe(esperado);
}
```

Añade el 0, el 1 y el 2 a los tests de cada mensaje plural: son los tres valores en los que suelen aparecer los errores.""",
            },
        ]
    },
    # 11) Fechas, números y moneda para es-ES y es-MX con Intl.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Nuestra app de facturación sale en España y México. Ahora mismo tenemos `toFixed(2)` y fechas `MM/DD/YYYY` puestas a mano en el frontend. ¿Cómo lo hago bien?",
            },
            {
                "role": "assistant",
                "content": r"""Deja de construir los formatos a mano y usa `Intl`, que ya conoce las convenciones de cada país. Tu formato actual, además, es un error grave para los dos mercados: en España y en México `03/04/2026` se lee como 3 de abril, no como 4 de marzo.

**Fechas**

```ts
const fecha = new Date(Date.UTC(2026, 9, 20, 15, 30)); // 20 de octubre de 2026, 15:30 UTC

new Intl.DateTimeFormat("es-ES", { dateStyle: "short", timeZone: "Europe/Madrid" }).format(fecha);
// "20/10/26"

new Intl.DateTimeFormat("es-MX", { dateStyle: "long", timeZone: "America/Mexico_City" }).format(fecha);
// "20 de octubre de 2026"
```

Pasa siempre `timeZone`: sin él se usa la zona del navegador, y una factura emitida a las 23:30 en Madrid puede aparecer con fecha del día siguiente o del anterior según quién la mire.

**Números y moneda**

```ts
new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(1234567.5);
// "1.234.567,50 €"

new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(1234567.5);
// "$1,234,567.50"
```

Lo que cambia entre los dos países: en España el decimal es coma y los miles van con punto; en México es al revés, como en Estados Unidos. Y un detalle que sorprende: con `es-ES`, los números de cuatro cifras no se agrupan (`1234,5`, no `1.234,5`), porque así lo define la norma para el español de España.

**Cinco reglas que evitan los errores típicos**

1. **El idioma decide el formato; el dato decide la moneda.** Una factura en euros vista por un usuario de México se formatea con `currency: "EUR"` y el locale `es-MX`. No derives la moneda del idioma.
2. **`Intl` es solo para mostrar.** Para calcular importes usa céntimos enteros o una biblioteca decimal; `toFixed(2)` sobre un `float` redondea mal en casos como `1.005`.
3. **Guarda fechas en UTC o ISO 8601 y formatea solo al mostrar.** Nunca guardes la cadena ya formateada.
4. **`Intl` no interpreta lo que escribe el usuario.** Si alguien en España escribe `1.234,50` en un campo de importe, necesitas un parseo que conozca el locale, o un campo numérico que no acepte separadores de miles.
5. **Ojo en los tests:** `Intl` usa espacios de no separación (U+00A0) en algunos formatos, como el que hay entre `50` y `€`. Comparar con una cadena escrita con un espacio normal falla aunque se vea idéntica. Normaliza antes de comparar:

```ts
const texto = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(1234567.5);
expect(texto.replace(/ /g, " ")).toBe("1.234.567,50 €");
```

Crea los formateadores una vez y reutilízalos (por ejemplo, uno por locale y moneda): construir un `Intl.NumberFormat` en cada render de una tabla de mil filas se nota.""",
            },
        ]
    },
    # 12) Multiturno: traducción ES→EN de un informe de incidente y versión corta para Slack.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tradúceme al inglés este informe para el equipo de la casa matriz: «Resumen del incidente del 14 de octubre. El martes 14, entre las 9:10 y las 10:25 (hora de Ciudad de México), el servicio de facturación electrónica no pudo timbrar facturas. Afectó a unos 340 clientes, que no pudieron emitir CFDI durante ese periodo. La causa fue la caducidad del certificado que usamos para autenticarnos con el PAC; la alerta de caducidad existía, pero llegaba a un buzón que nadie revisa desde que se fue la persona responsable. Renovamos el certificado y el servicio se recuperó a las 10:25. Las facturas pendientes se timbraron automáticamente en la hora siguiente. Acciones: mover las alertas de certificados al canal de guardia (hecho), hacer un inventario de todos los certificados con fecha de caducidad y responsable (en curso, fecha límite: 31 de octubre) y revisar cada trimestre los buzones de alertas.»",
            },
            {
                "role": "assistant",
                "content": """**Incident summary: October 14**

On Tuesday, October 14, from 9:10 to 10:25 Mexico City time (15:10–16:25 UTC), our e-invoicing service was unable to certify invoices with the tax authority's system. About 340 customers could not issue CFDIs (Mexico's mandatory electronic invoices) during that window.

**Cause.** The certificate we use to authenticate with our PAC (the authorized provider that certifies invoices on behalf of the tax authority) expired. An expiry alert existed, but it was sent to an inbox that had not been monitored since its owner left the company.

**Resolution.** We renewed the certificate and service was restored at 10:25. Invoices queued during the outage were certified automatically within the following hour.

**Action items**
- Route certificate alerts to the on-call channel. *Done.*
- Inventory all certificates with expiry date and owner. *In progress, due October 31.*
- Review alert inboxes quarterly.

---

Notas de traducción:

- **«Timbrar» → «certify».** Es el término mexicano para que un PAC valide la factura ante el SAT; no tiene equivalente directo en inglés. Usé «certify» y expliqué una vez qué es un CFDI y qué es un PAC, porque en la casa matriz probablemente no lo sepan. Mantuve las siglas porque son las que verán en cualquier otro documento sobre facturación en México.
- **Añadí la hora en UTC.** Ciudad de México está en UTC−6 todo el año desde que México eliminó el horario de verano en 2022. Para un equipo en otro huso horario, la hora local sola obliga a hacer la cuenta.
- **«Nadie revisa desde que se fue la persona responsable» → «had not been monitored since its owner left the company».** Lo formulé como un fallo del proceso, no de una persona, que es el tono habitual de estos informes en inglés (*blameless*). El hecho que se transmite es el mismo.
- **«Fecha límite» → «due».** Es la forma estándar en listas de acciones.""",
            },
            {
                "role": "user",
                "content": "Perfecto. Ahora una versión corta para Slack, en inglés y más informal.",
            },
            {
                "role": "assistant",
                "content": """> **Incident recap, Oct 14:** e-invoicing was down for 75 min (9:10–10:25 CDMX / 15:10–16:25 UTC). ~340 customers couldn't issue invoices. Cause: an expired PAC certificate; the expiry alert was going to an unmonitored inbox. Renewed, and the backlog cleared automatically within the hour.
>
> Follow-ups: cert alerts now go to on-call ✅, full cert inventory with owners by Oct 31, quarterly review of alert inboxes.

Cambios respecto al informe:

- **Duración explícita (75 min).** En Slack se lee en diagonal; «75 min» se entiende antes que un rango de horas. Mantuve el rango para quien necesite cruzarlo con sus métricas.
- **Fuera la explicación de CFDI y PAC.** Quien quiera detalle tiene el informe completo; enlázalo debajo del mensaje.
- **«Cert», «backlog cleared», «follow-ups»**: registro de chat, pero sin abreviaturas que alguien de otro equipo no entienda.""",
            },
        ]
    },
    # 13) Falsos amigos y calcos léxicos en documentación técnica.
    {
        "messages": [
            {
                "role": "user",
                "content": "Revisando traducciones de la documentación encontré estas palabras: «eventualmente», «actualmente» (traduciendo «actually»), «librería», «deprecado», «soportar», «asumir» y «resolver». ¿Cuáles están mal?",
            },
            {
                "role": "assistant",
                "content": """Cuatro son errores claros, una es discutible y una está bien. Y en una de ellas hay una excepción asentada.

| En el texto | Inglés | Problema | Usa |
|---|---|---|---|
| eventualmente | eventually | **Falso amigo.** En español significa «quizá, ocasionalmente», no «al final». «El nodo eventualmente se recupera» dice que *a lo mejor* se recupera. | finalmente, con el tiempo, tarde o temprano |
| actualmente | actually | **Falso amigo.** «Actualmente» es «en este momento». | en realidad, de hecho |
| librería | library | **Calco.** Una librería vende libros; la colección de código es una biblioteca. En la conversación está muy extendido, pero en documentación conviene evitarlo. | biblioteca |
| deprecado | deprecated | **Calco.** «Deprecar» existe en español, pero significa «rogar, suplicar». | obsoleto, en desuso, desaconsejado |
| soportar | support | **Calco.** «Soportar» es aguantar. «La API soporta JSON» suena a que lo tolera con esfuerzo. | admitir, ser compatible con, tener soporte para |
| asumir | assume | **Discutible.** Con el sentido de «suponer» está tan extendido que pocos lo consideran ya un error, pero en documentación formal sigue siendo más preciso otro verbo. | suponer, dar por hecho, partir de |
| resolver | resolve | **Correcto.** «Resolver un nombre de dominio» o «la promesa se resuelve» son usos asentados en español técnico. | — |

**La excepción:** *eventual consistency* se traduce como «consistencia eventual», a pesar del falso amigo. Es el término asentado y el que el lector buscará. Mantenlo, y si el público no es especialista explícalo en la primera aparición: «consistencia eventual (los datos acaban siendo coherentes en todas las réplicas, pero no al instante)».

Con «deprecated» hay además un matiz de significado: no quiere decir que ya no funcione, sino que **sigue funcionando** pero se desaconseja y se eliminará más adelante. «Obsoleto» puede sonar a «ya no funciona», así que en el glosario conviene definirlo: «obsoleto: sigue funcionando, pero se eliminará en una versión futura».

Ejemplo con todas las correcciones juntas:

- Antes: «Actualmente, esta librería soporta HTTP/2; la API antigua está deprecada y eventualmente será eliminada».
- Después: «En realidad, esta biblioteca admite HTTP/2; la API antigua está obsoleta y se eliminará en una versión futura».

Si la documentación es grande, busca estas palabras en todo el repositorio: suelen repetirse en muchas páginas, porque cada traductor copia el término que vio en la anterior.""",
            },
        ]
    },
    # 14) Mensajes de una CLI con flags, comandos y marcadores de formato (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que traducir estos mensajes de nuestra CLI: «Use --force to overwrite existing files.», «Run `mytool init` first.», «Found %d issues in %s.» y «Press Ctrl+C to cancel.» ¿Hay algo que no deba tocar?",
            },
            {
                "role": "assistant",
                "content": """Sí: todo lo que el usuario tiene que escribir o pulsar tal cual, y los marcadores que el programa sustituye.

| Original | Traducción | Qué no se toca |
|---|---|---|
| Use --force to overwrite existing files. | Usa --force para sobrescribir los archivos existentes. | `--force`: es lo que el usuario escribe. Si lo traduces, el comando falla. |
| Run `mytool init` first. | Ejecuta primero `mytool init`. | El comando completo. |
| Found %d issues in %s. | Se encontraron %d problemas en %s. | `%d` y `%s`: el programa los sustituye por un número y un texto. Si desaparecen o cambian, el programa falla o muestra basura. |
| Press Ctrl+C to cancel. | Pulsa Ctrl+C para cancelar. | `Ctrl+C`: es el nombre de la tecla tal como aparece en el teclado. |

Tres detalles más:

1. **El tercer mensaje tiene un problema que no se ve en inglés.** Con `%d = 1` saldría «Se encontraron 1 problemas». En inglés pasa lo mismo («Found 1 issues»), pero tradúcelo bien: si la CLI usa `gettext`, ese mensaje necesita formas de plural (`ngettext`) para que quien traduce escriba «Se encontró %d problema» y «Se encontraron %d problemas» por separado. Avisa a quien mantiene el código; no se arregla solo desde la traducción.
2. **El orden de los marcadores.** Aquí el español conserva el orden (número, luego archivo), pero si alguna traducción necesita invertirlo, con `%d`/`%s` no se puede: hacen falta marcadores con posición o con nombre. Conviene saberlo antes de que aparezca el primer caso.
3. **Ortografía y registro.** «Sobrescribir» es la forma que prefiere la RAE (aunque «sobreescribir» también se admite). Usé «tú» («usa», «ejecuta», «pulsa»), que es lo habitual en herramientas de terminal; si el resto de vuestros textos usa «usted», cambia los imperativos en todos los mensajes por igual.

Comprobación antes de entregar: cuenta que cada mensaje traducido tenga los mismos marcadores (`%d`, `%s`), flags y comandos que el original. Si usáis `gettext`, `msgfmt --check` detecta automáticamente los marcadores de formato que no coinciden.""",
            },
        ]
    },
    # 15) Registro en la interfaz (tú, usted, vos) para varios países; system rioplatense.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "Estamos traduciendo la app (es una fintech) para Argentina, México y España. ¿Usamos tú, usted o vos? ¿Hacemos una versión por país o una sola?",
            },
            {
                "role": "assistant",
                "content": """Una base neutra con ajustes por país. Ni una sola versión para todos ni tres traducciones completas.

**Por qué no una sola versión.** En Argentina, una app que te trata de «tú» suena a traducida de afuera: el voseo es la norma en las apps locales, incluidos bancos y billeteras. Y en España, «computadora» o «celular» suenan igual de ajenos que «ordenador» o «móvil» en México.

**Por qué no tres traducciones completas.** El 80-90 % de los textos son idénticos en los tres países. Mantener tres copias completas hace que, con el tiempo, se desincronicen: alguien corrige un texto legal en una y se olvida de las otras dos.

**El esquema que funciona:**

| Locale | Contenido | Registro |
|---|---|---|
| `es` (base) | Traducción completa | tú |
| `es-AR` | Solo las cadenas que cambian | vos |
| `es-ES` | Solo las cadenas que cambian | tú, con léxico de España |
| `es-MX` | Solo las cadenas que cambian, si hay alguna | tú |

Las bibliotecas de i18n permiten una cadena de respaldo (`es-AR` → `es`): si una clave no está en `es-AR`, se usa la de `es`. Así solo traducís dos veces lo que de verdad es distinto.

Cómo queda un mismo botón:

| | Base / México / España | Argentina |
|---|---|---|
| Confirm transfer | Confirma la transferencia | Confirmá la transferencia |
| You have 3 pending payments | Tienes 3 pagos pendientes | Tenés 3 pagos pendientes |
| Enter your PIN | Introduce tu PIN (España) / Ingresa tu PIN (México) | Ingresá tu PIN |

**¿Y «usted»?** En una fintech es tentador por seriedad, y en México y Colombia la banca tradicional lo usa mucho. Pero la mayoría de las fintech de la región tutean (o vosean en Argentina) justamente para diferenciarse del banco de siempre. La confianza la da la claridad de los textos y que nunca haya sorpresas en las comisiones, no el «usted». Si elegís «usted» para algún país, que sea para toda la app: lo peor es mezclar, por ejemplo «usted» en los errores y «tú» en los botones.

Dos cuidados con el voseo:

- **Solo cambian algunas formas verbales** (imperativo y presente: «confirmá», «tenés», «podés»). Los pronombres «te» y «tu» se mantienen: «tu cuenta», «te enviamos un código». Quien no es argentino suele pasarse y escribir «vos cuenta», que es incorrecto.
- **Que lo revise alguien de Argentina.** Un voseo mal hecho es peor que un tuteo correcto.""",
            },
        ]
    },
    # 16) Multiturno: revisión estricta de una traducción del usuario y debate sobre «deprecado».
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un revisor de localización estricto: señalas cada problema con su motivo y propones la corrección.",
            },
            {
                "role": "user",
                "content": "Revisa mi traducción. Original: «This method is deprecated and will be removed in version 3.0. Use fetchAll() instead, which supports pagination out of the box.» Mi traducción: «Este método está deprecado y será removido en la versión 3.0. Use fetchAll() en su lugar, el cual soporta paginación fuera de la caja.»",
            },
            {
                "role": "assistant",
                "content": """Seis problemas, de más a menos grave:

1. **«Fuera de la caja»: traducción literal de una expresión hecha.** *Out of the box* significa «sin configuración adicional» o «de serie». En español, «fuera de la caja» no significa nada, o se confunde con *thinking outside the box*. → «sin configuración adicional».
2. **«Deprecado»: calco.** «Deprecar» significa «rogar» en español. → «obsoleto» o «en desuso».
3. **«Soporta»: calco.** «Soportar» es «aguantar». → «admite».
4. **«Será removido»: pasiva perifrástica calcada del inglés, y «remover» con un sentido discutido.** La pasiva con «ser» es mucho menos frecuente en español que en inglés; la pasiva refleja suena natural. Y aunque en buena parte de Latinoamérica «remover» se usa como «quitar», en España significa «agitar». → «se eliminará».
5. **«Use»: registro.** «Use» es el imperativo de «usted». Comprueba qué registro usa el resto de la documentación; si tutea, → «Usa».
6. **«El cual»: pesado.** Los relativos compuestos son correctos, pero «que» basta aquí. → «que».

`fetchAll()` está bien: es un identificador, no se traduce. Ponlo con formato de código para que se distinga del texto.

**Versión corregida:**

> Este método está obsoleto y se eliminará en la versión 3.0. Usa `fetchAll()` en su lugar, que admite paginación sin configuración adicional.

Comprobación: la versión corregida conserva las cuatro informaciones del original (obsoleto, se elimina en 3.0, alternativa, ventaja de la alternativa) y no añade ninguna.""",
            },
            {
                "role": "user",
                "content": "En mi equipo todos dicen «deprecado». ¿De verdad está mal?",
            },
            {
                "role": "assistant",
                "content": """Depende de dónde. En una conversación del equipo o en un comentario de código, «deprecado» se entiende perfectamente y nadie debería corregirlo. En **documentación pública** es preferible evitarlo, por dos razones:

1. **Choca con el significado que ya tiene la palabra.** «Deprecar» existe en español con el sentido de «rogar, suplicar». Para quien no conoce la jerga, «método deprecado» no significa nada, y la documentación también la leen personas que empiezan.
2. **Hay alternativas que no pierden nada:** «obsoleto», «en desuso» o «desaconsejado».

Una advertencia sobre «obsoleto»: puede sugerir que el método **ya no funciona**, cuando *deprecated* significa justo lo contrario: funciona, pero no conviene usarlo porque se eliminará. Si te preocupa esa confusión, tienes dos opciones:

- **«En desuso»**, que transmite mejor «todavía existe, pero no lo uses».
- **«Obsoleto» definido en el glosario** y en la primera aparición: «obsoleto (sigue funcionando, pero se eliminará en una versión futura)».

Lo que **no** se traduce nunca, aunque elijas «obsoleto»: los identificadores que el lector verá en el código o en la consola, como la anotación `@deprecated`, el atributo `[Obsolete]` de C# o `DeprecationWarning` en Python. Ahí el texto tiene que coincidir con lo que aparece en pantalla.

Si tu equipo prefiere mantener «deprecado» como término del glosario, también es una decisión defendible. Lo importante es que sea una decisión y no una mezcla: tres páginas con «deprecado», dos con «obsoleto» y una con «en desuso» hacen pensar al lector que son tres estados distintos.""",
            },
        ]
    },
    # 17) Inglés: traducir terminología de concurrencia al español.
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm writing Spanish docs for our concurrency library, but I'm not a native speaker. How should I translate 'race condition', 'deadlock', 'lock', 'thread-safe' and 'starvation'? I'd like the explanation in English.",
            },
            {
                "role": "assistant",
                "content": """Here's what Spanish-speaking developers will recognize, with the reasoning for each:

| English | Recommended Spanish | Notes |
|---|---|---|
| race condition | **condición de carrera** | A calque, but fully established. Use it without hesitation. |
| deadlock | **interbloqueo** | The standard term in Spanish operating-systems textbooks. Many developers just say *deadlock*, so add it in parentheses on first use: «interbloqueo (*deadlock*)». |
| lock (noun) | **cerrojo**, or keep **lock** | Avoid «bloqueo»: see below. |
| thread-safe | **seguro para hilos** | Common and clear. «Seguro para uso concurrente» is more precise when the guarantee also covers async tasks or processes. |
| starvation | **inanición** | Also standard in OS textbooks. It sounds odd at first, but it's the term readers will find elsewhere. |

**The trap: «bloqueo».** It's tempting for *lock*, but in Spanish technical writing «bloqueo» and «bloqueante» are already used for *blocking* («una llamada bloqueante» = *a blocking call*). If your docs say «adquirir un bloqueo» on one page and «operación no bloqueante» on another, readers can't tell whether you're talking about a lock or about blocking. Use «cerrojo» or keep «lock» consistently, and reserve «bloquear/bloqueante» for blocking.

Related verbs and terms you'll need:

- *acquire / release a lock* → «adquirir / liberar el cerrojo»
- *contention* → «contención» (established in this sense)
- *mutex* → «mutex» (masculine: «el mutex»), never translated
- *thread* → «hilo»; *thread pool* → «grupo de hilos» or «pool de hilos»

Two practical tips:

1. **Fix gender and plural in your glossary** for every term you keep in English («el lock», «los locks»). Non-native writers often drift between genders across pages, and readers notice.
2. **Keep API names untranslated.** If your library exposes `Lock`, `try_lock()` or `ThreadSafe`, those stay in code format in every sentence, even right next to «cerrojo»: «Crea un cerrojo con `Lock()`».""",
            },
        ]
    },
    # 18) Inglés: revisar la traducción al inglés hecha por un compañero hispanohablante.
    {
        "messages": [
            {
                "role": "user",
                "content": "A teammate from our Madrid office translated this README section into English. Can you review it? It feels off, but I can't say why. «For to install the library, you must to execute the next command. It is important to have in account that the version of Python must be superior to 3.10. In case of having problems, you can consult the section of FAQ or open an issue, where we will attend you as soon as possible.»",
            },
            {
                "role": "assistant",
                "content": """It feels off because almost every phrase is a word-for-word rendering of a Spanish structure. The grammar is mostly understandable, but no native speaker would write it that way. Here's each issue, with the Spanish pattern behind it, which is useful feedback for your teammate:

| Text | Spanish source | Fix |
|---|---|---|
| For to install | *Para instalar* | To install |
| you must to execute | *debes ejecutar* (modal + infinitive) | run (modals take no «to») |
| the next command | *el siguiente comando* | the following command |
| It is important to have in account that | *Es importante tener en cuenta que* | Note that (or drop it) |
| superior to 3.10 | *superior a 3.10* | 3.10 or later (see below) |
| In case of having problems | *En caso de tener problemas* | If you run into problems |
| the section of FAQ | *la sección de FAQ* | the FAQ |
| attend you | *atenderte* | help you / get back to you |

**Rewrite:**

> To install the library, run the following command. You need Python 3.10 or later. If you run into problems, check the FAQ or open an issue and we'll get back to you as soon as we can.

That's 37 words instead of 54, with nothing lost.

**One point to confirm before publishing:** «superior a 3.10» in Spanish is often used loosely to mean «3.10 or newer», but a literal «higher than 3.10» would exclude 3.10 itself. I assumed 3.10 is supported; check it with your teammate or against the package's `requires-python` setting, since the two readings tell users different things.

When you pass this back, the most useful thing is the middle column: those Spanish patterns (*para + infinitive*, *tener en cuenta*, *en caso de*, *superior a*) will keep producing the same errors in future translations until your teammate recognizes them.""",
            },
        ]
    },
    # 19) Inglés: qué suele romperse al localizar una interfaz al español.
    {
        "messages": [
            {
                "role": "user",
                "content": "We're localizing our SaaS dashboard into Spanish next quarter. What usually breaks? I want to brief the frontend team before we start.",
            },
            {
                "role": "assistant",
                "content": """Here's what typically breaks, roughly in order of how often it causes bugs:

**1. Text expansion.** Spanish text usually runs 20–30% longer than English, and short labels can double («Save» → «Guardar», «Settings» → «Configuración»). Buttons overflow, tabs wrap, table headers truncate. Run a pseudo-localization pass before any translation exists: replace every string with a padded, accented version (`[Ŝéttîñĝš~~~~]`) and look for breakage. It also flags hardcoded strings, which show up untransformed.

**2. String concatenation.** `"Deleted by " + user + " on " + date` assumes English word order. Spanish may need a different order and agreement. Every user-visible sentence must be a single message with placeholders: `"Eliminado por {user} el {date}"`, so translators control the whole sentence.

**3. Plurals and gender.** `count === 1 ? "file" : "files"` isn't enough once adjectives and participles agree too: «1 archivo eliminado», «3 archivos eliminados», «carpeta eliminada». Use ICU MessageFormat (or your i18n library's plural support) and give translators full sentences per form.

**4. Formats.** Spain uses `1.234,56`; Mexico uses `1,234.56`. Dates are day-first everywhere in the Spanish-speaking world. Never build them by hand: use `Intl.NumberFormat` and `Intl.DateTimeFormat` with the user's locale.

**5. Sorting and search.** Default JavaScript sorting compares code points, so «ñu» lands after «oso» and accented words sort after unaccented ones. Search must also match «camion» with «camión». Use a collator:

```ts
const collator = new Intl.Collator("es", { sensitivity: "base" });
collator.compare("camión", "camion") === 0;           // true: accent- and case-insensitive
["ñu", "oso", "nube"].sort(new Intl.Collator("es").compare); // ["nube", "ñu", "oso"]
```

**6. Capitalization.** Spanish doesn't use Title Case: «Configuración de la cuenta», not «Configuración De La Cuenta». Day and month names are lowercase. If your components apply `text-transform: capitalize`, they'll produce wrong Spanish automatically.

**7. Strings outside the frontend.** Emails, PDFs, push notifications, backend error messages and text baked into images are the usual leftovers. Inventory them before you start, or the UI will be Spanish and the invoice email English.

**8. Register.** Decide early between «tú» and «usted» and put it in the translator brief. Mixed register across screens is one of the most noticeable signs of a rushed localization.

For the brief, a short checklist works best: no concatenated sentences, all user-facing text through the i18n layer (including backend errors mapped from codes), `Intl` for every number and date, a collator for sorting and search, sentence case, and layouts that tolerate 30% longer text. Add a CI check that fails on string literals in JSX if your lint setup supports it; that catches regressions after launch.""",
            },
        ]
    },
    # 20) Traducción de una referencia de API (parámetros, tipos y valores literales).
    {
        "messages": [
            {
                "role": "user",
                "content": """Traduce esta parte de la referencia de nuestra API:

### `POST /v1/invoices`

Creates a draft invoice for a customer.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | yes | ID of the customer to bill. |
| `currency` | string | no | Three-letter ISO 4217 code. Defaults to the customer's currency. |
| `due_date` | string (date) | no | Due date in `YYYY-MM-DD` format. Must be in the future. |
| `items` | array | yes | Line items. At least one item is required. |

Returns the created invoice object. Returns `400` if `items` is empty.""",
            },
            {
                "role": "assistant",
                "content": """### `POST /v1/invoices`

Crea una factura en borrador para un cliente.

| Parámetro | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `customer_id` | string | sí | ID del cliente al que se factura. |
| `currency` | string | no | Código de moneda de tres letras según ISO 4217. Si se omite, se usa la moneda del cliente. |
| `due_date` | string (date) | no | Fecha de vencimiento en formato `YYYY-MM-DD`. Debe ser posterior a la fecha actual. |
| `items` | array | sí | Líneas de la factura. Se requiere al menos una. |

Devuelve el objeto de la factura creada. Si `items` está vacío, devuelve un error `400`.

---

Criterios:

- **Sin traducir:** la ruta, los nombres de parámetros, los códigos de estado y `YYYY-MM-DD`. Son literales que el desarrollador escribe o recibe; si cambian, el código deja de funcionar.
- **Tipos (`string`, `array`) en inglés.** Son los tipos del esquema JSON, no descripciones. Si tu herramienta genera la referencia desde OpenAPI, coincidirán con lo que el desarrollador ve en el esquema.
- **`YYYY-MM-DD` frente a `AAAA-MM-DD`.** En texto corrido en español se escribe «AAAA-MM-DD», pero aquí está en formato de código y describe un patrón técnico, así que lo dejé igual que en el original. Si en el resto de la documentación usáis `AAAA-MM-DD`, sé coherente.
- **«Defaults to» → «Si se omite, se usa…».** «Por defecto» también vale, pero la paráfrasis deja claro qué pasa exactamente si no envías el parámetro.

Dos decisiones que conviene revisar con alguien de producto:

1. **«Line items» → «líneas de la factura».** Es lo habitual en España. En México, el término de facturación es «conceptos», que es el que usa el CFDI. Si la documentación es para desarrolladores mexicanos, «conceptos» les resultará más natural.
2. **«Must be in the future» es ambiguo en el original.** ¿Se acepta la fecha de hoy? Traduje «posterior a la fecha actual», que la excluye, porque es la lectura literal. Comprueba qué valida realmente la API y, si hoy se acepta, cambia a «igual o posterior a hoy» en los dos idiomas.""",
            },
        ]
    },
    # 21) Multiturno: ¿logs en español? Y qué hacer con los mensajes existentes.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Mi jefe quiere que los logs de la aplicación estén en español porque el equipo de soporte de primer nivel no lee inglés. ¿Es buena idea?",
            },
            {
                "role": "assistant",
                "content": """El problema que quiere resolver es real; la solución propuesta no es la adecuada. Soporte no necesita logs en español: necesita **saber qué pasó y qué hacer**, y eso no lo da ni un log en inglés ni uno traducido.

**Por qué traducir los logs sale mal:**

1. **Te quedarían logs en dos idiomas.** Las bibliotecas, el framework, la base de datos y el sistema operativo seguirán escribiendo en inglés. Soporte vería una mezcla y seguiría sin entender la mitad.
2. **Los logs los leen también máquinas.** Reglas de alerta, consultas guardadas y paneles buscan textos concretos. Cada mensaje traducido rompe en silencio la regla que lo buscaba.
3. **Se pierde la capacidad de buscar.** Un desarrollador que pega un mensaje de error en un buscador o en el gestor de incidencias de una biblioteca encuentra resultados en inglés, no de una traducción interna.
4. **Un mensaje traducido sigue siendo técnico.** «Tiempo de espera agotado al conectar con el pool» en español no le dice a soporte qué hacer.

**La alternativa: códigos de evento y un catálogo para soporte.**

Los logs siguen en inglés, pero cada evento relevante lleva un código estable:

```json
{"level": "error", "event": "payment.card_declined", "order_id": "A-1042", "msg": "Card declined by issuer"}
```

Y soporte trabaja con un catálogo en español, indexado por código:

| Código | Qué significa | Qué hacer |
|---|---|---|
| `payment.card_declined` | El banco del cliente rechazó el pago. No es un fallo nuestro. | Pedir al cliente otra tarjeta o que contacte con su banco. |
| `payment.provider_timeout` | El proveedor de pagos no respondió a tiempo. | Comprobar si el cobro llegó a hacerse antes de reintentarlo. Si se repite, escalar a nivel 2. |

Si la herramienta de logs lo permite, muestra la descripción del catálogo junto al evento. Así se lo puedes presentar a tu jefe: el equipo de soporte pasa de leer mensajes técnicos traducidos a recibir instrucciones concretas, y los desarrolladores no pierden nada.""",
            },
            {
                "role": "user",
                "content": "Me convenció. Pero ya tenemos cientos de mensajes de log sin código de evento. ¿Por dónde empiezo?",
            },
            {
                "role": "assistant",
                "content": """No los conviertas todos: empieza por los que soporte ve de verdad. La distribución de los logs suele ser muy desigual, y unos pocos mensajes concentran casi todo el volumen.

**1. Mide cuáles son.** Si tus logs son JSON con el texto en `msg`, los mensajes de error más frecuentes de los últimos días salen con:

```bash
jq -r 'select(.level == "error") | .msg' app.log | sort | uniq -c | sort -rn | head -20
```

Si tu plataforma de logs tiene consultas con agregación, haz lo mismo agrupando por mensaje. Cuidado con los mensajes que llevan datos variables («order A-1042 failed»): agrúpalos por plantilla, o cada pedido aparecerá como un mensaje distinto.

**2. Asigna código a esos 20 primero**, y escribe su entrada en el catálogo con soporte delante: la columna «qué hacer» la deben validar ellos, porque son quienes la usarán.

**3. Fija una regla para lo nuevo:** todo log de nivel `warning` o superior lleva `event`. Ponla en la guía de revisión de código y, si podéis, en un test o una regla de lint sobre el logger. Sin esta regla, la deuda vuelve a crecer mientras pagas la antigua.

**4. Para el resto, un respaldo explícito.** Cualquier error sin código aparece en el panel de soporte como «Evento sin descripción: escalar a nivel 2». Es mejor que un mensaje en inglés que alguien intenta interpretar.

**5. Mide el avance:** el porcentaje de errores del día que tienen código. Es la cifra que le enseñas a tu jefe cada semana, y te dice cuándo parar. Con el 90 % del volumen cubierto, los cientos de mensajes restantes probablemente no justifican el esfuerzo.""",
            },
        ]
    },
    # 22) Traducción de notas de la versión (release notes).
    {
        "messages": [
            {
                "role": "user",
                "content": """Traduce estas notas de la versión para la sección de novedades en español:

## v2.4.0

### New
- Bulk export: export up to 10,000 records to CSV from any list view.
- Dark mode now follows your OS setting by default.

### Fixed
- Fixed a bug where saved filters were lost after logging out.
- Timestamps in the activity feed now respect your time zone.

### Breaking changes
- The `GET /v1/reports` endpoint now requires the `reports:read` scope. Existing tokens without it will receive `403 Forbidden`.

### Deprecated
- The `legacy_id` field is deprecated and will be removed in v3.0.""",
            },
            {
                "role": "assistant",
                "content": """## v2.4.0

### Novedades
- Exportación masiva: exporta hasta 10 000 registros a CSV desde cualquier vista de lista.
- El modo oscuro sigue ahora, de forma predeterminada, la configuración de tu sistema operativo.

### Correcciones
- Los filtros guardados ya no se pierden al cerrar sesión.
- Las horas del registro de actividad se muestran ahora en tu zona horaria.

### Cambios incompatibles
- El endpoint `GET /v1/reports` requiere ahora el permiso `reports:read`. Los tokens que no lo tengan recibirán un error `403 Forbidden`.

### Obsoleto
- El campo `legacy_id` está obsoleto y se eliminará en la v3.0.

---

Decisiones:

- **Correcciones descritas por su efecto.** «Fixed a bug where…» se traduce literalmente como «Se corrigió un error por el que…», que es largo y pone el foco en el error. «Los filtros guardados ya no se pierden» dice lo que le importa al usuario en menos palabras.
- **«Breaking changes» → «Cambios incompatibles».** Es lo que son: cambios que pueden romper integraciones existentes. Va con encabezado propio para que nadie lo pase por alto.
- **«Scope» → «permiso».** En OAuth, *scope* se traduce a veces como «ámbito» o «alcance», pero en unas notas de versión «permiso» se entiende a la primera. El nombre `reports:read` queda intacto porque es lo que hay que configurar.
- **«10,000» → «10 000».** La norma del español separa los miles con un espacio en cifras de más de cuatro dígitos. Si el público es sobre todo mexicano, «10,000» es lo habitual allí; usa el mismo criterio en toda la documentación.
- **«Obsoleto» para *deprecated*.** Si tenéis glosario, que coincida con él; si no, añade allí que «obsoleto» significa que el campo sigue funcionando hasta la v3.0.
- **Sin traducir:** el endpoint, el código de estado, los nombres de campo y «CSV».
- **«Activity feed» → «registro de actividad».** Comprueba cómo se llama esa sección en la interfaz en español: las notas deben usar exactamente el mismo nombre que el usuario ve en pantalla.""",
            },
        ]
    },
    # 23) Multiturno: bug de i18n por concatenación en React con i18next, y cómo prevenirlo.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """En español este componente queda raro («Eliminado por Ana el 20/10/2026 (1 archivos)») y no sé cómo arreglarlo bien:

```tsx
function ActivityItem({ user, date, count }: Props) {
  const { t } = useTranslation();
  return (
    <p>
      {t("deleted_by")} <strong>{user}</strong> {t("on")} {formatDate(date)} ({count} {t("files")})
    </p>
  );
}
```

`es.json`: `{"deleted_by": "Eliminado por", "on": "el", "files": "archivos"}`""",
            },
            {
                "role": "assistant",
                "content": """El componente arma la frase con piezas sueltas, así que quien traduce nunca ve la oración completa. De ahí salen tres errores:

1. **Plural roto:** «1 archivos». `t("files")` siempre devuelve la misma forma.
2. **Orden fijo:** el código impone el orden inglés. Si el español necesita otro, el traductor no puede cambiarlo.
3. **Claves reutilizables y ambiguas:** `"on"` → `"el"` funciona delante de una fecha, pero en cuanto alguien reutilice `t("on")` para «turn on» o «on Monday», la traducción será incorrecta. Y «Eliminado» concuerda en masculino: si el objeto fuera una carpeta, debería ser «Eliminada».

**Arreglo: una clave por oración, con interpolación, plural y el componente `Trans` para la negrita.**

`es.json`:

```json
{
  "activity": {
    "deleted_one": "<bold>{{user}}</bold> eliminó {{count}} archivo el {{date}}",
    "deleted_other": "<bold>{{user}}</bold> eliminó {{count}} archivos el {{date}}"
  }
}
```

Componente:

```tsx
import { Trans } from "react-i18next";

function ActivityItem({ user, date, count }: Props) {
  return (
    <p>
      <Trans
        i18nKey="activity.deleted"
        count={count}
        values={{ user, date: formatDate(date) }}
        components={{ bold: <strong /> }}
      />
    </p>
  );
}
```

Resultado: «**Ana** eliminó 1 archivo el 20/10/2026» y «**Ana** eliminó 3 archivos el 20/10/2026».

Por qué así:

- **`count` como prop de `Trans`** es lo que activa la selección de plural: i18next elige `deleted_one` o `deleted_other` según las reglas del idioma (sufijos `_one`/`_other`, el formato de i18next v21 en adelante).
- **`<bold>` con nombre** en lugar de etiquetas numeradas (`<1>`): quien traduce ve qué es cada etiqueta y puede moverla dentro de la frase.
- **Cambié la frase a voz activa** («Ana eliminó…»). Además de sonar más natural en español, el verbo concuerda con la persona y no con el objeto, así que el problema de género de «Eliminado/Eliminada» desaparece. Reformular para evitar concordancias es una técnica legítima de localización, siempre que el significado sea el mismo.
- **La fecha llega ya formateada.** Usa `Intl.DateTimeFormat` con el idioma activo dentro de `formatDate`, no un formato fijo.

Comprobación: renderiza el componente con `count` 1 y 3 en un test con el idioma `es` y verifica el texto de los dos casos.""",
            },
            {
                "role": "user",
                "content": "¿Y cómo evito que vuelva a pasar? Somos ocho personas en frontend.",
            },
            {
                "role": "assistant",
                "content": """Tres capas, de más barata a más completa:

**1. Lint para los textos sin traducir.** El plugin `eslint-plugin-i18next` tiene la regla `i18next/no-literal-string`, que marca los textos escritos directamente en JSX. No detecta la concatenación de varios `t()`, pero impide la otra mitad del problema: el texto que nunca pasó por i18n.

**2. Pseudolocalización en desarrollo**, que es la que sí detecta la concatenación. Un postprocesador de i18next que envuelve cada traducción entre corchetes:

```ts
import i18n from "i18next";

i18n.use({
  type: "postProcessor",
  name: "pseudo",
  process: (value: string) => `[${value}]`,
});

// en la llamada a init, solo en desarrollo (con Vite):
// postProcess: import.meta.env.DEV ? ["pseudo"] : [],
```

Con eso, el componente antiguo se habría visto así: «[Eliminado por] Ana [el] 20/10/2026 (1 [archivos])». Varios corchetes en una misma frase significan concatenación; un texto sin corchetes significa que no pasó por i18n. Cualquiera lo detecta al mirar la pantalla, sin saber español.

**3. Una regla en la guía de revisión de código:** «una oración, una clave». Si un PR tiene dos llamadas a `t()` en el mismo párrafo o un `t()` pegado a una variable, se pide el cambio. Es la regla que cubre lo que las herramientas no ven.

Y un detalle que ayuda a los traductores: añadid contexto a las claves ambiguas. i18next admite variantes de contexto (`t("open", { context: "verb" })` → clave `open_verb`), y la mayoría de plataformas de traducción permiten un comentario por clave. Una clave `"on"` sin contexto es el tipo de clave que provocó este error.

Con ocho personas, el orden práctico es: la pseudolocalización hoy (es una tarde de trabajo y saca a la luz los casos existentes), la regla de revisión esta semana y el lint cuando hayáis limpiado lo que encuentre la pseudolocalización, para que no empiece con cientos de avisos.""",
            },
        ]
    },
    # 24) Error de Git mostrado en español (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Me salió esto en la terminal y no entiendo nada: `fatal: rehusando fusionar historias no relacionadas`. Busco en Google y casi no encuentro nada.",
            },
            {
                "role": "assistant",
                "content": """Tu Git está configurado en español y por eso no encuentras nada: casi toda la información está escrita con el mensaje original en inglés. Busca este:

```text
fatal: refusing to merge unrelated histories
```

**Qué significa.** «Historia» aquí es el historial de commits. Git te dice que las dos ramas que intentas fusionar no tienen ningún commit en común: empezaron por separado, así que no sabe cómo unirlas. (La traducción «historias» es literal y confunde; «historiales» sería más claro.)

**Por qué pasa casi siempre.** Creaste un repositorio en GitHub con un README o una licencia (eso ya es un commit), y por otro lado hiciste `git init` y commits en tu computadora. Al hacer `git pull`, Git encuentra dos historiales que no comparten ningún punto de partida.

**Cómo resolverlo:**

1. Comprueba que estás trayendo del repositorio correcto, porque el mismo error aparece si el remoto apunta a otro proyecto:

```bash
git remote -v
```

2. Si es el correcto y quieres unir los dos historiales:

```bash
git pull origin main --allow-unrelated-histories
```

Si los dos lados tienen un archivo con el mismo nombre (lo típico es `README.md`), Git marcará un conflicto. Edita el archivo, quédate con lo que quieras, y termina con:

```bash
git add README.md
git commit
```

Comprobación: `git log --oneline --graph` debe mostrar los commits de los dos lados unidos en un commit de fusión.

**Para ver los mensajes de Git en inglés** solo en un comando, antepón `LC_ALL=C`:

```bash
LC_ALL=C git pull origin main
```

Funciona en Linux, macOS y Git Bash en Windows, y no cambia nada de forma permanente. Te sirve para copiar el mensaje exacto y buscarlo.""",
            },
        ]
    },
    # 25) Léxico regional: documentación neutra para Latinoamérica y España.
    {
        "messages": [
            {
                "role": "user",
                "content": "Escribimos la documentación de producto para toda Latinoamérica y España en una sola versión. ¿Cómo resolvemos computadora/ordenador, archivo/fichero, celular/móvil, contraseña/clave, hacer clic/pulsar? Queremos que nadie sienta que está traducida para otro país.",
            },
            {
                "role": "assistant",
                "content": """La regla general: cuando una palabra cambia de un país a otro, busca primero una tercera opción que funcione en todos; si no existe, elige la que entiende todo el mundo aunque no sea la favorita de algún país.

| Pares | Recomendación | Por qué |
|---|---|---|
| computadora / ordenador | **equipo** o **dispositivo**; si hace falta el término, «computadora» | «Tu equipo» evita el problema por completo. En España «computadora» se entiende; en Latinoamérica «ordenador» se entiende, pero suena claramente a España. |
| archivo / fichero | **archivo** | Se usa en todos los países, también en España. «Fichero» es solo de España. |
| celular / móvil | **teléfono** | Neutro y claro en todas partes. |
| contraseña / clave | **contraseña** | Universal. Además, en varios países «clave» se usa también para el PIN numérico; usarla para la contraseña genera dudas en los textos de seguridad. |
| hacer clic / pulsar / dar clic | **hacer clic** (ratón), **tocar** (pantalla táctil) | «Hacer clic» es el más extendido. «Dar clic» es muy mexicano. «Pulsar» funciona, pero es más propio de España. |

Palabras que conviene vigilar aunque no las hayas preguntado:

- **«Coger»**: normal en España («coge el archivo»), vulgar en buena parte de Latinoamérica. → «tomar», «seleccionar», «abrir».
- **«Ratón» / «mouse»**: en España «ratón», en buena parte de Latinoamérica «mouse». → muchas veces se puede evitar: «haz clic» ya implica el dispositivo.
- **«Vale», «platicar», «chévere»** y similares: coloquialismos locales que no tienen sitio en una documentación neutra.
- **«Computador»** (Chile, Colombia) frente a **«computadora»** (México, Argentina y otros): otra razón para preferir «equipo».

Dos cosas más:

1. **Neutro no es lo mismo que «español de España» ni que «mexicano sin regionalismos».** Que revise la documentación al menos una persona de cada lado del Atlántico, y anotad en el glosario cada decisión tomada. Si no queda escrito, cada nuevo redactor vuelve a usar su variante.
2. **Lo neutro tiene límites.** En textos legales, de facturación o de impuestos, el vocabulario es distinto de verdad en cada país (CFDI, factura electrónica, NIF frente a RFC). Ahí no hay versión neutra posible, y hacen falta páginas por país.""",
            },
        ]
    },
    # 26) Transcreación: adaptar un texto de marketing técnico en lugar de traducirlo.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que adaptar el titular de nuestra landing: «Ship faster. Sleep better. Zero-config observability for teams that move fast and don't break things.» Si lo traduzco literal queda horrible.",
            },
            {
                "role": "assistant",
                "content": """Porque no hay que traducirlo, sino adaptarlo (transcreación): conservar lo que el texto **hace** (prometer, crear ritmo, hacer un guiño) aunque cambien las palabras.

Qué hace el original:

1. **Ritmo:** dos imperativos de dos palabras, paralelos y rotundos.
2. **Promesa doble:** velocidad («ship faster») y tranquilidad («sleep better»).
3. **Guiño:** «move fast and don't break things» invierte el famoso lema «move fast and break things». El lector técnico lo reconoce y sonríe.
4. **Palabra clave:** «observability», que es lo que el cliente busca.

La versión literal, «Despliega más rápido. Duerme mejor. Observabilidad sin configuración para equipos que se mueven rápido y no rompen cosas», pierde el ritmo (los imperativos se alargan) y el guiño: el lema solo se reconoce en inglés, y «no rompen cosas» suena infantil.

Tres propuestas:

**A. Mantener el paralelismo con un guiño propio**
> Despliega antes. Duerme tranquilo.
> Observabilidad lista para usar, para equipos que van rápido sin romper nada.

**B. Más directa**
> Publica más rápido. Duerme mejor.
> Observabilidad sin configurar nada, para equipos que no pueden permitirse caídas.

**C. Conservando el lema en inglés**
> Move fast. Sin romper nada.
> Observabilidad lista para usar desde el primer minuto.

**Recomiendo la A.** Conserva los dos imperativos cortos, la palabra clave y el sentido del guiño («van rápido sin romper nada») sin depender de que el lector conozca el lema. La B pierde el juego de palabras y cambia el tono hacia el miedo, que no es lo que transmite el original. La C es arriesgada: funciona con un público muy técnico, pero mezclar idiomas en el titular suele parecer un descuido.

Criterios que apliqué:

- **«Ship» → «despliega» o «publica».** En este contexto significa llevar código a producción. «Envía» sería un error de sentido y «lanza» sugiere un producto nuevo.
- **«Zero-config» → «lista para usar».** «Sin configuración» suena a carencia; «lista para usar» transmite lo mismo como ventaja.
- **Longitud.** El español ocupa más: comprueba la A en el diseño real, en móvil, antes de darla por buena. Si no cabe, el segundo renglón se puede acortar a «Observabilidad lista para usar».
- **Tuteo**, por coherencia con el imperativo del original; si el resto del sitio trata de «usted», «despliegue» y «duerma» funcionan peor en un titular, lo que es un argumento para tutear en todo el sitio.

Valídalo con dos o tres clientes reales que hablen español antes de publicarlo: con un titular, lo que importa es si se entiende y engancha a la primera, y eso no se decide solo desde el escritorio.""",
            },
        ]
    },
    # 27) Normas tipográficas que cambian al traducir del inglés.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Qué normas tipográficas cambian al pasar documentación del inglés al español? Comillas, mayúsculas, números… Quiero una lista para los traductores.",
            },
            {
                "role": "assistant",
                "content": """Lista para traductores, con el error típico de cada punto:

**Mayúsculas**
1. **Títulos con mayúscula solo inicial.** «Configuración de la cuenta», no «Configuración De La Cuenta». El estilo inglés (*Title Case*) no existe en español.
2. **Días, meses e idiomas en minúscula:** «el lunes 3 de marzo», «disponible en español».

**Puntuación**
3. **Signos de apertura obligatorios:** «¿Quieres continuar?», «¡Listo!».
4. **Comillas:** la RAE recomienda primero las angulares («»), después las inglesas (“ ”) y por último las simples (‘ ’). Excepción: dentro de código, las comillas son las del lenguaje y no se tocan.
5. **El punto va después de cerrar comillas o paréntesis:** «se llama “principal”.», no «se llama “principal.”».

**Números**
6. **Separador de miles:** la norma académica usa un espacio en cifras de más de cuatro dígitos («10 000»), y no agrupa las de cuatro («1000»). Los años nunca se agrupan («2026»). Si el público es mexicano, decidid si seguís la norma o el uso local («10,000») y aplicadlo siempre igual.
7. **Separador decimal:** coma en España y gran parte de Sudamérica; punto en México y Centroamérica. La RAE admite los dos.
8. **Porcentaje con espacio:** «50 %».
9. **Ordinales:** «1.º», «2.ª», no «1st» ni «1ro».

**Unidades y horas**
10. **Espacio entre número y unidad, y la unidad sin plural ni punto:** «10 MB», no «10MB» ni «10 MBs».
11. **Horas:** «15:30» o «3:30 p. m.» (con espacios y puntos). Evita «3:30 PM».

**Siglas**
12. **Las siglas no llevan «s» de plural:** «las API», «los PDF». El plural lo marca el artículo. «APIs» está muy extendido en jerga técnica; si el equipo prefiere mantenerlo, que sea una decisión del glosario.

**Listas**
13. **Si los elementos continúan una frase**, empiezan en minúscula y terminan en punto y coma, con punto final en el último. Si son oraciones independientes, mayúscula y punto en cada una. El inglés es más laxo con esto.

Ejemplo con varios errores corregidos a la vez:

- Antes: «Novedades De Octubre: Ahora Puedes Subir Archivos De Hasta 10GB (Antes 2GB), un 400% Más.»
- Después: «Novedades de octubre: ahora puedes subir archivos de hasta 10 GB (antes, 2 GB), un 400 % más.»

Comprobación del ejemplo: pasar de 2 GB a 10 GB es un aumento de 8 GB sobre 2, es decir, un 400 %. Verifica siempre los porcentajes al traducir: es el momento en el que los errores del original se detectan con más facilidad.""",
            },
        ]
    },
    # 28) Calcos sintácticos del inglés: pasiva, gerundio, «en orden a», participios sueltos.
    {
        "messages": [
            {
                "role": "user",
                "content": "Mis traducciones son «correctas», pero suenan a traducción. Ejemplo: «El archivo es procesado por el servidor, siendo luego enviado al cliente. En orden a mejorar el rendimiento, es recomendado usar caché. Basado en los resultados, decidimos migrar.» ¿Qué tiene de malo?",
            },
            {
                "role": "assistant",
                "content": """Las palabras son españolas, pero la sintaxis es inglesa. Tu ejemplo tiene cinco calcos sintácticos, y son los más frecuentes en traducción técnica:

1. **«Es procesado por el servidor»: pasiva perifrástica.** En inglés la pasiva con *to be* es muy normal; en español es mucho menos frecuente y suena a traducción. → Voz activa («el servidor procesa el archivo») o pasiva refleja («el archivo se procesa en el servidor»).
2. **«Siendo luego enviado»: gerundio de posterioridad.** El gerundio expresa algo simultáneo o anterior, no algo que ocurre después. Además, «siendo enviado» repite la pasiva. → «y después lo envía al cliente».
3. **«En orden a mejorar»: calco de *in order to*.** → «Para mejorar».
4. **«Es recomendado»: otra pasiva calcada.** → «se recomienda» o, mejor aún, «conviene».
5. **«Basado en los resultados, decidimos»: participio suelto.** «Basado» concuerda gramaticalmente con el sujeto, que es «nosotros»: literalmente dice que nosotros estamos basados en los resultados. Es el *dangling modifier* del inglés. → «A partir de los resultados» o «Según los resultados».

Versión corregida:

> El servidor procesa el archivo y después lo envía al cliente. Para mejorar el rendimiento, conviene usar caché. A la vista de los resultados, decidimos migrar.

Otros calcos que vas a encontrar en el mismo tipo de textos:

| Calco | Natural |
|---|---|
| Este método **retorna** una lista | Este método **devuelve** una lista |
| **Usted puede** configurar… (pronombre explícito en cada frase) | **Puede** configurar… (el español omite el sujeto) |
| Juega un **rol** importante | **Desempeña un papel** importante, o simplemente: es importante |
| **Hace sentido** | **Tiene sentido** |
| **A nivel de** base de datos | **En la** base de datos |
| Introduzca **su** contraseña en **su** dispositivo | Introduzca la contraseña en el dispositivo |

Un método de revisión rápido, en tres pasadas:

1. Busca «es/son/fue/será» + participio y pregúntate si la voz activa o el «se» funcionan mejor. Casi siempre sí.
2. Busca gerundios y comprueba que expresan algo simultáneo o anterior.
3. Lee el texto en voz alta. Si no lo dirías así al explicárselo a un compañero, todavía es una traducción.""",
            },
        ]
    },
    # 29) Citar errores del compilador de TypeScript en un tutorial en español.
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy escribiendo un tutorial de TypeScript en español. ¿Cito los errores del compilador en inglés o los traduzco? Por ejemplo: «Type 'string' is not assignable to type 'number'».",
            },
            {
                "role": "assistant",
                "content": """Cítalos en inglés, literalmente, **con su código**, y explícalos en español justo después. El código es la clave, porque es lo único que coincide para todos tus lectores.

Formato recomendado:

> **TS2322:** `Type 'string' is not assignable to type 'number'.`
> No puedes guardar un texto en una variable declarada como número.

Y el ejemplo que lo provoca:

```ts
let edad: number = 30;
edad = "treinta"; // TS2322
```

Por qué ese formato:

1. **No todos tus lectores ven el mismo texto.** TypeScript tiene mensajes traducidos: `tsc --locale es` los muestra en español, y VS Code usa por defecto el idioma del editor para los errores de TypeScript (se cambia con el ajuste `typescript.locale`). Un lector verá el mensaje en inglés y otro en español. **El código `TS2322` es el mismo en los dos casos**, así que es el ancla que permite a cualquiera reconocer el error en su pantalla.
2. **Para buscar, el inglés gana.** La gran mayoría de las respuestas en foros y en el gestor de incidencias de TypeScript citan el mensaje original. Si tu lector copia tu cita, encuentra resultados.
3. **No inventes la traducción oficial.** Si traduces el mensaje por tu cuenta y lo presentas como el error, el lector que tenga el editor en español verá un texto distinto del tuyo y pensará que es otro error. La explicación en español es tuya y debe parecerlo: formulada como explicación, no como cita.

Dos detalles de redacción:

- **«Assignable» no tiene buena traducción directa.** «Asignable» se entiende, pero lo que el error explica es compatibilidad de tipos. En la explicación, «no puedes guardar un `string` donde se espera un `number`» se entiende mejor que «no es asignable».
- **Los tipos y nombres en formato de código y sin traducir:** `string`, `number`, `edad`. Si escribes «el tipo cadena», el lector tiene que traducirlo de vuelta para buscarlo en la documentación.

Si el tutorial es para principiantes absolutos, añade en la introducción una nota: «Los errores aparecen en inglés o en español según la configuración de tu editor; fíjate siempre en el código que empieza por TS».""",
            },
        ]
    },
    # 30) Script de CI que comprueba el glosario en la documentación (avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos un glosario (deprecado → obsoleto, librería → biblioteca, removido → eliminado…) y nadie lo respeta en los .md de docs/. ¿Me haces un script sencillo para CI que lo compruebe? Python, sin dependencias.",
            },
            {
                "role": "assistant",
                "content": r"""El glosario en un JSON, con patrones que cubren las variantes de género y número:

```json
{
  "deprecad[oa]s?": "obsoleto",
  "librer[ií]as?": "biblioteca",
  "removid[oa]s?": "eliminado",
  "eventualmente": "finalmente / con el tiempo"
}
```

El script (`scripts/revisar_glosario.py`):

```python
#!/usr/bin/env python3
'''Comprueba que la documentación Markdown respeta el glosario.

Uso: python scripts/revisar_glosario.py docs/glosario.json docs/
Termina con código 1 si encuentra algún término desaconsejado.
'''
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MARCAS_DE_BLOQUE = ("`" * 3, "~~~")
RE_CODIGO_EN_LINEA = re.compile(r"`[^`]*`")
MARCA_IGNORAR = "glosario: ignorar"

Regla = tuple[re.Pattern[str], str]


def cargar_glosario(ruta: Path) -> list[Regla]:
    patrones: dict[str, str] = json.loads(ruta.read_text(encoding="utf-8"))
    return [
        (re.compile(rf"\b(?:{patron})\b", re.IGNORECASE), sugerencia)
        for patron, sugerencia in patrones.items()
    ]


def revisar_archivo(ruta: Path, reglas: list[Regla]) -> list[str]:
    hallazgos: list[str] = []
    en_bloque_de_codigo = False
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        if linea.lstrip().startswith(MARCAS_DE_BLOQUE):
            en_bloque_de_codigo = not en_bloque_de_codigo
            continue
        if en_bloque_de_codigo or MARCA_IGNORAR in linea:
            continue
        # Se tapa el código en línea con espacios para no mover las columnas.
        texto = RE_CODIGO_EN_LINEA.sub(lambda m: " " * len(m.group()), linea)
        for patron, sugerencia in reglas:
            for encontrado in patron.finditer(texto):
                hallazgos.append(
                    f"{ruta}:{numero}:{encontrado.start() + 1}: "
                    f"«{encontrado.group()}» → usa «{sugerencia}»"
                )
    return hallazgos


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: revisar_glosario.py GLOSARIO.json DIRECTORIO", file=sys.stderr)
        return 2
    reglas = cargar_glosario(Path(argv[0]))
    hallazgos = [
        hallazgo
        for markdown in sorted(Path(argv[1]).rglob("*.md"))
        for hallazgo in revisar_archivo(markdown, reglas)
    ]
    for hallazgo in hallazgos:
        print(hallazgo)
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Decisiones:

- **Ignora el código** (bloques y código en línea). Una función `api_deprecada()` o un ejemplo que cita un texto literal no son errores de redacción; marcarlos haría que el equipo ignorara el script en una semana.
- **Patrones como expresiones regulares** en el glosario, envueltos en `(?:…)` y entre `\b`, para cubrir «deprecada» o «librerías» sin coincidir con trozos de otras palabras. En Python 3, `\b` reconoce las letras acentuadas como parte de la palabra.
- **Salida `ruta:línea:columna`**, el formato que GitHub Actions y la mayoría de editores convierten en enlaces.
- **Una vía de escape:** una línea con `<!-- glosario: ignorar -->` se salta. Hace falta para los casos legítimos, como un texto que explica precisamente por qué no se dice «librería».
- **Sin dependencias** y compatible con Python 3.10 (el alias `Regla` usa `tuple[...]`, válido desde 3.9).

Limitación conocida: alterna el estado con cualquier línea que empiece por tres comillas invertidas o tres virgulillas, así que un bloque abierto con cuatro comillas invertidas que contenga otro de tres lo confundiría. En documentación normal no ocurre.

Test mínimo con pytest (asumo `pythonpath = ["scripts"]` en la configuración de pytest, para poder importar el script):

```python
import re

from revisar_glosario import revisar_archivo


def test_marca_texto_y_respeta_codigo(tmp_path):
    md = tmp_path / "guia.md"
    md.write_text(
        "La API está deprecada.\n~~~\nestado = 'deprecada'\n~~~\nEl valor `deprecada` es literal.\n",
        encoding="utf-8",
    )
    reglas = [(re.compile(r"\b(?:deprecad[oa]s?)\b", re.IGNORECASE), "obsoleto")]

    hallazgos = revisar_archivo(md, reglas)

    assert len(hallazgos) == 1
    assert f"{md}:1:" in hallazgos[0]
```

La línea 1 debe detectarse; la 3 está dentro de un bloque de código y la 5 en código en línea, así que ninguna de las dos debe aparecer.

En CI, un paso basta:

```yaml
- name: Revisar glosario
  run: python scripts/revisar_glosario.py docs/glosario.json docs/
```

Para no bloquear al equipo el primer día, ejecútalo primero sin que falle el pipeline (o solo sobre los archivos modificados en el PR), corrige lo existente y después hazlo obligatorio.""",
            },
        ]
    },
]
