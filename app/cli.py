"""CLI de prueba del agente (sin WhatsApp). Útil para verificación local.

Uso:
    python -m app.cli                      # modo interactivo
    python -m app.cli "¿Qué documentos necesito para exportar arándano a China?"
"""
from __future__ import annotations

import sys
import uuid

from app.observability import configure_observability


def main() -> int:
    configure_observability()
    from app.agent.orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    # ID único por proceso (no un valor fijo compartido): user_id gobierna la
    # memoria conversacional en Firestore (un documento por usuario, persistido
    # indefinidamente) y el rate limiting. Un "cli-tester" fijo haría que todas
    # las corridas del CLI, de cualquier persona y en cualquier momento, lean y
    # escriban sobre el mismo historial y compartan el mismo cupo de consultas
    # — justo lo contrario de una herramienta de verificación local.
    user_id = f"cli-tester-{uuid.uuid4().hex[:8]}"

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(orchestrator.answer(user_id, query).text)
        return 0

    print("SITFEN — Asistente conversacional de Información Temprana (escribe 'salir' para terminar)\n")
    while True:
        try:
            query = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() in ("salir", "exit", "quit"):
            break
        if not query:
            continue
        print(f"\nAru: {orchestrator.answer(user_id, query).text}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
