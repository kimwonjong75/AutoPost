"""
단가·환율 단일 출처(SSOT) 모듈.

config.yaml의 `pricing` 섹션을 읽어 USD 비용을 계산하고, 환율로 KRW 변환한다.
config에 값이 없으면 코드 기본값으로 폴백한다. 실시간 환율 조회(open.er-api.com)도 지원.

원칙: 비용은 환율 무관한 **USD로 저장**(cost_usd)하고, 화면 표시 시점에 ×환율로 KRW를 계산한다.
모든 모듈/페이지는 비용·환율을 이 모듈을 통해서만 계산한다.
"""

import logging

import requests

logger = logging.getLogger(__name__)

# 기본 환율 (오늘 시점 시드값, KRW per 1 USD)
DEFAULT_KRW_PER_USD = 1520.0

# 실시간 환율 조회 (무키, HTTPS) — rates.KRW 사용
FX_API_URL = "https://open.er-api.com/v6/latest/USD"
FX_TIMEOUT_SEC = 10

# 예측용 기본 lookback (일)
DEFAULT_LOOKBACK_DAYS = 7

# 이미지 엔진 기본 단가 (USD/장). gpt_image는 사이즈·품질별, 그 외는 평균 단가(_flat).
DEFAULT_IMAGE_PRICES_USD: dict = {
    "gpt_image": {
        "1024x1024": {"low": 0.011, "medium": 0.042, "high": 0.167},
        "1536x1024": {"low": 0.016, "medium": 0.063, "high": 0.25},
        "1024x1536": {"low": 0.016, "medium": 0.063, "high": 0.25},
    },
    "gemini_image": {"_flat": 0.04},
    "flux_schnell": {"_flat": 0.015},
    "flux_pro": {"_flat": 0.055},
    "ideogram": {"_flat": 0.04},
    "gemini_flash_image": {"_flat": 0.0},
    "pollinations": {"_flat": 0.0},
    "local": {"_flat": 0.0},
}

DEFAULT_IMAGE_QUALITY = "medium"
DEFAULT_IMAGE_SIZE = "1536x1024"


# ──────────────────────────────────────────────
# 환율
# ──────────────────────────────────────────────
def get_exchange_rate(config: dict) -> float:
    """현재 환율(KRW per USD). config 미설정 시 기본값."""
    fx = (config.get("pricing", {}) or {}).get("exchange_rate", {}) or {}
    try:
        rate = float(fx.get("krw_per_usd"))
        if rate > 0:
            return rate
    except (TypeError, ValueError):
        pass
    return DEFAULT_KRW_PER_USD


def usd_to_krw(config: dict, usd: float) -> float:
    """USD 금액을 현재 환율로 KRW 변환."""
    return (usd or 0.0) * get_exchange_rate(config)


def fetch_live_exchange_rate() -> float | None:
    """실시간 USD→KRW 환율 조회. 실패 시 None (예외 전파 금지)."""
    try:
        resp = requests.get(FX_API_URL, timeout=FX_TIMEOUT_SEC)
        resp.raise_for_status()
        rate = (resp.json().get("rates", {}) or {}).get("KRW")
        if rate:
            return float(rate)
    except Exception as exc:
        logger.warning("실시간 환율 조회 실패: %s", exc)
    return None


# ──────────────────────────────────────────────
# 텍스트(토큰) 단가
# ──────────────────────────────────────────────
def get_text_price(config: dict, engine: str, model: str) -> dict:
    """모델별 USD/1M 토큰 단가 {input, output}. config override → ENGINE_CONFIGS 폴백."""
    text_models = (config.get("pricing", {}) or {}).get("text_models", {}) or {}
    override = text_models.get(f"{engine}/{model}")
    if isinstance(override, dict) and "input" in override and "output" in override:
        try:
            return {"input": float(override["input"]), "output": float(override["output"])}
        except (TypeError, ValueError):
            pass
    return _default_text_price(engine, model)


def _default_text_price(engine: str, model: str) -> dict:
    """ENGINE_CONFIGS의 코드 기본 단가 (지연 import로 순환 참조 방지)."""
    from modules.content_generator import ENGINE_CONFIGS

    for m in ENGINE_CONFIGS.get(engine, {}).get("models", []):
        if m["id"] == model:
            return {"input": float(m["input_per_m"]), "output": float(m["output_per_m"])}
    return {"input": 0.0, "output": 0.0}


def calc_text_cost_usd(config: dict, engine: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """입력/출력 토큰으로 USD 비용 계산."""
    price = get_text_price(config, engine, model)
    return (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]


# ──────────────────────────────────────────────
# 이미지 단가
# ──────────────────────────────────────────────
def calc_image_cost_usd(config: dict, engine: str, size: str | None = None, quality: str | None = None) -> float:
    """이미지 1장 USD 단가. config override → DEFAULT_IMAGE_PRICES_USD 폴백."""
    size = size or DEFAULT_IMAGE_SIZE
    quality = quality or DEFAULT_IMAGE_QUALITY
    image_models = (config.get("pricing", {}) or {}).get("image_models", {}) or {}

    price = _lookup_image_price(image_models.get(engine), size, quality)
    if price is not None:
        return price
    price = _lookup_image_price(DEFAULT_IMAGE_PRICES_USD.get(engine), size, quality)
    return price if price is not None else 0.0


def _lookup_image_price(table, size: str, quality: str) -> float | None:
    """단가 테이블에서 (size, quality)로 단가 조회. _flat이면 사이즈/품질 무관."""
    if not isinstance(table, dict):
        return None
    if "_flat" in table:
        try:
            return float(table["_flat"])
        except (TypeError, ValueError):
            return None
    size_tbl = table.get(size)
    if isinstance(size_tbl, dict) and quality in size_tbl:
        try:
            return float(size_tbl[quality])
        except (TypeError, ValueError):
            return None
    # 사이즈 미스 시 동일 품질의 첫 사이즈로 폴백
    for v in table.values():
        if isinstance(v, dict) and quality in v:
            try:
                return float(v[quality])
            except (TypeError, ValueError):
                return None
    return None


# ──────────────────────────────────────────────
# 비용 표시/예측 헬퍼
# ──────────────────────────────────────────────
def row_krw(config: dict, cost_usd: float, cost_estimate_krw: float) -> float:
    """DB 행의 KRW 비용. cost_usd가 있으면 현재 환율로 환산, 없으면 저장된 KRW 폴백."""
    if cost_usd and cost_usd > 0:
        return usd_to_krw(config, cost_usd)
    return cost_estimate_krw or 0.0


def get_lookback_days(config: dict) -> int:
    """예측용 일평균 산출 구간(일)."""
    proj = (config.get("pricing", {}) or {}).get("projection", {}) or {}
    try:
        d = int(proj.get("lookback_days", DEFAULT_LOOKBACK_DAYS))
        return d if d > 0 else DEFAULT_LOOKBACK_DAYS
    except (TypeError, ValueError):
        return DEFAULT_LOOKBACK_DAYS


def get_assumed_cost_per_post_krw(config: dict) -> float:
    """실측 데이터가 없을 때 사용할 건당 가정 비용(KRW)."""
    proj = (config.get("pricing", {}) or {}).get("projection", {}) or {}
    try:
        return float(proj.get("assumed_cost_per_post_krw", 0))
    except (TypeError, ValueError):
        return 0.0
