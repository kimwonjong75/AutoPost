> 복잡한 변경 시 RULES.md를 먼저 읽을 것

## RULES.md 참조 트리거
아래 상황에서 반드시 RULES.md를 먼저 읽을 것:
- 새 파일 생성 또는 기존 파일 삭제
- 2개 이상 파일에 걸친 수정
- DB 모델(models.py) 변경
- AI 엔진 연동 코드(content_generator.py, image_generator.py) 수정
- Naver 발행 로직(blog_publisher.py) 수정
- 상태 관리(session_state, SQLite) 변경

## 코드 구조 원칙
- 비즈니스 로직은 `modules/`에, UI 코드는 `pages/`에만 위치
- `app.py`는 진입점·공통 설정만, 페이지별 로직 추가 금지
- 신규 AI 엔진은 기존 ENGINE_CONFIGS 패턴에 맞춰 추가
- 설정값은 config.yaml/secrets.yaml에서 읽을 것, 하드코딩 금지

## 코딩 규칙
- `any` 타입·매직 넘버 하드코딩 금지
- DB 쿼리는 반드시 Peewee ORM 사용, raw SQL 금지
- 새 상수는 파일 상단 UPPER_CASE로 선언
- 불필요한 주석·docstring 추가 금지

## API/데이터 연동 규칙
- API 키는 secrets.yaml에서만 읽을 것, 코드에 직접 기입 금지
- Google Sheets 연동은 google_sheet.py 클래스만 사용
- 외부 API 호출 시 retry·에러 핸들링 필수
- 발행 로직에서 delay는 config.yaml 값 사용, 임의 변경 금지

## UI/레이아웃 제약
- Streamlit 컴포넌트 순서 변경 시 다른 페이지 영향 확인
- 신규 페이지는 `pages/` 하위에 번호_이모지_이름.py 형식 준수
- 사용자 피드백(spinner, progress, error)은 누락 없이 포함

## 데이터 무결성 규칙
- GeneratedArticle 상태값: 생성완료→검토완료→발행완료 순서 준수
- PublishLog는 성공·실패 모두 반드시 기록
- 쿠키 파일(`data/cookies/`) 삭제·덮어쓰기 전 반드시 확인

## 에러 대응 원칙
에러 발생 시: 원인 분석 → 수정 범위 확인 → RULES.md 관련 섹션 참조 → 수정.
즉시 코드 변경 금지. 여러 파일에 걸친 에러는 반드시 RULES.md 참조.

## 작업 완료 후 문서 갱신 (필수)
코드 수정·추가 완료 후 RULES.md의 "자동 문서 갱신 기준" 섹션을 읽고 해당 항목 갱신.
갱신할 내용이 없으면 "문서 갱신 불필요"라고 명시. 사용자에게 묻지 말고 자동 수행.

## MEMORY.md 관리
CLAUDE.md나 RULES.md에 이미 기술된 내용은 MEMORY.md에 중복 기록하지 말 것.
