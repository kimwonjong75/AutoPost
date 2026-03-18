"""
다중 이미지 생성 엔진 통합 모듈
GPT Image, Gemini Image, Flux (Schnell/Pro), Ideogram, Pollinations를 지원한다.
"""

import base64
import logging
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# 병렬 이미지 생성 최대 워커 수 (API rate limit 고려)
MAX_PARALLEL_WORKERS = 3

# 엔진별 설정 정보
IMAGE_ENGINE_CONFIGS = {
    "gpt_image": {
        "label": "GPT Image 1 Mini",
        "api_key_field": "openai_api_key",
        "cost_per_image": "₩7~55 (품질별)",
        "options": {
            "quality": {"type": "select", "options": ["low", "medium", "high"], "default": "medium"},
            "size": {"type": "select", "options": ["1024x1024", "1536x1024", "1024x1536"], "default": "1536x1024"},
        },
    },
    "gemini_image": {
        "label": "Google Imagen 3",
        "api_key_field": "gemini_api_key",
        "cost_per_image": "~₩55",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["16:9", "4:3", "1:1", "3:4"], "default": "16:9"},
        },
    },
    "flux_schnell": {
        "label": "Flux 2 Schnell (빠름/저렴)",
        "api_key_field": "replicate_api_key",
        "cost_per_image": "~₩21",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["16:9", "4:3", "1:1"], "default": "16:9"},
        },
    },
    "flux_pro": {
        "label": "Flux 2 Pro (고품질)",
        "api_key_field": "replicate_api_key",
        "cost_per_image": "~₩77",
        "options": {
            "aspect_ratio": {"type": "select", "options": ["16:9", "4:3", "1:1"], "default": "16:9"},
        },
    },
    "ideogram": {
        "label": "Ideogram 2.0 (한국어 텍스트 최강)",
        "api_key_field": "ideogram_api_key",
        "cost_per_image": "~₩56",
        "options": {
            "aspect_ratio": {
                "type": "select",
                "options": ["ASPECT_16_9", "ASPECT_4_3", "ASPECT_1_1"],
                "default": "ASPECT_16_9",
            },
        },
    },
    "gemini_flash_image": {
        "label": "Gemini 2.0 Flash (네이티브 이미지)",
        "api_key_field": "gemini_api_key",
        "cost_per_image": "₩0 (무료티어)",
        "options": {},
    },
    "pollinations": {
        "label": "Pollinations (무료)",
        "api_key_field": None,
        "cost_per_image": "₩0",
        "options": {},
    },
}


class ImageGenerator:
    """다중 이미지 생성 엔진 통합"""

    def __init__(self, config: dict):
        self.config = config
        self.image_dir = Path(config.get("image_dir", "./data/images"))
        self.image_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 엔진 사용 가능 여부 확인
    # ------------------------------------------------------------------

    def get_available_engines(self) -> dict[str, bool]:
        """각 엔진의 사용 가능 여부를 반환한다."""
        result = {}
        for engine_id, engine_cfg in IMAGE_ENGINE_CONFIGS.items():
            key_field = engine_cfg.get("api_key_field")
            if key_field is None:
                # API 키가 필요 없는 엔진 (Pollinations)
                result[engine_id] = True
            else:
                result[engine_id] = bool(self.config.get(key_field))
        return result

    def is_available(self, engine: str) -> bool:
        """특정 엔진이 사용 가능한지 확인"""
        cfg = IMAGE_ENGINE_CONFIGS.get(engine)
        if not cfg:
            return False
        key_field = cfg.get("api_key_field")
        if key_field is None:
            return True
        return bool(self.config.get(key_field))

    # ------------------------------------------------------------------
    # 통합 생성 인터페이스
    # ------------------------------------------------------------------

    def generate(self, engine: str, prompt: str, options: dict | None = None) -> dict:
        """
        통합 이미지 생성 인터페이스

        Args:
            engine: 엔진 ID (gpt_image, gemini_image, flux_schnell, flux_pro, ideogram, pollinations)
            prompt: 이미지 생성 프롬프트
            options: 엔진별 추가 옵션

        Returns:
            {
                "local_path": str,
                "prompt_used": str,
                "engine": str,
                "cost_estimate": float,
                "width": int,
                "height": int,
            }

        Raises:
            ValueError: 지원하지 않는 엔진이거나 API 키가 없는 경우
        """
        if options is None:
            options = {}

        if engine not in IMAGE_ENGINE_CONFIGS:
            raise ValueError(f"지원하지 않는 이미지 엔진: {engine}")

        if not self.is_available(engine):
            key_field = IMAGE_ENGINE_CONFIGS[engine].get("api_key_field", "")
            raise ValueError(
                f"'{engine}' 엔진을 사용하려면 '{key_field}' API 키가 필요합니다. "
                f"설정에서 API 키를 등록해 주세요."
            )

        handlers = {
            "gpt_image": self._gen_gpt_image,
            "gemini_image": self._gen_gemini_image,
            "gemini_flash_image": self._gen_gemini_flash_image,
            "flux_schnell": self._gen_flux,
            "flux_pro": self._gen_flux,
            "ideogram": self._gen_ideogram,
            "pollinations": self._gen_pollinations,
        }

        handler = handlers[engine]
        # flux 계열은 어떤 모델인지 구분하기 위해 _engine 전달
        if engine in ("flux_schnell", "flux_pro"):
            options = {**options, "_engine": engine}

        return handler(prompt, options)

    def generate_batch(
        self,
        engine: str,
        prompts: list[dict],
        options: dict | None = None,
        max_workers: int | None = None,
        on_progress: callable = None,
    ) -> list[dict]:
        """
        여러 이미지를 병렬로 생성한다.

        Args:
            engine: 엔진 ID
            prompts: [{"prompt": str, ...extra_meta}, ...] 형태의 프롬프트 목록
            options: 엔진별 추가 옵션
            max_workers: 최대 병렬 워커 수 (기본: MAX_PARALLEL_WORKERS)
            on_progress: 진행률 콜백 fn(completed: int, total: int)

        Returns:
            [{"local_path": ..., "prompt_used": ..., ...} | {"error": str, ...}]
            입력 prompts와 동일 순서로 반환. 실패 시 "error" 키 포함.
        """
        if options is None:
            options = {}
        if max_workers is None:
            max_workers = MAX_PARALLEL_WORKERS

        total = len(prompts)
        workers = min(max_workers, total)
        results: list[dict | None] = [None] * total
        completed_count = 0

        def _generate_single(idx: int, prompt_data: dict) -> tuple[int, dict]:
            prompt_text = prompt_data["prompt"]
            try:
                result = self.generate(engine=engine, prompt=prompt_text, options=options)
                # 프롬프트 메타데이터 병합 (light_kr, angle_kr 등)
                for key, val in prompt_data.items():
                    if key != "prompt":
                        result[key] = val
                return idx, result
            except Exception as exc:
                logger.error("이미지 생성 실패 [%d/%d]: %s", idx + 1, total, exc)
                error_result = {"error": str(exc)}
                for key, val in prompt_data.items():
                    if key != "prompt":
                        error_result[key] = val
                return idx, error_result

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_generate_single, i, pd): i
                for i, pd in enumerate(prompts)
            }

            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                completed_count += 1
                if on_progress:
                    try:
                        on_progress(completed_count, total)
                    except Exception:
                        pass

        return results

    # ------------------------------------------------------------------
    # 로컬 이미지 불러오기
    # ------------------------------------------------------------------

    def load_local_image(self, source_path: str, keyword_id: str) -> dict:
        """로컬 이미지를 data/images 디렉토리로 복사하여 불러온다."""
        import shutil

        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {source_path}")

        ext = src.suffix
        filename = f"local_{keyword_id}_{int(time.time())}{ext}"
        filepath = self.image_dir / filename
        shutil.copy2(source_path, filepath)

        try:
            from PIL import Image

            with Image.open(filepath) as img:
                w, h = img.size
        except Exception:
            w, h = 0, 0

        return {
            "local_path": str(filepath),
            "prompt_used": "(로컬 업로드)",
            "engine": "local",
            "cost_estimate": 0,
            "width": w,
            "height": h,
        }

    # ------------------------------------------------------------------
    # 엔진별 구현
    # ------------------------------------------------------------------

    def _gen_gpt_image(self, prompt: str, options: dict) -> dict:
        """OpenAI GPT Image 1 API"""
        from openai import OpenAI

        client = OpenAI(api_key=self.config["openai_api_key"])

        quality = options.get("quality", "medium")
        size = options.get("size", "1024x1024")

        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
        )

        image_data = base64.b64decode(response.data[0].b64_json)
        filename = f"gpt_{int(time.time())}.png"
        filepath = self.image_dir / filename
        filepath.write_bytes(image_data)

        cost_map = {"low": 7, "medium": 19, "high": 55}
        w, h = (int(x) for x in size.split("x"))

        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "gpt_image",
            "cost_estimate": cost_map.get(quality, 19),
            "width": w,
            "height": h,
        }

    def _gen_gemini_image(self, prompt: str, options: dict) -> dict:
        """Google Gemini (Imagen 3) 이미지 생성"""
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
            "cost_estimate": 55,
            "width": 1024,
            "height": 576,
        }

    def _gen_flux(self, prompt: str, options: dict) -> dict:
        """Flux (Replicate 경유) — Schnell 또는 Pro"""
        import replicate

        engine = options.get("_engine", "flux_schnell")
        model_map = {
            "flux_schnell": "black-forest-labs/flux-schnell",
            "flux_pro": "black-forest-labs/flux-pro",
        }
        model_id = model_map.get(engine, model_map["flux_schnell"])

        # Replicate API 토큰 설정
        import os

        os.environ["REPLICATE_API_TOKEN"] = self.config["replicate_api_key"]

        output = replicate.run(
            model_id,
            input={
                "prompt": prompt,
                "aspect_ratio": options.get("aspect_ratio", "16:9"),
                "num_outputs": 1,
            },
        )

        # 결과에서 이미지 URL 추출
        image_url = output[0] if isinstance(output, list) else str(output)
        filename = f"flux_{int(time.time())}.png"
        filepath = self.image_dir / filename
        img_data = requests.get(image_url, timeout=60).content
        filepath.write_bytes(img_data)

        cost_map = {"flux_schnell": 21, "flux_pro": 77}
        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": engine,
            "cost_estimate": cost_map.get(engine, 21),
            "width": 1024,
            "height": 576,
        }

    def _gen_ideogram(self, prompt: str, options: dict) -> dict:
        """Ideogram API (REST 호출) — 한국어 텍스트 포함 이미지에 최적"""
        response = requests.post(
            "https://api.ideogram.ai/generate",
            headers={"Api-Key": self.config["ideogram_api_key"]},
            json={
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": options.get("aspect_ratio", "ASPECT_16_9"),
                    "model": "V_2",
                }
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        image_url = data["data"][0]["url"]

        filename = f"ideogram_{int(time.time())}.png"
        filepath = self.image_dir / filename
        img_data = requests.get(image_url, timeout=60).content
        filepath.write_bytes(img_data)

        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "ideogram",
            "cost_estimate": 56,
            "width": 1024,
            "height": 576,
        }

    def _gen_gemini_flash_image(self, prompt: str, options: dict) -> dict:
        """Gemini 2.0 Flash 네이티브 이미지 생성 (REST API)"""
        import base64

        api_key = self.config["gemini_api_key"]
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"/gemini-2.0-flash-preview-image-generation:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                image_data = base64.b64decode(part["inlineData"]["data"])
                filename = f"gemini_flash_{int(time.time())}.png"
                filepath = self.image_dir / filename
                filepath.write_bytes(image_data)
                return {
                    "local_path": str(filepath),
                    "prompt_used": prompt,
                    "engine": "gemini_flash_image",
                    "cost_estimate": 0,
                    "width": 1024,
                    "height": 1024,
                }

        raise RuntimeError("Gemini Flash에서 이미지를 생성하지 못했습니다. 응답에 이미지 데이터가 없습니다.")

    def _gen_pollinations(self, prompt: str, options: dict) -> dict:
        """Pollinations (무료 폴백)"""
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=576&seed={int(time.time())}"

        img_data = requests.get(url, timeout=120).content
        filename = f"poll_{int(time.time())}.jpg"
        filepath = self.image_dir / filename
        filepath.write_bytes(img_data)

        return {
            "local_path": str(filepath),
            "prompt_used": prompt,
            "engine": "pollinations",
            "cost_estimate": 0,
            "width": 1024,
            "height": 576,
        }
