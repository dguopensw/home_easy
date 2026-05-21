"""nanobanana_ratio_project의 app 모듈(_core)을 초기화하고 공유 경로를 설정합니다."""
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
    os.environ.get("SEGMENTATION_PROJECT_DIR", _PROJECT_ROOT / "nanobanana_ratio_project")
).expanduser()

sys.path.insert(0, str(SEGMENTATION_PROJECT_DIR))

import app as _core  # noqa: E402
_core.load_runtime_environment()

OUTPUT_DIR = _BACKEND_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# dahoo_fri/lama_inpaint_worker.py 경로 (LaMa subprocess 워커)
LAMA_WORKER_PATH = _PROJECT_ROOT / "dahoo_fri" / "lama_inpaint_worker.py"
