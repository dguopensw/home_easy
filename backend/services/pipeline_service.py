"""파이프라인 서비스: SAM3 기반 가구 컷아웃 및 치수 추정 전체 흐름 오케스트레이션."""
from __future__ import annotations

import json
import logging
import os
import requests
import shutil
import uuid
from pathlib import Path

from core import _core, OUTPUT_DIR
from services.crawling_service import CrawlingService
from services.image_selector import ImageSelectorService
from services.furniture_analysis_service import FurnitureAnalysisService
from services.segmentation_service import SegmentationService
from services.inpainting_service import InpaintingService
from services.dimension_estimator import DimensionEstimatorService

logger = logging.getLogger(__name__)


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


class PipelineService:
    def __init__(self):
        self.crawling = CrawlingService()
        self.image_selector = ImageSelectorService()
        self.furniture_analysis = FurnitureAnalysisService()
        self.segmentation = SegmentationService()
        self.inpainting = InpaintingService()
        self.dimension_estimator = DimensionEstimatorService()

    def run_pipeline(
        self,
        url: str,
        selected_image_index: int,
        backend_public_url: str | None = None,
    ) -> tuple[dict, int]:
        """SAM3-only 파이프라인 실행.

        흐름:
        1.  스크래핑
        2.  선택 이미지 다운로드
        3.  가구 종류 추론
        4.  판매글 치수 파싱
        5.  SAM3 가구 마스크 생성
        6.  마스크 정제
        7.  측정용 이미지 생성 (원본 픽셀 + SAM3 마스크, 회색 배경)
        8.  최종 컷아웃 생성 (소프트 알파 마스크)
        9.  장애물 / 오염물 분석
        10. 인페인팅 (필요 시)
        11. 생성용 컷아웃 생성
        12. 치수 추정
        13. 품질 평가 및 최종 판단
        """
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
            # ── 1. 스크래핑 ───────────────────────────────────────────────
            platform = _core.identify_platform(url)
            if not platform:
                return {"error": "당근마켓 또는 중고나라 URL만 지원합니다."}, 400

            try:
                scraped = self.crawling.scrape_listing(url)
            except Exception as e:
                return {"error": f"스크래핑 실패: {e}", "job_id": job_id}, 500

            image_urls = scraped.get("images", [])
            if not image_urls:
                return {"error": "이미지를 찾을 수 없습니다.", "job_id": job_id}, 400

            title = scraped.get("title", "")
            description = scraped.get("description", "")

            # ── 2. 선택 이미지 다운로드 ───────────────────────────────────
            idx = selected_image_index if 0 <= selected_image_index < len(image_urls) else 0
            original_path = job_dir / "01_original.jpg"
            try:
                _core.download_image(image_urls[idx], original_path)
            except Exception as e:
                return {"error": f"이미지 다운로드 실패: {e}", "job_id": job_id}, 500

            # ── 3. 가구 종류 추론 ─────────────────────────────────────────
            furniture_info = self.furniture_analysis.infer_furniture_type(
                original_path, title, description
            )
            furniture_type = furniture_info["furniture_type"]
            logger.info("Furniture type: %s (%s)", furniture_type, furniture_info["confidence"])

            if furniture_type == "unknown":
                warnings.append("furniture_type_unknown")

            # ── 4. 판매글 치수 파싱 ───────────────────────────────────────
            listing_dims = self.crawling.parse_listing_dimensions(title, description)
            if listing_dims:
                logger.info("Listing dimensions found: %s", listing_dims)

            # ── 5. SAM3 가구 마스크 생성 ──────────────────────────────────
            raw_mask_path        = job_dir / "04_raw_mask.png"
            final_mask_path      = job_dir / "04_final_mask.png"
            soft_alpha_mask_path = job_dir / "04_final_alpha.png"

            furniture_mask_info = self.segmentation.generate_sam3_furniture_mask_natural(
                original_path, furniture_type, raw_mask_path,
                title=title, description=description,
            )

            if furniture_mask_info["status"] != "done":
                warnings.append("sam3_furniture_mask_failed")
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

            detected_family = furniture_mask_info.get("masking_family", "generic")
            detected_subtype = furniture_mask_info.get("category_subtype", "generic")
            masking_strategy.update({
                "family": detected_family,
                "category_subtype": detected_subtype,
                "strategy": furniture_mask_info.get("method", "unknown"),
                "risk_level": furniture_mask_info.get("risk_level", "normal"),
                "manual_review_recommended": furniture_mask_info.get("manual_review_recommended", False),
                "multi_box_union": "multi_box" in furniture_mask_info.get("method", ""),
                "whole_object_first": True,
                "part_based": False,
            })

            floor_cleanup_info = {
                "status": "skipped",
                "removed_floor_like_components": 0,
                "refined_bbox": None,
                "warnings": ["category_specific_floor_cleanup_removed"],
            }

            # ── 6. 마스크 정제 ────────────────────────────────────────────
            mask_refinement_info = self.segmentation.refine_mask_for_output(
                raw_mask_path, furniture_type, detected_family, detected_subtype,
                final_mask_path, soft_alpha_mask_path,
            )
            if mask_refinement_info["status"] != "done":
                shutil.copy2(str(raw_mask_path), str(final_mask_path))
                shutil.copy2(str(raw_mask_path), str(soft_alpha_mask_path))
                warnings.append("mask_refinement_failed_used_raw")

            # ── 7. 측정용 이미지 ──────────────────────────────────────────
            measurement_path = job_dir / "02_measurement.png"
            meas_build_info = self.segmentation.build_measurement_image_from_mask(
                original_path, final_mask_path, measurement_path,
            )
            if meas_build_info["status"] != "done":
                warnings.append("measurement_image_build_failed")

            # ── 8. 최종 컷아웃 ────────────────────────────────────────────
            final_cutout_path = job_dir / "03_final_cutout.png"
            cutout_build_info = self.segmentation.apply_mask_to_image(
                original_path, soft_alpha_mask_path, final_cutout_path
            )
            if cutout_build_info["status"] != "done":
                warnings.append("final_cutout_build_failed")

            # ── 9. 장애물 / 오염물 분석 ──────────────────────────────────
            obstacle_result = self.furniture_analysis.analyze_major_obstacles(
                original_path, furniture_type
            )
            has_major_obstacle = obstacle_result.get("has_major_obstacle", False)

            contaminant_result = self.furniture_analysis.analyze_generation_contaminants(
                original_path, furniture_type, masking_family=detected_family,
            )
            has_contaminants = contaminant_result.get("has_generation_contaminants", False)

            obstacle_mask_path = None
            obstacle_removed_path = None
            inpainting_used = False
            inpainting_info = None
            sam3_info = None
            contaminant_sam3_info = None
            boundary_occlusion_info: dict = {"has_boundary_occlusion": False}
            boundary_completion_info = None
            generation_mask_expansion_info = None
            boundary_completion_used = False

            # ── 10. 인페인팅 (필요 시) ────────────────────────────────────
            if has_major_obstacle or has_contaminants:
                import cv2
                import numpy as np

                obstacle_mask_arr = None
                contaminant_mask_arr = None
                cont_mask_file = None

                if has_major_obstacle:
                    obs_mask_file = job_dir / "05_obstacle_mask.png"
                    sam3_info = self.segmentation.segment_objects_with_sam3(
                        original_path, obstacle_result.get("obstacles", []),
                        None, obs_mask_file, mode="major_obstacle",
                    )
                    if sam3_info["status"] == "done":
                        obstacle_mask_path = obs_mask_file
                        _m = cv2.imread(str(obs_mask_file), cv2.IMREAD_GRAYSCALE)
                        if _m is not None:
                            obstacle_mask_arr = _m
                    else:
                        reason = sam3_info.get("error") or sam3_info.get("status", "unknown")
                        warnings.append(f"obstacle_mask_generation_failed_{reason}")

                if has_contaminants:
                    cont_mask_file = job_dir / "07_contaminant_mask.png"
                    contaminant_sam3_info = self.segmentation.segment_objects_with_sam3(
                        original_path, contaminant_result.get("contaminants", []),
                        None, cont_mask_file, mode="generation_contaminant",
                    )
                    if contaminant_sam3_info["status"] == "done":
                        _m = cv2.imread(str(cont_mask_file), cv2.IMREAD_GRAYSCALE)
                        if _m is not None:
                            contaminant_mask_arr = _m
                        warnings.append("generation_contaminants_detected")
                    else:
                        warnings.append("generation_contaminant_mask_failed_fallback_to_original")
                        cont_mask_file = None

                # 경계 폐색 분석 (오염물만)
                if cont_mask_file is not None and contaminant_mask_arr is not None and final_mask_path.exists():
                    boundary_occlusion_info = self.inpainting.analyze_boundary_occlusion(
                        final_mask_path, cont_mask_file, furniture_type, detected_family,
                    )

                has_boundary_occ = boundary_occlusion_info.get("has_boundary_occlusion", False)

                if has_boundary_occ and cont_mask_file is not None:
                    # 경계 복원 경로
                    completion_mask_path = job_dir / "08_boundary_completion_mask.png"
                    boundary_completion_info = self.inpainting.build_boundary_completion_mask(
                        final_mask_path, cont_mask_file, boundary_occlusion_info,
                        completion_mask_path, masking_family=detected_family,
                    )

                    if boundary_completion_info.get("status") == "done":
                        if obstacle_mask_arr is not None:
                            comp_arr = cv2.imread(str(completion_mask_path), cv2.IMREAD_GRAYSCALE)
                            union_bc = np.maximum(
                                obstacle_mask_arr,
                                comp_arr if comp_arr is not None else np.zeros_like(obstacle_mask_arr),
                            )
                            cv2.imwrite(str(job_dir / "07_union_mask.png"), union_bc)
                            lama_src_mask = job_dir / "07_union_mask.png"
                        else:
                            lama_src_mask = completion_mask_path

                        boundary_completed_path = job_dir / "08_boundary_completed.png"
                        bc_result = self.inpainting.inpaint_with_flux(
                            original_path, lama_src_mask, boundary_completed_path,
                            furniture_type=furniture_type,
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
                        else:
                            warnings.append("boundary_completion_lama_failed_fallback")
                            has_boundary_occ = False
                    else:
                        warnings.append("boundary_completion_mask_build_failed_fallback")
                        has_boundary_occ = False

                if not has_boundary_occ:
                    union_arr = None
                    if obstacle_mask_arr is not None and contaminant_mask_arr is not None:
                        union_arr = np.maximum(obstacle_mask_arr, contaminant_mask_arr)
                    elif obstacle_mask_arr is not None:
                        union_arr = obstacle_mask_arr
                    elif contaminant_mask_arr is not None:
                        union_arr = contaminant_mask_arr

                    if union_arr is not None:
                        union_mask_path = job_dir / "07_union_mask.png"
                        cv2.imwrite(str(union_mask_path), union_arr)

                        obs_removed_file = job_dir / "05_obstacle_removed.png"
                        inpainting_info = self.inpainting.inpaint_with_flux(
                            original_path, union_mask_path, obs_removed_file,
                            furniture_type=furniture_type,
                        )

                        if inpainting_info["status"] == "done":
                            inpainting_used = True
                            obstacle_removed_path = obs_removed_file
                            if has_contaminants:
                                warnings.append("generation_uses_contaminant_removed_image")
                        else:
                            warnings.append("flux_inpainting_failed_fallback_to_original")

            # ── 11. 생성용 컷아웃 ─────────────────────────────────────────
            generation_cutout_path = None
            generation_mask_path = None
            generation_cutout_quality: dict = {"quality": "unknown", "warnings": []}

            if inpainting_used and obstacle_removed_path and obstacle_removed_path.exists():
                gen_cutout_file = job_dir / "06_generation_cutout.png"
                gen_mask_file   = job_dir / "06_generation_mask.png"

                # 인페인팅된 이미지에 SAM 재실행 → 담요 등이 사라진 상태의 깨끗한 가구 마스크 생성
                # BrushNet 합성 덕분에 마스크 영역 외에는 원본 픽셀이 그대로라 SAM 결과가 안정적
                gen_raw_mask_file = job_dir / "06_generation_raw_mask.png"
                gen_alpha_mask_file = job_dir / "06_generation_alpha_mask.png"

                regen_info = self.segmentation.generate_sam3_furniture_mask_natural(
                    obstacle_removed_path, furniture_type, gen_raw_mask_file,
                    title=title, description=description,
                )
                generation_mask_expansion_info = {"method": "sam_rerun_on_inpainted", "status": regen_info.get("status")}

                if regen_info.get("status") == "done":
                    # 재실행된 마스크도 동일한 정제 파이프라인 적용
                    regen_refine_info = self.segmentation.refine_mask_for_output(
                        gen_raw_mask_file, furniture_type, detected_family, detected_subtype,
                        gen_mask_file, gen_alpha_mask_file,
                    )
                    if regen_refine_info["status"] != "done":
                        shutil.copy2(str(gen_raw_mask_file), str(gen_mask_file))
                        warnings.append("generation_mask_refine_failed_used_raw")
                    gen_mask_for_cutout = gen_mask_file
                    warnings.append("generation_mask_regenerated_via_sam_on_inpainted")
                else:
                    # SAM 재실행 실패 시 기존 방식으로 폴백
                    warnings.append("generation_sam_rerun_failed_fallback_to_original_mask")
                    if boundary_completion_used and cont_mask_file is not None:
                        generation_mask_expansion_info = self.inpainting.expand_generation_mask_for_boundary_completion(
                            final_mask_path, cont_mask_file, gen_mask_file,
                            boundary_occlusion_info, masking_family=detected_family,
                        )
                    else:
                        shutil.copy2(str(final_mask_path), str(gen_mask_file))
                    gen_mask_for_cutout = gen_mask_file

                gen_build_info = self.segmentation.apply_mask_to_image(
                    obstacle_removed_path, gen_mask_for_cutout, gen_cutout_file,
                )
                if gen_build_info["status"] == "done":
                    generation_cutout_path = gen_cutout_file
                    generation_mask_path   = gen_mask_file
                    generation_cutout_quality = self.segmentation.evaluate_cutout_quality(
                        gen_mask_file, furniture_type
                    )
            else:
                if final_mask_path.exists():
                    generation_cutout_quality = self.segmentation.evaluate_cutout_quality(
                        final_mask_path, furniture_type
                    )

            # ── 12. 컷아웃 품질 평가 ─────────────────────────────────────
            cutout_quality: dict = {"quality": "unknown", "warnings": []}
            if final_mask_path.exists():
                cutout_quality = self.segmentation.evaluate_cutout_quality(
                    final_mask_path, furniture_type
                )

            # ── 13. 치수 추정 ─────────────────────────────────────────────
            meas_source = measurement_path if measurement_path.exists() else original_path
            dimensions = self.dimension_estimator.estimate_dimensions(
                meas_source, title, description, furniture_type, listing_dims
            )

            dim_confidence = dimensions.get("confidence", "low")
            if dim_confidence == "low":
                warnings.append("dimension_confidence_low")
            for w in (dimensions.get("warnings") or []):
                if w not in warnings:
                    warnings.append(w)

            # ── 최종 판단 ────────────────────────────────────────────────
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

            family_manual_review = masking_strategy.get("manual_review_recommended", False)
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
                "contaminant_mask": "07_contaminant_mask.png"
                    if (job_dir / "07_contaminant_mask.png").exists() else None,
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

            trellis_base_url = os.getenv("TRELLIS_BASE_URL", "").rstrip("/")
            backend_public_url = (backend_public_url or os.getenv("BACKEND_PUBLIC_URL", "")).rstrip("/")

            model_generation = {
                "status": "skipped",
                "trellis_job_id": job_id,
                "input_file": None,
                "image_url": None,
                "glb_url": None,
                "error": None,
            }

            trellis_input_file = None
            if generation_cutout_path and generation_cutout_path.exists():
                trellis_input_file = "06_generation_cutout.png"
            elif final_cutout_path.exists():
                trellis_input_file = "03_final_cutout.png"

            if trellis_input_file and trellis_base_url and backend_public_url:
                image_url = (
                    f"{backend_public_url}/api/furniture/output/"
                    f"{job_id}/{trellis_input_file}"
                )
                try:
                    response = requests.post(
                        f"{trellis_base_url}/generate",
                        json={"job_id": job_id, "image_url": image_url},
                        timeout=15,
                    )
                    response.raise_for_status()
                    model_generation.update({
                        "status": "processing",
                        "input_file": trellis_input_file,
                        "image_url": image_url,
                    })
                except Exception as e:
                    model_generation.update({
                        "status": "failed_to_start",
                        "input_file": trellis_input_file,
                        "image_url": image_url,
                        "error": str(e),
                    })
                    logger.warning("TRELLIS generation start failed: job_id=%s error=%s", job_id, e)
            elif trellis_input_file:
                model_generation.update({
                    "status": "not_configured",
                    "input_file": trellis_input_file,
                    "error": "TRELLIS_BASE_URL or BACKEND_PUBLIC_URL is missing",
                })

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
                "model_generation": model_generation,
                "sam3_obstacle_info": sam3_info,
                "sam3_contaminant_info": contaminant_sam3_info,
                "debug": {
                    "sam3_info": sam3_info,
                    "contaminant_sam3_info": contaminant_sam3_info,
                    "inpainting_info": inpainting_info,
                    "floor_cleanup_info": floor_cleanup_info,
                    "mask_refinement_info": mask_refinement_info,
                    "boundary_occlusion_info": boundary_occlusion_info,
                    "boundary_completion_info": boundary_completion_info,
                    "generation_mask_expansion_info": generation_mask_expansion_info,
                    "furniture_info": furniture_info,
                },
            }

            (job_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("Pipeline complete: job_id=%s", job_id)
            return result, 200

        except Exception as e:
            logger.exception("Pipeline failed: job_id=%s", job_id)
            return {"error": str(e), "job_id": job_id}, 500
