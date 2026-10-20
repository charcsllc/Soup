"""Razonamiento profundo: lógica, matemáticas discretas, probabilidad, estimación, planificación,
acertijos con trampa, paradojas, análisis de argumentos, teoría de juegos, tiempo y causalidad.

Cada respuesta expone el método a la vista y verifica el resultado por un segundo camino.
Todo el razonamiento va visible en la respuesta.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Lógica proposicional: afirmación del consecuente.
    {
        "messages": [
            {"role": "user", "content": "Si llueve, el suelo está mojado. El suelo está mojado. Entonces llovió, ¿no? Mi compañero dice que eso no es válido pero no sabe explicarme por qué."},
            {
                "role": "assistant",
                "content": """Tu compañero tiene razón: la conclusión no se sigue. El argumento tiene esta forma:

1. P → Q (si llueve, el suelo está mojado)
2. Q (el suelo está mojado)
3. ∴ P (llovió)

Se llama **afirmación del consecuente** y es una falacia formal. «Si llueve, el suelo se moja» solo dice que la lluvia es *suficiente* para mojar el suelo, no que sea *necesaria*. Un aspersor, una manguera o un camión cisterna también lo mojan.

**Comprobación con la tabla de verdad.** Un argumento es válido si no existe ningún caso con premisas verdaderas y conclusión falsa:

| P (llueve) | Q (mojado) | P → Q | ¿Premisas verdaderas? | Conclusión P |
|---|---|---|---|---|
| V | V | V | sí | V |
| V | F | F | no | — |
| F | V | V | **sí** | **F** |
| F | F | V | no | — |

La tercera fila es el contraejemplo: no llovió, el suelo está mojado, la implicación sigue siendo verdadera, y la conclusión «llovió» es falsa. Con un solo caso así, el argumento es inválido.

**Las dos formas válidas que se parecen a esta:**

- *Modus ponens*: P → Q, P, ∴ Q. («Llueve, luego el suelo está mojado.»)
- *Modus tollens*: P → Q, ¬Q, ∴ ¬P. («El suelo está seco, luego no llovió.»)

Lo que tu intuición está haciendo es razonar de forma *abductiva*: «el suelo está mojado, la lluvia es la explicación más probable». Eso es legítimo como hipótesis, no como deducción. Para que la deducción valiera, necesitarías la premisa más fuerte «el suelo está mojado **si y solo si** llueve», que en el mundo real es falsa.""",
            },
        ]
    },
    # 2) Conteo con complemento, multiturno.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Cuántas contraseñas de exactamente 8 caracteres hay si solo se permiten letras minúsculas (a-z) y dígitos, y tiene que haber al menos un dígito?"},
            {
                "role": "assistant",
                "content": """**2 612 282 842 880** (unos 2,6 billones).

**Método (contar el complemento).** «Al menos un dígito» es difícil de contar directamente porque habría que sumar los casos con 1, 2, 3 … 8 dígitos. Es más corto restar del total las contraseñas que *no* cumplen la condición (cero dígitos):

1. Alfabeto: 26 letras + 10 dígitos = 36 símbolos.
2. Total de cadenas de 8: 36⁸ = 2 821 109 907 456.
3. Cadenas sin ningún dígito (solo letras): 26⁸ = 208 827 064 576.
4. Con al menos un dígito: 36⁸ − 26⁸ = 2 612 282 842 880.

Cálculo de las potencias: 36² = 1296, 36⁴ = 1296² = 1 679 616, 36⁸ = 1 679 616² = 2 821 109 907 456. Y 26² = 676, 26⁴ = 456 976, 26⁸ = 456 976² = 208 827 064 576.

**Verificación por otro camino.** La fracción de cadenas sin dígitos es (26/36)⁸ = (0,7222)⁸ ≈ 0,074. Así que el 92,6 % de todas las cadenas tienen al menos un dígito: 0,926 × 2,82 × 10¹² ≈ 2,61 × 10¹². Coincide con el resultado exacto.

Un error típico es razonar «fijo un dígito en una posición y relleno el resto»: 8 × 10 × 36⁷. Eso cuenta varias veces las cadenas con más de un dígito y da un número mayor que el total, lo que ya delata el fallo.""",
            },
            {"role": "user", "content": "Y si además exijo al menos una letra?"},
            {
                "role": "assistant",
                "content": """Resta también las cadenas que son *solo dígitos*, que son las únicas que cumplían «al menos un dígito» pero no «al menos una letra»:

- Solo dígitos: 10⁸ = 100 000 000.
- Resultado: 36⁸ − 26⁸ − 10⁸ = 2 612 282 842 880 − 100 000 000 = **2 612 182 842 880**.

Esto es inclusión-exclusión con dos conjuntos «malos» (sin dígitos, sin letras). Normalmente habría que sumar de vuelta la intersección, pero una cadena no puede carecer a la vez de letras y de dígitos (tendría longitud 0), así que la intersección es vacía y no hay nada que corregir.

Verificación: 10⁸ es el 0,004 % del total, así que la cifra apenas cambia respecto a la anterior, que es lo esperable. Si la restricción hubiera movido el resultado en órdenes de magnitud, habría que sospechar del cálculo.""",
            },
        ]
    },
    # 3) Inducción: suma de impares.
    {
        "messages": [
            {"role": "user", "content": "Me piden demostrar por inducción que 1 + 3 + 5 + ... + (2n-1) = n². Entiendo la idea de inducción pero no sé cómo escribirlo bien."},
            {
                "role": "assistant",
                "content": """Una demostración por inducción tiene tres partes fijas. Te las escribo con el detalle que suele pedir un corrector.

**Afirmación.** Para todo entero n ≥ 1, S(n) = 1 + 3 + 5 + ⋯ + (2n − 1) = n².

**Caso base (n = 1).** La suma tiene un solo término: S(1) = 1 = 1². Se cumple.

**Hipótesis de inducción.** Supongamos que para algún n ≥ 1 se cumple S(n) = n².

**Paso inductivo.** Queremos probar S(n + 1) = (n + 1)². La suma hasta n + 1 es la suma hasta n más el siguiente impar, que es 2(n + 1) − 1 = 2n + 1:

S(n + 1) = S(n) + (2n + 1) = n² + 2n + 1 = (n + 1)².

Hemos usado la hipótesis en el segundo paso. Por el principio de inducción, la igualdad vale para todo n ≥ 1. ∎

**Dónde suelen restar puntos:**

- No decir explícitamente cuál es el «siguiente término». Escribe 2(n + 1) − 1 = 2n + 1; no des por obvio el salto.
- Suponer la hipótesis «para todo n» en vez de «para algún n». Si la supones para todo n ya tienes lo que quieres demostrar.
- Olvidar el caso base. Sin él, el paso inductivo es una cadena sin primer eslabón.

**Verificación por dos caminos independientes:**

1. Caso concreto: n = 4 → 1 + 3 + 5 + 7 = 16 = 4². ✓
2. Fórmula de la suma aritmética: n términos, primero 1, último 2n − 1, suma = n · (1 + 2n − 1) / 2 = n · 2n / 2 = n². ✓

La segunda vía es una demostración alternativa, no inductiva; sirve para convencerte de que el enunciado es cierto antes de pelearte con la forma.""",
            },
        ]
    },
    # 4) Invariante de paridad: tablero mutilado.
    {
        "messages": [
            {"role": "user", "content": "A un tablero de ajedrez le quito dos esquinas opuestas. Quedan 62 casillas. ¿Puedo cubrirlo con 31 fichas de dominó de 2x1? Llevo media hora probando y no lo consigo."},
            {
                "role": "assistant",
                "content": """No se puede, y no es cuestión de insistir: hay una prueba de imposibilidad en tres líneas.

**1. Encuentra un invariante.** Cada dominó, se coloque donde se coloque (horizontal o vertical), cubre exactamente **una casilla blanca y una negra**, porque dos casillas adyacentes siempre tienen colores distintos. Así que cualquier recubrimiento con 31 dominós cubre 31 blancas y 31 negras.

**2. Cuenta lo que hay.** Las esquinas opuestas de un tablero de ajedrez son del **mismo color** (a1 y h8 son ambas negras). Al quitarlas quedan 32 casillas de un color y 30 del otro.

**3. Contradicción.** Un recubrimiento necesitaría 31 y 31; el tablero ofrece 32 y 30. Imposible.

Por eso no lo consigues: cada intento acaba con dos casillas libres del mismo color, que no pueden compartir dominó.

**Verificación con un caso pequeño.** Tablero 2×2 sin dos esquinas opuestas: quedan 2 casillas en diagonal, del mismo color, no adyacentes. Un solo dominó no las cubre. El mismo argumento, en miniatura.

**Qué sí funciona.** Si quitas dos casillas de colores *distintos*, cualesquiera, siempre se puede (teorema de Gomory): existe un ciclo hamiltoniano por el tablero, y quitar una blanca y una negra lo parte en dos caminos de longitud par que se cubren con dominós.

La técnica general vale para muchos acertijos: busca una cantidad que ninguna jugada cambia (paridad, coloración, suma módulo algo) y comprueba si el estado final la respeta.""",
            },
        ]
    },
    # 5) Bayes con números, multiturno con segundo test.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Una prueba detecta una enfermedad con 99% de sensibilidad y 95% de especificidad. La enfermedad la tiene el 1% de la población. Me ha dado positivo. ¿Qué probabilidad tengo de estar enfermo? Supongo que como 99%..."},
            {
                "role": "assistant",
                "content": """Alrededor del **17 %**, no del 99 %. El 99 % es la probabilidad de dar positivo *si* estás enfermo; tú quieres la inversa, la probabilidad de estar enfermo *dado que* has dado positivo, y para eso cuenta mucho lo rara que es la enfermedad.

**Método 1: frecuencias naturales** (el más difícil de equivocar). Imagina 10 000 personas:

- Enfermas: 1 % → 100. De ellas dan positivo el 99 % → **99 verdaderos positivos**.
- Sanas: 9 900. La especificidad es 95 %, así que el 5 % da positivo por error → **495 falsos positivos**.
- Positivos totales: 99 + 495 = 594.
- P(enfermo | positivo) = 99 / 594 = 1/6 ≈ **16,7 %**.

Los falsos positivos ganan porque hay 99 sanos por cada enfermo: un 5 % de muchos es más que un 99 % de pocos.

**Método 2: fórmula de Bayes** (verificación):

P(E | +) = P(+ | E) · P(E) / [P(+ | E) · P(E) + P(+ | ¬E) · P(¬E)]
= 0,99 · 0,01 / (0,99 · 0,01 + 0,05 · 0,99)
= 0,0099 / (0,0099 + 0,0495) = 0,0099 / 0,0594 = 0,1667.

Coincide.

**Lo que sí cambia el positivo:** antes de la prueba tu probabilidad era 1 %; ahora es 17 %. El test ha multiplicado tu riesgo por 17, es informativo. Lo que no hace es confirmar nada por sí solo. Por eso en cribados de enfermedades poco frecuentes el protocolo es repetir con una segunda prueba, idealmente de otro tipo.""",
            },
            {"role": "user", "content": "Vale, me repiten la prueba y vuelve a dar positivo. ¿Ahora sí?"},
            {
                "role": "assistant",
                "content": """Ahora sube a **~80 %**, asumiendo que los dos resultados son independientes dado tu estado real (misma persona, pero el error de la prueba no se repite sistemáticamente). Si el segundo test es del mismo tipo y la causa del falso positivo es algo de tu organismo, los errores están correlacionados y el salto es menor; por eso se prefiere una prueba distinta.

**Cálculo con odds** (la forma más limpia de encadenar evidencia):

- Odds previas tras el primer positivo: 1/6 enfermo frente a 5/6 sano → 1 : 5.
- Razón de verosimilitud de un positivo: sensibilidad / (1 − especificidad) = 0,99 / 0,05 = 19,8.
- Odds posteriores: 1 × 19,8 : 5 = 19,8 : 5 ≈ 3,96 : 1.
- Probabilidad: 3,96 / (3,96 + 1) = 0,798 ≈ **80 %**.

**Verificación con frecuencias**, partiendo de los 594 positivos de antes:

- 99 enfermos → 98 dan positivo otra vez (99 × 0,99 = 98,01).
- 495 sanos → 24,75 dan positivo otra vez (495 × 0,05).
- 98,01 / (98,01 + 24,75) = 98,01 / 122,76 = 0,798. ✓

Cada positivo multiplica las odds por 19,8: de 1:99 (base) a 1:5 (un positivo) a ~4:1 (dos positivos). Un tercero te llevaría a ~79:1, es decir, 98,7 %.""",
            },
        ]
    },
    # 6) Monty Hall, usuario en inglés pide respuesta en español.
    {
        "messages": [
            {"role": "user", "content": "Can you explain the Monty Hall problem properly? Every explanation I read says 'switch, it's 2/3' but I still feel like once a door is open it's 50/50. Please answer in Spanish, I'm practicing."},
            {
                "role": "assistant",
                "content": """Cambiar de puerta gana con probabilidad 2/3; quedarse, con 1/3. Tu intuición del 50/50 falla por un detalle que las explicaciones cortas se saltan: **el presentador no abre una puerta al azar**. Sabe dónde está el coche y siempre abre una puerta con cabra. Esa regla es la que mueve la probabilidad.

**1. Enumerar los tres casos.** Supón que eliges la puerta 1. El coche está en 1, 2 o 3 con igual probabilidad.

| Coche en | El presentador abre | Si te quedas | Si cambias |
|---|---|---|---|
| 1 | 2 o 3 (cualquiera) | ganas | pierdes |
| 2 | 3 (obligado) | pierdes | ganas |
| 3 | 2 (obligado) | pierdes | ganas |

Cambiar gana en 2 de 3 casos. Fíjate en que en los casos 2 y 3 el presentador no tiene elección: está obligado a señalarte, por descarte, dónde está el coche.

**2. La forma de verlo sin tabla.** Tu primera elección acierta 1/3 de las veces, y nada de lo que haga el presentador después cambia eso: él siempre puede abrir una puerta con cabra, elijas lo que elijas. Así que el 2/3 restante sigue estando en «las otras puertas», y después de abrir una, todo ese 2/3 se concentra en la que queda cerrada.

**3. Versión con 100 puertas.** Eliges una (1 % de acierto). El presentador abre 98 con cabra y deja una cerrada. ¿De verdad crees que tu elección inicial y esa puerta que él ha dejado cerrada a propósito valen lo mismo?

**Por qué «quedan dos puertas, luego 50/50» es falso.** Dos opciones no implican dos opciones equiprobables. Comprar un billete de lotería también deja dos resultados (ganar o no) y nadie diría que es 50/50. La probabilidad la fija el proceso que genera la situación, no el número de alternativas.

**Verificación: la variante donde sí es 50/50.** Si el presentador *no* supiera dónde está el coche, abriera una puerta al azar y por casualidad saliera una cabra, entonces cambiar o quedarse daría 1/2. Con la tabla: en el caso «coche en 2», la mitad de las veces abriría la 2 y revelaría el coche; esos casos se descartan, y entre los que sobreviven, quedarse y cambiar ganan por igual. Que el resultado cambie al cambiar la regla del presentador es la prueba de que esa regla es lo que importa.""",
            },
        ]
    },
    # 7) Esperanza del máximo de dos dados, rioplatense.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con precisión y mostrando las cuentas."},
            {"role": "user", "content": "Un amigo me propone un juego: tiro dos dados y me paga en pesos el valor del dado más alto. Me cobra 5 pesos por jugar. ¿Me conviene?"},
            {
                "role": "assistant",
                "content": """No te conviene: el pago esperado es **161/36 ≈ 4,47 pesos** por tirada, así que pagando 5 perdés en promedio 0,53 por jugada. A la larga, tu amigo se queda con un 10,6 % de lo que apostás.

**Cálculo directo.** Sea M el máximo de los dos dados. P(M ≤ k) = (k/6)², porque los dos dados tienen que salir ≤ k. Entonces:

P(M = k) = P(M ≤ k) − P(M ≤ k−1) = (k² − (k−1)²)/36 = (2k − 1)/36.

| k | P(M = k) | k · P |
|---|---|---|
| 1 | 1/36 | 1/36 |
| 2 | 3/36 | 6/36 |
| 3 | 5/36 | 15/36 |
| 4 | 7/36 | 28/36 |
| 5 | 9/36 | 45/36 |
| 6 | 11/36 | 66/36 |

Las probabilidades suman 36/36 (bien). E[M] = (1 + 6 + 15 + 28 + 45 + 66)/36 = 161/36 = 4,472.

**Verificación por otro camino** (fórmula de la cola para variables enteras no negativas): E[M] = Σ P(M > k) para k = 0 … 5 = Σ (1 − (k/6)²) = 6 − (0 + 1 + 4 + 9 + 16 + 25)/36 = 6 − 55/36 = (216 − 55)/36 = 161/36. ✓

**Qué precio sería justo.** Cualquier cobro menor que 4,47 te favorece; 4,47 exacto es juego parejo. Si tu amigo acepta cobrarte 4 pesos, ganás 0,47 por tirada en promedio. Y ojo con la varianza: en 20 tiradas la desviación típica de tu resultado es de unos 6 pesos, así que a corto plazo podés ganar o perder bastante más que lo que dice la esperanza. La esperanza te dice quién gana *a la larga*, no qué pasa hoy.""",
            },
        ]
    },
    # 8) Estimación de Fermi técnica con supuestos declarados.
    {
        "messages": [
            {"role": "user", "content": "Tenemos unos 500 microservicios y quieren centralizar los logs con retención de 30 días. Me piden una estimación de almacenamiento para pedir presupuesto y no tengo métricas aún. ¿Cómo lo estimo sin inventarme el número?"},
            {
                "role": "assistant",
                "content": """Estimación de orden de magnitud: **del orden de 0,5 TB comprimidos (5 TB sin comprimir) para 30 días**, con un rango razonable entre 100 GB y 5 TB según el tráfico real. Lo importante es dejar los supuestos a la vista para que quien apruebe el presupuesto pueda discutirlos uno por uno.

**Supuestos (cámbialos por tus datos en cuanto los tengas):**

1. Tráfico medio por servicio: 10 peticiones/s. La mayoría de los servicios internos están muy por debajo; unos pocos de borde muy por encima. 10 es una media conservadora.
2. Líneas de log por petición: 2 (entrada y salida, o una línea más un error ocasional).
3. Tamaño por línea: 200 bytes. JSON estructurado con timestamp, nivel, trace id, servicio y mensaje corto ronda 150-300.
4. Compresión en el almacén: 10:1. Los logs se comprimen muy bien (campos repetidos); Loki o Elasticsearch con compresión suelen quedar entre 5:1 y 15:1.

**Cálculo:**

- Líneas por segundo: 500 × 10 × 2 = 10 000 líneas/s.
- Bytes por segundo: 10 000 × 200 B = 2 MB/s.
- Por día: 2 MB/s × 86 400 s ≈ 173 GB/día.
- 30 días: ≈ 5,2 TB sin comprimir.
- Comprimido 10:1: ≈ **520 GB**.

**Verificación por cotas.** Si el tráfico medio real fuera 1 req/s (sistema tranquilo), todo se divide por 10: 52 GB comprimidos. Si fuera 100 req/s, 5,2 TB comprimidos. Cualquier cifra fuera de ese rango de dos órdenes de magnitud indicaría un supuesto roto (por ejemplo, un servicio que loguea el cuerpo de cada petición).

**Lo que haría antes de enviar el presupuesto:**

- Medir un día real en 5 servicios representativos (uno de borde, dos medianos, dos internos) con `du` sobre sus logs rotados. Con eso sustituyes los supuestos 1-3 por datos.
- Pedir un 30-50 % de margen sobre la estimación y réplica ×2 si el almacén la exige (Elasticsearch con una réplica duplica el disco).
- Añadir a la cifra una política: nivel `DEBUG` desactivado en producción y cuerpos de petición fuera de los logs. Esos dos puntos mueven la estimación más que cualquier otro.""",
            },
        ]
    },
    # 9) Planificación con dependencias: camino crítico.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": """Tengo que planificar esto con 2 personas:

- A: diseñar el esquema de datos, 3 días
- B: migración de datos, 2 días, necesita A terminada
- C: implementar la API, 4 días, necesita A terminada
- D: pruebas de integración, 1 día, necesita B y C

¿Cuál es el mínimo de días y cómo reparto el trabajo? Mi jefe dice que con 2 personas debería salir en 5 días (10 días-persona / 2)."""},
            {
                "role": "assistant",
                "content": """El mínimo es **8 días**, no 5. La cuenta de tu jefe (días-persona / personas) supone que todo el trabajo es paralelizable, y las dependencias lo impiden.

**1. Camino crítico.** Sigue la cadena de dependencias más larga:

- A → B → D: 3 + 2 + 1 = 6 días.
- A → C → D: 3 + 4 + 1 = **8 días**.

Ninguna asignación de personas puede bajar de 8, porque C no puede empezar hasta que A acabe y D no puede empezar hasta que C acabe. Es una cota inferior independiente del número de personas.

**2. Un reparto que alcanza los 8 días:**

| Días | Persona 1 | Persona 2 |
|---|---|---|
| 1-3 | A (esquema) | libre para la cadena |
| 4-7 | C (API) | B (migración), días 4-5 |
| 8 | D (integración) | — |

Como la cota inferior (8) coincide con lo que consigue este plan, el plan es óptimo. No hace falta buscar más.

**3. Verificación por otro camino.** Con una sola persona serían 3 + 2 + 4 + 1 = 10 días. La segunda persona solo ahorra los días en los que hay dos tareas listas a la vez: B y C coinciden tras A, y B dura 2, así que el ahorro máximo es de 2 días → 10 − 2 = 8. ✓ Una tercera persona no ahorraría nada: nunca hay tres tareas listas simultáneamente.

**4. Qué hacer con la holgura.** B tiene 2 días de holgura (puede terminar el día 7 sin retrasar D). La persona 2 está libre los días 1-3 y 6-7; eso es tiempo útil para preparar el entorno de pruebas de D o escribir los scripts de migración antes de que A termine, lo que probablemente recorte B.

**La respuesta para tu jefe:** «8 días por el camino crítico A→C→D; los 5 días exigirían que la API se pudiera empezar sin tener el esquema. Si quieres acortar, la única palanca es partir A: entregar el esquema de las tablas que necesita la API el día 2 y seguir con el resto en paralelo.»""",
            },
        ]
    },
    # 10) Acertijo con trampa: el usuario trae su respuesta intuitiva.
    {
        "messages": [
            {"role": "user", "content": "Un bate y una pelota cuestan 1,10 €. El bate cuesta 1 € más que la pelota. La pelota cuesta 10 céntimos, ¿verdad? Me han dicho que está mal y no veo por qué."},
            {
                "role": "assistant",
                "content": """La pelota cuesta **5 céntimos**, y el bate 1,05 €.

**Por qué 10 céntimos está mal.** Si la pelota costara 0,10 €, el bate costaría 1 € más: 1,10 €. Y los dos juntos sumarían 1,20 €, no 1,10 €. La respuesta intuitiva solo comprueba la primera frase del enunciado y se olvida de la segunda.

**La trampa.** El cerebro lee «1,10 €» y «1 € más» y resta: 1,10 − 1 = 0,10. Pero el enunciado no dice que el bate cueste 1 €; dice que cuesta *1 € más que la pelota*. Ese euro de diferencia hay que repartirlo sobre el total.

**Resolución:**

- Sea p el precio de la pelota. El bate cuesta p + 1.
- p + (p + 1) = 1,10 → 2p = 0,10 → p = 0,05.

**Verificación, las dos condiciones del enunciado:**

1. Suma: 0,05 + 1,05 = 1,10 €. ✓
2. Diferencia: 1,05 − 0,05 = 1,00 €. ✓

Con 10 céntimos solo se cumple la segunda; con 5 se cumplen las dos.

**Forma de no caer en estas:** cuando una respuesta sale «a la primera», sustitúyela en *todas* las frases del enunciado antes de darla por buena. Aquí la comprobación tarda cinco segundos y la trampa se deshace sola.""",
            },
        ]
    },
    # 11) Acertijo con trampa: el euro que falta.
    {
        "messages": [
            {"role": "user", "content": "Tres amigos pagan 30 € por una habitación (10 cada uno). El dueño se da cuenta de que cuesta 25 y manda al botones a devolver 5 €. El botones se queda 2 y devuelve 1 a cada uno. Así que cada uno pagó 9 € → 27 €, más los 2 del botones son 29. ¿Dónde está el euro que falta?"},
            {
                "role": "assistant",
                "content": """No falta ningún euro. La trampa está en la última suma: **los 2 € del botones ya están dentro de los 27 €**, así que sumarlos otra vez cuenta el mismo dinero dos veces.

**Sigue el dinero, no el relato.** Hay 30 € al principio. Al final:

- Dueño: 25 €
- Botones: 2 €
- Amigos: 3 € (1 € cada uno)

25 + 2 + 3 = 30. Todo cuadra.

**Qué pagaron realmente los amigos.** 27 € en total (9 cada uno). ¿A dónde fueron esos 27? Al dueño (25) y al botones (2). La ecuación correcta es:

27 = 25 + 2

y no «27 + 2 = 29». Los 2 del botones son *parte* de lo que pagaron, no algo aparte.

**Por qué engaña.** El enunciado mezcla dos sentidos de «el dinero»: lo que *salió* de los bolsillos de los amigos (27) y lo que *recibieron* otros (25 + 2 + 3 devueltos = 30). Junta un número de la primera columna con uno de la segunda y espera que den 30. No hay ninguna razón para que lo hagan; 29 es un número sin significado.

**Verificación con cifras distintas**, para ver que el «agujero» es arbitrario: si el botones se hubiera quedado 4 € y devuelto 1 € en total, cada amigo habría pagado 9,67 € → 29 €, «más 4» = 33 €. Ahora «sobran» 3. Un sistema donde a veces falta 1 y a veces sobran 3 no está describiendo nada real: la suma está mal planteada.""",
            },
        ]
    },
    # 12) Proporcionalidad con trampa (gallina y media), léxico de México.
    {
        "messages": [
            {"role": "user", "content": "Oye, mi sobrina me trajo esta tarea y me trabé: si gallina y media pone huevo y medio en día y medio, ¿cuántos huevos ponen 3 gallinas en 3 días? Yo le dije que 3 pero ella dice que la maestra dijo que no."},
            {
                "role": "assistant",
                "content": """Son **6 huevos**. La maestra tiene razón.

**La trampa.** «Gallina y media, huevo y medio, día y medio» invita a pensar «una gallina pone un huevo al día» y de ahí 3 gallinas × 3 días = 9, o bien «todo es 1,5, entonces con 3 todo se duplica» y salen 3. Ninguna de las dos sigue el enunciado.

**Calcula el ritmo de UNA gallina:**

1. 1,5 gallinas ponen 1,5 huevos en 1,5 días.
2. Entonces 1 gallina pone 1 huevo en 1,5 días (divides gallinas y huevos entre 1,5; los días no cambian).
3. Ritmo: 1 / 1,5 = 2/3 de huevo por gallina por día.

**Aplica el ritmo:** 3 gallinas × 3 días × 2/3 = 6 huevos.

**Verificación por escalado, sin fracciones:**

- Duplico las gallinas: 3 gallinas ponen 3 huevos en 1,5 días.
- Duplico los días: 3 gallinas ponen 6 huevos en 3 días. ✓

Dos caminos, mismo número.

**Cómo explicárselo a tu sobrina:** la pregunta esconde que cada gallina tarda día y medio en poner un huevo, no un día. En 3 días le da tiempo a poner 2. Tres gallinas, 2 cada una: 6.""",
            },
        ]
    },
    # 13) Datos insuficientes: velocidad media, multiturno.
    {
        "messages": [
            {"role": "user", "content": "Un coche hace la primera mitad de un viaje a 100 km/h y la segunda mitad a 50 km/h. ¿Cuál es la velocidad media? Yo digo 75."},
            {
                "role": "assistant",
                "content": """El enunciado es ambiguo y la respuesta depende de qué significa «mitad»: la mitad de la **distancia** o la mitad del **tiempo**. Con la lectura habitual (mitad de la distancia) la respuesta es **66,7 km/h**, no 75.

**Caso 1: mitad de la distancia** (lo normal cuando se habla de un trayecto). Toma un viaje de 200 km:

- Primeros 100 km a 100 km/h → 1 h.
- Segundos 100 km a 50 km/h → 2 h.
- Velocidad media = distancia / tiempo = 200 / 3 = **66,7 km/h**.

El coche pasa el doble de tiempo en el tramo lento, así que la media se inclina hacia 50. En general es la media armónica: 2 / (1/100 + 1/50) = 2 / 0,03 = 66,7.

**Caso 2: mitad del tiempo.** Si viaja t horas a 100 y t horas a 50, recorre 150t km en 2t horas → **75 km/h**. Aquí sí vale la media aritmética, porque cada velocidad pesa el mismo tiempo.

**Verificación del caso 1 con otra distancia**, para ver que no depende de los 200 km: 100 km en total → 50 km a 100 (0,5 h) + 50 km a 50 (1 h) = 100 km en 1,5 h = 66,7 km/h. ✓

**Por qué 75 engaña.** La velocidad media es distancia total entre tiempo total, no el promedio de las velocidades. Promediar velocidades solo funciona cuando duran el mismo tiempo. Caso extremo que lo deja claro: si la segunda mitad de la distancia la haces a 0 km/h, nunca llegas y la media es 0, no 50.""",
            },
            {"role": "user", "content": "Era mitad de la distancia. Otra del mismo estilo: si la primera mitad la hace a 50 km/h, ¿a qué velocidad tiene que ir la segunda mitad para que la media sea 100?"},
            {
                "role": "assistant",
                "content": """Es imposible: ninguna velocidad finita lo consigue.

**Razón.** Para promediar 100 km/h en un viaje de 200 km hay que completarlo en 2 h. Pero la primera mitad, 100 km a 50 km/h, ya gasta exactamente 2 h. Para la segunda mitad queda tiempo cero: habría que recorrer 100 km en 0 segundos.

**Fórmula general.** Con la primera mitad a v₁ y media objetivo v, la segunda mitad necesita

v₂ = 1 / (2/v − 1/v₁).

Con v₁ = 50 y v = 100: 2/100 − 1/50 = 0,02 − 0,02 = 0 → división por cero. Y si pidieras una media mayor que 100, el denominador saldría negativo: tiempo negativo, tampoco tiene sentido. La condición para que exista solución es v < 2·v₁: la media nunca puede llegar al doble de la velocidad del primer tramo.

**Verificación con un objetivo alcanzable**, para ver que la fórmula funciona: primera mitad a 50, media deseada 80. Tiempo total disponible: 200/80 = 2,5 h; usado: 2 h; quedan 0,5 h para 100 km → 200 km/h. Con la fórmula: 1 / (2/80 − 1/50) = 1 / (0,025 − 0,02) = 1 / 0,005 = 200. ✓

**Por qué engaña.** La intuición dice «fui a 50, voy a 150 y promedio 100». Eso valdría si los dos tramos duraran lo mismo, pero el tramo lento siempre dura más que el rápido cuando las distancias son iguales. A 150 km/h la segunda mitad tarda 0,67 h, el total es 2,67 h y la media queda en 200/2,67 = 75 km/h.""",
            },
        ]
    },
    # 14) Datos insuficientes: significación estadística bajo supuestos explícitos.
    {
        "messages": [
            {"role": "user", "content": "La conversión de nuestra landing bajó del 3% al 2,5% después del rediseño. Marketing dice que el rediseño la ha hundido. ¿Es una caída real o puede ser ruido?"},
            {
                "role": "assistant",
                "content": """Con solo los porcentajes no se puede saber: hace falta el **número de visitas** detrás de cada cifra. Una caída de 0,5 puntos es ruido con mil visitas y una señal clarísima con cien mil. Te doy el cálculo para los dos extremos y el umbral a partir del cual es creíble.

**Método (test de dos proporciones).** Con p₁ = 0,03, p₂ = 0,025 y n visitas en cada periodo, la proporción conjunta es p = 0,0275 y el error estándar de la diferencia es

SE = √(p · (1 − p) · (1/n + 1/n)) = √(0,0275 · 0,9725 · 2/n) = √(0,0535 / n).

El estadístico es z = 0,005 / SE; se considera significativo a partir de |z| ≈ 1,96.

| Visitas por periodo | SE | z | Conclusión |
|---|---|---|---|
| 1 000 | 0,0073 | 0,68 | ruido: una diferencia así aparece por azar casi la mitad de las veces |
| 17 000 | 0,0018 | 2,8 | diferencia detectable con potencia razonable |
| 100 000 | 0,00073 | 6,8 | real sin ninguna duda estadística |

**Tamaño mínimo.** Para detectar 0,5 puntos con 80 % de potencia hacen falta unas (1,96 + 0,84)² · 0,0535 / 0,005² ≈ 7,84 · 0,0535 / 0,000025 ≈ **17 000 visitas por periodo**. Verificación: con n = 17 000, SE = √(0,0535/17 000) = 0,00177 y z = 0,005/0,00177 = 2,8, que es justo 1,96 + 0,84. ✓

**El problema más grave no es el tamaño de muestra.** Esto es un «antes y después», no un test A/B. Aunque la caída sea estadísticamente real, puede deberse a cualquier cosa que cambiara a la vez que el rediseño:

- Mezcla de tráfico distinta (una campaña de pago nueva trae visitantes que convierten menos).
- Estacionalidad o día de la semana.
- Un cambio en cómo se mide la conversión (evento de analítica movido en el rediseño).

**Qué haría:** (1) pedir n de cada periodo y repetir la cuenta de arriba; (2) comparar la conversión *por fuente de tráfico*, que es donde suele aparecer el culpable; (3) si se puede, servir el diseño antiguo al 50 % durante dos semanas. Ese A/B es el único dato que puede confirmar la afirmación de marketing o descartarla.""",
            },
        ]
    },
    # 15) Paradoja de Simpson con números.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "No entiendo cómo un hospital puede tener mejor tasa de supervivencia que otro en pacientes leves Y en pacientes graves, pero peor tasa en total. Me suena a error en los datos."},
            {
                "role": "assistant",
                "content": """No es un error: es la **paradoja de Simpson**, y pasa siempre que los dos grupos tienen mezclas de pacientes muy distintas. Aquí tienes números que lo reproducen.

| | Hospital A | Hospital B |
|---|---|---|
| Leves | 90/100 sobreviven = **90 %** | 765/900 = 85 % |
| Graves | 210/300 = **70 %** | 60/100 = 60 % |
| Total | 300/400 = 75 % | 825/1000 = **82,5 %** |

A es mejor en leves (90 > 85) y mejor en graves (70 > 60), pero peor en total (75 < 82,5).

**Por qué.** El total es una media ponderada de las dos tasas, y los pesos son la proporción de cada tipo de paciente:

- A: 25 % leves, 75 % graves → 0,25 · 90 + 0,75 · 70 = 22,5 + 52,5 = 75 %.
- B: 90 % leves, 10 % graves → 0,90 · 85 + 0,10 · 60 = 76,5 + 6 = 82,5 %.

Al hospital A le llegan sobre todo pacientes graves (probablemente porque es el de referencia), y los graves sobreviven menos en cualquier sitio. Su total está arrastrado por *a quién trata*, no por *cómo trata*.

**Verificación de que las cifras cuadran:** 90 + 210 = 300 supervivientes de 100 + 300 = 400 pacientes en A; 765 + 60 = 825 de 900 + 100 = 1000 en B. ✓ Y la condición que hace posible la paradoja se cumple: la variable oculta (gravedad) está correlacionada con el hospital *y* con el resultado.

**Qué número es el correcto.** Depende de la pregunta. Si eres un paciente concreto, ya sabes si eres leve o grave: mira tu fila, y A es mejor. Si eres un gestor que quiere saber «¿cuántos mueren en cada hospital?», el total es el dato, pero no dice nada sobre la calidad.

**Cómo detectarla en tus datos.** Siempre que un agregado contradiga los subgrupos, busca la variable de estratificación que está desigualmente repartida. Y antes de comparar totales, pregunta si los dos grupos son comparables; si no lo son, ajusta (estratifica o estandariza por la mezcla de un grupo de referencia).""",
            },
        ]
    },
    # 16) Paradoja del cumpleaños, multiturno.
    {
        "messages": [
            {"role": "user", "content": "¿Es verdad que en un grupo de 23 personas hay más del 50% de probabilidad de que dos cumplan años el mismo día? Me parece poquísima gente para 365 días."},
            {
                "role": "assistant",
                "content": """Es verdad: con 23 personas la probabilidad es del **50,7 %**. Parece poca gente porque la intuición compara 23 con 365, pero lo que importa no son las personas sino los **pares** de personas, y 23 personas forman 253 pares.

**Cálculo exacto.** Es más fácil calcular lo contrario: que *todos* cumplan en días distintos (ignorando el 29 de febrero y suponiendo días equiprobables).

- La 1.ª persona puede cumplir cualquier día: 365/365.
- La 2.ª debe evitar 1 día: 364/365.
- La 3.ª debe evitar 2: 363/365.
- La 23.ª debe evitar 22: 343/365.

P(todos distintos) = 365/365 · 364/365 · ⋯ · 343/365 = 0,4927.

P(al menos una coincidencia) = 1 − 0,4927 = **0,5073**.

**Verificación por aproximación**, que además explica el porqué. Cada par coincide con probabilidad 1/365. Con n personas hay n(n−1)/2 pares; tratándolos como casi independientes:

P(ninguna coincidencia) ≈ exp(−n(n−1) / (2 · 365)) = exp(−253/365) = exp(−0,693) = 0,500.

Da 50 %, a dos décimas del valor exacto. ✓ Y muestra que el umbral está donde n² ≈ 2 · 365 · ln 2 ≈ 506, es decir, n ≈ 22,5. La probabilidad crece con el *cuadrado* del número de personas; por eso 23 bastan.

**Prueba mental rápida:** con 23 personas, ¿cuántas comparaciones haces? 22 + 21 + ⋯ + 1 = 253. Cada una es un «tiro» con 1/365 de acierto. 253 tiros a 1/365 ya rozan la mitad de probabilidad de que alguno entre.""",
            },
            {"role": "user", "content": "¿Y cuánta gente haría falta para llegar al 99%?"},
            {
                "role": "assistant",
                "content": """**57 personas.** Con 57 la probabilidad exacta es del 99,0 %; con 56 se queda en 98,8 %.

**Con la aproximación:** quieres exp(−n²/730) ≈ 0,01 → n² ≈ 730 · ln(100) = 730 · 4,605 = 3 362 → n ≈ 58. La aproximación sobreestima ligeramente (usa n² en vez de n(n−1)), por eso el valor exacto, multiplicando las fracciones hasta 309/365, cae en 57.

**Verificación de que el exacto es coherente:** la aproximación es una cota superior del número necesario (sobrestima n), así que el exacto debe ser ≤ 58. Y como con 56 no se alcanza el 99 %, 57 es el primero. ✓

Tabla de referencia, por si la necesitas:

| Personas | P(coincidencia) |
|---|---|
| 23 | 50,7 % |
| 30 | 70,6 % |
| 41 | 90,3 % |
| 57 | 99,0 % |
| 70 | 99,9 % |

Fíjate en que para el 100 % exacto harían falta 366 personas (principio del palomar: 366 personas y 365 días), pero el 99,9 % se alcanza con 70. La curva sube muy deprisa y luego se arrastra.""",
            },
        ]
    },
    # 17) Análisis de un argumento: correlación, muestra sesgada.
    {
        "messages": [
            {"role": "system", "content": "Eres un analista lógico estricto: identifica la estructura del argumento, nombra la falacia si la hay y da un contraejemplo concreto."},
            {"role": "user", "content": "Un compañero argumenta: «Todos los programadores buenos que conozco usan Vim. Por lo tanto, si usas Vim te conviertes en mejor programador.» Me huele mal pero quiero rebatirlo bien."},
            {
                "role": "assistant",
                "content": """El argumento comete dos errores, uno en la premisa y otro en el salto a la conclusión.

**Estructura.**
- Premisa: los buenos programadores que conozco usan Vim (observación de una muestra).
- Conclusión: usar Vim causa ser mejor programador.

**Error 1: muestra sesgada (sesgo de selección).** «Los que conozco» no es una muestra de los buenos programadores; es una muestra de su entorno. Si trabaja en un equipo de sistemas con cultura de terminal, verá Vim por todas partes, sea quien sea bueno o malo. Además, no dice nada de los *malos* programadores que conoce: si también usan Vim, la premisa no distingue nada. Para que la observación significara algo necesitaría comparar la tasa de Vim entre buenos y malos.

**Error 2: correlación tomada como causalidad (*cum hoc ergo propter hoc*).** Aunque la correlación fuera real, hay al menos tres explicaciones que no son «Vim te mejora»:

1. *Causalidad inversa:* los programadores con años de experiencia tuvieron tiempo de aprender Vim. La habilidad precede al editor.
2. *Causa común:* la curiosidad y el gusto por dominar herramientas producen tanto buenos programadores como usuarios de Vim.
3. *Azar / muestra pequeña:* con cinco o seis personas, cualquier patrón aparece.

**Contraejemplo concreto.** Mismo esquema, conclusión absurda: «Todos los buenos cirujanos que conozco llevan reloj caro; por tanto, si te compras un reloj caro te conviertes en mejor cirujano.» La forma del argumento es idéntica y nadie la aceptaría. Si la forma es inválida aquí, es inválida con Vim.

**Qué evidencia sí apoyaría la conclusión.** Un experimento (o al menos una comparación controlada): programadores de nivel similar, la mitad aprende Vim, se mide su productividad o calidad de código meses después. Sin algo así, lo máximo que se puede decir es «en mi entorno, Vim y ser bueno aparecen juntos».

**Cómo rebatirlo en una frase:** «Eso demuestra que los buenos programadores que conoces eligen Vim, no que Vim los haya hecho buenos; confundes la dirección de la flecha.»""",
            },
        ]
    },
    # 18) Análisis de argumento en inglés: post hoc, confounders.
    {
        "messages": [
            {"role": "user", "content": "My CTO's argument for a rewrite: 'Competitor X moved their backend to Rust last year and their p99 latency dropped 40%. So we should rewrite ours in Rust.' We're a 12-person team on Python/Django. How do I push back without sounding like I'm just scared of Rust?"},
                {
                "role": "assistant",
                "content": """The argument has a real observation and an invalid inference. Separate the two and the pushback writes itself.

**Structure.**
- Observation: X rewrote in Rust; X's p99 dropped 40%.
- Hidden premise: the rewrite *caused* the drop, and the same cause would produce the same effect for us.
- Conclusion: we should rewrite in Rust.

**Problem 1: post hoc reasoning.** "After the rewrite, latency dropped" is not "because of the rewrite." A rewrite is never *only* a language change. In the same project they almost certainly:

- redesigned the data model and dropped years of accumulated hacks,
- fixed the three slow queries everyone knew about,
- added caching, changed infrastructure, retuned the database.

Any of those alone can cut p99 by 40%. The language is the most visible change, so it gets the credit. This is the classic second-system effect read backwards: the win comes from *starting over with knowledge*, not from the new tool.

**Problem 2: survivorship.** You hear about X because their rewrite worked. Companies whose rewrite took two years and shipped nothing do not publish blog posts. One success story is a sample of size one from a biased population.

**Problem 3: the inference assumes our bottleneck is theirs.** p99 latency in a Django service is usually dominated by I/O: database round trips, N+1 queries, external calls, lock contention. Rust does not make PostgreSQL faster. If your profile shows 85% of request time waiting on the database, a rewrite changes the remaining 15%.

**What to say instead of "no".** Reframe from language to evidence:

1. "Let's measure where our p99 actually goes." Run a profiler and a query log for a week. This costs days, not years.
2. "Let's try the cheap version of their win." Fix the top five slow endpoints in Python. If p99 drops 30% in a month, the rewrite argument collapses on its own.
3. "If after that CPU-bound code is the bottleneck, let's move *that module* to Rust via PyO3." A targeted port is reversible and keeps the team productive.

**One-sentence version for the meeting:** "X's number is real, but we do not know how much of it was Rust and how much was the redesign; before we bet 12 people for 18 months, let's spend two weeks finding out what *our* p99 is made of."

That is not fear of Rust. It is refusing to spend the largest budget on the least-tested hypothesis.""",
            },
        ]
    },
    # 19) Teoría de juegos: dilema del prisionero, multiturno (repetido).
    {
        "messages": [
            {"role": "user", "content": "Explícame el dilema del prisionero con números, y por qué se dice que lo 'racional' es traicionar si claramente a los dos les iría mejor callando."},
            {
                "role": "assistant",
                "content": """Lo racional *individualmente* es traicionar; lo mejor *colectivamente* es callar. El dilema está en que las dos cosas son verdad a la vez.

**Los números** (años de cárcel; menos es mejor):

| | B calla | B traiciona |
|---|---|---|
| **A calla** | A: 1, B: 1 | A: 10, B: 0 |
| **A traiciona** | A: 0, B: 10 | A: 5, B: 5 |

**Razonamiento de A**, caso por caso:

- Si B calla: traicionando saco 0 en vez de 1. Mejor traicionar.
- Si B traiciona: traicionando saco 5 en vez de 10. Mejor traicionar.

Traicionar es mejor *haga lo que haga B*: es una **estrategia dominante**. B razona igual. Resultado: los dos traicionan y se llevan 5 años cada uno. Ese es el único equilibrio de Nash: nadie mejora cambiando solo su jugada.

**Por qué callar no es estable aunque sea mejor (1 y 1).** Desde (callar, callar), A mira la tabla y ve que pasando a traicionar baja de 1 a 0. Tiene incentivo a desviarse. Y sabe que B tiene el mismo incentivo. «Yo callo si tú callas» no es sostenible sin un mecanismo que castigue la desviación, y en una sola jugada sin comunicación vinculante no lo hay.

**Verificación de que es un dilema y no solo un juego cualquiera.** Las condiciones son T > R > P > S con T = 0 años (tentación), R = 1 (recompensa mutua), P = 5 (castigo mutuo), S = 10 (el que calla solo). En «menos es mejor»: 0 < 1 < 5 < 10. ✓ Si cambiaras un número y rompieras ese orden (por ejemplo, el traidor solitario recibe 2 años en vez de 0), callar dejaría de ser dominado y el dilema desaparece.

**Dónde aparece de verdad.** Dos empresas decidiendo si bajan precios, dos países decidiendo si se arman, dos equipos decidiendo si dedican tiempo a tests que benefician al otro. El patrón es siempre el mismo: lo que a cada uno le conviene por separado los empobrece a los dos.""",
            },
            {"role": "user", "content": "¿Y si el juego se repite muchas veces? Ahí la cosa cambia, ¿no?"},
            {
                "role": "assistant",
                "content": """Cambia si el número de repeticiones es **indefinido** (no se sabe cuándo acaba). Si es conocido y finito, no cambia nada, y vale la pena ver por qué.

**Repetición finita y conocida (por ejemplo, 10 rondas).** Razona desde el final: en la ronda 10 no hay futuro que proteger, así que los dos traicionan. Sabiendo eso, en la ronda 9 tampoco hay nada que ganar cooperando (la 10 ya está perdida), así que traicionan. Y así hasta la ronda 1. La inducción hacia atrás deshace la cooperación entera. En experimentos reales la gente coopera hasta cerca del final, pero el equilibrio teórico es traicionar siempre.

**Repetición indefinida.** Ahora la amenaza «si me traicionas, te traiciono después» tiene dientes. Con la estrategia *gatillo*: coopero mientras cooperes; a la primera traición, traiciono para siempre. Para A, con factor de descuento δ (cuánto vale la siguiente ronda respecto a esta):

- Cooperar siempre: 1 + δ + δ² + ⋯ = 1 / (1 − δ) años.
- Traicionar hoy y sufrir después: 0 + 5δ + 5δ² + ⋯ = 5δ / (1 − δ) años.

Cooperar compensa cuando 1/(1−δ) ≤ 5δ/(1−δ), es decir, **δ ≥ 0,2**. Con estos pagos basta con que la siguiente ronda valga un 20 % de la actual: la cooperación es sostenible con un futuro muy modesto.

**Verificación con δ = 0,5:** cooperar cuesta 1/(1−0,5) = 2 años-equivalentes; traicionar, 5·0,5/0,5 = 5. Cooperar gana. Con δ = 0,1: cooperar 1,11, traicionar 0,56. Traicionar gana. El umbral 0,2 está entre ambos. ✓

**Qué estrategia usar en la práctica.** *Tit-for-tat* (coopera en la primera; luego repite lo que hizo el otro) ganó los torneos de Axelrod porque es amable, se venga rápido, perdona rápido y es fácil de leer. Su debilidad es el ruido: un error de interpretación desata venganzas alternas. Por eso en entornos con ruido funciona mejor una variante generosa que perdona una traición de cada diez.

La moraleja para el mundo real: la cooperación no nace de la bondad sino de la **sombra del futuro**. Si quieres que dos equipos cooperen, haz que sepan que volverán a trabajar juntos.""",
            },
        ]
    },
    # 20) Teoría de juegos: 2/3 de la media, léxico colombiano.
    {
        "messages": [
            {"role": "user", "content": "En la oficina hicimos un juego: cada uno escribe un número entre 0 y 100 y gana el que más se acerque a los 2/3 del promedio de todos. Yo puse 50 y perdí feo. ¿Cuál era el número correcto?"},
            {
                "role": "assistant",
                "content": """Depende de contra quién juegues. Contra jugadores perfectamente racionales, la única respuesta es **0**. Contra la oficina, el número ganador suele estar entre **20 y 25**. Lo interesante es el razonamiento que lleva de uno al otro.

**Paso 1: eliminar lo dominado.** El promedio no puede pasar de 100, así que 2/3 del promedio no pasa de 66,7. Escribir más de 67 nunca gana: cualquier número así está dominado.

**Paso 2: iterar.** Si todos saben el paso 1, nadie escribe más de 67, el promedio no pasa de 67 y el objetivo no pasa de 44,4. Si todos saben eso, el objetivo no pasa de 29,6. Luego 19,8; 13,2; 8,8 … La secuencia 100 · (2/3)ᵏ tiende a 0. Con racionalidad común (todos saben que todos saben, hasta el infinito), todos escriben 0.

**Verificación de que 0 es equilibrio.** Si todos ponen 0, el objetivo es 0 y nadie gana más desviándose: cualquier número positivo queda más lejos. ✓ Y es el único: si alguien escribe x > 0, el objetivo es menor que x (es 2/3 de algo ≤ x), así que ese jugador mejoraría bajando.

**Por qué 50 perdió feo.** 50 corresponde a «nivel 0» de razonamiento: escribir el centro sin pensar en los demás. Ya el primer paso de la cadena lo descarta.

**Por qué 0 también pierde en la oficina.** La gente real hace una o dos iteraciones, no infinitas. En experimentos con grupos grandes el promedio queda en 30-40 y gana quien escribe cerca de 22-25 (dos pasos de razonamiento). Escribir 0 solo gana si todos los demás también razonan hasta el final, cosa que no ocurrió, visto que ustedes no lo hicieron.

**El criterio general:** en estos juegos no se trata de ser el más listo, sino de estimar *cuántos pasos* razonan los demás y dar **uno más**. Si crees que la oficina llega a nivel 1 (33), tú pones 22. Si creen que llegan a 2, pones 15. Y si vuelven a jugar la semana que viene, todos habrán aprendido y el número bajará: el juego cambia cada vez que se repite.""",
            },
        ]
    },
    # 21) Razonamiento temporal: horario de verano, multiturno.
    {
        "messages": [
            {"role": "user", "content": "Tengo una tarea programada todos los días a las 02:30 hora de Madrid. ¿Hay algún día del año en que eso dé problemas? Lo pregunto porque en marzo nos faltó una ejecución y no entendemos por qué."},
            {
                "role": "assistant",
                "content": """Sí: **las 02:30 del último domingo de marzo no existen** en Madrid, y las 02:30 del último domingo de octubre existen **dos veces**. Eso explica la ejecución que os faltó.

**Qué pasa en marzo.** España (zona `Europe/Madrid`) pasa de CET (UTC+1) a CEST (UTC+2) el último domingo de marzo a las 02:00 hora local: los relojes saltan de 01:59:59 a 03:00:00. En 2026 ese día es el **29 de marzo**. Ningún instante de ese día tiene la etiqueta «02:30». Un planificador que trabaja en hora local y busca «02:30» no encuentra ese minuto; según la implementación, salta la ejecución o la hace a las 03:00. Lo que os pasó es la primera opción.

**Verificación vía UTC.** Las 02:30 CET serían 01:30 UTC. Pero a la 01:00 UTC el desfase ya cambió a +2, así que 01:30 UTC se muestra como 03:30 CEST. No hay ningún instante UTC cuya hora local sea 02:30 ese día. ✓

**Qué pasa en octubre.** El último domingo de octubre (en 2026, el **25 de octubre**) a las 03:00 CEST los relojes vuelven a las 02:00 CET. La hora local recorre 02:00-02:59 dos veces: primero en CEST (00:xx UTC), luego en CET (01:xx UTC). Un planificador en hora local puede ejecutar tu tarea dos veces, con una hora de diferencia. Si la tarea no es idempotente (envía correos, cobra, genera un informe con fecha), ese día veréis duplicados.

**Verificación de las fechas.** El 1 de marzo de 2026 es domingo (el 1 de enero fue jueves; enero tiene 31 días → el 1 de febrero es domingo; febrero tiene 28 → el 1 de marzo es domingo). Los domingos de marzo son 1, 8, 15, 22 y 29. Para octubre: contando los meses, el 1 de octubre de 2026 es jueves; domingos 4, 11, 18, 25. ✓

**Regla general:** cualquier hora local entre 02:00 y 02:59 en una zona con horario de verano europeo es problemática dos días al año. En EE. UU. el cambio es a las 02:00 también, con fechas distintas (segundo domingo de marzo, primer domingo de noviembre).""",
            },
            {"role": "user", "content": "¿Entonces cómo lo programo para que no se pierda ni se duplique?"},
            {
                "role": "assistant",
                "content": """Dos opciones, de más a menos robusta.

**Opción 1: programa la tarea en UTC.** Las 02:30 de Madrid son 01:30 UTC en invierno y 00:30 UTC en verano. Elige una y fíjala: por ejemplo, `30 1 * * *` con el planificador configurado en `TZ=UTC`. UTC no tiene saltos, así que la tarea corre exactamente una vez cada día. El coste es que la hora local de ejecución se mueve una hora entre invierno y verano; para una tarea nocturna eso casi nunca importa.

**Opción 2: si tiene que ser hora local, evita la franja 02:00-02:59.** Las 03:30 locales existen todos los días del año, exactamente una vez. Es el cambio más pequeño: mover 60 minutos la hora.

**Lo que no debes hacer:** confiar en que el planificador «lo gestione». Cada implementación lo hace a su manera (saltar, ejecutar al final del salto, ejecutar dos veces), y el comportamiento rara vez está documentado donde lo buscas. Diseña para que no importe.

**Red de seguridad, hagas lo que hagas:** haz la tarea idempotente con una clave por día lógico. Por ejemplo, antes de ejecutar comprueba si ya existe un registro para `fecha_logica = hoy`; si existe, sal. Así la duplicación de octubre no produce dos informes, y una ejecución manual de rescate (la que tuvisteis que hacer en marzo) no choca con la automática.

**Cómo verificar el arreglo sin esperar a marzo:** en un entorno de pruebas, fija la fecha del sistema (o la del planificador, si lo permite) al 28 de marzo de 2026 a las 01:55 hora de Madrid y avanza el reloj; debe aparecer exactamente una ejecución. Repite con el 25 de octubre a las 01:55. Una suite que no cubre esos dos días deja el bug exactamente donde estaba.""",
            },
        ]
    },
    # 22) Razonamiento causal: ¿la caché causa los errores?
    {
        "messages": [
            {"role": "user", "content": "Desde que metimos Redis como caché delante de la base de datos, los errores 500 han subido un 30%. El equipo dice que la caché es la culpable y quieren quitarla. ¿Es un razonamiento sólido?"},
            {
                "role": "assistant",
                "content": """No es sólido todavía. «Después de X, subió Y» es compatible con que X cause Y, pero también con tres cosas más, y cada una se distingue con una prueba concreta. Quitar la caché sin saber cuál es el caso puede dejaros sin caché y con los mismos errores.

**Hipótesis ordenadas por probabilidad y cómo separarlas:**

| # | Hipótesis | Qué esperarías ver | Prueba rápida |
|---|---|---|---|
| 1 | La caché causa los 500 directamente (timeouts a Redis, deserialización fallida, claves inconsistentes) | Las trazas de los 500 pasan por el código de caché | Agrupar los 500 por excepción y por endpoint; mirar si Redis aparece en la pila |
| 2 | Algo más se desplegó a la vez (otro cambio en el mismo release) | Los 500 vienen de endpoints que no usan la caché | Mismo agrupado: si el 70 % de los errores son de un endpoint sin caché, no es la caché |
| 3 | Subió el tráfico o cambió su mezcla en las mismas fechas | Los 500 absolutos suben pero la *tasa* por petición no | Comparar tasa de error (500 / total), no conteo |
| 4 | La caché destapó un bug latente (por ejemplo, respuestas más rápidas aumentan la concurrencia y aparece una carrera que antes no se veía) | Errores en zonas sin relación con Redis, correlacionados con el pico de peticiones concurrentes | Bajar temporalmente el TTL o el porcentaje de tráfico cacheado y ver si la tasa cambia de forma proporcional |

**Criterios causales que puedes aplicar sin estadística avanzada:**

- *Precedencia temporal* se cumple (la caché llegó antes), pero es necesaria, no suficiente.
- *Mecanismo:* ¿existe una ruta concreta por la que la caché produce un 500? Si nadie puede nombrarla, la hipótesis 1 pierde fuerza.
- *Dosis-respuesta:* si cacheas más y los errores suben, y cacheas menos y bajan, tienes un argumento fuerte. Esto es lo más cerca de un experimento que puedes hacer en producción.
- *Contrafactual:* el experimento limpio es desactivar la caché con un *feature flag* para el 50 % del tráfico durante un día y comparar tasas. Es mejor que quitarla del todo porque mantiene las otras variables iguales (mismo día, mismo tráfico).

**Verificación del método.** si la hipótesis 1 fuera cierta, al desactivar la caché al 50 % la tasa de error en ese 50 % debería volver a la de antes del cambio. Si no vuelve, la caché está exonerada aunque el calendario la señale.

**Lo que diría al equipo:** «Puede ser la caché, pero el calendario no lo demuestra. Dadme el desglose de los 500 por excepción y endpoint y un día con el flag al 50 %; con eso sabremos si la quitamos o si estamos a punto de quitar lo único que no está roto.»""",
            },
        ]
    },
    # 23) Optimización sencilla: valla contra un muro.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo 100 metros de valla para cercar un huerto rectangular pegado a un muro, así que solo necesito vallar tres lados. ¿Qué medidas dan la mayor superficie? Mi primera idea es un cuadrado pero no estoy seguro."},
            {
                "role": "assistant",
                "content": """El cuadrado no es la mejor opción cuando uno de los lados lo pone el muro. El óptimo es **25 m × 50 m** (los dos lados perpendiculares al muro de 25 m, el paralelo de 50 m), con **1 250 m²**.

**Planteamiento.** Sea x la longitud de cada lado perpendicular al muro. La valla cubre dos de esos lados más el lado paralelo: 2x + y = 100 → y = 100 − 2x. Área:

A(x) = x · (100 − 2x) = 100x − 2x².

**Máximo.** Es una parábola hacia abajo; el vértice está en x = −b/(2a) = −100/(2 · (−2)) = 25. Entonces y = 100 − 50 = 50 y A = 25 · 50 = 1 250 m².

**Verificación 1: derivada.** A'(x) = 100 − 4x = 0 → x = 25. A''(x) = −4 < 0, así que es un máximo. ✓

**Verificación 2: probar vecinos.** x = 20 → 20 · 60 = 1 200. x = 30 → 30 · 40 = 1 200. x = 25 → 1 250. Los dos vecinos dan menos y son simétricos, como corresponde al vértice. ✓

**Por qué no el cuadrado.** Con tres lados vallados, el cuadrado sería 33,3 m de lado: 33,3 · 33,3 = 1 111 m², bastante por debajo. El cuadrado es óptimo cuando pagas los cuatro lados; aquí el lado paralelo al muro es «gratis» a medias (solo lo pagas una vez en vez de dos), así que conviene alargarlo. La regla general en este tipo de problemas es que el gasto de valla se reparte a partes iguales entre las dos direcciones: 50 m para los perpendiculares (25 + 25) y 50 m para el paralelo.

**Si el muro fuera corto** (por ejemplo, 40 m), la solución 25 × 50 no cabe. Entonces el máximo está en el borde: y = 40, x = 30, área 1 200 m². Conviene comprobar esa restricción antes de comprar la valla.""",
            },
        ]
    },
    # 24) Ley de Little en inglés, sistema breve.
    {
        "messages": [
            {"role": "system", "content": "Answer concisely and show your working."},
            {"role": "user", "content": "I need to make 1,000 calls to a third-party API. They rate-limit me at 10 requests/second and each call takes about 300 ms. What's the fastest I can finish, and how many concurrent workers do I need? My colleague wants to spin up 50 goroutines."},
            {
                "role": "assistant",
                "content": """Fastest possible: **about 100 seconds**. Workers needed: **3**. Fifty goroutines buy nothing except a flood of 429s.

**1. The rate limit is the binding constraint.** 1,000 calls at a maximum of 10/s takes at least 1,000 / 10 = 100 s. No amount of concurrency beats that; the last response arrives roughly 0.3 s after the last request, so ~100.3 s in practice.

**2. Concurrency needed to sustain 10/s (Little's law).** In-flight requests = throughput × latency:

L = λ · W = 10 req/s × 0.3 s = 3 requests in flight.

So 3 workers, each keeping one request in flight, saturate the limit. Each worker does 1 / 0.3 ≈ 3.33 req/s; three of them give 10 req/s exactly.

**3. What fewer or more workers do.**

| Workers | Max throughput | Time for 1,000 calls |
|---|---|---|
| 1 | 3.33/s | 300 s |
| 2 | 6.67/s | 150 s |
| 3 | 10/s (limit) | 100 s |
| 50 | 10/s (limit) | 100 s, plus rate-limit errors and retries |

**Verification by a different route.** With 3 workers and no limiter, each completes a call every 0.3 s, so in 100 s each does 333 calls; 3 × 333 ≈ 1,000. ✓ With 50 workers the API would receive 50 requests in the first 300 ms, i.e. 167/s, and reject at least 157 of them; the retries make it *slower* than 3 workers, not faster.

**Practical setup.** Use a token-bucket limiter (`golang.org/x/time/rate` with `rate.Limit(10)` and a small burst) shared by the workers, and size the pool at 3-4 to absorb latency jitter. If latency rises to 500 ms, Little's law says you need 5 in flight; a pool of 4 would then drop to 8 req/s. Measure the real p50 latency and set workers = ceil(10 × latency) + 1.""",
            },
        ]
    },
    # 25) Caballeros y escuderos.
    {
        "messages": [
            {"role": "user", "content": "En una isla, los caballeros siempre dicen la verdad y los escuderos siempre mienten. Me encuentro a dos habitantes, A y B. A dice: 'Al menos uno de nosotros dos es escudero'. B no dice nada. ¿Qué son A y B?"},
            {
                "role": "assistant",
                "content": """**A es caballero y B es escudero.**

**Razonamiento por casos sobre A** (B no habla, así que toda la información viene de A):

- *Si A fuera escudero*, su frase sería falsa. «Al menos uno de los dos es escudero» falsa significa que *ninguno* es escudero. Pero hemos supuesto que A lo es: contradicción. Luego A no puede ser escudero.
- *Entonces A es caballero* y su frase es verdadera: al menos uno de los dos es escudero. Como A no lo es, tiene que serlo B.

**Verificación enumerando las cuatro combinaciones:**

| A | B | Frase de A («al menos uno es escudero») | ¿Coherente con lo que es A? |
|---|---|---|---|
| caballero | caballero | falsa | no: un caballero no dice falsedades |
| caballero | escudero | verdadera | **sí** |
| escudero | caballero | verdadera | no: un escudero no dice verdades |
| escudero | escudero | verdadera | no: un escudero no dice verdades |

Solo una fila sobrevive. ✓

**La idea general.** En estos acertijos, una frase dicha por X equivale a la afirmación «X es caballero ⇔ la frase es verdadera». Aquí: A caballero ⇔ (A escudero o B escudero). Si A es caballero, el lado derecho debe ser verdadero y solo puede serlo por B. Si A es escudero, el lado derecho debe ser falso, pero «A escudero» lo hace verdadero. Mismo resultado, sin tabla.

**Variante para comprobar que lo has entendido:** si A hubiera dicho «los dos somos escuderos», la respuesta sería la misma (A caballero es imposible porque se llamaría escudero a sí mismo; A escudero hace la frase falsa, así que B es caballero): A escudero, B caballero.""",
            },
        ]
    },
    # 26) Invariante de paridad en un proceso.
    {
        "messages": [
            {"role": "user", "content": "En una pizarra están escritos los números del 1 al 20. En cada paso borro dos números a y b y escribo |a − b|. Después de 19 pasos queda un solo número. ¿Puede ser 1? ¿Puede ser 0? ¿Puede ser 20?"},
            {
                "role": "assistant",
                "content": """**1: imposible. 0: posible. 20: posible.** La imposibilidad sale de un invariante de paridad; las dos posibilidades, de construcciones explícitas. Son dos tipos de argumento distintos y conviene no mezclarlos.

**1. Por qué nunca queda 1: invariante.** Al sustituir a y b por |a − b|, la suma de la pizarra cambia en

(a + b) − |a − b| = 2 · min(a, b),

que es par. Así que **la paridad de la suma no cambia nunca**. Al principio la suma es 1 + 2 + ⋯ + 20 = 20 · 21 / 2 = 210, par. El número final tiene la paridad de la suma: par. Luego no puede ser 1 (ni ningún impar).

**2. Por qué sí puede quedar 0: construcción.** Empareja (1,2), (3,4), …, (19,20): diez pasos, quedan diez unos. Empareja los unos entre sí: cinco pasos, quedan cinco ceros. Combina los ceros: cuatro pasos, queda 0. Total 19 pasos. ✓

**3. Por qué sí puede quedar 20: construcción.** La trampa aquí es pensar «los números solo bajan, así que 20 es inalcanzable». Es cierto que |a − b| ≤ max(a, b), de modo que ningún número nuevo supera al 20; pero el propio 20 puede quedarse sin tocar hasta el final. Basta con reducir 1…19 a un único 0 y hacer |0 − 20| = 20.

Para reducir 1…19 a 0 usa que **cuatro consecutivos siempre colapsan a 0**: de (a, a+1, a+2, a+3) sale (a+3) − (a+2) = 1, (a+1) − a = 1, y 1 − 1 = 0.

- (4,5,6,7), (8,9,10,11), (12,13,14,15), (16,17,18,19) → cuatro ceros.
- (1,2,3): 3 − 2 = 1, 1 − 1 = 0 → otro cero.
- Cinco ceros → 0. Pizarra: {0, 20} → 20. ✓

**Verificación con un caso pequeño** (1 a 4, suma 10, par): 0 se alcanza con (1,2)→1, (3,4)→1, (1,1)→0. El máximo, 4, se alcanza con (3,2)→1, (1,1)→0, (0,4)→4. Y 1 no aparece en ninguna de las seis combinaciones de orden posibles, como exige la paridad. El patrón es el mismo que en el caso grande. ✓

**Lección de método.** Un invariante solo sirve para demostrar que algo es *imposible*. Para afirmar que algo *es posible* hay que construirlo. La cota «el máximo no crece» era verdadera y sin embargo no descartaba el 20, porque 20 era ya el máximo inicial; si te quedas en la cota y no intentas la construcción, respondes mal con mucha seguridad.""",
            },
        ]
    },
    # 27) Gambler's fallacy vs. evidencia bayesiana, en inglés.
    {
        "messages": [
            {"role": "user", "content": "I flipped a coin 10 times and got 10 heads. Is tails now 'due'? My friend says yes because it has to even out, I say it's still 50/50. Who's right?"},
            {
                "role": "assistant",
                "content": """Neither, strictly. Your friend is wrong for a well-known reason; you are *almost* right, but the honest answer is that after ten heads, **heads is slightly more likely than tails**, not less.

**1. Why "tails is due" is wrong (gambler's fallacy).** A fair coin has no memory. P(tails on flip 11 | ten heads) = 0.5 for a fair coin, exactly as on flip 1. The law of large numbers says the *proportion* of heads converges to 0.5 over many flips; it does not say the *count* gets corrected. After 10 heads, the expected number of heads in the next 1,000 flips is 500, so the sequence ends up around 510/1,010 = 50.5%: the surplus is diluted, never repaid.

**2. Why "still 50/50" is slightly wrong too.** You said "a coin", not "a coin I have verified to be fair". Ten heads in a row is evidence about the coin. Under a fair coin, the probability of this run is (1/2)¹⁰ = 1/1024 ≈ 0.1%. That is rare enough that a sensible observer should move some belief toward "this coin or this flipping method favours heads".

Concrete Bayesian version. Suppose before flipping you thought there was a 1% chance the coin was double-headed (or otherwise always lands heads), 99% fair.

- P(10 heads | fair) = 1/1024 = 0.000977.
- P(10 heads | always heads) = 1.
- Posterior P(always heads) = 0.01 × 1 / (0.01 × 1 + 0.99 × 0.000977) = 0.01 / (0.01 + 0.000967) = 0.01 / 0.010967 = **0.912**.

Then P(heads on flip 11) = 0.912 × 1 + 0.088 × 0.5 = 0.956. With a milder prior (say, the coin might be biased 60/40 rather than 100/0) the posterior is less dramatic, but it always tilts toward heads, never toward tails.

**Verification with odds.** Prior odds for "always heads" are 1:99. The likelihood ratio of ten heads is 1 / (1/1024) = 1024. Posterior odds 1024:99 ≈ 10.3:1 → probability 10.3/11.3 = 0.912. ✓ Same number by a different path.

**So who is right?** If you both *know* the coin is fair (you inspected it, you trust the flipper), you are right: 50/50. If you do not, the data say the coin leans heads, and anyone betting on "due tails" is paying for the privilege of being wrong twice.""",
            },
        ]
    },
    # 28) Conteo circular, multiturno con restricción.
    {
        "messages": [
            {"role": "user", "content": "¿De cuántas formas se pueden sentar 5 personas en una mesa redonda? Me sale 120 pero el libro dice 24."},
            {
                "role": "assistant",
                "content": """Son **24** si solo importa quién está al lado de quién (lo habitual en «mesa redonda»), y **120** si las sillas están numeradas. El libro usa la primera convención.

**Por qué 120 cuenta de más.** 5! = 120 es el número de formas de asignar 5 personas a 5 sillas *distinguibles*. En una mesa redonda sin sillas marcadas, girar a todo el mundo un asiento produce la misma disposición: cada persona tiene los mismos vecinos. Cada disposición circular aparece 5 veces entre las 120 (una por cada giro), así que hay 120 / 5 = 24 distintas.

**Forma directa de contarlo.** Sienta a una persona cualquiera, por ejemplo a Ana, en cualquier sitio; eso fija la referencia y elimina los giros. Las otras 4 se reparten las 4 sillas restantes en relación a Ana: 4! = 24.

**Verificación con un caso pequeño.** Tres personas: con sillas numeradas, 3! = 6. En círculo, fija a Ana; las otras dos pueden estar (Beto a su izquierda, Carla a su derecha) o al revés: 2 = (3 − 1)!. ✓ Y 6 / 3 = 2 por el argumento de los giros. ✓

**Una convención más.** Si además consideras iguales una disposición y su imagen en el espejo (como en un collar de cuentas), divide entre 2: 24 / 2 = 12. En problemas de personas sentadas casi nunca se hace, porque «a la izquierda» y «a la derecha» sí se distinguen.

Resumen: sillas numeradas → n!; mesa redonda → (n − 1)!; collar → (n − 1)!/2.""",
            },
            {"role": "user", "content": "Vale. ¿Y si dos de ellas, Ana y Beto, no pueden sentarse juntas?"},
            {
                "role": "assistant",
                "content": """**12 formas.**

**Método (total menos las prohibidas).** De las 24 disposiciones circulares, resta aquellas en las que Ana y Beto están juntos.

- Pega a Ana y Beto como un bloque. Ahora hay 4 «unidades» en círculo: el bloque y las otras 3 personas → (4 − 1)! = 6 disposiciones.
- Dentro del bloque, Ana puede estar a la izquierda o a la derecha de Beto: × 2.
- Juntos: 6 · 2 = 12. Separados: 24 − 12 = **12**.

**Verificación por probabilidad.** Sienta a Ana. De las 4 sillas restantes, exactamente 2 son vecinas de Ana. Si Beto se sienta al azar, P(junto a Ana) = 2/4 = 1/2. La mitad de las 24 disposiciones los tiene juntos: 12 juntos, 12 separados. ✓

**Verificación directa.** Sienta a Ana. Beto tiene 2 sillas no vecinas. Las otras 3 personas ocupan las 3 sillas que quedan: 3! = 6. Total 2 · 6 = 12. ✓ Tres caminos, mismo número.""",
            },
        ]
    },
    # 29) Planificación: puente y linterna, con la trampa del greedy.
    {
        "messages": [
            {"role": "system", "content": "Responde con pasos numerados y una verificación final."},
            {"role": "user", "content": "Cuatro personas tienen que cruzar un puente de noche con una sola linterna. Caben dos a la vez y van al paso del más lento. Tardan 1, 2, 5 y 10 minutos. Yo lo resuelvo en 19 minutos haciendo que el de 1 acompañe a cada uno y vuelva. ¿Se puede mejorar?"},
            {
                "role": "assistant",
                "content": """Sí: **17 minutos**. Tu estrategia de 19 es la intuitiva («el rápido hace de taxi») y falla porque obliga a los dos lentos a cruzar en viajes separados, pagando 5 y 10 por separado.

**1. La idea clave.** Los dos lentos (5 y 10) deben cruzar **juntos**: así el viaje cuesta 10 en vez de 5 + 10 = 15. Para que eso funcione sin que vuelva uno de ellos con la linterna, hay que dejar antes al otro lado a alguien rápido que la traiga de vuelta.

**2. Plan óptimo** (orilla A → orilla B):

| Paso | Movimiento | Minutos | Acumulado |
|---|---|---|---|
| 1 | 1 y 2 cruzan | 2 | 2 |
| 2 | 1 vuelve | 1 | 3 |
| 3 | 5 y 10 cruzan | 10 | 13 |
| 4 | 2 vuelve | 2 | 15 |
| 5 | 1 y 2 cruzan | 2 | 17 |

**3. Comparación con tu plan (1 como taxi):** (1,2) cruzan 2, 1 vuelve 1, (1,5) cruzan 5, 1 vuelve 1, (1,10) cruzan 10 → 19. En fórmula, con tiempos a ≤ b ≤ c ≤ d: taxi = 2a + b + c + d = 2 + 2 + 5 + 10 = 19; parejas = a + 3b + d = 1 + 6 + 10 = 17. El plan de parejas gana cuando 2b < a + c, es decir, cuando el segundo más rápido es lo bastante rápido como para hacer de mensajero: 4 < 6. ✓

**4. Por qué no hay nada mejor que 17.** Hacen falta 5 viajes como mínimo (3 de ida para cruzar 4 personas de dos en dos, 2 de vuelta para traer la linterna). El viaje del de 10 cuesta al menos 10. Los otros dos viajes de ida cuestan al menos 2 cada uno (el más rápido viajando con alguien cuesta al menos lo que tarda el acompañante, y el mejor acompañante tarda 2) salvo que el de 10 viaje con el de 5, en cuyo caso el de 5 ya está cubierto. Las dos vueltas cuestan al menos 1 + 2 (dos personas distintas tienen que volver, o la misma dos veces: 1 + 1, pero entonces el de 2 cruza en un viaje aparte que cuesta 2 más). Sumando el mejor caso en cada rama se llega a 17 como cota inferior, que coincide con el plan. Es óptimo.

**Verificación final.** Recuento de personas en la orilla B tras cada paso: {1,2} → {2} → {2,5,10} → {5,10} → {1,2,5,10}. Todos cruzan, la linterna siempre está donde está el que se mueve, y la suma de la columna «Minutos» es 2 + 1 + 10 + 2 + 2 = 17. ✓""",
            },
        ]
    },
    # 30) Deducción con restricciones (mini puzle lógico).
    {
        "messages": [
            {"role": "user", "content": """Puzle de lógica que me dieron en una entrevista. Tres desarrolladores (Ana, Beto, Carla) usan cada uno un lenguaje distinto entre Go, Rust y Python.

1. Ana no usa Go.
2. Quien usa Rust llegó a la empresa antes que Beto.
3. Carla no usa Rust.
4. Beto no usa Python.

¿Quién usa qué? Lo saqué por prueba y error pero quiero una forma sistemática."""},
            {
                "role": "assistant",
                "content": """**Ana: Rust. Beto: Go. Carla: Python.**

**Método sistemático: empieza por la pista que más elimina.** Con tres personas y tres lenguajes hay 3! = 6 asignaciones posibles. Cada pista tacha algunas; cuando queda una, has terminado.

**Paso 1: ¿quién usa Rust?** Es la pregunta con más pistas encima.
- La pista 3 descarta a Carla.
- La pista 2 descarta a Beto: quien usa Rust llegó *antes que Beto*, así que no puede ser el propio Beto. Esta es la pista con trampa: habla de antigüedad, pero lo único que aporta es «Beto no es el de Rust».
- Queda **Ana → Rust**. (Coherente con la pista 1: Ana no usa Go.)

**Paso 2: Beto.** Ya no puede ser Rust (Ana lo tiene) y la pista 4 descarta Python. Queda **Beto → Go**.

**Paso 3: Carla.** Lo único que queda es **Python**.

**Verificación contra las cuatro pistas:**

1. Ana no usa Go: usa Rust. ✓
2. Quien usa Rust (Ana) llegó antes que Beto: no contradice nada; es posible. ✓
3. Carla no usa Rust: usa Python. ✓
4. Beto no usa Python: usa Go. ✓

**Verificación por la tabla de las seis asignaciones** (Ana, Beto, Carla):

| Asignación | Tachada por |
|---|---|
| Go, Rust, Python | pista 1 (Ana-Go) |
| Go, Python, Rust | pista 1 |
| Rust, Go, Python | **ninguna** |
| Rust, Python, Go | pista 4 (Beto-Python) |
| Python, Go, Rust | pista 3 (Carla-Rust) |
| Python, Rust, Go | pista 2 (Beto-Rust) |

Sobrevive una sola. ✓

**Para la próxima entrevista.** El método es siempre el mismo: (a) enumera las variables y sus valores; (b) traduce cada pista a una restricción simple, quitando el adorno narrativo (la pista 2 «es» Beto ≠ Rust); (c) ataca la variable más restringida; (d) propaga; (e) comprueba la solución contra *todas* las pistas, no solo las que usaste. El paso (e) es el que te salva cuando una pista parecía redundante y no lo era.""",
            },
        ]
    },
]
