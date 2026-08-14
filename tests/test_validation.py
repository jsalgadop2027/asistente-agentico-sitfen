"""Tests de validación de ingesta (integridad, antivirus, PII). Sin GCP."""
import pytest

from app.config import settings
from ingestion.validation import (
    ValidationError,
    _EICAR,
    _check_mime,
    _check_size,
    _scan_malware,
    apply_pii_policy,
)


# ----------------------------- Tamaño ---------------------------------------
def test_size_empty_rejected():
    with pytest.raises(ValidationError):
        _check_size(b"")


def test_size_over_limit_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ingestion_max_bytes", 10)
    with pytest.raises(ValidationError):
        _check_size(b"x" * 11)


def test_size_ok():
    _check_size(b"contenido razonable")  # no lanza


# ----------------------------- MIME / magic-bytes ----------------------------
def test_mime_pdf_ok():
    _check_mime("doc.pdf", b"%PDF-1.7\n...")  # no lanza


def test_mime_pdf_mismatch_rejected():
    # extensión .pdf pero el contenido no empieza con %PDF-
    with pytest.raises(ValidationError):
        _check_mime("falso.pdf", b"esto no es un pdf")


def test_mime_txt_ok():
    _check_mime("notas.txt", "arándano peruano".encode("utf-8"))


def test_mime_unsupported_ext_rejected():
    with pytest.raises(ValidationError):
        _check_mime("malware.exe", b"MZ...")


# ----------------------------- Antivirus (EICAR) -----------------------------
def test_eicar_detected():
    payload = b"%PDF-1.4 inocente " + _EICAR + b" resto"
    with pytest.raises(ValidationError):
        _scan_malware("x.pdf", payload)


def test_clean_passes_without_av():
    # Sin clamav_host configurado y AV no obligatorio: no lanza.
    _scan_malware("x.pdf", b"%PDF-1.4 contenido limpio")


# ----------------------------- PII -------------------------------------------
def test_pii_redact_mode(monkeypatch):
    monkeypatch.setattr(settings, "ingestion_pii_mode", "redact")
    out = apply_pii_policy("Contacto: juan@example.com", source="x.pdf")
    assert "juan@example.com" not in out
    assert "EMAIL_REDACTED" in out


def test_pii_block_mode(monkeypatch):
    monkeypatch.setattr(settings, "ingestion_pii_mode", "block")
    with pytest.raises(ValidationError):
        apply_pii_policy("Escríbeme a juan@example.com", source="x.pdf")


def test_pii_warn_mode_keeps_text(monkeypatch):
    monkeypatch.setattr(settings, "ingestion_pii_mode", "warn")
    text = "Mi correo es juan@example.com"
    assert apply_pii_policy(text, source="x.pdf") == text


def test_no_pii_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "ingestion_pii_mode", "redact")
    text = "El arándano peruano se exporta a China."
    assert apply_pii_policy(text, source="x.pdf") == text
