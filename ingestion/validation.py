"""Validaciones de integridad y seguridad PREVIAS a la vectorización.

Capa de calidad/seguridad que se ejecuta antes de generar embeddings:

  1) Integridad / formato (`validate_file`):
       - tamaño (no vacío, bajo el límite configurado),
       - MIME real por magic-bytes vs. extensión (detecta archivos renombrados
         o corruptos),
       - estructura abrible (PDF con páginas; DOCX con word/document.xml).
  2) Antivirus (`_scan_malware`, dentro de `validate_file`):
       - firma de prueba EICAR (siempre),
       - ClamAV si `settings.clamav_host` está configurado.
  3) PII (`apply_pii_policy`): sobre el texto ya extraído, con política
       configurable (redactar / bloquear / avisar), reutilizando el redactor
       de `app.agent.guardrails`.

Todas las fallas duras lanzan `ValidationError`, que la Admin UI y la ingesta
capturan para informar y NO indexar el documento.
"""
from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

from app.config import settings

logger = logging.getLogger("ingest.validation")

# EICAR: cadena estándar para PROBAR antivirus (NO es malware real).
_EICAR = (b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-"
          b"STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")

# Magic-bytes esperados por extensión.
_MAGIC = {
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04",),  # contenedor zip de OOXML
}
_TXT_EXT = ".txt"

# Tokens de contenido ACTIVO/armado en PDF (auto-ejecución y exfiltración).
_PDF_ACTIVE_TOKENS = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile")


def _find_pdf_active_content(raw: bytes) -> list[str]:
    """Busca contenido activo real inspeccionando la estructura de objetos del
    PDF (vía pypdf, que descomprime object streams /ObjStm) en vez de grep
    sobre bytes crudos. Un grep crudo hace falsos positivos masivos en PDFs
    escaneados: el token "/JS" aparece por coincidencia casual dentro de datos
    binarios comprimidos (imágenes JBIG2/JPEG) sin ser una clave PDF real. El
    parseo estructural evita eso y, a la vez, sigue detectando contenido activo
    aunque esté comprimido dentro de un ObjStm (que un simple recorte de
    bloques stream/endstream no vería).
    """
    from pypdf import PdfReader

    found: set[str] = set()
    try:
        reader = PdfReader(io.BytesIO(raw))
        root = reader.trailer.get("/Root")
        root = root.get_object() if root is not None else None
        if root is not None:
            if "/OpenAction" in root:
                found.add("/OpenAction")
            names = root.get("/Names")
            names = names.get_object() if names is not None else None
            if names is not None:
                if "/JavaScript" in names:
                    found.add("/JavaScript")
                if "/EmbeddedFiles" in names:
                    found.add("/EmbeddedFile")
        for page in reader.pages:
            if "/AA" in page:
                found.add("/JS")
            for ref in page.get("/Annots") or []:
                try:
                    annot = ref.get_object()
                except Exception:  # noqa: BLE001
                    continue
                if "/AA" in annot:
                    found.add("/JS")
                action = annot.get("/A")
                action = action.get_object() if action is not None else None
                if action is not None and action.get("/S") in ("/JavaScript", "/Launch"):
                    found.add(str(action.get("/S")))
    except Exception as exc:  # noqa: BLE001
        # No se pudo parsear la estructura (raro: _check_structure ya validó
        # que el PDF abre) — cae al escaneo textual simple sobre bytes crudos
        # para no perder cobertura de seguridad.
        logger.warning("No se pudo inspeccionar estructura PDF (%s), usando escaneo textual", exc)
        return [t.decode() for t in _PDF_ACTIVE_TOKENS if t in raw]
    return sorted(found)


class ValidationError(Exception):
    """El documento no pasó una validación de integridad/seguridad."""


def _check_size(raw: bytes) -> None:
    if len(raw) == 0:
        raise ValidationError("archivo vacío (0 bytes)")
    limit = settings.ingestion_max_bytes
    if limit and len(raw) > limit:
        raise ValidationError(
            f"excede el tamaño máximo permitido "
            f"({len(raw) / 1048576:.1f} MB > {limit / 1048576:.0f} MB)")


def _check_mime(name: str, raw: bytes) -> None:
    ext = Path(name).suffix.lower()
    if ext == _TXT_EXT:
        for enc in ("utf-8", "latin-1"):
            try:
                raw.decode(enc)
                return
            except UnicodeDecodeError:
                continue
        raise ValidationError("el .txt no es texto válido (utf-8/latin-1)")
    magics = _MAGIC.get(ext)
    if not magics:
        raise ValidationError(f"extensión no soportada: {ext or '(sin extensión)'}")
    if not any(raw.startswith(m) for m in magics):
        raise ValidationError(
            f"el contenido no corresponde a {ext}: magic-bytes no coinciden "
            "(archivo renombrado o corrupto)")


def _check_structure(name: str, raw: bytes) -> None:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            n = len(reader.pages)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"PDF corrupto o ilegible: {exc}")
        if n == 0:
            raise ValidationError("PDF sin páginas")
    elif ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"DOCX corrupto (zip ilegible): {exc}")
        if "word/document.xml" not in names:
            raise ValidationError("DOCX inválido (falta word/document.xml)")


def _scan_malware(name: str, raw: bytes) -> None:
    # 1) Firma de prueba EICAR — siempre.
    if _EICAR in raw:
        raise ValidationError("malware detectado: firma de prueba EICAR")
    # 2) ClamAV — sólo si está configurado.
    host = getattr(settings, "clamav_host", None)
    if host:
        try:
            import clamd

            cd = clamd.ClamdNetworkSocket(host=host, port=settings.clamav_port)
            result = cd.instream(io.BytesIO(raw)) or {}
            status, sig = result.get("stream", ("OK", None))
            if status == "FOUND":
                raise ValidationError(f"malware detectado por ClamAV: {sig}")
            logger.info("ClamAV OK: %s", name)
            return
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("ClamAV no disponible (%s): %s", host, exc)
            if settings.ingestion_require_av:
                raise ValidationError(f"antivirus no disponible y es obligatorio: {exc}")
    elif settings.ingestion_require_av:
        raise ValidationError("antivirus obligatorio pero no configurado (clamav_host)")


def _scan_active_content(name: str, raw: bytes) -> None:
    """Bloquea contenido activo/armado: macros VBA (Office) y JavaScript/acciones
    automáticas/archivos embebidos (PDF). Vectores de malware y exfiltración."""
    if not getattr(settings, "ingestion_block_active_content", True):
        return
    ext = Path(name).suffix.lower()
    if ext in (".docx", ".docm"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
        except Exception:  # noqa: BLE001
            return  # la estructura ya se validó; no bloquear por un fallo aquí
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            raise ValidationError(
                "documento con macros VBA (contenido activo); bloqueado por seguridad")
    elif ext == ".pdf":
        found = _find_pdf_active_content(raw)
        if found:
            raise ValidationError(
                f"PDF con contenido activo/embebido ({', '.join(sorted(set(found)))}); "
                "bloqueado por seguridad")


def validate_file(name: str, raw: bytes) -> None:
    """Valida integridad y seguridad del archivo. Lanza ValidationError si falla."""
    _check_size(raw)
    _check_mime(name, raw)
    _check_structure(name, raw)
    _scan_malware(name, raw)
    _scan_active_content(name, raw)
    logger.info("Validación OK: %s (%d bytes)", name, len(raw))


def apply_pii_policy(text: str, *, source: str) -> str:
    """Aplica la política de PII al texto extraído antes de vectorizar.

    Modo (`settings.ingestion_pii_mode`):
      - 'block'  : lanza ValidationError si hay PII.
      - 'redact' : reemplaza la PII por etiquetas (por defecto).
      - 'warn'   : registra un aviso y deja el texto intacto.
    """
    from app.agent.guardrails import find_pii, redact_pii

    found = find_pii(text)
    if not found:
        return text
    mode = (settings.ingestion_pii_mode or "redact").lower()
    if mode == "block":
        raise ValidationError(
            f"PII detectada ({', '.join(found)}); carga bloqueada por política")
    if mode == "warn":
        logger.warning("PII en %s (%s): se indexa sin redactar", source, ", ".join(found))
        return text
    logger.info("PII en %s (%s): redactada antes de indexar", source, ", ".join(found))
    return redact_pii(text)


def apply_injection_policy(text: str, *, source: str) -> str:
    """Defensa anti data-poisoning / inyección de prompt indirecta (OWASP LLM01/LLM03).

    Un documento no confiable puede traer instrucciones adversarias que el agente
    ejecutaría al recuperarlas. Según `settings.ingestion_injection_mode`:
      - 'sanitize' : neutraliza las instrucciones detectadas (por defecto).
      - 'block'    : lanza ValidationError.
      - 'warn'     : registra un aviso y deja el texto intacto.
      - 'off'      : desactiva el escaneo.
    """
    from app.agent.guardrails import detect_injection, sanitize_injection

    mode = (getattr(settings, "ingestion_injection_mode", "sanitize") or "sanitize").lower()
    if mode == "off" or not detect_injection(text):
        return text
    if mode == "block":
        raise ValidationError(
            f"posible inyección de prompt / envenenamiento en «{source}»; carga bloqueada")
    if mode == "warn":
        logger.warning("Inyección potencial en %s: se indexa sin cambios", source)
        return text
    logger.info("Inyección potencial en %s: neutralizada antes de indexar", source)
    return sanitize_injection(text)
