"""Utilidades compartidas para la evaluación (carga de dataset + generación RAG).

Genera (pregunta, respuesta, contextos, ground_truth) para alimentar RAGAS y
DeepEval. La respuesta se produce con una cadena RAG directa (retriever + LLM)
para capturar explícitamente los contextos usados, requisito de las métricas.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_RAG_PROMPT = (
    "Responde la pregunta del usuario usando EXCLUSIVAMENTE el siguiente contexto. "
    "Si el contexto no contiene la respuesta, dilo. Cita las fuentes.\n\n"
    "Contexto:\n{context}\n\nPregunta: {question}\n\nRespuesta:"
)

# Dataset dorado por defecto: ~180 preguntas (evaluation/golden_dataset_v2.jsonl),
# generado desde el corpus ACTUAL de 200 PDFs / 6 categorías físicas (ver
# evaluation/build_golden_dataset.py) — reemplaza a golden_dataset_1000.jsonl y
# eval_sample_150.jsonl (archivados en evaluation/archive/*_pre200corpus.*),
# construidos sobre el corpus viejo de ~148 PDFs y sin cobertura de las 4
# categorías agregadas después (economía_fen, agroexportacion_norte,
# agronomia_hidrica_norte, estudios_complementarios — 83 PDFs, 41% del corpus).
# Override con la env var EVAL_DATASET (ruta absoluta, o nombre/relativa resuelta
# contra este directorio) — p. ej.:
#   EVAL_DATASET=golden_dataset.jsonl        # smoke test rápido de 8 preguntas
#                                             # (ver evaluation/build_golden_dataset.py
#                                             # para regenerar golden_dataset_v2.jsonl)
_DEFAULT_DATASET = "golden_dataset_v2.jsonl"


def _resolve_dataset() -> Path:
    override = os.environ.get("EVAL_DATASET")
    if override:
        p = Path(override)
        return p if p.is_absolute() else Path(__file__).parent / p
    return Path(__file__).parent / _DEFAULT_DATASET


DATASET_PATH = _resolve_dataset()


@dataclass
class EvalSample:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str = ""
    extra: dict = field(default_factory=dict)


def load_golden(path: Path = DATASET_PATH) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def generate_samples() -> list[EvalSample]:
    """Ejecuta la cadena RAG sobre el dataset dorado. Requiere GCP/Firestore."""
    from app.agent.models import get_llm
    from app.agent.retriever import AdvancedRetriever

    retriever = AdvancedRetriever()
    llm = get_llm(temperature=0.0)
    samples: list[EvalSample] = []

    for row in load_golden():
        question = row["question"]
        result = retriever.retrieve(question)
        contexts = [c.text for c in result.chunks]
        context_block = "\n\n".join(contexts) or "(sin contexto)"
        answer = llm.invoke(
            _RAG_PROMPT.format(context=context_block, question=question)
        ).content
        samples.append(
            EvalSample(
                question=question,
                answer=answer if isinstance(answer, str) else str(answer),
                contexts=contexts,
                ground_truth=row.get("ground_truth", ""),
            )
        )
    return samples
