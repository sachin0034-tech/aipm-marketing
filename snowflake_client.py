import json
from datetime import datetime
import snowflake.connector


# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection(account, user, password, database, schema, warehouse):
    # qmark paramstyle sends values as true server-side bind parameters,
    # so single quotes inside JSON strings are never SQL-escaped.
    return snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        database=database,
        schema=schema,
        warehouse=warehouse,
        client_session_keep_alive=True,
        paramstyle="qmark",
    )


def test_connection(account, user, password, database, schema, warehouse) -> str:
    conn = get_connection(account, user, password, database, schema, warehouse)
    cur = conn.cursor()
    cur.execute("SELECT CURRENT_USER(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()")
    row = cur.fetchone()
    conn.close()
    return f"Connected as {row[0]} · DB: {row[1]} · Schema: {row[2]} · WH: {row[3]}"


# ── DDL ────────────────────────────────────────────────────────────────────────

DDL_YOUTUBE = """
CREATE TABLE IF NOT EXISTS CREATOR_YOUTUBE_SNAPSHOTS (
    SNAPSHOT_ID                  NUMBER AUTOINCREMENT PRIMARY KEY,
    FETCHED_AT                   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PROFILE_TYPE                 VARCHAR(20)  DEFAULT 'own',
    PROFILE_LABEL                VARCHAR(256) DEFAULT '',

    -- Channel core fields
    CHANNEL_ID                   VARCHAR(64),
    CHANNEL_NAME                 VARCHAR(512),
    CHANNEL_DESCRIPTION          TEXT,
    CHANNEL_THUMBNAIL_URL        VARCHAR(1024),
    CHANNEL_COUNTRY              VARCHAR(10),
    CHANNEL_JOINED_DATE          DATE,
    CHANNEL_SUBSCRIBERS          NUMBER,
    CHANNEL_TOTAL_VIEWS          NUMBER,
    CHANNEL_VIDEO_COUNT          NUMBER,
    UPLOADS_PLAYLIST_ID          VARCHAR(64),

    -- Analytics window (NULL if OAuth not connected)
    ANALYTICS_PERIOD_DAYS        NUMBER,
    ANALYTICS_START_DATE         DATE,
    ANALYTICS_END_DATE           DATE,
    ANALYTICS_HAS_DATA           BOOLEAN,
    ANALYTICS_VIEWS              NUMBER,
    ANALYTICS_WATCH_MINUTES      NUMBER,
    ANALYTICS_AVG_DURATION_SEC   NUMBER,
    ANALYTICS_LIKES              NUMBER,
    ANALYTICS_SUBSCRIBERS_GAINED NUMBER,

    -- Full detail arrays (queryable via LATERAL FLATTEN)
    VIDEOS                       VARIANT,   -- [{id,title,subtitle,thumbnail,published_at,views,likes,comments,duration,url}]
    ANALYTICS_DAILY              VARIANT    -- [{date,views,watch_minutes}]
)
"""

DDL_SUBSTACK = """
CREATE TABLE IF NOT EXISTS CREATOR_SUBSTACK_SNAPSHOTS (
    SNAPSHOT_ID           NUMBER AUTOINCREMENT PRIMARY KEY,
    FETCHED_AT            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PROFILE_TYPE          VARCHAR(20)  DEFAULT 'own',
    PROFILE_LABEL         VARCHAR(256) DEFAULT '',

    -- Publication profile
    NEWSLETTER_NAME       VARCHAR(512),
    NEWSLETTER_URL        VARCHAR(1024),
    NEWSLETTER_SUBDOMAIN  VARCHAR(256),
    AUTHOR_NAME           VARCHAR(512),
    AUTHOR_PHOTO_URL      VARCHAR(1024),
    LOGO_URL              VARCHAR(1024),
    COVER_URL             VARCHAR(1024),
    DESCRIPTION           TEXT,
    PAYMENTS_ENABLED      BOOLEAN,
    SUBSCRIBER_COUNT      NUMBER,

    -- Aggregate metrics
    TOTAL_POSTS           NUMBER,
    TOTAL_LIKES           NUMBER,
    TOTAL_COMMENTS        NUMBER,
    TOTAL_RESTACKS        NUMBER,
    FREE_POSTS_COUNT      NUMBER,
    PAID_POSTS_COUNT      NUMBER,
    AVG_LIKES_PER_POST    FLOAT,
    AVG_COMMENTS_PER_POST FLOAT,
    AVG_RESTACKS_PER_POST FLOAT,

    -- Full posts array
    -- Each item: {id,title,subtitle,date,month,audience,is_paid,type,
    --             likes,comments,restacks,wordcount,engagement,cover,url,tags,author}
    POSTS                 VARIANT
)
"""

DDL_LINKEDIN = """
CREATE TABLE IF NOT EXISTS CREATOR_LINKEDIN_SNAPSHOTS (
    SNAPSHOT_ID           NUMBER AUTOINCREMENT PRIMARY KEY,
    FETCHED_AT            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),

    PROFILE_TYPE          VARCHAR(20)  DEFAULT 'own',
    PROFILE_LABEL         VARCHAR(256) DEFAULT '',

    -- Company info
    COMPANY_NAME          VARCHAR(512),
    COMPANY_SLUG          VARCHAR(256),
    COMPANY_URL           VARCHAR(1024),
    COMPANY_LOGO_URL      VARCHAR(1024),
    FOLLOWERS             NUMBER,

    -- Aggregate metrics
    POSTS_ANALYSED        NUMBER,
    TOTAL_REACTIONS       NUMBER,
    TOTAL_LIKES           NUMBER,
    TOTAL_CELEBRATES      NUMBER,
    TOTAL_SUPPORTS        NUMBER,
    TOTAL_LOVES           NUMBER,
    TOTAL_INSIGHTFUL      NUMBER,
    TOTAL_COMMENTS        NUMBER,
    TOTAL_REPOSTS         NUMBER,
    TOTAL_ENGAGEMENT      NUMBER,
    AVG_REACTIONS_PER_POST FLOAT,
    AVG_COMMENTS_PER_POST  FLOAT,
    AVG_ENGAGEMENT_RATE    FLOAT,

    -- Full posts array
    -- Each item: {url,text,post_type,media_type,date,month,week,timestamp,
    --             reactions,likes,celebrates,supports,loves,insightful,
    --             comments,reposts,engagement}
    POSTS                 VARIANT
)
"""


# ── Save helpers ───────────────────────────────────────────────────────────────

def _jdump(obj) -> str:
    def _default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, default=_default)


# Adds PROFILE_TYPE / PROFILE_LABEL to existing tables that predate this change.
_MIGRATIONS = [
    "ALTER TABLE CREATOR_YOUTUBE_SNAPSHOTS  ADD COLUMN IF NOT EXISTS PROFILE_TYPE  VARCHAR(20)  DEFAULT 'own'",
    "ALTER TABLE CREATOR_YOUTUBE_SNAPSHOTS  ADD COLUMN IF NOT EXISTS PROFILE_LABEL VARCHAR(256) DEFAULT ''",
    "ALTER TABLE CREATOR_SUBSTACK_SNAPSHOTS ADD COLUMN IF NOT EXISTS PROFILE_TYPE  VARCHAR(20)  DEFAULT 'own'",
    "ALTER TABLE CREATOR_SUBSTACK_SNAPSHOTS ADD COLUMN IF NOT EXISTS PROFILE_LABEL VARCHAR(256) DEFAULT ''",
    "ALTER TABLE CREATOR_LINKEDIN_SNAPSHOTS ADD COLUMN IF NOT EXISTS PROFILE_TYPE  VARCHAR(20)  DEFAULT 'own'",
    "ALTER TABLE CREATOR_LINKEDIN_SNAPSHOTS ADD COLUMN IF NOT EXISTS PROFILE_LABEL VARCHAR(256) DEFAULT ''",
]


def _run(creds: dict, ddl: str, sql: str, params: tuple):
    conn = get_connection(**creds)
    try:
        cur = conn.cursor()
        cur.execute(ddl)
        for m in _MIGRATIONS:
            try:
                cur.execute(m)
            except Exception:
                pass
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ── YouTube ────────────────────────────────────────────────────────────────────

def save_youtube(creds: dict, channel_info: dict, videos: list, analytics: dict,
                 profile_type: str = "own", profile_label: str = ""):
    a = analytics or {}
    _run(
        creds, DDL_YOUTUBE,
        """
        INSERT INTO CREATOR_YOUTUBE_SNAPSHOTS (
            PROFILE_TYPE, PROFILE_LABEL,
            CHANNEL_ID, CHANNEL_NAME, CHANNEL_DESCRIPTION, CHANNEL_THUMBNAIL_URL,
            CHANNEL_COUNTRY, CHANNEL_JOINED_DATE, CHANNEL_SUBSCRIBERS,
            CHANNEL_TOTAL_VIEWS, CHANNEL_VIDEO_COUNT, UPLOADS_PLAYLIST_ID,
            ANALYTICS_PERIOD_DAYS, ANALYTICS_START_DATE, ANALYTICS_END_DATE,
            ANALYTICS_HAS_DATA, ANALYTICS_VIEWS, ANALYTICS_WATCH_MINUTES,
            ANALYTICS_AVG_DURATION_SEC, ANALYTICS_LIKES, ANALYTICS_SUBSCRIBERS_GAINED,
            VIDEOS, ANALYTICS_DAILY
        )
        SELECT ?, ?,
               ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
               ?, ?, ?, ?, ?, ?, ?, ?, ?,
               PARSE_JSON(?), PARSE_JSON(?)
        """,
        [
            profile_type, profile_label,
            channel_info.get("id"),
            channel_info.get("name"),
            channel_info.get("description"),
            channel_info.get("thumbnail"),
            channel_info.get("country"),
            channel_info.get("published_at"),
            channel_info.get("subscribers"),
            channel_info.get("total_views"),
            channel_info.get("video_count"),
            channel_info.get("uploads_playlist_id"),
            a.get("period_days"),
            a.get("start_date"),
            a.get("end_date"),
            a.get("has_data"),
            a.get("views"),
            a.get("watch_minutes"),
            a.get("avg_view_duration_sec"),
            a.get("likes"),
            a.get("subscribers_gained"),
            _jdump(videos or []),
            _jdump(a.get("daily") or []),
        ],
    )


# ── Substack ───────────────────────────────────────────────────────────────────

def save_substack(creds: dict, profile: dict, posts: list,
                  profile_type: str = "own", profile_label: str = ""):
    n = len(posts)
    total_likes     = sum(p["likes"]    for p in posts)
    total_comments  = sum(p["comments"] for p in posts)
    total_restacks  = sum(p["restacks"] for p in posts)
    paid_count      = sum(1 for p in posts if p["is_paid"])
    free_count      = n - paid_count
    avg_likes       = round(total_likes    / n, 4) if n else 0
    avg_comments    = round(total_comments / n, 4) if n else 0
    avg_restacks    = round(total_restacks / n, 4) if n else 0

    _run(
        creds, DDL_SUBSTACK,
        """
        INSERT INTO CREATOR_SUBSTACK_SNAPSHOTS (
            PROFILE_TYPE, PROFILE_LABEL,
            NEWSLETTER_NAME, NEWSLETTER_URL, NEWSLETTER_SUBDOMAIN,
            AUTHOR_NAME, AUTHOR_PHOTO_URL, LOGO_URL, COVER_URL,
            DESCRIPTION, PAYMENTS_ENABLED, SUBSCRIBER_COUNT,
            TOTAL_POSTS, TOTAL_LIKES, TOTAL_COMMENTS, TOTAL_RESTACKS,
            FREE_POSTS_COUNT, PAID_POSTS_COUNT,
            AVG_LIKES_PER_POST, AVG_COMMENTS_PER_POST, AVG_RESTACKS_PER_POST,
            POSTS
        )
        SELECT ?, ?,
               ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
               ?, ?, ?, ?, ?, ?, ?, ?, ?,
               PARSE_JSON(?)
        """,
        [
            profile_type, profile_label,
            profile.get("name"),
            profile.get("url"),
            profile.get("subdomain"),
            profile.get("author"),
            profile.get("author_photo"),
            profile.get("logo"),
            profile.get("cover"),
            profile.get("description"),
            profile.get("payments"),
            profile.get("subscribers"),
            n, total_likes, total_comments, total_restacks,
            free_count, paid_count,
            avg_likes, avg_comments, avg_restacks,
            _jdump(posts),
        ],
    )


# ── LinkedIn ───────────────────────────────────────────────────────────────────

def save_linkedin(creds: dict, company: dict, posts: list,
                  profile_type: str = "own", profile_label: str = ""):
    n = len(posts)
    total_reactions  = sum(p["reactions"]  for p in posts)
    total_likes      = sum(p["likes"]      for p in posts)
    total_celebrates = sum(p["celebrates"] for p in posts)
    total_supports   = sum(p["supports"]   for p in posts)
    total_loves      = sum(p["loves"]      for p in posts)
    total_insightful = sum(p["insightful"] for p in posts)
    total_comments   = sum(p["comments"]   for p in posts)
    total_reposts    = sum(p["reposts"]    for p in posts)
    total_engagement = sum(p["engagement"] for p in posts)
    avg_reactions    = round(total_reactions  / n, 4) if n else 0
    avg_comments_p   = round(total_comments   / n, 4) if n else 0
    followers        = company.get("followers") or 1
    eng_rate         = round((total_engagement / (n * followers)) * 100, 6) if n else 0

    _run(
        creds, DDL_LINKEDIN,
        """
        INSERT INTO CREATOR_LINKEDIN_SNAPSHOTS (
            PROFILE_TYPE, PROFILE_LABEL,
            COMPANY_NAME, COMPANY_SLUG, COMPANY_URL, COMPANY_LOGO_URL, FOLLOWERS,
            POSTS_ANALYSED,
            TOTAL_REACTIONS, TOTAL_LIKES, TOTAL_CELEBRATES, TOTAL_SUPPORTS,
            TOTAL_LOVES, TOTAL_INSIGHTFUL, TOTAL_COMMENTS, TOTAL_REPOSTS, TOTAL_ENGAGEMENT,
            AVG_REACTIONS_PER_POST, AVG_COMMENTS_PER_POST, AVG_ENGAGEMENT_RATE,
            POSTS
        )
        SELECT ?, ?,
               ?, ?, ?, ?, ?,
               ?,
               ?, ?, ?, ?, ?, ?, ?, ?, ?,
               ?, ?, ?,
               PARSE_JSON(?)
        """,
        [
            profile_type, profile_label,
            company.get("name"),
            company.get("slug"),
            company.get("url"),
            company.get("logo"),
            company.get("followers"),
            n,
            total_reactions, total_likes, total_celebrates, total_supports,
            total_loves, total_insightful, total_comments, total_reposts, total_engagement,
            avg_reactions, avg_comments_p, eng_rate,
            _jdump(posts),
        ],
    )


# ── Fetch latest snapshot per profile (for comparison views) ──────────────────

def _fetch(creds: dict, sql: str) -> list:
    conn = get_connection(**creds)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_youtube_snapshots(creds: dict) -> list:
    """Latest snapshot per profile, all types."""
    return _fetch(creds, """
        SELECT s.*
        FROM CREATOR_YOUTUBE_SNAPSHOTS s
        INNER JOIN (
            SELECT COALESCE(NULLIF(PROFILE_LABEL,''), CHANNEL_NAME) AS profile_key,
                   MAX(FETCHED_AT) AS latest
            FROM CREATOR_YOUTUBE_SNAPSHOTS
            GROUP BY profile_key
        ) t
        ON COALESCE(NULLIF(s.PROFILE_LABEL,''), s.CHANNEL_NAME) = t.profile_key
       AND s.FETCHED_AT = t.latest
        ORDER BY s.PROFILE_TYPE, s.CHANNEL_NAME
    """)


def fetch_substack_snapshots(creds: dict) -> list:
    """Latest snapshot per profile, all types."""
    return _fetch(creds, """
        SELECT s.*
        FROM CREATOR_SUBSTACK_SNAPSHOTS s
        INNER JOIN (
            SELECT COALESCE(NULLIF(PROFILE_LABEL,''), NEWSLETTER_NAME) AS profile_key,
                   MAX(FETCHED_AT) AS latest
            FROM CREATOR_SUBSTACK_SNAPSHOTS
            GROUP BY profile_key
        ) t
        ON COALESCE(NULLIF(s.PROFILE_LABEL,''), s.NEWSLETTER_NAME) = t.profile_key
       AND s.FETCHED_AT = t.latest
        ORDER BY s.PROFILE_TYPE, s.NEWSLETTER_NAME
    """)


def fetch_linkedin_snapshots(creds: dict) -> list:
    """Latest snapshot per profile, all types."""
    return _fetch(creds, """
        SELECT s.*
        FROM CREATOR_LINKEDIN_SNAPSHOTS s
        INNER JOIN (
            SELECT COALESCE(NULLIF(PROFILE_LABEL,''), COMPANY_NAME) AS profile_key,
                   MAX(FETCHED_AT) AS latest
            FROM CREATOR_LINKEDIN_SNAPSHOTS
            GROUP BY profile_key
        ) t
        ON COALESCE(NULLIF(s.PROFILE_LABEL,''), s.COMPANY_NAME) = t.profile_key
       AND s.FETCHED_AT = t.latest
        ORDER BY s.PROFILE_TYPE, s.COMPANY_NAME
    """)
