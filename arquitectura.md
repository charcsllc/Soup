# Arquitectura de Soup — mapa de referencia

> Documento de trabajo del mantenedor local. Resume **qué hace el repo, dónde vive cada cosa y
> qué reglas rigen**, para no releer archivo por archivo en cada sesión. Verificado contra el
> código y los docs de la versión **0.76.0** (commit `d500ae0d`, 2026-10). Cuando cambie algo
> en `schema.py`, `cli.py` o `docs/`, este archivo es el que hay que corregir.
>
> Fuentes de verdad por orden de prioridad: `src/soup_cli/config/schema.py` →
> `AGENTS.md` / `CONTRIBUTING.md` → `docs/*.md` → este archivo.

## 1. Qué es

**Soup** (`soup-cli`) es una CLI para **fine-tuning y post-entrenamiento de LLMs con un solo
comando y un solo YAML**. Cubre SFT, preferencias (DPO/ORPO/SimPO/IPO/KTO/BCO), RL
(GRPO/PPO/online DPO), reward models, PRM, pre-entrenamiento continuado, destilación,
clasificación, embeddings, TTS/ASR, visión/audio, unlearning, y además todo el ciclo
alrededor: datos (formatos, limpieza, síntesis), evaluación, merge/export (GGUF, ONNX,
TensorRT…), servidor OpenAI-compatible, registro de artefactos, gobernanza y cumplimiento.

| Dato | Valor |
|---|---|
| Paquete / entrypoint | `soup-cli` → `soup = soup_cli.cli:run` (Typer) |
| Versión | 0.76.0 (`pyproject.toml`) |
| Python | `>=3.10,<3.13` (CI: 3.10/3.11/3.12 × Ubuntu/Windows/macOS) |
| Licencia | Apache-2.0 |
| Build | hatchling; `packages = ["src/soup_cli"]` |
| Instalación | `pip install "soup-cli[train]"` (entrenar) · `soup-cli` solo = CLI ligera sin torch |
| Rasgo distintivo | **Layer streaming (BETA)**: entrena un 8B en 4 GB de VRAM (base congelada en RAM, una capa cada vez, NF4) |

### Extras de pip (los que importan)

| Extra | Trae | Para |
|---|---|---|
| `train` | torch≥2.6, transformers≥5.16.1<6, peft≥0.20, trl≥0.29<1, datasets, bitsandbytes, accelerate | `soup train` |
| `all` | train + serve + ui + data + mcp | todo en uno |
| `fast` | unsloth | `backend: unsloth` (2-5× más rápido, menos VRAM) |
| `serve` / `serve-fast` / `sglang` | fastapi+uvicorn / vllm / sglang | `soup serve` |
| `ui` / `tui` | fastapi / textual | `soup ui` / `soup tui` |
| `eval` / `aider` | lm-eval / aider | `soup eval benchmark` / `soup eval aider` |
| `data` / `data-pro` | datasketch, sklearn / langdetect, presidio | dedup MinHash / idioma + PII |
| `qat` | torchao≥0.18 | FP8, NVFP4, export torchao |
| `cce` / `liger` / `ring-attn` | cut-cross-entropy / liger-kernel / ring-flash-attn | memoria/velocidad |
| `mlx` | mlx, mlx-lm | Apple Silicon (backend independiente, no necesita `[train]`) |
| `onnx` / `tensorrt` | optimum / tensorrt_llm | export |
| `awq` / `gptq` | **deprecados**, se eliminan en v0.77; no instalables junto a `[train]` |
| `mcp` | mcp SDK | `soup mcp serve` (drive Soup desde Claude Code/Cursor) |
| `dev` | train+mcp+data + pytest, ruff, mypy, pre-commit, cryptography, reportlab | contribuir |

## 2. Flujo típico de usuario

```bash
soup init --template chat            # escribe soup.yaml (21 plantillas)
soup data validate ./data/train.jsonl   # formato auto-detectado, filas inválidas
soup doctor --config soup.yaml       # GPU, deps, y qué ajustes del YAML NO lee tu task/backend
soup profile --config soup.yaml      # estimación de VRAM/velocidad antes de gastar GPU
soup train --config soup.yaml        # pre-flight de VRAM → carga → entrena → ./output (adapter LoRA)
soup chat --model ./output           # prueba interactiva (carga base + adapter)
soup eval custom --model ./output --tasks eval.jsonl
soup merge --adapter ./output --output ./merged          # fusiona LoRA en el base (fp16/bf16)
soup export --model ./merged --format gguf --quant q4_k_m  # GGUF vía llama.cpp (pin b5270)
soup deploy ollama --model ./merged/model.q4_k_m.gguf --name mi-modelo
soup serve --model ./output --port 8000                  # API OpenAI-compatible (+ /v1/messages)
```

Cada paso tiene variantes (ver §9 y `docs/commands.md`). `soup autopilot` decide task/quant/LR/epochs
por ti; `soup advise` dice si tu problema es de prompt, RAG, SFT, DPO o GRPO antes de entrenar.

## 3. Capas y reglas de dependencia

```
cli.py (Typer: enrutado y registro de comandos)
  └─ commands/   (handlers: parsean flags, orquestan, imprimen con rich; SIN lógica algorítmica)
       ├─ trainer/   (wrappers por task sobre TRL/transformers/MLX)
       ├─ data/      (carga, detección/conversión de formatos, loss mask, collators, providers, traces)
       ├─ eval/      (benchmarks, judge, gate, arena, quant-check, forgetting…)
       ├─ utils/     (~400 módulos: GPU, quantización, streaming, PEFT, export, serve, gobernanza…)
       ├─ experiment/ registry/ cans/ autopilot/ autodistill/ bench/ cloud/ envs/ migrate/
       │  monitoring/ plugins/ recipes/ templates/ ui/ mcp_server/
       └─ config/    (Pydantic v2 puro: schema.py, loader.py; NO importa nada pesado)
```

Reglas obligatorias (`AGENTS.md`, `CONTRIBUTING.md`, `.claude/CLAUDE.md`):

- **Dependencias hacia dentro**: `config/` no importa `commands/` ni torch. Los frameworks
  pesados (torch, transformers, peft, trl, mlx) se importan **perezosamente dentro de la función**
  que los usa; cualquier módulo central importa limpio sin `[train]`.
- Salida solo con `rich.console.Console`, nunca `print()`.
- Contención de rutas: `os.path.realpath` + `os.path.commonpath` (no `Path.resolve()+relative_to()`;
  rompe con nombres cortos de Windows). Se rechazan symlinks en bordes de lectura/escritura
  (TOCTOU: `os.lstat + S_ISLNK`, `O_NOFOLLOW`).
- ruff `E,F,I,N,W`, línea 100, sin variables de una letra (E741), type hints siempre.
- Sin sintaxis 3.11+ (p. ej. `except*`, `Self` sin typing_extensions) y sin supuestos POSIX.
- Un trainer = un wrapper con la misma forma que sus hermanos; se conecta en **un** sitio
  (`trainer/dispatch.py::build_trainer`). Un formato = un `_convert_<fmt>` en `data/formats.py`
  + firma en `FORMAT_SIGNATURES` + entrada en `VALID_FORMATS`. Un comando = módulo en `commands/`
  + una línea en `cli.py`.
- Añadir/quitar opción CLI o campo YAML ⇒ `python scripts/gen_reference_docs.py` (regenera
  `docs/cli-reference.md` y `docs/config-reference.md`) + entrada en `changelog.d/<release>/<pr>.<cat>.md`.
- Cada fix lleva test de regresión; cada feature, los tests que pide CONTRIBUTING (30+ para un trainer).

## 4. Mapa de directorios

### Raíz

| Ruta | Qué es |
|---|---|
| `src/soup_cli/` | el paquete |
| `tests/` | ~980 archivos pytest (`test_<modulo>.py`); `conftest.py` tiene el único probe CUDA |
| `docs/` | referencia por tema (ver §12); `cli-reference.md` y `config-reference.md` son **generados** |
| `examples/` | configs ejecutables sobre fixtures de 5-10 filas (smoke, no entrenamiento real) + `synthetic_workflow.md` |
| `templates/` | 3 plantillas antiguas (chat/code/medical); las 21 vigentes están en `src/soup_cli/templates/` |
| `benchmarks/` | registros de medición publicados tal cual (gates de streaming, pruebas en RTX 5070 8 GB, T4, H100, M1) + `harness/` |
| `scripts/` | `gen_reference_docs.py`, `gen_llama_cpp_capabilities.py`, etc. |
| `changelog.d/<versión>/` | fragmentos de changelog por PR |
| `notebooks/proof-4gb.ipynb` | demo Colab T4: streaming bit-exacto bajo tope de 4 GB |
| `.github/` | CI (matriz 3 Py × 3 OS), `constraints/transformers-floor.txt` |
| `AGENTS.md`, `CONTRIBUTING.md`, `.claude/CLAUDE.md` | reglas para agentes y humanos (`.claude/` está en .gitignore) |

### `src/soup_cli/`

| Módulo | Responsabilidad |
|---|---|
| `cli.py` | crea la app Typer, registra ~100 comandos y grupos, `--log-level`, `--verbose`, audit log por comando (`~/.soup/audit.jsonl`), telemetría opt-in (`SOUP_TELEMETRY=1`) |
| `commands/` | un archivo por comando: `train.py` (115 KB, el más grande: pre-flights, replay, LR finder, annex-xi, energy…), `serve.py`, `export.py`, `merge.py`, `chat.py`, `infer.py`, `eval.py`, `data*.py`, `deploy.py`, `recipes.py`, `runs.py`, `registry.py`, `ship.py`, `mcp.py`, `shrink.py`, `draft.py`, `reward.py`, `probe.py`… |
| `config/schema.py` | **fuente de verdad** (398 KB): `LoraConfig`, `DataConfig`, `TrainingConfig`, `EvalConfig`, `ShipConfig`, `AdviseConfig`, `EvalGateConfig`, `SoupConfig` + validadores cruzados por task/backend |
| `config/loader.py`, `unknown_keys.py`, `deprecation.py`, `staged_fields.py`, `backend_support.py` | carga YAML (límites de tamaño), rechazo de claves desconocidas (v0.75+), avisos/rechazos de campos *staged* y deprecados, matriz de soporte por backend |
| `data/loader.py` | `load_dataset()`: JSONL/JSON/CSV/Parquet/TXT, remotos (s3/gs/az/oci), HF Hub, streaming, interleave de varias fuentes, replay, split de validación, resolución de rutas de imagen/audio |
| `data/formats.py` | `detect_format()` (100 primeras filas, familias ricas/pobres), `format_to_messages()` → forma normalizada, `messages_to_format()` para convertir |
| `data/sft_format.py`, `loss_mask.py`, `chat_templates.py`, `collators.py` | construcción de filas SFT con máscara solo-asistente, plantillas de chat con nombre (`chatml`, `llama3`, `qwen2.5`, `mistral`, `gemma3`, `phi4`, `deepseek-r1`) o Jinja, CrossDocCollator para packing |
| `data/validator.py`, `augment.py` | estadísticas/validación; aumentación LLM (rephrase/translate/style) |
| `data/providers/` | generación sintética: `anthropic.py`, `ollama.py`, `vllm.py` (+ openai/server) |
| `data/templates/` | plantillas de síntesis: code, conversation, qa, preference, reasoning, tool_calling, verifiable |
| `data/traces/` | trazas de producción → pares de preferencia (LangChain/OpenAI/Soup serve) |
| `data/_fixtures/` | JSONL demo empaquetados (`soup data demo`) |
| `trainer/` | un wrapper por task (ver §7) + `dispatch.py`, `_trl_compat.py` (sondas de capacidades TRL en vez de comparar versiones), `stream_setup.py` (mixin de layer streaming), `rewards.py`, `loss_summary.py`, `mlx_*.py` |
| `eval/` | `custom.py`, `judge.py`, `human.py` (Elo), `leaderboard.py`, `gate.py`+`gate_suites.py`, `quant_check.py`, `forgetting.py`, `calibrate.py`, `arena.py`, `aider_polyglot.py`, `checkpoint_intelligence.py` |
| `monitoring/` | `callback.py` (SoupTrainerCallback → panel rich + tracker), `display.py`, `rewind_log.py`, `hf_push.py`, `grpo_stability_callback.py`, `curriculum_callback.py`, `trace_logger.py` |
| `experiment/tracker.py` | tracker SQLite de runs (`.soup/`), base de `soup runs` |
| `registry/` | registro local de modelos con linaje (hash de config/datos, artefactos, diff, promote) |
| `cans/` | `.can` = tar.gz con manifest + config + data_ref + recipe (compartir/ejecutar recetas) |
| `recipes/catalog.py` | 170 recetas YAML embebidas (`soup recipes list/show/use/search/verify`) |
| `templates/` | 21 plantillas `soup init --template` + `manifest.json` |
| `autopilot/` | analizadores (dataset/hardware/modelo) + decisiones (task, quant, LR, epochs, batch, PEFT) |
| `autodistill/` | contratos/fingerprints de un pipeline de destilación offline (fase A, sin modelo) |
| `bench/` | `soup bench train` (demuestra que el modelo entrena mientras se mide) |
| `cloud/` | `soup train --cloud modal|lambda` (render de controlador; `--cloud-submit` envía) |
| `envs/` | entornos de rollout de juguete para GRPO/openenv |
| `migrate/` | importar configs de LLaMA-Factory, Axolotl, Unsloth |
| `plugins/` | sistema de hooks (`pre_train`, `post_step`…) + descubrimiento por entry points, opt-in explícito |
| `mcp_server/` | 14 tools de solo lectura + `train_start`/`export` plan-only (`--allow-mutating`) + ejecución con token (`--allow-execute`, solo stdio) |
| `ui/` | Web UI FastAPI + SPA (dashboard, nuevo entrenamiento, explorador de datos, chat); token Bearer, CSP estricta |
| `utils/` | todo lo transversal; los que más se tocan: `gpu.py` (detección, batch estimado, dtypes), `hardware_fit.py` (predictor analítico de VRAM), `quant_menu.py`, `layer_stream*.py`, `layer_shard.py`, `peft_builder.py`/`peft_wiring.py`, `gguf_quant.py`, `save_formats.py`, `ollama.py`, `vllm.py`, `sglang.py`, `errors.py`, `exit_codes.py`, `paths.py`, `trust_remote.py`, `optimizer_zoo.py`, `data_pipeline.py`, `data_clean.py`, `data_doctor.py`, `eval_schedule.py`, `rewind.py`, `advise.py`, `ship_verdict.py`, `deploy_autopilot.py`, `hf.py`, `hubs.py` |

## 5. `soup.yaml`: el esquema

Raíz (`SoupConfig`):

```yaml
base: Qwen/Qwen3-8B            # id HF o ruta local (obligatorio)
task: sft                      # ver tabla de tasks
modality: text                 # text | vision | audio | audio_out
backend: transformers          # transformers | unsloth | mlx
data: {...}                    # DataConfig (obligatorio: data.train)
training: {...}                # TrainingConfig
output: ./output
experiment_name: null          # sin / \ : ni bytes nulos
eval: null                     # EvalConfig (auto_eval, benchmarks, custom_tasks, judge, ship)
advise: null                   # AdviseConfig
```

**Tasks** (`SoupConfig.task`): `sft`, `dpo`, `grpo`, `ppo`, `reward_model`, `kto`, `orpo`, `simpo`,
`ipo`, `bco`, `preference`, `pretrain`, `embedding`, `prm`, `tts`, `classifier`, `reranker`,
`cross_encoder`, `distill`, `unlearn`, `moe_lora_routing`, `online_dpo`, `asr`.

**`data`** (`DataConfig`) — campos que usarás:

| Campo | Default | Nota |
|---|---|---|
| `train` | — | ruta local, URI remota, nombre HF, o **lista ≥2** (exige `data.interleave`; no mezclar hub con locales) |
| `format` | `auto` | `alpaca, sharegpt, chatml, dpo, kto, llava, sharegpt4v, plaintext, embedding, audio, tool-calling, prm, pre_tokenized, input_output, video, multimodal, raft, asr, cross_encoder` |
| `val_split` | `0.1` | se evalúa cada época (o `training.eval_steps`); `grpo/ppo/online_dpo` lo ignoran y entrenan con todo |
| `max_length` | `2048` | tokens por fila; **palanca principal de VRAM** junto a batch |
| `train_on_responses_only` | `true` | loss solo en turnos assistant (requiere chat_template en el tokenizer) |
| `train_on_messages_with_train_field` | `false` | máscara por campo `train: bool` en cada mensaje |
| `mask_history` | `false` | loss solo en el ÚLTIMO turno assistant |
| `chat_template` | `null` | nombre (`chatml`, `llama3`, `qwen2.5`, `mistral`, `gemma3`, `phi4`, `deepseek-r1`) o Jinja; override del tokenizer |
| `replay`, `replay_ratio`, `replay_seed` | — | rehearsal anti-olvido (sft/pretrain; incompatible con packing); ratio = fracción del conjunto FINAL |
| `interleave` | — | `{strategy: concat|under|over|probs, probs: [...]}` para `train` lista |
| `streaming`, `buffer_size`, `shards` | — | datasets grandes/remotos |
| `add_new_tokens`, `new_special_tokens` | — | amplía vocabulario (solo backend transformers, tasks listados en docs/data.md) |
| `image_dir`, `audio_dir`, `video_dir` | — | raíz de rutas de medios (contención comprobada) |
| `forget_set`, `retain_set` | — | `task: unlearn` |
| `tokenized_path` | — | con `format: pre_tokenized` tras `soup data preprocess` |

Campos **staged** (avisan en 0.76, se rechazan en 0.77; no hacen nada): `resize_vocab`,
`split_thinking`, `image_min_pixels/max_pixels`, `video_fps/maxlen`, `eval_on_each_dataset`.

**`training`** (`TrainingConfig`) — lo esencial:

| Campo | Default | Nota |
|---|---|---|
| `epochs` / `lr` | 3 / 2e-5 | recetas LoRA usan 1e-4–2e-4; DPO 5e-6; GRPO 1e-5 |
| `batch_size` | `auto` | `auto_batch_size_strategy: auto|static|probe` (probe = ensayo real, cachea en `~/.soup/batch_cache.json`, detecta el spill de WDDM en Windows) |
| `gradient_accumulation_steps` | 4 | batch efectivo = batch_size × acumulación |
| `seed`, `data_seed` | null (=42) | fija init LoRA + orden; MLX los ignora con aviso |
| `warmup_ratio`, `weight_decay`, `max_grad_norm`, `scheduler` (cosine), `optimizer` (adamw_torch) | | `optimizer_zoo.SUPPORTED_OPTIMIZERS` (8-bit bnb, paged, lion, adafactor, lomo, schedule_free…) |
| `save_steps` / `logging_steps` / `eval_steps` | 100 / 10 / null | |
| `lora` | `LoraConfig` | `r` (0 = full fine-tuning), `alpha`, `dropout` 0.05, `target_modules: auto`, `use_dora/rslora/vera/olora`, `rank_pattern`, `init_strategy: random|pissa|olora|loftq` |
| `quantization` | `4bit` | ver §8 (Quant Menu) |
| `gradient_checkpointing` | `false` | `true|selective|medium|full|auto` (auto: <24 GB → full) |
| `packing` / `multipack` | false | packing de muestras / FFD; incompatibles con replay e interleave |
| `neftune_alpha` | null | |
| `stream_layers` + `stream_source|buffers|read_ahead|pin|vram_override|vram_probe|nf4_scale_cache|disk_kind|expert_layout` | false | **layer streaming** (§8) |
| `use_cut_ce`, `use_liger`, `use_flash_attn`, `fast_lora`, `activation_offloading` | false | memoria/velocidad (extras); `kernel_auto_compose` existe pero nunca aplicó nada (#801) |
| `freeze_layers` / `freeze_ratio` / `unfrozen_parameters` (Spectrum) / `lisa_*` | — | modos "sin LoRA" (solo sft/pretrain text transformers) |
| `relora_steps`, `loraplus_lr_ratio`, `use_galore`, `expand_layers` (LLaMA Pro), `use_mod` | — | PEFT avanzado |
| `dpo_beta`, `kto_beta`, `orpo_beta`, `simpo_gamma`, `ipo_tau`, `bco_beta`, `preference_loss`, `dpo_beta_schedule` | | preferencias |
| `grpo_beta` (0.1), `num_generations` (4), `reward_fn` (`accuracy`, `format`, ruta `.py`, lista separada por comas), `verifiable_domain` (math/code/json_schema), `grpo_variant` (gspo/dapo/dr_grpo/bnpo/two_sided/rft) | | GRPO |
| `teacher_model`, `distill_temperature`, `distill_mode`, `distill_chunk_size` | | distill |
| `num_labels`, `label_names`, `classifier_lora` | | classifier |
| `reasoning_effort`, `train_on_eot` | | gpt-oss |
| `kv_cache_type` | null | `q8_0|bf16|f16|fp8` para `soup serve` |
| `loss_watchdog`, `loss_spike_recovery`, `convergence_detection`, `forgetting_detection`, `checkpoint_intelligence`, `eval_gate`, `rewind_log` (true), `curriculum` | | estabilidad e inteligencia de entrenamiento |
| `reward_hack_*`, `echo_trap_*`, `rl_checkpoint_*` | | endurecimiento del bucle RL |

Reglas de carga que muerden:

- **Clave desconocida ⇒ error** (v0.75+). Un typo no se ignora.
- **Ajuste que el task/backend no lee ⇒ rechazo o aviso** (v0.76): p. ej. `quantization_aware: true`
  (nunca funcionó), `use_longlora`, `freeze_layers` fuera de sft/tts, `backend: unsloth` en tasks sin setup.
  `soup doctor --config` lo lista antes de entrenar.
- Tasks que **ignoran `quantization`** y cargan sin cuantizar: `distill`, `classifier/reranker/cross_encoder`,
  `prm`, `moe_lora_routing`, `unlearn`, `asr` (un `4bit` explícito avisa y resuelve a `none`).
- `lora.r: 0` (full FT) exige `task: sft`, transformers, text, `quantization: none`, y excluye todo knob LoRA.
- `data.train` lista ⇔ `data.interleave`; `packing/multipack` apagados.
- `training.eval_steps` se rechaza en mlx, unlearn, y con `val_split: 0` en local.
- Config de tamaño limitado (`yaml_limits.py`); `experiment_name` sin separadores.

## 6. Datos

### Formatos (auto-detección sobre las 100 primeras filas)

| Formato | Fila mínima | Tasks |
|---|---|---|
| `alpaca` | `{"instruction","input","output"}` (+`system` opcional) | sft, grpo (output = gold) |
| `sharegpt` | `{"conversations":[{"from":"human","value":..},{"from":"gpt",..}]}` | sft |
| `chatml` | `{"messages":[{"role":"system|user|assistant","content":..}]}` | sft, distill, grpo |
| `tool-calling` | `messages` + `tools` (+ `tool_calls` en turnos assistant, `tool_call_id` en turnos tool) | sft |
| `dpo` | `{"prompt","chosen","rejected"}` (strings o listas de mensajes, **mismo tipo los tres**) | dpo/orpo/simpo/ipo/bco/reward_model/preference |
| `kto` | `{"prompt","completion","label": bool}` | kto |
| `plaintext` | `{"text"}` o `.txt` (1 doc/línea) | pretrain |
| `embedding` | `{"anchor","positive"[,"negative"]}` | embedding |
| `llava` / `sharegpt4v` | `image` + `conversations` (`<image>` en el turno) | sft vision |
| `audio` / `asr` | `audio`+`messages` / `audio`+`text` | sft audio / asr |
| `prm` | `{"prompt","completions":[..],"labels":[bool..]}` | prm |
| `raft` | docs dorados + distractores con citas `[doc-N]` | sft RAFT |
| `pre_tokenized`, `input_output`, `video`, `multimodal`, `cross_encoder` | ver `docs/data.md` | |

Detalles que importan:

- Archivos: JSONL (objeto por línea), JSON (array), CSV, Parquet, TXT; UTF-8 con o sin BOM.
- Mezcla de formatos en un archivo: solo se admite "familia rica/pobre" (chatml+tool-calling → tool-calling);
  cualquier otra mezcla se rechaza pidiendo `data.format`.
- Fila malformada ⇒ **se descarta con aviso** (`Warning: N of M rows dropped`), no aborta; si quedan 0 filas, exit 1.
- Todo se normaliza a `{"messages": [...]}` (o prompt/chosen/rejected) antes de tokenizar. Con
  `train_on_responses_only: true` la máscara de pérdida se construye con la plantilla real del tokenizer
  (`loss_mask.py`); sin plantilla ⇒ error explícito (poner `data.chat_template`).
- **Qwen3 y `<think>`**: el razonamiento va dentro del contenido del assistant como
  `<think>\n...\n</think>\n\nrespuesta`; la plantilla de chat de Qwen3 lo renderiza como bloque de pensamiento
  en el **último** turno y lo elimina del historial. `split_thinking` está *staged* (no hace nada).
- Las rutas de medios se resuelven contra `image_dir/audio_dir` o la carpeta del JSONL; fuera de ahí se omiten.
- Para GRPO, las columnas originales se conservan y llegan a `reward_fn(**kwargs)`; `answer` se deriva del
  `output` alpaca o del último turno assistant. El gold debe marcar la respuesta (`#### 42`, `\boxed{}`,
  `The answer is`, o la respuesta sola en una línea); si no, la fila se rechaza antes de generar.

### Herramientas (`soup data …`)

`inspect`, `validate` (exit 0/2/3; `--min-valid-fraction`), `doctor` (compatibilidad con la plantilla de
chat del modelo, `--show-mask`), `lint` (preferencias), `clean` (sanitización no destructiva),
`convert --to`, `merge`, `dedup` (MinHash / `--semantic`), `stats`, `filter` (perplejidad/coherencia),
`sample` (random/diverse/hard), `split` (val/test, estratificado), `search/preview/download` (HF Hub),
`register/registry`, `push`, `demo`, `ingest` (PDF/DOCX/MD→JSONL), `preprocess` (tokenización AOT),
`recipe` (DAG), `mix` (optimizador de mezclas), `forge` (síntesis desde docs con procedencia),
`score/decontaminate/toxicity/langdetect/pii/educational`, `topics`, `canary insert|check`,
`generate` (síntesis con OpenAI/Anthropic/Ollama/vLLM/servidor; plantillas code/conversation/qa/preference/
reasoning; `--seed` ejemplos; `--quality-pipeline`), `augment`, `from-traces`, `gen-magpie`, `best-of-n`,
`evolve`, `persona-mix`, `brain-rot`, `active-sample`.

## 7. Entrenamiento: qué pasa en `soup train`

1. `load_config` (Pydantic; claves desconocidas y campos no leídos → error/aviso).
2. Resolución de `--resume`/`--hf-resume`, replay, `--find-lr`, flags de cloud/multi-GPU
   (`--gpus`, `--fsdp`, `--deepspeed`, `--nodes`…; re-ejecución bajo `accelerate launch`).
3. **Pre-flight de VRAM** (`commands/train.py::_hardware_fit_preflight` + `utils/hardware_fit.py`):
   precio de pesos por formato (4bit 0.5 B/param, 8bit 1.0, none 2.0, gptq/awq 0.55, mxfp4/fp8 2.0
   porque se des-cuantizan al cargar) + optimizador + gradientes + activaciones + 10 % margen; si no cabe,
   **se niega** (`--allow-oom-attempt` fuerza). Con `stream_layers` el predictor es otro (ajustado a
   medidas, nunca sub-predice en seq ≤ 512; ver §8).
4. Carga de datos (`data/loader.py`), detección de formato, split de validación, aviso de filas descartadas.
5. `trainer/dispatch.py::build_trainer(cfg)` → wrapper por task (MLX primero si `backend: mlx`):

| task | wrapper | sobre |
|---|---|---|
| sft | `trainer/sft.py::SFTTrainerWrapper` (113 KB; text/vision/audio; streaming via `StreamingSetupMixin`) | TRL SFTTrainer |
| dpo / ipo / simpo / orpo / bco / kto / preference | `dpo.py`, `ipo.py`, `simpo.py`, `orpo.py`, `bco.py`, `kto.py`, `preference.py` | TRL (sondas en `_trl_compat.py`; orpo/cpo/bco caen a `trl.experimental` en ≥0.29) |
| online_dpo | `online_dpo.py` (+ `online_dpo_ranking.py`) | TRL + judge/RM en el bucle |
| grpo | `grpo.py` (+ `rewards.py`, variantes, PRM-guided) | TRL GRPOTrainer |
| ppo / reward_model | `ppo.py`, `reward_model.py` | TRL |
| pretrain | `pretrain.py` | HF Trainer (siempre LoRA; full FT vía LISA) |
| embedding | `embedding.py` | contrastive/triplet/cosine |
| distill | `distill.py` | KL por tokens / secuencia, ULD cross-tokenizer, MiniLLM |
| prm | `prm.py` | full FT fp32 |
| classifier / reranker / cross_encoder | `classifier.py` | AutoModelForSequenceClassification |
| unlearn | `unlearn.py` | NPO / SimNPO / RMU |
| moe_lora_routing | `mole_routing.py` | gate sobre N LoRAs congelados |
| tts | `tts.py` / `csm.py` (Sesame) | codec tokens |
| asr | `asr.py` | Whisper Seq2SeqTrainer |
| cualquiera con `backend: mlx` | `mlx_sft.py`, `mlx_dpo.py`, `mlx_grpo.py` vía `mlx_routing.py` | mlx-lm |

6. `wrapper.setup()`: tokenizer (+ override de plantilla), modelo (dtype del checkpoint para base congelada;
   fp32 para base entrenable; fp16 en pre-Ampere), cuantización (§8), PEFT (`peft_builder.py`:
   `target_modules: auto` → módulos lineales de atención/MLP según familia), kernels opcionales,
   callbacks (`monitoring/callback.py`: panel rich + tracker SQLite + loss watchdog + eval gate + rewind log +
   push a HF por checkpoint).
7. `wrapper.train()` → `./output` con `adapter_config.json` + `adapter_model.safetensors` (LoRA) o modelo
   completo (full FT / ReLoRA / MLX). Val loss al final de cada época o cada `eval_steps`.
8. Post: auto-eval (`eval.auto_eval`), `--diagnose`, annex-xi/repro-receipt/energy si se pidieron, registro
   del run (`soup runs`).

Backends: `transformers` (default, todo), `unsloth` (`[fast]`; SFT texto, DPO, GRPO, PPO, KTO, ORPO, SimPO,
IPO, BCO, preference, pretrain, embedding, TTS; solo `4bit`/`none`), `mlx` (Apple Silicon; sft/dpo/grpo).
Multi-GPU: `--gpus N`, `--fsdp full_shard`, `--deepspeed zero1|zero2|zero3|zero++|<json>`, `--nodes`.

## 8. Memoria y cuantización (lo que decide si cabe en tu GPU)

**Quant Menu** (`training.quantization`): `4bit` (BNB NF4, QLoRA, default), `8bit`, `none`, `gptq`, `awq`,
`hqq:1..8bit`, `aqlm` (2-bit), `eetq` (8-bit), `mxfp4` y `fp8` (checkpoints pre-cuantizados, se des-cuantizan
a bf16 al cargar: presupuesta 2 B/param), `bitnet_1.58` (reservado, se rechaza). `quantization_aware`: solo
`fp8` (Ada+) o `quest` (experimental); `true` se rechaza. QAT int8 real **no existe**: entrena normal y
cuantiza al exportar.

**Dónde se va la VRAM en QLoRA**: pesos NF4 (~0.5 B/param) + `embed_tokens`/`lm_head` **sin cuantizar**
(bitsandbytes no los toca; en el camino residente `prepare_model_for_kbit_training` los sube a fp32, lo que en un
8B con vocabulario de 150k son ~5 GB solo de embeddings) + logits (`batch × seq × vocab × ~12 B`) + activaciones
+ LoRA/optimizador (pequeños). Palancas en orden: `max_length` ↓, `batch_size` 1 + `gradient_accumulation_steps` ↑,
`gradient_checkpointing: full`, `use_cut_ce` (elimina el tensor de logits; triplica el microbatch medido),
`stream_layers`, `backend: unsloth`.

**Layer streaming** (`training.stream_layers: true`, BETA, v0.72+): la base congelada vive en RAM (page-locked
cuando se puede) o en NVMe, y se copia **una capa decoder cada vez** a dos buffers de VRAM en un stream CUDA
paralelo; adapters+optimizador residen en VRAM. Cada capa se lee dos veces por paso (forward y recompute del
backward). Con `quantization: 4bit` la base se cuantiza **una vez, offline**, a un caché de shards NF4 (~4× menor)
y es **bit-exacta** frente a NF4 residente (test de regresión). Soportado: Llama, Qwen2/3, Qwen3.5 denso y MoE,
Qwen4-Exp, Mistral, Gemma 1/2/3-text, Phi/Phi3; tasks `sft`, `dpo`, `orpo`, `simpo`, `kto`; backend transformers,
text. `grpo`/`ppo` excluidos. Incompatible con `lora.r: 0`, mlx, unsloth-kernels (se apagan).
Medido: Llama-3.1-8B NF4 en RTX 3050 4 GB → 2.4-3.3 GB pico; Qwen2.5-14B-shape NF4 en RTX 5070 8 GB / 32 GB RAM
→ **2.94 GB pico** con store de 9.93 GB en RAM; coste ~1.4× frente a residente. Regla de tamaño (seq 512, batch 1,
8B vocab 128k): ~3.45 GB, **+~1.06 GB por cada 512 tokens más** (el término de logits domina; con vocab 152k,
~1.25 GB). El pre-flight de streaming refuerza esto y nombra las dos palancas (`batch_size`, `max_length`).
Windows/WDDM: un exceso no lanza OOM, **derrama a RAM y va 10× más lento**; por eso Soup niega en vez de avisar.

**Otros**: `gradient_checkpointing` por niveles; `activation_offloading: cpu|disk`; FP8 (Ada+, `[qat]`);
Cut Cross-Entropy (`[cce]`); Liger; FlashAttention; ring attention; batch `auto` estático o `probe` real;
`soup profile` estima antes; `soup bench train` mide y comprueba que de verdad entrena.

## 9. Después de entrenar

| Necesidad | Comando | Notas |
|---|---|---|
| Probar | `soup chat --model ./output [--base …] [--device cpu|cuda|cuda:N|mps] [-s system]` | detecta adapter por `adapter_config.json`; `/system`, `/clear` |
| Lote | `soup infer --model … --input p.jsonl --output r.jsonl [--batch-size N] [--cuda-graphs]` | `{"prompt"}` por línea |
| API | `soup serve --model … [--backend transformers|vllm|sglang|mii] [--adapters a=./x] [--kv-cache-type q8_0] [--structured-output json --json-schema s.json] [--speculative-decoding d] [--reasoning-parser deepseek-r1]` | `/v1/chat/completions` (SSE), `/v1/models`, `/health`, `/metrics`, `/v1/messages` (Anthropic-shape), `/v1/adapters/*`, tools |
| Fusionar | `soup merge --adapter ./output [--base …] [--dtype bfloat16] [--save-format 4bit]` | ReLoRA ya sale fusionado |
| GGUF | `soup export --model ./output|./merged --format gguf --quant q4_0|q4_k_m|q5_k_m|q8_0|f16|f32 [--deploy ollama] [--verbose] [--no-install-deps] [--llama-cpp DIR]` | clona llama.cpp **b5270** en `~/.soup/llama.cpp`; **hay que compilar `llama-quantize`** (`cmake -B build … --target llama-quantize`); no hacer `pip install -r requirements.txt` de llama.cpp (baja torch a CPU) |
| GGUF avanzado | `--format gguf-ud --gguf-flavour UD-Q4_K_XL|IQ4_NL|Q4_0_4_4… --calibration-data c.jsonl` | imatrix + quantize |
| Otros | `--format onnx | tensorrt | bitnet|tq1_0 | torchao --quant-config q.yaml` | awq/gptq deprecados (fuera en 0.77) |
| Ollama | `soup deploy ollama --model m.gguf --name x [--system … --template chatml --parameter temperature=0.7]`; `--list`, `--remove` | genera Modelfile |
| Alias | `soup quantize ./out --to gguf --bits 4` | solo imprime el `soup export` equivalente |
| Evaluar | `soup eval benchmark|custom|judge|auto|compare|leaderboard|human|gate|quant-check|design|…`, `soup diagnose <run>`, `soup ship --base … --adapter …` (SHIP/DON'T, exit 0/2) | |
| Registrar | `soup registry push --run-id … --name … --tag v1`, `soup card <id>`, `soup can pack …`, `soup adapters list|info|compare|diff|check|sign|verify|scan|merge` | |

Arquitecturas que el convertidor GGUF del pin b5270 acepta (`utils/llama_cpp_capabilities.json`):
Llama/Llama4, Mistral/Mistral3, Gemma 1/2/3, Phi/Phi3/PhiMoE, **Qwen2/Qwen2-MoE/Qwen2-VL/Qwen2.5-VL/Qwen3/Qwen3-MoE**,
RWKV6-Qwen2… **No Qwen3.5/3.6/3.8** (necesitan `--llama-cpp` apuntando a un checkout más nuevo; la verificación
entonces se hace sondeando ese convertidor, y la conversión es el juez final).

Dispositivo en `chat/infer/diff`: `cpu` = fp32 (7B ≈ 28 GB RAM), `cuda` = `device_map=auto` fp16 (puede derramar
a CPU), `cuda:N` = fijo, `mps` = fp16.

## 10. Comandos por área (resumen; lista completa en `docs/commands.md`)

- **Config/inicio**: `init`, `fetch`, `recipes list|show|use|search|verify`, `autopilot`, `advise`, `migrate`,
  `plan`/`apply`, `env lock|status|check|fix`, `completions`, `doctor`, `version`, `quickstart`.
- **Datos**: ver §6.
- **Entrenar**: `train` (+ `--replay`, `--gate`, `--push-as`, `--find-lr`, `--tracker mlflow|swanlab|trackio`,
  `--tensorboard`, `--wandb`, `--profile`, `--annex-xi`, `--track-energy`, `--repro-receipt`, `--cloud`),
  `sweep`, `bench train`, `profile`, `cost`, `tokenizer train`, `ra-dit`, `iterative-dpo`, `local-rl`,
  `draft measure|distill|list`, `reward synth|stress`, `shrink`, `spectrum scan`, `edit set|diff`, `steer`.
- **Runs**: `runs [show|compare|replay|clean|delete|curriculum-curve]`, `why`, `rewind`, `history`, `monitor`, `tui`, `ui`.
- **Inferencia/servir/exportar**: ver §9; `llama cli|server|quantize|gguf-split` (proxy a binarios llama.cpp).
- **Evaluación**: `eval *`, `diagnose`, `ship`, `ab`, `drift-alarm`, `tunability`, `probe sae-diff|sleeper|truth|harm|interference|pack`, `expect`.
- **Gobernanza**: `registry *`, `can *`, `card`, `adapters *`, `lock *`, `bom emit`, `attest emit|verify`,
  `airgap-bundle`, `audit-log`, `license-advisor`, `ci init`.
- **Integración**: `mcp serve`, `agent synth|train|eval`, `compile`, `compile-tools`, `distill-prompt`,
  `apple-adapter`, `build`, `ingest`, `prune-prompt`, `plugins`.

Códigos de salida de gates: `0` OK/SHIP · `2` gate fallido/regresión/DON'T SHIP · `3` error de uso/entrada ·
`1` error de runtime.

## 11. Tests y verificación

```bash
pip install -e ".[dev]"
ruff check src/soup_cli/ scripts/ tests/ benchmarks/
pytest tests/ -v --tb=short           # excluye smoke; cobertura mínima 77 % (addopts)
pytest -m unit                        # ciclo rápido
pytest -m smoke                       # descarga un modelo diminuto y entrena
pytest -m gpu --no-cov                # necesita CUDA; resultados se registran en benchmarks/gpu-test-runs.md
pytest tests/test_<area>.py -v        # por módulo
```

- Marcadores: `unit`, `integration`, `smoke`, `gpu`, `requires_symlink`, `requires_hardlink`.
- Sondas de hardware únicas en `tests/conftest.py` (`cuda_available()`); no escribir `torch.cuda.is_available()` en tests.
- Tests de contrato que vigilan el repo entero: cabeceras de licencia ajenas, parámetros Typer sin rellenar,
  floors de dependencias vs CI, `TRL_TASKS`, guardas de DeepSpeed por wrapper, etc.
- Commits convencionales `tipo(scope): asunto`; refactors "boy scout" en commit `refactor:` aparte.

## 12. Dónde buscar

| Pregunta | Ir a |
|---|---|
| ¿Existe el campo X y qué valores acepta? | `src/soup_cli/config/schema.py` (o `docs/config-reference.md` generado) |
| ¿Qué hace el comando X y sus flags? | `docs/commands.md` → `docs/cli-reference.md` → `src/soup_cli/commands/<x>.py` |
| ¿Cómo se detecta/convierte un formato de datos? | `src/soup_cli/data/formats.py` + `docs/data.md#data-formats` |
| ¿Cómo se construye la máscara de pérdida / plantilla de chat? | `data/sft_format.py`, `data/loss_mask.py`, `data/chat_templates.py` |
| ¿Qué trainer corre para un task? | `trainer/dispatch.py` → `trainer/<task>.py` |
| ¿Cabe en mi GPU? | `utils/hardware_fit.py`, `commands/train.py::_hardware_fit_preflight`, `docs/performance-and-quantization.md` |
| Layer streaming | `trainer/stream_setup.py`, `utils/layer_stream*.py`, `utils/layer_shard.py`, `benchmarks/gate-v0.72.*`, `gate-901-14b-on-8gb.md` |
| Cuantización al entrenar | `utils/quant_menu.py`; al exportar `commands/export.py`, `utils/gguf_quant.py`, `utils/save_formats.py` |
| Servir | `commands/serve.py` (109 KB), `utils/vllm.py`, `utils/sglang.py`, `utils/structured_output.py` |
| Ollama | `utils/ollama.py`, `commands/deploy.py` |
| Recetas por modelo | `recipes/catalog.py` (170), `docs/models.md` |
| Tracker de runs / registro | `experiment/tracker.py`, `registry/store.py` |
| Cómo contribuir un trainer/formato/comando | `CONTRIBUTING.md` (secciones "Adding a …") |
| Números medidos reales | `benchmarks/README.md` y los `gate-*.md` / `probe-*.md` |

## 13. Trampas conocidas (resumen de issues cerrados que siguen vigentes)

- `prepare_model_for_kbit_training` sube embeddings/norms/lm_head a fp32 en el camino QLoRA residente; en modelos
  con vocabulario grande (Qwen 150k) eso pesa más que todo el decoder NF4. Streaming no lo hace.
- Pre-Ampere (T4/RTX 20xx) no tiene bf16: Soup usa fp16 y sube los LoRA a fp32 (`align_trainable_dtype_for_fp16`).
- Windows: wheel de torch de PyPI es CPU-only (`soup doctor` imprime el `pip install` correcto); WDDM derrama VRAM a RAM sin error.
- Qwen3.5+ son multimodales: Soup carga solo el decoder de texto (`modality: text`); no es fine-tune multimodal.
- `data.max_length` default 2048 es demasiado para 4-8 GB con vocab grande; baja a 512-1024 o usa CCE.
- GRPO: `grpo_beta: 0` = sin KL y sin forward de referencia; variantes no estándar ahora sí aplican `grpo_beta` (v0.76).
- `batch_size` debe ser múltiplo de `num_generations` en GRPO.
- `soup merge --save-format 4bit` guarda BNB-4bit en una sola etapa (sin dequant/merge/requant).
- `--trust-remote-code` es opt-in en todos los comandos; con streaming solo afecta al tokenizer.
- `awq`/`gptq` desaparecen en v0.77; destino: `gguf`, `onnx`, `tensorrt`, `bitnet`.
- `.soup/` (tracker, caches) y `*.db` están en .gitignore; `~/.soup/` guarda llama.cpp, batch_cache, audit log.
