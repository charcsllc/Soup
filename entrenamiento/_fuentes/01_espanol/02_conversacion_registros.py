"""Español: conversación y registros. 30 filas SFT (chatml).

Temas: registro formal vs informal, correo profesional, cliente enfadado, pedir un
aumento, responder a una crítica, variedades (vos/ustedes/vosotros, léxico de México,
Argentina, Colombia y España), cortesía, charlas cotidianas con contenido real,
entrevista técnica (roleplay), explicar a un niño y luego a un experto.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS: list[dict] = []

# --- Bloque 1 ---
ROWS += [
    # 1) Correo formal: pedir una prórroga a un cliente.
    {
        "messages": [
            {"role": "user", "content": "Necesito pedirle a un cliente una semana más para entregar el proyecto porque el equipo tuvo dos bajas por enfermedad. Es un cliente formal, un banco. ¿Me escribes el correo? No quiero sonar a excusa."},
            {
                "role": "assistant",
                "content": """Asumo que el proyecto se llama Alfa, que la entrega prevista era el 20 de marzo y que hay una parte ya terminada; cambia esos datos por los tuyos.

**Asunto:** Proyecto Alfa: propuesta de nueva fecha de entrega (27 de marzo)

Estimada señora Ortiz:

Le escribo para proponerle una nueva fecha de entrega del proyecto Alfa: el 27 de marzo, una semana más tarde de lo previsto.

El motivo es que dos personas del equipo han causado baja por enfermedad esta semana. Hemos redistribuido su trabajo, pero no es posible absorberlo sin ajustar el calendario si queremos mantener la calidad acordada.

Para que el cambio afecte lo menos posible a su planificación:

- El módulo de conciliación, ya terminado y probado, se lo entregamos el viernes 20 como estaba previsto, de modo que su equipo pueda empezar las pruebas de aceptación.
- El módulo de informes y la documentación de validación se entregan el 27.
- Le enviaré un estado de avance cada martes hasta la entrega.

¿Le encaja esta fecha? Si prefiere que lo hablemos, estoy disponible mañana de 10:00 a 13:00.

Un cordial saludo,

Laura Méndez
Directora de proyecto

---

Por qué está construido así:

1. **El asunto ya dice la noticia y la fecha.** Quien lea solo la bandeja de entrada se entera igual. Un asunto como «Sobre la entrega» obliga a abrir el correo para saber si es grave.
2. **La causa ocupa una frase y es un hecho, no una justificación.** «Dos personas han causado baja» es verificable y no admite réplica. Lo que convierte una causa en excusa es rodearla de adjetivos («una situación muy complicada», «circunstancias imprevistas») o repetir disculpas. Aquí no hay ninguna disculpa, y no hace falta: estás proponiendo un plan.
3. **Lo que sí se entrega a tiempo va antes que lo que se retrasa.** El cliente lee primero que puede empezar a probar el viernes; el retraso afecta a una parte, no al todo.
4. **El plan es concreto: qué, cuándo y con qué seguimiento.** Los estados semanales son lo que de verdad reduce la ansiedad del cliente, más que la disculpa.
5. **Cierra con una pregunta y una alternativa.** Pide una respuesta y le da una vía fácil si no quiere escribir.

Tres cosas que quité a propósito: «lamentablemente», «pido disculpas por las molestias» y cualquier mención a cuánto ha trabajado el equipo. Ninguna le sirve al banco para decidir, y las tres suenan a que te estás defendiendo.

Verificación: léelo como si fueras la señora Ortiz y tuvieras treinta segundos. En la primera línea sabes la fecha nueva; en la segunda, por qué; en la lista, qué recibes y cuándo. No hay nada que tengas que preguntar para poder decidir.""",
            },
        ]
    },
    # 2) De mensaje informal a correo formal sin sonar a robot.
    {
        "messages": [
            {"role": "user", "content": "Esto es lo que le iba a mandar a mi jefa por Slack, pero me han dicho que mejor por correo y más formal: «Hola Marta! Oye que al final lo del informe no llega para el jueves, se me ha liado todo con lo de producción, te lo paso el lunes si te parece bien, perdón!!». ¿Cómo lo pongo formal sin que suene a robot?"},
                {
                "role": "assistant",
                "content": """Formal no significa tratarla de usted ni usar palabras raras. Si la tuteas a diario, sigue tuteándola. Lo que cambia es la **estructura**, la **precisión** y la ausencia de marcas de oralidad.

Versión en correo:

**Asunto:** Informe de ventas: entrega el lunes 24 en lugar del jueves

Hola, Marta:

El informe de ventas no va a estar listo el jueves. Esta semana he tenido que dedicar dos días a la incidencia de producción y no me ha dado tiempo a cerrar los datos de marzo.

Te lo envío el lunes 24 por la mañana. Si lo necesitas antes para alguna reunión, dímelo y te paso el viernes la parte de facturación, que ya está terminada.

Un saludo,
Diego

Lo que cambia respecto a tu mensaje, uno por uno:

| En Slack | En el correo | Por qué |
|---|---|---|
| «Hola Marta!» | «Hola, Marta:» | Coma de vocativo y dos puntos tras el saludo. Un solo signo de exclamación, y al principio ninguno. |
| «Oye que al final lo del informe» | «El informe de ventas» | Nombra la cosa. «Lo del informe» obliga a la lectora a reconstruir de qué hablas. |
| «no llega para el jueves» | «no va a estar listo el jueves» | Mismo contenido, sin el verbo coloquial. |
| «se me ha liado todo con lo de producción» | «he tenido que dedicar dos días a la incidencia de producción» | La causa, con un dato (dos días) y sin dramatizar. «Se me ha liado» describe tu estado de ánimo; el correo describe hechos. |
| «te lo paso el lunes si te parece bien» | «Te lo envío el lunes 24 por la mañana» | Fecha completa y hora aproximada. «Si te parece bien» deja la decisión en el aire; mejor afirmar y ofrecer alternativa. |
| (nada) | «Si lo necesitas antes, te paso la parte de facturación» | Esto es lo que hace que el correo no sea solo una mala noticia: das una opción. |
| «perdón!!» | (nada) | Un retraso de dos días laborables con causa justificada no requiere disculpa. Si quieres incluirla, una vez y sin exclamaciones: «Siento el cambio». |

Las marcas de oralidad que se eliminan siempre al pasar a correo: «oye», «al final», «lo de», «todo», las exclamaciones dobles y las frases encadenadas con comas sin punto. No son errores en Slack; en un correo que tu jefa puede reenviar a su jefe, pesan.

Lo que **no** hace falta cambiar: el tuteo, «Hola», «Un saludo», la longitud (sigue siendo corto). Un correo formal de cuatro líneas es perfectamente normal; lo que suena a robot es añadir «Por la presente le informo» o «Quedo a su entera disposición».

Verificación: lee el correo en voz alta. Si suena a algo que dirías en una reunión con tu jefa, está bien. Si suena a carta del banco, has pasado de formal a acartonado.""",
            },
        ]
    },
    # 3) Cliente enfadado: respuesta y escalada (multiturno).
    {
        "messages": [
            {"role": "system", "content": "Eres responsable de atención al cliente de una tienda en línea. Respondes con empatía, precisión y sin fórmulas vacías."},
            {"role": "user", "content": "Un cliente nos escribió esto: «ES LA TERCERA VEZ QUE ESCRIBO. Mi pedido 48213 lleva 12 días 'en reparto'. Son unos incompetentes y me están tomando el pelo. Quiero mi dinero YA o pongo una reclamación en consumo.» ¿Cómo le respondo?"},
            {
                "role": "assistant",
                "content": """Antes de escribir una palabra, mira el pedido 48213 en el sistema de la transportista. La respuesta tiene que llevar lo que hayas visto; una respuesta sin datos es la cuarta vez que le haces perder el tiempo. Asumo que el paquete aparece parado en un centro logístico desde hace días y que no hay fecha de entrega fiable.

Respuesta:

---

Hola, Javier:

Tienes razón en las tres cosas: son doce días, es la tercera vez que escribes y no te hemos dado una respuesta útil. Lo siento.

He revisado el pedido 48213 con la transportista. El paquete lleva desde el día 8 en su centro de Zaragoza sin movimiento; han abierto una incidencia, pero no me garantizan fecha. No te voy a pedir que esperes más.

Tienes dos opciones; elige la que prefieras y la activo hoy mismo:

1. **Reembolso completo** (84,90 €) a tu tarjeta. Lo emito en cuanto me confirmes; lo verás en tu cuenta en 3 a 5 días hábiles, según tu banco.
2. **Reenvío con otra transportista**, salida mañana y entrega en 24 a 48 h, sin coste. Si el paquete original aparece, te lo quedas o lo devuelves, como prefieras.

Mi nombre es Ana Ruiz y este caso lo llevo yo. Si respondes a este correo, me llega directamente.

Un saludo,
Ana

---

Por qué está escrita así:

- **Reconoce los hechos concretos que él ha citado** (doce días, tercera vez) en vez de «lamentamos las molestias». Quien está enfadado necesita comprobar que le has leído; la fórmula genérica demuestra lo contrario.
- **No le pide calma, no se defiende y no explica la logística interna.** Nada de «entendemos su frustración» ni «debido al alto volumen de pedidos». A él no le importa, y lo lee como excusa.
- **Da datos verificables**: dónde está el paquete y desde cuándo. Eso convierte «incompetentes» en «un paquete perdido en Zaragoza», que es un problema con solución.
- **Ofrece el reembolso como opción real y primera**, no como último recurso. Él lo ha pedido; negárselo o condicionarlo es lo que lleva a la reclamación. Las dos opciones tienen fecha.
- **Una persona con nombre asume el caso.** La amenaza de reclamación casi siempre viene de sentir que nadie se hace cargo.
- **Una sola disculpa, corta, al principio.** Repetirla suena a servilismo y no arregla nada.

Lo que no debes hacer: responder al tono. Las mayúsculas y el «incompetentes» no se contestan, se ignoran. Si contestas «le rogamos mantenga un tono respetuoso», has perdido al cliente y, probablemente, has ganado la reclamación.

Verificación: ponte en su lugar y lee solo la primera frase y la lista. ¿Sabes qué ha pasado, qué puedes elegir y cuándo se resuelve? Sí. ¿Hay algo que te obligue a escribir una cuarta vez? Solo elegir la opción.""",
            },
            {"role": "user", "content": "Le respondí y contestó: «No quiero otro envío, quiero el dinero y que me digan quién es el responsable». Y mi jefe dice que no reembolsemos hasta que el paquete vuelva al almacén."},
            {
                "role": "assistant",
                "content": """Tu jefe está protegiendo 84,90 € y arriesgando bastante más. Aquí hay un conflicto de política interna, y el cliente tiene la razón legal y la razón práctica.

**Por qué conviene reembolsar ya:**

1. Asumo que vendéis en España. Un consumidor al que no se entrega en el plazo acordado puede resolver el contrato y tiene derecho a la devolución de lo pagado sin demora indebida (es la regla general de la ley de consumidores, y la de la UE). Esperar a que el paquete «vuelva» no es un requisito que puedas imponerle: el paquete perdido es un problema entre vosotros y la transportista, no entre vosotros y él.
2. Una reclamación en consumo cuesta tiempo de gestión, puede acabar en sanción y queda registrada. Una reseña pública con captura de este hilo cuesta más. Ninguna de las dos vale 84,90 €.
3. El reembolso y la recuperación del paquete son procesos independientes. Reembolsas hoy; reclamas a la transportista por el envío perdido con su propio seguro. Si el paquete vuelve, lo reintegras al stock. No pierdes el paquete por haber reembolsado antes.

**Lo que le dices a tu jefe** (tres líneas, por escrito):

«El cliente del pedido 48213 ha pedido el reembolso tras 12 días sin entrega. Legalmente tiene derecho a él sin esperar a la devolución del paquete, y ha anunciado reclamación en consumo. Propongo reembolsar hoy y abrir la reclamación a la transportista en paralelo; el coste de no hacerlo es mayor que el del pedido.»

**La respuesta al cliente:**

---

Hola, Javier:

Entendido: reembolso. Lo he emitido hoy a las 12:40 a la tarjeta con la que pagaste, por el importe completo (84,90 €). Según tu banco, lo verás entre el lunes y el miércoles. Te adjunto el justificante.

Sobre el responsable: del pedido y de la respuesta que no te dimos a tiempo me hago cargo yo, Ana Ruiz, como responsable de atención al cliente. Del paquete perdido, la transportista, con la que ya hemos abierto la reclamación; eso es cosa nuestra y no te afecta.

Si el reembolso no aparece el miércoles, respóndeme a este correo y lo persigo con el banco.

Un saludo,
Ana

---

Tres decisiones en esa respuesta:

- **Hora exacta y justificante.** «Lo he emitido» sin prueba es la frase que lleva a la cuarta queja. La hora y el adjunto cierran el tema.
- **«Quién es el responsable» tiene respuesta, y es una persona con nombre.** No la empresa, no «el departamento», no la transportista como escudo. Asumir el fallo de comunicación (que sí es vuestro) y separar el fallo logístico (que es de la transportista) es honesto y desactiva la pregunta.
- **Un último punto de contacto con condición clara.** Le das el siguiente paso solo si algo falla; si no, la conversación ha terminado.

Verificación: si tu jefe mantiene el no, pide que la decisión quede por escrito con su nombre. Es la manera educada de hacer visible quién asume el riesgo de la reclamación, y suele cambiar la decisión.""",
            },
        ]
    },
    # 4) Pedir un aumento (multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Llevo dos años en la empresa sin subida, he asumido el soporte de dos sistemas más y he formado a tres personas nuevas. Quiero pedir un aumento, pero no sé cómo plantearlo sin que suene a amenaza ni a súplica."},
            {
                "role": "assistant",
                "content": """Ni amenaza ni súplica: una **petición con datos y una cifra**. Lo que hace que suene a súplica es hablar de lo que necesitas; lo que hace que suene a amenaza es hablar de lo que harás si no. Habla solo de lo que aportas y de lo que pides.

**1. Preparación (una semana antes).**

- Escribe tres hechos con números: «Desde enero de 2024 doy soporte a Facturación y a Inventario además de Pedidos: de un sistema a tres». «He formado a tres incorporaciones; las tres están ya en guardia sin acompañamiento». «El tiempo medio de resolución de incidencias de mi área bajó de 2,1 días a 0,9».
- Busca el rango de mercado para tu puesto y ciudad (ofertas públicas, encuestas salariales, lo que cobran los recién contratados en tu empresa si lo sabes). Necesitas un número defendible.
- Decide la cifra que pides y el mínimo que aceptarías. Pide una cantidad concreta (un 15 %, o «de 38 000 a 44 000»), no «una subida». Lo que no se cuantifica no se aprueba.

**2. Pide la reunión con tema.** «Quiero hablar contigo de mi salario y de cómo ha cambiado mi puesto. ¿Te viene bien el jueves a las 11?» Nunca en el pasillo ni al final de otra reunión: le das tiempo a prepararse y evitas un no reflejo.

**3. El guion (cuatro partes, cinco minutos).**

> «Quería hablar de mi salario. En estos dos años mi puesto ha cambiado: he pasado de dar soporte a un sistema a tres, he formado a Marta, Luis y Sara, que ya están en guardia solos, y el tiempo de resolución de mi área se ha reducido más de la mitad.
>
> Mi salario es el mismo que cuando entré. Para un puesto con estas responsabilidades, el mercado está entre 42 000 y 46 000. Te pido pasar a 44 000.
>
> ¿Cómo lo ves?»

Y después de la pregunta, **silencio**. Deja que responda. La mayoría de la gente llena el silencio rebajando la petición antes de que el otro haya hablado.

**4. Lo que no dices:**

- Nada de gastos personales (hipoteca, alquiler). Es tu vida, no un argumento.
- Nada de comparaciones con compañeros concretos. Te mete en una discusión sobre ellos.
- Nada de «si no, me iré», salvo que tengas otra oferta y estés dispuesto a usarla. Un farol descubierto te cuesta la credibilidad para siempre.
- Nada de «sé que no es buen momento» ni «no sé si es posible». Estás pidiendo algo razonable; no te disculpes por pedirlo.

**5. Respuestas probables y qué haces:**

| Respuesta | Qué significa | Tu siguiente frase |
|---|---|---|
| «Déjame mirarlo» | Normal; necesita aprobación | «¿Para cuándo me puedes decir algo?» |
| «No hay presupuesto» | Puede ser cierto o una evasiva | «Entiendo. ¿Cuándo lo hay, y qué tendría que pasar para que entre?» |
| «Es mucho» | Está negociando | «¿Qué cifra ves razonable para estas responsabilidades?» |
| «Sí» | Lo has preparado bien | «Gracias. ¿Me lo confirmas por correo con la fecha de efecto?» |

Verificación de que el planteamiento es correcto: lee el guion y comprueba que no contiene ningún «necesito», ningún «me gustaría» y ningún condicional. Solo hechos, una cifra y una pregunta.""",
            },
            {"role": "user", "content": "Lo hice y me dijo que no hay presupuesto hasta el año que viene. ¿Y ahora?"},
            {
                "role": "assistant",
                "content": """«No hay presupuesto hasta el año que viene» no es un no a tu valor: es un no a la fecha. Lo que tienes que hacer es convertirlo en un **compromiso por escrito con fecha, cifra y condiciones**, y mientras tanto conseguir algo.

**1. El correo de resumen, hoy mismo.** Es la herramienta más eficaz y casi nadie la usa:

> Asunto: Resumen de nuestra conversación sobre mi salario
>
> Hola, Carlos:
>
> Gracias por la reunión de ayer. Para que lo tengamos los dos igual:
>
> - Estamos de acuerdo en que mi puesto ha crecido (soporte a tres sistemas, formación de tres personas, reducción del tiempo de resolución).
> - La subida a 44 000 no entra en el presupuesto de este año.
> - Se revisará en el presupuesto de 2026.
>
> ¿Podemos fijar la revisión en enero, con esa cifra como referencia, y dejarlo reflejado en mi evaluación de fin de año?
>
> Un saludo,
> Diego

Si responde «sí», tienes un compromiso documentado. Si no responde o matiza, ya sabes cuánto vale el «año que viene».

**2. Lo que pides mientras tanto.** Si no hay dinero fijo, suele haber otras cosas, y cada una es un reconocimiento que luego cuesta negar:

- Un **bono único** o un ajuste parcial ahora (a veces hay partida para variable aunque no para fijo).
- El **cambio de título** a lo que de verdad haces (p. ej., «técnico sénior» o «responsable de soporte»). Cuesta cero y fija tu posición para la próxima negociación.
- **Formación o certificación** pagada, días adicionales, teletrabajo.
- Una **revisión intermedia** a los tres meses, aunque sea solo para confirmar que el plan sigue.

Pide una o dos, no la lista entera.

**3. Tu plazo interno.** Pon una fecha en tu calendario: la de la revisión prometida. Si llega y no hay subida ni explicación concreta, el «no hay presupuesto» era un no. Entonces es cuando mirar el mercado deja de ser una amenaza y pasa a ser una decisión. No la anuncies; tómala.

**4. Cómo distinguir un «no» real de uno disfrazado:**

| Señal | Probablemente real | Probablemente evasiva |
|---|---|---|
| Fecha | «En el ciclo de enero» | «Más adelante», «cuando mejoren las cosas» |
| Cifra | «Te puedo garantizar un 8 %, el resto se verá» | Ninguna |
| Alternativas | Ofrece algo ahora sin que lo pidas | Nada hasta que insistes |
| Correo de resumen | Lo confirma | Lo ignora o lo suaviza |

Verificación: si en dos semanas tienes un correo con fecha y cifra, has ganado la negociación aunque el dinero llegue en enero. Si no lo tienes, has obtenido la información que necesitabas, y eso también es un resultado.""",
            },
        ]
    },
    # 5) Responder a una reseña negativa pública.
    {
        "messages": [
            {"role": "user", "content": "Tengo un restaurante y me dejaron esta reseña en Google: «Esperamos 50 minutos por un plato frío y el camarero ni se disculpó. 2 estrellas por el postre». Quiero contestar en público, pero sin pelearme ni parecer servil."},
            {
                "role": "assistant",
                "content": """Tu respuesta no es para esa persona: es para las doscientas que leerán la reseña antes de decidir si reservan. Ellas no buscan que tengas razón; buscan saber qué pasa cuando algo sale mal en tu restaurante.

Respuesta:

---

Hola, Marcos. Cincuenta minutos de espera y un plato frío no es lo que servimos, y que nadie se disculpara en la mesa es lo que más me molesta de lo que cuentas. Ese sábado abrimos con dos personas menos en cocina y la sala no avisó a las mesas; lo hemos hablado con el equipo y, desde esta semana, si un plato va a tardar más de 25 minutos, se avisa y se invita a la bebida.

Me alegra lo del postre: la tarta es de Marta, que lleva diez años con nosotros.

Si quieres darnos otra oportunidad, escríbeme a reservas con tu nombre y te guardo mesa yo mismo. Y si no, gracias por contárnoslo; nos sirve.

Andrés, propietario

---

Lo que hace cada parte:

1. **Repite los hechos concretos de la queja** (50 minutos, plato frío, sin disculpa) en vez de «sentimos que su experiencia no haya sido la esperada». Esa frase es la más leída de Google y significa «no lo hemos leído». Repetir sus palabras demuestra lo contrario.
2. **Una causa en media frase y sin excusas.** «Dos personas menos en cocina» es un dato. Si te extiendes, parece justificación. Y fíjate en que la causa no exime a la sala: el fallo que reconoces del todo es el de no avisar.
3. **Un cambio concreto y comprobable.** «Si tarda más de 25 minutos, se avisa y se invita a la bebida» es algo que el siguiente cliente puede verificar en su mesa. Es lo único de la respuesta que cambia la opinión del lector; sin esto, el resto es palabrería.
4. **Acepta lo positivo sin agarrarte a ello.** Una línea sobre el postre, con nombre propio, humaniza. Dos líneas serían ya «mira qué bueno es nuestro postre».
5. **Invitación con un canal real y una persona.** «Escríbeme a reservas y te guardo mesa yo mismo» frente a «contáctenos para resolver su incidencia». La primera es una oferta; la segunda, un trámite.
6. **Cierra aceptando que no vuelva.** «Y si no, gracias» quita presión y es lo que hace que no parezca servil: no estás pidiendo que cambie la reseña.

Lo que no debes escribir: que ese día estaba lleno (todos los restaurantes lo están los sábados), que «normalmente no pasa», que otros clientes salieron contentos, o cualquier pregunta que ponga en duda su versión («¿está seguro de que fueron 50 minutos?»). Y nunca pidas que la modifique.

Longitud: la mía tiene unas 130 palabras. Más de 150 en una respuesta a reseña se lee como que te ha dolido.

Verificación: léela como un desconocido que busca sitio para cenar el sábado. ¿Qué saca? Que si tarda, le avisan y le invitan a la bebida, y que el dueño contesta con nombre. Eso vale más que la reseña de dos estrellas.""",
            },
        ]
    },
    # 6) Responder a un comentario agresivo en una revisión de código.
    {
        "messages": [
            {"role": "user", "content": "Un compañero senior me dejó este comentario en mi PR: «Esto es una chapuza, ¿has probado siquiera a ejecutarlo? Vuelve a hacerlo entero». Tiene razón en que había un bug, pero el tono me parece fuera de lugar. ¿Cómo respondo sin empezar una guerra?"},
            {
                "role": "assistant",
                "content": """Separa las dos cosas que vienen mezcladas en ese comentario: el **contenido** (hay un bug, y quizá un problema de enfoque) y el **tono** (agresivo y público). Se responden en sitios distintos y en momentos distintos.

**1. El contenido, en el PR, hoy.** Público, breve, orientado a la tarea:

> Tienes razón: el cálculo de `total` ignoraba los pedidos con descuento, y no lo cubrí con un test. Lo arreglo y añado el caso.
>
> Sobre «rehacerlo entero»: ¿te refieres a la estructura de `OrderService` o solo a este método? Si es lo primero, prefiero que lo veamos 20 minutos en una llamada antes de reescribir, para no volver a traerte algo que no encaje.

Qué consigue:
- Reconoce el bug concreto sin genérico («tienes razón en todo») ni defensa.
- Ignora por completo el «chapuza» y el «¿has probado siquiera?». No se contesta a un insulto; se contesta al problema.
- Convierte «vuelve a hacerlo entero», que es una orden vaga, en una pregunta técnica precisa. O concreta lo que quiere, o reconoce que solo era el método. Las dos salidas son buenas para ti.
- Propone una llamada: lo saca del canal escrito, donde el tono escala.

**2. El tono, en privado, mañana.** Si es la primera vez, puedes dejarlo pasar: un senior con un mal día no es un patrón. Si ya ha ocurrido antes, o si el comentario lo han leído otros, un mensaje directo corto:

> Oye, sobre el comentario de ayer en el PR: el bug era real y ya está corregido, pero el «chapuza» y el «¿has probado siquiera?» no me ayudaron a arreglarlo, y lo leyó todo el equipo. Te lo digo porque prefiero que me revises tú a que no me revise nadie; solo te pido que la próxima vez vaya el qué sin el adjetivo.

Reglas de ese mensaje: una frase de hecho, una de efecto, una de petición. Sin «me sentí atacado» (es cierto, pero le da un argumento de «eres muy sensible»), sin disculparte por el bug otra vez, y reconociendo lo que vale su revisión, porque es verdad y porque es lo que hace que escuche.

**3. Lo que no haces:**
- Responder con el mismo tono («pues tú el mes pasado»). Pierdes aunque tengas razón.
- Responder en público al tono («no hace falta ponerse así»). Lo convierte en un espectáculo.
- Callarte y acumular. La tercera vez explotarás por algo pequeño.
- Escalar al manager antes de hablar con él. Primero directo; al manager solo si se repite tras habérselo dicho.

Verificación de que has acertado: en una semana, mira si el siguiente comentario suyo en un PR tuyo trae el qué sin el adjetivo. Si sí, listo. Si no, ya tienes dos datos para una conversación con tu manager que no será una queja, sino un patrón documentado.""",
            },
        ]
    },
    # 7) Español de España escribiendo a clientes mexicanos.
    {
        "messages": [
            {"role": "user", "content": "Soy de España y voy a llevar la cuenta de un cliente en México. Me han dicho que tenga cuidado con «vosotros» y con «coger». ¿Qué más cambio para no sonar raro, sin ponerme a imitar el acento?"},
            {
                "role": "assistant",
                "content": """Lo de no imitar es el mejor consejo que te han dado: un español escribiendo «ahorita» u «órale» suena a parodia. Lo que sí conviene es quitar lo que en México se lee raro o no se entiende, y ajustar el registro, que allí es un punto más formal.

**1. Gramática: una sola regla.** «Vosotros» no existe en México. Siempre «ustedes», con el verbo en tercera persona del plural: «¿Ustedes tienen acceso?», «les envío», «su equipo». Revisa también los posesivos y los imperativos: «revisad» → «revisen», «vuestro» → «su».

**2. Léxico que cambias sí o sí:**

| Dirías en España | En México | Nota |
|---|---|---|
| ordenador | computadora | «Ordenador» se entiende, pero marca mucho |
| móvil | celular | |
| coger | tomar, agarrar | En México «coger» es vulgar; evita hasta «coger el teléfono» |
| vale | de acuerdo, está bien, ok | «Vale» es la palabra que más delata a un español |
| piso (vivienda) | departamento | |
| coche | carro, auto | |
| conducir | manejar | |
| ir a por | ir por | |
| enfadado | enojado | |
| echar un vistazo | dar un vistazo, revisar | |
| apuntarse | anotarse, inscribirse | |
| curro, currar | trabajo, trabajar | Coloquial; mejor ni en España |
| hostia, joder, coño | (nada) | En un correo de trabajo no los pondrías, pero en una llamada se te pueden escapar |

**3. Registro: un punto más formal y más cortés.** En México, en contexto profesional:
- «Usted» dura más que en España. Con un cliente nuevo, trata de usted hasta que él te tutee; en España pasarías al tú en dos correos.
- Los títulos profesionales se usan: «licenciado Pérez», «ingeniera Ramírez». No estás obligado a usarlos, pero no te extrañes si te llaman «ingeniero».
- Las peticiones se suavizan: «¿Me apoyas con el acceso?» o «¿Sería posible que nos compartieran…?» en vez de «Pásame el acceso». Tu «pásame» directo no es grosero en Madrid; en Ciudad de México suena seco.
- Los saludos y cierres son un poco más largos: «Buen día», «Saludos cordiales», «Quedo atento a sus comentarios». Una línea de cortesía al principio de un correo no es relleno allí; es lo esperado.

**4. Prácticos:** horario (seis o siete horas de diferencia con España según la época), formato de fecha (igual que el vuestro, día/mes/año), moneda (pesos, símbolo $, que no confundas con dólares) y «día festivo» en vez de «fiesta».

**5. Lo que no cambias:** tu forma de hablar en general, el tuteo si te lo ofrecen, las tildes y la ortografía (son las mismas), y tu vocabulario técnico. No te inventes un español neutro de doblaje.

Verificación con un párrafo. Antes: «Vale, cuando cojáis el ordenador nuevo echadle un vistazo al piso de la configuración y me lo pasáis». Después: «De acuerdo. Cuando reciban la computadora nueva, revisen la sección de configuración y me comparten los resultados». Mismo contenido, nada de imitación, y ningún mexicano lo leerá dos veces.""",
            },
        ]
    },
    # 8) Documentación neutra para toda Latinoamérica desde Argentina.
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense."},
            {"role": "user", "content": "Tengo que escribir la documentación de usuario de nuestra app para toda Latinoamérica. Acá escribimos de vos, pero me dicen que ponga «tú» o «usted». ¿Qué conviene? ¿Y qué palabras argentinas evito?"},
            {
                "role": "assistant",
                "content": """Para documentación de usuario que va a toda la región, conviene el **tuteo** («tú», pero sin escribir el pronombre) o la **forma impersonal**. El voseo te lo entienden en todos lados, pero en México, Colombia o Perú se lee como «esta app es argentina», y eso no es lo que querés transmitir en un manual.

**Qué tratamiento elegir:**

| Opción | Cuándo | Ejemplo |
|---|---|---|
| Tuteo | Apps de consumo, tono cercano. Es lo que usan Google, Apple y la mayoría de las apps en es-419 | «Toca el botón y elige una opción» |
| Usted | Banca, salud, gobierno, público mayor | «Toque el botón y elija una opción» |
| Impersonal | Referencias técnicas, pasos largos | «Al tocar el botón se muestran las opciones» |

Elegí una y no la mezcles en el mismo documento. El error más común es empezar en tuteo y, cuando llega la parte de seguridad, pasar a usted sin querer.

**Conjugación: lo que cambia del voseo al tuteo.** Es casi todo en el imperativo y en el presente:

| Voseo | Tuteo |
|---|---|
| ingresá tu correo | ingresa tu correo |
| hacé clic | haz clic |
| tenés que | tienes que |
| podés | puedes |
| elegí | elige |
| fijate | fíjate |
| vení, andá, poné | ven, ve, pon |
| ¿querés guardar? | ¿quieres guardar? |

Ojo con «fíjate», que recupera la tilde en tuteo.

**Léxico argentino que conviene cambiar** (lo que no está en la tabla se entiende en toda la región):

| Argentina | Neutro |
|---|---|
| acá, allá | aquí, allí (aunque «acá» se entiende, «aquí» es el estándar escrito) |
| plata | dinero |
| laburo | trabajo |
| celular | celular (dejalo; «móvil» es de España) |
| computadora | computadora (dejalo; «ordenador» es de España) |
| colectivo, bondi | autobús |
| valija | maleta |
| remera | camiseta |
| pileta | piscina |
| recién (= hace un momento) | hace un momento, recién se entiende pero cambia de sentido en otros países |
| cheto, canchero, bárbaro | (evitalos) |
| ¿viste?, che, dale | (evitalos en texto) |
| subte | metro |
| vereda | acera, banqueta (México); mejor «vereda» o reformulá |
| frutilla, palta, ananá | fresa, aguacate, piña (si aparecen en ejemplos) |

**Dos trampas de pronunciación que no se ven pero afectan la escritura:** «ll» e «y» se escriben igual en todos lados, no hay problema; pero la «s» final que en Buenos Aires se aspira a veces desaparece en textos escritos a mano («lo usuario»). Un pasada con corrector lo detecta.

Verificación con un párrafo real. Antes: «Para empezar, ingresá tu correo y elegí una contraseña. Fijate que tenga al menos ocho caracteres. Si no te acordás, podés recuperarla acá». Después: «Para empezar, ingresa tu correo y elige una contraseña. Asegúrate de que tenga al menos ocho caracteres. Si no la recuerdas, puedes recuperarla aquí». Un usuario de Lima o de Bogotá lo lee como propio.""",
            },
        ]
    },
]

# --- Bloque 2 ---
ROWS += [
    # 9) Léxico colombiano en el chat del equipo.
    {
        "messages": [
            {"role": "user", "content": "Me cambié a un equipo con mayoría de colombianos y en el chat ponen cosas como «¿qué más?», «hágale», «a la orden», «regálame el log», «qué pena contigo», «de una». Entiendo más o menos, pero no quiero meter la pata. ¿Qué significan exactamente y cómo respondo?"},
            {
                "role": "assistant",
                "content": """Ninguna es jerga de pandilla ni requiere respuesta especial: son fórmulas de cortesía y de ritmo de conversación. Entenderlas bien te evita dos errores: leer frialdad donde hay cortesía, y leer confianza donde hay cortesía.

| Expresión | Significado real | Registro | Cómo respondes |
|---|---|---|---|
| ¿Qué más? | Saludo: «¿qué tal?», «¿cómo va?» | Informal, universal en Colombia | «Bien, ¿y tú?» o directamente al tema. No es una pregunta sobre novedades. |
| Hágale | «Adelante», «hazlo», «de acuerdo» | Informal; se usa con «usted» y no implica distancia | Haces lo que ibas a hacer. Equivale a «dale» o «venga». |
| A la orden | «De nada», «a su disposición»; también lo dicen comerciantes al saludar | Cortesía estándar | Si respondes a un «gracias», no hace falta contestar. Si te lo dicen al entrar en una tienda, un «gracias» basta. |
| Regálame el log | «Pásame el log», «¿me mandas el log?» | Cortesía; nadie regala nada | Mandas el log. «Regalar» ahí es un suavizador de la petición, igual que «¿me podrías…?». |
| Qué pena contigo | «Perdona», «disculpa la molestia» | Disculpa suave, muy frecuente | No es vergüenza ni culpa grave. Respondes «tranquilo, no pasa nada» y sigues. Si lo lees como «qué vergüenza», exageras. |
| De una | «Ahora mismo», «sí, sin dudar» | Informal | Es un sí entusiasta. Equivale a «de inmediato» o al «claro, va» mexicano. |
| Listo | «Ok», «hecho», «entendido» | Universal | Cierra turnos: «Listo, te lo mando». |
| Ahorita | Ambiguo: «ahora» o «en un rato» | Igual que en México | Si necesitas plazo, pregunta: «¿en cuánto, más o menos?». |
| Parce, parcero | «Amigo», «colega» | Muy informal, de confianza | Si te lo dicen, es buena señal. No lo uses tú hasta que salga natural. |

Dos cosas estructurales que te van a chocar más que el vocabulario:

1. **El «usted» entre iguales.** En Bogotá y en buena parte del interior, los amigos y los compañeros se tratan de usted con toda naturalidad; no es distancia ni formalidad. Si un compañero te escribe «¿usted ya revisó el PR?», no te está marcando jerarquía. Puedes responder de tú o de usted; ninguna de las dos ofende. En la costa Caribe, en cambio, se tutea más.
2. **La cortesía antes del contenido.** Un mensaje colombiano típico lleva saludo + suavizador + petición: «Buenas, qué pena molestarte, ¿me regalas el log cuando puedas?». Un «mándame el log» a secas, sin saludo, se lee como brusco. No tienes que imitar la fórmula, pero un «hola» antes y un «gracias» después te ponen en el tono.

Cómo respondes sin forzarte: con tu español normal. «Claro, te lo paso ahora», «perfecto», «gracias», «sin problema». Nadie espera que digas «de una» ni «hágale», y si lo fuerzas, se nota. Las fórmulas llegarán solas en unos meses, o no, y da igual.

Lo que sí evitas: «coger» (vulgar en Colombia como en México), «vale» (se entiende, pero marca), «vosotros» (no existe) y el «joder» de muletilla.

Verificación con un intercambio real:

> — Buenas, ¿qué más? Qué pena contigo, ¿me regalas el log del deploy de ayer?
> — Hola. Claro, te lo paso en cinco minutos.
> — Listo, de una. A la orden si necesitas algo.

Tú solo has dicho «hola», «claro» y «te lo paso». Has entendido todo y no has fingido nada.""",
            },
        ]
    },
    # 10) Decir que no a un compañero.
    {
        "messages": [
            {"role": "user", "content": "Un compañero de otro equipo me pide cada semana que le revise cosas «rápidas» que me llevan horas. Quiero decirle que no sin quedar mal. ¿Cómo lo digo?"},
            {
                "role": "assistant",
                "content": """Un no claro queda mejor que un «a ver si puedo» que luego no cumples. La fórmula que funciona tiene tres partes: **reconocer la petición, decir no sin excusa larga, ofrecer una vía acotada**. Y se dice una vez, no cada semana.

**En el chat (la próxima vez que pida):**

> Hola, Pablo. Esta semana no puedo revisarlo: tengo cerrado el calendario con la entrega del viernes. Y te lo digo también para las siguientes: lo que me pasas suele llevarme dos o tres horas y no me entra en el sprint. Si quieres, propónselo a Marta como tarea del equipo y lo planificamos; o, si es algo de media hora como mucho, dímelo y lo miro un jueves por la tarde, que es cuando tengo hueco.

**En persona (si os cruzáis):**

> «Oye, sobre las revisiones: no puedo seguir haciéndolas como favor, me comen medio día cada semana. Si son importantes, que entren por el equipo y las planificamos. Si son dudas rápidas de verdad, los jueves por la tarde tengo rato.»

**Por correo (si lo quieres dejar por escrito o copiar a tu responsable):**

> Asunto: Revisiones del equipo de Datos
>
> Hola, Pablo:
>
> Para ordenar las revisiones que me vas pasando: no puedo asumirlas como favor, porque cada una me lleva entre dos y tres horas que no tengo planificadas. Te propongo dos vías: las que sean importantes, que las pidáis a través de Marta para que entren en nuestro sprint; y para dudas cortas, los jueves de 16:00 a 17:00 tengo hueco.
>
> Un saludo,
> Lucía

Por qué está construido así:

1. **Un dato, no una justificación.** «Me lleva dos o tres horas» es un hecho que él no puede discutir. «Estoy muy liada» es un estado que él puede intentar negociar («pero esto es rapidísimo»).
2. **El «no» cubre el futuro, no solo esta semana.** Si dices «esta semana no», la próxima vuelve. Diciéndolo una vez para todas las siguientes te ahorras repetir la conversación.
3. **Hay una vía oficial y una vía pequeña.** La oficial (pedirlo al equipo) hace que el coste sea visible para quien decide prioridades. La pequeña (jueves por la tarde) demuestra que no es rechazo personal y pone un límite medible.
4. **No pides perdón ni das rodeos.** «Siento mucho no poder», «ojalá pudiera», «sabes que te ayudaría encantada» son frases que invitan a insistir.

Lo que no funciona: «lo intento», «a ver si saco un rato», «quizá la semana que viene». Son síes diferidos; él los escucha como sí.

Y una regla para después: cuando vuelva a pedir fuera de la vía acordada, no lo reabras. Responde con una línea: «Esto pídeselo a Marta como hablamos». La primera vez que cedes, el acuerdo deja de existir.

Verificación: lee tu mensaje y comprueba tres cosas. Que contiene la palabra «no» (no un rodeo). Que da un motivo medible. Que ofrece algo concreto con límite. Si cumple las tres, no queda mal; queda claro.""",
            },
        ]
    },
    # 11) Disentir en una reunión sin sonar grosero (México).
    {
        "messages": [
            {"role": "system", "content": "Responde en español de México, de forma práctica."},
            {"role": "user", "content": "En las juntas me cuesta decir que no estoy de acuerdo sin sonar grosero. Termino callándome y después me arrepiento. Dame frases y un método."},
            {
                "role": "assistant",
                "content": """El método tiene tres pasos y cabe en veinte segundos: **reconoce el punto, pon tu dato, haz una pregunta**. Lo que suena grosero no es disentir; es disentir sin dato o sin dejar salida al otro.

**Los tres pasos:**

1. **Reconoce algo concreto** de lo que dijo (no un «entiendo tu punto» genérico): «Coincido en que hay que salir antes del cierre de trimestre».
2. **Tu dato o tu preocupación**, en primera persona: «Lo que me preocupa es que el módulo de pagos no tiene pruebas de carga; la última vez que salimos sin ellas estuvimos caídos dos horas».
3. **Una pregunta que abra** en vez de cerrar: «¿Qué tal si salimos con pagos en beta cerrada y abrimos el resto?».

Reconocer + dato + pregunta. Si falta el dato, es opinión; si falta la pregunta, es sentencia.

**Frases por intensidad, de más suave a más firme:**

| Nivel | Frase | Cuándo |
|---|---|---|
| Matiz | «Yo lo veo un poco distinto: …» | Desacuerdo parcial |
| Preocupación | «Me preocupa una cosa de ese plan: …» | Quieres que se discuta un riesgo |
| Dato | «Tengo un dato que apunta en otra dirección: …» | Tienes evidencia |
| Desacuerdo | «No estoy de acuerdo con esa parte, y te digo por qué: …» | Es importante y necesitas que conste |
| Freno | «Antes de decidir, necesito que veamos esto: …» | Van a cerrar algo que crees equivocado |

**Para interrumpir** cuando la conversación se va:

- «Perdón que te interrumpa, un dato rápido antes de que avancemos: …»
- «¿Me permites treinta segundos sobre eso antes de pasar al siguiente punto?»

Pides permiso y pones un límite de tiempo; nadie te lo niega.

**Lo que evitas:**

- «Con todo respeto, …»: anuncia que viene lo contrario.
- «No estoy de acuerdo, pero bueno, ustedes deciden»: es una queja disfrazada; deja el desacuerdo sin argumento y te quita de la decisión.
- «Es que siempre pasa lo mismo»: generaliza, y la junta se convierte en defensa.
- Decirlo en el pasillo después. Lo que no se dice en la junta no existe para la decisión.

**Para no callarte:** antes de cada junta anota un solo punto en el que vas a hablar. Uno. No necesitas participar en todo; necesitas no irte con ese punto guardado. Cuando llevas tres o cuatro juntas haciéndolo, el miedo baja porque ya tienes evidencia de que no pasa nada.

Verificación con un diálogo:

> — Entonces salimos el viernes con todo.
> — Coincido en salir el viernes. Me preocupa pagos: no tiene pruebas de carga y la última vez nos costó dos horas de caída. ¿Qué tal si pagos sale en beta cerrada y el resto abierto?
> — Hmm, ¿y cuánto nos retrasa la beta?
> — Nada: es un *flag*. Lo activo el lunes si las pruebas pasan.

Tres frases tuyas, un dato, una propuesta, y la junta sigue sin que nadie se sienta atacado.""",
            },
        ]
    },
    # 12) Charla cotidiana con contenido real: alquilar en Madrid desde Buenos Aires (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Che, me mudo de Buenos Aires a Madrid en marzo por trabajo. ¿Qué tengo que saber para alquilar un departamento allá? Nunca alquilé fuera de Argentina."},
            {
                "role": "assistant",
                "content": """Asumo que llegás con contrato de trabajo español ya firmado; si no, la parte de «solvencia» se complica y te lo marco donde toca.

**1. Vocabulario primero, porque los anuncios lo usan entero:**

| Argentina | España |
|---|---|
| departamento | piso |
| monoambiente | estudio |
| expensas | gastos de comunidad (casi siempre los paga el dueño; preguntá) |
| garante | avalista / aval |
| inmobiliaria | agencia / inmobiliaria |
| depósito | fianza |
| recibo de sueldo | nómina |
| dueño | propietario, arrendador |
| alquiler temporario | alquiler de temporada |

**2. Lo que te van a pedir para firmar:**

- **Fianza**: un mes de alquiler, por ley. Es la garantía legal y el propietario la deposita en el organismo de la comunidad autónoma.
- **Garantía adicional**: la ley permite pedir hasta dos meses más. Es frecuente en Madrid, sobre todo si sos extranjero recién llegado.
- **Documentación**: contrato de trabajo, las últimas nóminas (si recién empezás, la carta de oferta y el contrato), pasaporte y, en cuanto lo tengas, el NIE (número de identidad de extranjero). Sin NIE podés firmar con pasaporte en la mayoría de los casos, pero algunos propietarios lo exigen.
- **Aval bancario o seguro de impago**: lo piden algunos cuando no tenés historial en España. Un seguro de impago lo contrata el propietario; si te piden a vos un aval bancario, cuesta dinero y bloquea plata; preguntá si aceptan el seguro en su lugar.

**3. Lo que dice la ley y conviene que sepas:**

- El contrato de vivienda habitual es de **cinco años** mínimo (siete si el propietario es una empresa), prorrogables; vos podés irte a partir de los seis meses avisando con 30 días. Si el contrato dice un año, igual tenés derecho a las prórrogas.
- Desde 2023, los **honorarios de la agencia** los paga el propietario, no el inquilino. Si te piden «un mes de agencia», ya te cuento qué hacer si te pasa.
- La **actualización anual** del alquiler está limitada por un índice oficial; no pueden subirte lo que quieran.

**4. Cómo buscar:** Idealista y Fotocasa concentran casi todo. Los pisos buenos a precio razonable duran horas, no días: configurá alertas y respondé el mismo día. Pedí ver el piso en persona o por videollamada antes de pagar nada. Nunca transfieras una reserva sin haber visto el piso ni sin un contrato de reserva firmado; las estafas de «estoy en el extranjero, te mando las llaves» son constantes.

**5. Lo práctico después de firmar:** empadronamiento en el ayuntamiento (lo necesitás para casi todo), cambio de titular de luz y gas (a veces lo gestiona la agencia), y revisá que el contrato tenga inventario y fotos del estado del piso, porque de eso depende recuperar la fianza al irte.

**6. Zonas y precios:** Madrid es cara y los precios cambian rápido, así que no te doy cifras; mirá los portales una semana antes de viajar. Como regla, cuanto más cerca de la M-30 (el anillo interior), más caro, y las líneas de metro definen más que el barrio: un piso a cinco minutos de una estación de línea directa a tu trabajo vale más que uno «céntrico» con dos transbordos.

Verificación: hacé esta lista antes de viajar y tildá: contrato de trabajo ✓, nóminas o carta de oferta ✓, pasaporte ✓, cita para el NIE ✓, alertas en los portales ✓, plata para fianza + hasta dos meses de garantía + primer mes ✓. Con eso podés firmar la primera semana.""",
            },
            {"role": "user", "content": "Me piden «dos meses de fianza y un mes de agencia». ¿Es legal eso?"},
            {
                "role": "assistant",
                "content": """Mitad y mitad. Los dos meses pueden ser legales según cómo estén nombrados; el mes de agencia, para un contrato de vivienda habitual, no te lo pueden cobrar a vos.

**«Dos meses de fianza».** La fianza legal es **un** mes. Lo que la ley permite es sumarle una **garantía adicional** de hasta dos meses. Así que «dos meses» es legal si en el contrato figura como «fianza: una mensualidad» + «garantía adicional: una mensualidad». Si figura como «fianza: dos mensualidades», está mal nombrado, aunque el importe total sea el mismo. Pedí que lo desglosen así; importa al final del contrato, porque la fianza se deposita en el organismo oficial y la garantía adicional la retiene el propietario, y los dos te los tienen que devolver.

**«Un mes de agencia».** Desde la Ley por el Derecho a la Vivienda de 2023, los gastos de gestión inmobiliaria y de formalización del contrato de vivienda **son a cargo del arrendador**. Es decir: si la agencia trabaja para el propietario (que es lo normal), sus honorarios se los cobra a él. Algunas agencias lo siguen intentando con extranjeros recién llegados, que no conocen la norma.

Excepciones donde sí podrían cobrarte: si vos contrataste a la agencia para que te buscara piso (entonces trabaja para vos), o si el alquiler es de temporada o de habitación, donde la ley es menos clara. Para un piso completo como vivienda habitual, no.

**Qué hacer, en orden:**

1. Pedí por escrito (correo o WhatsApp) el desglose: «¿Me confirman qué parte es fianza legal, qué parte garantía adicional y en concepto de qué es el mes de agencia?». Que quede escrito.
2. Aceptá fianza + garantía adicional si el piso te conviene.
3. Para el mes de agencia, respondé con la norma: «Según la ley de vivienda de 2023, los honorarios de gestión en alquiler de vivienda habitual corresponden al arrendador, así que ese importe no lo voy a abonar. Si el propietario prefiere no alquilar en esas condiciones, lo entiendo». Sin enojo, sin amenaza.
4. Si insisten, tenés dos caminos: denunciarlo en la oficina de consumo de la comunidad (OMIC o equivalente), que es lo correcto pero lento; o decidir si el piso vale ese mes extra para vos. Hay gente que lo paga para no perder el piso; no es ilegal pagarlo, es ilegal exigirlo.

**Un detalle que te protege:** no pagues nada en efectivo y no pagues nada antes de tener el contrato firmado por las dos partes. Si te piden una «reserva», que sea con un documento firmado que diga que se descuenta de la fianza y qué pasa si el propietario se echa atrás.

Verificación: la cuenta correcta para entrar es 1 (fianza) + hasta 2 (garantía) + 1 (primer mes) = hasta 4 mensualidades. Si te sale 5, el quinto es el que no corresponde. Y esto es la norma general; si el caso se complica, consultalo con la oficina de consumo o un abogado antes de firmar.""",
            },
        ]
    },
    # 13) Entrevista técnica de backend en Python (roleplay, multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Hazme de entrevistador para un puesto de backend en Python (nivel intermedio). Pregúntame una cosa cada vez y evalúa mi respuesta antes de pasar a la siguiente. Empieza."},
            {
                "role": "assistant",
                "content": """Formato: cuatro preguntas, una por bloque (rendimiento, corrección, diseño, operación). Después de cada respuesta tuya te doy evaluación, lo que faltó y la siguiente. Responde como lo harías en una entrevista real: en voz alta, con tus supuestos.

**Pregunta 1 (rendimiento).**

Tienes un endpoint `GET /orders` en una API hecha con FastAPI y SQLAlchemy que devuelve los pedidos de un cliente. Con 10 000 pedidos en la base de datos tarda 3 segundos. Nadie ha tocado ese código en meses y la tabla ha crecido.

Cuéntame cómo lo investigarías y qué sospechas antes de mirar nada.""",
            },
            {"role": "user", "content": "Primero miraría si hay un N+1 con el ORM, porque es lo típico. Luego pondría un índice en la columna por la que filtro, y si sigue lento paginaría la respuesta."},
            {
                "role": "assistant",
                "content": """**Evaluación: intermedio sólido.** Las tres sospechas son las correctas y están en el orden correcto: N+1 es la causa más probable con un ORM, el índice es la segunda y la paginación es la solución estructural cuando el volumen crece. Eso es lo que esperaba oír.

Lo que separa esta respuesta de una de nivel sénior, en tres puntos:

1. **Has saltado a las hipótesis sin medir.** La primera frase de un sénior es «antes de tocar nada, mido». Concretamente: activar el log de consultas de SQLAlchemy (`echo=True` o el logger `sqlalchemy.engine`) y contar cuántas consultas lanza una petición; si son cientos, es N+1 y ya está confirmado en un minuto. Si es una sola consulta lenta, `EXPLAIN ANALYZE` sobre ella te dice si falta índice o si está haciendo un `Seq Scan`. Sin medir, puedes poner un índice que no se usa.
2. **«Un índice en la columna por la que filtro» es vago.** ¿Qué columna? Aquí lo natural es `customer_id`, y si además ordenas por fecha, un índice compuesto `(customer_id, created_at DESC)` cubre filtro y orden en una pasada. Nombrar el índice concreto demuestra que has pensado en la consulta real.
3. **Hay una cuarta causa que no has mencionado: la serialización.** Con 10 000 filas, convertir objetos del ORM a Pydantic y a JSON puede costar más que la consulta. Se detecta con un perfilado rápido (`cProfile` o `py-spy`) y se arregla con paginación, que ya estaba en tu lista, o con `select` de solo las columnas necesarias.

Y un matiz sobre tu paginación: con `OFFSET` el coste crece con el número de página; para listados que se recorren hacia atrás en el tiempo, la paginación por cursor (`WHERE created_at < :last_seen ORDER BY created_at DESC LIMIT 50`) es constante. En una entrevista, mencionar la diferencia suma.

Resumen de lo que diría un sénior en treinta segundos: «Mido primero: número de consultas por petición y `EXPLAIN` de la lenta. Lo más probable es N+1, que arreglo con `selectinload`; si es una consulta, índice en `(customer_id, created_at)`; y en cualquier caso pagino por cursor, porque 10 000 filas en una respuesta no deberían salir».

**Pregunta 2 (corrección).**

Tienes un endpoint `POST /payments` que cobra una tarjeta. El cliente móvil tiene red mala y reintenta la petición si no recibe respuesta en 5 segundos. ¿Cómo garantizas que un pago no se procese dos veces?""",
            },
            {"role": "user", "content": "Guardaría en la base de datos un id de la operación y antes de procesar compruebo si ya existe. Si existe, devuelvo el resultado anterior."},
            {
                "role": "assistant",
                "content": """**Evaluación: correcto en la idea, incompleto en la ejecución.** Has descrito una clave de idempotencia, que es exactamente la solución, y has acertado en devolver el resultado anterior en lugar de un error. Lo que falta es lo que hace que funcione bajo concurrencia, que es justo el caso que plantea la pregunta.

Los huecos, por orden de gravedad:

1. **Condición de carrera entre «compruebo» y «guardo».** Dos reintentos que llegan con 20 ms de diferencia hacen los dos la comprobación, los dos ven que no existe y los dos cobran. «Comprobar y luego insertar» no es atómico. La solución es invertir el orden: **insertar primero** con una restricción `UNIQUE` sobre la clave de idempotencia, y dejar que la base de datos rechace al segundo. En SQL: `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING RETURNING id`; si no devuelve fila, otro lo está procesando o ya lo procesó.
2. **¿De dónde sale el id?** Lo tiene que generar el **cliente** antes del primer intento (un UUID) y enviarlo en todos los reintentos, normalmente en una cabecera `Idempotency-Key`. Si lo genera el servidor, cada reintento es una operación nueva y no hay nada que deduplicar.
3. **Qué devuelves mientras el primero sigue en curso.** El segundo reintento puede llegar cuando el primero aún está esperando a la pasarela de pago. No tienes «resultado anterior» todavía. Opciones: responder `409 Conflict` con «en proceso» para que el cliente reintente más tarde, o bloquear hasta que termine. Lo que no puedes hacer es cobrar otra vez ni devolver «no existe».
4. **Alcance y caducidad de la clave.** La clave debe ser única por cliente (dos clientes distintos pueden generar el mismo UUID por error, improbable pero posible) y puede caducar (24 horas es habitual) para que la tabla no crezca sin límite.
5. **La pasarela también la quieres idempotente.** Stripe y similares aceptan su propia clave de idempotencia; pásales la tuya. Así, si tu servidor muere después de cobrar y antes de guardar el resultado, el reintento contra la pasarela tampoco cobra dos veces.

Versión sénior en treinta segundos: «Clave de idempotencia generada por el cliente, en una cabecera. En el servidor, inserto la clave en una tabla con `UNIQUE` antes de hacer nada; si el insert falla, devuelvo el resultado guardado o un 409 si aún está en curso. La misma clave se la paso a la pasarela. Caducidad de 24 horas».

**Balance tras dos preguntas:** instintos correctos en las dos, y en las dos la diferencia con un sénior está en la misma cosa: pasar de «qué haría» a «qué puede fallar al hacerlo y cómo lo compruebo». Es la pregunta que te conviene hacerte en voz alta antes de responder la tercera.

**Pregunta 3 (diseño).** Te piden añadir a esa API un sistema de notificaciones por correo cuando un pago se completa. El equipo propone enviarlo dentro del mismo endpoint, después de cobrar. ¿Qué opinas y qué harías?""",
            },
        ]
    },
    # 14) Internet explicado a un niño y luego a un ingeniero de redes (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Explícame qué es internet como si tuviera siete años."},
            {
                "role": "assistant",
                "content": """Imagina que todas las computadoras del mundo son casas, y que cada casa tiene su dirección, como la tuya tiene calle y número. Internet son las calles que las unen.

Cuando quieres ver un video, tu tableta escribe una carta: «Hola, casa del video, ¿me mandas el video del gato?». La carta sale por las calles, pasa por muchos cruces, y en cada cruce hay un señor con un mapa que mira la dirección y dice «por aquí». Hasta que llega a la casa del video.

La casa del video no te manda el video entero de golpe, porque no cabe en una carta. Lo corta en trocitos chiquitos, como un rompecabezas, y manda cada pieza en un sobre con tu dirección. Las piezas pueden ir por calles distintas; algunas llegan antes y otras después. Tu tableta las va juntando en orden y, cuando tiene suficientes, empieza a mostrarte el gato. Por eso a veces el video se para un momento: está esperando una pieza que se retrasó.

Lo más raro de internet es que **no es de nadie**. No hay un jefe de internet. Cada ciudad cuida sus calles y las conecta con las de la ciudad de al lado, y así hasta dar la vuelta al mundo. Si una calle se rompe, los señores de los cruces buscan otro camino, y las cartas llegan igual.

Y cuando escribes «youtube.com», tu tableta primero pregunta a una guía telefónica gigante: «¿Cuál es la dirección de youtube.com?». La guía responde con un número larguísimo, y ese número es el que va en el sobre.

Entonces: direcciones, cartas cortadas en piezas, cruces con mapas, y nadie que mande. Eso es internet.

Para comprobar que lo has entendido, respóndeme: si una pieza del rompecabezas se pierde por el camino, ¿qué crees que hace tu tableta? (Pista: puede pedir solo esa pieza otra vez, no el video entero.)""",
            },
            {"role": "user", "content": "Ahora explícamelo como si fuera ingeniero de redes y quisieras convencerme de que entiendes el tema."},
            {
                "role": "assistant",
                "content": """Internet es una federación de redes autónomas que acuerdan intercambiar tráfico IP, y todo lo demás se deriva de tres decisiones de diseño.

**1. Una cintura estrecha: IP.** Lo único que todas las redes tienen que compartir es el formato del datagrama IP y la semántica de *best effort*. Debajo, cada red elige su capa de enlace (Ethernet, fibra con DWDM, 5G, satélite); encima, cada aplicación elige su transporte (TCP, UDP, QUIC) y su protocolo. Esa cintura es lo que permite que una red óptica de 400G y un enlace LoRa participen del mismo sistema sin coordinarse. Es también la razón de que IPv6 lleve treinta años desplegándose: cambiar la cintura obliga a tocar a todos a la vez.

**2. Conmutación de paquetes sin estado en el núcleo.** Los routers no conocen las conexiones: reenvían cada paquete de forma independiente según la tabla de encaminamiento, y la fiabilidad se construye en los extremos (principio *end-to-end*). Eso da robustez frente a fallos de enlace (el encaminamiento converge por otro camino) a cambio de reordenación, pérdida y *jitter*, que TCP o QUIC compensan con números de secuencia, retransmisión y control de congestión. El control de congestión es, de hecho, el mecanismo que impide que internet colapse: cada emisor infiere la capacidad disponible a partir de las pérdidas o del retardo (Reno, CUBIC, BBR) y se autolimita, sin que ningún nodo central reparta nada.

**3. Encaminamiento interdominio por política, no por métrica: BGP.** Internet se compone de unos cien mil sistemas autónomos (AS), cada uno con su número y sus prefijos. Entre ellos, BGP anuncia alcanzabilidad («el prefijo 203.0.113.0/24 se alcanza a través de AS64500, AS64496») y cada AS decide qué rutas acepta, prefiere y reanuncia según sus acuerdos comerciales: *peering* (intercambio gratuito, habitualmente en un IXP) o tránsito (pagas a un proveedor para llegar al resto). Por eso «internet no es de nadie» no es una metáfora: es la propiedad formal de que la política de encaminamiento es local a cada AS y nadie tiene una vista global autoritativa. También es la razón de los secuestros de prefijos y de que RPKI y ROV sean hoy la defensa estándar.

Alrededor de ese núcleo hay dos sistemas que lo hacen usable: **DNS**, una base de datos jerárquica y cacheada que traduce nombres a direcciones (y que es, en la práctica, el mayor punto de fallo compartido), y las **CDN**, que han desplazado la mayor parte del tráfico de contenido a servidores situados dentro o junto a las redes de acceso, de modo que el «internet largo» (tránsito entre continentes) transporta hoy una fracción pequeña de los bytes totales.

Dos tendencias que cambian el dibujo clásico: QUIC sobre UDP, que mueve el transporte al espacio de usuario y cifra las cabeceras para que los *middleboxes* no puedan osificar el protocolo; y la concentración de tráfico en un puñado de hipergigantes que hacen *peering* directo con casi todas las redes de acceso, lo que aplana la jerarquía de tránsito que describían los manuales de los años 2000.

Verificación de coherencia con la versión infantil: «las cartas cortadas en piezas» son datagramas; «los señores de los cruces con mapas» son routers con FIB; «nadie manda» es la autonomía de política en BGP; «la guía telefónica» es DNS; y «pedir solo la pieza perdida» es la retransmisión selectiva (SACK) de TCP. Ningún elemento del cuento era falso; solo estaba sin nombrar.""",
            },
        ]
    },
    # 15) «La nube» para una abuela y para un director de tecnología (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Mi abuela me preguntó qué es «la nube» donde guardo las fotos. ¿Cómo se lo explico?"},
            {
                "role": "assistant",
                "content": """Dile esto, más o menos con estas palabras:

«Abuela, la nube no está en el cielo. Son ordenadores de verdad, miles, metidos en naves enormes que tienen empresas como Google o Apple. Cuando hago una foto, mi móvil la manda por internet a uno de esos ordenadores y allí se guarda una copia. Por eso, si pierdo el móvil, no pierdo las fotos: están allí, y con mi contraseña las vuelvo a bajar a un móvil nuevo.

Es como un guardamuebles: tú tienes la llave, ellos tienen el local. Tus cosas no están en casa, pero son tuyas y las sacas cuando quieres. Se llama "nube" porque en los dibujos de los ingenieros, internet se pintaba como una nube: algo que está ahí y no sabes exactamente dónde.

Lo importante es la llave: la contraseña. Si alguien la consigue, puede entrar en mi guardamuebles. Por eso no la digo a nadie y por eso el móvil a veces me pide un código además.»

Tres preguntas que te va a hacer y qué responder:

- **«¿Y si se les rompe el ordenador a ellos?»** Guardan varias copias en sitios distintos, en ciudades diferentes. Que se pierdan todas a la vez es mucho más difícil que perder el móvil.
- **«¿Y las ven ellos, mis fotos?»** En principio, no: están guardadas de forma que solo se abren con mi llave. Pero sí es verdad que las tienen ellos, y que yo confío en que cumplan. (Si quieres ser honesto: algunas empresas cifran de forma que ni ellas pueden verlas; otras, no.)
- **«¿Y cuánto cuesta?»** Un poco es gratis; si guardas mucho, pagas al mes, como el alquiler del guardamuebles.

Lo que evitas: «servidores», «centro de datos», «sincronizar», «copia de seguridad». Cada una de esas palabras te obliga a explicar otra. «Ordenadores de una empresa», «copia», «llave» y «guardamuebles» las entiende sin preguntar.

Verificación: pídele que te lo explique ella a ti después. Si dice «mis fotos están en unos ordenadores de una empresa y las saco con mi contraseña», lo ha entendido mejor que mucha gente que usa la nube a diario.""",
            },
            {"role": "user", "content": "Y si tuviera que explicárselo a un director de tecnología que está decidiendo si migrar, ¿qué le diría?"},
            {
                "role": "assistant",
                "content": """A un CTO no le explicas qué es la nube; le explicas **qué compra, qué deja de controlar y en qué casos sale a cuenta**. La conversación es sobre una decisión, no sobre un concepto.

**Qué compra.** Capacidad de cómputo, almacenamiento y servicios gestionados por uso, con elasticidad: provisionar en minutos y pagar por lo consumido. El valor real no es «no tener servidores»; es convertir una decisión de capacidad a tres años (comprar hardware) en una decisión reversible a una hora. Eso reduce el coste de equivocarse en la previsión de demanda, que es el coste más alto en productos con crecimiento incierto.

**Qué deja de controlar.** Tres cosas, y conviene nombrarlas:

1. **Responsabilidad compartida.** El proveedor asegura la infraestructura; tú sigues siendo responsable de la configuración, los accesos, los datos y el parcheo de lo que despliegues. La mayoría de las brechas en nube son buckets públicos y credenciales filtradas, no fallos del proveedor.
2. **Dependencia (lock-in).** Cuanto más usas servicios gestionados propietarios (colas, bases de datos serverless, funciones), más barato es operar y más caro es irse. Es un trade-off legítimo, pero hay que elegirlo a sabiendas, no descubrirlo.
3. **Coste de salida de datos.** Sacar datos de la nube se paga por GB; meterlos, no. Afecta a arquitecturas multirregión, a copias externas y a cualquier plan de salida.

**Cuándo compensa y cuándo no:**

| Situación | Probablemente nube | Probablemente propio o colocación |
|---|---|---|
| Demanda | Variable, picos, crecimiento incierto | Estable y predecible |
| Equipo | Pequeño, sin personal de infraestructura | Equipo de sistemas experimentado |
| Cargas | Muchos servicios pequeños, necesidad de servicios gestionados | Pocas cargas grandes y constantes (bases de datos enormes, GPU 24/7) |
| Regulación | Requisitos cubiertos por certificaciones del proveedor | Soberanía de datos estricta o latencia local |
| Horizonte | Necesitas moverte rápido ahora | Ya tienes hardware amortizándose |

La regla que suele sorprender: una carga **constante** durante tres años sale más barata en hardware propio o alquilado en un centro de datos; la nube gana en lo variable y en lo que no sabes dimensionar.

**Cinco preguntas antes de decidir:**

1. ¿Qué porcentaje de nuestra carga es constante y qué porcentaje es pico?
2. ¿Cuánto nos cuesta hoy, de verdad, un servidor, incluyendo a la gente que lo cuida?
3. ¿Qué servicios gestionados usaríamos y cuáles de ellos no tienen equivalente fuera?
4. ¿Quién va a vigilar el gasto mes a mes? (Sin FinOps, la factura crece sola.)
5. ¿Cuál es nuestro plan de salida y cuánto costaría ejecutarlo?

Si las respuestas son «mayormente pico», «no lo sabemos», «muchos», «nadie» y «no hay», la migración tiene sentido, pero las preguntas 4 y 5 hay que resolverlas antes de mover la primera carga.

Verificación de que el mensaje es el correcto para el público: la abuela necesitaba saber dónde están las fotos y quién tiene la llave; el CTO necesita saber qué cuesta la llave, qué pasa si quiere cambiar de guardamuebles y si le compensa seguir teniendo trastero propio. Es la misma metáfora, con la contabilidad incluida.""",
            },
        ]
    },
    # 16) Mismo incidente, dos canales: WhatsApp al compañero y correo al cliente.
    {
        "messages": [
            {"role": "user", "content": "Se cayó el servicio de pagos 40 minutos esta mañana por un certificado caducado. Tengo que avisar a mi compañero de guardia por WhatsApp y al cliente por correo. ¿Me escribes los dos? Quiero ver la diferencia."},
            {
                "role": "assistant",
                "content": """**WhatsApp al compañero de guardia:**

> Pagos ha estado caído de 9:12 a 9:53. Causa: el cert TLS de `api-pagos` caducó anoche a las 00:00 y nadie tenía alerta. Lo he renovado a mano con certbot y he reiniciado nginx; ya responde 200. Pendiente: meter el cert en el renovador automático y una alerta a 14 días de caducidad. Lo apunto en el postmortem, lo vemos a las 12.

**Correo al cliente:**

> **Asunto:** Incidencia en el servicio de pagos, hoy de 9:12 a 9:53 (resuelta)
>
> Estimado señor Navarro:
>
> Le informo de que el servicio de pagos no estuvo disponible hoy entre las 9:12 y las 9:53. Durante ese periodo, los intentos de pago desde su plataforma recibieron un error de conexión y no se procesaron; no se ha cobrado ningún importe de forma incorrecta ni duplicada.
>
> La causa fue un certificado de seguridad caducado en uno de nuestros servidores. Lo renovamos a las 9:53 y el servicio funciona con normalidad desde entonces.
>
> Para que no se repita, hoy mismo incorporamos la renovación automática de ese certificado y una alerta que avisa con dos semanas de antelación. Le enviaré el informe de la incidencia antes del viernes.
>
> Si detecta algún pago de esa franja que no aparezca en su sistema, respóndame a este correo con la referencia y lo revisamos.
>
> Un cordial saludo,
> Elena Ruiz
> Responsable de plataforma

**Lo que cambia entre uno y otro, y por qué:**

| | WhatsApp | Correo |
|---|---|---|
| Lo primero que se dice | La causa técnica | El impacto para él y que ya está resuelto |
| Detalle técnico | Certbot, nginx, nombres de host | «Un certificado de seguridad»: entiende que no es un fallo de su integración, sin más |
| Culpa | «Nadie tenía alerta»: honesto, interno | No se busca culpable; se describe el fallo como del sistema («no se repita») |
| Lo que le importa | Qué está pendiente y cuándo lo vemos | Si perdió dinero, si se cobró dos veces, qué va a pasar ahora |
| Tono | Telegráfico, sin saludo | Formal, con saludo y firma |
| Longitud | 5 líneas | 12 líneas |

Dos cosas que **no** cambian: la honestidad y los datos. Las horas son las mismas en los dos, la causa es la misma, y en ninguno se escribe «problema técnico» a secas. Al cliente se le dice qué pasó en términos que entiende, no se le oculta.

Y una cosa que solo está en el correo: la frase sobre cobros duplicados. Es lo que el cliente va a preguntarse primero, y si no lo dices tú, te lo pregunta él en tono peor. Compruébalo antes de afirmarlo.

Verificación: lee el WhatsApp como si fueras el compañero. ¿Sabes qué hacer a las 12? Sí. Lee el correo como el cliente. ¿Sabes si has perdido dinero, qué pasó y qué viene? Sí, en el primer párrafo.""",
            },
        ]
    },
]

# --- Bloque 3 ---
ROWS += [
    # 17) Correo de seguimiento a un cliente que no responde.
    {
        "messages": [
            {"role": "user", "content": "Le mandé una propuesta a un posible cliente hace 10 días y no contesta. ¿Cómo le escribo para recordárselo sin parecer pesado ni desesperado?"},
            {
                "role": "assistant",
                "content": """Un recordatorio no parece pesado cuando **aporta algo** o **facilita la decisión**; parece pesado cuando solo dice «¿ya lo viste?». Y no parece desesperado cuando da una salida fácil, incluido el no.

> **Asunto:** Re: Propuesta de rediseño del portal (plazos para arrancar en mayo)
>
> Hola, Teresa:
>
> Te escribo por la propuesta que te envié el día 10. Un dato que no estaba y puede ayudarte a decidir: si arrancamos antes del 15 de mayo, el equipo que haría el proyecto es el mismo que hizo el portal de Ibérica, y tendríamos la primera versión navegable para finales de junio. A partir de esa fecha tendríamos que replanificar.
>
> ¿Te viene bien una llamada de 20 minutos esta semana para resolver dudas? Si ahora no es el momento, dímelo y lo retomamos cuando tenga sentido para vosotros.
>
> Un saludo,
> Sergio

Las cinco decisiones:

1. **Responde sobre el hilo original** («Re:») y con un asunto que añade algo. Así tiene la propuesta a un clic, y el asunto le da un motivo para abrirlo.
2. **Aporta un dato nuevo** (el equipo concreto, la fecha límite real). No es un truco de presión: es información que de verdad afecta a la decisión. Si no tienes ningún dato nuevo, búscalo: un caso parecido, la respuesta a una duda que surgió en la reunión, un cambio de alcance que abarata.
3. **Pide algo pequeño y concreto**: 20 minutos, esta semana. «Quedo a la espera de tus comentarios» no pide nada y no genera acción.
4. **Da la salida del no.** «Si ahora no es el momento, dímelo» hace dos cosas: le quita la incomodidad de ignorarte (es más fácil contestar «ahora no» que callar) y te da información. Un «ahora no» con fecha vale más que diez días de silencio.
5. **Seis líneas.** Un recordatorio largo se lee como ansiedad.

Lo que no escribes: «Solo quería hacer seguimiento», «Sé que estás muy ocupada», «¿Has tenido oportunidad de revisarla?», «Disculpa que insista». Las cuatro ponen el foco en ti o se disculpan por existir.

Calendario si sigue sin responder:

- Segundo recordatorio a los 7 días, aún más corto, con otro dato o una pregunta directa: «¿Hay algo en la propuesta que no encaje? Si es el precio o el alcance, prefiero saberlo y ajustar».
- Tercero a los 10 días, el de cierre: «Entiendo que no es el momento. Cierro el tema por mi parte; si más adelante lo retomáis, aquí estoy». Es, con diferencia, el que más respuestas recibe.
- Después, nada. Tres mensajes en un mes es el límite de lo profesional.

Verificación: lee el correo y pregúntate qué gana Teresa leyéndolo. Si la respuesta es «sabe que el equipo de Ibérica haría su proyecto si decide antes del 15», el correo tiene sentido para ella, no solo para ti.""",
            },
        ]
    },
    # 18) Comunicar un retraso a dirección.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Soy PM y tengo que avisar a dirección de que el lanzamiento se retrasa tres semanas por un problema de integración con el proveedor de identidad. ¿Cómo lo comunico?"},
            {
                "role": "assistant",
                "content": """Con la conclusión en la primera línea y una decisión que pedirles. Dirección no quiere la historia; quiere la fecha nueva, qué les cuesta y si tienen que hacer algo.

> **Asunto:** Lanzamiento de la plataforma: nueva fecha 12 de junio (+3 semanas) y decisión pendiente
>
> Hola a todos:
>
> **Resumen.** El lanzamiento pasa del 22 de mayo al 12 de junio. La causa es un fallo en la integración con el proveedor de identidad (el inicio de sesión único) que no podemos resolver solos. Hay una alternativa que permitiría mantener el 22 de mayo con alcance reducido; necesito que decidáis entre las dos antes del viernes.
>
> **Qué ha pasado.** El proveedor cambió el formato de sus tokens en abril sin avisar; nuestra integración, que funcionaba en pruebas, deja de autenticar al 15 % de los usuarios en el entorno real. El proveedor ha reconocido el problema y da una corrección para el 2 de junio; a partir de ahí necesitamos una semana de pruebas.
>
> **Impacto.**
> - Comercial: los tres clientes con fecha comprometida ya están avisados; dos aceptan el 12 de junio y el tercero (Grupo Norte) pide una llamada con vosotros.
> - Coste: tres semanas sin lanzar, unos 40 000 € de ingresos diferidos según la estimación de ventas; sin coste adicional de desarrollo.
>
> **Opciones.**
> 1. **Esperar al 12 de junio** con el producto completo. Riesgo: que el proveedor incumpla su fecha (ya lo ha hecho una vez).
> 2. **Lanzar el 22 de mayo sin inicio de sesión único**, con usuario y contraseña, y activar el SSO cuando llegue la corrección. Riesgo: los dos clientes que exigen SSO por contrato (Grupo Norte y Alcora) no podrían usarlo hasta junio.
>
> Mi recomendación es la opción 2 para todos salvo Grupo Norte y Alcora, que entrarían el 12 de junio.
>
> **Próximo aviso:** el viernes, con la decisión y el calendario cerrado.
>
> Marta López
> Jefa de producto

Reglas que sigue:

1. **La noticia completa en el primer párrafo**: fecha nueva, causa en una frase, y que hay una decisión que tomar. Quien lea solo eso puede actuar.
2. **La causa es un hecho, no un culpable.** «El proveedor cambió el formato sin avisar» es verificable; «el proveedor es poco fiable» es un juicio que te pedirán justificar. Y nada de detalle técnico: «formato de sus tokens» es el máximo; el nombre del campo del JWT no aporta a dirección.
3. **Impacto en lo que miden**: clientes y dinero. Si no tienes cifra, pon una horquilla y de dónde sale.
4. **Opciones con riesgos, y una recomendación.** Sin opciones, el correo es una queja; sin recomendación, les trasladas tu trabajo.
5. **Fecha del siguiente aviso.** Evita que te pregunten a diario.

Lo que no lleva: disculpas, «lamentablemente», cuánto ha trabajado el equipo ni el historial del proyecto. Y nada de «como ya sabéis»: si lo sabían, sobra; si no, les molesta.

Verificación: tapa todo salvo el primer párrafo. ¿Un director sabe la fecha nueva, el motivo y qué le toca hacer? Sí. Ese es el test que tiene que pasar cualquier correo de malas noticias.""",
            },
        ]
    },
    # 19) Disculparse por un error propio sin drama ni excusa.
    {
        "messages": [
            {"role": "user", "content": "Borré por error una tabla en staging y el equipo de QA perdió medio día. Ya está restaurada. ¿Cómo pido disculpas sin que suene ni a drama ni a excusa?"},
            {
                "role": "assistant",
                "content": """Hechos, impacto, lo que ya has hecho, lo que cambia, y una sola disculpa. En ese orden y en el canal del equipo, no en privado a cada uno.

> Hola a todos, en especial al equipo de QA:
>
> Esta mañana a las 10:20 borré la tabla `orders` de staging. Fue un `DROP TABLE` que lancé pensando que estaba conectado a mi base local. QA no pudo ejecutar la regresión hasta las 14:40, cuando terminé de restaurarla desde la copia de las 6:00; los datos de prueba creados entre las 6:00 y las 10:20 se han perdido y hay que recrearlos (ya he regenerado los 40 pedidos del escenario base; faltan los de devoluciones).
>
> Lo siento; os ha costado medio día.
>
> Para que no vuelva a pasar, ni a mí ni a nadie:
> - He pedido a infra que el usuario de staging que usamos a mano no tenga permiso de `DROP` (PR 412, pendiente de revisar).
> - He puesto un *prompt* de color distinto en mi terminal para cada entorno; es rudimentario, pero evita exactamente este error.
> - Propongo que la copia de staging pase de diaria a cada 4 horas; el coste es mínimo y reduce lo que se pierde en casos así.
>
> Si a alguien le falta algún dato de prueba que no haya regenerado, decídmelo y lo hago yo.
>
> Diego

Por qué cada parte:

1. **Hecho con hora y comando.** «Borré la tabla» en voz activa y en primera persona. Nada de «se borró» ni «hubo un incidente con la tabla». La voz pasiva es lo que suena a excusa.
2. **Impacto medido**: cuánto tiempo, qué datos, qué queda por recuperar. Es lo que QA necesita para planificar su tarde; la disculpa no les devuelve el tiempo, el estado sí.
3. **Una disculpa, en una línea, sin adjetivos.** «Lo siento; os ha costado medio día» reconoce el coste concreto. «Lo siento muchísimo, me siento fatal, no sé cómo ha podido pasar» traslada la atención a ti y obliga a los demás a consolarte.
4. **Cambios sistémicos, no promesas.** «No volverá a pasar» no vale nada. «El usuario ya no tiene permiso de DROP» sí. De las tres medidas, dos quitan la posibilidad del error a cualquiera, no solo a ti; eso convierte tu fallo en una mejora para el equipo.
5. **Ofrece el trabajo restante.** Terminar de limpiar lo tuyo es parte de la disculpa.

Lo que no escribes: «fue sin querer» (evidente), «estaba con mucha presión» (excusa), «el entorno es confuso» (excusa, aunque sea verdad; la conviertes en la medida 2 y queda mejor), ni «si alguien tiene algún problema conmigo» (drama).

Verificación: cuenta las frases del mensaje que hablan de ti y de cómo te sientes. Debería haber una (la disculpa). Las demás hablan del equipo, del estado y del sistema. Esa proporción es lo que distingue una disculpa profesional de una emocional.""",
            },
        ]
    },
    # 20) Responder en español a un reclutador (usuario en inglés, nivel intermedio).
    {
        "messages": [
            {"role": "user", "content": "A recruiter from a company in Barcelona messaged me on LinkedIn in Spanish. I'm interested, but my Spanish is intermediate and I don't want to commit to a Spanish-only interview yet. How do I reply? Give me the Spanish text and tell me what each part does."},
            {
                "role": "assistant",
                "content": """Reply in Spanish, keep it short, and be upfront about your level in the second sentence. Recruiters in Spain are used to mixed-language teams; what they can't handle is finding out at the interview.

Assuming the recruiter wrote in *tú* (standard on LinkedIn in Spain) and is called Clara:

> Hola, Clara:
>
> Gracias por el mensaje; el puesto me interesa. Una aclaración antes de seguir: mi español es de nivel intermedio. Lo leo y lo escribo sin problema, pero en una entrevista técnica me expreso mejor en inglés.
>
> ¿El equipo trabaja en español, en inglés o en ambos? Si os encaja, podemos hacer una primera llamada en inglés, o mezclando, y vemos si tiene sentido continuar.
>
> Tengo disponibilidad el martes y el jueves por la tarde.
>
> Un saludo,
> James

What each part does:

| Part | Function |
|---|---|
| «Hola, Clara:» | Mirrors her register. Comma after «Hola» and a colon after the name is the standard Spanish opening. If she wrote «Estimado James», reply «Estimada Clara:» instead. |
| «Gracias por el mensaje; el puesto me interesa.» | Interest first, in one line. Spanish business writing doesn't need a warm-up paragraph. |
| «Una aclaración antes de seguir: mi español es de nivel intermedio.» | The disclosure, framed as a clarification, not an apology. «Antes de seguir» signals you are saving her time. |
| «Lo leo y lo escribo sin problema, pero en una entrevista técnica me expreso mejor en inglés.» | Precise about what works and what doesn't. Recruiters can act on this; «my Spanish isn't great» they can't. |
| «¿El equipo trabaja en español, en inglés o en ambos?» | The question that decides whether this is viable. Many Barcelona tech teams run in English internally and Spanish socially. |
| «Si os encaja, podemos hacer una primera llamada en inglés, o mezclando» | A concrete proposal with an easy yes. «Os» (to you, plural) refers to her and the company; it's the natural form in Spain. |
| «Tengo disponibilidad el martes y el jueves por la tarde.» | Specific slots move things forward instead of «let me know when works». |
| «Un saludo,» | Neutral, standard closing between *tú*-level professionals. «Saludos cordiales» is a notch more formal; «Un abrazo» is for people you know. |

Three things to avoid:

- Don't write the whole reply in English «to be safe». She wrote in Spanish; answering in English without comment reads as either rude or as hiding your level.
- Don't over-apologize («perdón por mi español», «disculpa los errores»). Intermediate Spanish with a clear message is a strength in her eyes, not a flaw.
- Don't let a translation tool produce a flawless, formal paragraph. If your written Spanish suddenly reads like a native lawyer's, the gap at the interview will be worse.

Verification: before sending, check her message for two things and mirror them: whether she used *tú* or *usted* (look for «tu perfil» vs «su perfil»), and whether she signed with her first name only. Match both.""",
            },
        ]
    },
    # 21) tú/usted, «Estimado»/«Hola» y cierres por país (en inglés).
    {
        "messages": [
            {"role": "system", "content": "Answer in English."},
            {"role": "user", "content": "I write to Spanish-speaking partners in Spain, Mexico and Argentina. When do I use tú vs usted, 'Estimado' vs 'Hola', and how do I close? I keep getting conflicting advice."},
            {
                "role": "assistant",
                "content": """The advice conflicts because the three countries genuinely differ. One rule works everywhere, though: **mirror what they do, and start one notch more formal than you think you need.**

**Address forms by country, in business writing:**

| | Spain | Mexico | Argentina |
|---|---|---|---|
| First contact | *usted*, though *tú* is acceptable in tech and startups | *usted*, almost always | *usted* |
| After they switch | Spain switches to *tú* fast, often in the second email | Mexico keeps *usted* longer, especially toward anyone senior or a client | Argentina switches to *vos* informally; in writing to a foreigner they'll often use *tú* or stay on *usted* |
| What you use once they relax | *tú* | *tú* if they used it first; otherwise stay on *usted* | *tú* is fine; don't attempt *vos* unless you can conjugate it (tenés, podés, querés) |

The practical signal: look at their verbs and possessives. «Su propuesta», «le envío», «puede» → *usted*. «Tu propuesta», «te envío», «puedes» → *tú*. «Tenés», «podés», «te mando» → *vos* (Argentina). Reply in the same form.

**Openings:**

| Opening | Register | Use |
|---|---|---|
| Estimado señor García: / Estimada señora López: | Formal | First contact, anyone senior, Mexico by default |
| Estimado Carlos: | Formal-friendly | First contact when you know the first name and the culture is relaxed |
| Buenos días, Carlos: / Buenas tardes: | Neutral, very common in Mexico | Safe middle ground everywhere |
| Hola, Carlos: | Informal | Once you're on *tú*; standard in Spain and Argentina after the first exchange |
| Querido/a | Affectionate | Not for business; it reads as «dear friend», not «Dear Sir» |
| A quien corresponda: | Impersonal | Only when you truly don't know the recipient |

Note the punctuation: a **colon** after the greeting, not a comma. «Hola, Carlos:» with the comma before the name (vocative) and the colon after it.

**Closings:**

| Closing | Register |
|---|---|
| Atentamente, | Formal; slightly stiff in Spain, standard in Mexico |
| Saludos cordiales, | Formal-neutral, works in all three |
| Un cordial saludo, | Same, common in Spain |
| Un saludo, | Neutral-informal; the default in Spain once on *tú* |
| Saludos, | Informal, fine between colleagues |
| Un abrazo, | Warm; only with people you have met and like. Common in Argentina and Mexico between established contacts |
| Quedo atento/a a sus comentarios, | Mexican formula before the closing; signals «awaiting your reply» politely |

**Two mistakes that cost more than they seem:**

1. Switching to *tú* before they do, in Mexico. It reads as presumptuous, especially if they are older or on the client side.
2. Staying on *usted* long after a Spaniard has moved to *tú*. It reads as cold, as if you were keeping them at a distance.

Verification with a realistic sequence. First email to a Mexican client: «Estimada licenciada Ramírez: … Saludos cordiales». She replies «Hola, Mark, gracias por tu correo…». Your second email: «Hola, Patricia: … Un saludo». You have mirrored her switch to *tú* and her first-name use, and dropped the title because she did. That is the whole method.""",
            },
        ]
    },
    # 22) Usuario en inglés pide respuesta en español: la charla previa a las reuniones.
    {
        "messages": [
            {"role": "user", "content": "Answer in Spanish please, I need the practice. I just joined a team in Madrid and before every meeting there's 5 minutes of chat I don't know how to join. In my country we start the meeting on time and that's it. What do people talk about and how do I take part without being awkward?"},
            {
                "role": "assistant",
                "content": """Esos cinco minutos no son un retraso: son parte de la reunión. En España (y en la mayoría de Latinoamérica) la conversación previa establece que sois personas antes de ser roles, y quien la salta se lee como frío, no como eficiente.

**De qué se habla.** Temas seguros, por frecuencia:

1. **El fin de semana o el plan de la tarde.** «¿Qué tal el finde?» es la pregunta por defecto los lunes y martes; «¿Algún plan?» los jueves y viernes. No esperan detalles: «Tranquilo, un poco de monte» basta.
2. **El tiempo.** Más de lo que parece. El calor en verano, la lluvia, el frío repentino. Es un tema sin riesgo que da conversación a cualquiera.
3. **Comida.** Dónde comer, qué cocinaste, un restaurante nuevo. En Madrid es casi un deporte.
4. **Fútbol**, si hay aficionados en el equipo. Si no lo sigues, con «no soy muy de fútbol» se cierra el tema sin problema.
5. **Series, viajes, el tráfico, las obras de la ciudad.** Cualquier cosa compartida y ligera.

**De qué no se habla** en esos cinco minutos, aunque la gente parezca muy abierta: salario, política y religión (con compañeros de confianza sí, pero no en la previa de una reunión), problemas de salud de otros, y críticas a alguien que no está.

**Cómo entrar sin forzarlo.** Tres herramientas:

- **La pregunta de rebote.** Si alguien dice «qué fin de semana, no he parado», pregúntale: «¿Qué hiciste?». Preguntar es participar; no necesitas contar nada tú.
- **Un dato pequeño sobre ti.** «Este fin de semana fui por primera vez al Retiro» da pie a que te recomienden cosas, y eso les gusta.
- **Lo tuyo de extranjero, con humor.** «En mi país empezaríamos la reunión en punto y me estoy acostumbrando a esto» funciona muy bien: es sincero, da conversación y te quita la presión de fingir.

**Cuánto dura y cómo termina.** De tres a cinco minutos; quien convoca la reunión suele cerrarlo con un «bueno, ¿empezamos?» o «venga, vamos al lío». Tú no tienes que cerrarlo. Si eres tú quien convoca, hazlo igual: deja esos minutos y luego «vale, empecemos».

**Lo que no hace falta:** ser gracioso, hablar mucho, ni saber de fútbol. Un compañero que pregunta, escucha y dice dos frases por reunión está perfectamente integrado.

Verificación con un ejemplo:

> — Qué calor, ¿no? Yo no he dormido nada.
> — Pues sí, y en mi piso no hay aire. ¿Vosotros tenéis en casa?
> — Yo sí, pero el mío es de los antiguos y hace un ruido tremendo.
> — Bueno, ¿empezamos?

Has dicho una frase y una pregunta, y ya estás dentro.""",
            },
        ]
    },
    # 23) tú / usted / vos en la interfaz de una app bancaria para tres países.
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Diseñamos una app de banca que sale en España, México y Argentina. ¿Tuteamos, tratamos de usted o voseamos? Marketing quiere «cercanía», legal quiere «usted»."},
            {
                "role": "assistant",
                "content": """Decide por tipo de texto, no por país, y luego ajusta por país solo donde la gramática o el léxico lo exigen. Marketing y legal tienen razón los dos, pero sobre textos distintos.

**1. Un tratamiento por capa de la app:**

| Capa | Tratamiento | Por qué |
|---|---|---|
| Interfaz (botones, pantallas, mensajes) | **tú** (sin pronombre explícito) | Es lo que usan las apps de banca digital que la gente ya conoce; «usted» en una pantalla suena a cajero de los 90 |
| Notificaciones y correos transaccionales | **tú** | Misma voz que la interfaz; el usuario no debe notar el cambio de canal |
| Mensajes de seguridad y errores graves | **tú**, sin coloquialismos | «No hemos podido completar la transferencia» funciona en tú y es serio |
| Términos, contratos, avisos legales | **usted** o **impersonal** | Legal tiene razón aquí: es el registro del documento, y el usuario lo espera |
| Atención al cliente humana | el que use el cliente | Se refleja, no se impone |

Con esto, marketing tiene la cercanía en el 95 % de lo que ve el usuario y legal tiene su usted en el 5 % que se firma.

**2. Qué cambia por país.** En tuteo, casi nada: «Ingresa tu clave», «Confirma la transferencia», «¿Quieres guardar este contacto?» se leen igual en Madrid, Ciudad de México y Buenos Aires. Lo que cambia es el léxico bancario, no el tratamiento:

| Concepto | España | México | Argentina |
|---|---|---|---|
| identificador de cuenta | IBAN | CLABE | CBU / alias |
| transferencia inmediata | Bizum / transferencia inmediata | SPEI | transferencia inmediata |
| cuenta corriente | cuenta corriente | cuenta de cheques | cuenta corriente |
| ingreso del sueldo | nómina | nómina | sueldo / haberes |
| teléfono | móvil | celular | celular |

Esto sí hay que localizar por país, y pesa mucho más que el tú/vos: una app argentina que pide «el IBAN» pierde al usuario en la primera pantalla.

**3. ¿Voseo para Argentina?** Es la decisión más discutible. A favor: los bancos digitales argentinos vosean, y a un usuario argentino «confirmá» le suena más propio que «confirma». En contra: es una variante más que mantener en cada cadena de texto, con sus propias formas verbales, y el tuteo se acepta sin fricción en Argentina en productos internacionales. Recomendación: lanzar con tuteo en los tres países y, si Argentina tiene equipo propio de contenido, abrir la variante es-AR con voseo en una segunda fase. No es una decisión que haya que tomar antes de salir.

**4. Reglas que evitan los errores típicos:**

- Nunca mezclar tratamientos en una misma pantalla. «Ingresa tu clave» seguido de «Si no recuerda su clave» es el fallo más común y el más visible.
- Sin pronombres explícitos en la interfaz: «Confirma», no «Tú confirmas»; el pronombre sobra y marca.
- Imperativos para acciones, sustantivos para menús: botón «Enviar», menú «Transferencias», mensaje «Envía dinero a tus contactos».
- Una sola pregunta por diálogo y respuesta con verbo: «¿Eliminar este contacto?» → «Eliminar» / «Cancelar», no «Sí» / «No».

Verificación con una pantalla en los tres tratamientos, para que veáis el efecto:

- Tú: «Confirma la transferencia de 500 € a Ana López».
- Usted: «Confirme la transferencia de 500 € a Ana López».
- Vos: «Confirmá la transferencia de 500 € a Ana López».

Las tres son correctas. La segunda es la única que suena a documento; por eso va en el contrato y no en el botón.""",
            },
        ]
    },
]

# --- Bloque 4 ---
ROWS += [
    # 24) Pedir feedback útil a un jefe que solo dice «bien».
    {
        "messages": [
            {"role": "user", "content": "Acabé un proyecto grande y quiero pedirle feedback a mi jefe, pero cuando pregunto «¿qué tal lo hice?» me dice «bien» y ya. ¿Cómo consigo algo útil?"},
            {
                "role": "assistant",
                "content": """«¿Qué tal lo hice?» obliga a tu jefe a evaluar en caliente y a elegir entre halagar o criticar. Elige «bien» porque es la respuesta barata. Para sacar algo útil cambia tres cosas: la pregunta, el momento y lo que haces con la respuesta.

**1. Preguntas que no se pueden responder con «bien».**

- «¿Qué es lo primero que cambiarías si tuviéramos que repetir el proyecto?»
- «¿En qué momento del proyecto te preocupaste más por cómo iba?»
- «De lo que hice, ¿qué te gustaría que repitiera en el siguiente? ¿Y qué no?»
- «¿Qué tendría que haber hecho distinto para que me dieras más alcance en el próximo?»
- «Si tuvieras que explicarle a tu jefa qué aporté yo, ¿qué le dirías?»

Las cinco piden un **ejemplo** o una **comparación**, no una nota. Y la cuarta y la quinta van a lo que de verdad te interesa: qué necesita ver para darte más.

**2. Pídelo con antelación y con tema.** «Me gustaría dedicar diez minutos del 1:1 del jueves a repasar el proyecto: qué repetir y qué cambiar. Te lo digo hoy para que lo pienses». Un jefe al que preguntas de improviso responde de memoria; uno al que has avisado trae dos o tres cosas.

**3. Lleva tú el primer dato.** Empieza con tu propia evaluación: «Creo que la planificación salió bien y que la comunicación con el cliente la llevé tarde: no les avisé del cambio de alcance hasta la semana 4. ¿Lo ves igual?». Dar tu versión primero le quita la incomodidad de criticarte (ya lo has hecho tú) y le da algo concreto con lo que estar de acuerdo o no.

**4. Cuando conteste, no te defiendas.** Pregunta más: «¿Me das un ejemplo?», «¿Cómo lo habrías hecho tú?». Lo primero que digas después de una crítica determina si te vuelve a dar otra. Si justificas, la próxima vez volverá al «bien».

**5. Cierra con una acción y cuéntale el resultado.** «Vale: en el siguiente, aviso al cliente de cualquier cambio en la misma semana». Y cuando lo hagas, díselo en una línea. Es lo que convierte el feedback en hábito para él: ve que sirve.

**6. Si tu jefe no es de los que dan feedback, no insistas solo con él.** Pregunta a quien trabajó contigo de cerca: el cliente, el compañero de otro equipo, la persona de QA. Suelen tener más datos que el jefe y menos filtro.

Guion completo para el 1:1:

> «Quería repasar el proyecto contigo. Mi versión: la planificación y la entrega salieron bien; lo que haría distinto es avisar antes al cliente de los cambios de alcance. ¿Lo ves igual? Y aparte de eso: si repitiéramos el proyecto, ¿qué es lo primero que cambiarías de lo que hice yo?»

Verificación: si de la conversación sales con un ejemplo concreto de algo que cambiar y uno de algo que repetir, has conseguido feedback. Si sales con un adjetivo, repite el intento con la pregunta 4.""",
            },
        ]
    },
    # 25) Un compañero se atribuye tu trabajo: hablarlo con él y con el manager (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Tengo un compañero que se lleva el mérito de mi trabajo en las reuniones. Quiero hablarlo con mi manager en el 1:1, pero no quiero parecer que me quejo o que soy envidioso."},
            {
                "role": "assistant",
                "content": """Dos cosas antes del 1:1: habla primero con él, y lleva hechos, no etiquetas. «Se lleva el mérito» es una interpretación; «el martes presentó el análisis de churn como suyo y lo hice yo» es un hecho. Los managers actúan sobre hechos y se cansan de interpretaciones.

**1. Primero, con él, en privado, el mismo día que ocurra.** Es lo que tu manager te va a preguntar («¿se lo has dicho?»), y a veces basta.

> «Oye, en la reunión de hoy, cuando presentaste el análisis de churn, no quedó claro que lo había hecho yo. Supongo que no fue a propósito, pero para mí importa que se sepa. La próxima vez, ¿lo presento yo, o lo mencionas al menos?»

Da por hecho que no fue intencionado (aunque lo haya sido): le dejas salida y te quedas con la petición concreta.

**2. Si se repite, al manager.** Con esta estructura: hechos con fecha → impacto en el equipo → qué pides.

> «Quiero comentarte algo que ha pasado dos veces. El 12, en la revisión mensual, Pablo presentó el análisis de churn como trabajo suyo; lo hice yo, está en el repositorio con mi nombre. El 26 pasó lo mismo con el panel de retención. Hablé con él después de la primera vez y me dijo que fue un malentendido.
>
> Lo que me preocupa no es el reconocimiento en sí, sino que tú y dirección os estáis haciendo una idea equivocada de quién hace qué, y eso afecta a cómo se reparte el trabajo y a mi evaluación.
>
> Te pido dos cosas: que lo que haga yo lo presente yo en las revisiones, y que en los documentos conste quién lo ha hecho.»

Por qué así:
- **Fechas y evidencia verificable** (el repositorio, los documentos). El manager puede comprobarlo sin fiarse de tu palabra ni de la de Pablo.
- **El impacto está formulado como problema del equipo**, no como agravio tuyo: la información que recibe el manager es incorrecta. Eso no es envidia; es un problema de gestión que le afecta a él.
- **Pides algo que está en su mano** y que no requiere castigar a nadie. A un manager le resulta mucho más fácil «cambiar quién presenta» que «hablar con Pablo».
- **Dices que ya lo hablaste con él.** Demuestra que no has corrido a quejarte.

**3. Lo que no dices:** «siempre hace lo mismo», «todo el mundo lo sabe», «no es la primera vez que la gente se queja de él», ni nada sobre su carácter. En cuanto hablas de la persona en lugar de los hechos, el manager tiene que elegir entre vosotros, y es lo que no quieres.

**4. Y una medida que no depende de nadie:** publica un resumen en el canal del equipo cada vez que termines algo relevante, antes de la reunión. «Terminado el análisis de churn; está en el repositorio, resumen de hallazgos abajo». Es visibilidad preventiva: cuando alguien lo presente, ya hay un registro con tu nombre y fecha.

Verificación: lee lo que vas a decirle al manager y comprueba que podrías leérselo a Pablo delante sin cambiar una palabra. Si hay alguna frase que no le dirías a la cara, quítala: esa es la que suena a queja.""",
            },
            {"role": "user", "content": "Ya hablé con él y dijo que fue un malentendido, pero volvió a pasar esta semana."},
            {
                "role": "assistant",
                "content": """Entonces ya no es un malentendido: es un patrón, y tienes lo que necesitas para el 1:1 sin que parezca una queja: dos hechos, una conversación previa y una repetición.

**Qué cambia respecto al guion anterior:**

1. **Añade la tercera fecha y la conversación de en medio.** La secuencia «ocurrió, lo hablé, me dijo que fue un malentendido, volvió a ocurrir» es lo que convierte tu caso en indiscutible. No necesitas calificarlo; la secuencia lo califica sola.

2. **Lleva la evidencia preparada, pero no la muestres salvo que te la pidan.** Enlaces a los commits, al documento con historial de versiones, al mensaje donde entregaste el trabajo. Tenerla te da seguridad; ponerla sobre la mesa sin que te la pidan parece un expediente.

3. **Pide un cambio de sistema, no una sanción.** Es lo que un manager puede dar y lo que resuelve el problema aunque Pablo no cambie:
   - Los resultados los presenta quien los ha hecho (regla general del equipo, no una excepción para ti).
   - Antes de cada revisión, un resumen escrito con autor por cada entregable.
   - Si Pablo es tu *lead* y presentar es parte de su rol, que al menos atribuya en voz alta: «esto lo ha hecho Marta».

4. **Di cuál sería el resultado que te daría por satisfecho.** «Si en las dos próximas revisiones se presenta así, para mí está resuelto». Le das un criterio de éxito y una fecha, y le quitas la sensación de que esto va a ser un tema eterno.

Guion actualizado:

> «Te comenté lo de las presentaciones hace dos semanas. Después de hablarlo con Pablo, que me dijo que había sido un malentendido, ha vuelto a pasar el jueves con el informe de cohortes. Ya son tres veces en un mes y después de habérselo dicho, así que te lo traigo a ti.
>
> No busco que pase nada con Pablo. Busco que lo que yo entrego lo presente yo, o que quede dicho quién lo ha hecho. Si te parece, lo establecemos como norma del equipo: cada entregable lleva autor en el resumen previo y lo presenta esa persona. Si en las dos próximas revisiones funciona así, para mí está resuelto.»

**Lo que haces en paralelo, sin pedir permiso:** sigue publicando tu resumen con autor antes de cada reunión, y en la próxima revisión, cuando Pablo empiece a presentar tu trabajo, intervén con naturalidad: «Si quieres, lo cuento yo, que lo tengo fresco». Dicho sin tono, delante de todos, es imposible de negar y es perfectamente educado.

**Si el manager no hace nada en un mes:** ya no es un problema con Pablo; es un problema con el manager, y la pregunta deja de ser cómo plantearlo y pasa a ser si quieres seguir en ese equipo. No lo digas en el 1:1; apúntalo para ti.

Verificación de que el planteamiento sigue siendo el correcto: tu guion no contiene ningún adjetivo sobre Pablo ni ninguna frase sobre cómo te sientes, y sí contiene tres fechas, una petición concreta y un criterio de éxito. Eso no es quejarse; es gestionar.""",
            },
        ]
    },
    # 26) Explicarle a la abuela qué hace un ingeniero de datos.
    {
        "messages": [
            {"role": "user", "content": "Soy ingeniero de datos y mi abuela siempre me pregunta en las comidas «¿pero tú qué haces exactamente?». Ayúdame a explicárselo de una forma que no sea «cosas con ordenadores»."},
            {
                "role": "assistant",
                "content": """Dale algo que pueda repetirle a sus amigas. La explicación tiene que caber en dos frases y tener una imagen.

**La versión para la comida:**

«Abuela, ¿sabes que el supermercado apunta todo lo que se vende? Cada compra, en cada tienda, a cada hora. Son millones de apuntes al día y están desordenados, cada tienda a su manera. Mi trabajo es recogerlos todos, limpiarlos y ordenarlos para que los que deciden cuánto pan encargar puedan mirarlos y entenderlos. Yo no decido el pan; yo hago que los números lleguen limpios y a tiempo a quien decide.»

La imagen es lo que importa: **fontanero de la información**. Si quiere una frase corta para contárselo a alguien: «Mi nieto es como un fontanero, pero de datos: hace las tuberías para que la información llegue limpia de un sitio a otro».

**Las tres preguntas que vendrán después, y qué contestar:**

- **«¿Y eso no lo hace el ordenador solo?»** «El ordenador hace lo que yo le digo. Yo escribo las instrucciones: de dónde coger los apuntes, qué hacer si uno está mal, dónde guardarlos. Es como escribir una receta muy larga que la máquina sigue todas las noches.»
- **«¿Y si te equivocas?»** «Pues llegan números malos a quien decide, y encargan pan de más o de menos. Por eso me paso la mitad del tiempo comprobando que las cuentas cuadran.» (Esto le gusta: entiende que es un trabajo de cuidado, no de magia.)
- **«¿Y estás todo el día sentado?»** «Sí, pero hablo mucho con la gente que necesita los números, para saber qué les hace falta. No es solo con la máquina.»

**Lo que evitas:** «pipeline», «base de datos», «SQL», «la nube», «procesar», «ETL». Cada una te obliga a explicar otra. «Apuntes», «recoger», «limpiar», «ordenar», «tuberías» y «receta» las entiende sin preguntar y, más importante, las puede repetir.

**Un truco que funciona:** usa un ejemplo de su vida. Si tu abuela llevaba las cuentas de la casa en una libreta, dile que tú haces lo mismo, pero con las libretas de mil tiendas a la vez, y que tu trabajo es pasarlas a limpio para que otro las sume. Cuanto más cerca de algo que ella ha hecho, menos tiene que imaginar.

Verificación: la semana siguiente, pregúntale a ella qué haces. Si dice «ordenas los números del supermercado para que otros decidan», ya está. Si dice «cosas con ordenadores», prueba con la libreta.""",
            },
        ]
    },
    # 27) Respuesta de soporte a un usuario confundido, sin plantilla.
    {
        "messages": [
            {"role": "user", "content": "Un usuario nos escribió: «No encuentro dónde se cambia la contraseña, he mirado en todos lados, ¿es que no se puede?». No está enfadado, pero se le nota frustrado. ¿Cómo le contesto para que no suene a plantilla?"},
            {
                "role": "assistant",
                "content": """Suena a plantilla cuando empieza con «Gracias por contactarnos» y acaba con «No dude en contactarnos». Suena a persona cuando reconoce en una frase que la opción está escondida, da los pasos sin adornos y ofrece hacerlo por él.

> Hola, Raúl:
>
> Sí se puede, pero está escondido, y no eres el primero que nos lo pregunta. Se cambia desde aquí:
>
> 1. Pulsa en tu nombre, arriba a la derecha.
> 2. En el menú que se abre, entra en «Seguridad» (no en «Perfil», que es donde todo el mundo mira primero).
> 3. Ahí verás «Cambiar contraseña». Te pedirá la actual y la nueva dos veces.
>
> Si prefieres, te mando un enlace para restablecerla directamente y te saltas los pasos: respóndeme con un «sí» y lo envío al momento.
>
> Y tomamos nota: vamos a mover esa opción a «Perfil», que es donde debería estar.
>
> Un saludo,
> Clara

Por qué cada parte:

1. **«Sí se puede, pero está escondido»** responde a su pregunta literal en la primera palabra y le quita la culpa en la primera frase. Lo que frustra no es no encontrar algo; es sospechar que uno es torpe. «No eres el primero» lo deja claro sin decir «no es culpa tuya», que suena condescendiente.
2. **Pasos numerados, uno por acción, con la trampa señalada.** El paréntesis de «no en Perfil» es lo más útil del mensaje: le dice exactamente dónde se equivocó, sin reprochárselo.
3. **Una alternativa que le ahorra trabajo**, con una respuesta de una palabra. Es lo que distingue a quien quiere resolver de quien quiere cerrar el ticket.
4. **Reconoce el problema de diseño.** «Vamos a mover esa opción» convierte su queja en algo útil y le dice que alguien escucha. Solo escríbelo si es verdad; si no, «lo paso al equipo de producto», y pásalo.
5. **Sin «simplemente», sin «como puede ver», sin «solo tiene que».** Esas tres expresiones significan «era fácil y no lo viste», justo lo contrario de lo que quieres transmitir.

Longitud: ocho líneas. Con más de doce en un correo de soporte, el usuario deja de leer antes del paso 3.

Y una cosa interna: registra este ticket como incidencia de usabilidad, no solo como consulta resuelta. Si tres personas preguntan lo mismo, no es un problema de soporte; es un problema de la pantalla.

Verificación: lee el correo quitando el nombre y la firma. Si podría servir para cualquier otro usuario con cualquier otra pregunta, es una plantilla. Este no: habla de «Seguridad», de «Perfil» y de mover la opción. Solo sirve para esta pregunta.""",
            },
        ]
    },
    # 28) Directo vs indirecto: empleado mexicano con jefe español (multiturno).
    {
        "messages": [
            {"role": "user", "content": "Soy mexicano y trabajo con un jefe español. Me dice que mis correos «dan muchas vueltas» y que vaya al grano. Yo siento que los suyos son bruscos. ¿Es cultural? ¿Cómo me adapto sin ser grosero?"},
            {
                "role": "assistant",
                "content": """Es cultural, está muy documentado, y ninguno de los dos está siendo descortés según sus propias reglas. El problema es que cada uno lee al otro con las reglas equivocadas.

**La diferencia en dos líneas.** El español peninsular, en el trabajo, es **directo y de contexto bajo**: la información va al principio, el «no» se dice sin adornos, y las fórmulas de cortesía son pocas y cortas. El español de México es de **contexto más alto**: la relación se cuida antes de entrar en materia, las malas noticias se amortiguan y una petición sin preámbulo se lee como una orden. Lo que tu jefe lee como «vueltas» es, para ti, cortesía básica. Lo que tú lees como brusquedad es, para él, respeto por tu tiempo.

**Cómo adaptar tus correos sin perder tu forma de ser:**

1. **La conclusión en la primera línea.** Lo que en tu versión va al final («por lo anterior, le propongo») lo subes al principio. El resto se queda, pero después.
2. **Una sola línea de cortesía, no tres.** «Buen día, Carlos» y al tema. El «espero que te encuentres bien», el «antes que nada agradezco» y el «quedo atento a tus comentarios» se reducen a uno o desaparecen.
3. **Los condicionales se convierten en afirmaciones.** «Quizás podríamos considerar la posibilidad de» → «Propongo». Para un español, el condicional no suena cortés; suena inseguro.
4. **Las peticiones llevan verbo y fecha.** «Te agradecería mucho si pudieras revisarlo cuando tengas oportunidad» → «¿Puedes revisarlo antes del jueves?». No es grosero; es claro.

Ejemplo, el mismo correo en las dos versiones:

> **Tuyo:** «Hola, Carlos, espero que estés muy bien. Te escribo en relación al reporte de ventas que me solicitaste la semana pasada. Estuve revisando la información y me parece que hay algunos datos que tal vez convendría verificar antes de enviarlo a dirección, en particular los de la región norte, que no coinciden del todo con los del sistema. Si te parece bien, podríamos verlo juntos cuando tengas un espacio. Quedo atento a tus comentarios. Saludos cordiales.»
>
> **Adaptado:** «Hola, Carlos: el reporte de ventas tiene un problema en la región norte: las cifras no coinciden con el sistema (diferencia del 8 %). Prefiero no mandarlo a dirección hasta aclararlo. ¿Lo vemos mañana a las 10? Saludos.»

La segunda versión no es menos educada: saluda, explica, pregunta. Solo tiene la mitad de palabras y la noticia al principio.

**Y una cosa para él.** Esto no tiene por qué ser solo adaptación tuya. Dile, en persona y en una frase: «Te voy a escribir más directo, que ya veo que así lo prefieres; y a mí a veces tus correos me llegan secos, no por nada, es la costumbre de allá». Es una conversación de dos minutos y suele mejorar los dos lados.

Verificación: durante dos semanas, antes de enviar cada correo a tu jefe, lee solo la primera línea. Si esa línea ya dice lo que quieres o pides, está adaptado. Si la primera línea es un saludo largo o un «te escribo en relación a», mueve la conclusión arriba.""",
            },
            {"role": "user", "content": "¿Y cuando le tengo que decir que no a algo que me pide? Eso es lo que más me cuesta."},
            {
                "role": "assistant",
                "content": """Ahí está el riesgo real, y no es que suenes grosero: es que tu «no» mexicano **no lo oiga como un no**. «Déjame checarlo», «voy a ver qué se puede hacer», «lo intento» son, para ti, formas educadas de decir que no es viable. Para un jefe español son un «sí, lo miro», y cuando el jueves no está hecho, el problema es tuyo.

**La fórmula: no + motivo en una frase + alternativa + pregunta.**

> «No puedo tener el informe para el jueves: los datos de la región norte no están cerrados hasta el viernes. Puedo mandarte el jueves todo menos esa región, o el informe completo el lunes. ¿Cuál prefieres?»

Cuatro cosas en tres líneas:

1. **«No puedo» en la primera frase.** Sin «me temo que», sin «desafortunadamente», sin «quisiera, pero». Para él, la cortesía está en no hacerle perder tiempo adivinando.
2. **Un motivo de una frase, que sea un hecho.** No una explicación larga: la explicación larga es lo que él lee como «vueltas», y además suena a excusa.
3. **Dos alternativas concretas.** Esto es lo que mantiene tu cortesía: no le cierras la puerta, le das opciones. Y es lo que a él le gusta: puede decidir.
4. **La pregunta final** le devuelve la decisión. Él decide, tú ejecutas.

Más ejemplos, de los que te cuestan:

| Lo que te sale | Lo que él entiende | Lo que funciona |
|---|---|---|
| «Déjame ver si se puede» | «Sí, lo hará» | «No se puede con el presupuesto actual. Con 2 000 más, sí. ¿Lo pido?» |
| «Lo veo complicado» | «Es difícil, pero lo hará» | «No, no entra en este sprint. Lo meto en el siguiente, ¿te vale?» |
| «Ahorita lo checo» | «Ahora mismo» | «Hoy no llego; mañana a primera hora te digo» |
| «Sí, claro» (sin poder) | «Sí» | «Sí, pero entonces la migración se va a la semana que viene. ¿Qué prefieres?» |

El último es importante: en España, decir «sí» a todo y luego no cumplir se considera peor que decir «no» a tiempo. Un «sí, pero esto se retrasa» es un sí honesto y nadie lo toma a mal.

**Lo que no cambias:** el tono. Puedes decir «no puedo» con «hola», con «gracias» y con una sonrisa en la llamada. La diferencia entre un no cortés y uno brusco no está en si dices «no»; está en si ofreces alternativa y preguntas.

Verificación: la próxima vez que vayas a escribir «déjame ver» o «lo intento», para y pregúntate: «¿De verdad creo que va a salir?». Si la respuesta es no, escribe «no puedo» y añade la alternativa. En dos semanas notarás que él te pide menos cosas imposibles, porque ya se fía de tus síes.""",
            },
        ]
    },
    # 29) Correo en inglés a un proveedor (descuento por volumen), con explicación en español.
    {
        "messages": [
            {"role": "user", "content": "Tengo que pedirle a un proveedor de Estados Unidos un descuento por volumen en la renovación anual de licencias (pasamos de 50 a 120 asientos). Escríbeme el correo en inglés y explícame en español por qué lo planteas así."},
            {
                "role": "assistant",
                "content": """Asumo que hoy pagáis 720 USD por asiento y que la renovación es en marzo; ajusta las cifras.

**El correo:**

> **Subject:** Renewal 2026: pricing for 120 seats
>
> Hi Sarah,
>
> We're planning our renewal for March and we'll be growing from 50 to 120 seats, so I'd like to agree on pricing for the new volume before we sign.
>
> At the current per-seat rate, 120 seats would come to 86,400 USD/year. For a renewal of that size we'd expect a volume tier; our budget assumption is in the range of 600 USD per seat, i.e. 72,000 USD/year.
>
> Two things that might help on your side:
>
> - We can commit to a two-year term if that unlocks a better rate.
> - We can pay the full year upfront rather than quarterly.
>
> We need the renewal approved internally by February 14, so a proposal by February 7 would let us close it in this budget cycle.
>
> Could you send me a quote for 120 seats, with one-year and two-year options?
>
> Thanks,
> Marta Gil
> Head of Engineering, Acme

**Por qué está planteado así:**

1. **El crecimiento es el argumento, y va en la primera frase.** Pasar de 50 a 120 asientos es más del doble de ingresos para ellos; no pides un favor, anuncias una cuenta mayor. El descuento es la consecuencia natural, no una concesión.

2. **Pones tú la primera cifra.** «600 USD por asiento» ancla la negociación. Si no la pones, la pone ella, y será la tarifa de lista. La cifra tiene que ser agresiva pero defendible: aquí es un 17 % por debajo del precio actual, un descuento habitual de volumen en SaaS para ese salto. Y la presentas como «nuestra hipótesis de presupuesto», que suena menos a ultimátum que «queremos pagar X» y te deja margen.

3. **Le das dos cosas que ella puede vender internamente.** Un proveedor concede descuentos cuando obtiene algo que su jefe valore: compromiso a dos años (ingresos previsibles) y pago anticipado (caja). Ofrecerlas tú demuestra buena fe y le facilita el sí; además, decides tú cuál de las dos te cuesta menos.

4. **Hay una fecha, y tiene un motivo.** «Aprobado el 14 de febrero, propuesta el 7» crea urgencia sin amenaza: no dices «o nos vamos», dices «o se queda fuera de este ciclo de presupuesto», que es verdad y ella lo entiende.

5. **La petición final es concreta y fácil de cumplir.** «Un presupuesto con las dos opciones» es un trámite para ella, no una decisión. Las negociaciones avanzan cuando cada correo pide algo pequeño.

6. **Tono.** Directo, sin «I hope this email finds you well» ni «I was wondering if». En correos de negocio en Estados Unidos, el preámbulo largo se lee como inseguridad, igual que en España. Cordial, pero al grano: «Hi Sarah», «Thanks».

**Lo que no hace el correo:** no amenaza con cambiar de proveedor (úsalo solo si es verdad y tienes la alternativa evaluada), no menciona competidores por nombre en el primer intercambio (guárdalo por si la primera oferta es mala) y no se disculpa por pedir.

**Siguiente paso probable:** ella responde con una cifra entre tu ancla y la tarifa actual, por ejemplo 650 USD. Entonces aceptas con una condición pequeña («650 a dos años, con el pago anual en marzo») o pides un extra que no sea precio (formación incluida, más almacenamiento, soporte prioritario). Lo que no haces es volver a pedir 600 sin ofrecer nada nuevo.

Verificación: lee el correo como Sarah. En treinta segundos sabe que la cuenta crece, cuánto esperas pagar, qué puedes ofrecer y cuándo lo necesitas. Tiene todo para pedir aprobación a su jefe sin volver a preguntarte nada.""",
            },
        ]
    },
    # 30) Un mismo anuncio para tres públicos; luego, versión corta para clientes (multiturno).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo que anunciar que migramos el sistema de tickets a una herramienta nueva el 1 de junio. Necesito el mismo aviso para tres públicos: dirección, el equipo técnico y los clientes. ¿Me haces las tres versiones?"},
            {
                "role": "assistant",
                "content": """Asumo que pasáis de Mantis a una herramienta que llamaré Helpdesk Pro, que el histórico no se migra y que el portal de clientes cambia de dirección. Cambia los datos que no encajen.

**1. Dirección** (lo que necesitan: impacto, coste, riesgo, si deben decidir algo)

> **Asunto:** Migración del sistema de tickets el 1 de junio: coste, riesgos y lo que notaréis
>
> El 1 de junio sustituimos Mantis por Helpdesk Pro como sistema de tickets de soporte. No requiere decisión vuestra; os aviso del impacto.
>
> - **Coste:** 18 000 €/año frente a los 11 000 actuales. El retorno está en gestión: estimamos un 20 % menos de tiempo por ticket por la automatización de asignaciones y respuestas, unas 300 horas al año.
> - **Riesgo principal:** la semana del 1 al 5 de junio el tiempo de primera respuesta a clientes puede subir de 4 a 8 horas mientras el equipo se adapta. Los tres clientes con SLA estricto están avisados.
> - **Lo que no cambia:** el canal de correo de soporte y los acuerdos de nivel de servicio.
>
> Próximo aviso: 8 de junio, con las métricas de la primera semana.

**2. Equipo técnico** (lo que necesitan: qué cambia, fechas, qué tienen que hacer)

> **Asunto:** Migración a Helpdesk Pro: calendario y tareas (acción requerida antes del 28 de mayo)
>
> Calendario:
> - 25 de mayo: cuentas creadas; recibiréis la invitación por correo. Entrad y configurad la autenticación en dos pasos ese mismo día.
> - 28 de mayo, 10:00-11:30: formación. Obligatoria para soporte N1 y N2.
> - 31 de mayo, 18:00: Mantis pasa a solo lectura. Lo que esté abierto se migra automáticamente con el mismo número; el histórico cerrado se queda en Mantis en modo consulta durante un año.
> - 1 de junio, 8:00: Helpdesk Pro operativo.
>
> Cambios técnicos:
> - La API de Mantis desaparece. Las integraciones que hay que adaptar: las alertas de monitorización (las abre Sergio, PR antes del 27) y el bot de Slack (Lucía).
> - Los webhooks hacia Jira cambian de formato; la documentación está en el wiki del proyecto, página «Migración tickets».
> - Las plantillas de respuesta hay que recrearlas: cada equipo migra las suyas antes del 30.
>
> Dudas en el canal #migracion-tickets.

**3. Clientes** (lo que necesitan: qué notarán y qué tienen que hacer, que es casi nada)

> **Asunto:** Nuevo portal de soporte a partir del 1 de junio
>
> Hola:
>
> A partir del 1 de junio, el portal donde abres y consultas tus tickets de soporte cambia de dirección. Lo encontrarás en soporte.acme.com, con un diseño nuevo y la misma información.
>
> Qué tienes que hacer: nada ahora. El 31 de mayo recibirás un correo con tus nuevas credenciales de acceso. Tus tickets abiertos conservan su número y su historial.
>
> Lo que no cambia: puedes seguir escribiéndonos a soporte@acme.com como siempre, y los tiempos de respuesta de tu contrato son los mismos.
>
> Si tienes cualquier duda, responde a este correo.
>
> Equipo de soporte de Acme

**Lo que cambia entre versiones y por qué:**

| | Dirección | Técnico | Clientes |
|---|---|---|---|
| Primera línea | Coste y que no hay decisión | Fecha límite de la acción | Qué van a notar |
| Detalle técnico | Ninguno | Todo: API, webhooks, plantillas | Ninguno; ni el nombre de la herramienta |
| Lo que se pide | Nada | Tareas con responsable y fecha | Nada, salvo esperar un correo |
| Tono | Ejecutivo | Operativo | Tranquilizador |
| Longitud | 8 líneas | 15 líneas | 10 líneas |

El error habitual es enviar la versión técnica a todos con el asunto cambiado. Dirección no lee la lista de tareas, y los clientes se asustan con «la API desaparece».

Verificación: en cada versión, tapa todo salvo la primera línea y pregúntate si ese público sabe lo único que le importa. Dirección: cuánto cuesta y si decide algo. Técnico: qué hacer y para cuándo. Cliente: si tiene que hacer algo. Las tres pasan.""",
            },
            {"role": "user", "content": "Los clientes no van a leer tanto. ¿Puedes dejar la de clientes en cinco líneas?"},
            {
                "role": "assistant",
                "content": """> **Asunto:** Nuevo portal de soporte a partir del 1 de junio
>
> Hola:
>
> El 1 de junio el portal de soporte cambia a soporte.acme.com. El 31 de mayo te enviaremos las nuevas credenciales; tus tickets abiertos conservan su número e historial. El correo soporte@acme.com y los tiempos de respuesta de tu contrato siguen igual. No tienes que hacer nada hasta recibir ese correo.
>
> Equipo de soporte de Acme

Cinco líneas, y cada frase responde a una pregunta que el cliente se haría en este orden: ¿qué cambia? (la dirección), ¿qué tengo que hacer? (esperar las credenciales), ¿pierdo algo? (no: mismos tickets), ¿cambia lo que ya uso? (no: mismo correo y SLA), ¿y ahora? (nada).

Lo que quité y por qué no se pierde nada:

- **«Con un diseño nuevo y la misma información».** Lo verá al entrar; anunciarlo no le ayuda a decidir nada.
- **«Si tienes cualquier duda, responde a este correo».** Lo hará igual sin que se lo digas; es una línea de cortesía que en un aviso corto pesa más de lo que aporta.
- **El párrafo de «lo que no cambia» como bloque aparte.** Lo comprimí en una frase dentro del cuerpo, porque es la segunda cosa que más tranquiliza y conviene que esté, pero no necesita encabezado.

Lo que no quité, aunque tentaba: la fecha del correo de credenciales. Sin ella, la pregunta «¿y cuándo me llegan?» se convierte en veinte tickets el 1 de junio.

Una regla para avisos a clientes: una fecha, una acción (o la ausencia explícita de acción) y una garantía de que lo suyo no se pierde. Si el texto tiene esas tres cosas, puede ser tan corto como quieras.

Verificación: léelo en el móvil, sin abrir el correo, solo la vista previa de las dos primeras líneas. «El 1 de junio el portal de soporte cambia a soporte.acme.com. El 31 de mayo te enviaremos las nuevas credenciales». Con eso ya sabe lo esencial aunque no lo abra.""",
            },
        ]
    },
]
