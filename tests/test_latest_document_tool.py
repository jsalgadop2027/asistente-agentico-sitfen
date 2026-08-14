"""Tests de la tool 'documento más reciente de una serie' — fecha real, no
similitud semántica.

Bug reportado en producción: ante "¿cuál es el último informe de ENFEN?", la
búsqueda semántica (consultar_base_conocimiento) devolvió un informe de mayo
2026 como "el más reciente" cuando ya había uno de junio 2026 en el corpus —
la similitud de embeddings no tiene noción de cronología. La tool generaliza
el fix a CUALQUIER serie periódica del corpus (ENFEN, ADEX, PROMPERÚ...), no
solo ENFEN. Estos tests cubren el parseo de fecha real desde el nombre de
archivo, el filtro por palabras clave de la serie y la selección del máximo.
"""
import app.kb_events as kbe
import app.agent.tools.rag_tools as rag_tools
from app.agent.tools.rag_tools import parse_document_date


def test_parse_recognizes_various_filename_conventions():
    cases = [
        ("Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf", (2026, 6, 24)),
        ("Informe Tecnico ENFEN Año 12 N° 11 al 12 junio 2026.pdf", (2026, 6, 12)),
        ("Informe Tecnico ENFEN Año 12 N°09-2026 al 13 mayo 2026.pdf", (2026, 5, 13)),
        ("Informe Tecnico ENFEN 12 JUNIO 2024.pdf", (2024, 6, 12)),
        ("Informe_ENFEN_JUNIO_2022.pdf", (2022, 6, 1)),
        ("Informe Tecnico ENFEN Año 12 N° 04 al 25 de febrero 2026.pdf", (2026, 2, 25)),
        ("Informe Tecnico ENFEN N° 03 al 12 febrero del 2026.pdf", (2026, 2, 12)),
        ("ADEX_CIEN_Reporte_Exportaciones_Enero2025.pdf", (2025, 1, 1)),
        ("PROMPERU_Informe_Mensual_Exportaciones_setiembre2025.pdf", (2025, 9, 1)),
    ]
    for filename, expected in cases:
        assert parse_document_date(filename) == expected, filename


def test_parse_returns_none_for_unrecognizable_dates():
    for filename in ("Inf_Tec_ENFEN_05-2018.pdf",
                     "ENFEN_Informe_Tecnico_Extraordinario_001_2017_Nino_Costero.pdf"):
        assert parse_document_date(filename) is None


class _FakeSnap:
    def __init__(self, source):
        self._source = source

    def to_dict(self):
        return {"source": self._source, "title": self._source}


class _FakeCollection:
    def __init__(self, sources):
        self._sources = sources

    def stream(self):
        return [_FakeSnap(s) for s in self._sources]


class _FakeKBEventStore:
    def __init__(self, sources):
        self.collection = _FakeCollection(sources)


def _fake_kb(monkeypatch, sources):
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _FakeKBEventStore(sources))
    rag_tools._find_latest_document_cached.cache_clear()


def test_finds_actual_latest_by_date_not_list_order(monkeypatch):
    """El informe de mayo (que podría aparecer primero en la colección) NO debe
    ganarle al de junio: el ranking es por fecha real, no por orden de llegada."""
    _fake_kb(monkeypatch, [
        "Informe Tecnico ENFEN Año 12 N°09-2026 al 13 mayo 2026.pdf",
        "Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf",
        "Informe Tecnico ENFEN Año 12 N° 11 al 12 junio 2026.pdf",
        "Documentos-necesarios-exportar-2023.pdf",  # sin "enfen", debe ignorarse
    ])

    found = rag_tools._find_latest_document("ENFEN")

    assert found is not None
    source, _title = found
    assert source == "Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf"


def test_filters_by_series_keyword_not_just_any_periodic_doc(monkeypatch):
    """Con `tema="ADEX"`, un informe ENFEN más reciente NO debe ganarle a un
    reporte ADEX más antiguo: el filtro por palabra clave de la serie viene
    primero, la fecha solo desempata DENTRO de la serie encontrada."""
    _fake_kb(monkeypatch, [
        "Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf",
        "ADEX_CIEN_Reporte_Exportaciones_Enero2025.pdf",
        "ADEX_CIEN_Reporte_Exportaciones_Diciembre2025.pdf",
    ])

    found = rag_tools._find_latest_document("ADEX exportaciones")

    assert found is not None
    source, _title = found
    assert source == "ADEX_CIEN_Reporte_Exportaciones_Diciembre2025.pdf"


def test_returns_none_when_no_series_matches(monkeypatch):
    _fake_kb(monkeypatch, ["Guia_practica_del_exportador.pdf", "Peru-Super-Foods.pdf"])

    assert rag_tools._find_latest_document("informes del BCRP") is None


def test_returns_none_for_hint_without_distinctive_tokens(monkeypatch):
    """Si `tema` son solo palabras genéricas ("el más reciente informe"), no hay
    con qué filtrar la serie: falla cerrado en vez de devolver cualquier cosa."""
    _fake_kb(monkeypatch, ["Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf"])

    assert rag_tools._find_latest_document("el informe más reciente") is None


def test_tool_returns_content_of_the_true_latest_report(monkeypatch):
    _fake_kb(monkeypatch, [
        "Informe Tecnico ENFEN Año 12 N°09-2026 al 13 mayo 2026.pdf",
        "Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf",
    ])

    class _Chunk:
        def __init__(self, text):
            self.text = text

    class _FakeVectorStore:
        def get_document_chunks(self, source, *, limit=30):
            assert source == "Informe Tecnico ENFEN Año 12 N°12 al 24 junio 2026.pdf"
            return [_Chunk("Contenido real del informe de junio 2026.")]

    import app.firestore_store as fs
    monkeypatch.setattr(fs, "FirestoreVectorStore", _FakeVectorStore)

    out = rag_tools.consultar_documento_mas_reciente.invoke({"tema": "ENFEN"})

    assert "junio 2026" in out
    assert "Contenido real del informe de junio 2026." in out
    assert "13 mayo 2026" not in out
