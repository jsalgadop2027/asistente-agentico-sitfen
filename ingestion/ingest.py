"""Orquestador de ingesta: PDF -> chunks -> embeddings -> Firestore.

Uso:
    # Vista previa local sin tocar la nube (sin costo):
    python -m ingestion.ingest --source local --folder "Corpus Documental" --dry-run

    # Ingesta real desde carpeta local a Firestore:
    python -m ingestion.ingest --source local --folder "Corpus Documental"

    # Ingesta desde un bucket de GCS (usado por el Cloud Run Job / Admin UI):
    python -m ingestion.ingest --source gcs --bucket chatbot-agentico-v2-corpus

    # Re-ingesta de un solo PDF (reemplaza sus chunks):
    python -m ingestion.ingest --source gcs --bucket BUCKET --blob nuevo.pdf --replace

Diseñado para correr como Cloud Run Job (batch) — equilibrio serverless/batch.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
import time
from typing import Iterable

from ingestion.chunking import Chunk, chunk_document
from ingestion.loaders import (
    LoadedDocument,
    load_gcs_documents,
    load_local_documents,
    load_single_gcs_document,
    load_url,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")

EMBED_BATCH = 32


class DuplicateContentError(Exception):
    """El contenido a ingestar ya existe en el índice bajo otra fuente."""


def compute_content_hash(full_text: str) -> str:
    """Hash estable del contenido de un documento, para detectar duplicados.

    Se normaliza (espacios colapsados, sin distinción de mayúsculas) para que
    diferencias triviales de formato no eviten detectar el mismo contenido.
    """
    normalized = re.sub(r"\s+", " ", full_text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _iter_chunks(docs: Iterable[LoadedDocument]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        doc_chunks = list(chunk_document(doc.source, doc.title, doc.full_text))
        logger.info("  %-45s -> %3d chunks (%d páginas)", doc.source,
                    len(doc_chunks), len(doc.pages))
        chunks.extend(doc_chunks)
    return chunks


def _record_kb_events(chunks: list[Chunk], content_hashes: dict[str, str]) -> None:
    """Registra un aviso de novedad por cada documento vectorizado (para que el
    canal web anuncie por texto y voz que se incorporó información nueva).

    Se pasa el hash de contenido para que reingestar un documento IDÉNTICO no
    vuelva a marcarlo como novedad (ver `KBEventStore.record_ingestion`)."""
    from app.kb_events import KBEventStore

    events = KBEventStore()
    by_source: dict[str, dict] = {}
    for c in chunks:
        entry = by_source.setdefault(c.source, {"title": c.title, "chunks": 0})
        entry["chunks"] += 1
    for source, info in by_source.items():
        events.record_ingestion(source, info["title"], info["chunks"],
                                content_hash=content_hashes.get(source, ""))


EMBED_MAX_RETRIES = 6
EMBED_BACKOFF_BASE_SECONDS = 20.0


def _embed_documents_with_backoff(embeddings, texts: list[str]) -> list[list[float]]:
    """Reintenta con backoff exponencial ante 429 RESOURCE_EXHAUSTED de Vertex AI.

    La cuota observada en producción se agota tras pocas requests seguidas
    (el retry interno de langchain/tenacity no basta); aquí se espera bastante
    más entre reintentos antes de golpear la API de nuevo.
    """
    for attempt in range(EMBED_MAX_RETRIES):
        try:
            return embeddings.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            is_quota_error = "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc)
            if not is_quota_error or attempt == EMBED_MAX_RETRIES - 1:
                raise
            delay = EMBED_BACKOFF_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                "Cuota de embeddings agotada (intento %d/%d); esperando %.0fs antes de reintentar",
                attempt + 1, EMBED_MAX_RETRIES, delay,
            )
            time.sleep(delay)
    raise RuntimeError("No debería alcanzarse")  # pragma: no cover


def _embed_and_upsert(chunks: list[Chunk], *, replace_sources: set[str],
                      content_hashes: dict[str, str]) -> int:
    # Imports perezosos: sólo se cargan en ingesta real (requieren GCP).
    from app.agent.models import get_embeddings
    from app.firestore_store import FirestoreVectorStore

    embeddings = get_embeddings()
    store = FirestoreVectorStore()

    for source in replace_sources:
        removed = store.delete_by_source(source)
        if removed:
            logger.info("Reemplazo: eliminados %d chunks previos de %s", removed, source)

    total = 0
    for i in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[i : i + EMBED_BATCH]
        vectors = _embed_documents_with_backoff(embeddings, [c.text for c in batch])
        payloads = [
            {
                "source": c.source,
                "title": c.title,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "tokens": c.tokens,
                "content_hash": content_hashes.get(c.source),
                "embedding": vec,
            }
            for c, vec in zip(batch, vectors)
        ]
        total += store.upsert_chunks(payloads)
        logger.info("Subidos %d/%d chunks", total, len(chunks))
        time.sleep(2.0)  # cortesía con cuotas de la API

    # Aviso de novedad para el canal web (texto + voz). No debe tumbar la ingesta.
    try:
        _record_kb_events(chunks, content_hashes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo registrar el evento de novedad: %s", exc)
    return total


def run(args: argparse.Namespace) -> int:
    t0 = time.time()
    if getattr(args, "url", None):
        single = load_url(args.url)
        docs = [single] if single else []
    elif args.source == "local":
        docs = list(load_local_documents(args.folder))
    elif args.blob:
        single = load_single_gcs_document(args.bucket, args.blob)
        docs = [single] if single else []
    else:
        docs = list(load_gcs_documents(args.bucket, args.prefix))

    if not docs:
        logger.error("No se cargaron documentos. Revisa la ruta/bucket.")
        return 1

    logger.info("Documentos cargados: %d", len(docs))

    # Políticas de contenido sobre el texto extraído antes de generar
    # chunks/embeddings: (1) PII (redactar/bloquear/avisar) y (2) anti-inyección /
    # data-poisoning (neutralizar instrucciones adversarias embebidas).
    from ingestion.validation import apply_injection_policy, apply_pii_policy

    for d in docs:
        d.pages = [
            apply_injection_policy(apply_pii_policy(p, source=d.source), source=d.source)
            for p in d.pages
        ]

    chunks = _iter_chunks(docs)
    total_tokens = sum(c.tokens for c in chunks)
    logger.info("Total chunks: %d | tokens aprox: %d", len(chunks), total_tokens)

    if args.dry_run:
        logger.info("DRY-RUN: no se generan embeddings ni se escribe en Firestore.")
        logger.info("Costo estimado embeddings (~%d tokens): centavos de USD.",
                    total_tokens)
        return 0

    # --- Control de duplicados por hash de contenido (sólo ingesta real) ---
    content_hashes = {d.source: compute_content_hash(d.full_text) for d in docs}
    if not getattr(args, "allow_duplicates", False):
        from app.firestore_store import FirestoreVectorStore

        store = FirestoreVectorStore()
        kept_sources: set[str] = set()
        duplicates: list[tuple[str, str]] = []
        for d in docs:
            existing = store.find_source_by_content_hash(content_hashes[d.source])
            if existing and existing != d.source:
                duplicates.append((d.source, existing))
                logger.warning(
                    "Duplicado por contenido: «%s» coincide con «%s» (ya indexado). Se omite.",
                    d.source, existing,
                )
            else:
                kept_sources.add(d.source)
        if duplicates and not kept_sources:
            src, existing = duplicates[0]
            raise DuplicateContentError(
                f"El contenido de «{src}» ya está indexado como «{existing}»; no se reingestó."
            )
        if duplicates:
            docs = [d for d in docs if d.source in kept_sources]
            chunks = [c for c in chunks if c.source in kept_sources]

    replace_sources = {d.source for d in docs} if args.replace else set()
    written = _embed_and_upsert(chunks, replace_sources=replace_sources,
                                content_hashes=content_hashes)
    logger.info("Ingesta completa: %d chunks en %.1fs", written, time.time() - t0)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Ingesta del corpus al vector store Firestore.")
    p.add_argument("--source", choices=["local", "gcs"], default="local")
    p.add_argument("--folder", default="corpus_documental")
    p.add_argument("--bucket", default=None)
    p.add_argument("--prefix", default="")
    p.add_argument("--blob", default=None, help="Ingestar un único blob de GCS")
    p.add_argument("--url", default=None, help="Ingestar una única página web (scraping)")
    p.add_argument("--replace", action="store_true", help="Borra chunks previos de cada fuente")
    p.add_argument("--allow-duplicates", action="store_true",
                   help="Omite el control de duplicados por contenido (ingesta forzada)")
    p.add_argument("--dry-run", action="store_true", help="No toca la nube; sólo reporta")
    args = p.parse_args()

    if args.source == "gcs" and not args.bucket and not args.url:
        p.error("--bucket es obligatorio con --source gcs")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
