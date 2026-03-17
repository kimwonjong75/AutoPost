"""
🚀 발행 — 발행 대기열 관리, 선택 발행, 실시간 진행 표시, 발행 기록
"""

import datetime
import json
import random
import sys
import time
from pathlib import Path

import streamlit as st

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.models import (
    GeneratedArticle,
    GeneratedImage,
    PublishLog,
    init_db,
)

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="발행 — AutoPost",
    page_icon="🚀",
    layout="wide",
)

init_db()

from app import get_config, get_secrets, inject_custom_css, render_sidebar, render_status_bar

config = get_config()
inject_custom_css()
render_sidebar(config)
render_status_bar(config)


# ──────────────────────────────────────────────
# 발행 페이지 전용 CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
.publish-step {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.8rem;
    margin: 0.3rem 0;
    border-radius: 8px;
    font-size: 0.9rem;
}
.step-pending {
    background: #1A1D29;
    color: #666;
    border: 1px solid #2D3250;
}
.step-active {
    background: linear-gradient(135deg, #1a2332 0%, #1a2845 100%);
    color: #00D2FF;
    border: 1px solid #00D2FF;
    animation: pulse-border 1.5s infinite;
}
.step-done {
    background: #1a2e1a;
    color: #00E676;
    border: 1px solid #2d5a2d;
}
.step-fail {
    background: #2e1a1a;
    color: #FF5252;
    border: 1px solid #5a2d2d;
}
@keyframes pulse-border {
    0%, 100% { border-color: #00D2FF; }
    50% { border-color: #0066aa; }
}

.delay-banner {
    background: linear-gradient(135deg, #2a2200 0%, #332d00 100%);
    border: 1px solid #665500;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    text-align: center;
    color: #FFD600;
    font-size: 1.1rem;
    margin: 1rem 0;
}

.publish-summary {
    background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
    border: 1px solid #2D3250;
    border-radius: 14px;
    padding: 1.5rem;
    margin: 0.5rem 0;
    text-align: center;
}

.log-success { color: #00E676; }
.log-fail { color: #FF5252; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Mock 발행 시뮬레이터
# ──────────────────────────────────────────────

PUBLISH_STEPS = [
    ("airplane_on", "비행기모드 켜기"),
    ("ip_wait", "IP 대기"),
    ("airplane_off", "비행기모드 끄기"),
    ("ip_check", "IP 확인"),
    ("login", "로그인"),
    ("write", "글 작성"),
    ("publish", "발행"),
    ("done", "완료"),
]


def mock_change_ip() -> dict:
    """IP 변경 시뮬레이션"""
    octets = [random.randint(1, 254) for _ in range(4)]
    return {
        "success": True,
        "old_ip": f"121.{random.randint(100,199)}.{random.randint(1,254)}.{random.randint(1,254)}",
        "new_ip": f"121.{octets[1]}.{octets[2]}.{octets[3]}",
        "changed": True,
        "android_sdk": 34,
    }


def mock_publish_single(article, blog_id: str) -> dict:
    """단일 글 발행 시뮬레이션"""
    # 90% 확률로 성공
    if random.random() < 0.9:
        return {
            "status": "성공",
            "post_url": f"https://blog.naver.com/{blog_id}/{random.randint(100000000, 999999999)}",
            "error_message": "",
            "screenshot_path": "",
            "retry_count": 0,
        }
    else:
        failures = ["로그인실패", "에디터실패", "발행실패", "네트워크실패"]
        status = random.choice(failures)
        return {
            "status": status,
            "post_url": "",
            "error_message": f"{status}: 시뮬레이션 오류",
            "screenshot_path": "",
            "retry_count": 0,
        }


def render_step_indicator(current_step_idx: int, failed: bool = False):
    """발행 단계 인디케이터 렌더링"""
    html_parts = []
    for i, (step_id, step_label) in enumerate(PUBLISH_STEPS):
        if failed and i == current_step_idx:
            css_class = "step-fail"
            icon = "❌"
        elif i < current_step_idx:
            css_class = "step-done"
            icon = "✅"
        elif i == current_step_idx:
            css_class = "step-active"
            icon = "⏳"
        else:
            css_class = "step-pending"
            icon = "⬜"
        html_parts.append(
            f'<div class="publish-step {css_class}">'
            f'{icon} <b>Step {i + 1}</b> {step_label}'
            f'</div>'
        )
    return "".join(html_parts)


def get_blog_accounts_for_publish() -> list[dict]:
    """발행에 사용할 블로그 계정 목록 (config.yaml + secrets.yaml 병합)"""
    cfg = get_config()
    secrets = get_secrets()
    passwords = secrets.get("blog_passwords", {})

    result = []
    for acc in cfg.get("blog_accounts", []):
        if acc.get("status") == "활성":
            bid = acc.get("blog_id", "")
            merged = dict(acc)
            merged["naver_pw"] = passwords.get(bid, "")
            result.append(merged)
    return result


# ──────────────────────────────────────────────
# 메인 페이지
# ──────────────────────────────────────────────

st.title("🚀 발행")
st.caption("검토 완료된 글을 네이버 블로그에 발행합니다.")

# ──────────────────────────────────────────────
# 탭 구성
# ──────────────────────────────────────────────

tab_queue, tab_log = st.tabs(["📋 발행 대기열", "📜 최근 발행 기록"])

# ══════════════════════════════════════════════
# 탭 1: 발행 대기열
# ══════════════════════════════════════════════

with tab_queue:
    # 대기열 불러오기: 검토완료 상태의 글 + 실패한 글
    queue_articles = list(
        GeneratedArticle.select()
        .where(GeneratedArticle.status.in_(["검토완료", "실패"]))
        .order_by(GeneratedArticle.created_at.desc())
    )

    if not queue_articles:
        st.info("발행 대기 중인 글이 없습니다. '글 생성' → '검토/수정'에서 글을 검토 완료해주세요.")
    else:
        st.markdown(f"**발행 대기 글: {len(queue_articles)}건**")

        # ─── 블로그 배정 설정 ───
        blog_accounts = get_blog_accounts_for_publish()
        blog_options = {acc["blog_id"]: acc["name"] for acc in blog_accounts}

        with st.expander("⚙️ 발행 설정", expanded=False):
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                default_blog = st.selectbox(
                    "기본 발행 블로그",
                    options=list(blog_options.keys()),
                    format_func=lambda x: f"{blog_options[x]} ({x})",
                    key="default_blog",
                )
            with col_s2:
                publish_delay_min = st.number_input(
                    "블로그 간 최소 대기(초)", value=config.get("publish", {}).get("inter_blog_delay", [60, 180])[0],
                    min_value=10, max_value=600, key="delay_min",
                )
            with col_s3:
                publish_delay_max = st.number_input(
                    "블로그 간 최대 대기(초)", value=config.get("publish", {}).get("inter_blog_delay", [60, 180])[1],
                    min_value=30, max_value=600, key="delay_max",
                )

        # ─── 대기열 테이블 (체크박스) ───
        st.divider()

        # session state 초기화
        if "selected_articles" not in st.session_state:
            st.session_state["selected_articles"] = set()

        # 전체 선택/해제
        col_sel_all, col_sel_reviewed, col_sel_failed, col_spacer = st.columns([1, 1, 1, 3])
        with col_sel_all:
            if st.button("전체 선택", use_container_width=True):
                st.session_state["selected_articles"] = {a.id for a in queue_articles}
                st.rerun()
        with col_sel_reviewed:
            if st.button("검토완료만", use_container_width=True):
                st.session_state["selected_articles"] = {
                    a.id for a in queue_articles if a.status == "검토완료"
                }
                st.rerun()
        with col_sel_failed:
            if st.button("실패만", use_container_width=True):
                st.session_state["selected_articles"] = {
                    a.id for a in queue_articles if a.status == "실패"
                }
                st.rerun()

        # 테이블 헤더
        header_cols = st.columns([0.4, 1.2, 0.8, 0.8, 2.5, 0.8, 0.8])
        with header_cols[0]:
            st.markdown("**선택**")
        with header_cols[1]:
            st.markdown("**블로그**")
        with header_cols[2]:
            st.markdown("**글유형**")
        with header_cols[3]:
            st.markdown("**AI모델**")
        with header_cols[4]:
            st.markdown("**제목**")
        with header_cols[5]:
            st.markdown("**상태**")
        with header_cols[6]:
            st.markdown("**액션**")

        st.divider()

        # 테이블 행
        for article in queue_articles:
            row_cols = st.columns([0.4, 1.2, 0.8, 0.8, 2.5, 0.8, 0.8])

            with row_cols[0]:
                is_checked = st.checkbox(
                    "선택", value=article.id in st.session_state["selected_articles"],
                    key=f"sel_{article.id}", label_visibility="collapsed",
                )
                if is_checked:
                    st.session_state["selected_articles"].add(article.id)
                elif article.id in st.session_state["selected_articles"]:
                    st.session_state["selected_articles"].discard(article.id)

            with row_cols[1]:
                # keyword_id에서 블로그 추정 또는 기본 블로그 표시
                st.text(st.session_state.get("default_blog", "blog_01"))

            with row_cols[2]:
                # 키워드 기반 글유형 (간단히 engine으로 대체 표시)
                content_type = "정보성"
                st.text(content_type)

            with row_cols[3]:
                model_short = article.model.split("-")[-1] if article.model else "?"
                st.text(model_short)

            with row_cols[4]:
                title_display = article.title[:40] + "..." if len(article.title) > 40 else article.title
                st.text(title_display)

            with row_cols[5]:
                if article.status == "검토완료":
                    st.markdown(":green[검토완료]")
                elif article.status == "실패":
                    st.markdown(":red[실패]")
                else:
                    st.text(article.status)

            with row_cols[6]:
                if article.status == "실패":
                    if st.button("🔄", key=f"retry_{article.id}", help="재시도"):
                        article.status = "검토완료"
                        article.save()
                        st.rerun()

        # ─── 선택 발행 버튼 ───
        st.divider()

        selected_count = len(st.session_state.get("selected_articles", set()))
        col_pub_btn, col_pub_info = st.columns([1, 2])

        with col_pub_btn:
            publish_clicked = st.button(
                f"🚀 선택 발행 ({selected_count}건)",
                type="primary",
                disabled=selected_count == 0,
                use_container_width=True,
            )

        with col_pub_info:
            if selected_count > 0:
                est_min = selected_count * publish_delay_min
                est_max = selected_count * publish_delay_max
                st.caption(
                    f"예상 소요: {est_min // 60}분 ~ {est_max // 60}분 "
                    f"(글 간 {publish_delay_min}~{publish_delay_max}초 대기)"
                )
            else:
                st.caption("발행할 글을 선택해주세요.")

        # ══════════════════════════════════════════
        # 발행 프로세스 실행
        # ══════════════════════════════════════════
        if publish_clicked and selected_count > 0:
            selected_ids = list(st.session_state["selected_articles"])
            articles_to_publish = list(
                GeneratedArticle.select()
                .where(GeneratedArticle.id.in_(selected_ids))
                .order_by(GeneratedArticle.created_at)
            )

            st.divider()
            st.subheader("발행 진행")

            total = len(articles_to_publish)
            overall_progress = st.progress(0, text=f"0 / {total} 완료")
            results_summary = {"성공": 0, "실패": 0}

            prev_blog_id = None

            for idx, article in enumerate(articles_to_publish):
                blog_id = st.session_state.get("default_blog", "blog_01")
                blog_name = blog_options.get(blog_id, blog_id)
                is_same_blog = (prev_blog_id == blog_id)

                st.markdown(f"---\n**[{idx + 1}/{total}]** {article.title[:50]}")
                step_container = st.empty()
                status_text = st.empty()

                # 블로그 전환 시 대기
                if idx > 0:
                    if is_same_blog:
                        delay_range = config.get("publish", {}).get("inter_post_delay", [30, 90])
                    else:
                        delay_range = [publish_delay_min, publish_delay_max]

                    delay = random.uniform(delay_range[0], delay_range[1])
                    delay_int = int(delay)

                    label = "같은 블로그 연속 발행" if is_same_blog else "블로그 전환"
                    st.markdown(
                        f'<div class="delay-banner">'
                        f'⏱️ {label} 대기: {delay_int}초'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    delay_bar = st.progress(0, text=f"대기 중... {delay_int}초 남음")
                    for sec in range(delay_int):
                        remaining = delay_int - sec - 1
                        delay_bar.progress(
                            (sec + 1) / delay_int,
                            text=f"대기 중... {remaining}초 남음",
                        )
                        time.sleep(1)
                    delay_bar.progress(1.0, text="대기 완료!")

                # ─── Step 1~3: IP 변경 ───
                step_container.markdown(
                    render_step_indicator(0), unsafe_allow_html=True
                )
                status_text.caption("비행기모드를 켜는 중...")
                time.sleep(1.5)

                step_container.markdown(
                    render_step_indicator(1), unsafe_allow_html=True
                )
                status_text.caption("IP 할당 대기 중... (약 8초)")
                time.sleep(2)

                step_container.markdown(
                    render_step_indicator(2), unsafe_allow_html=True
                )
                status_text.caption("비행기모드를 끄는 중...")
                time.sleep(1.5)

                # ─── Step 4: IP 확인 ───
                step_container.markdown(
                    render_step_indicator(3), unsafe_allow_html=True
                )
                ip_result = mock_change_ip()
                status_text.caption(
                    f"IP 변경: {ip_result['old_ip']} → **{ip_result['new_ip']}**"
                )
                time.sleep(1)

                # ─── Step 5: 로그인 ───
                step_container.markdown(
                    render_step_indicator(4), unsafe_allow_html=True
                )
                status_text.caption(f"[{blog_name}] 로그인 중...")
                time.sleep(1.5)

                # ─── Step 6: 글 작성 ───
                step_container.markdown(
                    render_step_indicator(5), unsafe_allow_html=True
                )
                status_text.caption("에디터에 글 작성 중...")
                time.sleep(2)

                # ─── Step 7: 발행 ───
                step_container.markdown(
                    render_step_indicator(6), unsafe_allow_html=True
                )
                status_text.caption("발행 버튼 클릭...")
                time.sleep(1.5)

                # ─── 발행 결과 (Mock) ───
                pub_result = mock_publish_single(article, blog_id)

                if pub_result["status"] == "성공":
                    step_container.markdown(
                        render_step_indicator(7), unsafe_allow_html=True
                    )
                    status_text.caption(f"✅ 발행 성공! {pub_result['post_url']}")
                    results_summary["성공"] += 1

                    article.status = "발행완료"
                    article.save()

                    # 발행 기록 저장
                    PublishLog.create(
                        blog_id=blog_id,
                        keyword_id=article.keyword_id,
                        article=article,
                        title=article.title,
                        post_url=pub_result["post_url"],
                        ip_address=ip_result["new_ip"],
                        status="성공",
                        error_message="",
                        screenshot_path="",
                        retry_count=pub_result["retry_count"],
                        delay_seconds=int(delay) if idx > 0 else 0,
                    )
                else:
                    step_container.markdown(
                        render_step_indicator(6, failed=True), unsafe_allow_html=True
                    )
                    status_text.caption(f"❌ 발행 실패: {pub_result['error_message']}")
                    results_summary["실패"] += 1

                    article.status = "실패"
                    article.save()

                    PublishLog.create(
                        blog_id=blog_id,
                        keyword_id=article.keyword_id,
                        article=article,
                        title=article.title,
                        post_url="",
                        ip_address=ip_result.get("new_ip", ""),
                        status="실패",
                        error_message=pub_result["error_message"],
                        screenshot_path=pub_result.get("screenshot_path", ""),
                        retry_count=pub_result["retry_count"],
                        delay_seconds=int(delay) if idx > 0 else 0,
                    )

                prev_blog_id = blog_id
                overall_progress.progress(
                    (idx + 1) / total,
                    text=f"{idx + 1} / {total} 완료",
                )

            # ─── 발행 완료 요약 ───
            st.divider()
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.markdown(
                    f'<div class="publish-summary">'
                    f'<div style="font-size:2rem;">📊</div>'
                    f'<div style="font-size:1.5rem;font-weight:bold;">{total}건</div>'
                    f'<div style="color:#888;">전체</div></div>',
                    unsafe_allow_html=True,
                )
            with col_r2:
                st.markdown(
                    f'<div class="publish-summary">'
                    f'<div style="font-size:2rem;">✅</div>'
                    f'<div style="font-size:1.5rem;font-weight:bold;color:#00E676;">'
                    f'{results_summary["성공"]}건</div>'
                    f'<div style="color:#888;">성공</div></div>',
                    unsafe_allow_html=True,
                )
            with col_r3:
                st.markdown(
                    f'<div class="publish-summary">'
                    f'<div style="font-size:2rem;">❌</div>'
                    f'<div style="font-size:1.5rem;font-weight:bold;color:#FF5252;">'
                    f'{results_summary["실패"]}건</div>'
                    f'<div style="color:#888;">실패</div></div>',
                    unsafe_allow_html=True,
                )

            if results_summary["실패"] > 0:
                st.warning(
                    f"실패한 글 {results_summary['실패']}건은 '실패' 상태로 대기열에 남아있습니다. "
                    f"'🔄 재시도' 버튼으로 다시 발행할 수 있습니다."
                )

            # 선택 초기화
            st.session_state["selected_articles"] = set()
            st.success("발행 프로세스가 완료되었습니다!")


# ══════════════════════════════════════════════
# 탭 2: 최근 발행 기록
# ══════════════════════════════════════════════

with tab_log:
    st.subheader("최근 발행 기록")

    # 필터
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        log_status_filter = st.selectbox(
            "상태 필터", ["전체", "성공", "실패"], key="log_status_filter"
        )
    with col_f2:
        log_limit = st.selectbox(
            "표시 건수", [20, 50, 100], key="log_limit"
        )

    # 발행 로그 쿼리
    query = PublishLog.select().order_by(PublishLog.published_at.desc())
    if log_status_filter != "전체":
        query = query.where(PublishLog.status == log_status_filter)
    logs = list(query.limit(log_limit))

    if not logs:
        st.info("발행 기록이 없습니다.")
    else:
        # 요약 통계
        total_logs = PublishLog.select().count()
        success_logs = PublishLog.select().where(PublishLog.status == "성공").count()
        fail_logs = PublishLog.select().where(PublishLog.status == "실패").count()
        success_rate = (success_logs / total_logs * 100) if total_logs > 0 else 0

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("전체 발행", f"{total_logs}건")
        col_m2.metric("성공", f"{success_logs}건")
        col_m3.metric("실패", f"{fail_logs}건")
        col_m4.metric("성공률", f"{success_rate:.1f}%")

        st.divider()

        # 테이블 헤더
        header_cols = st.columns([1.2, 0.8, 2, 1.2, 0.8, 0.6])
        with header_cols[0]:
            st.markdown("**시간**")
        with header_cols[1]:
            st.markdown("**블로그**")
        with header_cols[2]:
            st.markdown("**제목**")
        with header_cols[3]:
            st.markdown("**IP**")
        with header_cols[4]:
            st.markdown("**대기(초)**")
        with header_cols[5]:
            st.markdown("**결과**")

        st.divider()

        # 테이블 행
        for log in logs:
            row_cols = st.columns([1.2, 0.8, 2, 1.2, 0.8, 0.6])

            with row_cols[0]:
                if isinstance(log.published_at, str):
                    time_str = log.published_at[:16]
                else:
                    time_str = log.published_at.strftime("%m/%d %H:%M")
                st.text(time_str)

            with row_cols[1]:
                st.text(log.blog_id)

            with row_cols[2]:
                title = log.title[:35] + "..." if len(log.title) > 35 else log.title
                if log.status == "성공" and log.post_url:
                    st.markdown(f"[{title}]({log.post_url})")
                else:
                    st.text(title)

            with row_cols[3]:
                st.text(log.ip_address or "-")

            with row_cols[4]:
                st.text(f"{log.delay_seconds}s" if log.delay_seconds else "-")

            with row_cols[5]:
                if log.status == "성공":
                    st.markdown(":green[성공]")
                else:
                    st.markdown(":red[실패]")

        # 실패 건 상세
        if log_status_filter == "실패" or log_status_filter == "전체":
            failed_logs = [l for l in logs if l.status == "실패"]
            if failed_logs:
                with st.expander(f"실패 상세 ({len(failed_logs)}건)", expanded=False):
                    for fl in failed_logs:
                        pub_time = fl.published_at
                        if isinstance(pub_time, str):
                            pub_time_str = pub_time[:16]
                        else:
                            pub_time_str = pub_time.strftime("%m/%d %H:%M")
                        st.markdown(
                            f"- **{pub_time_str}** | {fl.blog_id} | "
                            f"{fl.title[:30]} | 오류: `{fl.error_message or '알 수 없음'}`"
                        )
