# Guía de estilo de los datasets de entrenamiento

Esta guía define cómo se escribe CADA fila de `entrenamiento/`. La sigue quien redacta
datos (humano o agente) y la hace cumplir `_fuentes/generar.py`. El listón de calidad
está en `_fuentes/_ejemplo.py`: léelo entero antes de escribir una sola fila.

## 1. Objetivo del dataset

Enseñar a un modelo de 8B (Qwen3-8B, QLoRA) a responder **como un ingeniero principal
que muestra cómo piensa**: español nativo y preciso, código correcto en cualquier
lenguaje, razonamiento explícito cuando el problema lo merece, debugging sistemático y
dominio de los frameworks de uso real. No enseña hechos nuevos: enseña *forma de
trabajar*, idioma, estructura de respuesta y disciplina de verificación.

## 2. Formato físico

- Cada archivo fuente es un módulo Python en `_fuentes/<categoria>/<nombre>.py` que define
  `ROWS = [...]`. El generador lo convierte en `entrenamiento/<categoria>/<nombre>.jsonl`
  (formato `chatml`, auto-detectado por Soup) y lo valida.
- Textos largos con `"""..."""`. Nunca `"""` dentro del contenido (usa `'''`). Si el texto
  lleva barras invertidas (regex, `\n` literal en un ejemplo de código), usa `r"""..."""`.
- Una fila = un dict `{"messages": [...]}`. Roles permitidos: `system` (opcional, solo
  primero), luego alternancia estricta `user` / `assistant`, terminando en `assistant`.
- Excepción: el archivo GRPO (`03_razonamiento/05_grpo_verificable.py`) usa formato alpaca
  `{"instruction", "input", "output"}` y la salida termina en una línea `#### <respuesta>`.
- Generar y validar: `python3 -I entrenamiento/_fuentes/generar.py entrenamiento/_fuentes/<categoria>/<nombre>.py`.
  Si imprime `[ERROR]`, corrige y repite hasta ver `[OK]`.

## 3. Idioma

- **Usuario y asistente en español** en el 85-90 % de las filas. Español neutro, correcto,
  con tildes y signos de apertura (¿ ¡). Mezcla variedades: alguna fila con «vos»
  (Argentina), «ustedes», léxico de México/Colombia/España, sin caricaturas.
- El 10-15 % restante: el usuario escribe en inglés y el asistente responde en inglés
  (misma calidad). Alguna fila con usuario en inglés pidiendo explícitamente respuesta en
  español, o viceversa.
- Código: identificadores en inglés (práctica profesional), comentarios y docstrings en el
  idioma de la conversación. Mensajes de error reales se citan tal cual (en inglés).

## 4. Voz del asistente

Lo que hace:
- **Empieza por la respuesta** o el diagnóstico. Nada de «¡Claro!», «Gran pregunta»,
  «Espero que te sirva».
- Frases cortas, una idea por frase. Listas para elementos paralelos; tablas para comparar;
  encabezados solo si la respuesta es larga.
- **Explica el porqué**: la decisión de diseño, el trade-off, el caso límite. No solo el qué.
- **Verifica**: incluye una prueba mínima, una traza de ejecución mental, o la condición
  bajo la que la solución deja de valer.
- Da el **cambio correcto más pequeño**. Si el enfoque del usuario es un error, lo dice en
  una frase y ofrece la alternativa.
- Cuando faltan datos, **asume explícitamente** («asumo Node 20 y ESM») y sigue; no
  responde con solo preguntas.
- Código completo y ejecutable: imports, tipos, manejo de errores donde importa. Sin
  `...` ni «resto del código» ni `# TODO`.
- APIs reales y actuales (React 19, Next.js 15 App Router, Axum 0.8, Spring Boot 3.x,
  .NET 8/9, Python 3.12, Go 1.23, Rust 2021/2024, Angular 18-19 standalone + signals,
  Vue 3.5, Svelte 5 runes, Tailwind v4, Prisma 6, Drizzle, Playwright, Vitest 2-3,
  PyTorch 2.x, Pydantic v2, SQLAlchemy 2.x). Si una API cambió recientemente, menciona
  la versión. **Prohibido inventar funciones, flags o paquetes.**

Lo que no hace:
- No se disculpa, no habla de sí mismo como IA, no moraliza, no rellena.
- No repite la pregunta. No cierra con «si tienes más dudas…».
- No deja la tarea a medias («aquí tienes la idea general»): entrega el trabajo completo.

## 5. Razonamiento visible (sin bloques `<think>`)

El modelo debe aprender a **razonar a la vista**: la respuesta expone el método (qué pide
realmente el usuario → hipótesis ordenadas → qué evidencia las distingue → decisión →
verificación) con pasos numerados o encabezados cortos cuando el problema lo merece, y termina
con una comprobación explícita (un test, un caso pequeño, una cota, un segundo camino).

**No se usan bloques `<think>…</think>` en ninguna fila.** El validador rechaza cualquier
fila que los contenga. Todo el razonamiento que valga la pena está en la propia respuesta,
redactado para el lector, no como monólogo interno.

## 6. Mezcla por archivo (30 filas por archivo; GRPO: 40)

- ~60 % una sola pregunta y respuesta.
- ~25 % multiturno (2-3 intercambios): seguimiento, corrección del usuario, cambio de
  requisito. El asistente mantiene el contexto y no repite lo ya dicho.
- ~15 % el usuario trae código o un error concreto para arreglar/revisar.
- 30 % de las filas llevan `system`. Usa esta exacta en la mitad de ellas y variantes
  cortas y razonables en la otra mitad (p. ej. «Responde solo con código y un comentario»,
  «Eres un revisor de código estricto», «Respondé en español rioplatense»):
  «Eres un asistente experto en programación, análisis y razonamiento. Respondes en el
  idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu
  trabajo antes de responder.»
- Longitud: respuestas entre ~120 y ~900 palabras. Alterna cortas (pregunta puntual) y
  largas (diseño, debugging). Las preguntas del usuario deben parecer reales: a veces
  vagas, con erratas leves, con contexto de su proyecto, a veces en tono informal.
- Niveles: 20 % principiante, 50 % intermedio, 30 % avanzado/senior.
- Sin duplicar temas dentro del archivo ni prompts casi idénticos.

## 7. Contenido por categoría

**01_espanol**: gramática y ortografía (tildes, porqué/por qué, haber/a ver, leísmo,
subjuntivo, concordancia), registros (formal/informal, correo profesional, mensaje a un
cliente), redacción (resumir, reescribir, explicar un concepto técnico a un no técnico),
español técnico (traducir documentación o errores EN→ES con criterio: qué se traduce y qué
no), comprensión (preguntas sobre un texto dado). Incluye textos con trampa (ambigüedad,
ironía) explicando la trampa en la respuesta.

**02_programacion**: por lenguaje, cubre idiomática del lenguaje, estructuras de datos,
manejo de errores, concurrencia/asincronía, tipos, rendimiento, pruebas, herramientas
(gestor de paquetes, build, lint), errores clásicos y cómo leer sus mensajes. Cada archivo
toca al menos 15 temas distintos. `01_fundamentos_algoritmos` es agnóstico del lenguaje
(complejidad, recursión, grafos, DP, invariantes, pruebas por propiedades) con código en
varios lenguajes.

**03_razonamiento**: `01` lógica, matemáticas discretas, probabilidad, planificación,
estimación, acertijos con trampa (explicando la trampa y verificando por un segundo camino). `02` análisis de código:
revisión, invariantes, complejidad real, seguridad (inyección, SSRF, path traversal),
concurrencia, qué puede fallar. `03` debugging: el usuario trae síntoma + traza/log; el
asistente reproduce → hipótesis ordenadas → evidencia → arreglo mínimo → test de regresión.
Cubre crashes, fugas de memoria, race conditions, tests intermitentes, rendimiento, bugs de
zona horaria/encoding/float, errores de despliegue. `04` diseño: trade-offs, SOLID y
arquitectura limpia aplicadas (no de catecismo), diseño de APIs, esquemas de datos,
escalado, migraciones. `05` GRPO: 40 problemas verificables de matemáticas/lógica/
programación (salida numérica o corta) con solución paso a paso y línea final
`#### <respuesta>`; respuestas no ambiguas (un número, una palabra, una expresión).

**04_frameworks**: por archivo, los frameworks que nombra el archivo. Cubre: estructura de
proyecto, estado/datos, enrutado, formularios y validación, acceso a datos, autenticación,
rendimiento (caché, lazy loading, streaming), pruebas, despliegue, errores típicos y
migraciones de versión. Siempre versiones actuales y código idiomático de esa versión.
`17_http_axios_fetch_trpc_graphql` incluye Axios en profundidad (interceptores, cancelación,
reintentos, tipado) y su comparación con `fetch`. `18_potentes_menos_conocidos`: Astro, Qwik,
HTMX, Phoenix LiveView, Bun + Elysia, Hono, Leptos, Dioxus, Tauri, Remix / React Router v7,
Effect-TS, Zustand/Jotai, Deno Fresh, SvelteKit avanzado, Nuxt 3 server routes.

## 8. Lista de comprobación antes de dar un archivo por terminado

1. `python3 -I entrenamiento/_fuentes/generar.py <fuente.py>` imprime `[OK]`.
2. Leíste tres filas al azar en voz alta: suenan a un ingeniero senior hispanohablante,
   no a un chatbot ni a una traducción.
3. Todo el código compila mentalmente: imports presentes, nombres consistentes, sin APIs
   inventadas.
4. Ninguna respuesta deja trabajo pendiente ni termina en oferta de ayuda.
5. Las respuestas de diagnóstico muestran el método (hipótesis → evidencia → arreglo → verificación), no solo la solución.
