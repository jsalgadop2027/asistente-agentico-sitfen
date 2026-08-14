"""Chunking contextual consciente de oraciones, con solapamiento por tokens.

Estrategia RAG avanzada: se divide primero por párrafo y luego por oración
(regex consciente de puntuación/mayúsculas en español), empaquetando oraciones
de forma "greedy" hasta el tamaño máximo en tokens. El solape entre chunks se
lleva a nivel de oración completa (nunca a mitad de una), lo que evita cortar
hechos por la mitad frente al enfoque anterior de ventana de tokens pura.
Cada chunk lleva un encabezado contextual con el título del documento
prepended (contextual retrieval) para mejorar la recuperación.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")

CHUNK_TOKENS = 380
CHUNK_OVERLAP = 60
MIN_CHUNK_CHARS = 40

# Fin de oración (. ! ? …) seguido de espacio y una letra mayúscula/dígito/comilla
# de apertura — evita partir en abreviaturas o números decimales sueltos.
_SENTENCE_END_RE = re.compile(r'(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑ0-9¿¡"«])')
_PARAGRAPH_SPLIT_RE = re.compile(r'\n{2,}')


@dataclass
class Chunk:
    source: str
    title: str
    chunk_index: int
    text: str
    tokens: int


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _split_sentences(paragraph: str) -> list[str]:
    normalized = re.sub(r'\s+', ' ', paragraph).strip()
    if not normalized:
        return []
    return [p.strip() for p in _SENTENCE_END_RE.split(normalized) if p.strip()]


def _split_long_sentence(sentence: str, chunk_tokens: int) -> list[str]:
    """Fallback por ventana de tokens para texto sin puntuación (tablas, títulos
    mal extraídos) que ya excede el tamaño máximo por sí solo — nunca perdemos
    texto, aunque en ese caso puntual sí se corte a mitad de token."""
    tokens = _ENCODER.encode(sentence)
    pieces = []
    for i in range(0, len(tokens), chunk_tokens):
        piece = _ENCODER.decode(tokens[i:i + chunk_tokens]).strip()
        if piece:
            pieces.append(piece)
    return pieces


def _iter_units(full_text: str, chunk_tokens: int) -> Iterator[str]:
    """Genera "unidades" (oraciones, o fragmentos de una oración larga) en orden."""
    for paragraph in _PARAGRAPH_SPLIT_RE.split(full_text):
        for sentence in _split_sentences(paragraph):
            if _count_tokens(sentence) > chunk_tokens:
                yield from _split_long_sentence(sentence, chunk_tokens)
            else:
                yield sentence


def chunk_document(source: str, title: str, full_text: str,
                   *, chunk_tokens: int = CHUNK_TOKENS,
                   overlap: int = CHUNK_OVERLAP) -> Iterator[Chunk]:
    """Divide el texto en chunks por oración, empaquetados hasta chunk_tokens,
    con solape a nivel de oración completa entre chunks consecutivos."""
    units = list(_iter_units(full_text, chunk_tokens))
    if not units:
        return

    index = 0
    current: list[str] = []
    current_tokens = 0

    def _flush() -> Chunk | None:
        nonlocal index
        if not current:
            return None
        body = " ".join(current).strip()
        if len(body) < MIN_CHUNK_CHARS:
            return None
        contextual = f"[Documento: {title}]\n{body}"
        chunk = Chunk(
            source=source, title=title, chunk_index=index,
            text=contextual, tokens=_count_tokens(contextual),
        )
        index += 1
        return chunk

    for unit in units:
        unit_tokens = _count_tokens(unit)
        if current and current_tokens + unit_tokens > chunk_tokens:
            chunk = _flush()
            if chunk is not None:
                yield chunk
            # Solape: se llevan al siguiente chunk las últimas oraciones del
            # actual, hasta acumular ~`overlap` tokens (nunca a mitad de una).
            carried: list[str] = []
            carried_tokens = 0
            for sentence in reversed(current):
                t = _count_tokens(sentence)
                if carried_tokens + t > overlap:
                    break
                carried.insert(0, sentence)
                carried_tokens += t
            current, current_tokens = carried, carried_tokens
        current.append(unit)
        current_tokens += unit_tokens

    chunk = _flush()
    if chunk is not None:
        yield chunk
