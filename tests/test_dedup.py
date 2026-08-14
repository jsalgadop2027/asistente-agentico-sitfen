"""Tests del hash de contenido para control de duplicados (no requieren GCP)."""
from ingestion.ingest import compute_content_hash


def test_hash_is_deterministic():
    text = "Requisitos fitosanitarios para exportar arándano a China."
    assert compute_content_hash(text) == compute_content_hash(text)


def test_hash_ignores_whitespace_and_case():
    a = "Arándano   peruano\n\npara EXPORTACIÓN"
    b = "arándano peruano para exportación"
    assert compute_content_hash(a) == compute_content_hash(b)


def test_hash_differs_for_different_content():
    a = compute_content_hash("Requisitos de exportación a China.")
    b = compute_content_hash("Tarifas de flete marítimo a Europa.")
    assert a != b


def test_hash_is_hex_sha256():
    h = compute_content_hash("contenido de prueba")
    assert len(h) == 64
    int(h, 16)  # debe ser hexadecimal válido
