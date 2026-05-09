# Unit 1 Frontend — NFR Requirements Plan
# 집에 가구 쉽다 (Easy Furniture Fit)

---

## 생성 대상 아티팩트

- [x] `nfr-requirements/nfr-requirements.md`
- [x] `nfr-requirements/tech-stack-decisions.md`

---

## 질문

### Question 1
PWA 오프라인 지원이 필요한가요? (Service Worker 캐싱)

A) 오프라인 지원 없음 — 인터넷 연결 필수, Service Worker 미사용 (MVP에 적합)
B) 앱 셸만 캐싱 — 껍데기(HTML/CSS/JS)만 캐싱, 데이터는 항상 온라인 필요
C) Other (please describe after [Answer]: tag below)

[Answer]:A

---

### Question 2
지원 브라우저 범위를 선택해주세요.

A) 모바일 Chrome + Safari 만 — iOS/Android 실제 사용 환경 집중
B) 모바일 + 데스크톱 Chrome/Safari — 더 넓은 범위
C) Other (please describe after [Answer]: tag below)

[Answer]:A

---

### Question 3
프론트엔드 테스트 전략을 선택해주세요.

A) 테스트 없음 — MVP 속도 우선, 수동 테스트만
B) 핵심 비즈니스 로직만 단위 테스트 — URL 검사, SSE 처리 등 (Vitest)
C) Other (please describe after [Answer]: tag below)

[Answer]:A
