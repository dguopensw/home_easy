"""세그멘테이션 서비스: SAM3 마스크 생성, 마스크 정제, 이미지 합성."""
from __future__ import annotations

import logging
from pathlib import Path

from core import _core

logger = logging.getLogger(__name__)


def get_masking_family(furniture_type: str, title: str = "", description: str = "") -> str:
    """마스킹 패밀리 반환 (현재는 generic 고정)."""
    return "generic"


class SegmentationService:
    # ── SAM3 가구 마스크 생성 ──────────────────────────────────────────────

    def generate_sam3_furniture_mask_natural(
        self,
        image_path: Path,
        furniture_type: str,
        output_mask_path: Path,
        title: str = "",
        description: str = "",
        debug_dir: Path | None = None,
        sam3_prompts: list[str] | None = None,
    ) -> dict:
        """SAM3로 가구 마스크를 생성합니다 (텍스트 프롬프트 기반).

        sam3_prompts: GPT-vision이 이미지·게시글 텍스트를 종합해 만든 SAM3 호환 짧은
        명사구 리스트. 주어지면 ". "로 join해 한 번에 SAM3에 전달 (proxy가 split + union).
        없으면 furniture_type 한 단어로 폴백.
        """
        import cv2
        import numpy as np

        masking_family = get_masking_family(furniture_type, title, description)

        img = cv2.imread(str(image_path))
        if img is None:
            return {"status": "failed", "error": "cannot_read_image",
                    "masking_family": masking_family, "valid_part_count": 0}
        h, w = img.shape[:2]

        try:
            from PIL import Image as _PIL_Image

            segmenter = _core.get_segmenter()

            if not hasattr(segmenter, "segment_text"):
                return {"status": "failed", "error": "sam3_segmenter_unavailable",
                        "masking_family": masking_family, "valid_part_count": 0}

            pil_image = _PIL_Image.open(image_path).convert("RGB")

            cleaned_prompts = [p.strip().rstrip(".") for p in (sam3_prompts or []) if p and p.strip()]
            if cleaned_prompts:
                prompts_used_log = cleaned_prompts
            else:
                base = furniture_type if furniture_type != "unknown" else "furniture"
                prompts_used_log = [base]

            # 가구 마스킹: threshold=None 으로 raw 결과 그대로 수용 (legacy proxy 동작과 동일)
            # NaN 점수 박스도 포함 — 이후 cov 필터 (0.001~0.95) 가 노이즈 거름
            seg = segmenter.segment_text(pil_image, prompts_used_log, threshold=None)
            boxes = seg["boxes"]
            masks = seg["masks"]
            actual_prompts = seg["sam3_actual_prompts"]

            if boxes is None or len(boxes) == 0 or masks is None or len(masks) == 0:
                return {"status": "failed", "error": "no_detections",
                        "masking_family": masking_family, "valid_part_count": 0,
                        "prompts_used": prompts_used_log,
                        "sam3_actual_prompts": actual_prompts}

            union_mask = np.zeros((h, w), dtype=np.uint8)
            added = 0
            for i in range(len(boxes)):
                part_mask = (masks[i, 0].cpu().float().numpy() > 0).astype(np.uint8) * 255
                cov = float(np.count_nonzero(part_mask > 127)) / (h * w)
                if cov < 0.001 or cov > 0.95:
                    continue
                union_mask = np.maximum(union_mask, part_mask)
                added += 1

            if added == 0:
                return {"status": "failed", "error": "no_valid_masks",
                        "masking_family": masking_family, "valid_part_count": 0,
                        "prompts_used": prompts_used_log,
                        "sam3_actual_prompts": actual_prompts}

            output_mask_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_mask_path), union_mask)

            mask_coverage = float(np.count_nonzero(union_mask > 127)) / (h * w)
            ys, xs = np.where(union_mask > 127)
            bbox = ([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                    if len(xs) > 0 else None)

            logger.info("SAM3 mask done: family=%s prompts=%s valid_masks=%d coverage=%.3f",
                        masking_family, prompts_used_log, added, mask_coverage)
            return {
                "status": "done",
                "method": "sam3_natural_direct_mask",
                "masking_family": masking_family,
                "prompts_used": prompts_used_log,
                "sam3_actual_prompts": actual_prompts,
                "valid_part_count": added,
                "mask_coverage": round(mask_coverage, 4),
                "bbox": bbox,
                "warnings": [],
            }

        except Exception as e:
            logger.warning("generate_sam3_furniture_mask_natural failed: %s", e)
            return {"status": "failed", "error": str(e),
                    "masking_family": masking_family, "valid_part_count": 0}

    # ── SAM3 객체(장애물/오염물) 마스크 생성 ──────────────────────────────

    def segment_objects_with_sam3(
        self,
        image_path: Path,
        objects: list[dict],
        furniture_dino_bbox: list | None = None,
        output_mask_path: Path = None,
        mode: str = "major_obstacle",
    ) -> dict:
        """SAM3 직접 호출로 장애물/오염물 마스크를 생성합니다."""
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path))
        if img is None:
            return {"status": "failed", "error": "cannot_read_image", "mask_coverage": 0.0}
        h, w = img.shape[:2]

        object_names = [o.get("name", "object") for o in objects]
        if not object_names:
            object_names = ["obstacle on furniture" if mode == "major_obstacle" else "object on furniture"]

        # SAM3 paper requires short noun phrases — feed GPT names directly without location.
        # Spatial info from GPT lives in result.json's contaminants[].location for display only.
        prompt_text = ". ".join(object_names) + "."

        area_threshold = 0.35 if mode == "generation_contaminant" else 0.70

        try:
            from PIL import Image

            segmenter = _core.get_segmenter()

            if not hasattr(segmenter, "segment_text") or not hasattr(segmenter, "segment_box"):
                return {"status": "failed", "error": "sam3_segmenter_unavailable", "mask_coverage": 0.0}

            pil_image = Image.open(image_path).convert("RGB")

            seg = segmenter.segment_text(pil_image, object_names, threshold=0.20)
            boxes = seg["boxes"]
            sam3_actual_prompts = seg["sam3_actual_prompts"]

            if boxes is None or len(boxes) == 0:
                logger.warning("SAM3: no detections for: %s", prompt_text)
                return {
                    "status": "no_detections", "error": None, "mask_coverage": 0.0,
                    "prompts_used": object_names, "prompt_text": prompt_text,
                    "sam3_actual_prompts": sam3_actual_prompts,
                }

            union_mask = np.zeros((h, w), dtype=np.uint8)
            obstacle_count = 0

            for i in range(len(boxes)):
                box = boxes[i].detach().cpu().numpy()
                box_w = box[2] - box[0]
                box_h = box[3] - box[1]

                if (box_w * box_h) / (w * h) > area_threshold:
                    continue

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

                masks_pred, sam_scores = segmenter.segment_box(pil_image, box)
                best_idx = int(np.argmax(sam_scores))
                mask = masks_pred[best_idx].astype(np.uint8) * 255
                union_mask = np.maximum(union_mask, mask)
                obstacle_count += 1

            if obstacle_count == 0:
                return {"status": "no_valid_detections", "error": None,
                        "mask_coverage": 0.0, "prompts_used": object_names,
                        "prompt_text": prompt_text,
                        "sam3_actual_prompts": sam3_actual_prompts}

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
                "prompt_text": prompt_text,
                "sam3_actual_prompts": sam3_actual_prompts,
                "warnings": seg_warnings,
            }

        except Exception as e:
            logger.warning("SAM3 object segmentation failed: %s", e)
            return {"status": "failed", "error": str(e), "mask_coverage": 0.0}

    # ── 마스크 정제 헬퍼 ──────────────────────────────────────────────────

    @staticmethod
    def _remove_small_mask_artifacts(mask, min_component_area_ratio: float = 0.0005):
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
                comp_w = int(stats[i, cv2.CC_STAT_WIDTH])
                comp_h = int(stats[i, cv2.CC_STAT_HEIGHT])
                aspect = max(comp_w, comp_h) / max(min(comp_w, comp_h), 1)
                if aspect >= 3.0:
                    result = np.maximum(result, (labels == i).astype(np.uint8) * 255)
        return result

    @staticmethod
    def _fill_small_holes_safely(mask, max_hole_area_ratio: float = 0.001):
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
                continue
            x  = int(stats[i, cv2.CC_STAT_LEFT])
            y  = int(stats[i, cv2.CC_STAT_TOP])
            x2 = x + int(stats[i, cv2.CC_STAT_WIDTH])
            y2 = y + int(stats[i, cv2.CC_STAT_HEIGHT])
            if x <= 0 or y <= 0 or x2 >= w - 1 or y2 >= h - 1:
                continue
            result[labels == i] = 1

        return (result * 255).astype(np.uint8)

    @staticmethod
    def _feather_alpha_mask(hard_mask_path: Path, output_alpha_mask_path: Path, blur_radius: int = 3) -> dict:
        import cv2
        import numpy as np

        hard = cv2.imread(str(hard_mask_path), cv2.IMREAD_GRAYSCALE)
        if hard is None:
            return {"status": "failed", "blur_radius": blur_radius, "warnings": ["cannot_read_hard_mask"]}

        erode_k = max(3, blur_radius * 2 + 1)
        core_mask = cv2.erode(hard, np.ones((erode_k, erode_k), np.uint8), iterations=1)

        blur_k = blur_radius * 2 + 1
        blurred = cv2.GaussianBlur(hard.astype(np.float32), (blur_k, blur_k), 0)

        alpha = np.clip(blurred, 0, 255).astype(np.uint8)
        alpha[core_mask > 127] = 255

        output_alpha_mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_alpha_mask_path), alpha)
        return {"status": "done", "blur_radius": blur_radius, "warnings": []}

    def refine_mask_for_output(
        self,
        mask_path: Path,
        furniture_type: str,
        masking_family: str,
        category_subtype: str,
        output_hard_mask_path: Path,
        output_alpha_mask_path: Path,
    ) -> dict:
        """SAM3 원시 마스크를 정제합니다: 아티팩트 제거, 구멍 채우기, 경계 스무딩."""
        import cv2
        import numpy as np

        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            return {
                "status": "failed", "warnings": ["cannot_read_mask"],
                "small_components_removed": 0, "small_holes_filled": 0, "feather_applied": False,
            }

        min_artifact_ratio = 0.0005
        max_hole_ratio = 0.0010

        before_px = int(np.count_nonzero(mask > 127))
        cleaned = self._remove_small_mask_artifacts(mask, min_component_area_ratio=min_artifact_ratio)
        after_px = int(np.count_nonzero(cleaned > 127))
        components_removed_est = max(0, (before_px - after_px) // max(1, int(
            mask.shape[0] * mask.shape[1] * min_artifact_ratio * 0.5)))

        before_fill = int(np.count_nonzero(cleaned > 127))
        filled = self._fill_small_holes_safely(cleaned, max_hole_area_ratio=max_hole_ratio)
        holes_filled_est = max(0, (int(np.count_nonzero(filled > 127)) - before_fill) // max(1, int(
            mask.shape[0] * mask.shape[1] * max_hole_ratio * 0.5)))

        smoothed = cv2.medianBlur(filled, 3)
        smoothed = np.where(filled > 127, np.maximum(smoothed, 200), smoothed).astype(np.uint8)

        hard_mask = (smoothed > 127).astype(np.uint8) * 255
        output_hard_mask_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_hard_mask_path), hard_mask)

        feather_info = self._feather_alpha_mask(output_hard_mask_path, output_alpha_mask_path)

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

    # ── 가구 마스크 내부 구멍 검출 (방식 A) ────────────────────────────────

    @staticmethod
    def compute_internal_holes(
        mask_path: Path,
        output_path: Path,
        closing_kernel_ratio: float = 0.05,
        min_hole_area_ratio: float = 0.0005,
    ) -> dict:
        """가구 마스크의 '이상적 실루엣' 안에 있는 구멍을 contaminant 후보로 검출.

        흐름:
          1) morphological closing 으로 가구의 외곽 실루엣을 메움
          2) 실루엣 ∩ ¬(원본 마스크) = 내부 구멍
          3) 너무 작은 노이즈는 제거 (min_hole_area_ratio 미만 컴포넌트)

        외부 배경과 연결된 영역은 닫히지 않으므로 구멍으로 검출되지 않음 (의도된 동작).
        """
        import cv2
        import numpy as np

        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            return {"status": "failed", "error": "cannot_read_mask",
                    "hole_count": 0, "coverage": 0.0}

        h, w = mask.shape
        binary = (mask > 127).astype(np.uint8)

        k = max(11, int(min(h, w) * closing_kernel_ratio))
        if k % 2 == 0:
            k += 1
        kernel = np.ones((k, k), np.uint8)
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        holes = ((closed > 0) & (binary == 0)).astype(np.uint8) * 255

        num, labels, stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=8)
        min_area = int(h * w * min_hole_area_ratio)
        filtered = np.zeros_like(holes)
        kept = 0
        for i in range(1, num):
            if int(stats[i, cv2.CC_STAT_AREA]) >= min_area:
                filtered = np.maximum(filtered, (labels == i).astype(np.uint8) * 255)
                kept += 1

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), filtered)

        coverage = float(np.count_nonzero(filtered) / (h * w))
        return {
            "status": "done",
            "method": "morphological_closing_internal_holes",
            "hole_count": kept,
            "coverage": round(coverage, 4),
            "closing_kernel_size": k,
        }

    # ── 이미지 합성 헬퍼 ──────────────────────────────────────────────────

    @staticmethod
    def apply_mask_to_image(image_path: Path, mask_path: Path, output_png_path: Path) -> dict:
        """마스크를 알파 채널로 적용해 투명 배경 RGBA PNG를 생성합니다."""
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

    @staticmethod
    def build_measurement_image_from_mask(
        image_path: Path, mask_path: Path, output_path: Path
    ) -> dict:
        """마스크 내부는 원본 픽셀, 외부는 중성 회색(128)으로 측정용 이미지를 생성합니다."""
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

    # ── 컷아웃 품질 평가 ──────────────────────────────────────────────────

    @staticmethod
    def evaluate_cutout_quality(mask_path: Path, furniture_type: str) -> dict:
        """최종 마스크의 배경/바닥 누수 여부를 검사합니다."""
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
