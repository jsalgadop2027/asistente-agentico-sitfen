"""Evaluación con DeepEval usando Gemini (Vertex) como modelo juez.

Métricas: Faithfulness, Answer Relevancy y Contextual Relevancy (RAG triad).

Uso:
    python -m evaluation.deepeval_eval
"""
from __future__ import annotations

import sys


class _VertexJudge:
    """Adaptador mínimo de Gemini (Vertex) al interfaz DeepEvalBaseLLM."""

    def __init__(self):
        from app.agent.models import get_llm

        self._llm = get_llm(pro=True, temperature=0.0)

    def load_model(self):
        return self._llm

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        res = await self._llm.ainvoke(prompt)
        return res.content

    def get_model_name(self) -> str:
        return "gemini-vertex-judge"


def main() -> int:
    from deepeval import evaluate
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
    )
    from deepeval.models.base_model import DeepEvalBaseLLM
    from deepeval.test_case import LLMTestCase

    from app.observability import configure_observability
    from evaluation.harness import generate_samples

    configure_observability()

    # Envolver el adaptador en la clase base de DeepEval.
    class VertexJudge(DeepEvalBaseLLM, _VertexJudge):
        pass

    judge = VertexJudge()

    print("Generando respuestas RAG sobre el dataset dorado...")
    samples = generate_samples()

    test_cases = [
        LLMTestCase(
            input=s.question,
            actual_output=s.answer,
            expected_output=s.ground_truth,
            retrieval_context=s.contexts,
        )
        for s in samples
    ]

    metrics = [
        FaithfulnessMetric(threshold=0.7, model=judge),
        AnswerRelevancyMetric(threshold=0.7, model=judge),
        ContextualRelevancyMetric(threshold=0.6, model=judge),
    ]

    print("Evaluando con DeepEval (juez: Gemini)...")
    evaluate(test_cases=test_cases, metrics=metrics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
