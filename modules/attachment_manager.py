"""참고자료 첨부 파일 관리 모듈

PDF, 이미지(jpg/png), 텍스트(txt/md/csv) 파일을 키워드별로 영구 보관하고,
AI 글 작성 프롬프트에 주입할 컨텍스트를 생성한다.
"""

import hashlib
import os
import shutil
from pathlib import Path

from .models import Attachment, db

# 프로젝트 루트 기준 저장 디렉토리
STORAGE_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "data" / "attachments"

ALLOWED_TYPES = {
    "pdf": ["pdf"],
    "image": ["jpg", "jpeg", "png", "webp", "gif"],
    "text": ["txt", "md", "csv", "json"],
}

# 텍스트 추출 최대 길이
MAX_EXTRACT_LEN = 10_000
# 프롬프트 주입 시 첨부파일당 최대 길이
MAX_CONTEXT_PER_FILE = 3_000


class AttachmentManager:
    """참고자료 첨부 파일 관리"""

    def __init__(self, storage_dir: str | Path | None = None):
        self.storage_dir = Path(storage_dir) if storage_dir else STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, keyword_id: str, uploaded_file, description: str = "") -> Attachment:
        """첨부파일 저장 + DB 등록

        Args:
            keyword_id: 연결할 키워드 ID
            uploaded_file: Streamlit UploadedFile 또는 file-like 객체 (.name, .read() 필요)
            description: 사용자 메모

        Returns:
            생성된 Attachment 레코드
        """
        ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
        file_type = self._detect_type(ext)

        # 파일 해시로 고유 이름 생성
        content = uploaded_file.read()
        file_hash = hashlib.md5(content).hexdigest()[:8]
        uploaded_file.seek(0)

        stored_name = f"{keyword_id}_{file_hash}.{ext}"
        keyword_dir = self.storage_dir / keyword_id
        keyword_dir.mkdir(parents=True, exist_ok=True)
        stored_path = keyword_dir / stored_name

        stored_path.write_bytes(content)

        extracted = self._extract_text(stored_path, file_type)

        db.connect(reuse_if_open=True)
        return Attachment.create(
            keyword_id=keyword_id,
            original_filename=uploaded_file.name,
            stored_path=str(stored_path),
            file_type=file_type,
            file_size=len(content),
            description=description,
            extracted_text=extracted,
        )

    def save_from_path(self, keyword_id: str, source_path: str, description: str = "") -> Attachment:
        """로컬 파일 경로에서 첨부파일 저장

        Args:
            keyword_id: 연결할 키워드 ID
            source_path: 원본 파일 경로
            description: 사용자 메모

        Returns:
            생성된 Attachment 레코드
        """
        source = Path(source_path)
        ext = source.suffix.lstrip(".").lower()
        file_type = self._detect_type(ext)

        with open(source, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]

        stored_name = f"{keyword_id}_{file_hash}.{ext}"
        keyword_dir = self.storage_dir / keyword_id
        keyword_dir.mkdir(parents=True, exist_ok=True)
        stored_path = keyword_dir / stored_name

        shutil.copy2(source, stored_path)

        extracted = self._extract_text(stored_path, file_type)

        db.connect(reuse_if_open=True)
        return Attachment.create(
            keyword_id=keyword_id,
            original_filename=source.name,
            stored_path=str(stored_path),
            file_type=file_type,
            file_size=stored_path.stat().st_size,
            description=description,
            extracted_text=extracted,
        )

    def get_attachments(self, keyword_id: str) -> list[Attachment]:
        """키워드에 연결된 첨부파일 목록 조회"""
        db.connect(reuse_if_open=True)
        return list(Attachment.select().where(Attachment.keyword_id == keyword_id))

    def delete_attachment(self, attachment_id: int) -> bool:
        """첨부파일 삭제 (DB + 파일)"""
        db.connect(reuse_if_open=True)
        try:
            att = Attachment.get_by_id(attachment_id)
        except Attachment.DoesNotExist:
            return False

        # 실제 파일 삭제
        file_path = Path(att.stored_path)
        if file_path.exists():
            file_path.unlink()

        att.delete_instance()
        return True

    def build_context_for_prompt(self, keyword_id: str) -> str:
        """첨부자료를 AI 프롬프트에 주입할 텍스트로 변환

        Args:
            keyword_id: 키워드 ID

        Returns:
            프롬프트에 삽입할 컨텍스트 문자열 (첨부 없으면 빈 문자열)
        """
        attachments = self.get_attachments(keyword_id)
        if not attachments:
            return ""

        context_parts = ["[참고자료]"]
        for att in attachments:
            if att.extracted_text:
                context_parts.append(
                    f"\n--- {att.original_filename} ---\n"
                    f"{att.extracted_text[:MAX_CONTEXT_PER_FILE]}"
                )
            if att.description:
                context_parts.append(f"(메모: {att.description})")

        return "\n".join(context_parts)

    def _detect_type(self, ext: str) -> str:
        """확장자로 파일 유형 판별"""
        for file_type, exts in ALLOWED_TYPES.items():
            if ext in exts:
                return file_type
        return "unknown"

    def _extract_text(self, path: Path, file_type: str) -> str:
        """파일에서 텍스트 추출"""
        if file_type == "text":
            return path.read_text(encoding="utf-8", errors="ignore")[:MAX_EXTRACT_LEN]

        if file_type == "pdf":
            return self._extract_pdf_text(path)

        if file_type == "image":
            return "(이미지 - 텍스트 추출 미지원)"

        return ""

    def _extract_pdf_text(self, path: Path) -> str:
        """pdfplumber로 PDF 텍스트 추출"""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                return "\n".join(pages_text)[:MAX_EXTRACT_LEN]
        except ImportError:
            return "(pdfplumber 미설치 - pip install pdfplumber)"
        except Exception as e:
            return f"(PDF 텍스트 추출 실패: {e})"
