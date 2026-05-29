"""공유 경로 및 _core 초기화.

SEGMENTATION_PROJECT_DIR은 SAM3 segmentation 모듈(nanobanana_ratio_project 등)의
위치를 가리킵니다. sys.path에 추가해 app_core 내부의 `from segmentation import ...`가
동작하도록 합니다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_BACKEND_DIR / ".env")
        load_dotenv()
    except Exception:
        pass


_load_dotenv()

SEGMENTATION_PROJECT_DIR = Path(
    os.environ.get("SEGMENTATION_PROJECT_DIR", _BACKEND_DIR / "segmentation_module")
).expanduser()

# SAM3 segmentation 모듈을 import 가능하게 경로 추가
sys.path.insert(0, str(SEGMENTATION_PROJECT_DIR))

import app_core as _core  # noqa: E402
_core.load_runtime_environment()

OUTPUT_DIR = _BACKEND_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# LaMa subprocess 워커 경로
LAMA_WORKER_PATH = _BACKEND_DIR / "lama_inpaint_worker.py"
