"""
발행 입력 매핑 헬퍼.

GeneratedArticle(Peewee) → publish_single/publish_with_retry가 기대하는 dict,
선택 이미지 경로, 블로그 계정 dict 구성을 scheduler와 pages/4 발행에서 공용으로 사용한다.
(blog_publisher/Selenium에 의존하지 않으므로 어느 진입점에서나 가볍게 import 가능)
"""


def article_to_publish_dict(article) -> dict:
    """GeneratedArticle(Peewee) → publish_single이 기대하는 dict로 변환."""
    return {
        "keyword_id": article.keyword_id,
        "title": article.title,
        "body_html": article.body_html,
        "tags": article.get_tags_list(),
    }


def selected_image_paths(article) -> list[str]:
    """해당 article의 is_selected=True 이미지 local_path 목록을 반환."""
    from modules.models import GeneratedImage

    return [
        img.local_path
        for img in GeneratedImage.select().where(
            (GeneratedImage.article == article)
            & (GeneratedImage.is_selected == True)
        )
        if img.local_path
    ]


def build_blog_account(config: dict, secrets: dict, blog_id: str) -> dict | None:
    """config의 blog_accounts 항목 + secrets 비밀번호를 publish_single용 dict로 합친다.

    Returns:
        {"blog_id", "naver_id", "naver_pw", ...} 병합 dict, 계정이 없으면 None
    """
    passwords = secrets.get("blog_passwords", {})
    for acc in config.get("blog_accounts", []):
        if acc.get("blog_id") == blog_id:
            merged = dict(acc)
            merged["naver_pw"] = passwords.get(blog_id, "")
            return merged
    return None
