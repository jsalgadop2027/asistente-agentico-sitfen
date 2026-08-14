# -*- coding: utf-8 -*-
"""Evalúa el clasificador de derivación a entidades públicas (`app.entity_catalog`)
contra `evaluation/derivation_golden.jsonl` (135 casos escritos a mano: 90
single-entidad nuevos por las 10 entidades del catálogo, 20 multi-entidad, 15 de
escalamiento por urgencia y 10 sin match/ambiguos — ninguno reutiliza literalmente
los ~15 ejemplos few-shot que ya viven en el prompt de `entity_catalog.py`, para no
medir memorización).

No usa RAGAS ni DeepEval: son frameworks de calidad de generación-con-contexto
(fidelidad, relevancia, precisión/recall del contexto recuperado) y esto es
clasificación multi-etiqueta contra un catálogo cerrado con la etiqueta correcta ya
conocida — se mide con precisión/recall/exactitud directos, sin juez LLM.

Reproduce el mismo orden que usa producción (`app/agent/tools/derivation_tools.py`):
primero `evaluar_urgencia(resumen)`, y su resultado se pasa a
`identificar_entidades(resumen, urgencia)`. Ninguna de las dos tiene efectos
secundarios (no envían correo ni escriben Firestore — eso vive aparte en
`app/derivation.py::send_derivation`, corriente abajo del gate de confirmación),
así que esta evaluación es segura en fase de pre-producción.

Requiere Vertex AI (credenciales con aiplatform.endpoints.predict) — pensado para
correr vía el Cloud Run Job arandano-eval (infra/08_deploy_eval_job.ps1).

Uso:
    python -m evaluation.derivation_eval
    python -m evaluation.derivation_eval --out local.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
DATASET_PATH = HERE / "derivation_golden.jsonl"

EMERGENCY_IDS = {"indeci", "senamhi"}


def load_golden(path: Path = DATASET_PATH) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _urgencia_id(nombre: str) -> str:
    """`identificar_entidades` devuelve NOMBRES de despliegue (p.ej. "SENAMHI /
    ENFEN"), pero el golden dataset usa los ids internos del catálogo (p.ej.
    "senamhi") para no acoplarse al texto exacto de display. Reconstruye el id
    a partir del catálogo real, no de una tabla duplicada a mano."""
    from app.entity_catalog import ENTITY_CATALOG

    by_name = {e.nombre: e.id for e in ENTITY_CATALOG}
    return by_name.get(nombre, nombre)


def run_case(case: dict) -> dict:
    from app.entity_catalog import evaluar_urgencia, identificar_entidades

    resumen = case["resumen"]
    urgencia_detectada = evaluar_urgencia(resumen)
    entidades_nombres = identificar_entidades(resumen, urgencia_detectada)
    entidades_detectadas = {_urgencia_id(n) for n in entidades_nombres}
    expected = set(case["expected_entidades"])

    tp = entidades_detectadas & expected
    fp = entidades_detectadas - expected
    fn = expected - entidades_detectadas

    precision = len(tp) / len(entidades_detectadas) if entidades_detectadas else (1.0 if not expected else 0.0)
    recall = len(tp) / len(expected) if expected else (1.0 if not entidades_detectadas else 0.0)
    exact_match = entidades_detectadas == expected
    urgencia_match = urgencia_detectada == case["expected_urgencia"]

    escalation_ok = None
    if case["case_type"] == "escalation":
        escalation_ok = bool(entidades_detectadas & EMERGENCY_IDS)

    return {
        "resumen": resumen,
        "case_type": case["case_type"],
        "expected_entidades": sorted(expected),
        "detected_entidades": sorted(entidades_detectadas),
        "expected_urgencia": case["expected_urgencia"],
        "detected_urgencia": urgencia_detectada,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "exact_match": exact_match,
        "urgencia_match": urgencia_match,
        "escalation_ok": escalation_ok,
        "false_positives": sorted(fp),
        "false_negatives": sorted(fn),
    }


def _avg(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def summarize(results: list[dict]) -> dict:
    n = len(results)

    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_type[r["case_type"]].append(r)

    # Micro-averaged precision/recall por entidad (agregando TP/FP/FN de las 10
    # entidades del catálogo, no el promedio de promedios por caso).
    tp_by_entity: dict[str, int] = defaultdict(int)
    fp_by_entity: dict[str, int] = defaultdict(int)
    fn_by_entity: dict[str, int] = defaultdict(int)
    for r in results:
        expected = set(r["expected_entidades"])
        detected = set(r["detected_entidades"])
        for e in detected & expected:
            tp_by_entity[e] += 1
        for e in detected - expected:
            fp_by_entity[e] += 1
        for e in expected - detected:
            fn_by_entity[e] += 1

    per_entity = {}
    for e in sorted(set(tp_by_entity) | set(fp_by_entity) | set(fn_by_entity)):
        tp, fp, fn = tp_by_entity[e], fp_by_entity[e], fn_by_entity[e]
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        per_entity[e] = {"tp": tp, "fp": fp, "fn": fn,
                          "precision": round(prec, 4) if prec is not None else None,
                          "recall": round(rec, 4) if rec is not None else None}

    escalation_cases = [r for r in results if r["case_type"] == "escalation"]

    return {
        "n_cases": n,
        "overall": {
            "mean_precision": _avg([r["precision"] for r in results]),
            "mean_recall": _avg([r["recall"] for r in results]),
            "exact_match_rate": round(sum(r["exact_match"] for r in results) / n, 4),
            "urgencia_accuracy": round(sum(r["urgencia_match"] for r in results) / n, 4),
        },
        "by_case_type": {
            ct: {
                "n": len(rows),
                "exact_match_rate": round(sum(r["exact_match"] for r in rows) / len(rows), 4),
                "urgencia_accuracy": round(sum(r["urgencia_match"] for r in rows) / len(rows), 4),
            }
            for ct, rows in by_type.items()
        },
        "escalation_check": {
            "n": len(escalation_cases),
            "correctly_escalated_rate": (
                round(sum(bool(r["escalation_ok"]) for r in escalation_cases) / len(escalation_cases), 4)
                if escalation_cases else None
            ),
        },
        "per_entity": per_entity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DATASET_PATH))
    parser.add_argument("--out", default=None,
                        help="Ruta LOCAL. Si no se pasa, sube a "
                             "gs://<gcs_corpus_bucket>/eval/derivation_results.json "
                             "(el filesystem del Cloud Run Job es efímero)")
    args = parser.parse_args()

    cases = load_golden(Path(args.dataset))
    print(f"Evaluando {len(cases)} casos contra app.entity_catalog...")

    results = []
    for i, case in enumerate(cases, 1):
        r = run_case(case)
        results.append(r)
        if not r["exact_match"] or not r["urgencia_match"]:
            print(f"  [{i}/{len(cases)}] MISS ({r['case_type']}): "
                  f"esperado={r['expected_entidades']} urg={r['expected_urgencia']} | "
                  f"detectado={r['detected_entidades']} urg={r['detected_urgencia']}")

    summary = summarize(results)
    report = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "dataset": args.dataset,
        "summary": summary,
        "results": results,
    }

    print("\n=== RESUMEN ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(payload, encoding="utf-8")
        print(f"\nEscrito: {out_path}")
    else:
        # El filesystem del Cloud Run Job es efímero: sube a GCS en vez de a un
        # archivo local que desaparece cuando termina el contenedor.
        from app.config import settings
        from google.cloud import storage

        blob_name = "eval/derivation_results.json"
        client = storage.Client()
        client.bucket(settings.gcs_corpus_bucket).blob(blob_name).upload_from_string(
            payload, content_type="application/json")
        uri = f"gs://{settings.gcs_corpus_bucket}/{blob_name}"
        print(f"\nEscrito: {uri}")
        print(f"Para usarlo localmente: gsutil cp {uri} evaluation/derivation_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
