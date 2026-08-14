"""Runner unificado de evaluación de calidad: RAGAS + DeepEval (juez Gemini).

Ejecuta la cadena RAG sobre el dataset dorado, calcula métricas con ambas
librerías y escribe un JSON estructurado a GCS (y a stdout) para reportería.

Diseñado para correr como Cloud Run Job (usa la service account del proyecto).
Compatible con RAGAS 0.4.x y DeepEval 4.x.

Uso:
    python -m evaluation.run_all                 # escribe a gs://<corpus>/eval/results.json
    python -m evaluation.run_all --out local.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

from app.config import settings
from app.observability import configure_observability, get_logger

logger = get_logger("eval")


# --------------------------------------------------------------------------
# Generación de muestras (pregunta, respuesta RAG, contextos, ground_truth)
# --------------------------------------------------------------------------
def _retry_on_quota(fn, *, attempts: int = 6, base_delay: float = 20.0):
    """Reintenta `fn()` con backoff exponencial ante 429 RESOURCE_EXHAUSTED de
    Vertex AI. La evaluación dispara muchas más llamadas por minuto que un
    usuario real, así que puede chocar con cuotas que en producción nunca se
    alcanzan; esto es solo para el harness de evaluación, no para el agente."""
    import time

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            is_quota = "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc)
            if not is_quota or attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("quota_retry", attempt=attempt, delay=delay, error=str(exc)[:200])
            time.sleep(delay)


def build_samples(checkpoint=None) -> list[dict]:
    from app.agent.models import get_llm
    from app.agent.retriever import AdvancedRetriever
    from evaluation.harness import load_golden

    retriever = AdvancedRetriever()
    llm = get_llm(temperature=0.0)
    prompt = (
        "Responde la pregunta usando EXCLUSIVAMENTE el contexto. Si el contexto "
        "no contiene la respuesta, indícalo. Cita las fuentes.\n\n"
        "Contexto:\n{context}\n\nPregunta: {question}\n\nRespuesta:"
    )
    samples = []
    for row in load_golden():
        q = row["question"]
        result = _retry_on_quota(lambda: retriever.retrieve(q))
        contexts = [c.text for c in result.chunks]
        sources = result.sources
        ctx = "\n\n".join(contexts) or "(sin contexto)"
        answer = _retry_on_quota(
            lambda: llm.invoke(prompt.format(context=ctx, question=q)).content
        )
        samples.append({
            "question": q,
            "answer": answer if isinstance(answer, str) else str(answer),
            "contexts": contexts,
            "sources": sources,
            "ground_truth": row.get("ground_truth", ""),
        })
        logger.info("sample_built", question=q[:50], n_ctx=len(contexts))
        if checkpoint:
            checkpoint(len(samples))
    return samples


# --------------------------------------------------------------------------
# RAGAS
# --------------------------------------------------------------------------
def _install_community_vertexai_shim() -> None:
    """RAGAS 0.4.x referencia `langchain_community.chat_models.vertexai`, ruta
    eliminada en langchain nuevo (movida a langchain_google_vertexai). Se inyecta
    un módulo alias para satisfacer ese import sin degradar funcionalidad."""
    import sys
    import types

    name = "langchain_community.chat_models.vertexai"
    if name in sys.modules:
        return
    try:
        __import__(name)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        import langchain_google_vertexai as lgv

        shim = types.ModuleType(name)
        shim.ChatVertexAI = lgv.ChatVertexAI
        sys.modules[name] = shim
    except Exception as exc:  # noqa: BLE001
        logger.warning("vertexai_shim_failed", error=str(exc))


def run_ragas(samples: list[dict]) -> dict:
    try:
        _install_community_vertexai_shim()
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
            ResponseRelevancy,
        )
        from ragas.run_config import RunConfig

        from app.agent.models import get_embeddings, get_llm

        data = [{
            "user_input": s["question"],
            "response": s["answer"],
            "retrieved_contexts": s["contexts"],
            "reference": s["ground_truth"],
        } for s in samples]
        ds = EvaluationDataset.from_list(data)

        judge = LangchainLLMWrapper(get_llm(pro=True, temperature=0.0))
        emb = LangchainEmbeddingsWrapper(get_embeddings())
        metrics = [
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ]
        # max_workers bajo + retries/backoff generosos: la cuota de Vertex AI
        # para el modelo de embeddings es baja y el default (16 workers en
        # paralelo) la agota casi de inmediato pese a los reintentos de ragas.
        run_config = RunConfig(max_workers=2, max_retries=8, max_wait=90, timeout=300)
        result = evaluate(dataset=ds, metrics=metrics, llm=judge, embeddings=emb,
                          run_config=run_config)
        df = result.to_pandas()

        metric_cols = [c for c in df.columns
                       if c not in ("user_input", "response", "retrieved_contexts",
                                    "reference")]
        per_question = []
        for _, rrow in df.iterrows():
            per_question.append({c: _num(rrow[c]) for c in metric_cols})
        aggregate = {}
        for c in metric_cols:
            vals = [v for v in (_num(x) for x in df[c]) if v is not None]
            aggregate[c] = round(sum(vals) / len(vals), 4) if vals else None
        return {"ok": True, "aggregate": aggregate, "per_question": per_question,
                "metrics": metric_cols}
    except Exception as exc:  # noqa: BLE001
        logger.error("ragas_failed", error=str(exc))
        return {"ok": False, "error": str(exc), "trace": traceback.format_exc()}


# --------------------------------------------------------------------------
# DeepEval
# --------------------------------------------------------------------------
def _extract_json(text: str) -> str:
    """Normaliza la salida del LLM a JSON parseable: quita fences ```json y
    recorta a la primera estructura {..} o [..]. DeepEval falla si el modelo
    envuelve el JSON en markdown o añade prosa; esto lo corrige."""
    if not isinstance(text, str):
        return text
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    # recortar a la estructura JSON externa
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if starts:
        start = min(starts)
        end = max(t.rfind("}"), t.rfind("]"))
        if end > start:
            t = t[start:end + 1]
    return t.strip()


def _vertex_judge():
    from deepeval.models.base_model import DeepEvalBaseLLM

    from app.agent.models import get_llm

    class VertexJudge(DeepEvalBaseLLM):
        def __init__(self):
            self.model = get_llm(pro=True, temperature=0.0)

        def load_model(self):
            return self.model

        def generate(self, prompt: str, schema=None):
            if schema is not None:
                return self.model.with_structured_output(schema).invoke(prompt)
            return _extract_json(self.model.invoke(prompt).content)

        async def a_generate(self, prompt: str, schema=None):
            if schema is not None:
                return await self.model.with_structured_output(schema).ainvoke(prompt)
            res = await self.model.ainvoke(prompt)
            return _extract_json(res.content)

        def get_model_name(self):
            return "gemini-2.5-pro"

    return VertexJudge()


def run_deepeval(samples: list[dict], checkpoint=None) -> dict:
    try:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualRelevancyMetric,
            FaithfulnessMetric,
        )
        from deepeval.test_case import LLMTestCase

        judge = _vertex_judge()
        metric_defs = {
            "faithfulness": lambda: FaithfulnessMetric(threshold=0.7, model=judge,
                                                       async_mode=False),
            "answer_relevancy": lambda: AnswerRelevancyMetric(threshold=0.7, model=judge,
                                                              async_mode=False),
            "contextual_relevancy": lambda: ContextualRelevancyMetric(
                threshold=0.6, model=judge, async_mode=False),
        }

        per_question = []
        sums = {k: [] for k in metric_defs}
        for s in samples:
            case = LLMTestCase(
                input=s["question"],
                actual_output=s["answer"],
                expected_output=s["ground_truth"],
                retrieval_context=s["contexts"],
            )
            row = {}
            for name, factory in metric_defs.items():
                try:
                    m = factory()
                    m.measure(case)
                    row[name] = _num(m.score)
                    if row[name] is not None:
                        sums[name].append(row[name])
                except Exception as exc:  # noqa: BLE001
                    logger.error("deepeval_metric_failed", metric=name, error=str(exc))
                    row[name] = None
            per_question.append(row)
            if checkpoint:
                checkpoint(per_question, sums, metric_defs)

        aggregate = {k: (round(sum(v) / len(v), 4) if v else None)
                     for k, v in sums.items()}
        return {"ok": True, "aggregate": aggregate, "per_question": per_question,
                "metrics": list(metric_defs)}
    except Exception as exc:  # noqa: BLE001
        logger.error("deepeval_failed", error=str(exc))
        return {"ok": False, "error": str(exc), "trace": traceback.format_exc()}


_TRIAD_PROMPT = """Eres un evaluador experto de sistemas RAG. Evalúa la RESPUESTA dada
a la PREGUNTA, usando el CONTEXTO recuperado y la RESPUESTA DE REFERENCIA.

Devuelve SOLO un objeto JSON con estas claves (valores entre 0.0 y 1.0):
- "faithfulness": qué tan respaldada está la respuesta por el contexto (sin alucinar).
- "answer_relevancy": qué tan pertinente y completa es la respuesta a la pregunta.
- "context_relevancy": qué proporción del contexto es relevante para la pregunta.
- "correctness": qué tan correcta es respecto a la respuesta de referencia.

PREGUNTA: {q}
CONTEXTO: {ctx}
RESPUESTA: {ans}
RESPUESTA DE REFERENCIA: {ref}
"""


def run_custom_triad(samples: list[dict], checkpoint=None) -> dict:
    """Validación cruzada con juez Gemini propio (JSON estricto). Red de seguridad
    independiente de RAGAS/DeepEval que garantiza métricas del triángulo RAG."""
    try:
        import json as _json

        from app.agent.models import get_llm

        llm = get_llm(pro=True, temperature=0.0)
        keys = ["faithfulness", "answer_relevancy", "context_relevancy", "correctness"]
        per_question = []
        sums = {k: [] for k in keys}
        for s in samples:
            ctx = "\n\n".join(s["contexts"])[:8000] or "(sin contexto)"
            prompt = _TRIAD_PROMPT.format(q=s["question"], ctx=ctx,
                                          ans=s["answer"], ref=s["ground_truth"])
            try:
                raw = llm.invoke(prompt).content
                data = _json.loads(_extract_json(raw if isinstance(raw, str) else str(raw)))
                row = {k: _num(data.get(k)) for k in keys}
            except Exception as exc:  # noqa: BLE001
                logger.error("triad_item_failed", error=str(exc))
                row = {k: None for k in keys}
            per_question.append(row)
            for k in keys:
                if row[k] is not None:
                    sums[k].append(row[k])
            if checkpoint:
                checkpoint(per_question, sums)
        aggregate = {k: (round(sum(v) / len(v), 4) if v else None)
                     for k, v in sums.items()}
        return {"ok": True, "aggregate": aggregate, "per_question": per_question,
                "metrics": keys}
    except Exception as exc:  # noqa: BLE001
        logger.error("triad_failed", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _num(x):
    try:
        if x is None:
            return None
        f = float(x)
        if f != f:  # NaN
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
def _make_writer(out_arg: str | None):
    """Devuelve una función `write(report)` que persiste el estado actual (parcial
    o final) siempre en el MISMO destino (sobrescribe) — así, si el job se corta
    a mitad de camino (timeout, cuota, crash), lo último escrito es lo más
    avanzado que se alcanzó a calcular, no se pierde todo el cómputo previo."""
    if out_arg:
        out_path = Path(out_arg)

        def write_local(report: dict) -> None:
            payload = json.dumps(report, ensure_ascii=False, indent=2)
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(payload)
            logger.info("eval_checkpoint_local", path=str(out_path),
                        status=report.get("status"))

        return write_local

    from google.cloud import storage

    client = storage.Client()
    blob = client.bucket(settings.gcs_corpus_bucket).blob("eval/results.json")

    def write_gcs(report: dict) -> None:
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        blob.upload_from_string(payload, content_type="application/json")
        logger.info("eval_checkpoint_gcs",
                    uri=f"gs://{settings.gcs_corpus_bucket}/eval/results.json",
                    status=report.get("status"))

    return write_gcs


def main() -> int:
    configure_observability()
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None, help="Ruta local (si no, sube a GCS)")
    args = p.parse_args()

    write = _make_writer(args.out)
    report: dict = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "project": settings.gcp_project_id,
        "models": {
            "inference": settings.gemini_model_fast,
            "judge": settings.gemini_model_pro,
            "embeddings": settings.embedding_model,
        },
        "status": "running_build_samples",
        "n_questions": None,
        "samples": [],
        "ragas": None,
        "deepeval": None,
        "custom_triad": None,
    }
    write(report)

    logger.info("eval_start")
    samples: list[dict] = []

    def on_sample(_n_done: int) -> None:
        report["samples"] = samples
        report["n_questions"] = len(samples)
        write(report)

    samples[:] = build_samples(checkpoint=on_sample)
    report["samples"] = samples
    report["n_questions"] = len(samples)

    logger.info("ragas_running")
    report["status"] = "running_ragas"
    write(report)
    report["ragas"] = run_ragas(samples)
    write(report)

    logger.info("deepeval_running")
    report["status"] = "running_deepeval"
    write(report)

    def on_deepeval(per_question, sums, metric_defs) -> None:
        aggregate = {k: (round(sum(v) / len(v), 4) if v else None) for k, v in sums.items()}
        report["deepeval"] = {"ok": True, "aggregate": aggregate,
                              "per_question": per_question, "metrics": list(metric_defs)}
        write(report)

    report["deepeval"] = run_deepeval(samples, checkpoint=on_deepeval)
    write(report)

    logger.info("triad_running")
    report["status"] = "running_triad"
    write(report)

    def on_triad(per_question, sums) -> None:
        aggregate = {k: (round(sum(v) / len(v), 4) if v else None) for k, v in sums.items()}
        report["custom_triad"] = {"ok": True, "aggregate": aggregate,
                                  "per_question": per_question,
                                  "metrics": list(sums.keys())}
        write(report)

    report["custom_triad"] = run_custom_triad(samples, checkpoint=on_triad)
    report["status"] = "completed"
    write(report)

    print("=== RESULTADOS (resumen) ===")
    print(json.dumps({"ragas": report["ragas"].get("aggregate"),
                      "deepeval": report["deepeval"].get("aggregate"),
                      "custom_triad": report["custom_triad"].get("aggregate")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
