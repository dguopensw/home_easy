"""Furniture dimension pipeline: Daangn URL -> preprocess -> measure -> output PNG + dimensions.

Run: python pipeline/app.py
Open: http://localhost:5001
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

import requests as http_requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
OUTPUT_DIR = PIPELINE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Add nanobanana to path for segmentation reuse
sys.path.insert(0, str(PROJECT_ROOT / "nanobanana_ratio_project"))

app = Flask(__name__, static_folder="static")
app.json.ensure_ascii = False
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_runtime_environment() -> None:
    """Load local .env files needed by both Flask and FastAPI entrypoints."""
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "nanobanana_ratio_project" / ".env")
    load_dotenv(PROJECT_ROOT / "furniture_dimension_eval" / ".env")
    load_dotenv(PIPELINE_DIR / ".env")
    load_dotenv()

# ---------------------------------------------------------------------------
# OpenAI client (lazy init)
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
    """Classify OpenAI failures that should trigger local fallback mode."""
    msg = str(exc).lower()
    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return "openai_insufficient_quota"
    if "missing credentials" in msg or "openai_api_key" in msg:
        return "openai_missing_credentials"
    if "rate_limit" in msg or "rate limit" in msg:
        return "openai_rate_limited"
    return None


def _mark_openai_unavailable(exc: Exception) -> str | None:
    """Remember quota/credential failures so later steps avoid repeated API calls."""
    global _openai_unavailable_reason
    reason = _openai_error_reason(exc)
    if reason:
        _openai_unavailable_reason = reason
        logger.warning("OpenAI unavailable; using local fallbacks where possible: %s", reason)
    return reason


def _openai_skip_reason() -> str | None:
    if _openai_unavailable_reason:
        return _openai_unavailable_reason
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENAI_ADMIN_KEY"):
        return "openai_missing_credentials"
    return None


# ---------------------------------------------------------------------------
# Stage 1: Scrape Daangn / Joongna URL
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


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


VISION_MODEL = "gpt-4.1-mini"


def select_best_image_gpt(title: str, description: str, image_urls: list[str]) -> int:
    """Use GPT vision to pick the best representative furniture image."""
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
        pass
    return 0


def download_image(url: str, output_path: Path) -> Path:
    resp = http_requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)
    return output_path


# ---------------------------------------------------------------------------
# Segmenter singleton (heavy model, load once)
# ---------------------------------------------------------------------------

_segmenter = None
_segmenter_device = "cpu"


def get_segmenter(device: str = "cpu"):
    """Lazy-load GroundingDINO + SAM segmenter (singleton)."""
    global _segmenter, _segmenter_device
    if _segmenter is None or device != _segmenter_device:
        os.environ.setdefault(
            "SAM_CHECKPOINT",
            str(PROJECT_ROOT / "nanobanana_ratio_project" / "checkpoints" / "sam_vit_b_01ec64.pth"),
        )
        from segmentation import create_segmenter
        _segmenter = create_segmenter(device=device, prefer="grounded_sam")
        _segmenter_device = device
        logger.info("Segmenter loaded: %s", type(_segmenter).__name__)
    return _segmenter


# ---------------------------------------------------------------------------
# Stage 1.5: Furniture type classification (category-aware pipeline)
# ---------------------------------------------------------------------------

VALID_FURNITURE_TYPES = [
    "chair", "desk", "table", "sofa", "cabinet", "shelf", "bed", "dresser", "unknown",
]

# Korean keyword → type mapping for listing-based classification
_KO_FURNITURE_KEYWORDS = {
    "chair": ["의자", "체어", "chair", "스툴", "stool", "좌석"],
    "desk": ["책상", "데스크", "desk", "학생책상", "컴퓨터책상", "서재"],
    "table": ["테이블", "table", "식탁", "탁자", "커피테이블", "사이드테이블", "dining"],
    "sofa": ["소파", "sofa", "couch", "카우치", "쇼파", "거실소파"],
    "cabinet": ["캐비닛", "cabinet", "서랍장", "수납장", "옷장", "wardrobe", "찬장", "장롱"],
    "shelf": ["선반", "shelf", "책장", "bookshelf", "bookcase", "진열장", "shelving"],
    "bed": ["침대", "bed", "매트리스", "mattress", "프레임침대", "벙커침대"],
    "dresser": ["화장대", "dresser", "서랍", "drawer", "콘솔", "console"],
}


def classify_furniture_from_listing(title: str, description: str) -> dict:
    """Classify furniture type from listing title and description text."""
    text = f"{title} {description}".lower()
    scores = {}
    evidence = {}

    for ftype, keywords in _KO_FURNITURE_KEYWORDS.items():
        matched = [kw for kw in keywords if kw.lower() in text]
        if matched:
            # Title matches count double
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
    """Use GPT Vision to classify the main furniture object in the image."""
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
    """Reconcile listing-based and image-based furniture classifications."""
    lt = listing_type["furniture_type"]
    it = image_type["furniture_type"]
    lc = listing_type["confidence"]
    ic = image_type["confidence"]
    warning = None

    # Both agree
    if lt == it and lt != "unknown":
        return {"furniture_type": lt, "confidence": "high",
                "listing": lt, "image": it, "warning": None}

    # Listing high confidence, image low/unknown
    if lc == "high" and lt != "unknown" and (ic in ("low", "medium") or it == "unknown"):
        return {"furniture_type": lt, "confidence": "high",
                "listing": lt, "image": it, "warning": None}

    # The listing text describes the object being sold. When it is explicit,
    # use it to anchor DINO prompts even if the image classifier is distracted
    # by a doll, cushion, book, or other object near the furniture.
    if lc == "high" and lt != "unknown" and it != lt:
        warning = f"listing='{lt}' vs image='{it}' — using listing classification for target furniture"
        return {"furniture_type": lt, "confidence": "high",
                "listing": lt, "image": it, "warning": warning}

    # Image high confidence, listing vague/unknown
    if ic == "high" and it != "unknown" and (lt == "unknown" or lc == "low"):
        return {"furniture_type": it, "confidence": "high",
                "listing": lt, "image": it, "warning": None}

    # Both non-unknown but conflict
    if lt != "unknown" and it != "unknown" and lt != it:
        # Prefer image (visual ground truth), but warn
        warning = f"listing='{lt}' vs image='{it}' — using image classification"
        return {"furniture_type": it, "confidence": "medium",
                "listing": lt, "image": it, "warning": warning}

    # One is known, other unknown
    final = lt if lt != "unknown" else it
    if final == "unknown":
        return {"furniture_type": "unknown", "confidence": "low",
                "listing": lt, "image": it, "warning": None}

    return {"furniture_type": final, "confidence": "medium",
            "listing": lt, "image": it, "warning": None}


# ---------------------------------------------------------------------------
# Stage 2: Dual-output furniture extraction (category-aware)
# ---------------------------------------------------------------------------

# Model fallback chain for GPT cutout (env-configurable)
DEFAULT_GPT_IMAGE_MODELS = "gpt-image-1"

PART_PROMPTS_BY_TYPE = {
    "chair": ["chair", "chair seat", "chair backrest", "chair legs", "chair frame"],
    "desk": ["desk", "desktop", "desk legs", "desk frame"],
    "table": ["table", "tabletop", "table legs", "table frame"],
    "sofa": ["sofa", "sofa seat", "sofa backrest", "sofa armrest", "sofa legs"],
    "cabinet": ["cabinet", "cabinet body", "cabinet door", "cabinet legs"],
    "shelf": ["shelf", "shelving unit", "shelf boards", "shelf frame"],
    "bed": ["bed", "bed frame", "mattress", "bed legs"],
    "dresser": ["dresser", "drawer cabinet", "drawer front", "dresser body"],
}
FALLBACK_PROMPTS = ["main furniture object", "furniture object"]


def _get_part_prompts(furniture_type: str) -> list[str]:
    """Get SAM part prompts for the detected furniture type."""
    return PART_PROMPTS_BY_TYPE.get(furniture_type, FALLBACK_PROMPTS)


RATIO_LOCK_TEXT = """
Ratio and geometry preservation requirements:
- Keep the exact original width-to-height ratio of the object.
- Keep the same relative proportions between seat/back/legs/frame/surface parts.
- Do not make the object taller, wider, thinner, shorter, more upright, or more symmetrical.
- Do not change the apparent camera angle or perspective.
- Do not normalize the object into a catalog-style product photo.
- Do not change leg length, leg spacing, tabletop thickness, seat thickness, backrest height, frame thickness, or visible part proportions.
- This is background removal only. The furniture geometry must remain visually aligned with the input image.
""".strip()


def _build_edit_prompt(furniture_type: str) -> str:
    """Build category-aware GPT edit prompt with strong ratio lock."""
    target = furniture_type if furniture_type != "unknown" else "main furniture object"
    return (
        f"Extract only the original {target} from the input image and remove "
        f"the surrounding background.\n\n"
        f"This is a faithful object cutout task, not a product redesign or product generation.\n\n"
        f"Preserve the exact original shape, perspective, proportions, visible "
        f"structure, legs, frame, surface, material, edges, and object silhouette "
        f"of the {target}.\n\n"
        f"{RATIO_LOCK_TEXT}\n\n"
        f"Do not generate a new object.\n"
        f"Do not redraw or replace the object.\n"
        f"Do not turn it into another furniture type.\n"
        f"Do not beautify, simplify, straighten, stretch, compress, crop, resize, "
        f"rotate, or recompose the furniture.\n\n"
        f"Output only the isolated original {target} on a transparent background."
    )


def _get_gsam(segmenter):
    """Extract the GroundedSamSegmenter from a possibly-wrapped HybridSegmenter."""
    if hasattr(segmenter, "primary"):
        return segmenter.primary
    return segmenter


def generate_faithful_cutout(image_path: Path, mask_path: Path, output_path: Path) -> dict:
    """Create RGBA transparent PNG using original pixels + SAM mask as alpha.

    This is faithful extraction: zero AI generation, original pixels only.
    """
    import cv2
    import numpy as np

    img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if img_bgr is None or mask is None:
        raise ValueError("Cannot read image or mask for faithful cutout")

    # Resize mask to match image if needed
    if img_bgr.shape[:2] != mask.shape[:2]:
        mask = cv2.resize(mask, (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

    # Soft edge: slight Gaussian blur on mask for anti-aliasing
    alpha = cv2.GaussianBlur(mask, (3, 3), 0)

    # BGR → BGRA with SAM mask as alpha
    bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), bgra)
    logger.info("Faithful cutout: original pixels + SAM alpha mask → RGBA PNG")
    return {"method": "sam_faithful_extraction", "warnings": []}


# ---------------------------------------------------------------------------
# Background Removal Models: BiRefNet + RMBG (faithful alpha matte)
# ---------------------------------------------------------------------------

_birefnet_model = None
_rmbg_model = None


def _get_birefnet():
    """Lazy-load BiRefNet model singleton."""
    global _birefnet_model
    if _birefnet_model is None:
        import torch
        from transformers import AutoModelForImageSegmentation
        logger.info("Loading BiRefNet model...")
        _birefnet_model = AutoModelForImageSegmentation.from_pretrained(
            "zhengpeng7/BiRefNet", trust_remote_code=True,
        )
        _birefnet_model.eval()
        if torch.cuda.is_available():
            _birefnet_model = _birefnet_model.cuda()
        elif torch.backends.mps.is_available():
            _birefnet_model = _birefnet_model.to("mps")
        logger.info("BiRefNet loaded")
    return _birefnet_model


def _get_rmbg():
    """Lazy-load RMBG-1.4 model singleton."""
    global _rmbg_model
    if _rmbg_model is None:
        import torch
        from transformers import AutoModelForImageSegmentation
        logger.info("Loading RMBG-1.4 model...")
        _rmbg_model = AutoModelForImageSegmentation.from_pretrained(
            "briaai/RMBG-1.4", trust_remote_code=True,
        )
        _rmbg_model.eval()
        if torch.cuda.is_available():
            _rmbg_model = _rmbg_model.cuda()
        elif torch.backends.mps.is_available():
            _rmbg_model = _rmbg_model.to("mps")
        logger.info("RMBG-1.4 loaded")
    return _rmbg_model


def _alpha_matte_cutout(model, image_path: Path, output_cutout: Path,
                         output_mask: Path, model_name: str) -> dict:
    """Run an alpha-matte background removal model (BiRefNet or RMBG).

    Preserves original RGB pixels; model output is used only as alpha channel.
    """
    import cv2
    import numpy as np
    import torch
    from PIL import Image as PILImage
    from torchvision import transforms

    img_pil = PILImage.open(image_path).convert("RGB")
    orig_w, orig_h = img_pil.size

    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    input_tensor = transform(img_pil).unsqueeze(0)
    param = next(model.parameters())
    device = param.device
    input_tensor = input_tensor.to(device=device, dtype=param.dtype)

    with torch.no_grad():
        result = model(input_tensor)

    # Extract prediction: BiRefNet returns list (last elem), RMBG returns tuple of lists
    if isinstance(result, (list, tuple)):
        if isinstance(result[0], list):
            # RMBG-1.4: result = (list_of_side_outputs, list_of_features)
            pred = result[0][0]
        elif isinstance(result[-1], torch.Tensor):
            # BiRefNet: list of tensors, last is finest
            pred = result[-1]
        else:
            pred = result[0]
    else:
        pred = result

    pred = pred.sigmoid()
    mask_1024 = pred[0].squeeze().cpu().numpy()

    # Resize mask back to original size
    mask_orig = np.array(PILImage.fromarray((mask_1024 * 255).astype(np.uint8)).resize(
        (orig_w, orig_h), PILImage.LANCZOS
    ))

    # Save binary mask
    output_mask.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_mask), mask_orig)

    # Build RGBA cutout: original pixels + model alpha
    img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img_bgr.shape[:2] != (orig_h, orig_w):
        mask_orig = cv2.resize(mask_orig, (img_bgr.shape[1], img_bgr.shape[0]),
                                interpolation=cv2.INTER_LINEAR)

    # Soft edge anti-aliasing
    alpha = cv2.GaussianBlur(mask_orig, (3, 3), 0)
    bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha

    cv2.imwrite(str(output_cutout), bgra)
    logger.info("%s cutout: original pixels + alpha matte → RGBA PNG", model_name)

    return {"method": f"{model_name}_alpha_matte", "warnings": []}


def generate_birefnet_cutout(image_path: Path, output_cutout: Path,
                              output_mask: Path) -> dict:
    """Use BiRefNet to generate soft alpha matte. Original pixels preserved."""
    try:
        model = _get_birefnet()
        return _alpha_matte_cutout(model, image_path, output_cutout,
                                    output_mask, "birefnet")
    except Exception as e:
        logger.warning("BiRefNet cutout failed: %s", e)
        return {"method": "birefnet_alpha_matte", "status": "failed",
                "warnings": [str(e)]}


def generate_rmbg_cutout(image_path: Path, output_cutout: Path,
                          output_mask: Path) -> dict:
    """Use RMBG-1.4 to generate alpha matte. Original pixels preserved."""
    try:
        model = _get_rmbg()
        return _alpha_matte_cutout(model, image_path, output_cutout,
                                    output_mask, "rmbg")
    except Exception as e:
        logger.warning("RMBG cutout failed: %s", e)
        return {"method": "rmbg_alpha_matte", "status": "failed",
                "warnings": [str(e)]}


def _expand_bbox_for_image(
    bbox: tuple | list,
    img_w: int,
    img_h: int,
    padding_ratio: float = 0.06,
) -> tuple[int, int, int, int]:
    """Expand a detector bbox while keeping it inside image bounds."""
    x1, y1, x2, y2 = [float(v) for v in bbox]
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    pad_x = bw * padding_ratio
    pad_y = bh * padding_ratio
    ix1 = max(0, int(round(x1 - pad_x)))
    iy1 = max(0, int(round(y1 - pad_y)))
    ix2 = min(img_w, int(round(x2 + pad_x)))
    iy2 = min(img_h, int(round(y2 + pad_y)))
    if ix2 <= ix1:
        ix2 = min(img_w, ix1 + 1)
    if iy2 <= iy1:
        iy2 = min(img_h, iy1 + 1)
    return ix1, iy1, ix2, iy2


def _union_dino_boxes(
    boxes: list,
    img_w: int,
    img_h: int,
    padding_ratio: float = 0.03,
) -> tuple[int, int, int, int] | None:
    """Union GroundingDINO boxes into one target-furniture search region."""
    valid = []
    for box in boxes:
        if not box or len(box) < 4:
            continue
        x1, y1, x2, y2 = [float(v) for v in box[:4]]
        if x2 <= x1 or y2 <= y1:
            continue
        valid.append((x1, y1, x2, y2))
    if not valid:
        return None
    x1 = min(b[0] for b in valid)
    y1 = min(b[1] for b in valid)
    x2 = max(b[2] for b in valid)
    y2 = max(b[3] for b in valid)
    return _expand_bbox_for_image((x1, y1, x2, y2), img_w, img_h, padding_ratio)


def generate_dino_birefnet_cutout(
    image_path: Path,
    dino_bbox: tuple | list | None,
    output_cutout: Path,
    output_mask: Path,
    support_mask_path: Path | None = None,
    debug_dir: Path | None = None,
) -> dict:
    """Run BiRefNet only inside the DINO target box.

    BiRefNet is a foreground extractor, not a furniture detector. Restricting it
    to the DINO furniture box prevents small foreground items near the furniture
    from becoming the selected subject. A SAM support mask is used only as a
    guard when the boxed BiRefNet alpha is clearly smaller than the target.
    """
    import cv2
    import numpy as np

    img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"Cannot read image: {image_path}")
    img_h, img_w = img_bgr.shape[:2]

    warnings = []
    if not dino_bbox:
        warnings.append("missing_dino_bbox_used_full_image_birefnet")
        info = generate_birefnet_cutout(image_path, output_cutout, output_mask)
        info["method"] = "dino_birefnet_fallback_full_image"
        info["warnings"] = warnings + info.get("warnings", [])
        return info

    boxed = _expand_bbox_for_image(dino_bbox, img_w, img_h, padding_ratio=0.06)
    x1, y1, x2, y2 = boxed
    crop = img_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError("DINO bbox produced an empty crop")

    output_cutout.parent.mkdir(parents=True, exist_ok=True)
    output_mask.parent.mkdir(parents=True, exist_ok=True)
    scratch_dir = debug_dir or output_cutout.parent
    scratch_dir.mkdir(parents=True, exist_ok=True)
    crop_path = scratch_dir / "_dino_birefnet_crop.png"
    crop_cutout_path = scratch_dir / "_dino_birefnet_crop_cutout.png"
    crop_mask_path = scratch_dir / "_dino_birefnet_crop_mask.png"
    cv2.imwrite(str(crop_path), crop)

    birefnet_info = generate_birefnet_cutout(crop_path, crop_cutout_path, crop_mask_path)
    crop_mask = cv2.imread(str(crop_mask_path), cv2.IMREAD_GRAYSCALE)
    if crop_mask is None:
        warnings.append("birefnet_crop_failed_fallback_to_full_image")
        info = generate_birefnet_cutout(image_path, output_cutout, output_mask)
        info["method"] = "birefnet_fallback_full_image"
        info["warnings"] = warnings + info.get("warnings", [])
        return info
    if crop_mask.shape[:2] != (y2 - y1, x2 - x1):
        crop_mask = cv2.resize(crop_mask, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR)

    full_mask = np.zeros((img_h, img_w), dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = crop_mask

    support_area = 0
    support_bbox = None
    alpha_bbox = None
    if support_mask_path and support_mask_path.exists():
        support_mask = cv2.imread(str(support_mask_path), cv2.IMREAD_GRAYSCALE)
        if support_mask is not None:
            if support_mask.shape[:2] != (img_h, img_w):
                support_mask = cv2.resize(support_mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)

            support_box_mask = np.zeros_like(support_mask)
            support_box_mask[y1:y2, x1:x2] = support_mask[y1:y2, x1:x2]
            support_area = int(np.count_nonzero(support_box_mask > 127))
            alpha_area = int(np.count_nonzero(full_mask > 127))
            support_bbox = _bbox_from_mask(support_box_mask)
            alpha_bbox = _bbox_from_mask(full_mask)

            undercovered = False
            if support_area > 0 and alpha_area < support_area * 0.35:
                undercovered = True
            if support_bbox and alpha_bbox:
                sw = max(1, support_bbox[2] - support_bbox[0])
                sh = max(1, support_bbox[3] - support_bbox[1])
                aw = max(1, alpha_bbox[2] - alpha_bbox[0])
                ah = max(1, alpha_bbox[3] - alpha_bbox[1])
                if aw < sw * 0.55 or ah < sh * 0.45:
                    undercovered = True

            if undercovered:
                warnings.append("dino_birefnet_undercovered_target_used_sam_guard")
                full_mask = np.maximum(full_mask, support_box_mask)
                alpha_bbox = _bbox_from_mask(full_mask)

    alpha = cv2.GaussianBlur(full_mask, (3, 3), 0)
    bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    cv2.imwrite(str(output_mask), full_mask)
    cv2.imwrite(str(output_cutout), bgra)

    mask_coverage = float(np.count_nonzero(full_mask > 127)) / max(1, img_w * img_h)
    return {
        "method": "groundingdino_boxed_birefnet",
        "status": "done",
        "warnings": warnings + birefnet_info.get("warnings", []),
        "dino_bbox": [int(v) for v in dino_bbox],
        "expanded_bbox": [int(v) for v in boxed],
        "support_bbox": list(support_bbox) if support_bbox else None,
        "alpha_bbox": list(alpha_bbox) if alpha_bbox else None,
        "support_area": support_area,
        "mask_coverage": round(mask_coverage, 4),
    }


# ---------------------------------------------------------------------------
# Obstacle Analysis: GPT Vision decides, cutout models do not decide
# ---------------------------------------------------------------------------

OBSTACLE_STATUS_LABELS = {
    "none": "장애물 없음",
    "background_only": "배경만 복잡함",
    "surface_obstacle": "표면 장애물 제거 필요",
    "structural_occlusion": "구조 가림으로 신뢰도 낮음",
}

_OBSTACLE_ALLOWED_FURNITURE = {"desk", "chair", "sofa", "cabinet", "table", "bed", "unknown"}
_OBSTACLE_ALLOWED_STATUS = {"none", "background_only", "surface_obstacle", "structural_occlusion"}


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _default_obstacle_analysis(reason: str, furniture_type: str = "unknown") -> dict:
    main_furniture = furniture_type if furniture_type in _OBSTACLE_ALLOWED_FURNITURE else "unknown"
    return {
        "main_furniture": main_furniture,
        "obstacle_status": "background_only",
        "needs_inpainting": False,
        "occlusion_affects_outline": False,
        "confidence": "low",
        "obstacles": [],
        "reason": reason,
    }


def _normalize_obstacle_analysis(parsed: dict, furniture_type: str = "unknown") -> dict:
    main_furniture = str(parsed.get("main_furniture", furniture_type or "unknown")).lower()
    if main_furniture not in _OBSTACLE_ALLOWED_FURNITURE:
        main_furniture = "unknown"

    obstacle_status = str(parsed.get("obstacle_status", "background_only")).lower()
    if obstacle_status not in _OBSTACLE_ALLOWED_STATUS:
        obstacle_status = "background_only"

    confidence = str(parsed.get("confidence", "medium")).lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    obstacles = parsed.get("obstacles", [])
    if not isinstance(obstacles, list):
        obstacles = []
    normalized_obstacles = []
    for item in obstacles:
        if not isinstance(item, dict):
            continue
        normalized_obstacles.append({
            "name": str(item.get("name", "unknown")),
            "location": str(item.get("location", "")),
            "removal_needed": bool(item.get("removal_needed", False)),
            "affects_measurement": bool(item.get("affects_measurement", False)),
        })

    needs_inpainting = obstacle_status == "surface_obstacle"
    return {
        "main_furniture": main_furniture,
        "obstacle_status": obstacle_status,
        "needs_inpainting": needs_inpainting,
        "occlusion_affects_outline": bool(parsed.get(
            "occlusion_affects_outline",
            obstacle_status == "structural_occlusion",
        )),
        "confidence": "low" if obstacle_status == "structural_occlusion" else confidence,
        "obstacles": normalized_obstacles,
        "reason": str(parsed.get("reason", "")),
    }


def analyze_obstacles_with_gpt(
    original_path: Path,
    birefnet_cutout_path: Path | None = None,
    furniture_type: str = "unknown",
) -> dict:
    """Use GPT Vision to classify furniture obstacles.

    BiRefNet is provided only as a visual cutout aid. It does not determine
    obstacle status; GPT Vision must make the semantic judgement.
    """
    skip_reason = _openai_skip_reason()
    if skip_reason:
        return _default_obstacle_analysis(skip_reason, furniture_type=furniture_type)

    client = get_openai_client()
    content = [
        {
            "type": "text",
            "text": (
                "You are judging whether a furniture image contains removable obstacles.\n"
                "You must decide from vision only. The BiRefNet cutout, if provided, is only a visual aid; "
                "do not treat BiRefNet as the judge.\n\n"
                "Classify obstacle_status as:\n"
                "- none: clean furniture, no relevant obstacle.\n"
                "- background_only: background is complex, but no object is on or occluding the furniture.\n"
                "- surface_obstacle: clearly removable non-furniture clutter sits on the furniture surface, "
                "such as books, cups, clothes, bags, tools, or random clutter. "
                "They do not hide the outer silhouette or structural outline.\n"
                "- structural_occlusion: an object/person/cloth blocks the furniture outline, legs, frame, door, backrest, side, or other structural parts.\n\n"
                "Do NOT mark ordinary sofa cushions, bolsters, pillows, included back cushions, seams, wrinkles, "
                "product accessories, or small plush/doll decorations as surface_obstacle when they do not affect "
                "the furniture outline, structure, or measurement. In that case use none or background_only and set needs_inpainting false.\n\n"
                "Return ONLY valid JSON with exactly this shape:\n"
                "{\n"
                '  "main_furniture": "desk | chair | sofa | cabinet | table | bed | unknown",\n'
                '  "obstacle_status": "none | background_only | surface_obstacle | structural_occlusion",\n'
                '  "needs_inpainting": true,\n'
                '  "occlusion_affects_outline": true,\n'
                '  "confidence": "high | medium | low",\n'
                '  "obstacles": [\n'
                "    {\n"
                '      "name": "book",\n'
                '      "location": "on tabletop",\n'
                '      "removal_needed": true,\n'
                '      "affects_measurement": false\n'
                "    }\n"
                "  ],\n"
                '  "reason": "..."\n'
                "}\n\n"
                "Important policy for needs_inpainting:\n"
                "- true only for surface_obstacle.\n"
                "- false for none, background_only, and structural_occlusion.\n"
                "For structural_occlusion, mark confidence low because restoration cannot be trusted for measurement."
            ),
        },
        {"type": "text", "text": "[Original image]"},
        {"type": "image_url", "image_url": {"url": _image_data_url(original_path), "detail": "high"}},
    ]
    if birefnet_cutout_path and birefnet_cutout_path.exists():
        content.extend([
            {"type": "text", "text": "[BiRefNet cutout visual aid. Do not use this as the judge.]"},
            {"type": "image_url", "image_url": {"url": _image_data_url(birefnet_cutout_path), "detail": "high"}},
        ])

    kwargs = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        if _mark_openai_unavailable(e):
            return _default_obstacle_analysis(str(_openai_unavailable_reason), furniture_type=furniture_type)
        kwargs.pop("response_format", None)
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as retry_error:
            _mark_openai_unavailable(retry_error)
            raise

    raw = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise ValueError(f"Could not parse obstacle analysis response: {raw}")
        parsed = json.loads(match.group(0))
    return _normalize_obstacle_analysis(parsed, furniture_type)


def _build_obstacle_removal_prompt(obstacle_analysis: dict, furniture_type: str) -> str:
    target = furniture_type if furniture_type != "unknown" else obstacle_analysis.get("main_furniture", "furniture")
    obstacles = obstacle_analysis.get("obstacles", [])
    obstacle_lines = []
    for item in obstacles:
        if item.get("removal_needed"):
            name = item.get("name", "object")
            location = item.get("location", "")
            obstacle_lines.append(f"- {name}" + (f" ({location})" if location else ""))
    obstacle_text = "\n".join(obstacle_lines) if obstacle_lines else "- surface clutter/items on the furniture"
    return (
        f"Remove only the removable surface obstacles from the {target}.\n\n"
        f"Obstacles to remove:\n{obstacle_text}\n\n"
        f"Preserve the original {target}'s exact visible geometry, silhouette, width, height, "
        f"perspective, outline, leg/frame positions, surface dimensions, material, and edges.\n"
        f"Do not redesign, beautify, stretch, compress, rotate, recrop, or replace the furniture.\n"
        f"Do not invent hidden structural parts. Do not remove any part of the furniture.\n"
        f"Keep the result as a realistic photo on the same canvas. Only clean the removable objects."
    )


def generate_obstacle_removed_image(
    image_path: Path,
    output_path: Path,
    obstacle_analysis: dict,
    furniture_type: str,
) -> dict:
    """Run GPT Image Edit only for surface obstacles."""
    if obstacle_analysis.get("obstacle_status") != "surface_obstacle":
        return {"method": "skipped", "status": "skipped", "warnings": ["no_surface_obstacle"]}
    skip_reason = _openai_skip_reason()
    if skip_reason:
        return {"method": "skipped", "status": "skipped", "warnings": [skip_reason]}

    client = get_openai_client()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    models = [m.strip() for m in os.environ.get(
        "GPT_IMAGE_MODELS", DEFAULT_GPT_IMAGE_MODELS
    ).split(",") if m.strip()]
    edit_size = _select_edit_size(image_path)
    last_error = None

    for model in models:
        try:
            kwargs = {
                "model": model,
                "prompt": _build_obstacle_removal_prompt(obstacle_analysis, furniture_type),
                "size": edit_size,
                "n": 1,
                "quality": "high",
                "input_fidelity": "high",
                "output_format": "png",
            }
            with open(image_path, "rb") as img_file:
                kwargs["image"] = img_file
                result = _call_images_edit(client, **kwargs)
            if not result.data or not result.data[0].b64_json:
                raise RuntimeError(f"No valid inpainted image from {model}")
            output_path.write_bytes(base64.b64decode(result.data[0].b64_json))
            return {
                "method": f"obstacle_inpaint_{model}",
                "status": "done",
                "warnings": [],
                "size_used": edit_size,
                "obstacle_status": obstacle_analysis.get("obstacle_status"),
            }
        except Exception as e:
            _mark_openai_unavailable(e)
            last_error = e
            logger.warning("Obstacle removal with model '%s' failed: %s", model, e)

    return {
        "method": "obstacle_inpaint",
        "status": "failed",
        "warnings": [f"all_models_failed: {last_error}"],
        "obstacle_status": obstacle_analysis.get("obstacle_status"),
    }


def evaluate_cutout_quality(
    original_path: Path,
    mask_path: Path,
    cutout_path: Path,
    reference_bbox: tuple | None = None,
) -> dict:
    """Evaluate quality of a background removal result.

    Returns metrics: mask_coverage, bbox_aspect_ratio, edge_smoothness,
    connected_components_count, thin_structure_score, background_leakage_warning,
    ratio_score, quality_score.
    """
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    orig = cv2.imread(str(original_path))
    if mask is None or orig is None:
        return {"quality_score": 0, "warnings": ["unreadable"]}

    h, w = mask.shape[:2]
    total = h * w

    # Binarize
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    fg_pixels = int(np.count_nonzero(binary))

    # 1. Mask coverage
    coverage = fg_pixels / total

    # 2. Connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    # num_labels includes background (label 0)
    fg_components = num_labels - 1

    # Largest component area
    if fg_components > 0:
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest_area = int(areas.max())
        # Fragmentation: what fraction of fg is in the largest component
        cohesion = largest_area / max(fg_pixels, 1)
    else:
        largest_area = 0
        cohesion = 0

    # 3. Edge smoothness (perimeter / sqrt(area) — lower is smoother)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_perimeter = sum(cv2.arcLength(c, True) for c in contours)
    import math
    edge_smoothness = total_perimeter / max(math.sqrt(fg_pixels), 1)

    # 4. Thin structure score: erode and check survival ratio
    kernel_thin = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    eroded = cv2.erode(binary, kernel_thin, iterations=2)
    eroded_fg = int(np.count_nonzero(eroded))
    thin_structure_score = eroded_fg / max(fg_pixels, 1)
    # Higher = more robust thick structures, lower = lots of thin parts

    # 5. BBox and aspect ratio
    bbox = _bbox_from_mask(mask)
    bbox_ar = None
    if bbox:
        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        bbox_ar = bw / max(bh, 1)

    # 6. Background leakage warning
    bg_warnings = []
    if coverage > 0.75:
        bg_warnings.append("high_coverage_possible_bg_leak")
    if coverage < 0.01:
        bg_warnings.append("very_low_coverage_detection_failure")
    if fg_components > 5:
        bg_warnings.append("many_fragments")
    if cohesion < 0.5 and fg_components > 1:
        bg_warnings.append("low_cohesion")

    # 7. Ratio score vs reference
    ratio_score = None
    if reference_bbox and bbox:
        ev = evaluate_ratio_preservation(reference_bbox, bbox, "sam_bbox")
        ratio_score = ev["ratio_score"]

    # 8. Composite quality score (0-100)
    qs = 100.0
    # Penalize extreme coverage
    if coverage > 0.75:
        qs -= 20
    elif coverage < 0.02:
        qs -= 30
    # Penalize fragmentation
    qs -= min(max(fg_components - 1, 0) * 3, 20)
    # Reward cohesion
    qs -= max(0, (1 - cohesion)) * 15
    # Penalize jagged edges (typical smooth is ~15-25, bad is >40)
    if edge_smoothness > 35:
        qs -= min((edge_smoothness - 35) * 0.5, 15)
    # Reward thin structure survival
    if thin_structure_score < 0.5:
        qs -= (0.5 - thin_structure_score) * 20
    qs = max(0, round(qs, 1))

    return {
        "mask_coverage": round(coverage, 4),
        "bbox_aspect_ratio": round(bbox_ar, 3) if bbox_ar else None,
        "bbox": bbox,
        "edge_smoothness": round(edge_smoothness, 1),
        "connected_components_count": fg_components,
        "cohesion": round(cohesion, 3),
        "thin_structure_score": round(thin_structure_score, 3),
        "background_leakage_warning": bg_warnings,
        "ratio_score": ratio_score,
        "quality_score": qs,
        "warnings": bg_warnings,
    }


def _select_edit_size(image_path: Path) -> str:
    """Pick images.edit size closest to original aspect ratio."""
    from PIL import Image as PILImage
    img = PILImage.open(image_path)
    w, h = img.size
    ar = w / h
    if ar > 1.2:
        return "1536x1024"  # landscape
    elif ar < 0.8:
        return "1024x1536"  # portrait
    return "1024x1024"  # square-ish


def _create_edit_mask_from_sam(sam_mask_path: Path, image_path: Path, output_path: Path) -> Path:
    """Create OpenAI-compatible edit mask from SAM mask.

    OpenAI convention: transparent areas (alpha=0) = regions to edit.
    So: furniture (SAM=255) → alpha=255 (preserve), background (SAM=0) → alpha=0 (edit/remove).
    """
    import cv2
    import numpy as np

    mask = cv2.imread(str(sam_mask_path), cv2.IMREAD_GRAYSCALE)
    img = cv2.imread(str(image_path))
    if mask is None or img is None:
        raise ValueError("Cannot read mask or image for edit mask creation")

    h, w = img.shape[:2]
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    # RGBA: white pixels, alpha channel = SAM mask
    rgba = np.ones((h, w, 4), dtype=np.uint8) * 255
    rgba[:, :, 3] = mask  # furniture=255(preserve), background=0(edit)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), rgba)
    return output_path


def _call_images_edit(client, **kwargs):
    """Call images.edit with progressive fallback for unsupported params."""
    optional_params = ["input_fidelity", "background", "output_format", "quality"]

    while True:
        try:
            return client.images.edit(**kwargs)
        except TypeError as e:
            err_msg = str(e)
            removed = False
            for param in optional_params:
                if param in err_msg and param in kwargs:
                    logger.info("Removing unsupported param '%s' from images.edit call", param)
                    del kwargs[param]
                    removed = True
                    break
            if not removed:
                raise
        except Exception as e:
            err_msg = str(e)
            removed = False
            for param in optional_params:
                if param in err_msg and param in kwargs:
                    logger.info("Removing unsupported param '%s' from images.edit call", param)
                    del kwargs[param]
                    removed = True
                    break
            if not removed:
                raise


def generate_gpt_cutout(
    image_path: Path,
    output_path: Path,
    sam_mask_path: Path | None = None,
    ref_bbox: tuple | None = None,
    ref_source: str = "sam_bbox",
    furniture_type: str = "unknown",
) -> dict:
    """High-quality GPT cutout via images.edit with mask, multi-candidate selection.

    Key improvements over naive approach:
    - Uses original aspect ratio (not forced 1024x1024)
    - input_fidelity="high" to preserve original geometry
    - SAM mask guides edit (protect furniture, edit background only)
    - Generates 3 candidates, picks best by ratio_score vs ref_bbox
    - Model fallback chain (env-configurable)

    Returns dict with method, status, warnings, ratio eval, and candidate evals.
    This is DISPLAY-ONLY — never used for dimension measurement.
    """
    client = get_openai_client()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    warnings = []

    models = [m.strip() for m in os.environ.get(
        "GPT_IMAGE_MODELS", DEFAULT_GPT_IMAGE_MODELS
    ).split(",") if m.strip()]

    edit_size = _select_edit_size(image_path)
    logger.info("GPT cutout: size=%s, models=%s", edit_size, models)

    # Create edit mask from SAM mask if available
    edit_mask_path = None
    if sam_mask_path and sam_mask_path.exists():
        try:
            edit_mask_path = output_path.parent / "_edit_mask.png"
            _create_edit_mask_from_sam(sam_mask_path, image_path, edit_mask_path)
            logger.info("Created edit mask from SAM mask for guided editing")
        except Exception as e:
            logger.warning("Failed to create edit mask: %s", e)
            edit_mask_path = None

    last_error = None
    for model in models:
        try:
            # Build kwargs — optional params may not be supported by SDK
            kwargs = {
                "model": model,
                "prompt": _build_edit_prompt(furniture_type),
                "size": edit_size,
                "n": 3,
                "quality": "high",
                "input_fidelity": "high",
                "background": "transparent",
                "output_format": "png",
            }

            # Open files for API call
            img_file = open(image_path, "rb")
            mask_file = open(edit_mask_path, "rb") if edit_mask_path else None

            try:
                kwargs["image"] = img_file
                if mask_file:
                    kwargs["mask"] = mask_file

                result = _call_images_edit(client, **kwargs)
            finally:
                img_file.close()
                if mask_file:
                    mask_file.close()

            # Collect valid candidates
            candidates = []
            for i, img_data in enumerate(result.data):
                b64 = img_data.b64_json
                if not b64:
                    continue
                cand_path = output_path.parent / f"_gpt_candidate_{i}.png"
                cand_path.write_bytes(base64.b64decode(b64))
                candidates.append(cand_path)

            if not candidates:
                raise RuntimeError(f"No valid candidates from {model}")

            logger.info("GPT cutout: %d candidates from %s", len(candidates), model)

            # Pick best candidate by ratio_score vs reference bbox
            best_path, best_eval, candidates_eval = _pick_best_candidate(
                candidates, ref_bbox, ref_source
            )

            # Move best to output, cleanup rest
            shutil.copy2(str(best_path), str(output_path))
            for c in candidates:
                c.unlink(missing_ok=True)

            # Determine status from ratio eval
            status = "success"
            ar_diff_pct = None
            if best_eval:
                ar_diff_pct = best_eval.get("aspect_ratio_diff_pct")
                grade = best_eval.get("ratio_grade", "pass")
                if grade == "fail":
                    warnings.append("gpt_cutout_geometry_changed")
                    status = "geometry_warning"
                elif grade == "warning":
                    warnings.append("gpt_cutout_ratio_warning")
                    status = "geometry_warning"

            # Cleanup edit mask
            if edit_mask_path and edit_mask_path.exists():
                edit_mask_path.unlink(missing_ok=True)

            return {
                "method": f"images_edit_{model}",
                "status": status,
                "warnings": warnings,
                "ar_diff_pct": ar_diff_pct,
                "candidates_generated": len(candidates),
                "size_used": edit_size,
                "mask_guided": edit_mask_path is not None,
                "gpt_cutout_eval": best_eval,
                "gpt_candidates_eval": candidates_eval,
            }

        except Exception as e:
            last_error = e
            logger.warning("GPT cutout with model '%s' failed: %s", model, e)
            continue

    # Cleanup edit mask on total failure
    if edit_mask_path and edit_mask_path.exists():
        edit_mask_path.unlink(missing_ok=True)

    return {
        "method": "images_edit",
        "status": "failed",
        "warnings": [f"all_models_failed: {last_error}"],
    }


def _pick_best_candidate(
    candidates: list[Path],
    ref_bbox: tuple | None,
    ref_source: str = "sam_bbox",
) -> tuple[Path, dict | None, list[dict]]:
    """Pick the candidate with the highest ratio_score vs reference bbox.

    Returns (best_path, best_eval, candidates_eval_list).
    If ref_bbox is None, returns the first candidate with no eval.
    """
    if not candidates:
        raise ValueError("No candidates to pick from")
    if ref_bbox is None or len(candidates) == 1:
        return candidates[0], None, []

    best_path = candidates[0]
    best_score = -1.0
    best_eval = None
    candidates_eval = []

    for i, cand_path in enumerate(candidates):
        cand_bbox = _bbox_from_rgba_file(cand_path)
        if cand_bbox is None:
            candidates_eval.append({
                "candidate": i, "ratio_score": 0, "ratio_grade": "fail",
                "warnings": ["bbox_unreadable"],
            })
            continue
        cand_w = cand_bbox[2] - cand_bbox[0]
        cand_h = cand_bbox[3] - cand_bbox[1]
        if cand_h == 0:
            candidates_eval.append({
                "candidate": i, "ratio_score": 0, "ratio_grade": "fail",
                "warnings": ["zero_height"],
            })
            continue
        ev = evaluate_ratio_preservation(ref_bbox, cand_bbox, ref_source)
        candidates_eval.append({
            "candidate": i,
            "ratio_score": ev["ratio_score"],
            "ratio_grade": ev["ratio_grade"],
            "aspect_ratio_diff_pct": ev["aspect_ratio_diff_pct"],
            "width_diff_pct": ev["width_diff_pct"],
            "height_diff_pct": ev["height_diff_pct"],
            "warnings": ev["warnings"],
        })
        if ev["ratio_score"] > best_score:
            best_score = ev["ratio_score"]
            best_path = cand_path
            best_eval = ev

    return best_path, best_eval, candidates_eval


def _multi_prompt_segment(image_path: Path, device: str = "cpu", debug_dir: Path | None = None, furniture_type: str = "unknown") -> tuple:
    """Run GroundingDINO with multiple furniture-part prompts + SAM for each detection.

    Returns (list of part dicts, image_np).
    """
    import cv2
    import numpy as np
    import torch
    from PIL import Image

    segmenter = get_segmenter(device)
    gsam = _get_gsam(segmenter)

    # Check we have a real GroundedSamSegmenter
    if not hasattr(gsam, "processor") or not hasattr(gsam, "predictor"):
        # Fallback: single-prompt segmentation
        result = segmenter.segment(image_path, furniture_type=None, auto_detect=True)
        img = cv2.imread(str(image_path))
        h, w = img.shape[:2]
        return [{"mask": result.mask, "label": result.label or "furniture",
                 "confidence": result.confidence or 0.0,
                 "box": [0, 0, w, h]}], np.array(Image.open(image_path).convert("RGB"))

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    image_np = np.array(image)

    # Combined multi-prompt detection
    prompt_text = ". ".join(_get_part_prompts(furniture_type)) + "."
    inputs = gsam.processor(images=image, text=prompt_text, return_tensors="pt")
    inputs = {k: v.to(gsam.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = gsam.detector(**inputs)

    results = gsam.processor.post_process_grounded_object_detection(
        outputs,
        input_ids=inputs.get("input_ids"),
        threshold=0.15,
        text_threshold=0.15,
        target_sizes=[(height, width)],
    )[0]

    boxes = results.get("boxes")
    scores = results.get("scores")
    labels = results.get("labels", [])

    if boxes is None or len(boxes) == 0:
        raise ValueError("GroundingDINO detected no furniture parts with multi-prompt.")

    # SAM mask for each detection
    gsam.predictor.set_image(image_np)
    part_masks = []

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    for i in range(len(boxes)):
        box = boxes[i].detach().cpu().numpy()
        score = float(scores[i].detach().cpu().item())
        label = str(labels[i]) if i < len(labels) else "unknown"

        masks, sam_scores, _ = gsam.predictor.predict(box=box, multimask_output=True)
        best_idx = int(np.argmax(sam_scores))
        mask = masks[best_idx].astype(np.uint8) * 255

        part_masks.append({
            "mask": mask,
            "label": label,
            "confidence": score,
            "box": box.tolist(),
        })

        if debug_dir:
            cv2.imwrite(str(debug_dir / f"part_{i:02d}_{label}_{score:.2f}.png"), mask)

    logger.info("Multi-prompt detected %d parts: %s",
                len(part_masks), [(p["label"], round(p["confidence"], 2)) for p in part_masks])
    return part_masks, image_np


def _merge_and_filter_masks(part_masks: list, image_shape: tuple, debug_dir: Path | None = None) -> np.ndarray:
    """Merge part-level SAM masks with connected-component filtering.

    Keeps main furniture body + vertically elongated thin legs.
    Removes large background artifacts (window frames, curtains, floor patches).
    """
    import cv2
    import numpy as np

    h, w = image_shape[:2]
    total_area = h * w

    # Union of all part masks
    merged_raw = np.zeros((h, w), dtype=np.uint8)
    for part in part_masks:
        merged_raw = np.maximum(merged_raw, part["mask"])

    if debug_dir:
        cv2.imwrite(str(debug_dir / "merged_raw.png"), merged_raw)

    # Gentle closing only — preserve thin legs, close small gaps
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(merged_raw, cv2.MORPH_CLOSE, kernel_small, iterations=1)

    # Connected component analysis
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(closed, connectivity=8)

    if num_labels <= 1:
        return closed

    # Find largest component (assumed to be main furniture body)
    areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, num_labels)]
    largest_label = int(np.argmax(areas)) + 1
    largest_area = areas[largest_label - 1]
    largest_stats = stats[largest_label]
    main_left = largest_stats[cv2.CC_STAT_LEFT]
    main_top = largest_stats[cv2.CC_STAT_TOP]
    main_w = largest_stats[cv2.CC_STAT_WIDTH]
    main_h = largest_stats[cv2.CC_STAT_HEIGHT]
    main_right = main_left + main_w
    main_bottom = main_top + main_h
    main_cx, main_cy = centroids[largest_label]

    filtered = np.zeros((h, w), dtype=np.uint8)

    for label_id in range(1, num_labels):
        comp_area = stats[label_id, cv2.CC_STAT_AREA]
        comp_x = stats[label_id, cv2.CC_STAT_LEFT]
        comp_y = stats[label_id, cv2.CC_STAT_TOP]
        comp_w = stats[label_id, cv2.CC_STAT_WIDTH]
        comp_h = stats[label_id, cv2.CC_STAT_HEIGHT]
        comp_cx, comp_cy = centroids[label_id]

        # Always keep largest (main furniture body)
        if label_id == largest_label:
            filtered[labels == label_id] = 255
            continue

        # Skip tiny noise (< 0.05% of image area)
        if comp_area < total_area * 0.0005:
            continue

        aspect = comp_h / max(comp_w, 1)
        comp_right = comp_x + comp_w
        comp_bottom = comp_y + comp_h

        # Horizontal overlap with main body
        h_overlap = max(0, min(comp_right, main_right) - max(comp_x, main_left))
        h_overlap_ratio = h_overlap / max(comp_w, 1)

        # Vertical proximity: component bottom near or below main body bottom (legs)
        is_below_main = comp_cy > main_cy
        vert_dist = abs(comp_cy - main_cy)

        # === Keep: vertically elongated components overlapping main body (legs) ===
        if aspect > 1.8 and h_overlap_ratio > 0.3:
            filtered[labels == label_id] = 255
            logger.debug("Keep leg-like component #%d (aspect=%.1f, overlap=%.1f%%)",
                         label_id, aspect, h_overlap_ratio * 100)
            continue

        # === Keep: significant components with strong overlap (frame parts) ===
        if h_overlap_ratio > 0.5 and comp_area > largest_area * 0.03:
            filtered[labels == label_id] = 255
            continue

        # === Keep: components close to and below main body (legs/base) ===
        if is_below_main and vert_dist < main_h * 0.8 and h_overlap_ratio > 0.2:
            filtered[labels == label_id] = 255
            continue

        # === Remove: wide horizontal strips far from main body (window/curtain) ===
        if aspect < 0.4 and comp_area > total_area * 0.01:
            logger.debug("Remove wide background #%d (aspect=%.2f, area=%.1f%%)",
                         label_id, aspect, comp_area / total_area * 100)
            continue

        # === Remove: components far from main body ===
        dist = ((comp_cx - main_cx) ** 2 + (comp_cy - main_cy) ** 2) ** 0.5
        max_dist = ((main_w ** 2 + main_h ** 2) ** 0.5) * 0.8
        if dist > max_dist:
            logger.debug("Remove distant component #%d (dist=%.0f > %.0f)", label_id, dist, max_dist)
            continue

        # Default: keep if reasonably close and overlapping
        if h_overlap_ratio > 0.1:
            filtered[labels == label_id] = 255

    # Fill internal holes in the main body (but preserve large holes like space under tabletop)
    # Only fill small holes, not the space between legs
    contours, _ = cv2.findContours(filtered, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    hole_mask = np.zeros_like(filtered)
    cv2.drawContours(hole_mask, contours, -1, 255, cv2.FILLED)
    # Only fill holes smaller than 2% of main furniture area
    hole_diff = cv2.bitwise_and(hole_mask, cv2.bitwise_not(filtered))
    hole_num, hole_labels, hole_stats, _ = cv2.connectedComponentsWithStats(hole_diff, connectivity=8)
    for hl in range(1, hole_num):
        hole_area = hole_stats[hl, cv2.CC_STAT_AREA]
        if hole_area < largest_area * 0.02:
            filtered[hole_labels == hl] = 255

    if debug_dir:
        cv2.imwrite(str(debug_dir / "merged_filtered.png"), filtered)

    return filtered


def generate_measurement_image(
    image_path: Path, output_preprocessed: Path, output_mask: Path,
    device: str = "cpu", debug_dir: Path | None = None,
    furniture_type: str = "unknown",
) -> dict:
    """Generate measurement-grade preprocessed image via multi-prompt SAM segmentation.

    Preserves original pixels exactly. Furniture on neutral gray background.
    Returns segmentation metadata.
    """
    import cv2
    import numpy as np

    # Multi-prompt detection + SAM
    part_masks, image_np = _multi_prompt_segment(image_path, device, debug_dir, furniture_type=furniture_type)
    h, w = image_np.shape[:2]

    # Merge and filter
    final_mask = _merge_and_filter_masks(part_masks, (h, w), debug_dir)

    # Composite furniture onto neutral gray background (original pixels)
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise ValueError(f"Cannot read image: {image_path}")

    mask_float = final_mask.astype(np.float32) / 255.0
    bg_color = np.array([245, 245, 245], dtype=np.float32)
    img_float = img_bgr.astype(np.float32)
    preprocessed = (img_float * mask_float[:, :, None] +
                    bg_color[None, None, :] * (1.0 - mask_float[:, :, None]))

    for p in [output_preprocessed, output_mask]:
        p.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(output_preprocessed), preprocessed.astype(np.uint8))
    cv2.imwrite(str(output_mask), final_mask)

    mask_coverage = float(np.count_nonzero(final_mask > 127)) / (h * w)
    dino_boxes = [p.get("box") for p in part_masks if p.get("box")]
    dino_bbox = _union_dino_boxes(dino_boxes, w, h, padding_ratio=0.03)
    sam_bbox = _bbox_from_mask(final_mask)

    # Best confidence from parts
    best_part = max(part_masks, key=lambda p: p["confidence"])

    return {
        "method": "multi_prompt_groundingdino_sam",
        "confidence": best_part["confidence"],
        "label": best_part["label"],
        "mask_coverage": round(mask_coverage, 4),
        "dino_bbox": list(dino_bbox) if dino_bbox else None,
        "sam_bbox": list(sam_bbox) if sam_bbox else None,
        "dino_boxes": dino_boxes,
        "num_parts_detected": len(part_masks),
        "parts": [(p["label"], round(p["confidence"], 3)) for p in part_masks],
    }


# ---------------------------------------------------------------------------
# Stage 2.5: Quality validation
# ---------------------------------------------------------------------------

def _bbox_from_mask(mask) -> tuple | None:
    """Tight bounding box of non-zero pixels: (x_min, y_min, x_max, y_max)."""
    import numpy as np
    coords = np.where(mask > 127)
    if len(coords[0]) == 0:
        return None
    return (int(coords[1].min()), int(coords[0].min()),
            int(coords[1].max()), int(coords[0].max()))


def _bbox_from_mask_file(mask_path: Path) -> tuple | None:
    """Read a grayscale mask file and return its tight bbox."""
    import cv2
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return None
    return _bbox_from_mask(mask)


def _bbox_from_rgba_file(path: Path) -> tuple | None:
    """Bounding box of non-transparent pixels in a PNG file."""
    import numpy as np
    from PIL import Image as PILImage
    try:
        img = PILImage.open(path).convert("RGBA")
        alpha = np.array(img)[:, :, 3]
        return _bbox_from_mask(alpha)
    except Exception:
        return None


def _clamp_bbox(bbox: tuple, img_w: int, img_h: int) -> tuple:
    """Clamp bbox coordinates to image bounds. Returns clamped (x1,y1,x2,y2)."""
    x1 = max(0, min(int(bbox[0]), img_w))
    y1 = max(0, min(int(bbox[1]), img_h))
    x2 = max(0, min(int(bbox[2]), img_w))
    y2 = max(0, min(int(bbox[3]), img_h))
    return (x1, y1, x2, y2)


def _validate_bbox(bbox: tuple, img_w: int, img_h: int) -> tuple[bool, str | None]:
    """Check if bbox dimensions exceed image size (invalid reference).
    Returns (valid, reason_or_None).
    """
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    if bw <= 0 or bh <= 0:
        return False, "zero_size_bbox"
    if bw > img_w:
        return False, f"bbox_width_{bw}_exceeds_image_width_{img_w}"
    if bh > img_h:
        return False, f"bbox_height_{bh}_exceeds_image_height_{img_h}"
    return True, None


def evaluate_ratio_preservation(
    ref_bbox: tuple,
    gpt_bbox: tuple,
    ref_source: str = "sam_bbox",
    image_size: tuple | None = None,  # (width, height) of original image
    gpt_image_size: tuple | None = None,  # (width, height) of GPT output image
) -> dict:
    """Evaluate how well GPT cutout preserves original object proportions.

    Returns dict with ratio_score (0-100), ratio_grade (pass/fail/evaluation_unavailable).
    If reference bbox is invalid (e.g. wider than image), returns evaluation_unavailable.
    """
    import math

    img_w, img_h = image_size if image_size else (99999, 99999)
    gpt_w_img, gpt_h_img = gpt_image_size if gpt_image_size else (img_w, img_h)

    # Validate and clamp reference bbox
    ref_bbox_raw = tuple(int(v) for v in ref_bbox)
    ref_bbox_clamped = _clamp_bbox(ref_bbox_raw, img_w, img_h)
    ref_valid, ref_invalid_reason = _validate_bbox(ref_bbox_clamped, img_w, img_h)

    # Validate and clamp GPT bbox (against GPT output image size)
    gpt_bbox_raw = tuple(int(v) for v in gpt_bbox)
    gpt_bbox_clamped = _clamp_bbox(gpt_bbox_raw, gpt_w_img, gpt_h_img)

    # Same canvas: GPT output must match original image size for valid comparison
    same_canvas = (img_w == gpt_w_img and img_h == gpt_h_img)

    base = {
        "image_width": img_w,
        "image_height": img_h,
        "reference_bbox_source": ref_source,
        "reference_bbox_raw": list(ref_bbox_raw),
        "reference_bbox_clamped": list(ref_bbox_clamped),
        "reference_bbox_valid": ref_valid,
        "reference_bbox_invalid_reason": ref_invalid_reason,
        "gpt_alpha_bbox": list(gpt_bbox_clamped),
        "same_canvas": same_canvas,
    }

    if not ref_valid:
        return {**base,
                "status": "evaluation_unavailable",
                "reason": f"invalid_reference_bbox: {ref_invalid_reason}",
                "ratio_grade": "evaluation_unavailable",
                "ratio_score": None, "warnings": []}

    if not same_canvas:
        return {**base,
                "status": "evaluation_unavailable",
                "reason": "different_canvas_size_cannot_compare",
                "ratio_grade": "evaluation_unavailable",
                "ratio_score": None, "warnings": []}

    ref_w = ref_bbox_clamped[2] - ref_bbox_clamped[0]
    ref_h = ref_bbox_clamped[3] - ref_bbox_clamped[1]
    gpt_w = gpt_bbox_clamped[2] - gpt_bbox_clamped[0]
    gpt_h = gpt_bbox_clamped[3] - gpt_bbox_clamped[1]

    if ref_w <= 0 or ref_h <= 0:
        return {**base,
                "status": "evaluation_unavailable",
                "reason": "zero_size_after_clamp",
                "ratio_grade": "evaluation_unavailable",
                "ratio_score": None, "warnings": []}

    ref_ar = ref_w / max(ref_h, 1)
    gpt_ar = gpt_w / max(gpt_h, 1)
    ref_area = ref_w * ref_h
    gpt_area = gpt_w * gpt_h

    ref_cx = (ref_bbox_clamped[0] + ref_bbox_clamped[2]) / 2
    ref_cy = (ref_bbox_clamped[1] + ref_bbox_clamped[3]) / 2
    gpt_cx = (gpt_bbox_clamped[0] + gpt_bbox_clamped[2]) / 2
    gpt_cy = (gpt_bbox_clamped[1] + gpt_bbox_clamped[3]) / 2
    ref_diag = math.sqrt(ref_w ** 2 + ref_h ** 2)

    aspect_ratio_diff_pct = abs(gpt_ar - ref_ar) / max(ref_ar, 0.01) * 100
    width_diff_pct = abs(gpt_w - ref_w) / max(ref_w, 1) * 100
    height_diff_pct = abs(gpt_h - ref_h) / max(ref_h, 1) * 100
    area_diff_pct = abs(gpt_area - ref_area) / max(ref_area, 1) * 100
    center_dist = math.sqrt((gpt_cx - ref_cx) ** 2 + (gpt_cy - ref_cy) ** 2)
    center_shift_pct = center_dist / max(ref_diag, 1) * 100

    score = 100.0
    score -= min(aspect_ratio_diff_pct * 4, 40)
    score -= min(width_diff_pct * 1.5, 20)
    score -= min(height_diff_pct * 1.5, 20)
    score -= min(center_shift_pct * 2, 20)
    score = max(0, round(score, 1))

    warnings = []
    grade = "pass"

    if aspect_ratio_diff_pct > 10:
        grade = "fail"
        warnings.append("aspect_ratio_changed")
    elif aspect_ratio_diff_pct > 5:
        grade = "warning"
        warnings.append("aspect_ratio_slightly_changed")

    if width_diff_pct > 15:
        grade = "fail"
        warnings.append("width_changed")
    if height_diff_pct > 15:
        grade = "fail"
        warnings.append("height_changed")
    if center_shift_pct > 15:
        grade = "fail"
        warnings.append("center_shift_large")
    if area_diff_pct > 25:
        if grade != "fail":
            grade = "warning"
        warnings.append("area_significantly_different")

    return {
        **base,
        "status": grade,
        "reason": None,
        "ratio_score": score,
        "ratio_grade": grade,
        "reference_aspect_ratio": round(ref_ar, 3),
        "gpt_aspect_ratio": round(gpt_ar, 3),
        "aspect_ratio_diff_pct": round(aspect_ratio_diff_pct, 1),
        "width_diff_pct": round(width_diff_pct, 1),
        "height_diff_pct": round(height_diff_pct, 1),
        "area_diff_pct": round(area_diff_pct, 1),
        "center_shift_pct": round(center_shift_pct, 1),
        "reference_area": int(ref_area),
        "gpt_area": int(gpt_area),
        "warnings": warnings,
    }


def generate_ratio_overlay(
    image_path: Path,
    ref_bbox: tuple,
    gpt_bbox: tuple,
    output_path: Path,
    eval_result: dict,
) -> Path:
    """Generate overlay image comparing reference bbox (blue) vs GPT bbox (red)."""
    import cv2
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError("Cannot read image for overlay")

    overlay = img.copy()
    h, w = overlay.shape[:2]

    # Reference bbox in blue
    cv2.rectangle(overlay,
                  (int(ref_bbox[0]), int(ref_bbox[1])),
                  (int(ref_bbox[2]), int(ref_bbox[3])),
                  (255, 140, 0), 3)  # BGR blue
    # GPT bbox in red
    cv2.rectangle(overlay,
                  (int(gpt_bbox[0]), int(gpt_bbox[1])),
                  (int(gpt_bbox[2]), int(gpt_bbox[3])),
                  (0, 0, 255), 3)  # BGR red

    # Semi-transparent blend
    result = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)

    # Text info
    font = cv2.FONT_HERSHEY_SIMPLEX
    score = eval_result.get("ratio_score", 0)
    grade = eval_result.get("ratio_grade", "?")
    ar_diff = eval_result.get("aspect_ratio_diff_pct", 0)
    texts = [
        f"Score: {score}/100 ({grade})",
        f"AR diff: {ar_diff}%",
        f"W diff: {eval_result.get('width_diff_pct', 0)}%",
        f"H diff: {eval_result.get('height_diff_pct', 0)}%",
        f"Center shift: {eval_result.get('center_shift_pct', 0)}%",
    ]
    y_pos = 30
    for txt in texts:
        cv2.putText(result, txt, (10, y_pos), font, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(result, txt, (10, y_pos), font, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
        y_pos += 24

    # Legend
    legend_y = h - 50
    cv2.rectangle(result, (10, legend_y), (30, legend_y + 14), (255, 140, 0), -1)
    cv2.putText(result, "Reference (SAM)", (36, legend_y + 12), font, 0.5, (0, 0, 0), 1)
    cv2.rectangle(result, (10, legend_y + 20), (30, legend_y + 34), (0, 0, 255), -1)
    cv2.putText(result, "GPT Cutout", (36, legend_y + 32), font, 0.5, (0, 0, 0), 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), result)
    return output_path


def validate_geometry(sam_mask_path: Path, cutout_path: Path) -> dict:
    """Compare SAM measurement bbox vs GPT cutout bbox. Returns geometry_check dict."""
    import cv2
    import numpy as np

    warnings = []
    result = {"passed": True, "warnings": warnings}

    sam_mask = cv2.imread(str(sam_mask_path), cv2.IMREAD_GRAYSCALE)
    if sam_mask is None:
        warnings.append("sam_mask_unreadable")
        result["passed"] = False
        return result

    h, w = sam_mask.shape[:2]
    coverage = float(np.count_nonzero(sam_mask > 127)) / (h * w)
    result["mask_coverage"] = round(coverage, 4)

    if coverage > 0.85:
        warnings.append("mask_too_large_possible_background_leak")
    elif coverage < 0.02:
        warnings.append("mask_too_small_possible_detection_failure")

    sam_bbox = _bbox_from_mask(sam_mask)
    if sam_bbox is None:
        warnings.append("sam_mask_empty")
        result["passed"] = False
        return result

    sam_w = sam_bbox[2] - sam_bbox[0]
    sam_h = sam_bbox[3] - sam_bbox[1]
    sam_ratio = sam_w / max(sam_h, 1)
    result["sam_bbox"] = sam_bbox
    result["sam_aspect_ratio"] = round(sam_ratio, 3)

    # GPT cutout geometry check (strict: >10% diff = FAILURE, not just warning)
    gpt_failed = False
    if cutout_path.exists():
        cutout_bbox = _bbox_from_rgba_file(cutout_path)
        if cutout_bbox:
            cut_w = cutout_bbox[2] - cutout_bbox[0]
            cut_h = cutout_bbox[3] - cutout_bbox[1]
            cut_ratio = cut_w / max(cut_h, 1)
            ratio_diff = abs(sam_ratio - cut_ratio) / max(sam_ratio, 0.01)
            result["cutout_bbox"] = cutout_bbox
            result["cutout_aspect_ratio"] = round(cut_ratio, 3)
            result["aspect_ratio_diff_pct"] = round(ratio_diff * 100, 1)

            if ratio_diff > 0.10:
                warnings.append("gpt_cutout_geometry_failed")
                gpt_failed = True
        else:
            warnings.append("gpt_cutout_bbox_unreadable")
            gpt_failed = True

    result["gpt_cutout_failed"] = gpt_failed
    result["passed"] = len([w for w in warnings
                            if w not in ("gpt_cutout_geometry_failed",
                                         "gpt_cutout_bbox_unreadable")]) == 0
    return result


# ---------------------------------------------------------------------------
# Stage 4: Dimension Measurement via GPT-4o Vision
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
    "chair": {"width_cm": 50, "depth_cm": 55, "height_cm": 85},
    "desk": {"width_cm": 120, "depth_cm": 60, "height_cm": 75},
    "table": {"width_cm": 120, "depth_cm": 75, "height_cm": 74},
    "sofa": {"width_cm": 180, "depth_cm": 85, "height_cm": 80},
    "cabinet": {"width_cm": 80, "depth_cm": 45, "height_cm": 120},
    "shelf": {"width_cm": 80, "depth_cm": 30, "height_cm": 160},
    "bed": {"width_cm": 200, "depth_cm": 100, "height_cm": 50},
    "dresser": {"width_cm": 90, "depth_cm": 45, "height_cm": 140},
    "unknown": {"width_cm": None, "depth_cm": None, "height_cm": None},
}


def _local_dimension_fallback(
    title: str = "",
    description: str = "",
    furniture_type: str = "unknown",
    reason: str = "openai_unavailable",
) -> dict:
    """Return conservative category defaults when GPT Vision cannot run."""
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
            "OpenAI Vision dimension estimation was unavailable, so this uses "
            f"a low-confidence category default for '{ftype}'. Use real measured "
            "dimensions for AR scale or production modeling."
        ),
    }


def measure_dimensions(
    image_path: Path,
    title: str = "",
    description: str = "",
    furniture_type: str = "unknown",
) -> dict:
    """Use GPT Vision to estimate furniture dimensions."""
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


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


def scrape_listing(body: dict) -> tuple[dict, int]:
    """Scrape listing metadata and image candidates from a supported marketplace URL."""
    url = body.get("url", "").strip()

    if not url:
        return {"error": "URL을 입력해주세요."}, 400

    platform = identify_platform(url)
    if not platform:
        return {"error": "당근마켓 또는 중고나라 URL만 지원합니다."}, 400

    scrapers = {"daangn": scrape_daangn, "joongna": scrape_joongna}
    try:
        data = scrapers[platform](url)
        data["platform"] = platform
        return data, 200
    except Exception as e:
        return {"error": f"스크래핑 실패: {e}"}, 500


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    body = request.get_json(force=True)
    data, status_code = scrape_listing(body)
    return jsonify(data), status_code


def run_pipeline(body: dict) -> tuple[dict, int]:
    """Full pipeline: scrape -> select image -> preprocess -> bg remove -> measure."""
    url = body.get("url", "").strip()
    # preprocess_method kept for backward compat but now always runs dual-output
    selected_image_index = body.get("selected_image_index")  # optional, user-selected

    if not url:
        return {"error": "URL을 입력해주세요."}, 400

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    steps = []

    try:
        # Step 1: Scrape
        platform = identify_platform(url)
        if not platform:
            return {"error": "당근마켓 또는 중고나라 URL만 지원합니다."}, 400

        scrapers = {"daangn": scrape_daangn, "joongna": scrape_joongna}
        scraped = scrapers[platform](url)
        scraped["platform"] = platform
        steps.append({"step": "scrape", "status": "done", "data": scraped})

        if not scraped["images"]:
            return {"error": "이미지를 찾을 수 없습니다.", "steps": steps}, 400

        # Step 2: Select best image
        if selected_image_index is not None and 0 <= selected_image_index < len(scraped["images"]):
            best_idx = selected_image_index
        elif len(scraped["images"]) > 1:
            best_idx = select_best_image_gpt(scraped["title"], scraped["description"], scraped["images"])
        else:
            best_idx = 0

        best_image_url = scraped["images"][best_idx]
        original_path = job_dir / "01_original.jpg"
        download_image(best_image_url, original_path)
        steps.append({"step": "select_image", "status": "done", "selected_index": best_idx, "image_url": best_image_url})

        # Step 2.5: Furniture type classification (category-aware)
        listing_class = classify_furniture_from_listing(scraped["title"], scraped.get("description", ""))
        image_class = classify_furniture_from_image(original_path, scraped["title"], scraped.get("description", ""))
        furniture_info = reconcile_furniture_type(listing_class, image_class)
        furniture_type = furniture_info["furniture_type"]
        logger.info("Furniture type: %s (confidence=%s, listing=%s, image=%s)",
                     furniture_type, furniture_info["confidence"],
                     furniture_info.get("listing"), furniture_info.get("image"))
        steps.append({
            "step": "classify_furniture",
            "status": "done",
            "furniture_type": furniture_type,
            "confidence": furniture_info["confidence"],
            "listing_type": furniture_info.get("listing"),
            "image_type": furniture_info.get("image"),
            "warning": furniture_info.get("warning"),
        })

        # Step 3: Measurement image (multi-prompt SAM - original pixels preserved)
        preprocessed_path = job_dir / "02_measurement.png"
        mask_path = job_dir / "04_mask.png"
        display_cutout_path = job_dir / "03_display_cutout.png"
        debug_dir = job_dir / "debug"

        seg_info = generate_measurement_image(
            original_path, preprocessed_path, mask_path, debug_dir=debug_dir,
            furniture_type=furniture_type,
        )
        steps.append({
            "step": "measurement_image",
            "status": "done",
            "seg_method": seg_info["method"],
            "mask_coverage": seg_info["mask_coverage"],
            "confidence": seg_info.get("confidence"),
            "label": seg_info.get("label"),
            "num_parts": seg_info.get("num_parts_detected"),
            "parts": seg_info.get("parts"),
            "dino_bbox": seg_info.get("dino_bbox"),
            "sam_bbox": seg_info.get("sam_bbox"),
        })

        # Step 4a: Faithful cutout (SAM mask → RGBA, original pixels, zero AI)
        faithful_cutout_path = job_dir / "03_display_cutout.png"
        faithful_info = generate_faithful_cutout(original_path, mask_path, faithful_cutout_path)
        steps.append({
            "step": "faithful_cutout",
            "status": "done",
            "method": faithful_info["method"],
        })

        # Step 4a-2: BiRefNet cutout (alpha matte, original pixels)
        birefnet_cutout_path = job_dir / "06_birefnet_cutout.png"
        birefnet_mask_path = job_dir / "06_birefnet_mask.png"
        birefnet_info = {"method": "birefnet_alpha_matte", "status": "skipped", "warnings": []}
        try:
            birefnet_info = generate_birefnet_cutout(original_path, birefnet_cutout_path, birefnet_mask_path)
            birefnet_info["status"] = birefnet_info.get("status", "done")
            steps.append({"step": "birefnet_cutout", "status": "done", "method": birefnet_info["method"]})
        except Exception as e:
            logger.warning("BiRefNet cutout failed: %s", e)
            birefnet_info["status"] = "failed"
            steps.append({"step": "birefnet_cutout", "status": "failed", "error": str(e)})

        # Step 4a-2b: DINO + BiRefNet.
        # DINO anchors the target furniture box; BiRefNet only mattes inside it.
        dino_birefnet_cutout_path = job_dir / "06_dino_birefnet_cutout.png"
        dino_birefnet_mask_path = job_dir / "06_dino_birefnet_mask.png"
        dino_birefnet_info = {
            "method": "groundingdino_boxed_birefnet",
            "status": "skipped",
            "warnings": [],
        }
        try:
            dino_birefnet_info = generate_dino_birefnet_cutout(
                original_path,
                seg_info.get("dino_bbox") or seg_info.get("sam_bbox"),
                dino_birefnet_cutout_path,
                dino_birefnet_mask_path,
                support_mask_path=mask_path,
                debug_dir=debug_dir,
            )
            dino_birefnet_info["status"] = dino_birefnet_info.get("status", "done")
            steps.append({
                "step": "dino_birefnet_cutout",
                "status": dino_birefnet_info["status"],
                "method": dino_birefnet_info["method"],
                "warnings": dino_birefnet_info.get("warnings", []),
                "expanded_bbox": dino_birefnet_info.get("expanded_bbox"),
            })
        except Exception as e:
            logger.warning("DINO + BiRefNet cutout failed: %s", e)
            dino_birefnet_info["status"] = "failed"
            steps.append({"step": "dino_birefnet_cutout", "status": "failed", "error": str(e)})

        # Step 4a-3: RMBG cutout (alpha matte, original pixels)
        rmbg_cutout_path = job_dir / "07_rmbg_cutout.png"
        rmbg_mask_path = job_dir / "07_rmbg_mask.png"
        rmbg_info = {"method": "rmbg_alpha_matte", "status": "skipped", "warnings": []}
        try:
            rmbg_info = generate_rmbg_cutout(original_path, rmbg_cutout_path, rmbg_mask_path)
            rmbg_info["status"] = rmbg_info.get("status", "done")
            steps.append({"step": "rmbg_cutout", "status": "done", "method": rmbg_info["method"]})
        except Exception as e:
            logger.warning("RMBG cutout failed: %s", e)
            rmbg_info["status"] = "failed"
            steps.append({"step": "rmbg_cutout", "status": "failed", "error": str(e)})

        # Step 4b: GPT Vision obstacle analysis.
        # BiRefNet is passed only as a visual aid; GPT Vision owns the semantic judgement.
        try:
            obstacle_analysis = analyze_obstacles_with_gpt(
                original_path,
                dino_birefnet_cutout_path if dino_birefnet_cutout_path.exists()
                else (birefnet_cutout_path if birefnet_cutout_path.exists() else None),
                furniture_type=furniture_type,
            )
            steps.append({
                "step": "obstacle_analysis",
                "status": "done",
                "obstacle_status": obstacle_analysis["obstacle_status"],
                "needs_inpainting": obstacle_analysis["needs_inpainting"],
                "confidence": obstacle_analysis["confidence"],
                "occlusion_affects_outline": obstacle_analysis["occlusion_affects_outline"],
            })
        except Exception as e:
            logger.warning("Obstacle analysis failed: %s", e)
            obstacle_analysis = _default_obstacle_analysis(
                f"obstacle_analysis_failed: {e}",
                furniture_type=furniture_type,
            )
            steps.append({"step": "obstacle_analysis", "status": "failed", "error": str(e)})

        # Step 4d: Evaluate all faithful cutout models first (needed to determine ref_bbox)
        # SAM bbox used as temporary fallback during evaluation
        sam_bbox_tmp = _bbox_from_mask_file(mask_path)
        cutout_models_eval = {}
        cutout_models = [
            ("dino_sam", mask_path, faithful_cutout_path),
            ("dino_birefnet", dino_birefnet_mask_path, dino_birefnet_cutout_path),
            ("birefnet", birefnet_mask_path, birefnet_cutout_path),
            ("rmbg", rmbg_mask_path, rmbg_cutout_path),
        ]
        for name, m_path, c_path in cutout_models:
            if m_path.exists() and c_path.exists():
                try:
                    ev = evaluate_cutout_quality(original_path, m_path, c_path, sam_bbox_tmp)
                    ev["measurement_eligible"] = True
                    ev["display_only"] = False
                    if name == "dino_birefnet":
                        ev["dino_boxed"] = True
                        ev["guard_warnings"] = dino_birefnet_info.get("warnings", [])
                    cutout_models_eval[name] = ev
                except Exception as e:
                    logger.warning("Quality eval for %s failed: %s", name, e)
                    cutout_models_eval[name] = {"quality_score": 0, "warnings": [str(e)],
                                                "measurement_eligible": True, "display_only": False}

        # Auto-select faithful cutout model. DINO + BiRefNet is preferred because
        # DINO anchors the sold furniture and BiRefNet only refines alpha inside it.
        faithful_models = {k: v for k, v in cutout_models_eval.items()}
        if "dino_birefnet" in faithful_models:
            best_model = "dino_birefnet"
        elif "dino_sam" in faithful_models:
            best_model = "dino_sam"
        elif faithful_models:
            best_model = max(faithful_models, key=lambda k: faithful_models[k].get("quality_score", 0))
        else:
            best_model = "dino_sam"
        auto_selected = best_model

        # User override: body.selected_cutout_method (GPT not eligible for measurement)
        user_selected = body.get("selected_cutout_method")
        if user_selected and not str(user_selected).startswith("gpt") and user_selected in cutout_models_eval:
            selected_method = user_selected
        else:
            selected_method = auto_selected

        steps.append({
            "step": "cutout_comparison",
            "status": "done",
            "models_evaluated": list(cutout_models_eval.keys()),
            "auto_selected": auto_selected,
            "user_selected": user_selected,
            "selected_method": selected_method,
        })

        # Step 4d-2: Compute reference bbox with priority order:
        # 1) user ROI bbox, 2) selected_method mask, 3) auto_selected mask, 4) SAM mask
        roi_bbox_raw = body.get("roi_bbox")  # [x, y, w, h] or None
        ref_bbox = None
        ref_source = "unavailable"

        measurement_mask_map = {
            "dino_sam": mask_path,
            "sam": mask_path,
            "dino_birefnet": dino_birefnet_mask_path,
            "birefnet": birefnet_mask_path,
            "rmbg": rmbg_mask_path,
        }

        if roi_bbox_raw and len(roi_bbox_raw) == 4:
            rx, ry, rw, rh = roi_bbox_raw
            ref_bbox = (rx, ry, rx + rw, ry + rh)
            ref_source = "roi_bbox"
        else:
            # Try selected_method mask first
            for candidate_method in [selected_method, auto_selected, "dino_sam", "sam"]:
                candidate_mask = measurement_mask_map.get(candidate_method)
                if candidate_mask and candidate_mask.exists():
                    candidate_bbox = _bbox_from_mask_file(candidate_mask)
                    if candidate_bbox:
                        ref_bbox = candidate_bbox
                        ref_source = f"{candidate_method}_mask_bbox"
                        break

        # Get original image size for coordinate validation
        import cv2 as _cv2_size
        _orig_img_size = _cv2_size.imread(str(original_path))
        if _orig_img_size is not None:
            orig_h, orig_w = _orig_img_size.shape[:2]
            image_size = (orig_w, orig_h)
        else:
            image_size = None

        # Step 4b: GPT inpainting is allowed only for surface_obstacle.
        obstacle_removed_path = job_dir / "05_obstacle_removed.png"
        obstacle_removed_cutout_path = job_dir / "05_obstacle_removed_birefnet_cutout.png"
        obstacle_removed_mask_path = job_dir / "05_obstacle_removed_birefnet_mask.png"
        gpt_info = {"method": "skipped", "status": "skipped", "warnings": []}
        gpt_cutout_eval = None
        gpt_candidates_eval = []
        inpainting_used = False
        ratio_eval = {
            "status": "skipped",
            "reason": "no_inpainting_needed",
            "ratio_grade": "pass",
            "ratio_score": 100,
            "warnings": [],
            "reference_bbox_source": ref_source,
            "obstacle_status": obstacle_analysis["obstacle_status"],
        }

        if obstacle_analysis["obstacle_status"] == "surface_obstacle":
            gpt_info = generate_obstacle_removed_image(
                original_path,
                obstacle_removed_path,
                obstacle_analysis,
                furniture_type,
            )
            inpainting_used = gpt_info.get("status") == "done" and obstacle_removed_path.exists()
            steps.append({
                "step": "gpt_cutout",
                "status": gpt_info["status"],
                "method": gpt_info["method"],
                "warnings": gpt_info.get("warnings", []),
                "size_used": gpt_info.get("size_used"),
                "obstacle_status": obstacle_analysis["obstacle_status"],
            })

            if inpainting_used:
                inpaint_birefnet_info = generate_birefnet_cutout(
                    obstacle_removed_path,
                    obstacle_removed_cutout_path,
                    obstacle_removed_mask_path,
                )
                steps.append({
                    "step": "post_inpaint_birefnet_cutout",
                    "status": inpaint_birefnet_info.get("status", "done"),
                    "method": inpaint_birefnet_info.get("method"),
                    "warnings": inpaint_birefnet_info.get("warnings", []),
                })

                if obstacle_removed_mask_path.exists() and obstacle_removed_cutout_path.exists():
                    try:
                        ev = evaluate_cutout_quality(
                            obstacle_removed_path,
                            obstacle_removed_mask_path,
                            obstacle_removed_cutout_path,
                            ref_bbox,
                        )
                        ev["display_only"] = True
                        ev["measurement_eligible"] = False
                        cutout_models_eval["gpt_inpaint_birefnet"] = ev
                    except Exception as e:
                        cutout_models_eval["gpt_inpaint_birefnet"] = {
                            "quality_score": 0,
                            "warnings": [str(e)],
                            "display_only": True,
                            "measurement_eligible": False,
                        }

                if ref_bbox and obstacle_removed_mask_path.exists():
                    gpt_bbox = _bbox_from_mask_file(obstacle_removed_mask_path)
                    if gpt_bbox:
                        from PIL import Image as _PILSize
                        try:
                            _gpt_img = _PILSize.open(obstacle_removed_path)
                            gpt_image_size = _gpt_img.size
                        except Exception:
                            gpt_image_size = image_size
                        ratio_eval = evaluate_ratio_preservation(
                            ref_bbox,
                            gpt_bbox,
                            ref_source,
                            image_size=image_size,
                            gpt_image_size=gpt_image_size,
                        )
                        ratio_eval["obstacle_status"] = obstacle_analysis["obstacle_status"]
                        gpt_cutout_eval = ratio_eval
                    else:
                        ratio_eval = {
                            "status": "evaluation_unavailable",
                            "reason": "post_inpaint_birefnet_bbox_unreadable",
                            "ratio_grade": "evaluation_unavailable",
                            "ratio_score": None,
                            "warnings": [],
                            "reference_bbox_source": ref_source,
                            "obstacle_status": obstacle_analysis["obstacle_status"],
                        }
                elif ref_bbox is None:
                    ratio_eval = {
                        "status": "evaluation_unavailable",
                        "reason": "no_reference_bbox",
                        "ratio_grade": "evaluation_unavailable",
                        "ratio_score": None,
                        "warnings": [],
                        "reference_bbox_source": ref_source,
                        "obstacle_status": obstacle_analysis["obstacle_status"],
                    }
            else:
                ratio_eval = {
                    "status": "evaluation_unavailable",
                    "reason": "surface_obstacle_inpainting_failed",
                    "ratio_grade": "evaluation_unavailable",
                    "ratio_score": None,
                    "warnings": gpt_info.get("warnings", []),
                    "reference_bbox_source": ref_source,
                    "obstacle_status": obstacle_analysis["obstacle_status"],
                }
        else:
            if obstacle_analysis["obstacle_status"] == "structural_occlusion":
                ratio_eval = {
                    "status": "skipped",
                    "reason": "structural_occlusion_not_inpainted",
                    "ratio_grade": "fail",
                    "ratio_score": 0,
                    "warnings": ["structural_occlusion_low_confidence"],
                    "reference_bbox_source": ref_source,
                    "obstacle_status": obstacle_analysis["obstacle_status"],
                }
            steps.append({
                "step": "gpt_cutout",
                "status": "skipped",
                "method": "not_needed" if obstacle_analysis["obstacle_status"] != "structural_occlusion" else "structural_occlusion_not_inpainted",
                "warnings": ratio_eval.get("warnings", []),
                "obstacle_status": obstacle_analysis["obstacle_status"],
            })

        # Step 4b-3: Generate ratio overlay image for inpainted BiRefNet cutout.
        overlay_path = job_dir / "08_ratio_overlay.png"
        if ref_bbox and obstacle_removed_mask_path.exists() and ratio_eval.get("status") not in ("evaluation_unavailable", "skipped"):
            gpt_bbox_for_overlay = _bbox_from_mask_file(obstacle_removed_mask_path)
            if gpt_bbox_for_overlay:
                try:
                    generate_ratio_overlay(
                        original_path, ref_bbox, gpt_bbox_for_overlay,
                        overlay_path, ratio_eval,
                    )
                except Exception as e:
                    logger.warning("Ratio overlay generation failed: %s", e)

        # Step 4c: Geometry validation. Only compare GPT result when surface inpainting exists.
        geometry_target = obstacle_removed_cutout_path if inpainting_used else (job_dir / "_no_gpt_inpaint.png")
        geometry_check = validate_geometry(mask_path, geometry_target)
        geometry_check["cutout_method"] = gpt_info.get("method", "skipped")
        geometry_check["obstacle_status"] = obstacle_analysis["obstacle_status"]
        for w in gpt_info.get("warnings", []):
            if w not in geometry_check["warnings"]:
                geometry_check["warnings"].append(w)

        if obstacle_analysis["obstacle_status"] == "structural_occlusion":
            geometry_check["structural_occlusion"] = True
            geometry_check["gpt_cutout_failed"] = True
            if "structural_occlusion_low_confidence" not in geometry_check["warnings"]:
                geometry_check["warnings"].append("structural_occlusion_low_confidence")

        if geometry_check.get("gpt_cutout_failed"):
            logger.warning("GPT inpaint/cutout is not reliable for measurement or scale")

        if inpainting_used and ratio_eval.get("ratio_grade") == "fail":
            geometry_check["gpt_cutout_failed"] = True
            if "ratio_preservation_failed" not in geometry_check["warnings"]:
                geometry_check["warnings"].append("ratio_preservation_failed")

        steps.append({
            "step": "geometry_check",
            "status": "done",
            "passed": geometry_check["passed"],
            "warnings": geometry_check["warnings"],
            "details": {k: v for k, v in geometry_check.items()
                        if k not in ("passed", "warnings")},
        })

        # Determine measurement mask (selected_method, never GPT)
        selected_mask = measurement_mask_map.get(selected_method, mask_path)
        if not selected_mask.exists():
            selected_mask = mask_path  # fallback to SAM

        # Step 5: Dimension measurement (uses best faithful mask, never GPT)
        if selected_method != "sam" and selected_mask.exists():
            import cv2 as _cv2
            import numpy as _np
            _orig = _cv2.imread(str(original_path))
            _sel_mask = _cv2.imread(str(selected_mask), _cv2.IMREAD_GRAYSCALE)
            if _orig is not None and _sel_mask is not None:
                if _orig.shape[:2] != _sel_mask.shape[:2]:
                    _sel_mask = _cv2.resize(_sel_mask, (_orig.shape[1], _orig.shape[0]))
                _bg = _np.full_like(_orig, 245)
                _bin = (_sel_mask > 127).astype(_np.uint8)[:, :, None]
                _meas = _orig * _bin + _bg * (1 - _bin)
                _meas_path = job_dir / f"02_measurement_{selected_method}.png"
                _cv2.imwrite(str(_meas_path), _meas)
                preprocessed_path = _meas_path

        dimensions = measure_dimensions(
            preprocessed_path,
            scraped["title"],
            scraped["description"],
            furniture_type=furniture_type,
        )
        steps.append({"step": "dimension_measurement", "status": "done",
                       "dimensions": dimensions, "measurement_mask": selected_method})

        # Build final_decision
        obstacle_status = obstacle_analysis["obstacle_status"]
        structural_occlusion = obstacle_status == "structural_occlusion"
        ratio_grade = ratio_eval.get("ratio_grade", "evaluation_unavailable")
        dim_confidence = dimensions.get("confidence", "low") if dimensions else "low"
        can_measure = dim_confidence in ("medium", "high") and not structural_occlusion
        can_ar_scale = ratio_grade == "pass" and not structural_occlusion
        can_3d_gen = (
            not structural_occlusion
            and (not inpainting_used or ratio_grade in ("pass", "warning"))
            and not geometry_check.get("gpt_cutout_failed")
        )
        final_warnings = list(geometry_check.get("warnings", []))
        if structural_occlusion and "structural_occlusion_low_confidence" not in final_warnings:
            final_warnings.append("structural_occlusion_low_confidence")
        if ratio_grade == "fail" and (inpainting_used or structural_occlusion):
            final_warnings.append("ratio_preservation_failed_gpt_not_reliable_for_scale")
        if ratio_grade == "evaluation_unavailable" and obstacle_status == "surface_obstacle":
            final_warnings.append("ratio_evaluation_unavailable_cannot_verify_gpt_scale")
        if dim_confidence == "low":
            final_warnings.append("dimension_confidence_low")
        for warning in dimensions.get("warnings", []) if isinstance(dimensions, dict) else []:
            if warning not in final_warnings:
                final_warnings.append(warning)
        if obstacle_status == "surface_obstacle" and not inpainting_used:
            final_warnings.append("surface_obstacle_inpainting_unavailable")

        final_decision = {
            "measurement_source": selected_method,
            "preview_source": "gpt_inpaint_birefnet" if inpainting_used else selected_method,
            "can_use_for_dimension": can_measure,
            "can_use_for_3d_generation": can_3d_gen,
            "can_use_for_ar_scale": can_ar_scale,
            "warnings": final_warnings,
            "obstacle_status": obstacle_status,
            "inpainting_used": inpainting_used,
        }

        # Save results JSON
        result = {
            "job_id": job_id,
            "url": url,
            "platform": platform,
            "title": scraped["title"],
            "price": scraped["price"],
            "preprocess_method": "dual_output",
            "selected_image_index": best_idx,
            "furniture_type": furniture_type,
            "furniture_type_confidence": furniture_info["confidence"],
            "furniture_type_warning": furniture_info.get("warning"),
            "obstacle_analysis": obstacle_analysis,
            "obstacle_status": obstacle_status,
            "inpainting_used": inpainting_used,
            "dimensions": dimensions,
            "geometry_check": geometry_check,
            "ratio_eval": ratio_eval,
            "gpt_cutout_eval": gpt_cutout_eval,
            "gpt_candidates_eval": gpt_candidates_eval,
            "cutout_models_eval": cutout_models_eval,
            "segmentation_info": seg_info,
            "dino_birefnet_info": dino_birefnet_info,
            "selected_cutout_method": selected_method,
            "auto_selected_cutout": auto_selected,
            "final_decision": final_decision,
            "warnings": final_warnings,
            "steps": steps,
        }
        (job_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        return result, 200

    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        steps.append({"step": "error", "status": "failed", "error": str(e)})
        return {"error": str(e), "job_id": job_id, "steps": steps}, 500


@app.route("/api/process", methods=["POST"])
def api_process():
    body = request.get_json(force=True)
    data, status_code = run_pipeline(body)
    return jsonify(data), status_code


@app.route("/api/output/<job_id>/<filename>")
def serve_output(job_id, filename):
    """Serve output images."""
    safe_job_id = Path(job_id).name
    safe_filename = Path(filename).name
    job_dir = OUTPUT_DIR / safe_job_id
    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404
    return send_from_directory(str(job_dir), safe_filename)


if __name__ == "__main__":
    load_runtime_environment()

    print("=" * 60)
    print("Furniture Dimension Pipeline")
    print("=" * 60)
    print(f"Output dir: {OUTPUT_DIR}")
    print("Open: http://localhost:5001")
    print("=" * 60)
    app.run(debug=True, port=5001)
