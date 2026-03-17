"""
이미지 프롬프트 변수화 모듈
글 내용에서 핵심 변수를 추출하여 다양한 이미지 프롬프트를 생성한다.

[아파트 전용] prompt_guide.docx 기반 변수 시스템
- LOCATION: 30개 (주방/욕실/거실/침실/베란다/현관)
- DIRT_LEVEL: 1~5단계
- LIGHT_SOURCE: 5종
- ANGLE: 5종
"""

import random

# ──────────────────────────────────────────────────────────────────────────────
# 아파트 전용 변수 데이터 (prompt_guide.docx 기반 추정 생성 — 추후 수정 가능)
# ──────────────────────────────────────────────────────────────────────────────

APARTMENT_LOCATIONS: list[dict] = [
    # Kitchen (주방) — 6개
    {"id": "K01", "room": "Kitchen", "room_kr": "주방",
     "location": "gap between refrigerator and wall",
     "location_kr": "냉장고와 벽 사이 틈",
     "detail": "a narrow dark gap with accumulated dust bunnies and small debris on the floor"},
    {"id": "K02", "room": "Kitchen", "room_kr": "주방",
     "location": "under the kitchen sink cabinet",
     "location_kr": "싱크대 하부 공간",
     "detail": "exposed PVC drain pipes with moisture droplets on the cabinet floor surface"},
    {"id": "K03", "room": "Kitchen", "room_kr": "주방",
     "location": "behind the gas stove",
     "location_kr": "가스레인지 뒤편",
     "detail": "grease-stained wall tiles with dark residue buildup around the gas supply pipe"},
    {"id": "K04", "room": "Kitchen", "room_kr": "주방",
     "location": "corner of kitchen counter near wall",
     "location_kr": "주방 카운터와 벽 코너",
     "detail": "junction of tile backsplash and counter surface with accumulated food residue"},
    {"id": "K05", "room": "Kitchen", "room_kr": "주방",
     "location": "inside the kitchen cabinet lower shelf",
     "location_kr": "주방 수납장 하단 선반",
     "detail": "dark wooden shelf with crumbs and faint stains near the back wall corner"},
    {"id": "K06", "room": "Kitchen", "room_kr": "주방",
     "location": "floor corner under the refrigerator",
     "location_kr": "냉장고 하부 바닥 코너",
     "detail": "dusty floor surface with small debris visible under the appliance lower edge"},

    # Bathroom (욕실) — 6개
    {"id": "B01", "room": "Bathroom", "room_kr": "욕실",
     "location": "floor drain in the bathroom",
     "location_kr": "욕실 배수구",
     "detail": "stainless steel drain cover with hair strands and soap residue on wet tile"},
    {"id": "B02", "room": "Bathroom", "room_kr": "욕실",
     "location": "base of the toilet",
     "location_kr": "변기 바닥 부분",
     "detail": "gap between toilet base and floor tile with yellowed silicone caulking"},
    {"id": "B03", "room": "Bathroom", "room_kr": "욕실",
     "location": "under the bathroom sink cabinet",
     "location_kr": "세면대 하부",
     "detail": "exposed plumbing pipes with water stains on the cabinet bottom panel"},
    {"id": "B04", "room": "Bathroom", "room_kr": "욕실",
     "location": "corner of the shower area",
     "location_kr": "샤워 공간 코너",
     "detail": "tiled corner with grout lines and soap scum buildup at the base meeting point"},
    {"id": "B05", "room": "Bathroom", "room_kr": "욕실",
     "location": "gap between bathtub and wall",
     "location_kr": "욕조와 벽 사이 틈",
     "detail": "silicone caulk line between the tub edge and tiled wall with discoloration"},
    {"id": "B06", "room": "Bathroom", "room_kr": "욕실",
     "location": "bathroom window sill",
     "location_kr": "욕실 창틀",
     "detail": "narrow windowsill with water stains and small rust spots on the aluminum frame"},

    # Living Room (거실) — 5개
    {"id": "L01", "room": "Living Room", "room_kr": "거실",
     "location": "behind the sofa",
     "location_kr": "소파 뒤편",
     "detail": "dark narrow space between sofa back and wall with dust accumulation on the floor"},
    {"id": "L02", "room": "Living Room", "room_kr": "거실",
     "location": "floor corner near the TV stand",
     "location_kr": "TV 장 근처 바닥 코너",
     "detail": "wall corner behind the TV unit with cable clusters and settled dust"},
    {"id": "L03", "room": "Living Room", "room_kr": "거실",
     "location": "under the living room bookshelf",
     "location_kr": "거실 책장 하부",
     "detail": "narrow floor space under low bookshelf with small debris near the baseboard"},
    {"id": "L04", "room": "Living Room", "room_kr": "거실",
     "location": "gap between bookshelf and wall",
     "location_kr": "책장과 벽 사이 틈",
     "detail": "narrow vertical gap filled with accumulated dust and forgotten small items"},
    {"id": "L05", "room": "Living Room", "room_kr": "거실",
     "location": "baseboard corner near the hallway entrance",
     "location_kr": "현관 근처 거실 바닥 코너",
     "detail": "floor baseboard corner near the transition between hallway and living room"},

    # Bedroom (침실) — 5개
    {"id": "D01", "room": "Bedroom", "room_kr": "침실",
     "location": "under the bed frame",
     "location_kr": "침대 하부",
     "detail": "dark space under the bed with dust motes and small debris on the floor surface"},
    {"id": "D02", "room": "Bedroom", "room_kr": "침실",
     "location": "behind the wardrobe",
     "location_kr": "옷장 뒤편",
     "detail": "narrow gap between wardrobe back panel and the wall with dust accumulation"},
    {"id": "D03", "room": "Bedroom", "room_kr": "침실",
     "location": "floor corner of bedroom wall",
     "location_kr": "침실 벽 바닥 코너",
     "detail": "baseboard corner joint where two walls meet with dust and minor surface gaps"},
    {"id": "D04", "room": "Bedroom", "room_kr": "침실",
     "location": "gap between dresser and wall",
     "location_kr": "화장대와 벽 사이 틈",
     "detail": "side gap of wooden dresser against the wall with accumulated dust bunnies"},
    {"id": "D05", "room": "Bedroom", "room_kr": "침실",
     "location": "under the study desk",
     "location_kr": "책상 하부",
     "detail": "floor space under desk with cable organizers and dust accumulation near the wall"},

    # Balcony (베란다) — 4개
    {"id": "P01", "room": "Balcony", "room_kr": "베란다",
     "location": "corner of balcony floor",
     "location_kr": "베란다 바닥 코너",
     "detail": "concrete floor corner with weathered surface and small debris accumulation"},
    {"id": "P02", "room": "Balcony", "room_kr": "베란다",
     "location": "floor drain on the balcony",
     "location_kr": "베란다 배수구",
     "detail": "small round drain cover with debris and discoloration on surrounding concrete"},
    {"id": "P03", "room": "Balcony", "room_kr": "베란다",
     "location": "gap between washing machine and wall",
     "location_kr": "세탁기와 벽 사이 틈",
     "detail": "narrow space beside washing machine with water stains and lint accumulation"},
    {"id": "P04", "room": "Balcony", "room_kr": "베란다",
     "location": "under the balcony storage cabinet",
     "location_kr": "베란다 수납장 하부",
     "detail": "dark space under storage unit with dust and small debris on concrete floor"},

    # Hallway/Entrance (현관/복도) — 4개
    {"id": "H01", "room": "Hallway", "room_kr": "현관/복도",
     "location": "corner near the front door",
     "location_kr": "현관문 근처 코너",
     "detail": "floor corner near the door threshold with tracked-in debris and scuff marks"},
    {"id": "H02", "room": "Hallway", "room_kr": "현관/복도",
     "location": "gap under the shoe cabinet",
     "location_kr": "신발장 하부 틈새",
     "detail": "narrow floor gap under shoe storage unit with dust and small debris inside"},
    {"id": "H03", "room": "Hallway", "room_kr": "현관/복도",
     "location": "hallway baseboard floor corner",
     "location_kr": "복도 바닥 코너",
     "detail": "baseboard junction in the narrow hallway with dust accumulation at the corner"},
    {"id": "H04", "room": "Hallway", "room_kr": "현관/복도",
     "location": "area near the electrical panel box",
     "location_kr": "분전반 주변",
     "detail": "wall-mounted panel box area with cable conduits and settled dust on surrounding wall"},
]

APARTMENT_DIRT_LEVELS: list[dict] = [
    {"level": 1, "name_kr": "깨끗", "name_en": "Clean",
     "wear_detail": "minimal dust on surfaces, well-maintained and recently cleaned appearance",
     "mood": "clean and well-kept appearance, nearly pristine condition"},
    {"level": 2, "name_kr": "약간 사용", "name_en": "Slightly Used",
     "wear_detail": "thin dust layer on baseboard, faint water marks, minor scuff on flooring",
     "mood": "slightly lived-in with subtle signs of everyday use"},
    {"level": 3, "name_kr": "보통", "name_en": "Normal",
     "wear_detail": "moderate dust accumulation in corners, visible grime in cracks, worn surface finish",
     "mood": "typical household wear with noticeable but not severe neglect"},
    {"level": 4, "name_kr": "더러움", "name_en": "Dirty",
     "wear_detail": "thick dust accumulation, yellowed silicone caulking, visible mold spots, stained grout lines",
     "mood": "neglected and overdue for cleaning, with clearly visible grime and buildup"},
    {"level": 5, "name_kr": "심각", "name_en": "Very Dirty",
     "wear_detail": "heavy mold growth, severe dark grime buildup, cracked and stained materials, persistent water damage",
     "mood": "severely neglected with urgent cleaning needed, heavy contamination clearly visible"},
]

APARTMENT_LIGHT_SOURCES: list[dict] = [
    {"id": "L1", "value": "a window to the left casting soft side shadows",
     "label_kr": "창문 측광"},
    {"id": "L2", "value": "overhead fluorescent tube light with harsh white glow",
     "label_kr": "천장 형광등"},
    {"id": "L3", "value": "dim overhead LED spotlight creating a small pool of light",
     "label_kr": "희미한 LED 스팟"},
    {"id": "L4", "value": "indirect ambient light reflected from an adjacent room",
     "label_kr": "간접 반사광"},
    {"id": "L5", "value": "diffused natural daylight through a frosted glass window",
     "label_kr": "반투명 유리창 자연광"},
]

APARTMENT_ANGLES: list[dict] = [
    {"id": "A1", "value": "low angle from floor level, camera nearly touching the ground",
     "label_kr": "바닥 시점"},
    {"id": "A2", "value": "close-up macro perspective at ground level focusing on surface detail",
     "label_kr": "바닥 근접 매크로"},
    {"id": "A3", "value": "straight-on view at knee height looking directly at the subject",
     "label_kr": "무릎 높이 정면"},
    {"id": "A4", "value": "top-down overhead view looking straight down at the floor",
     "label_kr": "위에서 내려다보기"},
    {"id": "A5", "value": "diagonal perspective from corner showing depth and dimension",
     "label_kr": "코너에서 대각선"},
]

# prompt_guide.docx 기반 기본 템플릿
APARTMENT_TEMPLATE = (
    "A realistic close-up photo of the {location} inside a {room} of a typical South Korean "
    "apartment built in the early 2000s. Shot with a Samsung Galaxy S22 front camera, slightly "
    "soft focus, moderate noise grain, natural indoor lighting with visible shadows. {detail}. "
    "{mood}. Signs of wear: {wear_detail}. Dim ambient light from {light_source}. "
    "Warm-yellowish color tone from old fluorescent ceiling light. Photographed at {angle}, "
    "as if inspecting the area up close. No people, no products, no text. "
    "Ultra realistic candid unedited phone photo."
)

# 빠른 조회용 인덱스
_LOC_INDEX: dict[str, dict] = {loc["id"]: loc for loc in APARTMENT_LOCATIONS}
_DIRT_INDEX: dict[int, dict] = {d["level"]: d for d in APARTMENT_DIRT_LEVELS}
_LIGHT_INDEX: dict[str, dict] = {l["id"]: l for l in APARTMENT_LIGHT_SOURCES}
_ANGLE_INDEX: dict[str, dict] = {a["id"]: a for a in APARTMENT_ANGLES}


class ImagePromptBuilder:
    """글 내용 기반 이미지 프롬프트 생성기"""

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
            count: 생성할 프롬프트 변형 수 (1~5)

        Returns:
            [
                {
                    "prompt": str,          # 영어 프롬프트
                    "style": str,           # 사용된 스타일
                    "negative_prompt": str,  # 네거티브 프롬프트
                    "aspect_ratio": str,     # 비율
                }
            ]
        """
        count = max(1, min(count, 5))

        base_prompt = article_data.get("image_prompt", "")
        tags = article_data.get("tags", [])

        # 이미 사용한 조합을 추적해서 중복 방지
        used_styles = []
        used_moods = []
        used_compositions = []

        prompts = []
        for _ in range(count):
            style = self._pick_unique(self.STYLE_VARS, used_styles)
            mood = self._pick_unique(self.MOOD_VARS, used_moods)
            composition = self._pick_unique(self.COMPOSITION_VARS, used_compositions)

            used_styles.append(style)
            used_moods.append(mood)
            used_compositions.append(composition)

            tag_context = ", ".join(tags[:3]) if tags else ""
            parts = [base_prompt, style, mood, composition]
            if tag_context:
                parts.append(f"related to {tag_context}")
            parts.append("no text, no watermark, high resolution, blog thumbnail")

            enhanced_prompt = ", ".join(p for p in parts if p)

            prompts.append({
                "prompt": enhanced_prompt,
                "style": style,
                "negative_prompt": "text, watermark, logo, blurry, low quality, distorted, ugly, nsfw",
                "aspect_ratio": "16:9",
            })

        return prompts

    def _pick_unique(self, pool: list[str], used: list[str]) -> str:
        """이미 사용한 값을 피해서 선택. 풀이 소진되면 랜덤."""
        available = [v for v in pool if v not in used]
        if not available:
            available = pool
        return random.choice(available)

    # ------------------------------------------------------------------
    # 아파트 전용 — prompt_guide.docx 기반
    # ------------------------------------------------------------------

    def build_apartment_prompt(self, variables: dict) -> str:
        """
        변수 조합으로 아파트 배경 이미지 프롬프트 1개 생성.

        Args:
            variables: {
                "location_id": "K01",
                "dirt_level": 3,
                "light_id": "L1",
                "angle_id": "A1",
            }
        Returns:
            완성된 영어 프롬프트 문자열
        """
        loc = _LOC_INDEX.get(variables.get("location_id", "K01"), APARTMENT_LOCATIONS[0])
        dirt = _DIRT_INDEX.get(int(variables.get("dirt_level", 3)), APARTMENT_DIRT_LEVELS[2])
        light = _LIGHT_INDEX.get(variables.get("light_id", "L1"), APARTMENT_LIGHT_SOURCES[0])
        angle = _ANGLE_INDEX.get(variables.get("angle_id", "A1"), APARTMENT_ANGLES[0])

        return APARTMENT_TEMPLATE.format(
            location=loc["location"],
            room=loc["room"],
            detail=loc["detail"],
            mood=dirt["mood"],
            wear_detail=dirt["wear_detail"],
            light_source=light["value"],
            angle=angle["value"],
        )

    def build_apartment_prompts(self, variables: dict, count: int = 2) -> list[dict]:
        """
        기본 변수를 유지하면서 light/angle 조합을 변경해 count개 변형 프롬프트 생성.

        Args:
            variables: build_apartment_prompt 와 동일
            count: 생성할 변형 수 (1~5)

        Returns:
            [{"prompt": str, "light_id": str, "angle_id": str, "light_kr": str, "angle_kr": str}]
        """
        count = max(1, min(count, 5))

        base_light = variables.get("light_id", "L1")
        base_angle = variables.get("angle_id", "A1")

        # 기본 조합을 첫 번째로, 나머지는 다른 조합으로 채움
        light_ids = [base_light] + [l["id"] for l in APARTMENT_LIGHT_SOURCES if l["id"] != base_light]
        angle_ids = [base_angle] + [a["id"] for a in APARTMENT_ANGLES if a["id"] != base_angle]

        results = []
        for i in range(count):
            light_id = light_ids[i % len(light_ids)]
            angle_id = angle_ids[i % len(angle_ids)]

            vars_i = {**variables, "light_id": light_id, "angle_id": angle_id}
            prompt = self.build_apartment_prompt(vars_i)

            results.append({
                "prompt": prompt,
                "light_id": light_id,
                "angle_id": angle_id,
                "light_kr": _LIGHT_INDEX[light_id]["label_kr"],
                "angle_kr": _ANGLE_INDEX[angle_id]["label_kr"],
            })

        return results
