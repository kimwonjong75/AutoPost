import datetime
import json
import logging
import os

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

logger = logging.getLogger(__name__)

# DB 경로: 프로젝트 루트의 data/ 디렉토리
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "blog_auto.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = SqliteDatabase(DB_PATH, pragmas={
    "journal_mode": "wal",
    "cache_size": -1024 * 64,
    "foreign_keys": 1,
})


class BaseModel(Model):
    class Meta:
        database = db


class Attachment(BaseModel):
    """참고자료 첨부 파일"""
    id = AutoField()
    keyword_id = CharField(index=True)
    original_filename = CharField()
    stored_path = CharField()
    file_type = CharField()                      # pdf, image, text
    file_size = IntegerField(default=0)
    description = TextField(null=True)
    extracted_text = TextField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "attachments"


class GeneratedArticle(BaseModel):
    """생성된 글"""
    id = AutoField()
    keyword_id = CharField(index=True)
    engine = CharField()                         # openai, claude, gemini
    model = CharField()
    title = CharField()
    body_html = TextField()
    tags = TextField(default="[]")               # JSON 배열 문자열
    image_prompt = TextField(null=True)
    status = CharField(default="생성완료")        # 생성완료, 검토완료, 발행완료, 실패
    cost_estimate = FloatField(default=0)         # KRW (생성 시점 환율 스냅샷, 하위호환용)
    cost_usd = FloatField(default=0)              # USD (환율 무관 SSOT) — 표시 시 ×환율
    tokens_used = IntegerField(default=0)         # 입력+출력 합산
    input_tokens = IntegerField(default=0)
    output_tokens = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "generated_articles"

    def get_tags_list(self):
        return json.loads(self.tags) if self.tags else []

    def set_tags_list(self, tags_list):
        self.tags = json.dumps(tags_list, ensure_ascii=False)


class GeneratedImage(BaseModel):
    """생성된 이미지"""
    id = AutoField()
    keyword_id = CharField(index=True)
    article = ForeignKeyField(GeneratedArticle, backref="images", null=True)
    engine = CharField()                         # gpt_image, flux_schnell 등
    prompt_used = TextField()
    local_path = CharField()
    width = IntegerField()
    height = IntegerField()
    quality = CharField(default="")               # gpt_image 등 품질 옵션 (단가 계산용)
    cost_estimate = FloatField(default=0)         # KRW (생성 시점 환율 스냅샷, 하위호환용)
    cost_usd = FloatField(default=0)              # USD (환율 무관 SSOT) — 표시 시 ×환율
    is_selected = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "generated_images"


class PublishLog(BaseModel):
    """발행 기록"""
    id = AutoField()
    blog_id = CharField()
    keyword_id = CharField()
    article = ForeignKeyField(GeneratedArticle, backref="publish_logs")
    title = CharField()
    post_url = CharField(null=True)
    ip_address = CharField(null=True)
    status = CharField()                         # 성공, 실패
    error_message = TextField(null=True)
    screenshot_path = CharField(null=True)
    retry_count = IntegerField(default=0)
    delay_seconds = IntegerField(default=0)
    published_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "publish_logs"


# 기존 테이블에 추가돼야 하는 신규 컬럼 (peewee는 자동 마이그레이션 미지원)
_NEW_COLUMNS = {
    GeneratedArticle: ("cost_usd", "input_tokens", "output_tokens"),
    GeneratedImage: ("quality", "cost_usd"),
}


def _ensure_columns():
    """이미 생성된 테이블에 신규 컬럼이 없으면 playhouse migrator로 추가한다."""
    from playhouse.migrate import SqliteMigrator, migrate

    migrator = SqliteMigrator(db)
    for model, columns in _NEW_COLUMNS.items():
        table = model._meta.table_name
        try:
            existing = {c.name for c in db.get_columns(table)}
        except Exception:
            continue
        ops = [
            migrator.add_column(table, col, getattr(model, col))
            for col in columns
            if col not in existing
        ]
        if ops:
            try:
                migrate(*ops)
                logger.info("스키마 마이그레이션: %s에 %d개 컬럼 추가", table, len(ops))
            except Exception as exc:
                logger.warning("스키마 마이그레이션 실패 (%s): %s", table, exc)


def init_db():
    """테이블 생성 (없으면 자동 생성) 후 신규 컬럼 마이그레이션."""
    db.connect(reuse_if_open=True)
    db.create_tables([Attachment, GeneratedArticle, GeneratedImage, PublishLog])
    _ensure_columns()
    return db


if __name__ == "__main__":
    init_db()
    print(f"DB 생성 완료: {DB_PATH}")
    for table in [Attachment, GeneratedArticle, GeneratedImage, PublishLog]:
        print(f"  - {table._meta.table_name}")
