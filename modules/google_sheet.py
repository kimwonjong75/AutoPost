"""
구글 시트 연동 모듈

- gspread를 사용하여 구글 시트 읽기/쓰기
- 키워드 시트: status="대기" 항목 가져오기
- 블로그 계정 시트: 계정 정보 가져오기
- 발행기록 시트: 발행 결과 기록
"""

import datetime
import logging
from pathlib import Path

import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

# 구글 시트 API 스코프
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# 시트 이름 상수
SHEET_KEYWORDS = "키워드"
SHEET_PRODUCTS = "상품정보"
SHEET_ACCOUNTS = "블로그계정"
SHEET_PUBLISH_LOG = "발행기록"


class GoogleSheetManager:
    """구글 시트 읽기/쓰기 관리"""

    def __init__(self, config: dict):
        """
        Args:
            config: config.yaml 전체 딕셔너리
        """
        self.config = config
        gs_config = config.get("google_sheet", {})
        self.service_account_json = gs_config.get(
            "service_account_json", "./data/google-service-account.json"
        )
        self.sheet_id = gs_config.get("sheet_id", "")
        self._client = None
        self._spreadsheet = None

    def _connect(self):
        """구글 시트 연결 (lazy init)"""
        if self._client is not None:
            return

        json_path = Path(self.service_account_json)
        if not json_path.exists():
            raise FileNotFoundError(
                f"서비스 계정 JSON 파일을 찾을 수 없습니다: {json_path}"
            )

        creds = ServiceAccountCredentials.from_json_keyfile_name(
            str(json_path), SCOPES
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_key(self.sheet_id)
        logger.info("구글 시트 연결 완료: %s", self._spreadsheet.title)

    def _get_worksheet(self, name: str):
        """시트 이름으로 워크시트 가져오기"""
        self._connect()
        try:
            return self._spreadsheet.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(f"시트를 찾을 수 없습니다: '{name}'")

    # ──────────────────────────────────────────────
    # 키워드 시트
    # ──────────────────────────────────────────────
    # 예상 컬럼: keyword_id | keyword | content_type | blog_id | status | ...
    # status 값: 대기, 생성중, 생성완료, 발행완료, 실패

    def fetch_pending_keywords(self) -> list[dict]:
        """
        키워드 시트에서 status='대기' 항목을 가져온다.

        Returns:
            [
                {
                    "row_number": int,      # 시트 행 번호 (업데이트용)
                    "keyword_id": str,
                    "keyword": str,
                    "content_type": str,    # 정보성 / 상품홍보
                    "blog_id": str,
                    ...기타 컬럼
                }
            ]
        """
        ws = self._get_worksheet(SHEET_KEYWORDS)
        all_records = ws.get_all_records()

        pending = []
        for i, row in enumerate(all_records, start=2):  # 헤더가 1행이므로 데이터는 2행부터
            if str(row.get("status", "")).strip() == "대기":
                row["row_number"] = i
                pending.append(row)

        logger.info("대기 키워드 %d건 조회", len(pending))
        return pending

    def update_keyword_status(self, row_number: int, status: str):
        """키워드 시트의 특정 행 status 업데이트"""
        ws = self._get_worksheet(SHEET_KEYWORDS)
        headers = ws.row_values(1)

        try:
            col_idx = headers.index("status") + 1  # 1-based
        except ValueError:
            raise ValueError("키워드 시트에 'status' 컬럼이 없습니다.")

        ws.update_cell(row_number, col_idx, status)
        logger.info("키워드 행 %d 상태 → %s", row_number, status)

    # ──────────────────────────────────────────────
    # 블로그 계정 시트
    # ──────────────────────────────────────────────
    # 예상 컬럼: blog_id | naver_id | naver_pw | blog_url | memo | active

    def fetch_blog_accounts(self) -> list[dict]:
        """
        블로그 계정 시트에서 활성(active) 계정 목록을 가져온다.

        Returns:
            [{"blog_id": str, "naver_id": str, "naver_pw": str, "blog_url": str, ...}]
        """
        ws = self._get_worksheet(SHEET_ACCOUNTS)
        all_records = ws.get_all_records()

        accounts = []
        for row in all_records:
            active = str(row.get("active", "Y")).strip().upper()
            if active in ("Y", "YES", "TRUE", "1", ""):
                accounts.append(row)

        logger.info("활성 블로그 계정 %d건 조회", len(accounts))
        return accounts

    def fetch_account_by_id(self, blog_id: str) -> dict | None:
        """특정 blog_id의 계정 정보 조회"""
        accounts = self.fetch_blog_accounts()
        for acc in accounts:
            if str(acc.get("blog_id", "")).strip() == blog_id:
                return acc
        return None

    # ──────────────────────────────────────────────
    # 상품정보 시트
    # ──────────────────────────────────────────────
    # 예상 컬럼: product_id | keyword_id | product_name | price | link | features | ...

    def fetch_product_info(self, keyword_id: str) -> dict | None:
        """키워드에 연결된 상품 정보 조회"""
        ws = self._get_worksheet(SHEET_PRODUCTS)
        all_records = ws.get_all_records()

        for row in all_records:
            if str(row.get("keyword_id", "")).strip() == keyword_id:
                return row
        return None

    # ──────────────────────────────────────────────
    # 발행기록 시트
    # ──────────────────────────────────────────────
    # 컬럼: keyword_id | blog_id | title | post_url | ip_address | status |
    #        error_message | retry_count | published_at

    def write_publish_result(self, result: dict):
        """
        발행 결과를 발행기록 시트에 추가한다.

        Args:
            result: {
                "keyword_id": str,
                "blog_id": str,
                "title": str,
                "post_url": str or "",
                "ip_address": str or "",
                "status": str,          # 성공 / 실패
                "error_message": str or "",
                "retry_count": int,
                "published_at": str or None,  # ISO 포맷, None이면 현재 시각
            }
        """
        ws = self._get_worksheet(SHEET_PUBLISH_LOG)

        published_at = result.get("published_at") or datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        row = [
            result.get("keyword_id", ""),
            result.get("blog_id", ""),
            result.get("title", ""),
            result.get("post_url", ""),
            result.get("ip_address", ""),
            result.get("status", ""),
            result.get("error_message", ""),
            result.get("retry_count", 0),
            published_at,
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(
            "발행기록 추가: %s / %s / %s",
            result.get("keyword_id"),
            result.get("blog_id"),
            result.get("status"),
        )

    def write_publish_results_batch(self, results: list[dict]):
        """여러 발행 결과를 한 번에 추가 (API 호출 절약)"""
        ws = self._get_worksheet(SHEET_PUBLISH_LOG)

        rows = []
        for result in results:
            published_at = result.get(
                "published_at"
            ) or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows.append([
                result.get("keyword_id", ""),
                result.get("blog_id", ""),
                result.get("title", ""),
                result.get("post_url", ""),
                result.get("ip_address", ""),
                result.get("status", ""),
                result.get("error_message", ""),
                result.get("retry_count", 0),
                published_at,
            ])

        ws.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info("발행기록 일괄 추가: %d건", len(rows))

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            self._connect()
            worksheets = [ws.title for ws in self._spreadsheet.worksheets()]
            logger.info("시트 목록: %s", worksheets)
            return True
        except Exception as e:
            logger.error("구글 시트 연결 실패: %s", e)
            return False
