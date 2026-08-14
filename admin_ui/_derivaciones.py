"""Admin UI (Streamlit): estadísticas de las derivaciones a entidades públicas.

Cada vez que el agente canaliza el caso de un ciudadano a una entidad pública
(`app.derivation.send_derivation`, invocado por la tool `derivar_solicitud_entidad`),
queda un registro en Firestore (colección `derivations`, un documento por entidad de
cada caso — ver `app.derivation.DerivationStore`). Esta página lee esos registros y
muestra, para las atenciones a ciudadanos: cuántas derivaciones se hicieron, a qué
entidades, con qué nivel de urgencia, con qué éxito de envío y por qué CANAL llegó
la solicitud (texto/voz/imagen, ver `app.agent.turn_context`) — sin ese campo, una
derivación originada en una nota de voz era indistinguible de una escrita, incluso
en el correo enviado a la entidad.

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

from app.concerns import lima_day_str
from app.config import settings
from app.derivation import DerivationStore
from app.entity_catalog import ENTITY_CATALOG, URGENCY_LEVELS

# st.set_page_config lo llama el host de navegación (admin_ui/app.py); aquí no.
st.title("📊 Estadísticas de Derivaciones")
st.caption("Casos de ciudadanos canalizados a entidades públicas: volumen, entidad "
           "de destino, urgencia y éxito de envío.")

_URGENCY_LABELS = {"baja": "Baja", "media": "Media", "alta": "Alta", "critica": "Crítica"}
# De más a menos urgente: orden de lectura más natural para el gráfico que el
# orden alfabético/interno de URGENCY_LEVELS (usado para clasificación, no display).
_URGENCY_ORDER = ("critica", "alta", "media", "baja")
_URGENCY_COLORS = {"Crítica": "#c53030", "Alta": "#dd6b20",
                   "Media": "#d69e2e", "Baja": "#38a169"}

# Nombres de despliegue más cortos para el gráfico "Por entidad" (el catálogo
# completo de app.entity_catalog usa nombres largos con "/" o paréntesis,
# necesarios para el clasificador y los correos, pero poco legibles como
# etiqueta de barra con las 10 entidades a la vez). Solo afecta ESTE gráfico:
# el listado detallado y el CSV siguen usando el nombre oficial del catálogo.
_ENTITY_DISPLAY_NAMES = {
    "CITEagroindustrial Chavimochic": "CITEagro Chavimochic",
    "MIDAGRI / AGRO RURAL": "MIDAGRI",
    "RedCITE (ITP - PRODUCE)": "RedCITE - ITP",
    "SENAMHI / ENFEN": "SENAMHI",
}


def _display_entity(nombre: str) -> str:
    return _ENTITY_DISPLAY_NAMES.get(nombre, nombre)


# Medio de ENTRADA real del turno que originó la derivación (ver
# app.agent.turn_context): la nota de voz y la imagen llegan al agente ya
# convertidas a texto plano (transcripción/descripción), así que sin este
# campo su origen real se perdía por completo, incluso en el correo a la
# entidad (ver el aviso "Origen" que agrega `app.derivation._render`).
_MEDIO_LABELS = {"texto": "💬 Texto", "voz": "🎙️ Voz", "imagen": "📷 Imagen"}
_MEDIO_ORDER = ("texto", "voz", "imagen")
_MEDIO_COLORS = {"💬 Texto": "#2b6cb0", "🎙️ Voz": "#dd6b20", "📷 Imagen": "#38a169"}


def _medio_label(medio: str) -> str:
    return _MEDIO_LABELS.get(medio or "texto", _MEDIO_LABELS["texto"])


def _int_y_axis(series) -> alt.Axis:
    """Eje Y de conteo entero SIN ticks repetidos.

    tickMinStep=1 solo sugiere un mínimo: Vega-Lite igual puede elegir ticks
    intermedios fraccionarios (p. ej. 0, 0.67, 1.33, 2) que al redondear con
    format="d" se muestran como enteros duplicados ("0, 1, 1, 2"). Fijar
    `values` explícitos (0..máximo real de la serie) elimina la ambigüedad:
    Vega-Lite ya no "adivina" posiciones, solo dibuja las que le pasamos."""
    top = int(series.max()) if len(series) else 0
    return alt.Axis(format="d", values=list(range(0, top + 1)))


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
def _store() -> DerivationStore:
    return DerivationStore()


@st.cache_data(ttl=30, show_spinner=False)
def _list_derivations() -> list[dict]:
    return _store().list_recent()


def _fmt_ts(ts) -> str:
    if not isinstance(ts, _dt.datetime):
        return "—"
    try:
        local = ts.astimezone(_dt.timezone.utc) + _dt.timedelta(
            hours=settings.lima_utc_offset_hours)
        return local.strftime("%Y-%m-%d %I:%M %p (Perú)")
    except Exception:  # noqa: BLE001
        return str(ts)


_PERIODOS = {"Últimos 7 días": 7, "Últimos 30 días": 30, "Últimos 90 días": 90, "Todo": None}

_CSV_COLUMNS = [
    ("day", "Fecha"), ("entidad", "Entidad"), ("urgencia", "Urgencia"),
    ("medio", "Canal"), ("ok", "Enviada"), ("directo", "Directo a la entidad"),
    ("nombre", "Nombre"), ("whatsapp", "WhatsApp"), ("email", "Correo"),
    ("resumen", "Resumen del caso"),
]


def _csv_cell(r: dict, key: str) -> str:
    if key in ("ok", "directo"):
        return "Sí" if r.get(key) else "No"
    if key == "medio":
        return _medio_label(r.get(key, ""))
    return str(r.get(key, "") or "")


def _derivations_to_csv(rows: list[dict]) -> bytes:
    """Serializa derivaciones a CSV (UTF-8 con BOM para abrir bien en Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in _CSV_COLUMNS])
    for r in rows:
        writer.writerow([_csv_cell(r, key) for key, _ in _CSV_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")


with st.expander("ℹ️ Estado del sistema", expanded=False):
    st.write(f"**Proyecto GCP:** {settings.gcp_project_id}")
    st.write(f"**Colección de derivaciones:** {settings.firestore_derivations_collection}")

col_a, col_b = st.columns([3, 1])
with col_a:
    periodo = st.selectbox("Periodo", list(_PERIODOS.keys()), index=1)
with col_b:
    st.write("")  # alinea el botón con el selectbox
    if st.button("🔄 Actualizar"):
        _list_derivations.clear()

try:
    all_rows = _list_derivations()
except Exception as exc:  # noqa: BLE001
    all_rows = []
    _show_gcp_error(exc, context="No se pudo leer las derivaciones")

dias = _PERIODOS[periodo]
if dias is None:
    rows = all_rows
else:
    cutoff = lima_day_str(_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=dias))
    rows = [r for r in all_rows if str(r.get("day", "")) >= cutoff]

if not all_rows:
    st.info("Aún no hay derivaciones registradas.")
elif not rows:
    st.info(f"No hay derivaciones en el periodo «{periodo}».")
else:
    # ------------------------------ Métricas ----------------------------------
    total = len(rows)
    enviadas_ok = sum(1 for r in rows if r.get("ok"))
    urgentes = sum(1 for r in rows if r.get("urgencia") in ("alta", "critica"))
    entidades_distintas = len({r.get("entidad", "") for r in rows if r.get("entidad")})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Derivaciones", total)
    m2.metric("Enviadas con éxito", enviadas_ok,
              delta=f"{enviadas_ok / total:.0%} del total" if total else None)
    m3.metric("Casos urgentes", urgentes, help="Urgencia alta o crítica")
    m4.metric("Entidades distintas", entidades_distintas)

    st.divider()

    # --------------------------- Por entidad / urgencia ------------------------
    # Apiladas (no en columnas lado a lado): con las 10 entidades del catálogo,
    # el gráfico "Por entidad" necesita el ancho completo para que las etiquetas
    # se lean bien, así que va en su propia fila y "Por urgencia" queda debajo.
    st.subheader("Por entidad")
    # Arranca con las 10 entidades del catálogo cerrado en 0 (no solo las que
    # ya tuvieron algún caso), para que el gráfico muestre siempre el panorama
    # completo. Si algún registro trae un nombre fuera del catálogo (fallback
    # a la propuesta del LLM cuando `identificar_entidades` falla), se agrega
    # igual: no se pierde información real.
    por_entidad: dict[str, int] = {_display_entity(e.nombre): 0 for e in ENTITY_CATALOG}
    for r in rows:
        ent = _display_entity(r.get("entidad") or "—")
        por_entidad[ent] = por_entidad.get(ent, 0) + 1
    df_entidad = pd.DataFrame(
        {"Entidad": list(por_entidad.keys()), "Casos": list(por_entidad.values())}
    ).sort_values("Casos", ascending=False)
    chart_entidad = (
        alt.Chart(df_entidad)
        .mark_bar()
        .encode(
            x=alt.X("Entidad", sort="-y", title=None,
                    # Vega-Lite trunca labels más largos que labelLimit (~100px
                    # por defecto) con "…"; OJO: labelLimit=0 NO significa "sin
                    # límite", trunca a 0px (oculta el label). labelOverlap=False
                    # fuerza a dibujar las 10 aunque el ancho ajuste (por defecto
                    # Vega-Lite oculta labels alternos si detecta superposición).
                    axis=alt.Axis(labelAngle=-60, labelLimit=300, labelOverlap=False)),
            y=alt.Y("Casos", title="Casos", axis=_int_y_axis(df_entidad["Casos"])),
            color=alt.Color("Entidad", legend=None, scale=alt.Scale(scheme="tableau10")),
            tooltip=["Entidad", "Casos"],
        )
        .properties(height=430)
    )
    st.altair_chart(chart_entidad, use_container_width=True)

    st.subheader("Por urgencia")
    por_urgencia = {u: 0 for u in URGENCY_LEVELS}
    for r in rows:
        u = r.get("urgencia") or "media"
        por_urgencia[u] = por_urgencia.get(u, 0) + 1
    df_urg = pd.DataFrame({
        "Urgencia": [_URGENCY_LABELS.get(u, u) for u in _URGENCY_ORDER],
        "Casos": [por_urgencia[u] for u in _URGENCY_ORDER],
    })
    chart_urg = (
        alt.Chart(df_urg)
        .mark_bar()
        .encode(
            x=alt.X("Urgencia", sort=list(df_urg["Urgencia"]), title=None),
            y=alt.Y("Casos", title="Casos", axis=_int_y_axis(df_urg["Casos"])),
            color=alt.Color(
                "Urgencia", legend=None,
                scale=alt.Scale(domain=list(_URGENCY_COLORS.keys()),
                                range=list(_URGENCY_COLORS.values())),
            ),
            tooltip=["Urgencia", "Casos"],
        )
    )
    st.altair_chart(chart_urg, use_container_width=True)

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

    # ------------------------------ Serie temporal ------------------------------
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

    st.divider()

    # -------------------------------- Listado -----------------------------------
    st.subheader("📋 Casos derivados")
    q = st.text_input("🔎 Filtrar (entidad, canal, nombre, WhatsApp, correo o resumen)", "")
    ql = q.strip().lower()

    def _match(r: dict) -> bool:
        if not ql:
            return True
        blob = " ".join(str(r.get(k, "")) for k in
                        ("entidad", "nombre", "whatsapp", "email", "resumen")).lower()
        blob = f"{blob} {_medio_label(r.get('medio', '')).lower()}"
        return ql in blob

    shown = [r for r in rows if _match(r)]
    cap_col, dl_col = st.columns([3, 1])
    cap_col.caption(f"{len(shown)} de {len(rows)} derivación(es) en el periodo")
    dl_col.download_button(
        "⬇️ Exportar CSV",
        data=_derivations_to_csv(shown),
        file_name=f"derivaciones_{_dt.date.today():%Y%m%d}.csv",
        mime="text/csv",
        help="Descarga las derivaciones mostradas (respeta el filtro) como CSV.",
        use_container_width=True,
    )

    for r in shown[:200]:  # tope razonable para no saturar la página
        estado = "✅ Enviada" if r.get("ok") else "❌ Falló el envío"
        urgencia_lbl = _URGENCY_LABELS.get(r.get("urgencia", ""), r.get("urgencia", "—"))
        medio_lbl = _medio_label(r.get("medio", ""))
        header = (f"{r.get('day', '—')} · {r.get('entidad', '—')} — {urgencia_lbl} · "
                 f"{medio_lbl} · {estado}")
        with st.expander(header):
            st.write(f"**Entidad:** {r.get('entidad', '—')}")
            st.write(f"**Canal de origen:** {medio_lbl}")
            st.write(f"**Resumen del caso:** {r.get('resumen') or '—'}")
            contacto = " · ".join(p for p in [
                r.get("nombre") and f"Nombre: {r['nombre']}",
                r.get("whatsapp") and f"WhatsApp: {r['whatsapp']}",
                r.get("email") and f"Correo: {r['email']}",
            ] if p) or "No disponible"
            st.write(f"**Contacto del ciudadano:** {contacto}")
            ruteo = "Directo a la entidad" if r.get("directo") else "Ruteo manual (admin)"
            st.caption(f"Destino del correo: {r.get('destino', '—')} ({ruteo}) · "
                       f"Registrado: {_fmt_ts(r.get('created_at'))}")

st.divider()
st.caption("Datos personales tratados conforme a la Ley 29733 y GDPR: finalidad "
           "declarada (canalización del caso a la entidad pública pertinente).")
