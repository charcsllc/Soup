#!/usr/bin/env python3
"""Cuenta tokens reales (plantilla de chat de Qwen3 incluida) y dice cuántas filas truncaría `max_length`.

Uso (necesita `transformers`, que viene con `pip install "soup-cli[train]"`):
    python entrenamiento/_fuentes/contar_tokens.py                       # todos los JSONL, límite 2048
    python entrenamiento/_fuentes/contar_tokens.py --max-length 1792
    python entrenamiento/_fuentes/contar_tokens.py entrenamiento/02_programacion/05_rust.jsonl

Una fila truncada pierde el final de la respuesta y su token de fin: el modelo aprende a cortar
a mitad de frase. Si un archivo trunca mucho, sube `data.max_length` (si el pre-flight de VRAM lo
acepta) o quita esas filas para esa etapa.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def tokens_de_fila(tokenizer, fila: dict) -> int:
    if "messages" in fila:
        ids = tokenizer.apply_chat_template(fila["messages"], tokenize=True)
    else:  # alpaca (GRPO): instrucción como usuario, salida como asistente
        mensajes = [
            {"role": "user", "content": fila["instruction"]},
            {"role": "assistant", "content": fila["output"]},
        ]
        ids = tokenizer.apply_chat_template(mensajes, tokenize=True)
    return len(ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archivos", nargs="*", type=Path)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--modelo", default="Qwen/Qwen3-8B")
    args = parser.parse_args()

    from transformers import AutoTokenizer  # import perezoso: solo hace falta aquí

    tokenizer = AutoTokenizer.from_pretrained(args.modelo)
    archivos = args.archivos or sorted(RAIZ.glob("0*/*.jsonl"))
    todos: list[int] = []
    print(f"{'archivo':58s} {'filas':>5s} {'mediana':>7s} {'máx':>6s} {'> límite':>9s}")
    for ruta in archivos:
        filas = [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]
        longitudes = [tokens_de_fila(tokenizer, fila) for fila in filas]
        todos += longitudes
        exceden = sum(n > args.max_length for n in longitudes)
        nombre = str(ruta.relative_to(RAIZ)) if ruta.is_relative_to(RAIZ) else str(ruta)
        print(f"{nombre:58s} {len(filas):5d} {int(statistics.median(longitudes)):7d} {max(longitudes):6d} {exceden:9d}")
    exceden = sum(n > args.max_length for n in todos)
    print(f"\nTotal: {len(todos)} filas, {exceden} ({exceden / len(todos):.1%}) superan max_length={args.max_length}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
