"""backend 서비스 레이어가 공유하는 유틸리티 함수 모음.

dahoo_fri/app.py에서 Flask/라우트를 제거하고 순수 로직만 추출했습니다.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path

import requests as http_requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

VISION_MODEL = "gpt-4.1-mini"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def load_runtime_environment() -> None:
    """필요한 .env 파일들을 로드합니다."""
    try:
        from dotenv import load_dotenv
        _backend_dir = Path(__file__).resolve().parent
        load_dotenv(_backend_dir / ".env")
        load_dotenv()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# OpenAI 클라이언트
# ---------------------------------------------------------------------------

_openai_client = None
_openai_unavailable_reason = None


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI()
    return _openai_client


def _openai_error_reason(exc: Exception) -> str | None:
    msg = str(exc).lower()
    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return "openai_insufficient_quota"
    if "missing credentials" in msg or "openai_api_key" in msg:
        return "openai_missing_credentials"
    if "rate_limit" in msg or "rate limit" in msg:
        return "openai_rate_limited"
    return None


def _mark_openai_unavailable(exc: Exception) -> str | None:
    global _openai_unavailable_reason
    reason = _openai_error_reason(exc)
    if reason:
        _openai_unavailable_reason = reason
        logger.warning("OpenAI unavailable; using local fallbacks: %s", reason)
    return reason


def _openai_skip_reason() -> str | None:
    if _openai_unavailable_reason:
        return _openai_unavailable_reason
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENAI_ADMIN_KEY"):
        return "openai_missing_credentials"
    return None


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


# ---------------------------------------------------------------------------
# 스크래핑
# ---------------------------------------------------------------------------

def identify_platform(url: str) -> str | None:
    if "daangn.com" in url:
        return "daangn"
    if "joongna.com" in url:
        return "joongna"
    return None


def scrape_daangn(url: str) -> dict:
    resp = http_requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {"title": "", "description": "", "price": "", "images": []}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get("@type") == "Product":
            result["title"] = data.get("name", "")
            result["description"] = data.get("description", "")
            offers = data.get("offers", {})
            price = offers.get("price", "")
            if price:
                result["price"] = f"{int(float(price)):,}원"

    seen = set()
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "karroter" in src and "1440x1440" in src and src not in seen:
            seen.add(src)
            result["images"].append(src)

    if not result["images"]:
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            result["images"].append(og_img["content"])

    if not result["title"]:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            result["title"] = og_title.get("content", "")
    if not result["description"]:
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            result["description"] = og_desc.get("content", "")

    return result


def scrape_joongna(url: str) -> dict:
    resp = http_requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {"title": "", "description": "", "price": "", "images": []}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get("@type") == "Product":
            result["title"] = data.get("name", "")
            result["description"] = data.get("description", "")
            offers = data.get("offers", {})
            if isinstance(offers, list) and offers:
                offers = offers[0]
            price = offers.get("price", "")
            if price:
                result["price"] = f"{int(float(price)):,}원"

    if not result["title"]:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            result["title"] = og_title.get("content", "")
    if not result["description"]:
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            result["description"] = og_desc.get("content", "")

    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        result["images"].append(og_img["content"])

    seen = set(result["images"])
    for img in soup.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if src and ("joongna" in src or "joongnara" in src) and src not in seen:
            if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                seen.add(src)
                result["images"].append(src)

    return result


def download_image(url: str, output_path: Path) -> Path:
    resp = http_requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)
    return output_path


# ---------------------------------------------------------------------------
# 이미지 선택 (GPT Vision)
# ---------------------------------------------------------------------------

def select_best_image_gpt(title: str, description: str, image_urls: list[str]) -> int:
    if len(image_urls) < 2:
        return 0
    if _openai_skip_reason():
        return 0

    client = get_openai_client()
    image_content = []
    for i, url in enumerate(image_urls):
        image_content.append({"type": "text", "text": f"[Image {i}]"})
        image_content.append({"type": "image_url", "image_url": {"url": url, "detail": "low"}})

    prompt = (
        f"Title: {title}\nDescription: {description[:500]}\n\n"
        f"Pick the image that best shows the full furniture item. "
        f"Reply with only the image number (0-{len(image_urls)-1})."
    )

    try:
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + image_content}],
            max_tokens=10,
        )
        answer = resp.choices[0].message.content.strip()
        idx = int(re.search(r"\d+", answer).group())
        if 0 <= idx < len(image_urls):
            return idx
    except Exception as e:
        _mark_openai_unavailable(e)
    return 0


# ---------------------------------------------------------------------------
# 가구 종류 분류
# ---------------------------------------------------------------------------

VALID_FURNITURE_TYPES = [
    "chair", "desk", "table", "sofa", "cabinet", "shelf", "bed", "dresser", "unknown",
]

_KO_FURNITURE_KEYWORDS = {
    "chair":   ["의자", "체어", "chair", "스툴", "stool", "좌석"],
    "desk":    ["책상", "데스크", "desk", "학생책상", "컴퓨터책상", "서재"],
    "table":   ["테이블", "table", "식탁", "탁자", "커피테이블", "사이드테이블", "dining"],
    "sofa":    ["소파", "sofa", "couch", "카우치", "쇼파", "거실소파"],
    "cabinet": ["캐비닛", "cabinet", "서랍장", "수납장", "옷장", "wardrobe", "찬장", "장롱"],
    "shelf":   ["선반", "shelf", "책장", "bookshelf", "bookcase", "진열장", "shelving"],
    "bed":     ["침대", "bed", "매트리스", "mattress", "프레임침대", "벙커침대"],
    "dresser": ["화장대", "dresser", "서랍", "drawer", "콘솔", "console"],
}


def classify_furniture_from_listing(title: str, description: str) -> dict:
    text = f"{title} {description}".lower()
    scores: dict[str, int] = {}
    evidence: dict[str, list] = {}

    for ftype, keywords in _KO_FURNITURE_KEYWORDS.items():
        matched = [kw for kw in keywords if kw.lower() in text]
        if matched:
            title_lower = title.lower()
            title_matches = [kw for kw in matched if kw.lower() in title_lower]
            scores[ftype] = len(matched) + len(title_matches)
            evidence[ftype] = matched

    if not scores:
        return {"furniture_type": "unknown", "confidence": "low", "evidence": "no keywords matched"}

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    confidence = "high" if best_score >= 3 else ("medium" if best_score >= 2 else "low")

    return {
        "furniture_type": best_type,
        "confidence": confidence,
        "evidence": f"matched: {evidence[best_type]}",
    }


def classify_furniture_from_image(image_path: Path, title: str = "", description: str = "") -> dict:
    skip_reason = _openai_skip_reason()
    if skip_reason:
        return {"furniture_type": "unknown", "confidence": "low", "evidence": skip_reason}

    client = get_openai_client()
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    context = "What type of furniture is the main object in this image?\n"
    if title:
        context += f"Listing title: {title}\n"
    valid = ", ".join(VALID_FURNITURE_TYPES)
    context += (
        f"\nRespond with ONLY a JSON object: "
        f'{{"furniture_type": "<one of: {valid}>", "confidence": "high|medium|low"}}'
    )

    try:
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": context},
                {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
            ]}],
            max_tokens=60,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if match:
            parsed = json.loads(match.group(0))
            ftype = parsed.get("furniture_type", "unknown").lower()
            if ftype not in VALID_FURNITURE_TYPES:
                ftype = "unknown"
            return {
                "furniture_type": ftype,
                "confidence": parsed.get("confidence", "medium"),
                "evidence": "gpt_vision",
            }
    except Exception as e:
        _mark_openai_unavailable(e)
        logger.warning("Image furniture classification failed: %s", e)

    return {"furniture_type": "unknown", "confidence": "low", "evidence": "classification_failed"}


def reconcile_furniture_type(listing_type: dict, image_type: dict) -> dict:
    lt = listing_type["furniture_type"]
    it = image_type["furniture_type"]
    lc = listing_type["confidence"]
    ic = image_type["confidence"]

    if lt == it and lt != "unknown":
        return {"furniture_type": lt, "confidence": "high",
                "listing": lt, "image": it, "warning": None}

    if lc == "high" and lt != "unknown" and (ic in ("low", "medium") or it == "unknown"):
        return {"furniture_type": lt, "confidence": "high",
                "listing": lt, "image": it, "warning": None}

    if lc == "high" and lt != "unknown" and it != lt:
        warning = f"listing='{lt}' vs image='{it}' — using listing classification for target furniture"
        return {"furniture_type": lt, "confidence": "high",
                "listing": lt, "image": it, "warning": warning}

    if ic == "high" and it != "unknown" and (lt == "unknown" or lc == "low"):
        return {"furniture_type": it, "confidence": "high",
                "listing": lt, "image": it, "warning": None}

    if lt != "unknown" and it != "unknown" and lt != it:
        warning = f"listing='{lt}' vs image='{it}' — using image classification"
        return {"furniture_type": it, "confidence": "medium",
                "listing": lt, "image": it, "warning": warning}

    final = lt if lt != "unknown" else it
    if final == "unknown":
        return {"furniture_type": "unknown", "confidence": "low",
                "listing": lt, "image": it, "warning": None}

    return {"furniture_type": final, "confidence": "medium",
            "listing": lt, "image": it, "warning": None}


# ---------------------------------------------------------------------------
# 세그멘터 (SAM3 / GroundingDINO) — lazy singleton
# ---------------------------------------------------------------------------

_segmenter = None
_segmenter_device = "cpu"


def get_segmenter(device: str = "cpu"):
    global _segmenter, _segmenter_device
    if _segmenter is None or device != _segmenter_device:
        # SEGMENTATION_PROJECT_DIR가 sys.path에 추가돼 있어야 합니다 (core.py에서 처리).
        from segmentation import create_segmenter  # noqa: PLC0415
        _segmenter = create_segmenter(device=device, prefer="grounded_sam")
        _segmenter_device = device
        logger.info("Segmenter loaded: %s", type(_segmenter).__name__)
    return _segmenter


def _get_gsam(segmenter):
    if hasattr(segmenter, "primary"):
        return segmenter.primary
    return segmenter


# ---------------------------------------------------------------------------
# 치수 추정 (GPT Vision)
# ---------------------------------------------------------------------------

DIMENSION_PROMPT = """You estimate furniture dimensions from a single image.

Return only JSON with this exact shape:
{
  "width_cm": number,
  "depth_cm": number,
  "height_cm": number,
  "confidence": "low" | "medium" | "high",
  "reasoning": string
}

Definitions:
- width_cm: left-to-right horizontal size (가로)
- depth_cm: front-to-back size (세로/깊이)
- height_cm: floor-to-top vertical size (높이)

Use visual cues, category knowledge, and common real-world furniture sizes.
Give your best numeric estimate in centimeters.
"""

_DEFAULT_DIMENSIONS_BY_TYPE = {
    "chair":   {"width_cm": 50,  "depth_cm": 55,  "height_cm": 85},
    "desk":    {"width_cm": 120, "depth_cm": 60,  "height_cm": 75},
    "table":   {"width_cm": 120, "depth_cm": 75,  "height_cm": 74},
    "sofa":    {"width_cm": 180, "depth_cm": 85,  "height_cm": 80},
    "cabinet": {"width_cm": 80,  "depth_cm": 45,  "height_cm": 120},
    "shelf":   {"width_cm": 80,  "depth_cm": 30,  "height_cm": 160},
    "bed":     {"width_cm": 200, "depth_cm": 100, "height_cm": 50},
    "dresser": {"width_cm": 90,  "depth_cm": 45,  "height_cm": 140},
    "unknown": {"width_cm": None, "depth_cm": None, "height_cm": None},
}


def _local_dimension_fallback(
    title: str = "",
    description: str = "",
    furniture_type: str = "unknown",
    reason: str = "openai_unavailable",
) -> dict:
    ftype = furniture_type if furniture_type in _DEFAULT_DIMENSIONS_BY_TYPE else "unknown"
    if ftype == "unknown":
        listing_guess = classify_furniture_from_listing(title, description)
        ftype = listing_guess.get("furniture_type", "unknown")
    dims = dict(_DEFAULT_DIMENSIONS_BY_TYPE.get(ftype, _DEFAULT_DIMENSIONS_BY_TYPE["unknown"]))
    return {
        **dims,
        "confidence": "low",
        "source": "local_category_fallback",
        "furniture_type": ftype,
        "warnings": [reason, "dimension_local_fallback_used"],
        "reasoning": (
            f"OpenAI Vision unavailable — category default for '{ftype}'. "
            "Use real measured dimensions for AR scale or production modeling."
        ),
    }


def measure_dimensions(
    image_path: Path,
    title: str = "",
    description: str = "",
    furniture_type: str = "unknown",
) -> dict:
    skip_reason = _openai_skip_reason()
    if skip_reason:
        return _local_dimension_fallback(title, description, furniture_type, skip_reason)

    client = get_openai_client()
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    context = ""
    if title:
        context += f"Product title: {title}\n"
    if description:
        context += f"Description: {description[:300]}\n"
    context += "Estimate this furniture's width, depth, and height in centimeters."

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": DIMENSION_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": context},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ]},
            ],
            max_tokens=500,
        )
    except Exception as e:
        reason = _mark_openai_unavailable(e) or "openai_dimension_call_failed"
        logger.warning("Dimension measurement fell back to local defaults: %s", e)
        return _local_dimension_fallback(title, description, furniture_type, reason)

    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if match:
            parsed = json.loads(match.group(0))
        else:
            raise ValueError(f"Could not parse dimension response: {raw}")

    parsed.setdefault("source", "openai_vision")
    parsed.setdefault("warnings", [])
    return parsed
