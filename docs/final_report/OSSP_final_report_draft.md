# 오픈소스 프로젝트 최종보고서

> 작성 기준일: 2026-05-22
> 프로젝트명: 집에 가구 쉽다 (Home Easy)
> 브랜치: feat/backend-migration

---

## 1. 프로젝트 개요

### 서비스명

**집에 가구 쉽다 (Home Easy)**

### 한 줄 소개

중고 가구 거래 게시글 URL을 입력하면, 크롤링 → SAM3 전처리 → 치수 추정 → TRELLIS 3D 생성까지 자동으로 수행하여 Unity에서 실제 스케일로 배치 가능한 GLB 파일을 생성하는 파이프라인 서비스.

### 핵심 키워드

`SAM3 세그멘테이션` · `TRELLIS 3D 생성` · `중고가구 치수 추정` · `Unity 스케일 배치`

### 프로젝트 배경

온라인 중고거래 시장이 빠르게 성장하면서, 가구 카테고리는 가장 활발히 거래되는 품목 중 하나가 되었다. 그러나 가구는 크기와 형태가 구매 결정에 직접적인 영향을 미치는 상품임에도 불구하고, 중고거래 플랫폼의 판매글은 여전히 2차원 사진 중심으로 구성된다. 구매자는 사진만 보고 가구의 실제 크기, 깊이, 형태를 직관적으로 파악해야 하는 어려움을 겪는다.

본 프로젝트는 이 문제를 기술적으로 해결하기 위해 시작되었다. AI 기반 이미지 전처리 파이프라인을 통해 중고거래 게시글의 가구 사진에서 3D 모델을 자동으로 생성하고, Unity 가상 공간에서 실제 스케일에 가깝게 배치하는 시스템을 구현함으로써, 가구 구매 전 공간 적합성 판단을 보조하는 것을 목표로 한다.

### 최종 결과물 정의

본 프로젝트의 **최종 결과물은 Unity 기반 GLB 배치**이다. 백엔드 파이프라인이 생성한 GLB 파일을 Unity에 import하여, 추정된 치수 정보를 바탕으로 실제 스케일에 가까운 가구 3D 모델을 가상 공간에 배치하는 것이 목표이다.

**HTML 보고서와 Unity 결과물의 역할 구분:**

| 구분 | 역할 | 성격 |
|------|------|------|
| HTML 보고서 (`OSSP_final_report.html`) | 제출용 최종보고서 문서 산출물 | 문서 |
| Unity GLB 배치 | 서비스 최종 결과물 | 시연 결과 |

본 HTML 파일은 서비스의 결과물이 아니며, OSSP 제출을 위한 보고서 문서 산출물이다. 서비스 결과물은 파이프라인이 생성한 GLB 파일을 Unity에서 배치한 시연 결과이다.

---

## 2. 개발동기 및 문제정의

### 중고 가구 거래에서 크기 판단의 어려움

국내 중고거래 시장에서 가구는 거래량이 많고 평균 거래 금액도 높은 카테고리 중 하나다. 소파, 침대, 책상, 옷장 같은 대형 가구는 구매 후 반품이나 교환이 매우 어렵고, 이사 시 처분도 쉽지 않기 때문에 구매 전 신중한 판단이 필요하다. 그러나 중고거래 플랫폼에서 가구를 볼 때 구매자가 얻을 수 있는 정보는 대부분 2~5장의 사진과 판매자가 적은 간략한 텍스트에 불과하다. 사진만으로 가구의 실제 크기를 정확하게 파악하는 것은 경험 많은 구매자에게도 쉽지 않은 일이며, 초보 구매자에게는 더욱 그렇다.

### 사진 기반 거래의 구조적 한계

중고거래 가구 사진에는 구조적인 한계가 있다. 판매자는 대부분 스마트폰으로 가구를 촬영하며, 배경이나 조명을 통제하지 않는 경우가 대부분이다. 이로 인해 가구 뒤에 다른 물건이 쌓여 있거나, 가구 위에 물건이 올려져 있거나, 가구의 일부가 프레임 밖으로 잘려나간 사진이 자주 올라온다. 단일 이미지에서는 깊이(depth) 정보가 손실되기 때문에, 배경과 가구의 거리 관계를 파악하기 어렵다. 결과적으로 구매자는 사진에 찍힌 가구가 실제로 얼마나 큰지, 내 방에 들어갈 수 있는지, 공간을 얼마나 차지하는지를 추측에 의존해야 한다.

### 판매글 치수 정보의 불규칙성과 부재 문제

가구 판매글의 또 다른 문제는 치수 정보의 불규칙성이다. 일부 판매자는 정확한 WxDxH 수치를 제공하지만, 많은 판매글에서 치수가 아예 없거나, "꽤 큰 편", "2인용 소파" 같은 모호한 표현만 사용된다. 치수가 있더라도 표기 방식이 제각각이어서 자동 파싱이 쉽지 않다. "120*60*75", "가로120 세로60 높이75", "W1200×D600×H750" 같은 다양한 형식을 모두 인식해야 하며, cm와 mm가 혼용되는 경우도 있다. 치수 정보가 없는 경우 구매자는 직접 판매자에게 문의해야 하는 번거로움이 있으며, 이는 거래 전환율 저하로 이어진다.

### 공간 적합성 판단 수단의 부족

가구를 실제로 구매하기 전에 내 공간에 맞는지 확인할 수 있는 수단이 매우 부족하다. 가구의 치수를 알고 있다 하더라도, 숫자만으로 공간 적합성을 직관적으로 판단하기는 어렵다. "너비 150cm짜리 소파"라고 해도 내 거실에 어떻게 놓일지, 다른 가구들과 어떻게 어우러질지 머릿속으로 그리는 것은 공간 지각 능력이 필요하다. 실제 공간에서 테이프를 바닥에 붙여 가구 크기를 시뮬레이션하는 방식도 있지만, 이는 번거롭고 높이나 깊이는 파악하기 어렵다. 3D 시각화가 이 문제를 해결할 수 있는 가장 직접적인 방법이지만, 기존 서비스들은 이를 중고 가구 거래에 적용하지 못하고 있다.

### 기존 중고거래 플랫폼의 한계

당근마켓, 중고나라 등 주요 중고거래 플랫폼은 가구 거래를 지원하지만 3D 시각화 기능을 제공하지 않는다. 이들 플랫폼의 핵심 기능은 거래 중개이며, 상품 정보의 정확성이나 풍부함을 위한 별도 기능에 투자하는 구조가 아니다. 가구 치수 입력을 강제하거나 표준화하는 기능도 없으며, 판매자 주도의 비정형 정보 입력에 의존한다. 결국 구매자는 플랫폼 자체에서 제공하는 부가 정보 없이, 판매자가 제공하는 사진과 텍스트만으로 구매를 결정해야 한다.

### 기존 3D 가구 서비스의 한계와 우리 접근법

IKEA Place, 오늘의집 AR 등 기존 3D 가구 배치 서비스는 사전 제작된 3D 자산(해당 브랜드의 제품 카탈로그)을 기반으로 작동한다. 이러한 서비스는 등록된 신제품에는 유효하지만, 임의의 중고 가구 사진에서 3D 모델을 자동으로 생성하는 기능을 제공하지 않는다. 중고 가구는 세상에 하나뿐인 현재 상태의 물건이므로, 그 물건의 3D 모델이 미리 존재하지 않는다.

본 프로젝트는 이 간극을 메우는 것을 목표로 한다. 중고거래 URL만 입력하면 크롤링 → SAM3 세그멘테이션 → 인페인팅 → 치수 추정 → TRELLIS 3D 생성까지 자동으로 수행하는 파이프라인을 구축하여, **등록된 3D 자산이 없는 개별 중고 상품에도 적용 가능한 3D 시각화 흐름**을 실현한다.

---

## 3. 요구사항 분석

본 프로젝트의 요구사항은 사용자 시나리오와 시스템 구현 가능성을 기반으로 기능 요구사항(FR)과 비기능 요구사항(NFR)으로 분류하였다. 각 요구사항은 코드에서 구현 상태를 직접 확인한 결과를 병기한다.

### 표 1. 기능 요구사항 (Functional Requirements)

| ID | 요구사항 | 설명 | 구현 상태 | 근거 파일 |
|----|---------|------|----------|----------|
| FR-1 | URL 입력 | 당근마켓 또는 중고나라 게시글 URL 입력 지원 | 구현 완료 | `routers/crawling.py` |
| FR-2 | 게시글 크롤링 | 제목, 설명, 가격, 이미지 URL 목록 자동 수집 | 구현 완료 | `services/crawling_service.py` |
| FR-3 | 이미지 선택 | 3D 생성에 적합한 이미지 AI 추천 및 사용자 선택 | 구현 완료 | `services/image_selector.py` |
| FR-4 | 가구 유형 분석 | 텍스트 및 GPT Vision 기반 가구 종류 판단 | 구현 완료 | `services/furniture_analysis_service.py` |
| FR-5 | 판매글 치수 파싱 | 판매글에서 WxDxH 등 다양한 패턴의 치수 자동 추출 | 구현 완료 | `services/crawling_service.py` |
| FR-6 | SAM3 마스킹 | 가구 영역을 SAM3로 세그멘테이션 및 마스크 정제 | 구현 완료 | `services/segmentation_service.py` |
| FR-7 | 누끼 생성 | 소프트 알파 마스크 적용 배경 제거 이미지 생성 | 구현 완료 | `services/pipeline_service.py` |
| FR-8 | 장애물·오염물 분석 | GPT Vision으로 가구 위·주변 방해 요소 감지 | 구현 완료 | `services/furniture_analysis_service.py` |
| FR-9 | 인페인팅 | 장애물·오염물 제거 및 경계 복원 처리 | 선택 예정 | `services/inpainting_service.py`, `inpainting_flux.py` |
| FR-10 | 치수 추정 | 판매글 치수 우선, 없으면 GPT Vision 추정 | 구현 완료 | `services/dimension_estimator.py` |
| FR-11 | TRELLIS 3D 생성 | GLB 모델 생성 요청 및 비동기 상태 조회 | 구현 완료 | `services/generation_service.py` |
| FR-12 | 결과 파일 저장 | job_id별 파이프라인 산출물 및 result.json 저장 | 구현 완료 | `backend/output/` 구조 |
| FR-13 | Unity GLB 배치 | GLB 파일을 Unity에서 치수 기반 스케일 보정 | 확인 필요 | 시연 수동 적용, 자동화 코드 미확인 |

### 표 2. 비기능 요구사항 (Non-Functional Requirements)

| ID | 요구사항 | 설명 | 구현 상태 | 비고 |
|----|---------|------|----------|------|
| NFR-1 | 중간 산출물 저장 | 각 파이프라인 단계 결과 이미지 저장으로 디버깅 가능성 확보 | 구현 완료 | `output/{job_id}/01~08` 파일 |
| NFR-2 | 민감정보 보호 | API 키, 실제 서버 URL 등 시크릿 값 환경변수로 분리 | 구현 완료 | `.env` 기반 환경변수 |
| NFR-3 | 결과 추적성 | job_id 기반 파이프라인 실행 결과 조회 가능 | 구현 완료 | `GET /api/gen/status/{job_id}` |
| NFR-4 | 확장성 | 플랫폼 크롤러 및 AI 모델 교체가 가능한 구조 | 부분 구현 | 서비스 클래스 분리, 일부 하드코딩 |
| NFR-5 | 재현성 | output 파일과 result.json으로 실행 결과 재확인 가능 | 구현 완료 | `result.json` 전체 상태 포함 |
| NFR-6 | 상태 가시성 | 임시 프론트엔드에서 파이프라인 단계별 상태 확인 | 구현 완료 | `backend/static/index.html` |

각 요구사항의 구현 상태는 코드 직접 확인 결과에 기반한다. FR-9(인페인팅)의 경우 코드 내 Flux-Fill 구현이 존재하나, nano-banana와의 최종 비교 실험이 완료되지 않아 "선택 예정"으로 분류한다. FR-13(Unity GLB 배치)는 수동 시연 과정에서 적용되나 자동화 코드가 확인되지 않아 "확인 필요"로 분류한다.

---

## 4. 기존 서비스 및 선행 사례 비교

### 비교 배경

본 장에서는 중고가구 거래 관련 서비스와 3D 가구 배치 서비스를 비교하여, 본 프로젝트가 해결하는 문제 영역을 명확히 한다. 기존 서비스들은 각자의 영역에서 유용하지만, 중고 가구 이미지에서 3D 모델을 자동 생성하는 기능은 아무도 제공하지 않는다는 점이 본 프로젝트의 출발점이다.

### 서비스 비교 표

| 구분 | 중고거래 지원 | 임의 상품 이미지 입력 | 3D 모델 자동 생성 | 실제 스케일 보정 | 공간 배치 시뮬레이션 | 주요 한계 |
|------|------------|------------------|----------------|--------------|-----------------|---------|
| 당근마켓 | O | X | X | X | X | 거래 중개 전용, 3D 기능 없음 |
| 중고나라 | O | X | X | X | X | 거래 중개 전용, 정형화 미지원 |
| IKEA Place | X (신제품) | X | X | O | O | 자사 등록 제품만 지원 |
| IKEA Kreativ | X (신제품) | X | X | O | O | 자사 등록 제품만 지원 |
| 오늘의집 AR | X (등록 제품) | X | X | O | O | 파트너사 제품만 지원 |
| **본 서비스** | **O** | **O** | **O** | **부분 지원** | **Unity 기준** | 단일 이미지 깊이 한계 |

### 핵심 차별점

기존 3D 가구 배치 서비스들은 공통적으로 **사전 제작된 3D 자산(CAD 모델 또는 포토그래메트리 스캔 결과)** 을 기반으로 작동한다. 이 방식은 정확한 3D 품질을 보장하지만, 카탈로그에 등록된 제품에만 적용 가능하며 임의의 중고 가구 이미지를 처리할 수 없다.

본 프로젝트는 이와 근본적으로 다른 접근법을 취한다. 중고거래 게시글 URL 하나를 입력하면, 크롤링 → SAM3 세그멘테이션 → 인페인팅 → TRELLIS 3D 생성까지 자동으로 처리된다. **등록된 3D 자산이 존재하지 않는 개별 중고 상품에도 적용 가능한 흐름**이 본 프로젝트의 핵심 차별점이다.

중고거래 플랫폼(당근마켓, 중고나라)과의 차이점은, 이 플랫폼들이 거래 중개에 초점을 맞추는 반면 본 프로젝트는 구매 결정 보조에 초점을 맞춘다는 것이다. 플랫폼 자체가 변화하기 어려운 구조적 한계를 감안할 때, 외부에서 URL을 입력받아 3D 시각화를 제공하는 방식이 현실적인 접근법이다.

---

## 5. 개발목표 및 범위

본 프로젝트의 목표는 기술 목표, 서비스 목표, 실험 목표, 최종 결과물 목표 네 가지로 분류된다. 각 목표는 코드에서 확인된 구현 상태와 함께 기술한다.

### 5-1. 기술 목표

기술 목표는 파이프라인의 각 단계를 실제로 구현하는 것이다. 크롤링 서비스, SAM3 기반 세그멘테이션, 치수 추정, TRELLIS 3D 생성 연동을 순차적으로 연결하는 FastAPI 기반 백엔드를 구현하는 것이 핵심이다. 단순한 API 연결이 아니라, 중고거래 이미지의 특수성(복잡한 배경, 장애물, 불완전한 정보)에 대응하는 전처리 파이프라인을 설계하는 것이 이 목표의 핵심이다.

### 5-2. 서비스 목표

서비스 목표는 사용자가 중고 가구 URL 하나를 입력했을 때 전체 흐름이 자동으로 처리되어 Unity에서 배치 가능한 GLB 파일을 얻을 수 있는 end-to-end 흐름을 구현하는 것이다. 이 목표는 파이프라인의 각 단계가 개별적으로 동작할 뿐 아니라, 단계 간 데이터가 정확히 전달되고 중간 산출물이 저장되는 재현 가능한 구조를 포함한다.

### 5-3. 실험 목표

실험 목표는 다양한 가구 유형과 촬영 조건에서 파이프라인의 성능과 한계를 파악하는 것이다. 소파, 의자, 책상, 침대, 옷장 등 가구 유형별로 마스킹 품질, 치수 추정 정확도, 3D 생성 성공률을 평가하고, 실패 케이스를 분류하여 개선 방향을 도출하는 것이 목표이다. 현재 실제 테스트 결과는 수집되지 않았으며, 실험 설계와 평가 지표는 13장에 별도로 기술한다.

### 5-4. 최종 결과물 목표

최종 결과물 목표는 Unity에서 실제 스케일에 가까운 가구 3D 모델 배치를 시연하는 것이다. TRELLIS가 생성한 GLB 파일을 Unity에 import하여, result.json의 치수 정보를 기반으로 스케일 보정을 적용하고, 가상 공간에서 가구가 어떻게 배치되는지 확인할 수 있는 시연 결과를 산출하는 것이 목표이다.

### 개발목표 현황 표

| 구분 | 목표 | 구현 상태 | 설명 |
|------|------|----------|------|
| 기술 | 중고거래 URL 기반 크롤링 | 구현 완료 | 당근마켓/중고나라 지원 |
| 기술 | SAM3 기반 가구 세그멘테이션 | 구현 완료 | 17단계 파이프라인 오케스트레이션 |
| 기술 | 판매글 치수 파싱 | 구현 완료 | 정규식 다중 패턴 지원 |
| 기술 | GPT Vision 치수 추정 | 구현 완료 | 판매글 치수 없을 때 폴백 |
| 기술 | 인페인팅 파이프라인 | 선택 예정 | Flux-Fill 코드 존재, nano-banana 검토 중 |
| 기술 | TRELLIS 3D 생성 연동 | 구현 완료 | RunPod 기반 비동기 연동 |
| 서비스 | End-to-end 파이프라인 | 구현 완료 | POST /api/process 단일 엔드포인트 |
| 서비스 | 중간 산출물 저장 | 구현 완료 | output/{job_id}/ 구조 |
| 실험 | 가구 유형별 테스트 | 미수집 | 실험 설계 완료, 실행 필요 |
| 결과물 | Unity GLB 배치 시연 | 확인 필요 | 수동 시연, 자동화 코드 미확인 |

---

## 6. 시스템 아키텍처

### 아키텍처 개요

전체 시스템은 9개 레이어로 구성된다. 사용자 입력에서 시작하여 크롤링, 이미지 분석, SAM3 전처리, 인페인팅, 치수 추정, TRELLIS 3D 생성, 결과 저장, Unity 시연으로 이어지는 순차적 파이프라인이다. 각 레이어는 역할이 명확히 분리된 서비스 클래스로 구현된다.

### 레이어별 역할

| 레이어 | 구성 요소 | 역할 |
|--------|---------|------|
| 사용자 입력 | `backend/static/index.html` | 중고거래 URL 입력, 이미지 선택, 결과 확인 |
| 크롤링 | `CrawlingService` | 게시글 제목/설명/가격/이미지 수집, 치수 정규식 파싱 |
| 이미지 분석 | `ImageSelectorService`, `FurnitureAnalysisService` | GPT Vision 기반 이미지 선택 및 가구 유형·장애물 분석 |
| SAM3 전처리 | `SegmentationService` | 가구 영역 마스킹, 마스크 정제, 누끼 생성 |
| 인페인팅 | `InpaintingService`, `InpaintingFluxService` | 장애물·오염물 제거, 경계 복원 (Flux-Fill 또는 nano-banana) |
| 치수 추정 | `DimensionEstimatorService` | listing_text 파싱 우선, 없으면 GPT Vision 추정 |
| TRELLIS 생성 | `GenerationService` | RunPod TRELLIS 서버에 GLB 생성 요청 및 상태 조회 |
| 결과 저장 | `backend/output/{job_id}/` | 중간 산출물 이미지 및 result.json 저장 |
| Unity 시연 | Unity + GLB + dimensions | 수동 import 및 스케일 보정 (자동화 향후 검토) |

### 시스템 아키텍처 다이어그램

```mermaid
flowchart LR
  U[사용자] --> F[임시 프론트\nindex.html]
  F -- POST /api/scrape --> C[CrawlingService\n크롤링 + 치수 파싱]
  F -- POST /api/process --> P[PipelineService\n오케스트레이터]
  P --> IS[ImageSelectorService\n이미지 선택]
  P --> FA[FurnitureAnalysisService\n가구 분석 + 장애물]
  P --> SEG[SegmentationService\nSAM3 마스킹]
  P --> INP[InpaintingService\nFlux/nano-banana 후보]
  P --> DIM[DimensionEstimatorService\n치수 추정]
  P --> GEN[GenerationService\nTRELLIS 요청]
  GEN -- POST /generate --> TRELLIS[TRELLIS 서버\nRunPod]
  TRELLIS -- GET /status/{job_id} --> GEN
  TRELLIS --> S3[AWS S3\nGLB 파일]
  S3 --> Unity[Unity\nGLB import + 스케일 보정]
  P --> OUT[output/{job_id}/\n결과 파일 저장]
```

### 파이프라인 오케스트레이션

`pipeline_service.py`의 `PipelineService`가 전체 파이프라인을 오케스트레이션한다. 17단계로 구성된 파이프라인은 단계별로 중간 산출물을 `output/{job_id}/` 에 저장하며, 최종 결과는 `result.json`에 통합된다. 파이프라인 버전은 `pipeline_version: "service_v3_sam3_only"`이며, SAM3 기반 마스킹이 핵심이다.

---

## 7. 사용자 흐름 및 유즈케이스

### 주요 유즈케이스

본 시스템의 사용자 흐름은 세 가지 주요 유즈케이스로 구성된다.

**UC-1: 중고 가구 3D 모델 생성 (정상 흐름)**
구매를 고려하는 사용자가 중고거래 게시글 URL을 입력하면, 시스템이 게시글을 크롤링하고 이미지를 제시한다. 사용자가 이미지를 선택(또는 AI 추천 이미지 수락)하면 전체 파이프라인이 실행된다. TRELLIS 3D 생성이 완료되면 GLB 파일을 Unity에 import하여 실제 스케일로 배치한다.

**UC-2: 치수 정보 보완 (치수 없는 게시글)**
판매글에 치수 정보가 없는 경우, 시스템이 GPT Vision을 통해 이미지에서 치수를 추정한다. 이때 `dimensions.source`는 `vision_estimate`가 되며, `final_decision.needs_user_confirmation`이 true로 설정된다. 사용자는 Unity에서 수동으로 스케일을 보정할 수 있다.

**UC-3: 장애물이 있는 가구 이미지 (인페인팅 필요)**
가구 위에 물건이 놓여 있거나 배경에 방해 요소가 있는 경우, 장애물 분석 후 인페인팅으로 제거 처리를 시도한다. 인페인팅 완료 후 SAM3를 재실행하여 06_generation_cutout.png를 생성하고, 이를 TRELLIS 입력으로 사용한다.

### 단계별 사용자 흐름

| 단계 | 사용자 행동 | 시스템 응답 | API |
|------|-----------|-----------|-----|
| 1 | URL 입력 | 게시글 크롤링 실행 | POST /api/scrape |
| 2 | - | 이미지 목록 + AI 추천 인덱스 반환 | ← 응답 |
| 3 | 이미지 선택 또는 AI 추천 수락 | 파이프라인 실행 시작 | POST /api/process |
| 4 | 대기 | SAM3 마스킹 → 분석 → 인페인팅 → 치수 추정 | 처리 중 |
| 5 | - | result.json + 파이프라인 중간 이미지 반환 | ← 응답 |
| 6 | 결과 확인 | TRELLIS 상태 polling | GET /api/gen/status/{job_id} |
| 7 | - | TRELLIS 완료 시 GLB URL 포함 result.json | ← 응답 |
| 8 | GLB 다운로드 후 Unity 적용 | (백엔드 관여 없음) | 수동 시연 |

### 예외 흐름

- **TRELLIS 서버 미설정:** `model_generation.status = "not_configured"`. 파이프라인 나머지 단계는 정상 완료되며, GLB 생성만 건너뜀.
- **치수 정보 없음:** `listing_dimensions = null`, `dimensions.source = "vision_estimate"`. 치수 신뢰도 low.
- **인페인팅 미적용 (장애물 없음):** Stage 13 건너뜀, 06_generation_cutout.png가 없으므로 TRELLIS는 03_final_cutout.png를 폴백으로 사용.

---

## 8. 백엔드 구현

### FastAPI 서버 설계 의도

백엔드는 FastAPI 프레임워크 기반으로 구성하였다. FastAPI를 선택한 이유는 Python 생태계의 AI/ML 라이브러리(SAM3, diffusers, transformers 등)와의 호환성이 높고, 비동기 처리와 타입 힌트 기반 자동 문서화를 동시에 지원하기 때문이다. 전체 파이프라인이 AI 모델 추론 과정을 포함하므로, 동기적으로 처리되는 `/api/process`는 요청당 상당한 처리 시간이 소요될 수 있다. 향후 비동기 처리로의 전환을 고려한 구조로 설계하였다.

라우터는 크롤링, 3D 생성, 파일 서빙의 세 가지 역할로 분리하여 관심사를 분리하였다. 각 서비스는 별도의 클래스로 구현하여 의존성 주입 및 교체가 용이하도록 하였다. 예를 들어, 인페인팅 서비스는 `InpaintingService`가 실제 엔진(Flux-Fill 또는 향후 nano-banana)을 추상화하고, `PipelineService`는 어떤 인페인팅 엔진이 사용되는지 알 필요 없이 동일한 인터페이스로 호출한다.

### 디렉토리 구조

```
backend/
├── main.py                          # FastAPI 앱 진입점, 라우터 등록
├── core.py                          # OUTPUT_DIR 등 공통 상수
├── database.py                      # SQLAlchemy async 설정
├── routers/
│   ├── crawling.py                  # POST /api/scrape
│   ├── generation.py                # POST /api/process, GET /api/gen/status/{job_id}
│   └── furniture.py                 # 파일 서빙, 결과 조회
├── services/
│   ├── pipeline_service.py          # 17단계 파이프라인 오케스트레이션 (핵심)
│   ├── crawling_service.py          # 크롤링 + 치수 정규식 파싱
│   ├── furniture_analysis_service.py  # 가구 유형, 장애물/오염물 분석
│   ├── segmentation_service.py      # SAM3 마스킹
│   ├── inpainting_service.py        # 인페인팅 라우팅 (Flux/nano-banana 추상화)
│   ├── inpainting_flux.py           # FLUX.1-Fill-dev 인페인팅 구현
│   ├── dimension_estimator.py       # 치수 추정
│   ├── image_selector.py            # GPT Vision 기반 이미지 선택
│   └── generation_service.py        # TRELLIS 연동
├── segmentation_module/
│   └── segmentation.py              # SAM3 세그멘테이션 모듈
├── static/
│   └── index.html                   # 임시 프론트엔드
└── output/                          # 파이프라인 결과물 (job_id별)
```

### 주요 API 명세

| 기능 | Method | URL | 입력 | 출력 | 상태 |
|------|--------|-----|------|------|------|
| 헬스 체크 | GET | `/health` | - | `{"status": "ok"}` | 완료 |
| API 헬스 체크 | GET | `/api/health` | - | `{"status": "ok", "pipeline": "service_v3_sam3_only"}` | 완료 |
| 정적 UI | GET | `/` | - | index.html | 완료 |
| 게시글 스크래핑 | POST | `/api/scrape` | `{"url": "..."}` | 제목/설명/가격/이미지 목록/AI 추천 인덱스/치수 | 완료 |
| 전체 파이프라인 | POST | `/api/process` | `{"url": "...", "selected_image_index": 0}` | result.json + 파이프라인 결과 | 완료 |
| 생성 상태 조회 | GET | `/api/gen/status/{job_id}` | job_id | result.json + 최신 TRELLIS 상태 | 완료 |
| 파이프라인 시작(레거시) | POST | `/api/gen/start` | `url` (query) | `{"job_id": "...", "status": "completed"}` | 완료 |
| 출력 파일 서빙 | GET | `/api/furniture/output/{job_id}/{filename}` | job_id, filename | 이미지 파일 | 완료 |
| 작업 결과 조회 | GET | `/api/furniture/job/{job_id}` | job_id | result.json | 완료 |

### output 폴더 구조

`backend/output/{job_id}/` 하위 파일 구성:

| 파일명 | 생성 조건 | 설명 |
|--------|----------|------|
| `01_original.jpg` | 항상 | 선택된 원본 이미지 |
| `02_measurement.png` | 항상 | SAM3 마스크 + 원본 합성 (치수 추정 보조용) |
| `03_final_cutout.png` | 항상 | 소프트 알파 마스크 적용 최종 누끼 |
| `04_raw_mask.png` | 항상 | SAM3 원시 마스크 |
| `04_final_mask.png` | 항상 | 정제된 최종 마스크 |
| `04_final_alpha.png` | 항상 | 소프트 알파 마스크 |
| `05_obstacle_mask.png` | 조건부 | 장애물 마스크 (장애물 있을 때) |
| `05_obstacle_removed.png` | 조건부 | 인페인팅 결과 (장애물 있을 때) |
| `06_generation_cutout.png` | 조건부 | 인페인팅 후 SAM3 재실행 컷아웃 (TRELLIS 우선 입력) |
| `06_generation_mask.png` | 조건부 | 생성용 마스크 |
| `06_generation_raw_mask.png` | 조건부 | 생성용 원시 마스크 |
| `06_generation_alpha_mask.png` | 조건부 | 생성용 알파 마스크 |
| `07_contaminant_mask.png` | 조건부 | 오염물 마스크 |
| `07_union_mask.png` | 조건부 | 장애물+오염물 합집합 마스크 |
| `08_boundary_completion_mask.png` | 조건부 | 경계 복원 마스크 |
| `08_boundary_completed.png` | 조건부 | 경계 복원 인페인팅 결과 |
| `result.json` | 항상 | 전체 파이프라인 결과 JSON |

### result.json 주요 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `job_id` | string | 작업 식별자 (8자리 hex) |
| `pipeline_version` | string | `"service_v3_sam3_only"` |
| `furniture` | object | type, source (combined/listing_text/vision), confidence |
| `listing_dimensions` | object or null | width_cm, depth_cm, height_cm, source, pattern |
| `masking_strategy` | object | primary, family, risk_level 등 SAM3 전략 |
| `obstacle_analysis` | object | has_obstacles, items 등 |
| `generation_contaminant_analysis` | object | has_contaminants, items 등 |
| `dimensions` | object | width_cm, depth_cm, height_cm, source, confidence |
| `cutout_quality` | string | ok / warning / error / unknown |
| `generation_cutout_quality` | string | ok / warning / error / unknown |
| `final_decision` | object | can_generate_3d, dimension_status, warnings, needs_user_confirmation |
| `model_generation` | object | status, trellis_job_id, input_file, glb_url |
| `files` | object | 각 단계별 출력 파일 경로 |

### Public URL 자동 계산 방식

TRELLIS 서버가 백엔드의 이미지를 원격에서 가져올 수 있도록, 공개 접근 가능한 이미지 URL이 자동으로 계산된다. `BACKEND_PUBLIC_URL` 환경변수 또는 요청 헤더(`x-forwarded-proto`, `x-forwarded-host`)를 기반으로 다음 형식의 URL을 구성한다:

```
{BACKEND_PUBLIC_URL}/api/furniture/output/{job_id}/{trellis_input_file}
```

이 방식으로 RunPod의 백엔드 서버와 TRELLIS 서버가 별도 주소에서 운영되더라도, TRELLIS가 입력 이미지를 정상적으로 다운로드할 수 있다.

---

## 9. 임시 프론트엔드 구현

### 임시 프론트엔드의 목적과 위치

`backend/static/index.html`은 파이프라인 검증용 임시 프론트엔드이다. 최종 서비스 UI를 목표로 하지 않으며, FastAPI의 정적 파일 서빙을 통해 백엔드와 동일한 프로세스에서 서빙된다. RunPod GPU 서버에서 백엔드가 실행될 때, 공개 URL에 접속하면 이 페이지가 표시된다.

임시 프론트의 존재 이유는 두 가지다. 첫째, 백엔드 API를 시각적으로 테스트할 수 있는 인터페이스가 필요했다. 둘째, 파이프라인의 중간 결과 이미지(01~08 파일)를 단계별로 확인하려면 UI가 필요했다. 별도의 프론트엔드 서버를 세우는 대신, 백엔드가 정적 파일을 직접 서빙하는 방식을 택하여 배포 복잡도를 줄였다.

### 사용자 흐름 (임시 프론트)

1. **URL 입력:** 당근마켓 또는 중고나라 게시글 URL을 입력한다.
2. **게시글 정보 표시:** `/api/scrape` 응답으로 이미지 목록, 제목, 설명, 가격이 표시된다. AI 추천 이미지 인덱스도 함께 표시된다.
3. **이미지 선택:** 사용자가 이미지를 직접 선택하거나 AI 추천 이미지를 수락한다.
4. **처리 요청 및 대기:** `/api/process` 호출 후 파이프라인이 실행된다. 처리 중 상태가 표시된다.
5. **결과 확인:** 파이프라인 완료 후 각 단계별 이미지(원본, 마스크, 누끼, 컷아웃 등)와 분석 결과(가구 유형, 치수, 장애물 여부 등)가 표시된다.
6. **TRELLIS polling:** `/api/gen/status/{job_id}`를 주기적으로 호출하여 3D 생성 상태를 확인한다. 완료 시 GLB 다운로드 링크가 표시된다.

---

## 10. AI 및 전처리 파이프라인

본 장은 보고서의 핵심 파트로, 가장 상세히 기술한다. 3D 생성 품질은 생성 모델 자체뿐 아니라 입력 이미지의 품질에 크게 영향을 받는다. 중고거래 이미지는 배경이 복잡하고, 가구 위에 물체가 놓여 있거나, 일부 구조가 잘려 있는 경우가 많다. 따라서 본 프로젝트는 TRELLIS 3D 생성 모델에 들어가기 전 이미지를 정제하는 SAM3 중심 전처리 파이프라인을 구축하는 데 초점을 두었다.

### SAM3(Segment Anything Model 3) 선택 이유

SAM3를 세그멘테이션 엔진으로 선택한 이유는 명확하다. 중고거래 이미지의 가장 큰 특징은 배경이 통제되지 않는다는 점이다. 일반적인 배경 제거 도구(rembg 등)는 전경과 배경을 이진으로 분리하는 방식으로 작동하며, 복잡한 배경이나 가구와 비슷한 색상의 물체가 있을 때 정확도가 떨어진다.

SAM3는 점(point) 또는 박스(box) 형태의 프롬프트를 입력받아 특정 영역을 타겟으로 마스킹할 수 있다. 이를 통해 배경과 색상이 유사한 환경에서도 가구 영역을 명확하게 지정할 수 있다. 또한 마스크 정제 알고리즘과 결합하여 소프트 알파 마스크를 생성함으로써, 3D 생성 입력 이미지의 경계 품질을 높일 수 있다. 파이프라인에서 SAM3는 Stage 6과 Stage 14 두 번 호출되는데, 첫 번째는 기본 마스킹이고 두 번째는 인페인팅 후 재실행을 통한 더 깨끗한 생성용 컷아웃을 만들기 위한 것이다.

### 파이프라인 17단계 구성

| 단계 | 모델/방식 | 입력 | 출력 | 목적 | 구현 상태 |
|------|---------|------|------|------|----------|
| Stage 1 | 플랫폼 URL 판별 | 중고거래 URL | 플랫폼 유형 | 크롤링 방식 결정 | 완료 |
| Stage 2 | 게시글 크롤링 | URL | 제목/설명/가격/이미지 URL 목록 | 분석 대상 확보 | 완료 |
| Stage 3 | 이미지 선택 | 이미지 후보 목록 | 선택 이미지 1개 | 3D 생성에 적합한 입력 선정 | 완료 |
| Stage 4 | 가구 유형 분석 | 판매글 텍스트, 이미지 | furniture.type | SAM3 마스킹 전략 결정 | 완료 |
| Stage 5 | 판매글 치수 파싱 | description | listing_dimensions | Unity 스케일 기준 확보 | 완료 |
| Stage 6 | SAM3 마스킹 | 01_original.jpg | 04_raw_mask.png | 가구 영역 추출 | 완료 |
| Stage 7 | 마스크 정제 | raw mask | final mask, alpha | 누끼 경계 품질 개선 | 완료 |
| Stage 8 | 측정용 이미지 생성 | 원본, 마스크 | 02_measurement.png | GPT Vision 치수 추정 보조 | 완료 |
| Stage 9 | 최종 누끼 생성 | 원본, alpha | 03_final_cutout.png | 기본 3D 생성 입력 확보 | 완료 |
| Stage 10 | 장애물 분석 | 원본, 누끼 | obstacle_analysis | 가림 요소 유무 판단 | 완료 |
| Stage 11 | 오염물 분석 | 원본, 누끼 | contaminant_analysis | 3D 생성 방해 요소 판단 | 완료 |
| Stage 12 | 장애물/오염물 마스크 생성 | 분석 결과 | 05_mask, 07_mask | 인페인팅 대상 지정 | 완료 |
| Stage 13 | 인페인팅 | Flux-Fill 또는 nano-banana 후보 | 05_removed, 08_completed | 생성 방해 요소 제거 | 선택 예정 |
| Stage 14 | 생성용 SAM3 재실행 | 인페인팅 결과 | 06_generation_cutout.png | TRELLIS 입력 최적화 | 완료 |
| Stage 15 | 치수 추정 | listing_dimensions 또는 GPT Vision | dimensions | Unity 스케일 보정값 확보 | 완료 |
| Stage 16 | 최종 판단 | 품질 지표, 치수, cutout 상태 | final_decision | 3D 생성 가능 여부 판단 | 완료 |
| Stage 17 | TRELLIS 요청 | 06 또는 03 컷아웃 | model_generation (glb_url) | GLB 생성 요청 | 완료 |

### Stage 1-5: 크롤링, 이미지 선택, 가구 분석

CrawlingService는 입력 URL을 분석하여 당근마켓과 중고나라를 구분하고, 각 플랫폼에 맞는 크롤링 로직을 실행한다. 크롤링 결과에는 제목, 설명, 가격, 이미지 URL 목록이 포함되며, 설명 텍스트에서 정규식 파서가 다양한 치수 패턴을 추출하는 Stage 5도 이 단계에서 함께 실행된다.

ImageSelectorService는 GPT-4o Vision을 활용하여 이미지 후보들 중 3D 생성에 가장 적합한 이미지를 선택한다. 선택 기준은 가구 전체가 잘 보이는지, 배경이 비교적 단순한지, 가구가 이미지 중앙에 위치하는지 등이다. FurnitureAnalysisService는 판매글 텍스트와 이미지를 종합하여 가구 유형(소파, 의자, 책상, 침대 등)을 판단하고, 이 정보를 SAM3 마스킹 전략 결정에 활용한다.

### Stage 6-9: SAM3 마스킹 및 누끼 생성

SegmentationService가 SAM3를 사용하여 가구 영역의 raw mask를 생성한다. 가구 유형 정보를 기반으로 마스킹 전략이 결정되며, 점 프롬프트 또는 박스 프롬프트 방식으로 SAM3를 실행한다. raw mask는 형태학적 연산과 alpha matting 기법으로 정제되어 final mask와 소프트 알파 마스크가 생성된다.

소프트 알파 마스크를 원본 이미지에 적용하면 03_final_cutout.png가 생성된다. 이 파일은 배경이 투명하고 가구만 남은 상태로, TRELLIS의 폴백 입력 이미지이다. 동시에 02_measurement.png도 생성되는데, 이는 SAM3 마스크 윤곽선을 원본 위에 합성한 이미지로 GPT Vision이 가구 영역을 인식하는 것을 보조한다.

### Stage 10-13: 장애물/오염물 분석 및 인페인팅

GPT-4o Vision을 활용하여 가구 주변의 장애물(obstacle: 가구 위에 놓인 물체)과 오염물(contaminant: 3D 생성에 직접 방해가 되는 배경 요소)을 분석한다. 장애물이 감지되면 GPT Vision이 장애물의 위치를 바탕으로 마스크를 생성하고, 인페인팅 서비스가 해당 영역을 채운다.

인페인팅 엔진은 현재 코드상 Flux-Fill(`inpainting_flux.py`)이 실제 호출되고 있다. Flux-Fill은 `black-forest-labs/FLUX.1-Fill-dev` 모델을 사용하며 diffusers 라이브러리로 구동된다. nano-banana 방식은 별도 검토 중이며 코드에서 확인되지 않는다. LaMa(`simple-lama-inpainting`)는 기존 실험 후보 코드로 잔존하나, 현재 파이프라인에서 실제 호출되지 않는다. 최종적으로 Flux-Fill과 nano-banana 중 하나를 선택하는 비교 실험이 필요하다.

### Stage 14-17: 생성용 컷아웃, 치수 확정, TRELLIS 요청

인페인팅 완료 후 SAM3를 재실행하여 06_generation_cutout.png를 생성한다. 이 파일은 인페인팅으로 장애물이 제거된 이미지에서 가구 영역만 추출한 것으로, TRELLIS의 우선 입력 이미지이다. 06이 없거나 품질이 낮으면 03_final_cutout.png를 폴백으로 사용한다.

치수 추정은 listing_dimensions(판매글 파싱 결과)를 우선 사용하고, 없으면 DimensionEstimatorService가 GPT Vision으로 추정한다. 최종 판단(final_decision)에서 품질 지표, 치수 상태, 경고 사항이 종합되어 3D 생성 가능 여부가 결정된다. 모든 조건이 충족되면 GenerationService가 TRELLIS 서버에 POST /generate를 요청한다.

---

## 11. 치수측정 및 Unity 스케일 보정

### 치수측정이 필요한 이유: Unity 스케일 기준

TRELLIS가 생성하는 GLB 파일은 3D 형태를 복원하지만, 절대적인 실세계 스케일 정보를 포함하지 않는다. Unity에서 GLB를 import하면 임의의 단위 크기로 표시된다. 예를 들어, 2m짜리 소파가 Unity에서 0.2 단위로 표시될 수도 있고, 20 단위로 표시될 수도 있다. 실제 공간 배치 시뮬레이션을 위해서는 GLB의 스케일을 실제 가구 치수에 맞게 보정해야 한다.

본 프로젝트의 치수측정 파이프라인은 이 보정값을 확보하기 위한 것이다. 단일 이미지에서 모든 치수를 정확히 복원하는 것이 목표가 아니라, Unity에서 스케일 보정에 필요한 대표 치수(주로 너비 또는 높이)를 최대한 정확히 확보하는 것이 목적이다.

### 판매글 치수 파싱: 정규식 다중 패턴

CrawlingService의 치수 파서는 판매글 텍스트에서 다양한 표기 방식의 치수를 추출한다. 지원하는 주요 패턴은 다음과 같다:

- **WxDxH 형식:** "120x60x75", "120*60*75", "120X60X75"
- **한글 레이블 형식:** "가로120 세로60 높이75", "폭:120 깊이:60 높이:75"
- **IKEA 스타일:** "W1200×D600×H750" (mm 단위로 cm 변환)
- **단위 명시:** "120cm × 60cm × 75cm"
- **부분 치수:** 너비만 있거나 높이만 있는 경우도 추출

정규식 파싱이 실패하거나 치수 중 일부만 추출된 경우, `listing_dimensions.source`에 추출 성공한 항목만 기록하고, 나머지는 GPT Vision으로 보완한다.

### GPT Vision 기반 치수 추정 방식과 한계

판매글에 치수 정보가 없거나 파싱에 실패한 경우, DimensionEstimatorService가 GPT-4o Vision을 활용하여 이미지에서 치수를 추정한다. 이때 02_measurement.png(SAM3 마스크 경계선과 원본 이미지를 합성한 이미지)를 입력으로 사용한다. GPT Vision은 가구의 시각적 비율과 가구 유형별 일반적인 크기 범위(예: 2인용 소파는 보통 너비 160~200cm)를 참고하여 추정값을 생성한다.

이 방식의 한계는 명확하다. 단일 이미지에서는 깊이(depth) 정보가 없어 앞뒤 치수 추정이 어렵고, 절대 스케일을 결정할 기준점이 없다. 사람이나 다른 물체가 같이 찍혀 있지 않으면 가구의 실제 크기를 판단하기 어렵다. 따라서 GPT Vision 추정은 판매글 치수가 없을 때의 폴백으로만 사용하며, 이 경우 `dimensions.confidence`는 `low`가 된다.

### 02_measurement.png의 역할

02_measurement.png는 SAM3가 감지한 가구 영역의 윤곽선을 원본 이미지 위에 표시한 이미지다. 이 이미지를 GPT Vision에 입력함으로써 두 가지 효과를 얻는다. 첫째, GPT Vision이 가구 영역의 정확한 경계를 파악하여 가구 내부의 다른 물체(예: 소파 위 쿠션)를 제외한 가구 본체의 크기만 추정할 수 있다. 둘째, 마스크 경계선이 이미지 전체 크기 대비 가구 비율을 시각적으로 강조하여 GPT Vision의 비율 판단을 돕는다.

### 치수 확보 방식 비교 표

| 치수 확보 방식 | 입력 | 신뢰도 | 한계 | 사용 우선순위 |
|--------------|------|--------|------|-------------|
| 판매글 명시 치수 파싱 | 제목/설명 텍스트 | high | 표기 방식 불규칙 | 1순위 |
| GPT Vision 추정 | 02_measurement.png | low | 절대 스케일 한계 | 2순위 (폴백) |
| 사용자 직접 입력 | UI 입력값 | high | 추가 입력 필요 | 향후 개선 |
| Unity 수동 보정 | GLB import 후 시각 판단 | 주관적 | 정확도 불일치 가능 | 현재 시연 방식 |

### Unity 스케일 보정 방식

시연 단계에서 Unity에 GLB를 import한 후, result.json의 `dimensions` 필드를 참조하여 스케일 보정을 수동으로 적용한다. Unity의 1 unit = 1 meter 기준으로, 가구 너비(width_cm)를 Unity 스케일로 변환하여 적용한다. 자동화된 Unity 연동 코드는 현재 백엔드에서 확인되지 않으며, 향후 UnityWebRequest 또는 GLB 메타데이터 임베딩 방식으로 자동화할 수 있다.

---

## 12. TRELLIS 3D 생성 및 Unity 결과물

### TRELLIS 연동 구조

TRELLIS 3D 생성 서버는 RunPod GPU 서버에서 별도로 운영된다. 백엔드와 TRELLIS 서버 간 통신은 REST API 방식이며, 두 개의 환경변수로 연결 정보를 관리한다:

- `TRELLIS_BASE_URL`: TRELLIS 서버 기본 URL (실제 값 환경변수로 분리)
- `BACKEND_PUBLIC_URL`: 백엔드 공개 URL (TRELLIS가 이미지를 다운로드할 때 사용)

이 구조를 통해 백엔드와 TRELLIS 서버가 서로 다른 RunPod 인스턴스에서 실행되더라도, TRELLIS가 입력 이미지를 백엔드 공개 URL로 가져와 처리할 수 있다.

### TRELLIS 입력 이미지 선택 기준

TRELLIS에 제출하는 입력 이미지는 두 가지 후보가 있으며, 우선순위가 정해져 있다:

- **우선 입력:** `06_generation_cutout.png` — 인페인팅 후 SAM3를 재실행하여 생성한 컷아웃. 장애물이 제거되고 배경이 깨끗한 상태의 가구 이미지이므로 3D 생성 품질이 높을 것으로 기대된다.
- **폴백 입력:** `03_final_cutout.png` — 기본 누끼. 장애물 분석에서 장애물이 없었거나, 인페인팅이 미적용된 경우 사용한다. 인페인팅 없이 생성된 컷아웃이므로 배경 요소가 남아 있을 수 있다.

06을 우선으로 하는 이유는 인페인팅을 거친 이미지가 가구 본체만 깨끗하게 분리되어 있어 TRELLIS의 3D 복원 품질을 높이기 때문이다. TRELLIS는 단일 이미지에서 3D 구조를 추론하므로, 배경 노이즈가 적을수록 더 정확한 3D 형상을 생성할 수 있다.

### TRELLIS 연동 단계 표

| 단계 | 처리 주체 | 입력 | API | 출력 |
|------|---------|------|-----|------|
| 1. 입력 이미지 선택 | PipelineService | 06 또는 03 cutout | - | image_url (백엔드 공개 URL) |
| 2. 생성 요청 | GenerationService | job_id, image_url | POST {TRELLIS_BASE_URL}/generate | trellis_job_id |
| 3. 상태 조회 | GenerationService | trellis_job_id | GET {TRELLIS_BASE_URL}/status/{id} | processing / completed / error |
| 4. GLB URL 수신 | GenerationService | completed 응답 | - | S3 GLB URL |
| 5. result.json 저장 | PipelineService | glb_url | - | model_generation.glb_url 업데이트 |
| 6. Unity 적용 | 사용자 (수동) | glb_url + dimensions | - | Unity 배치 결과 |

### Unity 적용 현황

현재 Unity 연동은 시연 단계에서 수동으로 이루어진다. 사용자가 `model_generation.glb_url`에서 GLB 파일을 다운로드한 후, Unity 에디터에 직접 import하고, result.json의 `dimensions` 값을 참조하여 Transform 컴포넌트의 Scale을 수동으로 조정한다.

자동화된 Unity 연동 코드(`unity-ar/` 디렉토리 등)는 현재 백엔드 레포에서 확인되지 않는다. 향후 자동화 방향으로는 Unity의 GLB Loader 스크립트에서 백엔드 API로 result.json을 가져와 자동으로 스케일을 적용하는 방식이 검토될 수 있다.

> [여기에 Unity 배치 결과 캡처 삽입: GLB import 후 스케일 보정 적용 화면]

---

## 13. 실험 설계 및 평가 지표

### 실험 설계 배경

현재 `backend/output/` 폴더에는 실제 파이프라인 실행 결과가 존재하지 않는다. 따라서 본 장에서는 실제 결과를 제시하는 대신, 향후 실험을 위한 테스트 케이스 계획, 평가 지표, 판정 기준, 실험 실행 절차를 자세히 기술한다. 실험 실행 후 14장의 실험 결과 및 해석 장을 채우는 것이 목표이다.

### 테스트 케이스 계획

| 케이스 ID | 가구 유형 | 촬영 조건 | 치수 정보 | 예상 어려움 |
|---------|---------|---------|---------|-----------|
| TC-01 | 소파 (2인용) | 배경 복잡, 쿠션 위에 있음 | 판매글 치수 있음 | 쿠션 장애물, 소프트 소재 마스킹 |
| TC-02 | 의자 (다리 있음) | 배경 단순 | 판매글 치수 있음 | 얇은 다리 마스크 누락 |
| TC-03 | 책상 | 배경 복잡, 위에 물건 있음 | 치수 없음 | 장애물 인페인팅 필요, 치수 추정 |
| TC-04 | 침대 프레임 | 이미지 일부 잘림 | 판매글 치수 있음 | 프레임 밖 잘림으로 3D 왜곡 |
| TC-05 | 옷장 | 배경 비교적 단순 | 치수 없음 | 깊이 추정 어려움 |
| TC-06 | 소파 (1인용) | 배경과 색상 유사 | 판매글 치수 있음 | 배경-가구 경계 혼동 |
| TC-07 | 의자 (패브릭) | 배경 단순 | 치수 없음 | 패브릭 소재 3D 품질 |
| TC-08 | 책상 (L자형) | 배경 복잡 | 판매글 치수 있음 | 복잡한 형태 마스킹 |
| TC-09 | 서랍장 | 배경 단순 | 치수 없음 | 직육면체 형태 (3D 최적) |
| TC-10 | 소파 (코너) | 배경 복잡, 이미지 여러 장 | 판매글 치수 있음 | 복잡한 형태, 이미지 선택 중요 |

### 평가 지표 정의

**지표 1. 마스킹 품질 (Masking Quality)**

- **정의:** SAM3가 생성한 마스크가 가구 영역을 얼마나 정확하게 포함하는지
- **측정 방법:** 주관적 5점 척도 (1: 심각한 오류, 5: 완벽한 마스킹)
  - 5점: 가구 전체가 마스크에 포함, 배경 포함 없음
  - 4점: 가구 대부분 포함, 미세한 경계 오류
  - 3점: 가구 일부 누락 또는 배경 일부 포함, 허용 수준
  - 2점: 가구 상당 부분 누락 또는 배경 대거 포함
  - 1점: 마스킹 실패
- **목표:** TC 전체 평균 3점 이상

**지표 2. 치수 오차 비율 (Dimension Error Rate)**

- **정의:** 추정 치수와 실제 치수의 상대적 오차
- **측정 방법:** `|추정 치수 - 실제 치수| / 실제 치수 × 100%`
- **실제 치수 확보 방법:** TC 실행 전 줄자로 직접 측정
- **목표:** 판매글 치수 파싱 시 5% 이내, GPT Vision 추정 시 20% 이내
- **평가 항목:** 너비(width), 깊이(depth), 높이(height) 각각

**지표 3. 3D 생성 성공률 (3D Generation Success Rate)**

- **정의:** TRELLIS 서버가 GLB를 성공적으로 생성한 비율
- **측정 방법:** `model_generation.status == "completed"` 케이스 수 / 전체 케이스 수
- **목표:** 70% 이상

**지표 4. Unity 배치 적합성 (Unity Placement Suitability)**

- **정의:** 생성된 GLB를 Unity에 import하여 스케일 보정 후 시각적으로 자연스러운지 주관적 평가
- **측정 방법:** 5점 척도 (1: 완전히 부적합, 5: 실제 가구와 유사한 스케일/형태)
- **목표:** TC 전체 평균 3점 이상

### 성공/부분성공/실패 판정 기준 표

| 판정 | 마스킹 품질 | 치수 오차 | 3D 생성 | Unity 배치 |
|------|-----------|---------|--------|-----------|
| 성공 | 4~5점 | 5% 이내 (판매글) 또는 20% 이내 (Vision) | completed | 4~5점 |
| 부분성공 | 3점 | 5~15% (판매글) 또는 20~35% (Vision) | completed | 3점 |
| 부분성공 | 3점 이상 | 목표 내 | completed | 2점 (형태 OK, 스케일 문제) |
| 부분성공 | 3점 이상 | 목표 내 | completed | 3점 이상 |
| 실패 | 1~2점 | - | - | - |
| 실패 | - | - | failed/error | - |
| 실패 | - | 35% 초과 | completed | 1~2점 |

### 테스트 실행 절차

1. **환경 준비:** 백엔드 서버 실행 (RunPod 또는 로컬), TRELLIS 서버 연결 확인
2. **실제 치수 측정:** TC에 사용할 실제 가구 10개의 너비/깊이/높이를 줄자로 직접 측정하여 기록
3. **URL 수집:** 당근마켓/중고나라에서 TC 조건에 맞는 실제 게시글 URL 10개 수집
4. **파이프라인 실행:** 각 URL에 대해 POST /api/process 실행, output/{job_id}/ 결과 저장
5. **중간 결과 검수:** 01~08 파이프라인 이미지 확인, 마스킹 품질 평가
6. **치수 오차 계산:** result.json의 dimensions 값과 실제 측정값 비교
7. **GLB Unity 검수:** 생성된 GLB를 Unity에 import하여 스케일 보정 후 시각 평가
8. **결과 기록:** 14장 실험 결과 표 채우기

---

## 14. 실험 결과 및 해석

> **주의:** 현재 `backend/output/` 폴더에 실제 파이프라인 실행 결과가 존재하지 않는다. 아래 표는 구조를 유지하되, 실제 데이터가 없는 항목은 "테스트 미수집"으로 표시한다. 실제 실험 실행 후 이 장을 채워야 한다.

### 실험 결과 표

| TC ID | 가구 유형 | 마스킹 품질 | 치수 오차 | 3D 생성 | Unity 배치 | 판정 | 주요 문제 |
|-------|---------|-----------|---------|--------|-----------|-----|---------|
| TC-01 | 소파 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | - | - |
| TC-02 | 의자 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | - | - |
| TC-03 | 책상 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | - | - |
| TC-04 | 침대 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | - | - |
| TC-05 | 옷장 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | 테스트 미수집 | - | - |

> [여기에 실제 파이프라인 실행 결과 이미지 삽입: 원본 → SAM3 마스크 → 누끼 → 생성용 컷아웃 → GLB 결과]

### 예상 성공 유형 및 조건

실제 결과가 없는 상태에서, 파이프라인 구조 분석을 통해 다음과 같은 유형에서 성공 가능성이 높다고 예측한다.

- **단순 배경 + 판매글 치수 명시:** SAM3 마스크가 깨끗하게 추출되고, 판매글 치수 파싱이 성공하는 경우. 책상, 서랍장 등 직육면체에 가까운 형태의 가구에서 3D 생성 품질도 높을 것으로 예상.
- **가구 중앙 배치 + 전체 프레임 내 포함:** 이미지 내 가구 전체가 프레임 안에 있고 중앙에 배치된 경우.

### 예상 부분성공 유형 및 조건

- **장애물 있으나 인페인팅 성공:** 가구 위 물체가 있어도 인페인팅으로 제거 성공 시. 단, 인페인팅 결과가 가구 원래 구조를 일부 변형시킬 수 있다.
- **치수 정보 없어 GPT Vision 추정:** 치수 신뢰도가 낮아 Unity 스케일 보정 시 수동 조정이 필요한 경우.
- **복잡한 형태의 가구:** 소파, 패브릭 의자 등 유기적 형태의 가구에서 3D 생성은 성공하나 Unity 배치 품질이 낮은 경우.

### 예상 실패 유형 목록

| 실패 원인 | 단계 | 현상 |
|---------|------|------|
| 배경-가구 색상 유사 | Stage 6 (SAM3) | raw mask가 배경 영역 포함 |
| 가구 일부 프레임 밖 잘림 | Stage 6, 17 | 3D 생성 결과 구조 왜곡 |
| 얇은 다리 마스크 누락 | Stage 6, 7 | 의자/책상 다리가 마스크에서 누락 |
| 인페인팅 후 원본 구조 변형 | Stage 13 | 가구 비율 또는 형태 왜곡 |
| GPT Vision 치수 추정 오차 | Stage 15 | 절대 스케일 오류, Unity 스케일 불일치 |
| TRELLIS 서버 오류 | Stage 17 | `model_generation.status = "failed"` |
| S3 접근 권한 문제 | Stage 17 | GLB URL 접근 불가 |
| Unity 텍스처/축 방향 문제 | Unity 적용 | import 후 텍스처 깨짐 또는 좌표축 뒤집힘 |

---

## 15. 오픈소스 활용

본 장은 OSSP 보고서의 핵심 장으로, 프로젝트에서 활용한 오픈소스 라이브러리/모델, 외부 상용 API, 인프라 서비스를 명확히 분류하여 기술한다. OpenAI API, RunPod, AWS S3는 오픈소스가 아닌 상용 서비스이므로 별도 표로 분리한다.

### 표 1. 오픈소스 라이브러리 및 모델

| 분류 | 라이브러리/모델 | 용도 | 라이선스 |
|------|--------------|------|---------|
| 웹 프레임워크 | fastapi | 백엔드 API 서버 | MIT |
| 웹 프레임워크 | uvicorn[standard] | ASGI 서버 | BSD |
| ORM / DB | sqlalchemy[asyncio] | 비동기 DB ORM | MIT |
| ORM / DB | asyncpg | PostgreSQL 비동기 드라이버 | Apache 2.0 |
| ORM / DB | alembic | DB 마이그레이션 | MIT |
| 설정 관리 | python-dotenv | 환경변수 관리 | BSD |
| 설정 관리 | pydantic-settings | 설정 관리 | MIT |
| HTTP 통신 | sse-starlette | Server-Sent Events 지원 | 확인 필요 |
| HTTP 통신 | httpx | 비동기 HTTP 클라이언트 | BSD |
| 스크래핑 | requests | HTTP 클라이언트 | Apache 2.0 |
| 스크래핑 | beautifulsoup4 | HTML 파싱 | MIT |
| 이미지 처리 | Pillow | 이미지 처리 | HPND (Open) |
| 이미지 처리 | opencv-python | 컴퓨터 비전 | Apache 2.0 |
| 이미지 처리 | rembg | 배경 제거 | MIT |
| 이미지 처리 | onnxruntime | ONNX 모델 추론 | MIT |
| 세그멘테이션 | SAM3 (Segment Anything Model) | 가구 영역 세그멘테이션 | Apache 2.0 (출처 확인 필요) |
| 세그멘테이션 보조 | pycocotools | COCO 데이터셋 도구 | BSD |
| ML 공통 | einops | 텐서 연산 유틸리티 | MIT |
| ML 공통 | huggingface_hub | Hugging Face 모델 허브 | Apache 2.0 |
| ML 공통 | timm | 이미지 모델 라이브러리 | Apache 2.0 |
| ML 공통 | ftfy | 텍스트 정제 | MIT |
| 인페인팅 (Flux) | diffusers | Diffusion 모델 프레임워크 | Apache 2.0 |
| 인페인팅 (Flux) | transformers | Transformer 모델 프레임워크 | Apache 2.0 |
| 인페인팅 (Flux) | accelerate | 학습/추론 가속 | Apache 2.0 |
| 인페인팅 모델 | FLUX.1-Fill-dev (black-forest-labs) | Flux-Fill 인페인팅 모델 | FLUX.1 License (확인 필요) |
| 인페인팅 (레거시) | simple-lama-inpainting | LaMa 인페인팅 (코드상 잔존, 파이프라인 미호출) | 확인 필요 |
| Python SDK | openai (Python SDK) | OpenAI API 클라이언트 라이브러리 | MIT |
| 컨테이너 | Docker | 컨테이너화 배포 | Apache 2.0 |

### 표 2. 외부 API 및 상용 서비스

| 서비스 | 용도 | 유형 | 환경변수 |
|--------|------|------|---------|
| OpenAI API (GPT-4o Vision) | 가구 분석, 이미지 선택, 장애물/오염물 분석, 치수 추정 | 상용 API | `OPENAI_API_KEY` |
| TRELLIS 3D 생성 API | GLB 3D 모델 생성 (RunPod 기반 별도 서버) | 상용 GPU 서비스 | `TRELLIS_BASE_URL` |

### 표 3. 인프라 및 배포 도구

| 도구 | 용도 | 유형 | 비고 |
|------|------|------|------|
| RunPod | GPU 서버 호스팅 (백엔드 + TRELLIS 별도) | 클라우드 GPU 서비스 | 상용 서비스 |
| AWS S3 | TRELLIS가 생성한 GLB 파일 저장 | 클라우드 스토리지 | TRELLIS 서버 측 설정 |
| Docker | 컨테이너 기반 배포 | 컨테이너 플랫폼 | `Dockerfile`, `docker-compose.yml` 확인됨 |

---

## 16. 기대효과 및 활용방안

### 사용자 구매 결정 보조 측면

중고 가구 구매자는 가구의 3D 모델을 통해 2차원 사진으로는 파악하기 어려운 가구의 입체적 형태와 크기를 확인할 수 있다. 특히 Unity에서 치수 기반 스케일 보정이 적용된 3D 모델은, 가구가 실제 방 공간에서 어떻게 보일지에 대한 직관적인 판단을 돕는다. 판매글 치수가 있는 경우에는 실제 스케일에 가까운 배치 시뮬레이션이 가능하며, 이를 통해 "이 소파가 내 거실에 들어갈 수 있는가"라는 구체적인 질문에 대한 시각적 근거를 제공한다.

본 서비스는 구매 결정을 완전히 자동화하거나 대체하는 것이 아니라, 구매 전 판단을 보조하는 도구임을 명확히 한다. 치수 추정의 오차 가능성, 단일 이미지의 한계, 가구 상태 정보의 부재 등 여전히 구매자의 판단이 필요한 요소가 많다.

### 중고거래 신뢰도 개선 측면

사진만으로는 파악하기 어려운 가구의 구조와 크기 정보를 3D 시각화로 보완하면, 구매자와 판매자 간의 정보 비대칭이 줄어들 수 있다. 치수 정보가 불완전한 판매글에서도 AI 기반 추정으로 대략적인 크기 정보를 제공하여, 구매자가 판매자에게 치수를 직접 문의해야 하는 번거로움을 줄일 수 있다. 중고거래에서 "생각보다 컸다" 또는 "생각보다 작았다"와 같은 문제를 줄이는 데 기여할 수 있다.

### 기술적 확장 가능성

본 프로젝트에서 구현한 SAM3 기반 전처리 파이프라인은 중고거래 이미지의 복잡한 배경과 장애물을 처리하는 범용 이미지 정제 파이프라인으로 확장될 수 있다. 가구 외에도 의류, 전자제품, 소형 가전 등 다양한 카테고리의 중고거래 이미지에 동일한 파이프라인을 적용할 수 있다. 크롤링 모듈은 당근마켓과 중고나라 외에도 추가 플랫폼을 지원하도록 확장 가능하다.

### 인테리어 서비스 연계 가능성

중고 가구뿐 아니라 일반 가구 이미지에서도 동일한 파이프라인으로 3D 모델을 생성할 수 있으므로, 인테리어 시뮬레이션 서비스와의 연계 가능성이 있다. 사용자가 직접 촬영한 기존 가구 사진을 입력하여 3D 모델을 생성하고, 새로운 가구와 함께 배치 시뮬레이션을 수행하는 방향으로 확장될 수 있다.

### 기대효과 요약

| 영역 | 기대효과 |
|------|---------|
| 사용자 경험 | 중고 가구 구매 전 3D 시각화로 공간 적합성 판단 보조 |
| 거래 신뢰성 | 치수 정보 AI 자동 보완으로 정보 비대칭 감소 |
| 기술 | SAM3 전처리 + TRELLIS 3D 생성 end-to-end 파이프라인 구현 |
| 확장성 | 가구 외 카테고리 및 추가 플랫폼으로 확장 가능한 구조 |
| 연계 | 인테리어 시뮬레이션 서비스 연계 기반 제공 |

---

## 17. 한계 및 개선방향

### 치수 관련 한계와 개선방향

단일 이미지에서 정확한 3차원 치수를 복원하는 것은 원리적으로 제한된다. 깊이 정보가 없는 2D 사진에서는 앞뒤(depth) 치수를 정확히 파악할 수 없으며, 배율 기준이 없으면 절대 크기도 알 수 없다. 판매글에 치수 정보가 있는 경우에는 이 문제를 우회할 수 있지만, 치수 정보가 없는 경우 GPT Vision 추정은 가구 유형 기반 평균값에 의존하므로 정확도가 낮다.

개선 방향으로는 다중 이미지 입력 지원(여러 각도의 사진에서 깊이 정보를 보완), 사용자 치수 입력 UI 제공, 또는 판매자에게 치수 입력을 유도하는 방식이 있다.

### 마스킹 및 전처리 한계와 개선방향

SAM3 마스킹은 배경과 가구의 색상이 유사한 경우, 또는 가구의 다리나 팔걸이 같이 세밀한 부분에서 마스크 누락이 발생할 수 있다. 가구 일부가 이미지 프레임 밖으로 잘린 경우에는 잘린 부분이 3D 생성 결과에 구조적 왜곡을 유발한다.

개선 방향으로는 더 정밀한 마스크 정제 알고리즘 적용, 이미지 선택 단계에서 프레임 잘림 케이스 사전 감지 및 경고, 사용자 마스크 수동 수정 UI 제공이 있다.

### 인페인팅 한계와 개선방향

현재 Flux-Fill이 파이프라인에서 실제 호출되고 있으나, nano-banana와의 비교 실험이 완료되지 않았다. 인페인팅 결과가 가구의 원래 비율이나 디테일을 변형시킬 수 있으며, 특히 장애물과 가구 본체가 겹치는 영역에서 부자연스러운 결과가 나올 수 있다.

개선 방향으로는 Flux-Fill과 nano-banana 후보를 TC 케이스들에 동일하게 적용하여 비교 평가한 후 최종 선택, 인페인팅 대상 마스크의 정확도 향상이 있다.

### 3D 생성 및 Unity 한계와 개선방향

TRELLIS가 생성한 GLB 파일은 단일 이미지 기반이므로, 카메라에 보이지 않는 측면이나 뒷면 구조가 추정으로 채워진다. 텍스처 품질도 원본 이미지 해상도와 조명에 의존한다. Unity 연동이 현재 수동이므로, 스케일 보정 값을 정확히 적용하려면 사용자의 Unity 사용 지식이 필요하다.

개선 방향으로는 Unity 스크립트에서 result.json을 자동으로 읽어 스케일을 적용하는 자동화, GLB 메타데이터에 치수 정보 임베딩 방식이 있다.

### 시스템 구조 한계와 개선방향

`/api/process`가 동기적으로 처리되어 복잡한 이미지의 경우 응답 시간이 길어진다. S3 접근 권한 설정에 따라 GLB URL 접근이 차단될 수 있다. TRELLIS 서버가 미설정이거나 오류 시 3D 생성 단계만 건너뛰는 부분 완료 처리가 가능하나, 이에 대한 사용자 안내가 필요하다.

개선 방향으로는 비동기 파이프라인 처리로 전환, TRELLIS 서버 상태 모니터링 및 재시도 로직, S3 접근 권한 자동 검증이 있다.

### 한계-개선방향 요약 표

| 한계 영역 | 구체적 한계 | 개선 방향 | 우선순위 |
|---------|----------|----------|---------|
| 치수 | 단일 이미지 깊이 한계 | 다중 이미지 입력, 사용자 치수 확인 UI | 중간 |
| 마스킹 | 얇은 다리 누락, 배경 혼동 | 마스크 정제 알고리즘 개선 | 높음 |
| 인페인팅 | 가구 구조 변형 가능 | Flux vs nano-banana 비교 실험 후 선택 | 높음 |
| 3D 생성 | 보이지 않는 면 추정 | - (TRELLIS 모델 한계, 개선 어려움) | 낮음 |
| Unity 연동 | 수동 적용 | Unity 스크립트 자동화 | 중간 |
| 시스템 | 동기 처리로 응답 지연 | 비동기 파이프라인 전환 | 중간 |

---

## 18. 참고문헌 및 첨부

> 주의: 아래 목록 중 구체적 논문 URL이나 정확한 버전이 확인되지 않은 항목은 "추가 확인 필요"로 표시한다. URL 없이 임의로 생성하지 않는다.

| 항목 | 출처 | 접근 경로 | 비고 |
|------|------|---------|------|
| Segment Anything Model (SAM) | Meta AI Research | 추가 확인 필요 | SAM3 구체적 버전/출처 확인 필요 |
| TRELLIS (3D 생성 모델) | 추가 확인 필요 | 추가 확인 필요 | 사용 버전 및 논문 출처 확인 필요 |
| FLUX.1-Fill-dev | Black Forest Labs (Hugging Face) | huggingface.co/black-forest-labs/FLUX.1-Fill-dev | 라이선스 확인 필요 |
| LaMa (Resolution-robust Large Mask Inpainting) | 추가 확인 필요 | 추가 확인 필요 | 기존 실험 후보, 코드상 잔존 |
| GPT-4o Vision | OpenAI | platform.openai.com | 상용 API |
| FastAPI | Sebastián Ramírez | fastapi.tiangolo.com | MIT License |
| diffusers | Hugging Face | huggingface.co/docs/diffusers | Apache 2.0 |
| transformers | Hugging Face | huggingface.co/docs/transformers | Apache 2.0 |
| SAM 원논문 | Kirillov et al. (2023) | 추가 확인 필요 | "Segment Anything", Meta AI Research |

### 첨부 파일 목록

| 파일 | 상태 | 설명 |
|------|------|------|
| `docs/final_report/OSSP_final_report.html` | 있음 | 브라우저용 HTML 최종보고서 (문서 산출물) |
| `docs/final_report/repo_analysis_summary.md` | 있음 | 레포지토리 분석 결과 요약 |
| `docs/final_report/open_source_inventory.md` | 있음 | 오픈소스/외부API/인프라 분리 목록 |
| `docs/final_report/assets_checklist.md` | 있음 | 필요 이미지/캡처 자료 체크리스트 |
| `docs/final_report/report_gap_analysis.md` | 있음 | 보고서 결함 진단 및 보강 방향 |
| `docs/final_report/revision_summary.md` | 있음 | 검수 결과 요약 |
| `backend/output/{job_id}/` | 테스트 미수집 | 파이프라인 실행 결과 (실제 실행 필요) |
| Unity 배치 결과 캡처 | 미수집 | GLB import 후 스케일 보정 적용 화면 |
