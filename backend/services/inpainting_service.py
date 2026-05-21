"""인페인팅 서비스: LaMa를 이용한 장애물/오염물 제거 및 경계 복원."""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from core import LAMA_WORKER_PATH

logger = logging.getLogger(__name__)


class InpaintingService:
    # ── LaMa 인페인팅 ─────────────────────────────────────────────────────

    def inpaint_with_lama(
        self,
        image_path: Path,
        obstacle_mask_path: Path,
        output_path: Path,
    ) -> dict:
        """LaMa로 마스크 영역을 인페인팅합니다.

        우선순위:
        1. IOPaint CLI (LaMa 백엔드)
        2. simple_lama_inpainting Python 패키지
        3. 폴백: 원본 이미지 사용
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        BASE_WARNINGS = [
            "inpainting_used",
            "generation_uses_inpainted_image",
            "not_for_measurement",
        ]

        _LAMA_PYTHON = os.environ.get("LAMA_PYTHON", "/opt/miniconda3/envs/lama_env/bin/python")
        _LAMA_WORKER = str(LAMA_WORKER_PATH)

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

    # ── 경계 폐색 분석 ────────────────────────────────────────────────────

    @staticmethod
    def analyze_boundary_occlusion(
        furniture_mask_path: Path,
        contaminant_mask_path: Path,
        furniture_type: str,
        masking_family: str,
    ) -> dict:
        """오염물 마스크가 가구 마스크 경계와 겹치는지 검사합니다."""
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

        overlap = int((boundary_band & cont_bin).sum())
        ratio   = overlap / cont_area
        threshold = 0.03

        if ratio < threshold:
            return {"has_boundary_occlusion": False, "boundary_overlap_ratio": round(ratio, 4),
                    "occlusion_side": "none", "reason": "overlap_below_threshold", "warnings": []}

        furn_ys, furn_xs = np.where(furn_mask > 127)
        if len(furn_xs) == 0:
            return {"has_boundary_occlusion": False, "boundary_overlap_ratio": round(ratio, 4),
                    "occlusion_side": "none", "reason": "empty_furniture_mask", "warnings": []}
        fx1, fy1 = int(furn_xs.min()), int(furn_ys.min())
        fx2, fy2 = int(furn_xs.max()), int(furn_ys.max())
        fw, fh = fx2 - fx1, fy2 - fy1

        cont_ys, cont_xs = np.where(cont_bin)
        cx1, cy1 = int(cont_xs.min()), int(cont_ys.min())
        cx2, cy2 = int(cont_xs.max()), int(cont_ys.max())
        ccx = (cx1 + cx2) / 2
        ccy = (cy1 + cy2) / 2

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
            return {"has_boundary_occlusion": False, "boundary_overlap_ratio": round(ratio, 4),
                    "occlusion_side": "internal",
                    "reason": "contaminant_centroid_inside_furniture", "warnings": []}

        logger.info("Boundary occlusion detected: side=%s ratio=%.3f family=%s",
                    side, ratio, masking_family)
        return {
            "has_boundary_occlusion": True,
            "boundary_overlap_ratio": round(ratio, 4),
            "occlusion_side": side,
            "reason": f"contaminant overlaps {side} boundary of furniture mask, may hide outer edge",
            "warnings": ["boundary_occluder_detected"],
        }

    # ── 경계 복원 마스크 생성 ─────────────────────────────────────────────

    @staticmethod
    def build_boundary_completion_mask(
        furniture_mask_path: Path,
        contaminant_mask_path: Path,
        boundary_info: dict,
        output_mask_path: Path,
        masking_family: str = "generic",
    ) -> dict:
        """경계 복원용 인페인팅 마스크를 생성합니다."""
        import cv2
        import numpy as np

        furn_mask = cv2.imread(str(furniture_mask_path), cv2.IMREAD_GRAYSCALE)
        cont_mask  = cv2.imread(str(contaminant_mask_path), cv2.IMREAD_GRAYSCALE)
        if furn_mask is None or cont_mask is None:
            return {"status": "failed", "mask_coverage": 0.0, "warnings": ["cannot_read_masks"]}

        h, w = furn_mask.shape
        if cont_mask.shape != furn_mask.shape:
            cont_mask = cv2.resize(cont_mask, (w, h), interpolation=cv2.INTER_LINEAR)

        completion = (cont_mask > 127).astype(np.uint8)
        side       = boundary_info.get("occlusion_side", "none")
        band_px    = max(20, int(min(h, w) * 0.025))
        kernel     = np.ones((band_px, band_px), np.uint8)
        dilated    = cv2.dilate(furn_mask, kernel, iterations=1)
        eroded     = cv2.erode(furn_mask, kernel, iterations=1)
        band_mask  = ((dilated > 127) & ~(eroded > 127)).astype(np.uint8)

        if side == "right":
            roi = np.zeros((h, w), np.uint8); roi[:, max(0, w // 2):] = 1
            completion = np.maximum(completion, band_mask & roi)
        elif side == "left":
            roi = np.zeros((h, w), np.uint8); roi[:, :min(w, w // 2)] = 1
            completion = np.maximum(completion, band_mask & roi)
        elif side == "bottom":
            roi = np.zeros((h, w), np.uint8); roi[max(0, h // 2):, :] = 1
            completion = np.maximum(completion, band_mask & roi)
        elif side == "top":
            roi = np.zeros((h, w), np.uint8); roi[:min(h, h // 2), :] = 1
            completion = np.maximum(completion, band_mask & roi)
        else:
            completion = np.maximum(completion, band_mask)

        coverage = float(completion.sum()) / (h * w)
        warnings: list[str] = []
        if coverage > 0.08:
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

    @staticmethod
    def expand_generation_mask_for_boundary_completion(
        final_mask_path: Path,
        completion_mask_path: Path,
        output_generation_mask_path: Path,
        boundary_info: dict,
        masking_family: str = "generic",
    ) -> dict:
        """경계 복원 영역을 포함하도록 생성용 마스크를 확장합니다."""
        import cv2
        import numpy as np

        furn = cv2.imread(str(final_mask_path),       cv2.IMREAD_GRAYSCALE)
        comp = cv2.imread(str(completion_mask_path),  cv2.IMREAD_GRAYSCALE)
        if furn is None or comp is None:
            return {"status": "failed", "mask_expanded": False, "warnings": ["cannot_read_masks"]}

        h, w = furn.shape
        if comp.shape != furn.shape:
            comp = cv2.resize(comp, (w, h), interpolation=cv2.INTER_LINEAR)

        band_px = max(30, int(min(h, w) * 0.04))
        kernel  = np.ones((band_px, band_px), np.uint8)
        dilated = cv2.dilate(furn, kernel, iterations=1)
        boundary_extension = (dilated > 127) & (comp > 127)

        cov_before = float(np.count_nonzero(furn > 127)) / (h * w)
        expanded   = np.maximum(furn, (boundary_extension * 255).astype(np.uint8))
        cov_after  = float(np.count_nonzero(expanded > 127)) / (h * w)
        delta      = cov_after - cov_before

        warnings: list[str] = []
        if delta > 0.03:
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
