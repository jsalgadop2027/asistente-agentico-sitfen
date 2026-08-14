"""Guardrails de seguridad (DevSecOps / Ciberseguridad / Ley 29733 / GDPR).

Mapeado a OWASP Top 10 for LLM Applications (2025):
  - LLM01 Prompt Injection: normalización Unicode anti-evasión + detección por
    regex de patrones de inyección/jailbreak (ES/EN).
  - LLM02 Sensitive Information Disclosure: redacción de PII en logs/memoria,
    pseudonimización HMAC (minimización de datos).
  - LLM06 Excessive Agency: confirmación afirmativa determinística (en código, NO
    delegada al LLM) para tools que disparan acciones consecuentes/irreversibles.
  - LLM07 System Prompt Leakage: detección estructural (no solo por frases-gatillo)
    de fuga verbatim del system prompt real, con redacción efectiva de la salida.
  - LLM10 Unbounded Consumption: rate limiting por usuario (anti-abuso/anti-DoS).

La capa de toxicidad/contenido peligroso la cubre Vertex Safety Settings
(ver app/agent/models.py). Aquí se añaden controles específicos del dominio.
"""
from __future__ import annotations

import functools
import re
import time
import unicodedata
from dataclasses import dataclass

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Patrones de inyección de prompt / jailbreak frecuentes (ES/EN).
_INJECTION_PATTERNS = [
    r"ignora(r)?\s+(todas\s+)?las\s+instrucciones",
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"olvida\s+(todo|las\s+reglas|tus\s+instrucciones)",
    r"system\s*prompt",
    r"prompt\s+del?\s+sistema",
    r"act(úa|ua)\s+como\s+(dan|un\s+modelo\s+sin\s+restricciones)",
    r"developer\s+mode|modo\s+desarrollador",
    r"reveal|revela(r)?\s+(tu|el)\s+(prompt|configuraci)",
    r"jailbreak",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Normaliza Unicode para cerrar evasiones clásicas de LLM01 (Prompt Injection).

    Aplica NFKC (colapsa variantes de compatibilidad: full-width, ligaduras, etc.
    a su forma canónica) y elimina caracteres de la categoría Unicode 'Cf'
    (Format — invisibles: zero-width space/joiner U+200B-200D, word joiner
    U+2060, marcas de dirección RTL/LTR, BOM U+FEFF...). Estos caracteres se usan
    para partir palabras gatillo ("i​g​n​o​r​a") y evadir la detección por regex sin
    cambiar cómo se ve el texto para un humano. Se aplica ANTES de cualquier
    detección/heurística y el resultado es lo que ve el LLM y queda en logs.
    """
    if not text:
        return text
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")


# PII: emails, teléfonos, DNI peruano (8 dígitos), RUC (11 dígitos).
# Las tarjetas se tratan aparte con validación Luhn (menos falsos positivos).
_PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\+?\d[\d\s\-]{7,14}\d"),
    "dni": re.compile(r"\b\d{8}\b"),
    "ruc": re.compile(r"\b(10|20)\d{9}\b"),
}
# Candidato a número de tarjeta (13-19 dígitos con separadores); se confirma con Luhn.
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(seq: str) -> bool:
    """Valida un candidato a número de tarjeta con el algoritmo de Luhn."""
    ds = [int(c) for c in seq if c.isdigit()]
    if not 13 <= len(ds) <= 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _has_valid_card(text: str) -> bool:
    return any(_luhn_ok(m.group()) for m in _CARD_CANDIDATE.finditer(text))


def _redact_cards(text: str) -> str:
    return _CARD_CANDIDATE.sub(
        lambda m: "[CARD_REDACTED]" if _luhn_ok(m.group()) else m.group(), text)


def sanitize_injection(text: str) -> str:
    """Neutraliza instrucciones adversarias embebidas (defensa anti data-poisoning)."""
    if not text:
        return text
    return _INJECTION_RE.sub("[contenido-neutralizado]", text)


def pseudonymize(value: str) -> str:
    """Pseudonimiza un identificador personal (p. ej. teléfono) con HMAC-SHA256
    y una sal secreta. Determinista (misma entrada → mismo token) para conservar
    la continuidad de sesión, pero no reversible sin la sal. Minimización de datos.
    """
    import hashlib
    import hmac

    raw = (value or "").strip()
    if not raw:
        return raw
    digest = hmac.new(settings.pii_hash_salt.encode("utf-8"),
                      raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"anon_{digest[:16]}"


@dataclass
class GuardrailResult:
    allowed: bool
    sanitized_text: str
    reason: str | None = None


def detect_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(normalize_text(text or "")))


def sanitize_external_text(text: str, *, fallback: str = "") -> str:
    """Neutraliza texto libre de una API externa (AccuWeather, NOAA) antes de que
    entre al loop ReAct como "observación" de una tool.

    Mitiga ASI01:2026 (Agent Goal Hijack vía contenido que el agente LEE, no solo
    vía lo que el usuario escribe): a diferencia de `check_input` —que bloquea el
    turno completo—, aquí solo se descarta el campo de texto libre sospechoso.
    Los datos numéricos/factuales de la tool (temperatura, mm de lluvia) no
    dependen de este campo y siguen llegando con normalidad.
    """
    text = normalize_text(text or "")
    if not text:
        return fallback
    if detect_injection(text):
        logger.warning("guardrail_external_text_neutralized",
                       sample=redact_pii(text[:120]))
        return fallback
    return text


def redact_pii(text: str) -> str:
    """Reemplaza PII por etiquetas (para logs/memoria). Minimización de datos."""
    if not text:
        return text
    # Tarjetas primero (validadas por Luhn): así el patrón de teléfono no captura
    # antes un número de 16 dígitos y se etiqueta correctamente como tarjeta.
    redacted = _redact_cards(text)
    for label, pattern in _PII_PATTERNS.items():
        redacted = pattern.sub(f"[{label.upper()}_REDACTED]", redacted)
    return redacted


def find_pii(text: str) -> list[str]:
    """Devuelve las categorías de PII detectadas en el texto (vacío si no hay)."""
    if not text:
        return []
    found = [label for label, pattern in _PII_PATTERNS.items() if pattern.search(text)]
    if _has_valid_card(text):
        found.append("card")
    return found


def check_input(text: str) -> GuardrailResult:
    """Valida la entrada del usuario antes de procesarla.

    Normaliza Unicode PRIMERO (ver `normalize_text`): el texto saneado que se
    devuelve —y que ve el LLM, las tools y los logs— ya está libre de caracteres
    invisibles usados para evadir la detección de inyección (LLM01).
    """
    if not text or not text.strip():
        return GuardrailResult(False, "", reason="empty_input")

    text = normalize_text(text)
    if len(text) > settings.max_input_chars:
        text = text[: settings.max_input_chars]

    if detect_injection(text):
        logger.warning("guardrail_injection_blocked", sample=redact_pii(text[:120]))
        return GuardrailResult(
            False,
            text,
            reason=("Tu mensaje parece intentar modificar mi comportamiento. "
                    "Puedo ayudarte con consultas sobre exportación y comercio "
                    "del arándano peruano."),
        )

    return GuardrailResult(True, text)


_LEAK_TRIGGER_RE = re.compile(
    r"(system\s*prompt|prompt\s+del?\s+sistema|eres un asistente experto|"
    r"reglas\s+de\s+operaci[oó]n|=== idioma de respuesta|=== usuario ===)",
    re.IGNORECASE,
)
# Ventanas deslizantes del system prompt REAL para detectar fuga verbatim (LLM07)
# sin depender de frases-gatillo específicas: si el modelo reproduce un tramo
# largo y contiguo del prompt (cualquiera que sea la frase que se lo provocó),
# esto lo detecta igual. Ventanas largas (60 car.) hacen prácticamente imposible
# un falso positivo por vocabulario de dominio compartido (p. ej. "arándano").
_LEAK_WINDOW = 60
_LEAK_STRIDE = 40


def _normalize_for_leak(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text or "")).strip().lower()


@functools.lru_cache(maxsize=1)
def _system_prompt_windows() -> tuple[str, ...]:
    from app.agent.skills import (OBJECTIVE_SECTION, ORCHESTRATOR_SYSTEM_PROMPT,
                                  REASONING_EXAMPLE, TOOLS_SECTION)

    # Misma concatenación estática que orchestrator.py envía como base del
    # system prompt (antes de los augments dinámicos de memoria/usuario/idioma),
    # para que una fuga verbatim de cualquiera de sus bloques se detecte igual.
    norm = _normalize_for_leak(
        f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{OBJECTIVE_SECTION}\n\n"
        f"{TOOLS_SECTION}\n\n{REASONING_EXAMPLE}")
    if len(norm) <= _LEAK_WINDOW:
        return (norm,) if norm else ()
    stop = len(norm) - _LEAK_WINDOW
    return tuple(norm[i:i + _LEAK_WINDOW] for i in range(0, stop + 1, _LEAK_STRIDE))


def _leaks_system_prompt(text: str) -> bool:
    """True si `text` reproduce, verbatim y de forma contigua, un tramo del
    system prompt real (fuga estructural) o contiene una frase-gatillo conocida.
    """
    if not text:
        return False
    if _LEAK_TRIGGER_RE.search(text):
        return True
    norm = _normalize_for_leak(text)
    if len(norm) < _LEAK_WINDOW:
        return False
    return any(w and w in norm for w in _system_prompt_windows())


_LEAK_REFUSAL = (
    "No puedo compartir mis instrucciones internas. ¿En qué más puedo ayudarte "
    "sobre exportación y comercio del arándano peruano?"
)


def check_output(text: str) -> str:
    """Evita filtrar prompts de sistema y PII de alto riesgo en la respuesta.

    LLM07 (System Prompt Leakage): si se detecta fuga (por frase-gatillo o por
    coincidencia estructural con el prompt real), la respuesta se REEMPLAZA por
    un rechazo seguro — no basta con solo registrar el evento, porque el texto
    filtrado ya habría llegado al usuario.

    Red de seguridad de PII: redacta números de tarjeta validados con Luhn (que
    prácticamente nunca son contenido legítimo en este dominio). No se redactan
    teléfonos/emails de la salida para no borrar contactos oficiales legítimos
    (p. ej. de SENASA/PROMPERU) que sí pueden aparecer en las respuestas.
    """
    if text and _leaks_system_prompt(text):
        logger.warning("guardrail_output_leak_filtered")
        text = _LEAK_REFUSAL
    if text and _has_valid_card(text):
        logger.warning("guardrail_output_pii_card_redacted")
        text = _redact_cards(text)
    return text


# Confirmación afirmativa clara al INICIO del mensaje (ES/EN). Determinística: NO
# se delega al LLM si el usuario "realmente confirmó". Mitiga LLM06 (Excessive
# Agency) en tools que disparan acciones consecuentes/irreversibles (p. ej. enviar
# la solicitud de un ciudadano a una entidad pública por correo): aunque el LLM
# decida invocar la tool, la tool exige en código que el turno actual del usuario
# empiece con una expresión afirmativa reconocible.
_AFFIRMATIVE_RE = re.compile(
    # El prefijo tolera el signo de apertura "¡"/"¿" del español correcto
    # ("¡Sí, adelante!"), comillas y *negrita/_cursiva_ de WhatsApp: sin esto,
    # una confirmación perfectamente válida y bien escrita no matcheaba nunca
    # (bug real: "¡Sí!" no empieza con \s, así que ^\s* no lo saltaba).
    #
    # "va" y "por favor" NO están aquí a propósito, aunque puedan sonar
    # afirmativas: son demasiado comunes como arranque de una oración SIN
    # relación ("Va a llover...", "Por favor ayúdame con..."). Bug real:
    # calzaban como confirmación afirmativa de pasada, arriesgando disparar
    # una derivación o un escalamiento a humano sobre un caso viejo con un
    # mensaje que no confirmaba nada. "vale" se conserva (es una confirmación
    # real en español) pero con guardia: "vale la pena..." es la colocación
    # que más se confunde con ella y NO es una confirmación. "Falla cerrado"
    # (ver docstring de la función) exige preferir perder alguna confirmación
    # real y poco común con estas palabras antes que un falso positivo.
    r"^[\s¡¿\"'*_~\-–—]*(s[ií]|dale|ok(ay|ey)?|confirmo|correcto|procede|adelante|claro|"
    r"de\s+acuerdo|afirmativo|exacto|perfecto|vale(?!\s+la\s+pena)|hazlo|env[ií]al[oa]|"
    r"est[aá]\s+bien|yes|confirm(ed)?|sure|go\s+ahead)\b",
    re.IGNORECASE,
)


def is_affirmative_confirmation(text: str) -> bool:
    """True si `text` es una confirmación afirmativa clara y explícita.

    Exige que el mensaje EMPIECE con una expresión afirmativa reconocible (no
    basta con que la contenga en algún punto): así un mensaje largo que solo
    mencione "sí" de pasada, o contenido inyectado, no cuenta como confirmación
    real del usuario. Falla cerrado: ante duda, no es confirmación.
    """
    return bool(_AFFIRMATIVE_RE.match(normalize_text(text or "")))


class RateLimiter:
    """Rate limiting por usuario respaldado en Firestore (ventana deslizante simple).

    Para el MVP usa una ventana por minuto. Degrada a 'permitir' si Firestore
    no está disponible (no debe tumbar el servicio).
    """

    def __init__(self, store_collection: str = "rate_limits") -> None:
        self._collection = store_collection
        self._client = None

    def _db(self):
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client(project=settings.gcp_project_id)
        return self._client

    def allow(self, user_id: str) -> bool:
        window = int(time.time() // 60)
        doc_id = f"{user_id}:{window}"
        try:
            from google.cloud import firestore

            ref = self._db().collection(self._collection).document(doc_id)

            @firestore.transactional
            def _txn(txn):
                snap = ref.get(transaction=txn)
                count = (snap.to_dict() or {}).get("count", 0) if snap.exists else 0
                if count >= settings.rate_limit_per_minute:
                    return False
                txn.set(ref, {"count": count + 1, "window": window}, merge=True)
                return True

            return _txn(self._db().transaction())
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate_limiter_unavailable", error=str(exc))
            return True
