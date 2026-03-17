"""
포스팅 자동발행 시스템 v3.0
Streamlit 멀티페이지 메인 엔트리포인트
"""

import yaml
import streamlit as st
import requests
import subprocess
from pathlib import Path

# ──────────────────────────────────────────────
# config.yaml 로드 (캐시)
# ──────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent / "config.yaml"


@st.cache_data
def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        st.error("config.yaml 파일을 찾을 수 없습니다.")
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_config() -> dict:
    """session_state에 config를 캐시하여 페이지 간 공유"""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    return st.session_state["config"]


def save_config(config: dict):
    """config.yaml 저장 후 session_state 및 캐시 갱신."""
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    st.session_state["config"] = config
    st.cache_data.clear()


# ──────────────────────────────────────────────
# secrets.yaml 로드 (API 키 + 블로그 비밀번호)
# ──────────────────────────────────────────────
_SECRETS_PATH = Path(__file__).parent / "secrets.yaml"

_SECRETS_EMPTY: dict = {"api_keys": {}, "blog_passwords": {}}


def load_secrets() -> dict:
    """secrets.yaml 로드. 파일이 없으면 빈 구조 반환."""
    if not _SECRETS_PATH.exists():
        return _SECRETS_EMPTY.copy()
    with open(_SECRETS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("api_keys", {})
    data.setdefault("blog_passwords", {})
    return data


def save_secrets(secrets: dict):
    """secrets.yaml 저장 후 session_state 갱신."""
    with open(_SECRETS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(secrets, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    st.session_state["secrets"] = secrets


def get_secrets() -> dict:
    """session_state에 secrets를 캐시하여 페이지 간 공유."""
    if "secrets" not in st.session_state:
        st.session_state["secrets"] = load_secrets()
    return st.session_state["secrets"]


# ──────────────────────────────────────────────
# 네트워크 상태 확인
# ──────────────────────────────────────────────
def get_current_ip() -> str:
    """현재 공인 IP 조회"""
    try:
        return requests.get("https://api.ipify.org", timeout=5).text
    except Exception:
        return "확인 불가"


def get_tethering_status(config: dict) -> dict:
    """ADB로 테더링(비행기모드) 상태 확인"""
    adb_path = config.get("adb", {}).get("path", "adb")
    try:
        result = subprocess.run(
            [adb_path, "devices"],
            capture_output=True, text=True, timeout=5,
        )
        devices = [
            line for line in result.stdout.strip().split("\n")[1:]
            if line.strip() and "device" in line
        ]
        connected = len(devices) > 0

        if connected:
            airplane = subprocess.run(
                [adb_path, "shell", "settings", "get", "global", "airplane_mode_on"],
                capture_output=True, text=True, timeout=5,
            )
            airplane_on = airplane.stdout.strip() == "1"
        else:
            airplane_on = False

        return {
            "device_connected": connected,
            "device_count": len(devices),
            "airplane_mode": airplane_on,
        }
    except Exception:
        return {
            "device_connected": False,
            "device_count": 0,
            "airplane_mode": False,
        }


# ──────────────────────────────────────────────
# 블로그 계정 목록 (구글 시트 또는 로컬)
# ──────────────────────────────────────────────
def get_blog_accounts() -> list[dict]:
    """블로그 계정 목록 반환 (config.yaml의 blog_accounts)"""
    config = get_config()
    return config.get("blog_accounts", [])


# ──────────────────────────────────────────────
# 커스텀 CSS
# ──────────────────────────────────────────────
def inject_custom_css():
    st.markdown("""
    <style>
    /* 사이드바 스타일 */
    [data-testid="stSidebar"] {
        background-color: #12141D;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    /* 상단 헤더 바 */
    .status-bar {
        display: flex;
        align-items: center;
        gap: 1.5rem;
        padding: 0.6rem 1rem;
        background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
        border-radius: 10px;
        border: 1px solid #2D3250;
        margin-bottom: 1.5rem;
    }
    .status-item {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.85rem;
        color: #A0A4B8;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }
    .status-dot.green { background-color: #00D68F; }
    .status-dot.red { background-color: #FF6B6B; }
    .status-dot.yellow { background-color: #FFD93D; }
    .status-dot.gray { background-color: #636e72; }
    .status-value {
        color: #FAFAFA;
        font-weight: 600;
    }

    /* 메트릭 카드 */
    .metric-card {
        background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
        border: 1px solid #2D3250;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-card .label {
        font-size: 0.8rem;
        color: #A0A4B8;
        margin-bottom: 0.3rem;
    }
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: #FAFAFA;
    }
    .metric-card .sub {
        font-size: 0.75rem;
        color: #636e72;
        margin-top: 0.2rem;
    }

    /* 사이드바 블로그 카드 */
    .blog-card {
        background: #1A1D29;
        border: 1px solid #2D3250;
        border-radius: 8px;
        padding: 0.7rem 0.8rem;
        margin-bottom: 0.5rem;
    }
    .blog-card .blog-name {
        font-size: 0.85rem;
        font-weight: 600;
        color: #FAFAFA;
    }
    .blog-card .blog-meta {
        font-size: 0.72rem;
        color: #A0A4B8;
        margin-top: 0.2rem;
    }

    /* 테이블 스타일 개선 */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.2rem;
    }

    /* 프로그레스 바 커스텀 */
    .progress-container {
        background: #2D3250;
        border-radius: 6px;
        height: 8px;
        overflow: hidden;
        margin: 0.3rem 0;
    }
    .progress-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 0.5s ease;
    }
    </style>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 상단 상태 바 렌더링
# ──────────────────────────────────────────────
def render_status_bar(config: dict):
    """테더링 상태 + 현재 IP + 시스템 상태 표시"""
    ip = get_current_ip()
    tether = get_tethering_status(config)

    device_dot = "green" if tether["device_connected"] else "gray"
    device_text = f"{tether['device_count']}대 연결" if tether["device_connected"] else "미연결"

    airplane_dot = "yellow" if tether["airplane_mode"] else "green"
    airplane_text = "ON" if tether["airplane_mode"] else "OFF"

    ip_dot = "green" if ip != "확인 불가" else "red"

    # API 키 상태 (secrets.yaml 기준)
    secrets = get_secrets()
    api_keys = secrets.get("api_keys", {})
    configured_keys = sum(1 for v in api_keys.values() if v)
    key_dot = "green" if configured_keys > 0 else "red"

    st.markdown(f"""
    <div class="status-bar">
        <div class="status-item">
            <span class="status-dot {device_dot}"></span>
            ADB: <span class="status-value">{device_text}</span>
        </div>
        <div class="status-item">
            <span class="status-dot {airplane_dot}"></span>
            비행기모드: <span class="status-value">{airplane_text}</span>
        </div>
        <div class="status-item">
            <span class="status-dot {ip_dot}"></span>
            IP: <span class="status-value">{ip}</span>
        </div>
        <div class="status-item">
            <span class="status-dot {key_dot}"></span>
            API 키: <span class="status-value">{configured_keys}개 설정됨</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 사이드바 렌더링
# ──────────────────────────────────────────────
def render_sidebar(config: dict):
    with st.sidebar:
        st.markdown("## 🚀 AutoPost")
        st.caption("v3.0 — 다중 AI 엔진")
        st.divider()

        # 블로그 계정 목록
        st.markdown("#### 📝 블로그 계정")
        accounts = get_blog_accounts()

        for acc in accounts:
            status_color = "#00D68F" if acc["status"] == "활성" else "#636e72"
            st.markdown(f"""
            <div class="blog-card">
                <div class="blog-name">
                    <span style="color:{status_color}; margin-right:4px;">●</span>
                    {acc['name']}
                </div>
                <div class="blog-meta">
                    {acc.get('blog_id', acc.get('id', ''))} · 오늘 {acc.get('posts_today', 0)}건 발행
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 빠른 액션
        st.markdown("#### ⚡ 빠른 액션")
        if st.button("🔄 IP 변경", use_container_width=True):
            with st.spinner("IP 변경 중..."):
                st.info("IP 변경 기능은 발행 모듈에서 실행됩니다.")

        if st.button("📋 시트 동기화", use_container_width=True):
            with st.spinner("구글 시트 동기화 중..."):
                st.info("구글 시트 연동 후 사용 가능합니다.")

        st.divider()

        # 기본 설정 요약
        st.markdown("#### ⚙️ 현재 설정")
        defaults = config.get("defaults", {})
        engine_labels = {"openai": "OpenAI", "claude": "Claude", "gemini": "Gemini"}
        img_labels = {
            "gpt_image": "GPT Image",
            "gemini_image": "Gemini",
            "flux_schnell": "Flux",
            "pollinations": "Pollinations",
        }
        st.caption(f"글 엔진: **{engine_labels.get(defaults.get('text_engine', ''), defaults.get('text_engine', '-'))}**")
        st.caption(f"모델: **{defaults.get('text_model', '-')}**")
        st.caption(f"이미지: **{img_labels.get(defaults.get('image_engine', ''), defaults.get('image_engine', '-'))}**")


# ──────────────────────────────────────────────
# 메인 페이지 (app.py 직접 접속 시)
# ──────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="AutoPost",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    config = get_config()

    inject_custom_css()
    render_sidebar(config)
    render_status_bar(config)

    # 메인 페이지 내용 (홈 화면)
    st.markdown("# 🚀 AutoPost v3.0")
    st.markdown("**포스팅 자동발행 시스템** — 다중 AI 엔진 · 이미지 검토 · 키워드 일괄 처리")

    st.divider()

    # 퀵 네비게이션
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="label">📊 대시보드</div>
            <div class="value" style="font-size:1.5rem;">현황 확인</div>
            <div class="sub">오늘의 발행 현황</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="label">✍️ 글 생성</div>
            <div class="value" style="font-size:1.5rem;">AI 작성</div>
            <div class="sub">다중 엔진 선택</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="label">👁️ 검토/수정</div>
            <div class="value" style="font-size:1.5rem;">미리보기</div>
            <div class="sub">이미지 첨부</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="label">🚀 발행</div>
            <div class="value" style="font-size:1.5rem;">자동 발행</div>
            <div class="sub">대기열 관리</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # 시스템 상태 요약
    st.markdown("### 시스템 상태")
    c1, c2, c3 = st.columns(3)

    with c1:
        api_keys = get_secrets().get("api_keys", {})
        for name, key in api_keys.items():
            icon = "✅" if key else "❌"
            st.markdown(f"{icon} **{name.upper()}** API 키 {'설정됨' if key else '미설정'}")

    with c2:
        st.markdown("📂 **데이터 디렉토리**")
        paths = config.get("paths", {})
        for label, path in paths.items():
            p = Path(path)
            exists = "✅" if p.exists() else "⚠️"
            st.caption(f"{exists} {label}: `{path}`")

    with c3:
        st.markdown("🔧 **발행 설정**")
        publish = config.get("publish", {})
        st.caption(f"블로그 간 대기: {publish.get('inter_blog_delay', '-')}초")
        st.caption(f"연속 발행 대기: {publish.get('inter_post_delay', '-')}초")
        st.caption(f"최대 재시도: {publish.get('max_retries', '-')}회")
        st.caption(f"브라우저: {publish.get('browser_engine', '-')}")


if __name__ == "__main__":
    main()
