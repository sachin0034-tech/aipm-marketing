import re
from datetime import datetime
from apify_client import ApifyClient

ACTOR_ID = "apimaestro/linkedin-company-posts"


def extract_company_slug(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    m = re.search(r"linkedin\.com/(?:company|school)/([\w-]+)", raw)
    if m:
        return m.group(1)
    if re.match(r"^[\w-]+$", raw):
        return raw
    raise ValueError(
        "Couldn't extract company slug from the URL.\n"
        "Expected format: https://www.linkedin.com/company/your-company-slug/\n"
        "                 https://www.linkedin.com/school/your-school-slug/"
    )


def fetch_company_posts(token: str, company_url: str, max_posts: int = 100) -> dict:
    slug  = extract_company_slug(company_url)
    client = ApifyClient(token)

    all_posts = []
    page = 1
    per_page = min(100, max_posts)

    while len(all_posts) < max_posts:
        run = client.actor(ACTOR_ID).call(run_input={
            "company_name": slug,
            "limit": per_page,
            "page_number": page,
            "sort": "recent",
        })
        batch = list(client.dataset(run["defaultDatasetId"]).list_items().items)
        if not batch:
            break
        all_posts.extend(batch)
        if len(batch) < per_page:
            break
        page += 1

    if not all_posts:
        raise ValueError(
            f"No posts found for '{slug}'. "
            "Check the company slug or try the full URL."
        )

    company = _parse_company(all_posts[0].get("author", {}), slug)
    posts   = [_parse_post(p) for p in all_posts[:max_posts]]
    posts.sort(key=lambda p: p["timestamp"])

    return {"company": company, "posts": posts}


def _parse_company(author: dict, slug: str) -> dict:
    return {
        "name":      author.get("name") or slug,
        "followers": int(author.get("follower_count") or 0),
        "logo":      author.get("logo_url") or "",
        "url":       author.get("company_url") or f"https://www.linkedin.com/company/{slug}/",
        "slug":      slug,
    }


def _parse_post(p: dict) -> dict:
    stats = p.get("stats") or {}
    dt_str = (p.get("posted_at") or {}).get("date") or ""
    ts     = (p.get("posted_at") or {}).get("timestamp") or 0

    try:
        dt         = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        post_date  = dt.date()
        post_month = dt.strftime("%Y-%m")
        post_week  = dt.strftime("%Y-W%W")
    except Exception:
        post_date = post_month = post_week = None

    total_reactions = int(stats.get("total_reactions") or 0)
    comments        = int(stats.get("comments") or 0)
    reposts         = int(stats.get("reposts") or 0)

    text = p.get("text") or ""

    media = p.get("media") or {}
    media_type = None
    if isinstance(media, dict) and media:
        media_type = media.get("type") or "image"

    return {
        "url":         p.get("post_url") or "",
        "text":        text,
        "text_preview": text[:120] + "…" if len(text) > 120 else text,
        "post_type":   p.get("post_type") or "regular",
        "media_type":  media_type,
        "date":        post_date,
        "month":       post_month,
        "week":        post_week,
        "timestamp":   ts,
        "reactions":   total_reactions,
        "likes":       int(stats.get("like") or 0),
        "celebrates":  int(stats.get("celebrate") or 0),
        "supports":    int(stats.get("support") or 0),
        "loves":       int(stats.get("love") or 0),
        "insightful":  int(stats.get("insight") or 0),
        "comments":    comments,
        "reposts":     reposts,
        "engagement":  total_reactions + comments + reposts,
    }
