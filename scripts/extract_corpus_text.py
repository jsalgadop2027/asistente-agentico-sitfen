"""Extrae texto plano de todos los PDF del corpus a una cache local (scratchpad).

Uso puntual para construir el golden dataset de 1000 registros. No forma parte
del pipeline de ingesta de producción (ver ingestion/loaders.py para eso).
"""
from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader

CORPUS = Path("corpus_documental")
OUT = Path(sys.argv[1])


def extract(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            text = f"[ERROR extrayendo página {i}: {exc}]"
        pages.append(f"--- página {i + 1} ---\n{text}")
    return "\n\n".join(pages)


def main() -> None:
    static_out = OUT / "static"
    enfen_out = OUT / "enfen"
    static_out.mkdir(parents=True, exist_ok=True)
    enfen_out.mkdir(parents=True, exist_ok=True)

    static_pdfs = sorted(p for p in CORPUS.glob("*.pdf"))
    enfen_pdfs = sorted(CORPUS.glob("ENFEN/**/*.pdf"))

    print(f"Static PDFs: {len(static_pdfs)}  ENFEN PDFs: {len(enfen_pdfs)}")

    for pdf in static_pdfs:
        dest = static_out / (pdf.stem + ".txt")
        if dest.exists():
            continue
        try:
            text = extract(pdf)
        except Exception as exc:  # noqa: BLE001
            text = f"[FALLO TOTAL: {exc}]"
            print(f"FALLO: {pdf} -> {exc}")
        dest.write_text(text, encoding="utf-8")
        print(f"OK static: {pdf.name} ({len(text)} chars)")

    for pdf in enfen_pdfs:
        rel = pdf.relative_to(CORPUS / "ENFEN")
        dest = enfen_out / (str(rel).replace("/", "__").replace("\\", "__").replace(".pdf", ".txt"))
        if dest.exists():
            continue
        try:
            text = extract(pdf)
        except Exception as exc:  # noqa: BLE001
            text = f"[FALLO TOTAL: {exc}]"
            print(f"FALLO: {pdf} -> {exc}")
        dest.write_text(text, encoding="utf-8")
        print(f"OK enfen: {pdf.name} ({len(text)} chars)")

    print("Listo.")


if __name__ == "__main__":
    main()
