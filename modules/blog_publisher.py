"""
네이버 블로그 발행 모듈

- undetected-chromedriver로 봇 탐지 우회
- 쿠키 기반 로그인 (없으면 pyperclip으로 아이디/비번 입력 → 쿠키 저장)
- 스마트에디터에 클립보드(HTML)로 글 삽입
- 발행 실패 시 스크린샷 저장 + 재시도
- Chrome 프로필 분리 (계정별)
"""

import json
import logging
import os
import random
import time
from pathlib import Path

import pyperclip
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


class PublishResult:
    """발행 결과 상태 상수"""
    SUCCESS = "성공"
    LOGIN_FAIL = "로그인실패"
    EDITOR_FAIL = "에디터실패"
    PUBLISH_FAIL = "발행실패"
    NETWORK_FAIL = "네트워크실패"


class BlogPublisher:
    """네이버 블로그 발행 자동화"""

    NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
    NAVER_BLOG_EDITOR_URL = "https://blog.naver.com/{blog_id}/postwrite"
    NAVER_MAIN_URL = "https://www.naver.com"

    def __init__(self, config: dict):
        """
        Args:
            config: config.yaml 전체 딕셔너리
        """
        self.config = config
        publish_config = config.get("publish", {})
        paths_config = config.get("paths", {})

        self.inter_blog_delay = tuple(publish_config.get("inter_blog_delay", [60, 180]))
        self.inter_post_delay = tuple(publish_config.get("inter_post_delay", [30, 90]))
        self.action_delay = tuple(publish_config.get("action_delay", [1.5, 4.0]))
        self.max_retries = publish_config.get("max_retries", 2)

        warmup_config = publish_config.get("warmup", {})
        self.warmup_enabled = warmup_config.get("enabled", True)
        self.warmup_pages = warmup_config.get("pages", [
            "https://www.naver.com",
            "https://blog.naver.com/{blog_id}",
        ])

        self.cookie_dir = Path(paths_config.get("cookie_dir", "./data/cookies"))
        self.chrome_profiles_dir = Path(
            paths_config.get("chrome_profiles_dir", "./chrome_profiles")
        )
        self.log_dir = Path(paths_config.get("log_dir", "./logs"))
        self.screenshot_dir = self.log_dir / "error_screenshots"

        # 디렉토리 생성
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.chrome_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        self.driver = None

    # ──────────────────────────────────────────────
    # 랜덤 딜레이
    # ──────────────────────────────────────────────

    def _wait(self, delay_range: tuple):
        """가우시안 분포 랜덤 대기 (사람의 반응시간에 근사)"""
        min_val, max_val = delay_range
        mean = (min_val + max_val) / 2
        sigma = (max_val - min_val) / 4
        delay = random.gauss(mean, sigma)
        delay = max(min_val, min(max_val, delay))
        time.sleep(delay)

    def _action_wait(self):
        """에디터 내 액션 간 짧은 대기"""
        self._wait(self.action_delay)

    def _human_scroll(self, direction: str = "down", intensity: str = "light"):
        """사람처럼 자연스러운 스크롤 동작"""
        try:
            if intensity == "light":
                distance = random.randint(100, 300)
            else:
                distance = random.randint(300, 600)

            if direction == "up":
                distance = -distance

            steps = random.randint(2, 3)
            for _ in range(steps):
                partial = distance // steps + random.randint(-20, 20)
                self.driver.execute_script(f"window.scrollBy(0, {partial});")
                time.sleep(random.uniform(0.1, 0.3))

            time.sleep(random.uniform(0.3, 0.8))
        except Exception:
            logger.debug("스크롤 실패 (무시)")

    # ──────────────────────────────────────────────
    # 브라우저 관리
    # ──────────────────────────────────────────────

    def _create_driver(self, blog_id: str) -> uc.Chrome:
        """계정별 Chrome 프로필로 브라우저 생성"""
        profile_dir = self.chrome_profiles_dir / blog_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=ko-KR")

        driver = uc.Chrome(options=options, version_main=None)
        driver.set_window_size(1280, 900)
        return driver

    def _quit_driver(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ──────────────────────────────────────────────
    # 쿠키 관리
    # ──────────────────────────────────────────────

    def _cookie_path(self, blog_id: str) -> Path:
        return self.cookie_dir / f"{blog_id}_cookies.json"

    def _save_cookies(self, blog_id: str):
        """현재 브라우저 쿠키를 파일로 저장"""
        cookies = self.driver.get_cookies()
        cookie_file = self._cookie_path(blog_id)
        cookie_file.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
        logger.info("쿠키 저장: %s (%d개)", cookie_file.name, len(cookies))

    def _load_cookies(self, blog_id: str) -> bool:
        """저장된 쿠키 로드 → 브라우저에 적용"""
        cookie_file = self._cookie_path(blog_id)
        if not cookie_file.exists():
            return False

        try:
            cookies = json.loads(cookie_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            logger.warning("쿠키 파일 손상: %s", cookie_file)
            return False

        # 네이버 도메인에 쿠키 적용하기 위해 먼저 방문
        self.driver.get(self.NAVER_MAIN_URL)
        time.sleep(2)

        for cookie in cookies:
            # 쿠키 호환성을 위해 sameSite 등 제거
            cookie.pop("sameSite", None)
            cookie.pop("storeId", None)
            cookie.pop("id", None)
            try:
                self.driver.add_cookie(cookie)
            except Exception:
                continue

        logger.info("쿠키 로드: %s (%d개)", cookie_file.name, len(cookies))
        return True

    def _delete_cookies(self, blog_id: str):
        """쿠키 파일 삭제"""
        cookie_file = self._cookie_path(blog_id)
        if cookie_file.exists():
            cookie_file.unlink()
            logger.info("쿠키 삭제: %s", cookie_file.name)

    # ──────────────────────────────────────────────
    # 로그인
    # ──────────────────────────────────────────────

    def _is_logged_in(self) -> bool:
        """네이버 로그인 상태 확인"""
        try:
            self.driver.get(self.NAVER_MAIN_URL)
            time.sleep(2)
            # 로그인 버튼이 없으면 로그인 상태
            login_btns = self.driver.find_elements(By.CSS_SELECTOR, ".MyView-module__link_login___HpHMW")
            if login_btns:
                return False
            # 또는 로그아웃 링크가 있는지 확인
            return True
        except Exception:
            return False

    def _login_with_pyperclip(self, naver_id: str, naver_pw: str) -> bool:
        """
        pyperclip을 이용한 로그인 (복붙 방식으로 봇 탐지 우회)
        키보드 직접 입력 대신 클립보드를 사용한다.
        """
        try:
            self.driver.get(self.NAVER_LOGIN_URL)
            time.sleep(3)

            # 아이디 입력 (클립보드)
            id_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#id"))
            )
            id_input.click()
            self._action_wait()

            pyperclip.copy(naver_id)
            id_input.send_keys(Keys.CONTROL, "v")
            self._action_wait()

            # 비밀번호 입력 (클립보드)
            pw_input = self.driver.find_element(By.CSS_SELECTOR, "#pw")
            pw_input.click()
            self._action_wait()

            pyperclip.copy(naver_pw)
            pw_input.send_keys(Keys.CONTROL, "v")
            self._action_wait()

            # 로그인 버튼 클릭
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "#log\\.login")
            login_btn.click()
            time.sleep(5)

            # 캡챠/2차 인증 대기 (수동 처리 필요할 수 있음)
            # 로그인 성공 여부 확인 (URL이 로그인 페이지가 아니면 성공)
            if "nidlogin" not in self.driver.current_url:
                logger.info("로그인 성공: %s", naver_id)
                return True

            logger.warning("로그인 실패 (캡챠 또는 인증 필요): %s", naver_id)
            return False

        except Exception as e:
            logger.error("로그인 중 오류: %s", e)
            return False

    def login(self, blog_id: str, naver_id: str, naver_pw: str) -> bool:
        """
        쿠키 우선 로그인 → 실패 시 pyperclip 로그인 → 성공하면 쿠키 저장

        Returns:
            로그인 성공 여부
        """
        # 1. 쿠키로 로그인 시도
        if self._load_cookies(blog_id):
            if self._is_logged_in():
                logger.info("쿠키 로그인 성공: %s", blog_id)
                return True
            logger.info("쿠키 만료, 재로그인 필요: %s", blog_id)

        # 2. pyperclip 로그인
        if self._login_with_pyperclip(naver_id, naver_pw):
            self._save_cookies(blog_id)
            return True

        return False

    # ──────────────────────────────────────────────
    # 세션 워밍업
    # ──────────────────────────────────────────────

    def _warmup_session(self, blog_id: str):
        """발행 전 자연스러운 브라우징 세션 생성"""
        if not self.warmup_enabled:
            return
        for url_template in self.warmup_pages:
            url = url_template.format(blog_id=blog_id)
            try:
                self.driver.get(url)
                self._action_wait()
                self.driver.execute_script(
                    "window.scrollTo(0, Math.random() * 300 + 100);"
                )
                self._action_wait()
            except Exception:
                logger.debug("워밍업 페이지 로드 실패 (무시): %s", url)
        logger.info("세션 워밍업 완료: %s", blog_id)

    # ──────────────────────────────────────────────
    # 스마트에디터 글 작성
    # ──────────────────────────────────────────────

    def _open_editor(self, blog_id: str) -> bool:
        """블로그 에디터 페이지 열기"""
        try:
            editor_url = self.NAVER_BLOG_EDITOR_URL.format(blog_id=blog_id)
            self.driver.get(editor_url)
            time.sleep(5)

            # 에디터 iframe으로 전환될 수 있음
            # 스마트에디터 로딩 대기
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".se-component-content, .blog_editor, iframe[id*='editor']")
                )
            )
            self._human_scroll("down", "light")
            logger.info("에디터 열기 성공: %s", blog_id)
            return True
        except Exception as e:
            logger.error("에디터 열기 실패: %s", e)
            return False

    def _insert_title(self, title: str) -> bool:
        """제목 입력"""
        try:
            # 스마트에디터 제목 영역
            title_area = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".se-documentTitle .se-text-paragraph, .se-title-text")
                )
            )
            title_area.click()
            self._action_wait()

            # 클립보드로 제목 입력
            pyperclip.copy(title)
            title_area.send_keys(Keys.CONTROL, "a")
            time.sleep(0.3)
            title_area.send_keys(Keys.CONTROL, "v")
            self._action_wait()

            logger.info("제목 입력 완료: %s", title[:30])
            return True
        except Exception as e:
            logger.error("제목 입력 실패: %s", e)
            return False

    def _insert_body_html(self, body_html: str) -> bool:
        """
        본문 HTML 삽입 (클립보드 방식)
        스마트에디터의 HTML 모드 또는 클립보드 붙여넣기를 이용한다.
        """
        try:
            # 본문 편집 영역 클릭
            body_area = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".se-component-content .se-text-paragraph")
                )
            )
            body_area.click()
            self._action_wait()

            # HTML을 클립보드에 복사 후 붙여넣기
            pyperclip.copy(body_html)
            body_area.send_keys(Keys.CONTROL, "v")
            self._action_wait()

            self._human_scroll("down", "light")
            logger.info("본문 입력 완료 (길이: %d)", len(body_html))
            return True
        except Exception as e:
            logger.error("본문 입력 실패: %s", e)
            return False

    def _insert_image(self, image_path: str) -> bool:
        """이미지 첨부 (파일 업로드)"""
        if not image_path or not Path(image_path).exists():
            logger.warning("이미지 파일 없음: %s", image_path)
            return False

        try:
            # 이미지 추가 버튼 클릭
            img_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".se-toolbar-button-image, button[data-name='image']")
                )
            )
            img_btn.click()
            self._action_wait()

            # 파일 input에 경로 전송
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(os.path.abspath(image_path))
            time.sleep(3)  # 업로드 대기

            logger.info("이미지 첨부 완료: %s", Path(image_path).name)
            return True
        except Exception as e:
            logger.error("이미지 첨부 실패: %s", e)
            return False

    def _insert_tags(self, tags: list[str]) -> bool:
        """태그 입력"""
        if not tags:
            return True

        try:
            # 태그 입력 영역
            tag_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".tag_input input, input[placeholder*='태그']")
                )
            )

            for tag in tags:
                tag_input.click()
                self._action_wait()
                pyperclip.copy(tag.strip())
                tag_input.send_keys(Keys.CONTROL, "v")
                time.sleep(0.5)
                tag_input.send_keys(Keys.ENTER)
                self._action_wait()

            logger.info("태그 입력 완료: %s", ", ".join(tags[:5]))
            return True
        except Exception as e:
            logger.error("태그 입력 실패: %s", e)
            return False

    def _click_publish(self) -> str | None:
        """
        발행 버튼 클릭 후 발행된 글 URL을 반환한다.

        Returns:
            발행된 글 URL 또는 None (실패 시)
        """
        try:
            # 발행 버튼 클릭
            publish_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".publish_btn__Y5mLP, button.se-publish-button")
                )
            )
            publish_btn.click()
            time.sleep(3)

            # 공개 설정 확인 후 최종 발행
            try:
                confirm_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, ".confirm_btn, button[data-testid='publish-confirm']")
                    )
                )
                confirm_btn.click()
                time.sleep(5)
            except Exception:
                # 확인 다이얼로그가 없으면 바로 발행된 것
                time.sleep(3)

            # 발행된 글 URL 추출
            current_url = self.driver.current_url
            if "/postView" in current_url or "/blog/" in current_url:
                logger.info("발행 성공: %s", current_url)
                return current_url

            logger.warning("발행 후 URL 확인 불가: %s", current_url)
            return current_url

        except Exception as e:
            logger.error("발행 버튼 클릭 실패: %s", e)
            return None

    # ──────────────────────────────────────────────
    # 스크린샷
    # ──────────────────────────────────────────────

    def _save_screenshot(self, name: str) -> str:
        """에러 스크린샷 저장 후 경로 반환"""
        filepath = self.screenshot_dir / f"{name}_{int(time.time())}.png"
        try:
            self.driver.save_screenshot(str(filepath))
            logger.info("스크린샷 저장: %s", filepath)
            return str(filepath)
        except Exception:
            return ""

    # ──────────────────────────────────────────────
    # 통합 발행 메서드
    # ──────────────────────────────────────────────

    def publish_single(
        self,
        blog_account: dict,
        article: dict,
        image_paths: list[str] | None = None,
    ) -> dict:
        """
        단일 글 발행

        Args:
            blog_account: {"blog_id": str, "naver_id": str, "naver_pw": str, ...}
            article: {
                "keyword_id": str,
                "title": str,
                "body_html": str,
                "tags": list[str],
            }
            image_paths: 첨부할 이미지 경로 리스트

        Returns:
            {
                "status": str,           # PublishResult 상수
                "post_url": str or "",
                "error_message": str or "",
                "screenshot_path": str or "",
            }
        """
        blog_id = blog_account["blog_id"]
        naver_id = blog_account["naver_id"]
        naver_pw = blog_account["naver_pw"]

        result = {
            "status": PublishResult.PUBLISH_FAIL,
            "post_url": "",
            "error_message": "",
            "screenshot_path": "",
        }

        try:
            # 1. 브라우저 생성
            self.driver = self._create_driver(blog_id)

            # 2. 로그인
            if not self.login(blog_id, naver_id, naver_pw):
                result["status"] = PublishResult.LOGIN_FAIL
                result["error_message"] = "로그인 실패"
                result["screenshot_path"] = self._save_screenshot(f"login_{blog_id}")
                return result

            self._action_wait()

            # 2-1. 세션 워밍업
            self._warmup_session(blog_id)

            # 3. 에디터 열기
            if not self._open_editor(blog_id):
                result["status"] = PublishResult.EDITOR_FAIL
                result["error_message"] = "에디터 열기 실패"
                result["screenshot_path"] = self._save_screenshot(f"editor_{blog_id}")
                return result

            # 4. 제목 입력
            if not self._insert_title(article["title"]):
                result["status"] = PublishResult.EDITOR_FAIL
                result["error_message"] = "제목 입력 실패"
                result["screenshot_path"] = self._save_screenshot(f"title_{blog_id}")
                return result

            # 5. 본문 입력
            if not self._insert_body_html(article["body_html"]):
                result["status"] = PublishResult.EDITOR_FAIL
                result["error_message"] = "본문 입력 실패"
                result["screenshot_path"] = self._save_screenshot(f"body_{blog_id}")
                return result

            # 6. 이미지 첨부
            if image_paths:
                for img_path in image_paths:
                    self._insert_image(img_path)
                    self._action_wait()

            # 7. 태그 입력
            self._insert_tags(article.get("tags", []))

            # 8. 발행
            post_url = self._click_publish()
            if post_url:
                result["status"] = PublishResult.SUCCESS
                result["post_url"] = post_url
            else:
                result["status"] = PublishResult.PUBLISH_FAIL
                result["error_message"] = "발행 버튼 클릭 후 URL 확인 실패"
                result["screenshot_path"] = self._save_screenshot(f"publish_{blog_id}")

        except requests.ConnectionError:
            result["status"] = PublishResult.NETWORK_FAIL
            result["error_message"] = "네트워크 연결 실패"
        except Exception as e:
            result["error_message"] = str(e)
            result["screenshot_path"] = self._save_screenshot(f"error_{blog_id}")
            logger.error("발행 중 예외: %s", e, exc_info=True)

        return result

    def publish_with_retry(
        self,
        blog_account: dict,
        article: dict,
        image_paths: list[str] | None = None,
        ip_changer=None,
    ) -> dict:
        """
        발행 실패 시 자동 재시도

        Args:
            blog_account: 블로그 계정 정보
            article: 글 데이터
            image_paths: 이미지 경로들
            ip_changer: IPChanger 인스턴스 (네트워크 실패 시 IP 변경용)

        Returns:
            최종 발행 결과 dict + retry_count
        """
        last_result = None

        try:
            for attempt in range(self.max_retries + 1):
                if attempt > 0:
                    logger.info("재시도 %d/%d: %s", attempt, self.max_retries,
                                blog_account["blog_id"])

                # 이전 시도에서 브라우저 정리
                self._quit_driver()

                result = self.publish_single(blog_account, article, image_paths)
                result["retry_count"] = attempt
                last_result = result

                if result["status"] == PublishResult.SUCCESS:
                    return result

                # 상태별 복구 시도
                if result["status"] == PublishResult.LOGIN_FAIL:
                    self._delete_cookies(blog_account["blog_id"])
                    logger.info("쿠키 삭제 후 재시도")

                elif result["status"] == PublishResult.NETWORK_FAIL and ip_changer:
                    logger.info("IP 변경 후 재시도")
                    ip_changer.change_ip()

                elif result["status"] in (PublishResult.EDITOR_FAIL, PublishResult.PUBLISH_FAIL):
                    logger.info("에디터/발행 실패, 브라우저 재시작 후 재시도")

                self._action_wait()

            # 최종 실패
            logger.error("최종 발행 실패 (%d회 시도): %s",
                          self.max_retries + 1, blog_account["blog_id"])
            return last_result
        finally:
            # 성공/실패/예외 모든 경로에서 드라이버 정리 (성공 시 드라이버 누수 방지)
            self._quit_driver()

    def close(self):
        """리소스 정리"""
        self._quit_driver()
