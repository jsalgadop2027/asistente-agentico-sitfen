"""Admin UI (Streamlit): registro y control de usuarios por WhatsApp.

Interfaz de control de registros de usuarios finales del chatbot. Permite:
  - Dar de alta un usuario (nombre, apellido, dirección, rubro económico,
    WhatsApp y correo). El sistema genera un CÓDIGO INTERNO de 8 caracteres.
  - Listar, editar, activar/desactivar y eliminar usuarios.

El código interno controla cada sesión individual de WhatsApp: el webhook lo usa
como identificador de sesión/memoria en lugar del número de teléfono.

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

import streamlit as st

from app.config import settings
from app.user_registry import (
    ECONOMIC_SECTORS,
    UserRegistryError,
    get_user_registry,
)

# st.set_page_config lo llama el host de navegación (admin_ui/app.py); aquí no.
st.title("👤 Control de Usuarios")
st.caption("Registro y control de usuarios finales y de su sesión de WhatsApp "
           "mediante un código interno de 8 caracteres.")


def _is_credentials_error(exc: Exception) -> bool:
    """True si el fallo se debe a credenciales de GCP ausentes/ inválidas (ADC)."""
    try:
        from google.auth.exceptions import DefaultCredentialsError

        if isinstance(exc, DefaultCredentialsError):
            return True
    except Exception:  # noqa: BLE001
        pass
    msg = str(exc).lower()
    return ("default credentials were not found" in msg
            or "could not automatically determine credentials" in msg)


def _purge_user_memory(code: str, whatsapp: str) -> int:
    """Borra toda la memoria del usuario (derecho de supresión, Ley 29733/GDPR).

    Cubre las dos capas y las dos claves de sesión posibles: el código interno
    (usado tras registrarse) y el token pseudonimizado del teléfono (usado si
    conversó antes de registrarse). Fail-open: no interrumpe la baja del usuario.
    """
    keys = [code]
    try:
        from app.agent.guardrails import pseudonymize
        from app.user_registry import normalize_whatsapp

        keys.append(pseudonymize(normalize_whatsapp(whatsapp)))
    except Exception:  # noqa: BLE001
        pass

    removed = 0
    for key in filter(None, keys):
        try:
            from app.agent.memory import ConversationMemory

            ConversationMemory().forget(key)
        except Exception:  # noqa: BLE001
            pass
        try:
            from app.agent.semantic_memory import SemanticMemory

            removed += SemanticMemory().forget(key)
        except Exception:  # noqa: BLE001
            pass
    return removed


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
def _registry():
    return get_user_registry()


@st.cache_data(ttl=30, show_spinner=False)
def _list_users() -> list[dict]:
    # Se devuelven dicts (serializables por el cache de Streamlit).
    from dataclasses import asdict

    return [asdict(u) for u in _registry().list_users()]


def _fmt_ts(ts) -> str:
    if not ts:
        return "—"
    try:
        local = ts.astimezone(_dt.timezone.utc) + _dt.timedelta(
            hours=settings.lima_utc_offset_hours)
        return local.strftime("%Y-%m-%d %I:%M %p (Perú)")
    except Exception:  # noqa: BLE001
        return str(ts)


_CSV_COLUMNS = [
    ("code", "Código"), ("nombre", "Nombre"), ("apellido", "Apellido"),
    ("direccion", "Dirección"), ("rubro", "Rubro"), ("whatsapp", "WhatsApp"),
    ("email", "Correo"), ("active", "Activo"), ("send_kb_summary", "Resumen novedades"),
    ("created_at", "Alta"), ("last_seen_at", "Últ. actividad WhatsApp"),
]


def _csv_cell(u: dict, key: str) -> str:
    if key == "active":
        return "Sí" if u.get(key, True) else "No"
    if key == "send_kb_summary":
        return "Sí" if u.get(key, True) else "No"
    if key in ("created_at", "last_seen_at"):
        return _fmt_ts(u.get(key))
    return str(u.get(key, "") or "")


def _users_to_csv(rows: list[dict]) -> bytes:
    """Serializa usuarios a CSV (UTF-8 con BOM para abrir bien en Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in _CSV_COLUMNS])
    for u in rows:
        writer.writerow([_csv_cell(u, key) for key, _ in _CSV_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")


with st.expander("ℹ️ Estado del sistema", expanded=False):
    st.write(f"**Proyecto GCP:** {settings.gcp_project_id}")
    st.write(f"**Colección de usuarios:** {settings.firestore_users_collection}")

# --------------------------------- Alta --------------------------------------
st.subheader("➕ Registrar nuevo usuario")
with st.form("alta_usuario", clear_on_submit=True):
    col1, col2 = st.columns(2)
    nombre = col1.text_input("Nombre *")
    apellido = col2.text_input("Apellido *")
    direccion = st.text_input("Dirección")
    rubro = st.selectbox("Rubro económico *", ECONOMIC_SECTORS, index=0)
    col3, col4 = st.columns(2)
    whatsapp = col3.text_input("WhatsApp *", placeholder="+51987654321 o 987654321")
    email = col4.text_input("Correo electrónico *", placeholder="usuario@empresa.pe")
    send_kb_summary = st.checkbox(
        "Enviar resumen automático del contenido nuevo ingestado",
        value=True,
        help="Si se marca, el usuario recibirá por WhatsApp un resumen cuando se "
             "cargue e indexe contenido nuevo en la base de conocimiento.",
    )
    submitted = st.form_submit_button("Registrar", type="primary")

if submitted:
    try:
        user = _registry().create(
            nombre=nombre, apellido=apellido, direccion=direccion,
            rubro=rubro, whatsapp=whatsapp, email=email,
            send_kb_summary=send_kb_summary,
        )
        _list_users.clear()
        st.success(f"Usuario **{user.full_name}** registrado.")
        st.info(f"🔑 Código interno de sesión: **{user.code}**")
    except UserRegistryError as exc:
        st.error(f"No se pudo registrar: {exc}")
    except Exception as exc:  # noqa: BLE001
        _show_gcp_error(exc, context="No se pudo registrar")

st.divider()

# ------------------------------- Listado -------------------------------------
st.subheader("📋 Usuarios registrados")
col_a, col_b = st.columns([3, 1])
with col_b:
    if st.button("🔄 Actualizar"):
        _list_users.clear()

try:
    users = _list_users()
except Exception as exc:  # noqa: BLE001
    users = []
    _show_gcp_error(exc, context="No se pudo listar el registro")

if not users:
    st.info("Aún no hay usuarios registrados.")
else:
    q = st.text_input("🔎 Filtrar (nombre, código, WhatsApp, rubro o correo)", "")
    ql = q.strip().lower()

    def _match(u: dict) -> bool:
        if not ql:
            return True
        blob = " ".join(str(u.get(k, "")) for k in
                        ("code", "nombre", "apellido", "whatsapp", "email", "rubro")).lower()
        return ql in blob

    shown = [u for u in users if _match(u)]
    cap_col, dl_col = st.columns([3, 1])
    cap_col.caption(f"{len(shown)} de {len(users)} usuario(s)")
    dl_col.download_button(
        "⬇️ Exportar CSV",
        data=_users_to_csv(shown),
        file_name=f"usuarios_{_dt.date.today():%Y%m%d}.csv",
        mime="text/csv",
        help="Descarga los usuarios mostrados (respeta el filtro) como CSV.",
        use_container_width=True,
    )

    for u in shown:
        estado = "🟢 Activo" if u.get("active", True) else "🔴 Inactivo"
        header = f"{u['code']} · {u['nombre']} {u['apellido']} — {u['rubro']} · {estado}"
        with st.expander(header):
            st.write(f"**Código interno (sesión):** `{u['code']}`")
            st.write(f"**WhatsApp:** {u['whatsapp']}")
            st.write(f"**Correo:** {u['email']}")
            st.write(f"**Dirección:** {u.get('direccion') or '—'}")
            kb_txt = "Sí ✅" if u.get("send_kb_summary", True) else "No ❌"
            st.write(f"**Resumen de contenido nuevo:** {kb_txt}")
            st.caption(f"Alta: {_fmt_ts(u.get('created_at'))} · "
                       f"Últ. actividad WhatsApp: {_fmt_ts(u.get('last_seen_at'))}")

            st.markdown("**Editar**")
            with st.form(f"edit_{u['code']}"):
                e1, e2 = st.columns(2)
                n_nombre = e1.text_input("Nombre", u["nombre"], key=f"n_{u['code']}")
                n_apellido = e2.text_input("Apellido", u["apellido"], key=f"a_{u['code']}")
                n_dir = st.text_input("Dirección", u.get("direccion", ""), key=f"d_{u['code']}")
                n_rubro = st.selectbox(
                    "Rubro económico", ECONOMIC_SECTORS,
                    index=ECONOMIC_SECTORS.index(u["rubro"]) if u["rubro"] in ECONOMIC_SECTORS else 0,
                    key=f"r_{u['code']}")
                e3, e4 = st.columns(2)
                n_wa = e3.text_input("WhatsApp", u["whatsapp"], key=f"w_{u['code']}")
                n_email = e4.text_input("Correo", u["email"], key=f"e_{u['code']}")
                n_active = st.checkbox("Sesión activa", value=bool(u.get("active", True)),
                                       key=f"act_{u['code']}")
                n_kb = st.checkbox(
                    "Enviar resumen automático del contenido nuevo ingestado",
                    value=bool(u.get("send_kb_summary", True)), key=f"kb_{u['code']}")
                if st.form_submit_button("💾 Guardar cambios"):
                    try:
                        _registry().update(
                            u["code"], nombre=n_nombre, apellido=n_apellido,
                            direccion=n_dir, rubro=n_rubro, whatsapp=n_wa,
                            email=n_email, active=n_active, send_kb_summary=n_kb,
                        )
                        _list_users.clear()
                        st.success("Cambios guardados.")
                        st.rerun()
                    except UserRegistryError as exc:
                        st.error(f"No se pudo actualizar: {exc}")

            if st.button("🗑️ Eliminar usuario", key=f"del_{u['code']}",
                         help="Baja definitiva + borrado de su memoria (derecho de supresión)"):
                _registry().delete(u["code"])
                mem_removed = _purge_user_memory(u["code"], u.get("whatsapp", ""))
                _list_users.clear()
                st.warning(f"Usuario {u['code']} eliminado, junto con su memoria "
                           f"conversacional ({mem_removed} recuerdo(s) semántico(s)).")
                st.rerun()

st.divider()
st.caption("Datos personales tratados conforme a la Ley 29733 y GDPR: finalidad "
           "declarada (operación del asistente) y derecho de supresión disponible.")
