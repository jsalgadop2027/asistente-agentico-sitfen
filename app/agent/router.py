"""Router multimodelo Flash <-> Pro para el orquestador.

Selecciona, por consulta, qué modelo Gemini usa el agente ReAct:
  - FAST (gemini-2.5-flash): consultas simples/factuales, saludos, búsquedas
    directas en el corpus. Es el modelo por defecto (rápido y de menor costo).
  - PRO (gemini-2.5-pro): consultas que requieren razonamiento complejo —
    análisis, comparación, síntesis, estrategia, causalidad o multi-paso.

El enrutamiento es una heurística determinista (sin llamadas de red): trazable,
gratuita y fácil de testear. Cumple el requisito de "router multimodelo con
selección automática" manteniendo el costo cercano a cero (no añade una llamada
extra al LLM sólo para clasificar).

Las señales están en ES/EN porque el chatbot atiende consultas en varios idiomas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


class ModelTier(str, Enum):
    FAST = "fast"
    PRO = "pro"


# Verbos/expresiones que denotan razonamiento complejo (ES/EN). Si aparece
# alguno, la consulta se enruta a Pro.
_PRO_PATTERNS = [
    r"analiza|análisis|analy(ze|sis)",
    r"compara|comparaci[óo]n|compare|comparison|\bversus\b|\bvs\.?\b",
    r"estrateg|strateg",
    r"por\s+qu[ée]|porqu[ée]|\bwhy\b",
    r"recomien|recommend",
    r"eval[úu]a|evaluaci[óo]n|evaluate",
    r"ventajas?\s+y\s+desventajas?|pros\s+y\s+contras|pros\s+and\s+cons",
    r"proyecci[óo]n|tendencia|forecast|\btrend",
    r"resume|res[úu]men|sintetiza|s[íi]ntesis|summari[sz]e",
    r"diferencias?\s+entre|difference\s+between",
    r"impacto|impact",
    r"riesgos?|\brisks?\b",
    r"plan\s+de|planea|elabora\s+un|dise[ñn]a\s+un",
    r"paso\s+a\s+paso|step[-\s]?by[-\s]?step",
    r"optimiza|optimize",
]
_PRO_RE = re.compile("|".join(_PRO_PATTERNS), re.IGNORECASE)


@dataclass
class RouteDecision:
    tier: ModelTier
    reason: str

    @property
    def pro(self) -> bool:
        return self.tier is ModelTier.PRO


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


def route_model(text: str) -> RouteDecision:
    """Decide Flash vs Pro para `text` (heurística determinista, sin red).

    Orden de señales (la primera que coincide gana):
      1. Verbo/expresión de razonamiento complejo -> Pro.
      2. Varias preguntas en el mismo turno -> Pro.
      3. Consulta larga (>= router_pro_min_words) -> Pro.
      4. Por defecto -> Flash.
    """
    if not settings.router_enabled:
        return RouteDecision(ModelTier.FAST, "router_disabled")

    t = (text or "").strip()

    m = _PRO_RE.search(t)
    if m:
        return RouteDecision(ModelTier.PRO, f"keyword:{m.group(0).lower()}")

    if t.count("?") >= 2:
        return RouteDecision(ModelTier.PRO, "multi_question")

    wc = _word_count(t)
    if wc >= settings.router_pro_min_words:
        return RouteDecision(ModelTier.PRO, f"long_query:{wc}w")

    return RouteDecision(ModelTier.FAST, "default")
