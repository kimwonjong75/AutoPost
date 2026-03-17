"""프롬프트 템플릿 로딩/저장 유틸리티"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

TEMPLATE_INFO_ID = "__TEMPLATE_INFO__"
TEMPLATE_PRODUCT_ID = "__TEMPLATE_PRODUCT__"

DEFAULT_INFO_PROMPT = """당신은 네이버 블로그 전문 작가입니다.
아래 키워드에 대해 정보성 블로그 글을 작성하세요.

[작성 규칙]
1. 제목은 키워드를 포함하고 클릭을 유도하는 형태로 작성
2. 본문은 HTML 형식으로 작성 (h2, h3, p, ul, li 태그 사용)
3. 2000자 이상, 소제목 3~5개로 구성
4. 자연스러운 한국어, 구어체 사용
5. 핵심 정보를 먼저 제공하고, 개인 경험/의견을 섞어 작성

[출력 형식 - JSON]
{
  "title": "글 제목",
  "body_html": "<h2>소제목</h2><p>본문...</p>",
  "tags": ["태그1", "태그2", "태그3"],
  "image_prompt": "영어로 된 대표 이미지 프롬프트"
}"""

DEFAULT_PRODUCT_PROMPT = """당신은 네이버 블로그 전문 작가입니다.
아래 키워드(상품)에 대해 상품 홍보/리뷰 블로그 글을 작성하세요.

[작성 규칙]
1. 제목은 상품명을 포함하고, 리뷰/후기/추천 등의 키워드 활용
2. 본문은 HTML 형식으로 작성 (h2, h3, p, ul, li, strong 태그 사용)
3. 2000자 이상, 소제목 4~6개로 구성
4. 장점과 단점을 균형있게 서술 (장점 위주, 단점은 가볍게)
5. 구매 전 고려사항, 실사용 팁 포함
6. 자연스러운 후기 톤, 과도한 광고 느낌 배제

[출력 형식 - JSON]
{
  "title": "글 제목",
  "body_html": "<h2>소제목</h2><p>본문...</p>",
  "tags": ["태그1", "태그2", "태그3"],
  "image_prompt": "영어로 된 대표 이미지 프롬프트"
}"""


def load_template(filename: str, default: str) -> str:
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return default


def save_template(filename: str, content: str):
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATES_DIR / filename
    path.write_text(content, encoding="utf-8")


def get_system_prompt(content_type: str) -> str:
    if content_type == "상품홍보":
        return load_template("product_prompt.txt", DEFAULT_PRODUCT_PROMPT)
    return load_template("info_prompt.txt", DEFAULT_INFO_PROMPT)
