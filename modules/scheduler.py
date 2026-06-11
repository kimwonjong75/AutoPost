"""
예약 발행 스케줄러 모듈.

APScheduler의 BackgroundScheduler를 사용하여 Streamlit 세션과 독립적으로
예약된 발행 작업을 실행한다.

스케줄은 config.yaml의 scheduler 섹션에 저장·복원된다.
"""

import datetime
import json
import logging
import os
import random
import threading
import time
from pathlib import Path

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 스케줄러 상태 파일 (JSON)
SCHEDULE_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "scheduler_state.json"
)

# 최대 예약 슬롯 수
MAX_SCHEDULES = 10

# 스케줄러 싱글톤
_scheduler_instance: "PublishScheduler | None" = None
_scheduler_lock = threading.Lock()


def get_scheduler(config: dict) -> "PublishScheduler":
    """프로세스 전체에서 하나의 스케줄러 인스턴스를 공유한다."""
    global _scheduler_instance
    with _scheduler_lock:
        if _scheduler_instance is None:
            _scheduler_instance = PublishScheduler(config)
        return _scheduler_instance


class ScheduleEntry:
    """예약 발행 1건의 정의."""

    def __init__(
        self,
        schedule_id: str,
        name: str,
        cron_hour: int,
        cron_minute: int,
        blog_id: str,
        max_articles: int = 5,
        enabled: bool = True,
        days_of_week: str = "mon-fri",
    ):
        self.schedule_id = schedule_id
        self.name = name
        self.cron_hour = cron_hour
        self.cron_minute = cron_minute
        self.blog_id = blog_id
        self.max_articles = max_articles
        self.enabled = enabled
        self.days_of_week = days_of_week

    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "cron_hour": self.cron_hour,
            "cron_minute": self.cron_minute,
            "blog_id": self.blog_id,
            "max_articles": self.max_articles,
            "enabled": self.enabled,
            "days_of_week": self.days_of_week,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduleEntry":
        return cls(
            schedule_id=data["schedule_id"],
            name=data["name"],
            cron_hour=data["cron_hour"],
            cron_minute=data["cron_minute"],
            blog_id=data["blog_id"],
            max_articles=data.get("max_articles", 5),
            enabled=data.get("enabled", True),
            days_of_week=data.get("days_of_week", "mon-fri"),
        )


class ScheduleLog:
    """스케줄 실행 기록 1건."""

    def __init__(
        self,
        schedule_id: str,
        executed_at: str,
        articles_published: int,
        articles_failed: int,
        status: str,
        message: str = "",
    ):
        self.schedule_id = schedule_id
        self.executed_at = executed_at
        self.articles_published = articles_published
        self.articles_failed = articles_failed
        self.status = status
        self.message = message

    def to_dict(self) -> dict:
        return {
            "schedule_id": self.schedule_id,
            "executed_at": self.executed_at,
            "articles_published": self.articles_published,
            "articles_failed": self.articles_failed,
            "status": self.status,
            "message": self.message,
        }


class PublishScheduler:
    """APScheduler 기반 예약 발행 관리자."""

    def __init__(self, config: dict):
        self.config = config
        self._scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1}
        )
        self._schedules: dict[str, ScheduleEntry] = {}
        self._logs: list[dict] = []
        self._running = False

        # 상태 복원
        self._load_state()

    # ------------------------------------------------------------------
    # 상태 영속화
    # ------------------------------------------------------------------

    def _load_state(self):
        """스케줄 상태를 JSON 파일에서 복원한다."""
        if not os.path.exists(SCHEDULE_STATE_PATH):
            return
        try:
            with open(SCHEDULE_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            for entry_data in state.get("schedules", []):
                entry = ScheduleEntry.from_dict(entry_data)
                self._schedules[entry.schedule_id] = entry
            self._logs = state.get("logs", [])[-100:]  # 최근 100건만 유지
        except Exception as exc:
            logger.error("스케줄 상태 복원 실패: %s", exc)

    def _save_state(self):
        """스케줄 상태를 JSON 파일에 저장한다."""
        os.makedirs(os.path.dirname(SCHEDULE_STATE_PATH), exist_ok=True)
        state = {
            "schedules": [e.to_dict() for e in self._schedules.values()],
            "logs": self._logs[-100:],
        }
        try:
            with open(SCHEDULE_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("스케줄 상태 저장 실패: %s", exc)

    # ------------------------------------------------------------------
    # 스케줄 관리
    # ------------------------------------------------------------------

    def add_schedule(self, entry: ScheduleEntry) -> bool:
        """새 스케줄을 추가한다."""
        if len(self._schedules) >= MAX_SCHEDULES:
            logger.warning("최대 스케줄 수(%d)에 도달했습니다.", MAX_SCHEDULES)
            return False

        self._schedules[entry.schedule_id] = entry
        if self._running and entry.enabled:
            self._register_job(entry)
        self._save_state()
        return True

    def remove_schedule(self, schedule_id: str) -> bool:
        """스케줄을 삭제한다."""
        if schedule_id not in self._schedules:
            return False

        if self._running:
            try:
                self._scheduler.remove_job(schedule_id)
            except Exception:
                pass

        del self._schedules[schedule_id]
        self._save_state()
        return True

    def toggle_schedule(self, schedule_id: str, enabled: bool):
        """스케줄 활성/비활성 전환."""
        entry = self._schedules.get(schedule_id)
        if not entry:
            return

        entry.enabled = enabled
        if self._running:
            if enabled:
                self._register_job(entry)
            else:
                try:
                    self._scheduler.remove_job(schedule_id)
                except Exception:
                    pass
        self._save_state()

    def get_schedules(self) -> list[ScheduleEntry]:
        """등록된 스케줄 목록을 반환한다."""
        return list(self._schedules.values())

    def get_logs(self, limit: int = 20) -> list[dict]:
        """최근 실행 기록을 반환한다."""
        return self._logs[-limit:][::-1]

    # ------------------------------------------------------------------
    # 스케줄러 시작/종료
    # ------------------------------------------------------------------

    def start(self):
        """스케줄러를 시작한다."""
        if self._running:
            return

        for entry in self._schedules.values():
            if entry.enabled:
                self._register_job(entry)

        self._scheduler.start()
        self._running = True
        logger.info("스케줄러 시작됨. 활성 스케줄: %d건", len(self._scheduler.get_jobs()))

    def stop(self):
        """스케줄러를 중지한다."""
        if not self._running:
            return
        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("스케줄러 중지됨")

    def is_running(self) -> bool:
        return self._running

    def get_next_run(self, schedule_id: str) -> str | None:
        """다음 실행 예정 시각을 문자열로 반환한다."""
        if not self._running:
            return None
        try:
            job = self._scheduler.get_job(schedule_id)
            if job and job.next_run_time:
                return job.next_run_time.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------

    def _register_job(self, entry: ScheduleEntry):
        """APScheduler에 CronTrigger 작업을 등록한다."""
        try:
            self._scheduler.remove_job(entry.schedule_id)
        except Exception:
            pass

        trigger = CronTrigger(
            hour=entry.cron_hour,
            minute=entry.cron_minute,
            day_of_week=entry.days_of_week,
        )

        self._scheduler.add_job(
            self._execute_schedule,
            trigger=trigger,
            id=entry.schedule_id,
            args=[entry.schedule_id],
            replace_existing=True,
        )

    def _execute_schedule(self, schedule_id: str):
        """예약된 시각에 실행되는 발행 작업."""
        entry = self._schedules.get(schedule_id)
        if not entry:
            return

        logger.info("예약 발행 시작: %s (blog=%s, max=%d)",
                     entry.name, entry.blog_id, entry.max_articles)

        published = 0
        failed = 0
        message = ""

        try:
            from modules.models import GeneratedArticle, PublishLog, init_db
            init_db()

            # 검토완료 상태의 글 가져오기
            articles = list(
                GeneratedArticle.select()
                .where(GeneratedArticle.status == "검토완료")
                .order_by(GeneratedArticle.created_at)
                .limit(entry.max_articles)
            )

            if not articles:
                message = "발행할 글 없음 (검토완료 상태의 글이 없습니다)"
                logger.info(message)
            else:
                # 시간 분산 (jitter)
                jitter_minutes = self.config.get("publish", {}).get(
                    "schedule", {}
                ).get("time_jitter_minutes", 15)
                if jitter_minutes > 0:
                    jitter = random.randint(0, jitter_minutes * 60)
                    logger.info("시간 분산: %d초 대기", jitter)
                    time.sleep(jitter)

                # 발행 실행 (blog_publisher 호출)
                try:
                    from modules.blog_publisher import BlogPublisher, PublishResult
                    from modules.publish_helpers import (
                        article_to_publish_dict,
                        build_blog_account,
                        selected_image_paths,
                    )

                    secrets_path = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        "secrets.yaml",
                    )
                    secrets = {}
                    if os.path.exists(secrets_path):
                        with open(secrets_path, "r", encoding="utf-8") as f:
                            secrets = yaml.safe_load(f) or {}

                    # config 계정 + secrets 비밀번호를 publish_single용 dict로 합침
                    publish_account = build_blog_account(
                        self.config, secrets, entry.blog_id
                    )

                    if not publish_account:
                        message = f"블로그 계정 '{entry.blog_id}'을(를) 찾을 수 없습니다"
                        logger.error(message)
                    else:
                        publisher = BlogPublisher(self.config)
                        inter_post_delay = self.config.get("publish", {}).get(
                            "inter_post_delay", [30, 90]
                        )

                        try:
                            for idx, article in enumerate(articles):
                                try:
                                    result = publisher.publish_with_retry(
                                        blog_account=publish_account,
                                        article=article_to_publish_dict(article),
                                        image_paths=selected_image_paths(article),
                                    )

                                    if result["status"] == PublishResult.SUCCESS:
                                        published += 1
                                        article.status = "발행완료"
                                        article.save()
                                        PublishLog.create(
                                            blog_id=entry.blog_id,
                                            keyword_id=article.keyword_id,
                                            article=article,
                                            title=article.title,
                                            post_url=result.get("post_url", ""),
                                            ip_address=result.get("ip_address", ""),
                                            status="성공",
                                            error_message="",
                                            screenshot_path="",
                                            retry_count=result.get("retry_count", 0),
                                            delay_seconds=0,
                                        )
                                    else:
                                        failed += 1
                                        article.status = "실패"
                                        article.save()
                                        PublishLog.create(
                                            blog_id=entry.blog_id,
                                            keyword_id=article.keyword_id,
                                            article=article,
                                            title=article.title,
                                            post_url=result.get("post_url", ""),
                                            ip_address=result.get("ip_address", ""),
                                            status="실패",
                                            error_message=result.get("error_message", ""),
                                            screenshot_path=result.get("screenshot_path", ""),
                                            retry_count=result.get("retry_count", 0),
                                            delay_seconds=0,
                                        )

                                    # 글 간 대기
                                    if idx < len(articles) - 1:
                                        delay = random.uniform(
                                            inter_post_delay[0], inter_post_delay[1]
                                        )
                                        time.sleep(delay)

                                except Exception as exc:
                                    failed += 1
                                    logger.error("글 발행 실패 [%s]: %s", article.title[:30], exc)
                                    article.status = "실패"
                                    article.save()
                                    PublishLog.create(
                                        blog_id=entry.blog_id,
                                        keyword_id=article.keyword_id,
                                        article=article,
                                        title=article.title,
                                        post_url="",
                                        ip_address="",
                                        status="실패",
                                        error_message=str(exc),
                                        screenshot_path="",
                                        retry_count=0,
                                        delay_seconds=0,
                                    )

                            message = f"성공 {published}건, 실패 {failed}건"
                        finally:
                            publisher.close()

                except ImportError:
                    message = "blog_publisher 모듈을 불러올 수 없습니다 (mock 모드에서는 사용 불가)"
                    logger.warning(message)

        except Exception as exc:
            message = f"스케줄 실행 오류: {exc}"
            logger.error(message, exc_info=True)

        # 실행 기록 저장
        log = ScheduleLog(
            schedule_id=schedule_id,
            executed_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            articles_published=published,
            articles_failed=failed,
            status="성공" if failed == 0 and published > 0 else ("부분실패" if published > 0 else "실패"),
            message=message,
        )
        self._logs.append(log.to_dict())
        self._save_state()
        logger.info("예약 발행 완료: %s", message)
