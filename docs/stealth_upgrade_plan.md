# 브라우저 자동화 스텔스 업그레이드 계획서

> 총 6단계. 각 단계는 독립적으로 적용·테스트 가능하도록 설계됨.
> 각 BATCH를 복사해서 Claude에게 붙여넣으면 해당 작업만 수행됨.

---

## 변경 대상 파일 요약

| 단계 | 수정 파일 | 신규 파일 | config.yaml 변경 |
|---|---|---|---|
| BATCH 1 | `blog_publisher.py` | — | — |
| BATCH 2 | `blog_publisher.py` | — | warmup 설정 추가 |
| BATCH 3 | `blog_publisher.py` | — | — |
| BATCH 4 | — | `modules/human_mouse.py` | — |
| BATCH 4-B | `blog_publisher.py` | — | — |
| BATCH 5 | `pages/4_🚀_발행.py` | — | schedule 설정 추가 |
| BATCH 6 | — | `modules/adaptive_selector.py` | selectors 설정 추가 |
| BATCH 6-B | `blog_publisher.py` | — | — |

---

## BATCH 1 — 딜레이 분포를 가우시안으로 변경

### 목적
현재 `random.uniform(min, max)` 균등분포 → 가우시안(정규분포)로 변경.
사람의 반응시간은 정규분포에 가까우므로 봇 패턴 탐지를 어렵게 만듦.

### 변경 범위
- `modules/blog_publisher.py` — `_wait()` 메서드 1개만 수정

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
blog_publisher.py의 _wait() 메서드를 다음과 같이 수정해줘:

현재:
  def _wait(self, delay_range: tuple):
      delay = random.uniform(*delay_range)
      time.sleep(delay)

변경:
  def _wait(self, delay_range: tuple):
      min_val, max_val = delay_range
      mean = (min_val + max_val) / 2
      sigma = (max_val - min_val) / 4
      delay = random.gauss(mean, sigma)
      delay = max(min_val, min(max_val, delay))
      time.sleep(delay)

원리:
- mean = 범위의 중앙값, sigma = 범위의 1/4 (95%가 범위 내에 들어옴)
- clamp로 min~max 범위를 벗어나지 않도록 보장
- config.yaml의 action_delay [1.5, 4.0] 설정은 그대로 유지

수정 후 RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### 검증 방법
- 앱 실행 후 발행 시 딜레이가 중앙값(2.75초) 부근에 집중되는지 로그 확인
- 기존 동작과 체감 차이 거의 없음 (내부 분포만 변경)

---

## BATCH 2 — 세션 워밍업

### 목적
발행 직전 네이버 메인→블로그 홈을 방문하여 자연스러운 브라우징 세션을 만듦.
실제 사람은 에디터를 바로 열지 않고, 메인 페이지를 거쳐감.

### 변경 범위
- `modules/blog_publisher.py` — 새 메서드 `_warmup_session()` 추가 + `publish_single()`에서 호출
- `config.yaml` — `publish.warmup` 설정 추가

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
blog_publisher.py에 세션 워밍업 기능을 추가해줘.

1. config.yaml의 publish 섹션에 다음 추가:
   warmup:
     enabled: true
     pages:
       - https://www.naver.com
       - https://blog.naver.com/{blog_id}

2. BlogPublisher.__init__()에서 warmup 설정을 읽도록 추가:
   warmup_config = publish_config.get("warmup", {})
   self.warmup_enabled = warmup_config.get("enabled", True)
   self.warmup_pages = warmup_config.get("pages", [
       "https://www.naver.com",
       "https://blog.naver.com/{blog_id}",
   ])

3. 새 메서드 _warmup_session(blog_id) 추가:
   위치: _open_editor() 바로 위 (에디터 관련 섹션)

   def _warmup_session(self, blog_id: str):
       if not self.warmup_enabled:
           return
       for url_template in self.warmup_pages:
           url = url_template.format(blog_id=blog_id)
           try:
               self.driver.get(url)
               self._action_wait()
               # 페이지 로드 후 약간의 스크롤 (사람처럼)
               self.driver.execute_script(
                   "window.scrollTo(0, Math.random() * 300 + 100);"
               )
               time.sleep(random.uniform(1.0, 2.5))
           except Exception:
               logger.debug("워밍업 페이지 로드 실패 (무시): %s", url)
       logger.info("세션 워밍업 완료: %s", blog_id)

4. publish_single() 메서드의 "# 2. 로그인" 성공 후, "# 3. 에디터 열기" 전에 호출 추가:
   기존: self._action_wait() 후 바로 _open_editor()
   변경: self._action_wait() 후 self._warmup_session(blog_id) 추가, 그다음 _open_editor()

수정 후 RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### 검증 방법
- 발행 시 로그에 "세션 워밍업 완료" 메시지 확인
- 네이버 메인 → 블로그 홈 → 에디터 순서로 접속되는지 확인
- `warmup.enabled: false`로 끌 수 있는지 확인

---

## BATCH 3 — 스크롤 행동 추가

### 목적
에디터 페이지 로드 후 바로 입력하지 않고, 스크롤과 멈춤을 넣어 사람의 "페이지 훑어보기" 행동을 모방.

### 변경 범위
- `modules/blog_publisher.py` — 새 메서드 `_human_scroll()` 추가 + `_open_editor()`, `_insert_body_html()` 후에 호출

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
blog_publisher.py에 사람처럼 스크롤하는 기능을 추가해줘.

1. 새 메서드 _human_scroll() 추가:
   위치: _action_wait() 아래, 브라우저 관리 섹션 위

   def _human_scroll(self, direction: str = "down", intensity: str = "light"):
       """사람처럼 자연스러운 스크롤 동작"""
       try:
           if intensity == "light":
               distance = random.randint(100, 300)
           else:
               distance = random.randint(300, 600)

           if direction == "up":
               distance = -distance

           # 2~3회에 나눠서 스크롤 (사람은 한번에 정확히 스크롤하지 않음)
           steps = random.randint(2, 3)
           for _ in range(steps):
               partial = distance // steps + random.randint(-20, 20)
               self.driver.execute_script(f"window.scrollBy(0, {partial});")
               time.sleep(random.uniform(0.1, 0.3))

           time.sleep(random.uniform(0.3, 0.8))
       except Exception:
           pass  # 스크롤 실패는 무시

2. _open_editor() 수정:
   기존 마지막 부분:
       logger.info("에디터 열기 성공: %s", blog_id)
       return True

   변경 (logger.info 바로 위에 추가):
       self._human_scroll("down", "light")
       logger.info("에디터 열기 성공: %s", blog_id)
       return True

3. _insert_body_html() 수정:
   기존 마지막 부분:
       logger.info("본문 입력 완료 (길이: %d)", len(body_html))
       return True

   변경 (logger.info 바로 위에 추가):
       self._human_scroll("down", "light")
       logger.info("본문 입력 완료 (길이: %d)", len(body_html))
       return True

수정 후 RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### 검증 방법
- 발행 시 에디터 열린 후 약간의 스크롤 동작이 보이는지 육안 확인
- 본문 입력 후에도 자연스러운 스크롤이 발생하는지 확인
- 발행 실패가 발생하지 않는지 확인 (스크롤 실패는 무시되므로 안전)

---

## BATCH 4 — 마우스 궤적 (Bezier Curve)

> 2개 파트로 나뉨: 4(헬퍼 생성) → 4-B(적용)

### 목적
요소 클릭 시 마우스가 순간이동하는 대신, 베지어 곡선을 따라 자연스럽게 이동 후 클릭.
네이버가 마우스 이벤트 패턴을 수집한다면 가장 효과적인 우회.

### BATCH 4 — 헬퍼 파일 생성

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
modules/human_mouse.py 파일을 새로 생성해줘. 내용은 다음과 같아:

목적: Selenium ActionChains로 베지어 곡선 마우스 이동을 구현하는 유틸리티.
blog_publisher.py에서 import해서 사용할 예정.

요구사항:
- 외부 라이브러리 추가 없이 순수 Python + Selenium만 사용
- ActionChains의 move_by_offset()을 반복 호출하여 곡선 이동 구현

파일 내용:

import random
import time
from selenium.webdriver.common.action_chains import ActionChains


def bezier_point(t: float, p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> tuple:
    """3차 베지어 곡선 위의 점 계산"""
    u = 1 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


def human_move_to_element(driver, element, duration: float = 0.0):
    """
    현재 마우스 위치에서 element까지 베지어 곡선으로 자연스럽게 이동.

    Args:
        driver: Selenium WebDriver
        element: 이동 대상 요소
        duration: 미사용 (호환성), 실제 시간은 steps에 의해 결정
    """
    # 요소의 화면 내 위치
    rect = element.rect
    target_x = rect["x"] + rect["width"] / 2
    target_y = rect["y"] + rect["height"] / 2

    # 현재 뷰포트 크기 기준으로 시작점 추정 (정확한 마우스 위치는 알 수 없으므로)
    viewport_w = driver.execute_script("return window.innerWidth;")
    viewport_h = driver.execute_script("return window.innerHeight;")
    start_x = random.uniform(viewport_w * 0.3, viewport_w * 0.7)
    start_y = random.uniform(viewport_h * 0.3, viewport_h * 0.7)

    # 시작→타겟 사이에 랜덤 제어점 2개 (곡선의 휘어짐 정도)
    dx = target_x - start_x
    dy = target_y - start_y
    cp1 = (
        start_x + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
        start_y + dy * random.uniform(0.0, 0.3) + random.uniform(-50, 50),
    )
    cp2 = (
        start_x + dx * random.uniform(0.6, 0.8) + random.uniform(-30, 30),
        start_y + dy * random.uniform(0.7, 1.0) + random.uniform(-30, 30),
    )

    # 경로 생성 (15~25 스텝)
    steps = random.randint(15, 25)
    points = []
    for i in range(steps + 1):
        t = i / steps
        # ease-in-out 보간 (사람은 시작/끝에서 느림)
        t = t * t * (3 - 2 * t)
        points.append(bezier_point(t, (start_x, start_y), cp1, cp2, (target_x, target_y)))

    # ActionChains로 이동 실행
    actions = ActionChains(driver)
    # 먼저 시작점으로 이동 (body 기준)
    actions.move_to_element_with_offset(
        driver.find_element("tag name", "body"),
        int(start_x), int(start_y)
    )

    prev = (start_x, start_y)
    for point in points[1:]:
        offset_x = int(point[0] - prev[0])
        offset_y = int(point[1] - prev[1])
        if offset_x != 0 or offset_y != 0:
            actions.move_by_offset(offset_x, offset_y)
            actions.pause(random.uniform(0.01, 0.03))
        prev = point

    actions.perform()
    time.sleep(random.uniform(0.05, 0.15))


def human_click(driver, element):
    """베지어 이동 후 클릭"""
    try:
        human_move_to_element(driver, element)
        element.click()
    except Exception:
        # 베지어 이동 실패 시 일반 클릭으로 폴백
        element.click()

RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### BATCH 4-B — blog_publisher.py에 적용

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
blog_publisher.py에 human_mouse를 적용해줘.

1. import 추가 (파일 상단, 기존 import 블록의 마지막에):
   from modules.human_mouse import human_click

2. 다음 메서드들에서 element.click()을 human_click(self.driver, element)로 교체:

   대상 메서드와 교체 위치:
   a) _login_with_pyperclip():
      - id_input.click()  →  human_click(self.driver, id_input)
      - pw_input.click()  →  human_click(self.driver, pw_input)
      - login_btn.click() →  human_click(self.driver, login_btn)

   b) _insert_title():
      - title_area.click() →  human_click(self.driver, title_area)

   c) _insert_body_html():
      - body_area.click()  →  human_click(self.driver, body_area)

   d) _insert_tags():
      - tag_input.click()  →  human_click(self.driver, tag_input)

   e) _click_publish():
      - publish_btn.click() →  human_click(self.driver, publish_btn)

   주의: _insert_image()의 img_btn.click()과 file_input.send_keys()는 변경하지 않음.
         파일 업로드 다이얼로그는 마우스 궤적이 불필요하고 오히려 방해됨.

   주의: confirm_btn.click()도 변경하지 않음.
         확인 다이얼로그는 빠르게 클릭하는 게 자연스러움.

수정 후 RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### 검증 방법
- 발행 시 마우스가 곡선으로 이동하는 것이 육안으로 보임
- 클릭 실패 시 일반 click()으로 자동 폴백되므로 안전
- 이미지 첨부/확인 다이얼로그는 기존 방식 유지

---

## BATCH 5 — 발행 시간 분산

### 목적
매일 같은 시간대에 집중 발행하면 패턴으로 탐지됨.
발행 시작 시각에 랜덤 오프셋을 추가하여 분산시킴.

### 변경 범위
- `pages/4_🚀_발행.py` — 예약 발행 UI 및 시간 분산 로직 추가
- `config.yaml` — `publish.schedule` 설정 추가

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
발행 시간 분산 기능을 추가해줘.

1. config.yaml의 publish 섹션에 다음 추가:
   schedule:
     time_jitter_minutes: 30

2. pages/4_🚀_발행.py 수정:

   a) 발행 설정 expander 안 (⚙️ 발행 설정) 에 시간 분산 옵션 추가.
      기존 col_s1, col_s2, col_s3 아래에 새 행 추가:

      col_s4, col_s5, _ = st.columns(3)
      with col_s4:
          schedule_config = config.get("publish", {}).get("schedule", {})
          time_jitter = st.number_input(
              "시간 분산 (분)",
              value=schedule_config.get("time_jitter_minutes", 30),
              min_value=0,
              max_value=120,
              help="발행 시작 전 0~N분 랜덤 대기. 매번 다른 시간에 발행되어 패턴 탐지를 회피.",
              key="time_jitter",
          )

   b) 발행 프로세스 실행 블록 (if publish_clicked and selected_count > 0:) 시작 직후,
      articles_to_publish 쿼리 뒤, st.divider() 전에 시간 분산 대기 삽입:

      # 시간 분산 대기
      if time_jitter > 0:
          jitter_seconds = random.randint(0, time_jitter * 60)
          jitter_minutes = jitter_seconds // 60
          jitter_remain = jitter_seconds % 60
          st.markdown(
              f'<div class="delay-banner">'
              f'🎲 시간 분산: {jitter_minutes}분 {jitter_remain}초 대기 후 발행 시작'
              f'</div>',
              unsafe_allow_html=True,
          )
          jitter_bar = st.progress(0, text=f"시간 분산 대기 중... {jitter_seconds}초")
          for sec in range(jitter_seconds):
              remaining = jitter_seconds - sec - 1
              jitter_bar.progress(
                  (sec + 1) / jitter_seconds,
                  text=f"시간 분산 대기 중... {remaining}초 남음",
              )
              time.sleep(1)
          jitter_bar.progress(1.0, text="시간 분산 대기 완료!")

수정 후 RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### 검증 방법
- 발행 시작 시 "시간 분산: N분 M초 대기" 배너가 표시되는지 확인
- 분산값 0으로 설정 시 대기 없이 바로 발행되는지 확인
- 프로그레스 바가 정상 동작하는지 확인

---

## BATCH 6 — 적응형 셀렉터

> 2개 파트로 나뉨: 6(모듈 생성) → 6-B(적용)
> 이 단계는 Scrapling 라이브러리를 사용하지 않고 자체 구현.
> Scrapling의 컨셉만 차용하여 가볍게 구현 (외부 의존성 없음).

### 목적
네이버 스마트에디터의 CSS 셀렉터가 변경되면 발행이 실패함.
셀렉터 매칭 실패 시 저장된 요소 특성(태그, 위치, 속성)으로 유사 요소를 자동 탐색.

### BATCH 6 — 적응형 셀렉터 모듈 생성

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
modules/adaptive_selector.py 파일을 새로 생성해줘.

목적:
CSS 셀렉터로 요소를 못 찾을 때, 이전에 저장된 요소 특성(태그, 텍스트, 속성, 위치)을
기반으로 가장 유사한 요소를 찾아주는 모듈.
blog_publisher.py에서 WebDriverWait 대신 사용할 예정.

요구사항:
- 외부 라이브러리 없이 Selenium만 사용
- 셀렉터 캐시는 JSON 파일로 저장 (data/selector_cache.json)
- 유사도 점수 기반 매칭 (태그명, 속성, innerText 일부, 화면 위치)

파일 구조:

import json
import logging
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

CACHE_PATH = Path("./data/selector_cache.json")
SIMILARITY_THRESHOLD = 0.6


class ElementSignature:
    """요소의 고유 특성을 저장하는 데이터 클래스"""

    def __init__(self, tag: str, attrs: dict, text_hint: str,
                 rect: dict, css_selector: str):
        self.tag = tag
        self.attrs = attrs           # {"class": "...", "id": "...", "placeholder": "..."}
        self.text_hint = text_hint   # innerText 앞 50자
        self.rect = rect             # {"x": int, "y": int, "width": int, "height": int}
        self.css_selector = css_selector

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "attrs": self.attrs,
            "text_hint": self.text_hint,
            "rect": self.rect,
            "css_selector": self.css_selector,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ElementSignature":
        return cls(
            tag=d["tag"],
            attrs=d.get("attrs", {}),
            text_hint=d.get("text_hint", ""),
            rect=d.get("rect", {}),
            css_selector=d.get("css_selector", ""),
        )

    @classmethod
    def from_element(cls, element, css_selector: str) -> "ElementSignature":
        """Selenium WebElement에서 특성 추출"""
        tag = element.tag_name
        attrs = {}
        for attr_name in ["class", "id", "name", "placeholder", "data-name",
                          "data-testid", "type", "role"]:
            val = element.get_attribute(attr_name)
            if val:
                attrs[attr_name] = val
        text_hint = (element.text or "")[:50]
        rect = element.rect  # {"x", "y", "width", "height"}
        return cls(tag=tag, attrs=attrs, text_hint=text_hint,
                   rect=rect, css_selector=css_selector)


def _calc_similarity(sig: ElementSignature, candidate_sig: ElementSignature) -> float:
    """두 요소 서명의 유사도 계산 (0.0 ~ 1.0)"""
    score = 0.0
    max_score = 0.0

    # 1. 태그명 일치 (가중치 2.0)
    max_score += 2.0
    if sig.tag == candidate_sig.tag:
        score += 2.0

    # 2. 속성 일치 (가중치: 속성당 1.5)
    all_keys = set(sig.attrs.keys()) | set(candidate_sig.attrs.keys())
    if all_keys:
        for key in all_keys:
            max_score += 1.5
            v1 = sig.attrs.get(key, "")
            v2 = candidate_sig.attrs.get(key, "")
            if v1 and v2:
                # 클래스는 부분 일치 허용 (단어 단위)
                if key == "class":
                    words1 = set(v1.split())
                    words2 = set(v2.split())
                    if words1 and words2:
                        overlap = len(words1 & words2) / max(len(words1), len(words2))
                        score += 1.5 * overlap
                elif v1 == v2:
                    score += 1.5

    # 3. 텍스트 힌트 유사 (가중치 1.0)
    max_score += 1.0
    if sig.text_hint and candidate_sig.text_hint:
        if sig.text_hint in candidate_sig.text_hint or candidate_sig.text_hint in sig.text_hint:
            score += 1.0
        elif sig.text_hint[:20] == candidate_sig.text_hint[:20]:
            score += 0.5

    # 4. 화면 위치 근접도 (가중치 1.0)
    max_score += 1.0
    if sig.rect and candidate_sig.rect:
        dx = abs(sig.rect.get("x", 0) - candidate_sig.rect.get("x", 0))
        dy = abs(sig.rect.get("y", 0) - candidate_sig.rect.get("y", 0))
        distance = (dx ** 2 + dy ** 2) ** 0.5
        if distance < 50:
            score += 1.0
        elif distance < 150:
            score += 0.5
        elif distance < 300:
            score += 0.2

    return score / max_score if max_score > 0 else 0.0


class AdaptiveSelector:
    """CSS 셀렉터 실패 시 유사 요소를 자동으로 찾아주는 매니저"""

    def __init__(self, cache_path: Path = CACHE_PATH):
        self.cache_path = cache_path
        self.cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self):
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                self.cache = {}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def find_element(self, driver, css_selector: str, label: str,
                     timeout: int = 10):
        """
        요소를 찾고, 찾으면 서명을 캐시에 저장.
        CSS 셀렉터로 못 찾으면 캐시된 서명으로 유사 요소 탐색.

        Args:
            driver: Selenium WebDriver
            css_selector: 기본 CSS 셀렉터
            label: 캐시 키 (예: "title_area", "body_area")
            timeout: 대기 시간 (초)

        Returns:
            WebElement 또는 None
        """
        # 1차: 원래 셀렉터로 시도
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
            # 성공 → 서명 저장
            sig = ElementSignature.from_element(element, css_selector)
            self.cache[label] = sig.to_dict()
            self._save_cache()
            logger.debug("셀렉터 매칭 성공 (캐시 갱신): %s → %s", label, css_selector)
            return element
        except Exception:
            logger.warning("셀렉터 매칭 실패: %s → %s", label, css_selector)

        # 2차: 캐시된 서명으로 유사 요소 탐색
        if label not in self.cache:
            logger.error("캐시에 서명 없음, 탐색 불가: %s", label)
            return None

        saved_sig = ElementSignature.from_dict(self.cache[label])
        logger.info("적응형 탐색 시작: %s (태그=%s)", label, saved_sig.tag)

        # 같은 태그의 모든 요소 수집
        try:
            candidates = driver.find_elements(By.TAG_NAME, saved_sig.tag)
        except Exception:
            return None

        best_element = None
        best_score = 0.0

        for candidate in candidates:
            try:
                candidate_sig = ElementSignature.from_element(candidate, "")
                score = _calc_similarity(saved_sig, candidate_sig)
                if score > best_score:
                    best_score = score
                    best_element = candidate
            except Exception:
                continue

        if best_element and best_score >= SIMILARITY_THRESHOLD:
            logger.info(
                "적응형 매칭 성공: %s (유사도=%.2f, 임계값=%.2f)",
                label, best_score, SIMILARITY_THRESHOLD,
            )
            # 새로 찾은 요소로 캐시 갱신
            new_sig = ElementSignature.from_element(best_element, css_selector)
            self.cache[label] = new_sig.to_dict()
            self._save_cache()
            return best_element

        logger.error(
            "적응형 매칭 실패: %s (최고 유사도=%.2f < 임계값=%.2f)",
            label, best_score, SIMILARITY_THRESHOLD,
        )
        return None

RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### BATCH 6-B — blog_publisher.py에 적용

### 작업 지시 (이 블록을 복사하여 붙여넣기)

```
blog_publisher.py에 AdaptiveSelector를 적용해줘.

1. import 추가 (파일 상단):
   from modules.adaptive_selector import AdaptiveSelector

2. __init__()에 adaptive_selector 인스턴스 생성 추가:
   self.driver = None 아래에:
   self.selector = AdaptiveSelector()

3. 다음 메서드들에서 WebDriverWait → self.selector.find_element()로 교체:

   a) _open_editor():
      기존:
          WebDriverWait(self.driver, 15).until(
              EC.presence_of_element_located(
                  (By.CSS_SELECTOR, ".se-component-content, .blog_editor, iframe[id*='editor']")
              )
          )

      변경:
          element = self.selector.find_element(
              self.driver,
              ".se-component-content, .blog_editor, iframe[id*='editor']",
              "editor_container",
              timeout=15,
          )
          if not element:
              raise Exception("에디터 컨테이너를 찾을 수 없음")

   b) _insert_title():
      기존:
          title_area = WebDriverWait(self.driver, 10).until(
              EC.presence_of_element_located(
                  (By.CSS_SELECTOR, ".se-documentTitle .se-text-paragraph, .se-title-text")
              )
          )

      변경:
          title_area = self.selector.find_element(
              self.driver,
              ".se-documentTitle .se-text-paragraph, .se-title-text",
              "title_area",
          )
          if not title_area:
              raise Exception("제목 영역을 찾을 수 없음")

   c) _insert_body_html():
      기존:
          body_area = WebDriverWait(self.driver, 10).until(
              EC.presence_of_element_located(
                  (By.CSS_SELECTOR, ".se-component-content .se-text-paragraph")
              )
          )

      변경:
          body_area = self.selector.find_element(
              self.driver,
              ".se-component-content .se-text-paragraph",
              "body_area",
          )
          if not body_area:
              raise Exception("본문 영역을 찾을 수 없음")

   d) _insert_image():
      기존:
          img_btn = WebDriverWait(self.driver, 10).until(
              EC.element_to_be_clickable(
                  (By.CSS_SELECTOR, ".se-toolbar-button-image, button[data-name='image']")
              )
          )

      변경:
          img_btn = self.selector.find_element(
              self.driver,
              ".se-toolbar-button-image, button[data-name='image']",
              "image_button",
          )
          if not img_btn:
              raise Exception("이미지 버튼을 찾을 수 없음")

      주의: file_input은 적응형 셀렉터를 적용하지 않음.
            input[type='file']은 숨겨진 요소라 위치/크기 서명이 무의미.

   e) _insert_tags():
      기존:
          tag_input = WebDriverWait(self.driver, 10).until(
              EC.presence_of_element_located(
                  (By.CSS_SELECTOR, ".tag_input input, input[placeholder*='태그']")
              )
          )

      변경:
          tag_input = self.selector.find_element(
              self.driver,
              ".tag_input input, input[placeholder*='태그']",
              "tag_input",
          )
          if not tag_input:
              raise Exception("태그 입력 영역을 찾을 수 없음")

   f) _click_publish():
      기존:
          publish_btn = WebDriverWait(self.driver, 10).until(
              EC.element_to_be_clickable(
                  (By.CSS_SELECTOR, ".publish_btn__Y5mLP, button.se-publish-button")
              )
          )

      변경:
          publish_btn = self.selector.find_element(
              self.driver,
              ".publish_btn__Y5mLP, button.se-publish-button",
              "publish_button",
          )
          if not publish_btn:
              raise Exception("발행 버튼을 찾을 수 없음")

      주의: confirm_btn (확인 다이얼로그)은 적응형 셀렉터를 적용하지 않음.
            다이얼로그는 항상 같은 구조이고, 없을 수도 있어서 try/except가 더 적합.

수정 후 RULES.md 자동 문서 갱신 기준에 따라 갱신 여부 판단.
프로그램 수정만 해. 추가 질문 없이 바로 수행.
```

### 검증 방법
- 첫 발행 성공 시 `data/selector_cache.json`에 요소 서명이 저장되는지 확인
- 로그에 "셀렉터 매칭 성공 (캐시 갱신)" 메시지 확인
- (테스트) 존재하지 않는 셀렉터로 변경 후 "적응형 탐색 시작" → "적응형 매칭 성공" 로그가 나오는지 확인

---

## 단계별 적용 후 예상 효과

| 단계 | 적용 후 | 제재 위험 감소 | 작업 시간 |
|---|---|---|---|
| BATCH 1 (가우시안 딜레이) | 딜레이 패턴이 사람과 유사 | 낮음 → 더 낮음 | 5분 |
| BATCH 2 (세션 워밍업) | 자연스러운 브라우징 세션 | 중간 효과 | 10분 |
| BATCH 3 (스크롤 행동) | 페이지 탐색 행동 모방 | 낮은 효과 | 10분 |
| BATCH 4 (마우스 궤적) | 마우스 이동이 사람처럼 | 중간 효과 | 15분 |
| BATCH 5 (시간 분산) | 발행 시각 패턴 제거 | 중간 효과 | 10분 |
| BATCH 6 (적응형 셀렉터) | 에디터 변경 시 자동 대응 | 안정성 향상 | 20분 |

---

## 롤백 방법

각 BATCH는 독립적이므로 git에서 해당 커밋만 revert 가능.
권장: 각 BATCH 적용 후 커밋하여 개별 롤백 가능하도록 유지.

```bash
# 예: BATCH 3만 롤백
git log --oneline  # 커밋 해시 확인
git revert <해당 커밋 해시>
```
