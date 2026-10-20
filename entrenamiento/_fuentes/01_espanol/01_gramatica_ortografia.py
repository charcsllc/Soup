"""Español: gramática y ortografía. 30 filas SFT (chatml).

Temas: tildes diacríticas, porqué/por qué/porque/por que, haber/a ver, hay/ahí/ay,
leísmo/laísmo, subjuntivo vs indicativo, concordancia, gerundio, queísmo/dequeísmo,
mayúsculas, puntuación (coma, punto y coma, rayas, diálogos), voseo, anglicismos,
corrección de textos con varios errores, ambigüedad sintáctica.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# --- Bloque 1 ---
ROWS += [
    # 1) Tildes diacríticas (usuario voseante).
    {
        "messages": [
            {"role": "user", "content": "¿Me podés explicar de una vez las tildes diacríticas? Nunca sé si «aun» lleva tilde o no, y lo mismo con «mas»."},
            {
                "role": "assistant",
                "content": """La tilde diacrítica no marca dónde se pronuncia la fuerza: distingue dos palabras que suenan igual y tienen distinta función. En monosílabos son ocho pares; «aún/aun» es el único bisílabo del grupo.

| Con tilde | Sin tilde |
|---|---|
| **tú** (pronombre: tú sabés) | **tu** (posesivo: tu casa) |
| **él** (pronombre: él vino) | **el** (artículo: el perro) |
| **mí** (pronombre: para mí) | **mi** (posesivo: mi libro; nota musical) |
| **sí** (afirmación; reflexivo: volvió en sí) | **si** (condición; nota musical) |
| **té** (infusión) | **te** (pronombre: te llamo) |
| **dé** (verbo dar: que me dé) | **de** (preposición) |
| **sé** (saber, ser: no sé; sé bueno) | **se** (pronombre: se fue) |
| **más** (cantidad: más rápido) | **mas** (= pero, literario) |
| **aún** (= todavía) | **aun** (= incluso, hasta, también) |

Los dos que te trabás:

- **aún / aun.** Sustituí por «todavía». Si la frase funciona, lleva tilde. «Aún no llegó» → «Todavía no llegó» ✓. «Aun así, lo intentó» → «Todavía así» ✗; es «incluso así», sin tilde. Lo mismo con «ni aun» (= ni siquiera) y «aun cuando» (= aunque): siempre sin tilde.
- **más / mas.** «Mas» sin tilde solo existe como conjunción equivalente a «pero», y hoy aparece casi únicamente en textos literarios. Si estás escribiendo un correo o un mensaje, la probabilidad de que quieras «mas» es prácticamente cero: va con tilde.

Tres cosas que la gente cree que son diacríticas y no lo son:

1. **«Solo»** y los demostrativos («este», «ese», «aquel»): desde la Ortografía de 2010 se escriben sin tilde. En 2023 la RAE aclaró que quien escribe puede tildarlos si percibe ambigüedad, pero no es obligatorio nunca.
2. **«Ti»** no lleva tilde jamás. Es una falta frecuentísima por analogía con «mí» y «sí», pero «ti» no tiene ninguna palabra homófona de la que distinguirse.
3. **«Dio», «vio», «fue», «fui», «guion»**: monosílabos sin tilde. «Guion» la perdió en 2010 y sigue siendo de las faltas más repetidas.

Verificación con tus dos dudas en una sola frase: «Aún no entiendo por qué, mas lo acepto» = «Todavía no entiendo por qué, pero lo acepto». Las dos tildes están donde tienen que estar.""",
            },
        ]
    },
    # 2) porqué / por qué / porque / por que.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Diferencia entre porque, por que, por qué y porqué. Dame una regla que pueda aplicar sin pensar mucho: me toca revisar la documentación de mi equipo y esto aparece mal todo el tiempo."},
            {
                "role": "assistant",
                "content": """Cuatro formas, dos preguntas para decidir: ¿pregunta o explica? y ¿es un sustantivo?

**1. «Por qué» (separado, con tilde): pregunta o exclama.** Directa o indirecta. Prueba: puedes añadir «razón» o «motivo» detrás («por qué razón»).
- ¿Por qué falla el despliegue?
- No entiendo por qué falla el despliegue. (Indirecta: sin signos, pero sigue siendo una pregunta.)

**2. «Porque» (junto, sin tilde): responde o explica la causa.** Prueba: sustituible por «ya que» o «puesto que».
- Falla porque la variable de entorno no está definida. → ya que no está definida ✓

**3. «Porqué» (junto, con tilde): sustantivo.** Significa «motivo» y, como cualquier sustantivo, admite artículo y plural. Prueba: si puedes poner «el» delante o cambiarlo por «el motivo», es esta.
- Documenta el porqué de cada decisión. → el motivo de cada decisión ✓
- Los porqués del cambio.

**4. «Por que» (separado, sin tilde): preposición + «que».** Dos casos:
- Relativo: «por» + «el cual / la cual». Prueba: inserta «el» o «la» entre las dos palabras. «La razón por que renunció» → «por la que renunció» ✓. Hoy casi siempre se escribe con artículo, así que verlo sin él es raro, pero correcto.
- Verbos o sustantivos que rigen «por» seguidos de «que»: «preocuparse por que», «velar por que», «optar por que». Prueba: quita «que» y el verbo sigue pidiendo «por». «Se preocupa por que todo salga bien» → «se preocupa por eso» ✓.

**Regla de revisión en tres pasos:**

1. Si hay pregunta, aunque no haya signos, es «por qué».
2. Si puedes poner «el» delante, es «porqué».
3. Si no es ninguna de las dos, es «porque», salvo que el verbo anterior rija «por» (preocuparse, velar, optar, luchar, apostar): entonces «por que».

Lo que verás mal con más frecuencia en documentación técnica es el paso 3 en sentido contrario: «No se sabe porqué el servicio reinicia» (debe ser «por qué») y «Explicamos el por qué del cambio» (debe ser «el porqué»). Este último es el error favorito de los títulos de sección.

Verificación con los cuatro en una frase: «No sé **por qué** insistes en documentar el **porqué** de cada cosa, **porque** nadie lee las notas **por que** tanto te preocupas».""",
            },
        ]
    },
    # 3) haber / a ver, con erratas en el prompt.
    {
        "messages": [
            {"role": "user", "content": "haber si me explicas cuando se escribe 'haber' y cuando 'a ver', porque yo escribo 'haber si llueve' y mi hermana dice que esta mal"},
            {
                "role": "assistant",
                "content": """Tu hermana tiene razón, y la prueba está en tu propio mensaje: «haber si me explicas» debería ser «a ver si me explicas».

Son dos cosas que no tienen nada que ver y solo coinciden en la pronunciación.

**«A ver»** = preposición «a» + verbo «ver». Se usa para:
- Pedir que te muestren algo o expresar expectación: «A ver, enséñame la foto».
- «A ver si» + verbo: deseo, intención o advertencia: «A ver si llueve de una vez», «A ver si nos vemos pronto», «A ver si te vas a caer».
- Aceptar algo con reservas: «—¿Vienes? —A ver, si no tengo otra cosa, sí».

Prueba: casi siempre puedes sustituirlo por «veamos»: «Veamos si llueve de una vez» ✓.

**«Haber»** es el infinitivo del verbo auxiliar (he, has, ha, hemos) y del impersonal «hay». Aparece en tres sitios:
- Como auxiliar de infinitivo compuesto: «Tenías que haber avisado», «Debió de haber llovido».
- Como impersonal en infinitivo: «Va a haber problemas», «Tiene que haber otra salida».
- Como sustantivo, raro: «el haber de la cuenta», «sus haberes».

Prueba: si delante tienes «tener que», «deber», «poder», «ir a» o «parece», es «haber». Si lo que sigue es «si» o una coma, es «a ver».

Tus frases corregidas:
- «**A ver** si llueve» (deseo: veamos si llueve).
- «**A ver** si me explicas» (petición).
- Y una donde sí va «haber»: «Tiene que **haber** otra explicación». No podrías decir «tiene que veamos otra explicación».

El error en sentido contrario también existe: «Tenía que a ver venido» por «Tenía que haber venido». Si ves «que a ver», es error seguro, porque «a ver» nunca va detrás de «tener que».

Dos tildes más en tu mensaje: «cuándo» (interrogativo indirecto: «cuándo se escribe») y «está» («está mal»). «Porque» está bien: es causal. Así quedaría: «A ver si me explicas cuándo se escribe "haber" y cuándo "a ver", porque yo escribo "a ver si llueve" y mi hermana dice que está mal».""",
            },
        ]
    },
    # 4) hay / ahí / ay (principiante).
    {
        "messages": [
            {"role": "user", "content": "hay, ahí y ay… cual es cual? siempre me lo marcan en rojo"},
            {
                "role": "assistant",
                "content": """Tres palabras, tres funciones. La frase para recordarlas: «**Ahí hay** un hombre que dice **ay**».

**Hay** es el verbo haber (existir). Prueba: puedes cambiarlo por «existe», «existen» o por «había» en pasado.
- Hay tres errores en el informe. → Existen tres errores ✓
- ¿Hay café? → ¿Existe café? ✓ (suena raro, pero la sustitución funciona)

**Ahí** indica lugar. Lleva tilde porque la «i» se pronuncia separada de la «a» (a-HÍ), y es una palabra aguda terminada en vocal. Prueba: cámbialo por «en ese sitio» o «allí».
- Deja las llaves ahí. → Deja las llaves en ese sitio ✓
- Ahí está el problema. → Allí está el problema ✓

**Ay** es una exclamación de dolor, susto o pena. Siempre va entre signos de exclamación o seguida de coma.
- ¡Ay, me he cortado!
- Ay, qué pena.

Para no fallar nunca, hazte una pregunta al escribir:
1. ¿Es algo que existe? → **hay**.
2. ¿Es un sitio? → **ahí**.
3. ¿Es un quejido? → **ay**.

Y dos trampas que te van a aparecer:
- «Hay» nunca cambia de número: «hay un error» y «hay tres errores». «Hayn» no existe.
- «Ahí» no es «ahy» ni «ai». La tilde va en la «i» y es obligatoria.

Tu frase sin rojos: «Ahí hay tres palabras y, ay, siempre me las marcan en rojo».""",
            },
        ]
    },
    # 5) Leísmo, laísmo, loísmo (usuaria de Madrid).
    {
        "messages": [
            {"role": "system", "content": "Eres un corrector de estilo. Marca cada error, explica la regla en una frase y da la versión corregida."},
            {"role": "user", "content": "¿Está bien decir «la dije que viniera»? Soy de Madrid y lo digo así toda la vida, pero en el trabajo me lo corrigieron."},
            {
                "role": "assistant",
                "content": """No está bien: es laísmo. Lo correcto es «**le** dije que viniera». La regla en una frase: «lo/la» sustituyen al complemento directo y «le» al indirecto, sin importar el género.

El truco para decidir: pregunta al verbo **qué** y **a quién**.

- ¿Qué dije? → «que viniera». Eso es el complemento directo.
- ¿A quién se lo dije? → a ella. Eso es el indirecto → **le**.

Como «decir» ya tiene un directo (lo que se dice), la persona solo puede ser indirecto, y el indirecto es «le» para él y para ella. Lo mismo con «la pregunté», «la pedí», «la regalé», «la conté»: todos son «le».

| Pronombre | Función | Ejemplo correcto |
|---|---|---|
| lo / los | directo masculino | A Juan lo vi ayer. |
| la / las | directo femenino | A Ana la vi ayer. |
| le / les | indirecto (ambos géneros) | A Ana le dije la verdad. |

Los tres desvíos y su estatus normativo:

1. **Laísmo** («la dije», «la gusta»): usar «la» como indirecto. No se acepta en ningún registro. Es típico de Madrid y Castilla, y por eso te lo corrigen fuera de ese entorno.
2. **Loísmo** («lo di un golpe»): usar «lo» como indirecto. Tampoco se acepta nunca.
3. **Leísmo** («a Juan le vi»): usar «le» como directo. La RAE **admite** solo un caso: persona, masculino, singular («le vi» = a Juan). No admite «les vi» (plural), «le compré» por un objeto («el libro, le leí») ni «le vi» por una mujer.

Verbos que confunden porque cambian de régimen:
- «pegar», «gustar», «doler», «interesar», «preocupar»: siempre indirecto → «le pegó», «le gusta», «le duele».
- «ayudar», «obedecer», «llamar», «aplaudir»: en América se usan como directos («la ayudé», «lo obedeció»); en España alternan con «le», y ambos se aceptan.

Prueba de verificación: convierte la frase a pasiva. Solo el complemento directo puede ser sujeto de una pasiva. «La dije que viniera» → «Ella fue dicha» ✗ (imposible). «La vi en la oficina» → «Ella fue vista en la oficina» ✓. Si la pasiva no funciona, el pronombre tiene que ser «le».""",
            },
        ]
    },
    # 6) Subjuntivo vs indicativo (multiturno).
    {
        "messages": [
            {"role": "user", "content": "¿Cuál es correcto: «No creo que es buena idea» o «No creo que sea buena idea»? Y por qué, porque «Creo que es» sí me suena bien."},
            {
                "role": "assistant",
                "content": """«No creo que **sea** buena idea». La negación cambia el modo.

El principio general: el indicativo presenta lo que sigue como un hecho que afirmas; el subjuntivo presenta algo que no afirmas (lo deseas, lo dudas, lo niegas, lo valoras o todavía no ha ocurrido).

- «Creo que **es** buena idea» → afirmas que lo es, con algo de cautela. Indicativo.
- «No creo que **sea** buena idea» → no afirmas que lo sea; estás negando esa creencia. Subjuntivo.

El mismo cambio ocurre con todos los verbos de opinión y percepción cuando se niegan: «Pienso que viene / No pienso que venga», «Me parece que funciona / No me parece que funcione», «Está claro que falla / No está claro que falle».

Otros disparadores de subjuntivo que verás a diario:

| Disparador | Ejemplo |
|---|---|
| Deseo, petición, orden | Quiero que **vengas**. Pide que lo **revisen**. |
| Duda, posibilidad | Dudo que **llegue**. Es posible que **falle**. |
| Valoración | Es importante que **esté** documentado. Me alegra que **funcione**. |
| Finalidad | Lo escribo para que **quede** claro. |
| Futuro no realizado tras «cuando», «en cuanto», «hasta que» | Avísame cuando **termines**. |

Un matiz que te va a aparecer: la **pregunta negativa** que busca acuerdo lleva indicativo, porque en realidad afirmas: «¿No crees que **es** buena idea?» = «yo creo que lo es, ¿tú no?». Aquí el subjuntivo («¿no crees que sea?») sonaría a duda genuina.

Verificación: cambia el verbo principal por uno de certeza absoluta. «Sé que es buena idea» ✓ (hecho). «No sé si es buena idea» ✓ (no se niega el hecho, se niega el saber; va indicativo). «No creo que sea buena idea» ✓ (se niega la creencia, y lo creído deja de afirmarse). Si al negar la creencia el contenido deja de ser un hecho para ti, va subjuntivo.""",
            },
            {"role": "user", "content": "¿Y con «aunque»? He visto «aunque llueve» y «aunque llueva» y las dos me parecen bien."},
            {
                "role": "assistant",
                "content": """Las dos son correctas, pero no dicen lo mismo. «Aunque» admite ambos modos y el modo cambia el significado.

- «Aunque **llueve**, salgo» (indicativo): está lloviendo ahora, es un hecho, y salgo a pesar de eso. Informas al oyente de la lluvia.
- «Aunque **llueva**, salgo» (subjuntivo): no afirmo que llueva. Puede ser hipotético («si llegara a llover») o puede ser que ya llueve, pero lo presento como algo sabido por ambos y sin relevancia («sí, ya sé que llueve, da igual»).

La distinción se llama concesiva factual (indicativo) frente a concesiva no factual o de hecho no relevante (subjuntivo). En la práctica:

| Frase | Lectura |
|---|---|
| Aunque **es** caro, lo compro. | Es caro (dato nuevo) y aun así lo compro. |
| Aunque **sea** caro, lo compro. | Sea caro o no, lo compro. / Ya sabemos que es caro; no importa. |
| Aunque **tenía** razón, no lo escucharon. | Tenía razón, hecho. |
| Aunque **tuviera** razón, no lo escucharían. | Hipótesis: si llegara a tenerla. |

El mismo juego funciona con «cuando», y ahí sí hay una forma incorrecta:

- «Cuando **llega**, comemos» → hábito: cada vez que llega.
- «Cuando **llegue**, comemos» → un hecho futuro concreto.
- «Cuando llegará, comemos» ✗ → el futuro de indicativo nunca va tras «cuando», «en cuanto», «hasta que», «mientras», «apenas» ni «tan pronto como». Es uno de los errores más frecuentes en hablantes de inglés y en traducciones automáticas («when he will arrive»).

Y con «quizá», «tal vez», «posiblemente», «probablemente» también alternan: «Quizá **viene**» (lo ves bastante probable) frente a «Quizá **venga**» (más dudoso). Con «a lo mejor» solo indicativo: «A lo mejor viene».

Verificación con tu par: si quien lo dice está mirando la lluvia por la ventana y quiere que el otro lo sepa, «aunque llueve». Si está decidiendo qué hacer mañana, «aunque llueva».""",
            },
        ]
    },
    # 7) Concordancia en un informe.
    {
        "messages": [
            {"role": "user", "content": """En un informe tengo estas frases y no sé si están bien o si el verbo tendría que ir en plural:

1. La mayoría de los usuarios prefiere la versión móvil.
2. Se venden entradas en taquilla.
3. Se busca a los responsables del incidente.
4. Hubieron varios incidentes durante la migración.
5. El 40 % de los encuestados dijeron que no usan la app.
6. Este es uno de los módulos que más falla.

¿Cuáles corrijo?"""},
            {
                "role": "assistant",
                "content": """Dos están mal (4 y 6), dos admiten las dos formas (1 y 5) y dos están bien tal cual (2 y 3). Una por una, con el motivo:

**1. «La mayoría de los usuarios prefiere / prefieren».** Las dos son correctas. El sujeto gramatical es «la mayoría» (singular), pero con «la mayoría de + plural» la concordancia con el sentido (plural) es igual de válida y hoy más frecuente. Lo mismo con «la mitad de», «un grupo de», «el resto de». Elige una y sé coherente en todo el informe.

**2. «Se venden entradas».** Correcto. Es una pasiva refleja: «entradas» es el sujeto y el verbo concuerda con él. «Se vende entradas» es un error frecuente en rótulos, pero error.

**3. «Se busca a los responsables».** Correcto. Cuando el complemento lleva la preposición «a» (personas), la construcción es impersonal y el verbo va **siempre en singular**: «se busca a los responsables», «se premió a los ganadores», «se convocó a los delegados». Ponerlo en plural («se buscan a los responsables») es el error habitual aquí.

**4. «Hubieron varios incidentes» ✗ → «Hubo varios incidentes».** El verbo «haber» en sentido de existir es impersonal: no tiene sujeto, y «varios incidentes» es su complemento directo. Por eso no concuerda nunca: «hubo», «había», «ha habido», «habrá». Prueba: sustituye el complemento por un pronombre: «los hubo», no «los hubieron».

**5. «El 40 % de los encuestados dijo / dijeron».** Las dos son válidas, como en la 1. Cuando lo que sigue habla claramente de personas («dijeron que no usan la app»), el plural suena más natural y es el que recomendaría.

**6. «Uno de los módulos que más falla» ✗ → «uno de los módulos que más fallan».** El relativo «que» se refiere a «los módulos», no a «uno»: son los módulos los que fallan, y este es uno de ellos. El singular está muy extendido, pero es una concordancia equivocada. Mismo caso: «Es una de las personas que más saben de esto», «uno de los que más trabajan».

Regla única para revisar el resto del informe: localiza el sustantivo con el que el verbo concuerda de verdad. Con «se» + «a» + persona, no hay sujeto → singular. Con «haber» existencial, no hay sujeto → singular. Con «uno de los que», el sujeto del relativo es el plural.

Verificación del 6 por un segundo camino: invierte la frase. «De los módulos que más fallan, este es uno». Ahí ya nadie escribiría «falla».""",
            },
        ]
    },
    # 8) Gerundio mal usado.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Mi jefe me devolvió un documento con tres gerundios marcados y no entiendo qué tienen de malo: «Se aprobó la ley regulando el teletrabajo», «El servidor se reinició, perdiendo todas las sesiones» y «Entregamos una caja conteniendo los repuestos»."},
            {
                "role": "assistant",
                "content": """Los tres son usos no normativos del gerundio, y cada uno es de un tipo distinto. El gerundio español solo expresa **modo** o **simultaneidad** respecto al verbo principal («lo arregló reiniciando el servicio», «salió corriendo»). Cuando hace otra cosa, chirría.

**1. «La ley regulando el teletrabajo» → gerundio especificativo.** El gerundio está funcionando como adjetivo de un sustantivo («la ley que regula»). En español el gerundio no modifica sustantivos; eso lo hace la oración de relativo o un adjetivo.
Corrección: «Se aprobó la ley **que regula** el teletrabajo».

**2. «Se reinició, perdiendo todas las sesiones» → gerundio de posterioridad o de consecuencia.** Las sesiones se pierden *después* del reinicio y *como resultado* de él. El gerundio exige simultaneidad; aquí hay una secuencia causa-efecto.
Corrección: «El servidor se reinició **y se perdieron** todas las sesiones» o «se reinició, **con lo que se perdieron** todas las sesiones».

**3. «Una caja conteniendo los repuestos» → el mismo caso que el 1.** Es el gerundio favorito de albaranes y boletines oficiales («decreto estableciendo», «paquete conteniendo»). Sigue siendo un adjetivo disfrazado.
Corrección: «una caja **con** los repuestos» o «una caja **que contiene** los repuestos».

Solo hay dos gerundios lexicalizados que sí pueden acompañar a un sustantivo: «agua **hirviendo**» y «clavo **ardiendo**». No son licencia para los demás.

Los usos correctos, para que no acabes borrándolos todos:

| Uso | Ejemplo |
|---|---|
| Modo (¿cómo?) | Resolvimos el bloqueo **reiniciando** el pool. |
| Simultaneidad | Revisé los logs **esperando** el despliegue. |
| Con verbos de percepción | Vi al proceso **consumiendo** toda la memoria. |
| Perífrasis | Seguimos **investigando**. Lleva **fallando** desde ayer. |

Prueba para decidir en un segundo: pregunta «¿cómo?» o «¿mientras qué?» al verbo principal. Si el gerundio responde, está bien. Si responde a «¿qué pasó después?» o a «¿cuál?», cámbialo.

Verificación con los tres: «¿Cómo se aprobó la ley? Regulando» ✗ (no es el modo de aprobar). «¿Cómo se reinició? Perdiendo» ✗ (es el resultado). «¿Cómo entregamos? Conteniendo» ✗ (describe la caja). Los tres fallan la prueba.""",
            },
        ]
    },
]

# --- Bloque 2 ---
ROWS += [
    # 9) Queísmo y dequeísmo con prueba.
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de textos técnicos en español. Señala el error, la regla y la corrección, sin rodeos."},
            {"role": "user", "content": "Entre estas, ¿cuáles tienen dequeísmo o queísmo? «Pienso de que deberíamos migrar», «Me alegro que hayas venido», «Estoy seguro que funciona», «Me di cuenta que faltaba un índice», «Es posible de que falle», «Informó de que el servicio cayó», «¿Te acuerdas que te lo dije?». Dame una prueba para no depender de que me suene."},
            {
                "role": "assistant",
                "content": """Dos dequeísmos, cuatro queísmos y una correcta. La prueba: convierte la frase en pregunta. La preposición que aparece (o no) en la pregunta es la que lleva la frase.

| Frase | Pregunta de control | Diagnóstico | Corrección |
|---|---|---|---|
| Pienso de que deberíamos migrar | ¿**Qué** piensas? | dequeísmo | Pienso **que** deberíamos migrar |
| Me alegro que hayas venido | ¿**De qué** te alegras? | queísmo | Me alegro **de que** hayas venido |
| Estoy seguro que funciona | ¿**De qué** estás seguro? | queísmo | Estoy seguro **de que** funciona |
| Me di cuenta que faltaba un índice | ¿**De qué** te diste cuenta? | queísmo | Me di cuenta **de que** faltaba un índice |
| Es posible de que falle | ¿**Qué** es posible? | dequeísmo | Es posible **que** falle |
| Informó de que el servicio cayó | ¿**De qué** informó? | correcta | También «informó que», habitual en América |
| ¿Te acuerdas que te lo dije? | ¿**De qué** te acuerdas? | queísmo | ¿Te acuerdas **de que** te lo dije? |

Por qué funciona: la preposición no depende de «que», depende del verbo o del adjetivo anterior («acordarse **de**», «seguro **de**», «alegrarse **de**», «darse cuenta **de**»). Al preguntar, el verbo exige su preposición y la ves.

Segunda prueba, por si la primera no te convence: sustituye toda la subordinada por «eso». «Pienso eso» ✓ (sin «de»). «Me acuerdo de eso» ✓ (con «de»). «Es posible eso» ✓. «Estoy seguro de eso» ✓.

Patrones que generan dequeísmo (nunca llevan «de»):
- Verbos de pensamiento y habla con complemento directo: pensar, creer, opinar, decir, suponer, considerar.
- «Ser» + adjetivo: es posible que, es necesario que, es evidente que.
- Verbos con sujeto oracional: «me preocupa que», «me consta que», «conviene que».

Patrones que generan queísmo (siempre llevan «de»):
- Verbos pronominales con régimen: acordarse de, alegrarse de, olvidarse de, darse cuenta de, enterarse de.
- Adjetivos con régimen: seguro de, consciente de, convencido de, capaz de.
- Sustantivos con régimen: «la idea de que», «el hecho de que», «la posibilidad de que».

Dos casos que la gente corrige de más:
- «Antes que» y «antes de que» son ambas válidas; lo mismo «después que» y «después de que».
- Hay verbos que cambian de significado con la preposición: «advertir que» (= notar) frente a «advertir de que» (= avisar); «dudar que» y «dudar de que» son ambas válidas.

Verificación de la regla en tu caso más dudoso, «informó de que»: en España se prefiere «informar de algo» y en América «informar algo». Las dos están aceptadas. Lo que no es válido es mezclar: «informó de que» en un párrafo e «informó que» en el siguiente.""",
            },
        ]
    },
    # 10) Mayúsculas (usuario mexicano).
    {
        "messages": [
            {"role": "user", "content": "Oye, en la empresa escribimos todo con mayúscula: «el Director General», «los Lunes», «el Idioma Inglés», «Marketing», «el Gobierno Federal», «la Ciudad de México», «el Área de Sistemas». ¿Qué va con mayúscula de verdad y qué no?"},
            {
                "role": "assistant",
                "content": """De tu lista, solo dos llevan mayúscula con seguridad: «Gobierno» (como institución) y «Ciudad de México» (nombre propio oficial). Las demás son mayúsculas de respeto, y la ortografía no las admite.

La regla de fondo: la mayúscula marca **nombres propios** (una entidad concreta y única), no importancia ni jerarquía.

| Tu ejemplo | Correcto | Por qué |
|---|---|---|
| el Director General | el director general | Los cargos van en minúscula, por altos que sean: el presidente, la ministra, el papa, la gerente. |
| los Lunes | los lunes | Días, meses y estaciones: minúscula. |
| el Idioma Inglés | el idioma inglés | Idiomas y gentilicios: minúscula (inglés, mexicano, maya). |
| Marketing | marketing | Disciplinas y áreas de conocimiento: minúscula. Mayúscula solo como nombre de asignatura: «reprobé Cálculo». |
| el Gobierno Federal | el Gobierno federal | «Gobierno» con mayúscula cuando es la institución; el adjetivo que lo acompaña, en minúscula. |
| la Ciudad de México | la Ciudad de México | Nombre propio oficial. Pero «la ciudad de Puebla» en minúscula, porque «ciudad» no forma parte del nombre. |
| el Área de Sistemas | el Área de Sistemas / el área de Sistemas | Si es el nombre oficial de la unidad en el organigrama, mayúscula en todo; si es una descripción genérica, solo «Sistemas». Elige un criterio y mantenlo. |

Otras que vas a necesitar en documentos de empresa:

- **Instituciones y organismos**: mayúscula en todas las palabras significativas: la Secretaría de Hacienda, el Instituto Mexicano del Seguro Social, el Consejo de Administración. El genérico va en minúscula cuando no es el nombre: «cualquier consejo de administración».
- **Después de dos puntos**: minúscula, salvo tras el saludo de una carta («Estimada licenciada Ruiz: Le escribo») o cuando sigue una cita textual.
- **Títulos de documentos y obras**: solo la primera palabra y los nombres propios: *Manual de procedimientos de compras*, *Cien años de soledad*.
- **Siglas**: todo en mayúscula y sin puntos (IMSS, SAT, CDMX). Los acrónimos que se leen como palabra y pasan de cuatro letras pueden ir solo con inicial: Pemex, Conacyt.
- **Puntos cardinales**: minúscula («el norte del país»), salvo dentro de un nombre propio («Baja California Sur», «Corea del Norte»).
- **Estado**: mayúscula cuando es el país como entidad política («el Estado mexicano»); minúscula como entidad federativa genérica («los estados del sur») o como estado de ánimo.
- **Internet**: se admite con mayúscula o minúscula; la RAE recomienda hoy la minúscula.

Prueba para dudar menos: ponle un artículo indeterminado y mira si sigues hablando de lo mismo. «Un lunes», «un director general», «un idioma» → nombre común → minúscula. «Un Gobierno federal», «una Ciudad de México» → ya no es la misma entidad → nombre propio → mayúscula.

Verificación con todos juntos: «El director general del Área de Sistemas se reúne los lunes con el Gobierno federal en la Ciudad de México para hablar de marketing en inglés».""",
            },
        ]
    },
    # 11) Coma entre sujeto y verbo; puntuación de un aviso (multiturno).
    {
        "messages": [
            {"role": "user", "content": "¿Me revisas la puntuación de este párrafo? «Los usuarios que no completaron el registro, no podrán acceder al sistema. Sin embargo los que lo hicieron antes del lunes, mantendrán su cuenta, pero, deberán cambiar la contraseña. Gracias por su comprensión Equipo de soporte.»"},
            {
                "role": "assistant",
                "content": """Versión corregida:

«Los usuarios que no completaron el registro no podrán acceder al sistema. Sin embargo, los que lo hicieron antes del lunes mantendrán su cuenta, pero deberán cambiar la contraseña. Gracias por su comprensión.
Equipo de soporte»

Cinco cambios, cada uno con su regla:

1. **«Los usuarios que no completaron el registro, no podrán» → sin coma.** Nunca va coma entre el sujeto y el verbo, por largo que sea el sujeto. La oración de relativo «que no completaron el registro» forma parte del sujeto. Es el error más frecuente del párrafo y el más grave.
2. **«Sin embargo los que» → «Sin embargo, los que».** Los conectores al inicio de oración («sin embargo», «no obstante», «por tanto», «además», «en cambio») se aíslan con coma.
3. **«antes del lunes, mantendrán» → sin coma.** Mismo caso que el 1: «los que lo hicieron antes del lunes» es el sujeto de «mantendrán».
4. **«pero, deberán» → «pero deberán».** La coma va *antes* de «pero», nunca después. Solo llevaría coma detrás si hubiera un inciso: «pero, como ya saben, deberán».
5. **«comprensión Equipo de soporte» → punto y aparte.** La firma es un elemento independiente; no se pega a la frase anterior. Si fuera un vocativo dentro de la oración, iría con coma: «Gracias por su comprensión, Ana».

La regla que resuelve el 1 y el 3, y que vale para todo lo que escribas: la coma no marca una pausa para respirar. Marca **incisos** (dos comas), **enumeraciones**, **conectores**, **vocativos** y **elementos desplazados** («Antes del lunes, los usuarios podrán»). Si lo que separas es sujeto de verbo o verbo de complemento directo, la coma sobra.

La única forma de que haya comas entre un sujeto y su verbo es que haya un inciso, y entonces son dos: «Los usuarios, como ya avisamos, no podrán acceder».

Verificación: lee la versión corregida en voz alta haciendo pausa solo en las comas. Las pausas caen donde el sentido lo pide y ninguna parte un sujeto por la mitad.""",
            },
            {"role": "user", "content": "¿Y por qué no puedo poner coma después de «Los usuarios que no completaron el registro»? Es muy largo y se me hace raro leerlo todo seguido."},
            {
                "role": "assistant",
                "content": """Porque la coma no es un signo de respiración: es un signo sintáctico. Marca límites entre bloques de la oración, y sujeto y verbo son el **mismo** bloque, por largo que sea el sujeto. Un lector entrenado interpreta esa coma como el cierre de un inciso que nunca se abrió, y tropieza.

Lo que notas es real: un sujeto de ocho palabras pesa. Pero la solución no es puntuarlo mal, es **acortarlo o reorganizarlo**. Tres opciones, de menor a mayor cambio:

1. **Mover el complemento al principio**, que sí admite coma porque es un elemento desplazado:
   «Sin el registro completo, los usuarios no podrán acceder al sistema».

2. **Partir en dos oraciones**:
   «Algunos usuarios no completaron el registro. Esos usuarios no podrán acceder al sistema».

3. **Convertir el sujeto en condición**:
   «Si no completó el registro, no podrá acceder al sistema».

La tercera, además de más corta, es más directa: habla al lector en segunda persona, que es lo que un aviso de soporte necesita.

La prueba definitiva para no dudar: quita la oración de relativo y mira si la coma sigue teniendo sentido. «Los usuarios, no podrán acceder» → evidentemente no. Añadir «que no completaron el registro» al sujeto no cambia la estructura; solo la alarga.

Verificación de que la regla no tiene excepciones: busca en cualquier texto bien editado un sujeto larguísimo. «La decisión del comité de evaluación de propuestas técnicas sobre el expediente del año pasado fue unánime». Diecisiete palabras de sujeto y ninguna coma antes de «fue».""",
            },
        ]
    },
    # 12) Punto y coma.
    {
        "messages": [
            {"role": "user", "content": "Nadie en mi equipo usa el punto y coma, y cuando yo lo uso me lo cambian por punto o por coma. ¿Tiene algún uso que de verdad no pueda cubrir otro signo?"},
            {
                "role": "assistant",
                "content": """Sí: uno es insustituible y dos son cuestión de precisión. En orden de fuerza:

**1. Enumeraciones cuyos elementos ya llevan comas (insustituible).** Sin punto y coma, el lector no sabe dónde acaba cada elemento.

- Con coma: «Asistieron Ana, directora, Luis, contable, y Marta, abogada». ¿Cuántas personas? ¿Tres? ¿Cinco?
- Con punto y coma: «Asistieron Ana, directora; Luis, contable; y Marta, abogada». Tres, sin ambigüedad.

Lo mismo en listas de requisitos técnicos: «El servicio necesita Python 3.12, con pip; PostgreSQL 16, con la extensión pgvector; y Redis 7».

**2. Oraciones yuxtapuestas con relación estrecha.** El punto las separa del todo; la coma las une demasiado (y entre oraciones independientes es incorrecta). El punto y coma dice «son dos ideas, pero van juntas».

- «El despliegue falló; nadie revisó los logs». La segunda explica o contrasta con la primera.
- Con punto es correcto pero más frío: «El despliegue falló. Nadie revisó los logs».
- Con coma es incorrecto: «El despliegue falló, nadie revisó los logs».

**3. Antes de conectores en oraciones largas.** Cuando lo que precede a «sin embargo», «por tanto», «no obstante», «es decir» ya tiene comas, el punto y coma marca mejor el corte: «Revisamos la configuración, los permisos y la red; sin embargo, el error persistió». Si la oración es corta, basta la coma: «Lo revisamos, pero persistió».

Por qué tu equipo lo cambia: el punto y coma exige una decisión de matiz y la mayoría prefiere no tomarla. En textos técnicos cortos, sustituirlo por punto es casi siempre aceptable y casi nunca mejor. Lo que no es aceptable es que te lo cambien por coma en los casos 1 y 2: ahí introducen un error.

Regla práctica para defender tu uso: «Lo pongo donde pondría un punto, pero la segunda oración necesita la primera para entenderse». Si pueden leer la segunda sin la primera y no pierden nada, cede y pon punto.

Verificación por el caso 1, que puedes enseñar en diez segundos: pídeles que cuenten las personas en «Vinieron Pedro, el jefe, Ana, la nueva, y Juan». Cuando no se pongan de acuerdo, se acabó la discusión.""",
            },
        ]
    },
    # 13) Raya, guion, semirraya y comillas.
    {
        "messages": [
            {"role": "user", "content": "Para la guía de estilo de la documentación: ¿raya, guion o ese guion medio que sale a veces en el teclado? ¿Y comillas «» o las inglesas? Los de diseño dicen que da igual."},
            {
                "role": "assistant",
                "content": """No da igual: son tres signos distintos con funciones distintas, y cualquiera que edite texto los distingue a simple vista.

**Raya (—, U+2014).** El signo largo. Usos:
- Incisos, como un paréntesis más suave: «El servicio —el de pagos, no el de usuarios— se reinicia a diario». Siempre en pareja; la de cierre solo se omite si el inciso termina en punto.
- Diálogos en narrativa.
- Elementos de una lista en textos sin viñetas.
No lleva espacio entre la raya y la palabra del inciso; sí lo lleva por fuera.

**Guion (-, el de la tecla).** El signo corto. Usos:
- Palabras compuestas: «teórico-práctico», «franco-alemán», «relación coste-beneficio».
- Prefijos ante mayúscula, sigla o cifra: «anti-OTAN», «sub-21», «pro-Ucrania». Ante palabra normal, el prefijo va pegado: «antivirus», «exdirector», «preproducción».
- Rangos: «2019-2024», «páginas 10-25».
- División de palabra a final de línea.

**Semirraya o guion medio (–, U+2013).** En la ortografía española **no tiene función propia**. Viene de la tipografía inglesa (el *en dash*), donde marca rangos e incisos. En español los rangos van con guion y los incisos con raya. Si aparece en vuestros textos es porque el procesador lo autocorrigió o porque se copió de una fuente en inglés.

**Comillas.** La Ortografía recomienda esta jerarquía: «españolas» en primer nivel, "inglesas" dentro de ellas y 'simples' en un tercer nivel. En documentación técnica es habitual usar las inglesas en primer nivel porque son las del teclado y las que entienden los editores de código, y es una decisión defendible. Lo que no es defendible es alternar sin criterio.

Dos reglas de comillas que casi nadie respeta:
- El punto va **fuera** de las comillas de cierre: «El log decía "connection refused"». No «"connection refused."».
- Dentro de bloques de código no se tocan: las comillas de un literal `"hola"` son código, no texto.

Propuesta concreta para la guía, pensando en Markdown:

| Signo | Cuándo | Cómo escribirlo |
|---|---|---|
| — raya | incisos | Linux: Compose + tres guiones; macOS: Opt + Mayús + guion; Windows: Alt + 0151 |
| - guion | compuestos, rangos, prefijos ante sigla | tecla del teclado |
| – semirraya | nunca en prosa | desactivar la autocorrección del editor |
| « » | citas y términos en prosa | AltGr + Z / X en teclado español; Compose + < < en Linux |
| " " | dentro de « » y en código | tecla del teclado |

Verificación de que importa: en «El flag `--dry-run` —que no escribe nada— acepta rangos 1-5» aparecen tres signos cortos distintos y cada uno significa algo diferente. Si los unificáis, `--dry-run` deja de ser copiable y el inciso deja de verse.""",
            },
        ]
    },
    # 14) Voseo para un bot argentino.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {"role": "user", "content": "Estoy armando un bot de atención al cliente para Argentina y quiero que hable de vos. Pasame las reglas de conjugación, que los de contenido me mandaron textos con «vos tienes» y «vos puedes»."},
            {
                "role": "assistant",
                "content": """«Vos tienes» no existe en ninguna variedad: el pronombre es voseante y el verbo, tuteante. Si el bot vosea, el verbo tiene que acompañar. Las reglas son pocas y regulares.

**Presente de indicativo.** Sacás la «-r» del infinitivo y acentuás la última sílaba:
- -ar → -ás: hablar → hablás, pensar → pensás, estar → estás.
- -er → -és: tener → tenés, poder → podés, querer → querés.
- -ir → -ís: venir → venís, decir → decís, salir → salís.

La ventaja frente al tuteo: **no hay diptongación**. «Vos podés» (no «puedes»), «vos pensás» (no «piensas»), «vos dormís» (no «duermes»). Las únicas irregulares son «sos» (ser), «vas» (ir) y «has» (haber, que casi no se usa).

**Imperativo afirmativo.** Infinitivo sin «-r», con tilde en la última vocal:
- andá, mirá, entrá, ingresá, hacé, poné, tené, vení, decí, salí, elegí.
- Con pronombre pegado, la tilde se conserva si la palabra sigue siendo aguda: «decime», «contame», «escribinos». Si pasa a ser grave terminada en vocal, se pierde: «fijate», «andate».
- Para «ir» se usa «andá» o «andate»; para «ser», «sé».

**Imperativo negativo.** En registro cuidado, igual que el tuteo: «no hagas», «no vengas», «no te olvides». Las formas «no hagás», «no vengás» se oyen, pero son más informales y en un bot de atención suenan descuidadas.

**Subjuntivo presente.** En el estándar rioplatense escrito, idéntico al tuteo: «que tengas», «que puedas», «cuando quieras». Evitá «tengás» y «podás» en el bot.

**Todos los demás tiempos** son iguales a los de «tú»: «tenías», «tuviste», «tendrás», «tendrías», «hayas tenido».

**Pronombres.** «Vos» como sujeto y tras preposición: «con vos», «para vos», «de vos». El clítico sigue siendo «te» («te llamo», «te lo mando») y el posesivo, «tu/tuyo». El plural es «ustedes» para todo el mundo; «vosotros» no existe en Argentina.

Los textos de tu equipo, corregidos:
- «Vos tienes una orden pendiente» → «**Tenés** una orden pendiente». El pronombre explícito sobra casi siempre.
- «Vos puedes consultar el estado» → «**Podés** consultar el estado».

Frases tipo para el bot: «¿Querés que te ayude con tu pedido?», «Ingresá tu número de seguimiento», «Si no lo encontrás, escribinos por acá», «Elegí una opción».

Verificación: leé cada frase en voz alta. Si el acento cae en la última sílaba del verbo («tenÉS», «ingresÁ»), está bien. Si cae antes («TIEnes»), se te coló un tuteo.""",
            },
        ]
    },
    # 15) Anglicismos innecesarios en documentación interna.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Me pidieron que limpie de anglicismos la documentación interna. Tengo frases como «aplicar al puesto», «remover el archivo», «soportar Windows», «customizar el dashboard», «eventualmente lo migramos», «asumimos que el usuario está logueado» y «la librería de gráficos». ¿Cuáles son errores de verdad y cuáles ya están aceptados?"},
            {
                "role": "assistant",
                "content": """Hay tres niveles: calcos que cambian el significado (errores), calcos que ya recoge el diccionario pero conviene evitar en texto formal, y términos técnicos que no tiene sentido traducir.

| Expresión | Problema | Alternativa | Estatus |
|---|---|---|---|
| aplicar al puesto | «aplicar» es «poner en práctica»; el sentido «solicitar» es calco de *apply* | postularse al puesto, solicitar el puesto | Error en texto formal; muy extendido en América |
| remover el archivo | «remover» en español es «mover, agitar»; el DLE admite también «quitar», pero en un texto técnico induce a confusión | eliminar, borrar, quitar | Aceptado por el DLE; evitable por claridad |
| soportar Windows | «soportar» es «aguantar»; *support* aquí es «ser compatible con» | es compatible con Windows, admite Windows, funciona en Windows | Calco; no aceptado en ese sentido |
| customizar el dashboard | «customizar» no existe; «dashboard» tiene equivalente directo | personalizar el panel | Error claro |
| eventualmente lo migramos | «eventualmente» en español es «ocasionalmente»; *eventually* es «al final, con el tiempo» | con el tiempo lo migraremos, acabaremos migrándolo | Falso amigo: cambia el significado |
| asumimos que está logueado | «asumir» es «aceptar una responsabilidad»; *assume* es «suponer». «Logueado» es jerga adaptada | suponemos que ha iniciado sesión, damos por hecho que tiene la sesión iniciada | «Asumir» por suponer: calco extendido, evitable. «Loguearse»: aceptado como coloquial, no para documentación |
| la librería de gráficos | *library* es «biblioteca»; «librería» es una tienda de libros | la biblioteca de gráficos | Error normativo, aunque es jerga universal entre programadores |

Criterio para los casos que no están en la lista:

1. **Si el anglicismo cambia el significado de una palabra española** (eventualmente, asumir, soportar, bizarro), es un error: el lector que no sepa inglés entenderá otra cosa.
2. **Si existe una palabra española de uso general con el mismo significado exacto** (personalizar, panel, biblioteca; ejecutar por «correr», configurar por «setear», desplegar por «deployar»), úsala.
3. **Si es un término técnico establecido sin equivalente claro** (commit, backend, pull request, cookie, bug, token), mantenlo en inglés, en cursiva la primera vez si la guía lo pide, y no lo conjugues a la española en texto formal («hacer un commit», no «commitear»).
4. **Adaptaciones ya aceptadas** que puedes usar sin problema: caché, escanear, formatear, chatear, clicar, estándar, sénior, resetear (coloquial).

Sobre «librería»: la batalla está perdida en la conversación entre programadores, y no pasa nada. En documentación que leerán personas de negocio o traductores, «biblioteca» evita el malentendido y es lo que usan la RAE, Microsoft y la traducción oficial de la documentación de Python.

Verificación: párrafo reescrito con el criterio aplicado. «Para postularse al puesto, el candidato debe eliminar el archivo temporal, comprobar que la herramienta es compatible con Windows, personalizar el panel y, con el tiempo, migrar la biblioteca de gráficos; suponemos que ya ha iniciado sesión». Ningún lector sin inglés pierde nada.""",
            },
        ]
    },
    # 16) Corrección de un correo con varios errores.
    {
        "messages": [
            {"role": "user", "content": "Corrígeme este correo antes de enviarlo, por favor: «Hola Sr. Gomez, le escribo por que aún no e recibido la factura del mes pasado, haber si me la puede enviar hoy. Habían varios errores en la anterior, por eso la reenvio. Si no la recibo mañana, tendre que contactar con contabilidad. Un saludo, Laura»"},
            {
                "role": "assistant",
                "content": """Versión corregida:

«Buenos días, señor Gómez:

Le escribo porque aún no he recibido la factura del mes pasado; a ver si me la puede enviar hoy. Había varios errores en la anterior, por eso la reenvío. Si no la recibo mañana, tendré que contactar con Contabilidad.

Un saludo,
Laura»

Los errores, en orden de aparición:

1. **«Hola Sr. Gomez,» → «Buenos días, señor Gómez:».** Tres cosas: «Gómez» lleva tilde (llana terminada en consonante distinta de «n» o «s»); el vocativo se separa con coma («Hola, señor»); y el saludo de una carta cierra con dos puntos, no con coma (la coma es calco del inglés). Además, «Hola» + «Sr.» mezcla registros: si tratas de usted, abre con «Buenos días» o «Estimado señor Gómez». La abreviatura «Sr.» es correcta, pero en el cuerpo de un correo queda mejor la palabra completa.
2. **«por que» → «porque».** Es causal: explica por qué escribes. Prueba: «ya que aún no he recibido» ✓.
3. **«e recibido» → «he recibido».** «E» sin hache es la conjunción («padres e hijos»); el auxiliar de los tiempos compuestos es «he», del verbo haber.
4. **«haber si» → «a ver si».** Es «veamos si me la puede enviar». «Haber» solo cabe tras «tener que», «deber», «poder», «ir a».
5. **«Habían varios errores» → «Había varios errores».** «Haber» existencial es impersonal y va siempre en singular: «había», «hubo», «ha habido».
6. **«reenvio» → «reenvío».** Verbo «reenviar», primera persona del presente: la «i» es tónica y forma hiato con la «o», así que lleva tilde.
7. **«tendre» → «tendré».** Aguda terminada en vocal.
8. **«contactar con contabilidad» → «contactar con Contabilidad».** Si te refieres al departamento como entidad, va con mayúscula. «Contactar con» es la forma habitual en España; en América es más común «contactar a». Ambas son válidas.

Un cambio de puntuación que no corrige un error pero mejora el ritmo: el punto y coma entre «mes pasado» y «a ver si», porque la segunda oración depende de la primera.

Verificación: cuenta las tildes de la versión final. «Días», «Gómez», «aún», «reenvío», «tendré». Cinco, y todas se justifican por regla general (hiato o posición del acento), salvo «aún», que es la diacrítica de «todavía».""",
            },
        ]
    },
]

# --- Bloque 3 ---
ROWS += [
    # 17) «solo», demostrativos y «guion»: norma de 2010 y matiz de 2023 (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Mi profesora de lengua insiste en que «sólo» lleva tilde cuando significa «solamente» y en que «éste» lleva tilde cuando es pronombre. En internet leo lo contrario. ¿Quién tiene razón?"},
            {
                "role": "assistant",
                "content": """Tu profesora enseña la norma de antes de 2010. La norma vigente es: «solo» y los demostrativos («este», «ese», «aquel» y sus variantes) **no llevan tilde**, y nunca es obligatorio ponérsela.

La historia en tres pasos, porque explica por qué conviven las dos versiones:

1. **Hasta 2010.** La tilde en «sólo» (adverbio) y en «éste» (pronombre) era opcional y se recomendaba solo en caso de ambigüedad. En la práctica, la mayoría la ponía siempre, y así se enseñaba en el colegio.
2. **Ortografía de 2010.** La RAE y la ASALE decidieron que no se tilden nunca, ni siquiera en caso de ambigüedad. El argumento: la tilde diacrítica se reserva para pares en los que una palabra es tónica y la otra átona («él/el», «tú/tu»), y «solo» es tónica en los dos usos. Para las ambigüedades recomendaron reformular.
3. **2023.** Ante la resistencia de muchos escritores, la RAE matizó la redacción: queda a juicio de quien escribe tildar «solo» y los demostrativos **cuando perciba riesgo de ambigüedad**. No es una vuelta a la norma antigua: sigue sin ser obligatorio, y tildarlos sistemáticamente sigue siendo incorrecto.

Lo que significa para ti:

- Escribir «solo» y «este» siempre sin tilde es correcto en cualquier contexto y nadie puede marcártelo como error.
- Escribir «sólo» siempre que signifique «solamente», como pide tu profesora, es una falta según la norma actual.
- Tildarlo únicamente en una frase ambigua es admisible desde 2023, pero reformular es mejor.

El ejemplo clásico de ambigüedad y cómo resolverla sin tilde:

- «Trabajo solo los domingos» → ¿«solamente los domingos» o «sin compañía los domingos»?
- Reformulado: «Trabajo solamente los domingos» / «Los domingos trabajo sin nadie más».

Con los demostrativos la ambigüedad real es casi inexistente: en «Esta mañana llegó», el contexto deshace cualquier duda.

Verificación de que el criterio es coherente: «solo» nunca aparece en la lista de tildes diacríticas de la Ortografía, mientras que «aún/aun» sí. En «aun/aún» hay cambio de pronunciación (átona/tónica); en «solo/solo», no. Esa es la razón técnica, y es la que puedes darle a tu profesora.""",
            },
            {"role": "user", "content": "Vale. ¿Y «guión»? Ella también lo escribe con tilde, y a mí me lo marca el corrector."},
            {
                "role": "assistant",
                "content": """El corrector tiene razón: desde 2010 se escribe «guion», sin tilde.

El motivo es el mismo cambio de criterio. La secuencia de vocal cerrada átona + vocal abierta («io», «ia», «ui», «iu») se considera **siempre diptongo a efectos ortográficos**, aunque en algunas zonas se pronuncie en dos sílabas («gui-ón»). Con ese criterio, «guion» es un monosílabo, y los monosílabos no llevan tilde salvo la diacrítica.

Antes de 2010 se admitían las dos grafías según la pronunciación de cada hablante; la Ortografía eliminó la doble opción.

El grupo completo de palabras que perdieron la tilde con esa regla, para que no te sorprendan:

| Antes | Ahora | Qué es |
|---|---|---|
| guión | guion | sustantivo |
| truhán | truhan | sustantivo |
| fié, lié, crié, guié | fie, lie, crie, guie | pretérito de fiar, liar, criar, guiar |
| rió, frió | rio, frio | pretérito de reír, freír |
| huí | hui | pretérito de huir |
| riáis, friáis | riais, friais | subjuntivo de reír, freír |
| Sión, Ruán | Sion, Ruan | nombres propios |

Ojo con «frio» y «rio»: sin tilde son el pretérito («ella frio un huevo», «él rio mucho»). No confundir con «frío» (adjetivo, con hiato real y tilde) ni con «río» (sustantivo, igual).

Regla que resume toda la conversación: la Ortografía de 2010 quitó las tildes que no distinguían pronunciaciones distintas. «Solo», «este» y «guion» se pronuncian igual con tilde o sin ella; por eso la perdieron. «Aún/aun» y «él/el» se pronuncian distinto; por eso la conservan.

Verificación: «El guion lo escribió ella sola; solo le faltó el final, y se rio cuando lo vio». Ninguna tilde que la norma actual no exija, y ninguna de las exigidas falta («rio» no lleva; «vio» tampoco).""",
            },
        ]
    },
    # 18) Haber impersonal: «habían», «habemos» (usuario colombiano).
    {
        "messages": [
            {"role": "user", "content": "En Colombia decimos «habemos muchos que pensamos así» y «habían muchas personas en la fila». ¿Es incorrecto o es una variante aceptada?"},
            {
                "role": "assistant",
                "content": """Las dos son incorrectas en la norma culta, en Colombia y en cualquier otro país, aunque las dos están muy extendidas en el habla.

**«Habían muchas personas» → «Había muchas personas».** El verbo «haber» con sentido de existir es impersonal: no tiene sujeto. «Muchas personas» no es el sujeto, sino el complemento directo, y el verbo no concuerda con el complemento. Por eso va siempre en tercera persona del singular: «había», «hubo», «habrá», «ha habido», «habría».

Prueba que lo demuestra: sustituye «muchas personas» por un pronombre. Sale «**las** había», con pronombre de complemento directo, no «ellas habían». Si fuera sujeto, no podrías sustituirlo por «las».

Mismo error en todas estas, con su corrección:
- «Han habido quejas» → «Ha habido quejas».
- «Hubieron problemas» → «Hubo problemas».
- «Pueden haber errores» → «Puede haber errores» (la perífrasis también se mantiene en singular).
- «Deben haber más de cien» → «Debe de haber más de cien».

El plural es frecuentísimo en el Caribe, Centroamérica, el Cono Sur y el este de España. La RAE lo registra como desvío extendido y lo desaconseja en todo registro escrito.

**«Habemos muchos que pensamos así».** Aquí el hablante quiere incluirse en el grupo, y como «hay» no tiene primera persona, inventa una. La forma «habemos» existió en español antiguo como presente de «haber» (hoy «hemos»), pero no como existencial. Es coloquial y no se admite en escritos formales.

Alternativas según lo que quieras decir:
- «**Somos** muchos los que pensamos así».
- «**Hay** muchos que pensamos así» (verbo impersonal, y el relativo en primera persona del plural para incluirte; es una construcción admitida).
- «Muchos, yo entre ellos, pensamos así».

Por qué la norma no cede aquí, aunque haya cedido en otras cosas: la impersonalidad de «haber» es una propiedad gramatical, no una convención ortográfica como la tilde de «solo». Hacerlo concordar lo convierte en otro verbo.

Verificación por un segundo camino: pásalo al presente. Nadie dice «hayn muchas personas» ni «hayamos muchos»; todo el mundo dice «hay». La forma de presente que todos usan bien es la misma que falla en pasado.""",
            },
        ]
    },
    # 19) ha / a / ah y hecho / echo (principiante).
    {
        "messages": [
            {"role": "user", "content": "nunca se si es 'a echo' o 'ha hecho', y 'echo de menos' o 'hecho de menos'. ayuda"},
            {
                "role": "assistant",
                "content": """«Ha hecho» y «echo de menos». Son dos confusiones distintas, con una regla cada una.

**«Ha» / «a» / «ah».**
- **Ha** es del verbo haber y siempre va delante de un participio (hecho, dicho, venido, comido). Prueba: cámbialo por «había». «Ha hecho» → «había hecho» ✓.
- **A** es una preposición: dirección, destinatario, hora o persona. «Voy a casa», «se lo di a Juan», «a las tres».
- **Ah** es una exclamación: «¡Ah, ya entiendo!».

**«Hecho» / «echo».**
- **Hecho**, con hache, es el participio de **hacer** y también un sustantivo («un hecho probado», «de hecho»). Si tiene que ver con hacer, lleva hache.
- **Echo**, sin hache, es del verbo **echar**: «echo la basura», «echo de menos», «echo a perder», «te echo una mano».

De ahí sale la regla de oro: **«echar» no lleva hache, y por eso «echo», «echas», «echamos» tampoco.** Es la forma de no olvidarlo.

Tus dos frases:
- «Ha hecho» (haber + participio de hacer): «Mi hermano ha hecho la cena». Nunca «a echo», que juntaría una preposición con el verbo echar y no significa nada.
- «Echo de menos» (yo echo, de echar): «Echo de menos a mis amigos». «Hecho de menos» no existe.

Otros pares con la misma trampa:
- «Deshecho» (de deshacer: «el nudo está deshecho») / «desecho» (residuo: «desechos tóxicos»; o del verbo desechar: «desecho la idea»).
- «Hecho a mano» ✓, «echo a mano» ✗.
- «Ha habido» ✓, «a habido» ✗.

Verificación con una frase que los junta todos: «¡Ah! Mi padre ha hecho lo que ha podido; ahora echo de menos aquella época y voy a casa a recordarla». Cada «ha» tiene un participio detrás; cada «a» tiene un lugar o destinatario; «hecho» viene de hacer; «echo» viene de echar.""",
            },
        ]
    },
    # 20) «le dije a mis padres» y «se los dije» (multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "¿Es correcto «le dije a mis padres que no venía»? Me suena bien, pero algo me dice que debería ser «les»."},
            {
                "role": "assistant",
                "content": """Debería ser «**les** dije a mis padres». El pronombre de complemento indirecto concuerda en número con el complemento al que duplica, y «mis padres» es plural.

Por qué te suena bien el singular: como el complemento aparece explícito después («a mis padres»), el hablante relaja la concordancia del pronombre, que percibe como redundante. Es una discordancia muy frecuente, incluso en escritores cuidadosos y en prensa, y la RAE la señala como error que conviene evitar en la lengua escrita.

Prueba que lo deja claro: quita el complemento explícito. «Les dije que no venía» (a ellos) frente a «Le dije que no venía» (a él o a ella). Nadie dudaría ahí. La presencia de «a mis padres» no cambia la gramática del pronombre; solo lo hace menos visible.

Más casos del mismo error, corregidos:
- «Le pedí a los proveedores un presupuesto» → «**Les** pedí a los proveedores».
- «Le escribí a ambos» → «**Les** escribí a ambos».
- «No le des importancia a esas cosas» → «No **les** des importancia a esas cosas».
- «Hay que decirle a los usuarios que» → «Hay que decir**les** a los usuarios que».

Fíjate en el último: el error se esconde mejor cuando el pronombre va pegado al infinitivo.

Para que no lo confundas con el leísmo: aquí el pronombre es indirecto de verdad (¿a quién se lo dije? a ellos), así que «les» es la forma correcta. El leísmo es otro problema: usar «le» donde iría «lo» (directo).

Verificación: pásalo a una construcción con «se»: «A mis padres se les dijo que no venía». El «les» aparece por sí solo.""",
            },
            {"role": "user", "content": "¿Y entonces «se los dije» en vez de «se lo dije (a ellos)»? En México lo dice todo el mundo."},
            {
                "role": "assistant",
                "content": """«Se los dije» con el sentido de «les dije eso» es un uso no normativo, pero muy extendido en México, Centroamérica, el Caribe y el Río de la Plata. En escritura formal se mantiene «se lo dije».

Lo que pasa gramaticalmente: cuando el indirecto «les» se convierte en «se» (por la regla que impide «le lo»), el plural deja de verse. El hablante siente que falta la marca de plural y se la pone al único pronombre que puede llevarla, «lo», aunque «lo» se refiera a una sola cosa (lo que se dijo).

| Lo que se quiere decir | Normativo | Variante americana |
|---|---|---|
| Dije **eso** (singular) a **ellos** (plural) | se **lo** dije | se **los** dije |
| Dije **esas cosas** (plural) a **él** (singular) | se **las** dije | se **las** dije (igual) |
| Dije **eso** a **él** | se **lo** dije | se **lo** dije (igual) |

La ambigüedad de número en «se lo dije» es normal en español y se resuelve por contexto o añadiendo el complemento: «se lo dije a ellos».

Recomendación práctica: en documentación, informes y correos de trabajo, «se lo dije a ellos» o «les dije eso». En diálogo oral o en un texto que reproduzca habla mexicana, «se los dije» es natural y nadie lo va a leer como error.

Prueba para detectarlo en revisión: elimina «se» y repón el indirecto completo. «Lo dije a ellos» → el directo es singular, luego el pronombre es «lo», no «los». Si tras reponer el indirecto el «los» no tiene a qué referirse, es la variante.

Verificación de que la tabla es coherente: en la segunda fila, «se las dije», el plural de «las» sí tiene referente (las cosas dichas). Por eso ahí coinciden norma y uso.""",
            },
        ]
    },
    # 21) Puntuación de diálogos con raya (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Estoy escribiendo un relato y no sé puntuar los diálogos. ¿Va así? «- Hola, dijo Juan - ¿cómo estás?»"},
            {
                "role": "assistant",
                "content": """Así no. La versión correcta es:

«—Hola —dijo Juan—. ¿Cómo estás?»

Cinco reglas que explican cada signo:

1. **Raya, no guion.** El signo de diálogo es la raya (—), el largo. El guion (-) es para «teórico-práctico» y para partir palabras.
2. **La raya va pegada a lo que dice el personaje.** «—Hola», sin espacio detrás de la raya. Sí hay espacio antes de la raya que abre el inciso del narrador: «Hola —dijo».
3. **El inciso del narrador va entre dos rayas**, como un paréntesis. La de cierre va pegada a la última palabra del inciso: «—dijo Juan—».
4. **El verbo de habla va en minúscula** («dijo», «preguntó», «murmuró»), aunque lo que precede sea una pregunta o una exclamación: «—¿Vienes? —preguntó Ana».
5. **El signo de puntuación que correspondería al diálogo se coloca después del inciso**, no antes. Como «Hola» cierra ahí la primera frase, el punto va tras la raya de cierre: «—dijo Juan—. ¿Cómo estás?».

Un caso que confunde a todo el mundo: cuando el inciso **no** lleva verbo de habla (el narrador describe una acción, no cómo se dijo algo), el parlamento se cierra con su signo y el inciso empieza con mayúscula:

«—No vengas. —Cerró la puerta—. Mañana hablamos.»

Compáralo con el inciso de habla:

«—No vengas —dijo, y cerró la puerta—. Mañana hablamos.»

Si el inciso termina el párrafo, no se pone raya de cierre:

«—No vengas —dijo Juan.»

Verificación de tu frase original con estas reglas: «- Hola,» (guion, coma antes del inciso) ✗ → «—Hola» ✓. «dijo Juan -» (sin raya de apertura del inciso, raya con espacio) ✗ → «—dijo Juan—.» ✓. «¿cómo estás?» tras el punto va con mayúscula ✓.""",
            },
            {"role": "user", "content": "¿Y si el personaje sigue hablando después del inciso, pero sin punto? Algo como «Hola, dijo Juan, qué tal todo»."},
            {
                "role": "assistant",
                "content": """Entonces la coma va **después** de la raya de cierre del inciso, nunca antes de la de apertura:

«—Hola —dijo Juan—, ¿qué tal todo?»

Es la misma regla de antes: el signo que el diálogo habría llevado sin inciso se desplaza al final del inciso. Sin inciso, la frase sería «—Hola, ¿qué tal todo?»; la coma estaba tras «Hola», y al meter «dijo Juan» se recoloca tras la raya de cierre.

Los tres casos, uno al lado de otro:

| Sin inciso | Con inciso | Qué pasa con el signo |
|---|---|---|
| —Hola, ¿qué tal todo? | —Hola —dijo Juan—, ¿qué tal todo? | la coma se mueve tras el inciso |
| —Hola. ¿Qué tal todo? | —Hola —dijo Juan—. ¿Qué tal todo? | el punto se mueve tras el inciso |
| —Hola, ¿qué tal todo? | —Hola, ¿qué tal todo? —dijo Juan. | inciso al final: el signo se queda, y el inciso cierra con punto y sin raya |

Lo que nunca va: coma antes de la raya de apertura («—Hola, —dijo Juan») ni los dos signos a la vez («—Hola, —dijo Juan—, ¿qué tal?»).

Y si el personaje no termina la frase, sino que la retoma sin pausa, no hay signo ninguno:

«—Creo —dijo Juan— que deberíamos irnos.»

Verificación con tu ejemplo: «Hola, qué tal todo» es una sola frase con coma interna; el inciso cae donde estaba la coma; la coma pasa detrás del inciso; «qué» lleva tilde porque es interrogativo y va entre signos. «—Hola —dijo Juan—, ¿qué tal todo?» cumple las cuatro cosas.""",
            },
        ]
    },
    # 22) Reglas de acentuación explicadas en inglés.
    {
        "messages": [
            {"role": "user", "content": "I'm learning Spanish and I can't figure out the written accent rules. Words like 'canción', 'árbol', 'médico'. Is there an actual rule or do I just memorize everything?"},
            {
                "role": "assistant",
                "content": """There is a rule, and it covers almost every word. You memorize only the exceptions (the diacritic pairs). It has two steps: find the stressed syllable, then check the last letter.

**Step 1: which syllable carries the stress?** Spanish classifies words by it:
- *Aguda*: stress on the last syllable (can-CIÓN, co-MER, pa-PEL).
- *Llana* (or *grave*): stress on the second-to-last (ÁR-bol, CA-sa, LI-bro).
- *Esdrújula*: stress on the third-to-last (MÉ-di-co, PÁ-ja-ro).
- *Sobresdrújula*: earlier still, only with attached pronouns (DÍ-ga-me-lo).

**Step 2: the rule per class.**

| Class | Written accent when | With accent | Without |
|---|---|---|---|
| aguda | it ends in a vowel, **-n** or **-s** | canción, café, jamás | comer, papel, reloj |
| llana | it ends in anything **other than** a vowel, -n or -s | árbol, fácil, lápiz | casa, examen, lunes |
| esdrújula / sobresdrújula | always | médico, teléfono, dígamelo | (none) |

The first two rows are mirror images: vowel/-n/-s is the default ending for llanas and the marked ending for agudas. That symmetry is the whole system.

**Your three words:**
- *canción*: stress on the last syllable, ends in -n → aguda ending in -n → accent.
- *árbol*: stress on the second-to-last, ends in -l → llana not ending in vowel/n/s → accent.
- *médico*: third-to-last → esdrújula → always.

**Two additions you'll hit quickly:**

1. **Hiatus with í or ú.** When a stressed *i* or *u* sits next to *a*, *e* or *o*, it takes an accent to show they are separate syllables, regardless of the table: *país*, *día*, *raíz*, *baúl*, *reír*. Without it, *dia* would read as one syllable.
2. **Plurals re-evaluate the rule.** The stress stays on the same syllable, but the ending changes: *canción* → *canciones* (now llana ending in -s: no accent); *examen* → *exámenes* (now esdrújula: accent).

What you do memorize: the small set of diacritic pairs where identical-looking words differ in meaning (*tú/tu*, *él/el*, *sí/si*, *más/mas*, *dé/de*, *sé/se*, *té/te*, *mí/mi*, *aún/aun*). Nine items, and the list never grows.

Verification you can run on any word: say it aloud, find the stressed syllable, look at the last letter, apply the row. *Teléfono*: te-LÉ-fo-no, esdrújula, accent. *Ciudad*: ciu-DAD, aguda ending in -d, no accent. *Lápiz*: LÁ-piz, llana ending in -z, accent. Three for three.""",
            },
        ]
    },
    # 23) Usuario en inglés pide respuesta en español: «cuando» + subjuntivo.
    {
        "messages": [
            {"role": "user", "content": "Please answer in Spanish, I'm practicing. When do I use «cuando llegue» vs «cuando llega»? My textbook says 'future', but «cuando llega, comemos» also sounds like the future to me."},
            {
                "role": "assistant",
                "content": """La diferencia no es «futuro o no futuro»: es **hábito** frente a **hecho concreto que aún no ha ocurrido**.

- «Cuando **llega**, comemos» (indicativo): describe una rutina. Cada vez que llega, comemos. Vale para el presente habitual y también para contar algo que pasa siempre.
- «Cuando **llegue**, comemos» (subjuntivo): habla de una llegada concreta que todavía no se ha producido. Hoy, esta tarde, mañana.

Tu intuición acierta en una cosa: las dos miran hacia delante. Pero «llega» mira hacia una repetición y «llegue» hacia un evento único pendiente.

Prueba para decidir: añade «siempre» o «mañana».
- «Siempre, cuando llega, comemos» ✓ → indicativo.
- «Mañana, cuando llegue, comemos» ✓ → subjuntivo.
- «Mañana, cuando llega, comemos» ✗ → no funciona en español estándar.

Lo que tu libro quiere decir con «futuro» es esto: cuando la oración de «cuando» se refiere a algo que no ha pasado, **nunca** se usa el futuro de indicativo. «Cuando llegará» es un error típico de hablantes de inglés («when he will arrive») y de francés. El español pone subjuntivo presente donde el inglés pone presente simple: «when he arrives» → «cuando llegue».

La misma regla vale para todas las conjunciones de tiempo: «en cuanto», «tan pronto como», «apenas», «hasta que», «mientras», «después de que», «siempre que».
- «Avísame en cuanto **termines**» (pendiente).
- «Me avisa en cuanto **termina**» (hábito).
- «No salgas hasta que **deje** de llover» (pendiente).

En pasado el contraste se mantiene, con otras formas:
- «Cuando **llegó**, comimos» → hecho ocurrido.
- «Dijo que comeríamos cuando **llegara**» → futuro visto desde el pasado, todavía pendiente en ese momento.

Verificación: traduce mentalmente al inglés y mira si cabría «whenever». «Cuando llega, comemos» = «Whenever he arrives, we eat» ✓ (hábito → indicativo). «Cuando llegue, comemos» = «When he arrives today, we'll eat» → no admite «whenever» → subjuntivo.""",
            },
        ]
    },
]

# --- Bloque 4 ---
ROWS += [
    # 24) Ambigüedad sintáctica: cuatro tipos y cómo evitarla en contratos (multiturno).
    {
        "messages": [
            {"role": "user", "content": "¿Por qué estas frases se entienden de dos formas y cómo las arreglo? «Vi a tu hermano con los prismáticos», «Se buscan cuidadores para niños que no fumen», «El equipo de Ana que ganó el torneo se disuelve» y «Juan le dijo a Pedro que su propuesta era mejor»."},
            {
                "role": "assistant",
                "content": """Cada una tiene una ambigüedad de tipo distinto. Las cuatro son correctas gramaticalmente; el problema es que la sintaxis admite dos estructuras y el lector tiene que elegir.

**1. «Vi a tu hermano con los prismáticos» → complemento que puede colgar de dos sitios.** «Con los prismáticos» puede ser el instrumento de «vi» (yo usaba los prismáticos) o una característica de «tu hermano» (él los llevaba). Es la ambigüedad de adjunción de sintagma preposicional, la más común en español y en inglés.
Arreglo: pega el complemento a lo que modifica, o cambia la estructura.
- «Con los prismáticos vi a tu hermano» (los usaba yo).
- «Vi a tu hermano, que llevaba los prismáticos» (los llevaba él).

**2. «Cuidadores para niños que no fumen» → relativo con dos antecedentes posibles.** «Que no fumen» puede referirse a «cuidadores» (lo que se quiere) o a «niños» (lo que se lee). Hay una pista que casi nadie ve: el subjuntivo «fumen» indica antecedente indeterminado (se busca un tipo de persona), lo cual encaja con «cuidadores», pero la proximidad a «niños» gana en la lectura.
Arreglo: acerca el relativo a su antecedente.
- «Se buscan cuidadores que no fumen para niños».
- O rompe la estructura: «Se buscan cuidadores de niños. Requisito: no fumar».

**3. «El equipo de Ana que ganó el torneo se disuelve» → relativo especificativo o explicativo.** Sin coma, «que ganó el torneo» distingue ese equipo de otros equipos de Ana (tiene varios y se disuelve el ganador). Con comas, es información añadida sobre el único equipo de Ana: «El equipo de Ana, que ganó el torneo, se disuelve». La coma cambia el significado, no solo el ritmo.
Arreglo: decide cuál de las dos cosas quieres decir y puntúa en consecuencia.

**4. «Juan le dijo a Pedro que su propuesta era mejor» → posesivo con dos referentes.** «Su» puede ser de Juan o de Pedro. El español no tiene forma de distinguirlo con el pronombre.
Arreglo: sustituye el posesivo por el nombre o pasa a estilo directo.
- «Juan le dijo a Pedro que la propuesta de Pedro era mejor».
- «Juan le dijo a Pedro: "Tu propuesta es mejor"».

Método general para detectar estas trampas en un texto propio: busca un complemento con «con», «de» o «en» detrás de un sustantivo (caso 1); un «que» precedido de dos sustantivos (caso 2); un «su», «le» o «lo» con dos candidatos en la frase (caso 4). Y revisa cada relativo sin comas preguntándote si quieres restringir o solo añadir información (caso 3).

Verificación de que los arreglos funcionan: lee cada versión reescrita e intenta forzar la lectura contraria. «Con los prismáticos vi a tu hermano» ya no admite que los llevara él; «cuidadores que no fumen para niños» ya no admite que fumen los niños. Si no puedes forzar la segunda lectura, está resuelto.""",
            },
            {"role": "user", "content": "¿Y en un contrato o en una especificación, cómo evito esto de forma sistemática? No puedo revisar frase por frase."},
            {
                "role": "assistant",
                "content": """Sí puedes, pero no a ojo: con reglas de redacción que eliminan las estructuras ambiguas antes de escribirlas. Las que usan los redactores de contratos y de especificaciones técnicas:

1. **Un sujeto, un verbo, un complemento por frase.** Las ambigüedades de adjunción (caso 1) nacen de acumular complementos. «El proveedor entregará el informe con las métricas en formato PDF antes del día 5» tiene tres complementos que pueden colgar de dos sitios cada uno. Partido: «El proveedor entregará el informe antes del día 5. El informe incluirá las métricas. El formato será PDF».

2. **Nada de pronombres de tercera persona ni posesivos entre partes.** En lugar de «su», «este», «aquel», «el mismo», repite el nombre definido: «el Proveedor», «el Cliente», «el Sistema». La repetición es fea y es exactamente lo que quieres. Los contratos definen términos con mayúscula para eso.

3. **Relativos siempre con antecedente contiguo.** Si un «que» no puede ir pegado a su sustantivo, conviértelo en frase independiente. «Los módulos del sistema que fallen» → «Los módulos que fallen» o «Si un módulo del sistema falla».

4. **Listas en vez de enumeraciones en prosa.** «Se entregarán el código, la documentación y las pruebas en español» → ¿solo las pruebas en español? En lista numerada, cada elemento lleva sus condiciones.

5. **Verbos modales con un solo significado.** «Debe» = obligación, «puede» = permiso, «debería» = recomendación. Nunca «debe de» ni «podrá» (que mezcla futuro y permiso). Es la convención de las normas técnicas, equivalente a *must / may / should*.

6. **Negaciones sin alcance dudoso.** «No se aceptarán entregas incompletas o fuera de plazo» puede leerse como dos condiciones o como una sola compuesta. Separa: «No se aceptarán entregas incompletas. No se aceptarán entregas fuera de plazo».

7. **Cuantificadores con alcance explícito.** «Todos los usuarios tienen acceso a un servidor» → ¿el mismo servidor para todos o uno cada uno? Di «a un mismo servidor» o «cada usuario tiene acceso a su propio servidor».

Un filtro mecánico que sí puedes pasar sin leer frase a frase: busca en el documento «su », «que » precedido de dos sustantivos, « o », «respectivamente» y «el mismo». Cada aparición es un candidato a revisar. En un contrato de veinte páginas suelen salir entre treinta y cincuenta, y de esos, unos diez son ambigüedades reales.

Verificación de que las reglas cubren tus cuatro frases iniciales: la 1 cae por la regla 1; la 2 y la 3, por la 3; la 4, por la 2. Con esas tres reglas aplicadas al escribir, ninguna de las cuatro habría existido.""",
            },
        ]
    },
    # 25) Participios dobles, para una traductora (en inglés).
    {
        "messages": [
            {"role": "user", "content": "I'm a translator working into Spanish. Quick one: is it 'he imprimido' or 'he impreso'? And 'frito' vs 'freído'? My reviewer flagged both and I'm not sure she's right."},
            {
                "role": "assistant",
                "content": """Both of your forms are correct, and so are your reviewer's. *Imprimir*, *freír* and *proveer* are the only three Spanish verbs with two fully valid participles, usable in compound tenses and passives alike.

| Verb | Regular participle | Irregular participle | Usage note |
|---|---|---|---|
| imprimir | imprimido | impreso | *impreso* is far more frequent everywhere; *imprimido* is correct but sounds bookish in Spain and odd in parts of America |
| freír | freído | frito | *frito* dominates in speech; *freído* appears in careful writing and recipes |
| proveer | proveído | provisto | *provisto* is the common one; *proveído* survives mainly in legal Spanish |

So *he impreso el informe* and *he imprimido el informe* are both standard. If the client has a style guide, follow it; if not, pick the frequent form (*impreso*, *frito*, *provisto*) and stay consistent.

Where your reviewer may have a point is a different group: verbs whose short form is **only an adjective**, never a participle. Using it in a compound tense is a real error.

| Participle (for *haber* and passives) | Adjective only |
|---|---|
| ha elegido, fue elegido | el presidente electo |
| ha bendecido | agua bendita |
| ha despertado | está despierto |
| ha soltado | el perro está suelto |
| ha confundido | un texto confuso |
| ha prendido | el ladrón está preso |
| ha corrompido | un archivo corrupto |
| ha maldecido | un lugar maldito |

*Ha electo* or *fue electo presidente* is the common slip, especially in Latin American press under English influence; the standard is *fue elegido presidente* and *el presidente electo*.

The test to decide which group a verb belongs to: put the short form after *haber*. If *he + short form* sounds impossible to any native speaker (*he electo*, *he bendito*, *he despierto*), it's adjective-only. If it sounds fine (*he impreso*, *he frito*, *he provisto*), it's a true double participle.

Verification against a reference: the DPD (*Diccionario panhispánico de dudas*) entries for *imprimir*, *freír* and *proveer* explicitly list both participles as valid in all functions. That is the line to send your reviewer.""",
            },
        ]
    },
    # 26) deber / deber de (usuario mexicano).
    {
        "messages": [
            {"role": "user", "content": "¿Hay diferencia entre «debe estar en la oficina» y «debe de estar en la oficina»? En México casi nadie dice el «de»."},
            {
                "role": "assistant",
                "content": """Hay diferencia, y es de significado:

- «**Debe** estar en la oficina» = tiene la obligación de estar ahí. Obligación.
- «**Debe de** estar en la oficina» = probablemente está ahí, lo supongo. Probabilidad.

La norma reserva «deber + infinitivo» para la obligación y «deber de + infinitivo» para la suposición. En el habla, sobre todo en México y en buena parte de América, «debe estar» se usa para las dos cosas, y la RAE lo admite para la probabilidad porque el uso es abrumador. Lo que **no** admite es el camino contrario: «debes de estudiar más» con sentido de obligación es incorrecto en cualquier registro.

| Forma | Obligación | Probabilidad |
|---|---|---|
| debe estar | ✓ (sentido principal) | ✓ admitido por extensión |
| debe de estar | ✗ | ✓ (sentido único) |

En textos donde la distinción importa, conviene mantenerla, porque el lector no puede adivinar cuál de las dos quisiste decir:

- Especificaciones y manuales: «El servicio **debe** reiniciarse cada noche» es un requisito. Si escribes «debe de reiniciarse», estás diciendo que crees que se reinicia, que es otra cosa.
- Informes de incidentes: «El fallo **debe de** venir del balanceador» es una hipótesis. «El fallo debe venir del balanceador» suena a que el fallo tiene la obligación de venir de ahí.

Esto conecta con la convención de las normas técnicas, que traduce «must» por «debe», «should» por «debería» y «may» por «puede». Ahí «deber de» no tiene sitio, precisamente porque un requisito nunca es una suposición.

Para el pasado, la misma pareja: «Debió llegar a las ocho» (tenía que haber llegado) frente a «Debió de llegar a las ocho» (supongo que llegó a esa hora).

Prueba para elegir: sustituye por «tiene que» y por «seguramente». «Tiene que estar en la oficina» → obligación → «debe». «Seguramente está en la oficina» → probabilidad → «debe de». Si las dos sustituciones te parecen válidas, la frase es ambigua y hay que reescribirla.

Verificación con un caso donde solo cabe una: «Los visitantes deben registrarse en recepción». «Seguramente se registran» no tiene sentido como norma de un edificio. Obligación, sin «de».""",
            },
        ]
    },
    # 27) Muletillas de oficina: «a nivel de», «en base a», «a día de hoy».
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de textos. Sé directo: diagnóstico, corrección y motivo."},
            {"role": "user", "content": "Me dicen que escribo «como un consultor» y que no se entiende nada. Mi párrafo: «A nivel de equipo, en base a los datos, a día de hoy estamos en disposición de poner en valor la propuesta de cara al cliente, en relación a lo que se habló». ¿Qué sobra?"},
            {
                "role": "assistant",
                "content": """Sobra casi todo. Tu párrafo tiene 34 palabras y dice esto: «Con los datos actuales, el equipo ya puede presentar la propuesta al cliente, como se acordó» (16 palabras).

Lo que había dentro, expresión por expresión:

| Expresión | Qué le pasa | Sustituto |
|---|---|---|
| a nivel de equipo | «A nivel de» solo es correcto cuando hay niveles reales (a nivel del mar, a nivel ministerial). Como sinónimo de «en cuanto a» es un relleno que la RAE desaconseja. | el equipo (como sujeto) |
| en base a | Calco; la norma prefiere «con base en», «a partir de», «según». | con los datos |
| a día de hoy | Calco del francés; «hoy» o «actualmente» dicen lo mismo con menos. | actuales / ya |
| estamos en disposición de | Perífrasis de «podemos». | puede |
| poner en valor | Jerga administrativa; significa «presentar», «destacar» o «aprovechar» según el contexto, y el lector tiene que adivinar cuál. | presentar |
| de cara al cliente | «Al cliente» basta. «De cara a» tiene sentido con «el futuro» o «las elecciones», no como sustituto de «para». | al cliente |
| en relación a | La forma normativa es «en relación con» o «con relación a». Y aquí ni hace falta: es «como se acordó». | como se acordó |

Dos cosas que pasan cuando acumulas estas fórmulas:

1. **El sujeto desaparece.** Tu frase no tiene quién: «estamos» es un nosotros vago. La reescritura pone «el equipo» como sujeto y «puede presentar» como verbo. Sujeto concreto + verbo de acción es lo que hace que una frase se entienda a la primera.
2. **Las preposiciones se multiplican.** Cuéntalas en tu versión: a, de, en, a, a, de, en, de, de, en, a. Once. En la reescritura, cuatro. Las preposiciones son el pegamento, y cuando hay más pegamento que piezas, se nota.

Si el párrafo necesita sonar más formal, no vuelvas a las muletillas; añade precisión: «Con los datos del segundo trimestre, el equipo puede presentar la propuesta al cliente el jueves, según lo acordado en la reunión del día 3». Más formal y más informativo, sin una sola fórmula.

Verificación: lee la versión corta en voz alta a alguien de fuera del proyecto y pregúntale qué va a pasar. Si responde «que van a presentar una propuesta al cliente», está entendida. Haz lo mismo con la original.""",
            },
        ]
    },
    # 28) «detrás mío», «adelante de», «entrá adentro» (usuario argentino).
    {
        "messages": [
            {"role": "user", "content": "¿«Detrás mío» está mal? En Argentina lo dice todo el mundo, y también «adelante de la casa» y «entrá adentro»."},
            {
                "role": "assistant",
                "content": """Son tres casos distintos: uno no normativo, uno aceptado en América y uno redundante pero tolerado.

**1. «Detrás mío» → no normativo. Lo correcto es «detrás de mí».** «Detrás», «delante», «encima», «debajo», «cerca», «lejos», «enfrente», «alrededor», «dentro» y «fuera» son adverbios, y los adverbios no admiten posesivo: nadie dice «lejos tuyo» ni «cerca suyo», aunque sí «detrás mío» y «encima mío». El patrón normativo es «adverbio + de + pronombre»: «detrás de mí», «encima de ti», «delante de ellos».

Dos matices:
- La forma femenina («detrás mía», «encima suya») es un error mayor que la masculina: ni siquiera hay sustantivo con el que concordar.
- «Al lado mío», «a la derecha tuya», «a espaldas suyas» sí son correctas, porque «lado», «derecha» y «espaldas» son sustantivos y admiten posesivo.

El uso está extendido en Argentina, Uruguay, Chile, Centroamérica y también en España; el DPD lo califica de impropio y lo desaconseja en la lengua cuidada. En un chat con amigos nadie te va a corregir; en un texto formal, sí.

**2. «Adelante de la casa» → aceptado en el español de América.** En España la pareja es «delante de» (lugar) y «adelante» (dirección: «siguió adelante»). En América, «adelante de» con valor de lugar está consolidado y el DPD lo acepta: «adelante de la casa», «atrás de la casa», «adentro de la caja», «afuera del edificio». Para escribir en español neutro o para un público de España: «delante de», «detrás de», «dentro de», «fuera de».

**3. «Entrá adentro» → redundante, pero no incorrecto.** «Entrar» ya significa ir adentro; la expresión repite la idea, como «subir arriba» o «salir afuera». La norma lo considera pleonasmo expresivo: aceptable en la lengua coloquial, prescindible en la escrita. Lo mismo con «volver a repetir» o «vuelvo de nuevo».

Resumen:

| Expresión | Registro informal | Texto formal |
|---|---|---|
| detrás mío | se oye y se entiende | detrás de mí |
| adelante de la casa | correcto en América | delante de la casa (España) / adelante de la casa (América) |
| entrá adentro | expresivo, válido | entrá |

Verificación del caso 1 por analogía: sustituí el adverbio por otro de la misma lista. «Cerca mío» te suena peor que «detrás mío», pero es la misma estructura. Si la estructura falla con «cerca», falla con «detrás»; lo único que cambia es la costumbre.""",
            },
        ]
    },
    # 29) Tilde en interrogativos indirectos.
    {
        "messages": [
            {"role": "user", "content": "No entiendo cuando «que», «como», «donde» y «cuando» llevan tilde si no hay signos de interrogación. Por ejemplo: «No sé que hacer», «dime donde vives», «lo hizo como pudo», «el día que llegó»."},
            {
                "role": "assistant",
                "content": """Dos de tus cuatro llevan tilde y dos no: «No sé **qué** hacer», «Dime **dónde** vives», «lo hizo como pudo», «el día que llegó».

La regla: «qué», «cómo», «dónde», «cuándo», «cuánto», «quién», «cuál» llevan tilde cuando son **interrogativos o exclamativos**, con o sin signos. No la llevan cuando son **relativos o conjunciones**.

Sin signos, el interrogativo aparece en las preguntas indirectas: una pregunta metida dentro de otra frase. Tres pruebas para verlo:

1. **¿Hay una pregunta escondida?** «No sé qué hacer» contiene la pregunta «¿Qué hago?». «Dime dónde vives» contiene «¿Dónde vives?». Tilde.
2. **¿Puedes responder a la palabra?** «No sé qué hacer» → ¿qué? → «irte, quedarte». Hay una incógnita. «El día que llegó» → ¿qué? → no hay nada que responder: «que» solo conecta con «el día». Sin tilde.
3. **¿Se pronuncia con fuerza?** Los interrogativos son tónicos: «No sé QUÉ hacer». Los relativos son átonos: «el día que lleGÓ» (la fuerza va en el verbo). Dilo en voz alta y escucha.

Los relativos y conjunciones (sin tilde) siempre remiten a algo que ya está en la frase:
- «El día **que** llegó» = el día en el cual llegó. «Que» remite a «el día».
- «Lo hizo **como** pudo» = de la manera en que pudo. «Como» remite al modo, sin pregunta.
- «La ciudad **donde** nací» = en la cual nací.
- «Vendrá **cuando** termine» = en el momento en que termine.

Pares mínimos:

| Con tilde (incógnita) | Sin tilde (conector) |
|---|---|
| No sé **cómo** lo hizo. | Lo hizo **como** pudo. |
| Pregunta **dónde** está. | Está **donde** lo dejaste. |
| Dime **cuándo** vienes. | Ven **cuando** quieras. |
| No sé **qué** quiere. | Dice **que** quiere irse. |

Los exclamativos siguen la misma regla: «¡**Qué** bien!», «Mira **cómo** llueve», «No sabes **cuánto** lo siento».

Una trampa: «si» nunca lleva tilde en las preguntas indirectas («No sé si vendrá»), aunque también introduce una incógnita; la tilde de «sí» es solo para la afirmación y el reflexivo.

Y en tu propio mensaje: «No entiendo **cuándo** llevan tilde» es pregunta indirecta (¿cuándo la llevan?), así que ahí también va con tilde.

Verificación por la prueba 2 en tus cuatro frases: «qué hacer» → responde «nada» ✓ tilde. «dónde vives» → responde «en Lima» ✓ tilde. «como pudo» → ¿como qué? no hay respuesta ✗ sin tilde. «el día que llegó» → ¿que qué? sin sentido ✗ sin tilde.""",
            },
        ]
    },
    # 30) Post de LinkedIn con varios errores; el usuario quiere conservar el tono (multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Mira este post que quiero publicar y dime todo lo que esté mal: «Super contento de anunciar de que me uno a Acme como Senior Developer! Habían muchas opciones pero elegí esta por que el equipo es increible. Gracias a todos los que me apoyaron, especialmente a mis ex-compañeros, sin los cuales esto no hubiera sido posible, consiguiendo este nuevo reto. A por ello!»"},
            {
                "role": "assistant",
                "content": """Versión corregida:

«¡Súper contento de anunciar que me uno a Acme como Senior Developer! Había muchas opciones, pero elegí esta porque el equipo es increíble. Gracias a todos los que me apoyaron, especialmente a mis excompañeros, sin los cuales este nuevo reto no habría sido posible. ¡A por ello!»

Nueve correcciones:

1. **«Super» → «Súper».** Como adverbio o adjetivo independiente («súper contento», «un plan súper»), lleva tilde: es llana terminada en «r». Solo va sin tilde cuando es prefijo pegado: «supermercado», «superhéroe».
2. **Faltan los signos de apertura.** «¡Súper contento de anunciar que me uno a Acme como Senior Developer!» y «¡A por ello!». En español van en pareja, también en redes.
3. **«anunciar de que» → «anunciar que».** Dequeísmo. Prueba: ¿qué anuncias? → «que me uno», sin «de».
4. **«Habían muchas opciones» → «Había muchas opciones».** «Haber» existencial no concuerda: siempre singular.
5. **Coma antes de «pero».** «Había muchas opciones, pero elegí esta».
6. **«por que» → «porque».** Causal: «ya que el equipo es increíble».
7. **«increible» → «increíble».** Hiato «e-í» con la «i» tónica: lleva tilde siempre.
8. **«ex-compañeros» → «excompañeros».** Desde 2010 los prefijos van pegados a la palabra: «exjefe», «expresidente», «excompañero». Solo llevan guion ante mayúscula o sigla («ex-Beatle») y van separados ante un grupo de palabras («ex primer ministro»).
9. **«sin los cuales esto no hubiera sido posible, consiguiendo este nuevo reto» → reestructurado.** El gerundio «consiguiendo» es de posterioridad y, además, no tiene sujeto claro (¿quién consigue, tú o tus excompañeros?). Lo integré como sujeto de la oración: «sin los cuales este nuevo reto no habría sido posible». «Hubiera» y «habría» son ambas válidas aquí; «habría» es la forma más clara.

Dos observaciones que no son errores:

- «Senior Developer» puede quedarse en inglés si es el título oficial del puesto. Si prefieres traducirlo, la forma adaptada es «desarrollador sénior», con tilde.
- «¡A por ello!» es una expresión de España; en América se entiende, pero suena ajena. Si tu red es internacional, «¡Vamos!» o «¡Con todo!» funcionan en todas partes.

Verificación: tildes del texto final: «Súper», «Había», «increíble», «habría». Cada una responde a una regla general; ninguna es diacrítica. Y el gerundio ha desaparecido: no queda ningún «-ando/-iendo» que explicar.""",
            },
            {"role": "user", "content": "Vale, pero no quiero que suene a comunicado de prensa. Quiero mantener el tono informal."},
            {
                "role": "assistant",
                "content": """Informal no es lo mismo que incorrecto. Nada de lo que corregí era tono: eran faltas de ortografía y gramática que se ven igual en un post desenfadado que en uno formal, y que en LinkedIn un reclutador sí nota.

La versión que te di ya es informal: «súper contento», «increíble», «reto», exclamaciones. Lo que la hace sonar más rígida es la frase larga del medio con «sin los cuales». Esa es la que puedes soltar:

«¡Súper contento de anunciar que me uno a Acme como Senior Developer! Había muchas opciones, pero elegí esta porque el equipo es increíble. Gracias a todos los que me apoyaron, y sobre todo a mis excompañeros: sin ustedes este reto no habría sido posible. ¡A por ello!»

Qué cambié para el tono, sin tocar la corrección:

- **«sin los cuales» → «sin ustedes»** (o «sin vosotros» si tu público es de España). El relativo culto era lo que sonaba a comunicado; la segunda persona habla a la gente directamente.
- **«especialmente» → «sobre todo».** Mismo significado, registro más conversacional.
- **Dos puntos antes de «sin ustedes».** Marcan el giro hacia el agradecimiento directo y evitan la subordinada.
- **Frases cortas.** Ninguna pasa de dieciséis palabras. Eso es lo que da ritmo de post, no las faltas.

Lo que mantengo porque es corrección, no registro: «anunciar que» (el dequeísmo no es informal, es un error), «había», «porque», «increíble», «excompañeros» y los signos de apertura. Un post informal con faltas no parece relajado; parece descuidado, y en un anuncio profesional eso juega en contra.

Verificación de tono: léelo en voz alta como se lo contarías a un amigo. Si hay alguna palabra que no dirías hablando, cámbiala. En esta versión no debería quedar ninguna: «súper», «increíble», «sobre todo», «reto» son todas de conversación.""",
            },
        ]
    },
]
