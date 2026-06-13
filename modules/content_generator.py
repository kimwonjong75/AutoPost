"""
다중 AI 엔진을 지원하는 통합 글 생성 모듈.

지원 엔진: OpenAI (GPT), Anthropic (Claude), Google (Gemini)
"""

import json
import logging
import os
import re

import yaml

logger = logging.getLogger(__name__)

# 엔진별 모델 설정 + 비용 단가 (Input/Output per 1M tokens, USD)
ENGINE_CONFIGS = {
    "openai": {
        "label": "OpenAI (GPT)",
        "api_key_field": "openai",
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o-mini (최저가·빠름)", "input_per_m": 0.15, "output_per_m": 0.60},
            {"id": "gpt-4o", "name": "GPT-4o (중급·고품질)", "input_per_m": 2.50, "output_per_m": 10.00},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1-mini (신형·가성비)", "input_per_m": 0.40, "output_per_m": 1.60},
            {"id": "gpt-4.1", "name": "GPT-4.1 (신형·코딩특화)", "input_per_m": 2.00, "output_per_m": 8.00},
        ],
        "extra_options": {
            "temperature": {"type": "slider", "min": 0.0, "max": 1.5, "default": 0.7},
            "response_format": {"type": "select", "options": ["json_object", "text"], "default": "json_object"},
        },
    },
    "claude": {
        "label": "Anthropic (Claude)",
        "api_key_field": "claude",
        "models": [
            {"id": "claude-haiku-4-5-20251001", "name": "Haiku 4.5 (빠름·가성비)", "input_per_m": 1.00, "output_per_m": 5.00},
            {"id": "claude-sonnet-4-6", "name": "Sonnet 4.6 (균형·추천)", "input_per_m": 3.00, "output_per_m": 15.00},
            {"id": "claude-opus-4-8", "name": "Opus 4.8 (최고품질·플래그십)", "input_per_m": 5.00, "output_per_m": 25.00},
        ],
        "extra_options": {
            "temperature": {"type": "slider", "min": 0.0, "max": 1.0, "default": 0.7},
            "max_tokens": {"type": "number", "default": 8000},
        },
    },
    "gemini": {
        "label": "Google (Gemini)",
        "api_key_field": "gemini",
        "models": [
            {"id": "gemini-3.1-flash-lite", "name": "3.1 Flash-Lite (최저가)", "input_per_m": 0.25, "output_per_m": 1.50},
            {"id": "gemini-3.5-flash", "name": "3.5 Flash (균형)", "input_per_m": 1.50, "output_per_m": 9.00},
            {"id": "gemini-2.5-pro", "name": "2.5 Pro (고성능)", "input_per_m": 1.25, "output_per_m": 10.00},
        ],
        "extra_options": {
            "temperature": {"type": "slider", "min": 0.0, "max": 2.0, "default": 0.7},
        },
    },
}

# temperature 등 샘플링 파라미터를 허용하지 않는 Claude 모델 (Opus 4.7+는 전송 시 400 반환)
CLAUDE_NO_SAMPLING_MODELS = ("claude-opus-4-8", "claude-opus-4-7")


def load_config(config_path: str = None) -> dict:
    """config.yaml을 읽어 dict로 반환."""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ContentGenerator:
    """다중 AI 엔진을 지원하는 통합 글 생성기."""

    def __init__(self, config: dict):
        self.config = config
        self.api_keys = config.get("api_keys", {})
        self._clients: dict = {}
        self._init_clients()

    # ------------------------------------------------------------------
    # 초기화
    # ------------------------------------------------------------------

    def _init_clients(self):
        """API 키가 설정된 엔진만 클라이언트를 초기화한다."""
        openai_key = self.api_keys.get("openai", "")
        if openai_key:
            try:
                from openai import OpenAI
                self._clients["openai"] = OpenAI(api_key=openai_key)
                logger.info("OpenAI 클라이언트 초기화 완료")
            except ImportError:
                logger.warning("openai 패키지가 설치되어 있지 않습니다. pip install openai")
            except Exception as e:
                logger.error("OpenAI 클라이언트 초기화 실패: %s", e)

        claude_key = self.api_keys.get("claude", "")
        if claude_key:
            try:
                import anthropic
                self._clients["claude"] = anthropic.Anthropic(api_key=claude_key)
                logger.info("Claude 클라이언트 초기화 완료")
            except ImportError:
                logger.warning("anthropic 패키지가 설치되어 있지 않습니다. pip install anthropic")
            except Exception as e:
                logger.error("Claude 클라이언트 초기화 실패: %s", e)

        gemini_key = self.api_keys.get("gemini", "")
        if gemini_key:
            try:
                from google import genai
                self._clients["gemini"] = genai.Client(api_key=gemini_key)
                logger.info("Gemini 클라이언트 초기화 완료")
            except ImportError:
                logger.warning("google-genai 패키지가 설치되어 있지 않습니다. pip install google-genai")
            except Exception as e:
                logger.error("Gemini 클라이언트 초기화 실패: %s", e)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def available_engines(self) -> list[str]:
        """사용 가능한(API 키가 설정된) 엔진 목록 반환."""
        return list(self._clients.keys())

    def is_engine_available(self, engine: str) -> bool:
        return engine in self._clients

    def generate(
        self,
        engine: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        options: dict | None = None,
    ) -> dict:
        """
        통합 글 생성 인터페이스.

        Args:
            engine: "openai" | "claude" | "gemini"
            model: 해당 엔진의 모델 ID (e.g. "gpt-4o-mini")
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트 (키워드 + 참고자료 등)
            options: 엔진별 추가 옵션 (temperature, max_tokens 등)

        Returns:
            {
                "title": str,
                "body_html": str,
                "tags": list[str],
                "image_prompt": str,
                "meta": {"engine", "model", "input_tokens", "output_tokens",
                         "tokens_used", "cost_usd", "cost_estimate"}
            }

        Raises:
            ValueError: 지원하지 않는 엔진이거나 API 키 미설정
            RuntimeError: API 호출 실패
        """
        if options is None:
            options = {}

        if engine not in ENGINE_CONFIGS:
            raise ValueError(f"지원하지 않는 엔진: {engine}. 가능한 값: {list(ENGINE_CONFIGS.keys())}")

        if engine not in self._clients:
            raise ValueError(
                f"{ENGINE_CONFIGS[engine]['label']} API 키가 설정되지 않았습니다. "
                f"config.yaml의 api_keys.{ENGINE_CONFIGS[engine]['api_key_field']}를 확인하세요."
            )

        dispatch = {
            "openai": self._generate_openai,
            "claude": self._generate_claude,
            "gemini": self._generate_gemini,
        }

        try:
            return dispatch[engine](model, system_prompt, user_prompt, options)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"AI 응답을 JSON으로 파싱할 수 없습니다: {e}") from e
        except Exception as e:
            logger.error("[%s/%s] 글 생성 실패: %s", engine, model, e, exc_info=True)
            raise RuntimeError(f"{ENGINE_CONFIGS[engine]['label']} 글 생성 실패: {e}") from e

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    def _generate_openai(self, model: str, system_prompt: str, user_prompt: str, options: dict) -> dict:
        client = self._clients["openai"]

        temperature = options.get("temperature", 0.7)
        max_tokens = options.get("max_tokens", 8000)
        response_format = options.get("response_format", "json_object")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": response_format},
            temperature=temperature,
            max_tokens=max_tokens,
        )

        raw_text = response.choices[0].message.content
        result = self._parse_json_response(raw_text)

        result["meta"] = self._build_meta(
            "openai", model,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )
        return self._normalize_result(result)

    # ------------------------------------------------------------------
    # Claude
    # ------------------------------------------------------------------

    def _generate_claude(self, model: str, system_prompt: str, user_prompt: str, options: dict) -> dict:
        client = self._clients["claude"]

        max_tokens = options.get("max_tokens", 8000)

        request_params = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        # Opus 4.7+는 temperature를 전송하면 400을 반환하므로 지원 모델에만 추가
        if model not in CLAUDE_NO_SAMPLING_MODELS:
            request_params["temperature"] = options.get("temperature", 0.7)

        message = client.messages.create(**request_params)

        raw_text = message.content[0].text
        result = self._parse_json_response(raw_text)

        result["meta"] = self._build_meta(
            "claude", model,
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        return self._normalize_result(result)

    # ------------------------------------------------------------------
    # Gemini
    # ------------------------------------------------------------------

    def _generate_gemini(self, model: str, system_prompt: str, user_prompt: str, options: dict) -> dict:
        from google.genai import types

        client = self._clients["gemini"]

        temperature = options.get("temperature", 0.7)
        max_tokens = options.get("max_tokens", 8000)

        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        # Gemini의 safety 필터에 걸렸는지 확인 (candidates 비어있음)
        if not response.candidates:
            raise RuntimeError("Gemini 응답이 안전 필터에 의해 차단되었습니다.")

        raw_text = response.text
        result = self._parse_json_response(raw_text)

        usage = getattr(response, "usage_metadata", None)
        if usage:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        else:
            input_tokens = output_tokens = 0

        result["meta"] = self._build_meta("gemini", model, input_tokens, output_tokens)
        return self._normalize_result(result)

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict:
        """AI 응답에서 JSON을 추출한다. 코드블록 감싸기도 처리. 잘린 JSON 복구 시도."""
        text = raw_text.strip()

        # ```json ... ``` 또는 ``` ... ``` 블록 제거
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if code_block:
            text = code_block.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 잘린 JSON 복구 시도: 열린 문자열/배열/객체를 닫는다
            repaired = ContentGenerator._try_repair_truncated_json(text)
            return json.loads(repaired)

    @staticmethod
    def _try_repair_truncated_json(text: str) -> str:
        """max_tokens 초과로 잘린 JSON을 복구 시도."""
        # 열린 문자열 닫기: 마지막 홀수 번째 이스케이프 안 된 따옴표 확인
        in_string = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\\' and in_string:
                i += 2
                continue
            if ch == '"':
                in_string = not in_string
            i += 1

        if in_string:
            text += '"'

        # 열린 괄호 수 계산 후 닫기
        open_braces = 0
        open_brackets = 0
        in_str = False
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\\' and in_str:
                i += 2
                continue
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == '{':
                    open_braces += 1
                elif ch == '}':
                    open_braces -= 1
                elif ch == '[':
                    open_brackets += 1
                elif ch == ']':
                    open_brackets -= 1
            i += 1

        # 마지막 불완전한 key-value 쌍 정리: 쉼표 뒤 미완성 부분 제거
        text = re.sub(r',\s*"[^"]*"\s*:\s*$', '', text)
        text = re.sub(r',\s*$', '', text)

        text += ']' * max(open_brackets, 0)
        text += '}' * max(open_braces, 0)

        return text

    @staticmethod
    def _normalize_result(result: dict) -> dict:
        """반환 형식을 통일한다. 누락된 필드에 기본값 부여."""
        return {
            "title": result.get("title", "(제목 없음)"),
            "body_html": result.get("body_html", result.get("body", result.get("content", ""))),
            "tags": result.get("tags", []),
            "image_prompt": result.get("image_prompt", ""),
            "meta": result.get("meta", {}),
        }

    def _build_meta(self, engine: str, model: str, input_tokens: int, output_tokens: int) -> dict:
        """토큰 사용량으로 meta 구성. 비용은 USD(cost_usd)로 저장하고 KRW는 표시용으로 함께 제공."""
        from modules import pricing

        cost_usd = pricing.calc_text_cost_usd(self.config, engine, model, input_tokens, output_tokens)
        return {
            "engine": engine,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_used": input_tokens + output_tokens,
            "cost_usd": round(cost_usd, 6),
            "cost_estimate": round(pricing.usd_to_krw(self.config, cost_usd), 2),
        }
