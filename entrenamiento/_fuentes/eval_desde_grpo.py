#!/usr/bin/env python3
"""Convierte filas del dataset GRPO (alpaca con `#### respuesta`) en tareas de `soup eval custom`.

Uso:
    python3 -I entrenamiento/_fuentes/eval_desde_grpo.py [--ultimas N] [--salida RUTA]

Por defecto toma las 10 últimas filas de entrenamiento/03_razonamiento/05_grpo_verificable.jsonl
y escribe entrenamiento/eval/razonamiento_verificable.jsonl con filas
{"prompt", "expected", "scoring": "answer", "category"}. `scoring: answer` compara la
respuesta final con el mismo parser que el reward `accuracy` de GRPO, así que basta con que
el modelo termine su solución con una línea `#### <respuesta>`.

Si luego entrenas la etapa GRPO con el archivo completo, esas filas también se habrán visto
en entrenamiento: evalúa antes del GRPO, o quítalas del JSONL de entrenamiento.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "03_razonamiento" / "05_grpo_verificable.jsonl"
SALIDA = RAIZ / "eval" / "razonamiento_verificable.jsonl"
INDICACION = "\n\nResuelve paso a paso y termina con una línea exacta `#### <respuesta>`."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ultimas", type=int, default=10, help="cuántas filas finales usar")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()

    filas = [json.loads(linea) for linea in ORIGEN.read_text(encoding="utf-8").splitlines() if linea.strip()]
    elegidas = filas[-args.ultimas:] if args.ultimas > 0 else filas
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, "w", encoding="utf-8", newline="\n") as destino:
        for fila in elegidas:
            tarea = {
                "prompt": fila["instruction"] + INDICACION,
                "expected": fila["output"],
                "scoring": "answer",
                "category": "razonamiento",
            }
            destino.write(json.dumps(tarea, ensure_ascii=False) + "\n")
    print(f"{len(elegidas)} tareas -> {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
