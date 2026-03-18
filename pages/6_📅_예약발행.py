"""
📅 예약 발행 — 스케줄 등록/관리, 실행 상태, 실행 기록
"""

import sys
import uuid
from pathlib import Path

import streamlit as st

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.models import GeneratedArticle, init_db
from modules.scheduler import ScheduleEntry, get_scheduler, MAX_SCHEDULES

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="예약 발행 — AutoPost",
    page_icon="📅",
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
.schedule-card {
    background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
    border: 1px solid #2D3250;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem;
}
.schedule-card.active {
    border-color: #00D68F;
}
.schedule-card.inactive {
    border-color: #5a5a5a;
    opacity: 0.6;
}
.sched-name {
    font-size: 1rem;
    font-weight: 700;
    color: #FAFAFA;
}
.sched-detail {
    font-size: 0.8rem;
    color: #A0A4B8;
    margin-top: 0.3rem;
}
.sched-next {
    font-size: 0.78rem;
    color: #74B9FF;
    margin-top: 0.2rem;
}
.scheduler-status {
    display: inline-block;
    padding: 0.2rem 0.8rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}
.scheduler-status.running {
    background: rgba(0,214,143,0.15);
    color: #00D68F;
}
.scheduler-status.stopped {
    background: rgba(255,107,107,0.15);
    color: #FF6B6B;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 스케줄러 초기화
# ──────────────────────────────────────────────
scheduler = get_scheduler(config)


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────
def get_blog_options() -> dict[str, str]:
    """활성 블로그 계정 목록."""
    result = {}
    for acc in config.get("blog_accounts", []):
        if acc.get("status") == "활성":
            bid = acc.get("blog_id", "")
            name = acc.get("name", bid)
            result[bid] = f"{name} ({bid})" if name else bid
    return result


DAYS_OF_WEEK_OPTIONS = {
    "mon-sun": "매일",
    "mon-fri": "평일 (월~금)",
    "mon,wed,fri": "월/수/금",
    "tue,thu": "화/목",
    "sat,sun": "주말 (토~일)",
}


# ──────────────────────────────────────────────
# 메인 페이지
# ──────────────────────────────────────────────
st.title("📅 예약 발행")
st.caption("자동으로 검토 완료된 글을 예약 시간에 발행합니다.")

# ── 스케줄러 상태 / 제어 ──
status_col, ctrl_col = st.columns([3, 1])

with status_col:
    if scheduler.is_running():
        st.markdown(
            '<span class="scheduler-status running">스케줄러 실행 중</span>',
            unsafe_allow_html=True,
        )
        active_count = sum(1 for s in scheduler.get_schedules() if s.enabled)
        st.caption(f"활성 스케줄: {active_count}건")
    else:
        st.markdown(
            '<span class="scheduler-status stopped">스케줄러 중지됨</span>',
            unsafe_allow_html=True,
        )

with ctrl_col:
    if scheduler.is_running():
        if st.button("스케줄러 중지", type="secondary", use_container_width=True):
            scheduler.stop()
            st.rerun()
    else:
        if st.button("스케줄러 시작", type="primary", use_container_width=True):
            scheduler.start()
            st.rerun()

# 발행 대기 글 수 표시
pending_count = GeneratedArticle.select().where(
    GeneratedArticle.status == "검토완료"
).count()
st.info(f"현재 발행 대기 글: **{pending_count}건** (검토완료 상태)")

st.divider()

# ──────────────────────────────────────────────
# 탭 구성
# ──────────────────────────────────────────────
tab_schedules, tab_add, tab_logs = st.tabs([
    "📋 스케줄 목록",
    "➕ 스케줄 추가",
    "📜 실행 기록",
])


# ══════════════════════════════════════════════
# 탭 1: 스케줄 목록
# ══════════════════════════════════════════════
with tab_schedules:
    schedules = scheduler.get_schedules()

    if not schedules:
        st.info("등록된 스케줄이 없습니다. '스케줄 추가' 탭에서 새 스케줄을 등록하세요.")
    else:
        for entry in schedules:
            css_class = "active" if entry.enabled else "inactive"
            next_run = scheduler.get_next_run(entry.schedule_id) or "스케줄러 중지 상태"
            days_label = DAYS_OF_WEEK_OPTIONS.get(entry.days_of_week, entry.days_of_week)
            blog_name = get_blog_options().get(entry.blog_id, entry.blog_id)

            card_col, action_col = st.columns([4, 1])

            with card_col:
                st.markdown(f"""
                <div class="schedule-card {css_class}">
                    <div class="sched-name">{'🟢' if entry.enabled else '⚪'} {entry.name}</div>
                    <div class="sched-detail">
                        {days_label} {entry.cron_hour:02d}:{entry.cron_minute:02d}
                        | 블로그: {blog_name}
                        | 최대 {entry.max_articles}건
                    </div>
                    <div class="sched-next">다음 실행: {next_run}</div>
                </div>
                """, unsafe_allow_html=True)

            with action_col:
                st.markdown("<br>", unsafe_allow_html=True)

                if entry.enabled:
                    if st.button("비활성", key=f"disable_{entry.schedule_id}",
                                 use_container_width=True):
                        scheduler.toggle_schedule(entry.schedule_id, False)
                        st.rerun()
                else:
                    if st.button("활성화", key=f"enable_{entry.schedule_id}",
                                 use_container_width=True):
                        scheduler.toggle_schedule(entry.schedule_id, True)
                        st.rerun()

                if st.button("삭제", key=f"del_{entry.schedule_id}",
                             use_container_width=True):
                    scheduler.remove_schedule(entry.schedule_id)
                    st.success(f"'{entry.name}' 스케줄이 삭제되었습니다.")
                    st.rerun()


# ══════════════════════════════════════════════
# 탭 2: 스케줄 추가
# ══════════════════════════════════════════════
with tab_add:
    blog_options = get_blog_options()

    if not blog_options:
        st.warning("활성 블로그 계정이 없습니다. 설정에서 블로그 계정을 추가해주세요.")
    elif len(scheduler.get_schedules()) >= MAX_SCHEDULES:
        st.warning(f"최대 스케줄 수({MAX_SCHEDULES}개)에 도달했습니다. 기존 스케줄을 삭제 후 추가하세요.")
    else:
        with st.form("add_schedule_form"):
            st.markdown("**새 스케줄 등록**")

            name = st.text_input(
                "스케줄 이름",
                placeholder="오전 자동발행",
                key="new_sched_name",
            )

            col_time, col_blog = st.columns(2)
            with col_time:
                hour = st.number_input("발행 시각 (시)", min_value=0, max_value=23, value=9)
                minute = st.number_input("발행 시각 (분)", min_value=0, max_value=59, value=0)
            with col_blog:
                blog_id = st.selectbox(
                    "대상 블로그",
                    options=list(blog_options.keys()),
                    format_func=lambda x: blog_options[x],
                )
                max_articles = st.number_input(
                    "최대 발행 건수",
                    min_value=1,
                    max_value=20,
                    value=5,
                    help="한 번에 발행할 최대 글 수",
                )

            days = st.selectbox(
                "반복 요일",
                options=list(DAYS_OF_WEEK_OPTIONS.keys()),
                format_func=lambda x: DAYS_OF_WEEK_OPTIONS[x],
            )

            submitted = st.form_submit_button("스케줄 등록", type="primary")

            if submitted:
                if not name:
                    st.error("스케줄 이름을 입력하세요.")
                else:
                    entry = ScheduleEntry(
                        schedule_id=f"sched_{uuid.uuid4().hex[:8]}",
                        name=name,
                        cron_hour=hour,
                        cron_minute=minute,
                        blog_id=blog_id,
                        max_articles=max_articles,
                        enabled=True,
                        days_of_week=days,
                    )
                    if scheduler.add_schedule(entry):
                        st.success(f"'{name}' 스케줄이 등록되었습니다!")
                        st.rerun()
                    else:
                        st.error("스케줄 등록에 실패했습니다.")


# ══════════════════════════════════════════════
# 탭 3: 실행 기록
# ══════════════════════════════════════════════
with tab_logs:
    logs = scheduler.get_logs(limit=30)

    if not logs:
        st.info("아직 실행 기록이 없습니다.")
    else:
        # 요약 통계
        total_runs = len(logs)
        total_published = sum(l.get("articles_published", 0) for l in logs)
        total_failed = sum(l.get("articles_failed", 0) for l in logs)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("총 실행 횟수", f"{total_runs}회")
        mc2.metric("총 발행 성공", f"{total_published}건")
        mc3.metric("총 발행 실패", f"{total_failed}건")

        st.divider()

        # 기록 테이블
        for log in logs:
            status = log.get("status", "")
            pub = log.get("articles_published", 0)
            fail = log.get("articles_failed", 0)
            executed = log.get("executed_at", "")
            message = log.get("message", "")
            sched_id = log.get("schedule_id", "")

            # 스케줄 이름 찾기
            sched_name = sched_id
            for s in scheduler.get_schedules():
                if s.schedule_id == sched_id:
                    sched_name = s.name
                    break

            if status == "성공":
                status_icon = "🟢"
            elif status == "부분실패":
                status_icon = "🟡"
            else:
                status_icon = "🔴"

            st.markdown(
                f"{status_icon} **{executed}** | {sched_name} | "
                f"성공 {pub}건 / 실패 {fail}건 | {message}"
            )
