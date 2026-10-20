#!/usr/bin/env python3
"""Convierte un módulo fuente (ROWS = [...]) en JSONL y lo valida.

Uso:
    python3 -I entrenamiento/_fuentes/generar.py entrenamiento/_fuentes/02_programacion/02_python.py
    python3 -I entrenamiento/_fuentes/generar.py --solo-validar entrenamiento/02_programacion/02_python.jsonl
    python3 -I entrenamiento/_fuentes/generar.py --todo          # regenera y valida todos los .py

El JSONL de salida se escribe en entrenamiento/<categoria>/<nombre>.jsonl, es decir,
el espejo de _fuentes/<categoria>/<nombre>.py sin el prefijo _fuentes.

Formato aceptado por fila (lo mismo que detecta `soup data validate`):
  - chatml : {"messages": [{"role": "system"|"user"|"assistant", "content": str}, ...]}
  - alpaca : {"instruction": str, "input": str, "output": str}   (solo para GRPO verificable)

Reglas que se comprueban (y que hacen fallar la generación):
  - JSON válido, un objeto por línea, UTF-8.
  - chatml: primer mensaje system opcional; después alternancia estricta user/assistant;
    termina en assistant; contenidos no vacíos.
  - Sin bloques <think>...</think> en ningún mensaje: el razonamiento va visible en la
    respuesta (ver GUIA_DE_ESTILO.md §5).
  - Sin duplicados exactos del primer mensaje de usuario dentro del archivo.
  - Sin marcadores de relleno (TODO/FIXME en mayúsculas, "lorem ipsum", "[inserte") ni
    frases de chatbot ("como modelo de lenguaje", "as an ai").
  - Mínimo de filas (por defecto 20; 30 para el GRPO).
Sin dependencias externas: solo biblioteca estándar.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent  # entrenamiento/
FUENTES = RAIZ / "_fuentes"
MIN_FILAS = 20
MIN_FILAS_GRPO = 30
PROHIBIDO = (
    "como modelo de lenguaje", "as an ai", "as a language model", "lorem ipsum",
    "[inserte", "[insert", "<placeholder>",
)
# Marcadores de trabajo pendiente: solo en mayúsculas y como palabra completa, para no
# confundir «Método:» o «todo» con un TODO de código.
RE_PENDIENTE = re.compile(r"\b(TODO|FIXME)\b")
RE_THINK_OPEN = re.compile(r"<think>")
RE_THINK_CLOSE = re.compile(r"</think>")


def _es_str_no_vacio(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _validar_think(contenido: str, pos: int, es_ultimo: bool, fila: int) -> list[str]:
    """Rechaza cualquier bloque <think>: el método debe ir visible en la respuesta."""
    if RE_THINK_OPEN.search(contenido) or RE_THINK_CLOSE.search(contenido):
        return [
            f"fila {fila}: el mensaje {pos} contiene <think>; quita el bloque y deja solo la "
            "respuesta (el razonamiento va visible en el texto, GUIA_DE_ESTILO.md §5)"
        ]
    return []


def _validar_chatml(fila: dict, numero: int) -> list[str]:
    errores: list[str] = []
    mensajes = fila.get("messages")
    if not isinstance(mensajes, list) or not mensajes:
        return [f"fila {numero}: 'messages' debe ser una lista no vacía"]
    inicio = 0
    if mensajes[0].get("role") == "system":
        if not _es_str_no_vacio(mensajes[0].get("content")):
            errores.append(f"fila {numero}: system vacío")
        inicio = 1
    esperado = "user"
    for pos in range(inicio, len(mensajes)):
        msg = mensajes[pos]
        if not isinstance(msg, dict):
            errores.append(f"fila {numero}: mensaje {pos} no es un objeto")
            continue
        rol, contenido = msg.get("role"), msg.get("content")
        if rol != esperado:
            errores.append(f"fila {numero}: mensaje {pos} tiene rol '{rol}', se esperaba '{esperado}'")
        if not _es_str_no_vacio(contenido):
            errores.append(f"fila {numero}: mensaje {pos} con contenido vacío")
            contenido = ""
        if rol == "assistant":
            errores += _validar_think(contenido, pos, pos == len(mensajes) - 1, numero)
        esperado = "assistant" if esperado == "user" else "user"
    if mensajes[-1].get("role") != "assistant":
        errores.append(f"fila {numero}: la conversación debe terminar en assistant")
    bruto = json.dumps(mensajes, ensure_ascii=False)
    texto = bruto.lower()
    for marca in PROHIBIDO:
        if marca in texto:
            errores.append(f"fila {numero}: contiene texto prohibido {marca!r}")
    if RE_PENDIENTE.search(bruto):
        errores.append(f"fila {numero}: contiene un marcador TODO/FIXME; el código debe estar completo")
    return errores


def _validar_alpaca(fila: dict, numero: int) -> list[str]:
    errores: list[str] = []
    for campo in ("instruction", "output"):
        if not _es_str_no_vacio(fila.get(campo)):
            errores.append(f"fila {numero}: alpaca.{campo} vacío")
    if "input" in fila and not isinstance(fila["input"], str):
        errores.append(f"fila {numero}: alpaca.input debe ser str")
    salida = fila.get("output") or ""
    if not re.search(r"^#### .*\S\s*$", salida, flags=re.M):
        errores.append(f"fila {numero}: la salida GRPO debe terminar con una línea '#### <respuesta>'")
    return errores


def validar_filas(filas: list[dict], es_grpo: bool) -> list[str]:
    errores: list[str] = []
    minimo = MIN_FILAS_GRPO if es_grpo else MIN_FILAS
    if len(filas) < minimo:
        errores.append(f"solo {len(filas)} filas; mínimo {minimo}")
    vistos: set[str] = set()
    for numero, fila in enumerate(filas, start=1):
        if not isinstance(fila, dict):
            errores.append(f"fila {numero}: no es un objeto JSON")
            continue
        if "messages" in fila:
            errores += _validar_chatml(fila, numero)
            primero = next((m.get("content", "") for m in fila["messages"] if m.get("role") == "user"), "")
        elif "instruction" in fila:
            errores += _validar_alpaca(fila, numero)
            primero = fila.get("instruction", "")
        else:
            errores.append(f"fila {numero}: ni 'messages' ni 'instruction'")
            continue
        clave = " ".join(str(primero).split()).lower()
        if clave in vistos:
            errores.append(f"fila {numero}: prompt de usuario duplicado")
        vistos.add(clave)
    return errores


def cargar_fuente(ruta: Path) -> list[dict]:
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    if spec is None or spec.loader is None:
        raise SystemExit(f"no se pudo cargar {ruta}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    filas = getattr(modulo, "ROWS", None)
    if not isinstance(filas, list):
        raise SystemExit(f"{ruta}: debe definir ROWS = [...]")
    return filas


def destino_de(fuente: Path) -> Path:
    relativa = fuente.resolve().relative_to(FUENTES.resolve())
    return (RAIZ / relativa).with_suffix(".jsonl")


def escribir_jsonl(filas: list[dict], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".jsonl.tmp")
    with open(temporal, "w", encoding="utf-8", newline="\n") as salida:
        for fila in filas:
            salida.write(json.dumps(fila, ensure_ascii=False) + "\n")
    os.replace(temporal, destino)


def leer_jsonl(ruta: Path) -> list[dict]:
    filas: list[dict] = []
    with open(ruta, encoding="utf-8") as entrada:
        for numero, linea in enumerate(entrada, start=1):
            if not linea.strip():
                continue
            try:
                filas.append(json.loads(linea))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{ruta}:{numero}: JSON inválido: {exc}") from exc
    return filas


def _estadisticas(filas: list[dict]) -> str:
    total_chars = 0
    con_think = 0
    multiturno = 0
    for fila in filas:
        if "messages" in fila:
            total_chars += sum(len(m.get("content", "")) for m in fila["messages"])
            ultimo = fila["messages"][-1].get("content", "")
            con_think += "<think>" in ultimo
            multiturno += sum(1 for m in fila["messages"] if m.get("role") == "user") > 1
        else:
            total_chars += len(fila.get("instruction", "")) + len(fila.get("output", ""))
    media = total_chars // max(1, len(filas))
    return f"{len(filas)} filas · ~{media} caracteres/fila · {con_think} con <think> · {multiturno} multiturno"


def procesar_fuente(fuente: Path) -> int:
    fuente = fuente.resolve()
    try:
        filas = cargar_fuente(fuente)
    except SyntaxError as exc:
        print(f"[ERROR] {fuente.relative_to(RAIZ)}: no es Python válido (línea {exc.lineno}): {exc.msg}")
        return 1
    except Exception as exc:  # noqa: BLE001 - un fallo al importar la fuente no debe parar --todo
        print(f"[ERROR] {fuente.relative_to(RAIZ)}: no se pudo cargar: {type(exc).__name__}: {exc}")
        return 1
    es_grpo = "grpo" in fuente.stem
    errores = validar_filas(filas, es_grpo)
    destino = destino_de(fuente)
    if errores:
        print(f"[ERROR] {fuente.relative_to(RAIZ)} -> {len(errores)} problema(s):")
        for error in errores[:40]:
            print("   -", error)
        if len(errores) > 40:
            print(f"   ... y {len(errores) - 40} más")
        return 1
    escribir_jsonl(filas, destino)
    print(f"[OK] {destino.relative_to(RAIZ)}: {_estadisticas(filas)}")
    return 0


def solo_validar(ruta: Path) -> int:
    ruta = ruta.resolve()
    filas = leer_jsonl(ruta)
    errores = validar_filas(filas, "grpo" in ruta.stem)
    if errores:
        print(f"[ERROR] {ruta}: {len(errores)} problema(s):")
        for error in errores[:40]:
            print("   -", error)
        return 1
    print(f"[OK] {ruta}: {_estadisticas(filas)}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--todo":
        fuentes = sorted(p for p in FUENTES.rglob("*.py") if not p.name.startswith("_") and p.name != "generar.py")
        return max((procesar_fuente(f) for f in fuentes), default=0)
    if argv[0] == "--solo-validar":
        return max((solo_validar(Path(r)) for r in argv[1:]), default=0)
    return max((procesar_fuente(Path(r)) for r in argv), default=0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
