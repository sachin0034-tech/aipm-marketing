import os
from datetime import date as date_min, datetime
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px

from youtube_client import (
    get_channel_info, get_recent_videos, get_channel_analytics,
    credentials_from_token_dict, revoke_oauth,
    get_my_channel, format_number, format_watch_time, format_seconds,
)
from streamlit_oauth import OAuth2Component
from substack_client import CATEGORIES, BOARD_TYPES, fetch_leaderboard
from substack_author import fetch_newsletter_data
from linkedin_client import fetch_company_posts
from snowflake_client import (
    save_youtube, save_substack, save_linkedin, test_connection,
    fetch_youtube_snapshots, fetch_substack_snapshots, fetch_linkedin_snapshots,
)

load_dotenv(override=True)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Creator Dashboard",
    page_icon="🎛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0a0a0a; }
[data-testid="stSidebar"] { background: #0d0d0d; border-right: 1px solid #1f1f1f; }
[data-testid="stTabs"] button { font-weight: 600; font-size: 0.9rem; }

/* ── Sidebar nav cards ── */
div[data-testid="stSidebar"] .nav-card-wrap { margin-bottom: 5px; }
div[data-testid="stSidebar"] .nav-card-wrap .stButton > button {
    background: #111 !important;
    border: 1px solid #222 !important;
    border-radius: 11px !important;
    color: #6b7280 !important;
    text-align: left !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 11px 14px !important;
    transition: all 0.15s ease !important;
    box-shadow: none !important;
}
div[data-testid="stSidebar"] .nav-card-wrap .stButton > button:hover {
    background: #1a1a1a !important;
    border-color: #333 !important;
    color: #e5e7eb !important;
}
/* YouTube — red */
div[data-testid="stSidebar"] .nav-card-wrap.nav-active-yt .stButton > button {
    background: rgba(239,68,68,0.18) !important;
    border-color: rgba(239,68,68,0.55) !important;
    border-left: 3px solid #ef4444 !important;
    color: #fca5a5 !important;
    font-weight: 700 !important;
    box-shadow: 0 0 12px rgba(239,68,68,0.12) !important;
}
/* Substack — orange */
div[data-testid="stSidebar"] .nav-card-wrap.nav-active-ss .stButton > button {
    background: rgba(255,103,25,0.18) !important;
    border-color: rgba(255,103,25,0.55) !important;
    border-left: 3px solid #ff6719 !important;
    color: #fdba74 !important;
    font-weight: 700 !important;
    box-shadow: 0 0 12px rgba(255,103,25,0.12) !important;
}
/* LinkedIn — blue */
div[data-testid="stSidebar"] .nav-card-wrap.nav-active-li .stButton > button {
    background: rgba(10,102,194,0.22) !important;
    border-color: rgba(10,102,194,0.6) !important;
    border-left: 3px solid #0a66c2 !important;
    color: #93c5fd !important;
    font-weight: 700 !important;
    box-shadow: 0 0 12px rgba(10,102,194,0.14) !important;
}
/* Authentication — violet */
div[data-testid="stSidebar"] .nav-card-wrap.nav-active-auth .stButton > button {
    background: rgba(139,92,246,0.18) !important;
    border-color: rgba(139,92,246,0.55) !important;
    border-left: 3px solid #8b5cf6 !important;
    color: #c4b5fd !important;
    font-weight: 700 !important;
    box-shadow: 0 0 12px rgba(139,92,246,0.12) !important;
}

/* ── Auth section cards ── */
.auth-card {
    background: #111; border-radius: 14px; padding: 24px;
    border: 1px solid #1f1f1f; margin-bottom: 20px;
}
.auth-card-title {
    font-size: 1rem; font-weight: 700; color: #fff;
    margin: 0 0 16px 0; display: flex; align-items: center; gap: 8px;
}
.auth-status-ok  { color: #10b981; font-size: 0.75rem; font-weight: 600; }
.auth-status-off { color: #6b7280; font-size: 0.75rem; }

/* ── Section label ── */
.section-label {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #6b7280; margin: 0 0 10px 0;
}
.section-label.yt { color: #ff0000; }
.section-label.ss { color: #FF6719; }
.section-label.li { color: #0a66c2; }

/* ── Stat card ── */
.stat-card {
    background: #111; border-radius: 12px; padding: 18px 20px;
    border: 1px solid #1f1f1f; text-align: center; height: 100%;
}
.stat-value {
    font-size: 1.7rem; font-weight: 800; color: #fff;
    line-height: 1.1; letter-spacing: -0.02em;
}
.stat-label {
    font-size: 0.72rem; color: #6b7280; margin-top: 5px;
    font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em;
}

/* ── YouTube channel card ── */
.yt-card {
    background: linear-gradient(135deg, #111827 0%, #1a1a2e 100%);
    border-radius: 16px; padding: 24px 28px; display: flex;
    align-items: center; gap: 22px; border: 1px solid #1f2937; margin-bottom: 8px;
}
.yt-avatar {
    width: 86px; height: 86px; border-radius: 50%;
    border: 3px solid #ff0000; object-fit: cover; flex-shrink: 0;
}
.yt-channel-name { font-size: 1.4rem; font-weight: 700; color: #fff; margin: 0 0 4px 0; }
.yt-channel-sub  { color: #6b7280; font-size: 0.82rem; margin: 0 0 14px 0; }
.yt-pill {
    display: inline-block; background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 20px;
    padding: 4px 13px; font-size: 0.79rem; color: #d1d5db;
    margin-right: 7px; margin-bottom: 4px;
}

/* ── Video card ── */
.vid-card {
    background: #111; border-radius: 10px; overflow: hidden;
    border: 1px solid #1f1f1f; height: 100%;
}
.vid-thumb { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; }
.vid-duration {
    position: relative; margin-top: -24px; float: right;
    background: rgba(0,0,0,0.85); color: #fff;
    font-size: 0.71rem; padding: 2px 6px; border-radius: 4px;
    margin-right: 6px; font-weight: 700;
}
.vid-body { padding: 10px 12px 14px; clear: both; }
.vid-title {
    font-size: 0.87rem; font-weight: 600; color: #fff; margin: 0 0 7px 0;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; line-height: 1.35; min-height: 2.4em;
}
.vid-stats { font-size: 0.75rem; color: #6b7280; }
.vid-stats span { margin-right: 10px; }

/* ── Substack cards ── */
.ss-card {
    background: #111; border-radius: 14px; padding: 18px 18px 14px;
    border: 1px solid #1f1f1f; display: flex; gap: 14px; margin-bottom: 12px;
    position: relative; text-decoration: none !important; transition: border-color 0.15s;
}
.ss-card:hover { border-color: #FF6719; }
.ss-rank {
    position: absolute; top: 14px; right: 14px;
    background: rgba(255,103,25,0.12); border: 1px solid rgba(255,103,25,0.25);
    color: #FF6719; font-size: 0.72rem; font-weight: 800;
    padding: 2px 9px; border-radius: 20px;
}
.ss-logo {
    width: 54px; height: 54px; border-radius: 10px; object-fit: cover;
    flex-shrink: 0; background: #1f1f1f; border: 1px solid #2a2a2a;
}
.ss-logo-placeholder {
    width: 54px; height: 54px; border-radius: 10px;
    background: linear-gradient(135deg, #1f1f1f, #2a2a2a);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 1.4rem;
}
.ss-body { flex: 1; min-width: 0; padding-right: 36px; }
.ss-name {
    font-size: 0.93rem; font-weight: 700; color: #fff; margin: 0 0 2px 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ss-author { font-size: 0.76rem; color: #6b7280; margin: 0 0 7px 0; }
.ss-desc {
    font-size: 0.79rem; color: #9ca3af; margin: 0 0 10px 0;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; line-height: 1.45; min-height: 2.3em;
}
.ss-footer { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ss-badge-paid {
    background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.25);
    color: #10b981; font-size: 0.65rem; font-weight: 800;
    padding: 2px 8px; border-radius: 20px; text-transform: uppercase;
}
.ss-badge-rising {
    background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.25);
    color: #fbbf24; font-size: 0.65rem; font-weight: 800;
    padding: 2px 8px; border-radius: 20px; text-transform: uppercase;
}
.ss-badge-cat {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
    color: #9ca3af; font-size: 0.65rem; padding: 2px 8px; border-radius: 20px;
}
.ss-subs { font-size: 0.78rem; color: #FF6719; font-weight: 700; margin-left: auto; }

/* ── LinkedIn ── */
.li-card {
    background: linear-gradient(135deg, #0a1628 0%, #0d1f3c 100%);
    border-radius: 16px; padding: 24px 28px; display: flex;
    align-items: center; gap: 22px; border: 1px solid #1d4ed8; margin-bottom: 8px;
}
.li-logo {
    width: 86px; height: 86px; border-radius: 12px;
    border: 2px solid #0a66c2; object-fit: cover; flex-shrink: 0;
}
.li-name { font-size: 1.4rem; font-weight: 700; color: #fff; margin: 0 0 4px 0; }
.li-meta { color: #6b7280; font-size: 0.82rem; margin: 0 0 14px 0; }
.li-pill {
    display: inline-block; background: rgba(10,102,194,0.15);
    border: 1px solid rgba(10,102,194,0.35); border-radius: 20px;
    padding: 4px 13px; font-size: 0.79rem; color: #60a5fa;
    margin-right: 7px; margin-bottom: 4px;
}
.li-post-card {
    background: #0d1117; border-radius: 12px; padding: 16px;
    border: 1px solid #1a2535; margin-bottom: 10px;
    border-left: 3px solid #0a66c2;
}
.li-post-text {
    font-size: 0.83rem; color: #d1d5db; line-height: 1.5; margin: 0 0 12px 0;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.li-post-footer { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.li-stat { font-size: 0.72rem; color: #6b7280; background: rgba(255,255,255,0.04); padding: 3px 9px; border-radius: 10px; }
.li-stat-hi { color: #60a5fa; font-weight: 600; }
.li-date { font-size: 0.72rem; color: #4b5563; margin-left: auto; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
_cred_defaults = {
    "api_key":              os.getenv("YOUTUBE_API_KEY", ""),
    "apify_token":          os.getenv("APIFY_TOKEN", ""),
    "google_client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
    "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
    "google_redirect_uri":  os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501"),
    "sf_account":           os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "sf_user":              os.getenv("SNOWFLAKE_USER", ""),
    "sf_password":          os.getenv("SNOWFLAKE_PASSWORD", ""),
    "sf_database":          os.getenv("SNOWFLAKE_DATABASE", ""),
    "sf_schema":            os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
    "sf_warehouse":         os.getenv("SNOWFLAKE_WAREHOUSE", ""),
}
_data_defaults = {
    "channel_info":     None,
    "videos":           None,
    "analytics":        None,
    "analytics_error":  None,
    "analytics_period": 7,
    "oauth_creds":      None,
    "oauth_token":      None,
    "my_channel":       None,
    "ss_results":       None,
    "ss_error":         None,
    "ss_author":        None,
    "ss_author_error":  None,
    "li_data":          None,
    "li_error":         None,
    "sf_yt_status":     None,
    "sf_ss_status":     None,
    "sf_li_status":     None,
    "sf_test_status":   None,
    "nav_page":         "▶️  YouTube",
    # competitor tracking
    "yt_profile_type":  "My Channel",
    "yt_profile_label": "",
    "ss_profile_type":  "My Newsletter",
    "ss_profile_label": "",
    "li_profile_type":  "My Company",
    "li_profile_label": "",
    "yt_comparison":    None,
    "ss_comparison":    None,
    "li_comparison":    None,
}
for k, v in {**_cred_defaults, **_data_defaults}.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.oauth_creds and st.session_state.my_channel is None:
    try:
        st.session_state.my_channel = get_my_channel(st.session_state.oauth_creds)
    except Exception:
        pass

# ── Credential accessors (read from session state with .env fallback) ──────────
_ENV_MAP = {
    "api_key":              "YOUTUBE_API_KEY",
    "apify_token":          "APIFY_TOKEN",
    "google_client_id":     "GOOGLE_CLIENT_ID",
    "google_client_secret": "GOOGLE_CLIENT_SECRET",
    "google_redirect_uri":  "GOOGLE_REDIRECT_URI",
    "sf_account":           "SNOWFLAKE_ACCOUNT",
    "sf_user":              "SNOWFLAKE_USER",
    "sf_password":          "SNOWFLAKE_PASSWORD",
    "sf_database":          "SNOWFLAKE_DATABASE",
    "sf_schema":            "SNOWFLAKE_SCHEMA",
    "sf_warehouse":         "SNOWFLAKE_WAREHOUSE",
}

def _cred(key):
    return st.session_state.get(key) or os.getenv(_ENV_MAP.get(key, key.upper()), "")

# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:16px 8px 8px;">
        <div style="font-size:1.05rem;font-weight:800;color:#fff;letter-spacing:-0.01em;line-height:1.3;">
            🚀 Marketing SaaS Platform
        </div>
        <div style="font-size:0.72rem;color:#6366f1;margin-top:4px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;">
            for Mahesh Maven
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    _nav_items = [
        ("nav_btn_yt",   "▶️  YouTube",        "▶️  YouTube",        "nav-active-yt"),
        ("nav_btn_ss",   "📰  Substack",        "📰  Substack",        "nav-active-ss"),
        ("nav_btn_li",   "💼  LinkedIn",        "💼  LinkedIn",        "nav-active-li"),
        ("nav_btn_auth", "🔐  Authentication",  "🔐  Authentication",  "nav-active-auth"),
    ]
    for _btn_key, _btn_label, _page_val, _active_cls in _nav_items:
        _is_active = st.session_state.get("nav_page") == _page_val
        _wrap_cls = f"nav-card-wrap {_active_cls}" if _is_active else "nav-card-wrap"
        st.markdown(f'<div class="{_wrap_cls}">', unsafe_allow_html=True)
        if st.button(_btn_label, key=_btn_key, use_container_width=True):
            st.session_state.nav_page = _page_val
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    page = st.session_state.get("nav_page", "▶️  YouTube")

    st.divider()

    # Status indicators
    st.markdown('<p style="font-size:0.68rem;color:#4b5563;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">Connection Status</p>', unsafe_allow_html=True)

    yt_ok = bool(_cred("api_key"))
    oauth_ok = st.session_state.oauth_creds is not None
    apify_ok = bool(_cred("apify_token"))
    sf_ok = all([_cred("sf_account"), _cred("sf_user"), _cred("sf_password"), _cred("sf_database"), _cred("sf_warehouse")])

    def _dot(ok): return "🟢" if ok else "🔴"
    st.markdown(f"""
    <div style="font-size:0.78rem;color:#6b7280;line-height:2;">
        {_dot(yt_ok)} YouTube API &nbsp;&nbsp;
        {_dot(oauth_ok)} YouTube OAuth<br>
        {_dot(apify_ok)} Apify &nbsp;&nbsp;
        {_dot(sf_ok)} Snowflake
    </div>
    """, unsafe_allow_html=True)

    if not yt_ok or not oauth_ok or not apify_ok or not sf_ok:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button(
            "⚙️ Go to Authentication",
            use_container_width=True,
            on_click=lambda: st.session_state.update({"nav_page": "🔐  Authentication"}),
        )

# ── Credential shortcuts (used throughout pages) ───────────────────────────────
api_key      = _cred("api_key")
apify_token  = _cred("apify_token")
sf_account   = _cred("sf_account")
sf_user      = _cred("sf_user")
sf_password  = _cred("sf_password")
sf_database  = _cred("sf_database")
sf_schema    = _cred("sf_schema")
sf_warehouse = _cred("sf_warehouse")

def _sf_creds():
    return dict(account=sf_account, user=sf_user, password=sf_password,
                database=sf_database, schema=sf_schema, warehouse=sf_warehouse)

def _sf_ready():
    return all([sf_account, sf_user, sf_password, sf_database, sf_warehouse])


# ══════════════════════════════════════════════════════════════════════════════
#  YOUTUBE PAGE
# ══════════════════════════════════════════════════════════════════════════════
if page == "▶️  YouTube":
    st.markdown('<h2 style="color:#fff;font-weight:800;margin-bottom:4px;">▶️ YouTube</h2>', unsafe_allow_html=True)
    st.caption("Channel stats, analytics, and recent videos.")
    st.divider()

    pt_col, label_col = st.columns([2, 3])
    with pt_col:
        yt_ptype = st.radio("Profile type", ["My Channel", "Competitor"], horizontal=True, key="yt_profile_type")
    with label_col:
        if yt_ptype == "Competitor":
            st.text_input("Competitor label (e.g. MrBeast)", key="yt_profile_label", placeholder="Used to identify this competitor in Snowflake")
        else:
            st.session_state.yt_profile_label = ""

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        channel_input = st.text_input("Channel", placeholder="@MrBeast  ·  UCX6OQ...  ·  youtube.com/@channel", label_visibility="collapsed")
    with col_btn:
        fetch_yt = st.button("Fetch", type="primary", use_container_width=True, key="yt_fetch")

    if fetch_yt:
        if not api_key:
            st.error("Add your YouTube Data API Key in the Authentication page.")
        elif not channel_input.strip():
            st.error("Enter a channel ID or @handle.")
        else:
            with st.spinner("Fetching channel data…"):
                try:
                    info = get_channel_info(api_key, channel_input)
                    videos = get_recent_videos(api_key, info["uploads_playlist_id"])
                    st.session_state.channel_info = info
                    st.session_state.videos = videos
                    st.session_state.analytics = None
                    st.session_state.analytics_error = None
                    if st.session_state.oauth_creds:
                        try:
                            st.session_state.analytics = get_channel_analytics(
                                st.session_state.oauth_creds, info["id"],
                                days=st.session_state.analytics_period,
                            )
                        except Exception as e:
                            err = str(e)
                            st.session_state.analytics_error = (
                                "The connected Google account doesn't own a YouTube channel, "
                                "or the YouTube Analytics API isn't enabled in your project."
                                if "403" in err or "Forbidden" in err else err
                            )
                except Exception as e:
                    st.error(f"Error: {e}")

    info      = st.session_state.channel_info
    videos    = st.session_state.videos
    analytics = st.session_state.analytics

    if info:
        st.markdown('<p class="section-label yt">Channel</p>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="yt-card">
            <img class="yt-avatar" src="{info['thumbnail']}" alt="avatar">
            <div>
                <p class="yt-channel-name">{info['name']}</p>
                <p class="yt-channel-sub">📍 {info['country']} &nbsp;·&nbsp; Joined {info['published_at']}</p>
                <span class="yt-pill">👥 {format_number(info['subscribers'])} subscribers</span>
                <span class="yt-pill">👁 {format_number(info['total_views'])} total views</span>
                <span class="yt-pill">🎬 {format_number(info['video_count'])} videos</span>
                <span class="yt-pill">🆔 {info['id']}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        if info.get("description"):
            with st.expander("Channel description"):
                st.write(info["description"])

        st.divider()

        # Analytics
        ana_l, ana_c, ana_r = st.columns([3, 2, 1])
        with ana_l:
            st.markdown('<p class="section-label yt">Analytics</p>', unsafe_allow_html=True)
        with ana_c:
            period_map = {"Last 7 days": 7, "Last 28 days": 28, "Last 90 days": 90}
            sel = st.selectbox("Period", list(period_map.keys()), index=0, label_visibility="collapsed", key="yt_period")
            st.session_state.analytics_period = period_map[sel]
        with ana_r:
            if st.button("Refresh", use_container_width=True, key="yt_refresh"):
                with st.spinner("Refreshing…"):
                    try:
                        st.session_state.analytics = get_channel_analytics(
                            st.session_state.oauth_creds, st.session_state.channel_info["id"],
                            days=st.session_state.analytics_period)
                        st.session_state.analytics_error = None
                        analytics = st.session_state.analytics
                    except Exception as e:
                        err = str(e)
                        st.session_state.analytics_error = "Forbidden — check that the connected account owns this channel." if "403" in err else err

        if analytics:
            st.caption(f"{analytics['start_date']} → {analytics['end_date']}  ·  ~3 day lag")
            my_ch = st.session_state.get("my_channel")
            if my_ch:
                st.info(f"Analytics for **{my_ch['name']}** ({my_ch['id']})  ·  {format_number(my_ch['subscribers'])} subs", icon="📺")
            else:
                st.warning("Connected account has no YouTube channel.", icon="⚠️")
            if not analytics.get("has_data"):
                st.warning("No data for this period — channel may have no recent activity.", icon="📭")

            c1, c2, c3, c4, c5 = st.columns(5)
            for col, val, lbl in [
                (c1, format_number(analytics["views"]),                  "Views"),
                (c2, format_watch_time(analytics["watch_minutes"]),      "Watch Time"),
                (c3, format_seconds(analytics["avg_view_duration_sec"]), "Avg Duration"),
                (c4, format_number(analytics["likes"]),                  "Likes"),
                (c5, format_number(analytics["subscribers_gained"]),     "Subs Gained"),
            ]:
                with col:
                    st.markdown(f'<div class="stat-card"><div class="stat-value">{val}</div><div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)

            if analytics["daily"]:
                st.markdown("<br>", unsafe_allow_html=True)
                df_d = pd.DataFrame(analytics["daily"])
                df_d["date"] = pd.to_datetime(df_d["date"])
                df_d["day"]  = df_d["date"].dt.strftime("%b %d")
                use_bar = len(df_d) <= 14

                def _chart(df, x, y, label, color, use_bar):
                    if use_bar:
                        fig = px.bar(df, x=x, y=y, labels={x:"",y:label}, color_discrete_sequence=[color], text=y)
                        fig.update_traces(texttemplate="%{text:,}", textposition="outside", textfont_size=11)
                    else:
                        fig = px.area(df, x=x, y=y, labels={x:"",y:label}, color_discrete_sequence=[color])
                    fig.update_layout(margin=dict(t=30,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", showlegend=False)
                    fig.update_xaxes(showgrid=False, tickfont_color="#6b7280")
                    fig.update_yaxes(gridcolor="#1a1a1a", tickfont_color="#6b7280")
                    return fig

                tv, tw = st.tabs(["📈 Daily Views", "⏱ Daily Watch Time"])
                with tv:
                    st.plotly_chart(_chart(df_d, "day", "views", "Views", "#ff0000", use_bar), use_container_width=True)
                with tw:
                    st.plotly_chart(_chart(df_d, "day", "watch_minutes", "Minutes", "#6366f1", use_bar), use_container_width=True)

        elif st.session_state.get("analytics_error"):
            st.error(st.session_state.analytics_error)
        elif st.session_state.oauth_creds:
            st.info("Analytics connected — click Fetch to load data.", icon="📊")
        else:
            st.info("Connect your Google Account in Authentication to unlock analytics.", icon="🔒")

        st.divider()

        if videos:
            st.markdown(f'<p class="section-label yt">Recent Videos ({len(videos)})</p>', unsafe_allow_html=True)
            cols = st.columns(3)
            for i, v in enumerate(videos):
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="vid-card">
                        <a href="{v['url']}" target="_blank" style="text-decoration:none;">
                            <img class="vid-thumb" src="{v['thumbnail']}" alt="">
                            <div class="vid-duration">{v['duration']}</div>
                            <div class="vid-body">
                                <p class="vid-title">{v['title']}</p>
                                <div class="vid-stats">
                                    <span>👁 {format_number(v['views'])}</span>
                                    <span>👍 {format_number(v['likes'])}</span>
                                    <span>💬 {format_number(v['comments'])}</span>
                                </div>
                                <div class="vid-stats" style="margin-top:4px;color:#4b5563;">{v['published_at']}</div>
                            </div>
                        </a>
                    </div><br>""", unsafe_allow_html=True)

        st.divider()
        sf_yt_col, sf_yt_msg = st.columns([2, 3])
        with sf_yt_col:
            if st.button("❄️ Save YouTube Snapshot", use_container_width=True, key="sf_save_yt"):
                if not _sf_ready():
                    st.session_state.sf_yt_status = ("error", "Fill in Snowflake credentials in Authentication.")
                else:
                    with st.spinner("Saving to Snowflake…"):
                        try:
                            _ptype = "competitor" if st.session_state.yt_profile_type == "Competitor" else "own"
                            _plabel = st.session_state.yt_profile_label.strip()
                            save_youtube(_sf_creds(), st.session_state.channel_info, st.session_state.videos, st.session_state.analytics, _ptype, _plabel)
                            st.session_state.sf_yt_status = ("ok", f"Saved to CREATOR_YOUTUBE_SNAPSHOTS · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            st.session_state.yt_comparison = None
                        except Exception as e:
                            st.session_state.sf_yt_status = ("error", str(e))
        with sf_yt_msg:
            s = st.session_state.get("sf_yt_status")
            if s: (st.success if s[0]=="ok" else st.error)(s[1])

    # ── Competitor comparison (pulls from Snowflake) ───────────────────────────
    st.divider()
    st.markdown('<p class="section-label yt">Competitor Comparison</p>', unsafe_allow_html=True)
    cmp_load, cmp_msg = st.columns([2, 4])
    with cmp_load:
        if st.button("🔄 Load Comparison from Snowflake", use_container_width=True, key="yt_load_cmp"):
            if not _sf_ready():
                st.session_state.yt_comparison = ("error", "Fill in Snowflake credentials in Authentication.")
            else:
                with st.spinner("Loading snapshots…"):
                    try:
                        rows = fetch_youtube_snapshots(_sf_creds())
                        st.session_state.yt_comparison = ("ok", rows)
                    except Exception as e:
                        st.session_state.yt_comparison = ("error", str(e))

    cmp = st.session_state.get("yt_comparison")
    if cmp and cmp[0] == "error":
        st.error(cmp[1])
    elif cmp and cmp[0] == "ok":
        rows = cmp[1]
        if not rows:
            st.info("No snapshots saved yet. Fetch a channel and click Save to add one.", icon="📊")
        else:
            df_cmp = pd.DataFrame([{
                "Profile":     r.get("profile_label") or r.get("channel_name"),
                "Type":        r.get("profile_type", "own").capitalize(),
                "Subscribers": r.get("channel_subscribers", 0),
                "Total Views": r.get("channel_total_views", 0),
                "Videos":      r.get("channel_video_count", 0),
                "Views (period)": r.get("analytics_views", 0) or 0,
                "Subs Gained": r.get("analytics_subscribers_gained", 0) or 0,
                "Saved At":    str(r.get("fetched_at", ""))[:16],
            } for r in rows])

            st.dataframe(df_cmp, use_container_width=True, hide_index=True,
                column_config={
                    "Subscribers": st.column_config.NumberColumn(format="%d"),
                    "Total Views": st.column_config.NumberColumn(format="%d"),
                    "Views (period)": st.column_config.NumberColumn(format="%d"),
                    "Subs Gained": st.column_config.NumberColumn(format="%d"),
                })

            if len(df_cmp) > 1:
                st.markdown("<br>", unsafe_allow_html=True)
                cc1, cc2 = st.columns(2)
                with cc1:
                    fig_subs = px.bar(df_cmp.sort_values("Subscribers", ascending=False),
                        x="Profile", y="Subscribers", color="Type",
                        color_discrete_map={"Own":"#ff0000","Competitor":"#6366f1"},
                        title="Subscribers", text="Subscribers")
                    fig_subs.update_traces(texttemplate="%{text:,}", textposition="outside")
                    fig_subs.update_layout(margin=dict(t=40,b=10), plot_bgcolor="#0a0a0a",
                        paper_bgcolor="#0a0a0a", font_color="#9ca3af", showlegend=True)
                    fig_subs.update_xaxes(showgrid=False)
                    fig_subs.update_yaxes(gridcolor="#1a1a1a")
                    st.plotly_chart(fig_subs, use_container_width=True)
                with cc2:
                    fig_views = px.bar(df_cmp.sort_values("Total Views", ascending=False),
                        x="Profile", y="Total Views", color="Type",
                        color_discrete_map={"Own":"#ff0000","Competitor":"#6366f1"},
                        title="Total Views", text="Total Views")
                    fig_views.update_traces(texttemplate="%{text:,}", textposition="outside")
                    fig_views.update_layout(margin=dict(t=40,b=10), plot_bgcolor="#0a0a0a",
                        paper_bgcolor="#0a0a0a", font_color="#9ca3af", showlegend=True)
                    fig_views.update_xaxes(showgrid=False)
                    fig_views.update_yaxes(gridcolor="#1a1a1a")
                    st.plotly_chart(fig_views, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SUBSTACK PAGE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📰  Substack":
    st.markdown('<h2 style="color:#fff;font-weight:800;margin-bottom:4px;">📰 Substack</h2>', unsafe_allow_html=True)
    st.caption("Your newsletter analytics and the global leaderboard.")
    st.divider()

    ss_sub_my, ss_sub_lb = st.tabs(["📝  My Newsletter", "🏆  Leaderboard"])

    with ss_sub_my:
        ss_pt_col, ss_label_col = st.columns([2, 3])
        with ss_pt_col:
            ss_ptype = st.radio("Profile type", ["My Newsletter", "Competitor"], horizontal=True, key="ss_profile_type")
        with ss_label_col:
            if ss_ptype == "Competitor":
                st.text_input("Competitor label (e.g. The Hustle)", key="ss_profile_label", placeholder="Used to identify this competitor in Snowflake")
            else:
                st.session_state.ss_profile_label = ""

        url_col, btn_col = st.columns([5, 1])
        with url_col:
            ss_url = st.text_input("Newsletter URL", placeholder="yournewsletter.substack.com  ·  substack.com/@yourhandle", label_visibility="collapsed")
        with btn_col:
            fetch_author = st.button("Fetch", type="primary", use_container_width=True, key="ss_author_fetch")

        if fetch_author:
            if not ss_url.strip():
                st.error("Enter your Substack URL.")
            else:
                with st.spinner("Fetching newsletter data…"):
                    try:
                        data = fetch_newsletter_data(ss_url.strip())
                        st.session_state.ss_author = data
                        st.session_state.ss_author_error = None
                    except Exception as e:
                        st.session_state.ss_author_error = str(e)
                        st.session_state.ss_author = None

        if st.session_state.get("ss_author_error"):
            st.error(st.session_state.ss_author_error)

        author_data = st.session_state.get("ss_author")

        if author_data:
            profile = author_data["profile"]
            posts   = author_data["posts"]
            df = pd.DataFrame(posts)

            logo_html = (
                f'<img style="width:72px;height:72px;border-radius:12px;object-fit:cover;border:2px solid #FF6719;flex-shrink:0;" src="{profile["logo"]}" alt="">'
                if profile["logo"]
                else '<div style="width:72px;height:72px;border-radius:12px;background:#1f1f1f;display:flex;align-items:center;justify-content:center;font-size:2rem;flex-shrink:0;">📰</div>'
            )
            subs_pill = f'<span class="yt-pill">👥 {format_number(profile["subscribers"])} subscribers</span>' if profile.get("subscribers") else ""
            st.markdown(f"""
            <div class="yt-card" style="border-color:#2a1f14;">
                {logo_html}
                <div>
                    <p class="yt-channel-name">{profile["name"]}</p>
                    <p class="yt-channel-sub">✍️ {profile["author"]} &nbsp;·&nbsp;
                        <a href="{profile["url"]}" target="_blank" style="color:#FF6719;text-decoration:none;">{profile["url"]}</a>
                    </p>
                    {subs_pill}
                    <span class="yt-pill">📝 {len(posts)} posts</span>
                </div>
            </div>""", unsafe_allow_html=True)

            if profile.get("description"):
                with st.expander("About this newsletter"):
                    st.write(profile["description"])

            st.divider()
            st.markdown('<p class="section-label ss">Overview</p>', unsafe_allow_html=True)

            total_posts    = len(posts)
            total_likes    = sum(p["likes"]    for p in posts)
            total_coms     = sum(p["comments"] for p in posts)
            total_restacks = sum(p["restacks"] for p in posts)
            avg_likes      = round(total_likes / total_posts, 1) if total_posts else 0
            paid_count     = sum(1 for p in posts if p["is_paid"])
            free_count     = total_posts - paid_count

            sv1,sv2,sv3,sv4,sv5,sv6 = st.columns(6)
            for col,val,lbl in [
                (sv1,str(total_posts),"Total Posts"),(sv2,str(total_likes),"Total Likes"),
                (sv3,str(total_coms),"Total Comments"),(sv4,str(total_restacks),"Total Restacks"),
                (sv5,str(avg_likes),"Avg Likes / Post"),(sv6,f"{free_count}F · {paid_count}P","Free · Paid"),
            ]:
                with col:
                    st.markdown(f'<div class="stat-card"><div class="stat-value" style="font-size:1.4rem;">{val}</div><div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.divider()

            ch1, ch2 = st.columns([3, 1])
            with ch1:
                st.markdown('<p class="section-label ss">Engagement Over Time</p>', unsafe_allow_html=True)
                df_time = df[df["date"].notna()].copy()
                df_time["date"] = pd.to_datetime(df_time["date"])
                df_time = df_time.sort_values("date")
                fig_eng = px.line(df_time, x="date", y=["likes","comments","restacks"],
                    labels={"date":"","value":"Count","variable":""},
                    color_discrete_map={"likes":"#FF6719","comments":"#6366f1","restacks":"#10b981"})
                fig_eng.update_traces(mode="lines+markers", marker_size=5)
                fig_eng.update_layout(margin=dict(t=10,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", legend=dict(bgcolor="#111", bordercolor="#1f1f1f", borderwidth=1))
                fig_eng.update_xaxes(showgrid=False, tickfont_color="#6b7280")
                fig_eng.update_yaxes(gridcolor="#1a1a1a", tickfont_color="#6b7280")
                st.plotly_chart(fig_eng, use_container_width=True)

            with ch2:
                st.markdown('<p class="section-label ss">Content Split</p>', unsafe_allow_html=True)
                fig_pie = px.pie(pd.DataFrame({"Audience":["Free","Paid"],"Count":[free_count,paid_count]}),
                    names="Audience", values="Count", hole=0.5,
                    color_discrete_map={"Free":"#6366f1","Paid":"#FF6719"})
                fig_pie.update_layout(margin=dict(t=10,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af")
                fig_pie.update_traces(textfont_color="#fff")
                st.plotly_chart(fig_pie, use_container_width=True)

            st.markdown('<p class="section-label ss">Publishing Frequency</p>', unsafe_allow_html=True)
            df_freq = df[df["month"].notna()].groupby("month").size().reset_index(name="posts").sort_values("month").tail(18)
            fig_freq = px.bar(df_freq, x="month", y="posts", labels={"month":"","posts":"Posts Published"},
                color_discrete_sequence=["#FF6719"], text="posts")
            fig_freq.update_traces(textposition="outside", textfont_size=10)
            fig_freq.update_layout(margin=dict(t=20,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", showlegend=False)
            fig_freq.update_xaxes(showgrid=False, tickfont_color="#6b7280")
            fig_freq.update_yaxes(gridcolor="#1a1a1a", tickfont_color="#6b7280")
            st.plotly_chart(fig_freq, use_container_width=True)

            st.divider()
            st.markdown('<p class="section-label ss">Top 10 Most Engaging Posts</p>', unsafe_allow_html=True)
            top10 = sorted(posts, key=lambda p: p["engagement"], reverse=True)[:10]
            tc1, tc2 = st.columns(2)
            for i, p in enumerate(top10):
                col = tc1 if i%2==0 else tc2
                aud_badge = '<span class="ss-badge-paid">Paid</span>' if p["is_paid"] else '<span class="ss-badge-cat">Free</span>'
                cover_html = (f'<img style="width:56px;height:56px;border-radius:8px;object-fit:cover;flex-shrink:0;" src="{p["cover"]}" alt="">' if p["cover"] else '<div style="width:56px;height:56px;border-radius:8px;background:#1f1f1f;flex-shrink:0;"></div>')
                title_safe = p["title"].replace("<","&lt;").replace(">","&gt;")
                with col:
                    st.markdown(f"""
                    <a class="ss-card" href="{p['url']}" target="_blank">
                        <span class="ss-rank">#{i+1}</span>
                        {cover_html}
                        <div class="ss-body">
                            <p class="ss-name">{title_safe}</p>
                            <p class="ss-author">{str(p["date"]) if p["date"] else ""}</p>
                            <div class="ss-footer">{aud_badge}<span class="ss-badge-cat">❤ {p['likes']}</span><span class="ss-badge-cat">💬 {p['comments']}</span><span class="ss-subs">{p['engagement']} total</span></div>
                        </div>
                    </a>""", unsafe_allow_html=True)

            st.divider()
            st.markdown('<p class="section-label ss">All Posts</p>', unsafe_allow_html=True)
            df_table = pd.DataFrame([{
                "Date":p["date"] or "","Title":p["title"],"Audience":p["audience"],
                "Likes":p["likes"],"Comments":p["comments"],"Restacks":p["restacks"],
                "Engagement":p["engagement"],"Words":p["wordcount"],"URL":p["url"],
            } for p in sorted(posts, key=lambda x: x["date"] or date_min.min, reverse=True)])
            st.dataframe(df_table, use_container_width=True, hide_index=True,
                column_config={"Likes":st.column_config.NumberColumn(),"Comments":st.column_config.NumberColumn(),
                    "Restacks":st.column_config.NumberColumn(),"Engagement":st.column_config.NumberColumn(),
                    "Words":st.column_config.NumberColumn(),"URL":st.column_config.LinkColumn("Link")})

            st.divider()
            sf_ss_col, sf_ss_msg = st.columns([2, 3])
            with sf_ss_col:
                if st.button("❄️ Save Newsletter Snapshot", use_container_width=True, key="sf_save_ss"):
                    if not _sf_ready():
                        st.session_state.sf_ss_status = ("error", "Fill in Snowflake credentials in Authentication.")
                    else:
                        with st.spinner("Saving to Snowflake…"):
                            try:
                                _ptype = "competitor" if st.session_state.ss_profile_type == "Competitor" else "own"
                                _plabel = st.session_state.ss_profile_label.strip()
                                save_substack(_sf_creds(), st.session_state.ss_author["profile"], st.session_state.ss_author["posts"], _ptype, _plabel)
                                st.session_state.sf_ss_status = ("ok", f"Saved to CREATOR_SUBSTACK_SNAPSHOTS · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                st.session_state.ss_comparison = None
                            except Exception as e:
                                st.session_state.sf_ss_status = ("error", str(e))
            with sf_ss_msg:
                s = st.session_state.get("sf_ss_status")
                if s: (st.success if s[0]=="ok" else st.error)(s[1])

        elif not st.session_state.get("ss_author_error"):
            st.markdown('<div style="text-align:center;padding:60px 20px;"><div style="font-size:3rem;">✍️</div><div style="color:#9ca3af;font-size:1rem;font-weight:600;margin-top:12px;">Your Newsletter Dashboard</div><div style="color:#4b5563;font-size:0.85rem;margin-top:6px;">Enter your Substack URL above and click Fetch.</div></div>', unsafe_allow_html=True)

        # ── Substack competitor comparison ─────────────────────────────────────
        st.divider()
        st.markdown('<p class="section-label ss">Competitor Comparison</p>', unsafe_allow_html=True)
        ss_cmp_btn, _ = st.columns([2, 4])
        with ss_cmp_btn:
            if st.button("🔄 Load Comparison from Snowflake", use_container_width=True, key="ss_load_cmp"):
                if not _sf_ready():
                    st.session_state.ss_comparison = ("error", "Fill in Snowflake credentials in Authentication.")
                else:
                    with st.spinner("Loading snapshots…"):
                        try:
                            rows = fetch_substack_snapshots(_sf_creds())
                            st.session_state.ss_comparison = ("ok", rows)
                        except Exception as e:
                            st.session_state.ss_comparison = ("error", str(e))

        ss_cmp = st.session_state.get("ss_comparison")
        if ss_cmp and ss_cmp[0] == "error":
            st.error(ss_cmp[1])
        elif ss_cmp and ss_cmp[0] == "ok":
            ss_rows = ss_cmp[1]
            if not ss_rows:
                st.info("No snapshots saved yet. Fetch a newsletter and click Save to add one.", icon="📊")
            else:
                df_ss_cmp = pd.DataFrame([{
                    "Profile":      r.get("profile_label") or r.get("newsletter_name"),
                    "Type":         r.get("profile_type", "own").capitalize(),
                    "Total Posts":  r.get("total_posts", 0),
                    "Total Likes":  r.get("total_likes", 0),
                    "Total Comments": r.get("total_comments", 0),
                    "Total Restacks": r.get("total_restacks", 0),
                    "Avg Likes/Post": r.get("avg_likes_per_post", 0),
                    "Saved At":     str(r.get("fetched_at", ""))[:16],
                } for r in ss_rows])

                st.dataframe(df_ss_cmp, use_container_width=True, hide_index=True,
                    column_config={
                        "Total Posts":    st.column_config.NumberColumn(format="%d"),
                        "Total Likes":    st.column_config.NumberColumn(format="%d"),
                        "Total Comments": st.column_config.NumberColumn(format="%d"),
                        "Total Restacks": st.column_config.NumberColumn(format="%d"),
                    })

                if len(df_ss_cmp) > 1:
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        fig_likes = px.bar(df_ss_cmp.sort_values("Avg Likes/Post", ascending=False),
                            x="Profile", y="Avg Likes/Post", color="Type",
                            color_discrete_map={"Own":"#FF6719","Competitor":"#6366f1"},
                            title="Avg Likes per Post", text="Avg Likes/Post")
                        fig_likes.update_traces(texttemplate="%{text:.1f}", textposition="outside")
                        fig_likes.update_layout(margin=dict(t=40,b=10), plot_bgcolor="#0a0a0a",
                            paper_bgcolor="#0a0a0a", font_color="#9ca3af")
                        fig_likes.update_xaxes(showgrid=False)
                        fig_likes.update_yaxes(gridcolor="#1a1a1a")
                        st.plotly_chart(fig_likes, use_container_width=True)
                    with cc2:
                        fig_posts = px.bar(df_ss_cmp.sort_values("Total Posts", ascending=False),
                            x="Profile", y="Total Posts", color="Type",
                            color_discrete_map={"Own":"#FF6719","Competitor":"#6366f1"},
                            title="Total Posts", text="Total Posts")
                        fig_posts.update_traces(texttemplate="%{text:d}", textposition="outside")
                        fig_posts.update_layout(margin=dict(t=40,b=10), plot_bgcolor="#0a0a0a",
                            paper_bgcolor="#0a0a0a", font_color="#9ca3af")
                        fig_posts.update_xaxes(showgrid=False)
                        fig_posts.update_yaxes(gridcolor="#1a1a1a")
                        st.plotly_chart(fig_posts, use_container_width=True)

    with ss_sub_lb:
        cc1,cc2,cc3,cc4 = st.columns([4,2,1,1])
        with cc1:
            selected_labels = st.multiselect("Categories", options=list(CATEGORIES.keys()), default=["Bestseller"], placeholder="Choose categories…")
        with cc2:
            selected_board = st.multiselect("Board Type", options=BOARD_TYPES, default=["paid"])
        with cc3:
            max_results = st.number_input("Max", min_value=10, max_value=200, value=25, step=10)
        with cc4:
            st.markdown("<br>", unsafe_allow_html=True)
            fetch_ss = st.button("Fetch", type="primary", use_container_width=True, key="ss_fetch")

        if fetch_ss:
            if not apify_token:
                st.error("Add your Apify Token in the Authentication page.")
            elif not selected_labels or not selected_board:
                st.error("Select at least one category and board type.")
            else:
                slugs = [CATEGORIES[l] for l in selected_labels]
                with st.spinner("Running Apify actor… may take 1–2 minutes."):
                    try:
                        results = fetch_leaderboard(apify_token, slugs, selected_board, int(max_results))
                        st.session_state.ss_results = results
                        st.session_state.ss_error = None
                    except Exception as e:
                        st.session_state.ss_error = str(e)
                        st.session_state.ss_results = None

        if st.session_state.get("ss_error"):
            st.error(st.session_state.ss_error)

        results = st.session_state.get("ss_results")
        if results:
            total      = len(results)
            cats_found = len({r["category"] for r in results if r["category"]})
            with_subs  = [r for r in results if r["subscribers"] > 0]

            st.markdown('<p class="section-label ss">Overview</p>', unsafe_allow_html=True)
            s1,s2,s3,s4 = st.columns(4)
            for col,val,lbl in [
                (s1,str(total),"Newsletters"),(s2,str(cats_found),"Categories"),
                (s3,format_number(sum(r["subscribers"] for r in with_subs)) if with_subs else "—","Total Subscribers"),
                (s4,format_number(int(sum(r["subscribers"] for r in with_subs)/len(with_subs))) if with_subs else "—","Avg Subscribers"),
            ]:
                with col:
                    st.markdown(f'<div class="stat-card"><div class="stat-value">{val}</div><div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            vc,vch,vt = st.tabs(["🗂 Cards","📊 Chart","📋 Table"])

            with vc:
                lc,rc = st.columns(2)
                for i,r in enumerate(results):
                    col = lc if i%2==0 else rc
                    badge = ('<span class="ss-badge-paid">Paid</span>' if r["board_type"]=="paid" else '<span class="ss-badge-rising">Rising</span>' if r["board_type"]=="rising" else "")
                    cat_pill  = f'<span class="ss-badge-cat">{r["category"]}</span>' if r["category"] else ""
                    subs_html = f'<span class="ss-subs">{format_number(r["subscribers"])}</span>' if r["subscribers"] else ""
                    rank_str  = f"#{r['rank']}" if r["rank"] else f"#{i+1}"
                    logo_html = f'<img class="ss-logo" src="{r["logo"]}" alt="">' if r["logo"] else '<div class="ss-logo-placeholder">📰</div>'
                    desc   = r["description"][:120]+"…" if len(r["description"])>120 else r["description"]
                    author = f"by {r['author']}" if r["author"] else ""
                    with col:
                        st.markdown(f'<a class="ss-card" href="{r["url"]}" target="_blank"><span class="ss-rank">{rank_str}</span>{logo_html}<div class="ss-body"><p class="ss-name">{r["name"]}</p><p class="ss-author">{author}</p><p class="ss-desc">{desc}</p><div class="ss-footer">{badge}{cat_pill}{subs_html}</div></div></a>', unsafe_allow_html=True)

            with vch:
                chartable = [r for r in results if r["subscribers"]>0]
                if chartable:
                    top = sorted(chartable, key=lambda x: x["subscribers"], reverse=True)[:20]
                    fig = px.bar(pd.DataFrame(top), x="subscribers", y="name", orientation="h",
                        color="board_type", color_discrete_map={"paid":"#10b981","rising":"#fbbf24"},
                        labels={"subscribers":"Subscribers","name":"","board_type":"Type"}, hover_data=["author","category"])
                    fig.update_layout(height=max(400,len(top)*32), margin=dict(t=20,b=20,l=20,r=20),
                        plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", yaxis={"categoryorder":"total ascending"})
                    fig.update_xaxes(showgrid=False)
                    fig.update_yaxes(tickfont_color="#d1d5db", tickfont_size=11)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No subscriber data to chart.", icon="📊")

            with vt:
                df_t = pd.DataFrame([{"Rank":r["rank"] or i+1,"Newsletter":r["name"],"Author":r["author"],"Category":r["category"],"Type":r["board_type"],"Subscribers":r["subscribers"],"URL":r["url"]} for i,r in enumerate(results)])
                st.dataframe(df_t, use_container_width=True, hide_index=True,
                    column_config={"Subscribers":st.column_config.NumberColumn(format="%d"),"URL":st.column_config.LinkColumn("Link")})
        elif not st.session_state.get("ss_error"):
            st.markdown('<div style="text-align:center;padding:60px 20px;"><div style="font-size:3rem;">🏆</div><div style="color:#9ca3af;font-size:1rem;font-weight:600;margin-top:12px;">Substack Leaderboard</div><div style="color:#4b5563;font-size:0.85rem;margin-top:6px;">Select categories and click Fetch.</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  LINKEDIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💼  LinkedIn":
    st.markdown('<h2 style="color:#fff;font-weight:800;margin-bottom:4px;">💼 LinkedIn</h2>', unsafe_allow_html=True)
    st.caption("Company page posts, engagement trends, and audience insights.")
    st.divider()

    li_pt_col, li_label_col = st.columns([2, 3])
    with li_pt_col:
        li_ptype = st.radio("Profile type", ["My Company", "Competitor"], horizontal=True, key="li_profile_type")
    with li_label_col:
        if li_ptype == "Competitor":
            st.text_input("Competitor label (e.g. Lenny's Newsletter)", key="li_profile_label", placeholder="Used to identify this competitor in Snowflake")
        else:
            st.session_state.li_profile_label = ""

    li_col,li_max_col,li_btn_col = st.columns([5,1,1])
    with li_col:
        li_url = st.text_input("LinkedIn Company URL", value="https://www.linkedin.com/company/mahesh-ai-pm-community/", label_visibility="collapsed", placeholder="https://www.linkedin.com/company/your-company/")
    with li_max_col:
        li_max = st.number_input("Posts", min_value=10, max_value=200, value=100, step=10, label_visibility="collapsed")
    with li_btn_col:
        fetch_li = st.button("Fetch", type="primary", use_container_width=True, key="li_fetch")

    if fetch_li:
        if not apify_token:
            st.error("Add your Apify Token in the Authentication page.")
        else:
            with st.spinner(f"Scraping LinkedIn via Apify… fetching up to {li_max} posts."):
                try:
                    data = fetch_company_posts(apify_token, li_url.strip(), int(li_max))
                    st.session_state.li_data  = data
                    st.session_state.li_error = None
                except Exception as e:
                    st.session_state.li_error = str(e)
                    st.session_state.li_data  = None

    if st.session_state.get("li_error"):
        st.error(st.session_state.li_error)

    li = st.session_state.get("li_data")

    if li:
        co    = li["company"]
        posts = li["posts"]

        st.markdown('<p class="section-label li">Company</p>', unsafe_allow_html=True)
        logo_html = (f'<img class="li-logo" src="{co["logo"]}" alt="">' if co["logo"]
            else '<div style="width:86px;height:86px;border-radius:12px;background:#0a66c2;display:flex;align-items:center;justify-content:center;font-size:2.2rem;flex-shrink:0;">💼</div>')
        st.markdown(f"""
        <div class="li-card">
            {logo_html}
            <div>
                <p class="li-name">{co["name"]}</p>
                <p class="li-meta"><a href="{co["url"]}" target="_blank" style="color:#0a66c2;text-decoration:none;">linkedin.com/company/{co["slug"]}</a></p>
                <span class="li-pill">👥 {format_number(co["followers"])} followers</span>
                <span class="li-pill">📝 {len(posts)} posts scraped</span>
            </div>
        </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown('<p class="section-label li">Performance Overview</p>', unsafe_allow_html=True)

        n = len(posts)
        total_reactions = sum(p["reactions"]  for p in posts)
        total_comments  = sum(p["comments"]   for p in posts)
        total_reposts   = sum(p["reposts"]    for p in posts)
        total_eng       = sum(p["engagement"] for p in posts)
        avg_reactions   = round(total_reactions/n,1) if n else 0
        eng_rate        = round((total_eng/(n*max(co["followers"],1)))*100,3) if n else 0

        sc1,sc2,sc3,sc4,sc5,sc6 = st.columns(6)
        for col,val,lbl in [
            (sc1,format_number(co["followers"]),"Followers"),(sc2,str(n),"Posts Analysed"),
            (sc3,str(total_reactions),"Total Reactions"),(sc4,str(total_comments),"Total Comments"),
            (sc5,str(avg_reactions),"Avg Reactions"),(sc6,f"{eng_rate}%","Avg Eng. Rate"),
        ]:
            with col:
                st.markdown(f'<div class="stat-card"><div class="stat-value" style="font-size:1.35rem;">{val}</div><div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()

        st.markdown('<p class="section-label li">Engagement Trends</p>', unsafe_allow_html=True)
        ch1, ch2 = st.columns([3, 1])
        df_posts = pd.DataFrame(posts)

        with ch1:
            df_time = df_posts[df_posts["date"].notna()].copy()
            df_time["date"] = pd.to_datetime(df_time["date"])
            df_time = df_time.sort_values("date")
            fig_eng = px.line(df_time, x="date", y=["reactions","comments","reposts"],
                labels={"date":"","value":"Count","variable":""},
                color_discrete_map={"reactions":"#0a66c2","comments":"#60a5fa","reposts":"#10b981"})
            fig_eng.update_traces(mode="lines+markers", marker_size=4)
            fig_eng.update_layout(margin=dict(t=10,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", legend=dict(bgcolor="#111", bordercolor="#1a2535", borderwidth=1))
            fig_eng.update_xaxes(showgrid=False, tickfont_color="#6b7280")
            fig_eng.update_yaxes(gridcolor="#1a1a1a", tickfont_color="#6b7280")
            st.plotly_chart(fig_eng, use_container_width=True)

        with ch2:
            rx = {k:v for k,v in {"Like":sum(p["likes"] for p in posts),"Celebrate":sum(p["celebrates"] for p in posts),"Support":sum(p["supports"] for p in posts),"Love":sum(p["loves"] for p in posts),"Insightful":sum(p["insightful"] for p in posts)}.items() if v>0}
            if rx:
                fig_rx = px.pie(names=list(rx.keys()), values=list(rx.values()), hole=0.5,
                    color_discrete_sequence=["#0a66c2","#10b981","#f59e0b","#ef4444","#8b5cf6"])
                fig_rx.update_layout(margin=dict(t=10,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af",
                    legend=dict(bgcolor="#111",bordercolor="#1a2535",borderwidth=1), title=dict(text="Reaction Types",font_color="#9ca3af",x=0.5))
                fig_rx.update_traces(textfont_color="#fff")
                st.plotly_chart(fig_rx, use_container_width=True)

        ch3,ch4 = st.columns([3,1])
        with ch3:
            st.markdown('<p class="section-label li">Posting Frequency</p>', unsafe_allow_html=True)
            df_freq = df_posts[df_posts["month"].notna()].groupby("month").agg(posts=("engagement","count")).reset_index().sort_values("month").tail(18)
            if not df_freq.empty:
                fig_freq = px.bar(df_freq, x="month", y="posts", labels={"month":"","posts":"Posts"}, color_discrete_sequence=["#0a66c2"], text="posts")
                fig_freq.update_traces(textposition="outside", textfont_size=10)
                fig_freq.update_layout(margin=dict(t=20,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", showlegend=False)
                fig_freq.update_xaxes(showgrid=False, tickfont_color="#6b7280")
                fig_freq.update_yaxes(gridcolor="#1a1a1a", tickfont_color="#6b7280")
                st.plotly_chart(fig_freq, use_container_width=True)

        with ch4:
            st.markdown('<p class="section-label li">Post Types</p>', unsafe_allow_html=True)
            type_counts = df_posts["post_type"].value_counts().reset_index()
            type_counts.columns = ["type","count"]
            fig_type = px.pie(type_counts, names="type", values="count", hole=0.5,
                color_discrete_sequence=["#0a66c2","#3b82f6","#60a5fa","#93c5fd"])
            fig_type.update_layout(margin=dict(t=10,b=10), plot_bgcolor="#0a0a0a", paper_bgcolor="#0a0a0a", font_color="#9ca3af", legend=dict(bgcolor="#111",bordercolor="#1a2535",borderwidth=1))
            fig_type.update_traces(textfont_color="#fff")
            st.plotly_chart(fig_type, use_container_width=True)

        st.divider()
        st.markdown('<p class="section-label li">Top 10 Posts by Engagement</p>', unsafe_allow_html=True)
        top10 = sorted(posts, key=lambda p: p["engagement"], reverse=True)[:10]
        tc1,tc2 = st.columns(2)
        for i,p in enumerate(top10):
            col = tc1 if i%2==0 else tc2
            text_safe = p["text_preview"].replace("<","&lt;").replace(">","&gt;")
            with col:
                st.markdown(f"""
                <div class="li-post-card">
                    <p class="li-post-text">{text_safe}</p>
                    <div class="li-post-footer">
                        <span class="li-stat li-stat-hi">#{i+1}</span>
                        <span class="li-stat">👍 {p['reactions']}</span>
                        <span class="li-stat">💬 {p['comments']}</span>
                        <span class="li-stat">🔁 {p['reposts']}</span>
                        <span class="li-stat">⚡ {p['engagement']}</span>
                        <span class="li-date">{str(p['date']) if p['date'] else ""}</span>
                    </div>
                    <div style="margin-top:8px;"><a href="{p['url']}" target="_blank" style="font-size:0.72rem;color:#0a66c2;text-decoration:none;">View post →</a></div>
                </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown('<p class="section-label li">All Posts</p>', unsafe_allow_html=True)
        df_table = pd.DataFrame([{
            "Date":str(p["date"]) if p["date"] else "","Preview":p["text_preview"],"Type":p["post_type"],
            "Reactions":p["reactions"],"💙 Like":p["likes"],"🎉 Celebrate":p["celebrates"],
            "💬 Comments":p["comments"],"🔁 Reposts":p["reposts"],"Engagement":p["engagement"],"URL":p["url"],
        } for p in sorted(posts, key=lambda x: x["timestamp"], reverse=True)])
        st.dataframe(df_table, use_container_width=True, hide_index=True,
            column_config={"Reactions":st.column_config.NumberColumn(),"💙 Like":st.column_config.NumberColumn(),
                "🎉 Celebrate":st.column_config.NumberColumn(),"💬 Comments":st.column_config.NumberColumn(),
                "🔁 Reposts":st.column_config.NumberColumn(),"Engagement":st.column_config.NumberColumn(),
                "URL":st.column_config.LinkColumn("Link")})

        st.divider()
        sf_li_col,sf_li_msg = st.columns([2,3])
        with sf_li_col:
            if st.button("❄️ Save LinkedIn Snapshot", use_container_width=True, key="sf_save_li"):
                if not _sf_ready():
                    st.session_state.sf_li_status = ("error","Fill in Snowflake credentials in Authentication.")
                else:
                    with st.spinner("Saving to Snowflake…"):
                        try:
                            _ptype = "competitor" if st.session_state.li_profile_type == "Competitor" else "own"
                            _plabel = st.session_state.li_profile_label.strip()
                            save_linkedin(_sf_creds(), st.session_state.li_data["company"], st.session_state.li_data["posts"], _ptype, _plabel)
                            st.session_state.sf_li_status = ("ok",f"Saved to CREATOR_LINKEDIN_SNAPSHOTS · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            st.session_state.li_comparison = None
                        except Exception as e:
                            st.session_state.sf_li_status = ("error",str(e))
        with sf_li_msg:
            s = st.session_state.get("sf_li_status")
            if s: (st.success if s[0]=="ok" else st.error)(s[1])

    elif not st.session_state.get("li_error"):
        st.markdown('<div style="text-align:center;padding:60px 20px;"><div style="font-size:3rem;">💼</div><div style="color:#9ca3af;font-size:1rem;font-weight:600;margin-top:12px;">LinkedIn Company Dashboard</div><div style="color:#4b5563;font-size:0.85rem;margin-top:6px;">Enter your company page URL and click Fetch.</div></div>', unsafe_allow_html=True)

    # ── LinkedIn competitor comparison ─────────────────────────────────────────
    st.divider()
    st.markdown('<p class="section-label li">Competitor Comparison</p>', unsafe_allow_html=True)
    li_cmp_btn, _ = st.columns([2, 4])
    with li_cmp_btn:
        if st.button("🔄 Load Comparison from Snowflake", use_container_width=True, key="li_load_cmp"):
            if not _sf_ready():
                st.session_state.li_comparison = ("error", "Fill in Snowflake credentials in Authentication.")
            else:
                with st.spinner("Loading snapshots…"):
                    try:
                        rows = fetch_linkedin_snapshots(_sf_creds())
                        st.session_state.li_comparison = ("ok", rows)
                    except Exception as e:
                        st.session_state.li_comparison = ("error", str(e))

    li_cmp = st.session_state.get("li_comparison")
    if li_cmp and li_cmp[0] == "error":
        st.error(li_cmp[1])
    elif li_cmp and li_cmp[0] == "ok":
        li_rows = li_cmp[1]
        if not li_rows:
            st.info("No snapshots saved yet. Fetch a company and click Save to add one.", icon="📊")
        else:
            df_li_cmp = pd.DataFrame([{
                "Profile":       r.get("profile_label") or r.get("company_name"),
                "Type":          r.get("profile_type", "own").capitalize(),
                "Followers":     r.get("followers", 0),
                "Posts":         r.get("posts_analysed", 0),
                "Total Reactions": r.get("total_reactions", 0),
                "Total Comments":  r.get("total_comments", 0),
                "Avg Eng. Rate":   round(float(r.get("avg_engagement_rate") or 0), 3),
                "Saved At":      str(r.get("fetched_at", ""))[:16],
            } for r in li_rows])

            st.dataframe(df_li_cmp, use_container_width=True, hide_index=True,
                column_config={
                    "Followers":       st.column_config.NumberColumn(format="%d"),
                    "Total Reactions": st.column_config.NumberColumn(format="%d"),
                    "Total Comments":  st.column_config.NumberColumn(format="%d"),
                    "Avg Eng. Rate":   st.column_config.NumberColumn(format="%.3f%%"),
                })

            if len(df_li_cmp) > 1:
                lc1, lc2 = st.columns(2)
                with lc1:
                    fig_fol = px.bar(df_li_cmp.sort_values("Followers", ascending=False),
                        x="Profile", y="Followers", color="Type",
                        color_discrete_map={"Own":"#0a66c2","Competitor":"#6366f1"},
                        title="Followers", text="Followers")
                    fig_fol.update_traces(texttemplate="%{text:,}", textposition="outside")
                    fig_fol.update_layout(margin=dict(t=40,b=10), plot_bgcolor="#0a0a0a",
                        paper_bgcolor="#0a0a0a", font_color="#9ca3af")
                    fig_fol.update_xaxes(showgrid=False)
                    fig_fol.update_yaxes(gridcolor="#1a1a1a")
                    st.plotly_chart(fig_fol, use_container_width=True)
                with lc2:
                    fig_eng = px.bar(df_li_cmp.sort_values("Avg Eng. Rate", ascending=False),
                        x="Profile", y="Avg Eng. Rate", color="Type",
                        color_discrete_map={"Own":"#0a66c2","Competitor":"#6366f1"},
                        title="Avg Engagement Rate (%)", text="Avg Eng. Rate")
                    fig_eng.update_traces(texttemplate="%{text:.3f}%", textposition="outside")
                    fig_eng.update_layout(margin=dict(t=40,b=10), plot_bgcolor="#0a0a0a",
                        paper_bgcolor="#0a0a0a", font_color="#9ca3af")
                    fig_eng.update_xaxes(showgrid=False)
                    fig_eng.update_yaxes(gridcolor="#1a1a1a")
                    st.plotly_chart(fig_eng, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTHENTICATION PAGE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔐  Authentication":
    st.markdown('<h2 style="color:#fff;font-weight:800;margin-bottom:4px;">🔐 Authentication</h2>', unsafe_allow_html=True)
    st.caption("All credentials are stored in session state and sent only to their respective APIs.")
    st.divider()

    # ── YouTube ────────────────────────────────────────────────────────────────
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown("#### ▶️ YouTube")

    _yt_key_col, _yt_test_col, _yt_status_col = st.columns([4, 1, 3])
    with _yt_key_col:
        st.text_input("Data API Key", key="api_key", type="password", placeholder="AIza...",
                      help="Google Cloud Console → Credentials → API Key")
    with _yt_test_col:
        st.markdown("<br>", unsafe_allow_html=True)
        _test_key_clicked = st.button("🧪 Test", use_container_width=True, key="yt_test_key")
    with _yt_status_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if _test_key_clicked:
            _k = _cred("api_key")
            if not _k:
                st.error("No API key set.")
            else:
                try:
                    import requests as _req
                    _r = _req.get(
                        f"https://www.googleapis.com/youtube/v3/channels?part=snippet&forHandle=Google&key={_k}",
                        timeout=8,
                    )
                    if _r.status_code == 200:
                        st.success("✓ Key is valid and active.")
                    else:
                        _msg = _r.json().get("error", {}).get("message", "Unknown error")
                        st.error(f"✗ {_msg}")
                except Exception as _e:
                    st.error(f"✗ {_e}")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**YouTube Analytics — Sign in with Google**")
    st.caption("Grants access to your channel's watch time, views, and subscriber data.")

    _g_client_id     = _cred("google_client_id")
    _g_client_secret = _cred("google_client_secret")
    _g_redirect_uri  = _cred("google_redirect_uri")

    if not _g_client_id or not _g_client_secret:
        st.warning("Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in your environment to enable Sign in with Google.", icon="⚠️")
    elif st.session_state.oauth_creds:
        mc = st.session_state.get("my_channel")
        label = f"✓ Signed in as **{mc['name']}**" if mc else "✓ Google Account connected"
        oa1, oa2 = st.columns([3, 1])
        with oa1:
            st.success(label)
        with oa2:
            if st.button("Sign out", use_container_width=True, key="yt_disconnect"):
                revoke_oauth()
                st.session_state.oauth_creds = None
                st.session_state.oauth_token = None
                st.session_state.analytics   = None
                st.session_state.my_channel  = None
                st.rerun()
    else:
        _oauth2 = OAuth2Component(
            client_id=_g_client_id,
            client_secret=_g_client_secret,
            authorize_endpoint="https://accounts.google.com/o/oauth2/auth",
            token_endpoint="https://oauth2.googleapis.com/token",
            refresh_token_endpoint="https://oauth2.googleapis.com/token",
        )
        _result = _oauth2.authorize_button(
            name="Sign in with Google",
            redirect_uri=_g_redirect_uri,
            scope=" ".join([
                "https://www.googleapis.com/auth/youtube.readonly",
                "https://www.googleapis.com/auth/yt-analytics.readonly",
            ]),
            key="google_oauth",
            extras_params={"access_type": "offline", "prompt": "consent"},
            use_container_width=False,
            icon="https://www.google.com/favicon.ico",
        )
        if _result and "token" in _result:
            try:
                _creds = credentials_from_token_dict(_result["token"], _g_client_id, _g_client_secret)
                st.session_state.oauth_creds = _creds
                st.session_state.oauth_token = _result["token"]
                try:
                    st.session_state.my_channel = get_my_channel(_creds)
                except Exception:
                    pass
                st.rerun()
            except Exception as e:
                st.error(f"Auth failed: {e}")

    with st.expander("YouTube setup guide"):
        st.markdown("""
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable **YouTube Data API v3** and **YouTube Analytics API**
3. **API Key**: Credentials → Create Credential → API Key
4. **OAuth**: Credentials → Create Credential → **OAuth 2.0 Client ID** → Application type: **Web application**
5. Add your deployed URL under **Authorised redirect URIs** (e.g. `https://your-app.run.app`)
6. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` as environment variables
7. Set `GOOGLE_REDIRECT_URI` to your deployed URL (or `http://localhost:8501` for local dev)
        """)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Apify ──────────────────────────────────────────────────────────────────
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown("#### 🔄 Apify")
    st.caption("Used for Substack Leaderboard scraping and LinkedIn company posts.")
    st.text_input("Apify Token", key="apify_token", type="password", placeholder="apify_api_...",
                  help="console.apify.com → Account → Integrations → API token")
    if _cred("apify_token"):
        st.success("✓ Apify token set")
    with st.expander("Apify setup guide"):
        st.markdown("""
1. Go to [console.apify.com](https://console.apify.com)
2. Sign up / log in
3. Account (top right) → Integrations → copy your **API token**
        """)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Snowflake ──────────────────────────────────────────────────────────────
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown("#### ❄️ Snowflake")
    st.caption("Stores snapshots from all three platforms into `CREATOR_INTELLIGENCE` (or your database of choice).")

    sf_r1c1, sf_r1c2, sf_r1c3 = st.columns(3)
    with sf_r1c1:
        st.text_input("Account", key="sf_account", placeholder="orgname-accountname",
                      help="Found in your Snowflake URL: https://<account>.snowflakecomputing.com")
    with sf_r1c2:
        st.text_input("User", key="sf_user", placeholder="your_username")
    with sf_r1c3:
        st.text_input("Password", key="sf_password", type="password")

    sf_r2c1, sf_r2c2, sf_r2c3 = st.columns(3)
    with sf_r2c1:
        st.text_input("Database", key="sf_database", placeholder="CREATOR_INTELLIGENCE")
    with sf_r2c2:
        st.text_input("Schema", key="sf_schema", placeholder="PUBLIC")
    with sf_r2c3:
        st.text_input("Warehouse", key="sf_warehouse", placeholder="COMPUTE_WH")

    sf_btn_col, sf_msg_col = st.columns([1, 3])
    with sf_btn_col:
        if st.button("🧪 Test Snowflake Connection", use_container_width=True, key="sf_test"):
            if not _sf_ready():
                st.session_state.sf_test_status = ("error", "Fill in all six Snowflake fields above.")
            else:
                with st.spinner("Connecting…"):
                    try:
                        msg = test_connection(sf_account, sf_user, sf_password, sf_database, sf_schema, sf_warehouse)
                        st.session_state.sf_test_status = ("ok", msg)
                    except Exception as e:
                        st.session_state.sf_test_status = ("error", str(e))
    with sf_msg_col:
        s = st.session_state.get("sf_test_status")
        if s:
            st.markdown("<br>", unsafe_allow_html=True)
            (st.success if s[0]=="ok" else st.error)(s[1])

    with st.expander("Snowflake setup guide"):
        st.markdown("""
1. Log into [app.snowflake.com](https://app.snowflake.com)
2. Your **Account** identifier is in the URL: `https://<orgname>-<accountname>.snowflakecomputing.com`
3. Create a database: `CREATE DATABASE CREATOR_INTELLIGENCE;`
4. Tables are created automatically on first Save — no manual setup needed
        """)
    st.markdown('</div>', unsafe_allow_html=True)
