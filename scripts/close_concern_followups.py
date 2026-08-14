"""Cierra el SEGUIMIENTO proactivo de las inquietudes, sin borrar ninguna.

Marca `seguimiento_cerrado` en los documentos de `user_concerns`. El avatar deja
de proponerlas (`ConcernStore.list_recent_open_for_user` las omite), pero el dato
sigue intacto para el informe diario (`list_for_day`) y para las atenciones del
Admin UI (`list_recent`): el punto de dolor del ciudadano no se pierde.

Pensado para dejar el sistema sin avisos pendientes tras una tanda de pruebas.
Las inquietudes que se registren DESPUÉS no llevan la marca, así que el
seguimiento proactivo vuelve a funcionar con normalidad para casos nuevos.

Uso:
    python -m scripts.close_concern_followups              # dry-run: sólo reporta
    python -m scripts.close_concern_followups --apply      # escribe en Firestore
    python -m scripts.close_concern_followups --user AGBXMBMQ --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from google.cloud import firestore

from app.config import settings

BATCH_SIZE = 400


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Escribe en Firestore (por defecto sólo reporta)")
    parser.add_argument("--user", default=None,
                        help="Cerrar sólo las de un usuario (código o id de sesión)")
    args = parser.parse_args()

    db = settings.firestore_database
    client = firestore.Client(
        project=settings.gcp_project_id,
        database=None if db in ("(default)", "", None) else db,
    )
    collection = client.collection(settings.firestore_concerns_collection)

    pendientes = []
    for snap in collection.stream():
        data = snap.to_dict() or {}
        if data.get("seguimiento_cerrado"):
            continue
        if args.user and str(data.get("user_id")) != args.user:
            continue
        pendientes.append((snap.reference, data))

    print(f"inquietudes con seguimiento abierto: {len(pendientes)}")
    for tipo, n in Counter(str(d.get("tipo")) for _, d in pendientes).most_common():
        print(f"  {tipo:16} {n}")
    for usuario, n in Counter(str(d.get("user_id")) for _, d in pendientes).most_common(5):
        print(f"  usuario {usuario:26} {n}")

    if not args.apply:
        print("\nDRY-RUN: no se escribió nada. Repite con --apply.")
        return 0

    batch = client.batch()
    pending = 0
    written = 0
    for ref, _ in pendientes:
        batch.set(ref, {"seguimiento_cerrado": True,
                        "seguimiento_cerrado_at": firestore.SERVER_TIMESTAMP},
                  merge=True)
        pending += 1
        written += 1
        if pending >= BATCH_SIZE:
            batch.commit()
            batch = client.batch()
            pending = 0
    if pending:
        batch.commit()

    print(f"\nCerradas {written} inquietudes (el dato se conserva íntegro).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
