# RULES.md — Blog-automation 상세 레퍼런스 문서

> AI 코딩 도구가 코드 수정·추가 시 참고하는 문서. 매 대화마다 자동 로딩되지 않으며, CLAUDE.md 지시에 따라 필요 시 읽힌다.

---

## 1. 프로젝트 정체성 및 기술 스택

**목표:** 네이버 블로그용 한국어 콘텐츠(텍스트+이미지)를 AI로 자동 생성·검토·발행하는 자동화 시스템.

### 핵심 기술 스택

| 영역 | 라이브러리/버전 | 용도 |
|---|---|---|
| UI | Streamlit 1.40.0 | 웹 대시보드 |
| 텍스트 AI | openai 1.60.0, anthropic 0.42.0, google-generativeai 0.8.0 | 다중 엔진 글 생성 |
| 이미지 AI | replicate 1.0.0, Ideogram REST, Pollinations REST | 다중 엔진 이미지 생성 |
| 브라우저 자동화 | undetected-chromedriver 3.5.5 + Selenium | 네이버 블로그 발행 |
| ORM / DB | peewee 3.17.0, SQLite (`data/blog_auto.db`) | 영구 상태 저장 |
| Google Sheets | gspread 6.1.0, oauth2client 4.1.3 | 키워드 관리·발행 기록 |
| 파일 처리 | pdfplumber 0.11.0, Pillow 10.4.0 | PDF 추출·이미지 처리 |
| 설정 | PyYAML 6.0.2 | config.yaml / secrets.yaml 파싱 |
| 스케줄링 | apscheduler 3.10.4 | 예약 작업 |
| 클립보드 | pyperclip 1.9.0 | 봇 탐지 우회 입력 |

### 데이터 소스

- **SQLite** (`data/blog_auto.db`): 생성 기사·이미지·발행 로그 영구 저장
- **Google Sheets**: 키워드 워크큐(`키워드`), 발행 감사 로그(`발행기록`), 블로그 계정(`블로그계정`), 상품정보(`상품정보`)
- **`config.yaml`**: 엔진 기본값, 딜레이, 경로, 블로그 계정 메타
- **`secrets.yaml`**: API 키, 블로그 비밀번호 (절대 커밋 금지)

### 상태 관리 방식

- **런타임 상태**: `st.session_state["config"]`, `st.session_state["secrets"]` (YAML 로드 후 캐시)
- **영구 상태**: Peewee ORM (GeneratedArticle 상태 머신, PublishLog 이력)
- **브라우저 세션**: `chrome_profiles/{blog_id}/` 독립 프로필 + `data/cookies/{blog_id}_cookies.json`

---

## 2. 아키텍처 및 코드 작성 원칙

### 구조 분리 원칙

| 위치 | 역할 | 포함해야 할 것 | 포함 금지 |
|---|---|---|---|
| `app.py` | 진입점·공통 설정 | config 로드, 사이드바, CSS, 공통 유틸 함수 | 페이지별 비즈니스 로직 |
| `modules/` | 비즈니스 로직 | AI 호출, DB 쿼리, 외부 API 연동 | Streamlit UI 코드 |
| `pages/` | UI 레이어 | Streamlit 위젯, 레이아웃, 사용자 흐름 | 직접 API 호출, DB 접근 |

### 상태 관리 규칙

- `st.session_state`는 config/secrets 캐시에만 사용; UI 임시 상태는 `st.session_state`에 key prefix로 구분
- `load_config()` / `load_secrets()`는 `@st.cache_data` 적용; 저장 후 반드시 `st.cache_data.clear()` 호출
- GeneratedArticle 상태 전이는 반드시 순서를 지킬 것: `생성완료` → `검토완료` → `발행완료` (역방향 전이 금지)

### 타입 안전성 규칙

- `any` 타입 사용 금지
- 매직 넘버 금지 — 파일 상단 `UPPER_CASE` 상수로 선언
- 새 엔진 추가 시 반드시 `ENGINE_CONFIGS` / `IMAGE_ENGINE_CONFIGS` 딕셔너리 패턴에 맞춰 추가
- `GeneratedArticle.tags`는 JSON 문자열로 저장; `get_tags_list()` / `set_tags_list()` 메서드만 사용

### API 연동 원칙

- API 키는 `secrets.yaml`에서만 읽음; `get_secrets()["api_keys"]["엔진명"]` 패턴 사용
- 모든 외부 API 호출에 timeout 필수 (60~120초)
- 에러 시 `PublishLog`·로그에 반드시 기록; 묵음 실패(silent failure) 금지
- 딜레이 값은 `config.yaml` `publish.*_delay` 범위에서 `random.uniform()` 사용; 하드코딩 금지

---

## 3. 파일/폴더별 책임 범위

### 모듈 (`modules/`)

| 파일 | 책임 | 주요 의존 | 수정 시 확인 사항 |
|---|---|---|---|
| `models.py` | Peewee ORM 모델 정의, DB 초기화 | peewee, SQLite | 4개 테이블 스키마 일관성; `init_db()` 호출 여부 |
| `content_generator.py` | 텍스트 다중 엔진 AI 생성 | openai, anthropic, google.generativeai, models.py | `ENGINE_CONFIGS` 구조 유지; `_parse_json_response()` JSON 파싱 로직 |
| `image_generator.py` | 이미지 다중 엔진 생성 | replicate, requests (Ideogram/Pollinations), Pillow | `IMAGE_ENGINE_CONFIGS` 구조 유지; `data/images/` 저장 경로 |
| `image_prompt_builder.py` | 아파트 이미지 프롬프트 변형 생성 | — | `APARTMENT_LOCATIONS(30)`, `DIRT_LEVELS(5)`, `LIGHT_SOURCES(5)`, `ANGLES(5)` 배열 크기 |
| `image_variable_analyzer.py` | AI로 최적 이미지 변수 자동 선택 | content_generator.py (LLM 재사용) | 엔진 우선순위 순서(비용 오름차순) 유지 |
| `blog_publisher.py` | 네이버 블로그 Selenium 자동화 | undetected-chromedriver, pyperclip, models.py | 로그인→워밍업→에디터→본문→이미지→태그→발행 순서; 쿠키 경로; `_wait()` 가우시안 분포; `_warmup_session()` config.yaml `publish.warmup`; `_human_scroll()` 스크롤 모방 |
| `attachment_manager.py` | 참고 파일(PDF·이미지·텍스트) 관리 | pdfplumber, Pillow, models.py | `MAX_EXTRACT_LEN=10_000`, `MAX_CONTEXT_PER_FILE=3_000` 제한값 |
| `google_sheet.py` | Google Sheets 읽기/쓰기 | gspread, oauth2client | 4개 시트명 상수 변경 시 전체 참조 확인 |
| `ip_changer.py` | ADB 비행기 모드로 모바일 IP 교체 | subprocess (adb), requests | Android SDK 버전 분기(12+ vs 레거시) |
| `prompt_loader.py` | 프롬프트 템플릿 로딩/저장, 기본값 관리 | — | `TEMPLATES_DIR`, `DEFAULT_*_PROMPT` 상수; `2_글_생성.py`와 `5_설정.py` 양쪽에서 사용 |
| `seo_optimizer.py` | 생성된 글의 제목·태그 SEO 후처리 | content_generator.py (LLM 재사용) | 엔진 우선순위(비용 오름차순) 유지; `_fallback()` 실패 시 원본 반환 |
| `scheduler.py` | APScheduler 기반 예약 발행 | apscheduler, blog_publisher.py, models.py | 싱글톤 패턴(`get_scheduler()`); 상태 파일 `data/scheduler_state.json`; 최대 스케줄 10개 |

### 페이지 (`pages/`)

| 파일 | 책임 | 주요 의존 | 수정 시 확인 사항 |
|---|---|---|---|
| `1_📊_대시보드.py` | 지표·발행 현황 표시 | models.py | 쿼리 성능 (인덱스 활용 여부) |
| `2_✍️_글_생성.py` | 글·이미지 생성 워크플로우 | content_generator.py, image_generator.py, attachment_manager.py, prompt_loader.py, models.py | 비용 표시, 생성 후 DB 저장; 상품 선택 UI(config.yaml `products`) |
| `3_👁️_검토_수정.py` | 기사·이미지 리뷰·수정 | models.py, image_generator.py | 상태 전이 (생성완료→검토완료) |
| `4_🚀_발행.py` | 발행 큐 관리·실행 | blog_publisher.py, ip_changer.py, models.py, google_sheet.py | 딜레이 설정, 단계별 피드백, PublishLog 기록 |
| `5_⚙️_설정.py` | API 키·설정·ADB·상품 리스트 관리 | app.py (get/save config/secrets), attachment_manager.py, prompt_loader.py | 키 마스킹 표시; secrets.yaml 저장; 탭6 상품 리스트(config.yaml `products`, 최대 15개) |
| `6_📅_예약발행.py` | 예약 발행 스케줄 등록·관리·실행 기록 | scheduler.py, models.py | 스케줄러 싱글톤; 최대 10개 스케줄; CronTrigger 사용 |

### 진입점 (`app.py`)

| 함수 | 역할 |
|---|---|
| `get_config()` / `get_secrets()` | session_state 캐시에서 설정 반환 |
| `save_config(config)` / `save_secrets(secrets)` | YAML 파일 저장 + 캐시 무효화 |
| `load_config()` / `load_secrets()` | `@st.cache_data` YAML 로더 |
| `render_status_bar(config)` | 상단 상태 배너 (IP, ADB, API 상태) |
| `render_sidebar(config)` | 계정 목록, 빠른 작업 |
| `inject_custom_css()` | 다크테마 스타일링 |
| `get_current_ip()` | `api.ipify.org` 현재 IP 조회 |

---

## 4. 의존관계 매핑

### 핵심 데이터 흐름

```
[Google Sheets: 키워드]
        │ fetch_pending_keywords()
        ▼
[pages/2_글_생성.py]
   │ keyword + 참고파일(PDF/image/text) + 상품선택(config.yaml products)
   │
   ├─[prompt_loader.py] → templates/ 시스템 프롬프트 로딩
   ├─[attachment_manager.py] → DB: Attachment
   │
   ├─[content_generator.py]
   │    ├─ OpenAI ChatCompletion
   │    ├─ Anthropic Messages
   │    └─ Google Gemini GenerativeModel
   │         └─ {title, body_html, tags, image_prompt}
   │
   ├─[image_variable_analyzer.py] → 최적 변수 자동 선택 (LLM 재사용)
   ├─[image_prompt_builder.py] → 프롬프트 변형 생성
   └─[image_generator.py]
        ├─ GPT Image / Gemini Image / Flux / Ideogram / Pollinations
        └─ data/images/ 저장
              │
              DB: GeneratedArticle(status=생성완료), GeneratedImage
              │
              ▼
[pages/3_검토_수정.py]
   │ 기사 편집, 이미지 선택
   │ GeneratedArticle.status = 검토완료
   │ GeneratedImage.is_selected = True
              │
              ▼
[pages/4_발행.py]
   │
   ├─[ip_changer.py] → ADB airplane mode → 새 IP
   │
   └─[blog_publisher.py]
        ├─ _create_driver(blog_id) → isolated Chrome profile
        ├─ login() → cookie 재사용 or pyperclip 입력
        ├─ _open_editor() → 네이버 에디터
        ├─ _insert_title/body_html/image/tags()
        └─ _click_publish() → post_url
              │
              ├─ DB: PublishLog(status=성공|실패)
              ├─ DB: GeneratedArticle.status = 발행완료
              └─[google_sheet.py] → 발행기록 시트 기록
```

### 주요 기능별 흐름도

**글 생성 상세:**
```
system_prompt(templates/*.txt) + user_prompt(키워드+첨부 컨텍스트)
    → ContentGenerator.generate(engine, model)
    → _parse_json_response() → JSON 추출 (코드블록 래핑 처리 포함)
    → _normalize_result() → 필드 보정
    → _calc_cost(tokens) → KRW 비용 계산
    → 결과: {title, body_html, tags, image_prompt, meta}
```

**SEO 후처리:**
```
pages/2_글_생성.py → SeoOptimizer.optimize(title, tags, keyword)
    → ContentGenerator.generate() [cheapest LLM 자동 선택]
    → DB: GeneratedArticle.title/tags 업데이트
```

**예약 발행:**
```
pages/6_예약발행.py → PublishScheduler (APScheduler BackgroundScheduler)
    → CronTrigger(hour, minute, day_of_week)
    → _execute_schedule()
        → GeneratedArticle.select(status="검토완료")
        → BlogPublisher.publish_single() × N건
        → PublishLog 기록
    → data/scheduler_state.json 상태 영속화
```

**이미지 병렬 생성:**
```
pages/2_글_생성.py → ImageGenerator.generate_batch()
    → ThreadPoolExecutor(max_workers=3)
    → generate() × N건 동시 실행
    → on_progress 콜백 → Streamlit progress bar 업데이트
```

**이미지 생성 상세:**
```
ImageVariableAnalyzer.analyze() [cheapest LLM 자동 선택]
    → {location_id, dirt_level, light_id, angle_id}
ImagePromptBuilder.build_apartment_prompts(variables, count)
    → list[{prompt, style, mood, composition}]
ImageGenerator.generate(engine, prompt, options)
    → 각 엔진별 API 호출 → 이미지 다운로드 → data/images/ 저장
    → {local_path, cost_estimate, width, height}
```

**발행 딜레이 흐름:**
```
발행 시작
  ├─ 시간 분산: schedule.time_jitter_minutes [0~15분] random (발행 시작 전 1회)
  ├─ 세션 워밍업: warmup.pages 순회 (로그인 후, 에디터 열기 전)
  │
  블로그 계정 N개 × 기사 M개
    ├─ 기사 간: inter_post_delay [30~90초] random (가우시안)
    └─ 블로그 간: inter_blog_delay [60~180초] random (가우시안)
    └─ 브라우저 액션 간: action_delay [1.5~4.0초] random (가우시안)
    └─ 스크롤 모방: _human_scroll() (에디터 열기 후, 본문 입력 후)
```

---

## 5. 핵심 타입 정의

```python
# models.py — DB 모델

class Attachment(Model):
    id: AutoField
    keyword_id: str          # 인덱스 필드
    original_filename: str
    stored_path: str
    file_type: str           # "pdf" | "image" | "text"
    file_size: int
    description: str | None
    extracted_text: str | None
    created_at: datetime

class GeneratedArticle(Model):
    id: AutoField
    keyword_id: str          # 인덱스 필드
    engine: str              # "openai" | "claude" | "gemini"
    model: str
    title: str
    body_html: str
    tags: str                # JSON 배열 문자열 — get_tags_list() 사용
    image_prompt: str | None
    status: str              # "생성완료" | "검토완료" | "발행완료" | "실패"
    cost_estimate: float     # KRW
    tokens_used: int
    created_at: datetime

class GeneratedImage(Model):
    id: AutoField
    keyword_id: str
    article_id: ForeignKeyField  # → GeneratedArticle
    engine: str              # "gpt_image" | "gemini_image" | "gemini_flash_image"
                             # | "flux_schnell" | "flux_pro" | "ideogram" | "pollinations"
    prompt_used: str
    local_path: str
    width: int
    height: int
    cost_estimate: float     # KRW
    is_selected: bool
    created_at: datetime

class PublishLog(Model):
    id: AutoField
    blog_id: str
    keyword_id: str
    article_id: ForeignKeyField  # → GeneratedArticle
    title: str
    post_url: str | None
    ip_address: str | None
    status: str              # "성공" | "실패"
    error_message: str | None
    screenshot_path: str | None
    retry_count: int
    delay_seconds: float
    published_at: datetime
```

```python
# content_generator.py — 반환 타입

GenerateResult = {
    "title": str,
    "body_html": str,
    "tags": list[str],
    "image_prompt": str,
    "meta": {
        "engine": str,
        "model": str,
        "tokens_used": int,
        "cost_estimate": float   # KRW
    }
}

# ENGINE_CONFIGS 구조 (텍스트 엔진)
EngineConfig = {
    "models": list[str],
    "pricing": {
        model_name: {
            "input": float,   # $/1M tokens
            "output": float
        }
    }
}
```

```python
# image_generator.py — 반환 타입

ImageGenerateResult = {
    "local_path": str,
    "prompt_used": str,
    "engine": str,
    "cost_estimate": float,   # KRW
    "width": int,
    "height": int
}

# IMAGE_ENGINE_CONFIGS 구조
ImageEngineConfig = {
    "name": str,
    "available": bool,        # API 키 존재 여부
    "cost_krw": float,
    "aspect_ratios": list[str]
}
```

```python
# blog_publisher.py — 반환 타입

PublishResult = {
    "success": bool,
    "post_url": str | None,
    "status": str,   # "성공" | "로그인실패" | "에디터실패" | "발행실패"
    "blog_id": str,
    "retry_count": int,
    "delay_seconds": float,
    "ip_address": str | None,
    "screenshot_path": str | None,
    "error_message": str | None
}
```

```python
# ip_changer.py — 반환 타입

IpChangeResult = {
    "success": bool,
    "old_ip": str | None,
    "new_ip": str | None,
    "changed": bool,
    "android_sdk": int
}
```

```python
# config.yaml 블로그 계정 항목

BlogAccount = {
    "blog_id": str,
    "name": str,
    "naver_id": str,
    "blog_url": str | None,
    "cookie_path": str | None,
    "status": str,    # "활성" | "비활성"
    "posts_today": int
}
```

---

## 6. 핵심 로직 상세

### ContentGenerator._parse_json_response

```python
def _parse_json_response(self, raw_text: str) -> dict:
    """
    AI 응답에서 JSON 추출. 코드블록 래핑(```json ... ```) 처리 포함.
    실패 시 빈 dict 반환 (호출부에서 _normalize_result로 보정).
    """
    text = raw_text.strip()
    # 코드블록 제거
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 부분 추출 시도
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        return {}
```

### ImageVariableAnalyzer.pick_engine (비용 오름차순 선택)

```python
# 엔진 우선순위 (비용 KRW 오름차순)
ENGINE_PRIORITY = [
    ("gemini", "gemini-2.0-flash-lite"),   # ₩0.25
    ("gemini", "gemini-2.5-flash"),         # ₩0.50
    ("openai", "gpt-4o-mini"),              # ₩0.50
    ("claude", "claude-haiku-4-5"),         # ₩3.57
    ("gemini", "gemini-2.5-pro"),           # ₩5.25
    ("openai", "gpt-4o"),                   # ₩8.40
    ("claude", "claude-sonnet-4-5"),        # ₩10.71
]
# API 키 있는 첫 번째 엔진 선택
```

### BlogPublisher.login (쿠키 → pyperclip 폴백)

```python
def login(self, blog_id, naver_id, naver_pw) -> bool:
    # 1. 쿠키 로드 시도
    if self._load_cookies(blog_id):
        driver.get("https://www.naver.com")
        if self._is_logged_in():
            return True
    # 2. pyperclip 로그인 (키보드 탐지 우회)
    success = self._login_with_pyperclip(naver_id, naver_pw)
    if success:
        self._save_cookies(blog_id)
    return success
```

### GoogleSheetManager 시트명 상수

```python
SHEET_KEYWORDS = "키워드"
SHEET_PRODUCTS = "상품정보"
SHEET_ACCOUNTS = "블로그계정"
SHEET_PUBLISH_LOG = "발행기록"
```

### config.yaml publish 딜레이 구조

```yaml
publish:
  inter_blog_delay: [60, 180]   # 초 [min, max]
  inter_post_delay: [30, 90]    # 초 [min, max]
  action_delay: [1.5, 4.0]      # 초 [min, max] (가우시안 분포)
  max_retries: 2
  warmup:
    enabled: true               # 발행 전 세션 워밍업 활성화
    pages:                      # 워밍업 방문 페이지 (blog_id 치환)
      - https://www.naver.com
      - https://blog.naver.com/{blog_id}
  schedule:
    time_jitter_minutes: 15     # 발행 시작 전 랜덤 대기 (0~15분)
```

---

## 7. 에러 처리 패턴

### 발행 재시도 패턴

```python
max_retries = config["publish"]["max_retries"]  # default 2

for attempt in range(1, max_retries + 1):
    try:
        result = publisher.publish_single(...)
        if result["success"]:
            PublishLog.create(status="성공", post_url=result["post_url"], ...)
            article.status = "발행완료"
            article.save()
            break
    except Exception as e:
        screenshot_path = publisher._save_screenshot(f"error_{attempt}")
        if attempt == max_retries:
            PublishLog.create(
                status="실패",
                error_message=str(e),
                screenshot_path=screenshot_path,
                retry_count=attempt,
                ...
            )
            article.status = "실패"
            article.save()
        else:
            time.sleep(random.uniform(*config["publish"]["action_delay"]))
```

### IP 변경 재시도 패턴

```python
for attempt in range(1, ip_check_retries + 1):
    new_ip = self._get_public_ip()
    if new_ip and new_ip != old_ip:
        return {"success": True, "changed": True, "new_ip": new_ip}
    if attempt < ip_check_retries:
        time.sleep(5)
# 모든 시도 실패 시 success=False 반환 (예외 발생 금지)
```

### AI API 공통 에러 처리

```python
try:
    response = client.generate(...)
    result = self._parse_json_response(response)
    return self._normalize_result(result)
except (openai.APIError, anthropic.APIError, ...) as e:
    # 재시도 없이 바로 상위로 전파 (호출부에서 처리)
    raise
except json.JSONDecodeError:
    # 파싱 실패 시 빈 dict 반환 후 _normalize_result로 기본값 채움
    return self._normalize_result({})
```

### Gemini 안전 필터 탐지

```python
# Gemini 응답에서 safety block 감지 후 로그 기록
if response.prompt_feedback.block_reason:
    raise ValueError(f"Gemini safety block: {response.prompt_feedback.block_reason}")
```

---

## 8. 주의사항 및 오류 방지

### API 키 관련

- **secrets.yaml 누락 시**: `get_secrets()` 빈 dict 반환 → API 키 없음으로 처리. `is_engine_available(engine)` 로 사전 확인 필수
- **API 키 마스킹**: Settings 페이지에서 앞 4자·뒤 4자만 표시; 전체 노출 금지
- **Gemini 이미지 생성**: `secrets.yaml`의 `api_keys.gemini` 값 사용 (config.yaml 아님)

### 데이터 무결성

- **tags 필드**: `GeneratedArticle.tags`는 JSON 문자열(`"[\"태그1\", \"태그2\"]"`) — 직접 str 조작 금지, 반드시 `get_tags_list()` / `set_tags_list()` 사용
- **상태 역전 금지**: `발행완료` → `검토완료` 등 역방향 전이 금지
- **PublishLog 누락 금지**: 성공·실패 모두 반드시 `PublishLog.create()` 호출
- **article.status 업데이트 누락**: 발행 성공 후 `GeneratedArticle.status = "발행완료"` + `article.save()` 반드시 쌍으로 처리

### 쿠키 파일

- **경로**: `data/cookies/{blog_id}_cookies.json`
- **삭제 전**: 발행 중인 세션 여부 확인 (다른 프로세스가 사용 중일 수 있음)
- **덮어쓰기**: 로그인 성공 후에만 `_save_cookies()` 호출 (실패 시 이전 쿠키 유지)

### Chrome 프로필

- **경로**: `chrome_profiles/{blog_id}/`
- **계정당 독립 프로필**: 여러 계정 동시 사용 시 프로필 혼용 금지
- **드라이버 종료**: `_quit_driver()` 항상 finally 블록에서 호출

### 딜레이 설정

- `action_delay`, `inter_post_delay`, `inter_blog_delay` 값은 반드시 `config.yaml`에서 읽음
- `time.sleep(random.uniform(min, max))` 패턴 사용; `time.sleep(고정값)` 하드코딩 금지
- 발행 로직 외 코드에서 긴 sleep 추가 금지

### Google Sheets 연동

- **지연 연결(lazy connection)**: `_connect()` 는 첫 API 호출 시 실행; 초기화 시 연결 시도 금지
- **행 번호**: Google Sheets API는 1-based index. `fetch_pending_keywords()` 반환값의 `row_number`는 시트 실제 행 번호
- **배치 쓰기**: 다수 발행 결과는 `write_publish_results_batch()` 사용 (API 할당량 절약)

### 이미지 변수 분석

- `ImageVariableAnalyzer` 실패 시 `_default_vars()` 폴백 사용 (절대 예외 전파 금지)
- `APARTMENT_LOCATIONS` 배열 수정 시 `image_variable_analyzer.py`의 ID 범위 검증 로직도 동시 수정 필요

### 이미지 병렬 생성

- `MAX_PARALLEL_WORKERS = 3` — API rate limit을 고려한 기본값. 무분별한 증가 금지
- `generate_batch()` 내부에서 `ThreadPoolExecutor` 사용; Streamlit의 메인 스레드와 독립적
- 파일 이름 충돌 방지: 각 엔진의 `_gen_*()` 메서드가 `time.time()` 기반 유니크 파일명 사용. 병렬 실행 시 밀리초 단위 충돌 가능성은 무시할 수준
- `on_progress` 콜백은 예외를 먹으므로(try/except) UI 콜백 실패가 생성을 중단시키지 않음

### 예약 발행 스케줄러

- `get_scheduler()` 싱글톤 — 프로세스 내 하나의 인스턴스만 존재
- 상태 파일: `data/scheduler_state.json` — 스케줄 정의 + 최근 100건 실행 기록 저장
- Streamlit 재시작 시 `get_scheduler(config)` 호출로 자동 복원되지만, `start()` 호출은 수동 (UI에서 "스케줄러 시작" 버튼)
- `_execute_schedule()`은 백그라운드 스레드에서 실행 — DB 접근 시 `init_db()` 재호출 필수
- 최대 스케줄 수: `MAX_SCHEDULES = 10`
- `coalesce=True` — 스케줄러가 꺼진 동안 놓친 실행은 1회만 보충 실행

### 비용 계산

- `USD_TO_KRW = 1400` 고정 환율 사용 (실시간 환율 연동 없음)
- 비용은 추정치(`cost_estimate`)이며 실제 청구액과 다를 수 있음
- `tokens_used` 는 입력+출력 토큰 합산값으로 저장

---

## 9. 수정 시 체크리스트

### 새 텍스트 AI 엔진 추가 시

- [ ] `content_generator.py` `ENGINE_CONFIGS`에 엔진·모델·가격 추가
- [ ] `_init_clients()` 에 클라이언트 초기화 추가
- [ ] `_generate_{엔진명}()` 메서드 구현
- [ ] `generate()` 디스패치 딕셔너리에 등록
- [ ] `available_engines()` 에서 API 키 확인 조건 추가
- [ ] `image_variable_analyzer.py` `ENGINE_PRIORITY` 비용 순서에 삽입
- [ ] `pages/2_글_생성.py` 엔진 선택 UI 업데이트
- [ ] `pages/5_설정.py` API 키 입력 필드 추가

### 새 이미지 AI 엔진 추가 시

- [ ] `image_generator.py` `IMAGE_ENGINE_CONFIGS`에 추가
- [ ] `_gen_{엔진명}()` 메서드 구현
- [ ] `generate()` 디스패치 딕셔너리에 등록
- [ ] `get_available_engines()` API 키 확인 추가
- [ ] `GeneratedImage.engine` 허용값 문서에 추가 (섹션 5)
- [ ] `pages/2_글_생성.py` 이미지 엔진 선택 UI 업데이트

### DB 모델 새 필드 추가 시

- [ ] `models.py` 해당 Model 클래스에 필드 추가
- [ ] 기존 DB 마이그레이션 방안 확인 (peewee는 자동 마이그레이션 없음)
- [ ] 해당 모델을 쿼리·생성하는 모든 페이지 파일 업데이트
- [ ] 섹션 5 타입 정의 업데이트
- [ ] `init_db()` 가 `create_tables(safe=True)` 사용하는지 확인

### 새 페이지 추가 시

- [ ] `pages/` 하위에 `{번호}_{이모지}_{이름}.py` 형식 파일 생성
- [ ] 페이지 상단에서 `from app import get_config, get_secrets` 임포트
- [ ] 비즈니스 로직은 `modules/`에 분리, UI만 페이지에 작성
- [ ] 다른 페이지 레이아웃에 영향 없는지 확인 (공통 사이드바·CSS)

### 발행 로직 수정 시

- [ ] `PublishLog` 생성 코드 누락 여부 확인 (성공·실패 모두)
- [ ] `GeneratedArticle.status` 업데이트 + `save()` 쌍 확인
- [ ] `google_sheet.py` 발행기록 시트 기록 호출 확인
- [ ] 딜레이 값이 `config.yaml`에서 읽히는지 확인
- [ ] `_quit_driver()` finally 블록 처리 확인

### Google Sheets 연동 수정 시

- [ ] 시트명 변경 시 `google_sheet.py` 상단 상수 수정
- [ ] 열 순서 변경 시 `fetch_*` 및 `write_*` 메서드 동시 수정
- [ ] `test_connection()` 으로 연결 상태 검증 로직 유지

---

## 10. 확장 가이드

### 새 블로그 계정 추가

1. `config.yaml` `blog_accounts` 배열에 항목 추가
2. `chrome_profiles/{blog_id}/` 디렉토리 자동 생성 (첫 실행 시)
3. Google Sheets `블로그계정` 시트에 행 추가 (선택사항)
4. 첫 발행 시 `data/cookies/{blog_id}_cookies.json` 자동 생성

### 새 콘텐츠 유형(글 템플릿) 추가

1. `templates/` 에 `{유형}_prompt.txt` 파일 생성
2. `pages/2_글_생성.py` 콘텐츠 유형 선택 UI에 옵션 추가
3. `pages/5_설정.py` 프롬프트 편집 섹션에 해당 템플릿 추가

### 새 첨부 파일 유형 지원 추가

1. `attachment_manager.py` `ALLOWED_TYPES` 딕셔너리에 확장자 추가
2. `_detect_type()` 매핑 업데이트
3. `_extract_text()` 에 해당 파일 타입 처리 분기 추가

### 새 Google Sheets 시트 추가

1. `google_sheet.py` 상단 시트명 상수 추가
2. `_get_worksheet(name)` 패턴으로 접근 메서드 작성
3. `test_connection()` 테스트 범위에 포함

### ADB 명령 추가 (IP 변경 외 목적)

1. `ip_changer.py` `_run_adb(*args)` 메서드 재사용
2. Android SDK 버전 분기가 필요하면 `is_android_12_plus()` 활용

---

## 11. 자동 문서 갱신 기준

AI가 코드 수정·추가 작업을 완료한 후, 아래 기준에 따라 자동으로 문서를 갱신한다.
사용자에게 묻지 않고 수행하며, 갱신할 내용이 없으면 "문서 갱신 불필요"라고 작업 말미에 명시한다.

### RULES.md 갱신 조건 (해당 항목만)

- **섹션 3** (파일/폴더별 책임): 새 파일 추가, 기존 파일 책임 변경, 의존관계 변경
- **섹션 4** (의존관계 매핑): 데이터 흐름 변경
- **섹션 5** (타입 정의): 핵심 인터페이스 필드 추가/삭제
- **섹션 8** (주의사항): 새로운 gotcha/함정 발견
- 삭제된 기능이나 더 이상 유효하지 않은 내용은 제거

### CLAUDE.md 갱신 조건 (드물게)

- 새로운 "절대 금지" 수준의 규칙이 생겼을 때만
- 기존 금지 규칙이 변경되었을 때만
- 50줄 이내 유지 필수

### README.md 갱신 조건

- 사용자에게 보이는 기능이 추가/변경된 경우만
- 내부 리팩토링은 갱신하지 않음

### 갱신 원칙

- 변경사항이 없는 파일은 건드리지 않는다
- 기존 내용과 중복되는 내용을 추가하지 않는다
- 일자별 업데이트 기록을 남기지 않는다
