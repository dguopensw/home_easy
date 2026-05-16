"""pipeline_core — SAM3-only 가구 파이프라인 핵심 서비스 함수 모음.

SAM3-only cutout 방식:
  URL → scrape → image selection → SAM3 part-based furniture mask
      → measurement image (original + SAM3 mask, gray bg)
      → final_cutout (SAM3 mask as alpha, original pixels)
      → contaminant analysis → (if needed: LaMa inpaint → generation cutout)
      → dimension estimation → result

이 파일은 backend/services/ 에서 import해서 사용합니다.

NOTE: _core 모듈(app.py 기반)이 필요합니다. backend/core.py 로 구현 후 연결하세요.
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Paths & env
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
OUTPUT_DIR = PIPELINE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
SERVICE_STATIC_DIR = PIPELINE_DIR / "service_static"

sys.path.insert(0, str(PROJECT_ROOT / "nanobanana_ratio_project"))

# Reuse core functions from app.py (legacy pipeline is preserved, not modified)
# NOTE: _core = app.py 의 핵심 함수들. backend/core.py 로 구현 후 아래 주석을 해제하세요.
# from backend import core as _core


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    url: str = ""


class ProcessRequest(BaseModel):
    url: str = ""
    selected_image_index: int = 0


# ---------------------------------------------------------------------------
# scrape_listing
# ---------------------------------------------------------------------------

def scrape_listing(url: str) -> dict:
    """Scrape product listing from Daangn or Joongna."""
    platform = _core.identify_platform(url)
    if not platform:
        raise ValueError("당근마켓 또는 중고나라 URL만 지원합니다.")
    scrapers = {"daangn": _core.scrape_daangn, "joongna": _core.scrape_joongna}
    data = scrapers[platform](url)
    data["platform"] = platform
    return data


# ---------------------------------------------------------------------------
# choose_best_image
# ---------------------------------------------------------------------------

def choose_best_image(title: str, description: str, image_urls: list[str]) -> dict:
    """Use GPT-4o Vision to rank images and recommend the best representative."""
    if not image_urls:
        raise ValueError("이미지가 없습니다.")

    default = {
        "recommended_index": 0,
        "ranked_candidate_indices": list(range(len(image_urls))),
        "reasoning": {},
    }

    if len(image_urls) == 1:
        default["reasoning"] = {0: "only one image available"}
        return default

    skip = _core._openai_skip_reason()
    if skip:
        default["reasoning"] = {0: f"GPT unavailable: {skip}"}
        return default

    client = _core.get_openai_client()
    n = min(len(image_urls), 8)

    image_content: list[dict] = []
    for i, url in enumerate(image_urls[:n]):
        image_content.append({"type": "text", "text": f"[Image {i}]"})
        image_content.append({"type": "image_url", "image_url": {"url": url, "detail": "low"}})

    prompt = (
        f"Title: {title}\nDescription: {description[:400]}\n\n"
        f"Rank these {n} furniture images from best to worst for automated processing.\n"
        "Best = shows full furniture clearly, good angle, minimal occlusion, not too close-up.\n"
        "Return ONLY valid JSON:\n"
        '{"ranked": [0,1,2,...], "reasons": {"0": "reason", "1": "reason"}}'
    )

    try:
        resp = client.chat.completions.create(
            model=_core.VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
            ] + image_content}],
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        ranked_raw = parsed.get("ranked", list(range(n)))
        reasons = {int(k): v for k, v in parsed.get("reasons", {}).items()}

        # Validate and fill in missing indices
        ranked = [int(i) for i in ranked_raw if 0 <= int(i) < len(image_urls)]
        seen = set(ranked)
        for i in range(len(image_urls)):
            if i not in seen:
                ranked.append(i)

        return {
            "recommended_index": ranked[0],
            "ranked_candidate_indices": ranked,
            "reasoning": reasons,
        }
    except Exception as e:
        _core._mark_openai_unavailable(e)
        logger.warning("Image ranking failed: %s", e)
        return default


# ---------------------------------------------------------------------------
# infer_furniture_type
# ---------------------------------------------------------------------------

def infer_furniture_type(image_path: Path, title: str, description: str) -> dict:
    """Infer furniture type from listing text + GPT vision."""
    listing_class = _core.classify_furniture_from_listing(title, description)
    image_class = _core.classify_furniture_from_image(image_path, title, description)
    return _core.reconcile_furniture_type(listing_class, image_class)


# ---------------------------------------------------------------------------
# parse_listing_dimensions
# ---------------------------------------------------------------------------

_APPROX_WORDS = re.compile(r'약|대략|정도|쯤')


def _has_approx(text: str) -> bool:
    return bool(_APPROX_WORDS.search(text))


def parse_listing_dimensions(title: str, description: str) -> dict | None:
    """Extract dimensions (cm) from listing title/description text."""
    text = f"{title} {description}"

    # W x D x H (English notation): W120xD80xH75, W120*D80*H75
    m = re.search(
        r'[Ww][\s:]*(\d+\.?\d*)\s*[*xX×]\s*[Dd][\s:]*(\d+\.?\d*)\s*[*xX×]\s*[Hh][\s:]*(\d+\.?\d*)',
        text,
    )
    if m:
        return {
            "width_cm": float(m.group(1)),
            "depth_cm": float(m.group(2)),
            "height_cm": float(m.group(3)),
            "source": "listing_text",
            "pattern": "WxDxH",
            "approximate": _has_approx(m.group(0)),
            "raw_match": m.group(0),
        }

    # "가로세로 약 110cm 높이는 약 40cm" — square footprint (W=D) + height
    m = re.search(
        r'가로\s*세로\s*(?:약|대략|정도|쯤)?\s*(\d+\.?\d*)\s*(?:cm|CM)?\s*'
        r'높이\s*(?:는|은|가|이)?\s*(?:약|대략|정도|쯤)?\s*(\d+\.?\d*)\s*(?:cm|CM)?',
        text,
    )
    if m:
        side = float(m.group(1))
        return {
            "width_cm": side,
            "depth_cm": side,
            "height_cm": float(m.group(2)),
            "source": "listing_text",
            "pattern": "korean_galoselo_height",
            "approximate": _has_approx(m.group(0)),
            "raw_match": m.group(0),
        }

    # Korean keywords (separate 가로, 세로, 높이)
    found: dict[str, float] = {}
    approx_found = False
    kw_patterns = [
        (r'(?:가로|폭|너비)\s*(?:약|대략|정도|쯤)?\s*:?\s*(\d+\.?\d*)\s*(?:cm|CM)?', "width_cm"),
        (r'(?:세로|깊이)\s*(?:약|대략|정도|쯤)?\s*:?\s*(\d+\.?\d*)\s*(?:cm|CM)?', "depth_cm"),
        (r'(?:높이)\s*(?:는|은|가|이)?\s*(?:약|대략|정도|쯤)?\s*:?\s*(\d+\.?\d*)\s*(?:cm|CM)?', "height_cm"),
    ]
    for pattern, key in kw_patterns:
        m = re.search(pattern, text)
        if m:
            found[key] = float(m.group(1))
            if _has_approx(m.group(0)):
                approx_found = True

    if len(found) >= 2:
        dims: dict = {"width_cm": None, "depth_cm": None, "height_cm": None}
        dims.update(found)
        return {**dims, "source": "listing_text", "pattern": "korean_keywords",
                "approximate": approx_found}

    # Generic NxNxN pattern (last resort)
    m = re.search(
        r'(\d+\.?\d*)\s*[*xX×]\s*(\d+\.?\d*)\s*[*xX×]\s*(\d+\.?\d*)\s*(?:cm|CM|mm|MM)?',
        text,
    )
    if m:
        v1, v2, v3 = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if max(v1, v2, v3) > 500:  # likely mm → convert
            v1, v2, v3 = v1 / 10, v2 / 10, v3 / 10
        return {
            "width_cm": v1, "depth_cm": v2, "height_cm": v3,
            "source": "listing_text", "pattern": "NxNxN",
            "approximate": _has_approx(m.group(0)),
            "raw_match": m.group(0),
        }

    return None


# ---------------------------------------------------------------------------
# detect_target_with_dino
# ---------------------------------------------------------------------------

def detect_target_with_dino(
    image_path: Path,
    furniture_type: str,
    debug_dir: Path | None = None,
) -> dict:
    """Run GroundingDINO + SAM to locate target furniture.

    Produces:
    - job_dir/02_measurement.png  (furniture on neutral gray bg, original pixels)
    - job_dir/_sam_mask.png       (SAM mask for support in BiRefNet stage)
    Returns bbox and detection metadata.
    """
    measurement_path = image_path.parent / "02_measurement.png"
    sam_mask_path = image_path.parent / "_sam_mask.png"

    try:
        seg_info = _core.generate_measurement_image(
            image_path,
            measurement_path,
            sam_mask_path,
            debug_dir=debug_dir,
            furniture_type=furniture_type,
        )

        import cv2
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError("Cannot read image for bbox validation")
        h, w = img.shape[:2]

        dino_bbox = seg_info.get("dino_bbox") or seg_info.get("sam_bbox")
        bbox_clamped = list(_core._clamp_bbox(tuple(dino_bbox), w, h)) if dino_bbox else None
        bbox_valid = bool(
            bbox_clamped
            and (bbox_clamped[2] - bbox_clamped[0]) > 10
            and (bbox_clamped[3] - bbox_clamped[1]) > 10
        )

        return {
            "method": "grounding_dino",
            "prompt": furniture_type,
            "bbox_raw": list(dino_bbox) if dino_bbox else None,
            "bbox_clamped": bbox_clamped,
            "bbox_valid": bbox_valid,
            "mask_coverage": seg_info.get("mask_coverage"),
            "num_parts_detected": seg_info.get("num_parts_detected"),
            "seg_info": seg_info,
        }

    except Exception as e:
        logger.warning("DINO detection failed: %s", e)
        return {
            "method": "grounding_dino",
            "prompt": furniture_type,
            "bbox_raw": None,
            "bbox_clamped": None,
            "bbox_valid": False,
            "error": str(e),
            "seg_info": {},
        }


# ---------------------------------------------------------------------------
# analyze_major_obstacles
# ---------------------------------------------------------------------------

def analyze_major_obstacles(image_path: Path, furniture_type: str) -> dict:
    """Use GPT-4o Vision to detect MAJOR obstacles conservatively.

    Returns has_major_obstacle=True only when something clearly and significantly
    blocks the furniture's structural parts. Small props → False.
    """
    skip = _core._openai_skip_reason()
    if skip:
        return {
            "has_major_obstacle": False,
            "obstacle_summary": "",
            "obstacles": [],
            "reason": f"GPT unavailable: {skip}",
        }

    client = _core.get_openai_client()
    data_url = _core._image_data_url(image_path)

    prompt = (
        f"Analyze this furniture image (type: {furniture_type}) for MAJOR obstacles.\n\n"
        "A MAJOR obstacle significantly covers the furniture's key structural parts "
        "(silhouette, legs, frame, backrest, surface, doors). It would clearly harm "
        "automated background removal or dimension accuracy.\n\n"
        "Examples of MAJOR obstacles: person sitting on/against furniture, "
        "large box/bag/luggage on top, large laptop/monitor on desk, "
        "thick blanket covering most of the piece.\n\n"
        "NOT major obstacles: sofa cushions/pillows included with the piece, "
        "small decorative items, books, remotes, small plants, picture frames "
        "in the background, items that don't hide structural parts.\n\n"
        "Be CONSERVATIVE. Only mark has_major_obstacle=true when truly significant "
        "structural blocking is present. When in doubt → false.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "has_major_obstacle": false,\n'
        '  "obstacle_summary": "",\n'
        '  "obstacles": [\n'
        '    {"name": "laptop", "description": "large laptop on desk surface", '
        '"location": "tabletop center", "importance": "major"}\n'
        "  ],\n"
        '  "reason": "explanation"\n'
        "}"
    )

    try:
        resp = client.chat.completions.create(
            model=_core.VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
            ]}],
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        obstacles = parsed.get("obstacles", [])
        if not isinstance(obstacles, list):
            obstacles = []

        return {
            "has_major_obstacle": bool(parsed.get("has_major_obstacle", False)),
            "obstacle_summary": str(parsed.get("obstacle_summary", "")),
            "obstacles": [
                {
                    "name": str(o.get("name", "unknown")),
                    "description": str(o.get("description", "")),
                    "location": str(o.get("location", "")),
                    "importance": str(o.get("importance", "major")),
                }
                for o in obstacles if isinstance(o, dict)
            ],
            "reason": str(parsed.get("reason", "")),
        }

    except Exception as e:
        _core._mark_openai_unavailable(e)
        logger.warning("Obstacle analysis failed: %s", e)
        return {
            "has_major_obstacle": False,
            "obstacle_summary": "",
            "obstacles": [],
            "reason": f"analysis_failed: {e}",
        }


# ---------------------------------------------------------------------------
# analyze_generation_contaminants
# ---------------------------------------------------------------------------

def analyze_generation_contaminants(
    image_path: Path,
    furniture_type: str,
    masking_family: str = "generic",
) -> dict:
    """Use GPT-4o Vision to detect objects that would contaminate 3D generation.

    These objects don't block dimension estimation but would be baked into
    the generated 3D model if not removed first.
    """
    skip = _core._openai_skip_reason()
    if skip:
        return {
            "has_generation_contaminants": False,
            "contaminant_summary": "",
            "contaminants": [],
            "reason": f"GPT unavailable: {skip}",
        }

    client = _core.get_openai_client()
    data_url = _core._image_data_url(image_path)

    _FAMILY_GUIDANCE: dict[str, str] = {
        "soft_furniture": (
            "\nIMPORTANT — this is soft/upholstered furniture (sofa, lounge chair, armchair, "
            "recliner, or similar). Built-in back cushions, seat cushions, lumbar cushions, "
            "and pillow-like backrests are PART of the furniture structure. "
            "Do NOT mark them as contaminants. "
            "Only flag clearly loose decorative pillows, blankets, or personal items that are "
            "obviously unrelated to the furniture itself. "
            "When in doubt, do NOT flag as contaminant. "
            "Objects that are visually aligned with the backrest or seat cushion and share the "
            "same fabric or material should be treated as part of the furniture, not as contaminants.\n"
        ),
        "bed_type": (
            "\nIMPORTANT — this is a bed or mattress. Pillows, blankets, and bed linen that "
            "are placed ON the mattress are contaminants for 3D generation. "
            "The headboard, bed frame, slats, and legs are PART of the furniture. "
            "Flag loose pillows, duvets, or decorative items on the mattress surface.\n"
        ),
        "rack_or_thin_structure": (
            "\nIMPORTANT — this is a rack, coat stand, or thin shelf structure. "
            "Hanging clothes, bags, or accessories on the rack are contaminants. "
            "The poles, crossbars, base, and brackets are PART of the furniture. "
            "Do NOT flag the structural frame. Only flag items hung or placed on it.\n"
        ),
        "glass_or_reflective": (
            "\nIMPORTANT — this is a glass table or mirror with reflective surfaces. "
            "Items placed ON the glass surface or AROUND the mirror are contaminants. "
            "The glass panel, metal/wooden frame, and legs are PART of the furniture. "
            "Reflections visible through the glass are NOT contaminants.\n"
        ),
        "closed_body": (
            "\nIMPORTANT — this is a closed-body furniture item (bookshelf, cabinet, dresser). "
            "Items stored ON TOP of the furniture or placed IN FRONT of it are contaminants. "
            "Books on shelves that are inside the unit may also be contaminants for 3D generation. "
            "The cabinet body, doors, drawers, and handles are PART of the furniture.\n"
        ),
        "open_leg_hard": (
            "\nFor desk/table: any independent object on the tabletop surface is a contaminant "
            "(laptop, books, cups, lamps, plants, etc.). "
            "For hard chair: items placed ON the seat are contaminants, the chair itself is not.\n"
        ),
    }
    soft_guidance = _FAMILY_GUIDANCE.get(masking_family, "")

    prompt = (
        f"Analyze this furniture image (type: {furniture_type}) for objects that would "
        "contaminate 3D model generation.\n\n"
        "These are objects placed ON or AROUND the furniture that are NOT part of the "
        "furniture itself, and would be incorrectly baked into a 3D model if left in.\n\n"
        "Target contaminants: books, laptops, tablets, desk lamps, cups, mugs, bottles, "
        "decorative items, remote controls, small boxes, blankets, clutter, personal items.\n\n"
        "Do NOT flag as contaminants:\n"
        "- The furniture structure itself (legs, frame, surface, drawers, backrest)\n"
        f"- Built-in cushions/parts that are included with the {furniture_type}\n"
        "- Handles, knobs, or hardware attached to the furniture\n\n"
        f"For desk/table: any independent object on the tabletop surface is a contaminant.\n"
        f"{soft_guidance}\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "has_generation_contaminants": false,\n'
        '  "contaminant_summary": "",\n'
        '  "contaminants": [\n'
        '    {"name": "tablet", "description": "small black tablet on tabletop", '
        '"location": "rear-left area of tabletop", "removal_priority": "medium"}\n'
        "  ],\n"
        '  "reason": "explanation"\n'
        "}"
    )

    try:
        resp = client.chat.completions.create(
            model=_core.VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
            ]}],
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        contaminants = parsed.get("contaminants", [])
        if not isinstance(contaminants, list):
            contaminants = []

        return {
            "has_generation_contaminants": bool(parsed.get("has_generation_contaminants", False)),
            "contaminant_summary": str(parsed.get("contaminant_summary", "")),
            "contaminants": [
                {
                    "name": str(c.get("name", "unknown")),
                    "description": str(c.get("description", "")),
                    "location": str(c.get("location", "")),
                    "removal_priority": str(c.get("removal_priority", "medium")),
                }
                for c in contaminants if isinstance(c, dict)
            ],
            "reason": str(parsed.get("reason", "")),
        }

    except Exception as e:
        _core._mark_openai_unavailable(e)
        logger.warning("Generation contaminant analysis failed: %s", e)
        return {
            "has_generation_contaminants": False,
            "contaminant_summary": "",
            "contaminants": [],
            "reason": f"analysis_failed: {e}",
        }


# ---------------------------------------------------------------------------
# segment_objects_with_sam3
# ---------------------------------------------------------------------------

def segment_objects_with_sam3(
    image_path: Path,
    objects: list[dict],
    furniture_dino_bbox: list | None = None,
    output_mask_path: Path = None,
    mode: str = "major_obstacle",
) -> dict:
    """Generate union object mask via GroundingDINO + SAM predictor.

    mode="major_obstacle"        : original obstacle segmentation (area threshold 70%).
    mode="generation_contaminant": smaller objects allowed (area threshold 35%),
                                   location info included in prompt.
    Skips detections that match the furniture itself.
    """
    import cv2
    import numpy as np

    img = cv2.imread(str(image_path))
    if img is None:
        return {"status": "failed", "error": "cannot_read_image", "mask_coverage": 0.0}
    h, w = img.shape[:2]

    object_names = [o.get("name", "object") for o in objects]
    if not object_names:
        object_names = ["obstacle on furniture" if mode == "major_obstacle" else "object on furniture"]

    if mode == "generation_contaminant":
        parts = []
        for o in objects:
            name = o.get("name", "object")
            location = o.get("location", "")
            parts.append(f"{name} {location}".strip() if location else name)
        prompt_text = ". ".join(parts) + "." if parts else "object on furniture."
    else:
        prompt_text = ". ".join(object_names) + "."

    area_threshold = 0.35 if mode == "generation_contaminant" else 0.70

    try:
        import torch
        from PIL import Image

        segmenter = _core.get_segmenter()
        gsam = _core._get_gsam(segmenter)

        if not hasattr(gsam, "processor") or not hasattr(gsam, "predictor"):
            return {"status": "failed", "error": "gsam_not_available", "mask_coverage": 0.0}

        pil_image = Image.open(image_path).convert("RGB")
        image_np = np.array(pil_image)

        inputs = gsam.processor(images=pil_image, text=prompt_text, return_tensors="pt")
        inputs = {k: v.to(gsam.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = gsam.detector(**inputs)

        results = gsam.processor.post_process_grounded_object_detection(
            outputs,
            input_ids=inputs.get("input_ids"),
            threshold=0.20,
            text_threshold=0.20,
            target_sizes=[(h, w)],
        )[0]

        boxes = results.get("boxes")
        scores = results.get("scores")

        if boxes is None or len(boxes) == 0:
            logger.warning("SAM3: no detections for: %s", prompt_text)
            return {"status": "no_detections", "error": None, "mask_coverage": 0.0,
                    "prompts_used": object_names}

        gsam.predictor.set_image(image_np)
        union_mask = np.zeros((h, w), dtype=np.uint8)
        obstacle_count = 0

        for i in range(len(boxes)):
            box = boxes[i].detach().cpu().numpy()
            box_w = box[2] - box[0]
            box_h = box[3] - box[1]

            # Skip detections that are too large (likely the furniture itself)
            if (box_w * box_h) / (w * h) > area_threshold:
                continue

            # Skip if this detection is essentially the furniture bbox
            if furniture_dino_bbox:
                dx1, dy1, dx2, dy2 = furniture_dino_bbox
                inter_x1 = max(box[0], dx1)
                inter_y1 = max(box[1], dy1)
                inter_x2 = min(box[2], dx2)
                inter_y2 = min(box[3], dy2)
                if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                    furn_area = max((dx2 - dx1) * (dy2 - dy1), 1)
                    if inter_area / furn_area > 0.85:
                        continue

            masks, sam_scores, _ = gsam.predictor.predict(box=box, multimask_output=True)
            best_idx = int(np.argmax(sam_scores))
            mask = masks[best_idx].astype(np.uint8) * 255
            union_mask = np.maximum(union_mask, mask)
            obstacle_count += 1

        if obstacle_count == 0:
            return {"status": "no_valid_detections", "error": None,
                    "mask_coverage": 0.0, "prompts_used": object_names}

        output_mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_mask_path), union_mask)
        mask_coverage = float(np.count_nonzero(union_mask > 127)) / (h * w)

        seg_warnings = []
        if mask_coverage > 0.60:
            seg_warnings.append("object_mask_very_large_check_if_furniture_included")

        return {
            "status": "done",
            "error": None,
            "mask_coverage": round(mask_coverage, 4),
            "object_count": obstacle_count,
            "prompts_used": object_names,
            "warnings": seg_warnings,
        }

    except Exception as e:
        logger.warning("SAM3 object segmentation failed: %s", e)
        return {"status": "failed", "error": str(e), "mask_coverage": 0.0}


# ---------------------------------------------------------------------------
# inpaint_obstacles_with_lama
# ---------------------------------------------------------------------------

def inpaint_obstacles_with_lama(
    image_path: Path,
    obstacle_mask_path: Path,
    output_path: Path,
) -> dict:
    """Inpaint obstacle regions with LaMa.

    Priority:
    1. IOPaint CLI with LaMa backend
    2. simple_lama_inpainting Python package
    3. Fallback: warn + skip (caller uses original for generation)

    IMPORTANT: Result is for generation/preview only, NOT for measurement.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    BASE_WARNINGS = [
        "inpainting_used",
        "generation_uses_inpainted_image",
        "not_for_measurement",
    ]

    _LAMA_PYTHON = "/opt/miniconda3/envs/lama_env/bin/python"
    _LAMA_WORKER = str(PIPELINE_DIR / "lama_inpaint_worker.py")
    try:
        proc = subprocess.run(
            [_LAMA_PYTHON, _LAMA_WORKER,
             str(image_path), str(obstacle_mask_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode == 0 and output_path.exists():
            logger.info("LaMa inpainting done via lama_env subprocess")
            return {"status": "done", "method": "lama_env_subprocess", "warnings": BASE_WARNINGS}
        else:
            logger.warning("lama_env subprocess failed (code %d): %s",
                           proc.returncode, proc.stderr[:300])
    except Exception as e:
        logger.warning("LaMa subprocess error: %s", e)

    return {
        "status": "failed",
        "method": "lama_unavailable",
        "warnings": [
            "lama_inpainting_failed_fallback_to_original",
            "generation_uses_original_image",
        ],
    }


# ---------------------------------------------------------------------------
# estimate_dimensions
# ---------------------------------------------------------------------------

def estimate_dimensions(
    measurement_image_path: Path,
    title: str,
    description: str,
    furniture_type: str,
    listing_dims: dict | None,
) -> dict:
    """Estimate dimensions: listing text first, vision estimation as fallback.

    Measurement image is always based on original pixels (never inpainted).
    """
    if listing_dims and listing_dims.get("width_cm"):
        is_approx = bool(listing_dims.get("approximate", False))
        return {
            "width_cm": listing_dims["width_cm"],
            "depth_cm": listing_dims.get("depth_cm"),
            "height_cm": listing_dims.get("height_cm"),
            "source": "listing_text",
            "confidence": "high",
            "approximate": is_approx,
            "pattern": listing_dims.get("pattern"),
            "raw_match": listing_dims.get("raw_match"),
            "reasoning": (
                "Dimensions extracted from listing text (approximate)."
                if is_approx else
                "Dimensions extracted directly from listing text."
            ),
        }

    dims = _core.measure_dimensions(
        measurement_image_path,
        title,
        description,
        furniture_type=furniture_type,
    )
    dims.setdefault("source", "vision_estimate")
    return dims


# ---------------------------------------------------------------------------
# evaluate_detection_quality
# ---------------------------------------------------------------------------

def evaluate_detection_quality(
    image_path: Path,
    dino_bbox: list | None,
    furniture_type: str,
    mask_coverage: float | None = None,
) -> dict:
    """Check whether the DINO bbox looks suspiciously large or floor-inclusive."""
    if not dino_bbox:
        return {"quality": "unknown", "warnings": ["no_bbox"]}

    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        return {"quality": "unknown", "warnings": ["cannot_read_image"]}

    h, w = img.shape[:2]
    x1, y1, x2, y2 = dino_bbox
    bbox_w = x2 - x1
    bbox_h = y2 - y1
    img_area = w * h

    bbox_area_ratio = (bbox_w * bbox_h) / img_area
    bbox_width_ratio = bbox_w / w
    bbox_height_ratio = bbox_h / h

    touches_left   = x1 <= 5
    touches_right  = x2 >= w - 5
    touches_bottom = y2 >= h - 5
    touches_top    = y1 <= 5

    det_warnings = []
    if bbox_width_ratio > 0.92:
        det_warnings.append("dino_bbox_too_wide")
    if bbox_area_ratio > 0.55:
        det_warnings.append("dino_bbox_too_large")
    if touches_left and touches_right:
        det_warnings.append("dino_bbox_touches_both_sides")

    floor_furniture = {"desk", "table", "chair", "sofa", "bed", "bookshelf", "cabinet", "dresser"}
    if (furniture_type in floor_furniture
            and touches_bottom
            and mask_coverage is not None
            and mask_coverage > 0.45):
        det_warnings.append("dino_bbox_may_include_floor_or_background")

    quality = "ok" if not det_warnings else ("low" if len(det_warnings) >= 2 else "warning")

    return {
        "bbox_area_ratio": round(bbox_area_ratio, 4),
        "bbox_width_ratio": round(bbox_width_ratio, 4),
        "bbox_height_ratio": round(bbox_height_ratio, 4),
        "touches_left": touches_left,
        "touches_right": touches_right,
        "touches_bottom": touches_bottom,
        "touches_top": touches_top,
        "quality": quality,
        "warnings": det_warnings,
    }


# ---------------------------------------------------------------------------
# evaluate_cutout_quality
# ---------------------------------------------------------------------------

def evaluate_cutout_quality(mask_path: Path, furniture_type: str) -> dict:
    """Inspect the final mask for background/floor leakage."""
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"quality": "unknown", "warnings": ["cannot_read_mask"]}

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8)
    total_pixels = h * w

    mask_coverage = float(np.sum(binary)) / total_pixels
    bottom_edge_contact_ratio = float(np.sum(binary[h - 1, :])) / w
    left_edge_contact_ratio   = float(np.sum(binary[:, 0]))     / h
    right_edge_contact_ratio  = float(np.sum(binary[:, w - 1])) / h

    lower_third = binary[int(h * 2 / 3):, :]
    lower_third_density = (float(np.sum(lower_third)) / lower_third.size
                           if lower_third.size > 0 else 0.0)

    cut_warnings = []
    if mask_coverage > 0.50:
        cut_warnings.append("mask_coverage_high_possible_background_leakage")
    if bottom_edge_contact_ratio > 0.15:
        cut_warnings.append("bottom_edge_contact_high_possible_floor_leakage")

    open_leg_furniture = {"desk", "table", "chair"}
    if furniture_type in open_leg_furniture and lower_third_density > 0.35:
        cut_warnings.append("lower_region_too_dense_for_open_leg_furniture")
    if left_edge_contact_ratio > 0.15:
        cut_warnings.append("left_edge_contact_high_possible_background_leakage")
    if right_edge_contact_ratio > 0.15:
        cut_warnings.append("right_edge_contact_high_possible_background_leakage")
    if furniture_type == "sofa":
        if mask_coverage > 0.55 and bottom_edge_contact_ratio > 0.25 and lower_third_density > 0.65:
            cut_warnings.append("soft_support_surface_leakage_possible")

    quality = "ok" if not cut_warnings else ("low" if len(cut_warnings) >= 2 else "warning")

    return {
        "mask_coverage": round(mask_coverage, 4),
        "bottom_edge_contact_ratio": round(bottom_edge_contact_ratio, 4),
        "left_edge_contact_ratio": round(left_edge_contact_ratio, 4),
        "right_edge_contact_ratio": round(right_edge_contact_ratio, 4),
        "lower_third_density": round(lower_third_density, 4),
        "quality": quality,
        "warnings": cut_warnings,
    }



# ---------------------------------------------------------------------------
# soft_furniture support surface leakage helpers
# ---------------------------------------------------------------------------

def evaluate_soft_support_leakage(mask_path: Path) -> dict:
    """Detect floor/table/support surface leakage in a soft_furniture mask.
    Pure analysis — does not modify the mask.
    """
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"has_support_leakage": False, "warnings": ["cannot_read_mask"]}

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8)
    total  = h * w

    mask_coverage            = float(binary.sum()) / total
    bottom_edge_contact_ratio = float(binary[h - 1, :].sum()) / w
    lower_third = binary[int(h * 2 / 3):, :]
    lower_third_density = float(lower_third.sum()) / max(lower_third.size, 1)
    lower_half  = binary[h // 2:, :]
    lower_half_density  = float(lower_half.sum())  / max(lower_half.size, 1)

    has_support_leakage = (
        mask_coverage > 0.55
        and bottom_edge_contact_ratio > 0.25
        and lower_third_density > 0.65
    )
    return {
        "has_support_leakage": has_support_leakage,
        "mask_coverage": round(mask_coverage, 4),
        "bottom_edge_contact_ratio": round(bottom_edge_contact_ratio, 4),
        "lower_third_density": round(lower_third_density, 4),
        "lower_half_density": round(lower_half_density, 4),
        "reason": (
            "large bottom-connected support surface likely included"
            if has_support_leakage else "no leakage detected"
        ),
    }


def select_best_soft_furniture_sam_mask(
    masks: "np.ndarray",
    sam_scores: "np.ndarray",
    image_shape: tuple,
) -> "np.ndarray | None":
    """Pick the SAM mask with least floor/support surface coverage.
    Used only inside the soft_furniture branch — never called elsewhere.
    """
    import numpy as np

    if len(masks) == 0:
        return None

    h, w = image_shape[0], image_shape[1]
    best_idx   = 0
    best_score = -999.0

    for i, (mask, sam_score) in enumerate(zip(masks, sam_scores)):
        binary = mask.astype(bool)
        total  = h * w

        coverage    = float(binary.sum()) / total
        bottom_cont = float(binary[h - 1, :].sum()) / w
        lt          = binary[int(h * 2 / 3):, :]
        lt_density  = float(lt.sum()) / max(lt.size, 1)
        uh          = binary[:h // 2, :]
        uh_density  = float(uh.sum()) / max(uh.size, 1)

        ys = np.where(binary)[0]
        bbox_h_ratio = ((int(ys.max()) - int(ys.min())) / h) if len(ys) > 0 else 0.0

        score = float(sam_score)
        if bottom_cont > 0.15:
            score -= (bottom_cont - 0.15) * 3.0
        if coverage > 0.55:
            score -= (coverage - 0.55) * 2.0
        if lt_density > 0.70:
            score -= (lt_density - 0.70) * 2.0
        if bbox_h_ratio < 0.40:
            score -= 0.3
        if uh_density < 0.05:
            score -= 0.3

        if score > best_score:
            best_score = score
            best_idx   = i

    return masks[best_idx].astype(np.uint8) * 255


# ---------------------------------------------------------------------------
# generate_sam3_furniture_mask
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Category-to-family mapping (used by get_masking_family)
# ---------------------------------------------------------------------------

CATEGORY_TO_MASKING_FAMILY: dict[str, str] = {
    "desk": "open_leg_hard",
    "table": "open_leg_hard",
    "chair": "open_leg_hard",          # keyword overrides may upgrade to soft_furniture
    "sofa": "soft_furniture",
    "lounge_chair": "soft_furniture",
    "armchair": "soft_furniture",
    "recliner": "soft_furniture",
    "bed": "bed_type",
    "mattress": "bed_type",
    "bookshelf": "closed_body",
    "cabinet": "closed_body",
    "dresser": "closed_body",
    "wardrobe": "closed_body",
    "drawer": "closed_body",
    "rack": "rack_or_thin_structure",
    "shelf": "rack_or_thin_structure",
    "coat_rack": "rack_or_thin_structure",
    "hanger": "rack_or_thin_structure",
    "ladder_shelf": "rack_or_thin_structure",
    "glass_table": "glass_or_reflective",
    "mirror": "glass_or_reflective",
}

# ---------------------------------------------------------------------------
# Per-family prompt configs
# ---------------------------------------------------------------------------

# open_leg_hard: part-based union
OPEN_LEG_PROMPTS: dict[str, list[str]] = {
    "desk":  ["tabletop", "desk legs", "desk frame"],
    "table": ["tabletop", "table legs", "table frame"],
    "chair": ["chair seat", "chair backrest", "chair legs"],
}

# soft_furniture: whole-object first (keyed by subtype for _build_soft_furniture_prompts)
SOFT_FURNITURE_PROMPTS: dict[str, list[str]] = {
    "sofa": [
        "entire sofa including backrest, seat cushion, base, and legs",
        "whole sofa including all back cushions and seat cushions",
        "complete sofa",
    ],
    "lounge_chair": [
        "entire lounge chair including backrest and seat cushion",
        "whole lounge chair including back cushion, seat cushion, base and legs",
        "complete lounge chair",
    ],
    "armchair": [
        "entire armchair including backrest, seat cushion, armrests, and legs",
        "whole armchair including back cushion, seat cushion, base and legs",
        "complete armchair",
    ],
    "recliner": [
        "entire recliner chair including backrest and seat cushion",
        "whole recliner including headrest, backrest, seat, and base",
        "complete recliner chair",
    ],
    "_default": [
        "entire upholstered furniture including backrest and seat cushion",
        "whole upholstered chair including back cushion, seat cushion, base and legs",
        "complete furniture item, not only the seat",
    ],
}

# closed_body: whole-object, single box
CLOSED_BODY_PROMPTS: dict[str, list[str]] = {
    "bookshelf": [
        "entire bookshelf including all shelves and frame",
        "whole bookshelf unit",
        "complete bookshelf",
    ],
    "cabinet": [
        "entire cabinet including doors, frame, and base",
        "whole cabinet unit",
        "complete cabinet",
    ],
    "dresser": [
        "entire dresser including all drawers and frame",
        "whole dresser unit",
        "complete dresser",
    ],
    "wardrobe": [
        "entire wardrobe including doors and frame",
        "whole wardrobe unit",
        "complete wardrobe",
    ],
    "_default": [
        "entire furniture unit including all panels and frame",
        "whole furniture unit",
        "complete furniture",
    ],
}

# bed_type: whole-object, multi-box for bed+mattress separation
BED_TYPE_PROMPTS: dict[str, list[str]] = {
    "bed": [
        "entire bed including headboard, mattress, and frame",
        "whole bed frame including headboard and base",
        "complete bed",
    ],
    "mattress": [
        "entire mattress",
        "whole mattress including sides",
        "complete mattress",
    ],
    "_default": [
        "entire bed furniture including headboard and mattress",
        "whole bed",
        "complete bed including frame",
    ],
}

# rack_or_thin_structure: multi-box union for thin poles/shelves
RACK_THIN_PROMPTS: dict[str, list[str]] = {
    "rack": [
        "entire rack including all poles and shelves",
        "whole rack unit",
        "complete storage rack",
    ],
    "coat_rack": [
        "entire coat rack including pole and base",
        "whole coat rack",
        "complete coat hanger stand",
    ],
    "shelf": [
        "entire shelf unit including all shelves and frame",
        "whole shelf",
        "complete shelf unit",
    ],
    "_default": [
        "entire rack or shelf unit",
        "whole slim furniture structure",
        "complete furniture frame",
    ],
}

# glass_or_reflective: lower detection threshold, whole-object
GLASS_REFLECTIVE_PROMPTS: dict[str, list[str]] = {
    "glass_table": [
        "entire glass table including glass top, metal frame, and legs",
        "whole glass table",
        "complete glass table including transparent top",
    ],
    "mirror": [
        "entire mirror including frame",
        "whole mirror",
        "complete mirror with frame",
    ],
    "_default": [
        "entire glass or reflective furniture",
        "whole furniture including glass or transparent parts",
        "complete furniture",
    ],
}

# Booster prompts for soft_furniture — specific wording reduces background pickup
_SOFT_BOOSTER_PROMPTS = [
    "backrest of the furniture",
    "back cushion of the same furniture",
    "seat cushion of the same furniture",
    "base of the same furniture",
]

# Retry prompts used when soft_furniture mask fails backrest validation
_SOFT_RETRY_PROMPTS = [
    "entire chair including tall backrest and seat cushion",
    "whole sofa chair including backrest cushion, seat cushion, base and legs",
    "complete furniture item, not only the seat",
]


def should_accept_soft_booster_mask(
    candidate_mask: "np.ndarray",
    primary_mask: "np.ndarray",
    primary_bbox: list,
    image_shape: tuple,
    prompt: str = "",
) -> tuple:
    """Return (accept: bool, reasons: list[str]) for a booster candidate vs. primary mask."""
    import numpy as np
    import cv2

    h, w = image_shape[0], image_shape[1]
    px1, py1, px2, py2 = primary_bbox
    primary_h = py2 - py1

    ys, xs = np.where(candidate_mask > 127)
    if len(xs) == 0:
        return False, ["empty_candidate_mask"]

    cx1, cy1, cx2, cy2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    cand_cx = (cx1 + cx2) / 2

    # Filter 1: x-center must be within primary bbox ± 8% image width
    x_margin = w * 0.08
    if cand_cx < px1 - x_margin or cand_cx > px2 + x_margin:
        return False, [f"x_center_too_far (cand_cx={cand_cx:.0f} primary=[{px1},{px2}])"]

    # Filter 2: IoU >= 0.03 → accept
    inter_area = (max(0, min(px2, cx2) - max(px1, cx1)) *
                  max(0, min(py2, cy2) - max(py1, cy1)))
    cand_area = (cx2 - cx1) * (cy2 - cy1)
    prim_area = (px2 - px1) * (py2 - py1)
    iou = inter_area / max(prim_area + cand_area - inter_area, 1)
    if iou >= 0.03:
        return True, [f"iou_ok ({iou:.3f})"]

    # Filter 3: candidate directly above primary (backrest case)
    if cy2 <= py1 + primary_h * 0.3 and px1 <= cand_cx <= px2:
        return True, ["above_primary_backrest_case"]

    # Filter 4: dilation contact with primary mask
    dil_size = max(25, int(min(h, w) * 0.03))
    kernel = np.ones((dil_size, dil_size), np.uint8)
    dilated_primary = cv2.dilate(primary_mask, kernel, iterations=1)
    if np.any((dilated_primary > 127) & (candidate_mask > 127)):
        return True, ["dilation_contact_ok"]

    # Filter 5: candidate y-range within primary y-range
    if cy1 >= py1 - primary_h * 0.1 and cy2 <= py2 + primary_h * 0.1:
        return True, ["within_primary_y_range"]

    return False, ["no_spatial_connection"]


def cleanup_soft_furniture_external_components(
    mask_path: Path,
    image_path: Path,
    primary_bbox: list | None,
) -> dict:
    """Remove disconnected external components from soft furniture mask."""
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"status": "failed", "removed_external_components": 0,
                "kept_components": 0, "warnings": ["cannot_read_mask"]}

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8) * 255
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    if num_labels <= 2:
        return {"status": "skipped", "removed_external_components": 0,
                "kept_components": num_labels - 1, "warnings": []}

    # Find main component: weighted by primary_bbox overlap + area
    def _primary_overlap(i: int) -> float:
        if not primary_bbox:
            return 0.0
        px1, py1, px2, py2 = primary_bbox
        cx1 = stats[i, cv2.CC_STAT_LEFT]
        cy1 = stats[i, cv2.CC_STAT_TOP]
        cx2 = cx1 + stats[i, cv2.CC_STAT_WIDTH]
        cy2 = cy1 + stats[i, cv2.CC_STAT_HEIGHT]
        return float(max(0, min(px2, cx2) - max(px1, cx1)) *
                     max(0, min(py2, cy2) - max(py1, cy1)))

    scores = [_primary_overlap(i) * 0.7 + stats[i, cv2.CC_STAT_AREA] * 0.3
              for i in range(1, num_labels)]
    main_idx = int(np.argmax(scores)) + 1

    main_mask = (labels == main_idx).astype(np.uint8) * 255
    dil_size = max(30, int(min(h, w) * 0.04))
    kernel = np.ones((dil_size, dil_size), np.uint8)
    dilated_main = cv2.dilate(main_mask, kernel, iterations=1)

    result = main_mask.copy()
    removed = 0
    kept = 1

    for i in range(1, num_labels):
        if i == main_idx:
            continue
        comp_mask = (labels == i).astype(np.uint8) * 255
        comp_area = int(stats[i, cv2.CC_STAT_AREA])
        cx1 = stats[i, cv2.CC_STAT_LEFT]
        cy1 = stats[i, cv2.CC_STAT_TOP]
        cx2 = cx1 + stats[i, cv2.CC_STAT_WIDTH]
        cy2 = cy1 + stats[i, cv2.CC_STAT_HEIGHT]
        comp_cx = (cx1 + cx2) / 2
        comp_cy = (cy1 + cy2) / 2

        keep = False
        reason = ""
        if np.any((dilated_main > 127) & (comp_mask > 127)):
            keep = True
            reason = "dilation_contact"
        elif primary_bbox:
            px1, py1, px2, py2 = primary_bbox
            if (px1 - w * 0.05 <= comp_cx <= px2 + w * 0.05 and
                    py1 - h * 0.05 <= comp_cy <= py2 + h * 0.05):
                keep = True
                reason = "within_primary_bbox"

        if keep:
            result = np.maximum(result, comp_mask)
            kept += 1
            logger.info("Soft cleanup: kept %d area=%d (%s)", i, comp_area, reason)
        else:
            removed += 1
            logger.info("Soft cleanup: removed %d area=%d cx=%.0f cy=%.0f",
                        i, comp_area, comp_cx, comp_cy)

    cv2.imwrite(str(mask_path), result)
    warn = ["external_components_removed_from_soft_furniture_mask"] if removed > 0 else []
    return {
        "status": "done",
        "removed_external_components": removed,
        "kept_components": kept,
        "warnings": warn,
    }


def preserve_thin_structure_mask(mask_path: Path, dilation_px: int = 3) -> dict:
    """Apply slight dilation to preserve thin structure details (rack/shelf poles)."""
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"status": "failed", "dilation_px": 0, "warnings": ["cannot_read_mask"]}
    kernel = np.ones((dilation_px, dilation_px), np.uint8)
    dilated = cv2.dilate(mask, kernel, iterations=1)
    cv2.imwrite(str(mask_path), dilated)
    return {"status": "done", "dilation_px": dilation_px, "warnings": []}


def cleanup_closed_body_small_noise(mask_path: Path, min_area_ratio: float = 0.005) -> dict:
    """Remove small disconnected noise components from closed_body mask."""
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"status": "failed", "removed_components": 0, "warnings": ["cannot_read_mask"]}

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8) * 255
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    if num_labels <= 2:
        return {"status": "skipped", "removed_components": 0, "warnings": []}

    areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, num_labels)]
    main_idx = int(np.argmax(areas)) + 1
    min_area = int(h * w * min_area_ratio)

    result = (labels == main_idx).astype(np.uint8) * 255
    removed = 0
    for i in range(1, num_labels):
        if i == main_idx:
            continue
        if int(stats[i, cv2.CC_STAT_AREA]) >= min_area:
            result = np.maximum(result, (labels == i).astype(np.uint8) * 255)
        else:
            removed += 1

    cv2.imwrite(str(mask_path), result)
    return {
        "status": "done",
        "removed_components": removed,
        "warnings": ["small_noise_removed"] if removed > 0 else [],
    }


def get_masking_family(furniture_type: str, title: str = "", description: str = "") -> str:
    """Return masking family: open_leg_hard / soft_furniture / closed_body / bed_type /
    rack_or_thin_structure / glass_or_reflective / generic."""
    combined = f"{title} {description}".lower()

    _RACK_KW = {"행거", "rack", "ladder shelf", "coat rack", "옷걸이 스탠드", "coat hanger stand"}
    _GLASS_KW = {"유리 테이블", "glass table", "유리 책상", "거울", "mirror"}
    _SOFT_KW = {
        "소파", "좌식의자", "리클라이너", "라운지", "벤치형", "소파베드",
        "lounge", "recliner", "daybed", "sofa bed", "armchair",
    }
    _CHAIR_SOFT_KW = {
        "cushion", "lounge", "recliner", "sofa", "daybed",
        "좌식", "리클라이너", "소파베드", "라운지",
    }
    _BED_KW = {"침대", "bed", "매트리스", "mattress", "데이베드", "daybed"}

    # Keyword overrides take highest priority
    if any(kw in combined for kw in _RACK_KW):
        return "rack_or_thin_structure"
    if any(kw in combined for kw in _GLASS_KW):
        return "glass_or_reflective"
    if any(kw in combined for kw in _SOFT_KW):
        return "soft_furniture"

    if furniture_type == "chair":
        if any(kw in combined for kw in _CHAIR_SOFT_KW):
            return "soft_furniture"
        return "open_leg_hard"

    # Type-based lookup from config dict
    base_family = CATEGORY_TO_MASKING_FAMILY.get(furniture_type)
    if base_family:
        return base_family

    # Fallback keyword detection for unknown types
    if any(kw in combined for kw in _BED_KW):
        return "bed_type"
    if furniture_type in {"desk", "table"}:
        return "open_leg_hard"
    if furniture_type in {"sofa", "lounge_chair", "armchair", "recliner"}:
        return "soft_furniture"
    if furniture_type in {"bookshelf", "cabinet", "dresser", "wardrobe"}:
        return "closed_body"
    return "generic"


def infer_category_subtype(
    furniture_type: str,
    masking_family: str,
    title: str = "",
    description: str = "",
) -> str:
    """Return a descriptive category subtype string for strategy tracking."""
    combined = f"{title} {description}".lower()

    if masking_family == "open_leg_hard":
        if furniture_type == "desk":
            if any(k in combined for k in ["스탠딩", "standing", "높이조절", "height adjustable"]):
                return "standing_desk"
            _SHELF_KW = ["선반", "책장", "수납", "랙", "shelf", "rack", "bookshelf", "hutch"]
            if any(k in combined for k in _SHELF_KW):
                return "desk_with_shelf"
            return "standard_desk"
        if furniture_type == "table":
            if any(k in combined for k in ["식탁", "dining", "coffee", "커피", "티테이블"]):
                return "dining_or_coffee_table"
            return "standard_table"
        if furniture_type == "chair":
            return "hard_chair"

    if masking_family == "soft_furniture":
        if any(k in combined for k in ["리클라이너", "recliner"]):
            return "recliner"
        if any(k in combined for k in ["좌식", "lounge", "라운지"]):
            return "lounge_chair"
        if any(k in combined for k in ["소파", "sofa"]) or furniture_type == "sofa":
            return "sofa"
        if any(k in combined for k in ["armchair", "암체어"]):
            return "armchair"
        return "soft_chair"

    if masking_family == "bed_type":
        if any(k in combined for k in ["매트리스", "mattress"]):
            return "mattress_only"
        if any(k in combined for k in ["싱글", "single", "1인"]):
            return "single_bed"
        if any(k in combined for k in ["더블", "double", "퀸", "queen", "킹", "king"]):
            return "double_bed"
        return "standard_bed"

    if masking_family == "closed_body":
        if any(k in combined for k in ["책장", "bookshelf", "서재"]):
            return "bookshelf"
        if any(k in combined for k in ["옷장", "wardrobe", "장롱"]):
            return "wardrobe"
        if any(k in combined for k in ["서랍", "dresser", "서랍장"]):
            return "dresser"
        return "cabinet"

    if masking_family == "rack_or_thin_structure":
        if any(k in combined for k in ["행거", "coat_rack", "옷걸이", "coat rack"]):
            return "coat_rack"
        if any(k in combined for k in ["사다리", "ladder"]):
            return "ladder_shelf"
        return "standard_rack"

    if masking_family == "glass_or_reflective":
        if any(k in combined for k in ["유리", "glass"]):
            return "glass_table"
        if any(k in combined for k in ["거울", "mirror"]):
            return "mirror"
        return "glass_generic"

    return "generic"


def _build_soft_furniture_prompts(
    furniture_type: str, title: str, description: str
) -> list[str]:
    """Return whole-object prompts for soft_furniture strategy."""
    combined = f"{title} {description}".lower()
    is_recliner = any(k in combined for k in ["리클라이너", "recliner"])
    is_lounge   = any(k in combined for k in ["라운지", "lounge", "좌식"])
    is_sofa     = any(k in combined for k in ["소파", "sofa"]) or furniture_type == "sofa"
    is_bed      = any(k in combined for k in ["침대", "bed", "매트리스", "mattress", "데이베드", "daybed"])

    if is_recliner:
        return [
            "entire recliner chair including backrest and seat cushion",
            "whole recliner including headrest, backrest, seat, and base",
            "complete recliner chair",
        ]
    if is_lounge:
        return [
            "entire lounge chair including backrest and seat cushion",
            "whole lounge chair including back cushion, seat cushion, base and legs",
            "complete lounge chair",
        ]
    if is_sofa:
        return [
            "entire sofa including backrest, seat cushion, base, and legs",
            "whole sofa including all back cushions and seat cushions",
            "complete sofa",
        ]
    if is_bed:
        return [
            "entire bed including headboard, mattress, and frame",
            "whole bed frame including headboard and base",
            "complete bed",
        ]
    return [
        "entire upholstered furniture including backrest and seat cushion",
        "whole upholstered chair including back cushion, seat cushion, base and legs",
        "complete furniture item, not only the seat",
    ]


def generate_sam3_furniture_mask(
    image_path: Path,
    furniture_type: str,
    output_mask_path: Path,
    title: str = "",
    description: str = "",
    debug_dir: Path | None = None,
) -> dict:
    """Generate furniture mask using family-aware SAM3 strategy. No DINO bbox required."""
    import cv2
    import numpy as np

    masking_family = get_masking_family(furniture_type, title, description)

    img = cv2.imread(str(image_path))
    if img is None:
        return {"status": "failed", "error": "cannot_read_image",
                "masking_family": masking_family, "valid_part_count": 0}
    h, w = img.shape[:2]

    try:
        import torch
        from PIL import Image as _PIL_Image

        segmenter = _core.get_segmenter()
        gsam = _core._get_gsam(segmenter)

        if not hasattr(gsam, "processor") or not hasattr(gsam, "predictor"):
            return {"status": "failed", "error": "gsam_not_available",
                    "masking_family": masking_family, "valid_part_count": 0}

        pil_image = _PIL_Image.open(image_path).convert("RGB")
        image_np = np.array(pil_image)
        gsam.predictor.set_image(image_np)

        union_mask = np.zeros((h, w), dtype=np.uint8)
        prompts_used: list[str] = []

        def _detect_and_union(prompt: str, max_area_ratio: float,
                              min_score: float = 0.20, multi_box: bool = False) -> int:
            """Run GSAM for prompt, SAM-predict each valid box, union into union_mask."""
            nonlocal union_mask
            inputs = gsam.processor(images=pil_image, text=prompt + ".", return_tensors="pt")
            inputs = {k: v.to(gsam.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = gsam.detector(**inputs)
            results = gsam.processor.post_process_grounded_object_detection(
                outputs,
                input_ids=inputs.get("input_ids"),
                threshold=min_score,
                text_threshold=min_score,
                target_sizes=[(h, w)],
            )[0]
            boxes = results.get("boxes")
            scores = results.get("scores")
            if boxes is None or len(boxes) == 0:
                logger.info("SAM3 '%s': no detections", prompt)
                return 0

            indices = list(range(len(boxes))) if multi_box else [int(torch.argmax(scores).item())]
            added = 0
            for i in indices:
                if float(scores[i].item()) < min_score:
                    continue
                box = boxes[i].detach().cpu().numpy()
                bw, bh = box[2] - box[0], box[3] - box[1]
                if (bw * bh) / (w * h) > max_area_ratio:
                    logger.info("SAM3 '%s' box %d: area ratio %.2f > %.2f, skip",
                                prompt, i, (bw * bh) / (w * h), max_area_ratio)
                    continue
                masks, sam_scores, _ = gsam.predictor.predict(box=box, multimask_output=True)
                best_idx = int(np.argmax(sam_scores))
                part_mask = masks[best_idx].astype(np.uint8) * 255
                cov = float(np.count_nonzero(part_mask > 127)) / (h * w)
                if cov < 0.001 or cov > max_area_ratio:
                    logger.info("SAM3 '%s' box %d: coverage %.3f out of range, skip",
                                prompt, i, cov)
                    continue
                union_mask = np.maximum(union_mask, part_mask)
                added += 1
                logger.info("SAM3 '%s' box %d: accepted (coverage=%.3f)", prompt, i, cov)
            return added

        def _collect_masks(prompt: str, max_area_ratio: float,
                           min_score: float = 0.20, multi_box: bool = False) -> list:
            """Run GSAM for prompt, return list of SAM masks without unioning."""
            inputs = gsam.processor(images=pil_image, text=prompt + ".", return_tensors="pt")
            inputs = {k: v.to(gsam.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = gsam.detector(**inputs)
            results = gsam.processor.post_process_grounded_object_detection(
                outputs,
                input_ids=inputs.get("input_ids"),
                threshold=min_score,
                text_threshold=min_score,
                target_sizes=[(h, w)],
            )[0]
            boxes = results.get("boxes")
            scores = results.get("scores")
            if boxes is None or len(boxes) == 0:
                logger.info("SAM3 '%s': no detections", prompt)
                return []
            indices = list(range(len(boxes))) if multi_box else [int(torch.argmax(scores).item())]
            collected = []
            for i in indices:
                if float(scores[i].item()) < min_score:
                    continue
                box = boxes[i].detach().cpu().numpy()
                bw, bh = box[2] - box[0], box[3] - box[1]
                if (bw * bh) / (w * h) > max_area_ratio:
                    logger.info("SAM3 '%s' box %d: area %.2f > %.2f, skip",
                                prompt, i, (bw * bh) / (w * h), max_area_ratio)
                    continue
                masks, sam_scores, _ = gsam.predictor.predict(box=box, multimask_output=True)
                best_idx = int(np.argmax(sam_scores))
                part_mask = masks[best_idx].astype(np.uint8) * 255
                cov = float(np.count_nonzero(part_mask > 127)) / (h * w)
                if cov < 0.001 or cov > max_area_ratio:
                    logger.info("SAM3 '%s' box %d: coverage %.3f out of range, skip",
                                prompt, i, cov)
                    continue
                collected.append(part_mask)
                logger.info("SAM3 '%s' box %d: collected (coverage=%.3f)", prompt, i, cov)
            return collected

        def _collect_soft_masks(prompt: str, max_area_ratio: float,
                                min_score: float = 0.20, multi_box: bool = False) -> list:
            """Like _collect_masks but uses select_best_soft_furniture_sam_mask
            to pick the SAM candidate with least floor/support-surface coverage.
            Only called inside the soft_furniture branch.
            """
            inputs = gsam.processor(images=pil_image, text=prompt + ".", return_tensors="pt")
            inputs = {k: v.to(gsam.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = gsam.detector(**inputs)
            results = gsam.processor.post_process_grounded_object_detection(
                outputs,
                input_ids=inputs.get("input_ids"),
                threshold=min_score,
                text_threshold=min_score,
                target_sizes=[(h, w)],
            )[0]
            boxes  = results.get("boxes")
            scores = results.get("scores")
            if boxes is None or len(boxes) == 0:
                logger.info("SAM3-soft '%s': no detections", prompt)
                return []
            indices = list(range(len(boxes))) if multi_box else [int(torch.argmax(scores).item())]
            collected = []
            for i in indices:
                if float(scores[i].item()) < min_score:
                    continue
                box = boxes[i].detach().cpu().numpy()
                bw, bh = box[2] - box[0], box[3] - box[1]
                if (bw * bh) / (w * h) > max_area_ratio:
                    logger.info("SAM3-soft '%s' box %d: area %.2f > %.2f, skip",
                                prompt, i, (bw * bh) / (w * h), max_area_ratio)
                    continue
                masks_out, sam_s, _ = gsam.predictor.predict(box=box, multimask_output=True)
                part_mask = select_best_soft_furniture_sam_mask(masks_out, sam_s, (h, w))
                if part_mask is None:
                    continue
                cov = float(np.count_nonzero(part_mask > 127)) / (h * w)
                if cov < 0.001 or cov > max_area_ratio:
                    logger.info("SAM3-soft '%s' box %d: coverage %.3f out of range, skip",
                                prompt, i, cov)
                    continue
                collected.append(part_mask)
                logger.info("SAM3-soft '%s' box %d: collected (coverage=%.3f)", prompt, i, cov)
            return collected

        # ── Strategy dispatch ─────────────────────────────────────────────
        valid_parts = 0
        method = "sam3_only_part_union"
        primary_soft_mask: "np.ndarray | None" = None
        primary_soft_bbox: "list | None" = None
        category_subtype = infer_category_subtype(furniture_type, masking_family, title, description)
        thin_structure_info: dict = {}
        closed_body_cleanup_info: dict = {}

        if masking_family == "open_leg_hard":
            part_prompts = OPEN_LEG_PROMPTS.get(furniture_type, [furniture_type])
            for part in part_prompts:
                is_legs = "leg" in part.lower()
                added = _detect_and_union(part, max_area_ratio=0.85, multi_box=is_legs)
                if added > 0:
                    valid_parts += added
                    prompts_used.append(part)

            # desk_with_shelf: booster prompts for attached shelf structure
            if category_subtype == "desk_with_shelf" and valid_parts > 0:
                desk_primary = union_mask.copy()
                ys_dp, xs_dp = np.where(desk_primary > 127)
                if len(xs_dp) > 0:
                    _shelf_boosters = [
                        "side shelf attached to desk",
                        "vertical shelf frame attached to desk",
                        "horizontal shelf board attached to desk",
                        "desk side rack structure",
                    ]
                    dil_size = max(20, int(min(h, w) * 0.03))
                    dil_kernel = np.ones((dil_size, dil_size), np.uint8)
                    dilated_desk = cv2.dilate(desk_primary, dil_kernel, iterations=1)
                    for sbp in _shelf_boosters:
                        for cand in _collect_masks(sbp, max_area_ratio=0.60, multi_box=True):
                            if np.any((dilated_desk > 127) & (cand > 127)):
                                union_mask = np.maximum(union_mask, cand)
                                valid_parts += 1
                                if sbp not in prompts_used:
                                    prompts_used.append(sbp)
                                logger.info("SAM3 desk_with_shelf booster '%s': accepted", sbp)
                            else:
                                logger.info("SAM3 desk_with_shelf booster '%s': rejected "
                                            "(no dilation contact)", sbp)

        elif masking_family == "soft_furniture":
            method = "sam3_only_whole_object_first"
            whole_prompts = _build_soft_furniture_prompts(furniture_type, title, description)

            # Step 1: whole-object — first successful prompt → saved as primary
            # _collect_soft_masks picks the SAM candidate with least floor coverage
            for wp in whole_prompts:
                wp_masks = _collect_soft_masks(wp, max_area_ratio=0.92, multi_box=False)
                if wp_masks:
                    primary_soft_mask = wp_masks[0]
                    union_mask = np.maximum(union_mask, primary_soft_mask)
                    ys_p, xs_p = np.where(primary_soft_mask > 127)
                    if len(xs_p) > 0:
                        primary_soft_bbox = [int(xs_p.min()), int(ys_p.min()),
                                             int(xs_p.max()), int(ys_p.max())]
                    valid_parts += 1
                    prompts_used.append(wp)
                    logger.info("SAM3 whole-object '%s': accepted, primary_bbox=%s",
                                wp, primary_soft_bbox)
                    break

            # Step 2: booster prompts — spatially filtered against primary mask
            if primary_soft_mask is not None and primary_soft_bbox is not None:
                for bp in _SOFT_BOOSTER_PROMPTS:
                    bp_added = 0
                    for cand in _collect_masks(bp, max_area_ratio=0.70, multi_box=True):
                        accept, reasons = should_accept_soft_booster_mask(
                            cand, primary_soft_mask, primary_soft_bbox, (h, w), prompt=bp,
                        )
                        if accept:
                            union_mask = np.maximum(union_mask, cand)
                            bp_added += 1
                            logger.info("SAM3 booster '%s': accepted (%s)", bp, reasons)
                        else:
                            logger.info("SAM3 booster '%s': rejected (%s)", bp, reasons)
                    if bp_added > 0:
                        valid_parts += bp_added
                        prompts_used.append(bp)

        elif masking_family == "bed_type":
            method = "sam3_only_whole_object_multi_box"
            bed_prompts = BED_TYPE_PROMPTS.get(furniture_type,
                                               BED_TYPE_PROMPTS["_default"])
            for wp in bed_prompts:
                added = _detect_and_union(wp, max_area_ratio=0.95, multi_box=True)
                if added > 0:
                    valid_parts += added
                    prompts_used.append(wp)
                    break

        elif masking_family == "rack_or_thin_structure":
            method = "sam3_only_thin_structure_multi_box"
            rack_prompts = RACK_THIN_PROMPTS.get(furniture_type,
                                                  RACK_THIN_PROMPTS["_default"])
            for wp in rack_prompts:
                added = _detect_and_union(wp, max_area_ratio=0.90, multi_box=True)
                if added > 0:
                    valid_parts += added
                    prompts_used.append(wp)
                    break

        elif masking_family == "glass_or_reflective":
            method = "sam3_only_glass_low_threshold"
            glass_prompts = GLASS_REFLECTIVE_PROMPTS.get(furniture_type,
                                                          GLASS_REFLECTIVE_PROMPTS["_default"])
            for wp in glass_prompts:
                added = _detect_and_union(wp, max_area_ratio=0.95,
                                          min_score=0.15, multi_box=False)
                if added > 0:
                    valid_parts += added
                    prompts_used.append(wp)
                    break

        elif masking_family == "closed_body":
            method = "sam3_only_whole_object"
            closed_prompts = CLOSED_BODY_PROMPTS.get(furniture_type,
                                                      CLOSED_BODY_PROMPTS["_default"])
            for wp in closed_prompts:
                added = _detect_and_union(wp, max_area_ratio=0.90, multi_box=False)
                if added > 0:
                    valid_parts += added
                    prompts_used.append(wp)
                    break

        else:  # generic
            for wp in [furniture_type, f"entire {furniture_type}"]:
                added = _detect_and_union(wp, max_area_ratio=0.90, multi_box=False)
                if added > 0:
                    valid_parts += added
                    prompts_used.append(wp)
                    break

        if valid_parts == 0:
            return {"status": "failed", "error": "no_valid_parts_detected",
                    "masking_family": masking_family, "category_subtype": category_subtype,
                    "prompts_used": prompts_used, "valid_part_count": 0}

        output_mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_mask_path), union_mask)

        # ── Post-processing per family ─────────────────────────────────────
        mask_validation: dict = {}
        soft_cleanup_info: dict = {}
        support_cleanup_info: dict = {"status": "skipped", "support_leakage_detected": False,
                                      "support_removed": False, "warnings": []}

        if masking_family == "soft_furniture":
            mask_validation = validate_soft_furniture_mask(output_mask_path, image_path)
            if not mask_validation.get("valid", True):
                logger.warning("Soft furniture mask: backrest validation failed %s — retrying",
                               mask_validation.get("warnings"))
                for rp in _SOFT_RETRY_PROMPTS:
                    added = _detect_and_union(rp, max_area_ratio=0.92, multi_box=False)
                    if added > 0:
                        valid_parts += added
                        prompts_used.append(f"retry:{rp}")
                cv2.imwrite(str(output_mask_path), union_mask)
                mask_validation = validate_soft_furniture_mask(output_mask_path, image_path)

            # External component cleanup: remove radiators, background objects, etc.
            soft_cleanup_info = cleanup_soft_furniture_external_components(
                output_mask_path, image_path, primary_soft_bbox,
            )
            if soft_cleanup_info.get("removed_external_components", 0) > 0:
                cleaned = cv2.imread(str(output_mask_path), cv2.IMREAD_GRAYSCALE)
                if cleaned is not None:
                    union_mask = cleaned

            # Support surface leakage cleanup (floor/table under soft furniture)
            support_cleanup_info = cleanup_soft_support_surface_leakage(
                image_path=image_path,
                mask_path=output_mask_path,
                output_mask_path=output_mask_path,
                furniture_type=furniture_type,
                category_subtype=category_subtype,
                debug_dir=debug_dir,
            )
            if support_cleanup_info.get("support_removed", False):
                reloaded_sup = cv2.imread(str(output_mask_path), cv2.IMREAD_GRAYSCALE)
                if reloaded_sup is not None:
                    union_mask = reloaded_sup
                    logger.info("Soft support surface removed: coverage %.3f→%.3f",
                                support_cleanup_info.get("coverage_before", 0),
                                support_cleanup_info.get("coverage_after", 0))

        elif masking_family == "rack_or_thin_structure":
            thin_structure_info = preserve_thin_structure_mask(output_mask_path, dilation_px=3)
            reloaded = cv2.imread(str(output_mask_path), cv2.IMREAD_GRAYSCALE)
            if reloaded is not None:
                union_mask = reloaded

        elif masking_family == "closed_body":
            closed_body_cleanup_info = cleanup_closed_body_small_noise(output_mask_path)
            reloaded = cv2.imread(str(output_mask_path), cv2.IMREAD_GRAYSCALE)
            if reloaded is not None:
                union_mask = reloaded

        mask_coverage = float(np.count_nonzero(union_mask > 127)) / (h * w)
        ys, xs = np.where(union_mask > 127)
        bbox = ([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                if len(xs) > 0 else None)

        # Risk and review flags per family
        _HIGH_RISK = {"glass_or_reflective", "bed_type", "rack_or_thin_structure"}
        risk_level = "high" if masking_family in _HIGH_RISK else "normal"
        manual_review_recommended = masking_family in _HIGH_RISK

        logger.info("SAM3-only mask done: family=%s subtype=%s method=%s "
                    "valid_parts=%d coverage=%.3f",
                    masking_family, category_subtype, method, valid_parts, mask_coverage)
        return {
            "status": "done",
            "method": method,
            "masking_family": masking_family,
            "category_subtype": category_subtype,
            "risk_level": risk_level,
            "manual_review_recommended": manual_review_recommended,
            "primary_prompts": prompts_used[:3],
            "booster_prompts": [p for p in prompts_used if p in _SOFT_BOOSTER_PROMPTS],
            "cleanup_applied": (
                ["thin_structure_dilation"] if thin_structure_info.get("status") == "done"
                else (["closed_body_noise_removal"] if closed_body_cleanup_info.get("status") == "done"
                      else (
                          (["soft_external_cleanup"] if soft_cleanup_info.get("status") == "done" else [])
                          + (["soft_support_surface_cleanup"] if support_cleanup_info.get("support_removed") else
                             (["soft_support_cleanup_reverted"] if support_cleanup_info.get("status") == "reverted" else []))
                      ))
            ),
            "protected_parts": (
                ["backrest", "seat_cushion"] if masking_family == "soft_furniture"
                else (["thin_poles", "shelf_brackets"] if masking_family == "rack_or_thin_structure"
                      else [])
            ),
            "prompts_used": prompts_used,
            "valid_part_count": valid_parts,
            "mask_coverage": round(mask_coverage, 4),
            "bbox": bbox,
            "primary_soft_bbox": primary_soft_bbox,
            "mask_validation": mask_validation,
            "soft_cleanup_info": soft_cleanup_info,
            "soft_support_cleanup_info": support_cleanup_info,
            "thin_structure_info": thin_structure_info,
            "closed_body_cleanup_info": closed_body_cleanup_info,
            "warnings": (
                mask_validation.get("warnings", [])
                + support_cleanup_info.get("warnings", [])
            ),
        }

    except Exception as e:
        logger.warning("generate_sam3_furniture_mask failed: %s", e)
        return {"status": "failed", "error": str(e),
                "masking_family": masking_family, "valid_part_count": 0}


# ---------------------------------------------------------------------------
# validate_soft_furniture_mask
# ---------------------------------------------------------------------------

def validate_soft_furniture_mask(mask_path: Path, image_path: Path) -> dict:
    """Check that a soft-furniture mask plausibly covers the backrest region."""
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    img  = cv2.imread(str(image_path))
    if mask is None or img is None:
        return {"valid": False, "warnings": ["cannot_read_inputs"]}

    h, w = mask.shape
    binary = mask > 127
    if not np.any(binary):
        return {"valid": False, "warnings": ["empty_mask"]}

    ys, _ = np.where(binary)
    y_min, y_max = int(ys.min()), int(ys.max())
    bbox_height_ratio = (y_max - y_min) / h
    bbox_y_min_ratio  = y_min / h

    upper_half = binary[:h // 2, :]
    upper_half_density = float(np.sum(upper_half)) / max(upper_half.size, 1)

    warn = []
    if bbox_height_ratio < 0.45:
        warn.append("backrest_missing_possible_bbox_too_short")
    if bbox_y_min_ratio > 0.30:
        warn.append("upper_backrest_likely_missing")
    if upper_half_density < 0.05:
        warn.append("backrest_missing_possible_upper_half_empty")

    return {
        "valid": len(warn) == 0,
        "bbox_height_ratio": round(bbox_height_ratio, 3),
        "bbox_y_min_ratio": round(bbox_y_min_ratio, 3),
        "upper_half_density": round(upper_half_density, 4),
        "warnings": warn,
    }


# ---------------------------------------------------------------------------
# cleanup_soft_support_surface_leakage
# ---------------------------------------------------------------------------

def cleanup_soft_support_surface_leakage(
    image_path: Path,
    mask_path: Path,
    output_mask_path: Path,
    furniture_type: str,
    category_subtype: str,
    debug_dir: Path | None = None,
) -> dict:
    """Remove floor/table/support surface leakage from a soft_furniture mask.

    Only runs when evaluate_soft_support_leakage() confirms leakage.
    Reverts to original mask if cleanup would damage the furniture silhouette.
    """
    import cv2
    import numpy as np

    leakage = evaluate_soft_support_leakage(mask_path)
    if not leakage["has_support_leakage"]:
        return {
            "status": "skipped",
            "support_leakage_detected": False,
            "support_removed": False,
            "coverage_before": leakage["mask_coverage"],
            "coverage_after": leakage["mask_coverage"],
            "bottom_edge_contact_before": leakage["bottom_edge_contact_ratio"],
            "bottom_edge_contact_after": leakage["bottom_edge_contact_ratio"],
            "warnings": [],
        }

    logger.info("Soft support surface leakage detected: coverage=%.3f bottom=%.3f lower3=%.3f",
                leakage["mask_coverage"], leakage["bottom_edge_contact_ratio"],
                leakage["lower_third_density"])

    orig_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if orig_mask is None:
        return {"status": "failed", "support_leakage_detected": True, "support_removed": False,
                "warnings": ["cannot_read_mask"]}

    h, w = orig_mask.shape
    orig_binary       = (orig_mask > 127).astype(np.uint8)
    coverage_before   = leakage["mask_coverage"]
    bottom_before     = leakage["bottom_edge_contact_ratio"]

    # Protected core: eroded body + upper portion of bbox
    erode_k    = max(15, int(min(h, w) * 0.04))
    kernel     = np.ones((erode_k, erode_k), np.uint8)
    prot_erode = cv2.erode(orig_mask, kernel, iterations=1)

    ys_orig = np.where(orig_binary)[0]
    if len(ys_orig) == 0:
        return {"status": "skipped", "support_leakage_detected": True, "support_removed": False,
                "warnings": ["empty_original_mask"]}
    y_min_o  = int(ys_orig.min())
    y_mid_o  = int(ys_orig.min() + (ys_orig.max() - ys_orig.min()) * 0.55)
    prot_upper = np.zeros((h, w), np.uint8)
    prot_upper[:y_mid_o, :] = 255
    protected_mask = np.maximum(prot_erode, prot_upper)

    try:
        segmenter = _core.get_segmenter()
        gsam      = _core._get_gsam(segmenter)
        if not hasattr(gsam, "processor") or not hasattr(gsam, "predictor"):
            raise RuntimeError("gsam_not_available")

        import torch
        from PIL import Image as _PIL
        pil_image = _PIL.open(image_path).convert("RGB")
        image_np  = np.array(pil_image)
        gsam.predictor.set_image(image_np)

        _SUPPORT_PROMPTS = [
            "floor under the sofa",
            "table surface under the chair",
            "support surface under the furniture",
            "platform under the sofa",
            "background floor below the furniture",
        ]

        support_union = np.zeros((h, w), np.uint8)
        for sp in _SUPPORT_PROMPTS:
            inp = gsam.processor(images=pil_image, text=sp + ".", return_tensors="pt")
            inp = {k: v.to(gsam.device) for k, v in inp.items()}
            with torch.no_grad():
                out = gsam.detector(**inp)
            res = gsam.processor.post_process_grounded_object_detection(
                out,
                input_ids=inp.get("input_ids"),
                threshold=0.20,
                text_threshold=0.20,
                target_sizes=[(h, w)],
            )[0]
            boxes  = res.get("boxes")
            scores = res.get("scores")
            if boxes is None or len(boxes) == 0:
                continue
            bi = int(torch.argmax(scores).item())
            box = boxes[bi].detach().cpu().numpy()
            if ((box[2] - box[0]) * (box[3] - box[1])) / (w * h) > 0.70:
                continue
            ms, ss, _ = gsam.predictor.predict(box=box, multimask_output=True)
            cand = ms[int(np.argmax(ss))].astype(np.uint8) * 255
            cov  = float(np.count_nonzero(cand > 127)) / (w * h)
            if 0.01 <= cov <= 0.60:
                support_union = np.maximum(support_union, cand)

        if not np.any(support_union > 127):
            logger.info("Soft support cleanup: SAM3 found no support surface")
            return {
                "status": "skipped", "support_leakage_detected": True, "support_removed": False,
                "coverage_before": coverage_before, "coverage_after": coverage_before,
                "bottom_edge_contact_before": bottom_before, "bottom_edge_contact_after": bottom_before,
                "warnings": ["no_support_surface_detected_by_sam3"],
            }

        # Remove: support AND lower_half AND NOT protected_core
        lower_region = np.zeros((h, w), np.uint8)
        lower_region[h // 2:, :] = 255
        remove_mask = (
            (support_union > 127) & (lower_region > 127) & ~(protected_mask > 127)
        ).astype(np.uint8)

        refined_binary = np.clip(orig_binary.astype(np.int16) - remove_mask, 0, 1).astype(np.uint8)
        refined_mask   = (refined_binary * 255).astype(np.uint8)

        coverage_after = float(refined_binary.sum()) / (h * w)
        bottom_after   = float(refined_binary[h - 1, :].sum()) / w
        uh_before = float(orig_binary[:h // 2, :].sum())   / max(orig_binary[:h // 2, :].size, 1)
        uh_after  = float(refined_binary[:h // 2, :].sum()) / max(refined_binary[:h // 2, :].size, 1)
        ys_after  = np.where(refined_binary)[0]
        bh_before = (ys_orig.max() - ys_orig.min()) / h
        bh_after  = ((ys_after.max() - ys_after.min()) / h) if len(ys_after) > 0 else 0.0

        # Revert conditions
        revert = False
        revert_reason = ""
        if coverage_after < 0.15:
            revert = True; revert_reason = "coverage_after_too_low"
        elif coverage_before > 0 and coverage_after / coverage_before < 0.45:
            revert = True; revert_reason = "coverage_ratio_too_low"
        elif bh_before > 0 and bh_after / bh_before < 0.70:
            revert = True; revert_reason = "bbox_height_ratio_too_low"
        elif uh_before > 0 and uh_after / uh_before < 0.70:
            revert = True; revert_reason = "upper_half_density_decreased_too_much"
        elif not np.any(refined_binary):
            revert = True; revert_reason = "empty_refined_mask"

        if not revert:
            output_mask_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_mask_path), refined_mask)
            val = validate_soft_furniture_mask(output_mask_path, image_path)
            if not val.get("valid", True):
                revert = True
                revert_reason = "backrest_validation_failed:" + ",".join(val.get("warnings", []))

        if revert:
            output_mask_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_mask_path), orig_mask)
            logger.info("Soft support cleanup reverted: %s", revert_reason)
            return {
                "status": "reverted",
                "support_leakage_detected": True,
                "support_removed": False,
                "reason": revert_reason,
                "coverage_before": round(coverage_before, 4),
                "coverage_after":  round(coverage_before, 4),
                "bottom_edge_contact_before": round(bottom_before, 4),
                "bottom_edge_contact_after":  round(bottom_before, 4),
                "warnings": ["soft_support_cleanup_reverted_to_preserve_furniture"],
            }

        removed_cov = round(coverage_before - coverage_after, 4)
        logger.info("Soft support cleanup done: removed=%.3f before=%.3f after=%.3f bottom %.3f→%.3f",
                    removed_cov, coverage_before, coverage_after, bottom_before, bottom_after)
        return {
            "status": "done",
            "support_leakage_detected": True,
            "support_removed": True,
            "removed_coverage": removed_cov,
            "coverage_before": round(coverage_before, 4),
            "coverage_after":  round(coverage_after, 4),
            "bottom_edge_contact_before": round(bottom_before, 4),
            "bottom_edge_contact_after":  round(bottom_after, 4),
            "warnings": ["soft_support_surface_removed"],
        }

    except Exception as e:
        logger.warning("cleanup_soft_support_surface_leakage failed: %s", e)
        output_mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_mask_path), orig_mask)
        return {
            "status": "failed",
            "support_leakage_detected": True,
            "support_removed": False,
            "warnings": [f"soft_support_cleanup_exception: {e}"],
        }


# ---------------------------------------------------------------------------
# cleanup_floor_leakage_from_mask
# ---------------------------------------------------------------------------

def cleanup_floor_leakage_from_mask(mask_path: Path, furniture_type: str) -> dict:
    """Remove wide bottom-touching components (floor bleed) from open-leg furniture masks."""
    import cv2
    import numpy as np

    if furniture_type not in {"desk", "table", "chair"}:
        return {"status": "skipped", "removed_floor_like_components": 0,
                "refined_bbox": None, "warnings": []}

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"status": "failed", "removed_floor_like_components": 0,
                "refined_bbox": None, "warnings": ["cannot_read_mask"]}

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8) * 255

    if float(np.sum(binary[h - 1, :] > 127)) / w < 0.25:
        return {"status": "skipped", "removed_floor_like_components": 0,
                "refined_bbox": None, "warnings": []}

    num_labels, labels, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    result = binary.copy()
    removed = 0

    for i in range(1, num_labels):
        component = labels == i
        if not np.any(component[h - 1, :]):
            continue
        col_span = int(np.sum(np.any(component, axis=0)))
        if col_span / w > 0.65:
            result[component] = 0
            removed += 1

    cv2.imwrite(str(mask_path), result)

    ys, xs = np.where(result > 127)
    refined_bbox = ([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                    if len(xs) > 0 else None)

    return {
        "status": "done",
        "removed_floor_like_components": removed,
        "refined_bbox": refined_bbox,
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# mask refinement helpers
# ---------------------------------------------------------------------------

def remove_small_mask_artifacts(
    mask: "np.ndarray",
    min_component_area_ratio: float = 0.0005,
) -> "np.ndarray":
    """Remove small isolated artifact blobs; preserve elongated thin structures (legs/frames)."""
    import numpy as np
    import cv2

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8) * 255
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num_labels <= 2:
        return mask

    min_area = int(h * w * min_component_area_ratio)
    areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, num_labels)]
    main_idx = int(np.argmax(areas)) + 1

    result = np.zeros_like(binary)
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if i == main_idx:
            result = np.maximum(result, (labels == i).astype(np.uint8) * 255)
            continue
        if area >= min_area:
            result = np.maximum(result, (labels == i).astype(np.uint8) * 255)
        else:
            # Keep elongated components — likely a thin leg or frame
            comp_w = int(stats[i, cv2.CC_STAT_WIDTH])
            comp_h = int(stats[i, cv2.CC_STAT_HEIGHT])
            aspect = max(comp_w, comp_h) / max(min(comp_w, comp_h), 1)
            if aspect >= 3.0:
                result = np.maximum(result, (labels == i).astype(np.uint8) * 255)
            # else: small blob → discard
    return result


def fill_small_holes_safely(
    mask: "np.ndarray",
    max_hole_area_ratio: float = 0.001,
) -> "np.ndarray":
    """Fill tiny enclosed holes; never fill background or large internal gaps."""
    import numpy as np
    import cv2

    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8)
    inverted = ((1 - binary) * 255).astype(np.uint8)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inverted, connectivity=4)
    max_hole_px = int(h * w * max_hole_area_ratio)

    result = binary.copy()
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= max_hole_px:
            continue  # large region → background or intentional gap
        x  = int(stats[i, cv2.CC_STAT_LEFT])
        y  = int(stats[i, cv2.CC_STAT_TOP])
        x2 = x + int(stats[i, cv2.CC_STAT_WIDTH])
        y2 = y + int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or x2 >= w - 1 or y2 >= h - 1:
            continue  # touches image border → is background
        result[labels == i] = 1  # fill small enclosed hole

    return (result * 255).astype(np.uint8)


def feather_alpha_mask(
    hard_mask_path: Path,
    output_alpha_mask_path: Path,
    blur_radius: int = 3,
) -> dict:
    """Produce soft alpha mask: core area stays 255, boundary gets gentle Gaussian feather."""
    import cv2
    import numpy as np

    hard = cv2.imread(str(hard_mask_path), cv2.IMREAD_GRAYSCALE)
    if hard is None:
        return {"status": "failed", "blur_radius": blur_radius, "warnings": ["cannot_read_hard_mask"]}

    # Core: eroded region → alpha must stay 255
    erode_k = max(3, blur_radius * 2 + 1)
    core = cv2.erode(hard, np.ones((erode_k, erode_k), np.uint8), iterations=1)

    # Blurred boundary
    blur_k = blur_radius * 2 + 1
    blurred = cv2.GaussianBlur(hard.astype(np.float32), (blur_k, blur_k), 0)

    alpha = np.clip(blurred, 0, 255).astype(np.uint8)
    alpha[core > 127] = 255  # keep core fully opaque

    output_alpha_mask_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_alpha_mask_path), alpha)
    return {"status": "done", "blur_radius": blur_radius, "warnings": []}


def refine_mask_for_output(
    mask_path: Path,
    furniture_type: str,
    masking_family: str,
    category_subtype: str,
    output_hard_mask_path: Path,
    output_alpha_mask_path: Path,
) -> dict:
    """Refine SAM3 raw mask: remove artifacts, fill tiny holes, smooth boundaries.

    Produces:
    - output_hard_mask_path : binary hard mask for measurement + 3D generation
    - output_alpha_mask_path: feathered alpha mask for final cutout preview only
    """
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {
            "status": "failed", "warnings": ["cannot_read_mask"],
            "small_components_removed": 0, "small_holes_filled": 0, "feather_applied": False,
        }

    # Per-family tuning
    if masking_family == "rack_or_thin_structure":
        min_artifact_ratio = 0.0002
        max_hole_ratio     = 0.0002
        do_smooth          = False
        feather_blur       = 1
    elif masking_family == "glass_or_reflective":
        min_artifact_ratio = 0.0005
        max_hole_ratio     = 0.0003
        do_smooth          = True
        feather_blur       = 3
    elif masking_family == "open_leg_hard":
        min_artifact_ratio = 0.0005
        max_hole_ratio     = 0.0003   # conservative: legs create intentional large gaps
        do_smooth          = True
        feather_blur       = 3
    elif masking_family == "closed_body":
        min_artifact_ratio = 0.0005
        max_hole_ratio     = 0.0020   # can fill small panel/joint holes
        do_smooth          = True
        feather_blur       = 3
    elif masking_family == "soft_furniture":
        min_artifact_ratio = 0.0005
        max_hole_ratio     = 0.0010
        do_smooth          = True
        feather_blur       = 3
    elif masking_family == "bed_type":
        min_artifact_ratio = 0.0005
        max_hole_ratio     = 0.0015
        do_smooth          = True
        feather_blur       = 3
    else:  # generic
        min_artifact_ratio = 0.0005
        max_hole_ratio     = 0.0010
        do_smooth          = True
        feather_blur       = 3

    # Step 1: remove small artifact components
    before_px = int(np.count_nonzero(mask > 127))
    cleaned = remove_small_mask_artifacts(mask, min_component_area_ratio=min_artifact_ratio)
    after_px = int(np.count_nonzero(cleaned > 127))
    components_removed_est = max(0, (before_px - after_px) // max(1, int(
        mask.shape[0] * mask.shape[1] * min_artifact_ratio * 0.5)))

    # Step 2: fill small holes (skip for rack to avoid bridging thin pole gaps)
    if masking_family != "rack_or_thin_structure":
        before_fill = int(np.count_nonzero(cleaned > 127))
        filled = fill_small_holes_safely(cleaned, max_hole_area_ratio=max_hole_ratio)
        holes_filled_est = max(0, (int(np.count_nonzero(filled > 127)) - before_fill) // max(1, int(
            mask.shape[0] * mask.shape[1] * max_hole_ratio * 0.5)))
    else:
        filled = cleaned
        holes_filled_est = 0

    # Step 3: very mild smoothing (medianBlur=3 only, no erosion)
    if do_smooth:
        smoothed = cv2.medianBlur(filled, 3)
        # Protect: restore any pixel that was foreground after hole-fill
        smoothed = np.where(filled > 127, np.maximum(smoothed, 200), smoothed).astype(np.uint8)
    else:
        smoothed = filled

    # Save hard mask (binary)
    hard_mask = (smoothed > 127).astype(np.uint8) * 255
    output_hard_mask_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_hard_mask_path), hard_mask)

    # Save feathered alpha mask
    feather_info = feather_alpha_mask(output_hard_mask_path, output_alpha_mask_path, blur_radius=feather_blur)

    logger.info("Mask refine: family=%s subtype=%s removed_est=%d holes_est=%d feather=%s",
                masking_family, category_subtype, components_removed_est,
                holes_filled_est, feather_info.get("status"))
    return {
        "status": "done",
        "raw_mask": mask_path.name,
        "hard_mask": output_hard_mask_path.name,
        "alpha_mask": output_alpha_mask_path.name,
        "small_components_removed": components_removed_est,
        "small_holes_filled": holes_filled_est,
        "feather_applied": feather_info.get("status") == "done",
        "warnings": feather_info.get("warnings", []),
    }


# ---------------------------------------------------------------------------
# apply_mask_to_image
# ---------------------------------------------------------------------------

def apply_mask_to_image(image_path: Path, mask_path: Path, output_png_path: Path) -> dict:
    """Apply mask as alpha channel to produce a transparent-background RGBA PNG."""
    import cv2

    img = cv2.imread(str(image_path))
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if img is None or mask is None:
        return {"status": "failed", "error": "cannot_read_inputs"}

    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)

    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = mask

    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_png_path), rgba)
    return {"status": "done", "output": output_png_path.name}


# ---------------------------------------------------------------------------
# build_measurement_image_from_mask
# ---------------------------------------------------------------------------

def build_measurement_image_from_mask(
    image_path: Path,
    mask_path: Path,
    output_path: Path,
) -> dict:
    """Build measurement image: original pixels inside mask, neutral gray (128) outside."""
    import cv2
    import numpy as np

    img = cv2.imread(str(image_path))
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if img is None or mask is None:
        return {"status": "failed", "error": "cannot_read_inputs"}

    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)

    result = np.full_like(img, 128)
    result[mask > 127] = img[mask > 127]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), result)
    return {"status": "done", "output": output_path.name}


# ---------------------------------------------------------------------------
# boundary occlusion detection & completion
# ---------------------------------------------------------------------------

def analyze_boundary_occlusion(
    furniture_mask_path: Path,
    contaminant_mask_path: Path,
    furniture_type: str,
    masking_family: str,
) -> dict:
    """Detect whether a contaminant mask overlaps the furniture mask boundary.

    Returns has_boundary_occlusion=True only when the contaminant sits at the
    outer edge of the furniture — meaning simple removal would leave a hole in
    the furniture silhouette that needs completion.
    """
    import cv2
    import numpy as np

    furn_mask = cv2.imread(str(furniture_mask_path), cv2.IMREAD_GRAYSCALE)
    cont_mask  = cv2.imread(str(contaminant_mask_path), cv2.IMREAD_GRAYSCALE)
    if furn_mask is None or cont_mask is None:
        return {"has_boundary_occlusion": False, "boundary_overlap_ratio": 0.0,
                "occlusion_side": "none", "reason": "cannot_read_masks", "warnings": []}

    h, w = furn_mask.shape
    if cont_mask.shape != furn_mask.shape:
        cont_mask = cv2.resize(cont_mask, (w, h), interpolation=cv2.INTER_LINEAR)

    # Boundary band: dilated_furn - eroded_furn
    band_px = max(25, int(min(h, w) * 0.03))
    kernel  = np.ones((band_px, band_px), np.uint8)
    dilated = cv2.dilate(furn_mask, kernel, iterations=1)
    eroded  = cv2.erode(furn_mask, kernel, iterations=1)
    boundary_band = (dilated > 127) & ~(eroded > 127)

    cont_bin  = cont_mask > 127
    cont_area = int(cont_bin.sum())
    if cont_area == 0:
        return {"has_boundary_occlusion": False, "boundary_overlap_ratio": 0.0,
                "occlusion_side": "none", "reason": "empty_contaminant_mask", "warnings": []}

    overlap   = int((boundary_band & cont_bin).sum())
    ratio     = overlap / cont_area

    # Threshold: more sensitive for soft_furniture, conservative for open_leg_hard
    if masking_family == "soft_furniture":
        threshold = 0.02
    elif masking_family == "open_leg_hard":
        threshold = 0.05
    else:
        threshold = 0.03

    if ratio < threshold:
        return {"has_boundary_occlusion": False, "boundary_overlap_ratio": round(ratio, 4),
                "occlusion_side": "none", "reason": "overlap_below_threshold", "warnings": []}

    # Determine which side of the furniture the overlap is on
    furn_ys, furn_xs = np.where(furn_mask > 127)
    if len(furn_xs) == 0:
        return {"has_boundary_occlusion": False, "boundary_overlap_ratio": round(ratio, 4),
                "occlusion_side": "none", "reason": "empty_furniture_mask", "warnings": []}
    fx1, fy1, fx2, fy2 = int(furn_xs.min()), int(furn_ys.min()), int(furn_xs.max()), int(furn_ys.max())
    fw, fh = fx2 - fx1, fy2 - fy1

    cont_ys, cont_xs = np.where(cont_bin)
    cx1, cy1 = int(cont_xs.min()), int(cont_ys.min())
    cx2, cy2 = int(cont_xs.max()), int(cont_ys.max())
    ccx = (cx1 + cx2) / 2
    ccy = (cy1 + cy2) / 2

    # Classify occlusion side by contaminant centroid vs furniture bbox
    margin = max(20, int(min(fw, fh) * 0.1))
    if ccx > fx2 - margin:
        side = "right"
    elif ccx < fx1 + margin:
        side = "left"
    elif ccy > fy2 - margin:
        side = "bottom"
    elif ccy < fy1 + margin:
        side = "top"
    else:
        # centroid inside furniture bbox → likely sitting on top, not boundary occluder
        return {"has_boundary_occlusion": False, "boundary_overlap_ratio": round(ratio, 4),
                "occlusion_side": "internal", "reason": "contaminant_centroid_inside_furniture",
                "warnings": []}

    logger.info("Boundary occlusion detected: side=%s ratio=%.3f family=%s", side, ratio, masking_family)
    return {
        "has_boundary_occlusion": True,
        "boundary_overlap_ratio": round(ratio, 4),
        "occlusion_side": side,
        "reason": f"contaminant overlaps {side} boundary of furniture mask, may hide outer edge",
        "warnings": ["boundary_occluder_detected"],
    }


def build_boundary_completion_mask(
    furniture_mask_path: Path,
    contaminant_mask_path: Path,
    boundary_info: dict,
    output_mask_path: Path,
    masking_family: str = "generic",
) -> dict:
    """Build inpainting mask that covers the contaminant + a thin boundary extension.

    The mask is intentionally larger than the bare contaminant so LaMa can
    sample furniture-texture pixels just outside the contaminant edge.
    """
    import cv2
    import numpy as np

    furn_mask = cv2.imread(str(furniture_mask_path), cv2.IMREAD_GRAYSCALE)
    cont_mask  = cv2.imread(str(contaminant_mask_path), cv2.IMREAD_GRAYSCALE)
    if furn_mask is None or cont_mask is None:
        return {"status": "failed", "mask_coverage": 0.0, "warnings": ["cannot_read_masks"]}

    h, w = furn_mask.shape
    if cont_mask.shape != furn_mask.shape:
        cont_mask = cv2.resize(cont_mask, (w, h), interpolation=cv2.INTER_LINEAR)

    # Start with contaminant mask
    completion = (cont_mask > 127).astype(np.uint8)

    # Narrow expansion in the occlusion direction using furniture boundary band
    side       = boundary_info.get("occlusion_side", "none")
    band_px    = max(20, int(min(h, w) * 0.025))
    kernel     = np.ones((band_px, band_px), np.uint8)
    dilated    = cv2.dilate(furn_mask, kernel, iterations=1)
    eroded     = cv2.erode(furn_mask, kernel, iterations=1)
    band_mask  = ((dilated > 127) & ~(eroded > 127)).astype(np.uint8)

    # Add boundary band pixels near the occlusion side
    if side == "right":
        roi = np.zeros((h, w), np.uint8)
        roi[:, max(0, w // 2):] = 1
        completion = np.maximum(completion, band_mask & roi)
    elif side == "left":
        roi = np.zeros((h, w), np.uint8)
        roi[:, :min(w, w // 2)] = 1
        completion = np.maximum(completion, band_mask & roi)
    elif side == "bottom":
        roi = np.zeros((h, w), np.uint8)
        roi[max(0, h // 2):, :] = 1
        completion = np.maximum(completion, band_mask & roi)
    elif side == "top":
        roi = np.zeros((h, w), np.uint8)
        roi[:min(h, h // 2), :] = 1
        completion = np.maximum(completion, band_mask & roi)
    else:
        completion = np.maximum(completion, band_mask)

    coverage = float(completion.sum()) / (h * w)

    # Cap: 8% for most families, 12% for soft_furniture
    max_coverage = 0.12 if masking_family == "soft_furniture" else 0.08
    warnings: list[str] = []
    if coverage > max_coverage:
        warnings.append(f"completion_mask_too_large_{coverage:.3f}_falling_back_to_contaminant_only")
        completion = (cont_mask > 127).astype(np.uint8)
        coverage = float(completion.sum()) / (h * w)

    output_mask_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_mask_path), (completion * 255).astype(np.uint8))
    return {
        "status": "done",
        "mask_coverage": round(coverage, 4),
        "occlusion_side": side,
        "warnings": warnings,
    }


def complete_furniture_boundary_with_inpainting(
    image_path: Path,
    completion_mask_path: Path,
    furniture_mask_path: Path,
    output_path: Path,
    furniture_type: str,
    masking_family: str,
) -> dict:
    """Run LaMa inpainting on the boundary completion mask (generation use only)."""
    result = inpaint_obstacles_with_lama(image_path, completion_mask_path, output_path)
    if result.get("status") == "done":
        return {
            "status": "done",
            "method": "lama_boundary_completion",
            "used_for": "generation_only",
            "warnings": [
                "boundary_completion_used",
                "not_for_measurement",
                "needs_review_after_completion",
            ],
        }
    return {
        "status": "failed",
        "method": "lama_boundary_completion",
        "error": result.get("error", "lama_failed"),
        "warnings": ["boundary_completion_lama_failed"],
    }


def expand_generation_mask_for_boundary_completion(
    final_mask_path: Path,
    completion_mask_path: Path,
    output_generation_mask_path: Path,
    boundary_info: dict,
    masking_family: str = "generic",
) -> dict:
    """Expand the generation mask slightly at the furniture boundary so the
    completed furniture pixels are included in the generation cutout.

    Only the part of the completion mask that touches the furniture boundary
    is unioned — the rest of the contaminant area is excluded.
    """
    import cv2
    import numpy as np

    furn = cv2.imread(str(final_mask_path),    cv2.IMREAD_GRAYSCALE)
    comp = cv2.imread(str(completion_mask_path), cv2.IMREAD_GRAYSCALE)
    if furn is None or comp is None:
        return {"status": "failed", "mask_expanded": False, "warnings": ["cannot_read_masks"]}

    h, w = furn.shape
    if comp.shape != furn.shape:
        comp = cv2.resize(comp, (w, h), interpolation=cv2.INTER_LINEAR)

    # Expand boundary band and intersect with completion mask
    band_px = max(30, int(min(h, w) * 0.04))
    kernel  = np.ones((band_px, band_px), np.uint8)
    dilated = cv2.dilate(furn, kernel, iterations=1)
    boundary_extension = (dilated > 127) & (comp > 127)

    cov_before = float(np.count_nonzero(furn > 127)) / (h * w)
    expanded   = np.maximum(furn, (boundary_extension * 255).astype(np.uint8))
    cov_after  = float(np.count_nonzero(expanded > 127)) / (h * w)
    delta      = cov_after - cov_before

    # Coverage increase limits
    max_delta = 0.06 if masking_family == "soft_furniture" else 0.03
    warnings: list[str] = []
    if delta > max_delta:
        warnings.append(f"generation_mask_expansion_too_large_{delta:.3f}_using_original")
        expanded = furn.copy()
        cov_after = cov_before

    output_generation_mask_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_generation_mask_path), expanded)
    return {
        "status": "done",
        "mask_expanded": delta > 0.0005 and not warnings,
        "coverage_before": round(cov_before, 4),
        "coverage_after":  round(cov_after, 4),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# run_service_pipeline  (single flow)
# ---------------------------------------------------------------------------

def run_service_pipeline(url: str, selected_image_index: int) -> tuple[dict, int]:
    """Execute the SAM3-only experimental pipeline.

    Flow:
    1.  Scrape
    2.  Download selected image
    3.  Infer furniture type
    4.  Parse listing dimensions
    5.  SAM3 part-based furniture mask + floor cleanup
    6.  Build measurement image (original + SAM3 mask, gray bg)
    7.  Build final_cutout (SAM3 mask as alpha on original)
    8.  Analyze dimension obstacles + generation contaminants
    9.  If contaminants/obstacles: SAM3 mask → LaMa inpaint → generation source
    10. Build generation cutout (SAM3 mask applied to generation source)
    11. Estimate dimensions from measurement image
    12. Evaluate cutout quality → final_decision
    """
    import shutil

    job_id = uuid.uuid4().hex[:8]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    masking_strategy = {
        "primary": "sam3_only",
        "part_based": True,
        "dino_used": False,
        "birefnet_used": False,
        "fallback_used": False,
        "family": "generic",
        "category_subtype": "generic",
        "strategy": "unknown",
        "risk_level": "normal",
        "manual_review_recommended": False,
        "multi_box_union": False,
    }

    try:
        # ── 1. Scrape ─────────────────────────────────────────────────────
        platform = _core.identify_platform(url)
        if not platform:
            return {"error": "당근마켓 또는 중고나라 URL만 지원합니다."}, 400

        try:
            scraped = scrape_listing(url)
        except Exception as e:
            return {"error": f"스크래핑 실패: {e}", "job_id": job_id}, 500

        image_urls = scraped.get("images", [])
        if not image_urls:
            return {"error": "이미지를 찾을 수 없습니다.", "job_id": job_id}, 400

        title = scraped.get("title", "")
        description = scraped.get("description", "")

        # ── 2. Download selected image ────────────────────────────────────
        idx = selected_image_index if 0 <= selected_image_index < len(image_urls) else 0
        original_path = job_dir / "01_original.jpg"
        try:
            _core.download_image(image_urls[idx], original_path)
        except Exception as e:
            return {"error": f"이미지 다운로드 실패: {e}", "job_id": job_id}, 500

        # ── 3. Infer furniture type ───────────────────────────────────────
        furniture_info = infer_furniture_type(original_path, title, description)
        furniture_type = furniture_info["furniture_type"]
        logger.info("Furniture type: %s (%s)", furniture_type, furniture_info["confidence"])

        if furniture_type == "unknown":
            warnings.append("furniture_type_unknown")

        # ── 4. Parse listing dimensions ───────────────────────────────────
        listing_dims = parse_listing_dimensions(title, description)
        if listing_dims:
            logger.info("Listing dimensions found: %s", listing_dims)

        # ── 5. SAM3 part-based furniture mask ─────────────────────────────
        debug_dir = job_dir / "debug"
        raw_mask_path       = job_dir / "04_raw_mask.png"
        final_mask_path     = job_dir / "04_final_mask.png"
        soft_alpha_mask_path = job_dir / "04_final_alpha.png"

        furniture_mask_info = generate_sam3_furniture_mask(
            original_path, furniture_type, raw_mask_path,
            title=title, description=description, debug_dir=debug_dir,
        )

        if furniture_mask_info["status"] != "done":
            warnings.append("sam3_furniture_mask_failed")
            logger.warning("SAM3 furniture mask failed: %s", furniture_mask_info.get("error"))
            return {
                "job_id": job_id,
                "pipeline_version": "service_v3_sam3_only",
                "error": "sam3_furniture_mask_failed",
                "furniture_mask_info": furniture_mask_info,
                "masking_strategy": masking_strategy,
                "warnings": warnings,
                "final_decision": {
                    "can_use_for_dimension": False,
                    "can_use_for_3d_generation": False,
                    "can_use_for_ar_scale": False,
                },
            }, 200

        # Update masking_strategy with family info from the mask result
        detected_family = furniture_mask_info.get("masking_family", "generic")
        detected_subtype = furniture_mask_info.get("category_subtype", "generic")
        masking_strategy.update({
            "family": detected_family,
            "category_subtype": detected_subtype,
            "strategy": furniture_mask_info.get("method", "unknown"),
            "risk_level": furniture_mask_info.get("risk_level", "normal"),
            "manual_review_recommended": furniture_mask_info.get("manual_review_recommended", False),
            "multi_box_union": furniture_mask_info.get("method", "").endswith("multi_box")
                               or "multi_box" in furniture_mask_info.get("method", ""),
            "whole_object_first": detected_family in ("soft_furniture", "bed_type", "closed_body",
                                                       "rack_or_thin_structure",
                                                       "glass_or_reflective", "generic"),
            "part_based": detected_family == "open_leg_hard",
        })

        floor_cleanup_info = cleanup_floor_leakage_from_mask(raw_mask_path, furniture_type)
        if floor_cleanup_info.get("removed_floor_like_components", 0) > 0:
            warnings.append("floor_leakage_cleaned_from_mask")
            logger.info("Floor cleanup: removed %d component(s)",
                        floor_cleanup_info["removed_floor_like_components"])

        # ── 5b. Refine mask: remove artifacts, fill tiny holes, smooth ────
        mask_refinement_info = refine_mask_for_output(
            raw_mask_path,
            furniture_type,
            detected_family,
            detected_subtype,
            final_mask_path,       # hard mask → measurement + 3D generation
            soft_alpha_mask_path,  # feathered alpha → final cutout preview
        )
        if mask_refinement_info["status"] != "done":
            # Fallback: copy raw mask as both hard and alpha
            import shutil as _shutil
            _shutil.copy2(str(raw_mask_path), str(final_mask_path))
            _shutil.copy2(str(raw_mask_path), str(soft_alpha_mask_path))
            warnings.append("mask_refinement_failed_used_raw")

        # ── 6. Measurement image (hard mask, gray bg) ─────────────────────
        measurement_path = job_dir / "02_measurement.png"
        meas_build_info = build_measurement_image_from_mask(
            original_path, final_mask_path, measurement_path,
        )
        if meas_build_info["status"] != "done":
            warnings.append("measurement_image_build_failed")

        # ── 7. Final cutout (soft alpha mask → transparent PNG) ───────────
        final_cutout_path = job_dir / "03_final_cutout.png"
        cutout_build_info = apply_mask_to_image(original_path, soft_alpha_mask_path, final_cutout_path)
        if cutout_build_info["status"] == "done":
            logger.info("SAM3-only final cutout created (feathered alpha)")
        else:
            warnings.append("final_cutout_build_failed")

        # ── 8. Analyze obstacles + generation contaminants ────────────────
        obstacle_result = analyze_major_obstacles(original_path, furniture_type)
        has_major_obstacle = obstacle_result.get("has_major_obstacle", False)
        logger.info("Major obstacle: %s", has_major_obstacle)

        contaminant_result = analyze_generation_contaminants(
            original_path, furniture_type, masking_family=detected_family,
        )
        has_contaminants = contaminant_result.get("has_generation_contaminants", False)
        logger.info("Generation contaminants: %s", has_contaminants)

        obstacle_mask_path: Path | None = None
        obstacle_removed_path: Path | None = None
        inpainting_used = False
        inpainting_info: dict | None = None
        sam3_info: dict | None = None
        contaminant_sam3_info: dict | None = None
        boundary_occlusion_info: dict = {"has_boundary_occlusion": False}
        boundary_completion_info: dict | None = None
        generation_mask_expansion_info: dict | None = None
        boundary_completion_used = False

        # ── 9. Build generation source image (inpaint if needed) ──────────
        if has_major_obstacle or has_contaminants:
            import cv2 as _cv2
            import numpy as _np

            obstacle_mask_arr: "_np.ndarray | None" = None
            contaminant_mask_arr: "_np.ndarray | None" = None
            cont_mask_file: "Path | None" = None

            if has_major_obstacle:
                obs_mask_file = job_dir / "05_obstacle_mask.png"
                sam3_info = segment_objects_with_sam3(
                    original_path,
                    obstacle_result.get("obstacles", []),
                    None,
                    obs_mask_file,
                    mode="major_obstacle",
                )
                if sam3_info["status"] == "done":
                    obstacle_mask_path = obs_mask_file
                    _m = _cv2.imread(str(obs_mask_file), _cv2.IMREAD_GRAYSCALE)
                    if _m is not None:
                        obstacle_mask_arr = _m
                else:
                    reason = sam3_info.get("error") or sam3_info.get("status", "unknown")
                    warnings.append(f"obstacle_mask_generation_failed_{reason}")

            if has_contaminants:
                cont_mask_file = job_dir / "07_contaminant_mask.png"
                contaminant_sam3_info = segment_objects_with_sam3(
                    original_path,
                    contaminant_result.get("contaminants", []),
                    None,
                    cont_mask_file,
                    mode="generation_contaminant",
                )
                if contaminant_sam3_info["status"] == "done":
                    _m = _cv2.imread(str(cont_mask_file), _cv2.IMREAD_GRAYSCALE)
                    if _m is not None:
                        contaminant_mask_arr = _m
                    warnings.append("generation_contaminants_detected")
                else:
                    warnings.append("generation_contaminant_mask_failed_fallback_to_original")
                    cont_mask_file = None

            # ── 9b. Boundary occlusion check (contaminant only) ───────────
            if (cont_mask_file is not None and contaminant_mask_arr is not None
                    and final_mask_path.exists()):
                boundary_occlusion_info = analyze_boundary_occlusion(
                    final_mask_path, cont_mask_file, furniture_type, detected_family,
                )

            has_boundary_occ = boundary_occlusion_info.get("has_boundary_occlusion", False)

            if has_boundary_occ and cont_mask_file is not None:
                # ── 9c. Boundary completion path ──────────────────────────
                completion_mask_path = job_dir / "08_boundary_completion_mask.png"
                boundary_completion_info = build_boundary_completion_mask(
                    final_mask_path, cont_mask_file, boundary_occlusion_info,
                    completion_mask_path, masking_family=detected_family,
                )

                if boundary_completion_info.get("status") == "done":
                    # Build union mask: obstacles (if any) + completion mask
                    if obstacle_mask_arr is not None:
                        import numpy as _np2
                        comp_arr = _cv2.imread(str(completion_mask_path), _cv2.IMREAD_GRAYSCALE)
                        union_bc = _np2.maximum(obstacle_mask_arr,
                                                comp_arr if comp_arr is not None else _np2.zeros_like(obstacle_mask_arr))
                        _cv2.imwrite(str(job_dir / "07_union_mask.png"), union_bc)
                        lama_src_mask = job_dir / "07_union_mask.png"
                    else:
                        lama_src_mask = completion_mask_path

                    boundary_completed_path = job_dir / "08_boundary_completed.png"
                    bc_result = complete_furniture_boundary_with_inpainting(
                        original_path, lama_src_mask, final_mask_path,
                        boundary_completed_path, furniture_type, detected_family,
                    )

                    if bc_result.get("status") == "done":
                        boundary_completion_used = True
                        inpainting_used = True
                        obstacle_removed_path = boundary_completed_path
                        for _w in ["boundary_occlusion_detected",
                                   "boundary_completion_used_for_generation",
                                   "not_for_measurement",
                                   "needs_review_after_boundary_completion"]:
                            if _w not in warnings:
                                warnings.append(_w)
                        logger.info("Boundary completion done: side=%s coverage=%.3f",
                                    boundary_occlusion_info.get("occlusion_side"),
                                    boundary_completion_info.get("mask_coverage", 0))
                    else:
                        warnings.append("boundary_completion_lama_failed_fallback")
                        has_boundary_occ = False  # fall through to normal path
                else:
                    warnings.append("boundary_completion_mask_build_failed_fallback")
                    has_boundary_occ = False

            if not has_boundary_occ:
                # ── 9d. Normal contaminant removal path ───────────────────
                union_arr: "_np.ndarray | None" = None
                if obstacle_mask_arr is not None and contaminant_mask_arr is not None:
                    union_arr = _np.maximum(obstacle_mask_arr, contaminant_mask_arr)
                elif obstacle_mask_arr is not None:
                    union_arr = obstacle_mask_arr
                elif contaminant_mask_arr is not None:
                    union_arr = contaminant_mask_arr

                if union_arr is not None:
                    union_mask_path = job_dir / "07_union_mask.png"
                    _cv2.imwrite(str(union_mask_path), union_arr)

                    obs_removed_file = job_dir / "05_obstacle_removed.png"
                    inpainting_info = inpaint_obstacles_with_lama(
                        original_path, union_mask_path, obs_removed_file,
                    )

                    if inpainting_info["status"] == "done":
                        inpainting_used = True
                        obstacle_removed_path = obs_removed_file
                        if has_contaminants:
                            warnings.append("generation_uses_contaminant_removed_image")
                    else:
                        warnings.append("lama_inpainting_failed_fallback_to_original")

        # ── 10. Generation cutout (SAM3 mask applied to generation source) ─
        generation_cutout_path: Path | None = None
        generation_mask_path: Path | None = None
        generation_cutout_quality: dict = {"quality": "unknown", "warnings": []}

        if inpainting_used and obstacle_removed_path and obstacle_removed_path.exists():
            gen_cutout_file = job_dir / "06_generation_cutout.png"
            gen_mask_file   = job_dir / "06_generation_mask.png"

            if boundary_completion_used and cont_mask_file is not None:
                # Expand generation mask to include completed boundary area
                generation_mask_expansion_info = expand_generation_mask_for_boundary_completion(
                    final_mask_path, cont_mask_file, gen_mask_file,
                    boundary_occlusion_info, masking_family=detected_family,
                )
                gen_mask_for_cutout = gen_mask_file
            else:
                shutil.copy2(str(final_mask_path), str(gen_mask_file))
                gen_mask_for_cutout = gen_mask_file

            gen_build_info = apply_mask_to_image(
                obstacle_removed_path, gen_mask_for_cutout, gen_cutout_file,
            )
            if gen_build_info["status"] == "done":
                generation_cutout_path = gen_cutout_file
                generation_mask_path   = gen_mask_file
                logger.info("Generation cutout created: boundary_completion=%s",
                            boundary_completion_used)
                generation_cutout_quality = evaluate_cutout_quality(gen_mask_file, furniture_type)
        else:
            if final_mask_path.exists():
                generation_cutout_quality = evaluate_cutout_quality(final_mask_path, furniture_type)

        # ── 11. Evaluate original cutout quality ──────────────────────────
        cutout_quality: dict = {"quality": "unknown", "warnings": []}
        if final_mask_path.exists():
            cutout_quality = evaluate_cutout_quality(final_mask_path, furniture_type)

        # ── 12. Estimate dimensions (always from measurement image) ────────
        # Inpainted image is NEVER used for measurement.
        meas_source = measurement_path if measurement_path.exists() else original_path
        dimensions = estimate_dimensions(meas_source, title, description, furniture_type, listing_dims)

        dim_confidence = dimensions.get("confidence", "low")
        if dim_confidence == "low":
            warnings.append("dimension_confidence_low")
        for w in (dimensions.get("warnings") or []):
            if w not in warnings:
                warnings.append(w)

        # ── 13. Final decision ────────────────────────────────────────────
        can_dimension = dim_confidence in ("medium", "high") and measurement_path.exists()
        dim_source = dimensions.get("source", "")

        is_approx = bool(dimensions.get("approximate", False))
        if dim_source == "listing_text" and dim_confidence == "high" and not is_approx:
            can_ar = True
            scale_status = "verified_from_listing"
            needs_user_confirmation = False
        elif dim_source == "listing_text" and dim_confidence == "high" and is_approx:
            can_ar = False
            scale_status = "listing_approx_needs_user_confirmation"
            needs_user_confirmation = True
        elif dim_confidence == "low":
            can_ar = False
            scale_status = "low_confidence_blocked"
            needs_user_confirmation = True
        else:
            can_ar = False
            scale_status = "estimated_needs_user_confirmation"
            needs_user_confirmation = True

        eff_quality = generation_cutout_quality if generation_cutout_path else cutout_quality
        gen_q = eff_quality.get("quality", "unknown")
        if gen_q == "ok":
            can_3d = True
            needs_review_for_3d = False
        elif gen_q in ("warning", "unknown"):
            can_3d = True
            needs_review_for_3d = True
        else:
            can_3d = False
            needs_review_for_3d = True

        # Conservative flags for high-risk families
        family_manual_review = masking_strategy.get("manual_review_recommended", False)
        if detected_family == "glass_or_reflective":
            # Glass surfaces often produce incomplete/noisy masks
            needs_review_for_3d = True
            family_manual_review = True
        elif detected_family == "rack_or_thin_structure":
            # Thin structures frequently lose detail at edges
            family_manual_review = True
        elif detected_family == "bed_type" and detected_subtype == "mattress_only":
            # Bare mattress without frame is ambiguous
            family_manual_review = True

        if family_manual_review and not needs_review_for_3d:
            needs_review_for_3d = True

        if boundary_completion_used:
            needs_review_for_3d = True
            family_manual_review = True

        if boundary_completion_used:
            generation_source = "sam3_alpha_cutout_after_boundary_completion"
        elif inpainting_used:
            generation_source = "sam3_alpha_cutout_after_inpainting"
        else:
            generation_source = "sam3_alpha_cutout"
        confidence_level = (
            "high" if dim_confidence == "high"
            else "medium" if dim_confidence == "medium"
            else "low"
        )

        final_decision = {
            "measurement_source": "sam3_masked_original",
            "generation_source": generation_source,
            "inpainting_used": inpainting_used,
            "can_use_for_dimension": can_dimension,
            "can_use_for_3d_generation": can_3d,
            "can_use_for_ar_scale": can_ar,
            "needs_user_confirmation": needs_user_confirmation,
            "scale_status": scale_status,
            "needs_review_for_3d_generation": needs_review_for_3d,
            "manual_review_recommended": family_manual_review,
            "masking_family": detected_family,
            "category_subtype": detected_subtype,
            "confidence_level": confidence_level,
            "warnings": warnings,
        }

        files = {
            "original": "01_original.jpg",
            "measurement": "02_measurement.png" if measurement_path.exists() else None,
            "final_cutout": "03_final_cutout.png" if final_cutout_path.exists() else None,
            "raw_mask": "04_raw_mask.png" if raw_mask_path.exists() else None,
            "final_mask": "04_final_mask.png" if final_mask_path.exists() else None,
            "final_alpha": "04_final_alpha.png" if soft_alpha_mask_path.exists() else None,
            "obstacle_mask": "05_obstacle_mask.png"
                if obstacle_mask_path and obstacle_mask_path.exists() else None,
            "obstacle_removed": "05_obstacle_removed.png"
                if obstacle_removed_path and obstacle_removed_path.exists() else None,
            "boundary_completion_mask": "08_boundary_completion_mask.png"
                if (job_dir / "08_boundary_completion_mask.png").exists() else None,
            "boundary_completed": "08_boundary_completed.png"
                if (job_dir / "08_boundary_completed.png").exists() else None,
            "generation_cutout": "06_generation_cutout.png"
                if generation_cutout_path and generation_cutout_path.exists() else None,
            "generation_mask": "06_generation_mask.png"
                if generation_mask_path and generation_mask_path.exists() else None,
        }

        result = {
            "job_id": job_id,
            "pipeline_version": "service_v3_sam3_only",
            "selected_image_index": idx,
            "furniture": {
                "type": furniture_type,
                "type_source": _resolve_type_source(furniture_info),
                "type_confidence": furniture_info["confidence"],
                "warning": furniture_info.get("warning"),
            },
            "listing_dimensions": listing_dims,
            "masking_strategy": masking_strategy,
            "part_mask_info": furniture_mask_info,
            "obstacle_analysis": obstacle_result,
            "generation_contaminant_analysis": contaminant_result,
            "dimensions": dimensions,
            "cutout_quality": cutout_quality,
            "generation_cutout_quality": generation_cutout_quality,
            "final_decision": final_decision,
            "files": files,
            "debug": {
                "sam3_info": sam3_info,
                "contaminant_sam3_info": contaminant_sam3_info,
                "inpainting_info": inpainting_info,
                "floor_cleanup_info": floor_cleanup_info,
                "soft_external_cleanup_info": furniture_mask_info.get("soft_cleanup_info"),
                "soft_support_cleanup_info": furniture_mask_info.get("soft_support_cleanup_info"),
                "thin_structure_preservation_info": furniture_mask_info.get("thin_structure_info"),
                "closed_body_cleanup_info": furniture_mask_info.get("closed_body_cleanup_info"),
                "mask_refinement_info": mask_refinement_info,
                "boundary_occlusion_info": boundary_occlusion_info,
                "boundary_completion_info": boundary_completion_info,
                "generation_mask_expansion_info": generation_mask_expansion_info,
                "category_strategy_info": {
                    "family": detected_family,
                    "subtype": detected_subtype,
                    "method": furniture_mask_info.get("method"),
                    "risk_level": furniture_mask_info.get("risk_level"),
                    "primary_prompts": furniture_mask_info.get("primary_prompts"),
                    "booster_prompts": furniture_mask_info.get("booster_prompts"),
                    "cleanup_applied": furniture_mask_info.get("cleanup_applied"),
                    "protected_parts": furniture_mask_info.get("protected_parts"),
                },
                "furniture_info": furniture_info,
            },
        }

        (job_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Service pipeline complete: job_id=%s", job_id)
        return result, 200

    except Exception as e:
        logger.exception("Service pipeline failed: job_id=%s", job_id)
        return {"error": str(e), "job_id": job_id}, 500


def _resolve_type_source(furniture_info: dict) -> str:
    listing = furniture_info.get("listing", "unknown")
    image = furniture_info.get("image", "unknown")
    if listing == image and listing != "unknown":
        return "combined"
    if listing != "unknown" and image == "unknown":
        return "listing_text"
    if image != "unknown" and listing == "unknown":
        return "vision"
    return "combined"


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

