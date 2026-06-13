"""
설정 페이지 — API 키, 발행 설정, 프롬프트 템플릿, ADB/IP
"""

import datetime
import sys
import yaml
import subprocess
import streamlit as st
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules import pricing
from modules.attachment_manager import AttachmentManager
from modules.content_generator import ENGINE_CONFIGS
from modules.image_generator import IMAGE_ENGINE_CONFIGS
from modules.prompt_loader import (
    TEMPLATE_INFO_ID, TEMPLATE_PRODUCT_ID,
    DEFAULT_INFO_PROMPT, DEFAULT_PRODUCT_PROMPT,
    load_template, save_template,
)
from app import get_secrets, save_secrets, save_config as _app_save_config

# ──────────────────────────────────────────────
# config.yaml 경로 / 상수
# ──────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
MAX_PRODUCTS = 15


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict):
    _app_save_config(config)


def mask_key(key: str) -> str:
    """API 키를 마스킹하여 표시"""
    if not key or len(key) < 8:
        return key
    return key[:4] + "•" * (len(key) - 8) + key[-4:]


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
st.header("설정")

config = load_config()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["API 키", "발행 설정", "프롬프트 템플릿", "ADB / IP", "블로그 계정", "상품 리스트", "단가 · 환율"]
)

# ══════════════════════════════════════════════
# 탭 1: API 키
# ══════════════════════════════════════════════
with tab1:
    st.subheader("API 키 관리")
    st.caption("각 AI 서비스의 API 키를 입력하세요. 키는 **secrets.yaml**에 저장되며 Git에 포함되지 않습니다.")

    secrets = get_secrets()
    api_keys = secrets.get("api_keys", {})

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**AI 글 작성 엔진**")

        openai_key = st.text_input(
            "OpenAI API Key",
            value=api_keys.get("openai", ""),
            type="password",
            help="GPT 글 작성 + GPT Image 이미지 생성에 공통 사용",
            placeholder="sk-proj-...",
        )

        claude_key = st.text_input(
            "Claude API Key (Anthropic)",
            value=api_keys.get("claude", ""),
            type="password",
            help="Anthropic Claude 글 작성에 사용",
            placeholder="sk-ant-...",
        )

        gemini_key = st.text_input(
            "Gemini API Key (Google)",
            value=api_keys.get("gemini", ""),
            type="password",
            help="Google Gemini 글 작성 + Imagen 3 + Gemini 2.0 Flash 이미지 생성에 공통 사용",
            placeholder="AIza...",
        )

    with col_right:
        st.markdown("**이미지 생성 엔진**")
        st.info(
            "**Gemini 이미지 생성** (Imagen 3 / Flash 2.0)\n\n"
            "왼쪽의 **Gemini API Key**를 공통으로 사용합니다.",
            icon="ℹ️",
        )

        replicate_key = st.text_input(
            "Replicate API Key (Flux)",
            value=api_keys.get("replicate", ""),
            type="password",
            help="Flux Schnell/Pro 이미지 생성에 사용",
            placeholder="r8_...",
        )

        ideogram_key = st.text_input(
            "Ideogram API Key",
            value=api_keys.get("ideogram", ""),
            type="password",
            help="Ideogram 2.0 이미지 생성에 사용 (한국어 텍스트 포함 이미지에 최적)",
        )

        st.markdown("**구글 시트 연동**")

        gs_config = config.get("google_sheet", {})
        sheet_id = st.text_input(
            "구글 시트 ID",
            value=gs_config.get("sheet_id", ""),
            help="구글 스프레드시트 URL에서 /d/ 뒤의 ID",
            placeholder="1BxiM...",
        )
        sa_json_path = st.text_input(
            "서비스 계정 JSON 경로",
            value=gs_config.get("service_account_json", "./data/google-service-account.json"),
            help="구글 서비스 계정 키 파일 경로",
        )

    # 설정된 키 상태 표시
    st.divider()
    st.markdown("**현재 상태**")
    status_cols = st.columns(5)
    key_status = [
        ("OpenAI", openai_key),
        ("Claude", claude_key),
        ("Gemini", gemini_key),
        ("Replicate", replicate_key),
        ("Ideogram", ideogram_key),
    ]
    for col, (name, key) in zip(status_cols, key_status):
        with col:
            if key:
                st.success(f"{name}: {mask_key(key)}", icon="✅")
            else:
                st.warning(f"{name}: 미설정", icon="⚠️")

    st.markdown("")
    if st.button("저장", key="save_api_keys", type="primary", use_container_width=True):
        # API 키는 secrets.yaml에 저장 (Git 제외)
        secrets = get_secrets()
        secrets.setdefault("api_keys", {})
        secrets["api_keys"]["openai"] = openai_key
        secrets["api_keys"]["claude"] = claude_key
        secrets["api_keys"]["gemini"] = gemini_key
        secrets["api_keys"]["replicate"] = replicate_key
        secrets["api_keys"]["ideogram"] = ideogram_key
        save_secrets(secrets)

        # 구글 시트 설정은 config.yaml에 저장 (민감 정보 아님)
        config.setdefault("google_sheet", {})
        config["google_sheet"]["sheet_id"] = sheet_id
        config["google_sheet"]["service_account_json"] = sa_json_path
        save_config(config)

        st.success("API 키가 secrets.yaml에 저장되었습니다. (Git에 포함되지 않습니다)")


# ══════════════════════════════════════════════
# 탭 2: 발행 설정
# ══════════════════════════════════════════════
with tab2:
    st.subheader("발행 설정")
    st.caption("블로그 발행 시 사용되는 타이밍 및 브라우저 설정입니다.")

    publish = config.get("publish", {})

    st.markdown("**블로그 간 대기 시간 (초)**")
    st.caption("서로 다른 블로그에 발행할 때 사이의 대기 시간")
    inter_blog = publish.get("inter_blog_delay", [60, 180])
    ib_col1, ib_col2 = st.columns(2)
    with ib_col1:
        ib_min = st.number_input("최소 (초)", value=int(inter_blog[0]), min_value=0, max_value=600, key="ib_min")
    with ib_col2:
        ib_max = st.number_input("최대 (초)", value=int(inter_blog[1]), min_value=0, max_value=600, key="ib_max")

    st.divider()

    st.markdown("**같은 블로그 연속 발행 대기 (초)**")
    st.caption("동일 블로그에 연속으로 발행할 때 사이의 대기 시간")
    inter_post = publish.get("inter_post_delay", [30, 90])
    ip_col1, ip_col2 = st.columns(2)
    with ip_col1:
        ip_min = st.number_input("최소 (초)", value=int(inter_post[0]), min_value=0, max_value=600, key="ip_min")
    with ip_col2:
        ip_max = st.number_input("최대 (초)", value=int(inter_post[1]), min_value=0, max_value=600, key="ip_max")

    st.divider()

    st.markdown("**에디터 내 액션 딜레이 (초)**")
    st.caption("블로그 에디터에서 텍스트 입력, 이미지 삽입 등 개별 액션 간 대기 시간")
    action_delay = publish.get("action_delay", [1.5, 4.0])
    ad_col1, ad_col2 = st.columns(2)
    with ad_col1:
        ad_min = st.number_input("최소 (초)", value=float(action_delay[0]), min_value=0.0, max_value=30.0, step=0.5, key="ad_min")
    with ad_col2:
        ad_max = st.number_input("최대 (초)", value=float(action_delay[1]), min_value=0.0, max_value=30.0, step=0.5, key="ad_max")

    st.divider()

    retry_col, browser_col = st.columns(2)
    with retry_col:
        max_retries = st.number_input(
            "최대 재시도 횟수",
            value=publish.get("max_retries", 2),
            min_value=0,
            max_value=10,
            help="발행 실패 시 자동 재시도 횟수",
        )

    with browser_col:
        browser_options = ["undetected_chromedriver", "nodriver"]
        current_browser = publish.get("browser_engine", "undetected_chromedriver")
        browser_engine = st.selectbox(
            "브라우저 엔진",
            options=browser_options,
            index=browser_options.index(current_browser) if current_browser in browser_options else 0,
            help="undetected_chromedriver: 안정적, nodriver: 차세대 (실험적)",
        )

    st.markdown("")
    if st.button("저장", key="save_publish", type="primary", use_container_width=True):
        if ib_min > ib_max:
            st.error("블로그 간 대기 시간: 최소값이 최대값보다 클 수 없습니다.")
        elif ip_min > ip_max:
            st.error("연속 발행 대기 시간: 최소값이 최대값보다 클 수 없습니다.")
        elif ad_min > ad_max:
            st.error("액션 딜레이: 최소값이 최대값보다 클 수 없습니다.")
        else:
            config.setdefault("publish", {})
            config["publish"]["inter_blog_delay"] = [ib_min, ib_max]
            config["publish"]["inter_post_delay"] = [ip_min, ip_max]
            config["publish"]["action_delay"] = [ad_min, ad_max]
            config["publish"]["max_retries"] = max_retries
            config["publish"]["browser_engine"] = browser_engine

            save_config(config)
            st.success("발행 설정이 저장되었습니다.")


# ══════════════════════════════════════════════
# 탭 3: 프롬프트 템플릿
# ══════════════════════════════════════════════
with tab3:
    st.subheader("프롬프트 템플릿 관리")
    st.caption("AI 글 작성 시 사용되는 시스템 프롬프트를 관리합니다. templates/ 폴더에 저장됩니다.")

    info_prompt = load_template("info_prompt.txt", DEFAULT_INFO_PROMPT)
    product_prompt = load_template("product_prompt.txt", DEFAULT_PRODUCT_PROMPT)

    st.markdown("**정보성 글 프롬프트**")
    edited_info = st.text_area(
        "정보성 글 시스템 프롬프트",
        value=info_prompt,
        height=300,
        key="info_prompt_editor",
        label_visibility="collapsed",
    )

    st.markdown("**상품홍보 글 프롬프트**")
    edited_product = st.text_area(
        "상품홍보 글 시스템 프롬프트",
        value=product_prompt,
        height=300,
        key="product_prompt_editor",
        label_visibility="collapsed",
    )

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("저장", key="save_prompts", type="primary", use_container_width=True):
            save_template("info_prompt.txt", edited_info)
            save_template("product_prompt.txt", edited_product)
            st.success("프롬프트 템플릿이 저장되었습니다.")

    with btn_col2:
        if st.button("기본값 복원", key="reset_prompts", use_container_width=True):
            save_template("info_prompt.txt", DEFAULT_INFO_PROMPT)
            save_template("product_prompt.txt", DEFAULT_PRODUCT_PROMPT)
            st.success("프롬프트가 기본값으로 복원되었습니다.")
            st.rerun()

    st.divider()

    # ─── 프롬프트 참고자료 첨부 ───
    st.subheader("프롬프트 참고자료 첨부")
    st.caption("각 글 유형별로 참고자료를 등록하면 AI 글 생성 시 자동으로 프롬프트에 포함됩니다.")

    att_manager = AttachmentManager()

    def render_template_attachments(template_id: str, label: str, upload_key: str, save_key: str):
        st.markdown(f"**{label}**")
        existing = att_manager.get_attachments(template_id)
        if existing:
            for att in existing:
                type_icon = {"pdf": "📄", "image": "🖼️", "text": "📝"}.get(att.file_type, "📎")
                size_kb = att.file_size // 1024
                c1, c2, c3 = st.columns([4, 2, 1])
                with c1:
                    st.markdown(f"{type_icon} **{att.original_filename}**")
                with c2:
                    st.caption(f"{att.file_type} | {size_kb}KB")
                with c3:
                    if st.button("삭제", key=f"del_tpl_att_{att.id}"):
                        att_manager.delete_attachment(att.id)
                        st.rerun()
        else:
            st.caption("등록된 참고자료가 없습니다.")

        uploaded = st.file_uploader(
            "파일 추가 (PDF, 이미지, 텍스트)",
            type=["pdf", "jpg", "jpeg", "png", "txt", "md", "csv"],
            accept_multiple_files=True,
            key=upload_key,
        )
        if uploaded:
            if st.button("첨부파일 저장", key=save_key):
                for f in uploaded:
                    att_manager.save(template_id, f)
                st.success(f"{len(uploaded)}개 파일이 저장되었습니다.")
                st.rerun()

    tpl_col1, tpl_col2 = st.columns(2)
    with tpl_col1:
        render_template_attachments(TEMPLATE_INFO_ID, "정보성 글 참고자료", "tpl_info_upload", "tpl_info_save")
    with tpl_col2:
        render_template_attachments(TEMPLATE_PRODUCT_ID, "상품홍보 글 참고자료", "tpl_product_upload", "tpl_product_save")


# ══════════════════════════════════════════════
# 탭 4: ADB / IP
# ══════════════════════════════════════════════
with tab4:
    st.subheader("ADB / IP 변경 설정")
    st.caption("Android 기기의 비행기모드를 제어하여 IP를 변경하는 설정입니다.")

    adb_config = config.get("adb", {})

    adb_path = st.text_input(
        "ADB 경로",
        value=adb_config.get("path", "C:\\platform-tools\\adb.exe"),
        help="Android Debug Bridge 실행 파일 경로",
    )

    st.divider()

    st.markdown("**비행기모드 대기 시간**")
    adb_col1, adb_col2 = st.columns(2)
    with adb_col1:
        airplane_on_wait = st.number_input(
            "비행기모드 ON 후 대기 (초)",
            value=adb_config.get("airplane_on_wait", 8),
            min_value=1,
            max_value=60,
            help="비행기모드를 켠 후 네트워크 완전 차단까지 대기 시간",
        )
    with adb_col2:
        airplane_off_wait = st.number_input(
            "비행기모드 OFF 후 대기 (초)",
            value=adb_config.get("airplane_off_wait", 20),
            min_value=1,
            max_value=120,
            help="비행기모드를 끈 후 새 IP 할당까지 대기 시간",
        )

    ip_check_retries = st.number_input(
        "IP 확인 재시도 횟수",
        value=adb_config.get("ip_check_retries", 3),
        min_value=1,
        max_value=10,
        help="IP 변경 확인 실패 시 재시도 횟수",
    )

    st.markdown("")
    if st.button("저장", key="save_adb", type="primary", use_container_width=True):
        config.setdefault("adb", {})
        config["adb"]["path"] = adb_path
        config["adb"]["airplane_on_wait"] = airplane_on_wait
        config["adb"]["airplane_off_wait"] = airplane_off_wait
        config["adb"]["ip_check_retries"] = ip_check_retries

        save_config(config)
        st.success("ADB 설정이 저장되었습니다.")

    st.divider()

    # 테스트 버튼들
    st.markdown("**연결 테스트**")
    test_col1, test_col2 = st.columns(2)

    with test_col1:
        if st.button("ADB 연결 테스트", use_container_width=True):
            try:
                result = subprocess.run(
                    [adb_path, "devices"],
                    capture_output=True, text=True, timeout=10,
                )
                output = result.stdout.strip()
                devices = [
                    line for line in output.split("\n")[1:]
                    if line.strip() and "device" in line
                ]

                if devices:
                    st.success(f"ADB 연결 성공! {len(devices)}대 기기 감지")
                    for d in devices:
                        st.code(d)
                else:
                    st.warning("ADB가 실행되었지만 연결된 기기가 없습니다.")

                if result.returncode != 0 and result.stderr:
                    st.error(f"stderr: {result.stderr}")

            except FileNotFoundError:
                st.error(f"ADB를 찾을 수 없습니다: {adb_path}")
            except subprocess.TimeoutExpired:
                st.error("ADB 연결 시간 초과 (10초)")
            except Exception as e:
                st.error(f"ADB 테스트 실패: {e}")

    with test_col2:
        if st.button("IP 변경 테스트", use_container_width=True):
            try:
                # 1. 현재 IP 확인
                st.info("현재 IP 확인 중...")
                old_ip = requests.get("https://api.ipify.org", timeout=5).text
                st.write(f"변경 전 IP: `{old_ip}`")

                # 2. 비행기모드 ON
                st.info("비행기모드 ON...")
                subprocess.run(
                    [adb_path, "shell", "cmd", "connectivity", "airplane-mode", "enable"],
                    capture_output=True, text=True, timeout=10,
                )

                # 3. 대기
                import time
                with st.spinner(f"비행기모드 ON 대기 ({airplane_on_wait}초)..."):
                    time.sleep(airplane_on_wait)

                # 4. 비행기모드 OFF
                st.info("비행기모드 OFF...")
                subprocess.run(
                    [adb_path, "shell", "cmd", "connectivity", "airplane-mode", "disable"],
                    capture_output=True, text=True, timeout=10,
                )

                # 5. 대기
                with st.spinner(f"비행기모드 OFF 대기 ({airplane_off_wait}초)..."):
                    time.sleep(airplane_off_wait)

                # 6. 새 IP 확인
                new_ip = requests.get("https://api.ipify.org", timeout=10).text
                st.write(f"변경 후 IP: `{new_ip}`")

                if old_ip != new_ip:
                    st.success(f"IP 변경 성공! {old_ip} → {new_ip}")
                else:
                    st.warning("IP가 변경되지 않았습니다. 대기 시간을 늘려보세요.")

            except FileNotFoundError:
                st.error(f"ADB를 찾을 수 없습니다: {adb_path}")
            except requests.RequestException:
                st.error("IP 확인 실패 — 네트워크 연결을 확인하세요.")
            except Exception as e:
                st.error(f"IP 변경 테스트 실패: {e}")


# ══════════════════════════════════════════════
# 탭 5: 블로그 계정
# ══════════════════════════════════════════════
with tab5:
    st.subheader("블로그 계정 관리")
    st.caption("네이버 블로그 계정을 등록하고 관리합니다. **비밀번호는 secrets.yaml에 별도 저장**되어 Git에 포함되지 않습니다.")

    accounts: list[dict] = config.get("blog_accounts", [])
    acct_secrets = get_secrets()
    blog_passwords: dict = acct_secrets.get("blog_passwords", {})

    # ─── 계정 목록 (비밀번호 컬럼 없음) ───
    if accounts:
        st.markdown("**등록된 계정 목록**")

        hdr = st.columns([1.2, 2, 2, 1, 0.8])
        hdr[0].markdown("**블로그ID**")
        hdr[1].markdown("**이름**")
        hdr[2].markdown("**네이버ID**")
        hdr[3].markdown("**상태**")

        for i, acc in enumerate(accounts):
            bid = acc.get("blog_id", "")
            status_color = "#00D68F" if acc.get("status") == "활성" else "#636e72"
            with st.container():
                row_cols = st.columns([1.2, 2, 2, 1, 0.8])
                row_cols[0].markdown(f"`{bid}`")
                row_cols[1].markdown(acc.get("name", ""))
                row_cols[2].markdown(acc.get("naver_id", ""))
                row_cols[3].markdown(
                    f"<span style='color:{status_color};font-weight:600;'>{acc.get('status', '활성')}</span>",
                    unsafe_allow_html=True,
                )
                if row_cols[4].button("삭제", key=f"del_acc_{i}"):
                    blog_passwords.pop(bid, None)
                    acct_secrets["blog_passwords"] = blog_passwords
                    save_secrets(acct_secrets)
                    accounts.pop(i)
                    config["blog_accounts"] = accounts
                    save_config(config)
                    st.rerun()

        st.divider()

        # ─── 비밀번호 관리 (별도 섹션) ───
        st.markdown("**비밀번호 관리**")
        st.caption(
            "비밀번호를 등록하면 쿠키 만료 시 자동으로 재로그인됩니다. "
            "쿠키는 내부적으로 자동 관리되므로 별도로 설정할 필요 없습니다."
        )

        for acc in accounts:
            bid = acc.get("blog_id", "")
            pw_cols = st.columns([1.5, 1.5, 3])
            pw_cols[0].markdown(f"**{acc.get('name', bid)}** `{bid}`")
            pw_cols[1].caption(f"네이버ID: {acc.get('naver_id', '-')}")
            pw_cols[2].text_input(
                "비밀번호",
                value=blog_passwords.get(bid, ""),
                type="password",
                key=f"pw_{bid}",
                label_visibility="collapsed",
                placeholder="네이버 비밀번호",
            )

        st.markdown("")
        if st.button("비밀번호 저장", key="save_passwords", type="primary", use_container_width=True):
            for acc in accounts:
                bid = acc.get("blog_id", "")
                pw = st.session_state.get(f"pw_{bid}", "")
                if pw:
                    blog_passwords[bid] = pw
                else:
                    blog_passwords.pop(bid, None)
            acct_secrets["blog_passwords"] = blog_passwords
            save_secrets(acct_secrets)
            st.success("비밀번호가 secrets.yaml에 저장되었습니다. (Git에 포함되지 않습니다)")

        st.divider()
    else:
        st.info("등록된 블로그 계정이 없습니다. 아래에서 추가하세요.")

    # 새 계정 추가 폼
    with st.expander("새 계정 추가", expanded=len(accounts) == 0):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            new_blog_id = st.text_input(
                "블로그 ID (내부 식별자)",
                placeholder="blog_01",
                key="new_blog_id",
                help="시스템 내부에서 사용하는 고유 식별자 (영문/숫자/언더스코어)",
            )
            new_name = st.text_input(
                "블로그 이름",
                placeholder="맛집탐방일기",
                key="new_name",
            )
            new_naver_id = st.text_input(
                "네이버 ID",
                placeholder="naver_login_id",
                key="new_naver_id",
            )
        with f_col2:
            new_naver_pw = st.text_input(
                "네이버 비밀번호",
                placeholder="비밀번호",
                type="password",
                key="new_naver_pw",
                help="secrets.yaml에 저장됩니다. Git에 포함되지 않습니다.",
            )
            new_blog_url = st.text_input(
                "블로그 URL",
                placeholder="https://blog.naver.com/your_id",
                key="new_blog_url",
            )
            new_status = st.selectbox(
                "상태",
                options=["활성", "휴식"],
                key="new_status",
            )

        if st.button("계정 추가", key="btn_add_account", type="primary", use_container_width=True):
            if not new_blog_id:
                st.error("블로그 ID는 필수입니다.")
            elif any(a.get("blog_id") == new_blog_id for a in accounts):
                st.error(f"블로그 ID '{new_blog_id}'가 이미 존재합니다.")
            else:
                # 계정 기본 정보는 config.yaml에 저장
                new_acc = {
                    "blog_id": new_blog_id,
                    "name": new_name,
                    "naver_id": new_naver_id,
                    "blog_url": new_blog_url,
                    "status": new_status,
                    "posts_today": 0,
                }
                accounts.append(new_acc)
                config["blog_accounts"] = accounts
                save_config(config)

                # 비밀번호는 secrets.yaml에 저장
                if new_naver_pw:
                    fresh_secrets = get_secrets()
                    fresh_secrets.setdefault("blog_passwords", {})
                    fresh_secrets["blog_passwords"][new_blog_id] = new_naver_pw
                    save_secrets(fresh_secrets)

                st.success(f"'{new_name}' 계정이 추가되었습니다.")
                st.rerun()


# ══════════════════════════════════════════════
# 탭 6: 상품 리스트
# ══════════════════════════════════════════════
with tab6:
    st.subheader("상품 리스트 관리")
    st.caption("상품홍보 글 작성 시 선택할 수 있는 상품 목록을 관리합니다. (최대 15개)")

    products: list[dict] = config.get("products", [])

    if products:
        st.markdown("**등록된 상품 목록**")
        for i, product in enumerate(products):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.text_input(
                    f"상품 {i + 1}",
                    value=product.get("name", ""),
                    key=f"product_{i}",
                    label_visibility="collapsed",
                )
            with col2:
                if st.button("삭제", key=f"del_product_{i}"):
                    products.pop(i)
                    config["products"] = products
                    save_config(config)
                    st.rerun()

        st.markdown("")
        if st.button("변경사항 저장", key="save_products", type="primary", use_container_width=True):
            updated = []
            for i in range(len(products)):
                name = st.session_state.get(f"product_{i}", "").strip()
                if name:
                    updated.append({"name": name})
            config["products"] = updated
            save_config(config)
            st.success("상품 리스트가 저장되었습니다.")
            st.rerun()

        st.divider()
    else:
        st.info("등록된 상품이 없습니다. 아래에서 추가하세요.")

    new_product = st.text_input(
        "새 상품명",
        placeholder="예: 삼성 비스포크 냉장고 RF85C90D2AP",
        key="new_product_name",
    )

    add_disabled = len(products) >= MAX_PRODUCTS
    if add_disabled:
        st.caption(f"최대 {MAX_PRODUCTS}개까지 등록할 수 있습니다.")

    if st.button("상품 추가", key="btn_add_product", disabled=add_disabled, use_container_width=True):
        if new_product.strip():
            products.append({"name": new_product.strip()})
            config["products"] = products
            save_config(config)
            st.success(f"'{new_product.strip()}' 상품이 추가되었습니다.")
            st.rerun()
        else:
            st.warning("상품명을 입력하세요.")


# ══════════════════════════════════════════════
# 탭 7: 단가 · 환율
# ══════════════════════════════════════════════
with tab7:
    st.subheader("단가 · 환율 관리")
    st.caption(
        "AI 글·이미지 비용 추정에 쓰이는 단가와 환율을 편집합니다. "
        "비용은 USD 기준으로 저장되어, 환율만 바꿔도 과거 기록까지 즉시 재환산됩니다."
    )

    pricing_cfg = config.get("pricing", {}) or {}
    fx_cfg = pricing_cfg.get("exchange_rate", {}) or {}

    # ─── 환율 ───
    st.markdown("**환율 (KRW per USD)**")
    fx_col1, fx_col2 = st.columns([2, 1])
    with fx_col1:
        if "_fx_fetched" in st.session_state:
            default_rate = float(st.session_state["_fx_fetched"])
        else:
            default_rate = float(fx_cfg.get("krw_per_usd", pricing.DEFAULT_KRW_PER_USD))
        krw_per_usd = st.number_input(
            "1 USD = ? KRW",
            min_value=0.0,
            value=default_rate,
            step=10.0,
            format="%.2f",
        )
    with fx_col2:
        st.caption(f"출처: {st.session_state.get('_fx_source', fx_cfg.get('source', 'manual'))}")
        st.caption(f"갱신: {fx_cfg.get('last_updated', '-')}")
        if st.button("🔄 환율 자동 갱신", key="btn_fetch_fx", use_container_width=True):
            live = pricing.fetch_live_exchange_rate()
            if live:
                st.session_state["_fx_fetched"] = live
                st.session_state["_fx_source"] = "auto"
                st.success(f"실시간 환율 ₩{live:,.2f}/USD — 저장 버튼으로 확정하세요.")
                st.rerun()
            else:
                st.error("환율 조회 실패 — 기존 값을 유지합니다.")

    # ─── 텍스트 모델 단가 ───
    st.divider()
    st.markdown("**텍스트 모델 단가 (USD / 1M tokens)**")
    st.caption("입력값은 config에 override로 저장됩니다. 여기 없는 모델은 코드 기본 단가가 적용됩니다.")
    text_price_inputs: dict = {}
    for eng_key, eng_cfg in ENGINE_CONFIGS.items():
        with st.expander(eng_cfg["label"]):
            for m in eng_cfg["models"]:
                cur = pricing.get_text_price(config, eng_key, m["id"])
                tc1, tc2 = st.columns(2)
                inp = tc1.number_input(
                    f"{m['name']} · 입력", min_value=0.0, value=float(cur["input"]),
                    step=0.05, format="%.4f", key=f"tp_in_{eng_key}_{m['id']}",
                )
                out = tc2.number_input(
                    f"{m['name']} · 출력", min_value=0.0, value=float(cur["output"]),
                    step=0.05, format="%.4f", key=f"tp_out_{eng_key}_{m['id']}",
                )
                text_price_inputs[f"{eng_key}/{m['id']}"] = (inp, out)

    # ─── 이미지 단가 ───
    st.divider()
    st.markdown("**이미지 단가 (USD / 장)**")
    image_price_inputs: dict = {}

    with st.expander("GPT Image (사이즈 · 품질별)", expanded=True):
        gpt_tbl: dict = {}
        for size in ("1024x1024", "1536x1024", "1024x1536"):
            st.caption(size)
            q_cols = st.columns(3)
            for qi, q in enumerate(("low", "medium", "high")):
                cur = pricing.calc_image_cost_usd(config, "gpt_image", size, q)
                val = q_cols[qi].number_input(
                    q, min_value=0.0, value=float(cur), step=0.001,
                    format="%.4f", key=f"img_gpt_{size}_{q}",
                )
                gpt_tbl.setdefault(size, {})[q] = val
        image_price_inputs["gpt_image"] = gpt_tbl

    with st.expander("기타 이미지 엔진 (장당 단가)"):
        for eng in ("gemini_image", "flux_schnell", "flux_pro", "ideogram", "gemini_flash_image", "pollinations"):
            cur = pricing.calc_image_cost_usd(config, eng)
            label = IMAGE_ENGINE_CONFIGS.get(eng, {}).get("label", eng)
            val = st.number_input(
                label, min_value=0.0, value=float(cur), step=0.005,
                format="%.4f", key=f"img_flat_{eng}",
            )
            image_price_inputs[eng] = {"_flat": val}

    # ─── 예측 설정 ───
    st.divider()
    st.markdown("**예측 설정**")
    pj1, pj2 = st.columns(2)
    lookback = pj1.number_input(
        "예측 일평균 산출 구간(일)", min_value=1, max_value=90,
        value=pricing.get_lookback_days(config), key="proj_lookback_setting",
    )
    assumed = pj2.number_input(
        "건당 비용 가정(₩, 실측 없을 때)", min_value=0.0,
        value=float(pricing.get_assumed_cost_per_post_krw(config)),
        step=50.0, key="proj_assumed_setting",
    )

    # ─── 저장 ───
    st.markdown("")
    if st.button("단가 · 환율 저장", type="primary", use_container_width=True, key="save_pricing"):
        new_pricing = config.get("pricing", {}) or {}
        new_pricing["exchange_rate"] = {
            "krw_per_usd": krw_per_usd,
            "source": st.session_state.get("_fx_source", fx_cfg.get("source", "manual")),
            "last_updated": datetime.date.today().isoformat(),
        }
        new_pricing["text_models"] = {
            k: {"input": v[0], "output": v[1]} for k, v in text_price_inputs.items()
        }
        new_pricing["image_models"] = image_price_inputs
        new_pricing["projection"] = {
            "lookback_days": int(lookback),
            "assumed_cost_per_post_krw": assumed,
        }
        config["pricing"] = new_pricing
        save_config(config)
        st.session_state.pop("_fx_fetched", None)
        st.session_state.pop("_fx_source", None)
        st.success("단가·환율이 저장되었습니다.")
