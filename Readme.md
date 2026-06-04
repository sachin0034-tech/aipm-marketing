# Creator Intelligence Dashboard

A unified marketing analytics dashboard for **YouTube**, **Substack**, and **LinkedIn** — built with Streamlit. Fetch live data, visualise engagement trends, and save snapshots to Snowflake with one click.

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in your credentials
streamlit run app.py
```

Open **http://localhost:8501** → go to **🔐 Authentication** and paste your credentials.

---

## Architecture Overview

```
app.py                  ← Streamlit UI (sidebar nav + 4 pages)
├── youtube_client.py   ← YouTube Data API v3 + Analytics API
├── substack_author.py  ← Substack public API (unofficial)
├── substack_client.py  ← Apify actor wrapper (leaderboard)
├── linkedin_client.py  ← Apify actor wrapper (company posts)
└── snowflake_client.py ← Snowflake connector (3 tables)
```

---

## 1. YouTube

### APIs Used

| API | Purpose | Auth |
|-----|---------|------|
| YouTube Data API v3 | Channel stats, video details, subscriber count | API Key |
| YouTube Analytics API | Views, watch time, likes, subscribers gained | OAuth 2.0 |

### What We Fetch

- **Channel**: name, description, thumbnail, country, join date, subscribers, total views, video count
- **Videos** (last 9): title, thumbnail, views, likes, comments, duration, publish date
- **Analytics** (7 / 28 / 90 day window): views, watch time, avg view duration, likes, subscribers gained, daily breakdown

### Step 1 — Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**
3. Give it any name (e.g. `creator-dashboard`) → **Create**

### Step 2 — Enable the APIs

1. Left menu → **APIs & Services** → **Library**
2. Search **YouTube Data API v3** → click it → **Enable**
3. Search **YouTube Analytics API** → click it → **Enable**

### Step 3 — Create an API Key (for channel + video data)

1. **APIs & Services** → **Credentials** → **+ Create Credentials** → **API Key**
2. Copy the key
3. Paste it into the **Authentication** page → YouTube → Data API Key field

> The API Key is enough to see channel stats and all video details. No login required.

### Step 4 — Create OAuth Credentials (for Analytics only)

Analytics data (watch time, views over time, subscriber growth) is private — Google requires you to prove you own the channel.

1. **Credentials** → **+ Create Credentials** → **OAuth 2.0 Client ID**
2. If prompted, click **Configure Consent Screen**:
   - User type: **External**
   - App name: anything (e.g. `Creator Dashboard`)
   - Fill in your email → **Save and Continue** through all steps
3. Back on Create OAuth Client ID:
   - Application type: **Desktop app**
   - Name: anything → **Create**
4. Click **Download JSON** → save the file
5. Go to **Authentication** page → upload it under **OAuth client_secrets.json**
6. Click **Connect Google Account** — a browser tab opens, sign in with the Google account that **owns the channel**, grant access

> The OAuth token is saved to `token.json` in the project folder. The app reuses it on future runs — you only need to connect once.

---

## 2. Substack

### Two Separate Data Sources

#### 2a. My Newsletter (your own newsletter)

Uses **Substack's unofficial public API** — no credentials needed, just your newsletter URL.

| Endpoint | What it returns |
|----------|----------------|
| `substack.com/api/v1/user/{handle}/public_profile` | Newsletter name, author, logo, payment status |
| `{subdomain}.substack.com/api/v1/posts` | All posts with likes, comments, restacks, word count, tags, audience (free/paid) |

**What we fetch:**
- Publication profile: name, author, logo, description, payment status
- Every post ever published: title, date, audience type (free/paid), likes, comments, restacks, word count, tags, URL
- Aggregates: total posts, avg likes/post, avg comments/post, publishing frequency per month

**Supported URL formats:**
```
https://substack.com/@myaicommunity
https://myaicommunity.substack.com
myaicommunity.substack.com
```

#### 2b. Leaderboard (discover top newsletters)

Uses **Apify** to scrape Substack's public leaderboard across 31 categories.

**Actor**: `parsebird/substack-leaderboard-scraper`
**Input**:
```json
{
  "categories": ["bestseller", "technology", "business"],
  "boardTypes": ["paid", "rising"],
  "maxResults": 25
}
```
**What it returns per newsletter**: rank, name, author, description, subscriber count, category, board type, URL, logo

**All 31 category slugs**: `bestseller`, `technology`, `business`, `finance`, `politics`, `culture`, `health`, `science`, `food`, `sports`, `arts`, `music`, `fiction`, `history`, `international`, `environment`, `education`, `crypto`, `philosophy`, `humor`, `religion`, `self-improvement`, `parenting`, `travel`, `fashion`, `gaming`, `architecture`, `local-news`, `productivity`, `law`, `writing`

---

## 3. LinkedIn

Uses **Apify** to scrape company page posts without requiring LinkedIn cookies or login.

**Actor**: `apimaestro/linkedin-company-posts`
**Input**:
```json
{
  "company_name": "mahesh-ai-pm-community",
  "limit": 100,
  "sort": "recent"
}
```

> `company_name` is the slug from your LinkedIn URL: `linkedin.com/company/`**`mahesh-ai-pm-community`**`/`

**What it returns per post:**
- Post text, URL, post type (regular / article / video)
- Date and timestamp
- Reaction breakdown: total reactions, likes, celebrates, supports, loves, insightful
- Comments count
- Reposts count
- Total engagement (reactions + comments + reposts)

**What we compute:**
- Follower count (from author object on each post)
- Avg reactions per post, avg comments per post
- Avg engagement rate = (total engagement / posts / followers) × 100
- Reaction type breakdown (pie chart)
- Posting frequency per month (bar chart)

### Getting Your Apify Token

1. Sign up at [console.apify.com](https://console.apify.com)
2. Click your avatar (top right) → **Settings** → **Integrations**
3. Copy the **Personal API token**
4. Paste it into **Authentication** → Apify Token

> Both the Substack Leaderboard actor and the LinkedIn actor use the same Apify token.

---

## 4. Snowflake

### Three Tables (auto-created on first Save)

| Table | When it's written | Rows |
|-------|------------------|------|
| `CREATOR_YOUTUBE_SNAPSHOTS` | Click "❄️ Save YouTube Snapshot" | 1 row per click |
| `CREATOR_SUBSTACK_SNAPSHOTS` | Click "❄️ Save Newsletter Snapshot" | 1 row per click |
| `CREATOR_LINKEDIN_SNAPSHOTS` | Click "❄️ Save LinkedIn Snapshot" | 1 row per click |

Every row is timestamped. Repeated saves build a history — the marketing team can track growth over time by comparing snapshots.

### What Each Table Stores

**CREATOR_YOUTUBE_SNAPSHOTS**
```
CHANNEL_ID, CHANNEL_NAME, CHANNEL_DESCRIPTION, CHANNEL_THUMBNAIL_URL,
CHANNEL_COUNTRY, CHANNEL_JOINED_DATE, CHANNEL_SUBSCRIBERS,
CHANNEL_TOTAL_VIEWS, CHANNEL_VIDEO_COUNT, UPLOADS_PLAYLIST_ID,
ANALYTICS_PERIOD_DAYS, ANALYTICS_START_DATE, ANALYTICS_END_DATE,
ANALYTICS_HAS_DATA, ANALYTICS_VIEWS, ANALYTICS_WATCH_MINUTES,
ANALYTICS_AVG_DURATION_SEC, ANALYTICS_LIKES, ANALYTICS_SUBSCRIBERS_GAINED,
VIDEOS (VARIANT),          ← full JSON array of all video objects
ANALYTICS_DAILY (VARIANT)  ← daily {date, views, watch_minutes}
```

**CREATOR_SUBSTACK_SNAPSHOTS**
```
NEWSLETTER_NAME, NEWSLETTER_URL, NEWSLETTER_SUBDOMAIN,
AUTHOR_NAME, AUTHOR_PHOTO_URL, LOGO_URL, COVER_URL,
DESCRIPTION, PAYMENTS_ENABLED, SUBSCRIBER_COUNT,
TOTAL_POSTS, TOTAL_LIKES, TOTAL_COMMENTS, TOTAL_RESTACKS,
FREE_POSTS_COUNT, PAID_POSTS_COUNT,
AVG_LIKES_PER_POST, AVG_COMMENTS_PER_POST, AVG_RESTACKS_PER_POST,
POSTS (VARIANT)  ← full JSON array: {id, title, date, audience, likes,
                    comments, restacks, wordcount, engagement, tags, url}
```

**CREATOR_LINKEDIN_SNAPSHOTS**
```
COMPANY_NAME, COMPANY_SLUG, COMPANY_URL, COMPANY_LOGO_URL, FOLLOWERS,
POSTS_ANALYSED,
TOTAL_REACTIONS, TOTAL_LIKES, TOTAL_CELEBRATES, TOTAL_SUPPORTS,
TOTAL_LOVES, TOTAL_INSIGHTFUL, TOTAL_COMMENTS, TOTAL_REPOSTS, TOTAL_ENGAGEMENT,
AVG_REACTIONS_PER_POST, AVG_COMMENTS_PER_POST, AVG_ENGAGEMENT_RATE,
POSTS (VARIANT)  ← full JSON array: {text, post_type, date, reactions,
                    likes, celebrates, supports, loves, insightful,
                    comments, reposts, engagement, url}
```

### Querying VARIANT Columns

VARIANT columns store the full JSON arrays. Use `LATERAL FLATTEN` to query individual posts:

```sql
-- Top 10 Substack posts by engagement across all snapshots
SELECT
    s.FETCHED_AT,
    s.NEWSLETTER_NAME,
    p.value:title::STRING        AS post_title,
    p.value:date::DATE           AS post_date,
    p.value:likes::INT           AS likes,
    p.value:comments::INT        AS comments,
    p.value:engagement::INT      AS engagement
FROM CREATOR_SUBSTACK_SNAPSHOTS s,
LATERAL FLATTEN(input => s.POSTS) p
ORDER BY engagement DESC
LIMIT 10;

-- LinkedIn engagement rate trend over time
SELECT
    FETCHED_AT::DATE AS snapshot_date,
    FOLLOWERS,
    TOTAL_REACTIONS,
    AVG_ENGAGEMENT_RATE
FROM CREATOR_LINKEDIN_SNAPSHOTS
ORDER BY FETCHED_AT;
```

### Snowflake Setup

#### Account details (this project)

| Field | Value |
|-------|-------|
| Account identifier | `LUMNPAC-EF71075` |
| Organization | `LUMNPAC` |
| Account name | `EF71075` |
| Server URL | `LUMNPAC-EF71075.snowflakecomputing.com` |
| Database | `AIPM_GROWTH_DB` |
| Warehouse | `COMPUTE_WH` |
| Cloud | AWS / Enterprise |

---

#### Step 1 — Run this SQL first (create role, user, and permissions)

Log into [app.snowflake.com](https://app.snowflake.com), open a worksheet, and run:

```sql
USE ROLE ACCOUNTADMIN;

-- Create a dedicated read-only role for Amplitude
CREATE ROLE IF NOT EXISTS AMPLITUDE_ROLE;

-- Create the Amplitude user (password auth for Amplitude's connector)
CREATE USER IF NOT EXISTS AMPLITUDE_USER
    PASSWORD             = 'AmplitudePass2024!'
    DEFAULT_ROLE         = AMPLITUDE_ROLE
    DEFAULT_WAREHOUSE    = COMPUTE_WH
    MUST_CHANGE_PASSWORD = FALSE;

-- Assign the role to the user
GRANT ROLE AMPLITUDE_ROLE TO USER AMPLITUDE_USER;

-- Grant warehouse access
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE AMPLITUDE_ROLE;

-- Grant database and schema access
GRANT USAGE ON DATABASE AIPM_GROWTH_DB TO ROLE AMPLITUDE_ROLE;
GRANT USAGE ON SCHEMA AIPM_GROWTH_DB.PUBLIC TO ROLE AMPLITUDE_ROLE;

-- Grant read-only access to the three tables
GRANT SELECT ON TABLE AIPM_GROWTH_DB.PUBLIC.CREATOR_YOUTUBE_SNAPSHOTS  TO ROLE AMPLITUDE_ROLE;
GRANT SELECT ON TABLE AIPM_GROWTH_DB.PUBLIC.CREATOR_SUBSTACK_SNAPSHOTS TO ROLE AMPLITUDE_ROLE;
GRANT SELECT ON TABLE AIPM_GROWTH_DB.PUBLIC.CREATOR_LINKEDIN_SNAPSHOTS TO ROLE AMPLITUDE_ROLE;

-- Verify grants were applied
SHOW GRANTS TO USER AMPLITUDE_USER;
```

---

#### Step 2 — Generate RSA key pair on your machine

Amplitude's Snowflake connector uses RSA key-pair authentication (not plain password). Run these commands in Terminal:

```bash
# Generate private key (unencrypted)
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out amplitude_rsa_key.p8 -nocrypt

# Generate matching public key from the private key
openssl rsa -in amplitude_rsa_key.p8 -pubout -out amplitude_rsa_key.pub
```

This creates two files:
- `amplitude_rsa_key.p8` → **private key** — you paste this into Amplitude
- `amplitude_rsa_key.pub` → **public key** — you put this into Snowflake

To get the public key content without headers (needed for Snowflake):

```bash
grep -v "PUBLIC KEY" amplitude_rsa_key.pub | tr -d '\n'
```

Copy that one-line output.

---

#### Step 3 — Assign the public key to AMPLITUDE_USER in Snowflake

Back in your Snowflake worksheet, run:

```sql
USE ROLE ACCOUNTADMIN;

ALTER USER AMPLITUDE_USER SET RSA_PUBLIC_KEY='paste_the_one_line_public_key_here';
```

Replace `paste_the_one_line_public_key_here` with the output from Step 2 — the long base64 string with no headers or line breaks.

---

#### Step 4 — Connect Amplitude to Snowflake

In Amplitude → **Data** → **Sources** → **Add Data Source** → **Snowflake**, enter:

| Field | Value |
|-------|-------|
| Account | `LUMNPAC-EF71075` |
| Database | `AIPM_GROWTH_DB` |
| Warehouse | `COMPUTE_WH` |
| Username | `AMPLITUDE_USER` |
| Role | `AMPLITUDE_ROLE` |
| Private Key | full contents of `amplitude_rsa_key.p8` (including `-----BEGIN PRIVATE KEY-----` headers) |
| Passphrase | leave empty |

Click **Test Connection** — it should pass.

---

#### Step 5 — Configure the import queries

Add one source per platform. Paste these queries. Amplitude automatically replaces `${lastRunTime}` with the timestamp of the last successful sync so no duplicates are ever imported.

**YouTube — one event per video**
```sql
SELECT
    'youtube_video'                                     AS "event_type",
    OBJECT_CONSTRUCT(
        'profile_type',     s.PROFILE_TYPE,
        'profile_label',    s.PROFILE_LABEL,
        'channel_name',     s.CHANNEL_NAME,
        'channel_id',       s.CHANNEL_ID,
        'title',            v.value:title::STRING,
        'views',            v.value:views::INT,
        'likes',            v.value:likes::INT,
        'comments',         v.value:comments::INT,
        'duration',         v.value:duration::STRING,
        'published_at',     v.value:published_at::STRING,
        'url',              v.value:url::STRING
    )                                                   AS "event_properties",
    DATE_PART('epoch_millisecond', s.FETCHED_AT)        AS "time",
    s.FETCHED_AT,
    s.CHANNEL_ID                                        AS "user_id"
FROM AIPM_GROWTH_DB.PUBLIC.CREATOR_YOUTUBE_SNAPSHOTS s,
LATERAL FLATTEN(input => s.VIDEOS) v
WHERE s.FETCHED_AT > TO_TIMESTAMP_NTZ('${lastRunTime}');
```

**Substack — one event per post**
```sql
SELECT
    'substack_post'                                     AS "event_type",
    OBJECT_CONSTRUCT(
        'profile_type',     s.PROFILE_TYPE,
        'profile_label',    s.PROFILE_LABEL,
        'newsletter_name',  s.NEWSLETTER_NAME,
        'author',           s.AUTHOR_NAME,
        'title',            p.value:title::STRING,
        'audience',         p.value:audience::STRING,
        'type',             p.value:type::STRING,
        'likes',            p.value:likes::INT,
        'comments',         p.value:comments::INT,
        'restacks',         p.value:restacks::INT,
        'wordcount',        p.value:wordcount::INT,
        'engagement',       p.value:engagement::INT,
        'date',             p.value:date::STRING,
        'url',              p.value:url::STRING
    )                                                   AS "event_properties",
    DATE_PART('epoch_millisecond', s.FETCHED_AT)        AS "time",
    s.FETCHED_AT,
    s.NEWSLETTER_SUBDOMAIN                              AS "user_id"
FROM AIPM_GROWTH_DB.PUBLIC.CREATOR_SUBSTACK_SNAPSHOTS s,
LATERAL FLATTEN(input => s.POSTS) p
WHERE s.FETCHED_AT > TO_TIMESTAMP_NTZ('${lastRunTime}');
```

**LinkedIn — one event per post**
```sql
SELECT
    'linkedin_post'                                     AS "event_type",
    OBJECT_CONSTRUCT(
        'profile_type',     c.PROFILE_TYPE,
        'profile_label',    c.PROFILE_LABEL,
        'company_name',     c.COMPANY_NAME,
        'company_slug',     c.COMPANY_SLUG,
        'text_preview',     p.value:text_preview::STRING,
        'post_type',        p.value:post_type::STRING,
        'reactions',        p.value:reactions::INT,
        'likes',            p.value:likes::INT,
        'celebrates',       p.value:celebrates::INT,
        'supports',         p.value:supports::INT,
        'loves',            p.value:loves::INT,
        'insightful',       p.value:insightful::INT,
        'comments',         p.value:comments::INT,
        'reposts',          p.value:reposts::INT,
        'engagement',       p.value:engagement::INT,
        'date',             p.value:date::STRING,
        'url',              p.value:url::STRING
    )                                                   AS "event_properties",
    DATE_PART('epoch_millisecond', c.FETCHED_AT)        AS "time",
    c.FETCHED_AT,
    c.COMPANY_SLUG                                      AS "user_id"
FROM AIPM_GROWTH_DB.PUBLIC.CREATOR_LINKEDIN_SNAPSHOTS c,
LATERAL FLATTEN(input => c.POSTS) p
WHERE c.FETCHED_AT > TO_TIMESTAMP_NTZ('${lastRunTime}');
```

Set sync schedule to **daily**. Every time you click a Save button in the dashboard, a new row lands in Snowflake and Amplitude picks it up within 24 hours.

---

> **Keep `amplitude_rsa_key.p8` safe** — treat it like a password. Add it to `.gitignore` and never commit it.

> Tables are created automatically the first time you click a Save button in the dashboard. No manual `CREATE TABLE` needed.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
# YouTube
YOUTUBE_API_KEY=AIza...

# Apify (Substack Leaderboard + LinkedIn)
APIFY_TOKEN=apify_api_...

# Snowflake
SNOWFLAKE_ACCOUNT=orgname-accountname
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=CREATOR_INTELLIGENCE
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
```

Values set in `.env` are loaded as defaults. You can override any of them live in the **🔐 Authentication** page without editing the file.

---

## What Cannot Be Fetched

| Data | Reason |
|------|--------|
| LinkedIn follower growth over time | Requires LinkedIn Marketing API (gated partnership) |
| LinkedIn impressions / CTR | Private — only in LinkedIn Analytics dashboard |
| Substack paid subscriber count | Private server-side — not in any public API |
| Substack email open rates | Private — only in Substack dashboard |
| YouTube exact subscriber count (hidden channels) | Channels can hide subscriber counts from the API |

---

## File Reference

| File | Purpose |
|------|---------|
| `app.py` | Streamlit app — all UI, navigation, page rendering |
| `youtube_client.py` | YouTube Data API v3 + Analytics API calls |
| `substack_author.py` | Substack public API — your newsletter data |
| `substack_client.py` | Apify `parsebird/substack-leaderboard-scraper` wrapper |
| `linkedin_client.py` | Apify `apimaestro/linkedin-company-posts` wrapper |
| `snowflake_client.py` | Snowflake connector — DDL + insert for all 3 tables |
| `requirements.txt` | Python dependencies |
| `.env.example` | Credential template (safe to commit) |
| `.env` | Your actual credentials (gitignored) |
| `token.json` | YouTube OAuth token (gitignored, auto-created) |
| `client_secrets.json` | YouTube OAuth client secrets (gitignored) |
