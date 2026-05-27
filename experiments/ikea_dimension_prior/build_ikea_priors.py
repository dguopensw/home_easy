#!/usr/bin/env python3
"""Build IKEA furniture dimension priors from the IKEA-Dataset zips."""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DIMENSION_MIN_CM = 5.0
DIMENSION_MAX_CM = 500.0
UNRELIABLE_COUNT_THRESHOLD = 20

CLEAN_COLUMNS = [
    "room_category",
    "normalized_category",
    "raw_category",
    "product_name",
    "product_id",
    "width_cm",
    "depth_cm",
    "height_cm",
    "material",
    "image_path",
    "raw_dimension_text",
]

OUTLIER_COLUMNS = CLEAN_COLUMNS + ["reason"]

PRIOR_COLUMNS = [
    "category",
    "axis",
    "count",
    "mean",
    "median",
    "p05",
    "p10",
    "p25",
    "p75",
    "p90",
    "p95",
    "min",
    "max",
    "is_unreliable",
]


@dataclass
class ParsedRow:
    room_category: str
    normalized_category: str
    raw_category: str
    product_name: str
    product_id: str
    width_cm: float | None
    depth_cm: float | None
    height_cm: float | None
    material: str
    image_path: str
    raw_dimension_text: str
    reason: str = ""

    def to_clean_dict(self) -> dict[str, str]:
        return {
            "room_category": self.room_category,
            "normalized_category": self.normalized_category,
            "raw_category": self.raw_category,
            "product_name": self.product_name,
            "product_id": self.product_id,
            "width_cm": format_number(self.width_cm),
            "depth_cm": format_number(self.depth_cm),
            "height_cm": format_number(self.height_cm),
            "material": self.material,
            "image_path": self.image_path,
            "raw_dimension_text": self.raw_dimension_text,
        }

    def to_outlier_dict(self) -> dict[str, str]:
        row = self.to_clean_dict()
        row["reason"] = self.reason
        return row


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    rounded = round(value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def normalize_text(value: str) -> str:
    value = re.sub(r"[_-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def title_from_text(value: str) -> str:
    cleaned = normalize_text(value)
    return cleaned.title() if cleaned else ""


def is_package_context(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "package number",
            "package measurement",
            "package measurements",
            "packaging",
            "packages",
            "package",
        )
    )


def convert_to_cm(value: str, unit: str) -> float:
    number = float(value.replace(",", "."))
    unit = unit.lower()
    if unit == "cm":
        return number
    if unit == "mm":
        return number / 10.0
    if unit == "m":
        return number * 100.0
    if unit in {"inch", "in"}:
        return number * 2.54
    raise ValueError(f"Unsupported unit: {unit}")


def first_measurement(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return convert_to_cm(match.group("value"), match.group("unit"))


def parse_dimensions(text: str) -> tuple[float | None, float | None, float | None]:
    number_unit = r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>cm|mm|m|inch|in)\b"
    width = first_measurement(rf"(?:^|\s)Width\s*:\s*{number_unit}", text)
    depth = first_measurement(rf"(?:^|\s)Depth(?:\s+[^:]+)?\s*:\s*{number_unit}", text)
    length = first_measurement(rf"(?:^|\s)Length\s*:\s*{number_unit}", text)
    if depth is None:
        depth = length

    height = first_measurement(rf"(?:^|\s)Height\s*:\s*{number_unit}", text)
    if height is None:
        height = first_measurement(rf"(?:^|\s)Max\.\s*height\s*:\s*{number_unit}", text)
    if height is None:
        height = first_measurement(rf"(?:^|\s)Height with legs\s*:\s*{number_unit}", text)

    return width, depth, height


def parse_material(text: str) -> str:
    match = re.search(r"\bMaterial\s*:\s*([^|;,]+)$", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return normalize_text(match.group(1))


def extract_product_from_dimension_line(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"\bDimension\s+(?P<token>.+?)\s+(?=Width\s*:|Depth\s*:|Length\s*:|Height\s*:)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    token = normalize_text(match.group("token"))
    id_match = re.search(r"(?P<name>.+?)[ _-]*(?P<id>\d{5,})$", token)
    if not id_match:
        return token, ""
    return title_from_text(id_match.group("name")), id_match.group("id")


def product_id_from_line(line: str) -> str | None:
    match = re.fullmatch(r"\s*(\d{5,})\s*", line)
    return match.group(1) if match else None


def product_id_from_filename(path: Path) -> str | None:
    match = re.search(r"(\d{5,})", path.stem)
    return match.group(1) if match else None


def category_parts_for_path(path: Path, extraction_root: Path, room_category: str) -> list[str]:
    try:
        relative_parts = list(path.parent.relative_to(extraction_root).parts)
    except ValueError:
        relative_parts = list(path.parent.parts)
    if relative_parts and normalize_text(relative_parts[0]).lower() == normalize_text(room_category).lower():
        relative_parts = relative_parts[1:]
    return [normalize_text(part) for part in relative_parts if normalize_text(part)]


def raw_category_from_path(path: Path, extraction_root: Path, room_category: str) -> str:
    parts = category_parts_for_path(path, extraction_root, room_category)
    return parts[-1] if parts else room_category


def normalize_category(raw_category: str, product_name: str) -> str:
    category_text = f"{raw_category} {product_name}".lower()
    mapping = [
        (
            (
                "tv bench",
                "tv benches",
                "tv unit",
                "tv units",
                "tv stand",
                "tv stands",
                "media unit",
                "media units",
            ),
            "tv_unit",
        ),
        (("sideboard", "sideboards"), "sideboard"),
        (("chest of drawers", "chests of drawers"), "dresser"),
        (("drawer unit", "drawer units"), "drawer_unit"),
        (("storage combination", "storage combinations"), "storage"),
        (("shelving unit", "shelving units"), "shelf"),
        (("bookcase", "bookcases", "bookshelf", "bookshelves"), "bookshelf"),
        (("wardrobe", "wardrobes"), "wardrobe"),
        (("dresser", "dressers", "chest", "drawer"), "dresser"),
        (("cabinet", "cabinets", "counter", "counters", "cupboard"), "cabinet"),
        (("coat stand", "coat stands", "rack", "racks"), "rack"),
        (("desk", "desks"), "desk"),
        (("table", "tables"), "table"),
        (("chair", "chairs", "stool", "stools"), "chair"),
        (("sofa", "sofas", "couch", "couches"), "sofa"),
        (("bed", "beds", "mattress", "mattresses"), "bed"),
        (("shelf", "shelves", "shelving"), "shelf"),
        (("storage",), "storage"),
    ]
    for keywords, normalized in mapping:
        if any(keyword in category_text for keyword in keywords):
            return normalized
    fallback = normalize_text(raw_category or product_name).lower()
    fallback = re.sub(r"[^a-z0-9]+", "_", fallback).strip("_")
    return fallback or "unknown"


def choose_image_path(product_id: str, source_path: Path, image_index: dict[str, list[Path]]) -> str:
    if not product_id or product_id not in image_index:
        return ""
    candidates = image_index[product_id]
    source_parent = source_path.parent
    same_folder = [path for path in candidates if path.parent == source_parent]
    selected = same_folder[0] if same_folder else candidates[0]
    return str(selected)


def make_row(
    *,
    room_category: str,
    extraction_root: Path,
    source_path: Path,
    product_id: str,
    product_name: str,
    raw_text: str,
    image_index: dict[str, list[Path]],
) -> ParsedRow:
    width_cm, depth_cm, height_cm = parse_dimensions(raw_text)
    raw_category = raw_category_from_path(source_path, extraction_root, room_category)
    resolved_product_name = product_name or title_from_text(raw_category)
    normalized_category = normalize_category(raw_category, resolved_product_name)
    return ParsedRow(
        room_category=room_category,
        normalized_category=normalized_category,
        raw_category=raw_category,
        product_name=resolved_product_name,
        product_id=product_id,
        width_cm=width_cm,
        depth_cm=depth_cm,
        height_cm=height_cm,
        material=parse_material(raw_text),
        image_path=choose_image_path(product_id, source_path, image_index),
        raw_dimension_text=normalize_text(raw_text),
    )


def classify_row(row: ParsedRow) -> str:
    if row.width_cm is None or row.depth_cm is None or row.height_cm is None:
        return "missing_dimension"
    values = (row.width_cm, row.depth_cm, row.height_cm)
    if any(value < DIMENSION_MIN_CM or value > DIMENSION_MAX_CM for value in values):
        return "dimension_out_of_range"
    return ""


def extract_zip_if_needed(zip_path: Path, extracted_root: Path) -> Path:
    target_dir = extracted_root / zip_path.stem
    if target_dir.exists():
        return target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(target_dir)
    return target_dir


def build_image_index(extraction_root: Path) -> dict[str, list[Path]]:
    image_index: dict[str, list[Path]] = defaultdict(list)
    for path in extraction_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        product_id = product_id_from_filename(path)
        if product_id:
            image_index[product_id].append(path)
    return image_index


def parse_text_file(
    text_path: Path,
    *,
    room_category: str,
    extraction_root: Path,
    image_index: dict[str, list[Path]],
) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    try:
        text = text_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return rows

    current_product_id: str | None = None
    for raw_line in text.splitlines():
        line = normalize_text(raw_line)
        if not line or set(line) == {"-"}:
            continue

        maybe_id = product_id_from_line(line)
        if maybe_id:
            current_product_id = maybe_id
            continue

        has_dimension = any(token in line.lower() for token in ("width", "depth", "length", "height"))
        if not has_dimension:
            continue

        dimension_product = extract_product_from_dimension_line(line)
        if dimension_product:
            product_name, dimension_product_id = dimension_product
            product_id = dimension_product_id or current_product_id or ""
        else:
            product_name = ""
            product_id = current_product_id or ""

        if not product_id:
            rows.append(
                ParsedRow(
                    room_category=room_category,
                    normalized_category="unknown",
                    raw_category=raw_category_from_path(text_path, extraction_root, room_category),
                    product_name=product_name,
                    product_id="",
                    width_cm=None,
                    depth_cm=None,
                    height_cm=None,
                    material=parse_material(line),
                    image_path="",
                    raw_dimension_text=line,
                    reason="missing_product_id",
                )
            )
            continue

        row = make_row(
            room_category=room_category,
            extraction_root=extraction_root,
            source_path=text_path,
            product_id=product_id,
            product_name=product_name,
            raw_text=line,
            image_index=image_index,
        )
        if is_package_context(line):
            row.reason = "package_dimension"
        rows.append(row)
    return rows


def parse_extraction_root(room_category: str, extraction_root: Path) -> list[ParsedRow]:
    image_index = build_image_index(extraction_root)
    rows: list[ParsedRow] = []
    for text_path in sorted(extraction_root.rglob("*.txt")):
        rows.extend(
            parse_text_file(
                text_path,
                room_category=room_category,
                extraction_root=extraction_root,
                image_index=image_index,
            )
        )
    return rows


def percentile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_priors(clean_rows: list[ParsedRow]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in clean_rows:
        grouped[(row.normalized_category, "width_cm")].append(row.width_cm or 0.0)
        grouped[(row.normalized_category, "depth_cm")].append(row.depth_cm or 0.0)
        grouped[(row.normalized_category, "height_cm")].append(row.height_cm or 0.0)

    prior_rows: list[dict[str, str]] = []
    for (category, axis), values in sorted(grouped.items()):
        count = len(values)
        prior_rows.append(
            {
                "category": category,
                "axis": axis,
                "count": str(count),
                "mean": format_number(statistics.fmean(values)),
                "median": format_number(statistics.median(values)),
                "p05": format_number(percentile(values, 0.05)),
                "p10": format_number(percentile(values, 0.10)),
                "p25": format_number(percentile(values, 0.25)),
                "p75": format_number(percentile(values, 0.75)),
                "p90": format_number(percentile(values, 0.90)),
                "p95": format_number(percentile(values, 0.95)),
                "min": format_number(min(values)),
                "max": format_number(max(values)),
                "is_unreliable": "true" if count < UNRELIABLE_COUNT_THRESHOLD else "false",
            }
        )
    return prior_rows


def write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def split_clean_and_outliers(rows: list[ParsedRow]) -> tuple[list[ParsedRow], list[ParsedRow]]:
    clean_rows: list[ParsedRow] = []
    outlier_rows: list[ParsedRow] = []
    seen_clean_keys: set[tuple[str, str, str]] = set()

    for row in rows:
        reason = row.reason or classify_row(row)
        if reason:
            row.reason = reason
            outlier_rows.append(row)
            continue

        key = (row.room_category, row.product_id, row.raw_dimension_text)
        if key in seen_clean_keys:
            continue
        seen_clean_keys.add(key)
        clean_rows.append(row)

    return clean_rows, outlier_rows


def print_summary(
    *,
    total_rows: int,
    clean_rows: list[ParsedRow],
    outlier_rows: list[ParsedRow],
    clean_path: Path,
    prior_path: Path,
    outlier_path: Path,
) -> None:
    print(f"Total parsed products: {total_rows}")
    print(f"Clean rows: {len(clean_rows)}")
    print(f"Outlier rows: {len(outlier_rows)}")
    print("Category counts:")
    for category, count in sorted(Counter(row.normalized_category for row in clean_rows).items()):
        flag = " unreliable" if count < UNRELIABLE_COUNT_THRESHOLD else ""
        print(f"  {category}: {count}{flag}")
    print("Generated files:")
    print(f"  {clean_path}")
    print(f"  {prior_path}")
    print(f"  {outlier_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("datasets/IKEA-Dataset"),
        help="Path to the IKEA-Dataset directory containing zip files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/ikea_dimension_prior/data"),
        help="Directory where generated CSV files will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_root = args.dataset_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not dataset_root.exists():
        raise SystemExit(f"Dataset root does not exist: {dataset_root}")

    zip_paths = sorted(dataset_root.glob("*.zip"))
    if not zip_paths:
        raise SystemExit(f"No zip files found in: {dataset_root}")

    extracted_root = dataset_root / "extracted"
    extracted_root.mkdir(parents=True, exist_ok=True)

    all_rows: list[ParsedRow] = []
    for zip_path in zip_paths:
        extraction_root = extract_zip_if_needed(zip_path, extracted_root)
        all_rows.extend(parse_extraction_root(zip_path.stem, extraction_root))

    clean_rows, outlier_rows = split_clean_and_outliers(all_rows)
    prior_rows = build_priors(clean_rows)

    clean_path = output_dir / "ikea_dimensions_clean.csv"
    prior_path = output_dir / "ikea_dimension_priors.csv"
    outlier_path = output_dir / "ikea_dimension_outliers.csv"

    write_csv(clean_path, CLEAN_COLUMNS, [row.to_clean_dict() for row in clean_rows])
    write_csv(outlier_path, OUTLIER_COLUMNS, [row.to_outlier_dict() for row in outlier_rows])
    write_csv(prior_path, PRIOR_COLUMNS, prior_rows)

    print_summary(
        total_rows=len(all_rows),
        clean_rows=clean_rows,
        outlier_rows=outlier_rows,
        clean_path=clean_path,
        prior_path=prior_path,
        outlier_path=outlier_path,
    )


if __name__ == "__main__":
    main()
