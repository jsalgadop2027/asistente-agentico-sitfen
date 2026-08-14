# -*- coding: utf-8 -*-
"""Genera el golden dataset de evaluación RAG desde el corpus actual (200 PDFs).

Reemplaza a golden_dataset_1000.jsonl / eval_sample_150.jsonl / golden_dataset.jsonl
(archivados en evaluation/archive/, construidos sobre el corpus viejo de ~148 PDFs
en 5 categorías — ninguna de sus preguntas cubre los 83 PDFs nuevos: economía_fen,
agroexportacion_norte, agronomia_hidrica_norte, estudios_complementarios).

Estratifica por las 6 categorías FÍSICAS del corpus (carpetas reales bajo
corpus_documental/, listadas en evaluation/corpus_categories.json — un mapeo
{nombre_de_archivo: categoría} generado una vez desde el disco local y comiteado
al repo, NO recalculado en el Cloud Run Job): piso mínimo de preguntas por
categoría + resto proporcional al Nº de documentos (mismo método que
evaluation/build_eval_sample.py::stratified_sample, aplicado aquí sobre documentos
a generar en vez de preguntas ya existentes a muestrear).

El TEXTO de cada documento se reconstruye desde los chunks YA ingestados en
Firestore (`corpus_chunks`, reensamblados por `source` y ordenados por
`chunk_index`) — no se re-parsean los PDFs. Dos razones: (1) los PDFs (1.4 GB)
nunca se subieron a GCS con la estructura de subcarpetas por categoría que este
script necesita (el bucket de ingesta es plano y solo tiene los 19 PDFs de la
"raíz" original — la reingesta real corrió `--source local` desde un disco con
el árbol completo, que el Cloud Run Job no tiene disponible), y (2) hornear 1.4 GB
de PDFs en la imagen del job infla el build/push sin necesidad. Firestore ya tiene
las 200 fuentes completas (confirmado: 200 `source` distintos, 20559 chunks) — es
la fuente de verdad más barata y de solo lectura disponible desde el job.

Requiere Vertex AI (credenciales con aiplatform.endpoints.predict) para el modo
real, y Firestore de lectura — pensado para correr vía el Cloud Run Job
arandano-eval (infra/08_deploy_eval_job.ps1), no con una cuenta personal sin ese
permiso de Vertex AI (Firestore sí es accesible con la cuenta personal).
`--dry-run` valida el mapeo de categorías y el plan de cuotas sin llamar al LLM
ni a Firestore (gratis, corre en cualquier entorno).

Uso:
    python -m evaluation.build_golden_dataset --dry-run
    python -m evaluation.build_golden_dataset --n 180 --floor 15 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from ingestion.loaders import LoadedDocument

HERE = Path(__file__).parent
CATEGORIES_FILE = HERE / "corpus_categories.json"
OUT_PATH = HERE / "golden_dataset_v2.jsonl"

CATEGORIES: list[tuple[str, str]] = [
    ("raiz", "Comercio, agronomía y mercado (raíz)"),
    ("enfen", "Clima / ENFEN"),
    ("economia_fen", "Economía y política del FEN"),
    ("agroexportacion_norte", "Agroexportación multi-cultivo"),
    ("agronomia_hidrica_norte", "Agronomía/hídrica complementaria"),
    ("estudios_complementarios", "Estudios complementarios"),
]

_GEN_PROMPT = (
    "Eres un experto en agroindustria peruana preparando un examen de evaluación "
    "para un asistente de IA. Lee el siguiente documento y genera {k} preguntas "
    "DISTINTAS que un productor agrícola o exportador peruano podría hacerle al "
    "asistente, cada una respondible ÚNICAMENTE con información de este texto "
    "(nada de conocimiento externo). Evita preguntas triviales de una palabra; "
    "prioriza preguntas concretas y factuales (requisitos, cifras, plazos, "
    "procedimientos, definiciones).\n\n"
    "Devuelve EXCLUSIVAMENTE un JSON: una lista de {k} objetos con las claves "
    '"question" y "ground_truth" (la respuesta de referencia, 1-3 oraciones, '
    "basada solo en el texto). Sin texto adicional ni ```.\n\n"
    "DOCUMENTO ({source}):\n{text}"
)

_HEADER_RE = re.compile(r"^\[Documento:[^\]]*\]\n?")


def _load_source_map() -> dict[str, str]:
    with CATEGORIES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _group_by_category(source_map: dict[str, str]) -> dict[str, list[str]]:
    by_cat: dict[str, list[str]] = {}
    for source, cat in source_map.items():
        by_cat.setdefault(cat, []).append(source)
    for sources in by_cat.values():
        sources.sort()
    return by_cat


def _load_document(store, source: str) -> LoadedDocument | None:
    """Reensambla el texto completo de `source` desde sus chunks en Firestore,
    ordenados por chunk_index (orden client-side: evita depender de un índice
    compuesto de Firestore para una query igualdad+orden)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    query = store.collection.where(filter=FieldFilter("source", "==", source)).select(
        ["text", "chunk_index", "title"]
    )
    chunks = [(d.to_dict() or {}) for d in query.stream()]
    if not chunks:
        return None
    chunks.sort(key=lambda c: c.get("chunk_index", 0))
    title = chunks[0].get("title") or Path(source).stem
    parts = []
    for i, c in enumerate(chunks):
        text = c.get("text", "")
        if i > 0:
            text = _HEADER_RE.sub("", text, count=1)
        parts.append(text)
    return LoadedDocument(source=source, title=title, pages=["\n\n".join(parts)])


def _quota_per_category(counts: dict[str, int], *, n: int, floor: int) -> dict[str, int]:
    """Piso mínimo de PREGUNTAS por categoría + resto proporcional al Nº de
    documentos (mismo método que build_eval_sample.py::stratified_sample, pero
    sin capar el piso por Nº de documentos: a diferencia de esa función -que
    muestrea filas ya existentes-, acá una categoría con pocos documentos puede
    igual alcanzar el piso pidiendo varias preguntas por documento
    (`_questions_per_doc` permite hasta 3 por documento)."""
    quotas = {k: floor for k, v in counts.items() if v > 0}
    budget = n - sum(quotas.values())
    if budget <= 0:
        return quotas
    total_docs = sum(counts.values())
    raw = {k: budget * counts[k] / total_docs for k in quotas}
    for k in quotas:
        quotas[k] += round(raw[k])
    diff = n - sum(quotas.values())
    cats_by_size = sorted(quotas, key=lambda c: counts[c], reverse=True)
    i = 0
    while diff != 0 and cats_by_size:
        cat = cats_by_size[i % len(cats_by_size)]
        if diff > 0:
            quotas[cat] += 1
            diff -= 1
        elif quotas[cat] > 1:
            quotas[cat] -= 1
            diff += 1
        i += 1
        if i > 10000:
            break
    return quotas


def _questions_per_doc(n_docs: int, quota: int) -> list[int]:
    """Reparte `quota` preguntas entre `n_docs` documentos, 1-3 por documento
    (nunca 0, para no desperdiciar una llamada al LLM sin generar nada)."""
    if n_docs == 0:
        return []
    base = max(1, quota // n_docs)
    base = min(base, 3)
    alloc = [base] * n_docs
    remaining = quota - sum(alloc)
    i = 0
    while remaining > 0 and i < n_docs * 10:
        idx = i % n_docs
        if alloc[idx] < 3:
            alloc[idx] += 1
            remaining -= 1
        i += 1
    return alloc


def _extract_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    start = t.find("[")
    end = t.rfind("]")
    return t[start:end + 1] if start != -1 and end > start else t


def generate_for_doc(llm, doc: LoadedDocument, k: int) -> list[dict]:
    text = doc.full_text[:9000]
    prompt = _GEN_PROMPT.format(k=k, source=doc.source, text=text)
    raw = llm.invoke(prompt).content
    raw = raw if isinstance(raw, str) else str(raw)
    try:
        data = json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q, gt = item.get("question"), item.get("ground_truth")
        if q and gt:
            out.append({"question": str(q).strip(), "ground_truth": str(gt).strip()})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=180)
    parser.add_argument("--floor", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo valida el mapeo de categorías y las cuotas, "
                             "sin llamar al LLM ni a Firestore")
    parser.add_argument("--out", default=None,
                        help="Ruta LOCAL. Si no se pasa, sube a "
                             "gs://<gcs_corpus_bucket>/eval/golden_dataset_v2.jsonl "
                             "(el filesystem del Cloud Run Job es efímero)")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    source_map = _load_source_map()
    by_cat = _group_by_category(source_map)
    counts = {k: len(by_cat.get(k, [])) for k, _label in CATEGORIES}

    print(f"Mapeo de categorías: {CATEGORIES_FILE.name} ({len(source_map)} fuentes)")
    for key, label in CATEGORIES:
        print(f"  {counts[key]:4d}  {label}")

    quotas = _quota_per_category(counts, n=args.n, floor=args.floor)
    print(f"\nCuota de preguntas por categoría (objetivo {args.n}, piso {args.floor}):")
    for key, label in CATEGORIES:
        if key in quotas:
            print(f"  {quotas[key]:4d}  {label}")
    print(f"  Total: {sum(quotas.values())}")

    if args.dry_run:
        print("\n--dry-run: no se llamó al LLM ni a Firestore, no se escribió ningún archivo.")
        return 0

    from app.agent.models import get_llm
    from app.firestore_store import FirestoreVectorStore

    llm = get_llm(temperature=0.4)  # algo de variedad en el fraseo de preguntas
    store = FirestoreVectorStore()

    rows: list[dict] = []
    for key, label in CATEGORIES:
        sources = list(by_cat.get(key, []))
        quota = quotas.get(key, 0)
        if not sources or quota == 0:
            continue
        rng.shuffle(sources)
        selected = sources[: max(quota, min(len(sources), quota))]
        per_doc = _questions_per_doc(len(selected), quota)
        for source, k in zip(selected, per_doc):
            doc = _load_document(store, source)
            if doc is None or not doc.full_text.strip():
                print(f"  [{label}] {source}: sin chunks en Firestore, omitido")
                continue
            items = generate_for_doc(llm, doc, k)
            for item in items:
                rows.append({**item, "category": label, "source_document": doc.source})
            print(f"  [{label}] {source}: +{len(items)} preguntas")

    rng.shuffle(rows)
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(payload, encoding="utf-8")
        print(f"\nEscrito: {out_path} ({len(rows)} preguntas)")
    else:
        # El filesystem del Cloud Run Job es efímero: sube a GCS en vez de a un
        # archivo local que desaparece cuando termina el contenedor.
        from app.config import settings
        from google.cloud import storage

        blob_name = "eval/golden_dataset_v2.jsonl"
        client = storage.Client()
        client.bucket(settings.gcs_corpus_bucket).blob(blob_name).upload_from_string(
            payload, content_type="application/jsonl")
        uri = f"gs://{settings.gcs_corpus_bucket}/{blob_name}"
        print(f"\nEscrito: {uri} ({len(rows)} preguntas)")
        print(f"Para usarlo localmente: gsutil cp {uri} evaluation/golden_dataset_v2.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
