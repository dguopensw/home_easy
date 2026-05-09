# 집에 가구 쉽다 (Home Easy)

중고 가구 게시글 URL을 입력하면 AI가 3D 모델을 생성하고, AR로 내 방에 배치해볼 수 있는 모바일 PWA 서비스

---

## 프로젝트 구조

```
home_easy/
├── frontend/      # React PWA (Vite + TypeScript + Tailwind CSS v4)
├── backend/       # FastAPI (Python)
├── ai-pipeline/   # AI 파이프라인 (RunPod Serverless)
└── unity-ar/      # Unity WebGL AR 씬
```

---

## 브랜치 전략

> 직접 `main`에 push하지 않습니다. Issue → 브랜치 → PR 흐름으로 작업하세요.

```
main                    # 최종 배포용 브랜치 (직접 push 금지)
└── develop             # 통합 개발 브랜치 (기능 완성 후 여기로 합침)
    ├── feature/홈페이지
    ├── feature/ar-연동
    ├── feature/백엔드-api
    └── ...
```

### 작업 흐름 (Issue → PR)

#### 1단계: Issue 생성

GitHub 레포 → **Issues** 탭 → **New issue**

- 제목 예시: `AR 바닥 인식 기능 구현`, `URL 입력 페이지 UI 수정`
- 담당자(Assignees)에 본인 지정
- 적절한 Label 선택 (`feature`, `fix`, `ui` 등)

#### 2단계: Issue에서 브랜치 생성

Issue 페이지 오른쪽 → **Development** → **Create a branch**

- 브랜치 이름 예시: `feature/ar-연동`, `feature/preview-ui`
- **Change branch source** 클릭 후 `develop`으로 변경 후 생성

생성된 브랜치를 로컬에 받기:

```bash
git fetch origin
git switch feature/ar-연동
```

#### 3단계: 작업 후 커밋 & push

```bash
git add .
git commit -m "feat: AR 바닥 인식 기능 구현"
git push origin feature/ar-연동
```

#### 4단계: Pull Request 생성

GitHub 레포 → **Pull requests** → **New pull request**

- **base**: `develop` ← **compare**: `feature/ar-연동`
- 제목과 설명 작성, 연결된 Issue 번호 언급 (`closes #이슈번호`)
- 팀원 리뷰 요청 후 Merge

---

## 커밋 메시지 규칙

형식: `태그: 작업 내용`

| 태그 | 언제 쓰나요? | 예시 |
|------|------------|------|
| `feat` | 새로운 기능 추가 | `feat: AR 가구 배치 기능 구현` |
| `fix` | 버그 수정 | `fix: 모델 로딩 안 되는 오류 수정` |
| `ui` | UI/스타일 변경 | `ui: 홈 화면 버튼 디자인 수정` |
| `refactor` | 기능 변화 없이 코드 정리 | `refactor: ARPage 컴포넌트 분리` |
| `docs` | 문서 수정 | `docs: README 브랜치 설명 추가` |
| `chore` | 설정, 패키지 등 기타 | `chore: tailwind 패키지 업데이트` |

### 커밋 예시

```bash
# ✅ 좋은 예시
git commit -m "feat: 로딩 페이지 3D 큐브 애니메이션 추가"
git commit -m "fix: URL 입력 후 빈 화면 뜨는 문제 수정"
git commit -m "ui: 결과 페이지 버튼 간격 조정"

# ❌ 나쁜 예시
git commit -m "수정"
git commit -m "ㅇㅇ"
git commit -m "작업함"
```

---

## 개발 환경 시작하기

### Frontend

```bash
cd frontend
pnpm install    # 처음 한 번만
pnpm run dev    # 개발 서버 실행 → http://localhost:5173
```

> 자세한 내용은 `frontend/GUIDE.md` 참고

---

## GitHub 처음 쓰는 분을 위한 기본 명령어

```bash
# 현재 상태 확인
git status

# 변경된 파일 스테이징
git add .                # 전체
git add 파일명           # 특정 파일만

# 커밋
git commit -m "feat: 기능 설명"

# push (원격 저장소에 올리기)
git push origin 브랜치명

# pull (원격 저장소에서 최신 내용 가져오기)
git pull origin 브랜치명

# 브랜치 목록 확인
git branch

# 브랜치 이동
git switch 브랜치명

# 새 브랜치 만들면서 이동
git switch -c 새브랜치명
```

### 매일 작업 시작 전 루틴

```bash
git switch feature/내브랜치     # 내 브랜치로 이동
git pull origin develop          # develop 최신 내용 받기
```
