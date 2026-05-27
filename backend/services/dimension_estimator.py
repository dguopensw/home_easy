"""치수 추정 서비스: listing_text → product_match → vision_estimate_v2 우선순위 체인."""
from __future__ import annotations

import logging
import os
import re
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

from core import _core

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 카테고리 별칭 / 브랜드 상수
# ---------------------------------------------------------------------------

_CATEGORY_ALIASES: dict[str, str] = {
    "desk": "desk", "의자": "chair", "chair": "chair",
    "소파": "sofa", "sofa": "sofa", "table": "table", "테이블": "table",
    "bed": "bed", "침대": "bed", "bookshelf": "bookshelf",
    "cabinet": "cabinet", "dresser": "dresser", "wardrobe": "wardrobe",
    "shelf": "shelf",
}

_KNOWN_BRANDS = [
    "IKEA", "이케아", "한샘", "리바트", "일룸", "데스커",
    "시디즈", "마켓비", "까사미아", "무인양품", "MUJI",
]

_MODEL_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9-]{2,}\b")
_SUPPORTED_PRODUCT_MATCH_BRANDS = {"ikea", "muji"}
_PACKAGE_CONTEXT_RE = re.compile(
    r"package|packaging|package size|box|shipping|delivery|parcel|박스|포장|배송|택배",
    flags=re.IGNORECASE,
)
_EXTERNAL_PRODUCT_DOMAINS = (
    "naver.me",
    "smartstore.naver.com",
    "brand.naver.com",
    "shopping.naver.com",
    "ohou.se",
    "coupang.com",
    "11st.co.kr",
    "gmarket.co.kr",
    "auction.co.kr",
    "lotteon.com",
    "ssg.com",
)
_IMAGE_URL_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg")
_MODEL_KO_ALIASES = {
    "HEMNES": "헴네스",
    "MALM": "말름",
    "KALLAX": "칼락스",
    "BILLY": "빌리",
}

# confidence 레벨 ↔ 숫자 매핑
_CONF_LEVEL: dict[str, int] = {
    "high": 5,
    "medium_high": 4,
    "medium": 3,
    "medium_low": 2,
    "low": 1,
}
_LEVEL_CONF: dict[int, str] = {v: k for k, v in _CONF_LEVEL.items()}


# ---------------------------------------------------------------------------
# listing_dims 완성도 분류
# ---------------------------------------------------------------------------

def _classify_listing_dims(listing_dims: dict | None) -> str:
    """listing_dims의 완성도를 반환한다: 'complete' | 'partial' | 'missing'."""
    if not listing_dims:
        return "missing"
    has_w = listing_dims.get("width_cm") is not None
    has_d = listing_dims.get("depth_cm") is not None
    has_h = listing_dims.get("height_cm") is not None
    if has_w and has_d and has_h:
        return "complete"
    if has_w or has_d or has_h:
        return "partial"
    return "missing"


# ---------------------------------------------------------------------------
# IKEA prior table 로딩
# ---------------------------------------------------------------------------

def load_ikea_prior_table() -> dict | None:
    """IKEA 카테고리별 치수 prior 통계를 로드한다. CSV 없으면 None 반환."""
    repo_root = Path(__file__).resolve().parents[2]
    prior_relative_path = Path("experiments/ikea_dimension_prior/data/ikea_dimension_priors.csv")
    candidate_paths = [
        repo_root / prior_relative_path,
        prior_relative_path,
        Path("/Users/dahoo/home_easy/experiments/ikea_dimension_prior/data/ikea_dimension_priors.csv"),
        Path("/Users/dahoo/home_easy/datasets/ikea_dimension_priors.csv"),
        Path("/Users/dahoo/home_easy/datasets/ikea_dimensions_clean.csv"),
        Path("data/ikea_dimension_priors.csv"),
    ]

    # datasets/ 디렉토리 내 CSV 탐색
    datasets_dir = Path("/Users/dahoo/home_easy/datasets")
    if datasets_dir.is_dir():
        candidate_paths.extend(datasets_dir.glob("*.csv"))

    for csv_path in candidate_paths:
        if not csv_path.exists():
            continue
        try:
            return _parse_ikea_prior_csv(csv_path)
        except Exception as e:
            logger.warning("IKEA prior CSV parse failed (%s): %s", csv_path, e)

    logger.warning("prior_table_missing: IKEA dimension prior CSV not found; skipping prior validation")
    return None


def _parse_ikea_prior_csv(csv_path: Path) -> dict:
    """CSV → {category: {axis: {count, p05, p10, p90, p95, is_unreliable}}}."""
    import csv

    prior: dict[str, dict[str, dict[str, float | int | bool]]] = {}

    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_lower = {k.lower(): v for k, v in row.items()}
            category = _normalize_prior_category(row_lower.get("category"))
            axis = row_lower.get("axis", "").strip().lower()
            if not category or axis not in {"width_cm", "depth_cm", "height_cm"}:
                continue

            p05 = _to_cm(row_lower.get("p05"))
            p10 = _to_cm(row_lower.get("p10"))
            p90 = _to_cm(row_lower.get("p90"))
            p95 = _to_cm(row_lower.get("p95"))
            if None in (p05, p10, p90, p95):
                continue

            try:
                count = int(float(row_lower.get("count", "0") or 0))
            except ValueError:
                count = 0

            is_unreliable = str(row_lower.get("is_unreliable", "")).strip().lower() in {
                "true",
                "1",
                "yes",
            }
            prior.setdefault(category, {})[axis] = {
                "count": count,
                "p05": p05,
                "p10": p10,
                "p90": p90,
                "p95": p95,
                "is_unreliable": is_unreliable,
            }

    return prior


def _to_cm(value: str | float | int | None) -> float | None:
    """단위 문자열 포함 수치를 cm로 변환. 변환 불가 시 None."""
    if value is None:
        return None
    s = str(value).strip().lower().replace(",", ".")
    try:
        num_str = re.search(r"[\d.]+", s)
        if not num_str:
            return None
        num = float(num_str.group())
        if "mm" in s:
            return num / 10.0
        if "inch" in s or '"' in s:
            return num * 2.54
        if s.endswith("m") and "cm" not in s:
            return num * 100.0
        return num  # cm 또는 단위 없음 → cm 가정
    except ValueError:
        return None


def _normalize_prior_category(furniture_type: str | None) -> str:
    """서비스의 furniture_type을 IKEA prior category 키로 맞춘다."""
    category_raw = (furniture_type or "unknown").strip().lower()
    category_raw = re.sub(r"[_-]+", " ", category_raw)
    category_raw = re.sub(r"\s+", " ", category_raw)

    direct = _CATEGORY_ALIASES.get(category_raw)
    if direct:
        return direct

    keyword_map = [
        (("tv bench", "tv unit", "tv stand", "media unit"), "tv_unit"),
        (("sideboard",), "sideboard"),
        (("chest of drawers", "dresser", "chest", "drawer"), "dresser"),
        (("drawer unit",), "drawer_unit"),
        (("storage combination", "storage"), "storage"),
        (("shelving unit", "shelving", "shelf"), "shelf"),
        (("bookcase", "bookshelf"), "bookshelf"),
        (("cabinet", "counter"), "cabinet"),
        (("wardrobe",), "wardrobe"),
        (("desk",), "desk"),
        (("table",), "table"),
        (("chair", "stool"), "chair"),
        (("sofa", "couch"), "sofa"),
        (("bed",), "bed"),
        (("rack", "coat stand"), "rack"),
    ]
    for keywords, category in keyword_map:
        if any(keyword in category_raw for keyword in keywords):
            return category
    return category_raw.replace(" ", "_") or "unknown"


def _axis_value(dimensions: dict, axis: str) -> float | None:
    """width_cm/depth_cm/height_cm 우선, 기존 w/d/h 키도 보조로 읽는다."""
    value = dimensions.get(axis)
    if value is None and axis == "width_cm":
        value = dimensions.get("w")
    elif value is None and axis == "depth_cm":
        value = dimensions.get("d")
    elif value is None and axis == "height_cm":
        value = dimensions.get("h")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dedupe_strings(values: list[str], max_items: int = 12) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
        if len(deduped) >= max_items:
            break
    return deduped


def _hint_list(product_candidate_hint: dict | None, key: str) -> list[str]:
    if not isinstance(product_candidate_hint, dict):
        return []
    value = product_candidate_hint.get(key)
    if not isinstance(value, list):
        return []
    return _dedupe_strings([item for item in value if isinstance(item, str)])


def _extract_brand_model_candidates(title: str, description: str) -> tuple[list[str], list[str]]:
    text = f"{title} {description}"
    lowered = text.lower()
    brands = [brand for brand in _KNOWN_BRANDS if brand.lower() in lowered]

    models: list[str] = []
    for token in _MODEL_TOKEN_RE.findall(text):
        if token.upper() in {"IKEA", "MUJI", "CM", "MM"}:
            continue
        models.append(token)

    return _dedupe_strings(brands, max_items=5), _dedupe_strings(models, max_items=8)


def _drawer_count_terms(title: str, description: str) -> list[str]:
    text = f"{title} {description}"
    terms: list[str] = []
    for match in re.finditer(r"(\d+)\s*(?:칸|단)", text):
        count = match.group(1)
        terms.extend([
            f"{count} drawer dresser",
            f"{count}-drawer chest",
            f"chest of {count} drawers",
            f"{count}칸 서랍장",
            f"{count}단 서랍장",
        ])
    if "서랍장" in text:
        terms.extend(["dresser", "chest of drawers", "drawer chest", "서랍장"])
    return _dedupe_strings(terms, max_items=12)


def _expected_drawer_counts(title: str, description: str) -> set[int]:
    text = f"{title} {description}"
    counts: set[int] = set()
    for match in re.finditer(r"(\d+)\s*(?:칸|단)", text):
        counts.add(int(match.group(1)))
    for match in re.finditer(r"\b(\d+)\s*-?\s*drawers?\b", text, flags=re.IGNORECASE):
        counts.add(int(match.group(1)))
    for match in re.finditer(r"\bchest\s+of\s+(\d+)\s+drawers?\b", text, flags=re.IGNORECASE):
        counts.add(int(match.group(1)))
    return counts


def _candidate_drawer_counts(text: str) -> set[int]:
    counts: set[int] = set()
    for match in re.finditer(r"(\d+)\s*(?:칸|단)", text):
        counts.add(int(match.group(1)))
    for match in re.finditer(r"\b(\d+)\s*-?\s*drawers?\b", text, flags=re.IGNORECASE):
        counts.add(int(match.group(1)))
    for match in re.finditer(r"\bchest\s+of\s+(\d+)\s+drawers?\b", text, flags=re.IGNORECASE):
        counts.add(int(match.group(1)))
    return counts


def _drawer_count_matches(text: str, title: str, description: str) -> bool:
    expected = _expected_drawer_counts(title, description)
    if not expected:
        return True
    candidate_counts = _candidate_drawer_counts(text)
    if not candidate_counts:
        return True
    return bool(expected & candidate_counts)


def _is_storage_like_furniture(furniture_type: str, title: str, description: str) -> bool:
    haystack = f"{furniture_type} {title} {description}".lower()
    return any(
        token in haystack
        for token in (
            "cabinet",
            "dresser",
            "drawer",
            "storage",
            "wardrobe",
            "서랍",
            "서랍장",
            "수납",
            "옷장",
        )
    )


def _model_terms_with_aliases(models: list[str]) -> list[str]:
    terms: list[str] = []
    for model in models:
        terms.append(model)
        alias = _MODEL_KO_ALIASES.get(model.upper())
        if alias:
            terms.append(alias)
    return _dedupe_strings(terms, max_items=12)


def _build_product_match_queries(
    title: str,
    description: str,
    furniture_type: str,
    product_candidate_hint: dict | None,
) -> list[str]:
    text_brands, text_models = _extract_brand_model_candidates(title, description)
    hint_brands = _hint_list(product_candidate_hint, "possible_brands")
    hint_models = _hint_list(product_candidate_hint, "possible_models")
    hint_keywords = _hint_list(product_candidate_hint, "search_keywords")
    hint_features = _hint_list(product_candidate_hint, "visual_features")

    queries: list[str] = []
    all_brands = _dedupe_strings(text_brands + hint_brands)
    all_models = _model_terms_with_aliases(_dedupe_strings(text_models + hint_models))
    drawer_terms = _drawer_count_terms(title, description)
    storage_terms = ["dresser", "chest of drawers", "drawer chest"]
    if any(term.startswith("8") for term in drawer_terms):
        storage_terms.extend(["8 drawer dresser", "8-drawer chest"])

    if _is_storage_like_furniture(furniture_type, title, description):
        for brand in all_brands:
            for model in all_models or [title]:
                for term in drawer_terms or storage_terms:
                    if re.search(r"[가-힣]", term):
                        queries.append(f"{brand} {model} {term} 크기")
                    else:
                        queries.append(f"{brand} {model} {term} dimensions")

    for brand in text_brands:
        if text_models:
            for model in text_models:
                queries.append(f"{brand} {model} {furniture_type} dimensions cm")
        else:
            queries.append(f"{brand} {title} {furniture_type} dimensions cm")

    for brand in hint_brands:
        queries.append(f"{brand} {title} {furniture_type} dimensions cm")

    for model in hint_models:
        brand_prefix = f"{hint_brands[0]} " if hint_brands else ""
        queries.append(f"{brand_prefix}{model} {furniture_type} dimensions cm")

    for keyword in hint_keywords:
        queries.append(f"{keyword} dimensions cm")

    for feature in hint_features[:5]:
        queries.append(f"{feature} {furniture_type} dimensions cm")

    if not queries:
        queries.append(f"{title} {furniture_type} dimensions cm")

    return _dedupe_strings(queries)


def _extract_external_product_urls(title: str, description: str) -> list[str]:
    """판매글 텍스트에서 외부 상품 상세 링크 후보를 추출한다."""
    text = f"{title} {description}"
    raw_urls = re.findall(r"https?://[^\s<>\"]+", text)
    urls: list[str] = []
    for raw_url in raw_urls:
        url = raw_url.rstrip(").,]}>\"'")
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if not host:
            continue
        if path.endswith(_IMAGE_URL_EXTENSIONS):
            continue
        if not any(domain in host for domain in _EXTERNAL_PRODUCT_DOMAINS):
            continue
        urls.append(url)
    return _dedupe_strings(urls, max_items=8)


def _canonical_brand(value: str | None) -> str | None:
    lowered = (value or "").strip().lower()
    if lowered in {"ikea", "이케아"}:
        return "ikea"
    if lowered in {"muji", "무인양품"}:
        return "muji"
    return None


def _select_product_match_brand(
    title: str,
    description: str,
    product_candidate_hint: dict | None,
) -> str | None:
    text_brands, _ = _extract_brand_model_candidates(title, description)
    for brand in text_brands + _hint_list(product_candidate_hint, "possible_brands"):
        canonical = _canonical_brand(brand)
        if canonical in _SUPPORTED_PRODUCT_MATCH_BRANDS:
            return canonical
    return None


def _best_model_query(title: str, description: str, product_candidate_hint: dict | None) -> str:
    _, text_models = _extract_brand_model_candidates(title, description)
    hint_models = _hint_list(product_candidate_hint, "possible_models")
    if text_models:
        return text_models[0]
    if hint_models:
        return hint_models[0]
    keywords = _hint_list(product_candidate_hint, "search_keywords")
    if keywords:
        return keywords[0]
    return title


def _build_candidate_urls_for_ikea(
    brand: str,
    queries: list[str],
    product_candidate_hint: dict | None,
) -> list[str]:
    """IKEA/MUJI 공식 검색 URL 후보를 만든다. 실제 확정은 페이지 파싱 후에만 한다."""
    urls: list[str] = []
    for query in queries[:8]:
        if query.startswith(("http://", "https://")):
            urls.append(query)
            continue
        encoded = quote_plus(query)
        if brand == "ikea":
            urls.extend([
                f"https://www.ikea.com/kr/ko/search/?q={encoded}",
                f"https://www.ikea.com/us/en/search/?q={encoded}",
            ])
        elif brand == "muji":
            urls.extend([
                f"https://www.muji.com/kr/search?query={encoded}",
                f"https://www.muji.com/us/search/?q={encoded}",
            ])

    for keyword in _hint_list(product_candidate_hint, "search_keywords")[:4]:
        if keyword.startswith(("http://", "https://")):
            urls.append(keyword)
            continue
        encoded = quote_plus(keyword)
        if brand == "ikea":
            urls.append(f"https://www.ikea.com/kr/ko/search/?q={encoded}")
        elif brand == "muji":
            urls.append(f"https://www.muji.com/kr/search?query={encoded}")

    return _dedupe_strings(urls, max_items=16)


def _fetch_url_text(url: str, timeout: int = 5) -> str | None:
    html = _fetch_url_html(url, timeout=timeout)
    if html is None:
        return None

    return _html_to_text(html)


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_url_html(url: str, timeout: int = 5) -> str | None:
    result = _fetch_url_html_with_final_url(url, timeout=timeout)
    return result.get("html")


def _fetch_url_html_with_final_url(url: str, timeout: int = 5) -> dict:
    try:
        import requests

        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        html = response.text
    except Exception as e:
        logger.debug("product_match fetch failed: url=%s error=%s", url, e)
        return {"html": None, "final_url": None, "error": str(e)}

    return {"html": html, "final_url": response.url, "error": None}


def _is_package_dimension_context(text: str) -> bool:
    return bool(_PACKAGE_CONTEXT_RE.search(text or ""))


def _unit_to_cm(value: str, unit: str | None) -> float:
    number = _parse_number(value)
    unit = (unit or "cm").lower()
    if unit == "mm":
        return number / 10.0
    if unit == "m":
        return number * 100.0
    if unit in {"in", "inch", "inches"}:
        return number * 2.54
    return number


def _parse_number(value: str | float | int) -> float:
    text = str(value).strip().replace(",", ".")
    fraction_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s+(\d+)/(\d+)", text)
    if fraction_match:
        whole = float(fraction_match.group(1))
        numerator = float(fraction_match.group(2))
        denominator = float(fraction_match.group(3))
        return whole + numerator / denominator
    simple_fraction = re.fullmatch(r"(\d+)/(\d+)", text)
    if simple_fraction:
        return float(simple_fraction.group(1)) / float(simple_fraction.group(2))
    return float(text)


def _valid_product_dimension_triplet(width: float, depth: float, height: float) -> bool:
    return all(5 <= value <= 500 for value in (width, depth, height))


def _valid_product_dimension_value(value: float | None) -> bool:
    return value is not None and 5 <= value <= 500


def _dimension_signature(dimensions: dict) -> tuple:
    return (
        round(dimensions["width_cm"], 1) if dimensions.get("width_cm") is not None else None,
        round(dimensions["depth_cm"], 1) if dimensions.get("depth_cm") is not None else None,
        round(dimensions["height_cm"], 1) if dimensions.get("height_cm") is not None else None,
    )


def _dimensions_conflict(a: dict, b: dict, tolerance_cm: float = 3.0) -> bool:
    for axis in ("width_cm", "depth_cm", "height_cm"):
        av = a.get(axis)
        bv = b.get(axis)
        if av is None or bv is None:
            continue
        if abs(float(av) - float(bv)) > tolerance_cm:
            return True
    return False


def _has_any_dimension_axis(dimensions: dict | None) -> bool:
    return bool(dimensions) and any(
        dimensions.get(axis) is not None
        for axis in ("width_cm", "depth_cm", "height_cm")
    )


def _merge_dimensions(base: dict | None, supplement: dict | None) -> dict | None:
    if not base and not supplement:
        return None
    merged = dict(base or {})
    for axis in ("width_cm", "depth_cm", "height_cm"):
        if merged.get(axis) is None and supplement and supplement.get(axis) is not None:
            merged[axis] = supplement.get(axis)
    if not merged.get("raw_match") and supplement and supplement.get("raw_match"):
        merged["raw_match"] = supplement["raw_match"]
    return merged if _has_any_dimension_axis(merged) else None


_NUM_RE = r"\d+(?:[.,]\d+)?(?:\s+\d+/\d+)?|\d+/\d+"


def _extract_dimension_axes_from_text(text: str) -> dict | None:
    """검색 title/snippet에서 1개 이상 명확한 축 치수를 추출한다."""
    if not text:
        return None

    candidates: list[dict] = []

    for pattern in [
        re.compile(
            rf"(?:\bwidth\b|폭|너비|가로)\s*:?\s*(?P<w>{_NUM_RE})\s*(?P<wu>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\bW\b\s*[:=]?\s*(?P<w>{_NUM_RE})\s*(?P<wu>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"(?:\bdepth\b|깊이|세로)\s*:?\s*(?P<d>{_NUM_RE})\s*(?P<du>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\bD\b\s*[:=]?\s*(?P<d>{_NUM_RE})\s*(?P<du>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"(?:\bheight\b|높이)\s*:?\s*(?P<h>{_NUM_RE})\s*(?P<hu>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\bH\b\s*[:=]?\s*(?P<h>{_NUM_RE})\s*(?P<hu>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
    ]:
        for match in pattern.finditer(text):
            context = text[max(0, match.start() - 80): min(len(text), match.end() + 80)]
            if _is_package_dimension_context(context):
                continue
            groups = match.groupdict()
            dims = {"width_cm": None, "depth_cm": None, "height_cm": None}
            if groups.get("w"):
                dims["width_cm"] = _unit_to_cm(groups["w"], groups.get("wu") or "cm")
            if groups.get("d"):
                dims["depth_cm"] = _unit_to_cm(groups["d"], groups.get("du") or "cm")
            if groups.get("h"):
                dims["height_cm"] = _unit_to_cm(groups["h"], groups.get("hu") or "cm")
            if any(_valid_product_dimension_value(dims[axis]) for axis in dims):
                dims["raw_match"] = re.sub(r"\s+", " ", match.group(0)).strip()
                candidates.append(dims)

    combo_pattern = re.compile(
        rf"(?P<a>{_NUM_RE})\s*(?:x|×|\*)\s*(?P<b>{_NUM_RE})(?:\s*(?:x|×|\*)\s*(?P<c>{_NUM_RE}))?\s*(?P<u>cm|mm|m|inch|in)?",
        flags=re.IGNORECASE,
    )
    for match in combo_pattern.finditer(text):
        context = text[max(0, match.start() - 80): min(len(text), match.end() + 80)]
        if _is_package_dimension_context(context):
            continue
        unit = match.group("u") or "cm"
        first = _unit_to_cm(match.group("a"), unit)
        second = _unit_to_cm(match.group("b"), unit)
        third = _unit_to_cm(match.group("c"), unit) if match.group("c") else None
        dims = {"width_cm": first, "depth_cm": None, "height_cm": second}
        if third is not None:
            dims["depth_cm"] = second
            dims["height_cm"] = third
        if any(_valid_product_dimension_value(dims[axis]) for axis in dims):
            dims["raw_match"] = re.sub(r"\s+", " ", match.group(0)).strip()
            candidates.append(dims)

    if not candidates:
        return None

    merged = {"width_cm": None, "depth_cm": None, "height_cm": None, "raw_match": ""}
    raw_matches: list[str] = []
    for candidate in candidates:
        for axis in ("width_cm", "depth_cm", "height_cm"):
            if merged.get(axis) is None and _valid_product_dimension_value(candidate.get(axis)):
                merged[axis] = candidate[axis]
        if candidate.get("raw_match"):
            raw_matches.append(candidate["raw_match"])
    merged["raw_match"] = "; ".join(_dedupe_strings(raw_matches, max_items=3))
    return merged if _has_any_dimension_axis(merged) else None


def _extract_any_dimensions_from_text(text: str) -> dict | None:
    return _extract_dimensions_from_text(text) or _extract_dimension_axes_from_text(text)


def _extract_dimensions_from_text(text: str) -> dict | None:
    """페이지 텍스트에서 제품 W/D/H 3축 치수만 추출한다."""
    if not text:
        return None

    patterns = [
        re.compile(
            r"Width\s*:?\s*(?P<w>\d+(?:[.,]\d+)?)\s*(?P<wu>cm|mm|m|inch|in)?"
            r".{0,80}?Depth\s*:?\s*(?P<d>\d+(?:[.,]\d+)?)\s*(?P<du>cm|mm|m|inch|in)?"
            r".{0,80}?Height\s*:?\s*(?P<h>\d+(?:[.,]\d+)?)\s*(?P<hu>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"\bW\s*:?\s*(?P<w>\d+(?:[.,]\d+)?)\s*(?P<wu>cm|mm|m|inch|in)?"
            r"(?:\s*x\s*|\s+)"
            r"D\s*:?\s*(?P<d>\d+(?:[.,]\d+)?)\s*(?P<du>cm|mm|m|inch|in)?"
            r"(?:\s*x\s*|\s+)"
            r"H\s*:?\s*(?P<h>\d+(?:[.,]\d+)?)\s*(?P<hu>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"(?:제품\s*크기|product\s*size|size)?\s*"
            r"(?P<w>\d+(?:[.,]\d+)?)\s*(?:x|×|\*)\s*"
            r"(?P<d>\d+(?:[.,]\d+)?)\s*(?:x|×|\*)\s*"
            r"(?P<h>\d+(?:[.,]\d+)?)\s*(?P<u>cm|mm|m|inch|in)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"(?:가로|폭|너비)\s*:?\s*(?P<w>\d+(?:[.,]\d+)?)\s*(?P<wu>cm|mm|m)?"
            r".{0,80}?(?:깊이|세로)\s*:?\s*(?P<d>\d+(?:[.,]\d+)?)\s*(?P<du>cm|mm|m)?"
            r".{0,80}?높이\s*:?\s*(?P<h>\d+(?:[.,]\d+)?)\s*(?P<hu>cm|mm|m)?",
            flags=re.IGNORECASE,
        ),
    ]

    candidates: list[dict] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 120)
            end = min(len(text), match.end() + 120)
            context = text[start:end]
            if _is_package_dimension_context(context):
                continue

            groups = match.groupdict()
            unit = groups.get("u")
            width = _unit_to_cm(groups["w"], groups.get("wu") or unit)
            depth = _unit_to_cm(groups["d"], groups.get("du") or unit)
            height = _unit_to_cm(groups["h"], groups.get("hu") or unit)
            if not _valid_product_dimension_triplet(width, depth, height):
                continue
            candidates.append({
                "width_cm": width,
                "depth_cm": depth,
                "height_cm": height,
                "raw_match": re.sub(r"\s+", " ", match.group(0)).strip(),
            })

    if not candidates:
        return None

    first = candidates[0]
    first["candidate_count"] = len(candidates)
    first["ambiguous"] = len({
        (round(c["width_cm"], 1), round(c["depth_cm"], 1), round(c["height_cm"], 1))
        for c in candidates
    }) > 1
    return first


def _score_product_candidate(candidate: dict, brand: str, model_query: str) -> dict:
    url = candidate.get("url", "")
    text = f"{candidate.get('title', '')} {candidate.get('text', '')}".lower()
    brand_ok = brand == "ikea" and ("ikea" in url.lower() or "ikea" in text or "이케아" in text)
    brand_ok = brand_ok or (
        brand == "muji"
        and ("muji" in url.lower() or "muji" in text or "무인양품" in text)
    )
    model_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9가-힣-]{2,}", model_query or "")
        if token.lower() not in {"ikea", "muji", "dimensions", "cm"}
    ]
    model_matches = sum(1 for token in model_tokens[:5] if token in text or token in url.lower())
    is_official = (
        brand == "ikea" and "ikea.com" in url.lower()
    ) or (
        brand == "muji" and "muji.com" in url.lower()
    )

    score = 0
    if is_official:
        score += 4
    if brand_ok:
        score += 3
    score += min(model_matches, 3)
    if candidate.get("dimensions"):
        score += 5
    if (candidate.get("dimensions") or {}).get("ambiguous"):
        score -= 3

    return {
        "score": score,
        "is_official": is_official,
        "brand_ok": brand_ok,
        "model_matches": model_matches,
    }


def _extract_candidate_links(text: str, base_url: str, brand: str) -> list[str]:
    if not text:
        return []
    links = re.findall(r'https?://[^\s"\'<>]+|href=["\']([^"\']+)["\']', text)
    flattened = [item if isinstance(item, str) else next((part for part in item if part), "") for item in links]
    urls: list[str] = []
    for href in flattened:
        if not href:
            continue
        url = urljoin(base_url, href)
        lowered = url.lower()
        if brand == "ikea" and "ikea.com" in lowered and "/p/" in lowered:
            urls.append(url)
        elif brand == "muji" and "muji.com" in lowered and ("/store/" in lowered or "/product/" in lowered):
            urls.append(url)
    return _dedupe_strings(urls, max_items=8)


def _external_url_confidence(final_url: str | None) -> str:
    host = urlparse(final_url or "").netloc.lower()
    if any(
        domain in host
        for domain in (
            "smartstore.naver.com",
            "brand.naver.com",
            "shopping.naver.com",
            "ohou.se",
            "coupang.com",
            "11st.co.kr",
            "gmarket.co.kr",
            "auction.co.kr",
            "lotteon.com",
            "ssg.com",
        )
    ):
        return "medium_high"
    return "medium_high"


def try_parse_dimensions_from_external_urls(urls: list[str]) -> dict:
    warnings: list[str] = []
    candidates: list[dict] = []
    final_urls: list[str] = []

    for url in urls[:5]:
        fetch_result = _fetch_url_html_with_final_url(url, timeout=5)
        final_url = fetch_result.get("final_url") or url
        final_urls.append(final_url)

        if fetch_result.get("error"):
            warnings.append(f"external_fetch_failed:{url}")
            continue

        html = fetch_result.get("html")
        if not html:
            warnings.append(f"external_empty_html:{url}")
            continue

        text = _html_to_text(html)
        dimensions = _extract_dimensions_from_text(text)
        if not dimensions:
            warnings.append(f"external_dimension_parse_failed:{final_url}")
            continue

        candidates.append({
            "url": url,
            "final_url": final_url,
            "dimensions": dimensions,
            "text": text[:5000],
        })

    if not candidates:
        return {
            "match_confidence": "failed",
            "candidate": None,
            "final_urls": final_urls,
            "warnings": warnings,
        }

    distinct_dimensions = {
        (
            round(candidate["dimensions"]["width_cm"], 1),
            round(candidate["dimensions"]["depth_cm"], 1),
            round(candidate["dimensions"]["height_cm"], 1),
        )
        for candidate in candidates
    }
    if len(candidates) > 1 and len(distinct_dimensions) > 1:
        warnings.append("external_url_match_ambiguous")
        return {
            "match_confidence": "ambiguous",
            "candidate": None,
            "final_urls": final_urls,
            "warnings": warnings,
        }

    candidate = candidates[0]
    return {
        "match_confidence": _external_url_confidence(candidate.get("final_url")),
        "candidate": candidate,
        "final_urls": final_urls,
        "warnings": warnings + ["matched_from_external_listing_url"],
    }


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _search_web_results(queries: list[str], warnings: list[str]) -> list[dict]:
    """선택적으로 설정된 검색 API에서 title/snippet/url 후보를 가져온다."""
    results: list[dict] = []
    try:
        import requests
    except Exception as e:
        warnings.append(f"search_api_requests_unavailable:{e}")
        return results

    naver_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    naver_secret = (
        os.getenv("NAVER_CLIENT_SECRET", "").strip()
        or os.getenv("NAVER_SECRET", "").strip()
    )
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()

    if not any((naver_id and naver_secret, brave_key, serpapi_key)):
        warnings.append("search_api_not_configured")
        return results

    for query in queries[:5]:
        if naver_id and naver_secret:
            try:
                response = requests.get(
                    "https://openapi.naver.com/v1/search/webkr.json",
                    params={"query": query, "display": 5},
                    headers={
                        "X-Naver-Client-Id": naver_id,
                        "X-Naver-Client-Secret": naver_secret,
                    },
                    timeout=5,
                )
                response.raise_for_status()
                for item in response.json().get("items", []):
                    results.append({
                        "title": _strip_html(item.get("title", "")),
                        "snippet": _strip_html(item.get("description", "")),
                        "url": item.get("link", ""),
                        "query": query,
                        "source": "naver",
                    })
            except Exception as e:
                warnings.append(f"naver_search_failed:{query}:{e}")

        if brave_key:
            try:
                response = requests.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": 5},
                    headers={"X-Subscription-Token": brave_key},
                    timeout=5,
                )
                response.raise_for_status()
                for item in (response.json().get("web") or {}).get("results", []):
                    results.append({
                        "title": _strip_html(item.get("title", "")),
                        "snippet": _strip_html(item.get("description", "")),
                        "url": item.get("url", ""),
                        "query": query,
                        "source": "brave",
                    })
            except Exception as e:
                warnings.append(f"brave_search_failed:{query}:{e}")

        if serpapi_key:
            try:
                response = requests.get(
                    "https://serpapi.com/search.json",
                    params={"q": query, "api_key": serpapi_key, "num": 5},
                    timeout=5,
                )
                response.raise_for_status()
                for item in response.json().get("organic_results", []):
                    results.append({
                        "title": _strip_html(item.get("title", "")),
                        "snippet": _strip_html(item.get("snippet", "")),
                        "url": item.get("link", ""),
                        "query": query,
                        "source": "serpapi",
                    })
            except Exception as e:
                warnings.append(f"serpapi_search_failed:{query}:{e}")

    deduped: list[dict] = []
    seen: set[str] = set()
    for item in results:
        key = (item.get("url") or item.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:20]


def _candidate_keyword_score(text: str, model_query: str, title: str, description: str) -> dict:
    lowered = text.lower()
    brand_ok = any(token in lowered for token in ("ikea", "이케아", "muji", "무인양품"))

    model_terms = _model_terms_with_aliases([model_query]) if model_query else []
    _, text_models = _extract_brand_model_candidates(title, description)
    model_terms.extend(_model_terms_with_aliases(text_models))
    model_terms = _dedupe_strings(model_terms, max_items=8)
    model_ok = any(term and term.lower() in lowered for term in model_terms)

    furniture_terms = [
        "8 drawer",
        "8-drawer",
        "chest of 8 drawers",
        "8칸",
        "8단",
        "dresser",
        "chest of drawers",
        "drawer chest",
        "서랍장",
    ]
    furniture_ok = any(term in lowered for term in furniture_terms)
    drawer_count_ok = _drawer_count_matches(text, title, description)
    return {
        "brand_ok": brand_ok,
        "model_ok": model_ok,
        "furniture_ok": furniture_ok,
        "drawer_count_ok": drawer_count_ok,
        "strong": brand_ok and model_ok and furniture_ok and drawer_count_ok,
    }


def _score_search_result_candidate(candidate: dict, model_query: str, title: str, description: str) -> dict:
    text = f"{candidate.get('title', '')} {candidate.get('snippet', '')} {candidate.get('url', '')}"
    keyword_score = _candidate_keyword_score(text, model_query, title, description)
    score = 0
    if keyword_score["brand_ok"]:
        score += 3
    if keyword_score["model_ok"]:
        score += 4
    if keyword_score["furniture_ok"]:
        score += 2
    if not keyword_score["drawer_count_ok"]:
        score -= 8
    if candidate.get("dimensions"):
        score += 5
    host = urlparse(candidate.get("url", "")).netloc.lower()
    if "ikea.com" in host or "dimensions.com" in host:
        score += 2
    elif any(domain in host for domain in _EXTERNAL_PRODUCT_DOMAINS):
        score += 1
    return {**keyword_score, "score": score}


def _confidence_from_search_candidates(candidates: list[dict], warnings: list[str]) -> tuple[str, dict | None]:
    if not candidates:
        return "failed", None
    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    best = candidates[0]
    strong_candidates = [
        candidate for candidate in candidates
        if candidate.get("strong")
        and candidate.get("drawer_count_ok", True)
        and _has_any_dimension_axis(candidate.get("dimensions"))
    ]
    usable = strong_candidates or [
        candidate for candidate in candidates
        if candidate.get("brand_ok")
        and candidate.get("model_ok")
        and candidate.get("drawer_count_ok", True)
        and _has_any_dimension_axis(candidate.get("dimensions"))
    ]
    if not usable:
        return "failed", None

    official_strong = [
        candidate for candidate in usable
        if candidate.get("strong")
        and any(
            official_host in urlparse(candidate.get("url", "")).netloc.lower()
            for official_host in ("ikea.com", "muji.com")
        )
    ]
    if official_strong:
        usable = official_strong

    for idx, candidate in enumerate(usable):
        for other in usable[idx + 1:]:
            if _dimensions_conflict(candidate["dimensions"], other["dimensions"]):
                warnings.append("search_result_dimension_conflict")
                return "ambiguous", None

    best = sorted(usable, key=lambda item: item.get("score", 0), reverse=True)[0]
    return ("high" if best.get("strong") else "medium_high"), best


def try_parse_dimensions_from_search_results(
    queries: list[str],
    model_query: str,
    title: str,
    description: str,
    warnings: list[str],
) -> dict:
    search_results = _search_web_results(queries, warnings)
    candidates: list[dict] = []

    for result in search_results:
        result_text = f"{result.get('title', '')} {result.get('snippet', '')}"
        dimensions = _extract_any_dimensions_from_text(result_text)

        detail_dimensions = None
        url = result.get("url")
        if url:
            detail_text = _fetch_url_text(url, timeout=5)
            if detail_text:
                detail_dimensions = _extract_any_dimensions_from_text(detail_text)

        merged_dimensions = _merge_dimensions(dimensions, detail_dimensions)
        if not _has_any_dimension_axis(merged_dimensions):
            continue

        candidate = {
            **result,
            "dimensions": merged_dimensions,
        }
        candidate.update(_score_search_result_candidate(candidate, model_query, title, description))
        candidates.append(candidate)

    confidence, best = _confidence_from_search_candidates(candidates, warnings)
    return {
        "match_confidence": confidence,
        "candidate": best,
        "search_results": search_results,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# prior 검증
# ---------------------------------------------------------------------------

def validate_with_category_prior(
    furniture_type: str,
    dimensions: dict,
    prior_table: dict | None,
) -> dict:
    """치수를 카테고리 prior와 비교해 상태를 반환한다. 값 직접 수정 안 함."""
    skipped = {
        "prior_validation": {
            "width_cm": "skipped",
            "depth_cm": "skipped",
            "height_cm": "skipped",
        },
        "warnings": [],
        "confidence_penalty": 0,
    }

    if prior_table is None:
        return skipped

    category = _normalize_prior_category(furniture_type)
    if category not in prior_table:
        skipped["warnings"] = [f"prior_category_missing:{category}"]
        return skipped

    cat_prior = prior_table[category]
    axis_results: dict[str, str] = {}
    warnings: list[str] = []
    penalty = 0

    for axis in ("width_cm", "depth_cm", "height_cm"):
        val = _axis_value(dimensions, axis)
        if val is None or axis not in cat_prior:
            axis_results[axis] = "skipped"
            continue

        stats = cat_prior[axis]
        if stats.get("is_unreliable"):
            axis_results[axis] = "weak_prior"
            warnings.append(f"{axis} prior has small sample count; validation is weak")
            continue

        p05, p10, p90, p95 = stats["p05"], stats["p10"], stats["p90"], stats["p95"]

        if p10 <= val <= p90:
            axis_results[axis] = "normal"
        elif p05 <= val <= p95:
            axis_results[axis] = "warning"
            penalty = max(penalty, 1)
            warnings.append(f"{axis} outside typical range (p10–p90)")
        else:
            axis_results[axis] = "extreme"
            penalty = max(penalty, 2)
            warnings.append(f"{axis} extreme outlier (outside p05–p95)")

    return {
        "prior_validation": axis_results,
        "warnings": warnings,
        "confidence_penalty": penalty,
    }


# ---------------------------------------------------------------------------
# confidence 헬퍼
# ---------------------------------------------------------------------------

def _apply_prior_to_confidence(
    base_confidence: str,
    prior_result: dict,
    prior_table: dict | None,
) -> str:
    """prior penalty를 적용해 최종 confidence 문자열을 반환한다."""
    level = _CONF_LEVEL.get(base_confidence, 3)
    statuses = set((prior_result.get("prior_validation") or {}).values())

    # prior table 없으면 vision estimate는 최대 medium_low
    if prior_table is None and level > _CONF_LEVEL["medium_low"]:
        level = _CONF_LEVEL["medium_low"]

    if "extreme" in statuses:
        return "low"
    if "warning" in statuses:
        return "medium_low"

    penalty = prior_result.get("confidence_penalty", 0)
    level = max(_CONF_LEVEL["low"], level - penalty)
    return _LEVEL_CONF.get(level, "low")


# ---------------------------------------------------------------------------
# product match (stub — 실제 웹 검색 API 미지원)
# ---------------------------------------------------------------------------

def find_product_dimensions_from_web(
    title: str,
    description: str,
    furniture_type: str,
    product_candidate_hint: dict | None = None,
) -> dict:
    """IKEA/MUJI 한정 제품 치수를 공식/신뢰 후보 페이지에서 확인한다."""
    brand: str | None = None
    text = f"{title} {description}"
    for b in _KNOWN_BRANDS:
        if b.lower() in text.lower():
            brand = b
            break

    supported_brand = _select_product_match_brand(title, description, product_candidate_hint)
    query_candidates = _build_product_match_queries(
        title,
        description,
        furniture_type,
        product_candidate_hint,
    )
    external_product_urls = _extract_external_product_urls(title, description)
    model_query = _best_model_query(title, description, product_candidate_hint)
    warnings: list[str] = []
    external_result: dict | None = None
    external_final_url: str | None = None

    if external_product_urls:
        external_result = try_parse_dimensions_from_external_urls(external_product_urls)
        final_urls = external_result.get("final_urls") or []
        external_final_url = final_urls[0] if final_urls else None
        warnings.extend(external_result.get("warnings", []))
        external_candidate = external_result.get("candidate")

        if external_result.get("match_confidence") in {"medium_high", "high"} and external_candidate:
            dims = external_candidate["dimensions"]
            final_url = external_candidate.get("final_url") or external_candidate.get("url")
            return {
                "source": "product_match",
                "match_confidence": external_result["match_confidence"],
                "brand": None,
                "model": None,
                "model_query": model_query,
                "matched_product_title": None,
                "matched_url": final_url,
                "width_cm": dims.get("width_cm"),
                "depth_cm": dims.get("depth_cm"),
                "height_cm": dims.get("height_cm"),
                "raw_match": dims.get("raw_match"),
                "external_product_urls": external_product_urls,
                "external_final_url": final_url,
                "external_url_match_result": external_result.get("match_confidence"),
                "search_queries": query_candidates,
                "candidate_urls": [final_url] if final_url else external_product_urls,
                "warnings": warnings,
            }

        if external_result.get("match_confidence") == "ambiguous":
            return {
                "source": "product_match",
                "match_confidence": "ambiguous",
                "brand": None,
                "model": None,
                "model_query": model_query,
                "matched_product_title": None,
                "matched_url": None,
                "width_cm": None,
                "depth_cm": None,
                "height_cm": None,
                "raw_match": None,
                "external_product_urls": external_product_urls,
                "external_final_url": (external_result.get("final_urls") or [None])[0],
                "external_url_match_result": "ambiguous",
                "search_queries": query_candidates,
                "candidate_urls": external_result.get("final_urls") or external_product_urls,
                "warnings": warnings,
            }

    search_result_match = try_parse_dimensions_from_search_results(
        query_candidates,
        model_query,
        title,
        description,
        warnings,
    )
    search_candidate = search_result_match.get("candidate")
    if search_result_match.get("match_confidence") in {"high", "medium_high"} and search_candidate:
        dims = search_candidate["dimensions"]
        return {
            "source": "product_match",
            "match_confidence": search_result_match["match_confidence"],
            "brand": brand,
            "model": model_query,
            "model_query": model_query,
            "matched_product_title": search_candidate.get("title"),
            "matched_url": search_candidate.get("url"),
            "width_cm": dims.get("width_cm"),
            "depth_cm": dims.get("depth_cm"),
            "height_cm": dims.get("height_cm"),
            "raw_match": dims.get("raw_match"),
            "external_product_urls": external_product_urls,
            "external_final_url": external_final_url,
            "external_url_match_result": external_result.get("match_confidence")
                if external_result else None,
            "search_result_match_result": search_result_match.get("match_confidence"),
            "search_queries": query_candidates,
            "candidate_urls": _dedupe_strings(
                [result.get("url", "") for result in search_result_match.get("search_results", [])],
                max_items=20,
            ),
            "warnings": warnings,
        }

    if search_result_match.get("match_confidence") == "ambiguous":
        return {
            "source": "product_match",
            "match_confidence": "ambiguous",
            "brand": brand,
            "model": None,
            "model_query": model_query,
            "matched_product_title": None,
            "matched_url": None,
            "width_cm": None,
            "depth_cm": None,
            "height_cm": None,
            "raw_match": None,
            "external_product_urls": external_product_urls,
            "external_final_url": external_final_url,
            "external_url_match_result": external_result.get("match_confidence")
                if external_result else None,
            "search_result_match_result": "ambiguous",
            "search_queries": query_candidates,
            "candidate_urls": _dedupe_strings(
                [result.get("url", "") for result in search_result_match.get("search_results", [])],
                max_items=20,
            ),
            "warnings": warnings,
        }

    candidate_urls = (
        _build_candidate_urls_for_ikea(supported_brand, query_candidates, product_candidate_hint)
        if supported_brand else []
    )

    if supported_brand is None:
        warnings.append("product_match_supported_brand_missing")
        return {
            "source": "product_match",
            "match_confidence": "failed",
            "brand": brand,
            "model": None,
            "model_query": model_query,
            "matched_product_title": None,
            "matched_url": None,
            "width_cm": None,
            "depth_cm": None,
            "height_cm": None,
            "raw_match": None,
            "external_product_urls": external_product_urls,
            "external_final_url": external_final_url,
            "external_url_match_result": external_result.get("match_confidence")
                if external_result else None,
            "search_queries": query_candidates,
            "candidate_urls": candidate_urls,
            "warnings": warnings,
        }

    if not candidate_urls:
        warnings.append("product_match_candidate_urls_missing")
        return {
            "source": "product_match",
            "match_confidence": "failed",
            "brand": supported_brand.upper(),
            "model": None,
            "model_query": model_query,
            "matched_product_title": None,
            "matched_url": None,
            "width_cm": None,
            "depth_cm": None,
            "height_cm": None,
            "raw_match": None,
            "external_product_urls": external_product_urls,
            "external_final_url": external_final_url,
            "external_url_match_result": external_result.get("match_confidence")
                if external_result else None,
            "search_queries": query_candidates,
            "candidate_urls": candidate_urls,
            "warnings": warnings,
        }

    search_page_candidates: list[dict] = []
    detail_page_candidates: list[dict] = []
    detail_urls: list[str] = []

    for search_url in candidate_urls[:10]:
        search_html = _fetch_url_html(search_url, timeout=5)
        if not search_html:
            warnings.append(f"fetch_failed:{search_url}")
            continue

        extracted_links = _extract_candidate_links(search_html, search_url, supported_brand)
        detail_urls.extend(extracted_links)

        search_text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", search_html)
        search_text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", search_text)
        search_text = unescape(re.sub(r"(?s)<[^>]+>", " ", search_text))
        search_text = re.sub(r"\s+", " ", search_text).strip()
        dimensions = _extract_dimensions_from_text(search_text)
        if dimensions:
            candidate = {
                "url": search_url,
                "title": title,
                "text": search_text[:5000],
                "dimensions": dimensions,
                "page_kind": "search",
            }
            score_info = _score_product_candidate(candidate, supported_brand, model_query)
            candidate.update(score_info)
            search_page_candidates.append(candidate)

    detail_urls = _dedupe_strings(detail_urls, max_items=12)
    for detail_url in detail_urls:
        detail_text = _fetch_url_text(detail_url, timeout=5)
        if not detail_text:
            warnings.append(f"detail_fetch_failed:{detail_url}")
            continue

        dimensions = _extract_dimensions_from_text(detail_text)
        if not dimensions:
            warnings.append(f"detail_dimension_parse_failed:{detail_url}")
            continue

        candidate = {
            "url": detail_url,
            "title": title,
            "text": detail_text[:5000],
            "dimensions": dimensions,
            "page_kind": "detail",
        }
        score_info = _score_product_candidate(candidate, supported_brand, model_query)
        candidate.update(score_info)
        detail_page_candidates.append(candidate)

    candidate_urls = _dedupe_strings(candidate_urls + detail_urls, max_items=24)
    scored_candidates = detail_page_candidates or search_page_candidates

    if not scored_candidates:
        warnings.append("product_match_no_verified_dimensions")
        return {
            "source": "product_match",
            "match_confidence": "failed",
            "brand": supported_brand.upper(),
            "model": None,
            "model_query": model_query,
            "matched_product_title": None,
            "matched_url": None,
            "width_cm": None,
            "depth_cm": None,
            "height_cm": None,
            "raw_match": None,
            "external_product_urls": external_product_urls,
            "external_final_url": external_final_url,
            "external_url_match_result": external_result.get("match_confidence")
                if external_result else None,
            "search_queries": query_candidates,
            "candidate_urls": candidate_urls,
            "warnings": warnings,
        }

    scored_candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    best = scored_candidates[0]
    dims = best["dimensions"]

    tied_candidates = [
        candidate for candidate in scored_candidates
        if candidate.get("score") == best.get("score")
    ]
    distinct_tied_dimensions = {
        (
            round(candidate["dimensions"]["width_cm"], 1),
            round(candidate["dimensions"]["depth_cm"], 1),
            round(candidate["dimensions"]["height_cm"], 1),
        )
        for candidate in tied_candidates
    }
    if dims.get("ambiguous") or len(distinct_tied_dimensions) > 1:
        warnings.append("product_match_ambiguous")
        match_confidence = "ambiguous"
    elif best.get("is_official") and best.get("brand_ok") and best.get("model_matches", 0) > 0:
        match_confidence = "high"
    elif best.get("brand_ok") and best.get("model_matches", 0) > 0:
        match_confidence = "medium_high"
    else:
        warnings.append("product_match_brand_or_model_not_confirmed")
        match_confidence = "failed"

    return {
        "source": "product_match",
        "match_confidence": match_confidence,
        "brand": supported_brand.upper(),
        "model": model_query if best.get("model_matches", 0) > 0 else None,
        "model_query": model_query,
        "matched_product_title": model_query if match_confidence in {"high", "medium_high"} else None,
        "matched_url": best.get("url") if match_confidence in {"high", "medium_high"} else None,
        "width_cm": dims.get("width_cm") if match_confidence in {"high", "medium_high"} else None,
        "depth_cm": dims.get("depth_cm") if match_confidence in {"high", "medium_high"} else None,
        "height_cm": dims.get("height_cm") if match_confidence in {"high", "medium_high"} else None,
        "raw_match": dims.get("raw_match") if match_confidence in {"high", "medium_high"} else None,
        "external_product_urls": external_product_urls,
        "external_final_url": external_final_url,
        "external_url_match_result": external_result.get("match_confidence")
            if external_result else None,
        "search_queries": query_candidates,
        "candidate_urls": candidate_urls,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# DimensionEstimatorService
# ---------------------------------------------------------------------------

class DimensionEstimatorService:
    def estimate_dimensions(
        self,
        measurement_image_path: Path,
        title: str,
        description: str,
        furniture_type: str,
        listing_dims: dict | None,
        product_candidate_hint: dict | None = None,
    ) -> dict:
        """치수 추정: listing_text → product_match → vision_estimate_v2 우선순위 체인."""
        completeness = _classify_listing_dims(listing_dims)
        base_warnings: list[str] = []

        # ------------------------------------------------------------------
        # A. listing complete (width + depth + height 모두 있음)
        # ------------------------------------------------------------------
        if completeness == "complete":
            is_approx = bool(listing_dims.get("approximate", False))  # type: ignore[union-attr]
            return {
                "width_cm": listing_dims["width_cm"],  # type: ignore[index]
                "depth_cm": listing_dims["depth_cm"],  # type: ignore[index]
                "height_cm": listing_dims["height_cm"],  # type: ignore[index]
                "source": "listing_text",
                "confidence": "high",
                "approximate": is_approx,
                "pattern": listing_dims.get("pattern"),  # type: ignore[union-attr]
                "raw_match": listing_dims.get("raw_match"),  # type: ignore[union-attr]
                "reasoning": (
                    "Dimensions extracted from listing text (approximate)."
                    if is_approx else
                    "Dimensions extracted directly from listing text."
                ),
                "warnings": [],
                "dimension_source_priority_used": "listing_text",
                "listing_dimension_completeness": "complete",
                "product_match_result": None,
                "prior_validation": None,
                "axis_confidence": {
                    "width_cm": "high",
                    "depth_cm": "high",
                    "height_cm": "high",
                },
                "needs_user_confirmation": False,
            }

        # ------------------------------------------------------------------
        # B. listing partial (1~2개만 있음)
        # ------------------------------------------------------------------
        if completeness == "partial":
            return {
                "width_cm": listing_dims.get("width_cm"),  # type: ignore[union-attr]
                "depth_cm": listing_dims.get("depth_cm"),  # type: ignore[union-attr]
                "height_cm": listing_dims.get("height_cm"),  # type: ignore[union-attr]
                "source": "listing_text",
                "confidence": "high",
                "approximate": bool(listing_dims.get("approximate", False)),  # type: ignore[union-attr]
                "pattern": listing_dims.get("pattern"),  # type: ignore[union-attr]
                "raw_match": listing_dims.get("raw_match"),  # type: ignore[union-attr]
                "reasoning": "At least one dimension axis was extracted directly from listing text.",
                "warnings": [],
                "dimension_source_priority_used": "listing_text",
                "listing_dimension_completeness": "partial_listing_text",
                "product_match_result": None,
                "prior_validation": None,
                "axis_confidence": {
                    "width_cm": "high" if listing_dims.get("width_cm") is not None else "low",  # type: ignore[union-attr]
                    "depth_cm": "high" if listing_dims.get("depth_cm") is not None else "low",  # type: ignore[union-attr]
                    "height_cm": "high" if listing_dims.get("height_cm") is not None else "low",  # type: ignore[union-attr]
                },
                "needs_user_confirmation": False,
            }

        # ------------------------------------------------------------------
        # C. product_match 시도
        # ------------------------------------------------------------------
        try:
            pm_result = find_product_dimensions_from_web(
                title,
                description,
                furniture_type,
                product_candidate_hint=product_candidate_hint,
            )
        except Exception as e:
            logger.warning("product_match failed, falling back to vision: %s", e)
            pm_result = {
                "source": "product_match",
                "match_confidence": "failed",
                "warnings": ["product_match_exception"],
            }

        pm_conf = pm_result.get("match_confidence", "failed")
        pm_has_any_axis = (
            pm_result.get("width_cm") is not None
            or pm_result.get("depth_cm") is not None
            or pm_result.get("height_cm") is not None
        )

        if pm_conf in ("high", "medium_high") and pm_has_any_axis:
            confidence = "high" if pm_conf == "high" else "medium_high"
            return {
                "width_cm": pm_result.get("width_cm"),
                "depth_cm": pm_result.get("depth_cm"),
                "height_cm": pm_result.get("height_cm"),
                "source": "product_match",
                "confidence": confidence,
                "approximate": False,
                "pattern": None,
                "raw_match": pm_result.get("raw_match"),
                "reasoning": f"Matched product: {pm_result.get('matched_product_title')}",
                "warnings": pm_result.get("warnings", []),
                "dimension_source_priority_used": "product_match",
                "listing_dimension_completeness": "missing",
                "product_match_result": pm_result,
                "prior_validation": None,
                "axis_confidence": {
                    "width_cm": confidence if pm_result.get("width_cm") is not None else "low",
                    "depth_cm": confidence if pm_result.get("depth_cm") is not None else "low",
                    "height_cm": confidence if pm_result.get("height_cm") is not None else "low",
                },
                "needs_user_confirmation": False,
            }

        # product_match 실패 시 warnings 누적
        base_warnings.extend(pm_result.get("warnings", []))

        # ------------------------------------------------------------------
        # D. vision estimate
        # ------------------------------------------------------------------
        dims = _core.measure_dimensions(
            measurement_image_path,
            title,
            description,
            furniture_type=furniture_type,
        )
        dims["source"] = "vision_estimate_v2"

        # axis_confidence 기본값: 값이 있으면 "medium", 없으면 "low"
        axis_confidence = {
            axis: ("medium" if dims.get(axis) is not None else "low")
            for axis in ("width_cm", "depth_cm", "height_cm")
        }

        # ------------------------------------------------------------------
        # E. prior 검증 및 confidence 조정
        # ------------------------------------------------------------------
        prior_table = load_ikea_prior_table()
        prior_result = validate_with_category_prior(furniture_type, dims, prior_table)

        if prior_table is None:
            base_warnings.append("prior_table_missing")

        base_conf = dims.get("confidence", "medium")
        final_confidence = _apply_prior_to_confidence(base_conf, prior_result, prior_table)

        # extreme axis는 axis_confidence 낮춤
        for axis, status in prior_result["prior_validation"].items():
            if status == "extreme":
                axis_confidence[axis] = "low"
            elif status == "warning" and axis_confidence[axis] != "low":
                axis_confidence[axis] = "medium_low"

        all_warnings = (
            base_warnings
            + dims.get("warnings", [])
            + prior_result.get("warnings", [])
        )

        return {
            "width_cm": dims.get("width_cm"),
            "depth_cm": dims.get("depth_cm"),
            "height_cm": dims.get("height_cm"),
            "source": "vision_estimate_v2",
            "confidence": final_confidence,
            "approximate": dims.get("approximate", True),
            "pattern": dims.get("pattern"),
            "raw_match": dims.get("raw_match"),
            "reasoning": dims.get("reasoning", ""),
            "warnings": all_warnings,
            "dimension_source_priority_used": "vision_estimate_v2",
            "listing_dimension_completeness": "missing",
            "product_match_result": pm_result,
            "prior_validation": prior_result["prior_validation"],
            "axis_confidence": axis_confidence,
            "needs_user_confirmation": True,
        }

    async def estimate(self, image_path: str) -> dict:
        """기존 인터페이스 호환용 — w/h/d 키 반환."""
        dims = _core.measure_dimensions(Path(image_path), "", "", furniture_type="unknown")
        return {
            "w": dims.get("width_cm"),
            "h": dims.get("height_cm"),
            "d": dims.get("depth_cm"),
        }
