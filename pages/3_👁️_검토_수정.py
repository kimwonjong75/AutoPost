"""
검토/수정 — 이미지 검토 + 글 검토/수정 (미리보기)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.content_generator import ENGINE_CONFIGS, ContentGenerator, load_config
from modules.image_generator import IMAGE_ENGINE_CONFIGS, ImageGenerator
from modules.image_prompt_builder import ImagePromptBuilder
from modules.models import GeneratedArticle, GeneratedImage, init_db

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="검토/수정 — AutoPost",
    page_icon="👁️",
    layout="wide",
)

init_db()

from app import get_config, inject_custom_css, render_sidebar, render_status_bar

config = get_config()
inject_custom_css()
render_sidebar(config)
render_status_bar(config)

# ──────────────────────────────────────────────
# 페이지 전용 CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
.review-section {
    background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
    border: 1px solid #2D3250;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
}
.review-section-title {
    font-size: 1rem;
    font-weight: 700;
    color: #FAFAFA;
    margin-bottom: 0.8rem;
}
.img-card {
    background: #1A1D29;
    border: 1px solid #2D3250;
    border-radius: 10px;
    padding: 0.6rem;
    text-align: center;
}
.img-card .img-meta {
    font-size: 0.75rem;
    color: #A0A4B8;
    margin-top: 0.4rem;
}
.preview-box {
    background: #FFFFFF;
    color: #333333;
    border-radius: 10px;
    padding: 1.5rem 2rem;
    min-height: 400px;
    font-family: 'Noto Sans KR', sans-serif;
    line-height: 1.8;
}
.preview-box h1, .preview-box h2, .preview-box h3 {
    color: #1a1a1a;
    margin-top: 1.2rem;
    margin-bottom: 0.5rem;
}
.preview-box h2 { font-size: 1.3rem; border-bottom: 2px solid #00D68F; padding-bottom: 0.3rem; }
.preview-box h3 { font-size: 1.1rem; }
.preview-box p { margin-bottom: 0.8rem; }
.preview-box ul, .preview-box ol { margin-left: 1.2rem; margin-bottom: 0.8rem; }
.preview-box img { max-width: 100%; border-radius: 8px; margin: 0.5rem 0; }
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
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 세션 초기화
# ──────────────────────────────────────────────
if "review_generated_images" not in st.session_state:
    st.session_state["review_generated_images"] = []
if "review_selected_images" not in st.session_state:
    st.session_state["review_selected_images"] = set()

# ──────────────────────────────────────────────
# 글 목록 로드
# ──────────────────────────────────────────────
st.markdown("# 검토/수정")
st.caption("생성된 글을 검토하고 이미지를 첨부한 뒤 최종 확인합니다.")

# DB에서 검토 대상 글 목록 가져오기
articles = list(
    GeneratedArticle.select()
    .where(GeneratedArticle.status.in_(["생성완료", "검토완료"]))
    .order_by(GeneratedArticle.created_at.desc())
    .limit(50)
)

if not articles:
    st.info("검토할 글이 없습니다. 먼저 '글 생성' 페이지에서 글을 생성하세요.")
    st.stop()

# 글 선택
article_options = {
    a.id: f"[{a.status}] {a.title} ({a.engine}/{a.model} · {a.created_at:%m/%d %H:%M})"
    for a in articles
}
selected_article_id = st.selectbox(
    "검토할 글 선택",
    options=list(article_options.keys()),
    format_func=lambda x: article_options[x],
    key="review_article_select",
)

article = GeneratedArticle.get_by_id(selected_article_id)
article_tags = article.get_tags_list()

# 글 데이터를 dict로 준비 (이미지 프롬프트 빌더용)
article_data = {
    "title": article.title,
    "body_html": article.body_html,
    "tags": article_tags,
    "image_prompt": article.image_prompt or "",
    "keyword_id": article.keyword_id,
}

st.divider()

# ══════════════════════════════════════════════
# 영역 1: 이미지 검토
# ══════════════════════════════════════════════
st.markdown('<div class="review-section-title">이미지 검토</div>', unsafe_allow_html=True)

# 이미지 엔진 선택 + 생성 수
img_col1, img_col2, img_col3 = st.columns([3, 1, 1])

with img_col1:
    available_engines = list(IMAGE_ENGINE_CONFIGS.keys())
    default_img_engine = config.get("defaults", {}).get("image_engine", "gpt_image")
    default_idx = available_engines.index(default_img_engine) if default_img_engine in available_engines else 0

    img_engine = st.selectbox(
        "이미지 생성 엔진",
        options=available_engines,
        index=default_idx,
        format_func=lambda x: f"{IMAGE_ENGINE_CONFIGS[x]['label']} ({IMAGE_ENGINE_CONFIGS[x]['cost_per_image']})",
        key="review_img_engine",
    )

with img_col2:
    img_count = st.number_input(
        "생성 수",
        min_value=1,
        max_value=5,
        value=config.get("defaults", {}).get("image_count", 3),
        key="review_img_count",
    )

with img_col3:
    # 엔진별 옵션 (품질 등)
    engine_opts = IMAGE_ENGINE_CONFIGS[img_engine].get("options", {})
    img_extra_options = {}
    for opt_key, opt_cfg in engine_opts.items():
        if opt_cfg["type"] == "select":
            img_extra_options[opt_key] = st.selectbox(
                opt_key.replace("_", " ").title(),
                options=opt_cfg["options"],
                index=opt_cfg["options"].index(opt_cfg["default"]),
                key=f"review_imgopt_{opt_key}",
            )

# 이미지 생성 버튼
with st.form("image_generate_form"):
    st.markdown("**이미지 생성**")
    generate_submitted = st.form_submit_button(
        "이미지 생성",
        type="primary",
        use_container_width=True,
    )

    if generate_submitted:
        # API 키 확인
        key_field = IMAGE_ENGINE_CONFIGS[img_engine].get("api_key_field")
        if key_field and not config.get("api_keys", {}).get(key_field.replace("_api_key", "").replace("_", ""), ""):
            # api_key_field가 "openai_api_key" 형태일 수 있으므로 config 구조에 맞게 매핑
            api_keys = config.get("api_keys", {})
            key_map = {
                "openai_api_key": "openai",
                "gemini_api_key": "gemini",
                "replicate_api_key": "replicate",
                "ideogram_api_key": "ideogram",
            }
            config_key = key_map.get(key_field, key_field)
            if not api_keys.get(config_key, ""):
                st.error(f"{IMAGE_ENGINE_CONFIGS[img_engine]['label']} API 키가 설정되지 않았습니다.")
                st.stop()

        # ImageGenerator config 매핑
        api_keys = config.get("api_keys", {})
        gen_config = {
            "openai_api_key": api_keys.get("openai", ""),
            "gemini_api_key": api_keys.get("gemini", ""),
            "replicate_api_key": api_keys.get("replicate", ""),
            "ideogram_api_key": api_keys.get("ideogram", ""),
            "image_dir": config.get("paths", {}).get("image_dir", "./data/images"),
            "pricing": config.get("pricing", {}),
        }

        builder = ImagePromptBuilder()
        prompts = builder.build_prompts(article_data, count=img_count)

        generator = ImageGenerator(gen_config)
        new_images = []
        progress = st.progress(0, text="이미지 생성 중...")

        for i, p in enumerate(prompts):
            try:
                options = {
                    **img_extra_options,
                    "negative_prompt": p["negative_prompt"],
                    "aspect_ratio": p["aspect_ratio"],
                }
                result = generator.generate(img_engine, p["prompt"], options)
                new_images.append(result)
            except Exception as e:
                st.warning(f"이미지 {i+1} 생성 실패: {e}")
            progress.progress((i + 1) / len(prompts), text=f"{i+1}/{len(prompts)} 완료")

        progress.empty()
        st.session_state["review_generated_images"] = new_images
        st.session_state["review_selected_images"] = set()

        # DB에도 저장
        for img in new_images:
            GeneratedImage.create(
                keyword_id=article.keyword_id,
                article=article,
                engine=img["engine"],
                prompt_used=img["prompt_used"],
                local_path=img["local_path"],
                width=img["width"],
                height=img["height"],
                quality=img.get("quality", ""),
                cost_estimate=img["cost_estimate"],
                cost_usd=img.get("cost_usd", 0),
                is_selected=False,
            )

        if new_images:
            st.success(f"{len(new_images)}개 이미지 생성 완료!")

# DB에서 기존 이미지도 로드
db_images = list(
    GeneratedImage.select()
    .where(GeneratedImage.article == article)
    .order_by(GeneratedImage.created_at.desc())
)
if db_images and not st.session_state["review_generated_images"]:
    st.session_state["review_generated_images"] = [
        {
            "local_path": img.local_path,
            "prompt_used": img.prompt_used,
            "engine": img.engine,
            "cost_estimate": img.cost_estimate,
            "cost_usd": img.cost_usd,
            "width": img.width,
            "height": img.height,
            "_db_id": img.id,
        }
        for img in db_images
    ]
    st.session_state["review_selected_images"] = {
        i for i, img in enumerate(db_images) if img.is_selected
    }

# 생성된 이미지 그리드 표시
images = st.session_state.get("review_generated_images", [])
if images:
    st.markdown("---")
    st.markdown(f"**생성된 이미지 ({len(images)}개)**")

    # 3열 그리드
    grid_cols = st.columns(min(len(images), 3))
    selected = st.session_state.get("review_selected_images", set())

    for i, img in enumerate(images):
        with grid_cols[i % 3]:
            # 이미지 표시
            img_path = img.get("local_path", "")
            if img_path and Path(img_path).exists():
                st.image(img_path, use_container_width=True)
            else:
                st.warning("이미지 파일을 찾을 수 없습니다.")

            # 엔진명 + 비용
            engine_label = IMAGE_ENGINE_CONFIGS.get(img.get("engine", ""), {}).get("label", img.get("engine", ""))
            st.caption(f"{engine_label} | 비용: ~₩{img.get('cost_estimate', 0)}")

            # 선택 체크박스
            is_checked = st.checkbox(
                "첨부 선택",
                value=i in selected,
                key=f"img_sel_{selected_article_id}_{i}",
            )
            if is_checked:
                selected.add(i)
            elif i in selected:
                selected.discard(i)

    st.session_state["review_selected_images"] = selected

    # 선택 요약
    if selected:
        total_cost = sum(images[i].get("cost_estimate", 0) for i in selected if i < len(images))
        st.info(f"선택된 이미지: {len(selected)}개 | 총 비용: ~₩{total_cost:,.0f}")

# 프롬프트 직접 수정 후 재생성
with st.expander("프롬프트 직접 수정 후 재생성"):
    with st.form("custom_prompt_form"):
        custom_prompt = st.text_area(
            "이미지 프롬프트 (영어)",
            value=article.image_prompt or "",
            height=100,
            key="review_custom_prompt",
        )
        custom_submitted = st.form_submit_button("이 프롬프트로 생성")

        if custom_submitted and custom_prompt.strip():
            api_keys = config.get("api_keys", {})
            gen_config = {
                "openai_api_key": api_keys.get("openai", ""),
                "gemini_api_key": api_keys.get("gemini", ""),
                "replicate_api_key": api_keys.get("replicate", ""),
                "ideogram_api_key": api_keys.get("ideogram", ""),
                "image_dir": config.get("paths", {}).get("image_dir", "./data/images"),
                "pricing": config.get("pricing", {}),
            }
            generator = ImageGenerator(gen_config)
            try:
                result = generator.generate(img_engine, custom_prompt.strip(), img_extra_options)
                st.session_state["review_generated_images"].append(result)

                GeneratedImage.create(
                    keyword_id=article.keyword_id,
                    article=article,
                    engine=result["engine"],
                    prompt_used=result["prompt_used"],
                    local_path=result["local_path"],
                    width=result["width"],
                    height=result["height"],
                    quality=result.get("quality", ""),
                    cost_estimate=result["cost_estimate"],
                    cost_usd=result.get("cost_usd", 0),
                    is_selected=False,
                )
                st.success("이미지 생성 완료!")
                st.rerun()
            except Exception as e:
                st.error(f"이미지 생성 실패: {e}")

# 로컬 이미지 업로드
with st.expander("로컬 이미지 업로드"):
    uploaded_files = st.file_uploader(
        "이미지 파일 선택",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="review_local_upload",
    )
    if uploaded_files:
        if st.button("업로드", key="btn_upload_local"):
            api_keys = config.get("api_keys", {})
            gen_config = {
                "image_dir": config.get("paths", {}).get("image_dir", "./data/images"),
            }
            generator = ImageGenerator(gen_config)

            for f in uploaded_files:
                # 임시 파일로 저장 후 load_local_image 호출
                temp_dir = tempfile.mkdtemp()
                temp_path = os.path.join(temp_dir, f.name)
                with open(temp_path, "wb") as tf:
                    tf.write(f.getbuffer())

                result = generator.load_local_image(temp_path, article.keyword_id)
                st.session_state["review_generated_images"].append(result)

                GeneratedImage.create(
                    keyword_id=article.keyword_id,
                    article=article,
                    engine="local",
                    prompt_used="(로컬 업로드)",
                    local_path=result["local_path"],
                    width=result["width"],
                    height=result["height"],
                    quality="",
                    cost_estimate=0,
                    cost_usd=0,
                    is_selected=False,
                )

            st.success(f"{len(uploaded_files)}개 이미지 업로드 완료!")
            st.rerun()

st.divider()

# ══════════════════════════════════════════════
# 영역 2: 글 검토/수정
# ══════════════════════════════════════════════
st.markdown('<div class="review-section-title">글 검토/수정</div>', unsafe_allow_html=True)

editor_col, preview_col = st.columns([1, 1])

# 왼쪽: 에디터
with editor_col:
    st.markdown("**에디터**")

    with st.form("article_edit_form"):
        edit_title = st.text_input(
            "제목",
            value=article.title,
            key="edit_title",
        )

        edit_body = st.text_area(
            "본문 (HTML)",
            value=article.body_html,
            height=400,
            key="edit_body",
        )

        edit_tags = st.text_input(
            "태그 (쉼표 구분)",
            value=", ".join(article_tags),
            key="edit_tags",
        )

        edit_image_prompt = st.text_input(
            "이미지 프롬프트",
            value=article.image_prompt or "",
            key="edit_image_prompt",
        )

        # 메타 정보
        st.caption(
            f"엔진: {article.engine} | 모델: {article.model} | "
            f"토큰: {article.tokens_used:,} | 비용: ₩{article.cost_estimate:,.1f}"
        )

        # 선택된 이미지 미리보기
        selected_indices = st.session_state.get("review_selected_images", set())
        if selected_indices and images:
            st.markdown("**선택된 이미지**")
            sel_cols = st.columns(min(len(selected_indices), 3))
            for col_idx, img_idx in enumerate(sorted(selected_indices)):
                if img_idx < len(images):
                    with sel_cols[col_idx % 3]:
                        img_path = images[img_idx].get("local_path", "")
                        if img_path and Path(img_path).exists():
                            st.image(img_path, use_container_width=True, caption=f"#{img_idx+1}")

        # 버튼 행
        btn_col1, btn_col2, btn_col3 = st.columns(3)

        with btn_col1:
            save_submitted = st.form_submit_button("저장", use_container_width=True)

        with btn_col2:
            review_done = st.form_submit_button("검토 완료", type="primary", use_container_width=True)

        with btn_col3:
            regenerate = st.form_submit_button("재생성", use_container_width=True)

    # 폼 외부: 결과 처리
    if save_submitted or review_done:
        # 글 업데이트
        new_tags = [t.strip() for t in edit_tags.split(",") if t.strip()]
        article.title = edit_title
        article.body_html = edit_body
        article.set_tags_list(new_tags)
        article.image_prompt = edit_image_prompt

        if review_done:
            article.status = "검토완료"

        article.save()

        # 선택된 이미지 상태 업데이트
        if images:
            for i, img in enumerate(images):
                db_id = img.get("_db_id")
                if db_id:
                    GeneratedImage.update(
                        is_selected=(i in selected_indices)
                    ).where(GeneratedImage.id == db_id).execute()

        if review_done:
            st.success("검토 완료! 발행 대기 상태로 변경되었습니다.")
        else:
            st.success("저장되었습니다.")
        st.rerun()

    if regenerate:
        st.session_state["_regenerate_article"] = selected_article_id

# 재생성 처리 (폼 밖)
if st.session_state.get("_regenerate_article") == selected_article_id:
    st.session_state.pop("_regenerate_article", None)
    st.info("글 생성 페이지에서 동일 키워드로 다시 생성해주세요.")

# AI 수정 요청
with st.expander("AI 수정 요청"):
    with st.form("ai_modify_form"):
        modification_request = st.text_area(
            "수정 요청 사항",
            placeholder="예: 좀 더 친근한 톤으로 변경해주세요 / 문단을 줄여주세요 / 결론 부분을 강화해주세요",
            height=80,
            key="ai_modify_request",
        )
        ai_engine_for_modify = st.selectbox(
            "수정에 사용할 AI 엔진",
            options=list(ENGINE_CONFIGS.keys()),
            format_func=lambda x: ENGINE_CONFIGS[x]["label"],
            key="ai_modify_engine",
        )
        ai_model_for_modify = st.selectbox(
            "모델",
            options=[m["id"] for m in ENGINE_CONFIGS[ai_engine_for_modify]["models"]],
            format_func=lambda x: next(
                (m["name"] for m in ENGINE_CONFIGS[ai_engine_for_modify]["models"] if m["id"] == x), x
            ),
            key="ai_modify_model",
        )
        modify_submitted = st.form_submit_button("AI 수정 실행", type="primary", use_container_width=True)

    if modify_submitted and modification_request.strip():
        try:
            gen = ContentGenerator(config)

            system_prompt = (
                "당신은 블로그 글 수정 전문가입니다. "
                "아래 블로그 글을 사용자의 요청에 맞게 수정하세요.\n"
                "원래 글의 구조(HTML 태그)를 유지하되, 요청된 부분만 수정합니다.\n\n"
                "[출력 형식 - 반드시 JSON으로]\n"
                '{"title": "수정된 제목", "body_html": "수정된 본문 HTML", '
                '"tags": ["태그1", "태그2"], "image_prompt": "이미지 프롬프트 (영어)"}'
            )
            user_prompt = (
                f"[원본 제목]\n{article.title}\n\n"
                f"[원본 본문]\n{article.body_html}\n\n"
                f"[수정 요청]\n{modification_request}"
            )

            with st.spinner("AI가 글을 수정하고 있습니다..."):
                result = gen.generate(
                    engine=ai_engine_for_modify,
                    model=ai_model_for_modify,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

            # DB 업데이트
            article.title = result.get("title", article.title)
            article.body_html = result.get("body_html", article.body_html)
            if result.get("tags"):
                article.set_tags_list(result["tags"])
            if result.get("image_prompt"):
                article.image_prompt = result["image_prompt"]

            meta = result.get("meta", {})
            article.cost_estimate = article.cost_estimate + meta.get("cost_estimate", 0)
            article.cost_usd = article.cost_usd + meta.get("cost_usd", 0)
            article.tokens_used = article.tokens_used + meta.get("tokens_used", 0)
            article.input_tokens = article.input_tokens + meta.get("input_tokens", 0)
            article.output_tokens = article.output_tokens + meta.get("output_tokens", 0)
            article.save()

            st.success("AI 수정 완료!")
            st.rerun()

        except Exception as e:
            st.error(f"AI 수정 실패: {e}")

# 오른쪽: 미리보기
with preview_col:
    st.markdown("**미리보기**")

    # 현재 편집 상태 반영 (세션에서 읽기)
    preview_title = article.title
    preview_body = article.body_html
    preview_tags = article_tags

    # 선택된 이미지 HTML
    selected_images_html = ""
    selected_indices = st.session_state.get("review_selected_images", set())
    if selected_indices and images:
        for idx in sorted(selected_indices):
            if idx < len(images):
                img_path = images[idx].get("local_path", "")
                if img_path and Path(img_path).exists():
                    # file:// 프로토콜 대신 data URI 사용
                    import base64
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()
                    ext = Path(img_path).suffix.lstrip(".")
                    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
                    b64 = base64.b64encode(img_bytes).decode()
                    selected_images_html += (
                        f'<img src="data:image/{mime};base64,{b64}" '
                        f'style="max-width:100%;border-radius:8px;margin:0.5rem 0;" />'
                    )

    # 태그 HTML
    tags_html = ""
    if preview_tags:
        tags_html = '<div style="margin-bottom:1rem;">'
        for t in preview_tags:
            tags_html += f'<span style="display:inline-block;background:#E8F5E9;color:#2E7D32;padding:3px 10px;border-radius:15px;font-size:0.8rem;margin-right:4px;margin-bottom:4px;">#{t}</span>'
        tags_html += "</div>"

    # 미리보기 렌더링
    st.markdown(
        f"""
        <div class="preview-box">
            <h1 style="font-size:1.5rem;color:#1a1a1a;margin-bottom:0.5rem;">{preview_title}</h1>
            {tags_html}
            {selected_images_html}
            {preview_body}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 글 정보 요약
    st.caption(
        f"상태: {article.status} | 키워드: {article.keyword_id} | "
        f"생성: {article.created_at:%Y-%m-%d %H:%M}"
    )
