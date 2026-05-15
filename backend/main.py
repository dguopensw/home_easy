from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from models import job  # noqa: F401 — Base.metadata에 테이블 등록
from routers import generation, crawling, furniture


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="집에 가구 쉽다 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generation.router, prefix="/furniture", tags=["generation"])
app.include_router(crawling.router, prefix="/furniture", tags=["crawling"])
app.include_router(furniture.router, prefix="/furniture", tags=["furniture"])


@app.get("/health")
async def health():
    return {"status": "ok"}
