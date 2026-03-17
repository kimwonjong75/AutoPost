"""
✍️ 글 생성 — AI 엔진 선택 + 키워드 입력 + 참고자료 첨부 + 글 생성
"""

import csv
import io
import json
import sys
import uuid
from pathlib import Path

import streamlit as st

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.content_generator import ENGINE_CONFIGS, ContentGenerator, load_config
from modules.attachment_manager import AttachmentManager
from modules.prompt_loader import get_system_prompt
from modules.models import GeneratedArticle, GeneratedImage, init_db
from modules.image_generator import ImageGenerator, IMAGE_ENGINE_CONFIGS
from modules.image_prompt_builder import (
    APARTMENT_LOCATIONS, APARTMENT_DIRT_LEVELS,
    APARTMENT_LIGHT_SOURCES, APARTMENT_ANGLES,
    ImagePromptBuilder,
)
from modules.image_variable_analyzer import ImageVariableAnalyzer

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="글 생성 — AutoPost",
    page_icon="✍️",
    layout="wide",
)

init_db()

from app import get_config, inject_custom_css, render_sidebar, render_status_bar, save_config

config = get_config()
inject_custom_css()
render_sidebar(config)
render_status_bar(config)

# ──────────────────────────────────────────────
# 페이지 전용 CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
.gen-section {
    background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
    border: 1px solid #2D3250;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
}
.gen-section-title {
    font-size: 1rem;
    font-weight: 700;
    color: #FAFAFA;
    margin-bottom: 0.8rem;
}
.result-card {
    background: #1A1D29;
    border: 1px solid #2D3250;
    border-radius: 12px;
    padding: 1.5rem;
    margin-top: 1rem;
}
.result-card .rc-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #FAFAFA;
    margin-bottom: 0.5rem;
}
.result-card .rc-meta {
    font-size: 0.78rem;
    color: #A0A4B8;
    margin-bottom: 1rem;
}
.tag-chip {
    display: inline-block;
    background: #2D3250;
    color: #A29BFE;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.75rem;
    margin-right: 0.3rem;
    margin-bottom: 0.3rem;
}
.att-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.8rem;
    background: #1A1D29;
    border: 1px solid #2D3250;
    border-radius: 8px;
    margin-bottom: 0.4rem;
    font-size: 0.85rem;
}
.att-row .att-name { color: #FAFAFA; flex: 1; }
.att-row .att-info { color: #A0A4B8; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

MANUAL_INPUT_LABEL = "직접 입력"

# ──────────────────────────────────────────────
# 세션 초기화
# ──────────────────────────────────────────────
if "gen_keywords" not in st.session_state:
    st.session_state["gen_keywords"] = []
if "gen_results" not in st.session_state:
    st.session_state["gen_results"] = []
if "gen_attachments_keyword_id" not in st.session_state:
    st.session_state["gen_attachments_keyword_id"] = ""
if "img_vars" not in st.session_state:
    st.session_state["img_vars"] = {}         # {idx: {location_id, dirt_level, light_id, angle_id}}
if "img_generated" not in st.session_state:
    st.session_state["img_generated"] = {}    # {idx: [image_result, ...]}


# ──────────────────────────────────────────────
# 페이지 렌더링
# ──────────────────────────────────────────────
st.markdown("# ✍️ AI 글 생성")
st.caption("키워드를 입력하고 AI 엔진을 선택하여 블로그 글을 자동 생성합니다.")

# ══════════════════════════════════════════════
# 1) AI 엔진 선택
# ══════════════════════════════════════════════
st.markdown('<div class="gen-section-title">1. AI 엔진 선택</div>', unsafe_allow_html=True)

engine_col, model_col = st.columns([1, 1])

with engine_col:
    engine_keys = list(ENGINE_CONFIGS.keys())
    engine_labels = [ENGINE_CONFIGS[k]["label"] for k in engine_keys]
    # config에서 기본값 인덱스 계산
    default_engine = config.get("defaults", {}).get("text_engine", "openai")
    default_engine_idx = engine_keys.index(default_engine) if default_engine in engine_keys else 0

    selected_engine = st.selectbox(
        "AI 엔진",
        options=engine_keys,
        index=default_engine_idx,
        format_func=lambda x: ENGINE_CONFIGS[x]["label"],
        key="sel_engine",
    )

with model_col:
    models = ENGINE_CONFIGS[selected_engine]["models"]
    model_ids = [m["id"] for m in models]
    model_labels = {m["id"]: m["name"] for m in models}

    # config에서 기본 모델 인덱스
    default_model = config.get("defaults", {}).get("text_model", "")
    default_model_idx = model_ids.index(default_model) if default_model in model_ids else 0

    selected_model = st.selectbox(
        "모델",
        options=model_ids,
        index=default_model_idx,
        format_func=lambda x: model_labels.get(x, x),
        key="sel_model",
    )

# 기본값 저장 버튼
_save_col, _ = st.columns([1, 3])
with _save_col:
    if st.button("💾 기본값으로 저장", key="btn_save_text_defaults", help="현재 선택한 엔진/모델을 세션 종료 후에도 유지되는 기본값으로 저장합니다"):
        _cfg = get_config()
        _cfg.setdefault("defaults", {})
        _cfg["defaults"]["text_engine"] = selected_engine
        _cfg["defaults"]["text_model"] = selected_model
        save_config(_cfg)
        st.success("텍스트 엔진 기본값이 저장되었습니다.", icon="✅")

# 엔진별 추가 옵션 (동적)
extra_opts = ENGINE_CONFIGS[selected_engine].get("extra_options", {})
engine_options = {}

if extra_opts:
    opt_cols = st.columns(len(extra_opts))
    for i, (opt_key, opt_cfg) in enumerate(extra_opts.items()):
        with opt_cols[i]:
            if opt_cfg["type"] == "slider":
                engine_options[opt_key] = st.slider(
                    opt_key.replace("_", " ").title(),
                    min_value=float(opt_cfg["min"]),
                    max_value=float(opt_cfg["max"]),
                    value=float(opt_cfg["default"]),
                    step=0.1,
                    key=f"opt_{opt_key}",
                )
            elif opt_cfg["type"] == "select":
                engine_options[opt_key] = st.selectbox(
                    opt_key.replace("_", " ").title(),
                    options=opt_cfg["options"],
                    index=opt_cfg["options"].index(opt_cfg["default"]),
                    key=f"opt_{opt_key}",
                )
            elif opt_cfg["type"] == "number":
                engine_options[opt_key] = st.number_input(
                    opt_key.replace("_", " ").title(),
                    value=opt_cfg["default"],
                    step=500,
                    key=f"opt_{opt_key}",
                )

st.divider()

# ══════════════════════════════════════════════
# 2) 키워드 입력
# ══════════════════════════════════════════════
st.markdown('<div class="gen-section-title">2. 키워드 입력</div>', unsafe_allow_html=True)

input_method = st.radio(
    "입력 방식",
    ["직접 입력 (줄바꿈 구분)", "CSV 파일 업로드", "구글 시트에서 가져오기"],
    horizontal=True,
    key="kw_input_method",
)

parsed_keywords: list[dict] = []

if input_method == "직접 입력 (줄바꿈 구분)":
    kw_text = st.text_area(
        "키워드 목록 (한 줄에 하나씩)",
        placeholder="겨울철 난방비 절약\n삼성 온풍기 SEH-P2100 후기\n원룸 단열 방법",
        height=150,
        key="kw_text",
    )
    for line in kw_text.split("\n"):
        line = line.strip()
        if line:
            parsed_keywords.append({
                "keyword": line,
                "content_type": "정보성",
                "blog_id": "자동배정",
            })

elif input_method == "CSV 파일 업로드":
    uploaded_csv = st.file_uploader("CSV 파일 (키워드, 글유형, 대상블로그)", type=["csv", "txt"], key="kw_csv")
    if uploaded_csv:
        content = uploaded_csv.read().decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        for row_idx, row in enumerate(reader):
            if not row:
                continue
            # 첫 줄이 헤더인 경우 스킵
            if row_idx == 0 and row[0].strip() in ("키워드", "keyword"):
                continue
            kw = row[0].strip()
            if not kw:
                continue
            content_type = row[1].strip() if len(row) > 1 else "정보성"
            blog_id = row[2].strip() if len(row) > 2 else "자동배정"
            parsed_keywords.append({
                "keyword": kw,
                "content_type": content_type,
                "blog_id": blog_id,
            })

elif input_method == "구글 시트에서 가져오기":
    if st.button("구글 시트 동기화", key="btn_sync_sheet"):
        try:
            from modules.google_sheet import GoogleSheetManager
            gs = GoogleSheetManager(config.get("google_sheet", {}))
            fetched = gs.fetch_pending_keywords()
            st.session_state["gen_keywords"] = fetched
            st.success(f"{len(fetched)}개 키워드를 가져왔습니다.")
        except Exception as e:
            st.error(f"구글 시트 연동 실패: {e}")
    # 이전에 가져온 키워드
    parsed_keywords = st.session_state.get("gen_keywords", [])

# 키워드 미리보기
if parsed_keywords:
    st.markdown(f"**{len(parsed_keywords)}개 키워드**")
    import pandas as pd
    df_kw = pd.DataFrame(parsed_keywords)
    st.dataframe(df_kw, use_container_width=True, hide_index=True, height=min(200, 40 + 35 * len(parsed_keywords)))

st.divider()

# ══════════════════════════════════════════════
# 3) 글 유형 선택 + 상품정보
# ══════════════════════════════════════════════
st.markdown('<div class="gen-section-title">3. 글 유형</div>', unsafe_allow_html=True)

content_type = st.radio(
    "글 유형 선택",
    ["정보성", "상품홍보"],
    horizontal=True,
    key="content_type",
)

product_info = ""
if content_type == "상품홍보":
    products = config.get("products", [])
    product_names = [p["name"] for p in products]

    if product_names:
        options = product_names + [MANUAL_INPUT_LABEL]
        selected_product = st.selectbox(
            "상품 선택",
            options=options,
            key="selected_product",
        )

        if selected_product == MANUAL_INPUT_LABEL:
            product_name = st.text_input("상품명", key="product_name")
        else:
            product_name = selected_product
    else:
        st.info("등록된 상품이 없습니다. 설정 > 상품 리스트에서 추가하거나, 아래에 직접 입력하세요.")
        product_name = st.text_input("상품명", key="product_name")

    product_info = f"\n[상품 정보]\n- 상품명: {product_name}\n"

    with st.expander("상품 추가 정보 (선택)"):
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            product_brand = st.text_input("브랜드", key="product_brand")
            product_price = st.text_input("가격", placeholder="39,900원", key="product_price")
        with p_col2:
            product_link = st.text_input("구매 링크", key="product_link")
        product_features = st.text_area(
            "주요 특징/장점",
            placeholder="특징 1\n특징 2\n특징 3",
            height=80,
            key="product_features",
        )
        extra_parts = []
        if product_brand:
            extra_parts.append(f"- 브랜드: {product_brand}")
        if product_price:
            extra_parts.append(f"- 가격: {product_price}")
        if product_link:
            extra_parts.append(f"- 구매링크: {product_link}")
        if product_features:
            extra_parts.append(f"- 주요 특징:\n{product_features}")
        if extra_parts:
            product_info += "\n".join(extra_parts) + "\n"

st.divider()

# ══════════════════════════════════════════════
# 4) 참고자료 첨부
# ══════════════════════════════════════════════
st.markdown('<div class="gen-section-title">4. 참고자료 첨부</div>', unsafe_allow_html=True)
st.caption("첨부된 자료는 AI 글 작성 시 참고 컨텍스트로 사용되며, 영구 보관됩니다.")

# 키워드 ID: 첫 키워드 기반 또는 세션 ID
if parsed_keywords:
    kw_id = parsed_keywords[0]["keyword"].replace(" ", "_")[:20]
else:
    if not st.session_state["gen_attachments_keyword_id"]:
        st.session_state["gen_attachments_keyword_id"] = f"DRAFT-{uuid.uuid4().hex[:6]}"
    kw_id = st.session_state["gen_attachments_keyword_id"]

att_manager = AttachmentManager()

# 기존 첨부파일 표시
existing_atts = att_manager.get_attachments(kw_id)
if existing_atts:
    for att in existing_atts:
        type_icon = {"pdf": "📄", "image": "🖼️", "text": "📝"}.get(att.file_type, "📎")
        size_kb = att.file_size // 1024
        c1, c2, c3 = st.columns([4, 2, 1])
        with c1:
            st.markdown(f"{type_icon} **{att.original_filename}**")
        with c2:
            st.caption(f"{att.file_type} | {size_kb}KB")
        with c3:
            if st.button("삭제", key=f"del_att_{att.id}"):
                att_manager.delete_attachment(att.id)
                st.rerun()

# 새 파일 업로드
uploaded_atts = st.file_uploader(
    "파일 추가 (PDF, 이미지, 텍스트)",
    type=["pdf", "jpg", "jpeg", "png", "txt", "md", "csv"],
    accept_multiple_files=True,
    key="att_upload",
)
att_description = st.text_input("메모 (선택)", key="att_desc", placeholder="이 자료에 대한 간단한 설명")

if uploaded_atts:
    if st.button("첨부파일 저장", key="btn_save_atts"):
        saved_count = 0
        for f in uploaded_atts:
            att_manager.save(kw_id, f, att_description)
            saved_count += 1
        st.success(f"{saved_count}개 파일이 첨부되었습니다.")
        st.rerun()

st.divider()

# ══════════════════════════════════════════════
# 5) 프롬프트 관리
# ══════════════════════════════════════════════
st.markdown('<div class="gen-section-title">5. 프롬프트 설정</div>', unsafe_allow_html=True)

link_cols = st.columns(2)
with link_cols[0]:
    st.page_link("pages/5_⚙️_설정.py", label="⚙️ 프롬프트 템플릿 편집", icon="📎")
with link_cols[1]:
    if content_type == "상품홍보":
        st.page_link("pages/5_⚙️_설정.py", label="📦 상품 리스트 관리", icon="📦")

custom_instruction = st.text_area(
    "글 작성 지침 (선택)",
    placeholder="예: 20대 여성 타겟, 이모티콘 사용, ~요 체로 작성",
    height=68,
    key="custom_instruction",
)

with st.expander("전체 시스템 프롬프트 보기/수정"):
    default_prompt = get_system_prompt(content_type)

    system_prompt = st.text_area(
        "시스템 프롬프트",
        value=default_prompt,
        height=300,
        key="system_prompt",
    )

st.divider()

# ══════════════════════════════════════════════
# 6) 생성 버튼 + 결과
# ══════════════════════════════════════════════
st.markdown('<div class="gen-section-title">6. 글 생성</div>', unsafe_allow_html=True)

# API 키 확인
api_key_field = ENGINE_CONFIGS[selected_engine]["api_key_field"]
has_api_key = bool(config.get("api_keys", {}).get(api_key_field, ""))

if not has_api_key:
    st.warning(
        f"{ENGINE_CONFIGS[selected_engine]['label']} API 키가 설정되지 않았습니다. "
        f"config.yaml의 api_keys.{api_key_field}를 확인하세요."
    )

if not parsed_keywords:
    st.info("위에서 키워드를 입력하세요.")

# 생성 실행
can_generate = parsed_keywords and has_api_key
if st.button(
    f"AI 글 생성 ({len(parsed_keywords)}건)",
    type="primary",
    disabled=not can_generate,
    use_container_width=True,
    key="btn_generate",
):
    # 프롬프트 준비 (expander 밖에서 정의된 값 사용)
    final_system_prompt = st.session_state.get("system_prompt", default_prompt)

    # 참고자료 컨텍스트 (키워드 전용)
    ref_context = att_manager.build_context_for_prompt(kw_id)

    # ContentGenerator 초기화
    try:
        generator = ContentGenerator(config)
    except Exception as e:
        st.error(f"AI 엔진 초기화 실패: {e}")
        st.stop()

    results = []
    progress_bar = st.progress(0, text="생성 준비 중...")
    status_area = st.empty()

    for idx, kw_data in enumerate(parsed_keywords):
        keyword = kw_data["keyword"]
        kw_content_type = kw_data.get("content_type", content_type)

        status_area.markdown(f"**[{idx + 1}/{len(parsed_keywords)}]** `{keyword}` 생성 중...")

        # 템플릿 참고자료 컨텍스트 병합 (정보성/상품홍보 구분)
        template_id = "__TEMPLATE_PRODUCT__" if kw_content_type == "상품홍보" else "__TEMPLATE_INFO__"
        template_context = att_manager.build_context_for_prompt(template_id)
        combined_ref = "\n\n".join(filter(None, [ref_context, template_context]))

        # 사용자 프롬프트 구성
        user_prompt_parts = [f"키워드: {keyword}"]
        if kw_content_type == "상품홍보" and product_info:
            user_prompt_parts.append(product_info)
        if custom_instruction:
            user_prompt_parts.append(f"\n[추가 지침]\n{custom_instruction}")
        if combined_ref:
            user_prompt_parts.append(f"\n{combined_ref}")

        user_prompt = "\n".join(user_prompt_parts)

        try:
            result = generator.generate(
                engine=selected_engine,
                model=selected_model,
                system_prompt=final_system_prompt,
                user_prompt=user_prompt,
                options=engine_options,
            )

            # DB에 저장
            keyword_id = kw_data.get("keyword_id", keyword.replace(" ", "_")[:30])
            tags_json = json.dumps(result.get("tags", []), ensure_ascii=False)
            meta = result.get("meta", {})

            article_obj = GeneratedArticle.create(
                keyword_id=keyword_id,
                engine=meta.get("engine", selected_engine),
                model=meta.get("model", selected_model),
                title=result.get("title", ""),
                body_html=result.get("body_html", ""),
                tags=tags_json,
                image_prompt=result.get("image_prompt", ""),
                status="생성완료",
                cost_estimate=meta.get("cost_estimate", 0),
                tokens_used=meta.get("tokens_used", 0),
            )

            result["_keyword"] = keyword
            result["_status"] = "성공"
            result["_article_id"] = article_obj.id
            result["_keyword_id"] = keyword_id
            result["_content_type"] = kw_content_type
            results.append(result)

        except Exception as e:
            results.append({
                "_keyword": keyword,
                "_status": "실패",
                "_error": str(e),
            })

        progress_bar.progress((idx + 1) / len(parsed_keywords), text=f"{idx + 1}/{len(parsed_keywords)} 완료")

    status_area.empty()
    progress_bar.empty()
    st.session_state["gen_results"] = results
    st.success(f"생성 완료! 성공 {sum(1 for r in results if r['_status'] == '성공')}건 / 실패 {sum(1 for r in results if r['_status'] == '실패')}건")

# ══════════════════════════════════════════════
# 결과 미리보기
# ══════════════════════════════════════════════
if st.session_state.get("gen_results"):
    st.markdown("---")
    st.markdown("### 생성 결과")

    for i, result in enumerate(st.session_state["gen_results"]):
        keyword = result.get("_keyword", "")

        if result["_status"] == "실패":
            st.error(f"**{keyword}** — 생성 실패: {result.get('_error', '알 수 없는 오류')}")
            continue

        meta = result.get("meta", {})
        tags = result.get("tags", [])

        with st.expander(f"**{result.get('title', '(제목 없음)')}** — {keyword}", expanded=(i == 0)):
            # 메타 정보
            meta_parts = []
            if meta.get("engine"):
                meta_parts.append(f"엔진: {ENGINE_CONFIGS.get(meta['engine'], {}).get('label', meta['engine'])}")
            if meta.get("model"):
                meta_parts.append(f"모델: {meta['model']}")
            if meta.get("tokens_used"):
                meta_parts.append(f"토큰: {meta['tokens_used']:,}")
            if meta.get("cost_estimate"):
                meta_parts.append(f"비용: ₩{meta['cost_estimate']:,.1f}")
            st.caption(" | ".join(meta_parts))

            # 태그
            if tags:
                tags_html = "".join(f'<span class="tag-chip">#{t}</span>' for t in tags)
                st.markdown(tags_html, unsafe_allow_html=True)

            # 본문 미리보기
            st.markdown("**본문 미리보기**")
            body_html = result.get("body_html", "")
            if body_html:
                st.markdown(body_html, unsafe_allow_html=True)
            else:
                st.info("본문 없음")

            # 이미지 프롬프트
            img_prompt = result.get("image_prompt", "")
            if img_prompt:
                st.markdown("**이미지 프롬프트**")
                st.code(img_prompt, language=None)

# ══════════════════════════════════════════════
# 이미지 자동생성
# ══════════════════════════════════════════════
successful_results = [
    (i, r) for i, r in enumerate(st.session_state.get("gen_results", []))
    if r.get("_status") == "성공"
]

if successful_results:
    st.markdown("---")
    st.markdown("### 🖼️ 이미지 자동생성")
    st.caption("글 내용을 AI가 분석해 아파트 배경 이미지 변수를 자동 선택합니다. 수동으로 변경도 가능합니다.")

    # ── 전역 이미지 생성 설정 ──
    with st.container(border=True):
        img_engine_keys = list(IMAGE_ENGINE_CONFIGS.keys())
        _default_img_engine = config.get("defaults", {}).get("image_engine", "gemini_image")
        default_engine_idx = img_engine_keys.index(_default_img_engine) if _default_img_engine in img_engine_keys else 0

        col_eng, col_cnt1, col_cnt2 = st.columns([2, 1, 1])
        with col_eng:
            img_engine_global = st.selectbox(
                "이미지 엔진",
                options=img_engine_keys,
                index=default_engine_idx,
                format_func=lambda x: f"{IMAGE_ENGINE_CONFIGS[x]['label']} ({IMAGE_ENGINE_CONFIGS[x]['cost_per_image']})",
                key="img_engine_global",
            )
        with col_cnt1:
            info_img_count = st.number_input(
                "정보성 이미지 수", min_value=1, max_value=5,
                value=st.session_state.get("_info_img_count", config.get("defaults", {}).get("info_image_count", 2)),
                key="_info_img_count",
            )
        with col_cnt2:
            promo_img_count = st.number_input(
                "홍보성 이미지 수", min_value=1, max_value=5,
                value=st.session_state.get("_promo_img_count", config.get("defaults", {}).get("promo_image_count", 1)),
                key="_promo_img_count",
            )

        # 이미지 설정 기본값 저장
        if st.button("💾 이미지 설정 기본값으로 저장", key="btn_save_img_defaults", help="현재 이미지 엔진/카운트를 기본값으로 저장합니다"):
            _cfg = get_config()
            _cfg.setdefault("defaults", {})
            _cfg["defaults"]["image_engine"] = img_engine_global
            _cfg["defaults"]["info_image_count"] = info_img_count
            _cfg["defaults"]["promo_image_count"] = promo_img_count
            save_config(_cfg)
            st.success("이미지 설정 기본값이 저장되었습니다.", icon="✅")

        # 분석 엔진 안내
        analyzer_preview = ImageVariableAnalyzer(config)
        ep = analyzer_preview.pick_engine()
        if ep:
            st.caption(f"변수 분석 엔진: **{ep[0]} / {ep[1]}** | 예상 분석 비용: ₩{analyzer_preview.get_estimated_cost():.2f}/건")
        else:
            st.warning("변수 분석에 사용할 수 있는 API 키가 없습니다. 기본값으로 대체됩니다.")

    # ── 이미지 생성기 초기화 ──
    _img_gen_config = {
        "gemini_api_key": config.get("api_keys", {}).get("gemini", ""),
        "openai_api_key": config.get("api_keys", {}).get("openai", ""),
        "replicate_api_key": config.get("api_keys", {}).get("replicate", ""),
        "ideogram_api_key": config.get("api_keys", {}).get("ideogram", ""),
        "image_dir": "./data/images",
    }
    img_generator = ImageGenerator(_img_gen_config)
    img_builder = ImagePromptBuilder()
    img_analyzer = ImageVariableAnalyzer(config)

    # Room 인덱스 (드롭다운 그룹핑용)
    _rooms: dict[str, list[dict]] = {}
    for _loc in APARTMENT_LOCATIONS:
        _rooms.setdefault(_loc["room_kr"], []).append(_loc)
    _room_names = list(_rooms.keys())

    # 선택된 이미지 엔진
    _selected_img_engine = st.session_state.get("img_engine_global", "gemini_image")

    # ── 글별 이미지 생성 UI ──
    for idx, result in successful_results:
        vars_key = f"img_vars_{idx}"
        gen_key = f"img_generated_{idx}"
        r_content_type = result.get("_content_type", "정보성")
        r_img_count = info_img_count if r_content_type == "정보성" else promo_img_count

        with st.expander(f"📷 {result.get('title', f'글 {idx+1}')} [{r_content_type}]", expanded=(idx == 0)):

            # ── 변수 분석 버튼 ──
            ana_col, status_col = st.columns([2, 5])
            with ana_col:
                if st.button("🔍 변수 자동분석", key=f"btn_analyze_{idx}"):
                    with st.spinner("AI 분석 중..."):
                        analysis = img_analyzer.analyze(
                            result,
                            APARTMENT_LOCATIONS, APARTMENT_DIRT_LEVELS,
                            APARTMENT_LIGHT_SOURCES, APARTMENT_ANGLES,
                        )
                    st.session_state["img_vars"][vars_key] = analysis
                    st.rerun()

            current_vars = st.session_state["img_vars"].get(vars_key)
            with status_col:
                if current_vars:
                    eng = current_vars.get("engine", "")
                    cost = current_vars.get("cost_estimate", 0)
                    reason = current_vars.get("reason", "")
                    if eng and eng != "none":
                        st.caption(f"분석 엔진: {eng}/{current_vars.get('model','')} | 비용: ₩{cost:.2f} | {reason}")
                    else:
                        st.caption(reason)
                else:
                    st.caption("자동분석 버튼을 누르거나 아래에서 변수를 직접 선택하세요.")

            # 기본값 세팅 (분석 전 상태)
            if current_vars is None:
                current_vars = {
                    "location_id": APARTMENT_LOCATIONS[0]["id"],
                    "dirt_level": 3,
                    "light_id": APARTMENT_LIGHT_SOURCES[0]["id"],
                    "angle_id": APARTMENT_ANGLES[0]["id"],
                }

            st.markdown("**변수 설정**")

            # Location 선택 (공간 → 위치 2단계)
            cur_loc = next(
                (l for l in APARTMENT_LOCATIONS if l["id"] == current_vars.get("location_id")),
                APARTMENT_LOCATIONS[0],
            )
            cur_room_kr = cur_loc["room_kr"]

            lc1, lc2 = st.columns(2)
            with lc1:
                sel_room = st.selectbox(
                    "공간",
                    options=_room_names,
                    index=_room_names.index(cur_room_kr) if cur_room_kr in _room_names else 0,
                    key=f"sel_room_{idx}",
                )
            room_locs = _rooms[sel_room]
            room_loc_ids = [l["id"] for l in room_locs]
            cur_loc_idx = room_loc_ids.index(current_vars["location_id"]) if current_vars["location_id"] in room_loc_ids else 0

            with lc2:
                sel_loc_id = st.selectbox(
                    "촬영 위치",
                    options=room_loc_ids,
                    index=cur_loc_idx,
                    format_func=lambda x: next(l["location_kr"] for l in APARTMENT_LOCATIONS if l["id"] == x),
                    key=f"sel_loc_{idx}",
                )

            vc1, vc2, vc3 = st.columns(3)
            with vc1:
                sel_dirt = st.slider(
                    "더러움 레벨",
                    min_value=1, max_value=5,
                    value=int(current_vars.get("dirt_level", 3)),
                    key=f"sel_dirt_{idx}",
                )
                dirt_info = next(d for d in APARTMENT_DIRT_LEVELS if d["level"] == sel_dirt)
                st.caption(f"{dirt_info['name_kr']} ({dirt_info['name_en']})")

            with vc2:
                light_ids = [l["id"] for l in APARTMENT_LIGHT_SOURCES]
                cur_light_idx = light_ids.index(current_vars.get("light_id", "L1")) if current_vars.get("light_id") in light_ids else 0
                sel_light_id = st.selectbox(
                    "조명",
                    options=light_ids,
                    index=cur_light_idx,
                    format_func=lambda x: next(l["label_kr"] for l in APARTMENT_LIGHT_SOURCES if l["id"] == x),
                    key=f"sel_light_{idx}",
                )

            with vc3:
                angle_ids = [a["id"] for a in APARTMENT_ANGLES]
                cur_angle_idx = angle_ids.index(current_vars.get("angle_id", "A1")) if current_vars.get("angle_id") in angle_ids else 0
                sel_angle_id = st.selectbox(
                    "카메라 각도",
                    options=angle_ids,
                    index=cur_angle_idx,
                    format_func=lambda x: next(a["label_kr"] for a in APARTMENT_ANGLES if a["id"] == x),
                    key=f"sel_angle_{idx}",
                )

            # ── 프롬프트 미리보기 ──
            preview_vars = {
                "location_id": sel_loc_id,
                "dirt_level": sel_dirt,
                "light_id": sel_light_id,
                "angle_id": sel_angle_id,
            }
            st.caption("생성될 프롬프트 미리보기")
            st.code(img_builder.build_apartment_prompt(preview_vars), language=None)

            # ── 이미지 생성 버튼 ──
            gc1, gc2 = st.columns([2, 5])
            with gc1:
                engine_available = img_generator.is_available(_selected_img_engine)
                if not engine_available:
                    st.warning(f"'{IMAGE_ENGINE_CONFIGS[_selected_img_engine]['label']}' API 키를 설정해주세요.")

                if st.button(
                    f"이미지 {r_img_count}장 생성",
                    type="primary",
                    disabled=not engine_available,
                    key=f"btn_gen_img_{idx}",
                ):
                    # 변수 확정 저장
                    st.session_state["img_vars"][vars_key] = preview_vars

                    prompts = img_builder.build_apartment_prompts(preview_vars, count=r_img_count)
                    generated = []
                    prog = st.progress(0, text="이미지 생성 중...")

                    for i, pd in enumerate(prompts):
                        try:
                            img_result = img_generator.generate(
                                engine=_selected_img_engine,
                                prompt=pd["prompt"],
                                options={},
                            )
                            img_result["light_kr"] = pd["light_kr"]
                            img_result["angle_kr"] = pd["angle_kr"]

                            # DB 저장
                            GeneratedImage.create(
                                keyword_id=result.get("_keyword_id", ""),
                                article=result.get("_article_id"),
                                engine=img_result["engine"],
                                prompt_used=img_result["prompt_used"],
                                local_path=img_result["local_path"],
                                width=img_result.get("width", 0),
                                height=img_result.get("height", 0),
                                cost_estimate=img_result.get("cost_estimate", 0),
                            )
                            generated.append(img_result)
                        except Exception as exc:
                            generated.append({"error": str(exc)})
                        prog.progress((i + 1) / r_img_count, text=f"{i+1}/{r_img_count} 완료")

                    prog.empty()
                    st.session_state["img_generated"][gen_key] = generated
                    st.rerun()

            with gc2:
                img_cfg = IMAGE_ENGINE_CONFIGS.get(_selected_img_engine, {})
                st.caption(f"엔진: {img_cfg.get('label', _selected_img_engine)} | {img_cfg.get('cost_per_image', '')} × {r_img_count}장")

            # ── 생성된 이미지 표시 ──
            if gen_key in st.session_state["img_generated"]:
                gen_imgs = st.session_state["img_generated"][gen_key]
                st.markdown("**생성된 이미지**")
                cols = st.columns(min(len(gen_imgs), 3))
                for i, img_data in enumerate(gen_imgs):
                    with cols[i % len(cols)]:
                        if "error" in img_data:
                            st.error(f"오류: {img_data['error']}")
                        else:
                            st.image(img_data["local_path"], use_container_width=True)
                            st.caption(
                                f"{img_data.get('light_kr','')} / {img_data.get('angle_kr','')} "
                                f"| ₩{img_data.get('cost_estimate', 0)}"
                            )
