"""Admin UI (Streamlit): carga de nuevos archivos/contenidos al corpus.

Cumple "Diseñar la interfaz para la carga de nuevos archivos o contenidos".
Sube documentos (PDF/DOCX/TXT) a GCS y dispara la ingesta (chunking + embeddings
-> Firestore) para que el conocimiento del chatbot se actualice sin redeploy.
Incluye carga múltiple y un listado de los documentos ya indexados (con borrado).

Ejecutar local:  streamlit run admin_ui/app.py
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta, timezone
from pathlib import Path

# Streamlit pone admin_ui/ en sys.path al ejecutar este script; como el archivo se
# llama app.py, tapaba al paquete 'app' del proyecto. Insertamos la raíz primero
# para que 'app.config' resuelva al paquete y no a este módulo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.config import settings

# st.set_page_config lo llama el host de navegación (admin_ui/app.py); aquí no.
st.title("📥 Ingesta de contenidos — Chatbot Arándano")
st.caption("Carga de documentos (PDF, DOCX, TXT) y URLs a la base de conocimiento (RAG).")

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


@st.cache_resource
def _gcs_client():
    from google.cloud import storage

    return storage.Client(project=settings.gcp_project_id)


def _upload_to_gcs(file_bytes: bytes, filename: str) -> str:
    # Sanitiza el nombre (evita path traversal vía "../" o rutas absolutas en el
    # nombre de archivo que llega del cliente antes de usarlo como blob name).
    safe_name = Path(filename).name
    client = _gcs_client()
    bucket = client.bucket(settings.gcs_corpus_bucket)
    ext = safe_name.rsplit(".", 1)[-1].lower()
    blob = bucket.blob(safe_name)
    blob.upload_from_string(file_bytes, content_type=_CONTENT_TYPES.get(ext, "application/octet-stream"))
    return f"gs://{settings.gcs_corpus_bucket}/{safe_name}"


def _ingest_blob(blob_name: str, replace: bool, allow_duplicates: bool = False) -> int:
    from argparse import Namespace

    from ingestion.ingest import run

    args = Namespace(
        source="gcs", folder=None, bucket=settings.gcs_corpus_bucket,
        prefix="", blob=blob_name, replace=replace,
        allow_duplicates=allow_duplicates, dry_run=False,
    )
    run(args)
    from app.firestore_store import FirestoreVectorStore

    return FirestoreVectorStore().count()


def _ingest_url(url: str, replace: bool, allow_duplicates: bool = False) -> int:
    from argparse import Namespace

    from ingestion.ingest import run

    args = Namespace(
        source="gcs", folder=None, bucket=settings.gcs_corpus_bucket,
        prefix="", blob=None, url=url, replace=replace,
        allow_duplicates=allow_duplicates, dry_run=False,
    )
    if run(args) != 0:
        raise RuntimeError("no se pudo extraer contenido (página vacía o inaccesible)")
    from app.firestore_store import FirestoreVectorStore

    return FirestoreVectorStore().count()


def _delete_blob(blob_name: str) -> None:
    """Borra un archivo de GCS (p. ej. tras detectar que su contenido es duplicado)."""
    try:
        _gcs_client().bucket(settings.gcs_corpus_bucket).blob(blob_name).delete()
    except Exception:  # noqa: BLE001
        pass


@st.cache_data(ttl=60, show_spinner=False)
def _list_sources() -> list[dict]:
    from app.firestore_store import FirestoreVectorStore

    return FirestoreVectorStore().list_sources()


def _notify_subscribers(sources: list[str]) -> None:
    """Envía por WhatsApp el resumen de cada documento nuevo a los suscritos.

    Idempotente: si el trigger automático (Eventarc sobre `kb_events`) ya difundió
    el documento, aquí se omite para no duplicar el mensaje.
    """
    from app.kb_broadcast import broadcast_source

    total_sent = 0
    for src in sources:
        try:
            res = broadcast_source(src)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"📣 No se pudo notificar «{src}»: {exc}")
            continue
        if res is None:
            st.info(f"📣 «{src}»: ya notificado automáticamente.")
            continue
        if res.skipped_reason:
            st.info(f"📣 «{src}»: sin envío ({res.skipped_reason}).")
            continue
        total_sent += res.sent
        msg = f"📣 «{src}»: {res.sent}/{res.recipients} usuario(s) notificado(s)."
        if res.failed:
            msg += f" {res.failed} fallo(s) (p. ej. no unidos al Sandbox)."
        st.info(msg)
    if total_sent:
        st.success(f"📣 Resumen enviado por WhatsApp a {total_sent} usuario(s) suscrito(s).")


def _delete_source(source: str) -> int:
    from app.firestore_store import FirestoreVectorStore

    removed = FirestoreVectorStore().delete_by_source(source)
    # Limpieza del archivo en GCS (si existe) para evitar re-ingesta en lote.
    try:
        _gcs_client().bucket(settings.gcs_corpus_bucket).blob(source).delete()
    except Exception:  # noqa: BLE001
        pass
    return removed


with st.expander("ℹ️ Estado del sistema", expanded=False):
    st.write(f"**Proyecto GCP:** {settings.gcp_project_id}")
    st.write(f"**Bucket corpus:** {settings.gcs_corpus_bucket}")
    st.write(f"**Colección vectorial:** {settings.firestore_vector_collection}")
    st.write(f"**Modelo embeddings:** {settings.embedding_model}")

# ----------------------------- Carga de documentos ----------------------------
st.subheader("Subir nuevos documentos")
uploaded = st.file_uploader(
    "Selecciona uno o varios archivos (PDF, DOCX, TXT)",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
)
replace = st.checkbox("Reemplazar si ya existe (re-ingesta)", value=True)
allow_dup = st.checkbox(
    "Permitir duplicados (omitir control por contenido)", value=False,
    help="Por defecto se rechaza un documento cuyo contenido ya esté indexado "
         "bajo otro nombre. Marca esto solo si quieres forzar la ingesta.",
)
notify_wa = st.checkbox(
    "📣 Notificar por WhatsApp a los usuarios suscritos al resumen", value=True,
    help="Al terminar, envía un resumen del contenido nuevo a los usuarios activos "
         "que optaron por recibir novedades (Registro de usuarios → casilla de resumen).",
)

if uploaded:
    from ingestion.ingest import DuplicateContentError
    from ingestion.validation import ValidationError

    st.write(f"**{len(uploaded)}** archivo(s) seleccionado(s):")
    for f in uploaded:
        st.write(f"- {f.name} ({f.size/1024:.0f} KB)")

    if st.button("📤 Subir e ingestar todos", type="primary"):
        ok, fail, dup, inv, total = 0, 0, 0, 0, 0
        ingested_sources: list[str] = []
        n_files = len(uploaded)
        bar = st.progress(0.0, text=f"Procesando 0/{n_files} (0%)…")
        with st.status("Procesando documentos...", expanded=True) as status:
            for idx, f in enumerate(uploaded, 1):
                bar.progress((idx - 1) / n_files,
                             text=f"Procesando {idx}/{n_files} "
                                  f"({int((idx - 1) / n_files * 100)}%) — {f.name}")
                try:
                    st.write(f"**{f.name}** — subiendo a Cloud Storage...")
                    uri = _upload_to_gcs(f.getvalue(), f.name)
                    st.write(f"`{uri}` — validando, generando chunks y embeddings...")
                    total = _ingest_blob(f.name, replace, allow_dup)
                    st.write(f"✅ {f.name} ingestado.")
                    ingested_sources.append(f.name)
                    ok += 1
                except ValidationError as exc:
                    # No pasó integridad/seguridad/PII: descartar el archivo subido.
                    _delete_blob(f.name)
                    st.write(f"🚫 {f.name}: rechazado por validación — {exc}")
                    inv += 1
                except DuplicateContentError as exc:
                    # El contenido ya existe bajo otra fuente: descartar el archivo
                    # redundante recién subido para no dejarlo huérfano en GCS.
                    _delete_blob(f.name)
                    st.write(f"⚠️ {f.name}: {exc}")
                    dup += 1
                except Exception as exc:  # noqa: BLE001
                    st.write(f"❌ {f.name}: {exc}")
                    fail += 1
                bar.progress(idx / n_files,
                             text=f"{idx}/{n_files} ({int(idx / n_files * 100)}%) procesados")
            bar.progress(1.0, text=f"Completado: {n_files}/{n_files} (100%)")
            state = "complete" if fail == 0 else "error"
            status.update(
                label=f"Listo: {ok} ok, {dup} duplicado(s), {inv} rechazado(s), {fail} con error",
                state=state)
        if ok:
            st.success(f"{ok} documento(s) ingestado(s). Total de chunks en el índice: {total}")
        if dup:
            st.warning(f"{dup} documento(s) omitido(s) por contenido duplicado.")
        if inv:
            st.warning(f"{inv} documento(s) rechazado(s) por validación de integridad/seguridad.")
        if fail:
            st.warning(f"{fail} documento(s) fallaron. Revisa el detalle arriba.")
        if notify_wa and ingested_sources:
            _notify_subscribers(ingested_sources)
        _list_sources.clear()  # refrescar el listado

st.divider()

# ----------------------- Páginas web preseleccionadas -------------------------
st.subheader("🌐 Agregar páginas web (preseleccionadas)")
st.caption("Scraping de URLs que elijas (exportación, SENASA, costos, mercados…). "
           "Cada URL se indexa y aparece abajo como una fuente más.")
urls_text = st.text_area(
    "Pega una o varias URLs (una por línea)",
    placeholder="https://www.senasa.gob.pe/...\nhttps://www.gob.pe/...",
    height=110,
)
replace_urls = st.checkbox("Reemplazar si ya existe (re-ingesta)", value=True, key="replace_urls")
allow_dup_urls = st.checkbox(
    "Permitir duplicados (omitir control por contenido)", value=False, key="allow_dup_urls",
    help="Rechaza una URL cuyo contenido ya esté indexado bajo otra fuente.",
)
notify_wa_urls = st.checkbox(
    "📣 Notificar por WhatsApp a los usuarios suscritos al resumen", value=True,
    key="notify_wa_urls",
    help="Al terminar, envía un resumen de cada página nueva a los usuarios suscritos.",
)

if st.button("🌐 Ingestar URLs"):
    from ingestion.ingest import DuplicateContentError
    from ingestion.validation import ValidationError

    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
    if not urls:
        st.warning("No ingresaste ninguna URL.")
    else:
        ok, fail, dup, inv, total = 0, 0, 0, 0, 0
        ingested_urls: list[str] = []
        n_urls = len(urls)
        bar = st.progress(0.0, text=f"Procesando 0/{n_urls} (0%)…")
        with st.status("Procesando páginas web...", expanded=True) as status:
            for idx, u in enumerate(urls, 1):
                bar.progress((idx - 1) / n_urls,
                             text=f"Procesando {idx}/{n_urls} "
                                  f"({int((idx - 1) / n_urls * 100)}%) — {u}")
                try:
                    st.write(f"**{u}** — descargando y extrayendo texto...")
                    total = _ingest_url(u, replace_urls, allow_dup_urls)
                    st.write(f"✅ {u} ingestada.")
                    ingested_urls.append(u)
                    ok += 1
                except ValidationError as exc:
                    st.write(f"🚫 {u}: rechazada por validación — {exc}")
                    inv += 1
                except DuplicateContentError as exc:
                    st.write(f"⚠️ {u}: {exc}")
                    dup += 1
                except Exception as exc:  # noqa: BLE001
                    st.write(f"❌ {u}: {exc}")
                    fail += 1
                bar.progress(idx / n_urls,
                             text=f"{idx}/{n_urls} ({int(idx / n_urls * 100)}%) procesadas")
            bar.progress(1.0, text=f"Completado: {n_urls}/{n_urls} (100%)")
            state = "complete" if fail == 0 else "error"
            status.update(
                label=f"Listo: {ok} ok, {dup} duplicado(s), {inv} rechazada(s), {fail} con error",
                state=state)
        if ok:
            st.success(f"{ok} página(s) ingestada(s). Total de chunks en el índice: {total}")
        if dup:
            st.warning(f"{dup} URL(s) omitida(s) por contenido duplicado.")
        if inv:
            st.warning(f"{inv} URL(s) rechazada(s) por validación (p. ej. PII en modo bloqueo).")
        if fail:
            st.warning(f"{fail} URL(s) fallaron (sin texto extraíble o error de red).")
        if notify_wa_urls and ingested_urls:
            _notify_subscribers(ingested_urls)
        _list_sources.clear()

st.divider()

# -------------------- Listado de contenido (archivos y URLs) ------------------
st.subheader("📚 Contenido en la base de conocimiento")
col_a, col_b = st.columns([3, 1])
with col_b:
    if st.button("🔄 Actualizar"):
        _list_sources.clear()

try:
    sources = _list_sources()
except Exception as exc:  # noqa: BLE001
    sources = []
    st.error(f"No se pudo listar el índice: {exc}")


def _is_url(src: str) -> bool:
    return src.startswith("http://") or src.startswith("https://")


def _fmt_ts(ts) -> str:
    """Formatea el timestamp de procesamiento (updated_at) de Firestore."""
    if not ts:
        return "—"
    try:
        local = ts.astimezone(timezone.utc) + timedelta(
            hours=settings.lima_utc_offset_hours)
        return local.strftime("%Y-%m-%d %I:%M %p (Perú)")
    except Exception:  # noqa: BLE001
        return str(ts)


def _sort_ts(s) -> float:
    """Clave de orden cronológico por fecha de procesamiento (updated_at).

    Devuelve el epoch en segundos; las fuentes sin fecha quedan al final.
    """
    try:
        return s.get("updated_at").timestamp()
    except Exception:  # noqa: BLE001
        return float("-inf")


def _render_group(items, label):
    head = st.columns([6, 1, 1])
    head[0].markdown(f"**{label}**")
    head[1].markdown("**Chunks**")
    head[2].markdown("**Acción**")
    for s in items:
        c = st.columns([6, 1, 1])
        if _is_url(s["source"]):
            c[0].markdown(f"[{s['source']}]({s['source']})")
        else:
            c[0].write(s["source"])
        c[1].write(str(s["chunks"]))
        if c[2].button("🗑️", key=f"del_{s['source']}", help=f"Eliminar {s['source']}"):
            removed = _delete_source(s["source"])
            _list_sources.clear()
            st.success(f"Eliminado «{s['source']}» ({removed} chunks).")
            st.rerun()
        # Metadatos: fecha de procesamiento + hash completo del contenido (SHA-256).
        st.caption(f"📅 Procesado: {_fmt_ts(s.get('updated_at'))}")
        chash = s.get("content_hash")
        if chash:
            st.caption("🔑 Hash de contenido (SHA-256) — clic para copiar:")
            st.code(chash, language=None)
        else:
            st.caption("🔑 Hash: — (ingestado antes del control de duplicados; reingesta para generarlo)")
        st.divider()


if not sources:
    st.info("Aún no hay contenido indexado.")
else:
    # Orden cronológico descendente: del más reciente al más antiguo.
    docs = sorted((s for s in sources if not _is_url(s["source"])),
                  key=_sort_ts, reverse=True)
    webs = sorted((s for s in sources if _is_url(s["source"])),
                  key=_sort_ts, reverse=True)
    total_chunks = sum(s["chunks"] for s in sources)
    st.caption(f"{len(docs)} documento(s) · {len(webs)} página(s) web · {total_chunks} chunks en total")

    st.markdown("#### 📄 Documentos (archivos)")
    if docs:
        _render_group(docs, "Documento")
    else:
        st.info("Sin archivos indexados.")

    st.markdown("#### 🌐 Páginas web (URLs)")
    if webs:
        _render_group(webs, "URL")
    else:
        st.info("Sin páginas web indexadas.")

st.divider()
st.caption("Datos tratados conforme a la Ley 29733 y GDPR. Sólo documentos "
           "corporativos del dominio del arándano.")
