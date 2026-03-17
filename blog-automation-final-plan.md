# 포스팅 자동발행 시스템 — 최종 수정 계획서

> 기존 계획서(system-design.md)와 리서치 추천안을 비교 분석하여, 양쪽의 장점만 결합한 최종 버전입니다.

---

## 비교 분석 요약

### 기존 계획서의 장점 (유지할 것)

1. **구글 시트 데이터 허브** — 프로그래밍 없이 키워드·상품정보를 관리할 수 있어 실제 운영이 편함
2. **프롬프트 설계** — 정보성/상품홍보 프롬프트 템플릿이 구체적이고 실전적임
3. **0원 운영비** — Gemini Flash 무료 + Pollinations 무료 조합
4. **폴더 구조** — 모듈별 분리가 깔끔하고 바이브코딩에 적합
5. **UI 목업** — 대시보드/생성/검토/발행 4탭 구조와 발행 진행률 UX가 훌륭함
6. **발행 워크플로우** — 같은 블로그 연속 발행 시 IP 유지하는 최적화 로직
7. **쿠키 관리** — 블로그별 쿠키 저장/재사용으로 로그인 빈도 최소화
8. **Chrome 프로필 분리** — 계정별 프로필로 핑거프린트 다양화

### 기존 계획서의 약점 (개선할 것)

1. **Gemini Flash 한국어 품질** — 무료 티어는 품질이 불안정하고, 블로그 글 수준에 못 미치는 경우가 빈번
2. **Pollinations 이미지 품질** — 무료 API라 해상도, 일관성, 안정성이 떨어짐 (서비스 중단 리스크도 있음)
3. **Streamlit 리로드 문제** — 글 수정 중 버튼 클릭 시 전체 페이지가 리셋될 수 있음
4. **구글 시트 단독 의존** — 네트워크 끊김 시 데이터 접근 불가, API 호출 속도 느림
5. **ADB 명령어 호환성** — `settings put global` 방식은 Android 12+에서 제한됨
6. **에러 복구 로직 부재** — 발행 중 실패 시 어디서부터 재시도할지 불명확

### 리서치 추천안의 장점 (반영할 것)

1. **AI 모델 이원화** — 정보성은 GPT-4o, 홍보성은 Claude로 나눠 품질 극대화
2. **GPT Image 1 Mini** — 안정적 이미지 품질 + OpenAI 통합 API 키로 관리 간소화
3. **NiceGUI** — 이벤트 기반이라 편집 중 상태 유지됨
4. **SQLite + Peewee** — 로컬 DB로 오프라인에서도 동작, 관계형 쿼리 가능
5. **Android 12+ ADB 명령** — `cmd connectivity airplane-mode` 최신 방식
6. **undetected-chromedriver 대안** — nodriver, SeleniumBase UC Mode 등 백업 옵션

### 리서치 추천안의 약점 (개선할 것)

1. **구글 시트 제외** — 비개발자에게 SQLite는 직접 데이터 확인/수정이 어려움
2. **NiceGUI 생태계** — Streamlit 대비 커뮤니티가 작아 바이브코딩 시 코드 생성 품질이 낮을 수 있음
3. **비용 발생** — 월 3.5~5만원이 들지만 예산(5~10만원) 범위 내

---

## 최종 결합 기술 스택

| 구성요소 | 최종 선택 | 근거 |
|---------|----------|------|
| **데이터 허브** | 구글 시트 (주) + SQLite (보조) | 기존 계획의 운영 편의성 유지 + SQLite로 로컬 캐시·쿠키·세션 관리 |
| **AI 글 작성** | GPT-4o-mini (기본) + GPT-4o (품질 필요시) | 기존 Gemini Flash 대비 한국어 품질 우수, 월 600~9,500원 수준 |
| **AI 이미지** | GPT Image 1 Mini (기본) + Pollinations (백업) | 안정성 확보 + Pollinations는 무료 백업으로 유지 |
| **검토 UI** | Streamlit (현실적 선택) | 바이브코딩 생태계 최강, 기존 목업 그대로 활용 가능. `st.form()`으로 리로드 문제 완화 |
| **브라우저 자동화** | undetected-chromedriver | 양쪽 동일 |
| **IP 변경** | ADB (Android 12+ 명령어 우선) | 리서치안의 최신 명령어 적용 |
| **스케줄러** | APScheduler (선택 추가) | 자동 글 생성 예약 기능으로 확장 가능 |
| **개발 도구** | Cursor + Claude Code | 바이브코딩에 최적 |

### 월 예상 비용

| 항목 | 월 비용 | 비고 |
|------|--------|------|
| GPT-4o-mini (글 600건) | ~600원 | Batch API 사용 시 ~300원 |
| GPT-4o (고품질 필요시 일부) | ~5,000원 | 전체 10% 수준만 사용 |
| GPT Image 1 Mini (1,200장) | ~18,000원 | 블로그당 3장 기준 |
| Pollinations (백업) | 0원 | 무료 |
| 구글 시트 | 0원 | 개인 계정 |
| **합계** | **약 2~2.5만원** | 예산 5~10만원 대비 충분한 여유 |

---

## 수정된 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│              구글 시트 (운영자용 데이터 관리)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 키워드    │  │ 상품정보  │  │ 블로그계정 │  │ 발행기록  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└────────┬───────────┬──────────────────────────┬──────────┘
         │           │                          │
         ▼           ▼                          ▲
┌─────────────────────────────────────────────────────────┐
│                  Python 백엔드                           │
│                                                         │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │ GPT-4o-mini  │  │ GPT Image 1   │  │ APScheduler  │ │
│  │ / GPT-4o     │  │ Mini          │  │ (예약 생성)   │ │
│  │ 글 생성       │  │ + Pollinations│  │              │ │
│  │              │  │ 이미지 생성    │  │              │ │
│  └──────────────┘  └───────────────┘  └──────────────┘ │
│                                                         │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │ ADB IP 변경   │  │ undetected    │  │ SQLite       │ │
│  │ (최신 명령어) │  │ -chromedriver │  │ + 쿠키/세션   │ │
│  │              │  │ 블로그 발행    │  │ + 발행 큐     │ │
│  └──────────────┘  └───────────────┘  └──────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Streamlit UI (검토·관리 화면)                │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 📊 대시보드   │  │ ✍️ 글 생성    │  │ 👁️ 검토/수정  │ │
│  │              │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────────────────────────┐ │
│  │ 🚀 발행      │  │ ⚙️ 설정 (API키, 프롬프트 관리)    │ │
│  └──────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 모듈별 수정사항

### 모듈 1: 데이터 관리 — 하이브리드 방식

**기존안의 구글 시트 구조를 그대로 유지**하되, SQLite를 로컬 캐시 겸 발행 큐로 활용한다.

**구글 시트 역할 (변경 없음):**
- 키워드 시트, 상품정보 시트, 블로그 계정 시트, 발행기록 시트 — 기존 구조 그대로

**SQLite 역할 (추가):**
- 발행 대기 큐 (검토 완료된 글을 순서대로 관리)
- 쿠키/세션 저장
- 생성된 글/이미지 임시 저장
- 오프라인 작업 지원 (구글 시트 접속 불가 시에도 발행 가능)

**동기화 로직:**
```
구글 시트에서 키워드 읽기 → SQLite에 캐시
글 생성 후 SQLite에 저장 → 발행 후 구글 시트에 기록
```

이렇게 하면 평소에는 구글 시트에서 편하게 데이터를 관리하면서, 시스템 내부적으로는 SQLite의 안정성과 속도를 활용할 수 있다.

---

### 모듈 2: AI 글 생성 — 모델 업그레이드

**변경: Gemini Flash → GPT-4o-mini (기본) / GPT-4o (고품질)**

변경 이유:
- Gemini Flash 무료 티어는 한국어 블로그 글 품질이 불안정
- GPT-4o-mini는 월 600원에 600건 처리 가능 (사실상 무료 수준)
- 중요한 글은 GPT-4o로 생성하면 품질이 확연히 다름

**프롬프트 템플릿은 기존안 그대로 유지** (매우 잘 설계되어 있음). 다만 OpenAI API에 맞게 호출 부분만 변경:

```python
# 기존: google-generativeai 라이브러리
# 변경: openai 라이브러리
from openai import OpenAI
client = OpenAI(api_key="...")

response = client.chat.completions.create(
    model="gpt-4o-mini",  # 또는 "gpt-4o"
    messages=[
        {"role": "system", "content": "당신은 네이버 블로그 SEO 전문가입니다."},
        {"role": "user", "content": formatted_prompt}
    ],
    response_format={"type": "json_object"}
)
```

**AI 모델 선택 전략:**
| 상황 | 모델 | 이유 |
|------|------|------|
| 일반 정보성 글 | GPT-4o-mini | 비용 효율, 품질 양호 |
| 고품질 필요한 글 | GPT-4o | 자연스러운 한국어, SEO 최적화 |
| 대량 사전 생성 | GPT-4o-mini + Batch API | 50% 할인, 24시간 내 완료 |

UI에서 글 생성 시 모델을 선택할 수 있도록 드롭다운 추가.

---

### 모듈 3: AI 이미지 생성 — 2단계 체제

**변경: Pollinations 단독 → GPT Image 1 Mini (기본) + Pollinations (백업)**

```python
# 1순위: GPT Image 1 Mini
from openai import OpenAI
client = OpenAI()

response = client.images.generate(
    model="gpt-image-1",
    prompt=image_prompt,
    size="1024x1024",
    quality="medium",  # low/medium/high
    n=1
)

# 2순위: Pollinations (GPT 실패 시 폴백)
fallback_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=500"
```

**변경 이유:**
- GPT Image 1 Mini는 장당 약 15원으로 품질 대비 가성비 최고
- Pollinations는 무료지만 품질이 일정하지 않고 서비스 안정성이 보장되지 않음
- 두 가지를 함께 쓰면 하나가 죽어도 시스템이 멈추지 않음

이미지 처리 흐름은 기존안 그대로 유지 (로컬 저장 → Pillow 후처리 → DB 저장).

---

### 모듈 4: 검토 UI — Streamlit 유지 + 리로드 대응

**결론: Streamlit 유지**

NiceGUI가 기술적으로 더 적합하지만, 현실적 이유로 Streamlit을 선택:
- 기존 목업(blog-automation-mockup.jsx)의 UX 설계가 Streamlit으로 변환하기 쉬움
- 바이브코딩 시 AI 코드 생성 품질이 Streamlit이 압도적으로 높음
- 커뮤니티가 커서 문제 해결이 쉬움

**Streamlit 리로드 문제 해결책:**

```python
# 글 수정 폼을 st.form()으로 감싸면 제출 전까지 리로드 안 됨
with st.form("edit_form"):
    title = st.text_input("제목", value=draft["title"])
    body = st.text_area("본문", value=draft["body"], height=400)
    tags = st.text_input("태그", value=", ".join(draft["tags"]))
    
    col1, col2 = st.columns(2)
    with col1:
        regenerate = st.form_submit_button("🔄 재생성")
    with col2:
        approve = st.form_submit_button("✅ 검토 완료")
```

**기존 목업 대비 추가할 기능:**
- AI 모델 선택 드롭다운 (GPT-4o-mini / GPT-4o)
- 이미지 품질 선택 (GPT Image / Pollinations)
- 프롬프트 직접 수정 기능 (고급 사용자용)
- 발행 실패 시 재시도 버튼
- ⚙️ 설정 탭 추가 (API 키, 프롬프트 템플릿, 블로그 발행 간격 등)

---

### 모듈 5: IP 변경 — ADB 명령어 업데이트

**기존 코드의 ADB 명령어를 Android 12+ 호환 방식으로 변경:**

```python
import subprocess
import time
import requests

def change_ip():
    """비행기모드 토글로 IP 변경 (Android 12+ 호환)"""
    
    # Android 버전 감지
    android_ver = subprocess.run(
        ["adb", "shell", "getprop", "ro.build.version.sdk"],
        capture_output=True, text=True
    ).stdout.strip()
    
    if int(android_ver) >= 31:  # Android 12+
        # 신규 방식 (권장)
        subprocess.run(["adb", "shell", "cmd", "connectivity", "airplane-mode", "enable"])
        time.sleep(8)
        subprocess.run(["adb", "shell", "cmd", "connectivity", "airplane-mode", "disable"])
    else:
        # 구형 방식 (기존 계획서)
        subprocess.run(["adb", "shell", "settings", "put", "global", "airplane_mode_on", "1"])
        subprocess.run(["adb", "shell", "am", "broadcast", "-a", 
                        "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"])
        time.sleep(8)
        subprocess.run(["adb", "shell", "settings", "put", "global", "airplane_mode_on", "0"])
        subprocess.run(["adb", "shell", "am", "broadcast", "-a", 
                        "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"])
    
    # 네트워크 재연결 대기 (기존 15초 → 20초로 여유 확보)
    time.sleep(20)
    
    # IP 변경 확인 (재시도 로직 추가)
    for attempt in range(3):
        try:
            new_ip = requests.get("https://api.ipify.org", timeout=10).text
            return new_ip
        except:
            time.sleep(5)
    
    raise Exception("IP 변경 후 네트워크 복구 실패")
```

**기존안 대비 개선점:**
- Android 버전 자동 감지로 두 방식 모두 대응
- 네트워크 복구 재시도 로직 추가 (3회)
- timeout 설정으로 무한 대기 방지

---

### 모듈 6: 블로그 발행 — 기존안 유지 + 안정성 강화

기존 계획서의 발행 흐름, 스마트에디터 대응, 봇 탐지 회피 전략을 **그대로 유지**하되, 아래를 추가:

**추가 1: 에러 복구 로직**

```python
class PublishResult:
    SUCCESS = "success"
    LOGIN_FAIL = "login_fail"
    EDITOR_FAIL = "editor_fail"  
    PUBLISH_FAIL = "publish_fail"
    NETWORK_FAIL = "network_fail"

def publish_with_retry(post, blog_account, max_retries=2):
    """발행 실패 시 자동 재시도"""
    for attempt in range(max_retries + 1):
        result = publish_single(post, blog_account)
        
        if result.status == PublishResult.SUCCESS:
            return result
        
        if result.status == PublishResult.LOGIN_FAIL:
            # 쿠키 삭제 후 새로 로그인
            delete_cookie(blog_account.id)
            continue
        
        if result.status == PublishResult.NETWORK_FAIL:
            # IP 재변경 후 재시도
            change_ip()
            continue
        
        if result.status in [PublishResult.EDITOR_FAIL, PublishResult.PUBLISH_FAIL]:
            # 스크린샷 저장 후 수동 처리 대기열에 추가
            save_screenshot(f"error_{post.id}_{attempt}.png")
            continue
    
    return result  # 최종 실패 반환
```

**추가 2: 발행 간격 랜덤화 강화**

```python
import random

# 기존: 고정 딜레이
# 변경: 블로그 간 전환 시 60~180초 랜덤 대기
INTER_BLOG_DELAY = (60, 180)    # 블로그 전환 시
INTER_POST_DELAY = (30, 90)     # 같은 블로그 내 연속 발행 시
ACTION_DELAY = (1.5, 4.0)       # 에디터 내 각 액션 사이

def wait_random(delay_range):
    delay = random.uniform(*delay_range)
    time.sleep(delay)
```

**추가 3: nodriver 백업 옵션**

```python
# undetected-chromedriver가 탐지될 경우 대안
# pip install nodriver
import nodriver as nd

async def publish_with_nodriver(post, blog_account):
    browser = await nd.start()
    page = await browser.get("https://nid.naver.com/nidlogin.login")
    # ... nodriver 방식의 발행 로직
```

---

## 수정된 폴더 구조

```
naver-blog-automation/
├── app.py                    # Streamlit 메인 앱
├── config.yaml               # 설정 파일 (API 키, 경로 등)
├── requirements.txt           # Python 패키지 목록
│
├── modules/
│   ├── google_sheet.py        # 구글 시트 읽기/쓰기
│   ├── content_generator.py   # ★ OpenAI API 글 생성 (기존 Gemini → 변경)
│   ├── image_generator.py     # ★ GPT Image + Pollinations 듀얼 (변경)
│   ├── ip_changer.py          # ★ ADB Android 12+ 호환 (업데이트)
│   ├── blog_publisher.py      # Selenium 블로그 발행 (유지)
│   ├── cookie_manager.py      # 쿠키/세션 관리 (유지)
│   ├── error_handler.py       # ★ 에러 복구 + 재시도 로직 (추가)
│   └── scheduler.py           # ★ APScheduler 예약 생성 (추가)
│
├── templates/
│   ├── info_prompt.txt        # 정보성 글 프롬프트 (유지)
│   └── product_prompt.txt     # 상품홍보 글 프롬프트 (유지)
│
├── data/
│   ├── blog_auto.db           # SQLite (확장: 발행 큐 + 캐시 추가)
│   ├── cookies/               # 블로그별 쿠키 파일 (유지)
│   └── images/                # 생성된 이미지 저장 (유지)
│
├── chrome_profiles/           # 블로그별 Chrome 프로필 (유지)
│
└── logs/                      # ★ 에러 로그 + 스크린샷 (추가)
    ├── error_screenshots/
    └── publish.log
```

---

## 수정된 전체 발행 워크플로우

```
[일괄 발행 시작 버튼 클릭]
        │
        ▼
┌─ 발행 대기열에서 첫 번째 글 선택 ─┐
│                                  │
│   ① IP 변경 (ADB, Android 버전  │
│      자동 감지)                   │
│         │                        │
│   ② IP 변경 확인 (20초 대기,     │
│      3회 재시도)                  │
│         │                        │
│   ③ 해당 블로그 계정으로 로그인    │
│      (쿠키 우선, 없으면 pyperclip)│
│         │                        │
│   ④ 에디터 열기                   │
│         │                        │
│   ⑤ 제목 + 본문 + 이미지 + 태그   │
│      (랜덤 딜레이 1.5~4초)        │
│         │                        │
│   ⑥ 발행 버튼 클릭               │
│         │                        │
│   ⑦ 발행 URL 확인                │
│      ├─ 성공 → ⑧로              │
│      └─ 실패 → 재시도 (최대 2회) │
│                → 스크린샷 저장    │
│         │                        │
│   ⑧ 구글 시트에 결과 기록         │
│         │                        │
│   ⑨ 브라우저 종료                │
│         │                        │
│   ⑩ 다음 글 확인                 │
│      같은 블로그 → 30~90초 대기   │
│                    → ③번으로      │
│      다른 블로그 → 60~180초 대기  │
│                    → ①번으로      │
│                                  │
└──── 대기열 소진까지 반복 ──────────┘
        │
        ▼
[발행 완료 요약 + 실패 건 표시]
```

---

## 수정된 구현 우선순위

### Phase 1: AI 핵심 기능 (1주)
- [ ] OpenAI API 연동 (GPT-4o-mini 글 생성)
- [ ] GPT Image 1 Mini 이미지 생성
- [ ] Pollinations 폴백 이미지 생성
- [ ] 기존 프롬프트 템플릿으로 품질 테스트
- **목표**: AI 글+이미지 생성 품질 확인, Gemini와 비교

### Phase 2: UI + 데이터 (1~2주)
- [ ] Streamlit 대시보드 (기존 목업 기반)
- [ ] 구글 시트 연동 (키워드·상품정보 읽기)
- [ ] SQLite 로컬 캐시 + 발행 큐
- [ ] 글 미리보기 + 수정 (st.form 활용)
- **목표**: 편하게 검토할 수 있는 환경

### Phase 3: 발행 자동화 (2~3주)
- [ ] undetected-chromedriver 네이버 로그인
- [ ] 스마트에디터 글 삽입 (클립보드 방식)
- [ ] ADB 비행기모드 토글 (Android 12+ 호환)
- [ ] 에러 복구 + 재시도 로직
- [ ] 발행 결과 구글 시트 기록
- **목표**: 버튼 하나로 발행되는 구조

### Phase 4: 안정화 + 확장 (지속)
- [ ] 발행 간격 랜덤화 고도화
- [ ] APScheduler로 예약 글 생성
- [ ] 에러 로그 + 스크린샷 자동 저장
- [ ] 프롬프트 A/B 테스트 기능
- [ ] 네이버 정책 변경 대응
- **목표**: 매일 안정적 운영 + 지속적 개선

---

## 수정된 필요 패키지 (requirements.txt)

```
streamlit==1.40.0              # 웹 UI (유지)
openai==1.60.0                 # ★ GPT-4o + 이미지 생성 (추가)
undetected-chromedriver==3.5.5 # 봇 탐지 우회 (유지)
gspread==6.1.0                 # 구글 시트 (유지)
oauth2client==4.1.3            # 구글 인증 (유지)
pyperclip==1.9.0               # 클립보드 (유지)
Pillow==10.4.0                 # 이미지 처리 (유지)
requests==2.32.0               # HTTP 요청 (유지)
pyyaml==6.0.2                  # 설정 파일 (유지)
peewee==3.17.0                 # ★ SQLite ORM (추가)
apscheduler==3.10.4            # ★ 스케줄러 (추가)
```

---

## 리스크 및 대응 (업데이트)

| 리스크 | 확률 | 기존 대응 | 추가 대응 |
|-------|------|----------|----------|
| 네이버 봇 탐지 강화 | 높음 | 랜덤 딜레이 + 프로필 분리 | **nodriver/SeleniumBase UC Mode 백업 + 발행 간격 60~180초로 확대** |
| AI 글 품질 부족 | 중간 | Gemini 무료 | **GPT-4o 업그레이드 옵션, 프롬프트 A/B 테스트** |
| 이미지 서비스 중단 | 낮음 | SD 로컬 대체 | **GPT Image + Pollinations 듀얼 체제로 한쪽 죽어도 무중단** |
| ADB 비행기모드 제한 | 중간 | Tasker 대체 | **Android 버전 자동 감지 + 구형/신형 명령어 분기** |
| 발행 중 에러 | 높음 | 없음 | **자동 재시도 2회 + 스크린샷 저장 + 수동 처리 큐** |
| 계정 제재 | 중간 | IP 변경 | **블로그 간 60~180초 랜덤 대기 + 글 패턴 변주** |
| 구글 시트 접속 불가 | 낮음 | 없음 | **SQLite 로컬 캐시로 오프라인 발행 가능** |

---

## 결론: 뭐가 바뀌었나 한 줄 요약

**기존 계획의 뼈대(구글 시트 + Streamlit + 폴더 구조 + 프롬프트 + 발행 워크플로우)는 그대로 살리고, AI 모델(GPT-4o-mini/4o), 이미지(GPT Image 1 Mini), ADB 명령어, 에러 복구 로직만 업그레이드했다.** 월 비용 0원 → 2~2.5만원으로 소폭 증가하지만, 글·이미지 품질과 시스템 안정성이 크게 향상된다.
