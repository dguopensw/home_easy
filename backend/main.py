from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from database import engine, Base
from models import job  # noqa: F401 — Base.metadata에 테이블 등록
from routers import generation, crawling, furniture

_BACKEND_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _BACKEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="집에 가구 쉽다 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (테스트 UI)
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# 라우터 등록
app.include_router(crawling.router, prefix="/api", tags=["crawling"])
app.include_router(generation.router, prefix="/api", tags=["generation"])
app.include_router(furniture.router, prefix="/api/furniture", tags=["furniture"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    return {"status": "ok", "framework": "fastapi", "pipeline": "service_v3_sam3_only"}


@app.get("/")
def index():
    html_path = _STATIC_DIR / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return HTMLResponse(
        "<h1>집에 가구 쉽다 API</h1>"
        "<p><a href='/static/index.html'>테스트 UI</a> | "
        "<a href='/docs'>API 문서</a></p>",
        status_code=200,
    )
