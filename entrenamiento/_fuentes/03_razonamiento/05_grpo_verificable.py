"""GRPO verificable: 40 problemas con una única respuesta comprobable (aritmética, álgebra,
combinatoria, probabilidad, teoría de números, lógica, programación, cambios de base y
sucesiones). Formato alpaca; cada salida es una solución paso a paso en texto plano que
termina en una línea '#### <respuesta>'.
"""

ROWS = [
    # 1) Aritmética con enunciado.
    {
        "instruction": "Ana compra 4 cuadernos a 3,50 € cada uno y 5 bolígrafos a 1,20 € cada uno. Paga con un billete de 50 €. ¿Cuántos euros le devuelven?",
        "input": "",
        "output": """1. Coste de los cuadernos: 4 × 3,50 = 14,00 €.
2. Coste de los bolígrafos: 5 × 1,20 = 6,00 €.
3. Total de la compra: 14,00 + 6,00 = 20,00 €.
4. Cambio: 50,00 − 20,00 = 30,00 €.

Comprobación: lo que paga más lo que le devuelven debe dar el billete: 20 + 30 = 50. Correcto.

#### 30""",
    },
    # 2) Aritmética: trabajo conjunto.
    {
        "instruction": "Un grifo llena un depósito en 6 horas y otro grifo lo llena en 3 horas. Si se abren los dos a la vez con el depósito vacío, ¿cuántos minutos tardan en llenarlo?",
        "input": "",
        "output": """La clave es sumar caudales (fracción del depósito por hora), no tiempos.

1. El primer grifo llena 1/6 del depósito por hora.
2. El segundo llena 1/3 = 2/6 del depósito por hora.
3. Juntos: 1/6 + 2/6 = 3/6 = 1/2 del depósito por hora.
4. Para llenar el depósito entero hacen falta 1 ÷ (1/2) = 2 horas.
5. En minutos: 2 × 60 = 120.

Comprobación: en 2 horas el primero llena 2/6 = 1/3 y el segundo 2/3; 1/3 + 2/3 = 1 depósito completo. Además, el resultado es menor que las 3 horas del grifo más rápido, como debe ser al añadir un segundo grifo.

#### 120""",
    },
    # 3) Porcentajes encadenados (trampa: no vuelve al precio inicial).
    {
        "instruction": "Un artículo cuesta 250 €. Su precio sube un 20 % y, después, el nuevo precio baja un 20 %. ¿Cuál es el precio final en euros?",
        "input": "",
        "output": """La trampa es pensar que +20 % y −20 % se anulan. No se anulan, porque la bajada se aplica sobre un precio mayor.

1. Tras la subida: 250 × 1,20 = 300 €.
2. Tras la bajada: 300 × 0,80 = 240 €.

Comprobación por un segundo camino: los dos cambios equivalen a multiplicar por 1,20 × 0,80 = 0,96, es decir, una bajada neta del 4 %. 250 × 0,96 = 240 €.

#### 240""",
    },
    # 4) Movimiento: alcance.
    {
        "instruction": "Un tren sale de una estación a las 9:00 a 80 km/h. Otro tren sale de la misma estación a las 10:00, por la misma vía y en el mismo sentido, a 120 km/h. ¿A qué hora alcanza el segundo tren al primero? Responde en formato HH:MM.",
        "input": "",
        "output": """1. A las 10:00 el primer tren lleva 1 hora de marcha: 80 km de ventaja.
2. Desde ese momento, el segundo tren recorta la distancia a 120 − 80 = 40 km/h.
3. Tiempo para recortar 80 km: 80 ÷ 40 = 2 horas.
4. Hora del alcance: 10:00 + 2 h = 12:00.

Comprobación: a las 12:00 el primer tren ha viajado 3 horas, 3 × 80 = 240 km; el segundo ha viajado 2 horas, 2 × 120 = 240 km. Están en el mismo punto.

#### 12:00""",
    },
    # 5) Álgebra: ecuación lineal.
    {
        "instruction": "Resuelve la ecuación 3(x − 4) + 2 = 2x + 4.",
        "input": "",
        "output": """1. Desarrollo el paréntesis: 3x − 12 + 2 = 2x + 4.
2. Simplifico el lado izquierdo: 3x − 10 = 2x + 4.
3. Paso las x a la izquierda y los números a la derecha: 3x − 2x = 4 + 10.
4. Por tanto, x = 14.

Comprobación sustituyendo x = 14: lado izquierdo 3(14 − 4) + 2 = 30 + 2 = 32; lado derecho 2 × 14 + 4 = 28 + 4 = 32. Coinciden.

#### 14""",
    },
    # 6) Álgebra: sistema de dos ecuaciones.
    {
        "instruction": "La suma de dos números es 47 y su diferencia es 13. ¿Cuál es el número menor?",
        "input": "",
        "output": """Llamo M al mayor y m al menor.

1. M + m = 47 y M − m = 13.
2. Resto la segunda ecuación de la primera: (M + m) − (M − m) = 47 − 13, es decir, 2m = 34.
3. Por tanto m = 17, y M = 47 − 17 = 30.

Comprobación: 30 + 17 = 47 y 30 − 17 = 13. Las dos condiciones se cumplen y 17 es el menor.

#### 17""",
    },
    # 7) Álgebra: ecuación de segundo grado.
    {
        "instruction": "¿Cuál es la mayor de las soluciones de la ecuación x² − 17x + 60 = 0?",
        "input": "",
        "output": """1. Busco dos números cuyo producto sea 60 y cuya suma sea 17: son 5 y 12. Por tanto, x² − 17x + 60 = (x − 5)(x − 12).
2. Las soluciones son x = 5 y x = 12. La mayor es 12.

Comprobación por la fórmula general: el discriminante es 17² − 4 × 60 = 289 − 240 = 49, su raíz es 7, y x = (17 ± 7) / 2 da 12 y 5. Sustituyendo x = 12: 144 − 204 + 60 = 0.

#### 12""",
    },
    # 8) Álgebra: problema de edades.
    {
        "instruction": "La edad de un padre es hoy el triple que la de su hija. Dentro de 12 años, la edad del padre será el doble que la de la hija. ¿Cuántos años tiene hoy el padre?",
        "input": "",
        "output": """Llamo h a la edad actual de la hija; el padre tiene 3h.

1. Dentro de 12 años: padre 3h + 12, hija h + 12.
2. Condición: 3h + 12 = 2(h + 12) = 2h + 24.
3. Despejo: 3h − 2h = 24 − 12, así que h = 12.
4. El padre tiene hoy 3 × 12 = 36 años.

Comprobación: hoy 36 = 3 × 12. Dentro de 12 años, el padre tendrá 48 y la hija 24, y 48 = 2 × 24.

#### 36""",
    },
    # 9) Combinatoria: permutaciones con repetición.
    {
        "instruction": "¿De cuántas maneras distintas se pueden ordenar las letras de la palabra CASA?",
        "input": "",
        "output": """1. CASA tiene 4 letras, con la A repetida dos veces (C, A, S, A).
2. Si todas fueran distintas habría 4! = 24 ordenaciones.
3. Intercambiar las dos A entre sí no produce una palabra nueva, así que cada ordenación distinta aparece contada 2! = 2 veces.
4. Ordenaciones distintas: 24 ÷ 2 = 12.

Comprobación por un segundo camino: elijo las posiciones de las dos A entre las 4 posibles, C(4, 2) = 6 formas, y coloco C y S en las dos posiciones restantes, 2 formas. Total 6 × 2 = 12.

#### 12""",
    },
    # 10) Combinatoria: combinaciones.
    {
        "instruction": "¿De cuántas formas se puede elegir un comité de 3 personas entre 8 candidatos, si el orden de elección no importa?",
        "input": "",
        "output": """Como el orden no importa, son combinaciones de 8 elementos tomados de 3 en 3.

1. Si el orden importara: 8 × 7 × 6 = 336 formas.
2. Cada comité aparece contado 3! = 6 veces (las ordenaciones de sus 3 miembros).
3. C(8, 3) = 336 ÷ 6 = 56.

Comprobación por simetría: elegir los 3 que entran equivale a elegir los 5 que se quedan fuera, y C(8, 5) = (8 × 7 × 6 × 5 × 4) / (5 × 4 × 3 × 2 × 1) = 6720 / 120 = 56.

#### 56""",
    },
    # 11) Combinatoria: variaciones sin repetición.
    {
        "instruction": "¿Cuántos códigos de 4 dígitos se pueden formar con los dígitos del 0 al 9 si no se puede repetir ningún dígito? El primer dígito puede ser 0.",
        "input": "",
        "output": """Aquí el orden importa (1234 y 4321 son códigos distintos) y no hay repetición.

1. Primer dígito: 10 opciones.
2. Segundo: 9 opciones (todas menos la ya usada).
3. Tercero: 8 opciones.
4. Cuarto: 7 opciones.
5. Total: 10 × 9 × 8 × 7 = 5040.

Comprobación con la fórmula de variaciones: V(10, 4) = 10! / 6! = 3 628 800 / 720 = 5040.

#### 5040""",
    },
    # 12) Combinatoria: caminos en una cuadrícula.
    {
        "instruction": "En una cuadrícula quieres ir del punto (0, 0) al punto (4, 3) moviéndote en cada paso una unidad a la derecha o una unidad hacia arriba. ¿Cuántos caminos distintos hay?",
        "input": "",
        "output": """1. Todo camino tiene exactamente 4 pasos a la derecha (D) y 3 hacia arriba (A): 7 pasos en total.
2. Un camino queda determinado por en qué 3 de los 7 pasos se sube.
3. Número de caminos: C(7, 3) = (7 × 6 × 5) / (3 × 2 × 1) = 210 / 6 = 35.

Comprobación por el otro lado: elegir las 4 posiciones de los pasos D da C(7, 4) = (7 × 6 × 5 × 4) / 24 = 840 / 24 = 35. Mismo resultado, como debe ser.

#### 35""",
    },
    # 13) Probabilidad: suma de dos dados.
    {
        "instruction": "Se lanzan dos dados equilibrados de seis caras. ¿Cuál es la probabilidad de que la suma sea 7? Da la respuesta como fracción irreducible.",
        "input": "",
        "output": """1. Casos posibles: 6 × 6 = 36 pares ordenados, todos igual de probables.
2. Casos favorables (primer dado, segundo dado): (1,6), (2,5), (3,4), (4,3), (5,2), (6,1). Son 6.
3. Probabilidad: 6/36 = 1/6.

Comprobación por un segundo camino: sea cual sea el primer dado, hay exactamente un valor del segundo que completa 7 (el 7 menos el primero, que siempre está entre 1 y 6). Así que la probabilidad es la de acertar ese único valor: 1/6.

#### 1/6""",
    },
    # 14) Probabilidad: extracción sin reposición.
    {
        "instruction": "Una bolsa tiene 5 bolas rojas y 3 azules. Se sacan 2 bolas al azar sin reposición. ¿Cuál es la probabilidad de que las dos sean rojas? Da la respuesta como fracción irreducible.",
        "input": "",
        "output": """1. Probabilidad de que la primera sea roja: 5/8.
2. Si la primera fue roja, quedan 4 rojas de 7 bolas: probabilidad 4/7.
3. Probabilidad de ambas: 5/8 × 4/7 = 20/56 = 5/14.

Comprobación contando combinaciones: hay C(8, 2) = 28 parejas posibles y C(5, 2) = 10 parejas de dos rojas. 10/28 = 5/14.

#### 5/14""",
    },
    # 15) Probabilidad: complementario.
    {
        "instruction": "Se lanzan 3 monedas equilibradas. ¿Cuál es la probabilidad de obtener al menos una cara? Da la respuesta como fracción irreducible.",
        "input": "",
        "output": """«Al menos una» se calcula mejor por el suceso contrario: ninguna cara.

1. Probabilidad de que una moneda salga cruz: 1/2.
2. Probabilidad de tres cruces: (1/2)³ = 1/8.
3. Probabilidad de al menos una cara: 1 − 1/8 = 7/8.

Comprobación enumerando: los 8 resultados posibles son CCC, CCX, CXC, CXX, XCC, XCX, XXC y XXX (C cara, X cruz). Solo XXX no tiene ninguna cara, así que 7 de 8 cumplen.

#### 7/8""",
    },
    # 16) Teoría de números: máximo común divisor.
    {
        "instruction": "¿Cuál es el máximo común divisor de 84 y 126?",
        "input": "",
        "output": """1. Factorizo: 84 = 2² × 3 × 7 y 126 = 2 × 3² × 7.
2. El MCD toma los factores comunes con el menor exponente: 2¹ × 3¹ × 7¹ = 42.

Comprobación con el algoritmo de Euclides: 126 = 1 × 84 + 42; 84 = 2 × 42 + 0. El último resto no nulo es 42. Y efectivamente 84 / 42 = 2 y 126 / 42 = 3, que no tienen divisores comunes.

#### 42""",
    },
    # 17) Teoría de números: mínimo común múltiplo con enunciado.
    {
        "instruction": "Tres semáforos se ponen en verde cada 12, 18 y 30 segundos respectivamente. Ahora mismo los tres acaban de ponerse en verde a la vez. ¿Dentro de cuántos segundos volverán a ponerse en verde los tres a la vez por primera vez?",
        "input": "",
        "output": """Buscan el primer instante que sea múltiplo de los tres periodos: el mínimo común múltiplo.

1. Factorizo: 12 = 2² × 3, 18 = 2 × 3², 30 = 2 × 3 × 5.
2. El mcm toma cada primo con su mayor exponente: 2² × 3² × 5 = 4 × 9 × 5 = 180.

Comprobación: 180 / 12 = 15, 180 / 18 = 10 y 180 / 30 = 6, todos enteros. Y ningún múltiplo menor de 30 sirve: 30 y 90 no son múltiplos de 12, y 60, 120 y 150 no lo son de 18.

#### 180""",
    },
    # 18) Teoría de números: aritmética modular con potencias.
    {
        "instruction": "¿Cuál es el resto de dividir 2^100 entre 17?",
        "input": "",
        "output": """1. Busco una potencia pequeña de 2 con un resto sencillo: 2^4 = 16 = 17 − 1, así que 2^4 deja resto −1 módulo 17.
2. Al cuadrado: 2^8 deja resto (−1)² = 1. Comprobación directa: 2^8 = 256 = 15 × 17 + 1.
3. Divido el exponente: 100 = 8 × 12 + 4. Entonces 2^100 = (2^8)^12 × 2^4, que deja resto 1^12 × 16 = 16.

Comprobación por un segundo camino: 2^100 = (2^4)^25, que deja resto (−1)^25 = −1 módulo 17, es decir, 17 − 1 = 16.

#### 16""",
    },
    # 19) Teoría de números: últimas cifras de una potencia.
    {
        "instruction": "¿Cuáles son las dos últimas cifras de 3 elevado a 2025? Responde con el número de dos cifras.",
        "input": "",
        "output": """Las dos últimas cifras son el resto de dividir entre 100.

1. 3^5 = 243, resto 43 módulo 100.
2. 3^10 = (3^5)², resto 43² = 1849, es decir, 49.
3. 3^20 = (3^10)², resto 49² = 2401, es decir, 01. A partir de aquí el patrón se repite cada 20 exponentes.
4. 2025 = 20 × 101 + 5, así que 3^2025 = (3^20)^101 × 3^5 deja resto 1 × 43 = 43.

Comprobación por dos caminos:
- Módulo 4: 3 deja resto −1, así que 3^2025 deja resto (−1)^2025 = −1, es decir, 3. Y 43 = 4 × 10 + 3. Coincide.
- 3^20 = 3 486 784 401 termina en 01, lo que confirma el paso 3.

#### 43""",
    },
    # 20) Teoría de números: número de divisores.
    {
        "instruction": "¿Cuántos divisores positivos tiene el número 360?",
        "input": "",
        "output": """1. Factorizo: 360 = 8 × 45 = 2³ × 3² × 5.
2. Cada divisor es 2^a × 3^b × 5^c con a entre 0 y 3, b entre 0 y 2 y c entre 0 y 1.
3. Número de divisores: (3 + 1) × (2 + 1) × (1 + 1) = 4 × 3 × 2 = 24.

Comprobación emparejando divisores: como √360 ≈ 18,97 y 360 no es un cuadrado perfecto, cada divisor menor que 18,97 se empareja con uno mayor. Los menores son 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15 y 18: doce. Doce parejas dan 24 divisores.

#### 24""",
    },
    # 21) Teoría de números / combinatoria: inclusión-exclusión.
    {
        "instruction": "¿Cuántos números enteros del 1 al 1000, ambos incluidos, no son divisibles ni por 2, ni por 3, ni por 5?",
        "input": "",
        "output": """Cuento los que son divisibles por al menos uno (inclusión-exclusión) y los resto de 1000.

1. Divisibles por 2: 500. Por 3: 333. Por 5: 200. Suma: 1033.
2. Resto los contados dos veces. Por 6: 166. Por 10: 100. Por 15: 66. Suma: 332.
3. Sumo los divisibles por los tres a la vez, que se restaron de más. Por 30: 33.
4. Divisibles por al menos uno: 1033 − 332 + 33 = 734.
5. Ninguno de los tres: 1000 − 734 = 266.

Comprobación por un segundo camino: en cada bloque de 30 números consecutivos hay exactamente 8 que no son divisibles por 2, 3 ni 5 (los que dejan resto 1, 7, 11, 13, 17, 19, 23 y 29). 1000 = 33 × 30 + 10: los 33 bloques completos aportan 33 × 8 = 264, y en los 10 últimos números (991 a 1000, restos 1 a 10) solo cuentan los de resto 1 y 7: 991 y 997. Total 264 + 2 = 266.

#### 266""",
    },
    # 22) Lógica: día de la semana.
    {
        "instruction": "Hoy es miércoles. ¿Qué día de la semana será dentro de 100 días?",
        "input": "",
        "output": """1. Los días de la semana se repiten cada 7 días, así que solo importa el resto de 100 entre 7.
2. 100 = 7 × 14 + 2: dentro de 98 días volverá a ser miércoles, y faltan 2 días más.
3. Miércoles + 2 días = viernes.

Comprobación: dentro de 98 días es miércoles (14 semanas exactas); el día 99 es jueves y el día 100 es viernes.

#### viernes""",
    },
    # 23) Lógica: calendario.
    {
        "instruction": "El 1 de enero de 2025 fue miércoles. ¿Qué día de la semana fue el 1 de marzo de 2025?",
        "input": "",
        "output": """1. 2025 no es bisiesto (no es divisible por 4), así que febrero tiene 28 días.
2. Del 1 de enero al 1 de marzo hay 31 (enero) + 28 (febrero) = 59 días.
3. 59 = 7 × 8 + 3: el 1 de marzo cae 3 días de la semana después del miércoles.
4. Miércoles + 3 = sábado.

Comprobación por saltos de semanas completas: 29 de enero (miércoles, +28 días), 26 de febrero (miércoles, +28 días); después, 27 de febrero jueves, 28 de febrero viernes y 1 de marzo sábado.

#### sábado""",
    },
    # 24) Lógica / combinatoria: apretones de manos.
    {
        "instruction": "En una reunión hay 5 personas y cada una se da la mano exactamente una vez con cada una de las demás. ¿Cuántos apretones de manos hay en total?",
        "input": "",
        "output": """1. Cada apretón corresponde a una pareja de personas, sin orden.
2. Número de parejas: C(5, 2) = (5 × 4) / 2 = 10.

Comprobación contando en orden: la primera persona estrecha 4 manos nuevas, la segunda 3 (la de la primera ya se contó), la tercera 2, la cuarta 1 y la quinta 0. Total 4 + 3 + 2 + 1 = 10.

#### 10""",
    },
    # 25) Lógica: veraces y mentirosos.
    {
        "instruction": "Ana, Beto y Carla hacen una afirmación cada uno. Exactamente una de las tres personas miente; las otras dos dicen la verdad. Ana dice: «Beto miente». Beto dice: «Carla dice la verdad». Carla dice: «Ana miente». ¿Quién miente? Responde con el nombre.",
        "input": "",
        "output": """Pruebo cada hipótesis y compruebo si deja exactamente un mentiroso.

1. Si miente Ana: entonces Beto dice la verdad, así que Carla dice la verdad, y Carla afirma que Ana miente, lo cual es cierto. La afirmación de Ana («Beto miente») es falsa, como corresponde a una mentirosa. Hay exactamente un mentiroso: consistente.
2. Si miente Beto: Ana dice la verdad (Beto miente, correcto). Pero la afirmación de Beto («Carla dice la verdad») sería falsa, así que Carla también mentiría. Dos mentirosos: imposible.
3. Si miente Carla: su afirmación («Ana miente») es falsa, así que Ana dice la verdad, y entonces Beto miente. Dos mentirosos: imposible.

Solo la primera hipótesis es consistente.

Comprobación: con Ana mintiendo, las afirmaciones de Beto y Carla son ambas verdaderas y la de Ana es falsa; se cumple la condición de un único mentiroso.

#### Ana""",
    },
    # 26) Lógica: ordenación con pistas.
    {
        "instruction": "En una carrera de cinco corredoras no hubo empates. Ana llegó antes que Bea. Bea llegó antes que Diana. Carla llegó después de Diana. Eva llegó la última. ¿Quién llegó en tercer lugar?",
        "input": "",
        "output": """1. Eva fue la última, así que ocupa el puesto 5 y las otras cuatro ocupan los puestos 1 a 4.
2. Las pistas forman una cadena completa: Ana antes que Bea, Bea antes que Diana y Diana antes que Carla.
3. Una cadena de cuatro personas en cuatro puestos solo admite un orden: Ana 1.ª, Bea 2.ª, Diana 3.ª, Carla 4.ª.

Comprobación de las cinco pistas con el orden Ana, Bea, Diana, Carla, Eva: Ana (1) antes que Bea (2); Bea (2) antes que Diana (3); Carla (4) después de Diana (3); Eva (5) la última; sin empates. Todas se cumplen.

#### Diana""",
    },
    # 27) Programación: alias de listas en Python.
    {
        "instruction": """¿Qué imprime este programa en Python?

```python
x = list(range(10))
y = x
y.append(10)
y = y + [11]
print(len(x))
```""",
        "input": "",
        "output": """1. x = list(range(10)) crea una lista con los números del 0 al 9: 10 elementos.
2. y = x no copia la lista: y y x son dos nombres para el mismo objeto.
3. y.append(10) modifica ese objeto compartido: x tiene ahora 11 elementos.
4. y = y + [11] crea una lista nueva (el operador + no modifica la original) y hace que y apunte a ella. x sigue apuntando a la lista anterior, que no cambia.
5. len(x) es 11.

Comprobación: la diferencia está entre mutar (append, que afecta a todos los nombres del mismo objeto) y reasignar (y = ..., que solo cambia a qué apunta y). Si la última línea fuera y += [11], la lista se ampliaría en el sitio y el resultado sería 12; con y = y + [11] es 11.

#### 11""",
    },
    # 28) Programación: contar ejecuciones de un bucle anidado.
    {
        "instruction": """¿Qué imprime este programa en Python?

```python
contador = 0
for i in range(8):
    for j in range(i, 8):
        contador += 1
print(contador)
```""",
        "input": "",
        "output": """1. Para cada i, el bucle interno recorre j desde i hasta 7: son 8 − i iteraciones.
2. i va de 0 a 7, así que las iteraciones son 8, 7, 6, 5, 4, 3, 2 y 1.
3. Suma: 8 + 7 + 6 + 5 + 4 + 3 + 2 + 1 = 36.

Comprobación con la fórmula de la suma de los n primeros naturales: 8 × 9 / 2 = 36. También se puede ver como el número de pares (i, j) con 0 ≤ i ≤ j ≤ 7: C(8, 2) pares con i < j más 8 pares con i = j, es decir, 28 + 8 = 36.

#### 36""",
    },
    # 29) Programación: número de llamadas recursivas.
    {
        "instruction": """Dada esta función en Python:

```python
def f(n):
    if n <= 1:
        return n
    return f(n - 1) + f(n - 2)

resultado = f(5)
```

¿Cuántas veces se llama a la función f en total al ejecutar f(5), contando la llamada inicial?""",
        "input": "",
        "output": """Llamo C(n) al número total de llamadas que produce f(n), incluida ella misma.

1. Casos base: f(0) y f(1) no llaman a nada más, así que C(0) = 1 y C(1) = 1.
2. Para n ≥ 2: C(n) = 1 + C(n − 1) + C(n − 2).
3. C(2) = 1 + 1 + 1 = 3.
4. C(3) = 1 + 3 + 1 = 5.
5. C(4) = 1 + 5 + 3 = 9.
6. C(5) = 1 + 9 + 5 = 15.

Comprobación por un segundo camino: C(n) + 1 cumple la recurrencia de Fibonacci, y C(n) = 2 × F(n + 1) − 1 con F(1) = F(2) = 1. Como F(6) = 8, C(5) = 2 × 8 − 1 = 15.

#### 15""",
    },
    # 30) Programación: complejidad de bucles con duplicación.
    {
        "instruction": """¿Cuál es la complejidad temporal de esta función en notación O, en función de n?

```python
def g(n):
    i = 1
    while i < n:
        for j in range(n):
            pass
        i *= 2
```""",
        "input": "",
        "output": """1. El bucle externo duplica i en cada vuelta: i vale 1, 2, 4, 8, … mientras sea menor que n. Eso son unas log₂(n) vueltas.
2. En cada vuelta externa, el bucle interno hace n iteraciones, independientemente de i.
3. Trabajo total: n × log₂(n), es decir, O(n log n).

Comprobación con un caso concreto: para n = 16, i toma los valores 1, 2, 4 y 8 (4 vueltas = log₂ 16), y cada una hace 16 iteraciones: 64 = 16 × 4. Si se duplica n a 32, las vueltas pasan a 5 y el total a 160, que crece algo más que el doble, como corresponde a n log n.

#### O(n log n)""",
    },
    # 31) Programación: complejidad con bucle interno que se reduce a la mitad (trampa).
    {
        "instruction": """¿Cuál es la complejidad temporal de esta función en notación O, en función de n?

```python
def h(n):
    total = 0
    i = n
    while i > 0:
        for j in range(i):
            total += 1
        i //= 2
    return total
```""",
        "input": "",
        "output": """La trampa es ver dos bucles anidados y un bucle externo de unas log₂(n) vueltas y concluir O(n log n). Hay que mirar cuánto trabaja el bucle interno en cada vuelta, porque no es siempre n.

1. En la primera vuelta el bucle interno hace n iteraciones; en la segunda, n/2; en la tercera, n/4; y así sucesivamente.
2. Trabajo total: n + n/2 + n/4 + … , una serie geométrica de razón 1/2.
3. Esa suma es siempre menor que 2n. Por tanto, el coste es O(n).

Comprobación con n = 16: el bucle interno hace 16 + 8 + 4 + 2 + 1 = 31 iteraciones, menos que 2 × 16 = 32. Con n = 32: 32 + 16 + 8 + 4 + 2 + 1 = 63, menos que 64. Duplicar n duplica el trabajo: crecimiento lineal.

#### O(n)""",
    },
    # 32) Programación: sort por defecto en JavaScript.
    {
        "instruction": """¿Qué imprime este código JavaScript?

```js
console.log([10, 1, 2].sort().join(","));
```""",
        "input": "",
        "output": """1. Array.prototype.sort sin función de comparación convierte cada elemento a cadena y ordena las cadenas por sus unidades de código UTF-16, no por su valor numérico.
2. Las cadenas son "10", "1" y "2".
3. Comparadas como texto: "1" va antes que "10" (es un prefijo suyo), y "10" va antes que "2" (porque el carácter "1" es menor que "2").
4. Orden resultante: 1, 10, 2. Con join(",") se imprime 1,10,2.

Comprobación: con una función de comparación numérica, [10, 1, 2].sort((a, b) => a - b) da 1, 2, 10. La diferencia entre ambos resultados es exactamente el efecto de comparar como texto.

#### 1,10,2""",
    },
    # 33) Programación: módulo con negativos en Python.
    {
        "instruction": """¿Qué imprime este programa en Python?

```python
print((-47) % 30)
```""",
        "input": "",
        "output": """En Python, a % b se define a partir de la división entera hacia abajo (floor): a == (a // b) * b + a % b, y el resto tiene el mismo signo que el divisor.

1. -47 / 30 ≈ -1,57; redondeando hacia abajo, -47 // 30 = -2.
2. Resto: -47 − (-2 × 30) = -47 + 60 = 13.

Comprobación: (-2) × 30 + 13 = -60 + 13 = -47, y 0 ≤ 13 < 30, como exige Python para un divisor positivo. En lenguajes que truncan hacia cero, como C o Java, el resultado sería -17; esa es precisamente la diferencia que el ejercicio pone a prueba.

#### 13""",
    },
    # 34) Cambio de base: binario a decimal.
    {
        "instruction": "Convierte el número binario 10110111 a decimal.",
        "input": "",
        "output": """1. Asigno a cada cifra su peso, de derecha a izquierda: 1, 2, 4, 8, 16, 32, 64 y 128.
2. Cifras de izquierda a derecha: 1 (128), 0 (64), 1 (32), 1 (16), 0 (8), 1 (4), 1 (2), 1 (1).
3. Sumo los pesos de las cifras que valen 1: 128 + 32 + 16 + 4 + 2 + 1 = 183.

Comprobación por hexadecimal: agrupo en bloques de 4 bits, 1011 0111, que son B (11) y 7. B7 en hexadecimal es 11 × 16 + 7 = 176 + 7 = 183.

#### 183""",
    },
    # 35) Cambio de base: decimal a hexadecimal.
    {
        "instruction": "Escribe el número 2024 en base 16 (hexadecimal), usando letras mayúsculas para las cifras mayores que 9.",
        "input": "",
        "output": """Divido sucesivamente entre 16 y guardo los restos.

1. 2024 ÷ 16 = 126, resto 8.
2. 126 ÷ 16 = 7, resto 14, que en hexadecimal es E.
3. 7 ÷ 16 = 0, resto 7.
4. Leo los restos de abajo arriba: 7, E, 8. Resultado: 7E8.

Comprobación: 7 × 256 + 14 × 16 + 8 = 1792 + 224 + 8 = 2024.

#### 7E8""",
    },
    # 36) Cambio de base: decimal a base 3.
    {
        "instruction": "Escribe el número 100 en base 3.",
        "input": "",
        "output": """Divido sucesivamente entre 3 y guardo los restos.

1. 100 ÷ 3 = 33, resto 1.
2. 33 ÷ 3 = 11, resto 0.
3. 11 ÷ 3 = 3, resto 2.
4. 3 ÷ 3 = 1, resto 0.
5. 1 ÷ 3 = 0, resto 1.
6. Leo los restos de abajo arriba: 1, 0, 2, 0, 1. Resultado: 10201.

Comprobación con los pesos 81, 27, 9, 3 y 1: 1 × 81 + 0 × 27 + 2 × 9 + 0 × 3 + 1 × 1 = 81 + 18 + 1 = 100.

#### 10201""",
    },
    # 37) Sucesiones: suma de una progresión aritmética.
    {
        "instruction": "¿Cuánto vale la suma de todos los múltiplos de 3 comprendidos entre 1 y 100?",
        "input": "",
        "output": """1. Los múltiplos de 3 entre 1 y 100 son 3, 6, 9, …, 99, es decir, 3 × 1, 3 × 2, …, 3 × 33. Hay 33 términos.
2. Saco el 3 como factor común: 3 × (1 + 2 + … + 33).
3. 1 + 2 + … + 33 = 33 × 34 / 2 = 561.
4. Suma: 3 × 561 = 1683.

Comprobación con la fórmula de la progresión aritmética (primero más último, por número de términos, entre dos): (3 + 99) × 33 / 2 = 102 × 33 / 2 = 51 × 33 = 1683.

#### 1683""",
    },
    # 38) Sucesiones: progresión geométrica.
    {
        "instruction": "En una progresión geométrica el primer término es 3 y la razón es 2. ¿Cuál es el décimo término?",
        "input": "",
        "output": """1. En una progresión geométrica, el término n-ésimo es a(n) = a(1) × r^(n − 1).
2. a(10) = 3 × 2^9 = 3 × 512 = 1536.

Comprobación escribiendo los diez términos: 3, 6, 12, 24, 48, 96, 192, 384, 768, 1536. El décimo es 1536.

#### 1536""",
    },
    # 39) Sucesiones: identificar el patrón.
    {
        "instruction": "La sucesión 2, 6, 12, 20, 30, … sigue un patrón regular. ¿Cuál es el término que ocupa el lugar 12?",
        "input": "",
        "output": """1. Diferencias entre términos consecutivos: 4, 6, 8, 10. Las segundas diferencias son constantes (2), así que el término general es un polinomio de grado 2.
2. Pruebo n × (n + 1): 1 × 2 = 2, 2 × 3 = 6, 3 × 4 = 12, 4 × 5 = 20, 5 × 6 = 30. Encaja con los cinco términos dados.
3. Término 12: 12 × 13 = 156.

Comprobación continuando las diferencias (que crecen de 2 en 2): 30 + 12 = 42, + 14 = 56, + 16 = 72, + 18 = 90, + 20 = 110, + 22 = 132, + 24 = 156. Ese es el término 12.

#### 156""",
    },
    # 40) Sucesiones: recurrencia lineal.
    {
        "instruction": "Una sucesión cumple a(1) = 1 y a(n + 1) = 2 × a(n) + 1 para todo n ≥ 1. ¿Cuánto vale a(8)?",
        "input": "",
        "output": """1. Calculo los primeros términos: a(1) = 1, a(2) = 3, a(3) = 7, a(4) = 15.
2. Patrón: a(n) = 2^n − 1. Se demuestra por inducción: vale para n = 1 (2 − 1 = 1), y si a(n) = 2^n − 1, entonces a(n + 1) = 2 × (2^n − 1) + 1 = 2^(n + 1) − 1.
3. a(8) = 2^8 − 1 = 256 − 1 = 255.

Comprobación aplicando la recurrencia paso a paso: 1, 3, 7, 15, 31, 63, 127, 255. El octavo término es 255.

#### 255""",
    },
]
