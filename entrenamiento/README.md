# Entrenamiento por etapas: Qwen3-8B en una RTX 4060 Laptop (8 GB)

Carpeta autocontenida: datasets, configs y el orden en que se entrena. El mapa del repo y
sus reglas están en `../arquitectura.md`; la forma de cada fila, en `GUIA_DE_ESTILO.md`.

## 1. Modelo elegido y por qué

**Base: `Qwen/Qwen3-8B`** (Apache-2.0, 8.2B parámetros, 32k de contexto nativo, modo
"thinking" con `<think>…</think>` integrado en su plantilla de chat).

| Criterio | Qwen3-8B | Por qué pesa |
|---|---|---|
| Entrenar en 8 GB | Sí, con `stream_layers: true` + NF4 (caché de ~6 GB en RAM; pico de VRAM ~3-5 GB). Un 8B es el tamaño máximo razonable: la inferencia posterior también tiene que caber. | Las medidas del repo: 8B en 4 GB, 14B en 8 GB (`benchmarks/`) |
| Ejecutar después en 8 GB | GGUF `q4_k_m` ≈ 5,0 GB, `q5_k_m` ≈ 5,8 GB: entran en VRAM con 2-3 GB de margen para contexto (8-16k tokens) | El objetivo no es solo entrenar |
| Exportable con el llama.cpp que trae Soup | **Sí** (`Qwen3ForCausalLM` está en la lista del pin `b5270`) | Qwen3.5/3.6 **no** lo están |
| Español | Entrenado en 119 idiomas; español de calidad nativa | Etapa 1 |
| Código y razonamiento | Entre lo mejor de su tamaño en código; razonamiento con modo thinking | Etapas 2-3 |
| Soporte en Soup | Recetas `qwen3-8b-sft`, `qwen3-8b-grpo`, `qwen3-8b-tools`; streaming NF4 verificado en Qwen3-8B por un contribuidor | Menos sorpresas |

Alternativas, por si cambian las condiciones:

- **`Qwen/Qwen3.5-9B`**: más nuevo y probablemente más capaz, con 262k de contexto. En Soup se
  entrena **solo el decodificador de texto** (`modality: text`) y la exportación a GGUF exige un
  llama.cpp más reciente que el pin de Soup (`--llama-cpp /ruta/a/llama.cpp` nuevo). Es la mejora
  natural cuando quieras asumir ese paso extra.
- **`Qwen/Qwen3-4B`**: si prefieres iterar rápido o quieres GRPO residente en 8 GB. Cabe en
  `q8_0` (≈ 4,3 GB) para inferencia, que conserva más calidad que `q4_k_m`.
- **`deepseek-ai/DeepSeek-R1-Distill-Llama-8B`** o **`Qwen2.5-Coder-7B-Instruct`**: solo si el
  objetivo fuera únicamente razonamiento matemático o únicamente código; en español y en uso general
  Qwen3-8B es mejor.

Lo que un ajuste LoRA de ~1.200 filas puede y no puede hacer: enseña **idioma, voz, estructura
de respuesta y método de trabajo**; no convierte un 8B en un modelo de frontera. Para ganar
capacidad real hay que escalar los datos (ver §7).

## 2. Hardware y entorno

- GPU: RTX 4060 Laptop, 8 GB VRAM (Ada, sm_89: bf16 nativo, FP8 posible). RAM del sistema:
  ~32 GB (la captura muestra 16 GB compartidos, que es la mitad). El caché NF4 de Qwen3-8B ocupa
  ~6 GB y se bloquea en RAM; sobra.
- Windows: instala el **wheel CUDA de torch** (el de PyPI es solo CPU; `soup doctor` imprime el
  comando). Con WDDM un exceso de VRAM no da error: **derrama a RAM y va 10× más lento**; por eso
  Soup rechaza una config que no cabe en vez de avisar. `soup.yaml` usa `max_length: 2048` con
  `stream_vram_probe: true` (mide un paso real); si no cabe, baja a 1792. Cierra el navegador y
  cualquier juego antes de entrenar: cada GB de VRAM libre cuenta.
- Linux: lo mismo sin las salvedades de WDDM.

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install "soup-cli[train]"
# si torch quedó en CPU:  soup doctor  -> copia el pip install que imprime
soup doctor --config entrenamiento/soup.yaml
```

## 3. Qué hay en esta carpeta

```
entrenamiento/
  README.md                 este archivo
  GUIA_DE_ESTILO.md         cómo se escribe cada fila (voz, idioma, formato, proporciones)
  soup.yaml                 config SFT por etapa (Qwen3-8B, streaming NF4)
  soup_grpo.yaml            opcional: refuerzo GRPO con problemas verificables
  _fuentes/                 fuentes .py (ROWS = [...]) + generar.py (convierte a JSONL y valida)
                            + eval_desde_grpo.py (tareas de evaluación verificables)
                            + contar_tokens.py (tokens reales con la plantilla de Qwen3)
  01_espanol/*.jsonl        etapa 1 · 4 archivos
  02_programacion/*.jsonl   etapa 2 · 12 archivos (fundamentos + 11 lenguajes/familias)
  03_razonamiento/*.jsonl   etapa 3 · 4 archivos SFT + 1 GRPO (alpaca con `#### respuesta`)
  04_frameworks/*.jsonl     etapa 4 · 18 archivos (React, Next.js, Axios/tRPC/GraphQL, Axum…)
```

Los `.jsonl` son los que lee Soup (`format: chatml`, auto-detectado). Las fuentes `.py` son más
cómodas de editar a mano; tras cambiarlas: `python3 -I entrenamiento/_fuentes/generar.py --todo`.

## 4. Orden de entrenamiento

| Etapa | Archivos (en orden) | Filas | Enseña |
|---|---|---|---|
| 1 Español | `01_espanol/01…04` | 120 | gramática, registros, redacción, español técnico y traducción |
| 2 Programación | `02_programacion/01…12` | 360 | fundamentos, Python, JS, TS, Rust, Go, Java/Kotlin, C/C++, C#, SQL, shell, otros |
| 3 Razonamiento | `03_razonamiento/01…04` (SFT), luego `05` (GRPO, opcional) | 120 + 40 | lógica y matemáticas, revisión de código, debugging sistemático, diseño |
| 4 Frameworks | `04_frameworks/01…18` | 540 | React, Next.js, Vue/Nuxt/Svelte/Solid, Angular, Node, FastAPI/Django/Flask, Axum/tokio, Go web, Spring/Ktor, ASP.NET, móvil, datos/ML, infra, CSS/Tailwind, ORMs, testing, Axios/fetch/tRPC/GraphQL, Astro/HTMX/Qwik/Tauri… |

Total: **39 archivos, 1.180 filas** (≈ 4,8 M caracteres; ~1.100 tokens de mediana por fila).

**Cómo se encadenan las etapas.** Soup no tiene un campo para *continuar* un adapter LoRA, y
`--resume` reanuda también el optimizador y el contador de pasos, así que no sirve para cambiar de
dataset. Hay dos formas correctas de que el modelo acumule lo aprendido, y una que **no** funciona:

- **No funciona:** entrenar un adapter nuevo sobre `Qwen/Qwen3-8B` con cada archivo. El adapter final
  solo sabría el último archivo (más el pequeño `replay`).
- **Recomendado, por etapa (4 entrenamientos):** cada etapa entrena con la **lista** de sus archivos y,
  al terminar, fusionas el adapter en el modelo. Ese modelo fusionado es la `base` de la etapa
  siguiente. Cuatro fusiones, pocos GB de disco y suficientes pasos de optimización por run.
- **Archivo a archivo (lo que pediste):** igual que lo anterior pero con un archivo por run y una
  fusión tras cada uno. Funciona, pero son 39 fusiones (~16 GB de disco y ~10-15 min cada una) y
  39 cachés NF4 nuevas en `~/.soup/layer-stream` (~6 GB cada una; borra la anterior). Úsalo si
  quieres observar el efecto de cada archivo; si no, entrena por etapa.

En ambos modos, a partir de la etapa 2 añade `data.replay` (rehearsal) con una muestra de lo ya
entrenado: evita que lo nuevo borre lo anterior.

## 5. Ciclo de entrenamiento

```bash
# 0) Cuenta los tokens reales (necesita transformers) y valida con Soup
python entrenamiento/_fuentes/contar_tokens.py --max-length 2048
soup data validate entrenamiento/02_programacion/02_python.jsonl
soup data doctor   entrenamiento/02_programacion/02_python.jsonl --model Qwen/Qwen3-8B   # plantilla + máscara
```

**Modo por etapa (recomendado).** En `entrenamiento/soup.yaml`, para la etapa 2 por ejemplo:

```yaml
base: ./modelos/etapa_1            # etapa 1: Qwen/Qwen3-8B
data:
  train:                           # todos los archivos de la etapa, en orden
    - ./entrenamiento/02_programacion/01_fundamentos_algoritmos.jsonl
    - ./entrenamiento/02_programacion/02_python.jsonl
    # … hasta 12_otros_lenguajes.jsonl
  interleave: {strategy: concat}
  replay: ./entrenamiento/_replay/acumulado.jsonl    # desde la etapa 2
  replay_ratio: 0.2
output: ./runs/etapa_2
```

```bash
# Acumulado de rehearsal con lo ya entrenado (antes de la etapa 2: la etapa 1)
soup data merge entrenamiento/01_espanol/*.jsonl --output entrenamiento/_replay/acumulado.jsonl --shuffle

soup train --config entrenamiento/soup.yaml --dry-run    # valida, estima VRAM y tok/s
soup train --config entrenamiento/soup.yaml

# Revisar y probar
soup runs ; soup why ; soup rewind
soup chat --model ./runs/etapa_2

# Fusionar: este modelo es la base de la etapa siguiente
soup merge --adapter ./runs/etapa_2 --output ./modelos/etapa_2 --dtype bfloat16
```

Para la etapa 3 regenera el acumulado con las etapas 1 y 2
(`soup data merge entrenamiento/01_espanol/*.jsonl entrenamiento/02_programacion/*.jsonl …`).
El archivo GRPO (`03_razonamiento/05_grpo_verificable.jsonl`) es alpaca: no lo metas en la lista
SFT ni en el acumulado; va con `soup_grpo.yaml`.

**Modo archivo a archivo.** Mismo ciclo con `data.train` apuntando a un solo archivo y
`gradient_accumulation_steps: 4` (con 27 filas de entrenamiento, 16 dejaría ~2 pasos por época).
Tras cada archivo: `soup merge` → `base:` del siguiente, y borra el modelo fusionado y la caché NF4
anteriores (`~/.soup/layer-stream/<hash>`) para no llenar el disco.

**Tiempo orientativo.** La etapa 4 procesa ~1,6 M tokens (486 filas × ~1.100 tokens × 3 épocas).
El pre-flight de `soup train` imprime una previsión de tok/s medida en tu tarjeta; úsala para
calcular la duración real antes de lanzar.

## 6. Fusionar, exportar y ejecutar

```bash
# Fusiona el adapter de la última etapa (bf16, ~16 GB en disco)
soup merge --adapter ./runs/etapa_4 --output ./modelos/final --dtype bfloat16

# Compila el cuantizador de llama.cpp una sola vez (Soup clona el pin b5270 en ~/.soup/llama.cpp)
soup export --model ./modelos/final --format gguf --quant f16 --output ./modelos/final.f16.gguf   # primer uso: clona
cd ~/.soup/llama.cpp && cmake -B build -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release \
  && cmake --build build --config Release --target llama-quantize -j 4 && cd -

# GGUF cuantizado y despliegue en Ollama en un paso
soup export --model ./modelos/final --format gguf --quant q4_k_m --deploy ollama --deploy-name qwen3-8b-mio
ollama run qwen3-8b-mio

# Alternativa sin Ollama: servidor OpenAI-compatible desde el adapter (sin fusionar)
soup serve --model ./runs/etapa_4 --port 8000
```

**Medir antes y después.** `soup eval custom` puntúa un modelo sobre tareas `{"prompt", "expected",
"scoring"}`. El conversor incluido crea tareas verificables a partir del set GRPO:

```bash
python3 -I entrenamiento/_fuentes/eval_desde_grpo.py --ultimas 10      # -> entrenamiento/eval/razonamiento_verificable.jsonl
huggingface-cli download Qwen/Qwen3-8B --local-dir ./modelos/qwen3-8b-base   # eval custom necesita una carpeta local
soup eval custom --model ./modelos/qwen3-8b-base --tasks entrenamiento/eval/razonamiento_verificable.jsonl   # base
soup eval custom --model ./runs/etapa_4     --tasks entrenamiento/eval/razonamiento_verificable.jsonl   # tu adapter
# Pérdida por cuantización (ambos lados cargables con transformers, p. ej. bf16 frente a BNB 4-bit):
soup merge --adapter ./runs/etapa_4 --output ./modelos/final_4bit --save-format 4bit
soup eval quant-check --before ./modelos/final --after ./modelos/final_4bit --tasks entrenamiento/eval/razonamiento_verificable.jsonl
```

`quant-check` compara modelos que carga transformers; para el GGUF, prueba en Ollama con las
mismas preguntas. Si entrenas la etapa GRPO con el archivo completo, evalúa antes de hacerlo
(esas 10 filas también están en su entrenamiento).

Tamaños orientativos para Qwen3-8B: `q4_k_m` ≈ 5,0 GB (cabe con contexto largo), `q5_k_m` ≈ 5,8 GB
(mejor calidad, todavía cabe), `q8_0` ≈ 8,7 GB (no cabe entero en 8 GB; Ollama lo partiría entre
GPU y CPU). Para apagar el modo thinking en inferencia, Qwen3 acepta `/no_think` en el prompt o
`enable_thinking=false` en la plantilla.

## 7. Escalar los datos (cuando quieras más que forma y estilo)

Soup trae todo lo necesario para multiplicar estos archivos sin perder el estilo:

```bash
# Síntesis guiada por tus propias filas como semilla (Anthropic, Ollama local o vLLM)
soup data generate --prompt "Preguntas y respuestas de un ingeniero senior sobre Rust async" \
  --seed entrenamiento/02_programacion/05_rust.jsonl --count 300 --format chatml \
  --provider anthropic --quality-pipeline -o entrenamiento/_ampliado/rust_sintetico.jsonl
soup data dedup entrenamiento/_ampliado/rust_sintetico.jsonl --threshold 0.8
soup data score --input entrenamiento/_ampliado/rust_sintetico.jsonl
soup data merge entrenamiento/02_programacion/05_rust.jsonl entrenamiento/_ampliado/rust_sintetico.jsonl -o rust_total.jsonl --shuffle
```

Referencia de volumen (de `examples/data/README.md`): un formato o estilo → cientos de filas; una
tarea que el modelo ya medio sabe → miles; hechos nuevos → mejor RAG que fine-tuning.

## 8. Problemas frecuentes

- **El pre-flight rechaza la config**: baja `data.max_length` (2048 → 1792 → 1536) o usa
  `lora.r: 8` (libera ~0,35 GB); `batch_size` ya es 1. Comprueba con `contar_tokens.py` cuántas
  filas truncarías. `--allow-oom-attempt` solo si entiendes el derrame de WDDM.
- **`could not page-lock`**: cierra programas que usen mucha RAM; Soup cae a RAM paginable (más
  lento) o a NVMe (`stream_source: disk`).
- **`Tokenizer has no chat_template`**: no debería pasar con Qwen3; si cargas otro base, añade
  `data.chat_template: chatml`.
- **GGUF falla al cuantizar**: falta compilar `llama-quantize` (paso de §6) o la arquitectura no
  está en el pin (`--llama-cpp` a un checkout nuevo).
- **El modelo responde en inglés**: añade el `system` de la guía en inferencia o sube el peso
  de la etapa 1 en el `replay`.
