"""
글 내용 기반 이미지 변수 자동 분석 모듈.

글 제목/태그/이미지힌트를 분석하여 아파트 배경 이미지에 적합한
변수 조합(Location, DirtLevel, Light, Angle)을 자동 선택한다.

비용 절감을 위해 가용 엔진 중 가장 저렴한 모델을 자동 사용한다.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# 분석 전용 엔진 우선순위 (저렴한 순)
_ANALYSIS_ENGINE_PRIORITY: list[tuple[str, str]] = [
    ("gemini", "gemini-2.0-flash-lite"),
    ("gemini", "gemini-2.5-flash"),
    ("openai", "gpt-4o-mini"),
    ("claude", "claude-haiku-4-5-20241022"),
    ("gemini", "gemini-2.5-pro"),
    ("openai", "gpt-4o"),
    ("claude", "claude-sonnet-4-6-20250514"),
]

# 분석 1회 예상 비용 (원화, ~1800 input + 150 output tokens 기준)
ANALYSIS_COST_KRW: dict[tuple[str, str], float] = {
    ("gemini", "gemini-2.0-flash-lite"): 0.25,
    ("gemini", "gemini-2.5-flash"): 0.50,
    ("openai", "gpt-4o-mini"): 0.50,
    ("claude", "claude-haiku-4-5-20241022"): 3.57,
    ("gemini", "gemini-2.5-pro"): 5.25,
    ("openai", "gpt-4o"): 8.40,
    ("claude", "claude-sonnet-4-6-20250514"): 10.71,
}


class ImageVariableAnalyzer:
    """글 내용 분석 → 아파트 이미지 변수 자동 선택"""

    def __init__(self, config: dict):
        self.config = config
        # ContentGenerator 방식: api_keys 하위에 엔진명 키로 저장
        self.api_keys: dict = config.get("api_keys", {})

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def pick_engine(self) -> tuple[str, str] | None:
        """사용 가능한 엔진 중 가장 저렴한 (engine, model) 반환."""
        for engine, model in _ANALYSIS_ENGINE_PRIORITY:
            if self.api_keys.get(engine):
                return engine, model
        return None

    def get_estimated_cost(self) -> float:
        """이번 분석 예상 비용 (원화)."""
        ep = self.pick_engine()
        if ep is None:
            return 0.0
        return ANALYSIS_COST_KRW.get(ep, 1.0)

    def analyze(
        self,
        article_data: dict,
        locations: list[dict],
        dirt_levels: list[dict],
        lights: list[dict],
        angles: list[dict],
    ) -> dict:
        """
        글 데이터를 분석해 최적 변수 조합을 반환한다.

        Args:
            article_data: {"title": str, "tags": list, "image_prompt": str, "body_html": str}
            locations: APARTMENT_LOCATIONS
            dirt_levels: APARTMENT_DIRT_LEVELS
            lights: APARTMENT_LIGHT_SOURCES
            angles: APARTMENT_ANGLES

        Returns:
            {
                "location_id": str,
                "dirt_level": int,
                "light_id": str,
                "angle_id": str,
                "reason": str,
                "engine": str,
                "model": str,
                "cost_estimate": float,
            }
        """
        ep = self.pick_engine()
        if ep is None:
            logger.warning("사용 가능한 분석 엔진이 없어 기본값을 사용합니다.")
            return self._default_vars(locations, dirt_levels, lights, angles, reason="API 키 없음 — 기본값 사용")

        engine, model = ep
        prompt = self._build_prompt(article_data, locations, dirt_levels, lights, angles)

        try:
            raw = self._call_llm(engine, model, prompt)
            result = self._parse_json(raw)
            result["engine"] = engine
            result["model"] = model
            result["cost_estimate"] = ANALYSIS_COST_KRW.get(ep, 1.0)
            # 값 검증 및 보정
            result = self._validate(result, locations, dirt_levels, lights, angles)
            return result
        except Exception as exc:
            logger.warning("변수 분석 실패, 기본값 사용: %s", exc)
            return self._default_vars(
                locations, dirt_levels, lights, angles,
                reason=f"분석 실패 — 기본값 사용 ({exc})",
                engine=engine, model=model,
            )

    # ------------------------------------------------------------------
    # 내부 구현
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        article_data: dict,
        locations: list[dict],
        dirt_levels: list[dict],
        lights: list[dict],
        angles: list[dict],
    ) -> str:
        title = article_data.get("title", "")
        tags = ", ".join(article_data.get("tags", []))
        img_hint = article_data.get("image_prompt", "")

        loc_list = "\n".join(f"  {l['id']}: {l['room_kr']} — {l['location_kr']}" for l in locations)
        dirt_list = "\n".join(f"  {d['level']}: {d['name_kr']} ({d['name_en']})" for d in dirt_levels)
        light_list = "\n".join(f"  {l['id']}: {l['label_kr']}" for l in lights)
        angle_list = "\n".join(f"  {a['id']}: {a['label_kr']}" for a in angles)

        return f"""다음 블로그 글에 가장 어울리는 이미지 변수를 선택하세요.
이미지는 한국 2000년대 아파트 내부 살충제/해충 관련 배경 사진입니다.

[글 정보]
제목: {title}
태그: {tags}
이미지 힌트: {img_hint}

[LOCATION — 1개 선택]
{loc_list}

[DIRT_LEVEL — 1~5 중 1개]
{dirt_list}

[LIGHT_SOURCE — 1개 선택]
{light_list}

[ANGLE — 1개 선택]
{angle_list}

글의 주제와 분위기에 맞는 조합을 선택하고, 반드시 아래 JSON 형식으로만 응답하세요:
{{"location_id": "K01", "dirt_level": 3, "light_id": "L1", "angle_id": "A1", "reason": "선택 이유 한 줄"}}"""

    def _call_llm(self, engine: str, model: str, prompt: str) -> str:
        if engine == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self.api_keys["gemini"])
            m = genai.GenerativeModel(model)
            response = m.generate_content(prompt)
            return response.text.strip()

        if engine == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=self.api_keys["openai"])
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()

        if engine == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_keys["claude"])
            message = client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()

        raise ValueError(f"지원하지 않는 분석 엔진: {engine}")

    @staticmethod
    def _parse_json(text: str) -> dict:
        """LLM 응답에서 JSON 추출."""
        # 코드블록 제거
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
        return json.loads(text)

    @staticmethod
    def _validate(
        result: dict,
        locations: list[dict],
        dirt_levels: list[dict],
        lights: list[dict],
        angles: list[dict],
    ) -> dict:
        """LLM 응답값이 유효 범위 내인지 확인 후 보정."""
        valid_loc_ids = {l["id"] for l in locations}
        valid_light_ids = {l["id"] for l in lights}
        valid_angle_ids = {a["id"] for a in angles}
        valid_dirt_levels = {d["level"] for d in dirt_levels}

        if result.get("location_id") not in valid_loc_ids:
            result["location_id"] = locations[0]["id"]
        if int(result.get("dirt_level", 0)) not in valid_dirt_levels:
            result["dirt_level"] = 3
        if result.get("light_id") not in valid_light_ids:
            result["light_id"] = lights[0]["id"]
        if result.get("angle_id") not in valid_angle_ids:
            result["angle_id"] = angles[0]["id"]

        result["dirt_level"] = int(result["dirt_level"])
        result.setdefault("reason", "")
        return result

    @staticmethod
    def _default_vars(
        locations: list[dict],
        dirt_levels: list[dict],
        lights: list[dict],
        angles: list[dict],
        reason: str = "기본값",
        engine: str = "none",
        model: str = "",
    ) -> dict:
        return {
            "location_id": locations[0]["id"] if locations else "K01",
            "dirt_level": 3,
            "light_id": lights[0]["id"] if lights else "L1",
            "angle_id": angles[0]["id"] if angles else "A1",
            "reason": reason,
            "engine": engine,
            "model": model,
            "cost_estimate": 0.0,
        }
