"""Catálogo cerrado de entidades públicas y clasificador de derivación.

Diagnóstico previo: la selección de entidad debe resolverse como un agente
REACTIVO BASADO EN MODELO, no delegando en texto libre generado por el LLM
orquestador (riesgo de invención/inconsistencia de nombres, ver `app.derivation`).

Este módulo define el conjunto CERRADO de las 10 entidades públicas a las que el
asistente puede canalizar un caso, cada una con ~15 ejemplos distintivos (few-shot)
de puntos de dolor que le corresponden, y clasifica el resumen del caso contra ese
catálogo con un LLM determinista (Flash, temperatura 0), devolviendo SOLO ids que
existen en el catálogo (nunca un nombre inventado).

`identificar_entidades` es fail-open: cualquier fallo (LLM, parseo) devuelve
lista vacía, y quien la invoque debe usar esa vacía como señal para caer de vuelta
a la propuesta del LLM orquestador en vez de bloquear la derivación.

`evaluar_urgencia` añade el eje de "análisis del sentir" (temor, inminencia,
magnitud de la pérdida) que el objetivo del proyecto declara pero que el
clasificador de puntos de dolor (`app.concerns`) no captura: ese módulo corre
en paralelo, después de responder, y solo etiqueta TIPO (reclamo/pedido/...)
para el informe diario — nunca llega a influir en qué entidad recibe el caso.
Aquí, con el Fenómeno de El Niño ya confirmado para los próximos meses, la
urgencia detectada SÍ condiciona la elección de entidad: un caso "alta"/
"critica" vinculado a clima o desastre prioriza incluir a las entidades de
emergencia (INDECI, SENAMHI/ENFEN) además de la entidad temática regular.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class EntityProfile:
    id: str
    nombre: str
    dominio: str
    ejemplos: tuple[str, ...]


ENTITY_CATALOG: tuple[EntityProfile, ...] = (
    EntityProfile(
        id="senasa",
        nombre="SENASA",
        dominio="Sanidad agraria: plagas, enfermedades, certificación fitosanitaria "
                "y protocolos sanitarios de exportación.",
        ejemplos=(
            "Encontré una plaga desconocida en mis plantas de arándano y no sé qué hacer.",
            "Necesito el certificado fitosanitario para exportar a China.",
            "¿Qué protocolo de cuarentena debo seguir antes de embarcar mi fruta?",
            "Mi cultivo tiene manchas foliares, temo que sea una enfermedad regulada.",
            "¿Cómo solicito una inspección sanitaria previa a la cosecha?",
            "¿Cómo registro mi predio como área libre de mosca de la fruta?",
            "Necesito saber qué insecticidas están autorizados para uso en arándano de exportación.",
            "Mis vecinos no fumigan y la plaga se está pasando a mi parcela, ¿a quién reporto esto?",
            "¿Qué documentos pide SENASA para renovar mi código de exportador?",
            "Encontré larvas en mis frutos, ¿es una plaga cuarentenaria?",
            "¿Cómo solicito la habilitación sanitaria de mi packing?",
            "Quiero saber el límite máximo de residuos de plaguicidas permitido para exportar a Estados Unidos.",
            "¿SENASA hace fiscalización de agroquímicos falsificados?",
            "Necesito el registro sanitario para mi vivero de plantones de arándano.",
            "¿Cómo denuncio el ingreso de material vegetal sin control sanitario a la zona?",
        ),
    ),
    EntityProfile(
        id="senamhi",
        nombre="SENAMHI / ENFEN",
        dominio="Clima, pronóstico meteorológico y monitoreo oficial del Fenómeno "
                "de El Niño.",
        ejemplos=(
            "¿Va a llover fuerte esta semana en Chepén?",
            "Tengo miedo de que El Niño arrase mi cosecha este año, ¿hay alguna alerta?",
            "¿Cuál es el pronóstico de temperatura del mar para los próximos meses?",
            "No sé si debo adelantar la cosecha por el calor que se viene.",
            "¿Hay un boletín oficial sobre el estado actual del FEN?",
            "¿Cuál es la probabilidad de que El Niño se intensifique este trimestre?",
            "Necesito el pronóstico de heladas para las próximas semanas.",
            "¿Dónde veo el registro histórico de temperaturas de mi zona?",
            "¿Hay alerta de vientos fuertes para mi distrito esta semana?",
            "Quiero suscribirme a los boletines climáticos de SENAMHI.",
            "¿Qué tan confiable es el pronóstico a 15 días para planear el riego?",
            "¿Cuándo se espera el pico de temperatura del mar frente a Piura?",
            "Necesito un reporte oficial de precipitación acumulada del mes pasado.",
            "¿ENFEN ya declaró el estado actual del Fenómeno de El Niño?",
            "¿Hay riesgo de sequía después de esta temporada de lluvias?",
        ),
    ),
    EntityProfile(
        id="indeci",
        nombre="INDECI",
        dominio="Riesgo de desastres, emergencias, evacuación y apoyo humanitario "
                "ante huaicos e inundaciones.",
        ejemplos=(
            "El río está creciendo y temo que se desborde cerca de mi parcela.",
            "¿Cómo reporto un huaico que dañó el camino a mi fundo?",
            "Necesito ayuda humanitaria porque el agua inundó mi vivienda y almacén.",
            "¿Dónde queda el refugio o albergue más cercano ante una emergencia?",
            "Quiero saber el protocolo de evacuación para mi zona ante lluvias intensas.",
            "Necesito reportar daños en mi vivienda tras el desborde del río.",
            "¿Cómo accedo al padrón de damnificados para recibir ayuda?",
            "¿Dónde entrego mi solicitud de kit de ayuda humanitaria?",
            "Quiero saber si mi zona está declarada en emergencia.",
            "¿Cómo se activa el sistema de alerta temprana ante huaicos?",
            "Necesito apoyo para evacuar maquinaria antes de que suba el nivel del río.",
            "¿INDECI tiene brigadas de rescate cerca de mi localidad?",
            "Perdí mi almacén de insumos en la inundación, ¿cómo reporto la pérdida?",
            "¿Cómo participo en un simulacro de evacuación para mi comunidad?",
            "Necesito saber la ruta de evacuación oficial más cercana a mi fundo.",
        ),
    ),
    EntityProfile(
        id="midagri",
        nombre="MIDAGRI / AGRO RURAL",
        dominio="Apoyo agrario general: subsidios, insumos y asistencia al productor.",
        ejemplos=(
            "¿Hay algún programa de apoyo para reponer plantones perdidos por el Niño?",
            "Quiero saber si hay créditos o subsidios agrarios disponibles este año.",
            "¿Cómo accedo a semillas o insumos subsidiados para mi parcela?",
            "Necesito orientación general sobre políticas agrarias del gobierno.",
            "¿MIDAGRI tiene algún censo o registro que deba actualizar como productor?",
            "¿Cómo me inscribo en el padrón de productores agrarios?",
            "Quiero saber si hay algún seguro agrario subsidiado disponible.",
            "¿MIDAGRI tiene un programa de renovación de plantones de arándano?",
            "Necesito información sobre el bono agrario de este año.",
            "¿Cómo solicito asistencia técnica de Agro Rural para mi asociación?",
            "¿Existen líneas de crédito agrario con tasa preferencial?",
            "Quiero saber qué requisitos pide MIDAGRI para el padrón de pequeño productor.",
            "¿Hay algún fondo de contingencia agraria ante El Niño?",
            "Necesito orientación sobre el registro de predio rural.",
            "¿Cómo actualizo mis datos en el censo agropecuario?",
        ),
    ),
    EntityProfile(
        id="cite_chavimochic",
        nombre="CITEagroindustrial Chavimochic",
        dominio="Asistencia técnica en campo y planta, transferencia tecnológica, "
                "laboratorios, control de calidad, procesamiento y valor agregado.",
        ejemplos=(
            "¿Pueden ayudarme a mejorar el manejo poscosecha de mi arándano?",
            "Necesito analizar en laboratorio la calidad de mi fruta antes de exportar.",
            "Quiero capacitación técnica para mejorar el rendimiento de mi parcela.",
            "¿Cómo agrego valor a mi producción, por ejemplo procesando pulpa o mermelada?",
            "Busco asesoría técnica para adoptar una nueva tecnología de riego.",
            "Necesito un análisis de suelo para optimizar la fertilización de mi parcela.",
            "¿Cómo agendo una capacitación en manejo integrado de plagas?",
            "Quiero certificar la calidad de mi fruta antes de negociar con un comprador.",
            "¿El CITE puede ayudarme a diseñar una línea de procesamiento de pulpa?",
            "Necesito asesoría para automatizar el riego tecnificado de mi campo.",
            "¿Tienen laboratorio para medir grados Brix de mi arándano?",
            "Quiero mejorar el empaque de mi fruta para reducir mermas en transporte.",
            "¿Ofrecen capacitación en buenas prácticas agrícolas (BPA)?",
            "Necesito ayuda técnica para diagnosticar por qué baja el rendimiento de mi parcela.",
            "¿Cómo accedo a los servicios de planta piloto del CITE?",
        ),
    ),
    EntityProfile(
        id="redcite",
        nombre="RedCITE (ITP - PRODUCE)",
        dominio="Red nacional de CITEs: innovación productiva y transferencia "
                "tecnológica sectorial más allá de Chavimochic.",
        ejemplos=(
            "¿Hay algún CITE que me pueda apoyar además del de Chavimochic?",
            "Quiero innovar en mi proceso productivo, ¿con quién del ITP hablo?",
            "Busco capacitación en innovación tecnológica para mi asociación de productores.",
            "¿La red de CITEs tiene programas de transferencia tecnológica para arándano?",
            "Necesito contacto con el ITP para mejorar mi línea de producción.",
            "¿Hay un CITE especializado en otros cultivos además del arándano?",
            "Quiero saber qué CITEs del país trabajan innovación en agroindustria.",
            "¿Cómo postulo a un fondo de innovación del ITP?",
            "Necesito contacto con un CITE que apoye el desarrollo de nuevos productos derivados de fruta.",
            "¿La red de CITEs tiene programas de mentoría para emprendedores agroindustriales?",
            "Quiero saber si existe un CITE textil o pesquero al que pueda derivar una consulta de un familiar.",
            "¿Cómo se financia un proyecto de innovación a través del ITP?",
            "Necesito información sobre certificaciones de innovación que ofrece la red CITE.",
            "¿Hay talleres de RedCITE sobre digitalización de procesos agroindustriales?",
            "¿Cómo me conecto con otro CITE si el de Chavimochic no cubre mi necesidad específica?",
        ),
    ),
    EntityProfile(
        id="promperu",
        nombre="PROMPERÚ",
        dominio="Promoción de exportaciones, inteligencia de mercado, ferias y "
                "oportunidades comerciales.",
        ejemplos=(
            "¿Cómo consigo compradores de arándano en Europa?",
            "Quiero participar en una feria internacional de exportación.",
            "¿Qué mercados tienen mayor demanda de arándano fresco este año?",
            "Necesito asesoría para iniciar mi primera exportación.",
            "¿PROMPERÚ tiene programas de capacitación para exportadores nuevos?",
            "¿Qué requisitos pide la Unión Europea para importar arándano fresco?",
            "Necesito contactos de importadores en Asia interesados en fruta peruana.",
            "¿Cuándo es la próxima misión comercial organizada por PROMPERÚ?",
            "Quiero un estudio de mercado sobre la demanda de arándano orgánico.",
            "¿Cómo registro mi empresa en el directorio de exportadores de PROMPERÚ?",
            "Necesito asesoría para fijar el precio de exportación de mi producto.",
            "¿PROMPERÚ ofrece capacitación en negociación internacional?",
            "Quiero saber qué ferias virtuales de agroexportación hay este año.",
            "¿Cómo obtengo información sobre aranceles preferenciales por tratados de libre comercio?",
            "Necesito ayuda para elaborar mi ficha de producto para exportación.",
        ),
    ),
    EntityProfile(
        id="sunat",
        nombre="SUNAT",
        dominio="Tributación, aranceles y trámites aduaneros.",
        ejemplos=(
            "¿Qué impuestos debo pagar al exportar arándano?",
            "Necesito saber el régimen tributario correcto para mi empresa agrícola.",
            "¿Cómo hago el trámite aduanero para embarcar mi contenedor?",
            "Tengo una duda sobre una multa tributaria que me llegó.",
            "¿Qué beneficios tributarios existen para exportadores agrícolas?",
            "¿Cómo obtengo mi RUC para formalizar mi negocio agrícola?",
            "Necesito saber el procedimiento de drawback para mi exportación.",
            "¿Qué documentos aduaneros necesito para el régimen de exportación definitiva?",
            "Tengo dudas sobre el crédito fiscal del IGV en mi actividad agraria.",
            "¿Cómo declaro mis ingresos si recién empiezo a exportar?",
            "Necesito el cronograma de vencimientos tributarios de este año.",
            "¿Qué pasa si mi contenedor es observado en la aduana?",
            "¿Existen beneficios tributarios para la actividad agraria hasta qué año?",
            "Necesito orientación sobre la factura electrónica para mis ventas.",
            "¿Cómo tramito la devolución del IGV a exportadores?",
        ),
    ),
    EntityProfile(
        id="gobierno_regional",
        nombre="Gobierno Regional",
        dominio="Gestión regional: infraestructura, proyectos agrarios regionales "
                "y coordinación de riesgos.",
        ejemplos=(
            "El canal de regadío de mi zona está dañado, ¿quién lo repara?",
            "Quiero que el gobierno regional invierta en un proyecto de defensa ribereña.",
            "¿A quién reclamo por el mal estado de la carretera hacia mi fundo?",
            "Necesito el apoyo del gobierno regional para un proyecto agrario de mi asociación.",
            "¿Hay alguna oficina regional que coordine la respuesta al Fenómeno de El Niño?",
            "Quiero proponer un proyecto de mejoramiento del canal madre de mi valle.",
            "¿A quién le corresponde la rehabilitación de la trocha que conecta mi fundo con la carretera principal?",
            "Necesito saber si hay presupuesto regional para defensas ribereñas este año.",
            "¿El gobierno regional tiene un plan de contingencia ante El Niño para mi provincia?",
            "Quiero presentar una queja por la demora en un proyecto de irrigación regional.",
            "¿Cómo participo en el presupuesto participativo de mi región?",
            "Necesito información sobre el plan regional de desarrollo agrario.",
            "¿Existe algún programa regional de electrificación rural para mi zona?",
            "¿Quién coordina el dragado del río a nivel regional antes de la temporada de lluvias?",
            "Necesito el contacto de la gerencia regional de agricultura.",
        ),
    ),
    EntityProfile(
        id="municipalidad",
        nombre="Municipalidad",
        dominio="Gestión local: drenaje pluvial, licencias municipales y "
                "ordenamiento territorial local.",
        ejemplos=(
            "El desagüe de mi calle está tapado y se inunda cada vez que llueve.",
            "Necesito una licencia municipal para mi almacén de acopio.",
            "¿Cómo reporto un terreno abandonado que acumula basura en mi distrito?",
            "Quiero saber si mi municipalidad limpia los canales antes de la temporada de lluvias.",
            "¿Dónde tramito un permiso local para una feria agrícola en mi pueblo?",
            "Necesito el permiso municipal para instalar un cerco perimétrico en mi parcela.",
            "¿Cómo reporto un poste de luz caído que bloquea el acceso a mi fundo?",
            "Quiero saber si mi distrito tiene un plan de limpieza de acequias antes de las lluvias.",
            "¿Dónde tramito la licencia de funcionamiento para mi tienda de insumos agrícolas?",
            "Necesito que la municipalidad recoja los residuos acumulados cerca de mi parcela.",
            "¿Cómo denuncio una construcción informal que bloquea el drenaje de mi zona?",
            "Quiero saber el horario de atención de la oficina de defensa civil municipal.",
            "¿La municipalidad tiene algún programa de arborización o control de erosión?",
            "Necesito el certificado de zonificación de mi terreno.",
            "¿Cómo solicito el mantenimiento del alumbrado público en el camino rural?",
        ),
    ),
)

_ENTITY_BY_ID = {e.id: e for e in ENTITY_CATALOG}

URGENCY_LEVELS = ("baja", "media", "alta", "critica")

_URGENCY_PROMPT = (
    "Eres un analista de riesgo que evalúa la URGENCIA de un caso de un "
    "productor agrícola peruano (contexto: Fenómeno de El Niño confirmado para "
    "los próximos meses). Evalúa por el TEMOR, la INMINENCIA del riesgo y la "
    "MAGNITUD de la pérdida (económica, del cultivo, la vivienda o la "
    "seguridad) que expresa el ciudadano — NO por el tema formal del pedido.\n\n"
    "Devuelve UN solo nivel:\n"
    "- \"baja\": consulta informativa, sin riesgo ni pérdida en curso.\n"
    "- \"media\": inquietud o pedido concreto, sin urgencia inmediata.\n"
    "- \"alta\": riesgo probable o pérdida parcial ya en curso (p. ej. plaga "
    "avanzando, lluvias que ya afectan el cultivo).\n"
    "- \"critica\": peligro inminente para la vida, la vivienda o pérdida "
    "total/severa del cultivo o sustento (p. ej. inundación en curso, huaico, "
    "desborde de río, pérdida total de cosecha).\n\n"
    "Devuelve EXCLUSIVAMENTE el nivel entre comillas, sin texto adicional ni "
    "```: \"baja\", \"media\", \"alta\" o \"critica\".\n\n"
    "CASO:\n{resumen}"
)


def evaluar_urgencia(resumen: str) -> str:
    """Nivel de urgencia del caso (el "análisis del sentir" del ciudadano).

    Complementa `identificar_entidades`: mientras ese clasificador decide el
    ÁMBITO (qué entidad), este evalúa la URGENCIA para que casos graves
    prioricen entidades de emergencia. Fail-open: ante cualquier error o
    resumen vacío devuelve "media" (nivel neutro que ni infla ni suprime la
    urgencia real de un caso que no se pudo evaluar).
    """
    resumen = (resumen or "").strip()
    if not resumen:
        return "media"
    try:
        from app.agent.models import invoke_with_failover

        # Flash por defecto (determinista), con failover de ubicación ante 429.
        resp = invoke_with_failover(
            _URGENCY_PROMPT.format(resumen=resumen[:1500]), temperature=0.0)
        content = getattr(resp, "content", "") or ""
        if isinstance(content, list):  # Gemini puede devolver bloques
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        nivel = str(content).strip().strip('"').strip("`").lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("urgency_classification_failed", error=str(exc))
        return "media"
    return nivel if nivel in URGENCY_LEVELS else "media"


def _build_classification_prompt(resumen: str, urgencia: str = "") -> str:
    bloques = []
    for e in ENTITY_CATALOG:
        ejemplos = "\n".join(f"  - {ej}" for ej in e.ejemplos)
        bloques.append(f'"{e.id}" ({e.nombre}) — {e.dominio}\n{ejemplos}')
    catalogo = "\n\n".join(bloques)
    ids = ", ".join(f'"{e.id}"' for e in ENTITY_CATALOG)
    urgencia_clause = ""
    if urgencia in ("alta", "critica"):
        urgencia_clause = (
            f'\nEste caso tiene URGENCIA "{urgencia}" (riesgo inminente o '
            "pérdida grave declarados por el ciudadano). El Fenómeno de El "
            "Niño está CONFIRMADO para los próximos meses: si el caso está "
            'vinculado a clima, desastre o pérdida de cultivo, incluye también '
            '"indeci" y/o "senamhi" aunque el caso toque además otro ámbito '
            "temático, para asegurar atención de emergencia junto con la "
            "atención regular.\n"
        )
    return (
        "Eres un clasificador determinista que decide a cuál(es) entidad(es) "
        "públicas peruanas corresponde canalizar el CASO de un ciudadano (una "
        "solicitud formal o un punto de dolor: preocupación, temor, inquietud o "
        "reclamo). Elige SOLO entre el siguiente catálogo CERRADO, guiándote por "
        "los ejemplos distintivos de cada entidad. El caso puede corresponder a "
        f"MÁS DE UNA entidad si toca varios ámbitos a la vez.\n{urgencia_clause}\n"
        f"CATÁLOGO:\n{catalogo}\n\n"
        f"Devuelve EXCLUSIVAMENTE un JSON: una lista de ids del catálogo ({ids}). "
        "Sin texto adicional ni ```. Si ninguna aplica con claridad, devuelve [].\n\n"
        f"CASO:\n{resumen}"
    )


def _parse_ids(raw: str) -> list[str]:
    """Extrae ids del JSON del LLM, descartando cualquiera fuera del catálogo."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    seen: list[str] = []
    for item in data:
        key = str(item).strip().lower()
        if key in _ENTITY_BY_ID and key not in seen:
            seen.append(key)
    return seen


def identificar_entidades(resumen: str, urgencia: str = "") -> list[str]:
    """Clasifica el resumen del caso contra el catálogo cerrado (multi-etiqueta).

    `urgencia` (opcional, ver `evaluar_urgencia`) condiciona la clasificación:
    si es "alta"/"critica", el clasificador prioriza incluir a las entidades de
    emergencia (INDECI, SENAMHI/ENFEN) cuando el caso toca clima o desastre,
    aunque también aplique otra entidad temática — así el "análisis del sentir"
    del ciudadano se traduce en una elección de entidad más idónea, no solo en
    una etiqueta informativa.

    Devuelve los NOMBRES de despliegue (no los ids internos) de las entidades que
    aplican, en el mismo formato que espera `app.derivation.send_derivations`.
    Fail-open: cualquier fallo (LLM caído, JSON inválido) devuelve `[]`; quien
    invoque esta función debe interpretar `[]` como "sin veredicto del modelo" y
    recurrir a la propuesta original del LLM orquestador, no como "ninguna
    entidad aplica".
    """
    resumen = (resumen or "").strip()
    if not resumen:
        return []
    try:
        from app.agent.models import invoke_with_failover

        # Flash por defecto (determinista), con failover de ubicación ante 429.
        resp = invoke_with_failover(
            _build_classification_prompt(resumen[:1500], urgencia), temperature=0.0)
        content = getattr(resp, "content", "") or ""
        if isinstance(content, list):  # Gemini puede devolver bloques
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        ids = _parse_ids(str(content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("entity_classification_failed", error=str(exc))
        return []
    return [_ENTITY_BY_ID[i].nombre for i in ids]


def match_known_entities(nombres: list[str]) -> list[str]:
    """Valida nombres de entidad en texto libre contra el catálogo cerrado.

    Emparejamiento por substring insensible a mayúsculas (mismo criterio que
    `app.derivation._resolve_destino`), para reconocer variantes razonables del
    nombre (p. ej. "CITE Chavimochic" -> "CITEagroindustrial Chavimochic").
    Descarta cualquier nombre que no corresponda a ninguna entidad del
    catálogo: nunca se inventa ni se deja pasar una entidad no reconocida.

    Complementa (no reemplaza) a `identificar_entidades`: esa clasifica el
    CASO contra el catálogo; esta valida nombres de entidad que el LLM
    orquestador ya propuso en texto libre (p. ej. porque se los ofreció al
    ciudadano en un turno previo y el ciudadano confirmó), para no perder de
    vista una entidad que el clasificador —más estricto por diseño— no
    hubiera derivado solo del resumen del caso.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in nombres:
        key = (raw or "").strip().lower()
        if not key:
            continue
        for e in ENTITY_CATALOG:
            nombre_low = e.nombre.lower()
            if key in nombre_low or nombre_low in key:
                if e.id not in seen:
                    seen.add(e.id)
                    out.append(e.nombre)
                break
    return out
