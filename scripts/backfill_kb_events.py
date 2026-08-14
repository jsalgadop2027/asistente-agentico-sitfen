"""Backfill puntual de `kb_events`: drena la cola de avisos y siembra `content_hash`.

Contexto (agosto 2026). El avatar web anunciaba "acabo de incorporar un documento
nuevo" en sesión tras sesión: `latest_pending()` devuelve UN evento por sesión y
había 147 pendientes acumulados de las cargas iniciales del corpus (ninguno era
novedad real; el más reciente tenía 17 días). `KBEventStore.record_ingestion` ya
no reabre avisos al reingestar contenido idéntico, pero esa guarda no drena lo
que ya estaba en cola. Este script hace tres cosas, sólo sobre `kb_events`:

1. **Borra eventos huérfanos de logs** — `log-<uuid>.txt` ingestados por error,
   ya eliminados del índice vectorial. Su evento seguía vivo, así que el avatar
   los anunciaba por nombre y, ante un "Sí", `presentar_documento_nuevo` no podía
   recuperar contenido alguno.
2. **Marca como anunciados** los avisos pendientes restantes.
3. **Siembra `content_hash`** copiándolo del índice vectorial, para que la
   próxima ingesta del corpus completo no vuelva a marcarlos como novedad (la
   guarda de `record_ingestion` compara justamente ese campo).

No toca el índice vectorial ni `updated_at` (mover `updated_at` rehabilitaría la
difusión por WhatsApp, ver `KBEventStore.claim_broadcast`).

Uso:
    python -m scripts.backfill_kb_events            # dry-run: sólo reporta
    python -m scripts.backfill_kb_events --apply    # escribe en Firestore
"""
from __future__ import annotations

import argparse
import sys

from google.cloud import firestore

from app.config import settings
from app.firestore_store import FirestoreVectorStore

BATCH_SIZE = 400


def _client() -> firestore.Client:
    db = settings.firestore_database
    return firestore.Client(
        project=settings.gcp_project_id,
        database=None if db in ("(default)", "", None) else db,
    )


def _is_orphan_log(source: str) -> bool:
    """`log-<uuid>.txt` de la ingesta accidental del 29-jun-2026."""
    low = source.lower()
    return low.startswith("log-") and low.endswith(".txt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Escribe en Firestore (por defecto sólo reporta)")
    args = parser.parse_args()

    client = _client()
    collection = client.collection(settings.firestore_kb_events_collection)
    events = [(s.reference, s.to_dict() or {}) for s in collection.stream()]
    events = [(ref, d) for ref, d in events if d.get("source")]

    hashes = {r["source"]: r.get("content_hash") for r in
              FirestoreVectorStore().list_sources()}

    to_delete, to_announce, to_hash = [], [], []
    for ref, data in events:
        source = data["source"]
        indexed = source in hashes
        if not indexed and _is_orphan_log(source):
            to_delete.append((ref, source))
            continue
        if not data.get("announced", False):
            to_announce.append((ref, source))
        wanted = hashes.get(source)
        if wanted and data.get("content_hash") != wanted:
            to_hash.append((ref, wanted))

    print(f"eventos={len(events)}  fuentes indexadas={len(hashes)}")
    print(f"  a borrar (logs huérfanos): {len(to_delete)}")
    print(f"  a marcar como anunciados : {len(to_announce)}")
    print(f"  a sembrar content_hash   : {len(to_hash)}")
    for _, source in to_delete:
        print(f"    borrar: {source}")

    if not args.apply:
        print("\nDRY-RUN: no se escribió nada. Repite con --apply.")
        return 0

    batch = client.batch()
    pending = 0

    def flush(force: bool = False) -> None:
        nonlocal batch, pending
        if pending and (force or pending >= BATCH_SIZE):
            batch.commit()
            batch = client.batch()
            pending = 0

    for ref, _ in to_delete:
        batch.delete(ref)
        pending += 1
        flush()
    for ref, _ in to_announce:
        batch.set(ref, {"announced": True,
                        "announced_at": firestore.SERVER_TIMESTAMP}, merge=True)
        pending += 1
        flush()
    for ref, wanted in to_hash:
        # Sin `updated_at`: no debe reabrir la difusión por WhatsApp.
        batch.set(ref, {"content_hash": wanted}, merge=True)
        pending += 1
        flush()
    flush(force=True)

    print("\nAplicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
