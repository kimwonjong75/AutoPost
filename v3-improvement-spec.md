# 네이버 블로그 자동화 시스템 v3.0 — 개선안 + 구현 명세서

> **목적**: 이 문서는 Cursor 등 AI 코딩 도구에서 바이브코딩으로 시스템을 구현할 때, 빠짐없이 참고할 수 있는 **완전한 명세서**입니다.
>
> **⚠️ 가격 정보 주의사항**: 아래 API 가격은 2026년 3월 기준 리서치 결과입니다. AI API 가격은 빠르게 변동하므로, 실제 구현 전 각 공급자의 공식 가격 페이지에서 반드시 교차 확인하세요.

---

## 1. 개선 요약 (v2.0 → v3.0 변경점)

| 항목 | v2.0 | v3.0 (이번 개선) |
|------|------|-----------------|
| AI 글 작성 엔진 | GPT-4o-mini / GPT-4o 고정 | **다중 엔진 선택** (OpenAI, Claude, Gemini) + 엔진별 동적 입력 폼 |
| 이미지 생성 | GPT Image 1 Mini + Pollinations | **다중 이미지 엔진** (GPT Image, Gemini Image, Flux, Ideogram, Pollinations) + 프롬프트 변수화 |
| 이미지 워크플로우 | 자동 생성 → 바로 첨부 | **생성 → 검토 → 선택 첨부** + 로컬 이미지 업로드 |
| 키워드 입력 | 단일 키워드 | **키워드 리스트** (CSV/줄바꿈) 일괄 입력 + 대기열 자동 추가 |
| 자료 첨부 | 없음 | **글 작성시 참고자료 첨부** (PDF, 이미지, 텍스트) + 영구 보관 |

---

## 2. AI 글 작성 — 다중 엔진 시스템

### 2-1. 지원 엔진 목록 및 API 사양

아래 가격은 **2026년 3월 리서치 기준**이며, 각 공급사의 공식 가격 페이지에서 최종 확인 필요합니다.

#### OpenAI (GPT 시리즈)

| 모델 | Input/1M토큰 | Output/1M토큰 | 한국어 품질 | 비고 |
|------|-------------|--------------|-----------|------|
| gpt-4o-mini | $0.15 | $0.60 | 양호 | 최저가, 대량 생성용 |
| gpt-4o | $2.50 | $10.00 | 우수 | 중급 품질 |
| gpt-4.1 | $2.00 | $8.00 | 우수 | 4o 후속, 코딩 특화 |
| gpt-4.1-mini | $0.40 | $1.60 | 양호 | 4o-mini 후속 |

**공식 가격 확인**: https://openai.com/api/pricing/

```python
# OpenAI API 호출 코드
from openai import OpenAI
client = OpenAI(api_key=config["openai_api_key"])

response = client.chat.completions.create(
    model="gpt-4o-mini",  # 설정에서 선택한 모델
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    response_format={"type": "json_object"},
    temperature=0.7,
    max_tokens=4000
)
result = json.loads(response.choices[0].message.content)
```

#### Anthropic (Claude 시리즈)

| 모델 | Input/1M토큰 | Output/1M토큰 | 한국어 품질 | 비고 |
|------|-------------|--------------|-----------|------|
| claude-haiku-4-5 | $1.00 | $5.00 | 양호 | 속도 최적화, 가성비 |
| claude-sonnet-4-5 | $3.00 | $15.00 | 매우 우수 | 균형형, 추천 |
| claude-sonnet-4-6 | $3.00 | $15.00 | 매우 우수 | 최신 Sonnet |
| claude-opus-4-5 | $5.00 | $25.00 | 최고 | 최고 품질 |

**공식 가격 확인**: https://docs.anthropic.com/en/docs/about-claude/models

```python
# Claude API 호출 코드
import anthropic
client = anthropic.Anthropic(api_key=config["claude_api_key"])

message = client.messages.create(
    model="claude-sonnet-4-5-20241022",  # 설정에서 선택한 모델
    max_tokens=4000,
    system=system_prompt,
    messages=[
        {"role": "user", "content": user_prompt}
    ]
)
result = json.loads(message.content[0].text)
```

#### Google (Gemini 시리즈)

| 모델 | Input/1M토큰 | Output/1M토큰 | 한국어 품질 | 비고 |
|------|-------------|--------------|-----------|------|
| gemini-2.5-flash | $0.15 | $0.60 | 양호 | 무료 티어 있음 |
| gemini-2.5-pro | $1.25 | $10.00 | 우수 | 2M 컨텍스트 |
| gemini-2.0-flash-lite | $0.075 | $0.30 | 보통 | 최저가 |

**공식 가격 확인**: https://ai.google.dev/gemini-api/docs/pricing

```python
# Gemini API 호출 코드
import google.generativeai as genai
genai.configure(api_key=config["gemini_api_key"])

model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content(
    full_prompt,
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        temperature=0.7,
        max_output_tokens=4000
    )
)
result = json.loads(response.text)
```

### 2-2. 엔진별 동적 입력 폼 설계

UI에서 AI 엔진을 선택하면, 해당 엔진에 맞는 설정 옵션이 동적으로 변경되어야 한다.

```python
# Streamlit 동적 폼 구현 예시
ENGINE_CONFIGS = {
    "openai": {
        "label": "OpenAI (GPT)",
        "api_key_field": "openai_api_key",
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o-mini (₩200/건·빠름)", "cost_per_1k": 0.2},
            {"id": "gpt-4o", "name": "GPT-4o (₩18/건·고품질)", "cost_per_1k": 18},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1-mini (₩3/건·신형)", "cost_per_1k": 3},
            {"id": "gpt-4.1", "name": "GPT-4.1 (₩14/건·코딩특화)", "cost_per_1k": 14},
        ],
        "extra_options": {
            "temperature": {"type": "slider", "min": 0.0, "max": 1.5, "default": 0.7},
            "response_format": {"type": "select", "options": ["json_object", "text"], "default": "json_object"},
        }
    },
    "claude": {
        "label": "Anthropic (Claude)",
        "api_key_field": "claude_api_key",
        "models": [
            {"id": "claude-haiku-4-5", "name": "Haiku 4.5 (₩8/건·빠름)", "cost_per_1k": 8},
            {"id": "claude-sonnet-4-5", "name": "Sonnet 4.5 (₩25/건·추천)", "cost_per_1k": 25},
            {"id": "claude-sonnet-4-6", "name": "Sonnet 4.6 (₩25/건·최신)", "cost_per_1k": 25},
            {"id": "claude-opus-4-5", "name": "Opus 4.5 (₩42/건·최고)", "cost_per_1k": 42},
        ],
        "extra_options": {
            "temperature": {"type": "slider", "min": 0.0, "max": 1.0, "default": 0.7},
            "max_tokens": {"type": "number", "default": 4000},
        }
    },
    "gemini": {
        "label": "Google (Gemini)",
        "api_key_field": "gemini_api_key",
        "models": [
            {"id": "gemini-2.0-flash-lite", "name": "Flash-Lite (₩0.5/건·최저가)", "cost_per_1k": 0.5},
            {"id": "gemini-2.5-flash", "name": "2.5 Flash (₩1/건·무료티어)", "cost_per_1k": 1},
            {"id": "gemini-2.5-pro", "name": "2.5 Pro (₩16/건·고성능)", "cost_per_1k": 16},
        ],
        "extra_options": {
            "temperature": {"type": "slider", "min": 0.0, "max": 2.0, "default": 0.7},
        }
    },
}
```

### 2-3. 통합 글 생성 모듈 (content_generator.py)

```python
# modules/content_generator.py
class ContentGenerator:
    """다중 AI 엔진을 지원하는 통합 글 생성기"""

    def __init__(self, config: dict):
        self.config = config
        self._init_clients()

    def _init_clients(self):
        """API 키가 설정된 엔진만 초기화"""
        self.clients = {}
        if self.config.get("openai_api_key"):
            from openai import OpenAI
            self.clients["openai"] = OpenAI(api_key=self.config["openai_api_key"])
        if self.config.get("claude_api_key"):
            import anthropic
            self.clients["claude"] = anthropic.Anthropic(api_key=self.config["claude_api_key"])
        if self.config.get("gemini_api_key"):
            import google.generativeai as genai
            genai.configure(api_key=self.config["gemini_api_key"])
            self.clients["gemini"] = genai

    def generate(self, engine: str, model: str, system_prompt: str,
                 user_prompt: str, options: dict = {}) -> dict:
        """
        통합 글 생성 인터페이스

        Returns:
            {
                "title": str,
                "body_html": str,
                "tags": list[str],
                "image_prompt": str,
                "meta": {"engine": str, "model": str, "tokens_used": int, "cost_estimate": float}
            }
        """
        if engine == "openai":
            return self._generate_openai(model, system_prompt, user_prompt, options)
        elif engine == "claude":
            return self._generate_claude(model, system_prompt, user_prompt, options)
        elif engine == "gemini":
            return self._generate_gemini(model, system_prompt, user_prompt, options)
        else:
            raise ValueError(f"지원하지 않는 엔진: {engine}")

    def _generate_openai(self, model, system_prompt, user_prompt, options):
        response = self.clients["openai"].chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": options.get("response_format", "json_object")},
            temperature=options.get("temperature", 0.7),
            max_tokens=options.get("max_tokens", 4000)
        )
        result = json.loads(response.choices[0].message.content)
        result["meta"] = {
            "engine": "openai",
            "model": model,
            "tokens_used": response.usage.total_tokens,
            "cost_estimate": self._calc_cost("openai", model, response.usage)
        }
        return result

    def _generate_claude(self, model, system_prompt, user_prompt, options):
        message = self.clients["claude"].messages.create(
            model=model,
            max_tokens=options.get("max_tokens", 4000),
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        text = message.content[0].text
        # Claude는 JSON을 코드블록으로 감쌀 수 있으므로 정리
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
        result = json.loads(text)
        result["meta"] = {
            "engine": "claude",
            "model": model,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
            "cost_estimate": self._calc_cost("claude", model, message.usage)
        }
        return result

    def _generate_gemini(self, model, system_prompt, user_prompt, options):
        genai_model = self.clients["gemini"].GenerativeModel(model)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        response = genai_model.generate_content(
            full_prompt,
            generation_config=self.clients["gemini"].GenerationConfig(
                response_mime_type="application/json",
                temperature=options.get("temperature", 0.7),
                max_output_tokens=options.get("max_tokens", 4000)
            )
        )
        result = json.loads(response.text)
        result["meta"] = {
            "engine": "gemini",
            "model": model,
            "tokens_used": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            "cost_estimate": 0  # Gemini usage_metadata로 계산
        }
        return result

    def _calc_cost(self, engine, model, usage):
        """비용 추정 (원화)"""
        # ENGINE_CONFIGS에서 단가 조회하여 계산
        # 실제 구현 시 모델별 단가 테이블 참조
        return 0.0
```

---

## 3. AI 이미지 생성 — 다중 엔진 + 프롬프트 변수화

### 3-1. 지원 이미지 엔진 목록

아래 가격은 **2026년 3월 리서치 기준**이며, 변동 가능합니다.

| 엔진 | 장당 비용 | 품질 | 한국어 텍스트 | API 방식 | 비고 |
|------|----------|------|-------------|---------|------|
| **GPT Image 1 Mini** | $0.005~$0.019 | 7.5/10 | 보통 | OpenAI API (동일 키) | Low/Medium/High 품질 선택 |
| **Gemini Image** | ~$0.039 | 7/10 | 양호 | Google AI Studio | 텍스트+이미지 동시 생성 가능 |
| **Flux 2 Schnell** | ~$0.015 | 7/10 | 보통 | Replicate/fal.ai | 최저가, 빠른 속도 |
| **Flux 2 Pro** | ~$0.055 | 8.5/10 | 보통 | Replicate/fal.ai/BFL | 최고 품질 사진 |
| **Ideogram 2.0** | ~$0.040 | 8/10 | 최고 | Ideogram API | 텍스트 렌더링 최강 |
| **Pollinations** | 무료 | 5/10 | 없음 | URL 호출 | 무료 폴백, 품질 낮음 |

**공식 가격 확인 링크**:
- OpenAI: https://openai.com/api/pricing/
- Google: https://ai.google.dev/gemini-api/docs/pricing
- Replicate (Flux): https://replicate.com/pricing
- fal.ai (Flux 등): https://fal.ai/pricing
- Ideogram: https://ideogram.ai/pricing

### 3-2. 이미지 프롬프트 변수화 시스템

글 내용에서 핵심 변수를 추출하여 프롬프트를 다양화한다.

```python
# modules/image_prompt_builder.py

class ImagePromptBuilder:
    """글 내용 기반 이미지 프롬프트 생성기"""

    # 프롬프트 다양화 변수
    STYLE_VARS = [
        "photorealistic, high quality photography",
        "clean modern illustration, flat design",
        "warm watercolor style, soft tones",
        "minimalist infographic style",
        "cozy lifestyle photography, natural lighting",
        "professional stock photo style, white background",
    ]

    MOOD_VARS = [
        "bright and cheerful",
        "warm and cozy",
        "clean and professional",
        "soft and inviting",
        "modern and sleek",
    ]

    COMPOSITION_VARS = [
        "centered composition, rule of thirds",
        "overhead flat lay view",
        "close-up detail shot",
        "wide angle establishing shot",
        "side view with depth of field",
    ]

    def build_prompts(self, article_data: dict, count: int = 3) -> list[dict]:
        """
        글 데이터에서 변수를 추출하여 다양한 이미지 프롬프트를 생성

        Args:
            article_data: {"title": str, "body_html": str, "tags": list, "image_prompt": str}
            count: 생성할 프롬프트 변형 수

        Returns:
            [
                {
                    "prompt": str,          # 영어 프롬프트
                    "style": str,           # 사용된 스타일
                    "negative_prompt": str,  # 네거티브 프롬프트
                    "aspect_ratio": str,     # 비율 (16:9, 4:3 등)
                }
            ]
        """
        base_prompt = article_data.get("image_prompt", "")
        tags = article_data.get("tags", [])
        title = article_data.get("title", "")

        prompts = []
        for i in range(count):
            style = random.choice(self.STYLE_VARS)
            mood = random.choice(self.MOOD_VARS)
            composition = random.choice(self.COMPOSITION_VARS)

            enhanced_prompt = (
                f"{base_prompt}, {style}, {mood}, {composition}, "
                f"related to {' '.join(tags[:3])}, "
                f"no text, no watermark, high resolution, blog thumbnail"
            )

            prompts.append({
                "prompt": enhanced_prompt,
                "style": style,
                "negative_prompt": "text, watermark, logo, blurry, low quality, distorted, ugly, nsfw",
                "aspect_ratio": "16:9",  # 블로그 썸네일 최적 비율
            })

        return prompts
```

### 3-3. 통합 이미지 생성 모듈 (image_generator.py)

```python
# modules/image_generator.py
import os, requests, base64, time
from pathlib import Path

class ImageGenerator:
    """다중 이미지 생성 엔진 통합"""

    def __init__(self, config: dict):
        self.config = config
        self.image_dir = Path(config.get("image_dir", "./data/images"))
        self.image_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, engine: str, prompt: str, options: dict = {}) -> dict:
        """
        통합 이미지 생성 인터페이스

        Returns:
            {
                "local_path": str,      # 로컬 저장 경로
                "prompt_used": str,     # 사용된 프롬프트
                "engine": str,          # 사용된 엔진
                "cost_estimate": float, # 예상 비용 (원)
                "width": int,
                "height": int,
            }
        """
        handlers = {
            "gpt_image": self._gen_gpt_image,
            "gemini_image": self._gen_gemini_image,
            "flux_schnell": self._gen_flux,
            "flux_pro": self._gen_flux,
            "ideogram": self._gen_ideogram,
            "pollinations": self._gen_pollinations,
        }

        handler = handlers.get(engine)
        if not handler:
            raise ValueError(f"지원하지 않는 이미지 엔진: {engine}")

        return handler(prompt, options)

    def _gen_gpt_image(self, prompt: str, options: dict) -> dict:
        """OpenAI GPT Image 1 API"""
        from openai import OpenAI
        client = OpenAI(api_key=self.config["openai_api_key"])

        quality = options.get("quality", "medium")  # low, medium, high
        size = options.get("size", "1024x1024")

        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
        )

        # base64로 반환됨 → 파일로 저장
        image_data = base64.b64decode(response.data[0].b64_json)
        filename = f"gpt_{int(time.time())}.png"
        filepath = self.image_dir / filename
        filepath.write_bytes(image_data)

        cost_map = {"low": 7, "medium": 19, "high": 55}  # 원화 기준 추정
        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "gpt_image",
            "cost_estimate": cost_map.get(quality, 19),
            "width": int(size.split("x")[0]),
            "height": int(size.split("x")[1]),
        }

    def _gen_gemini_image(self, prompt: str, options: dict) -> dict:
        """Google Gemini 이미지 생성"""
        import google.generativeai as genai
        genai.configure(api_key=self.config["gemini_api_key"])

        model = genai.ImageGenerationModel("imagen-3.0-generate-002")
        response = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio=options.get("aspect_ratio", "16:9"),
        )

        filename = f"gemini_{int(time.time())}.png"
        filepath = self.image_dir / filename
        response.images[0].save(str(filepath))

        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "gemini_image",
            "cost_estimate": 55,  # ~$0.039
            "width": 1024, "height": 576,
        }

    def _gen_flux(self, prompt: str, options: dict) -> dict:
        """Flux (Replicate 또는 fal.ai 경유)"""
        import replicate

        model_map = {
            "flux_schnell": "black-forest-labs/flux-schnell",
            "flux_pro": "black-forest-labs/flux-pro",
        }
        engine = options.get("_engine", "flux_schnell")
        model_id = model_map.get(engine, model_map["flux_schnell"])

        output = replicate.run(
            model_id,
            input={
                "prompt": prompt,
                "aspect_ratio": options.get("aspect_ratio", "16:9"),
                "num_outputs": 1,
            }
        )

        # URL에서 이미지 다운로드
        image_url = output[0] if isinstance(output, list) else str(output)
        filename = f"flux_{int(time.time())}.png"
        filepath = self.image_dir / filename
        img_data = requests.get(image_url).content
        filepath.write_bytes(img_data)

        cost_map = {"flux_schnell": 21, "flux_pro": 77}
        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": engine,
            "cost_estimate": cost_map.get(engine, 21),
            "width": 1024, "height": 576,
        }

    def _gen_ideogram(self, prompt: str, options: dict) -> dict:
        """Ideogram API (한국어 텍스트 포함 이미지에 최적)"""
        response = requests.post(
            "https://api.ideogram.ai/generate",
            headers={"Api-Key": self.config["ideogram_api_key"]},
            json={
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": options.get("aspect_ratio", "ASPECT_16_9"),
                    "model": "V_2",
                }
            }
        )
        data = response.json()
        image_url = data["data"][0]["url"]

        filename = f"ideogram_{int(time.time())}.png"
        filepath = self.image_dir / filename
        img_data = requests.get(image_url).content
        filepath.write_bytes(img_data)

        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "ideogram",
            "cost_estimate": 56,  # ~$0.04
            "width": 1024, "height": 576,
        }

    def _gen_pollinations(self, prompt: str, options: dict) -> dict:
        """Pollinations (무료 폴백)"""
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=576&seed={int(time.time())}"

        img_data = requests.get(url, timeout=60).content
        filename = f"poll_{int(time.time())}.jpg"
        filepath = self.image_dir / filename
        filepath.write_bytes(img_data)

        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "pollinations",
            "cost_estimate": 0,
            "width": 1024, "height": 576,
        }

    def load_local_image(self, source_path: str, keyword_id: str) -> dict:
        """로컬 이미지 불러오기"""
        import shutil
        ext = Path(source_path).suffix
        filename = f"local_{keyword_id}_{int(time.time())}{ext}"
        filepath = self.image_dir / filename
        shutil.copy2(source_path, filepath)

        from PIL import Image
        with Image.open(filepath) as img:
            w, h = img.size

        return {
            "local_path": str(filepath),
            "prompt_used": "(로컬 업로드)",
            "engine": "local",
            "cost_estimate": 0,
            "width": w, "height": h,
        }
```

### 3-4. 이미지 엔진 설정 (config 구조)

```python
IMAGE_ENGINE_CONFIGS = {
    "gpt_image": {
        "label": "GPT Image 1 Mini",
        "api_key_field": "openai_api_key",  # OpenAI와 동일 키
        "cost_per_image": "₩7~55 (품질별)",
        "options": {
            "quality": {"type": "select", "options": ["low", "medium", "high"], "default": "medium"},
            "size": {"type": "select", "options": ["1024x1024", "1536x1024", "1024x1536"], "default": "1536x1024"},
        }
    },
    "gemini_image": {
        "label": "Google Imagen 3",
        "api_key_field": "gemini_api_key",
        "cost_per_image": "~₩55",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["16:9", "4:3", "1:1", "3:4"], "default": "16:9"},
        }
    },
    "flux_schnell": {
        "label": "Flux 2 Schnell (빠름/저렴)",
        "api_key_field": "replicate_api_key",
        "cost_per_image": "~₩21",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["16:9", "4:3", "1:1"], "default": "16:9"},
        }
    },
    "flux_pro": {
        "label": "Flux 2 Pro (고품질)",
        "api_key_field": "replicate_api_key",
        "cost_per_image": "~₩77",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["16:9", "4:3", "1:1"], "default": "16:9"},
        }
    },
    "ideogram": {
        "label": "Ideogram 2.0 (한국어 텍스트 최강)",
        "api_key_field": "ideogram_api_key",
        "cost_per_image": "~₩56",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["ASPECT_16_9", "ASPECT_4_3", "ASPECT_1_1"], "default": "ASPECT_16_9"},
        }
    },
    "pollinations": {
        "label": "Pollinations (무료)",
        "api_key_field": None,  # API 키 불필요
        "cost_per_image": "₩0",
        "options": {}
    },
}
```

---

## 4. 이미지 검토 및 첨부 워크플로우

### 4-1. 워크플로우 흐름

```
글 생성 완료
    │
    ▼
[이미지 자동 생성] ← 프롬프트 변수화로 3~5개 변형 생성
    │
    ▼
[이미지 검토 화면]
    ├─ 생성된 이미지 그리드 (3~5개)
    ├─ 각 이미지에: [선택] [삭제] [재생성] 버튼
    ├─ [다른 엔진으로 재생성] 버튼
    ├─ [프롬프트 직접 수정 후 재생성] 입력란
    ├─ [로컬 이미지 업로드] 버튼
    └─ 선택된 이미지에 체크표시
    │
    ▼
[선택된 이미지 첨부 확정]
    │
    ▼
글 검토 화면에서 최종 확인
```

### 4-2. UI 구현 명세 (Streamlit)

```python
# 이미지 검토 섹션
def render_image_review(article_data, images: list[dict]):
    """이미지 검토 및 선택 UI"""

    st.subheader("🖼️ 이미지 검토")

    # 이미지 엔진 선택 + 재생성
    col1, col2 = st.columns([2, 1])
    with col1:
        img_engine = st.selectbox(
            "이미지 생성 엔진",
            options=list(IMAGE_ENGINE_CONFIGS.keys()),
            format_func=lambda x: IMAGE_ENGINE_CONFIGS[x]["label"]
        )
    with col2:
        regenerate_count = st.number_input("생성 수", min_value=1, max_value=5, value=3)

    if st.button("🎨 이미지 생성", key="gen_images"):
        builder = ImagePromptBuilder()
        prompts = builder.build_prompts(article_data, count=regenerate_count)
        generator = ImageGenerator(config)
        new_images = []
        progress = st.progress(0)
        for i, p in enumerate(prompts):
            result = generator.generate(img_engine, p["prompt"], {
                "negative_prompt": p["negative_prompt"],
                "aspect_ratio": p["aspect_ratio"],
                "_engine": img_engine,
            })
            new_images.append(result)
            progress.progress((i + 1) / len(prompts))
        st.session_state["generated_images"] = new_images

    # 생성된 이미지 그리드 표시
    if "generated_images" in st.session_state:
        cols = st.columns(min(len(st.session_state["generated_images"]), 3))
        selected = st.session_state.get("selected_images", [])

        for i, img in enumerate(st.session_state["generated_images"]):
            with cols[i % 3]:
                st.image(img["local_path"], use_container_width=True)
                st.caption(f"{img['engine']} | ₩{img['cost_estimate']}")
                is_selected = st.checkbox("선택", key=f"img_sel_{i}",
                                          value=i in selected)
                if is_selected and i not in selected:
                    selected.append(i)
                elif not is_selected and i in selected:
                    selected.remove(i)

        st.session_state["selected_images"] = selected

    # 프롬프트 직접 수정 후 재생성
    with st.expander("✏️ 프롬프트 직접 수정"):
        custom_prompt = st.text_area(
            "이미지 프롬프트 (영어)",
            value=article_data.get("image_prompt", ""),
            height=100
        )
        if st.button("이 프롬프트로 생성"):
            result = generator.generate(img_engine, custom_prompt)
            st.session_state["generated_images"].append(result)
            st.rerun()

    # 로컬 이미지 업로드
    uploaded = st.file_uploader(
        "📤 로컬 이미지 업로드",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )
    if uploaded:
        for f in uploaded:
            temp_path = f"/tmp/{f.name}"
            with open(temp_path, "wb") as tf:
                tf.write(f.getbuffer())
            result = generator.load_local_image(temp_path, article_data.get("keyword_id", "unknown"))
            st.session_state.setdefault("generated_images", []).append(result)
        st.rerun()
```

---

## 5. 키워드 리스트 일괄 입력

### 5-1. 입력 방식

```python
# 키워드 리스트 입력 UI
def render_keyword_list_input():
    """키워드 리스트 일괄 입력"""

    st.subheader("📋 키워드 리스트 입력")

    input_method = st.radio(
        "입력 방식",
        ["직접 입력 (줄바꿈 구분)", "CSV 파일 업로드", "구글 시트에서 가져오기"],
        horizontal=True
    )

    keywords = []

    if input_method == "직접 입력 (줄바꿈 구분)":
        text = st.text_area(
            "키워드 목록 (한 줄에 하나씩)",
            placeholder="겨울철 난방비 절약\n삼성 온풍기 SEH-P2100 후기\n원룸 단열 방법\n...",
            height=200
        )
        keywords = [k.strip() for k in text.split("\n") if k.strip()]

    elif input_method == "CSV 파일 업로드":
        uploaded = st.file_uploader("CSV 파일", type=["csv", "txt"])
        if uploaded:
            import csv, io
            content = uploaded.read().decode("utf-8-sig")
            reader = csv.reader(io.StringIO(content))
            for row in reader:
                if row:
                    # 첫 번째 열을 키워드로, 두 번째 열이 있으면 글 유형으로
                    kw = row[0].strip()
                    content_type = row[1].strip() if len(row) > 1 else "정보성"
                    blog_id = row[2].strip() if len(row) > 2 else None
                    keywords.append({
                        "keyword": kw,
                        "content_type": content_type,
                        "blog_id": blog_id
                    })

    elif input_method == "구글 시트에서 가져오기":
        if st.button("🔄 구글 시트 동기화"):
            # gspread로 키워드 시트에서 status="대기" 항목 가져오기
            keywords = fetch_pending_keywords_from_sheet()

    # 키워드 리스트 미리보기
    if keywords:
        st.write(f"**총 {len(keywords)}개 키워드**")
        # 테이블로 미리보기
        df_data = []
        for k in keywords:
            if isinstance(k, dict):
                df_data.append(k)
            else:
                df_data.append({"keyword": k, "content_type": "정보성", "blog_id": "자동배정"})
        st.dataframe(df_data, use_container_width=True)

        # 일괄 생성 옵션
        col1, col2, col3 = st.columns(3)
        with col1:
            batch_engine = st.selectbox("AI 엔진", list(ENGINE_CONFIGS.keys()),
                                        format_func=lambda x: ENGINE_CONFIGS[x]["label"])
        with col2:
            batch_model = st.selectbox("모델", [m["id"] for m in ENGINE_CONFIGS[batch_engine]["models"]])
        with col3:
            use_batch_api = st.checkbox("Batch API 사용 (50% 할인, 24시간)", value=False)

        if st.button("✨ 전체 키워드 일괄 생성 시작"):
            # 키워드를 발행 대기열(SQLite)에 추가
            add_keywords_to_queue(keywords, batch_engine, batch_model, use_batch_api)
            st.success(f"{len(keywords)}개 키워드가 생성 대기열에 추가되었습니다!")
```

### 5-2. CSV 형식 예시

```csv
키워드,글유형,대상블로그
겨울철 난방비 절약,정보성,blog_01
삼성 온풍기 SEH-P2100 후기,상품홍보,blog_01
2026년 가성비 노트북 TOP5,정보성,blog_02
로지텍 MX Keys S 키보드 리뷰,상품홍보,blog_02
집에서 만드는 크림파스타,정보성,blog_03
```

---

## 6. 글 작성 시 참고자료 첨부 + 영구 보관

### 6-1. DB 스키마 (SQLite + Peewee)

```python
# modules/models.py
from peewee import *
import datetime

db = SqliteDatabase("./data/blog_auto.db")

class BaseModel(Model):
    class Meta:
        database = db

class Attachment(BaseModel):
    """참고자료 첨부 파일"""
    id = AutoField()
    keyword_id = CharField(index=True)          # 연결된 키워드 ID
    original_filename = CharField()              # 원본 파일명
    stored_path = CharField()                    # 저장 경로
    file_type = CharField()                      # pdf, image, text, url
    file_size = IntegerField(default=0)          # 바이트
    description = TextField(null=True)           # 사용자 메모
    extracted_text = TextField(null=True)        # 텍스트 추출 결과 (PDF/이미지 OCR)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "attachments"

class GeneratedArticle(BaseModel):
    """생성된 글"""
    id = AutoField()
    keyword_id = CharField(index=True)
    engine = CharField()                         # openai, claude, gemini
    model = CharField()                          # 사용된 모델명
    title = CharField()
    body_html = TextField()
    tags = TextField()                           # JSON 배열 문자열
    image_prompt = TextField(null=True)
    status = CharField(default="생성완료")        # 생성완료, 검토완료, 발행완료, 실패
    cost_estimate = FloatField(default=0)        # 원화
    tokens_used = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "generated_articles"

class GeneratedImage(BaseModel):
    """생성된 이미지"""
    id = AutoField()
    keyword_id = CharField(index=True)
    article_id = ForeignKeyField(GeneratedArticle, null=True)
    engine = CharField()                         # gpt_image, flux_schnell 등
    prompt_used = TextField()
    local_path = CharField()
    width = IntegerField()
    height = IntegerField()
    cost_estimate = FloatField(default=0)
    is_selected = BooleanField(default=False)    # 최종 첨부용으로 선택 여부
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "generated_images"

class PublishLog(BaseModel):
    """발행 기록"""
    id = AutoField()
    blog_id = CharField()
    keyword_id = CharField()
    article_id = ForeignKeyField(GeneratedArticle)
    title = CharField()
    post_url = CharField(null=True)
    ip_address = CharField(null=True)
    status = CharField()                         # 성공, 실패
    error_message = TextField(null=True)
    screenshot_path = CharField(null=True)
    retry_count = IntegerField(default=0)
    delay_seconds = IntegerField(default=0)      # 이전 발행과의 간격
    published_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "publish_logs"

# 테이블 생성
db.create_tables([Attachment, GeneratedArticle, GeneratedImage, PublishLog])
```

### 6-2. 참고자료 첨부 모듈

```python
# modules/attachment_manager.py
import shutil, hashlib
from pathlib import Path
from PIL import Image

class AttachmentManager:
    """참고자료 첨부 파일 관리"""

    STORAGE_DIR = Path("./data/attachments")
    ALLOWED_TYPES = {
        "pdf": ["pdf"],
        "image": ["jpg", "jpeg", "png", "webp", "gif"],
        "text": ["txt", "md", "csv", "json"],
    }

    def __init__(self):
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, keyword_id: str, uploaded_file, description: str = "") -> Attachment:
        """첨부파일 저장 + DB 등록"""
        ext = uploaded_file.name.split(".")[-1].lower()
        file_type = self._detect_type(ext)

        # 고유 경로로 저장
        file_hash = hashlib.md5(uploaded_file.read()).hexdigest()[:8]
        uploaded_file.seek(0)
        stored_name = f"{keyword_id}_{file_hash}.{ext}"
        stored_path = self.STORAGE_DIR / keyword_id / stored_name
        stored_path.parent.mkdir(parents=True, exist_ok=True)

        with open(stored_path, "wb") as f:
            f.write(uploaded_file.read())

        # 텍스트 추출 (PDF/이미지는 별도 처리)
        extracted = self._extract_text(stored_path, file_type, ext)

        return Attachment.create(
            keyword_id=keyword_id,
            original_filename=uploaded_file.name,
            stored_path=str(stored_path),
            file_type=file_type,
            file_size=stored_path.stat().st_size,
            description=description,
            extracted_text=extracted,
        )

    def _detect_type(self, ext: str) -> str:
        for file_type, exts in self.ALLOWED_TYPES.items():
            if ext in exts:
                return file_type
        return "unknown"

    def _extract_text(self, path: Path, file_type: str, ext: str) -> str:
        """PDF, 이미지, 텍스트에서 내용 추출"""
        if file_type == "text":
            return path.read_text(encoding="utf-8", errors="ignore")[:10000]
        elif file_type == "pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return text[:10000]
            except:
                return "(PDF 텍스트 추출 실패)"
        elif file_type == "image":
            return "(이미지 - 텍스트 추출 미지원)"
        return ""

    def get_attachments(self, keyword_id: str) -> list:
        """키워드에 연결된 첨부파일 조회"""
        return list(Attachment.select().where(Attachment.keyword_id == keyword_id))

    def build_context_for_prompt(self, keyword_id: str) -> str:
        """첨부자료를 프롬프트 컨텍스트로 변환"""
        attachments = self.get_attachments(keyword_id)
        if not attachments:
            return ""

        context_parts = ["[참고자료]"]
        for att in attachments:
            if att.extracted_text:
                context_parts.append(
                    f"\n--- {att.original_filename} ---\n"
                    f"{att.extracted_text[:3000]}"
                )
            if att.description:
                context_parts.append(f"(메모: {att.description})")

        return "\n".join(context_parts)
```

### 6-3. UI에서 참고자료 첨부

```python
# 글 생성 화면의 참고자료 섹션
def render_attachment_section(keyword_id: str):
    """참고자료 첨부 UI"""
    manager = AttachmentManager()

    st.markdown("**📎 참고자료 첨부**")
    st.caption("첨부된 자료는 AI 글 작성 시 참고 컨텍스트로 사용되며, 영구 보관됩니다.")

    # 기존 첨부파일 표시
    existing = manager.get_attachments(keyword_id)
    if existing:
        for att in existing:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.text(f"📄 {att.original_filename}")
            with col2:
                st.text(f"{att.file_type} | {att.file_size // 1024}KB")
            with col3:
                if st.button("🗑️", key=f"del_{att.id}"):
                    att.delete_instance()
                    st.rerun()

    # 새 파일 업로드
    uploaded = st.file_uploader(
        "파일 추가 (PDF, 이미지, 텍스트)",
        type=["pdf", "jpg", "jpeg", "png", "txt", "md", "csv"],
        accept_multiple_files=True,
        key=f"attach_{keyword_id}"
    )
    description = st.text_input("메모 (선택)", key=f"desc_{keyword_id}")

    if uploaded:
        for f in uploaded:
            manager.save(keyword_id, f, description)
        st.success(f"{len(uploaded)}개 파일이 첨부되었습니다.")
        st.rerun()
```

---

## 7. 수정된 폴더 구조 (v3.0)

```
naver-blog-automation/
├── app.py                        # Streamlit 메인 앱
├── config.yaml                   # 설정 파일 (API 키, 경로 등)
├── requirements.txt              # Python 패키지 목록
│
├── modules/
│   ├── __init__.py
│   ├── content_generator.py      # ★ 다중 AI 엔진 글 생성 (OpenAI/Claude/Gemini)
│   ├── image_generator.py        # ★ 다중 이미지 엔진 (GPT/Gemini/Flux/Ideogram/Poll)
│   ├── image_prompt_builder.py   # ★ 이미지 프롬프트 변수화
│   ├── attachment_manager.py     # ★ 참고자료 첨부 + 영구 보관
│   ├── models.py                 # ★ Peewee DB 모델 (Attachment, Article, Image, Log)
│   ├── google_sheet.py           # 구글 시트 읽기/쓰기
│   ├── ip_changer.py             # ADB 비행기모드 제어
│   ├── blog_publisher.py         # Selenium 블로그 발행
│   ├── cookie_manager.py         # 쿠키/세션 관리
│   ├── error_handler.py          # 에러 복구 + 재시도 로직
│   └── scheduler.py              # APScheduler 예약 생성
│
├── pages/                        # ★ Streamlit 멀티페이지 (새 구조)
│   ├── 1_📊_대시보드.py
│   ├── 2_✍️_글_생성.py
│   ├── 3_👁️_검토_수정.py
│   ├── 4_🚀_발행.py
│   └── 5_⚙️_설정.py
│
├── templates/
│   ├── info_prompt.txt            # 정보성 글 프롬프트
│   └── product_prompt.txt         # 상품홍보 글 프롬프트
│
├── data/
│   ├── blog_auto.db               # SQLite 데이터베이스
│   ├── attachments/               # ★ 참고자료 영구 보관
│   │   ├── KW-001/
│   │   │   ├── KW-001_a1b2c3d4.pdf
│   │   │   └── KW-001_e5f6g7h8.jpg
│   │   └── KW-002/
│   ├── cookies/                   # 블로그별 쿠키 파일
│   └── images/                    # 생성된 이미지 저장
│
├── chrome_profiles/               # 블로그별 Chrome 프로필
│
└── logs/                          # 에러 로그 + 스크린샷
    ├── error_screenshots/
    └── publish.log
```

---

## 8. 수정된 requirements.txt (v3.0)

```
# === UI ===
streamlit==1.40.0

# === AI 글 작성 (다중 엔진) ===
openai==1.60.0                     # OpenAI GPT + 이미지
anthropic==0.42.0                  # Claude
google-generativeai==0.8.0         # Gemini

# === AI 이미지 생성 (다중 엔진) ===
replicate==1.0.0                   # Flux (Replicate 경유)
# ideogram은 requests로 REST 호출

# === 브라우저 자동화 ===
undetected-chromedriver==3.5.5
pyperclip==1.9.0

# === 데이터 ===
gspread==6.1.0
oauth2client==4.1.3
peewee==3.17.0

# === 유틸리티 ===
Pillow==10.4.0
requests==2.32.0
pyyaml==6.0.2
apscheduler==3.10.4
pdfplumber==0.11.0                 # ★ PDF 텍스트 추출 (참고자료용)
```

---

## 9. config.yaml 구조 (v3.0)

```yaml
# === API 키 ===
api_keys:
  openai: "sk-proj-..."          # GPT + GPT Image 공유
  claude: "sk-ant-..."           # Anthropic Claude
  gemini: "AIza..."              # Google Gemini + Imagen
  replicate: "r8_..."            # Flux (Replicate)
  ideogram: "..."                # Ideogram (선택)

# === 기본 설정 ===
defaults:
  text_engine: "openai"          # 기본 글 작성 엔진
  text_model: "gpt-4o-mini"      # 기본 모델
  image_engine: "gpt_image"      # 기본 이미지 엔진
  image_quality: "medium"        # GPT Image 품질
  image_count: 3                 # 이미지 생성 수

# === 구글 시트 ===
google_sheet:
  service_account_json: "./data/google-service-account.json"
  sheet_id: "1BxiM..."

# === 발행 설정 ===
publish:
  inter_blog_delay: [60, 180]    # 블로그 간 대기 (초, 랜덤)
  inter_post_delay: [30, 90]     # 같은 블로그 연속 (초, 랜덤)
  action_delay: [1.5, 4.0]       # 에디터 내 액션 (초, 랜덤)
  max_retries: 2                 # 실패 시 최대 재시도
  browser_engine: "undetected_chromedriver"  # 또는 "nodriver"

# === ADB ===
adb:
  path: "C:\\platform-tools\\adb.exe"
  airplane_on_wait: 8            # 비행기모드 ON 후 대기 (초)
  airplane_off_wait: 20          # 비행기모드 OFF 후 대기 (초)
  ip_check_retries: 3            # IP 확인 재시도 횟수

# === 경로 ===
paths:
  image_dir: "./data/images"
  attachment_dir: "./data/attachments"
  cookie_dir: "./data/cookies"
  chrome_profiles_dir: "./chrome_profiles"
  log_dir: "./logs"
```

---

## 10. 구현 순서 (바이브코딩 로드맵)

Cursor에서 순서대로 구현하면 된다. 각 단계가 독립적으로 테스트 가능하도록 설계.

### Phase 1: 핵심 인프라 (1~2일)
1. `config.yaml` 작성
2. `modules/models.py` — DB 스키마 정의 + 테이블 생성
3. `modules/content_generator.py` — OpenAI 한 개만 먼저 연동
4. 터미널에서 글 생성 테스트

### Phase 2: 다중 AI 엔진 (1~2일)
5. `content_generator.py`에 Claude, Gemini 추가
6. 엔진별 동적 폼 로직 (ENGINE_CONFIGS dict)
7. 각 엔진 테스트

### Phase 3: 이미지 시스템 (2~3일)
8. `modules/image_generator.py` — GPT Image 먼저
9. `modules/image_prompt_builder.py` — 프롬프트 변수화
10. Flux, Ideogram, Pollinations 추가
11. 로컬 이미지 업로드 기능

### Phase 4: UI 구현 (3~5일)
12. `app.py` + `pages/` 멀티페이지 Streamlit 앱
13. 글 생성 페이지 (엔진 선택 + 키워드 리스트 + 자료 첨부)
14. 이미지 검토 페이지 (그리드 + 선택 + 재생성)
15. 검토/수정 페이지 (미리보기 + 에디터)
16. 발행 페이지 (대기열 + 진행률)
17. 대시보드 (현황 + 비용)
18. 설정 페이지 (API 키 + 발행설정 + 프롬프트 관리)

### Phase 5: 참고자료 시스템 (1일)
19. `modules/attachment_manager.py`
20. PDF 텍스트 추출 연동
21. 프롬프트 컨텍스트에 자동 주입

### Phase 6: 발행 자동화 (3~5일)
22. `modules/ip_changer.py` — ADB Android 12+ 호환
23. `modules/blog_publisher.py` — undetected-chromedriver
24. `modules/cookie_manager.py` — 계정별 쿠키
25. `modules/error_handler.py` — 재시도 + 스크린샷
26. 구글 시트 연동 (발행 결과 기록)

### Phase 7: 안정화 (지속)
27. 에러 로깅 고도화
28. APScheduler 예약 생성
29. 비용 추적 대시보드
30. 프롬프트 A/B 테스트

---

## 11. Cursor에 전달할 초기 프롬프트 예시

Cursor에서 프로젝트를 시작할 때, 아래 프롬프트를 첫 지시로 사용:

```
이 프로젝트는 포스팅 자동발행 시스템이야.
Python + Streamlit으로 구현하고, 아래 핵심 기능이 필요해:

1. AI 글 작성: OpenAI, Claude, Gemini 3개 엔진 중 선택 가능
   - 엔진 선택 시 모델 목록과 옵션이 동적으로 변경
   - 키워드 리스트(줄바꿈/CSV) 일괄 입력 지원
   - 참고자료 첨부(PDF, 이미지, 텍스트) → AI 프롬프트에 자동 주입

2. AI 이미지 생성: GPT Image, Gemini, Flux, Ideogram, Pollinations 중 선택
   - 글 내용에서 변수 추출하여 프롬프트 다양화 (3~5개 변형)
   - 생성된 이미지 그리드로 미리보기 → 선택 첨부
   - 로컬 이미지 업로드도 가능

3. 데이터: 구글 시트(운영) + SQLite/Peewee(로컬 캐시/큐)
4. UI: Streamlit 멀티페이지 (대시보드/글생성/검토/발행/설정)
5. 발행: undetected-chromedriver + ADB IP 변경

먼저 config.yaml과 modules/models.py부터 만들어줘.
프로젝트 루트에 위의 명세서(v3-spec.md)를 참고해.
```

---

## 12. 리스크 및 주의사항

| 항목 | 내용 |
|------|------|
| **API 가격 변동** | 이 문서의 가격은 2026년 3월 리서치 기준. AI API 가격은 수시로 변경되므로 구현 전 공식 페이지에서 반드시 재확인 |
| **무료 티어 제한** | Gemini 무료 티어는 분당 15건 제한. 대량 생성 시 유료 전환 필요 |
| **Replicate 계정** | Flux 사용 시 Replicate 또는 fal.ai 계정 별도 필요 |
| **Ideogram API** | 2026년 3월 기준 API 접근이 유료 플랜(Plus 이상)에서만 가능할 수 있음. 공식 문서 확인 필요 |
| **네이버 이용약관** | 자동화된 블로그 발행은 네이버 이용약관 위반 가능. 계정 정지 리스크 상존 |
| **Claude API JSON** | Claude는 JSON 출력이 코드블록으로 감싸일 수 있음. 파싱 시 ```json 제거 필요 |
| **Gemini JSON** | `response_mime_type="application/json"` 설정 시 안정적으로 JSON 반환 |
| **이미지 저작권** | AI 생성 이미지의 상업적 사용 시 각 엔진의 이용약관 확인 필요 |
