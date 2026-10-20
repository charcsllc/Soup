"""Español: redacción, resumen y explicación. 30 filas SFT (chatml).

Temas: resumir textos dados (informes, actas, reseñas), reescribir para claridad, pasar de
técnico a divulgativo, explicar conceptos técnicos a no técnicos con analogías correctas
(API, latencia, hash, transacción, caché, recursión, índice, deuda técnica, clave pública),
estructurar un documento, titular, redactar un README, criticar y mejorar un párrafo,
detectar falacias, verificar la fidelidad de un resumen.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Resumir un informe técnico en tres frases.
    {
        "messages": [
            {
                "role": "user",
                "content": """Resume este informe en tres frases para el canal del equipo:

«Durante el fin de semana del 12 y 13 de octubre se migró la base de datos de pedidos de PostgreSQL 13 a PostgreSQL 16 en el clúster de producción. La ventana de mantenimiento prevista era de cuatro horas, pero se extendió a seis porque la reconstrucción de índices en la tabla order_items (1.200 millones de filas) tardó más de lo estimado en el ensayo, que se hizo con una copia del 40 % del volumen. No hubo pérdida de datos: las sumas de verificación por tabla coincidieron antes y después. Tras la migración, el tiempo medio de respuesta de la API de pedidos bajó de 180 ms a 120 ms, sobre todo por las mejoras del planificador en consultas sobre tablas particionadas. Se detectaron dos incidencias menores: un job nocturno de informes falló porque usaba el operador factorial postfijo, eliminado en PostgreSQL 14, y la herramienta de monitorización dejó de mostrar la métrica de bloqueos hasta actualizar su extensión. Ambas se corrigieron el lunes por la mañana. Queda pendiente decidir si se elimina la réplica antigua, que sigue costando unos 1.400 € al mes, o si se mantiene dos semanas más como respaldo. El equipo de datos propone eliminarla el día 28 si no aparecen nuevas incidencias.»""",
            },
            {
                "role": "assistant",
                "content": """La base de datos de pedidos ya está en PostgreSQL 16: la migración del fin de semana duró seis horas en vez de cuatro por la reconstrucción de índices de `order_items`, pero no hubo pérdida de datos. La API de pedidos responde ahora en 120 ms de media (antes, 180 ms), y las dos incidencias menores que aparecieron, un job de informes y una métrica de monitorización, quedaron corregidas el lunes. Falta decidir si eliminamos la réplica antigua (unos 1.400 €/mes) el día 28, como propone el equipo de datos, o la mantenemos dos semanas más.

**Criterio que seguí.** En un canal de equipo la gente lee la primera línea y decide si sigue. Por eso el orden es: estado final (¿funcionó?), impacto (¿qué cambia para mí?) y lo que requiere una acción (la decisión pendiente). La decisión va al final y con fecha porque es lo único que pide algo al lector.

**Qué dejé fuera y por qué:**

- El detalle de las incidencias (operador factorial, extensión de monitorización): ya están resueltas y no afectan a nadie. Quien lo necesite lo encontrará en el informe.
- Que el ensayo se hizo con el 40 % del volumen. Es la lección más útil del informe, pero no es un resultado. Si el canal lo leen quienes planificarán la próxima migración, cambiaría la primera frase por: «… duró seis horas en vez de cuatro porque el ensayo se hizo con el 40 % de los datos y subestimó la reconstrucción de índices».
- La causa de la mejora de rendimiento. El original dice «sobre todo» por el planificador; resumirlo como causa única sería más fuerte que el texto, y omitirlo no distorsiona nada.

**Comprobación de fidelidad.** Cada cifra del resumen aparece en el original (6 h frente a 4 h, 180 → 120 ms, 1.400 €, día 28) y no hay ninguna afirmación que el informe no haga: no digo que la réplica se vaya a eliminar, sino que hay una propuesta.""",
            },
        ]
    },
    # 2) Acta de reunión -> decisiones, tareas y temas abiertos.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Notas de la reunión de ayer, sácame decisiones, tareas con responsable y lo que quedó abierto:

Marta: el cliente quiere el panel de reportes para el 15 de noviembre. Jorge dice que con el equipo actual no llegamos si además hacemos la exportación a Excel. Se habla de sacar primero el panel sin exportación. Marta está de acuerdo pero tiene que confirmarlo con el cliente, lo hace esta semana. Lucía comenta que la API de facturación devuelve los importes como texto y hay que convertirlos; Jorge se encarga de hablar con el equipo de facturación. Alguien pregunta si usamos Metabase o lo hacemos a mano, no se decide, Lucía prepara una comparación para el jueves. Se acuerda hacer daily de 15 minutos a las 9:30 hasta la entrega. Pendiente: quién hace QA, porque Andrés está de vacaciones la primera semana de noviembre.""",
            },
            {
                "role": "assistant",
                "content": """**Decisiones**

1. Daily de 15 minutos a las 9:30 hasta la entrega del 15 de noviembre. Es la única decisión firme.
2. Entregar el panel sin exportación a Excel en la primera versión. **Condicionada**: depende de que el cliente lo acepte.

**Tareas**

| Tarea | Responsable | Fecha |
|---|---|---|
| Confirmar con el cliente que la primera entrega va sin exportación a Excel | Marta | Esta semana |
| Hablar con facturación sobre los importes que la API devuelve como texto | Jorge | **Sin fecha** |
| Comparar Metabase frente a desarrollo propio para el panel | Lucía | Jueves |

**Temas abiertos**

- **Quién hace QA** la primera semana de noviembre, con Andrés de vacaciones. Es el riesgo más serio de la lista: cae justo antes de la entrega y nadie lo tiene asignado.
- **Metabase o desarrollo propio.** Se cierra cuando Lucía presente la comparación.
- **Qué pasa si el cliente no acepta el recorte.** Las notas no lo dicen, y es lo primero que conviene acordar si Marta vuelve con un no, porque según Jorge el plazo no da para las dos cosas.

Por qué lo clasifiqué así:

- Separé la decisión del recorte de las firmes porque presentarla como cerrada es el error típico de estas actas: el equipo empieza a trabajar sin exportación y el cliente se entera en la entrega.
- Marqué la tarea de Jorge sin fecha en lugar de inventarle una. Una tarea sin fecha es la que antes se olvida; conviene ponérsela en la próxima daily.
- «Alguien pregunta» no necesita responsable: lo que importa es quién cierra la pregunta, y eso sí está (Lucía).

Comprobación: cada frase de tus notas aparece en una de las tres secciones y ninguna en dos. La conversión de importes no la puse como decisión porque nadie decidió nada todavía: solo se asignó a quién preguntar.""",
            },
        ]
    },
    # 3) Reescribir para claridad un párrafo administrativo.
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo que dejar este párrafo de nuestra wiki más claro, que nadie lo entiende:

«En lo que respecta a la realización de despliegues a producción, cabe señalar que, con carácter previo a la ejecución de los mismos, y siempre y cuando no se trate de una corrección urgente, en cuyo caso se aplicará el procedimiento de excepción descrito en otro apartado, deberá procederse a la obtención de la aprobación por parte de al menos un miembro del equipo de plataforma, la cual habrá de quedar registrada en el ticket correspondiente, no pudiendo realizarse los despliegues los viernes a partir de las 15:00 salvo autorización expresa.»""",
            },
            {
                "role": "assistant",
                "content": """Versión propuesta:

> **Antes de desplegar a producción**
>
> 1. Consigue la aprobación de al menos una persona del equipo de plataforma.
> 2. Deja registrada esa aprobación en el ticket del despliegue.
>
> **Los viernes no se despliega a partir de las 15:00**, salvo autorización expresa de la responsable de plataforma.
>
> **Correcciones urgentes:** no siguen estos pasos, sino el procedimiento de la sección «Despliegues urgentes».

Qué cambié y por qué:

1. **Una idea por frase.** El original mete cuatro normas en una sola oración de 90 palabras: el lector tiene que guardar la excepción en la cabeza mientras busca la regla principal. Ahora la regla va primero y las excepciones después.
2. **Verbos en vez de sustantivos.** «Proceder a la obtención de la aprobación» es «conseguir la aprobación». «La realización de despliegues» es «desplegar». Las nominalizaciones alargan sin añadir información.
3. **Imperativo dirigido al lector.** «Deberá procederse» no dice quién lo hace. «Consigue» sí: la persona que despliega.
4. **Fuera el gerundio encadenado.** «No pudiendo realizarse…» añade una regla nueva colgada de la anterior. Es un uso del gerundio poco claro y desaconsejado; la prohibición del viernes merece frase propia.
5. **Fuera las muletillas.** «En lo que respecta a», «cabe señalar que», «los mismos»: ninguna aporta contenido.
6. **Referencia concreta.** «Otro apartado» obliga a buscar. Nombré la sección; cambia el título por el real.

Dos huecos del original que no puedo resolver yo:

- **«Salvo autorización expresa»: ¿de quién?** El texto no lo dice. Asumí la responsable de plataforma; confírmalo, porque es justo la duda que generará un viernes a las 15:05.
- **¿La aprobación vale para cualquier despliegue o por cada uno?** Lo redacté como «por cada despliegue» porque habla del «ticket correspondiente», que suena a un ticket por despliegue.

Comprobación de que no se perdió nada: el original contiene cinco elementos (aprobación de plataforma, registro en el ticket, excepción urgente, prohibición del viernes y su excepción) y los cinco están en la versión nueva.""",
            },
        ]
    },
    # 4) De técnico a divulgativo, con system de editor.
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres editor de una revista de divulgación para público general. Escribes con precisión y sin tecnicismos innecesarios.",
            },
            {
                "role": "user",
                "content": """Convierte este párrafo en algo que entienda un lector de 15 años, sin perder exactitud:

«El receptor GNSS determina su posición mediante trilateración a partir de las pseudodistancias a, como mínimo, cuatro satélites. Cada satélite emite su efeméride y una marca temporal generada por relojes atómicos; el receptor calcula la pseudodistancia multiplicando el retardo de propagación por la velocidad de la luz. El cuarto satélite es necesario para resolver el sesgo del reloj del receptor, que no es atómico. Además, el sistema aplica correcciones relativistas: los relojes de los satélites adelantan unos 38 microsegundos al día respecto a los terrestres.»""",
            },
            {
                "role": "assistant",
                "content": """**¿Cómo sabe tu móvil dónde estás?**

Cada satélite de navegación lleva un reloj atómico extremadamente preciso y emite sin parar un mensaje con dos datos: dónde está él en ese momento y qué hora marca su reloj.

Tu móvil recibe ese mensaje un instante después, porque la señal tarda en llegar. Viaja a la velocidad de la luz, unos 300.000 km por segundo, y el satélite está a unos 20.000 km de altura. Si el móvil sabe cuánto tardó la señal, multiplica ese tiempo por la velocidad de la luz y obtiene la distancia al satélite.

Saber la distancia a un satélite te dice que estás en algún punto de una esfera gigante con el satélite en el centro. Con tres satélites, las tres esferas solo coinciden en dos puntos, y uno de ellos suele estar en el espacio, así que se descarta.

Hay una trampa: el reloj de tu móvil no es atómico, y un error de una milésima de segundo equivale a 300 km. Por eso se usa un cuarto satélite. Con cuatro medidas, el móvil calcula a la vez dónde está y cuánto se equivoca su propio reloj.

Falta un detalle sorprendente: según la teoría de la relatividad de Einstein, el tiempo no pasa igual allá arriba. Los relojes de los satélites se adelantan unas 38 millonésimas de segundo al día respecto a los de la Tierra. Parece nada, pero sin corregirlo el GPS acumularía un error de unos 11 km cada día.

---

Notas de edición:

- **«Trilateración», no «triangulación».** La versión popular dice «triangula», pero triangular es medir ángulos y aquí se miden distancias. Por eso describo esferas y no menciono la palabra técnica.
- **«Pseudodistancia»** desaparece, pero no su idea: se llama «pseudo» precisamente porque incluye el error del reloj del receptor, que es lo que explico en el párrafo del cuarto satélite.
- **«Efeméride»** pasa a «dónde está él en ese momento», que es lo que significa en este contexto.
- **Las cifras nuevas son derivadas, no inventadas.** 1 ms × 300.000 km/s = 300 km. 38 µs × 300.000 km/s ≈ 11,4 km. Las añadí porque a esa edad un número concreto convence más que «un error importante».
- **«GNSS» pasa a «satélite de navegación».** GPS es solo uno de los sistemas (también están Galileo, GLONASS y BeiDou); en el título uso «tu móvil» para no tener que elegir.""",
            },
        ]
    },
    # 5) Explicar qué es una API a alguien de ventas (principiante, léxico de México).
    {
        "messages": [
            {
                "role": "user",
                "content": "Trabajo en ventas en una empresa de software y siempre me dicen 'eso se hace por la API'. ¿Me explicas qué es una API sin tecnicismos? Algo que le pueda repetir a un cliente sin quedar mal.",
            },
            {
                "role": "assistant",
                "content": """Una API es la puerta oficial por la que un programa le pide cosas a otro programa, con reglas fijas sobre qué se puede pedir y cómo.

**La analogía del restaurante**

| Restaurante | Software |
|---|---|
| El menú: qué puedes pedir y cómo se llama cada plato | La documentación de la API: qué operaciones existen y qué datos llevan |
| El mesero, que lleva tu pedido y te trae el plato | La API, que recibe la petición y devuelve la respuesta |
| La cocina, que no ves ni puedes tocar | El sistema interno y la base de datos |
| Pedir algo que no está en el menú: «eso no lo tenemos» | Una petición inválida: la API devuelve un error |

La clave de la analogía: tú no entras a la cocina. No necesitas saber cómo se prepara el plato, y el restaurante puede cambiar de cocinero o de horno sin que cambie el menú. Eso es lo que hace valiosa una API: el otro sistema puede cambiar por dentro mientras la puerta siga funcionando igual.

**Un ejemplo real.** Cuando una app de entregas te muestra el mapa, no dibujó ella el mapa: le pidió a un servicio de mapas, a través de su API, «dame el mapa de esta dirección». Cuando pagas con tarjeta en una tienda en línea, la tienda le pide al banco por su API «cobra esta cantidad a esta tarjeta», y el banco responde «aprobado» o «rechazado».

**Dónde no funciona la analogía:** en la API no pide una persona, sino un programa, y lo hace miles de veces por segundo sin que nadie intervenga. Esa es la diferencia frente a «exportar un Excel y subirlo a mano».

**Frases para usar con un cliente:**

- «¿Tiene API?» significa: «¿pueden otros sistemas conectarse a esto de forma automática?».
- «Se integra por API con su CRM» significa: «los datos pasan solos de un sistema al otro, sin que nadie los copie a mano».
- «Lo hacemos por la API» significa: «no hace falta usar la pantalla; un programa lo hace directamente».

Si un cliente pregunta algo más técnico (formatos, límites de peticiones, seguridad), esa es la señal para llevar a alguien de ingeniería a la llamada.""",
            },
        ]
    },
    # 6) Multiturno: latencia frente a ancho de banda, y luego un caso real.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuál es la diferencia entre latencia y ancho de banda? Explícamelo como si no supiera nada de redes.",
            },
            {
                "role": "assistant",
                "content": """Piensa en una autopista entre tu casa y otra ciudad.

- **Ancho de banda** es el número de carriles: cuántos coches pueden pasar por segundo. Se mide en megabits por segundo (Mbps).
- **Latencia** es cuánto tarda un coche en llegar de una ciudad a la otra. Se mide en milisegundos (ms).

Son independientes. Puedes tener una autopista de veinte carriles hacia una ciudad lejana: entran muchísimos coches a la vez, pero cada uno tarda lo mismo en llegar. Añadir carriles no acorta el viaje.

Por eso cada uso depende de una cosa distinta:

| Uso | Lo que importa | Por qué |
|---|---|---|
| Descargar una película | Ancho de banda | Hay muchos datos y da igual que el primero tarde un poco |
| Videojuego en línea | Latencia | Cada acción es un mensaje pequeño que tiene que llegar ya |
| Videollamada | Las dos, sobre todo la latencia | Es poco volumen, pero un retraso de medio segundo hace que os piséis al hablar |
| Abrir una web | Las dos | Muchas peticiones pequeñas seguidas: la latencia se suma en cada una |

La prueba que puedes hacer tú: el número de «velocidad» que anuncia tu proveedor es el ancho de banda. La latencia es lo que muestran los test de velocidad como *ping*; por debajo de unos 30 ms va bien para casi todo.""",
            },
            {
                "role": "user",
                "content": "Vale, pero entonces no entiendo una cosa: tengo fibra de 600 megas y las videollamadas se me cortan y van con retraso. ¿Cómo puede ser?",
            },
            {
                "role": "assistant",
                "content": """Porque 600 megas son carriles, y a una videollamada le sobran: una llamada en HD usa entre 1 y 4 Mbps según la calidad, menos del 1 % de tu conexión. El problema casi seguro está en la latencia o en que algunos coches no llegan. Hay cuatro sospechosos, de más a menos frecuente:

1. **El wifi.** Es el tramo más débil: paredes, distancia al router y redes vecinas hacen que se pierdan paquetes y haya que reenviarlos. Siguiendo con la autopista, es un tramo de tierra justo antes de tu casa.
2. **La subida saturada.** Alguien en casa sube fotos a la nube o hace una copia de seguridad. La subida suele ser el carril estrecho, y cuando se llena se forma una cola en el router: tus paquetes de vídeo esperan detrás de los de la copia. Esto se llama *bufferbloat* y dispara la latencia aunque el test de velocidad salga bien.
3. **La irregularidad (jitter).** Los coches salen cada 20 ms pero llegan unos a los 5 y otros a los 80. La videollamada tiene que esperar a los rezagados o descartarlos, y eso es lo que ves como cortes.
4. **El otro extremo.** Si la otra persona tiene mala conexión, tú lo ves cortado aunque la tuya vaya perfecta.

Cómo distinguirlos, en este orden:

1. Haz una llamada con el ordenador **conectado por cable** al router. Si se arregla, era el wifi: acércate al router o usa la banda de 5 GHz.
2. Haz un test de velocidad mientras alguien sube archivos. Si el *ping* pasa de 20 ms a 200 ms, es *bufferbloat*. Muchos routers tienen una opción de calidad de servicio (QoS) que limita la subida un poco por debajo del máximo y lo resuelve.
3. Si con cable y sin nadie subiendo sigue fallando, prueba con otra persona. Si con unos va bien y con otros no, el problema está en el otro lado.

Lo que no va a arreglar nada es contratar más megas: estarías añadiendo carriles a una autopista que ya va vacía.""",
            },
        ]
    },
    # 7) Multiturno: hash para no técnicos y por qué no basta para contraseñas.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo que explicar qué es un hash en una charla para gente de recursos humanos (vamos a cambiar cómo guardamos sus contraseñas). ¿Alguna analogía que no sea falsa?",
            },
            {
                "role": "assistant",
                "content": """La huella dactilar funciona bien si cuentas exactamente tres propiedades, que son las que importan:

1. **La misma persona deja siempre la misma huella.** El mismo texto produce siempre el mismo hash. Por eso sirve para comprobar: el sistema no guarda tu contraseña, guarda su huella, y cuando entras calcula la huella de lo que escribes y compara.
2. **Con la huella no puedes reconstruir a la persona.** Del hash no se puede recuperar el texto original. No hay llave que lo «descifre».
3. **Personas casi idénticas dejan huellas totalmente distintas.** Cambiar una sola letra de la contraseña produce un hash que no se parece en nada al anterior. No hay forma de saber «estás cerca».

Un cuarto detalle que la analogía también aguanta: la huella tiene siempre el mismo tamaño, sea la contraseña de 6 caracteres o un libro entero.

**El error que conviene evitar en la charla:** decir que el hash «cifra» la contraseña. Cifrar es reversible: quien tiene la llave recupera el original. Si el público se lleva la idea de «cifrado», pensará que alguien en la empresa puede ver su contraseña, y es justo lo contrario: con un hash, nadie puede, ni siquiera el equipo de sistemas. Por eso, si alguien olvida la contraseña, se le pide crear una nueva en lugar de recordársela.

**Dónde cojea la analogía**, por si alguien pregunta: en teoría dos textos distintos podrían tener el mismo hash (hay infinitos textos y un número finito de huellas). Con las funciones actuales encontrar dos así es inviable en la práctica, así que en la charla basta con «tan improbable que no se tiene en cuenta».

Frase de cierre para la diapositiva: «No guardamos tu contraseña; guardamos su huella. Con la huella podemos comprobar que eres tú, pero nadie puede saber cuál es tu contraseña».""",
            },
            {
                "role": "user",
                "content": "Perfecto. Una duda técnica mía: el equipo propone SHA-256. ¿Con eso ya está?",
            },
            {
                "role": "assistant",
                "content": """No. SHA-256 es un buen hash para comprobar archivos, pero es mala elección para contraseñas, por dos motivos.

**1. Es demasiado rápido.** Está diseñado para calcular miles de millones de hashes por segundo en una tarjeta gráfica. Si alguien roba la tabla de hashes, no necesita «revertirlos»: prueba contraseñas candidatas (diccionarios, filtraciones previas, variaciones como `Verano2024!`) y compara huellas. Con esa velocidad, cualquier contraseña humana normal cae en poco tiempo.

**2. Sin sal, contraseñas iguales dan hashes iguales.** Si veinte personas usan `Empresa123`, las veinte tienen la misma huella en la tabla: el atacante rompe una y tiene las veinte, y además puede usar tablas precalculadas.

Lo correcto es una función diseñada para contraseñas: **Argon2id** (la recomendación actual de OWASP), o **bcrypt** o **scrypt** si tu plataforma no tiene Argon2. Las tres:

- Añaden una **sal** aleatoria distinta por usuario, que se guarda junto al hash. Así, dos contraseñas iguales producen huellas distintas.
- Son **lentas a propósito y configurables**: calcular un hash cuesta, por ejemplo, unos cientos de milisegundos y bastante memoria. Para quien inicia sesión es imperceptible; para quien prueba miles de millones de candidatas, es la diferencia entre horas y siglos.

En la mayoría de lenguajes no tienes que implementarlo: usa la biblioteca estándar de tu framework (por ejemplo, `argon2-cffi` en Python, `password_hash` con `PASSWORD_ARGON2ID` en PHP, o `BCryptPasswordEncoder` en Spring Security). Y para la migración, como no puedes recalcular los hashes sin las contraseñas originales, lo habitual es rehashear cada contraseña con Argon2id la próxima vez que esa persona inicie sesión correctamente.

Para la charla de RR. HH. esto se traduce en una línea: «Además, la huella se calcula de forma lenta a propósito, para que probar contraseñas a ciegas sea inútil».""",
            },
        ]
    },
    # 8) Transacción explicada a un jefe no técnico (léxico de España).
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi jefe (no es técnico) me ha preguntado por qué el programa de nóminas 'no puede quedarse a medias' si se cae el servidor. Le dije que porque usamos transacciones y se quedó igual. ¿Cómo se lo explico?",
            },
            {
                "role": "assistant",
                "content": """Explícaselo con una transferencia bancaria, que es el ejemplo para el que se inventaron las transacciones.

**El problema.** Pasar 1.000 € de la cuenta de la empresa a la de un empleado son dos operaciones: restar en una y sumar en otra. Si el servidor se cae justo entre las dos, los 1.000 € han salido de la empresa y no han llegado a nadie. Con una nómina de 300 empleados hay cientos de puntos así donde todo podría cortarse.

**La solución.** Una transacción agrupa todas esas operaciones en un paquete de «todo o nada»:

- Mientras el paquete no termina, ningún cambio es definitivo.
- Si todo va bien, al final se confirma de golpe (*commit*) y todos los cambios pasan a la vez.
- Si algo falla a mitad, incluido un apagón, la base de datos deshace todo lo que se hubiera hecho (*rollback*) y queda exactamente como antes de empezar.

**Una segunda garantía que conviene mencionar:** mientras la nómina se procesa, nadie más ve el estado intermedio. Si alguien consulta un informe a mitad del proceso, ve los datos de antes, no una mezcla de empleados pagados y sin pagar.

**Y el límite, para no prometer de más:** la transacción garantiza que la nómina se guarda entera o no se guarda; no garantiza que esté bien calculada. Si el programa calcula mal una retención, la transacción guardará ese error de forma impecable. Eso lo cubren las pruebas y las revisiones, no la base de datos.

Versión en dos frases para tu jefe:

> «El sistema trata la nómina como una sola operación: o se registra completa o no se registra nada. Si el servidor se cae a mitad, al volver está como antes de empezar y basta con lanzarla otra vez».

Ojo con esa última frase: solo es cierta si todo el proceso va en una única transacción. Si el programa confirma por bloques (por ejemplo, cada 50 empleados), un corte deja la mitad hecha y relanzarla podría pagar dos veces. Antes de decírselo, comprueba en el código dónde se hace el *commit*.""",
            },
        ]
    },
    # 9) Caché, con system rioplatense y usuario voseante.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {
                "role": "user",
                "content": "che, qué es la caché? en el laburo dicen 'borrá la caché' para todo y no entiendo qué estoy borrando",
            },
            {
                "role": "assistant",
                "content": """La caché es una copia guardada cerca de algo que está lejos o que cuesta conseguir, para no tener que ir a buscarlo cada vez.

**La analogía.** Imaginá que en tu oficina los expedientes están en un archivo del subsuelo. Si cada vez que necesitás uno bajás, lo buscás y subís, perdés diez minutos. Entonces hacés fotocopias de los que usás seguido y las dejás en tu escritorio. Eso es una caché: las fotocopias.

- **Ventaja:** todo va mucho más rápido.
- **Problema:** si alguien actualiza el expediente original, tu fotocopia queda vieja y vos seguís trabajando con datos viejos sin saberlo.

**Qué pasa en tu navegador.** Cuando entrás a una página, el navegador guarda copias de cosas que casi no cambian: el logo, los estilos, el código de la página. La próxima vez las carga de tu disco en lugar de bajarlas de nuevo. El propio sitio le dice al navegador cuánto tiempo puede usar cada copia.

Por eso aparece el clásico problema: el sitio se actualizó, pero vos ves la versión vieja, o una mezcla rara (la página nueva con un estilo viejo) que hace que algo no ande. **«Borrá la caché» es tirar las fotocopias para obligar al navegador a buscar los originales.**

**Qué estás borrando y qué no:**

- Borrar solo la caché (en Chrome: «Archivos e imágenes almacenados en caché») no te cierra ninguna sesión ni borra contraseñas. Lo peor que pasa es que la próxima carga es un poco más lenta.
- Borrar **cookies** es otra cosa: ahí sí se te cierran las sesiones. En la misma ventana del navegador aparecen como casillas separadas, así que fijate cuál marcás.

**Atajo antes de borrar nada:** la recarga forzada (Ctrl + Shift + R en Windows o Linux, Cmd + Shift + R en Mac) recarga esa página ignorando las copias. Arregla la mayoría de los casos sin tocar el resto.

Y si te dicen «borrá la caché» para un problema que no tiene nada que ver con ver algo desactualizado (por ejemplo, un error al guardar un formulario), es probable que no sirva: la caché solo explica los problemas de «estoy viendo algo viejo».""",
            },
        ]
    },
    # 10) Multiturno: recursión para principiantes, y qué pasa sin caso base.
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy empezando a programar y no entiendo la recursión. ¿Me la explicas sin código primero?",
            },
            {
                "role": "assistant",
                "content": """Imagina que estás en un cine a oscuras y quieres saber en qué fila estás. No puedes contar las filas, pero puedes hablar con la persona de delante.

1. Le preguntas: «¿En qué fila estás tú?».
2. Esa persona tampoco lo sabe, así que hace lo mismo: le pregunta a la de delante.
3. La pregunta avanza hasta la persona de la **primera fila**, que no tiene a nadie delante y sabe la respuesta sin preguntar: «Estoy en la 1».
4. Ahora la respuesta vuelve hacia atrás: la de la segunda fila suma uno y dice «2», la siguiente dice «3»… hasta que te llega a ti.

Eso es la recursión: resolver un problema pidiendo la solución de una versión **un poco más pequeña** del mismo problema. Tiene siempre dos partes:

- **Caso base:** la situación en la que la respuesta se sabe sin preguntar (la primera fila).
- **Caso recursivo:** la regla para resolver tu caso usando la respuesta del caso más pequeño («lo que me diga el de delante, más uno»).

Ahora sí, el código. El factorial de un número (4! = 4 × 3 × 2 × 1) tiene exactamente esa forma:

```python
def factorial(n: int) -> int:
    if n == 0:                    # caso base: la primera fila
        return 1
    return n * factorial(n - 1)   # pregunto al de delante y uso su respuesta
```

Traza de `factorial(3)`:

- `factorial(3)` necesita `factorial(2)` y espera.
- `factorial(2)` necesita `factorial(1)` y espera.
- `factorial(1)` necesita `factorial(0)` y espera.
- `factorial(0)` devuelve `1`: caso base.
- Vuelta atrás: `1 × 1 = 1`, `2 × 1 = 2`, `3 × 2 = 6`.

Fíjate en que nadie hace todo el trabajo: cada llamada hace una multiplicación y confía en que la de delante le devuelva lo correcto.""",
            },
            {
                "role": "user",
                "content": "¿Y qué pasa si me olvido del caso base?",
            },
            {
                "role": "assistant",
                "content": """En el cine: si la primera fila tampoco supiera la respuesta y siguiera preguntando hacia delante, la pregunta no terminaría nunca y nadie respondería.

En el ordenador ocurre lo mismo, con un detalle: cada llamada que se queda esperando ocupa un poco de memoria en la **pila de llamadas**, para recordar dónde estaba y qué le faltaba hacer. Sin caso base las llamadas se acumulan hasta llenar ese espacio. Python lo corta antes con un límite de unas 1.000 llamadas anidadas:

```text
RecursionError: maximum recursion depth exceeded
```

En otros lenguajes se ve como *stack overflow* («desbordamiento de pila»), que es literalmente el nombre del problema.

Hay una variante más traicionera: **tener caso base y no llegar nunca a él.** Con la función de antes:

```python
factorial(-1)   # -1, -2, -3... nunca llega a 0
```

El caso base existe, pero cada paso te aleja de él. Por eso la regla completa es: debe haber caso base, **y cada llamada recursiva debe acercarse a él**. La forma de blindarlo es rechazar la entrada imposible al principio:

```python
def factorial(n: int) -> int:
    if n < 0:
        raise ValueError(f"el factorial no está definido para negativos: {n}")
    if n == 0:
        return 1
    return n * factorial(n - 1)
```

Comprobación rápida: `factorial(0) == 1`, `factorial(5) == 120` y `factorial(-1)` lanza `ValueError` en vez de colgarse hasta el `RecursionError`.

Ten presente también que, aun con todo bien escrito, `factorial(5000)` fallaría en Python por ese límite de profundidad. Para entradas grandes, la versión con un bucle `for` es la adecuada.""",
            },
        ]
    },
    # 11) Multiturno: estructurar un documento de diseño a partir de notas sueltas.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Tengo que escribir un documento de diseño para mover nuestros cron jobs a una cola de tareas. Estas son mis notas tal cual, ayúdame a estructurarlo:

- los crons corren en una sola VM, si se cae no corre nada
- 23 jobs, algunos tardan 2 h
- a veces se solapan dos ejecuciones del mismo job (el de facturas) y se duplican correos
- opciones: Celery + Redis, AWS SQS + workers, Temporal
- el equipo conoce Python
- presupuesto: no más de 300 USD/mes extra
- hay que migrar sin parar la facturación
- no hay alertas cuando un job falla, nos enteramos por los clientes
- Temporal parece potente pero nadie lo conoce""",
            },
            {
                "role": "assistant",
                "content": """Esta estructura sigue el orden en que lo lee quien decide: problema, qué se quiere conseguir, opciones, propuesta y cómo se hace sin romper nada.

1. **Resumen** (5 líneas; escríbelo al final). Problema, propuesta, coste y plazo.
2. **Contexto y problema**
   - Los 23 jobs corren en una sola VM: si cae, no corre ninguno.
   - Ejecuciones solapadas del job de facturas que duplican correos.
   - Sin alertas: los fallos los detectan los clientes.
   Añade un incidente real con fecha para cada punto; un ejemplo concreto convence más que la descripción.
3. **Objetivos y no objetivos**
   - Objetivos: que la caída de una máquina no detenga los jobs, que un mismo job no se ejecute dos veces a la vez, y alertas ante cualquier fallo.
   - No objetivos: reescribir la lógica de los jobs o cambiar de lenguaje. Escribirlo evita que la discusión se desvíe.
4. **Requisitos y restricciones**: Python, como máximo 300 USD/mes adicionales, jobs de hasta 2 h, migración sin interrumpir la facturación.
5. **Alternativas consideradas**: Celery + Redis, SQS + workers y Temporal, con una tabla de criterios sacada de las secciones 3 y 4.
6. **Propuesta**: la opción elegida y por qué gana con esos criterios.
7. **Plan de migración**: orden de los jobs (facturación al final), ejecución en paralelo, criterio para dar cada job por migrado y cómo volver atrás.
8. **Observabilidad**: alertas, métricas por job y quién recibe los avisos.
9. **Riesgos y preguntas abiertas**.

Tres cosas que tus notas no resuelven y que el documento tiene que abordar:

- **La cola no arregla por sí sola el solapamiento.** Con varios workers, dos ejecuciones del job de facturas pueden correr a la vez en máquinas distintas; es más fácil que pase que ahora. Hace falta un candado por job o que el envío de correos sea idempotente. Va en Propuesta y en Riesgos.
- **Jobs de 2 h y reentregas.** Las colas reentregan un mensaje si el worker no confirma en cierto tiempo: en SQS es el *visibility timeout* (máximo 12 h), y con Celery sobre Redis el `visibility_timeout` por defecto es de 1 hora. Mal configurado, un job de 2 h se ejecutaría dos veces, que es justo el problema que quieres eliminar.
- **Quién dispara los jobs.** Una cola ejecuta tareas, pero alguien tiene que encolarlas a su hora. Si eso vive en otra VM única, conservas el punto único de fallo. Cada alternativa debe decir dónde vive el planificador.

«Temporal parece potente pero nadie lo conoce» no es una sección: es un criterio («curva de aprendizaje») dentro de la tabla de alternativas.""",
            },
            {
                "role": "user",
                "content": "Genial. Redáctame la sección de alternativas consideradas. Estamos en AWS.",
            },
            {
                "role": "assistant",
                "content": """## 5. Alternativas consideradas

Evaluamos tres opciones con los criterios de las secciones 3 y 4. En todas, cada job tendrá un candado por nombre para evitar ejecuciones simultáneas, así que ese requisito no diferencia a ninguna.

| Criterio | Celery + Redis | SQS + workers | Temporal |
|---|---|---|---|
| Tolera la caída de una máquina | Sí, si Redis es gestionado (ElastiCache) y `celery beat` puede reiniciarse en otra máquina | Sí: SQS y EventBridge Scheduler son servicios gestionados | Sí, con un clúster en alta disponibilidad o Temporal Cloud |
| Planificación periódica | `celery beat`, que debe correr como instancia única | EventBridge Scheduler, que envía el mensaje a SQS a la hora indicada | Integrada (*Schedules*), con política configurable para ejecuciones solapadas |
| Jobs de 2 h | Requiere subir el `visibility_timeout` de Redis por encima de la duración máxima | Requiere ajustar el *visibility timeout* de la cola (máximo 12 h) | Diseñado para tareas largas, con *heartbeats* |
| Conocimiento del equipo | Alto: Python y Celery son conocidos | Medio: Python, pero el bucle del worker lo escribimos nosotros | Bajo: modelo de programación nuevo |
| Coste adicional estimado | ElastiCache pequeño + workers | Coste de SQS despreciable a este volumen + workers | Clúster propio con su base de datos, o Temporal Cloud por uso |
| Encaje con el presupuesto (300 USD/mes) | Probable | Probable | Por confirmar |

**Celery + Redis.** Es la opción que el equipo podría poner en marcha antes. Sus puntos débiles son operativos: `celery beat` debe ser una única instancia (dos instancias encolarían cada job dos veces) y el `visibility_timeout` por defecto de 1 hora provoca reentregas en los jobs largos si no se ajusta. Ninguno de los dos es grave, pero los dos reproducen exactamente los fallos que queremos eliminar si se configuran mal.

**SQS + workers con EventBridge Scheduler.** Elimina todos los componentes que tendríamos que operar: la cola y el planificador son gestionados y no tienen un punto único de fallo nuestro. A cambio, el worker, los reintentos y la cola de mensajes fallidos (*dead-letter queue*) los configuramos y escribimos nosotros. Es la opción con menos piezas propias en producción.

**Temporal.** Resuelve de serie casi todo lo que pedimos: planificación, reintentos, visibilidad de cada ejecución y control de solapamientos. Pero ningún miembro del equipo lo conoce, introduce un modelo de programación con restricciones propias (el código de un *workflow* debe ser determinista) y su coste no está estimado. Para 23 jobs periódicos, la potencia que aporta no compensa la curva de aprendizaje en este momento; sería la opción natural si en el futuro aparecen procesos de varios pasos con estado.

**Descartada sin evaluar en detalle:** mantener cron y añadir una segunda VM en espera. Resuelve la caída de la máquina, pero no el solapamiento ni las alertas.

---

Dos notas para ti antes de enviarlo:

- Las filas de coste dicen «probable» y «por confirmar» porque no tengo tus cifras de instancias ni de volumen. Rellénalas con la calculadora de precios de AWS; un revisor rechazará una tabla de costes sin números.
- No incluí la recomendación aquí a propósito: la sección 6 la da, y separar «qué opciones había» de «cuál elegimos» hace que la tabla se lea como un análisis y no como una justificación a posteriori.""",
            },
        ]
    },
    # 12) Titulares para un post técnico.
    {
        "messages": [
            {
                "role": "user",
                "content": "Escribí un post para el blog técnico de la empresa sobre cómo pasamos de hacer polling cada 5 segundos a usar WebSockets en el panel de seguimiento de envíos. Bajamos las peticiones al backend un 92 % y el coste de infraestructura de ese servicio de 4.100 a 1.300 dólares al mes. Mi título actual es «Nuestra experiencia con WebSockets». ¿Me propones mejores?",
            },
            {
                "role": "assistant",
                "content": """Tu título actual tiene dos problemas: no dice qué problema resolviste y esconde tus dos mejores datos. «Nuestra experiencia con» podría encabezar un post sobre cualquier cosa.

Cinco opciones, agrupadas por lo que priorizan:

**Con el dato de rendimiento**
1. De polling a WebSockets: 92 % menos peticiones al backend
2. Dejamos de preguntar cada 5 segundos: WebSockets en el panel de envíos

**Con el dato de coste**
3. Cómo recortamos un 68 % el coste del seguimiento de envíos
4. De 4.100 a 1.300 dólares al mes cambiando polling por WebSockets

**Para quien busca comparar**
5. Polling frente a WebSockets en producción: lo que medimos

**Mi recomendación: la 1**, con la 4 como subtítulo. Quien lee un blog técnico busca la técnica y el resultado, y la 1 tiene las dos palabras que esa persona buscaría en Google, más una cifra concreta. El coste en el subtítulo atrae además a quien decide presupuestos.

Criterios que seguí:

- **Una cifra concreta.** Un número creíble vale más que cualquier adjetivo. Ojo: el 68 % lo calculé yo, (4.100 − 1.300) / 4.100 = 0,683; comprueba que el post use la misma cifra, o el lector atento lo notará.
- **Las palabras clave al principio.** Los buscadores y las redes cortan los títulos largos; todos los propuestos quedan por debajo de unos 70 caracteres.
- **Mayúscula solo en la primera palabra.** En español no se usa el estilo inglés de poner mayúscula en cada palabra («Cómo Recortamos Un 68 %…»). Solo van en mayúscula la inicial y los nombres propios. «WebSockets» conserva la suya por ser nombre de una tecnología.
- **Espacio entre la cifra y el %.** La norma académica es «92 %», con espacio (mejor uno de no separación, para que la cifra y el signo no queden en líneas distintas).
- **Nada que el post no cumpla.** Descarté opciones como «sin tocar el frontend» o «en una semana» porque no sé si son ciertas. Un título que promete más que el texto es *clickbait*, y en un blog de empresa cuesta credibilidad.""",
            },
        ]
    },
    # 13) Redactar un README en español a partir de datos dados.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito un README en español para una herramienta interna. Datos: se llama csvlimpio, es una CLI en Python 3.10+, se instala con pipx desde nuestro índice interno (https://pypi.interno.example/simple). Tiene dos subcomandos: `revisar ARCHIVO`, que lista problemas sin tocar nada (filas duplicadas, fechas en formatos mezclados, codificación que no es UTF-8), y `limpiar ARCHIVO -o SALIDA`, que aplica arreglos. Opciones de limpiar: `--dedup` quita filas duplicadas exactas, `--fechas iso` convierte las fechas a AAAA-MM-DD, `--encoding auto` detecta la codificación de entrada (por defecto asume utf-8). Nunca sobrescribe el archivo original. Licencia MIT. Lo mantiene el equipo de Datos (#datos-soporte en Slack).",
            },
            {
                "role": "assistant",
                "content": """````markdown
# csvlimpio

Revisa y limpia archivos CSV desde la terminal: filas duplicadas, fechas en formatos mezclados y codificaciones distintas de UTF-8. Nunca modifica el archivo original.

## Instalación

Requiere Python 3.10 o superior y [pipx](https://pipx.pypa.io/).

```bash
pipx install csvlimpio --index-url https://pypi.interno.example/simple
```

Comprueba la instalación:

```bash
csvlimpio --help
```

## Uso rápido

Primero revisa, luego limpia:

```bash
csvlimpio revisar ventas.csv
csvlimpio limpiar ventas.csv -o ventas_limpio.csv --dedup --fechas iso
```

## Comandos

### `revisar ARCHIVO`

Analiza el archivo y lista los problemas que encuentra, sin cambiar nada:

- filas duplicadas;
- fechas escritas en formatos distintos dentro del mismo archivo;
- codificación distinta de UTF-8.

Úsalo antes de `limpiar` para saber qué opciones necesitas.

### `limpiar ARCHIVO -o SALIDA`

Escribe en `SALIDA` una versión corregida de `ARCHIVO`. El original no se toca nunca; `-o` es obligatorio.

| Opción | Qué hace |
|---|---|
| `--dedup` | Elimina las filas duplicadas exactas (mismo valor en todas las columnas). |
| `--fechas iso` | Convierte las fechas al formato AAAA-MM-DD (ISO 8601). |
| `--encoding auto` | Detecta la codificación del archivo de entrada. Sin esta opción, se asume UTF-8. |

Sin opciones, `limpiar` no aplica ningún arreglo.

## Ejemplos

Archivo exportado desde Excel en Windows, con codificación desconocida:

```bash
csvlimpio limpiar clientes.csv -o clientes_utf8.csv --encoding auto
```

Quitar duplicados y unificar fechas en un solo paso:

```bash
csvlimpio limpiar pedidos.csv -o pedidos_limpio.csv --dedup --fechas iso
```

## Soporte

Mantiene el equipo de Datos. Dudas y errores en **#datos-soporte** (Slack).

## Licencia

MIT.
````

Decisiones y huecos:

- **Orden: qué es → instalar → usar en 30 segundos → referencia.** La mayoría de la gente llega al README para instalar y copiar un ejemplo; la tabla de opciones va después porque solo se consulta.
- **Dos frases que no estaban explícitas en tus datos**, pero se deducen de ellos: «`-o` es obligatorio» (si nunca sobrescribe, necesita destino) y «sin opciones, `limpiar` no aplica ningún arreglo». Confirma las dos; si la segunda es falsa (por ejemplo, si sin opciones aplica todo), cambia esa línea.
- **Asumí que pipx acepta tu índice con `--index-url`**, que es la opción de pipx para eso. Si en vuestra configuración el índice ya viene en `pip.conf`, basta con `pipx install csvlimpio`.
- **No incluí lo que no me diste**, aunque un buen README lo tendría:
  - Qué formatos de fecha de entrada reconoce `--fechas iso` y qué hace con una fecha ambigua como `03/04/2024` (¿3 de abril o 4 de marzo?). Es la pregunta que más llegará a #datos-soporte.
  - En qué columnas busca fechas: todas o solo algunas.
  - Si `--dedup` conserva la primera aparición o la última.
  - Códigos de salida (útiles si alguien la usa en un pipeline).""",
            },
        ]
    },
    # 14) Multiturno: criticar un párrafo y mejorarlo, con un corrector estricto.
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un corrector de estilo estricto: señalas cada problema antes de proponer la versión final.",
            },
            {
                "role": "user",
                "content": "Revísame este párrafo de una propuesta de proyecto: «En la actualidad, y cada vez más, las organizaciones se enfrentan a numerosos desafíos en materia de gestión de datos, lo cual hace que resulte fundamental contar con soluciones innovadoras y disruptivas que permitan optimizar los procesos de manera eficiente. Nuestra plataforma, basada en tecnologías de última generación, se posiciona como una herramienta clave para dar respuesta a estas necesidades, aportando valor añadido a lo largo de toda la cadena.»",
            },
            {
                "role": "assistant",
                "content": """**Problema principal: el párrafo no contiene ninguna afirmación comprobable.** No dice qué desafíos, qué organizaciones, qué procesos ni cuánto mejoran. Podría aparecer sin cambios en la propuesta de cualquier empresa de software, y quien evalúa lo nota en la primera línea.

Problemas concretos, en orden de gravedad:

1. **Adjetivos sin respaldo:** «innovadoras», «disruptivas», «de última generación», «clave», «valor añadido». Son afirmaciones que el lector no puede verificar, así que no las cree.
2. **Redundancia:** «optimizar de manera eficiente». Optimizar ya implica eficiencia.
3. **Arranque vacío:** «En la actualidad, y cada vez más». Es la frase que se escribe mientras se piensa qué decir; se puede eliminar sin perder nada.
4. **Circunloquios:** «en materia de» (= «de»), «lo cual hace que resulte fundamental» (= «por eso hace falta»), «dar respuesta a estas necesidades» (= «resolverlas»).
5. **Autoelogio en tercera persona:** «se posiciona como». Posicionarse es algo que decide el mercado, no el texto.
6. **Metáfora sin referente:** «a lo largo de toda la cadena». ¿Qué cadena? ¿De suministro, de valor, de datos?

Versión propuesta. No tengo tus datos, así que **asumo** que la plataforma unifica los datos de ventas de cadenas de tiendas; sustituye el sector y las cifras por los reales:

> Las cadenas con más de veinte tiendas suelen tener sus datos de ventas repartidos en tres o cuatro sistemas que no se comunican. Cerrar el mes les exige días de hojas de cálculo y conciliaciones manuales, y los errores aparecen cuando ya se han tomado decisiones. Nuestra plataforma conecta esos sistemas y genera el cierre de forma automática. En el piloto con una cadena de 35 farmacias, el cierre mensual pasó de seis días a uno.

Por qué funciona: cada frase hace un trabajo (quién tiene el problema, qué le cuesta, qué hacemos, prueba de que funciona). La cifra del piloto sustituye a los cinco adjetivos del original.""",
            },
            {
                "role": "user",
                "content": "Me gusta, pero ¿no queda demasiado seco? Es para pedir financiación y quiero que suene ambicioso.",
            },
            {
                "role": "assistant",
                "content": """La ambición en una propuesta se transmite con la **magnitud** del problema y del resultado, no con adjetivos. Quien evalúa ha leído «disruptivo» en la mitad de las propuestas de esa convocatoria; un dato de escala solo aparece en las buenas.

Añade una frase al final que diga hasta dónde puede llegar esto, con un número que puedas defender:

> … En el piloto con una cadena de 35 farmacias, el cierre mensual pasó de seis días a uno. **Solo en España hay más de 1.200 cadenas de ese tamaño en alimentación, farmacia y moda; con esta financiación queremos llegar a 50 en dos años.**

Esa frase es ambiciosa y no tiene un solo adjetivo: tamaño del mercado, objetivo y plazo.

Advertencias:

- **El 1.200 es inventado para el ejemplo.** Pon tu cifra real y ten a mano la fuente: un evaluador puede preguntarla, y una cifra que no puedes justificar resta más de lo que suma.
- **El objetivo tiene que ser coherente con el presupuesto que pides.** Si pides financiación para dos personas durante un año, «50 cadenas en dos años» debe ser creíble con ese equipo, o el evaluador dudará también del resto.
- **No vuelvas a meter los adjetivos «para dar color».** Si quieres más fuerza, cámbiala en los verbos: «conecta», «genera» y «pasó de seis días a uno» ya son activos y concretos.

Si el formato de la convocatoria tiene una sección de «impacto» o «escalabilidad», mueve allí la frase nueva y deja este párrafo como descripción del problema y la solución; los evaluadores suelen puntuar por secciones.""",
            },
        ]
    },
    # 15) Detectar falacias en un argumento dado.
    {
        "messages": [
            {
                "role": "user",
                "content": "Un compañero mandó esto al canal de arquitectura y quiero responder con argumentos, no con opiniones. ¿Qué falacias tiene? «Tenemos que reescribir el backend en Rust. Discord y Cloudflare lo usan, así que es lo que funciona a escala. El único que se opone es Pedro, y es lógico: lleva diez años con Java y no quiere aprender nada nuevo. Si seguimos con Java, el año que viene nadie querrá trabajar con nosotros y acabaremos cerrando. O lo reescribimos todo este año o nos quedamos atrás para siempre.»",
            },
            {
                "role": "assistant",
                "content": """Tiene cuatro falacias, una por frase. Ninguna demuestra que reescribir en Rust sea mala idea; demuestran que **este argumento** no sirve para decidirlo.

**1. «Discord y Cloudflare lo usan» → apelación a la autoridad + falsa analogía.**
Que empresas reconocidas usen algo no prueba que resuelva tu problema. Además, la comparación no se sostiene: esas empresas adoptaron Rust en componentes concretos, con problemas de rendimiento medidos y a una escala que probablemente no es la tuya. La pregunta relevante no es quién lo usa, sino qué problema tenemos que Java no resuelve.

**2. «Pedro se opone porque no quiere aprender» → ad hominem circunstancial.**
Ataca el supuesto motivo de Pedro en lugar de sus objeciones. Aunque fuera cierto que Pedro prefiere Java, sus argumentos (coste de la reescritura, riesgo, conocimiento del equipo) pueden ser correctos igualmente. Además, reduce un desacuerdo técnico a un rasgo personal, lo que hace más difícil que otros discrepen en público.

**3. «Si seguimos con Java, nadie querrá trabajar con nosotros y cerraremos» → pendiente resbaladiza.**
Encadena pasos sin justificar ninguno: Java → no atraemos talento → cerramos. Cada eslabón necesitaría evidencia, y el primero ya es dudoso: Java sigue siendo uno de los lenguajes con más demanda y más profesionales disponibles.

**4. «O lo reescribimos todo este año o nos quedamos atrás para siempre» → falso dilema.**
Presenta dos opciones como si fueran las únicas. Hay muchas intermedias: escribir en Rust solo el servicio que tenga un problema de rendimiento medido, migrar por partes sustituyendo un componente cada vez, o mejorar el sistema actual. «Para siempre» es además una exageración que ningún dato respalda.

**Cómo responder sin entrar en guerra.** No nombres las falacias en el canal: suena a corregir al compañero y la discusión pasa a ser sobre quién tiene razón. Haz las preguntas que el argumento evita:

> ¿Qué problema concreto tenemos hoy que Java no resuelve (latencia, memoria, coste)? ¿Tenemos medidas? ¿Cuánto costaría reescribir el backend y qué dejaríamos de hacer mientras tanto? Si hay un servicio con un problema medido, ¿por qué no empezamos por ese y comparamos?

Si su postura es buena, estas preguntas le dan la oportunidad de demostrarlo con datos. Si no lo es, las respuestas lo mostrarán sin que tengas que decirlo.

Una advertencia final: que un argumento sea falaz no hace falsa su conclusión. Quizá Rust sí convenga en algún servicio. Concluir «está mal argumentado, luego es falso» sería caer en otra falacia, la llamada falacia de la falacia.""",
            },
        ]
    },
    # 16) Multiturno: post hoc, ad ignorantiam y hombre de paja; luego "pero los datos son reales".
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En la retro alguien dijo esto y algo no me cuadra, pero no sé nombrarlo: «Desde que en marzo empezamos a hacer code review obligatorio, los bugs reportados en producción bajaron un 40 %. Está claro que las reviews funcionan. Y los que dicen que las reviews ralentizan al equipo no tienen datos que lo demuestren, así que no es verdad. Además, ¿qué proponen, que cada uno suba lo que quiera sin que nadie lo mire?»",
            },
            {
                "role": "assistant",
                "content": """Son tres falacias distintas, una en cada parte del argumento.

**1. «Desde marzo… bajaron un 40 %, está claro que funcionan» → post hoc ergo propter hoc («después de esto, luego a causa de esto»).**
Que B ocurra después de A no prueba que A cause B. Antes de atribuir la bajada a las reviews hay que descartar lo que también cambió desde marzo:
- ¿Se desplegó menos? Menos cambios en producción implican menos bugs nuevos, con o sin reviews.
- ¿Hubo otros cambios a la vez: más tests, un equipo de QA, una congelación de funcionalidades?
- ¿Cambió la forma de contar? «Bugs reportados» no es lo mismo que «bugs existentes»: si bajó el uso o cambió el canal de soporte, se reportan menos aunque haya los mismos.

**2. «No tienen datos que demuestren que ralentizan, así que no es verdad» → argumento ad ignorantiam (apelación a la ignorancia).**
La falta de pruebas de algo no prueba lo contrario. Lo correcto sería: «no lo sabemos». Y es fácil de medir: el tiempo desde que se abre un pull request hasta que se fusiona, antes y después de marzo.

**3. «¿Qué proponen, que cada uno suba lo que quiera?» → hombre de paja.**
Deforma la postura contraria para que sea fácil de rebatir. Quien dice que las reviews ralentizan casi nunca propone eliminarlas; suele pedir revisiones más pequeñas, tiempos de respuesta acordados o que los cambios triviales no esperen dos aprobaciones. Responder a «nadie mira nada» evita discutir esas propuestas reales.

Fíjate en que la conclusión, «las reviews ayudan», puede ser perfectamente cierta. El problema es que este argumento no la demuestra.""",
            },
            {
                "role": "user",
                "content": "Pero los datos son reales, los bugs bajaron de verdad. ¿Eso no basta?",
            },
            {
                "role": "assistant",
                "content": """No. El dato es real; lo que no está demostrado es la **causa**. Un ejemplo con números muestra por qué importa:

- Febrero: 50 despliegues, 20 bugs → 0,40 bugs por despliegue.
- Abril: 30 despliegues, 12 bugs → 0,40 bugs por despliegue.

Los bugs bajaron un 40 %, exactamente la cifra de la retro, y la calidad por cambio no mejoró nada: simplemente se desplegó un 40 % menos. Si las reviews ralentizaron al equipo, esta sería incluso una lectura coherente con los dos bandos.

Para que el dato se convierta en un argumento hacen falta comparaciones que descarten las otras explicaciones. De más fácil a más sólida:

1. **Normalizar.** Bugs por despliegue o por cada cien pull requests, no en total. Es un cálculo de cinco minutos con el historial de git y el gestor de incidencias.
2. **Evidencia directa.** Cuántos comentarios de review señalaron un defecto real que se corrigió antes de fusionar. Es la prueba más cercana a «las reviews atrapan bugs», porque no depende de qué más cambió en marzo.
3. **Comparar con un grupo sin el cambio.** Si algún equipo o repositorio adoptó las reviews más tarde, compara cómo evolucionaron ambos en el mismo periodo. Si los dos bajaron igual, la causa fue otra cosa.
4. **Mirar la tendencia previa.** Si los bugs ya bajaban desde noviembre, marzo no marca ningún cambio.

En la próxima retro puedes proponerlo sin contradecir a nadie: «Me parece plausible; para estar seguros, ¿medimos bugs por despliegue y el tiempo de los PR antes y después de marzo?». Esa misma medición responde también a la otra mitad de la discusión, la de si las reviews ralentizan al equipo.""",
            },
        ]
    },
    # 17) Usuario en inglés que pide el resumen en español.
    {
        "messages": [
            {
                "role": "user",
                "content": """I need to share this with my team in Bogotá; most of them prefer Spanish. Can you summarize it in Spanish, five bullet points max?

«Starting March 1, 2027, API keys created before January 2024 will stop working. Customers must migrate to scoped tokens. Scoped tokens can be restricted to specific projects and expire after 90 days by default, configurable up to one year. From January 15 to March 1, legacy keys will keep working in read-only mode so teams can test the migration. Webhooks signed with legacy keys must be re-registered. Rate limits remain unchanged. The migration tool in the dashboard can create equivalent tokens automatically, but it cannot update secrets stored in your CI systems.»""",
            },
            {
                "role": "assistant",
                "content": """- **El 1 de marzo de 2027 dejan de funcionar las API keys creadas antes de enero de 2024.** Hay que migrar a *scoped tokens* antes de esa fecha.
- **Desde el 15 de enero, las keys antiguas pasan a solo lectura.** Cualquier integración que escriba datos con una key antigua fallará a partir de esa fecha, no el 1 de marzo: ese es el plazo real para todo lo que escribe.
- **Los nuevos tokens se limitan por proyecto y caducan a los 90 días por defecto** (configurable hasta un año). Hay que planear su renovación.
- **Los webhooks firmados con keys antiguas hay que registrarlos de nuevo.** Los límites de peticiones no cambian.
- **La herramienta de migración del panel crea los tokens, pero no actualiza los secretos de CI.** Esos hay que cambiarlos a mano en cada pipeline.

Notes on the translation, in English since you asked in English:

- I kept *API key*, *scoped token* and *webhook* untranslated because Spanish-speaking dev teams use those terms as is, and they match what your team will see in the vendor's dashboard.
- Dates are written out ("1 de marzo de 2027"), not as 01/03/2027. In Colombia 01/03 reads as March 1st, but anyone used to the US format reads it as January 3rd; spelling the month out removes the ambiguity.
- I reworded the read-only period on purpose. The original presents it as a testing window, but its practical effect is that write access ends on January 15. That is the deadline your team most needs to notice, so I made it explicit rather than leaving it implied.""",
            },
        ]
    },
    # 18) Inglés: resumen de un postmortem para dirección.
    {
        "messages": [
            {
                "role": "user",
                "content": """Summarize this postmortem for our exec team. They're not technical: they want impact, cause, and what we're doing about it. Under 150 words.

«On Oct 3, between 14:05 and 15:40 UTC, checkout requests failed for approximately 18% of users in the EU region. Root cause: a configuration change to the CDN's TLS settings disabled TLS 1.2 on the EU edge, on the assumption that all clients supported TLS 1.3. Older Android devices (Android 9 and below) and some corporate proxies only support TLS 1.2. The change passed staging because staging traffic comes only from internal test devices. Detection took 50 minutes because our error-rate alert is global, and the EU-only spike stayed below the 5% global threshold. Estimated lost revenue: EUR 42,000. Action items: per-region alerting (owner: SRE, due Oct 24); synthetic checks from legacy clients (owner: QA, due Nov 7); two approvals required for CDN TLS changes (done).»""",
            },
            {
                "role": "assistant",
                "content": """**What happened.** On October 3, for 95 minutes, about 18% of our EU customers could not complete checkout. Estimated lost revenue: €42,000.

**Why.** A security setting change made our site reject connections from older phones and some corporate networks. Our test environment only uses modern internal devices, so the problem didn't show up before release. It then took 50 minutes to notice because our alarms watch worldwide error rates, and a problem limited to Europe didn't cross the global threshold.

**What we're doing.**
- Changes to this setting now require two approvals (done).
- Alarms per region, so a regional outage is caught in minutes (October 24).
- Automated tests that use older devices before each release (November 7).

---

That's about 110 words. What I left out and why:

- **TLS versions and the CDN.** Execs need to know that a setting excluded older devices, not which protocol version did it. The technical detail stays in the full postmortem.
- **Owners.** I kept dates but dropped team names; if your execs track accountability by team, add them back in parentheses.
- **"Root cause" as a heading.** I used "Why" instead. "Root cause" tends to read as "whose fault", and the real story here is a gap in testing and alerting, not one person's mistake.

I checked the arithmetic: 14:05 to 15:40 is 95 minutes, which I used instead of the raw timestamps.""",
            },
        ]
    },
    # 19) Inglés: reescribir una actualización de estado para que sea clara.
    {
        "messages": [
            {"role": "system", "content": "You are a concise technical editor."},
            {
                "role": "user",
                "content": "Can you rewrite this status update so it's clearer? It goes in the weekly email to stakeholders. «So basically this week we were mostly working on the payments thing, which is kind of blocked still because of the vendor not getting back to us about the webhook stuff, but we did manage to get the refunds part mostly done-ish, pending QA, and also there was the outage on Tuesday which took a bunch of time. Next week hopefully we can wrap up refunds and maybe start on invoices if the vendor responds.»",
            },
            {
                "role": "assistant",
                "content": """**Payments: weekly update**

**Done**
- Refunds: development complete; in QA.

**Blocked**
- Payment webhooks: waiting on the vendor's answer since [date]. **Ask:** we need someone with a vendor contact to escalate.

**Unplanned work**
- Tuesday's outage took roughly [N] engineer-days. Postmortem: [link].

**Next week**
- Ship refunds once QA passes.
- Start invoices, only if the vendor unblocks webhooks.

---

What changed and why:

1. **Structure by status, not by narrative.** Stakeholders scan for two things: is anything finished, and do they need to act. Headings answer both in five seconds.
2. **The blocker became an ask.** "Kind of blocked" invites no action. A blocker in a stakeholder email should say what's needed and from whom; that's often the only line a manager acts on.
3. **Hedges removed.** "Basically", "mostly", "done-ish", "hopefully", "a bunch of time". Each one makes the reader guess. "Development complete; in QA" says exactly what "mostly done-ish, pending QA" was trying to say.
4. **The dependency is explicit.** "Maybe start on invoices if the vendor responds" becomes a clear condition, so nobody reads it as a commitment.

The three bracketed fields are things your draft doesn't say and I can't infer: when you first contacted the vendor, how much time the outage cost, and where the postmortem lives. Fill them in. "Waiting since September 30" is far more persuasive for an escalation than "still waiting".""",
            },
        ]
    },
    # 20) Multiturno: deuda técnica explicada a un gerente, y cómo ponerle números.
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi gerente no entiende por qué pido dos semanas para «refactorizar» en vez de hacer features. ¿Cómo le explico la deuda técnica?",
            },
            {
                "role": "assistant",
                "content": """Con la metáfora original, que es financiera y la va a entender a la primera: **la deuda técnica es un préstamo**.

- **Pedir prestado:** cuando tomamos un atajo para llegar a una fecha (copiar código en vez de diseñarlo, saltarnos pruebas), ganamos tiempo hoy.
- **Pagar intereses:** a partir de ahí, cada cambio en esa parte del sistema cuesta más. Hay que entender el atajo, sortearlo y arreglar lo que rompe. Ese sobrecoste se paga en cada funcionalidad, para siempre, mientras la deuda siga ahí.
- **Amortizar el principal:** reorganizar ese código (lo que llamamos refactorizar) elimina la deuda y, con ella, los intereses.

Dos matices que hacen la explicación honesta y más convincente:

1. **Endeudarse no es malo.** A veces conviene, igual que pedir un crédito para abrir un negocio: llegar a tiempo a una feria puede valer más que el código perfecto. Lo malo es no saber cuánto debes o no pagar nunca.
2. **Los intereses son compuestos.** Sobre código con atajos se construyen más atajos, porque hacerlo bien ya es más caro. Por eso esperar sale cada vez más caro.

**Cambia también la palabra.** «Refactorizar» suena a capricho técnico. Habla del resultado: «Quiero dos semanas para que las funcionalidades de facturación pasen de tardar ocho días a tres». Eso es una inversión con retorno, que es el idioma de un gerente.""",
            },
            {
                "role": "user",
                "content": "Me va a pedir números. ¿Cómo le pongo cifras a eso?",
            },
            {
                "role": "assistant",
                "content": """Mide los intereses: cuánto tiempo pierde el equipo hoy por culpa de esa deuda. No hace falta precisión de contable, sino un orden de magnitud defendible. Tres fuentes que ya tienes:

1. **Tiempo de entrega en la zona afectada.** Compara cuánto tardaron cambios parecidos dentro y fuera del módulo problemático (desde que se empieza la tarea hasta que está en producción). Lo sacas del gestor de tareas o de las fechas de los pull requests.
2. **Incidencias y correcciones urgentes.** Cuántas incidencias de los últimos seis meses vinieron de ese módulo y cuántas horas se fueron en arreglarlas.
3. **Estimación del equipo, si no hay más.** Pregunta a cada persona cuántas horas a la semana pierde peleando con ese código. Es subjetivo, pero si cuatro personas dicen «unas dos horas» de forma independiente, el dato se sostiene.

Con eso haces la cuenta de amortización. Un ejemplo:

- Intereses: 4 personas × 2 h/semana = **8 h/semana** perdidas.
- Inversión: 2 semanas de 1 persona = **80 h**.
- Recuperación: 80 / 8 = **10 semanas**. A partir de ahí, todo es ganancia.

Plantéalo así: «Invertimos 80 horas y recuperamos 8 por semana; en dos meses y medio está pagado».

Dos cosas que te dan credibilidad:

- **Compromete una métrica de verificación.** «Mediré el tiempo de entrega de las próximas cinco funcionalidades de facturación y te lo enseño». Si no mejora, lo sabrás tú antes que él, y la próxima vez confiará en tus cifras.
- **Ofrece una alternativa más pequeña.** Si dos semanas seguidas no caben, propone dedicar un 15-20 % de cada sprint a pagar deuda en la zona que más intereses genera. Muchos gerentes aceptan antes un goteo constante que una pausa visible en las funcionalidades.""",
            },
        ]
    },
    # 21) Resumen con límite de palabras para el programa de una conferencia.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que mandar el resumen de mi charla para el programa de una conferencia, máximo 60 palabras, y el mío es eterno: «En esta charla voy a contar cómo en nuestra empresa, una fintech mediana con unos 80 desarrolladores, pasamos de tener los tests de integración tardando 45 minutos en CI a tardar 9 minutos. Hablaré de cómo identificamos los cuellos de botella con trazas de los propios tests, de por qué paralelizar no fue suficiente al principio (los tests compartían una base de datos y se pisaban), de cómo usamos contenedores efímeros con Testcontainers para aislar cada worker, y de los errores que cometimos por el camino, como cachear imágenes de Docker de forma incorrecta. También daré recomendaciones prácticas para equipos que quieran hacer lo mismo sin repetir nuestros errores. La charla está pensada para desarrolladores con experiencia en CI que sufren pipelines lentos.»",
            },
            {
                "role": "assistant",
                "content": """> Nuestros tests de integración tardaban 45 minutos en CI; hoy tardan 9. Contaré cómo encontramos los cuellos de botella con trazas de los propios tests, por qué paralelizar no bastó mientras compartían base de datos, cómo aislamos cada worker con Testcontainers y qué errores cometimos por el camino. Para desarrolladores con experiencia en CI que sufren pipelines lentos.

**58 palabras**, contando «45» y «9» como palabras.

Qué hice:

- **El resultado, primero.** «45 minutos → 9» es lo que hace que alguien marque tu charla en el programa. En el original aparecía en la línea dos, después de «En esta charla voy a contar», que no aporta nada: todo el programa son charlas.
- **Conservé los cuatro bloques del contenido** (diagnóstico, paralelización, aislamiento, errores), cada uno reducido a una cláusula. Son lo que distingue tu charla de otra sobre «CI más rápido».
- **Mantuve el público objetivo** al final. Ayuda a quien decide a qué sala ir y te trae a la audiencia correcta.

Qué quité y por qué:

- **«Fintech mediana con unos 80 desarrolladores».** Es contexto útil, pero cabe en tu biografía de ponente, que suele ir justo al lado del resumen.
- **«Recomendaciones prácticas»**: todas las charlas las prometen. La lista de lo que vas a contar ya deja claro que es práctica.
- **El ejemplo de la caché de imágenes de Docker.** Es lo que más me costó quitar: un error concreto atrae más que «qué errores cometimos». Si prefieres conservarlo, cambia «y qué errores cometimos por el camino» por «y cómo nos saboteó la caché de Docker»; sube a 60 palabras justas, así que revisa antes cómo cuenta la conferencia (algunos formularios cuentan caracteres, no palabras).

Comprobación de fidelidad: no prometo nada que no estuviera en tu texto. «Por qué paralelizar no bastó mientras compartían base de datos» resume el paréntesis del original sin afirmar que la paralelización fuera inútil.""",
            },
        ]
    },
    # 22) Multiturno de tres intercambios: resumen, versión de tuit y cambio de tono.
    {
        "messages": [
            {
                "role": "user",
                "content": "Resume este anuncio para la newsletter de la comunidad: «A partir del 1 de diciembre, la versión 1 de la API pública quedará obsoleta. Seguirá funcionando hasta el 31 de mayo de 2027, fecha en la que se apagará definitivamente. La versión 2, disponible desde hace un año, ofrece paginación por cursor, respuestas hasta un 30 % más rápidas y autenticación con OAuth 2.0 en lugar de claves estáticas. Hemos publicado una guía de migración con equivalencias de cada endpoint y habrá soporte prioritario en el foro durante diciembre y enero. Las integraciones que no se migren antes del 31 de mayo dejarán de recibir datos y devolverán un error 410 Gone.»",
            },
            {
                "role": "assistant",
                "content": """**La API v1 se apagará el 31 de mayo de 2027.** Queda obsoleta el 1 de diciembre y, a partir de mayo, las integraciones que sigan en v1 dejarán de recibir datos y obtendrán un error 410. La v2 ofrece respuestas hasta un 30 % más rápidas, paginación por cursor y OAuth 2.0 en lugar de claves estáticas. Para migrar hay una guía con la equivalencia de cada endpoint y soporte prioritario en el foro durante diciembre y enero.

Puse la fecha de apagado y su consecuencia en la primera frase, aunque el original empieza por la obsolescencia. «Obsoleta» no obliga a nada; «se apaga y deja de recibir datos» es lo que hace que alguien migre.""",
            },
            {
                "role": "user",
                "content": "Más corto, que quepa en un tuit.",
            },
            {
                "role": "assistant",
                "content": """> La API v1 se apaga el 31 de mayo de 2027 (obsoleta desde el 1 de diciembre). Migra a la v2: hasta un 30 % más rápida, con OAuth 2.0 y paginación por cursor. Guía de migración y soporte prioritario en el foro: https://…

Son unos 230 caracteres contando el enlace (X cuenta cualquier enlace como 23), así que caben en los 280 con margen para una etiqueta.

Quité el error 410: en un tuit, «se apaga» ya dice lo esencial. Mantuve el «hasta» del 30 %: sin él, la cifra prometería más que el anuncio original.""",
            },
            {
                "role": "user",
                "content": "Ahora en un tono más cercano, para el canal de Discord de la comunidad. Sin perder la fecha.",
            },
            {
                "role": "assistant",
                "content": """> Si tu integración todavía usa la API v1, es buen momento para pasarte a la v2: la v1 deja de funcionar el **31 de mayo de 2027**.
>
> Lo bueno del cambio: la v2 responde hasta un 30 % más rápido, pagina por cursor y usa OAuth 2.0, así que te olvidas de las claves estáticas. Tienes una guía que traduce cada endpoint de v1 a v2, y en diciembre y enero vamos a responder primero las dudas de migración en el foro. Si algo se te traba, pregunta ahí y lo vemos.

Qué lo hace cercano sin restarle seriedad:

- **Segunda persona y verbos de conversación** («pasarte», «te olvidas», «lo vemos») en lugar de «las integraciones que no se migren».
- **El beneficio va justo después del aviso**, no la amenaza del error: en un canal de comunidad, la gente responde mejor a «esto te conviene» que a «esto se rompe».
- **La fecha sigue en negrita y sin ambigüedad.** El tono cercano no puede suavizar el plazo. Evité frases como «sin prisa» o «cuando puedas», que en mayo se convertirían en quejas.

Dejé fuera la fecha de obsolescencia (1 de diciembre): para quien lee en Discord solo hay una fecha que importa, y dos fechas en un mensaje corto hacen que alguien recuerde la equivocada.""",
            },
        ]
    },
    # 23) Reescribir instrucciones para clientes como pasos numerados (principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que mandarle a los clientes de la tienda cómo activar la verificación en dos pasos y lo que escribí es un desastre: «Para activar la verificación en dos pasos primero tienen que tener instalada una app de autenticación como Google Authenticator o Microsoft Authenticator, después entrar a su cuenta y en Configuración buscar Seguridad y ahí darle a Activar verificación en dos pasos, les va a salir un código QR que tienen que escanear con la app, y luego poner el código de 6 números que les sale en la app, ojo que cambia cada 30 segundos, y guardar los códigos de recuperación en un lugar seguro porque si pierden el celular no van a poder entrar.»",
            },
            {
                "role": "assistant",
                "content": """**Cómo activar la verificación en dos pasos**

**Antes de empezar:** instale en su celular una app de autenticación, por ejemplo Google Authenticator o Microsoft Authenticator. Las dos son gratuitas.

1. Inicie sesión en su cuenta de la tienda.
2. Vaya a **Configuración** → **Seguridad**.
3. Pulse **Activar verificación en dos pasos**. Aparecerá un código QR.
4. Abra la app de autenticación en su celular y escanee el código QR.
5. La app mostrará un código de 6 números. Escríbalo en la tienda y pulse **Confirmar**.
   Si el código no funciona, espere a que la app muestre uno nuevo (cambia cada 30 segundos) y escríbalo otra vez.
6. **Importante:** la tienda le mostrará unos códigos de recuperación. Guárdelos en un lugar seguro fuera del celular, por ejemplo impresos o en su gestor de contraseñas. Si pierde el celular, son la única forma de volver a entrar a su cuenta.

Listo: a partir de ahora, al iniciar sesión, la tienda le pedirá su contraseña y el código de la app.

---

Por qué lo armé así:

- **Un paso, una acción.** Su texto tenía seis acciones en una sola frase; si el cliente se pierde en el tercer «y luego», no sabe dónde retomar. Con números, puede decir a soporte «me quedé en el paso 4».
- **Lo que hay que tener antes, fuera de los pasos.** Instalar la app es requisito previo: si el cliente lo descubre en el paso 4, tiene que salir de la tienda a mitad del proceso.
- **Cada aviso, en el paso donde importa.** Lo de los 30 segundos va en el paso 5, que es cuando el código falla. Los códigos de recuperación tienen paso propio y en negrita, porque es lo que más llamadas a soporte genera cuando se ignora.
- **Los nombres de los botones, en negrita y tal como aparecen en pantalla.** Así el cliente busca exactamente ese texto. Verifique que coinciden con su web: puse **Confirmar** en el paso 5 suponiendo que existe ese botón, porque su texto no lo decía.
- **Usé «usted»**, que es lo habitual con clientes en un texto de soporte. Si la tienda trata de «tú» en el resto de sus comunicaciones, cambie los imperativos (instale → instala, vaya → ve) para que no choque.""",
            },
        ]
    },
    # 24) Criptografía de clave pública y firma digital con analogías correctas (avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": "Doy un taller de seguridad para el equipo comercial y tengo que explicar la criptografía de clave pública: por qué puedo publicar mi clave y aun así nadie puede leer lo que me mandan, y qué es una firma digital. ¿Qué analogía uso que no sea mentira?",
            },
            {
                "role": "assistant",
                "content": """Usa dos imágenes distintas, una para cada cosa. Intentar explicar cifrado y firma con la misma analogía es lo que suele acabar en una explicación falsa.

**1. Cifrado: candados abiertos**

- Tienes una llave que no le das a nadie (**clave privada**).
- Fabricas todos los candados abiertos que quieras, que solo esa llave abre, y los repartes por todas partes (**clave pública**).
- Quien quiere mandarte algo secreto mete el mensaje en una caja y cierra uno de tus candados. Cerrarlo no requiere llave: basta con apretarlo.
- A partir de ese momento, ni siquiera quien lo cerró puede abrirlo. Solo tú, con tu llave.

Por eso publicar la clave pública es seguro: un candado sirve para cerrar, no para abrir. Tener mil copias de tus candados no acerca a nadie a tu llave.

**2. Firma digital: un sello que todo el mundo puede comprobar**

- Con tu clave privada produces un sello sobre un documento. Solo tú puedes producirlo.
- Cualquiera que tenga tu clave pública puede comprobar que el sello es auténtico, pero no puede fabricar uno nuevo.

Y aquí está el punto en que la firma digital es mejor que cualquier sello físico: **el sello depende del contenido exacto del documento.** Si alguien cambia una coma, la comprobación falla. Un sello de lacre se podría despegar y poner en otra carta; una firma digital no, porque se calcula a partir de la huella (el *hash*) de ese documento concreto. Es lo que la convierte en prueba de dos cosas: quién lo firmó y que nadie lo modificó después.

**3. El problema que conviene contar al equipo comercial**

¿Cómo sabes que el candado que te dieron es de verdad mío? Un impostor podría repartir candados suyos diciendo que son míos, y leer todo lo que me mandan. La solución son los **certificados**: una entidad en la que todos confían (una autoridad de certificación) firma un documento que dice «este candado pertenece a tienda.example». Es lo que comprueba tu navegador cuando muestra que la conexión es segura. Para un equipo comercial es la parte más útil: el candado del navegador confirma con quién hablas y que nadie lee la conexión por el camino, no que la empresa sea honrada. Una web de *phishing* también puede tener certificado.

**Dónde no llevar la analogía**

- En la práctica, la clave pública no se usa para cifrar todo el contenido, sino para acordar de forma segura una clave compartida y rápida que se usa el resto de la conversación. Para el taller no hace falta entrar ahí, pero no digas que «todo se cifra con el candado».
- Los candados digitales se copian sin coste ni límite; los físicos no. No es un problema para la explicación, porque precisamente por eso se pueden repartir.

Resumen para la diapositiva:
- **Cifrar:** cualquiera puede cerrar un candado mío; solo yo puedo abrirlo.
- **Firmar:** solo yo puedo sellar; cualquiera puede comprobar el sello, y si el documento cambia, el sello deja de valer.
- **Certificado:** un tercero de confianza garantiza que el candado es realmente mío.""",
            },
        ]
    },
    # 25) Texto con trampa: reseña irónica con cinco estrellas.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que resumir las reseñas de la app para el informe mensual. ¿Cómo resumirías esta? «Genial, la nueva actualización. Ahora la app me pide la contraseña siete veces antes de dejarme entrar; por fin entiendo por qué dicen que es segura. Lo de las notificaciones a las 3 de la mañana también es un detalle precioso. Cinco estrellas por el esfuerzo, de verdad.» Viene con 5 estrellas, así que la cuento como positiva, ¿no?",
            },
            {
                "role": "assistant",
                "content": """No: es una reseña **negativa escrita con ironía**. Las cinco estrellas contradicen el contenido, y lo que cuenta para el informe es el contenido.

Las señales de ironía, una por frase:

1. **«Genial, la nueva actualización»**, seguido inmediatamente de una queja. El elogio sin ningún motivo concreto, justo antes de un problema, es la marca más típica.
2. **«Por fin entiendo por qué dicen que es segura»**: presenta un fallo (pedir la contraseña siete veces) como si fuera una virtud. Nadie considera seguro un inicio de sesión que no funciona.
3. **«Un detalle precioso»** aplicado a notificaciones a las 3 de la mañana. Ningún usuario valora eso literalmente.
4. **«Cinco estrellas por el esfuerzo, de verdad»**: el «de verdad» final insiste en la sinceridad justamente porque no la hay.

Resumen para el informe:

> **Negativa (irónica, pese a las 5 estrellas).** Tras la última actualización, la app pide la contraseña varias veces antes de permitir el acceso (el usuario dice siete) y envía notificaciones de madrugada.

Decisiones de ese resumen:

- **«Varias veces (el usuario dice siete)».** En un texto irónico, las cifras pueden ser exageración. Registro el dato sin presentarlo como medido.
- **Dos problemas, dos categorías.** Inicio de sesión y notificaciones son incidencias distintas, probablemente de equipos distintos. Si el informe agrupa por tema, esta reseña suma en ambos.
- **Señalo la discrepancia de estrellas.** Quien lea el informe y vea la puntuación original necesita saber por qué la clasificaste al revés.

Una consecuencia para el método del informe: si en algún momento clasificas reseñas solo por estrellas o con una herramienta automática de análisis de sentimiento, esta acabaría como positiva. Las palabras «genial», «precioso» y «cinco estrellas» empujan en esa dirección. Antes de fiarte de la clasificación automática, revisa a mano una muestra, sobre todo las de puntuación alta que mencionen algún fallo.""",
            },
        ]
    },
    # 26) Verificar la fidelidad de un resumen escrito por el usuario (avanzado).
    {
        "messages": [
            {
                "role": "user",
                "content": """¿Es fiel mi resumen? Va en la presentación para dirección.

Texto original: «Un estudio interno con 120 desarrolladores de tres equipos comparó durante seis semanas el uso de un asistente de código frente a no usarlo. Los participantes que usaron el asistente completaron las tareas de tipo CRUD un 26 % más rápido de media. En tareas de depuración no hubo diferencias significativas. Los revisores encontraron una tasa de defectos similar en ambos grupos, aunque señalaron que el código generado tendía a duplicar lógica existente en lugar de reutilizarla. Los autores advierten de que la muestra no incluyó a desarrolladores júnior y de que la mayoría de los participantes ya conocía el código base.»

Mi resumen: «El estudio demuestra que los asistentes de código hacen a los desarrolladores un 26 % más productivos sin afectar a la calidad del código, aunque tienden a duplicar lógica.»""",
            },
            {
                "role": "assistant",
                "content": """No del todo: el resumen es más fuerte y más general que el estudio, justo en la dirección que más influye en una decisión de dirección. Lo comprobé afirmación por afirmación:

| Tu resumen dice | El texto dice | Veredicto |
|---|---|---|
| «El estudio demuestra» | Un estudio interno de 6 semanas, con limitaciones declaradas por los autores | **Exagera.** «Indica» o «encontró» se ajusta a lo que hay. |
| «un 26 % más productivos» | 26 % más rápido **en tareas CRUD**; en depuración, sin diferencias | **Generaliza.** El 26 % vale para un tipo de tarea, y medía velocidad, no productividad. |
| «sin afectar a la calidad» | Tasa de defectos similar, **pero** duplicación de lógica | **Contradicción interna.** Duplicar lógica es un problema de calidad (mantenibilidad); tu propia frase lo menciona a continuación. |
| «aunque tienden a duplicar lógica» | Correcto | **Fiel.** |
| (omitido) | Sin júnior; la mayoría conocía el código base | **Omisión relevante.** Si dirección decide para toda la plantilla, son justo los dos casos que el estudio no cubre. |

Versión fiel, con la misma extensión aproximada:

> En un estudio interno de seis semanas con 120 desarrolladores, quienes usaron el asistente completaron las tareas CRUD un 26 % más rápido, sin diferencias en depuración. La tasa de defectos fue similar, aunque el código generado tendía a duplicar lógica existente. El estudio no incluyó perfiles júnior y casi todos los participantes conocían el código base.

Por qué importa cada corrección en una presentación a dirección:

- **«26 % más productivos»** es la frase que se citará en otras reuniones. Si alguien hace la cuenta («26 % más productivos equivale a contratar a uno de cada cuatro desarrolladores»), estará decidiendo sobre un dato que el estudio no contiene.
- **Las limitaciones no son letra pequeña.** Si dirección decide extender el asistente a los júnior, querrá saber que no hay datos sobre ellos. Omitirlo ahora es lo que te pedirán explicar después.

Comprobación final: cada cifra y cada afirmación de la versión fiel aparece en el original, y ninguna afirmación del original con peso para la decisión quedó fuera.""",
            },
        ]
    },
    # 27) Convertir una política en preguntas frecuentes.
    {
        "messages": [
            {
                "role": "user",
                "content": "Convierte esta política en preguntas frecuentes para la intranet: «Las copias de seguridad de los portátiles corporativos se realizan automáticamente cada día a las 13:00 si el equipo está conectado a la red de la oficina o a la VPN. Se conservan las copias diarias de los últimos 30 días y una copia mensual durante un año. Las carpetas Descargas y Escritorio no se incluyen. Los archivos de más de 2 GB se excluyen salvo solicitud expresa a Sistemas. Para restaurar un archivo, abra un ticket en la categoría Restauraciones indicando ruta y fecha aproximada; el plazo de respuesta es de un día laborable. Los datos personales no relacionados con el trabajo no deben almacenarse en los equipos corporativos.»",
            },
            {
                "role": "assistant",
                "content": """**Copias de seguridad del portátil: preguntas frecuentes**

**¿Se guarda lo que tengo en el Escritorio o en Descargas?**
No. Esas dos carpetas no se incluyen en la copia. Si guardas ahí documentos de trabajo, muévelos a otra carpeta.

**¿Tengo que hacer algo para que se haga la copia?**
No. Se hace automáticamente cada día a las 13:00, siempre que el portátil esté conectado a la red de la oficina o a la VPN.

**Trabajo desde casa. ¿Se hace la copia?**
Solo si a las 13:00 estás conectado a la VPN.

**Borré un archivo hace unas semanas. ¿Puedo recuperarlo?**
Sí, si fue en los últimos 30 días: se guarda una copia de cada día. De ahí hacia atrás, durante un año, se guarda una copia por mes.

**¿Cómo pido que me restauren un archivo?**
Abre un ticket en la categoría **Restauraciones** indicando la ruta del archivo (por ejemplo, `Documentos/Clientes/contrato.docx`) y la fecha aproximada que quieres recuperar. Sistemas responde en un día laborable.

**Tengo archivos muy grandes. ¿Se copian?**
Los archivos de más de 2 GB no se incluyen. Si necesitas que se copie alguno, pídelo expresamente a Sistemas.

**¿Puedo guardar fotos u otros archivos personales en el portátil?**
No. Los datos personales que no tengan relación con el trabajo no deben guardarse en los equipos de la empresa.

---

Criterios:

- **Preguntas como las haría alguien, no como títulos de la política.** «¿Se guarda lo que tengo en el Escritorio?» en lugar de «Exclusiones».
- **Orden por riesgo, no por el orden del texto.** Lo del Escritorio va primero porque mucha gente guarda allí su trabajo y descubrirá que no tenía copia justo cuando la necesite.
- **Un ejemplo de ruta** en la pregunta de restauración, porque «indicar la ruta» no significa nada para quien no sabe qué es.

Tres huecos de la política que conviene confirmar con Sistemas antes de publicar, porque generarán tickets:

1. **Si el portátil está apagado a las 13:00**, ¿se pierde la copia de ese día o se hace al conectarlo? La política no lo dice y la respuesta cambia lo que hay que decirle a quien teletrabaja.
2. **La copia mensual, ¿de qué día del mes es?** De ello depende algo poco intuitivo: un archivo que se creó y se borró entre dos copias mensuales, hace más de 30 días, no se puede recuperar. No lo puse en las preguntas porque es una deducción mía, pero si Sistemas lo confirma merece una entrada.
3. **¿Se avisa a alguien si la copia falla?** Si no, conviene decirlo, para que nadie dé por hecho que tiene copia.""",
            },
        ]
    },
    # 28) Inglés: explicar qué es un índice de base de datos a un cofundador no técnico.
    {
        "messages": [
            {
                "role": "user",
                "content": "My cofounder isn't technical and keeps asking why we can't just 'add indexes to everything' to make the app faster. How do I explain what a database index is, and why that doesn't work?",
            },
            {
                "role": "assistant",
                "content": """Use the index at the back of a book. It maps surprisingly well, including the part about why you can't have indexes on everything.

**What an index is.** To find every mention of "inflation" in a 600-page book without an index, you read all 600 pages. With an index, you look up "inflation" in an alphabetical list, get page numbers, and go straight there. A database works the same way: without an index on the column you search by, it reads every row of the table; with one, it jumps to the matching rows. On a table with millions of rows, that's the difference between seconds and milliseconds.

**Why not index everything:**

1. **Every edit has to update every index.** If the book had twenty indexes (by topic, by person, by date, by place…), adding one paragraph means updating all twenty. In the database, every insert or update gets slower with each index you add. For a table that's written to constantly, like orders or events, too many indexes slow down exactly the operations customers wait on.
2. **Indexes take space.** Twenty indexes could take more pages than the book itself. They also compete for memory, and a database is fast largely because the data it uses most fits in memory.
3. **An index only helps the lookups it's organized for.** An index sorted by surname doesn't help you find people by city. And some questions don't benefit from any index: "show me every order" has to read everything anyway, and an index on a yes/no column barely narrows anything down.

**What to tell your cofounder:** "Indexes make reads faster and writes slower. We add them where we've measured a slow query, not everywhere."

That last part is also what to actually do. Find the slow queries first, then index for those. In PostgreSQL, for example, the `pg_stat_statements` extension shows which queries take the most total time, and `EXPLAIN ANALYZE` on one of them shows whether it's scanning the whole table. If it is, and the query is frequent, that's where an index pays off. Then check it worked by running `EXPLAIN ANALYZE` again: the plan should switch from a sequential scan to an index scan, and the time should drop.""",
            },
        ]
    },
    # 29) Lenguaje claro: cláusula de términos de servicio.
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero poner en lenguaje claro esta cláusula de nuestros términos de servicio para una página de resumen que irá junto al texto legal: «El Usuario otorga al Prestador una licencia no exclusiva, mundial, gratuita y transferible para usar, reproducir y mostrar el Contenido que el Usuario publique en la Plataforma, con la única finalidad de prestar y mejorar el Servicio. Dicha licencia se extinguirá cuando el Usuario elimine el Contenido, salvo en la medida en que el Contenido haya sido compartido con terceros que no lo hayan eliminado, o sea necesario conservarlo para cumplir obligaciones legales.»",
            },
            {
                "role": "assistant",
                "content": """Versión en lenguaje claro:

> **Lo que publicas y lo que podemos hacer con ello**
>
> Para que la plataforma funcione, nos das permiso para guardar, copiar y mostrar lo que publicas en ella. Solo usamos ese permiso para ofrecer el servicio y mejorarlo.
>
> - **No te pagamos por ese permiso**, y vale en cualquier país.
> - **No es exclusivo:** puedes dar permiso a quien quieras para usar tu contenido en otros sitios.
> - **Podemos traspasarlo** a otra empresa.
>
> **Cuando borras tu contenido, el permiso termina**, con dos excepciones:
> - las copias que otras personas hayan compartido y no hayan borrado;
> - lo que la ley nos obligue a conservar.

Cómo traduje cada término jurídico, para que puedas revisarlo:

| Original | Versión clara | Nota |
|---|---|---|
| licencia | permiso | Equivalente en lenguaje común. |
| no exclusiva | puedes dar permiso a otros | Lo expliqué por su consecuencia práctica para el usuario. |
| mundial | vale en cualquier país | |
| gratuita | no te pagamos | Formulado desde el lado del usuario, que es quien lee. |
| transferible | podemos traspasarlo a otra empresa | **Es la parte que hay que revisar con el equipo legal.** |
| usar, reproducir y mostrar | guardar, copiar y mostrar | «Usar» es muy amplio; lo concreté en «guardar». Si legal quiere mantener la amplitud, pon «usar, copiar y mostrar». |
| se extinguirá | termina | |

Tres decisiones que conviene validar con legal:

1. **No suavicé «transferible».** Es la palabra que más incomoda al usuario y la tentación es omitirla. Pero un resumen que promete menos de lo que dice el texto legal puede considerarse engañoso, y es justo lo que un usuario molesto citaría. No sé a quién y en qué casos lo traspasaríais (proveedores, una venta de la empresa…); si legal lo concreta, añádelo, porque un ejemplo tranquiliza más que la palabra sola.
2. **No escribí «lo que publicas sigue siendo tuyo»**, aunque es la frase que suele abrir estos resúmenes. La cláusula lo da a entender (das un permiso, no cedes la propiedad), pero no lo dice. Si otra cláusula de los términos lo afirma, añádelo arriba: es lo primero que quiere saber quien lee.
3. **Usé «tú».** Si el resto de la web trata de «usted», cambia los verbos para que no choque con el texto legal de al lado.

Añade al pie una línea del tipo «Este resumen no sustituye a los términos completos», con enlace a la cláusula, para que quede claro cuál de los dos textos manda.""",
            },
        ]
    },
    # 30) Revisar analogías de una formación básica: cuáles son correctas y cuáles no.
    {
        "messages": [
            {
                "role": "user",
                "content": "Preparo una formación de informática básica para el personal administrativo y tengo estas analogías en las diapositivas. ¿Son correctas? 1) La RAM es el escritorio y el disco duro es el archivador. 2) La nube es simplemente el ordenador de otra persona. 3) Un virus es como un bug del programa. 4) La dirección IP es el DNI del ordenador. 5) El wifi es internet.",
            },
            {
                "role": "assistant",
                "content": """Una es buena, una es incompleta y tres enseñan algo falso. La prueba que apliqué a cada una: ¿la conclusión que sacará el público al pensar en la analogía es cierta en la realidad?

**1. RAM = escritorio, disco = archivador → correcta.** Funciona en todo lo importante: el escritorio es rápido de usar pero pequeño, y el archivador es grande pero lento. Añade el detalle que la completa: **al apagar, el escritorio se vacía.** Así se entiende por qué se pierde un documento sin guardar cuando se va la luz.

**2. «La nube es simplemente el ordenador de otra persona» → incompleta.** Es verdad que tus archivos están en ordenadores de otra empresa. Pero «simplemente» esconde lo que el personal necesita saber: esos ordenadores están en centros de datos con copias en varios sitios (por eso es raro perder datos en la nube), y a cambio dependes de esa empresa y de tu conexión. Propuesta: «La nube son ordenadores de otra empresa, en centros de datos, a los que accedes por internet: es más difícil perder los datos, pero sin conexión no llegas a ellos».

**3. Virus = bug → incorrecta, y es la más peligrosa.** Un bug es un error involuntario de quien hizo el programa. Un virus es un programa malicioso hecho a propósito para dañar o robar. Si el personal los confunde, entenderá una infección como «un fallo técnico, no es culpa de nadie», justo cuando la lección que necesitas es «no abras adjuntos que no esperabas». Propuesta: «Un bug es una errata en un libro; un virus es un desconocido que entra en la oficina disfrazado de repartidor».

**4. IP = DNI → incorrecta.** El DNI es permanente y solo tuyo. La IP cambia al reiniciar el router o al conectarte desde otra red, y todos los equipos de la oficina suelen salir a internet con la misma IP pública. Propuesta: **la dirección postal**. Indica adónde entregar los datos, cambia si te mudas, y en un edificio de oficinas todos comparten la dirección de la calle mientras la recepción reparte el correo por despachos, que es lo que hace el router.

**5. Wifi = internet → incorrecta, y genera tickets de soporte.** El wifi es solo la conexión sin cables entre tu equipo y el router. Internet empieza al otro lado del router. Por eso existen dos averías distintas: «no tengo wifi» (el problema está en tu equipo o en el router) y «tengo wifi pero no internet» (el problema está más allá, a menudo en el proveedor). Propuesta: «El wifi es el pasillo de tu casa hasta la puerta; internet es la calle». Si el personal distingue los dos casos, los avisos a soporte serán mucho más útiles.

Regla para cualquier analogía que añadas: escribe al lado en qué se parece y dónde deja de valer. Si no encuentras dónde deja de valer, no la has pensado lo suficiente; si deja de valer justo en lo que quieres enseñar, cámbiala.""",
            },
        ]
    },
]
