"""
ADB 비행기모드 토글 IP 변경 모듈

- Android 12+ / 구형 자동 감지
- 비행기모드 ON → 대기 → OFF → 네트워크 복구 대기
- IP 변경 확인 (config에서 설정한 재시도 횟수)
- config.yaml의 adb 섹션 설정 사용
"""

import logging
import subprocess
import time

import requests

logger = logging.getLogger(__name__)


class IPChanger:
    """ADB 비행기모드 토글로 모바일 테더링 IP를 변경한다."""

    def __init__(self, config: dict):
        """
        Args:
            config: config.yaml 전체 딕셔너리
        """
        adb_config = config.get("adb", {})
        self.adb_path = adb_config.get("path", "adb")
        self.airplane_on_wait = adb_config.get("airplane_on_wait", 8)
        self.airplane_off_wait = adb_config.get("airplane_off_wait", 20)
        self.ip_check_retries = adb_config.get("ip_check_retries", 3)

        self._android_version = None
        self._current_ip = None

    # ──────────────────────────────────────────────
    # ADB 명령 실행
    # ──────────────────────────────────────────────

    def _run_adb(self, *args: str, timeout: int = 15) -> str:
        """ADB 명령 실행 후 stdout 반환"""
        cmd = [self.adb_path, *args]
        logger.debug("ADB 명령: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0 and result.stderr.strip():
                logger.warning("ADB stderr: %s", result.stderr.strip())
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("ADB 명령 타임아웃: %s", " ".join(cmd))
            raise
        except FileNotFoundError:
            raise FileNotFoundError(
                f"ADB를 찾을 수 없습니다: {self.adb_path}\n"
                "config.yaml의 adb.path를 확인하세요."
            )

    # ──────────────────────────────────────────────
    # Android 버전 감지
    # ──────────────────────────────────────────────

    def get_android_sdk_version(self) -> int:
        """연결된 기기의 Android SDK 버전을 반환한다."""
        if self._android_version is not None:
            return self._android_version

        output = self._run_adb("shell", "getprop", "ro.build.version.sdk")
        try:
            self._android_version = int(output)
        except ValueError:
            logger.warning("SDK 버전 파싱 실패 (%s), 기본값 31 사용", output)
            self._android_version = 31

        logger.info("Android SDK 버전: %d", self._android_version)
        return self._android_version

    def is_android_12_plus(self) -> bool:
        """Android 12 (SDK 31) 이상인지 확인"""
        return self.get_android_sdk_version() >= 31

    # ──────────────────────────────────────────────
    # 비행기모드 토글
    # ──────────────────────────────────────────────

    def _airplane_mode_on(self):
        """비행기모드 켜기"""
        if self.is_android_12_plus():
            self._run_adb("shell", "cmd", "connectivity", "airplane-mode", "enable")
        else:
            self._run_adb(
                "shell", "settings", "put", "global", "airplane_mode_on", "1"
            )
            self._run_adb(
                "shell", "am", "broadcast",
                "-a", "android.intent.action.AIRPLANE_MODE",
                "--ez", "state", "true",
            )
        logger.info("비행기모드 ON")

    def _airplane_mode_off(self):
        """비행기모드 끄기"""
        if self.is_android_12_plus():
            self._run_adb("shell", "cmd", "connectivity", "airplane-mode", "disable")
        else:
            self._run_adb(
                "shell", "settings", "put", "global", "airplane_mode_on", "0"
            )
            self._run_adb(
                "shell", "am", "broadcast",
                "-a", "android.intent.action.AIRPLANE_MODE",
                "--ez", "state", "false",
            )
        logger.info("비행기모드 OFF")

    # ──────────────────────────────────────────────
    # IP 확인
    # ──────────────────────────────────────────────

    def _get_public_ip(self, timeout: int = 10) -> str | None:
        """공인 IP 조회 (여러 서비스 시도)"""
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
        ]
        for url in services:
            try:
                resp = requests.get(url, timeout=timeout)
                ip = resp.text.strip()
                if ip:
                    return ip
            except requests.RequestException:
                continue
        return None

    # ──────────────────────────────────────────────
    # 메인: IP 변경
    # ──────────────────────────────────────────────

    def change_ip(self) -> dict:
        """
        비행기모드 토글로 IP를 변경하고 결과를 반환한다.

        Returns:
            {
                "success": bool,
                "old_ip": str or None,
                "new_ip": str or None,
                "changed": bool,         # IP가 실제로 변경되었는지
                "android_sdk": int,
            }
        """
        # 현재 IP 기록
        old_ip = self._current_ip or self._get_public_ip()
        logger.info("현재 IP: %s", old_ip)

        # 비행기모드 ON
        self._airplane_mode_on()
        time.sleep(self.airplane_on_wait)

        # 비행기모드 OFF
        self._airplane_mode_off()
        logger.info("네트워크 복구 대기 %d초...", self.airplane_off_wait)
        time.sleep(self.airplane_off_wait)

        # IP 변경 확인 (재시도)
        new_ip = None
        for attempt in range(1, self.ip_check_retries + 1):
            new_ip = self._get_public_ip()
            if new_ip:
                break
            logger.warning("IP 확인 실패 (시도 %d/%d), 5초 후 재시도",
                           attempt, self.ip_check_retries)
            time.sleep(5)

        if not new_ip:
            logger.error("IP 변경 후 네트워크 복구 실패")
            return {
                "success": False,
                "old_ip": old_ip,
                "new_ip": None,
                "changed": False,
                "android_sdk": self.get_android_sdk_version(),
            }

        self._current_ip = new_ip
        changed = old_ip != new_ip

        if changed:
            logger.info("IP 변경 성공: %s → %s", old_ip, new_ip)
        else:
            logger.warning("IP 동일: %s (변경되지 않음)", new_ip)

        return {
            "success": True,
            "old_ip": old_ip,
            "new_ip": new_ip,
            "changed": changed,
            "android_sdk": self.get_android_sdk_version(),
        }

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    def check_device_connected(self) -> bool:
        """ADB 기기 연결 여부 확인"""
        output = self._run_adb("devices")
        lines = [l for l in output.split("\n") if "\tdevice" in l]
        connected = len(lines) > 0
        if connected:
            logger.info("ADB 기기 연결됨: %d대", len(lines))
        else:
            logger.warning("ADB 연결된 기기 없음")
        return connected

    def get_current_ip(self) -> str | None:
        """현재 공인 IP 반환 (캐시 없이 새로 조회)"""
        ip = self._get_public_ip()
        self._current_ip = ip
        return ip
