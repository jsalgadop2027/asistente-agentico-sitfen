"""Admin UI (Streamlit): reporte de atenciones normales (no derivadas).

Fuente principal: la colección Firestore `attentions` (ver `app.attentions`),
que registra CADA turno de WhatsApp que el agente respondió sin bloqueo — no
solo los que `app.concerns` clasifica como punto de dolor accionable (reclamo/
pedido/sugerencia/recomendación/preocupación). La mayoría del tráfico real son
consultas informativas comunes que ese clasificador etiqueta "ninguno" y por
eso nunca llegaban a `user_concerns`; sin `attentions`, este reporte las pasaba
por alto por completo.

Esta página cruza `attentions` con dos colecciones más:
  - `derivations` (ver `admin_ui/_derivaciones.py`): una atención NO es
    "normal" si el mismo usuario tuvo una derivación registrada dentro de una
    ventana ASIMÉTRICA alrededor de esa atención (`_DERIVATION_WINDOW_BEFORE_MIN`
    / `_DERIVATION_WINDOW_AFTER_SEC`, ver comentario junto a esas constantes) —
    no simplemente "el mismo día": un usuario que deriva varios casos
    distintos en un mismo día —p. ej. una cuenta de pruebas— no debe perder
    TODAS sus atenciones de ese día, solo las cercanas en el tiempo al turno
    de confirmación real. Sigue siendo una aproximación (no hay una
    referencia directa atención→derivación), pero acotada a la ventana en la
    que de verdad ocurre esa confirmación dentro de la misma sesión.
  - `user_concerns`: cuando el mismo usuario tuvo una inquietud clasificada el
    mismo día, se usa su tipo para etiquetar la atención en el desglose "Por
    tipo"; si no, se etiqueta "Consulta general" (la mayoría del volumen).

También agrupa por usuario para resaltar las consultas RECURRENTES (dos o más
atenciones normales en el periodo elegido), y desglosa por CANAL de entrada
(texto/voz/imagen, ver `app.agent.turn_context`) — antes de propagar ese dato,
una consulta por nota de voz quedaba indistinguible de una escrita una vez
transcrita, así que no se podía reportar "cuántas consultas llegaron por voz".

Ejecutar local:  streamlit run admin_ui/app.py   (esta página aparece en el menú)
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import os
import sys

# Garantizar que la raíz del proyecto esté en sys.path para que 'app.*' resuelva
# al paquete. Este archivo vive en admin_ui/, así que la raíz es dos niveles arriba.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altair as alt
import pandas as pd
import streamlit as st

from app.attentions import AttentionStore, lima_day_str
from app.concerns import CONCERN_TYPES, ConcernStore
from app.config import settings
from app.derivation import DerivationStore

# st.set_page_config lo llama el host de navegación (admin_ui/app.py); aquí no.
st.title("💬 Atenciones Normales")
st.caption("Consultas de WhatsApp que el asistente resolvió por sí mismo, SIN "
           "canalizarlas a una entidad pública, incluidas las consultas "
           "recurrentes de un mismo usuario.")

_TIPO_LABELS = {
    "reclamo": "Reclamo", "pedido": "Pedido", "sugerencia": "Sugerencia",
    "recomendacion": "Recomendación", "preocupacion": "Preocupación",
}
_CONSULTA_GENERAL = "Consulta general"
_TIPO_ORDER = tuple(t for t in CONCERN_TYPES if t in _TIPO_LABELS)
_TIPO_COLORS = {
    "Reclamo": "#c53030", "Preocupación": "#dd6b20", "Pedido": "#2b6cb0",
    "Sugerencia": "#38a169", "Recomendación": "#805ad5",
    _CONSULTA_GENERAL: "#718096",
}

# Medio de ENTRADA real del turno (ver app.agent.turn_context): la nota de voz
# y la imagen llegan al agente ya convertidas a texto plano (transcripción/
# descripción), así que sin este campo su origen real se perdía por completo.
_MEDIO_LABELS = {"texto": "💬 Texto", "voz": "🎙️ Voz", "imagen": "📷 Imagen"}
_MEDIO_ORDER = ("texto", "voz", "imagen")
_MEDIO_COLORS = {"💬 Texto": "#2b6cb0", "🎙️ Voz": "#dd6b20", "📷 Imagen": "#38a169"}


def _medio_label(medio: str) -> str:
    return _MEDIO_LABELS.get(medio or "texto", _MEDIO_LABELS["texto"])


def _is_credentials_error(exc: Exception) -> bool:
    """True si el fallo se debe a credenciales de GCP ausentes/inválidas (ADC)."""
    try:
        from google.auth.exceptions import DefaultCredentialsError

        if isinstance(exc, DefaultCredentialsError):
            return True
    except Exception:  # noqa: BLE001
        pass
    msg = str(exc).lower()
    return ("default credentials were not found" in msg
            or "could not automatically determine credentials" in msg)


def _show_gcp_error(exc: Exception, *, context: str) -> None:
    """Muestra un error de GCP como aviso accionable (no como traza cruda)."""
    if _is_credentials_error(exc):
        st.warning(
            "🔐 **No hay credenciales de Google Cloud (ADC) en este equipo**, así "
            "que no se puede conectar con Firestore. Autentícate una sola vez y "
            "recarga la página:"
        )
        st.code(
            "gcloud auth application-default login\n"
            f"gcloud auth application-default set-quota-project {settings.gcp_project_id}",
            language="bash",
        )
        st.caption("En producción (Cloud Run) esto no aplica: usa la service "
                   "account del servicio automáticamente.")
    else:
        st.error(f"{context}: {exc}")


@st.cache_resource
def _attention_store() -> AttentionStore:
    return AttentionStore()


@st.cache_resource
def _concern_store() -> ConcernStore:
    return ConcernStore()


@st.cache_resource
def _derivation_store() -> DerivationStore:
    return DerivationStore()


@st.cache_data(ttl=30, show_spinner=False)
def _list_attentions() -> list[dict]:
    return _attention_store().list_recent()


@st.cache_data(ttl=30, show_spinner=False)
def _list_concerns() -> list[dict]:
    return _concern_store().list_recent()


@st.cache_data(ttl=30, show_spinner=False)
def _list_derivations() -> list[dict]:
    return _derivation_store().list_recent()


@st.cache_data(ttl=300, show_spinner=False)
def _user_label(user_id: str) -> str:
    """Nombre legible del usuario si está registrado; si no, id enmascarado
    (evita exponer el número de WhatsApp completo en un reporte agregado)."""
    from app.user_registry import get_user_registry, looks_like_code

    uid = (user_id or "").strip()
    if not uid:
        return "—"
    if looks_like_code(uid):
        try:
            rec = get_user_registry().get_by_code(uid)
        except Exception:  # noqa: BLE001
            rec = None
        return f"{rec.nombre} {rec.apellido} ({uid})" if rec else uid
    return f"…{uid[-4:]}" if len(uid) > 4 else uid


def _fmt_ts(ts) -> str:
    if not isinstance(ts, _dt.datetime):
        return "—"
    try:
        local = ts.astimezone(_dt.timezone.utc) + _dt.timedelta(
            hours=settings.lima_utc_offset_hours)
        return local.strftime("%Y-%m-%d %I:%M %p (Perú)")
    except Exception:  # noqa: BLE001
        return str(ts)


def _int_y_axis(series) -> alt.Axis:
    top = int(series.max()) if len(series) else 0
    return alt.Axis(format="d", values=list(range(0, top + 1)))


_PERIODOS = {"Últimos 7 días": 7, "Últimos 30 días": 30, "Últimos 90 días": 90, "Todo": None}

_CSV_COLUMNS = [
    ("day", "Fecha"), ("tipo", "Tipo"), ("medio", "Canal"), ("usuario", "Usuario"),
    ("resumen", "Resumen"),
]


def _csv_cell(r: dict, key: str) -> str:
    return str(r.get(key, "") or "")


def _attentions_to_csv(rows: list[dict]) -> bytes:
    """Serializa atenciones a CSV (UTF-8 con BOM para abrir bien en Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in _CSV_COLUMNS])
    for r in rows:
        writer.writerow([_csv_cell(r, key) for key, _ in _CSV_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")


with st.expander("ℹ️ Estado del sistema", expanded=False):
    st.write(f"**Proyecto GCP:** {settings.gcp_project_id}")
    st.write(f"**Colección de atenciones:** {settings.firestore_attentions_collection}")
    st.write(f"**Colección de inquietudes (tipo):** {settings.firestore_concerns_collection}")
    st.write(f"**Colección de derivaciones (cruce):** {settings.firestore_derivations_collection}")

col_a, col_b = st.columns([3, 1])
with col_a:
    periodo = st.selectbox("Periodo", list(_PERIODOS.keys()), index=1)
with col_b:
    st.write("")  # alinea el botón con el selectbox
    if st.button("🔄 Actualizar"):
        _list_attentions.clear()
        _list_concerns.clear()
        _list_derivations.clear()
        _user_label.clear()

try:
    all_attentions = _list_attentions()
    all_concerns = _list_concerns()
    all_derivations = _list_derivations()
except Exception as exc:  # noqa: BLE001
    all_attentions, all_concerns, all_derivations = [], [], []
    _show_gcp_error(exc, context="No se pudo leer las atenciones")

# Ventana ASIMÉTRICA alrededor de cada derivación dentro de la cual una atención
# del MISMO usuario se considera parte de ese caso derivado (ver docstring del
# módulo). La derivación se escribe a mitad del turno de confirmación (dentro de
# la tool), mientras que la atención de ESE MISMO turno se escribe al final
# (tras redactar la respuesta) — por eso el lado "después" solo necesita cubrir
# el remate de ese turno, unos segundos. El lado "antes" sí necesita ser amplio:
# cubre el ida y vuelta de varios turnos que originó el caso hasta la oferta de
# derivar. Sin esta asimetría, una pregunta nueva y sin relación hecha 1-2
# minutos DESPUÉS de una derivación (frecuente en pruebas donde el mismo
# usuario deriva varios casos seguidos) se contaba erróneamente como derivada.
_DERIVATION_WINDOW_BEFORE_MIN = 15
_DERIVATION_WINDOW_AFTER_SEC = 60

derivations_by_user: dict[str, list[dict]] = {}
for d in all_derivations:
    uid = d.get("user_id")
    if uid:
        derivations_by_user.setdefault(uid, []).append(d)


def _is_derived(attention: dict) -> bool:
    uid = attention.get("user_id")
    ts = attention.get("created_at")
    if not uid or not isinstance(ts, _dt.datetime):
        return False
    before = _dt.timedelta(minutes=_DERIVATION_WINDOW_BEFORE_MIN)
    after = _dt.timedelta(seconds=_DERIVATION_WINDOW_AFTER_SEC)
    for d in derivations_by_user.get(uid, ()):
        dts = d.get("created_at")
        if not isinstance(dts, _dt.datetime):
            continue
        delta = dts - ts  # positivo: la derivación quedó DESPUÉS de la atención
        if -after <= delta <= before:
            return True
    return False


# Cruce (usuario, día) -> inquietud clasificada ese día (si la hubo), para
# etiquetar el tipo en el desglose. `all_concerns` viene ordenado por
# `created_at` descendente, así que ante varias inquietudes el mismo día se
# queda con la más reciente (aproximación razonable, no hay más señal).
concern_by_user_day: dict[tuple, dict] = {}
for c in all_concerns:
    if c.get("tipo") not in _TIPO_LABELS:
        continue
    key = (c.get("user_id"), c.get("day"))
    concern_by_user_day.setdefault(key, c)

all_normales = [a for a in all_attentions if not _is_derived(a)]

dias = _PERIODOS[periodo]
if dias is None:
    rows = all_normales
else:
    cutoff = lima_day_str(_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=dias))
    rows = [r for r in all_normales if str(r.get("day", "")) >= cutoff]


def _tipo_for(r: dict) -> str:
    concern = concern_by_user_day.get((r.get("user_id"), r.get("day")))
    return concern["tipo"] if concern else ""


def _resumen_for(r: dict) -> str:
    concern = concern_by_user_day.get((r.get("user_id"), r.get("day")))
    if concern and concern.get("resumen"):
        return concern["resumen"]
    return r.get("message", "")


if not all_attentions:
    st.info("Aún no hay atenciones registradas.")
elif not rows:
    st.info(f"No hay atenciones normales en el periodo «{periodo}».")
else:
    # ------------------------------ Métricas ----------------------------------
    total = len(rows)
    por_usuario: dict[str, int] = {}
    con_inquietud = 0
    for r in rows:
        uid = r.get("user_id") or ""
        por_usuario[uid] = por_usuario.get(uid, 0) + 1
        if _tipo_for(r):
            con_inquietud += 1
    usuarios_distintos = len(por_usuario)
    usuarios_recurrentes = sum(1 for c in por_usuario.values() if c >= 2)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Atenciones normales", total)
    m2.metric("Usuarios atendidos", usuarios_distintos)
    m3.metric("Con consultas recurrentes", usuarios_recurrentes,
              help="Usuarios con 2 o más atenciones normales en el periodo")
    m4.metric("Con inquietud clasificada", f"{con_inquietud / total:.0%}" if total else "—",
              help="Proporción de atenciones que además trajeron un punto de dolor "
                   "clasificado (reclamo/pedido/sugerencia/recomendación/preocupación); "
                   "el resto son consultas informativas comunes")

    st.divider()

    # --------------------------- Por tipo / fecha -------------------------------
    st.subheader("Por tipo")
    por_tipo = {t: 0 for t in _TIPO_ORDER}
    por_tipo[_CONSULTA_GENERAL] = 0
    for r in rows:
        t = _tipo_for(r)
        por_tipo[t if t in _TIPO_LABELS else _CONSULTA_GENERAL] += 1
    tipo_keys = (_CONSULTA_GENERAL, *_TIPO_ORDER)
    df_tipo = pd.DataFrame({
        "Tipo": [_TIPO_LABELS.get(t, t) for t in tipo_keys],
        "Casos": [por_tipo[t] for t in tipo_keys],
    })
    chart_tipo = (
        alt.Chart(df_tipo)
        .mark_bar()
        .encode(
            x=alt.X("Tipo", sort=list(df_tipo["Tipo"]), title=None),
            y=alt.Y("Casos", title="Casos", axis=_int_y_axis(df_tipo["Casos"])),
            color=alt.Color(
                "Tipo", legend=None,
                scale=alt.Scale(domain=list(_TIPO_COLORS.keys()),
                                range=list(_TIPO_COLORS.values())),
            ),
            tooltip=["Tipo", "Casos"],
        )
    )
    st.altair_chart(chart_tipo, use_container_width=True)

    st.subheader("Por fecha")
    por_dia: dict[str, int] = {}
    for r in rows:
        d = r.get("day") or "—"
        por_dia[d] = por_dia.get(d, 0) + 1
    df_dia = pd.DataFrame(
        {"Día": list(por_dia.keys()), "Casos": list(por_dia.values())}
    ).sort_values("Día")
    chart_dia = (
        alt.Chart(df_dia)
        .mark_bar()
        .encode(
            x=alt.X("Día", title=None, sort=list(df_dia["Día"])),
            y=alt.Y("Casos", title="Casos", axis=_int_y_axis(df_dia["Casos"])),
            tooltip=["Día", "Casos"],
        )
    )
    st.altair_chart(chart_dia, use_container_width=True)

    st.subheader("Por canal")
    por_medio = {m: 0 for m in _MEDIO_ORDER}
    for r in rows:
        m = r.get("medio") or "texto"
        por_medio[m if m in por_medio else "texto"] += 1
    df_medio = pd.DataFrame({
        "Canal": [_MEDIO_LABELS[m] for m in _MEDIO_ORDER],
        "Casos": [por_medio[m] for m in _MEDIO_ORDER],
    })
    chart_medio = (
        alt.Chart(df_medio)
        .mark_bar()
        .encode(
            x=alt.X("Canal", sort=list(df_medio["Canal"]), title=None),
            y=alt.Y("Casos", title="Casos", axis=_int_y_axis(df_medio["Casos"])),
            color=alt.Color(
                "Canal", legend=None,
                scale=alt.Scale(domain=list(_MEDIO_COLORS.keys()),
                                range=list(_MEDIO_COLORS.values())),
            ),
            tooltip=["Canal", "Casos"],
        )
    )
    st.altair_chart(chart_medio, use_container_width=True)

    st.divider()

    # ------------------------ Consultas recurrentes -----------------------------
    st.subheader("👥 Usuarios con consultas recurrentes")
    solo_recurrentes = st.checkbox(
        "Mostrar solo usuarios con 2 o más atenciones en el periodo", value=True)
    df_usuarios = pd.DataFrame(
        {"Usuario": [_user_label(u) for u in por_usuario.keys()],
         "Atenciones": list(por_usuario.values())}
    ).sort_values("Atenciones", ascending=False)
    if solo_recurrentes:
        df_usuarios = df_usuarios[df_usuarios["Atenciones"] >= 2]
    if df_usuarios.empty:
        st.caption("Ningún usuario tiene consultas recurrentes en este periodo.")
    else:
        st.dataframe(df_usuarios, use_container_width=True, hide_index=True)

    st.divider()

    # -------------------------------- Listado -----------------------------------
    st.subheader("📋 Atenciones registradas")
    q = st.text_input("🔎 Filtrar (tipo, canal, resumen o mensaje)", "")
    ql = q.strip().lower()

    def _match(r: dict) -> bool:
        if not ql:
            return True
        blob = (f"{_tipo_for(r)} {_medio_label(r.get('medio', ''))} "
                f"{_resumen_for(r)} {r.get('message', '')}").lower()
        return ql in blob

    shown = [r for r in rows if _match(r)]
    shown_csv = [
        {"day": r.get("day", ""), "tipo": _TIPO_LABELS.get(_tipo_for(r), _CONSULTA_GENERAL),
         "medio": _medio_label(r.get("medio", "")),
         "usuario": _user_label(r.get("user_id", "")), "resumen": _resumen_for(r)}
        for r in shown
    ]
    cap_col, dl_col = st.columns([3, 1])
    cap_col.caption(f"{len(shown)} de {len(rows)} atención(es) en el periodo")
    dl_col.download_button(
        "⬇️ Exportar CSV",
        data=_attentions_to_csv(shown_csv),
        file_name=f"atenciones_{_dt.date.today():%Y%m%d}.csv",
        mime="text/csv",
        help="Descarga las atenciones mostradas (respeta el filtro) como CSV.",
        use_container_width=True,
    )

    for r in shown[:200]:  # tope razonable para no saturar la página
        tipo_lbl = _TIPO_LABELS.get(_tipo_for(r), _CONSULTA_GENERAL)
        medio_lbl = _medio_label(r.get("medio", ""))
        header = (f"{r.get('day', '—')} · {tipo_lbl} · {medio_lbl} — "
                 f"{_user_label(r.get('user_id', ''))}")
        with st.expander(header):
            st.write(f"**Tipo:** {tipo_lbl}")
            st.write(f"**Canal:** {medio_lbl}")
            st.write(f"**Resumen:** {_resumen_for(r) or '—'}")
            st.caption(f"Usuario: {_user_label(r.get('user_id', ''))} · "
                       f"Registrado: {_fmt_ts(r.get('created_at'))}")

st.divider()
st.caption("Datos personales tratados conforme a la Ley 29733 y GDPR: finalidad "
           "declarada (calidad de atención del asistente). Los identificadores de "
           "usuarios no registrados se muestran enmascarados.")
