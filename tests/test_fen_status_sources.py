"""Tests del parser del índice semanal Niño 1+2 (NOAA CPC), fuente primaria de
la insignia del FEN.

`web-sst-monitor/` es un microservicio aparte y su carpeta lleva guion (no es un
paquete importable), así que el módulo se carga por ruta.
"""
import datetime
import importlib.util
from pathlib import Path

import pytest

APP_PY = Path(__file__).resolve().parents[1] / "web-sst-monitor" / "app.py"


@pytest.fixture(scope="module")
def monitor():
    spec = importlib.util.spec_from_file_location("sst_monitor_app", APP_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Extracto real de wksst9120.for (semanas de julio y agosto de 2026).
CPC_SAMPLE = """ Weekly SST data starts week centered on 2Sept1981
  Nino1+2      Nino3        Nino34        Nino4
 15JUL2026     25.6 3.7     28.1 2.3     29.4 2.1     29.9 1.1
 22JUL2026     25.4 3.8     28.1 2.5     29.3 2.2     29.8 1.0
 29JUL2026     25.4 4.1     28.3 2.8     29.4 2.3     29.7 1.0
 05AUG2026     25.3 4.1     28.4 3.1     29.5 2.6     29.8 1.1
"""

# Extracto con anomalías NEGATIVAS: van pegadas al valor de SST (`24.6-0.4`).
CPC_SAMPLE_NEG = """ Weekly SST data starts week centered on 3Jan1990
 20JAN2021     23.9-0.8     25.2-0.6     25.5-1.1     26.9-1.4
 27JAN2021     24.6-0.4     25.7-0.2     25.9-0.7     27.1-1.1
"""


def test_parses_latest_week(monitor):
    fecha, anomalia = monitor.parse_cpc_weekly(CPC_SAMPLE)
    assert fecha == datetime.date(2026, 8, 5)
    assert anomalia == pytest.approx(4.1)


def test_parses_negative_anomaly_glued_to_sst(monitor):
    """Sin espacio entre SST y anomalía: partir por espacios daría 24.6-0.4."""
    fecha, anomalia = monitor.parse_cpc_weekly(CPC_SAMPLE_NEG)
    assert fecha == datetime.date(2021, 1, 27)
    assert anomalia == pytest.approx(-0.4)


def test_takes_nino12_not_another_region(monitor):
    """La primera columna es Niño 1+2 (costa peruana), no Niño 3.4."""
    _, anomalia = monitor.parse_cpc_weekly(CPC_SAMPLE)
    assert anomalia == pytest.approx(4.1)   # Niño 1+2
    assert anomalia != pytest.approx(2.6)   # Niño 3.4 de esa misma línea


def test_ignores_headers_and_garbage(monitor):
    assert monitor.parse_cpc_weekly(" cabecera sin datos\n\n") is None
    assert monitor.parse_cpc_weekly("") is None
    assert monitor.parse_cpc_weekly(" 05XXX2026     25.3 4.1") is None


def test_month_parsing_is_locale_independent(monitor):
    """Se mapea el mes a mano: %b dependería del locale del contenedor."""
    for mes, numero in (("JAN", 1), ("MAY", 5), ("DEC", 12)):
        fecha, _ = monitor.parse_cpc_weekly(f" 03{mes}2026     25.0 1.5     26 1     27 1     28 1")
        assert fecha.month == numero


def test_classification_uses_icen_thresholds(monitor):
    """+4.1 °C cae en 'extraordinario' según la escala ICEN/ENFEN."""
    key, label, _color, _text = monitor._classify_fen_level(4.1)
    assert key == "extraordinario"
    assert monitor._classify_fen_level(1.98)[0] == "fuerte"
