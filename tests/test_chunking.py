"""Tests del chunking por tokens (no requieren GCP)."""
from ingestion.chunking import chunk_document


def test_chunk_basic():
    text = "El arándano peruano es un producto de exportación. " * 200
    chunks = list(chunk_document("test.pdf", "Test Doc", text))
    assert len(chunks) > 1
    assert all(c.tokens > 0 for c in chunks)
    assert all("[Documento: Test Doc]" in c.text for c in chunks)
    # los índices deben ser consecutivos
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_empty():
    assert list(chunk_document("e.pdf", "Empty", "")) == []


def test_chunk_short_text_single():
    chunks = list(chunk_document("s.pdf", "Short",
                                 "Arándano peruano para exportación a China y EEUU."))
    assert len(chunks) == 1
