"""
📊 대시보드 — 오늘의 현황, 블로그별 진행률, 비용 추정, 최근 발행 기록
"""

import datetime
import json
import sys
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
    page_title="대시보드 — AutoPost",
    page_icon="📊",
    layout="wide",
)

# DB 초기화
init_db()

# app.py의 공통 함수 재사용
from app import get_config, inject_custom_css, render_sidebar, render_status_bar

config = get_config()
inject_custom_css()
render_sidebar(config)
render_status_bar(config)


# ──────────────────────────────────────────────
# 추가 CSS (대시보드 전용)
# ──────────────────────────────────────────────
st.markdown("""
<style>
.big-metric {
    background: linear-gradient(135deg, #1A1D29 0%, #232738 100%);
    border: 1px solid #2D3250;
    border-radius: 14px;
    padding: 1.5rem 1.2rem;
    text-align: center;
    transition: transform 0.2s;
}
.big-metric:hover {
    transform: translateY(-2px);
    border-color: #6C5CE7;
}
.big-metric .icon {
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
}
.big-metric .num {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1.1;
}
.big-metric .desc {
    font-size: 0.78rem;
    color: #A0A4B8;
    margin-top: 0.3rem;
}
.big-metric.waiting .num { color: #74B9FF; }
.big-metric.done .num { color: #00D68F; }
.big-metric.published .num { color: #6C5CE7; }
.big-metric.failed .num { color: #FF6B6B; }

.section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #FAFAFA;
    margin: 1.5rem 0 0.8rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #2D3250;
}

.blog-progress-row {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.7rem 1rem;
    background: #1A1D29;
    border: 1px solid #2D3250;
    border-radius: 10px;
    margin-bottom: 0.5rem;
}
.blog-progress-row .bp-name {
    font-weight: 600;
    color: #FAFAFA;
    min-width: 120px;
    font-size: 0.9rem;
}
.blog-progress-row .bp-bar {
    flex: 1;
    background: #2D3250;
    border-radius: 6px;
    height: 10px;
    overflow: hidden;
}
.blog-progress-row .bp-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, #6C5CE7, #A29BFE);
}
.blog-progress-row .bp-stats {
    font-size: 0.78rem;
    color: #A0A4B8;
    min-width: 100px;
    text-align: right;
}

.cost-card {
    background: #1A1D29;
    border: 1px solid #2D3250;
    border-radius: 10px;
    padding: 1rem;
}
.cost-card .cost-engine {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.4rem 0;
    border-bottom: 1px solid #232738;
}
.cost-card .cost-engine:last-child {
    border-bottom: none;
}
.cost-card .engine-name {
    font-size: 0.85rem;
    color: #A0A4B8;
}
.cost-card .engine-cost {
    font-size: 0.9rem;
    font-weight: 600;
    color: #FAFAFA;
}
.cost-total {
    display: flex;
    justify-content: space-between;
    padding: 0.8rem 1rem;
    background: linear-gradient(135deg, #6C5CE7 0%, #A29BFE 100%);
    border-radius: 10px;
    margin-top: 0.5rem;
}
.cost-total .ct-label {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.85);
}
.cost-total .ct-value {
    font-size: 1.1rem;
    font-weight: 700;
    color: #FFFFFF;
}

.record-status {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}
.record-status.success {
    background: rgba(0,214,143,0.15);
    color: #00D68F;
}
.record-status.fail {
    background: rgba(255,107,107,0.15);
    color: #FF6B6B;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 데이터 조회 함수
# ──────────────────────────────────────────────
def get_today_range():
    today = datetime.date.today()
    start = datetime.datetime.combine(today, datetime.time.min)
    end = datetime.datetime.combine(today, datetime.time.max)
    return start, end


def get_month_range():
    today = datetime.date.today()
    start = datetime.datetime(today.year, today.month, 1)
    if today.month == 12:
        end = datetime.datetime(today.year + 1, 1, 1) - datetime.timedelta(seconds=1)
    else:
        end = datetime.datetime(today.year, today.month + 1, 1) - datetime.timedelta(seconds=1)
    return start, end


def get_status_counts() -> dict:
    """오늘의 상태별 글 수 집계"""
    start, end = get_today_range()
    try:
        articles = GeneratedArticle.select().where(
            GeneratedArticle.created_at.between(start, end)
        )
        counts = {"전체대기": 0, "생성완료": 0, "검토완료": 0, "발행완료": 0, "실패": 0}
        for a in articles:
            if a.status in counts:
                counts[a.status] += 1
            else:
                counts["전체대기"] += 1
        # 발행 로그에서 오늘 발행 건수
        published = PublishLog.select().where(
            PublishLog.published_at.between(start, end),
            PublishLog.status == "성공",
        ).count()
        failed = PublishLog.select().where(
            PublishLog.published_at.between(start, end),
            PublishLog.status == "실패",
        ).count()
        counts["발행완료"] = published
        counts["실패"] = failed
        total = sum(counts.values())
        counts["전체대기"] = total  # 전체 = 모든 상태 합
        return counts
    except Exception:
        return {"전체대기": 0, "생성완료": 0, "검토완료": 0, "발행완료": 0, "실패": 0}


def get_blog_progress() -> list[dict]:
    """블로그별 진행률 (발행 로그 기반)"""
    try:
        accounts = st.session_state.get("blog_accounts", [
            {"id": "blog_01", "name": "맛집탐방일기", "target": 5},
            {"id": "blog_02", "name": "IT리뷰어", "target": 3},
            {"id": "blog_03", "name": "살림노하우", "target": 4},
        ])
        start, end = get_today_range()
        result = []
        for acc in accounts:
            blog_id = acc["id"]
            published = PublishLog.select().where(
                PublishLog.blog_id == blog_id,
                PublishLog.published_at.between(start, end),
                PublishLog.status == "성공",
            ).count()
            target = acc.get("target", 5)
            result.append({
                "name": acc.get("name", blog_id),
                "blog_id": blog_id,
                "published": published,
                "target": target,
                "pct": min(100, int(published / max(target, 1) * 100)),
            })
        return result
    except Exception:
        return []


def get_monthly_cost() -> dict:
    """이번 달 엔진별 비용 추정"""
    start, end = get_month_range()
    costs = {
        "OpenAI (글)": 0.0,
        "Claude (글)": 0.0,
        "Gemini (글)": 0.0,
        "GPT Image": 0.0,
        "Flux": 0.0,
        "Ideogram": 0.0,
        "Pollinations": 0.0,
    }
    engine_map = {
        "openai": "OpenAI (글)",
        "claude": "Claude (글)",
        "gemini": "Gemini (글)",
    }
    img_engine_map = {
        "gpt_image": "GPT Image",
        "flux_schnell": "Flux",
        "flux_pro": "Flux",
        "ideogram": "Ideogram",
        "gemini_image": "Gemini (글)",
        "pollinations": "Pollinations",
    }

    try:
        articles = GeneratedArticle.select().where(
            GeneratedArticle.created_at.between(start, end)
        )
        for a in articles:
            key = engine_map.get(a.engine, "OpenAI (글)")
            costs[key] += a.cost_estimate

        images = GeneratedImage.select().where(
            GeneratedImage.created_at.between(start, end)
        )
        for img in images:
            key = img_engine_map.get(img.engine, "GPT Image")
            costs[key] += img.cost_estimate
    except Exception:
        pass

    return costs


def get_recent_publish_logs(limit: int = 20) -> list[dict]:
    """최근 발행 기록"""
    try:
        logs = (
            PublishLog
            .select()
            .order_by(PublishLog.published_at.desc())
            .limit(limit)
        )
        result = []
        for log in logs:
            result.append({
                "시간": log.published_at.strftime("%m/%d %H:%M") if log.published_at else "-",
                "블로그": log.blog_id,
                "제목": log.title[:30] + "..." if len(log.title) > 30 else log.title,
                "상태": log.status,
                "IP": log.ip_address or "-",
                "재시도": log.retry_count,
                "URL": log.post_url or "-",
            })
        return result
    except Exception:
        return []


# ──────────────────────────────────────────────
# 페이지 렌더링
# ──────────────────────────────────────────────
st.markdown("# 📊 대시보드")
st.caption(f"마지막 업데이트: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ── 1) 오늘의 현황 카드 ──
st.markdown('<div class="section-header">오늘의 현황</div>', unsafe_allow_html=True)

counts = get_status_counts()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="big-metric waiting">
        <div class="icon">📋</div>
        <div class="num">{counts['전체대기']}</div>
        <div class="desc">전체 대기</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="big-metric done">
        <div class="icon">✅</div>
        <div class="num">{counts['생성완료'] + counts['검토완료']}</div>
        <div class="desc">생성 완료</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="big-metric published">
        <div class="icon">🚀</div>
        <div class="num">{counts['발행완료']}</div>
        <div class="desc">발행 완료</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="big-metric failed">
        <div class="icon">⚠️</div>
        <div class="num">{counts['실패']}</div>
        <div class="desc">실패</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ── 2) 블로그별 진행률 + 비용 추정 (2열 레이아웃) ──
left_col, right_col = st.columns([3, 2])

with left_col:
    st.markdown('<div class="section-header">블로그별 오늘 진행률</div>', unsafe_allow_html=True)

    progress_data = get_blog_progress()

    if progress_data:
        for bp in progress_data:
            bar_color = "#00D68F" if bp["pct"] >= 100 else "#6C5CE7"
            st.markdown(f"""
            <div class="blog-progress-row">
                <div class="bp-name">{bp['name']}</div>
                <div class="bp-bar">
                    <div class="bp-fill" style="width:{bp['pct']}%; background:linear-gradient(90deg, {bar_color}, {bar_color}88);"></div>
                </div>
                <div class="bp-stats">{bp['published']}/{bp['target']}건 ({bp['pct']}%)</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("블로그 계정을 설정하면 진행률이 표시됩니다.")

with right_col:
    st.markdown('<div class="section-header">이번 달 비용 추정</div>', unsafe_allow_html=True)

    costs = get_monthly_cost()
    total_cost = sum(costs.values())

    cost_rows = ""
    for engine, cost in costs.items():
        if cost > 0:
            cost_rows += f"""
            <div class="cost-engine">
                <span class="engine-name">{engine}</span>
                <span class="engine-cost">₩{cost:,.0f}</span>
            </div>
            """

    if cost_rows:
        st.markdown(f"""
        <div class="cost-card">
            {cost_rows}
        </div>
        <div class="cost-total">
            <span class="ct-label">총 비용</span>
            <span class="ct-value">₩{total_cost:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="cost-card">
            <div class="cost-engine">
                <span class="engine-name">사용 기록 없음</span>
                <span class="engine-cost">₩0</span>
            </div>
        </div>
        <div class="cost-total">
            <span class="ct-label">총 비용</span>
            <span class="ct-value">₩0</span>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")

# ── 3) 최근 발행 기록 테이블 ──
st.markdown('<div class="section-header">최근 발행 기록</div>', unsafe_allow_html=True)

logs = get_recent_publish_logs()

if logs:
    import pandas as pd

    df = pd.DataFrame(logs)

    # 상태에 따라 색상 표시
    def style_status(val):
        if val == "성공":
            return "color: #00D68F; font-weight: 600;"
        elif val == "실패":
            return "color: #FF6B6B; font-weight: 600;"
        return ""

    styled_df = df.style.applymap(style_status, subset=["상태"])
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=400,
    )
else:
    # 발행 기록 없을 때 안내 화면
    st.markdown("""
    <div style="
        text-align: center;
        padding: 3rem 2rem;
        background: #1A1D29;
        border: 1px dashed #2D3250;
        border-radius: 12px;
        color: #636e72;
    ">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📭</div>
        <div style="font-size: 1rem; margin-bottom: 0.3rem;">아직 발행 기록이 없습니다</div>
        <div style="font-size: 0.8rem;">글을 생성하고 발행하면 여기에 기록이 표시됩니다</div>
    </div>
    """, unsafe_allow_html=True)

# ── 4) 하단 요약 통계 ──
st.markdown("")
st.divider()

sc1, sc2, sc3, sc4 = st.columns(4)

with sc1:
    try:
        total_articles = GeneratedArticle.select().count()
    except Exception:
        total_articles = 0
    st.metric("총 생성된 글", f"{total_articles}건")

with sc2:
    try:
        total_images = GeneratedImage.select().count()
    except Exception:
        total_images = 0
    st.metric("총 생성된 이미지", f"{total_images}장")

with sc3:
    try:
        total_published = PublishLog.select().where(PublishLog.status == "성공").count()
    except Exception:
        total_published = 0
    st.metric("총 발행 성공", f"{total_published}건")

with sc4:
    try:
        total_failed = PublishLog.select().where(PublishLog.status == "실패").count()
    except Exception:
        total_failed = 0
    fail_rate = f"{total_failed / max(total_published + total_failed, 1) * 100:.1f}%"
    st.metric("실패율", fail_rate)
