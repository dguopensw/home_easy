"""jobs 테이블 정의 — 처리가 완료된 결과만 저장."""

from datetime import datetime

from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.sql import func

from database import Base


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)          # UUID, 백엔드가 생성
    source_url = Column(String, nullable=False)         # 사용자가 입력한 원본 게시글 URL
    dimensions = Column(JSON, nullable=True)            # {"w": 80, "h": 60, "d": 40} (단위: cm)
    glb_url = Column(String, nullable=True)             # S3에 업로드된 3D 모델 파일 URL
    created_at = Column(DateTime(timezone=True), server_default=func.now())
