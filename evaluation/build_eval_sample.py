"""Construye una muestra estratificada del golden set de 1000 preguntas.

golden_dataset_1000.jsonl no lleva columna `category` (solo question/ground_truth);
esa columna vive en golden_dataset_1000.xlsx, en el mismo orden de filas. Este
script hace un join posicional (con verificación defensiva de que el texto de
la pregunta coincide) para recuperar `category`/`source_document` sin agregar
pandas/openpyxl como dependencia — parsea el XML de la hoja directamente.

Uso:
    python -m evaluation.build_eval_sample [--n 150] [--floor 5] [--seed 42]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import zipfile
from collections import defaultdict
from html import unescape
from pathlib import Path

HERE = Path(__file__).parent
JSONL_PATH = HERE / "golden_dataset_1000.jsonl"
XLSX_PATH = HERE / "golden_dataset_1000.xlsx"

_ROW_RE = re.compile(r"<row[^>]*>(.*?)</row>", re.DOTALL)
_CELL_RE = re.compile(r"<c[^>]*?(?:\st=\"(?P<t>[^\"]*)\")?[^>]*>(?:<is>(?P<is>.*?)</is>|<v>(?P<v>.*?)</v>)?</c>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _cell_text(cell_xml: str, shared: list[str]) -> str:
    m = _CELL_RE.match(cell_xml)
    if not m:
        return ""
    if m.group("is") is not None:
        return unescape(_TAG_RE.sub("", m.group("is"))).strip()
    v = m.group("v")
    if v is None:
        return ""
    if m.group("t") == "s":
        return shared[int(v)] if int(v) < len(shared) else ""
    return unescape(v).strip()


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml").decode("utf-8")
    except KeyError:
        return []
    items = re.findall(r"<si>(.*?)</si>", data, re.DOTALL)
    out = []
    for item in items:
        text = "".join(re.findall(r"<t[^>]*>(.*?)</t>", item, re.DOTALL))
        out.append(unescape(_TAG_RE.sub("", text)))
    return out


def load_xlsx_rows(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as zf:
        shared = _load_shared_strings(zf)
        sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")

    rows_xml = _ROW_RE.findall(sheet_xml)
    rows: list[list[str]] = []
    for row_xml in rows_xml:
        cells_xml = re.findall(r"<c[^>/]*(?:/>|>.*?</c>)", row_xml, re.DOTALL)
        rows.append([_cell_text(c, shared) for c in cells_xml])

    header, *data_rows = rows
    header = [h.strip().lower() for h in header]
    out = []
    for r in data_rows:
        d = dict(zip(header, r))
        out.append(d)
    return out


def load_jsonl_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_joined_rows() -> list[dict]:
    jsonl_rows = load_jsonl_rows(JSONL_PATH)
    xlsx_rows = load_xlsx_rows(XLSX_PATH)
    if len(jsonl_rows) != len(xlsx_rows):
        raise ValueError(
            f"Desalineados: jsonl tiene {len(jsonl_rows)} filas, xlsx tiene {len(xlsx_rows)}"
        )
    joined = []
    for i, (j, x) in enumerate(zip(jsonl_rows, xlsx_rows)):
        if j["question"].strip() != x.get("question", "").strip():
            raise ValueError(
                f"Fila {i}: la pregunta del jsonl no coincide con la del xlsx.\n"
                f"  jsonl: {j['question'][:80]!r}\n  xlsx:  {x.get('question', '')[:80]!r}"
            )
        joined.append({
            "question": j["question"],
            "ground_truth": j.get("ground_truth", ""),
            "category": x.get("category", ""),
            "source_document": x.get("source_document", ""),
        })
    return joined


def stratified_sample(rows: list[dict], *, n: int, floor: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    selected: list[dict] = []
    remaining_pool: dict[str, list[dict]] = {}
    for cat, items in by_cat.items():
        items = items[:]
        rng.shuffle(items)
        take = min(floor, len(items))
        selected.extend(items[:take])
        remaining_pool[cat] = items[take:]

    budget = n - len(selected)
    if budget > 0:
        total_remaining = sum(len(v) for v in remaining_pool.values())
        if total_remaining > 0:
            allocations = {}
            for cat, items in remaining_pool.items():
                allocations[cat] = round(budget * len(items) / total_remaining)
            # ajustar redondeo para respetar el presupuesto exacto
            diff = budget - sum(allocations.values())
            cats_by_size = sorted(remaining_pool, key=lambda c: len(remaining_pool[c]), reverse=True)
            i = 0
            while diff != 0 and cats_by_size:
                cat = cats_by_size[i % len(cats_by_size)]
                if diff > 0 and allocations[cat] < len(remaining_pool[cat]):
                    allocations[cat] += 1
                    diff -= 1
                elif diff < 0 and allocations[cat] > 0:
                    allocations[cat] -= 1
                    diff += 1
                i += 1
                if i > 10000:
                    break
            for cat, take in allocations.items():
                selected.extend(remaining_pool[cat][:take])

    rng.shuffle(selected)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--floor", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(HERE / "eval_sample_150.jsonl"))
    args = parser.parse_args()

    joined = build_joined_rows()
    print(f"Filas unidas correctamente: {len(joined)}")

    from collections import Counter
    cat_counts = Counter(r["category"] for r in joined)
    print(f"Categorías ({len(cat_counts)}):")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {cat}")

    sample = stratified_sample(joined, n=args.n, floor=args.floor, seed=args.seed)
    print(f"\nMuestra final: {len(sample)} preguntas")
    sample_cat_counts = Counter(r["category"] for r in sample)
    for cat, count in sorted(sample_cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {cat}")

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in sample:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nEscrito: {out_path}")


if __name__ == "__main__":
    main()
