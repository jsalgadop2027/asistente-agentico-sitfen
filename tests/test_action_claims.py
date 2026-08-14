"""Antialucinación de ACCIONES: el agente no puede afirmar que canalizó o escaló
un caso si la tool correspondiente no se ejecutó de verdad en el turno.

Regresión de un bug real de producción: ante una vía colapsada, el agente
respondió "He comunicado tu interés ... a SENASA y al CITEagroindustrial" sin
invocar ninguna tool — no salió ningún correo, no quedó registro, y el ciudadano
quedó creyendo que el Estado ya estaba avisado.
"""
from app.agent.orchestrator import _strip_unbacked_action_claim, _tool_was_used


class _Msg:
    """Doble mínimo de ToolMessage/AIMessage (type + name, como LangGraph)."""
    def __init__(self, type_: str, name: str = "", content: str = ""):
        self.type = type_
        self.name = name
        self.content = content


_AI = _Msg("ai", content="respuesta")
_DERIV = _Msg("tool", name="derivar_solicitud_entidad", content="✅ Listo.")
_HANDOFF = _Msg("tool", name="escalar_a_humano", content="✅ Ya avisé.")
_RAG = _Msg("tool", name="consultar_base_conocimiento", content="[Fuentes: a.pdf]")


# ------------------------------- _tool_was_used -------------------------------
def test_detects_action_tool_that_ran():
    assert _tool_was_used([_AI, _DERIV], ("derivar_solicitud_entidad",))


def test_ignores_unrelated_tool():
    assert not _tool_was_used([_AI, _RAG], ("derivar_solicitud_entidad",))


def test_ignores_ai_message_mentioning_tool_name():
    """Un AIMessage que nombre la tool no cuenta como ejecución."""
    fake = _Msg("ai", name="derivar_solicitud_entidad", content="la invocaré")
    assert not _tool_was_used([fake], ("derivar_solicitud_entidad",))


# ------------------------ afirmaciones SIN respaldo ---------------------------
def test_blocks_the_real_production_claim():
    """El texto exacto que el agente envió por WhatsApp sin ejecutar la tool."""
    claim = ("¡Excelente, Julio! He comunicado tu interés en capacitar a tu "
             "personal en buenas prácticas agrícolas y manejo integrado de plagas "
             "a **SENASA y al CITEagroindustrial Chavimochic**.")
    out, stripped = _strip_unbacked_action_claim(claim, [_AI])
    assert out != claim
    assert "NO he canalizado" in out
    # `stripped=True` es la señal que orchestrator.answer() usa para NO tratar
    # este texto de reconfirmación como un ofrecimiento nuevo (ver el bug real
    # de producción en test_reconfirmation_text_is_flagged_as_stripped abajo).
    assert stripped is True


def test_blocks_variants_without_backing():
    for claim in (
        "Ya canalicé tu caso a INDECI.",
        "Tu solicitud fue derivada al Gobierno Regional.",
        "He escalado tu caso a una persona del equipo.",
        "Tu caso ha sido comunicado a SENAMHI.",
        "Ya registré y envié tu pedido.",
        "Quedó registrado y canalizado a la municipalidad.",
    ):
        out, stripped = _strip_unbacked_action_claim(claim, [_AI])
        assert out != claim, f"no bloqueó: {claim!r}"
        assert stripped is True


# ------------------------ afirmaciones CON respaldo ---------------------------
def test_allows_claim_when_derivation_tool_ran():
    claim = "✅ Listo. Registré y canalicé tu caso a SENASA."
    out, stripped = _strip_unbacked_action_claim(claim, [_AI, _DERIV])
    assert out == claim and stripped is False


def test_allows_claim_when_handoff_tool_ran():
    claim = "Ya avisé a una persona del equipo; te escribirá en breve."
    out, stripped = _strip_unbacked_action_claim(claim, [_AI, _HANDOFF])
    assert out == claim and stripped is False


# ------------- la tool corrió pero NO completó la acción ----------------------
def test_blocks_claim_when_confirmation_gate_rejected_the_tool():
    """El gate rechaza la derivación por falta de un "Sí" real, pero igual queda
    un ToolMessage en el turno. Ese texto PIDE confirmación, no la confirma: no
    debe servir de respaldo para que el LLM narre un éxito inexistente."""
    rechazada = _Msg("tool", name="derivar_solicitud_entidad",
                     content=("Antes de canalizar tu caso necesito tu confirmación "
                              "explícita. ¿Confirmas que deseas que lo envíe?"))
    claim = "Ya canalicé tu caso a SENASA."
    out, stripped = _strip_unbacked_action_claim(claim, [_AI, rechazada])
    assert out != claim and stripped is True


def test_blocks_claim_when_sending_failed():
    fallida = _Msg("tool", name="derivar_solicitud_entidad",
                   content="No pude enviar tu caso en este momento.")
    claim = "Tu caso fue derivado a INDECI."
    out, stripped = _strip_unbacked_action_claim(claim, [_AI, fallida])
    assert out != claim and stripped is True


# ------------------------- NO debe tocar ofrecimientos ------------------------
def test_does_not_touch_offers_or_questions():
    """Los OFRECIMIENTOS son el flujo normal previo a la confirmación: si se
    bloquearan, el usuario nunca llegaría a confirmar y la derivación moriría."""
    for texto in (
        "¿Deseas que comunique tu caso a SENASA y al CITEagroindustrial?",
        "Puedo canalizar tu solicitud a INDECI si me lo confirmas.",
        "Si quieres, escalo tu caso a una persona del equipo.",
        "Te recomiendo comunicar esta situación a la municipalidad.",
        "SENASA es la entidad que atiende plagas cuarentenarias.",
    ):
        out, stripped = _strip_unbacked_action_claim(texto, [_AI])
        assert out == texto and stripped is False, texto


# --------- regresión: el texto de reconfirmación NO debe colarse como oferta --
def test_reconfirmation_text_is_flagged_as_stripped():
    """Bug real de producción: un "Sí" ambiguo (sin caso pendiente real) hizo
    que el LLM alucinara una derivación; el guardarraíl la bloqueó y devolvió el
    texto genérico "¿Confirmas que lo envíe a las entidades correspondientes?".
    Ese texto coincide por accidente con el patrón de `pending_derivation.
    is_offer` (contiene "¿...que lo envíe...?"), así que sin la bandera
    `stripped=True` el orquestador lo registraba como un ofrecimiento NUEVO y
    guardaba como "caso pendiente" el último mensaje sustantivo del usuario —
    que podía no tener nada que ver con una derivación real. Terminó
    canalizando una petición de gráfico del ENFEN a SENAMHI como si fuera un
    punto de dolor genuino."""
    from app.pending_derivation import is_offer

    claim = "Ya canalicé tu caso a SENASA."
    out, stripped = _strip_unbacked_action_claim(claim, [_AI])
    assert stripped is True
    assert is_offer(out)  # confirma que el texto SÍ dispara el falso positivo
