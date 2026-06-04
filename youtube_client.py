import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
TOKEN_FILE = "token.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

def format_number(n) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_watch_time(minutes: int) -> str:
    if minutes >= 60:
        return f"{minutes / 60:,.0f}h"
    return f"{minutes:,} min"


def format_seconds(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def parse_duration(iso: str) -> str:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        return "0:00"
    h, m, s = (int(x or 0) for x in match.groups())
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def extract_channel_identifier(raw: str):
    """
    Returns (kind, value).
    Handles: full URLs, @handles, bare channel IDs (UC...), usernames.
    """
    raw = raw.strip()
    if "youtube.com" in raw:
        if m := re.search(r"/channel/(UC[\w-]+)", raw):
            return "id", m.group(1)
        if m := re.search(r"/@([\w.-]+)", raw):
            return "handle", m.group(1)
        if m := re.search(r"/user/([\w.-]+)", raw):
            return "username", m.group(1)
    if raw.startswith("@"):
        return "handle", raw[1:]
    if re.match(r"^UC[\w-]{22}$", raw):
        return "id", raw
    return "handle", raw


# ── YouTube Data API v3 ────────────────────────────────────────────────────────

def _build_data_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key)


def get_channel_info(api_key: str, raw_input: str) -> dict:
    yt = _build_data_client(api_key)
    kind, value = extract_channel_identifier(raw_input)

    params = {"part": "snippet,statistics,contentDetails,brandingSettings"}
    if kind == "id":
        params["id"] = value
    elif kind == "handle":
        params["forHandle"] = value
    else:
        params["forUsername"] = value

    resp = yt.channels().list(**params).execute()
    if not resp.get("items"):
        raise ValueError(f"No channel found for: {raw_input!r}")

    ch = resp["items"][0]
    sn = ch["snippet"]
    st = ch["statistics"]
    thumbs = sn.get("thumbnails", {})
    thumb = (
        thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}
    ).get("url", "")

    return {
        "id": ch["id"],
        "name": sn["title"],
        "description": sn.get("description", ""),
        "thumbnail": thumb,
        "country": sn.get("country", "—"),
        "published_at": sn["publishedAt"][:10],
        "subscribers": int(st.get("subscriberCount", 0)),
        "total_views": int(st.get("viewCount", 0)),
        "video_count": int(st.get("videoCount", 0)),
        "uploads_playlist_id": ch["contentDetails"]["relatedPlaylists"]["uploads"],
    }


def get_recent_videos(api_key: str, uploads_playlist_id: str, max_results: int = 9) -> list:
    yt = _build_data_client(api_key)

    playlist_resp = yt.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_results,
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in playlist_resp.get("items", [])
    ]
    if not video_ids:
        return []

    videos_resp = yt.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(video_ids),
    ).execute()

    result = []
    for v in videos_resp.get("items", []):
        sn = v["snippet"]
        st = v.get("statistics", {})
        cd = v.get("contentDetails", {})
        thumbs = sn.get("thumbnails", {})
        thumb = (
            thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}
        ).get("url", "")
        result.append({
            "id": v["id"],
            "title": sn["title"],
            "thumbnail": thumb,
            "published_at": sn["publishedAt"][:10],
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "duration": parse_duration(cd.get("duration", "PT0S")),
            "url": f"https://youtube.com/watch?v={v['id']}",
        })
    return result


# ── Authenticated user's own channel ──────────────────────────────────────────

def get_my_channel(creds: Credentials) -> Optional[dict]:
    """Returns the YouTube channel owned by the authenticated Google account, or None."""
    yt = build("youtube", "v3", credentials=creds)
    resp = yt.channels().list(
        part="snippet,statistics",
        mine=True,
    ).execute()
    if not resp.get("items"):
        return None
    ch = resp["items"][0]
    sn = ch["snippet"]
    st = ch["statistics"]
    return {
        "id": ch["id"],
        "name": sn["title"],
        "subscribers": int(st.get("subscriberCount", 0)),
        "total_views": int(st.get("viewCount", 0)),
        "thumbnail": (sn.get("thumbnails", {}).get("default") or {}).get("url", ""),
    }


# ── Web OAuth helper ───────────────────────────────────────────────────────────

def credentials_from_token_dict(token_dict: dict, client_id: str, client_secret: str) -> Credentials:
    """Build a Credentials object from the token dict returned by streamlit-oauth."""
    expiry = None
    if token_dict.get("expires_at"):
        expiry = datetime.fromtimestamp(float(token_dict["expires_at"]), tz=timezone.utc).replace(tzinfo=None)
    elif token_dict.get("expires_in"):
        expiry = datetime.utcnow() + timedelta(seconds=int(token_dict["expires_in"]))
    return Credentials(
        token=token_dict.get("access_token"),
        refresh_token=token_dict.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
        expiry=expiry,
    )


# ── File-based OAuth (local dev only) ─────────────────────────────────────────

def get_oauth_credentials(client_secrets_path: str) -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def load_cached_credentials() -> Optional[Credentials]:
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        return creds if creds.valid else None
    except Exception:
        return None


def revoke_oauth():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


# ── YouTube Analytics API ──────────────────────────────────────────────────────

def get_channel_analytics(creds: Credentials, channel_id: str, days: int = 28) -> dict:
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    # YouTube Analytics has a 2-3 day reporting lag — end 3 days ago to avoid empty rows
    end_date   = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=days + 3)).strftime("%Y-%m-%d")

    totals_resp = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views,estimatedMinutesWatched,averageViewDuration,likes,shares,subscribersGained",
    ).execute()

    daily_resp = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views,estimatedMinutesWatched",
        dimensions="day",
        sort="day",
    ).execute()

    has_data = bool(totals_resp.get("rows"))

    totals = {}
    if has_data:
        headers = [h["name"] for h in totals_resp["columnHeaders"]]
        totals = dict(zip(headers, totals_resp["rows"][0]))

    daily = []
    if daily_resp.get("rows"):
        daily = [
            {"date": r[0], "views": int(r[1]), "watch_minutes": int(r[2])}
            for r in daily_resp["rows"]
        ]

    return {
        "period_days": days,
        "start_date": start_date,
        "end_date": end_date,
        "has_data": has_data,
        "views": int(totals.get("views", 0)),
        "watch_minutes": int(totals.get("estimatedMinutesWatched", 0)),
        "avg_view_duration_sec": int(totals.get("averageViewDuration", 0)),
        "likes": int(totals.get("likes", 0)),
        "shares": int(totals.get("shares", 0)),
        "subscribers_gained": int(totals.get("subscribersGained", 0)),
        "daily": daily,
    }
