"""FastAPI 앱 진입점 — 서버 시작 시 DB 테이블 자동 생성."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import generation, crawling, furniture


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="집에 가구 쉽다 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generation.router, prefix="/furniture/gen", tags=["generation"])
app.include_router(crawling.router, prefix="/furniture/crawl", tags=["crawling"])
app.include_router(furniture.router, prefix="/furniture", tags=["furniture"])


@app.get("/health")
async def health():
    return {"status": "ok"}
