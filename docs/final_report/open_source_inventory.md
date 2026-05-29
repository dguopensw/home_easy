# 오픈소스 및 외부 서비스 목록

> 작성 기준: `backend/requirements.txt` 및 코드 분석 결과
> 라이선스가 requirements.txt나 코드에서 직접 확인되지 않은 항목은 "확인 필요"로 표시

---

## 표 1. 오픈소스 라이브러리 및 모델

| 분류 | 라이브러리/모델 | 버전 | 용도 | 라이선스 | 비고 |
|------|--------------|------|------|---------|------|
| 웹 프레임워크 | fastapi | requirements.txt 미지정 | 백엔드 API 서버 | 확인 필요 | |
| 웹 프레임워크 | uvicorn[standard] | requirements.txt 미지정 | ASGI 서버 | 확인 필요 | |
| ORM / DB | sqlalchemy[asyncio] | requirements.txt 미지정 | 비동기 DB ORM | 확인 필요 | |
| ORM / DB | asyncpg | requirements.txt 미지정 | PostgreSQL 비동기 드라이버 | 확인 필요 | |
| ORM / DB | alembic | requirements.txt 미지정 | DB 마이그레이션 | 확인 필요 | |
| 설정 | python-dotenv | requirements.txt 미지정 | 환경변수 관리 (.env 파일 로드) | 확인 필요 | |
| 설정 | pydantic-settings | requirements.txt 미지정 | Pydantic 기반 설정 관리 | 확인 필요 | |
| 통신 | sse-starlette | requirements.txt 미지정 | Server-Sent Events 지원 | 확인 필요 | |
| 통신 | httpx | requirements.txt 미지정 | 비동기 HTTP 클라이언트 | 확인 필요 | |
| AI / OpenAI SDK | openai | requirements.txt 미지정 | OpenAI API Python 클라이언트 | 확인 필요 | SDK 자체는 오픈소스, API 호출은 상용 |
| 스크래핑 | requests | requirements.txt 미지정 | HTTP 클라이언트 | 확인 필요 | |
| 스크래핑 | beautifulsoup4 | requirements.txt 미지정 | HTML 파싱 | 확인 필요 | |
| 이미지 처리 | Pillow | requirements.txt 미지정 | 이미지 처리 (리사이즈, 합성 등) | 확인 필요 | |
| 이미지 처리 | opencv-python | requirements.txt 미지정 | 컴퓨터 비전 (마스크 처리 등) | 확인 필요 | |
| 이미지 처리 | rembg | requirements.txt 미지정 | 배경 제거 | 확인 필요 | |
| 이미지 처리 | onnxruntime | requirements.txt 미지정 | ONNX 모델 추론 (rembg 등에서 사용) | 확인 필요 | |
| 세그멘테이션 | SAM3 (Segment Anything Model 3) | 확인 필요 | 가구 영역 세그멘테이션 | 확인 필요 | segmentation_module/segmentation.py에서 사용, 정확한 출처/버전 확인 필요 |
| 세그멘테이션 보조 | pycocotools | requirements.txt 미지정 | COCO 데이터셋 도구 | 확인 필요 | |
| ML 공통 | einops | requirements.txt 미지정 | 텐서 연산 유틸리티 | 확인 필요 | |
| ML 공통 | huggingface_hub | requirements.txt 미지정 | Hugging Face 모델 허브 접근 | 확인 필요 | |
| ML 공통 | iopath | requirements.txt 미지정 | 파일 I/O 유틸리티 | 확인 필요 | |
| ML 공통 | timm | requirements.txt 미지정 | PyTorch 이미지 모델 라이브러리 | 확인 필요 | |
| ML 공통 | ftfy | requirements.txt 미지정 | 텍스트 인코딩 정제 | 확인 필요 | |
| ML 공통 | regex | requirements.txt 미지정 | 정규표현식 확장 라이브러리 | 확인 필요 | |
| 인페인팅 (Flux) | diffusers | requirements.txt 미지정 | Hugging Face Diffusion 모델 프레임워크 | 확인 필요 | inpainting_flux.py에서 사용 |
| 인페인팅 (Flux) | transformers | requirements.txt 미지정 | Hugging Face Transformer 모델 프레임워크 | 확인 필요 | |
| 인페인팅 (Flux) | accelerate | requirements.txt 미지정 | 학습/추론 가속 | 확인 필요 | |
| 인페인팅 (Flux) | sentencepiece | requirements.txt 미지정 | 토크나이저 | 확인 필요 | |
| 인페인팅 (레거시) | simple-lama-inpainting | requirements.txt 미지정 | LaMa 인페인팅 | 확인 필요 | 코드상 잔존 (lama_inpaint_worker.py), 현재 파이프라인에서 미호출 |
| 인페인팅 모델 | black-forest-labs/FLUX.1-Fill-dev | 확인 필요 | Flux-Fill 인페인팅 모델 (Hugging Face) | 확인 필요 | inpainting_flux.py에서 로드 |

---

## 표 2. 외부 API 및 상용 서비스

| 서비스 | 용도 | 유형 | 환경변수 | 비고 |
|--------|------|------|---------|------|
| OpenAI API (GPT-4o Vision) | 가구 유형 분석, 이미지 선택, 장애물/오염물 분석, 치수 추정 | 상용 API | OPENAI_API_KEY | 다수 파이프라인 단계에서 사용 |
| TRELLIS 3D 생성 API | 이미지에서 GLB 3D 모델 생성 | 자체 운영 서버 (RunPod 기반) | TRELLIS_BASE_URL | POST /generate, GET /status/{job_id} |

---

## 표 3. 인프라 및 배포 도구

| 도구 | 용도 | 유형 | 비고 |
|------|------|------|------|
| RunPod | GPU 서버 호스팅 (백엔드 및 TRELLIS 서버) | 클라우드 GPU 서비스 (상용) | 환경변수: BACKEND_PUBLIC_URL |
| AWS S3 | GLB 파일 저장 및 배포 | 클라우드 스토리지 (상용) | TRELLIS 서버 측에서 업로드, 접근 권한 설정 확인 필요 |
| Docker | 컨테이너 기반 배포 | 컨테이너 플랫폼 | Dockerfile, docker-compose.yml 존재 |

---

## 참고 사항

- **OpenAI API, RunPod, AWS S3는 오픈소스가 아니므로 표 1에 포함하지 않았다.**
- `openai` Python SDK는 오픈소스 라이브러리이므로 표 1에 포함하였으나, 실제 API 호출은 상용 서비스(표 2)에 해당한다.
- 모든 라이브러리의 정확한 버전은 requirements.txt에 명시되어 있지 않으므로 (버전 고정 없음), 실제 설치 환경에서 확인이 필요하다.
- SAM3의 정확한 출처(GitHub 저장소, 논문)와 라이선스는 segmentation_module을 추가로 분석하여 확인해야 한다.
- LaMa 관련 코드(lama_inpaint_worker.py, simple-lama-inpainting)는 기존 실험 후보로 코드상 잔존하나, 현재 파이프라인에서 실제 호출되지 않는다.
