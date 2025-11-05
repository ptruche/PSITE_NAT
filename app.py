# app.py
import streamlit as st
import pandas as pd
import datetime
from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, clear_persisted_login,
    get_category_map, get_topics, resolve_review_path,
    load_questions_frame, questions_count_by_topic, record_attempt,
    overall_accuracy, sr_due_ids, sr_update, load_progress,
    topic_to_slug, get_review_word_count, load_history
)

# ------------------------------------------------------------------ #
# 1. Page config + theme
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="PSITE Mastery",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ------------------------------------------------------------------ #
# 2. Global CSS
# ------------------------------------------------------------------ #
st.markdown(
    """
<style>
:root {
    --accent: #1d4ed8;
    --border: #e5e7eb;
    --bg: #ffffff;
    --text: #111111;
}
@media (prefers-color-scheme: dark) {
    :root {
        --accent: #3b82f6;
        --border: #374151;
        --bg: #111827;
        --text: #f9fafb;
    }
}
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
}
.app-header {
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 56px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 1.5rem;
    z-index: 10000;
    justify-content: space-between;
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.main {
    margin-top: 56px;
    padding: 1.5rem;
}
.q-prompt {
    border: 1px solid var(--border);
    background: #f9fafb;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    font-size: 1rem;
}
.verdict-ok {
    background: #10b9811a;
    color: #065f46;
    border: 1px solid #34d399;
    padding: 0.25rem 0.5rem;
    border-radius: 6px;
    font-size: 0.9rem;
}
.verdict-err {
    background: #ef44441a;
    color: #7f1d1d;
    border: 1px solid #fca5a5;
    padding: 0.25rem 0.5rem;
    border-radius: 6px;
    font-size: 0.9rem;
}
.section-title {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 1rem;
}
.kpi-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--bg);
}
.kpi-ring {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: conic-gradient(var(--accent) 0deg, var(--accent) calc(var(--val) * 3.6deg), #e5e7eb calc(var(--val) * 3.6deg) 360deg);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
}
.kpi-ring::after {
    content: '';
    position: absolute;
    width: 80%;
    height: 80%;
    background: var(--bg);
    border-radius: 50%;
}
.kpi-ring > div {
    position: relative;
    z-index: 1;
    font-weight: 600;
    font-size: 1rem;
    color: var(--text);
}
.topic-title {
    font-weight: 600;
    margin-bottom: .5rem;
}
.meter {
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    position: relative;
    overflow: hidden;
}
.meter > span {
    position: absolute;
    top: 0; left: 0; bottom: 0;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.3s ease;
}
.badge {
    font-size: .78rem;
    color: #6b7280;
    display: flex;
    align-items: center;
    gap: .25rem;
}
.dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #d1d5db;
}
.dot.green {
    background: #10b981;
}
.last-attempt {
    font-size: .82rem;
    color: #6b7280;
    margin-bottom: .5rem;
}
.sidebar-logo {
    text-align: center;
    padding: 1rem 0;
    font-size: 1.4rem;
    font-weight: 900;
    color: var(--text);
    border-bottom: 1px solid var(--border);
    margin-bottom: 1rem;
}
.sidebar-logo span {
    color: var(--accent);
}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ #
# 3. AUTH
# ------------------------------------------------------------------ #
if not auth_is_authed():
    with st.container():
        st.markdown("#### Welcome to **PSITE Mastery**")
        st.caption("Sign-in to unlock your personal dashboard, spaced-repetition, and analytics.")
        auth_login_form()
    st.stop()

# ------------------------------------------------------------------ #
# 4. CACHING
# ------------------------------------------------------------------ #
@st.cache_data(ttl=3600, show_spinner=False)
def _load_all_questions() -> pd.DataFrame:
    return load_questions_frame()

ALL_Q = _load_all_questions()

def load_questions_for_subjects(subjects: list) -> pd.DataFrame:
    if not subjects:
        return ALL_Q
    return ALL_Q[ALL_Q["subject"].isin(subjects)].reset_index(drop=True)

# ------------------------------------------------------------------ #
# 5. Helpers
# ------------------------------------------------------------------ #
def _pct(n, d): return int(round(100 * n / d)) if d else 0

def _render_topic_card(topic: str):
    total = int(Q_COUNT.get(topic, 0))
    prog = PROGRESS.get(topic, {})
    attempted = prog.get("total", 0)
    pct = _pct(attempted, total)
    rev_words = get_review_word_count(topic)
    has_review = rev_words >= 250
    has_quiz = total >= 5
    with st.container(border=True):
        st.markdown(f"<div class='topic-title'>{topic}</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 8, 1])
        with c2:
            st.markdown(f"<div class='meter'><span style='width:{pct}%;'></span></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div style='text-align:right;font-size:.82rem;'>{pct}%</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex;gap:.5rem;margin:.35rem 0;'>"
            f"<span class='badge'><span class='dot{' green' if has_review else ''}'></span>Review</span>"
            f"<span class='badge'><span class='dot{' green' if has_quiz else ''}'></span>Quiz</span>"
            f"<span style='margin-left:auto;font-size:.78rem;color:#6b7280'>Q: {attempted}/{total}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Review", key=f"rev_{topic}", use_container_width=True):
                st.session_state.active_topic = topic
                st.session_state.view = "review"
                st.rerun()
        with b2:
            if st.button("Quiz", key=f"quiz_{topic}", use_container_width=True):
                pool = load_questions_for_subjects([topic]).reset_index(drop=True)
                _start_quiz(pool, mode="normal", topic=topic)

# ------------------------------------------------------------------ #
# 6. Quiz engine
# ------------------------------------------------------------------ #
def _start_quiz(df: pd.DataFrame, mode: str = "normal", topic: str | None = None):
    st.session_state.quiz_pool = df
    st.session_state.quiz_idx = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_revealed = set()
    st.session_state.quiz_finished = False
    st.session_state.quiz_mode = mode
    st.session_state.active_topic = topic
    st.session_state.view = "quiz"
    st.session_state.quiz_status = {}
    st.rerun()

def _record_and_update(row: pd.Series, correct: bool):
    key = f"scored_{row['id']}"
    if not st.session_state.get(key, False):
        record_attempt(row.get("subject", ""), row["id"], correct)
        if st.session_state.get("quiz_mode") == "spaced":
            sr_update(row["id"], correct)
        st.session_state[key] = True
    st.session_state.quiz_status[row["id"]] = correct

# ------------------------------------------------------------------ #
# 7. PRE-COMPUTE
# ------------------------------------------------------------------ #
Q_COUNT = questions_count_by_topic()
PROGRESS = load_progress()

# ------------------------------------------------------------------ #
# 8. HEADER + SIDEBAR
# ------------------------------------------------------------------ #
# Clean header — NO LOGO (prevents flash on sidebar collapse)
st.markdown(
    "<div class='app-header'>"
    "<div></div>"
    "<div></div>"
    "</div>",
    unsafe_allow_html=True,
)

# TEXT-ONLY LOGO IN SIDEBAR — only visible source
st.sidebar.markdown(
    """
    <div class="sidebar-logo">
        PSITE <span>Mastery</span>
    </div>
    """,
    unsafe_allow_html=True
)

# NAVIGATION
nav = {
    "Dashboard": "dashboard",
    "Topics": "topics",        # ← Renamed from "Score Topics"
    "Make Quiz": "make_quiz",
}
for label, view in nav.items():
    if st.sidebar.button(label, key=f"nav_{view}", use_container_width=True):
        st.session_state.view = view
        st.rerun()

st.sidebar.markdown("<div class='sidebar-sep'></div>", unsafe_allow_html=True)

if st.sidebar.button("Spaced Repetition", key="nav_sr", use_container_width=True):
    ids = sr_due_ids(limit=50)
    pool = ALL_Q[ALL_Q["id"].isin(ids)].reset_index(drop=True) if not ALL_Q.empty else ALL_Q
    _start_quiz(pool, mode="spaced")

st.sidebar.markdown("<div class='sidebar-sep'></div>", unsafe_allow_html=True)

if st.sidebar.button("Logout", type="secondary", use_container_width=True):
    clear_persisted_login()
    st.rerun()

# ------------------------------------------------------------------ #
# 9. MAIN + VIEW ROUTER
# ------------------------------------------------------------------ #
st.markdown("<div class='main'>", unsafe_allow_html=True)
view = st.session_state.get("view", "dashboard")

# ---------- DASHBOARD ----------
if view == "dashboard":
    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    attempted_all = sum(v.get("total", 0) for v in PROGRESS.values())
    total_all = sum(Q_COUNT.get(t, 0) for t in Q_COUNT)
    pct_done = _pct(attempted_all, total_all)
    pct_acc = int(round(overall_accuracy() * 100))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-ring" style="--val:{pct_done};"><div>{pct_done}%</div></div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <div style="font-weight:600;font-size:.95rem;">Completed</div>
                <div style="font-size:.82rem;color:#6b7280">{attempted_all} of {total_all}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-ring" style="--val:{pct_acc};"><div>{pct_acc}%</div></div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <div style="font-weight:600;font-size:.95rem;">Accuracy</div>
                <div style="font-size:.82rem;color:#6b7280">All attempts</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------- TOPICS ----------
elif view == "topics":
    st.markdown("<div class='section-title'>Topics</div>", unsafe_allow_html=True)
    cats = get_category_map()
    s1, s2 = st.columns([2, 1])
    with s1:
        q = st.text_input("Search topics", placeholder="Search…", label_visibility="collapsed").strip().lower()
    with s2:
        cat_names = ["All"] + list(cats.keys())
        chosen_cat = st.selectbox("Category", cat_names, index=0, label_visibility="collapsed")
    topics = []
    for cat, arr in cats.items():
        if chosen_cat != "All" and cat != chosen_cat:
            continue
        for t in arr:
            if q and q not in t.lower():
                continue
            topics.append(t)
    if not topics:
        st.info("No topics match your filter.")
    else:
        cols = st.columns(3)
        for i, t in enumerate(topics):
            with cols[i % 3]:
                _render_topic_card(t)

# ---------- REVIEW ----------
elif view == "review":
    topic = st.session_state.get("active_topic")
    if not topic:
        st.info("Choose a topic from Topics.")
    else:
        st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
        p = resolve_review_path(topic)
        if not p:
            st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named with the topic slug.")
        else:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
            st.markdown(txt, unsafe_allow_html=True)
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        if st.button("Quiz this topic", use_container_width=True):
            df = load_questions_for_subjects([topic])
            st.session_state.quiz_pool = df.reset_index(drop=True)
            st.session_state.quiz_idx = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_revealed = set()
            st.session_state.quiz_finished = False
            st.session_state.quiz_mode = "normal"
            st.session_state.view = "quiz"
            st.rerun()

# ---------- MAKE QUIZ ----------
elif view == "make_quiz":
    st.markdown("<div class='section-title'>Make a Quiz</div>", unsafe_allow_html=True)
    topics = ["Any"] + get_topics()
    pick = st.multiselect("Choose topics (or leave empty for Any):", topics, default=[])
    n = st.number_input("Number of questions", 5, 100, 20, step=5)
    if st.button("Start", use_container_width=True):
        if pick and "Any" in pick:
            pick = []
        df = load_questions_for_subjects(pick)
        df = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True) if not df.empty else df
        st.session_state.quiz_pool = df
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.quiz_mode = "normal"
        st.session_state.view = "quiz"
        st.rerun()

# ---------- QUIZ ----------
elif view == "quiz":
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files to `data/questions/`.")
    else:
        history = load_history()
        i = st.session_state.quiz_idx
        row = pool.iloc[i]
        pct = int(((i + 1) / len(pool)) * 100)
        st.progress(pct/100)
        suffix = f" • {row.get('subject','')}" if row.get('subject') else ""
        st.caption(f"Question {i+1} of {len(pool)}{suffix}")
        q_attempts = [h for h in history if h["id"] == row["id"]]
        if q_attempts:
            last_ts = max(h["ts"] for h in q_attempts)
            last_date = datetime.datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S")
            st.markdown(f"<div class='last-attempt'>Last attempted: {last_date}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)
        letters = ["A","B","C","D","E"]
        prev_choice = st.session_state.quiz_answers.get(row["id"])
        default_idx = letters.index(prev_choice) if prev_choice in letters else 0
        choice = st.radio(
            "",
            letters,
            index=default_idx,
            format_func=lambda L: row[L],
            label_visibility="collapsed",
            key=f"q_{row['id']}"
        )
        st.session_state.quiz_answers[row["id"]] = choice
        c1, c2, c3, c4 = st.columns([1,2,2,1])
        with c1:
            if st.button("Reveal", key=f"rev_{i}"):
                st.session_state.quiz_revealed.add(row["id"])
        with c2:
            if st.button("Previous", disabled=(i==0)):
                st.session_state.quiz_idx = max(0, i-1); st.rerun()
        with c3:
            if st.button("Next", disabled=(i==len(pool)-1)):
                st.session_state.quiz_idx = min(len(pool)-1, i+1); st.rerun()
        with c4:
            if st.button("Finish"):
                st.session_state.quiz_finished = True
        if row["id"] in st.session_state.quiz_revealed:
            is_correct = (choice == row["correct"])
            verdict_class = "verdict-ok" if is_correct else "verdict-err"
            verdict_text = "Correct" if is_correct else "Incorrect"
            st.markdown(f"<span class='verdict {verdict_class}'>{verdict_text}</span>", unsafe_allow_html=True)
            if str(row.get("explanation","")).strip():
                st.markdown(row["explanation"], unsafe_allow_html=True)
            _record_and_update(row, is_correct)
        if st.session_state.quiz_finished:
            idxed = pool.set_index("id")
            scored_ids = [qid for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed]
            correct_n = sum(1 for qid in scored_ids if idxed.loc[qid]["correct"] == st.session_state.quiz_answers[qid])
            denom = len(scored_ids) if scored_ids else len(pool)
            st.success(f"Score: {correct_n}/{denom}")

st.markdown("</div>", unsafe_allow_html=True)  # .main
