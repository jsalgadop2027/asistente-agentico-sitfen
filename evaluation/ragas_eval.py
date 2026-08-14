"""Evaluación con RAGAS usando Gemini (Vertex) como juez y embeddings de Vertex.

Métricas: faithfulness, answer_relevancy, context_precision, context_recall.

Uso:
    python -m evaluation.ragas_eval
"""
from __future__ import annotations

import sys


def main() -> int:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    from app.agent.models import get_embeddings, get_llm
    from app.observability import configure_observability
    from evaluation.harness import generate_samples

    configure_observability()
    print("Generando respuestas RAG sobre el dataset dorado...")
    samples = generate_samples()

    data = {
        "question": [s.question for s in samples],
        "answer": [s.answer for s in samples],
        "contexts": [s.contexts for s in samples],
        "ground_truth": [s.ground_truth for s in samples],
    }
    dataset = Dataset.from_dict(data)

    judge = LangchainLLMWrapper(get_llm(pro=True, temperature=0.0))
    emb = LangchainEmbeddingsWrapper(get_embeddings())

    print("Evaluando con RAGAS (juez: Gemini)...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge,
        embeddings=emb,
    )
    print("\n=== Resultados RAGAS ===")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
