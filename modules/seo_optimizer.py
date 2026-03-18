"""
SEO 후처리 모듈.

생성된 글의 제목과 태그를 저가 LLM으로 검토·보정한다.
ImageVariableAnalyzer와 동일한 비용 오름차순 엔진 선택 패턴을 사용한다.
"""

import json
import logging

logger = logging.getLogger(__name__)

# 엔진 선택 우선순위 (비용 KRW 오름차순)
ENGINE_PRIORITY = [
    ("gemini", "gemini-2.0-flash-lite"),
    ("gemini", "gemini-2.5-flash"),
    ("openai", "gpt-4o-mini"),
    ("claude", "claude-haiku-4-5-20241022"),
]

SEO_SYSTEM_PROMPT = """당신은 네이버 블로그 SEO 전문가입니다.
아래 블로그 글의 제목과 태그를 검토하고 최적화해 주세요.

규칙:
1. 제목: 네이버 검색 최적화를 위해 핵심 키워드를 앞쪽에 배치. 40자 이내. 클릭 유도력 있게.
2. 태그: 검색 유입에 효과적인 태그 5~10개. 기존 태그 중 비효과적인 것은 교체.
3. 원본의 의미와 어조를 유지하되, SEO 관점에서만 보정.
4. 변경이 불필요하면 원본 그대로 반환.

반드시 아래 JSON 형식으로만 응답:
{"title": "최적화된 제목", "tags": ["태그1", "태그2", ...], "changes": "변경 사항 요약 (없으면 '변경 없음')"}"""

# 분석당 예상 토큰 (입력+출력)
ESTIMATED_TOKENS_PER_CALL = 800
USD_TO_KRW = 1400


class SeoOptimizer:
    """생성된 글의 제목·태그를 저가 LLM으로 SEO 최적화한다."""

    def __init__(self, config: dict):
        self.config = config
        self.api_keys = config.get("api_keys", {})

    def pick_engine(self) -> tuple[str, str] | None:
        """사용 가능한 가장 저렴한 엔진을 선택한다."""
        for engine, model in ENGINE_PRIORITY:
            key_field = {
                "openai": "openai",
                "claude": "claude",
                "gemini": "gemini",
            }.get(engine)
            if key_field and self.api_keys.get(key_field):
                return engine, model
        return None

    def get_estimated_cost(self) -> float:
        """1건당 예상 비용 (KRW)."""
        from modules.content_generator import ENGINE_CONFIGS

        ep = self.pick_engine()
        if not ep:
            return 0.0

        engine, model = ep
        engine_cfg = ENGINE_CONFIGS.get(engine, {})
        for m in engine_cfg.get("models", []):
            if m["id"] == model:
                avg_price = (m["input_per_m"] + m["output_per_m"]) / 2
                return round((ESTIMATED_TOKENS_PER_CALL / 1_000_000) * avg_price * USD_TO_KRW, 2)
        return 0.0

    def optimize(self, title: str, tags: list[str], keyword: str) -> dict:
        """
        제목과 태그를 SEO 최적화한다.

        Args:
            title: 원본 제목
            tags: 원본 태그 목록
            keyword: 대상 키워드

        Returns:
            {
                "title": str,           # 최적화된 제목
                "tags": list[str],      # 최적화된 태그
                "changes": str,         # 변경 내용 설명
                "engine": str,
                "model": str,
                "cost_estimate": float,  # KRW
                "optimized": bool,       # 실제 최적화 수행 여부
            }
        """
        ep = self.pick_engine()
        if not ep:
            logger.warning("SEO 최적화에 사용할 수 있는 API 키가 없습니다.")
            return self._fallback(title, tags, "API 키 없음")

        engine, model = ep

        user_prompt = (
            f"키워드: {keyword}\n"
            f"현재 제목: {title}\n"
            f"현재 태그: {json.dumps(tags, ensure_ascii=False)}"
        )

        try:
            from modules.content_generator import ContentGenerator

            generator = ContentGenerator(self.config)
            result = generator.generate(
                engine=engine,
                model=model,
                system_prompt=SEO_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                options={"temperature": 0.3, "max_tokens": 1000},
            )

            meta = result.get("meta", {})
            optimized_title = result.get("title", title)
            optimized_tags = result.get("tags", tags)
            changes = result.get("body_html", "")

            # _normalize_result가 body_html에 매핑하므로 changes 필드 재추출
            if not changes:
                changes = "변경 없음"

            # 빈 결과 방지
            if not optimized_title or optimized_title == "(제목 없음)":
                optimized_title = title
            if not optimized_tags:
                optimized_tags = tags

            return {
                "title": optimized_title,
                "tags": optimized_tags,
                "changes": changes,
                "engine": engine,
                "model": model,
                "cost_estimate": meta.get("cost_estimate", 0),
                "optimized": True,
            }

        except Exception as exc:
            logger.error("SEO 최적화 실패: %s", exc)
            return self._fallback(title, tags, f"오류: {exc}")

    @staticmethod
    def _fallback(title: str, tags: list[str], reason: str) -> dict:
        """최적화 실패 시 원본을 그대로 반환한다."""
        return {
            "title": title,
            "tags": tags,
            "changes": reason,
            "engine": "none",
            "model": "",
            "cost_estimate": 0,
            "optimized": False,
        }
