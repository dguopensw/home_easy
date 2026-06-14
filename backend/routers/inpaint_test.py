"""인페인팅 트러블슈팅 비교 테스트 엔드포인트.

발표 자료(시도 1 LaMa blur, 시도 2 Nano Banana 단독 비율 변형)용 '부정확한
전처리 결과 이미지'를 직접 생성하기 위한 개발용 라우터. 이미지(+선택적 마스크)를
업로드하고 방식을 선택하면 결과 이미지를 저장·서빙한다.

운영 파이프라인(/api/process)과는 독립적이며 static/index.html의 비교 카드에서 호출한다.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from core import OUTPUT_DIR
from services.inpainting_service import InpaintingService
from services.segmentation_service import SegmentationService

logger = logging.getLogger(__name__)

router = APIRouter()
_service = InpaintingService()
_segmentation = SegmentationService()
_TEST_ROOT = OUTPUT_DIR / "_inpaint_test"

# 마스크가 필요한 방식
_NEEDS_MASK = {"lama", "lama_composite", "flux", "banana_brushnet"}
_VALID_METHODS = _NEEDS_MASK | {"banana_e2e"}


def _suffix(filename: str | None, default: str = ".png") -> str:
    if filename and "." in filename:
        ext = Path(filename).suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            return ext
    return default


def _file_url(job: str, name: str) -> str:
    return f"/api/inpaint-test/file/{job}/{name}"


def _run_sam3_check(
    job: str,
    job_dir: Path,
    inpainted_path: Path,
    furniture_type: str,
    inpaint_mask_path: Path | None,
    sam3_prompts: list[str] | None = None,
) -> dict:
    """인페인팅 결과에 SAM3 가구 마스킹을 재실행해 인식 여부를 검사한다.

    인페인팅된 영역이 다시 '가구'로 인식되는지(=구멍이 안 생기는지)가 핵심 지표.
    sam3_prompts: SAM3에 직접 넣을 텍스트 프롬프트 리스트(없으면 furniture_type 폴백).
    """
    sam3_mask = job_dir / "sam3_remask.png"
    info = _segmentation.generate_sam3_furniture_mask_natural(
        inpainted_path,
        furniture_type or "furniture",
        sam3_mask,
        sam3_prompts=sam3_prompts or None,
    )
    out: dict = {
        "status": info.get("status"),
        "mask_coverage": info.get("mask_coverage"),
        "valid_part_count": info.get("valid_part_count"),
        "prompts_used": info.get("prompts_used"),
        "sam3_actual_prompts": info.get("sam3_actual_prompts"),
        "error": info.get("error"),
    }
    if info.get("status") == "done" and sam3_mask.exists():
        out["mask_url"] = _file_url(job, sam3_mask.name)
        # SAM3가 인식한 영역만 잘라낸 컷아웃 (시각 확인용)
        cutout = job_dir / "sam3_cutout.png"
        try:
            _segmentation.apply_mask_to_image(inpainted_path, sam3_mask, cutout)
            if cutout.exists():
                out["cutout_url"] = _file_url(job, cutout.name)
        except Exception as e:  # pragma: no cover
            logger.warning("sam3 cutout failed: %s", e)

        # 인페인팅 영역이 새 가구 마스크에서 빠졌는지(=구멍) 비율 측정
        if inpaint_mask_path is not None and inpaint_mask_path.exists():
            try:
                import cv2

                inp = cv2.imread(str(inpaint_mask_path), cv2.IMREAD_GRAYSCALE)
                fur = cv2.imread(str(sam3_mask), cv2.IMREAD_GRAYSCALE)
                if inp is not None and fur is not None:
                    if fur.shape != inp.shape:
                        fur = cv2.resize(fur, (inp.shape[1], inp.shape[0]))
                    ip = inp > 127
                    fr = fur > 127
                    if ip.sum() > 0:
                        hole = float((ip & ~fr).sum()) / float(ip.sum())
                        out["hole_ratio_in_inpaint_region"] = round(hole, 3)
                        out["hole_note"] = (
                            "인페인팅 영역 중 SAM3가 가구로 인식 못한 비율 "
                            "(높을수록 구멍 — 단, 가구 밖 오염물 포함 시 과대평가될 수 있음)"
                        )
            except Exception as e:  # pragma: no cover
                logger.warning("hole ratio calc failed: %s", e)
    return out


@router.post("/run")
async def run_inpaint_test(
    method: str = Form(...),
    image: UploadFile = File(...),
    mask: Optional[UploadFile] = File(None),
    furniture_type: str = Form(""),
    composite_blur: float = Form(1.5),
    composite_mode: str = Form("blur"),
    composite_dilate: int = Form(0),
    run_sam3: bool = Form(False),
    sam3_prompts: str = Form(""),
):
    """선택한 방식으로 인페인팅을 실행하고 결과 이미지 URL과 진단값을 반환한다."""
    method = method.strip().lower()
    if method not in _VALID_METHODS:
        raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
    if method in _NEEDS_MASK and mask is None:
        raise HTTPException(status_code=400, detail=f"'{method}' 방식은 마스크 이미지가 필요합니다.")

    job = uuid.uuid4().hex[:12]
    job_dir = _TEST_ROOT / job
    job_dir.mkdir(parents=True, exist_ok=True)

    image_path = job_dir / f"input{_suffix(image.filename)}"
    image_path.write_bytes(await image.read())

    mask_path = None
    if mask is not None:
        mask_path = job_dir / f"mask{_suffix(mask.filename)}"
        mask_path.write_bytes(await mask.read())

    output_path = job_dir / "result.png"

    try:
        if method == "lama":
            result = _service.inpaint_with_lama_local(
                image_path, mask_path, output_path, composite=False
            )
        elif method == "lama_composite":
            result = _service.inpaint_with_lama_local(
                image_path, mask_path, output_path, composite=True
            )
        elif method == "banana_e2e":
            result = _service.inpaint_with_banana_e2e(
                image_path, output_path, furniture_type=furniture_type
            )
        elif method == "banana_brushnet":
            result = _service.inpaint_with_banana(
                image_path, mask_path, output_path, furniture_type=furniture_type,
                composite_blur_radius=composite_blur,
                composite_mode=composite_mode,
                composite_dilate_px=composite_dilate,
            )
        elif method == "flux":
            result = _service.inpaint_with_flux(
                image_path, mask_path, output_path, furniture_type=furniture_type
            )
        else:  # pragma: no cover - guarded above
            raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Inpaint test failed (method=%s)", method)
        result = {"status": "failed", "method": method, "error": str(e), "warnings": []}

    response = {
        "job": job,
        "method": method,
        "status": result.get("status"),
        "warnings": result.get("warnings", []),
        "diagnostics": result.get("diagnostics", {}),
        "error": result.get("error"),
        "input_url": _file_url(job, image_path.name),
    }
    if mask_path is not None:
        response["mask_url"] = _file_url(job, mask_path.name)
    if result.get("status") == "done" and output_path.exists():
        response["result_url"] = _file_url(job, output_path.name)
        # banana_e2e는 native 해상도 결과도 함께 보존
        native = result.get("diagnostics", {}).get("native_output_file")
        if native and (job_dir / native).exists():
            response["native_result_url"] = _file_url(job, native)

        # banana_brushnet: 원본에 덮이는 인페인팅 '조각'(RGBA) 노출
        piece = result.get("diagnostics", {}).get("composite_piece_file")
        if piece and (job_dir / piece).exists():
            response["composite_piece_url"] = _file_url(job, piece)

        # 인페인팅 결과에 SAM3 재마스킹 검사 (선택)
        if run_sam3:
            prompts = [p.strip() for p in sam3_prompts.split(",") if p.strip()]
            try:
                response["sam3"] = _run_sam3_check(
                    job, job_dir, output_path, furniture_type, mask_path,
                    sam3_prompts=prompts,
                )
            except Exception as e:
                logger.exception("SAM3 re-mask check failed")
                response["sam3"] = {"status": "failed", "error": str(e)}

    status_code = 200 if result.get("status") == "done" else 500
    return JSONResponse(content=response, status_code=status_code)


@router.get("/file/{job}/{name}")
def serve_test_file(job: str, name: str):
    """테스트 입력/결과 이미지를 서빙한다."""
    safe_job = Path(job).name
    safe_name = Path(name).name
    file_path = _TEST_ROOT / safe_job / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))
