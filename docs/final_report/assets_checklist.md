# 자료 체크리스트

## 필요한 이미지 및 캡처 목록

| 장 번호 | 필요한 자료 | 파일 후보 | 상태 | 비고 |
|---------|-----------|---------|------|------|
| 3 | 시스템 아키텍처 그림 | 직접 제작 필요 | TODO | 사용자 --> 프론트 --> FastAPI --> 크롤링 --> SAM3 --> TRELLIS --> Unity 흐름 |
| 3 | 사용자 흐름도 | 직접 제작 필요 | TODO | URL 입력부터 Unity 배치까지 단계별 흐름 |
| 3 | 원본→SAM3 마스크→누끼→컷아웃→GLB 비교 | output/{job_id} | TODO | 실제 결과 필요 |
| 3 | Unity 배치 결과 캡처 | Unity 프로젝트 | TODO | unity-ar/ 디렉토리 확인 필요 |
| 4 | 백엔드 폴더 구조 캡처 | repo tree | TODO | backend/ 디렉토리 트리 |
| 5 | 임시 프론트 URL 입력 화면 | backend/static/index.html 실행 화면 | TODO | RunPod 서버 실행 후 캡처 |
| 6 | 01_original.jpg | output/{job_id}/01_original.jpg | TODO | 실제 결과 없음 |
| 6 | 04_raw_mask.png | output/{job_id}/04_raw_mask.png | TODO | 실제 결과 없음 |
| 6 | 04_final_mask.png | output/{job_id}/04_final_mask.png | TODO | 실제 결과 없음 |
| 6 | 03_final_cutout.png | output/{job_id}/03_final_cutout.png | TODO | 실제 결과 없음 |
| 6 | 06_generation_cutout.png | output/{job_id}/06_generation_cutout.png | TODO | 실제 결과 없음 |
| 6 | 05_obstacle_removed.png | output/{job_id}/05_obstacle_removed.png | TODO | 인페인팅 사용 시만 |
| 7 | 치수 추정 결과 캡처 | result.json dimensions 필드 | TODO | 실제 결과 없음 |
| 8 | TRELLIS GLB URL 결과 | result.json model_generation 필드 | TODO | 실제 결과 없음 |
| 8 | Unity 배치 결과 캡처 | Unity 프로젝트 | TODO | unity-ar/ 디렉토리 확인 필요 |
| 9 | 성공 사례 비교 이미지 | output 비교 | TODO | 실제 결과 없음 |
| 9 | 실패 사례 비교 이미지 | output 비교 | TODO | 실제 결과 없음 |
