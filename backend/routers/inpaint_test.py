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

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from core import OUTPUT_DIR
from services.inpainting_service import InpaintingService

logger = logging.getLogger(__name__)

router = APIRouter()
_service = InpaintingService()
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


@router.post("/run")
async def run_inpaint_test(
    method: str = Form(...),
    image: UploadFile = File(...),
    mask: UploadFile | None = File(None),
    furniture_type: str = Form(""),
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
                image_path, mask_path, output_path, furniture_type=furniture_type
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
