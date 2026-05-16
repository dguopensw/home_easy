"""Production-style single-path furniture pipeline.

Run:
    python -m uvicorn clean_pipeline:app --host 127.0.0.1 --port 5004

Core rule:
    DINO finds the target furniture, BiRefNet cuts it out inside that DINO box,
    GPT is used only for obstacle judgement/removal, and dimensions are measured
    from the original-image measurement mask only. SAM is not used in this
    speed-first service flow.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

import app as legacy


PIPELINE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PIPELINE_DIR / "output_clean"
OUTPUT_DIR.mkdir(exist_ok=True)

legacy.load_runtime_environment()


class DimensionsInput(BaseModel):
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    height_cm: Optional[float] = None


class ProcessRequest(BaseModel):
    url: str = ""
    image_path: str = ""
    title: str = ""
    description: str = ""
    selected_image_index: Optional[int] = None
    user_input_dimensions: Optional[DimensionsInput] = None


app = FastAPI(title="Clean Furniture Pipeline", version="clean_v2_speed")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _jsonable(value):
    """Convert numpy scalar/tuple values into JSON-safe builtin values."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as img:
        return img.size


def _copy_or_convert_image(src: Path, dst: Path) -> None:
    from PIL import Image

    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img.convert("RGB").save(dst, quality=95)


def _clamp_bbox(bbox: list | tuple, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = image_size
    return legacy._clamp_bbox(tuple(bbox), w, h)


def _bbox_valid(bbox: tuple[int, int, int, int], image_size: tuple[int, int]) -> tuple[bool, str | None]:
    w, h = image_size
    return legacy._validate_bbox(bbox, w, h)


def _scale_bbox(
    bbox: tuple[int, int, int, int],
    from_size: tuple[int, int],
    to_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    if from_size == to_size:
        return bbox
    fw, fh = from_size
    tw, th = to_size
    sx = tw / max(1, fw)
    sy = th / max(1, fh)
    return (
        int(round(bbox[0] * sx)),
        int(round(bbox[1] * sy)),
        int(round(bbox[2] * sx)),
        int(round(bbox[3] * sy)),
    )


def _draw_bbox_image(
    image_path: Path,
    bbox: tuple[int, int, int, int],
    output_path: Path,
    label: str = "DINO target",
) -> None:
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image for bbox preview: {image_path}")
    x1, y1, x2, y2 = bbox
    cv2.rectangle(img, (x1, y1), (x2, y2), (37, 99, 235), 3)
    cv2.putText(
        img,
        label,
        (x1, max(24, y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (37, 99, 235),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(output_path), img)


def _detect_target_bbox_dino_only(
    image_path: Path,
    furniture_type: str,
    debug_dir: Path | None = None,
    device: str = "cpu",
) -> dict:
    """Detect target furniture bbox with GroundingDINO only.

    This intentionally does not call SAM. DINO provides candidate target boxes;
    the union of those boxes becomes the crop region for boxed BiRefNet.
    """
    import torch
    from PIL import Image

    segmenter = legacy.get_segmenter(device)
    gsam = legacy._get_gsam(segmenter)
    if not hasattr(gsam, "processor") or not hasattr(gsam, "detector"):
        raise RuntimeError("grounding_dino_unavailable")

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    prompt_text = ". ".join(legacy._get_part_prompts(furniture_type)) + "."
    inputs = gsam.processor(images=image, text=prompt_text, return_tensors="pt")
    inputs = {k: v.to(gsam.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = gsam.detector(**inputs)

    processed = gsam.processor.post_process_grounded_object_detection(
        outputs,
        input_ids=inputs.get("input_ids"),
        threshold=0.15,
        text_threshold=0.15,
        target_sizes=[(height, width)],
    )[0]

    boxes_tensor = processed.get("boxes")
    if boxes_tensor is None or len(boxes_tensor) == 0:
        raise RuntimeError("grounding_dino_detected_no_target_furniture")

    scores_tensor = processed.get("scores")
    raw_labels = processed.get("text_labels", processed.get("labels", []))
    boxes = boxes_tensor.detach().cpu().numpy().tolist()
    scores = scores_tensor.detach().cpu().numpy().tolist() if scores_tensor is not None else [0.0] * len(boxes)
    labels = [str(raw_labels[i]) if i < len(raw_labels) else "unknown" for i in range(len(boxes))]

    bbox = legacy._union_dino_boxes(boxes, width, height, padding_ratio=0.03)
    if not bbox:
        raise RuntimeError("grounding_dino_bbox_union_failed")

    detections = [
        {
            "label": labels[i],
            "confidence": round(float(scores[i]), 4),
            "box": [round(float(v), 2) for v in boxes[i]],
        }
        for i in range(len(boxes))
    ]

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "dino_only_detections.json").write_text(
            json.dumps({"prompt": prompt_text, "detections": detections}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    best_idx = max(range(len(scores)), key=lambda i: float(scores[i])) if scores else 0
    return {
        "method": "grounding_dino_only",
        "prompt": prompt_text,
        "bbox_raw": [int(v) for v in bbox],
        "image_width": width,
        "image_height": height,
        "num_detections": len(detections),
        "label": labels[best_idx] if labels else "unknown",
        "confidence": float(scores[best_idx]) if scores else 0.0,
        "detections": detections,
    }


def _validate_birefnet_mask_against_bbox(
    mask_path: Path,
    bbox: tuple[int, int, int, int],
) -> dict:
    """Fail boxed BiRefNet when it is clearly too small for the DINO target box."""
    import cv2
    import numpy as np

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return {"valid": False, "reason": "birefnet_mask_unreadable"}

    alpha_bbox = legacy._bbox_from_mask(mask)
    if alpha_bbox is None:
        return {"valid": False, "reason": "birefnet_mask_empty"}

    bbox_w = max(1, bbox[2] - bbox[0])
    bbox_h = max(1, bbox[3] - bbox[1])
    bbox_area = bbox_w * bbox_h
    alpha_w = max(1, alpha_bbox[2] - alpha_bbox[0])
    alpha_h = max(1, alpha_bbox[3] - alpha_bbox[1])
    alpha_area = int(np.count_nonzero(mask > 127))

    width_ratio = alpha_w / bbox_w
    height_ratio = alpha_h / bbox_h
    area_ratio = alpha_area / max(1, bbox_area)
    reasons = []
    if width_ratio < 0.40:
        reasons.append("mask_width_too_small_vs_dino_bbox")
    if height_ratio < 0.40:
        reasons.append("mask_height_too_small_vs_dino_bbox")
    if area_ratio < 0.03:
        reasons.append("mask_area_too_small_vs_dino_bbox")

    return {
        "valid": not reasons,
        "reason": ",".join(reasons) if reasons else None,
        "alpha_bbox": list(alpha_bbox),
        "dino_bbox": list(bbox),
        "width_ratio": round(width_ratio, 4),
        "height_ratio": round(height_ratio, 4),
        "area_ratio": round(area_ratio, 4),
        "alpha_area": alpha_area,
        "bbox_area": bbox_area,
    }


def _create_measurement_image(original_path: Path, mask_path: Path, output_path: Path) -> None:
    import cv2
    import numpy as np

    original = cv2.imread(str(original_path))
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if original is None or mask is None:
        raise ValueError("Cannot create measurement image: original or mask unreadable")
    if original.shape[:2] != mask.shape[:2]:
        mask = cv2.resize(mask, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_NEAREST)
    bg = np.full_like(original, 245)
    binary = (mask > 127).astype(np.uint8)[:, :, None]
    measurement = original * binary + bg * (1 - binary)
    cv2.imwrite(str(output_path), measurement)


def _parse_listing_dimensions(title: str, description: str) -> dict | None:
    """Extract simple cm dimensions from Korean/English listing text."""
    text = f"{title}\n{description}".lower()

    labeled = {}
    patterns = {
        "width_cm": r"(?:가로|폭|넓이|width|w)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:cm|센치|센티)?",
        "depth_cm": r"(?:세로|깊이|depth|d)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:cm|센치|센티)?",
        "height_cm": r"(?:높이|height|h)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:cm|센치|센티)?",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            labeled[key] = float(match.group(1))

    if len(labeled) >= 2:
        return {
            "width_cm": labeled.get("width_cm"),
            "depth_cm": labeled.get("depth_cm"),
            "height_cm": labeled.get("height_cm"),
            "source": "listing_text_dimensions",
            "confidence": "high" if len(labeled) == 3 else "medium",
            "reasoning": "Dimensions were parsed from listing text labels.",
        }

    triple = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:cm)?\s*[x×*]\s*"
        r"(\d+(?:\.\d+)?)\s*(?:cm)?\s*[x×*]\s*"
        r"(\d+(?:\.\d+)?)\s*(?:cm)?",
        text,
    )
    if triple:
        width, depth, height = [float(v) for v in triple.groups()]
        return {
            "width_cm": width,
            "depth_cm": depth,
            "height_cm": height,
            "source": "listing_text_dimensions",
            "confidence": "medium",
            "reasoning": "Dimensions were parsed from a W x D x H style listing pattern.",
        }
    return None


def _resolve_furniture_type(title: str, description: str, image_path: Path) -> dict:
    listing = legacy.classify_furniture_from_listing(title, description)
    if listing.get("confidence") == "high" and listing.get("furniture_type") != "unknown":
        return {
            "type": listing["furniture_type"],
            "type_source": "listing",
            "type_confidence": "high",
            "listing": listing,
            "vision": None,
        }

    vision = legacy.classify_furniture_from_image(image_path, title, description)
    reconciled = legacy.reconcile_furniture_type(listing, vision)
    source = "vision" if reconciled.get("furniture_type") == vision.get("furniture_type") else "listing"
    if reconciled.get("furniture_type") == "unknown":
        source = "fallback"
    return {
        "type": reconciled.get("furniture_type", "unknown"),
        "type_source": source,
        "type_confidence": reconciled.get("confidence", "low"),
        "warning": reconciled.get("warning"),
        "listing": listing,
        "vision": vision,
    }


def _load_input_image(body: ProcessRequest, job_dir: Path) -> tuple[dict, Path, int | None, str | None]:
    original_path = job_dir / "01_original.jpg"
    if body.url.strip():
        platform = legacy.identify_platform(body.url)
        if not platform:
            raise HTTPException(status_code=400, detail="당근마켓 또는 중고나라 URL만 지원합니다.")
        scraper = {"daangn": legacy.scrape_daangn, "joongna": legacy.scrape_joongna}[platform]
        scraped = scraper(body.url)
        scraped["platform"] = platform
        if not scraped.get("images"):
            raise HTTPException(status_code=400, detail="이미지를 찾을 수 없습니다.")

        selected_idx = body.selected_image_index
        if selected_idx is None or selected_idx < 0 or selected_idx >= len(scraped["images"]):
            selected_idx = (
                legacy.select_best_image_gpt(
                    scraped.get("title", ""),
                    scraped.get("description", ""),
                    scraped["images"],
                )
                if len(scraped["images"]) > 1
                else 0
            )
        legacy.download_image(scraped["images"][selected_idx], original_path)
        return scraped, original_path, selected_idx, scraped["images"][selected_idx]

    if body.image_path.strip():
        src = Path(body.image_path).expanduser()
        if not src.exists() or not src.is_file():
            raise HTTPException(status_code=400, detail=f"이미지 파일을 찾을 수 없습니다: {src}")
        _copy_or_convert_image(src, original_path)
        scraped = {
            "platform": "local_image",
            "title": body.title or src.stem,
            "description": body.description or "",
            "price": "",
            "images": [str(src)],
        }
        return scraped, original_path, 0, str(src)

    raise HTTPException(status_code=400, detail="URL 또는 image_path를 입력해주세요.")


def _select_dimensions(
    body: ProcessRequest,
    measurement_path: Path,
    title: str,
    description: str,
    furniture_type: str,
    measurement_source: str,
) -> dict:
    listing_dims = _parse_listing_dimensions(title, description)
    if listing_dims:
        return listing_dims

    if body.user_input_dimensions:
        dims = body.user_input_dimensions.model_dump()
        if any(v is not None for v in dims.values()):
            return {
                **dims,
                "source": "user_input_dimensions",
                "confidence": "high",
                "reasoning": "Dimensions were provided by the user.",
            }

    dims = legacy.measure_dimensions(
        measurement_path,
        title,
        description,
        furniture_type=furniture_type,
    )
    if dims.get("source") == "openai_vision":
        dims["source"] = measurement_source
    elif dims.get("source") == "local_category_fallback":
        dims["source"] = "local_category_fallback"
    return dims


_LOW_IMPACT_ACCESSORY_TERMS = (
    "cushion", "pillow", "bolster", "throw pillow", "back cushion", "seat cushion",
    "plush", "stuffed", "stuffed animal", "teddy", "doll", "toy",
    "쿠션", "베개", "볼스터", "인형", "장난감", "방석",
)


def _is_low_impact_accessory(name: str) -> bool:
    lowered = str(name or "").lower()
    return any(term in lowered for term in _LOW_IMPACT_ACCESSORY_TERMS)


def _apply_service_obstacle_policy(obstacle: dict) -> tuple[dict, dict]:
    """Downgrade low-impact accessories so GPT edit does not run unnecessarily.

    GPT Vision may classify sofa cushions, bolsters, or a small plush toy as
    surface obstacles. For the service path, those should not trigger image edit
    unless they affect measurement or hide the furniture outline.
    """
    service = dict(obstacle)
    service["obstacles"] = [dict(item) for item in obstacle.get("obstacles", [])]
    policy = {
        "raw_obstacle_status": obstacle.get("obstacle_status"),
        "applied": False,
        "reason": None,
    }

    if service.get("obstacle_status") != "surface_obstacle":
        return service, policy
    if service.get("occlusion_affects_outline"):
        return service, policy

    removable = [
        item for item in service.get("obstacles", [])
        if item.get("removal_needed", False)
    ]
    if not removable:
        service["obstacle_status"] = "none"
        service["needs_inpainting"] = False
        service["service_policy"] = "downgraded_empty_surface_obstacle"
        service["reason"] = (
            "Service policy ignored a surface_obstacle judgement with no concrete "
            f"removable obstacle. Raw GPT reason: {obstacle.get('reason', '')}"
        )
        policy.update({"applied": True, "reason": service["service_policy"]})
        return service, policy

    all_low_impact = all(
        _is_low_impact_accessory(item.get("name", ""))
        and not item.get("affects_measurement", False)
        for item in removable
    )
    if all_low_impact:
        service["obstacle_status"] = "none"
        service["needs_inpainting"] = False
        service["service_policy"] = "ignored_low_impact_accessory"
        service["reason"] = (
            "Service policy treated the detected item as a low-impact sofa/accessory "
            "item and skipped GPT image edit. "
            f"Raw GPT reason: {obstacle.get('reason', '')}"
        )
        policy.update({"applied": True, "reason": service["service_policy"]})
    return service, policy


def run_clean_pipeline(body: ProcessRequest) -> tuple[dict, int]:
    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    steps: list[dict] = []

    try:
        scraped, original_path, selected_idx, selected_image_url = _load_input_image(body, job_dir)
        title = scraped.get("title", "")
        description = scraped.get("description", "")
        steps.append({"step": "input", "status": "done", "selected_image_index": selected_idx})

        furniture = _resolve_furniture_type(title, description, original_path)
        furniture_type = furniture["type"]
        if furniture.get("warning"):
            warnings.append(furniture["warning"])
        steps.append({"step": "furniture_type", "status": "done", **furniture})

        dino_debug_dir = job_dir / "debug"
        detection_info = _detect_target_bbox_dino_only(
            original_path,
            furniture_type=furniture_type,
            debug_dir=dino_debug_dir,
        )

        image_size = _image_size(original_path)
        bbox_raw = detection_info.get("bbox_raw")
        if not bbox_raw:
            result = {
                "job_id": job_id,
                "pipeline_version": "clean_v2_speed",
                "pipeline_status": "failed",
                "error": "target_bbox_not_found",
                "steps": steps,
            }
            (job_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result, 422

        bbox_clamped = _clamp_bbox(bbox_raw, image_size)
        bbox_valid, bbox_reason = _bbox_valid(bbox_clamped, image_size)
        detection_path = job_dir / "02_detection_bbox.png"
        _draw_bbox_image(original_path, bbox_clamped, detection_path, f"DINO {furniture_type}")
        steps.append({
            "step": "target_detection",
            "status": "done" if bbox_valid else "failed",
            "bbox_raw": bbox_raw,
            "bbox_clamped": list(bbox_clamped),
            "bbox_valid": bbox_valid,
        })
        if not bbox_valid:
            result = {
                "job_id": job_id,
                "pipeline_version": "clean_v2_speed",
                "pipeline_status": "failed",
                "error": bbox_reason,
                "target_detection": {
                    "method": "grounding_dino",
                    "bbox_raw": bbox_raw,
                    "bbox_clamped": list(bbox_clamped),
                    "bbox_valid": False,
                    "reason": bbox_reason,
                },
                "steps": steps,
            }
            (job_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result, 422

        measurement_path = job_dir / "02_measurement.png"
        final_cutout_path = job_dir / "03_final_cutout.png"
        final_mask_path = job_dir / "04_final_mask.png"

        measurement_source = "dino_birefnet"
        cutout_info = {}
        try:
            cutout_info = legacy.generate_dino_birefnet_cutout(
                original_path,
                bbox_clamped,
                final_cutout_path,
                final_mask_path,
                support_mask_path=None,
                debug_dir=dino_debug_dir,
            )
            mask_validation = _validate_birefnet_mask_against_bbox(final_mask_path, bbox_clamped)
            cutout_info["bbox_validation"] = mask_validation
            if not mask_validation["valid"]:
                warnings.append("dino_birefnet_too_small_failed")
                result = {
                    "job_id": job_id,
                    "pipeline_version": "clean_v2_speed",
                    "pipeline_status": "failed",
                    "error": mask_validation["reason"],
                    "warnings": warnings,
                    "target_detection": {
                        "method": "grounding_dino_only",
                        "bbox_raw": bbox_raw,
                        "bbox_clamped": list(bbox_clamped),
                        "bbox_valid": True,
                        "image": "02_detection_bbox.png",
                    },
                    "measurement": {
                        "source": "dino_birefnet",
                        "eligible_for_dimension": False,
                    },
                    "files": {
                        "original": "01_original.jpg",
                        "target_detection": "02_detection_bbox.png",
                        "final_cutout": "03_final_cutout.png",
                        "final_mask": "04_final_mask.png",
                    },
                    "debug": {
                        "steps": steps,
                        "dino_detection": detection_info,
                        "cutout_info": cutout_info,
                    },
                }
                result = _jsonable(result)
                (job_dir / "result.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return result, 422
        except Exception as e:
            warnings.append("dino_birefnet_failed")
            result = {
                "job_id": job_id,
                "pipeline_version": "clean_v2_speed",
                "pipeline_status": "failed",
                "error": str(e),
                "warnings": warnings,
                "target_detection": {
                    "method": "grounding_dino_only",
                    "bbox_raw": bbox_raw,
                    "bbox_clamped": list(bbox_clamped),
                    "bbox_valid": True,
                    "image": "02_detection_bbox.png",
                },
                "measurement": {
                    "source": "dino_birefnet",
                    "eligible_for_dimension": False,
                },
                "debug": {
                    "steps": steps,
                    "dino_detection": detection_info,
                    "cutout_info": cutout_info,
                },
            }
            result = _jsonable(result)
            (job_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return result, 422

        _create_measurement_image(original_path, final_mask_path, measurement_path)
        steps.append({
            "step": "target_cutout",
            "status": "done",
            "source": measurement_source,
            "cutout_info": cutout_info,
        })

        try:
            raw_obstacle = legacy.analyze_obstacles_with_gpt(
                original_path,
                final_cutout_path,
                furniture_type=furniture_type,
            )
        except Exception as e:
            raw_obstacle = legacy._default_obstacle_analysis(
                f"obstacle_analysis_failed: {e}",
                furniture_type=furniture_type,
            )
        obstacle, obstacle_policy = _apply_service_obstacle_policy(raw_obstacle)
        steps.append({
            "step": "obstacle_analysis",
            "status": "done",
            "service_obstacle_status": obstacle.get("obstacle_status"),
            "raw_obstacle_status": raw_obstacle.get("obstacle_status"),
            "policy": obstacle_policy,
            **obstacle,
        })

        if obstacle.get("obstacle_status") == "structural_occlusion":
            warnings.append("structural_occlusion_low_confidence")

        obstacle_removed_file = None
        generation_cutout_file = None
        generation_mask_file = None
        inpainting_used = False
        preview_source = measurement_source

        if obstacle.get("obstacle_status") == "surface_obstacle":
            obstacle_removed_path = job_dir / "05_obstacle_removed.png"
            gpt_info = legacy.generate_obstacle_removed_image(
                original_path,
                obstacle_removed_path,
                obstacle,
                furniture_type,
            )
            if gpt_info.get("status") == "done" and obstacle_removed_path.exists():
                inpainting_used = True
                obstacle_removed_file = "05_obstacle_removed.png"
                generation_cutout_path = job_dir / "06_generation_cutout.png"
                generation_mask_path = job_dir / "06_generation_mask.png"
                generation_size = _image_size(obstacle_removed_path)
                generation_bbox = _scale_bbox(bbox_clamped, image_size, generation_size)
                try:
                    legacy.generate_dino_birefnet_cutout(
                        obstacle_removed_path,
                        generation_bbox,
                        generation_cutout_path,
                        generation_mask_path,
                        support_mask_path=None,
                        debug_dir=dino_debug_dir,
                    )
                    generation_validation = _validate_birefnet_mask_against_bbox(
                        generation_mask_path,
                        generation_bbox,
                    )
                    if not generation_validation["valid"]:
                        raise RuntimeError(f"generation_cutout_too_small: {generation_validation['reason']}")
                    generation_cutout_file = "06_generation_cutout.png"
                    generation_mask_file = "06_generation_mask.png"
                    preview_source = "obstacle_removed_dino_birefnet"
                except Exception as e:
                    warnings.append(f"generation_cutout_failed: {e}")
            else:
                warnings.extend(gpt_info.get("warnings", ["surface_obstacle_inpainting_failed"]))

        dimensions = _select_dimensions(
            body,
            measurement_path,
            title,
            description,
            furniture_type,
            "original_dino_birefnet_measurement",
        )
        warnings.extend([w for w in dimensions.get("warnings", []) if w not in warnings])
        steps.append({"step": "dimension_measurement", "status": "done", "dimensions": dimensions})

        structural = obstacle.get("obstacle_status") == "structural_occlusion"
        has_real_dimensions = dimensions.get("source") in ("listing_text_dimensions", "user_input_dimensions")
        confidence_level = "high"
        if structural or dimensions.get("confidence") == "low":
            confidence_level = "low"
        elif obstacle.get("confidence") == "medium" or dimensions.get("confidence") == "medium":
            confidence_level = "medium"

        final_decision = {
            "can_use_for_dimension": not structural,
            "can_use_for_3d_generation": not structural,
            "can_use_for_ar_scale": bool(has_real_dimensions and not structural),
            "confidence_level": confidence_level,
            "warnings": warnings,
        }

        result = {
            "job_id": job_id,
            "pipeline_version": "clean_v2_speed",
            "pipeline_status": "success",
            "input": {
                "url": body.url or None,
                "image_path": body.image_path or None,
                "selected_image_index": selected_idx,
                "selected_image_url": selected_image_url,
                "title": title,
                "description": description,
                "price": scraped.get("price", ""),
                "platform": scraped.get("platform"),
            },
            "furniture": {
                "type": furniture_type,
                "type_source": furniture["type_source"],
                "type_confidence": furniture["type_confidence"],
                "debug": {
                    "listing": furniture.get("listing"),
                    "vision": furniture.get("vision"),
                    "warning": furniture.get("warning"),
                },
            },
            "target_detection": {
                "method": "grounding_dino",
                "bbox_raw": bbox_raw,
                "bbox_clamped": list(bbox_clamped),
                "bbox_valid": True,
                "image": "02_detection_bbox.png",
                "debug": detection_info,
            },
            "measurement": {
                "source": measurement_source,
                "image": "02_measurement.png",
                "mask": "04_final_mask.png",
                "eligible_for_dimension": True,
            },
            "preview": {
                "source": preview_source,
                "image": generation_cutout_file or "03_final_cutout.png",
                "inpainting_used": inpainting_used,
            },
            "obstacle_analysis": obstacle,
            "dimensions": dimensions,
            "final_decision": final_decision,
            "files": {
                "original": "01_original.jpg",
                "target_detection": "02_detection_bbox.png",
                "measurement": "02_measurement.png",
                "final_cutout": "03_final_cutout.png",
                "final_mask": "04_final_mask.png",
                "obstacle_removed": obstacle_removed_file,
                "generation_cutout": generation_cutout_file,
                "generation_mask": generation_mask_file,
            },
            "debug": {
                "steps": steps,
                "cutout_info": cutout_info,
                "raw_obstacle_analysis": raw_obstacle,
                "obstacle_policy": obstacle_policy,
                "warnings": warnings,
            },
        }

        result = _jsonable(result)
        (job_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result, 200
    except HTTPException:
        raise
    except Exception as e:
        result = {
            "job_id": job_id,
            "pipeline_version": "clean_v2_speed",
            "pipeline_status": "failed",
            "error": str(e),
            "warnings": warnings,
            "debug": {"steps": steps},
        }
        (job_dir / "result.json").write_text(
            json.dumps(_jsonable(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result, 500


INDEX_HTML = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Clean Furniture Pipeline</title>
  <style>
    :root { color-scheme: light; --line:#d8dee9; --ink:#111827; --muted:#667085; --blue:#2563eb; --bg:#f6f8fb; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); }
    header { background:#fff; border-bottom:1px solid var(--line); padding:18px 24px; display:flex; gap:16px; align-items:center; justify-content:space-between; }
    h1 { margin:0; font-size:24px; letter-spacing:0; }
    .sub { color:var(--muted); font-size:14px; margin-top:4px; }
    main { padding:22px; max-width:1440px; margin:0 auto; }
    .controls { display:grid; grid-template-columns: 1fr 160px; gap:10px; background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; }
    input { width:100%; height:44px; border:1px solid var(--line); border-radius:6px; padding:0 12px; font-size:14px; }
    button { height:44px; border:0; border-radius:6px; background:var(--blue); color:#fff; font-size:15px; font-weight:700; cursor:pointer; }
    .grid { margin-top:18px; display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:14px; }
    .panel { background:#fff; border:1px solid var(--line); border-radius:8px; min-height:330px; overflow:hidden; }
    .panel h2 { margin:0; padding:12px 14px; border-bottom:1px solid var(--line); font-size:15px; }
    .panel img { width:100%; height:280px; object-fit:contain; background:#f9fafb; display:block; }
    .status { margin-top:14px; background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
    .kv { display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid #edf0f5; font-size:14px; }
    .kv span:first-child { color:var(--muted); }
    .badge { display:inline-block; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:700; }
    .ok { background:#dcfce7; color:#166534; }
    .warn { background:#fef3c7; color:#92400e; }
    .bad { background:#fee2e2; color:#991b1b; }
    details { margin-top:14px; background:#fff; border:1px solid var(--line); border-radius:8px; padding:12px; }
    pre { white-space:pre-wrap; overflow:auto; font-size:12px; }
    .hidden { display:none; }
    @media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, minmax(0,1fr)); } .status { grid-template-columns:1fr; } }
    @media (max-width: 640px) { header { display:block; } .controls { grid-template-columns:1fr; } .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Clean Furniture Pipeline</h1>
      <div class="sub">DINO bbox → boxed BiRefNet only → GPT obstacle only when needed → original-mask measurement</div>
    </div>
  </header>
  <main>
    <div class="controls">
      <input id="url" placeholder="당근/중고나라 URL 또는 local image path" />
      <button id="run">실행</button>
    </div>
    <div id="message" class="sub" style="margin:12px 2px;"></div>
    <section id="result" class="hidden">
      <div class="grid">
        <div class="panel"><h2>A. 원본 이미지</h2><img id="img-original" /></div>
        <div class="panel"><h2>B. 목표 가구 감지</h2><img id="img-detection" /></div>
        <div class="panel"><h2>C. 최종 누끼</h2><img id="img-cutout" /></div>
        <div class="panel"><h2>D. 측정 이미지</h2><img id="img-measurement" /></div>
      </div>
      <div class="status">
        <div>
          <div class="kv"><span>가구 타입</span><b id="furniture-type">-</b></div>
          <div class="kv"><span>누끼 소스</span><b id="measurement-source">-</b></div>
          <div class="kv"><span>장애물 상태</span><b id="obstacle-status">-</b></div>
          <div class="kv"><span>치수</span><b id="dimensions">-</b></div>
        </div>
        <div>
          <div class="kv"><span>치수 측정 가능</span><b id="can-dim">-</b></div>
          <div class="kv"><span>3D 생성 가능</span><b id="can-3d">-</b></div>
          <div class="kv"><span>AR scale 가능</span><b id="can-ar">-</b></div>
          <div class="kv"><span>신뢰도</span><b id="confidence">-</b></div>
        </div>
      </div>
      <div id="warnings" style="margin-top:12px;"></div>
      <details>
        <summary>debug result.json</summary>
        <pre id="raw-json"></pre>
      </details>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const boolBadge = (v) => `<span class="badge ${v ? 'ok' : 'bad'}">${v ? '가능' : '불가'}</span>`;
    $("run").onclick = async () => {
      const value = $("url").value.trim();
      if (!value) return;
      $("message").textContent = "처리 중입니다. DINO/BiRefNet 모델 로딩 때문에 첫 실행은 오래 걸릴 수 있습니다.";
      $("run").disabled = true;
      $("result").classList.add("hidden");
      const payload = value.startsWith("http") ? {url:value} : {image_path:value};
      try {
        const res = await fetch("/api/process", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok || data.pipeline_status === "failed") {
          $("message").textContent = data.error || data.detail || "처리 실패";
          $("raw-json").textContent = JSON.stringify(data, null, 2);
          return;
        }
        const job = data.job_id;
        const file = (name) => `/api/output/${job}/${name}`;
        $("img-original").src = file(data.files.original);
        $("img-detection").src = file(data.files.target_detection);
        $("img-cutout").src = file(data.preview.image || data.files.final_cutout);
        $("img-measurement").src = file(data.files.measurement);
        $("furniture-type").textContent = `${data.furniture.type} (${data.furniture.type_source}, ${data.furniture.type_confidence})`;
        $("measurement-source").textContent = data.measurement.source;
        $("obstacle-status").textContent = `${data.obstacle_analysis.obstacle_status} / ${data.obstacle_analysis.confidence}`;
        const d = data.dimensions || {};
        $("dimensions").textContent = `${d.width_cm ?? "-"} × ${d.depth_cm ?? "-"} × ${d.height_cm ?? "-"} cm (${d.source || "-"})`;
        $("can-dim").innerHTML = boolBadge(data.final_decision.can_use_for_dimension);
        $("can-3d").innerHTML = boolBadge(data.final_decision.can_use_for_3d_generation);
        $("can-ar").innerHTML = boolBadge(data.final_decision.can_use_for_ar_scale);
        $("confidence").innerHTML = `<span class="badge ${data.final_decision.confidence_level === 'high' ? 'ok' : data.final_decision.confidence_level === 'medium' ? 'warn' : 'bad'}">${data.final_decision.confidence_level}</span>`;
        const warns = data.final_decision.warnings || [];
        $("warnings").innerHTML = warns.length ? `<div class="badge warn" style="border-radius:6px;display:block;padding:10px;">${warns.join("<br>")}</div>` : "";
        $("raw-json").textContent = JSON.stringify(data, null, 2);
        $("result").classList.remove("hidden");
        $("message").textContent = "완료";
      } catch (e) {
        $("message").textContent = String(e);
      } finally {
        $("run").disabled = false;
      }
    };
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "framework": "fastapi", "pipeline_version": "clean_v2_speed"}


@app.post("/api/process")
def api_process(body: ProcessRequest) -> JSONResponse:
    data, status_code = run_clean_pipeline(body)
    return JSONResponse(content=data, status_code=status_code)


@app.get("/api/output/{job_id}/{filename}")
def serve_output(job_id: str, filename: str) -> FileResponse:
    safe_job_id = Path(job_id).name
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR / safe_job_id / safe_filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(file_path)
